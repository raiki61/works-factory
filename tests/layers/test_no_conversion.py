"""Archon が読む所（place.workflow_source の置き場の .archon/workflows/<pack>/ の下）の全部のファイルが、workflows/ とバイトで同じ（workflows/AGENTS.md の E1 の機械の行）。"""
import pathlib
import tempfile
import unittest

from bin._lib import pack, place

ROOT = pathlib.Path(__file__).resolve().parents[2]


def files(root: pathlib.Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class NoConversionTest(unittest.TestCase):
    def test_archon_reads_workflows_byte_for_byte(self):
        loaded = pack.load(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            shim = place.workflow_source(loaded, ROOT, pathlib.Path(tmp))
            read = files(place.pack_folder(loaded, shim))
        self.assertIn(".shared/ports.py", read)
        self.assertEqual(read, files(ROOT / loaded["ours"]["folder"]))


if __name__ == "__main__":
    unittest.main()
