"""修正の block（workflows/fix/）の形 group の子の run の試験（docs/design/fix.md の 14.2 の test_group.py）。

今の tests/workflows/test_fix.py の GroupChildScriptsCase と lib/tests/test_fix_seams.py の GroupChildSeamCase を写した物。
子の run は port だけを渡して回す: intake（mode group・group・out_dir＝親の place の groups/・from_tree）→ group-start → route-go →
route-prep・route-step → orders → tdd-prep・tdd-step → fix-prep・fix-accept → group-end。親の place は prep が書く写し（intake.json・values.json・judgment.json・baseline.json）を
試験が置く。返りは節の output_format で照らす。テストの実行器は tests/blocks/fix/support.py の SUITE。
写さない物: 深さの上げ直し（unit_depths・頭の深さの控え。port skip_rerun に替わった）、始めの記録の方針の固めた写し（line の仕事。
values.json の policy をそのまま名指す）
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.blocks.fix import support

ROOT = kit.ROOT
BLOCK = kit.BLOCKS / "fix"
SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN = "wf-grp"
GROUP = {"group_id": "g1", "unit_ids": ["stats.py mean: 分母が len(xs) - 1 になっている"], "items": []}
MEAN = GROUP["unit_ids"][0]
NEW_TEST = '''
    def test_mean_of_two(self):
        self.assertEqual(mean([2, 4]), 3)
'''
CHANGED_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                 "path_changed")

runvals = kit.load("fix", "runvals")
if str(ROOT / "lib" / "graphloops") not in sys.path:
    sys.path.append(str(ROOT / "lib" / "graphloops"))
from engine.schema import validate_schema  # noqa: E402


def _src(module: str):
    """src.<module> を読み直す（ほかの block の試験が src を差し替えても、この試験の名を引けるように）"""
    return kit.load("fix", module)


def _nodes() -> dict:
    doc = yaml.safe_load((BLOCK / "works-factory-fix.yaml").read_text(encoding="utf-8"))
    out = {}

    def walk(nodes):   # 入れ子の輪の中まで（書き手の輪 writers-loop の中の修正の輪 fix-loop）
        for node in nodes:
            out[node["id"]] = node
            walk((node.get("loop_group") or {}).get("nodes") or [])
    walk(doc["nodes"])
    return out


NODES = _nodes()


def _write(path, doc):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


def _recorder_root(tmp):
    """記録の根を持つ隔離した設定の置き場（toolset.install が作る形）。(子の環境に足す物, 記録の根)"""
    import writelog
    cfg = pathlib.Path(tmp) / "claude-config"
    root = writelog.root(cfg)
    root.mkdir(parents=True)
    return {"CLAUDE_CONFIG_DIR": str(cfg)}, root


def _record(log, path, tool="Edit"):
    """記録のフックが書く形の 1 行を log に足す"""
    import hashlib
    log.parent.mkdir(parents=True, exist_ok=True)
    real = os.path.realpath(str(path))
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"tool_name": tool, "path": real,
                            "file_sha": hashlib.sha256(pathlib.Path(real).read_bytes()).hexdigest()}) + "\n")


def _change(unit, files, **extra):
    """修正役の返答の changes の 1 行（closure の site は 1 つ。自己申告の欄は tests/blocks/fix/support.py の SELF_REPORT）"""
    from tests.blocks.fix.support import SELF_REPORT
    return {"unit_key": unit, "files": files, "what": "直した", **SELF_REPORT, **extra,
            "closure": {"mechanism": "分母", "fix_mechanism": "len(xs)", "verified_how": "読んだ",
                        "sites": [{"site": f"{files[0]}:9", "red_seen": True}]}}


class GroupChildScriptsCase(unittest.TestCase):
    """形 group の子の run の scripts を一時の対象のリポジトリ（tests/e2e/target-seed/ の写し）と、親の place・子の place（どちらも
    一時の $ARTIFACTS_DIR。include の道の無い単独の run なので place は $ARTIFACTS_DIR そのもの）で子のプロセスで起こす"""

    def setUp(self):
        from tests.blocks.fix.support import SUITE
        self.tmp = hermetic.tmpdir(self, prefix="works-fix-grp-")
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(SUITE, encoding="utf-8")
        self.parent = self.tmp / "parent-art"
        self.out_dir = self.parent / "groups"
        self.out_dir.mkdir(parents=True)
        self.art = self.tmp / "child-art"
        self.art.mkdir()
        self.place = self.art
        self.grp_env = {}
        out = self.run_script("intake", art=self.parent, mode="whole",
                              judgment=json.dumps({"units": [{"key": MEAN, "label": "block"}], "questions": []},
                                                  ensure_ascii=False))
        self.assertTrue(out["ok"], out)
        self.parent_inputs("")

    # ---- 助け
    def parent_inputs(self, suite, **values):
        """親の place に prep が書く写し（values.json・判定・直す前の結末）を置く"""
        runvals.write(self.parent, {"tdd_suite": suite, "reuse_key": RUN, **values})
        _write(self.parent / "judgment.json", {"units": [{"key": MEAN, "label": "block"}], "questions": []})
        _write(self.parent / "baseline.json", {"cases": [], "exit": 1})

    def env(self, art, inputs):
        env = hermetic.child_env()
        env.update({"ARTIFACTS_DIR": str(art), "WORKFLOW_ID": RUN, "WORKS_FACTORY_ROOT": str(ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1", **self.grp_env})
        env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items()})
        return support.variant_return(env)

    def run_script(self, script, *, art=None, ok=True, cwd=None, node=None, **inputs):
        """workflows/fix/scripts/<script>.py を起こす。ok なら返りを JSON で読み、node（既定は script の名の - 綴り）の output_format で
        照らす。ok が偽なら落ちることを見て標準エラーを返す。修正の輪の頭（fix_prep・fix_ruled_prep）の前には、YAML の並びどおり外の輪の頭
        writer_pick を回す（型を選ぶ。済んでいない型の間は何度回しても同じ型）"""
        art = art or self.art
        if script in ("fix_prep", "fix_ruled_prep") and ok:
            self.run_script("writer_pick", art=art, cwd=cwd, node="writer-pick" if script == "fix_prep" else "ruled-writer-pick",
                            **{"pass": "first" if script == "fix_prep" else "ruled"})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=cwd or self.repo,
                              env=self.env(art, inputs), capture_output=True, text=True, encoding="utf-8")
        if not ok:
            self.assertNotEqual(done.returncode, 0, done.stdout)
            return done.stderr
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        nid = node or script.replace("_", "-")
        self.assertEqual(validate_schema(out, NODES[nid]["output_format"]), [], (nid, out))
        return out

    def intake(self, ok=True, **inputs):
        ports = {"mode": "group", "group": json.dumps(GROUP, ensure_ascii=False), "out_dir": str(self.out_dir),
                 "from_tree": "", **inputs}
        out = self.run_script("intake", cwd=None, **ports)
        if ok:
            self.assertEqual((out["ok"], out["whole"]), (True, False), out)
        return out

    def start(self, ok=True, cwd=None, **inputs):
        """子の頭: intake（port を読む）→ group-start"""
        self.intake(**inputs)
        if not ok:
            return self.run_script("group_start", ok=False, cwd=cwd)
        out = self.run_script("group_start", cwd=cwd)
        if not self.run_script("route_go", cwd=cwd)["route"]:
            self.run_script("orders", cwd=cwd)
        return out

    def start_routed(self, cwd=None, **inputs):
        """子の頭から振り分けまで（MEAN を tdd に振る）。輪の状態は振り分けの後に orders が置くので、輪の状態を読む試験はここから始める"""
        out = self.start(cwd=cwd, **inputs)
        if self.loop_phase() == "route":
            self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]}, cwd=cwd)
        return out

    def finish_loop(self, cwd=None):
        """start_routed の後、MEAN の単位を test の赤 → fix の緑まで回して輪を抜ける（輪の記録 record.json は輪が抜ける時に書く。cwd は
        並べた子の作業ツリー）"""
        root = pathlib.Path(cwd) if cwd else self.repo
        test_file = root / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"),
                             encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]}, cwd=cwd)
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)
        stats = root / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"}, cwd=cwd)
        self.assertEqual((got["ok"], got["done"]), (True, True), got)

    def loop_phase(self) -> str:
        """今の段: 振り分けの状態（place の route.json）の段が route なら "route"、輪の状態の段（振り分けの後に orders が置く。無ければ ""）"""
        routed = self.place / "route.json"
        if routed.is_file() and json.loads(routed.read_text(encoding="utf-8")).get("phase") == "route":
            return "route"
        started = json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))
        if not started.get("state_file"):
            return ""
        return json.loads(pathlib.Path(started["state_file"]).read_text(encoding="utf-8"))["phase"]

    def step(self, reply, cwd=None):
        """組の子の順の 1 歩: 段が route なら route-step（済めば注文の node orders。返りの phase は輪の状態の段）、ほかは tdd-step"""
        text = json.dumps(reply, ensure_ascii=False)
        if self.loop_phase() != "route":
            return self.run_script("tdd_step", reply=text, cwd=cwd)
        out = self.run_script("route_step", reply=text, cwd=cwd)
        if not out["done"]:
            return out
        self.run_script("orders", cwd=cwd)
        phase = self.loop_phase()
        return {**out, "done": phase == "done", "phase": phase}

    def tdd_prompt(self):
        return self.run_script("route_prep" if self.loop_phase() == "route" else "tdd_prep")["prompt"]

    def notes(self):
        """親の place に修正前の関所の一言（prep が書く human-notes.md）を置き、子の place に写ったパスを返す"""
        (self.parent / "human-notes.md").write_text("平均の直しは分母だけに留める\n", encoding="utf-8")
        return str(self.place / "human-notes.md")

    def green_loop(self):
        """実行器の在る子の run で TDD の輪を mean の単位の緑まで回し（route → test の赤 → fix の緑）、修正の輪の頭（fix-prep）を
        回す。返りは (テストのファイル, fix-prep の指示。型の block の周は slots のテストの節の行)"""
        self.parent_inputs(str(self.suite))
        self.start()
        self.assertEqual(self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})["phase"], "test")
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"),
                             encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        prep = self.run_script("fix_prep")
        self.assertTrue(prep["go"], prep)
        # 指示は型の block が組むので、fix-prep が渡す slots の材料の字（テストの節の行）を読む
        return test_file, support.slots_of(self.place, prep)["values"]["tests_rows"]

    def accept(self, reply):
        return self.run_script("fix_accept", reply_variant=support.reply_json(reply), consulted="false", iteration="1")

    @staticmethod
    def frozen_line(prompt: str) -> set:
        (line,) = [ln for ln in prompt.splitlines() if ln.startswith("- 凍ったテストのファイル（")]
        return set(re.findall(r"`([^`]+)`", line.split("）: ", 1)[1]))

    def frozen_reason(self, reason: str) -> str:
        b = _src("board")
        head = b.FIX_CHECK_HEAD.format(head=b.FIX_CHECKS["frozen"], cid="frozen", count=1)
        self.assertIn(head, reason)
        return reason.split(head, 1)[1].split("\n## ", 1)[0]

    def parent_groups(self, start_tree):
        b = _src("board")
        b.write_json(self.parent / "groups.json", {"groups": [GROUP], "count": 1, "par": False, "start_tree": start_tree,
                                                   "out_dir": str(self.out_dir)})

    # ---- group-start
    def test_group_start_adopts_the_parent_tree_and_skips_tdd_without_runner(self):
        """from_tree の姿を作業ツリーに写し、親の place の写しを自分の place に写す。実行器の無い run は tdd: false"""
        import leftovers
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        tree = leftovers.snapshot(self.repo)
        git(self.repo, "checkout", "--", "stats.py")
        out = self.start(from_tree=tree)
        self.assertEqual((out["tdd"], out["units"]), (False, 1), out)
        self.assertIn("tdd_suite", out["reason"])
        self.assertIn("/ len(xs)", stats.read_text(encoding="utf-8"), "親の姿の木を写した")
        for name in ("values.json", "judgment.json", "baseline.json", "fix-ignored-before.json",
                     "tdd-start.json"):
            self.assertTrue((self.place / name).is_file(), name)
        self.assertEqual(json.loads((self.place / "values.json").read_text(encoding="utf-8"))["reuse_key"], RUN,
                         "子の values.json は親の物の写し")
        grp = json.loads((self.place / "groups.json").read_text(encoding="utf-8"))
        self.assertEqual((grp["groups"], grp["par"], grp["out_dir"], grp["start_tree"]),
                         ([GROUP], False, str(self.out_dir), tree))
        self.assertEqual(self.run_script("tdd_prep"), {"prompt": "", "go": False, "new_unit": False})
        bad = self.intake(ok=False, group="{}")
        self.assertEqual(bad["ok"], False, bad)
        self.assertTrue(bad["reason"].startswith("入力 group"), bad)

    def test_side_by_side_child_measures_from_the_parent_head(self):
        """並べた子の worktree は origin の枝から切られ、HEAD が親と違う。修正前の版は親の prep が控えた親の HEAD を写して使い、
        子の HEAD からは測らない（親の姿を写しただけの子の累積差分は空）"""
        import leftovers
        parent_head = git(self.repo, "rev-parse", "HEAD")
        _write(self.parent / "base-rev.json", {"rev": parent_head})
        tree = leftovers.snapshot(self.repo)
        (self.repo / "elsewhere.py").write_text("Z = 1\n", encoding="utf-8")
        git(self.repo, "add", "elsewhere.py")
        git(self.repo, "commit", "-qm", "origin の枝にだけ在る commit")
        self.start(from_tree=tree)
        self.assertFalse((self.repo / "elsewhere.py").exists(), "親の姿の木を写した")
        self.assertEqual(_src("board").base_rev_of(self.place), parent_head)
        out = self.run_script("finish")
        self.assertEqual(out["diff"]["path"], "fix-diff-none.txt", out["diff"])

    def test_group_start_in_order_stops_while_an_earlier_child_is_halted(self):
        """#576: 親の作業ツリーで 1 つずつ回る子は、前の組の子が使える結果を残さずに止まっていれば（結果が無いか壊れている）、
        その変更を戻さず何も書かずに 1 で止まる（親の resume が前の子を続きから回す）。前の組が結果を書いていれば今どおり始める"""
        import leftovers
        before = leftovers.snapshot(self.repo)
        (self.out_dir / "g0").mkdir()
        _write(self.out_dir / "g0" / "group-start.json", {"start_tree": before})
        (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
        err = self.start(ok=False)
        self.assertIn("g0", err)
        self.assertEqual((self.repo / "half.py").read_text(encoding="utf-8"), "Y = 1\n")
        self.assertEqual(sorted(p.name for p in self.out_dir.iterdir()), ["g0"])
        self.assertEqual(sorted(p.name for p in (self.out_dir / "g0").iterdir()), ["group-start.json"])
        self.assertEqual(sorted(p.name for p in self.place.iterdir()), ["intake.json", "values.json"],
                         "intake の書いた物のほかは何も書かない")
        (self.out_dir / "g0" / "result.json").write_text("{", encoding="utf-8")
        self.assertIn("g0", self.run_script("group_start", ok=False))
        self.assertEqual((self.repo / "half.py").read_text(encoding="utf-8"), "Y = 1\n")
        _write(self.out_dir / "g0" / "result.json", {"end_tree": before})
        self.run_script("group_start")
        self.assertTrue((self.repo / "half.py").is_file(), "前の組の結果の在る変更は残す")

    def test_group_start_side_by_side_ignores_a_sibling_still_running(self):
        """並べた子は兄弟の組がまだ結果を書いていなくても止まらず、兄弟のフォルダに触らない（兄弟は同時に回っている）"""
        import leftovers
        tree = leftovers.snapshot(self.repo)
        (self.out_dir / "g0").mkdir()
        _write(self.out_dir / "g0" / "group-start.json", {"start_tree": tree})
        self.start(from_tree=tree)
        self.assertEqual(sorted(p.name for p in (self.out_dir / "g0").iterdir()), ["group-start.json"])

    def test_group_start_in_order_drops_its_own_earlier_attempt(self):
        """自分の組の始めの記録が前の試みから残っていれば、前の試みの結果が無くても壊れていても、その木に戻してから始める
        （戻した控えは書かない）"""
        import leftovers
        before = leftovers.snapshot(self.repo)
        self.intake()
        for left in (None, "{"):
            with self.subTest(result=left):
                (self.out_dir / "g1").mkdir(exist_ok=True)
                _write(self.out_dir / "g1" / "group-start.json", {"start_tree": before})
                if left is not None:
                    (self.out_dir / "g1" / "result.json").write_text(left, encoding="utf-8")
                (self.repo / "half.py").write_text("Y = 1\n", encoding="utf-8")
                self.run_script("group_start")
                self.assertFalse((self.repo / "half.py").exists())
                self.assertFalse((self.out_dir / "g1" / "dropped.json").exists())
                began = json.loads((self.out_dir / "g1" / "group-start.json").read_text(encoding="utf-8"))
                self.assertEqual(began["start_tree"], before)

    def test_group_start_alone_places_the_inputs_it_points_to(self):
        """out_dir が空の単独の run は、port の判定と run の値を自分の place に置く（node prep と同じ写し。board.prep）"""
        out = self.start(out_dir="", tdd_suite="", reuse_key="",
                         judgment=json.dumps({"units": [{"key": MEAN, "label": "block"}], "questions": []}, ensure_ascii=False))
        self.assertEqual((out["tdd"], out["units"]), (False, 1), out)
        self.assertEqual(json.loads((self.place / "values.json").read_text(encoding="utf-8"))["reuse_key"], RUN,
                         "reuse_key の既定はこの run の id")
        self.assertEqual(json.loads((self.place / "judgment.json").read_text(encoding="utf-8"))["units"][0]["key"], MEAN)
        grp = json.loads((self.place / "groups.json").read_text(encoding="utf-8"))
        self.assertEqual(grp["out_dir"], str(self.place / "groups"))

    def test_group_start_alone_without_judgment_is_refused_by_intake(self):
        """out_dir の無い group は判定を要る（intake が ok: false と「入力 judgment: …」で返し、group-start は走らない）"""
        out = self.intake(ok=False, out_dir="")
        self.assertEqual(out["ok"], False, out)
        self.assertTrue(out["reason"].startswith("入力 judgment"), out)

    # ---- 子の TDD の輪の状態を親へ（join）
    def test_ruled_accept_runs_the_tests_of_the_tdd_state_the_join_copied(self):
        """子の TDD の輪の記録は組の結果の tdd_record に載り、join が親の place の tdd-<k>/ に写す（2 度回しても写し直さない）。
        親の裁定の後の修正の受け付けは、写した状態の実行器で変更に当たる試験を走らせ、元で緑だった試験を赤にする直しを拒む"""
        import leftovers
        self.parent_inputs(str(self.suite))
        self.start_routed()
        self.finish_loop()
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertTrue(pathlib.Path(result["tdd_record"]).is_file(), result["tdd_record"])
        self.parent_groups(result["start_tree"])
        leftovers.record_ignored(self.parent, self.repo)
        for _ in range(2):
            self.run_script("join", art=self.parent)
        b = _src("board")
        copied = b.ruled_states(self.parent)
        self.assertEqual(copied, (str(self.parent / "tdd-1" / "record.json"),) * 2)
        self.assertFalse((self.parent / "tdd-2").exists())
        record = json.loads((self.parent / "tdd-1" / "record.json").read_text(encoding="utf-8"))
        self.assertEqual((record["adopted_from"], record["summary"]),
                         (result["tdd_record"], str(self.parent / "tdd-1" / "summary.md")), "写し元の印と写し先の要約のパス")
        self.assertTrue((self.parent / "tdd-1" / "summary.md").is_file())
        self.assertEqual(json.loads((self.parent / "tdd-1" / "state.json").read_text(encoding="utf-8"))["work"],
                         str(self.parent / "tdd-1"))
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)")
                         .replace("    return x\n", "    return lo\n"), encoding="utf-8")
        reply = {"changes": [_change(MEAN, ["stats.py"])]}
        out = self.run_script("fix_ruled_accept", art=self.parent, reply_variant=support.reply_json(reply),
                              consulted="false", iteration="1")
        self.assertFalse(out["ok"], out)
        self.assertIn("test_clamp_within_range", out["reason"])

    def test_ruled_accept_rejects_a_rewrite_of_a_test_the_child_loop_froze(self):
        """組の子の輪が凍らせた試験は、join が親へ写した後も凍ったまま: 親の裁定の後の修正の受け付け（fix-ruled-accept）は、子の輪で
        緑にした単位の試験のファイルの既存の行を変えた返答を、凍ったテストの確かめで拒み、そのファイルを名指す（keep-essence の 3。
        写しを消すと board.ruled_states → facts.check_frozen が子の輪の凍結を見失う）"""
        import leftovers
        test_file, _ = self.green_loop()
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.parent_groups(result["start_tree"])
        leftovers.record_ignored(self.parent, self.repo)
        self.run_script("join", art=self.parent)
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("mean([2, 4]), 3)", "mean([2, 4]), 3.0)"),
                             encoding="utf-8")
        out = self.run_script("fix_ruled_accept", art=self.parent, consulted="false", iteration="1",
                              reply_variant=support.reply_json({"changes": [_change(MEAN, ["stats.py", "test_stats.py"])]}))
        self.assertFalse(out["ok"], out)
        self.assertIn("test_stats.py", self.frozen_reason(out["reason"]))

    def test_join_resolves_a_relative_runner_in_the_parent_tree(self):
        """並べた子の worktree で回った輪の状態の実行器（相対パス。自分の place から根を引く）を、join は親の作業ツリーで解き直して
        写す。親の裁定の後の修正の受け付けは親の木で試験を走らせ、元で緑だった試験を赤にする直しを拒む"""
        from tests.blocks.fix.support import SUITE
        (self.repo / "ci").mkdir()
        (self.repo / "ci" / "suite.py").write_text(
            "import os\nos.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))\n" + SUITE, encoding="utf-8")
        git(self.repo, "add", "ci/suite.py")
        git(self.repo, "commit", "-qm", "根を自分の place から引く実行器")
        child = self.tmp / "child-tree"
        git(self.repo, "worktree", "add", "--detach", "--quiet", str(child), "HEAD")
        self.parent_inputs("ci/suite.py")
        self.start_routed(cwd=child)
        self.finish_loop(cwd=child)
        result = json.loads(pathlib.Path(self.run_script("group_end", cwd=child)["result_file"]).read_text(encoding="utf-8"))
        self.parent_groups(result["start_tree"])
        self.run_script("join", art=self.parent)
        state = json.loads((self.parent / "tdd-1" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(pathlib.Path(state["exe"]).resolve(), (self.repo / "ci" / "suite.py").resolve())
        base = json.loads((self.parent / "bases" / "1" / "base.json").read_text(encoding="utf-8"))
        self.assertEqual(pathlib.Path(base["exe"]).resolve(), (self.repo / "ci" / "suite.py").resolve(), "写した元の結末も親の木で解く")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("    return x\n", "    return lo\n"), encoding="utf-8")
        reply = {"changes": [_change(MEAN, ["stats.py"])]}
        out = self.run_script("fix_ruled_accept", art=self.parent, reply_variant=support.reply_json(reply),
                              consulted="false", iteration="1")
        self.assertFalse(out["ok"], out)
        self.assertIn("test_clamp_within_range", out["reason"])

    # ---- 指示の名指し
    def test_fix_prep_names_the_gate_notes(self):
        """修正役の指示は、親から写した修正前の関所の一言のファイルを notes_file に名指す（board.fix_values）"""
        notes = self.notes()
        self.parent_inputs(str(self.suite))   # 実行器の無い組は組の頭が no-suite で止める
        self.start()
        prep = self.run_script("fix_prep")
        self.assertTrue(prep["go"], prep)
        self.assertEqual(support.slots_of(self.place, prep)["values"]["notes_file"], notes, "slots の材料に名指す")
        self.assertIn(notes, support.writer_prompt(self.env(self.art, {}), prep, self.repo), "型の block が組んだ指示にも名指す")

    def test_tdd_prep_names_the_gate_notes(self):
        """TDD の役の指示は、親から写した修正前の関所の一言のファイルを notes_file に名指す"""
        notes = self.notes()
        self.parent_inputs(str(self.suite))
        self.start()
        self.assertIn(notes, self.tdd_prompt())

    def test_tdd_prep_names_the_policy_of_the_run_values(self):
        """TDD の役の指示が名指す方針の文書は、values.json の policy（line が渡した固めた写し）で、子は親の values.json を写す"""
        doc = self.tmp / "frozen-policy.md"
        doc.write_text("- 固めた版\n", encoding="utf-8")
        self.parent_inputs(str(self.suite), policy=str(doc))
        self.start()
        self.assertIn(str(doc), self.tdd_prompt())

    # ---- TDD の輪
    def test_tdd_step_reads_the_recorder_log(self):
        """記録の根が在る run の TDD の輪の受け付けは、group-start が作った作業ツリーの記録を読み、記録の無い変更を拒む"""
        import writelog
        import writes
        env, root = _recorder_root(self.tmp)
        self.parent_inputs(str(self.suite))
        self.grp_env = env
        self.start()
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["phase"]), (True, "test"), got)
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace(
            "\n\nif __name__", NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                 "tests": ["test_stats.py::TestStats::test_mean_of_two"]}
        got = self.step(reply)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(writes.REJECT + "test_stats.py", got["reason"])
        _record(writelog.log_path(root, self.repo), test_file)
        got = self.step(reply)
        self.assertEqual((got["ok"], got["phase"]), (True, "fix"), got)

    def test_tdd_head_reuses_a_green_test_cmd_within_the_run(self):
        """fix の組の子の run の TDD の輪の頭は、同じ run の控え（親の values.json の reuse_dir・reuse_key）から test_cmd の緑を引き、
        同じ run の中で 2 度走らせない。組の子に reuse_dir が届かなければ、自分の place へ黙って倒さずに使い回さない。
        test-gate の base は直す前の版で test_cmd を走らせない（持ち主の決め base-runs-nothing）ので、控えを置くのは最初の組の子"""
        import tree_run
        count = self.tmp / "test-cmd-count"
        test_cmd = f"{sys.executable} -c \"open({str(count)!r}, 'a').write('1\\n')\""
        line = self.tmp / "line-art"
        line.mkdir()
        reuse = str(tree_run.reuse_dir(line))
        gate_ports = {"mode": "base", "test_cmd": test_cmd, "reuse_dir": reuse, "reuse_key": "line-run",
                      "user_env_dir": str(line)}
        env = hermetic.child_env()
        env.update({"ARTIFACTS_DIR": str(line), "WORKFLOW_ID": "line-run", "WORKS_FACTORY_ROOT": str(ROOT),
                    "ARCHON_NODE_EXECUTION": json.dumps({"runId": "line-run", "path": "test-gate-base__run"}),
                    "PYTHONDONTWRITEBYTECODE": "1", **{f"INPUTS_{k.upper()}": v for k, v in gate_ports.items()}})
        for name in ("intake", "run"):
            gate = subprocess.run([sys.executable, str(kit.BLOCKS / "test-gate" / "scripts" / f"{name}.py")], cwd=self.repo,
                                  env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(gate.returncode, 0, gate.stderr)
        self.assertEqual(json.loads(gate.stdout)["runs"], [], gate.stdout)
        self.assertFalse(count.exists(), "test-gate の base が test_cmd を走らせた")
        self.parent_inputs(str(self.suite), test_cmd=test_cmd, reuse_dir=reuse, reuse_key="line-run")
        self.assertEqual(self.start()["tdd"], True)
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 1)
        self.parent_inputs(str(self.suite), test_cmd=test_cmd, reuse_dir=reuse, reuse_key="line-run")
        self.assertEqual(self.run_script("group_start")["tdd"], True)
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 1, "同じ run の控えから引く")
        self.parent_inputs(str(self.suite), test_cmd=test_cmd, reuse_key="line-run")
        self.assertEqual(self.run_script("group_start")["tdd"], True)
        self.assertEqual(len(count.read_text(encoding="utf-8").split()), 2, "reuse_dir の無い組の子は使い回さずに走らせる")

    def test_tdd_head_is_narrowed_only_for_a_run_without_test_cmd_and_declaration(self):
        """持ち主の決め related-tests-only: group-start は related.applies（test_cmd が空で、対象の根に走らせる段の宣言が無い）の時だけ
        輪の頭の元の結末を関わる試験に絞る。test_cmd が在る run は今のまま（状態の related は applied 偽）"""
        def related_of() -> dict:
            return _src("route").read(self.place)["related"]   # 振り分けの状態（輪の状態と同じ元の結末の欄）
        self.parent_inputs(str(self.suite))
        self.assertEqual(self.start()["tdd"], True)
        self.assertTrue(related_of()["applied"], "plan の欄が無くても絞る対象と読む（起点が無いので一式。whole）")
        self.assertTrue(related_of()["whole"])
        self.parent_inputs(str(self.suite), test_cmd="true")
        self.assertEqual(self.start()["tdd"], True)
        self.assertEqual(related_of(), {"applied": False})

    def test_tdd_prep_and_step_route_the_unit_change_between_the_two_roles(self):
        """tdd-prep は 1 周目と単位が替わる周だけ new_unit: true（新しい会話の役 tdd-new）、同じ単位の出し直しは false（続きの役
        tdd）。tdd-step は飛ばされた方の束ね（null）を読まず、起きた方の返答で段を進める（F032）。振り分けは前の loop route-loop
        （route-prep → route-step → 注文の orders）で済ませ、TDD の輪の 1 周目は新しい会話"""
        self.parent_inputs(str(self.suite))
        self.start()
        self.assertIs(self.run_script("route_prep")["go"], True)
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["phase"]), (True, "test"), got)
        self.assertIs(self.run_script("tdd_prep")["new_unit"], True, "振り分けから単位の段へ")
        bad = json.dumps({"phase": "test", "unit_key": MEAN, "test_files": [], "tests": []}, ensure_ascii=False)
        got = self.run_script("tdd_step", reply="null", reply_new=bad)
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        self.assertIs(self.run_script("tdd_prep")["new_unit"], False, "同じ単位の出し直しは続きの会話")
        got = self.run_script("tdd_step", reply=bad, reply_new="null")
        self.assertEqual((got["ok"], got["phase"]), (False, "test"), got)
        state = json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))["state_file"]
        calls = json.loads(pathlib.Path(state).read_text(encoding="utf-8"))["calls"]
        self.assertEqual([c["ok"] for c in calls], [True, False, False], "どちらの束ねの返答も 1 周 1 回の確かめ")

    def test_tdd_step_rejects_a_query_claim_when_the_judgment_is_unreadable(self):
        """TDD の輪の query の申し出も、修正役の受け付けと同じ口（board.judge_query）で試す: place の判定の写しが読めなければ
        「読めない」と名指して拒み、黙って積まない（K15）"""
        b = _src("board")
        self.parent_inputs(str(self.suite))
        self.start()
        self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})
        (self.place / b.JUDGMENT_FILE).unlink()
        got = self.step({"phase": "conflict", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:9"],
                         "why_both_cannot_hold": "テストは分母 len(xs) - 1 の値を期待しているが、依頼は算術平均を求めている",
                         "which_is_right": "query", "kind": "query_hits_fixed",
                         "correct_lines": ["    return sum(xs) / (len(xs) - 1)"]})
        self.assertFalse(got["ok"], got)
        self.assertIn(f"{b.JUDGMENT_FILE} が読めない", got["reason"])
        self.assertFalse((self.place / "conflicts.json").exists(), "拒んだ申し出は積まない")

    def test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal(self):
        """実行器が在る run: 振り分け → 名指しが failure で落ちる赤を受け → 直しの段で 3 回拒まれた単位は、単位の頭の木に戻して
        機械の申し出を place の conflicts.json に積み、輪を抜ける"""
        self.parent_inputs(str(self.suite))
        out = self.start()
        self.assertEqual((out["tdd"], out["units"], out["reason"]), (True, 1, ""), out)
        prep = self.run_script("route_prep")
        self.assertTrue(prep["go"])
        self.assertIn(MEAN, prep["prompt"])
        self.assertIn("## Handoff from the previous units", prep["prompt"], "周ごとに新しい会話なので引き継ぎの節が載る")
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["done"], got["phase"]), (True, False, "test"), got)
        test_file = self.repo / "test_stats.py"
        head = test_file.read_text(encoding="utf-8")
        test_file.write_text(head.replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        got = self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                         "tests": ["test_stats.py::TestStats::test_mean_of_two"]})
        self.assertEqual((got["ok"], got["phase"], got["reason_file"]), (True, "fix", ""), got)
        self.assertTrue(self.run_script("tdd_prep")["go"])
        fix = {"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を直したつもり"}
        for _ in (1, 2):
            got = self.step(fix)
            self.assertEqual((got["ok"], got["done"]), (False, False), got)
            self.assertTrue(pathlib.Path(got["reason_file"]).is_file())
            self.assertIn(got["reason"].splitlines()[0], self.tdd_prompt())
        got = self.step(fix)
        self.assertEqual((got["ok"], got["done"], got["phase"]), (False, True, "done"), got)
        self.assertEqual(test_file.read_text(encoding="utf-8"), head, "単位の頭の木に戻した")
        rows = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))["items"]
        self.assertEqual([r["unit_key"] for r in rows], [MEAN])
        self.assertEqual(self.run_script("tdd_prep"), {"prompt": "", "go": False, "new_unit": False})
        index = self.place / "orders.json"
        self.assertEqual(json.loads(index.read_text(encoding="utf-8"))["weapons"], {MEAN: "tdd"})
        for _ in (1, 2):   # 修正の輪の頭が、諦めた単位を variant の注文に書き直す（何度呼んでも同じ。orders.regive）
            self.run_script("fix_prep")
            self.assertEqual(json.loads(index.read_text(encoding="utf-8"))["weapons"], {MEAN: "variant"})
            self.assertFalse((self.place / "orders" / "tdd.json").exists())
            variant = json.loads((self.place / "orders" / "variant.json").read_text(encoding="utf-8"))
            self.assertEqual([u["key"] for u in variant["units"]], [MEAN])
        end = self.run_script("group_end")
        result = json.loads(pathlib.Path(end["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(result["base"], str(self.place / "base.json"), "元の結末を取った組は base.json の場所を運ぶ")
        self.assertTrue(result["tdd"]["ran"])
        self.assertEqual([(u["unit_key"], u["gave_up"]) for u in result["tdd"]["units"]], [(MEAN, "green")])
        self.assertEqual([(u["unit_id"], u["status"]) for u in result["units"]], [(MEAN, "given_up")])
        self.assertEqual([r["unit_key"] for r in result["conflicts"]], [MEAN])

    def test_orders_hand_the_route_counts_to_the_loop_and_the_loop_writes_its_record(self):
        """E1: 振り分けの状態は place の route.json（輪の置き場 tdd-<k>/ を持たない）。振り分けが使った周・呼びの控え・渡した証拠の種類は
        orders が注文の型ごとの欄 tdd（weapon-order の形）に書き、輪の状態はそこから数え始める。輪が抜けたら tdd-<k>/record.json を
        書く（形は schemas/tdd-record.schema.json）"""
        self.parent_inputs(str(self.suite))
        self.start()
        self.assertEqual(self.loop_phase(), "route")
        self.assertFalse(list(self.place.glob("tdd-[0-9]*")), "振り分けは輪の置き場を作らない")
        self.assertFalse(json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8")).get("state_file"))
        self.assertTrue(self.run_script("route_prep")["go"])
        self.assertTrue((self.place / "route-delivered.json").is_file(), "振り分けの控えは輪の控えと別")
        self.assertFalse(self.step({"phase": "route", "units": []})["ok"])
        got = self.step({"phase": "route", "units": [{"unit_key": MEAN, "route": "tdd"}]})
        self.assertEqual((got["ok"], got["phase"]), (True, "test"), got)
        order = json.loads((self.place / "orders" / "tdd.json").read_text(encoding="utf-8"))
        schema = json.loads((kit.SHARED / "schemas" / "weapon-order.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_schema(order, schema), [])
        started = json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))
        loop = json.loads(pathlib.Path(started["state_file"]).read_text(encoding="utf-8"))
        self.assertEqual(order["tdd"]["iterations"], 2)
        self.assertEqual([(c["phase"], c["ok"]) for c in order["tdd"]["calls"]], [("route", False), ("route", True)])
        self.assertEqual(order["tdd"]["kinds"], ["code"])
        self.assertEqual((loop["iterations"], loop["calls"], loop["kinds"]),
                         (2, order["tdd"]["calls"], order["tdd"]["kinds"]), "輪は注文の欄から数え始める")
        self.assertFalse((pathlib.Path(started["state_file"]).parent / "record.json").exists())
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", NEW_TEST + "\n\nif __name__"),
                             encoding="utf-8")
        self.assertTrue(self.step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"],
                                   "tests": ["test_stats.py::TestStats::test_mean_of_two"]})["ok"])
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        got = self.step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        record = json.loads((pathlib.Path(started["state_file"]).parent / "record.json").read_text(encoding="utf-8"))
        shape = json.loads((BLOCK / "schemas" / "tdd-record.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_schema(record, shape), [], record)
        self.assertEqual([(c["phase"], c["ok"]) for c in record["calls"]],
                         [("route", False), ("route", True), ("test", True), ("fix", True)], "振り分けの呼びが輪の記録の頭に入る")
        self.assertEqual(list(record["frozen"]), ["test_stats.py"])

    # ---- 修正の輪
    def test_fix_accept_rejects_a_change_to_a_loop_frozen_test(self):
        """輪の後の修正役が、TDD の輪で緑にした単位のテストのファイルの既存の行を変えた返答を、fix-accept が凍ったテストの確かめで
        拒み、そのファイルを名指す"""
        test_file, _ = self.green_loop()
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("mean([2, 4]), 3)", "mean([2, 4]), 3.0)"),
                             encoding="utf-8")
        out = self.accept({"changes": [_change(MEAN, ["stats.py", "test_stats.py"])]})
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertIn("test_stats.py", self.frozen_reason(out["reason"]))

    def test_fix_prompt_pastes_the_frozen_files_the_accept_checks(self):
        """#603: fix-prep が修正役の指示に貼る凍ったテストのファイルは、fix-accept の凍ったテストの確かめが拒むファイルと同じ"""
        test_file, prompt = self.green_loop()
        pasted = self.frozen_line(prompt)
        self.assertEqual(pasted, {"test_stats.py"})
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("mean([2, 4]), 3)", "mean([2, 4]), 3.0)"),
                             encoding="utf-8")
        out = self.accept({"changes": [_change(MEAN, ["stats.py", "test_stats.py"])]})
        frozen = self.frozen_reason(out["reason"])
        self.assertTrue(all(p in frozen for p in pasted), frozen)

    def test_fix_ruled_prompt_pastes_the_frozen_files_the_ruled_accept_checks(self):
        """#603: fix-ruled-prep が裁定の後の修正役の指示に貼る凍ったテストのファイルは、fix-ruled-accept の凍ったテストの確かめが
        拒むファイルと同じ（どちらも輪の状態を board.ruled_states から引く）"""
        import conflict
        test_file, _ = self.green_loop()
        conflict.park(self.place, [{"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_code_as", "text": "分母を len(xs) にせよ", "limits": []})
        out = self.run_script("fix_ruled_prep")
        self.assertTrue(out["go"], out)
        idx = json.loads((self.place / "orders.json").read_text(encoding="utf-8"))   # 4.4 の 5: 段の頭で裁定の後の注文を書く
        self.assertEqual((idx["pass"], idx["weapons"], idx["stage"], idx["since"]),
                         ("ruled", {MEAN: "variant"}, 2, _src("board").fixer_head(self.place, "ruled")))
        pasted = self.frozen_line(support.writer_prompt(self.env(self.art, {}), out, self.repo))
        self.assertEqual(pasted, {"test_stats.py"})
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("mean([2, 4]), 3)", "mean([2, 4]), 3.0)"),
                             encoding="utf-8")
        out = self.run_script("fix_ruled_accept", consulted="false", iteration="1",
                              reply_variant=support.reply_json({"changes": [_change(MEAN, ["stats.py", "test_stats.py"])]}))
        frozen = self.frozen_reason(out["reason"])
        self.assertTrue(all(p in frozen for p in pasted), frozen)

    def test_fix_ruled_prompt_names_the_saved_first_reply_once(self):
        """裁定の後の修正役の指示は、1 回目の修正役の返答の保存したファイルを段落 ruled_reply に 1 度だけ名指す（返答が無い run には
        その段落を入れない）"""
        import conflict
        self.green_loop()
        conflict.park(self.place, [{"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_code_as", "text": "分母を len(xs) にせよ", "limits": []})
        env = self.env(self.art, {})
        first = support.writer_prompt(env, self.run_script("fix_ruled_prep"), self.repo)
        self.assertNotIn("The first fixer's answer (saved by the machine)", first)
        reply = _write(self.tmp / "first-reply.json", {"changes": [], "not_done": [], "plan_faces": []})
        _write(self.place / "groups.json", {"groups": [GROUP], "out_dir": str(self.out_dir)})
        _write(self.out_dir / "g1" / "result.json", {"reply_file": str(reply)})
        prompt = support.writer_prompt(env, self.run_script("fix_ruled_prep"), self.repo)
        saved = str(self.place / "fix-reply.json")
        self.assertEqual(prompt.count("The first fixer's answer (saved by the machine): "), 1)
        self.assertEqual(prompt.count(saved), 1)

    def test_fix_accept_rejects_a_change_under_the_skip_head(self):
        """fix-prep が修正の段の頭に .archon/ の下の姿を控え（board.record_skipped。除くパスの頭は ports.RUNTIME_COPY_PREFIX）、
        fix-accept がその下を変えた返答を拒む"""
        b = _src("board")
        copy = self.repo / ".archon" / "workflows" / "x.yaml"
        copy.parent.mkdir(parents=True)
        copy.write_text("a: 1\n", encoding="utf-8")
        self.green_loop()
        self.assertEqual(b.read_json(self.place / b.SKIP_BEFORE_FILE),
                         {".archon/workflows/x.yaml": b.skip_digests(self.repo, (".archon/",))[".archon/workflows/x.yaml"]})
        copy.write_text("a: 2\n", encoding="utf-8")
        out = self.accept({"changes": [_change(MEAN, ["stats.py"])]})
        self.assertFalse(out["ok"], out)
        head = b.FIX_CHECK_HEAD.format(head=b.FIX_CHECKS["pack"], cid="pack", count=1)
        self.assertIn(head, out["reason"])
        self.assertIn(".archon/workflows/x.yaml", out["reason"].split(head, 1)[1])

    # ---- group-end
    def test_group_end_writes_the_result(self):
        """組の結果を out_dir/<group_id>/result.json に約束の形で書く（修正の輪の結末・返答の写し・許したテストを読む）"""
        import conflict
        import impact
        import leftovers
        b = _src("board")
        self.start()
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        _write(self.place / "fix-units.json", {MEAN: {"status": "fixed", "reason": ""}})
        _write(self.place / "fix-reply.json", {"changes": [
            {"unit_key": MEAN, "breaks": {"accepted": "空の列の平均の値が変わる"}}], "gates_changed": True,
            "rejudge_requested": "単位の見立てが違う", "premise_drift_note": "上限を測り直した", "x_scalars": {"x_moved": 2}})
        agreed = {"op": conflict.ASKED_OP, "id": 1, "item": "1", "status": "answered", "decision": "allow",
                  "granted_paths": [], "granted_tests": ["test_stats.py"], "granted_new_tests": [], "reason": "許した"}
        (self.place / "trace.jsonl").write_text(json.dumps(agreed, ensure_ascii=False) + "\n", encoding="utf-8")
        closure = {"unit_key": MEAN, "closed": True, "discrepancies": []}
        _write(self.place / "fix-unit-rows.json", {"round": 1, "rows": [closure]})
        notice = {"op": impact.ACCEPT_TRACE_OP, "ci_left": [], "final_left": ["test_far.py"], "final_far": []}
        b.write_json(self.place / b.ACCEPT_TRACE_FILE, [notice])
        out = self.run_script("group_end")
        self.assertEqual(out["result_file"], str(self.out_dir / "g1" / "result.json"))
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(set(result), {"group_id", "unit_ids", "end_tree", "start_tree", "units", "tdd", "conflicts",
                                       "objection", "changed", "x_scalars", "allowed_tests", "verified",
                                       "reply_file", "tdd_record", "worktree", "handoffs", "handoff_titles", "mismatched", "accept_trace", "writer_report", "closure",
                                       "claimed", "place", "base"})
        # F427・F428・F013: 子の place の受け入れた壊れ・閉鎖の表・受け付けの知らせを、親の finish へ結果で運ぶ
        self.assertEqual((result["handoffs"], result["claimed"], result["closure"]),
                         ([f"{MEAN}: 壊すと分かって通した——空の列の平均の値が変わる"], [MEAN], [closure]))
        self.assertEqual(result["accept_trace"], [{**notice, "group_id": "g1"}, {**agreed, "group_id": "g1"}])
        self.assertEqual(result["tdd_record"], "", "輪の無い組")
        self.assertEqual(result["base"], "", "実行器の無い組は元の結末を取らない")
        self.assertEqual(result["worktree"], os.path.realpath(self.repo))
        self.assertEqual(result["units"], [{"unit_id": MEAN, "status": "fixed", "reason": ""}])
        self.assertEqual(result["end_tree"], leftovers.snapshot(self.repo))
        self.assertNotEqual(result["end_tree"], result["start_tree"])
        self.assertEqual((result["tdd"]["ran"], result["tdd"]["units"]), (False, []))
        self.assertEqual(result["changed"], {**{k: k == "gates_changed" for k in CHANGED_MARKS},
                                             "premise_drift_note": "上限を測り直した"})
        self.assertEqual(result["x_scalars"], {"x_moved": 2})
        self.assertEqual((result["objection"], [t["path"] for t in result["allowed_tests"]], result["verified"],
                          result["conflicts"]), ("単位の見立てが違う", ["test_stats.py"], [], []))
        self.assertEqual(result["reply_file"], str(self.place / "fix-reply.json"))
        self.assertEqual(result["place"], str(self.place), "place のパス（読み手と使い道は board.group_result の place の説明）")

    def test_group_end_lists_allowed_tests_only_for_an_accepted_reply(self):
        """受け付けが通らず fix-reply.json が無い組は、place に許しが在っても許しの訳 allowed_tests を空にする（#286。join の和と
        親の finish が同じ欄から読む）。相談の 1 問 1 答の行は accept_trace に残る"""
        import conflict
        self.start()
        agreed = {"op": conflict.ASKED_OP, "id": 1, "item": "1", "status": "answered", "decision": "allow",
                  "granted_paths": [], "granted_tests": ["test_stats.py"], "granted_new_tests": [], "reason": "許した"}
        (self.place / "trace.jsonl").write_text(json.dumps(agreed, ensure_ascii=False) + "\n", encoding="utf-8")
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual((result["allowed_tests"], result["reply_file"]), ([], ""))
        self.assertEqual(result["accept_trace"], [{**agreed, "group_id": "g1"}])

    def test_refix_child_sees_the_first_pass_and_returns_only_its_rows(self):
        """L-W18・F023: 2 度目の修正の段の組の子は、親の place が写した 1 回目の段の申し出と裁定（印 prior_pass）を写して読み
        （conflict.second_pass が真）、結果の conflicts にはこの段の行だけを載せる（親の conflict-check が 1 回目の行を積み直さない）"""
        import conflict
        first = self.tmp / "first"
        first.mkdir()
        row = {"id": "c1-1", "round": 1, "source": "fix", "unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
               "why_both_cannot_hold": "案の項目が判定と食い違う", "which_is_right": "request", "kind": "brief_vs_judgment",
               "status": "ruled", "replan": "waiting",
               "ruling": {"decision": "fix_plan_item", "text": "項目 1 が誤り", "limits": [], "plan_items": [1], "by": "ruler"}}
        _write(first / "conflicts.json", {"items": [row]})
        conflict.adopt_prior(self.parent, first, ["1"])
        self.start()
        self.assertTrue(conflict.second_pass(self.place))
        new = conflict.park(self.place, [{"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                          "why_both_cannot_hold": "直した後も分母が空の列で割れる", "which_is_right": "unknown",
                                          "kind": "needs_context"}], source=conflict.FIX_SOURCE)
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in result["conflicts"]], new)

    def test_group_end_carries_permits_mismatches_and_accept_notices_to_the_parent_finish(self):
        """修正役の返答を受け付けた組の子の place の許しの訳（F429）・申告と数え直しが合わない単位・受け付けが選んだ試験の知らせ
        （F014）は group-end が組の結果に載せ、親の finish が返りの diff の隣の allowed-tests.json・返りの mismatched・
        accept-trace.json に集める"""
        import conflict
        import querytest
        b = _src("board")
        self.start()
        conflict.park(self.place, [{"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
                                    "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
                                    "which_is_right": "request", "kind": "unnamed_test_broke"}],
                      source=conflict.FIX_SOURCE, ruling={"decision": "fix_test_scope", "text": "期待を直してよい",
                                                          "limits": ["test_stats.py:8"]})
        _write(self.place / querytest.CLOSURE_FILE, {"round": 1, "rows": [
            {"unit_key": MEAN, "closed": True, "discrepancies": ["申告の数が問いの数と合わない"]}]})
        notice = {"op": "fix_tests_selected", "node": "fix-accept", "pass": "first", "attempt": 1,
                  "note": "選んだ試験が 0 件しか走らなかった", "ci_left": [], "final_left": [], "final_far": []}
        _write(self.place / b.ACCEPT_TRACE_FILE, [notice])
        _write(self.place / b.FIX_REPLY_FILE, {"changes": []})
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        permit = {"path": "test_stats.py", "permit": f"{conflict.RULED_TEST_ID}-c1-1", "source": "ruling"}
        self.assertEqual(result["allowed_tests"], [permit])
        self.assertEqual(len(result["mismatched"]), 1, result["mismatched"])
        self.assertIn("合わない: 申告の数が問いの数と合わない", result["mismatched"][0])
        child_notice = {**notice, "group_id": "g1"}
        self.assertEqual(result["accept_trace"], [child_notice])

        self.parent_groups(result["start_tree"])
        _write(self.parent / b.JOIN_FILE, {"par": False, "groups": [
            {"group_id": "g1", "unit_ids": [MEAN], "returned": True, "reason": ""}],
            "units": [{"unit_id": MEAN, "group_id": "g1", "status": "fixed", "reason": ""}]})
        own = {**notice, "pass": "ruled", "node": "fix-ruled-accept"}
        _write(self.parent / b.ACCEPT_TRACE_FILE, [own])
        for _ in range(2):   # 回し直しても行を重ねない
            out = self.run_script("finish", art=self.parent)
            beside = (self.parent / out["diff"]["path"]).parent
            self.assertEqual(json.loads((beside / b.ACCEPT_TRACE_FILE).read_text(encoding="utf-8")), [child_notice, own])
            self.assertEqual(json.loads((beside / b.ALLOWED_TESTS_FILE).read_text(encoding="utf-8")), [permit])
            self.assertEqual(out["allowed_test_changes"], ["test_stats.py"])
            self.assertEqual(out["mismatched"], result["mismatched"])

    def test_group_end_reports_a_touched_excluded_hunk_in_mismatched(self):
        """組の終わりは、組の始めの木から今への変更が並行 PR に回した hunk に触れていれば、その hunk を名指す行を mismatched に載せる
        （受け付けを通らない TDD の役・合わせ役の変更も照らす）。触れていなければ載せない"""
        row = {"pr": 4, "file": "stats.py", "start": 5, "end": 5, "why": "PR 4 が同じ行を書く"}
        self.parent_inputs("", excluded=[row])
        self.start()
        _write(self.place / _src("board").FIX_REPLY_FILE, {"changes": []})
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(result["mismatched"], [])
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(len(result["mismatched"]), 1, result["mismatched"])
        self.assertIn("並行 PR #4 に回した hunk stats.py:5-5（PR 4 が同じ行を書く）", result["mismatched"][0])

    def test_group_child_starts_its_log_and_reports_where_join_finds_it(self):
        """並べた子は自分の作業ツリーの記録を group-start で空で作り、group-end の結果の worktree から join が同じ記録を引く"""
        import writelog
        env, root = _recorder_root(self.tmp)
        self.grp_env = env
        self.start()
        log = writelog.log_path(root, self.repo)
        self.assertEqual(log.read_text(encoding="utf-8"), "")
        result = json.loads(pathlib.Path(self.run_script("group_end")["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(writelog.log_path(root, result["worktree"]), log)

    def test_group_end_alone_writes_into_its_own_place(self):
        """out_dir が空の単独の run は自分の place の groups/<group_id>/ に書く（finish も同じ所を読む）"""
        self.intake(out_dir="", judgment=json.dumps({"units": [{"key": MEAN, "label": "block"}], "questions": []},
                                                    ensure_ascii=False))
        out = self.run_script("group_end")
        self.assertEqual(out["result_file"], str(self.place / "groups" / "g1" / "result.json"))
        self.assertFalse((self.place / "result.json").exists())
        result = json.loads(pathlib.Path(out["result_file"]).read_text(encoding="utf-8"))
        self.assertEqual(result["units"][0]["status"], "not_done")
        self.assertIn("group-start", result["tdd"]["reason"])


class GroupChildSeamCase(unittest.TestCase):
    """形 group の子の run の口: board.adopt_inputs（親の place の写しと凍結の印の置き直し）・verified_tests・group_result（組の
    結果の形と単位の結末の選び）"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self, prefix="works-fix-grp-seam-")
        self.place = self.tmp / "place"
        self.place.mkdir()
        self.board = _src("board")

    def test_adopt_inputs_copies_the_parent_and_refreezes_the_fields(self):
        import conflict
        import planmarks
        parent = self.tmp / "parent"
        parent.mkdir()
        runvals.write(parent, {"tdd_suite": ""})
        (parent / "judgment.json").write_text('{"units": []}\n', encoding="utf-8")
        fields = [{"route": "direct", "tests": [], "rewrite_tests": [], "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py"],
                   "out_of_scope": []}]
        planmarks.save(parent, 1, fields)
        got = self.board.adopt_inputs(parent, self.place)
        self.assertEqual(got, ["values.json", "judgment.json", "plan-fields.json"])
        self.assertEqual((self.place / "judgment.json").read_text(encoding="utf-8"), '{"units": []}\n')
        self.assertEqual(runvals.read(self.place), runvals.read(parent))
        self.assertEqual(conflict.frozen_fields(self.place, 1), fields, "子の trace に凍結の印が在る")
        bare = self.tmp / "bare"
        bare.mkdir()
        self.assertEqual(self.board.adopt_inputs(bare, self.tmp / "child2"), [], "欄の控えの無い親は何も置かない")
        with self.assertRaises(ValueError):
            self.board.adopt_inputs(self.tmp / "no-such", self.place)

    def test_verified_tests(self):
        tdd = {"ran": True, "units": [{"unit_key": "a", "route": "tdd", "green": "ok", "tests": ["t.py::x", "t.py::y"]},
                                      {"unit_key": "b", "route": "tdd", "green": "", "tests": ["t.py::z"]},
                                      {"unit_key": "c", "route": "direct", "green": "", "tests": []}]}
        self.assertEqual(self.board.verified_tests(tdd), ["t.py::x", "t.py::y"])

    def test_group_result_shape(self):
        b = self.board
        tdd = {"ran": True, "suite": "s", "reason": "", "units": [
            {"unit_key": "b", "route": "parked", "gave_up": "red", "why": "赤が 3 回とも通らなかった", "tests": []}]}
        reply = {"mechanism_changed": True, "rejudge_requested": "判定の単位 a は誤り"}
        got = b.group_result({"group_id": "g1", "unit_ids": ["a", "b", "c"], "items": [1]}, start_tree="t0",
                             end_tree="t1", tdd=tdd, fix_units={"a": {"status": "fixed", "reason": ""}},
                             reply=reply, reply_file="/r.json", conflicts=[{"id": 1}],
                             allowed_rows=[{"path": "t.py", "permit": "p1", "source": "plan"},
                                           {"path": "t.py", "permit": "p2", "source": "plan"}])
        self.assertEqual(set(got), {"group_id", "unit_ids", "end_tree", "start_tree", "units", "tdd", "conflicts",
                                    "objection", "changed", "x_scalars", "allowed_tests", "verified",
                                    "reply_file", "tdd_record", "worktree", "handoffs", "handoff_titles", "mismatched", "accept_trace", "writer_report", "closure",
                                    "claimed", "place", "base"})
        self.assertEqual((got["worktree"], got["place"], got["base"]), ("", "", ""), "渡さなければ空")
        self.assertEqual((got["handoffs"], got["claimed"], got["closure"], got["accept_trace"], got["writer_report"]), ([], [], [], [], []))
        self.assertEqual([(u["unit_id"], u["status"]) for u in got["units"]],
                         [("a", "fixed"), ("b", "given_up"), ("c", "not_done")])
        self.assertEqual(got["units"][2]["reason"], b.NO_UNIT_RESULT)
        self.assertEqual(got["objection"], "判定の単位 a は誤り")
        self.assertEqual(got["changed"], {**{k: k == "mechanism_changed" for k in b.CHANGED_MARKS}, b.DRIFT_NOTE: ""})
        self.assertEqual([r["permit"] for r in got["allowed_tests"]], ["p1", "p2"])
        row = {"path": "t.py", "permit": "plan-rewrite-1", "source": "plan"}
        unreplied = b.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                   allowed_rows=[row, "壊れた行"])
        self.assertEqual(unreplied["allowed_tests"], [],
                         "返答を受け付けていない組は許しの訳を載せない（join と親の finish が同じ欄から読む）")
        final = b.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                               reply={"changes": [{"unit_key": "a", "breaks": {"accepted": "x"}}]}, mismatched=["m"],
                               accept_trace=[{"op": "fix_tests_selected", "note": "0 件"}, "壊れた行"])
        self.assertEqual((final["handoffs"], final["mismatched"]), (["a: 壊すと分かって通した——x"], ["m"]))
        self.assertEqual(final["accept_trace"], [{"op": "fix_tests_selected", "note": "0 件", "group_id": "g1"}])
        empty = b.group_result({"group_id": "g2", "unit_ids": []}, start_tree="", end_tree="", tdd=None)
        self.assertEqual((empty["tdd"]["ran"], empty["objection"], empty["reply_file"]), (False, "", ""))
        self.assertFalse(any(empty["changed"].values()))


if __name__ == "__main__":
    unittest.main()
