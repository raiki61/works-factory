# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の入口: port を読んで mode を決め、write なら place のこの block のファイルを消して依頼の行を request.json に書く。port が読めなくても
落ちず、go: false と理由を返す（write の止めの控えにも書く）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(ports.place(), mode=os.environ.get("INPUTS_MODE"), request=os.environ.get("INPUTS_REQUEST"),
                        pr_text=os.environ.get("INPUTS_PR_TEXT"), lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"mode": "", "go": False, "reason": f"入口が落ちた（{why}）"})
