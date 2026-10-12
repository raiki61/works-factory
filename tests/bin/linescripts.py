"""線の script（workflows/line/scripts/）を試験から読む助け（テストのモジュールではない。test_*.py に当たらない）。

script は名前の script として Archon が走らせるファイルで、境の口（workflows/.shared/boundary.py）と lib/ を自分で sys.path に足して
import する。ここではファイルを `line_<名>` のモジュールとして読む（start・result などの短い名がほかのモジュールと重ならないように）。
"""
import importlib.util

from tests import archon

SCRIPTS = archon.WORKFLOWS / "line" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"line_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
