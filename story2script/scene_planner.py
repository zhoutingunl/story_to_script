"""场景拆分（design.md §10 场景拆分 / §6.2 Scene Planner）。

把"连续叙事"切成"场景驱动"的剧本结构：按地点/时间/事件变化分场，
并记录每个场景对应的原文段落区间（source span），让生成结果可溯源、可校对。

支持粗/细两种粒度（granularity），对应 design.md §17 的 A/B 场景规划策略。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ai_service import AIService
from .parser import Chapter, Novel
from .prompts import GRANULARITY_HINTS, PLAN_SCENES, SYSTEM_SCREENWRITER

_INT_EXT = {"INT", "EXT", "INT/EXT"}
_TIMES = {"日", "夜", "黄昏", "清晨", "连续", "不明"}


@dataclass
class SceneHeading:
    int_ext: str = "INT"
    location: str = "未知地点"
    time: str = "不明"

    def slugline(self) -> str:
        return f"{self.int_ext}. {self.location} - {self.time}"

    def to_dict(self) -> dict:
        return {"int_ext": self.int_ext, "location": self.location, "time": self.time}


@dataclass
class Scene:
    id: str
    index: int                       # 全剧顺序号
    chapter: int                     # 来源章节序号
    span: tuple[int, int]            # 章内段落区间（闭区间，0 基）
    heading: SceneHeading
    summary: str = ""
    conflict: str = ""
    character_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "index": self.index,
            "heading": self.heading.to_dict(),
            "summary": self.summary,
            "source": {"chapter": self.chapter, "span": list(self.span)},
            "conflict": self.conflict,
            "characters": self.character_names,
        }


def _norm_int_ext(v: str) -> str:
    v = (v or "").strip().upper().replace("内景", "INT").replace("外景", "EXT")
    return v if v in _INT_EXT else "INT"


def _norm_time(v: str) -> str:
    v = (v or "").strip()
    return v if v in _TIMES else (v or "不明")


def _clamp_span(start, end, n_paras: int) -> tuple[int, int]:
    """把模型给的段落区间夹到合法范围，保证可溯源不越界。"""
    try:
        s = max(0, int(start))
        e = min(n_paras - 1, int(end))
    except (TypeError, ValueError):
        return (0, max(0, n_paras - 1))
    if e < s:
        s, e = e, s
    return (s, e)


def build_scenes_for_chapter(payload: dict, chapter: Chapter,
                             start_index: int) -> list[Scene]:
    """把模型对单章返回的 scenes 转成 Scene 列表（纯函数，便于单测）。"""
    n_paras = len(chapter.paragraphs)
    scenes: list[Scene] = []
    for i, rs in enumerate(payload.get("scenes", []) or []):
        idx = start_index + i
        heading = SceneHeading(
            int_ext=_norm_int_ext(rs.get("int_ext", "")),
            location=(rs.get("location") or "未知地点").strip(),
            time=_norm_time(rs.get("time", "")),
        )
        span = _clamp_span(rs.get("para_start"), rs.get("para_end"), n_paras)
        names = [s.strip() for s in (rs.get("characters") or []) if s and s.strip()]
        scenes.append(Scene(
            id=f"s{idx}", index=idx, chapter=chapter.index, span=span,
            heading=heading,
            summary=(rs.get("summary") or "").strip(),
            conflict=(rs.get("conflict") or "").strip(),
            character_names=names,
        ))
    return scenes


def _numbered_paragraphs(chapter: Chapter) -> str:
    return "\n".join(f"[{i}] {p}" for i, p in enumerate(chapter.paragraphs))


def plan_scenes_for_chapter(chapter: Chapter, ai: AIService,
                            start_index: int, granularity: str = "coarse") -> list[Scene]:
    if not chapter.paragraphs:
        return []
    hint = GRANULARITY_HINTS.get(granularity, GRANULARITY_HINTS["coarse"])
    prompt = (PLAN_SCENES
              .replace("{granularity_hint}", hint)
              .replace("{chapter}", _numbered_paragraphs(chapter)))
    payload = ai.chat_json(prompt, system=SYSTEM_SCREENWRITER,
                           task=f"plan_scenes_ch{chapter.index}_{granularity}")
    return build_scenes_for_chapter(payload, chapter, start_index)


def plan_scenes(novel: Novel, ai: AIService, granularity: str = "coarse") -> list[Scene]:
    """逐章拆分场景，拼成全剧有序场景序列。"""
    scenes: list[Scene] = []
    next_index = 1
    for chapter in novel.chapters:
        chapter_scenes = plan_scenes_for_chapter(chapter, ai, next_index, granularity)
        scenes.extend(chapter_scenes)
        next_index += len(chapter_scenes)
    return scenes


def scene_text(scene: Scene, chapter: Chapter) -> str:
    """取出场景对应的原文段落拼接，供后续对白提炼使用。"""
    s, e = scene.span
    return "\n".join(chapter.paragraphs[s:e + 1])
