# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立の目から修正の段へ返す輪の集め eyes-back（docs/design/line.md の 1.3・5.4。trigger_rule: none_failed_min_one_success・when を持たない）。

周の頭 back-1〜back-4 の出力（走らなかった周は null）から、最後に走った周の頭の状態（返した周の記録 rows・抜けた訳 exit・残った作り残し left・
最後の合わせ・試験・独立の目・指紋・封じてよいか）を 1 つの出どころとして返す。封じ・最後の承認ノード・返す node・殻はこの 1 つから読む。
落ちない: 周の頭が 1 つも走っていない・読めない時は、輪の節が落ちたとして封じてよくない記録（最初の状態は持たない）を返す。

入力（with:）: back_1〜back_4（周の頭の出力。`{from, if_skipped: null}`）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

EXIT_FELL = "返す周のノードが落ちた（周の頭が前の周の出力か、案の直しの出力を読めなかった）"   # src/eyesback.py の EXITS["fell"] と同じ字（試験が突き合わせる）


def compute():
    from src import eyesback
    heads = [ports.parsed(os.environ.get(name)) for name in ("INPUTS_BACK_1", "INPUTS_BACK_2", "INPUTS_BACK_3", "INPUTS_BACK_4")]
    record = eyesback.last(heads)
    if record is None:
        raise ValueError("周の頭が 1 つも走っていない")
    return record


def fallback(reason: str) -> dict:
    return {"rows": [], "exit": EXIT_FELL, "left": [], "fixed": None, "tests": None, "eyes": None, "fingerprint": None, "green_ok": False,
            "eyes_ok": False, "sealable": False, "item_claims": None}


ports.run(compute, fallback)
