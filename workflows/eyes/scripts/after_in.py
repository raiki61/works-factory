# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返し after-in（docs/design/judge-eyes.md の 2.3 の 2）: 直した後の構造の実測の控えの pointer を r1・r3・r4 の port after へ運ぶ。
実測が返らなかった・控えが無い run は null（目は「測っていない」と読む）。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    raw = os.environ.get("INPUTS_STRUCTURE_AFTER_OUT")
    whole = ports.picked(raw, ("got", "why"))
    got = whole["got"] if whole is not None else None
    after = got.get("after") if isinstance(got, dict) else None
    return {"after": after if isinstance(after, dict) else None, "why": ""}


ports.run(compute, lambda why: {"after": None, "why": why})
