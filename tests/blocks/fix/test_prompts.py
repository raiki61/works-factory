"""修正の block（workflows/fix/）の 9 つの AI の node の指示を、その prep（か prep が呼ぶ src/prompts.py の口）を回して md から組み、
決まった文が入ることを見る（docs/design/fix.md の 14.2 の test_prompts.py）。

表 RENDERED は、筋書き（fixtures/）で届かない 8 つの node（全体の形は fan_out で dry-run が落ち、tdd-new と tdd は振り分けで tdd の単位が在る組だけ〔tdd は同じ単位の 2 周目〕、suite-fix は起動スクリプトが壊れた組だけ）の
md の決まった文。tests/layers/test_block_shape.py の 7.1 の 3 の照らしは、この表の在りと字だけを見る（14.3）。表の行は下の試験が
本当に組んだ指示の中に在ることを照らす。
"""
import functools
import json
import pathlib
import sys
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.fix import support

ROOT = pathlib.Path(__file__).resolve().parents[3]
BLOCK = kit.BLOCKS / "fix"
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import conflict  # noqa: E402

RENDERED = {
    "ruler": "# Ruling on conflicts (a read-only role)",
    "clash-fix": "# Merging groups (the merger)",
    "clash-ruled": "# Merging groups (the merger after a ruling)",
    "consult-answer": "# Scope consultation (from the fixing stage)",   # 筋書き consult は書き手の返りを読めず consult-check を差し替えるので、ここで組んで照らす
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
PLAN = json.dumps({"round": 1, "fields": [{"route": "direct", "tests": [], "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
                                            "allowed_paths": ["stats.py"], "out_of_scope": []}]})
FIX_PLAN = json.dumps({"plan": [{"unit_keys": [KEY], "approach": "空の並びを先に返す"}]})


def prompt_of(run, out: dict) -> str:
    """支度 fix_prep の返り out の周に起こす型の書き手の block が、渡された order・slots から組む指示（その block の writer_prep.py を回す）"""
    return support.writer_prompt(run.environ(), out, run.repo)


def seeded(case) -> kit.Run:
    run = kit.Run(case, "fix")
    (run.repo / "stats.py").write_text("def mean(xs):\n    return sum(xs) / len(xs)\n", encoding="utf-8")
    git(run.repo, "add", ".")
    git(run.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
    return run


# brief ファイルの読み方の句（背景は参照・書き換えてよい範囲が引けない）。brief を読む AI の指示に共通の断片 brief-reading で入る
BRIEF_READING = ("the brief wins", "could not be looked up")


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
        self.assertIn("Each item must let them decide from its own text alone", out["prompt"])   # 共通の断片 plain-ask（人に回す文の決まり）
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
        self.assertEqual(run.script("writer_pick", **{"pass": "ruled"}), {"go": True, "writer": "wr-variant", "done": True})
        out = run.script("fix_ruled_prep")
        self.assertTrue(out["go"], out)
        self.assertEqual(out["writer"], "wr-variant")
        text = prompt_of(run, out)   # 指示は型の block が組む
        self.assertIn("# Fixing (the writer's job)", text)
        self.assertIn(str(place / conflict.RULINGS_FILE), text)
        again = prompt_of(run, run.script("fix_ruled_prep"))
        self.assertNotIn(str(place / conflict.RULINGS_FILE), again.split("# Fixing")[0])   # 裁定の文の段落は 1 周目だけ

    def test_consult_answer(self):
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN)
        prompts = kit.load("fix", "prompts")
        asked = [{"n": 1, "item": 1, "paths": ["README.md"], "tests": [], "new_tests": [], "why": "直しの記録を足す要がある",
                  "out_of_scope": []}]
        table = {1: {"item": 1, "unit_keys": [KEY], "allowed_paths": ["stats.py"], "out_of_scope": []}}
        with run.env():
            text = prompts.consult_render(run.artifacts, "first", plan_file="/p/fix-plan-reply.json", ripple_file="")(table, asked)
        self.assert_rendered("consult-answer", text)
        self.assertIn("Answer as the author of the fix plan.", text)
        self.assertTrue((run.artifacts / "consult-answer-prompt-1.md").is_file())

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

    def test_route_prep_stops_when_group_start_did_not_run(self):
        """組の頭の返り tdd-start.json が無い（group-start が走らなかった）時、route-prep は黙って go: false を返さずに落ちる"""
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        self.assertIn("group-start", run.failing("route_prep"))

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
        first_prompt = prompt_of(run, first)
        self.assertIn("# Fixing (the writer's job)", first_prompt)
        self.assertIn("## Scope consultation and the pre-check", first_prompt)
        self.assertIn("If the write to ", first_prompt)   # 下書きの置き場が拒まれた時の逃げ道（temporary directory）
        self.assertIn("pass that path to `--reply`", first_prompt)
        reply = {**REPLY, "consult": [{"item": 1, "paths": ["README.md"], "tests": [], "why": "直しに伴う記録を README に足す要がある",
                                       "tried": ["stats.py の分母を直した"], "blocked": "直しは済んだが記録の置き場が範囲の外",
                                       "evidence": [{"path": "stats.py", "line": 4}]}]}
        asked = run.script("consult_check", reply_variant=support.reply_json(reply), **{"pass": "first"})
        self.assertTrue(asked["go"], asked)
        self.assertIn("Answer as the author of the fix plan.", asked["prompt"])
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["README.md"], "tests": [], "spec": "",
                               "reason": "直しの記録は範囲に入れてよい"}]}
        run.script("consult_accept", answer=json.dumps(answer), **{"pass": "first"})
        resumed = run.script("fix_prep")
        self.assertEqual(resumed["iteration"], first["iteration"])
        resumed_prompt = prompt_of(run, resumed)
        self.assertIn("# The answer to your scope consultation (continued)", resumed_prompt)
        self.assertNotIn("# Fixing (the writer's job)", resumed_prompt)
        self.assertNotIn("## Scope consultation and the pre-check", resumed_prompt)
        self.assertIn("## How to fix", resumed_prompt)   # 共通の断片の直し方は続きの周にも入る（13.2 の 1）

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
        text = prompt_of(bare, bare.script("fix_prep"))
        self.assertIn("## Tests you may add or change, and frozen tests", text)
        self.assertIn("- Changing or removing the body of any other existing test function is rejected.", text)
        self.assertNotIn("## Paths you may change and what you must not touch", text)
        planned = seeded(self)
        planned.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}),
                       judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        planned.script("group_start")
        text = prompt_of(planned, planned.script("fix_prep"))
        self.assertIn("## Paths you may change and what you must not touch", text)
        self.assertIn("## Tests you may add or change, and frozen tests", text)

    def test_tests_broken_before_the_fix_are_named_as_fixable_along_the_way(self):
        """#836: 関わる試験で直す前から壊れていた物（置き場の conflict.BROKEN_TESTS_FILE。TDD の輪の頭が書く）は、テストの節に別の行で
        名指され、ついでに直してよいと書かれる。無い run には出ない"""
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        self.assertNotIn("直す前から壊れていた関わる試験", prompt_of(run, run.script("fix_prep")))
        (run.artifacts / conflict.BROKEN_TESTS_FILE).write_text(
            json.dumps({"tests": [{"path": "test_stats.py", "ids": ["test_stats.TestStats::test_mean"]}]}), encoding="utf-8")
        text = prompt_of(run, run.script("fix_prep"))
        self.assertIn("- 直す前から壊れていた関わる試験（ついでに直してよい。最後の承認ノードに出る）: `test_stats.py`", text)
        self.assertIn("You may fix them along with your fix", text)

    def test_the_first_prompt_names_the_borrowed_reading_file_and_the_resumed_one_the_first_prompt(self):
        """下請けを起こす時に Read させる読み替えのファイルを 1 回目の指示が名指し、続きの周は読み落とした時の逃げ道として 1 回目の
        指示のファイルを名指す"""
        run = seeded(self)
        run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}),
                   judgment=JUDGMENT, plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        run.script("group_start")
        first = prompt_of(run, run.script("fix_prep"))
        self.assertRegex(first, r"write in its prompt to Read this file: \S+unattended\.md")
        reply = {**REPLY, "consult": [{"item": 1, "paths": ["README.md"], "tests": [], "why": "直しに伴う記録を README に足す要がある",
                                       "tried": ["stats.py の分母を直した"], "blocked": "直しは済んだが記録の置き場が範囲の外",
                                       "evidence": [{"path": "stats.py", "line": 4}]}]}
        run.script("consult_check", reply_variant=support.reply_json(reply), **{"pass": "first"})
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["README.md"], "tests": [], "spec": "",
                               "reason": "直しの記録は範囲に入れてよい"}]}
        run.script("consult_accept", answer=json.dumps(answer), **{"pass": "first"})
        resumed = prompt_of(run, run.script("fix_prep"))
        self.assertRegex(resumed, r"Read \S+variant-prompt-1\.md again")

    def test_language_line_keeps_code_identifiers_and_error_messages(self):
        for name in ("writer.md", "parts/tdd.md", "parts/clash.md", "ruler.md"):
            with self.subTest(name=name):
                text = ((kit.SHARED / "prompts" / name if name == "writer.md" else BLOCK / "prompts" / name)   # writer は pack の共通（段 2 の D1）
                        .read_text(encoding="utf-8"))
                self.assertIn("Keep keys, enum values, code identifiers, paths, commands, and error messages as they are "
                              "(keys are matched across rounds, so do not translate them).", text)
        fixer = (kit.SHARED / "prompts" / "writer.md").read_text(encoding="utf-8")
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
        return prompt_of(run, run.script("fix_prep"))

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

    def test_ruler_names_the_rulings_red_at_base_allows(self):
        """種類 red_at_base の申し出に許す裁定は、受け付けの表 conflict.RED_AT_BASE_DECISIONS の物を全部、その段落で言う"""
        para = next(p for p in self.ruler().split("\n\n") if "`red_at_base`" in p)
        for decision in conflict.RED_AT_BASE_DECISIONS:
            self.assertIn(f"`{decision}`", para)

    def test_ruler_says_same_run(self):
        self.assertIn("within the same run, the fix plan's side fixes that item", self.ruler())


class SubAgentFilesCase(unittest.TestCase):
    """下請けのファイル（g1-impl-<n>.md・g1-review-<n>.md）は、修正の block の fix-prep が slots の subagents に渡した材料から、型の block（variant）が
    .shared/prompts の md で組み、型の block の place に書く（値の関数は lib/tests/test_subagents.py、ファイルを書く本体の事は
    tests/blocks/shared/test_writerblock.py。ここは fix-prep → 型の block の通し）"""

    def test_g1_files(self):
        run = seeded(self)
        run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, tdd_suite=str(RUNNER))
        run.script("group_start")
        out = run.script("fix_prep")
        self.assertEqual(out["writer"], "w-variant")
        text = prompt_of(run, out)
        place = run.artifacts / out["writer"]   # 型の block の place
        self.assertIn("## Running subagents", text)
        impl = (place / "g1-impl-1.md").read_text(encoding="utf-8")
        review = (place / "g1-review-1.md").read_text(encoding="utf-8")
        self.assertIn("## works rules", impl)
        self.assertIn("**Do not put the target's names in queries.**", impl)
        self.assertNotIn("If you start a sub-agent", impl)   # spawns は偽
        self.assertIn("## works rules", review)
        self.assertIn(str(place / "g1-impl-1.md"), text)
        self.assertFalse(list(run.artifacts.glob("g1-*")), "下請けのファイルは修正の block の place に置かない")
        for name, body in (("g1-impl", impl), ("g1-review", review), ("fixer", text)):
            for phrase in BRIEF_READING:
                self.assertIn(phrase, body, f"{name} に brief の読み方の句が無い")


SLOTS_SHAPE = json.loads((kit.SHARED / "schemas" / "writer-slots.schema.json").read_text(encoding="utf-8"))
PIN_ORDER = (kit.BLOCKS / "weapon-pin" / "fixtures" / "standalone.stubs.yaml")
TYPE_OWNED_VALUES = {"first_prompt", "unattended", "overlay_file", "summary_file", "g1_items"}   # 型の block の本体が足す物（slots に入れない）
TYPE_OWNED_WHEN = {"spawns", "g1", "ask_variant"}


class WriterSlotsCase(unittest.TestCase):
    """縛る試験 5（docs/design/fix.md の 2.3）: writer_slots が組む slots の values・when の鍵の組が形（writer-slots.schema.json）の required と
    等しく、義務の表から引く段落が表（duties・board.RED_WEAPONS・prompts.SITES_WEAPONS）のとおり。型の block に渡る注文と slots は
    fix-prep が pointer で返す"""

    def setUp(self):
        self.run = seeded(self)
        self.run.script("intake", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": [1]}), judgment=JUDGMENT,
                        plan=PLAN, fix_plan=FIX_PLAN, tdd_suite=str(RUNNER))
        self.run.script("group_start")
        self.prompts, self.board, self.duties, self.writers = (kit.load("fix", m) for m in ("prompts", "board", "duties", "writers"))

    def slots(self, weapon: str) -> dict:
        facts, rules = kit.load("fix", "facts"), kit.load("fix", "rules")
        import ports
        place = self.run.artifacts
        with self.run.env():
            owed = self.board.group_owed(place, [KEY])
            record, summary = self.board.loop_files(place)
            values = self.board.fix_values(place, owed, record=record, summary=summary if weapon == "tdd" else "", answer_node=rules.answer_node("first"))
            got, rnd = self.prompts.writer_slots(place, self.run.repo, "first", weapon, values, owed=owed,
                                                 items=functools.partial(self.board.place_items, place),
                                                 sources=self.board.brief_sources(place),
                                                 frozen=facts.frozen_tests(place, record, "first"), shared=ports.shared_cache())
        self.assertEqual(set(rnd), {"iteration", "kinds", "ledger"})
        return got

    def test_the_keys_of_the_values_and_the_paragraphs_are_the_required_of_the_shape(self):
        want = {"values": set(SLOTS_SHAPE["properties"]["values"]["required"]), "when": set(SLOTS_SHAPE["properties"]["when"]["required"])}
        for weapon in self.writers.SEQUENCE["first"]:
            with self.subTest(weapon=weapon):
                got = self.slots(weapon)
                self.assertEqual(set(got), set(SLOTS_SHAPE["required"]))
                self.assertEqual(set(got["values"]), want["values"])
                self.assertEqual(set(got["when"]), want["when"])
                self.assertFalse((set(got["values"]) & TYPE_OWNED_VALUES) | (set(got["when"]) & TYPE_OWNED_WHEN), "型が持つ物は slots に入れない")
                kit.shaped("shared:writer-slots.schema.json", got)
                self.assertEqual(set(got["subagents"]), set(SLOTS_SHAPE["properties"]["subagents"]["required"]), "欄は全部置く（型を問わず同じ組み方）")
                self.assertEqual(bool(got["summary_file"]), weapon == "tdd", "輪の要約は閉じの書き手の注文の時だけ")

    def test_the_subagents_hold_the_data_and_no_instruction_text(self):
        """slots の subagents（11.4 の 5）: 下請けを起こす単位・それに当たる brief の行・凍結した項目の番号・直す義務の単位の brief の行・判定のファイル・
        修正前の版・事前の確かめのコマンド・作業ツリーの根。データだけで、指示の文を持たない"""
        got = self.slots("variant")["subagents"]
        place = self.run.artifacts
        brief = str(place / "brief-1.md")
        self.assertEqual((got["owed"], got["all_items"], got["judgment_file"], got["policy_path"], got["directory"]),
                         ([KEY], [1], str(place / "judgment.json"), "", str(self.run.repo)))
        self.assertEqual(got["briefs"], [{"item": 1, "file": brief, "unit_keys": [KEY]}])
        self.assertTrue(got["seat_brief_rows"].startswith(f"- 項目 1: {brief}（sha256 "), got["seat_brief_rows"])
        self.assertRegex(got["base_rev"], r"^[0-9a-f]{40}$")
        self.assertTrue(got["check_cmd"].endswith(str(place / "consult.json")), "相談の控えが在れば事前の確かめのコマンド")

    def test_the_units_the_tdd_loop_made_green_are_not_handed_to_the_subagents(self):
        """下請けを起こす単位は、TDD の輪が緑にした単位を除いた物（rules.dispatched）。除いた後に brief の行も合わせて減る"""
        two = ["a.py:1 x", "b.py:2 y"]
        briefs = [{"item": 1, "file": "/b/1.md", "unit_keys": [two[0]], "sha256": "s"}, {"item": 2, "file": "/b/2.md", "unit_keys": [two[1]], "sha256": "s"}]
        got = self.prompts.subagents_slot({"judgment_file": "/j", "policy_path": ""}, self.run.repo, briefs, two, frozenset({two[0]}), "")
        self.assertEqual((got["owed"], [r["item"] for r in got["briefs"]], got["all_items"]), ([two[1]], [2], [1, 2]))
        self.assertNotIn("/b/1.md", got["seat_brief_rows"])
        self.assertEqual(got["check_cmd"], "", "相談の控えが無ければ空")

    def test_a_round_without_subagents_has_every_field_and_no_data(self):
        want = self.prompts.no_subagents()
        self.assertEqual(set(want), set(SLOTS_SHAPE["properties"]["subagents"]["required"]))
        self.assertFalse(any(want.values()), "空の並びと空の字だけ")
        kit.shaped("shared:writer-slots.schema.json", {**self.slots("pin"), "subagents": want})

    def test_the_duty_paragraphs_are_drawn_from_the_duty_tables(self):
        for weapon in self.writers.SEQUENCE["first"]:
            with self.subTest(weapon=weapon):
                when = self.slots(weapon)["when"]
                change = self.duties.box_of(weapon) == "change"
                table = {getattr(fn, "paragraph", None) for fn in self.duties.table_of(weapon)}
                self.assertEqual({k: when[k] for k in self.prompts.DUTY_WHEN},
                                 {"rules_change": change, "rules_sites": weapon in self.prompts.SITES_WEAPONS,
                                  "rules_red": weapon in self.board.RED_WEAPONS, "conflict_change": change,
                                  **{k: k in table for k in self.prompts.TABLE_WHEN}})   # 表の関数の属性 paragraph から引く（F1）

    def test_the_duty_names_are_a_part_of_the_slots_and_not_of_the_types_own_paragraphs(self):
        """義務から引く段落（slots が持つ）と型の block の本体が足す段落は重ならない（和にした時に同じ名が 2 度出ない）"""
        self.assertFalse(set(self.prompts.DUTY_WHEN) & TYPE_OWNED_WHEN)
        self.assertLessEqual(set(self.prompts.DUTY_WHEN), set(SLOTS_SHAPE["properties"]["when"]["required"]))

    def test_fix_prep_hands_the_type_block_its_order_and_slots_by_pointer(self):
        """どの型の周も writer が include の id で、order と slots が pointer。指示は組まない（型の block が組む）"""
        place = self.run.artifacts
        orders = place / "orders"
        orders.mkdir()
        (orders / "pin.json").write_text(yaml.safe_load(PIN_ORDER.read_text(encoding="utf-8"))["fixture"]["inputs"]["order"], encoding="utf-8")
        self.assertEqual(self.run.script("writer_pick", **{"pass": "first"}), {"go": True, "writer": "w-pin", "done": True})
        out = self.run.script("fix_prep")
        self.assertEqual((out["go"], out["writer"]), (True, "w-pin"))
        self.assertNotIn("prompt", out, "指示は型の block が組む")
        self.assertEqual(out["order"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "orders/pin.json"})
        self.assertEqual(out["slots"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "slots-w-pin-1.json"})
        kit.shaped("shared:writer-slots.schema.json", json.loads((place / "slots-w-pin-1.json").read_text(encoding="utf-8")))
        self.assertTrue((place / "w-pin-delivered.json").is_file(), "渡した証拠の種類の控えは include の id の名")
        self.assertEqual(self.run.script("fix_prep")["slots"]["path"], "slots-w-pin-2.json", "周ごとに別のファイル")


if __name__ == "__main__":
    unittest.main()
