# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""2 つの修正の段（fix と refix-run）と、独立の目から返した修正の段と、段ごとの差分の審査（lens・delta-review）を合わせて後の段へ渡す
node fixed（docs/design/line.md の 4.3。決まりは src/stages.py の fixed）。

入力（with:）: from_spec（start の from_spec。仕様駆動の run は異議を止めにする）・fix_in（fix-in の出力まるごと）と、受け皿の got（fix・lens・delta・replan・refix・lens_2・delta_2）・after_fix・raise の出力。
走らなかった物は `{from, if_skipped: null}` で null。独立の目から返した修正の段を合わせる周の節（back-k-fixed）だけが more（前の周までに返した段の
fix の got の並び）と add（この周の返しの修正の受け皿の got。落ちていれば null）を足し、出力の more は more の後ろに add を足した並びになる。受け皿の got と出力は要る欄を全部名指して読む（欄の欠けた前の版の返りを resume で
受けたら空と読まずに止める。integration.md 4.3-12）。例外の時は止めの語 works:line-script を返し、試験の関門から先へ進めない
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIX = ("ok", "reason", "units", "groups", "conflicts", "carry", "replan_items", "objection", "diff", "start_tree", "reply",
       "ruled_reply", "scope", "checked", "allowed_test_changes", "changed", "x_scalars", "handoffs", "handoff_titles", "mismatched", "plan_declared",
       "stop_reason", "allowed_tests", "accept_trace", "closure", "tdd_unit", "tdd", "frozen", "removed", "tdd_refused",
       "item_claims", "freeze_off", "removed_tests", "untested", "report")
LENS = ("ok", "status", "reason", "rows", "ran", "failed", "not_routed", "carry", "report")
DELTA = ("ok", "status", "reason", "rounds", "pass", "holes", "diff", "carry", "report")
PLAN = ("ok", "status", "reason", "mode", "round", "owed", "plan", "fix_plan", "reply", "handoff", "replan", "ripple", "rejects",
        "gave_up", "report")
FIX_IN = ("go", "no_fix", "plan", "ripple")
AFTER_FIX = ("replan", "prior", "stop_reason")
RAISE = ("units", "checks", "skip_why", "eyes_due", "raised", "counted", "lines", "stop_reason")


def picked(raw, names):
    got = ports.picked(raw, names)
    return None if got is None else dict(got)


def compute():
    from src import stages
    values = {
        "fix_in": picked(os.environ.get("INPUTS_FIX_IN"), FIX_IN),
        "fix": picked(os.environ.get("INPUTS_FIX"), FIX),
        "after_fix": picked(os.environ.get("INPUTS_AFTER_FIX"), AFTER_FIX),
        "raise": picked(os.environ.get("INPUTS_RAISE"), RAISE),
        "lens": picked(os.environ.get("INPUTS_LENS"), LENS),
        "delta": picked(os.environ.get("INPUTS_DELTA"), DELTA),
        "replan": picked(os.environ.get("INPUTS_REPLAN"), PLAN),
        "refix": picked(os.environ.get("INPUTS_REFIX"), FIX),
        "lens_2": picked(os.environ.get("INPUTS_LENS_2"), LENS),
        "delta_2": picked(os.environ.get("INPUTS_DELTA_2"), DELTA),
        "from_spec": ports.text(os.environ.get("INPUTS_FROM_SPEC")).strip() == "true",
    }
    earlier, added = ports.parsed(os.environ.get("INPUTS_MORE")), picked(os.environ.get("INPUTS_ADD"), FIX)
    if earlier is not None:   # 返しの周の節だけが more を持つ（元の fixed は持たず、鍵が無い）
        values[stages.MORE] = [*earlier, added]
    return stages.fixed(values)


def fallback(reason: str) -> dict:
    from src import guard
    return {"go": False, "done": False, "held": True, "no_fix": False, "diffed": False, "checks": False, "eyes_due": False,
            "skip_why": "", "rejudge": False, "refixed": False, "stages": [], "carry": [], "tdd": [], "units": [], "groups": [],
            "conflicts": [], "replan_items": [], "objection": "", "diff": None, "item_claims": None, "allowed_test_changes": [],
            "changed": None, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [], "plan_declared": [], "plan": None, "ripple": None,
            "more": [], "left": [], "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)
