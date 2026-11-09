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


class PolicyCase(unittest.TestCase):
    """TDD の役の指示は、line が固めた方針の写し（port policy）を名指す"""

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


SLOTS_SHAPE = json.loads((kit.SHARED / "schemas" / "writer-slots.schema.json").read_text(encoding="utf-8"))
PIN_ORDER = (kit.BLOCKS / "weapon-pin" / "fixtures" / "standalone.stubs.yaml")


class WriterSlotsCase(unittest.TestCase):
    """縛る試験 5（docs/design/fix.md の 2.3）: 義務の表から引く段落が表（duties・board.RED_WEAPONS・prompts.SITES_WEAPONS）のとおり
    （崩れると書き手は義務の欄を書けと言われず、受け付けが毎回拒む）・TDD の輪が緑にした単位を下請けへ渡さない・型の block に渡る
    注文と slots は fix-prep が pointer で返し、slots は形 writer-slots.schema.json に合う（values・when の鍵の欠けはここで赤）"""

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

    def test_the_units_the_tdd_loop_made_green_are_not_handed_to_the_subagents(self):
        """下請けを起こす単位は、TDD の輪が緑にした単位を除いた物（rules.dispatched）。除いた後に brief の行も合わせて減る"""
        two = ["a.py:1 x", "b.py:2 y"]
        briefs = [{"item": 1, "file": "/b/1.md", "unit_keys": [two[0]], "sha256": "s"}, {"item": 2, "file": "/b/2.md", "unit_keys": [two[1]], "sha256": "s"}]
        got = self.prompts.subagents_slot({"judgment_file": "/j", "policy_path": ""}, self.run.repo, briefs, two, frozenset({two[0]}), "")
        self.assertEqual((got["owed"], [r["item"] for r in got["briefs"]], got["all_items"]), ([two[1]], [2], [1, 2]))
        self.assertNotIn("/b/1.md", got["seat_brief_rows"])
        self.assertEqual(got["check_cmd"], "", "相談の控えが無ければ空")

    def test_a_round_without_subagents_has_every_field_and_no_data(self):
        """続きの周の slots の subagents（prompts.no_subagents）も形の欄を全部置く（欠けると続きの周だけ型の block の形の照らしで落ちる。
        ほかの試験は 1 回目の周の slots しか形に当てない）"""
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
