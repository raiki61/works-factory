# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""全部のブロックと関所と返しの節の返りを、report の入力の形に集める返しの節 collect（埋め P2。trigger_rule: all_done）。

欄は report の YAML の inputs: の名の `-` を `_` にした物で、report の with: は $collect.output.<欄> だけを読む。
ブロックと計画の往復の返りは受け皿の節（returned.py。<include の id>-out・plan-rounds-out）の出力を
`{from: "$<受け皿>.output", if_skipped: null}` で受ける。受けた物の got が、include の id ごとの返りの欄の object になる。
飛ばされた（受ける節が落ちたか飛ばされた）受け皿は null。計画の往復の返りは plan と plan-review の欄に分け、欄が全部 null の方は null。
fix は 1 回目と 2 度目の修正を合わせた節 fixed の返り（申し出は段ごとの指し札の配列。report の約束の fix の形）。fixed が飛ばされた
（2 度目の修正の中が落ちた）時は 1 回目の返り。2 度目の修正の段の行（refixed・2 度目の異議をつないだ objection・1 回目の行を写した 2 度目の申し出）も fixed の返りが運ぶ。

線の節の値（docs/design.md の report の返りの「線の値」）:
- stops: 線の script の節（STOPS）の止めの語 {節: 語}（入口の拒み・無人の関所の止め・線の script の例外・人の止め。空と飛ばされた節は
  載せない）
- deferred・widened・final_reasons: 無人の run で関所に載せなかった問い・聞かずに通した範囲を広げるだけの直し・最後の関所を開ける
  理由（飛ばされた節は []）
- prior_failures: 依頼の前の失敗の指し札（start の返り）・redepth: 直した後の深さの上げ直しの返り（飛ばされた節は null）
- optional: 受け止める段の宣言（線の YAML の collect の with: の 1 か所。落ちても線が先へ進めてよい段の節の id の頭の並び）

入力（with:）: <include の id>（受け皿の出力）・plan_rounds・start・fixed・gate_<関所>・stop_<節>・deferred・widened・final_reasons・
prior_failures・redepth・optional
"""
import os

import linekit
import plan_out

RECEIVED = ("test_gate_base", "judge", "rejudge", "replan", "replan_review", "fix", "test_gate_final", "eyes", "merge_seal",
            "merge_apply")
GATES = ("gate_start", "gate_before_fix", "gate_replan", "gate_final")
STOPS = ("start", "answer-start", "ask-before-fix", "answer-before-fix", "after-fix", "judged", "ask-replan", "answer-replan", "fixed",
         "redepth", "ask-final", "answer-final")
LISTS = ("deferred", "widened", "final_reasons", "optional")
VALUES = ("prior_failures", "redepth")


def group(got: dict | None, keys) -> dict | None:
    part = {key: (got or {}).get(key) for key in keys}
    return None if all(value is None for value in part.values()) else part


def collect(received: dict, line: dict) -> dict:
    got = {name: (linekit.value(received.get(name)) or {}).get("got") for name in (*RECEIVED, "plan_rounds")}
    rounds = got.pop("plan_rounds")
    fixed = linekit.value(line["fixed"])
    stops = {node: linekit.text((line.get("stops") or {}).get(node)) for node in STOPS}
    return {
        **got,
        "fix": None if got["fix"] is None else fixed if isinstance(fixed, dict) else got["fix"],
        "plan": group(rounds, plan_out.PLAN),
        "plan_review": group(rounds, plan_out.REVIEW),
        "start": linekit.value(line["start"]),
        **{name: linekit.value(line["gates"][name]) for name in GATES},
        "stops": {node: word for node, word in stops.items() if word},
        **{name: linekit.items(line.get(name)) for name in LISTS},
        **{name: linekit.value(line.get(name)) for name in VALUES},
    }


def received_of_env() -> dict:
    return {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*RECEIVED, "plan_rounds")}


def stop_key(node: str) -> str:
    return f"stop_{node.replace('-', '_')}"


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START"),
        "fixed": os.environ.get("INPUTS_FIXED"),
        "gates": {name: os.environ.get(f"INPUTS_{name.upper()}") for name in GATES},
        "stops": {node: os.environ.get(f"INPUTS_{stop_key(node).upper()}") for node in STOPS},
        **{name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*LISTS, *VALUES)},
    }


def fallback(reason: str) -> dict:
    return {**{name: None for name in RECEIVED}, "plan": None, "plan_review": None, "start": None, **{name: None for name in GATES},
            "stops": {"collect": linekit.LINE_SCRIPT}, **{name: [] for name in LISTS}, **{name: None for name in VALUES}}


if __name__ == "__main__":
    linekit.run(lambda: collect(received_of_env(), line_of_env()), fallback)
