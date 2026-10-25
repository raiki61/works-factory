# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-prep（組の形の修正の輪の頭）: 修正役の指示を md から組む（src/prompts.fixer。今の fixrules.prep の順）。
直す義務は組の単位のうち判定の直す義務の物（board.group_owed）。義務が残らなければ go: false。段の頭の木（TDD の輪の後の姿）と
除くパスの頭の下の姿を 1 回目に控える（fix-head.json・skip-before.json）。範囲の相談の答えがまだ渡っていない周・はみ出しを相談に
積んだ周は続きの段落だけを組む（回は数え直さない）。TDD の輪が緑にした単位の外の単位には、項目ごとの下請けのファイルを置く。
tdd の輪が諦めた単位は、先に variant の注文に書き直す（orders.regive）。
返り {prompt, go, iteration}。回す側の誤り（判定の写しが無い・brief の控えが壊れた・指示が組めない）は prompt-error.json に書いて非 0"""
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

from src import board, facts, files, intake, orders, prompts, rules, tdd  # noqa: E402

NODE = "fix-prep"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    orders.regive(place)   # tdd の輪が諦めた単位を variant の注文に書き直す（何度呼んでも同じ）
    group = intake.load(place).get("group")
    owed = board.group_owed(place, group["unit_ids"] if group else None)
    head = place / rules.head_file("first")
    if not head.is_file():
        board.record_skipped(place, repo, SKIP)   # 印より先に（落ちて回し直した prep が控えを飛ばさない）
        board.write_json(head, {"tree": groups.end_tree(repo)})
    n = rules.iteration_next(place / prompts.LEDGER["first"])
    duty, _ = board.fix_duty(place, owed)
    if not duty:
        return {"prompt": "", "go": False, "iteration": n}
    state, summary = board.loop_files(place)
    values = board.fix_values(place, owed, state=state, summary=summary, answer_node=rules.answer_node("first"))
    try:
        got = prompts.fixer(place, repo, "first", values, owed=owed, items=functools.partial(board.place_items, place),
                            sources=board.brief_sources(place), green=tdd.green_units(summary),
                            frozen=facts.frozen_tests(place, state, "first"), shared=ports.shared_cache())
    except prompts.Broken as e:
        prompts.error(place, "fixer", oneline.one_line(e))
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
