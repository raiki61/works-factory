# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""人の関所の答えを受ける返しの節（answer-start・answer-final と、before_fix_answer を通して answer-before-fix、replan_answer を通して
answer-replan。埋め P2）。

関所が方針で飛ばされても走る（trigger_rule: none_failed_min_one_success）。関所の出力は `{from, if_skipped: null}` で受ける。
返り {go, answer, stop_reason}（lib/answer.py の taken）: 関所が飛ばされたら前のノードが決めた go と止めの理由をそのまま返し、answer は
null。関所が開いたら答え {decision, text, asked} を返し、通す語なら go、通す語でない語（stop・reject・知らない語）なら go: false と
止めの理由 human:<関所>。止める答えの一言が空なら既定の文（answer.STOP_NOTE・最後の関所は with: の final で見分けて FINAL_STOP_NOTE）を一言にする。
asked は関所が人に見せた項目の行（before_fix_answer だけが ask-before-fix の asked を渡す）で、項目を持たない関所は []。
答えは run の置き場の gates/<関所>.json に書く（同じ関所の答えは書き直す。人が読む控えで、関所の文が名指す）。
報告へは返りの answer が collect を通って届く。

入力（with:）: gate（関所の出力）・go・stop_reason（関所の前の節の決め）・place（関所の節の id）・final（最後の関所か。真の字 "true" の時だけ
最後の関所。書かなければ最後でない）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import answer


def take(gate_raw, go_raw, stop_raw, place: str, artifacts: Path, final: bool = False) -> dict:
    return answer.taken(boundary.value(gate_raw), go=boundary.flag(go_raw), stop_reason=boundary.text(stop_raw), place=place,
                        folder=artifacts, final=final)


def from_env() -> dict:
    """take の引数のうち with: の欄（全部を読む）"""
    return {"gate_raw": os.environ.get("INPUTS_GATE"), "go_raw": os.environ.get("INPUTS_GO"),
            "stop_raw": os.environ.get("INPUTS_STOP_REASON"), "place": os.environ.get("INPUTS_PLACE"),
            "final": boundary.flag(os.environ.get("INPUTS_FINAL"))}


def fallback(reason: str) -> dict:
    return {"go": False, "answer": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: take(**from_env(), artifacts=Path(os.environ["ARTIFACTS_DIR"])), fallback)
