# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の最後の差分のノード final-diff。

採る周（lib/chain.pick: 最後の周から戻って、結末の種が halted でなく周の commit の head が在る最初の周）を決め、元の基
（chain-start の origin）から採る周の head までの差分を親の置き場の chain/final.diff に lib/seal.py で封じて書く。止まった周は採らず、
その周の差分（前の周の head からその周の head まで）を chain/round-<周>.diff に残して名指す。周ごとの表と合計を親の置き場の
chain.md（lib/chain.render）に書く。
返す apply・sealed は、メイングラフの出力と同じ形（bin/apply が読む {ok, hash, diff}）。最後の差分は元の基からなので、前の周の変更も
入る。apply.ok は最後の差分に入る（自分の差分のファイルが在る）どの周の子の run も自分の差分を置いた時だけ真で、どれかが置かなかった時は
sealed だけを当てられる（bin/apply の --allow-stopped）。採る周の結末の語 outcome と、r2_status（最後の差分に入る周のどれかで R2 が
作り直しと言えばそれ、ほかは採る周の物）も返す（bin/apply が拒む訳と、R2 の作り直しを拒むのに読む）。
書くのは親の置き場だけで、作業ツリーと枝は動かさない（git は commit の間の差分を読むだけ）。始めに前の chain/final.diff を消し、
封じた時だけ書く（resume で走り直して採る周が無くなっても古い物が残らない）。
出力ノード result が結ぶので落ちない: どの誤りも ok: false と訳を返す。1 つの周の差分を作れない時は、残りの周だけで最後の差分を
作らず、chain.md も書かずに、その周（d<k>）と子の run の id を訳で名指す（result がその訳を stop_reason にする）。境の口か lib を読めない時も、標準ライブラリだけで返す。

入力（with:）: start（chain-start の出力）・d1〜d<周の数の上限>（round-k-decide の出力。番号の順に読む。どれも `{from, if_skipped: null}`）
"""
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 出力ノード result が結ぶので落ちない（上の docstring）
    boundary, unread = None, error

if boundary is not None:
    with boundary.guarded_imports():
        import chain
        import green_cert
        import seal

DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>。周の数はグラフの with: が持つ。result.py も同じ読み（試験が縛る）


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def decisions() -> list:
    names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
    return [d for d in (boundary.value(os.environ[name]) for name in names) if isinstance(d, dict)]


def sealed_at(rel: str, data: bytes) -> dict:
    ptr = boundary.pointer(rel)
    return {"ok": True, "hash": seal.write_readback(boundary.resolve(ptr), data), "diff": ptr}


class RoundFailed(Exception):
    """1 つの周の差分を作れない。訳はその周の番号（d<k>）と子の run の id を名指す"""


def with_diffs(repo: Path, origin: str, rows: list) -> list:
    """周の行に、その周の差分のファイルの数 files と、止まった周の残した差分のパス diff を足す。作れない周が在れば RoundFailed"""
    out, prev = [], origin
    for r in rows:
        r = dict(r)
        if r.get("head") and prev:
            try:
                data = green_cert.diff_between(repo, prev, r["head"], skip=boundary.SKIP)
                r["files"] = len(seal.diff_files(repo, data)) if data else 0
                if r.get("kind") == chain.KIND_HALTED and data:
                    r["diff"] = str(boundary.resolve(sealed_at(f"chain/round-{r['n']}.diff", data)["diff"]))
            except Exception as error:   # 出力ノード result が結ぶので落ちない（上の docstring）
                raise RoundFailed(f"周 {r.get('n')}（d{r.get('n')}・子の run {r.get('run') or '読めない'}）の差分を作れない: "
                                  + " ".join(f"{type(error).__name__}: {error}".split())) from error
            prev = r["head"]
        out.append(r)
    return out


def carried(rows: list, kept: dict) -> list:
    """最後の差分に入る周: 採る周までの、自分の差分のファイルが在る周（数えられなかった周も入れる）"""
    return [r for r in rows if r["n"] <= kept["n"] and r.get("files") != 0]


def placed(rows: list, kept: dict) -> dict:
    """apply の ok と訳。最後の差分に入るどの周の子の run も自分の差分を置いた時だけ真"""
    unplaced = [r for r in carried(rows, kept) if r.get("placed") is not True]
    if not unplaced:
        return {"ok": True, "reason": ""}
    return {"ok": False, "reason": "最後の差分に入る周の子の run が差分を置かなかった: "
            + "・".join(f"周 {r['n']}（結末 {r.get('outcome') or '読めない'}）" for r in unplaced)}


def r2_of(rows: list, kept: dict):
    """最後の差分に入る周のどれかで R2 が作り直しと言えばそれ、ほかは採る周の r2_status"""
    if any(r.get("r2_status") == seal.REDESIGN for r in carried(rows, kept)):
        return seal.REDESIGN
    return kept.get("r2_status")


def final() -> dict:
    boundary.resolve(boundary.pointer(chain.FINAL)).unlink(missing_ok=True)
    start = as_dict(boundary.value(os.environ.get("INPUTS_START")))
    if start.get("ok") is not True:
        return nothing(start.get("reason") or "chain-start が鎖を受けなかった")
    made = decisions()
    last = made[-1] if made else start
    origin, repo = start.get("origin") or "", Path.cwd()
    try:
        rows = with_diffs(repo, origin, max((d.get("rows") or [] for d in made), key=len, default=[]))
    except RoundFailed as failed:
        return nothing(str(failed))
    kept, skipped = chain.pick(rows)
    got = {**nothing(""), "skipped": [r["n"] for r in skipped]}
    if kept is None:
        got["reason"] = "採れる周が無い（どの周も止まったか、周の commit が無い）"
    elif not origin:
        got["reason"] = "元の基が無い（鎖を起こした時の作業ツリーに commit が無い）"
    else:
        data = green_cert.diff_between(repo, origin, kept["head"], skip=boundary.SKIP)
        got.update(kept=kept["n"], outcome=kept.get("outcome") or "")
        if not data:
            got["reason"] = f"差分が空（元の基から周 {kept['n']} の結果まで変わった物が無い）"
        else:
            got["sealed"] = sealed_at(chain.FINAL, data)
            got["apply"] = {**got["sealed"], **placed(rows, kept)}
            got["r2_status"] = r2_of(rows, kept)
            got["ok"] = True
    run = os.environ["WORKFLOW_ID"]
    report = boundary.pointer(chain.REPORT)
    final_path = str(boundary.resolve(got["sealed"]["diff"])) if got["sealed"] else ""
    text = chain.render({"run": run, "rounds_max": start.get("rounds"), "rounds": rows, "original_base": origin,
                         "stop": None if last.get("act") == "launch" else {"word": last.get("word"), "text": last.get("text")},
                         "final": final_path, "apply": f"bin/apply {run}", "worktree": str(repo)})
    boundary.resolve(report).write_text(text, encoding="utf-8")
    return {**got, "report": report}


def nothing(reason: str) -> dict:
    return {"ok": False, "reason": reason, "apply": None, "sealed": None, "report": None, "kept": 0, "skipped": [], "outcome": "",
            "r2_status": None}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(nothing(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(final, nothing)


if __name__ == "__main__":
    main()
