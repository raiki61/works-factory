"""観点 provenance（根拠の出所検査）の宣言（docs/design/materials.md の 5.1・docs/design/provenance.md の 1.5）。

対象差分の本文・説明・docstring が根拠に引く物が差分の根の時点に在ったかを確かめさせ、主張の行（claims）と素材 provenance を返させる。
判定から入る run のほかはいつも回し（1 run は 1 周で、いつも初回）、判定から入る run では役を起こさずに入口の理由つきの
not_applicable を書く。『条件に当たらない』は名乗れない。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/
import oneline  # lib/

NAME = "provenance"
MATERIALS = ("provenance",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む


def due(view, values) -> materialkit.Due:
    if values.get("entry"):
        return materialkit.entry_skip("出典の確かめ")
    return materialkit.Due(True, "根拠の出所検査は run ごとに 1 回回す（判定から入る run でない。1 run は 1 周で、いつも初回）")


def fill(view, values, due) -> dict:
    return {"provenance": materialkit.fill_entry(values["entry"], None)}   # 回さないのは判定から入る run の時だけ。依頼の件数の port は無い


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("provenance は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    return {"repo": str(view.repo), "base": view.base, "diff_file": view.diff_file}


def when(view, values) -> dict:
    return {"spawns": False}   # この役は Agent の道具を持たない


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"provenance": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    """差分の根に無い根拠（循環と未確認の前提）の行だけを出す。claims の全部は material.json の reply に残る"""
    reply = doc.get("reply")
    rows = reply.get("claims") if isinstance(reply, dict) else None
    return [f"  - 差分の根に無い根拠: {oneline.one_line(r.get('claim') or '')}"
            for r in rows or [] if isinstance(r, dict) and r.get("exists_at_base") is False]
