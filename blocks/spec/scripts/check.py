# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""固めた仕様の受け入れ条件のテストが承認の版から変わったかを照らす。仕様が渡されない・読めない・照らしが落ちた時は、黙って 0 件にせず
照らせなかったと言う（問い 1 行と unchecked: true）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import check, steps
    path = ports.file(os.environ.get("INPUTS_SPEC"))
    return steps.no_spec() if path is None else check.questions(path, Path.cwd())


def fallback(why: str) -> dict:
    from src import steps
    return steps.check_failed(why)


ports.run(compute, fallback)
