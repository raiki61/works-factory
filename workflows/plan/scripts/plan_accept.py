# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の返答の受け付け（lib/planfile.take_plan・take_replan）。拒否は rolekit.accept_round が控え rejects-plan.json に積み、3 回目の拒否で
done・give_up（輪を max_iterations で落とさずに抜ける）。受けた案の控えを置けない時（halt。take の返りの count: false・give_up: true）は拒否に数えずに done・give_up。
拒否の控えが読めない・書けない時は、落ちずに done・give_up の拒否（理由『拒否の控えが扱えない』）。
with: の status_guarded が真なら、Archon の状態の照らしと重なる git status の行は比べない（accept.status_keys）。返り {ok, done, give_up, reason, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import planfile  # noqa: E402
import rolekit  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir, round_dir, repo = art / planfile.PLAN_DIR, art / os.environ["INPUTS_DIR"], Path.cwd()
    rnd = planfile.read_round(round_dir)
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.pointed)
    base_rev = (start.get("base_rev") if isinstance(start, dict) else "") or ""
    world, _ = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.pointed)
    tables = planfile.answer_tables(plan_dir / rnd["structure"], world)
    keys = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        out = {"ok": False, "reason": why}
    elif rnd["mode"] == "replan":
        out = planfile.take_replan(round_dir, plan_dir, items=rnd["items"], reply=reply, repo=repo, tables=tables,
                                   base_rev=base_rev, keys=keys)
    else:
        judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.pointed)
        out = planfile.take_plan(round_dir, plan_dir, judgment=judgment, reply=reply, repo=repo, tables=tables,
                                 base_rev=base_rev, keys=keys)
    n, stopped = rolekit.current_round(round_dir, planfile.ROLE)
    got = stopped or rolekit.accept_round(round_dir, planfile.ROLE, None, lambda _: out)
    tries = max(n - (1 if out.get("halt") else 0), 0)   # 受けた・拒んだ回は今の回、halt は前の拒否の数
    boundary.returns({**rolekit.round_outcome(got), "attempt": tries})


if __name__ == "__main__":
    main()
