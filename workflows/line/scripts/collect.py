# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""全部のブロックと関所と返しの節の返りを、report の入力の形に集める返しの節 collect（埋め P2。trigger_rule: all_done）。

欄は report の YAML の inputs: の名の `-` を `_` にした物で、report の with: は $collect.output.<欄> だけを読む。
ブロックと計画の往復の返りは受け皿の節（returned.py。<include の id>-out・plan-rounds-out・plan-rounds-review-out）の出力を
`{from: "$<受け皿>.output", if_skipped: null}` で受ける。受けた物の got が、include の id ごとの返りの欄の object になる。
飛ばされた（受ける節が落ちたか飛ばされた）受け皿は null。計画の往復の返りは plan と plan-review の欄を別の受け皿で受け、欄が全部
null の方（plan-review が飛ばされた周で抜けた往復）は null。
fix は 1 回目と 2 度目の修正を合わせた節 fixed の返り（申し出は段ごとの指し札の配列。report の約束の fix の形）。fixed が飛ばされた
（2 度目の修正の中が落ちた）時は 1 回目の返り。

入力（with:）: <include の id>（受け皿の出力）・plan・plan_review（計画の往復の受け皿の出力）・start・fixed・gate_<関所>
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

RECEIVED = ("test_gate_base", "judge", "rejudge", "replan", "replan_review", "fix", "test_gate_final", "eyes", "merge_seal",
            "merge_apply")
ROUNDS = ("plan", "plan_review")
GATES = ("gate_start", "gate_before_fix", "gate_replan", "gate_final")


def filled(got: dict | None) -> dict | None:
    return None if got is None or all(value is None for value in got.values()) else got


def collect(received: dict, line: dict) -> dict:
    got = {name: (boundary.value(received.get(name)) or {}).get("got") for name in (*RECEIVED, *ROUNDS)}
    fixed = boundary.value(line["fixed"])
    return {
        **got,
        "fix": None if got["fix"] is None else fixed if isinstance(fixed, dict) else got["fix"],
        **{name: filled(got[name]) for name in ROUNDS},
        "start": boundary.value(line["start"]),
        **{name: boundary.value(line["gates"][name]) for name in GATES},
    }


def received_of_env() -> dict:
    return {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*RECEIVED, *ROUNDS)}


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START"),
        "fixed": os.environ.get("INPUTS_FIXED"),
        "gates": {name: os.environ.get(f"INPUTS_{name.upper()}") for name in GATES},
    }


def fallback(reason: str) -> dict:
    return {**{name: None for name in (*RECEIVED, *ROUNDS)}, "start": None, **{name: None for name in GATES}}


if __name__ == "__main__":
    boundary.run(lambda: collect(received_of_env(), line_of_env()), fallback)
