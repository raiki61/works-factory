# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""一言の向きの判定の支度: 承認ノードの答え・見せた項目・承認に掛けた計画の行を読み、役を起こすか（due）と、役の指示を prompts/direction.md から
組む。決めの語が通す語で一言が空でない時だけ起こす。一言が空か止める語なら due 偽・reason 空（要らない）。入力が読めなければ due 偽で
読めなかった入力を名指す訳を返す（出口が failed にする）。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
import prompt  # noqa: E402

NO_ASKED = "(no item was shown)"


def compute():
    from src import direction
    place = ports.place()
    for name in direction.OWN_FILES:   # 自分の名のファイルだけ消す（前の周の返答の控えを今の判定と読み違えない。ほかの物は消さない）
        (place / name).unlink(missing_ok=True)
    got = direction.due(os.environ.get("INPUTS_ANSWER"), os.environ.get("INPUTS_ASKED"), os.environ.get("INPUTS_PLAN"))
    if not got["due"]:
        return not_due(got["reason"])
    lang = ports.text(os.environ.get("INPUTS_LANG")).strip()
    values = {"note": got["note"], "asked": "\n".join(f"- {row}" for row in got["asked"]) or NO_ASKED, "plan": "\n".join(got["plan"]),
              "lang": lang}
    return {"due": True, "prompt": prompt.emit("direction", values, {"lang_given": bool(lang)}, prompt.round_of("direction"))["prompt"],
            "reason": ""}


def not_due(why: str) -> dict:
    return {"due": False, "prompt": "", "reason": why}


ports.run(compute, not_due)
