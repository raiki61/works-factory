# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の材料を plan/r<k>/brief-<n>.md に組み（lib/planfile.write_brief）、役を起こす前の作業ツリーの姿を tree.json に置き直す
（planfile.snap_tree。受け付けが比べる）。返り {brief, attempt}

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


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir, round_dir, repo = art / planfile.PLAN_DIR, art / os.environ["INPUTS_DIR"], Path.cwd()
    rnd = planfile.read_round(round_dir)
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.pointed)
    start = start if isinstance(start, dict) else {}
    judgment_file, _ = planfile.pointed(os.environ["INPUTS_JUDGMENT"], boundary.pointed)
    judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.pointed)
    units = planfile.units_of(os.environ["INPUTS_UNITS"])
    world, bad_world = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.pointed)
    spec, bad_spec = planfile.read_pointed(os.environ["INPUTS_SPEC"], boundary.pointed, text=True)
    conflicts, bad_conflicts = planfile.read_pointed(os.environ["INPUTS_CONFLICTS"], boundary.pointed)
    prior, bad_prior = planfile.read_pointed(os.environ["INPUTS_PRIOR_FAILURES"], boundary.pointed)
    unread = [f"{name}: {why}" for name, why in (("world", bad_world), ("spec", bad_spec), ("conflicts", bad_conflicts),
                                                 ("prior_failures", bad_prior)) if why]
    keys = set(planfile.slots(judgment)) if isinstance(judgment, dict) else None
    path, n = planfile.write_brief(
        round_dir, plan_dir, mode=rnd["mode"], judgment=judgment, judgment_dir=judgment_file.parent if judgment_file else None,
        units=units, structure_dir_=plan_dir / rnd["structure"], world_rows=world, spec=spec,
        repo=repo, base_rev=start.get("base_rev") or "", review_md=str(boundary.lib_root() / "REVIEW.md"),
        lang_line=rolekit.lang_line(start), lib_docs=planfile.lib_section(plan_dir, repo, str(judgment_file or ""), keys,
                                                                     shared=boundary.shared_cache()),
        conflicts=conflicts, policy_md=policy.frozen_copy(start), prior_failures=prior, unread=unread)
    planfile.snap_tree(round_dir / planfile.TREE_FILE, repo)
    boundary.returns({"brief": str(path), "attempt": n})


if __name__ == "__main__":
    main()
