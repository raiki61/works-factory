# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""構造の目の支度（lib/eye.prep）。structure.json から指示書を描く。返り {prompt, prompt_file, attempt}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eye  # noqa: E402


def main() -> None:
    boundary.returns(eye.prep(os.environ["INPUTS_STRUCTURE_FILE"]))


if __name__ == "__main__":
    main()
