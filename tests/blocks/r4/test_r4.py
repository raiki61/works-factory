"""block r4 を、script を子のプロセスで回して確かめる（docs/design/r4.md の 8 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → scope_prep → 台本の返答 → scope_accept →
（拒まれたら scope_prep → scope_fix_prep → 台本の出し直し → scope_accept）→ finish と回す。今の tests/workflows/test_eyes.py の ScriptCase と
lib/tests/test_eyeverdict.py の R4 の場面を、port の値で作り直した（各試験の docstring に元の試験の名を書く）。筋書きを Archon の
workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import pathlib
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "r4"
DOC = yaml.safe_load((BLOCK / "works-factory-r4.yaml").read_text(encoding="utf-8"))
PORTS = ["base", "lang", "purpose", "green", "policy", "after", "review", "answers", "request", "changed", "pushes", "decisions",
         "ripple", "world_rows", "asked", "declared", "coherence"]
PASS = {"status": "pass", "reason": "なし", "capability_inventory": {"fired": False}, "policy_conflicts": [], "surfaced": [],
        "seen": ["a.txt"], "unseen": []}
R3 = {"status": "pass", "reason": "整合", "seen": ["a.txt"], "unseen": []}
LINE = "方針の文書の 2 行目の『空の列は試験しない』に反する"
LOST = "古い入口——使う人がいない"
NARROW = f"修正案 1 が狭める能力: {LOST}"


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "r4")
        self.repo = self.run.repo
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.place = self.run.artifacts
        self.gate = kit.load("r4", "gate")

    def intake(self, **inputs):
        return self.run.script("intake", **{"base": self.base, **inputs})

    def prep(self, prev=None) -> dict:
        return self.run.script("scope_prep", **({} if prev is None else {"prev": prev}))

    def accept(self, reply="null", fix_reply="null") -> dict:
        return self.run.script("scope_accept", reply=reply if isinstance(reply, str) else dump(reply),
                               fix_reply=fix_reply if isinstance(fix_reply, str) else dump(fix_reply))

    def finish(self) -> dict:
        return self.run.script("finish")

    def write(self, name, text) -> pathlib.Path:
        path = self.run.artifacts.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def intake_json(self) -> dict:
        return json.loads((self.place / "intake.json").read_text(encoding="utf-8"))

    def policy_doc(self) -> pathlib.Path:
        return self.write("policy/abc.md", "一\n二\n三\n")


class ShapeCase(unittest.TestCase):
    def test_inputs_are_the_declared_ports(self):
        self.assertEqual(list(DOC["inputs"]), PORTS)

    def test_scripts_read_only_the_declared_inputs(self):
        import re
        reads = {}
        for path in (BLOCK / "scripts").glob("*.py"):
            reads[path.stem] = {m.lower() for m in re.findall(r'os\.environ\.get\("INPUTS_([A-Z_]+)"', path.read_text(encoding="utf-8"))}
        self.assertEqual(reads["intake"], set(PORTS))
        self.assertEqual(reads["scope_prep"], {"prev"})
        self.assertEqual(reads["scope_accept"], {"reply", "fix_reply"})
        self.assertEqual({k for k in reads if reads[k]}, {"intake", "scope_prep", "scope_accept"})

    def test_fixtures_reach_the_nodes(self):
        ids = [n["id"] for n in DOC["nodes"][1].get("loop_group", {}).get("nodes", [])]
        standalone = kit.fixture("r4", "standalone")["fixture"]["reached"]
        self.assertEqual(standalone, ["intake", "r4-scope-prep", "r4-scope", "r4-scope-accept", "finish"])
        self.assertEqual(kit.fixture("r4", "resubmit")["fixture"]["reached"],
                         ["intake", "r4-scope-prep", "r4-scope-fix-prep", "r4-scope-fix", "r4-scope-accept", "finish"])
        self.assertEqual(ids, ["r4-scope-prep", "r4-scope", "r4-scope-fix-prep", "r4-scope-fix", "r4-scope-accept"])


class FlowCase(_RepoCase):
    def test_flow_reaches_the_verdict_and_the_report(self):
        """筋: 役が pass を返し、棚卸しが発火して lost が通した行と同じ本文なら問いにならず、通した行の控えが出力と報告に載る
        （test_verdict_drops_passed_questions・test_prep_pastes_passed_rows_at_the_r4_head）"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.intake(purpose="古い入口を消す", answers=dump({"before_fix": {"decision": "continue", "text": ""}}),
                                     asked=dump([{"kind": "regression", "text": NARROW}])), {"due": True, "reason": ""})
        first = self.prep()
        self.assertEqual((first["resubmit"], first["attempt"]), (False, 1))
        self.assertIn("As the inspector: R4, the scope the change does not see.", first["prompt"])
        self.assertIn(f"- [regression] {LOST}", first["prompt"])
        self.assertNotIn("new conversation", first["prompt"])
        self.assertIn("Original purpose: 古い入口を消す", first["prompt"])
        self.assertIn(f"Cumulative diff: `{self.place / 'run.diff'}`", first["prompt"])
        reply = {**PASS, "capability_inventory": {"fired": True, "lost": [LOST, "別の能力"]}}
        self.assertEqual(self.accept(reply), {"ok": True, "done": True, "give_up": False, "reason": ""})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["reason"]), (True, "ran", ""))
        self.assertEqual(done["verdict"], {"status": "pass", "reason": "なし"})
        self.assertEqual(done["questions"], ["R4 が BASE から消えたと見た能力: 別の能力"])
        self.assertEqual([(p["by"], p["item"], p["node"]) for p in done["passes"]],
                         [("human", f"R4 が BASE から消えたと見た能力: {LOST}", "r4.human_gate")])
        self.assertIsNone(done["coherence"])
        self.assertEqual(done["report"][0], "R4: pass（なし）")
        self.assertIn("1 件", done["report"][1])
        self.assertEqual(json.loads((self.place / "finish.json").read_text(encoding="utf-8")), done)
        self.assertEqual(json.loads((self.place / "r4-scope.json").read_text(encoding="utf-8")), reply)

    def test_intake_clears_only_its_own_files(self):
        self.intake()
        self.prep()
        self.accept(PASS)
        other = self.place / "rejects-other.json"
        other.write_text("[]", encoding="utf-8")
        (self.place / "accept-crash.json").write_text("{}", encoding="utf-8")
        self.intake()
        for name in ("r4-scope.json", "candidate-r4-scope.json", "rejects-r4-scope.json", "accept-crash.json"):
            self.assertFalse((self.place / name).exists(), name)
        self.assertFalse(list(self.place.glob("r4-scope-prompt-*.md")))
        self.assertTrue(other.exists())

    def test_unreadable_port_is_not_due_and_finish_says_so(self):
        got = self.intake(answers="[1]")
        self.assertFalse(got["due"])
        self.assertIn("入力 answers", got["reason"])
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["verdict"]["status"], "unverifiable")
        self.assertEqual((done["questions"], done["passes"], done["coherence"]), ([], [], None))

    def test_finish_without_intake_does_not_fall(self):
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["report"], ["R4: unverifiable（入力が読めない: 入口の控え intake.json が無いか読めない（入口の node が落ちた））"])

    def test_finish_without_a_reply_is_failed(self):
        self.intake()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["questions"], done["passes"]), (False, "failed", [], []))
        self.assertIn("R4 の筋が落ちた", done["verdict"]["reason"])
        self.assertEqual(len(done["report"]), 1)

    def test_finish_does_not_fall_on_an_inner_error(self):
        self.intake()
        self.accept({**PASS, "capability_inventory": "x"})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertIn("出口が落ちた", done["verdict"]["reason"])

    def test_an_accept_that_fell_after_writing_the_reply_makes_finish_failed(self):
        """受け付けが r4-scope.json を書いた後で中の誤りで落ちても、出口は ran にせず、判定の行の reason の尾に落ちた訳を足す（9 の 11・12）"""
        self.intake(answers=dump({"before_fix": {"decision": "continue"}}))
        doc = self.intake_json()
        (self.place / "intake.json").write_text(dump({**doc, "asked": 5}), encoding="utf-8")
        got = self.accept(PASS)
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True))
        self.assertTrue(got["reason"].startswith("受け付けが落ちた: TypeError"), got["reason"])
        self.assertTrue((self.place / "r4-scope.json").is_file())
        self.assertIn("TypeError", json.loads((self.place / "accept-crash.json").read_text(encoding="utf-8"))["why"])
        (self.place / "intake.json").write_text(dump(doc), encoding="utf-8")
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertTrue(done["verdict"]["reason"].startswith("なし（受け付けが落ちた: TypeError"), done["verdict"]["reason"])
        self.assertEqual(done["reason"], done["verdict"]["reason"])
        self.assertIn("受け付けが落ちた", done["report"][0])

    def test_an_accept_that_fell_before_writing_the_reply_is_named_in_finish(self):
        """受け付けが返答を書けずに落ちた時も、出口の判定の行の reason に落ちた訳が載る（scope_accept.py の fallback の形）"""
        self.intake()
        (self.place / "r4-scope.json").mkdir()
        got = self.accept(PASS)
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True))
        self.assertTrue(got["reason"].startswith("受け付けが落ちた: "), got["reason"])
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertIn("（受け付けが落ちた: ", done["verdict"]["reason"])

    def test_status_outside_the_words_is_unverifiable(self):
        self.intake()
        self.accept({**PASS, "status": "fix-needed"})
        done = self.finish()
        self.assertEqual((done["ok"], done["verdict"]["status"]), (False, "unverifiable"))

    def test_empty_diff_points_at_the_reason(self):
        self.intake()
        doc = self.intake_json()
        self.assertEqual(doc["diff"]["lines"], 0)
        self.assertNotIn("text", doc["diff"])
        self.assertIn(self.base, pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))

    def test_materials_are_named_or_say_not_given(self):
        """波及と定石の置き場と修正の印は在れば並べ、無ければ (not given)"""
        self.intake()
        text = self.prep()["prompt"]
        for want in ("Ripple list: (not given)", "Rows of established practice: (not given)", "Fix marks: (not given)",
                     "Original purpose: (not given)"):
            self.assertIn(want, text)
        ripple, world = self.write("plan/ripple.json", "[]"), self.write("judge/world.jsonl", "")
        self.intake(ripple=str(ripple), world_rows=str(world), purpose="目的",
                    changed=dump({"mechanism_changed": False, "seams_changed": True, "premise_drift_note": "x"}))
        text = self.prep()["prompt"]
        self.assertIn(f"Ripple list: {ripple}", text)
        self.assertIn(f"Rows of established practice: {world}", text)
        self.assertIn("Fix marks: mechanism_changed=false・seams_changed=true", text)

    def test_green_paragraph_only_when_not_certified(self):
        """test_green_line_only_when_not_certified。既定の true は文を足さない"""
        line = "The certification of the last tests did not pass"
        self.intake()
        self.assertNotIn(line, self.prep()["prompt"])
        self.intake(green="false")
        self.assertIn(line, self.prep()["prompt"])

    def test_declared_plan_blocks_are_pasted(self):
        """test_prep_pastes_declared_plan_blocks_at_the_r4_head（issue #662）。無ければ節ごと入らない"""
        self.intake()
        self.assertNotIn("fixer answered it would leave unfixed", self.prep()["prompt"])
        row = "stale-docstring-left: 古い docstring が直しの後の戻り値を説明しない（直す側の答え: 範囲の外なので残す）"
        self.intake(declared=dump([row]))
        text = self.prep()["prompt"]
        self.assertIn("fixer answered it would leave unfixed", text)
        self.assertIn(f"- {row}", text)

    def test_no_passed_section_without_passed_rows(self):
        self.intake(asked=dump([{"kind": "regression", "text": NARROW}]))
        self.assertNotIn("## Narrowings passed", self.prep()["prompt"])
        self.intake(answers=dump({"before_fix": {"decision": "stop"}}), asked=dump([{"kind": "regression", "text": NARROW}]))
        self.assertNotIn("## Narrowings passed", self.prep()["prompt"])

    def test_policy_and_recorded_policy_sections(self):
        """test_policy_section_on_r1_r3_r4・test_recorded_policy_only_on_r3_r4 の R4 の半分・test_prep_keeps_the_recorded_rows_for_the_verdict"""
        self.intake()
        text = self.prep()["prompt"]
        self.assertNotIn("The person's policy", text)
        self.assertIn("Recorded policy: none", text)
        self.assertEqual(self.intake_json()["recorded"], [])
        doc = self.policy_doc()
        self.intake(policy=str(doc), answers=dump({"before_fix": {"decision": "continue", "text": "古い入口は消してよい"}}))
        text = self.prep()["prompt"]
        self.assertIn("The person's policy", text)
        self.assertIn("一\n二\n三", text)
        self.assertIn("write each conflict with the policy as one row in `policy_conflicts`", text)
        self.assertNotIn("Recorded policy: none", text)
        self.assertEqual([r["source"] for r in self.intake_json()["recorded"]], ["doc", "gate"])
        self.assertNotIn("R3 overall coherence", text)
        self.assertNotIn("Where concepts live", text)

    def test_language_defaults_to_the_request_language(self):
        self.intake()
        self.assertIn("in the language of the request (the user's language).", self.prep()["prompt"])
        self.intake(lang="English")
        self.assertIn("`unseen` (and the `reason`, `seen`, and `unseen` of `r3`, if you write it) in English.", self.prep()["prompt"])


class AcceptCase(_RepoCase):
    def named_policy(self) -> dict:
        doc = self.policy_doc()
        self.intake(policy=str(doc))
        return {"copy": str(doc)}

    def test_unnamed_policy_line_is_rejected_then_resubmitted(self):
        """test_r4_accept_rejects_an_unnamed_policy_line・test_r4_resubmit_returns_only_the_rejected_fields（#455・#571）"""
        copy = self.named_policy()["copy"]
        self.assertEqual(self.prep()["attempt"], 1)
        reply = {**PASS, "policy_conflicts": [LINE]}
        first = self.accept(reply)
        self.assertEqual((first["ok"], first["done"], first["give_up"]), (False, False, False))
        gate = self.gate
        self.assertTrue(first["reason"].startswith(gate.R4_REJECT), first["reason"])
        self.assertIn(LINE, first["reason"])
        again = self.prep(prev="false")
        self.assertEqual((again["resubmit"], again["prompt"], again["attempt"]), (True, "", 2))
        fix = self.run.script("scope_fix_prep")["prompt"]
        self.assertIn(first["reason"], fix)
        self.assertIn(str(self.place / "candidate-r4-scope.json"), fix)
        self.assertIn("In this same conversation, fix only what was rejected and return it.", fix)
        self.assertEqual((self.place / "r4-scope-fix-prompt-1.md").read_text(encoding="utf-8"), fix)
        resumed = self.prep(prev="")
        self.assertIs(resumed["resubmit"], False)
        self.assertIn(first["reason"].splitlines()[0], resumed["prompt"])
        self.assertIn("Why your previous answer was rejected", resumed["prompt"])
        fixed = [f"{copy}:2 の『空の列は試験しない』に反する"]
        got = self.accept("null", {"policy_conflicts": fixed})
        self.assertEqual((got["ok"], got["done"]), (True, True), got["reason"])
        self.assertEqual(json.loads((self.place / "r4-scope.json").read_text(encoding="utf-8")), {**reply, "policy_conflicts": fixed})

    def test_first_round_has_no_rejection_section(self):
        self.named_policy()
        self.assertNotIn("Why your previous answer was rejected", self.prep()["prompt"])

    def test_lost_capabilities_are_not_checked_against_the_recorded_rows(self):
        """test_lost_capabilities_are_not_checked_against_the_recorded_rows"""
        self.named_policy()
        got = self.accept({**PASS, "capability_inventory": {"fired": True, "lost": ["どの行も名指さない能力"]}})
        self.assertEqual((got["ok"], got["done"]), (True, True))

    def test_unnamed_policy_line_the_human_passed_is_kept(self):
        """test_r4_accept_keeps_an_unnamed_policy_line_the_human_passed"""
        doc = self.policy_doc()
        self.intake(policy=str(doc), answers=dump({"before_fix": {"decision": "continue", "text": ""}}),
                    asked=dump([{"kind": "policy", "text": f"事前審査の穴 [policy] k: {LINE}"}]))
        got = self.accept({**PASS, "policy_conflicts": [LINE]})
        self.assertEqual((got["ok"], got["done"]), (True, True), got["reason"])
        done = self.finish()
        self.assertEqual(done["questions"], [])
        self.assertEqual([p["item"] for p in done["passes"]], [f"R4 が見た人の方針とのぶつかり: {LINE}"])

    def test_gives_up_after_three_rejections_and_asks_the_unnamed_line(self):
        """test_r4_policy_conflict_is_asked_when_the_accept_gave_up: 3 回目の拒否で輪を抜け、名指さない行も問いに入り、判定の理由に諦めた尾"""
        self.named_policy()
        rounds = []
        for _ in range(3):
            rounds.append(self.prep()["attempt"])
            got = self.accept({**PASS, "policy_conflicts": [LINE]})
        self.assertEqual(rounds, [1, 2, 3])
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True))
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))
        self.assertEqual(done["questions"], [f"R4 が見た人の方針とのぶつかり: {LINE}"])
        self.assertIn("名指さない行も人に聞く", done["verdict"]["reason"])
        self.assertTrue(done["verdict"]["reason"].startswith("なし"))

    def test_a_named_line_is_asked_when_accepted(self):
        """test_r4_policy_conflict_naming_a_recorded_row_is_asked"""
        copy = self.named_policy()["copy"]
        line = f"{copy}:2 の『空の列は試験しない』に反する"
        self.assertEqual(self.accept({**PASS, "policy_conflicts": [line]})["ok"], True)
        self.assertEqual(self.finish()["questions"], [f"R4 が見た人の方針とのぶつかり: {line}"])

    def test_unreadable_reply_is_a_reject(self):
        self.intake()
        for raw, word in (("not json", "JSON"), ("[1]", "オブジェクトでない")):
            with self.subTest(raw):
                got = self.accept(raw)
                self.assertEqual((got["ok"], got["done"]), (False, False))
                self.assertIn(word, got["reason"])
                self.assertIn(word, self.prep()["prompt"])
                (self.place / "rejects-r4-scope.json").unlink()

    def test_the_condition_an_unattended_run_pushed_can_be_named(self):
        """test_r4_can_name_the_condition_an_unattended_run_pushed（#562）: 推しの条件は人の答えと別の行で並び、名指せば通る"""
        note = "空の列は 0 を返す形で通す"
        self.intake(answers=dump({"before_fix": {"decision": "continue", "text": note, "asked": [],
                                                 "pushed": [{"item": "x", "answer": "continue", "note": note, "why": "y"}]}}))
        row, = self.intake_json()["recorded"]
        self.assertEqual((row["source"], row["text"]), ("push", note))
        self.assertIn(f"`{row['name']}`: {note}", self.prep()["prompt"])
        named = {**PASS, "policy_conflicts": [f"{row['name']} の『{note}』に反し、空の列で None を返す"]}
        self.assertTrue(self.accept(named)["ok"])
        unnamed = {**PASS, "policy_conflicts": [f"『{note}』に反し、空の列で None を返す"]}
        self.assertFalse(self.accept(unnamed)["ok"])

    def test_the_push_taken_for_a_held_question_can_be_named(self):
        """test_r4_can_name_the_push_an_unattended_run_took_for_a_held_question（#600）: port pushes の推しも PUSH_NAME の行で並ぶ"""
        push = "問い q-a: 0 を返す——呼び手が既に 0 を前提にしている"
        self.intake()
        self.assertEqual(self.intake_json()["recorded"], [])
        self.intake(pushes=dump([push]))
        row, = self.intake_json()["recorded"]
        self.assertEqual((row["source"], row["text"]), ("push", push))
        self.assertIn(f"`{row['name']}`: {push}", self.prep()["prompt"])
        self.assertTrue(self.accept({**PASS, "policy_conflicts": [f"{row['name']} の『0 を返す』に反し、例外を投げる"]})["ok"])
        self.assertFalse(self.accept({**PASS, "policy_conflicts": ["『0 を返す』に反し、例外を投げる"]})["ok"])

    def test_the_request_answers_are_recorded_rows(self):
        request = self.write("request.json", dump({"findings": [], "answers": [{"question": "q-1", "text": "決めた"}]}))
        self.intake(request=str(request))
        row, = self.intake_json()["recorded"]
        self.assertEqual((row["source"], row["name"]), ("answer", "q-1"))

    def test_push_marks_the_passed_rows_by_push(self):
        """test_verdict_marks_the_lines_an_unattended_run_passed_by_push（passes の by）"""
        self.intake(answers=dump({"before_fix": {"decision": "continue", "text": "x", "asked": [],
                                                 "pushed": [{"item": NARROW, "answer": "continue", "note": "x", "why": "y"}]}}),
                    asked=dump([{"kind": "regression", "text": NARROW}]))
        self.accept({**PASS, "capability_inventory": {"fired": True, "lost": [LOST]}})
        done = self.finish()
        self.assertEqual([p["by"] for p in done["passes"]], ["push"])
        self.assertEqual(done["questions"], [])

    def test_a_lost_row_that_copies_the_kind_head_keeps_its_pass(self):
        """役が指示の通した行の頭「[regression] 」を lost に写しても、同じ種類の頭なら外して照らし、問いにしない（9 の 17）"""
        self.intake(answers=dump({"before_fix": {"decision": "continue"}}), asked=dump([{"kind": "regression", "text": NARROW}]))
        self.accept({**PASS, "capability_inventory": {"fired": True, "lost": [f"[regression] {LOST}"]}})
        done = self.finish()
        self.assertEqual(done["questions"], [])
        self.assertEqual([p["item"] for p in done["passes"]], [f"R4 が BASE から消えたと見た能力: [regression] {LOST}"])

    def test_a_head_of_another_kind_is_asked_again(self):
        """ほかの種類の頭「[policy] 」を写した lost の行は外さず、聞き直す"""
        self.intake(answers=dump({"before_fix": {"decision": "continue"}}), asked=dump([{"kind": "regression", "text": NARROW}]))
        self.accept({**PASS, "capability_inventory": {"fired": True, "lost": [f"[policy] {LOST}"]}})
        done = self.finish()
        self.assertEqual(done["questions"], [f"R4 が BASE から消えたと見た能力: [policy] {LOST}"])
        self.assertEqual(done["passes"], [])

    def test_a_different_kind_is_asked_again(self):
        """種類が違えば聞き直す（regression で通した本文を policy_conflicts に書いても外れない）"""
        self.intake(answers=dump({"before_fix": {"decision": "continue"}}), asked=dump([{"kind": "regression", "text": NARROW}]))
        self.accept({**PASS, "policy_conflicts": [LOST]})
        self.assertEqual(self.finish()["questions"], [f"R4 が見た人の方針とのぶつかり: {LOST}"])


class CoherenceCase(_RepoCase):
    def test_coherence_adds_the_r3_section_and_reads_the_reply(self):
        """まとめた形（test_eye_verdict_reads_the_part_of_the_one_role_reply・test_r4_accept_takes_the_one_role_reply）"""
        self.intake(coherence="true")
        text = self.prep()["prompt"]
        for want in ("R3 overall coherence, in this same conversation", "You do not look at R1 or R2; other roles do",
                     "Where concepts live", "Map of where concepts live", "(none at the root of the target repository)",
                     "For R3, a conflict with the policy is judged by R3: write the item it conflicts with in `r3.reason`",
                     "First look at R3 and write `r3`, then look at R4."):
            self.assertIn(want, text)
        self.assertLess(text.index("R3 overall coherence, in this same conversation"), text.index("Map of where concepts live"))
        self.assertLess(text.index("Map of where concepts live"), text.index("As the inspector: R4"))
        r3 = {**R3, "status": "redesign-needed", "reason": "文書が古い"}
        self.assertTrue(self.accept({**PASS, "r3": r3})["ok"])
        done = self.finish()
        self.assertEqual(done["coherence"], {"status": "redesign-needed", "reason": "文書が古い"})
        self.assertEqual(done["verdict"]["status"], "pass")
        self.assertEqual(done["report"][:2], ["R4: pass（なし）", "R3（R4 と同じ会話で見た）: redesign-needed（文書が古い）"])

    def test_not_coherent_run_shows_no_r3_or_map(self):
        """まとめない run は R3 の節も地図も見せず、返答の r3 を読まない"""
        self.intake()
        text = self.prep()["prompt"]
        self.assertNotIn("R3 overall coherence", text)
        self.assertNotIn("Map of where concepts live", text)
        self.assertTrue(self.accept({**PASS, "r3": {"status": "bogus"}})["ok"])
        self.assertIsNone(self.finish()["coherence"])

    def test_missing_r3_is_rejected_and_resubmitted_with_r3_only(self):
        self.intake(coherence="true")
        self.prep()
        first = self.accept(PASS)
        self.assertEqual((first["ok"], first["done"]), (False, False))
        self.assertIn("欄 r3", first["reason"])
        self.assertNotIn(self.gate.R4_REJECT, first["reason"])
        self.assertTrue(self.prep(prev="false")["resubmit"])
        got = self.accept("null", {"r3": R3})
        self.assertEqual((got["ok"], got["done"]), (True, True), got["reason"])
        self.assertEqual(json.loads((self.place / "r4-scope.json").read_text(encoding="utf-8")), {**PASS, "r3": R3})
        for bad in ({"status": "pass", "reason": "", "seen": [], "unseen": []}, {"status": "weird", "reason": "x", "seen": [], "unseen": []},
                    {"status": "pass", "reason": "x", "seen": "a", "unseen": []},
                    {"status": "pass", "reason": "x", "seen": [], "unseen": "a"}, "x"):
            with self.subTest(bad=bad):
                self.assertFalse(self.accept({**PASS, "r3": bad})["ok"])
                (self.place / "rejects-r4-scope.json").unlink()

    def test_both_reasons_are_joined_in_one_rejection(self):
        doc = self.write("policy/abc.md", "一\n二\n")
        self.intake(coherence="true", policy=str(doc))
        got = self.accept({**PASS, "policy_conflicts": [LINE]})
        self.assertIn(self.gate.R4_REJECT, got["reason"])
        self.assertIn("欄 r3", got["reason"])
        self.assertIn("\n\n", got["reason"])

    def test_missing_r3_in_the_final_reply_gives_an_unverifiable_coherence_row(self):
        self.intake(coherence="true")
        self.accept(PASS)
        done = self.finish()
        self.assertEqual(done["coherence"]["status"], "unverifiable")
        self.assertIn("出力の欄 r3 が無い", done["coherence"]["reason"])

    def test_the_failed_finish_keeps_the_coherence_row_for_a_coherent_run(self):
        self.intake(coherence="true", answers="[1]")
        done = self.finish()
        self.assertEqual(done["coherence"]["status"], "unverifiable")


if __name__ == "__main__":
    unittest.main()
