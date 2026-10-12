"""線の script（workflows/line/scripts/）を試験から読む助け（テストのモジュールではない。test_*.py に当たらない）。

script は名前の script として Archon が走らせるファイルで、同じフォルダの linekit を import する。ここではフォルダを sys.path の
後ろに足し、ファイルを `line_<名>` のモジュールとして読む（start・result などの短い名がほかのモジュールと重ならないように）。
"""
import importlib.util
import sys

from tests import archon

SCRIPTS = archon.WORKFLOWS / "line" / "scripts"


def load(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.append(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"line_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
