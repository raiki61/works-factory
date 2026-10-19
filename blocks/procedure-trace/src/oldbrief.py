"""今の材料のファイル（material-procedure-trace-brief.md）を同じ字で組む（指示の比べの 1 つ目の commit だけ。docs/design/procedure-trace.md の 2.9）。
写す元 lib/judge_accept.py の material_prep と _na_note（条件 touches_procedures を持つ節の、真の枝と偽の枝）。2 つ目の commit で消す"""
import json

BRIEF_FILE = "material-procedure-trace-brief.md"
HEAD = "# 素材集めの役の材料（機械が描いた物）"
NA_HEADING = "## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）"
NA_REFUSED = "`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で書け。"


def brief(view, values) -> str:
    from src import viewpoint
    review_md = viewpoint.materialkit.review_md_paths(view.repo)[0]
    holes = (("loop.diff_file", view.diff_file),
             ("loop.changed_files", json.dumps(list(view.changed_files), ensure_ascii=False, indent=1)),
             ("inputs.review_md", review_md), ("inputs.cwd", str(view.repo)))
    ok, why = viewpoint.applies(view, values)
    if ok:
        na = f"このノードの条件 `touches_procedures` はこの周に真（{why}）なので、{NA_REFUSED}"
    else:
        na = f"このノードの条件 `touches_procedures` はこの周に偽（{why}）なので、`not_applicable`（理由を reason に）を書いてよい。"
    parts = [f"{HEAD}\n\n素材集めの役 procedure-trace（graphloops のノード p1.procedure_trace）の指示書の「［材料: 〜］」は、この下の同じ名の"
             "セクションの値。パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    parts += [f"## 材料: {name}\n\n{value}" for name, value in holes]
    parts.append(f"{NA_HEADING}\n\n{na}")
    return "\n\n".join(parts) + "\n"
