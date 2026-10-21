"""line の始めの node start（workflows/line/scripts/start.py。docs/design/line.md の 1.3 の 1・1.6・9 節の start）: 入力の拒み・始めの記録・
固定材料の取り込み・起動の承認ノードの文と、配る値 ports の欄ごとの式。

元は今の tests/workflows/test_line.py の StartCase（README 9.5）。start を名で読み（compute を回さない）、load の後に start.start を
直に呼ぶ（gh の読み出しと lib の根を差し替えるため）。始めの記録を読む口は line の src/startrec.py（integration.md の 4.3-追加-6）なので、
今の StartCase が lib の読み手（conflict.request_file・fixboard.fix_values）で照らした所は、配る値で照らす。
TestPolicyBrief は lib/tests/test_blk_fix.py の同じ名の場面の line の側（始めの記録が方針の写しを固め、配る値 policy がその写しを指す。
integration.md の 4.2-7。写しを役に貼る側は fix の試験）。
"""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[3]
LINE = kit.BLOCKS / "line"
SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN = kit.RUN_ID
INPUTS = ("request", "base", "pr", "spec", "test_cmd", "tdd_suite", "final_gate", "unattended", "design_only", "thickness",
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
answer, entry, entryshape, stopby = start.answer, start.entry, start.entryshape, start.stopby
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


class SpecTableCase(Seeded):
    """入力 spec_table（仕様駆動の道の表。docs/design/spec-driven.md の 6.2 の変える node の 1 と 6.5 の 4）。start は表のファイルが在る
    ことと組めない入力だけを照らし、表の中身は読まない（PyYAML を持たない）"""

    def put_table(self) -> pathlib.Path:
        return self.outside("spec.yaml", "design: docs/d.md\n")

    def test_request_run_is_not_a_spec_run(self):
        """表を名指さない run: from_spec は偽、ports の spec_table は空、routes は修正の部品の既定と同じ auto"""
        got = self.start(request="request_ok.json")
        self.assertTrue(got["ok"], got)
        self.assertIs(got["from_spec"], False)
        self.assertEqual((got["ports"]["spec_table"], got["ports"]["routes"]), ("", "auto"))
        self.assertNotIn("spec_table", self.record(got))

    def test_spec_table_alone_is_an_entry(self):
        """表だけの run は依頼の行も差分も要らない。from_spec は真、ports の spec_table は表の絶対パス、routes は plan"""
        table = self.put_table()
        got = self.start(spec_table=str(table))
        self.assertTrue(got["ok"], got)
        self.assertIs(got["from_spec"], True)
        self.assertEqual((got["ports"]["spec_table"], got["ports"]["routes"]), (str(table.resolve()), "plan"))
        self.assertEqual(self.record(got)["spec_table"], str(table.resolve()))
        self.assertIn(f"仕様駆動の道: 表 {table.resolve()}", got["gate_text"])

    def test_missing_table_and_clashing_inputs_are_refused(self):
        self.assertIn("spec_table", self.refused(spec_table="nope.yaml"))
        table = str(self.put_table())
        for kw in ({"request": "request_ok.json"}, {"base": "base"}, {"pr": "7"}, {"spec": "on"}):
            with self.subTest(kw):
                self.assertIn("spec_table", self.refused(spec_table=table, **kw))
        fixture_dir = self.tmp / "fixture"
        fixture_dir.mkdir()
        self.assertIn("spec_table", self.refused(spec_table=table, fix_fixture=str(fixture_dir)))

    def test_refused_and_fallen_runs_are_not_spec_runs(self):
        self.assertIs(self.start(spec_table="nope.yaml")["from_spec"], False)
        self.assertIs(start.fallback("x")["from_spec"], False)


class StartCase(Seeded):
    def test_request_builds_the_entry_shape_and_the_record(self):
        got = self.start(request="request_ok.json", final_gate="when_needed", features_off="tdd_lanes")
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["ask"], got["unattended"], got["design_only"], got["final_gate"]), (True, False, False, "when_needed"))
        doc = self.record(got)
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(doc["input"]["base"], {"rev": head, "from": "head", "name": "", "label": "HEAD"})
        self.assertEqual((doc["input"]["requests"], doc["input"]["diff"]["empty"]), (2, True))
        self.assertEqual(doc["input"]["request_file"], str((self.repo / "request_ok.json").resolve()),
                         "相対の依頼は対象の根から読み、絶対パスで残す（L-E06）")
        self.assertEqual(doc["features_off"], ["tdd_lanes"])
        self.assertEqual(doc["features"]["tdd_lanes"], "off")
        self.assertEqual(doc["final_gate"], "when_needed")
        self.assertIn("archon", doc["versions"])
        self.assertTrue(got["gate_text"].startswith("起きたこと: "), got["gate_text"])

    def test_start_deals_the_shared_places(self):
        """#681: 始めの node は run の共有の置き場（試験の結果の控え tree_run.reuse_dir と、利用者の HOME・XDG に戻して起こした印の
        置き場＝run directory）を配る値で渡す。拒んだ run の配る値は全部の欄が空（後ろの node は飛ぶ）"""
        import tree_run
        got = self.start(request="request_ok.json")
        self.assertEqual((got["ports"]["reuse_dir"], got["ports"]["user_env_dir"]),
                         (str(tree_run.reuse_dir(self.artifacts)), str(self.artifacts)))
        refused = self.start()
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["ports"], deal.empty())

    def test_base_alone_is_a_change_entry(self):
        got = self.start(base="base")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"], {"rev": self.fork, "from": "base", "name": "base", "label": "base base"},
                         "差分の根は base と HEAD の merge-base、label は「base <名>」（L-E09）")
        self.assertGreaterEqual(doc["input"]["diff"]["files"], 1)
        self.assertEqual(doc["base_rev"], git(self.repo, "rev-parse", "HEAD"),
                         "base_rev は修正の前の HEAD（merge と test-gate が差分の起点に読む）")
        self.assertEqual(doc["review_rev"], doc["base_rev"], "review_rev は役の材料の読む版。差分の根 input.base.rev とは別に持つ")

    def test_request_file_is_on_the_top_of_the_record(self):
        """issue #89: 始めの記録の上の欄 request_file は input.request_file と同じ絶対パス。依頼の無い入口では両方 \"\""""
        doc = self.record(self.start(request="request_ok.json"))
        self.assertEqual(doc["request_file"], str((self.repo / "request_ok.json").resolve()))
        self.assertEqual(doc["request_file"], doc["input"]["request_file"])
        doc = self.record(self.start(base="base"))
        self.assertEqual((doc["request_file"], doc["input"]["request_file"]), ("", ""))

    def test_blocks_get_the_request_file_by_the_ports(self):
        """issue #89 の後継: block は始めの記録を読まず、配る値 request・request_file で依頼のファイルを受ける。記録を字のまま写しても
        line の読む口（src/startrec.py）が同じ値を返す"""
        got = self.start(request="request_ok.json")
        want = str((self.repo / "request_ok.json").resolve())
        self.assertEqual((got["ports"]["request"], got["ports"]["request_file"]), (want, want))
        place = self.tmp / "copy"
        self.assertEqual(startrec.adopt(place, self.artifacts / got["record"]["path"]), self.record(got))
        self.assertEqual(startrec.request_file(startrec.read(place)), want)
        bare = self.start(base="base")["ports"]
        self.assertEqual((bare["request"], bare["request_file"]), ("[]", ""), "依頼の無い run の request は空の配列の字")

    def test_unattended_does_not_open_the_start_gate(self):
        got = self.start(request="request_ok.json", unattended="true")
        self.assertEqual((got["ok"], got["ask"], got["unattended"]), (True, False, True))
        self.assertEqual((got["ports"]["unattended"], got["ports"]["takes_push"]), (True, True))

    def test_prior_failures_of_the_request_are_placed(self):
        (self.repo / "next.json").write_text(json.dumps({"findings": [{"where": "a", "text": "b"}],
                                                         "prior_failures": [{"where": "判定", "text": "拒まれた"}]}),
                                             encoding="utf-8")
        got = self.start(request="next.json")
        self.assertEqual(got["prior_failures"]["path"], "prior-failures-in.json")
        self.assertEqual(json.loads((self.artifacts / "prior-failures-in.json").read_text(encoding="utf-8")),
                         [{"where": "判定", "text": "拒まれた"}])
        self.assertEqual(got["ports"]["prior_rows"], [{"where": "判定", "text": "拒まれた"}])

    def test_policy_md_is_recorded_as_an_absolute_path(self):
        (self.repo / "policy.md").write_text("方針\n", encoding="utf-8")
        got = self.start(request="request_ok.json", policy_md="policy.md")
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.record(got)["policy_md"], str(self.repo / "policy.md"))

    def test_record_carries_the_policy_frozen_at_the_start(self):
        """始めの記録の欄 policy は run の始めに固めた版 {named, path, sha256, copy}（写しは run directory の中）。名指しも既定の置き場の
        文書も無ければ path は空・sha256 と copy は null"""
        (self.tmp / "policy.md").write_text("方針\n", encoding="utf-8")
        frozen = self.record(self.start(request="request_ok.json", policy_md=str(self.tmp / "policy.md")))["policy"]
        self.assertEqual((frozen["named"], frozen["path"]), (str(self.tmp / "policy.md"),) * 2)
        self.assertTrue(pathlib.Path(frozen["copy"]).is_relative_to(self.artifacts))
        self.assertEqual(pathlib.Path(frozen["copy"]).read_text(encoding="utf-8"), "方針\n")
        self.assertEqual(self.record(self.start(request="request_ok.json"))["policy"],
                         {"named": "", "path": "", "sha256": None, "copy": None})

    def bad_findings(self) -> pathlib.Path:
        return self.outside("bad_findings.json", json.dumps([{"where": "stats.py"}]))

    def test_refusals_stop_before_any_role(self):
        for kw, words in (({}, "直す物も審査する物も無い"),
                          ({"request": "request_ok.json", "base": "base", "pr": "1"}, "両方"),
                          ({"request": "request_ok.json", "spec": "on", "unattended": "true"}, "組めない"),
                          ({"request": "request_ok.json", "thickness": "xx"}, "知らない値"),
                          ({"request": "request_ok.json", "features_off": "nope"}, "nope"),
                          ({"request": "request_ok.json", "deliver": "merge"}, "deliver='merge' は知らない語"),
                          ({"request": "request_ok.json", "features_off": "judge_verify", "features_on": "judge_verify"}, "両方"),
                          ({"request": "no-such.json"}, "no-such.json"),
                          ({"request": "request_ok.json", "design_only": "yes"}, "design_only"),
                          ({"request": "request_ok.json", "policy_md": "no-such.md"}, "no-such.md"),
                          ({"request": "request_ok.json", "fix_fixture": "fx"}, "固定材料のフォルダ fx が無い"),
                          ({"request": "request_ok.json", "spec": "on", "fix_fixture": str(self.tmp)}, "固定材料（fix_fixture）と組めない"),
                          ({"request": str(self.bad_findings())}, "findings は")):
            with self.subTest(kw=kw):
                got = self.start(**kw)
                self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
                self.assertIn(words, got["reason"])
                self.assertEqual(got["ports"], deal.empty())
                doc = self.record(got)
                self.assertEqual(doc["refused"], got["reason"])
                self.assertEqual(doc["inputs"], raw(**kw), "拒む run でも設定の写しを残す（L-E46）")
                self.assertIn("unknown", doc["versions"], "拒む run でも版の控えを残す（L-E46）")

    def test_fixture_starts_the_run_from_the_copy(self):
        """#509: 写した run の置き場の固定材料を名指した start は、写しを今の run の置き場に取り込み、始めの記録を写しの物に今の run の
        id・入力・版の控えと固定材料の印を足して書き、運ぶ値の pointer を返す。配る値は取り込んだ記録から同じ式で引く（1.6）"""
        first = self.start(request="request_ok.json", final_gate="when_needed")
        carried = {"judge": {"judgment": {"type": "archon_artifact", "run_id": RUN, "path": "judge/judgment.json"}}}
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried=carried)
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            kw = {"request": "request_ok.json", "final_gate": "when_needed", "fix_fixture": str(self.artifacts / fixture.DIR),
                  "features_off": "tdd_lanes"}
            got = start.start(raw(**kw), self.repo, place, "run-2")
        self.assertEqual((got["ok"], got["from_fixture"], got["ask"], got["final_gate"]), (True, True, True, "when_needed"), got)
        self.assertEqual(got["fixture"], {"type": "archon_artifact", "run_id": "run-2", "path": fixture.CARRIED})
        self.assertEqual(json.loads((place / fixture.CARRIED).read_text(encoding="utf-8"))["judge"]["judgment"]["run_id"], "run-2")
        doc = json.loads((place / got["record"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((doc["run_id"], doc["inputs"], doc[fixture.KEY]["source_run"]), ("run-2", raw(**kw), RUN))
        self.assertEqual(doc["input"], self.record(first)["input"])
        self.assertIn("archon", doc["versions"])
        self.assertIn(f"- 固定材料から: run {RUN} の修正の前の写し", got["gate_text"])
        self.assertNotIn("tdd_lanes", self.record(first)[entry.FEATURES_CUT_KEY])
        self.assertEqual((doc[entry.FEATURES_KEY], doc[entry.FEATURES_CUT_KEY]),
                         (["tdd_lanes"], entry.features_cut(["tdd_lanes"], doc[entry.FEATURES_ON_KEY])),
                         "機能の切り替えは写しの物でなく今の run の物（修正の段だけを替えて比べる）")
        self.assertEqual((got["ports"]["run_id"], got["ports"]["parallel"], got["ports"]["user_env_dir"]), ("run-2", False, str(place)),
                         "配る値は取り込んだ記録（今の run の id と機能の切り替え）から引く")
        self.assertEqual(got["ports"]["base_rev"], startrec.head_rev(doc))

    def test_fixture_run_points_at_its_own_request_file(self):
        """依頼は今の値にする欄なので、同じ中身の別のファイルで起こした固定材料の run の始めの記録は、今の依頼のファイルを指す"""
        self.start(request="request_ok.json")
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried={})
        again = self.tmp / "request-again.json"
        shutil.copyfile(self.repo / "request_ok.json", again)
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            got = start.start(raw(request=str(again), fix_fixture=str(self.artifacts / fixture.DIR)), self.repo, place, "run-2")
        self.assertTrue(got["ok"], got)
        doc = json.loads((place / got["record"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((doc["request_file"], doc["input"]["request_file"]), (str(again.resolve()), str(again.resolve())))
        self.assertEqual(got["ports"]["request_file"], str(again.resolve()))

    def test_fixture_that_does_not_match_is_refused_before_any_role(self):
        self.start(request="request_ok.json")
        fixture.capture(self.artifacts, self.repo, run_id=RUN, carried={})
        place = self.tmp / "artifacts-2"
        with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "run-2"}):
            got = start.start(raw(request="request_ok.json", test_cmd="make other", fix_fixture=str(self.artifacts / fixture.DIR)),
                              self.repo, place, "run-2")
        self.assertEqual((got["ok"], got["stop_reason"], got["from_fixture"]), (False, stopby.START_REFUSED, False), got)
        self.assertTrue(got["reason"].startswith("固定材料を取り込まない: "), got["reason"])
        self.assertIn("test_cmd", got["reason"])
        self.assertFalse((place / fixture.CARRIED).exists())

    def test_request_refusals_name_the_cause(self):
        """L-E02: 依頼が読めない・JSON として読めない・形が違うを別の文で拒む"""
        self.assertIn("読めない", self.refused(request="no-such.json"))
        self.assertNotIn("JSON", self.refused(request="no-such.json"))
        self.assertIn("JSON として読めない", self.refused(request=str(self.outside("broken.json", "{findings"))))
        bad = json.dumps({"findings": [{"where": "a", "text": "b"}], "answers": "x"})
        reason = self.refused(request=str(self.outside("bad_answers.json", bad)))
        self.assertIn("の形", reason)
        self.assertNotIn("読めない", reason)

    def test_request_without_findings_is_taken(self):
        """#505: findings を省いた依頼（answers・pr だけ）は空の findings として受け、差分の在る base で始まる。差分も依頼の行も
        無ければ空の入力として拒む"""
        rows = [{"question": "q1", "text": "a を選ぶ"}]
        path = self.outside("answers_only.json", json.dumps({"answers": rows}))
        got = self.start(request=str(path), base="base")
        self.assertTrue(got["ok"], got)
        self.assertEqual(self.record(got)["answers"], rows)
        self.assertEqual(got["ports"]["request_answers"], rows)
        self.assertIn(entryshape.EMPTY_REFUSED, self.refused(request=str(path)))

    def test_omitted_tdd_suite_says_how_the_runner_is_prepared(self):
        """#505・#516: tdd_suite を省いた run は、承認ノードの文が TDD の実行器の用意を言う。名指した tdd_suite は記録にそのまま載る"""
        import suitewrite
        got = self.start(base="base", test_cmd="make test")
        self.assertEqual(self.record(got)["tdd_suite"], "")
        self.assertIn(suitewrite.GATE_NOTE, got["gate_text"])
        got = self.start(base="base", test_cmd="make test", tdd_suite="run-tests.sh")
        self.assertEqual(self.record(got)["tdd_suite"], "run-tests.sh")
        self.assertNotIn(suitewrite.GATE_NOTE, got["gate_text"])
        self.assertEqual((got["ports"]["test_cmd"], got["ports"]["tdd_suite"], got["ports"]["has_checks"]),
                         ("make test", "run-tests.sh", True))

    def test_bad_answers_or_prior_shape_refused(self):
        """L-E04・L-D51: answers・prior_failures の形の違う依頼は AI の前で拒む"""
        for key, bad in (("answers", [{"text": "問いの無い答え"}]), ("answers", "x"), ("prior_failures", [{"where": "w"}]),
                         ("prior_failures", [{"where": "w", "text": "t", "extra": 1}])):
            with self.subTest(key=key, bad=bad):
                path = self.outside("shape.json", json.dumps({"findings": [{"where": "a", "text": "b"}], key: bad}))
                self.assertIn(key, self.refused(request=str(path)))

    def test_bad_base_or_pr_refused(self):
        """L-E10: 引けない base・番号でない pr を名を言って拒む"""
        self.assertIn("no-such-branch", self.refused(base="no-such-branch"))
        self.assertIn("引けない", self.refused(base="no-such-branch"))
        self.assertIn("番号でない", self.refused(pr="x"))

    def test_named_pr_is_read_once_and_placed(self):
        """L-E11: 名指した PR は run の中で 1 度だけ読み、run directory の根の github.json に 0600 で置く。2 度目（再開）は読み直さない"""
        import ghreads
        got, calls = self.start_with_gh(self.pr_reads(), pr="7")
        self.assertTrue(got["ok"], got)
        self.assertEqual(calls, [([7], [])])
        placed = self.artifacts / ghreads.BOARD_FILE
        self.assertEqual(placed.stat().st_mode & 0o777, 0o600)
        again, calls = self.start_with_gh(self.pr_reads(title="別の題"), pr="7")
        self.assertEqual(calls, [])
        self.assertEqual(self.record(again)["input"]["pr"]["title"], "題 T")

    def test_pr_base_is_the_github_base_oid(self):
        """L-E12: PR の差分の根は GitHub の baseRefOid と HEAD の merge-base、label は「PR #N「題」」"""
        got, _ = self.start_with_gh(self.pr_reads(), pr="7")
        doc = self.record(got)
        self.assertEqual(doc["input"]["base"], {"rev": self.fork, "from": "pr", "name": "7", "label": "PR #7「題 T」"})
        self.assertEqual((got["ports"]["base"], got["ports"]["base_label"]), (self.fork, "PR #7「題 T」"))
        self.assertEqual(got["ports"]["pr_text"], "# PR #7\n\n## 題\n\n題 T\n\n## 本文\n\n本文X\n", "PR の番号・題・本文の文（purpose・spec）")

    def test_pr_refused_when_head_differs_or_base_missing(self):
        """L-E13: PR の head が対象の HEAD と違えば止め、PR の base の版が無ければ fetch してからと言って止める"""
        import ghreads
        got, _ = self.start_with_gh(self.pr_reads(headRefOid=self.fork), pr="7")
        self.assertIn("head", got["reason"])
        self.assertIn("違う", got["reason"])
        (self.artifacts / ghreads.BOARD_FILE).unlink()
        got, _ = self.start_with_gh(self.pr_reads(baseRefOid="f" * 40), pr="7")
        self.assertIn("fetch してから", got["reason"])
        self.assertFalse(got["ok"])

    def test_no_auth_launch_refuses_named_pr_without_gh(self):
        """L-E15: 認証の要らない起動（殻が立てる WORKS_FACTORY_NO_AUTH=1）で PR を名指せば、gh を呼ばずに止める"""
        with mock.patch.dict(os.environ, {"WORKS_FACTORY_NO_AUTH": "1"}):
            got, calls = self.start_with_gh(self.pr_reads(), pr="7")
        self.assertEqual(calls, [])
        self.assertFalse(got["ok"])
        self.assertIn("認証を使う起動", got["reason"])

    def test_request_text_carries_request_and_pr(self):
        """L-E16・L-E17: 依頼と PR の両方なら見出しつき、片方ならその文。PR の題と本文は始めの記録の input.pr に載る"""
        req = self.outside("req.json", json.dumps([{"where": "stats.py", "text": "依頼の穴"}], ensure_ascii=False))
        doc = self.record(self.start_with_gh(self.pr_reads(), pr="7", request=str(req))[0])
        self.assertIn("## 依頼", doc["request_text"])
        self.assertIn("依頼の穴", doc["request_text"])
        self.assertIn("## PR #7 の題と本文", doc["request_text"])
        self.assertIn("本文X", doc["request_text"])
        self.assertEqual(doc["input"]["pr"], {"number": "7", "title": "題 T", "body": "本文X"})
        doc = self.record(self.start_with_gh(self.pr_reads(), pr="7")[0])
        self.assertEqual(doc["request_text"], "題 T\n\n本文X")
        doc = self.record(self.start(request=str(req)))
        self.assertEqual(doc["request_text"], req.read_text(encoding="utf-8"))

    def test_every_entry_has_the_same_shape(self):
        """L-E19: 依頼・base・PR のどの入口でも input の鍵が同じ"""
        keys = {"base", "head_rev", "diff", "requests", "request_file", "pr", "spec"}
        for name, got in (("依頼", self.start(request="request_ok.json")), ("base", self.start(base="base")),
                          ("PR", self.start_with_gh(self.pr_reads(), pr="7")[0])):
            with self.subTest(entry=name):
                doc = self.record(got)
                self.assertEqual(set(doc["input"]), keys)
                self.assertEqual(set(doc["input"]["base"]), {"rev", "from", "name", "label"})

    def test_record_is_where_the_line_reader_looks(self):
        """L-E24: start が書いた記録を line の読む口（src/startrec.read）がそのまま読む（置き場が 2 つに割れない）"""
        got = self.start(request="request_ok.json", features_off="world")
        self.assertEqual(startrec.read(self.artifacts), self.record(got))
        self.assertEqual(self.artifacts / got["record"]["path"], startrec.path(self.artifacts))

    def test_spec_word_checked(self):
        """L-E27: spec は空か on。on は input.spec を真に"""
        self.assertIn("spec", self.refused(request="request_ok.json", spec="yes"))
        self.assertTrue(self.record(self.start(request="request_ok.json", spec="on"))["input"]["spec"])
        self.assertFalse(self.record(self.start(request="request_ok.json"))["input"]["spec"])

    def test_spec_on_reaches_the_ports(self):
        """#550: spec=on は配る値 spec で judge の graph と spec-check-run に渡る（拒んだ・落ちた返りは偽）"""
        self.assertIs(self.start(request="request_ok.json", spec="on")["ports"]["spec"], True)
        self.assertIs(self.start(request="request_ok.json")["ports"]["spec"], False)
        self.assertIs(self.start(base="base", spec="on")["ports"]["spec"], False)
        self.assertIs(start.fallback("落ちた")["ports"]["spec"], False)

    def test_spec_refused_without_request_text(self):
        """L-E29: spec=on なのに依頼の文（依頼も PR の題と本文も）が無ければ止める"""
        self.assertIn("依頼の文", self.refused(base="base", spec="on"))

    def test_spec_refused_without_findings_or_pr_text(self):
        """#526: findings を省いた依頼は受けるが、spec=on では仕様の書き手が読む物が無いので止める。名指した PR の題と本文が在れば足りる"""
        answers_only = self.outside("answers_only.json", json.dumps({"answers": [{"question": "q1", "text": "a"}]}))
        got = self.start(request=str(answers_only), base="base", spec="on")
        self.assertEqual((got["ok"], got["stop_reason"], got["ask"]), (False, stopby.START_REFUSED, False), got)
        self.assertIn("依頼の文", got["reason"])
        self.assertIn("refused", self.record(got))
        pr_only = self.outside("pr_only.json", json.dumps({"pr": [7]}))
        got, _ = self.start_with_gh(self.pr_reads(), request=str(pr_only), base="base", spec="on")
        self.assertEqual((got["ok"], got["stop_reason"]), (False, stopby.START_REFUSED), got)
        self.assertIn("依頼の文", got["reason"])
        got, _ = self.start_with_gh(self.pr_reads(), pr="7", spec="on")
        self.assertTrue(got["ok"], got)

    def test_features_cut_is_recorded(self):
        """L-E33: 機能の切り替えは始めの記録の features_cut に載り、block には line が値で配る（world の段を回すか）"""
        got = self.start(request="request_ok.json", features_off="world")
        self.assertIn("world", self.record(got)["features_cut"])
        self.assertIs(got["ports"]["world"], False)
        self.assertIs(self.start(request="request_ok.json")["ports"]["world"], True)

    def test_test_cmd_and_tdd_suite_are_recorded(self):
        """L-E38: test_cmd・tdd_suite を始めの記録に置き、test-gate と fix には配る値で渡す"""
        got = self.start(request="request_ok.json", test_cmd="make test", tdd_suite="./junit-suite.sh")
        doc = self.record(got)
        self.assertEqual((doc["test_cmd"], doc["tdd_suite"]), ("make test", "./junit-suite.sh"))
        self.assertEqual((got["ports"]["test_cmd"], got["ports"]["tdd_suite"]), ("make test", "./junit-suite.sh"))

    def test_unknown_versions_say_why(self):
        """L-E45: 分からない版の値は null にし、unknown に理由を書く"""
        bare = self.tmp / "bare-bin"   # git だけを置いた PATH（claude が無い）
        bare.mkdir()
        (bare / "git").symlink_to(shutil.which("git"))
        with mock.patch.dict(os.environ, {"PATH": str(bare)}), \
                mock.patch.object(start.ports, "lib_root", return_value=self.tmp / "nowhere" / "lib"):
            doc = self.record(self.start(request="request_ok.json"))["versions"]
        for key in ("archon", "claude_code"):
            with self.subTest(key=key):
                self.assertIsNone(doc[key])
                self.assertTrue(doc["unknown"][key])
        self.assertTrue(doc["python"])
        self.assertTrue(doc["platform"])

    def test_start_gate_text_names_entry_features_and_answers(self):
        """L-E48・L-G09: 起動の承認ノードの文は冒頭 3 行・入口の文・機能・最後の承認ノードの開き方・答え方の 2 行を持つ"""
        text = self.start(request="request_ok.json", final_gate="when_needed", features_off="world")["gate_text"]
        self.assertTrue(text.splitlines()[0].startswith("起きたこと: "))
        self.assertIn("入口: 差分なし（HEAD）・依頼 2 件", text)
        self.assertIn("機能: ", text)
        self.assertIn("world off", text)
        self.assertIn("最後の承認ノード: when_needed", text)
        self.assertIn(answer.line(RUN, "continue", "<一言>"), text)
        self.assertIn(answer.line(RUN, "stop", "<理由>"), text)

    def test_start_gate_text_names_the_deliver_word(self):
        """#751: 始めの承認ノードの頭の行に出口の語（deliver）を、最後の承認ノードの開き方の次の行に出す"""
        rows = {"": "- 出口（deliver）: 空（既定）——差分を run の置き場に置くだけで、対象の repo に何も書かない",
                "pr": "- 出口（deliver）: pr——最後の承認ノードを通ると、報告の前に run の枝へ commit を積んで push し、"
                      "対象の既定の枝へ向けた PR を作る（merge はしない）"}
        for word, row in rows.items():
            with self.subTest(deliver=word):
                got = self.start(request="request_ok.json", deliver=word)
                lines = got["gate_text"].splitlines()
                self.assertIn(row, lines)
                self.assertEqual(lines.index(row), lines.index("- 最後の承認ノード: always") + 1)
                self.assertEqual(got["ports"]["deliver"], word)

    def test_heavy_thickness_is_taken(self):
        got = self.start(request="request_ok.json", thickness="重厚")
        self.assertTrue(got["ok"], got)
        doc = self.record(got)
        self.assertEqual(doc["thickness"], "重厚")
        self.assertNotIn("judge_verify", doc[entry.FEATURES_CUT_KEY])
        self.assertEqual(doc["features"]["judge_verify"], "on")
        self.assertEqual(doc["features"]["review_tree"], "on")
        self.assertIn("段: 重厚", got["gate_text"])
        self.assertNotIn("judge_verify off", got["gate_text"])
        self.assertNotIn("review_tree auto", got["gate_text"])
        plain = self.start(request="request_ok.json")
        self.assertIn("judge_verify", self.record(plain)[entry.FEATURES_CUT_KEY])
        self.assertIn("judge_verify off", plain["gate_text"])

    def test_heavy_with_a_named_off_is_refused(self):
        """issue #561 の求め 4: 名指した重厚が足す機能を features_off で切ると、入口がぶつかった機能を名指して止める"""
        for off in ("judge_verify", "review_tree", "tdd_lanes, review_tree"):
            with self.subTest(off=off):
                reason = self.refused(request="request_ok.json", thickness="重厚", features_off=off)
                self.assertIn("thickness=重厚", reason)
                self.assertIn("review_tree" if "review_tree" in off else "judge_verify", reason)
                self.assertNotIn("tdd_lanes", reason)
        self.assertTrue(self.start(request="request_ok.json", thickness="重厚", features_off="tdd_lanes")["ok"])
        for thickness in ("", "自動", "軽量", "標準"):
            with self.subTest(thickness=thickness):
                self.assertTrue(self.start(request="request_ok.json", thickness=thickness, features_off="judge_verify")["ok"])

    def test_gate_text_has_the_depth_word(self):
        """L-E49: 頭の行に段（thickness と（既定））・機能・最後の承認ノード・修正前のテストの任せ先の注を並べる"""
        text = self.start(request="request_ok.json")["gate_text"]
        self.assertIn("段: 自動（既定）", text)
        self.assertIn("修正前のテスト: 宣言も test_cmd も無い", text)
        text = self.start(request="request_ok.json", thickness="軽量", test_cmd="make test")["gate_text"]
        self.assertIn("- 段: 軽量\n", text)
        self.assertNotIn("修正前のテスト:", text)


class PortsCase(Seeded):
    """配る値（docs/design/line.md の 1.6）の欄ごとの式"""

    def test_every_field_is_dealt_in_the_yaml_order(self):
        import yaml
        doc = yaml.safe_load((LINE / "works-factory-line.yaml").read_text(encoding="utf-8"))
        [node] = [n for n in doc["nodes"] if n["id"] == "start"]
        shape = node["output_format"]["properties"]["ports"]
        got = self.start(request="request_ok.json")["ports"]
        self.assertEqual(list(got), list(shape["properties"]))
        self.assertEqual(list(deal.empty()), list(shape["properties"]))
        self.assertEqual(shape["required"], list(shape["properties"]))
        names = {"string": str, "boolean": bool, "object": dict, "array": list}
        for name, value in (*got.items(), *deal.empty().items()):
            with self.subTest(field=name):
                want = shape["properties"][name]["type"]
                self.assertTrue(any(isinstance(value, names[t]) for t in ([want] if isinstance(want, str) else want)), (name, value))

    def test_empty_has_blank_values(self):
        empty = deal.empty()
        self.assertEqual((empty["request"], empty["carried"], empty["verify_by_tier"], empty["prior_rows"]), ("[]", "[]", {}, []))
        self.assertEqual({k: v for k, v in empty.items() if isinstance(v, bool)}, dict.fromkeys(deal.FLAGS, False))

    def test_entry_needs_an_empty_diff_and_request_rows(self):
        """entry は入口の差分が空で依頼の行が 1 件以上の時だけ（判定から入る run）。差分の在る run・依頼の無い run は空"""
        want = str((self.repo / "request_ok.json").resolve())
        got = self.start(request="request_ok.json")["ports"]
        self.assertEqual((got["entry"], got["request_origin"], got["request_scope"]), (f"人の依頼（{want}）",) * 2 + (True,))
        changed = self.start(request="request_ok.json", base="base")["ports"]
        self.assertEqual((changed["entry"], changed["request_origin"], changed["request_scope"]), ("", f"人の依頼（{want}）", False))
        rows = self.outside("answers_only.json", json.dumps({"answers": [{"question": "q", "text": "a"}]}))
        none = self.start(request=str(rows), base="base")["ports"]
        self.assertEqual(none["entry"], "")
        self.assertEqual(deal.entry_origin({"input": {"diff": {"empty": True}, "requests": 0}}), "", "差分が空でも依頼の行が無ければ空")
        self.assertEqual(deal.entry_origin({"input": {"diff": {"empty": True}, "requests": 1}}), "人の依頼（依頼の行）")

    def test_verify_by_tier_follows_the_naming(self):
        """判定の裏取りは名指さなければ重厚の段だけが足す。features_on で名指せば全段で回し、features_off で名指せば全段で回さない"""
        self.assertEqual(self.start(request="request_ok.json")["ports"]["verify_by_tier"], {"軽量": False, "標準": False, "重厚": True})
        self.assertEqual(self.start(request="request_ok.json", features_on="judge_verify")["ports"]["verify_by_tier"],
                         {"軽量": True, "標準": True, "重厚": True})
        self.assertEqual(self.start(request="request_ok.json", features_off="judge_verify")["ports"]["verify_by_tier"],
                         {"軽量": False, "標準": False, "重厚": False})

    def test_tree_named_reads_only_the_naming(self):
        self.assertEqual(self.start(request="request_ok.json")["ports"]["tree_named"], "")
        self.assertEqual(self.start(request="request_ok.json", features_on="review_tree")["ports"]["tree_named"], "on")
        self.assertEqual(self.start(request="request_ok.json", features_off="review_tree")["ports"]["tree_named"], "off")

    def test_thickness_and_forced(self):
        for word, (thickness, forced) in (("", ("auto", "")), ("自動", ("auto", "")), ("軽量", ("light", "軽量")),
                                          ("標準", ("standard", "標準")), ("重厚", ("heavy", "重厚"))):
            with self.subTest(thickness=word):
                got = self.start(request="request_ok.json", thickness=word)["ports"]
                self.assertEqual((got["thickness"], got["forced"]), (thickness, forced))

    def test_parallel_and_design_only_and_web(self):
        got = self.start(request="request_ok.json", design_only="true")["ports"]
        self.assertEqual((got["parallel"], got["design_only"], got["web"], got["has_checks"]), (True, True, "on", False))
        for off in ("fix_lanes", "tdd_lanes"):
            with self.subTest(off=off):
                self.assertIs(self.start(request="request_ok.json", features_off=off)["ports"]["parallel"], False)

    def test_carried_constraints_are_placed_and_dealt(self):
        """依頼の容器の constraints は carried.json に置き、配る値 carried がその pointer。前の run の前提の検算が運んだ実測の行
        （measured_how が carry.CARRIED_HOW_HEAD で始まる）が在れば carried_measured が真（raise が目を省かない）"""
        import carry
        plain = self.start(request="request_ok.json")["ports"]
        self.assertEqual((plain["carried"], plain["carried_measured"]), ("[]", False))
        rows = [{"text": "API は 1 秒で切れる", "measured_how": carry.CARRIED_HOW, "kind": "実測"}]
        req = self.outside("carried.json", json.dumps({"findings": [{"where": "a", "text": "b"}], "constraints": rows},
                                                      ensure_ascii=False))
        got = self.start(request=str(req))["ports"]
        self.assertEqual(got["carried"], {"type": "archon_artifact", "run_id": RUN, "path": "carried.json"})
        self.assertIs(got["carried_measured"], True)
        self.assertEqual(json.loads((self.artifacts / "carried.json").read_text(encoding="utf-8")), rows)

    def test_lang_and_review_rev(self):
        got = self.start(request="request_ok.json", lang="English")["ports"]
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual((got["lang"], got["review_rev"], got["base_rev"], got["base"]), ("English", head, head, head))


class TestPolicyBrief(Seeded):
    def test_policy_port_points_at_the_frozen_copy(self):
        """方針の文書は run の始めに固め、配る値 policy は固めた写しを指す（始めの後に policy_md の文書を書き換えても固めた版。
        写しを役に貼る側は fix の試験。integration.md の 4.2-7）"""
        pmd = self.tmp / "policy.md"
        pmd.write_text("方針の印: 固めた版\n", encoding="utf-8")
        got = self.start(request="request_ok.json", policy_md=str(pmd))
        pmd.write_text("方針の印: 書き換えた版\n", encoding="utf-8")
        copy = pathlib.Path(got["ports"]["policy"])
        self.assertEqual(str(copy), self.record(got)["policy"]["copy"])
        self.assertEqual(copy.read_text(encoding="utf-8"), "方針の印: 固めた版\n")
        self.assertEqual(self.start(request="request_ok.json")["ports"]["policy"], "", "方針の文書の無い run は空")


class ScriptCase(unittest.TestCase):
    """start を子のプロセスで回す（line の inputs: は INPUTS_<名> で届く）"""

    def setUp(self):
        self.run = kit.Run(self, "line")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)

    def test_script_returns_the_yaml_shape(self):
        got = self.run.script("start", request="request_ok.json")
        self.assertTrue(got["ok"], got)
        self.assertEqual(set(got), {"ok", "stop_reason", "reason", "record", "prior_failures", "ask", "gate_text", "unattended",
                                    "design_only", "final_gate", "from_fixture", "fixture", "from_spec", "ports"})
        self.assertEqual(got["record"]["path"], "r1/start.json")
        self.assertTrue((self.run.artifacts / "r1" / "start.json").is_file())

    def test_script_does_not_fall_without_lib(self):
        """lib の import が落ちても fallback の止めの語で返す（L-G52）"""
        env = hermetic.child_env(**{**self.run.environ(request="request_ok.json"), "WORKS_FACTORY_ROOT": str(self.run.repo)})
        done = subprocess.run([sys.executable, str(LINE / "scripts" / "start.py")], cwd=self.run.repo, env=env, capture_output=True,
                              text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertEqual((got["ok"], got["stop_reason"], got["ports"]), (False, "works:line-script", deal.empty()))


if __name__ == "__main__":
    unittest.main()
