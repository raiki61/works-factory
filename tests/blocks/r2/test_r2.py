"""block r2 を、script を子のプロセスで回して確かめる（docs/design/r2.md の 8 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → 支度 → 台本の返答 → save → finish と回す。
今の tests/workflows/test_eyes.py の ScriptCase と lib/tests/test_eyeverdict.py の R2 の場面を、port の値で作り直した（各試験の
docstring に元の試験の名を書く）。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import os
import pathlib
import unittest
from unittest import mock

from tests.bin.gitkit import git
from tests.blocks import kit

STANDS = {"question_stands": True, "reason": "立つ", "design": "設計の本文", "elements": []}
NOT_STANDS = {"question_stands": False, "reason": "既に入っている", "premise_invalid_reason": "上限が既に在る", "design": ""}
PASS = {"status": "pass", "reason": "構造は一致", "differences": [{"kind": "表現", "text": "呼び名が違う"}]}
CHECK = {"key": "上限を呼び手ごとに持つか", "assumption": "上限が無い", "assumption_false": True, "evidence": "config.py:3",
         "verdict": "resolved", "reason": "上限は在る", "resolution": "config.py:3 に上限 10", "facts_to_add": ["上限は config.py:3 の 10"]}


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "r2")
        self.repo = self.run.repo
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD").strip()
        self.place = self.run.artifacts

    def intake(self, **inputs):
        return self.run.script("intake", **{"base": self.base, "purpose": "入口を 1 つにする", "design": dump(STANDS), **inputs})

    def compare(self):
        return self.run.script("compare_prep")

    def premise(self):
        return self.run.script("premise_prep")["prompt"]

    def save(self, name, reply):
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


class CompareRoadCase(_RepoCase):
    def test_flow_reaches_the_verdict_and_the_report(self):
        """筋: 問いが立つ設計と差分を比べる役が返り、pass の判定の行と、渡した入力の控えの行を報告に出す"""
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        self.assertEqual(self.intake(), {"compare": True, "premise": False, "reason": ""})
        got = self.compare()
        self.assertIn("The whole diff is in this file", got["prompt"])
        self.assertIn(str(self.place / "run.diff"), got["prompt"])
        self.assertIn("設計の本文", got["prompt"])
        self.assertIn("入口を 1 つにする", got["prompt"])
        self.assertIn("All the instructions are in the body", got["system"])
        self.assertNotIn("{", got["system"])
        self.assertEqual(self.save("r2-compare", PASS), {"saved": True})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["reason"]), (True, "ran", ""))
        self.assertEqual(done["verdict"], {"status": "pass", "reason": "構造は一致"})
        self.assertIsNone(done["premise_check"])
        self.assertEqual(done["questions"], [])
        self.assertEqual(done["report"][0], "R2: pass（構造は一致）")
        self.assertEqual(done["report"][1:], [f"  - {x}" for x in done["notes"]])
        self.assertIn("独立の設計を作る役に渡した入力の控えが無い（design）", done["notes"])
        self.assertEqual(json.loads((self.place / "finish.json").read_text(encoding="utf-8")), done)
        self.assertEqual(json.loads((self.place / "r2-premises.json").read_text(encoding="utf-8"))["node"], "r2.compare")

    def test_prompt_pastes_the_measured_test_outcomes_and_the_tdd_proof(self):
        """test_prep_pastes_the_measured_test_outcomes_and_the_tdd_proof（issue #384）: tdd の port で。渡っていない時は測っていないと書く"""
        self.intake()
        none = self.compare()["prompt"]
        self.assertIn("test_outcomes）が渡っていない", none)
        self.assertIn("修正の段が走っていない", none)
        outcomes = {"rows": [{"key": "tests.test_stats.TestStats::test_clamp_above_range", "base": "failure", "final": "passed",
                              "fail_message": "AssertionError: 0 != 10"}], "unmeasured": ""}
        tdd = [[{"group_id": "g1", "ran": True, "reason": "", "suite": "", "reused": {},
                 "units": [{"unit_key": "u1", "route": "tdd", "red": "ok", "green": "ok",
                            "tests": ["tests/test_stats.py::TestStats::test_clamp_above_range"]}]}]]
        self.intake(test_outcomes=dump(outcomes), tdd=dump(tdd))
        got = self.compare()["prompt"]
        self.assertIn("  - `tests.test_stats.TestStats::test_clamp_above_range`（base failure: AssertionError: 0 != 10）", got)
        self.assertIn("u1: 赤 ok・緑 ok", got)
        self.assertIn("名指しのテスト tests/test_stats.py::TestStats::test_clamp_above_range", got)

    def test_green_to_green_tests_are_named_in_the_compare_prompt(self):
        """test_rename_without_red_puts_the_green_tests_in_the_compare_prompt（issue #384）"""
        names = [f"tests.test_stats.TestMedian::test_{n}" for n in ("odd", "even", "single")]
        outcomes = {"rows": [{"key": k, "base": "passed", "final": "passed", "fail_message": ""} for k in names], "unmeasured": ""}
        self.intake(test_outcomes=dump(outcomes))
        text = self.compare()["prompt"]
        self.assertIn("- 緑→緑（base でも最後でも緑）: 3 件", text)
        for k in names:
            self.assertIn(f"  - `{k}`\n", text)
        self.assertLess(text.index(names[-1]), text.index("Before you write that something is missing"))

    def test_origin_names_the_pr_diff_and_the_fix_diff_apart(self):
        """test_prep_names_the_pr_diff_and_the_fix_diff_apart（issue #384）: head の port で"""
        (self.repo / "a.txt").write_text("pr\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "pr")
        head = git(self.repo, "rev-parse", "HEAD").strip()
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        self.intake(head=head, base_label="PR #7 の根")
        text = self.compare()["prompt"]
        self.assertIn(f"起点は PR の根 `{self.base[:12]}`（PR #7 の根）", text)
        self.assertIn("PR の差分（起点 → 修正前の HEAD）で変わったファイル: a.txt", text)
        self.assertIn("この run の直しの差分（修正前の HEAD → 作業ツリー）で変わったファイル: a.txt", text)
        self.assertIn("打ち消し合った", text)

    def test_premises_are_pasted_and_the_late_answers_are_split(self):
        """test_prep_pastes_the_premises_and_names_the_target_review_md の前提の半分・test_prep_reads_constraints_from_the_premises_input:
        独立設計が見た数より後の答えは「後に来た答え」に分かれ、前提のずれ・記録の制約が載る"""
        request = self.write("request.md", "`docs/d.md` の 2 節のとおりに入口を直す")
        answers = {"start": {"decision": "continue", "text": "入口は 1 つに絞る"}, "before_fix": {"decision": "continue", "text": "古い入口は消してよい"}}
        constraints = [{"kind": "実測", "text": "1 デプロイは 2 リポジトリ", "measured_how": "grep"}]
        self.intake(answers=dump(answers), request=str(request), constraints=dump(constraints), lang="English",
                    design_premises=dump({"given": [], "withheld": [], "seen": {"count": 1, "last_round": 1}}),
                    changed=dump({"premise_drift": True, "premise_drift_note": "入口は 2 つあった"}))
        text = self.compare()["prompt"]
        for want in ("古い入口は消してよい", "入口は 2 つあった", "（実測）1 デプロイは 2 リポジトリ", "### Map of the target repository",
                     "### Sections of design documents the request names", "依頼が名指したが引けなかった: docs/d.md 2 節",
                     "### Answers that came after the independent design", "English"):
            with self.subTest(want):
                self.assertIn(want, text)
        late = text.partition("### Answers that came after the independent design")[2].partition("### Drift")[0]
        self.assertIn("古い入口は消してよい", late)
        self.assertNotIn("入口は 1 つに絞る", late)
        ledger = json.loads((self.place / "r2-premises.json").read_text(encoding="utf-8"))
        self.assertEqual(len([g for g in ledger["given"] if g["kind"] == "human_answer"]), 2)
        self.assertEqual(len(ledger["after_design"]), 1)
        self.assertEqual([g["kind"] for g in ledger["given"] if g["kind"] in ("drift", "constraint")], ["drift", "constraint"])

    def test_without_the_design_premises_nothing_is_split_as_late(self):
        self.intake(answers=dump({"start": {"decision": "continue", "text": "x"}}))
        text = self.compare()["prompt"]
        self.assertNotIn("Answers that came after the independent design", text)
        self.assertIn("（修正の印が渡っていない）", text)
        self.assertIn("### Recorded constraints\n\n（無い）", text)
        self.assertNotIn("after_design", json.loads((self.place / "r2-premises.json").read_text(encoding="utf-8")))

    def test_unreadable_request_says_so(self):
        """依頼のファイルが渡っていない時、request_unread の段落と withheld の行が入る"""
        self.intake()
        text = self.compare()["prompt"]
        self.assertIn("The request file could not be read", text)
        ledger = json.loads((self.place / "r2-premises.json").read_text(encoding="utf-8"))
        self.assertIn({"kind": "named_section", "what": "依頼", "why": "依頼のファイルが渡っていない"}, ledger["withheld"])
        self.intake(request=str(self.write("request.md", "依頼")))
        self.assertNotIn("The request file could not be read", self.compare()["prompt"])

    def test_notes_carry_the_unpassed_claims_and_what_was_given(self):
        """test_verdict_writes_the_notes_for_the_final_gate（E45）: 比べの役が『渡されていない』と書いた文と、渡していた物"""
        answers = {"start": {"decision": "continue", "text": "x"}}
        self.intake(answers=dump(answers), design_premises=dump({"given": [], "withheld": [], "seen": {"count": 0}}))
        self.compare()
        self.save("r2-compare", {"status": "pass", "reason": "人の答えが渡されていない", "differences": []})
        done = self.finish()
        self.assertIn("独立の設計と比べる目が渡されていないと書いた（R2）: 人の答えが渡されていない", done["notes"])
        self.assertTrue(any("渡していた（R2）" in n and "human_answer" in n for n in done["notes"]))
        self.assertTrue(any(n.startswith("独立設計の後に来た人の答え") for n in done["notes"]))
        saved = json.loads((self.place / "premise-inputs.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["claims"], ["人の答えが渡されていない"])
        self.assertEqual(saved["design"], {"given": [], "withheld": [], "seen": {"count": 0}})
        self.assertEqual([c["kind"] for c in saved["compare"]["claims_given"]], ["human_answer"])

    def test_missing_reply_fails_the_road(self):
        self.intake()
        self.compare()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["verdict"]["status"], "unverifiable")
        self.assertIn("R2 の筋が落ちた", done["verdict"]["reason"])
        self.assertEqual(done["reason"], done["verdict"]["reason"])

    def test_off_contract_status_fails_the_road(self):
        self.intake()
        self.compare()
        self.save("r2-compare", {"status": "fix-needed", "reason": "x", "differences": []})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertIn("出力の判定の語が約束の外", done["verdict"]["reason"])

    def test_redesign_is_still_a_run_of_the_block(self):
        self.intake()
        self.compare()
        self.save("r2-compare", {"status": "redesign-needed", "reason": "構造が違う", "differences": [{"kind": "構造", "text": "t"}]})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["verdict"]["status"]), (True, "ran", "redesign-needed"))

    def test_save_refuses_an_unknown_name(self):
        err = self.run.failing("save", NAME="r1-comments", reply=dump(PASS))
        self.assertIn("r1-comments", err)
        self.assertFalse((self.place / "r1-comments.json").exists())

    def test_intake_clears_only_its_own_files(self):
        self.intake()
        self.save("r2-compare", PASS)
        self.compare()
        other = self.place / "rejects-other.json"
        other.write_text("[]", encoding="utf-8")
        self.intake()
        self.assertFalse((self.place / "r2-compare.json").exists())
        self.assertFalse(list(self.place.glob("r2-compare-prompt-*.md")))
        self.assertTrue(other.exists())

    def test_empty_diff_points_at_the_reason(self):
        """test_empty_diff_points_at_the_reason: 差分が空でも止めず、訳が累積差分の代わりのファイルに載る"""
        self.intake()
        text = self.compare()["prompt"]
        self.assertIn("(0 lines;", text)
        self.assertTrue(pathlib.Path(self.intake_json()["diff"]["file"]).is_file())
        self.assertIn("PR も直しも何も変えていない", text)
        self.assertNotIn("打ち消し", text)

    def test_runtime_copy_is_left_out_of_the_origin_section(self):
        """test_skipped_paths_are_left_out_of_the_pr_diff_too: Archon が作業ツリーに写す置き場の下は、直しの差分のファイルに載らない"""
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "w.yaml").write_text("x: 1\n", encoding="utf-8")
        self.intake()
        text = self.compare()["prompt"]
        self.assertNotIn(".archon", text)
        self.assertIn("この run の直しの差分（修正前の HEAD → 作業ツリー）で変わったファイル: 無い", text)


class PremiseSectionCase(_RepoCase):
    """元 PremiseSectionCase のうち、貼りと後に来た答え以外（名指しの引き方・控えの kind の柵・渡っていない物の言い方）を block の筋で"""

    def setUp(self):
        super().setUp()
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "d.md").write_text("# 設計\n\n## 2 入口\n\n入口は 1 つ\n\n## 3 出口\n\n出口\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "docs")

    def ledger(self) -> dict:
        return json.loads((self.place / "r2-premises.json").read_text(encoding="utf-8"))

    def named(self, request: str) -> tuple:
        self.intake(request=str(self.write("request.md", request)))
        text = self.compare()["prompt"]
        return text, self.ledger()

    def test_link_anchor_finds_the_heading_by_its_slug(self):
        _, ledger = self.named("[入口](docs/d.md#2-入口) のとおりに直す")
        self.assertIn({"kind": "named_section", "what": "docs/d.md#2-入口"}, ledger["given"])

    def test_heading_inside_a_code_fence_is_not_an_anchor(self):
        """名指された文書の見出しは囲い（``` と ~~~。情報文字列つきも）の外だけを読む: 囲いの中の # 行はアンカーにならず、節も切らない"""
        for fence in ("```", "```js title=x", "~~~"):
            with self.subTest(fence):
                (self.repo / "docs" / "f.md").write_text(
                    f"# 設計\n\n## 2 入口\n\n{fence}\n## 9 偽\n{fence[:3]}\n\nBODY-2-TAIL\n\n## 3 出口\n\nS3\n", encoding="utf-8")
                git(self.repo, "add", "-A")
                git(self.repo, "commit", "-q", "-m", fence)
                text, ledger = self.named("[偽](docs/f.md#9-偽) と [入口](docs/f.md#2-入口) のとおりに直す")
                self.assertIn({"kind": "named_section", "what": "docs/f.md#2-入口"}, ledger["given"])
                self.assertNotIn({"kind": "named_section", "what": "docs/f.md#9-偽"}, ledger["given"])
                self.assertIn("docs/f.md#9-偽", [w["what"] for w in ledger["withheld"]])
                self.assertIn("BODY-2-TAIL", text)
                self.assertNotIn("S3", text)

    def test_premise_kinds_fence_is_design_premises(self):
        """test_premise_kinds_fence_is_design_premises: 貼る入力の種類が design.PREMISE_KINDS の外なら、比べの支度が落ちる。
        後半が足す drift・constraint の kind も、控えの kind の許す一覧 KINDS の外なら落ちる"""
        self.intake(answers=dump({"start": {"decision": "continue", "text": "x"}}))
        with self.run.env():
            import design
            steps = kit.load("r2", "steps")
            premises = steps.premises
            with mock.patch.object(design, "PREMISE_KINDS", ("named_section", "repo_map")):
                with self.assertRaises(premises.BoardGap) as raised:
                    steps.compare_prompt(self.place, self.repo)
            self.assertIn("human_answer", str(raised.exception))
            self.intake(changed=dump({"premise_drift": True, "premise_drift_note": "ずれ"}))
            with mock.patch.object(premises, "KINDS", design.PREMISE_KINDS):
                with self.assertRaises(premises.BoardGap) as raised:
                    steps.compare_prompt(self.place, self.repo)
            self.assertIn("drift", str(raised.exception))

    def test_says_what_was_not_passed(self):
        """依頼が無い・修正の印が無い・制約が無い時の言い方（元 test_says_what_was_not_passed の残り）"""
        self.intake()
        text = self.compare()["prompt"]
        self.assertIn("（修正の印が渡っていない）", text)
        self.assertIn("### Recorded constraints\n\n（無い）", text)
        self.intake(changed=dump({"premise_drift": False}))
        self.assertIn("### Drift of premises (declared during the fix)\n\n（無い）", self.compare()["prompt"])
        self.intake(changed=dump({"premise_drift": True}))
        self.assertIn("（申告の文なし）", self.compare()["prompt"])

    def test_constraints_come_as_an_object_and_read_the_same_in_both_roles(self):
        """test_constraints_read_the_same_in_the_compare_head_and_the_premise_check（E43）: object の形で来ても同じ行。
        検算の役の md にも同じ行が載る"""
        cons = [{"kind": "実測", "text": "1 デプロイは 2 リポジトリ", "measured_how": "grep"},
                {"kind": "仮説", "text": "入口は 1 つ", "measured_how": "読んだ"}]
        want = "- （実測）1 デプロイは 2 リポジトリ\n- （仮説）入口は 1 つ"
        for form in (cons, {"constraints": cons}):
            with self.subTest(type(form).__name__):
                self.intake(constraints=dump(form))
                self.assertIn(want, self.compare()["prompt"])
        self.intake(design=dump(NOT_STANDS), constraints=dump({"constraints": cons}))
        self.assertIn(want, self.premise())


class OriginSectionCase(_RepoCase):
    """元 OriginSectionCase のうち、PR の根の 1 本以外を block の筋で（head と base_label の port で起点を替える）"""

    def test_origin_at_head_has_no_pr_diff(self):
        (self.repo / "a.txt").write_text("fix\n", encoding="utf-8")
        self.intake()
        text = self.compare()["prompt"]
        self.assertIn(f"起点は修正前の HEAD `{self.base[:12]}`", text)
        self.assertIn("PR の差分は無い", text)
        self.assertIn("直しの差分（修正前の HEAD → 作業ツリー）で変わったファイル: a.txt", text)
        self.assertNotIn("打ち消し", text)

    @unittest.skipIf(os.geteuid() == 0, "root はモードを無視してファイルを読める")
    def test_unreadable_work_tree_is_said_not_raised(self):
        secret = self.repo / "secret"
        secret.write_text("s\n", encoding="utf-8")
        secret.chmod(0)
        self.addCleanup(secret.chmod, 0o644)
        self.intake()
        self.assertIn("累積差分の起点を測れない", self.compare()["prompt"])


class PremiseRoadCase(_RepoCase):
    def test_premise_road_runs_only_the_check_and_carries_the_facts(self):
        """test_premise_facts_reach_the_report（E37）: 偽と示せた仮定の key と実測 facts が、出力の premise_check と報告に載る"""
        self.assertEqual(self.intake(design=dump(NOT_STANDS)), {"compare": False, "premise": True, "reason": ""})
        self.assertIn("R2 returned premise-invalid", self.premise())
        self.assertIn("この run の直しの差分", self.premise())
        self.assertFalse(list(self.place.glob("r2-compare-prompt-*.md")))
        self.save("premise-check", CHECK)
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))
        self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": "前提不成立: 上限が既に在る"})
        self.assertEqual(done["premise_check"], {"verdict": "resolved", "reason": "上限は在る", "key": "上限を呼び手ごとに持つか",
                                                 "resolution": "config.py:3 に上限 10", "facts": ["上限は config.py:3 の 10"]})
        report = done["report"]
        self.assertIn("前提の検算: resolved（上限は在る）", report)
        self.assertIn("  - 次の run の制約に足す実測: 上限は config.py:3 の 10", report)
        self.assertTrue(any("保留（held）のまま残す" in line for line in report))
        self.assertTrue(any("独立の設計と差分を比べる役に渡した入力の控えが無い（compare）" in n for n in done["notes"]))

    def test_premise_reason_falls_back_to_the_reason(self):
        """test_premise_reason_prefers_the_named_field_then_the_reason: premise_invalid_reason が無ければ reason を判定の行に"""
        design = {k: v for k, v in NOT_STANDS.items() if k != "premise_invalid_reason"}
        self.intake(design=dump(design))
        self.premise()
        self.save("premise-check", CHECK)
        self.assertEqual(self.finish()["verdict"], {"status": "unverifiable", "reason": "前提不成立: 既に入っている"})

    def test_escalate_carries_no_facts(self):
        self.intake(design=dump(NOT_STANDS))
        self.premise()
        self.save("premise-check", {**CHECK, "verdict": "escalate", "assumption_false": False})
        done = self.finish()
        self.assertEqual(done["premise_check"], {"verdict": "escalate", "reason": "上限は在る", "key": "", "resolution": "", "facts": []})
        self.assertEqual(done["status"], "ran")

    def test_fallen_check_escalates(self):
        """test_fallen_premise_check_escalates（E35）: 返答が無ければ escalate と落ちた訳。status は failed、報告は役の出力が無いと言う"""
        self.intake(design=dump(NOT_STANDS))
        self.premise()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["premise_check"]["verdict"], "escalate")
        self.assertIn("R2 の筋が落ちた", done["premise_check"]["reason"])
        self.assertEqual(done["verdict"]["reason"], "前提不成立: 上限が既に在る")
        self.assertIn("  - 前提の検算の役の出力が無い: 偽と分かった仮定と次の run の制約に足す実測は読んでいない", done["report"])

    def test_off_contract_verdict_escalates(self):
        self.intake(design=dump(NOT_STANDS))
        self.premise()
        self.save("premise-check", {**CHECK, "verdict": "maybe"})
        done = self.finish()
        self.assertEqual(done["premise_check"]["verdict"], "escalate")
        self.assertIn("出力の判定の語が約束の外", done["premise_check"]["reason"])
        self.assertEqual(done["status"], "failed")
        self.assertFalse(any("役の出力が無い" in line for line in done["report"]))

    def test_premise_road_runs_without_a_purpose(self):
        """目的の文が空でも検算は回る（今のまま）"""
        self.assertEqual(self.intake(design=dump(NOT_STANDS), purpose="")["premise"], True)


class SkippedRoadCase(_RepoCase):
    def test_missing_design_skips_both_roles(self):
        """test_missing_design_makes_r2_unverifiable（E52）。訳は port design_reason"""
        self.assertEqual(self.intake(design="null", design_reason="独立設計の block が落ちた"), {"compare": False, "premise": False, "reason": ""})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["reason"]), (True, "skipped", ""))
        self.assertEqual(done["verdict"], {"status": "unverifiable", "reason": "独立設計が取れなかった: 独立設計の block が落ちた"})
        self.assertIsNone(done["premise_check"])
        self.assertFalse(list(self.place.glob("*-prompt-*.md")))

    def test_design_in_three_forms(self):
        """design を pointer・パス・値の 3 通りで受ける"""
        (self.place / "design.json").write_text(dump(STANDS), encoding="utf-8")
        for form in (dump(STANDS), str(self.place / "design.json"), self.run.pointer("design.json")):
            with self.subTest(form[:20]):
                self.assertEqual(self.intake(design=form)["compare"], True)

    def test_no_design_at_all_names_the_default_reason(self):
        self.run.script("intake", base=self.base, purpose="x")
        done = self.finish()
        self.assertEqual(done["verdict"]["reason"], "独立設計が取れなかった: 独立設計の出力が渡っていない")

    def test_empty_purpose_is_not_compared(self):
        """test_r2_not_compared_names_which_input_was_missing（E53）"""
        self.assertEqual(self.intake(purpose="")["compare"], False)
        done = self.finish()
        self.assertEqual((done["status"], done["verdict"]["reason"]), ("skipped", "独立設計と比べなかった: 目的の文が空"))

    def test_design_without_the_stands_field_is_not_compared(self):
        self.intake(design=dump({"reason": "x"}))
        done = self.finish()
        self.assertEqual(done["verdict"]["reason"], "独立設計と比べなかった: 独立設計の返答に問いが立つかの欄（question_stands）が無い")
        self.assertEqual(done["status"], "skipped")


    def test_a_design_with_a_missing_field_is_not_due(self):
        """design の値が missing の欄を持つ時は、問いが立つ・立たないと言っていても役を起こさない（形の照らしは余分な欄を通す）"""
        for stands in (True, False):
            with self.subTest(stands):
                out = self.intake(design=dump({**STANDS, "question_stands": stands, "missing": "x"}))
                self.assertEqual((out["compare"], out["premise"]), (False, False))


class FailureCase(_RepoCase):
    def test_unreadable_port_fails_with_its_name(self):
        out = self.intake(design='{"question_stands": "yes"}')
        self.assertEqual((out["compare"], out["premise"]), (False, False))
        self.assertIn("入力 design:", out["reason"])
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertIn("入力が読めない: 入力 design:", done["verdict"]["reason"])
        self.assertEqual((done["premise_check"], done["notes"], done["questions"]), (None, [], []))

    def test_unwritable_notes_say_so_in_one_line(self):
        """premise-inputs.json が書けなくても出口は落ちず、notes は控えが無いの 1 行"""
        self.intake()
        self.compare()
        self.save("r2-compare", PASS)
        (self.place / "premise-inputs.json").mkdir()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (True, "ran"))
        self.assertEqual(done["notes"], ["独立の設計と比べる目に渡した入力の控えが無い（R2）"])

    def test_finish_without_intake_fails_softly(self):
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(done["verdict"]["status"], "unverifiable")

    def test_prep_for_the_other_road_refuses(self):
        self.intake()
        self.assertIn("premise", self.run.failing("premise_prep"))


if __name__ == "__main__":
    unittest.main()
