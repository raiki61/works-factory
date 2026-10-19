"""1 つ目の commit だけの物: 今の judge_accept.material_prep が書く材料のファイル material-external-standards-brief.md を、同じ字で書く
（docs/design/external-standards.md の 2.9 の指示の比べ）。2 つ目の commit で消す"""
import json
import pathlib

import judge_accept  # lib/
import materialkit  # lib/

ROLE = "external-standards"
NODE = "p1.external_standards"
FILE = f"material-{ROLE}-brief.md"


def brief(view, values, place) -> pathlib.Path:
    purpose = values.get("purpose") or {"purpose_text": judge_accept.PURPOSE_MISSING, "known_weaknesses": []}
    review_md, _ = materialkit.review_md_paths(view.repo)
    dump = lambda x: json.dumps(x, ensure_ascii=False, indent=1)
    holes = (("loop.diff_file", view.diff_file), ("loop.changed_files", dump(list(view.changed_files))),
             ("inputs.review_md", review_md), ("out.p0.purpose.purpose_text", purpose["purpose_text"]),
             ("out.p0.purpose.known_weaknesses", dump(purpose["known_weaknesses"])), ("inputs.cwd", str(view.repo)))
    parts = [f"{judge_accept.MATERIAL_BRIEF_HEAD}\n\n素材集めの役 {ROLE}（graphloops のノード {NODE}）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。"
             "パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    parts += [f"## 材料: {hole}\n\n{value}" for hole, value in holes]
    body = ("このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
            f"無い）ので、{judge_accept.NA_REFUSED}")
    parts.append(f"{judge_accept.NA_HEADING}\n\n{body}")
    path = pathlib.Path(place) / FILE
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return path
