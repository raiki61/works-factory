# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""一般の構造を描く目の返答を受け付ける。通れば general.json に行を書く。拒否は ok: false で、3 回目の拒否で done。落ちない。
返り {ok, done, give_up, reason, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import sketch
    try:
        reply = ports.parsed(os.environ.get("INPUTS_REPLY"))
    except ValueError:
        reply = None
    return sketch.general_accept(ports.place(), reply)


ports.run(compute, lambda why: {"ok": False, "done": True, "give_up": True, "reason": f"受け付けが落ちた（{why}）", "attempt": 0})
