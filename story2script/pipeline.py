"""端到端流水线：小说 → 结构化剧本字典（design.md §9 核心处理流程）。

串起 解析 → 人物 → 场景 → 对白 → 组装。Web UI 与 demo 都调用它。
每一步可单独替换/测试；AI 调用都经过可插拔的 AIService。
"""
from __future__ import annotations

from dataclasses import dataclass

from .ai_service import AIService
from .character_extractor import extract_characters
from .dialogue_generator import generate_dialogue
from .parser import Novel, parse_novel, parse_novel_text
from .scene_planner import plan_scenes
from .script_generator import build_script


@dataclass
class PipelineResult:
    novel: Novel
    script: dict


def run_pipeline(novel: Novel, ai: AIService, *, model: str | None = None,
                 granularity: str = "coarse", dialogue_mode: str = "conservative",
                 generated_at: str | None = None, logline: str = "") -> dict:
    """对已解析的 Novel 跑完整流水线，返回剧本字典。"""
    model = model or ai.cfg.model
    character_set = extract_characters(novel, ai)
    scenes = plan_scenes(novel, ai, granularity=granularity)
    by_index = {c.index: c for c in novel.chapters}
    elements = generate_dialogue(scenes, by_index, ai, mode=dialogue_mode)
    return build_script(
        novel, character_set, scenes, elements,
        model=model, dialogue_mode=dialogue_mode,
        generated_at=generated_at, logline=logline,
    )


def run_from_path(path: str, ai: AIService, **kwargs) -> dict:
    return run_pipeline(parse_novel(path), ai, **kwargs)


def run_from_text(text: str, ai: AIService, *, title: str = "未命名",
                  source_name: str = "inline", **kwargs) -> dict:
    novel = parse_novel_text(text, title=title, source_name=source_name)
    return run_pipeline(novel, ai, **kwargs)
