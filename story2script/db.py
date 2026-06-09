"""SQLite 持久层（design.md §19 数据模型）。

用标准库 sqlite3，保持零额外依赖、易部署。表结构覆盖：
Novel / Chapter / Character / Scene / Dialogue / Script / Event(埋点/metrics)。

剧本的结构化内容（场景/元素等嵌套数据）以 JSON 文本存在 script.data 字段里——
关系表负责"可统计"的维度（数量、耗时、覆盖率），JSON 负责"可还原"的完整剧本，
两者职责分离。
"""
from __future__ import annotations

import json
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


# --------------------------------------------------------------------------- #
# 剧本存取
# --------------------------------------------------------------------------- #
def save_script(script: dict, *, gen_seconds: float = 0.0,
                db_path: str | None = None) -> int:
    """把剧本字典存库，返回 script id。novel 与 script 各落一行。"""
    meta = script.get("meta", {})
    qr = script.get("quality_report", {})
    char_count = len(script.get("characters", []))
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO novel(title, source_name, char_count) VALUES (?, ?, ?)",
            (meta.get("title", "未命名"), meta.get("source", ""), 0))
        novel_id = cur.lastrowid
        cur = conn.execute(
            """INSERT INTO script(novel_id, model, data, scene_count, char_count,
                                  line_count, gen_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (novel_id, meta.get("model", ""), json.dumps(script, ensure_ascii=False),
             qr.get("scene_count", len(script.get("scenes", []))),
             char_count, qr.get("dialogue_lines", 0), gen_seconds))
        return int(cur.lastrowid)


def get_script(script_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT data FROM script WHERE id = ?", (script_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def list_scripts(db_path: str | None = None) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT s.id, n.title, s.model, s.scene_count, s.char_count,
                      s.line_count, s.gen_seconds, s.created_at
               FROM script s JOIN novel n ON n.id = s.novel_id
               ORDER BY s.id DESC""").fetchall()
    return [dict(r) for r in rows]


def dashboard_stats(db_path: str | None = None) -> dict:
    """Dashboard 聚合统计（design.md §15）。真实数据，非伪指标。"""
    with connect(db_path) as conn:
        agg = conn.execute(
            """SELECT COUNT(*) AS scripts,
                      COALESCE(SUM(scene_count), 0) AS scenes,
                      COALESCE(SUM(char_count), 0) AS characters,
                      COALESCE(SUM(line_count), 0) AS lines,
                      COALESCE(AVG(scene_count), 0) AS avg_scenes,
                      COALESCE(AVG(line_count), 0) AS avg_lines,
                      COALESCE(AVG(gen_seconds), 0) AS avg_seconds
               FROM script""").fetchone()
        events = conn.execute(
            "SELECT name, COUNT(*) AS n FROM event GROUP BY name ORDER BY n DESC"
        ).fetchall()
    d = dict(agg)
    d["events"] = [dict(e) for e in events]
    return d


def track(name: str, props: dict | None = None, db_path: str | None = None) -> None:
    """埋点（design.md §18）。失败不应影响主流程。"""
    try:
        with connect(db_path) as conn:
            conn.execute("INSERT INTO event(name, props) VALUES (?, ?)",
                         (name, json.dumps(props or {}, ensure_ascii=False)))
    except Exception:
        pass
