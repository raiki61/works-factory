# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-ruled-prep（全体の形の裁定の後の修正の輪の頭）: 外の輪の頭 ruled-writer-pick が選んだ型の書き手に渡す slots を組み
（src/prompts.writer_slots の ruled）、注文とともに pointer で返す（型の block が指示を組む）。fix の node のまま残る variant（D1 の間）の
分だけ指示を md から組む（src/prompts.writer）。型を選んでいなければ go: false（直す裁定が無い段は ruled-writer-pick が型を選ばず、裁定の後の直しの注文も
そこで段の頭で 1 度書く）。型の 1 周目は裁定の文のファイルを名指し（無ければ rulings.write で書く）、毎周、保存した 1 回目の返答
（board.group_fix_reply）を名指す。直す義務は board.ruled_owed のうちその型の注文の単位（src/writers.owed）。
返り {prompt, go, iteration, writer, order, slots}（writer は起こす include の id か variant の node の名。order・slots は variant と go が偽の周は無い。
prompt は variant の周だけ）"""
import functools
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import groups  # noqa: E402
import oneline  # noqa: E402
import writelog  # noqa: E402

from src import board, facts, prompts, rules, writers  # noqa: E402

NODE = "fix-ruled-prep"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    weapon = writers.current(place)
    if not weapon or not writers.ruled_due(place):   # 直す裁定が無い段は書き手を起こさない
        return {"prompt": "", "go": False, "iteration": 1, "writer": ""}
    node = writers.node("ruled", weapon)
    head = place / rules.head_file("ruled")
    if not head.is_file():   # 外の輪の頭が控えていない置き場（注文を書く段を通らない置き場）: 型の段の頭をここで控える
        board.record_skipped(place, repo, SKIP)   # 印より先に（落ちて回し直した支度が控えを飛ばさない）
        board.write_json(head, {"tree": groups.end_tree(repo)})
    owed = writers.owed(place, board.ruled_owed(place))
    saved = board.group_fix_reply(place)
    values = board.fix_values(place, owed, answer_node=rules.answer_node("ruled"))
    state, _ = board.ruled_states(place)
    extra = dict(owed=owed, items=functools.partial(board.place_items, place), sources=board.brief_sources(place),
                 frozen=facts.frozen_tests(place, state, "ruled"), shared=ports.shared_cache(), saved_reply=str(saved) if saved is not None else "")
    try:
        if weapon == "variant":   # D1 の間は fix の node のまま（D2 で型の block になる）
            got = prompts.writer(place, repo, "ruled", weapon, values, **extra)
            handed = {}
        else:
            slots, rnd = prompts.writer_slots(place, repo, "ruled", weapon, values, **extra)
            handed = writers.hand_over(place, "ruled", weapon, slots)   # 形に合わなければ落ちる（落ちた周は控えない）
            if rnd["kinds"] is not None:
                rules.remember(rnd["ledger"], rnd["kinds"], rnd["iteration"])
            got = {"prompt": "", "iteration": rnd["iteration"]}
    except prompts.Broken as e:
        prompts.error(place, node, oneline.one_line(e))
        raise
    board.consult_skip(place, SKIP, writelog.log_here())
    return {"prompt": got["prompt"], "go": True, "iteration": got["iteration"], "writer": node, **handed}

if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
