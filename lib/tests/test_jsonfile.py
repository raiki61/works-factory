"""JSON のファイルの読み書きの口（lib/jsonfile）。寄せる前の写しと同じ振る舞い（無い・壊れた時の読み・置き換えの書き方・親の
フォルダ）を見る（FAST。一時の置き場だけ）"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import jsonfile  # noqa: E402


class JsonFileCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def test_read_or_gives_the_default_for_missing_or_broken(self):
        (self.dir / "broken.json").write_text("{x", encoding="utf-8")
        (self.dir / "bytes.json").write_bytes(b"\xff\xfe")
        for name in ("missing.json", "broken.json", "bytes.json", ""):
            with self.subTest(name):
                self.assertIsNone(jsonfile.read_or(self.dir / name))
                self.assertEqual(jsonfile.read_or(self.dir / name, []), [])
        (self.dir / "ok.json").write_text('{"a": "字"}', encoding="utf-8")
        self.assertEqual(jsonfile.read_or(str(self.dir / "ok.json")), {"a": "字"})

    def test_write_replaces_with_indent_and_newline(self):
        path = self.dir / "doc.json"
        path.write_text("古い", encoding="utf-8")
        self.assertEqual(jsonfile.write(path, {"a": "字"}), path)
        self.assertEqual(path.read_text(encoding="utf-8"), '{\n "a": "字"\n}\n')
        jsonfile.write(str(path), [1], indent=2)
        self.assertEqual(path.read_text(encoding="utf-8"), json.dumps([1], indent=2) + "\n")
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["doc.json"], "一時のファイルを残さない")

    def test_parent_folder_is_made_only_when_asked(self):
        deep = self.dir / "a" / "b" / "doc.json"
        with self.assertRaises(FileNotFoundError):
            jsonfile.write(deep, {})
        self.assertEqual(jsonfile.write(deep, {}, parents=True), deep)
        self.assertEqual(json.loads(deep.read_text(encoding="utf-8")), {})

    def test_read_dict_and_dump(self):
        """read_dict は JSON のオブジェクトだけ返し、オブジェクトでなければ ValueError。dump は書いた中身のバイトを返し、一時のファイルを残さない"""
        path = self.dir / "d.json"
        raw = jsonfile.dump(path, {"a": "字"})
        self.assertEqual(raw, '{\n "a": "字"\n}\n'.encode("utf-8"))
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(jsonfile.read_dict(path), {"a": "字"})
        path.write_text("[1]", encoding="utf-8")
        with self.assertRaises(ValueError):
            jsonfile.read_dict(path)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["d.json"])

    def test_rows_and_split_walk_the_path(self):
        """rows は道を辿って行を（写さず）返し、EACH の段だけ入れ子の並びになる。split は欄を外した写しと外した欄を返し、元は変えない"""
        doc = {"a": [{"x": 1, "y": 2}, {"y": 3}], "b": {"x": 9}}
        self.assertEqual(jsonfile.rows(doc, ["a", jsonfile.EACH]), [{"x": 1, "y": 2}, {"y": 3}])
        self.assertIs(jsonfile.rows(doc, ["a", jsonfile.EACH])[0], doc["a"][0])
        self.assertEqual(jsonfile.rows(doc, ["b"]), {"x": 9})
        self.assertEqual(jsonfile.rows(doc, ["a", jsonfile.EACH, "y"]), [2, 3])
        self.assertEqual(jsonfile.rows(doc, ["b", jsonfile.EACH]), [])
        self.assertIsNone(jsonfile.rows(doc, ["a", "z"]))
        out, taken = jsonfile.split(doc, ["a", jsonfile.EACH], ["x"])
        self.assertEqual(out, {"a": [{"y": 2}, {"y": 3}], "b": {"x": 9}})
        self.assertEqual(taken, [{"x": 1}, {}])
        self.assertEqual(doc["a"][0], {"x": 1, "y": 2}, "元の doc は変えない")
        self.assertEqual(jsonfile.split(doc, ["b"], ["x"])[1], {"x": 9})
        self.assertEqual(jsonfile.split(doc, ["a"], ["x"])[1], {}, "行が dict でなければ空")


if __name__ == "__main__":
    unittest.main()
