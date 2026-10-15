# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の返答を受け付ける（lib/eyeverdict.r4_accept）。拒否は数え、3 回目で done。返りの reply は輪の外の r4-scope-verdict が書く。
拒まれた後の出し直しの役の返答 fix_reply（直す欄だけ）は、前の答えの控えと欄ごとに合わせてから照らす（rolekit.resubmitted に
rolekit.merge_fields。返りの reply は合わせた答え）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eyeverdict  # noqa: E402
import rolekit  # noqa: E402

eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
passed = eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), boundary.parsed(os.environ["INPUTS_ANSWERS"]))
got = rolekit.resubmitted(eyes, eyeverdict.R4_NODE, boundary.value(os.environ.get("INPUTS_REPLY")),
                          boundary.value(os.environ.get("INPUTS_FIX_REPLY")), rolekit.merge_fields)
boundary.returns(eyeverdict.r4_accept(eyes, got, passed))
