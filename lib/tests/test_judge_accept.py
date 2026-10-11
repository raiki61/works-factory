"""判定のブロックの受け付けと支度の芯（lib/judge_accept）の試験。

今の works の試験（test_blk_judge・test_blk_premises・test_blk_purpose・test_blk_material・test_blk_spec・test_rejudge・
test_judge_verify・test_structure_units・test_accept の TestJudge・TestIntake）が盤面の上で確かめていた場面を、値を渡す形に写した。
各試験の docstring に元の試験の名を書く。
"""
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

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


_A_SEED = LIB.parent / "tests" / "e2e" / "target-seed"
_A_MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
_A_CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
_A_REQUEST = [{"where": "stats.py", "text": "mean([1, 2, 3]) が 2 でなく 3 を返す。test_mean_of_three が赤"},
              {"where": "stats.py", "text": "clamp(15, 0, 10) が 10 でなく 0 を返す。test_clamp_above_range が赤"}]


def _a_unit(key, how_patterns, counts, total, label="block", disposition="do-now"):
    return {"key": key, "label": label, "disposition": disposition,
            "reason": f"事実: {key}。反証: 意図の取り違えを当たったが、関数名とテストが逆を期待する",
            "origin_analysis": "写し間違いの形",
            "why_chain": ["テストが境界の値を試していない"],
            "class_query": {"how": {"patterns": how_patterns, "fixed": True, "paths": ["stats.py"], "count": "lines"},
                            "counts": counts, "total": total}}


def _a_judge_ok():
    """元 works/tests/replies/judge_ok.json の形（今の works の良い判定の見本）"""
    return {
        "framing": "依頼の 2 件はどちらも stats.py の算術の取り違え",
        "one_shot": "mean の分母を len(xs) に、clamp の上限の枝の戻り値を hi に直す",
        "units": [_a_unit(_A_MEAN, ["(len(xs) - 1)"], "defects", 1), _a_unit(_A_CLAMP, ["return lo"], "population", 2)],
        "questions": [], "materials_missing": [], "carried_r1": [],
        "one_shot_closes": [_A_MEAN, _A_CLAMP],
        "precedents": [
            {"key": _A_MEAN, "problem": "数列の算術平均を求める", "source": "Python の statistics.mean の文書の節",
             "verdict": "adopt", "reason": "分母はデータ点の数 len(xs)"},
            {"key": _A_CLAMP, "problem": "値を下限と上限の間に収める", "source": "numpy.clip の文書の節",
             "verdict": "adopt", "reason": "上限を超えた値は上限に置き換える"}],
    }


class _AJudgeBase(unittest.TestCase):
    """種（tests/e2e/target-seed）を写して commit した使い捨ての対象リポジトリと、判定の置き場 J（入口が judge-tree.json と
    request.json と start.json を置いた後の姿）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = pathlib.Path(self._tmp.name)
        self.repo = tmp / "repo"
        self.base = gitkit.committed_copy(self.repo, _A_SEED)
        self.jdir = tmp / "art" / "judge"
        self.jdir.mkdir(parents=True)
        ja.write_json(self.jdir / ja.TREE_FILE, core_accept.tree_state(self.repo))
        ja.write_json(self.jdir / ja.REQUEST_FILE, _A_REQUEST)
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({}))

    def take(self, reply, **kw):
        return ja.take(self.jdir, reply, self.repo, **kw)

    def judgment(self):
        return json.loads((self.jdir / ja.JUDGMENT_FILE).read_text(encoding="utf-8"))


class RequestCase(unittest.TestCase):
    def test_request_rows_pass_the_add_type(self):
        """元 test_accept.TestIntake.test_intake_accepts_request（依頼の行が rules の add の型を通る）"""
        self.assertEqual(ja.check_request(_A_REQUEST, "持ち主"), {"ok": True, "reason": ""})
        self.assertEqual(ja.add(_A_REQUEST, "持ち主"), {"round": 1, "origin": "持ち主", "findings": _A_REQUEST})

    def test_unknown_key_is_rejected(self):
        """元 test_accept.TestIntake.test_intake_rejects_unknown_key"""
        rows = copy.deepcopy(_A_REQUEST)
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


class JudgeTakeCase(_AJudgeBase):
    def test_good_reply_is_written_as_judgment(self):
        """元 test_accept.TestJudge.test_judge_accepts_good_reply・test_blk_judge.ScriptCase.test_accept_good_and_bad_reply"""
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(got["judgment_file"], str(self.jdir / ja.JUDGMENT_FILE))
        self.assertEqual(sorted(got["open_units"]), sorted([_A_MEAN, _A_CLAMP]))
        doc = self.judgment()
        for k in ("units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes",
                  "precedents"):
            self.assertIn(k, doc)

    def test_label_outside_the_table_is_rejected(self):
        """元 rules の judge_output の「units[i] の label が不正」（検証器の表 LABELS の外。元の試験に同じ場面の物は無い）"""
        reply = _a_judge_ok()
        reply["units"][0]["label"] = "major"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("label", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_open_unit_why_chain_must_be_lines(self):
        """計画の「開いた単位の why_chain が足りないと拒む」。元の型（graph の p2.diagnose の schema）は why_chain を文の配列にし、
        元の rules に段の数の規則は無い。型の外（文でない段）を拒む"""
        reply = _a_judge_ok()
        reply["units"][0]["why_chain"] = [{"段": 1}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("why_chain", got["reason"])

    def test_open_unit_without_class_query_is_rejected(self):
        """元 rules の judge_output の「今の周に直す単位に class_query が無い」（元 test_blk_judge の判定の受け付けの場面）"""
        reply = _a_judge_ok()
        del reply["units"][1]["class_query"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("class_query", got["reason"])

    def test_class_query_examples_that_do_not_match_are_rejected(self):
        """元 test_blk_judge.QueryExamplesCase.test_hit_the_query_does_not_match_is_rejected・
        test_accept.TestJudge.test_judge_tests_query_examples_itself"""
        reply = _a_judge_ok()
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
        self.assertEqual(saved[_A_MEAN], {"hits": cq["hits"], "misses": cq["misses"]})

    def test_precedent_source_not_in_world_rows_is_rejected(self):
        """元 test_blk_judge.WorldSourceCase.test_take_refuses_unknown_world_source"""
        reply = _a_judge_ok()
        reply["precedents"][0]["source"] = "world:no-such-class"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("precedents の出どころが世界の解の行に無い", got["reason"])

    def test_question_without_kind_or_status_is_rejected(self):
        """元 rules の judge_output の問いの kind・status の照らし（検証器の QUESTION_KINDS・QUESTION_STATUS）"""
        reply = _a_judge_ok()
        reply["questions"] = [{"key": "q1", "reason": "決まらない"}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("kind", got["reason"])
        self.assertIn("status", got["reason"])
        reply["questions"] = [{"key": "q1", "kind": "fork", "status": "held", "reason": "決まらない", "origin": _A_MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("options", got["reason"])

    def test_judge_that_changed_the_tree_is_rejected(self):
        """元 test_accept.TestJudge.test_judge_rejects_dirty_tree・test_blk_judge.ScriptCase.test_accept_rejects_file_added_after_intake"""
        (self.repo / "extra.txt").write_text("読むだけの役が書いた\n", encoding="utf-8")
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("extra.txt", got["reason"])
        self.assertFalse((self.jdir / ja.JUDGMENT_FILE).exists())

    def test_judge_that_moved_head_is_rejected(self):
        """元 test_blk_judge.ScriptCase.test_accept_rejects_commit_after_intake"""
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        gitkit.git(self.repo, "add", "extra.txt")
        gitkit.git(self.repo, "commit", "-qm", "役が commit した")
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリー", got["reason"])

    def test_without_tree_record_the_tree_must_be_clean(self):
        """元 test_blk_judge.ScriptCase.test_check_judge_without_snapshot_needs_clean_tree"""
        (self.jdir / ja.TREE_FILE).unlink()
        self.assertIs(self.take(_a_judge_ok())["ok"], True)
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリーに変更が在る", got["reason"])

    def test_precedent_without_searched_is_rejected(self):
        """元 test_accept.TestJudge.test_judge_rejects_precedent_without_searched"""
        reply = _a_judge_ok()
        reply["precedents"][0].update(verdict="not_found", source="")
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("searched", got["reason"])

    def test_awaiting_material_needs_awaiting_question(self):
        """元 test_line_a の test_reply_without_awaiting_goes_back_to_judge（awaiting_human の素材に kind=awaiting の問いが無い）"""
        ja.write_json(self.jdir / "materials.json", {"parallel_pr": {"status": "awaiting_human", "reason": "gh が無い"}})
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("素材 'parallel_pr' が awaiting_human なのに台帳に kind=awaiting で無い", got["reason"])
        reply = _a_judge_ok()
        reply["questions"] = [{"key": "parallel_pr: 並行 PR を確かめる", "kind": "awaiting", "status": "held",
                               "reason": "gh が無く確かめられない", "origin": "parallel_pr"}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])

    def test_materials_missing_is_rejected(self):
        """元 rules の judge_output の materials_missing の拒否（graph の enforced_by）"""
        reply = _a_judge_ok()
        reply["materials_missing"] = ["hygiene"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("hygiene", got["reason"])

    def test_out_of_purpose_rows_are_checked_against_material_rows(self):
        """元 test_out_of_purpose（outpurpose.problems を盤面の材料の行に当てる）と judgetake.take の目的の外の行の扱い"""
        reply = _a_judge_ok()
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
        got = self.take(_a_judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("依頼の答え 'どれを採るか'", got["reason"])
        reply = _a_judge_ok()
        reply["answer_ties"] = [{"answer": "どれを採るか", "to": _A_MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        saved = json.loads((self.jdir / "answer-ties.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["rounds"]["1"], reply["answer_ties"])

    def test_carried_r1_tells_to_copy_the_where(self):
        """元 test_accept.TestJudge.test_judge_carried_r1_tells_to_copy_the_where（前の周の R1 が在る時だけ当たる道）"""
        reply = _a_judge_ok()
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
        reply = _a_judge_ok()
        reply["questions"] = [{"key": "岐路", "kind": "fork", "status": "held", "reason": "推し: A——安い",
                               "origin": _A_MEAN, "options": ["A: 安い", "B: 堅い"]}]
        reply["precedents"].append({"key": "岐路", "problem": "選び方の問題", "source": "文書の節", "verdict": "adopt",
                                    "reason": "当たった", "undecided_because": "先例が割れて決まらない（①）"})
        first = self.take(reply)
        self.assertIs(first["ok"], True, first["reason"])
        got = self.take(reply, prev_questions=[{"kind": "fork", "status": "held", "origin": _A_MEAN}])
        self.assertIs(got["ok"], False)
        self.assertIn("escalate に上げて", got["reason"])

    def test_declared_route_errors(self):
        """元 rules の _declared_route_errors（履歴の判定 p2.history の欄。このブロックの判定は当てない部品として持つ）"""
        out = {"units": [{"key": "u", "label": "block"}], "declared_routed": [{"key": "穴", "route": "to_unit", "unit_key": "v"}]}
        errs = ja._declared_route_errors(out, [{"key": "穴"}, {"key": "別の穴"}])
        self.assertTrue(any("unit_key が今の周の units に無い" in e for e in errs))
        self.assertTrue(any("'別の穴' を振り分けていない" in e for e in errs))


class JudgeAcceptCase(_AJudgeBase):
    def test_accept_parses_and_collect_builds_exit(self):
        """元 test_blk_judge.ScriptCase.test_collect_builds_exit・test_accept_good_and_bad_reply"""
        bad = ja.accept(self.jdir, "{not json", self.repo)
        self.assertIs(bad["ok"], False)
        self.assertIn("JSON", bad["reason"])
        got = ja.accept(self.jdir, json.dumps(_a_judge_ok(), ensure_ascii=False), self.repo)
        self.assertIs(got["ok"], True, got["reason"])
        out = ja.collect(self.jdir)
        self.assertEqual((out["ok"], out["need_fix"], sorted(out["open_units"])), (True, True, sorted([_A_MEAN, _A_CLAMP])))
        self.assertEqual(out["one_shot"], _a_judge_ok()["one_shot"])

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


class _AVerifyBase(_AJudgeBase):
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


class VerifyPrepCase(_AVerifyBase):
    def test_places_are_under_the_brief_dir(self):
        """置き場の名が judgeverify の BRIEF_DIR・TREE_FILE と合う（judgeverify から先に読んでも読み込める）"""
        self.assertEqual(ja.VERIFY_ANSWERS_DIR, f"{jv.BRIEF_DIR}/answers")
        self.assertEqual(ja.VERIFY_TREE_FILE, f"{jv.BRIEF_DIR}/{jv.TREE_FILE}")

    def test_one_open_unit_or_off_does_not_go_and_writes_not_run(self):
        """元 test_judge_verify.PrepCase.test_no_judgment_or_one_open_unit_does_not_go・test_verify_off_does_not_go_and_clears"""
        one = self.judged(_a_unit(_A_MEAN, ["x"], "defects", 1), _a_unit(_A_CLAMP, ["x"], "defects", 1, label="nit"))
        got = ja.prep_on(self.jdir, one, self.repo, True)
        self.assertEqual((got["go"], got["prompt_file"]), (False, ""))
        self.assertTrue(got["reason"])
        self.assertEqual(self.notes()["units"], [])
        self.assertEqual(self.notes()["synergy"]["state"], jv.UNVERIFIED)
        two = self.judged(_a_unit(_A_MEAN, ["x"], "defects", 1), _a_unit(_A_CLAMP, ["x"], "defects", 1))
        got = ja.prep_on(self.jdir, two, self.repo, False)
        self.assertIs(got["go"], False)
        self.assertIn("judge_verify", got["reason"])
        self.assertEqual(ja.prep_on(self.jdir, None, self.repo, True)["go"], False)

    def test_two_open_units_write_briefs_and_prompt(self):
        """元 test_judge_verify.PrepCase.test_two_open_units_write_briefs_and_prompt・test_prep_places_unverified_notes_first"""
        doc = self.judged(_a_unit(_A_MEAN, ["x"], "defects", 1), _a_unit(_A_CLAMP, ["x"], "defects", 1),
                          _a_unit("stats.py fmt: 桁", ["x"], "defects", 1, label="info", disposition="defer"))
        got = ja.prep_on(self.jdir, doc, self.repo, True)
        self.assertIs(got["go"], True)
        prompt = pathlib.Path(got["prompt_file"])
        self.assertTrue(str(prompt).startswith(str(self.jdir / jv.BRIEF_DIR)))
        names = sorted(p.name for p in prompt.parent.glob("*.md"))
        self.assertEqual(names, ["prompt.md", "synergy.md", "unit-1.md", "unit-2.md"])
        one = (prompt.parent / "unit-1.md").read_text(encoding="utf-8")
        self.assertIn(_A_MEAN, one)
        self.assertNotIn(_A_CLAMP, one)
        self.assertEqual(pathlib.Path(jv.answer_in(one)), self.jdir / ja.VERIFY_ANSWERS_DIR / "unit-1.json")
        self.assertIn(jv.SUBAGENT_TYPE, prompt.read_text(encoding="utf-8"))
        self.assertEqual([(u["key"], u["state"]) for u in self.notes()["units"]],
                         [(_A_MEAN, jv.UNVERIFIED), (_A_CLAMP, jv.UNVERIFIED)])


class VerifyMergeCase(_AVerifyBase):
    def setUp(self):
        super().setUp()
        doc = self.judged(_a_unit(_A_MEAN, ["x"], "defects", 1), _a_unit(_A_CLAMP, ["x"], "defects", 1))
        self.assertIs(ja.prep_on(self.jdir, doc, self.repo, True)["go"], True)

    def test_good_answers_are_merged_with_keys(self):
        """元 test_judge_verify.MergeCase.test_good_answers_and_synergy_are_merged_with_keys"""
        self.answer(1, _A_MEAN)
        self.answer(2, _A_CLAMP, verdict="not_root", real_root=f"単位 1（{_A_MEAN}）と同じ根")
        self.synergy({"why": "2 つの単位は同じ関数の群の取り違え", "duplicates": [{"units": [1, 2], "why": "同じ根の別の現れ"}],
                      "relations": [], "order": [{"first": 1, "then": 2, "why": "mean を先に直す"}]})
        self.assertEqual(ja.merge_on(self.jdir, self.repo), {"ok": True, "reason": ""})
        doc = self.notes()
        self.assertEqual([(u["key"], u["state"], u["verdict"]) for u in doc["units"]],
                         [(_A_MEAN, jv.CHECKED, "root"), (_A_CLAMP, jv.CHECKED, "not_root")])
        self.assertEqual(doc["synergy"]["duplicates"], [{"units": [_A_MEAN, _A_CLAMP], "why": "同じ根の別の現れ"}])
        self.assertIsNone(ja.read_stop(self.jdir))

    def test_verification_never_deletes_units(self):
        """元 test_judge_verify.MergeCase.test_missing_or_bad_answers_are_named_unverified（単位は消さない）"""
        self.answer(2, _A_CLAMP, verdict="not_root")
        self.synergy({"why": "短い"})
        ja.merge_on(self.jdir, self.repo)
        doc = self.notes()
        self.assertEqual([u["key"] for u in doc["units"]], [_A_MEAN, _A_CLAMP], "単位は消さない")
        self.assertTrue(any("答えのファイルが無い" in e for e in doc["units"][0]["errors"]))
        self.assertTrue(any("real_root" in e for e in doc["units"][1]["errors"]))
        self.assertEqual(doc["synergy"]["state"], jv.UNVERIFIED)

    def test_tree_moved_writes_verify_stop(self):
        """元 test_judge_verify.MergeCase.test_tree_moved_stops_board"""
        self.answer(1, _A_MEAN)
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


class _BCase(unittest.TestCase):
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

    def snap_tree(self):
        ja.write_json(self.jdir / ja.TREE_FILE, core_accept.tree_state(self.repo))

    def start(self, **over):
        doc = {"base_rev": self.head, "input": {"base": {"rev": self.head}, "diff": {"empty": False}, "requests": 1}}
        doc.update(over)
        return ja.start_view(doc)


# ================================================================ 前提の実測
class PremisesCase(_BCase):
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
class PurposeCase(_BCase):
    GOOD = {"purpose_text": "件数を正しく数える", "source": "②計画・タスク記述", "known_weaknesses": [],
            "source_files": ["README.md"], "means": ["数え直す関数を足す"]}

    def test_good_reply_writes_purpose_and_means(self):
        """元 test_blk_purpose の test_accept_good_and_bad_reply・test_purpose_means_split_to_mark"""
        self.snap_tree()
        got = ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)
        self.assertTrue(got["ok"], got)
        doc = ja.read_json(self.jdir / "purpose.json")
        self.assertNotIn("means", doc, "purpose.json は写しの型のまま（足し欄を外す）")
        self.assertEqual(doc["source_files"], ["README.md"])
        self.assertEqual(ja.read_json(self.jdir / "purpose-means.json"), {"means": ["数え直す関数を足す"]})

    def test_purpose_role_changed_the_tree_rejected(self):
        """元 test_blk_purpose の test_accept_rejects_tree_change_after_intake"""
        self.snap_tree()
        (self.repo / "note.txt").write_text("書いた\n", encoding="utf-8")
        got = ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])
        self.assertFalse((self.jdir / "purpose.json").exists())

    def test_source_files_outside_or_missing_rejected(self):
        """元 test_blk_purpose の test_accept_rejects_source_files_outside_tree・test_accept_rejects_missing_source_file_sample"""
        self.snap_tree()
        for bad in (["/etc/hosts"], ["./README.md"], ["nothing.md"]):
            with self.subTest(bad):
                got = ja.check_purpose({**self.GOOD, "source_files": bad}, self.jdir, self.repo)
                self.assertFalse(got["ok"], got)
                self.assertIn("source_files", got["reason"])

    def test_frozen_purpose_is_not_overwritten(self):
        """元 test_blk_purpose の test_accept_refuses_to_overwrite_frozen_purpose（p0.purpose の once）"""
        self.snap_tree()
        self.assertTrue(ja.check_purpose(dict(self.GOOD), self.jdir, self.repo)["ok"])
        got = ja.check_purpose({**self.GOOD, "purpose_text": "別の目的"}, self.jdir, self.repo)
        self.assertFalse(got["ok"])
        self.assertEqual(ja.read_json(self.jdir / "purpose.json")["purpose_text"], "件数を正しく数える")

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
class MaterialCase(_BCase):
    def view(self):
        self.snap_tree()
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

    def test_material_role_changed_the_tree_rejected(self):
        """元 test_blk_material.test_tree_change_rejects_and_names_peers"""
        self.view()
        (self.repo / "tmp.out").write_text("x\n", encoding="utf-8")
        got = ja.material_take(self.jdir, "provenance", {"material": {"status": "clean", "checked": "x"}, "claims": []}, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])

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
        self.snap_tree()
        ja.write_json(self.jdir / ja.START_FILE, self.start(input={"base": {"rev": self.head}, "diff": {"empty": True},
                                                                   "requests": 2}))
        got = ja.material_route(self.jdir, self.repo)
        self.assertFalse(got["local_review"])
        mats = ja.fill_materials(self.jdir)
        self.assertEqual(mats["local_review"]["status"], "not_applicable")
        self.assertIn("判定から入る run", mats["local_review"]["reason"])
        self.assertEqual(mats["prior_decisions"]["status"], "not_run")


# ================================================================ 判定役の材料
class BriefCase(_BCase):
    def test_brief_emits_the_seven_sections_in_order(self):
        """元 test_blk_judge（judgebrief.brief の節の並び・answers_section・carry.prior_section）"""
        self.snap_tree()
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
        prior = [{"where": "受け付け", "text": "前の拒否"}, {"where": carry.REDESIGN_WHERE, "text": "作り直し"}]
        path = ja.brief(self.jdir, self.repo, start, str(self.tmp / "REVIEW.md"), "", prior)
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

    def test_diagnose_prep_stops_after_material_give_up(self):
        """元 blk-material の collect（素材の役が 3 回とも拒まれたら盤面を止めた）。残りの素材で材料は組む"""
        self.snap_tree()
        ja.write_json(self.jdir / ja.START_FILE, self.start())
        route = ja.material_route(self.jdir, self.repo)
        self.assertTrue(route["hygiene"])
        for _ in range(3):
            ja.rolekit.with_done(self.jdir, "hygiene", {"ok": False, "reason": "形が違う"})
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "", [], str(self.tmp / "REVIEW.md"), "")
        self.assertFalse(got["go"])
        self.assertTrue(pathlib.Path(got["brief_file"]).is_file())
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], ja.MATERIAL_STOP)
        self.assertEqual(ja.read_json(self.jdir / "materials.json")["hygiene"]["status"], "not_run")

    def test_diagnose_prep_skips_on_objection_or_stop(self):
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "異議", [], "", "")
        self.assertFalse(got["go"])
        ja.write_stop(self.jdir, ja.JUDGE_STOP, "前で止めた")
        got = ja.diagnose_prep(self.jdir, self.repo, self.start(), "", [], "", "")
        self.assertFalse(got["go"])
        self.assertIn("前で止めた", got["reason"])


# ================================================================ 再審と仕様


# 元 works/tests/test_blk_spec.py の ACCEPT_TEST・write_reply・review_reply・revise_reply の写し（走らせるのは exit 1 の字面）
_C_ACCEPT_TEST = ("def test_mean_is_middle():\n"
                  "    # Given 1, 2, 3 の 3 つの数\n"
                  "    # When mean を呼ぶ\n"
                  "    # Then 2 を返す\n"
                  "    assert False\n")
_C_ACCEPT_RUN = "exit 1"
_C_FACE = {"key": "F1", "kind": "missing", "where": "R1",
           "why": "空の列の平均をどう扱うかが要件にも受け入れ条件にも無い（例外か 0 か）"}


def _c_write_reply(file="test_spec_accept.txt"):
    return {"requirements": [{"key": "R1", "text": "mean は 3 つの数の平均を返す"}],
            "acceptance": [{"key": "A1", "requirement": "R1", "file": file, "name": "test_mean_is_middle",
                            "run": _C_ACCEPT_RUN}],
            "out_of_scope": []}


def _c_review_reply(faces=True):
    if faces:
        return {"faces": [_C_FACE], "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}
    return {"faces": [], "faces_none": "要件 R1 と A1 の Then は依頼の 2 つ目と同じ値を見ている。範囲の外も無い",
            "reason": "要件 R1 と受け入れ条件 A1 を読み、境目の入力を確かめた"}


def _c_revise_reply():
    spec = _c_write_reply()
    spec["out_of_scope"] = ["空の列の平均（依頼に無い。今の実装のまま）"]
    return {"spec": spec, "handled": [{"key": "F1", "handled": "declared",
                                       "how": "空の列は依頼の範囲の外と決め、out_of_scope に理由つきで足した"}]}


class _CCase(unittest.TestCase):
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

    def write_tests(self, text=_C_ACCEPT_TEST, name="test_spec_accept.txt"):
        (self.repo / name).write_text(text, encoding="utf-8")

    def written(self):
        self.write_tests()
        got = ja.spec_take(self.jdir, "write", _c_write_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        return got


class SpecErrorsCase(_CCase):
    def test_acceptance_without_gwt_rejected(self):
        """元 test_blk_spec の書く役の拒否（写しの rules の _spec_errors: テストの中に Given/When/Then が要る）"""
        self.write_tests("def test_mean_is_middle():\n    assert False\n")
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_c_write_reply(), self.repo)
        self.assertIn("Given/When/Then", str(cm.exception))
        self.assertTrue(str(cm.exception).startswith("spec.write: "))

    def test_missing_test_file_and_name_rejected(self):
        """元 test_blk_spec の test_give_up_after_three（テストのファイルが無い）と、名前の無いファイル"""
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_c_write_reply(file="missing_test.txt"), self.repo)
        self.assertIn("missing_test.txt", str(cm.exception))
        self.write_tests(_C_ACCEPT_TEST.replace("test_mean_is_middle", "test_other"))
        with self.assertRaises(Reject) as cm:
            ja.spec_write_output(_c_write_reply(), self.repo)
        self.assertIn("name 'test_mean_is_middle'", str(cm.exception))

    def test_keys_unique_and_point_to_requirements(self):
        """元 写しの rules の _spec_errors（鍵が一意・受け入れ条件が要件を指す・要件は受け入れ条件を持つ）"""
        self.write_tests()
        spec = _c_write_reply()
        spec["requirements"].append({"key": "R1", "text": "同じ鍵の要件"})
        spec["requirements"].append({"key": "R2", "text": "受け入れ条件の無い要件"})
        spec["acceptance"].append({**spec["acceptance"][0], "key": "A2", "requirement": "R9"})
        errs = ja._spec_errors(spec, self.repo)
        self.assertTrue(any("requirements[1] の key が重複" in e for e in errs), errs)
        self.assertTrue(any("'R9' が requirements に無い" in e for e in errs), errs)
        self.assertTrue(any("要件 'R2' に受け入れ条件が無い" in e for e in errs), errs)
        self.write_tests()
        self.assertEqual(ja._spec_errors(_c_write_reply(), self.repo), [])

    def test_review_needs_faces_none(self):
        """元 写しの rules の spec_review_output（穴を挙げないなら faces_none が要る）"""
        ja.spec_review_output(_c_review_reply())
        ja.spec_review_output(_c_review_reply(faces=False))
        with self.assertRaises(Reject) as cm:
            ja.spec_review_output({"faces": [], "faces_none": "無い", "reason": "x" * 20})
        self.assertIn("faces_none", str(cm.exception))

    def test_revise_answers_each_face_once(self):
        """元 写しの rules の spec_revise_output（審査の穴に key ごとに 1 度だけ答える）"""
        self.write_tests()
        ja.spec_revise_output(_c_revise_reply(), _c_review_reply(), self.repo)
        bad = _c_revise_reply()
        bad["handled"] = [{"key": "F9", "handled": "absorbed", "how": "x" * 20}]
        with self.assertRaises(Reject) as cm:
            ja.spec_revise_output(bad, _c_review_reply(), self.repo)
        self.assertIn("'F9' は仕様の審査に無い", str(cm.exception))
        self.assertIn("'F1' に応答が無い", str(cm.exception))

    def test_revise_due_only_with_faces(self):
        """元 test_blk_spec の test_no_faces_skips_revise（写しの条件 spec_revise_due）"""
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_c_review_reply()))[0], True)
        self.assertEqual(ja.spec_revise_due(ja.spec_view(_c_review_reply(faces=False)))[0], False)


class SpecTakeCase(_CCase):
    def test_review_is_read_only(self):
        """元 test_blk_spec の test_review_is_read_only（審査の役が作業ツリーを変えたら拒む。元に戻せば通る）"""
        self.written()
        (self.repo / "note.txt").write_text("x\n", encoding="utf-8")
        got = ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])
        (self.repo / "note.txt").unlink()
        got = ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIs(got["revise"], True, "穴が開いた審査は直す輪を回す")
        self.assertEqual(ja.read_json(self.jdir / "spec-review.json"), _c_review_reply())

    def test_review_without_faces_skips_revise(self):
        """元 test_blk_spec の test_no_faces_skips_revise"""
        self.written()
        got = ja.spec_take(self.jdir, "review", _c_review_reply(faces=False), self.repo)
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
        ja.spec_take(self.jdir, "review", _c_review_reply(), self.repo)
        got = ja.spec_take(self.jdir, "revise", _c_revise_reply(), self.repo)
        self.assertTrue(got["ok"], got)
        self.assertEqual(ja.spec_now(self.jdir), _c_revise_reply()["spec"])


class SpecGateCase(_CCase):
    def asked(self, faces=True):
        self.written()
        self.assertTrue(ja.spec_take(self.jdir, "review", _c_review_reply(faces), self.repo)["ok"])
        if faces:
            self.assertTrue(ja.spec_take(self.jdir, "revise", _c_revise_reply(), self.repo)["ok"])
        got = ja.spec_ask(self.jdir, self.repo, "run-spec")
        self.assertIs(got["ask"], True, got)
        return got

    def test_ask_message(self):
        """元 test_blk_spec の test_pass_path の関所の文（run の字面・審査の穴と答え・答えの行）と test_blk_spec_gate"""
        got = self.asked()
        for part in (_C_ACCEPT_RUN, "spec.approve", "F1", "declared", "process.spec.approval",
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
        self.assertEqual(spec["out_of_scope"], _c_revise_reply()["spec"]["out_of_scope"], "直した版を固めた")
        rows = ja.read_json(self.jdir / "request.json")
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1]["text"].startswith(ja.SPEC_PROVENANCE), rows[1])
        self.assertIn("exit 1", rows[1]["measured"])
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


_C_UNIT_A = "src/a.py:f — 上限を超えた入力を黙って切る"
_C_UNIT_B = "src/b.py:g — 名前の誤り"


def _c_judgment():
    return {"units": [{"key": _C_UNIT_A, "label": "block", "reason": "切ると呼び手が気づけない", "why_chain": ["a", "b"]},
                      {"key": _C_UNIT_B, "label": "suggest", "disposition": "do-now", "reason": "読み手が迷う"}],
            "questions": [], "framing": "上限の扱い", "one_shot": "切らずに拒む", "materials_missing": [],
            "carried_r1": [], "one_shot_closes": [], "precedents": []}


def _c_rejudge_reply(verdict="一部採る", **over):
    units = [{"key": _C_UNIT_A, "label": "block", "reason": "異議の通り、切る前に拒む形に直す"},
             {"key": _C_UNIT_B, "label": "nit", "reason": "読み手は迷わない"}]
    return {"verdict": verdict, "new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた", "units": units,
            "reason": "上限の単位は採り、名前の単位は下げた", **over}


class RejudgeCase(_CCase):
    def prepared(self, objection=f"{_C_UNIT_A} の処方が誤り。12 行は切らずに拒んでいる"):
        ja.write_json(self.jdir / "judgment.json", _c_judgment())
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
        for part in ("12 行は切らずに拒んでいる", _C_UNIT_B, "上限の扱い", str(self.jdir / "judgment.json")):
            self.assertIn(part, brief)
        before = ja.read_json(self.rdir / "units-before.json")
        self.assertEqual([u["key"] for u in before["units"]], [_C_UNIT_A, _C_UNIT_B])
        self.assertEqual(before["numbered_keys"], [_C_UNIT_A, _C_UNIT_B])
        ja.rejudge_prep(self.jdir, self.rdir, "別の異議", self.repo)
        self.assertEqual(ja.read_json(self.rdir / "units-before.json"), before, "写しは 1 回目の前だけ")

    def test_verdict_word_outside_three_rejected(self):
        """元 test_rejudge の test_type_rejected（写しの型: verdict は 採る・退ける・一部採る）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(verdict="保留"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("型に合わない", got["reason"])
        got = ja.rejudge_take(self.jdir, self.rdir, {"verdict": "採る"}, self.repo)
        self.assertFalse(got["ok"])
        self.assertFalse((self.rdir / "judgment.json").exists())

    def test_empty_facts_rejected(self):
        """元 test_rejudge の test_empty_facts_rejected（写しの rules の rejudge_output）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(new_facts="確かめた"), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("new_facts", got["reason"])
        self.assertFalse((self.rdir / "rejudge-diff.json").exists())

    def test_tree_changed_rejected(self):
        """元 test_rejudge の test_tree_changed_rejected"""
        self.prepared()
        (self.repo / "a.txt").write_text("x\n", encoding="utf-8")
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(), self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])

    def test_accept_writes_judgment_and_diff(self):
        """元 test_rejudge の test_unnamed_change_recorded（下げた単位と名指されていない変化を前後の差に残す）"""
        self.prepared()
        got = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(), self.repo)
        self.assertEqual((got["ok"], got["verdict"]), (True, "一部採る"), got)
        self.assertEqual(ja.read_json(self.jdir / "judgment.json"), _c_judgment(), "1 回目の判定は上書きしない")
        now = ja.read_json(self.rdir / "judgment.json")
        self.assertEqual(set(now), set(_c_judgment()))
        self.assertEqual(now["units"][1], {"key": _C_UNIT_B, "label": "nit", "reason": "読み手は迷わない"})
        rows = ja.read_json(self.rdir / "rejudge-diff.json")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["pass"], row["node"], row["verdict"]), ("rejudge", "p2.rejudge", "一部採る"))
        self.assertEqual(row["unnamed_changed"], [_C_UNIT_B])
        named = {(c["key"], c["field"]): c["named"] for c in row["changed"] if c["kind"] == "changed"}
        self.assertEqual(named[(_C_UNIT_B, "label")], False)
        self.assertEqual(named[(_C_UNIT_A, "reason")], True)

    def test_lowered_block_named_in_diff_and_exit(self):
        """元 test_rejudge の test_collect_exit_has_lowered_and_objection（block から下げた単位）"""
        self.prepared()
        reply = _c_rejudge_reply(verdict="採る")
        reply["units"][0] = {**reply["units"][0], "label": "suggest", "disposition": "do-now"}
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        self.assertEqual(ja.read_json(self.rdir / "rejudge-diff.json")[0]["lowered"], [_C_UNIT_A])
        got = ja.rejudge_collect(self.rdir)
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["passes"], got["verdicts"], got["lowered"]), (1, ["採る"], [_C_UNIT_A]))
        self.assertIn(_C_UNIT_A, got["objection"])
        self.assertEqual(got["unsettled"], {"text": "", "settled": True})
        self.assertEqual(ja.read_json(self.rdir / "rejudge-exit.json"), got)
        self.assertEqual(ja.rejudge_verdict(self.rdir), "採る")

    def test_new_open_units(self):
        """元 test_rejudge の test_new_open_units"""
        self.prepared()
        reply = _c_rejudge_reply()
        reply["units"].append({"key": "src/c.py:h — 上限の抜け道がもう 1 つ", "label": "block"})
        self.assertTrue(ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)["ok"])
        got = ja.rejudge_collect(self.rdir)
        self.assertEqual(got["new_open_units"], ["src/c.py:h — 上限の抜け道がもう 1 つ"])
        self.assertFalse(got["unsettled"]["settled"], "一部採るは異議を降ろさない")

    def test_collect_after_give_up_stops(self):
        """元 test_rejudge の test_collect_names_last_rejection（3 回とも拒まれたら works:rejudge で止める）"""
        self.prepared()
        for _ in range(3):
            out = ja.rejudge_take(self.jdir, self.rdir, _c_rejudge_reply(new_facts="確かめた"), self.repo)
            rolekit.with_done(self.rdir, "rejudge", out)
        got = ja.rejudge_collect(self.rdir)
        self.assertFalse(got["ok"])
        self.assertIn("3 回", got["reason"])
        self.assertEqual(ja.read_stop(self.rdir)["stop_reason"], stopby.REJUDGE)
        self.assertIsNone(ja.rejudge_verdict(self.rdir))

    def test_class_query_examples_tried(self):
        """元 test_blk_rejudge の test_rejudge_defects_query_matching_fixed_form_is_rejected（例が問いと合わなければ拒む）"""
        self.prepared()
        reply = _c_rejudge_reply()
        reply["units"][0]["class_query"] = {
            "how": {"patterns": ["truncate("], "fixed": True, "paths": ["src"], "count": "lines"},
            "counts": "defects", "total": 1, "hits": ["x = truncate(v)"], "misses": ["x = reject_over(truncate(v))"]}
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("class_query", got["reason"])
        reply["units"][0]["class_query"]["misses"] = ["x = reject_over(v)"]
        got = ja.rejudge_take(self.jdir, self.rdir, reply, self.repo)
        self.assertTrue(got["ok"], got)
        self.assertIn(_C_UNIT_A, ja.read_json(self.rdir / "query-examples.json"))


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

    def test_parse_gate(self):
        self.assertIsNone(specblk.parse_gate("null"))
        self.assertIsNone(specblk.parse_gate(""))
        self.assertEqual(specblk.parse_gate('{"decision": "reject"}'), {"decision": "reject", "text": ""})
        with self.assertRaises(rolekit.BoardGap):
            specblk.parse_gate("[1]")
        self.assertEqual(specblk.snapshot_name("spec.review"), "spec-snapshot-spec.review.json")


# ================================================================ 並行 PR と世界の解


_W_GITHUB = "git@github.com:o/r.git"
_W_SEED = "def mean(xs):\n    return sum(xs)\n"
# 元 works/tests/replies/pr_ok.json・pr_no_conflicts.json・pr_handed_over.json
_W_PR_OK = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている（gh pr diff 7 -R o/r の hunk @@ -1,3 +1,4 @@）。申し送りの下書きを conflicts[0].note に書いた（投稿していない）"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": False,
                   "note": "PR #7 の担当へ: この run（判定から入る run）も stats.py の mean を直します。#7 の hunk @@ -1,3 +1,4 @@ と同じ行です。どちらを先に入れるか決めてください。"}],
    "excluded": [{"pr": "7", "file": "stats.py", "start": 1, "end": 2,
                  "why": "PR #7 の hunk @@ -1,3 +1,4 @@ が mean の同じ行を書き換える（この run の依頼 1 件目と同じ所）"}],
}
_W_PR_NO_CONFLICTS = {
    "material": {"status": "clean", "checked": "gh -R o/r で open な PR 2 件を引き、自分の PR（headRefOid が HEAD）を除いて、変更ファイルの集合と交差した PR #7 の差分を読んだ。同じファイルの hunk はこの run の変更とぶつからない（衝突 0 件・打ち切りなし）"},
    "repo": "o/r", "listed": 2, "truncated": False, "conflicts": [], "excluded": [],
}
_W_PR_HANDED_OVER = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている。担当の PR に申し送った"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": True, "note": "gh pr comment 7 -R o/r で申し送った"}],
    "excluded": [],
}


def _w_fake_gh(prs, files):
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


def _w_never(*args):
    raise AssertionError(f"gh を呼んではいけない: {args}")


class _WPrBase(unittest.TestCase):
    """並行 PR の場面（元 test_blk_pr の PrCase）: 判定から入る run の対象（stats.py を持つ git の木）と judge/ の置き場"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="judge-w-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo, self.jdir = self.tmp / "repo", self.tmp / "art" / ja.JUDGE_DIR
        self.repo.mkdir()
        self.jdir.mkdir(parents=True)
        gitkit.git(self.repo, "init", "-q")
        (self.repo / "stats.py").write_text(_W_SEED, encoding="utf-8")
        gitkit.git(self.repo, "add", "-A")
        gitkit.git(self.repo, "commit", "-q", "-m", "seed")
        gitkit.git(self.repo, "remote", "add", "origin", _W_GITHUB)
        self.head = gitkit.git(self.repo, "rev-parse", "HEAD").strip()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({"base_rev": self.head, "input": {"base": {"rev": self.head}}}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, [{"where": "stats.py:2", "text": "mean が数で割っていない"}])

    def scan(self, gh=None, which=lambda name: "/bin/gh"):
        return ja.pr_scan(self.jdir, self.repo, gh=gh or _w_never, which=which)

    def material(self):
        return json.loads((self.jdir / ja.MATERIAL_PR_FILE).read_text(encoding="utf-8"))

    def snap(self):
        """入口が置く作業ツリーの写し（judge/judge-tree.json。元 prcheck.snapshot の pr-snapshot.json）"""
        ja.write_json(self.jdir / ja.TREE_FILE, core_accept.tree_state(self.repo))


class WPrScanCase(_WPrBase):
    def test_no_crossing_is_decided_by_machine(self):
        """元 test_blk_pr の test_helper_by_engine_when_no_crossing: 交差 0 → 機械で済む（役は要らない）。素材は clean、
        自分の PR（headRefOid が HEAD）は外す。外す hunk の一覧は空で置く"""
        gh = _w_fake_gh([{"number": 3, "headRefName": "me", "headRefOid": self.head},
                         {"number": 7, "headRefName": "x", "headRefOid": "f" * 40}], {"7": ["other.py"], "3": ["stats.py"]})
        got = self.scan(gh)
        self.assertEqual((got["go"], got["go_role"]), (True, False), got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")
        self.assertEqual(self.material()["role"], "pr-check")
        self.assertNotIn(("pr", "view", "3", "-R", "o/r", "--json", "files"), gh.calls, "自分の PR は見ない")
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["excluded"]), ("p0.parallel_pr", []))
        self.assertTrue(all("-R" in c for c in gh.calls), "gh は必ず -R で呼ぶ")

    def test_crossing_falls_back_to_role(self):
        """元 test_blk_pr の test_fallback_on_crossing_sets_role_needed: 交差 1 件 → 役へ（go_role）。渡し物に理由と
        交差を取る集合（差分が空なので依頼の where が名指す追跡中のパス）。素材は役が返すまで書かない"""
        got = self.scan(_w_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual((got["go"], got["go_role"]), (True, True))
        self.assertIn("交差", got["reason"])
        brief = json.loads((self.jdir / "pr-brief.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["node"], brief["changed_files"], brief["fallback"]), ("p0.parallel_pr", ["stats.py"], got["reason"]))
        self.assertEqual(brief["request_wheres"], ["stats.py:2"])
        self.assertFalse((self.jdir / ja.MATERIAL_PR_FILE).exists())

    def test_diff_files_win_over_request_wheres(self):
        """元 review-loop.py の _pr_files: 差分の根から変わったファイルが在れば、それが交差を取る集合（依頼の where は使わない）"""
        (self.repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        got = self.scan(_w_fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
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
        self.scan(_w_fake_gh(many, {}))
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
        self.assertEqual(ja._github_repo(self.repo), ("o/r", None))


class WPrAcceptCase(_WPrBase):
    def setUp(self):
        super().setUp()
        self.snap()

    def accept(self, reply):
        return ja.pr_accept(self.jdir, json.dumps(reply, ensure_ascii=False), self.repo)

    def test_check_no_post(self):
        """元 test_blk_pr の test_check_no_post"""
        self.assertEqual(ja.check_no_post(_W_PR_HANDED_OVER), ["7"])
        self.assertEqual(ja.check_no_post(_W_PR_OK), [])
        self.assertEqual(ja.check_no_post(_W_PR_NO_CONFLICTS), [])
        two = json.loads(json.dumps(_W_PR_OK))
        two["conflicts"] += [{"pr": "9", "files": ["a"], "handed_over": True}, {"pr": "11", "files": ["b"], "handed_over": True}]
        self.assertEqual(ja.check_no_post(two), ["9", "11"])
        self.assertEqual(ja.check_no_post({"conflicts": "x"}), [])

    def test_handed_over_true_rejected(self):
        """元 test_blk_pr の test_handed_over_true_rejected: handed_over true が 1 件 → ok false、文に pr と「投稿しない」。何も書かない"""
        got = self.accept(_W_PR_HANDED_OVER)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("投稿しない", got["reason"])
        self.assertTrue(got["reason"].endswith(": 7"), got["reason"])
        self.assertFalse((self.jdir / "pr-excluded.json").exists())

    def test_handover_draft_accepted_with_anchor(self):
        """元 test_blk_pr の test_handover_draft_accepted・test_excluded_hunks_leave_scope・test_excluded_carries_content_anchor:
        通れば外す hunk が中身と sha256 と写しの HEAD つきで pr-excluded.json に、申し送りの下書きが pr-downgrades.json に、
        素材（excluded を外した返答）が material-pr-check.json に置かれる"""
        got = self.accept(_W_PR_OK)
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["head"]), ("p0.parallel_pr", self.head))
        h = doc["excluded"][0]
        self.assertEqual({k: h[k] for k in ("pr", "file", "start", "end", "why")}, _W_PR_OK["excluded"][0])
        self.assertEqual(h["text"], _W_SEED)
        self.assertEqual(h["sha256"], hashlib.sha256(_W_SEED.encode("utf-8")).hexdigest())
        drafts = json.loads((self.jdir / ja.PR_DOWNGRADES_FILE).read_text(encoding="utf-8"))
        self.assertEqual(drafts, [{"pr": "7", "files": ["stats.py"], "note": _W_PR_OK["conflicts"][0]["note"]}])
        mat = self.material()
        self.assertEqual(mat["materials"]["parallel_pr"]["status"], "found")
        self.assertNotIn("excluded", mat["reply"])

    def test_no_conflicts_reply_accepted(self):
        """元 test_blk_pr の test_no_conflicts_reply_accepted"""
        self.assertTrue(self.accept(_W_PR_NO_CONFLICTS)["ok"])
        doc = json.loads((self.jdir / "pr-excluded.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["excluded"], [])

    def test_excluded_checked(self):
        """元 test_blk_pr の test_excluded_checked: 外す hunk の誤り → ok false。何も書かない"""
        hunk = _W_PR_OK["excluded"][0]
        cases = {"excluded が無い": {k: v for k, v in _W_PR_OK.items() if k != "excluded"},
                 "conflicts に無い": dict(_W_PR_OK, excluded=[dict(hunk, pr="99")]),
                 "交差したファイル": dict(_W_PR_OK, excluded=[dict(hunk, file="other.py")]),
                 "より大きい": dict(_W_PR_OK, excluded=[dict(hunk, start=2, end=1)]),
                 "行の数 2 を超える": dict(_W_PR_OK, excluded=[dict(hunk, end=3)]),
                 "note": dict(_W_PR_OK, conflicts=[{k: v for k, v in _W_PR_OK["conflicts"][0].items() if k != "note"}]),
                 "型": dict(_W_PR_OK, excluded=[dict(hunk, start=0)])}
        for word, bad in cases.items():
            got = ja.prcheck_take(self.jdir, bad, self.repo)
            self.assertFalse(got["ok"], word)
            self.assertIn(word, got["reason"], word)
            self.assertFalse((self.jdir / "pr-excluded.json").exists(), word)

    def test_fallback_role_reads_only(self):
        """元 test_blk_pr の test_fallback_role_reads_only・test_head_move_rejected: 入口の写しの後に作業ツリーや HEAD を
        変えて受け付け → ok false、文に「作業ツリーを変えた」"""
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = ja.prcheck_take(self.jdir, _W_PR_OK, self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])
        (self.repo / "stats.py").write_text(_W_SEED, encoding="utf-8")
        gitkit.git(self.repo, "checkout", "-q", "-b", "other")
        self.assertIn("ref", ja.prcheck_take(self.jdir, _W_PR_OK, self.repo)["reason"])

    def test_malformed_reply_bounced_not_crashed(self):
        """元 test_blk_pr の test_malformed_reply_bounced_not_crashed・test_accept_script_unreadable_reply: JSON でない・
        素材の形が違う返答 → 例外でなく ok false"""
        got = ja.pr_accept(self.jdir, "not json", self.repo)
        self.assertFalse(got["ok"])
        self.assertIn("JSON", got["reason"])
        self.assertIn("型", ja.prcheck_take(self.jdir, dict(_W_PR_OK, material={"status": "maybe"}), self.repo)["reason"])

    def test_third_rejection_gives_up_and_stops(self):
        """元 blk-pr/scripts/collect.py の gave_up（rolekit.gave_up。by は stopby.PR）: 3 回目の拒否で done、止めの控えを置く"""
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = self.accept(_W_PR_HANDED_OVER)
            self.assertEqual(got["done"], n == rolekit.GIVE_UP_AFTER, n)
        self.assertEqual(len(json.loads((self.jdir / "rejects-pr-check.json").read_text(encoding="utf-8"))), 3)
        self.assertEqual(ja.read_stop(self.jdir)["stop_reason"], stopby.PR)


# 元 works/tests/test_blk_world.py の見本
_W_URL = "https://example.org/guide/tdd"
_W_PAGE = ("<html><body><p>Write a failing test first. A compile error is not a red test: add the smallest stub so the test runs"
           " and fails on the expected assertion.</p></body></html>").encode()
_W_GOOD = "A compile error is not a red test: add the smallest stub so the test runs and fails on the expected assertion."
_W_FINDINGS = [
    {"where": "src/red_check.py:40", "text": "赤の判定がコンパイルの要る対象で読み込みの失敗を赤に数える。読むだけの役を足して生のログから判じさせる"},
    {"where": "docs/guide.md", "text": "手引きの誤字（赤を緑と書いている）"},
]
_W_PROBLEM = "テストを先に書く開発で、まだ無い機能を呼ぶテストを、コンパイルの要る対象でどう赤にするか"
_W_CLASSES = {"classes": [
    {"finding": 1, "problem": _W_PROBLEM, "activity": "テストを先に書く開発", "proposed": "読むだけの役を足して生のログから判じさせる",
     "queries": ["test-first red phase compile error stub"]},
    {"finding": 2, "problem": "文書の誤字を直す", "activity": "文書の校正", "proposed": "", "queries": ["proofreading documentation typos practice"]},
]}


def _w_judged(finding=1, **kw):
    row = {"finding": finding, "practice": "読み込みの失敗は赤に数えず、最小の仮の実装で走らせてから期待違いの失敗を赤とする",
           "sources": [], "applies": "赤の判定の直し", "not_applies": "", "verdict": "differs",
           "challenge": "依頼は読む役を足す、定石は仮の実装で走らせる。読み込みの失敗が赤でない訳が無い限り定石を選ぶ"}
    row.update(kw)
    return row


class WWorldCase(unittest.TestCase):
    """世界の解の段を judge/ の置き場で回す（元 test_blk_world の Scripts.test_web_off_run_reaches_exit と Verify・Judge の場面を、
    節の中身の関数で。網に出ない: 取り直しの口 get を差し替える）"""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="judge-w-world-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.jdir = self.tmp / ja.JUDGE_DIR
        self.jdir.mkdir()
        ja.write_json(self.jdir / ja.START_FILE, ja.start_view({}))
        ja.write_json(self.jdir / ja.REQUEST_FILE, _W_FINDINGS)
        ja.write_json(self.jdir / "purpose.json", {"purpose_text": "赤を言語に依らず判じる", "source": "request",
                                                   "known_weaknesses": [], "source_files": []})
        ja.write_json(self.jdir / "purpose-means.json", {"means": ["読むだけの役を足す"]})

    def intake(self):
        return ja.world_intake(self.jdir, self.tmp)

    def through_classes(self):
        self.assertTrue(self.intake()["due"])
        self.assertTrue(ja.world_accept(self.jdir, "world-classes", json.dumps(_W_CLASSES, ensure_ascii=False))["ok"])

    def test_intake_shows_request_purpose_and_means(self):
        """元 test_blk_world の test_purpose_means_are_shown: 言い直す役の指示書の本文に依頼の行・目的の文・依頼の解き方が載る。
        段の入力の目的の文は judge/world-purpose.json（元 line_edge._world_due）、worldblk の控えは judge/world/ の下"""
        got = self.intake()
        self.assertEqual((got["due"], got["reason"]), (True, ""))
        for want in ("赤を言語に依らず判じる", "読むだけの役を足す", _W_FINDINGS[0]["where"]):
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
        self.assertNotIn(_W_FINDINGS[0]["text"], plan["prompt"])
        made_up = {"id": "x2", "url": _W_URL, "excerpt": "Nothing like this sentence is on that page at all."}
        reply = {"rows": [_w_judged(sources=["x1", "x2"]), _w_judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _W_URL, "excerpt": _W_GOOD}, made_up]}
        got = ja.world_accept(self.jdir, "world-judge", json.dumps(reply, ensure_ascii=False), get=lambda u: (200, _W_PAGE))
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        fin = ja.world_finish(self.jdir)
        self.assertEqual((fin["ok"], fin["status"]), (True, "ok"), fin)
        rows = worldmark.rows(self.jdir / worldmark.WORLD_FILE)
        self.assertEqual([(r["basis"], [s["id"] for s in r["sources"]]) for r in rows], [("web", ["x1"]), ("knowledge", [])])
        self.assertEqual(rows[0]["where"], _W_FINDINGS[0]["where"])
        state = worldmark.read(self.jdir)
        self.assertEqual((state["status"], state["classes"], state["dropped"]), ("ok", 2, 1))
        self.assertEqual(worldmark.stage_rows(self.jdir), rows)

    def test_offline_run_still_finishes(self):
        """元 test_blk_world の test_verified_fields_offline_and_web_off: 網に届かない run は止めず、行は知識だけ（NOT_WEB）"""
        self.through_classes()
        ja.world_plan(self.jdir)

        def down(url):
            raise webget.FetchError("網に届かない")
        reply = {"rows": [_w_judged(sources=["x1"]), _w_judged(2, verdict="none", challenge="")],
                 "excerpts": [{"id": "x1", "url": _W_URL, "excerpt": _W_GOOD}]}
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
        bad = {"rows": [_w_judged(challenge="短い"), _w_judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("challenge", ja.world_accept(self.jdir, "world-judge", json.dumps(bad))["reason"])
        bad = {"rows": [_w_judged(practice="src/red_check.py を直す"), _w_judged(2, verdict="none", challenge="")], "excerpts": []}
        self.assertIn("src/red_check.py", ja.world_accept(self.jdir, "world-judge", json.dumps(bad))["reason"])


# ================================================================ 入口と返り
class StartViewCase(unittest.TestCase):
    def test_missing_fields_take_the_contract_defaults(self):
        """元 test_accept.TestIntake（始めの記録の欄が無い時の読み）。既定は docs/design.md の「judge の返り」の入力 start の決め"""
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


if __name__ == "__main__":
    unittest.main()
