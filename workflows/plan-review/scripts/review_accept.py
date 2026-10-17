# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の受け付け（boardview.take_review）。役の節は単独の組（reply・fix_reply）と束ね役の組（tree_reply・tree_fix_reply）の
4 つで、起きなかった節の返答は null（if_skipped: null）。null でない方を take_review の reply・fix_reply に渡す（どの組が起きたかは
boardview が知らない。open の tree で木のまとめに入るかを決める）。拒まれた後の出し直しの役の返答 fix_reply（拒まれた欄だけ）は
前の答えと合わせてから照らす。拒みは控えに積み、3 回目で done・give_up"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import boardview  # noqa: E402


def replied(*raws):
    """with: で受けた返答の字（節ごとに 1 つ）のうち、null でない最初の値（起きた節の返答。どれも無ければ None）"""
    got = (boundary.value(raw) for raw in raws)
    return next((x for x in got if x is not None), None)


boundary.returns(boardview.take_review(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER,
                                       replied(os.environ.get("INPUTS_REPLY"), os.environ.get("INPUTS_TREE_REPLY")), Path.cwd(),
                                       keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")),
                                       fix_reply=replied(os.environ.get("INPUTS_FIX_REPLY"), os.environ.get("INPUTS_TREE_FIX_REPLY"))))
