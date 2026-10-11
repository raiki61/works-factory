# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正案の役の返答の受け付け（lib/planfile.take_plan・take_replan）。拒否は rolekit.with_done の控えに積み、3 回目の拒否で
done・give_up（輪を max_iterations で落とさずに抜ける）。返り {ok, done, give_up, reason, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402
import rolekit  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir, round_dir, repo = art / planfile.PLAN_DIR, art / os.environ["INPUTS_DIR"], Path.cwd()
    rnd = planfile.read_round(round_dir)
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    base_rev = (start.get("base_rev") if isinstance(start, dict) else "") or ""
    world, _ = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.resolve)
    tables = planfile.answer_tables(plan_dir / rnd["structure"], world)
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        out = {"ok": False, "reason": why}
    elif rnd["mode"] == "replan":
        out = planfile.take_replan(round_dir, plan_dir, items=rnd["items"], reply=reply, repo=repo, tables=tables,
                                   base_rev=base_rev)
    else:
        judgment, _ = planfile.read_pointed(os.environ["INPUTS_JUDGMENT"], boundary.resolve)
        out = planfile.take_plan(round_dir, plan_dir, judgment=judgment, reply=reply, repo=repo, tables=tables,
                                 base_rev=base_rev)
    out = rolekit.with_done(round_dir, planfile.ROLE, out)
    tries = len(rolekit.rejected(round_dir, planfile.ROLE)) + (1 if out["ok"] else 0)
    boundary.returns({"ok": out["ok"], "done": out["done"], "give_up": out["done"] and not out["ok"], "reason": out["reason"],
                      "attempt": tries})


if __name__ == "__main__":
    main()
