"""CharacterExtractor 单测：纯函数 + FakeBackend，全部离线。"""
import json
from pathlib import Path

import pytest

from story2script.ai_service import AIService
from story2script.character_extractor import (
    build_character_set,
    extract_characters,
)
from story2script.parser import parse_novel, parse_novel_text
from tests.conftest import FakeBackend

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "story.txt"

PAYLOAD = {
    "characters": [
        {"name": "庞少", "aka": ["庞家少年"], "role": "protagonist",
         "profile": "穿越少年", "goal": "立足", "arc": "成长"},
        {"name": "李四", "aka": [], "role": "supporting", "profile": "女子"},
        {"name": "路人", "aka": [], "role": "unknown_role", "profile": ""},
    ],
    "relations": [
        {"from": "庞少", "to": "李四", "type": "喜欢", "directed": True, "note": "一见钟情"},
        {"from": "庞少", "to": "查无此人", "type": "敌对"},   # 端点不存在，应丢弃
        {"from": "庞少", "to": "庞少", "type": "自恋"},        # 自环，应丢弃
    ],
}

NOVEL_TEXT = "庞少出场。庞家少年又出场。庞少第三次出场。李四只来一次。"


def test_build_assigns_ids_and_counts_appearances():
    cs = build_character_set(PAYLOAD, NOVEL_TEXT)
    pang = next(c for c in cs.characters if c.name == "庞少")
    # 庞少(2次) + 庞家少年(1次) = 3
    assert pang.appearances == 3
    assert pang.id == "c1"  # id 按模型给的顺序分配，与排序无关


def test_role_normalized():
    cs = build_character_set(PAYLOAD, NOVEL_TEXT)
    luren = next(c for c in cs.characters if c.name == "路人")
    assert luren.role == "supporting"  # unknown_role → 默认


def test_invalid_relations_dropped():
    cs = build_character_set(PAYLOAD, NOVEL_TEXT)
    assert len(cs.relations) == 1
    r = cs.relations[0]
    assert r.source == "c1" and r.target == "c2" and r.type == "喜欢"


def test_importance_normalized_and_sorted():
    cs = build_character_set(PAYLOAD, NOVEL_TEXT)
    # 出场+关系度数最高者 importance==1.0，且排在最前
    assert cs.characters[0].importance == 1.0
    assert cs.characters[0].name == "庞少"
    assert all(0.0 <= c.importance <= 1.0 for c in cs.characters)


def test_story_graph_shape():
    cs = build_character_set(PAYLOAD, NOVEL_TEXT)
    g = cs.story_graph()
    assert {n["id"] for n in g["nodes"]} == {"c1", "c2", "c3"}
    assert g["edges"][0]["from"] == "c1" and g["edges"][0]["to"] == "c2"


def test_extract_characters_via_fake_backend():
    ai = AIService(backend=FakeBackend({"extract_characters": json.dumps(PAYLOAD)}))
    novel = parse_novel_text("第一章 起\n" + NOVEL_TEXT)
    cs = extract_characters(novel, ai)
    assert len(cs.characters) == 3
    assert cs.by_id("c1").name == "庞少"


def test_empty_payload():
    cs = build_character_set({}, "")
    assert cs.characters == [] and cs.relations == []


# ---- 离线集成：用真实录制的 fixture 跑完整抽取（无网络） ----
FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "story2script" / "fixtures" / "extract_characters.d34d090829641f0b.json"
)


@pytest.mark.skipif(not FIXTURE.exists() or not SAMPLE.exists(),
                    reason="缺少录制 fixture 或示例小说")
def test_extract_from_real_offline_fixture():
    """OfflineBackend 回放真实模型输出，完整跑通人物抽取与关系图。"""
    ai = AIService()  # 测试默认 offline 后端
    novel = parse_novel(SAMPLE)
    cs = extract_characters(novel, ai)
    assert len(cs.characters) >= 10
    assert cs.characters[0].role == "protagonist"      # 主角排第一
    assert cs.characters[0].importance == 1.0
    assert cs.characters[0].appearances > 50           # 真实统计的高频出场
    assert len(cs.relations) >= 5
    g = cs.story_graph()
    assert len(g["nodes"]) == len(cs.characters)
