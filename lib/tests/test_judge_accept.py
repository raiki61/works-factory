"""判定のブロックの受け付けと支度の芯（lib/judge_accept）の試験。

今の works の試験（test_blk_judge・test_blk_premises・test_blk_purpose・test_blk_material・test_blk_spec・test_rejudge・
test_judge_verify・test_structure_units・test_accept の TestJudge・TestIntake）が盤面の上で確かめていた場面を、値を渡す形に写した。
各試験の docstring に元の試験の名を書く。
"""
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import accept as core_accept  # noqa: E402
import carry  # noqa: E402
import diverted  # noqa: E402
import judge_accept as ja  # noqa: E402
import judgeverify as jv  # noqa: E402
import rolekit  # noqa: E402
import specblk  # noqa: E402
import stopby  # noqa: E402
import webget  # noqa: E402
import worldblk  # noqa: E402
import worldmark  # noqa: E402
from engine.util import Reject  # noqa: E402
from tests.bin import gitkit  # noqa: E402


class TablesCase(unittest.TestCase):
    def test_is_open_follows_label_and_disposition(self):
        """元 test_judge_verify の開いた単位の数え（検証器の is_open）"""
        self.assertTrue(ja.is_open({"label": "block"}))
        self.assertTrue(ja.is_open({"label": "suggest", "disposition": "do-now"}))
        self.assertFalse(ja.is_open({"label": "suggest", "disposition": "defer"}))
        self.assertFalse(ja.is_open({"label": "nit"}))


# ================================================================ 依頼と判定


_TARGET_SEED = LIB.parent / "tests" / "e2e" / "target-seed"
_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
_REQUEST = [{"where": "stats.py", "text": "mean([1, 2, 3]) が 2 でなく 3 を返す。test_mean_of_three が赤"},
              {"where": "stats.py", "text": "clamp(15, 0, 10) が 10 でなく 0 を返す。test_clamp_above_range が赤"}]


def _unit(key, how_patterns, counts, total, label="block", disposition="do-now"):
    return {"key": key, "label": label, "disposition": disposition,
            "reason": f"事実: {key}。反証: 意図の取り違えを当たったが、関数名とテストが逆を期待する",
            "origin_analysis": "写し間違いの形",
            "why_chain": ["テストが境界の値を試していない"],
            "class_query": {"how": {"patterns": how_patterns, "fixed": True, "paths": ["stats.py"], "count": "lines"},
                            "counts": counts, "total": total}}


def _judge_ok():
    """元 works/tests/replies/judge_ok.json の形（今の works の良い判定の見本）"""
    return {
        "framing": "依頼の 2 件はどちらも stats.py の算術の取り違え",
        "one_shot": "mean の分母を len(xs) に、clamp の上限の枝の戻り値を hi に直す",
        "units": [_unit(_MEAN, ["(len(xs) - 1)"], "defects", 1), _unit(_CLAMP, ["return lo"], "population", 2)],
        "questions": [], "materials_missing": [], "carried_r1": [],
        "one_shot_closes": [_MEAN, _CLAMP],
        "precedents": [
            {"key": _MEAN, "problem": "数列の算術平均を求める", "source": "Python の statistics.mean の文書の節",
             "verdict": "adopt", "reason": "分母はデータ点の数 len(xs)"},
            {"key": _CLAMP, "problem": "値を下限と上限の間に収める", "source": "numpy.clip の文書の節",
             "verdict": "adopt", "reason": "上限を超えた値は上限に置き換える"}],
    }


class _JudgeBase(unittest.TestCase):
    """種（tests/e2e/target-seed）を写して commit した使い捨ての対象リポジトリと、判定の置き場 J（判定の支度が diagnose-tree.json を、入口が
    request.json と start.json を置いた後の姿）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.base = gitkit.committed_copy(self.repo, _TARGET_SEED)
        self.jdir = tmp / "art" / "judge"
        self.jdir.mkdir(parents=True)
        ja.snap_tree(self.jdir, ja.DIAGNOSE_TREE_FILE, self.repo)
        ja.write_json(self.jdir / ja.REQUEST_FILE, _REQUEST)
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({}))

    def take(self, reply, **kw):
        return ja.take(self.jdir, reply, self.repo, **kw)

    def judgment(self):
        return json.loads((self.jdir / ja.JUDGMENT_FILE).read_text(encoding="utf-8"))


class RequestCase(unittest.TestCase):
    def test_request_rows_pass_the_add_type(self):
        """元 test_accept.TestIntake.test_intake_accepts_request（依頼の行が rules の add の型を通る）"""
        self.assertEqual(ja.check_request(_REQUEST, "持ち主"), {"ok": True, "reason": ""})
        self.assertEqual(ja.add(_REQUEST, "持ち主"), {"round": 1, "origin": "持ち主", "findings": _REQUEST})

    def test_unknown_key_is_rejected(self):
        """元 test_accept.TestIntake.test_intake_rejects_unknown_key"""
        rows = copy.deepcopy(_REQUEST)
        rows[0]["severity"] = "high"
        got = ja.check_request(rows, "持ち主")
        self.assertIs(got["ok"], False)
        self.assertIn("severity", got["reason"])
        self.assertIn("add の形", got["reason"])

    def test_non_list_and_empty_are_rejected(self):
        """元 test_accept.TestIntake.test_intake_rejects_non_list（findings は空でない配列。REQUEST_SCHEMA の minItems 1）"""
        self.assertIs(ja.check_request({"where": "stats.py", "text": "x"}, "持ち主")["ok"], False)
        self.assertIs(ja.check_request([], "持ち主")["ok"], False)
        self.assertIs(ja.check_request([{"where": "stats.py"}], "持ち主")["ok"], False)

    def test_check_inputs_refuses_misspelled_key_and_unknown_value(self):
        """元 test_blk_spec の頭の注（写しの rules の check_inputs が flow=spec・gates=merge 以外を init で拒む）"""
        ja.check_inputs({})
        ja.check_inputs({"flow": "spec", "gates": "merge"})
        with self.assertRaises(Reject) as cm:
            ja.check_inputs({"gate": "merge"})
        self.assertIn("gates", str(cm.exception))
        with self.assertRaises(Reject) as cm:
            ja.check_inputs({"gates": "all"})
        self.assertIn("知らない値", str(cm.exception))


class JudgeTakeCase(_JudgeBase):
    def test_good_reply_is_written_as_judgment(self):
        """元 test_accept.TestJudge.test_judge_accepts_good_reply・test_blk_judge.ScriptCase.test_accept_good_and_bad_reply"""
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(got["judgment_file"], str(self.jdir / ja.JUDGMENT_FILE))
        self.assertEqual(sorted(got["open_units"]), sorted([_MEAN, _CLAMP]))
        doc = self.judgment()
        for k in ("units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes",
                  "precedents"):
            self.assertIn(k, doc)

    def test_label_outside_the_table_is_rejected(self):
        """元 rules の judge_output の「units[i] の label が不正」（検証器の表 LABELS の外。元の試験に同じ場面の物は無い）"""
        reply = _judge_ok()
        reply["units"][0]["label"] = "major"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("label", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_open_unit_why_chain_must_be_lines(self):
        """計画の「開いた単位の why_chain が足りないと拒む」。元の型（graph の p2.diagnose の schema）は why_chain を文の配列にし、
        元の rules に段の数の規則は無い。型の外（文でない段）を拒む"""
        reply = _judge_ok()
        reply["units"][0]["why_chain"] = [{"段": 1}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("why_chain", got["reason"])

    def test_open_unit_without_class_query_is_rejected(self):
        """元 rules の judge_output の「今の周に直す単位に class_query が無い」（元 test_blk_judge の判定の受け付けの場面）"""
        reply = _judge_ok()
        del reply["units"][1]["class_query"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("class_query", got["reason"])

    def test_class_query_examples_that_do_not_match_are_rejected(self):
        """元 test_blk_judge.QueryExamplesCase.test_hit_the_query_does_not_match_is_rejected・
        test_accept.TestJudge.test_judge_tests_query_examples_itself"""
        reply = _judge_ok()
        cq = reply["units"][0]["class_query"]
        cq["hits"], cq["misses"] = ["    return sum(xs) / len(xs)"], ["    return 0"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("class_query の例が問いと合わない", got["reason"])
        cq["hits"], cq["misses"] = ["    return sum(xs) / (len(xs) - 1)"], ["    return sum(xs) / len(xs)"]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(self.judgment()["units"][0]["class_query"]["misses"], cq["misses"], "例は judgment に戻る")
        saved = json.loads((self.jdir / "query-examples.json").read_text(encoding="utf-8"))
        self.assertEqual(saved[_MEAN], {"hits": cq["hits"], "misses": cq["misses"]})

    def test_precedent_source_not_in_world_rows_is_rejected(self):
        """元 test_blk_judge.WorldSourceCase.test_take_refuses_unknown_world_source"""
        reply = _judge_ok()
        reply["precedents"][0]["source"] = "world:no-such-class"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("precedents の出どころが世界の解の行に無い", got["reason"])

    def test_question_without_kind_or_status_is_rejected(self):
        """元 rules の judge_output の問いの kind・status の照らし（検証器の QUESTION_KINDS・QUESTION_STATUS）"""
        reply = _judge_ok()
        reply["questions"] = [{"key": "q1", "reason": "決まらない"}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("kind", got["reason"])
        self.assertIn("status", got["reason"])
        reply["questions"] = [{"key": "q1", "kind": "fork", "status": "held", "reason": "決まらない", "origin": _MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("options", got["reason"])

    def test_judge_that_changed_the_tree_is_rejected(self):
        """元 test_accept.TestJudge.test_judge_rejects_dirty_tree・test_blk_judge.ScriptCase.test_accept_rejects_file_added_after_intake"""
        (self.repo / "extra.txt").write_text("読むだけの役が書いた\n", encoding="utf-8")
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("extra.txt", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_judge_that_moved_head_is_rejected(self):
        """元 test_blk_judge.ScriptCase.test_accept_rejects_commit_after_intake"""
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "extra.txt")
        gitkit.git(self.repo, "commit", "-qm", "役が commit した")
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリー", got["reason"])

    def test_without_tree_record_the_tree_must_be_clean(self):
        """元 test_blk_judge.ScriptCase.test_check_judge_without_snapshot_needs_clean_tree"""
        (self.jdir / ja.DIAGNOSE_TREE_FILE).unlink()
        self.assertIs(self.take(_judge_ok())["ok"], True)
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリーに変更が在る", got["reason"])

    def test_precedent_without_searched_is_rejected(self):
        """元 test_accept.TestJudge.test_judge_rejects_precedent_without_searched"""
        reply = _judge_ok()
        reply["precedents"][0].update(verdict="not_found", source="")
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("searched", got["reason"])

    def test_awaiting_material_needs_awaiting_question(self):
        """元 test_line_a の test_reply_without_awaiting_goes_back_to_judge（awaiting_human の素材に kind=awaiting の問いが無い）"""
        ja.write_json(self.jdir / "materials.json", {"parallel_pr": {"status": "awaiting_human", "reason": "gh が無い"}})
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("素材 'parallel_pr' が awaiting_human なのに台帳に kind=awaiting で無い", got["reason"])
        reply = _judge_ok()
        reply["questions"] = [{"key": "parallel_pr: 並行 PR を確かめる", "kind": "awaiting", "status": "held",
                               "reason": "gh が無く確かめられない", "origin": "parallel_pr"}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])

    def test_materials_missing_is_rejected(self):
        """元 rules の judge_output の materials_missing の拒否（graph の enforced_by）"""
        reply = _judge_ok()
        reply["materials_missing"] = ["hygiene"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("hygiene", got["reason"])

    def test_out_of_purpose_rows_are_checked_against_material_rows(self):
        """元 test_out_of_purpose（outpurpose.problems を盤面の材料の行に当てる）と judgetake.take の目的の外の行の扱い"""
        reply = _judge_ok()
        reply["out_of_purpose"] = [{"source": "局所レビュー", "where": "no-such.py", "why_outside": "凍結した目的の外の所見"}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("out_of_purpose", got["reason"])
        ja.write_json(self.jdir / "material-hygiene.json", {
            "role": "hygiene", "materials": {"hygiene": {"status": "found", "count": 1, "detail": "1 件"}},
            "reply": {"findings": [{"where": "test_stats.py", "text": "使わない import が残る"}]}})
        reply["out_of_purpose"] = [{"source": "衛生", "where": "test_stats.py", "why_outside": "凍結した目的の外の衛生の所見"}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(self.judgment()["out_of_purpose"], reply["out_of_purpose"])
        saved = json.loads((self.jdir / "out-of-purpose.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["rounds"]["1"][0]["found"][0]["from"], "p1.hygiene")

    def test_material_rows_read_material_files_and_request(self):
        """元 outpurpose.material_rows（P1 の節の出力の where・text の行と今の周の依頼の行）の書き直し"""
        ja.write_json(self.jdir / "material-local-review.json", {
            "role": "local-review", "materials": {}, "reply": {"lenses": [{"skill": "code-review", "findings": [
                {"where": "stats.py:9", "text": "分母", "mechanism": "m"}]}]}})
        ja.write_json(self.jdir / "material-prior-decisions.json", {
            "role": "prior-decisions", "materials": {}, "reply": {"decisions": [{"where": "x", "text": "y"}]}})
        rows = ja.material_rows(self.jdir)
        self.assertIn({"where": "stats.py:9", "text": "分母", "mechanism": "m", "from": "p1.local_review / code-review"}, rows)
        self.assertNotIn("x", [r["where"] for r in rows], "P0 の素材は材料の行に入らない（元は p1.* の節だけ）")
        self.assertEqual([r["where"] for r in rows if r["from"].startswith("依頼")], ["stats.py", "stats.py"])

    def test_unbound_answer_without_tie_is_rejected(self):
        """元 test_blk_judge.AnswerTiesTakeCase.test_unbound_answer_without_tie_is_rejected_by_question"""
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"answers": [{"question": "どれを採るか", "text": "A を採る"}]}))
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("依頼の答え 'どれを採るか'", got["reason"])
        reply = _judge_ok()
        reply["answer_ties"] = [{"answer": "どれを採るか", "to": _MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        saved = json.loads((self.jdir / "answer-ties.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["rounds"]["1"], reply["answer_ties"])

    def test_carried_r1_tells_to_copy_the_where(self):
        """元 test_accept.TestJudge.test_judge_carried_r1_tells_to_copy_the_where（前の周の R1 が在る時だけ当たる道）"""
        reply = _judge_ok()
        reply["carried_r1"] = [{"where": "stats.py:4", "disposition": "decline", "why": "削除すると mean が壊れる"},
                               {"where": "stats.py:3", "disposition": "decline", "why": "削除すると mean が壊れる"}]
        self.assertIs(self.take(reply)["ok"], True, "1 run は 1 周で、前の周の R1 は無い")
        got = self.take(reply, prev_deletions=[{"where": "stats.py:3"}])
        self.assertIs(got["ok"], False)
        self.assertIn("carried_r1[0] の where 'stats.py:4'", got["reason"])
        self.assertIn("削除候補の where を字面のまま写せ", got["reason"])
        self.assertNotIn("no で指せ", got["reason"])

    def test_fork_held_twice_must_escalate(self):
        """元 rules の _fork_moves_forward（前の周も fork で免除された出どころを held のまま持ち越さない）"""
        reply = _judge_ok()
        reply["questions"] = [{"key": "岐路", "kind": "fork", "status": "held", "reason": "推し: A——安い",
                               "origin": _MEAN, "options": ["A: 安い", "B: 堅い"]}]
        reply["precedents"].append({"key": "岐路", "problem": "選び方の問題", "source": "文書の節", "verdict": "adopt",
                                    "reason": "当たった", "undecided_because": "先例が割れて決まらない（①）"})
        first = self.take(reply)
        self.assertIs(first["ok"], True, first["reason"])
        got = self.take(reply, prev_questions=[{"kind": "fork", "status": "held", "origin": _MEAN}])
        self.assertIs(got["ok"], False)
        self.assertIn("escalate に上げて", got["reason"])

    def test_declared_route_errors(self):
        """元 rules の _declared_route_errors（履歴の判定 p2.history の欄。このブロックの判定は当てない部品として持つ）"""
        out = {"units": [{"key": "u", "label": "block"}], "declared_routed": [{"key": "穴", "route": "to_unit", "unit_key": "v"}]}
        errs = ja._declared_route_errors(out, [{"key": "穴"}, {"key": "別の穴"}])
        self.assertTrue(any("unit_key が今の周の units に無い" in e for e in errs))
        self.assertTrue(any("'別の穴' を振り分けていない" in e for e in errs))

    def test_ignored_file_added_by_the_judge_is_rejected(self):
        """元 test_accept.py:178 の test_judge_rejects_ignored_file_without_snapshot・:186 の
        test_judge_rejects_ignored_file_after_snapshot・test_blk_judge.py:437・447・454（git が無視するファイルの増減と書き換えも拒む）"""
        cache = self.repo / "__pycache__"
        cache.mkdir()
        old = cache / "old.pyc"
        old.write_bytes(b"old")
        ja.snap_tree(self.jdir, ja.DIAGNOSE_TREE_FILE, self.repo)
        self.assertIs(self.take(_judge_ok())["ok"], True, "前から在って変わらない無視されるファイルは通る")
        (self.jdir / ja.JUDGMENT_FILE).unlink()
        (self.repo / ".env.pyc").write_bytes(b"x")
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn(".env.pyc", got["reason"])
        (self.repo / ".env.pyc").unlink()
        old.write_bytes(b"new")
        self.assertIs(self.take(_judge_ok())["ok"], False, "名前が同じまま中身だけ変わっても拒む")
        old.unlink()
        (self.jdir / ja.DIAGNOSE_TREE_FILE).unlink()
        (cache / "stats.cpython-314.pyc").write_bytes(b"x")
        got = self.take(_judge_ok())
        self.assertIs(got["ok"], False, "写しが無い時も無視されるファイルを数える")
        self.assertIn("__pycache__", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_newlines_in_key_and_reason_are_folded(self):
        """元 rules の judge_output の 1 行の欄（ONE_LINE_FIELDS）の正規化（review-loop.py:2508。元の試験に同じ場面の物は無い）"""
        reply = _judge_ok()
        reply["units"][0]["key"] = _MEAN.replace(": ", ":\n  ")
        reply["units"][0]["reason"] = "事実: 分母が違う。\n反証: 意図の取り違えを当たった"
        reply["questions"] = [{"key": "実機で\n確かめる", "kind": "field", "status": "held", "reason": "実機が\n要る"}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        doc = self.judgment()
        self.assertEqual(doc["units"][0]["key"], _MEAN)
        self.assertEqual(doc["units"][0]["reason"], "事実: 分母が違う。 反証: 意図の取り違えを当たった")
        self.assertEqual((doc["questions"][0]["key"], doc["questions"][0]["reason"]), ("実機で 確かめる", "実機が 要る"))

    def test_duplicate_key_and_suggest_without_disposition_are_rejected(self):
        """元 rules の judge_output の key の重複・suggest の disposition・defer の構造的理由（review-loop.py:2520-2530）"""
        reply = _judge_ok()
        reply["units"].append(copy.deepcopy(reply["units"][0]))
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn(f"units[2] の key が重複: {_MEAN}", got["reason"])
        reply = _judge_ok()
        reply["units"].append(_unit("stats.py fmt: 桁", ["x"], "population", 0, label="suggest"))
        del reply["units"][2]["disposition"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("units[2]（suggest）に disposition（do-now / defer）が無い", got["reason"])
        reply["units"][2].update(disposition="defer", reason="")
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("units[2] の defer に構造的理由が無い", got["reason"])

    def test_engine_recounts_the_class_query_total(self):
        """元 rules の judge_output の class_query の数え直し（review-loop.py:2531-2550 と _run_query）。違う total は engine の数に
        置き換えて注記し、engine が 0 件なら役の数を残して注記する"""
        reply = _judge_ok()
        reply["units"][1]["class_query"]["total"] = 5
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertIn("class_query の件数を engine が走らせた値に置き換えた: units[1].class_query.total 5 → 2", got["reason"])
        cq = self.judgment()["units"][1]["class_query"]
        self.assertEqual(cq["total"], 2)
        self.assertIn("役の書いた total は 5", cq["note"])
        reply = _judge_ok()
        reply["units"][1]["class_query"].update(how={"patterns": ["no-such-line-anywhere"], "fixed": True, "paths": ["stats.py"],
                                                    "count": "lines"}, total=3)
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertIn("engine の数が 0 件なので置き換えなかった: units[1].class_query（役 3 / engine 0）", got["reason"])
        cq = self.judgment()["units"][1]["class_query"]
        self.assertEqual(cq["total"], 3)
        self.assertIn("engine が how を走らせると 0 件", cq["note"])

    def test_defects_query_needs_misses_and_must_not_match_the_fixed_form(self):
        """元 test_blk_judge.py:604 の QueryExamplesCase.test_defects_query_without_misses_is_rejected・:613 の
        test_defects_query_matching_fixed_form_is_rejected"""
        reply = _judge_ok()
        cq = reply["units"][0]["class_query"]
        cq["hits"] = ["    return sum(xs) / (len(xs) - 1)"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn(f"{_MEAN}: 欠陥の形を数える問い（counts: defects）に misses が無い", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())
        fixed = "    return sum(xs) / (len(xs) - 1)  # 直した"
        cq["misses"] = [fixed]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("直した後の正しい形にも当たる", got["reason"])
        self.assertIn(repr(fixed), got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_one_shot_closes_must_name_open_units(self):
        """元 rules の judge_output の一撃の反証（one_shot_closes。review-loop.py:2551-2558）"""
        reply = _judge_ok()
        reply["one_shot_closes"] = []
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("one_shot_closes が空", got["reason"])
        reply["one_shot_closes"] = [_MEAN, "stats.py: 無い単位"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("one_shot_closes に今の周の units に無い key: ['stats.py: 無い単位']", got["reason"])

    def test_question_ledger_targets_and_settled_state(self):
        """元 rules の judge_output の問いの台帳の照らし（review-loop.py:2559-2595。検証器の QUESTION_FIELDS・targets・NO_OPEN_ORIGIN・
        settled_state_errors）"""
        out = {"units": [], "questions": [{"key": "q", "kind": "field", "status": "held", "reason": "実機が要る", "severity": "high"}]}
        with self.assertRaises(Reject) as cm:
            ja.judge_output(out, self.jdir, "", "", {})
        self.assertIn("questions[0] に知らない欄: ['severity']", str(cm.exception))
        reply = _judge_ok()
        reply["units"].append(_unit("stats.py fmt: 桁", ["x"], "population", 0, label="nit"))
        for name, q, needle in (
                ("無い出どころ", {"kind": "stuck", "status": "held", "origin": "stats.py: 無い単位"},
                 "questions[0] の origin 'stats.py: 無い単位' が units にも defer 台帳にも無い"),
                ("無い depends", {"kind": "stuck", "status": "held", "origin": _MEAN, "depends": ["stats.py: 無い単位"]},
                 "questions[0] の depends 'stats.py: 無い単位' が units にも defer 台帳にも無い"),
                ("開いた単位の split", {"kind": "split", "status": "held", "origin": _MEAN},
                 f"questions[0]（split）の出どころ '{_MEAN}' が [block] / do-now"),
                ("開いたまま resolved", {"kind": "stuck", "status": "resolved", "resolution": "A を採る", "origin": _MEAN},
                 "出どころが [block] / do-now のまま resolved"),
                ("閉じたのに decided", {"kind": "stuck", "status": "decided", "resolution": "A を採る",
                                        "origin": "stats.py fmt: 桁"},
                 "出どころが閉じているのに decided")):
            with self.subTest(name):
                reply["questions"] = [{"key": "q", "reason": "決まらない", **q}]
                got = self.take(reply)
                self.assertIs(got["ok"], False)
                self.assertIn(needle, got["reason"])
        reply["questions"] = [{"key": "q", "reason": "決まらない", "kind": "stuck", "status": "decided", "resolution": "A を採る",
                               "origin": _MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])

    def test_open_unit_without_precedent_row_and_ask_without_undecided_because_are_rejected(self):
        """元 rules の _precedent_errors（review-loop.py:2445。今の周に直す単位と人へ回す問いの key ごとに先行例の行。人へ回す問いには
        undecided_because）"""
        reply = _judge_ok()
        del reply["precedents"][1]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn(f"precedents に '{_CLAMP}' の行が無い", got["reason"])
        reply = _judge_ok()
        reply["questions"] = [{"key": "実機で確かめる", "kind": "field", "status": "escalate", "reason": "実機が要る"}]
        reply["precedents"].append({"key": "実機で確かめる", "problem": "実機の振る舞い", "source": "機器の文書の節",
                                    "verdict": "adopt", "reason": "当たった"})
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("precedents['実機で確かめる'] に undecided_because が無い", got["reason"])
        reply["precedents"][-1]["undecided_because"] = "文書が機器の版ごとに割れて決まらない"
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])

    def test_answer_ties_rules(self):
        """元 test_blk_judge.py:743 の AnswerTiesTakeCase.test_literal_and_material_answers_need_no_tie・
        :757 の test_answer_hitting_two_reply_questions_needs_tie・:767 の test_tie_to_unknown_key_is_rejected・
        :774 の test_redesign_row_must_bind_to_open_unit_or_none・:790 の test_redesign_none_row_passes_and_is_reported・
        :803 の test_good_ties_are_taken_off_and_saved（結びの規則。報告の行は持たない）"""
        def answers(*rows):
            ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"answers": list(rows)}))

        def stuck(key):
            return {"key": key, "kind": "stuck", "status": "held", "reason": "割れる", "origin": _MEAN}

        with self.subTest("字の一致・測れていない素材・機械が立てる問いの答えは結びが要らない"):
            answers({"question": "q-1", "text": "0 を返す"}, {"question": "parallel_pr", "text": "並行する PR は無い"},
                    {"question": ja.ASK_KEYS["R3"], "text": "docs/ を見よ"})
            ja.write_json(self.jdir / ja.MATERIALS_FILE, {"parallel_pr": {"status": "not_run", "reason": "通信を拒まれた"}})
            reply = _judge_ok()
            reply["questions"] = [stuck("q-1")]
            got = self.take(reply)
            self.assertIs(got["ok"], True, got["reason"])
            (self.jdir / ja.MATERIALS_FILE).unlink()
        with self.subTest("返答の問い 2 つに当たる答え"):
            answers({"question": _MEAN, "text": "例外"})
            reply = _judge_ok()
            reply["questions"] = [stuck("q-1"), stuck("q-2")]
            got = self.take(reply)
            self.assertIs(got["ok"], False)
            self.assertIn("返答の複数の問いに当たる（q-1・q-2）", got["reason"])
            reply["answer_ties"] = [{"answer": _MEAN, "to": "q-2"}]
            got = self.take(reply)
            self.assertIs(got["ok"], True, got["reason"])
        with self.subTest("知らない key への結び"):
            answers({"question": "空の列の扱い", "text": "例外"})
            reply = _judge_ok()
            reply["answer_ties"] = [{"answer": "空の列の扱い", "to": "q-9"}]
            got = self.take(reply)
            self.assertIs(got["ok"], False)
            self.assertIn("to 'q-9' が今の返答の問いの key にも単位の key にも無い", got["reason"])
        answers()
        (self.jdir / "answer-ties.json").unlink()
        redesign = {"where": carry.REDESIGN_WHERE, "text": "R2 が redesign-needed: 独立設計と構造が合わない"}
        carry.place_prior(self.jdir, [redesign])
        defer = _unit("stats.py fmt: 桁", ["x"], "population", 0, label="suggest", disposition="defer")
        head = redesign["text"]
        for name, ties, needle in (("結び無し", [], "作り直しの行"),
                                   ("defer の単位", [{"redesign": head, "to": defer["key"]}], "[block] でも do-now でもない"),
                                   ("知らない行", [{"redesign": "別の行", "to": _MEAN}], "作り直しのセクションのどの行にも当たらない"),
                                   ("短い訳", [{"redesign": head, "none": "目的の外"}], "字に満たない")):
            with self.subTest(name):
                reply = _judge_ok()
                reply["units"].append(copy.deepcopy(defer))
                reply["answer_ties"] = ties
                got = self.take(reply)
                self.assertIs(got["ok"], False)
                self.assertIn(needle, got["reason"])
                self.assertFalse((self.jdir / "answer-ties.json").exists())
        for ties in ([{"redesign": head, "to": _MEAN}],
                     [{"redesign": head, "none": "反証で死んだ: 独立設計の構造は依頼の外の物で、この周の目的に入らない"}]):
            with self.subTest(ties[0]):
                reply = _judge_ok()
                reply["answer_ties"] = ties
                got = self.take(reply)
                self.assertIs(got["ok"], True, got["reason"])
                self.assertNotIn("answer_ties", self.judgment())
                saved = json.loads((self.jdir / "answer-ties.json").read_text(encoding="utf-8"))
                self.assertEqual(saved, {"rounds": {"1": ties}})


class JudgeAcceptCase(_JudgeBase):
    def test_accept_parses_and_collect_builds_exit(self):
        """元 test_blk_judge.ScriptCase.test_collect_builds_exit・test_accept_good_and_bad_reply"""
        bad = ja.accept(self.jdir, "{not json", self.repo)
        self.assertIs(bad["ok"], False)
        self.assertIn("JSON", bad["reason"])
        got = ja.accept(self.jdir, json.dumps(_judge_ok(), ensure_ascii=False), self.repo)
        self.assertIs(got["ok"], True, got["reason"])
        out = ja.collect(self.jdir)
        self.assertEqual((out["ok"], out["need_fix"], sorted(out["open_units"])), (True, True, sorted([_MEAN, _CLAMP])))
        self.assertEqual(out["one_shot"], _judge_ok()["one_shot"])

    def test_collect_without_judgment_gives_up_with_last_reject(self):
        """元 test_line_a の test_judge_gives_up_without_failing_the_run（3 回とも拒めば最後の拒否の文で止める）"""
        for _ in range(3):
            rolekit.with_done(self.jdir, ja.DIAGNOSE_ROLE, {"ok": False, "reason": "kind が不正"})
        out = ja.collect(self.jdir)
        self.assertEqual(out, {"ok": False, "open_units": [], "need_fix": False, "judgment_file": "", "one_shot": ""})
        stop = ja.read_stop(self.jdir)
        self.assertEqual(stop["stop_reason"], ja.JUDGE_STOP)
        self.assertIn("3 回とも", stop["reason"])
        self.assertIn("kind が不正", stop["reason"])


class _VerifyBase(_JudgeBase):
    def judged(self, *units):
        doc = {"framing": "依頼の 2 件はどちらも算術の取り違え", "one_shot": "直す", "units": list(units), "questions": []}
        return doc

    def answer(self, n, key, verdict="root", **extra):
        p = self.jdir / ja.VERIFY_ANSWERS_DIR / jv.ANSWER_FILE.format(n=n)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"unit": n, "verdict": verdict, "evidence_found": True,
                                    "evidence": f"stats.py:9 を読んだ。{key} の式が在る", "location_ok": True,
                                    "location": "stats.py:9", "why": "式を直せば期待どおりの値", **extra},
                                   ensure_ascii=False), encoding="utf-8")

    def synergy(self, body):
        p = self.jdir / ja.VERIFY_ANSWERS_DIR / jv.SYNERGY_FILE
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    def notes(self):
        return json.loads((self.jdir / jv.VERIFY_FILE).read_text(encoding="utf-8"))


class VerifyPrepCase(_VerifyBase):
    def test_places_are_under_the_brief_dir(self):
        """置き場の名が judgeverify の BRIEF_DIR・TREE_FILE と合う"""
        self.assertEqual(ja.VERIFY_ANSWERS_DIR, f"{jv.BRIEF_DIR}/answers")
        self.assertEqual(ja.VERIFY_TREE_FILE, f"{jv.BRIEF_DIR}/{jv.TREE_FILE}")

    def test_judgeverify_loads_before_judge_accept(self):
        """judgeverify を先に読んでも judge_accept が読み込める（読み込みの順で落ちる循環が無い）"""
        done = subprocess.run([sys.executable, "-c", "import judgeverify, judge_accept"], cwd=LIB,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_one_open_unit_or_off_does_not_go_and_writes_not_run(self):
        """元 test_judge_verify.PrepCase.test_no_judgment_or_one_open_unit_does_not_go・test_verify_off_does_not_go_and_clears"""
        one = self.judged(_unit(_MEAN, ["x"], "defects", 1), _unit(_CLAMP, ["x"], "defects", 1, label="nit"))
        got = ja.prep_on(self.jdir, one, self.repo, True)
        self.assertEqual((got["go"], got["prompt_file"]), (False, ""))
        self.assertTrue(got["reason"])
        self.assertEqual(self.notes()["units"], [])
        self.assertEqual(self.notes()["synergy"]["state"], jv.UNVERIFIED)
        two = self.judged(_unit(_MEAN, ["x"], "defects", 1), _unit(_CLAMP, ["x"], "defects", 1))
        got = ja.prep_on(self.jdir, two, self.repo, False)
        self.assertIs(got["go"], False)
        self.assertIn("judge_verify", got["reason"])
        self.assertEqual(ja.prep_on(self.jdir, None, self.repo, True)["go"], False)

    def test_two_open_units_write_briefs_and_prompt(self):
        """元 test_judge_verify.PrepCase.test_two_open_units_write_briefs_and_prompt・test_prep_places_unverified_notes_first"""
        doc = self.judged(_unit(_MEAN, ["x"], "defects", 1), _unit(_CLAMP, ["x"], "defects", 1),
                          _unit("stats.py fmt: 桁", ["x"], "defects", 1, label="info", disposition="defer"))
        got = ja.prep_on(self.jdir, doc, self.repo, True)
        self.assertIs(got["go"], True)
        prompt = pathlib.Path(got["prompt_file"])
        self.assertTrue(str(prompt).startswith(str(self.jdir / jv.BRIEF_DIR)))
        names = sorted(p.name for p in prompt.parent.glob("*.md"))
        self.assertEqual(names, ["prompt.md", "synergy.md", "unit-1.md", "unit-2.md"])
        one = (prompt.parent / "unit-1.md").read_text(encoding="utf-8")
        self.assertIn(_MEAN, one)
        self.assertNotIn(_CLAMP, one)
        self.assertEqual(pathlib.Path(jv.answer_in(one)), self.jdir / ja.VERIFY_ANSWERS_DIR / "unit-1.json")
        self.assertIn(jv.SUBAGENT_TYPE, prompt.read_text(encoding="utf-8"))
        self.assertEqual([(u["key"], u["state"]) for u in self.notes()["units"]],
                         [(_MEAN, jv.UNVERIFIED), (_CLAMP, jv.UNVERIFIED)])


class VerifyMergeCase(_VerifyBase):
    def setUp(self):
        super().setUp()
        doc = self.judged(_unit(_MEAN, ["x"], "defects", 1), _unit(_CLAMP, ["x"], "defects", 1))
        self.assertIs(ja.prep_on(self.jdir, doc, self.repo, True)["go"], True)

    def test_good_answers_are_merged_with_keys(self):
        """元 test_judge_verify.MergeCase.test_good_answers_and_synergy_are_merged_with_keys"""
        self.answer(1, _MEAN)
        self.answer(2, _CLAMP, verdict="not_root", real_root=f"単位 1（{_MEAN}）と同じ根")
        self.synergy({"why": "2 つの単位は同じ関数の群の取り違え", "duplicates": [{"units": [1, 2], "why": "同じ根の別の現れ"}],
                      "relations": [], "order": [{"first": 1, "then": 2, "why": "mean を先に直す"}]})
        self.assertEqual(ja.merge_on(self.jdir, self.repo), {"ok": True, "reason": ""})
        doc = self.notes()
        self.assertEqual([(u["key"], u["state"], u["verdict"]) for u in doc["units"]],
                         [(_MEAN, jv.CHECKED, "root"), (_CLAMP, jv.CHECKED, "not_root")])
        self.assertEqual(doc["synergy"]["duplicates"], [{"units": [_MEAN, _CLAMP], "why": "同じ根の別の現れ"}])
        self.assertIsNone(ja.read_stop(self.jdir))

    def test_verification_never_deletes_units(self):
        """元 test_judge_verify.MergeCase.test_missing_or_bad_answers_are_named_unverified（単位は消さない）"""
        self.answer(2, _CLAMP, verdict="not_root")
        self.synergy({"why": "短い"})
        ja.merge_on(self.jdir, self.repo)
        doc = self.notes()
        self.assertEqual([u["key"] for u in doc["units"]], [_MEAN, _CLAMP], "単位は消さない")
        self.assertTrue(any("答えのファイルが無い" in e for e in doc["units"][0]["errors"]))
        self.assertTrue(any("real_root" in e for e in doc["units"][1]["errors"]))
        self.assertEqual(doc["synergy"]["state"], jv.UNVERIFIED)

    def test_bad_missing_and_out_of_range_answers_are_unverified(self):
        """元 test_judge_verify.py:180 の MergeCase.test_good_answers_and_synergy_are_merged_with_keys・
        :199 の test_missing_or_bad_answers_are_named_unverified・:213 の test_wrong_unit_number_and_out_of_range_synergy。
        無い・型の外・番号の外の答えは「確かめられなかった」と誤りの行で控え、単位は消さない"""
        self.answer(1, _MEAN, unit=2)
        self.answer(2, _CLAMP, verdict="maybe")
        self.synergy({"why": "単位 3 と単位 1 が重なる", "duplicates": [{"units": [1, 3], "why": "同じ根の別の現れ"}],
                      "relations": [], "order": []})
        self.assertEqual(ja.merge_on(self.jdir, self.repo), {"ok": True, "reason": ""})
        doc = self.notes()
        self.assertEqual([(u["key"], u["state"]) for u in doc["units"]], [(_MEAN, jv.UNVERIFIED), (_CLAMP, jv.UNVERIFIED)])
        self.assertIn("$.unit: 1 でない（2）", doc["units"][0]["errors"])
        self.assertTrue(any("verdict" in e for e in doc["units"][1]["errors"]), doc["units"][1]["errors"])
        self.assertEqual(doc["synergy"]["state"], jv.UNVERIFIED)
        self.assertIn("単位 3 は無い（単位は 1〜2）", doc["synergy"]["errors"])
        (self.jdir / ja.VERIFY_ANSWERS_DIR / jv.ANSWER_FILE.format(n=1)).unlink()
        (self.jdir / ja.VERIFY_ANSWERS_DIR / jv.SYNERGY_FILE).unlink()
        ja.merge_on(self.jdir, self.repo)
        doc = self.notes()
        self.assertEqual([u["key"] for u in doc["units"]], [_MEAN, _CLAMP], "単位は消さない")
        self.assertEqual(doc["units"][0]["state"], jv.UNVERIFIED)
        self.assertTrue(any("答えのファイルが無い" in e for e in doc["units"][0]["errors"]))
        self.assertEqual(doc["synergy"]["state"], jv.UNVERIFIED)
        self.assertTrue(doc["synergy"]["errors"])

    def test_tree_moved_writes_verify_stop(self):
        """元 test_judge_verify.MergeCase.test_tree_moved_stops_board"""
        self.answer(1, _MEAN)
        (self.repo / "extra.txt").write_text("下請けが書いた\n", encoding="utf-8")
        got = ja.merge_on(self.jdir, self.repo)
        self.assertIs(got["ok"], False)
        stop = ja.read_stop(self.jdir)
        self.assertEqual(stop["stop_reason"], ja.VERIFY_STOP)
        self.assertIn("extra.txt", stop["reason"])
        self.assertEqual(len(self.notes()["units"]), 2, "止めても申し送りは書く")

    def test_merge_without_prep_record_writes_not_run(self):
        """元 test_judge_verify.MergeCase.test_merge_without_prep_record_is_empty"""
        (self.jdir / jv.PLAN_FILE).unlink()
        (self.jdir / jv.VERIFY_FILE).unlink()
        got = ja.merge_on(self.jdir, self.repo)
        self.assertIs(got["ok"], True)
        self.assertEqual(self.notes()["units"], [])
        p = ja.verify_not_run(self.jdir, "判定の輪が諦めた")
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")),
                         {"units": [], "synergy": {"state": jv.UNVERIFIED, "errors": ["判定の輪が諦めた"]}})


class StructureUnitsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "b.py").write_text("y = 2\n", encoding="utf-8")

    @staticmethod
    def unit(paths=None, key="src/a.py mean: 分母が違う", label="block"):
        u = {"key": key, "label": label, "disposition": "do-now", "reason": "r"}
        if paths is not None:
            u["class_query"] = {"how": {"patterns": ["x"], "paths": paths}}
        return u

    def test_keeps_files_under_root_in_order_without_duplicates(self):
        """元 test_structure_units.UnitFilePathsCase.test_keeps_files_under_root_in_order_without_duplicates"""
        self.assertEqual(ja._unit_file_paths(self.unit(["b.py", "./src/a.py", "src/a.py"]), self.repo), (["b.py", "src/a.py"], []))

    def test_drops_paths_that_are_not_files_under_root(self):
        """元 test_structure_units.UnitFilePathsCase.test_drops_paths_measure_cannot_read"""
        bad = ["src", "*.py", ":(glob)src/*.py", str(self.repo / "b.py"), "../b.py", "src/../b.py", "gone.py"]
        self.assertEqual(ja._unit_file_paths(self.unit(["b.py", *bad]), self.repo), (["b.py"], bad))

    def test_falls_back_to_key_head_only_without_how_paths(self):
        """元 test_structure_units.UnitFilePathsCase.test_falls_back_to_key_head_only_without_how_paths"""
        self.assertEqual(ja._unit_file_paths(self.unit(), self.repo), (["src/a.py"], []))
        self.assertEqual(ja._unit_file_paths(self.unit(key="上限を呼び手ごとに持つ"), self.repo), ([], ["上限を呼び手ごとに持つ"]))

    def test_all_open_units_are_listed_even_without_paths(self):
        """元 line_edge.structure_units（計画の決め: paths が空の単位も落とさない。開いていない単位は入れない）"""
        doc = {"units": [self.unit(["b.py"], key="b.py 一"), self.unit(key="上限を呼び手ごとに持つ"),
                         self.unit(["b.py"], key="b.py 情報", label="info")]}
        self.assertEqual(ja.structure_units(doc, self.repo),
                         [{"id": "b.py 一", "paths": ["b.py"], "summary": "r"},
                          {"id": "上限を呼び手ごとに持つ", "paths": [], "summary": "r"}])
        self.assertEqual(ja.structure_units(None, self.repo), [])


# ================================================================ 材料・前提・目的・素材
# ---------------------------------------------------------------- 試験の助け


class _RepoCase(unittest.TestCase):
    """対象のリポジトリ（commit 1 つ）と run の置き場 judge/ を一時の場所に組む"""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = pathlib.Path(td.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        gitkit.git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("# 対象\n\n件数は 3 件\n", encoding="utf-8")
        (self.repo / "app.txt").write_text("一行目\n二行目\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        self.head = gitkit.git(self.repo, "rev-parse", "HEAD").strip()
        self.jdir = self.tmp / "artifacts" / ja.JUDGE_DIR
        self.jdir.mkdir(parents=True)

    def snap_tree(self, name=ja.TREE_FILE):
        ja.snap_tree(self.jdir, name, self.repo)

    def start(self, **over):
        doc = {"base_rev": self.head, "input": {"base": {"rev": self.head}, "diff": {"empty": False}, "requests": 1}}
        doc.update(over)
        return ja.start_view(doc)


# ================================================================ 入口
class IntakeCase(_RepoCase):
    ROWS = [{"where": "app.txt", "text": "二行目が違う"}]

    def intake(self, start):
        return ja.intake(start, "", self.jdir, self.tmp / "artifacts" / ja.REJUDGE_DIR, self.repo, "")

    def test_request_file_shapes(self):
        """元 test_blk_judge.py:300・313・322・328（intake.py の main）: 無い・JSON でない・形の違う依頼のファイルは AI を 1 つも
        起こさずに依頼の語で止める。容器の形と、根からの相対・根の外の絶対パスは受けて request.json に行を置く"""
        outside = self.tmp / "outside.json"
        outside.write_text(json.dumps(self.ROWS), encoding="utf-8")
        (self.repo / "req.json").write_text(json.dumps({"findings": self.ROWS, "pr": [7]}), encoding="utf-8")
        (self.repo / "broken.json").write_text("{", encoding="utf-8")
        (self.repo / "odd.json").write_text(json.dumps({"rows": self.ROWS}), encoding="utf-8")
        for name, go in (("req.json", True), (str(outside), True), ("nothing.json", False), ("broken.json", False),
                         ("odd.json", False)):
            with self.subTest(name):
                shutil.rmtree(self.jdir)
                got = self.intake(self.start(request_file=name))
                self.assertIs(got["go"], go, got)
                self.assertEqual(ja.read_json(self.jdir / ja.INTAKE_FILE), got)
                if go:
                    self.assertEqual(ja.read_json(self.jdir / ja.REQUEST_FILE), self.ROWS)
                    self.assertFalse((self.jdir / ja.STOP_FILE).exists())
                else:
                    self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], ja.REQUEST_STOP)
                    self.assertFalse((self.jdir / ja.REQUEST_FILE).exists())

    def test_features_cut_and_spec_set_the_stage_flags(self):
        """元 entry.py の FEATURES・line_edge.py:1026 の _world_due・judgeverify.py:306 の prep: 始めの記録の features_cut の world が
        世界の解の段を、judge_verify が判定の裏取りを切り、input.spec が仕様の段を入れる（features_cut の無い記録は裏取りだけ切る）"""
        cases = (({}, (False, True, False)),
                 ({"features_cut": []}, (False, True, True)),
                 ({"features_cut": ["world"]}, (False, False, True)),
                 ({"features_cut": ["world", "judge_verify"]}, (False, False, False)),
                 ({"input": {"base": {"rev": self.head}, "spec": True}}, (True, True, False)))
        (self.repo / "req.json").write_text(json.dumps(self.ROWS), encoding="utf-8")
        for over, flags in cases:
            with self.subTest(over):
                got = self.intake(self.start(request_file="req.json", **over))
                self.assertTrue(got["go"], got)
                self.assertEqual((got["spec"], got["world"], got["verify"]), flags)


# ================================================================ 前提の実測
class PremisesCase(_RepoCase):
    GOOD = {"constraints": [{"text": "README.md の件数は 3 件", "measured_how": "grep", "kind": "実測",
                             "measured_output": "$ grep -c 件 README.md\n1"}]}

    def test_measured_without_output_rejected(self):
        """元 test_blk_premises.PremisesAcceptCase.test_measured_without_output_rejected_by_copied_rule と test_blank_output_rejected"""
        self.snap_tree()
        for bad in ({"text": "a", "measured_how": "b", "kind": "実測"},
                    {"text": "a", "measured_how": "b", "kind": "実測", "measured_output": "  "}):
            with self.subTest(bad):
                got = ja.check_premises({"constraints": [bad]}, self.jdir, self.repo, [])
                self.assertFalse(got["ok"])
                self.assertIn("measured_output", got["reason"])
        self.assertFalse((self.jdir / "premises.json").exists(), "拒んだ返答は書かない")

    def test_reply_outside_the_copied_type_rejected(self):
        """元 premises.check_premises の型（写しの graph の p0.premises の schema）: 欠けた欄・知らない語・知らない欄を拒む"""
        self.snap_tree()
        for bad in ({"text": "a", "kind": "仮説"}, {"text": "a", "measured_how": "b", "kind": "推測"},
                    {"text": "a", "measured_how": "b", "kind": "仮説", "note": "足した欄"}):
            with self.subTest(bad):
                got = ja.check_premises({"constraints": [bad]}, self.jdir, self.repo, [])
                self.assertFalse(got["ok"])
                self.assertIn("型が合わない", got["reason"])

    def test_hypothesis_needs_no_output_and_good_reply_is_written(self):
        """元 test_blk_premises の test_hypothesis_needs_no_output_and_empty_is_ok・test_accepts_good_reply"""
        self.snap_tree()
        got = ja.check_premises({"constraints": [{"text": "a", "measured_how": "b", "kind": "仮説"}]}, self.jdir, self.repo, [])
        self.assertTrue(got["ok"], got)
        got = ja.check_premises(self.GOOD, self.jdir, self.repo, [])
        self.assertTrue(got["ok"], got)
        self.assertEqual(ja.read_json(self.jdir / "premises.json"), self.GOOD)

    def test_request_claim_must_be_measured_again(self):
        """元 test_blk_premises の test_request_claim_missing_rejected・test_request_claim_hypothesis_passes（check_claims）"""
        self.snap_tree()
        items = [{"where": "README.md:3", "text": "件数", "measured": "3 件"}]
        got = ja.check_premises(self.GOOD, self.jdir, self.repo, items)
        self.assertFalse(got["ok"])
        self.assertIn("README.md:3", got["reason"])
        hyp = {"constraints": [{"text": "README.md:3 は本番の値で測れない", "measured_how": "読んだ", "kind": "仮説"}]}
        self.assertTrue(ja.check_premises(hyp, self.jdir, self.repo, items)["ok"])

    def test_premises_role_changed_the_tree_rejected(self):
        """元 test_blk_premises の test_rejects_tree_changed_after_intake・test_rejects_commit_after_intake"""
        self.snap_tree()
        (self.repo / "out.txt").write_text("測った出力\n", encoding="utf-8")
        got = ja.check_premises(self.GOOD, self.jdir, self.repo, [])
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])
        (self.repo / "out.txt").unlink()
        self.assertTrue(ja.check_premises(self.GOOD, self.jdir, self.repo, [])["ok"])
        (self.repo / "app.txt").write_text("書き換えた\n", encoding="utf-8")
        gitkit.git(self.repo, "commit", "-qam", "x")
        self.assertFalse(ja.check_premises(self.GOOD, self.jdir, self.repo, [])["ok"], "commit しても HEAD で見える")

    def test_bytecode_made_by_measuring_is_not_counted(self):
        """元 test_blk_premises の test_bytecode_not_counted_without_gitignore（測るために試験を走らせて出来る物）"""
        self.snap_tree()
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
        self.assertTrue(ja.check_premises(self.GOOD, self.jdir, self.repo, [])["ok"])


# ================================================================ 目的
class PurposeCase(_RepoCase):
    GOOD = {"purpose_text": "件数を正しく数える", "source": "②計画・タスク記述", "known_weaknesses": [],
            "source_files": ["README.md"], "means": ["数え直す関数を足す"]}

    def test_good_reply_writes_purpose_and_means(self):
        """元 test_blk_purpose の test_accept_good_and_bad_reply・test_purpose_means_split_to_mark"""
        self.snap_tree(ja.PURPOSE_TREE_FILE)
        got = ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)
        self.assertTrue(got["ok"], got)
        doc = ja.read_json(self.jdir / "purpose.json")
        self.assertNotIn("means", doc, "purpose.json は写しの型のまま（足し欄を外す）")
        self.assertEqual(doc["source_files"], ["README.md"])
        self.assertEqual(ja.read_json(self.jdir / "purpose-means.json"), {"means": ["数え直す関数を足す"]})

    def test_purpose_role_changed_the_tree_rejected(self):
        """元 test_blk_purpose の test_accept_rejects_tree_change_after_intake"""
        self.snap_tree(ja.PURPOSE_TREE_FILE)
        (self.repo / "note.txt").write_text("書いた\n", encoding="utf-8")
        got = ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])
        self.assertFalse((self.jdir / "purpose.json").exists())

    def test_source_files_outside_or_missing_rejected(self):
        """元 test_blk_purpose の test_accept_rejects_source_files_outside_tree・test_accept_rejects_missing_source_file_sample"""
        self.snap_tree(ja.PURPOSE_TREE_FILE)
        for bad in (["/etc/hosts"], ["./README.md"], ["nothing.md"]):
            with self.subTest(bad):
                got = ja.check_purpose({**self.GOOD, "source_files": bad}, self.jdir, self.repo)
                self.assertFalse(got["ok"], got)
                self.assertIn("source_files", got["reason"])

    def test_source_files_nested_ignored_and_subdir(self):
        """元 test_blk_purpose.py:460・472・505・512（_source_files_errors）: 入れ子の綴り・git が無視するファイル・git の形でない名前を
        拒み、未追跡の新規は通す。サブディレクトリで回しても根からの相対を通し、そこからの相対は拒む"""
        (self.repo / "sub").mkdir()
        for name in ("a.md", "new.md", "skip.log"):
            (self.repo / "sub" / name).write_text("x\n", encoding="utf-8")
        (self.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "sub/a.md", ".gitignore")
        gitkit.git(self.repo, "commit", "-q", "-m", "sub")
        for repo, good, bads in (
                (self.repo, ["sub/a.md", "sub/new.md"],
                 ("sub//a.md", "sub/./a.md", "sub/skip.log", "sub/a.md/", "Sub/a.md", "./sub/a.md")),
                (self.repo / "sub", ["sub/a.md"], ("a.md",))):
            for bad in bads:
                with self.subTest(repo=repo.name, bad=bad):
                    shutil.rmtree(self.jdir)
                    ja.snap_tree(self.jdir, ja.PURPOSE_TREE_FILE, repo)
                    got = ja.check_purpose({**self.GOOD, "source_files": [*good, bad]}, self.jdir, repo)
                    self.assertFalse(got["ok"], got)
                    self.assertIn(f"source_files に作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る: {[bad]!r}",
                                  got["reason"])
            with self.subTest(repo=repo.name, good=good):
                shutil.rmtree(self.jdir)
                ja.snap_tree(self.jdir, ja.PURPOSE_TREE_FILE, repo)
                got = ja.check_purpose({**self.GOOD, "source_files": good}, self.jdir, repo)
                self.assertTrue(got["ok"], got)
                self.assertEqual(ja.read_json(self.jdir / "purpose.json")["source_files"], good)

    def test_frozen_purpose_is_not_overwritten(self):
        """元 test_blk_purpose の test_accept_refuses_to_overwrite_frozen_purpose（p0.purpose の once）"""
        self.snap_tree(ja.PURPOSE_TREE_FILE)
        self.assertTrue(ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)["ok"])
        got = ja.check_purpose({**self.GOOD, "purpose_text": "別の目的"}, self.jdir, self.repo)
        self.assertFalse(got["ok"])
        self.assertEqual(ja.read_json(self.jdir / "purpose.json")["purpose_text"], "件数を正しく数える")

    def test_prep_snapshots_the_tree_the_accept_compares(self):
        """支度が役を起こす前の作業ツリーの姿を purpose-tree.json に置き、受け付けはそれと比べる"""
        self.assertTrue(ja.purpose_prep(self.jdir, self.repo, self.start())["go"])
        self.assertEqual(ja.read_json(self.jdir / ja.PURPOSE_TREE_FILE), core_accept.tree_state(self.repo))
        (self.repo / "note.txt").write_text("書いた\n", encoding="utf-8")
        got = ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])

    def test_purpose_material_has_no_prior_failures(self):
        """元 test_blk_purpose.test_purpose_never_sees_prior_failures（目的の役に前の run の判断を見せない。carry.without_prior）"""
        req = self.repo / "request.json"
        req.write_text(json.dumps({"findings": [{"where": "app.txt:1", "text": "数え違い"}],
                                     "prior_failures": [{"where": "受け付け", "text": "前の run で拒まれた行の印XYZ"}]},
                                    ensure_ascii=False), encoding="utf-8")
        ja.write_json(self.jdir / "premises.json", {"constraints": [{"text": "制約の印ABC", "measured_how": "m", "kind": "仮説"}]})
        start = self.start(request_file="request.json", input={"pr": {"number": 7, "title": "題", "body": "本文"}})
        got = ja.purpose_prep(self.jdir, self.repo, start)
        self.assertTrue(got["go"], got)
        request = ja.read_json(self.jdir / "purpose-request.json")
        self.assertNotIn("prior_failures", request)
        self.assertEqual(request["findings"][0]["where"], "app.txt:1")
        text = pathlib.Path(got["brief_file"]).read_text(encoding="utf-8")
        self.assertNotIn("印XYZ", text)
        self.assertNotIn(carry.PRIOR_HEAD, text)
        self.assertNotIn(carry.REDESIGN_HEAD, text)
        self.assertIn("制約の印ABC", text)
        self.assertIn("app.txt:1", text)
        self.assertIn("本文", text, "PR の説明は目的の出典①")


# ================================================================ 素材の要否
class DueCase(unittest.TestCase):
    """元 test_blk_material の test_normal_run_routes_every_due_lens・test_entry_round_prior_decisions_only・
    test_purpose_review_runs_its_path（盤面の settle の ready を、値を渡す見方 due_view で写した）"""
    P1 = ("local-review", "consistency-bypass", "hygiene", "external-standards", "provenance", "procedure-trace",
          "gate-efficacy", "test-double-fidelity", "main-path-observation")

    def view(self, empty, requests, source="②計画・タスク記述", files=("README.md", "src/a.txt")):
        start = ja.start_view({"input": {"diff": {"empty": empty}, "requests": requests}, "gates": ""})
        purpose = {"purpose_text": "p", "source": source, "known_weaknesses": [], "source_files": []}
        return ja.due_view(start, purpose, list(files))

    def test_view_values(self):
        v = self.view(True, 2)
        self.assertEqual(v("round"), 1)
        self.assertIsNone(v("prev.p3.fix.mechanism_changed"))
        self.assertFalse(v("loop.escalated"))
        self.assertIsNone(v("loop.request_fixed_at"))
        self.assertTrue(v("out.p0.base.touches_gates"))
        self.assertIsNone(v("loop.last_material.main_path_observation.status", None))
        self.assertEqual(v("out.p0.purpose.source"), "②計画・タスク記述")
        self.assertEqual(v("loop.changed_files"), ["README.md", "src/a.txt"])
        self.assertTrue(ja.request_entry(v)[0], "差分が空で依頼の在る run は入口の印が立つ")
        self.assertFalse(ja.request_entry(self.view(True, 0))[0])
        self.assertFalse(ja.request_entry(self.view(False, 2))[0])

    def test_empty_diff_run_with_requests_runs_only_prior_decisions(self):
        got = ja.due_roles(self.view(True, 1, files=()))
        for role in self.P1:
            self.assertFalse(got[role][0], role)
            self.assertTrue(got[role][1], "回さない訳を言う")
        self.assertTrue(got["prior-decisions"][0])
        self.assertFalse(got["purpose-review"][0])

    def test_purpose_review_only_for_writer_summary(self):
        self.assertTrue(ja.due_roles(self.view(True, 1, source="③writer の要約"))["purpose-review"][0])
        self.assertFalse(ja.due_roles(self.view(False, 1, source="①PR 説明"))["purpose-review"][0])

    def test_run_with_a_diff_runs_them(self):
        got = ja.due_roles(self.view(False, 1))
        for role in self.P1 + ("prior-decisions",):
            self.assertTrue(got[role][0], (role, got[role]))

    def test_procedure_trace_needs_procedure_files(self):
        got = ja.due_roles(self.view(False, 1, files=("src/a.txt",)))
        self.assertFalse(got["procedure-trace"][0])

    def test_gates_merge_turns_gate_efficacy_off(self):
        start = ja.start_view({"input": {"diff": {"empty": False}, "requests": 0}, "gates": "merge"})
        self.assertFalse(ja.due_roles(ja.due_view(start, {"source": "①PR 説明"}, ["a.yml"]))["gate-efficacy"][0])


# ================================================================ 素材の受け付けと素材の状態
class MaterialCase(_RepoCase):
    def view(self):
        start = self.start()
        ja.write_json(self.jdir / ja.START_FILE, start)
        return ja.material_route(self.jdir, self.repo)

    def test_route_writes_view_and_decisions(self):
        """元 test_blk_material の test_normal_run_routes_every_due_lens（差分の在る run）"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        got = self.view()
        self.assertEqual(set(got), {ja.route_key(r) for r in ja.MATERIAL_ROLES} | {"reason"})
        self.assertTrue(got["local_review"])
        self.assertTrue((self.jdir / "diff.patch").read_text(encoding="utf-8").strip())
        self.assertIn("app.txt", ja.read_json(self.jdir / ja.MATERIAL_VIEW_FILE)["changed_files"])

    def test_diff_sees_files_hidden_by_index_marks(self):
        """本物の index の assume-unchanged・skip-worktree の印を付けた変更済みのファイルも、変更ファイルと diff.patch の両方に入る"""
        gitkit.git(self.repo, "update-index", "--assume-unchanged", "README.md")
        gitkit.git(self.repo, "update-index", "--skip-worktree", "app.txt")
        (self.repo / "README.md").write_text("# 対象\n\n件数は 4 件\n", encoding="utf-8")
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        self.view()
        doc = ja.read_json(self.jdir / ja.MATERIAL_VIEW_FILE)
        self.assertEqual(doc["changed_files"], ["README.md", "app.txt"])
        patch = (self.jdir / "diff.patch").read_text(encoding="utf-8")
        self.assertIn("件数は 4 件", patch)
        self.assertIn("直した", patch)
        self.assertTrue(doc["stat"].startswith("2 files changed"), doc["stat"])
        self.assertEqual(gitkit.git(self.repo, "ls-files", "-v", "README.md", "app.txt").splitlines(),
                         ["h README.md", "S app.txt"])

    def test_sparse_checkout_out_of_cone_files_are_not_changes(self):
        """sparse checkout の範囲外（skip-worktree の印が付き disk に無い）のファイルは、変更ファイルにも diff.patch にも入らない"""
        for name in ("x/a.txt", "y/b.txt"):
            (self.repo / name).parent.mkdir()
            (self.repo / name).write_text("元\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "x", "y")
        gitkit.git(self.repo, "commit", "-q", "-m", "xy")
        self.head = gitkit.git(self.repo, "rev-parse", "HEAD").strip()
        gitkit.git(self.repo, "sparse-checkout", "set", "y")
        (self.repo / "y" / "b.txt").write_text("直した\n", encoding="utf-8")
        self.view()
        doc = ja.read_json(self.jdir / ja.MATERIAL_VIEW_FILE)
        self.assertEqual(doc["changed_files"], ["y/b.txt"])
        self.assertNotIn("x/a.txt", (self.jdir / "diff.patch").read_text(encoding="utf-8"))
        self.assertTrue(doc["stat"].startswith("1 files changed"), doc["stat"])

    def test_stop_turns_every_role_off(self):
        ja.write_stop(self.jdir, ja.MATERIAL_STOP, "止めた")
        got = self.view()
        self.assertFalse(any(v for k, v in got.items() if k != "reason"))

    def test_prep_renders_role_inputs(self):
        """元 test_blk_material の test_prompt_is_mainline_prompt_rendered_from_board・test_isolated_role_gets_pasted_prompt・
        test_local_review_prompt_carries_declared_lenses"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        self.view()
        review = self.tmp / "REVIEW.md"
        review.write_text("# 観点\n\n## コード衛生観点\n\n衛生の本文\n\n## 次\n", encoding="utf-8")
        got = ja.material_prep(self.jdir, "hygiene", self.repo, str(review), "")
        self.assertEqual(pathlib.Path(got["brief_file"]).read_text(encoding="utf-8"), got["brief"])
        self.assertIn("衛生の本文", got["brief"])
        self.assertIn("直した", got["brief"], "差分の本文を貼る")
        got = ja.material_prep(self.jdir, "local-review", self.repo, str(review), "")
        self.assertIn("/code-review", got["brief"])
        self.assertIn('"applies": true', got["brief"])
        self.assertEqual(got["review_md"], str(review))

    def test_accept_writes_material_file(self):
        self.view()
        reply = {"material": {"status": "clean", "checked": "README を見た"}, "observed": [{"path": "p", "value": "v"}]}
        got = ja.material_take(self.jdir, "main-path-observation", reply, self.repo)
        self.assertTrue(got["ok"], got)
        doc = ja.read_json(self.jdir / "material-main-path-observation.json")
        self.assertEqual(doc["role"], "main-path-observation")
        self.assertEqual(doc["materials"], {"main_path_observation": {"status": "clean", "checked": "README を見た"}})

    def test_accept_rules(self):
        """元 test_blk_material の test_rejected_reply_retries_then_gives_up と写しの rules の post_check
        （main_path_observed・external_rankings・gate_arms_all_red）"""
        self.view()
        cases = {
            "main-path-observation": {"material": {"status": "clean", "checked": "x"}, "observed": []},
            "external-standards": {"material": {"status": "clean", "checked": "x"}, "findings": [], "seen": "s", "unseen": "u",
                                   "web_refetched": True, "rankings": [{"problem": "問題の名", "source": "https://x",
                                                                        "ranked": ["上", "下"], "diff_at": "下"}]},
            "gate-efficacy": {"material": {"status": "clean", "checked": "x"},
                              "arms": [{"gate": "g", "arm": "a", "red_confirmed": False, "control_green": True,
                                        "hit_evidence": "印を出力で見た（十分に長い）"}]},
            "provenance": {"material": {"status": "carried_over", "from_round": 1, "reason": "前の周"}, "claims": []},
        }
        for role, reply in cases.items():
            with self.subTest(role):
                got = ja.material_take(self.jdir, role, reply, self.repo)
                self.assertFalse(got["ok"], got)
                self.assertFalse((self.jdir / f"material-{role}.json").exists())

    def test_gate_role_may_judge_a_gate_free_diff_not_applicable(self):
        """元 test_gate_na.PolicyCase（entry.role_judged_na_works。canary の run e91112dd）: 機械は touches_gates を真へ倒すが、
        差分にゲートの印が無ければゲートの検算の役の『条件外』を受ける。印が在れば拒む（測らせる）"""
        na = {"material": {"status": "not_applicable", "reason": "差分は文書の行だけで、検証ゲートを足しも変えもしない"}, "arms": []}
        for extra, ok in ((None, True), ("test_app.txt", False)):
            with self.subTest(extra=extra):
                self.setUp()
                (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
                if extra:
                    (self.repo / extra).write_text("x\n", encoding="utf-8")
                self.view()
                brief = ja.material_prep(self.jdir, "gate-efficacy", self.repo, "")["brief"]
                self.assertEqual("役の判定を受ける" in brief, ok)
                got = ja.material_take(self.jdir, "gate-efficacy", na, self.repo)
                self.assertEqual(got["ok"], ok, got)

    def test_material_role_changed_the_tree_rejected(self):
        """元 test_blk_material.test_tree_change_rejects_and_names_peers"""
        self.view()
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        got = ja.material_take(self.jdir, "provenance", {"material": {"status": "clean", "checked": "x"}, "claims": []}, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])

    def changed(self, *names):
        """app.txt と names を変えた差分で素材の道を分ける"""
        for name in ("app.txt", *names):
            with (self.repo / name).open("a", encoding="utf-8") as fh:
                fh.write("直した\n")
        return self.view()

    def take_round(self, role, reply):
        return ja.accept_round(self.jdir, role, json.dumps(reply, ensure_ascii=False),
                               lambda r: ja.material_take(self.jdir, role, r, self.repo))

    def test_route_keeps_the_first_tree_record(self):
        """元 test_blk_material.py:471 の test_route_keeps_first_snapshot: 素材の役を起こす前の作業ツリーの姿は 1 度だけ置く
        （run の再開で道分けが走り直しても、役が変えた後の姿で上書きしない）"""
        self.changed()
        first = ja.read_json(self.jdir / ja.MATERIAL_TREE_FILE)
        (self.repo / "tmp.out").write_text("役が残した\n", encoding="utf-8")
        self.view()
        self.assertEqual(ja.read_json(self.jdir / ja.MATERIAL_TREE_FILE), first)
        got = ja.material_take(self.jdir, "provenance", {"material": {"status": "clean", "checked": "x"}, "claims": []}, self.repo)
        self.assertIn("tmp.out", got["reason"])

    def test_na_note_for_each_kind_of_node(self):
        """元 test_blk_material.py:885・892・898・903（NaNoteCase。_na_note）: 材料の末尾に、条件の偽・条件の真・役の判定を受ける
        ゲートの役・条件の無い節・na_self_ok を宣言した節ごとに、not_applicable を書けるかの文を足す"""
        refused = "`not_applicable` は受け付けが拒む"
        allowed = "`not_applicable`（理由を reason に）を書いてよい"
        cases = (("procedure-trace", (), ["`touches_procedures` はこの周に偽", allowed], refused),
                 ("procedure-trace", ("run.sh",), ["`touches_procedures` はこの周に真", refused], allowed),
                 ("gate-efficacy", (), ["`gates_touched` はこの周に真", "役の判定を受ける", allowed], refused),
                 ("gate-efficacy", ("test_app.txt",), ["`gates_touched` はこの周に真", refused], allowed),
                 ("consistency-bypass", (), ["条件（applies_cond）を持たず", "na_self_ok が無い", refused], allowed))
        for role, files, said, unsaid in cases:
            with self.subTest(role=role, files=files):
                self.setUp()
                self.changed(*files)
                brief = ja.material_prep(self.jdir, role, self.repo, "")["brief"]
                self.assertIn(str(ja.NA_HEADING), brief)
                for text in said:
                    self.assertIn(text, brief)
                self.assertNotIn(unsaid, brief)
        nid = ja.MATERIAL_ROLES["consistency-bypass"]
        nodes = {**ja.MATERIAL_NODES, nid: {**ja.MATERIAL_NODES[nid], "na_self_ok": "差分にコードが無い"}}
        with mock.patch.object(ja, "MATERIAL_NODES", nodes):
            brief = ja.material_prep(self.jdir, "consistency-bypass", self.repo, "")["brief"]
        self.assertIn("na_self_ok: 差分にコードが無い", brief)
        self.assertIn(allowed, brief)

    def test_missing_purpose_is_said_not_invented(self):
        """元 test_blk_material.py:527: 目的の文が無い run の材料は PURPOSE_MISSING と書き、目的を作らない"""
        self.changed()
        self.assertFalse((self.jdir / "purpose.json").exists())
        brief = ja.material_prep(self.jdir, "external-standards", self.repo, "")["brief"]
        self.assertIn(f"## 材料: out.p0.purpose.purpose_text\n\n{ja.PURPOSE_MISSING}", brief)
        self.assertFalse((self.jdir / "purpose.json").exists())

    def test_purpose_review_findings_must_cite_the_version(self):
        """元 rules:3274 の purpose_findings_cited（:3471 _cite_errors・:3612 _count_in_version）: 目的の監査の所見の引用を、
        素材の道が固めた版で数え直す。版に無い引用・数の合わない申告・根拠の無い『狭めている』を拒む"""
        self.changed()
        def reply(*findings, verdict="狭めている"):
            return {"verdict": verdict, "findings": [{"text": "目的が件数の数えに狭まっている", "cite": c, "hits": h}
                                                     for c, h in findings]}
        cases = ((reply(("件数は 3 件", 1)), ""),
                 (reply(("どこにも無い字列", 1)), "'どこにも無い字列' が現物に 1 件も無い"),
                 (reply(("件数は 3 件", 2)), "'件数は 3 件' の件数の申告 2 が数え直し 1 と違う"),
                 (reply(), "『狭めている』のに findings が空"))
        for got_reply, why in cases:
            with self.subTest(why=why):
                got = ja.material_take(self.jdir, "purpose-review", got_reply, self.repo)
                self.assertEqual(got["ok"], not why, got)
                if why:
                    self.assertIn(why, got["reason"])
        self.assertEqual(ja.read_json(self.jdir / "material-purpose-review.json")["reply"], cases[0][0])

    def test_local_review_rows_cover_the_declared_lenses(self):
        """元 rules:3214 の local_review_covers_lenses: 宣言のレンズ 1 本に findings の行 1 本。行の欠け・宣言の外の名・同じレンズの
        2 行・items も failed も無い行をそれぞれ拒む"""
        self.changed()
        rows = self._lens_rows(lambda s: True)
        hunter = "pr-review-toolkit:silent-failure-hunter"
        def without(skill):
            return [r for r in rows if r["skill"] != skill]
        cases = ((rows, ""),
                 (without("/security-review"), "宣言した '/security-review' の行が findings に無い"),
                 ([*rows, {**rows[1], "skill": "my:lens"}], "findings[7] の skill 'my:lens' は宣言に無い"),
                 ([*rows, rows[1]], "findings に同じ skill の行が 2 本: pr-review-toolkit:code-reviewer"),
                 ([*without(hunter), {"skill": hunter, "items": [], "invoked": True, "failed": ""}],
                  f"'{hunter}' の行が items も failed も持たない"))
        for found, why in cases:
            with self.subTest(why=why):
                reply = {"material": {"status": "clean", "checked": "差分を見た"}, "simplify_carried": False, "findings": found}
                got = ja.material_take(self.jdir, "local-review", reply, self.repo)
                self.assertEqual(got["ok"], not why, got)
                if why:
                    self.assertIn(why, got["reason"])

    def test_location_beyond_the_file_is_sent_back_then_marked(self):
        """元 test_blk_material.py:610・627・640・650（_location_problems・_location_gap）: 所見の場所の行がファイルに無ければ
        拒んで出し直させ、上限の 1 つ手前からは where に LOCATION_MARK を付けて受ける。作業ツリーの外とファイルの無い場所は照らさない"""
        self.changed()
        outside = self.tmp / "outside.txt"
        outside.write_text("1 行\n", encoding="utf-8")
        def hygiene(*wheres):
            return {"findings": [{"where": w, "text": "所見の見本"} for w in wheres], "seen": "差分の全部"}
        self.assertTrue(self.take_round("hygiene", hygiene("app.txt:1", f"{outside}:50", "infra/main.tf:184"))["ok"])
        (self.jdir / "material-hygiene.json").unlink()
        bad = hygiene("app.txt:1", "app.txt:99")
        for n in range(1, ja.GIVE_UP_AFTER):
            with self.subTest(round=n):
                got = self.take_round("hygiene", bad)
                self.assertEqual((got["ok"], got["done"]), (False, False), got)
                self.assertIn(ja.LOCATION_HEAD, got["reason"])
                self.assertIn("app.txt:99", got["reason"])
        got = self.take_round("hygiene", bad)
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        wheres = [f["where"] for f in ja.read_json(self.jdir / "material-hygiene.json")["reply"]["findings"]]
        self.assertEqual(wheres, ["app.txt:1", "app.txt:99" + ja.LOCATION_MARK])

    def test_prior_decisions_reply_is_taken_or_refused(self):
        """素材の役の受け付け（先例の突合）: 見た返答は素材の欄に写して受け、名乗れない not_applicable は拒む"""
        self.changed()
        good = {"material": {"status": "clean", "checked": "PR と issue の議論を見た"}, "checked": "PR #1", "searched": "題で探した",
                "settled": []}
        self.assertFalse(self.take_round("prior-decisions", {**good, "material": {"status": "not_applicable", "reason": "無い"}})["ok"])
        self.assertTrue(self.take_round("prior-decisions", good)["ok"])
        self.assertEqual(ja.read_json(self.jdir / "material-prior-decisions.json")["materials"],
                         {"prior_decisions": good["material"]})

    def test_consistency_bypass_reply_is_taken_or_refused(self):
        """素材の役の受け付け（整合と標準機構の迂回）: 2 つの素材を両方書いた返答だけ受ける"""
        self.changed()
        good = {"consistency": {"status": "clean", "checked": "呼び手を見た"}, "bypass": {"status": "clean", "checked": "標準の口を見た"},
                "findings": [], "bypass_findings": []}
        got = self.take_round("consistency-bypass", {k: v for k, v in good.items() if k != "bypass"})
        self.assertFalse(got["ok"])
        self.assertIn("素材 'bypass' が返答に無い", got["reason"])
        self.assertTrue(self.take_round("consistency-bypass", good)["ok"])
        self.assertEqual(ja.read_json(self.jdir / "material-consistency-bypass.json")["materials"],
                         {"consistency": good["consistency"], "bypass": good["bypass"]})

    def test_hygiene_reply_is_taken_or_refused(self):
        """素材の役の受け付け（コード衛生）: findings と seen を素材 1 つに写す。何を見たかの無い clean は拒む"""
        self.changed()
        got = self.take_round("hygiene", {"findings": [], "seen": ""})
        self.assertFalse(got["ok"])
        self.assertIn("素材 'hygiene'（clean）に 'checked' が要る", got["reason"])
        self.assertTrue(self.take_round("hygiene", {"findings": [{"where": "app.txt:2", "text": "名が短い"}], "seen": "差分"})["ok"])
        self.assertEqual(ja.read_json(self.jdir / "material-hygiene.json")["materials"],
                         {"hygiene": {"status": "found", "checked": "差分", "count": 1, "detail": "app.txt:2: 名が短い"}})

    def test_procedure_trace_reply_is_taken_or_refused(self):
        """素材の役の受け付け（手順の追跡）: 条件 touches_procedures が偽なら not_applicable を受け、真なら拒む"""
        na = {"material": {"status": "not_applicable", "reason": "手順書の変更が無い"}, "findings": []}
        for files, ok in (((), True), (("run.sh",), False)):
            with self.subTest(files=files):
                self.setUp()
                self.changed(*files)
                got = self.take_round("procedure-trace", na)
                self.assertEqual(got["ok"], ok, got)
                self.assertEqual((self.jdir / "material-procedure-trace.json").exists(), ok)

    def test_test_double_fidelity_reply_is_taken_or_refused(self):
        """素材の役の受け付け（代役の忠実性）: 見た返答は受け、走った節の流用（carried_over）は拒む"""
        self.changed()
        got = self.take_round("test-double-fidelity",
                              {"material": {"status": "carried_over", "from_round": 1, "reason": "前の周と同じ"}})
        self.assertFalse(got["ok"])
        self.assertIn("素材 'test_double_fidelity'（ノード p1.test_double_fidelity）は今の周に走ったのに carried_over", got["reason"])
        good = {"material": {"status": "clean", "checked": "代役と本物の口を比べた"}}
        self.assertTrue(self.take_round("test-double-fidelity", good)["ok"])
        self.assertEqual(ja.read_json(self.jdir / "material-test-double-fidelity.json")["materials"],
                         {"test_double_fidelity": good["material"]})

    def test_tree_change_names_the_peer_roles(self):
        """元 test_blk_material.test_tree_change_rejects_and_names_peers（_peers）: 拒みの文に、material-route.json で同じ時に回す
        ほかの役を名指す。route が読めない時は読めないと言う"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        self.view()
        route = ja.read_json(self.jdir / ja.MATERIAL_ROUTE_FILE)
        peers = [r for r, d in route["roles"].items() if d["run"] and r != "provenance"]
        self.assertIn("hygiene", peers)
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        reply = {"material": {"status": "clean", "checked": "x"}, "claims": []}
        got = ja.material_take(self.jdir, "provenance", reply, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("・".join(peers), got["reason"])
        self.assertNotIn("provenance・", got["reason"])
        (self.jdir / ja.MATERIAL_ROUTE_FILE).write_text("{", encoding="utf-8")
        got = ja.material_take(self.jdir, "provenance", reply, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn(f"{ja.MATERIAL_ROUTE_FILE} が読めない", got["reason"])

    def test_gate_prep_shows_the_declared_mutation_stage(self):
        """元 review-loop.py:734 の mutation_decl: 対象の宣言の mutation の段を材料に貼る。段が無ければ探させる文、
        壊れていれば読めないと名指す"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        (self.repo / "arms.txt").write_text("arm-1\n", encoding="utf-8")
        decl = {"suite": [{"name": "t", "argv": ["true"]}], "mutation": {"argv": ["mutate", "--fast"], "arms": "arms.txt"}}
        self.view()
        undeclared = ja.MUTATION_UNDECLARED.format(decl=ja.DECL_NAME)
        cases = (
            (json.dumps(decl), ['["mutate", "--fast"]', "arms.txt"], "探せ"),
            (json.dumps({"suite": decl["suite"]}), [undeclared], "読めない"),
            (json.dumps({**decl, "mutation": {"argv": []}}), ["探せ", "mutation の段を読めない"], "mutate"),
            ("{", [undeclared, "読めない"], "mutate"),
            (json.dumps({**decl, "suite": []}), [undeclared, "読めない"], "mutate"),
        )
        for text, said, unsaid in cases:
            with self.subTest(text=text):
                (self.repo / ja.DECL_NAME).write_text(text, encoding="utf-8")
                brief = ja.material_prep(self.jdir, "gate-efficacy", self.repo, "")["brief"]
                for s in said:
                    self.assertIn(s, brief)
                self.assertNotIn(unsaid, brief)

    def _lens_rows(self, invoked):
        return [{"skill": e["skill"], "items": [], "invoked": invoked(e["skill"]), "failed": "起こしたが所見なし（差分を見た）"}
                for e in ja._skills(ja.due_view(self.start(), {}, []), "local-review")]

    def _plugins(self, names):
        cfg = self.tmp / "claude-config"
        ja.write_json(cfg / "plugins" / "installed_plugins.json", {"plugins": {f"{n}@market": [] for n in names}})
        return mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(cfg)})

    def test_missing_required_lens_is_refused(self):
        """元 test_blk_material の必須のレンズの場面（_lens_gap）: 必須のレンズを起こしていない返答と、それを awaiting_human に
        した返答を拒む。プラグインが入っていれば出し直させる（1 回目で諦めない）"""
        self.view()
        rows = self._lens_rows(lambda s: s != "pr-review-toolkit:code-reviewer")
        with self._plugins(["pr-review-toolkit"]):
            for status in ("clean", "awaiting_human"):
                with self.subTest(status):
                    mat = {"status": status, "checked": "差分を見た", "reason": "待つ"}
                    reply = {"material": mat, "simplify_carried": False, "findings": rows}
                    got = self.take_round("local-review", reply)
                    self.assertFalse(got["ok"])
                    self.assertFalse(got["done"], "プラグインが在れば出し直させる")
                    self.assertIn("'pr-review-toolkit:code-reviewer' は必須のレンズ", got["reason"])
                    self.assertEqual("awaiting_human にできない" in got["reason"], status == "awaiting_human")
        self.assertEqual(ja.rolekit.given_up_reason(self.jdir, "local-review"), "")

    def test_absent_plugin_gives_up_at_once(self):
        """元 material.py:455 の _lens_gap の 2 つ目（出し直さないか）を _reject(give_up=True) に渡した: レンズのプラグインが
        隔離した設定に無ければ、1 回目の拒みで done にして人に渡し、素材の欄と判定の支度がその理由を読む"""
        self.view()
        reply = {"material": {"status": "clean", "checked": "差分を見た"}, "simplify_carried": False,
                 "findings": self._lens_rows(lambda s: not s.startswith("pr-review-toolkit:"))}
        with self._plugins(["other-plugin"]):
            got = self.take_round("local-review", reply)
        self.assertFalse(got["ok"])
        self.assertTrue(got["done"], "1 回目から諦める")
        self.assertIn("プラグイン pr-review-toolkit が入っていない", got["reason"])
        self.assertEqual(len(ja.rolekit.rejected(self.jdir, "local-review")), 1)
        gave = ja.rolekit.given_up_reason(self.jdir, "local-review")
        self.assertIn("pr-review-toolkit", gave)
        self.assertEqual(ja.materials_given_up(self.jdir), [gave])
        self.assertIn("pr-review-toolkit", ja.fill_materials(self.jdir)["local_review"]["reason"])

    def test_local_review_unseen_lens_is_marked(self):
        """元 test_diverted.TakeCase.test_unrecovered_loss_is_taken_but_said_unseen（受け付けは拒まず、見ていないと書く）"""
        self.view()
        rows = [{"skill": e["skill"], "items": [], "invoked": True, "failed": "起こしたが所見なし（差分を見た）"}
                for e in ja._skills(ja.due_view(self.start(), {}, []), "local-review")]
        rows[0]["failed"] = "本文が届かなかった"
        reply = {"material": {"status": "clean", "checked": "差分を見た"}, "simplify_carried": False, "findings": rows}
        got = ja.material_take(self.jdir, "local-review", reply, self.repo)
        self.assertTrue(got["ok"], got)
        doc = ja.read_json(self.jdir / "material-local-review.json")
        self.assertTrue(doc["reply"]["findings"][0]["failed"].startswith(diverted.UNSEEN_TAG))
        self.assertEqual(ja.read_json(self.jdir / diverted.LENS_FILE)["unseen"], ["/code-review"])

    def test_materials_mark_not_run_and_given_up(self):
        """元 test_blk_material.test_collect_names_every_waiting_node と写しの rules の fill_materials"""
        got = self.view()
        self.assertTrue(got["provenance"])
        ja.write_json(self.jdir / "material-hygiene.json",
                      {"role": "hygiene", "reply": {}, "materials": {"hygiene": {"status": "clean", "checked": "差分"}}})
        ja.write_json(self.jdir / "material-pr-check.json",
                      {"role": "pr-check", "reply": {}, "materials": {"parallel_pr": {"status": "clean", "checked": "PR"}}})
        for _ in range(3):
            ja.rolekit.with_done(self.jdir, "provenance", {"ok": False, "reason": "出典が違う"})
        mats = ja.fill_materials(self.jdir)
        self.assertEqual(set(mats), set(ja.MATERIALS))
        self.assertEqual(mats["hygiene"]["status"], "clean")
        self.assertEqual(mats["parallel_pr"]["status"], "clean")
        self.assertEqual(mats["provenance"]["status"], "not_run")
        self.assertIn("出典が違う", mats["provenance"]["reason"])
        self.assertEqual(mats["local_review"]["status"], "not_run")
        self.assertIn("走っていない", mats["local_review"]["reason"])
        self.assertEqual(mats["fix_closure"]["status"], "not_applicable")
        self.assertEqual(ja.read_json(self.jdir / "materials.json"), mats)

    def test_materials_of_an_entry_run_are_not_applicable(self):
        """元 写しの rules の fill_materials（判定から入る run の周の P1 の素材は not_applicable と入口の理由）"""
        ja.write_json(self.jdir / ja.START_FILE, self.start(input={"base": {"rev": self.head}, "diff": {"empty": True},
                                                                   "requests": 2}))
        got = ja.material_route(self.jdir, self.repo)
        self.assertFalse(got["local_review"])
        mats = ja.fill_materials(self.jdir)
        self.assertEqual(mats["local_review"]["status"], "not_applicable")
        self.assertIn("判定から入る run", mats["local_review"]["reason"])
        self.assertEqual(mats["prior_decisions"]["status"], "not_run")


class GateSignalsCase(unittest.TestCase):
    """元 test_gate_na.SignalsCase: 差分に機械が見るゲートの印（テスト・CI・pre-commit・変異の腕の一覧などの定義のファイルと、
    assert を足す・消す行）"""
    DOCSTRING_DIFF = ('diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n@@ -9,7 +9,7 @@ def mean(xs):\n def median(xs):\n'
                      '-    """中央値"""\n+    """中央値（並べた真ん中）"""\n     if not xs:\n')

    @staticmethod
    def assert_diff(sign):
        return ("diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n@@ -1,3 +1,3 @@\n def clamp(x, lo, hi):\n"
                f"{sign}    assert lo <= hi, 'lo > hi'\n     return min(max(x, lo), hi)\n")

    def test_docstring_only_diff_has_no_signal(self):
        self.assertEqual(ja.gate_signals(["calc.py"], self.DOCSTRING_DIFF), [])

    def test_gate_files_are_signals(self):
        for f in ("tests/test_calc.py", "test_calc.py", "calc_test.go", "src/calc.test.ts", "conftest.py",
                  ".github/workflows/ci.yml", ".gitlab-ci.yml", ".pre-commit-config.yaml", ".husky/pre-commit",
                  ".review-checks.json", ".works-checks.json", "pyproject.toml", "Makefile", "package.json", ".eslintrc.json",
                  "tox.ini", "pytest.ini", "mypy.ini", "setup.cfg"):
            with self.subTest(f):
                got = ja.gate_signals(["calc.py", f], "")
                self.assertEqual(len(got), 1, got)
                self.assertIn(f, got[0])

    def test_added_or_removed_assert_is_a_signal(self):
        for sign in "+-":
            with self.subTest(sign):
                got = ja.gate_signals(["calc.py"], self.assert_diff(sign))
                self.assertEqual(len(got), 1, got)
                self.assertIn("assert", got[0])

    def test_context_assert_is_not_a_signal(self):
        """変えていない行（頭が空白）の assert は差分がゲートを変えた印にならない"""
        self.assertEqual(ja.gate_signals(["calc.py"], self.assert_diff(" ")), [])

    def test_only_the_gate_node_lets_the_role_judge(self):
        """元 test_gate_na.PolicyCase.test_other_node_keeps_the_copy_rule: ほかの節（代役の忠実性）は写しのまま拒む"""
        with tempfile.TemporaryDirectory() as tmp:
            diff = pathlib.Path(tmp) / "diff.patch"
            diff.write_text(self.DOCSTRING_DIFF, encoding="utf-8")
            view = ja.due_view({}, None, ["calc.py"])
            self.assertTrue(ja.role_judged_na(view, ja.GATE_NODE, diff))
            self.assertFalse(ja.role_judged_na(view, "p1.test_double_fidelity", diff))
            self.assertFalse(ja.role_judged_na(view, ja.GATE_NODE, pathlib.Path(tmp) / "nowhere.patch"))


# ================================================================ 判定役の材料
class BriefCase(_RepoCase):
    def test_brief_emits_the_seven_sections_in_order(self):
        """元 test_blk_judge（judgebrief.brief の節の並び・answers_section・carry.prior_section）"""
        (self.repo / "app.txt").write_text("一行目\n直した\n", encoding="utf-8")
        req = self.repo / "request.json"
        req.write_text(json.dumps([{"where": "app.txt:2", "text": "依頼の本文"}], ensure_ascii=False), encoding="utf-8")
        row = {"finding": 1, "where": "app.txt:2", "class_id": "w1", "problem": "問題", "activity": "作業", "practice": "定石",
               "sources": [], "applies": "", "not_applies": "", "basis": "knowledge",
               "versus": {"proposed": "", "verdict": "none", "challenge": ""}}
        (self.jdir / "world.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        worldmark.write(self.jdir, status="ok", reason="", world_file=str(self.jdir / "world.jsonl"), classes=[], dropped=[])
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "app.txt:2", "text": "依頼の本文"}])
        ja.write_json(self.jdir / "purpose.json", {"purpose_text": "凍った目的の印", "source": "①PR 説明",
                                                   "known_weaknesses": [], "source_files": []})
        ja.write_json(self.jdir / "premises.json", {"constraints": []})
        start = self.start(request_file="request.json",
                           answers=[{"question": "q1", "text": "答えの印"}],
                           input={"base": {"rev": self.head}, "pr": {"number": 9, "title": "PR の題", "body": "PR の本文"}})
        ja.write_json(self.jdir / ja.START_FILE, start)
        ja.material_route(self.jdir, self.repo)
        carry.place_prior(self.jdir, [{"where": "受け付け", "text": "前の拒否"}, {"where": carry.REDESIGN_WHERE, "text": "作り直し"}])
        path = ja.brief(self.jdir, self.repo, start, str(self.tmp / "REVIEW.md"), "")
        text = pathlib.Path(path).read_text(encoding="utf-8")
        heads = [ja.BRIEF_HEAD, worldmark.HEAD, "## 入力", ja.LEDGER_HEAD.strip(), ja.REQUEST_HEAD, ja.ANSWERS_HEAD,
                 carry.PRIOR_HEAD, carry.REDESIGN_HEAD]
        at = [text.find(h) for h in heads]
        self.assertNotIn(-1, at, list(zip(heads, at)))
        self.assertEqual(at, sorted(at), "節の並び")
        self.assertIn("凍った目的の印", text)
        self.assertIn("答えの印", text)
        self.assertIn("PR の本文", text)
        self.assertIn(str(self.jdir / "diff.patch"), text)
        self.assertNotIn("{{", text, "穴を残さない")

    def test_brief_carries_the_human_policy_cut_at_the_paste_cap(self):
        """元 diagnose.md の付録「人の方針」（start の policy_paste。policy.brief が PASTE_CAP バイトで切った物）。文書の無い run は節を
        置かない。再審の材料も同じ本文を貼る"""
        start = self.start()
        ja.write_json(self.jdir / ja.START_FILE, start)
        ja.material_route(self.jdir, self.repo)
        text = pathlib.Path(ja.brief(self.jdir, self.repo, start, str(self.tmp / "REVIEW.md"))).read_text(encoding="utf-8")
        self.assertNotIn(ja.POLICY_HEAD, text)
        pmd = self.tmp / "policy.md"
        for body, whole in (("方針の印: 既定の道を狭めない\n", True), ("方" * 20000, False)):
            with self.subTest(whole=whole):
                pmd.write_text(body, encoding="utf-8")
                start = self.start(policy_md=str(pmd))
                text = pathlib.Path(ja.brief(self.jdir, self.repo, start, str(self.tmp / "REVIEW.md"))).read_text(encoding="utf-8")
                tail = text[text.index(ja.POLICY_HEAD) + len(ja.POLICY_HEAD):].strip()
                self.assertLessEqual(len(tail.encode("utf-8")), ja.policy.PASTE_CAP)
                self.assertEqual(tail == body.strip(), whole)
                self.assertEqual(ja._rejudge_brief(self.jdir, "異議", {}, start).split(ja.POLICY_HEAD)[1].strip(), tail)

    def test_policy_text_reads_frozen_copy(self):
        """貼る方針は始めの記録の固めた版の写し（policy.copy）。始めの後に policy_md の文書を書き換えても固めた版を貼る"""
        pmd = self.tmp / "policy.md"
        pmd.write_text("方針の印: 固めた版\n", encoding="utf-8")
        start = self.start(policy_md=str(pmd), policy=ja.policy.freeze(self.tmp / "run", self.repo, str(pmd)))
        pmd.write_text("方針の印: 書き換えた版\n", encoding="utf-8")
        self.assertEqual(ja.policy_text(start).strip(), "方針の印: 固めた版")
        self.assertEqual(ja.policy_text(ja.start_view({"policy_md": str(pmd), "policy": "壊れた"})).strip(), "方針の印: 書き換えた版")

    def test_baseline_that_cannot_be_read_leaves_local_checks_not_run(self):
        """直す前の結末が読めない・素材の欄が欠けた時は、素材 local_checks を not_run と理由にする（clean と読まない）"""
        path = self.tmp / "baseline.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(ja.baseline_local_checks(path)["status"], "not_run")
        ja.baseline_red.write_baseline(path, suite="", test_cmd="", rev=self.head, exit=0, cases=[], material={"status": "clean"})
        got = ja.baseline_local_checks(path)
        self.assertEqual(got["status"], "not_run")
        self.assertIn("形が違う", got["reason"])

    def test_diagnose_prep_stops_after_material_give_up(self):
        """元 blk-material の collect（素材の役が 3 回とも拒まれたら盤面を止めた）。残りの素材で材料は組む"""
        ja.write_json(self.jdir / ja.START_FILE, self.start())
        route = ja.material_route(self.jdir, self.repo)
        self.assertTrue(route["hygiene"])
        for _ in range(3):
            ja.rolekit.with_done(self.jdir, "hygiene", {"ok": False, "reason": "形が違う"})
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "", str(self.tmp / "REVIEW.md"), "")
        self.assertFalse(got["go"])
        self.assertTrue(pathlib.Path(got["brief_file"]).is_file())
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], ja.MATERIAL_STOP)
        self.assertEqual(ja.read_json(self.jdir / "materials.json")["hygiene"]["status"], "not_run")

    def test_diagnose_prep_skips_on_objection_or_stop(self):
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "異議", "", "")
        self.assertFalse(got["go"])
        ja.write_stop(self.jdir, ja.JUDGE_STOP, "前で止めた")
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "", "", "")
        self.assertFalse(got["go"])
        self.assertIn("前で止めた", got["reason"])


# ================================================================ 再審と仕様


# 元 works/tests/test_blk_spec.py の ACCEPT_TEST・write_reply・review_reply・revise_reply の写し（走らせるのは exit 1 の字面）
_ACCEPT_TEST = ("def test_mean_is_middle():\n"
                  "    # Given 1, 2, 3 の 3 つの数\n"
                  "    # When mean を呼ぶ\n"
                  "    # Then 2 を返す\n"
                  "    assert False\n")
_ACCEPT_RUN = "exit 1"
_FACE = {"key": "F1", "kind": "missing", "where": "R1",
           "why": "空の列の平均をどう扱うかが要件にも受け入れ条件にも無い（例外か 0 か）"}


def _write_reply(file="test_spec_accept.txt"):
    return {"requirements": [{"key": "R1", "text": "mean は 3 つの数の平均を返す"}],
            "acceptance": [{"key": "A1", "requirement": "R1", "file": file, "name": "test_mean_is_middle",
                            "run": _ACCEPT_RUN}],
            "out_of_scope": []}


def _review_reply(faces=True):
    if faces:
        return {"faces": [_FACE], "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}
    return {"faces": [], "faces_none": "要件 R1 と A1 の Then は依頼の 2 つ目と同じ値を見ている。範囲の外も無い",
            "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}


def _revise_reply():
    spec = _write_reply()
    spec["out_of_scope"] = ["空の列の平均（依頼に無い。今の実装のまま）"]
    return {"spec": spec, "handled": [{"key": "F1", "handled": "declared",
                                       "how": "空の列は依頼の範囲の外と決め、out_of_scope に理由つきで足した"}]}


class _SpecRepoCase(unittest.TestCase):
    """使い捨ての対象のリポジトリ（git。1 commit）と、run の置き場の judge/・rejudge/"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        gitkit.git(self.repo, "init", "-q")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        self.jdir = self.tmp / "art" / ja.JUDGE_DIR
        self.rdir = self.tmp / "art" / ja.REJUDGE_DIR
        self.jdir.mkdir(parents=True)

    def write_tests(self, text=_ACCEPT_TEST, name="test_spec_accept.txt"):
        (self.repo / name).write_text(text, encoding="utf-8")

    def written(self):
        self.write_tests()
        got = ja.spec_take(self.jdir, "write", _write_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        return got


class SpecErrorsCase(_SpecRepoCase):
    def test_acceptance_without_gwt_rejected(self):
        """元 test_blk_spec の書く役の拒否（写しの rules の _spec_errors: テストの中に Given/When/Then が要る）"""
        self.write_tests("def test_mean_is_middle():\n    assert False\n")
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_write_reply(), self.repo)
        self.assertIn("Given/When/Then", str(cm.exception))
        self.assertTrue(str(cm.exception).startswith("spec.write: "))

    def test_missing_test_file_and_name_rejected(self):
        """元 test_blk_spec の test_give_up_after_three（テストのファイルが無い）と、名前の無いファイル"""
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_write_reply(file="missing_test.txt"), self.repo)
        self.assertIn("missing_test.txt", str(cm.exception))
        self.write_tests(_ACCEPT_TEST.replace("test_mean_is_middle", "test_other"))
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_write_reply(), self.repo)
        self.assertIn("name 'test_mean_is_middle'", str(cm.exception))

    def test_keys_unique_and_point_to_requirements(self):
        """元 写しの rules の _spec_errors（鍵が一意・受け入れ条件が要件を指す・要件は受け入れ条件を持つ）"""
        self.write_tests()
        spec = _write_reply()
        spec["requirements"].append({"key": "R1", "text": "同じ鍵の要件"})
        spec["requirements"].append({"key": "R2", "text": "受け入れ条件の無い要件"})
        spec["acceptance"].append({**spec["acceptance"][0], "key": "A2", "requirement": "R9"})
        errs = ja._spec_errors(spec, self.repo)
        self.assertTrue(any("requirements[1] の key が重複" in e for e in errs), errs)
        self.assertTrue(any("'R9' が requirements に無い" in e for e in errs), errs)
        self.assertTrue(any("要件 'R2' に受け入れ条件が無い" in e for e in errs), errs)
        self.write_tests()
        self.assertEqual(ja._spec_errors(_write_reply(), self.repo), [])

    def test_review_needs_faces_none(self):
        """元 写しの rules の spec_review_output（穴を挙げないなら faces_none が要る）"""
        ja.spec_review_output(_review_reply())
        ja.spec_review_output(_review_reply(faces=False))
        with self.assertRaises(Reject) as cm:
            ja.spec_review_output({"faces": [], "faces_none": "無い", "reason": "x" * 20})
        self.assertIn("faces_none", str(cm.exception))

    def test_revise_answers_each_face_once(self):
        """元 写しの rules の spec_revise_output（審査の穴に key ごとに 1 度だけ答える）"""
        self.write_tests()
        ja.spec_revise_output(_revise_reply(), _review_reply(), self.repo)
        bad = _revise_reply()
        bad["handled"] = [{"key": "F9", "handled": "absorbed", "how": "x" * 20}]
        with self.assertRaises(Reject) as cm:
            ja.spec_revise_output(bad, _review_reply(), self.repo)
        self.assertIn("'F9' は仕様の審査に無い", str(cm.exception))
        self.assertIn("'F1' に応答が無い", str(cm.exception))

    def test_revise_due_only_with_faces(self):
        """元 test_blk_spec の test_no_faces_skips_revise（写しの条件 spec_revise_due）"""
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_review_reply()))[0], True)
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_review_reply(faces=False)))[0], False)


class SpecTakeCase(_SpecRepoCase):
    def test_review_is_read_only(self):
        """元 test_blk_spec の test_review_is_read_only（審査の役が作業ツリーを変えたら拒む。元に戻せば通る）"""
        self.written()
        (self.repo / "note.txt").write_text("x\n", encoding="utf-8")
        got = ja.spec_take(self.jdir, "review", _review_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])
        (self.repo / "note.txt").unlink()
        got = ja.spec_take(self.jdir, "review", _review_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIs(got["revise"], True, "穴が開いた審査は直す輪を回す")
        self.assertEqual(ja.read_json(self.jdir / "spec-review.json"), _review_reply())

    def test_review_without_faces_skips_revise(self):
        """元 test_blk_spec の test_no_faces_skips_revise"""
        self.written()
        got = ja.spec_take(self.jdir, "review", _review_reply(faces=False), self.repo)
        self.assertEqual((got["ok"], got["revise"]), (True, False), got)

    def test_bad_shape_is_a_reject_not_a_crash(self):
        """元 test_blk_spec の test_unreadable_reply_is_counted（読めない・形の違う返答は拒否として返す）"""
        got = ja.spec_take(self.jdir, "write", {"requirements": "x"}, self.repo)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"])
        got = ja.spec_take(self.jdir, "nope", {}, self.repo)
        self.assertFalse(got["ok"])

    def test_revise_replaces_the_spec(self):
        """元 写しの rules の _spec_now（直した版が在ればそれが今の仕様）"""
        self.written()
        ja.spec_take(self.jdir, "review", _review_reply(), self.repo)
        got = ja.spec_take(self.jdir, "revise", _revise_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertEqual(ja.spec_now(self.jdir), _revise_reply()["spec"])


class SpecGateCase(_SpecRepoCase):
    def asked(self, faces=True):
        self.written()
        self.assertTrue(ja.spec_take(self.jdir, "review", _review_reply(faces), self.repo)["ok"])
        if faces:
            self.assertTrue(ja.spec_take(self.jdir, "revise", _revise_reply(), self.repo)["ok"])
        got = ja.spec_ask(self.jdir, self.repo, "run-spec")
        self.assertIs(got["ask"], True, got)
        return got

    def test_ask_message(self):
        """元 test_blk_spec の test_pass_path の関所の文（run の字面・審査の穴と答え・答えの行）と test_blk_spec_gate"""
        got = self.asked()
        for part in (_ACCEPT_RUN, "spec.approve", "F1", "declared", "process.spec.approval",
                     specblk.gatemarks.answer.line("run-spec", "continue", "<通す範囲と条件>", env={}),
                     specblk.gatemarks.answer.line("run-spec", "stop", "<理由>", env={})):
            self.assertIn(part, got["message"])
        self.assertFalse((self.jdir / specblk.SPEC_FILE).exists(), "承認の前に仕様を固めない")

    def test_ask_without_faces_has_no_face_lines(self):
        """元 test_blk_spec の test_no_faces_skips_revise（審査の穴の行が無い）"""
        self.assertNotIn("審査の穴", self.asked(faces=False)["message"])

    def test_ask_after_give_up_stops(self):
        """元 test_blk_spec の test_give_up_after_three（3 回とも拒まれたら関所を開かず works:spec で止める）"""
        for _ in range(3):
            rolekit.with_done(self.jdir, "spec-write", {"ok": False, "reason": "テストのファイルが無い"})
        got = ja.spec_ask(self.jdir, self.repo, "run-spec")
        self.assertEqual(got, {"ask": False, "message": ""})
        stop = ja.read_stop(self.jdir)
        self.assertEqual(stop["stop_reason"], ja.SPEC_STOP)
        self.assertIn("3 回とも", stop["reason"])

    def test_freeze_records_sha_and_exit(self):
        """元 test_blk_spec の test_pass_path（承認の後に run を走らせ、sha256 と exit_at_approval を固め、依頼の行を積む）"""
        self.asked()
        ja.write_json(self.jdir / "request.json", [{"where": "x.txt", "text": "人の依頼"}])
        got = ja.spec_answer(self.jdir, self.repo, json.dumps({"decision": "approve", "text": "A1 で進めてよい"}))
        self.assertEqual(got, {"go": True, "reason": ""})
        spec = ja.read_json(self.jdir / "spec.json")
        a = spec["acceptance"][0]
        want = hashlib.sha256((self.repo / "test_spec_accept.txt").read_bytes()).hexdigest()
        self.assertEqual((a["sha256"], a["exit_at_approval"]), (want, 1))
        self.assertEqual((spec["approval"]["answer"], spec["approval"]["note"]), ("continue", "A1 で進めてよい"))
        self.assertEqual(spec["out_of_scope"], _revise_reply()["spec"]["out_of_scope"], "直した版を固めた")
        rows = ja.read_json(self.jdir / "request.json")
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]["text"].startswith(ja.SPEC_PROVENANCE), rows[1])
        self.assertIn("exit 1", rows[1]["measured"])
        batches = ja.request_batches(self.jdir, ja.start_view({}))
        self.assertEqual([(b["origin"], b["findings"]) for b in batches][1:], [(ja.SPEC_ORIGIN, rows[1:])],
                         "受け入れ条件の行は出どころの印 SPEC_ORIGIN のバッチ（元 review-loop.py:4040）")
        self.assertEqual(batches[0]["findings"], rows[:1])
        again = ja.spec_answer(self.jdir, self.repo, json.dumps({"decision": "continue", "text": "二度目"}))
        self.assertTrue(again["go"])
        self.assertEqual(ja.read_json(self.jdir / "spec.json")["approval"]["note"], "A1 で進めてよい", "1 度だけ固める")
        self.assertEqual(len(ja.read_json(self.jdir / "request.json")), 2)

    def test_gate_stop_words(self):
        """元 test_blk_spec の test_gate_stop と report.py の REQUEST_BY・HUMAN_BY（人の止めと止め札を分ける）"""
        for decision, text, want in (("stop", "受け入れ条件が弱い", "human:spec-gate"),
                                     ("reject", "", "human:spec-gate"),
                                     ("reject", "request: 札", "request:spec-gate"),
                                     ("stop", "request:札", "request:spec-gate")):
            with self.subTest(decision=decision, text=text):
                self.setUp()
                self.asked(faces=False)
                got = ja.spec_answer(self.jdir, self.repo, json.dumps({"decision": decision, "text": text}))
                self.assertIs(got["go"], False)
                stop = ja.read_stop(self.jdir)
                self.assertEqual(stop["stop_reason"], want)
                self.assertIn(text or specblk.GATE_STOP_NOTE, stop["reason"])
                self.assertFalse((self.jdir / "spec.json").exists())

    def test_gate_skipped(self):
        """元 test_blk_spec の test_give_up_after_three の answer gate=null（関所が開かなかった）"""
        for _ in range(3):
            rolekit.with_done(self.jdir, "spec-write", {"ok": False, "reason": "テストのファイルが無い"})
        ja.spec_ask(self.jdir, self.repo, "run-spec")
        got = ja.spec_answer(self.jdir, self.repo, "null")
        self.assertIs(got["go"], False)
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], ja.SPEC_STOP)

    def test_gate_unknown_word(self):
        """元 test_blk_spec の test_answer_rejects_unknown_word"""
        with self.assertRaises(rolekit.BoardGap):
            specblk.parse_gate(json.dumps({"decision": "maybe", "text": ""}))
        self.asked(faces=False)
        got = ja.spec_answer(self.jdir, self.repo, json.dumps({"decision": "maybe", "text": ""}))
        self.assertIs(got["go"], False)
        self.assertIn("maybe", got["reason"])


_UNIT_A = "src/a.py:f — 上限を超えた入力を黙って切る"
_UNIT_B = "src/b.py:g — 名前の誤り"


def _judgment():
    return {"units": [{"key": _UNIT_A, "label": "block", "reason": "切ると呼び手が気づけない", "why_chain": ["a", "b"]},
                      {"key": _UNIT_B, "label": "suggest", "disposition": "do-now", "reason": "読み手が迷う"}],
            "questions": [], "framing": "上限の扱い", "one_shot": "切らずに拒む", "materials_missing": [],
            "carried_r1": [], "one_shot_closes": [], "precedents": []}


def _rejudge_reply(verdict="一部採る", **over):
    units = [{"key": _UNIT_A, "label": "block", "reason": "異議の通り、切る前に拒む形に直す"},
             {"key": _UNIT_B, "label": "nit", "reason": "読み手は迷わない"}]
    return {"verdict": verdict, "new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた", "units": units,
            "reason": "上限の単位は採り、名前の単位は下げた", **over}


class RejudgeCase(_SpecRepoCase):
    def prepared(self, objection=f"{_UNIT_A} の処方が誤り。12 行は切らずに拒んでいる"):
        ja.write_json(self.jdir / "judgment.json", _judgment())
        got = ja.rejudge_prep(self.jdir, self.rdir, objection, self.repo)
        self.assertTrue(got["go"], got)
        return got

    def test_no_first_judgment_stops_session(self):
        """元 test_blk_rejudge の test_block_no_session_path（1 回目の判定が無ければ再審せずに rejudge-session で止める）"""
        got = ja.rejudge_prep(self.jdir, self.rdir, "異議", self.repo)
        self.assertEqual((got["go"], got["brief_file"]), (False, ""))
        self.assertEqual(ja.read_stop(self.rdir)["stop_reason"], stopby.REJUDGE_SESSION)
        self.assertIsNone(ja.read_stop(self.jdir))

    def test_prep_writes_brief_and_before(self):
        """元 test_rejudge の test_prep_marks_once（1 回目の前だけ単位の写しを置く）と描いた指示書の値"""
        got = self.prepared()
        brief = pathlib.Path(got["brief_file"]).read_text(encoding="utf-8")
        for part in ("12 行は切らずに拒んでいる", _UNIT_B, "上限の扱い", str(self.jdir / "judgment.json")):
            self.assertIn(part, brief)
        before = ja.read_json(self.rdir / "units-before.json")
        self.assertEqual([u["key"] for u in before["units"]], [_UNIT_A, _UNIT_B])
        self.assertEqual(before["numbered_keys"], [_UNIT_A, _UNIT_B])
        ja.rejudge_prep(self.jdir, self.rdir, "別の異議", self.repo)
        self.assertEqual(ja.read_json(self.rdir / "units-before.json"), before, "写しは 1 回目の前だけ")

    def test_verdict_word_outside_three_rejected(self):
        """元 test_rejudge の test_type_rejected（写しの型: verdict は 採る・退ける・一部採る）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _rejudge_reply(verdict="保留"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("型が合わない", got["reason"])
        got = ja.rejudge_take(self.jdir, self.rdir, {"verdict": "採る"}, self.repo)
        self.assertFalse(got["ok"])
        self.assertFalse((self.rdir / "judgment.json").exists())

    def test_empty_facts_rejected(self):
        """元 test_rejudge の test_empty_facts_rejected（写しの rules の rejudge_output）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _rejudge_reply(new_facts="確かめた"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("new_facts", got["reason"])
        self.assertFalse((self.rdir / "rejudge-diff.json").exists())

    def test_tree_changed_rejected(self):
        """元 test_rejudge の test_tree_changed_rejected"""
        self.prepared()
        (self.repo / "a.txt").write_text("x\n", encoding="utf-8")
        got = ja.rejudge_take(self.jdir, self.rdir, _rejudge_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])

    def test_accept_writes_judgment_and_diff(self):
        """元 test_rejudge の test_unnamed_change_recorded（下げた単位と名指されていない変化を前後の差に残す）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _rejudge_reply(), self.repo)
        self.assertEqual((got["ok"], got["verdict"]), (True, "一部採る"), got)
        self.assertEqual(ja.read_json(self.jdir / "judgment.json"), _judgment(), "1 回目の判定は上書きしない")
        now = ja.read_json(self.rdir / "judgment.json")
        self.assertEqual(set(now), set(_judgment()))
        self.assertEqual(now["units"][1], {"key": _UNIT_B, "label": "nit", "reason": "読み手は迷わない"})
        rows = ja.read_json(self.rdir / "rejudge-diff.json")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["pass"], row["node"], row["verdict"]), ("rejudge", "p2.rejudge", "一部採る"))
        self.assertEqual(row["unnamed_changed"], [_UNIT_B])
        named = {(c["key"], c["field"]): c["named"] for c in row["changed"] if c["kind"] == "changed"}
        self.assertEqual(named[(_UNIT_B, "label")], False)
        self.assertEqual(named[(_UNIT_A, "reason")], True)

    def test_lowered_block_named_in_diff_and_exit(self):
        """元 test_rejudge の test_collect_exit_has_lowered_and_objection（block から下げた単位）"""
        self.prepared()
        reply = _rejudge_reply(verdict="採る")
        reply["units"][0] = {**reply["units"][0], "label": "suggest", "disposition": "do-now"}
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        self.assertEqual(ja.read_json(self.rdir / "rejudge-diff.json")[0]["lowered"], [_UNIT_A])
        got = ja.rejudge_collect(self.rdir)
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["passes"], got["verdicts"], got["lowered"]), (1, ["採る"], [_UNIT_A]))
        self.assertIn(_UNIT_A, got["objection"])
        self.assertEqual(got["unsettled"], {"text": "", "settled": True})
        self.assertEqual(ja.read_json(self.rdir / "rejudge-exit.json"), got)
        self.assertEqual(ja.rejudge_verdict(self.rdir), "採る")

    def test_new_open_units(self):
        """元 test_rejudge の test_new_open_units"""
        self.prepared()
        reply = _rejudge_reply()
        reply["units"].append({"key": "src/c.py:h — 上限の抜け道がもう 1 つ", "label": "block"})
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        got = ja.rejudge_collect(self.rdir)
        self.assertEqual(got["new_open_units"], ["src/c.py:h — 上限の抜け道がもう 1 つ"])
        self.assertFalse(got["unsettled"]["settled"], "一部採るは異議を降ろさない")

    def test_collect_after_give_up_stops(self):
        """元 test_rejudge の test_collect_names_last_rejection（3 回とも拒まれたら works:rejudge で止める）"""
        self.prepared()
        for _ in range(3):
            out = ja.rejudge_take(self.jdir, self.rdir, _rejudge_reply(new_facts="確かめた"), self.repo)
            rolekit.with_done(self.rdir, "rejudge", out)
        got = ja.rejudge_collect(self.rdir)
        self.assertFalse(got["ok"])
        self.assertIn("3 回", got["reason"])
        self.assertEqual(ja.read_stop(self.rdir)["stop_reason"], stopby.REJUDGE)
        self.assertIsNone(ja.rejudge_verdict(self.rdir))

    def test_class_query_examples_tried(self):
        """元 test_blk_rejudge の test_rejudge_defects_query_matching_fixed_form_is_rejected（例が問いと合わなければ拒む）"""
        self.prepared()
        reply = _rejudge_reply()
        reply["units"][0]["class_query"] = {
            "how": {"patterns": ["truncate("], "fixed": True, "paths": ["src"], "count": "lines"},
            "counts": "defects", "total": 1, "hits": ["x = truncate(v)"], "misses": ["x = reject_over(truncate(v))"]}
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("class_query", got["reason"])
        reply["units"][0]["class_query"]["misses"] = ["x = reject_over(v)"]
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIn(_UNIT_A, ja.read_json(self.rdir / "query-examples.json"))


class RejudgeDiffCase(unittest.TestCase):
    """元 test_rejudge の DiffCase（diff_units）"""
    BEFORE = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "suggest", "disposition": "do-now"},
              {"key": "k3", "label": "info"}]

    def test_named_by_number(self):
        after = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "nit"}, {"key": "k3", "label": "info"}]
        for text in ("#2 の判定を見直せ", "no 2 は誤り", "No.2 は誤り", "2 番の単位", "２番の単位"):
            with self.subTest(text):
                got = ja.diff_units(self.BEFORE, after, text, ["k1", "k2", "k3"])
                self.assertEqual(got["unnamed_changed"], [], got)
                self.assertTrue(all(c["named"] for c in got["changed"]))
        got = ja.diff_units(self.BEFORE, after, "#12 と #1 を見直せ", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k2"])

    def test_no_names_all_unnamed(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k2", "label": "nit"},
                 {"key": "k3", "label": "info", "reason": "足した"}]
        got = ja.diff_units(self.BEFORE, after, "判定がおかしい", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k1", "k2", "k3"])
        self.assertEqual(got["lowered"], ["k1"])

    def test_removed_and_lowered(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k4", "label": "block"}]
        got = ja.diff_units(self.BEFORE, after, "k1 は block でない", [])
        kinds = {(c["key"], c["kind"]) for c in got["changed"]}
        self.assertTrue({("k2", "removed"), ("k3", "removed"), ("k4", "added"), ("k1", "changed")} <= kinds)
        self.assertEqual(got["lowered"], ["k1"])
        self.assertEqual(got["unnamed_changed"], ["k2", "k3", "k4"])

    def test_fields_are_the_writes_pick(self):
        after = [dict(self.BEFORE[0], origin_analysis="書き足した"), self.BEFORE[1], self.BEFORE[2]]
        self.assertEqual(ja.diff_units(self.BEFORE, after, "", [])["changed"], [])
        self.assertEqual(list(ja.REJUDGE_UNIT_FIELDS), ["key", "label", "disposition", "reason", "reopen_evidence"])


class SpecblkCase(unittest.TestCase):
    """元 test_blk_spec_gate の GateTextCase と test_blk_spec の parse_gate の場面（lib/specblk に残した口）"""

    def test_gate_text_answer_lines(self):
        asking = {"node": "spec.approve", "kinds": ["declared"], "question": "承認するか", "items": ["A1"]}
        text = specblk.gate_text(asking, run_id="run-x")
        for verb, note in (("continue", "<通す範囲と条件>"), ("stop", "<理由>")):
            self.assertIn(specblk.gatemarks.answer.line("run-x", verb, note), text)

    def test_gate_text_subjects_are_plain_and_quote_the_question(self):
        """元 test_blk_spec_gate.py:34・41: 仕様の関所の文も平易な名を主語にし（記録の名は括弧の中の『記録の名』の後ろにだけ）、
        本線の答え方で書かれた問いは引用（> の行）で載せて読み替えの 1 行を添え、答え方の continue は 1 通りだけ"""
        from lib.tests.test_plan_gate import MAINLINE_Q, internal_subjects, unquoted_mainline
        asking = {"node": "spec.approve", "kinds": ["declared"], "question": MAINLINE_Q, "items": ["A1"]}
        text = specblk.gate_text(asking, run_id="run-x")
        self.assertEqual(internal_subjects(text), [])
        self.assertEqual(unquoted_mainline(text), [])
        quoted = [x.lstrip()[1:].strip() for x in text.splitlines() if x.lstrip().startswith(">")]
        self.assertEqual(quoted, [x.strip() for x in MAINLINE_Q.splitlines()])
        after = text.split(quoted[-1], 1)[1].split("答え方", 1)[0]
        self.assertEqual(len([x for x in after.splitlines() if "--note" in x and "--detail" in x]), 1, after)
        self.assertEqual(text.count(specblk.gatemarks.answer.line("run-x", "continue", "<通す範囲と条件>")), 1)

    def test_parse_gate(self):
        self.assertIsNone(specblk.parse_gate("null"))
        self.assertIsNone(specblk.parse_gate(""))
        self.assertEqual(specblk.parse_gate('{"decision": "reject"}'), {"decision": "reject", "text": ""})
        with self.assertRaises(rolekit.BoardGap):
            specblk.parse_gate("[1]")
        self.assertEqual(specblk.snapshot_name("spec.review"), "spec-snapshot-spec.review.json")


# ================================================================ 並行 PR と世界の解


_GITHUB = "git@github.com:o/r.git"
_MEAN_SOURCE = "def mean(xs):\n    return sum(xs)\n"
# 元 works/tests/replies/pr_ok.json・pr_no_conflicts.json・pr_handed_over.json
_PR_OK = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている（gh pr diff 7 -R o/r の hunk @@ -1,3 +1,4 @@）。申し送りの下書きを conflicts[0].note に書いた（投稿していない）"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": False,
                   "note": "PR #7 の担当へ: この run（判定から入る run）も stats.py の mean を直します。#7 の hunk @@ -1,3 +1,4 @@ と同じ行です。どちらを先に入れるか決めてください。"}],
    "excluded": [{"pr": "7", "file": "stats.py", "start": 1, "end": 2,
                  "why": "PR #7 の hunk @@ -1,3 +1,4 @@ が mean の同じ行を書き換える（この run の依頼 1 件目と同じ所）"}],
}
_PR_NO_CONFLICTS = {
    "material": {"status": "clean", "checked": "gh -R o/r で open な PR 2 件を引き、自分の PR（headRefOid が HEAD）を除いて、変更ファイルの集合と交差した PR #7 の差分を読んだ。同じファイルの hunk はこの run の変更とぶつからない（衝突 0 件・打ち切りなし）"},
    "repo": "o/r", "listed": 2, "truncated": False, "conflicts": [], "excluded": [],
}
_PR_HANDED_OVER = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている。担当の PR に申し送った"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": True, "note": "gh pr comment 7 -R o/r で申し送った"}],
    "excluded": [],
}


def _fake_gh(prs, files):
    """lib/ghreads._gh の代わりの読む口（本物の gh・GitHub に触らない）。prs は pr list の返り、files は番号 → 変更ファイル"""
    calls = []

    def gh(*args):
        calls.append(args)
        if args[:2] == ("pr", "list"):
            return prs, None, False
        if args[:2] == ("pr", "view"):
            return {"files": [{"path": p} for p in files.get(args[2], [])]}, None, False
        return None, f"知らない語 {args}", False
    gh.calls = calls
    return gh


def _never(*args):
    raise AssertionError(f"gh を呼んではいけない: {args}")


class _PrBase(unittest.TestCase):
    """並行 PR の場面（元 test_blk_pr の PrCase）: 判定から入る run の対象（stats.py を持つ git の木）と judge/ の置き場"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="judge-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo, self.jdir = self.tmp / "repo", self.tmp / "art" / ja.JUDGE_DIR
        self.repo.mkdir()
        self.jdir.mkdir(parents=True)
        gitkit.git(self.repo, "init", "-q")
        (self.repo / "stats.py").write_text(_MEAN_SOURCE, encoding="utf-8")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        gitkit.git(self.repo, "remote", "add", "origin", _GITHUB)
        self.head = gitkit.git(self.repo, "rev-parse", "HEAD").strip()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"base_rev": self.head, "input": {"base": {"rev": self.head}}}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "stats.py:2", "text": "mean が数で割っていない"}])

    def scan(self, gh=None, which=lambda name: "/bin/gh"):
        return ja.pr_scan(self.jdir, self.repo, gh=gh or _never, which=which)

    def material(self):
        return json.loads((self.jdir / ja.MATERIAL_PR_FILE).read_text(encoding="utf-8"))

    def snap(self):
        """入口が置く作業ツリーの写し（judge/judge-tree.json。元 prcheck.snapshot の pr-snapshot.json）"""
        ja.write_json(self.jdir / ja.TREE_FILE, core_accept.tree_state(self.repo))


class PrScanCase(_PrBase):
    def test_no_crossing_is_decided_by_machine(self):
        """元 test_blk_pr の test_helper_by_engine_when_no_crossing: 交差 0 → 機械で済む（役は要らない）。素材は clean、
        自分の PR（headRefOid が HEAD）は外す。外す hunk の一覧は空で置く"""
        gh = _fake_gh([{"number": 3, "headRefName": "me", "headRefOid": self.head},
                         {"number": 7, "headRefName": "x", "headRefOid": "f" * 40}], {"7": ["other.py"], "3": ["stats.py"]})
        got = self.scan(gh)
        self.assertEqual((got["go"], got["go_role"]), (True, False), got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")
        self.assertEqual(self.material()["role"], "pr-check")
        self.assertIn(("pr", "view", "7", "-R", "github.com/o/r", "--json", "files"), gh.calls)
        self.assertNotIn(("pr", "view", "3", "-R", "github.com/o/r", "--json", "files"), gh.calls, "自分の PR は見ない")
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["excluded"]), ("p0.parallel_pr", []))
        self.assertTrue(all("-R" in c for c in gh.calls), "gh は必ず -R で呼ぶ")

    def test_crossing_falls_back_to_role(self):
        """元 test_blk_pr の test_fallback_on_crossing_sets_role_needed: 交差 1 件 → 役へ（go_role）。渡し物に理由と
        交差を取る集合（差分が空なので依頼の where が名指す追跡中のパス）。素材は役が返すまで書かない"""
        got = self.scan(_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual((got["go"], got["go_role"]), (True, True))
        self.assertIn("交差", got["reason"])
        brief = json.loads((self.jdir / "pr-brief.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["node"], brief["changed_files"], brief["fallback"]), ("p0.parallel_pr", ["stats.py"], got["reason"]))
        self.assertEqual(brief["request_wheres"], ["stats.py:2"])
        self.assertFalse((self.jdir / ja.MATERIAL_PR_FILE).exists())

    def test_diff_files_win_over_request_wheres(self):
        """元 review-loop.py の _pr_files: 差分の根から変わったファイルが在れば、それが交差を取る集合（依頼の where は使わない）"""
        (self.repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        got = self.scan(_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual(got["go_role"], False, got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")

    def test_gh_missing_falls_back(self):
        """元 test_blk_pr の test_fallback_when_gh_missing: gh が無い → 何も走らせずに役へ"""
        got = self.scan(which=lambda name: None)
        self.assertTrue(got["go_role"])
        self.assertIn("gh", got["reason"])

    def test_no_forge_is_not_applicable(self):
        """元 test_forge の forge の無い run（entry の parallel_pr_due・fill_materials の組み手）: remote が GitHub でない
        （ローカルのパス）→ 役を起こさず、素材は not_applicable（no_forge: …）"""
        gitkit.git(self.repo, "remote", "set-url", "origin", str(self.tmp / "elsewhere"))
        got = self.scan()
        self.assertEqual((got["go"], got["go_role"]), (True, False))
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_applicable")
        self.assertTrue(m["reason"].startswith("no_forge: local_path"), m)

    def test_empty_set_is_not_run(self):
        """元 test_blk_pr の test_blocked_is_engine_with_reason: 交差を取る集合が空 → 機械が not_run で済ませ、理由に「空」"""
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "nowhere.py", "text": "x"}])
        got = self.scan()
        self.assertFalse(got["go_role"])
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_run")
        self.assertIn("空", m["reason"])

    def test_truncated_and_unreadable_wait_for_human(self):
        """元 review-loop.py の parallel_pr_reply: 一覧が上限で打ち切られた・gh が読めない → awaiting_human（衝突なしと書かない）"""
        many = [{"number": n, "headRefOid": "f" * 40} for n in range(ja.PR_LIMIT)]
        self.scan(_fake_gh(many, {}))
        self.assertIn("打ち切られた", self.material()["materials"]["parallel_pr"]["reason"])
        self.scan(lambda *a: (None, "gh pr が exit 1: HTTP 401", False))
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "awaiting_human")
        self.assertIn("HTTP 401", m["reason"])

    def test_stopped_run_does_not_go(self):
        """仕様の段が止めた run は先へ進めない（go 偽）"""
        ja.write_stop(self.jdir, "human:spec-gate", "要らない")
        got = self.scan()
        self.assertEqual((got["go"], got["go_role"]), (False, False))

    def test_github_repo_redacts_token(self):
        """元 entry.py の github_repo_redacted: GitHub でない remote の理由の文に URL の userinfo（トークン）を載せない"""
        gitkit.git(self.repo, "remote", "set-url", "origin", "https://user:SECRET@git.example.com/o/r.git")
        slug, why = ja._github_repo(self.repo)
        self.assertIsNone(slug)
        self.assertNotIn("SECRET", why)
        gitkit.git(self.repo, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.assertEqual(ja._github_repo(self.repo), ("github.com/o/r", None))

    def test_github_repo_reads_the_url_with_forge(self):
        """URL の読みは forge.repo_of と同じ広さで、gh -R には常にホストまで渡す（github.com の別名は github.com に寄せる）"""
        for url, slug in (("ssh://git@ssh.github.com:443/o/r.git", "github.com/o/r"), ("https://www.github.com/o/r", "github.com/o/r"),
                          ("git@github.com-work:o/r.git", "github.com/o/r"), ("https://acme.ghe.com/o/r.git", "acme.ghe.com/o/r")):
            with self.subTest(url):
                gitkit.git(self.repo, "remote", "set-url", "origin", url)
                self.assertEqual(ja._github_repo(self.repo), (slug, None))

    def test_github_repo_takes_the_tracked_remote_first(self):
        """枝が origin の外の remote を追えばその remote の PR を引く（fork の clone で origin の fork を引いて clean と言わない）。
        追う先が手元の枝（remote の無い名）なら origin"""
        gitkit.git(self.repo, "remote", "add", "up", "https://github.com/up/r.git")
        gitkit.git(self.repo, "update-ref", "refs/remotes/up/main", "HEAD")
        gitkit.git(self.repo, "branch", "-q", "--set-upstream-to=up/main")
        self.assertEqual(ja._github_repo(self.repo), ("github.com/up/r", None))
        gitkit.git(self.repo, "branch", "-q", "base")
        gitkit.git(self.repo, "branch", "-q", "--set-upstream-to=base")
        self.assertEqual(ja._github_repo(self.repo), ("github.com/o/r", None))


class PrAcceptCase(_PrBase):
    def setUp(self):
        super().setUp()
        self.snap()

    def accept(self, reply):
        return ja.pr_accept(self.jdir, json.dumps(reply, ensure_ascii=False), self.repo)

    def test_check_no_post(self):
        """元 test_blk_pr の test_check_no_post"""
        self.assertEqual(ja.check_no_post(_PR_HANDED_OVER), ["7"])
        self.assertEqual(ja.check_no_post(_PR_OK), [])
        self.assertEqual(ja.check_no_post(_PR_NO_CONFLICTS), [])
        two = json.loads(json.dumps(_PR_OK))
        two["conflicts"] += [{"pr": "9", "files": ["a"], "handed_over": True}, {"pr": "11", "files": ["b"], "handed_over": True}]
        self.assertEqual(ja.check_no_post(two), ["9", "11"])
        self.assertEqual(ja.check_no_post({"conflicts": "x"}), [])

    def test_handed_over_true_rejected(self):
        """元 test_blk_pr の test_handed_over_true_rejected: handed_over true が 1 件 → ok false、文に pr と「投稿しない」。何も書かない"""
        got = self.accept(_PR_HANDED_OVER)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("投稿しない", got["reason"])
        self.assertTrue(got["reason"].endswith(": 7"), got["reason"])
        self.assertFalse((self.jdir / "pr-excluded.json").exists())

    def test_handover_draft_accepted_with_anchor(self):
        """元 test_blk_pr の test_handover_draft_accepted・test_excluded_hunks_leave_scope・test_excluded_carries_content_anchor:
        通れば外す hunk が中身と sha256 と写しの HEAD つきで pr-excluded.json に、申し送りの下書きが pr-downgrades.json に、
        素材（excluded を外した返答）が material-pr-check.json に置かれる"""
        got = self.accept(_PR_OK)
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["head"]), ("p0.parallel_pr", self.head))
        h = doc["excluded"][0]
        self.assertEqual({k: h[k] for k in ("pr", "file", "start", "end", "why")}, _PR_OK["excluded"][0])
        self.assertEqual(h["text"], _MEAN_SOURCE)
        self.assertEqual(h["sha256"], hashlib.sha256(_MEAN_SOURCE.encode("utf-8")).hexdigest())
        drafts = json.loads((self.jdir / ja.PR_DOWNGRADES_FILE).read_text(encoding="utf-8"))
        self.assertEqual(drafts, [{"pr": "7", "files": ["stats.py"], "note": _PR_OK["conflicts"][0]["note"]}])
        mat = self.material()
        self.assertEqual(mat["materials"]["parallel_pr"]["status"], "found")
        self.assertNotIn("excluded", mat["reply"])

    def test_no_conflicts_reply_accepted(self):
        """元 test_blk_pr の test_no_conflicts_reply_accepted"""
        self.assertTrue(self.accept(_PR_NO_CONFLICTS)["ok"])
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["excluded"], [])

    def test_excluded_checked(self):
        """元 test_blk_pr の test_excluded_checked: 外す hunk の誤り → ok false。何も書かない"""
        hunk = _PR_OK["excluded"][0]
        cases = {"excluded が無い": {k: v for k, v in _PR_OK.items() if k != "excluded"},
                 "conflicts に無い": dict(_PR_OK, excluded=[dict(hunk, pr="99")]),
                 "交差したファイル": dict(_PR_OK, excluded=[dict(hunk, file="other.py")]),
                 "より大きい": dict(_PR_OK, excluded=[dict(hunk, start=2, end=1)]),
                 "行の数 2 を超える": dict(_PR_OK, excluded=[dict(hunk, end=3)]),
                 "note": dict(_PR_OK, conflicts=[{k: v for k, v in _PR_OK["conflicts"][0].items() if k != "note"}]),
                 "型": dict(_PR_OK, excluded=[dict(hunk, start=0)])}
        for word, bad in cases.items():
            got = ja.prcheck_take(self.jdir, bad, self.repo)
            self.assertFalse(got["ok"], word)
            self.assertIn(word, got["reason"], word)
            self.assertFalse((self.jdir / "pr-excluded.json").exists(), word)

    def test_fallback_role_reads_only(self):
        """元 test_blk_pr の test_fallback_role_reads_only・test_head_move_rejected: 入口の写しの後に作業ツリーや HEAD を
        変えて受け付け → ok false、文に「作業ツリーを変えた」"""
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = ja.prcheck_take(self.jdir, _PR_OK, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])
        (self.repo / "stats.py").write_text(_MEAN_SOURCE, encoding="utf-8")
        gitkit.git(self.repo, "checkout", "-q", "-b", "other")
        self.assertIn("ref", ja.prcheck_take(self.jdir, _PR_OK, self.repo)["reason"])

    def test_head_move_and_ignored_paths_are_refused(self):
        """元 test_blk_pr.py:442・467・557（prcheck.py:199 の take）: 作業ツリーの中身が同じままの別の commit への checkout と、
        git が無視するパスの追加も拒み、拒みの文が変わった欄を名指す"""
        (self.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        gitkit.git(self.repo, "add", ".gitignore")
        gitkit.git(self.repo, "commit", "-q", "-m", "ignore")
        self.snap()
        tree = gitkit.git(self.repo, "rev-parse", "HEAD^{tree}").strip()
        other = gitkit.git(self.repo, "commit-tree", tree, "-p", "HEAD", "-m", "same tree").strip()
        gitkit.git(self.repo, "checkout", "-q", "--detach", other)
        got = ja.prcheck_take(self.jdir, _PR_OK, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn(f"/ 今 {other}", got["reason"])
        self.assertIn("ref: 役を起こす前 refs/heads/", got["reason"])
        self.assertNotIn("git status --porcelain", got["reason"])
        gitkit.git(self.repo, "checkout", "-q", "-")
        (self.repo / "cache.log").write_text("x\n", encoding="utf-8")
        got = ja.prcheck_take(self.jdir, _PR_OK, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("git が無視するパス: 増えた ['cache.log'] 消えた []", got["reason"])
        self.assertFalse((self.jdir / ja.MATERIAL_PR_FILE).exists())

    def test_malformed_reply_bounced_not_crashed(self):
        """元 test_blk_pr の test_malformed_reply_bounced_not_crashed・test_accept_script_unreadable_reply: JSON でない・
        素材の形が違う返答 → 例外でなく ok false"""
        got = ja.pr_accept(self.jdir, "not json", self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("JSON", got["reason"])
        self.assertIn("型", ja.prcheck_take(self.jdir, dict(_PR_OK, material={"status": "maybe"}), self.repo)["reason"])

    def test_third_rejection_gives_up_and_stops(self):
        """元 blk-pr/scripts/collect.py の gave_up（rolekit.gave_up。by は stopby.PR）: 3 回目の拒否で done、止めの控えを置く"""
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = self.accept(_PR_HANDED_OVER)
            self.assertEqual(got["done"], n == rolekit.GIVE_UP_AFTER, n)
        self.assertEqual(len(json.loads((self.jdir / "rejects-pr-check.json").read_text(encoding="utf-8"))), 3)
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], stopby.PR)

    def test_third_rejection_by_exception_also_stops(self):
        """受け付けの中の例外（conflicts[].note が字でない）も拒否として数え、3 回目で止めの控えを置く"""
        bad = dict(_PR_OK, conflicts=[dict(_PR_OK["conflicts"][0], note=5)])
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = self.accept(bad)
            self.assertEqual((got["ok"], got["done"]), (False, n == rolekit.GIVE_UP_AFTER), n)
        self.assertIn("例外", got["reason"])
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], stopby.PR)


# 元 works/tests/test_blk_world.py の見本
_URL = "https://example.org/guide/tdd"
_PAGE = ("<html><body><p>Write a failing test first. A compile error is not a red test: add the smallest stub so the test runs"
           " and fails on the expected assertion.</p></body></html>").encode()
_GOOD = "A compile error is not a red test: add the smallest stub so the test runs and fails on the expected assertion."
_FINDINGS = [
    {"where": "src/red_check.py:40", "text": "赤の判定がコンパイルの要る対象で読み込みの失敗を赤に数える。読むだけの役を足して生のログから判じさせる"},
    {"where": "docs/guide.md", "text": "手引きの誤字（赤を緑と書いている）"},
]
_PROBLEM = "テストを先に書く開発で、まだ無い機能を呼ぶテストを、コンパイルの要る対象でどう赤にするか"
_CLASSES = {"classes": [
    {"finding": 1, "problem": _PROBLEM, "activity": "テストを先に書く開発", "proposed": "読むだけの役を足して生のログから判じさせる",
     "queries": ["test-first red phase compile error stub"]},
    {"finding": 2, "problem": "文書の誤字を直す", "activity": "文書の校正", "proposed": "", "queries": ["proofreading documentation typos practice"]},
]}


def _judged(finding=1, **kw):
    row = {"finding": finding, "practice": "読み込みの失敗は赤に数えず、最小の仮の実装で走らせてから期待違いの失敗を赤とする",
           "sources": [], "applies": "赤の判定の直し", "not_applies": "", "verdict": "differs",
           "challenge": "依頼は読む役を足す、定石は仮の実装で走らせる。読み込みの失敗が赤でない訳が無い限り定石を選ぶ"}
    row.update(kw)
    return row


class WorldStageCase(unittest.TestCase):
    """世界の解の段を judge/ の置き場で回す（元 test_blk_world の Scripts.test_web_off_run_reaches_exit と Verify・Judge の場面を、
    節の中身の関数で。網に出ない: 取り直しの口 get を差し替える）"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="judge-w-world-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.jdir = self.tmp / ja.JUDGE_DIR
        self.jdir.mkdir()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, _FINDINGS)
        ja.write_json(self.jdir / "purpose.json", {"purpose_text": "赤を言語に依らず判じる", "source": "request",
                                                   "known_weaknesses": [], "source_files": []})
        ja.write_json(self.jdir / "purpose-means.json", {"means": ["読むだけの役を足す"]})

    def intake(self):
        return ja.world_intake(self.jdir, self.tmp)

    def through_classes(self):
        self.assertTrue(self.intake()["due"])
        self.assertTrue(ja.world_accept(self.jdir, "world-classes", json.dumps(_CLASSES, ensure_ascii=False))["ok"])

    def test_intake_shows_request_purpose_and_means(self):
        """元 test_blk_world の test_purpose_means_are_shown: 言い直す役の指示書の本文に依頼の行・目的の文・依頼の解き方が載る。
        段の入力の目的の文は judge/world-purpose.json（元 line_edge._world_due）、worldblk の控えは judge/world/ の下"""
        got = self.intake()
        self.assertEqual((got["due"], got["reason"]), (True, ""))
        for want in ("赤を言語に依らず判じる", "読むだけの役を足す", _FINDINGS[0]["where"]):
            self.assertIn(want, got["prompt"])
        doc = json.loads((self.jdir / ja.WORLD_PURPOSE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(doc, {"purpose_text": "赤を言語に依らず判じる", "means": ["読むだけの役を足す"]})
        self.assertTrue((self.jdir / "world" / worldblk.INTAKE).is_file())
        self.assertTrue(json.loads((self.jdir / "world" / worldblk.INTAKE).read_text(encoding="utf-8"))["web"])

    def test_world_cut_turns_web_off(self):
        """始めの記録の features_cut に world が在れば web は off（元 entry.py の WORLD_FEATURE）"""
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"features_cut": ["world"]}))
        self.intake()
        self.assertFalse(json.loads((self.jdir / "world" / worldblk.INTAKE).read_text(encoding="utf-8"))["web"])

    def test_missing_purpose_is_not_due_and_finish_says_why(self):
        """元 line_edge._world_due: 目的の文が読めなければ回さない。出口は status failed で理由に目的の文のファイル"""
        (self.jdir / "purpose.json").unlink()
        got = self.intake()
        self.assertFalse(got["due"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "failed"))
        self.assertIn(ja.WORLD_PURPOSE_FILE, fin["reason"])

    def test_stopped_run_is_not_due(self):
        ja.write_stop(self.jdir, stopby.PURPOSE, "目的が決まらない")
        self.assertEqual(self.intake()["due"], False)
        self.assertEqual(ja.world_plan(self.jdir)["due"], False)

    def test_full_stage_writes_world_rows_and_state(self):
        """元 test_blk_world の test_web_row_carries_kept_sources・test_verify_keeps_fetched_excerpt_and_caps_total: 言い直し →
        類を決める → web の役（指示書の本文に excerpts の返し方）→ 抜き書きを取り直した本文で照らす（字のまま無い抜き書きは落ち、
        それを指す根拠も外れる）→ judge/world.jsonl と judge/world-state.json（worldmark.stage_rows が読む）"""
        self.through_classes()
        plan = ja.world_plan(self.jdir)
        self.assertTrue(plan["due"], plan)
        self.assertIn("excerpts に", plan["prompt"])
        self.assertNotIn(_FINDINGS[0]["text"], plan["prompt"])
        made_up = {"id": "x2", "url": _URL, "excerpt": "Nothing like this sentence is on that page at all."}
        reply = {"rows": [_judged(sources=["x1", "x2"]), _judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _URL, "excerpt": _GOOD}, made_up]}
        got = ja.world_accept(self.jdir, "world-judge", json.dumps(reply, ensure_ascii=False), get=lambda u: (200, _PAGE))
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "ok"), fin)
        rows = worldmark.rows(self.jdir / worldmark.WORLD_FILE)
        self.assertEqual([(r["basis"], [s["id"] for s in r["sources"]]) for r in rows], [("web", ["x1"]), ("knowledge", [])])
        self.assertEqual(rows[0]["where"], _FINDINGS[0]["where"])
        state = worldmark.read(self.jdir)
        self.assertEqual((state["status"], state["classes"], state["dropped"]), ("ok", 2, 1))
        self.assertEqual(worldmark.stage_rows(self.jdir), rows)

    def test_offline_run_still_finishes(self):
        """元 test_blk_world の test_verified_fields_offline_and_web_off: 網に届かない run は止めず、行は知識だけ（NOT_WEB）"""
        self.through_classes()
        ja.world_plan(self.jdir)

        def down(url):
            raise webget.FetchError("網に届かない")
        reply = {"rows": [_judged(sources=["x1"]), _judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _URL, "excerpt": _GOOD}]}
        self.assertTrue(ja.world_accept(self.jdir, "world-judge", json.dumps(reply), get=down)["ok"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual(fin["status"], "ok")
        self.assertIn(worldmark.NOT_WEB, fin["reason"])
        self.assertEqual({r["basis"] for r in worldmark.rows(self.jdir / worldmark.WORLD_FILE)}, {"knowledge"})

    def test_rejections_counted_and_give_up_does_not_stop(self):
        """元 test_blk_world の test_rejections_counted_by_rolekit・test_classes_given_up_skips_everything: JSON でない返答も
        拒否として数え、3 回目で done。web の役は起こさず、出口は status failed（言い直す役）で、run は止めない"""
        self.intake()
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = ja.world_accept(self.jdir, "world-classes", "not json" if n == 1 else '{"classes": []}')
            self.assertEqual((got["ok"], got["done"]), (False, n == rolekit.GIVE_UP_AFTER), n)
        self.assertEqual(len(rolekit.rejected(self.jdir, "world-classes")), 3)
        self.assertEqual(len(rolekit.rejected(self.jdir / "world", worldblk.CLASSES_ROLE)), 3)
        plan = ja.world_plan(self.jdir)
        self.assertFalse(plan["due"])
        self.assertIn("3 回とも", plan["reason"])
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "failed"))
        self.assertIn("言い直す役", fin["reason"])
        self.assertIsNone(ja.read_stop(self.jdir))
        self.assertEqual(worldmark.read(self.jdir)["status"], "failed")
        self.assertIsNone(worldmark.stage_rows(self.jdir))

    def test_judge_reject_names_the_problem(self):
        """元 test_blk_world の Judge.test_differs_needs_challenge・test_practice_with_target_identifier_is_refused"""
        self.through_classes()
        ja.world_plan(self.jdir)
        bad = {"rows": [_judged(challenge="短い"), _judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("challenge", ja.world_accept(self.jdir, "world-judge", json.dumps(bad))["reason"])
        bad = {"rows": [_judged(practice="src/red_check.py を直す"), _judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("src/red_check.py", ja.world_accept(self.jdir, "world-judge", json.dumps(bad))["reason"])


# ================================================================ 入口と返り
class StartViewCase(unittest.TestCase):
    def test_missing_fields_take_the_contract_defaults(self):
        """元 test_accept.TestIntake（始めの記録の欄が無い時の読み）。既定は docs/design.md の「judge の出力」の入力 start の決め"""
        view = ja.start_view({"input": {"request_file": "/r.json", "base": {"rev": "a" * 40}}})
        self.assertEqual(view["request_file"], "/r.json")
        self.assertEqual((view["policy_md"], view["features_cut"], view["spec"], view["answers"], view["gates"]),
                         ("", ["judge_verify"], False, [], ""))
        self.assertEqual(view["diff_base"], "a" * 40)
        self.assertEqual(ja.start_view(None)["request_file"], "")

    def test_explicit_fields_win(self):
        view = ja.start_view({"request_file": "/top.json", "features_cut": [], "input": {"spec": True, "request_file": "/r.json"}})
        self.assertEqual((view["request_file"], view["features_cut"], view["spec"]), ("/top.json", [], True))


class StopFileCase(unittest.TestCase):
    def test_first_stop_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ja.read_stop(tmp))
            ja.write_stop(tmp, ja.SPEC_STOP, "一つ目")
            ja.write_stop(tmp, ja.JUDGE_STOP, "二つ目")
            self.assertEqual(ja.read_stop(tmp), {"stop_reason": ja.SPEC_STOP, "reason": "一つ目"})

    def test_block_words_carry_the_machine_head(self):
        for word in (ja.JUDGE_STOP, ja.VERIFY_STOP, ja.SPEC_STOP, ja.MATERIAL_STOP, ja.REQUEST_STOP):
            self.assertTrue(word.startswith("works:"), word)


class VerdictPublicCase(unittest.TestCase):
    REPLY = {"verdict": "狭めている", "reason": "依頼は 2 件を名指すが目的は 1 件だけを書く",
             "findings": [{"text": "clamp の件が目的から落ちた", "cite": "request.json:2", "hits": 1}]}

    def test_verdict_places_purpose_review_sibling(self):
        """目的の監査の受けた返答は判定の指し札の隣の purpose-review.json に返答のまま置く（plan-review が名で開く）。
        監査が走らない・止めの道では {}。再審では最初の置き場から写る"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            jdir, rdir = root / "judge", root / "rejudge"
            jdir.mkdir()
            ja.write_json(jdir / "material-purpose-review.json",
                          {"role": "purpose-review", "materials": {}, "reply": self.REPLY})
            ja.verdict(jdir, rdir, root, "", lambda rel: rel)
            self.assertEqual(ja.read_json(jdir / "purpose-review.json"), self.REPLY)
            ja.verdict(jdir, rdir, root, "異議", lambda rel: rel)
            self.assertEqual(ja.read_json(rdir / "purpose-review.json"), self.REPLY)
        with tempfile.TemporaryDirectory() as tmp:
            jdir = pathlib.Path(tmp) / "judge"
            ja.verdict(jdir, pathlib.Path(tmp) / "rejudge", tmp, "", lambda rel: rel)
            self.assertEqual(ja.read_json(jdir / "purpose-review.json"), {})


class PublicFileReadersCase(unittest.TestCase):
    OWNERS = {"judge_accept.py", "premises.py", "judgeverify.py", "marks.py", "gatemarks.py", "purpose.py"}
    READERS = ("outcome", "runreport", "boardview", "planfile")

    def test_readers_take_the_names_from_the_owner(self):
        """判定の隣の公開のファイルの名（PUBLIC_FILES）を、持ち主の外の lib と script の節が字で書かない（持ち主が名を変えると、
        字で書いた読み手は黙って何も読まなくなる）"""
        import ast
        files = [p for p in LIB.glob("*.py") if p.name not in self.OWNERS] + sorted(LIB.parent.glob("workflows/*/scripts/*.py"))
        hits = [f"{p.relative_to(LIB.parent)}:{n.lineno} {n.value}" for p in files
                for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                if isinstance(n, ast.Constant) and n.value in ja.PUBLIC_FILES]
        self.assertEqual(hits, [])

    def test_readers_do_not_load_judge_accept(self):
        """名だけを読む読み手は名の軽い持ち主を読み、判定の受け付け（judge_accept と、それが読む数十のモジュール）を読み込まない"""
        for mod in self.READERS:
            with self.subTest(mod=mod):
                got = subprocess.run([sys.executable, "-c", f"import sys, {mod}; print('judge_accept' in sys.modules)"],
                                     cwd=LIB, capture_output=True, text=True, check=True)
                self.assertEqual(got.stdout.strip(), "False")
        prep = LIB.parent / "workflows" / "eyes" / "scripts" / "prep.py"
        self.assertNotIn("judge_accept", prep.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
