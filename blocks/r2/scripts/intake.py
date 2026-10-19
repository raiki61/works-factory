# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R2 の入口: port を読み、この block のファイルを名で消して累積差分を取り、独立設計の返答から比べの道と検算の道のどちらを起こすかを
決めて intake.json を書く。読めない port は両方偽と訳。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    raw = {"base": os.environ.get("INPUTS_BASE"), "head": os.environ.get("INPUTS_HEAD"), "base_label": os.environ.get("INPUTS_BASE_LABEL"),
           "purpose": os.environ.get("INPUTS_PURPOSE"), "design": os.environ.get("INPUTS_DESIGN"),
           "design_reason": os.environ.get("INPUTS_DESIGN_REASON"), "design_premises": os.environ.get("INPUTS_DESIGN_PREMISES"),
           "answers": os.environ.get("INPUTS_ANSWERS"), "request": os.environ.get("INPUTS_REQUEST"),
           "changed": os.environ.get("INPUTS_CHANGED"), "constraints": os.environ.get("INPUTS_CONSTRAINTS"),
           "test_outcomes": os.environ.get("INPUTS_TEST_OUTCOMES"), "tdd": os.environ.get("INPUTS_TDD"),
           "lang": os.environ.get("INPUTS_LANG")}
    return steps.intake(ports.place(), Path.cwd(), raw, (ports.RUNTIME_COPY_PREFIX,))


ports.run(compute, lambda why: {"compare": False, "premise": False, "reason": f"R2 の入口が落ちた（{why}）"})
