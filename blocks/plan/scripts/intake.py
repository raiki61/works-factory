# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の入口: 全部の port を読み、周のフォルダ r<k>/（k は prior.round + 1）を開いて、形（ruling が空でなければ replan）と役を起こすかを決める。
読めない judgment・world_rows・prior（形 replan は prior・ruling）は役を起こさない。落ちない: 誤りは go 偽と訳を周のフォルダの round.json に残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), Path.cwd(), {
        "judgment": os.environ.get("INPUTS_JUDGMENT"),
        "units": os.environ.get("INPUTS_UNITS"),
        "answer_ties": os.environ.get("INPUTS_ANSWER_TIES"),
        "materials": os.environ.get("INPUTS_MATERIALS"),
        "answers": os.environ.get("INPUTS_ANSWERS"),
        "takes_push": os.environ.get("INPUTS_TAKES_PUSH"),
        "verify": os.environ.get("INPUTS_VERIFY"),
        "excluded": os.environ.get("INPUTS_EXCLUDED"),
        "depth_record": os.environ.get("INPUTS_DEPTH_RECORD"),
        "decisions": os.environ.get("INPUTS_DECISIONS"),
        "world_rows": os.environ.get("INPUTS_WORLD_ROWS"),
        "structure": os.environ.get("INPUTS_STRUCTURE"),
        "spec": os.environ.get("INPUTS_SPEC"),
        "policy": os.environ.get("INPUTS_POLICY"),
        "prior_failures": os.environ.get("INPUTS_PRIOR_FAILURES"),
        "prior": os.environ.get("INPUTS_PRIOR"),
        "ruling": os.environ.get("INPUTS_RULING"),
        "conflicts": os.environ.get("INPUTS_CONFLICTS"),
        "base": os.environ.get("INPUTS_BASE"),
        "review_rev": os.environ.get("INPUTS_REVIEW_REV"),
        "diff_base": os.environ.get("INPUTS_DIFF_BASE"),
        "lang": os.environ.get("INPUTS_LANG")})


def fallback(why: str) -> dict:
    try:
        from src import files
        return files.crash_round(ports.place(), f"周を開くノードの中で誤りが起きた: {why}")
    except Exception:  # noqa: BLE001 — 控えを残せなくても返りは返す
        return {"go": False, "mode": "plan", "round": 1, "reason": f"周を開くノードの中で誤りが起きた: {why}"}


ports.run(compute, fallback)
