# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の裏取りの支度（stage prep。lib/judge_accept.prep_on）とまとめ（stage merge。lib/judge_accept.merge_on）。
支度は役の文の頭に足す言語の 1 行（始めの記録の lang から rolekit.lang_line）も lang_line で返す。裏取りを回すかは、始めの記録の機能の
切り替え（名指し）と頭の深さの控え judge/depth-head.json の段の足しから entry.switch が決める"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import depth  # noqa: E402
import entry  # noqa: E402
import headdepth  # noqa: E402
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402

stage = os.environ.get("INPUTS_STAGE", "")
if stage not in ("prep", "merge"):
    sys.exit(f"stage は prep か merge（{stage!r}）")
lang = {"lang_line": rolekit.pointed_lang_line(os.environ.get("INPUTS_START"), boundary.pointed)}
jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
if stage == "prep":
    try:
        start_file = boundary.pointed(os.environ.get("INPUTS_START"))
        start = startrec.load(start_file) if start_file else {}
        judgment = ja.read_json(jdir / ja.JUDGMENT_FILE)
        adds = depth.tier_adds(headdepth.read(jdir)["depth"])
        out = ja.prep_on(jdir, judgment, Path.cwd(), entry.switch(start, ja.VERIFY_FEATURE, adds) == entry.SWITCH_ON)
    except Exception as e:   # 支度が落ちれば裏取りを回さない（判定は消さない）
        reason = f"判定の裏取りの支度の中で例外（{type(e).__name__}: {e}）"
        ja.verify_not_run(jdir, reason)
        out = {"go": False, "prompt_file": "", "reason": reason}
    boundary.returns({**out, **lang})
else:
    try:
        out = ja.merge_on(jdir, Path.cwd(), keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))
    except Exception as e:
        reason = f"判定の裏取りのまとめの中で例外（{type(e).__name__}: {e}）"
        ja.verify_not_run(jdir, reason)
        out = {"ok": False, "reason": reason}
    boundary.returns(out)
