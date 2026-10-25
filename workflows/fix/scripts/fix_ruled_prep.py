# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-ruled-prep（全体の形の裁定の後の修正の輪の頭）: 裁定の後の修正役の指示を md から組む（src/prompts.fixer の ruled）。
直す裁定（PRIOR でも join-clash でもない fix_test_scope・fix_code_as）が無ければ go: false。1 周目は裁定の文のファイルを名指し
（無ければ rulings.write で書く）、毎周、保存した 1 回目の返答（board.group_fix_reply）を名指す。直す義務は board.ruled_owed。
段の頭で 1 度、裁定の後の直しの注文（orders.write_ruled。since は段の頭の木）を書く。
返り {prompt, go, iteration}"""
import functools
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import conflict  # noqa: E402
import groups  # noqa: E402
import oneline  # noqa: E402
import writelog  # noqa: E402

from src import board, facts, files, orders, prompts, rules  # noqa: E402

NODE = "fix-ruled-prep"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    n = rules.iteration_next(place / prompts.LEDGER["ruled"])
    if not [r for r in conflict.ruled_fix(place)   # 1 回目の段の裁定（2 回目の段が写した行）は直し直さない。組どうしの合わせの申し出は合わせ役が直す
            if not r.get(conflict.PRIOR) and r.get("source") != conflict.JOIN_SOURCE]:
        return {"prompt": "", "go": False, "iteration": n}
    head = place / rules.head_file("ruled")
    if not head.is_file():
        board.record_skipped(place, repo, SKIP)   # 印より先に（落ちて回し直した prep が控えを飛ばさない）
        board.write_json(head, {"tree": groups.end_tree(repo)})
    owed = board.ruled_owed(place)
    if not orders.is_ruled(place):
        orders.write_ruled(place, owed, since=board.fixer_head(place, "ruled"))
    saved = board.group_fix_reply(place)
    values = board.fix_values(place, owed, answer_node=rules.answer_node("ruled"))
    state, _ = board.ruled_states(place)
    try:
        got = prompts.fixer(place, repo, "ruled", values, owed=owed, items=functools.partial(board.place_items, place),
                            sources=board.brief_sources(place), frozen=facts.frozen_tests(place, state, "ruled"),
                            shared=ports.shared_cache(), saved_reply=str(saved) if saved is not None else "")
    except prompts.Broken as e:
        prompts.error(place, "fix-ruled", oneline.one_line(e))
        raise
    board.consult_skip(place, SKIP, writelog.log_here())
    return {"prompt": got["prompt"], "go": True, "iteration": got["iteration"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
