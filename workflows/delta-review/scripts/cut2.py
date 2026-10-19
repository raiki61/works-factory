# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""2 回目の審査の支度: 1 回目の手直しが fixed と答えた穴が在る時だけ、手直しだけの差分を切り、材料と作業ツリーの写しを置く。返り {due, reason}。落ちない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.run(lambda: steps.cut2(ports.place(), Path.cwd()), lambda why: {"due": False, "reason": f"2 回目の差分を切れなかった（{why}）"})
