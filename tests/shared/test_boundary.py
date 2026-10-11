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
        self.base = pathlib.Path(tmp.name)
        self.artifacts = self.base / "runs" / "run-1"
        self.artifacts.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {"WORKFLOW_ID": "run-1", "ARTIFACTS_DIR": str(self.artifacts)})
        env.start()
        self.addCleanup(env.stop)

    def write(self, rel, text):
        path = self.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class PointerTest(FakeRunTest):
    def test_pointer_names_this_run(self):
        self.write("plan/plan.md", "# plan\n")
        self.assertEqual(
            boundary.pointer("plan/plan.md"),
            {"type": "archon_artifact", "run_id": "run-1", "path": "plan/plan.md"},
        )

    def test_pointer_refuses_empty_file(self):
        self.write("empty.md", "")
        with self.assertRaisesRegex(ValueError, "empty.md"):
            boundary.pointer("empty.md")

    def test_pointer_refuses_missing_file(self):
        with self.assertRaisesRegex(ValueError, "missing.md"):
            boundary.pointer("missing.md")

    def test_pointer_refuses_directory(self):
        (self.artifacts / "dir").mkdir()
        with self.assertRaisesRegex(ValueError, "dir"):
            boundary.pointer("dir")

    def test_pointer_refuses_outside(self):
        outside = self.base / "outside.md"
        outside.write_text("x", encoding="utf-8")
        for rel in ("../../outside.md", str(outside), "a/../../../outside.md"):
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, "相対"):
                boundary.pointer(rel)

    def test_pointer_refuses_backslash_outside(self):
        # POSIX では \ はただの文字なので、在るファイルの名にして、在る無しではなくパスの決まりで止まるのを見る
        for rel in ("..\\x", "\\x"):
            self.write(rel, "x")
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, "相対"):
                boundary.pointer(rel)

    def test_pointer_refuses_trailing_slash(self):
        self.write("plan.md", "# plan\n")
        with self.assertRaisesRegex(ValueError, "相対"):
            boundary.pointer("plan.md/")


class ResolveTest(FakeRunTest):
    def test_resolve_returns_file_in_this_run(self):
        path = self.write("report.md", "ok")
        self.assertEqual(
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": "report.md"}),
            path,
        )

    def test_resolve_refuses_other_run(self):
        self.write("report.md", "ok")
        with self.assertRaisesRegex(ValueError, "run-2"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-2", "path": "report.md"})

    def test_resolve_refuses_outside(self):
        with self.assertRaisesRegex(ValueError, r"\.\./x"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": "../x"})

    def test_resolve_refuses_non_pointer(self):
        with self.assertRaisesRegex(ValueError, "archon_artifact"):
            boundary.resolve({"type": "file", "run_id": "run-1", "path": "report.md"})


class InputsTest(unittest.TestCase):
    def test_inputs_reads_upper_snake_env(self):
        env = {"INPUTS_PLAN": "p", "INPUTS_BASE_BRANCH": "main"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(boundary.inputs(["plan", "base-branch"]), {"plan": "p", "base-branch": "main"})

    def test_inputs_names_missing(self):
        with mock.patch.dict(os.environ, {"INPUTS_PLAN": "p"}):
            os.environ.pop("INPUTS_MODE", None)
            with self.assertRaisesRegex(KeyError, "mode"):
                boundary.inputs(["plan", "mode"])


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
