"""段 A の実測（lib/planfile.measure）。単位の目録のうち paths の在る単位を plan/structure/<鍵>/ で測る。同じ鍵の控えが在れば
測らない。返り {structure_file, design_file, eye, reused}"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    rnd = planfile.read_round(art / os.environ["INPUTS_DIR"])
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    units = planfile.units_of(os.environ["INPUTS_UNITS"])
    out_dir = planfile.structure_dir(art / "plan", units, Path.cwd(), rnd["mode"])
    policy = start.get("policy_md") if isinstance(start, dict) else ""
    boundary.returns(planfile.measure(out_dir, units, Path.cwd(), policy or ""))


if __name__ == "__main__":
    main()
