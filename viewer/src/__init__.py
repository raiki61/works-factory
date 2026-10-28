"""見る道具の読む部品。lib/ のモジュール（runlog など）は lib/ の中で名だけで互いを import するので、lib/ を sys.path の後ろに足す
（頭に入れると lib/tests が根の tests を隠す。lib/AGENTS.md と同じ足し方）"""
import sys
from pathlib import Path

_LIB = str(Path(__file__).resolve().parents[2] / "lib")
if _LIB not in sys.path:
    sys.path.append(_LIB)
