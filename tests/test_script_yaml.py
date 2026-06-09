"""ScriptGenerator / YamlExporter / Schema 校验 / Pipeline 单测。全部离线。"""
import json
from pathlib import Path

import pytest
import yaml

from story2script.ai_service import AIService
from story2script.character_extractor import build_character_set
from story2script.dialogue_generator import Element
from story2script.parser import parse_novel, parse_novel_text
from story2script.scene_planner import Scene, SceneHeading
from story2script.schema import is_valid, reference_warnings, validate_script
from story2script.script_generator import build_script
from story2script.yaml_exporter import to_yaml
from tests.conftest import FakeBackend

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "story.txt"
FIXTURES = Path(__file__).resolve().parent.parent / "story2script" / "fixtures"


def _mini_script():
    novel = parse_novel_text("第一章 起\n庞雨出场。庞雨说话。周月如也在。")
    cs = build_character_set({
        "characters": [
            {"name": "庞雨", "aka": ["庞少"], "role": "protagonist"},
            {"name": "周月如", "aka": [], "role": "supporting"},
        ],
        "relations": [{"from": "庞雨", "to": "周月如", "type": "喜欢", "directed": True}],
    }, novel.chapters[0].text)
    scene = Scene(id="s1", index=1, chapter=1, span=(0, 0),
                  heading=SceneHeading("EXT", "大街", "日"),
                  summary="街头", character_names=["庞少", "周月如"])
    elements = {"s1": [
        Element("action", text="庞雨上前。"),
        Element("dialogue", character="庞少", line="姑娘留步", mode="extracted"),
        Element("dialogue", character="周家女子", line="你是谁", mode="expanded"),  # 未消解
    ]}
    return build_script(novel, cs, [scene], elements, model="MiniMax-M3")


def test_build_script_shape_and_meta():
    s = _mini_script()
    assert s["schema_version"] == 1
    assert s["meta"]["model"] == "MiniMax-M3"
    assert len(s["characters"]) == 2 and len(s["scenes"]) == 1


def test_character_name_resolved_to_id():
    s = _mini_script()
    scene = s["scenes"][0]
    # "庞少"(aka) → c1；"周月如" → c2
    assert "c1" in scene["characters"] and "c2" in scene["characters"]
    # 对白说话人 "庞少" → c1
    assert scene["elements"][1]["character"] == "c1"


def test_unresolved_speaker_kept_as_name():
    s = _mini_script()
    # "周家女子" 无法精确消解 → 保留原名
    assert s["scenes"][0]["elements"][2]["character"] == "周家女子"
    assert s["quality_report"]["unresolved_speakers"] == 1


def test_schema_valid_for_wellformed_script():
    s = _mini_script()
    assert validate_script(s) == []      # 结构通过（描述性人名不算结构错误）
    assert is_valid(s)


def test_reference_warnings_lists_unresolved():
    s = _mini_script()
    warns = reference_warnings(s)
    assert any("周家女子" in w for w in warns)


def test_dangling_id_is_structural_error():
    s = _mini_script()
    s["scenes"][0]["elements"][1]["character"] = "c99"   # 悬空 id
    errs = validate_script(s)
    assert any("悬空人物引用" in e and "c99" in e for e in errs)


def test_schema_catches_bad_enum():
    s = _mini_script()
    s["scenes"][0]["heading"]["int_ext"] = "WRONG"
    assert any("int_ext" in e or "WRONG" in e for e in validate_script(s))


def test_yaml_roundtrip_unicode_and_order():
    s = _mini_script()
    text = to_yaml(s)
    assert "\\u" not in text                      # 中文不转义
    assert text.splitlines()[0] == "schema_version: 1"   # 顺序保留
    loaded = yaml.safe_load(text)                 # 可被解析回来
    assert loaded["meta"]["title"] == s["meta"]["title"]


# ---- 离线端到端：用真实 fixture 跑完整流水线 ----
@pytest.mark.skipif(
    not SAMPLE.exists() or len(list(FIXTURES.glob("dialogue_s*conservative*.json"))) < 30,
    reason="缺少完整 fixture")
def test_full_pipeline_offline_valid_yaml():
    from story2script.pipeline import run_pipeline

    ai = AIService()
    novel = parse_novel(SAMPLE)
    script = run_pipeline(novel, ai, model="MiniMax-M3",
                          generated_at="2026-06-09T12:00:00")
    assert validate_script(script) == []          # 真实输出结构合法
    assert script["quality_report"]["scene_count"] >= 20
    assert script["quality_report"]["dialogue_lines"] > 100
    text = to_yaml(script)
    assert yaml.safe_load(text)["schema_version"] == 1
