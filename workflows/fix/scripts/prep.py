# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node prep（全体の形）: intake.json の port の値を place に写し、git が無視するファイルを控え、始めの木を取り、組を作る
（src/board.prep。今の prep と同じ順）。書き込みの記録を空で作る（writelog.open_here）。
返り {groups, count, par, start_tree, out_dir}。入力が読めない・git が効かない: 標準エラーに 1 行で 1"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import writelog  # noqa: E402

from src import board, intake  # noqa: E402


def main() -> dict:
    writelog.open_here()
    place = ports.place()
    return board.prep(place, Path.cwd(), intake.load(place))


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・置き場が無い・git が効かない）
        print(f"prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
