"""対象の宣言（.review-checks.json）の読み手（lib/graphloops/engine/declared.py）の検査。元に単体の試験が無いので新しく書く。

- parse: 受ける形（必須の suite・任意の mutation・段の junit）と拒む形（最上位の鍵・段の鍵・名の重なり・junit の相対パス）
- read: 無い・壊れた・mutation の誤り（suite は止めない）
- steps_sha: 鍵の順・空白に依らない
"""
import json
import pathlib
import sys
import tempfile
import unittest

GL = pathlib.Path(__file__).resolve().parents[1] / "graphloops"
if str(GL) not in sys.path:
    sys.path.append(str(GL))

from engine import declared  # noqa: E402

STEP = {"name": "suite", "argv": ["run-tests", "-q"]}


class ParseCase(unittest.TestCase):
    def test_accepts_suite_with_optional_junit(self):
        steps, err = declared.parse(json.dumps({"suite": [STEP, {"name": "b", "argv": ["x"], "junit": "out/r.xml"}]}))
        self.assertIsNone(err)
        self.assertEqual(steps, [STEP, {"name": "b", "argv": ["x"], "junit": "out/r.xml"}])

    def test_accepts_mutation_key(self):
        steps, err = declared.parse(json.dumps({"suite": [STEP], "mutation": {"argv": ["m"], "arms": "a.json"}}))
        self.assertIsNone(err)
        self.assertEqual(steps, [STEP])

    def test_accepts_setup_only_beside_suite(self):
        """suite の横の setup（argv の並び）は誤り無しで読み、sha は suite だけで結ぶ。setup だけの宣言は拒む。空の argv・文字列でない語の
        setup は、parse の誤り（宣言の書式の誤り）にも read_setup の誤りにもなる"""
        setup = [["prepare", "--here"], ["second"]]
        doc = json.dumps({"suite": [STEP], "setup": setup})
        steps, err = declared.parse(doc)
        self.assertIsNone(err)
        self.assertEqual(steps, [STEP])
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / declared.DECL_NAME).write_text(doc, encoding="utf-8")
            self.assertEqual(declared.read_setup(root), (setup, ""))
            self.assertEqual(declared.read(root)["sha"], declared.steps_sha([STEP]))
            self.assertEqual(declared.read(root)["steps"], [STEP])
        steps, err = declared.parse(json.dumps({"setup": setup}))
        self.assertIsNone(steps)
        self.assertIn("最上位", err)
        for bad in ([], "x", [[]], [[""]], [["x", 3]], ["x"], [["x"], 4]):
            with self.subTest(bad=bad):
                bad_doc = json.dumps({"suite": [STEP], "setup": bad})
                steps, err = declared.parse(bad_doc)
                self.assertIsNone(steps)
                self.assertIn("setup", err)
                with tempfile.TemporaryDirectory() as tmp:
                    (pathlib.Path(tmp) / declared.DECL_NAME).write_text(bad_doc, encoding="utf-8")
                    argvs, read_err = declared.read_setup(tmp)
                    self.assertEqual(argvs, [])
                    self.assertIn("setup", read_err)
                    self.assertIn("setup", declared.read(tmp)["error"])   # 宣言の読みは書式の誤りとして返す
        with tempfile.TemporaryDirectory() as tmp:   # 準備が無い形は read_setup が ([], "") を返す
            root = pathlib.Path(tmp)
            self.assertEqual(declared.read_setup(root), ([], ""))   # 宣言が無い
            for text in ("{", "[]", json.dumps({"suite": [STEP]}), json.dumps({"setup": [["x"]]})):   # 読めない・setup の鍵が無い・suite が無い
                with self.subTest(text=text):
                    (root / declared.DECL_NAME).write_text(text, encoding="utf-8")
                    self.assertEqual(declared.read_setup(root), ([], ""))

    def test_rejects_top_level_keys(self):
        for doc in ({}, {"suite": [STEP], "extra": 1}, [STEP], {"steps": [STEP]}):
            with self.subTest(doc):
                steps, err = declared.parse(json.dumps(doc))
                self.assertIsNone(steps)
                self.assertIn("最上位", err)

    def test_rejects_unreadable_and_empty_suite(self):
        self.assertIn("JSON として読めない", declared.parse("{")[1])
        self.assertIn("1 段以上", declared.parse(json.dumps({"suite": []}))[1])

    def test_rejects_step_keys(self):
        for step in ({"name": "a"}, {"argv": ["x"]}, {**STEP, "cwd": "."}, "a"):
            with self.subTest(step):
                steps, err = declared.parse(json.dumps({"suite": [step]}))
                self.assertIsNone(steps)
                self.assertIn("suite[0]", err)

    def test_rejects_overlapping_or_blank_names(self):
        for suite in ([STEP, STEP], [{**STEP, "name": " "}], [{**STEP, "name": 3}]):
            with self.subTest(suite):
                self.assertIn(".name は空でない・重ならない", declared.parse(json.dumps({"suite": suite}))[1])

    def test_rejects_bad_argv(self):
        for argv in ([], "x", [""], ["x", 3]):
            with self.subTest(argv):
                self.assertIn(".argv は 1 語以上", declared.parse(json.dumps({"suite": [{**STEP, "argv": argv}]}))[1])

    def test_junit_must_be_relative_inside_root(self):
        for bad in ("", "/abs.xml", "../r.xml", "a/../../r.xml", 3):
            with self.subTest(bad):
                steps, err = declared.parse(json.dumps({"suite": [{**STEP, "junit": bad}]}))
                self.assertIsNone(steps)
                self.assertIn(".junit はリポジトリのルートからの相対パス", err)


class ReadCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)

    def write(self, text):
        (self.root / declared.DECL_NAME).write_text(text, encoding="utf-8")

    def test_absent_is_none(self):
        self.assertIsNone(declared.read(self.root))

    def test_broken_names_the_declaration(self):
        self.write("{")
        got = declared.read(self.root)
        self.assertEqual(set(got), {"error"})
        self.assertTrue(got["error"].startswith(declared.DECL_NAME))

    def test_steps_and_sha(self):
        self.write(json.dumps({"suite": [STEP]}))
        self.assertEqual(declared.read(self.root), {"steps": [STEP], "sha": declared.steps_sha([STEP])})

    def test_mutation_error_does_not_stop_suite(self):
        self.write(json.dumps({"suite": [STEP], "mutation": {"argv": ["m"], "arms": "missing.json"}}))
        got = declared.read(self.root)
        self.assertEqual(got["steps"], [STEP])
        self.assertIn("missing.json", got["mutation_error"])
        self.assertNotIn("mutation", got)

    def test_mutation_with_arms_present(self):
        (self.root / "arms.json").write_text("[]", encoding="utf-8")
        self.write(json.dumps({"suite": [STEP], "mutation": {"argv": ["m"], "arms": "arms.json"}}))
        self.assertEqual(declared.read(self.root)["mutation"], {"argv": ["m"], "arms": "arms.json"})


class StepsShaCase(unittest.TestCase):
    def test_key_order_and_spacing_do_not_matter(self):
        a = [{"name": "s", "argv": ["x", "y"], "junit": "r.xml"}]
        b = json.loads('[ {"junit":"r.xml",   "argv":["x","y"], "name":"s"} ]')
        self.assertEqual(declared.steps_sha(a), declared.steps_sha(b))
        self.assertNotEqual(declared.steps_sha(a), declared.steps_sha([{**a[0], "argv": ["y", "x"]}]))


if __name__ == "__main__":
    unittest.main()
