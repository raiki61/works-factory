"""判定役の受け付け（src/judge.py）の試験。写す元は lib/tests/test_judge_accept.py の JudgeTakeCase・StructureUnitsCase と
tests/workflows/test_judge.py の受け付けの場面。受け付けの決まりは docs/design/diagnose.md の 2.8。

keep-essence の 7（class_query の件数を機械が数え直す）は test_engine_recounts_the_class_query_total・
test_defects_query_needs_misses_and_must_not_match_the_fixed_form・test_class_query_examples_that_do_not_match_are_rejected、
12（先行例の出どころを世界の解の行に照らす）は test_precedent_source_not_in_world_rows_is_rejected で守る。
"""
import copy
import json
import pathlib
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.diagnose import support
from tests.blocks.diagnose.support import CLAMP, MEAN, judge_ok, unit


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.mod = support.modules()
        self.judge, self.files = self.mod["judge"], self.mod["files"]
        import materialkit
        self.materialkit = materialkit
        self.repo, self.place = self.run.repo, self.run.artifacts
        materialkit.snap_tree(self.place, self.repo)
        self.state = {"world_rows": [], "answers": [], "redesign": [], "recorded": [], "materials": {}, "material_rows": []}

    def take(self, reply, **kw):
        return self.judge.take(self.place, reply, self.repo, **{**self.state, **kw})

    def judgment(self):
        return json.loads((self.place / "judgment.json").read_text(encoding="utf-8"))

    def saved(self, name):
        return json.loads((self.place / name).read_text(encoding="utf-8"))


class TablesCase(_Base):
    def test_is_open_follows_label_and_disposition(self):
        is_open = self.judge.is_open
        self.assertTrue(is_open({"label": "block"}))
        self.assertTrue(is_open({"label": "suggest", "disposition": "do-now"}))
        self.assertFalse(is_open({"label": "suggest", "disposition": "defer"}))
        self.assertFalse(is_open({"label": "nit"}))

    def test_tables_keep_the_words(self):
        self.assertEqual(self.judge.LABELS, ("block", "suggest", "nit", "question", "info"))
        self.assertEqual(set(self.judge.QUESTION_KINDS),
                         {"fork", "split", "rule", "stuck", "thrash", "premise", "unverifiable", "awaiting", "field"})
        self.assertEqual(self.judge.QUESTION_KINDS["fork"].fields, ("options",))
        self.assertEqual({k: v.domain for k, v in self.judge.QUESTION_KINDS.items()},
                         {"fork": "unit", "split": "unit", "rule": "unit", "stuck": "unit", "thrash": "none", "premise": "review",
                          "unverifiable": "review", "awaiting": "material", "field": "none"})
        self.assertEqual(self.judge.QUESTION_STATUS, {"held": (), "decided": ("resolution",), "resolved": ("resolution",), "escalate": ()})
        self.assertEqual(self.judge.NO_OPEN_ORIGIN, ("split", "rule"))


class JudgeTakeCase(_Base):
    def test_good_reply_is_written_as_judgment(self):
        got = self.take(judge_ok())
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(got["judgment_file"], str(self.place / "judgment.json"))
        self.assertEqual(sorted(got["open_units"]), sorted([MEAN, CLAMP]))
        doc = self.judgment()
        for k in ("units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes", "precedents"):
            self.assertIn(k, doc)

    def test_reply_that_is_not_an_object_is_rejected(self):
        got = self.take([1])
        self.assertIs(got["ok"], False)
        self.assertIn("JSON のオブジェクトでない", got["reason"])

    def test_label_outside_the_table_is_rejected(self):
        reply = judge_ok()
        reply["units"][0]["label"] = "major"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("label", got["reason"])
        self.assertFalse((self.place / "judgment.json").exists())

    def test_open_unit_without_class_query_is_rejected(self):
        reply = judge_ok()
        del reply["units"][1]["class_query"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("class_query", got["reason"])

    def test_class_query_examples_that_do_not_match_are_rejected(self):
        reply = judge_ok()
        cq = reply["units"][0]["class_query"]
        cq["hits"], cq["misses"] = ["    return sum(xs) / len(xs)"], ["    return 0"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("class_query の例が問いと合わない", got["reason"])
        cq["hits"], cq["misses"] = ["    return sum(xs) / (len(xs) - 1)"], ["    return sum(xs) / len(xs)"]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(self.judgment()["units"][0]["class_query"]["misses"], cq["misses"], "例は judgment に戻る")
        self.assertEqual(self.saved("query-examples.json")[MEAN], {"hits": cq["hits"], "misses": cq["misses"]})

    def test_precedent_source_not_in_world_rows_is_rejected(self):
        reply = judge_ok()
        reply["precedents"][0]["source"] = "world:no-such-class"
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("precedents の出どころが世界の解の行に無い", got["reason"])
        got = self.take(reply, world_rows=[{"class_id": "no-such-class"}])
        self.assertIs(got["ok"], True, got["reason"])

    def test_world_ref_problems_read_rows(self):
        reply = {"precedents": [{"source": "world:w-1"}, {"source": "文書の節"}, {"source": "world:w-2（抜き書き）"}]}
        self.assertEqual(self.judge.world_ref_problems(reply, [{"class_id": "w-1"}]), ["world:w-2 が実在の行を指さない"])
        self.assertEqual(self.judge.world_ref_problems(reply, []), ["world:w-1 が実在の行を指さない", "world:w-2 が実在の行を指さない"])

    def test_fork_question_without_options_is_rejected(self):
        reply = judge_ok()
        reply["questions"] = [{"key": "q1", "kind": "fork", "status": "held", "reason": "決まらない", "origin": MEAN}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("options", got["reason"])

    def test_judge_that_changed_the_tree_is_rejected(self):
        (self.repo / "extra.txt").write_text("読むだけの役が書いた\n", encoding="utf-8")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("判定役を起こした後から作業ツリーが変わった", got["reason"])
        self.assertFalse((self.place / "judgment.json").exists())

    def test_judge_that_moved_head_is_rejected(self):
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        git(self.repo, "add", "extra.txt")
        git(self.repo, "commit", "-qm", "役が commit した")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリー", got["reason"])

    def test_without_tree_record_the_tree_must_be_clean(self):
        (self.place / "tree.json").unlink()
        self.assertIs(self.take(judge_ok())["ok"], True)
        (self.repo / "extra.txt").write_text("x\n", encoding="utf-8")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("作業ツリーに変更が在る", got["reason"])

    def test_precedent_without_searched_is_rejected(self):
        reply = judge_ok()
        reply["precedents"][0].update(verdict="not_found", source="")
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("searched", got["reason"])

    def test_awaiting_material_needs_awaiting_question(self):
        materials = {"parallel_pr": {"status": "awaiting_human", "reason": "gh が無い"}}
        got = self.take(judge_ok(), materials=materials)
        self.assertIs(got["ok"], False)
        self.assertIn("素材 'parallel_pr' が awaiting_human なのに台帳に kind=awaiting で無い", got["reason"])
        reply = judge_ok()
        reply["questions"] = [{"key": "parallel_pr: 並行 PR を確かめる", "kind": "awaiting", "status": "held",
                               "reason": "gh が無く確かめられない", "origin": "parallel_pr"}]
        got = self.take(reply, materials=materials)
        self.assertIs(got["ok"], True, got["reason"])

    def test_awaiting_question_origin_must_be_awaiting_human_now(self):
        reply = judge_ok()
        reply["questions"] = [{"key": "parallel_pr: 並行 PR を確かめる", "kind": "awaiting", "status": "held",
                               "reason": "gh が無く確かめられない", "origin": "parallel_pr"}]
        got = self.take(reply, materials={"parallel_pr": {"status": "clean", "checked": "gh pr list"}})
        self.assertIs(got["ok"], False)
        self.assertIn("awaiting の出どころは今 awaiting_human の素材だけ", got["reason"])

    def test_materials_missing_is_rejected(self):
        reply = judge_ok()
        reply["materials_missing"] = ["hygiene"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("hygiene", got["reason"])

    def test_out_of_purpose_rows_are_checked_against_material_rows(self):
        reply = judge_ok()
        reply["out_of_purpose"] = [{"source": "局所レビュー", "where": "no-such.py", "why_outside": "凍結した目的の外の所見"}]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("out_of_purpose", got["reason"])
        rows = [{"where": "test_stats.py", "text": "使わない import が残る", "from": "p1.hygiene"}]
        reply["out_of_purpose"] = [{"source": "衛生", "where": "test_stats.py", "why_outside": "凍結した目的の外の衛生の所見"}]
        got = self.take(reply, material_rows=rows)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(self.judgment()["out_of_purpose"], reply["out_of_purpose"])
        self.assertEqual(self.saved("out-of-purpose.json")["rounds"]["1"][0]["found"][0]["from"], "p1.hygiene")

    def test_unbound_answer_without_tie_is_rejected(self):
        answers = [{"question": "どれを採るか", "text": "A を採る"}]
        got = self.take(judge_ok(), answers=answers)
        self.assertIs(got["ok"], False)
        self.assertIn("依頼の答え 'どれを採るか'", got["reason"])
        reply = judge_ok()
        reply["answer_ties"] = [{"answer": "どれを採るか", "to": MEAN}]
        got = self.take(reply, answers=answers)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertEqual(self.saved("answer-ties.json")["rounds"]["1"], reply["answer_ties"])

    def test_ignored_file_added_by_the_judge_is_rejected(self):
        cache = self.repo / "__pycache__"
        cache.mkdir()
        old = cache / "old.pyc"
        old.write_bytes(b"old")
        (self.place / "tree.json").unlink()
        self.materialkit.snap_tree(self.place, self.repo)
        self.assertIs(self.take(judge_ok())["ok"], True, "前から在って変わらない無視されるファイルは通る")
        (self.place / "judgment.json").unlink()
        (self.repo / ".env.pyc").write_bytes(b"x")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn(".env.pyc", got["reason"])
        (self.repo / ".env.pyc").unlink()
        old.write_bytes(b"new")
        self.assertIs(self.take(judge_ok())["ok"], False, "名前が同じまま中身だけ変わっても拒む")
        old.unlink()
        (self.place / "tree.json").unlink()
        (cache / "stats.cpython-314.pyc").write_bytes(b"x")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False, "写しが無い時も無視されるファイルを数える")
        self.assertIn("__pycache__", got["reason"])
        self.assertFalse((self.place / "judgment.json").exists())

    def test_newlines_in_key_and_reason_are_folded(self):
        reply = judge_ok()
        reply["units"][0]["key"] = MEAN.replace(": ", ":\n  ")
        reply["units"][0]["reason"] = "事実: 分母が違う。\n反証: 意図の取り違えを当たった"
        reply["questions"] = [{"key": "実機で\n確かめる", "kind": "field", "status": "held", "reason": "実機が\n要る"}]
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        doc = self.judgment()
        self.assertEqual(doc["units"][0]["key"], MEAN)
        self.assertEqual(doc["units"][0]["reason"], "事実: 分母が違う。 反証: 意図の取り違えを当たった")
        self.assertEqual((doc["questions"][0]["key"], doc["questions"][0]["reason"]), ("実機で 確かめる", "実機が 要る"))

    def test_duplicate_key_and_suggest_without_disposition_are_rejected(self):
        reply = judge_ok()
        reply["units"].append(copy.deepcopy(reply["units"][0]))
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn(f"units[2] の key が重複: {MEAN}", got["reason"])
        reply = judge_ok()
        reply["units"].append(unit("stats.py fmt: 桁", ["x"], "population", 0, label="suggest"))
        del reply["units"][2]["disposition"]
        got = self.take(reply)
        self.assertIn("units[2]（suggest）に disposition（do-now / defer）が無い", got["reason"])
        reply["units"][2].update(disposition="defer", reason="")
        got = self.take(reply)
        self.assertIn("units[2] の defer に構造的理由が無い", got["reason"])

    def test_query_that_counts_only_the_request_files_is_rejected(self):
        """入力 request_files（依頼そのものを書いたファイル。docs/design/spec-driven.md の 9 章）: 探し方の paths がどれもその中の単位は
        拒む（数えるのは直す所で、依頼の文ではない）。paths が 1 つでも外を指せば通す。空の配列（既定）は照らさない"""
        reply = judge_ok()
        self.assertIs(self.take(reply)["ok"], True)
        got = self.take(reply, request_files=["stats.py"])
        self.assertIs(got["ok"], False)
        self.assertIn("units[0].class_query.how.paths がどれも依頼そのものを書いたファイル", got["reason"])
        self.assertIs(self.take(reply, request_files=["./stats.py/"])["ok"], False, "正規化して比べる")
        self.assertIs(self.take(reply, request_files=["docs/spec.yaml"])["ok"], True)
        both = judge_ok()
        for u in both["units"]:
            if "class_query" in u:
                u["class_query"]["how"]["paths"] = ["stats.py", "other.py"]
        self.assertNotIn("依頼そのものを書いたファイル", self.take(both, request_files=["stats.py"])["reason"])

    def test_engine_recounts_the_class_query_total(self):
        reply = judge_ok()
        reply["units"][1]["class_query"]["total"] = 5
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertIn("class_query の件数を engine が走らせた値に置き換えた: units[1].class_query.total 5 → 2", got["reason"])
        cq = self.judgment()["units"][1]["class_query"]
        self.assertEqual(cq["total"], 2)
        self.assertIn("役の書いた total は 5", cq["note"])
        reply = judge_ok()
        reply["units"][1]["class_query"].update(how={"patterns": ["no-such-line-anywhere"], "fixed": True, "paths": ["stats.py"],
                                                    "count": "lines"}, total=3)
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        self.assertIn("engine の数が 0 件なので置き換えなかった: units[1].class_query（役 3 / engine 0）", got["reason"])
        cq = self.judgment()["units"][1]["class_query"]
        self.assertEqual(cq["total"], 3)
        self.assertIn("engine が how を走らせると 0 件", cq["note"])

    def test_count_budget_stops_endless_recounts(self):
        (self.place / "count-budget.json").write_text(json.dumps({"round": 1, "calls": 300, "seconds": 0.0}), encoding="utf-8")
        got = self.take(judge_ok())
        self.assertIs(got["ok"], False)
        self.assertIn("上限（300 回か 900 秒）に達した", got["reason"])

    def test_defects_query_needs_misses_and_must_not_match_the_fixed_form(self):
        reply = judge_ok()
        cq = reply["units"][0]["class_query"]
        cq["hits"] = ["    return sum(xs) / (len(xs) - 1)"]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn(f"{MEAN}: 欠陥の形を数える問い（counts: defects）に misses が無い", got["reason"])
        self.assertFalse((self.place / "judgment.json").exists())
        fixed = "    return sum(xs) / (len(xs) - 1)  # 直した"
        cq["misses"] = [fixed]
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("直した後の正しい形にも当たる", got["reason"])
        self.assertIn(repr(fixed), got["reason"])

    def test_one_shot_closes_must_name_open_units(self):
        reply = judge_ok()
        reply["one_shot_closes"] = []
        got = self.take(reply)
        self.assertIs(got["ok"], False)
        self.assertIn("one_shot_closes が空", got["reason"])
        reply["one_shot_closes"] = [MEAN, "stats.py: 無い単位"]
        got = self.take(reply)
        self.assertIn("one_shot_closes に今の周の units に無い key: ['stats.py: 無い単位']", got["reason"])

    def test_question_ledger_targets_and_settled_state(self):
        out = {"units": [], "questions": [{"key": "q", "kind": "field", "status": "held", "reason": "実機が要る", "severity": "high"}]}
        with self.assertRaises(self.mod["judge"].Reject) as cm:
            self.judge.judge_output(out, self.place, "", "", {})
        self.assertIn("questions[0] に知らない欄: ['severity']", str(cm.exception))
        reply = judge_ok()
        reply["units"].append(unit("stats.py fmt: 桁", ["x"], "population", 0, label="nit"))
        for name, q, needle in (
                ("無い出どころ", {"kind": "stuck", "status": "held", "origin": "stats.py: 無い単位"},
                 "questions[0] の origin 'stats.py: 無い単位' が units に無い"),
                ("無い depends", {"kind": "stuck", "status": "held", "origin": MEAN, "depends": ["stats.py: 無い単位"]},
                 "questions[0] の depends 'stats.py: 無い単位' が units に無い"),
                ("開いた単位の split", {"kind": "split", "status": "held", "origin": MEAN},
                 f"questions[0]（split）の出どころ '{MEAN}' が [block] / do-now"),
                ("開いたまま resolved", {"kind": "stuck", "status": "resolved", "resolution": "A を採る", "origin": MEAN},
                 "出どころが [block] / do-now のまま resolved"),
                ("閉じたのに decided", {"kind": "stuck", "status": "decided", "resolution": "A を採る", "origin": "stats.py fmt: 桁"},
                 "出どころが閉じているのに decided")):
            with self.subTest(name):
                reply["questions"] = [{"key": "q", "reason": "決まらない", **q}]
                got = self.take(reply)
                self.assertIs(got["ok"], False)
                self.assertIn(needle, got["reason"])
        reply["questions"] = [{"key": "q", "reason": "決まらない", "kind": "stuck", "status": "decided", "resolution": "A を採る",
                               "origin": MEAN}]
        self.assertIs(self.take(reply)["ok"], True)

    def test_open_unit_without_precedent_row_and_ask_without_undecided_because_are_rejected(self):
        reply = judge_ok()
        del reply["precedents"][1]
        got = self.take(reply)
        self.assertIn(f"precedents に '{CLAMP}' の行が無い", got["reason"])
        reply = judge_ok()
        reply["questions"] = [{"key": "実機で確かめる", "kind": "field", "status": "escalate", "reason": "実機が要る"}]
        reply["precedents"].append({"key": "実機で確かめる", "problem": "実機の振る舞い", "source": "機器の文書の節",
                                    "verdict": "adopt", "reason": "当たった"})
        got = self.take(reply)
        self.assertIn("precedents['実機で確かめる'] に undecided_because が無い", got["reason"])
        reply["precedents"][-1]["undecided_because"] = "文書が機器の版ごとに割れて決まらない"
        got = self.take(reply)
        self.assertIs(got["ok"], True, got["reason"])

    def test_precedent_asks_are_the_gate_asks(self):
        import gatemarks
        questions = [{"key": f"{kind}-{status}", "kind": kind, "status": status}
                     for kind in ("fork", "field", "stuck") for status in (*gatemarks.ASKING, "decided")]
        errs = self.judge._precedent_errors({"units": [], "questions": questions, "precedents": []})
        wanted = sorted(q["key"] for q in questions if f"precedents に '{q['key']}' の行が無い" in " ".join(errs))
        self.assertEqual(wanted, sorted(["fork-held", "fork-escalate", "field-escalate", "stuck-escalate"]))

    def test_premise_three_question_must_name_a_recorded_row(self):
        import policy

        def asked(because):
            reply = judge_ok()
            reply["questions"] = [{"key": "空の列を試すか", "kind": "field", "status": "escalate", "reason": "試験を足すかが割れる"}]
            reply["precedents"].append({"key": "空の列を試すか", "problem": "空の列の試験", "source": "対象のテストの頭",
                                        "verdict": "adopt", "reason": "当たった", "undecided_because": because})
            return reply
        for because in ("③ 方針とぶつかる: test_stats.py:1 の『わざと試験しない』", "①・③ 先例が割れ、test_stats.py:1 ともぶつかる"):
            with self.subTest(because):
                got = self.take(asked(because))
                self.assertIs(got["ok"], False)
                self.assertIn("対象の文で、そのぶつかりは ③ に当たらない", got["reason"])
        for because in ("② 優先の付け方で変わる（③ のぶつかりは無い）", "3 つ目の場合（記録された方針とぶつかる）: test_stats.py:1"):
            with self.subTest("頭の印に ③ が無い問いは ③ を名乗らない", because=because):
                self.assertIs(self.take(asked(because))["ok"], True)
        pmd = self.place / "policy-copy.md"
        pmd.write_text("# 方針\n- 空の列は試験しない\n", encoding="utf-8")
        recorded = policy.recorded({"policy": {"named": "", "path": "", "sha256": None, "copy": str(pmd)}, "answers": []}, None)
        got = self.take(asked(f"③ {pmd}:2 とぶつかる"), recorded=recorded)
        self.assertIs(got["ok"], True, got["reason"])

    def test_answer_ties_rules(self):
        carry = __import__("carry")

        def stuck(key):
            return {"key": key, "kind": "stuck", "status": "held", "reason": "割れる", "origin": MEAN}

        with self.subTest("字の一致・測れていない素材・機械が立てる問いの答えは結びが要らない"):
            answers = [{"question": "q-1", "text": "0 を返す"}, {"question": "parallel_pr", "text": "並行する PR は無い"},
                       {"question": self.judge.ASK_KEYS["R3"], "text": "docs/ を見よ"}]
            reply = judge_ok()
            reply["questions"] = [stuck("q-1")]
            got = self.take(reply, answers=answers, materials={"parallel_pr": {"status": "not_run", "reason": "通信を拒まれた"}})
            self.assertIs(got["ok"], True, got["reason"])
        with self.subTest("返答の問い 2 つに当たる答え"):
            answers = [{"question": MEAN, "text": "例外"}]
            reply = judge_ok()
            reply["questions"] = [stuck("q-1"), stuck("q-2")]
            got = self.take(reply, answers=answers)
            self.assertIs(got["ok"], False)
            self.assertIn("返答の複数の問いに当たる（q-1・q-2）", got["reason"])
            reply["answer_ties"] = [{"answer": MEAN, "to": "q-2"}]
            self.assertIs(self.take(reply, answers=answers)["ok"], True)
        with self.subTest("知らない key への結び"):
            answers = [{"question": "空の列の扱い", "text": "例外"}]
            reply = judge_ok()
            reply["answer_ties"] = [{"answer": "空の列の扱い", "to": "q-9"}]
            got = self.take(reply, answers=answers)
            self.assertIs(got["ok"], False)
            self.assertIn("to 'q-9' が今の返答の問いの key にも単位の key にも無い", got["reason"])
        (self.place / "answer-ties.json").unlink(missing_ok=True)
        redesign = [{"where": carry.REDESIGN_WHERE, "text": "R2 が redesign-needed: 独立設計と構造が合わない"}]
        defer = unit("stats.py fmt: 桁", ["x"], "population", 0, label="suggest", disposition="defer")
        head = redesign[0]["text"]
        for name, ties, needle in (("結び無し", [], "作り直しの行"),
                                   ("defer の単位", [{"redesign": head, "to": defer["key"]}], "[block] でも do-now でもない"),
                                   ("知らない行", [{"redesign": "別の行", "to": MEAN}], "作り直しのセクションのどの行にも当たらない"),
                                   ("短い訳", [{"redesign": head, "none": "目的の外"}], "字に満たない")):
            with self.subTest(name):
                reply = judge_ok()
                reply["units"].append(copy.deepcopy(defer))
                reply["answer_ties"] = ties
                got = self.take(reply, redesign=redesign)
                self.assertIs(got["ok"], False)
                self.assertIn(needle, got["reason"])
                self.assertFalse((self.place / "answer-ties.json").exists())
        for ties in ([{"redesign": head, "to": MEAN}],
                     [{"redesign": head, "none": "反証で死んだ: 独立設計の構造は依頼の外の物で、この周の目的に入らない"}]):
            with self.subTest(ties[0]):
                reply = judge_ok()
                reply["answer_ties"] = ties
                got = self.take(reply, redesign=redesign)
                self.assertIs(got["ok"], True, got["reason"])
                self.assertNotIn("answer_ties", self.judgment())
                self.assertEqual(self.saved("answer-ties.json"), {"rounds": {"1": ties}})


class AcceptRoundCase(_Base):
    def accept(self, reply):
        return self.judge.accept_reply(self.place, json.dumps(reply, ensure_ascii=False), self.repo,
                                       **{k: self.state[k] for k in ("world_rows", "answers", "redesign", "recorded", "materials", "material_rows")})

    def test_third_rejection_gives_up_without_a_stop_record(self):
        import rolekit
        bad = judge_ok()
        bad["units"][0]["label"] = "major"
        outs = [self.accept(bad) for _ in range(3)]
        self.assertEqual([o["done"] for o in outs], [False, False, True])
        self.assertIs(outs[-1]["ok"], False)
        self.assertIn("3 回とも", rolekit.given_up_reason(self.place, "diagnose"))
        self.assertEqual(sorted(p.name for p in self.place.glob("stop*")), [], "止めの控えは書かない")
        self.assertEqual(len(rolekit.rejected(self.place, "diagnose")), 3)

    def test_good_reply_ends_the_loop(self):
        got = self.accept(judge_ok())
        self.assertEqual((got["ok"], got["done"]), (True, True), got)

    def test_reply_that_is_not_json_is_rejected(self):
        got = self.judge.accept_reply(self.place, "これは JSON でない", self.repo, [], [], [], [], {}, [])
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("JSON として読めない", got["reason"])


class StructureUnitsCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "b.py").write_text("y = 2\n", encoding="utf-8")
        self.judge = support.modules()["judge"]

    @staticmethod
    def unit(paths=None, key="src/a.py mean: 分母が違う", label="block"):
        u = {"key": key, "label": label, "disposition": "do-now", "reason": "r"}
        if paths is not None:
            u["class_query"] = {"how": {"patterns": ["x"], "paths": paths}}
        return u

    def test_keeps_files_under_root_in_order_without_duplicates(self):
        self.assertEqual(self.judge._unit_file_paths(self.unit(["b.py", "./src/a.py", "src/a.py"]), self.repo), (["b.py", "src/a.py"], []))

    def test_drops_paths_that_are_not_files_under_root(self):
        bad = ["src", "*.py", ":(glob)src/*.py", str(self.repo / "b.py"), "../b.py", "src/../b.py", "gone.py"]
        self.assertEqual(self.judge._unit_file_paths(self.unit(["b.py", *bad]), self.repo), (["b.py"], bad))

    def test_falls_back_to_key_head_only_without_how_paths(self):
        self.assertEqual(self.judge._unit_file_paths(self.unit(), self.repo), (["src/a.py"], []))
        self.assertEqual(self.judge._unit_file_paths(self.unit(key="上限を呼び手ごとに持つ"), self.repo), ([], ["上限を呼び手ごとに持つ"]))

    def test_all_open_units_are_listed_even_without_paths(self):
        doc = {"units": [self.unit(["b.py"], key="b.py 一"), self.unit(key="上限を呼び手ごとに持つ"),
                         self.unit(["b.py"], key="b.py 情報", label="info")]}
        self.assertEqual(self.judge.structure_units(doc, self.repo),
                         [{"id": "b.py 一", "paths": ["b.py"], "summary": "r"},
                          {"id": "上限を呼び手ごとに持つ", "paths": [], "summary": "r"}])
        self.assertEqual(self.judge.structure_units(None, self.repo), [])

    def test_dropped_paths_are_recorded(self):
        doc = {"units": [self.unit(["b.py", "src", "gone.py"], key="b.py 一"), self.unit(key="上限を呼び手ごとに持つ")]}
        record = self.repo / "out" / "structure-units-dropped.json"
        record.parent.mkdir()
        self.judge.structure_units(doc, self.repo, record=record)
        self.assertEqual(json.loads(record.read_text(encoding="utf-8")),
                         {"units": ["上限を呼び手ごとに持つ"], "paths": ["src", "gone.py", "上限を呼び手ごとに持つ"]})
