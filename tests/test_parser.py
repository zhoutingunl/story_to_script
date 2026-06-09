"""Parser 单测：章节解析、段落切分、边界与真实样本。"""
from pathlib import Path

import pytest

from story2script.parser import (
    Chapter,
    parse_chapters,
    parse_novel,
    parse_novel_text,
    split_paragraphs,
)

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "story.txt"


def test_split_paragraphs_basic():
    text = "第一段。\n\n第二段。\n\n\n第三段。"
    assert split_paragraphs(text) == ["第一段。", "第二段。", "第三段。"]


def test_split_paragraphs_folds_soft_newlines_and_fullwidth_space():
    text = "　这是一段\n继续同一段。\n\n下一段。"
    paras = split_paragraphs(text)
    assert paras == ["这是一段继续同一段。", "下一段。"]


def test_parse_chapters_standard_headers():
    text = "第一章 开始\n正文一。\n\n第二章 发展\n正文二。"
    chs = parse_chapters(text)
    assert [c.index for c in chs] == [1, 2]
    assert chs[0].title == "开始"
    assert chs[1].title == "发展"
    assert "正文二" in chs[1].text


def test_parse_chapters_preamble_without_header():
    """首章无标题：标题前的正文应成为第 1 章。"""
    text = "无题开篇正文。\n\n第二章 桐城\n第二章正文。"
    chs = parse_chapters(text)
    assert len(chs) == 2
    assert chs[0].index == 1 and chs[0].title is None
    assert "无题开篇" in chs[0].text
    assert chs[0].display_title == "第1章"
    assert chs[1].title == "桐城"


def test_parse_chapters_no_headers_single_chapter():
    chs = parse_chapters("就一段话，没有章节。")
    assert len(chs) == 1 and chs[0].index == 1


def test_parse_chapters_markdown_and_arabic():
    text = "# 第1章 起\n正文。\n\n## 第2章 承\n正文二。"
    chs = parse_chapters(text)
    assert [c.title for c in chs] == ["起", "承"]


def test_heading_not_confused_by_inline_mention():
    """正文里提到'第三章'不应被当成标题（整行更长）。"""
    text = "他随手翻到第三章那一页，叹了口气，把书合上放回原处去了。"
    chs = parse_chapters(text)
    assert len(chs) == 1


def test_chapter_char_count_excludes_whitespace():
    ch = Chapter(index=1, title=None, text="一 二\n三", paragraphs=[])
    assert ch.char_count == 3


# ---- 真实样本 ----
@pytest.mark.skipif(not SAMPLE.exists(), reason="缺少示例小说")
def test_real_sample_nine_chapters():
    novel = parse_novel(SAMPLE)
    assert len(novel.chapters) == 9          # 首章无标题 + 第二~九章
    assert novel.chapters[0].title is None   # 第一章无标题
    assert novel.chapters[1].title == "桐城"
    assert novel.chapters[-1].title == "调解"
    assert novel.char_count > 10000
    # 每章都应有段落
    assert all(c.paragraphs for c in novel.chapters)


@pytest.mark.skipif(not SAMPLE.exists(), reason="缺少示例小说")
def test_real_sample_title_from_filename():
    novel = parse_novel(SAMPLE)
    assert novel.title == "story"
    assert novel.source_name == "story.txt"


def test_parse_novel_text_inline():
    novel = parse_novel_text("开篇。\n\n第二章 二\n内容。", title="测试")
    assert novel.title == "测试" and len(novel.chapters) == 2
