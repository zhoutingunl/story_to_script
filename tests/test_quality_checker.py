"""QualityChecker 单测：可计算指标、场景旗标、覆盖率。全部离线。"""
from story2script.quality_checker import (
    check_quality,
    gini,
    scene_coverage,
)


def _scene(sid, elements, conflict="有冲突", chapter=1, span=(0, 1)):
    return {"id": sid, "source": {"chapter": chapter, "span": list(span)},
            "conflict": conflict, "elements": elements}


def _dlg(line="台词"):
    return {"kind": "dialogue", "character": "c1", "line": line, "mode": "extracted"}


def _act(text="动作"):
    return {"kind": "action", "text": text}


def test_gini_balanced_vs_skewed():
    assert gini([5, 5, 5, 5]) == 0.0
    assert gini([100, 1, 1, 1]) > 0.5
    assert gini([]) == 0.0


def test_low_dialogue_flag():
    script = {"scenes": [_scene("s1", [_act(), _act(), _act(), _act(), _dlg()])],
              "characters": []}
    report = check_quality(script)
    assert "low_dialogue" in script["scenes"][0]["quality_flags"]
    assert any(w["type"] == "low_dialogue" for w in report["warnings"])


def test_no_dialogue_is_low_dialogue():
    script = {"scenes": [_scene("s1", [_act()])], "characters": []}
    check_quality(script)
    assert "low_dialogue" in script["scenes"][0]["quality_flags"]


def test_too_long_flag_by_chars():
    big = _act("一" * 1100)
    script = {"scenes": [_scene("s1", [big, _dlg(), _dlg()])], "characters": []}
    check_quality(script)
    assert "too_long" in script["scenes"][0]["quality_flags"]


def test_thin_conflict_flag():
    script = {"scenes": [_scene("s1", [_dlg(), _dlg()], conflict="")], "characters": []}
    check_quality(script)
    assert "thin_conflict" in script["scenes"][0]["quality_flags"]


def test_healthy_scene_no_flags():
    script = {"scenes": [_scene("s1", [_act(), _dlg(), _act(), _dlg()])], "characters": []}
    check_quality(script)
    assert script["scenes"][0]["quality_flags"] == []


def test_character_imbalance_warning():
    chars = [{"appearances": 300}, {"appearances": 2}, {"appearances": 1}]
    script = {"scenes": [_scene("s1", [_dlg(), _dlg()])], "characters": chars}
    report = check_quality(script)
    assert report["character_balance_gini"] > 0.6
    assert any(w["type"] == "character_imbalance" for w in report["warnings"])


def test_scene_coverage():
    script = {"scenes": [
        _scene("s1", [_dlg()], chapter=1, span=(0, 2)),
        _scene("s2", [_dlg()], chapter=2, span=(0, 1)),
    ]}
    # 第1章覆盖段 0-2(3段)，第2章覆盖段 0-1(2段)；总段数 = 5+4 = 9
    cov = scene_coverage(script, {1: 5, 2: 4})
    assert cov == round(5 / 9, 3)


def test_check_quality_sets_report_fields():
    script = {"scenes": [_scene("s1", [_act(), _dlg()])],
              "characters": [{"appearances": 10}]}
    report = check_quality(script, {1: 2})
    assert "avg_scene_length" in report
    assert "character_balance_gini" in report
    assert "scene_coverage" in report
    assert "warnings" in report
