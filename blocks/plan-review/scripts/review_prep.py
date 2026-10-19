# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の役の指示を組む（docs/design/plan-review.md の 8 節の review_prep）。前の周の受け付けが拒み、合わせた答えの控えが在れば
返り {prompt: "", resubmit: true} だけを返し（出し直しの役の指示は review-fix-prep が組む）、無ければ材料のファイルを書いて 1 回目の役（review・review-tree）の指示を組む。
役を起こす前の作業ツリーの姿も置く。組めなければ crash.json に訳を書いてから落ちる（出口が訳を名指す）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402


def compute(place: Path, repo: Path) -> dict:
    import accept    # lib/
    import jsonfile  # lib/
    import prompt
    import rolekit   # lib/
    from src import files, material, view
    intake = steps.read_intake(place)
    tree = bool(intake.get("tree"))
    prev = ports.parsed(os.environ.get("INPUTS_PREV", ""))
    if rolekit.resubmitting(place, files.REVIEW_NODE, prev):
        # 出し直しの役の指示は review-fix-prep が組む（出し直しの周だけ回る）。ここは作業ツリーの姿を置き直すだけ
        jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
        return {"prompt": "", "resubmit": True, "tree": tree}
    node = "review-tree" if tree else "review"
    n = prompt.round_of(node)
    b = view.view(place, intake)
    path, values, when = material.write_material(place, intake, repo, n=n, b=b)
    if tree:
        from src import tree as tree_part
        values, when = tree_part.write_tree(place, b, intake, path, n)
    out = prompt.emit(node, values, when, n)
    jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
    return {"prompt": out["prompt"], "resubmit": False, "tree": tree}


try:
    ports.returns(compute(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "review-prep", f"{type(error).__name__}: {error}")
    raise
