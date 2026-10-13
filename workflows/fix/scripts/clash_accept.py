# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""合わせ役の返答の受け付け（ノード clash-accept・clash-ruled-accept。入力 pass は first か ruled、iteration は支度が数えたループの周、
limit はループの max_iterations）。

支度が go: false で役を起こさなかった（with: reply が null）時は、扱う組が残っていないので done: true。返答が在れば、当て直し中の組を
修正役と同じ軸で照らす（clash.problems: 組が変えたファイルの外を変えていない・許しの無いテストのファイルを変えていない・書き込みが
返答に在る・名指しのテストの中身が子の終わりの木と同じ・確かめ直しが緑。走らせる前に Archon の変数を環境から落とす）。通れば組を
戻せた組にする（clash.settle_repaired）。拒否は理由のファイルを置き、この組の 3 回目の拒否か、役が直せない（handled: cannot）と
答えた時は、当て直す前の木へ戻して申し出へ回す（clash.settle_parked。first は裁定役へ、ruled は人へ）。上限の周（iteration が
limit）では、残りの組を全部直さずに申し出へ回してループを抜ける。done は扱う組が残っていない。
返り {ok, done, reason, reason_file}。回す側の誤り（返答・入力が読めない・当て直し中の組が無い）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import clash  # noqa: E402
import fixboard  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402
import writelog  # noqa: E402

ACCEPT = {clash.FIRST: "clash-accept", clash.RULED: "clash-ruled-accept"}   # 拒否の控えの名の頭（組ごとに -<group_id>）
NOT_LAUNCHED = "合わせ役を起こさなかった（扱う組が無い）"
REJECTED = "合わせ役の返答の照らしに通らない:\n"


def main(pass_: str, limit: int) -> dict:
    raw = os.environ["INPUTS_REPLY"]
    turn = int(os.environ["INPUTS_ITERATION"])
    if boundary.value(raw) is None:
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo, log = boundary.place("fix"), boundary.work_tree(), writelog.log_here()
    staged = [r["group_id"] for r in clash.load(place) if r["state"] == clash.STAGED and r.get("pass") == pass_]
    if not staged:
        raise ValueError("当て直し中の組が無い（支度が go: true を返したのに控えが当て直し中でない）")
    gid, name = staged[0], f"{ACCEPT[pass_]}-{staged[0]}"
    boundary.drop_runner_env()   # 確かめ直しのテストに Archon の変数を継がせない（置き場のパスは上で取った）
    if reply.get("handled") == clash.CANNOT:
        out = {"ok": False, "done": True, "reason": clash.SAID_CANNOT.format(how=oneline.one_line(reply.get("how") or "")),
               "reason_file": ""}
        gave_up = out["reason"]
    else:
        start = startrec.read(place)
        cases = (fixboard.read_json(place / fixboard.BASELINE_FILE, {}) or {}).get("cases") or []
        bad = clash.problems(place, repo, gid, reply, start=start, cases=cases, skip=boundary.SKIP, name=ACCEPT[pass_],
                             k=rolekit.attempt(place, name))
        out = fixboard.accept_out(place, name, {"ok": not bad, "reason": REJECTED + "\n".join(f"  - {x}" for x in bad)})
        gave_up = clash.GAVE_UP.format(n=rolekit.GIVE_UP_AFTER, file=out["reason_file"]) if not out["ok"] and out["done"] else ""
        if out["ok"]:
            clash.settle_repaired(place, repo, gid, log=log)
            fixboard.trace(place, "clash_repaired", group=gid, stage=pass_, turn=turn)
    if gave_up:
        ids = clash.settle_parked(place, repo, gid, pass_=pass_, why=gave_up, skip=boundary.SKIP)
        fixboard.trace(place, "clash_parked", group=gid, stage=pass_, requests=ids, why=gave_up)
    if turn >= limit:
        for left in clash.todo(place, pass_):
            why = clash.LIMIT.format(limit=limit)
            ids = clash.settle_parked(place, repo, left, pass_=pass_, why=why, skip=boundary.SKIP)
            fixboard.trace(place, "clash_parked", group=left, stage=pass_, requests=ids, why=why)
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
    boundary.returns(result)
