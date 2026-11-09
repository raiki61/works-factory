"""plan の block の周と出口と指示の材料の検査（docs/design/plan.md の 1.2〜1.4・2.3・9.2）。

元の test_plan.py の CollectCase・SurvivesCase・BriefCase の写しと、9.2 の「足す」の 4 つ（値で受けた判定と前の周の欄の写し・
place の分かれと前の周のフォルダの残り・status の 5 つの語・owed の順）。block は base.PlanRun で Archon と同じ順に回す。
前の周は line が組む port prior の形で渡す（Line: 前の include の出口の pointer と、受けた事前審査から組み直した往復の記録）。
指示の字は英語の md の札と、値（パス・key）で照らす（段落が在るか無いかだけを見て、文の全体は見ない）。
写さなかった試験: test_depth_follows_start_thickness_and_checks（深さは line へ。6 節）。始めの記録 start の読めない場合は、
start が無くなったので読めない prior に替えた。
"""
import copy
import importlib
import json
import pathlib
import unittest

from tests.blocks import kit
from tests.blocks.plan import base
from tests.blocks.plan.base import (CLAMP, DIRTY_ROW, HANDOFF_NOTE, MEAN, NIT, RUN_ID, PlanRun, catalog, item, judgment, narrow,
                                    unit, writer_of)

rounds = kit.load("line", "rounds")   # 往復の記録の書き手（line）。plan の src より先に読む（kit.load は前の src を外す）
steps = kit.load("plan", "steps")
take = importlib.import_module("src.take")   # kit.load が置いた src の package から
files = kit.load("plan", "files")

import converge  # noqa: E402  （lib/。base が sys.path に足す）
import gatemarks  # noqa: E402
import planmarks  # noqa: E402
import rolekit  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

# md の札（prompts/plan-writer.md と workflows/.shared/prompts/ の断片の見出しと頼みの頭）
RIPPLE_HEAD = "## Ripple list (looked up by the machine with git grep: the callers and tests of the names that the items change)"
UNREAD_HEAD = "## Inputs that could not be read"

FACE_MEAN = {"key": "key-a1-mean", "kind": "regression", "where": "stats.py", "why": "空の列が落ちる", "severity": "block",
             "unit_keys": [MEAN]}
FACE_CLAMP = {"key": "key-b1-clamp", "kind": "regression", "where": "stats.py", "why": "下限の枝が抜ける", "severity": "block",
              "unit_keys": [CLAMP]}
NO_NARROW = "狭めない案として空の列に 0 を返す形を当たったが、呼び手が例外を捕まえている"
MARKED = narrow(no_narrow=NO_NARROW, undecided_because="②空の列を渡す呼び手が在るかは依頼に書いていない",
                recommend={"answer": "continue", "note": "空の列は例外のまま残す", "why": "呼び手が例外を捕まえている"})
REWRITE = {"id": "test_stats.py::TestStats::test_clamp_above_range", "behavior": "上限を超えた値に上限を返す",
           "old": "lo を返す", "new": "上限を超えたら hi を返す"}
FIXED_MEAN = {"key": "key-a1-mean", "handled": "fixed", "how": "空の列を先に返す枝を足した"}
CHANGED_APPROACH = "空の列も直す形にした案の手順をここに書いた"


def seq(*replies):
    """修正案の役と出し直しの役を通した回ごとに replies[n-1] を返す役（足りなければ最後の物）。writer と fixer の両方に渡す"""
    calls = []

    def reply(n, prompt):
        calls.append(prompt)
        return copy.deepcopy(replies[min(len(calls), len(replies)) - 1])
    return reply


def never(case):
    return lambda n, prompt: case.fail("役を起こした")


def writer_prompts(run) -> list:
    return [p for nid, p in run.prompts if nid == "plan-writer"]


def review_rows(run, out) -> list:
    """事前審査が往復の記録の plan に置く行（plan-review の intake の 5 と 8 と同じ道）: 出口 out の受けた案 fix_plan から narrows の
    行の決め手の欄を外し、欄の行（plan-fields.json）を planmarks.joined で重ね、外した欄を converge.plan_rows で項目ごとに添える"""
    bare, marks = gatemarks.split(planmarks.NODE, run.json(out["fix_plan"]))
    fields = run.json(out["plan"])["fields"]
    return converge.plan_rows([planmarks.joined(r, f) for r, f in zip(bare["plan"], fields)], marks=marks)


def converge_record(passes, dest: pathlib.Path) -> dict:
    """往復の記録（line が prior.record に渡す物）を、line の書き手で組む: rounds.fresh() に、受けた事前審査ごとに pass.json の中身を
    rounds.record_pass で足し、受けた案の項目の行を記録の plan に置く。passes は周ごとの (その周を開いた時に受けた事前審査, その周の
    受けた案[, 記録の plan に置く行])。最後は今開く周で、案は None。行を渡さなければ受けた案の項目そのものから組む。手で枠を組まないので、
    書き手の欄の組と記録の形（shared:plan-converge.schema.json）から外れない"""
    doc = rounds.fresh()
    answers: list = []
    for k, (review, reply, *rows) in enumerate(passes, 1):
        if isinstance(review, dict) and doc.get("plan"):
            resolved = review.get(converge.RESOLVED)
            rounds.record_pass(doc, {"pass": len(doc["passes"]) + 1, "plan": doc["plan"], "answers": copy.deepcopy(answers),
                                     "review": review, "resolved": resolved if isinstance(resolved, list) else []},
                               at_cap=False, dest=dest / f"pass-{k}")
        if isinstance(reply, dict) and isinstance(reply.get("plan"), list):
            doc["plan"] = rows[0] if rows else converge.plan_rows(reply["plan"])
            answers = [r for r in reply.get(converge.ANSWERS) or [] if isinstance(r, dict)]
    return kit.shaped("shared:plan-converge.schema.json", doc)


class Line:
    """line の計画の往復の側: 周ごとに block を include し、前の周の出口から port prior を組む（docs/design/plan.md の 1.6）。往復の記録の
    案の行は事前審査が置くのと同じ道（review_rows）で組む"""

    def __init__(self, run: PlanRun):
        self.run = run
        self.history: list = []   # (その周を開いた時に受けた事前審査, 出口の返り)

    def prior(self, review, *, review_form=None) -> dict:
        last = self.history[-1][1]
        rounds = [(rv, self.run.json(o["reply"]), review_rows(self.run, o)) if o["reply"] else (rv, None)
                  for rv, o in self.history] + [(review, None)]
        return {"round": last["round"], "reply": last["reply"], "fields": last["plan"], "fix_plan": last["fix_plan"],
                "ripple": last["ripple"], "review": review if review_form is None else review_form,
                "record": converge_record(rounds, self.run.tmp / "line-rounds"),
                "handoffs": [{"round": o["round"], "handoff": o["handoff"]} for _, o in self.history]}

    def round(self, review=None, *, review_form=None, **kw) -> dict:
        prior = self.prior(review, review_form=review_form) if self.history else ""
        out = self.run.include(prior=prior, **kw)
        self.history.append((review, out))
        return out


def structure(run, rows=None, *, status="ok", reason="", skipped=()):
    """port structure の構造の目の控え（{status, reason, design_file, skipped}）の pointer。rows は設計の行（JSON Lines）"""
    design = ""
    if rows is not None:
        path = run.art / "structure" / "design.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        design = str(path)
    return run.file("structure/state.json", {"status": status, "reason": reason, "design_file": design, "skipped": list(skipped)})


def clean_rows(keys=(MEAN, CLAMP)):
    return [{"unit_id": k, "verdict": "汚れない", "faces": [], "evidence": [f"/units/{i}/id"], "reason": "足す形が増えない"}
            for i, k in enumerate(keys)]


def dirty_rows(route=False):
    rows = clean_rows()
    rows[0].update(DIRTY_ROW, evidence=["/units/0/id"])
    if route:
        rows[0].update(route="人に上げる", undecided_because="方針の文書も前の決定も当たったが、どちらの避け方にも決め手が無い",
                       rejected=[{"option": "新しい口を足す", "cost": "知る場所が増える"}])
    return rows


def pointer_to(rel: str) -> str:
    return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})


def missing(rel="nowhere/x.json") -> str:
    """在らないファイルを指す pointer"""
    return pointer_to(rel)


FINISH_FORMAT = base.node("finish")["output_format"]


class CollectCase(unittest.TestCase):
    """出口は落ちない・pointer の先はいつも在って空でない・周の番号は prior.round + 1"""

    def assert_contract(self, run, out):
        self.assertEqual(validate_schema(out, FINISH_FORMAT), [])
        self.assertIs(out["ok"], False)
        self.assertTrue(out["reason"], out)
        for key in ("plan", "ripple"):
            run.pointed(out[key])

    def test_broken_inputs_still_return_the_contract(self):
        """読めない prior（今の start の代わり）・在らない pointer・ほかの run の pointer の判定は、役を起こさずに約束の形を返す"""
        cases = {
            "読めない prior": {"prior": "{壊れた"},
            "在らない pointer": {"judgment": missing("judge/none.json")},
            "ほかの run の pointer": {"judgment": json.dumps({"type": "archon_artifact", "run_id": "other", "path": "x.json"})},
        }
        for name, bad in cases.items():
            with self.subTest(name):
                run = PlanRun(self)
                out = run.include(writer=never(self), **bad)
                self.assert_contract(run, out)
                self.assertEqual(out["status"], "held")
        with self.subTest("形の違う units"):
            run = PlanRun(self)
            out = run.include(units='{"id": 1}')
            self.assertEqual(validate_schema(out, FINISH_FORMAT), [])
            self.assertIn("- units: ", writer_prompts(run)[0].split(UNREAD_HEAD, 1)[1])

    def test_finish_without_the_round_folder_still_returns_the_contract(self):
        """周のフォルダが消えた後（入口の控えが無い）の出口も、約束の形と在って空でない pointer の先を返し、ok でない訳を名指す"""
        run = PlanRun(self)
        run.include()
        for p in sorted((run.art / "r1").iterdir()):
            p.unlink()
        (run.art / "r1").rmdir()
        out = run.script("finish")
        self.assertEqual(out["status"], "failed")
        self.assert_contract(run, out)

    def test_lost_ripple_of_an_accepted_plan_is_not_called_no_plan(self):
        """案を受けた周で波及の一覧のノードが ripple.json を残さなかった時、出口が補う一覧の訳は「案が無い」でなく、一覧が無い訳"""
        run = PlanRun(self)
        run.include()
        (run.art / "r1" / files.RIPPLE).unlink()
        out = run.script("finish")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(run.json(out["ripple"])["error"], steps.RIPPLE_LOST)

    def test_rounds_count_and_second_round_gets_review(self):
        run = PlanRun(self)
        line = Line(run)
        self.assertEqual(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["round"], 1)
        review = {"faces": [FACE_MEAN]}
        second = seq({"plan": [item(1)]}, {"plan": [item(1, approach=CHANGED_APPROACH), item(2)], "block_answers": [FIXED_MEAN]})
        out = line.round(review, writer=second, fixer=second)
        self.assertEqual((out["round"], out["status"]), (2, "ok"), out)
        rnd = run.art / "r2"
        self.assertEqual(json.loads((rnd / files.PRIOR_COPIES["review"]).read_text(encoding="utf-8")), review)
        self.assertTrue((run.art / "r1" / files.REPLY).is_file(), "前の周のフォルダは消えない")
        self.assertIn("block の key key-a1-mean への答えが無い", rolekit.rejected(rnd, "plan")[0])
        side = json.loads((rnd / files.FIX_PLAN).read_text(encoding="utf-8"))
        self.assertEqual([p["unit_keys"] for p in side["plan"]], [[MEAN], [CLAMP]], "閉じた項目 2 を機械が差し込む")
        self.assertEqual(side["block_answers"][0]["key"], "key-a1-mean")
        trace = [json.loads(x) for x in (rnd / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["op"], r.get("id")) for r in trace if r["op"] == converge.DROPPED_OP],
                         [(converge.DROPPED_OP, converge.item_id([CLAMP]))], "前のまま書いた閉じた項目の行は捨てて trace に残す")

    def test_accepted_reply_without_handoff_removes_a_stale_handoff(self):
        """メモを返さずに受かった周は、周のフォルダに前から残るメモを消す（使い回した周の古いメモを次の周に前の周の物として載せない）"""
        run = PlanRun(self)
        rnd = run.art / "r1"

        def writer(n, prompt):
            (rnd / files.HANDOFF).write_text(json.dumps(HANDOFF_NOTE), encoding="utf-8")
            return {"plan": [item(1, 2)]}

        out = run.include(writer=writer)
        self.assertIs(out["ok"], True)
        self.assertFalse((rnd / files.HANDOFF).exists())
        self.assertIsNone(out["handoff"])

    def test_second_round_changing_a_closed_item_is_rejected(self):
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["ok"], True)
        changed = item(2, approach="閉じた項目 2 の手順を書き換えた形をここに書いた")
        role = seq({"plan": [item(1, approach=CHANGED_APPROACH), changed], "block_answers": [FIXED_MEAN]},
                   {"whole_plan": True, "plan": [item(1, approach=CHANGED_APPROACH)]})
        out = line.round({"faces": [FACE_MEAN]}, writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        why = rolekit.rejected(run.art / "r2", "plan")[0]
        self.assertTrue(why.startswith(steps.CLOSED_REJECT), why)

    def test_closed_row_shape_error_halts_on_the_first_try(self):
        """#851: 往復の記録から機械が差し込んだ閉じた項目の行が受け付けの形に合わない時は、役は閉じた項目を直せない（splice が拒む）ので
        拒みとして役へ返さず、1 回目で止める（status failed・halt）。訳は合わない欄を名指す"""
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["ok"], True)
        prior = line.prior({"faces": [FACE_MEAN]})
        prior["record"]["plan"][1]["row"]["route"] = "機械が壊した語"   # 記録の書き手の誤り（役の書いた行ではない）
        role = seq({"plan": [item(1, approach=CHANGED_APPROACH)], "block_answers": [FIXED_MEAN]})
        out = run.include(prior=prior, writer=role, fixer=role)
        self.assertEqual((out["ok"], out["status"]), (False, "failed"), out)
        self.assertIn(take.MACHINE_ROWS_HALT, out["reason"])
        self.assertIn("閉じた項目 2", out["reason"])
        self.assertIn("plan[1].route", out["reason"])
        self.assertEqual(len(writer_prompts(run)), 2, "1 周目と 2 周目の 1 回ずつ。2 周目の役に出し直させない")
        self.assertEqual(rolekit.rejected(run.art / "r2", "plan"), [], "役の拒否に数えない")
        self.assertTrue(run.read("r2/round.json")["halt"])

    def test_closed_row_without_an_ask_case_neither_halts_nor_rejects(self):
        """機械が差し込んだ閉じた項目の行は、人に聞く場合の印の照らし（gatemarks.ask_gaps）にも当てない。照らしを足す前の往復の記録の
        行が決め手も印も持たなくても、再開した run を止めず、役に直せない拒否も返さない"""
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["ok"], True)
        prior = line.prior({"faces": [FACE_MEAN]})
        prior["record"]["plan"][1]["row"]["narrows"] = [narrow(no_narrow=NO_NARROW)]
        role = seq({"plan": [item(1, approach=CHANGED_APPROACH)], "block_answers": [FIXED_MEAN]})
        out = run.include(prior=prior, writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        self.assertEqual(rolekit.rejected(run.art / "r2", "plan"), [])

    def test_role_row_without_an_ask_case_is_still_rejected(self):
        """照らしを外すのは記録から差し込んだ行だけ。役が書いた行が決め手も印も持たなければ、今どおり拒む"""
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["ok"], True)
        extra = item(2, narrows=[narrow(no_narrow=NO_NARROW)])
        role = seq({"plan": [item(1, approach=CHANGED_APPROACH), item(2), extra], "block_answers": [FIXED_MEAN]},
                   {"whole_plan": True, "plan": [item(1, approach=CHANGED_APPROACH)]})
        line.round({"faces": [FACE_MEAN]}, writer=role, fixer=role)
        why = rolekit.rejected(run.art / "r2", "plan")[0]
        self.assertIn(gatemarks.ASK_CASE_REJECT, why)
        self.assertIn("plan[2].narrows[0]", why)

    def test_closed_rows_tests_declared_by_an_open_item_do_not_halt(self):
        """項目の間の照らし（閉じた項目の files が足すテストを、開いた項目の tests が宣言する）は、閉じた項目の行 1 本だけでは誤りに
        見えても、案の全体で通るなら止めない（行 1 本に当てた項目の間の照らしの分は機械の誤りに数えない）"""
        adds = {"path": "test_stats.py", "op": "modify", "responsibility": "上限の枝の試験を足す",
                "home": {"concept": "単位 2 の試験", "why": "上限の枝の試験は test_stats.py が持つ"},
                "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}],
                "symbols": [{"name": "test_mean_of_two", "change": "add"}]}
        two = item(2, tests=[], rewrite_tests=[REWRITE], route="direct", route_why="上限の枝の戻り値を 1 か所直すだけ")
        two["files"] = [*two["files"], adds]
        run = PlanRun(self)
        line = Line(run)
        first = line.round(writer=writer_of({"plan": [item(1), two]}))
        self.assertIs(first["ok"], True, first)
        self.assertEqual(planmarks._added_test_gaps([run.json(first["reply"])["plan"][1]]) != [], True, "行 1 本では誤りに見える")
        role = seq({"plan": [item(1, approach=CHANGED_APPROACH)], "block_answers": [FIXED_MEAN]})
        out = line.round({"faces": [FACE_MEAN]}, writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        self.assertEqual(len(writer_prompts(run)), 2)

    def test_closed_item_with_machine_limit_is_not_rejected(self):
        """#845: line の往復の記録の案の行は、事前審査が planmarks.joined で欄の行を重ねた物で、rewrite_tests の行に機械が足した範囲
        limit を持つ。閉じた項目をその行で差し込んでも、前のまま書いた閉じた項目も、limit を理由に拒まない。役が自分で書いた limit は拒む"""
        rewrite = {"id": "test_stats.py::TestStats::test_clamp_above_range", "behavior": "上限を超えた値に上限を返す",
                   "old": "lo を返す", "new": "上限を超えたら hi を返す"}
        for name, closed in (("差し込む", []), ("前のまま書く", [item(2, rewrite_tests=[rewrite])])):
            with self.subTest(name):
                run = PlanRun(self)
                line = Line(run)
                first = line.round(writer=writer_of({"plan": [item(1), item(2, rewrite_tests=[rewrite])]}))
                self.assertIs(first["ok"], True, first)
                prior = line.prior({"faces": [FACE_MEAN]})
                fields = run.json(first["plan"])["fields"]
                self.assertEqual(fields[1]["rewrite_tests"][0]["limit"], "test_stats.py:14")
                joined = [planmarks.joined(r, f) for r, f in zip(run.json(first["reply"])["plan"], fields)]
                prior["record"]["plan"] = converge.plan_rows(joined)   # plan-review の note_plan と同じ行
                own = item(1, approach=CHANGED_APPROACH, rewrite_tests=[{**rewrite, "limit": "test_stats.py:14"}])
                role = seq({"plan": [own, *closed], "block_answers": [FIXED_MEAN]},
                           {"plan": [item(1, approach=CHANGED_APPROACH), *closed]})
                out = run.include(prior=prior, writer=role, fixer=role, typed=False)   # 役の書いた limit を受け付けまで通す
                self.assertIs(out["ok"], True, out)
                why = rolekit.rejected(run.art / "r2", "plan")
                self.assertEqual(len(why), 1, why)
                self.assertIn("plan[0].rewrite_tests[0]: 知らない欄 'limit'", why[0], "役の書いた limit は拒む")
                self.assertNotIn("plan[1]", why[0])
                self.assertNotIn(steps.CLOSED_REJECT, why[0])
                self.assertEqual(run.json(out["reply"])["plan"][1]["rewrite_tests"], [rewrite], "受けた案の閉じた項目は役の書く形")

    def test_record_rows_return_to_the_accepted_items(self):
        """#849: 事前審査が往復の記録の plan に置く行（narrows の決め手の欄を外し、機械が足した limit を持つ欄の行を重ねた物）を
        bare_record で戻すと、受けた案の全部の項目と字のまま同じになり、hash も受けた項目の物と同じ（欄が欠ける向きも余る向きも無い）"""
        run = PlanRun(self)
        first = run.include(writer=writer_of({"plan": [item(1, narrows=[MARKED]),
                                                       item(2, rewrite_tests=[REWRITE], narrows=[MARKED, narrow(no_narrow=NO_NARROW, undecided_because=MARKED["undecided_because"])])]}))
        self.assertIs(first["ok"], True, first)
        rows = review_rows(run, first)
        self.assertNotIn(gatemarks.NO_NARROW, rows[1]["row"]["narrows"][0], "事前審査の行は決め手の欄を外した形")
        self.assertIn("limit", rows[1]["row"]["rewrite_tests"][0], "事前審査の行は機械の欄 limit を持つ")
        got = take.bare_record({"round": 1, "passes": [], "outcome": None, "open": {}, "plan": rows})["plan"]
        want = run.json(first["reply"])["plan"]
        self.assertEqual([it["row"] for it in got], want)
        self.assertEqual([it["hash"] for it in got], [converge.item_hash(r) for r in want])

    def test_second_round_returns_only_changed_items(self):
        """#571: 2 往復目の修正案の役は変えた項目だけを返す。返さない開いた項目は機械が前の往復の行を差し込み、受けた案は全部の
        項目を持つ。fixed と答えた block の項目を変えていない答えは拒む"""
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1), item(2)]}))["ok"], True)
        first = json.loads((run.art / "r1" / files.REPLY).read_text(encoding="utf-8"))["plan"]
        changed = item(1, approach=CHANGED_APPROACH)
        fixed_both = [FIXED_MEAN, {"key": "key-b1-clamp", "handled": "fixed", "how": "下限の枝も直したことにした"}]
        disputed = [FIXED_MEAN, {"key": "key-b1-clamp", "handled": "disputed", "how": "下限の枝は呼び手が先に弾いている"}]
        role = seq({"plan": [changed], "block_answers": fixed_both}, {"block_answers": disputed})
        out = line.round({"faces": [FACE_MEAN, FACE_CLAMP]}, writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        why = rolekit.rejected(run.art / "r2", "plan")
        self.assertEqual(len(why), 1, why)
        self.assertIn("block key-b1-clamp を fixed と答えたが、その block の項目 2 を変えていない", why[0])
        got = run.json(out["reply"])["plan"]
        self.assertEqual(got[1], first[1], "返さない開いた項目は前の往復の行のまま")
        self.assertEqual(got[0]["approach"], changed["approach"])
        kept = json.loads(rolekit.candidate_path(run.art / "r2", "plan").read_text(encoding="utf-8"))
        self.assertEqual(kept["plan"], got, "出し直しの役が読む控えは、機械が前の往復の行を差し込んだ案の全体")

    def test_second_round_counts_its_own_rejections(self):
        """拒否の控えは周ごと: 1 周目に 2 回拒まれても、2 周目は 0 から数えて受け付けの網の回まで出し直せる"""
        run = PlanRun(self)
        line = Line(run)
        bad = {"plan": [item(1)]}
        role = seq(bad, bad, {"plan": [item(1, 2)]})
        self.assertIs(line.round(writer=role, fixer=role)["ok"], True)
        self.assertEqual(len(rolekit.rejected(run.art / "r1", "plan")), 2)
        role = seq(bad, bad, {"plan": [item(1, 2)]})
        out = line.round({"faces": []}, writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        self.assertEqual(run.out["plan-accept"]["attempt"], 3)
        self.assertEqual(len(rolekit.rejected(run.art / "r2", "plan")), 2)
        self.assertEqual(len(out["rejects"]), 2)
        self.assertEqual(len(rolekit.rejected(run.art / "r1", "plan")), 2, "前の周の拒否の控えは残る")

    def test_route_up_row_keeps_ok(self):
        run = PlanRun(self)
        out = run.include(structure=structure(run, dirty_rows(route=True)),
                          writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["status"], "ok")

    def test_finish_returns_the_fix_plan_rejects_and_status(self):
        """#681: 出口は、ほかの block が読む周のフォルダの控えを欄で返す: 修正案の役の返答の pointer fix_plan（周の p2.fix_plan.json）・
        受け付けの拒否の行 rejects・status（義務 0 件の周は nothing_owed）・諦めの行 gave_up（形 plan は null）"""
        run = PlanRun(self)
        out = run.include()
        self.assertEqual(run.pointed(out["fix_plan"]), run.pointed(out["plan"]).parent / files.FIX_PLAN)
        self.assertTrue(run.json(out["fix_plan"])["plan"])
        self.assertEqual((out["rejects"], out["status"], out["gave_up"], out["mode"]), ([], "ok", None, "plan"))
        self.assertEqual(run.pointed(out["reply"]), run.art / "r1" / files.REPLY)

    def test_nothing_owed_skips_the_role(self):
        run = PlanRun(self, judge={"units": [unit(NIT, "nit", None)], "questions": []})
        out = run.include(writer=never(self))
        self.assertEqual(out["status"], "nothing_owed")
        self.assertIsNone(out["fix_plan"])
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ok"], False)
        self.assertEqual(out["owed"], [])
        self.assertIn(steps.NOTHING_OWED, run.json(out["ripple"])["error"])
        for key in ("plan", "ripple"):
            run.pointed(out[key])
        self.assertEqual(run.json(out["plan"])["fields"], [])

    def test_stuck_unit_skips_the_role(self):
        """同じ key の単位が開いた行と開いていない行で来た判定は行き止まり（必ず入れるのに案に入れられない）。義務 0 件ではない"""
        run = PlanRun(self, judge={"units": [unit(MEAN), unit(MEAN, "nit", None)], "questions": []})
        out = run.include(writer=never(self))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertIs(out["ok"], False)
        self.assertEqual(out["status"], "held")
        self.assertIn(steps.PLAN_STUCK, run.json(out["ripple"])["error"])
        self.assertIn(steps.PLAN_STUCK, out["reason"])

    def test_unreadable_pointer_inputs_are_not_absent(self):
        """空の字だけが「無い」。line が渡した pointer が読めない入力は、役を起こさずに held で訳を残す"""
        for name in ("judgment", "world_rows", "prior"):
            with self.subTest(name):
                run = PlanRun(self)
                out = run.include(**{name: missing()}, writer=never(self))
                self.assertEqual(run.status["plan-loop"], "skipped")
                self.assertEqual((out["ok"], out["status"]), (False, "held"))
                error = run.json(out["ripple"])["error"]
                self.assertIn(f"{name} が読めない", error)
                self.assertIn("nowhere/x.json", error)
        run = PlanRun(self)
        out = run.include(prior="{壊れた", writer=never(self))
        self.assertEqual(out["status"], "held")
        self.assertIn("prior が読めない", run.json(out["ripple"])["error"])


class SurvivesCase(unittest.TestCase):
    """周を開く node と出口は落ちない（出口が周のフォルダを束ねる。line は落ちた出口の先へ進めない）"""

    def no_lib(self, run) -> pathlib.Path:
        broken = run.tmp / "no-lib"
        broken.mkdir(exist_ok=True)
        return broken

    def test_intake_and_finish_survive_a_lib_that_does_not_load(self):
        run = PlanRun(self)
        run.env_extra = {"WORKS_FACTORY_ROOT": str(self.no_lib(run))}
        rnd = run.script("intake")
        self.assertEqual(validate_schema(rnd, base.node("intake")["output_format"]), [])
        self.assertEqual((rnd["round"], rnd["go"]), (1, False))
        why = run.read("r1/round.json")["why"]
        self.assertIn("周を開くノードの中で誤りが起きた: ModuleNotFoundError", why)
        out = run.script("finish")
        self.assertEqual(validate_schema(out, FINISH_FORMAT), [])
        self.assertEqual((out["ok"], out["status"], out["round"], out["owed"]), (False, "failed", 1, []))
        self.assertEqual((out["plan"], out["ripple"]), (None, None), "形を照らせない出口は照らさずに指さない")
        self.assertIn("ModuleNotFoundError", out["reason"])
        self.assertIn("ModuleNotFoundError", (run.art / "r1" / files.FINISH_ERROR).read_text(encoding="utf-8"))
        run.env_extra = {}
        again = run.script("intake")
        self.assertEqual((again["round"], again["go"]), (1, True), "lib が読める次の入口は同じ周を開き直す（周の番号は prior が決める）")
        self.assertNotIn("error", run.read("r1/round.json"))

    def test_a_crashed_intake_never_reopens_the_previous_round(self):
        """lib が読めず落ちた入口は、前の周のフォルダ（prior の pointer の先）に書かず、新しい周に error を残す。出口は前の案があっても failed"""
        run = PlanRun(self)
        line = Line(run)
        first = line.round()
        before = {n: (run.art / "r1" / n).read_bytes() for n in (files.REPLY, files.FIELDS, files.ROUND, files.RIPPLE)}
        run.env_extra = {"WORKS_FACTORY_ROOT": str(self.no_lib(run))}
        prior = line.prior(None)
        run.inputs["prior"] = json.dumps(prior, ensure_ascii=False)
        rnd = run.script("intake")
        self.assertEqual((rnd["round"], rnd["go"]), (first["round"] + 1, False))
        self.assertTrue(run.read("r2/round.json")["error"])
        self.assertEqual(run.read("current-round.json"), {"round": 2})
        run.script("ripple_items", check=False)   # lib が読めないので node は落ちる（出口は all_done で進む）
        out = run.script("finish")
        self.assertEqual((out["status"], out["round"]), ("failed", 2))
        for name, data in before.items():
            self.assertEqual((run.art / "r1" / name).read_bytes(), data, name)

    def test_intake_takes_over_a_folder_left_half_open(self):
        """周のフォルダが既に在れば開き直す。消すのは周の名のファイルだけ（ほかのファイルと、place の直下の指示の記録は残す）"""
        run = PlanRun(self)
        rnd = run.art / "r1"
        rnd.mkdir(parents=True)
        run.env_extra = {"WORKS_FACTORY_ROOT": str(self.no_lib(run))}
        self.assertEqual(run.script("intake")["round"], 1)
        run.env_extra = {}
        (rnd / files.REPLY).write_text("{}", encoding="utf-8")
        (rnd / "keep.txt").write_text("x", encoding="utf-8")
        (run.art / "plan-writer-prompt-1.md").write_text("前の指示", encoding="utf-8")
        got = run.script("intake")
        self.assertEqual((got["round"], got["go"]), (1, True))
        self.assertFalse((rnd / files.REPLY).exists())
        self.assertTrue((rnd / "keep.txt").exists())
        self.assertTrue((run.art / "plan-writer-prompt-1.md").exists())

    def test_question_with_depends_that_is_not_a_list(self):
        """判定の問いの depends が配列でない判定は、port の形（shared:judgment.schema.json）が拒む: 周を開かず、読めない入力を名指す"""
        judge = judgment()
        judge["questions"] = [{"key": "q", "kind": "fork", "status": "held", "origin": CLAMP, "depends": 3}]
        run = PlanRun(self, judge=judge)
        out = run.include(writer=never(self))
        self.assertEqual(out["status"], "held", out)
        self.assertIn("$.questions[0].depends", out["reason"])


class BriefCase(unittest.TestCase):
    """修正案の役の指示の材料の代表 1 本: 方針は line が固めた写しを渡す（指示の字の残りは workflows/.shared/prompt.py の emit が
    印と値の対で照らす）"""

    def prompt(self, run, n=0):
        return writer_prompts(run)[n]

    def test_policy_is_the_frozen_copy_the_line_passes(self):
        """修正案の指示が貼り名指す方針は、port policy の写し（対象のリポジトリの生の文書ではない）"""
        run = PlanRun(self)
        (run.repo / "POLICY.md").write_text("生の方針の文\n", encoding="utf-8")
        frozen = run.art / "policy" / "frozen.md"
        frozen.parent.mkdir(parents=True)
        frozen.write_text("固めた方針の文\n", encoding="utf-8")
        self.assertIs(run.include(policy=str(frozen))["ok"], True)
        prompt = self.prompt(run)
        self.assertIn("固めた方針の文", prompt)
        self.assertIn(f"- Policy document: name `{frozen}:<line>`", prompt)
        self.assertNotIn("生の方針の文", prompt)


class PlaceCase(unittest.TestCase):
    """値で受けた入力の写し・include ごとの place・周のフォルダの残り（docs/design/plan.md の 1.4・9.2 の足す）"""

    def test_values_are_copied_into_the_round_and_named(self):
        """judgment と prior の欄を値で受けると、周のフォルダに写しを書き、指示はそのパスを名指す。パスと pointer で受けた欄は写さず、
        受けたパスを名指す"""
        judge = judgment()
        judge["units"][0]["prescriptions"] = ["分母を len(xs) にする"]
        run = PlanRun(self)
        run.inputs["judgment"] = json.dumps(judge, ensure_ascii=False)
        first = run.include(writer=writer_of({"plan": [item(1, 2)], "handoff": HANDOFF_NOTE}))
        self.assertIs(first["ok"], True, first)
        copied = run.art / "r1" / files.JUDGMENT_COPY
        self.assertEqual(json.loads(copied.read_text(encoding="utf-8")), judge)
        self.assertIn(f"Judgment record: {copied}", writer_prompts(run)[0])
        review = {"faces": []}
        reply, fields = run.json(first["reply"]), run.json(first["plan"])
        fix_plan = str(run.pointed(first["fix_plan"]))
        prior = {"round": 1, "reply": reply, "fields": fields, "fix_plan": fix_plan, "ripple": first["ripple"], "review": review,
                 "record": converge_record([(None, reply), (review, None)], run.tmp), "handoffs": [{"round": 1, "handoff": HANDOFF_NOTE}]}
        second = run.include(prior=prior)
        self.assertEqual((second["round"], second["status"]), (2, "ok"), second)
        r2 = run.art / "r2"
        for field, value in (("reply", reply), ("fields", fields), ("review", review)):
            self.assertEqual(json.loads((r2 / files.PRIOR_COPIES[field]).read_text(encoding="utf-8")), value, field)
        for field in ("fix_plan", "ripple"):
            self.assertFalse((r2 / files.PRIOR_COPIES[field]).exists(), field)
        note = r2 / "prior-handoff-r1.json"
        self.assertEqual(json.loads(note.read_text(encoding="utf-8")), HANDOFF_NOTE)
        prompt = writer_prompts(run)[-1]
        self.assertIn(f"- Plan of the previous round: {fix_plan} and {r2 / files.PRIOR_COPIES['fields']}", prompt)
        self.assertIn(f"- Review findings: {r2 / files.PRIOR_COPIES['review']}", prompt)
        self.assertIn(f"- r1: {note} (Read it)", prompt)
        self.assertIn(RIPPLE_HEAD, prompt, "pointer で受けた前の周の波及の一覧を読む")
        self.assertIn(f"Judgment record: {r2 / files.JUDGMENT_COPY}", prompt)

    def test_includes_with_different_places_share_no_files(self):
        """2 つの include は place（$ARTIFACTS_DIR/<include の id>/）が分かれ、互いのファイルに触れない。後の周は前の周のフォルダを消さない"""
        run = PlanRun(self)

        def at(name):
            run.env_extra = {"ARCHON_NODE_EXECUTION": json.dumps({"runId": RUN_ID, "path": f"{name}__intake"})}

        def snapshot(folder):
            return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}

        at("plan-a")
        line_a = Line(run)
        out_a = line_a.round()
        at("plan-b")
        out_b = run.include(prior="")
        self.assertEqual((out_a["plan"]["path"], out_b["plan"]["path"]), ("plan-a/r1/plan-fields.json", "plan-b/r1/plan-fields.json"))
        self.assertFalse((run.art / "r1").exists())
        self.assertFalse((run.art / files.CURRENT_ROUND).exists())
        for name in ("plan-a", "plan-b"):
            self.assertTrue((run.art / name / "plan-writer-prompt-1.md").is_file(), name)
            self.assertEqual(run.read(f"{name}/{files.CURRENT_ROUND}"), {"round": 1})
        first_a, all_b = snapshot(run.art / "plan-a" / "r1"), snapshot(run.art / "plan-b")
        at("plan-a")
        out = line_a.round({"faces": []})
        self.assertEqual((out["round"], out["status"], out["plan"]["path"]), (2, "ok", "plan-a/r2/plan-fields.json"), out)
        self.assertEqual(snapshot(run.art / "plan-a" / "r1"), first_a, "後の周は前の周のフォルダを消さず、書き換えない")
        self.assertEqual(snapshot(run.art / "plan-b"), all_b, "ほかの include の place に触れない")
        self.assertTrue((run.art / "plan-a" / "plan-writer-prompt-2.md").is_file(), "指示の記録は周をまたいで数え続ける")
        self.assertTrue((run.art / "plan-a" / "plan-writer-prompt-1.md").is_file())


class StatusCase(unittest.TestCase):
    """status の 5 つの語はそれぞれの道で出る・owed は判定の順の直す義務の単位（docs/design/plan.md の 1.2）"""

    def test_ok(self):
        run = PlanRun(self)
        out = run.include()
        self.assertEqual((out["ok"], out["status"], out["reason"]), (True, "ok", ""))

    def test_nothing_owed(self):
        run = PlanRun(self, judge={"units": [unit(NIT, "nit", None)], "questions": []})
        out = run.include(writer=never(self))
        self.assertEqual((out["ok"], out["status"], out["reason"]), (False, "nothing_owed", steps.NOTHING_OWED))

    def test_held(self):
        run = PlanRun(self)
        out = run.include(judgment=missing(), writer=never(self))
        self.assertEqual((out["ok"], out["status"]), (False, "held"))
        self.assertIn("judgment が読めない", out["reason"])

    def test_gave_up(self):
        """拒否の控えが扱えない受け付けは輪を抜け、出口は failed（機械の故障）と訳を返す"""
        run = PlanRun(self)

        def writer(n, prompt):
            (run.art / "r1" / files.REJECTS).write_text("{壊れた", encoding="utf-8")
            return {"plan": [item(1)]}

        out = run.include(writer=writer)
        self.assertEqual((out["ok"], out["status"]), (False, "failed"), out)
        self.assertIn("拒否の控えが扱えない", out["reason"])

    def test_failed(self):
        """入口の中の誤り（lib が読めない）は、出口が failed と訳を返す（出口そのものは lib を読める）"""
        run = PlanRun(self)
        broken = run.tmp / "no-lib"
        broken.mkdir()
        script = run.script

        def only_intake_breaks(name, bound=None, *, check=True):
            run.env_extra = {"WORKS_FACTORY_ROOT": str(broken)} if name == "intake" else {}
            return script(name, bound, check=check)

        run.script = only_intake_breaks
        out = run.include(writer=never(self))
        self.assertEqual((out["ok"], out["status"]), (False, "failed"), out)
        self.assertIn("周を開くノードの中で誤りが起きた: ModuleNotFoundError", out["reason"])
        self.assertFalse((run.art / "r1" / files.FINISH_ERROR).exists(), "出口は落ちていない")

    def test_owed_is_the_owed_units_in_judgment_order(self):
        """owed は直す義務の単位の key を判定の順に（開いていない単位と、人の答え待ちの問いの出どころは入れない）"""
        other = "stats.py median: 偶数個の列で真ん中の 1 つを返す"
        judge = {"units": [unit(CLAMP), unit(NIT, "nit", None), unit(other), unit(MEAN)],
                 "questions": [{"key": "q-median", "kind": "fork", "status": "held", "origin": other, "depends": []}]}
        run = PlanRun(self, judge=judge, units=[*catalog(), {"id": other, "paths": ["stats.py"], "summary": "median"}])
        out = run.include(writer=writer_of({"plan": [item(1, 3)]}))
        self.assertEqual(out["status"], "ok", out)
        self.assertEqual(out["owed"], [CLAMP, MEAN])


if __name__ == "__main__":
    unittest.main()
