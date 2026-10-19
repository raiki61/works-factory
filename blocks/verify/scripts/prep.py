# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の裏取りの支度: 判定を読み、下請けのファイル・束ね役の指示・番号の控え・作業ツリーの写しを place に書く。開いた単位が 2 つ未満なら回さない。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.prep(ports.place(), judgment=os.environ.get("INPUTS_JUDGMENT"), lang=os.environ.get("INPUTS_LANG"))


def fallback(why: str) -> dict:
    return {"go": False, "prompt": "", "reason": f"判定の裏取りの支度が落ちた（{why}）"}


ports.run(compute, fallback)
