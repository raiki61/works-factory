# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の返す節。seal は今の差分を封じて守りのパスの当たりを返し、apply は封じた hash を今の差分と照らして置く。

差分は作業ツリー（節の cwd）と始めの記録の base_rev の間で green_cert.diff_bytes が組み、守りのパスの当たりもその差分から数える
（守りの一覧は自分の一覧と、対象のリポジトリの base_rev の宣言を合わせた物）。seal の返りの当たりは先頭の数行と残りの 1 行に切り
（protect.shown）、全件の数を protected_count に、全件を置き場の PROTECTED_FILE に置く。
Archon が作業ツリーに置く工程の写し（.archon/ の下）は修正の差分でないので載せない。
書く（消す）のは run の置き場だけ。apply は始めに前の merge/apply.diff を消し、置くと決めた時だけ書く（やり直しの apply が拒んでも古い物が残らない）。
落ちない: どの誤りも終了の値 0 で ok: false と理由を返す（線は落ちた返す節の先へ進めない）。
"""
import json
import os

PROTECTED_FILE = "merge/protected.json"


def broken(mode: str, reason: str) -> dict:
    return {"mode": mode, "ok": False, "hash": "", "diff": None, "protected_hits": None, "protected_count": None, "reason": reason}


def mode_of(raw: str) -> str:
    return "apply" if raw == "apply" else "seal"


def object_or_none(got, name: str):
    if got is not None and not isinstance(got, dict):
        raise ValueError(f"{name} は object か null: {json.dumps(got, ensure_ascii=False)}")
    return got


def main() -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import green_cert
    import protect
    import seal

    mode = os.environ["INPUTS_MODE"]
    if mode not in ("seal", "apply"):
        raise ValueError(f"mode は seal か apply: {mode!r}")
    if mode == "apply":
        boundary.resolve(boundary.pointer("merge/apply.diff")).unlink(missing_ok=True)
    base_rev = json.loads(boundary.needed(os.environ["INPUTS_START"], "start").read_text(encoding="utf-8")).get("base_rev")
    if not isinstance(base_rev, str) or not base_rev:
        raise ValueError(f"始めの記録に base_rev が無い: {base_rev!r}")
    fingerprint = boundary.parsed(os.environ["INPUTS_FINGERPRINT"])
    repo = Path.cwd()

    data = green_cert.diff_bytes(repo, base_rev, skip=(boundary.RUNTIME_COPY_PREFIX,))
    if not data:
        boundary.returns(broken(mode, f"差分が空（{base_rev} から今の作業ツリーまで変わった物が無い）"))
        return

    try:
        stats = seal.diff_files(repo, data)
        protected = protect.lines([{**r, "added": stats[r["path"]][0], "deleted": stats[r["path"]][1]}
                                   for r in protect.hits(stats, protect.merged(repo, base_rev))])
        counted = len(protected)
    except (protect.Broken, ValueError) as e:
        protected, counted = [seal.unknown_row(str(e))], 0

    def place(rel: str) -> tuple:
        ptr = boundary.pointer(rel)
        return ptr, seal.write_readback(boundary.resolve(ptr), data)

    if mode == "seal":
        reason = seal.seal_refusal(fingerprint=fingerprint, fingerprint_ok=green_cert.matches(fingerprint, repo))
        ptr, digest = place("merge/sealed.diff")
        whole = boundary.resolve(boundary.pointer(PROTECTED_FILE))
        whole.write_text(json.dumps({"protected_hits": protected}, ensure_ascii=False), encoding="utf-8")
        boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr,
                          "protected_hits": protect.shown(protected, "protected_hits", whole), "protected_count": counted,
                          "reason": reason})
        return

    reason = seal.apply_refusal(
        sealed_hash=boundary.text(os.environ["INPUTS_SEALED_HASH"]),
        current_hash=seal.digest(data),
        answer=object_or_none(boundary.parsed(os.environ["INPUTS_ANSWER"]), "answer"),
        green_ok=boundary.parsed(os.environ["INPUTS_GREEN_OK"]),
        eyes_ok=boundary.parsed(os.environ["INPUTS_EYES_OK"]),
        r2=object_or_none(boundary.parsed(os.environ["INPUTS_R2"]), "r2"),
        fingerprint_ok=green_cert.matches(fingerprint, repo),
        protected=protected,
    )
    ptr, digest = place("merge/refused.diff" if reason else "merge/apply.diff")
    boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": None, "protected_count": None,
                      "reason": reason})


try:
    main()
except Exception as e:
    print(json.dumps(broken(mode_of(os.environ.get("INPUTS_MODE", "")), f"{type(e).__name__}: {e}"), ensure_ascii=False,
                     allow_nan=False), flush=True)
