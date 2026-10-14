# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""全部のサブグラフと承認ノードと返しのノードの出力を、report の入力の形に集める返しのノード collect（埋め P2。trigger_rule: all_done）。

欄は report の YAML の inputs: の名の `-` を `_` にした物で、report の with: は $collect.output.<欄> だけを読む。
サブグラフと計画の往復の出力は受け皿のノード（returned.py。<include の id>-out・plan-rounds-out・plan-rounds-review-out）の出力を
`{from: "$<受け皿>.output", if_skipped: null}` で受ける。受けた物の got が、include の id ごとの出力の欄の object になる。
飛ばされた（受けるノードが落ちたか飛ばされた）受け皿は null。計画の往復の出力は plan と plan-review の欄を別の受け皿で受け、欄が全部
null の方（plan-review が飛ばされた周で抜けた往復）は null。直す物が無い周（計画の往復が飛び、独立設計だけを作る design-only が
走った）は、plan-review の欄に design-only の受け皿の出力を置く（L-W07）。
fix は 1 回目と 2 度目の修正を合わせたノード fixed の出力（申し出は段ごとのポインタの配列。report の約束の fix の形）。fixed が
飛ばされた（2 度目の修正の中が落ちた）時は 1 回目の出力。2 度目の修正の段の行（refixed・2 度目の異議をつないだ objection・1 回目の行を
写した 2 度目の申し出）も fixed の出力が運ぶ。

メイングラフのノードの値（docs/design.md の report の出力の「メイングラフの値」）:
- stops: メイングラフの script のノード（STOPS）の止めの語 {ノード: 語}（入口の拒み・無人の承認ノードの止め・script の例外・人の止め。
  空と飛ばされたノードは載せない）
- deferred・widened・final_reasons・spec_changed: 無人の run で承認ノードに載せなかった問い・聞かずに通した範囲を広げるだけの直し・
  最後の承認ノードを開ける理由・承認の後に受け入れ条件のテストが変わった問い（spec-check の questions）（飛ばされたノードは []）
- prior_failures: 依頼の前の失敗のポインタ（start の出力）・redepth: 直した後の深さの上げ直しの出力・spec_unchecked: 受け入れ条件の
  テストを照らせなかったか（spec-check の unchecked）（飛ばされたノードは null）
- optional: 受け止める段の宣言（メイングラフの YAML の collect の with: の 1 か所。落ちても先へ進めてよい段のノードの id の頭の並び）

result が $collect.output を読むので、このノードは落ちない: 境の口を読めない時も、標準ライブラリだけで fallback の出力を書く（止めの
理由は LINE_SCRIPT。境の口の LINE_SCRIPT の写しで、lib/tests/test_stopby.py が突き合わせる）。

入力（with:）: <include の id>（受け皿の出力）・plan・plan_review・design_only（計画の往復と直す物が無い周の受け皿の出力）・start・
fixed・gate_<承認ノード>・stop_<ノード>・deferred・widened・final_reasons・spec_changed・prior_failures・redepth・spec_unchecked・optional
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # result が読むノードは落ちない（上の docstring）
    boundary, unread = None, error

RECEIVED = ("test_gate_base", "judge", "rejudge", "replan", "replan_review", "fix", "test_gate_final", "eyes", "merge_seal",
            "merge_apply")
ROUNDS = ("plan", "plan_review")
GATES = ("gate_start", "gate_before_fix", "gate_replan", "gate_final")
STOPS = ("start", "answer-start", "ask-before-fix", "answer-before-fix", "after-fix", "judged", "ask-replan", "answer-replan", "fixed",
         "spec-check", "redepth", "ask-final", "answer-final")
LISTS = ("deferred", "widened", "final_reasons", "spec_changed", "optional")
VALUES = ("prior_failures", "redepth", "spec_unchecked")
LINE_SCRIPT = "works:line-script"


def filled(got: dict | None) -> dict | None:
    return None if got is None or all(value is None for value in got.values()) else got


def collect(received: dict, line: dict) -> dict:
    got = {name: (boundary.value(received.get(name)) or {}).get("got") for name in (*RECEIVED, *ROUNDS, "design_only")}
    design_only = got.pop("design_only")
    fixed = boundary.value(line["fixed"])
    stops = {node: boundary.text((line.get("stops") or {}).get(node)) for node in STOPS}
    return {
        **got,
        "fix": None if got["fix"] is None else fixed if isinstance(fixed, dict) else got["fix"],
        "plan": filled(got["plan"]),
        "plan_review": filled(got["plan_review"]) or filled(design_only),
        "start": boundary.value(line["start"]),
        **{name: boundary.value(line["gates"][name]) for name in GATES},
        "stops": {node: word for node, word in stops.items() if word},
        **{name: boundary.items(line.get(name)) for name in LISTS},
        **{name: boundary.value(line.get(name)) for name in VALUES},
    }


def received_of_env() -> dict:
    return {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*RECEIVED, *ROUNDS, "design_only")}


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
    return {**{name: None for name in (*RECEIVED, *ROUNDS)}, "start": None, **{name: None for name in GATES},
            "stops": {"collect": LINE_SCRIPT}, **{name: [] for name in LISTS}, **{name: None for name in VALUES}}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(lambda: collect(received_of_env(), line_of_env()), fallback)


if __name__ == "__main__":
    main()
