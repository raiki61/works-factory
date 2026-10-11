"""書き手の返答と初見の読み手の判定を受け付ける（輪の until_bash が done を読む）。受け取った物は run の置き場の report/ に書く。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import runreport  # noqa: E402
from place import out_dir  # noqa: E402

if __name__ == "__main__":
    boundary.returns(runreport.accept(os.environ.get("INPUTS_REPLY", ""), os.environ.get("INPUTS_COLD", ""),
                                      out_dir=out_dir()))
