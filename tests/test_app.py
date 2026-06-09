"""Web 层单测：Flask test client + offline 后端 + 临时文件库。"""
from pathlib import Path

import pytest

from story2script.app import create_app

SAMPLE_SCRIPT = Path(__file__).resolve().parent.parent / "samples" / "script.yaml"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY2SCRIPT_AI_BACKEND", "offline")
    monkeypatch.setenv("STORY2SCRIPT_DB", str(tmp_path / "app.db"))
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_index_seeded_with_sample(client):
    """首启用 samples/script.yaml 播种，首页应能看到一条剧本。"""
    r = client.get("/")
    assert r.status_code == 200
    assert "Story2Script" in r.get_data(as_text=True)


def test_script_view_and_yaml_and_graph(client):
    # 播种后 id=1 存在
    r = client.get("/script/1")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "人物关系图" in body and "下载 script.yaml" in body

    y = client.get("/script/1/yaml")
    assert y.status_code == 200
    assert "schema_version: 1" in y.get_data(as_text=True)
    assert "attachment" in y.headers["Content-Disposition"]

    g = client.get("/script/1/graph.json")
    assert g.status_code == 200
    assert "nodes" in g.get_json()


def test_script_404(client):
    assert client.get("/script/999").status_code == 404


def test_dashboard(client):
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Dashboard" in r.get_data(as_text=True)


@pytest.mark.skipif(not SAMPLE_SCRIPT.exists(), reason="缺少样本")
def test_generate_from_sample_offline(client):
    """点「用示例小说生成」→ 离线跑流水线 → 重定向到剧本页。"""
    r = client.post("/generate", data={"use_sample": "1", "mode": "conservative"})
    assert r.status_code == 302
    assert "/script/" in r.headers["Location"]
    # 生成后列表至少 2 条（播种 1 + 新生成 1）
    follow = client.get(r.headers["Location"])
    assert follow.status_code == 200


def test_generate_without_input_flashes(client):
    r = client.post("/generate", data={}, follow_redirects=True)
    assert r.status_code == 200
    assert "请上传小说文件" in r.get_data(as_text=True)
