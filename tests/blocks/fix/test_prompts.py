"""修正の block（workflows/fix/）の 9 つの AI の node の指示を、その prep（か prep が呼ぶ src/prompts.py の口）を回して md から組み、
決まった文が入ることを見る（docs/design/fix.md の 14.2 の test_prompts.py）。

表 RENDERED は、筋書き（fixtures/）で届かない 8 つの node（全体の形は fan_out で dry-run が落ち、tdd-new と tdd は振り分けで tdd の単位が在る組だけ〔tdd は同じ単位の 2 周目〕、suite-fix は起動スクリプトが壊れた組だけ）の
md の決まった文。tests/layers/test_block_shape.py の 7.1 の 3 の照らしは、この表の在りと字だけを見る（14.3）。表の行は下の試験が
本当に組んだ指示の中に在ることを照らす。
"""
import json
import pathlib
import sys
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[3]
BLOCK = kit.BLOCKS / "fix"
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import conflict  # noqa: E402

RENDERED = {
    "ruler": "# Ruling on conflicts (a read-only role)",
    "clash-fix": "# Merging groups (the merger)",
    "clash-ruled": "# Merging groups (the merger after a ruling)",
    "fix-ruled": "# Fixing (the writer's job)",
    "ruled-consult-answer": "# Scope consultation (from the fixing stage)",
    "tdd": "## What this role does",
    "tdd-new": "## What this role does",   # tdd の単位の在る組の 1 周目だけ（振り分けの役 route が筋書きで回る）
    "suite-fix": "## What to look for",   # 起動スクリプトが壊れた組だけ（試験は tests/blocks/fix/test_suite_fix.py が組んで照らす）
}
KEY = "stats.py:4 mean"
JUDGMENT = json.dumps({"units": [{"key": KEY, "label": "block", "reason": "空の並びで 0 除算する"}], "questions": []})
GROUP = json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": []})
RUNNER = BLOCK / "fixtures" / "tdd-runner.py"
REPLY = {"changes": [], "not_done": [], "fix_closure": {"status": "not_applicable"}, "mechanism_changed": False,
         "premise_drift": False, "gates_changed": False, "seams_changed": False, "security_surface_changed": False,
         "path_changed": False, "interactions": [], "wrote_refs": [], "plan_faces": []}
PLAN = json.dumps({"round": 1, "fields": [{"route": "direct", "tests": [], "rewrite_tests": [], "refactor": "",
                                            "allowed_paths": ["stats.py"], "out_of_scope": []}]})
FIX_PLAN = json.dumps({"plan": [{"unit_keys": [KEY], "approach": "空の並びを先に返す"}]})


def seeded(case) -> kit.Run:
    run = kit.Run(case, "fix")
    (run.repo / "stats.py").write_text("def mean(xs):\n    return sum(xs) / len(xs)\n", encoding="utf-8")
    git(run.repo, "add", ".")
    git(run.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
    return run


# brief ファイルの読み方の句（背景は参照・書き換えてよい範囲が引けない・範囲を決めていない項目）。brief を読む AI の指示に共通の断片 brief-reading で入る
BRIEF_READING = ("the brief wins", "could not be looked up", "did not decide a scope")


class RenderedCase(unittest.TestCase):
    """表 RENDERED の node の指示を組み、表の字が入る"""

    def assert_rendered(self, node: str, text: str):
        self.assertIn(RENDERED[node], text)

    def test_ruler(self):
        run = seeded(self)
        run.script("intake", mode="whole", judgment=JUDGMENT, parallel="false")
        run.script("prep")
        place = run.artifacts
        conflict.park(place, [{"unit_key": KEY, "between": ["stats.py:2", "stats.py:1"], "why_both_cannot_hold": "期待と実装が両立しない",
                               "which_is_right": "unknown", "kind": "needs_context"}], source=conflict.FIX_SOURCE)
        out = run.script("rule_prep")
        self.assert_rendered("ruler", out["prompt"])
        self.assertIn("There is no policy document.", out["prompt"])
        self.assertTrue((place / "ruler-prompt-1.md").is_file())

    def test_clash_fix_and_ruled(self):
        run = seeded(self)
        run.script("intake", mode="whole", judgment=JUDGMENT)
        prompts = kit.load("fix", "prompts")
        with run.env():
            first = prompts.clash(run.artifacts, "first", "clash-accept-g1", "/b/clash-brief-g1.json", "/b/join/g1.diff")
            ruled = prompts.clash(run.artifacts, "ruled", "clash-ruled-accept-g1", "/b/clash-brief-g1.json", "/b/join/g1.diff")
        self.assert_rendered("clash-fix", first["prompt"])
        self.assertNotIn(RENDERED["clash-ruled"], first["prompt"])
        self.assert_rendered("clash-ruled", ruled["prompt"])
        self.assertIn("/b/join/g1.diff", ruled["prompt"])

    def test_fix_ruled_first_round_names_the_rulings_and_the_saved_reply(self):
        run = seeded(self)
        run.script("intake", mode="whole", judgment=JUDGMENT, parallel="false")
        run.script("prep")
        place = run.artifacts
        ids = conflict.park(place, [{"unit_key": KEY, "between": ["stats.py:2", "stats.py:1"],
                                     "why_both_cannot_hold": "期待と実装が両立しない", "which_is_right": "code",
                                     "kind": "not_red"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(place, {ids[0]: {"decision": "fix_code_as", "text": "分母が 0 の時は 0 を返すように直す", "limits": []}},
                               by="role:rule")
        out = run.script("fix_ruled_prep")
        self.assertTrue(out["go"], out)
        self.assert_rendered("fix-ruled", out["prompt"])
        self.assertIn(str(place / conflict.RULINGS_FILE), out["prompt"])
        again = run.script("fix_ruled_prep")
        self.assertNotIn(str(place / conflict.RULINGS_FILE), again["prompt"].split("# Fixing")[0])   # 裁定の文の段落は 1 周目だけ

    def test_ruled_consult_answer(self):
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN)
        prompts = kit.load("fix", "prompts")
        asked = [{"n": 1, "item": 1, "paths": ["README.md"], "tests": [], "new_tests": [], "why": "直しの記録を足す要がある",
                  "out_of_scope": []}]
        table = {1: {"item": 1, "unit_keys": [KEY], "allowed_paths": ["stats.py"], "out_of_scope": []}}
        with run.env():
            text = prompts.consult_render(run.artifacts, "ruled", plan_file="/p/fix-plan-reply.json", ripple_file="")(table, asked)
        self.assert_rendered("ruled-consult-answer", text)
        self.assertTrue((run.artifacts / "ruled-consult-answer-prompt-1.md").is_file())

    def test_tdd_same_unit_round_uses_the_continuing_role(self):
        """同じ単位の 2 回目の支度は tdd（会話を継ぐ役）の指示を組む。1 回目は tdd-new"""
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        self.assertTrue(run.script("group_start")["tdd"])
        self.assertEqual(run.script("route_go"), {"route": True, "stop": False})
        self.assertTrue(run.script("route_prep")["go"])
        self.assertTrue((run.artifacts / "route-prompt-1.md").is_file())
        routed = run.script("route_step", reply=json.dumps({"phase": "route", "units": [{"unit_key": KEY, "route": "tdd"}]}))
        self.assertTrue(routed["done"], routed)
        self.assertTrue(run.script("orders")["tdd"])
        first = run.script("tdd_prep")
        second = run.script("tdd_prep")
        self.assertEqual((first["go"], first["new_unit"], second["go"], second["new_unit"]), (True, True, True, False))
        self.assertTrue((run.artifacts / "tdd-new-prompt-1.md").is_file())
        self.assertTrue((run.artifacts / "tdd-prompt-1.md").is_file())
        self.assert_rendered("tdd-new", first["prompt"])
        self.assert_rendered("tdd", second["prompt"])


class FixerParagraphsCase(unittest.TestCase):
    """修正役の続きの周は決まりの段落が入らず、TDD の役は段ごとに 1 つの段の段落だけが入る"""

    def test_consult_resume_round_has_no_rules(self):
        run = seeded(self)
        inp = {"mode": "group", "group": json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}), "judgment": JUDGMENT,
               "plan": PLAN, "fix_plan": FIX_PLAN, "tdd_suite": str(RUNNER)}
        run.script("intake", **inp)
        run.script("group_start")
        first = run.script("fix_prep")
        self.assertIn("# Fixing (the writer's job)", first["prompt"])
        self.assertIn("## Scope consultation and the pre-check", first["prompt"])
        self.assertIn("If the write to ", first["prompt"])   # 下書きの置き場が拒まれた時の逃げ道（temporary directory）
        self.assertIn("pass that path to `--reply`", first["prompt"])
        reply = {**REPLY, "consult": [{"item": 1, "paths": ["README.md"], "tests": [], "why": "直しに伴う記録を README に足す要がある",
                                       "tried": ["stats.py の分母を直した"], "blocked": "直しは済んだが記録の置き場が範囲の外",
                                       "evidence": [{"path": "stats.py", "line": 4}]}]}
        asked = run.script("consult_check", reply=json.dumps(reply), **{"pass": "first"})
        self.assertTrue(asked["go"], asked)
        self.assertIn("Answer as the author of the fix plan.", asked["prompt"])
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["README.md"], "tests": [], "spec": "",
                               "reason": "直しの記録は範囲に入れてよい"}]}
        run.script("consult_accept", answer=json.dumps(answer), **{"pass": "first"})
        resumed = run.script("fix_prep")
        self.assertEqual(resumed["iteration"], first["iteration"])
        self.assertIn("# The answer to your scope consultation (continued)", resumed["prompt"])
        self.assertNotIn("# Fixing (the writer's job)", resumed["prompt"])
        self.assertNotIn("## Scope consultation and the pre-check", resumed["prompt"])
        self.assertIn("## How to fix", resumed["prompt"])   # 共通の断片の直し方は続きの周にも入る（13.2 の 1）

    def test_tdd_prompt_names_the_policy_the_port_gives(self):
        """TDD の役の指示が名指す方針の文書は port policy の値（line が固めて渡す写し）。run の途中で書き換えた生の文書の名は載らない"""
        run = seeded(self)
        copy = run.repo.parent / "policy-copy.md"
        raw = run.repo.parent / "policy-raw.md"
        copy.write_text("方針\n", encoding="utf-8")
        raw.write_text("書き換えた方針\n", encoding="utf-8")
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER), policy=str(copy))
        run.script("group_start")
        run.script("route_go")   # 1 周目は振り分けの段（組の子の loop route-loop の route-prep）
        text = run.script("route_prep")["prompt"]
        self.assertIn(str(copy), text)
        self.assertNotIn(str(raw), text)

    def test_tests_section_is_always_there_and_the_scope_section_needs_a_fix_plan(self):
        """テストの節（変えてよい既存のテストと、それ以外の本体を変えると拒む文）は修正案の有無によらず入る。範囲の節は修正案が在る時だけ"""
        bare = seeded(self)
        bare.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        bare.script("group_start")
        text = bare.script("fix_prep")["prompt"]
        self.assertIn("## Tests you may add or change, and frozen tests", text)
        self.assertIn("- Changing or removing the body of any other existing test function is rejected.", text)
        self.assertNotIn("## Paths you may change and what you must not touch", text)
        planned = seeded(self)
        planned.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}),
                       judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        planned.script("group_start")
        text = planned.script("fix_prep")["prompt"]
        self.assertIn("## Paths you may change and what you must not touch", text)
        self.assertIn("## Tests you may add or change, and frozen tests", text)

    def test_tests_broken_before_the_fix_are_named_as_fixable_along_the_way(self):
        """#836: 関わる試験で直す前から壊れていた物（置き場の conflict.BROKEN_TESTS_FILE。TDD の輪の頭が書く）は、テストの節に別の行で
        名指され、ついでに直してよいと書かれる。無い run には出ない"""
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        self.assertNotIn("直す前から壊れていた関わる試験", run.script("fix_prep")["prompt"])
        (run.artifacts / conflict.BROKEN_TESTS_FILE).write_text(
            json.dumps({"tests": [{"path": "test_stats.py", "ids": ["test_stats.TestStats::test_mean"]}]}), encoding="utf-8")
        for name in list(run.artifacts.glob("fixer-prompt-*.md")) + list(run.artifacts.glob("fix-first*.json")):
            name.unlink()
        text = run.script("fix_prep")["prompt"]
        self.assertIn("- 直す前から壊れていた関わる試験（ついでに直してよい。最後の承認ノードに出る）: `test_stats.py`", text)
        self.assertIn("You may fix them along with your fix", text)

    def test_the_first_prompt_names_the_borrowed_reading_file_and_the_resumed_one_the_first_prompt(self):
        """下請けを起こす時に Read させる読み替えのファイルを 1 回目の指示が名指し、続きの周は読み落とした時の逃げ道として 1 回目の
        指示のファイルを名指す"""
        run = seeded(self)
        run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}),
                   judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        run.script("group_start")
        first = run.script("fix_prep")
        self.assertRegex(first["prompt"], r"write in its prompt to Read this file: \S+unattended\.md")
        reply = {**REPLY, "consult": [{"item": 1, "paths": ["README.md"], "tests": [], "why": "直しに伴う記録を README に足す要がある",
                                       "tried": ["stats.py の分母を直した"], "blocked": "直しは済んだが記録の置き場が範囲の外",
                                       "evidence": [{"path": "stats.py", "line": 4}]}]}
        run.script("consult_check", reply=json.dumps(reply), **{"pass": "first"})
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["README.md"], "tests": [], "spec": "",
                               "reason": "直しの記録は範囲に入れてよい"}]}
        run.script("consult_accept", answer=json.dumps(answer), **{"pass": "first"})
        resumed = run.script("fix_prep")["prompt"]
        self.assertRegex(resumed, r"Read \S+fixer-prompt-1\.md again")

    def test_language_line_keeps_code_identifiers_and_error_messages(self):
        for name in ("parts/fixer.md", "parts/tdd.md", "parts/clash.md", "ruler.md"):
            with self.subTest(name=name):
                text = (BLOCK / "prompts" / name).read_text(encoding="utf-8")
                self.assertIn("Keep keys, enum values, code identifiers, paths, commands, and error messages as they are "
                              "(keys are matched across rounds, so do not translate them).", text)
        fixer = (BLOCK / "prompts" / "parts" / "fixer.md").read_text(encoding="utf-8")
        for field in ("`coverage.remaining`", "`precedent.problem`", "`precedent.searched`"):
            self.assertIn(field, fixer.rsplit("Write the human-facing fields", 1)[1])

    def test_tdd_route_phase_has_only_its_phase(self):
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        run.script("route_go")   # 1 周目は振り分けの段（組の子の loop route-loop の route-prep）
        text = run.script("route_prep")["prompt"]
        self.assertIn("# The TDD loop prompt (round 1, phase route)", text)
        self.assertIn("## Units you owe a fix", text)
        self.assertNotIn("## The current unit", text)
        self.assertIn("- **route**", text)
        for other in ("- **test**", "- **fix**", "- **refactor**"):
            self.assertNotIn(other, text)


class ConflictWordsCase(unittest.TestCase):
    """食い違いの申し出の種類と裁定の範囲の決まりの文が、組んだ指示に在る（keep-essence の 8。元 lib/tests/test_conflict_kinds.py の
    test_rules_name_the_kinds・test_brief_rules_name_the_kinds・test_ruler_says_limits_only_add_paths・test_ruler_opens_brief_for_limits_too・
    test_brief_rule_names_ruling_limits と test_conflict_replan_words.py の test_ruler_says_same_run）"""

    def planned_fixer(self) -> str:
        run = seeded(self)
        run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}), judgment=JUDGMENT,
                   plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        run.script("group_start")
        return run.script("fix_prep")["prompt"]

    def ruler(self) -> str:
        run = seeded(self)
        run.script("intake", mode="whole", judgment=JUDGMENT, parallel="false")
        run.script("prep")
        conflict.park(run.artifacts, [{"unit_key": KEY, "between": ["stats.py:2", "stats.py:1"], "why_both_cannot_hold": "期待と実装が両立しない",
                                       "which_is_right": "unknown", "kind": "needs_context"}], source=conflict.FIX_SOURCE)
        return run.script("rule_prep")["prompt"]

    def test_rules_name_the_kinds(self):
        """共通の断片 writer-rules の食い違いの決まりと TDD の役の指示が、DIV_KINDS の語を全部 `語` で言う"""
        text = self.planned_fixer()
        for kind in conflict.DIV_KINDS:
            self.assertIn(f"`{kind}`", text)
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        run.script("route_go")   # 1 周目は振り分けの段（組の子の loop route-loop の route-prep）
        tdd = run.script("route_prep")["prompt"]
        for kind in conflict.DIV_KINDS:
            self.assertIn(f"`{kind}`", tdd)
        self.assertIn('"kind"', tdd)

    def test_brief_rules_name_the_kinds(self):
        """brief の決まりの申し出の道（範囲の外・query・brief の誤り）がそれぞれ種類の名を言う"""
        text = self.planned_fixer()
        for kind in ("scope_needed", "query_hits_fixed", "brief_vs_judgment"):
            self.assertIn(f"`kind` is `{kind}`", text)

    def test_brief_rule_names_ruling_limits(self):
        self.assertIn("the ruling wins over the brief within the ruling's scope", self.planned_fixer())

    def test_ruler_says_limits_only_add_paths(self):
        """裁定役の決まりは、足しても項目は変わらず、項目の `tests`・`files`（足す物・消す物の行）を直しで満たす義務は残ると言う"""
        text = self.ruler()
        for word in ("if empty, no path is added", "a new file outside the scope", "`out_of_scope`", "`tests` and `files`"):
            self.assertIn(word, text)

    def test_ruler_opens_brief_for_limits_too(self):
        """範囲（limits）を書く時も fix_plan_item を考える時も、その単位の brief を開く"""
        self.assertIn("When you write `limits` and when you consider `fix_plan_item`, open that unit's brief", self.ruler())

    def test_ruler_says_same_run(self):
        self.assertIn("within the same run, the fix plan's side fixes that item", self.ruler())


class SubAgentFilesCase(unittest.TestCase):
    """下請けのファイル（g1-impl-<n>.md・g1-review-<n>.md）は prompts/parts/ の md から組まれ、place に書かれる"""

    def test_g1_files(self):
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        out = run.script("fix_prep")
        self.assertIn("## Running subagents", out["prompt"])
        impl = (run.artifacts / "g1-impl-1.md").read_text(encoding="utf-8")
        review = (run.artifacts / "g1-review-1.md").read_text(encoding="utf-8")
        self.assertIn("## works rules", impl)
        self.assertIn("**Do not put the target's names in queries.**", impl)
        self.assertNotIn("If you start a sub-agent", impl)   # spawns は偽
        self.assertIn("## works rules", review)
        self.assertIn(str(run.artifacts / "g1-impl-1.md"), out["prompt"])
        for name, text in (("g1-impl", impl), ("g1-review", review), ("fixer", out["prompt"])):
            for phrase in BRIEF_READING:
                self.assertIn(phrase, text, f"{name} に brief の読み方の句が無い")


if __name__ == "__main__":
    unittest.main()
