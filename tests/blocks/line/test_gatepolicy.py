"""人の関所と無人の方針（元 lib/tests/test_gatepolicy.py。住処は line の src/gates.py。docs/design/line.md の 6 節）の語・入口の確かめ・
始めの記録からの読み・最後の関所を開くかの決め。一時の置き場のファイルだけ（git・子のプロセスなし）。

元の StuckPushableCase は、止まった壁打ちを推しで越えてよいかの決めが往復の記録の住処 src/rounds.py へ移ったので、
tests/blocks/line/test_converge_line.py が持つ。
"""
import json
import tempfile
import unittest

from tests.blocks import kit

gp = kit.load("line", "gates")
startrec = __import__("sys").modules["src.startrec"]   # gates が読んだのと同じ src の始めの記録の口
import answer  # noqa: E402
import stopby  # noqa: E402


def record(d, **fields):
    p = startrec.path(d)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(fields), encoding="utf-8")


class WordsCase(unittest.TestCase):
    def test_words(self):
        """最後の関所の開き方は 3 つ（空の既定は always）、無人の語は true（空は人の居る run）"""
        self.assertEqual(gp.FINAL_GATES, ("always", "when_needed", "protected_only"))
        self.assertEqual(gp.FINAL_GATES[0], gp.ALWAYS)
        self.assertEqual(gp.UNATTENDED, "true")


class CheckCase(unittest.TestCase):
    def test_empty_is_default(self):
        self.assertEqual(gp.check("", "", spec=False), {gp.FINAL_KEY: gp.ALWAYS, gp.UNATTENDED_KEY: ""})

    def test_unattended_empty_is_when_needed(self):
        """無人の run は最後の関所で推しを持たず、開けば止まって差分を当てない。空の既定は理由が在る時だけ開く。名指した always は残す"""
        self.assertEqual(gp.check("", gp.UNATTENDED, spec=False), {gp.FINAL_KEY: gp.WHEN_NEEDED, gp.UNATTENDED_KEY: gp.UNATTENDED})
        self.assertEqual(gp.check(gp.ALWAYS, gp.UNATTENDED, spec=False)[gp.FINAL_KEY], gp.ALWAYS)

    def test_known_words_pass(self):
        for mode in gp.FINAL_GATES:
            self.assertEqual(gp.check(mode, gp.UNATTENDED, spec=False), {gp.FINAL_KEY: mode, gp.UNATTENDED_KEY: gp.UNATTENDED})

    def test_unknown_words_refused(self):
        for final, unattended_ in (("sometimes", ""), ("", "yes"), ("", "1")):
            with self.subTest(final=final, unattended_=unattended_), self.assertRaises(gp.Refused):
                gp.check(final, unattended_, spec=False)

    def test_spec_and_unattended_refused(self):
        """仕様の段の承認は人の関所なので、無人の run とは組めない"""
        with self.assertRaises(gp.Refused):
            gp.check("", gp.UNATTENDED, spec=True)
        self.assertEqual(gp.check("", "", spec=True)[gp.FINAL_KEY], gp.ALWAYS)


class ReadCase(unittest.TestCase):
    def test_reads_the_start_record(self):
        """読み手は始めの記録から読む（線の節に入力を写さない）。記録が無い・欄が空なら既定（always・人の居る run）"""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(gp.final_mode(d), gp.ALWAYS)
            self.assertFalse(gp.unattended(d))
            record(d, **{gp.FINAL_KEY: "when_needed", gp.UNATTENDED_KEY: gp.UNATTENDED})
            self.assertEqual(gp.final_mode(d), "when_needed")
            self.assertTrue(gp.unattended(d))
            record(d, **{gp.FINAL_KEY: "", gp.UNATTENDED_KEY: ""})
            self.assertEqual(gp.final_mode(d), gp.ALWAYS)
            self.assertFalse(gp.unattended(d))

    def test_reads_the_start_record_dict(self):
        """報告と台帳の見え方は始めの記録の dict から同じ式で読む（無い・欄が無いなら人の居る run）"""
        self.assertTrue(gp.unattended_of({gp.UNATTENDED_KEY: gp.UNATTENDED}))
        self.assertFalse(gp.unattended_of({}))
        self.assertFalse(gp.unattended_of(None))

    def test_unknown_mode_in_record_is_an_error(self):
        """入口が確かめた語の外が記録に在れば配線の誤り（黙って always に倒さない）"""
        with tempfile.TemporaryDirectory() as d:
            record(d, **{gp.FINAL_KEY: "sometimes"})
            with self.assertRaises(ValueError):
                gp.final_mode(d)

    def test_head_words(self):
        """報告の頭の行の句: 記録に開き方が在れば「最後の関所: <語>」、無ければ空"""
        self.assertEqual(gp.head_words({gp.FINAL_KEY: "when_needed"}), "最後の承認ノード: when_needed")
        self.assertEqual(gp.head_words({}), "")


class OpensCase(unittest.TestCase):
    def test_always_opens(self):
        self.assertTrue(gp.opens(gp.ALWAYS, reasons=[], guarded=False))

    def test_when_needed_opens_only_with_reasons(self):
        self.assertFalse(gp.opens("when_needed", reasons=[], guarded=False))
        self.assertTrue(gp.opens("when_needed", reasons=["赤"], guarded=False))

    def test_protected_only_opens_only_when_guarded(self):
        self.assertFalse(gp.opens("protected_only", reasons=["赤"], guarded=False))
        self.assertTrue(gp.opens("protected_only", reasons=[], guarded=True))


def push(word, note):
    rec = {"item": "x", "answer": word, "note": note, "why": "推す理由"}
    return gp.Push(word == "continue", note, rec)


class PassageCase(unittest.TestCase):
    """#653: 無人の run で開くはずの承認ノードの抜け方（今の筋書きの結果を縛る）"""
    PUSHES = {"a": push("continue", "a で通す"), "b": push("continue", "b で通す"), "a2": push("continue", "a で通す"),
              "s": push("stop", "止める訳"), "none": None}

    def passage(self, rows):
        return gp.passage(rows, self.PUSHES.get)

    def test_every_row_pushes_continue_goes_with_the_push(self):
        got = self.passage(["a", "b", "a2"])
        self.assertEqual((got.go, got.stop_reason, got.asked), (True, "", ["a", "b", "a2"]))
        self.assertEqual(got.pushed, {"decision": "continue", "text": "a で通す；b で通す",
                                      answer.PUSHED: [self.PUSHES[k].rec for k in ("a", "b", "a2")]})
        self.assertIn(got.pushed["decision"], answer.GO_WORDS)

    def test_a_row_without_a_push_or_with_a_stop_push_stops(self):
        for rows in (["a", "none"], ["a", "s"], ["none"], []):
            with self.subTest(rows=rows):
                self.assertEqual(self.passage(rows), gp.Passage(False, stopby.NEEDS_HUMAN, [], None))


if __name__ == "__main__":
    unittest.main()
