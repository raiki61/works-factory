# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定役の返答を受け付ける: 作業ツリー・class_query の例と件数・先行例の出どころ・台帳の語彙・目的の外の所見・依頼の答えと作り直しの行の結び・
記録された方針の名指し。通れば judgment.json を書く。3 回目の却下で done。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import inputs
    return inputs.accept_diagnose(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd())


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})
