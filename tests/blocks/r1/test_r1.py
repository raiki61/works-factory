"""block r1 を、script を子のプロセスで回して確かめる（docs/design/r1.md の 8 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → comments_prep → 台本の返答 → save →
minimality_prep → 台本の返答 → save → finish と回す。今の tests/workflows/test_eyes.py の ScriptCase と lib/tests/test_eyeverdict.py
の R1 の場面を、port の値で作り直した（各試験の docstring に元の試験の名を書く）。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。keep-essence の 9（独立設計と R1〜R4）の R1 の守りは、役が別の会話・読むだけ（test_r1_shape.py）と、
材料が修正の会話を持たないこと（test_inputs_carry_no_fix_conversation）が縛る。
"""
import json
import pathlib
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "r1"
DOC = yaml.safe_load((BLOCK / "works-factory-r1.yaml").read_text(encoding="utf-8"))
PORTS = ["base", "purpose", "units", "judgment", "fixes", "x_scalars", "green", "checks", "after", "review", "policy", "lang"]
COMMENTS = {"candidates": [{"where": "a.txt:1", "comment": "# 入口", "same_content_at": "README.md:1", "reason": "見出しの言い直し"}],
            "kept": [{"where": "a.txt:3", "fact": "既定の値を選んだ訳"}]}
PASS = {"status": "pass", "reason": "最小", "deletions": [], "ledger_audit": [], "increments": []}
AFTER = {"changed": ["a.txt"], "tables": [], "new_names": [{"name": "x", "sites": 2}], "dup_blocks_added": 2}
DEVIATION = {"item": 2, "row": "u2", "deviation": "入口を 2 つ残す（呼び手が別のリポジトリに在る）"}


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "r1")
        self.repo = self.run.repo
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.place = self.run.artifacts
        self.eyekit = kit.load("r1", "steps").eyekit

    def intake(self, **inputs):
        return self.run.script("intake", **{"base": self.base, **inputs})

    def comments(self):
        return self.run.script("comments_prep")["prompt"]

    def minimality(self):
        return self.run.script("minimality_prep")["prompt"]

    def save(self, name, reply):
        # 欄 name は Run.script の引数の名と重なるので、大文字の鍵で渡す（INPUTS_NAME になる）
        return self.run.script("save", NAME=name, reply=reply if isinstance(reply, str) else dump(reply))

    def finish(self):
        return self.run.script("finish")

    def write(self, name, text) -> pathlib.Path:
        path = self.run.artifacts.parent / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def intake_json(self) -> dict:
        return json.loads((self.place / "intake.json").read_text(encoding="utf-8"))


class ShapeCase(unittest.TestCase):
    def test_inputs_carry_no_fix_conversation(self):
        """keep-essence の 9 の R1: 入力は差分の根・目的・単位・台帳・結末・規模・証拠・実測・審査の結論・方針・言語だけで、修正の会話を
        運ぶ port が無い（目は材料だけで判じる）"""
        self.assertEqual(list(DOC["inputs"]), PORTS)

    def test_scripts_read_only_the_declared_inputs(self):
        import re
        read = set()
        for path in (BLOCK / "scripts").glob("*.py"):
            read |= {m.lower() for m in re.findall(r'os\.environ\.get\("INPUTS_([A-Z_]+)"', path.read_text(encoding="utf-8"))}
        self.assertEqual(read - {"name", "reply"}, set(PORTS))

    def test_save_names_are_the_ai_nodes(self):
        files = kit.load("r1", "files")
        saves = {n["with"]["name"] for n in DOC["nodes"] if n.get("script") == "save"}
        self.assertEqual(saves, set(files.REPLIES))
        self.assertEqual(set(files.REPLIES), {n["id"] for n in DOC["nodes"] if "prompt" in n})

    def test_fixture_reaches_every_node(self):
        fx = kit.fixture("r1", "standalone")
        self.assertEqual(fx["fixture"]["reached"], [n["id"] for n in DOC["nodes"]])


class FlowCase(_RepoCase):
    def test_flow_reaches_the_verdict_and_the_report(self):
        """筋: 2 つの役が返り、pass の判定の行と、削るとした所・残したコメントの事実の行を報告に出す"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.intake(purpose="古い入口を消す"), {"due": True, "reason": ""})
        self.assertIn("You are a meticulous code comment analyzer", self.comments())
        self.assertEqual(self.save("r1-comments", COMMENTS), {"saved": True})
        text = self.minimality()
        self.assertIn(f"Read `{self.place / 'r1-comments.json'}`", text)
        reply = {**PASS, "status": "fix-needed", "reason": "写しが在る", "deletions": [{"where": "a.txt:2", "why": "b.py:9 に同じ\n内容"}]}
        self.save("r1-minimality", reply)
        done = self.finish()
        self.assertEqual(done, {"ok": True, "status": "ran", "reason": "", "verdict": {"status": "fix-needed", "reason": "写しが在る"},
                                "questions": [], "report": ["R1: fix-needed（写しが在る）", "  - 削るとした所: a.txt:2（b.py:9 に同じ 内容）",
                                                            "  - 残したコメントが運ぶ事実: a.txt:3: 既定の値を選んだ訳"]})
        self.assertEqual(json.loads((self.place / "finish.json").read_text(encoding="utf-8")), done)

    def test_save_reply_writes_the_reply(self):
        """test_save_reply_writes_the_reply"""
        self.assertEqual(self.save("r1-comments", COMMENTS), {"saved": True})
        self.assertEqual(json.loads((self.place / "r1-comments.json").read_text(encoding="utf-8")), COMMENTS)

    def test_save_refuses_an_unknown_name(self):
        err = self.run.failing("save", NAME="r2-compare", reply=dump(PASS))
        self.assertIn("r2-compare", err)
        self.assertFalse((self.place / "r2-compare.json").exists())

    def test_minimality_runs_without_the_comment_candidates(self):
        """test_r1_minimality_runs_without_the_comment_candidates: 前段の返答が無い道は「取れなかった」の段落を持ち、報告にもそう書く"""
        self.intake()
        text = self.minimality()
        self.assertIn("could not be taken. Write why in the string field `candidates_note`", text)
        self.assertNotIn("Read `", text.split("could not be taken")[0].splitlines()[-1])
        self.assertIn("do not set `status` to unverifiable only because the earlier step is missing", text)
        self.save("r1-minimality", {**PASS, "candidates_note": "前段が無い"})
        done = self.finish()
        self.assertEqual(done["report"], ["R1: pass（最小）", "  - コメントの削除候補は取れなかった（出力のファイルが無い）"])

    def test_intake_clears_only_its_own_files(self):
        self.intake()
        self.save("r1-comments", COMMENTS)
        self.comments()
        other = self.place / "rejects-other.json"
        other.write_text("[]", encoding="utf-8")
        self.intake()
        self.assertFalse((self.place / "r1-comments.json").exists())
        self.assertFalse(list(self.place.glob("r1-comments-prompt-*.md")))
        self.assertTrue(other.exists())


class DiffCase(_RepoCase):
    def test_no_fix_round_sees_the_requested_change(self):
        """test_no_fix_round_sees_the_requested_change・test_prep_takes_the_diff_from_the_entry_base: 目は port base からの累積差分を読む"""
        (self.repo / "a.txt").write_text("頼まれた変更\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "requested")
        self.intake()
        diff = self.intake_json()["diff"]
        self.assertEqual((diff["base"], diff["changed"]), (self.base, ["a.txt"]))
        self.assertEqual(pathlib.Path(diff["file"]), self.place / "run.diff")
        self.assertIn("+頼まれた変更", (self.place / "run.diff").read_text(encoding="utf-8"))
        self.assertGreater(diff["lines"], 0)
        text = self.comments()
        self.assertIn(f"Cumulative diff: `{self.place / 'run.diff'}` (Read it. It is the difference from the base `{self.base}`", text)
        self.assertIn("Changed files: a.txt  Repository: ", text)

    def test_empty_diff_points_at_the_reason(self):
        """test_empty_diff_points_at_the_reason"""
        self.intake()
        doc = self.intake_json()
        self.assertEqual(doc["diff"]["lines"], 0)
        self.assertIn(self.base, pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))
        self.assertIn("変わったファイル 0 本", self.minimality())

    def test_untaken_diff_is_unmeasured_not_zero(self):
        """test_untaken_diff_is_unmeasured_not_zero: 引けない base は訳のファイルを指し、規模と変更ファイルを 0 にせず測れないと書く"""
        self.assertTrue(self.intake(base="no-such-rev")["due"])
        doc = self.intake_json()
        self.assertIn("累積差分が取れない", pathlib.Path(doc["diff"]["file"]).read_text(encoding="utf-8"))
        text = self.minimality()
        self.assertNotIn("変わったファイル 0 本", text)
        self.assertIn("測れなかった: 累積差分が取れない", text)
        self.assertIn("Changed files: 累積差分が取れない", text)

    def test_diff_leaves_out_the_runtime_copy(self):
        """test_prep_diff_leaves_out_the_archon_copy"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        ports = kit.load("r1", "steps").ports
        copy = self.repo / ports.RUNTIME_COPY / "workflows"
        copy.mkdir(parents=True)
        (copy / "x.yaml").write_text("name: x\n", encoding="utf-8")
        self.intake()
        self.assertEqual(self.intake_json()["diff"]["changed"], ["a.txt"])
        self.assertNotIn(ports.RUNTIME_COPY, (self.place / "run.diff").read_text(encoding="utf-8"))


class MaterialCase(_RepoCase):
    def test_units_fixes_and_scalars_are_listed(self):
        """PromptTextsCase.test_units_fixes_and_context_are_listed の units と fixes の半分と、規模の数値"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.intake(units=dump([{"id": "u1", "paths": ["a.txt"], "summary": "入口が古い"}]),
                    fixes=dump([{"unit_id": "u1", "group_id": "g1", "status": "fixed", "reason": "直した"}]),
                    x_scalars=dump({"x_endpoints": 2}))
        text = self.minimality()
        self.assertIn("Root units:\n- u1: 入口が古い（a.txt）\n", text)
        self.assertIn("Fixes in this run:\n- u1（組 g1）: fixed——直した\n", text)
        self.assertIn("Scalars: now 足した行 1・消した行 1・文書の足した行 0・変わったファイル 1 本・x_endpoints 2 / no previous round", text)
        self.assertIn("Frozen purpose: (not given)", text)

    def test_missing_units_and_fixes_say_so(self):
        self.intake()
        text = self.minimality()
        self.assertIn("（単位の目録が渡っていない）", text)
        self.assertIn("（修正の単位の結末が渡っていない）", text)

    def test_r1_minimality_reads_the_question_ledger(self):
        """test_r1_minimality_reads_the_question_ledger"""
        judgment = self.write("judge/judgment.json", dump({"units": [], "questions": []}))
        self.intake(judgment=str(judgment))
        text = self.minimality()
        self.assertIn(f"Question ledger: Read `questions` in `{judgment}`.", text)
        self.intake()
        self.assertIn("Question ledger: the judgment's output was not given", self.minimality())

    def test_prep_names_the_final_gate_evidence_for_r1(self):
        """test_prep_names_the_final_gate_evidence_for_r1: 証拠の文は pointer で受け、置き場のパスを Read させる"""
        evidence = self.run.artifacts / "test-gate" / "final" / "evidence.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("# test-gate（final）\n", encoding="utf-8")
        self.intake(checks=self.run.pointer("test-gate/final/evidence.md"))
        self.assertIn(f"Evidence of the last test gate: `{self.run.artifacts / 'test-gate' / 'final' / 'evidence.md'}` (Read it. "
                      "Also Read the log location the evidence names.)", self.minimality())

    def test_prep_says_when_no_gate_evidence_came(self):
        """test_prep_says_when_no_gate_evidence_came"""
        self.intake()
        self.assertIn("Evidence of the last test gate: none (最後の試験の関門の証拠が渡っていない).", self.minimality())

    def test_prep_names_an_unreadable_gate_evidence(self):
        """test_prep_names_an_unreadable_gate_evidence: 読めない証拠は落とさず、入力の名・読めないこと・先のパスを書く"""
        self.assertTrue(self.intake(checks=self.run.pointer("gone/evidence.md"))["due"])
        text = self.minimality()
        for want in ("入力 checks の証拠の文が読めない", str(self.run.artifacts / "gone" / "evidence.md")):
            self.assertIn(want, text)
        self.assertNotIn("最後の試験の関門の証拠が渡っていない", text)

    def test_green_paragraph_only_when_not_certified(self):
        """test_green_line_only_when_not_certified（段落の有無に）。既定の true は文を足さない"""
        line = "The certification of the last tests did not pass"
        self.intake()
        self.assertNotIn(line, self.minimality())
        self.intake(green="true")
        self.assertNotIn(line, self.minimality())
        self.intake(green="false")
        self.assertIn(line, self.minimality())

    def test_policy_body_is_pasted(self):
        """test_policy_path_is_frozen_copy（方針の本文が入る形に）: 方針の写しの本文を貼り、書く先は reason。無い run は節ごと入らない"""
        self.intake()
        self.assertNotIn("## The person's policy", self.minimality())
        policy = self.write("policy/frozen.md", "方針の第 1 項: 入口は 1 つ\n")
        self.intake(policy=str(policy))
        text = self.minimality()
        self.assertIn("## The person's policy", text)
        self.assertIn("方針の第 1 項: 入口は 1 つ", text)
        self.assertIn("This role makes a judgment, so write the item it conflicts with in `reason`", text)

    def test_prep_names_the_bundled_review_md(self):
        """test_prep_names_the_bundled_review_md: 同梱の観点の正本を 2 つの役に名指す"""
        self.intake()
        review = kit.ROOT / "lib" / "REVIEW.md"
        text = review.read_text(encoding="utf-8")
        for head in ("**処方の最小性", "**導線を作る手段の優先順位**"):
            self.assertIn(head, text)
        self.assertIn(f"`{review}`, the section \"導線を作る手段の優先順位\"", self.comments())
        self.assertIn(f"Canonical sources: `{review}` (\"処方の最小性\"", self.minimality())

    def test_concept_map_section_follows_the_tree(self):
        """test_concept_map_only_on_r1_and_r3 の r1 の半分: 地図の節は 2 段目にだけ在り、見つかった・無いで段落を選ぶ"""
        self.intake()
        self.assertNotIn("Map of where concepts live", self.comments())
        text = self.minimality()
        self.assertIn("## Map of where concepts live\n\nNone (searched for: the tracked file `docs/concepts.md`", text)
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "concepts.md").write_text("# map\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        text = self.minimality()
        self.assertIn("## Map of where concepts live (the machine searched the tracked files; Read it first)\n\n- docs/concepts.md\n", text)
        self.assertLess(text.index("## What minimal means"), text.index("## Map of where concepts live"))


class AfterCase(_RepoCase):
    def test_r1_head_carries_after_counts(self):
        """test_r1_head_carries_after_counts"""
        self.intake()
        self.assertIn(self.eyekit.NO_AFTER, self.minimality())
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[], after=AFTER)
        self.intake(after=str(path))
        text = self.minimality()
        self.assertIn(structmark.after_counts(folder) + "\n", text)
        self.assertIn("増えた写しの塊 2 個", text)
        self.assertNotIn(self.eyekit.NO_AFTER, text)

    def test_r1_head_carries_plan_deviations_and_the_plan_review_verdict(self):
        """test_r1_head_carries_plan_deviations_and_the_plan_review_verdict（port review で）"""
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[DEVIATION], after=AFTER)
        line = "  - 修正案の項目 2・設計の行 u2から外れる——入口を 2 つ残す（呼び手が別のリポジトリに在る）"
        self.intake(after=str(path), review=dump({"round": 2, "verdict": "accepted", "blocks": [], "why": ""}))
        text = self.minimality()
        self.assertIn(f"{structmark.after_counts(folder)}\n{line}\n{self.eyekit.REVIEW_ACCEPTED.format(k=2)}\n", text)
        self.intake(after=str(path), review=dump({"round": 3, "verdict": "blocked", "blocks": [{"key": "f1", "why": "入口は 1 つで足りる"}]}))
        self.assertIn(self.eyekit.REVIEW_BLOCKED.format(k=3, n=1, faces="f1: 入口は 1 つで足りる"), self.minimality())

    def test_empty_review_port_says_it_was_not_given(self):
        structmark = self.eyekit.structmark
        folder = self.run.artifacts.parent / "structure"
        folder.mkdir()
        path = structmark.write_after(folder, status="ok", reason="", deviations=[DEVIATION], after=AFTER)
        self.intake(after=str(path))
        self.assertIn(self.eyekit.REVIEW_UNREAD.format(why=self.eyekit.REVIEW_NOT_GIVEN), self.minimality())


class VerdictCase(_RepoCase):
    def ran(self, reply) -> dict:
        self.intake()
        self.save("r1-comments", COMMENTS)
        self.save("r1-minimality", reply)
        return self.finish()

    def test_r1_redesign_without_points_falls_to_fix_needed(self):
        """CollectCase.test_r1_redesign_without_points_falls_to_fix_needed"""
        done = self.ran({**PASS, "status": "redesign-needed", "reason": "冗長な写しが在る"})
        self.assertEqual(done["verdict"], {"status": "fix-needed", "reason": self.eyekit.UNNAMED_REDESIGN + "冗長な写しが在る"})
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))

    def test_r1_malformed_points_are_unverifiable_not_unnamed(self):
        """CollectCase.test_r1_malformed_points_are_unverifiable_not_unnamed"""
        done = self.ran({**PASS, "status": "redesign-needed", "reason": "冗長", "redesign_points": "設計の点"})
        self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": self.eyekit.BROKEN_POINTS + "冗長"})

    def test_r1_points_make_redesign_whatever_the_eye_wrote(self):
        """CollectCase.test_r1_points_make_redesign_whatever_the_eye_wrote"""
        done = self.ran({**PASS, "reason": "冗長", "redesign_points": ["返りの型を作り替える"]})
        self.assertEqual(done["verdict"], {"status": "redesign-needed",
                                           "reason": self.eyekit.RAISED_BY_POINTS + "冗長（組み直す設計の点: 返りの型を作り替える）"})

    def test_missing_eye_file_is_unverifiable_and_named(self):
        """CollectCase.test_missing_eye_file_is_unverifiable_and_named（R4 を回した尾は eyes のまとめが足す）"""
        self.intake()
        done = self.finish()
        reason = "R1 の筋が落ちた（r1: 出力のファイルが無い。ノードが落ちた）"
        self.assertEqual(done, {"ok": False, "status": "failed", "reason": reason, "verdict": {"status": "unverifiable", "reason": reason},
                                "questions": [], "report": [f"R1: unverifiable（{reason}）",
                                                            "  - コメントの削除候補は取れなかった（出力のファイルが無い）"]})

    def test_off_contract_status_is_named(self):
        """CollectCase.test_off_contract_status_is_named"""
        done = self.ran({**PASS, "status": "ok"})
        self.assertEqual((done["ok"], done["status"], done["verdict"]["status"]), (False, "failed", "unverifiable"))
        self.assertIn("約束の外", done["verdict"]["reason"])

    def test_a_port_that_cannot_be_read_fails_with_its_name(self):
        for name, raw in (("units", '{"rows": 1}'), ("judgment", self.run.pointer("absent.json")), ("policy", "/no/such/file.md"),
                          ("green", "yes"), ("review", dump({"verdict": "maybe"}))):
            with self.subTest(name):
                got = self.intake(**{name: raw})
                self.assertFalse(got["due"])
                self.assertTrue(got["reason"].startswith(f"入力 {name}: "), got["reason"])
                done = self.finish()
                self.assertEqual((done["ok"], done["status"], done["reason"]), (False, "failed", got["reason"]))
                self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": f"入力が読めない: {got['reason']}"})
                self.assertEqual(len(done["report"]), 1)

    def test_finish_never_fails(self):
        """test_verdict_never_fails の r1 の半分: 中の誤りでも落ちず、出口が落ちた形を返す"""
        self.intake()
        (self.place / "finish.json").mkdir()   # 写しを書けない
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["questions"]), (False, "failed", []))
        self.assertTrue(done["verdict"]["reason"].startswith("出口が落ちた: "), done["verdict"])
        self.assertEqual(done["verdict"]["status"], "unverifiable")
        self.assertEqual(len(done["report"]), 1)


class ScalarsCase(unittest.TestCase):
    """lib/tests/test_eyeverdict.py の ScalarsCase の全部（src/scalars.py に）"""
    DIFF = ("diff --git a/a.py b/a.py\nindex 1..2 100644\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n keep\n-old\n+new\n+more\n"
            "diff --git a/docs/x.md b/docs/x.md\nnew file mode 100644\n--- /dev/null\n+++ b/docs/x.md\n@@ -0,0 +1 @@\n+doc line\n")

    def setUp(self):
        self.s = kit.load("r1", "scalars")

    def test_counts_lines_and_files_from_the_diff(self):
        self.assertEqual(self.s.scalars(self.DIFF), {"added_lines": 3, "deleted_lines": 1, "doc_lines": 1, "files": ["a.py", "docs/x.md"]})

    def test_empty_diff_counts_zero(self):
        self.assertEqual(self.s.scalars(""), {"added_lines": 0, "deleted_lines": 0, "doc_lines": 0, "files": []})

    def test_hunk_lines_that_look_like_file_heads_are_counted(self):
        diff = "diff --git a/doc.md b/doc.md\n--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n title\n----\n+++i;\n"
        self.assertEqual(self.s.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["doc.md"]})

    def test_quoted_non_ascii_path_is_read(self):
        diff = ('diff --git "a/\\346\\226\\207.md" "b/\\346\\226\\207.md"\n--- "a/\\346\\226\\207.md"\n'
                '+++ "b/\\346\\226\\207.md"\n@@ -1 +1 @@\n-古い\n+新しい\n')
        self.assertEqual(self.s.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["文.md"]})

    def test_unreadable_diff_is_named_not_zero(self):
        got = self.s.scalars("これは差分でない")
        self.assertNotIn("added_lines", got)
        self.assertIn("測れなかった", self.s.scalars_text(got))

    def test_untaken_diff_is_named_not_zero(self):
        self.assertEqual(self.s.scalars("", {"x_endpoints": 2}, "累積差分が取れない（git が落ちた）"),
                         {"x_endpoints": 2, "unmeasured": ["累積差分が取れない（git が落ちた）"]})

    def test_fix_x_scalars_are_added(self):
        got = self.s.scalars(self.DIFF, {"x_endpoints": 2})
        self.assertEqual((got["x_endpoints"], got["added_lines"]), (2, 3))
        self.assertIn("x_endpoints 2", self.s.scalars_text(got))

    def test_part_measured_returns_the_measured_part(self):
        got = self.s.scalars("これは差分でない", {"x_endpoints": 2})
        self.assertEqual((got["x_endpoints"], got["unmeasured"]), (2, ["累積差分が git の差分の形でない"]))
        self.assertIn("測れなかった: 累積差分が git の差分の形でない", self.s.scalars_text(got))

    def test_x_scalars_outside_the_graph_shape_are_named(self):
        got = self.s.scalars(self.DIFF, {"x_ok": 1, "endpoints": 2, "x_flag": True})
        self.assertEqual(got["x_ok"], 1)
        self.assertNotIn("endpoints", got)
        self.assertNotIn("x_flag", got)
        self.assertIn("endpoints・x_flag", got["unmeasured"][0])
        self.assertIn("object でない", self.s.scalars(self.DIFF, [1])["unmeasured"][0])


if __name__ == "__main__":
    unittest.main()
