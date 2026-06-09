"""db 层 smoke 测试（内存库）。"""
from story2script.db import connect, init_db


def test_init_and_insert():
    init_db(":memory:")  # 仅验证 schema 可建


def test_schema_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    init_db(db)
    with connect(db) as conn:
        conn.execute("INSERT INTO novel(title, char_count) VALUES (?, ?)", ("测试小说", 100))
    with connect(db) as conn:
        row = conn.execute("SELECT title, char_count FROM novel").fetchone()
    assert row["title"] == "测试小说"
    assert row["char_count"] == 100
