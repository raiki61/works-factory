# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node orders（組の形。振り分けの loop の後・型の輪の前。今の tdd-go に替わる）: 型ごとの注文を書き、型ごとの輪を回すかの真偽だけを
返す（src/orders.compute）。{tdd, writer, stop, reason}。stop は組を止める（起動スクリプトが書き直しても壊れたまま）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import oneline  # noqa: E402

from src import orders  # noqa: E402

if __name__ == "__main__":
    try:
        result = orders.compute(ports.place(), Path.cwd())
    except Exception as e:
        print(f"orders: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
