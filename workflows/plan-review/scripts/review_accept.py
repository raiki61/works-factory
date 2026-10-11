# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の受け付け（boardview.take_review）。拒みは控えに積み、3 回目で done・give_up"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402

boundary.returns(boardview.take_review(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER, os.environ["INPUTS_REPLY"],
                                       Path.cwd()))
