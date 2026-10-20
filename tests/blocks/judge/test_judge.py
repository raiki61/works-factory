"""判定のまとめの graph（workflows/judge。docs/design/judge-eyes.md の 1 節）: 止めの語の順・返りの無い block の欄・diagnose へ渡す値の
そろえ方・判定の裏取りの選び・返す node が落ちないこと・配線の yes/no・筋書きの verdict を確かめる。

元は今の tests/workflows/test_judge.py の graph の場面（docs/design/README.md の 9.5）。include した block の中は各 block の試験が見る。
守る keep-essence: 7（class_query。diagnose が作り、この graph は judgment の pointer を運ぶ）・12（世界の解の行を world の欄で運ぶ）
"""
import copy
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = "judge"
MATERIALS = ("prior-decisions", "purpose-review", "local-review", "consistency-bypass", "hygiene", "external-standards",
             "procedure-trace", "test-double-fidelity", "main-path-observation", "provenance")
INCLUDED = ("head-depth", "spec", "parallel-pr", "premises", "purpose", "world", *MATERIALS, "diagnose", "verify")
# include した block の入力のうち、この graph が渡さない物と訳（README の 8.1・各設計書の 1.2）
NOT_PASSED = {
    ("spec", "spec"): "check の時だけ読む（判定の道は write）",
    ("diagnose", "objection"): "再審の道の入力（再審は line が diagnose を直に include する）",
    ("diagnose", "prior"): "再審の道の入力", ("diagnose", "prior_brief"): "再審の道の入力",
    ("diagnose", "prior_inputs"): "再審の道の入力", ("diagnose", "spec"): "再審の道の入力",
    ("diagnose", "verify"): "再審の道の入力", ("diagnose", "excluded"): "再審の道の入力",
    ("diagnose", "answers"): "空の配列で依頼の容器の answers を読む", ("diagnose", "prior_failures"): "空の配列で依頼の容器の物を読む",
}
REQUEST = [{"where": "app.py", "text": "Uploads fail on a flaky link; retry them."}]


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": path}


def passing() -> dict:
    """どの段も通った受け皿の got（include した block の名 → got）と返しの出力"""
    got = {
        "head-depth": {"ok": True, "status": "ok", "reason": "", "tier": "標準", "why": "原因が未知", "rows": [], "record": ptr("h.json"),
                       "report": ["- 段: 標準"]},
        "spec-in": {"go": True, "stop_reason": "", "reason": "", "request": ptr("judge/request.json"), "spec": None, "added_rows": None,
                    "added_origin": ""},
        "parallel-pr": {"ok": True, "status": "clean", "stop_reason": "", "reason": "", "material": {"status": "clean", "checked": "x"},
                        "excluded": ptr("pr.json"), "drafts": None, "reads": None,
                        "downgrades": [{"what": "pr", "versus": "rg"}], "report": ["- 並行 PR"]},
        "premises": {"ok": True, "status": "ok", "reason": "", "constraints": ptr("c.json"), "report": ["- 前提"]},
        "purpose": {"ok": True, "status": "ok", "reason": "", "purpose": ptr("p.json"), "purpose_text": "P", "source": "①PR 説明",
                    "means": ["m"], "report": ["- 目的"]},
        "world": {"ok": True, "status": "ok", "reason": "", "rows": ptr("w.jsonl"), "classes": 1, "dropped": 0, "report": ["- 世界"]},
        "diagnose-in": {"ok": True, "reason": "", "go": True, "materials": [], "missing": [], "tier": "標準", "verify": True},
        "diagnose": {"ok": True, "status": "ok", "stop_reason": "", "reason": "", "ready": True, "judgment": ptr("j.json"),
                     "units": [{"id": "u1", "paths": ["a.py"], "summary": "s"}], "questions": [{"id": "q1", "text": "t"}], "inputs": None,
                     "brief": None, "materials": ptr("m.json"), "out_of_purpose": None, "answer_ties": None,
                     "downgrades": [{"what": "rejudge", "versus": "rg"}], "report": ["- 判定"]},
        "verify": {"ok": True, "status": "ok", "stop_reason": "", "reason": "", "verify": ptr("v.json"), "report": ["- 裏取り"]},
    }
    for name in MATERIALS:
        got[name] = {"ok": True, "status": "skipped", "reason": "", "material": ptr(f"{name}/material.json"), "report": [f"観点 {name}"]}
    return got


class FeedCase(unittest.TestCase):
    def setUp(self):
        self.feed = kit.load(BLOCK, "feed")

    def test_spec_gate(self):
        gate = self.feed.spec_gate
        self.assertEqual(gate(False, None)["go"], True, "仕様の段を挟まない run は進む")
        self.assertEqual(gate(True, None), {"go": False, "stop_reason": "works:spec", "reason": self.feed.SPEC_FELL})
        self.assertEqual(gate(True, {"status": "approved", "stop_reason": ""})["go"], True)
        self.assertEqual(gate(True, {"status": "stopped", "stop_reason": "human:spec-gate", "reason": "人が止めた"}),
                         {"go": False, "stop_reason": "human:spec-gate", "reason": "人が止めた"})
        self.assertEqual(gate(True, {"status": "failed", "stop_reason": ""})["stop_reason"], "works:spec")

    def test_spec_rows_are_stacked_on_the_request(self):
        added = [{"where": "t.py: test_a", "text": "accept"}]
        self.assertEqual(self.feed.merged(REQUEST, added), [*REQUEST, *added])
        box = {"findings": REQUEST, "answers": [{"question": "q", "text": "a"}]}
        self.assertEqual(self.feed.merged(box, added), {**box, "findings": [*REQUEST, *added]})
        self.assertIs(self.feed.merged(box, []), box)

    def test_materials_keep_the_order_and_name_the_missing(self):
        got = passing()
        got["hygiene"] = None
        got["provenance"] = {**got["provenance"], "material": None}
        values = self.feed.diagnose_values(got, {})
        self.assertEqual(values["materials"], [got[n]["material"] for n in MATERIALS if n not in ("hygiene", "provenance")])
        self.assertEqual(values["missing"], ["hygiene", "provenance"])
        self.assertEqual(values["pr_material"], {"status": "clean", "checked": "x"})
        self.assertEqual((values["world_rows"], values["row_asks"], values["depth_why"]), (ptr("w.jsonl"), [], "原因が未知"))
        self.assertEqual((values["go"], values["purpose"], values["constraints"]), (True, ptr("p.json"), ptr("c.json")))
        got["purpose"] = None
        self.assertEqual((self.feed.diagnose_values(got, {})["go"], self.feed.diagnose_values(got, {})["purpose"]), (False, None),
                         "目的の固定が返らなければ diagnose を回さない")

    def test_verify_is_picked_by_the_tier(self):
        got = passing()
        table = {"軽量": False, "標準": False, "重厚": True}
        self.assertFalse(self.feed.diagnose_values(got, table)["verify"])
        got["head-depth"] = {**got["head-depth"], "tier": "重厚"}
        self.assertTrue(self.feed.diagnose_values(got, table)["verify"])
        self.assertFalse(self.feed.diagnose_values(got, {})["verify"], "空の表はどの段でも回さない")
        got["head-depth"] = None
        values = self.feed.diagnose_values(got, {"標準": True})
        self.assertEqual((values["tier"], values["verify"], values["depth_why"], values["row_asks"]), ("標準", True, "", []),
                         "段が返らなければ標準で引く")

    def test_spec_rows_are_passed_to_diagnose(self):
        got = passing()
        got["spec-in"] = {**got["spec-in"], "added_rows": ptr("judge/spec/added-rows.json"), "added_origin": "仕様の受け入れ条件"}
        values = self.feed.diagnose_values(got, {})
        self.assertEqual((values["spec_rows"], values["spec_origin"]), (ptr("judge/spec/added-rows.json"), "仕様の受け入れ条件"))

    def test_absent_feeds_are_empty(self):
        got = passing()
        for name in ("parallel-pr", "world", "spec-in"):
            got[name] = None
        values = self.feed.diagnose_values(got, {})
        self.assertEqual((values["pr_material"], values["world_rows"], values["spec_rows"], values["spec_origin"]), (None, "", "", ""))


class VerdictCase(unittest.TestCase):
    def setUp(self):
        self.v = kit.load(BLOCK, "verdict")

    def build(self, got, world_on=True, rows=True):
        return self.v.build(got, world_on=world_on, world_has_rows=rows)

    def test_passing_run(self):
        out = self.build(passing())
        self.assertEqual((out["ok"], out["ready"], out["stop_reason"]), (True, True, ""))
        self.assertEqual(out["units"], passing()["diagnose"]["units"])
        self.assertEqual(out["questions"], passing()["diagnose"]["questions"])
        self.assertEqual((out["judgment"], out["world"], out["verify"], out["verify_why"]), (ptr("j.json"), ptr("w.jsonl"), ptr("v.json"), ""))
        self.assertEqual((out["purpose_text"], out["purpose_source"], out["means"]), ("P", "①PR 説明", ["m"]))
        self.assertEqual(out["downgrades"], [{"what": "pr", "versus": "rg"}, {"what": "rejudge", "versus": "rg"}])
        self.assertEqual(out["decisions"], ptr("prior-decisions/material.json"))
        self.assertEqual([s["title"] for s in out["sections"]][:6], ["run の頭の深さ", "並行 PR", "前提の実測", "目的の固定", "世界の解",
                                                                    "素材: 先行議論の突合"])
        self.assertEqual(out["sections"][-1]["title"], "判定のまとめ")

    def test_stop_order(self):
        """1.4 の 1〜6 を全部立て、上から 1 つずつ外すと、残りの最初の物が返る"""
        stops = [("spec-in", {"go": False, "stop_reason": "human:spec-gate", "reason": "s"}, "human:spec-gate"),
                 ("parallel-pr", {"stop_reason": "works:pr", "ok": False, "reason": "p"}, "works:pr"),
                 ("premises", {"ok": False, "reason": "r"}, "works:premises"),
                 ("purpose", {"ok": False, "reason": "u"}, "works:purpose"),
                 ("diagnose", {"stop_reason": "works:material", "ok": False, "ready": False, "reason": "m"}, "works:material"),
                 ("verify", {"stop_reason": "works:judge-verify", "ok": False, "reason": "v"}, "works:judge-verify")]
        for first in range(len(stops)):
            got = passing()
            for name, change, _ in stops[first:]:
                got[name] = {**got[name], **change}
            with self.subTest(first=stops[first][2]):
                out = self.build(got)
                self.assertEqual((out["ok"], out["ready"], out["stop_reason"]), (False, False, stops[first][2]))
                self.assertIn(f"止めた（{stops[first][2]}）", out["report"][0])

    def test_absent_blocks_stop_by_their_word(self):
        for name, word in (("parallel-pr", "works:pr"), ("premises", "works:premises"), ("purpose", "works:purpose"),
                           ("diagnose", "works:judge")):
            got = passing()
            got[name] = None
            with self.subTest(name=name):
                out = self.build(got)
                self.assertEqual(out["stop_reason"], word)
                self.assertIn("返らなかった", out["reason"])

    def test_unready_feed_names_its_reason(self):
        got = passing()
        got["diagnose"] = None
        got["diagnose-in"] = {"ok": False, "reason": "判定へ渡す値をそろえられない（x）"}
        self.assertEqual(self.v.stop_of(got), ("works:judge", "判定へ渡す値をそろえられない（x）"))

    def test_materials_not_run_after_a_stop_are_not_named(self):
        got = passing()
        got["premises"] = {**got["premises"], "ok": False}
        got["diagnose-in"] = {**got["diagnose-in"], "go": False, "missing": list(MATERIALS)}
        got["diagnose"] = got["verify"] = None
        out = self.build(got)
        self.assertEqual(out["stop_reason"], "works:premises")
        self.assertNotIn("素材", "\n".join(out["report"]))
        self.assertEqual(out["verify_why"], "判定が止まったので回さなかった")

    def test_no_open_units_is_not_a_stop(self):
        got = passing()
        got["diagnose"] = {**got["diagnose"], "ready": False, "units": []}
        got["verify"] = None
        out = self.build(got)
        self.assertEqual((out["ok"], out["ready"], out["verify"]), (True, False, None))
        self.assertEqual(out["verify_why"], "開いた単位が無いので回さなかった")

    def test_absent_fields_are_null_and_reported(self):
        got = passing()
        for name in ("head-depth", "world", "verify", "hygiene"):
            got[name] = None
        got["diagnose-in"] = {**got["diagnose-in"], "missing": ["hygiene"], "verify": False, "tier": "標準"}
        out = self.build(got)
        self.assertTrue(out["ok"])
        self.assertEqual((out["tier"], out["tier_why"], out["tier_record"], out["row_asks"]),
                         ("標準", self.v.NO_TIER_WHY, None, []))
        self.assertEqual((out["world"], out["world_state"]["status"]), (None, "failed"))
        self.assertEqual((out["verify"], out["verify_why"]), (None, "段 標準 では判定の裏取りを回さない（段ごとの表）"))
        text = "\n".join(out["report"])
        for want in ("run の頭の深さの段が返らなかった", "世界の解の段が返らなかった", "素材: コード衛生の段が返らなかった",
                     "判定の裏取り: 段 標準"):
            self.assertIn(want, text)
        self.assertNotIn("素材: コード衛生", [s["title"] for s in out["sections"]])

    def test_world_cut_and_empty_rows(self):
        got = passing()
        got["world"] = None
        out = self.build(got, world_on=False)
        self.assertEqual(out["world_state"]["status"], "skipped")
        self.assertIn("world: false", out["world_state"]["reason"])
        out = self.build(passing(), rows=False)
        self.assertEqual((out["world"], out["world_state"]["status"]), (None, "ok"), "行が 0 の世界の解は null（J29）")

    def test_stopped_run_keeps_what_ran(self):
        got = passing()
        got["diagnose"] = {**got["diagnose"], "stop_reason": "works:judge", "ok": False, "ready": False, "reason": "諦めた"}
        out = self.build(got)
        self.assertEqual((out["units"], out["judgment"], out["purpose"]), ([], ptr("j.json"), ptr("p.json")))
        self.assertIn("前提の実測", [s["title"] for s in out["sections"]])

    def test_optional_absorbs_block_declarations(self):
        got = passing()
        got["head-depth"] = {**got["head-depth"], "optional": [{"node": "x", "bare": False}, {"node": "y", "bare": True}]}
        rows = self.build(got)["optional"]
        self.assertIn({"node": "world__", "bare": False}, rows)
        self.assertIn({"node": "provenance-run__", "bare": False}, rows)
        self.assertIn({"node": "head-depth-run__x", "bare": False}, rows)
        self.assertIn({"node": "y", "bare": True}, rows)
        self.assertEqual(len(rows), len({(r["node"], r["bare"]) for r in rows}))

    def test_fallback_has_every_field(self):
        fallback = kit.load(BLOCK, "fallback")
        doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
        shape = next(n for n in doc["nodes"] if n["id"] == "verdict")["output_format"]
        out = fallback.fallen("x")
        self.assertEqual(set(out), set(shape["required"]))
        self.assertEqual(set(self.build(passing())), set(shape["required"]))
        self.assertEqual((out["ok"], out["stop_reason"]), (False, "works:judge"))


class ScriptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def test_returned_carries_named_fields(self):
        got = self.run.script("returned", "judge__x-out", got=json.dumps({"ok": True, "report": [], "extra": 1}), names="ok report")
        self.assertEqual(got, {"got": {"ok": True, "report": [], "optional": None}, "why": ""})
        got = self.run.script("returned", "judge__x-out", got=json.dumps({"ok": True}), names="ok report")
        self.assertIsNone(got["got"])
        self.assertIn("report", got["why"])

    def test_ins(self):
        got = self.run.script("ins", "judge__ins", spec="true", world="false", web="off")
        self.assertEqual(got, {"spec": True, "world": False, "web": "off"})

    def test_spec_in_stacks_rows_for_the_later_stages(self):
        place = self.run.artifacts / "judge" / "spec"
        place.mkdir(parents=True)
        added = [{"where": "tests/test_up.py: test_retry", "text": "【仕様】受け入れ条件 A1 がまだ満たされていない"}]
        (place / "added-rows.json").write_text(json.dumps(added, ensure_ascii=False), encoding="utf-8")
        spec = {"ok": True, "status": "approved", "stop_reason": "", "reason": "", "spec": ptr("judge/spec/spec.json"),
                "added_rows": ptr("judge/spec/added-rows.json"), "added_origin": "仕様の受け入れ条件", "report": []}
        got = self.run.script("spec_in", "judge__spec-in", spec="true", request=json.dumps(REQUEST),
                              spec_out=json.dumps({"got": spec, "why": ""}))
        self.assertEqual((got["go"], got["stop_reason"], got["added_origin"]), (True, "", "仕様の受け入れ条件"))
        self.assertEqual(got["added_rows"], ptr("judge/spec/added-rows.json"))
        stacked = json.loads((self.run.artifacts / got["request"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(stacked, [*REQUEST, *added])

    def test_spec_in_without_spec_copies_the_request(self):
        got = self.run.script("spec_in", "judge__spec-in", spec="false", request=json.dumps(REQUEST), spec_out="null")
        self.assertEqual((got["go"], got["added_rows"], got["spec"]), (True, None, None))
        self.assertEqual(json.loads((self.run.artifacts / got["request"]["path"]).read_text(encoding="utf-8")), REQUEST)
        got = self.run.script("spec_in", "judge__spec-in", spec="true", request=json.dumps(REQUEST), spec_out="null")
        self.assertEqual((got["go"], got["stop_reason"]), (False, "works:spec"))

    def test_spec_in_falls_without_crashing(self):
        got = self.run.script("spec_in", "judge__spec-in", spec="false", request="{not json", spec_out="null")
        self.assertEqual((got["go"], got["stop_reason"], got["request"]), (False, "works:request", None))

    def test_stacked_request_reaches_the_premises_intake(self):
        """spec-in の pointer を前提の実測の入口が port のまま読める（同じ run の pointer）"""
        (self.run.repo / "app.py").write_text("print('up')\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        got = self.run.script("spec_in", "judge__spec-in", spec="false", request=json.dumps(REQUEST), spec_out="null")
        intake = self.run.other("premises").script("intake", "judge__premises-run__intake", request=json.dumps(got["request"]),
                                                   carried="[]", lang="")
        self.assertTrue(intake["due"], intake)

    def receivers(self, got: dict) -> dict:
        outs = {f"{name.replace('-', '_')}_out": json.dumps({"got": got.get(name), "why": ""} if got.get(name) else None)
                for name in INCLUDED}
        return {**outs, "spec_in": json.dumps(got.get("spec-in")), "diagnose_in": json.dumps(got.get("diagnose-in"))}

    def test_diagnose_in_script(self):
        got = passing()
        got["hygiene"] = None
        out = self.run.script("diagnose_in", "judge__diagnose-in", verify_by_tier='{"標準": true}', **self.receivers(got))
        self.assertEqual((out["ok"], out["missing"], out["verify"], len(out["materials"])), (True, ["hygiene"], True, 9))

    def test_diagnose_in_falls_without_crashing(self):
        out = self.run.script("diagnose_in", "judge__diagnose-in", verify_by_tier='{"標準": "yes"}', spec_in="null")
        self.assertEqual((out["ok"], out["verify"]), (False, False))

    def test_verdict_script_writes_its_files(self):
        got = passing()
        got["world"] = {**got["world"], "rows": None}
        out = self.run.script("verdict", "judge__verdict", world="true", **self.receivers(got))
        self.assertEqual((out["ok"], out["ready"]), (True, True), out["report"])
        self.assertEqual(out["purpose_review"], ptr("judge/purpose-review.json"))
        self.assertEqual(json.loads((self.run.artifacts / "judge" / "purpose-review.json").read_text(encoding="utf-8")), {})
        self.assertIn("目的の監査の素材が読めない", "\n".join(out["report"]), "素材のファイルが無いのは行で言い、まとめは落ちない")
        self.assertTrue((self.run.artifacts / "judge" / "verdict.json").is_file())

    def test_verdict_never_falls(self):
        out = self.run.script("verdict", "judge__verdict", world="maybe")
        self.assertEqual((out["ok"], out["stop_reason"], out["ready"]), (False, "works:judge", False))
        self.assertIn("判定のまとめが落ちた", out["report"][0])


class WiringCase(unittest.TestCase):
    """配線の yes/no（docs/design/judge-eyes.md の 1.8）"""

    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.doc["nodes"]}
        # include した block の名 → include の node（id は fallback.include_id。block の中の node と同じ id にしない）
        cls.includes = {n["include"].removeprefix("works-factory-"): n for n in cls.doc["nodes"] if "include" in n}

    def test_every_block_of_the_judgment_is_included_once(self):
        named = sorted(n["include"] for n in self.includes.values())
        self.assertEqual(named, sorted(f"works-factory-{b}" for b in INCLUDED))
        self.assertNotIn("works-factory-gate-efficacy", named, "重い検算は run の中で回さない（持ち主の決め 2026-10-19）")
        self.assertNotIn("gates", self.doc["inputs"])

    def test_web_reaches_the_world_stage(self):
        """world-offline の筋書きは world の中を台本で差し替えるので、web が world に渡ることは配線で見る"""
        self.assertEqual(self.includes["world"]["with"]["web"], "$ins.output.web")

    def test_no_rejudge_path(self):
        self.assertNotIn("objection", self.includes["diagnose"]["with"])
        self.assertNotIn("prior", self.includes["diagnose"]["with"])

    def test_every_include_has_a_receiver_and_the_verdict_reads_receivers_only(self):
        verdict = self.nodes["verdict"]
        self.assertEqual(verdict["trigger_rule"], "all_done")
        for node in self.includes.values():
            name = node["id"]
            self.assertEqual(self.nodes[f"{name}-out"]["with"]["got"], f"${name}.output")
            self.assertIn(f"{name}-out", verdict["depends_on"])
        reads = json.dumps(verdict["with"])
        self.assertFalse([n["id"] for n in self.includes.values() if f"${n['id']}.output" in reads], "verdict は include を直に読まない")

    def test_include_ids_follow_the_verdict_table(self):
        """include の id は verdict が optional の頭に付ける名（fallback.include_id）と同じ"""
        fallback = kit.load(BLOCK, "fallback")
        self.assertEqual({b: n["id"] for b, n in self.includes.items()}, {b: fallback.include_id(b) for b in self.includes})

    def test_spec_rows_reach_the_stages_after_the_spec(self):
        """今の spec_freeze は受け入れ条件の行を依頼の行に積み、並行 PR・前提の実測・世界の解・先行議論の突合が読んだ"""
        for name in ("parallel-pr", "premises", "world", "prior-decisions"):
            self.assertEqual(self.includes[name]["with"]["request"], "$spec-in.output.request", name)
        self.assertEqual(self.includes["diagnose"]["with"]["request"], "$INPUTS.request", "判定は仕様の行を spec_rows で別に受ける")
        self.assertEqual(self.includes["diagnose"]["with"]["spec_rows"], "$diagnose-in.output.spec_rows")

    def test_verify_runs_only_when_picked_and_ready(self):
        self.assertEqual(self.includes["verify"]["when"], "$diagnose-in.output.verify == true && $diagnose-run.output.ready == true")

    def test_materials_run_after_world_even_when_it_is_cut(self):
        for name in MATERIALS:
            node = self.includes[name]
            self.assertEqual((node["depends_on"], node["trigger_rule"]), (["purpose-run", "world-out"], "none_failed_min_one_success"))

    def test_include_inputs_are_passed_or_named(self):
        """include した block の inputs: の全部が with: で渡るか、渡さない訳の一覧に在る（include した block が要る）"""
        for block, node in self.includes.items():
            path = kit.BLOCKS / block / f"works-factory-{block}.yaml"
            with self.subTest(block=block):
                self.assertTrue(path.is_file(), f"include した block {block} が workflows/ に無い")
                inputs = set(yaml.safe_load(path.read_text(encoding="utf-8")).get("inputs") or {})
                given = set(node.get("with") or {})
                self.assertEqual(sorted(given - inputs), [], "block の inputs: に無い鍵を渡している")
                self.assertEqual(sorted(i for i in inputs - given if (block, i) not in NOT_PASSED), [])


class FixtureCase(unittest.TestCase):
    """筋書きを dry-run で回し、verdict の出力を見る（include した block が workflows/ に要る）"""
    SCENARIOS = ("standalone", "pass", "bad-request", "judge-gave-up", "material-peer-stop", "no-open-units", "spec-on",
                 "spec-stop", "world-offline", "world-cut", "verify-heavy")

    @classmethod
    def setUpClass(cls):
        cls.traces = kit.dry_run_traces(BLOCK, cls.SCENARIOS, INCLUDED)

    def verdict(self, name):
        return json.loads(self.traces[name]["verdict"]["output"])

    def test_verdicts(self):
        want = {"standalone": (True, True, ""), "pass": (True, True, ""), "bad-request": (False, False, "works:premises"),
                "judge-gave-up": (False, False, "works:judge"), "material-peer-stop": (False, False, "works:material"),
                "no-open-units": (True, False, ""), "spec-on": (True, True, ""), "spec-stop": (False, False, "human:spec-gate"),
                "world-offline": (True, True, ""),
                "world-cut": (True, True, ""), "verify-heavy": (True, True, "")}
        for name, (ok, ready, stop) in want.items():
            with self.subTest(scenario=name):
                out = self.verdict(name)
                self.assertEqual((out["ok"], out["ready"], out["stop_reason"]), (ok, ready, stop), out["report"])

    def test_verify_runs_only_when_the_tier_picks_it(self):
        self.assertIsNotNone(self.verdict("verify-heavy")["verify"])
        self.assertEqual(self.traces["standalone"].get("verify__finish", {}).get("state", "skipped"), "skipped")

    def test_world_cut_still_runs_materials(self):
        out = self.verdict("world-cut")
        self.assertEqual(out["world_state"]["status"], "skipped")
        self.assertIn("素材: 先行議論の突合", [s["title"] for s in out["sections"]])


if __name__ == "__main__":
    unittest.main()
