"""Flask Web UI（design.md §22 Demo 流程 / §15 Dashboard）。

页面：
  /                上传 / 用示例生成 + 已生成剧本列表
  /generate        运行流水线（POST）：示例 或 上传文件
  /script/<id>     剧本详情：人物 / 场景对白 / Story Graph / 质量报告
  /script/<id>/yaml  下载 script.yaml
  /script/<id>/graph.json  人物关系图数据（供前端可视化）
  /dashboard       聚合统计
  /health          健康检查

设计取舍：示例生成走离线 fixture（瞬时、无需 VPN），上传文件走配置的 AI 后端
（hermes 需内网）。首次启动若库空，自动用 samples/script.yaml 播种一条，
保证打开即有内容可看（demo 健壮性）。
"""
from __future__ import annotations

import time
from pathlib import Path

import yaml
from flask import (Flask, Response, abort, flash, jsonify, redirect,
                   render_template, request, url_for)

from . import __version__
from .ai_service import AIError, AIService
from .config import get_config
from .db import (dashboard_stats, get_script, init_db, list_scripts,
                 save_script, track)
from .parser import parse_novel_text
from .pipeline import run_pipeline
from .schema import reference_warnings, validate_script
from .yaml_exporter import to_yaml

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_NOVEL = ROOT / "samples" / "story.txt"
SAMPLE_SCRIPT = ROOT / "samples" / "script.yaml"


def create_app() -> Flask:
    cfg = get_config()
    init_db(cfg.db_path)
    app = Flask(__name__)
    app.config["SECRET_KEY"] = cfg.flask_secret
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4MB 上限

    _seed_if_empty(cfg.db_path)

    @app.get("/")
    def index():
        track("dashboard_open", db_path=cfg.db_path)
        return render_template("index.html", scripts=list_scripts(cfg.db_path),
                               cfg=cfg, has_sample=SAMPLE_NOVEL.exists())

    @app.post("/generate")
    def generate():
        title, text, source = _read_input(cfg)
        if text is None:
            flash("请上传小说文件，或点击「用示例小说生成」。")
            return redirect(url_for("index"))
        track("novel_upload", {"source": source, "chars": len(text)}, db_path=cfg.db_path)
        novel = parse_novel_text(text, title=title, source_name=source)
        try:
            t0 = time.time()
            ai = AIService(cfg=cfg)
            script = run_pipeline(novel, ai, model=cfg.model,
                                  dialogue_mode=request.form.get("mode", "conservative"))
            dt = time.time() - t0
        except AIError as e:
            flash(f"生成失败：{e}")
            return redirect(url_for("index"))
        sid = save_script(script, gen_seconds=dt, db_path=cfg.db_path)
        track("script_generate",
              {"scenes": script["quality_report"]["scene_count"], "seconds": round(dt, 1)},
              db_path=cfg.db_path)
        return redirect(url_for("script_view", script_id=sid))

    @app.get("/script/<int:script_id>")
    def script_view(script_id: int):
        script = get_script(script_id, cfg.db_path)
        if not script:
            abort(404)
        chapters_summary = _chapter_index(script)
        return render_template("script.html", script=script, sid=script_id,
                               warnings=reference_warnings(script),
                               valid=not validate_script(script),
                               chapters=chapters_summary)

    @app.get("/script/<int:script_id>/yaml")
    def script_yaml(script_id: int):
        script = get_script(script_id, cfg.db_path)
        if not script:
            abort(404)
        track("yaml_export", {"script": script_id}, db_path=cfg.db_path)
        return Response(
            to_yaml(script), mimetype="application/x-yaml",
            headers={"Content-Disposition": f'attachment; filename="script_{script_id}.yaml"'})

    @app.get("/script/<int:script_id>/graph.json")
    def script_graph(script_id: int):
        script = get_script(script_id, cfg.db_path)
        if not script:
            abort(404)
        return jsonify(script.get("story_graph", {"nodes": [], "edges": []}))

    @app.get("/dashboard")
    def dashboard():
        return render_template("dashboard.html", stats=dashboard_stats(cfg.db_path), cfg=cfg)

    @app.get("/health")
    def health():
        return jsonify(status="ok", version=__version__,
                       ai_backend=cfg.ai_backend, model=cfg.model)

    return app


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
def _read_input(cfg) -> tuple[str, str | None, str]:
    """解析请求：示例 or 上传文件，返回 (title, text|None, source)。"""
    if request.form.get("use_sample") and SAMPLE_NOVEL.exists():
        return ("桐城旧事", SAMPLE_NOVEL.read_text(encoding="utf-8"), "story.txt")
    f = request.files.get("novel")
    if f and f.filename:
        name = f.filename
        if name.lower().endswith(".pdf"):
            from .parser import _read_pdf
            tmp = Path(cfg.db_path).parent / f"_upload_{int(time.time())}.pdf"
            f.save(tmp)
            try:
                text = _read_pdf(tmp)
            finally:
                tmp.unlink(missing_ok=True)
        else:
            text = f.read().decode("utf-8", errors="ignore")
        return (Path(name).stem, text, name)
    return ("", None, "")


def _chapter_index(script: dict) -> list[dict]:
    """按章节聚合场景，便于剧本页分章展示。"""
    by_ch: dict[int, list] = {}
    for s in script.get("scenes", []):
        by_ch.setdefault(s["source"]["chapter"], []).append(s)
    return [{"chapter": ch, "scenes": by_ch[ch]} for ch in sorted(by_ch)]


def _seed_if_empty(db_path: str) -> None:
    if list_scripts(db_path) or not SAMPLE_SCRIPT.exists():
        return
    try:
        script = yaml.safe_load(SAMPLE_SCRIPT.read_text(encoding="utf-8"))
        if script:
            save_script(script, db_path=db_path)
    except Exception:
        pass


def main() -> None:
    create_app().run(host="127.0.0.1", port=8000, debug=True)


if __name__ == "__main__":
    main()
