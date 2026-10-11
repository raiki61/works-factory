# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の返す節。seal は今の差分を封じて守りのパスの当たりを返し、apply は封じた hash を今の差分と照らして置く。

差分は作業ツリー（節の cwd）と始めの記録の base_rev の間で green_cert.diff_bytes が組み、守りのパスの当たりもその差分から数える。
書く（消す）のは run の置き場だけ。apply は始めに前の merge/apply.diff を消し、置くと決めた時だけ書く（やり直しの apply が拒んでも古い物が残らない）。
落ちない: どの誤りも終了の値 0 で ok: false と理由を返す（線は落ちた返す節の先へ進めない）。
"""
import json
import os

NO_VALUE = ("", "null")


def broken(mode: str, reason: str) -> dict:
    return {"mode": mode, "ok": False, "hash": "", "diff": None, "protected_hits": None, "reason": reason}


def mode_of(raw: str) -> str:
    return "apply" if raw == "apply" else "seal"


def value(raw: str):
    return None if raw in NO_VALUE else json.loads(raw)


def object_or_none(raw: str, name: str):
    got = value(raw)
    if got is not None and not isinstance(got, dict):
        raise ValueError(f"{name} は object か null: {raw}")
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
    start = object_or_none(os.environ["INPUTS_START"], "start")
    if start is None:
        raise ValueError("start の指し札が無い")
    base_rev = json.loads(boundary.resolve(start).read_text(encoding="utf-8")).get("base_rev")
    if not isinstance(base_rev, str) or not base_rev:
        raise ValueError(f"始めの記録に base_rev が無い: {base_rev!r}")
    fingerprint = value(os.environ["INPUTS_FINGERPRINT"])
    repo = Path.cwd()

    data = green_cert.diff_bytes(repo, base_rev)
    if not data:
        boundary.returns(broken(mode, f"差分が空（{base_rev} から今の作業ツリーまで変わった物が無い）"))
        return

    try:
        stats = seal.diff_files(repo, data)
        protected = protect.lines([{**r, "added": stats[r["path"]][0], "deleted": stats[r["path"]][1]}
                                   for r in protect.hits(stats)])
    except (protect.Broken, ValueError) as e:
        protected = [seal.unknown_row(str(e))]

    def place(rel: str) -> tuple:
        ptr = boundary.pointer(rel)
        return ptr, seal.write_readback(boundary.resolve(ptr), data)

    if mode == "seal":
        reason = seal.seal_refusal(fingerprint=fingerprint, fingerprint_ok=green_cert.matches(fingerprint, repo))
        ptr, digest = place("merge/sealed.diff")
        boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": protected,
                          "reason": reason})
        return

    sealed_hash = os.environ["INPUTS_SEALED_HASH"]
    reason = seal.apply_refusal(
        sealed_hash="" if sealed_hash in NO_VALUE else sealed_hash,
        current_hash=seal.digest(data),
        answer=object_or_none(os.environ["INPUTS_ANSWER"], "answer"),
        green_ok=value(os.environ["INPUTS_GREEN_OK"]),
        eyes_ok=value(os.environ["INPUTS_EYES_OK"]),
        r2=object_or_none(os.environ["INPUTS_R2"], "r2"),
        fingerprint_ok=green_cert.matches(fingerprint, repo),
        protected=protected,
    )
    ptr, digest = place("merge/refused.diff" if reason else "merge/apply.diff")
    boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": None, "reason": reason})


try:
    main()
except Exception as e:
    print(json.dumps(broken(mode_of(os.environ.get("INPUTS_MODE", "")), f"{type(e).__name__}: {e}"), ensure_ascii=False),
          flush=True)
