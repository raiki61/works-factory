# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の照らしの節 place。seal は今の差分を封じて守りのパスの当たりを返し、apply は封じた hash を今の差分と照らして置き、
check は封じた hash を今の差分と照らすだけで置く（関所の答え・緑・目は、その差分を作った所で済んだ物）。

差分は作業ツリー（節の cwd）と差分の根の間で green_cert.diff_bytes が組む。差分の根は、seal・apply は始めの記録の base_rev、
check は入力 base_rev。守りのパスの当たりは seal・apply が差分から数える（守りの一覧は自分の一覧と、対象のリポジトリの base_rev の
宣言を合わせた物）。seal の返りの当たりは先頭の数行と残りの 1 行に切り（protect.shown）、全件の数を protected_count に、全件を
置き場の PROTECTED_FILE に置く。
Archon が作業ツリーに置く工程の写し（.archon/ の下）は修正の差分でないので載せない。
書く（消す）のは run の置き場だけ。apply・check は始めに前の merge/apply.diff を消し、置くと決めた時だけ書く（やり直しが拒んでも古い
物が残らない）。返りの base_rev（差分の根）と deliver（確かめた出口の語。lib/entry.py の DELIVERS）は後ろの渡しの節が読む。
落ちない: どの誤りも終了の値 0 で ok: false と理由を返す（後ろの節が読めなくならない）。
"""
import json
import os

PROTECTED_FILE = "merge/protected-all.json"
MODES = ("seal", "apply", "check")


def broken(mode: str, reason: str) -> dict:
    return {"mode": mode, "ok": False, "hash": "", "diff": None, "protected_hits": None, "protected_count": None, "reason": reason,
            "base_rev": "", "deliver": ""}


def mode_of(raw: str) -> str:
    return raw if raw in MODES else "seal"


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
    import entry
    import green_cert
    import protect
    import seal

    mode = os.environ["INPUTS_MODE"]
    if mode not in MODES:
        raise ValueError(f"mode は {' か '.join(MODES)}: {mode!r}")
    if mode != "seal":
        boundary.resolve(boundary.pointer("merge/apply.diff")).unlink(missing_ok=True)
    deliver = entry.deliver_word(boundary.text(os.environ.get("INPUTS_DELIVER")))
    if mode == "check":
        base_rev = boundary.text(os.environ.get("INPUTS_BASE_REV"))
    else:
        base_rev = json.loads(boundary.needed(os.environ["INPUTS_START"], "start").read_text(encoding="utf-8")).get("base_rev")
    if not isinstance(base_rev, str) or not base_rev:
        raise ValueError(f"差分の根 base_rev が無い: {base_rev!r}")
    fingerprint = boundary.parsed(os.environ.get("INPUTS_FINGERPRINT"))
    repo = Path.cwd()

    data = green_cert.diff_bytes(repo, base_rev, skip=(boundary.RUNTIME_COPY_PREFIX,))
    if not data:
        boundary.returns(broken(mode, f"差分が空（{base_rev} から今の作業ツリーまで変わった物が無い）"))
        return

    def place(rel: str) -> tuple:
        ptr = boundary.pointer(rel)
        return ptr, seal.write_readback(boundary.resolve(ptr), data)

    def returned(ptr, digest: str, reason: str, hits=None, count=None) -> dict:
        return {"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": hits, "protected_count": count,
                "reason": reason, "base_rev": base_rev, "deliver": deliver}

    sealed_hash = boundary.text(os.environ.get("INPUTS_SEALED_HASH"))
    if mode == "check":
        reason = seal.hash_refusal(sealed_hash, seal.digest(data))
        boundary.returns(returned(*place("merge/refused.diff" if reason else "merge/apply.diff"), reason))
        return

    try:
        stats = seal.diff_files(repo, data)
        protected = protect.lines([{**r, "added": stats[r["path"]][0], "deleted": stats[r["path"]][1]}
                                   for r in protect.hits(stats, protect.merged(repo, base_rev))])
        counted = len(protected)
    except (protect.Broken, ValueError) as e:
        protected, counted = [seal.unknown_row(str(e))], 0

    if mode == "seal":
        reason = seal.seal_refusal(fingerprint=fingerprint, fingerprint_ok=green_cert.matches(fingerprint, repo))
        ptr, digest = place("merge/sealed.diff")
        whole = boundary.resolve(boundary.pointer(PROTECTED_FILE))
        whole.write_text(json.dumps({"protected_hits": protected}, ensure_ascii=False), encoding="utf-8")
        boundary.returns(returned(ptr, digest, reason, protect.shown(protected, "protected_hits", whole), counted))
        return

    reason = seal.apply_refusal(
        sealed_hash=sealed_hash,
        current_hash=seal.digest(data),
        answer=object_or_none(boundary.parsed(os.environ.get("INPUTS_ANSWER")), "answer"),
        green_ok=boundary.parsed(os.environ.get("INPUTS_GREEN_OK")),
        eyes_ok=boundary.parsed(os.environ.get("INPUTS_EYES_OK")),
        r2=object_or_none(boundary.parsed(os.environ.get("INPUTS_R2")), "r2"),
        fingerprint_ok=green_cert.matches(fingerprint, repo),
        protected=protected,
    )
    boundary.returns(returned(*place("merge/refused.diff" if reason else "merge/apply.diff"), reason))


try:
    main()
except Exception as e:
    print(json.dumps(broken(mode_of(os.environ.get("INPUTS_MODE", "")), f"{type(e).__name__}: {e}"), ensure_ascii=False,
                     allow_nan=False), flush=True)
