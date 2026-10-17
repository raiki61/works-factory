"""境（workflows/.shared/）のモジュールをファイルから読む。.shared は import の名にならず、Archon が置き場をバイトで照らすので
__pycache__ を作らない。"""
import importlib.util
import pathlib
import sys
from types import ModuleType

SHARED = pathlib.Path(__file__).resolve().parents[2] / "workflows" / ".shared"


def load(name: str) -> ModuleType:
    """workflows/.shared/<name>.py を読んだモジュール。2 度目からは読んだ物を返す"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHARED / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    sys.modules[name] = module
    return module
