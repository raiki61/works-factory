# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の支度（boardview.review_material）: 材料のファイル pass-<k>/prompt.md と役を起こす前の作業ツリーの姿を置く。返り {prompt_file, resubmit}。
この輪の実行の中で前の周が拒まれ（with: の prev が前の周の受け付けの ok の false。拒否の文を with: に貼らないのは元の裁定 R44）、
受け付けが合わせた答えの控えが在れば、材料の代わりに出し直しの役の短い指示書を書き（boardview.review_resubmit）、resubmit: true で
出し直しの役（1 回目の役の会話の続き）を起こさせる。resume で輪が 1 周目から回り直した時は prev が空なので、1 回目の役が起きる。
ライブラリの文書の run をまたぐ控えは、境の控えの根（boundary.shared_cache）に置く"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402
import rolekit  # noqa: E402

COMMAND = Path(__file__).resolve().parents[1] / "commands" / "plan-review.md"

folder = Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER
pass_dir = boardview.pass_dir(folder, boardview.read_open(folder)["k"])
if boundary.value(os.environ.get("INPUTS_PREV")) is False and rolekit.candidate_path(pass_dir, boardview.REVIEW_NODE).is_file():
    boundary.returns({"prompt_file": str(boardview.review_resubmit(folder, Path.cwd())), "resubmit": True})
else:
    path = boardview.review_material(folder, Path.cwd(), COMMAND.read_text(encoding="utf-8"),
                                     boundary.lib_root() / boardview.REVIEW_MD, shared=boundary.shared_cache())
    boundary.returns({"prompt_file": str(path), "resubmit": False})
