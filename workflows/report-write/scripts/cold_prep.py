# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""人に向けた報告の頭と同じ物（機械の報告の冒頭・書き手の返答の頭・その後ろに付く語の定義の節を語の表で言い換えた物）を、
初見の読み手に貼る本文にして返す。機械の報告は入力 facts_file（run の置き場からの相対のパス）から読む。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import runreport  # noqa: E402

if __name__ == "__main__":
    boundary.returns({"body": runreport.cold_body(os.environ.get("INPUTS_WRITER", ""),
                                                  machine=Path(os.environ["ARTIFACTS_DIR"]) / os.environ.get("INPUTS_FACTS_FILE", ""))})
