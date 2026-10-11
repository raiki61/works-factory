"""構造の目の控え structure-state.json を書く（lib/planfile.write_state。使い回しの周は書き直さない）。返り {state_file}"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    state = planfile.write_state(art / planfile.PLAN_DIR / planfile.read_round(art / os.environ["INPUTS_DIR"])["structure"])
    boundary.returns({"state_file": state.relative_to(art).as_posix()})


if __name__ == "__main__":
    main()
