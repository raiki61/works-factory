# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の後に、承認済みの受け入れ条件のテストが承認の版から変わったかを照らすノード spec-check（docs/design.md の「メイングラフ」の
「順と承認ノード」の 7。fixed の後、最後のテストの前）。

仕様の段（spec=on）が J/spec.json に固めた受け入れ条件のファイルの sha256 と今の作業ツリーを照らす（lib/judge_accept.py の
spec_questions）。TDD の凍結（lib/tddloop.py の frozen_problems）とは別に置く: 基準が人の承認の時で、許しを持たず、結末を人待ちにする。
変わっていれば問いを返し、止めの理由 works:spec-changed（人待ち）を返す。差分の審査・最後のテスト・独立の目は飛ばさない——最後の
承認ノードが問いを載せて必ず開き、その答えは問いに答えない（承認し直すのは次の run の仕様の段）。仕様の段を挟まない run（spec_on が
偽で spec が null）は問いも止めも無い。spec_on が真なのに spec が null なら、照らせないので問いを 1 行と works:spec-changed を返す。
例外は「照らしが落ちた」の問いを 1 行と止めの理由 works:line-script を返す（黙って 0 件にしない——0 件は最後の承認ノードに
「変わっていない」と読まれ、問わずに通る）。unchecked は照らせなかった時（spec を読めない・指しが無い・落ちた）だけ真で、
最後の承認ノードと報告は「変わった」でなく「照らせなかった」と言う。

入力（with:）: spec（judge の返りの J/spec.json の指し札。仕様の段が固めていなければ null）・spec_on（start の出力 spec。
仕様の段を挟んだ run か）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import judge_accept
    import stopby


NO_POINTER = ("仕様の段（spec=on）を挟んだ run なのに、判定が承認済みの仕様 J/spec.json の指しを返さなかった——"
              "受け入れ条件のテストが変わったかを照らせない")


def check(spec_raw, spec_on: bool) -> dict:
    path = boundary.pointed(spec_raw)
    if path is None:
        if spec_on:
            return {"questions": [NO_POINTER], "stop_reason": stopby.SPEC_CHANGED, "unchecked": True}
        return {"questions": [], "stop_reason": "", "unchecked": False}
    got = judge_accept.spec_questions(path, Path.cwd())
    return {**got, "stop_reason": stopby.SPEC_CHANGED if got["questions"] else ""}


def fallback(reason: str) -> dict:
    question = f"照らしが落ちた——承認済みの受け入れ条件のテストが変わったかを確かめられない（{reason}）"
    return {"questions": [question], "stop_reason": boundary.LINE_SCRIPT, "unchecked": True}


if __name__ == "__main__":
    boundary.run(lambda: check(os.environ.get("INPUTS_SPEC"), boundary.flag(os.environ.get("INPUTS_SPEC_ON"))), fallback)
