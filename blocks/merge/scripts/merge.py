# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の node place。seal は今の差分を封じて守りのファイルの当たりを返し、apply は封じた hash を今の差分と照らして置き、
check は封じた hash を今の差分と照らすだけで置く（答え・緑・目は、その差分を作った所で済んだ物）。

差分は作業ツリー（node の cwd）と差分の根 base の間で green_cert.diff_bytes が組む。守りのファイルの当たりは seal・apply が差分から
数える（守りの一覧は自分の一覧と、対象のリポジトリの base の宣言を合わせた物）。seal の返りの当たりは先頭の数行と残りの 1 行に切り
（protect.shown）、全件の数を protected_count に、全件を place の protected-all.json に置く。
Archon が作業ツリーに置く工程の写し（.archon/ の下）は修正の差分でないので載せない。
書く（消す）のは place の自分の名のファイルだけ。apply・check は始めに前の apply.diff を消し、置くと決めた時だけ書く（やり直しが拒んでも
古い物が残らない）。返りの base_rev（差分の根）と deliver（確かめた出口の語。lib/entry.py の DELIVERS）は後ろの node が読む。
落ちない: どの誤りも終了の値 0 で ok: false と理由を返す。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

MODES = ("seal", "apply", "check")


def broken(mode: str, reason: str) -> dict:
    return {"mode": mode if mode in MODES else "seal", "ok": False, "hash": "", "diff": None, "protected_hits": None,
            "protected_count": None, "reason": reason, "base_rev": "", "deliver": ""}


def true_only(raw) -> bool:
    """flag の入力。真偽でない値は偽（拒む側に倒れる）"""
    try:
        return ports.flag(raw)
    except ValueError:
        return False


def optional_json(raw, schema: str):
    return None if ports.text(raw).strip() in ("", "null") else ports.json(raw, schema)


def compute() -> dict:
    import entry
    import green_cert
    import protect
    import seal
    from src import files

    mode = ports.choice(os.environ.get("INPUTS_MODE"), MODES)
    folder = ports.place()
    if mode != "seal":
        (folder / files.APPLIED).unlink(missing_ok=True)
    deliver = entry.deliver_word(ports.text(os.environ.get("INPUTS_DELIVER")))
    base = ports.text(os.environ.get("INPUTS_BASE")).strip()
    if not base:
        raise ValueError(f"差分の根 base が無い: {base!r}")
    fingerprint = optional_json(os.environ.get("INPUTS_FINGERPRINT"), "fingerprint.schema.json")
    repo = Path.cwd()

    data = green_cert.diff_bytes(repo, base, skip=(ports.RUNTIME_COPY_PREFIX,))
    if not data:
        return broken(mode, f"差分が空（{base} から今の作業ツリーまで変わった物が無い）")

    def put(name: str) -> tuple:
        path = folder / name
        return ports.pointer(path), seal.write_readback(path, data)

    def returned(ptr, digest: str, reason: str, hits=None, count=None) -> dict:
        return {"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": hits, "protected_count": count,
                "reason": reason, "base_rev": base, "deliver": deliver}

    sealed_hash = ports.text(os.environ.get("INPUTS_SEALED_HASH")).strip()
    if mode == "check":
        reason = seal.hash_refusal(sealed_hash, seal.digest(data))
        return returned(*put(files.REFUSED if reason else files.APPLIED), reason)

    try:
        stats = seal.diff_files(repo, data)
        protected = protect.lines([{**r, "added": stats[r["path"]][0], "deleted": stats[r["path"]][1]}
                                   for r in protect.hits(stats, protect.merged(repo, base))])
        counted = len(protected)
    except (protect.Broken, ValueError) as error:
        protected, counted = [seal.unknown_row(str(error))], 0

    if mode == "seal":
        reason = seal.seal_refusal(fingerprint=fingerprint, fingerprint_ok=green_cert.matches(fingerprint, repo))
        ptr, digest = put(files.SEALED)
        whole = folder / files.PROTECTED_FILE
        whole.write_text(json.dumps({"protected_hits": protected}, ensure_ascii=False), encoding="utf-8")
        return returned(ptr, digest, reason, protect.shown(protected, "protected_hits", whole), counted)

    reason = seal.apply_refusal(
        sealed_hash=sealed_hash,
        current_hash=seal.digest(data),
        answer=optional_json(os.environ.get("INPUTS_ANSWER"), "answer.schema.json"),
        green_ok=true_only(os.environ.get("INPUTS_GREEN_OK")),
        eyes_ok=true_only(os.environ.get("INPUTS_EYES_OK")),
        r2=optional_json(os.environ.get("INPUTS_R2"), "r2.schema.json"),
        fingerprint_ok=green_cert.matches(fingerprint, repo),
        protected=protected,
    )
    return returned(*put(files.REFUSED if reason else files.APPLIED), reason)


ports.run(compute, lambda why: broken(os.environ.get("INPUTS_MODE", ""), why))
