# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の材料を plan/r<k>/brief-<n>.md に組む（lib/planfile.write_brief）。返り {brief, attempt}

ライブラリの文書の run をまたぐ控えは、Archon が project ごとに渡す run をまたぐ置き場 STATE_DIR の下 works-factory/ に置く"""
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


def shared_cache() -> Path | None:
    state = os.environ.get("STATE_DIR")
    return Path(state) / "works-factory" if state else None


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir, round_dir, repo = art / planfile.PLAN_DIR, art / os.environ["INPUTS_DIR"], Path.cwd()
    rnd = planfile.read_round(round_dir)
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    start = start if isinstance(start, dict) else {}
    judgment_file, _ = planfile.pointed(os.environ["INPUTS_JUDGMENT"], boundary.resolve)
    judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.resolve)
    units = planfile.units_of(os.environ["INPUTS_UNITS"])
    world, bad_world = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.resolve)
    spec, bad_spec = planfile.read_pointed(os.environ["INPUTS_SPEC"], boundary.resolve, text=True)
    conflicts, bad_conflicts = planfile.read_pointed(os.environ["INPUTS_CONFLICTS"], boundary.resolve)
    prior, bad_prior = planfile.read_pointed(os.environ["INPUTS_PRIOR_FAILURES"], boundary.resolve)
    unread = [f"{name}: {why}" for name, why in (("world", bad_world), ("spec", bad_spec), ("conflicts", bad_conflicts),
                                                 ("prior_failures", bad_prior)) if why]
    keys = set(planfile.slots(judgment)) if isinstance(judgment, dict) else None
    path, n = planfile.write_brief(
        round_dir, plan_dir, mode=rnd["mode"], judgment=judgment, judgment_dir=judgment_file.parent if judgment_file else None,
        units=units, structure_dir_=plan_dir / rnd["structure"], world_rows=world, spec=spec,
        repo=repo, base_rev=start.get("base_rev") or "", review_md=str(boundary.lib_root() / "REVIEW.md"),
        lang_line=rolekit.lang_line(start), lib_docs=planfile.lib_section(plan_dir, repo, str(judgment_file or ""), keys,
                                                                     shared=shared_cache()),
        conflicts=conflicts, policy_md=policy.frozen_copy(start), prior_failures=prior, unread=unread)
    boundary.returns({"brief": str(path), "attempt": n})


if __name__ == "__main__":
    main()
