# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""承認ノードの答えを受ける返しの node（answer-start・answer-final。docs/design/line.md の 2 節。埋め P2。今の gate_answer.py のまま）。

承認ノードが方針で飛ばされても走る（trigger_rule: none_failed_min_one_success）。承認ノードの出力は `{from, if_skipped: null}` で受ける。
返り {go, answer, stop_reason}（lib/answer.py の taken）: 承認ノードが飛ばされたら前の node が決めた go と止めの語をそのまま返し、
answer は null。開いたら答え {decision, text, asked} を返し、通す語なら go、通す語でない語（stop・reject・知らない語）なら go: false と
止めの語 human:<承認ノード>。止める答えの一言が空なら既定の文（最後の承認ノードは with: の final で見分けて別の既定の文）。
答えは place（line は run directory の根）の gates/<承認ノード>.json に書く（同じ承認ノードの答えは書き直す）。

入力（with:）: gate（承認ノードの出力）・go・stop_reason（承認ノードの前の node の決め）・place（承認ノードの node の id）・
final（最後の承認ノードか。true の字の時だけ）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def take() -> dict:
    raw = {"gate": os.environ.get("INPUTS_GATE"), "go": os.environ.get("INPUTS_GO"), "stop_reason": os.environ.get("INPUTS_STOP_REASON"),
           "place": os.environ.get("INPUTS_PLACE"), "final": os.environ.get("INPUTS_FINAL")}
    import answer

    gate = ports.polyfill("skip_value").value(raw["gate"])
    return answer.taken(gate, go=ports.flag(raw["go"]), stop_reason=ports.text(raw["stop_reason"]), place=ports.text(raw["place"]),
                        folder=ports.place(), final=ports.flag(raw["final"]))


def fallback(reason: str) -> dict:
    from src import guard

    return {"go": False, "answer": None, "stop_reason": guard.LINE_SCRIPT}


ports.run(take, fallback)
