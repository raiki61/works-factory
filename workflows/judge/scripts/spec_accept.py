# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の役（書く・審査・直す）の返答を受け付け、通れば J/spec-<役>.json に置く。審査が穴を挙げたら直す輪を回す印を返す
（lib/judge_accept.spec_take）"""
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
role = os.environ.get("INPUTS_ROLE", "")
name = ja.SPEC_ROLES.get(role, "spec-" + "".join(c if c.isalnum() else "-" for c in role)[:40])
out = ja.accept_round(jdir, name, os.environ.get("INPUTS_REPLY", ""), lambda reply: ja.spec_take(jdir, role, reply, Path.cwd()))
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"], "revise": bool(out.get("revise"))})
