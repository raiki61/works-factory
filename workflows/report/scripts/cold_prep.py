"""書き手の返答の頭（平易な冒頭と人が決めること）と、その後ろに付く語の定義の節を、初見の読み手に貼る本文にして返す。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import runreport  # noqa: E402

if __name__ == "__main__":
    boundary.returns({"body": runreport.cold_body(os.environ.get("INPUTS_WRITER", ""))})
