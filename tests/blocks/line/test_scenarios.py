"""line の筋書きの組 A（workflows/line/fixtures/*.stubs.yaml の 17 本）の試験（docs/design/README.md の 11.3 の 2、line.md の 11 節）。

元は今の tests/e2e/test_line_scenarios.py と tests/workflows/test_line.py の筋書きの場面。筋書きを新しい line の node の id
（include した block の中の node は `<include の id>__<中の id>`）に書き直し、各筋書きが何を照らすかは変えない。
- 筋書きの宣言（expect・reached・fail-node・resolved-text-contains）は Archon の workflow test で照らす（ScenariosCase）
- 宣言で照らせない物（節が走らなかったこと・節の出力の値）は dry-run（exec-code）の trace で照らす。workflow test は節の出力を
  返さないので、筋書きの stub と入力をそのまま `workflow run --dry-run` に渡す（tests/blocks/kit.py の dry_run_traces）
- line の script は本物で回る（dry-run は include の入力を名前の script に渡さず、置き場にファイルを置けないので、判定の控えを
  読む owed・始めの記録を作れない固定材料の start と fix-in だけ stub で差す）
- Archon の源か bun が無ければ tests/archon.py の absent で見送る（CI は赤）

組 B の試験は、ここの line_traces・ran・bound を import して使う。
"""
import json
import pathlib
import unittest

import yaml

from tests import archon
from tests.blocks import kit

BLOCK = "line"
LINE = kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml"
SCENARIOS = (
    "block-failed", "block-returns-failed", "conflict-ask", "depth-heavy", "depth-light", "depth-no-evidence", "depth-raised",
    "fix-excluded", "fix-fixture", "light", "light-all-units", "no-fix", "nothing-owed", "plan-failed", "plan-stalled", "spec-changed", "standard",
    "start-refused", "test-gate-failed",
)


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


def line_results() -> dict:
    """筋書きの名 → workflow test の 1 件の結果"""
    with archon.blocks_tree([BLOCK, *included_blocks()]) as tree:
        done = archon.archon(tree, "workflow", "test", f"works-factory-{BLOCK}", "--cwd", str(tree), "--json")
        try:
            report = json.loads(done.stdout)
        except json.JSONDecodeError as error:
            raise AssertionError(f"workflow test の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
        if "results" not in report:
            raise AssertionError(f"workflow test が筋書きを回せない: {json.dumps(report, ensure_ascii=False)}")
        return {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r for r in report["results"]}


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


class ScenariosCase(unittest.TestCase):
    """筋書きの宣言（expect・reached・fail-node・resolved-text-contains）が全部通る"""

    @classmethod
    def setUpClass(cls):
        cls.results = line_results()

    def test_every_scenario_is_declared(self):
        self.assertFalse(set(SCENARIOS) - set(self.results), "筋書きが無い")

    def test_every_scenario_passes(self):
        for name in SCENARIOS:
            with self.subTest(scenario=name):
                got_ = self.results.get(name)
                self.assertIsNotNone(got_, f"筋書き {name} が無い")
                self.assertTrue(got_["pass"], json.dumps(got_, ensure_ascii=False))


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


# 仕様駆動の道だけで回る node（docs/design/spec-driven.md の 6.2 の足す node）。include の中の node は `<id>__<中の id>`。前からの
# spec-check-run（仕様の段の照らし）は仕様駆動の道の node でないので、頭の字でなく id で名指す
SPEC_DRIVEN_NODES = ("spec-entry", "spec-entry-out", "spec-diagnose", "spec-diagnose-out", "spec-plan", "spec-plan-out", "spec-check",
                     "spec-check-out", "spec-rounds", "spec-ask-before-fix", "spec-gate-before-fix", "spec-answer-before-fix")
# 仕様駆動の道の筋書き（docs/design/spec-driven.md の 6.5 の 7 と 8）
SPEC_SCENARIOS = ("spec-driven", "spec-refused", "spec-mismatch", "spec-gate", "spec-unattended")


def touched(trace: dict, node: str) -> bool:
    """node が走りかけた（trace に在り、飛ばされていない）か。落ちた node も走ったと読む（走っていないのは state が無いか skipped だけ）"""
    return node in trace and trace[node]["state"] != "skipped"


def spec_driven_ran(trace: dict) -> list:
    """trace で走りかけた仕様駆動の道の node（落ちた node も数える）"""
    return sorted(n for n in trace if touched(trace, n) and any(n == s or n.startswith(f"{s}__") for s in SPEC_DRIVEN_NODES))


class RequestRunsStayTest(unittest.TestCase):
    """依頼の文・差分・固定材料で入る筋書き（組 A の全部）は、仕様駆動の道の node を 1 つも走らせず、直す前の結末が通った run では
    今の判定（graph judge）を回す（docs/design/spec-driven.md の 6.5 の 2。仕様駆動の道を足しても本線の振る舞いが変わらない縛り）"""

    def test_no_spec_driven_node_runs_and_the_judge_runs(self):
        for name, trace in line_traces(SCENARIOS).items():
            with self.subTest(scenario=name):
                self.assertEqual(spec_driven_ran(trace), [])
                base_ok = (got(trace, "test-gate-base") or {}).get("ok") is True
                self.assertEqual(touched(trace, "judge__ins"), base_ok)   # 判定の graph の頭の node（落ちる筋書きも在る）


class SpecDrivenScenariosTest(unittest.TestCase):
    """仕様駆動の道の筋書き（SPEC_SCENARIOS）。宣言（reached など）は ScenariosCase と同じく workflow test で照らし、ここは trace で
    走らなかった node と値を照らす"""

    @classmethod
    def setUpClass(cls):
        cls.results = line_results()
        cls.traces = line_traces(SPEC_SCENARIOS)

    def test_every_spec_scenario_passes(self):
        for name in SPEC_SCENARIOS:
            with self.subTest(scenario=name):
                got_ = self.results.get(name)
                self.assertIsNotNone(got_, f"筋書き {name} が無い")
                self.assertTrue(got_["pass"], json.dumps(got_, ensure_ascii=False))

    def test_spec_runs_skip_the_judge_graph_and_the_plan_rounds(self):
        for name, trace in self.traces.items():
            with self.subTest(scenario=name):
                for node in ("judge__ins", "plan-rounds", "ask-before-fix", "gate-before-fix", "answer-before-fix", "owed"):
                    self.assertFalse(touched(trace, node), node)

    def test_refused_spec_run_wakes_no_ai(self):
        """入口の確かめで止まった run は試験の段（中に AI の段を持つ）・判定の役・計画の部品へ届かない"""
        trace = self.traces["spec-refused"]
        for node in ("test-gate-base__intake", "spec-diagnose__intake", "spec-plan__intake", "fix__intake"):
            self.assertFalse(ran(trace, node), node)
        self.assertIs(out(trace, "fix-in")["go"], False, "fix-in はどの run でも回り、修正へ進まない値を返す")
        self.assertEqual(out(trace, "result")["stop_reason"], "spec-entry:works:spec-entry")

    def test_spec_run_carries_the_spec_values_to_the_fix(self):
        trace = self.traces["spec-driven"]
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


class EyesInputsTest(unittest.TestCase):
    """筋書き standard で独立の目に修正役の規模の数値（x_scalars）が届く。dry-run は include の入力を名前の script に渡さないので、
    筋書きが include の with: に結んだ値を trace から引いて照らす"""

    def test_eyes_get_the_fix_x_scalars(self):
        trace = line_traces(("standard",))["standard"]
        self.assertEqual(bound(trace, nodes()["eyes"]["with"]["x_scalars"]), {"x_moved_lines": 3})


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


class NothingOwedRoundTest(unittest.TestCase):
    """#291（筋書き nothing-owed）: 計画の直す義務が 0 件の周も修正前の承認ノード・修正を飛ばしたまま、独立設計・fixed の直す物の無い形・
    最後のテスト・独立の目で周を締め、目の阻害が結末に届く"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("nothing-owed",))["nothing-owed"]

    def test_the_tail_runs_like_works(self):
        fix_in, fixed = out(self.trace, "fix-in"), out(self.trace, "fixed")
        self.assertEqual((fix_in["no_fix"], fixed["no_fix"], fixed["go"]), (True, True, True), (fix_in, fixed))
        for node in ("plan-rounds", "independent-design-out", "test-gate-final-out", "eyes-out", "ask-final"):
            self.assertTrue(ran(self.trace, node), node)
        for node in ("fix__finish", "merge-seal-out", "merge-apply-out", "plan-review-run__finish", "structure__finish"):
            self.assertFalse(ran(self.trace, node), node)
        self.assertEqual(got(self.trace, "eyes")["r2"]["status"], "redesign-needed")
        self.assertEqual(out(self.trace, "result")["outcome"], "round_limit")


class PlanStopTest(unittest.TestCase):
    """計画の往復が止まった姿（plan-stalled）は往復を抜けて、修正前の承認ノードが必ず開く。止まりの決めと止まった理由の文は往復の記録の
    ファイルを読む plan-out が持ち、dry-run の置き場には無いので、plan-out の返りを止まりの値（stalled と事前審査が諦めた印）で差す。
    上限の周（旧 plan-unsettled。止まった理由の文が記録のファイルから組まれる）は筋書きで届かず、tests/blocks/line/test_rounds.py と
    test_gates.py が見る（line.md の 3 節）"""

    def test_stalled_round_opens_the_gate_before_fix(self):
        trace = line_traces(("plan-stalled",))["plan-stalled"]
        asked = out(trace, "ask-before-fix")
        self.assertIs(asked["open"], True, asked)
        self.assertIn("事前審査の受け付けが諦めた: ", asked["text"])
        for node in ("plan-out", "gate-before-fix", "answer-before-fix", "fix__finish"):
            self.assertTrue(ran(trace, node), node)


class FailedBlockTest(unittest.TestCase):
    """block の node・返す node・計画の往復の中の node・最後の試験の関門の node が落ちた run は、後ろの段が飛んでも collect・report・
    result まで走る（collect が block の返りを直に読むと collect も落ちる）"""

    NAMES = ("block-failed", "block-returns-failed", "plan-failed", "test-gate-failed")

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
        for name, node in (("block-failed", "judge__ins"), ("block-returns-failed", "judge__verdict"), ("plan-failed", "plan__intake"),
                           ("test-gate-failed", "test-gate-final__run")):
            with self.subTest(scenario=name):
                self.assertEqual(self.traces[name][node]["state"], "failed")

    def test_the_gates_after_the_failure_do_not_open(self):
        for name in ("block-failed", "block-returns-failed", "plan-failed"):
            with self.subTest(scenario=name):
                for node in ("fix__finish", "merge-seal__merge", "merge-apply__merge", "gate-final"):
                    self.assertFalse(ran(self.traces[name], node), node)

    def test_the_test_gate_still_returns_without_the_run(self):
        trace = self.traces["test-gate-failed"]
        self.assertTrue(ran(trace, "test-gate-final__result"))
        self.assertTrue(ran(trace, "test-gate-final-out"))


def tiers_table():
    """段の表（段 → 省く物・足す物）。line の src/tiers.py の TIERS（lib/depth.py は組み込みで消えた）"""
    return kit.load(BLOCK, "tiers")


class HeadDepthTest(unittest.TestCase):
    """run の頭の深さ（issue #441・#561）: 計画の壁打ち（plan と plan-review の往復）はどの深さでも省かない。頭が軽量・重厚・標準の
    どの筋書きでも事前審査の輪が走って報告まで届き、事前審査の輪を飛ばす node（plan-review-due）は line に無い。判定の段の語は
    tiers に届き、省く物と足す物が段ごとに違う（軽量は省く物、重厚は足した物と事前審査の木 on）"""

    LOOP = "review-accept"   # 事前審査の輪の本体の node は include の id の頭が付かない
    NAMES = ("depth-light", "depth-raised", "depth-heavy", "depth-no-evidence")

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(cls.NAMES)

    def test_light_head_runs_the_review_loop(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                trace = self.traces[name]
                self.assertTrue(ran(trace, self.LOOP))
                self.assertNotIn("plan-review-due", trace)
                self.assertTrue(ran(trace, "report__finish"))

    def test_the_head_reaches_what_it_omits_and_adds(self):
        table = tiers_table()
        for name, head, omits, tree in (("depth-light", table.LIGHT, True, "off"), ("depth-heavy", table.HEAVY, False, "on"),
                                        ("depth-no-evidence", table.STANDARD, False, "auto")):
            with self.subTest(name=name):
                tiers = out(self.traces[name], "tiers")
                self.assertEqual((tiers["tier"], tiers["omits"], tiers["tree"]), (head, omits, tree), tiers)
                lines = "\n".join(tiers["lines"])
                for said in (table.TIERS[head]["omits"] if omits else table.tier_adds(head)):
                    self.assertIn(said, lines)

    def test_a_stopped_unit_raises_the_light_head(self):
        """軽量の頭でも、1 回目の修正が止めた単位は標準へ上がり、差分の審査と独立の目を回す"""
        raised = out(self.traces["depth-raised"], "raise")
        self.assertIs(raised["checks"], True, raised)
        self.assertIs(raised["eyes_due"], True, raised)
        self.assertTrue(raised["raised"], raised)


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
        for node in ("lens__finish", "delta-review__finish", "eyes__r1__finish", "eyes__r4__finish"):
            self.assertFalse(ran(self.trace, node), node)
        self.assertTrue(ran(self.trace, "eyes__structure-after__finish"))


class LightAllUnitsTest(unittest.TestCase):
    """line.md 11 節の light-all-units: 全部の単位が軽量の周は lens・delta-review・r1〜r4 が飛び、structure after は走る"""

    def test_only_the_structure_after_runs(self):
        trace = line_traces(("light-all-units",))["light-all-units"]
        for node in ("lens__finish", "delta-review__finish", "eyes__r1__finish", "eyes__r2__finish", "eyes__r3__finish", "eyes__r4__finish"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "eyes__structure-after__finish"))
        self.assertIs(bound(trace, nodes()["eyes"]["with"]["run"]), False)


class FixExcludedTest(unittest.TestCase):
    """line.md 11 節の fix-excluded（4.5 の fix の excluded）: 並行 PR が外した hunk の控えが fix-in を通って fix に届き、2 度目の修正
    （refix-run）にも同じ値が配られる。fix の受け付けが外した hunk に触れた修正を拒むのは fix の block の筋書きが見る"""

    POINTER = {"type": "archon_artifact", "run_id": "dry-run", "path": "parallel-pr/pr-excluded.json"}

    def test_excluded_reaches_fix_and_refix(self):
        trace = line_traces(("fix-excluded",))["fix-excluded"]
        self.assertEqual(out(trace, "fix-in")["excluded"], self.POINTER)
        self.assertEqual(bound(trace, nodes()["fix"]["with"]["excluded"]), self.POINTER)
        self.assertEqual(nodes()["refix-run"]["with"]["excluded"], nodes()["fix"]["with"]["excluded"])


class ConflictGateTest(unittest.TestCase):
    """筋書き conflict-ask の最後の承認ノード（L-W24・F426）: 申し出の控えは dry-run の置き場に無いので、ask-final は読めない控えを
    名指して protected_only でも開く（黙って 0 にしない）。裁定の中身で開くかは ask-final の試験（tests/blocks/line/test_gates.py）"""

    def test_unreadable_conflicts_open_and_are_named_in_the_scenario(self):
        trace = line_traces(("conflict-ask",))["conflict-ask"]
        asked = out(trace, "ask-final")
        self.assertTrue(asked["open"], asked)
        self.assertIn("食い違いの申し出の控えを読めない（1 件。", asked["text"].splitlines()[0])
        self.assertTrue(ran(trace, "gate-final") and ran(trace, "merge-apply__merge"))


class FixFixtureTest(unittest.TestCase):
    """#509（筋書き fix-fixture）: 固定材料を名指した run は、判定と修正案の役を起こさずに修正から始まる。直す前のテスト・判定・
    計画の往復・修正前の承認ノードが走らず、修正から後ろが走る"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("fix-fixture",))["fix-fixture"]

    def test_roles_start_from_the_fix(self):
        for node in ("test-gate-base__result", "judge__verdict", "structure__finish", "plan-rounds", "plan__finish", "ask-before-fix",
                     "gate-before-fix", "answer-before-fix"):
            self.assertFalse(ran(self.trace, node), node)
        for node in ("gate-start", "fix-in", "fix__finish", "fixed", "judged", "test-gate-final__result", "eyes__verdict", "collect"):
            self.assertTrue(ran(self.trace, node), node)

    def test_spec_check_does_not_run_without_a_spec_stage(self):
        """固定材料の run は仕様の段と組めない（spec は偽）ので、仕様の照らしの block は飛ぶ"""
        self.assertFalse(ran(self.trace, "spec-check-run__finish"))


if __name__ == "__main__":
    unittest.main()
