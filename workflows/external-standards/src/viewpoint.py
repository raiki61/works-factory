"""観点 external-standards（外部標準照合）の宣言（docs/design/materials.md の 5.1・docs/design/external-standards.md の 1.5）。

対象差分が解いている問題を一般の問題の類に言い直させ、外の一次情報で定番解からの逸脱・劣化変種・手元の依存の使い残しを見させる。
判定から入る run では役を起こさない。『条件に当たらない』は名乗れない。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import json

import ports  # blocks/.shared/

import materialkit  # lib/
import oneline  # lib/

from src import rankings

REVIEW_MD = ports.SHARED / "prompts" / "REVIEW.md"   # 観点の正本（工場の物。lib は経由しない）

NAME = "external-standards"
MATERIALS = ("external_standards",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
STANDARDS_SECTION = "外部標準照合観点"   # 観点の正本 blocks/.shared/prompts/REVIEW.md の見出しの字（md と正本が合うべき値）
CRITERIA_SECTION = "指摘の提出基準"


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def due(view, values) -> materialkit.Due:
    if materialkit.is_entry_run(view, values):
        return materialkit.entry_skip("外部標準の照合")
    return materialkit.Due(True, "外部標準の照合は、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回）")


def fill(view, values, due) -> dict:
    return {"external_standards": materialkit.fill_entry(values["entry"], None)}


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("external-standards は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    own, theirs = materialkit.review_md_paths(view.repo, REVIEW_MD)
    out = {"diff_file": view.diff_file, "changed_files": _dump(list(view.changed_files)), "repo": str(view.repo),
           "review_md": own, "standards_section": STANDARDS_SECTION, "criteria_section": CRITERIA_SECTION,
           "purpose_text": "", "known_weaknesses": "", "repo_review_md": theirs}   # 段落が入らない時も空の字で渡す（指示を組む口が数える）
    if values["purpose"] is not None:
        out["purpose_text"] = values["purpose"]["purpose_text"]
        out["known_weaknesses"] = _dump(values["purpose"]["known_weaknesses"])
    return out


def when(view, values) -> dict:
    _, theirs = materialkit.review_md_paths(view.repo, REVIEW_MD)
    return {"spawns": False, "purpose": values["purpose"] is not None, "repo_review": bool(theirs)}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return rankings.problem(reply)


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"external_standards": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    if not isinstance(reply, dict):
        return []
    rows = [r for r in reply.get("rankings") or [] if isinstance(r, dict)]
    if not rows:
        return [f"  - 順位: 付けられる問題なし（{oneline.one_line(reply.get('rankings_none') or '')}）"]
    out = []
    for r in rows:
        ranked = r.get("ranked") or []
        k = ranked.index(r.get("diff_at")) + 1 if r.get("diff_at") in ranked else 0
        out.append(f"  - 順位: {oneline.one_line(r.get('problem') or '')}——差分は {k} 位／{len(ranked)} 位中"
                   f"（{oneline.one_line(r.get('diff_at') or '')}）")
    return out
