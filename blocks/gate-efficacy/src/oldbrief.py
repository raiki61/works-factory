"""今の判定が役に Read させる材料のファイル（judge/material-gate-efficacy-brief.md）を、同じ字で組む。1 つ目の commit だけの物
（指示の比べの間。docs/design/gate-efficacy.md の 2.9）。2 つ目の commit でファイルごと消す——Python が指示の文を持つのはこの間だけ。
元 lib/judge_accept.py の material_prep・_na_note・mutation_decl"""
import json
import pathlib

from src import mutation, signals

BRIEF_FILE = "material-gate-efficacy-brief.md"
HEAD = "# 素材集めの役の材料（機械が描いた物）"
INTRO = ("素材集めの役 gate-efficacy（graphloops のノード p1.gate_efficacy）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。"
         "パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。")
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_REFUSED = "`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。"
MUTATION_UNDECLARED = ("対象リポジトリの宣言（{decl}）に mutation の段が無い——在りかと呼び方は対象リポジトリの側（README・CONTRIBUTING・"
                       "CI 定義・対象リポジトリの REVIEW.md など）が名指しする物を探せ（このプロンプトは道具の名前と引数の綴りを持たない）")
TOUCHED = "差分が検証ゲートに触れる"


def _mutation_text(repo) -> str:
    m = mutation.state(repo)
    if m["declared"]:
        return (f"対象リポジトリの宣言 {mutation.DECL_NAME} の mutation の段——実行器の呼び方の頭 {m['argv']}・"
                f"腕の一覧 {m['arms']}（口の綴りは実行器の --help が正本）")
    text = MUTATION_UNDECLARED.format(decl=mutation.DECL_NAME)
    return text + (f"（宣言は在るが mutation の段を読めない: {m['error']}）" if m["error"] else "")


def _na_note(view) -> str:
    got = signals.signals_of(view)
    if got is not None and not got:
        body = (f"このノードの条件 `gates_touched` はこの周に真（{TOUCHED}）だが、機械が持つ事実はどれも条件を立てていない（works の受け付けは"
                "このノードの役の判定を受ける）。差分を読んで条件に当たらないと判じたら `not_applicable`（理由を reason に）を"
                "書いてよい。")
    else:
        body = f"このノードの条件 `gates_touched` はこの周に真（{TOUCHED}）なので、{NA_REFUSED}"
    return f"{NA_HEADING}\n\n{body}"


def brief(view, values) -> str:
    holes = (("loop.diff_file", view.diff_file), ("loop.changed_files_file", view.changed_files_file),
             ("record.base", view.base), ("inputs.cwd", str(pathlib.Path(view.repo).resolve())),
             ("loop.mutation_decl.text", _mutation_text(view.repo)))
    parts = [f"{HEAD}\n\n{INTRO}", *[f"## 材料: {name}\n\n{value}" for name, value in holes], _na_note(view)]
    return "\n\n".join(parts) + "\n"
