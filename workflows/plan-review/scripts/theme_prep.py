# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の案の審査の役の指示を組む（docs/design/plan-review.md の 19 節の theme_prep）。前の周の受け付けが拒み、合わせた答えの控えが
在れば返り {prompt: "", resubmit: true} だけを返し（出し直しの役の指示は theme-fix-prep が組む）、無ければ 1 回目の役（review-theme）の
指示を md から組む。役を起こす前の作業ツリーの姿も置く。組めなければ crash.json に訳を書いてから落ちる（出口が訳を名指す）"""
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
    from src import files, themeform
    if themeform.resubmitting(place, ports.parsed(os.environ.get("INPUTS_PREV", ""))):
        # 出し直しの役の指示は theme-fix-prep が組む（出し直しの周だけ回る）。ここは作業ツリーの姿を置き直すだけ
        jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
        return {"prompt": "", "resubmit": True}
    values, when = themeform.prompt_values(place, steps.read_intake(place), repo)
    out = prompt.emit(themeform.NODE, values, when, prompt.round_of(themeform.NODE))
    jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
    return {"prompt": out["prompt"], "resubmit": False}


try:
    ports.returns(compute(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "theme-prep", f"{type(error).__name__}: {error}")
    raise
