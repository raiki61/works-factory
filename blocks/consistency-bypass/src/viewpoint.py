"""観点 consistency-bypass（整合性と標準機構の迂回）の宣言（docs/design/materials.md の 5.1・docs/design/consistency-bypass.md の 1.5）。

対象差分の依存先・近傍・呼び元を読ませ、リポジトリ横断の整合性（素材 consistency）と標準機構の迂回（素材 bypass）を独立に見て、
所見の行も 2 系統（findings・bypass_findings）で返させる。判定から入る run（entry が空でない）では役を起こさず、2 つの素材に理由つきの
not_applicable を書く。『条件に当たらない』は名乗れない。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import json

import materialkit  # lib/
import oneline  # lib/

NAME = "consistency-bypass"
MATERIALS = ("consistency", "bypass")
GUARDED = True   # AI の node が mutates_checkout: false を持つ（Archon 自身が git status を照らすので porcelain を比べない）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = True   # md が共通の断片 material-na を差し込む（na_* の段落と na_why を prompt_inputs が足す）


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def due(view, values) -> materialkit.Due:
    # 判定から入る run の周（entry が在り、対象差分が空）だけ回さない。修正が入って差分が出来た run は入口の周でない
    return materialkit.not_entry_due(view, values, "P1 の役")


def fill(view, values, due) -> dict:
    # 回さないのは判定から入る run の時だけ。この観点は依頼の行を持たないので、件数は 0 を渡す
    return {m: materialkit.fill_entry(values["entry"], 0) for m in MATERIALS}


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("consistency-bypass は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    # repo_review_md は対象に REVIEW.md が無い回も空の字で渡す（指示を組む口は選ばれない段落の中の差し込み口も数える）
    own, theirs = materialkit.review_md_paths(view.repo)
    return {"repo": str(view.repo), "review_rev": view.review_rev, "base": view.base, "diff_file": view.diff_file,
            "changed_files": _dump(list(view.changed_files)), "review_md": own, "repo_review_md": theirs}


def when(view, values) -> dict:
    return {"repo_review": bool(materialkit.review_md_paths(view.repo)[1])}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {m: reply[m] for m in MATERIALS if isinstance(reply.get(m), dict)}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    unseen = reply.get("unseen") if isinstance(reply, dict) else None
    return [f"  - 見ていない範囲: {oneline.one_line(unseen)}"] if isinstance(unseen, str) and unseen.strip() else []
