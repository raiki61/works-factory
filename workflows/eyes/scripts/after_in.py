# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し after-in（docs/design/judge-eyes.md の 2.3 の 2）: 直した後の構造の実測の控えの pointer を r1・r3・r4 の port after へ運ぶ。
実測が返らなかった・控えが無い run は null（目は「測っていない」と読む）。落ちない。

入力（with:）: structure_after_out（structure の返りまるごと。読む欄は after だけ）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

STRUCTURE = ("after",)   # structure の返りのうち読む欄


def compute():
    got = ports.picked(os.environ.get("INPUTS_STRUCTURE_AFTER_OUT"), STRUCTURE)
    after = got["after"] if got is not None else None
    return {"after": after if isinstance(after, dict) else None, "why": ""}


ports.run(compute, lambda why: {"after": None, "why": why})
