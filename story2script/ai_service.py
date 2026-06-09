"""统一 AI 接入层。

design.md §8 要求所有 AI 能力统一通过 Hermes，并封装成 AIService。
这里在此基础上多做了一件对评审/演示很关键的事：**可插拔后端 + 离线回放**。

后端
----
- HermesBackend：真正调用 Hermes WebUI（需公司内网/VPN）。封装了 SKILL.md 里
  踩过的坑：工具自动批准、首事件看门狗、总时长预算、脏会话作废。
- OfflineBackend：按 (task, prompt 指纹) 回放本地 fixture，**无需网络**即可跑
  demo 与单测，保证结果确定性。
- RecordingBackend：包一层 Hermes，把真实响应落盘成 fixture，供 offline 回放。

为什么这么设计
--------------
Hermes 是公司内网服务，评审者本地不一定能连。可插拔 + 离线回放让：
  1) `pytest` 不依赖网络、结果确定；
  2) 没有 VPN 也能完整演示一遍流水线；
  3) "录制一次、离线回放" 是诚实的（fixture 来自真实模型输出，非手写假数据）。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from .config import Config, get_config


class AIError(RuntimeError):
    """AI 调用失败（连不通、超时、卡死、无 fixture 等）。"""


def _fingerprint(task: str, prompt: str, system: Optional[str]) -> str:
    """对一次调用生成稳定指纹，用作 fixture 文件名。"""
    h = hashlib.sha256()
    h.update((system or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(prompt.encode("utf-8"))
    return f"{task}.{h.hexdigest()[:16]}"


# --------------------------------------------------------------------------- #
# 后端
# --------------------------------------------------------------------------- #
class AIBackend:
    """后端接口：给定 prompt（与可选 system），返回模型的纯文本输出。"""

    def chat(self, prompt: str, *, system: Optional[str] = None, task: str = "chat") -> str:
        raise NotImplementedError


class HermesBackend(AIBackend):
    """调用 Hermes WebUI（8787）。会话生命周期 + 自动批准工具 + 看门狗。"""

    def __init__(self, cfg: Config):
        self.base = cfg.hermes_base
        self.model = cfg.model
        self.timeout = cfg.ai_timeout

    def _auto_approve(self, sid: str, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                r = requests.get(f"{self.base}/api/approval/pending",
                                 params={"session_id": sid}, timeout=5)
                if r.json().get("pending"):
                    requests.post(f"{self.base}/api/approval/respond",
                                  json={"session_id": sid, "choice": "always"}, timeout=5)
            except Exception:
                pass
            stop.wait(1.5)

    def chat(self, prompt: str, *, system: Optional[str] = None, task: str = "chat") -> str:
        message = prompt if not system else f"{system}\n\n{prompt}"
        try:
            sid = requests.post(f"{self.base}/api/session/new", json={"model": self.model},
                                timeout=30).json()["session"]["session_id"]
        except Exception as e:
            raise AIError(f"无法创建 Hermes 会话（是否连了 VPN？）：{e}") from e

        stop = threading.Event()
        threading.Thread(target=self._auto_approve, args=(sid, stop), daemon=True).start()
        try:
            stream_id = requests.post(
                f"{self.base}/api/chat/start",
                json={"session_id": sid, "message": message, "model": self.model},
                timeout=30,
            ).json()["stream_id"]

            full, event = "", ""
            deadline = time.time() + self.timeout
            last_event = time.time()
            watchdog = 60  # 首/任意事件 N 秒内无动静 → 判卡死
            with requests.get(f"{self.base}/api/chat/stream",
                              params={"stream_id": stream_id},
                              stream=True, timeout=(15, 120)) as resp:
                for raw in resp.iter_lines():
                    now = time.time()
                    if now > deadline:
                        raise AIError("Hermes 响应超时（总预算）")
                    if now - last_event > watchdog and not full:
                        raise AIError("Hermes 首事件看门狗超时（疑似卡死）")
                    if not raw:
                        continue
                    last_event = now
                    line = raw.decode("utf-8")
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if event == "token":
                            full += data["text"]
                        elif event == "approval":
                            requests.post(f"{self.base}/api/approval/respond",
                                          json={"session_id": sid, "choice": "always"}, timeout=5)
                        elif event == "done":
                            break
                        elif event == "error":
                            raise AIError(f"Hermes 返回错误：{data.get('message')}")
            if not full.strip():
                raise AIError("Hermes 未返回任何内容")
            return full
        finally:
            stop.set()
            try:  # 作废会话，避免 409 连锁
                requests.post(f"{self.base}/api/chat/cancel", json={"session_id": sid}, timeout=5)
            except Exception:
                pass


class OfflineBackend(AIBackend):
    """按 (task, prompt 指纹) 从 fixtures/ 回放。无网络依赖。"""

    def __init__(self, cfg: Config):
        self.dir = Path(cfg.fixtures_dir)

    def chat(self, prompt: str, *, system: Optional[str] = None, task: str = "chat") -> str:
        fp = self.dir / f"{_fingerprint(task, prompt, system)}.json"
        if not fp.exists():
            raise AIError(
                f"离线模式缺少 fixture：{fp.name}\n"
                f"请先用 hermes 后端跑一遍以录制（见 README『录制 fixture』），"
                f"或检查 task='{task}' 与输入是否与录制时一致。"
            )
        payload = json.loads(fp.read_text(encoding="utf-8"))
        return payload["response"]


class RecordingBackend(AIBackend):
    """包住一个真实后端，把响应落盘成 offline fixture。"""

    def __init__(self, inner: AIBackend, fixtures_dir: Path):
        self.inner = inner
        self.dir = Path(fixtures_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def chat(self, prompt: str, *, system: Optional[str] = None, task: str = "chat") -> str:
        response = self.inner.chat(prompt, system=system, task=task)
        fp = self.dir / f"{_fingerprint(task, prompt, system)}.json"
        fp.write_text(json.dumps(
            {"task": task, "system": system, "prompt": prompt, "response": response},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[record] {fp.name}", file=sys.stderr)
        return response


# --------------------------------------------------------------------------- #
# 门面
# --------------------------------------------------------------------------- #
_FENCE = re.compile(r"```(?:json|yaml|ya?ml)?\s*(.*?)```", re.DOTALL)

# CJK 文字 + 中文/全角标点 + 弯引号——用于识别"被当成中文引号的 ASCII 双引号"
_CJK = r"[㐀-鿿　-〿！-｠‘-‟]"
_INNER_QUOTE = re.compile(rf'(?<={_CJK})"(?={_CJK})')


def _repair_inner_quotes(text: str) -> str:
    """模型常把中文引号写成 ASCII ""，夹在汉字中间会破坏 JSON。

    结构性引号总有 ASCII 定界符（: , {{ }} [ ] 空白）相邻；内容引号两侧都是
    CJK 字符。据此把"被汉字包夹的 ASCII 双引号"替换成中文右引号，使 JSON 可解析。
    """
    return _INNER_QUOTE.sub("”", text)


class AIService:
    """高层模块（人物/场景/对白/剧本）统一用它。

    - chat(): 纯文本
    - chat_json(): 强制解析为 JSON（自动剥离 ```json``` 围栏、容错截取首个 {...}/[...]）
    """

    def __init__(self, backend: Optional[AIBackend] = None, cfg: Optional[Config] = None):
        self.cfg = cfg or get_config()
        self.backend = backend or self._make_backend(self.cfg)

    @staticmethod
    def _make_backend(cfg: Config) -> AIBackend:
        kind = (cfg.ai_backend or "hermes").lower()
        if kind == "offline":
            return OfflineBackend(cfg)
        if kind == "record":
            return RecordingBackend(HermesBackend(cfg), cfg.fixtures_dir)
        return HermesBackend(cfg)

    def chat(self, prompt: str, *, system: Optional[str] = None, task: str = "chat") -> str:
        return self.backend.chat(prompt, system=system, task=task)

    def chat_json(self, prompt: str, *, system: Optional[str] = None, task: str = "chat"):
        raw = self.chat(prompt, system=system, task=task)
        return self.parse_json(raw)

    @staticmethod
    def parse_json(raw: str):
        """从模型输出里抠出 JSON。容忍代码围栏、前后多余文本。"""
        text = raw.strip()
        m = _FENCE.search(text)
        if m:
            text = m.group(1).strip()

        def _try(candidate: str):
            for variant in (candidate, _repair_inner_quotes(candidate)):
                try:
                    return json.loads(variant)
                except json.JSONDecodeError:
                    continue
            return None

        result = _try(text)
        if result is not None:
            return result
        # 容错：截取第一个 { 或 [ 到对应的最后一个 } 或 ]
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            start = text.find(open_ch)
            end = text.rfind(close_ch)
            if start != -1 and end > start:
                result = _try(text[start:end + 1])
                if result is not None:
                    return result
        raise AIError(f"无法将模型输出解析为 JSON：{raw[:200]}...")
