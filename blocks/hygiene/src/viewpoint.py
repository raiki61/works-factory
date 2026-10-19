"""観点 hygiene（コード衛生）の宣言（docs/design/materials.md の 5.1・docs/design/hygiene.md の 1.5）。

対象差分を、何の機能かも近傍のコードも知らない目（道具を持たない役）で読み、言語・フレームワーク一般の衛生の逸脱を拾わせて
素材 hygiene を返させる。観点の本文（lib/REVIEW.md の「コード衛生観点」の節）と差分の本文の全部を指示に貼る。返答に material の
欄は無く、findings と seen から機械が素材を作る。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/

from src import paste

NAME = "hygiene"
MATERIALS = ("hygiene",)
GUARDED = True   # AI の node が mutates_checkout: false を持つ（作業ツリーの照らしは porcelain を外して比べる）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = False   # 返答に material の欄が無く、md は共通の断片 material-na を差し込まない


def due(view, values) -> materialkit.Due:
    return materialkit.not_entry_due(view, values, "P1 の役")


def fill(view, values, due) -> dict:
    return {"hygiene": materialkit.fill_entry(values["entry"], None)}


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("hygiene は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    own, _ = materialkit.review_md_paths(view.repo)   # 対象の根の REVIEW.md は使わない（工場の観点の正本だけ）
    return {"review_section": paste.review_section(own), "diff": paste.diff_body(view.diff_file)}


def when(view, values) -> dict:
    return {}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"hygiene": materialkit.material_from_findings(reply)}


def report_lines(doc) -> list:
    return []
