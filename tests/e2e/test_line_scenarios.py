"""線 works-factory-line の筋書き（workflows/line/fixtures/*.stubs.yaml）を、止めた Archon の `workflow test` で回す。

木は tests/archon.py の使い捨ての木に、線と .shared/ と、線が差し込む本物のブロックを置いた物。筋書きは本物のブロックの節の id
（例 test-gate-base__run）に stub を置き、本物の返す節の output_format に合う値で差す。
筋書きは exec-code: true で、stub の無い線の script は本当に走る。dry-run の制約と stub の置き方は docs/design.md の U3。
Archon の源か bun が無ければ名前つきで見送る。
"""
import json
import pathlib
import unittest

import yaml

from tests import archon
from tests.layers import scan

SCENARIOS = (
    "standard", "start-refused", "no-fix", "policy-continue", "policy-stop", "plan-stalled", "plan-unsettled", "replan",
    "rejudge", "light", "final-stop", "final-when-needed-green", "conflict-ask", "unattended-needs-human", "block-failed",
    "replan-stop", "plan-failed", "block-returns-failed", "replan-answers", "rejudge-stop", "unattended-questions",
    "unattended-policy-change",
)


def blocks() -> list[str]:
    """線が差し込むブロックのフォルダの名"""
    return sorted({name.removeprefix(scan.OURS_PREFIX) for name in scan.includes(archon.ROOT, scan.LINE_YAML)})


def run_line() -> dict:
    """筋書きの名 → workflow test の 1 件の結果"""
    with archon.tree(["line", *blocks()]) as tree:
        done = archon.archon(tree, "workflow", "test", archon.PACK["ours"]["line"], "--cwd", str(tree), "--json")
        return scenarios(done)


def scenarios(done) -> dict:
    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"workflow test の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
    if "results" not in report:
        raise AssertionError(f"workflow test が筋書きを回せない: {json.dumps(report, ensure_ascii=False)}")
    return {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r for r in report["results"]}


class LineScenariosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = run_line()

    def test_every_scenario_is_declared(self):
        self.assertEqual(sorted(self.results), sorted(SCENARIOS))

    def test_every_scenario_passes(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                got = self.results.get(name)
                self.assertIsNotNone(got, f"筋書き {name} が無い")
                self.assertTrue(got["pass"], json.dumps(got, ensure_ascii=False))



def line_traces(names) -> dict:
    """筋書きの名 → その筋書きの stub で線を dry-run（exec-code）した trace（節の id → trace の行）。workflow test は節の出力を返さない
    ので、筋書きの stub と入力をそのまま `workflow run --dry-run` に渡す（tests/workflows/test_report.py と同じ形）"""
    out = {}
    with archon.tree(["line", *blocks()]) as tree:
        for name in names:
            fixture = yaml.safe_load((archon.WORKFLOWS / "line" / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))
            stubs = tree.parent / f"{name}.stubs.yaml"
            stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")},
                                            allow_unicode=True), encoding="utf-8")
            args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
            done = archon.archon(tree, "workflow", "run", archon.PACK["ours"]["line"], "--dry-run", "--exec-code", "--stubs", str(stubs),
                                 "--json", *args, "--cwd", str(tree))
            try:
                out[name] = {n["nodeId"]: n for n in json.loads(done.stdout)["trace"]}
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise AssertionError(f"{name} の dry-run の trace が読めない（{error}）: {done.stdout[-2000:]}{done.stderr[-2000:]}") from None
    return out


def line_returns(names) -> dict:
    """筋書きの名 → 線の返す節 result の出力（line_traces の result の行）"""
    out = {}
    for name, trace in line_traces(names).items():
        try:
            out[name] = json.loads(trace["result"]["output"])
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise AssertionError(f"{name} の dry-run の result が読めない（{error}）: {trace.get('result')}") from None
    return out


class LineReturnsTest(unittest.TestCase):
    """線の返り（result）の欄 apply・sealed・r2_status・final_answer（bin/apply と段 1 が読む）を、筋書きの道で照らす"""

    @classmethod
    def setUpClass(cls):
        cls.returns = line_returns(("standard", "final-stop", "rejudge-stop"))

    def test_standard_applies_the_sealed_diff(self):
        got = self.returns["standard"]
        self.assertIs(got["apply"]["ok"], True, got)
        self.assertEqual(got["apply"]["hash"], got["sealed"]["hash"])
        self.assertEqual(got["r2_status"], "pass")
        self.assertEqual(got["final_answer"], {"decision": "approve", "text": "", "asked": []})

    def test_final_stop_keeps_the_seal_without_applying(self):
        got = self.returns["final-stop"]
        self.assertIsNone(got["apply"], got)
        self.assertIs(got["sealed"]["ok"], True)
        self.assertEqual(got["final_answer"]["decision"], "stop")

    def test_rejudge_stop_never_seals(self):
        """L-D48: 再審が止まった run は試験の関門から先へ進まず、封じも当てもしない"""
        got = self.returns["rejudge-stop"]
        self.assertEqual((got["apply"], got["sealed"], got["r2_status"], got["final_answer"]), (None, None, None, None), got)


class UnattendedGateTest(unittest.TestCase):
    """無人の run の修正前の関所（L-G38・L-G40・P236）: 台帳の問いだけなら関所を開かず修正へ進み、方針の文書の変化が在れば修正へ
    進まずに止まる。筋書きの宣言は節が走らなかったことを照らせない（止めた Archon の packages/workflows/src/fixture-runner.ts 70-77 行）
    ので、dry-run の trace で照らす"""

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(("unattended-questions", "unattended-policy-change"))

    @staticmethod
    def ran(trace, node) -> bool:
        return node in trace and trace[node]["state"] in ("completed", "stubbed")

    def test_questions_only_go_to_fix_without_the_gate(self):
        trace = self.traces["unattended-questions"]
        asked = json.loads(trace["ask-before-fix"]["output"])
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"], len(asked["deferred"])), (False, True, "", 1), asked)
        self.assertFalse(self.ran(trace, "gate-before-fix"))
        self.assertTrue(self.ran(trace, "fix__fix"))

    def test_policy_change_stops_before_fix(self):
        trace = self.traces["unattended-policy-change"]
        asked = json.loads(trace["ask-before-fix"]["output"])
        self.assertEqual((asked["open"], asked["go"], asked["stop_reason"]), (False, False, "works:needs-human"), asked)
        self.assertFalse(self.ran(trace, "gate-before-fix"))
        self.assertFalse(self.ran(trace, "fix__fix"))
        self.assertTrue(self.ran(trace, "report__report"))


if __name__ == "__main__":
    unittest.main()
