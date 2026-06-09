"""剧本组装（design.md §6 剧本生成）。

把人物表、场景序列、各场对白元素，组装成符合 yaml_schema.md 的单一剧本字典。
职责是"拼装 + 引用消解 + 基础指标"，不调用 AI（确定性，易测）。

引用消解：场景与对白里的人物用 name 表示，这里统一映射成 character id；
映射不到的保留原名（不丢信息），由 schema 校验给出提示。
"""
from __future__ import annotations

from datetime import datetime

from . import __version__
from .character_extractor import CharacterSet
from .dialogue_generator import Element, dialogue_stats
from .parser import Novel
from .scene_planner import Scene
from .schema import reference_warnings


def _name_to_id_map(cs: CharacterSet) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for c in cs.characters:
        for name in [c.name, *c.aka]:
            mapping.setdefault(name, c.id)
    return mapping


def _resolve(name: str, mapping: dict[str, str]) -> str:
    """人物名 → id；映射不到则原样返回（保留信息）。"""
    return mapping.get(name, name)


def build_script(novel: Novel, character_set: CharacterSet, scenes: list[Scene],
                 elements_by_scene: dict[str, list[Element]], *,
                 model: str, dialogue_mode: str = "conservative",
                 generated_at: str | None = None, logline: str = "") -> dict:
    """组装成符合 schema 的剧本字典。"""
    name_to_id = _name_to_id_map(character_set)
    gen_at = generated_at or datetime.now().isoformat(timespec="seconds")

    scene_dicts = []
    for scene in scenes:
        elements = elements_by_scene.get(scene.id, [])
        char_ids = []
        for n in scene.character_names:
            cid = _resolve(n, name_to_id)
            if cid not in char_ids:
                char_ids.append(cid)
        elem_dicts = []
        for e in elements:
            d = e.to_dict()
            if d["kind"] == "dialogue":
                d["character"] = _resolve(d["character"], name_to_id)
            elem_dicts.append(d)

        sd = scene.to_dict()
        sd["characters"] = char_ids
        sd["elements"] = elem_dicts
        sd["quality_flags"] = []          # 由 QualityChecker(PR7) 填充
        scene_dicts.append(sd)

    stats = dialogue_stats(elements_by_scene)
    quality_report = {
        "scene_count": len(scenes),
        "character_count": len(character_set.characters),
        "dialogue_lines": stats["dialogue_lines"],
        "extracted": stats["extracted"],
        "expanded": stats["expanded"],
        "dialogue_density": stats["dialogue_density"],
        "expanded_ratio": stats["expanded_ratio"],
        "warnings": [],                   # PR7 填充
    }

    script = {
        "schema_version": 1,
        "meta": {
            "title": novel.title,
            "source": novel.source_name,
            "logline": logline,
            "generated_at": gen_at,
            "generator": f"story2script {__version__}",
            "model": model,
            "dialogue_mode": dialogue_mode,
        },
        "characters": [c.to_dict() for c in character_set.characters],
        "scenes": scene_dicts,
        "story_graph": character_set.story_graph(),
        "quality_report": quality_report,
    }
    # 诚实披露：未消解为 id 的描述性说话人数量（coreference 难题，保留原名）
    quality_report["unresolved_speakers"] = len(reference_warnings(script))
    return script
