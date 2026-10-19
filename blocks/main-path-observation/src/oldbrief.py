"""今の材料のファイル（material-main-path-observation-brief.md）を同じ字で組む（指示の比べの 1 つ目の commit だけ。
docs/design/main-path-observation.md の 2.9）。写す元 lib/judge_accept.py の material_prep と _na_note（条件 user_path_touched が真の枝）。
2 つ目の commit で消す"""
BRIEF_FILE = "material-main-path-observation-brief.md"
HEAD = "# 素材集めの役の材料（機械が描いた物）"
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_REFUSED = "`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。"


def brief(view, values) -> str:
    holes = (("loop.diff_file", view.diff_file), ("loop.changed_files_file", view.changed_files_file), ("inputs.cwd", str(view.repo)))
    parts = [f"{HEAD}\n\n素材集めの役 main-path-observation（graphloops のノード p1.main_path_observation）の指示書の「［材料: 〜］」は、この下の同じ名の"
             "セクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    parts += [f"## 材料: {name}\n\n{value}" for name, value in holes]
    parts.append(f"{NA_HEADING}\n\nこのノードの条件 `user_path_touched` はこの周に真（差分が利用者から見える経路に触れる）なので、{NA_REFUSED}")
    return "\n\n".join(parts) + "\n"
