"""修正の block（workflows/fix/）の全体の形の頭と組の戻し: prep・join・conflict-check の script と、src/board.py の組の分けと戻しの口・
src/lanes.py の試験（docs/design/fix.md の 14.2 の test_join.py）。

今の tests/workflows/test_fix.py の BlockScriptsCase の prep・join・conflict-check の部分、lib/tests/test_lanekit.py、
lib/tests/test_fix_seams.py の GroupScriptsSeamCase を写した。始めの記録の無い使い捨ての run directory（place はその根。単独の run）と
tests/e2e/target-seed/ の写しの git のリポジトリで、port の値だけを渡す。全体の形の prep は intake（mode=whole）の後に回す。
組の子は、子の結果（out_dir/<group_id>/result.json）を試験が書いて模す（今の試験と同じ）。

写さなかった物: 深さ（depth・head_depth・depth_record）の試験、2 度目の修正の置き場（refix-run の place）の試験（2 回目の段は port
prior の束で test_carry.py）、始めの記録を字のまま写す照らし、差分の審査と手直しの brief（delta-review・refix の block の物）、
fixboard.owed_keys（写していない lib の名）と delta_review（差分の審査の欄）。
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock


from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

ROOT = kit.ROOT
SEED = ROOT / "tests" / "e2e" / "target-seed"


def load_src():
    """block の src を読み直す（ほかの block の試験が同じ過程で src の名を差し替えても、この試験の前に fix の物へ戻す）"""
    global board, clash, lanes, runvals, files
    board = kit.load("fix", "board")
    from src import clash, files, lanes, runvals   # noqa: F811


load_src()

import conflict  # noqa: E402  （lib。kit.load の後に届く）
import globs  # noqa: E402
import leftovers  # noqa: E402
import planmarks  # noqa: E402
import planrange  # noqa: E402

MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed", "path_changed")


def write(path, doc):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def result(gid, units, end_tree, start_tree, **extra):
    """組の子の結果 result.json の形（board.group_result が書く欄）"""
    doc = {"group_id": gid, "unit_ids": units, "end_tree": end_tree, "start_tree": start_tree,
           "units": [{"unit_id": k, "status": "fixed", "reason": ""} for k in units],
           "tdd": {"ran": False, "reason": "実行器が無い", "suite": "", "units": []}, "conflicts": [], "objection": "",
           "changed": {k: False for k in MARKS}, "allowed_tests": [], "verified": []}
    doc.update(extra)
    return doc


def recorder_root(tmp):
    """記録の根を持つ隔離した設定の置き場（toolset.install が作る形）。(子の環境に足す物, 記録の根)"""
    import writelog
    cfg = pathlib.Path(tmp) / "claude-config"
    root = writelog.root(cfg)
    root.mkdir(parents=True)
    return {"CLAUDE_CONFIG_DIR": str(cfg)}, root


def record(log, path, tool="Edit"):
    """記録のフックが書く形の 1 行を log に足す"""
    import hashlib
    log.parent.mkdir(parents=True, exist_ok=True)
    real = os.path.realpath(str(path))
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool_name": tool, "path": real,
                            "file_sha": hashlib.sha256(pathlib.Path(real).read_bytes()).hexdigest()}) + "\n")


class Whole(unittest.TestCase):
    """全体の形の place（使い捨ての run directory の根）と target-seed の写しのリポジトリ"""

    def setUp(self):
        load_src()
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.repo = self.run.repo
        self.art = self.run.artifacts
        self.place = self.art
        self.tmp = self.art.parent

    # ---- 助け
    def go(self, name, env_extra=None, **inputs):
        """workflows/fix/scripts/<name>.py を子のプロセスで回す。(終了の値, 標準出力の JSON か None, 標準エラー)"""
        env = hermetic.child_env(**self.run.environ(**inputs), PYTHONDONTWRITEBYTECODE="1", **(env_extra or {}))
        done = subprocess.run([sys.executable, str(kit.BLOCKS / "fix" / "scripts" / f"{name}.py")], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")
        try:
            out = json.loads(done.stdout)
        except ValueError:
            out = None
        return done.returncode, out, done.stderr

    def intake(self, **ports):
        """全体の形の intake（mode=whole）を回し、ok を確かめる"""
        base = {"mode": "whole", "judgment": json.dumps({"units": [], "questions": []})}
        code, out, err = self.go("intake", **{**base, **ports})
        self.assertEqual((code, out["ok"], out["whole"]), (0, True, True), (err, out))
        return out

    def snapshot(self, repo=None):
        return leftovers.snapshot(repo or self.repo)

    def restore(self):
        git(self.repo, "checkout", "-q", "--", ".")
        git(self.repo, "clean", "-qfd")

    def tree_with(self, files_):
        """files を書いた作業ツリーの姿の木を取り、作業ツリーを元に戻す"""
        for name, text in files_.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text, encoding="utf-8")
        tree = self.snapshot()
        self.restore()
        return tree

    def groups_file(self, groups, start_tree, par=True):
        out_dir = self.place / "groups"
        write(self.place / "groups.json", {"groups": groups, "count": len(groups), "par": par,
                                           "start_tree": start_tree, "out_dir": str(out_dir)})
        return out_dir

    def rerun_seed(self, files_, *, test_cmd="", suite_text=None):
        """走らせ直しの種: files を commit し、実行器（suite_text。既定は tests/blocks/fix/support.py の SUITE）を values.json に置き、
        その実行器で取った直す前の結末を place に置く。返りは始めの木"""
        import baseline_red
        from tests.blocks.fix.support import SUITE
        for name, text in files_.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "走らせ直しの種")
        suite = self.tmp / "suite.py"
        suite.write_text(suite_text or SUITE, encoding="utf-8")
        runvals.write(self.place, {"tdd_suite": str(suite), "test_cmd": test_cmd})
        cases, code, why = baseline_red.run_suite(str(suite), self.repo, self.tmp, "base")
        self.assertIsNotNone(cases, why)
        write(self.place / "baseline.json", {"cases": cases, "exit": code})
        return self.snapshot()

    def joined(self):
        return json.loads((self.place / "join.json").read_text(encoding="utf-8"))


class PrepCase(Whole):
    """node prep（全体の形）: intake.json の port の値を place に写し、組を作る"""

    JUDGMENT = {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"},
                          {"key": "C", "label": "suggest", "disposition": "do-now"}, {"key": "D", "label": "suggest"}],
                "questions": []}

    def prep_inputs(self, *, only="", **more):
        return {"mode": "whole", "judgment": json.dumps(self.JUDGMENT, ensure_ascii=False),
                "plan": json.dumps({"round": 1, "fields": [{"allowed_paths": ["a.py"], "out_of_scope": []}, {"allowed_paths": ["c.py"], "out_of_scope": []}]}),
                "fix_plan": json.dumps({"plan": [{"unit_keys": ["A", "B"]}, {"unit_keys": ["C"]}]}),
                "only_items": only, **more}

    def prep(self, env_extra=None, **inputs):
        code, out, err = self.go("intake", **inputs)
        self.assertEqual((code, out["ok"]), (0, True), (err, out))
        return self.go("prep", env_extra=env_extra)

    def test_prep_two_groups_run_side_by_side(self):
        subprocess.run(["git", "remote", "add", "origin", str(self.tmp / "origin.git")], cwd=self.repo, check=True,
                       env=hermetic.child_env())
        code, out, err = self.prep(**self.prep_inputs())
        self.assertEqual(code, 0, err)
        self.assertEqual([(g["unit_ids"], g["items"]) for g in out["groups"]], [(["A", "B"], [1]), (["C"], [2])])
        self.assertTrue(out["par"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["out_dir"], str(self.place / "groups"))
        self.assertEqual(out["start_tree"], self.snapshot())
        for name in (files.VALUES, "judgment.json", "plan-fields.json", board.PLAN_REPLY_FILE,
                     "fix-ignored-before.json", "groups.json", "only-items.json", "base-rev.json"):
            self.assertTrue((self.place / name).is_file(), name)
        self.assertEqual(json.loads((self.place / "groups.json").read_text(encoding="utf-8")), out)

    def test_prep_writes_only_copies_the_children_adopt(self):
        """prep（と intake）が place に書く入力の写しは、組の子が親から写す一覧 board.ADOPTED に全部載る（載らない写しは子で黙って
        空になる）"""
        write(self.tmp / "in" / "ripple.json", {"items": [{"item": 1, "unit_keys": ["A"]}], "overlaps": []})
        write(self.tmp / "in" / "baseline.json", {"cases": [], "exit": 0, "suite": "", "test_cmd": "", "rev": "HEAD"})
        inputs = self.prep_inputs(only='["1"]',
                                  answer_ties=json.dumps({"rounds": {"1": []}}), materials=json.dumps({"ci": {"status": "not_run"}}),
                                  ripple=str(self.tmp / "in" / "ripple.json"), baseline=str(self.tmp / "in" / "baseline.json"),
                                  answers=json.dumps({"decision": "approve", "text": "stats.py の外は触らない"}, ensure_ascii=False),
                                  plan_review=json.dumps({"faces": [], "shrink": []}), notes="## 直した項目 1 の事前審査の穴",
                                  skip_rerun='["A"]')
        code, out, err = self.prep(**inputs)
        self.assertEqual(code, 0, err)
        written = {p.relative_to(self.place).as_posix() for p in self.place.rglob("*") if p.is_file()}
        own = {files.INTAKE, board.GROUPS_FILE, "fix-ignored-before.json", board.marks_path(self.place).name,
               board.TRACE_FILE, planmarks.FIELDS_FILE}
        self.assertEqual(written - own, set(board.ADOPTED))
        self.assertEqual(runvals.read(self.place)["skip_rerun"], ["A"])

    def test_prep_stops_on_broken_answer_ties(self):
        """入力 answer_ties が JSON として読めなければ intake が ok: false と「入力 answer_ties: …」を返し、何も写さない。修正の段の
        読み手は壊れた結びを無いと読み、人の答えを問いに結ぶ行が黙って消えるため（no-silent-loosen）"""
        code, out, err = self.go("intake", **self.prep_inputs(answer_ties='{"rounds": {"1": ['))
        self.assertEqual(code, 0, err)
        self.assertFalse(out["ok"])
        self.assertTrue(out["reason"].startswith("入力 answer_ties: "), out)
        self.assertFalse((self.place / board.TIES_FILE).exists())
        code, _, err = self.go("prep")
        self.assertNotEqual(code, 0, "intake.json の無い place で prep は落ちる")

    def test_prep_takes_the_gate_answers_into_the_duty(self):
        """修正前の関所で答えた問いの単位は直す義務に戻り、答えていない問いの単位は外れる（gatemarks.returned・withheld_by）。
        関所の一言と戻った単位の行は修正役と TDD の役が読む human-notes.md に載る"""
        import gatemarks
        fork = {"key": "q-fork", "kind": "fork", "status": "held", "origin": "B", "reason": "分母はどちらか"}
        held = {"key": "q-esc", "kind": "decision", "status": "escalate", "origin": "C", "reason": "人に上げる"}
        judgment = {**self.JUDGMENT, "questions": [fork, held]}
        answer = {"decision": "continue", "text": "分母は len(xs)", "asked": [gatemarks.ask_text(fork)]}
        code, out, err = self.prep(**self.prep_inputs(judgment=json.dumps(judgment, ensure_ascii=False),
                                                      answers=json.dumps(answer, ensure_ascii=False)))
        self.assertEqual(code, 0, err)
        self.assertEqual([g["unit_ids"] for g in out["groups"]], [["A", "B"]])
        notes = (self.place / "human-notes.md").read_text(encoding="utf-8")
        self.assertIn("分母は len(xs)", notes)
        self.assertIn("q-fork", notes)

    def test_prep_without_remote_runs_in_order(self):
        """子ごとの作業ツリーは remote の既定の枝から切られる（U8 の実測: remote の無いリポジトリでは子を 1 つも起こせない）"""
        code, out, err = self.prep(**self.prep_inputs())
        self.assertEqual(code, 0, err)
        self.assertEqual(out["count"], 2)
        self.assertFalse(out["par"])

    def test_prep_parallel_off_runs_in_order(self):
        """port parallel が偽なら remote が在っても組を並べない（今の機能の切り替え fix_lanes の off の代わり）"""
        subprocess.run(["git", "remote", "add", "origin", str(self.tmp / "origin.git")], cwd=self.repo, check=True,
                       env=hermetic.child_env())
        code, out, err = self.prep(**self.prep_inputs(parallel="false"))
        self.assertEqual(code, 0, err)
        self.assertEqual(out["count"], 2)
        self.assertFalse(out["par"])

    def test_prep_only_items_keeps_their_units(self):
        code, out, err = self.prep(**self.prep_inputs(only='["2"]'))
        self.assertEqual(code, 0, err)
        self.assertEqual([g["unit_ids"] for g in out["groups"]], [["C"]])
        self.assertFalse(out["par"])

    def test_prep_copies_the_fix_plan_from_its_input(self):
        """#681: 修正案の役の返答は port fix_plan の値を自分の名（board.PLAN_REPLY_FILE）で写す。空なら写さない（前の写しも残さない）"""
        write(self.tmp / "elsewhere" / "reply.json", {"plan": [{"unit_keys": ["A", "B"]}, {"unit_keys": ["C"]}], "moved": True})
        code, out, err = self.prep(**self.prep_inputs(fix_plan=str(self.tmp / "elsewhere" / "reply.json")))
        self.assertEqual(code, 0, err)
        self.assertIs(json.loads((self.place / board.PLAN_REPLY_FILE).read_text(encoding="utf-8"))["moved"], True)
        code, out, err = self.prep(**self.prep_inputs(fix_plan=""))
        self.assertEqual(code, 0, err)
        self.assertFalse((self.place / board.PLAN_REPLY_FILE).exists())

    def test_prep_pastes_the_machine_notes(self):
        """P144・L-D35: 入力 notes（2 度目の修正に線が渡す機械の申し送り）は修正役と TDD の役の notes_file（human-notes.md）に載る"""
        notes = "## 直した項目 1（単位 A）の事前審査の穴\n\n- [contract_drift] 穴-分母（stats.py）: 空の列"
        code, out, err = self.prep(**self.prep_inputs(notes=notes))
        self.assertEqual(code, 0, err)
        self.assertIn(notes, (self.place / "human-notes.md").read_text(encoding="utf-8"))

    def test_prep_starts_an_empty_log_when_recorder_root_exists(self):
        import writelog
        env, root = recorder_root(self.tmp)
        log = writelog.log_path(root, self.repo)
        code, out, err = self.prep(env_extra=env, **self.prep_inputs())
        self.assertEqual(code, 0, err)
        self.assertEqual(log.read_text(encoding="utf-8"), "")
        record(log, self.repo / "stats.py")
        code, out, err = self.prep(env_extra=env, **self.prep_inputs())
        self.assertEqual(code, 0, err)
        self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 1, "在る記録は空にしない")
        self.assertEqual((log.parent / writelog.WHERE).read_text(encoding="utf-8"), os.path.realpath(self.repo),
                         "作業の場の控えが無いと、作業の場が消えても起動の片付け（writelog.sweep）が残す")
        shutil.rmtree(self.repo)
        self.assertEqual(writelog.sweep(root), ([log.parent], []))


class JoinCase(Whole):
    """node join（全体の形）: 子の結果を組の順に読み、並べた run は子の差分を親の作業ツリーへ当てて確かめ直す"""

    def test_join_carries_child_records_to_parent(self):
        """並べた子の記録（子の作業ツリーのパス）を、子の差分を当てた親の作業ツリーの記録へ写す。記録の無い子の変更は写さない"""
        import writelog
        import writes
        env, root = recorder_root(self.tmp)
        parent_log = writelog.log_path(root, self.repo)
        parent_log.parent.mkdir()
        parent_log.write_text("", encoding="utf-8")
        start = self.snapshot()
        fixed = (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")
        t1 = self.tree_with({"stats.py": fixed})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        child = self.tmp / "child-g1"
        child.mkdir()
        (child / "stats.py").write_text(fixed, encoding="utf-8")
        record(writelog.log_path(root, child), child / "stats.py")
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, worktree=str(child)))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, worktree=""))
        code, out, err = self.go("join", env_extra=env)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 2})
        rows = [json.loads(ln) for ln in parent_log.read_text(encoding="utf-8").splitlines()]
        carried = [r for r in rows if r["tool_name"] == writes.CARRY_TOOL]
        self.assertEqual([(r["path"], r["from"]) for r in carried],
                         [(os.path.realpath(self.repo / "stats.py"), os.path.realpath(child / "stats.py"))])
        self.assertEqual(writes.unrecorded(self.repo, ["stats.py", "extra.py"], parent_log), ["extra.py"])

    def test_join_carries_a_childs_agreed_scope_to_the_parent(self):
        """組の子の place の範囲の相談の合意（allow の行）は、join が親の place へ group_id つきで写す（deny は写さない）。親が自分で
        聞いた行ではない"""
        start = self.snapshot()
        t1 = self.tree_with({"stats.py": (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")})
        child = self.tmp / "child-place"
        row = {"id": 4, "item": "1", "status": "answered", "decision": "allow", "origin": "",
               "granted_paths": ["extra.py"], "granted_tests": [], "granted_new_tests": [], "reason": "子が記録の定数を足す"}
        board.trace(child, conflict.ASKED_OP, **row)
        board.trace(child, conflict.ASKED_OP, **{**row, "id": 5, "decision": "deny", "granted_paths": ["denied.py"]})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, place=str(child)))
        code, out, err = self.go("join")
        self.assertEqual((code, out), (0, {"groups": 1, "returned": 1}), err)
        self.assertEqual([(r["id"], r["group_id"], r["granted_paths"]) for r in conflict.agreed(self.place)],
                         [(4, "g1", ["extra.py"])])
        self.assertEqual(conflict.plan_asks(self.place), [], "写した行は親が自分で聞いた行ではない")

    def test_join_applies_both_groups_in_order(self):
        start = self.snapshot()
        t1 = self.tree_with({"stats.py": (self.repo / "stats.py").read_text(encoding="utf-8").replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"extra.py": "X = 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 2})
        self.assertIn("/ (len(xs))\n", (self.repo / "stats.py").read_text(encoding="utf-8"))
        self.assertTrue((self.repo / "extra.py").is_file())
        self.assertEqual([u["status"] for u in self.joined()["units"]], ["fixed", "fixed"])

    def test_join_keeps_first_when_second_clashes(self):
        start = self.snapshot()
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        t1 = self.tree_with({"stats.py": src.replace("len(xs) - 1", "len(xs)")})
        t2 = self.tree_with({"stats.py": src.replace("len(xs) - 1", "max(len(xs), 1)")})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        self.assertIn("/ (len(xs))\n", (self.repo / "stats.py").read_text(encoding="utf-8"))
        joined = self.joined()
        g2 = joined["groups"][1]
        self.assertFalse(g2["returned"])
        self.assertIn("当たらない", g2["reason"])
        self.assertEqual(joined["units"][1], {"unit_id": "B", "group_id": "g2", "status": "not_done", "reason": g2["reason"]})
        row, = json.loads((self.place / "clash.json").read_text(encoding="utf-8"))["clashes"]
        self.assertEqual((row["group_id"], row["kind"], row["state"], row["names"]), ("g2", "text", "pending", ["stats.py"]),
                         "字で当たらない組も合わせのループの直し待ちに控える")

    def test_join_stops_on_a_group_without_a_readable_result(self):
        """#576: 結果のファイルが無いか読めない組が在れば、並べない run でも並べた run でも作業ツリーを変えず join.json も書かずに
        1 で止まる（済んだ子の変更を戻して持ち越しにしない）"""
        start = self.snapshot()
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(src.replace("len(xs) - 1", "len(xs)"), encoding="utf-8")
        t1 = self.snapshot()
        for par, broken in ((False, None), (False, {"group_id": "g2"}), (True, None)):
            with self.subTest(par=par, broken=broken):
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []},
                                            {"group_id": "g2", "unit_ids": ["B"], "items": []}], start, par=par)
                write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
                write(out_dir / "g2" / "group-start.json", {"start_tree": t1})
                (out_dir / "g2" / "result.json").unlink(missing_ok=True)
                if broken is not None:
                    write(out_dir / "g2" / "result.json", broken)
                code, out, err = self.go("join")
                self.assertEqual(code, 1, err)
                self.assertIn("g2", err)
                self.assertNotIn("g1", err)
                self.assertEqual(self.snapshot(), t1)
                self.assertFalse((self.place / "join.json").exists())

    def test_join_reruns_fixer_only_group_against_the_earlier_group(self):
        """F411: TDD の名指しの無い組（修正役だけが直した組 g2）も親の木で走らせ直す。前に戻した組 g1 が赤 → 緑を確かめた名指しを
        g2 が赤にすれば、g2 だけを戻して returned: false"""
        start = self.rerun_seed({
            "e.py": "LIMIT = 10\n",
            "a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT + 1)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n"})
        t1 = self.tree_with({"a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT)\n"})
        t2 = self.tree_with({"e.py": "LIMIT = 20\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, verified=["test_a.py::TestA::test_cap"]))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        g1, g2 = self.joined()["groups"]
        self.assertTrue(g1["returned"], g1)
        self.assertFalse(g2["returned"])
        self.assertIn("test_cap", g2["reason"])
        self.assertEqual((self.repo / "e.py").read_text(encoding="utf-8"), "LIMIT = 10\n", "後の組の直しは戻す")
        self.assertIn("min(x, LIMIT)\n", (self.repo / "a.py").read_text(encoding="utf-8"), "前の組の直しは残す")

    def test_join_does_not_carry_a_backed_out_groups_named_tests(self):
        """F411 (1): 戻した組（g2）が赤 → 緑を確かめた名指しは、後の組（g3）の走らせ直しに持ち越さない"""
        start = self.rerun_seed({
            "e.py": "LIMIT = 10\n",
            "a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT + 1)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n",
            "b.py": "def double(x):\n    return x * 2 + 1\n",
            "test_b.py": "import unittest\n\nfrom b import double\n\n\nclass TestB(unittest.TestCase):\n"
                         "    def test_double(self):\n        self.assertEqual(double(2), 4)\n",
            "c.py": "C = 1\n"})
        t1 = self.tree_with({"a.py": "from e import LIMIT\n\n\ndef cap(x):\n    return min(x, LIMIT)\n"})
        t2 = self.tree_with({"e.py": "LIMIT = 20\n", "b.py": "def double(x):\n    return x * 2\n"})
        t3 = self.tree_with({"c.py": "C = 2\n"})
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": [n]}
                                    for n, (g, k) in enumerate((("g1", "A"), ("g2", "B"), ("g3", "C")), 1)], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, verified=["test_a.py::TestA::test_cap"]))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_double"]))
        write(out_dir / "g3" / "result.json", result("g3", ["C"], t3, start))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        rows = {g["group_id"]: g for g in self.joined()["groups"]}
        self.assertEqual({k: g["returned"] for k, g in rows.items()}, {"g1": True, "g2": False, "g3": True}, rows)
        self.assertIn("test_cap", rows["g2"]["reason"])
        self.assertEqual((self.repo / "c.py").read_text(encoding="utf-8"), "C = 2\n", "関わりの無い後の組の直しは親の木に残る")

    def test_join_backs_out_the_later_group_on_a_semantic_clash(self):
        """F412: 2 つの組が同じファイル e.py を違う行で変え、字では合うが、後の組 g2 の直しが前の組 g1 の変えた定数を当てにして
        いて親の木で g2 の名指しが赤: 後の組だけを意味の食い違いとして戻す"""
        filler = "".join(f"# {i}\n" for i in range(10))
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{filler}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": "import unittest\n\nfrom b import triple\n\n\nclass TestB(unittest.TestCase):\n"
                         "    def test_triple(self):\n        self.assertEqual(triple(2), 6)\n"})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{filler}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{filler}E8 = 80\n",
                             "b.py": "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 1\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"]))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 1})
        g1, g2 = self.joined()["groups"]
        self.assertTrue(g1["returned"], g1)
        self.assertFalse(g2["returned"])
        self.assertIn("意味の食い違い", g2["reason"])
        self.assertIn("e.py", g2["reason"])
        self.assertIn("test_triple", g2["reason"])
        self.assertNotIn("backed_out", g1, "当てたままの組は印を持たない")
        self.assertEqual(sorted(g2["backed_out"]), ["b.py", "e.py"], "#383 の 8: 当ててから赤で戻した組は戻したパスを名指す")
        e = (self.repo / "e.py").read_text(encoding="utf-8")
        self.assertIn("E1 = 10\n", e, "前の組は残す")
        self.assertIn("E8 = 8\n", e, "後の組の直しは戻す")
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3 + 1\n")
        [row] = clash.load(self.place)
        self.assertEqual((row["group_id"], row["unit_ids"], row["state"]), ("g2", ["B"], clash.PENDING),
                         "#382: 赤で戻した組は合わせのループの直し待ちに控える")
        self.assertEqual((sorted(row["names"]), row["shared"], row["why"]), (["b.py", "e.py"], ["e.py"], g2["reason"]))
        self.assertEqual(pathlib.Path(row["patch"]), self.place / "join" / "g2.diff")

    def test_join_keeps_a_group_whose_named_test_was_red_the_same_way_before(self):
        """#837: 名指しのテストが当てた後に error でも、直す前の結末で同じテストが同じ失敗の文の error だったなら
        （board.same_red）、組を戻さず、組の行の old_red に「前から赤」として名指す。直す前に緑だった名指しが赤なら今と同じに戻す"""
        from tests.blocks.fix.support import SUITE_WITH_MESSAGE
        start = self.rerun_seed({
            "a.py": "def cap(x):\n    return min(x, 11)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n\n"
                         "    def test_env(self):\n        import no_such_module_837  # noqa: F401\n"},
            suite_text=SUITE_WITH_MESSAGE)
        base = json.loads((self.place / "baseline.json").read_text(encoding="utf-8"))["cases"]
        env_row = next(c for c in base if c["name"] == "test_env")
        self.assertEqual((env_row["outcome"], env_row["fail_message"]), ("error", "No module named 'no_such_module_837'"),
                         "直す前から読み込めずに error")
        t1 = self.tree_with({"a.py": "def cap(x):\n    return min(x, 10)\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start,
                                                     verified=["test_a.py::TestA::test_cap", "test_a.py::TestA::test_env"]))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 1, "returned": 1}, self.joined())
        g1, = self.joined()["groups"]
        self.assertEqual(g1["reason"], "")
        self.assertEqual(len(g1["old_red"]), 1, g1)
        self.assertIn("test_env", g1["old_red"][0])
        self.assertIn("min(x, 10)", (self.repo / "a.py").read_text(encoding="utf-8"), "組の直しは親の木に残る")

    def test_join_compares_new_reds_by_name_on_the_base_even_when_the_suite_picks_by_diff(self):
        """#846: 実行器が走らせる試験を差分から選ぶ形（差分の無い直す前の版の写しでは既定で何も回さない）でも、確かめ直しの 2 段目は
        直す前の結末に無い赤を直す前の版で名指しで走らせて比べる。名指しを聞く実行器なら、直す前も同じく赤の試験で組を戻さない。
        名指しを聞かない実行器なら比べられないので、組を戻さず、組の行の uncompared に名指す（報告が人に聞く）。
        #855: 関門が on の test_cmd が組を外した木でも赤なら、組を戻さず、組の行の test_cmd_notes に「前から赤」と書き、finish の
        report に同じ行を出す"""
        from tests.blocks.fix.support import DIFF_SUITE
        for heed in (True, False):
            with self.subTest(heed_named=heed):
                self.setUp()
                red_cmd = self.tmp / "red_cmd.py"
                red_cmd.write_text("raise SystemExit(1)\n", encoding="utf-8")
                start = self.rerun_seed({
                    "a.py": "def cap(x):\n    return min(x, 11)\n",
                    "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                                 "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n\n"
                                 "    def test_env(self):\n        import no_such_module_846  # noqa: F401\n"},
                    suite_text=DIFF_SUITE.replace("{heed}", str(heed)), test_cmd=f"{sys.executable} {red_cmd}")
                self.assertEqual(json.loads((self.place / "baseline.json").read_text(encoding="utf-8"))["cases"], [],
                                 "差分の無い直す前の結末は空（run 96f35545 の小さな直す前の結末と同じく、test_env を持たない）")
                t1 = self.tree_with({"a.py": "def cap(x):\n    return min(x, 10)\n"})
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
                write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, tdd={
                    "ran": False, "reason": "実行器が無い", "suite": "", "units": [], "test_cmd": {"gate": "on"}}))
                code, out, err = self.go("join")
                self.assertEqual(code, 0, err)
                g1, = self.joined()["groups"]
                self.assertTrue(g1["returned"], f"直す前から赤の test_env か test_cmd を理由に組を戻した: {g1}")
                self.assertIn("min(x, 10)", (self.repo / "a.py").read_text(encoding="utf-8"), "組の直しは親の木に残る")
                if heed:
                    self.assertNotIn("uncompared", g1, "名指しで比べられた赤を比べられなかったと言う")
                else:
                    self.assertEqual(g1["uncompared"], ["test_a.TestA::test_env"], g1)
                notes = g1.get("test_cmd_notes") or []
                self.assertEqual([n.startswith("前から赤") for n in notes], [True], g1)
                write(self.place / "assert-changed.json", {"ok": True, "reason": ""})
                self.intake()
                code, out, err = self.go("finish")
                self.assertEqual(code, 0, err)
                self.assertIn(f"組 g1: {notes[0]}", out["report"], out["report"])

    def test_join_still_backs_out_a_named_test_that_was_green_before(self):
        """#837: 直す前に緑だった名指しが当てた後に赤なら、今と同じに組を戻す（old_red は持たない）"""
        from tests.blocks.fix.support import SUITE_WITH_MESSAGE
        start = self.rerun_seed({
            "a.py": "def cap(x):\n    return min(x, 10)\n",
            "test_a.py": "import unittest\n\nfrom a import cap\n\n\nclass TestA(unittest.TestCase):\n"
                         "    def test_cap(self):\n        self.assertEqual(cap(15), 10)\n"},
            suite_text=SUITE_WITH_MESSAGE)
        t1 = self.tree_with({"a.py": "def cap(x):\n    return min(x, 12)\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, verified=["test_a.py::TestA::test_cap"]))
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        g1, = self.joined()["groups"]
        self.assertFalse(g1["returned"], g1)
        self.assertIn("test_cap", g1["reason"])
        self.assertNotIn("old_red", g1)
        self.assertIn("min(x, 10)", (self.repo / "a.py").read_text(encoding="utf-8"), "組の直しは戻す")

    def test_join_does_not_record_a_group_whose_recheck_raised(self):
        """#382: 確かめ直しそのものが落ちた組（board.CHECK_RAISED）は戻すが、合わせのループの直し待ちには控えない"""
        filler = "".join(f"# {i}\n" for i in range(10))
        start = self.rerun_seed({"e.py": f"E1 = 1\n{filler}E8 = 8\n"})
        t1 = self.tree_with({"e.py": f"E1 = 10\n{filler}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{filler}E8 = 80\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, tdd={
            "ran": True, "units": [{"tests": 5, "test_files": ["e.py"]}]}))   # 名指しの並びが壊れていて照らしが落ちる
        code, out, err = self.go("join")
        self.assertEqual(code, 0, err)
        g2 = self.joined()["groups"][1]
        self.assertIn("当てた後の確かめ直しが落ちた", g2["reason"])
        self.assertFalse((self.place / "clash.json").exists())

    def unrestorable_seed(self):
        (self.repo / "pkg").mkdir()
        self.addCleanup(os.chmod, self.repo / "pkg", 0o755)
        return self.rerun_seed({
            "pkg/__init__.py": "",
            "pkg/m.py": "V = 1\n",
            "c.py": "C = 1\n",
            "test_m.py": "import os\nimport unittest\n\nfrom pkg.m import V\n\n\nclass TestM(unittest.TestCase):\n"
                         "    def test_v(self):\n        if V == 2:\n            os.chmod('pkg', 0o555)\n        self.assertEqual(V, 3)\n"})

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も書ける")
    def test_join_keeps_a_group_it_could_not_restore_and_stops_applying(self):
        """#403: 確かめ直しが赤の組 g1 の差分を戻せないと、g1 を当てていないと言わず、当たったままのパスを unrestored に名指して
        止めの文を置き、作業ツリーが信用できないので後の組 g2 は当てない"""
        start = self.unrestorable_seed()
        t1 = self.tree_with({"pkg/m.py": "V = 2\n"})
        t2 = self.tree_with({"c.py": "C = 2\n"})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, verified=["test_m.py::TestM::test_v"]))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start))
        code, out, err = self.go("join")
        os.chmod(self.repo / "pkg", 0o755)
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"groups": 2, "returned": 0})
        g1, g2 = self.joined()["groups"]
        self.assertEqual(g1["unrestored"], ["pkg/m.py"], g1)
        self.assertNotIn("backed_out", g1)
        self.assertIn(board.UNRESTORED_HEAD, g1["reason"])
        self.assertNotIn("当てられない", g1["reason"])
        self.assertEqual((self.repo / "pkg" / "m.py").read_text(encoding="utf-8"), "V = 2\n", "差分は当たったまま")
        self.assertFalse(g2["returned"])
        self.assertEqual(g2["reason"], board.AFTER_UNRESTORED.format(group="g1"))
        self.assertEqual((self.repo / "c.py").read_text(encoding="utf-8"), "C = 1\n", "後の組は当てない")
        self.assertEqual(board.held(self.place), board.HELD.format(groups="g1"))

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も書ける")
    def test_join_that_fails_after_an_unrestored_group_still_leaves_it_held(self):
        """#403: 戻せない組 g1 の後で join 自身が落ちても（戻せた組 g0 の TDD の輪の状態を写せない）、当たったままの組を join.json に
        先に書いてあるので、後の節は held と読み、返す node finish は止めの語 stopby.UNRESTORED で人に回す"""
        import stopby
        start = self.unrestorable_seed()
        t0 = self.tree_with({"c.py": "C = 2\n"})
        t1 = self.tree_with({"pkg/m.py": "V = 2\n"})
        out_dir = self.groups_file([{"group_id": "g0", "unit_ids": ["B"], "items": [2]},
                                    {"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start)
        broken = self.tmp / "g0-state.json"
        broken.write_text("{broken", encoding="utf-8")
        write(out_dir / "g0" / "result.json", result("g0", ["B"], t0, start, tdd_record=str(broken)))
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start, verified=["test_m.py::TestM::test_v"]))
        code, _, err = self.go("join")
        os.chmod(self.repo / "pkg", 0o755)
        self.assertEqual(code, 1, err)
        g0, g1 = self.joined()["groups"]
        self.assertTrue(g0["returned"], g0)
        self.assertEqual(g1["unrestored"], ["pkg/m.py"], g1)
        self.assertEqual(board.held(self.place), board.HELD.format(groups="g1"))
        self.intake()
        code, out, err = self.go("finish")
        self.assertEqual((code, out["ok"], out["stop_reason"]), (0, False, stopby.UNRESTORED), err)

    def added_test(self, name):
        src = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        tail = 'if __name__ == "__main__":'
        return src.replace(tail, f"class {name}(unittest.TestCase):\n    def test_{name.lower()}(self):\n"
                                 f"        self.assertTrue(True)\n\n\n{tail}")

    def test_group_permits_reach_join_and_finish_only_for_an_accepted_reply(self):
        """#286: 修正役の返答を受け付けていない組の子の許しは、join の和（同じテストのファイルへの挿しだけの食い違いを合わせる）にも
        親の finish の返りの allowed_test_changes・diff の隣の allowed-tests.json にも入らない。受け付けた組の許しは両方に入る。
        #304: 形の崩れた許しの行（path の無い行・ALLOWED_SOURCES に無い source）は join も finish も同じ決まりで捨て、join は落ちない"""
        child = {"path": "test_stats.py", "permit": "plan-agreed-2", "source": "consult"}
        malformed = [{"permit": "plan-3", "source": "plan"}, {"path": "test_other.py", "permit": "x-1", "source": "guess"}]
        bad_source = [{"path": "test_stats.py", "permit": "x-1", "source": "guess"}]
        for reply, returned, given, rows, extra in ((None, 1, [child], [], []), ({"changes": []}, 2, [child], [child], []),
                                                    ({"changes": []}, 2, [child], [child], malformed),
                                                    ({"changes": []}, 1, [], [], bad_source)):
            with self.subTest(reply=reply, extra=extra):
                shutil.rmtree(self.art, ignore_errors=True)
                self.restore()
                self.place.mkdir(parents=True)
                permits = board.group_result({"group_id": "g2", "unit_ids": ["B"]}, start_tree="", end_tree="", tdd=None,
                                             reply=reply, allowed_rows=given)["allowed_tests"] + extra
                start = self.snapshot()
                t1, t2 = self.tree_with({"test_stats.py": self.added_test("TestG1")}), \
                    self.tree_with({"test_stats.py": self.added_test("TestG2")})
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                            {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
                write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
                write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, allowed_tests=permits))
                code, out, err = self.go("join")
                self.assertEqual((code, out), (0, {"groups": 2, "returned": returned}), err)
                # finish の置き場（今の collect_place: 組 1 つが戻り、確かめが通った）
                start = self.snapshot()
                out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]}], start, par=False)
                write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, allowed_tests=permits))
                write(self.place / "join.json", {"par": False, "groups": [
                    {"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}],
                    "units": [{"unit_id": "A", "group_id": "g1", "status": "fixed", "reason": ""}]})
                write(self.place / "assert-changed.json", {"ok": True, "reason": ""})
                (self.repo / "stats.py").write_text("X = 2\n", encoding="utf-8")
                self.intake()
                code, out, err = self.go("finish")
                self.assertEqual(code, 0, err)
                self.assertEqual(out["allowed_test_changes"], [r["path"] for r in rows], out)
                beside = (self.art / out["diff"]["path"]).parent / board.ALLOWED_TESTS_FILE
                self.assertEqual(json.loads(beside.read_text(encoding="utf-8")), rows)

    def test_join_drops_malformed_test_files_of_a_child_tdd_unit(self):
        """#319: 組の子の result.json の TDD の単位の test_files に文字列でない要素（null）が混じっても、test_files が並びでない（数）
        時も、join の和は落ちず、文字列の要素だけで組を戻す"""
        start = self.snapshot()
        t1, t2 = self.tree_with({"test_stats.py": self.added_test("TestG1")}), self.tree_with({"test_stats.py": self.added_test("TestG2")})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        tdd = {"ran": True, "reason": "", "suite": "", "units": [{"unit_key": "B", "tests": [], "test_files": ["test_stats.py", None]},
                                                          {"unit_key": "B", "tests": [], "test_files": 5}]}
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, tdd=tdd))
        code, out, err = self.go("join")
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 2}), err)

    def test_join_reads_a_malformed_child_tdd_as_empty(self):
        """#342: 組の子の result.json の tdd が dict でない（並び・文字列）時も、units が並びでない（数）時も、verified・
        allowed_tests が並びでない（数・文字列）時も、join は落ちず、TDD の単位・名指し・許しの無い組として戻す"""
        start = self.snapshot()
        tdds = {"g1": ["x"], "g2": "x", "g3": {"ran": True, "reason": "", "suite": "", "units": 5, "test_cmd": ["x"]}}
        broken = {"g1": {"verified": 5, "allowed_tests": 5}, "g2": {"verified": "test_x", "allowed_tests": "x"}, "g3": {}}
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [g.upper()], "items": [i]} for i, g in enumerate(tdds, 1)], start)
        for g, tdd in tdds.items():
            end = self.tree_with({f"{g}.md": f"{g}\n"})
            write(out_dir / g / "result.json", result(g, [g.upper()], end, start, tdd=tdd, **broken[g]))
        code, out, err = self.go("join")
        self.assertEqual((code, out), (0, {"groups": 3, "returned": 3}), err)


class ConflictCheckCase(Whole):
    """node conflict-check（全体の形）: 子と join が集めた食い違いの申し出の名指しを現物で照らし、在る申し出を conflicts.json に積む"""

    def joined_rows(self, rows, par=False):
        write(self.place / "join.json", {"par": par, "units": [], "groups": rows})

    def test_conflict_check_gathers_child_claims_and_goes(self):
        """F208: 組を戻した後、戻せた組の子の申し出（結果の conflicts）を親の place の conflicts.json に集める。名指した行が親の作業
        ツリーに無くなった申し出は積まずに conflicts-dropped.json に名指し、戻せなかった組の申し出は裁かない。裁く申し出が在る時だけ
        go: true（裁定の輪を回す）"""
        claim = {"unit_key": "A", "between": ["stats.py:9", "test_stats.py:8"], "why_both_cannot_hold": "期待と判定が食い違う",
                 "which_is_right": "request", "kind": "test_vs_request", "source": "tdd"}
        gone = {**claim, "unit_key": "B", "between": ["stats.py:900", "test_stats.py:8"]}
        start = self.snapshot()
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))],
                                   start, par=False)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, conflicts=[claim]))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start, conflicts=[gone]))
        write(out_dir / "g3" / "result.json", result("g3", ["C"], start, start, conflicts=[{**claim, "unit_key": "C"}]))
        self.joined_rows([{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                          {"group_id": "g2", "unit_ids": ["B"], "returned": True, "reason": ""},
                          {"group_id": "g3", "unit_ids": ["C"], "returned": False, "reason": "当たらない"}])
        code, out, err = self.go("conflict_check")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, {"go": True, "count": 1})
        items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["source"], r["status"]) for r in items], [("A", "tdd", "parked")])
        dropped = json.loads((self.place / files.CONFLICTS_DROPPED).read_text(encoding="utf-8"))["dropped"]
        self.assertEqual(len(dropped), 1)
        self.assertIn("B", dropped[0])
        with self.subTest("申し出の無い run は裁定の輪を回さない"):
            shutil.rmtree(self.place)
            self.place.mkdir(parents=True)
            out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": []}], start, par=False)
            write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start))
            self.joined_rows([{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""}])
            code, out, err = self.go("conflict_check")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"go": False, "count": 0})
            self.assertFalse((self.place / files.CONFLICTS_DROPPED).exists())
        with self.subTest("当たったままの組が在る run も、先に戻せた組の申し出は積んで名を残し、裁定の輪だけを回さない"):
            shutil.rmtree(self.place)
            self.place.mkdir(parents=True)
            out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"))],
                                       start, par=True)
            write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, conflicts=[claim, {**gone, "unit_key": "A"}]))
            self.joined_rows([{"group_id": "g1", "unit_ids": ["A"], "returned": True, "reason": ""},
                              {"group_id": "g2", "unit_ids": ["B"], "returned": False, "reason": board.UNRESTORED_HEAD,
                               "unrestored": ["x.py"]}], par=True)
            code, out, err = self.go("conflict_check")
            self.assertEqual(code, 0, err)
            self.assertEqual(out, {"go": False, "count": 1})
            items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
            self.assertEqual([(r["unit_key"], r["status"]) for r in items], [("A", "parked")])
            self.assertEqual(len(json.loads((self.place / files.CONFLICTS_DROPPED).read_text(encoding="utf-8"))["dropped"]), 1)

    def test_conflict_check_keeps_claims_citing_their_own_child_place(self):
        """依頼 290: 子の申し出が名指す子の place（結果の place）の brief は、その組の名指しの根に許す。ほかの組の place は許さない。
        brief の無い run の機械の諦め（between が空）は照らさずに積み、役の申し出の空の between は落とす"""
        child = self.tmp / "child-g1"
        child.mkdir()
        (child / "brief-1.md").write_text("# brief\n", encoding="utf-8")
        other = self.tmp / "child-g2"
        other.mkdir()
        giveup = {"unit_key": "A", "between": [f"{child}/brief-1.md:1"], "why_both_cannot_hold": "赤の確かめが 3 回とも通らなかった",
                  "which_is_right": "unknown", "kind": "needs_context", "source": "tdd-gave-up"}
        bare = {**giveup, "unit_key": "C", "between": []}
        start = self.snapshot()
        out_dir = self.groups_file([{"group_id": g, "unit_ids": [k], "items": []} for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))],
                                   start, par=False)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], start, start, conflicts=[giveup], place=str(child)))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], start, start, conflicts=[{**giveup, "unit_key": "B"}],
                                                     place=str(other)))
        write(out_dir / "g3" / "result.json", result("g3", ["C"], start, start, conflicts=[
            bare, {**bare, "unit_key": "D", "source": "tdd"}], place=""))
        self.joined_rows([{"group_id": g, "unit_ids": [k], "returned": True, "reason": ""}
                          for g, k in (("g1", "A"), ("g2", "B"), ("g3", "C"))])
        code, out, err = self.go("conflict_check")
        self.assertEqual(code, 0, err)
        items = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([(r["unit_key"], r["source"]) for r in items], [("A", "tdd-gave-up"), ("C", "tdd-gave-up")])
        dropped = json.loads((self.place / files.CONFLICTS_DROPPED).read_text(encoding="utf-8"))["dropped"]
        self.assertEqual([d.split(":", 1)[0] for d in dropped], ["g2", "g3"])
        self.assertIn("（B）", dropped[0])
        self.assertIn("（D）", dropped[1])


class LanesCase(unittest.TestCase):
    """組の部品（src/lanes.py。lib/lanekit.py の写し）の純粋な口（今の lib/tests/test_lanekit.py）"""

    def setUp(self):
        load_src()

    def test_transitive_and_ordered(self):
        got = lanes.groups([(1, ["a"]), (2, ["b"]), (3, ["a", "c"]), (4, ["c"]), (5, ["d"])])
        self.assertEqual(got, [[1, 3, 4], [2], [5]])

    def test_untagged_alone(self):
        self.assertEqual(lanes.groups([("u1", []), ("u2", None), ("u3", [7])]), [["u1"], ["u2"], ["u3"]])

    def test_later_link_joins_earlier_groups(self):
        self.assertEqual(lanes.groups([("p", [1]), ("q", [2]), ("r", [1, 2])]), [["p", "q", "r"]])

    def test_empty(self):
        self.assertEqual(lanes.groups([]), [])

    def test_after_joins_and_orders_within_group(self):
        """after の対（前, 後）は、タグを共にしない 2 つを同じ組に入れ、組の中で前を先に並べる（rows の順が後→前でも。鎖も通る）"""
        self.assertEqual(lanes.groups([("late", ["x"]), ("early", ["y"])], after=[("early", "late")]), [["early", "late"]])
        self.assertEqual(lanes.groups([("c", []), ("b", []), ("a", [])], after=[("a", "b"), ("b", "c")]), [["a", "b", "c"]])

    def test_after_drops_pairs_outside_rows_and_keeps_rows_order_among_ready(self):
        """rows の外の端を持つ対は捨てる。依存の無い 2 つは rows の順のまま、同時に進めてよい物も rows の位置で並べる"""
        self.assertEqual(lanes.groups([("p", []), ("q", [])], after=[("p", "gone"), ("gone", "q"), ("x", "y")]), [["p"], ["q"]])
        got = lanes.groups([("d", []), ("b", []), ("c", []), ("a", [])], after=[("a", "d"), ("c", "d")])
        self.assertEqual(got, [["c", "a", "d"], ["b"]], "組は rows の先頭の順、組の中は準備できた物を rows の順に並べてから後ろへ")

    def test_earlier_grows_only_with_applied(self):
        seen = []

        def one(lane, earlier):
            seen.append((lane, set(earlier)))
            if lane == "b":
                return lanes.Merge("当たらない", "b.patch", [], [], True)
            return lanes.Merge("", f"{lane}.patch", [f"{lane}.py", "shared.py"], [], False)
        got = lanes.merge_in_order(["a", "b", "c"], one)
        self.assertEqual(seen, [("a", set()), ("b", {"a.py", "shared.py"}), ("c", {"a.py", "shared.py"})])
        self.assertEqual([(lane, m.why) for lane, m in got], [("a", ""), ("b", "当たらない"), ("c", "")])


class GroupBoardCase(unittest.TestCase):
    """src/board.py の組の分けと戻し・返す node の欄の口（今の lib/tests/test_fix_seams.py の GroupScriptsSeamCase）"""

    SKIP = ("vendored/",)

    def setUp(self):
        load_src()
        tmp = tempfile.TemporaryDirectory(prefix="works-fix-join-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()

    def test_usable_result_is_the_one_group_rule(self):
        """#594: 組の子が使える結果を残したかは 1 つの決まり。JSON の dict で end_tree が文字列の時だけその dict、ほかは None"""
        gdir = self.tmp / "out" / "g1"
        self.assertIsNone(board.usable_result(gdir))
        gdir.mkdir(parents=True)
        for text in ("{", "[]", "{}", '{"end_tree": 1}'):
            with self.subTest(result=text):
                (gdir / board.RESULT_FILE).write_text(text, encoding="utf-8")
                self.assertIsNone(board.usable_result(gdir))
        (gdir / board.RESULT_FILE).write_text('{"end_tree": "t"}', encoding="utf-8")
        self.assertEqual(board.usable_result(gdir), {"end_tree": "t"})

    def test_halted_groups_and_drop_unreturned_follow_the_rule(self):
        """#594: 始めの記録が在り使える結果の無い組（結果が壊れていても）は止まった組で、戻す。始めの記録より前に落ちた組は
        止まった組でなく、木に触らない。使える結果の在る組は止まった組でなく、戻さない"""
        out = self.tmp / "out"
        start = leftovers.snapshot(self.repo)
        (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
        broken, unstarted, returned = out / "g1", out / "g2", out / "g3"
        for g in (broken, unstarted, returned):
            g.mkdir(parents=True)
        for g in (broken, returned):
            (g / board.GROUP_START_FILE).write_text(json.dumps({"start_tree": start}), encoding="utf-8")
        (broken / board.RESULT_FILE).write_text("{", encoding="utf-8")
        (returned / board.RESULT_FILE).write_text(json.dumps({"end_tree": start}), encoding="utf-8")
        self.assertEqual(board.halted_groups(out, "g9"), ["g1"])
        self.assertEqual(board.drop_unreturned(self.repo, unstarted), [])
        self.assertEqual(board.drop_unreturned(self.repo, returned), [])
        self.assertTrue((self.repo / "half.py").is_file())
        self.assertEqual(board.drop_unreturned(self.repo, broken), ["half.py"])
        self.assertFalse((self.repo / "half.py").exists())

    def test_child_allowed_rows_share_the_row_check_with_finish(self):
        """#304: 組の子の結果の許しの訳は join の和と finish（allowed_test_rows）が同じ口で読む。path・permit の無い行と
        ALLOWED_SOURCES に無い source の行はどちらにも入らない"""
        good = {"path": "tests/t.py", "permit": "plan-1", "source": "plan"}
        res = {"allowed_tests": [good, {"permit": "plan-2", "source": "plan"}, {"path": "tests/u.py", "source": "plan"},
                                 {"path": "tests/v.py", "permit": "x-1", "source": "guess"}, {"path": "", "permit": "p", "source": "plan"},
                                 {"path": 7, "permit": "p", "source": "plan"}, {"path": "tests/w.py", "permit": 3, "source": "plan"},
                                 "壊れた行", good]}
        self.assertEqual(board.child_allowed_rows(res), [good, good])
        self.assertEqual(board.allowed_test_rows(self.place, [res]), [good])
        self.assertEqual((board.child_allowed_rows(None), board.child_allowed_rows({"allowed_tests": None})), ([], []))
        self.assertEqual([board.child_allowed_rows({"allowed_tests": v}) for v in (5, "tests/t.py", good)], [[], [], []])

    def test_fix_groups_join_units_through_items(self):
        items = [{"item": 1, "unit_keys": ["A", "C"]}, {"item": 2, "unit_keys": ["C", "D"]}, {"item": 3, "unit_keys": ["B"]}]
        got = board.fix_groups(["A", "B", "C", "D", "E"], items)
        self.assertEqual([(g["group_id"], g["unit_ids"], g["items"]) for g in got],
                         [("g1", ["A", "C", "D"], [1, 2]), ("g2", ["B"], [3]), ("g3", ["E"], [])])
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["A", "B", "C"], items, ["3"])], [["B"]])
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["A", "B"], None)], [["A"], ["B"]])

    def test_fix_groups_put_dependent_items_in_one_group_in_order(self):
        """項目 2 が項目 1 の単位 A に依る時、owed が [B, A] でも組は 1 つで、unit_ids は [A, B]。依存の無い項目は別の組"""
        items = [{"item": 1, "unit_keys": ["A"]},
                 {"item": 2, "unit_keys": ["B"], "depends_on": [{"unit": "A", "receives": ["stats.py"]}]},
                 {"item": 3, "unit_keys": ["C"]}]
        got = board.fix_groups(["B", "C", "A"], items)
        self.assertEqual([(g["unit_ids"], g["items"]) for g in got], [(["A", "B"], [1, 2]), (["C"], [3])])

    def test_fix_groups_keep_order_through_units_left_out_by_only_items(self):
        """依存が A→B→C で、only_items が B の項目を外した時、組は [A, C] の順で 1 つになる"""
        items = [{"item": 1, "unit_keys": ["A"]},
                 {"item": 2, "unit_keys": ["B"], "depends_on": [{"unit": "A", "receives": ["a.py"]}]},
                 {"item": 3, "unit_keys": ["C"], "depends_on": [{"unit": "B", "receives": ["b.py"]}]}]
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["C", "B", "A"], items, ["1", "3"])], [["A", "C"]])
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["C", "B", "A"], items)], [["A", "B", "C"]])

    def test_fix_groups_join_items_whose_ranges_meet(self):
        items = [{"item": 1, "unit_keys": ["A"], "allowed_paths": ["lib/a.py"]},
                 {"item": 2, "unit_keys": ["B"], "allowed_paths": ["lib/*.py"]},
                 {"item": 3, "unit_keys": ["C"], "allowed_paths": ["docs/x.md"]},
                 {"item": 4, "unit_keys": ["D"]},
                 {"item": 5, "unit_keys": ["E"], "allowed_paths": ["lib/a.py"]}]
        got = board.fix_groups(["A", "B", "C", "D", "E"], items)
        self.assertEqual([(g["unit_ids"], g["items"]) for g in got],
                         [(["A", "B", "E"], [1, 2, 5]), (["C"], [3]), (["D"], [4])])
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["A", "B", "C", "D", "E"], items, ["1", "3"])], [["A"], ["C"]])

    def test_fix_groups_join_items_whose_test_files_meet(self):
        items = [{"item": 1, "unit_keys": ["A"], "allowed_paths": ["lib/a.py", ""],
                  "tests": [{"id": "tests/test_s.py::Case::test_a"}]},
                 {"item": 2, "unit_keys": ["B"], "allowed_paths": ["lib/b.py"],
                  "rewrite_tests": [{"id": "tests/test_s.py::Case::test_b"}]},
                 {"item": 3, "unit_keys": ["C"], "allowed_paths": ["", "lib/c.py"]}]
        self.assertEqual([g["unit_ids"] for g in board.fix_groups(["A", "B", "C"], items)], [["A", "B"], ["C"]])

    # 項目の範囲の表: テストのファイルの名に * ? [ を含む行・rewrite_tests だけの項目・空の allowed_paths の字の行
    RANGE_ITEMS = {
        "bracket": {"item": 1, "unit_keys": ["A"], "allowed_paths": ["lib/a.py", ""], "tests": [{"id": "tests/test_[x].py::Case::test_a"}]},
        "plain": {"item": 2, "unit_keys": ["B"], "allowed_paths": ["tests/test_x.py"]},
        "star": {"item": 3, "unit_keys": ["C"], "rewrite_tests": [{"id": "tests/test_*.py::Case::test_c"}]},
        "mark": {"item": 4, "unit_keys": ["D"], "tests": [{"id": "tests/test_?.py::Case::test_d"}]},
        "glob": {"item": 5, "unit_keys": ["E"], "allowed_paths": ["lib/*.py", "tests/**"]},
    }
    RANGE_PATHS = ["lib/a.py", "lib/b.py", "lib/sub/c.py", "tests/test_[x].py", "tests/test_x.py", "tests/test_*.py",
                   "tests/test_a.py", "tests/test_?.py", "tests/sub/test_x.py", ""]

    def test_fix_groups_join_items_only_when_inside_shares_a_path(self):
        """組分けは項目の範囲を planrange.inside と同じ読みで見る: inside が共にパスを入れる項目の単位は同じ組、共有するパスの無い
        項目は別の組"""
        items = [self.RANGE_ITEMS["bracket"], self.RANGE_ITEMS["plain"],
                 {"item": 3, "unit_keys": ["C"], "allowed_paths": ["lib/*.py"]},
                 {"item": 4, "unit_keys": ["D"], "allowed_paths": ["docs/x.md"]}]
        got = board.fix_groups(["A", "B", "C", "D"], items)
        shared = {(a["item"], b["item"]) for i, a in enumerate(items) for b in items[i + 1:]
                  if any(planrange.inside(p, a) and planrange.inside(p, b) for p in self.RANGE_PATHS + ["docs/x.md"] if p)}
        joined = {(a, b) for g in got for i, a in enumerate(g["items"]) for b in g["items"][i + 1:]}
        self.assertEqual(shared, {(1, 3)})
        self.assertEqual(joined, shared)
        self.assertEqual([g["unit_ids"] for g in got], [["A", "C"], ["B"], ["D"]])

    def test_item_globs_match_bracket_names_without_future_warning(self):
        """名に [ を含むテストのファイルの項目の glob は、読む時に re の FutureWarning を出さない"""
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            re.purge()
            for g in planrange.item_globs(self.RANGE_ITEMS["bracket"]):
                globs.glob_match("", g)
        self.assertEqual([str(w.message) for w in seen if issubclass(w.category, FutureWarning)], [])

    def test_parallel_needs_two_groups_and_the_port_and_a_remote(self):
        """並べるのは組が 2 つ以上で、port parallel が真で、remote の在るリポジトリだけ"""
        two = [{"group_id": "g1"}, {"group_id": "g2"}]
        repo = self.tmp / "bare"
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=hermetic.child_env())
        self.assertFalse(board.parallel(two, True, repo))
        subprocess.run(["git", "remote", "add", "origin", str(repo / "origin.git")], cwd=repo, check=True, env=hermetic.child_env())
        self.assertTrue(board.parallel(two, True, repo))
        self.assertFalse(board.parallel(two, False, repo))
        self.assertFalse(board.parallel(two[:1], True, repo))

    def test_join_rows_keep_child_status_only_for_returned_groups(self):
        gs = [{"group_id": "g1", "unit_ids": ["A", "B"]}, {"group_id": "g2", "unit_ids": ["C"]}]
        res = {"units": [{"unit_id": "A", "status": "given_up", "reason": "3 回拒まれた"}]}
        rows, units = board.join_rows(gs, {"g1": (res, True, ""), "g2": (res, False, "当たらない")})
        self.assertEqual([r["returned"] for r in rows], [True, False])
        self.assertEqual([(u["unit_id"], u["status"]) for u in units], [("A", "given_up"), ("B", "not_done"), ("C", "not_done")])
        self.assertEqual(units[2]["reason"], "当たらない")
        rows, _ = board.join_rows(gs[:1], {})
        self.assertEqual(rows[0]["reason"], board.NO_RESULT)

    def test_tdd_units_fill_groups_without_a_loop(self):
        row = {"unit_key": "A"}
        got = board.tdd_units([{"group_id": "g1"}, {"group_id": "g2"}],
                              {"g1": {"tdd": {"ran": True, "reason": "", "suite": "s", "units": [row]}}, "g2": None})
        self.assertEqual(got[0], {"group_id": "g1", "ran": True, "reason": "", "suite": "s", "reused": {}, "related": {}, "units": [row]})
        self.assertEqual((got[1]["ran"], got[1]["units"], got[1]["reason"]), (False, [], board.NO_RESULT))
        got = board.tdd_units([{"group_id": "g1"}, {"group_id": "g2"}],
                              {"g1": {"tdd": ["x"]}, "g2": {"tdd": {"ran": True, "reason": "", "suite": "s", "units": 5}}})
        self.assertEqual([(r["ran"], r["units"]) for r in got], [(False, []), (True, [])], "形の崩れた tdd・units は空で読む（#342）")

    def test_refused_units_name_the_refused_calls(self):
        """tdd.refused_units は、calls のうち ok が偽で phase が runner でない call の unit_key（振り分けの段の空の key は
        ROUTE_REFUSED）"""
        from src import tdd
        calls = [{"n": 1, "phase": "route", "unit_key": "", "ok": False, "runs": 0, "secs": 0.1},
                 {"n": 2, "phase": "route", "unit_key": "", "ok": True, "runs": 0, "secs": 0.1},
                 {"n": 3, "phase": "test", "unit_key": "A", "ok": False, "runs": 1, "secs": 0.1},
                 {"n": 4, "phase": "test", "unit_key": "A", "ok": False, "runs": 1, "secs": 0.1},
                 {"n": 5, "phase": "conflict", "unit_key": "B", "ok": False, "runs": 0, "secs": 0.1},
                 {"n": 6, "phase": "fix", "unit_key": "A", "ok": True, "runs": 1, "secs": 0.1}]
        self.assertEqual(tdd.refused_units(calls), [tdd.ROUTE_REFUSED, "A", "B"])
        self.assertEqual(tdd.refused_units([{"n": 1, "phase": "runner", "unit_key": "A", "ok": False}]), [])
        self.assertEqual(tdd.refused_units([{"n": 1, "phase": "test", "unit_key": "A", "ok": True}]), [])
        self.assertEqual(tdd.refused_units(None), [])
        self.assertEqual(tdd.refused_units([{"ok": False, "phase": "fix", "unit_key": 5}, "x"]), [])

    def test_cited_rows_drop_claims_whose_lines_are_gone(self):
        row = {"unit_key": "A", "between": ["stats.py:9", "test_stats.py:1"], "why_both_cannot_hold": "x" * 12,
               "which_is_right": "code"}
        gone = {**row, "between": ["stats.py:900", "test_stats.py:1"]}
        ok, dropped = board.cited_rows([row, gone, {"unit_key": "B"}], self.repo)
        self.assertEqual(ok, [row])
        self.assertEqual(len(dropped), 2)

    def test_changed_problem_and_declared_files(self):
        self.assertEqual(board.declared_files([{"changes": [{"files": ["./a.py", "b/c.py"]}]}, {"changes": []}], self.repo), ["a.py", "b/c.py"])
        # 絶対パスの申告も受け付け（facts.declared_files）と同じく根からの相対に揃える
        self.assertEqual(board.declared_files([{"changes": [{"files": [str(self.repo / "stats.py")]}]}], self.repo), ["stats.py"])
        with self.assertRaises(ValueError):
            board.declared_files([{"changes": [{"files": [""]}]}], self.repo)
        self.assertEqual(board.changed_problem(["a.py"], ["a.py", "b.py"]), (True, ""))
        ok, why = board.changed_problem(["a.py", "c.py"], ["a.py"])
        self.assertFalse(ok)
        self.assertIn("c.py", why)
        self.assertEqual(board.changed_problem([], ["a.py"]), (False, board.NOT_DECLARED))
        ok, why = board.changed_problem([], [], {"A": "人の答え待ち"})
        self.assertTrue(ok)
        self.assertIn("A（人の答え待ち）", why)

    def test_touched_since_and_run_diff_skip_the_given_head(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "stats.py").write_text("X = 1\n", encoding="utf-8")
        (self.repo / "vendored").mkdir()
        (self.repo / "vendored" / "w.txt").write_text("w\n", encoding="utf-8")
        self.assertEqual(board.touched_since(self.repo, start, self.SKIP), ["stats.py"])
        self.assertEqual(board.touched_since(self.repo, start), ["stats.py", "vendored/w.txt"])
        diff = board.run_diff(self.repo, "HEAD", self.SKIP)
        self.assertIn("b/stats.py", diff)
        self.assertNotIn("vendored", diff)
        self.assertIn("vendored/w.txt", board.run_diff(self.repo))

    def test_diff_file_points_at_the_reason_when_empty_or_unreadable(self):
        place = self.repo.parent / "place"
        path, text, why = board.diff_file(self.repo, lambda: "HEAD", place, "x.diff", "x-none.txt")
        self.assertEqual((path.name, text, why), ("x-none.txt", "", ""))
        self.assertEqual(path.read_text(encoding="utf-8"), board.DIFF_EMPTY.format(base="HEAD") + "\n")

        def no_base():
            raise ValueError("起点が無い")
        path, text, why = board.diff_file(self.repo, no_base, place, "x.diff", "x-none.txt")
        self.assertEqual(text, "")
        self.assertIn("ValueError: 起点が無い", why)
        self.assertEqual(path.read_text(encoding="utf-8"), why + "\n")
        (self.repo / "stats.py").write_text("X = 1\n", encoding="utf-8")
        path, text, why = board.diff_file(self.repo, lambda: "HEAD", place, "x.diff", "x-none.txt")
        self.assertEqual((path.name, why), ("x.diff", ""))
        self.assertEqual(path.read_text(encoding="utf-8"), text)
        self.assertIn("b/stats.py", text)

    def test_finish_fields(self):
        rows = [{"unit_key": "A", "ruling": {"decision": "fix_plan_item", "plan_items": [2]}},
                {"unit_key": "B", "ruling": {"decision": "fix_plan_item"}},
                {"unit_key": "C", "ruling": {"decision": "ask_human"}}]
        self.assertEqual(board.replan_items(rows, [{"unit_ids": ["B"], "items": [3]}]), ["2", "3"])
        marks = board.changed_marks([{"changed": {"gates_changed": True, board.DRIFT_NOTE: "測り直した"}}, None,
                                     {"changed": {board.DRIFT_NOTE: "測り直した"}}])
        self.assertEqual(set(marks), {*board.CHANGED_MARKS, board.DRIFT_NOTE})
        self.assertEqual([k for k, v in marks.items() if v is True], ["gates_changed"])
        self.assertEqual(marks[board.DRIFT_NOTE], "測り直した", "同じ文は 1 度")
        self.assertEqual(board.x_scalars([{"x_scalars": {"x_a": 1, "x_b": "多い"}}, {"x_scalars": {"x_a": 2.5, "x_b": 3}},
                                          {"x_scalars": "壊れた"}, None]), {"x_a": 3.5, "x_b": "多い"})
        self.assertEqual(board.objection([{"objection": "前提が違う"}, {"rejudge_requested": "前提が違う"}, {}]), "前提が違う")
        self.assertEqual(board.allowed_tests(self.place, [{"allowed_tests": [{"path": "t/a.py", "permit": "plan-1",
                                                                              "source": "plan"}]}]), ["t/a.py"])

    def test_changed_marks_or_over_groups_and_ruled(self):
        """F138: 修正役の 6 つの印は、戻せた組の子の結果と裁定の後の返答の論理和"""
        off = {k: False for k in board.CHANGED_MARKS}
        g1 = board.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                reply={**off, "mechanism_changed": True})
        off = {**off, board.DRIFT_NOTE: ""}
        g2 = board.group_result({"group_id": "g2", "unit_ids": []}, start_tree="", end_tree="", tdd=None, reply=dict(off))
        ruled = board.reply_marks({"seams_changed": True})
        self.assertEqual(board.changed_marks([g1, g2, ruled]), {**off, "mechanism_changed": True, "seams_changed": True})
        self.assertEqual(board.changed_marks([g2, board.reply_marks({})]), off)
        self.assertEqual(board.changed_marks([g2, g1]), {**off, "mechanism_changed": True}, "後の組が偽でも前の組の真は残る")

    def test_join_group_applies_and_check_reverts(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        git(self.repo, "clean", "-qfd")
        got = board.join_group(self.repo, start, end, self.place / "g1.diff")
        self.assertEqual((got.why, got.names), ("", ["extra.py"]))
        self.assertTrue((self.repo / "extra.py").is_file())
        git(self.repo, "clean", "-qfd")
        got = board.join_group(self.repo, start, end, self.place / "g1.diff", check=lambda names: "確かめ直しが赤")
        self.assertEqual(got.why, "確かめ直しが赤")
        self.assertFalse((self.repo / "extra.py").exists())
        self.assertIn("extra.py", (self.place / "g1.diff").read_text(encoding="utf-8"))

    def test_tests_moved_names_named_tests_that_differ_from_the_child(self):
        src = (self.repo / "test_stats.py").read_text(encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        unit = {"tests": ["test_stats.py::TestStats::test_mean_of_three"], "test_files": ["test_stats.py"]}
        self.assertEqual(board.tests_moved(self.repo, end, [unit], {"test_stats.py"}), "")
        (self.repo / "test_stats.py").write_text(src.replace("mean([1, 2, 3]), 2", "mean([2, 4]), 3"), encoding="utf-8")
        self.assertIn("test_mean_of_three", board.tests_moved(self.repo, end, [unit], {"test_stats.py"}))
        self.assertEqual(board.tests_moved(self.repo, end, [unit], set()), "")

    def test_join_group_reverts_when_the_check_raises(self):
        start = leftovers.snapshot(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        end = leftovers.snapshot(self.repo)
        git(self.repo, "clean", "-qfd")

        def broken(names):
            raise RuntimeError("地図が引けない")
        got = board.join_group(self.repo, start, end, self.place / "g1.diff", check=broken)
        self.assertFalse((self.repo / "extra.py").exists())
        self.assertIn("RuntimeError: 地図が引けない", got.why)
        self.assertEqual((got.names, got.backed_out, got.unrestored), ([], ["extra.py"], []),
                         "#406: 確かめ直しが落ちて戻した組も、赤で戻した組と同じく戻したパスを名指す")

    def test_join_group_keeps_a_group_it_could_not_restore_as_applied(self):
        """#403: 当てたパスを戻せなければ、組を当てていないと言わず、当たったままのパスと止めの文を返す"""
        from src import common
        start = leftovers.snapshot(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        end = leftovers.snapshot(self.repo)

        def broken(names):
            raise RuntimeError("地図が引けない")
        for check in (lambda names: "確かめ直しが赤", broken):
            with self.subTest(check=check):
                git(self.repo, "clean", "-qfd")
                with mock.patch.object(common, "restore_paths", side_effect=OSError("書けない")):
                    got = board.join_group(self.repo, start, end, self.place / "g1.diff", check=check)
                self.assertTrue((self.repo / "extra.py").is_file())
                self.assertEqual((got.names, got.backed_out, got.unrestored), ([], [], ["extra.py"]))
                self.assertIn(board.UNRESTORED_HEAD, got.why)
                self.assertIn("OSError: 書けない", got.why)

    def test_same_red_is_one_yes_no_rule(self):
        """#837（docs/design/fix.md の 18 節）: 名指しが「前から同じ形で赤」なのは、直す前と当てた後の両方の結末に名指しに当たる行が在り、
        どちらも error で、失敗の文（fail_message）が空でなく同じ時だけ。failure は同じ文でも数えない（後の組が直しを壊して元の赤に
        戻した物と見分けられない）"""
        def row(outcome, message=""):
            return {"classname": "test_a.TestA", "name": "test_x", "outcome": outcome, "fail_message": message}
        t = "test_a.py::TestA::test_x"
        y = "No module named 'yaml'"
        self.assertTrue(board.same_red(t, [row("error", y)], [row("error", y)]))
        no = [(row("failure", "m"), row("failure", "m")), (row("error"), row("error")), (row("passed"), row("error", y)),
              (None, row("error", y)), (row("error", y), None), (row("error", y), row("error", "other")),
              (row("failure", y), row("error", y)), (row("error", y), row("failure", y)), (row("skipped"), row("error", y)),
              (row("error", y), row("passed"))]
        for before, after in no:
            with self.subTest(no=(before, after)):
                self.assertFalse(board.same_red(t, [before] if before else [], [after] if after else []))
        self.assertFalse(board.same_red(t, [{"outcome": "error", "fail_message": y}, "x"], [row("error", y)]), "形の崩れた元の行は当たらない")

    def test_rerun_problem_does_not_blame_named_tests_red_the_same_way_before(self):
        """#837: 確かめ直しで名指しが赤でも、直す前の結末 cases で同じ形の赤（same_red）なら戻す理由にせず old_red に名指す。
        失敗の文が違う・直す前に緑・居ないなら、今と同じに戻す理由"""
        exe = self.tmp / "fixed.py"
        named = ["test_stats.py::TestStats::test_mean_of_three"]

        def suite(message):
            exe.write_text("import sys\nopen(sys.argv[1], 'w').write('<testsuite><testcase classname=\"test_stats.TestStats\" "
                           f"name=\"test_mean_of_three\"><error message=\"{message}\">t</error></testcase></testsuite>')\n"
                           "sys.exit(1)\n", encoding="utf-8")
        base = [{"classname": "test_stats.TestStats", "name": "test_mean_of_three", "outcome": "error", "fail_message": "env"}]
        suite("env")
        kept = []
        self.assertEqual(board.rerun_problem(self.place, self.repo, str(exe), base, named, name="same", old_red=kept), "")
        self.assertEqual(len(kept), 1)
        self.assertIn("test_mean_of_three", kept[0])
        for label, cases, message in (("失敗の文が違う", base, "other"), ("直す前に緑", [{**base[0], "outcome": "passed"}], "env"),
                                      ("直す前は failure", [{**base[0], "outcome": "failure"}], "env"),
                                      ("直す前に居ない", [], "env")):
            with self.subTest(label):
                suite(message)
                kept = []
                got = board.rerun_problem(self.place, self.repo, str(exe), cases, named, name="other", old_red=kept)
                self.assertIn("test_mean_of_three", got)
                self.assertEqual(kept, [])

    def test_rerun_problem_is_empty_without_suite_or_names(self):
        self.assertEqual(board.rerun_problem(self.place, self.repo, "", [], ["t.py::x"]), "")
        self.assertEqual(board.rerun_problem(self.place, self.repo, "run.sh", [], []), "")

    def test_rerun_problem_names_red_unrunnable_and_unreported_tests(self):
        import baseline_red
        from tests.blocks.fix.support import SUITE
        suite = self.tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        named = ["test_stats.py::TestStats::test_mean_of_three"]
        self.assertIn("test_mean_of_three", board.rerun_problem(self.place, self.repo, str(suite), [], named))
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        self.assertEqual(board.rerun_problem(self.place, self.repo, str(suite), [], named), "")
        self.assertIn("走らせられない", board.rerun_problem(self.place, self.repo, str(self.tmp / "no-such.py"), [], named))
        empty = self.tmp / "empty.py"
        empty.write_text("import sys\nopen(sys.argv[1], 'w').write('<testsuite/>')\n", encoding="utf-8")
        self.assertIn("test_mean_of_three", board.rerun_problem(self.place, self.repo, str(empty), [], named),
                      "0 件の結末は通ったと数えない")
        cases, _, why = baseline_red.run_suite(str(suite), self.repo, self.tmp, "base")
        self.assertIsNotNone(cases, why)
        src = stats.read_text(encoding="utf-8")
        with self.subTest("名指しの無い組も、変えたファイルに当たる試験を走らせ直す（F411 の 1）"):
            stats.write_text(src.replace("    return x\n", "    return lo\n"), encoding="utf-8")
            got = board.rerun_problem(self.place, self.repo, str(suite), cases, [], name="fixer-only")
            stats.write_text(src, encoding="utf-8")
            self.assertIn("test_clamp_within_range", got)
            self.assertEqual(board.rerun_problem(self.place, self.repo, str(suite), cases, [], name="fixer-only-green"), "")
        with self.subTest("前の組と重なったファイルから地図が届く試験を足す（F411 の 2）"):
            from unittest import mock
            from src import common
            with mock.patch.object(common, "selected_problems", wraps=common.selected_problems) as seen:
                self.assertEqual(board.rerun_problem(self.place, self.repo, str(suite), cases, named, name="wide",
                                                     shared=["stats.py"]), "")
            self.assertIn("test_stats.py", seen.call_args.kwargs["named"], "地図が届く試験のファイルを名指しに足す")
            self.assertEqual(pathlib.Path(seen.call_args.args[0]), self.place / "wide" / "base.json",
                             "仮の元の結末 base.json を渡す（仮の輪の状態は組まない）")
            self.assertTrue((self.place / "wide" / "accept.json").is_file(), "書き戻しは <name>/accept.json")
        with self.subTest("重なりの在る組の赤は意味の食い違いと名指す"):
            stats.write_text(src.replace("    return x\n", "    return lo\n"), encoding="utf-8")
            got = board.rerun_problem(self.place, self.repo, str(suite), cases, named, name="clash", shared=["stats.py"])
            stats.write_text(src, encoding="utf-8")
            self.assertTrue(got.startswith(board.SEMANTIC_CLASH.split("{")[0]), got)
            self.assertIn("stats.py", got)
            self.assertIn("test_clamp_within_range", got)
        with self.subTest("test_cmd を渡すのは子の関門が on で、走らせ直しを省かない単位が在る組だけ（rerun_cmd・port skip_rerun）"):
            on = {"unit_ids": ["A", "B"], "tdd": {"test_cmd": {"gate": "on"}}}
            self.assertEqual(board.rerun_cmd(self.place, on, " make test "), "make test")
            self.assertEqual(board.rerun_cmd(self.place, {**on, "tdd": {"test_cmd": {"gate": "same_as_suite"}}}, "make test"), "")
            self.assertEqual(board.rerun_cmd(self.place, {**on, "tdd": {"ran": False}}, "make test"), "")
            for tdd in (["x"], "x", {"test_cmd": ["x"]}, {"test_cmd": "on"}):
                self.assertEqual(board.rerun_cmd(self.place, {**on, "tdd": tdd}, "make test"), "make test",
                                 f"関門が読めない子の結果（{tdd!r}）は on と見て走らせ直す")
            runvals.write(self.place, {"skip_rerun": ["A"]})
            self.assertEqual(board.rerun_cmd(self.place, on, "make test"), "make test", "省かない単位 B が在る")
            runvals.write(self.place, {"skip_rerun": ["A", "B"]})
            self.assertEqual(board.rerun_cmd(self.place, on, "make test"), "", "全部の単位が省く単位")
            runvals.write(self.place, {})
        with self.subTest("test_cmd が渡れば緑の後に 1 回走らせ、赤なら戻す理由（F411 の 2）"):
            red = f"{sys.executable} -c \"import sys; sys.exit(3)\""
            got = board.rerun_problem(self.place, self.repo, str(suite), cases, named, name="cmd-red", test_cmd=red)
            self.assertIn("test_cmd", got)
            self.assertTrue((self.place / "cmd-red" / "test-cmd.log").is_file())
            green = f"{sys.executable} -c \"import sys; sys.exit(0)\""
            self.assertEqual(board.rerun_problem(self.place, self.repo, str(suite), cases, named, name="cmd-green",
                                                 test_cmd=green), "")

    def test_rerun_problem_tells_test_cmd_red_apart_on_the_tree_without_the_group(self):
        """#855: 当てた後の test_cmd の赤は、組を当てる前の木 base を渡す呼びでは 1 回で戻さない。組を外した木でも赤なら前から赤、
        外すと緑で走らせ直しに緑が在れば揺れとして cmd_notes に書いて戻さず、3 回とも赤の時だけ戻す。外した木で走らない時は
        uncompared が在れば人に聞き、無ければ戻す。base の無い呼びは今どおり 1 回の赤で戻す。外した木で走らせた後の作業ツリーは
        当てた姿のまま（外した木で出来たファイルも残さない）"""
        from src import common
        from tests.blocks.fix.support import SUITE
        suite = self.tmp / "suite.py"
        suite.write_text(SUITE, encoding="utf-8")
        named = ["test_stats.py::TestStats::test_mean_of_three"]
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        base = common.snapshot(self.repo)
        (self.repo / "applied.txt").write_text("組の直し\n", encoding="utf-8")
        (self.repo / "run.sh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (self.repo / "run.sh").chmod(0o755)
        applied = common.snapshot(self.repo)
        script = self.tmp / "cmd.py"
        script.write_text(
            "import pathlib, sys\n"
            "mode, count = sys.argv[1], pathlib.Path(sys.argv[2])\n"
            "on = pathlib.Path('applied.txt').exists()\n"
            "n = int(count.read_text()) + 1 if count.exists() else 1\n"
            "if on:\n    count.write_text(str(n))\n"
            "else:\n    pathlib.Path('made-on-base.txt').write_text('x')\n"
            "sys.exit({'always': 1, 'group': int(on), 'flaky': int(on and n == 1)}[mode])\n", encoding="utf-8")
        rows = (   # (訳, mode か命令, base を渡すか, uncompared の受け口を渡すか, 戻すか, cmd_notes の頭, uncompared の件数)
            ("外しても赤なら前から赤として戻さない", "always", True, True, False, "前から赤", 0),
            ("外すと緑で走らせ直しに緑が在れば揺れとして戻さない", "flaky", True, True, False, "揺れ", 0),
            ("外すと緑で 3 回とも赤なら戻す", "group", True, True, True, None, 0),
            ("外した木で走らなければ人に聞く", "./run.sh", True, True, False, None, 1),
            ("外した木で走らず受け口も無ければ戻す", "./run.sh", True, False, True, None, 0),
            ("base の無い呼びは 1 回の赤で戻す", "flaky", False, True, True, None, 0),
        )
        for i, (label, mode, with_base, ask, back, note, asked) in enumerate(rows):
            with self.subTest(label):
                count = self.tmp / f"count-{i}"
                cmd = mode if mode.startswith("./") else f"{sys.executable} {script} {mode} {count}"
                notes, unknown = [], []
                got = board.rerun_problem(self.place, self.repo, str(suite), [], named, name=f"cmd-{i}", test_cmd=cmd,
                                          base=base if with_base else "", cmd_notes=notes, uncompared=unknown if ask else None)
                self.assertEqual(bool(got), back, got)
                if back:
                    self.assertIn("test_cmd", got)
                self.assertEqual([n.startswith(note) for n in notes] if note else notes, [True] if note else [], notes)
                self.assertEqual(len(unknown), asked, unknown)
                if mode == "group":
                    self.assertEqual(count.read_text(), "3", "当てた木で 3 回走らせた")
                    self.assertIn("3 回とも赤", got)
                self.assertEqual(common.touched(self.repo, applied, common.snapshot(self.repo)), [], "作業ツリーは当てた姿のまま")
        with self.subTest("戻さなかった文は組の行の test_cmd_notes に置き、修正の報告に 1 件 1 行で出す"):
            from src import report
            rows, _ = board.join_rows([{"group_id": "g1", "unit_ids": []}, {"group_id": "g2", "unit_ids": []}],
                                      {"g1": (None, True, ""), "g2": (None, True, "")}, test_cmd_notes={"g1": ["揺れ: x"]})
            self.assertEqual([g.get("test_cmd_notes") for g in rows], [["揺れ: x"], None])
            self.assertEqual(report.test_cmd_lines(rows), ["組 g1: 揺れ: x"])



class LanekitSeamCase(unittest.TestCase):
    """lanes.groups: 項目を共にする単位は同じ組（推移的）・組の順と組の中の順は入力の順。待ちの列と固定の枝の数は持たない
    （持ち主の決め no-queue。元 lib/tests/test_fix_seams.py の LanekitSeamCase）"""

    def setUp(self):
        load_src()

    def test_groups_units_sharing_items_transitively_in_input_order(self):
        rows = [("u3", ["i1"]), ("u1", ["i2"]), ("u2", ["i1", "i3"]), ("u5", []), ("u4", ["i3"]), ("u6", ["i2"])]
        self.assertEqual(lanes.groups(rows), [["u3", "u2", "u4"], ["u1", "u6"], ["u5"]])

    def test_no_queue_and_no_fixed_lane_count(self):
        for name in ("MAX_LANES", "queue_put", "take"):
            self.assertFalse(hasattr(lanes, name), name)


if __name__ == "__main__":
    unittest.main()
