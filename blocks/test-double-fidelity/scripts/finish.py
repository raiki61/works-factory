# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""代役の忠実性の出口: 素材の状態を material.json に書き、block の返り {ok, status, reason, material, report} を返す。
どの段が落ちても落ちない（落とし穴 K1・K13）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import viewpoint  # noqa: E402

ports.returns(materialkit.finish(viewpoint, ports.place(), ports.pointer))
