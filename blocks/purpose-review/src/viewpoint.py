"""観点 purpose-review（目的の監査）の宣言（docs/design/materials.md の 5.1・docs/design/purpose-review.md の 1.5）。

目的の文を役（writer）が自分で要約した run（出典が ③writer の要約）で、その目的の文が実装に都合よく狭められていないかを別の目に
判じさせ、判定の語・理由・作業ツリーで引ける根拠の行を返させる。根拠は固めた版で数え直す（src/cited）。素材は書かず、受けた返答を
material.json の reply に置く。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/
import oneline  # lib/

from . import cited

NAME = "purpose-review"
MATERIALS = ()
GUARDED = True   # AI の node が mutates_checkout: false を持つ（作業ツリーの照らしは porcelain を外す）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = False   # 返答は material の欄を持たず、md は共通の断片 material-na を差し込まない
WRITER_SOURCE = "③writer の要約"   # 目的の block の出典の語の写し
VERDICT_OK = "問題なし"
VERDICT_NARROWS = "狭めている"
VERDICTS = (VERDICT_OK, VERDICT_NARROWS)


def due(view, values) -> materialkit.Due:
    purpose = values.get("purpose")
    if purpose is None:
        return materialkit.Due(False, f"目的の文が渡されていない——監査するのは writer が要約した目的（{WRITER_SOURCE}）だけ")
    src = purpose["source"]
    if src != WRITER_SOURCE:
        return materialkit.Due(False, f"目的テキストの出典が {src}——監査するのは writer が要約した目的（③）だけ")
    return materialkit.Due(True, "writer が要約した目的の 1 周目")


def fill(view, values, due) -> dict:
    return {}


def applies(view, values):
    raise NotImplementedError("purpose-review は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    return {"purpose_text": values["purpose"]["purpose_text"], "repo": str(view.repo), "review_rev": view.review_rev,
            "verdict_ok": VERDICT_OK, "verdict_narrows": VERDICT_NARROWS}


def when(view, values) -> dict:
    return {}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return cited.problem(reply, view.review_rev, VERDICT_NARROWS)


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    if not isinstance(reply, dict):
        return []
    rows = [r for r in reply.get("findings") or [] if isinstance(r, dict)]
    return ([f"  - 判定: {reply.get('verdict')}（根拠 {len(rows)} 件）"]
            + [f"  - 根拠: {oneline.one_line(r.get('text') or '')}（{oneline.one_line(r.get('cite') or '')} が {r.get('hits')} 行）"
               for r in rows])
