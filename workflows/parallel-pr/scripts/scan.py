# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""並行 PR の入口: port を読み、place のこの block のファイルを名で消し、役の前の作業ツリーの写しを取り、機械の道で交差を数える。
返り {go_role, reason}。port が読めない時は go_role: false と訳（出口が status: failed にする）。機械の道が落ちたら役に任せる"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import requestrows  # noqa: E402


def compute():
    from src import files, scan
    name = "request"   # 読めない入力を名指す（読む順に置き換える）
    try:
        values = {"request": requestrows.findings(os.environ.get("INPUTS_REQUEST"))}
        name = "base"
        values["base"] = ports.text(os.environ.get("INPUTS_BASE")).strip()
        name = "changed"
        values["changed"] = ports.json(os.environ.get("INPUTS_CHANGED"), "changed.schema.json")
    except ValueError as e:
        return scan.refuse(ports.place(), f"入力 {name} が読めない: {e}")
    return scan.scan(ports.place(), Path.cwd(), **values)


ports.run(compute, lambda why: {"go_role": False, "reason": f"入口が落ちた（{why}）"})
