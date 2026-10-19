"""埋め P6（workflows/.shared/child_pointer.py。integration.md の 4.5-1 で ports を読む形に直した）を、使い捨ての runs/{parent,child} の置き場で確かめる。"""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from tests.blocks import kit

sys.dont_write_bytecode = True
sys.path.insert(0, str(kit.SHARED))   # 埋めが import する口 ports の置き場
import child_pointer  # noqa: E402


def ptr(run_id="child", path="report/next-request.json", kind="archon_artifact"):
    return {"type": kind, "run_id": run_id, "path": path}


class ChildPointerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        runs = pathlib.Path(tmp.name) / "runs"
        self.parent, self.child = runs / "parent", runs / "child"
        (self.child / "report").mkdir(parents=True)
        self.parent.mkdir()
        self.file = self.child / "report" / "next-request.json"
        self.file.write_text("{}", encoding="utf-8")
        (self.parent / "secret.json").write_text("{}", encoding="utf-8")
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.parent)})
        env.start()
        self.addCleanup(env.stop)

    def test_reads_a_file_in_the_sibling_run(self):
        self.assertEqual(child_pointer.resolve(ptr()), self.file.resolve())

    def test_paths_leaving_the_child_run_are_refused(self):
        for path in ("../parent/secret.json", str(self.parent / "secret.json"), "", None, "report/../../parent/secret.json"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    child_pointer.resolve(ptr(path=path))

    def test_paths_archon_refuses_are_refused_even_inside_the_child_run(self):
        for path in ("report/../report/next-request.json", "report/", "\\report\\next-request.json"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    child_pointer.resolve(ptr(path=path))

    def test_bad_run_ids_are_refused(self):
        for run_id in ("", "..", ".", "a/b", "../parent", None, 3):
            with self.subTest(run_id=run_id):
                with self.assertRaises(ValueError):
                    child_pointer.resolve(ptr(run_id=run_id))

    def test_symlink_out_of_the_child_run_is_refused(self):
        (self.child / "report" / "out.json").symlink_to(self.parent / "secret.json")
        with self.assertRaisesRegex(ValueError, "外"):
            child_pointer.resolve(ptr(path="report/out.json"))

    def test_other_shapes_are_refused(self):
        for got in (ptr(kind="file"), None, "child/report/next-request.json", {"run_id": "child", "path": "x"}):
            with self.subTest(got=got):
                with self.assertRaises(ValueError):
                    child_pointer.resolve(got)


if __name__ == "__main__":
    unittest.main()
