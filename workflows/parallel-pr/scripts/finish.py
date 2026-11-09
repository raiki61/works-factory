# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""並行 PR の出口: place の控えから block の返りを組む。どの段が落ちても落ちない（落とし穴 K1・K13）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import finish
    return finish.build(ports.place())


def fallback(why):
    from src import fallback as fell   # 標準ライブラリだけ（lib を読めない時も返す。落とし穴 K1）
    return fell.fallen(why)


ports.run(compute, fallback)
