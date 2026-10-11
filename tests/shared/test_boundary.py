"""境の口（workflows/.shared/boundary.py）を、偽の環境と偽の run の置き場で確かめる。"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_boundary():
    # .shared は import の名にならないので、ファイルから読む。Archon が置き場をバイトで照らすので __pycache__ を作らない
    spec = importlib.util.spec_from_file_location("boundary", ROOT / "workflows" / ".shared" / "boundary.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


boundary = load_boundary()


class FakeRunTest(unittest.TestCase):
    """Archon が script の節に渡す環境（WORKFLOW_ID・ARTIFACTS_DIR）を偽の run で作る"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.artifacts = pathlib.Path(tmp.name)
        env = mock.patch.dict(os.environ, {"WORKFLOW_ID": "run-1", "ARTIFACTS_DIR": str(self.artifacts)})
        env.start()
        self.addCleanup(env.stop)


class PointerTest(FakeRunTest):
    def test_pointer_names_this_run(self):
        self.assertEqual(
            boundary.pointer("plan/plan.md"),
            {"type": "archon_artifact", "run_id": "run-1", "path": "plan/plan.md"},
        )


class ResolveTest(FakeRunTest):
    def test_resolve_returns_file_in_this_run(self):
        self.assertEqual(
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": "report.md"}),
            self.artifacts / "report.md",
        )

    def test_resolve_refuses_other_run(self):
        with self.assertRaisesRegex(ValueError, "run-2"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-2", "path": "report.md"})

    def test_resolve_refuses_bad_path(self):
        for rel in ("", "a\0b", "/x", "\\x", "../x", "..\\x", "a/../../x", "report.md/"):
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, "相対"):
                boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": rel})

    def test_resolve_refuses_missing_path(self):
        with self.assertRaisesRegex(ValueError, "相対"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1"})

    def test_resolve_refuses_non_pointer(self):
        with self.assertRaisesRegex(ValueError, "archon_artifact"):
            boundary.resolve({"type": "file", "run_id": "run-1", "path": "report.md"})


class ReturnsTest(unittest.TestCase):
    def test_returns_writes_one_json(self):
        obj = {"outcome": "完了", "items": [1, 2], "ptr": None}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            boundary.returns(obj)
        text = out.getvalue()
        value, end = json.JSONDecoder(parse_constant=self.refuse_constant).raw_decode(text)
        self.assertEqual(value, obj)
        self.assertEqual(text[end:].strip(), "")

    def test_returns_refuses_nan(self):
        for number in (float("nan"), float("inf")):
            with self.subTest(number=number), self.assertRaises(ValueError):
                boundary.returns({"x": number})

    @staticmethod
    def refuse_constant(name):
        raise ValueError(f"JSON でない値: {name}")


class LibRootTest(unittest.TestCase):
    def test_lib_root_is_repository_lib(self):
        self.assertEqual(boundary.lib_root(), ROOT / "lib")


if __name__ == "__main__":
    unittest.main()
