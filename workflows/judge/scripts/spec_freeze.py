# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の関所の答えを受け、通す語なら受け入れ条件を走らせて仕様を J/spec.json に固め、依頼の行に積む。止める語なら
human:spec-gate か request:spec-gate で止める（lib/judge_accept.spec_answer）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
try:
    got = ja.spec_answer(jdir, Path.cwd(), boundary.value(os.environ.get("INPUTS_ANSWER")))
except Exception as e:  # 固められない誤りは仕様の止めにする
    why = f"仕様を固められない（{type(e).__name__}: {e}）"
    ja.write_stop(jdir, ja.SPEC_STOP, why)
    got = {"go": False, "reason": why}
boundary.returns({"go": got["go"], "reason": got["reason"]})
