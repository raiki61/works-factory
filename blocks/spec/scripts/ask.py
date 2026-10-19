# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の承認ノードに見せる文を組む。役の輪が諦めた・仕様が揃わない時は承認ノードを開かずに止める"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.ask(ports.place(), Path.cwd())


ports.run(compute, lambda why: {"ask": False, "message": ""})
