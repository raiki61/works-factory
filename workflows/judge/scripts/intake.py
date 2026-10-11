"""入口の節: 始めの記録を開き、依頼の行を型に通し、判定の道か再審の道かと段の切り替えを返す（lib/judge_accept.intake）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402


def pointed(raw: str):
    """指し札の JSON の字の先の JSON（null の字は None）"""
    ptr = json.loads(raw)
    return None if ptr is None else json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))


start, prior, error = None, [], ""
try:
    start = pointed(os.environ["INPUTS_START"])
    prior = pointed(os.environ.get("INPUTS_PRIOR_FAILURES", "null")) or []
except (KeyError, OSError, TypeError, ValueError, AttributeError) as e:
    error = f"始めの記録か前の失敗の行が読めない（{type(e).__name__}: {e}）"
boundary.returns(ja.intake(start, error, boundary.resolve(boundary.pointer(ja.JUDGE_DIR)),
                           boundary.resolve(boundary.pointer(ja.REJUDGE_DIR)), Path.cwd(),
                           os.environ.get("INPUTS_OBJECTION", ""), prior))
