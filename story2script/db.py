"""SQLite 持久层（design.md §19 数据模型）。

用标准库 sqlite3，保持零额外依赖、易部署。表结构覆盖：
Novel / Chapter / Character / Scene / Dialogue / Script / Event(埋点/metrics)。

剧本的结构化内容（场景/元素等嵌套数据）以 JSON 文本存在 script.data 字段里——
关系表负责"可统计"的维度（数量、耗时、覆盖率），JSON 负责"可还原"的完整剧本，
两者职责分离。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import get_config

SCHEMA = """
CREATE TABLE IF NOT EXISTS novel (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    source_name TEXT,
    char_count  INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chapter (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id  INTEGER NOT NULL REFERENCES novel(id) ON DELETE CASCADE,
    idx       INTEGER NOT NULL,
    title     TEXT,
    text      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS script (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id    INTEGER NOT NULL REFERENCES novel(id) ON DELETE CASCADE,
    model       TEXT,
    data        TEXT NOT NULL,            -- 完整剧本 JSON
    scene_count INTEGER DEFAULT 0,
    char_count  INTEGER DEFAULT 0,        -- 角色数
    line_count  INTEGER DEFAULT 0,        -- 对白条数
    gen_seconds REAL DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,             -- 埋点事件名：novel_upload / scene_generate ...
    props      TEXT,                      -- JSON
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def connect(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_config().db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
