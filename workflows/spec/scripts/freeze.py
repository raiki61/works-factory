# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の承認ノードの答えを受け、通す語なら受け入れ条件の run を走らせて仕様を place の spec.json に固め、足した依頼の行を
added-rows.json に書く。止める語なら human:spec-gate か request:spec-gate で止める。固められない誤りは works:spec の止めにする"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import files, steps
    return steps.freeze_answer(ports.place(), Path.cwd(), files.value(os.environ.get("INPUTS_ANSWER")),
                               ports.text(os.environ.get("INPUTS_USER_ENV_DIR")))


ports.run(compute, lambda why: {"go": False, "reason": f"仕様を固められない（{why}）"})
