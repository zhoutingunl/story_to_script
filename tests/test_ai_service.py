"""AIService 的离线/解析单测（不触网）。"""
import json

import pytest

from story2script.ai_service import AIError, AIService, OfflineBackend, RecordingBackend
from story2script.config import Config


def test_parse_json_plain():
    assert AIService.parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_with_code_fence():
    raw = "好的，结果如下：\n```json\n{\"name\": \"李婷\"}\n```\n以上。"
    assert AIService.parse_json(raw) == {"name": "李婷"}


def test_parse_json_array_with_noise():
    raw = "前言[1, 2, 3]后记"
    assert AIService.parse_json(raw) == [1, 2, 3]


def test_parse_json_invalid_raises():
    with pytest.raises(AIError):
        AIService.parse_json("这里没有任何 JSON")


def test_parse_json_repairs_inner_chinese_quotes():
    """模型把中文引号写成 ASCII "" 夹在汉字间，应被修复后解析。"""
    raw = '{"profile": "落入原主"傻子皂隶"躯壳的少年"}'
    out = AIService.parse_json(raw)
    assert "傻子皂隶" in out["profile"]


def test_parse_json_inner_quote_repair_keeps_structure():
    raw = '```json\n{"a": "他说"好"就走", "b": "正常值"}\n```'
    out = AIService.parse_json(raw)
    assert out["b"] == "正常值" and "好" in out["a"]


def test_offline_backend_missing_fixture(tmp_path):
    cfg = Config(ai_backend="offline", fixtures_dir=tmp_path)
    svc = AIService(backend=OfflineBackend(cfg), cfg=cfg)
    with pytest.raises(AIError) as ei:
        svc.chat("你好", task="greet")
    assert "缺少 fixture" in str(ei.value)


def test_record_then_replay_roundtrip(tmp_path):
    """录制后离线回放应拿到一致结果（record/replay 闭环）。"""
    class Stub:
        def chat(self, prompt, *, system=None, task="chat"):
            return '{"ok": true}'

    rec = RecordingBackend(Stub(), tmp_path)
    out = rec.chat("提取人物", system="你是编剧", task="extract")
    assert json.loads(out) == {"ok": True}

    cfg = Config(ai_backend="offline", fixtures_dir=tmp_path)
    off = OfflineBackend(cfg)
    replayed = off.chat("提取人物", system="你是编剧", task="extract")
    assert replayed == out


def test_make_backend_selection(tmp_path):
    assert type(AIService(cfg=Config(ai_backend="offline", fixtures_dir=tmp_path)).backend).__name__ == "OfflineBackend"
    assert type(AIService(cfg=Config(ai_backend="hermes")).backend).__name__ == "HermesBackend"
