"""ScenePlanner 单测：纯函数 + FakeBackend，全部离线。"""
import json
from pathlib import Path

import pytest

from story2script.ai_service import AIService
from story2script.parser import Chapter, parse_novel, parse_novel_text
from story2script.scene_planner import (
    SceneHeading,
    build_scenes_for_chapter,
    plan_scenes,
    scene_text,
)
from tests.conftest import FakeBackend

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "story.txt"
FIXTURES = Path(__file__).resolve().parent.parent / "story2script" / "fixtures"


def _chapter(n_paras=6, index=2):
    return Chapter(index=index, title="桐城",
                   text="x", paragraphs=[f"第{i}段内容。" for i in range(n_paras)])


PAYLOAD = {
    "scenes": [
        {"int_ext": "外景", "location": "东西大街", "time": "日",
         "summary": "街头戏弄", "conflict": "调戏被揭穿",
         "characters": ["庞少", "周月如"], "para_start": 0, "para_end": 2},
        {"int_ext": "INT", "location": "纸铺", "time": "日",
         "summary": "理论", "characters": ["庞少"], "para_start": 3, "para_end": 99},
    ]
}


def test_slugline():
    h = SceneHeading("INT", "庞家药铺", "夜")
    assert h.slugline() == "INT. 庞家药铺 - 夜"


def test_build_scenes_basic_and_index():
    scenes = build_scenes_for_chapter(PAYLOAD, _chapter(), start_index=5)
    assert [s.id for s in scenes] == ["s5", "s6"]
    assert scenes[0].index == 5 and scenes[0].chapter == 2


def test_int_ext_and_time_normalized():
    scenes = build_scenes_for_chapter(PAYLOAD, _chapter(), 1)
    assert scenes[0].heading.int_ext == "EXT"   # 外景 → EXT
    assert scenes[0].heading.time == "日"


def test_span_clamped_to_paragraph_count():
    scenes = build_scenes_for_chapter(PAYLOAD, _chapter(n_paras=6), 1)
    # 第二个场景 para_end=99 被夹到 5
    assert scenes[1].span == (3, 5)


def test_span_reversed_is_fixed():
    payload = {"scenes": [{"location": "x", "para_start": 4, "para_end": 1}]}
    scenes = build_scenes_for_chapter(payload, _chapter(6), 1)
    assert scenes[0].span == (1, 4)


def test_invalid_span_falls_back():
    payload = {"scenes": [{"location": "x", "para_start": None, "para_end": "bad"}]}
    scenes = build_scenes_for_chapter(payload, _chapter(6), 1)
    assert scenes[0].span == (0, 5)


def test_scene_text_extracts_paragraphs():
    ch = _chapter(6)
    scenes = build_scenes_for_chapter(PAYLOAD, ch, 1)
    txt = scene_text(scenes[0], ch)
    assert "第0段" in txt and "第2段" in txt and "第3段" not in txt


def test_plan_scenes_across_chapters_global_index():
    ai = AIService(backend=FakeBackend({"*": json.dumps(PAYLOAD)}))
    novel = parse_novel_text("开篇一段。\n\n第二章 二\n二章一段。\n\n二章二段。")
    scenes = plan_scenes(novel, ai)
    # 两章各 2 场 → 全局 index 连续 1..4
    assert [s.index for s in scenes] == [1, 2, 3, 4]
    assert scenes[2].chapter == 2


def test_empty_chapter_yields_no_scenes():
    empty = Chapter(index=1, title=None, text="", paragraphs=[])
    ai = AIService(backend=FakeBackend({"*": json.dumps(PAYLOAD)}))
    assert build_scenes_for_chapter({}, empty, 1) == []


@pytest.mark.skipif(
    not SAMPLE.exists() or not list(FIXTURES.glob("plan_scenes_ch*coarse*.json")),
    reason="缺少示例小说或场景 fixture")
def test_plan_scenes_real_offline():
    """OfflineBackend 回放真实模型输出，完整跑通全书场景拆分。"""
    ai = AIService()  # 测试默认 offline
    novel = parse_novel(SAMPLE)
    scenes = plan_scenes(novel, ai, granularity="coarse")
    assert len(scenes) >= 20
    # 全局 index 连续
    assert [s.index for s in scenes] == list(range(1, len(scenes) + 1))
    # 每个场景的 span 都落在所属章节段落范围内（溯源不越界）
    for s in scenes:
        ch = novel.chapters[s.chapter - 1]
        assert 0 <= s.span[0] <= s.span[1] <= len(ch.paragraphs) - 1
        assert s.heading.int_ext in {"INT", "EXT", "INT/EXT"}
