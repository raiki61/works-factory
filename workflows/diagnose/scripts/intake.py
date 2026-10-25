# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""診断の入口: port を読み、道（判定か再審）を決め、この block のファイルを名で消して道ごとの支度をする。判定の道は対象差分・素材の
15 欄・材料のファイル・作業ツリーの写し、再審の道は 1 回目の判定の写しと単位の前の写し。読めない port は due: false と訳。落ちない（思わぬ落ちは intake.json に status: failed と訳を書く）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import inputs
    raw = {
        "request": os.environ.get("INPUTS_REQUEST"), "request_origin": os.environ.get("INPUTS_REQUEST_ORIGIN"),
        "objection": os.environ.get("INPUTS_OBJECTION"), "base": os.environ.get("INPUTS_BASE"),
        "purpose": os.environ.get("INPUTS_PURPOSE"), "constraints": os.environ.get("INPUTS_CONSTRAINTS"),
        "materials": os.environ.get("INPUTS_MATERIALS"), "pr_material": os.environ.get("INPUTS_PR_MATERIAL"),
        "reply_sources": os.environ.get("INPUTS_REPLY_SOURCES"),
        "baseline": os.environ.get("INPUTS_BASELINE"), "world_rows": os.environ.get("INPUTS_WORLD_ROWS"),
        "row_asks": os.environ.get("INPUTS_ROW_ASKS"), "depth_why": os.environ.get("INPUTS_DEPTH_WHY"),
        "spec_rows": os.environ.get("INPUTS_SPEC_ROWS"), "spec_origin": os.environ.get("INPUTS_SPEC_ORIGIN"),
        "answers": os.environ.get("INPUTS_ANSWERS"), "prior_failures": os.environ.get("INPUTS_PRIOR_FAILURES"),
        "pr_text": os.environ.get("INPUTS_PR_TEXT"), "policy": os.environ.get("INPUTS_POLICY"), "prior": os.environ.get("INPUTS_PRIOR"),
        "prior_brief": os.environ.get("INPUTS_PRIOR_BRIEF"), "prior_inputs": os.environ.get("INPUTS_PRIOR_INPUTS"),
        "spec": os.environ.get("INPUTS_SPEC"), "verify": os.environ.get("INPUTS_VERIFY"), "excluded": os.environ.get("INPUTS_EXCLUDED"),
        "request_files": os.environ.get("INPUTS_REQUEST_FILES"), "lang": os.environ.get("INPUTS_LANG"),
    }
    return inputs.intake(ports.place(), Path.cwd(), raw)


def fallback(why: str) -> dict:
    rejudge = bool(os.environ.get("INPUTS_OBJECTION", "").strip())
    head = "再審の支度ができない" if rejudge else "判定役の材料を組めない"
    mode, reason = ("rejudge" if rejudge else "judge"), f"{head}（{why}）"
    try:
        from src import inputs
        inputs.intake_fell(ports.place(), mode, reason)
    except Exception:  # noqa: BLE001 — 落ちない node の口。控えが書けなくても返りは返す
        pass
    return {"due": False, "mode": mode, "reason": reason}


ports.run(compute, fallback)
