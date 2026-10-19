"""手直しの役の受け付けと指示（docs/design/delta-review.md の 3.8・3.3・10.2 の RefixAcceptCase・RefixPromptCase）。"""
import ast
import hashlib
import importlib
import json
import os
import pathlib
from unittest import mock

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


class WritesLogNameCase(s.Flow):
    """書き込みの記録の名の持ち主は writelog.LOG の 1 か所。手直しの受け付けの既定の置き場はその名を引き、src にほかの写しの字が無い
    （元 lib/tests/test_writes.py の WritesLogNameCase。block の src の字を照らす）"""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.start(), {"due": True, "reason": ""})
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")

    def test_default_record_name_is_writelog_log(self):
        touchup = kit.load(s.BLOCK_NAME, "touchup")
        writelog, writes = importlib.import_module("writelog"), importlib.import_module("writes")
        seen = []

        def check(reply, repo, paths, log, **kw):
            seen.append(pathlib.Path(log))
            return {"problems": ["止める"], "reply": reply}

        reply = self.handled(self.answer(HOLE), self.answer(CHECK))
        with mock.patch.object(writelog, "LOG", "renamed.jsonl"), mock.patch.object(writelog, "log_here", return_value=None), \
                mock.patch.object(writes, "check", check):
            got = touchup.take(self.run.artifacts, 1, reply, self.run.repo, self.read("intake.json")["base"], self.seal)
        self.assertEqual(got["reason"], "止める", got)
        self.assertEqual([p.name for p in seen], ["renamed.jsonl"])

    def test_no_second_copy_of_the_record_name_in_src(self):
        copies = []
        for path in sorted((kit.BLOCKS / "delta-review" / "src").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body
                    and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
            copies += [f"{path.name}:{n.lineno} {n.value!r}" for n in ast.walk(tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
                       and "writes" in n.value and n.value.endswith(".jsonl")]
        self.assertEqual(copies, [], "書き込みの記録の名は writelog.LOG を引く")


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
    def prompt(self, n=1):
        return self.step("refix_prep", n)["prompt"]

    def test_policy_request_and_scope_reach_the_prompt(self):
        policy = self.run.artifacts / "policy.md"
        policy.write_text("# Policy\nNever weaken a test.\n", encoding="utf-8")
        item = s.plan_item(1, ("a.py", "docs/**"), out_of_scope=[{"glob": "secret/**", "why": "owner only"}], tests=[{"id": "tests/test_a.py::test_x"}])
        self.start(plan={"plan_items": [item], "ruled_paths": ["docs/ruled.md"], "agreed": []}, policy=str(policy), permits='["tests/p.py"]',
                   request='[{"where": "a.py", "text": "fix it"}]', lang="Japanese")
        text = self.prompt()
        self.assertIn(f"Human policy document: `{policy}` (read it all first).", text)
        self.assertIn(f"Request file: `{self.run.artifacts / 'request.json'}` (read it all first).", text)
        for line in ("- Item 1 (units: unit-1)", "  - allowed_paths: `a.py`, `docs/**`", "  - test files (ids in tests and rewrite_tests): `tests/test_a.py`",
                     "  - out_of_scope: `secret/**` (owner only)",
                     "- Permits for every item (test-change permits and paths added by fix rulings; they do not beat out_of_scope): `tests/p.py`, `docs/ruled.md`"):
            self.assertIn(line, text)
        self.assertIn("in Japanese", text)
        self.assertIn("Never weaken a test", self.step("review_prep", 1)["prompt"], "方針の本文は審査役にも貼られる")

    def test_no_policy_no_request_no_plan_say_so(self):
        self.start()
        text = self.prompt()
        self.assertIn("Human policy document: none.", text)
        self.assertIn("Request file: none.", text)
        self.assertNotIn("## Paths you may change", text)
        self.assertNotIn("write in `how` which item it conflicts with", text)

    def test_the_writer_rules_carry_the_evidence_kinds_but_not_the_conflict_declarations(self):
        self.start()
        text = self.prompt()
        for part in ("## How to fix", "## Evidence for fixes whose red-to-green a test cannot show", "- Documents:", "- Instructions (prompts):",
                     "- Settings, YAML, workflows:", "- Notes and types:", "## What to keep", "Rules for queries to outside services"):
            self.assertIn(part, text)
        self.assertNotIn("## Conflict declarations", text)
        self.assertNotIn("put this whole block of rules, word for word, into its instructions", text, "下請けを起こさない役")

    def test_seat_names_the_skill_and_the_reinterpretation(self):
        self.start()
        text = self.prompt()
        self.assertIn("Read `receiving-code-review` with the Skill tool", text)
        self.assertIn("審査の指摘を受けて、確かめてから直すか反論する仕事", text)
        self.assertIn("unattended.md", text)
        self.assertIn("Answer **every row of `owed` once**", text)
        self.assertIn("a second review is run on the touch-up-only diff", text)

    def test_the_whole_rejection_history_comes_first_on_the_third_round(self):
        self.start()
        self.write("b.py", "gamma = 4\n")
        for _ in range(2):
            self.refix(1, self.handled(self.answer(HOLE)))
            self.prompt()
        text = self.step("refix_prep", 1)["prompt"]
        self.assertTrue(text.startswith("## Why your previous answer was rejected"))
        self.assertEqual(text.count("回目の拒否:"), 2)

    def test_the_second_round_prompt_is_about_the_touch_up_diff(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")
        self.assertTrue(self.refix(1, self.handled(self.answer(HOLE), self.answer(CHECK)))["ok"])
        self.assertTrue(self.run.script("cut2")["due"])
        reply = s.second_reply(checks=[s.check(HOLE, closed=True), s.check(CHECK, closed=False)])
        self.assertTrue(self.review(2, reply)["ok"])
        self.assertTrue(self.step("owed", 2)["due"])
        text = self.prompt(2)
        self.assertIn("You are the writer who touches up the holes the second diff review raised.", text)
        self.assertIn(str(self.run.artifacts / "delta-2.patch"), text)
        self.assertIn("What you fix here will no longer be reviewed", text)
        self.assertEqual(self.read("refix-2-brief.json")["owed"][0]["key"], CHECK)
        self.assertNotIn("plan_items", self.read("refix-2-brief.json"))


class SealCase(s.Flow):
    """許しの写し（scope.json・permits.json）と範囲の照らしで外すパスの控え（cut-1.json）は入口の後に書き換えられない
    （keep-essence 3: 許す道は 1 本）。印は trace.jsonl と入口の返り seal に在り、seal は Archon が with: で受け付けへ渡す"""

    def marks(self):
        rows = [json.loads(x) for x in (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        return [r for r in rows if r["op"] == "plan_fields_saved"]

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

    def test_a_missing_mark_is_named(self):
        self.start()
        (self.run.artifacts / "trace.jsonl").write_text("", encoding="utf-8")
        got = self.refix(1, self.handled(self.answer("copy-of-the-rule"), self.answer("claimed-closed-hole")))
        self.assertIn("凍結の印が無い", got["reason"])
