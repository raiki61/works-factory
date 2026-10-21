"""修正の block（workflows/fix/）の返す node finish と、全体の形の終わりの clean・assert-changed の試験（docs/design/fix.md の 1.2・7 節・
11 節・14.2）。

今の tests/workflows/test_fix.py の BlockScriptsCase の collect・clean・assert_changed の試験を写した（差分の審査とレンズの欄の物は
delta-review と lens の block へ移ったので写さない）。script は始めの記録の無い使い捨ての run directory と tests/e2e/target-seed/ の写しの
git のリポジトリで子のプロセスで回し、port の値だけを渡す（finish は intake が書いた intake.json で形を読む）。足した物:
- 出力の欄が YAML の finish の output_format の required・properties と同じで、形に合う
- report と freeze_off の行が lib の report.tdd_lines・freeze_lines の字のまま（11 節）
- UnitsReachReportCase（直す単位ごとの記録が出力 units と report の TDD の行に届く。12 節の 11）
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

ROOT = kit.ROOT
SEED = ROOT / "tests" / "e2e" / "target-seed"
YAML_PATH = kit.BLOCKS / "fix" / "works-factory-fix.yaml"
MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed", "path_changed")
JUDGMENT = {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"},
                      {"key": "C", "label": "suggest", "disposition": "do-now"}], "questions": []}


def node_format(node: str) -> dict:
    doc = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    return next(n for n in doc["nodes"] if n["id"] == node)["output_format"]


def lib_report():
    """lib の report（ほかの試験が sys.path や sys.modules を動かしても、名の重なる block の src/report.py と取り違えない）"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("lib_report_for_fix_tests", ROOT / "lib" / "report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, doc) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def result(gid, unit_ids, end_tree, start_tree, **extra) -> dict:
    """組の子が out_dir/<gid>/result.json に書く結果（board.group_result の形）"""
    doc = {"group_id": gid, "unit_ids": unit_ids, "end_tree": end_tree, "start_tree": start_tree,
           "units": [{"unit_id": k, "status": "fixed", "reason": ""} for k in unit_ids],
           "tdd": {"ran": False, "reason": "実行器が無い", "suite": "", "units": []}, "conflicts": [], "objection": "",
           "changed": {k: False for k in MARKS}, "allowed_tests": [], "verified": []}
    doc.update(extra)
    return doc


TDD_ROW = {"unit_key": "A", "route": "tdd", "why": "", "tests": ["test_stats.py::test_mean"], "test_files": [],
           "red": "ok", "green": "ok", "refactor": "none", "gave_up": "", "problems": [], "red_quotes": {},
           "quote_unchecked": [], "stub_files": [], "test_cmd": "", "refactor_why": ""}


class FinishPlace(unittest.TestCase):
    """全体の形の place（intake を mode whole で回した後）と、組の子の結果・join の控えを置く助け"""

    @classmethod
    def setUpClass(cls):
        cls.board = kit.load("fix", "board")   # lib も読める
        cls.files = kit.load("fix", "files")
        import leftovers
        from engine.schema import validate_schema
        cls.snapshot = staticmethod(leftovers.snapshot)
        cls.validate = staticmethod(validate_schema)
        cls.fmt = node_format("finish")

    def setUp(self):
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.repo = self.run.repo
        self.art = self.place = self.run.artifacts   # 単独の run の place は $ARTIFACTS_DIR
        self.tmp = self.art.parent
        self.intake(mode="whole", judgment=json.dumps(JUDGMENT, ensure_ascii=False))

    # ---- 助け
    def intake(self, **inputs):
        out = self.run.script("intake", **inputs)
        self.assertTrue(out["ok"], out)

    def script(self, name, **inputs):
        return self.run.script(name, **inputs)

    def finish(self) -> dict:
        out = self.script("finish")
        self.assert_contract(out)
        return out

    def restore(self):
        git(self.repo, "checkout", "-q", "--", ".")
        git(self.repo, "clean", "-qfd")

    def tree_with(self, files):
        """files を書いた作業ツリーの姿の木を取り、作業ツリーを元に戻す"""
        for name, text in files.items():
            (self.repo / name).write_text(text, encoding="utf-8")
        tree = self.snapshot(self.repo)
        self.restore()
        return tree

    def groups_file(self, groups, start_tree, par=True):
        out_dir = self.place / "groups"
        write(self.place / "groups.json", {"groups": groups, "count": len(groups), "par": par, "start_tree": start_tree,
                                           "out_dir": str(out_dir)})
        return out_dir

    def collect_place(self, *, ok=True, result_extra=None, conflicts=None):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start, par=False)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, **(result_extra or {})))
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}]})
        write(self.place / "assert-changed.json", {"ok": ok, "reason": "" if ok else "申告が無い"})
        if conflicts is not None:
            write(self.place / "conflicts.json", {"items": conflicts})
        (self.repo / "stats.py").write_text("X = 2\n", encoding="utf-8")

    def assert_contract(self, out):
        self.assertEqual(self.validate(out, self.fmt), [], out)
        self.assertEqual(set(out), set(self.fmt["properties"]), "返す node は required に無い欄も全部返す")

    def beside(self, out) -> pathlib.Path:
        return (self.art / out["diff"]["path"]).parent

    def without_lib(self) -> dict:
        """lib が読めない（WORKS_FACTORY_ROOT の先に lib/ が無い）finish。落ちずに約束の形を返す"""
        empty = self.tmp / "no-root"
        empty.mkdir(exist_ok=True)
        env = hermetic.child_env(**{**self.run.environ(), "WORKS_FACTORY_ROOT": str(empty), "PYTHONDONTWRITEBYTECODE": "1"})
        done = subprocess.run([sys.executable, str(kit.BLOCKS / "fix" / "scripts" / "finish.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assert_contract(out)
        return out


class ContractCase(FinishPlace):
    """出力の欄が YAML の output_format と同じ（docs/design/fix.md の 1.2）"""

    def test_output_keys_are_the_yaml_fields(self):
        self.assertEqual(set(self.fmt["required"]), set(self.fmt["properties"]), "出力の欄は全部 required")
        self.collect_place()
        out = self.finish()
        self.assertEqual(set(out), set(self.fmt["required"]))

    def test_fallback_keys_are_the_yaml_fields(self):
        """組めない時（groups.json が無い）の返りも同じ欄"""
        out = self.finish()
        self.assertFalse(out["ok"])
        self.assertEqual(set(out), set(self.fmt["required"]))

    def test_group_form_keys_are_the_yaml_fields(self):
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start))
        self.intake(mode="group", group=json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []}), out_dir=str(out_dir))
        self.assertEqual(set(self.finish()), set(self.fmt["required"]))


class CollectCase(FinishPlace):
    """今の BlockScriptsCase の collect の試験"""

    def test_finish_returns_the_diff_and_no_conflicts(self):
        self.collect_place()
        out = self.finish()
        self.assertTrue(out["ok"])
        self.assertEqual(out["reason"], "")
        self.assertIsNone(out["conflicts"])
        diff = self.art / out["diff"]["path"]
        self.assertIn("stats.py", diff.read_text(encoding="utf-8"))
        self.assertEqual(out["diff"]["run_id"], kit.RUN_ID)
        self.assertEqual(out["checked"], {"ok": True, "reason": ""})

    def test_collect_returns_the_item_claims_of_the_returned_groups(self):
        """#569: 欄 item_claims は、戻せた組の子の修正役の返答の changes[].files と TDD の輪の単位の test_files を単位ごとに
        並べる（承認済みの修正案の無い place は items が null）。返答を読めなければ訳"""
        reply = write(self.tmp / "g1-reply.json", {"changes": [{"unit_key": "A", "files": [str(self.repo / "stats.py")]}]})
        tdd = {"ran": True, "reason": "", "suite": "run.sh", "units": [{"unit_key": "A", "test_files": ["test_stats.py"]}]}
        self.collect_place(result_extra={"reply_file": str(reply), "tdd": tdd})
        out = self.finish()
        self.assertEqual(out["item_claims"], {"items": None, "unread": [],
                                              "claims": [{"unit_key": "A", "files": ["stats.py"]},
                                                         {"unit_key": "A", "files": ["test_stats.py"]}]})
        reply.unlink()
        out = self.finish()
        self.assertIn("組 g1 の修正役の返答", out["item_claims"]["unread"][0])

    def test_collect_returns_the_beside_records_as_ports(self):
        """#681: 出力は diff の隣の控えを欄の pointer で返す（先が無ければ null）。tdd-unit.json は finish が書く"""
        self.collect_place()
        out = self.finish()
        for field, name in (("allowed_tests", self.files.ALLOWED_TESTS_FILE), ("accept_trace", self.files.ACCEPT_TRACE_FILE),
                            ("closure", self.files.CLOSURE_FILE), ("tdd_unit", self.files.TDD_UNIT_FILE)):
            self.assertEqual(self.art / out[field]["path"], self.beside(out) / name, field)
        self.assertEqual(out["tdd_refused"], {"refused": [], "unread": []})
        self.assertEqual(out["removed"], [])
        self.assertIsNone(out["frozen"], "TDD の輪の無い place は frozen.json を書かない")

    def test_tdd_unit_writes_one_body_for_all_groups(self):
        """今の tdd-unit の node の本文（組ごとの TDD の輪の結果）は finish が tdd-unit.json に書き、出力 tdd で同じ物を返す"""
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": []}], start)
        write(out_dir / "g1" / "result.json", result(
            "g1", ["A"], start, start, tdd={"ran": True, "reason": "", "suite": "run.sh", "reused": {}, "units": [TDD_ROW]}))
        out = self.finish()
        self.assertEqual(out["tdd"], [{"group_id": "g1", "ran": True, "reason": "", "suite": "run.sh", "reused": {}, "related": {}, "units": [TDD_ROW]},
                                      {"group_id": "g2", "ran": False, "reason": out["tdd"][1]["reason"], "suite": "", "reused": {},
                                       "related": {}, "units": []}])
        self.assertTrue(out["tdd"][1]["reason"])
        self.assertEqual(json.loads((self.art / out["tdd_unit"]["path"]).read_text(encoding="utf-8")), out["tdd"])

    def test_collect_returns_removed_as_pointers_to_every_scope_file(self):
        """#681: clean が消したパスの控えは全件を欄に載せず、place の根と scope の根の控えの pointer の並びで返す"""
        import leftovers
        self.collect_place()
        write(self.place / leftovers.REMOVED_FILE, {"removed": [f"build/{i}.o" for i in range(5000)]})
        write(self.place / "sub" / leftovers.REMOVED_FILE, {"removed": ["gen/a.o"]})
        out = self.finish()
        self.assertEqual([self.art / ptr["path"] for ptr in out["removed"]],
                         [self.place / leftovers.REMOVED_FILE, self.place / "sub" / leftovers.REMOVED_FILE])
        self.assertLess(len(json.dumps(out["removed"])), 1000)
        names = [json.loads(p.read_text(encoding="utf-8"))["removed"] for p in map(lambda ptr: self.art / ptr["path"], out["removed"])]
        self.assertEqual([len(x) for x in names], [5000, 1], "控えの全件が pointer の先に残る（読み手の数え方は report と line の試験）")

    def test_unrestored_group_holds_the_tree_and_stops_for_a_human(self):
        """#403: 戻せず当たったままの組が在る run は、裁定・後始末が木を動かさず、finish は ok: false と人待ちの止めの語
        stopby.UNRESTORED で返す（組の行は当たったままのパスを持つ）"""
        import leftovers
        import stopby
        self.collect_place()
        leftovers.record_ignored(self.place, self.repo)
        (self.repo / "junk.pyc").write_bytes(b"x")
        row = {"group_id": "g1", "unit_ids": ["A"], "returned": False, "reason": self.board.UNRESTORED_HEAD,
               "unrestored": ["stats.py"]}
        write(self.place / "join.json", {"par": True, "groups": [row],
                                         "units": [{"unit_id": "A", "group_id": "g1", "status": "not_done", "reason": "x"}]})
        self.assertEqual(self.script("conflict_check"), {"go": False, "count": 0})
        self.assertEqual(self.script("clean"), {"ok": True, "count": 0})
        self.assertTrue((self.repo / "junk.pyc").is_file(), "人が確かめるまで木を動かさない")
        out = self.finish()
        self.assertEqual((out["ok"], out["stop_reason"], out["groups"]), (False, stopby.UNRESTORED, [row]))
        self.assertIn(stopby.UNRESTORED, stopby.WAITING, "人待ちの語（結末は needs_human）")
        with self.subTest("finish の中が落ちた道（fallback）も、当たったままの組を名指して人に回す"):
            (self.place / self.board.FIX_UNITS_FILE).write_text("{broken", encoding="utf-8")
            out = self.finish()
            self.assertIn("fix の出力を組めない", out["groups"][0]["reason"])
            self.assertEqual((out["ok"], out["stop_reason"], out["groups"][0]["unrestored"]), (False, stopby.UNRESTORED, ["stats.py"]))
            (self.place / self.board.FIX_UNITS_FILE).unlink()
        with self.subTest("当たったままの組の無い run の止めの語は空"):
            self.collect_place()
            out = self.finish()
            self.assertEqual((out["ok"], out["stop_reason"]), (True, ""))

    def test_collect_returns_the_contract_when_lib_cannot_be_read(self):
        """lib が読めない run でも、finish は落ちずに約束の形の ok: false を返す（標準ライブラリだけの最後の手）"""
        self.collect_place()
        out = self.without_lib()
        self.assertFalse(out["ok"])
        self.assertEqual(out["diff"]["path"], self.files.COLLECT_ERROR)
        self.assertIn("fix の出力を組めない", (self.place / self.files.COLLECT_ERROR).read_text(encoding="utf-8"))

    def test_collect_fallback_still_points_at_the_beside_files_that_exist(self):
        """#681: lib の読めない finish も、自分が置いた控え（許したテストの変更・受け付けの行）は pointer の欄で返し、ほかの欄は
        null・removed は null・tdd_refused は訳つきの空"""
        out = self.without_lib()
        for field, name in (("allowed_tests", "allowed-tests.json"), ("accept_trace", "accept-trace.json")):
            self.assertEqual(out[field], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": name}, field)
            self.assertTrue((self.place / name).is_file(), name)
        self.assertEqual({k: out[k] for k in ("closure", "tdd_unit", "removed", "frozen", "carry")},
                         dict.fromkeys(("closure", "tdd_unit", "removed", "frozen", "carry")))
        self.assertEqual(out["tdd_refused"]["refused"], [])
        self.assertTrue(out["tdd_refused"]["unread"])

    def test_collect_refused_change_is_not_done(self):
        self.collect_place(ok=False)
        out = self.finish()
        self.assertEqual((out["ok"], out["checked"]), (False, {"ok": False, "reason": "申告が無い"}))
        self.assertEqual(out["reason"], "申告が無い")

    def test_change_check_that_did_not_run_is_not_done(self):
        """assert-changed.json が無い run は ok: false と訳"""
        self.collect_place()
        (self.place / "assert-changed.json").unlink()
        out = self.finish()
        self.assertEqual(out["checked"], {"ok": False, "reason": "assert-changed が走らなかった"})
        self.assertFalse(out["ok"])

    def test_collect_plan_item_ruling_and_objection(self):
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:1"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "plan_items": [1]},
               "replan": "waiting"}
        self.collect_place(conflicts=[row], result_extra={"objection": "判定の単位 A は前提が違う",
                                                          "changed": {**{k: False for k in MARKS}, "premise_drift": True}})
        out = self.finish()
        self.assertEqual(out["replan_items"], ["1"])
        self.assertIn("前提が違う", out["objection"])
        self.assertTrue(out["changed"]["premise_drift"])
        self.assertEqual(out["conflicts"]["path"], "conflicts.json")

    def test_changed_carries_the_premise_drift_note_and_the_x_scalars(self):
        """E42・E17: changed は前提のずれの申告の文 premise_drift_note を組の順につなぎ、x_scalars は修正役が足した x_ の数値を
        名ごとに足す"""
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [1]}], start, par=False)
        for gid, unit, note, xs in (("g1", "A", "上限を 10 に測り直した", {"x_moved": 2}),
                                    ("g2", "B", "", {"x_moved": 3, "x_new_files": 1})):
            write(out_dir / gid / "result.json", result(
                gid, [unit], start, start, changed={**{k: False for k in MARKS}, "premise_drift": bool(note),
                                                    "premise_drift_note": note}, x_scalars=xs))
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": g, "unit_ids": [u], "returned": True, "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))],
            "units": [{"unit_id": u, "group_id": g, "status": "fixed", "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))]})
        write(self.place / "assert-changed.json", {"ok": True, "reason": ""})
        out = self.finish()
        self.assertEqual((out["changed"]["premise_drift"], out["changed"]["premise_drift_note"]), (True, "上限を 10 に測り直した"))
        self.assertEqual(out["x_scalars"], {"x_moved": 5, "x_new_files": 1})

    def test_collect_returns_accepted_breaks(self):
        """F427・L-W20・R23（S03）: 修正役が壊すと分かって通した理由（changes[].breaks.accepted。空白だけは除く）を、戻せた組の子の
        結果（handoffs）と裁定の後の修正役の返答から、出力 handoffs に 1 件 1 行で返す"""
        reply = {"changes": [{"unit_key": "A", "breaks": {"accepted": "古い呼び手の戻り値が変わる"}}]}
        child = self.board.group_result({"group_id": "g1", "unit_ids": ["A"]}, start_tree="t", end_tree="t", tdd=None, reply=reply)
        self.collect_place(result_extra={"handoffs": child["handoffs"]})
        write(self.place / "fix-ruled-reply.json", {"changes": [
            {"unit_key": "B", "breaks": {"accepted": " 設定の既定が変わる\n（人が決める）"}},
            {"unit_key": "C", "breaks": {"accepted": "  "}}]})
        out = self.finish()
        self.assertEqual(out["handoffs"], ["A: 壊すと分かって通した——古い呼び手の戻り値が変わる",
                                           "B: 壊すと分かって通した——設定の既定が変わる （人が決める）"])
        self.assertEqual(child["claimed"], ["A"])
        self.assertEqual(out["ruled_reply"]["path"], "fix-ruled-reply.json")

    CLOSURE_A = {"unit_key": "A", "counts": "defects", "total": 3, "after": 3, "claimed": 1, "covered": 1, "bound": True,
                 "how_from": "判定", "closed": False, "discrepancies": ["申告の site 1 件・数え直しの当たり 3 件"], "out_of_query": []}
    CLOSURE_B = {"unit_key": "B", "counts": "defects", "total": 2, "after": 0, "claimed": 2, "covered": 2, "bound": True,
                 "how_from": "判定", "closed": True, "discrepancies": [], "out_of_query": []}

    def test_collect_writes_the_closure_beside_the_diff(self):
        """F428・R72（S28）: 閉鎖の表（組の子の結果の closure と、裁定の後の段の place の fix-unit-rows.json）と申告の単位
        （claimed）を diff の隣の closure.json に置く"""
        self.collect_place(result_extra={"closure": [self.CLOSURE_A], "claimed": ["A"]})
        write(self.place / "fix-unit-rows.json", {"round": 1, "rows": [self.CLOSURE_B]})
        write(self.place / "fix-ruled-reply.json", {"changes": [{"unit_key": "B"}, {"unit_key": "C"}]})
        out = self.finish()
        doc = json.loads((self.beside(out) / self.files.CLOSURE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"rows": [self.CLOSURE_A, self.CLOSURE_B], "claimed": ["A", "B", "C"]})
        # 閉じたかの読み分け（closure_lines・not_closed）は読み手（report・line）の物。ここは読み手が読む 2 つの欄を縛る:
        # 閉じていない行は A だけ、申告したのに表に行が無い単位は C だけ
        self.assertEqual([r["unit_key"] for r in doc["rows"] if not r["closed"]], ["A"])
        self.assertEqual(sorted(set(doc["claimed"]) - {r["unit_key"] for r in doc["rows"]}), ["C"])

    def test_collect_writes_the_accept_trace_beside_the_diff(self):
        """F013・F041・R37: 受け付けの行を、組の子の結果の accept_trace と place の trace.jsonl の受け付けの行から diff の隣の
        accept-trace.json に置く"""
        import importlib

        import impact
        gates = importlib.import_module("src.gates")
        child = {"op": impact.ACCEPT_TRACE_OP, "ci_left": ["tests/test_slow.py"], "final_left": ["tests/test_far.py"], "final_far": [],
                 "group_id": "g1"}
        self.collect_place(result_extra={"accept_trace": [child]})
        self.board.trace(self.place, gates.SKIPPED_OP, why=["実行器が無い"])
        self.board.trace(self.place, "fix_accepted", node="fix-ruled-accept")
        out = self.finish()
        rows = json.loads((self.beside(out) / self.files.ACCEPT_TRACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual([r["op"] for r in rows], [impact.ACCEPT_TRACE_OP, gates.SKIPPED_OP])
        self.assertEqual((rows[0]["ci_left"], rows[0]["final_left"], rows[1]["why"]),
                         (["tests/test_slow.py"], ["tests/test_far.py"], ["実行器が無い"]))   # 行の読み方（報告の文）は report の試験

    def test_collect_names_the_beside_files_when_it_cannot_build_the_return(self):
        """K13・errors F1・F2: 出力を組めない（place に groups.json が無い）時、閉鎖の表は無く、読み手は無いと名指して 0 件に
        見せない（閉鎖の表の訳は閉じたかを数えていない行）"""
        out = self.finish()
        self.assertFalse(out["ok"])
        self.assertIsNone(out["closure"])   # 読み手（report・line）はこの null を「閉じたかを数えていない」と読む

    def test_collect_takes_units_fixed_after_ruling(self):
        """裁定の後の修正の段が直した単位（place の fix-units.json）は fixed で返る"""
        self.collect_place()
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "not_done", "reason": "申し出で止めた"}]})
        write(self.place / "fix-units.json", {"A": {"status": "fixed", "reason": ""}})
        out = self.finish()
        self.assertEqual(out["units"], [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}])

    def test_join_missing_is_not_done(self):
        """join が控えを残さなかった run は、組の行を返っていないにして ok: false"""
        self.collect_place()
        (self.place / "join.json").unlink()
        out = self.finish()
        self.assertFalse(out["ok"])
        self.assertEqual([(g["group_id"], g["returned"]) for g in out["groups"]], [("g1", False)])
        self.assertEqual(out["reason"], out["groups"][0]["reason"])

    def group_intake(self, out_dir, gid="g2", units=("B",)):
        self.intake(mode="group", group=json.dumps({"group_id": gid, "unit_ids": list(units), "items": []}), out_dir=str(out_dir))

    def test_collect_group_mode_returns_its_own_row(self):
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start))
        self.group_intake(out_dir)
        out = self.finish()
        self.assertEqual(out["units"], [{"unit_id": "B", "group_id": "g2", "status": "fixed", "reason": ""}])
        self.assertTrue(out["ok"])
        self.assertIsNone(out["carry"], "組の形は申し送りを書かない")

    def test_collect_group_mode_takes_only_a_usable_result(self):
        """組の子の自分の結果も 1 つの決まり（board.usable_result）で読む: end_tree の無い結果は返っていない組で、ok: false"""
        start = self.snapshot(self.repo)
        out_dir = self.tmp / "parent" / "groups"
        broken = result("g2", ["B"], start, start)
        del broken["end_tree"]
        write(out_dir / "g2" / "result.json", broken)
        self.group_intake(out_dir)
        out = self.finish()
        self.assertEqual([g["returned"] for g in out["groups"]], [False])
        self.assertFalse(out["ok"])

    def test_standalone_group_reads_its_own_groups_dir(self):
        """out_dir の無い組（単独の run）は自分の place の groups/<gid>/result.json を読む"""
        start = self.snapshot(self.repo)
        write(self.place / "groups" / "g2" / "result.json", result("g2", ["B"], start, start))
        self.intake(mode="group", group=json.dumps({"group_id": "g2", "unit_ids": ["B"], "items": []}),
                    judgment=json.dumps(JUDGMENT, ensure_ascii=False))
        out = self.finish()
        self.assertTrue(out["ok"], out)
        self.assertEqual([g["group_id"] for g in out["groups"]], ["g2"])

    def test_collect_allowed_test_changes_from_rulings_and_groups(self):
        """F429: 許したテストの変更（裁定 fix_test_scope の範囲・組の子が許した物）を allowed_test_changes にパスで並べ、訳を diff の
        隣の allowed-tests.json に [{path, permit, source}] で置く。止めの道と lib の無い道でも、diff の隣に空の [] を置く"""
        ruled = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"],
                 "why_both_cannot_hold": "テストの期待が判定と食い違う", "which_is_right": "request", "kind": "test_vs_request",
                 "status": "ruled", "ruling": {"decision": "fix_test_scope", "text": "期待を直してよい",
                                               "limits": ["test_stats.py:8-9"]}}
        child = {"path": "test_extra.py", "permit": "plan-agreed-2", "source": "consult"}
        self.collect_place(conflicts=[ruled], result_extra={"allowed_tests": [child]})
        out = self.finish()
        self.assertEqual(out["allowed_test_changes"], ["test_extra.py", "test_stats.py"])
        beside = self.beside(out) / self.files.ALLOWED_TESTS_FILE
        self.assertEqual(json.loads(beside.read_text(encoding="utf-8")),
                         [child, {"path": "test_stats.py", "permit": "conflict-ruling-c1-1", "source": "ruling"}])
        self.assertTrue({r["source"] for r in json.loads(beside.read_text(encoding="utf-8"))} <= set(self.board.ALLOWED_SOURCES))
        with self.subTest("止めの道"):
            for name in ("groups.json", "join.json", "allowed-tests.json", "accept-trace.json"):
                (self.place / name).unlink(missing_ok=True)
            out = self.finish()
            self.assertFalse(out["ok"])
            beside = self.beside(out) / self.files.ALLOWED_TESTS_FILE
            self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), [])
            self.assertEqual(json.loads((beside.parent / self.files.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [])
        with self.subTest("lib の無い道"):
            (self.place / "allowed-tests.json").write_text('[{"path": "x"}]', encoding="utf-8")
            (self.place / "accept-trace.json").unlink()
            out = self.without_lib()
            beside = self.beside(out) / self.files.ALLOWED_TESTS_FILE
            self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), [])
            self.assertEqual(json.loads((beside.parent / self.files.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [])

    def test_collect_returns_handoffs_and_mismatched_units(self):
        """最後の関所を開ける理由の 2 欄: handoffs は修正役が人に回した物、mismatched は直したという申告と機械の数え直しが合わない
        単位。組の子の結果の行と、place の裁定の後の返答と閉鎖の表の行を重ねずに並べる。形 group は自分の結果の行だけ、返りを組めない
        道は空"""
        import querytest
        child = {"handoffs": ["A: 壊すと分かって通した——古い呼び出しを捨てる"],
                 "mismatched": ["A: 閉じていない（defects・修正前 3・修正後 1・申告の site 3・問い 判定者）——合わない: 残り 1"]}
        self.collect_place(result_extra=child)
        write(self.place / self.board.RULED_REPLY_FILE, {"changes": [
            {"unit_key": "B", "breaks": {"how": "h", "result": "r", "accepted": "  外の利用者の\n挙動が変わる  "}},
            {"unit_key": "C", "breaks": {"how": "h", "result": "r", "accepted": " "}},
            {"unit_key": "A", "breaks": {"how": "h", "result": "r"}}]})
        write(self.place / querytest.CLOSURE_FILE, {"round": 1, "rows": [
            {"unit_key": "B", "closed": True, "discrepancies": ["申告の数が問いの数と合わない"]},
            {"unit_key": "C", "closed": False, "discrepancies": []}]})
        out = self.finish()
        self.assertEqual(out["handoffs"], [*child["handoffs"], "B: 壊すと分かって通した——外の利用者の 挙動が変わる"])
        self.assertEqual(len(out["mismatched"]), 2, out["mismatched"])
        self.assertEqual(out["mismatched"][0], child["mismatched"][0])
        self.assertTrue(out["mismatched"][1].startswith("B: 閉じた（"), out["mismatched"])
        self.assertIn("合わない: 申告の数が問いの数と合わない", out["mismatched"][1])
        with self.subTest("形 group は自分の結果の行だけ"):
            start = self.snapshot(self.repo)
            out_dir = self.tmp / "parent" / "groups"
            write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start, **child))
            self.group_intake(out_dir)
            out = self.finish()
            self.assertEqual((out["handoffs"], out["mismatched"]), (child["handoffs"], child["mismatched"]))
        with self.subTest("返りを組めない道"):
            self.intake(mode="whole", judgment=json.dumps(JUDGMENT))
            (self.place / "groups.json").unlink()
            out = self.finish()
            self.assertEqual((out["ok"], out["handoffs"], out["mismatched"]), (False, [], []))

    def test_collect_returns_the_titles_the_fixer_wrote_for_handoffs(self):
        """修正役が breaks.accepted_title に書いた短い題は、handoffs の行をキーに handoff_titles で返る（組の子の結果と、裁定の後の返答を
        つなぐ）。題の無い・空白だけの行は入れない（報告の頭は種の名に戻す）"""
        reply = {"changes": [{"unit_key": "A", "breaks": {"accepted": "古い呼び手の戻り値が変わる", "accepted_title": "古い呼び手の戻り値を変える"}}]}
        child = self.board.group_result({"group_id": "g1", "unit_ids": ["A"]}, start_tree="t", end_tree="t", tdd=None, reply=reply)
        self.assertEqual(child["handoff_titles"], {"A: 壊すと分かって通した——古い呼び手の戻り値が変わる": "古い呼び手の戻り値を変える"})
        self.collect_place(result_extra={"handoffs": child["handoffs"], "handoff_titles": child["handoff_titles"]})
        write(self.place / "fix-ruled-reply.json", {"changes": [
            {"unit_key": "B", "breaks": {"accepted": "設定の既定が変わる", "accepted_title": "設定の既定を変える"}},
            {"unit_key": "C", "breaks": {"accepted": "外の利用者に効く", "accepted_title": "  "}},
            {"unit_key": "D", "breaks": {"accepted": "題を書かなかった"}}]})
        out = self.finish()
        self.assertEqual(out["handoff_titles"], {"A: 壊すと分かって通した——古い呼び手の戻り値が変わる": "古い呼び手の戻り値を変える",
                                                  "B: 壊すと分かって通した——設定の既定が変わる": "設定の既定を変える"})
        self.assertEqual(len(out["handoffs"]), 4)

    def test_collect_returns_declared_plan_blocks(self):
        """修正役が直さずに残すと答えた（plan_faces の declared）事前審査の block は、key・why・修正役の答えの 1 行で plan_declared に
        載る。取り込んだ block と suggest は載らず、裁定の後の返答の答えが組の答えに勝つ"""
        self.collect_place()
        why = "古い docstring が直しの後の戻り値を説明しないまま残る"
        write(self.place / self.board.PLAN_REVIEW_FILE, {"faces": [
            {"key": "stale-docstring-left", "severity": "block", "why": why},
            {"key": "absorbed-block-0001", "severity": "block", "why": "取り込んだ穴"},
            {"key": "suggest-left-000001", "severity": "suggest", "why": "参考の穴"},
            {"key": "ruled-block-000001", "severity": "block", "why": "裁定の後に答え直した穴"}], "shrink": []})
        write(self.place / self.board.FIX_REPLY_FILE, {"changes": [], "not_done": [], "plan_faces": [
            {"key": "stale-docstring-left", "handled": "declared", "how": "範囲の外のファイルなので直さずに残す"},
            {"key": "absorbed-block-0001", "handled": "absorbed", "how": "直しに取り込んだ"},
            {"key": "suggest-left-000001", "handled": "declared", "how": "参考なので残す"},
            {"key": "ruled-block-000001", "handled": "declared", "how": "組では残すと答えた"}]})
        write(self.place / self.board.RULED_REPLY_FILE, {"changes": [], "plan_faces": [
            {"key": "ruled-block-000001", "handled": "absorbed", "how": "裁定の後の修正で取り込んだ"}]})
        out = self.finish()
        self.assertEqual(out["plan_declared"], [f"stale-docstring-left: {why}（直す側の答え: 範囲の外のファイルなので直さずに残す）"])

    def test_collect_diff_holds_every_returned_group(self):
        """F424: diff は run の始めの版（base-rev.json）から今の作業ツリーへの累積差分の pointer で、戻せた組の全部の直し（未追跡の
        新しいファイルも）が載り、.archon/ の下は載らない。途中で HEAD が進んでも始めの版から取る。差分が無ければ空の訳のファイル"""
        self.board.record_base_rev(self.place, self.repo)
        start = self.snapshot(self.repo)
        t1 = self.tree_with({"stats.py": (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start))
        self.assertEqual(self.script("join"), {"groups": 2, "returned": 2})
        git(self.repo, "commit", "-qam", "途中で HEAD が進む")
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "run.json").write_text("{}\n", encoding="utf-8")
        out = self.finish()
        self.assertEqual(out["diff"]["path"], self.files.DIFF_FILE)
        diff = (self.art / out["diff"]["path"]).read_text(encoding="utf-8")
        self.assertIn("b/stats.py", diff)
        self.assertIn("/ (len(xs))", diff)
        self.assertIn("b/extra.py", diff)
        self.assertNotIn(".archon", diff)
        with self.subTest("差分が無い"):
            (self.place / self.files.DIFF_FILE).unlink()
            git(self.repo, "reset", "-q", "--hard", self.board.base_rev_of(self.place))
            git(self.repo, "clean", "-qfd", "-e", ".archon")
            out = self.finish()
            self.assertEqual(out["diff"]["path"], self.files.DIFF_NONE_FILE)
            self.assertIn("空", (self.art / out["diff"]["path"]).read_text(encoding="utf-8"))

    def test_collect_conflicts_pointer_only_with_rows(self):
        """F425: conflicts は conflicts.json の pointer で、行が無ければ null。replan_items は裁定 fix_plan_item が誤りとした項目の
        番号（欄 plan_items、無ければその単位の組の項目）"""
        self.collect_place()
        out = self.finish()
        self.assertEqual((out["conflicts"], out["replan_items"]), (None, []))
        self.collect_place(conflicts=[])
        self.assertIsNone(self.finish()["conflicts"], "行の無い conflicts.json は指さない")
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "ruling": {"decision": "fix_plan_item", "text": "項目が誤り", "limits": []}, "replan": "waiting"}
        self.collect_place(conflicts=[row, {**row, "id": "c1-2", "unit_key": "B",
                                             "ruling": {"decision": "ask_human", "text": "人に聞く", "limits": []}}])
        out = self.finish()
        self.assertEqual(out["conflicts"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "conflicts.json"})
        self.assertEqual(out["replan_items"], ["1"], "欄 plan_items の無い裁定はその単位の組の項目")

    def test_collect_never_fails(self):
        def broken_result():
            start = self.snapshot(self.repo)
            out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
            (out_dir / "g1").mkdir(parents=True)
            (out_dir / "g1" / "result.json").write_text("{broken", encoding="utf-8")
            write(self.place / "join.json", {"par": False, "groups": [
                {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
                "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}]})

        def no_intake():
            (self.place / "intake.json").unlink()

        def broken_intake():
            (self.place / "intake.json").write_text("{not json", encoding="utf-8")

        def group_without_result():
            self.intake(mode="group", group='{"group_id": "g9", "unit_ids": ["Z"], "items": []}',
                        judgment=json.dumps(JUDGMENT))
        cases = {"empty_place": lambda: None, "no_intake": no_intake, "broken_intake": broken_intake,
                 "broken_result": broken_result, "group_without_result": group_without_result}
        for name, make in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.art)
                self.art.mkdir()
                self.intake(mode="whole", judgment=json.dumps(JUDGMENT))
                make()
                out = self.finish()
                self.assertFalse(out["ok"])
                reasons = [g["reason"] for g in out["groups"]] + [u["reason"] for u in out["units"]]
                self.assertTrue(any(reasons), out)
                self.assertTrue(out["reason"])


class ReportCase(FinishPlace):
    """出力 report と freeze_off の字（docs/design/fix.md の 11 節）"""

    def two_groups(self, *, ran=True):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": []}], start, par=False)
        tdd = ({"ran": True, "reason": "", "suite": "run.sh", "reused": {}, "units": [TDD_ROW]} if ran
               else {"ran": False, "reason": "実行器が無い", "suite": "", "units": []})
        write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, tdd=tdd))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start))
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": g, "unit_ids": [u], "returned": True, "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))],
            "units": [{"unit_id": u, "group_id": g, "status": "fixed", "reason": ""} for g, u in (("g1", "A"), ("g2", "B"))]})
        write(self.place / "assert-changed.json", {"ok": True, "reason": ""})

    def test_report_and_freeze_off_are_the_lib_lines(self):
        report = lib_report()
        self.two_groups()
        out = self.finish()
        stages = [(f"組 {g['group_id']}", g) for g in out["tdd"]]
        self.assertEqual(out["report"], report.tdd_lines(stages))
        self.assertEqual(out["freeze_off"], report.freeze_lines(stages))
        self.assertEqual(len(out["freeze_off"]), 1, "TDD の輪を回していない組 g2 だけ")
        self.assertIn("組 g2", out["freeze_off"][0])
        self.assertTrue(out["report"][0].startswith("組 g1: 1 単位（赤→緑 1"), out["report"])

    def test_report_without_group_records_names_the_unit_rows(self):
        """組の結果が無く units だけが在れば、成果物の名を持たない字の行と単位の行"""
        rep = kit.load("fix", "report")
        units = [{"unit_id": "A", "group_id": "g1", "status": "not_done", "reason": "x"}]
        self.assertEqual(rep.tdd_lines([], units), [rep.NO_TDD, "  - A: not_done（x）"])
        self.assertEqual(rep.NO_TDD, "組の TDD の記録が無い。修正の出力の単位の行で出す:")
        self.assertEqual(rep.tdd_lines([], []), [])

    def test_report_carries_the_read_evidence(self):
        """読んだ証拠の索引の訳は report の行に「<place の中の相対>: <訳>」で載る（fix-reads が書く物）"""
        self.two_groups()
        got = self.script("fix_reads")
        self.assertTrue(got["ok"], got)
        out = self.finish()
        rep = kit.load("fix", "report")
        self.assertEqual(out["report"][len(out["report"]) - len(rep.evidence_lines(self.place, self.repo)):],
                         rep.evidence_lines(self.place, self.repo))
        self.assertTrue(rep.evidence_lines(self.place, self.repo), "索引が在れば 1 行以上")

    def test_fallback_report_names_the_reason(self):
        out = self.finish()
        self.assertEqual(out["freeze_off"], [])
        self.assertEqual(len(out["report"]), 1)
        self.assertTrue(out["report"][0].startswith("修正の出力を組めない: "), out["report"])


class UnitsReachReportCase(FinishPlace):
    """直す単位ごとの記録が報告と最後の承認ノードに届く（docs/design/fix.md の 12 節の 11）: 出力 units の形と、report の TDD の行が
    report.tdd_lines の字のまま"""

    def test_units_have_the_shape_and_report_quotes_tdd_lines(self):
        report = lib_report()
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A", "B"], "items": []}], start, par=False)
        gave = {**TDD_ROW, "unit_key": "B", "route": "direct", "gave_up": "3 回拒まれた", "green": ""}
        write(out_dir / "g1" / "result.json", result(
            "g1", ["A", "B"], start, start, units=[{"unit_id": "A", "status": "fixed", "reason": ""},
                                                   {"unit_id": "B", "status": "given_up", "reason": "3 回拒まれた"}],
            tdd={"ran": True, "reason": "", "suite": "run.sh", "reused": {}, "units": [TDD_ROW, gave]}))
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A", "B"], "returned": True, "reason": ""}],
            "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""},
                      {"unit_id": "B", "group_id": "g1", "status": "given_up", "reason": "3 回拒まれた"}]})
        write(self.place / "assert-changed.json", {"ok": True, "reason": ""})
        out = self.finish()
        self.assertEqual(out["units"], [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""},
                                        {"unit_id": "B", "group_id": "g1", "status": "given_up", "reason": "3 回拒まれた"}])
        for row in out["units"]:
            self.assertEqual(set(row), {"unit_id", "group_id", "status", "reason"})
        tdd_lines = report.tdd_lines([("組 g1", out["tdd"][0])])
        self.assertEqual(out["report"][:len(tdd_lines)], tdd_lines)
        self.assertEqual(len(tdd_lines), 3, "件数の 1 行と単位ごとの 2 行")
        self.assertIn("TDD を諦めた 1", tdd_lines[0])
        self.assertTrue(tdd_lines[2].startswith("  - B"), tdd_lines)
        self.assertEqual(json.loads((self.art / out["tdd_unit"]["path"]).read_text(encoding="utf-8")), out["tdd"])


class CleanAndChangedCase(FinishPlace):
    """clean・assert-changed（今の BlockScriptsCase の clean.py・assert_changed.py）"""

    def test_clean_keeps_archon_place(self):
        import leftovers
        leftovers.record_ignored(self.place, self.repo)
        (self.repo / ".archon").mkdir()
        (self.repo / ".archon" / "w.pyc").write_bytes(b"x")
        (self.repo / "junk.pyc").write_bytes(b"x")
        self.assertEqual(self.script("clean"), {"ok": True, "count": 1})
        self.assertFalse((self.repo / "junk.pyc").exists())
        self.assertTrue((self.repo / ".archon" / "w.pyc").is_file())

    def assert_case(self, declared, touch):
        start = self.snapshot(self.repo)
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
        reply = write(self.tmp / "reply.json", {"changes": [{"files": declared}]})
        write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, reply_file=str(reply)))
        write(self.place / "join.json", {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}], "units": []})
        for name in touch:
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("changed\n", encoding="utf-8")
        out = self.script("assert_changed")
        self.assertEqual(self.validate(out, node_format("assert-changed")), [], out)
        self.assertEqual(json.loads((self.place / "assert-changed.json").read_text(encoding="utf-8")), out)
        return out

    def test_assert_changed_passes_declared_change(self):
        out = self.assert_case(["stats.py"], ["stats.py", ".archon/run.json"])
        self.assertEqual(out, {"ok": True, "reason": ""})

    def test_assert_changed_names_a_touched_excluded_hunk_once_for_the_whole_tree(self):
        """始めの木から今への変更が並行 PR に回した hunk に触れていれば、誰が書いた変更でも（受け付けを通らない TDD の役・合わせ役の
        変更も）ok: false と hunk を名指す理由で返す。触れていなければ通す"""
        runvals = kit.load("fix", "runvals")
        runvals.write(self.place, {"excluded": [{"pr": 3, "file": "stats.py", "start": 5, "end": 5, "why": "PR 3 が同じ行を書く"}]})
        out = self.assert_case(["stats.py"], ["stats.py"])
        self.assertFalse(out["ok"])
        self.assertIn("並行 PR #3 に回した hunk stats.py:5-5", out["reason"])
        self.restore()
        runvals.write(self.place, {"excluded": [{"pr": 3, "file": "stats.py", "start": 5, "end": 5}]})
        out = self.assert_case(["other.py"], ["other.py"])
        self.assertEqual(out, {"ok": True, "reason": ""})

    def test_assert_changed_does_not_count_archon_place(self):
        out = self.assert_case([".archon/run.json"], [".archon/run.json"])
        self.assertFalse(out["ok"])
        self.assertIn(".archon/run.json", out["reason"])

    def test_assert_changed_refuses_empty_declaration(self):
        out = self.assert_case([], ["stats.py"])
        self.assertFalse(out["ok"])

    def test_assert_changed_without_groups_fails_and_says_why(self):
        """比べの外の誤り（groups.json が無い）は assert-changed.json に訳を書いて落ちる"""
        err = self.run.failing("assert_changed")
        self.assertIn("groups.json", err)
        doc = json.loads((self.place / "assert-changed.json").read_text(encoding="utf-8"))
        self.assertFalse(doc["ok"])
        self.assertIn("変更の確かめが回せない", doc["reason"])

    def test_assert_changed_reads_japanese_and_untracked_names(self):
        """F419: 日本語の名前は git の引用でなくそのままの名で申告と突き合わせ、未追跡の新しいファイルも変わった物に数える。申告した
        のに変わっていないファイルと、テストを走らせただけの木は通さず、落ちずに ok: false と理由を書く"""
        (self.repo / "日本.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "日本.py")
        git(self.repo, "commit", "-qm", "日本")
        out = self.assert_case(["日本.py", "未追跡.py"], ["日本.py", "未追跡.py"])
        self.assertEqual(out, {"ok": True, "reason": ""})
        self.restore()
        with self.subTest("申告したのに変わっていない"):
            out = self.assert_case(["stats.py", "test_stats.py"], ["stats.py"])
            self.assertFalse(out["ok"])
            self.assertIn("test_stats.py", out["reason"])
        self.restore()
        with self.subTest("テストを走らせただけ"):
            run = subprocess.run([sys.executable, "-m", "unittest", "-q"], cwd=self.repo, capture_output=True, text=True,
                                 env={"PATH": os.environ["PATH"]})
            self.assertTrue(list(self.repo.glob("__pycache__/*.pyc")), run.stderr)
            out = self.assert_case(["stats.py"], [])
            self.assertFalse(out["ok"])
            self.assertIn("stats.py", out["reason"])


if __name__ == "__main__":
    unittest.main()
