# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の返答と初見の読み手の判定を受け付ける（輪の until_bash が done を読む）。受け取った物は run の置き場の report/ に書く。
拒否の訳のファイル reason_file と、前の答えの控え prev_file（まだ諦めていない拒否の回だけ。無ければ空。先は rolekit の前の答えの控え
candidate-report.json）は、機械の事実のファイル（facts の facts_file）と同じく run の置き場からの相対で返す。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import runreport  # noqa: E402


def out_dir() -> Path:
    """報告の置き場（run の置き場の runreport.OUT_DIR）"""
    return Path(os.environ["ARTIFACTS_DIR"]) / runreport.OUT_DIR


if __name__ == "__main__":
    got = runreport.accept(os.environ.get("INPUTS_REPLY", ""), os.environ.get("INPUTS_COLD", ""), out_dir=out_dir())
    boundary.returns({**got, "reason_file": boundary.rel_of(got["reason_file"]) if got["reason_file"] else "",
                      "prev_file": boundary.rel_of(got["prev_file"]) if got["prev_file"] else ""})
