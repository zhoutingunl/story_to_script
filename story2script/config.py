"""集中配置：全部从环境变量/.env 读取，避免把密钥、地址硬编码进代码。

设计原因（呼应 design.md §24 安全设计）：
- Hermes 地址、模型、超时等都可被环境变量覆盖，方便在不同网络/机器上运行；
- 不在仓库里保存任何 token/cookie/密钥；
- 单测默认走 offline 后端，不依赖网络。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv 是可选依赖；没装也能用纯环境变量运行
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - 仅在缺少 dotenv 时触发
    pass

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _env(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val if val not in (None, "") else default


@dataclass(frozen=True)
class Config:
    ai_backend: str = _env("STORY2SCRIPT_AI_BACKEND", "hermes")
    hermes_base: str = _env("HERMES_BASE", "http://10.210.32.30:8787").rstrip("/")
    model: str = _env("STORY2SCRIPT_MODEL", "MiniMax-M3")
    ai_timeout: int = int(_env("STORY2SCRIPT_AI_TIMEOUT", "300"))
    db_path: str = _env("STORY2SCRIPT_DB", str(ROOT / "story2script.db"))
    flask_secret: str = _env("FLASK_SECRET", "dev-only-change-me")
    fixtures_dir: Path = FIXTURES_DIR

    @classmethod
    def load(cls) -> "Config":
        return cls()


def get_config() -> Config:
    return Config.load()
