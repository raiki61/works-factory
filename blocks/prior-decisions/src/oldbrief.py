"""今の材料のファイル（material-prior-decisions-brief.md）を同じ字で組む（指示の比べの 1 つ目の commit だけ。docs/design/prior-decisions.md の 2.9）。
写す元 lib/judge_accept.py の material_prep と _na_note（条件を持たず na_self_ok も無い節の枝）。2 つ目の commit で消す"""
import json

BRIEF_FILE = "material-prior-decisions-brief.md"
HEAD = "# 素材集めの役の材料（機械が描いた物）"
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_REFUSED = "`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。"


def brief(view, values) -> str:
    from src import viewpoint
    holes = (("inputs.cwd", str(view.repo)), ("record.base", view.base),
             ("loop.changed_files", json.dumps(list(view.changed_files), ensure_ascii=False, indent=1)),
             ("loop.request_wheres", json.dumps(viewpoint.request_wheres(values), ensure_ascii=False, indent=1)))
    parts = [f"{HEAD}\n\n素材集めの役 prior-decisions（graphloops のノード p0.prior_decisions）の指示書の「［材料: 〜］」は、この下の同じ名の"
             "セクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    parts += [f"## 材料: {name}\n\n{value}" for name, value in holes]
    parts.append(f"{NA_HEADING}\n\nこのノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない"
                 f"（na_self_ok が無い）ので、{NA_REFUSED}")
    return "\n\n".join(parts) + "\n"
