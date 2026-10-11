"""言い直す役の返答を受け付ける: 依頼の全部の行に 1 つ・対象の識別子を持たない・検索語が在る（lib/judge_accept.world_accept）。3 回目の拒否で done。諦めても run は止めない"""
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
out = ja.world_accept(jdir, "world-classes", os.environ.get("INPUTS_REPLY", ""))
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
