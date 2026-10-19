# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R1 の入口: port を読み、この block のファイルを名で消して累積差分を取り、intake.json を書く。読めない port は due: false と訳。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    raw = {"base": os.environ.get("INPUTS_BASE"), "purpose": os.environ.get("INPUTS_PURPOSE"), "units": os.environ.get("INPUTS_UNITS"),
           "judgment": os.environ.get("INPUTS_JUDGMENT"), "fixes": os.environ.get("INPUTS_FIXES"),
           "x_scalars": os.environ.get("INPUTS_X_SCALARS"), "green": os.environ.get("INPUTS_GREEN"),
           "checks": os.environ.get("INPUTS_CHECKS"), "after": os.environ.get("INPUTS_AFTER"), "review": os.environ.get("INPUTS_REVIEW"),
           "policy": os.environ.get("INPUTS_POLICY"), "lang": os.environ.get("INPUTS_LANG")}
    return steps.intake(ports.place(), Path.cwd(), raw, (ports.RUNTIME_COPY_PREFIX,))


ports.run(compute, lambda why: {"due": False, "reason": f"R1 の入口が落ちた（{why}）"})
