"""今の材料のファイル judge/material-provenance-brief.md を同じ字で組む（1 つ目の commit だけ。指示の比べのため。
docs/design/provenance.md の 2.9）。今は lib/judge_accept.py の material_prep が組む"""

HEAD = "# 素材集めの役の材料（機械が描いた物）"
INTRO = ("素材集めの役 provenance（graphloops のノード p1.provenance）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。"
         "パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。")
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_BODY = ("このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
           "無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。")


def brief(view, values) -> str:
    parts = [f"{HEAD}\n\n{INTRO}",
             f"## 材料: loop.diff_file\n\n{view.diff_file}",
             f"## 材料: record.base\n\n{view.base}",
             f"## 材料: inputs.cwd\n\n{view.repo}",
             f"{NA_HEADING}\n\n{NA_BODY}"]
    return "\n\n".join(parts) + "\n"
