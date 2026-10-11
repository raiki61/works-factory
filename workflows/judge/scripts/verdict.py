"""返す節: 判定か再審の結果を、線との約束（docs/design.md の「judge の返り」）の欄で返す（lib/judge_accept.verdict）。
落ちない: 中の誤りは標準エラーに書き、ready: false と止めの理由を返す（線は落ちた返す節の先へ進めない）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
rdir = boundary.resolve(boundary.pointer(ja.REJUDGE_DIR))
objection = os.environ.get("INPUTS_OBJECTION", "")
try:
    out = ja.verdict(jdir, rdir, Path.cwd(), objection, boundary.pointer)
except Exception as e:  # noqa: BLE001  返す節は落ちない
    print(f"verdict: {type(e).__name__}: {e}", file=sys.stderr)
    out = ja.verdict_fallback(jdir, rdir, objection, boundary.pointer)
boundary.returns(out)
