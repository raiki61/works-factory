"""独立設計の block を、script を子のプロセスで回して確かめる（docs/design/independent-design.md の 12 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（根の AGENTS.md・設計書 1 本・pr_commit.py を commit した物）で、
port の値だけを渡し、intake → design_prep → 台本の返答 → design_accept → finish と回す。受け付けと印は script と src の関数を
この過程で呼んで確かめる。YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
keep-essence の 9（独立設計と R1〜R4）の守りは test_inputs_carry_no_plan_judgment_or_diff が縛る。
"""
import json
import pathlib
import unittest
import unittest.mock

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.independent_design import values

BLOCK = kit.BLOCKS / "independent-design"
PORTS = ["purpose", "purpose_source", "purpose_review", "constraints", "answers", "request", "policy", "base", "head", "lang"]
HOOK = "workflows/merge/scripts/pr_commit.py"
FILLER = [f"# 行 {n}" for n in range(1, 73)]
ADDED = ["def hook_env() -> dict:", "    env = copy_of_env()", "    read_gh_first(env)", "    return env"]   # 73〜76 行


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "independent-design")
        repo = self.run.repo
        (repo / "workflows/merge/scripts").mkdir(parents=True)
        (repo / "docs").mkdir()
        (repo / "x").mkdir()
        (repo / "y").mkdir()
        (repo / "AGENTS.md").write_text(values.AGENTS_MD, encoding="utf-8")
        (repo / "docs" / "design.md").write_text(values.DESIGN_DOC, encoding="utf-8")
        (repo / HOOK).write_text("\n".join(FILLER) + "\n", encoding="utf-8")
        (repo / "x" / "util.py").write_text("a = 1\n", encoding="utf-8")
        (repo / "y" / "util.py").write_text("b = 1\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        self.base = git(repo, "rev-parse", "HEAD")
        with (repo / HOOK).open("a", encoding="utf-8") as f:
            f.write("\n".join(ADDED) + "\n")
        (repo / "x" / "util.py").write_text("a = 2\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "head")
        self.steps = kit.load("independent-design", "steps")

    def intake(self, **inputs):
        return self.run.script("intake", **{"purpose": values.PURPOSE, **inputs})

    def prep(self):
        return self.run.script("design_prep")

    def accept(self, reply, **inputs):
        raw = reply if isinstance(reply, str) else dump(reply)
        return self.run.script("design_accept", reply=raw, status_guarded="true", **inputs)

    def finish(self):
        return self.run.script("finish")

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))

    def to_prompt(self, **inputs) -> str:
        got = self.intake(constraints=dump(values.CONSTRAINTS), **inputs)
        self.assertTrue(got["due"], got)
        return self.prep()["prompt"]

    def write(self, name, text) -> str:
        path = self.run.artifacts.parent / name
        path.write_text(text, encoding="utf-8")
        return str(path)


class ShapeCase(unittest.TestCase):
    def test_inputs_carry_no_plan_judgment_or_diff(self):
        """keep-essence の 9: 入力は目的・前提・方針・印の 10 個だけで、修正案・判定・差分を運ぶ port が無い（独立の守りは port の形そのもの）"""
        doc = yaml.safe_load((BLOCK / "works-factory-independent-design.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sorted(doc["inputs"]), sorted(PORTS))

    def test_scripts_read_only_the_declared_inputs(self):
        import re
        read = set()
        for path in (BLOCK / "scripts").glob("*.py"):
            read |= {m.lower() for m in re.findall(r'os\.environ(?:\.get)?\(?\[?"INPUTS_([A-Z_]+)"', path.read_text(encoding="utf-8"))}
        self.assertEqual(read - {"reply", "status_guarded"}, set(PORTS))

    def test_loop_count_is_the_give_up_count(self):
        doc = yaml.safe_load((BLOCK / "works-factory-independent-design.yaml").read_text(encoding="utf-8"))
        loop = next(n for n in doc["nodes"] if n["id"] == "design-loop")["loop_group"]
        self.assertEqual(loop["max_iterations"], kit.load("independent-design", "steps").rolekit.GIVE_UP_AFTER)

    def test_fixtures_match_the_nodes(self):
        doc = yaml.safe_load((BLOCK / "works-factory-independent-design.yaml").read_text(encoding="utf-8"))
        ids = {n["id"] for n in doc["nodes"]} | {n["id"] for n in doc["nodes"][1]["loop_group"]["nodes"]}
        for name in ("standalone", "unusable", "gave-up"):
            with self.subTest(name):
                fx = kit.fixture("independent-design", name)
                self.assertLessEqual(set(fx["fixture"]["reached"]), ids)

    def test_downgrades_are_the_current_row(self):
        rows = json.loads((kit.ROOT / "lib" / "downgrades.json").read_text(encoding="utf-8"))
        self.assertEqual(kit.load("independent-design", "report").DOWNGRADES, [r for r in rows if r["node"] == "r2.design"])


class FlowCase(_RepoCase):
    def test_flow_reaches_the_design_and_the_ledger(self):
        got = self.intake(constraints=dump(values.CONSTRAINTS), answers=dump(values.ANSWERS))
        self.assertEqual(got, {"due": True, "status": "", "reason": ""})
        out = self.prep()
        self.assertEqual(sorted(out), ["prompt", "system"])
        self.assertEqual(self.accept(values.REPLY), {"ok": True, "done": True, "give_up": False, "reason": ""})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["stands"], done["reason"]), (True, "ok", True, ""))
        self.assertEqual(done["report"], [])
        self.assertEqual(self.read(done["design"]["path"]), values.REPLY)
        ledger = self.read(done["premises"]["path"])
        self.assertEqual(ledger["node"], "r2.design")
        kinds = {g["kind"] for g in ledger["given"]}
        self.assertEqual(kinds, {"human_answer", "repo_map"})
        self.assertEqual(ledger["claims"], [])
        self.assertEqual(self.read("finish.json"), done)

    def test_a_port_that_cannot_be_read_stops_the_run_with_the_name(self):
        for name, raw in (("constraints", '{"rows": 1}'), ("answers", self.run.pointer("absent.json")), ("policy", "/no/such/file.md")):
            with self.subTest(name):
                got = self.intake(**{name: raw})
                self.assertEqual((got["due"], got["status"]), (False, "failed"))
                self.assertIn(f"入力 {name}", got["reason"])
                done = self.finish()
                self.assertEqual((done["ok"], done["status"], done["design"], done["premises"]), (False, "failed", None, None))
                self.assertEqual(done["report"], [f"独立設計: {got['reason']}"])

    def test_purpose_is_required(self):
        got = self.intake(purpose="  ")
        self.assertEqual((got["due"], got["status"]), (False, "failed"))
        self.assertIn("入力 purpose", got["reason"])

    def test_intake_clears_only_its_own_files(self):
        self.intake()
        self.prep()
        self.accept({**values.REPLY, "elements": []})
        (self.run.artifacts / "other.json").write_text("{}", encoding="utf-8")
        self.assertTrue((self.run.artifacts / "rejects-r2.design.json").is_file())
        self.intake()
        for name in ("rejects-r2.design.json", "design-prompt-1.md", "design-system-1.md", "design-tree.json"):
            self.assertFalse((self.run.artifacts / name).exists(), name)
        self.assertTrue((self.run.artifacts / "other.json").is_file(), "ほかの物の名のファイルは消さない")

    def test_place_follows_the_include_path(self):
        self.run.script("intake", include="judge__independent-design__intake", purpose=values.PURPOSE)
        self.assertTrue((self.run.artifacts / "judge" / "independent-design" / "intake.json").is_file())
        self.assertFalse((self.run.artifacts / "intake.json").exists())


class PromptCase(_RepoCase):
    def test_prompt_carries_purpose_and_constraints_only(self):
        (self.run.repo / "docs" / "plan.md").write_text("修正案の印 PLAN-XYZ\n", encoding="utf-8")
        text = self.to_prompt()
        self.assertIn(values.PURPOSE, text)
        self.assertIn(values.CONSTRAINTS[0]["text"], text)
        self.assertIn("対象のコマンドの環境は", self.run.repo.joinpath("docs/design.md").read_text(encoding="utf-8"))
        for foreign in ("PLAN-XYZ", "fix_plan", "judgment", "diff.patch"):
            self.assertNotIn(foreign, text)
        self.assertIn("AGENTS.md:1-", text)
        self.assertIn(values.AGENTS_MD.splitlines()[2], text)

    def test_human_answers_and_named_sections_are_pasted(self):
        request = self.write("request.md", "`docs/design.md` 2 節 の通りに直す\n")
        text = self.to_prompt(answers=dump(values.ANSWERS), request=request)
        self.assertIn("continue（一言: 始める（main の確かめの run））", text)
        self.assertIn("フックの環境を試験で縛る。", text)
        self.assertIn("docs/design.md:", text)
        ledger = self.read("design-premises.json")
        self.assertEqual({g["kind"] for g in ledger["given"]}, {"human_answer", "named_section", "repo_map"})
        self.assertEqual(ledger["seen"], {"count": 1, "last_round": 1})

    def test_no_answers_and_no_constraints_are_named_in_the_ledger(self):
        self.intake()
        self.prep()
        withheld = {(w["kind"], w["what"]) for w in self.read("design-premises.json")["withheld"]}
        self.assertEqual(withheld, {("human_answer", "answers"), ("constraint", "constraints")})

    def test_unvetted_narrowing_review_is_pasted_and_does_not_stop_the_role(self):
        review = {"verdict": "狭めている", "reason": "r", "findings": [{"text": "cite の無い行"}]}
        got = self.intake(purpose_review=dump(review))
        self.assertEqual(got, {"due": True, "status": "", "reason": ""})
        text = self.prep()["prompt"]
        self.assertIn(self.steps.STALE_WHY, text)

    def test_vetted_narrowing_review_does_not_start_the_role(self):
        review = {"verdict": "狭めている", "reason": "r", "findings": [{"text": "t", "cite": "a.py:1"}]}
        got = self.intake(purpose_review=dump(review))
        self.assertEqual((got["due"], got["status"]), (False, "unusable"))
        self.assertEqual(got["reason"], "目的の文を監査が『狭めている』と判定した——狭められた目的で独立設計を回さない")

    def test_unknown_purpose_source_does_not_start_the_role(self):
        got = self.intake(purpose_source="目的不明")
        self.assertEqual(got, {"due": False, "status": "unusable", "reason": "目的の出典が取れない（目的不明）——独立設計を回さない"})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["design"], done["premises"], done["stands"]), (True, "unusable", None, None, None))
        self.assertEqual(done["reason"], got["reason"])
        self.assertEqual(done["report"], [f"独立設計: {got['reason']}"])
        self.assertFalse((self.run.artifacts / "design-prompt-1.md").exists())

    def test_other_purpose_source_starts_the_role(self):
        self.assertTrue(self.intake(purpose_source="②計画・タスク記述")["due"])

    def test_unreadable_purpose_review_is_named_and_read_as_no_audit(self):
        got = self.intake(purpose_review=self.run.pointer("absent.json"))
        self.assertTrue(got["due"])
        self.prep()
        rows = [w for w in self.read("design-premises.json")["withheld"] if w["kind"] == "purpose_review"]
        self.assertEqual(len(rows), 1)
        self.assertIn("目的の監査の受けた返答", rows[0]["why"])
        self.assertEqual(self.read("intake.json")["purpose_review"], {})

    def test_unreadable_request_file_is_named(self):
        got = self.intake(request="/no/such/request.md")
        self.assertTrue(got["due"])
        text = self.prep()["prompt"]
        rows = [w for w in self.read("design-premises.json")["withheld"] if w["kind"] == "named_section"]
        self.assertEqual(len(rows), 1)
        self.assertIn("依頼のファイル /no/such/request.md を読めない", rows[0]["why"])
        self.assertNotIn("/no/such/request.md", text)

    def test_policy_is_pasted(self):
        policy = self.write("policy.md", "方針の印 POLICY-QRS: 環境は 1 か所で組む\n")
        text = self.to_prompt(policy=policy)
        self.assertIn("POLICY-QRS", text)
        self.assertNotIn("POLICY-QRS", self.to_prompt())

    def test_policy_body_is_capped(self):
        policy = self.steps.policy
        path = self.run.artifacts.parent / "big.md"
        path.write_text("あ" * (policy.PASTE_CAP // 3 + 100), encoding="utf-8")
        body = self.steps.policy_body(path)
        self.assertLessEqual(len(body.encode("utf-8")), policy.PASTE_CAP)
        self.assertIn(f"［方針の文書は {path.stat().st_size} バイトで、{policy.PASTE_CAP} バイトまでを貼った。続きは {path}］", body)
        path.write_text("短い方針\n", encoding="utf-8")
        self.assertEqual(self.steps.policy_body(path), "短い方針\n")

    def test_earlier_rejects_are_pasted_oldest_first(self):
        self.intake()
        self.prep()
        self.assertFalse(self.accept({**values.REPLY, "elements": []})["done"])
        self.assertFalse(self.accept({**values.REPLY, "elements": []}, )["done"])
        text = self.prep()["prompt"]
        self.assertEqual(text.count("elements に誤りが在る"), 2)
        self.assertTrue((self.run.artifacts / "design-prompt-2.md").is_file())


class AddedMarkCase(_RepoCase):
    def marked(self, constraints, base=None, head=""):
        return self.steps.added_marks(constraints, self.run.repo, self.base if base is None else base, head)

    def test_constraint_naming_an_added_line_is_marked(self):
        got = self.marked([{"text": f"{HOOK}:74 に同じ", "kind": "実測"}, {"text": f"{HOOK} の hook_env（73 行あたり）", "kind": "実測"}])
        self.assertIn(f"足した行: {HOOK}:74）", got[0]["mark"])
        self.assertNotIn("mark", got[1], "パス:行 の形で名指さない文には付けない")

    def test_grep_output_naming_an_added_line_is_marked(self):
        out = f"{HOOK}:73:def hook_env() -> dict:\n"
        got = self.marked([{"text": "hook_env", "measured_output": f"$ grep -n hook_env .\n{out}", "kind": "実測"}])
        self.assertIn(f"{HOOK}:73", got[0]["mark"])
        self.assertTrue(got[0]["mark"].startswith(f"（審査する変更 {self.base[:12]}.."))

    def test_line_the_change_did_not_add_is_not_marked(self):
        self.assertNotIn("mark", self.marked([{"text": f"{HOOK}:10 は前からある"}])[0])

    def test_run_without_a_diff_is_not_marked(self):
        rows = [{"text": f"{HOOK}:74"}]
        self.assertEqual(self.marked(rows, base=""), rows)
        head = git(self.run.repo, "rev-parse", "HEAD")
        self.assertEqual(self.marked(rows, base=head), rows, "起点と先が同じ版なら差分は無い")
        self.assertEqual(self.marked(rows, base="no-such-rev"), rows, "git が引けない起点では付けない")

    def test_tail_two_files_share_is_not_marked(self):
        """末尾の一致が 2 本のファイル（x/util.py と y/util.py）は決められないので、足した行でも印を付けない"""
        self.assertNotIn("mark", self.marked([{"text": "util.py:1 を足した"}])[0])

    def test_marks_flow_through_the_ports(self):
        rows = [{"text": f"{HOOK}:74 が足した行", "measured_how": "sed", "kind": "仮説"}]
        self.intake(constraints=dump(rows), base=self.base, head="HEAD")
        text = self.prep()["prompt"]
        self.assertIn(f"（審査する変更 {self.base[:12]}..", text)
        self.assertIn(f"足した行: {HOOK}:74）", text)


class AcceptCase(_RepoCase):
    def start(self):
        self.intake(constraints=dump(values.CONSTRAINTS))
        self.prep()

    def test_design_accepted(self):
        self.start()
        self.assertEqual(self.accept(values.REPLY), {"ok": True, "done": True, "give_up": False, "reason": ""})
        self.assertEqual(self.read("design.json"), values.REPLY)

    def test_standing_design_needs_elements(self):
        self.start()
        for elements in ([], [{"id": "D1", "adds": ["a"], "removes": []}, {"id": "D1", "adds": ["b"], "removes": []}]):
            got = self.accept({**values.REPLY, "elements": elements})
            self.assertEqual((got["ok"], got["done"]), (False, False))
            self.assertIn("elements に誤りが在る", got["reason"])
        self.assertFalse((self.run.artifacts / "design.json").exists())

    def test_not_standing_design_needs_no_elements_but_real_anchors(self):
        self.start()
        stands_not = {"question_stands": False, "reason": "要らない", "premise_invalid_reason": f"{HOOK}:1-5 が既に満たす", "design": ""}
        self.assertTrue(self.accept(stands_not)["ok"])
        self.assertEqual(self.read("design.json")["question_stands"], False)
        done = self.finish()
        self.assertEqual((done["status"], done["stands"], done["report"]), ("ok", False, []))

    def test_anchor_must_be_in_the_frozen_version(self):
        self.start()
        for why in (f"{HOOK}:9999 が既に満たす", "docs/no-such.md:3 が既に満たす", f"{HOOK}:80-70 が既に満たす"):
            with self.subTest(why):
                got = self.accept({"question_stands": False, "reason": why, "design": ""})
                self.assertFalse(got["ok"])
                self.assertIn("premise_invalid_reason の名指しが固めた版の実物に当たらない", got["reason"])

    def test_unanchored_not_standing_design_is_reported(self):
        self.start()
        self.assertTrue(self.accept({"question_stands": False, "reason": "名指しの無い根拠", "design": ""})["ok"])
        done = self.finish()
        self.assertEqual(done["report"], ["独立設計は問いが立たないと返したが、根拠の実物の名指しなし（名指しの無い根拠）"])

    def test_give_up_on_the_third_reject_still_done(self):
        self.start()
        bad = {**values.REPLY, "elements": []}
        got = [self.accept(bad) for _ in range(3)]
        self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in got], [(False, False, False)] * 2 + [(False, True, True)])
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["design"], done["stands"]), (False, "failed", None, None))
        self.assertTrue(done["reason"].startswith("独立設計が取れなかった: r2.design の返答が 3 回とも受け付けで拒まれた（最後の拒否: "))
        self.assertIn("elements に誤りが在る", done["reason"])
        self.assertEqual(done["premises"]["path"], "design-premises.json")
        self.assertEqual(done["report"], [f"独立設計: {done['reason']}"])

    def test_tree_change_rejected(self):
        self.start()
        (self.run.repo / "AGENTS.md").write_text("役が書き換えた\n", encoding="utf-8")
        got = self.accept(values.REPLY)
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた: ", got["reason"])

    def test_missing_tree_snapshot_rejected(self):
        self.start()
        (self.run.artifacts / "design-tree.json").unlink()
        self.assertIn("役を起こす前の作業ツリーの控え design-tree.json が無い", self.accept(values.REPLY)["reason"])

    def test_unreadable_reply_is_rejected_not_a_crash(self):
        self.start()
        got = self.accept("これは JSON でない")
        self.assertEqual((got["ok"], got["done"]), (False, False))

    def test_claims_pair_an_unpassed_sentence_with_what_was_given(self):
        self.intake(constraints=dump(values.CONSTRAINTS), answers=dump(values.ANSWERS))
        self.prep()
        reply = {**values.REPLY, "reason": "地図は渡されていない。ただ問いは実在する"}
        self.assertTrue(self.accept(reply)["ok"])
        claims = self.read("design-premises.json")["claims"]
        self.assertEqual([(c["kind"], c["claim"]) for c in claims], [("repo_map", "地図は渡されていない")])

    def test_finish_without_a_design_names_why(self):
        self.intake()
        done = self.finish()
        self.assertEqual((done["status"], done["reason"]), ("failed", "独立設計が取れなかった: 役の loop が回らなかった"))


class PremisesCase(_RepoCase):
    def test_kinds_outside_the_allowlist_fall(self):
        premises = kit.load("independent-design", "premises")
        design = premises.design
        view = self.steps.r2_view("", [])
        with unittest.mock.patch.object(design, "repo_map", return_value=("x", [{"kind": "judgment", "what": "w"}], [])):
            with self.assertRaises(premises.BoardGap):
                premises.material(view, self.run.repo)

    def test_a_changed_lib_head_is_an_error_not_a_double_head(self):
        premises = kit.load("independent-design", "premises")
        view = self.steps.r2_view("", values.ANSWERS)
        self.assertTrue(premises.material(view, self.run.repo)["answers"].startswith("- 周 1"))
        changed = ("違う見出し\n\n違う頼み\n\n- 周 1", ["周 1"], [], {"count": 1, "last_round": 1})
        with unittest.mock.patch.object(premises.design, "human_answers", return_value=changed):
            with self.assertRaises(ValueError):
                premises.material(view, self.run.repo)

    def test_map_without_documents_says_so(self):
        git(self.run.repo, "rm", "-q", "AGENTS.md")
        git(self.run.repo, "commit", "-q", "-m", "no map")
        premises = kit.load("independent-design", "premises")
        got = premises.material(self.steps.r2_view("", []), self.run.repo)
        self.assertIn("地図なし", got["map"])


if __name__ == "__main__":
    unittest.main()
