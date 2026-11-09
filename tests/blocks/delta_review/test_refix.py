"""手直しの役の受け付けと凍結の印（docs/design/delta-review.md の 3.8・3.3・10.2 の RefixAcceptCase・SealCase）。"""
import hashlib
import json
import os

import yaml

from tests.blocks import kit
from tests.blocks.delta_review import support as s

HOLE, CHECK = "copy-of-the-rule", "claimed-closed-hole"


class RefixAcceptCase(s.Flow):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.start(), {"due": True, "reason": ""})
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")   # 手直しが書いた

    def both(self, **more):
        return self.handled(self.answer(HOLE, **more), self.answer(CHECK, **more))

    def rejected(self, reply, text, forget=True):
        got = self.refix(1, reply)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(text, got["reason"])
        self.assertFalse(self.exists("refix-1-reply.json"))
        if forget:
            (self.run.artifacts / "rejects-refix-1.json").unlink()
        return got

    def trace(self):
        rows = [json.loads(x) for x in (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        return [r for r in rows if r["op"] != "plan_fields_saved"]   # 入口の凍結の印は SealCase が見る

    def test_the_owed_rows_are_the_holes_and_the_unclosed_checks(self):
        brief = self.read("refix-1-brief.json")
        self.assertEqual([(r["key"], r["from"]) for r in brief["owed"]], [(HOLE, "review-1"), (CHECK, "review-1.checks")])
        self.assertTrue(brief["owed"][0]["text"].startswith("copy a.py:「beta = 22」——"))
        self.assertTrue(brief["owed"][1]["text"].startswith("塞いだと言われたが、差分で塞がっていない"))
        self.assertEqual(brief["diff_file"], str(self.run.artifacts / "delta-1.patch"))
        self.assertEqual(brief["compliance"], [])

    def test_a_good_reply_is_taken_and_traced(self):
        got = self.refix(1, self.both())
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        self.assertEqual([h["key"] for h in self.read("refix-1-reply.json")["handled"]], [HOLE, CHECK])
        self.assertEqual([r["op"] for r in self.trace()], ["delta_verdicts_saved", "writes_unrecorded_run", "refix_accepted"])
        self.assertEqual(self.trace()[-1], {"op": "refix_accepted", "node": "refix-1-accept", "iteration": 1, "done": True})

    def test_every_owed_key_is_answered_exactly_once(self):
        self.rejected(self.handled(self.answer(HOLE)), "応答が無い")
        self.rejected(self.handled(self.answer(HOLE), self.answer(HOLE), self.answer(CHECK)), "key が重複")
        self.rejected(self.handled(self.answer(HOLE), self.answer(CHECK), self.answer("not-an-owed-key")), "差分の審査に無い")

    def test_fixed_needs_files_but_declared_does_not(self):
        self.rejected(self.handled(self.answer(HOLE, files=()), self.answer(CHECK)), "files が空")
        ok = self.handled(self.answer(HOLE), self.answer(CHECK, handled="declared", files=(), how="Leave it " + s.LONG))
        self.assertTrue(self.refix(1, ok)["ok"])

    def test_a_change_that_is_declared_nowhere_is_rejected_until_declared(self):
        self.write("b.py", "gamma = 4\n")
        self.rejected(self.both(), "handled[].files にも bash_writes にも無い")
        reply = {**self.both(), "bash_writes": [{"path": "b.py", "why": "wrote it with a shell heredoc"}]}
        self.assertTrue(self.refix(1, reply)["ok"])
        self.assertNotIn("bash_writes", self.read("refix-1-reply.json"))

    def test_a_declaration_in_handled_files_counts(self):
        self.write("b.py", "gamma = 4\n")
        reply = self.handled(self.answer(HOLE, files=("a.py", "b.py")), self.answer(CHECK))
        self.assertTrue(self.refix(1, reply)["ok"])

    def test_bash_writes_need_a_reason(self):
        reply = {**self.both(), "bash_writes": [{"path": "a.py", "why": "x"}]}
        got = self.rejected(reply, "理由")
        self.assertIn("bash_writes", got["reason"])

    def test_the_write_record_file_is_read_when_it_exists(self):
        """書き込みの記録が在る run は、記録にも申告にも無い変更を拒む。記録に在る変更は通す"""
        log = self.run.artifacts / "writes.jsonl"
        log.write_text("", encoding="utf-8")
        got = self.rejected(self.both(), "書き込みの記録（Edit・Write）も申告")
        self.assertIn("a.py", got["reason"])
        sha = hashlib.sha256((self.run.repo / "a.py").read_bytes()).hexdigest()
        log.write_text(json.dumps({"path": os.path.realpath(self.run.repo / "a.py"), "file_sha": sha}) + "\n", encoding="utf-8")
        self.assertTrue(self.refix(1, self.both())["ok"])
        self.assertNotIn("writes_unrecorded_run", [r["op"] for r in self.trace()], "記録が在る run は知らせを残さない")

    def test_gives_up_on_the_third_rejection_and_keeps_the_work_tree(self):
        bad = self.handled(self.answer(HOLE))
        self.assertEqual([self.refix(1, bad)["done"] for _ in range(3)], [False, False, True])
        self.assertEqual((self.run.repo / "a.py").read_text(encoding="utf-8"), "alpha = 1\nbeta = 22\ngamma = 5\n", "手直しは戻さない")
        self.assertEqual([r["op"] for r in self.trace()][-3:], ["refix_rejected"] * 3)
        self.assertEqual([r["done"] for r in self.trace()[-3:]], [False, False, True])
        self.assertFalse(self.exists("refix-1-reply.json"))

    def test_a_reply_that_is_not_an_object_is_rejected(self):
        self.rejected([self.answer(HOLE)], "JSON のオブジェクトでない")

    def test_a_missing_head_tree_stops_the_writer_and_the_run_is_failed(self):
        (self.run.artifacts / "refix-1-head.json").unlink()
        got = self.refix(1, self.both())
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("refix-1-head.json", got["reason"])
        self.assertEqual(self.read("errors.json")[-1]["node"], "refix-1-accept")
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))

    def test_unreadable_reply_is_a_rejection(self):
        got = self.run.script("refix_accept", n="1", reply="nope")
        self.assertEqual((got["ok"], got["done"]), (False, False))


class RefixScopeCase(s.Flow):
    """承認済みの修正案の項目の範囲の照らし（planrange.outside。修正の段が触ったファイルの外）"""

    def begin(self, items, **inputs):
        self.start(plan={"plan_items": items, "ruled_paths": inputs.pop("ruled", []), "agreed": []}, **inputs)

    def answer_all(self, *paths):
        return self.handled(self.answer(HOLE, files=paths or ("a.py",)), self.answer(CHECK, files=paths or ("a.py",)))

    def test_a_change_outside_every_item_is_rejected_and_the_fix_steps_own_files_are_not_checked(self):
        self.begin([s.plan_item(1, ("docs/**",))])
        self.write("a.py", "alpha = 1\nbeta = 23\n")   # 修正の段が触ったファイル（1 回目の差分の files）は範囲の外でも照らさない
        self.assertTrue(self.refix(1, self.answer_all())["ok"])

    def test_a_new_file_outside_the_scope_is_rejected(self):
        self.begin([s.plan_item(1, ("docs/**",))])
        self.write("c.py", "x = 1\n")
        got = self.refix(1, self.answer_all("a.py", "c.py"))
        self.assertFalse(got["ok"])
        self.assertIn("承認済みの修正案の項目の範囲から外れた", got["reason"])
        self.assertIn("c.py はどの項目の allowed_paths にも無い", got["reason"])

    def test_out_of_scope_beats_the_scope(self):
        self.begin([s.plan_item(1, ("**",), out_of_scope=[{"glob": "c.py", "why": "do not touch"}])])
        self.write("c.py", "x = 1\n")
        got = self.refix(1, self.answer_all("a.py", "c.py"))
        self.assertIn("c.py は項目 1 の out_of_scope（c.py）に当たる", got["reason"])

    def test_permits_and_ruled_paths_let_a_path_through(self):
        for kind in ("permits", "ruled"):
            with self.subTest(kind=kind):
                self.setUp()
                inputs = {"permits": '["c.py"]'} if kind == "permits" else {"ruled": ["c.py"]}
                self.begin([s.plan_item(1, ("docs/**",))], **inputs)
                self.write("c.py", "x = 1\n")
                self.assertTrue(self.refix(1, self.answer_all("a.py", "c.py"))["ok"])

    def test_a_scope_consultation_agreement_is_already_in_allowed_paths(self):
        item = s.plan_item(1, ("docs/**", "c.py"), out_of_scope_lifted=["c.py"])
        self.begin([item])
        self.write("c.py", "x = 1\n")
        self.assertTrue(self.refix(1, self.answer_all("a.py", "c.py"))["ok"])

    def test_a_run_without_a_plan_is_not_checked(self):
        self.start()
        self.write("c.py", "x = 1\n")
        self.assertTrue(self.refix(1, self.answer_all("a.py", "c.py"))["ok"])


class RefixPromptCase(s.Flow):
    def test_the_whole_rejection_history_comes_first_on_the_third_round(self):
        """拒まれた周の次の手直しの指示は、輪の拒否の全部を古い順に頭に置く（prep が rolekit の控えを読む配線。最後の 1 件だけに
        しても、ほかの試験は赤にならない）"""
        self.start()
        self.write("b.py", "gamma = 4\n")
        for _ in range(2):
            self.refix(1, self.handled(self.answer(HOLE)))
            self.step("refix_prep", 1)
        text = self.step("refix_prep", 1)["prompt"]
        self.assertTrue(text.startswith("## Why your previous answer was rejected"))
        self.assertEqual(text.count("回目の拒否:"), 2)


class SealCase(s.Flow):
    """許しの写し（scope.json・permits.json）と範囲の照らしで外すパスの控え（cut-1.json）は入口の後に書き換えられない
    （keep-essence 3: 許す道は 1 本）。印は trace.jsonl と入口の返り seal に在り、seal は Archon が with: で受け付けへ渡す"""

    def marks(self):
        rows = [json.loads(x) for x in (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        return [r for r in rows if r["op"] == "plan_fields_saved"]

    def test_the_seal_reaches_every_accept_through_with_outside_the_roles(self):
        """入口の凍結の印は Archon が持ち、役の手の届かない with: で 4 つの受け付けへ渡る（YAML の配線。手元の確かめは筋書きを回さないので
        ここで見る。印の無い受け付けが配線の誤りを名指すのは test_an_accept_without_the_seal_names_the_wiring）"""
        doc = yaml.safe_load((kit.BLOCKS / s.BLOCK_NAME / "works-factory-delta-review.yaml").read_text(encoding="utf-8"))
        loops = {n["id"]: {x["id"]: x for x in n["loop_group"]["nodes"]} for n in doc["nodes"] if "loop_group" in n}
        for n in (1, 2):
            for kind in ("review", "refix"):
                self.assertEqual(loops[f"{kind}-{n}-loop"][f"{kind}-{n}-accept"]["with"],
                                 {"n": n, "reply": f"${kind}-{n}.output", "seal": "$intake.output.seal"})

    def test_intake_seals_the_copies_in_the_planmarks_mark_shape_and_returns_the_marks(self):
        self.start()
        marks = {r["file"]: r for r in self.marks()}
        self.assertEqual(sorted(marks), ["cut-1.json", "permits.json", "scope.json"])
        for name, row in marks.items():
            digest = hashlib.sha256((self.run.artifacts / name).read_bytes()).hexdigest()
            self.assertEqual((row["round"], row["sha256"], self.seal[name]), (1, digest, digest))

    def test_an_edited_copy_with_a_rewritten_mark_is_caught_by_the_seal_archon_holds(self):
        self.start()
        target = self.run.artifacts / "permits.json"
        target.write_text('["anything.py"]', encoding="utf-8")
        trace = self.run.artifacts / "trace.jsonl"
        old = next(r["sha256"] for r in self.marks() if r["file"] == "permits.json")
        trace.write_text(trace.read_text(encoding="utf-8").replace(old, hashlib.sha256(target.read_bytes()).hexdigest()), encoding="utf-8")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("permits.json", got["reason"])
        self.assertEqual(self.run.script("finish")["status"], "failed")

    def test_a_second_mark_is_caught(self):
        self.start()
        target = self.run.artifacts / "permits.json"
        target.write_text('["anything.py"]', encoding="utf-8")
        with open(self.run.artifacts / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"op": "plan_fields_saved", "round": 1, "file": "permits.json",
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}) + "\n")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("凍結の印が重なった", got["reason"])

    def test_a_rewritten_cut_stops_the_writers_accept(self):
        self.start()
        cut = self.read("cut-1.json")
        (self.run.artifacts / "cut-1.json").write_text(json.dumps({**cut, "files": [*cut["files"], "b.py"]}), encoding="utf-8")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("cut-1.json", got["reason"])

    def test_an_unreadable_copy_is_named(self):
        self.start()
        (self.run.artifacts / "permits.json").unlink()
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("写し permits.json が読めない", got["reason"])

    def test_an_accept_without_the_seal_names_the_wiring(self):
        self.start()
        reply = self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole"))
        got = self.run.script("refix_accept", n="1", reply=json.dumps(reply))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("with:", got["reason"])

    def test_a_rewritten_copy_stops_the_writers_accept_and_the_run_is_failed(self):
        self.start()
        (self.run.artifacts / "permits.json").write_text('["anything.py"]', encoding="utf-8")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("permits.json", got["reason"])
        self.assertFalse(self.exists("refix-1-reply.json"))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("permits.json", fin["reason"])

    def test_a_rewritten_scope_stops_the_review_accept(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        (self.run.artifacts / "scope.json").write_text('{"plan_items": [], "ruled_paths": ["x"], "agreed": []}', encoding="utf-8")
        got = self.review(1, s.review_reply(checks=[s.check()]))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertEqual(self.run.script("finish")["status"], "failed")
        # 印の置き場の trace.jsonl が壊れた時の審査の受け付けも、書き換えの訳でなく、壊れた行の番号で trace.jsonl を名指す
        trace = self.run.artifacts / "trace.jsonl"
        broken = len(trace.read_text(encoding="utf-8").splitlines()) + 1
        with open(trace, "a", encoding="utf-8") as f:
            f.write("{not json\n")
        got = self.review(1, s.review_reply(checks=[s.check()]))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        reason = self.read("errors.json")[-1]["reason"]
        for text in (got["reason"], reason):
            self.assertIn("trace.jsonl が読めない・壊れている", text)
            self.assertIn(f"{broken} 行目", text)
            self.assertNotIn("line 1 column", text)
            self.assertNotIn("入口の後に変わった", text)

    def assert_named_as_the_trace(self, got):
        self.assertEqual((got["ok"], got["done"]), (False, True))
        reason = self.read("errors.json")[-1]["reason"]
        for text in (got["reason"], reason):
            self.assertIn("trace.jsonl が読めない・壊れている", text)
            self.assertNotIn("入口が置いていない", text)
            self.assertNotIn("入口の後に変わった", text)

    def test_a_broken_trace_line_is_named_as_the_trace(self):
        self.start()
        with open(self.run.artifacts / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write("{not json\n")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assert_named_as_the_trace(got)

    def test_a_missing_trace_is_named_as_the_trace(self):
        self.start()
        (self.run.artifacts / "trace.jsonl").unlink()
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assert_named_as_the_trace(got)

    def test_a_missing_mark_is_named(self):
        self.start()
        (self.run.artifacts / "trace.jsonl").write_text("", encoding="utf-8")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertIn("凍結の印が無い", got["reason"])
