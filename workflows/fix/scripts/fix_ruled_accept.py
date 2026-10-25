# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-ruled-accept（全体の形の裁定の後の修正の輪の終わり）: 裁定の後の修正役の返答を受け付ける（src/board.accept_reply の
ruled。今のまま）。直す義務は board.ruled_owed、頭の木は fix-ruled-head.json、輪の状態は board.ruled_states。
返り {ok, done, reason, reason_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import rolekit  # noqa: E402
import writelog  # noqa: E402

from src import board, runvals  # noqa: E402

NAME = "fix-ruled-accept"
NOT_LAUNCHED = "裁定の後の修正役を起こさなかった（直す裁定が無い）"
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def main() -> dict:
    raw = os.environ.get("INPUTS_REPLY", "")
    consulted = os.environ.get("INPUTS_CONSULTED", "").strip().lower() == "true"
    if consulted:
        return {"ok": False, "done": False, "reason": board.CONSULTED, "reason_file": ""}
    if ports.polyfill("skip_value").value(raw) is None:
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo = ports.place(), Path.cwd()
    iteration, stopped = board.round_number(place, NAME)
    if stopped:
        return stopped
    owed = board.ruled_owed(place)
    values = runvals.read(place)
    judgment = board.read_json(place / board.JUDGMENT_FILE) or {}
    head = board.fixer_head(place, "ruled")
    state, tests_state = board.ruled_states(place)
    log = writelog.log_here()
    ports.drop_runner_env(values["user_env_dir"])   # 対象のテストを走らせる前に Archon の変数を落とす（place は先に取った）
    got = board.accept_reply(reply, place, repo, pass_="ruled", iteration=iteration, owed=owed,
                             judged=judgment.get("units"), suite=str(values["tdd_suite"] or ""), state=state,
                             tests_state=tests_state, head=head, skip=SKIP, log=log)
    board.write_json(place / board.FIX_UNITS_FILE, got["units"])
    if got.get("stop"):   # 実行器が結末を返さない・試験を拾わない（board.no_suite_at_accept）: 出し直させずに輪を抜ける
        board.trace(place, "fix_ruled_stopped", node=NAME, iteration=iteration, reason=got["reason"])
        return {"ok": False, "done": True, "reason": got["reason"], "reason_file": ""}
    if got["ok"]:
        path = place / board.RULED_REPLY_FILE
        board.write_json(path, board.reply_marks(got["reply"], board.read_json(path)))
        board.trace(place, "fix_ruled_accepted", node=NAME, iteration=iteration, parked=sorted(got["parked"]))
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    out = board.accept_out(place, NAME, got)
    board.trace(place, "fix_ruled_rejected", node=NAME, iteration=iteration, done=out["done"], parked=sorted(got["parked"]))
    return {**out, "reason": got["reason"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
