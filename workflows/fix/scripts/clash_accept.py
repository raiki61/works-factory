# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node clash-accept・clash-ruled-accept（全体の形の合わせの輪の終わり）: 合わせ役の返答を照らす（clash.problems。印が残る・組の
変えたファイルの外・許しの無いテストのファイル・申告の無い書き込み・名指しのテストと当たる試験の走らせ直しの赤）。通れば組を戻せた
組にし（clash.settle_repaired）、cannot か 3 回目の拒否で当てる前の木へ戻して申し出へ回す（clash.settle_parked）。上限の周（入力
limit。max_iterations と同じ）で残りの組を申し出へ回して抜ける。今のまま。返り {ok, done, reason, reason_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import rolekit  # noqa: E402
import writelog  # noqa: E402

from src import board, clash, runvals  # noqa: E402

SKIP = (ports.RUNTIME_COPY_PREFIX,)
ACCEPT = {clash.FIRST: "clash-accept", clash.RULED: "clash-ruled-accept"}   # 拒否の控えの名の頭（組ごとに -<group_id>）
NOT_LAUNCHED = "合わせ役を起こさなかった（扱う組が無い）"
REJECTED = "合わせ役の返答の照らしに通らない:\n"


def main(pass_: str, limit: int) -> dict:
    raw = os.environ.get("INPUTS_REPLY", "")
    turn = int(os.environ["INPUTS_ITERATION"])
    if ports.polyfill("skip_value").value(raw) is None:
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo, log = ports.place(), Path.cwd(), writelog.log_here()
    staged = [r["group_id"] for r in clash.load(place) if r["state"] == clash.STAGED and r.get("pass") == pass_]
    if not staged:
        raise ValueError("当て直し中の組が無い（支度が go: true を返したのに控えが当て直し中でない）")
    gid, name = staged[0], f"{ACCEPT[pass_]}-{staged[0]}"
    ports.drop_runner_env(runvals.read(place)["user_env_dir"])   # 確かめ直しのテストに Archon の変数を継がせない（置き場のパスは上で取った）
    if reply.get("handled") == clash.CANNOT:
        out = {"ok": False, "done": True, "reason": clash.SAID_CANNOT.format(how=oneline.one_line(reply.get("how") or "")),
               "reason_file": ""}
        gave_up = out["reason"]
    else:
        start = runvals.read(place)
        cases = (board.read_json(place / board.BASELINE_FILE, {}) or {}).get("cases") or []
        k, out = board.round_number(place, name)   # 控えが読めなければ out が done 真の拒否（照らさずに抜ける）
        if out is None:
            bad = clash.problems(place, repo, gid, reply, start=start, cases=cases, skip=SKIP, name=ACCEPT[pass_], k=k)
            out = board.accept_out(place, name, {"ok": not bad, "reason": REJECTED + "\n".join(f"  - {x}" for x in bad)})
        gave_up = clash.GAVE_UP.format(n=rolekit.GIVE_UP_AFTER, file=out["reason_file"]) if not out["ok"] and out["done"] else ""
        if out["ok"]:
            clash.settle_repaired(place, repo, gid, log=log)
            board.trace(place, "clash_repaired", group=gid, stage=pass_, turn=turn)
    if gave_up:
        ids = clash.settle_parked(place, repo, gid, pass_=pass_, why=gave_up, skip=SKIP)
        board.trace(place, "clash_parked", group=gid, stage=pass_, requests=ids, why=gave_up)
    if turn >= limit:
        for left in clash.todo(place, pass_):
            why = clash.LIMIT.format(limit=limit)
            ids = clash.settle_parked(place, repo, left, pass_=pass_, why=why, skip=SKIP)
            board.trace(place, "clash_parked", group=left, stage=pass_, requests=ids, why=why)
    return {**out, "done": not clash.todo(place, pass_)}


if __name__ == "__main__":
    pass_ = os.environ.get("INPUTS_PASS", "")
    try:
        if pass_ not in clash.PASSES:
            raise ValueError(f"入力 pass は {clash.PASSES} のどれか: {pass_!r}")
        result = main(pass_, int(os.environ["INPUTS_LIMIT"]))
    except Exception as e:
        print(f"clash-accept: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
