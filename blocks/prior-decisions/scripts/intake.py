# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""先行議論の突合の入口: port を読み、対象差分を取り、回すかを決め（いつも回す）、作業ツリーを写して intake.json を書く。
返り {due, reason}。port が読めない・差分が取れない時は due: false と訳（出口が status: failed にする）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import materialkit  # noqa: E402  （lib/。ports を読むと lib/ が sys.path に入る）
from src import viewpoint  # noqa: E402

values, unreadable = {}, []
for name, read in (("base", lambda: ports.text(os.environ.get("INPUTS_BASE"))),
                   ("request", lambda: ports.json(os.environ.get("INPUTS_REQUEST"), "shared:request.schema.json")),
                   ("entry", lambda: ports.text(os.environ.get("INPUTS_ENTRY"))),
                   ("lang", lambda: ports.text(os.environ.get("INPUTS_LANG")))):
    try:
        values[name] = read()
    except ValueError as e:
        values[name] = None
        unreadable.append(f"{name}: {e}")
ports.returns(materialkit.intake(viewpoint, ports.place(), Path.cwd(), values, "／".join(unreadable)))
