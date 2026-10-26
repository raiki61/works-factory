# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node route-step（組の形の route-loop の中。役 route の後）: 振り分けの返答を機械が確かめる（src/route.step。今の tdd-step の振り分けの段と
同じ確かめ・回数の数え）。止めた申し出は状態の未送の並びから place の conflicts.json に積む（loopkit.flush_unsent → rulings.park）。
拒んだ理由は place の route-step-reject-<n>.md にも書く。返り {ok, done, reason, reason_file, phase}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import writelog  # noqa: E402

import loopkit  # noqa: E402  （lib）
from src import board, route, rulings, runvals  # noqa: E402

REJECT = "route-step-reject-{}.md"


def main() -> dict:
    reply = ports.polyfill("skip_value").value(os.environ.get("INPUTS_REPLY"))
    place, repo = ports.place(), Path.cwd()
    state = route.path(place)
    if not state.is_file():
        return {"ok": True, "done": True, "reason": "", "reason_file": "", "phase": route.ROUTED}
    hits = board.judge_query(place)
    log = writelog.log_here()
    ports.drop_runner_env(runvals.read(place)["user_env_dir"])
    out = route.step(state, reply, repo, try_query=hits, log=log)
    loopkit.flush_unsent(state, lambda rows: rulings.park(place, rows))
    reason_file = ""
    if out["reason"]:
        n = len(loopkit.load_state(state).get("calls") or [])
        reason_file = str(board.write_text(place / REJECT.format(n), out["reason"] + "\n"))
    return {"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": out["reason"], "reason_file": reason_file,
            "phase": out["phase"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"route-step: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
