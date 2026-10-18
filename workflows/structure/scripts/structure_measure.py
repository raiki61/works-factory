# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""段 A の実測（lib/structfile.measure）。単位の目録のうち paths の在る単位を置き場 structure/ で測る。
返り {structure_file, design_file, eye}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import jsonfile  # noqa: E402
import policy  # noqa: E402
import rolekit  # noqa: E402
import structfile  # noqa: E402


def main() -> None:
    start_file, bad_start = rolekit.pointed(os.environ["INPUTS_START"], boundary.pointed)
    start = jsonfile.read_or(start_file) if start_file else None
    out_dir = Path(os.environ["ARTIFACTS_DIR"]) / structfile.DIR
    units = boundary.value(os.environ["INPUTS_UNITS"])   # JSON でなければ字のまま（段 A の読みが形の誤りを言う）
    unread = [f"start: {bad_start}"] if bad_start else []
    boundary.returns(structfile.measure(out_dir, units, Path.cwd(), policy.frozen_copy(start), unread))


if __name__ == "__main__":
    main()
