# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の返答を受け付ける（lib/eyeverdict.r4_accept）。1 回目の返答と出し直しは、R4 の役の組（reply・fix_reply）か、まとめた役
eyes-one の組（one_reply・one_fix_reply。R4 の欄に R3 の欄を足した返り）のどちらか 1 組だけが起きる。拒否は数え、3 回目で
done。返りの reply は輪の外の r4-scope-verdict が書く。
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


def first(*names):
    """名の順で最初の起きた役の返答（起きなかった役は null）"""
    return next((v for v in (boundary.value(os.environ.get(n)) for n in names) if v is not None), None)


eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
passed = eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), boundary.parsed(os.environ["INPUTS_ANSWERS"]))
got = rolekit.resubmitted(eyes, eyeverdict.R4_NODE, first("INPUTS_REPLY", "INPUTS_ONE_REPLY"),
                          first("INPUTS_FIX_REPLY", "INPUTS_ONE_FIX_REPLY"), rolekit.merge_fields)
boundary.returns(eyeverdict.r4_accept(eyes, got, passed))
