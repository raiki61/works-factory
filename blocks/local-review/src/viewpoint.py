"""観点 local-review（局所レビュー）の宣言（docs/design/materials.md の 5.1・docs/design/local-review.md の 1.5）。

対象差分に、宣言した 7 本のレンズ（skill 3 本と pr-review-toolkit の agent 4 本。src/lenses.py の LENSES）を 1 本ずつ名指しで起こさせ、
レンズごとに 1 行の所見と素材 local_review を返させる。判定から入る run では役を起こさない（修正が入るまで依頼の外を見る役は起こさない）。
『条件に当たらない』は名乗れない。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言とレンズの照らしの配線だけを持つ。
"""
import json

import jsonfile  # lib/
import materialkit  # lib/
import seat  # lib/

from src import lenses

NAME = "local-review"
MATERIALS = ("local_review",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（Archon が節の前後の git status を照らさない役。porcelain も比べる）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
NOUN = "P1 の役"


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def due(view, values) -> materialkit.Due:
    if values["entry"]:
        return materialkit.entry_skip(NOUN)
    return materialkit.Due(True, "判定から入る run でない（port entry が空）——通常の run")


def fill(view, values, due) -> dict:
    return {"local_review": materialkit.fill_entry(values["entry"], None)}


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("local-review は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    own, theirs = materialkit.review_md_paths(view.repo)
    return {"diff_file": view.diff_file, "base": view.base, "changed_files_file": view.changed_files_file,
            "review_md": own, "repo_review_md": theirs, "skills": _dump(lenses.skills()),
            "unattended": seat.overlay_body(seat.OVERLAY_KINDS["local-review"])}


def when(view, values) -> dict:
    _, theirs = materialkit.review_md_paths(view.repo)
    return {"spawns": True, "repo_review": bool(theirs)}


def before(view, values, reply, place) -> tuple:
    skills = lenses.skills()
    got, _ = lenses.mark_unseen(reply, skills)
    gap = lenses.lens_gap(skills, got)
    if gap:
        return gap[0], got, gap[1]
    return None, got, False


def after(view, values, reply, place):
    return lenses.covers_lenses(lenses.skills(), reply)


def after_accept(reply, place) -> None:
    jsonfile.write(place / lenses.LENS_FILE, {"round": 1, "unseen": lenses.unseen(reply)}, parents=True)


def materials_of(reply) -> dict:
    return {"local_review": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    if not isinstance(reply, dict):
        return []
    return [f"  - {s}" for s in lenses.unseen_lines(lenses.unseen(reply))]
