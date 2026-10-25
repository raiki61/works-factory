# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node group-end（組の形の終わり）: 終わりの木・単位ごとの結末・TDD の輪の結果・申し出・異議・修正役の印・許したテストの変更と、始めの木からの変更が並行 PR に回した hunk に触れたことを（mismatched に）と、元の結末のファイル base.json の場所（欄 base）を
out_dir/<group_id>/result.json（out_dir が空なら place の groups/）に書く（board.group_result。今のまま）。返り {result_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import conflict  # noqa: E402
import groups  # noqa: E402
import oneline  # noqa: E402

from src import basecase, board, finish, intake, common, tdd  # noqa: E402


def tdd_exit(started) -> dict:
    """TDD の輪の出口の欄（tdd.exit_fields）。輪の頭の返りが無い・輪が済んでいなければ ran: false と理由"""
    if not isinstance(started, dict):
        return {"ran": False, "suite": "", "reason": f"置き場に {board.TDD_START_FILE} が無い（group-start が走らなかった）",
                "units": []}
    try:
        return tdd.exit_fields(started)
    except common.Broken as e:
        return {"ran": False, "suite": str(started.get("suite") or ""),
                "reason": f"TDD のループが済まずに抜けた（{oneline.one_line(e)}）", "units": []}


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    doc = intake.load(place)
    group = doc["group"]
    gdir = board.group_dir(place, doc.get("out_dir") or "", group["group_id"])
    began = board.read_json(gdir / board.GROUP_START_FILE) or {}
    reply_path = place / board.FIX_REPLY_FILE
    start = str(began.get("start_tree") or board.start_tree(place))
    result = board.group_result(
        group, start_tree=start, end_tree=groups.end_tree(repo),
        tdd=tdd_exit(board.read_json(place / board.TDD_START_FILE)), tdd_state=board.loop_files(place)[0],
        fix_units=board.read_json(place / board.FIX_UNITS_FILE, {}), reply=board.read_json(reply_path),
        reply_file=str(reply_path) if reply_path.is_file() else "",
        allowed_rows=board.allowed_test_rows(place), conflicts=conflict.this_pass(place),
        worktree=os.path.realpath(repo), mismatched=[*board.mismatched_lines(place), *board.check_excluded(place, repo, start)],
        accept_trace=board.accept_trace_rows(place), closure=finish.closure_rows(place), place=str(place),
        base=str(basecase.path(place)) if basecase.path(place).is_file() else "")
    target = gdir / board.RESULT_FILE
    board.write_json(target, result)
    return {"result_file": str(target)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"group-end: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
