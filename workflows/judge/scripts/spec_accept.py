# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の役（書く・審査・直す）の返答を受け付け、通れば J/spec-<役>.json に置く。審査が穴を挙げたら直す輪を回す印を返す
（lib/judge_accept.spec_take）。拒まれた後の出し直しの役の返答 fix_reply（直す欄だけ）は、前の答えの控えと欄ごとに合わせてから
照らす（rolekit.resubmitted に rolekit.merge_fields）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
role = os.environ.get("INPUTS_ROLE", "")
KEYS = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
name = ja.SPEC_ROLES.get(role, "spec-" + "".join(c if c.isalnum() else "-" for c in role)[:40])
got = rolekit.resubmitted(jdir, name, boundary.value(os.environ.get("INPUTS_REPLY")), boundary.value(os.environ.get("INPUTS_FIX_REPLY")),
                          rolekit.merge_fields)
out = rolekit.accept_parsed(jdir, name, got, lambda reply: ja.spec_take(jdir, role, reply, Path.cwd(), keys=KEYS))
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"], "revise": bool(out.get("revise"))})
