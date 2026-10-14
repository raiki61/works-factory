# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の後に、承認済みの受け入れ条件のテストが承認の版から変わったかを照らすノード spec-check（docs/design.md の「メイングラフ」の
「順と承認ノード」の 7。fixed の後、最後のテストの前）。

仕様の段（spec=on）が J/spec.json に固めた受け入れ条件のファイルの sha256 と今の作業ツリーを照らす（lib/judge_accept.py の
spec_questions）。TDD の凍結（lib/tddloop.py の frozen_problems）とは別に置く: 基準が人の承認の時で、許しを持たず、結末を人待ちにする。
変わっていれば問いを返し、止めの理由 works:spec-changed（人待ち）を返す。差分の審査・最後のテスト・独立の目は飛ばさない——最後の
承認ノードが問いを載せて必ず開き、その答えは問いに答えない（承認し直すのは次の run の仕様の段）。仕様の段が無い run（spec が null）は
問いも止めも無い。例外は止めの理由 works:line-script（黙って 0 件にしない）。

入力（with:）: spec（judge の返りの J/spec.json の指し札。仕様の段が固めていなければ null）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import judge_accept
    import stopby


def check(spec_raw) -> dict:
    path = boundary.pointed(spec_raw)
    if path is None:
        return {"questions": [], "stop_reason": ""}
    questions = judge_accept.spec_questions(path, Path.cwd())
    return {"questions": questions, "stop_reason": stopby.SPEC_CHANGED if questions else ""}


def fallback(reason: str) -> dict:
    return {"questions": [], "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: check(os.environ.get("INPUTS_SPEC")), fallback)
