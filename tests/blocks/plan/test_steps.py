"""修正案の block の中身（blocks/plan/src/steps.py・take.py・brief.py・files.py）の検査。今の lib/tests/test_planfile.py を、port の値で
受ける形に写した物（docs/design/plan.md の 9.2）。

元の関数は盤面の置き場から判定・往復の記録・修正前の版を読んでいた。ここでは入口（steps.intake）を port の値で本当に回して周のフォルダ
r<k>/ と intake.json を作り、その上で src の関数をこの過程で、script と同じ環境（kit.Run.env）で呼ぶ:
直す義務の単位と入れてよい単位（OwedCase・SlotsCase・CoversCase）・案の直しの返答の誤り（ReplanErrorsCase）・判定の処方（PrescriptionCase）・
リポジトリの行の値（RepoLineCase）・修正前の版のテストの中身（BaseTestsCase）・往復の記録の読み口（ConvergeCase。記録を組むのは line に
移ったので、記録は converge.add_pass と plan_rows で試験が組む）・材料の行（UnitsSectionCase・WorldRowsCase・PriorFailuresCase・
VerifyNeighborCase・HeadDepthNeighborCase）・受け付け（TakePlanCase・WholePlanTakeCase・RevisedFieldsCase・ReplanModuleCase・
ResubmitMergeCase）・波及の一覧（RippleItemsCase）・周の番号とファイルの名（RoundCase・FilesCase）・入れ子の値・出口（FinishCase）。
種の git は gitkit の型の写し（FAST）。
"""
import copy
import importlib
import json
import os
import pathlib
import shutil
import unittest
from unittest import mock

from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit
from tests.blocks.plan import base

brief = kit.load("plan", "brief")
take = importlib.import_module("src.take")   # kit.load が置いた src の package から（steps・files を brief と同じ物に揃える）
steps, files = brief.steps, brief.files
import ports  # noqa: E402  （blocks/.shared/。kit.load が sys.path に足す）
import carry  # noqa: E402  （lib/）
import conflict  # noqa: E402
import converge  # noqa: E402
import handoff  # noqa: E402
import judgmark  # noqa: E402
import headdepth  # noqa: E402
import planmarks  # noqa: E402
import replan  # noqa: E402
import rolekit  # noqa: E402
import worldmark  # noqa: E402

MEAN, CLAMP, NIT = base.MEAN, base.CLAMP, base.NIT
DEFER = "stats.py clamp: 引数の順が読みにくい"
ASKED = "stats.py mean: 空の列の扱い"
DEP = "stats.py mean: 空の列の試験"


def dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False)


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
    return {"unit_keys": list(keys), "approach": "mean の分母を len(xs) に、clamp の上限の枝を hi に直す", "files": [],
            "shrink_first": "足す物は無い。式と戻り値を 1 か所ずつ直すだけで足りる", "narrows": [],
            "route": "tdd",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均がその真ん中の値になる",
                       "path": "stats.mean を本物のまま呼び、戻り値を断言する", "red_kind": "assertion",
                       "red_why": "今の分母は len(xs) - 1 なので mean([1, 3]) が 4.0 を返す"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""},
            "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": [], **more}


def _frow(path, *adds, **over):
    """files の 1 行（足す symbol の並び。home の考えの名は行の path ごとに違う字で、considered は根に置く 1 段の path 1 つ）"""
    return {"path": path, "op": "modify", "responsibility": "この行の受け持ち",
            "home": {"concept": f"{path} の考え", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
            "symbols": [{"name": n, "change": "add"} for n in adds], **over}


def face(key, units, severity="block"):
    return {"key": key, "kind": "regression", "where": f"{key} の場所", "why": f"{key} が穴である理由",
            "severity": severity, "unit_keys": list(units)}


def answer(key, handled="fixed", how="案の項目 1 の手順を直した"):
    return {"key": key, "handled": handled, "how": how}


# ---------------------------------------------------------------- 往復の記録（line が組む物を試験が組む）
def plan_step(rows, answers=None):
    return ("plan", rows, answers)


def review_step(faces, resolved=()):
    return ("review", faces, list(resolved))


def record(*events) -> dict:
    """往復の記録（prior.record の形）。line と同じく、受けた事前審査ごとに converge.add_pass を当て、受けた案の行を converge.plan_rows で
    置く（今の planfile.converge_record の中身）。審査はその前の一番新しい案を審査した物で、答えはその案の返答の block_answers"""
    doc = {"round": 0, "passes": [], "outcome": None, "open": {}}
    answers: list = []
    for kind, rows, extra in events:
        if kind == "plan":
            doc["plan"] = converge.plan_rows(rows)
            answers = list(extra or [])
        elif doc.get("plan"):
            converge.add_pass(doc, {"faces": rows, "resolved": extra}, answers=copy.deepcopy(answers), resolved=extra)
    return doc


class PlaceCase(unittest.TestCase):
    """使い捨ての run directory（place）と、stats.py・test_stats.py を持つ git の作業ツリー。src の関数は script と同じ環境で呼ぶ
    （網に出ない。run をまたぐ控えの置き場は渡さない）"""

    def setUp(self):
        self.run = kit.Run(self, "plan")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, base.SEED)
        self.repo, self.place = self.run.repo, self.run.artifacts
        self.enterContext(self.run.env())
        self.enterContext(mock.patch.dict(os.environ, {"WORKS_LIBDOCS_WEB": "off"}))
        os.environ.pop(ports.SHARED_CACHE_ENV, None)

    def intake(self, **inputs) -> dict:
        """入口を port の値で回す（YAML の既定の字に、渡した物だけを替える。judgment の既定はこのモジュールの見本の値）"""
        raw = base.defaults()
        raw["judgment"] = dump(judgment())
        raw.update({k: v if isinstance(v, str) else dump(v) for k, v in inputs.items()})
        return steps.intake(self.place, self.repo, files.next_round(self.place, raw["prior"]), raw)

    def opened(self, **inputs) -> tuple:
        """入口を回して (周のフォルダ, intake.json の値)。役を起こす周であること"""
        got = self.intake(**inputs)
        self.assertTrue(got["go"], got)
        return steps.load(self.place)

    def artifact(self, rel, doc, *, lines=False) -> str:
        """run directory に置いたファイルの pointer の字"""
        p = self.place / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(dump(r) + "\n" for r in doc) if lines else dump(doc), encoding="utf-8")
        return self.run.pointer(rel)

    def read(self, path):
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


class OwedCase(unittest.TestCase):
    """元 conflict.py:676 の owed_units_but_asked（開いた単位から、答えていない関所の問い——人に聞く状態の fork と status が escalate の
    問い——の出どころ・depends を除く）と元 review-record.py:624 の is_open"""

    def test_owed_is_open_units_minus_asking_fork_origin_and_depends(self):
        self.assertEqual(steps._owed_units(judgment()), {MEAN, CLAMP})

    def test_open_is_block_or_do_now_suggest(self):
        self.assertEqual([steps.is_open(u) for u in judgment()["units"]], [True, True, False, False, True, True])

    def test_decided_fork_and_held_non_fork_do_not_excuse(self):
        doc = judgment()
        doc["questions"] = [{"key": "q", "kind": "fork", "status": "decided", "origin": ASKED, "depends": [DEP]},
                            {"key": "r", "kind": "scope", "status": "held", "origin": CLAMP}]
        self.assertEqual(steps._owed_units(doc), {MEAN, CLAMP, ASKED, DEP})

    def test_escalated_fork_excuses(self):
        doc = judgment()
        doc["questions"][0]["status"] = "escalate"
        self.assertEqual(steps._owed_units(doc), {MEAN, CLAMP})

    def test_escalated_non_fork_excuses_origin_and_depends(self):
        """元の差し替えは写しの RL が外さない escalate の問い（fork でない）の出どころ・depends も外す（gatemarks.asks・withheld）"""
        doc = judgment(questions=[{"key": "r", "kind": "scope", "status": "escalate", "origin": CLAMP, "depends": [MEAN]}])
        self.assertEqual(steps._owed_units(doc), set())

    def test_broken_rows_are_not_read(self):
        self.assertEqual(steps._owed_units({"units": ["x", {"label": "block"}], "questions": "q"}), set())

    def test_depends_that_is_not_a_list_is_not_read(self):
        """depends が並びでない（数）問いでも落ちない。出どころは外し、depends は読まない"""
        doc = judgment()
        doc["questions"][0]["depends"] = 3
        self.assertEqual(steps._owed_units(doc), {MEAN, CLAMP, DEP})

    def test_owed_order_follows_the_judgment(self):
        doc = judgment(questions=[{"key": "r", "kind": "scope", "status": "escalate", "origin": MEAN}])
        self.assertEqual(steps.owed_order(doc), [CLAMP])
        self.assertEqual(steps.owed_order(judgment()), [MEAN, CLAMP])

    def test_ledger_beside_the_judgment_is_read(self):
        """with_ledger が添えた問いの台帳の見え方（依頼の answers が答えた問い）を数えに使う: 答えた fork の出どころ・depends は義務に戻る"""
        ctx = {"answers": [{"question": "q-asked", "text": "空の列は 0 を返す"}], "takes_push": False}
        doc = steps.with_ledger(ctx, judgment())
        self.assertIn(steps.LEDGER, doc)
        self.assertEqual(steps._owed_units(doc), {MEAN, CLAMP, ASKED, DEP})
        self.assertIsNone(steps.with_ledger(ctx, "判定でない"))


class SlotsCase(unittest.TestCase):
    """元 planblk の plan_slots・stuck_reason・not_allowed（番号は開いた単位に 1 から）"""

    def test_slots_number_open_units_in_order(self):
        self.assertEqual(steps.slots(judgment()), [MEAN, CLAMP, ASKED, DEP])

    def test_plan_slots_must_may_and_units(self):
        must, may, units = steps.plan_slots(judgment())
        self.assertEqual(must, {MEAN, CLAMP})
        self.assertEqual(may, {MEAN, CLAMP, ASKED, DEP})
        self.assertLessEqual(must, may)
        self.assertEqual(set(units), {MEAN, CLAMP, NIT, DEFER, ASKED, DEP})

    def test_no_stuck_unit_when_every_owed_unit_is_open(self):
        self.assertEqual(steps.stuck_reason(judgment()), "")
        self.assertEqual(steps.held_why(judgment()), "")

    def test_stuck_names_owed_unit_that_is_not_open(self):
        """必ず入れるのに開いていない単位（元は関所で答えた問いの出どころが defer）が在れば、行き止まりの理由が番号と key を名指す"""
        with mock.patch.object(judgmark, "owed_units", return_value={MEAN, DEFER}):
            why = steps.stuck_reason(judgment())
            self.assertEqual(steps.held_why(judgment()), why)
        self.assertTrue(why.startswith(steps.PLAN_STUCK), why)
        self.assertIn(f"no の一覧に無い単位（{DEFER}）", why)
        self.assertIn(steps.STUCK_WHY, why)

    def test_held_why_names_nothing_owed_and_unreadable(self):
        self.assertEqual(steps.held_why({"units": [unit(NIT, "nit", None)], "questions": []}), steps.NOTHING_OWED)
        self.assertEqual(steps.held_why(None), "判定が読めない")

    def test_not_allowed_names_label_of_unit_without_duty(self):
        reply = {"plan": [item(MEAN, CLAMP, NIT)]}
        got = steps.not_allowed(judgment(), reply)
        self.assertEqual(len(got), 1, got)
        self.assertIn("label=nit", got[0])
        self.assertEqual(steps.not_allowed(judgment(), {"plan": [item(MEAN, CLAMP, ASKED)]}), [])

    def test_not_allowed_keeps_plan_order_and_repeats(self):
        """同じ単位を 2 つの案に入れたら拒む行も 2 つ（converge.plan_keys の順と重複のまま）"""
        got = steps.not_allowed(judgment(), {"plan": [item(MEAN, NIT), item(CLAMP, NIT)]})
        self.assertEqual(len(got), 2, got)
        self.assertEqual(got[0], got[1])
        self.assertIn("label=nit", got[0])

    def test_not_allowed_reads_past_broken_rows(self):
        self.assertEqual(steps.not_allowed(judgment(), {"plan": ["x", {"unit_keys": 5}]}), [])

    def test_named_turns_numbers_into_ids_and_keeps_unknown_numbers(self):
        reply = {"plan": [item(1, 2), item(CLAMP, 9)]}
        got = steps.named(reply, [MEAN, CLAMP])
        self.assertEqual([p["unit_keys"] for p in got["plan"]], [[MEAN, CLAMP], [CLAMP, 9]])
        self.assertEqual(reply["plan"][0]["unit_keys"], [1, 2], "役の返答は書き換えない")

    def test_named_turns_depends_on_units_into_ids(self):
        """named が depends_on[].unit の no を単位の名に戻す（unit_keys と同じ表 UNIT_REFS）。字の unit・slots に無い no・形の崩れた欄は
        そのまま通す"""
        later = item(CLAMP, depends_on=[{"unit": 1, "receives": ["stats.py::mean"]}, {"unit": CLAMP, "receives": ["stats.py"]},
                                        {"unit": 9, "receives": ["x.py"]}])
        reply = {"plan": [item(1), later, item(2)]}
        got = steps.named(reply, [MEAN, CLAMP])
        self.assertEqual([r["unit"] for r in got["plan"][1]["depends_on"]], [MEAN, CLAMP, 9])
        self.assertEqual(got["plan"][0].get("depends_on"), None)
        self.assertEqual(reply["plan"][1]["depends_on"][0]["unit"], 1, "役の返答は書き換えない")
        self.assertEqual(steps.named({"plan": [{"unit_keys": [1], "depends_on": "壊れ"}, "項目でない"]}, [MEAN])["plan"][0],
                         {"unit_keys": [MEAN], "depends_on": "壊れ"})

    def test_unit_name_turns_only_numbers_in_range(self):
        names = [MEAN, CLAMP]
        self.assertEqual([steps.unit_name(names, k) for k in (1, 2, 0, 3, True, "1")], [MEAN, CLAMP, 0, 3, True, "1"])


class CoversCase(unittest.TestCase):
    """元 rules/review-loop.py:3077 の fix_plan_covers_units（例外の代わりに行を返す）"""
    owed, opened = {MEAN, CLAMP}, {MEAN, CLAMP, ASKED}

    def covers(self, *rows):
        return steps.fix_plan_covers_units([{"unit_keys": list(r)} for r in rows], self.owed, self.opened)

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


class ReplanErrorsCase(PlaceCase):
    """元 replan._plan_errors（数・unit_keys の字・works の欄・狭めない案を全部並べて 1 回で拒む。元 tests/test_replan.py の
    test_reply_limited_to_handed_items・test_all_errors_in_one_rejection）。今は take.plan_errors"""

    def setUp(self):
        super().setUp()
        self.rows = [{"item": 1, "old": item(MEAN)}]

    def errors(self, reply, whole=None):
        return take.plan_errors(self.rows, reply, self.repo, take.exists_at(self.repo, "HEAD"), [],
                                [item(MEAN)] if whole is None else whole)

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

    def test_malformed_reply_skips_the_field_checks(self):
        """形の崩れた返答は数と unit_keys の行だけで拒む（欄の照らしに渡して落ちない）"""
        got = self.errors({"plan": "x"})
        self.assertEqual(got, ["plan[] は 1 項目（貼った項目の数）"])

    def test_depends_on_reads_the_whole_plan_with_revised_items(self):
        """案の直しで、2 項目の案の 2 番目だけを直した返答を扱う。直さない 1 番目の単位を字で指す depends_on は通る。1 番目を直して
        受けられる物を外すと、直さない 2 番目の受けの切れが拒まれる（直した項目だけを見ると、直さない項目を指す行を誤って拒み、
        直さない項目の受けの切れを見逃す）"""
        first = item(MEAN, files=[_frow("stats.py", "mean")])
        second = item(CLAMP, depends_on=[{"unit": MEAN, "receives": ["stats.py::mean"]}])
        whole = [first, second]
        self.rows = [{"item": 2, "old": second}]
        revised = item(CLAMP, depends_on=[{"unit": MEAN, "receives": ["stats.py::mean"]}], approach="clamp の上限の枝を hi に直す。mean を使う")
        self.assertEqual(self.errors({"plan": [revised]}, whole), [])
        cut_first = item(MEAN, files=[_frow("stats.py", "other")])
        self.rows = [{"item": 1, "old": first}]
        got = self.errors({"plan": [cut_first]}, whole)
        self.assertEqual(len([g for g in got if g.startswith("plan[1].depends_on[0].receives[0]")]), 1, got)
        loop = item(MEAN, depends_on=[{"unit": CLAMP, "receives": ["stats.py"]}], files=[_frow("stats.py", "mean")])
        got = self.errors({"plan": [loop]}, whole)
        self.assertTrue(any(g.startswith("plan.depends_on") and "循環" in g for g in got), got)
        self.assertEqual(self.errors({"plan": [first]}, whole), [], "直さない項目の受けは切れていない")

    def test_home_concept_is_read_over_the_whole_plan(self):
        """案の直しで、直した項目の行の home.concept が、直さない承認済みの項目の行の考えと同じなら、拒否の行が出る（直した項目だけを
        見ると、直さない項目の行と考えが重なるのを見逃す）。考えが分かれていれば出ない"""
        first = item(MEAN, files=[_frow("stats.py", "mean")])
        second = item(CLAMP)
        self.rows = [{"item": 2, "old": second}]
        apart = item(CLAMP, files=[_frow("test_stats.py", "clamp")])
        self.assertEqual(self.errors({"plan": [apart]}, [first, second]), [])
        twice = item(CLAMP, files=[_frow("test_stats.py", "clamp", home={"concept": " STATS.py の考え", "why": "ここが住処だから"})])
        got = self.errors({"plan": [twice]}, [first, second])
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[1].files[0].home.concept") and "plan[0].files[0]" in got[0], got)

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
            take.exists_at(self.repo, "no-such-rev")


class PrescriptionCase(PlaceCase):
    """元 planmarks.prescriptions（判定の返答の単位ごとの処方。空の処方は入れない）と planblk.prescription_section（今は brief の
    prescription_rows の行と、判定の記録のパスの値。見出しと頼みの文は md が持つ）"""

    def test_prescriptions_skip_blank(self):
        self.assertEqual(steps.prescriptions(judgment()), {MEAN: ["分母を len(xs) にする"]})
        self.assertEqual(steps.prescriptions({"units": "x"}), {})

    def test_rows_list_units_that_may_be_in_the_plan_only(self):
        """処方の行は案に入れてよい単位（必ず入れる物を含む）の物だけ。開いていない単位の処方は貼らない"""
        doc = judgment()
        doc["units"][2]["prescriptions"] = ["変数名を長くする"]   # NIT（開いていない）
        got = brief.prescription_rows(doc)
        self.assertEqual(got, f"### {MEAN}\n\n1. 分母を len(xs) にする")
        self.assertNotIn(NIT, got)
        self.assertNotIn(f"### {CLAMP}", got)
        self.assertEqual(brief.prescription_rows({"units": [unit(CLAMP)], "questions": []}), "")

    def test_values_name_the_judgment_file(self):
        """処方を決め手に引く先（判定の記録の絶対パス）を名指す: 値で受けた判定は周のフォルダの写し、pointer で受けた判定はその先"""
        folder, ctx = self.opened()
        v, w = brief.values(self.place, self.repo)
        self.assertEqual(v["judgment_file"], str(folder / files.JUDGMENT_COPY))
        self.assertEqual(self.read(v["judgment_file"]), judgment())
        self.assertTrue(w["prescriptions"])
        self.assertIn(f"### {MEAN}", v["prescriptions"])
        self.opened(judgment=self.artifact("judge/judgment.json", judgment()))
        v, _ = brief.values(self.place, self.repo)
        self.assertEqual(v["judgment_file"], str(self.place / "judge" / "judgment.json"))


class RepoLineCase(PlaceCase):
    """P035 のリポジトリの行の値（修正役の md の `Repository: {repo} (version read: {read_rev}) BASE: {diff_base}`）。読む版は review_rev、
    空なら base、それも空なら HEAD。BASE は diff_base、空なら base、それも空なら読む版"""

    def values(self, **inputs):
        self.opened(**inputs)
        v, _ = brief.values(self.place, self.repo)
        return v["repo"], v["read_rev"], v["diff_base"], v["review_md"]

    def test_blank_base_falls_back_to_review_rev(self):
        repo, read_rev, diff_base, review_md = self.values(review_rev="abc")
        self.assertEqual((repo, read_rev, diff_base), (str(self.repo), "abc", "abc"))
        self.assertEqual(self.values(review_rev="abc", base="def")[1:3], ("abc", "def"))
        self.assertEqual(self.values(review_rev="abc", base="def", diff_base="ghi")[1:3], ("abc", "ghi"))
        self.assertEqual(self.values(base="def")[1:3], ("def", "def"))
        self.assertEqual(self.values()[1:3], ("HEAD", "HEAD"))

    def test_review_md_is_the_lib_viewpoint_file(self):
        review_md = pathlib.Path(self.values()[3])
        self.assertEqual(review_md, ports.lib_root() / "REVIEW.md")
        self.assertTrue(review_md.is_file())


class BaseTestsCase(PlaceCase):
    """元 writes.base_test_texts（修正前の版のテストのファイルの中身。読めない物は含めず、返りの 2 つ目に名指す）"""

    def test_texts_of_tests_at_rev(self):
        rev = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "test_stats.py").write_text("# 作業ツリーだけの書き換え\n", encoding="utf-8")
        texts, unread = take.base_test_texts(self.repo, rev)
        self.assertEqual(unread, [])
        self.assertIn("test_stats.py", texts)
        self.assertIn("def test_mean_of_three", texts["test_stats.py"])
        self.assertNotIn("stats.py", texts)

    def test_non_utf8_test_file_is_unread_not_an_exception(self):
        rev = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "test_latin.py").write_bytes("# caf\xe9\n".encode("latin-1"))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "latin-1")
        rev = git(self.repo, "rev-parse", "HEAD")
        texts, unread = take.base_test_texts(self.repo, rev)
        self.assertEqual(unread, ["test_latin.py"])
        self.assertIn("test_stats.py", texts)
        self.assertIsNone(take.exists_at(self.repo, rev)("test_latin.py::test_x"), "読めない版のファイルは『その版に無い』と同じ扱い")

    def test_unreadable_rev_names_rev(self):
        self.assertEqual(take.base_test_texts(self.repo, "no-such-rev"), ({}, ["<版>"]))


class ConvergeCase(unittest.TestCase):
    """往復の記録の読み口（filled_units・splice・answer_gaps）と、修正案の役に返す往復の材料の値（brief.revise_values。元
    converge.revise_section）。記録を周のフォルダから組み直す照らし（元 converge_record）は line へ移ったので写さない"""

    def blocked_first(self):
        return record(plan_step([item("u1"), item("u2")]), review_step([face("key-a1", ["u1"])]))

    def states(self, doc):
        return [it["state"] for it in doc["passes"][-1]["items"]]

    def test_blocked_item_opens_and_clean_item_closes(self):
        got = record(plan_step([item("u1"), item("u2")]),
                     review_step([face("key-a1", ["u1"]), face("key-s1", ["u2"], severity="suggest")]))
        self.assertEqual(self.states(got), [converge.OPEN, converge.CLOSED])
        self.assertEqual(got["outcome"], converge.AGAIN)

    def test_same_block_twice_holds_item(self):
        got = record(plan_step([item("u1"), item("u2")]),
                     review_step([face("key-a1", ["u1"]), face("key-b1", ["u2"])]),
                     plan_step([item("u1", approach="直した案の手順をここに書いた"), item("u2", approach="直した案の手順をここに書いた")],
                               [answer("key-a1"), answer("key-b1")]),
                     review_step([face("key-a1", ["u1"]), face("key-b2", ["u2"])], resolved=["key-b1"]))
        self.assertEqual(self.states(got), [converge.HELD, converge.OPEN])
        self.assertEqual(got["passes"][1]["answers"], [answer("key-a1"), answer("key-b1")])

    def test_filled_units_are_every_item_with_a_row(self):
        self.assertEqual(converge.filled_units(self.blocked_first()), ["u1", "u2"])
        self.assertEqual(converge.filled_units(take.EMPTY_RECORD), [])

    def test_answer_gaps_need_one_answer_per_open_block(self):
        doc = self.blocked_first()
        self.assertEqual(converge.answer_gaps(doc, [answer("key-a1")]), [])
        gaps = converge.answer_gaps(doc, [answer("key-a1", handled="ignored"), answer("key-z")])
        self.assertTrue(any("handled" in g for g in gaps), gaps)
        self.assertIn("key-z は前の往復の答えの要る穴（block と開いた項目の suggest）に無い", gaps)
        self.assertIn("block の key key-a1 への答えが無い", converge.answer_gaps(doc, []))

    def test_no_answers_asked_on_first_round(self):
        doc = record(plan_step([item("u1")]))
        self.assertEqual(converge.answer_gaps(doc, []), [])
        self.assertEqual(converge.answer_gaps(take.EMPTY_RECORD, [answer("key-x")]),
                         ["key-x は前の往復の答えの要る穴（block と開いた項目の suggest）に無い"])

    def test_splice_fills_closed_item_and_refuses_changed_one(self):
        doc = self.blocked_first()
        fixed = item("u1", approach="直した案の手順をここに書いた")
        whole, rejects, dropped = converge.splice(doc, [fixed])
        self.assertEqual((rejects, dropped), ([], []))
        self.assertEqual(whole, [fixed, item("u2")])
        _, rejects, dropped = converge.splice(doc, [fixed, item("u2")])
        self.assertEqual((rejects, dropped), ([], ["u2"]), "閉じた項目を前のまま書いた行は捨てる")
        _, rejects, _ = converge.splice(doc, [fixed, item("u2", approach="閉じた項目を書き換えてしまった")])
        self.assertEqual(len(rejects), 1, rejects)
        self.assertIn("閉じた項目 2 を変えた", rejects[0])

    def test_splice_fills_missing_open_item(self):
        """#571: 返答に無い開いた項目は前の往復の行を差し込む（役は変えた項目だけを返す）"""
        whole, rejects, _ = converge.splice(self.blocked_first(), [])
        self.assertEqual((whole, rejects), ([item("u1"), item("u2")], []))

    def test_splice_without_passes_takes_reply(self):
        rows = [item("u1"), item("u9")]
        self.assertEqual(converge.splice(record(plan_step([item("u1")])), rows), (rows, [], []))
        self.assertEqual(converge.splice(take.EMPTY_RECORD, rows), (rows, [], []))

    def test_revise_values_name_blocks_and_closed_items(self):
        got = brief.revise_values(self.blocked_first())
        self.assertTrue(got["revise"])
        self.assertTrue(got["closed_items"])
        self.assertFalse(got["held_items"])
        self.assertFalse(got["owed_suggests"])
        self.assertTrue(got["revise_keys"], "suggest の穴の行が無い往復は key の行を出す")
        v = got["values"]
        self.assertTrue(v["revise_blocks"].startswith("### key-a1\n- kind: regression"), v["revise_blocks"])
        self.assertEqual(v["revise_pass"], "1")
        self.assertEqual(v["closed_items"], "- Item 2 (u2)")
        self.assertEqual(v["suggest_keys"], "none")

    def test_revise_values_split_owed_suggests_and_notes(self):
        """開いた項目に付いた suggest は答えの要る穴、閉じた項目に付いた suggest は参考の行（答えなくてよい）"""
        doc = record(plan_step([item("u1"), item("u2")]),
                     review_step([face("key-a1", ["u1"]), face("key-s1", ["u1"], severity="suggest"),
                                  face("key-s2", ["u2"], severity="suggest")]))
        got = brief.revise_values(doc)
        self.assertTrue(got["owed_suggests"] and got["revise_notes"])
        self.assertFalse(got["revise_keys"])
        self.assertIn("### key-s1", got["values"]["owed_suggests"])
        self.assertIn("### key-s2", got["values"]["revise_notes"])
        self.assertNotIn("key-s1", got["values"]["revise_notes"])

    def test_no_revise_without_a_returned_pass(self):
        for doc in (take.EMPTY_RECORD, record(plan_step([item("u1")]))):
            got = brief.revise_values(doc)
            self.assertFalse(any(got[k] for k in ("revise", "owed_suggests", "revise_notes", "revise_keys", "closed_items", "held_items")))
            self.assertEqual(set(got["values"].values()), {""})


class UnitsSectionCase(unittest.TestCase):
    """材料の単位の行: 前の往復の案の項目の単位は、開いた項目も『必ず案に入れる』でなく、機械が差し込む行に分ける（splice が返答に無い
    項目を全部差し込むので、md の「変えない項目は書かなくてよい」と食い違わない。#571）"""

    def test_filled_units_are_not_owed_in_the_brief(self):
        doc = record(plan_step([item(MEAN), item(CLAMP)]), review_step([face("key-a1", [MEAN])]))
        filled = converge.filled_units(doc)
        self.assertEqual(filled, [MEAN, CLAMP])
        text, nos, _ = brief.units_rows(judgment(), [], filled)
        self.assertIn(f"- no 1 `{MEAN}`: label=block・disposition=do-now・{brief.DUTY_FILLED}", text)
        self.assertIn(f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{brief.DUTY_FILLED}", text)
        self.assertNotIn(brief.DUTY_OWED, text)
        self.assertEqual(nos, [1, 2])
        self.assertEqual(brief.units_rows(judgment(), [], [])[1], [])

    def test_rows_name_duty_catalog_and_shut_units(self):
        catalog = base.catalog()
        text, _, shut = brief.units_rows(judgment(), catalog, [])
        self.assertEqual(text.splitlines()[:3], [f"- no 1 `{MEAN}`: label=block・disposition=do-now・{brief.DUTY_OWED}",
                                                 "  - paths: stats.py", "  - summary: mean の分母"])
        self.assertIn(f"- no 3 `{ASKED}`: label=suggest・disposition=do-now・{brief.DUTY_MAY}", text)
        self.assertEqual(shut, f"`{NIT}` (label=nit・disposition=none), `{DEFER}` (label=suggest・disposition=defer)")
        self.assertEqual(brief.units_rows({"units": [unit(MEAN)], "questions": []}, "目録でない", [])[2], "none")


class ReplanInputsCase(unittest.TestCase):
    """案の直しの材料: 裁定の種類で絞った申し出の行（steps.conflict_rows）と裁定の文（ruling_text）"""

    def test_conflict_rows_are_fix_plan_item_rulings_only(self):
        rows = [{"id": "c1", "unit_key": MEAN, "ruling": {"decision": "fix_plan_item", "plan_items": [1]}},
                {"id": "c2", "unit_key": MEAN, "ruling": {"decision": "ask_human"}},
                {"id": "c3", "unit_key": "ほかの単位", "ruling": {"decision": "fix_plan_item", "plan_items": [2]}},
                {"id": "c4", "unit_key": MEAN, "ruling": "壊れた"}]
        got = steps.conflict_rows({"items": rows}, 1, item(MEAN))
        self.assertEqual([c["id"] for c in got], ["c1"])

    def test_conflict_rows_compare_unit_keys_as_text(self):
        rows = [{"id": "c1", "unit_key": 7, "ruling": {"decision": "fix_plan_item"}}]
        self.assertEqual([c["id"] for c in steps.conflict_rows({"items": rows}, 1, item("7"))], ["c1"])

    def test_conflict_rows_read_the_replan_decision_from_conflict(self):
        rows = [{"id": "c1", "unit_key": MEAN, "ruling": {"decision": "renamed"}}]
        with mock.patch.object(conflict, "REPLAN", "renamed"):
            self.assertEqual([c["id"] for c in steps.conflict_rows({"items": rows}, 1, item(MEAN))], ["c1"])
        self.assertFalse(hasattr(steps, "REPLAN_DECISION"))

    def test_conflict_rows_read_past_missing_conflicts(self):
        self.assertEqual(steps.conflict_rows(None, 1, item(MEAN)), [])

    def test_ruling_text_joins_rulings_or_names_no_rows(self):
        rows = [{"ruling": {"text": "項目 1 の手順を直す"}}, {"ruling": {"text": "試験を足す"}}]
        self.assertEqual(steps.ruling_text(rows), "項目 1 の手順を直す／試験を足す")
        self.assertEqual(steps.ruling_text([]), steps.NO_ROWS)


class WorldRowsCase(PlaceCase):
    """世界の解の行: 入口が行ごとの JSON を先に照らして周に名指し、brief.world_lines が英語の札で 1 類ずつ行にする"""

    def test_world_of_two_rows_is_read_as_json_lines(self):
        """#295: 判定の world.jsonl は行ごとの JSON。2 行を 1 つの JSON として読む読み手はここで落ちる"""
        rows = [base.WORLD_ROW, {**base.WORLD_ROW, "finding": 2, "class_id": "w-empty"}]
        _, ctx = self.opened(world_rows=self.artifact("judge/world.jsonl", rows, lines=True))
        self.assertEqual(ctx["world_rows"], str(self.place / "judge" / "world.jsonl"))
        self.assertEqual([r["class_id"] for r in worldmark.rows(ctx["world_rows"])], ["mean-denominator", "w-empty"])
        v, w = brief.values(self.place, self.repo)
        self.assertTrue(w["world"])
        self.assertEqual(v["world_rows"].count("- Class "), 2)

    def test_unreadable_world_rows_hold_the_plan_round(self):
        bad = self.place / "judge" / "world.jsonl"
        bad.parent.mkdir(parents=True)
        bad.write_text("{壊れた行\n", encoding="utf-8")
        got = self.intake(world_rows=self.run.pointer("judge/world.jsonl"))
        self.assertFalse(got["go"])
        self.assertIn("world_rows が読めない", got["reason"])

    def test_same_row_lines(self):
        self.assertEqual(brief.world_lines([base.WORLD_ROW]).splitlines(), [
            "- Class mean-denominator (request line 1・stats.py): 平均の分母の取り違え (activity: 算術)",
            f"  - Practice: 算術平均は要素の数で割る ({brief.NOT_WEB})",
            "  - Applies: mean の分母",
            "  - The request's way 「分母を直す」 is the same as the practice"])

    def test_differs_row_lines_carry_sources_challenge_and_not_applies(self):
        row = {**base.WORLD_ROW, "basis": worldmark.WEB, "not_applies": "空の列",
               "sources": [{"id": "s1", "url": "https://example.org/mean", "excerpt": "divide by n"}, "壊れ"],
               "versus": {"proposed": "分母を直す", "verdict": worldmark.DIFFERS, "challenge": "n で割る"}}
        self.assertEqual(brief.world_lines([row]).splitlines()[1:], [
            "  - Practice: 算術平均は要素の数で割る",
            "  - Source s1: https://example.org/mean「divide by n」",
            "  - Applies: mean の分母／Does not apply: 空の列",
            "  - The request's way 「分母を直す」 is different from the practice——n で割る"])

    def test_row_without_a_way_or_applies(self):
        row = {**base.WORLD_ROW, "applies": "", "versus": {"proposed": "", "verdict": worldmark.NONE, "challenge": ""}}
        self.assertEqual(brief.world_lines([row]).splitlines()[-2:], [
            "  - Applies: none (a row that needs no answer)", "  - the request shows no way to solve it"])


class PriorFailuresCase(PlaceCase):
    """前の run で最後まで通らなかった物（元 planblk.prior_part の carry.prior_section）: 入口が周のフォルダに写しを置き、
    brief.prior_failure_rows が作り直しの行と分けて 1 件 1 行にする"""

    ROWS = [{"where": "修正案の受け付け", "text": "単位の網羅が 3 回とも欠けた"}]

    def test_rows_are_kept_in_the_round(self):
        folder, ctx = self.opened(prior_failures=self.ROWS)
        self.assertEqual(self.read(folder / files.PRIOR_FAILURES_IN), self.ROWS)
        self.assertEqual(ctx["prior_failures"], self.ROWS)
        folder, _ = self.opened()
        self.assertEqual(self.read(folder / files.PRIOR_FAILURES_IN), [])

    def test_rows_split_notes_and_redesign(self):
        redesign = {"where": carry.REDESIGN_WHERE, "text": "住処を分け直す"}
        self.assertEqual(brief.prior_failure_rows([*self.ROWS, redesign, "行でない"]),
                         ("- 修正案の受け付け: 単位の網羅が 3 回とも欠けた", f"- {carry.REDESIGN_WHERE}: 住処を分け直す"))
        self.assertEqual(brief.prior_failure_rows([]), ("", ""))

    def test_wrong_shape_is_named_unread_not_raised(self):
        """形の違う前の失敗は役を止めず、intake.json の unread に名指して空と読む（元は ValueError。今は 4 節の『ほかの port』）"""
        for bad in ({"where": "x"}, [{"where": "x"}], ["x"]):
            with self.subTest(bad=bad):
                folder, ctx = self.opened(prior_failures=bad)
                self.assertEqual(ctx["prior_failures"], [])
                self.assertTrue(any(u.startswith("prior_failures: ") for u in ctx["unread"]), ctx["unread"])
                self.assertEqual(self.read(folder / files.PRIOR_FAILURES_IN), [])


class VerifyNeighborCase(PlaceCase):
    """L-W10: 判定の単位の裏取りの申し送り（判定の出力の欄 verify の先）を修正案の役の材料に貼る（元 planblk.verify_part。今は
    brief.verify_rows の英語の札の行）"""

    DOC = {"units": [{"n": 1, "key": "a.py 分母", "state": "checked", "verdict": "root", "evidence_found": True, "evidence": "a.py:3",
                      "location_ok": True, "location": "a.py:3", "why": "確か"}], "synergy": {}}

    def test_verify_rows(self):
        self.assertEqual(brief.verify_rows(self.DOC).splitlines(), [
            "- Unit 1 `a.py 分母`: the root・evidence found (a.py:3)・place matches (a.py:3). 確か", "",
            "Synergy between units: could not be checked ()"])

    def test_unchecked_unit_and_synergy(self):
        doc = {"units": [{"n": 2, "key": "b", "state": "failed", "errors": ["読めない"]},
                         {"n": 3, "key": "c", "state": "checked", "verdict": "not_root", "real_root": "d.py", "evidence_found": False,
                          "evidence": "", "location_ok": False, "location": "c.py:1", "why": "違う"}, "行でない"],
               "synergy": {"state": "checked", "why": "同じ枝", "duplicates": [{"units": ["b", "c"], "why": "同じ穴"}],
                           "relations": [{"units": ["b"], "place": "apart", "why": "別の所"}],
                           "order": [{"first": "b", "then": "c", "why": "受けが先"}]}}
        self.assertEqual(brief.verify_rows(doc).splitlines(), [
            "- Unit 2 `b`: could not be checked (読めない)",
            "- Unit 3 `c`: not the root (real root: d.py)・evidence missing ()・place differs (c.py:1). 違う", "",
            "Synergy between units: 同じ枝",
            "- duplicate: `b`・`c` (同じ穴)",
            "- related (different place): `b` (別の所)",
            "- order: `b` first, then `c` (受けが先)"])

    def test_verify_notes_reach_the_values(self):
        self.opened(verify=self.artifact("judge/judge-verify.json", self.DOC))
        v, w = brief.values(self.place, self.repo)
        self.assertTrue(w["verify"])
        self.assertFalse(w["verify_unreadable"])
        self.assertIn("- Unit 1 `a.py 分母`: ", v["verify_rows"])

    def test_unreadable_verify_names_the_file(self):
        ptr = self.artifact("judge/judge-verify.json", ["申し送りでない"])
        self.opened(verify=ptr)
        v, w = brief.values(self.place, self.repo)
        self.assertTrue(w["verify_unreadable"])
        self.assertFalse(w["verify"])
        self.assertEqual(v["verify_file"], str(self.place / "judge" / "judge-verify.json"))


class HeadDepthNeighborCase(PlaceCase):
    """判定の出力の欄 depth_record の先の頭の深さの控えの行ごとの未知の種類を、形 plan の修正案の役の材料に貼る（brief.unknown_rows。
    種類ごとの指示の文は md の断片 unknown-asks が持つ）"""

    ITEMS = [{"item": 1, "unknown": "範囲", "cause_quote": "設定の鍵に響く", "where": "a.py:3", "code_quote": "KEY = 1"},
             {"item": 2, "unknown": "形", "cause_quote": "二通りの直し方", "where": "a.py:5", "code_quote": "def pick():"},
             {"item": 3, "unknown": "原因", "cause_quote": "落ちる訳", "where": "", "code_quote": ""},
             {"item": 4, "unknown": "表に無い種類", "cause_quote": "x"}]

    def test_head_depth_kinds_reach_the_rows(self):
        """控えが在れば種類・番地の行、控えが無ければ行が無く訳だけ"""
        self.assertEqual(brief.unknown_rows(""), ("", headdepth.NO_RECORD))
        jdir = self.place / "judge"
        path = headdepth.write(jdir, headdepth.record(headdepth.tier_of(self.ITEMS), "設計の選び", items=self.ITEMS))
        rows, why = brief.unknown_rows(str(path))
        self.assertEqual(why, "設計の選び")
        self.assertEqual(rows.splitlines(), [
            "- line 1 (範囲): request text 「設定の鍵に響く」・place a.py:3「KEY = 1」",
            "- line 2 (形): request text 「二通りの直し方」・place a.py:5「def pick():」",
            "- line 3 (原因): request text 「落ちる訳」・place: none (the cause is not visible in code)"])

    def test_values_switch_between_rows_and_none(self):
        self.opened()
        v, w = brief.values(self.place, self.repo)
        self.assertEqual((w["unknown_rows"], w["unknown_none"], v["unknown_why"]), (False, True, headdepth.NO_RECORD))
        path = headdepth.write(self.place / "judge", headdepth.record(headdepth.tier_of(self.ITEMS), "設計の選び", items=self.ITEMS))
        self.opened(depth_record=self.run.pointer(path.relative_to(self.place).as_posix()))
        v, w = brief.values(self.place, self.repo)
        self.assertEqual((w["unknown_rows"], w["unknown_none"]), (True, False))
        self.assertEqual((v["kind_none"], v["kind_cause"], v["kind_shape"], v["kind_scope"]),
                         (headdepth.NONE, headdepth.CAUSE, headdepth.SHAPE, headdepth.SCOPE))


class RevisedFieldsCase(PlaceCase):
    """元 replan.revised_fields（直した項目の欄を planmarks.split で作り直して差し替える）"""

    def test_replaces_only_revised_items(self):
        _, fields = planmarks.split({"plan": [item(MEAN), item(CLAMP)]}, self.repo)
        new = item(CLAMP, allowed_paths=["stats.py"])
        rows = [{"item": 2, "new": new, "new_marks": []}, {"item": 9, "new": new, "new_marks": []}, {"item": 1, "new": None}]
        got = take.revised_fields(fields, rows, self.repo)
        self.assertEqual(got[0], fields[0])
        self.assertEqual(got[1]["allowed_paths"], ["stats.py"])
        self.assertEqual(len(got), 2, "案の外の番号は足さない")
        self.assertEqual(fields[1]["allowed_paths"], ["stats.py", "test_stats.py"], "渡した欄は書き換えない")


class RoundCase(PlaceCase):
    """周の番号は prior.round + 1（前の周が無ければ 1）。入口は周のフォルダを作り、current-round.json に番号を書き、同じ周を開き直した
    時は名のファイルだけを消す（元 planfile.next_round の周のフォルダの数えは line の prior に替わった）"""

    def prior(self, k=3, **more):
        return {"round": k, "reply": {"plan": [item(MEAN, CLAMP)]}, "fields": {"round": k, "fields": []}, **more}

    def test_unreadable_world_rows_hold_the_replan_round_too(self):
        bad = self.place / "judge" / "world.jsonl"
        bad.parent.mkdir(parents=True)
        bad.write_text("{壊れた行\n", encoding="utf-8")
        got = self.intake(ruling=[1], prior=self.prior(k=1), world_rows=self.run.pointer("judge/world.jsonl"))
        self.assertEqual((got["mode"], got["go"]), ("replan", False))
        self.assertIn("world_rows が読めない", got["reason"])

    def test_first_round_is_one(self):
        got = self.intake()
        self.assertEqual(got, {"go": True, "mode": "plan", "round": 1, "reason": ""})
        self.assertEqual(self.read(self.place / files.CURRENT_ROUND), {"round": 1})
        self.assertEqual(files.current_dir(self.place), self.place / "r1")
        rnd = files.read_round(self.place / "r1")
        self.assertEqual((rnd["round"], rnd["mode"], rnd["go"], rnd["items"]), (1, "plan", True, []))
        self.assertEqual(self.read(self.place / "r1" / files.SLOTS), [MEAN, CLAMP, ASKED, DEP])

    def test_round_is_prior_round_plus_one_and_prior_fields_are_copied(self):
        note = self.artifact("r3/handoff.json", base.HANDOFF_NOTE)
        got = self.intake(prior=self.prior(handoffs=[{"round": 3, "handoff": json.loads(note)}, {"round": 2, "handoff": None}]))
        self.assertEqual((got["round"], got["go"]), (4, True))
        self.assertEqual(self.read(self.place / files.CURRENT_ROUND), {"round": 4})
        folder, ctx = steps.load(self.place)
        self.assertEqual(folder, self.place / "r4")
        prior = ctx["prior"]
        self.assertEqual(prior["round"], 3)
        self.assertEqual(prior["reply"], str(folder / files.PRIOR_COPIES["reply"]))
        self.assertEqual(self.read(prior["reply"]), {"plan": [item(MEAN, CLAMP)]})
        self.assertEqual(prior["fields"], str(folder / files.PRIOR_COPIES["fields"]))
        self.assertIsNone(prior["fix_plan"])
        self.assertEqual(prior["handoffs"], [{"round": 3, "handoff": str(self.place / "r3" / "handoff.json")},
                                             {"round": 2, "handoff": None}])
        self.assertEqual(steps.prior_rows(ctx), [item(MEAN, CLAMP)])

    def test_prior_by_pointer_keeps_nested_paths(self):
        reply = self.artifact("r1/reply.json", {"plan": [item(MEAN, CLAMP)]})
        fields = self.artifact("r1/plan-fields.json", {"round": 1, "fields": []})
        prior = self.artifact("prior.json", {"round": 1, "reply": json.loads(reply), "fields": str(self.place / "r1" / "plan-fields.json")})
        self.assertEqual(self.intake(prior=prior)["round"], 2)
        _, ctx = steps.load(self.place)
        self.assertEqual(ctx["prior"]["reply"], str(self.place / "r1" / "reply.json"))
        self.assertEqual(ctx["prior"]["fields"], str(self.place / "r1" / "plan-fields.json"))
        self.assertFalse((self.place / "r2" / files.PRIOR_COPIES["reply"]).exists(), "pointer で受けた欄は写さない")
        self.assertTrue(fields)

    def test_unreadable_prior_holds_the_round(self):
        for bad in ("{壊れ", dump({"round": 1, "reply": {"plan": []}}), dump({"round": 0, "reply": {}, "fields": {}})):
            with self.subTest(bad=bad):
                got = self.intake(prior=bad)
                self.assertFalse(got["go"])
                self.assertIn("prior が読めない", got["reason"])
                self.assertEqual(files.read_round(files.current_dir(self.place))["why"], got["reason"])

    def test_unreadable_prior_deletes_nothing_of_earlier_rounds(self):
        """読めない prior で前の周のフォルダを開き直さない（pointer の先の reply・plan-fields・handoff を消さない）"""
        folder = self.place / "r1"
        for name in (files.REPLY, files.FIELDS, files.HANDOFF):
            files.write_json(folder / name, {"keep": name})
        got = self.intake(prior="{壊れ")
        self.assertEqual((got["go"], got["round"]), (False, 2))
        for name in (files.REPLY, files.FIELDS, files.HANDOFF):
            self.assertEqual(files.read_json(folder / name), {"keep": name})

    def test_missing_review_and_handoff_files_read_as_not_received(self):
        reply = self.artifact("r1/reply.json", {"plan": [item(MEAN, CLAMP)]})
        self.artifact("r1/plan-fields.json", {"round": 1, "fields": []})
        prior = {"round": 1, "reply": json.loads(reply), "fields": str(self.place / "r1" / "plan-fields.json"),
                 "review": str(self.place / "無い指摘.json"), "handoffs": [{"round": 1, "handoff": str(self.place / "無いメモ.json")}]}
        got = self.intake(prior=dump(prior))
        self.assertEqual((got["go"], got["round"]), (True, 2), got)
        _, ctx = steps.load(self.place)
        self.assertIsNone(ctx["prior"]["review"])
        self.assertEqual(ctx["prior"]["handoffs"], [{"round": 1, "handoff": None}])

    def test_reopening_a_round_removes_only_its_own_files(self):
        """同じ周を開き直すと、その周の名のファイル（と round.json が名指す項目の brief）だけを消す。place の直下の指示の記録・ほかの周の
        フォルダ・名の無いファイルは残す"""
        folder = self.place / "r1"
        files.write_json(folder / files.ROUND, {"round": 1, "mode": "replan", "go": True, "why": "", "items": [2]})
        for name in (files.REPLY, files.FIELDS, files.REJECTS, files.HANDOFF, files.TRACE, files.ITEM_BRIEF.format(no=2)):
            (folder / name).write_text("前の回の物\n", encoding="utf-8")
        (folder / "keep.txt").write_text("名の無いファイル\n", encoding="utf-8")
        (self.place / "plan-writer-prompt-1.md").write_text("前の指示\n", encoding="utf-8")
        files.write_json(self.place / "r5" / files.REPLY, {"plan": []})
        self.intake()
        for name in (files.REPLY, files.FIELDS, files.REJECTS, files.HANDOFF, files.TRACE, files.ITEM_BRIEF.format(no=2)):
            self.assertFalse((folder / name).exists(), name)
        self.assertTrue((folder / "keep.txt").is_file())
        self.assertTrue((self.place / "plan-writer-prompt-1.md").is_file())
        self.assertTrue((self.place / "r5" / files.REPLY).is_file())
        self.assertEqual(files.read_round(folder)["mode"], "plan")

    def test_replan_mode_hands_items_or_holds(self):
        got = self.intake(ruling=[1], prior=self.prior(k=2))
        self.assertEqual((got["mode"], got["round"], got["go"]), ("replan", 3, True))
        self.assertEqual(files.read_round(self.place / "r3")["items"], [1])
        self.assertFalse((self.place / "r3" / files.SLOTS).exists(), "形 replan は単位の並びを書かない")
        got = self.intake(ruling=[5], prior=self.prior(k=2))
        self.assertFalse(got["go"])
        self.assertIn("ruling の項目 5", got["reason"])
        got = self.intake(ruling=[1])
        self.assertEqual((got["mode"], got["round"], got["go"]), ("replan", 1, False))
        self.assertEqual(got["reason"], "直す元の承認済みの修正案が無い")

    def test_plan_round_without_owed_units_holds(self):
        got = self.intake(judgment={"units": [unit(NIT, "nit", None)], "questions": []})
        self.assertEqual((got["go"], got["reason"]), (False, steps.NOTHING_OWED))
        got = self.intake(judgment="")
        self.assertEqual((got["go"], got["reason"]), (False, "judgment が読めない（空）"))

    def test_other_unreadable_ports_are_named_but_start_the_role(self):
        got = self.intake(verify=str(self.place / "無いファイル.json"), takes_push="maybe", units="{壊れ")
        self.assertTrue(got["go"], got)
        _, ctx = steps.load(self.place)
        self.assertEqual(sorted(u.split(":")[0] for u in ctx["unread"]), ["takes_push", "units", "verify"])
        self.assertEqual((ctx["verify"], ctx["takes_push"], ctx["units"]), ("", False, []))

    def test_load_refuses_a_round_without_intake(self):
        files.write_json(self.place / files.CURRENT_ROUND, {"round": 2})
        with self.assertRaises(ValueError):
            steps.load(self.place)


class FilesCase(PlaceCase):
    """place のファイルの名（files.py だけが持つ）と、標準ライブラリだけの落ちない道"""

    def test_names_equal_the_lib_owners(self):
        self.assertEqual(files.REJECTS, rolekit.rejects_path(pathlib.Path(), files.ROLE).name)
        self.assertEqual(files.CANDIDATE, rolekit.candidate_path(pathlib.Path(), files.ROLE).name)
        self.assertEqual(files.FIELDS, planmarks.FIELDS_FILE)
        self.assertEqual(files.HANDOFF, handoff.path_of(pathlib.Path()).name)
        self.assertEqual(files.REPLAN, replan.TRIP_FILE)
        self.assertEqual(files.TRACE, planmarks.TRACE_FILE)
        self.assertEqual(files.PRIOR_FAILURES_IN, carry.PRIOR_IN_FILE)
        self.assertEqual(files.ROLE, "plan")

    def test_own_files_are_the_round_names(self):
        own = set(files.OWN_FILES)
        self.assertEqual(len(own), len(files.OWN_FILES), "重なりが無い")
        for name in (files.INTAKE, files.ROUND, files.SLOTS, files.JUDGMENT_COPY, files.PRIOR_FAILURES_IN, files.RIPPLE_UNITS,
                     files.TREE, files.REJECTS, files.CANDIDATE, files.REPLY, files.FIX_PLAN, files.FIELDS, files.HANDOFF,
                     files.REPLAN, files.REPLAN_GAVE_UP, files.RIPPLE, files.TRACE, files.PROMPT_ERROR, files.FINISH_ERROR,
                     *files.PRIOR_COPIES.values()):
            self.assertIn(name, own)
        self.assertNotIn(files.CURRENT_ROUND, own, "place の直下の今の周の番号は消さない")
        self.assertTrue(all("/" not in n for n in own))

    def test_round_dir_and_current_round(self):
        self.assertEqual(files.round_dir(self.place, 2), self.place / "r2")
        self.assertEqual(files.current_round(self.place), 1, "無ければ 1")
        for doc, want in (({"round": 3}, 3), ({"round": True}, 1), ({"round": 0}, 1), ({"round": "2"}, 1), (["x"], 1)):
            with self.subTest(doc=doc):
                files.write_json(self.place / files.CURRENT_ROUND, doc)
                self.assertEqual(files.current_round(self.place), want)
        (self.place / files.CURRENT_ROUND).write_text("{壊れ", encoding="utf-8")
        self.assertEqual(files.current_round(self.place), 1)

    def test_read_round_defaults(self):
        self.assertEqual(files.read_round(self.place / "r7"), {"round": 7, "mode": "plan", "go": False, "why": "", "items": []})
        self.assertEqual(files.read_round(self.place / "x")["round"], 1)
        files.write_json(self.place / "r2" / files.ROUND, {"round": 2, "mode": "その他", "go": True, "items": "壊れ"})
        got = files.read_round(self.place / "r2")
        self.assertEqual((got["mode"], got["go"], got["items"], got["why"]), ("plan", True, [], ""))
        files.write_json(self.place / "r3" / files.ROUND, ["round でない"])
        self.assertEqual(files.read_round(self.place / "r3")["round"], 3)

    def test_write_json_leaves_no_temp_file(self):
        path = files.write_json(self.place / "a" / "b.json", {"x": "字"})
        self.assertEqual(files.read_json(path), {"x": "字"})
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["b.json"])
        self.assertEqual(files.read_json(self.place / "無い.json", "既定"), "既定")

    def test_crash_round_marks_the_round_failed(self):
        got = files.crash_round(self.place, "落ちた訳", 3)
        self.assertEqual(got, {"go": False, "mode": "plan", "round": 3, "reason": "落ちた訳"})
        self.assertEqual(self.read(self.place / "r3" / files.ROUND),
                         {"round": 3, "mode": "plan", "go": False, "why": "落ちた訳", "items": [], "error": True})
        self.assertEqual(self.read(self.place / files.CURRENT_ROUND), {"round": 3})
        files.write_json(self.place / "r3" / files.REPLY, {"plan": []})
        files.write_json(self.place / "r3" / files.FIELDS, {"round": 3, "fields": [{"x": 1}]})
        rnd = files.read_round(self.place / "r3")
        self.assertEqual(steps.status_of(self.place / "r3", rnd, [{"x": 1}]), ("failed", "落ちた訳"), "落ちた周は残った案があっても failed")
        self.assertEqual(files.crash_round(self.place, "別の周", 4)["round"], 4, "番号は呼び手が決める（前の周の番号を使い回さない）")
        self.assertEqual(files.read_round(self.place / "r3")["why"], "落ちた訳")

    def test_next_round_follows_prior_or_the_highest_folder(self):
        files.write_json(self.place / "r1" / files.ROUND, {"round": 1})
        files.write_json(self.place / "r2" / files.ROUND, {"round": 2})
        self.assertEqual(files.next_round(self.place, ""), 1)
        self.assertEqual(files.next_round(self.place, dump({"round": 1})), 2)
        for bad in ("{壊れ", dump({"reply": 1}), dump({"round": "x"})):
            with self.subTest(bad=bad):
                self.assertEqual(files.next_round(self.place, bad), 3, "読めない prior は在る周の一番大きい番号 + 1")

    def test_crash_finish_fills_pointers_and_keeps_a_kept_plan(self):
        files.write_json(self.place / files.CURRENT_ROUND, {"round": 2})
        files.write_json(self.place / "r2" / files.FIELDS, {"round": 2, "fields": [{"x": 1}]})
        got = files.crash_finish(self.place, "出口が落ちた")
        self.assertEqual((got["ok"], got["status"], got["round"], got["reason"]), (False, "failed", 2, "出口が落ちた"))
        self.assertEqual(got["plan"], {"type": ports.POINTER_TYPE, "run_id": kit.RUN_ID, "path": "r2/plan-fields.json"})
        self.assertEqual(got["ripple"]["path"], "r2/ripple.json")
        self.assertEqual(self.read(self.place / "r2" / files.FIELDS)["fields"], [{"x": 1}], "在って空でない控えは上書きしない")
        self.assertEqual(self.read(self.place / "r2" / files.RIPPLE), {"items": [], "error": "出口が落ちた"})
        self.assertEqual((self.place / "r2" / files.FINISH_ERROR).read_text(encoding="utf-8"), "出口が落ちた\n")
        self.assertEqual(got["report"], ["修正案: 周 2・修正案を出せなかった（failed）: 出口が落ちた"])


class NestedFileCase(PlaceCase):
    """steps.nested_file: 入れ子の値（prior の欄）は pointer・パスの字なら解き、ほかの値は周のフォルダに写しを書いてそのパス。null は None"""

    def test_pointer_path_value_and_none(self):
        ptr = json.loads(self.artifact("r1/reply.json", {"plan": []}))
        folder = self.place / "r2"
        self.assertEqual(steps.nested_file(ptr, folder, "copy.json"), self.place / "r1" / "reply.json")
        self.assertEqual(steps.nested_file(str(self.place / "r1" / "reply.json"), folder, "copy.json"), self.place / "r1" / "reply.json")
        got = steps.nested_file({"plan": [item(MEAN)]}, folder, "copy.json")
        self.assertEqual(got, folder / "copy.json")
        self.assertEqual(self.read(got), {"plan": [item(MEAN)]})
        self.assertIsNone(steps.nested_file(None, folder, "copy.json"))

    def test_missing_path_and_foreign_pointer_raise(self):
        with self.assertRaises(ValueError):
            steps.nested_file(str(self.place / "無い.json"), self.place, "copy.json")
        with self.assertRaises(ValueError):
            steps.nested_file({"type": ports.POINTER_TYPE, "run_id": "ほかの run", "path": "x.json"}, self.place, "copy.json")

    def test_value_of_the_pointer_shape_with_another_type_is_copied(self):
        got = steps.nested_file({"type": "値", "path": "x"}, self.place / "r1", "copy.json")
        self.assertEqual(self.read(got), {"type": "値", "path": "x"})


class TakePlanCase(PlaceCase):
    """修正案の役の返答の受け付け（元 planblk.take・with_plan_fields。元 tests/test_blk_plan.py の test_take_malformed_plan_resubmits_not_raises・
    test_save_failure_after_board_took_plan_halts）。周は入口を本当に回して開く"""

    def setUp(self):
        super().setUp()
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.round, self.ctx = self.opened()
        steps.snap_tree(self.round / files.TREE, self.repo)

    def take(self, reply, *, base_rev=None):
        return take.take_plan(self.round, self.ctx, judgment=steps.read_judgment(self.ctx), reply=reply, repo=self.repo,
                              tables=[], base_rev=self.base if base_rev is None else base_rev)

    def trace(self):
        return [json.loads(x) for x in (self.round / files.TRACE).read_text(encoding="utf-8").splitlines()]

    def test_good_reply_puts_every_file(self):
        self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)]}), {"ok": True, "reason": ""})
        for name in (files.FIX_PLAN, files.FIELDS, files.REPLY):
            self.assertTrue((self.round / name).is_file(), name)
        self.assertEqual(self.read(self.round / files.REPLY), {"plan": [item(MEAN, CLAMP)]})
        self.assertEqual(len(steps.accepted_fields(self.round)), 1)
        self.assertFalse(rolekit.candidate_path(self.round, files.ROLE).exists(), "往復の行が無い周は合わせた控えを書かない")

    def test_numbers_are_named_by_the_round_slots(self):
        self.assertEqual(self.take({"plan": [item(1, 2)]}), {"ok": True, "reason": ""})
        self.assertEqual(self.read(self.round / files.REPLY)["plan"][0]["unit_keys"], [MEAN, CLAMP])

    def test_malformed_reply_is_a_rejection_not_an_exception(self):
        for reply in ({"plan": "s"}, {"plan": ["x"]}, {"plan": [item(MEAN, CLAMP, narrows=3)]}):
            with self.subTest(reply=reply):
                self.assertEqual(self.take(reply), {"ok": False, "reason": steps.MALFORMED_REJECT})
        self.assertFalse((self.round / files.REPLY).exists())

    def test_missing_and_extra_units_are_rejected_in_one_reason(self):
        got = self.take({"plan": [item(MEAN, NIT)]})
        self.assertFalse(got["ok"])
        self.assertIn(steps.NOT_OWED_REJECT, got["reason"])
        self.assertIn(steps.COVERS_REJECT, got["reason"])
        self.assertIn("[1, 2, 3, 4]", got["reason"])

    def test_moved_tree_and_missing_snapshot_are_rejected_first(self):
        (self.repo / "stats.py").write_text("# 役が書き換えた\n", encoding="utf-8")
        got = self.take({"plan": "崩れ"})
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(steps.READONLY_MOVED), got["reason"])
        (self.round / files.TREE).unlink()
        self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)]})["reason"], steps.NO_TREE.format(name=files.TREE))

    def test_unreadable_base_is_traced(self):
        self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)]}, base_rev="0" * 40), {"ok": True, "reason": ""})
        rows = [r for r in self.trace() if r["op"] == steps.BASE_TESTS_UNREAD_OP]
        self.assertEqual([(r["rev"], r["unread"]) for r in rows], [("0" * 40, ["<版>"])])

    def test_concept_housed_twice_is_rejected(self):
        """案の受け付けは、2 つの項目の files の行が同じ home.concept を持つ返答を ok False で拒み、reason に home.concept の行を名指す。
        考えが分かれた返答は通る"""
        def reply(second):
            return {"plan": [item(MEAN, files=[_frow("stats.py", "mean")]), item(CLAMP, files=[_frow("test_stats.py", "clamp", **second)])]}
        same = {"home": {"concept": "stats.py の考え", "why": "ここが住処だから"}}
        out = self.take(reply(same))
        self.assertFalse(out["ok"], out)
        self.assertIn("plan[1].files[0].home.concept", out["reason"])
        self.assertIn("plan[0].files[0]", out["reason"])
        self.assertFalse((self.round / files.REPLY).exists())
        self.assertEqual(self.take(reply({})), {"ok": True, "reason": ""})

    def test_handoff_is_kept_beside_the_plan_not_in_it(self):
        """返答の頭の欄 handoff は案から外れ、周のフォルダの引き継ぎのメモの控えに字のまま置かれる。案の控え（p2.fix_plan.json・
        plan-fields.json・reply.json）には入らない"""
        note = base.HANDOFF_NOTE
        self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)], "handoff": note}), {"ok": True, "reason": ""})
        kept = self.round / files.HANDOFF
        self.assertTrue(kept.is_file(), "引き継ぎのメモの控えが無い")
        self.assertEqual(self.read(kept), note)
        for name in (files.FIX_PLAN, files.FIELDS, files.REPLY):
            self.assertNotIn("handoff", (self.round / name).read_text(encoding="utf-8"), f"{name} に引き継ぎのメモが混ざった")

    def test_note_is_saved_through_the_home(self):
        """メモは住処の handoff.save で周のフォルダに置く（受け付けは自前の書き口を持たない）。空のメモでは周に残る前のメモを消す"""
        note = {"read": [], "kept": ["分母は len(xs) にする"], "set_aside": [], "open": []}
        with mock.patch.object(handoff, "save", wraps=handoff.save) as save:
            self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)], "handoff": note}), {"ok": True, "reason": ""})
        save.assert_called_once_with(self.round, note)
        self.assertEqual(self.read(handoff.path_of(self.round)), note)
        with mock.patch.object(handoff, "save", wraps=handoff.save) as save:
            self.assertEqual(self.take({"plan": [item(MEAN, CLAMP)]}), {"ok": True, "reason": ""})
        save.assert_called_once_with(self.round, None)
        self.assertFalse(handoff.path_of(self.round).exists())

    def test_save_failure_leaves_no_accepted_plan(self):
        """受けた後に欄の控えを置けなければ、置いた控えを消し、置けなかった控えの名を round.json の why に残す（欄の無い案で進ませない）"""
        with mock.patch.object(planmarks, "save", side_effect=OSError("書けない")):
            out = self.take({"plan": [item(MEAN, CLAMP)]})
        self.assertEqual((out["ok"], out["halt"], out["count"], out["give_up"]), (False, True, False, True))
        self.assertIn(files.FIELDS, out["reason"])
        for name in (files.FIX_PLAN, files.FIELDS, files.REPLY):
            self.assertFalse((self.round / name).exists(), name)
        self.assertIsNone(steps.accepted_fields(self.round))
        why = steps.why_not_ready(self.round)
        self.assertIn(files.FIELDS, why)
        self.assertIn("書けない", why)

    def test_pop_field_copies(self):
        reply = {"plan": [], "handoff": {"kept": []}}
        out, got = take.pop_field(reply, ("handoff", "無い欄"))
        self.assertEqual((out, got), ({"plan": []}, {"handoff": {"kept": []}}))
        self.assertIn("handoff", reply, "返答は書き換えない")
        self.assertEqual(take.pop_field("字", ("handoff",)), ("字", {}))


class WholePlanTakeCase(PlaceCase):
    """R2: 2 往復目からの出し直しが WHOLE_PLAN で開いた項目を消したら、受け付けは消した項目を前の往復の行で戻さない。往復の記録は
    port prior の record（line が組む物）で受ける"""

    def setUp(self):
        super().setUp()
        rows = [item(MEAN, CLAMP), item(ASKED)]
        doc = record(plan_step(rows), review_step([face("key-a1", [MEAN]), face("key-b1", [ASKED])]))
        self.round, self.ctx = self.opened(prior={"round": 1, "reply": {"plan": rows}, "fields": {"round": 1, "fields": []},
                                                  "review": {"faces": [face("key-a1", [MEAN]), face("key-b1", [ASKED])]},
                                                  "record": doc})
        self.assertEqual(self.round, self.place / "r2")
        steps.snap_tree(self.round / files.TREE, self.repo)

    def take(self, reply):
        return take.take_plan(self.round, self.ctx, judgment=steps.read_judgment(self.ctx), reply=reply, repo=self.repo, tables=[],
                              base_rev=git(self.repo, "rev-parse", "HEAD"))

    def reply(self, **more):
        return {"plan": [item(MEAN, CLAMP, approach="mean の分母と clamp の上限の枝を直し、空の列は扱わない")],
                "block_answers": [answer("key-a1"), answer("key-b1", how="空の列の項目は要らないので案から外した")], **more}

    def test_whole_plan_drops_open_item(self):
        self.assertEqual(self.take(self.reply(**{steps.WHOLE_PLAN: True})), {"ok": True, "reason": ""})
        got = self.read(self.round / files.REPLY)
        self.assertEqual([it["unit_keys"] for it in got["plan"]], [[MEAN, CLAMP]])
        self.assertNotIn(steps.WHOLE_PLAN, got)
        self.assertEqual(got[converge.ANSWERS], self.reply()["block_answers"], "往復の行が在れば答えも控えに残す")

    def test_changed_items_only_keep_the_rest(self):
        reply = {**self.reply(), "block_answers": [answer("key-a1"), answer("key-b1", handled="disputed", how="空の列の扱いも要る項目なので残す")]}
        self.assertEqual(self.take(reply), {"ok": True, "reason": ""})
        got = self.read(self.round / files.REPLY)
        self.assertEqual([it["unit_keys"] for it in got["plan"]], [[MEAN, CLAMP], [ASKED]])
        kept = self.read(rolekit.candidate_path(self.round, files.ROLE))
        self.assertEqual(kept, {**reply, "plan": got["plan"]}, "控えは機械が前の往復の行を差し込んだ案の全体")

    def test_missing_answer_is_rejected(self):
        got = self.take({**self.reply(), "block_answers": [answer("key-a1")]})
        self.assertFalse(got["ok"])
        self.assertIn(steps.ANSWERS_REJECT, got["reason"])
        self.assertIn("key-b1", got["reason"])


class ReplanModuleCase(unittest.TestCase):
    """持ってきた replan.py の残り（受け付けが使う、盤面を受けない項目の小道具）"""

    def test_new_item_puts_marks_back_on_narrows(self):
        row = {"new": {"narrows": [{"what": "x"}]}, "new_marks": [{"no_narrow": "狭めない案を当たったが無い"}]}
        self.assertEqual(replan.new_item(row), {"narrows": [{"what": "x", "no_narrow": "狭めない案を当たったが無い"}]})
        self.assertEqual(row["new"], {"narrows": [{"what": "x"}]})

    def test_malformed(self):
        for reply in (None, {"plan": "x"}, {"plan": ["x"]}, {"plan": [{"narrows": 5}]}):
            self.assertTrue(replan._malformed(reply), reply)
        self.assertFalse(replan._malformed({"plan": [{"narrows": []}]}))


class ResubmitMergeCase(unittest.TestCase):
    """#571: 修正案の出し直し（拒まれた項目だけ）を前の答えと合わせる決まり（take.merge_plan_items・merge_resubmit・merge_replan_resubmit）"""

    SLOTS = ["u1", "u2", "u3"]

    @staticmethod
    def it(*keys, tag=""):
        return {"unit_keys": list(keys), "approach": tag or f"項目 {keys}"}

    def merged(self, old, new):
        return take.merge_plan_items(old, new, self.SLOTS)

    def test_overlapping_item_replaces_in_place(self):
        old = [self.it("u1"), self.it("u2"), self.it("u3")]
        self.assertEqual(self.merged(old, [self.it("u2", tag="新")]), [self.it("u1"), self.it("u2", tag="新"), self.it("u3")])

    def test_joined_item_takes_the_first_place(self):
        old = [self.it("u1"), self.it("u2"), self.it("u3")]
        self.assertEqual(self.merged(old, [self.it("u3", "u1")]), [self.it("u3", "u1"), self.it("u2")])

    def test_moved_unit_replaces_both_items(self):
        old = [self.it("u1", "u2"), self.it("u3")]
        new = [self.it("u1"), self.it("u2", "u3")]
        self.assertEqual(self.merged(old, new), [self.it("u1"), self.it("u2", "u3")])

    def test_new_item_without_overlap_is_appended(self):
        old = [self.it("u1"), self.it("u2")]
        self.assertEqual(self.merged(old, [self.it("u3")]), [self.it("u1"), self.it("u2"), self.it("u3")])

    def test_units_compare_as_text(self):
        """番号の 1 と字の "1" は同じ単位（converge.planned_units と同じ）"""
        self.assertEqual(take.merge_plan_items([self.it(1)], [self.it("1", tag="新")], ["1"]), [self.it("1", tag="新")])

    def test_no_and_name_are_the_same_unit(self):
        """R1: 前の答えが単位の名で、出し直しが no で同じ単位を指しても、受け付けと同じく名に戻してから合わせる（重なりを見落として
        同じ単位が 2 つの項目に入らない）"""
        prev = {"plan": [self.it("u1"), self.it(2, tag="2")]}
        got = take.merge_resubmit(prev, {"plan": [self.it(1, tag="新")]}, self.SLOTS)
        self.assertEqual(got["plan"], [self.it("u1", tag="新"), self.it("u2", tag="2")])

    def test_item_with_unknown_keys_only_is_dropped(self):
        """R1: 前の答えの、今の周の単位を 1 つも持たない項目（key の書き誤り）は、直した項目を返した出し直しで消える"""
        prev = {"plan": [self.it("u1"), self.it("u-typo")]}
        got = take.merge_resubmit(prev, {"plan": [self.it(2, tag="直した")]}, self.SLOTS)
        self.assertEqual(got["plan"], [self.it("u1"), self.it("u2", tag="直した")])

    def test_merge_resubmit_merges_items_and_replaces_other_fields(self):
        prev = {"plan": [self.it("u1"), self.it("u2")], "block_answers": [{"key": "a"}]}
        got = take.merge_resubmit(prev, {"plan": [self.it("u2", tag="新")], "block_answers": [{"key": "b"}]}, self.SLOTS)
        self.assertEqual(got, {"plan": [self.it("u1"), self.it("u2", tag="新")], "block_answers": [{"key": "b"}]})
        self.assertEqual(take.merge_resubmit(prev, {"block_answers": []}, self.SLOTS)["plan"], prev["plan"])

    def test_whole_plan_replaces_the_plan_and_stays(self):
        """WHOLE_PLAN の出し直しは plan を丸ごと置き換え、印は控えに残って、この後の項目だけの出し直しも全部の案に合わさる"""
        prev = {"plan": [self.it("u1"), self.it("u2")]}
        got = take.merge_resubmit(prev, {steps.WHOLE_PLAN: True, "plan": [self.it("u1")]}, self.SLOTS)
        self.assertEqual(got, {"plan": [self.it("u1")], steps.WHOLE_PLAN: True})
        after = take.merge_resubmit(got, {"plan": [self.it("u1", tag="新")]}, self.SLOTS)
        self.assertEqual(after, {"plan": [self.it("u1", tag="新")], steps.WHOLE_PLAN: True})
        self.assertNotIn(steps.WHOLE_PLAN,
                         take.merge_resubmit(prev, {steps.WHOLE_PLAN: False, "plan": [self.it("u1")]}, self.SLOTS))

    def test_replan_replaces_the_plan_in_pasted_order(self):
        """R1: 形 replan は貼った位置で照らすので、出し直しの plan は項目で合わせずに丸ごと置き換わる（重ならない項目を後ろに
        足して位置をずらさない）"""
        prev = {"plan": [self.it("c")]}
        part = {"plan": [self.it("a", "b"), self.it("c")], steps.WHOLE_PLAN: False}
        self.assertEqual(take.merge_replan_resubmit(prev, part), {"plan": [self.it("a", "b"), self.it("c")]})
        self.assertEqual(take.merge_replan_resubmit({"plan": [self.it("c")], "x": 1}, {"x": 2}), {"plan": [self.it("c")], "x": 2})

    def test_rules_name_the_whole_plan_field(self):
        """R4: 役に読ませる返し方の欄の名は定数から作る（md は口 {whole_plan} を持ち、fix_prep が steps.WHOLE_PLAN を入れる。型の欄の名と
        食い違わない）"""
        self.assertEqual(steps.WHOLE_PLAN, "whole_plan")
        self.assertIn("{whole_plan}", (kit.BLOCKS / "plan" / "prompts" / "plan-writer-fix.md").read_text(encoding="utf-8"))


class RippleItemsCase(PlaceCase):
    """受け付けた案の項目ごとの波及の一覧（steps.ripple_items。今の周のフォルダの reply.json・plan-fields.json を読み ripple.json に書く）"""

    def round_one(self):
        files.write_json(self.place / files.CURRENT_ROUND, {"round": 1})
        return self.place / "r1"

    def test_ripple_items_sees_removes(self):
        """受け付けた案の項目の files の change=remove の symbol（planmarks.split が欄に写す）が波及の一覧に届き、残る名指しが kind removed で
        名指される"""
        gone = {"name": "stats.clamp", "change": "remove", "why": "境の判定は mean に寄せたので要らない"}
        rows = [{**_frow("stats.py"), "responsibility": "境の判定", "symbols": [gone]}]
        it = {"unit_keys": [MEAN], "approach": "x" * 20, "files": rows, "shrink_first": "y" * 20,
              "narrows": [], "route": "tdd", "route_why": "", "tests": [], "rewrite_tests": [],
              "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py"], "out_of_scope": []}
        folder = self.round_one()
        files.write_json(folder / files.REPLY, {"plan": [it]})
        files.write_json(folder / files.FIELDS, {"round": 1, "fields": planmarks.split({"plan": [it]}, self.repo)[1]})
        self.assertEqual(steps.ripple_items(self.place, self.repo), {"ok": True})
        doc = self.read(folder / files.RIPPLE)
        got = [(h["kind"], h["at"]) for h in doc["items"][0]["uncovered"]]
        self.assertIn(("removed_test", "test_stats.py::TestStats::test_clamp_within_range"), got)

    def test_round_without_a_plan_names_why(self):
        folder = self.round_one()
        files.write_json(folder / files.ROUND, {"round": 1, "mode": "plan", "go": False, "why": steps.NOTHING_OWED, "items": []})
        steps.ripple_items(self.place, self.repo)
        self.assertEqual(self.read(folder / files.RIPPLE), {"items": [], "error": steps.NOTHING_OWED})
        files.write_json(folder / files.ROUND, {"round": 1, "mode": "plan", "go": True, "why": "", "items": []})
        steps.ripple_items(self.place, self.repo)
        self.assertEqual(self.read(folder / files.RIPPLE), {"items": [], "error": files.NO_PLAN})


class FinishCase(PlaceCase):
    """出口: status の 5 つの語（status_of）・報告の行（report_lines）・空の周でも落ちない finish"""

    def folder(self, **round_doc):
        folder = self.place / "r1"
        files.write_json(folder / files.ROUND, {"round": 1, "mode": "plan", "go": True, "why": "", "items": [], **round_doc})
        return folder

    def status(self, folder, fields=None):
        return steps.status_of(folder, files.read_round(folder), fields)

    def test_status_of_every_status(self):
        folder = self.folder()
        self.assertEqual(self.status(folder, [{"x": 1}]), ("ok", ""))
        self.assertEqual(self.status(folder), ("failed", files.NO_PLAN))
        self.assertEqual(self.status(self.folder(go=False, why="落ちた", error=True)), ("failed", "落ちた"))
        self.assertEqual(self.status(self.folder(go=False, why=steps.NOTHING_OWED)), ("nothing_owed", steps.NOTHING_OWED))
        self.assertEqual(self.status(self.folder(go=False, why="判定が読めない")), ("held", "判定が読めない"))
        self.assertEqual(self.status(self.folder(why="受けた修正案の控え plan-fields.json を置けない: 書けない")),
                         ("gave_up", "受けた修正案の控え plan-fields.json を置けない: 書けない"))

    def test_status_of_prompt_error_and_rejects(self):
        folder = self.folder()
        steps.record_crash(self.place, "plan-prep", "断片が無い")
        self.assertEqual(self.status(folder), ("failed", "指示が組めない（plan-prep: 断片が無い）"))
        (folder / files.PROMPT_ERROR).unlink()
        files.write_json(folder / files.REJECTS, [{"at": "t", "reason": "網羅が欠けた", "give_up": True}])
        self.assertEqual(self.status(folder), ("gave_up", rolekit.given_up_reason(folder, files.ROLE)))
        self.assertIn("網羅が欠けた", self.status(folder)[1])
        (folder / files.REJECTS).write_text("{壊れ", encoding="utf-8")
        status, reason = self.status(folder)
        self.assertEqual(status, "failed")
        self.assertTrue(reason.startswith("拒否の控えが扱えない（"), reason)

    def test_status_of_unhandled_reject_record_is_failed_even_with_a_why(self):
        """拒否の控えが読めない周は、round.json に訳が在っても役の諦め（gave_up）でなく機械の故障（failed）"""
        folder = self.folder(why="何かの訳")
        (folder / files.REJECTS).write_text("{壊れ", encoding="utf-8")
        status, reason = self.status(folder)
        self.assertEqual(status, "failed")
        self.assertIn("拒否の控えが扱えない", reason)

    def test_report_lines(self):
        rnd = {"round": 2, "mode": "plan", "items": []}
        self.assertEqual(steps.report_lines("ok", "", rnd, [{}, {}], [{}], None),
                         ["修正案: 周 2（案を書く）・項目 2 件・受け付けの拒否 1 回"])
        self.assertEqual(steps.report_lines("ok", "", {**rnd, "mode": "replan", "items": [1, 3]}, [{}], [], None),
                         ["修正案: 周 2（案の直し）・項目 1 件・受け付けの拒否 0 回", "案の直しで直した項目: 1・3"])
        self.assertEqual(steps.report_lines("nothing_owed", steps.NOTHING_OWED, rnd, None, [], None),
                         [f"修正案: 周 2・直す義務の単位が無いので修正案の役を起こさなかった（{steps.NOTHING_OWED}）"])
        for status in ("held", "failed"):
            self.assertEqual(steps.report_lines(status, "訳", rnd, None, [], None), [f"修正案: 周 2・修正案を出せなかった（{status}）: 訳"])
        gave = [{"item": 1, "why": "拒まれ続けた", "ruling": "手順を直す"}]
        self.assertEqual(steps.report_lines("gave_up", "訳", {**rnd, "mode": "replan"}, None, [], gave),
                         ["修正案: 周 2・修正案を出せなかった（gave_up）: 訳",
                          "案の直しを終えられなかった 項目 1: 拒まれ続けた。裁定の文: 手順を直す"])

    def test_finish_never_raises_on_an_empty_place(self):
        """入口の走っていない place・読めない控えでも落ちず、pointer の先（plan-fields.json・ripple.json）が在って空でない約束の形を返す"""
        got = steps.finish(self.place)
        self.assertEqual(set(got), {"ok", "status", "reason", "mode", "round", "owed", "plan", "fix_plan", "reply", "handoff", "replan",
                                    "ripple", "rejects", "gave_up", "report"})
        self.assertFalse(got["ok"])
        self.assertIn(got["status"], ("held", "failed", "gave_up"))
        self.assertEqual((got["round"], got["owed"], got["rejects"], got["fix_plan"], got["reply"]), (1, [], [], None, None))
        for name in ("plan", "ripple"):
            path = self.place / got[name]["path"]
            self.assertTrue(path.is_file() and path.stat().st_size > 0, name)
        folder = self.folder()
        (folder / files.INTAKE).write_text("{壊れ", encoding="utf-8")
        (folder / files.REJECTS).write_text("{壊れ", encoding="utf-8")
        got = steps.finish(self.place)
        self.assertEqual((got["status"], got["rejects"], got["gave_up"]), ("failed", [], None))

    def test_finish_after_an_accepted_plan(self):
        folder, ctx = self.opened()
        steps.snap_tree(folder / files.TREE, self.repo)
        out = take.take_plan(folder, ctx, judgment=steps.read_judgment(ctx), reply={"plan": [item(MEAN, CLAMP)]}, repo=self.repo,
                             tables=[], base_rev="")
        self.assertTrue(out["ok"], out)
        got = steps.finish(self.place)
        self.assertEqual((got["ok"], got["status"], got["owed"]), (True, "ok", [MEAN, CLAMP]))
        self.assertEqual(got["reply"]["path"], "r1/reply.json")
        self.assertEqual(got["report"], ["修正案: 周 1（案を書く）・項目 1 件・受け付けの拒否 0 回"])


if __name__ == "__main__":
    unittest.main()
