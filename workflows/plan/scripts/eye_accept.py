"""構造の目の受け付け（lib/eye.accept）。通れば design.jsonl に行を書く。拒否は ok: false で、3 回目の拒否で done。
返り {ok, done, give_up, reason, attempt}"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eye  # noqa: E402


def main() -> None:
    try:
        reply = json.loads(os.environ["INPUTS_REPLY"])
    except json.JSONDecodeError:
        reply = None
    boundary.returns(eye.accept(os.environ["INPUTS_STRUCTURE_FILE"], os.environ["INPUTS_DESIGN_FILE"], reply))


if __name__ == "__main__":
    main()
