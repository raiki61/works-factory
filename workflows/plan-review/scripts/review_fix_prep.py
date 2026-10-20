# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""受け付けに拒まれた後の出し直しの役（review-fix・review-tree-fix。1 回目の役の会話の続き）の指示を組む（docs/design/plan-review.md の
8 節の review_prep の出し直しの道）。却下の控えの最後の理由と、合わせた答えの控えのパスを共通の断片 resubmit に入れる。役を起こす前の
作業ツリーの姿を置き直す。出し直しの周（review-prep の resubmit が真）だけ回る。組めなければ crash.json に訳を書いてから落ちる"""
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
    from src import files
    intake = steps.read_intake(place)
    node = "review-tree-fix" if intake.get("tree") else "review-fix"
    rejected = rolekit.rejected(place, files.REVIEW_NODE)
    values = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(place, files.REVIEW_NODE)),
              "lang": prompt.lang(intake.get("lang") or "")}
    out = prompt.emit(node, values, {}, prompt.round_of(node))
    jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
    return {"prompt": out["prompt"]}


try:
    ports.returns(compute(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "review-fix-prep", f"{type(error).__name__}: {error}")
    raise
