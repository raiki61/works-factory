# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 consult-check・ruled-consult-check（修正の輪の中、修正役の後）: 返答の consult の頼み（と受け付けが積んだ頼み・人の関所の
条件）を先の確かめ（consult.screen・oos_hits）に当てて置き場の相談の状態に積み、聞く頼みが在れば答えの役（consult-answer・
ruled-consult-answer）の指示書（修正案のファイルと波及の一覧を読む新しい会話）を置き場に書いて go: true（fixboard.consult_ask）。
入力 pass は first（修正役）か ruled（裁定の後の修正役）。相談の枠を使い切った後の頼みは consulted: false（受け付けが拒む）。
返り {consulted, go, prompt_file}。回す側の誤り（返答・pass が読めない）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import factchecks  # noqa: E402
import fixboard  # noqa: E402
import fixrules  # noqa: E402
import oneline  # noqa: E402
import planmarks  # noqa: E402
import rolekit  # noqa: E402


def main() -> dict:
    pass_ = os.environ["INPUTS_PASS"]
    node = fixrules.answer_node(pass_)
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        raise ValueError(why)
    place = boundary.place("fix")
    try:
        items = factchecks.place_items(place)() or []
    except (planmarks.FieldsBroken, ValueError):   # 控えの壊れは受け付けが止める。頼みは全部断る側
        items = []
    plan = next((str(place / n) for n in (fixboard.PLAN_REPLY_FILE, fixboard.marks_path(place).name)
                 if (place / n).is_file()), "")
    ripple = place / fixboard.RIPPLE_FILE
    got = fixboard.consult_ask(place, reply, pass_, items, node=node, plan_file=plan,
                               human_items=fixboard.gate_items(fixboard.read_json(place / fixboard.ANSWERS_FILE)),
                               ripple_file=str(ripple) if ripple.is_file() else "")
    return {"consulted": got["consulted"], "go": got["go"], "prompt_file": got["prompt_file"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"consult-check: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
