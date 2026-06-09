"""DialogueGenerator 单测：元素规整、mode 复核、统计。全部离线。"""
import json
from pathlib import Path

import pytest

from story2script.ai_service import AIService
from story2script.dialogue_generator import (
    Element,
    build_elements,
    dialogue_stats,
    generate_dialogue,
    verify_mode,
)
from story2script.parser import Chapter, parse_novel
from story2script.scene_planner import Scene, SceneHeading, plan_scenes
from tests.conftest import FakeBackend

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "story.txt"
FIXTURES = Path(__file__).resolve().parent.parent / "story2script" / "fixtures"

SOURCE = '庞少凑上前，对女子道：“姑娘莫怕，这老鼠颇有怪力。”女子又惊又怒，心想这登徒子好生无赖。'


def test_verify_mode_extracted_when_line_in_source():
    assert verify_mode("姑娘莫怕，这老鼠颇有怪力", SOURCE) == "extracted"


def test_verify_mode_expanded_when_fabricated():
    assert verify_mode("你给我滚出桐城，永世不得再来！", SOURCE) == "expanded"


def test_verify_mode_empty_line_is_expanded():
    assert verify_mode("", SOURCE) == "expanded"


def test_build_elements_overrides_model_mode():
    """模型把扩写台词谎标成 extracted，应被程序复核纠正为 expanded。"""
    payload = {"elements": [
        {"kind": "action", "text": "庞少凑上前。"},
        {"kind": "dialogue", "character": "庞少",
         "line": "姑娘莫怕，这老鼠颇有怪力", "mode": "expanded"},   # 实为原文→应纠正 extracted
        {"kind": "dialogue", "character": "女子",
         "line": "你这无赖给我滚！", "mode": "extracted"},          # 实为扩写→应纠正 expanded
        {"kind": "transition", "text": "切至"},
    ]}
    els = build_elements(payload, SOURCE)
    assert els[1].mode == "extracted"
    assert els[2].mode == "expanded"


def test_build_elements_skips_invalid():
    payload = {"elements": [
        {"kind": "dialogue", "character": "", "line": "无人说"},   # 缺 character
        {"kind": "dialogue", "character": "庞少", "line": ""},      # 缺 line
        {"kind": "weird", "text": "未知类型"},                      # 非法 kind
        {"kind": "action", "text": ""},                            # 空 action
    ]}
    assert build_elements(payload, SOURCE) == []


def test_element_to_dict_shapes():
    d = Element(kind="dialogue", character="庞少", line="台词", mode="extracted",
                parenthetical="(冷笑)").to_dict()
    assert d == {"kind": "dialogue", "character": "庞少", "line": "台词",
                 "mode": "extracted", "parenthetical": "(冷笑)"}
    a = Element(kind="action", text="他笑了。").to_dict()
    assert a == {"kind": "action", "text": "他笑了。"}


def test_dialogue_stats():
    by_scene = {
        "s1": [
            Element("dialogue", character="A", line="一", mode="extracted"),
            Element("dialogue", character="B", line="二", mode="expanded"),
            Element("action", text="动作"),
        ]
    }
    st = dialogue_stats(by_scene)
    assert st["dialogue_lines"] == 2 and st["extracted"] == 1 and st["expanded"] == 1
    assert st["action_blocks"] == 1
    assert st["dialogue_density"] == round(2 / 3, 3)
    assert st["expanded_ratio"] == 0.5


def test_generate_dialogue_via_fake_backend():
    payload = {"elements": [
        {"kind": "dialogue", "character": "庞少", "line": "姑娘莫怕", "mode": "extracted"},
    ]}
    ai = AIService(backend=FakeBackend({"*": json.dumps(payload)}))
    ch = Chapter(index=1, title=None, text=SOURCE, paragraphs=[SOURCE])
    scene = Scene(id="s1", index=1, chapter=1, span=(0, 0),
                  heading=SceneHeading("EXT", "大街", "日"),
                  summary="街头", character_names=["庞少", "女子"])
    out = generate_dialogue([scene], {1: ch}, ai)
    assert len(out["s1"]) == 1 and out["s1"][0].character == "庞少"


def test_generate_dialogue_missing_chapter():
    ai = AIService(backend=FakeBackend({"*": json.dumps({"elements": []})}))
    scene = Scene(id="s9", index=9, chapter=99, span=(0, 0),
                  heading=SceneHeading(), summary="", character_names=[])
    assert generate_dialogue([scene], {}, ai)["s9"] == []


@pytest.mark.skipif(
    not SAMPLE.exists() or len(list(FIXTURES.glob("dialogue_s*conservative*.json"))) < 30,
    reason="缺少完整对白 fixture")
def test_generate_dialogue_real_offline():
    """OfflineBackend 回放真实模型输出，跑通全书对白生成，验证 mode 真实可分。"""
    ai = AIService()
    novel = parse_novel(SAMPLE)
    scenes = plan_scenes(novel, ai, granularity="coarse")
    by_index = {c.index: c for c in novel.chapters}
    elements = generate_dialogue(scenes, by_index, ai, mode="conservative")
    st = dialogue_stats(elements)
    assert st["dialogue_lines"] > 30
    # 既有原文提取也有 AI 扩写
    assert st["extracted"] > 0 and st["expanded"] > 0
    assert 0.0 < st["dialogue_density"] <= 1.0
