"""版の控え（lib/versions.py。元 works/.shared/core/versions.py）の検査: 分からない値は null と理由、引ける値はその値。"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import versions  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402


class SnapshotCase(unittest.TestCase):
    def test_unknown_values_are_null_with_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = versions.snapshot(tmp, {}, run_id="r", settings={"features_off": "world"},
                                    given={"engine": (None, "引けない訳"), "pin": ("abc", "")})
        self.assertEqual((got["works"], got["borrowed"], got["engine"], got["pin"]), ({"rev": None, "dirty": None}, None, None, "abc"))
        for key in ("works.rev", "borrowed", "engine"):
            with self.subTest(key=key):
                self.assertTrue(got["unknown"][key])
        self.assertNotIn("pin", got["unknown"])
        self.assertEqual((got["run_id"], got["settings"]), ("r", {"features_off": "world"}))

    def test_known_values_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "pin.json").write_text(json.dumps({"rev": "abc"}), encoding="utf-8")
            cfg = root / "cfg"
            cfg.mkdir()
            (cfg / versions.TOOLSET_RECORD).write_text(json.dumps({"superpowers": {"version": "1"}}), encoding="utf-8")
            git(root, "init", "-q")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "x")
            got = versions.snapshot(root, {"CLAUDE_CONFIG_DIR": str(cfg)})
            self.assertEqual(versions.pinned(root / "pin.json", "rev"), ("abc", ""))
            self.assertIsNone(versions.pinned(root / "pin.json", "no")[0])
        self.assertEqual(got["borrowed"], {"superpowers": {"version": "1"}})
        self.assertEqual((len(got["works"]["rev"]), got["works"]["dirty"]), (40, False))


if __name__ == "__main__":
    unittest.main()
