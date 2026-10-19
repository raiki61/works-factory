"""独立の目のまとめの graph（workflows/eyes。docs/design/judge-eyes.md の 2 節）: ok の決まり・返らなかった目の行と「まま R4 を回した」の尾・
目を省いた run の行・まとめた R3 の行・返す node が落ちないこと・配線の yes/no・筋書きの verdict を確かめる。

元は今の tests/workflows/test_eyes.py と lib/tests/test_eyeverdict.py のまとめの部分（docs/design/README.md の 9.5）。目の中は各 block の
試験が見る。守る keep-essence: 9（R1〜R4。この graph は r2 に独立設計の pointer を渡すだけで、修正案・判定・差分を独立設計に運ばない）
"""
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = "eyes"
EYES = ("r1", "r2", "r3", "r4")
INCLUDED = ("structure", *EYES)


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": path}


def eye(name: str, status: str = "pass", **extra) -> dict:
    return {"ok": True, "status": "ran", "reason": "", "verdict": {"status": status, "reason": f"{name} の訳"}, "questions": [],
            **extra, "report": [f"{name.upper()}: {status}"]}


def passing() -> dict:
    return {"structure-after": {"ok": True, "status": "ok", "reason": "", "structure": None, "after": ptr("structure-after/a.json"),
                                "dirty": 0, "escalate": 0, "optional": [{"node": "measure", "bare": False}], "report": ["- 実測"]},
            "r1": eye("r1"), "r2": eye("r2", premise_check=None, notes=["控え"]), "r3": eye("r3"),
            "r4": eye("r4", questions=["R4 が見た人の方針とのぶつかり: x"], passes=[{"node": "gate", "item": "y"}], coherence=None)}


class VerdictCase(unittest.TestCase):
    """まとめ（src/verdict.py。lib/eyekit を読む）"""

    def setUp(self):
        self.v = kit.load(BLOCK, "verdict")

    def build(self, got, run=True, merge=False, skip_why=""):
        return self.v.build(got, run=run, merge=merge, skip_why=skip_why)

    def test_all_pass(self):
        out = self.build(passing())
        self.assertTrue(out["ok"])
        self.assertEqual(out["r1"], {"status": "pass", "reason": "r1 の訳"})
        self.assertEqual((out["questions"], out["passes"], out["notes"], out["premise_check"]),
                         (["R4 が見た人の方針とのぶつかり: x"], [{"node": "gate", "item": "y"}], ["控え"], None))
        self.assertEqual((out["after"], out["after_ok"]), (ptr("structure-after/a.json"), True))
        self.assertEqual([s["title"] for s in out["sections"]], [*self.v.TITLES.values(), self.v.OWN_TITLE])

    def test_any_eye_not_pass_makes_ok_false(self):
        for name in EYES:
            for status in ("fix-needed", "redesign-needed", "unverifiable"):
                got = passing()
                got[name] = eye(name, status, **{k: v for k, v in got[name].items() if k in ("premise_check", "notes", "passes", "coherence")})
                with self.subTest(eye=name, status=status):
                    out = self.build(got)
                    self.assertFalse(out["ok"])
                    self.assertIn(f"{name.upper()}: {status}", out["report"][0])

    def test_premise_path_makes_ok_false(self):
        got = passing()
        got["r2"] = {**got["r2"], "premise_check": {"verdict": "resolved", "reason": "r", "key": "k", "resolution": "x", "facts": ["f"]}}
        out = self.build(got)
        self.assertFalse(out["ok"], "行が pass でも前提の検算の道なら通さない（E49）")
        self.assertEqual(out["premise_check"]["facts"], ["f"])

    def test_measured_dirt_does_not_decide_ok(self):
        got = passing()
        got["structure-after"] = {**got["structure-after"], "dirty": 3, "escalate": 1}
        out = self.build(got)
        self.assertEqual((out["ok"], out["dirty"], out["escalate"]), (True, 3, 1), "直した後の実測の数は ok に入れない（E73）")

    def test_fallen_eye_is_unverifiable_and_tail_names_r4(self):
        got = passing()
        got["r1"] = got["r3"] = None
        out = self.build(got)
        self.assertFalse(out["ok"])
        self.assertEqual(out["r1"], {"status": "unverifiable", "reason": "R1 の筋が落ちたまま R4 を回した（r1: 出力が無い。ノードが落ちた）"})
        self.assertEqual(out["r3"]["reason"], "R3 の筋が落ちた（r3: 出力が無い。ノードが落ちた）", "R4 は R3 を待たないので尾を足さない")
        got["r4"] = None
        out = self.build(got)
        self.assertEqual(out["r1"]["reason"], "R1 の筋が落ちた（r1: 出力が無い。ノードが落ちた）", "R4 が返らなければ尾を足さない")
        self.assertEqual((out["questions"], out["passes"]), ([], []))

    def test_tail_also_on_a_block_that_fell_inside(self):
        got = passing()
        got["r2"] = {**got["r2"], "status": "failed", "verdict": {"status": "unverifiable", "reason": "R2 の筋が落ちた（r2-compare: x。ノードが落ちた）"}}
        self.assertIn("落ちたまま R4 を回した", self.build(got)["r2"]["reason"])

    def test_skipped_eyes(self):
        out = self.build({"structure-after": passing()["structure-after"]}, run=False, skip_why="単位が全部軽量")
        self.assertEqual((out["ok"], out["r1"], out["r4"], out["questions"]), (True, None, None, []))
        self.assertEqual(out["report"], ["- 独立の目: 深さで省いた（単位が全部軽量）"])
        self.assertTrue(out["after_ok"], "目を省く run でも直した後の実測は回る（E71）")

    def test_merged_r3_reads_r4_coherence(self):
        got = passing()
        got["r3"] = None
        got["r4"] = {**got["r4"], "coherence": {"status": "fix-needed", "reason": "整合が欠ける"}}
        out = self.build(got, merge=True)
        self.assertEqual(out["r3"], {"status": "fix-needed", "reason": "整合が欠ける"})
        self.assertFalse(out["ok"])
        self.assertNotIn(self.v.TITLES["r3"], [s["title"] for s in out["sections"]])
        got["r4"] = {**got["r4"], "coherence": None}
        self.assertEqual(self.build(got, merge=True)["r3"]["status"], "unverifiable")

    def test_missing_after_is_said(self):
        got = passing()
        got["structure-after"] = None
        out = self.build(got)
        self.assertEqual((out["ok"], out["after"], out["after_ok"], out["dirty"]), (True, None, False, 0))
        self.assertIn("直した後の構造の実測が無い", "\n".join(out["report"]))

    def test_optional(self):
        rows = self.build(passing())["optional"]
        self.assertEqual(rows, [{"node": "structure-after__", "bare": False}, {"node": "structure-after__measure", "bare": False}])


class FallbackCase(unittest.TestCase):
    def test_fallback_has_every_field(self):
        fallback = kit.load(BLOCK, "fallback")
        doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
        shape = next(n for n in doc["nodes"] if n["id"] == "verdict")["output_format"]
        out = fallback.fallen("x")
        self.assertEqual(set(out), set(shape["required"]))
        self.assertFalse(out["ok"])
        self.assertEqual({out[e]["status"] for e in EYES}, {"unverifiable"})


class ScriptCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def test_ins(self):
        got = self.run.script("ins", "eyes__ins", run="false", merge="true", head="abc123")
        self.assertEqual(got, {"run": False, "merge": True, "head": "abc123"})

    def test_ins_resolves_empty_head_to_the_real_head(self):
        """単独（head 空）で回しても structure の base が空にならない（憲法 5）"""
        kit.git(self.run.repo, "commit", "-q", "--allow-empty", "-m", "x")
        real = kit.git(self.run.repo, "rev-parse", "HEAD")
        self.assertEqual(self.run.script("ins", "eyes__ins", run="true", merge="false", head="")["head"], real)

    def test_after_in(self):
        got = {"got": passing()["structure-after"], "why": ""}
        self.assertEqual(self.run.script("after_in", "eyes__after-in", structure_after_out=json.dumps(got))["after"],
                         ptr("structure-after/a.json"))
        self.assertEqual(self.run.script("after_in", "eyes__after-in", structure_after_out="null"), {"after": "", "why": ""})

    def test_returned(self):
        got = self.run.script("returned", "eyes__r1-out", got=json.dumps(eye("r1")), names="ok verdict report")
        self.assertEqual(got["got"]["verdict"], {"status": "pass", "reason": "r1 の訳"})

    def receivers(self, got: dict) -> dict:
        return {f"{name.replace('-', '_')}_out": json.dumps({"got": got[name], "why": ""}) if got.get(name) else "null"
                for name in ("structure-after", *EYES)}

    def test_verdict_script(self):
        out = self.run.script("verdict", "eyes__verdict", run="true", merge="false", skip_why="", **self.receivers(passing()))
        self.assertTrue(out["ok"], out["report"])
        self.assertTrue((self.run.artifacts / "eyes" / "verdict.json").is_file())

    def test_verdict_never_falls(self):
        out = self.run.script("verdict", "eyes__verdict", run="maybe", merge="false", skip_why="")
        self.assertFalse(out["ok"])
        self.assertEqual({out[e]["status"] for e in EYES}, {"unverifiable"})
        self.assertIn("出口が落ちた", out["r1"]["reason"])


class WiringCase(unittest.TestCase):
    """配線の yes/no（docs/design/judge-eyes.md の 2.7）"""

    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load((kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
        cls.nodes = {n["id"]: n for n in cls.doc["nodes"]}
        cls.includes = {n["id"]: n for n in cls.doc["nodes"] if "include" in n}

    def test_includes(self):
        self.assertEqual(sorted(n["include"] for n in self.includes.values()), sorted(f"works-factory-{b}" for b in INCLUDED))
        self.assertEqual(self.includes["structure-after"]["with"]["mode"], "after")
        self.assertEqual(self.includes["structure-after"]["with"]["base"], "$ins.output.head")

    def test_r4_waits_r1_and_r2_and_runs_when_one_fell(self):
        r4 = self.includes["r4"]
        self.assertEqual((sorted(r4["depends_on"]), r4["trigger_rule"]), (["after-in", "r1-out", "r2-out"], "none_failed_min_one_success"))
        self.assertEqual(r4["with"]["coherence"], "$ins.output.merge")

    def test_structure_after_runs_without_when(self):
        self.assertNotIn("when", self.includes["structure-after"])

    def test_r3_reads_merge_and_r2_does_not_wait_after(self):
        self.assertEqual(self.includes["r3"]["when"], "$ins.output.run == true && $ins.output.merge == false")
        self.assertEqual(self.includes["r2"]["depends_on"], ["ins"])
        self.assertNotIn("after", self.includes["r2"]["with"])

    def test_eyes_read_after_from_the_relay(self):
        for name in ("r1", "r3", "r4"):
            self.assertEqual(self.includes[name]["with"]["after"], "$after-in.output.after")

    def test_verdict_reads_receivers_only(self):
        verdict = self.nodes["verdict"]
        self.assertEqual(verdict["trigger_rule"], "all_done")
        self.assertEqual(sorted(verdict["with"]), ["r1_out", "r2_out", "r3_out", "r4_out", "structure_after_out"])

    def test_include_inputs_are_passed(self):
        """include した block の inputs: の全部が with: で渡る（include した block が要る）"""
        for name, node in self.includes.items():
            block = node["include"].removeprefix("works-factory-")
            path = kit.BLOCKS / block / f"works-factory-{block}.yaml"
            with self.subTest(block=block):
                self.assertTrue(path.is_file(), f"include した block {block} が workflows/ に無い")
                inputs = set(yaml.safe_load(path.read_text(encoding="utf-8")).get("inputs") or {})
                self.assertEqual(set(node["with"]), inputs)


class FixtureCase(unittest.TestCase):
    """筋書きを dry-run で回し、verdict の出力を見る（include した block が workflows/ に要る）"""
    SCENARIOS = ("standalone", "pass", "all-light", "one-eye", "premise", "redesign")

    @classmethod
    def setUpClass(cls):
        cls.traces = kit.dry_run_traces(BLOCK, cls.SCENARIOS, INCLUDED)

    def verdict(self, name):
        return json.loads(self.traces[name]["verdict"]["output"])

    def test_verdicts(self):
        want = {"standalone": True, "pass": True, "all-light": True, "one-eye": True, "premise": False, "redesign": False}
        for name, ok in want.items():
            with self.subTest(scenario=name):
                self.assertEqual(self.verdict(name)["ok"], ok, self.verdict(name)["report"])

    def test_standalone_with_empty_head_hands_structure_a_real_revision(self):
        """単独（head を渡さない）の筋書きで、ins が HEAD の版に解いた（structure の base が空で落ちない）"""
        head = json.loads(self.traces["standalone"]["ins"]["output"])["head"]
        self.assertRegex(head, r"^[0-9a-f]{40}$")

    def test_light_run_skips_eyes_and_keeps_after(self):
        out = self.verdict("all-light")
        self.assertEqual((out["r1"], out["after_ok"]), (None, True))
        for eye in ("r1", "r2", "r3", "r4"):
            self.assertEqual(self.traces["all-light"].get(f"{eye}__intake", {}).get("state", "skipped"), "skipped", eye)

    def test_merged_run_skips_r3(self):
        self.assertEqual(self.traces["one-eye"].get("r3__intake", {}).get("state", "skipped"), "skipped")
        self.assertEqual(self.verdict("one-eye")["r3"], {"status": "pass", "reason": "全体の整合も見た"})

    def test_premise_path(self):
        self.assertIsNotNone(self.verdict("premise")["premise_check"])


if __name__ == "__main__":
    unittest.main()
