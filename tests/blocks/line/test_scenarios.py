"""line の筋書き（workflows/line/fixtures/*.stubs.yaml）の組 A の試験（docs/design/README.md の 11.3 の 2、line.md の 11 節）。結末ごとに
1 本を残す（持ち主の決め tests-guard-writes）。

元は test_line_scenarios.py と test_line.py の筋書きの場面。筋書きを新しい line の node の id
（include した block の中の node は `<include の id>__<中の id>`）に書き直し、各筋書きが何を照らすかは変えない。
- 筋書きの宣言（expect・reached・fail-node・resolved-text-contains）は Archon の workflow test で照らす（pack の全部の筋書きを回す層の
  試験 tests/layers/test_block_shape.py の ArchonCase。ここでは回し直さない）
- 宣言で照らせない物（節が走らなかったこと・節の出力の値）は dry-run（exec-code）の trace で照らす。workflow test は節の出力を
  返さないので、筋書きの stub と入力をそのまま `workflow run --dry-run` に渡す（tests/blocks/kit.py の dry_run_traces）
- line の script は本物で回る（dry-run は include の入力を名前の script に渡さず、置き場にファイルを置けないので、判定の控えを
  読む owed・始めの記録を作れない固定材料の start と fix-in だけ stub で差す）
- Archon の源か bun が無ければ tests/archon.py の absent で見送る（CI は赤）

組 B の試験は、ここの line_traces・ran・bound を import して使う。
"""
import json
import re
import unittest

import yaml

from tests.blocks import kit
from tests.blocks.line.test_wiring import would_run

BLOCK = "line"
LINE = kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml"


def nodes() -> dict:
    """line の node の id → node（loop_group の本体の node も含む）"""
    top = yaml.safe_load(LINE.read_text(encoding="utf-8"))["nodes"]
    return {n["id"]: n for n in [*top, *(m for n in top for m in (n.get("loop_group") or {}).get("nodes") or [])]}


def included_blocks(block: str = BLOCK) -> list[str]:
    """block が include する block の名（graph の中の include も辿る）。dry-run の木に一緒に置く"""
    seen: set[str] = set()

    def walk(name: str) -> None:
        doc = yaml.safe_load((kit.BLOCKS / name / f"works-factory-{name}.yaml").read_text(encoding="utf-8"))
        todo = list(doc["nodes"])
        while todo:
            node = todo.pop()
            todo.extend((node.get("loop_group") or {}).get("nodes") or [])
            inner = str(node.get("include", "")).removeprefix("works-factory-")
            if inner and inner not in seen:
                seen.add(inner)
                walk(inner)

    walk(block)
    return sorted(seen)


_TRACES: dict = {}


def line_traces(names) -> dict:
    """筋書きの名 → その筋書きの stub で line を dry-run（exec-code）した trace（node の id → trace の行）。同じ名は 1 度だけ回す"""
    todo = [n for n in names if n not in _TRACES]
    if todo:
        _TRACES.update(kit.dry_run_traces(BLOCK, todo, included=included_blocks()))
    return {n: _TRACES[n] for n in names}


def ran(trace: dict, node: str) -> bool:
    """node が走った（completed か stubbed）か。飛ばされた・落ちた・trace に無い node は偽"""
    return node in trace and trace[node]["state"] in ("completed", "stubbed")


def out(trace: dict, node: str):
    """node の出力（JSON）。受け皿 `<id>-out` の got は `got(trace, id)`"""
    return json.loads(trace[node]["output"])


def got(trace: dict, include: str):
    """include した block の返り（受け皿 `<include>-out` の got。飛んだ受け皿は None）"""
    return out(trace, f"{include}-out")["got"] if ran(trace, f"{include}-out") else None


def bound(trace: dict, value):
    """line の node の with: の 1 つの値を、dry-run の trace の出力で結ぶ（`$<id>.output.<欄>`・まるごとの参照 `$<id>.output` と
    `{from, if_skipped}`。include した block の返りは trace に include の id の行が無いので、受け皿 `<id>-out` の got から読む）"""
    if isinstance(value, dict) and "from" in value:
        node = value["from"].split(".", 1)[0].lstrip("$")
        node = node if node in trace else f"{node}-out"
        if node not in trace or trace[node]["state"] == "skipped":
            return value.get("if_skipped")
        value = value["from"]
    if isinstance(value, str) and value.startswith("$") and value.endswith(".output"):
        node = value[1:-len(".output")]
        if node in trace:
            return trace[node].get("output")
        if f"{node}-out" in trace:
            raw = trace[f"{node}-out"].get("output")
            return json.loads(raw)["got"] if raw else None
    if not (isinstance(value, str) and value.startswith("$") and ".output." in value):
        return value
    node, field = value[1:].split(".output.", 1)
    if node in trace:
        return json.loads(trace[node]["output"]).get(field)
    return (json.loads(trace[f"{node}-out"]["output"])["got"] or {}).get(field)


class LineReturnsTest(unittest.TestCase):
    """line の返り（result）の欄 apply・sealed・r2_status・final_answer・spec_questions（bin/apply と段 1 が読む）を、筋書きの道で照らす"""

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(("standard", "spec-changed", "start-refused"))

    def test_standard_applies_the_sealed_diff(self):
        returned = out(self.traces["standard"], "result")
        self.assertIs(returned["apply"]["ok"], True, returned)
        self.assertEqual(returned["apply"]["hash"], returned["sealed"]["hash"])
        self.assertEqual(returned["r2_status"], "pass")
        self.assertEqual(returned["final_answer"], {"decision": "approve", "text": "", "asked": []})
        self.assertEqual(returned["spec_questions"], 0)

    def test_spec_changed_counts_the_reapproval_questions(self):
        returned = out(self.traces["spec-changed"], "result")
        self.assertEqual(returned["spec_questions"], 1, returned)

    def test_sweep_without_children_reaches_the_return(self):
        """後始末の node は落ちずに返りが line の返りの欄 children に載る。試験の Archon は入口の殻を通らないので、node は何も消さない"""
        children = out(self.traces["standard"], "result")["children"]
        self.assertEqual((children["cleaned"], children["left"]), ([], []))

    def test_start_refused_reaches_the_report(self):
        """入口の拒み: block は全部飛び、報告と返りは走る。結末は stopped_by_line で、止めの語が報告へ渡す事実に載る"""
        trace = self.traces["start-refused"]
        for node in ("gate-start", "test-gate-base", "judge__verdict", "fix__finish", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        for node in ("collect", "report__finish", "sweep-children", "result"):
            self.assertTrue(ran(trace, node), node)
        self.assertEqual(out(trace, "result")["outcome"], "stopped_by_line")
        self.assertEqual(out(trace, "result")["stop_reason"], "start:works:start-refused")

    def test_spec_changed_stop_reaches_the_report(self):
        trace = self.traces["spec-changed"]
        self.assertEqual(out(trace, "result")["outcome"], "needs_human")
        self.assertEqual(out(trace, "result")["stop_reason"], "spec-check-run:works:spec-changed")
        for node in ("test-gate-final__result", "eyes__verdict", "merge-seal__merge", "gate-final"):
            self.assertTrue(ran(trace, node), node)


class SpecDrivenScenariosTest(unittest.TestCase):
    """仕様駆動の道の筋書き spec-driven: 仕様の値（段・目的・道 routes）が修正へ届く。宣言（reached など）は層の試験の workflow test が照らす"""

    def test_spec_run_carries_the_spec_values_to_the_fix(self):
        trace = line_traces(("spec-driven",))["spec-driven"]
        fix_in = out(trace, "fix-in")
        self.assertEqual((fix_in["go"], fix_in["switches"]["tier"], fix_in["purpose_text"]), (True, "標準", "空の列でも mean が落ちない"))
        self.assertEqual(nodes()["fix"]["with"]["routes"], "$start.output.ports.routes")
        self.assertEqual(out(trace, "start")["ports"]["routes"], "plan")


class DefaultDeliverTest(unittest.TestCase):
    """#555: 出口の語を名指さない（既定の空の）run は、差分を置いて止まり、run の枝に積む node と PR を作る子の run の node が走らない"""

    def test_default_run_places_without_the_pr_path(self):
        trace = line_traces(("standard",))["standard"]
        for node in ("merge-apply__place", "merge-apply__merge"):
            self.assertTrue(ran(trace, node), node)
        for node in ("merge-apply__pr-commit", "merge-apply__pr-open", "merge-apply__pr-read",
                     "merge-seal__pr-commit", "merge-seal__pr-open", "merge-seal__pr-read"):
            self.assertFalse(ran(trace, node), node)
        self.assertEqual(got(trace, "merge-apply")["deliver"], {"act": "placed", "pr": None, "reason": ""})


class NoFixRoundTest(unittest.TestCase):
    """L-W07（筋書き no-fix）: 直す物が無い周も周を締める。判定の後に回る独立設計が fix-in を通って独立の目に届き、最後のテストと
    独立の目が走り、差分が無いので封じも当てもしない"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("no-fix",))["no-fix"]

    def test_the_round_is_closed_without_sealing(self):
        fix_in, fixed = out(self.trace, "fix-in"), out(self.trace, "fixed")
        self.assertEqual((fix_in["no_fix"], fixed["no_fix"], fixed["go"]), (True, True, True), (fix_in, fixed))
        self.assertEqual(fix_in["design"]["path"], "independent-design/design.json")
        for node in ("independent-design__finish", "test-gate-final-out", "eyes-out", "eyes__r2__finish", "ask-final", "answer-final"):
            self.assertTrue(ran(self.trace, node), node)
        for node in ("plan-rounds", "fix__finish", "merge-seal-out", "merge-apply-out"):
            self.assertFalse(ran(self.trace, node), node)
        self.assertEqual(out(self.trace, "result")["outcome"], "no_fix_needed")


class FailedBlockTest(unittest.TestCase):
    """block の node（block-failed）・最後の試験の関門の node（test-gate-failed）が落ちた run は、後ろの段が飛んでも collect・report・
    result まで走る（collect が block の返りを直に読むと collect も落ちる）。block が落ちた run は封じも当てもしない。試験の関門が落ちた
    run は試験を緑と数えない: 最後の承認ノードが認証できなかった訳で開き、当ての段へ渡す緑の値が偽のまま（通すのは人の答えだけ）"""

    NAMES = ("block-failed", "test-gate-failed")

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(cls.NAMES)

    def test_the_report_and_the_return_still_run(self):
        for name in self.NAMES:
            with self.subTest(scenario=name):
                trace = self.traces[name]
                for node in ("collect", "report__finish", "result"):
                    self.assertTrue(ran(trace, node), node)
                self.assertEqual(trace["result"]["state"], "completed")

    def test_the_failed_node_is_where_the_scenario_puts_it(self):
        for name, node in (("block-failed", "judge__ins"), ("test-gate-failed", "test-gate-final__run")):
            with self.subTest(scenario=name):
                self.assertEqual(self.traces[name][node]["state"], "failed")

    def test_the_gates_after_the_failure_do_not_open(self):
        for node in ("fix__finish", "merge-seal__merge", "merge-apply__merge", "gate-final"):
            self.assertFalse(ran(self.traces["block-failed"], node), node)

    def test_the_test_gate_still_returns_without_the_run(self):
        trace = self.traces["test-gate-failed"]
        self.assertTrue(ran(trace, "test-gate-final__result"))
        self.assertTrue(ran(trace, "test-gate-final-out"))

    def test_a_fallen_test_gate_is_not_counted_green(self):
        trace = self.traces["test-gate-failed"]
        self.assertEqual((got(trace, "test-gate-final")["ok"], got(trace, "test-gate-final")["red_cause"]), (False, "incomplete"))
        asked = out(trace, "ask-final")
        self.assertEqual((asked["open"], asked["green_ok"]), (True, False), asked)
        self.assertIn("認証できなかった", asked["text"].splitlines()[0])
        self.assertIs(bound(trace, nodes()["merge-apply"]["with"]["green_ok"]), False, "当ての段へ渡す緑の値は偽")


class LightTest(unittest.TestCase):
    """筋書き light: 頭の深さが軽量で全部の単位が軽量のまま、上げ直しの信号が無い。差分の審査・レンズ・独立の目 R1〜R4 を省き、
    直した後の実測だけが回る"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("light",))["light"]

    def test_the_checks_are_omitted(self):
        raised = out(self.trace, "raise")
        self.assertEqual((raised["checks"], raised["eyes_due"]), (False, False), raised)
        self.assertIs(bound(self.trace, nodes()["eyes"]["with"]["run"]), False)
        for node in ("lens__finish", "delta-review__finish", "eyes__r1__finish", "eyes__r2__finish", "eyes__r3__finish", "eyes__r4__finish"):
            self.assertFalse(ran(self.trace, node), node)
        self.assertTrue(ran(self.trace, "eyes__structure-after__finish"))


class FixFixtureGateTest(unittest.TestCase):
    """筋書き fix-fixture-gate（docs/design/line.md の 4.1）: 修正前の承認ノードで止まった写しを名指した人の居る run は、判定と計画を
    回さずに、写しの値の修正前の承認ノード（fixture- の付いた 3 つ）を通ってから修正へ進む。止まらずに写した写しで開かないことは
    tests/blocks/line/test_start.py の StartCase（写しの採り方）が見る"""

    def test_the_gate_reopens_from_the_copy_before_the_fix(self):
        trace = line_traces(("fix-fixture-gate",))["fix-fixture-gate"]
        for node in ("judge__verdict", "plan-rounds", "ask-before-fix", "gate-before-fix", "answer-before-fix"):
            self.assertFalse(ran(trace, node), node)
        for node in ("fixture-ask-before-fix", "fixture-gate-before-fix", "fixture-answer-before-fix", "fix-in", "fix__finish", "collect"):
            self.assertTrue(ran(trace, node), node)
        answered = out(trace, "fixture-answer-before-fix")
        self.assertEqual((answered["go"], answered["answer"]["decision"]), (True, "continue"), answered)


class DirectionStopTest(unittest.TestCase):
    """一言の向きの止め（docs/design/line.md の 2 節の 2・docs/design/answer-direction.md）: 承認ノードの continue に添えた一言が計画と
    逆向きと判定されると、答えの node が go 偽・止めの語 works:answer-redirected・止めた訳を返し、修正へ進まない。差すのは include の中の
    返す node（spec-direction__finish）だけで、答えの node と受け皿と fix-in は本物の script で回る。写しの道が同じ答えの node に届く配線は
    tests/blocks/line/test_wiring.py の DirectionWiringCase が見る"""

    def test_spec_redirected_note_stops_before_the_fix(self):
        trace = line_traces(("spec-direction",))["spec-direction"]
        for node in ("spec-ask-before-fix", "spec-gate-before-fix", "spec-direction-out", "spec-answer-before-fix", "fix-in"):
            self.assertTrue(ran(trace, node), node)
        self.assertIs(got(trace, "spec-direction")["aligned"], False)
        answered = out(trace, "spec-answer-before-fix")
        self.assertEqual((answered["go"], answered["stop_reason"]), (False, "works:answer-redirected"), answered)
        self.assertTrue(answered["reason"].strip(), "止めた訳が空でない")
        self.assertIn("例外を投げる形にして", answered["reason"], "人の一言が訳に入る")
        self.assertIs(out(trace, "fix-in")["go"], False)
        self.assertFalse(ran(trace, "fix__finish"), "修正の節は走らない")
        self.assertTrue(ran(trace, "collect") and ran(trace, "result"))


class EyesBackTest(unittest.TestCase):
    """独立の目から修正の段へ返す輪（筋書き eyes-back）: R1 が最初の目で直しが要ると言い、1 度返した後の目で通る"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("eyes-back",))["eyes-back"]

    def test_r1_fix_needed_returns_once_then_passes(self):
        """修正の段が 1 度返り、2 周目の頭が返さずに抜け、最後の承認ノードと封じと返す node の R2 が最後の周の判定と指紋を読む"""
        trace = self.trace
        first, second = out(trace, "back-1"), out(trace, "back-2")
        self.assertTrue(first["go"], first)
        self.assertEqual([r["items"][0]["text"] for r in first["rows"]], ["同じ内容の写しが残っている"])
        self.assertIn("独立の目 R1: app.py:3: 同じ内容の写しが残っている", first["notes"])
        self.assertFalse(second["go"], second)
        self.assertEqual(second["exit"], "返す物が無い")
        self.assertEqual(len(second["rows"]), 1)
        for node in ("back-1-fix__finish", "back-1-fixed", "back-1-gate__result", "back-1-eyes__verdict", "back-2", "eyes-back"):
            self.assertTrue(ran(trace, node), node)
        for node in ("back-2-fix__finish", "back-2-fixed", "back-2-gate__result", "back-2-eyes__verdict"):
            self.assertFalse(ran(trace, node), node)
        for node in ("back-3", "back-4"):   # 頭は毎周走り、返さなかった周は前の記録を運ぶ
            self.assertEqual({k: out(trace, node)[k] for k in ("go", "exit", "rows")}, {k: second[k] for k in ("go", "exit", "rows")}, node)
        fixed = out(trace, "back-1-fixed")
        self.assertEqual([s["stage"] for s in fixed["stages"]], [1, 2], "返した段が最初の修正の段の次に積まれる")
        self.assertEqual(len(fixed["more"]), 1)
        last = out(trace, "eyes-back")
        self.assertEqual((last["exit"], last["sealable"], last["eyes_ok"], last["green_ok"]), ("返す物が無い", True, True, True))
        self.assertEqual(last["fingerprint"]["diff_hash"], "e" * 64, "最後の周の試験の指紋")
        self.assertEqual(last["eyes"]["r1"]["status"], "pass")
        self.assertTrue(ran(trace, "merge-seal-out"))
        asked = out(trace, "ask-final")
        self.assertEqual(asked["fingerprint"]["diff_hash"], "e" * 64, "封じて当てる値は最後の周の物")
        self.assertIs(asked["eyes_ok"], True)
        self.assertEqual(asked["r2"]["status"], "pass")
        self.assertEqual(out(trace, "result")["r2_status"], "pass")
        self.assertIn("独立の目から修正の段へ 1 回返した", asked["text"])


class NoApplyTest(unittest.TestCase):
    """止まった・落ちた・直す物が無い run（block-failed・no-fix・spec-direction・start-refused）は差分を当てない。修正の前で止まる run は封じもしない。
    when: の句の取り違え（止まった run で後ろの書き込みの段が走る）を、当てない結末の筋書きの全部で照らす（消した YAML の形の試験
    WhenCase・FlowCase の代わり。持ち主の決め mechanism-over-tests）"""

    NEVER_APPLY = ("block-failed", "no-fix", "spec-direction", "start-refused")
    NEVER_SEAL = ("block-failed", "no-fix", "spec-direction", "start-refused")

    def test_no_write_after_a_stop(self):
        traces = line_traces(self.NEVER_APPLY)
        for name in self.NEVER_APPLY:
            with self.subTest(scenario=name):
                trace = traces[name]
                for node in ("merge-apply__place", "merge-apply__merge", "merge-apply__pr-commit", "merge-apply__pr-open"):
                    self.assertFalse(ran(trace, node), node)
                self.assertIsNone(out(trace, "result")["apply"])
                if name in self.NEVER_SEAL:
                    self.assertFalse(ran(trace, "merge-seal__merge"))
                    self.assertIsNone(out(trace, "result")["sealed"])


ROUND_NODE = re.compile(r"back-\d+(?:-.+)?|eyes-back")


def settle(seed: dict, failing: set, go: dict) -> dict:
    """返す輪の節（周の節と集め eyes-back）の結末を、depends_on と trigger_rule（待ち方の模型は test_wiring.would_run の 1 か所）と when で
    求める。結末は would_run の状態の語。seed は輪の外の節（eyes-out など）の結末、failing は走って誤りで落ちる節、go は when の
    `.go == true` が読む節の値"""
    top = nodes()
    state = dict(seed)
    todo = [n for n in top if ROUND_NODE.fullmatch(n)]
    while todo:
        ready = [n for n in todo if all(d in state for d in top[n].get("depends_on") or [])]
        if not ready:
            raise AssertionError(f"待つ先の結末が決まらない節: {todo}")
        for n in ready:
            todo.remove(n)
            deps = [state[d] for d in top[n].get("depends_on") or []]
            if not would_run({**top[n], "depends_on": top[n].get("depends_on") or []}, state):
                state[n] = "skipped_after_failure" if any(d in ("failed", "skipped_after_failure") for d in deps) else "skipped"
                continue
            reads = re.findall(r"\$([\w-]+)\.output\.go == true", top[n].get("when") or "")
            state[n] = "skipped" if not all(go.get(r, False) for r in reads) else "failed" if n in failing else "completed"
    return state


class EyesBackFellTest(unittest.TestCase):
    """独立の目から修正の段へ返す輪で、返した周の修正の段の中の節が誤りで落ちた run（筋書き eyes-back-fell）: 後ろの節は飛ぶが、次の周の頭と
    集めと戻す節と封じと最後の承認ノードは走り、返す前に試験と独立の目を通った状態を封じに出す。待ち方は配線を Archon の決めに当てて確かめ
    （周の頭が 1 つも走らない run では集めが飛んだままなことも）、Archon の源が使える時は筋書きを dry-run した trace も照らす"""

    GO = {"back-1": True}   # 1 周目の頭は返す。返した段の合わせは落ちた段を受けて進めない。ほかの頭は返さない

    def test_internal_error_in_the_returned_stage_seals_the_state_before_the_return(self):
        fell = settle({"eyes-out": "completed"}, {"back-1-fix"}, self.GO)
        self.assertEqual(fell["back-1-fix"], "failed")
        for node in ("back-1-gate", "back-1-eyes"):
            self.assertNotEqual(fell[node], "completed", f"{node} は落ちた修正の段の後ろなので走らない")
        for node in ("back-1-fixed", "back-2", "back-3", "back-4", "eyes-back"):
            self.assertEqual(fell[node], "completed", f"{node} は落ちた周の後ろでも走る")
        stopped = settle({"eyes-out": "skipped"}, set(), self.GO)
        self.assertEqual({n: s for n, s in stopped.items() if s == "completed"}, {}, "周の頭が 1 つも走らない run では集めも飛ぶ")
        try:
            trace = line_traces(("eyes-back-fell",))["eyes-back-fell"]
        except unittest.SkipTest:
            return
        self.assertEqual(trace["back-1-fix__finish"]["state"], "failed")
        for node in ("back-1-gate__result", "back-1-eyes__verdict"):
            self.assertFalse(ran(trace, node), f"{node} は落ちた修正の段の後ろなので走らない")
        for node in ("back-2", "eyes-back", "eyes-back-restore", "merge-seal__merge", "ask-final", "gate-final", "collect", "result"):
            self.assertTrue(ran(trace, node), node)
        first, second = out(trace, "back-1"), out(trace, "back-2")
        self.assertTrue(first["go"], first)
        self.assertFalse(second["go"], second)
        self.assertTrue(second["exit"].startswith("修正の段"), second["exit"])
        last = out(trace, "eyes-back")
        self.assertTrue(last["sealable"], last)
        self.assertEqual(last["checkpoint"]["round"], 1)
        self.assertEqual(last["checkpoint"]["tree"], first["rows"][-1]["tree"])
        self.assertEqual(last["fingerprint"], out(trace, "test-gate-final-out")["got"]["fingerprint"], "封じる指紋は返す前の試験の物")
        asked = out(trace, "ask-final")
        self.assertIn("封じに出したのは 1 周目に返す前の状態", asked["text"])
        self.assertIn("返したが直せなかった項目", asked["text"])


if __name__ == "__main__":
    unittest.main()
