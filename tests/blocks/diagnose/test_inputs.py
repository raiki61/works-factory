"""入口と指示の値（src/inputs.py）の試験。写す元は tests/workflows/test_judge.py の BaselineTest・PriorFailuresTest・MaterialGiveUpTest と
lib/tests/test_judge_accept.py の BriefCase のうち値を見る物。支度の決まりは docs/design/diagnose.md の 5.1〜5.4。"""
import json
import pathlib
import unittest

from tests.blocks import kit
from tests.blocks.diagnose import support
from tests.blocks.diagnose.support import REQUEST

PORTS = {"request": json.dumps(REQUEST, ensure_ascii=False), "request_origin": "", "objection": "", "base": "", "purpose": "",
         "constraints": "[]", "materials": "[]", "pr_material": "null", "baseline": "", "world_rows": "", "row_asks": "[]",
         "depth_why": "", "spec_rows": "", "spec_origin": "", "answers": "[]", "prior_failures": "[]", "pr_text": "", "policy": "",
         "prior": "null", "prior_brief": "", "prior_inputs": "", "spec": "", "verify": "", "excluded": "", "lang": ""}


def dump(value):
    return json.dumps(value, ensure_ascii=False)


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.mod = support.modules()
        self.art = self.run.artifacts

    def intake(self, **ports):
        return self.run.script("intake", **{**PORTS, **ports})

    def doc(self, name):
        return json.loads((self.art / name).read_text(encoding="utf-8"))

    def write(self, rel, value):
        path = self.art / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return self.run.pointer(rel)

    def material(self, role, reply=None, status="ran", materials=None, reason=""):
        return self.write(f"{role}/material.json", {"role": role, "status": status, "reason": reason, "reply": reply,
                                                    "materials": materials or {}, "base": None, "commits": None})

    def values(self):
        return self.doc("intake.json")["values"]


class JudgeIntakeCase(_Base):
    def test_request_alone_is_enough(self):
        self.assertEqual(self.intake(), {"due": True, "mode": "judge", "reason": ""})
        doc = self.doc("intake.json")
        self.assertEqual((doc["mode"], doc["due"], doc["status"], doc["stop_reason"]), ("judge", True, "ok", ""))
        inputs = self.doc("diagnose-input.json")
        self.assertTrue(all(s["status"] == "not_run" for k, s in inputs["materials"].items() if k not in ("fix_closure", "base_determination")))
        self.assertEqual(inputs["materials"]["fix_closure"]["status"], "not_applicable")
        self.assertEqual(inputs["request_findings"], [{"round": 1, "origin": "人の依頼（依頼の行）", "findings": REQUEST}])
        for name in ("tree.json", "view.json", "diff.patch", "changed-files.txt", "materials.json"):
            self.assertTrue((self.art / name).is_file(), name)

    def test_input_doc_keys_are_the_documented_keys(self):
        self.intake()
        self.assertEqual(set(self.doc("diagnose-input.json")),
                         {"materials", "local_findings", "consistency_findings", "bypass_findings", "external_findings",
                          "procedure_findings", "test_double_fidelity", "main_path_observation", "provenance",
                          "prior_decisions", "purpose_review", "request_findings", "constraints", "world_rows", "answers",
                          "changed_files", "diff_file"})

    def test_diff_file_is_the_absolute_path_of_the_target_diff(self):
        """再審の役は 1 回目の材料のファイルからこのパスで差分に届く（再審の材料に diff.patch を直に渡さない）"""
        self.intake()
        path = pathlib.Path(self.doc("diagnose-input.json")["diff_file"])
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.resolve(), (self.art / "diff.patch").resolve())

    def test_base_determination_falls_back_to_the_view(self):
        """根を持つ素材の doc が 1 本も無い run は、見方の根と commit の数で found に埋める（not_run にしない）"""
        self.intake()
        view = self.doc("view.json")
        got = self.doc("diagnose-input.json")["materials"]["base_determination"]
        self.assertEqual(got, {"status": "found", "count": view["commits"], "detail": f"{view['base']}（始めの記録の差分の根。空なら HEAD）"})
        self.assertEqual(self.doc("materials.json")["base_determination"], got)

    def test_base_determination_from_a_material_wins_over_the_view(self):
        ptr = self.write("local-review/material.json", {"role": "local-review", "status": "ran", "reason": "", "reply": None,
                                                        "materials": {}, "base": "abc123", "commits": 2})
        self.assertTrue(self.intake(materials=dump([json.loads(ptr)]))["due"])
        self.assertEqual(self.doc("diagnose-input.json")["materials"]["base_determination"]["count"], 2)
        said = {"status": "not_run", "reason": "根を決める観点が回らなかった"}
        ptr = self.material("local-review", materials={"base_determination": said})
        self.assertTrue(self.intake(materials=dump([json.loads(ptr)]))["due"])
        self.assertEqual(self.doc("diagnose-input.json")["materials"]["base_determination"], said, "素材が言った not_run は埋めない")

    def test_replies_are_picked_by_role(self):
        pointers = [
            self.material("local-review", {"findings": [{"where": "stats.py:2", "text": "分母"}]}, materials={"local_review": {"status": "found", "count": 1, "detail": "1 件"}}),
            self.material("consistency-bypass", {"findings": [{"where": "a", "text": "整合"}], "bypass_findings": [{"where": "b", "text": "迂回"}]}),
            self.material("hygiene", {"findings": [{"where": "h.py", "text": "衛生"}]}),
            self.material("prior-decisions", {"settled": [{"where": "docs/d.md:3", "topic": "t", "decision": "d"}]}),
            self.material("purpose-review", {"verdict": "narrows"}),
            self.material("provenance", {"checked": 1})]
        self.assertTrue(self.intake(materials=json.dumps(pointers))["due"])
        doc = self.doc("diagnose-input.json")
        self.assertEqual(doc["local_findings"], [{"where": "stats.py:2", "text": "分母"}])
        self.assertEqual(doc["consistency_findings"], [{"where": "a", "text": "整合"}])
        self.assertEqual(doc["bypass_findings"], [{"where": "b", "text": "迂回"}])
        self.assertEqual(doc["provenance"], {"checked": 1})
        self.assertEqual(doc["purpose_review"], {"verdict": "narrows"})
        self.assertEqual(doc["prior_decisions"]["settled"][0]["where"], "docs/d.md:3")
        self.assertIsNone(doc["external_findings"])
        self.assertNotIn("hygiene", json.dumps({k: v for k, v in doc.items() if k != "materials"}), "hygiene の findings は今も判定役に届かない")
        self.assertEqual(doc["materials"]["local_review"]["count"], 1)

    def test_material_rows_follow_p1_roles_and_request(self):
        pointers = [self.material("local-review", {"lenses": [{"skill": "code-review", "findings": [{"where": "stats.py:9", "text": "分母", "mechanism": "m"}]}]}),
                    self.material("prior-decisions", {"decisions": [{"where": "x", "text": "y"}]}),
                    self.material("hygiene", {"findings": [{"where": "h.py", "text": "衛生"}]})]
        self.intake(materials=json.dumps(pointers))
        rows = self.values()["material_rows"]
        self.assertIn({"where": "stats.py:9", "text": "分母", "mechanism": "m", "from": "p1.local_review / code-review"}, rows)
        self.assertIn("p1.hygiene", [r["from"] for r in rows])
        self.assertNotIn("x", [r["where"] for r in rows], "P0 の素材は材料の行に入らない")
        self.assertEqual([r["where"] for r in rows if r["from"].startswith("依頼")], ["stats.py", "stats.py"])

    def test_parallel_pr_card_joins_the_materials(self):
        card = {"status": "found", "count": 1, "detail": "PR #12 が stats.py を触る"}
        self.assertTrue(self.intake(pr_material=json.dumps(card))["due"])
        self.assertEqual(self.doc("diagnose-input.json")["materials"]["parallel_pr"], card)
        bad = self.intake(pr_material=json.dumps({"status": "unknown"}))
        self.assertFalse(bad["due"])
        self.assertIn("入力 materials", bad["reason"])

    def test_gate_efficacy_is_not_a_material_of_this_block(self):
        """gate_efficacy は判定の材料の欄でなく、gate-efficacy の block が返しても読まない（持ち主の決め 2026-10-19）"""
        ptr = self.material("gate-efficacy", {"arms": [{"arm": "a"}]}, materials={"gate_efficacy": {"status": "clean", "checked": "x"}})
        self.assertTrue(self.intake(materials=dump([json.loads(ptr)]))["due"])
        doc = self.doc("diagnose-input.json")
        self.assertNotIn("gate_efficacy", doc["materials"])
        self.assertNotIn("gate_arms", doc)
        self.assertEqual(len(doc["materials"]), 14)
        self.assertNotIn("gate_efficacy", self.doc("materials.json"))

    def test_local_checks_come_from_the_baseline(self):
        import baseline_red
        clean = {"status": "clean", "count": 0, "checked": "宣言の一式を対象の根で走らせた: exit 0"}
        found = {"status": "found", "count": 1, "detail": "test_mean_of_three が赤"}
        for material in (clean, found, None):
            with self.subTest(status=material and material["status"]):
                ports = {}
                if material:
                    baseline_red.write_baseline(self.art / "base" / "baseline.json", suite="", test_cmd="", rev="x", exit=0, cases=[],
                                                material=material)
                    ports["baseline"] = self.run.pointer("base/baseline.json")
                self.assertTrue(self.intake(**ports)["due"])
                got = self.doc("diagnose-input.json")["materials"]["local_checks"]
                self.assertEqual(got, material or {"status": "not_run", "reason": "走っていない（どのノードも返していない）"})

    def test_bad_baseline_is_not_run_with_the_reason(self):
        self.write("base/baseline.json", {"suite": 1})
        self.assertTrue(self.intake(baseline=self.run.pointer("base/baseline.json"))["due"])
        got = self.doc("diagnose-input.json")["materials"]["local_checks"]
        self.assertEqual(got["status"], "not_run")
        self.assertIn("直す前の結末が読めない", got["reason"])

    def test_given_up_material_stops_without_waking_the_role(self):
        pointers = [self.material("hygiene", None, status="gave_up", reason="衛生の役の返答が 3 回とも拒まれた"),
                    self.material("provenance", None, status="gave_up", reason="出所の役の返答が 3 回とも拒まれた")]
        got = self.intake(materials=json.dumps(pointers))
        self.assertEqual((got["due"], got["reason"]), (False, "衛生の役の返答が 3 回とも拒まれた／出所の役の返答が 3 回とも拒まれた"))
        doc = self.doc("intake.json")
        self.assertEqual((doc["status"], doc["stop_reason"]), ("stopped", "works:material"))
        self.assertTrue((self.art / "diagnose-input.json").is_file(), "材料は組んでから止める")

    def test_unreadable_request_is_works_request(self):
        for bad in ('{"where": "x"}', json.dumps([{"where": "a", "text": "b", "draft": True, "source": "s"}])):
            with self.subTest(bad):
                got = self.intake(request=bad)
                self.assertFalse(got["due"])
                doc = self.doc("intake.json")
                self.assertEqual((doc["status"], doc["stop_reason"]), ("failed", "works:request"))
                self.assertIn("入力 request", doc["reason"])

    def test_other_unreadable_inputs_are_works_judge(self):
        for name, value in (("materials", '["", 3]'), ("row_asks", '[{"item": "x"}]'), ("constraints", '[{"text": "a"}]'),
                            ("world_rows", self.write("w.jsonl", "not json\n")), ("answers", '[{"question": 3}]'),
                            ("spec_rows", self.write("spec.json", [{"where": "a", "text": "b"}]))):
            with self.subTest(name):
                got = self.intake(**{name: value})
                self.assertFalse(got["due"], got)
                doc = self.doc("intake.json")
                self.assertEqual((doc["status"], doc["stop_reason"]), ("failed", "works:judge"))
                self.assertIn(f"入力 {name}", doc["reason"])

    def test_spec_rows_become_their_own_batch(self):
        rows = [{"where": "tests/test_x.py", "text": "【仕様の受け入れ条件】Given a When b Then c"}]
        got = self.intake(spec_rows=self.write("spec/added-rows.json", rows), spec_origin="仕様（人が承認した受け入れ条件）",
                          request_origin="人の依頼（/path/req.json）")
        self.assertTrue(got["due"])
        batches = self.doc("diagnose-input.json")["request_findings"]
        self.assertEqual([(b["origin"], len(b["findings"])) for b in batches],
                         [("人の依頼（/path/req.json）", 2), ("仕様（人が承認した受け入れ条件）", 1)])

    def test_spec_rows_of_a_wrong_shape_stop(self):
        for rows in ([{"where": "tests/test_x.py"}], [{"where": "a", "text": "b", "extra": "c"}], ["a"]):
            with self.subTest(rows=rows):
                got = self.intake(spec_rows=self.write("spec/added-rows.json", rows), spec_origin="仕様（人が承認した受け入れ条件）")
                self.assertFalse(got["due"])
                self.assertIn("入力 spec_rows", got["reason"])

    def test_empty_request_has_no_batch(self):
        self.assertTrue(self.intake(request="[]")["due"])
        self.assertEqual(self.doc("diagnose-input.json")["request_findings"], [])

    def test_declared_request_without_rows_is_works_request(self):
        """依頼をファイル・pointer・容器の形で渡したのに行が空なら拒む（旧 check_request の minItems 1）。行の無い run は [] だけ"""
        for request in (self.write("req/empty.json", []), self.write("req/container.json", {"findings": []}), '{"findings": []}'):
            with self.subTest(request=request):
                got = self.intake(request=request)
                self.assertFalse(got["due"])
                self.assertIn("入力 request: 依頼を渡したのに行が空", got["reason"])
                self.assertEqual(self.doc("intake.json")["stop_reason"], "works:request")

    def test_answers_come_from_the_container_unless_the_port_has_rows(self):
        container = json.dumps({"findings": REQUEST, "answers": [{"question": "容器の問い", "text": "容器の答え"}]}, ensure_ascii=False)
        self.intake(request=container)
        self.assertEqual(self.doc("diagnose-input.json")["answers"], [{"question": "容器の問い", "text": "容器の答え"}])
        self.intake(request=container, answers=json.dumps([{"question": "入力の問い", "text": "入力の答え"}]))
        self.assertEqual(self.doc("diagnose-input.json")["answers"], [{"question": "入力の問い", "text": "入力の答え"}])

    def test_container_rows_and_the_input_rows_split_into_notes_and_redesign(self):
        import carry
        container = json.dumps({"findings": REQUEST, "prior_failures": [{"where": "受け付け", "text": "容器の側の印"}]}, ensure_ascii=False)
        port = [{"where": carry.REDESIGN_WHERE, "text": "R2 が redesign-needed: 構造が合わない"}, {"where": "受け付け", "text": "入力の側の印"}]
        self.intake(request=container, prior_failures=json.dumps(port, ensure_ascii=False))
        v = self.values()
        self.assertEqual([r["text"] for r in v["prior_rows"]], ["容器の側の印", "入力の側の印"])
        self.assertEqual([r["text"] for r in v["redesign"]], ["R2 が redesign-needed: 構造が合わない"])
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertTrue(when["prior_notes"] and when["prior_redesign"])
        self.assertEqual(values["prior_notes"], "- 受け付け: 容器の側の印\n- 受け付け: 入力の側の印")
        self.assertEqual(values["prior_redesign"], f"- {carry.REDESIGN_WHERE}: R2 が redesign-needed: 構造が合わない")

    def test_recorded_policy_rows(self):
        policy = self.write("policy-copy.md", "# 方針\n- 空の列は試験しない\n- 例外は握り潰さない\n")
        decisions = self.material("prior-decisions", {"settled": [{"where": "docs/d.md:3", "topic": "出荷", "decision": "タグは作らない"},
                                                                  {"topic": "場所の無い論点", "decision": "決めた"}]})
        container = json.dumps({"findings": REQUEST, "answers": [{"question": "どれを採るか", "text": "A を採る"}]}, ensure_ascii=False)
        self.intake(request=container, policy=policy, materials=json.dumps([decisions]))
        rows = self.values()["recorded"]
        self.assertEqual([r["source"] for r in rows], ["doc", "answer", "settled", "settled"])
        self.assertEqual(rows[0]["name"], str(self.art / "policy-copy.md"))
        self.assertEqual(rows[0]["lines"], 3)
        text = self.mod["inputs"].recorded_text(rows)
        self.assertIn(f"- Policy document: name `{rows[0]['name']}:<line>` (lines 1–3; original place: none)", text)
        self.assertIn("  - name `どれを採るか`: A を採る", text)
        self.assertIn("- Answers a person gave at approval nodes: not given to this role", text)
        self.assertIn("  - name `docs/d.md:3`: 出荷——タグは作らない", text)
        self.assertIn("  - (no where, so it cannot be named) 場所の無い論点——決めた", text)

    def test_recorded_text_without_rows(self):
        text = self.mod["inputs"].recorded_text([])
        self.assertEqual(text.splitlines(), ["- Policy document: none", "- answers of the request: none",
                                             "- Answers a person gave at approval nodes: not given to this role",
                                             "- Settled points (from the decision records): none"])

    def test_world_rows_are_read_into_the_input_doc(self):
        row = {"finding": 1, "where": "stats.py", "class_id": "w-1", "problem": "p", "activity": "a", "practice": "x", "sources": [],
               "applies": "a", "not_applies": "", "versus": {"proposed": "p", "verdict": "same", "challenge": ""}, "basis": "knowledge"}
        path = self.write("world/world.jsonl", json.dumps(row, ensure_ascii=False) + "\n")
        got = self.intake(world_rows=path)
        if not got["due"]:   # 世界の解の行の形が変わった時は、この行の作り方を直す
            self.fail(got["reason"])
        self.assertEqual(self.doc("diagnose-input.json")["world_rows"][0]["class_id"], "w-1")

    def test_intake_clears_its_own_stale_files_only(self):
        self.intake()
        self.run.script("diagnose_prep")
        self.assertTrue((self.art / "diagnose-prompt-1.md").is_file())
        (self.art / "judgment.json").write_text("{}", encoding="utf-8")
        (self.art / "other.json").write_text("{}", encoding="utf-8")
        self.intake()
        self.assertFalse((self.art / "diagnose-prompt-1.md").exists())
        self.assertFalse((self.art / "judgment.json").exists())
        self.assertTrue((self.art / "other.json").is_file(), "名を持たないファイルは消さない")


class ValuesCase(_Base):
    def test_unknown_lines_use_known_kinds_only(self):
        inputs = self.mod["inputs"]
        rows = [{"item": 1, "unknown": "無し", "cause_quote": "分母が違う", "where": "stats.py:4", "code_quote": "return sum(xs) / 2"},
                {"item": 2, "unknown": "原因", "cause_quote": "落ちる"},
                {"item": 3, "unknown": "知らない種類", "cause_quote": "x"}]
        self.assertEqual(inputs.unknown_lines(rows), [
            "- line 1 (無し): request text 「分母が違う」・place stats.py:4「return sum(xs) / 2」",
            "- line 2 (原因): request text 「落ちる」・place: none (the cause is not visible in code)"])

    def test_head_depth_rows_and_why_reach_the_values(self):
        import headdepth
        self.intake(row_asks=json.dumps([{"item": 1, "unknown": "形", "cause_quote": "どちらでも"}]))
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertTrue(when["unknown_rows"] and not when["unknown_none"])
        self.assertEqual(values["unknown_rows"], "- line 1 (形): request text 「どちらでも」・place: none (the cause is not visible in code)")
        self.intake(depth_why="頭の深さの段が走らなかった")
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertTrue(when["unknown_none"] and not when["unknown_rows"])
        self.assertEqual((values["unknown_rows"], values["unknown_why"]), ("", "頭の深さの段が走らなかった"))
        self.intake()
        self.assertEqual(self.mod["inputs"].diagnose_values(self.art)[0]["unknown_why"], headdepth.NO_RECORD)

    def test_purpose_policy_and_pr_reach_the_values(self):
        purpose = self.write("purpose/purpose.json", {"purpose_text": "平均の関数が正しい値を返す", "source": "②計画・タスク記述",
                                                      "known_weaknesses": [], "source_files": []})
        policy = self.write("policy-copy.md", "# 方針\n- 空の列は試験しない\n")
        self.intake(purpose=purpose, policy=policy, pr_text="PR #3 平均を直す")
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertEqual(values["purpose_text"], "平均の関数が正しい値を返す")
        self.assertIn("空の列は試験しない", values["policy_body"])
        self.assertEqual(values["pr_text"], "PR #3 平均を直す")
        self.assertTrue(when["purpose"] and when["policy"] and when["pr_text"])
        self.assertFalse(when["repo_review"] or when["rejected"])
        self.intake()
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertEqual((values["purpose_text"], values["policy_body"], values["pr_text"]), ("", "", ""))
        self.assertFalse(when["purpose"] or when["policy"] or when["pr_text"])
        self.assertTrue(when["recorded_none"])

    def test_repo_review_md_is_found_in_the_target(self):
        (self.run.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        self.intake()
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertTrue(when["repo_review"])
        self.assertTrue(values["repo_review_md"].endswith("REVIEW.md"))

    def test_policy_body_is_cut_at_the_paste_cap(self):
        import policy
        path = self.art / "big-policy.md"
        path.write_text("あ" * (policy.PASTE_CAP // 3 + 500), encoding="utf-8")
        body = self.mod["inputs"].policy_body(path)
        self.assertLessEqual(len(body.encode("utf-8")), policy.PASTE_CAP)
        self.assertIn(f"続きは {path}", body)

    def test_every_rejection_of_the_loop_reaches_the_next_prompt(self):
        import rolekit
        self.intake()
        for reason in ("一つ目の拒否の印", "二つ目の拒否の印"):
            rolekit.with_done(self.art, "diagnose", {"ok": False, "reason": reason})
        values, when = self.mod["inputs"].diagnose_values(self.art)
        self.assertTrue(when["rejected"])
        self.assertTrue(values["rejection"].index("一つ目の拒否の印") < values["rejection"].index("二つ目の拒否の印"))


class RejudgeValuesCase(_Base):
    FIRST = {"framing": "根は 1 つ", "one_shot": "直す", "questions": [{"key": "q", "kind": "fork", "status": "held", "reason": "割れる"}],
             "units": [{"key": "k1", "label": "block", "disposition": "do-now", "reason": "r", "class_query": {"how": {}}}]}

    def test_values_and_paragraphs(self):
        purpose = self.write("purpose/purpose.json", {"purpose_text": "p"})
        self.run.script("intake", **{**PORTS, "objection": "異議の文", "prior": json.dumps(self.FIRST), "purpose": purpose,
                                    "world_rows": self.write("world.jsonl", ""), "lang": "English"})
        values, when = self.mod["inputs"].rejudge_values(self.art)
        self.assertEqual(values["objection"], "異議の文")
        self.assertEqual(json.loads(values["units"]), [{"key": "k1", "label": "block", "disposition": "do-now"}])
        self.assertEqual(json.loads(values["questions"]), [{"key": "q", "kind": "fork", "status": "held"}])
        self.assertEqual(json.loads(values["diagnosis"]), {"framing": "根は 1 つ", "one_shot": "直す"})
        self.assertEqual(values["first_judgment_file"], str(self.art / "first-judgment.json"))
        self.assertEqual(values["purpose_file"], str(self.art / "purpose" / "purpose.json"))
        self.assertTrue(when["questions"] and when["diagnosis"] and when["purpose"] and when["world_rows"])
        self.assertFalse(when["prior_brief"] or when["spec"] or when["verify"] or when["excluded"] or when["policy"])
        self.assertEqual(values["lang"], "English")

    def test_empty_ledger_and_view_turn_the_paragraphs_off(self):
        self.run.script("intake", **{**PORTS, "objection": "異議の文", "prior": json.dumps({"units": []})})
        values, when = self.mod["inputs"].rejudge_values(self.art)
        self.assertFalse(when["questions"] or when["diagnosis"])
        self.assertEqual((values["questions"], values["diagnosis"]), ("", ""))
