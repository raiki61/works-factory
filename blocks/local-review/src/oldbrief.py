"""今の材料のファイル material-local-review-brief.md を同じ字で組む（1 つ目の commit だけ。指示の比べ用。2 つ目の commit で消す）。

写す元 lib/judge_accept.py の material_prep（局所レビューの穴 MATERIAL_HOLES["local-review"] と『条件に当たらない』の段）と
LOCAL_REVIEW_SKILLS の note つきの一覧。lib/judge_accept.py は import しない。
"""
import json

NOTES = {
    "/code-review": "組み込み（同名のプラグインが別に在る）。対象は changed_files_file に並ぶ**ファイルのパス**で渡す——ref 範囲は作業ツリーを含まない。--comment も --fix も付けるな。",
    "pr-review-toolkit:code-reviewer": "準拠とバグ検出の両方を担う汎用レンズ。**落とすな。**",
    "/simplify": "**修正を禁じた形でだけ呼べ**（実物は既定で作業ツリーを書き換える）。4 観点（再利用・単純化・効率・高度）をそれぞれ起こし、指摘だけ返させる。",
    "pr-review-toolkit:silent-failure-hunter": "黙って無力化される検査・握り潰される失敗を見る。",
    "pr-review-toolkit:type-design-analyzer": "不変条件を平坦な値で持つ設計を見る。散文の振り分けでは当たらないクラス。",
    "pr-review-toolkit:pr-test-analyzer": "振る舞い網羅のレンズ。他のどのノードも見ていない。",
}
HEAD = ("# 素材集めの役の材料（機械が描いた物）\n\n素材集めの役 local-review（graphloops のノード p1.local_review）の指示書の「［材料: 〜］」は、"
        "この下の同じ名のセクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。")
NA = ("## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）\n\n"
      "このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
      "無い）ので、`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。")


def brief(view, review_md: str, repo_review_md: str, skills: list) -> str:
    """skills は新しい形の宣言（applies つき）。note を足して今の一覧の字にする"""
    withnote = []
    for e in skills:
        e = dict(e)
        if e["skill"] in NOTES:
            e["note"] = NOTES[e["skill"]]
        withnote.append(e)
    ordered = [{k: e[k] for k in ("skill", "args", "required", "note", "applies_cond", "applies", "applies_why") if k in e}
               for e in withnote]
    holes = [("loop.diff_file", view.diff_file), ("record.base", view.base), ("loop.changed_files_file", view.changed_files_file),
             ("inputs.review_md", review_md)]
    if repo_review_md:
        holes.append(("inputs.repo_review_md", repo_review_md))
    holes.append(("node.skills", json.dumps(ordered, ensure_ascii=False, indent=1)))
    return "\n\n".join([HEAD, *[f"## 材料: {name}\n\n{value}" for name, value in holes], NA]) + "\n"
