# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node consult-check・ruled-consult-check（修正の輪の中、修正役の後）: 返答の consult の頼み（と受け付けが積んだ頼み・人の関所の
条件）を先の確かめに当てて place の相談の状態に積み、聞く頼みが在れば答えの役の指示を md から組んで go: true
（board.consult_ask・src/prompts.consult_render）。入力 pass は first か ruled、reply_<型> は型の書き手の返答（起きた 1 つだけを読む）。相談の枠を使い切った後の頼みは consulted: false。
返り {consulted, go, prompt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import planmarks  # noqa: E402

from src import board, prompts, rules, writers  # noqa: E402


def main() -> dict:
    pass_ = os.environ["INPUTS_PASS"]
    node = rules.answer_node(pass_)
    reply = writers.reply_of(os.environ, pass_, lambda v: ports.polyfill("skip_value").value(v) is None)   # 起きた型の書き手の返答
    if reply is None:
        raise ValueError("どの型の書き手の返答も無い")
    place = ports.place()
    try:
        items = board.place_items(place) or []
    except (planmarks.FieldsBroken, ValueError):   # 控えの壊れは受け付けが止める。頼みは全部断る側
        items = []
    plan = next((str(place / n) for n in (board.PLAN_REPLY_FILE, board.marks_path(place).name)
                 if (place / n).is_file()), "")
    ripple = place / board.RIPPLE_FILE
    got = board.consult_ask(place, reply, pass_, items, node=node,
                            human_items=board.gate_items(board.read_json(place / board.ANSWERS_FILE)),
                            render=prompts.consult_render(place, pass_, plan_file=plan,
                                                          ripple_file=str(ripple) if ripple.is_file() else ""))
    return {"consulted": got["consulted"], "go": got["go"], "prompt": got["prompt"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"consult-check: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
