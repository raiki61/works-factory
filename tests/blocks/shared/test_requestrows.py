"""blocks/.shared/requestrows.py: 依頼の行を port から読む共通の口。形の照らしの後に lib/carry の容器の読みを通す"""
import json
import sys
import unittest

from tests.blocks import kit

sys.dont_write_bytecode = True
sys.path.insert(0, str(kit.SHARED))
import requestrows  # noqa: E402

ROW = {"where": "README", "text": "x"}


class ReadCase(unittest.TestCase):
    def test_both_forms_give_the_rows(self):
        self.assertEqual(requestrows.findings(json.dumps([ROW])), [ROW])
        self.assertEqual(requestrows.findings(json.dumps({"findings": [ROW], "pr": [3]})), [ROW])
        self.assertEqual(requestrows.parts(json.dumps({"findings": [ROW], "pr": [3]}))["pr"], [3])

    def test_refusals_are_named(self):
        cases = {json.dumps([{"text": "no where"}]): "where", json.dumps({"findings": [ROW], "extra": 1}): "知らない鍵",
                 json.dumps([{**ROW, "draft": True, "source": "r"}]): "下書き",
                 json.dumps({"findings": [{**ROW, "draft": True, "source": "r"}]}): "下書き",
                 json.dumps({"findings": [ROW], "pr": ["x"]}): "pr",
                 # 行の知らない欄（打ち違い）は拒む（元の judge の REQUEST_SCHEMA の additionalProperties: false）
                 json.dumps([{**ROW, "mesured": "x"}]): "mesured",
                 json.dumps({"findings": [{**ROW, "mesured": "x"}]}): "mesured"}
        for raw, word in cases.items():
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, word):
                requestrows.parts(raw)


if __name__ == "__main__":
    unittest.main()
