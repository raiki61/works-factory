"""block r3 を、script を子のプロセスで回して確かめる（docs/design/r3.md の 7 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → coherence_prep → 台本の返答 → save →
finish と回す。今の tests/workflows/test_eyes.py の ScriptCase と lib/tests/test_eyeverdict.py の R3 の場面を、port の値で作り直した
（各試験の docstring に元の試験の名を書く）。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
keep-essence の 9（独立設計と R1〜R4）の R3 の守りは、役が別の会話・読むだけ（test_r3_shape.py）と、入力が修正の会話を持たないこと
（test_inputs_carry_no_fix_conversation）が縛る。
"""
import json
import pathlib
import re
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "r3"
DOC = yaml.safe_load((BLOCK / "works-factory-r3.yaml").read_text(encoding="utf-8"))
PORTS = ["base", "lang", "green", "after", "review", "policy", "answers", "request", "pushes", "decisions"]
PASS = {"status": "pass", "reason": "整合", "seen": ["docs/concepts.md"], "unseen": []}
AFTER = {"changed": ["a.txt"], "tables": [], "new_names": [{"name": "x", "sites": 2}], "dup_blocks_added": 2}
DEVIATION = {"item": 2, "row": "u2", "deviation": "入口を 2 つ残す（呼び手が別のリポジトリに在る）"}
NO_ROWS = "- Policy document: none\n- The request's answers: none\n- People's answers at the approval nodes: none\n"


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "r3")
        self.repo = self.run.repo
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.place = self.run.artifacts
        self.eyekit = kit.load("r3", "steps").eyekit

    def intake(self, **inputs):
        return self.run.script("intake", **{"base": self.base, **inputs})

    def prompt(self):
        return self.run.script("coherence_prep")["prompt"]

    def save(self, reply):
        # 欄 name は Run.script の引数の名と重なるので、大文字の鍵で渡す（INPUTS_NAME になる）
        return self.run.script("save", NAME="r3-coherence", reply=reply if isinstance(reply, str) else dump(reply))

    def finish(self):
        return self.run.script("finish")

    def write(self, name, text) -> pathlib.Path:
        path = self.run.artifacts.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def intake_json(self) -> dict:
        return json.loads((self.place / "intake.json").read_text(encoding="utf-8"))

    def ran(self, reply) -> dict:
        self.intake()
        self.save(reply)
        return self.finish()


class ShapeCase(unittest.TestCase):
    def test_inputs_carry_no_fix_conversation(self):
        """keep-essence の 9 の R3: 入力は差分の根・言語・緑・実測・審査の結論・方針・記録された方針の素材だけで、修正の会話を運ぶ port が
        無い（目は材料だけで判じる）"""
        self.assertEqual(list(DOC["inputs"]), PORTS)

    def test_scripts_read_only_the_declared_inputs(self):
        read = set()
        for path in (BLOCK / "scripts").glob("*.py"):
            read |= {m.lower() for m in re.findall(r'os\.environ\.get\("INPUTS_([A-Z_]+)"', path.read_text(encoding="utf-8"))}
        self.assertEqual(read - {"name", "reply"}, set(PORTS))

    def test_save_name_is_the_ai_node(self):
        files = kit.load("r3", "files")
        self.assertEqual({n["with"]["name"] for n in DOC["nodes"] if n.get("script") == "save"}, set(files.REPLIES))
        self.assertEqual(set(files.REPLIES), {n["id"] for n in DOC["nodes"] if "prompt" in n})

    def test_fixture_reaches_every_node(self):
        fx = kit.fixture("r3", "standalone")
        self.assertEqual(fx["fixture"]["reached"], [n["id"] for n in DOC["nodes"]])


class FlowCase(_RepoCase):
    def test_flow_reaches_the_verdict_and_the_report(self):
        """筋: 役が返り、判定の行と頭の 1 行の報告を出す（seen・unseen は報告に載せない）。finish.json にも同じ物を書く"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.intake(), {"due": True, "reason": ""})
        self.assertIn("You are one of the independent eyes (R3 overall coherence), started in a new conversation.", self.prompt())
        self.assertEqual(self.save(PASS), {"saved": True})
        done = self.finish()
        self.assertEqual(done, {"ok": True, "status": "ran", "reason": "", "verdict": {"status": "pass", "reason": "整合"},
                                "questions": [], "report": ["R3: pass（整合）"]})
        self.assertEqual(json.loads((self.place / "finish.json").read_text(encoding="utf-8")), done)

    def test_redesign_needed_passes_through(self):
        """R3 は redesign_points を読まない（R1 だけ）。返答の status と reason のまま"""
        done = self.ran({**PASS, "status": "redesign-needed", "reason": "考えの住処: docs/design.md の行が古い", "redesign_points": ["x"]})
        self.assertEqual(done["verdict"], {"status": "redesign-needed", "reason": "考えの住処: docs/design.md の行が古い"})
        self.assertTrue(done["ok"])

    def test_save_refuses_an_unknown_name(self):
        err = self.run.failing("save", NAME="r4-scope", reply=dump(PASS))
        self.assertIn("r4-scope", err)
        self.assertFalse((self.place / "r4-scope.json").exists())

    def plant_old_files(self) -> dict:
        """この block が名を持つファイルの全部（と前の回の指示）を「前の run の物」の字で置く"""
        files = kit.load("r3", "files")
        old = {name: self.place / name for name in files.OWN_FILES}
        old.update({p.replace("*", "1"): self.place / p.replace("*", "1") for p in files.OWN_PROMPTS})
        for path in old.values():
            path.write_text("old", encoding="utf-8")
        return old

    def test_intake_clears_only_its_own_files(self):
        """入口は src/files.py が名を持つファイルの全部と前の回の指示を消し（書き直す物は新しい字）、ほかのファイルは残す"""
        old = self.plant_old_files()
        other = self.place / "rejects-other.json"
        other.write_text("[]", encoding="utf-8")
        self.intake()
        for name, path in old.items():
            with self.subTest(name):
                self.assertFalse(path.is_file() and path.read_text(encoding="utf-8") == "old", name)
        self.assertTrue(other.exists())

    def test_intake_that_cannot_read_lib_still_clears_its_files(self):
        """lib を読めずに落ちた入口も、この block のファイルを名で消して落ちた訳を返す"""
        import subprocess
        import sys
        from tests.bin import hermetic
        old = self.plant_old_files()
        env = hermetic.child_env(**{**self.run.environ(), "WORKS_FACTORY_ROOT": str(self.run.artifacts.parent / "no-lib")})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "intake.py")], cwd=self.repo, env=env, capture_output=True,
                              text=True, encoding="utf-8")
        got = json.loads(done.stdout)
        self.assertFalse(got["due"])
        self.assertIn("R3 の入口が落ちた", got["reason"])
        self.assertEqual([n for n, p in old.items() if p.exists()], [])
        self.assertEqual(self.finish()["status"], "failed")

    def test_output_that_json_cannot_hold_is_refused_before_the_copy(self):
        """NaN・Infinity は finish.json を書く前に落とす（script の出口はこれを落ちた形にする）"""
        from unittest import mock
        steps = kit.load("r3", "steps")
        self.intake()
        self.save(PASS)
        with self.run.env(), mock.patch.object(steps.eyekit, "verdict_row", return_value=({"status": "pass", "reason": float("nan")}, True)):
            with self.assertRaisesRegex(ValueError, "JSON に書けない"):
                steps.finish(self.place)
        self.assertFalse((self.place / "finish.json").exists())

    def test_prompt_needs_the_intake(self):
        """入口が落ちていれば指示を組めない（node が落ち、出口が判定の行にする）"""
        self.assertIn("intake.json", self.run.failing("coherence_prep"))


class VerdictCase(_RepoCase):
    def test_missing_eye_file_is_unverifiable_and_named(self):
        """CollectCase.test_missing_eye_file_is_unverifiable_and_named の R3"""
        self.intake()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["verdict"]["status"], "unverifiable")
        self.assertIn(self.eyekit.FELL_MARK, done["verdict"]["reason"])
        self.assertTrue(done["verdict"]["reason"].startswith("R3 "), done["verdict"]["reason"])
        self.assertEqual(done["reason"], done["verdict"]["reason"])
        self.assertEqual(len(done["report"]), 1)

    def test_unreadable_eye_file_is_unverifiable(self):
        """CollectCase.test_unreadable_eye_file_is_unverifiable の R3"""
        self.intake()
        self.save("{")
        done = self.finish()
        self.assertEqual((done["ok"], done["verdict"]["status"]), (False, "unverifiable"))
        self.assertIn(self.eyekit.FELL_MARK, done["verdict"]["reason"])

    def test_off_contract_status_is_named(self):
        """CollectCase.test_off_contract_status_is_named の R3（R1 だけの fix-needed も約束の外）"""
        for word in ("ok", "fix-needed"):
            with self.subTest(word):
                done = self.ran({**PASS, "status": word})
                self.assertEqual((done["ok"], done["status"], done["verdict"]["status"]), (False, "failed", "unverifiable"))
                self.assertIn("約束の外", done["verdict"]["reason"])
                self.assertTrue(done["verdict"]["reason"].startswith("R3 "), done["verdict"]["reason"])

    def test_unreadable_port_is_failed_with_the_port_named(self):
        """読めない port は役を起こさず、入口が due: false と訳を返し、出口は failed の判定の行にする"""
        got = self.intake(green="maybe")
        self.assertFalse(got["due"])
        self.assertTrue(got["reason"].startswith("入力 green: "), got["reason"])
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["verdict"]["status"]), (False, "failed", "unverifiable"))
        self.assertEqual(done["verdict"]["reason"], "入力が読めない: " + got["reason"])
        self.assertEqual(done["report"], [f"R3: unverifiable（{done['verdict']['reason']}）"])

    def test_missing_request_file_is_an_unreadable_port(self):
        got = self.intake(request=str(self.repo / "gone.json"))
        self.assertFalse(got["due"])
        self.assertTrue(got["reason"].startswith("入力 request: "), got["reason"])

    def test_missing_decisions_path_is_an_unreadable_port(self):
        got = self.intake(decisions=str(self.repo / "gone" / "material.json"))
        self.assertFalse(got["due"])
        self.assertTrue(got["reason"].startswith("入力 decisions: "), got["reason"])

    def test_unfit_answers_shape_is_named(self):
        got = self.intake(answers=dump({"start": "continue"}))
        self.assertFalse(got["due"])
        self.assertTrue(got["reason"].startswith("入力 answers: "), got["reason"])


class DiffCase(_RepoCase):
    def test_the_diff_is_read_from_the_base(self):
        """test_prep_takes_the_diff_from_the_entry_base: 役は port base からの累積差分を読む"""
        (self.repo / "a.txt").write_text("頼まれた変更\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "requested")
        self.intake()
        diff = self.intake_json()["diff"]
        self.assertEqual((diff["base"], diff["changed"]), (self.base, ["a.txt"]))
        self.assertEqual(pathlib.Path(diff["file"]), self.place / "run.diff")
        self.assertIn("+頼まれた変更", (self.place / "run.diff").read_text(encoding="utf-8"))
        self.assertIn(f"Cumulative diff: `{self.place / 'run.diff'}` (Read it. It is the difference from the base `{self.base}`", self.prompt())
        self.assertIn("Changed files: a.txt  Repository: ", self.prompt())

    def test_empty_and_untaken_diff_point_at_the_reason(self):
        """test_empty_diff_points_at_the_reason・test_untaken_diff_is_unmeasured_not_zero: 空・取れない差分でも止めず、訳のファイルを指す"""
        self.intake()
        doc = self.intake_json()
        self.assertEqual(doc["diff"]["lines"], 0)
        self.assertIn(self.base, pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))
        self.assertTrue(self.intake(base="no-such-rev")["due"])
        self.assertIn("累積差分が取れない", pathlib.Path(self.intake_json()["diff"]["file"]).read_text(encoding="utf-8"))
        self.assertIn("Changed files: 累積差分が取れない", self.prompt())

    def test_diff_leaves_out_the_runtime_copy(self):
        """test_prep_diff_leaves_out_the_archon_copy"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        ports = kit.load("r3", "steps").ports
        copy = self.repo / ports.RUNTIME_COPY / "workflows"
        copy.mkdir(parents=True)
        (copy / "x.yaml").write_text("name: x\n", encoding="utf-8")
        self.intake()
        self.assertEqual(self.intake_json()["diff"]["changed"], ["a.txt"])
        self.assertNotIn(ports.RUNTIME_COPY, (self.place / "run.diff").read_text(encoding="utf-8"))


class MaterialCase(_RepoCase):
    def test_prompt_names_the_bundled_and_the_target_review_md(self):
        """test_prep_pastes_the_premises_and_names_the_target_review_md の REVIEW.md の半分（在る時はパス、無い時は札）"""
        review = kit.SHARED / "prompts" / "REVIEW.md"
        self.intake()
        self.assertIn(f"The canonical sources: `{review}` (on the target repository's side: (none at the root of the target repository))",
                      self.prompt())
        (self.repo / "REVIEW.md").write_text("# 観点\n", encoding="utf-8")
        self.intake()
        self.assertIn(f"(on the target repository's side: {self.repo / 'REVIEW.md'})", self.prompt())

    def test_green_paragraph_only_when_not_certified(self):
        """test_green_line_only_when_not_certified（段落の有無に）。既定の true は文を足さない"""
        line = "The certification of the last tests did not pass"
        self.intake()
        self.assertNotIn(line, self.prompt())
        self.intake(green="true")
        self.assertNotIn(line, self.prompt())
        self.intake(green="false")
        self.assertIn(line, self.prompt())

    def test_policy_body_is_pasted(self):
        """test_policy_path_is_frozen_copy（方針の本文が入る形に）: 方針の写しの本文を貼り、書く先は reason。無い run は節ごと入らない"""
        self.intake()
        self.assertNotIn("## The person's policy", self.prompt())
        policy = self.write("policy/frozen.md", "方針の第 1 項: 入口は 1 つ\n")
        self.intake(policy=str(policy))
        text = self.prompt()
        self.assertIn("## The person's policy", text)
        self.assertIn("方針の第 1 項: 入口は 1 つ", text)
        self.assertIn("This role makes a judgment, so write the item it conflicts with in `reason`", text)

    def test_concept_map_section_follows_the_tree(self):
        """test_concept_map_only_on_r1_and_r3 の r3 の半分: 見つかった・無いで段落を選び、住処の観点の後ろに在る"""
        self.intake()
        text = self.prompt()
        self.assertIn("## Map of where concepts live\n\nNone (searched for: the tracked file `docs/concepts.md`", text)
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "concepts.md").write_text("# map\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        text = self.prompt()
        self.assertIn("## Map of where concepts live (the machine searched the tracked files; Read it first)\n\n- docs/concepts.md\n", text)
        self.assertLess(text.index("## Where concepts live"), text.index("## Map of where concepts live"))
        self.assertIn("start `reason` with \"考えの住処: \"", text)

    def test_status_words_are_the_three_of_r3(self):
        self.intake()
        text = self.prompt()
        self.assertIn("`status` is one of pass, redesign-needed, unverifiable, with the reason in `reason`.", text)
        self.assertNotIn("fix-needed", text)


class AfterCase(_RepoCase):
    def test_head_carries_after_counts(self):
        """test_r1_head_carries_after_counts の R3 の半分"""
        self.intake()
        self.assertIn(self.eyekit.NO_AFTER, self.prompt())
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[], after=AFTER)
        self.intake(after=str(path))
        text = self.prompt()
        self.assertIn(structmark.after_counts(folder) + "\n", text)
        self.assertIn("増えた写しの塊 2 個", text)
        self.assertNotIn(self.eyekit.NO_AFTER, text)

    def test_head_carries_plan_deviations_and_the_plan_review_verdict(self):
        """test_r1_head_carries_plan_deviations_and_the_plan_review_verdict の R3 の半分（port review で）"""
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[DEVIATION], after=AFTER)
        line = "  - 修正案の項目 2・設計の行 u2から外れる——入口を 2 つ残す（呼び手が別のリポジトリに在る）"
        self.intake(after=str(path), review=dump({"round": 2, "verdict": "accepted", "blocks": [], "why": ""}))
        self.assertIn(f"{structmark.after_counts(folder)}\n{line}\n{self.eyekit.REVIEW_ACCEPTED.format(k=2)}\n", self.prompt())
        self.intake(after=str(path))
        self.assertIn(self.eyekit.REVIEW_UNREAD.format(why=self.eyekit.REVIEW_NOT_GIVEN), self.prompt())


class RecordedPolicyCase(_RepoCase):
    def test_a_run_without_rows_says_none(self):
        """test_prep_carries_the_recorded_policy_section: 方針の文書の無い run の役にも、記録された方針の節が「無い」と載る（#427）"""
        self.intake()
        text = self.prompt()
        self.assertIn("## Recorded policy", text)
        self.assertIn("Recorded policy: none (no row below can be named).", text)
        self.assertIn(NO_ROWS, text)
        self.assertEqual(self.intake_json()["recorded"], [])

    def test_gate_answers_the_request_answers_and_the_policy_copy_become_rows(self):
        """方針の写し・依頼の answers・承認ノードの人の答えが行になって指示に入る（記録された方針の一覧の 4 つの出どころのうち 3 つ）"""
        policy = self.write("policy/frozen.md", "a\nb\nc\n")
        request = self.write("request.json", dump({"findings": [], "answers": [{"question": "入口は何本か", "text": "1 本"}]}))
        self.intake(policy=str(policy), request=str(request),
                    answers=dump({"start": {"decision": "continue", "text": "入口は 1 つに絞る"}, "before_fix": None}))
        rows = self.intake_json()["recorded"]
        self.assertEqual([r["source"] for r in rows], ["doc", "answer", "gate"])
        text = self.prompt()
        self.assertNotIn("Recorded policy: none", text)
        self.assertIn(f"- Policy document: name `{policy}:<line>` (lines 1-3;", text)
        self.assertIn("  - name `入口は何本か`: 1 本", text)
        self.assertIn(f"  - name `{rows[2]['name']}`: 入口は 1 つに絞る", text)

    def test_push_an_unattended_run_took_is_a_row(self):
        """test_r4_can_name_the_push_an_unattended_run_took_for_a_held_question の推しの行が記録された方針に入る半分（port pushes で）。
        承認ノードの人の答えには混ぜない"""
        push = "0 を返す——呼び手が既に 0 を前提にしている"
        self.intake()
        self.assertEqual(self.intake_json()["recorded"], [])
        self.intake(pushes=dump([f"問い q-a: {push}"]))
        row, = self.intake_json()["recorded"]
        self.assertEqual((row["source"], row["text"]), ("push", f"問い q-a: {push}"))
        self.assertTrue(row["name"].startswith("無人の run が採った推し "), row["name"])
        text = self.prompt()
        self.assertIn(f"  - name `{row['name']}`: 問い q-a: {push}", text)
        self.assertIn("People's answers at the approval nodes: none", text)

    def test_settled_points_from_the_prior_decisions_material(self):
        """port decisions の material.json の reply.settled の where が名指しの行になる"""
        material = self.write("prior/material.json", dump({"reply": {"settled": [{"where": "docs/d.md:3", "topic": "入口", "decision": "1 つ"}]}}))
        self.intake(decisions=str(material))
        row, = self.intake_json()["recorded"]
        self.assertEqual((row["source"], row["name"]), ("settled", "docs/d.md:3"))
        self.assertIn("  - name `docs/d.md:3`: 入口——1 つ", self.prompt())

    def test_unreadable_request_content_does_not_stop_the_role(self):
        """依頼のファイルの中身が依頼の形に合わなくても止めない: answers は空にして、訳を intake.json の unread に残す。finish は落ちない
        （JSON として読めないファイルは port の誤り。#851 で ports.file が形を照らすようになった）"""
        request = self.write("request.json", '{"findings": 3}')
        self.assertEqual(self.intake(request=str(request)), {"due": True, "reason": ""})
        doc = self.intake_json()
        self.assertTrue(doc["unread"], doc)
        self.assertEqual(doc["recorded"], [])
        self.assertIn("Recorded policy: none", self.prompt())
        self.assertIn("- " + doc["unread"], self.prompt())
        self.assertTrue(doc["unread"].startswith("依頼のファイルの中身が読めない"), doc)
        self.save(PASS)
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))
        self.assertEqual(self.intake(request=str(self.write("ok.json", dump({"findings": []}))))["due"], True)
        self.assertEqual(self.intake_json()["unread"], "")


if __name__ == "__main__":
    unittest.main()
