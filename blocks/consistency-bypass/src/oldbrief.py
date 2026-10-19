"""1 つ目の commit だけ（指示の比べの間）: 今の材料のファイル material-consistency-bypass-brief.md を同じ字で組む。
今の judge_accept.material_prep のうち、この観点の分（docs/design/consistency-bypass.md の 2.9）。2 つ目の commit で消す"""
import json

import materialkit  # lib/

HEAD = "# 素材集めの役の材料（機械が描いた物）"
INTRO = ("素材集めの役 consistency-bypass（graphloops のノード p1.consistency_bypass）の指示書の「［材料: 〜］」は、この下の同じ名の"
         "セクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。")
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_BODY = ("このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
           "無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で"
           "書け。")
ABSENT = "（この周には無い）"


def brief(view, values) -> str:
    own, theirs = materialkit.review_md_paths(view.repo)
    holes = (("loop.diff_file", view.diff_file),
             ("loop.changed_files", json.dumps(list(view.changed_files), ensure_ascii=False, indent=1)),
             ("record.base", view.base), ("inputs.review_md", own), ("inputs.repo_review_md", theirs or ABSENT),
             ("inputs.review_rev", view.review_rev), ("inputs.cwd", str(view.repo)))
    parts = [f"{HEAD}\n\n{INTRO}", *[f"## 材料: {name}\n\n{value}" for name, value in holes], f"{NA_HEADING}\n\n{NA_BODY}"]
    return "\n\n".join(parts) + "\n"
