# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-accept（組の形の修正の輪の終わり）: 修正役の返答を受け付ける（src/board.accept_reply。今のまま）。
- 範囲の相談の周（入力 consulted が true）は受け付けを回さず done: false
- 修正役を起こさなかった（入力 reply が null）周は、義務の単位を not_done で fix-units.json に書いて done: true
- 拒否は rolekit の控え rejects-fix-accept.json に積み（board.accept_out）、最後の回まで done: false。最後の回の拒否は、名指しの
  単位だけを段の頭の木に戻して諦め、ほかの単位を受けて done: true
- 1 回目で裁かれていない申し出が在れば輪を抜ける（done: true。裁定の後の修正役が受け付け直す）
返り {ok, done, reason, reason_file}。回す側の誤り（返答が読めない・判定の写しが無い）は標準エラーに 1 行で非 0"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import rolekit  # noqa: E402
import writelog  # noqa: E402

from src import board, intake, runvals  # noqa: E402

NAME = "fix-accept"
NOT_LAUNCHED = "修正役を起こさなかった（組の直す義務の単位が残らない）"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    raw = os.environ.get("INPUTS_REPLY", "")
    consulted = os.environ.get("INPUTS_CONSULTED", "").strip().lower() == "true"
    if consulted:
        return {"ok": False, "done": False, "reason": board.CONSULTED, "reason_file": ""}
    place, repo = ports.place(), Path.cwd()
    group = intake.load(place).get("group")
    owed = board.group_owed(place, group["unit_ids"] if group else None)
    if ports.polyfill("skip_value").value(raw) is None:
        _, excused = board.fix_duty(place, owed)
        board.write_json(place / board.FIX_UNITS_FILE, board.unit_outcomes(owed, {}, excused=excused))
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    iteration, stopped = board.round_number(place, NAME)
    if stopped:
        return stopped
    values = runvals.read(place)
    state, _ = board.loop_files(place)
    judgment = board.read_json(place / board.JUDGMENT_FILE) or {}
    head = board.fixer_head(place, "first")
    log = writelog.log_here()
    ports.drop_runner_env(values["user_env_dir"])   # 対象のテストを走らせる前に Archon の変数を落とす（place は先に取った）
    got = board.accept_reply(reply, place, repo, pass_="first", iteration=iteration, owed=owed,
                             judged=judgment.get("units"), suite=str(values["tdd_suite"] or ""), state=state,
                             head=head, skip=SKIP, log=log)
    return finish(place, got, iteration)


def finish(place: Path, got: dict, iteration: int) -> dict:
    board.write_json(place / board.FIX_UNITS_FILE, got["units"])
    if got["ok"]:
        path = place / board.FIX_REPLY_FILE
        board.write_json(path, board.reply_marks(got["reply"], board.read_json(path)))
        board.trace(place, "fix_accepted", node=NAME, iteration=iteration, parked=sorted(got["parked"]),
                    conflicted=got["conflicted"])
        return {"ok": True, "done": True, "reason": board.PARKED_FOR_RULING if got["conflicted"] else "",
                "reason_file": ""}
    out = board.accept_out(place, NAME, got)
    board.trace(place, "fix_rejected", node=NAME, iteration=iteration, done=out["done"], parked=sorted(got["parked"]))
    return {**out, "reason": got["reason"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
