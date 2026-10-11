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

start, error = None, ""
try:
    start = json.loads(boundary.resolve(json.loads(os.environ["INPUTS_START"])).read_text(encoding="utf-8"))
except (KeyError, OSError, TypeError, ValueError, AttributeError) as e:
    error = f"始めの記録が読めない（{type(e).__name__}: {e}）"
boundary.returns(ja.intake(start, error, boundary.resolve(boundary.pointer(ja.JUDGE_DIR)),
                           boundary.resolve(boundary.pointer(ja.REJUDGE_DIR)), Path.cwd(), os.environ["INPUTS_OBJECTION"]))
