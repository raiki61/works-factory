# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立設計の受け付け（boardview.check_design。役の型は差し込みの頭が置いた材料から読む）。拒みは控えに積み、3 回目で done・give_up
（諦めても止めない）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402

boundary.returns(boardview.check_design(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER, os.environ["INPUTS_REPLY"],
                                        Path.cwd()))
