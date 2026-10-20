# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""n 回目（INPUTS_N は 1 か 2）の審査が直す義務を出したかを決め、出していれば手直しの段の頭の木と材料を置く。返り {due, reason}。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

n = steps.round_input(os.environ.get("INPUTS_N"))
ports.run(lambda: steps.owed(ports.place(), n, Path.cwd()), lambda why: {"due": False, "reason": f"手直しの支度が落ちた（{why}）"})
