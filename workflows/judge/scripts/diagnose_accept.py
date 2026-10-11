"""判定役の返答を受け付ける（lib/judge_accept.accept）。拒否は数え、3 回目で done。諦めた時は止めの控えを置く"""
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
out = ja.accept(jdir, os.environ.get("INPUTS_REPLY", ""), Path.cwd())
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
