# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""案の前の波及の一覧（lib/planfile.ripple_units）を plan/r<k>/ripple-units.json に書く。返り {ripple_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.pointed)
    judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.pointed,
                                       ties=os.environ.get("INPUTS_ANSWER_TIES", ""), materials=os.environ.get("INPUTS_MATERIALS", ""))
    path = planfile.ripple_units(art / os.environ["INPUTS_DIR"], judgment, Path.cwd(), skip_dirs=boundary.RUNTIME_COPY_DIRS)
    boundary.returns({"ripple_file": path.relative_to(art).as_posix()})


if __name__ == "__main__":
    main()
