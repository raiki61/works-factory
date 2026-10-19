"""診断の block を script を子のプロセスで回して確かめる（docs/design/diagnose.md の 9.2）。始めの記録の無い使い捨ての run directory と
種のリポジトリで、port の値だけを渡し、intake → prep → 台本の返答 → accept → finish と回す。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。"""
import json
import unittest

import yaml

from tests.blocks import kit
from tests.blocks.diagnose import support
from tests.blocks.diagnose.support import CLAMP, MEAN, REQUEST, judge_ok
from tests.blocks.diagnose.test_inputs import PORTS
from tests.blocks.diagnose.test_rejudge import FIRST, OBJECTION, UNIT_A, reply as rejudge_reply

OPEN_WORLD = {"finding": 1, "where": "stats.py", "class_id": "w-1", "problem": "p", "activity": "a", "practice": "x", "sources": [],
              "applies": "a", "not_applies": "", "versus": {"proposed": "p", "verdict": "same", "challenge": ""}, "basis": "knowledge"}
BLOCK = kit.BLOCKS / "diagnose"


def dump(value):
    return json.dumps(value, ensure_ascii=False)


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.art = self.run.artifacts

    def intake(self, **ports):
        return self.run.script("intake", **{**PORTS, **ports})

    def prep(self):
        return self.run.script("diagnose_prep")

    def accept(self, reply):
        return self.run.script("diagnose_accept", reply=dump(reply))

    def finish(self, objection=""):
        return self.run.script("finish", objection=objection)

    def doc(self, name):
        return json.loads((self.art / name).read_text(encoding="utf-8"))


class JudgePathCase(_Base):
    def test_open_units_make_it_ready(self):
        self.assertTrue(self.intake()["due"])
        self.assertIn("You are the judgment role of this run.", self.prep()["prompt"])
        got = self.accept(judge_ok())
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""}, "返りは output_format の 3 欄だけ")
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["mode"], out["stop_reason"], out["reason"]), (True, "ok", "judge", "", ""))
        self.assertTrue(out["ready"])
        self.assertEqual([u["id"] for u in out["units"]], [MEAN, CLAMP])
        self.assertEqual(out["units"][0]["paths"], ["stats.py"])
        self.assertEqual(out["judgment"], {"type": "archon_artifact", "run_id": "run-test", "path": "judgment.json"})
        for field, rel in (("inputs", "diagnose-input.json"), ("brief", "diagnose-prompt-1.md"), ("materials", "materials.json")):
            self.assertEqual(out[field]["path"], rel)
        self.assertIsNone(out["answer_ties"])
        self.assertIsNone(out["rejudge_exit"])
        self.assertEqual(out["downgrades"], [{"what": "再審は判定役の会話を継がず、保存した返答を読む新しい会話で回す",
                                              "versus": "review-graph と今の works は判定役の会話を継ぐ"}])
        self.assertEqual(out["questions"], [])

    def test_questions_are_the_ones_asked_of_a_person(self):
        self.intake()
        reply = judge_ok()
        reply["questions"] = [
            {"key": "岐路", "kind": "fork", "status": "held", "reason": "推し: A——安い", "origin": MEAN, "options": ["A: 安い", "B: 堅い"]},
            {"key": "実機", "kind": "field", "status": "held", "reason": "実機が要る"}]
        reply["precedents"].append({"key": "岐路", "problem": "選び方の問題", "source": "文書の節", "verdict": "adopt", "reason": "当たった",
                                    "undecided_because": "① 先例が割れて決まらない"})
        self.assertTrue(self.accept(reply)["ok"])
        out = self.finish()
        self.assertEqual([q["key"] for q in out["questions"]], ["岐路"], "人へ回す問いは fork の held と escalate の問いだけ")

    def test_no_open_units_is_not_a_stop(self):
        self.intake()
        reply = {**judge_ok(), "units": [], "one_shot": "", "one_shot_closes": [], "precedents": []}
        self.assertTrue(self.accept(reply)["ok"])
        out = self.finish()
        self.assertEqual((out["ok"], out["ready"], out["stop_reason"], out["units"]), (True, False, "", []))

    def test_three_rejections_give_up_with_the_last_reason(self):
        self.intake()
        bad = judge_ok()
        bad["units"][0]["label"] = "major"
        outs = []
        for _ in range(3):
            self.prep()
            outs.append(self.accept(bad))
        self.assertEqual([o["done"] for o in outs], [False, False, True])
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"], out["ready"]), (False, "failed", "works:judge", False))
        self.assertIn("3 回とも", out["reason"])
        self.assertIn("major", out["reason"])
        self.assertEqual(out["units"], [])
        self.assertEqual(self.doc("judgment.json")["units"], [], "judgment はいつも在る")
        self.assertTrue(out["report"][0].startswith("判定: "), out["report"])
        prompt = (self.art / "diagnose-prompt-3.md").read_text(encoding="utf-8")
        self.assertIn("2 回目の拒否", prompt, "輪の却下の全部が古い順に次の指示に入る")

    def test_loop_that_ended_before_giving_up_names_the_last_rejection(self):
        self.intake()
        bad = judge_ok()
        bad["units"][0]["label"] = "major"
        self.accept(bad)
        out = self.finish()
        self.assertEqual((out["status"], out["stop_reason"]), ("failed", "works:judge"))
        self.assertIn("major", out["reason"])

    def test_no_reply_recorded(self):
        self.intake()
        out = self.finish()
        self.assertEqual((out["status"], out["stop_reason"]), ("failed", "works:judge"))
        self.assertIn("判定役の返答を受けた記録が無い", out["reason"])

    def test_given_up_material_returns_stopped_without_waking_the_role(self):
        gave = self.run.pointer("hy/material.json")
        (self.art / "hy").mkdir()
        (self.art / "hy" / "material.json").write_text(dump({"role": "hygiene", "status": "gave_up", "reason": "衛生の役を諦めた", "reply": None,
                                                              "materials": {}, "base": None, "commits": None}), encoding="utf-8")
        got = self.intake(materials=dump([json.loads(gave)]))
        self.assertFalse(got["due"])
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"], out["reason"]), (False, "stopped", "works:material", "衛生の役を諦めた"))
        self.assertEqual(out["units"], [])
        self.assertIsNone(out["answer_ties"])
        self.assertEqual(out["inputs"]["path"], "diagnose-input.json")

    def test_unreadable_request_is_works_request(self):
        self.intake(request='{"where": "x"}')
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:request"))
        self.assertIn("入力 request", out["reason"])
        self.assertEqual(out["judgment"]["path"], "judgment.json")

    def test_prompt_error_reason_reaches_the_exit(self):
        self.intake()
        (self.art / "prompts-broken").mkdir()
        doc = self.doc("intake.json")
        doc["values"].pop("depth_why")
        (self.art / "intake.json").write_text(dump(doc), encoding="utf-8")
        err = self.run.failing("diagnose_prep")
        self.assertIn("KeyError", err)
        self.assertEqual(self.doc("prompt-error.json")["node"], "diagnose-prep")
        out = self.finish()
        self.assertEqual((out["status"], out["stop_reason"]), ("failed", "works:judge"))
        self.assertIn("KeyError", out["reason"])

    def test_answer_ties_and_out_of_purpose_are_pointed_at(self):
        self.intake(answers=dump([{"question": "どれを採るか", "text": "A"}]))
        reply = judge_ok()
        reply["answer_ties"] = [{"answer": "どれを採るか", "to": MEAN}]
        reply["out_of_purpose"] = [{"source": "依頼", "where": "stats.py", "text": REQUEST[0]["text"], "why_outside": "凍結した目的の外だと判断した"}]
        got = self.accept(reply)
        self.assertTrue(got["ok"], got)
        out = self.finish()
        self.assertEqual((out["answer_ties"]["path"], out["out_of_purpose"]["path"]), ("answer-ties.json", "out-of-purpose.json"))
        self.assertTrue(any("目的の外" in line for line in out["report"]), out["report"])

    def test_report_names_unproven_queries(self):
        self.intake()
        self.assertTrue(self.accept(judge_ok())["ok"])
        out = self.finish()
        self.assertTrue(any(line.startswith("例で証明できない判定の問い: 2 件") for line in out["report"]), out["report"])


class FinishNeverFailsCase(_Base):
    def test_no_intake_at_all(self):
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:judge"))
        self.assertIn("intake.json が読めない", out["reason"])
        self.assertEqual(out["judgment"]["path"], "judgment.json")
        self.assertTrue((self.art / "judgment.json").is_file())

    def test_rejudge_without_intake(self):
        out = self.finish(objection="異議")
        self.assertEqual((out["mode"], out["stop_reason"]), ("rejudge", "works:rejudge"))

    def test_broken_judgment_file_falls_back(self):
        self.intake()
        self.assertTrue(self.accept(judge_ok())["ok"])
        (self.art / "judgment.json").write_text("{not json", encoding="utf-8")
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:judge"))
        self.assertTrue(out["reason"].startswith("判定の出口が落ちた（"), out["reason"])
        self.assertEqual(out["judgment"]["path"], "judgment.json")
        self.assertEqual(out["downgrades"][0]["versus"], "review-graph と今の works は判定役の会話を継ぐ")
        self.assertEqual(len(out["report"]), 1)

    def test_value_that_json_cannot_hold_falls_back(self):
        self.intake()
        self.assertTrue(self.accept(judge_ok())["ok"])
        doc = self.doc("judgment.json")
        (self.art / "judgment.json").write_text(json.dumps({**doc, "questions": [{"key": "q", "kind": "field", "status": "escalate", "reason": float("nan")}]}),
                                                encoding="utf-8")
        out = self.finish()
        self.assertEqual((out["ok"], out["status"]), (False, "failed"))
        self.assertTrue(out["reason"].startswith("判定の出口が落ちた（"), out["reason"])


class RejudgePathCase(_Base):
    def rejudge_intake(self, **extra):
        return self.run.script("intake", **{**PORTS, "objection": OBJECTION, "prior": dump(FIRST), **extra})

    def test_accepted_rejudge(self):
        self.assertEqual(self.rejudge_intake()["mode"], "rejudge")
        prompt = self.run.script("rejudge_prep")["prompt"]
        self.assertIn("You are woken to reconsider this run's judgment.", prompt)
        self.assertIn(OBJECTION, prompt)
        got = self.run.script("rejudge_accept", reply=dump(rejudge_reply()))
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        out = self.finish(objection=OBJECTION)
        self.assertEqual((out["ok"], out["mode"], out["status"], out["rejudge_verdict"]), (True, "rejudge", "ok", "一部採る"))
        self.assertTrue(out["ready"])
        self.assertEqual([u["id"] for u in out["units"]], [UNIT_A], "開いた単位だけ（UNIT_B は nit に下がった）")
        self.assertEqual(out["rejudge_exit"]["path"], "rejudge-exit.json")
        self.assertEqual(out["rejudge_diff"]["path"], "rejudge-diff.json")
        for field in ("inputs", "brief", "materials", "out_of_purpose", "answer_ties"):
            self.assertIsNone(out[field], field)
        judgment = self.doc("judgment.json")
        self.assertEqual({k: judgment[k] for k in FIRST if k != "units"}, {k: FIRST[k] for k in FIRST if k != "units"})
        self.assertTrue(any(line.startswith("再審の結果（1 往復）: 一部採る（異議: ") for line in out["report"]), out["report"])
        self.assertTrue(any("争点でない単位が変わった" in line for line in out["report"]), out["report"])

    def test_no_first_judgment_stops_the_session(self):
        got = self.run.script("intake", **{**PORTS, "objection": "異議", "prior": "null"})
        self.assertEqual((got["due"], got["mode"]), (False, "rejudge"))
        out = self.finish(objection="異議")
        self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:rejudge-session"))
        self.assertEqual(out["units"], [])
        self.assertTrue((self.art / "judgment.json").is_file())
        self.assertIsNone(out["rejudge_verdict"])

    def test_three_rejections_stop_as_rejudge(self):
        self.rejudge_intake()
        for _ in range(3):
            self.run.script("rejudge_prep")
            got = self.run.script("rejudge_accept", reply=dump(rejudge_reply(new_facts="確かめた")))
        self.assertTrue(got["done"])
        out = self.finish(objection=OBJECTION)
        self.assertEqual((out["ok"], out["status"], out["stop_reason"]), (False, "failed", "works:rejudge"))
        self.assertIn("3 回", out["reason"])
        self.assertTrue(out["report"][0].startswith("再審: "))
        prompt = (self.art / "rejudge-prompt-3.md").read_text(encoding="utf-8")
        self.assertIn("1 回目の拒否", prompt)
        self.assertIn("2 回目の拒否", prompt)

    def test_resubmit_path_prep_fix_prep_accept(self):
        self.rejudge_intake()
        self.assertEqual(self.run.script("rejudge_prep", prev="")["resubmit"], False)
        got = self.run.script("rejudge_accept", reply=dump(rejudge_reply(new_facts="確かめた")), fix_reply="")
        self.assertEqual((got["ok"], got["done"]), (False, False))
        again = self.run.script("rejudge_prep", prev="false")
        self.assertEqual(again, {"prompt": "", "resubmit": True})
        fix = self.run.script("rejudge_fix_prep")["prompt"]
        self.assertIn("Your previous answer was rejected by the machine's check.", fix)
        self.assertIn("new_facts", fix)
        self.assertIn(str(self.art / "candidate-rejudge.json"), fix)
        part = {"new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた"}
        got = self.run.script("rejudge_accept", reply="", fix_reply=dump(part))
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        out = self.finish(objection=OBJECTION)
        self.assertEqual((out["status"], out["rejudge_verdict"]), ("ok", "一部採る"))

    def test_resume_from_the_first_round_does_not_resubmit(self):
        """前の周の ok が空（resume で輪が 1 周目から回り直した）なら、控えが在っても 1 回目の指示を組む"""
        self.rejudge_intake()
        self.run.script("rejudge_accept", reply=dump(rejudge_reply(new_facts="確かめた")), fix_reply="")
        self.assertEqual(self.run.script("rejudge_prep", prev="")["resubmit"], False)

    def test_exit_is_written_when_the_loop_never_ran(self):
        self.rejudge_intake()
        out = self.finish(objection=OBJECTION)
        self.assertEqual((out["status"], out["stop_reason"]), ("failed", "works:rejudge"))
        self.assertIn("返答を受けないまま", out["reason"])
        self.assertTrue((self.art / "rejudge-exit.json").is_file())


class YamlCase(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load((BLOCK / "works-factory-diagnose.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in self.doc["nodes"]}

    def loop(self, name):
        return self.nodes[name]["loop_group"]

    def test_loops_are_fresh_context_false_with_three_rounds_and_one_node_per_layer(self):
        for name, prep, role, acc in (("diagnose-loop", "diagnose-prep", "diagnose", "diagnose-accept"),
                                      ("rejudge-loop", "rejudge-prep", "rejudge", "rejudge-accept")):
            loop = self.loop(name)
            self.assertEqual((loop["fresh_context"], loop["max_iterations"]), (False, 3))
            by = {n["id"]: n for n in loop["nodes"]}
            self.assertNotIn("depends_on", by[prep], "輪の頭の層は prep 1 つだけ")
            if role == "rejudge":   # 出し直しの役を持つ輪: 出し直しの道の node は、頭の prep と 1 回目の役の両方に依る（層が 2 つ以上の node にならない）
                self.assertEqual(list(by), [prep, role, "rejudge-fix-prep", "rejudge-fix", acc])
                self.assertEqual(by[role]["depends_on"], [prep])
                self.assertEqual(by["rejudge-fix-prep"]["depends_on"], [prep, role])
                self.assertEqual(by["rejudge-fix"]["depends_on"], [prep, "rejudge-fix-prep", role])
                self.assertEqual(by[acc]["depends_on"], [role, "rejudge-fix"])
                self.assertEqual(by[acc]["trigger_rule"], "none_failed_min_one_success")
                self.assertEqual(by[role]["when"], "$rejudge-prep.output.resubmit != true")
                self.assertEqual(by["rejudge-fix"]["when"], "$rejudge-prep.output.resubmit == true")
                self.assertEqual(by["rejudge-fix"]["output_format"]["required"], [])
                continue
            self.assertEqual(list(by), [prep, role, acc])
            self.assertEqual(by[role]["depends_on"], [prep])
            self.assertEqual(by[acc]["depends_on"], [role])
            self.assertEqual(loop["until_bash"], f'done=${acc}.output.done; test "$done" = true')

    def test_paths_are_split_by_mode(self):
        self.assertIn("mode == 'judge'", self.nodes["diagnose-loop"]["when"])
        self.assertIn("mode == 'rejudge'", self.nodes["rejudge-loop"]["when"])
        self.assertEqual(self.nodes["finish"]["trigger_rule"], "all_done")
        self.assertEqual(self.nodes["finish"]["depends_on"], ["intake", "diagnose-loop", "rejudge-loop"])

    def test_ai_nodes_are_read_only_with_the_judge_launch(self):
        for loop, role in (("diagnose-loop", "diagnose"), ("rejudge-loop", "rejudge"), ("rejudge-loop", "rejudge-fix")):
            node = next(n for n in self.loop(loop)["nodes"] if n["id"] == role)
            self.assertEqual(node["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])
            self.assertEqual((node["model"], node["mutates_checkout"], node["sandbox"]), ("@wf-judge-core", False, {"enabled": True, "allowUnsandboxedCommands": False}))
            self.assertEqual(node["retry"], {"max_attempts": 2, "on_error": "all"})

    def test_verdict_words_match_the_table(self):
        from tests.blocks.diagnose import support
        rejudge = support.modules()["rejudge"]
        node = next(n for n in self.loop("rejudge-loop")["nodes"] if n["id"] == "rejudge")
        self.assertEqual(tuple(node["output_format"]["properties"]["verdict"]["enum"]), rejudge.REJUDGE_VERDICTS)
        finish = self.nodes["finish"]["output_format"]["properties"]["rejudge_verdict"]["enum"]
        self.assertEqual(tuple(w for w in finish if w), rejudge.REJUDGE_VERDICTS)

    def test_reply_vocabulary_matches_the_tables(self):
        judge = support.modules()["judge"]
        node = next(n for n in self.loop("diagnose-loop")["nodes"] if n["id"] == "diagnose")
        props = node["output_format"]["properties"]
        self.assertEqual(tuple(props["units"]["items"]["properties"]["label"]["enum"]), judge.LABELS)
        self.assertEqual(set(props["questions"]["items"]["properties"]["kind"]["enum"]), set(judge.QUESTION_KINDS))
        self.assertEqual(set(props["questions"]["items"]["properties"]["status"]["enum"]), set(judge.QUESTION_STATUS))
        self.assertEqual(tuple(props["questions"]["items"]["properties"]), judge.QUESTION_FIELDS)

    def test_max_iterations_is_the_give_up_count(self):
        support.modules()
        import rolekit
        self.assertEqual(self.loop("diagnose-loop")["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertEqual(self.loop("rejudge-loop")["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_every_input_is_read_by_a_script(self):
        text = (BLOCK / "scripts" / "intake.py").read_text(encoding="utf-8") + (BLOCK / "scripts" / "finish.py").read_text(encoding="utf-8")
        for name in self.doc["inputs"]:
            self.assertIn(f"INPUTS_{name.upper()}", text, name)
