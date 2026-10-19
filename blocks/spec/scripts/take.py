# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役（書く・審査・直す）の返答を受け付け、通れば place の spec-<役>.json に置く。審査が穴を挙げたら直す輪を回す印を返す。拒まれた後の
出し直しの役の返答 fix_reply（直す欄だけ）は、前の答えの控えと欄ごとに合わせてから照らす。3 回目の却下で done。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import files, steps
    return steps.take_reply(ports.place(), ports.choice(os.environ.get("INPUTS_ROLE"), tuple(files.ROLES)),
                            ports.flag(os.environ.get("INPUTS_STATUS_GUARDED")), files.value(os.environ.get("INPUTS_REPLY")),
                            files.value(os.environ.get("INPUTS_FIX_REPLY")), Path.cwd())


ports.run(compute, lambda why: {"ok": False, "done": True, "reason": f"受け付けが落ちた（{why}）", "revise": False})
