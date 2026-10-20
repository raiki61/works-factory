# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造の目の入口: port を読み、place のこの block のファイルを消して、書いた意図を探し、before なら単位を測り（段 A）、after なら
差分を測る（段 B）。中の誤りは控えの status: failed に残し、構造の目を起こさない（落ちない）。返り {eye, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import survey
    return survey.run(ports.place(), mode=os.environ.get("INPUTS_MODE"), units=os.environ.get("INPUTS_UNITS"),
                      intent_paths=os.environ.get("INPUTS_INTENT"), policy=os.environ.get("INPUTS_POLICY"),
                      base=os.environ.get("INPUTS_BASE"), plan=os.environ.get("INPUTS_PLAN"))


ports.run(compute, lambda why: {"eye": False, "reason": f"実測の支度が落ちた（{why}）"})
