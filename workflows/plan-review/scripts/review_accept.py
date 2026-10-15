# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の受け付け（boardview.take_review）。拒まれた後の出し直しの役の返答 fix_reply（拒まれた欄だけ）は前の答えと合わせてから
照らす。拒みは控えに積み、3 回目で done・give_up"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import boardview  # noqa: E402

boundary.returns(boardview.take_review(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER,
                                       boundary.value(os.environ.get("INPUTS_REPLY")), Path.cwd(),
                                       keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")),
                                       fix_reply=boundary.value(os.environ.get("INPUTS_FIX_REPLY"))))
