# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の裏取りの支度（stage prep。lib/judge_accept.prep_on）とまとめ（stage merge。lib/judge_accept.merge_on）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import judge_accept as ja  # noqa: E402

stage = os.environ.get("INPUTS_STAGE", "")
objection = os.environ.get("INPUTS_OBJECTION", "")
if stage not in ("prep", "merge"):
    sys.exit(f"stage は prep か merge（{stage!r}）")
if objection.strip():   # 再審の道: 判定の道の裏取りは走らせず、置き場に触らない
    boundary.returns({"go": False, "prompt_file": "", "reason": "再審の道（入力 objection が空でない）"} if stage == "prep"
                     else {"ok": True, "reason": "再審の道（入力 objection が空でない）"})
    sys.exit(0)
jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
if stage == "prep":
    try:
        intake = ja.read_json(jdir / ja.INTAKE_FILE, {}) or {}
        judgment = ja.read_json(jdir / ja.JUDGMENT_FILE)
        out = ja.prep_on(jdir, judgment, Path.cwd(), intake.get("verify") is True)
    except Exception as e:   # 支度が落ちれば裏取りを回さない（判定は消さない）
        reason = f"判定の裏取りの支度の中で例外（{type(e).__name__}: {e}）"
        ja.verify_not_run(jdir, reason)
        out = {"go": False, "prompt_file": "", "reason": reason}
    boundary.returns(out)
else:
    try:
        out = ja.merge_on(jdir, Path.cwd(), keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))
    except Exception as e:
        reason = f"判定の裏取りのまとめの中で例外（{type(e).__name__}: {e}）"
        ja.verify_not_run(jdir, reason)
        out = {"ok": False, "reason": reason}
    boundary.returns(out)
