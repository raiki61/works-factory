"""【1 つ目の commit だけ】今の判定の材料のファイル material-purpose-review-brief.md を、今と同じ字で書く（docs/design/purpose-review.md
の 2.9 の指示の比べ。2 つ目の commit で、このファイルと比べる試験を消す）。写す元 lib/judge_accept.py の material_prep・_na_note"""
from pathlib import Path

BRIEF_FILE = "material-purpose-review-brief.md"
HEAD = "# 素材集めの役の材料（機械が描いた物）"
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_BODY = ("このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
           "無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で"
           "書け。")


def brief(view, values) -> str:
    holes = (("out.p0.purpose.purpose_text", values["purpose"]["purpose_text"]),
             ("inputs.review_rev", view.review_rev),
             ("inputs.cwd", str(Path(view.repo).resolve())))
    parts = [f"{HEAD}\n\n素材集めの役 purpose-review（graphloops のノード p0.purpose_review）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。"
             "パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    parts += [f"## 材料: {name}\n\n{value}" for name, value in holes]
    parts.append(f"{NA_HEADING}\n\n{NA_BODY}")
    return "\n\n".join(parts) + "\n"
