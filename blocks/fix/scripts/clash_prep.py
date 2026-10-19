# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node clash-prep・clash-ruled-prep（全体の形の合わせの輪の頭）: 周を 1 つ数え、合わせの控えの次の組を当て直し（clash.stage。字の
食い違いは印つき）、当たらなければ申し出へ回して次の組へ（clash.settle_parked）。当てた組が在れば合わせ役の指示を md から組む
（prompts/parts/clash.md。src/prompts.clash_values）。入力 pass は first か ruled。扱う組が無ければ go: false。今のまま。
返り {prompt, go, iteration}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import board, clash, prompts  # noqa: E402

ACCEPT = {clash.FIRST: "clash-accept", clash.RULED: "clash-ruled-accept"}   # 受け付けの node（拒否の控えの名の頭）
SKIP = (ports.RUNTIME_COPY_PREFIX,)


def turn(place, pass_: str) -> int:
    """ループの周の数を 1 つ進めて返す（控えはファイル。数えすぎは上限の周の片付けを早めるだけで、ループを上限で落とさない側）"""
    path = place / f"clash-turns-{pass_}.json"
    n = int((board.read_json(path, {}) or {}).get("turns") or 0) + 1
    board.write_json(path, {"turns": n})
    return n


def main(pass_: str) -> dict:
    place, repo = ports.place(), Path.cwd()
    n = turn(place, pass_)
    stuck = board.held(place)
    while (todo := clash.todo(place, pass_)):
        gid = todo[0]
        ok, why = (False, stuck) if stuck else clash.stage(place, repo, gid, pass_, SKIP)
        if not ok:
            ids = clash.settle_parked(place, repo, gid, pass_=pass_, why=why, skip=SKIP)
            board.trace(place, "clash_parked", group=gid, stage=pass_, requests=ids, why=why)
            stuck = board.held(place)
            continue
        board.trace(place, "clash_staged", group=gid, stage=pass_, turn=n)
        brief = clash.brief(place, gid)
        row = next(r for r in clash.load(place) if r["group_id"] == gid)
        out = prompts.clash(place, pass_, f"{ACCEPT[pass_]}-{gid}", str(brief), row["patch"])
        return {"prompt": out["prompt"], "go": True, "iteration": n}
    return {"prompt": "", "go": False, "iteration": n}


if __name__ == "__main__":
    pass_ = os.environ.get("INPUTS_PASS", "")
    try:
        if pass_ not in clash.PASSES:
            raise ValueError(f"入力 pass は {clash.PASSES} のどれか: {pass_!r}")
        out = main(pass_)
    except Exception as e:
        print(f"clash-prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
