"""審査役の返答の受け付けと 2 判定（docs/design/delta-review.md の 2.8・4 節・10.2 の ReviewAcceptCase・VerdictsCase）。"""
import json

from tests.blocks import kit
from tests.blocks.delta_review import support as s

COMPLIANCE_FAIL = {"verdict": "fail", "read": "Read item 1 and the diff of a.py against it.",
                   "items": [{"item": 1, "kind": "missing", "face_key": "missing-in-item-one", "why": "The item said to add a test " + s.LONG}]}


class ReviewAcceptCase(s.Case):
    def setUp(self):
        super().setUp()
        self.write("a.py", "alpha = 1\nbeta = 22\n")

    def start(self, **inputs):
        inputs.setdefault("fix_reply", json.dumps(s.CLAIMED))
        return self.intake(**inputs)

    def rejected(self, reply, n=1, text="", forget=True):
        """拒まれ、輪はまだ続く（done でない）こと。forget なら拒否の控えを消す（1 つの試験で何度も拒ませても 3 回に届かない）"""
        got = self.review(n, reply)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(text, got["reason"])
        self.assertFalse(self.exists(f"review-{n}.json"))
        if forget:
            (self.run.artifacts / f"rejects-review-{n}.json").unlink()
        return got

    def test_a_good_reply_is_taken_and_leaves_the_records(self):
        self.start()
        got = self.review(1, s.review_reply(checks=[s.check()]))
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        self.assertEqual(self.read("review-1.json"), {"pass": True, "owed": 0, "reply_file": str(self.run.artifacts / "review-1-reply.json")})
        reply = self.read("review-1-reply.json")
        self.assertNotIn("compliance", reply, "2 判定の欄は外して受ける")
        self.assertEqual(self.read("verdicts.json")["quality"]["verdict"], "pass")
        rows = [json.loads(x) for x in (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        rows = [r for r in rows if r["op"] != "plan_fields_saved"]   # 入口の凍結の印は SealCase が見る
        self.assertEqual(rows, [{"op": "delta_verdicts_saved", "compliance": "not_applicable", "quality": "pass"}])

    def test_plan_only_kinds_are_rejected(self):
        self.start()
        for kind, text in (("regression", "事前審査だけの語"), ("policy", "事前審査だけの語"), ("precedent", "先行例")):
            with self.subTest(kind=kind):
                self.rejected(s.review_reply([s.face(kind=kind)]), text=text)

    def test_where_must_be_a_changed_file_and_cite_must_be_in_its_current_state(self):
        self.start()
        self.rejected(s.review_reply([s.face(where="b.py", cite="gamma")]), text="触ったファイルでない")
        self.rejected(s.review_reply([s.face(cite="not in the file")]), text="今の姿に無い")
        self.rejected(s.review_reply([s.face(where="no/such.py")]), text="触ったファイルでない")
        good = self.review(1, s.review_reply([s.face(cite="beta = 22")], [s.check()]))
        self.assertTrue(good["ok"])

    def test_duplicate_face_keys_are_rejected(self):
        self.start()
        self.rejected(s.review_reply([s.face(), s.face()], [s.check()]), text="key が重複")

    def test_no_hole_needs_faces_none(self):
        self.start()
        self.rejected(s.review_reply(none="too short", checks=[s.check()]), text="faces_none")

    def test_every_claimed_hole_needs_exactly_one_check(self):
        self.start()
        self.rejected(s.review_reply(), text="検算が無い")
        self.rejected(s.review_reply(checks=[s.check(), s.check()]), text="key が重複")
        self.rejected(s.review_reply(checks=[s.check(), s.check("unclaimed-hole")]), text="塞いだと言われた穴に無い")

    def test_a_tree_moved_by_the_reader_is_rejected(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 23\n")
        self.rejected(s.review_reply(checks=[s.check()]), text="読むだけの役が作業ツリーを変えた")

    def test_new_ignored_or_untracked_files_also_count_as_moved(self):
        self.start()
        self.write("note.txt", "the reader wrote this\n")
        self.rejected(s.review_reply(checks=[s.check()]), text="読むだけの役が作業ツリーを変えた")

    def test_missing_tree_snapshot_is_rejected_naming_it(self):
        self.start()
        (self.run.artifacts / "review-1-tree.json").unlink()
        self.rejected(s.review_reply(checks=[s.check()]), text="作業ツリーの写し")

    def test_a_hole_makes_the_round_owe_and_the_record_says_so(self):
        self.start()
        got = self.review(1, s.review_reply([s.face(cite="beta = 22")], [s.check(closed=False)]))
        self.assertTrue(got["ok"])
        self.assertEqual(self.read("review-1.json")["pass"], False)
        self.assertEqual(self.read("review-1.json")["owed"], 2)

    def test_inner_words_in_added_lines_become_owed_holes(self):
        self.write("a.py", "alpha = 1\n# この単位の key は共有ボードに在る\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        got = self.review(1, s.review_reply(checks=[s.check()]))
        self.assertTrue(got["ok"])
        faces = self.read("review-1-reply.json")["faces"]
        self.assertEqual([f["kind"] for f in faces], ["inner_word"])
        self.assertEqual((faces[0]["where"], faces[0]["key"].split(":")[0]), ("a.py", "inner_word a.py"))
        self.assertEqual(self.read("review-1.json")["owed"], 1)

    def test_a_word_the_target_already_used_before_is_not_counted(self):
        self.write("a.py", "alpha = 1\n# 共有ボードの印\n")
        from tests.bin.gitkit import git
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "word")
        base = git(self.run.repo, "rev-parse", "HEAD")
        self.write("a.py", "alpha = 1\n# 共有ボードの印\n# 共有ボードの別の印\n")
        self.intake(base=base, fix_reply=json.dumps(s.CLAIMED))
        self.assertTrue(self.review(1, s.review_reply(checks=[s.check()]))["ok"])
        self.assertEqual(self.read("review-1-reply.json")["faces"], [])

    def test_gives_up_on_the_third_rejection_and_says_so_in_the_record(self):
        self.start()
        bad = s.review_reply(checks=[])
        self.assertEqual([self.review(1, bad)["done"] for _ in range(3)], [False, False, True])
        record = self.read("review-1.json")
        self.assertEqual((record["pass"], record["owed"], record["reply_file"], record["gave_up"]), (False, 0, "", True))
        self.assertIn("3 回とも受け付けで拒まれた", record["reason"])
        self.assertEqual(len(self.read("rejects-review-1.json")), 3)

    def test_a_late_good_reply_passes_and_keeps_the_earlier_rejections(self):
        self.start()
        self.rejected(s.review_reply(checks=[]), text="検算が無い", forget=False)
        self.assertTrue(self.review(1, s.review_reply(checks=[s.check()]))["ok"])
        self.assertEqual(len(self.read("rejects-review-1.json")), 1)
        self.assertFalse(self.read("review-1.json").get("gave_up"))

    def test_unsaved_verdicts_stop_the_round_and_name_the_stage(self):
        self.start()
        (self.run.artifacts / "verdicts.json").mkdir()   # 控えを置けない
        got = self.review(1, s.review_reply(checks=[s.check()]))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("控えの無いまま先へ進ませない", got["reason"])
        errors = self.read("errors.json")
        self.assertEqual(errors[0]["node"], "review-1-accept")
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("review-1-accept", fin["reason"])

    def test_unreadable_reply_is_a_rejection_not_a_crash(self):
        self.start()
        got = self.run.script("review_accept", n="1", reply="not json")
        self.assertEqual((got["ok"], got["done"]), (False, False))

    def test_a_reply_that_is_not_an_object_is_rejected(self):
        self.start()
        got = self.run.script("review_accept", n="1", reply="[1, 2]")
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("オブジェクトでない", got["reason"])

    def test_input_n_must_be_one_or_two(self):
        self.start()
        self.assertIn("入力 n", self.run.failing("review_accept", n="3", reply="{}"))


class VerdictsCase(s.Case):
    def setUp(self):
        super().setUp()
        self.verdicts = kit.load("delta-review", "verdicts")
        self.write("a.py", "alpha = 1\nbeta = 22\n")

    def gaps(self, reply, items=()):
        return self.verdicts.gaps(reply, list(items))

    def face(self, key="missing-in-item-one"):
        return s.face(key=key, cite="beta = 22")

    def fails(self, reply, text, items=(s.plan_item(1),)):
        got = self.gaps(reply, items)
        self.assertTrue(any(text in g for g in got), (text, got))

    def test_without_items_the_compliance_is_not_applicable_with_no_rows(self):
        self.assertEqual(self.gaps(s.review_reply()), [])
        self.fails(s.review_reply(compliance={"verdict": "pass", "items": [], "read": s.LONG}), "not_applicable にせよ", items=())
        row = {"item": 1, "kind": "unverifiable", "face_key": "", "why": s.LONG}
        self.fails(s.review_reply(compliance={"verdict": "not_applicable", "items": [row], "read": s.LONG}), "空の並びにせよ", items=())

    def test_with_items_not_applicable_is_not_allowed(self):
        self.fails(s.review_reply(compliance={"verdict": "not_applicable", "items": [], "read": s.LONG}), "個在る")

    def test_the_verdict_is_decided_by_the_rows(self):
        face = self.face()
        ok = s.review_reply([face], compliance=COMPLIANCE_FAIL, quality={"verdict": "pass", "why": s.LONG})
        self.assertEqual(self.gaps(ok, [s.plan_item(1)]), [])
        self.fails({**ok, "compliance": {**COMPLIANCE_FAIL, "verdict": "pass"}}, "行から決まる値は fail")
        none = {"verdict": "fail", "items": [], "read": s.LONG}
        self.fails(s.review_reply(compliance=none), "行から決まる値は pass")
        unv = {"verdict": "pass", "items": [{"item": 1, "kind": "unverifiable", "face_key": "", "why": s.LONG}], "read": s.LONG}
        self.fails(s.review_reply(compliance=unv), "行から決まる値は unverifiable")
        unv["verdict"] = "unverifiable"
        self.assertEqual(self.gaps(s.review_reply(compliance=unv), [s.plan_item(1)]), [])

    def test_fail_rows_must_tie_to_a_face_and_unverifiable_rows_must_not(self):
        reply = s.review_reply([self.face("another-hole-key")], compliance=COMPLIANCE_FAIL, quality={"verdict": "fail", "why": s.LONG})
        self.fails(reply, "faces の key に無い")
        unv = {"verdict": "unverifiable", "read": s.LONG, "items": [{"item": 1, "kind": "unverifiable", "face_key": "missing-in-item-one", "why": s.LONG}]}
        self.fails(s.review_reply([self.face()], compliance=unv), "face_key を空にせよ")

    def test_item_numbers_are_in_range_and_held_items_take_no_failing_row(self):
        row = {"item": 3, "kind": "missing", "face_key": "missing-in-item-one", "why": s.LONG}
        comp = {"verdict": "fail", "read": s.LONG, "items": [row]}
        self.fails(s.review_reply([self.face()], compliance=comp, quality={"verdict": "pass", "why": s.LONG}), "番号は 1〜1")
        held = s.plan_item(1, held="a ruling took it out")
        self.fails(s.review_reply([self.face()], compliance=COMPLIANCE_FAIL, quality={"verdict": "pass", "why": s.LONG}), "裁定で直す義務から外れた", items=[held])

    def test_quality_follows_untied_holes(self):
        face = s.face(key="an-untied-hole-key", cite="beta = 22")
        self.fails(s.review_reply([face], quality={"verdict": "pass", "why": s.LONG}), "fail にせよ", items=())
        self.fails(s.review_reply(quality={"verdict": "fail", "why": s.LONG}), "pass にせよ", items=())

    def test_missing_and_malformed_fields_are_named(self):
        self.assertIn("compliance: 無い", self.gaps({"faces": []})[0])
        self.assertTrue(self.gaps({**s.review_reply(), "quality": {"verdict": "great", "why": s.LONG}}))
        self.assertEqual(self.gaps([1]), ["compliance: 返答が object でない（2 判定の欄を読めない）"])

    def test_a_reply_whose_faces_are_not_rows_skips_the_verdicts_but_is_still_taken_apart(self):
        self.assertTrue(self.verdicts.malformed({"faces": "oops"}))
        self.assertTrue(self.verdicts.malformed({"faces": [1]}))
        self.assertFalse(self.verdicts.malformed(s.review_reply()))
        bare, got = self.verdicts.split({"faces": "oops", "compliance": 1, "quality": 2})
        self.assertEqual((bare, got), ({"faces": "oops"}, {"compliance": 1, "quality": 2}))

    def test_split_does_not_change_the_reply_it_was_given(self):
        reply = s.review_reply()
        before = json.dumps(reply)
        bare, got = self.verdicts.split(reply)
        self.assertEqual(json.dumps(reply), before)
        self.assertEqual(sorted(got), ["compliance", "quality"])
        self.assertEqual(sorted(bare), ["checks", "faces", "faces_none"])

    def test_accept_ties_compliance_rows_into_the_owed_holes_and_the_ties(self):
        self.intake(plan=self.file("plan.json", [s.plan_item(1)]), fix_reply=json.dumps(s.CLAIMED))
        reply = s.review_reply([self.face()], [s.check()], compliance=COMPLIANCE_FAIL, quality={"verdict": "pass", "why": s.LONG})
        self.assertTrue(self.review(1, reply)["ok"])
        self.assertEqual([r["face_key"] for r in self.verdicts.fail_rows(self.read("verdicts.json"))], ["missing-in-item-one"])
        self.step("owed", 1)
        brief = self.read("refix-1-brief.json")
        self.assertEqual(brief["compliance"][0]["item"], 1)
        tie = {t["key"]: t for t in brief["ties"]}["missing-in-item-one"]
        self.assertEqual(tie["branches"], ["項目 1"])
        self.assertIn("compliance", tie["via"])

    def test_accept_rejects_bad_verdicts_with_the_fixed_head(self):
        self.intake(plan=self.file("plan.json", [s.plan_item(1)]), fix_reply=json.dumps(s.CLAIMED))
        got = self.review(1, s.review_reply(checks=[s.check()]))   # 項目が在るのに not_applicable
        self.assertEqual(got["ok"], False)
        self.assertIn(self.verdicts.REJECT, got["reason"])
        self.assertFalse(self.exists("verdicts.json"), "拒否では控えを置かない")

    def test_fail_rows_ignores_unreadable_records(self):
        self.assertEqual(self.verdicts.fail_rows(None), [])
        self.assertEqual(self.verdicts.fail_rows({"compliance": "x"}), [])
