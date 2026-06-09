"""pytest 公共夹具。

默认强制 offline 后端，保证单测不依赖网络、结果确定。
"""
import os

import pytest

os.environ.setdefault("STORY2SCRIPT_AI_BACKEND", "offline")
os.environ.setdefault("STORY2SCRIPT_DB", ":memory:")


class FakeBackend:
    """可编程的假后端：按 task 返回预设响应，用于离线单测。"""

    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.calls: list[dict] = []

    def chat(self, prompt, *, system=None, task="chat"):
        self.calls.append({"task": task, "prompt": prompt, "system": system})
        if task in self.responses:
            return self.responses[task]
        if "*" in self.responses:
            return self.responses["*"]
        raise KeyError(f"FakeBackend 未配置 task='{task}' 的响应")


@pytest.fixture
def fake_backend():
    return FakeBackend
