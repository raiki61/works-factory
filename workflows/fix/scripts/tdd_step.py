# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node tdd-step（組の形の tdd-loop の中。役の後）: 役の返答を機械が確かめて段を進める（src/tdd.step。今のまま）。止めた申し出は
状態の未送の並びから place の conflicts.json に積む（tdd.flush_unsent → rulings.park → conflict.park_claims）。入力 reply は同じ単位の続きの役 tdd の
返答、reply_new は新しい単位の役 tdd-new の返答（周ごとにどちらか一方だけ）。拒んだ理由は place の tdd-step-reject-<n>.md にも書く。
返り {ok, done, reason, reason_file, phase}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import writelog  # noqa: E402

from src import board, runvals, tdd  # noqa: E402
from src import rulings  # noqa: E402

REJECT = "tdd-step-reject-{}.md"


def read_reply():
    value = ports.polyfill("skip_value").value   # null・空・飛ばされた返答は None、JSON でなければ字のまま（step が拒む）
    reply = value(os.environ.get("INPUTS_REPLY"))
    if reply is None:
        reply = value(os.environ.get("INPUTS_REPLY_NEW"))   # 単位が替わった周は新しい単位の役の返答
    return reply


def main() -> dict:
    reply = read_reply()
    place, repo = ports.place(), Path.cwd()
    started = board.read_json(place / board.TDD_START_FILE)
    if not isinstance(started, dict):
        raise ValueError(f"置き場に {board.TDD_START_FILE} が無い（group-start が走らなかった。{place}）")
    if not started.get("go"):
        return {"ok": True, "done": True, "reason": "", "reason_file": "", "phase": "done"}
    state = started["state_file"]
    hits = board.judge_query(place)
    log = writelog.log_here()
    ports.drop_runner_env(runvals.read(place)["user_env_dir"])   # 対象のテストに Archon の変数を継がせない（place・repo は先に取った）
    out = tdd.step(state, reply, repo, try_query=hits, log=log)
    tdd.flush_unsent(state, lambda rows: rulings.park(place, rows))
    reason_file = ""
    if out["reason"]:
        n = len(tdd.load_state(state).get("calls") or [])
        reason_file = str(board.write_text(place / REJECT.format(n), out["reason"] + "\n"))
    return {"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": out["reason"], "reason_file": reason_file,
            "phase": out["phase"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"tdd-step: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
