"""2 往復の仕組みと出口（docs/design/delta-review.md の 6 節・4 節・5 節・10.2 の RoundsCase・FinishCase）。"""
import json

from tests.blocks.delta_review import support as s

HOLE, CHECK = "copy-of-the-rule", "claimed-closed-hole"


class RoundsCase(s.Flow):
    def fixed_first_round(self, rows=None):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")   # 手直しが書いた
        reply = self.handled(*(rows or [self.answer(HOLE), self.answer(CHECK)]))
        self.assertTrue(self.refix(1, reply)["ok"])

    def test_cut2_waits_for_a_fixed_answer(self):
        self.start()
        self.assertEqual(self.run.script("cut2"), {"due": False, "reason": "1 回目の手直しが fixed と答えた穴が無い"})
        declared = [self.answer(HOLE, handled="declared", files=()), self.answer(CHECK, handled="declared", files=())]
        self.assertTrue(self.refix(1, self.handled(*declared))["ok"])
        self.assertFalse(self.run.script("cut2")["due"], "declared だけなら 2 回目は回さない")
        self.assertFalse(self.exists("cut-2.json"))

    def test_the_second_diff_is_the_touch_up_only(self):
        self.fixed_first_round()
        self.assertEqual(self.run.script("cut2"), {"due": True, "reason": ""})
        patch = (self.run.artifacts / "delta-2.patch").read_text(encoding="utf-8")
        self.assertIn("+gamma = 5", patch)
        self.assertNotIn("+beta = 22", patch, "修正の行は載らない")
        cut1, cut2 = self.read("cut-1.json"), self.read("cut-2.json")
        self.assertEqual((cut2["base"], cut2["files"]), (cut1["rev"], ["a.py"]))
        brief = self.read("review-2-brief.json")
        self.assertEqual([h["key"] for h in brief["handled"]], [HOLE, CHECK])
        self.assertNotIn("lens", brief)
        self.assertNotIn("plan_items", brief)
        self.assertTrue(self.exists("review-2-tree.json"))

    def test_cut2_without_the_first_cut_is_logged_not_fatal(self):
        self.fixed_first_round()
        (self.run.artifacts / "cut-1.json").unlink()
        self.assertFalse(self.run.script("cut2")["due"])
        self.assertIn("cut-2", self.read("errors.json")[0]["node"])

    def test_owed_decides_from_the_record(self):
        self.assertIn("審査を受けていない", self.step("owed", 1)["reason"])
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.assertTrue(self.review(1, s.review_reply(checks=[s.check()]))["ok"])
        self.assertEqual(self.step("owed", 1), {"due": False, "reason": "1 回目の審査が直す義務を出していない（通った）"})
        self.assertFalse(self.exists("refix-1-head.json"))

    def test_a_failing_record_without_owed_rows_stops_instead_of_starting_the_writer(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.assertTrue(self.review(1, s.review_reply(checks=[s.check()]))["ok"])
        record = self.read("review-1.json")
        (self.run.artifacts / "review-1.json").write_text(json.dumps({**record, "pass": False}), encoding="utf-8")
        got = self.step("owed", 1)
        self.assertFalse(got["due"])
        self.assertIn("義務の行が 0 件", got["reason"])
        self.assertFalse(self.exists("refix-1-head.json"))
        self.assertEqual(self.read("errors.json")[-1]["node"], "owed-1")
        self.assertEqual(self.run.script("finish")["status"], "failed")

    def test_owed_after_a_given_up_review_does_not_start_the_writer(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        for _ in range(3):
            self.review(1, s.review_reply(checks=[]))
        self.assertEqual(self.step("owed", 1), {"due": False, "reason": "1 回目の審査を諦めた"})

    def test_the_head_tree_is_kept_when_owed_runs_again(self):
        self.start()
        head = self.read("refix-1-head.json")
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")
        self.assertTrue(self.step("owed", 1)["due"])
        self.assertEqual(self.read("refix-1-head.json"), head, "手直しが書いた後に頭の木を撮り直さない")

    def test_second_review_checks_the_fixed_answers_and_files_of_both_diffs(self):
        self.fixed_first_round()
        self.run.script("cut2")
        bad = s.second_reply(checks=[s.check(HOLE)])
        got = self.review(2, bad)
        self.assertIn("検算が無い", got["reason"])
        self.assertIn(CHECK, got["reason"])
        reply = s.second_reply([s.face(key="touch-up-copied-it", cite="gamma = 5")], [s.check(HOLE), s.check(CHECK, closed=False)])
        self.assertTrue(self.review(2, reply)["ok"])
        self.assertEqual(self.read("review-2.json")["owed"], 2)
        self.assertNotIn("verdicts", json.dumps(self.read("review-2-reply.json")))

    def test_second_review_refuses_a_file_the_touch_up_did_not_touch(self):
        self.fixed_first_round()
        self.run.script("cut2")
        reply = s.second_reply([s.face(key="holes-in-fix-lines", cite="beta = 22")], [s.check(HOLE), s.check(CHECK)])
        reply["faces"][0]["where"] = "b.py"
        got = self.review(2, reply)
        self.assertFalse(got["ok"])
        self.assertIn("この往復の差分が触ったファイルでない", got["reason"])

    def test_inner_words_left_by_the_first_touch_up_are_found_in_the_second_review(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\n# この周の共有ボード\n")
        self.assertTrue(self.refix(1, self.handled(self.answer(HOLE), self.answer(CHECK))).get("ok"))
        self.run.script("cut2")
        self.assertTrue(self.review(2, s.second_reply(checks=[s.check(HOLE), s.check(CHECK)]))["ok"])
        faces = self.read("review-2-reply.json")["faces"]
        self.assertTrue(faces and all(f["kind"] == "inner_word" for f in faces), faces)

    def test_second_review_is_given_up_after_three_rejections(self):
        self.fixed_first_round()
        self.run.script("cut2")
        self.assertEqual([self.review(2, s.second_reply())["done"] for _ in range(3)], [False, False, True])
        self.assertTrue(self.read("review-2.json")["gave_up"])
        self.assertFalse(self.step("owed", 2)["due"])

    def test_there_is_no_third_round_and_the_last_fixed_answers_are_carried(self):
        self.fixed_first_round()
        self.run.script("cut2")
        self.assertTrue(self.review(2, s.second_reply(checks=[s.check(HOLE), s.check(CHECK, closed=False)]))["ok"])
        self.assertTrue(self.step("owed", 2)["due"])
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 6\n")
        self.assertTrue(self.refix(2, self.handled(self.answer(CHECK, how="Closed the second route in the touch-up " + s.LONG)))["ok"])
        self.assertFalse(self.exists("cut-3.json"))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["rounds"], fin["pass"]), (True, "ok", 2, False))
        texts = [c["text"] for c in fin["carry"]]
        self.assertTrue(any("手直し 2 回目が fixed と言ったが、3 回目の審査は無い——検算が要る" in t and t.startswith(CHECK) for t in texts), texts)


class FinishCase(s.Flow):
    def test_the_whole_two_round_run(self):
        self.start()
        self.write("a.py", "alpha = 1\nbeta = 22\ngamma = 5\n")
        self.assertTrue(self.refix(1, self.handled(self.answer(HOLE), self.answer(CHECK, handled="declared", files=(), how="Leave this one " + s.LONG)))["ok"])
        self.run.script("cut2")
        self.assertTrue(self.review(2, s.second_reply(checks=[s.check(HOLE)]))["ok"])
        self.assertEqual(self.step("owed", 2), {"due": False, "reason": "2 回目の審査が直す義務を出していない（通った）"})
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["reason"], fin["rounds"], fin["pass"]), (True, "ok", "", 2, True))
        self.assertEqual(fin["holes"], {"type": "archon_artifact", "run_id": "run-test", "path": "holes.json"})
        holes = self.read("holes.json")
        self.assertEqual(sorted(holes), ["handled", "ties"])
        self.assertEqual([t["key"] for t in holes["ties"]["1"]], [HOLE, CHECK])
        self.assertEqual(holes["ties"]["2"], [])
        self.assertEqual([h["key"] for h in holes["handled"]["1"]], [HOLE, CHECK])
        self.assertEqual(holes["handled"]["2"], [])
        self.assertEqual(fin["diff"], {"type": "archon_artifact", "run_id": "run-test", "path": "delta.diff"})
        diff = (self.run.artifacts / "delta.diff").read_text(encoding="utf-8")
        self.assertTrue("+beta = 22" in diff and "+gamma = 5" in diff, "base から手直しの後までの累積の差分")
        report = fin["report"]
        self.assertEqual(report[0], "- 差分の審査: 2 回（最後の審査は通った）")
        self.assertIn("- 差分の審査の穴の枝（機械が修正案の項目に結んだ名札。手直しの役にも同じ名札を渡した）: 2 件（枝 1 つ 0・2 つ以上の枝にまたがる 0・"
                      "どの枝にも結べない 2・裁定で外れた項目だけ 0。穴の在る組 1）", report)
        self.assertIn("  - copy-of-the-rule: どの枝にも結べない", report)
        self.assertIn("- 手直しの結果（2 件）:", report)
        self.assertTrue(any(x.startswith("  - claimed-closed-hole: 直さずに残すと申告した（declared）——Leave this one") for x in report), report)
        self.assertIn("- レンズを走らせていない（控えが無い）", report)
        self.assertEqual([c["where"] for c in fin["carry"]], ["claimed-closed-hole"])
        self.assertIn("手直しが declared で残した穴", fin["carry"][0]["text"])
        self.assertIn("（枝: どの枝にも結べない）", fin["carry"][0]["text"])

    def test_the_review_given_up_is_gave_up_not_failed(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        for _ in range(3):
            self.review(1, s.review_reply(checks=[]))
        self.step("owed", 1)
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["rounds"], fin["pass"]), (True, "gave_up", 1, False))
        self.assertIn("review-1（1 回目）", fin["reason"])
        self.assertIn("- 差分の審査（1 回目）が 3 回拒まれて諦めた: ", " ".join(fin["report"]))

    def test_the_writer_given_up_is_gave_up(self):
        self.start()
        for _ in range(3):
            self.refix(1, self.handled(self.answer(HOLE)))
        fin = self.run.script("finish")
        self.assertEqual((fin["status"], fin["rounds"], fin["pass"]), ("gave_up", 1, False))
        self.assertIn("refix-1（1 回目）", fin["reason"])
        self.assertTrue(any(x.startswith("- 手直し（1 回目）が 3 回拒まれて諦めた: ") for x in fin["report"]), fin["report"])

    def test_a_round_rejected_but_never_taken_nor_given_up_is_failed(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.review(1, s.review_reply(checks=[]))   # 拒否の後に役か支度の node が落ちた（諦めた役は控えを書く）
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["pass"]), (False, "failed", False))
        self.assertIn("1 回目の審査", fin["reason"])

    def test_a_writer_rejected_but_never_taken_nor_given_up_is_failed(self):
        self.start()
        self.refix(1, self.handled(self.answer(HOLE)))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("1 回目の手直し", fin["reason"])

    def test_a_loop_that_never_ran_is_failed_naming_the_missing_record(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("審査の受け付けの控えが無い", fin["reason"])

    def test_a_writer_that_never_ran_is_failed(self):
        self.start()
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertIn("手直しの受け付けの控えが無い", fin["reason"])

    def test_a_broken_stage_is_failed_with_its_reason(self):
        self.start()
        self.run.script("refix_prep", n="1")
        (self.run.artifacts / "errors.json").write_text(json.dumps([{"node": "refix-1", "reason": "指示が組めない: boom"}]), encoding="utf-8")
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
        self.assertEqual(fin["reason"], "refix-1: 指示が組めない: boom")

    def test_finish_without_an_intake_is_failed_not_a_crash(self):
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["holes"], fin["diff"]), (False, "failed", None, None))
        self.assertIn("入口の控えが無い", fin["reason"])

    def test_unmakeable_prompt_names_the_node_and_stops_the_node(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        (self.run.artifacts / "cut-1.json").unlink()
        self.assertIn("cut-1.json", self.run.failing("review_prep", n="1"))

    def test_lens_counts_and_failed_lenses_reach_the_report_and_carry(self):
        rows = [{"lens": "silent-failure-hunter", "agent": "x", "go": True, "reason": "", "state": "ran", "dropped": 1,
                 "findings": [{"lens": "silent-failure-hunter", "where": "a.py", "cite": "beta", "why": "w"},
                              {"lens": "silent-failure-hunter", "where": "a.py", "cite": "alpha", "why": "w"}]},
                {"lens": "type-design-analyzer", "agent": "y", "go": True, "reason": "", "state": "failed", "findings": []}]
        lens_file = self.file("lens.json", {"rows": rows})
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED), lens_rows=lens_file)
        self.assertTrue(self.review(1, s.review_reply([s.face(cite="beta = 22", lens="silent-failure-hunter")], [s.check()]))["ok"])
        fin = self.run.script("finish")
        text = "\n".join(fin["report"])
        self.assertIn("レンズの発見: 採った 1 件・採らなかった 1 件・形の誤りで捨てた 1 件・落ちたレンズ 1 件", text)
        self.assertIn("  - silent-failure-hunter: 採った 1・採らなかった 1・形の誤りで捨てた 1（出した発見 2）", text)
        self.assertIn("  - 落ちたレンズ type-design-analyzer（再実行の要あり）", text)
        self.assertIn("手直しの差分にはレンズが当たらない（最後のテストで守る）", text)
        carried = {c["where"]: c["text"] for c in fin["carry"]}
        self.assertIn("レンズ type-design-analyzer", carried)
        self.assertIn("落ちて観点を誰も見ていない", carried["レンズ type-design-analyzer"])

    def test_unreadable_lens_rows_are_named_in_the_report_and_carry(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.intake(fix_reply=json.dumps(s.CLAIMED), lens_rows=self.file("lens.json", {"rows": 3}))
        self.review(1, s.review_reply(checks=[s.check()]))
        fin = self.run.script("finish")
        self.assertTrue(any(x.startswith("- レンズの控えが読めない（") and x.endswith("。どのレンズが見たかを確かめられない") for x in fin["report"]), fin["report"])
        self.assertEqual(fin["carry"][0]["where"], "レンズ")
        self.assertIn("再実行の要あり", fin["carry"][0]["text"])

    def test_included_block_writes_holes_and_diff_in_its_own_place(self):
        self.write("a.py", "alpha = 1\nbeta = 22\n")
        self.run.script("intake", "delta-review__intake", base=self.base, plan="", lens_rows="", fix_reply=json.dumps(s.CLAIMED),
                        permits="[]", plan_review="null", policy="", request="[]", lang="")
        fin = self.run.script("finish", "delta-review__finish")
        self.assertEqual(fin["holes"]["path"], "delta-review/holes.json")
        self.assertEqual(fin["diff"]["path"], "delta-review/delta.diff")
        self.assertTrue((self.run.artifacts / "delta-review" / "delta.diff").is_file())

    def test_the_cumulative_diff_is_null_when_nothing_changed(self):
        self.intake(fix_reply=json.dumps(s.CLAIMED))
        self.assertTrue(self.review(1, s.review_reply(checks=[s.check()]))["ok"])
        self.assertIsNone(self.run.script("finish")["diff"])
