# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の材料を plan/r<k>/brief-<n>.md に組み（lib/planfile.write_brief）、役を起こす前の作業ツリーの姿を tree.json に置き直す
（planfile.snap_tree。受け付けが比べる）。返り {brief, attempt, resubmit}

この輪の実行の中で前の周が拒まれ（with: の prev が前の周の受け付けの ok の false。拒否の文でなく真偽を結ぶのは、Archon が
with: に貼った値の中の節の参照の字をもう 1 度置き換えるため。元の裁定 R44）、受け付けが合わせた答えの控えが在れば
（rolekit.resubmitting）、材料の代わりに出し直しの役の短い指示書を書き（rolekit.write_resubmit。名を周の材料と同じ brief-<n>.md に
するのは、読んだ証拠 collect_reads がこの周の役の会話として拾うため）、resubmit: true で出し直しの役（1 回目の役の会話の続き）を
起こさせる

ライブラリの文書の run をまたぐ控えは、境の控えの根（boundary.shared_cache）に置く"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402
import policy  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir, round_dir, repo = art / planfile.PLAN_DIR, art / os.environ["INPUTS_DIR"], Path.cwd()
    rnd = planfile.read_round(round_dir)
    if rolekit.resubmitting(round_dir, planfile.ROLE, boundary.value(os.environ.get("INPUTS_PREV"))):
        rules = planfile.REPLAN_RESUBMIT_RULES if rnd["mode"] == "replan" else planfile.RESUBMIT_RULES
        path, n = rolekit.write_resubmit(round_dir, planfile.ROLE, planfile.BRIEF_FILE, rules)
        planfile.snap_tree(round_dir / planfile.TREE_FILE, repo)
        boundary.returns({"brief": str(path), "attempt": n, "resubmit": True})
        return
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.pointed)
    start = start if isinstance(start, dict) else {}
    judgment_file, _ = planfile.pointed(os.environ["INPUTS_JUDGMENT"], boundary.pointed)
    judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.pointed,
                                       ties=os.environ.get("INPUTS_ANSWER_TIES", ""), materials=os.environ.get("INPUTS_MATERIALS", ""))
    units = planfile.units_of(os.environ["INPUTS_UNITS"])
    world, bad_world = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.pointed)
    spec, bad_spec = planfile.read_pointed(os.environ["INPUTS_SPEC"], boundary.pointed, text=True)
    conflicts, bad_conflicts = planfile.read_pointed(os.environ["INPUTS_CONFLICTS"], boundary.pointed)
    prior, bad_prior = planfile.read_pointed(os.environ["INPUTS_PRIOR_FAILURES"], boundary.pointed)
    excluded, bad_excluded = planfile.pointed(os.environ.get("INPUTS_PR_EXCLUDED", ""), boundary.pointed)
    verify, bad_verify = planfile.pointed(os.environ.get("INPUTS_VERIFY", ""), boundary.pointed)
    depth_record, bad_depth = planfile.pointed(os.environ.get("INPUTS_DEPTH_RECORD", ""), boundary.pointed)
    decisions, bad_decisions = planfile.pointed(os.environ.get("INPUTS_DECISIONS", ""), boundary.pointed)
    structure, bad_structure = planfile.pointed(os.environ["INPUTS_STRUCTURE"], boundary.pointed)
    bad_ties = planfile.pointed(os.environ.get("INPUTS_ANSWER_TIES", ""), boundary.pointed)[1]
    bad_materials = planfile.pointed(os.environ.get("INPUTS_MATERIALS", ""), boundary.pointed)[1]
    unread = [f"{name}: {why}" for name, why in (("world", bad_world), ("spec", bad_spec), ("conflicts", bad_conflicts),
                                                 ("prior_failures", bad_prior), ("pr_excluded", bad_excluded),
                                                 ("verify", bad_verify), ("depth_record", bad_depth), ("decisions", bad_decisions),
                                                 ("answer_ties", bad_ties), ("materials", bad_materials),
                                                 ("structure", bad_structure)) if why]
    keys = set(planfile.slots(judgment)) if isinstance(judgment, dict) else None
    path, n = planfile.write_brief(
        round_dir, plan_dir, mode=rnd["mode"], judgment=judgment, judgment_file=judgment_file,
        units=units, structure=structure, world_rows=world, spec=spec,
        repo=repo, review_rev=startrec.read_rev(start), base=startrec.diff_base(start),
        review_md=str(boundary.lib_root() / "REVIEW.md"),
        lang_line=rolekit.lang_line(start), lib_docs=planfile.lib_section(plan_dir, repo, str(judgment_file or ""), keys,
                                                                     shared=boundary.shared_cache()),
        conflicts=conflicts, policy_md=policy.frozen_copy(start), prior_failures=prior, unread=unread,
        recorded=policy.recorded_text(start, decisions), excluded_file=excluded, verify_file=verify, depth_file=depth_record)
    planfile.snap_tree(round_dir / planfile.TREE_FILE, repo)
    boundary.returns({"brief": str(path), "attempt": n, "resubmit": False})


if __name__ == "__main__":
    main()
