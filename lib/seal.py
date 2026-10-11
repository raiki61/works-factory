"""run の差分の封印と、封じた差分を置いてよいかの決まり。標準ライブラリと答えの語（answer.VERBS）だけ。

差分を組む・作業ツリーの指紋を取るのは green_cert（差分の組み方の 1 か所）で、ここは持たない。
封じる型は ASF の merge-queue（gate の封印を execute が照らし直し、書いた後に読み戻す）に倣う。

- SealError: 書けない・読み戻しが書いた物と違う
- digest(data) -> str: sha256 の 16 進 64 字
- write_readback(path, data) -> str: 書いて読み戻し、読み戻した物の digest を返す。違えば SealError（書けたと言わない）
- seal_refusal(*, fingerprint, fingerprint_ok) -> str: 封じてよいかの理由（空なら封じてよい）
- unknown_row(reason) -> str: 守りのパスを確かめられない時に、当たりとして数える 1 行
- apply_refusal(*, ...) -> str: 置いてよいかの理由（空なら置く）。決まりは関数の doc
"""
import hashlib
import pathlib

from answer import VERBS

PASS = ("approve", VERBS[0])     # 通す語。approve は承認の節の decisions に要る語、continue は今の works の答えの語
STOPS = (VERBS[1], "reject")     # 止める語（今の works の report.FINAL_GATE_STOPS）
REQUEST_BY = "request:"          # 止め札: 文がこれで始まる止める語（今の works の report.REQUEST_BY）
REDESIGN = "redesign-needed"     # R2 の作り直しの語。unverifiable は機械で拒まず人の答えに任せる
UNKNOWN_HEAD = "守りのパスを確かめられない（差分が一覧に触れていないとは言えない）: "


class SealError(Exception):
    """書けない・読み戻しが書いた物と違う"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_readback(path, data: bytes) -> str:
    path = pathlib.Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        back = path.read_bytes()
    except OSError as e:
        raise SealError(f"{path} に書けない（{e}）") from e
    if digest(back) != digest(data):
        raise SealError(f"{path} の読み戻しが書いた物と違う（書いた {digest(data)}・読んだ {digest(back)}）")
    return digest(back)


def seal_refusal(*, fingerprint, fingerprint_ok) -> str:
    """緑の認証の指紋 fingerprint が在り、今の木と合わなければ（fingerprint_ok が偽。照らすのは green_cert.matches）理由。
    fingerprint が無ければ照らさない"""
    if fingerprint is None or fingerprint_ok:
        return ""
    return "緑の認証の指紋が今の木と違う（test-gate の後に作業ツリーが変わった）"


def unknown_row(reason: str) -> str:
    return UNKNOWN_HEAD + reason


def _answer_refusal(answer: dict) -> str:
    word = answer.get("decision")
    if word in PASS:
        return ""
    text = answer.get("text")
    if word in STOPS and isinstance(text, str) and text.startswith(REQUEST_BY):
        kind = "（止め札）"
    elif word in STOPS:
        kind = ""
    else:
        kind = f"（通す語 {'・'.join(PASS)} のどれでもない）"
    return f"最後の関所で {word or '語なし'} と答えた{kind}"


def apply_refusal(*, sealed_hash, current_hash, answer, green_ok, eyes_ok, r2, fingerprint_ok, protected) -> str:
    """置いてよいかの理由（空なら置く）。上から順に見て最初の理由を返す:
    1. sealed_hash が空（seal が走っていない）
    2. current_hash が sealed_hash と違う
    3. 答え answer（{decision, text}）が在り、decision が PASS のどれでもない（止め札もここ）
    4. r2（None か {status, reason}）の status が REDESIGN。人の通しの答えでも拒む（R2 が作り直しと言った run は部分を取り込まない）
    5. 答えが無い（関所が開かなかった）のに、green_ok・eyes_ok・fingerprint_ok のどれかが真でないか、protected（守りの当たりの行。
       unknown_row の行も当たり）が空でない。守りのパスは人の通しの答えだけが通す
    答えが PASS なら、赤でも・R2 の作り直しのほかの目の阻害でも置く"""
    if not sealed_hash:
        return "封じた hash が無い（seal が走っていない）"
    if current_hash != sealed_hash:
        return f"封じた差分と今の差分が違う（封じた {sealed_hash}・今 {current_hash}）"
    if answer is not None:
        why = _answer_refusal(answer)
        if why:
            return why
    if isinstance(r2, dict) and r2.get("status") == REDESIGN:
        return f"R2 が作り直しと言った（部分を取り込まない）: {r2.get('reason') or '理由なし'}"
    if answer is None:
        unchecked = [word for word, fact in (("緑でない", green_ok), ("目が通していない", eyes_ok),
                                             ("緑の認証の指紋が今の木と違う", fingerprint_ok)) if fact is not True]
        if protected:
            unchecked.append(f"守りのパスに当たった（{len(protected)} 行）")
        if unchecked:
            return f"人の通しの答えが無いのに {'・'.join(unchecked)}"
    return ""
