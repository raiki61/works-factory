"""試験の助け gitkit の、木を読む口 known_under（git が無視する置き場を読まない）の試験。"""
import pathlib
import tempfile
import unittest

from tests.bin import gitkit


class KnownUnderTest(unittest.TestCase):
    def test_ignored_files_are_left_out(self):
        """追跡中の物と無視されない未追跡の物は出し、無視される置き場（道具の控え・仮想環境）の物と別のフォルダ・別の suffix の物は出さない"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            gitkit.git(root, "init", "-q")
            files = {".gitignore": ".venv/\n", "lib/a.py": "", "lib/sub/b.py": "", "lib/.venv/c.py": "", "lib/notes.md": "",
                     "other/d.py": ""}
            for rel, body in files.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(body, encoding="utf-8")
            gitkit.git(root, "add", "lib/a.py")
            self.assertEqual(gitkit.known_under(root, "lib", ".py"), [root / "lib/a.py", root / "lib/sub/b.py"])
            self.assertEqual(gitkit.known_under(root, "lib/"), [root / "lib/a.py", root / "lib/notes.md", root / "lib/sub/b.py"])


if __name__ == "__main__":
    unittest.main()
