"""人物抽取 + 人物关系图（design.md §11 人物系统 / §6.1 Story Graph）。

由 AI 抽取人物与关系，但**出场次数与重要度由程序在原文上统计得出**，
而非让模型拍脑袋——避免伪指标，也让 importance 可复现、可解释。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ai_service import AIService
from .parser import Novel
from .prompts import EXTRACT_CHARACTERS, SYSTEM_SCREENWRITER

_ROLES = {"protagonist", "supporting", "minor", "group"}


@dataclass
class Character:
    id: str
    name: str
    aka: list[str] = field(default_factory=list)
    role: str = "supporting"
    profile: str = ""
    goal: str = ""
    arc: str = ""
    appearances: int = 0
    importance: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "aka": self.aka, "role": self.role,
            "profile": self.profile, "goal": self.goal, "arc": self.arc,
            "appearances": self.appearances, "importance": self.importance,
        }


@dataclass
class Relation:
    source: str          # character id
    target: str          # character id
    type: str
    directed: bool = False
    weight: int = 1
    note: str = ""

    def to_dict(self) -> dict:
        return {"from": self.source, "to": self.target, "type": self.type,
                "directed": self.directed, "weight": self.weight, "note": self.note}


@dataclass
class CharacterSet:
    characters: list[Character]
    relations: list[Relation]

    def by_id(self, cid: str) -> Character | None:
        return next((c for c in self.characters if c.id == cid), None)

    def story_graph(self) -> dict:
        """供 Web UI 可视化的人物关系图数据。"""
        return {
            "nodes": [{"id": c.id, "name": c.name, "importance": c.importance,
                       "role": c.role} for c in self.characters],
            "edges": [r.to_dict() for r in self.relations],
        }


def _norm_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in _ROLES else "supporting"


def _count_appearances(text: str, names: list[str]) -> int:
    """在原文中统计该人物所有称呼的出现次数之和（真实数字）。"""
    return sum(text.count(n) for n in names if n)


def build_character_set(payload: dict, novel_text: str) -> CharacterSet:
    """把模型返回的 {characters, relations} 转成带 id、真实出场/重要度的 CharacterSet。

    纯函数，便于单测：不触网。
    """
    raw_chars = payload.get("characters", []) or []
    characters: list[Character] = []
    name_to_id: dict[str, str] = {}

    for i, rc in enumerate(raw_chars, start=1):
        name = (rc.get("name") or "").strip()
        if not name:
            continue
        cid = f"c{i}"
        aka = [a.strip() for a in (rc.get("aka") or []) if a and a.strip()]
        all_names = [name, *aka]
        char = Character(
            id=cid, name=name, aka=aka, role=_norm_role(rc.get("role", "")),
            profile=(rc.get("profile") or "").strip(),
            goal=(rc.get("goal") or "").strip(),
            arc=(rc.get("arc") or "").strip(),
            appearances=_count_appearances(novel_text, all_names),
        )
        characters.append(char)
        for n in all_names:
            name_to_id.setdefault(n, cid)

    # 关系：把 name 映射成 id，丢弃端点不存在的
    relations: list[Relation] = []
    degree: dict[str, int] = {c.id: 0 for c in characters}
    for rr in payload.get("relations", []) or []:
        sid = name_to_id.get((rr.get("from") or "").strip())
        tid = name_to_id.get((rr.get("to") or "").strip())
        if not sid or not tid or sid == tid:
            continue
        relations.append(Relation(
            source=sid, target=tid, type=(rr.get("type") or "关联").strip(),
            directed=bool(rr.get("directed", False)),
            note=(rr.get("note") or "").strip(),
        ))
        degree[sid] += 1
        degree[tid] += 1

    _assign_importance(characters, degree)
    return CharacterSet(characters=characters, relations=relations)


def _assign_importance(characters: list[Character], degree: dict[str, int]) -> None:
    """importance = 归一化(出场次数 + 2×关系度数)。真实可复现。"""
    raw = {c.id: c.appearances + 2 * degree.get(c.id, 0) for c in characters}
    top = max(raw.values(), default=0) or 1
    for c in characters:
        c.importance = round(raw[c.id] / top, 2)
    # 按重要度降序，方便展示
    characters.sort(key=lambda c: c.importance, reverse=True)


def _novel_to_prompt_text(novel: Novel, per_chapter_limit: int = 6000) -> str:
    parts = []
    for c in novel.chapters:
        body = c.text[:per_chapter_limit]
        parts.append(f"【第{c.index}章 {c.display_title}】\n{body}")
    return "\n\n".join(parts)


def extract_characters(novel: Novel, ai: AIService) -> CharacterSet:
    """调用 AI 抽取人物与关系，统计真实出场与重要度。"""
    novel_text = "\n".join(c.text for c in novel.chapters)
    prompt = EXTRACT_CHARACTERS.replace("{novel}", _novel_to_prompt_text(novel))
    payload = ai.chat_json(prompt, system=SYSTEM_SCREENWRITER, task="extract_characters")
    return build_character_set(payload, novel_text)
