"""計画のブロックの盤面の読みの書き直し（lib/planfile.py）の検査。

元の関数は盤面 b から判定の記録・壁打ちの控え・修正前の版を読んでいた。ここでは値かパスを渡して、元の試験の場合を写す:
直す義務の単位と入れてよい単位（元 rules/review-loop.py の _owed_units・fix_plan_covers_units、planblk の plan_slots・
stuck_reason・not_allowed。元 tests/test_duty_sets.py・test_blk_plan.py）、案の直しの返答の誤り（元 replan._plan_errors。
元 tests/test_replan.py）、判定の処方（元 planmarks.prescriptions・planblk.prescription_section）、修正前の版のテストの中身
（元 writes.base_test_texts）、壁打ちの控えの組み直しと答え・差し込み（元 converge の read・record_pass・answer_gaps・splice。
元 tests/test_converge.py・test_plan_gate.py）、周の番号。種の git は gitkit の型の写し。
"""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import carry  # noqa: E402
import converge  # noqa: E402
import planblk  # noqa: E402
import planfile  # noqa: E402
import planmarks  # noqa: E402
import replan  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
NIT = "stats.py mean: 変数名が短い"
DEFER = "stats.py clamp: 引数の順が読みにくい"
ASKED = "stats.py mean: 空の列の扱い"
DEP = "stats.py mean: 空の列の試験"


def unit(key, label="block", disposition="do-now", **more):
    u = {"key": key, "label": label, "reason": f"事実: {key}。反証: 無し", **more}
    if disposition:
        u["disposition"] = disposition
    return u


def judgment(*, questions=()):
    """判定の返答（judgment.json の中身）: 直す 2 単位・nit・defer・人に諮る fork の出どころと depends"""
    return {"framing": "算術平均と上限の枝の取り違え", "one_shot": "2 行を直す", "one_shot_closes": [MEAN, CLAMP],
            "units": [unit(MEAN, prescriptions=["分母を len(xs) にする", "  "]), unit(CLAMP),
                      unit(NIT, "nit", None), unit(DEFER, "suggest", "defer"),
                      unit(ASKED, "suggest", "do-now"), unit(DEP, "block")],
            "questions": [{"key": "q-asked", "kind": "fork", "status": "held", "origin": ASKED, "depends": [DEP]},
                          *questions]}


def item(*keys, **more):
    """修正案の項目の見本（works の欄つき。stats.py の 2 単位を直す形）"""
    return {"unit_keys": list(keys), "approach": "mean の分母を len(xs) に、clamp の上限の枝を hi に直す", "adds": [],
            "removes": [], "shrink_first": "足す物は無い。式と戻り値を 1 か所ずつ直すだけで足りる", "narrows": [],
            "route": "tdd",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                       "path": "stats.mean を本物のまま呼び、戻り値を断言する", "red_kind": "assertion",
                       "red_why": "今の分母は len(xs) - 1 なので mean([1, 3]) が 4.0 を返す"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
            "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": [], **more}


def face(key, units, severity="block"):
    return {"key": key, "kind": "regression", "where": f"{key} の場所", "why": f"{key} が穴である理由",
            "severity": severity, "unit_keys": list(units)}


def answer(key, handled="fixed", how="案の項目 1 の手順を直した"):
    return {"key": key, "handled": handled, "how": how}


class TmpCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)

    def write(self, rel, doc):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return p


class OwedCase(unittest.TestCase):
    """元 conflict.py:676 の owed_units_but_asked（開いた単位から、答えていない関所の問い——人に聞く状態の fork と status が escalate の
    問い——の出どころ・depends を除く）と元 review-record.py:624 の is_open"""

    def test_owed_is_open_units_minus_asking_fork_origin_and_depends(self):
        self.assertEqual(planfile._owed_units(judgment()), {MEAN, CLAMP})

    def test_open_is_block_or_do_now_suggest(self):
        self.assertEqual([planfile.is_open(u) for u in judgment()["units"]], [True, True, False, False, True, True])

    def test_decided_fork_and_held_non_fork_do_not_excuse(self):
        doc = judgment()
        doc["questions"] = [{"key": "q", "kind": "fork", "status": "decided", "origin": ASKED, "depends": [DEP]},
                            {"key": "r", "kind": "scope", "status": "held", "origin": CLAMP}]
        self.assertEqual(planfile._owed_units(doc), {MEAN, CLAMP, ASKED, DEP})

    def test_escalated_fork_excuses(self):
        doc = judgment()
        doc["questions"][0]["status"] = "escalate"
        self.assertEqual(planfile._owed_units(doc), {MEAN, CLAMP})

    def test_escalated_non_fork_excuses_origin_and_depends(self):
        """元の差し替えは写しの RL が外さない escalate の問い（fork でない）の出どころ・depends も外す（gatemarks.asks・withheld）"""
        doc = judgment(questions=[{"key": "r", "kind": "scope", "status": "escalate", "origin": CLAMP, "depends": [MEAN]}])
        self.assertEqual(planfile._owed_units(doc), set())

    def test_broken_rows_are_not_read(self):
        self.assertEqual(planfile._owed_units({"units": ["x", {"label": "block"}], "questions": "q"}), set())

    def test_depends_that_is_not_a_list_is_not_read(self):
        """depends が並びでない（数）問いでも落ちない。出どころは外し、depends は読まない"""
        doc = judgment()
        doc["questions"][0]["depends"] = 3
        self.assertEqual(planfile._owed_units(doc), {MEAN, CLAMP, DEP})

    def test_owed_order_follows_the_judgment(self):
        doc = judgment(questions=[{"key": "r", "kind": "scope", "status": "escalate", "origin": MEAN}])
        self.assertEqual(planfile.owed_order(doc), [CLAMP])
        self.assertEqual(planfile.owed_order(judgment()), [MEAN, CLAMP])


class SlotsCase(unittest.TestCase):
    """元 planblk の plan_slots・stuck_reason・not_allowed（番号は開いた単位に 1 から）"""

    def test_slots_number_open_units_in_order(self):
        self.assertEqual(planfile.slots(judgment()), [MEAN, CLAMP, ASKED, DEP])

    def test_plan_slots_must_may_and_units(self):
        must, may, units = planfile.plan_slots(judgment())
        self.assertEqual(must, {MEAN, CLAMP})
        self.assertEqual(may, {MEAN, CLAMP, ASKED, DEP})
        self.assertLessEqual(must, may)
        self.assertEqual(set(units), {MEAN, CLAMP, NIT, DEFER, ASKED, DEP})

    def test_no_stuck_unit_when_every_owed_unit_is_open(self):
        self.assertEqual(planfile.stuck_reason(judgment()), "")

    def test_stuck_names_owed_unit_that_is_not_open(self):
        """必ず入れるのに開いていない単位（元は関所で答えた問いの出どころが defer）が在れば、行き止まりの理由が番号と key を名指す"""
        with mock.patch.object(planfile, "_owed_units", return_value={MEAN, DEFER}):
            why = planfile.stuck_reason(judgment())
        self.assertTrue(why.startswith(planblk.PLAN_STUCK), why)
        self.assertIn(f"no の一覧に無い単位（{DEFER}）", why)
        self.assertIn(planblk.STUCK_WHY, why)

    def test_not_allowed_names_label_of_unit_without_duty(self):
        reply = {"plan": [item(MEAN, CLAMP, NIT)]}
        got = planfile.not_allowed(judgment(), reply)
        self.assertEqual(len(got), 1, got)
        self.assertIn("label=nit", got[0])
        self.assertEqual(planfile.not_allowed(judgment(), {"plan": [item(MEAN, CLAMP, ASKED)]}), [])

    def test_not_allowed_reads_past_broken_rows(self):
        self.assertEqual(planfile.not_allowed(judgment(), {"plan": ["x", {"unit_keys": 5}]}), [])

    def test_named_turns_numbers_into_ids_and_keeps_unknown_numbers(self):
        reply = {"plan": [item(1, 2), item(CLAMP, 9)]}
        got = planfile.named(reply, [MEAN, CLAMP])
        self.assertEqual([p["unit_keys"] for p in got["plan"]], [[MEAN, CLAMP], [CLAMP, 9]])
        self.assertEqual(reply["plan"][0]["unit_keys"], [1, 2], "役の返答は書き換えない")


class CoversCase(unittest.TestCase):
    """元 rules/review-loop.py:3077 の fix_plan_covers_units（例外の代わりに行を返す）"""
    owed, opened = {MEAN, CLAMP}, {MEAN, CLAMP, ASKED}

    def covers(self, *rows):
        return planfile.fix_plan_covers_units([{"unit_keys": list(r)} for r in rows], self.owed, self.opened)

    def test_every_owed_unit_once(self):
        self.assertEqual(self.covers([MEAN], [CLAMP]), [])
        self.assertEqual(self.covers([MEAN, CLAMP, ASKED]), [], "人に諮っている単位は入れてもよい")

    def test_missing_unit_named(self):
        got = self.covers([MEAN])
        self.assertEqual(len(got), 1, got)
        self.assertIn("どの案にも入っていない単位", got[0])
        self.assertIn(CLAMP[:40], got[0])

    def test_unit_in_two_items_named(self):
        got = self.covers([MEAN, CLAMP], [CLAMP])
        self.assertTrue(any("2 つの案に入った単位" in g for g in got), got)

    def test_unknown_key_and_number_named(self):
        got = self.covers([MEAN, CLAMP, "どこにも無い単位"], [7])
        self.assertTrue(any("今の周に直す単位に無い key" in g and "どこにも無い単位" in g and "7" in g for g in got), got)


class ReplanErrorsCase(TmpCase):
    """元 replan._plan_errors（数・unit_keys の字・works の欄・狭めない案を全部並べて 1 回で拒む。元 tests/test_replan.py の
    test_reply_limited_to_handed_items・test_all_errors_in_one_rejection）"""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.rows = [{"item": 1, "old": item(MEAN)}]

    def errors(self, reply):
        return planfile._plan_errors(self.rows, reply, self.repo, planfile.exists_at(self.repo, "HEAD"), [])

    def test_good_reply_has_no_error(self):
        self.assertEqual(self.errors({"plan": [item(MEAN, approach="mean の分母を len(xs) にし、試験を足して直す")]}), [])

    def test_reply_limited_to_handed_items(self):
        got = self.errors({"plan": [item(MEAN), item(CLAMP)]})
        self.assertTrue(any("plan[] は 1 項目" in g for g in got), got)
        got = self.errors({"plan": [item(1)]})
        self.assertTrue(any("一字も変えずに写す" in g for g in got), got)

    def test_all_errors_in_one_rejection(self):
        bad = item(CLAMP, route="direct", route_why="",
                   narrows=[{"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}])
        got = "\n".join(self.errors({"plan": [bad]}))
        for word in ("plan[0].unit_keys が貼った", "plan[0].route_why", "plan[0].narrows[0]"):
            self.assertIn(word, got)

    def test_test_in_start_tree_is_rejected(self):
        it = item(MEAN)
        it["tests"] = [{**it["tests"][0], "id": "test_stats.py::TestStats::test_mean_of_three"}]
        self.assertTrue(any("既に在るテスト" in g for g in self.errors({"plan": [it]})))

    def test_test_only_in_work_tree_is_not_in_start_tree(self):
        """作業ツリーに書いた受け入れのテスト（修正の段の残り）は、起点の版の木に無ければ在ると数えない"""
        path = self.repo / "test_stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "    def test_clamp_within_range", "    def test_mean_of_two(self):\n        self.assertEqual(mean([1, 3]), 2)\n\n"
            "    def test_clamp_within_range"), encoding="utf-8")
        self.assertIsNotNone(planmarks.find_test(self.repo, item(MEAN)["tests"][0]["id"]))
        self.assertEqual(self.errors({"plan": [item(MEAN)]}), [])

    def test_unreadable_start_rev_raises(self):
        with self.assertRaises(ValueError):
            planfile.exists_at(self.repo, "no-such-rev")


class PrescriptionCase(unittest.TestCase):
    """元 planmarks.prescriptions（判定の返答の単位ごとの処方。空の処方は入れない）と planblk.prescription_section"""

    def test_prescriptions_skip_blank(self):
        self.assertEqual(planfile.prescriptions(judgment()), {MEAN: ["分母を len(xs) にする"]})
        self.assertEqual(planfile.prescriptions({"units": "x"}), {})

    def test_section_lists_given_units_only(self):
        got = planfile.prescription_section([MEAN, CLAMP], planfile.prescriptions(judgment()))
        self.assertTrue(got.startswith(planblk.PRESCRIPTION_HEAD), got)
        self.assertIn(planblk.PRESCRIPTION_ASK, got)
        self.assertIn(f"### {MEAN}\n\n1. 分母を len(xs) にする", got)
        self.assertNotIn(f"### {CLAMP}", got)
        self.assertEqual(planfile.prescription_section([CLAMP], {}), "")


class BaseTestsCase(TmpCase):
    """元 writes.base_test_texts（修正前の版のテストのファイルの中身。読めない物は含めず、返りの 2 つ目に名指す）"""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)

    def test_texts_of_tests_at_rev(self):
        rev = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "test_stats.py").write_text("# 作業ツリーだけの書き換え\n", encoding="utf-8")
        texts, unread = planfile.base_test_texts(self.repo, rev)
        self.assertEqual(unread, [])
        self.assertIn("test_stats.py", texts)
        self.assertIn("def test_mean_of_three", texts["test_stats.py"])
        self.assertNotIn("stats.py", texts)

    def test_unreadable_rev_names_rev(self):
        self.assertEqual(planfile.base_test_texts(self.repo, "no-such-rev"), ({}, ["<版>"]))


class ConvergeCase(TmpCase):
    """元 converge の read・record_pass（周ごとの案と受けた事前審査から組み直す）と answer_gaps・splice（元 tests/test_converge.py
    の ItemsCase・FieldsCase の盤面を使わずに書ける場合）"""

    def plan_round(self, k, rows, answers=None, mode="plan"):
        self.write(f"r{k}/round.json", {"round": k, "mode": mode})
        doc = {"plan": rows, **({"block_answers": answers} if answers is not None else {})}
        self.write(f"r{k}/{planfile.REPLY_FILE}", doc)

    def review(self, k, faces, resolved=()):
        self.write(f"r{k}/round.json", {"round": k, "mode": "plan"})
        self.write(f"r{k}/{planfile.REVIEW_FILE}", {"faces": faces, "resolved": list(resolved)})

    def states(self, record):
        return [it["state"] for it in record["passes"][-1]["items"]]

    def test_first_round_has_no_pass(self):
        self.plan_round(1, [item("u1"), item("u2")])
        got = planfile.converge_record(self.tmp)
        self.assertEqual((got["passes"], got["outcome"]), ([], None))
        self.assertEqual([it["unit_keys"] for it in got["plan"]], [["u1"], ["u2"]])

    def test_blocked_item_opens_and_clean_item_closes(self):
        self.plan_round(1, [item("u1"), item("u2")])
        self.review(2, [face("key-a1", ["u1"]), face("key-s1", ["u2"], severity="suggest")])
        got = planfile.converge_record(self.tmp)
        self.assertEqual(self.states(got), [converge.OPEN, converge.CLOSED])
        self.assertEqual(got["outcome"], converge.AGAIN)
        self.assertEqual(got["passes"][0]["blocks"], ["key-a1"])

    def test_same_block_twice_holds_item(self):
        self.plan_round(1, [item("u1"), item("u2")])
        self.review(2, [face("key-a1", ["u1"]), face("key-b1", ["u2"])])
        self.plan_round(2, [item("u1", approach="直した案の手順をここに書いた"), item("u2", approach="直した案の手順をここに書いた")],
                        answers=[answer("key-a1"), answer("key-b1")])
        self.review(3, [face("key-a1", ["u1"]), face("key-b2", ["u2"])], resolved=["key-b1"])
        got = planfile.converge_record(self.tmp)
        self.assertEqual(self.states(got), [converge.HELD, converge.OPEN])
        self.assertEqual(got["passes"][1]["answers"], [answer("key-a1"), answer("key-b1")])
        self.assertEqual(got["passes"][1]["resolved"], ["key-b1"])

    def test_replan_rounds_are_not_passes(self):
        self.plan_round(1, [item("u1")])
        self.plan_round(2, [item("u1", approach="案の直しで直した項目の手順を書いた")], mode="replan")
        self.assertEqual(planfile.converge_record(self.tmp)["plan"][0]["row"], item("u1"))

    def blocked_first(self):
        self.plan_round(1, [item("u1"), item("u2")])
        self.review(2, [face("key-a1", ["u1"])])
        return planfile.converge_record(self.tmp)

    def test_answer_gaps_need_one_answer_per_open_block(self):
        record = self.blocked_first()
        self.assertEqual(planfile.answer_gaps(record, [answer("key-a1")]), [])
        gaps = planfile.answer_gaps(record, [answer("key-a1", handled="ignored"), answer("key-z")])
        self.assertTrue(any("handled" in g for g in gaps), gaps)
        self.assertIn("key-z は前の往復の block に無い", gaps)
        self.assertIn("block の key key-a1 への答えが無い", planfile.answer_gaps(record, []))

    def test_no_answers_asked_on_first_round(self):
        self.plan_round(1, [item("u1")])
        record = planfile.converge_record(self.tmp)
        self.assertEqual(planfile.answer_gaps(record, []), [])
        self.assertEqual(planfile.answer_gaps(record, [answer("key-x")]), ["key-x は前の往復の block に無い"])

    def test_splice_fills_closed_item_and_refuses_changed_one(self):
        record = self.blocked_first()
        fixed = item("u1", approach="直した案の手順をここに書いた")
        whole, rejects, dropped = planfile.splice(record, [fixed])
        self.assertEqual((rejects, dropped), ([], []))
        self.assertEqual(whole, [fixed, item("u2")])
        _, rejects, dropped = planfile.splice(record, [fixed, item("u2")])
        self.assertEqual((rejects, dropped), ([], ["u2"]), "閉じた項目を前のまま書いた行は捨てる")
        _, rejects, _ = planfile.splice(record, [fixed, item("u2", approach="閉じた項目を書き換えてしまった")])
        self.assertEqual(len(rejects), 1, rejects)
        self.assertIn("閉じた項目 2 を変えた", rejects[0])

    def test_splice_refuses_missing_open_item(self):
        _, rejects, _ = planfile.splice(self.blocked_first(), [])
        self.assertEqual(len(rejects), 1, rejects)
        self.assertIn("開いた項目 1 の行が無い", rejects[0])

    def test_splice_without_passes_takes_reply(self):
        self.plan_round(1, [item("u1")])
        rows = [item("u1"), item("u9")]
        self.assertEqual(planfile.splice(planfile.converge_record(self.tmp), rows), (rows, [], []))

    def test_revise_section_names_blocks_and_closed_items(self):
        sec = planfile.revise_section(self.blocked_first())
        self.assertIn(converge.REVISE_ASK, sec)
        self.assertIn("### key-a1", sec)
        self.assertIn(converge.CLOSED_ASK, sec)
        self.assertIn("項目 2（u2）", sec)
        self.assertEqual(planfile.revise_section(planfile.converge_record(self.tmp / "none")), "")


class UnitsSectionCase(TmpCase):
    """材料の単位の節: 閉じた・保留の項目の単位は『必ず案に入れる』でなく、機械が差し込む行に分ける（元 planblk.plan_slots_section の
    filled）"""

    def test_filled_units_are_not_owed_in_the_brief(self):
        self.write("r1/round.json", {"round": 1, "mode": "plan"})
        self.write(f"r1/{planfile.REPLY_FILE}", {"plan": [item(MEAN), item(CLAMP)]})
        self.write("r2/round.json", {"round": 2, "mode": "plan"})
        self.write(f"r2/{planfile.REVIEW_FILE}", {"faces": [face("key-a1", [MEAN])]})
        filled = planfile.filled_units(planfile.converge_record(self.tmp))
        self.assertEqual(filled, [CLAMP])
        text = planfile.units_section(judgment(), [], [], filled)
        self.assertIn(f"- no 1 `{MEAN}`: label=block・disposition=do-now・必ず案に入れる", text)
        self.assertIn(f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{planfile.FILLED_DUTY}", text)
        self.assertIn("- 機械が差し込む no（閉じた・保留の項目。書かなくてよい）: [2]", text)
        self.assertNotIn("機械が差し込む no", planfile.units_section(judgment(), [], []))


class ReplanInputsCase(TmpCase):
    """案の直しの材料と置き場: 裁定の種類で絞った申し出の行・直す元の周の構造の置き場"""

    def test_conflict_rows_are_fix_plan_item_rulings_only(self):
        rows = [{"id": "c1", "unit_key": MEAN, "ruling": {"decision": "fix_plan_item", "plan_items": [1]}},
                {"id": "c2", "unit_key": MEAN, "ruling": {"decision": "ask_human"}},
                {"id": "c3", "unit_key": "ほかの単位", "ruling": {"decision": "fix_plan_item", "plan_items": [2]}},
                {"id": "c4", "unit_key": MEAN, "ruling": "壊れた"}]
        got = planfile.conflict_rows({"items": rows}, 1, item(MEAN))
        self.assertEqual([c["id"] for c in got], ["c1"])

    def test_replan_structure_is_the_source_rounds(self):
        """直す元の周の round.json の structure を使う（後から書いたほかの鍵の控えに倒れない）"""
        plan = self.tmp / "plan"
        self.write("plan/r1/round.json", {"round": 1, "mode": "plan", "structure": "structure/aaa"})
        self.write("plan/structure/aaa/structure-state.json", {"status": "ok"})
        self.write("plan/structure/bbb/structure-state.json", {"status": "ok"})
        self.assertEqual(planfile.structure_dir(plan, [], self.tmp, plan / "r1"), plan / "structure" / "aaa")

    def test_round_without_role_gets_its_own_structure_folder(self):
        plan = self.tmp / "plan"
        got = planfile.open_round(plan, ruling=[], judgment=None, review=None, units=[], repo=self.tmp)
        self.assertEqual((got["go"], got["structure"]), (False, "r1/structure"))
        state = planfile.write_state(plan / got["structure"], skipped=got["why"])
        doc = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed")
        self.assertIn("判定が読めない", doc["reason"])
        self.assertEqual((plan / "r1" / "structure" / planfile.DESIGN_FILE).stat().st_size, 0)
        self.assertFalse((plan / planfile.STRUCTURE_DIR / "unread").exists())


class PriorFailuresCase(TmpCase):
    """前の run で最後まで通らなかった物の節（元 planblk.prior_part の carry.prior_section）"""

    def test_rows_become_the_section_and_are_kept_in_the_round(self):
        rows = [{"where": "修正案の受け付け", "text": "単位の網羅が 3 回とも欠けた"}]
        text = planfile.prior_section(self.tmp, rows)
        self.assertIn(carry.PRIOR_HEAD, text)
        self.assertIn("修正案の受け付け: 単位の網羅が 3 回とも欠けた", text)
        self.assertEqual(json.loads((self.tmp / carry.PRIOR_IN_FILE).read_text(encoding="utf-8")), rows)
        self.assertEqual(planfile.prior_section(self.tmp, None), "")

    def test_wrong_shape_is_an_error(self):
        for bad in ({"where": "x"}, [{"where": "x"}], ["x"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                planfile.prior_section(self.tmp, bad)


class RevisedFieldsCase(TmpCase):
    """元 replan.revised_fields（直した項目の欄を planmarks.split で作り直して差し替える）"""

    def test_replaces_only_revised_items(self):
        repo = self.tmp / "repo"
        committed_copy(repo, SEED)
        _, fields = planmarks.split({"plan": [item(MEAN), item(CLAMP)]}, repo)
        new = item(CLAMP, allowed_paths=["stats.py"])
        rows = [{"item": 2, "new": new, "new_marks": []}]
        got = planfile.revised_fields(fields, rows, repo)
        self.assertEqual(got[0], fields[0])
        self.assertEqual(got[1]["allowed_paths"], ["stats.py"])
        self.assertEqual(fields[1]["allowed_paths"], ["stats.py", "test_stats.py"], "渡した欄は書き換えない")


class RoundCase(TmpCase):
    """ブロックの名の小道具: 周の番号・一番新しい案の周・構造の実測の使い回しの鍵"""

    def test_next_round_counts_round_folders(self):
        self.assertEqual(planfile.next_round(self.tmp / "plan"), 1)
        (self.tmp / "plan" / "r1").mkdir(parents=True)
        (self.tmp / "plan" / "structure").mkdir()
        self.assertEqual(planfile.next_round(self.tmp / "plan"), 2)

    def test_latest_is_newest_round_with_accepted_plan(self):
        self.write("r1/" + planfile.REPLY_FILE, {"plan": []})
        self.write("r2/round.json", {"round": 2})
        self.write("r10/" + planfile.REPLY_FILE, {"plan": []})
        self.assertEqual(planfile.latest(self.tmp), self.tmp / "r10")
        self.assertIsNone(planfile.latest(self.tmp / "none"))

    def test_structure_key_follows_units_and_head(self):
        units = [{"id": "u", "paths": ["stats.py"], "summary": ""}]
        key = planfile.structure_key(units, "a" * 40)
        self.assertEqual(len(key), 12)
        self.assertEqual(key, planfile.structure_key(json.loads(json.dumps(units)), "a" * 40))
        self.assertNotEqual(key, planfile.structure_key(units, "b" * 40))
        self.assertNotEqual(key, planfile.structure_key([], "a" * 40))


class ReplanModuleCase(unittest.TestCase):
    """持ってきた replan.py の残り（盤面を受けない項目の小道具）"""

    def test_new_item_puts_marks_back_on_narrows(self):
        row = {"new": {"narrows": [{"what": "x"}]}, "new_marks": [{"no_narrow": "狭めない案を当たったが無い"}]}
        self.assertEqual(replan.new_item(row), {"narrows": [{"what": "x", "no_narrow": "狭めない案を当たったが無い"}]})
        self.assertEqual(row["new"], {"narrows": [{"what": "x"}]})

    def test_malformed(self):
        for reply in (None, {"plan": "x"}, {"plan": ["x"]}, {"plan": [{"narrows": 5}]}):
            self.assertTrue(replan._malformed(reply), reply)
        self.assertFalse(replan._malformed({"plan": [{"narrows": []}]}))


if __name__ == "__main__":
    unittest.main()
