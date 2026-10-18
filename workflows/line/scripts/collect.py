# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""全部のサブグラフと承認ノードと返しのノードの出力を、report の入力の形に集める返しのノード collect（埋め P2。trigger_rule: all_done）。

欄と report の入力のポートは、線の YAML の report の with: が結ぶ（with: は $collect.output.<欄> だけを読む）。
サブグラフと計画の往復の出力は受け皿のノード（returned.py。<include の id>-out・plan-rounds-out・plan-rounds-review-out）の出力を
`{from: "$<受け皿>.output", if_skipped: null}` で受ける。受けた物の got が、include の id ごとの出力の欄の object になる。
飛ばされた（受けるノードが落ちたか飛ばされた）受け皿は null。計画の往復の出力は plan と plan-review の欄を別の受け皿で受け、欄が全部
null の方（plan-review が飛ばされた周で抜けた往復）は null。直す物が無い周（計画の往復が飛び、独立設計だけを作る design-only が
走った）は、plan-review の欄に design-only の受け皿の出力を置く（L-W07）。
fix は 1 回目と 2 度目の修正を合わせたノード fixed の出力（申し出は段ごとのポインタの配列。report の約束の fix の形）。fixed が
飛ばされた（2 度目の修正の中が落ちた）時は 1 回目の出力。2 度目の修正の段の行（refixed・2 度目の異議をつないだ objection・1 回目の行を
写した 2 度目の申し出）も fixed の出力が運ぶ。
固定材料から始めた run（fix-in の received が在る）は直す前のテスト・判定・計画の往復・修正前の承認が飛ぶので、その受け皿と
承認の答え・載せなかった問いの空の所を、fix-in が運んだ写しの値（received）で埋める（報告の結末の決めは判定と計画の出力が無いと
途中で終わった run と読む）。
判定・再審・計画・案の直し・修正の受け皿の got と fixed の出力がこの版より前に走った返り（judge_accept.require_ports・
planfile.require_ports・fixbeside.require_ports と、fixed の段の並び records の無い出力）なら、欄を空と読んで結末を作らず fallback で止める。

メイングラフのノードの値（docs/design.md の report の出力の「メイングラフの値」）:
- stops: メイングラフの script のノード（STOPS）の止めの語 {ノード: 語}（入口の拒み・無人の承認ノードの止め・script の例外・人の止め。
  空と飛ばされたノードは載せない）
- deferred・widened・final_reasons・spec_changed: 無人の run で承認ノードに載せなかった問い・聞かずに通した範囲を広げるだけの直し・
  最後の承認ノードを開ける理由・承認の後に受け入れ条件のテストが変わった問い（spec-check の questions）（飛ばされたノードは []）
- prior_failures: 依頼の前の失敗のポインタ（start の出力）・redepth: 直した後の深さの上げ直しの出力・spec_unchecked: 受け入れ条件の
  テストを照らせなかったか（spec-check の unchecked）（飛ばされたノードは null）
- notices: run を止めずに進めた起こす前の注意の行の並び（メイングラフの YAML の collect の with: が、どのノードの出力の字かを決める。
  行ごとに割る。飛ばされたノードと空の字は []）
- optional: 受け止める段の宣言（落ちても先へ進めてよい段の、区切りで終わるノードの id の頭かノードの id の並び。runreport._declared）。
  include 丸ごと受け止める段の宣言はメイングラフの collect の with: の optional、ブロックの中の節の宣言は各ブロックが返す節の返りの欄
  optional で、受け皿が運ぶ。ここで include の id の頭を付けて（absorbed）メイングラフの宣言と重ねずに合わせる。report の入力の欄の値には
  宣言を載せない（collect() の最後で外す）
- stages: 段の表 STAGES（下。役の名 → ノードの id と返りの続き。報告の lib はこの表で段の名と途中の切れ目を決め、ノードの id も段の順も持たない）
- user_env_dir: 利用者の HOME・XDG に戻して起こした印の置き場（start の出力の字。飛ばされたら ""）

result が $collect.output を読むので、このノードは落ちない: 境の口を読めない時も、標準ライブラリだけで fallback の出力を書く（字の入力 TEXTS は
そのまま運ぶ。止めの理由は LINE_SCRIPT。境の口の LINE_SCRIPT の写しで、lib/tests/test_stopby.py が突き合わせる）。

入力（with:）: <include の id>（受け皿の出力）・plan・plan_review・design_only（計画の往復と直す物が無い周の受け皿の出力）・start・
fixed・fix_in（fix-in の出力）・gate_<承認ノード>・stop_<ノード>・deferred・widened・final_reasons・spec_changed・prior_failures・redepth・spec_unchecked・optional・notices・
user_env_dir
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    import childsweep
    unread = None
except Exception as error:   # result が読むノードは落ちない（上の docstring）
    boundary, childsweep, unread = None, None, error
if boundary is not None:
    with boundary.guarded_imports():
        import fixbeside
        import judge_accept
        import planfile

RECEIVED = ("test_gate_base", "judge", "rejudge", "replan", "replan_review", "fix", "test_gate_final", "eyes", "merge_seal",
            "merge_apply")
ROUNDS = ("plan", "plan_review")
GATES = ("gate_start", "gate_before_fix", "gate_replan", "gate_final")
STOPS = ("start", "answer-start", "ask-before-fix", "answer-before-fix", "fix-in", "after-fix", "judged", "ask-replan", "answer-replan", "fixed",
         "spec-check", "redepth", "ask-final", "answer-final")
LISTS = ("deferred", "widened", "final_reasons", "spec_changed", "optional")
VALUES = ("prior_failures", "redepth", "spec_unchecked")
TEXT_LINES = ("notices",)   # 字を行ごとの並びに割る入力
TEXTS = ("user_env_dir",)   # 字のまま運ぶ入力（飛ばされたら ""）
LINE_SCRIPT = "works:line-script"
# 受け皿が運んだブロックの返りの宣言（欄 optional）を、記録の step の頭にする対応: collect の欄 → その返りを返す include の id の並び。
# 欄の名と include の id は字が違う物（rejudge は rejudge-run）があり、2 度目の修正 refix-run は受け皿が無く 1 回目の修正 fix と同じブロックの
# 宣言を使う（refix-run は fix の後にしか走らない）
INNER = {"judge": ("judge",), "rejudge": ("rejudge-run",), "plan": ("plan",), "replan": ("replan",), "fix": ("fix", "refix-run")}
# 段の表（メイングラフの段の名と順を持つ 1 か所。report へ値で渡し、lib はこの表で段の名と返りの続きの切れ目を決める）。
# nodes: 報告の入力の役の名 → この線の節の id（名の替わった物だけ。承認の答えの役は承認ノードの id を指す。載っていない役は名がそのまま節の id）。
# links: 返りの続き。前の段 before の欄 flag（None は返りが在るだけ）が真なのに後の段 after の返りが無ければ text の切れ目。
# held: before の返りのこの欄が偽なら切れ目に数えない（線が意図して後の段を飛ばした周）。needs: この役の返りが無い周は数えない
STAGES = {
    "nodes": {"before-tests": "test-gate-base", "final-tests": "test-gate-final", "sealed-diff": "merge-seal",
              "applied-diff": "merge-apply", "replan-review-result": "replan-review", "start-answer": "gate-start",
              "before-fix-answer": "gate-before-fix", "replan-answer": "gate-replan", "final-answer": "gate-final"},
    "links": [
        {"before": "judge", "flag": "ready", "after": "plan", "text": "判定が直す単位を出したのに計画の出力が無い"},
        {"before": "plan", "flag": "ready", "after": "fix", "text": "計画が修正案を出したのに修正の出力が無い"},
        {"before": "fix", "flag": None, "after": "final-tests", "text": "修正の段が走ったのに最後のテストの出力が無い", "held": "go"},
        {"before": "final-tests", "flag": "ok", "after": "sealed-diff", "text": "最後のテストが通ったのに差分を封じた出力が無い",
         "needs": "fix"},
    ],
}


def filled(got: dict | None) -> dict | None:
    return None if got is None or all(value is None for value in got.values()) else got


def carried(fix_in) -> dict:
    """固定材料の run の写しの値（fix-in の received）。ほかの run と飛んだ fix-in は空"""
    got = boundary.value(fix_in)
    received = got.get("received") if isinstance(got, dict) else None
    return received if isinstance(received, dict) else {}


def without_optional(value):
    """report の入力の欄の値（ブロックの返り）から、宣言の欄 optional を外す。宣言は欄 optional で別に運ぶ"""
    return {key: item for key, item in value.items() if key != "optional"} if isinstance(value, dict) else value


def absorbed(got: dict, own: list) -> list:
    """受け止める段の宣言: メイングラフ自身の並び own に、この run で受け皿が運んだ got の各欄の optional（[{node, bare}]）を include の id の
    頭を付けて（INNER。bare の行はループの中の節で、記録の step に素の id で載るので頭を付けない）重ねずに足す。宣言の無い欄
    （受け皿が null・差し替えの返りに optional が無い）は宣言を持たない物と読み、形の違う行は読み飛ばす"""
    heads = list(own)
    for field, includes in INNER.items():
        block = got.get(field)
        for row in boundary.as_items(block.get("optional") if isinstance(block, dict) else None):
            if not isinstance(row, dict) or not isinstance(row.get("node"), str) or not row["node"]:
                continue
            heads += [row["node"]] if row.get("bare") is True else [f"{include}{childsweep.INCLUDE_SEP}{row['node']}" for include in includes]
    return list(dict.fromkeys(heads))


def collect(received: dict, line: dict) -> dict:
    got = {name: (boundary.value(received.get(name)) or {}).get("got") for name in (*RECEIVED, *ROUNDS, "design_only")}
    design_only = got.pop("design_only")
    for name in ("judge", "rejudge"):
        judge_accept.require_ports(got[name])
    for name in ("plan", "replan"):
        planfile.require_ports(got[name])
    fixbeside.require_ports(got["fix"])
    fixed = boundary.value(line["fixed"])
    if isinstance(fixed, dict) and "records" not in fixed:
        raise ValueError(fixbeside.PRIOR_VERSION)
    stops = {node: boundary.text((line.get("stops") or {}).get(node)) for node in STOPS}
    out = {
        **got,
        "stages": STAGES,
        "fix": None if got["fix"] is None else fixed if isinstance(fixed, dict) else got["fix"],
        "plan": filled(got["plan"]),
        "plan_review": filled(got["plan_review"]) or filled(design_only),
        "start": boundary.value(line["start"]),
        **{name: boundary.value(line["gates"][name]) for name in GATES},
        "stops": {node: word for node, word in stops.items() if word},
        **{name: boundary.items(line.get(name)) for name in LISTS},
        **{name: boundary.value(line.get(name)) for name in VALUES},
        **{name: boundary.text(line.get(name)).splitlines() for name in TEXT_LINES},
        **{name: boundary.text(line.get(name)) for name in TEXTS},
    }
    out["optional"] = absorbed(got, out["optional"])   # 宣言を読むのはこの run で受け皿が運んだ got だけ（carried は読まない）
    out = {**out, **{name: value for name, value in carried(line.get("fix_in")).items() if name in out and not out[name]}}
    return {name: without_optional(value) if name in (*RECEIVED, *ROUNDS) else value for name, value in out.items()}


def received_of_env() -> dict:
    return {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*RECEIVED, *ROUNDS, "design_only")}


def stop_key(node: str) -> str:
    return f"stop_{node.replace('-', '_')}"


def line_of_env() -> dict:
    return {
        "start": os.environ.get("INPUTS_START"),
        "fixed": os.environ.get("INPUTS_FIXED"),
        "fix_in": os.environ.get("INPUTS_FIX_IN"),
        "gates": {name: os.environ.get(f"INPUTS_{name.upper()}") for name in GATES},
        "stops": {node: os.environ.get(f"INPUTS_{stop_key(node).upper()}") for node in STOPS},
        **{name: os.environ.get(f"INPUTS_{name.upper()}") for name in (*LISTS, *VALUES, *TEXT_LINES, *TEXTS)},
    }


def fallback(reason: str) -> dict:
    return {**{name: None for name in (*RECEIVED, *ROUNDS)}, "start": None, **{name: None for name in GATES},
            "stops": {"collect": LINE_SCRIPT}, **{name: [] for name in LISTS}, **{name: None for name in VALUES}, **{name: [] for name in TEXT_LINES},
            **{name: os.environ.get(f"INPUTS_{name.upper()}", "") for name in TEXTS}, "stages": STAGES}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(lambda: collect(received_of_env(), line_of_env()), fallback)


if __name__ == "__main__":
    main()
