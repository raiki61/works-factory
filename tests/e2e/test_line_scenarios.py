"""線 works-factory-line の筋書き（workflows/line/fixtures/*.stubs.yaml）を、止めた Archon の `workflow test` で回す。

木は tests/archon.py の使い捨ての木に、線と .shared/ と、線が差し込む本物のブロックを置いた物。筋書きは本物のブロックの節の id
（例 test-gate-base__run）に stub を置き、本物の返す節の output_format に合う値で差す。
筋書きは exec-code: true で、stub の無い線の script は本当に走る。dry-run の制約と stub の置き方は docs/design.md の U3。
Archon の源か bun が無ければ名前つきで見送る。
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml

from bin._lib import place
from tests import archon
from tests.layers import scan

if str(archon.ROOT / "lib") not in sys.path:
    sys.path.append(str(archon.ROOT / "lib"))
import fixbeside  # noqa: E402  （diff の隣の控えの名の持ち主）
import fixboard  # noqa: E402

SCENARIOS = (
    "standard", "start-refused", "no-fix", "policy-continue", "policy-stop", "plan-stalled", "plan-unsettled", "replan",
    "rejudge", "light", "final-stop", "final-when-needed-green", "conflict-ask", "unattended-needs-human", "block-failed",
    "replan-stop", "plan-failed", "block-returns-failed", "replan-answers", "test-gate-failed", "rejudge-stop",
    "unattended-questions", "unattended-policy-change", "eyes-failed-protected", "refix-handoff",
    "nothing-owed", "spec-changed", "depth-light", "depth-raised", "depth-no-evidence",
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
    """筋書きの名 → その筋書きの stub で線を dry-run（exec-code）した trace（節の id → trace の行）"""
    return dry_run_traces("line", archon.PACK["ours"]["line"], ["line", *blocks()], names)


def dry_run_traces(folder: str, workflow: str, placed, names) -> dict:
    """筋書きの名 → workflows/<folder>/fixtures/ のその筋書きの stub でグラフ workflow を dry-run（exec-code）した trace（ノードの id →
    trace の行）。木には placed のフォルダを置く。workflow test はノードの出力を返さないので、筋書きの stub と入力をそのまま
    `workflow run --dry-run` に渡す（tests/workflows/test_report.py と同じ形）"""
    out = {}
    with archon.tree(placed) as tree:
        for name in names:
            fixture = yaml.safe_load((archon.WORKFLOWS / folder / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))
            stubs = tree.parent / f"{name}.stubs.yaml"
            stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")},
                                            allow_unicode=True), encoding="utf-8")
            args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
            done = archon.archon(tree, "workflow", "run", workflow, "--dry-run", "--exec-code", "--stubs", str(stubs),
                                 "--json", *args, "--cwd", str(tree))
            try:
                # 落ちた dry-run は trace の後ろに {ok: false, error} を足して出すので、頭の 1 つの JSON だけを読む
                out[name] = {n["nodeId"]: n for n in json.JSONDecoder().raw_decode(done.stdout.lstrip())[0]["trace"]}
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
    """線の返り（result）の欄 apply・sealed・r2_status・final_answer・spec_questions（bin/apply と段 1 が読む）を、筋書きの道で照らす"""

    @classmethod
    def setUpClass(cls):
        cls.returns = line_returns(("standard", "final-stop", "rejudge-stop", "spec-changed"))

    def test_standard_applies_the_sealed_diff(self):
        got = self.returns["standard"]
        self.assertIs(got["apply"]["ok"], True, got)
        self.assertEqual(got["apply"]["hash"], got["sealed"]["hash"])
        self.assertEqual(got["r2_status"], "pass")
        self.assertEqual(got["final_answer"], {"decision": "approve", "text": "", "asked": []})
        self.assertEqual(got["spec_questions"], 0)

    def test_spec_changed_counts_the_reapproval_questions(self):
        self.assertEqual(self.returns["spec-changed"]["spec_questions"], 1, self.returns["spec-changed"])

    def test_sweep_without_children_reaches_the_return(self):
        """後始末の節は写した工程のフォルダから部品 childsweep まで届き、落ちずに返りが線の返りの欄 children に載る。試験の Archon は
        入口の殻を通さない（tests/archon.py が源のパスを継がない）ので、節は何も消さず、訳に源のパスの環境変数の名を書く"""
        children = self.returns["standard"]["children"]
        self.assertEqual((children["cleaned"], children["left"]), ([], []))
        self.assertIn(place.SOURCE_ENV, children["error"])

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


class ProtectedNotAppliedTest(unittest.TestCase):
    """L-G50: 独立の目のブロックが落ち、目の守りのパスの照らしが当たりを返した run は、最後の関所が開かない（封じる段から先が飛ぶ）
    まま差分を当てない（merge-apply に届かない）。報告と線の返りは出る"""

    def test_eyes_failed_with_protected_hits_never_applies(self):
        trace = line_traces(("eyes-failed-protected",))["eyes-failed-protected"]
        ran = UnattendedGateTest.ran
        self.assertTrue(ran(trace, "eyes__protected"))
        for node in ("merge-seal__merge", "ask-final", "gate-final", "answer-final", "merge-apply__merge"):
            self.assertFalse(ran(trace, node), node)
        self.assertTrue(ran(trace, "report__report"))
        self.assertIsNone(json.loads(trace["result"]["output"])["apply"])


class HeadDepthTest(unittest.TestCase):
    """run の頭の深さ（issue #441）: 軽量の run は表のノード（事前審査の輪）が skipped になり報告まで届く。走っている間に上げる信号
    （計画の単位に標準）が出た run と、根拠が引けず判定が標準を返した run は、輪が走る。筋書きの宣言は節が走らなかったことを照らせない
    ので、dry-run の trace で照らす"""

    LOOP = "plan-review-run__review-loop"

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(("depth-light", "depth-raised", "depth-no-evidence"))

    def due(self, name) -> dict:
        return json.loads(self.traces[name]["plan-review-due"]["output"])

    def test_light_run_skips_the_listed_node_and_reports(self):
        trace = self.traces["depth-light"]
        due = self.due("depth-light")
        self.assertIs(due["skip"], True, due)
        self.assertEqual(trace[self.LOOP]["state"], "skipped")
        self.assertIs(json.loads(trace["fixed"]["output"])["review_skipped"], True)
        self.assertTrue(UnattendedGateTest.ran(trace, "report__report"))

    def test_raised_run_runs_the_loop(self):
        due = self.due("depth-raised")
        self.assertEqual((due["skip"], due["why"]), (False, "計画の単位がすべて軽量ではない"), due)
        self.assertEqual(self.traces["depth-raised"][self.LOOP]["state"], "completed")

    def test_unproven_request_is_standard_and_runs_the_loop(self):
        due = self.due("depth-no-evidence")
        self.assertEqual((due["skip"], due["why"]), (False, ""), due)
        self.assertEqual(self.traces["depth-no-evidence"][self.LOOP]["state"], "completed")
        self.assertIs(json.loads(self.traces["depth-no-evidence"]["fixed"]["output"])["review_skipped"], False)


def bound(trace: dict, value):
    """線の節の with: の 1 つの値を、dry-run の trace の出力で結ぶ（`$<id>.output.<欄>` と `{from, if_skipped}`。差し込んだブロックの
    返りは trace に include の id の行が無いので、受け皿 `<id>-out` の got から読む）"""
    if isinstance(value, dict) and "from" in value:
        node = value["from"].split(".", 1)[0].lstrip("$")
        node = node if node in trace else f"{node}-out"   # 差し込んだブロックは受け皿の行で見る
        if node not in trace or trace[node]["state"] == "skipped":
            return value.get("if_skipped")
        value = value["from"]
    if isinstance(value, str) and value.startswith("$") and value.endswith(".output") and value[1:-len(".output")] in trace:
        return trace[value[1:-len(".output")]].get("output")   # 節の出力の丸ごと（関所の答えの字）
    if not (isinstance(value, str) and value.startswith("$") and ".output." in value):
        return value
    node, field = value[1:].split(".output.", 1)
    if node in trace:
        return json.loads(trace[node]["output"]).get(field)
    return (json.loads(trace[f"{node}-out"]["output"])["got"] or {}).get(field)


def rerun(trace: dict, node: str, artifacts: pathlib.Path, run_id: str) -> dict:
    """線の script の節 node を、dry-run が結んだのと同じ with: の値で、置き場 artifacts と run の id を替えて走らせ直した返り（dry-run は
    置き場にファイルを置けないので、stub の指し札の先を試験が置いて読ませる）"""
    with_ = {n["id"]: n for n in yaml.safe_load(LINE.read_text(encoding="utf-8"))["nodes"]}[node]
    env = {**os.environ, "ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": run_id}
    for key, value in with_["with"].items():
        got = bound(trace, value)
        env[f"INPUTS_{key.upper()}"] = got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)
    script = archon.WORKFLOWS / "line" / "scripts" / f"{with_['script']}.py"
    done = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, cwd=artifacts)
    return json.loads(done.stdout)


LINE = archon.WORKFLOWS / "line" / "works-factory-line.yaml"


def place_beside(artifacts: pathlib.Path, diff: dict) -> None:
    """修正の段の diff のポインタ diff の隣に、何も残っていない段の控え（閉鎖の表・差分の審査の穴・受け付けの行・レンズの集め役・許した
    テストの変更の訳。lib/fixbeside.py の FILES と fixboard の名）を置く。dry-run の置き場には無いので、走らせ直す試験が置く"""
    folder = (artifacts / diff["path"]).parent
    folder.mkdir(parents=True, exist_ok=True)
    for name, doc in ((fixbeside.CLOSURE_FILE, {"rows": [], "claimed": []}), (fixbeside.DELTA_HOLES_FILE, {}),
                      (fixboard.ACCEPT_TRACE_FILE, []), (fixboard.LENSES_FILE, {"collector": {"ok": True, "reason": ""}}),
                      (fixboard.ALLOWED_TESTS_FILE, [])):
        (folder / name).write_text(json.dumps(doc), encoding="utf-8")


class ConflictGateTest(unittest.TestCase):
    """筋書き conflict-ask の最後の関所（L-W24・F426。部分 B2 の受け入れ）: 申し出は人に回した行（ask_human・諦めた fix_plan_item）
    だけを数え、裁定が直す裁定だけなら protected_only の関所は開かず、ask_human の行が 1 つ在れば開いて文にその行が出る。dry-run は
    置き場にファイルを書けず（止めた Archon の packages/workflows/src/dry-run.ts 614・798 行）、run の id も dry-run（同 791 行）なので、
    stub の conflicts.json の指し札は筋書きの中では読めない: 筋書きでは読めない控えを名指して開くことを照らし、裁定の中身で開くかは、
    筋書きが ask-final に結んだ値のまま script を走らせ直し、指し札の先に控えを置いて照らす"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("conflict-ask",))["conflict-ask"]

    def ask_final(self, *decisions) -> dict:
        ptr = bound(self.trace, "$fixed.output.conflicts")[0]
        rows = [{"id": f"c{i}", "unit_key": "u1", "between": ["stats.py:3", "test_stats.py:2"], "why_both_cannot_hold": "両方は立たない",
                 "which_is_right": "unknown", "kind": "needs_context",
                 "ruling": {"decision": d, "text": f"裁定の文 {i}（{d}）", "limits": []}} for i, d in enumerate(decisions, 1)]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / ptr["path"]
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
            for diff in bound(self.trace, "$fixed.output.diffs"):
                place_beside(pathlib.Path(tmp), diff)
            return rerun(self.trace, "ask-final", pathlib.Path(tmp), ptr["run_id"])

    def test_unreadable_conflicts_open_and_are_named_in_the_scenario(self):
        got = json.loads(self.trace["ask-final"]["output"])
        self.assertTrue(got["open"], got)
        self.assertIn("食い違いの申し出の控えを読めない（1 件。", got["text"].splitlines()[0])

    def test_fix_rulings_only_keep_the_gate_shut(self):
        got = self.ask_final("fix_code_as", "fix_test_scope")
        self.assertEqual((got["open"], got["go"]), (False, True), got)

    def test_one_asked_row_opens_and_is_shown(self):
        got = self.ask_final("fix_code_as", "ask_human")
        self.assertTrue(got["open"], got)
        self.assertIn("食い違いの申し出を人に回した（1 件）", got["text"].splitlines()[0])
        self.assertIn("- u1: 裁定の文 2（ask_human）（名指し stats.py:3, test_stats.py:2・種類 needs_context・", got["text"])
        self.assertNotIn("裁定の文 1", got["text"])


class RefixHandoffTest(unittest.TestCase):
    """部分 D2 の受け入れ（筋書き refix-handoff。L-W20・F427・R23）: 1 回目と 2 度目の修正の段の修正役が人に回した物（壊すと分かって
    通した理由。fix の出力 handoffs）を fixed が合わせて渡すと、開き方 when_needed でも最後の関所が開き、1 行目に件数、節に 1 件 1 行で
    出る。dry-run は置き場にファイルを書けない（ConflictGateTest と同じ訳）ので、筋書きでは読めない控えも開けた理由に並ぶ。受け入れた
    壊れだけで開くかは、筋書きが ask-final に結んだ値のまま、両方の段の diff の隣に控えを置いて script を走らせ直して照らす"""

    ROWS = "- u1: 壊すと分かって通した——段 1 で既定が変わる\n- u1: 壊すと分かって通した——段 2 で既定が変わる"

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("refix-handoff",))["refix-handoff"]

    def test_scenario_opens_with_both_stages_rows(self):
        got = json.loads(self.trace["ask-final"]["output"])
        self.assertTrue(got["open"], got)
        self.assertEqual(len(bound(self.trace, "$fixed.output.diffs")), 2, "1 回目と 2 度目の修正の diff")
        self.assertIn("修正役が人に回した物が在る（2 件）", got["text"].splitlines()[0])
        self.assertIn(self.ROWS, got["text"])

    def test_accepted_breaks_alone_open_the_gate(self):
        diffs = bound(self.trace, "$fixed.output.diffs")
        with tempfile.TemporaryDirectory() as tmp:
            for ptr in diffs:
                place_beside(pathlib.Path(tmp), ptr)
            got = rerun(self.trace, "ask-final", pathlib.Path(tmp), diffs[0]["run_id"])
        self.assertEqual((got["open"], got["reasons"]), (True, ["修正役が人に回した物が在る（2 件）"]), got)
        self.assertIn(self.ROWS, got["text"])


class NoFixRoundTest(unittest.TestCase):
    """L-W07（筋書き no-fix）: 直す物が無い周も周を締める。独立設計だけを作る差し込み design-only の設計が fixed を通って独立の目に
    届き、最後のテストと独立の目が走り、差分が無いので封じも当てもせず、報告は design-only の返りを事前審査の欄で読む"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("no-fix",))["no-fix"]

    @staticmethod
    def ran(trace, node) -> bool:
        return node in trace and trace[node]["state"] != "skipped"

    def test_the_round_is_closed_without_sealing(self):
        got = json.loads(self.trace["fixed"]["output"])
        self.assertEqual((got["no_fix"], got["go"], got["design"]["path"]), (True, True, "plan-review/design.json"), got)
        for node in ("test-gate-final-out", "eyes-out", "ask-final"):
            self.assertTrue(self.ran(self.trace, node), node)
        for node in ("plan-rounds", "fix", "merge-seal-out", "merge-apply-out"):
            self.assertFalse(self.ran(self.trace, node), node)
        collected = json.loads(self.trace["collect"]["output"])
        self.assertEqual((collected["fix"], collected["plan_review"]["design"]["path"]), (None, "plan-review/design.json"))


class NothingOwedRoundTest(unittest.TestCase):
    """#291（筋書き nothing-owed。元 works/darkfactory/lib/line_edge.py:1109-1114 の空の修正）: 計画の直す義務が 0 件の周も修正前の
    関所・修正を飛ばしたまま、design-only・fixed の直す物の無い形・最後のテスト・独立の目で周を締め、目の阻害が collect に届く"""

    @classmethod
    def setUpClass(cls):
        cls.trace = line_traces(("nothing-owed",))["nothing-owed"]

    def test_the_tail_runs_like_works(self):
        ran = NoFixRoundTest.ran
        got = json.loads(self.trace["fixed"]["output"])
        self.assertEqual((got["no_fix"], got["go"], got["design"]["path"]), (True, True, "plan-review/design.json"), got)
        for node in ("plan-rounds", "design-only-out", "test-gate-final-out", "eyes-out", "ask-final"):
            self.assertTrue(ran(self.trace, node), node)
        for node in ("fix", "merge-seal-out", "merge-apply-out"):
            self.assertFalse(ran(self.trace, node), node)
        collected = json.loads(self.trace["collect"]["output"])
        self.assertEqual((collected["fix"], collected["plan_review"]["design"]["path"], collected["eyes"]["r2"]["status"]),
                         (None, "plan-review/design.json", "redesign-needed"))


class RefixInputsTest(unittest.TestCase):
    """部分 D1 の受け入れ: 筋書き replan で 2 度目の修正（refix-run）に 1 回目の申し出と裁定（prior_conflicts）・案の直しの事前審査の
    返り（plan_review）・機械の申し送り（notes）・直す項目の JSON の配列（only_items。S44）が届き、筋書き standard で独立の目に
    修正役の規模の数値（x_scalars）が届く。dry-run は include の入力を名前の script に渡さず（docs/design.md の U3。止めた Archon の
    packages/workflows/src/dry-run.ts 757-766 行）、resolved-text-contains は script の節の with: を写さないので、筋書きが include の
    with: に結んだ値を trace から引いて照らす。notes は dry-run が置き場にファイルを置けないので、筋書きが answer-replan に結んだ値の
    まま script を走らせ直し、指し札の先に事前審査の返りと修正案の役の返答を置いて照らす"""

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(("replan", "standard"))
        cls.nodes = {n["id"]: n for n in yaml.safe_load(LINE.read_text(encoding="utf-8"))["nodes"]}

    def stub(self, scenario: str, node: str):
        doc = yaml.safe_load((archon.WORKFLOWS / "line" / "fixtures" / f"{scenario}.stubs.yaml").read_text(encoding="utf-8"))
        return doc[node]

    def test_refix_gets_the_first_conflicts_the_replan_review_and_the_items(self):
        trace, with_ = self.traces["replan"], self.nodes["refix-run"]["with"]
        self.assertEqual(bound(trace, with_["prior_conflicts"]), self.stub("replan", "fix__fix")["conflicts"])
        self.assertEqual(bound(trace, with_["plan_review"]), self.stub("replan", "replan-review__review")["review"])
        self.assertEqual(bound(trace, with_["only_items"]), ["1"])
        notes = bound(trace, with_["notes"])
        self.assertTrue(isinstance(notes, str) and notes, notes)   # 筋書きの中では事前審査の返りが読めず、訳の 1 行

    def test_refix_notes_carry_the_replan_review_faces(self):
        trace = self.traces["replan"]
        review = bound(trace, self.nodes["answer-replan"]["with"]["review"])
        plan = bound(trace, self.nodes["answer-replan"]["with"]["plan"])
        with tempfile.TemporaryDirectory() as tmp:
            art = pathlib.Path(tmp)
            (art / review["path"]).parent.mkdir(parents=True, exist_ok=True)
            (art / review["path"]).write_text(json.dumps({"faces": [
                {"key": "穴-空の列", "kind": "contract_drift", "where": "stats.py", "why": "空の列で割れる", "unit_keys": ["u1"]}]},
                ensure_ascii=False), encoding="utf-8")
            (art / plan["path"]).parent.mkdir(parents=True, exist_ok=True)
            (art / plan["path"]).parent.joinpath("p2.fix_plan.json").write_text(json.dumps({"plan": [{"unit_keys": ["u1"]}]}),
                                                                                encoding="utf-8")
            got = rerun(trace, "answer-replan", art, review["run_id"])
        self.assertIn("## 直した項目 1（単位 u1）の事前審査の穴\n\n- [contract_drift] 穴-空の列（stats.py）: 空の列で割れる",
                      got["fix_notes"])

    def test_eyes_get_the_fix_x_scalars(self):
        trace = self.traces["standard"]
        self.assertEqual(bound(trace, self.nodes["eyes"]["with"]["x_scalars"]), {"x_moved_lines": 3})


class ReportOutcomeTest(unittest.TestCase):
    """部分 C の受け入れ: 筋書き start-refused・unattended-needs-human・final-stop の道で、本物の report（facts）が結末の語を
    返す（入口の拒み → stopped_by_line、無人の run の最後の関所の止め → needs_human、人の最後の関所の stop → stopped_by_human）。
    dry-run は include の入力を名前の script に渡さない（docs/design.md の U3）ので筋書きの中の report は stub のまま、筋書きが
    report の with: に結んだ collect の値のまま facts を走らせ直す（始めの記録は dry-run が置き場に書けないので、指し札の先に試験が置く）"""

    WANT = {"start-refused": ("stopped_by_line", "start:works:start-refused"),
            "unattended-needs-human": ("needs_human", "ask-final:works:needs-human"),
            "final-stop": ("stopped_by_human", "gate-final:stop"),
            "spec-changed": ("needs_human", "spec-check:works:spec-changed")}

    @classmethod
    def setUpClass(cls):
        cls.traces = line_traces(tuple(cls.WANT))

    def facts(self, trace: dict) -> dict:
        with_ = {n["id"]: n for n in yaml.safe_load(LINE.read_text(encoding="utf-8"))["nodes"]}["report"]["with"]
        start = bound(trace, with_["start"])
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = pathlib.Path(tmp)
            run_id = (start or {}).get("run_id") or "dry-run"
            if start:
                (artifacts / start["path"]).parent.mkdir(parents=True, exist_ok=True)
                (artifacts / start["path"]).write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if not k.startswith("INPUTS_")}
            env.update({"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": run_id, "TYPED_ARTIFACTS_FILE": "", "LOG_DIR": "",
                        "WORKS_FACTORY_ROOT": str(archon.WORKFLOWS.parent)})
            for key, value in with_.items():
                got = bound(trace, value)
                env[f"INPUTS_{key.upper().replace('-', '_')}"] = got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)
            script = archon.WORKFLOWS / "report" / "scripts" / "facts.py"
            done = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, cwd=artifacts)
            out = json.loads(done.stdout)
            out["text"] = (artifacts / out["facts_file"]).read_text(encoding="utf-8")
            return out

    def test_real_report_names_the_outcome(self):
        for name, want in self.WANT.items():
            with self.subTest(scenario=name):
                got = self.facts(self.traces[name])
                self.assertEqual((got["outcome"], got["stop_reason"]), want, got["text"])

    def test_line_stop_reaches_the_report_text(self):
        got = self.facts(self.traces["unattended-needs-human"])
        self.assertIn("- メイングラフのノードの止め: ask-final が works:needs-human", got["text"])


if __name__ == "__main__":
    unittest.main()
