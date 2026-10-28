# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の案の書き手の入口: 全部の port を読み、周のフォルダ r<k>/（k は往復の記録の往復の数 + 1）を開いて、書き手を起こすかを決める。
読めない port は書き手を起こさない。落ちない: 誤りは due 偽と訳を周のフォルダの intake.json に残す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

K = []   # この周の番号（compute が決め、fallback が同じ番号を返す）


def round_number() -> int:
    from src import files
    if not K:
        K.append(files.next_round(os.environ.get("INPUTS_PRIOR")))
    return K[0]


def compute():
    from src import files
    k = round_number()
    files.write_json(ports.place() / files.CURRENT_ROUND, {"round": k})   # lib を読む前に置く（後の node が今の周を引く）
    from src import steps
    return steps.intake(ports.place(), k, {
        "theme": os.environ.get("INPUTS_THEME"),
        "prior": os.environ.get("INPUTS_PRIOR"),
        "prior_design": os.environ.get("INPUTS_PRIOR_DESIGN"),
        "answers": os.environ.get("INPUTS_ANSWERS"),
        "world_rows": os.environ.get("INPUTS_WORLD_ROWS"),
        "policy": os.environ.get("INPUTS_POLICY"),
        "recorded": os.environ.get("INPUTS_RECORDED"),
        "base": os.environ.get("INPUTS_BASE"),
        "lang": os.environ.get("INPUTS_LANG")})


def fallback(why: str) -> dict:
    try:
        k = round_number()
    except Exception:  # noqa: BLE001 — 周の番号を決められなくても返答は返す
        k = 1
    return {"due": False, "round": k, "reason": f"周を開くノードの中で誤りが起きた: {why}"}


ports.run(compute, fallback)
