"""役の節を回す共通の口（lib/rolekit.py。P1 計画 Task 13）の検査（FAST: git・盤面の再生・子のプロセスを使わない）。

- ScriptMainCase: 役の返答の読み（parse_reply）
- PointedLangLineCase: 始めの記録の指し札の字から言語の 1 行（pointed_lang_line。読めなくても落ちない）
- GivenUpCase: 回数で諦めた時と出し直させずに諦めた時の 1 行の文（with_done・given_up_reason。回数は GIVE_UP_AFTER か、方針 net の
  受け付けの網 NET_AFTER。網の受け付けは 3 回の拒否で諦めず、網に届けば NET_WHY を添える）
- RejectWordsCase: 役に返る拒みの文に古い「done し直す」を残さない
- RejectLedgerCase: 拒否の控え rejects-<名>.json の今の回（attempt）と、拒否の全部のファイル（reject_file）
- AcceptRoundCase: 受け付けの回の口 accept_round（読む・take・積む・上限で諦める・count: false と kind・控えの誤りは done 真の拒否）、
  落ちずに今の回を読む current_round、輪の until が読む 4 つの欄 round_outcome、最後の回か（is_last_attempt）、前の版の控えの読み替え（_legacy_rows）
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


    def test_net_gives_up_only_at_the_net(self):
        """方針 net の拒否は GIVE_UP_AFTER 回では done にならず、控えの行に after: NET_AFTER を残す。given_up_reason は行の after で
        諦めを判じ（3 件の拒否の後は諦めと読まない）、NET_AFTER 回目の拒否で done になった時だけ NET_WHY を添えた諦めの文を返す"""
        for n in range(1, rolekit.NET_AFTER + 1):
            got = rolekit.with_done(self.tmp, "n", {"ok": False, "reason": f"拒否 {n}"}, net=True)
            self.assertEqual(got["done"], n == rolekit.NET_AFTER, n)
            if n == rolekit.GIVE_UP_AFTER:
                self.assertEqual(rolekit.given_up_reason(self.tmp, "n"), "")
        rows = json.loads(rolekit.rejects_path(self.tmp, "n").read_text(encoding="utf-8"))
        self.assertEqual({r["after"] for r in rows}, {rolekit.NET_AFTER})
        why = rolekit.given_up_reason(self.tmp, "n")
        self.assertIn(f"n の返答が {rolekit.NET_AFTER} 回とも受け付けで拒まれた（最後の拒否: 拒否 {rolekit.NET_AFTER}）", why)
        self.assertTrue(why.endswith(rolekit.NET_WHY.format(n=rolekit.NET_AFTER)), why)
        got = rolekit.accept_round(self.tmp, "m", None, lambda _: {"ok": False, "reason": "欠け"}, net=True)
        self.assertFalse(got["done"])


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
        first = call("{")
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
        self.assertEqual((once["done"], gave_up), (True, [1]))
        self.assertEqual(rolekit.given_up_reason(self.tmp, "y"), "y の返答を受け付けが出し直させずに諦めた（拒否: 直らない）")
        got = rolekit.accept_round(self.tmp, "z", None, lambda r: {"ok": False, "reason": f"take({r})"})
        self.assertEqual(got["reason"], "take(None)")

    def test_uncounted_round_keeps_the_ledger_and_kind_is_kept(self):
        rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "形", "kind": "format"})
        rolekit.accept_round(self.tmp, "k", None, lambda _: {"ok": False, "reason": "種類なし"})
        self.assertEqual([r.get("kind") for r in self.ledger("k")], ["format", None], "kind は在る行にだけ残す")
        self.assertEqual([(r["reason"], r.get("kind")) for r in rolekit.reject_rows(self.tmp, "k")], [("形", "format"), ("種類なし", None)])
        self.assertNotIn("kind", rolekit.reject_rows(self.tmp, "k")[1])
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
        # take の中で控えを読んで落ちても、口が done 真の拒否にする
        got = rolekit.accept_round(self.tmp, "bad", None, lambda _: {"ok": True, "n": rolekit.attempt(self.tmp, "bad")})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("拒否の控えが扱えない", got["reason"])

    def test_current_round_reads_the_round_or_returns_the_ledger_reject(self):
        rolekit.accept_round(self.tmp, "o", None, lambda _: {"ok": False, "reason": "欠け"})
        self.assertEqual(rolekit.current_round(self.tmp, "o"), (2, None))
        (self.tmp / "rejects-bad.json").mkdir()
        n, stopped = rolekit.current_round(self.tmp, "bad")
        self.assertEqual((n, stopped["ok"], stopped["done"]), (0, False, True))
        self.assertEqual(stopped["reason"], rolekit.accept_round(self.tmp, "bad", None, lambda _: {"ok": False, "reason": "x"})["reason"],
                         "口の控えの誤りと同じ拒否")
        self.assertEqual(rolekit.round_outcome(stopped), {**stopped, "give_up": True})

    def test_round_outcome_gives_up_only_on_a_done_reject(self):
        for ok, done in ((True, True), (False, False), (False, True)):
            got = rolekit.round_outcome({"ok": ok, "done": done, "reason": "r", "kind": "format"})
            self.assertEqual(got, {"ok": ok, "done": done, "give_up": done and not ok, "reason": "r"})

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


class ResubmitCase(Base):
    """#571: 拒まれた後の出し直しは拒まれた欄だけを返し、受け付けが前の答えの控えと合わせる"""

    def test_merge_fields_replaces_given_fields_and_keeps_the_rest(self):
        prev, part = {"a": [1], "b": "x"}, {"b": "y", "c": 2}
        self.assertEqual(rolekit.merge_fields(prev, part), {"a": [1], "b": "y", "c": 2})
        self.assertEqual((prev, part), ({"a": [1], "b": "x"}, {"b": "y", "c": 2}), "前の答えも出し直しも書き換えない")

    def test_first_reply_is_written_to_the_candidate(self):
        got, why = rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields)
        self.assertEqual((got, why), ({"a": 1}, ""))
        self.assertEqual(json.loads(rolekit.candidate_path(self.tmp, "r").read_text(encoding="utf-8")), {"a": 1})

    def test_resubmit_is_merged_with_the_candidate(self):
        rolekit.resubmitted(self.tmp, "r", {"a": 1, "b": 2}, None, rolekit.merge_fields)
        got, why = rolekit.resubmitted(self.tmp, "r", None, {"b": 3}, rolekit.merge_fields)
        self.assertEqual((got, why), ({"a": 1, "b": 3}, ""))
        self.assertEqual(json.loads(rolekit.candidate_path(self.tmp, "r").read_text(encoding="utf-8")), got)

    def test_bad_replies_are_refused_without_touching_the_candidate(self):
        rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields)
        for reply, part, word in ((None, [1], "出し直しの返答が JSON のオブジェクトでない"),
                                  ("{x", None, "返答が JSON として読めない"), (None, None, "返答が JSON のオブジェクトでない")):
            with self.subTest(reply=reply, part=part):
                got, why = rolekit.resubmitted(self.tmp, "r", reply, part, rolekit.merge_fields)
                self.assertIsNone(got)
                self.assertIn(word, why)
        self.assertEqual(json.loads(rolekit.candidate_path(self.tmp, "r").read_text(encoding="utf-8")), {"a": 1})

    def test_empty_resubmit_keeps_the_previous_answer(self):
        """拒否が作業ツリーのファイルだけを名指した時、役はファイルを直して {} を返す。受け付けは前の答えのまま全体を照らし直す"""
        rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields)
        self.assertEqual(rolekit.resubmitted(self.tmp, "r", None, {}, rolekit.merge_fields), ({"a": 1}, ""))

    def test_resubmit_brief_only_after_a_rejected_round_with_a_candidate(self):
        """前の周が拒まれ（prev が False）、合わせた答えの控えが在る時だけ指示書を書いてパスを返す（resume の 1 周目は prev が空）"""
        self.assertEqual(rolekit.resubmit_brief(self.tmp, "r", False), "", "控えが無い")
        rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields)
        rolekit.with_done(self.tmp, "r", {"ok": False, "reason": "a が違う"})
        for prev in (None, True, ""):
            self.assertEqual(rolekit.resubmit_brief(self.tmp, "r", prev), "", prev)
        path = pathlib.Path(rolekit.resubmit_brief(self.tmp, "r", False))
        self.assertEqual(path.name, "resubmit-r-2.md")
        text = path.read_text(encoding="utf-8")
        for part in ("a が違う", str(rolekit.candidate_path(self.tmp, "r")), rolekit.FIELD_RULES):
            self.assertIn(part, text)

    def test_parse_reply_and_merge_share_the_object_rule(self):
        """R5: 返答が JSON のオブジェクトでない時の文は parse_reply と出し直しの合わせで同じ"""
        self.assertEqual(rolekit.parse_reply("[1]")[1], rolekit.resubmitted(self.tmp, "r", [1], None, rolekit.merge_fields)[1])

    def test_resubmit_without_a_candidate_is_refused(self):
        got, why = rolekit.resubmitted(self.tmp, "r", None, {"a": 1}, rolekit.merge_fields)
        self.assertIsNone(got)
        self.assertIn("出し直しを合わせられない", why)

    def test_unwritable_candidate_is_refused(self):
        rolekit.candidate_path(self.tmp, "r").mkdir()
        got, why = rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields)
        self.assertIsNone(got)
        self.assertIn("書けない", why)

    def test_first_reply_without_a_required_field_is_refused_but_kept(self):
        """#832: 出し直しの役の形を 1 回目の役と同じにしたので、要る欄の欠けは形でなく受け付けが拒む。控えは書くので、次の周の
        出し直しの役は欠けた欄だけを返せる"""
        got, why = rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields, required=("a", "b", "c"))
        self.assertIsNone(got)
        self.assertEqual(why, rolekit.MISSING_FIELDS.format(keys="b, c"))
        self.assertEqual(json.loads(rolekit.candidate_path(self.tmp, "r").read_text(encoding="utf-8")), {"a": 1})
        got, why = rolekit.resubmitted(self.tmp, "r", None, {"b": 2, "c": 3}, rolekit.merge_fields, required=("a", "b", "c"))
        self.assertEqual((got, why), ({"a": 1, "b": 2, "c": 3}, ""))

    def test_merged_answer_without_a_required_field_is_refused(self):
        rolekit.resubmitted(self.tmp, "r", {"a": 1}, None, rolekit.merge_fields, required=("a", "b"))
        got, why = rolekit.resubmitted(self.tmp, "r", None, {}, rolekit.merge_fields, required=("a", "b"))
        self.assertIsNone(got)
        self.assertEqual(why, rolekit.MISSING_FIELDS.format(keys="b"))

    def test_fix_only_field_in_the_first_reply_is_refused(self):
        """#832: 出し直しの役だけが書く欄（形は 1 回目の役と同じなので形が拒まない）は、1 回目の答えに在れば拒み、控えには残さない。
        出し直しの答えに在るのは通す"""
        got, why = rolekit.resubmitted(self.tmp, "r", {"a": 1, "w": True}, None, rolekit.merge_fields, fix_only=("w",))
        self.assertIsNone(got)
        self.assertEqual(why, rolekit.FIX_ONLY_FIELDS.format(keys="w"))
        self.assertEqual(json.loads(rolekit.candidate_path(self.tmp, "r").read_text(encoding="utf-8")), {"a": 1})
        got, why = rolekit.resubmitted(self.tmp, "r", None, {"w": True}, rolekit.merge_fields, fix_only=("w",))
        self.assertEqual((got, why), ({"a": 1, "w": True}, ""))

    def test_merged_answer_goes_through_the_one_accept_round(self):
        """#557: 合わせは take の前段。合わせた答えも合わせられない出し直しも、拒否は accept_parsed が同じ控えに数える"""
        seen = []

        def take(reply):
            seen.append(reply)
            return {"ok": reply.get("b") == 3, "reason": "b が違う"}

        first = rolekit.accept_parsed(self.tmp, "r", rolekit.resubmitted(self.tmp, "r", {"a": 1, "b": 2}, None, rolekit.merge_fields), take)
        bad = rolekit.accept_parsed(self.tmp, "r", rolekit.resubmitted(self.tmp, "r", None, [1], rolekit.merge_fields), take)
        self.assertEqual((first["ok"], first["done"], bad["ok"], bad["done"]), (False, False, False, False))
        self.assertEqual(rolekit.attempt(self.tmp, "r"), 3)
        last = rolekit.accept_parsed(self.tmp, "r", rolekit.resubmitted(self.tmp, "r", None, {"b": 3}, rolekit.merge_fields), take)
        self.assertEqual((last["ok"], last["done"]), (True, True))
        self.assertEqual(seen, [{"a": 1, "b": 2}, {"a": 1, "b": 3}], "合わせられない出し直しは take に渡らない")


if __name__ == "__main__":
    unittest.main()
