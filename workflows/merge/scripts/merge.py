# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の返す節。3 つの形を持つ。seal は今の差分を封じて守りのパスの当たりを返し、apply は封じた hash を今の差分と照らして置く。
handoff は周の鎖の最後の差分（鎖の final-diff が封じて返す apply）を、そのバイトの hash と R2 の状態を照らして置く。

seal と apply の差分は作業ツリー（節の cwd）と始めの記録の base_rev の間で green_cert.diff_bytes が組み、守りのパスの当たりもその差分から数える
（守りの一覧は自分の一覧と、対象のリポジトリの base_rev の宣言を合わせた物）。handoff の差分は placed のポインタの先のバイトで、
元の基は入力 base_rev（鎖の始めの HEAD）、拒みを当てる決めは lib/seal.py の handoff_refusal（鎖の側に受け入れの決めを写さない）。
Archon が作業ツリーに置く工程の写し（.archon/ の下）は修正の差分でないので載せない。
作業ツリーは書かない。書く（消す）のは run の置き場だけで、外への書き込みは下の出口の語 deliver が pr の時の 1 か所だけ。apply と handoff は始めに前の
merge/apply.diff を消し、置くと決めた時だけ書く（やり直しが拒んでも古い物が残らない）。
出口の語 deliver（apply と handoff だけ読む。seal は読まない）が pr の時だけ、置いた差分を lib/deliver.py の口 submit が専用の枝と PR として
対象の remote へ書き、結果を delivered に返す。置かなかった時は書かず、置かなかった訳を delivered に返す。空の語は何も書かず delivered は null。
落ちない: どの誤りも終了の値 0 で ok: false と理由を返す（線は落ちた返す節の先へ進めない）。apply と handoff で出口の語が空でなければ、
例外で落ちた時も delivered に {ok: false, reason} を載せ、訳の頭はこの run で merge/apply.diff を置いたかで分ける（null は何も頼まれて
いない印。lib を読めずに落ちた時だけは null）。
提出する commit と PR の本文が名指す依頼の issue は、始めのノードが控えた番号の並び（apply は始めの記録の欄 issues、handoff は入力 issues）
を読み、依頼のファイルは読み直さない（run の途中でファイルが変わっても値がずれず、置く能力を落とさない）。控えが null（始めに読めなかった）
なら番号なしで提出し、読めなかったと本文に 1 行書く（lib/deliver.py の submit）。
"""
import json
import os

MODES = ("seal", "apply", "handoff")
APPLY_DIFF = "merge/apply.diff"
PLACED = []   # この run で置いた APPLY_DIFF のポインタ（落ちた時の delivered の訳を、置いた事実で分ける）


def broken(mode: str, reason: str) -> dict:
    return {"mode": mode, "ok": False, "hash": "", "diff": None, "protected_hits": None, "reason": reason, "delivered": None}


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
    import deliver
    import green_cert
    import protect
    import seal

    mode = os.environ["INPUTS_MODE"]
    if mode not in MODES:
        raise ValueError(f"mode は {'・'.join(MODES)} のどれか: {mode!r}")
    word = "" if mode == "seal" else deliver.check(boundary.text(os.environ.get("INPUTS_DELIVER")))
    if mode != "seal":
        boundary.resolve(boundary.pointer(APPLY_DIFF)).unlink(missing_ok=True)

    def place(rel: str, data: bytes) -> tuple:
        ptr = boundary.pointer(rel)
        digest = seal.write_readback(boundary.resolve(ptr), data)
        if rel == APPLY_DIFF:
            PLACED.append(ptr)
        return ptr, digest

    def delivered_of(placed: bool, why: str, repo, base_rev: str, data: bytes, digest: str = "", issues=None):
        """出口の結果。空の語は null、置かなかった時は書かずにその訳、置いた時だけ提出する"""
        if not placed:
            return deliver.refused(word, why)
        if word != deliver.PR:
            return None
        scratch = boundary.resolve(boundary.pointer("merge/objects"))
        return deliver.submit(repo, base_rev, data, os.environ["WORKFLOW_ID"], scratch, digest, issues)

    def handoff() -> None:
        """周の鎖の最後の差分を置く。placed は final-diff の apply {ok, hash, diff, reason}、r2 は final-diff の r2_status の字（pass・
        redesign-needed・null）。通らなければ何も置かず・書かずに ok: false"""
        placed = object_or_none(boundary.parsed(os.environ["INPUTS_PLACED"]), "placed")
        r2_status = boundary.text(os.environ["INPUTS_R2"])
        data, unreadable = None, ""
        if isinstance(placed, dict) and placed.get("ok") is True:
            try:
                data = boundary.resolve(placed.get("diff")).read_bytes()
            except (OSError, ValueError) as error:
                unreadable = f"placed のポインタの先を読めない: {error}"
        reason = unreadable or seal.handoff_refusal(placed, seal.digest(data) if data is not None else "", r2_status)
        if not reason and not data:
            reason = "差分が空（placed のポインタの先にバイトが無い）"
        base_rev = boundary.text(os.environ.get("INPUTS_BASE_REV"))
        if not reason and word == deliver.PR and not base_rev:
            raise ValueError("入力 base_rev が無い（提出する差分の元の基）")
        if reason:
            boundary.returns({**broken("handoff", reason), "delivered": delivered_of(False, reason, None, "", b"")})
            return
        ptr, digest = place(APPLY_DIFF, data)
        boundary.returns({"mode": "handoff", "ok": True, "hash": digest, "diff": ptr, "protected_hits": None, "reason": "",
                          "delivered": delivered_of(True, "", Path.cwd(), base_rev, data, digest,
                                                    boundary.value(os.environ.get("INPUTS_ISSUES")))})

    if mode == "handoff":
        handoff()
        return

    record = json.loads(boundary.needed(os.environ["INPUTS_START"], "start").read_text(encoding="utf-8"))
    base_rev = record.get("base_rev")
    if not isinstance(base_rev, str) or not base_rev:
        raise ValueError(f"始めの記録に base_rev が無い: {base_rev!r}")
    fingerprint = boundary.parsed(os.environ["INPUTS_FINGERPRINT"])
    repo = Path.cwd()

    data = green_cert.diff_bytes(repo, base_rev, skip=(boundary.RUNTIME_COPY_PREFIX,))
    if not data:
        why = f"差分が空（{base_rev} から今の作業ツリーまで変わった物が無い）"
        boundary.returns({**broken(mode, why), "delivered": delivered_of(False, why, repo, base_rev, data)})
        return

    try:
        stats = seal.diff_files(repo, data)
        protected = protect.lines([{**r, "added": stats[r["path"]][0], "deleted": stats[r["path"]][1]}
                                   for r in protect.hits(stats, protect.merged(repo, base_rev))])
    except (protect.Broken, ValueError) as e:
        protected = [seal.unknown_row(str(e))]

    if mode == "seal":
        reason = seal.seal_refusal(fingerprint=fingerprint, fingerprint_ok=green_cert.matches(fingerprint, repo))
        ptr, digest = place("merge/sealed.diff", data)
        boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": protected,
                          "reason": reason, "delivered": None})
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
    ptr, digest = place("merge/refused.diff" if reason else APPLY_DIFF, data)
    boundary.returns({"mode": mode, "ok": not reason, "hash": digest, "diff": ptr, "protected_hits": None, "reason": reason,
                      "delivered": delivered_of(not reason, reason, repo, base_rev, data, digest, record.get("issues"))})


def broken_with_delivery(mode: str, reason: str) -> dict:
    """落ちた時の返り。apply と handoff は、出口の語（確かめる前の字）で頼まれていれば書かなかった訳を delivered に載せる。
    lib を読めずに落ちた時は delivered は null のまま（訳は reason に在る）"""
    got = broken(mode, reason)
    if mode != "seal":
        try:
            import deliver
        except ImportError:
            return got
        got["delivered"] = deliver.refused(os.environ.get("INPUTS_DELIVER"), reason, placed=bool(PLACED))
    return got


try:
    main()
except Exception as e:
    print(json.dumps(broken_with_delivery(mode_of(os.environ.get("INPUTS_MODE", "")), f"{type(e).__name__}: {e}"), ensure_ascii=False,
                     allow_nan=False), flush=True)
