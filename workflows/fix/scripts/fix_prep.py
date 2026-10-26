# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-prep（組の形の修正の輪の頭）: 外の輪の頭 writer-pick が選んだ型の書き手に渡す slots を組み（src/prompts.writer_slots）、
注文 orders/<型>.json とともに pointer で返す（型の block 6 つが include の入力で受ける。指示は型の block が組む）。直す義務は組の単位のうち判定の直す義務の物（board.group_owed）で、その型の注文の単位（src/writers.owed）。義務が
残らなければ go: false。型の段の頭の木と除くパスの頭の下の姿は writer-pick が控える（無ければここで控える）。組が no-suite で止まっていれば
（board.no_suite_stop）go: false。範囲の相談の答えがまだ渡っていない周・はみ出しを相談に積んだ周は続きの段落だけを組む（回は数え直さない）。
variant の書き手には項目ごとの下請けのファイルを置き、tdd の輪の閉じの書き手には輪の要約を渡す（slots の欄 summary_file）。
返り {go, iteration, writer, order, slots}（writer は起こす include の id。order・slots は go が偽の周は無い）。回す側の誤り（判定の写しが無い・brief の控えが壊れた・slots が組めない）は prompt-error.json に書いて非 0"""
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

from src import board, facts, intake, prompts, rules, tdd, writers  # noqa: E402

NODE = "fix-prep"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    weapon = writers.current(place)
    group = intake.load(place).get("group")
    owed = writers.owed(place, board.group_owed(place, group["unit_ids"] if group else None))
    if not weapon:
        return {"go": False, "iteration": 1, "writer": ""}
    node = writers.node("first", weapon)
    head = place / rules.head_file("first")
    if not head.is_file():   # 外の輪の頭が控えていない置き場（注文を書く段を通らない置き場）: 型の段の頭をここで控える
        board.record_skipped(place, repo, SKIP)   # 印より先に（落ちて回し直した支度が控えを飛ばさない）
        board.write_json(head, {"tree": groups.end_tree(repo)})
    n = rules.iteration_next(writers.ledger(place, "first", weapon))
    duty, _ = board.fix_duty(place, owed)
    if not duty or board.no_suite_stop(place):   # 組が no-suite で止まった（TDD のループが実行器の止まりで抜けた・受け付けが止めた）
        return {"go": False, "iteration": n, "writer": node}
    state, summary = board.loop_files(place)
    summary = summary if weapon == "tdd" else ""   # 輪の要約を読むのは tdd の輪の閉じの書き手だけ
    values = board.fix_values(place, owed, state=state, summary=summary, answer_node=rules.answer_node("first"))
    extra = dict(owed=owed, items=functools.partial(board.place_items, place), sources=board.brief_sources(place), green=tdd.green_units(summary),
                 frozen=facts.frozen_tests(place, state, "first"), shared=ports.shared_cache())
    try:
        slots, rnd = prompts.writer_slots(place, repo, "first", weapon, values, **extra)
        handed = writers.hand_over(place, "first", weapon, slots, owed)   # 形に合わなければ落ちる（落ちた周は控えない）
        if rnd["kinds"] is not None:
            rules.remember(rnd["ledger"], rnd["kinds"], rnd["iteration"])
    except prompts.Broken as e:
        prompts.error(place, node, oneline.one_line(e))
        raise
    board.consult_skip(place, SKIP, writelog.log_here())
    return {"go": True, "iteration": rnd["iteration"], "writer": node, **handed}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
