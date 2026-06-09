"""剧本质量检查（design.md §14 / §16 评估框架）。

对生成的结构化剧本做**可计算的**质量评估，产出 quality_report 与每场 quality_flags。
所有指标都从剧本结构直接算出（非 AI 自评），避免伪指标。

检测项：
- too_long       场景过长（元素过多/正文过长）
- low_dialogue   对白过少（动作多而台词少）
- thin_conflict  缺少冲突描述
- 角色失衡        用出场次数的 Gini 系数衡量（报告级）
- scene_coverage 原文事件覆盖率（被场景 span 覆盖的段落占比）
"""
from __future__ import annotations

# 阈值（surface 离群的过长场景，而非略高于平均者）
_MAX_ELEMENTS = 24          # 单场元素数上限
_MAX_SCENE_CHARS = 1000     # 单场正文字数上限
_LOW_DIALOGUE_ACTIONS = 4   # 动作块达到此数而台词 <=1 视为对白过少


def _scene_text_len(scene: dict) -> int:
    total = 0
    for e in scene.get("elements", []):
        total += len(e.get("text", "")) + len(e.get("line", ""))
    return total


def _scene_counts(scene: dict) -> tuple[int, int]:
    dialogue = sum(1 for e in scene.get("elements", []) if e.get("kind") == "dialogue")
    actions = sum(1 for e in scene.get("elements", []) if e.get("kind") == "action")
    return dialogue, actions


def gini(values: list[float]) -> float:
    """基尼系数：0=完全均衡，1=极端失衡。用于角色出场平衡。"""
    xs = sorted(v for v in values if v >= 0)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return round((2 * cum) / (n * sum(xs)) - (n + 1) / n, 3)


def scene_coverage(script: dict, paras_per_chapter: dict[int, int]) -> float:
    """原文事件覆盖率 = 被场景 span 覆盖的段落数 / 原文总段落数。"""
    covered: set[tuple[int, int]] = set()
    for s in script.get("scenes", []):
        ch = s["source"]["chapter"]
        a, b = s["source"]["span"]
        for p in range(a, b + 1):
            covered.add((ch, p))
    total = sum(paras_per_chapter.values())
    return round(len(covered) / total, 3) if total else 0.0


def check_quality(script: dict, paras_per_chapter: dict[int, int] | None = None) -> dict:
    """就地填充每场 quality_flags 与 quality_report.warnings，返回 quality_report。"""
    warnings: list[dict] = []
    scene_lengths: list[int] = []

    for scene in script.get("scenes", []):
        flags: list[str] = []
        sid = scene.get("id", "?")
        n_elements = len(scene.get("elements", []))
        text_len = _scene_text_len(scene)
        scene_lengths.append(text_len)
        dialogue, actions = _scene_counts(scene)

        if n_elements > _MAX_ELEMENTS or text_len > _MAX_SCENE_CHARS:
            flags.append("too_long")
            warnings.append({"scene": sid, "type": "too_long",
                             "detail": f"{text_len} 字 / {n_elements} 个元素，建议拆分。"})
        if dialogue == 0 or (actions >= _LOW_DIALOGUE_ACTIONS and dialogue <= 1):
            flags.append("low_dialogue")
            warnings.append({"scene": sid, "type": "low_dialogue",
                             "detail": f"动作 {actions} 块但台词仅 {dialogue} 句。"})
        if not scene.get("conflict"):
            flags.append("thin_conflict")

        scene["quality_flags"] = flags

    report = script.setdefault("quality_report", {})
    appearances = [c.get("appearances", 0) for c in script.get("characters", [])]
    report["avg_scene_length"] = round(sum(scene_lengths) / len(scene_lengths), 1) if scene_lengths else 0
    report["character_balance_gini"] = gini(appearances)
    if report["character_balance_gini"] > 0.6:
        warnings.append({"scene": "-", "type": "character_imbalance",
                         "detail": f"角色出场失衡(Gini={report['character_balance_gini']})，"
                                   f"主角戏份高度集中。"})
    if paras_per_chapter:
        report["scene_coverage"] = scene_coverage(script, paras_per_chapter)

    report["warnings"] = warnings
    return report
