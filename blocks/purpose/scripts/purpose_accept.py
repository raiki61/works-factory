# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の役の返答を受け付ける: 固めた目的を書き直さない・作業ツリーを変えていない・source_files が版に在る正規形のファイル。
通れば purpose.json と purpose-means.json を書く。3 回目の却下で done。諦めても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.take(ports.place(), os.environ.get("INPUTS_REPLY", ""), Path.cwd())


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）"})
