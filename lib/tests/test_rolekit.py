"""役の節を回す共通の口（lib/rolekit.py。P1 計画 Task 13）の検査（FAST: git・盤面の再生・子のプロセスを使わない）。

- ScriptMainCase: 役の返答の読み（parse_reply）
- PointedLangLineCase: 始めの記録の指し札の字から言語の 1 行（pointed_lang_line。読めなくても落ちない）
- GivenUpCase: 回数で諦めた時と出し直させずに諦めた時の 1 行の文（with_done・given_up_reason。回数は GIVE_UP_AFTER の 1 つ）
- RejectWordsCase: 役に返る拒みの文に古い「done し直す」を残さない
- RejectLedgerCase: 拒否の控え rejects-<名>.json の今の回（attempt）と、拒否の全部のファイル（reject_file）
- AcceptRoundCase: 受け付けの回の口 accept_round（読む・take・積む・上限で諦める・count: false と kind・控えの誤りは done 真の拒否）、
  最後の回か（is_last_attempt）、前の版の控えの読み替え（_legacy_rows）
実物の盤面での描画（本線の p2.fix_plan・p2.plan_review）は test_blk_plan（HEAVY）、rejudge.render の本文の一致は test_rejudge が見る。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import rolekit  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()


class ScriptMainCase(Base):
    def test_parse_reply(self):
        self.assertEqual(rolekit.parse_reply('{"a": 1}'), ({"a": 1}, ""))
        self.assertIsNone(rolekit.parse_reply("{x")[0])
        self.assertIn("オブジェクトでない", rolekit.parse_reply("[1]")[1])


class PointedLangLineCase(Base):
    """#367: 始めの記録の指し札の字から言語の 1 行を組む 1 か所。指し札が読めない時は落ちずに既定の言語の 1 行に訳を添える"""

    def test_reads_the_pointed_record(self):
        path = self.tmp / "start.json"
        path.write_text(json.dumps({"lang": "English"}), encoding="utf-8")
        self.assertEqual(rolekit.pointed_lang_line("札", lambda raw: path), rolekit.lang_line({"lang": "English"}))
        self.assertEqual(rolekit.pointed_lang_line("", lambda raw: None), rolekit.lang_line({}))

    def test_unreadable_pointer_degrades(self):
        for error in (ValueError("ほかの run"), TypeError("t"), AttributeError("a"), KeyError("k")):
            def locate(raw, error=error):
                raise error
            with self.subTest(type(error).__name__):
                got = rolekit.pointed_lang_line("札", locate)
                self.assertTrue(got.startswith(rolekit.lang_line({})), got)
                self.assertIn(rolekit.POINTER_UNREAD, got)


class GivenUpCase(Base):
    def test_count_and_at_once_give_up_lines(self):
        """回数で諦めた時と出し直させずに諦めた時（with_done の give_up）で、諦めの 1 行の文が分かれる"""
        for _ in range(2):
            rolekit.with_done(self.tmp, "a", {"ok": False, "reason": "欠け"})
        self.assertEqual(rolekit.given_up_reason(self.tmp, "a"), "")
        rolekit.with_done(self.tmp, "a", {"ok": False, "reason": "欠け\n2 行目"})
        self.assertEqual(rolekit.given_up_reason(self.tmp, "a"),
                         "a の返答が 3 回とも受け付けで拒まれた（最後の拒否: 欠け 2 行目）")
        out = rolekit.with_done(self.tmp, "b", {"ok": False, "reason": "無い"}, give_up=True)
        self.assertTrue(out["done"])
        self.assertEqual(rolekit.given_up_reason(self.tmp, "b"), "b の返答を受け付けが出し直させずに諦めた（拒否: 無い）")


class RejectWordsCase(unittest.TestCase):
    def test_no_board_done_in_lib(self):
        """役に返る拒みの文は「出し直せ」と言う（works-factory に盤面の命令 done は無い。古い「直して done し直す」を残さない）"""
        hits = [f"{p.name}:{n}" for p in sorted(LIB.glob("*.py"))
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if "done し直す" in line]
        self.assertEqual(hits, [])


class RejectLedgerCase(Base):
    def test_attempt_counts_the_kept_rejects(self):
        """輪の今の回は控え rejects-<名>.json の拒否の数 + 1。控えはファイルなので、同じ置き場で数え直さない。通った返答は積まない"""
        self.assertEqual(rolekit.attempt(self.tmp, "eye"), 1)
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = rolekit.with_done(self.tmp, "eye", {"ok": False, "reason": f"拒否 {n}"})
            self.assertEqual((got["done"], rolekit.attempt(self.tmp, "eye")), (n == rolekit.GIVE_UP_AFTER, n + 1))
        self.assertTrue(rolekit.with_done(self.tmp, "other", {"ok": True})["done"])
        self.assertEqual(rolekit.attempt(self.tmp, "other"), 1)
        self.assertIn(f"拒否 {rolekit.GIVE_UP_AFTER}", rolekit.given_up_reason(self.tmp, "eye"))

    def test_reject_file_carries_every_reject_oldest_first(self):
        """次の回の役が名指すファイルに輪の拒否の全部が古い順に在る（#345）。報告の最後の拒否の読み
        （last_reject）はそのファイルを最後の拒否と取り違えない"""
        self.assertEqual(rolekit.reject_file(self.tmp, "plan"), "")
        for n in (1, 2):
            rolekit.with_done(self.tmp, "plan", {"ok": False, "reason": f"拒否 {n}\n2 行目"})
        path = pathlib.Path(rolekit.reject_file(self.tmp, "plan"))
        self.assertEqual(path.name, "rejects-plan.md")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text, rolekit.rejects_text(["拒否 1\n2 行目", "拒否 2\n2 行目"]) + "\n")
        self.assertLess(text.index("1 回目の拒否:\n拒否 1"), text.index("2 回目の拒否:\n拒否 2"))
        self.assertEqual(rolekit.last_reject(self.tmp), "拒否 2 2 行目")
        pasted = rolekit.with_reject("本文", rolekit.rejects_text(rolekit.rejected(self.tmp, "plan")))
        self.assertIn("拒否 1", pasted, "道具ゼロの役に貼る文も全部")


class AcceptRoundCase(Base):
    """受け付けの回の口 rolekit.accept_round。1 回の拒否の定義（読めない返答と take の例外は拒否・count と kind と give_up の読み）は
    口の中にだけ在る"""

    @staticmethod
    def take(reply):
        if reply is None:
            return {"ok": False, "reason": "返答が無い"}
        return {"ok": True, "reason": ""} if reply.get("good") else {"ok": False, "reason": reply.get("why", "欠け")}

    def ledger(self, name):
        return json.loads((self.tmp / f"rejects-{name}.json").read_text(encoding="utf-8"))

    def test_round_reads_takes_counts_and_gives_up_once(self):
        gave_up = []
        call = lambda raw: rolekit.accept_round(self.tmp, "r", raw, self.take, on_give_up=lambda: gave_up.append(1))
        first = call("{")   # 読めない返答は拒否
        self.assertEqual((first["ok"], first["done"]), (False, False))
        self.assertIn("JSON として読めない", first["reason"])
        second = call(json.dumps({"why": "2 つ目"}))
        self.assertEqual((second["ok"], second["done"], second["reason"]), (False, False, "2 つ目"))
        self.assertEqual(gave_up, [])
        third = call(json.dumps({"why": "3 つ目"}))
        self.assertEqual((third["ok"], third["done"]), (False, True))
        self.assertEqual(gave_up, [1], "on_give_up は諦めた 1 回だけ")
        self.assertEqual(len(self.ledger("r")), rolekit.GIVE_UP_AFTER)
        self.assertEqual([r["reason"] for r in rolekit.reject_rows(self.tmp, "r")][1:], ["2 つ目", "3 つ目"])
        text = pathlib.Path(rolekit.reject_file(self.tmp, "r")).read_text(encoding="utf-8")
        self.assertLess(text.index("2 つ目"), text.index("3 つ目"), "全部の拒否が古い順")
        # 同じ置き場で呼び直すと数えを引き継ぐ（resume を跨いで数え直さない）
        self.assertEqual(rolekit.attempt(self.tmp, "r"), rolekit.GIVE_UP_AFTER + 1)
        passed = rolekit.accept_round(self.tmp, "r", json.dumps({"good": True}), self.take)
        self.assertEqual((passed["ok"], passed["done"]), (True, True))
        self.assertEqual(len(self.ledger("r")), rolekit.GIVE_UP_AFTER, "通った返答は積まない")
        self.exception_and_at_once_rounds()

    def exception_and_at_once_rounds(self):
        """take の中の例外は拒否。give_up 真は 1 回目で done。raw が None なら読まずに take(None)"""
        def boom(reply):
            raise RuntimeError("中で落ちた")
        got = rolekit.accept_round(self.tmp, "x", json.dumps({}), boom)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("RuntimeError", got["reason"])
        gave_up = []
        once = rolekit.accept_round(self.tmp, "y", json.dumps({}), lambda r: {"ok": False, "give_up": True, "reason": "直らない"},
                                    on_give_up=lambda: gave_up.append(1))
        self.assertEqual((once["done"], gave_up), (True, [1]), "give_up 真は 1 回目で done")
        self.assertEqual(rolekit.given_up_reason(self.tmp, "y"), "y の返答を受け付けが出し直させずに諦めた（拒否: 直らない）")
        got = rolekit.accept_round(self.tmp, "z", None, lambda r: {"ok": False, "reason": f"take({r})"})
        self.assertEqual(got["reason"], "take(None)", "raw が None なら読まずに take(None)")

    def test_uncounted_round_keeps_the_ledger_and_kind_is_kept(self):
        rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "形", "kind": "format"})
        rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "種類なし"})
        self.assertEqual([r.get("kind") for r in self.ledger("k")], ["format", None], "kind は在る行にだけ残す")
        self.assertEqual([(r["reason"], r.get("kind")) for r in rolekit.reject_rows(self.tmp, "k")], [("形", "format"), ("種類なし", None)])
        self.assertNotIn("kind", rolekit.reject_rows(self.tmp, "k")[1])
        # count: false は積まない。done は give_up が真の時だけ真
        queued = rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "相談に積んだ", "count": False})
        self.assertEqual((queued["ok"], queued["done"]), (False, False))
        self.assertEqual(len(self.ledger("k")), 2, "積んだ回は控えに数えない")
        halted = []
        halt = rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "止める", "count": False, "give_up": True},
                                    on_give_up=lambda: halted.append(1))
        self.assertEqual((halt["ok"], halt["done"], halted), (False, True, [1]))
        self.assertEqual(len(self.ledger("k")), 2, "halt も控えに数えない")

    def test_unusable_ledger_is_a_done_reject_without_on_give_up(self):
        (self.tmp / "rejects-bad.json").mkdir()
        called = []
        got = rolekit.accept_round(self.tmp, "bad", None, lambda _: {"ok": False, "reason": "欠け", "kind": "format"},
                                   on_give_up=lambda: called.append(1))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("拒否の控えが扱えない", got["reason"])
        self.assertEqual(called, [])
        self.assertEqual(got.get("kind"), "format", "take の返りの欄は残る")
        self.assertEqual(rolekit.reject_file_or_blank(self.tmp, "bad"), "", "読み直して落ちない")
        with self.assertRaises(rolekit.BoardGap):
            rolekit.reject_file(self.tmp, "bad")
        # take の中で控えを読んで落ちても、口が done 真の拒否にする（呼び手が口の前に控えを読まなくてよい）
        got = rolekit.accept_round(self.tmp, "bad", None, lambda _: {"ok": True, "n": rolekit.attempt(self.tmp, "bad")})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("拒否の控えが扱えない", got["reason"])

    def test_failing_on_give_up_is_not_called_a_ledger_error(self):
        """諦めた後の処理が落ちても、控えは積めている。理由を『拒否の控えが扱えない』にせず、別の理由の done 真の拒否で返す"""
        def boom():
            raise RuntimeError("裁定が積めない")
        got = rolekit.accept_round(self.tmp, "g", None, lambda _: {"ok": False, "reason": "直らない", "give_up": True}, on_give_up=boom)
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertNotIn("拒否の控えが扱えない", got["reason"])
        self.assertIn("諦めた後の処理が落ちた", got["reason"])
        self.assertIn("裁定が積めない", got["reason"])
        self.assertEqual([r["reason"] for r in self.ledger("g")], ["直らない"], "控えは書けている")

    def test_reject_file_or_blank_blanks_only_an_unreadable_ledger(self):
        """控えが読めない時だけ空。控えは読めて rejects-<名>.md が書けない時は空にせず OSError を上げる"""
        rolekit.with_done(self.tmp, "w", {"ok": False, "reason": "欠け"})
        rolekit.rejects_text_path(self.tmp, "w").mkdir()
        with self.assertRaises(OSError):
            rolekit.reject_file_or_blank(self.tmp, "w")

    def test_last_attempt_is_the_give_up_attempt(self):
        self.assertFalse(rolekit.is_last_attempt(rolekit.GIVE_UP_AFTER - 1))
        self.assertTrue(rolekit.is_last_attempt(rolekit.GIVE_UP_AFTER))
        self.assertTrue(rolekit.is_last_attempt(rolekit.GIVE_UP_AFTER + 1))
        for n in range(rolekit.GIVE_UP_AFTER - 1):
            self.assertFalse(rolekit.is_last_attempt(rolekit.attempt(self.tmp, "last")), n)
            rolekit.accept_round(self.tmp, "last", None, lambda _: {"ok": False, "reason": "欠け"})
        self.assertTrue(rolekit.is_last_attempt(rolekit.attempt(self.tmp, "last")), "拒否が GIVE_UP_AFTER - 1 件の時は最後の回")
        self.assertTrue(rolekit.accept_round(self.tmp, "last", None, lambda _: {"ok": False, "reason": "欠け"})["done"])

    def test_old_ledgers_are_read_once_and_rewritten(self):
        for k, text in ((1, "1 つ目\n"), (2, "2 つ目\n")):
            (self.tmp / f"reject-fix-accept-{k}.md").write_text(text, encoding="utf-8")
        (self.tmp / "reject-fix-accept-extra-1.md").write_text("別の名\n", encoding="utf-8")
        self.assertEqual(rolekit.attempt(self.tmp, "fix-accept"), 3)
        self.assertEqual(rolekit.rejected(self.tmp, "fix-accept"), ["1 つ目", "2 つ目"])
        text = pathlib.Path(rolekit.reject_file(self.tmp, "fix-accept")).read_text(encoding="utf-8")
        self.assertLess(text.index("1 つ目"), text.index("2 つ目"))
        self.assertFalse((self.tmp / "rejects-fix-accept.json").exists(), "読むだけでは書き換えない")
        got = rolekit.accept_round(self.tmp, "fix-accept", None, lambda _: {"ok": False, "reason": "3 つ目"})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertEqual([r["reason"] for r in self.ledger("fix-accept")], ["1 つ目", "2 つ目", "3 つ目"], "一度だけの読み替え")
        # 報告の形（<名>-rejects.json の行 {node, attempt, kind, reason}）
        rows = [{"node": "report", "attempt": 1, "kind": "format", "reason": "表"},
                {"node": "report", "attempt": 2, "kind": "answer", "reason": "型"}]
        (self.tmp / "report-rejects.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        self.assertEqual([(r["reason"], r["kind"]) for r in rolekit.reject_rows(self.tmp, "report")], [("表", "format"), ("型", "answer")])
        self.assertEqual(rolekit.attempt(self.tmp, "report"), 3)
        rolekit.accept_round(self.tmp, "report", None, lambda _: {"ok": False, "reason": "次", "kind": "cold"})
        self.assertEqual([r["kind"] for r in self.ledger("report")], ["format", "answer", "cold"])
        # 新しい控えが在れば前の版の形は読まない
        (self.tmp / "reject-report-1.md").write_text("古い\n", encoding="utf-8")
        self.assertEqual(rolekit.attempt(self.tmp, "report"), 4)


if __name__ == "__main__":
    unittest.main()
