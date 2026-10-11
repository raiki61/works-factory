"""受け付けた案の項目ごとの波及の一覧（lib/planfile.ripple_items）を plan/r<k>/ripple.json に書く。返り {ripple_file}"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402

SKIP_DIRS = ((".archon",),)   # 実行基盤が対象に置く工程の写し（呼び出し元でない）


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    path = planfile.ripple_items(art / os.environ["INPUTS_DIR"], Path.cwd(), skip_dirs=SKIP_DIRS)
    boundary.returns({"ripple_file": path.relative_to(art).as_posix()})


if __name__ == "__main__":
    main()
