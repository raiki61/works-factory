# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の最後の差分のノード final-diff。

採る周（lib/chain.pick: 最後の周から戻って、結末の種が halted でなく周の commit の head が在る最初の周）を決め、元の基
（chain-start の origin）から採る周の head までの差分を親の置き場の chain/final.diff に lib/seal.py で封じて書く。止まった周は採らず、
その周の差分（前の周の head からその周の head まで）を chain/round-<周>.diff に残して名指す。周ごとの表と合計を親の置き場の
chain.md（lib/chain.render）に書く。
返す apply・sealed は、メイングラフの出力と同じ形（bin/apply が読む {ok, hash, diff}）。apply.ok は採る周の子の run が自分の差分を
置いた時だけ真で、置かなかった周を採った時は sealed だけを当てられる（bin/apply の --allow-stopped）。採る周の結末の語 outcome と
r2_status も返す（bin/apply が拒む訳と、R2 の作り直しを拒むのに読む）。
書くのは親の置き場だけで、作業ツリーと枝は動かさない（git は commit の間の差分を読むだけ）。始めに前の chain/final.diff を消し、
封じた時だけ書く（resume で走り直して採る周が無くなっても古い物が残らない）。
出力ノード result が結ぶので落ちない: どの誤りも ok: false と訳を返す。境の口か lib を読めない時も、標準ライブラリだけで返す。

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

DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>。周の数はグラフの with: が持つ


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def decisions() -> list:
    names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
    return [d for d in (boundary.value(os.environ[name]) for name in names) if isinstance(d, dict)]


def sealed_at(rel: str, data: bytes) -> dict:
    ptr = boundary.pointer(rel)
    return {"ok": True, "hash": seal.write_readback(boundary.resolve(ptr), data), "diff": ptr}


def with_diffs(repo: Path, origin: str, rows: list) -> list:
    """周の行に、その周の差分のファイルの数 files と、止まった周の残した差分のパス diff を足す"""
    out, prev = [], origin
    for r in rows:
        r = dict(r)
        if r.get("head") and prev:
            data = green_cert.diff_between(repo, prev, r["head"], skip=boundary.SKIP)
            r["files"] = len(seal.diff_files(repo, data)) if data else 0
            if r.get("kind") == chain.KIND_HALTED and data:
                r["diff"] = str(boundary.resolve(sealed_at(f"chain/round-{r['n']}.diff", data)["diff"]))
            prev = r["head"]
        out.append(r)
    return out


def final() -> dict:
    final_rel = f"chain/{chain.FINAL}"
    boundary.resolve(boundary.pointer(final_rel)).unlink(missing_ok=True)
    start = as_dict(boundary.value(os.environ.get("INPUTS_START")))
    if start.get("ok") is not True:
        return nothing(start.get("reason") or "chain-start が鎖を受けなかった")
    made = decisions()
    last = made[-1] if made else start
    origin, repo = start.get("origin") or "", Path.cwd()
    rows = with_diffs(repo, origin, max((d.get("rows") or [] for d in made), key=len, default=[]))
    kept, skipped = chain.pick(rows)
    got = {**nothing(""), "skipped": [r["n"] for r in skipped]}
    if kept is None:
        got["reason"] = "採れる周が無い（どの周も止まったか、周の commit が無い）"
    elif not origin:
        got["reason"] = "元の基が無い（鎖を起こした時の作業ツリーに commit が無い）"
    else:
        data = green_cert.diff_between(repo, origin, kept["head"], skip=boundary.SKIP)
        got.update(kept=kept["n"], outcome=kept.get("outcome") or "", r2_status=kept.get("r2_status"))
        if not data:
            got["reason"] = f"差分が空（元の基から周 {kept['n']} の結果まで変わった物が無い）"
        else:
            got["sealed"] = sealed_at(final_rel, data)
            placed = kept.get("placed") is True
            got["apply"] = {**got["sealed"], "ok": placed,
                            "reason": "" if placed else f"採った周 {kept['n']} の子の run が差分を置かなかった（結末 {got['outcome']}）"}
            got["ok"] = True
    run = os.environ["WORKFLOW_ID"]
    report = boundary.pointer(chain.REPORT)
    final_path = str(boundary.resolve(got["sealed"]["diff"])) if got["sealed"] else ""
    text = chain.render({"run": run, "rounds_max": start.get("rounds"), "rounds": rows, "original_base": origin,
                         "stop": None if last.get("act") == "launch" else {"word": last.get("word"), "text": last.get("text")},
                         "final": final_path, "apply": f"bin/apply {run}"})
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
