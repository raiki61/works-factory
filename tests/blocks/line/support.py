"""line の試験の助け（試験のモジュールではない）。line の試験が共に使う物を 1 か所に置き、試験のモジュールどうしで import しない
（tests/blocks/diagnose/support.py・tests/blocks/report/base.py と同じ形）。

- 段の返りの材料: handed（request-in の返りの欄）・rounds・ask_row・NARROW（計画の往復の返り）・fix・lens・delta・values（修正の段）・
  passing・seed・record・COLLECT_INPUTS・ptr・check（collect の入力）
- script と start: script（scripts/<名>.py を名で読む）・start と、run directory を一時にする Artifacts・種の対象を組む Seeded・raw・INPUTS
- 筋書き（workflows/line/fixtures/*.stubs.yaml）の dry-run: nodes・line_traces・ran・out・got・bound・assert_no_write・LINE_YAML・TOP
- 設計の相談: written_record・no_materials・TalkBase・APPROACH
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.workflows.test_returns_never_fail import would_run  # noqa: F401  （Archon の待ち方の模型。line の試験はここから読む）

BLOCK = "line"
LINE_YAML = kit.BLOCKS / BLOCK / f"works-factory-{BLOCK}.yaml"
TOP = {n["id"]: n for n in yaml.safe_load(LINE_YAML.read_text(encoding="utf-8"))["nodes"]}   # line の最上段の node の id → node
descend = kit.load(BLOCK, "descend")


def handed(dealt: dict) -> str:
    """request-in の返りの形の依頼の欄（配る値まるごとを受ける script は依頼をここから読む。src/descend.py の dealt）"""
    return json.dumps({name: dealt.get(name) for name in descend.REQUEST_FIELDS}, ensure_ascii=False)


NARROW = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える"


def ask_row(text=NARROW, *, decided=False, why=None, mark=None, kind="regression") -> dict:
    """plan-review の出力 asks の 1 行（plan-review の設計書の 10.1）"""
    return {"kind": kind, "node": "p2.fix_plan", "text": text, "units": ["u1"], "mark": mark or {},
            "decided": decided, "why": why if why is not None else ({} if decided else {"obvious": ["決め手の欄が揃わない"]})}


def rounds(**over) -> dict:
    """計画の往復の返り（plan-out の返り）。既定は修正へ進む抜け方で、人に回しうる行は無い"""
    return {"done": True, "ok": True, "status": "ok", "round": 1, "plan_prior": None, "record": None, "plan": None, "fix_plan": None,
            "reply": None, "handoffs": [], "ripple": None, "owed": ["u1"], "gave_up": None, "stalled": False, "capped": False,
            "review": None, "asks": [], "deviations": [], "review_status": "ok", "review_reason": "", "stop_reason": "", **over}


ROOT = kit.ROOT
LINE = kit.BLOCKS / "line"
SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN = kit.RUN_ID
INPUTS = ("request", "base", "pr", "spec", "test_cmd", "tdd_suite", "final_gate", "unattended", "design_talk", "thickness",
          "features_off", "features_on", "policy_md", "fix_fixture", "lang", "deliver", "spec_table")


def script(name: str):
    """workflows/line/scripts/<name>.py を名で読む（__main__ でないので ports.run は回らない）。src と共通の口を sys.path の頭に置く"""
    sys.dont_write_bytecode = True
    for mod in [n for n in sys.modules if n == "src" or n.startswith("src.")]:
        del sys.modules[mod]
    for path in (str(LINE), str(kit.SHARED)):
        while path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location(f"line_script_{name}", LINE / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


start = script("start")
start.load()
entry, entryshape, stopby = start.entry, start.entryshape, start.stopby
startrec, fixture, deal = start.startrec, start.fixture, start.deal


def raw(**kw) -> dict:
    got = dict.fromkeys(INPUTS, "")
    got.update(kw)
    return got


class Artifacts(unittest.TestCase):
    """run directory（ARTIFACTS_DIR）と run の id（WORKFLOW_ID）を一時の物にする"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        env = mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN})
        env.start()
        self.addCleanup(env.stop)


class Seeded(Artifacts):
    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.fork = committed_copy(self.repo, SEED)
        git(self.repo, "branch", "base")
        with (self.repo / "stats.py").open("a", encoding="utf-8") as f:
            f.write("\n# 変更\n")
        git(self.repo, "commit", "-q", "-am", "change")

    def start(self, **kw):
        return start.start(raw(**kw), self.repo, self.artifacts, RUN)

    def record(self, got):
        self.assertEqual(got["record"]["run_id"], RUN)
        return json.loads((self.artifacts / got["record"]["path"]).read_text(encoding="utf-8"))

    def outside(self, name: str, text: str) -> pathlib.Path:
        """対象の木の外に置く依頼のファイル（木を汚すと差分が空でなくなる）"""
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def refused(self, **kw) -> str:
        got = self.start(**kw)
        self.assertEqual((got["ok"], got["stop_reason"]), (False, stopby.START_REFUSED), got)
        return got["reason"]

    def pr_reads(self, **pr) -> dict:
        doc = {"baseRefOid": self.fork, "headRefOid": git(self.repo, "rev-parse", "HEAD"), "title": "題 T", "body": "本文X",
               "status": "ok"}
        doc.update(pr)
        return {"version": 1, "pr": {"7": doc}, "issue": {}}

    def start_with_gh(self, reads, **kw):
        """run の中の gh の読み出しを reads に差して start を回す（呼ばれた回数を返す）"""
        import ghreads
        calls = []

        def read_named(repo, prs, issues):
            calls.append((prs, issues))
            return reads
        with mock.patch.object(ghreads, "read_named", read_named):
            return self.start(**kw), calls


def nodes() -> dict:
    """line の node の id → node（loop_group の本体の node も含む）"""
    top = yaml.safe_load(LINE_YAML.read_text(encoding="utf-8"))["nodes"]
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
    """node の出力（JSON）。include した block の返りは `got(trace, id)`"""
    return json.loads(trace[node]["output"])


def returned(include: str) -> str:
    """include の id → trace の中の返す節の id（`<include の id>__<block の returns:>`。Archon が `$<include>.output` を解く先）"""
    inner = str(nodes()[include]["include"]).removeprefix("works-factory-")
    doc = yaml.safe_load((kit.BLOCKS / inner / f"works-factory-{inner}.yaml").read_text(encoding="utf-8"))
    return f"{include}__{doc['returns']}"


def got(trace: dict, include: str):
    """include した block の返り（返す節の出力）か、輪（loop_group）の返り（輪の行の出力）。走らなければ None"""
    node = returned(include) if "include" in nodes()[include] else include
    return out(trace, node) if ran(trace, node) else None


def _traced(trace: dict, node: str) -> str:
    """with: が名指す node の trace の行の id（include は返す節）"""
    return node if node in trace or "include" not in nodes().get(node, {}) else returned(node)


def bound(trace: dict, value):
    """line の node の with: の 1 つの値を、dry-run の trace の出力で結ぶ（`$<id>.output.<欄>`・まるごとの参照 `$<id>.output` と
    `{from, if_skipped}`。include した block の返りは trace に include の id の行が無いので、返す節の行から読む）"""
    if isinstance(value, dict) and "from" in value:
        node = _traced(trace, value["from"].split(".", 1)[0].lstrip("$"))
        if node not in trace or trace[node]["state"] == "skipped":
            return value.get("if_skipped")
        value = value["from"]
    if isinstance(value, str) and value.startswith("$") and value.endswith(".output"):
        node = _traced(trace, value[1:-len(".output")])
        return trace[node].get("output") if node in trace else None
    if not (isinstance(value, str) and value.startswith("$") and ".output." in value):
        return value
    node, field = value[1:].split(".output.", 1)
    return json.loads(trace[_traced(trace, node)]["output"]).get(field)


def assert_no_write(case, never_apply, never_seal):
    """筋書き never_apply のどれも差分を当てる段を走らせず、result の apply が null。never_seal のものは封じもしない"""
    traces = line_traces(never_apply)
    for name in never_apply:
        with case.subTest(scenario=name):
            trace = traces[name]
            for node in ("merge-apply__place", "merge-apply__merge", "merge-apply__pr-commit", "merge-apply__pr-open"):
                case.assertFalse(ran(trace, node), node)
            case.assertIsNone(out(trace, "result")["apply"])
            if name in never_seal:
                case.assertFalse(ran(trace, "merge-seal__merge"))
                case.assertIsNone(out(trace, "result")["sealed"])


COLLECT_INPUTS = ("notices", "start", "answer_start", "test_gate_base", "judge", "tiers", "owed", "structure", "structure_in", "independent_design",
          "design_in", "rounds", "ask_before_fix", "answer_before_fix", "fix_in", "fix", "after_fix", "raise", "lens", "lens_in", "delta",
          "replan", "replan_review", "ask_replan", "answer_replan", "refix", "lens_2", "lens_2_in", "delta_2", "fixed", "parallel_after",
          "rejudge", "spec_check", "judged", "test_gate_final", "eyes_in", "eyes", "eyes_back", "back_1", "merge_seal", "ask_final", "answer_final", "merge_apply",
          "optional")


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": path}


def check(value, schema: pathlib.Path) -> list:
    import sys
    sys.path.insert(0, str(ROOT / "lib" / "graphloops"))
    from engine.schema import validate_schema
    return validate_schema(value, json.loads(schema.read_text(encoding="utf-8")))


def passing() -> dict:
    """どの段も通った run の collect の入力の値（block の返りと line の script の出力）"""
    tests = {"mode": "final", "ok": True, "green": True, "red_cause": "", "ran_steps": {"ran": ["t"], "unran": []}, "baseline": None,
             "fingerprint": None, "test_outcomes": None, "evidence": ptr("test-gate-final/evidence.txt"), "by": "test_cmd", "suites_line": "",
             "log": "", "baseline_line": "直す前のテスト: 緑", "reason": "", "suite": "", "suite_note": "",
             "related": {"applied": False, "whole": False, "files": [], "left": [], "far": [], "reasons": [], "ran": "none"},
             "report": ["- 最後のテスト: 緑"]}
    fix = {"ok": True, "reason": "", "units": [{"unit_id": "u1", "status": "fixed"}], "groups": [], "conflicts": None, "carry": None,
           "replan_items": [], "objection": "", "diff": ptr("fix/diff"), "start_tree": "t", "reply": None, "ruled_reply": None,
           "scope": None, "checked": {"ok": True, "reason": ""}, "allowed_test_changes": [], "changed": {}, "x_scalars": {}, "handoffs": [], "handoff_titles": {},
           "mismatched": [], "plan_declared": [], "stop_reason": "", "allowed_tests": None, "accept_trace": None, "closure": None,
           "tdd_unit": None, "tdd": [{"units": [{"unit_key": "u1", "test_cmd": "light"}]}], "frozen": None, "removed": [],
           "tdd_refused": {"refused": [], "unread": []}, "item_claims": None, "freeze_off": [], "removed_tests": [], "untested": [], "report": ["- u1: fixed"]}
    fix["closure"] = ptr("fix/closure.json")
    eyes = {"ok": True, **{f"r{n}": {"status": "pass", "reason": ""} for n in range(1, 5)}, "questions": [], "means_questions": [], "passes": [],
            "premise_check": None, "notes": [], "after": None, "dirty": 0, "escalate": 0, "after_ok": True, "findings": [], "route": "stay",
            "route_why": "返す物が無い（どの目も通った）", "report": ["- 目: 通した"],
            "sections": [{"title": "独立の目 R1 最小性とコメント", "lines": ["- R1 通した"]}, {"title": "直した後の構造の実測", "lines": ["- 実測"]}]}
    judge = {"ok": True, "stop_reason": "", "reason": "", "ready": True, "units": [{"id": "u1"}], "questions": [], "judgment": None, "answer_ties": None,
             "out_of_purpose": None, "materials": None, "brief": None, "inputs": None, "purpose": None, "purpose_text": "P",
             "purpose_source": "", "means": [], "purpose_review": None, "constraints": None, "world": None, "world_state": {"status": "ok", "reason": ""},
             "spec": None, "spec_rows": None, "spec_origin": "", "excluded": None, "pr_drafts": None, "downgrades": [], "decisions": None,
             "tier": "標準", "tier_why": "", "row_asks": [], "tier_record": None, "verify": None, "verify_why": "既定で切（features の既定）",
             "report": [], "sections": [{"title": "世界の解", "lines": ["- 世界"]}, {"title": "根本の診断", "lines": ["- 判定"]},
                                        {"title": "素材: 局所レビュー", "lines": ["- 局所"]}, {"title": "素材: コード衛生", "lines": ["- 衛生"]}],
             "optional": [{"node": "world", "bare": False}]}
    seal = {"mode": "seal", "ok": True, "hash": "h", "diff": ptr("merge-seal/diff"), "protected_hits": [], "protected_count": 0,
            "reason": "", "deliver": None, "report": ["- 封じた"]}
    fixed = {"go": True, "done": True, "held": False, "no_fix": False, "diffed": True, "checks": True, "eyes_due": True, "skip_why": "",
             "rejudge": False, "refixed": False, "stages": [{"stage": 1, "kind": "first", "fix": fix, "lens": None, "delta": None}], "carry": [],
             "tdd": [fix["tdd"]], "units": fix["units"], "groups": [], "conflicts": [], "replan_items": [], "objection": "", "diff": fix["diff"],
             "item_claims": None, "allowed_test_changes": [], "changed": {}, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [],
             "plan_declared": [], "plan": None, "ripple": None, "left": [], "stop_reason": ""}
    return {name: None for name in COLLECT_INPUTS} | {
        "notices": "注意（test_cmd）: x",
        "start": {"ok": True, "stop_reason": "", "reason": "", "record": ptr("r1/start.json"), "prior_failures": None, "ask": False,
                  "gate_text": "", "unattended": False, "design_talk": False, "final_gate": "always", "from_fixture": False, "fixture": None,
                  "ports": {"run_id": kit.RUN_ID, "user_env_dir": ""}},
        "answer_start": {"go": True, "answer": None, "stop_reason": ""},
        "test_gate_base": {**tests, "mode": "base", "report": ["- 直す前: 緑"]},
        "judge": judge,
        "rounds": {"done": True, "ok": True, "status": "ok", "round": 1, "plan_prior": None, "record": None, "plan": ptr("plan/p.json"),
                   "fix_plan": None, "reply": None, "handoffs": [], "ripple": None, "owed": ["u1"], "gave_up": None, "stalled": False,
                   "capped": False, "review": None, "asks": [], "deviations": [], "review_status": "ok", "review_reason": "", "stop_reason": "", "pointed": []},
        "ask_before_fix": {"open": True, "go": True, "stop_reason": "", "text": "", "deferred": [], "asked": [], "pushed": None, "passes": [],
                           "policy_changed": False},
        "answer_before_fix": {"go": True, "answer": {"decision": "approve", "text": "よい"}, "stop_reason": "", "policy": ""},
        "fix_in": {"go": True, "no_fix": False, "received": None, "switches": {"tier": "標準", "lines": ["- 省く物は無い"]}},
        "fix": fix, "after_fix": {"replan": False, "prior": None, "stop_reason": ""},
        "raise": {"units": [{"unit_id": "u1", "depth": "軽量", "why": "単位が小さい"}], "checks": True, "skip_why": "", "eyes_due": True, "raised": [], "counted": "", "lines": ["深さ: 標準"],
                  "stop_reason": ""},
        "fixed": fixed, "judged": {"units": [], "lines": [], "carry": [], "stop_reason": ""}, "test_gate_final": tests, "eyes": eyes,
        "merge_seal": seal, "ask_final": {"open": True, "go": True, "stop_reason": "", "text": "", "reasons": []},
        "answer_final": {"go": True, "answer": {"decision": "approve", "text": "当てる"}, "stop_reason": ""},
        "optional": ["eyes__", "lens__", "lens-2__"],
    }


def seed_closure(run) -> None:
    """修正の段の控え（閉鎖の表）を place に置く"""
    (run.artifacts / "fix").mkdir(exist_ok=True)
    (run.artifacts / "fix" / "closure.json").write_text(json.dumps({"rows": [{"unit_key": "u1", "closed": True}], "claimed": ["u1"]}))
    (run.artifacts / "fix" / "diff").write_text("")


def base_record() -> dict:
    return {"input": {"base": {"label": "差分なし（HEAD）"}}, "answers": [], "versions": {}}


def fix(**kw) -> dict:
    """fix の返り（docs/design/fix.md の 1.2 の欄）"""
    got = {"ok": True, "reason": "", "units": [{"unit_id": "u1", "status": "given_up"}], "groups": [{"group_id": "g1"}],
           "conflicts": {"path": "fix/conflicts.json"}, "carry": None, "replan_items": ["1"], "objection": "", "diff": {"path": "fix/diff"},
           "start_tree": "t1", "reply": None, "ruled_reply": None, "scope": None, "checked": {"ok": True, "reason": ""},
           "allowed_test_changes": ["tests/a.py"], "changed": {"path_changed": False}, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [],
           "plan_declared": [], "stop_reason": "", "allowed_tests": {"path": "fix/allowed.json"}, "accept_trace": {"path": "fix/trace.json"},
           "closure": {"path": "fix/closure.json"}, "tdd_unit": {"path": "fix/tdd.json"}, "tdd": [{"units": []}], "frozen": None,
           "removed": [], "tdd_refused": {"refused": [], "unread": []}, "item_claims": None, "freeze_off": [], "removed_tests": [], "untested": [], "report": ["- 修正"]}
    got.update(kw)
    return got


def lens(**kw) -> dict:
    return {"ok": True, "status": "ok", "reason": "", "rows": None, "ran": 1, "failed": 0, "not_routed": 0,
            "carry": [{"where": "レンズ x", "text": "再実行の要あり"}], "report": [], **kw}


def delta(**kw) -> dict:
    return {"ok": True, "status": "ok", "reason": "", "rounds": 1, "pass": True, "holes": None, "diff": {"path": "delta/diff"},
            "carry": [], "report": [], **kw}


def values(**kw) -> dict:
    base = {"fix_in": {"go": True, "no_fix": False, "plan": {"path": "p.json"}, "ripple": {"path": "r.json"}},
            "fix": fix(), "after_fix": {"replan": False, "prior": None, "stop_reason": ""},
            "raise": {"units": [], "checks": True, "skip_why": "", "eyes_due": True, "raised": [], "counted": "", "lines": [], "stop_reason": ""},
            "lens": lens(), "delta": delta(), "replan": None, "refix": None, "lens_2": None, "delta_2": None}
    base.update(kw)
    return base


APPROACH = "空の列で 0 を返す形に変える"


def written_record(rounds_mod, dest, *, passes=((),)) -> dict:
    """line の書き手の道で作った往復の記録: 項目 1 つの案に、passes の往復ごとの block の key の組で事前審査の返答を足す"""
    doc = rounds_mod.fresh()
    for k, keys in enumerate(passes, 1):
        rounds_mod.record_pass(doc, {"plan": [{"id": "u1", "unit_keys": ["u1"], "hash": "h1"}],
                                     "review": {"faces": [{"key": key, "kind": "x", "where": "", "why": "w", "severity": "block",
                                                           "unit_keys": ["u1"]} for key in keys]},
                                     "answers": [], "resolved": []}, at_cap=False, dest=pathlib.Path(dest) / str(k))
    return doc


def no_materials(_rounds) -> dict:
    """設計の相談の行の材料（判定・構造の目・方針の文書の変化・前の答えの無い run）"""
    return {"ledger": None, "design_rows_": [], "policy_row": "", "stuck_reason": "", "record_doc": None, "answered": [],
            "unread": []}


class TalkBase(unittest.TestCase):
    """設計の相談の試験の助け（周の頭と終わりを place の一時のフォルダで回す）"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        with self.run.env():
            self.t = kit.load(BLOCK, "talk")
            self.r = kit.load(BLOCK, "rounds")
            self.g = kit.load(BLOCK, "gates")
        self.answer = __import__("answer")

    def put(self, rel: str, doc) -> dict:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.loads(self.run.pointer(rel))

    def record(self) -> dict:
        """往復が 1 つで、項目 1 つの閉じた記録（plan-converge.json）。line の書き手（rounds.fresh・record_pass）で作る"""
        return written_record(self.r, self.run.artifacts / "plan-converge")

    def plan_out(self, **over) -> dict:
        """plan-out の返り（往復の記録と案の控えの pointer つき）"""
        record = self.put("plan-converge.json", self.record())
        fix_plan = self.put("plan/r1/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "approach": APPROACH}]})
        fields = self.put("plan/r1/plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": [], "route": "tdd"}]})
        reply = self.put("plan/r1/reply.json", {"plan": [{"unit_keys": ["u1"], "approach": APPROACH}]})
        prior = self.put("plan-rounds/prior-1.json", {"round": 1, "reply": reply, "fields": fields, "record": self.record()})
        return {**rounds(record=record, plan_prior=prior, fix_plan=fix_plan, plan=fields), **over}

    def turn(self, answer="", previous=None, last=None, design_talk=True, **given):
        with self.run.env():
            return self.t.turn(answer_raw=answer if isinstance(answer, str) else json.dumps(answer),
                               previous_raw=json.dumps(previous) if previous is not None else "",
                               last_raw=json.dumps(last) if last is not None else "",
                               given={"design_talk": design_talk, "unattended": False, "request_answers": [{"question": "q", "text": "a"}],
                                      **given},
                               recorded=[{"source": "doc", "name": "p.md", "text": ""}], place=self.run.artifacts)

    def materials(self, po) -> dict:
        """材料の読み（asking.materials と同じく往復の記録を 1 つの読み口で読む。ほかの材料は無い run）"""
        return {**no_materials(po), "record_doc": self.t._record_of(po.get("record"))}

    def settle(self, turn_got, plan_out=None, previous=None, design_talk=True):
        with self.run.env():
            return self.t.settle(turn_got=turn_got, plan_out=plan_out, previous=previous,
                                 given={"design_talk": design_talk, "unattended": False}, materials=self.materials, run_id=kit.RUN_ID)

    def opened(self, **over) -> dict:
        """対話モードで往復が止まった周の design-talk の返り（関所が開いた）"""
        return self.settle(self.turn(), self.plan_out(**over))
