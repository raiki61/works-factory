# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""受け付けに拒まれた後の出し直しの役（review-theme-fix。1 回目の役の会話の続き）の指示を組む（docs/design/plan-review.md の 19 節の
theme_fix_prep）。却下の控えの最後の理由と、合わせた答えの控えのパスを共通の断片 resubmit に入れる。役を起こす前の作業ツリーの姿を
置き直す。出し直しの周（theme-prep の resubmit が真）だけ回る。組めなければ crash.json に訳を書いてから落ちる"""
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
    from src import files, themeform
    values, when = themeform.fix_values(place, steps.read_intake(place))
    out = prompt.emit(themeform.FIX_NODE, values, when, prompt.round_of(themeform.FIX_NODE))
    jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
    return {"prompt": out["prompt"]}


try:
    ports.returns(compute(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "theme-fix-prep", f"{type(error).__name__}: {error}")
    raise
