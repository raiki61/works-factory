"""始めの記録の住処 startrec（.shared/core/startrec.py）の読み口と入口の文と版の控え。一時の置き場のファイルだけ（FAST。git なし。子のプロセスは版の控えの試験の 1 つだけ）"""
import json
import pathlib
import re
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import startrec  # noqa: E402


def shape(empty=True, requests=2, label="HEAD", spec=False):
    return {"base": {"rev": "a" * 40, "from": "head", "name": "", "label": label}, "head_rev": "b" * 40,
            "diff": {"empty": empty, "files": 0 if empty else 3, "stat": ""}, "requests": requests, "request_file": "",
            "pr": None, "spec": spec}


class StartRecCase(unittest.TestCase):
    def test_place(self):
        """置き場は盤面の根の r1/start.json（周の置き場の中の名は start.json）"""
        self.assertEqual(startrec.REL, "r1/start.json")
        self.assertEqual(startrec.NAME, "start.json")
        self.assertEqual(startrec.path("/b"), pathlib.Path("/b/r1/start.json"))

    def test_read_missing_or_broken_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(startrec.read(d), {})
            p = startrec.path(d)
            p.parent.mkdir()
            for text in ("{", "[1]"):
                p.write_text(text, encoding="utf-8")
                self.assertEqual(startrec.read(d), {})
            p.write_text(json.dumps({"input": shape(), "test_cmd": "x"}), encoding="utf-8")
            self.assertEqual(startrec.read(d)["test_cmd"], "x")

    def test_shape_readers(self):
        """入口の入力の形の欄の読み。形の無い前の版の控えは None（分からない。0 や偽と読まない）"""
        doc = {"input": shape(empty=False, requests=0)}
        self.assertEqual((startrec.diff_empty(doc), startrec.requests(doc)), (False, 0))
        for old in ({}, {"input": None}, {"input": {"diff": "x"}}, {"entry": "change"}):
            with self.subTest(old):
                self.assertIsNone(startrec.diff_empty(old))
                self.assertIsNone(startrec.requests(old))

    def test_read_rev_and_diff_base(self):
        """読む版は review_rev・BASE は input.base.rev。どちらも無い前の版の控えは base_rev に倒す（前は両方が base_rev）。
        judge の start_view の diff_base も同じ読み口を通る"""
        doc = {"input": shape(empty=False), "base_rev": "c" * 40, "review_rev": "b" * 40}
        self.assertEqual((startrec.read_rev(doc), startrec.diff_base(doc)), ("b" * 40, "a" * 40))
        self.assertEqual((startrec.read_rev({"base_rev": "abc"}), startrec.diff_base({"base_rev": "abc"})), ("abc", "abc"))
        self.assertEqual((startrec.read_rev({}), startrec.diff_base({})), ("HEAD", ""))

    def test_diff_base_label(self):
        doc = {"input": shape(empty=False)}
        self.assertEqual(startrec.diff_base_label(doc), doc["input"]["base"]["label"])
        self.assertEqual(startrec.diff_base_label({"base_rev": "abc"}), "")

    def test_cli_version_reads_the_first_line_or_nothing(self):
        self.assertTrue(startrec.cli_version(sys.executable).startswith("Python "))
        self.assertEqual(startrec.cli_version("no-such-command-for-works-factory"), "")

    def test_words_shapes(self):
        """入口の文の 3 形（差分なし・差分あり・仕様の段あり）。出どころは base.label のまま"""
        self.assertEqual(startrec.words(shape()), "差分なし（HEAD）・依頼 2 件——P1 の役は起こさない")
        self.assertEqual(startrec.words(shape(empty=False, requests=0, label="PR #12「題」")),
                         "差分 aaaaaaaaaaaa..HEAD（3 ファイル・PR #12「題」）・依頼 0 件")
        self.assertEqual(startrec.words(shape(empty=False, label="base main", spec=True)),
                         "差分 aaaaaaaaaaaa..HEAD（3 ファイル・base main）・依頼 2 件・仕様の段あり")



class RequestFileOwner(unittest.TestCase):
    """始めの記録の依頼のファイルを読む式は startrec.request_file の 1 か所（#393。盤面から読む conflict.request_file もここを引く）"""
    READ = re.compile(r"""\.get\(\s*["']request_file["']|\[\s*["']request_file["']\s*\]""")
    OTHER_DICTS = {"fixrules.py": "役の指示書の run の値 values を読む（始めの記録ではない）",
                   "entryshape.py": "入口の変換が依頼の読みの dict から入口の入力の形を組む（始めの記録を書く前）"}

    def test_read_once_in_lib(self):
        found = {str(f.relative_to(LIB)) for f in LIB.rglob("*.py")
                 if "tests" not in f.relative_to(LIB).parts and self.READ.search(f.read_text(encoding="utf-8"))}
        self.assertEqual(found - set(self.OTHER_DICTS), {"startrec.py"})

    def test_pattern_sees_a_second_copy(self):
        for copy in ('req = start.get("request_file")', "start['request_file']"):
            with self.subTest(copy=copy):
                self.assertTrue(self.READ.search(copy))

    def test_falls_back_to_the_entry_shape(self):
        """欄 request_file が無い・空なら入口の入力の形の input.request_file。どちらも無ければ空（事前審査と判定の読みの既定を全部の読み手に）"""
        cases = [({"request_file": "/a.json", "input": {"request_file": "/b.json"}}, "/a.json"),
                 ({"request_file": "", "input": {"request_file": "/b.json"}}, "/b.json"),
                 ({"input": {"request_file": "/b.json"}}, "/b.json"),
                 ({"request_file": 3, "input": {"request_file": None}}, ""),
                 ({}, ""), (None, "")]
        for doc, want in cases:
            with self.subTest(doc=doc):
                self.assertEqual(startrec.request_file(doc), want)


if __name__ == "__main__":
    unittest.main()
