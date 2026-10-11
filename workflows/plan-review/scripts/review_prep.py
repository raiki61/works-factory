"""事前審査の支度（boardview.review_material）: 材料のファイル pass-<k>/prompt.md と役を起こす前の作業ツリーの姿を置く"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402

COMMAND = Path(__file__).resolve().parents[1] / "commands" / "plan-review.md"

path = boardview.review_material(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER, Path.cwd(),
                                 COMMAND.read_text(encoding="utf-8"), boundary.lib_root() / boardview.REVIEW_MD)
boundary.returns({"prompt_file": str(path)})
