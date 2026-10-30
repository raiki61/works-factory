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
sealed だけを当てられる（bin/apply の --allow-stopped）。placed は最後の差分を封じて apply.ok が真で、採らなかった周が run の枝と作業ツリーに
変更を残していない時だけ真（出口の語 pr の渡しが読む。残した時は reason にその周を名指す）。採る周の結末の語 outcome と、r2_status（最後の差分に入る周のどれかで R2 が
作り直しと言えばそれ、ほかは採る周の物）と、spec_questions（最後の差分に入る周の承認し直すかの問いの数の和）も返す（bin/apply が
拒む訳と、R2 の作り直しを拒むのと、承認し直しの知らせに読む）。
書くのは親の置き場だけで、作業ツリーと枝は動かさない（git は commit の間の差分を読むだけ）。final() は始めに前の chain/final.diff と
chain.md を消し、final.diff は封じた時だけ、chain.md は周の差分を作れた時だけ書く（resume で走り直して採る周が無くなったり final() が
途中で返ったりしても、前の回の差分や、それを名指す表が残らない）。
出力ノード result が結ぶので落ちない: どの誤りも ok: false と訳を返す。1 つの周の差分を作れない時は、残りの周だけで最後の差分を
作らず、chain.md も書かずに、その周（d<k>）と子の run の id を訳で名指す（result がその訳を stop_reason にする）。ports か lib を読めない時も、標準ライブラリだけで返す。
この時は final() が走らず、何も消さない（消す名の持ち主の lib/chain が読めない）。前の回の表が残りうるが、result が読めない訳を
stop_reason にし、sealed は null。

入力（with:）: start（chain-start の出力）・d1〜d<周の数の上限>（round-k-decide の出力。番号の順に読む。どれも `{from, if_skipped: null}`）
"""
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
try:
    import ports
    from src import files, reads
    import chain
    import green_cert
    import seal
    unread = None
except Exception as error:   # 出力ノード result が結ぶので落ちない（上の docstring）
    ports, unread = None, error

SKIP = (ports.RUNTIME_COPY_PREFIX,) if ports is not None else ()   # 差分に数えない（Archon が run の作業ツリーに写す置き場）
DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>。周の数はグラフの with: が持つ。result.py も同じ読み（試験が縛る）


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def decisions() -> list:
    names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
    return [d for d in (reads.value(os.environ[name]) for name in names) if isinstance(d, dict)]


def sealed_at(rel: str, data: bytes) -> tuple:
    """親の置き場の rel に差分を封じて書く。(書いたパス, {ok, hash, diff: pointer})"""
    path = ports.place() / rel
    return path, {"ok": True, "hash": seal.write_readback(path, data), "diff": ports.pointer(path, "file")}


def with_diffs(repo: Path, origin: str, rows: list) -> list:
    """周の行に、その周の差分のファイルの数 files と、止まった周の残した差分のパス diff を足す。作れない周が在れば、その周（d<k>）と子の run の id を名指す誤り"""
    out, prev = [], origin
    for r in rows:
        r = dict(r)
        if r.get("head") and prev:
            try:
                data = green_cert.diff_between(repo, prev, r["head"], skip=SKIP)
                r["files"] = len(seal.diff_files(repo, data)) if data else 0
                if r.get("kind") == chain.KIND_HALTED and data:
                    r["diff"] = str(sealed_at(files.round_diff(r["n"]), data)[0])
            except Exception as error:   # 出力ノード result が結ぶので落ちない（上の docstring）
                raise RuntimeError(f"周 {r.get('n')}（d{r.get('n')}・子の run {r.get('run') or '読めない'}）の差分を作れない: "
                                   f"{type(error).__name__}: {error}") from error
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


def left_over(skipped: list, kept: dict) -> str:
    """PR へ渡せない訳: 採らなかった周が採る周の head の後に変更を積んだか、commit できずに作業ツリーに残した（周の commit は結末に
    よらず run の枝に積まれ、出口の語 pr の渡しは元の基から今の作業ツリーまでを最後の差分と照らすので、必ず合わない）。無ければ空"""
    rest = [r for r in skipped if r.get("head") != kept["head"]]
    if not rest:
        return ""
    return ("採らなかった周の変更が run の枝か作業ツリーに残り、PR の差分が最後の差分と合わない: "
            + "・".join(f"周 {r['n']}（結末 {r.get('outcome') or '読めない'}）" for r in rest))


def r2_of(rows: list, kept: dict):
    """最後の差分に入る周のどれかで R2 が作り直しと言えばそれ、ほかは採る周の r2_status"""
    if any(r.get("r2_status") == seal.REDESIGN for r in carried(rows, kept)):
        return seal.REDESIGN
    return kept.get("r2_status")


def spec_of(rows: list, kept: dict) -> int:
    """最後の差分に入る周の承認し直すかの問いの数の和。前の周の変更も最後の差分に入るので、採る周だけでなく足す"""
    return sum(r["spec_questions"] for r in carried(rows, kept) if isinstance(r.get("spec_questions"), int))


def final() -> dict:
    for stale in (files.FINAL, files.REPORT):
        (ports.place() / stale).unlink(missing_ok=True)
    start = as_dict(reads.value(os.environ.get("INPUTS_START")))
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
        data = green_cert.diff_between(repo, origin, kept["head"], skip=SKIP)
        got.update(kept=kept["n"], outcome=kept.get("outcome") or "")
        if not data:
            got["reason"] = f"差分が空（元の基から周 {kept['n']} の結果まで変わった物が無い）"
        else:
            got["sealed"] = sealed_at(files.FINAL, data)[1]
            got["apply"] = {**got["sealed"], **placed(rows, kept)}
            got["r2_status"] = r2_of(rows, kept)
            got["spec_questions"] = spec_of(rows, kept)
            got["ok"] = True
            got["reason"] = left_over(skipped, kept)
            got["placed"] = got["apply"]["ok"] is True and not got["reason"]
    run = os.environ["WORKFLOW_ID"]
    report_path = ports.place() / files.REPORT
    final_path = str(ports.place() / files.FINAL) if got["sealed"] else ""
    text = chain.render({"run": run, "rounds_max": start.get("rounds"), "rounds": rows, "original_base": origin,
                         "stop": None if last.get("act") == "launch" else {"word": last.get("word"), "text": last.get("text")},
                         "final": final_path, "apply": f"bin/apply {run}", "worktree": str(repo)})
    report_path.write_text(text, encoding="utf-8")
    return {**got, "report": ports.pointer(report_path, "file")}


def nothing(reason: str) -> dict:
    return {"ok": False, "reason": reason, "apply": None, "sealed": None, "report": None, "kept": 0, "skipped": [], "outcome": "",
            "r2_status": None, "spec_questions": 0, "placed": False}


def main() -> None:
    if ports is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(nothing(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(final, nothing)


if __name__ == "__main__":
    main()
