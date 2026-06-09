"""Flask 入口（PR0 占位，Web UI 在 PR6 实现）。

  python -m story2script.app          # 开发模式直接起
  # 或生产用 gevent（见 README）
"""
from __future__ import annotations

from flask import Flask, jsonify

from . import __version__
from .config import get_config
from .db import init_db


def create_app() -> Flask:
    cfg = get_config()
    init_db(cfg.db_path)
    app = Flask(__name__)
    app.config["SECRET_KEY"] = cfg.flask_secret

    @app.get("/health")
    def health():
        return jsonify(status="ok", version=__version__,
                       ai_backend=cfg.ai_backend, model=cfg.model)

    return app


def main() -> None:
    create_app().run(host="127.0.0.1", port=8000, debug=True)


if __name__ == "__main__":
    main()
