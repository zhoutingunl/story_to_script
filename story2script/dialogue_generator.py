"""对白生成（design.md §12 对白生成 / §6.3 Dialogue Expansion）。

把每个场景的原文片段改写成**有序的剧本元素流**：动作(action)、对白(dialogue)、
转场(transition)。对白区分两种来源：
  - extracted：原文已有的台词（引号内）
  - expanded ：原文只有心理/叙述、由 AI 扩写出来的新台词

诚信设计
--------
模型自报的 mode 不可全信，因此这里**用程序在原文上复核**每句台词：
若台词与原文有足够长的公共子串 → 判定 extracted，否则 expanded，覆盖模型标注。
这样 YAML 里的 `mode` 是可验证的事实，作者能一眼区分"原著台词"与"AI 补写"。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .ai_service import AIService
from .parser import Chapter
from .prompts import DIALOGUE_MODE_HINTS, GENERATE_DIALOGUE, SYSTEM_SCREENWRITER
from .scene_planner import Scene, scene_text

_KINDS = {"action", "dialogue", "transition"}
_PUNCT = re.compile(r"[\s，。！？、：；“”‘’\"'（）()「」『』…—.,!?:;]")


@dataclass
class Element:
    kind: str
    text: str = ""              # action / transition
    character: str = ""         # dialogue
    parenthetical: str = ""
    line: str = ""
    mode: str = ""              # extracted | expanded

    def to_dict(self) -> dict:
        if self.kind == "dialogue":
            d = {"kind": "dialogue", "character": self.character,
                 "line": self.line, "mode": self.mode}
            if self.parenthetical:
                d["parenthetical"] = self.parenthetical
            return d
        return {"kind": self.kind, "text": self.text}


def _normalize(s: str) -> str:
    return _PUNCT.sub("", s or "")


def verify_mode(line: str, source: str, min_run: int = 5) -> str:
    """在原文上复核台词来源：足够长的公共子串 → extracted，否则 expanded。"""
    ln, src = _normalize(line), _normalize(source)
    if not ln:
        return "expanded"
    match = SequenceMatcher(None, ln, src, autojunk=False).find_longest_match(
        0, len(ln), 0, len(src))
    threshold = max(min_run, int(0.6 * len(ln)))
    return "extracted" if match.size >= threshold else "expanded"


def build_elements(payload: dict, source: str) -> list[Element]:
    """把模型返回的 elements 规整为 Element 列表，并复核 dialogue 的 mode。纯函数。"""
    elements: list[Element] = []
    for raw in payload.get("elements", []) or []:
        kind = (raw.get("kind") or "").strip().lower()
        if kind not in _KINDS:
            continue
        if kind == "dialogue":
            line = (raw.get("line") or "").strip()
            character = (raw.get("character") or "").strip()
            if not line or not character:
                continue
            elements.append(Element(
                kind="dialogue", character=character, line=line,
                parenthetical=(raw.get("parenthetical") or "").strip(),
                mode=verify_mode(line, source),     # 程序复核，覆盖模型自报
            ))
        else:
            text = (raw.get("text") or "").strip()
            if text:
                elements.append(Element(kind=kind, text=text))
    return elements


def generate_for_scene(scene: Scene, chapter: Chapter, ai: AIService,
                       mode: str = "conservative") -> list[Element]:
    source = scene_text(scene, chapter)
    if not source.strip():
        return []
    hint = DIALOGUE_MODE_HINTS.get(mode, DIALOGUE_MODE_HINTS["conservative"])
    prompt = (GENERATE_DIALOGUE
              .replace("{mode_hint}", hint)
              .replace("{heading}", scene.heading.slugline())
              .replace("{summary}", scene.summary)
              .replace("{characters}", "、".join(scene.character_names))
              .replace("{source}", source))
    payload = ai.chat_json(prompt, system=SYSTEM_SCREENWRITER,
                           task=f"dialogue_{scene.id}_{mode}")
    return build_elements(payload, source)


def generate_dialogue(scenes: list[Scene], chapters_by_index: dict[int, Chapter],
                      ai: AIService, mode: str = "conservative") -> dict[str, list[Element]]:
    """为每个场景生成元素流，返回 {scene_id: [Element]}。"""
    result: dict[str, list[Element]] = {}
    for scene in scenes:
        chapter = chapters_by_index.get(scene.chapter)
        if chapter is None:
            result[scene.id] = []
            continue
        result[scene.id] = generate_for_scene(scene, chapter, ai, mode)
    return result


def dialogue_stats(elements_by_scene: dict[str, list[Element]]) -> dict:
    """统计对白相关指标（真实数字，供质量报告/Dashboard 用）。"""
    total = extracted = expanded = actions = 0
    for elements in elements_by_scene.values():
        for e in elements:
            if e.kind == "dialogue":
                total += 1
                if e.mode == "extracted":
                    extracted += 1
                else:
                    expanded += 1
            elif e.kind == "action":
                actions += 1
    all_elems = total + actions
    return {
        "dialogue_lines": total,
        "extracted": extracted,
        "expanded": expanded,
        "action_blocks": actions,
        "dialogue_density": round(total / all_elems, 3) if all_elems else 0.0,
        "expanded_ratio": round(expanded / total, 3) if total else 0.0,
    }
