# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""run の頭の深さの入口: port を読み、事実を測って機械の止めを通し、標準（か止めの段）の控えを先に書く。place のこの block のファイルを
消して intake.json を書く。port が読めなくても落ちず、due: false と理由を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), request=os.environ.get("INPUTS_REQUEST"), has_checks=os.environ.get("INPUTS_HAS_CHECKS"),
                        thickness=os.environ.get("INPUTS_THICKNESS"), spec=os.environ.get("INPUTS_SPEC"),
                        design_only=os.environ.get("INPUTS_DESIGN_ONLY"), lang=os.environ.get("INPUTS_LANG"), repo=Path.cwd())


ports.run(compute, lambda why: {"due": False, "reason": f"run の頭の深さの支度が落ちた（{why}）"})
