"""小说导入与章节解析（design.md §5 小说导入 / 章节解析）。

职责：把各种格式的小说文本读进来，切成「章节 → 段落」的结构，给后续 AI 流水线用。
这一步**不调用 AI**，是确定性的纯文本处理，因此也最适合写充分的单测。

支持格式：.txt / .md（按纯文本处理）/ .pdf（pypdf 提取文字）。

章节识别要点
------------
真实网文常见两个坑，本解析器都处理了：
1. **首章没有「第X章」标题**——开篇直接进正文（示例小说就是这样）。
   → 第一个章节标题之前若有正文，将其作为第 1 章（标题留空）。
2. 标题行可能带前导空格、Markdown 的 `#`、中文数字（第二章）或阿拉伯数字。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 章节标题行：整行就是一个标题（短行）。支持 第X章/回/卷/节、Chapter N。
_CHAPTER_RE = re.compile(
    r"^\s*#*\s*"
    r"(?:"
    r"第\s*[0-9零〇一二两三四五六七八九十百千]+\s*[章回卷节]"   # 第二章 / 第十回
    r"|Chapter\s+\d+|CHAPTER\s+\d+|卷[一二三四五六七八九十]+"
    r")"
    r"(?:[ \t　]+(?P<title>\S.*?))?\s*$"   # 标题须以空白分隔，否则正文'第X章…'会被误判
)
_MAX_HEADING_LEN = 30  # 标题行一般很短，借此排除把正文误判成标题


@dataclass
class Chapter:
    index: int               # 顺序号，从 1 开始
    title: str | None        # 标题（首章可能为空）
    text: str                # 本章正文（不含标题行）
    paragraphs: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.title or f"第{self.index}章"

    @property
    def char_count(self) -> int:
        return len(self.text.replace("\n", "").replace(" ", ""))


@dataclass
class Novel:
    title: str
    source_name: str
    chapters: list[Chapter]

    @property
    def char_count(self) -> int:
        return sum(c.char_count for c in self.chapters)


def split_paragraphs(text: str) -> list[str]:
    """按空行切段，去除每段首尾空白（含全角空格）与空段。"""
    raw = re.split(r"\n\s*\n", text)
    out = []
    for p in raw:
        cleaned = p.strip().strip("　").strip()
        # 段内换行折叠成一行（小说排版里换行≈段内软换行）
        cleaned = re.sub(r"\s*\n\s*", "", cleaned)
        if cleaned:
            out.append(cleaned)
    return out


def _is_heading(line: str) -> re.Match | None:
    if len(line.strip()) > _MAX_HEADING_LEN:
        return None
    return _CHAPTER_RE.match(line)


def parse_chapters(text: str) -> list[Chapter]:
    """把整篇正文切成章节。首个标题前的正文作为第 1 章。"""
    lines = text.splitlines()
    # 找到所有标题行的位置
    heads: list[tuple[int, str | None]] = []
    for i, line in enumerate(lines):
        m = _is_heading(line)
        if m:
            title = (m.group("title") or "").strip() or None
            heads.append((i, title))

    chapters: list[Chapter] = []

    # 情况一：没有任何标题 → 整篇就是一章
    if not heads:
        body = text.strip()
        if body:
            chapters.append(_make_chapter(1, None, body))
        return chapters

    # 情况二：首个标题前有正文 → 作为第 1 章（无标题）
    first_head_line = heads[0][0]
    preamble = "\n".join(lines[:first_head_line]).strip()
    idx = 1
    if preamble:
        chapters.append(_make_chapter(idx, None, preamble))
        idx += 1

    # 其余按标题切分
    for h, (line_no, title) in enumerate(heads):
        start = line_no + 1
        end = heads[h + 1][0] if h + 1 < len(heads) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        chapters.append(_make_chapter(idx, title, body))
        idx += 1

    return chapters


def _make_chapter(index: int, title: str | None, body: str) -> Chapter:
    return Chapter(index=index, title=title, text=body, paragraphs=split_paragraphs(body))


# --------------------------------------------------------------------------- #
# 文件读取
# --------------------------------------------------------------------------- #
def load_text(path: str | Path) -> str:
    """按扩展名读取小说文本。"""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    # .txt / .md / 其它：按文本读
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("解析 PDF 需要 pypdf：pip install pypdf") from e
    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def parse_novel(path: str | Path, title: str | None = None) -> Novel:
    """从文件解析为 Novel。"""
    path = Path(path)
    text = load_text(path)
    chapters = parse_chapters(text)
    return Novel(
        title=title or path.stem,
        source_name=path.name,
        chapters=chapters,
    )


def parse_novel_text(text: str, title: str = "未命名", source_name: str = "inline") -> Novel:
    """从内存文本解析为 Novel（便于测试 / Web 上传内容直传）。"""
    return Novel(title=title, source_name=source_name, chapters=parse_chapters(text))
