"""plan の block の周と出口と指示の材料の検査（docs/design/plan.md の 1.2〜1.4・2.3・9.2）。

今の tests/workflows/test_plan.py の CollectCase・SurvivesCase・BriefCase の写しと、9.2 の「足す」の 4 つ（値で受けた判定と前の周の欄の写し・
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
from tests.blocks.plan.base import (CLAMP, DIRTY_ROW, HANDOFF_NOTE, LOOSE, MEAN, NIT, RUN_ID, PlanRun, catalog, item, judgment, narrow,
                                    unit, writer_of)

steps = kit.load("plan", "steps")
take = importlib.import_module("src.take")   # kit.load が置いた src の package から
brief = kit.load("plan", "brief")
files = kit.load("plan", "files")

import converge  # noqa: E402  （lib/。base が sys.path に足す）
import gatemarks  # noqa: E402
import libdocs  # noqa: E402
import planmarks  # noqa: E402
import rolekit  # noqa: E402
import structmark  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

FORK = "f0" * 20   # 差分の run の差分の根（読む版と違う版）

# md の札（prompts/plan-writer.md と workflows/.shared/prompts/ の断片の見出しと頼みの頭）
ROLE_HEAD = "You are the planning role, and you only read."
PRIOR_HEAD = "## The previous round's plan and the review's findings"
NO_REVIEW = "- Review findings: not received"
HANDOFF_ASK = "In the answer field `handoff`"
HANDOFF_ROUNDS = "Notes that earlier rounds of you wrote"
UNITS_HEAD = "## Units to fix in this round"
FILLED = "- The machine fills in these numbers (items of the previous pass's plan; you need not write items you do not change; do not write closed items): "
RIPPLE_HEAD = "## Ripple list (looked up by the machine with git grep: the callers and tests of the names that the items change)"
UNITS_RIPPLE_HEAD = "## Ripple list before the plan"
STRUCT_HEAD = "## Rows of the structure eye"
STRUCT_ASK = "For an item that has the unit of a row seen as dirtying, write per row"
STRUCT_NONE = "No row was seen as dirtying the structure"
STRUCT_CLEAN_HEAD = "### Rows seen as not dirtying"
POLICY_HEAD = "## The person's policy"
PRIOR_FAILURES_HEAD = "## What did not pass to the end in the previous run"
MAP_HEAD = "## Map of where concepts live"
RECORDED_HEAD = "## Recorded policy"
PRESCRIPTION_HEAD = "## Prescriptions of the judgment"
EXCLUDED = "Range of parallel pull requests. Do not touch it, and do not put it in a unit: "
SPEC_HEAD = "## Spec (requirements and acceptance tests."
UNREAD_HEAD = "## Inputs that could not be read"
ROUTES_SPEC_HEAD = "## Route of each item (decided by the spec)"
LANG_LINE = "Write the fields that people read ("
LAST_LINE = "Return only JSON that matches the output schema."

FACE_MEAN = {"key": "key-a1-mean", "kind": "regression", "where": "stats.py", "why": "空の列が落ちる", "severity": "block",
             "unit_keys": [MEAN]}
FACE_CLAMP = {"key": "key-b1-clamp", "kind": "regression", "where": "stats.py", "why": "下限の枝が抜ける", "severity": "block",
              "unit_keys": [CLAMP]}
NO_NARROW = "狭めない案として空の列に 0 を返す形を当たったが、呼び手が例外を捕まえている"
MARKED = narrow(no_narrow=NO_NARROW, undecided_because="空の列を渡す呼び手が在るかは依頼に書いていない",
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


def converge_record(rounds) -> dict:
    """往復の記録（line が prior.record に渡す物。今の planfile.converge_record の中身）。rounds は周ごとの
    (その周を開いた時に受けた事前審査, その周の受けた案[, 記録の plan に置く行])。最後は今開く周で、案は None。行を渡さなければ
    受けた案の項目そのものから組む"""
    doc = {"round": 0, "passes": [], "outcome": None, "open": {}}
    answers: list = []
    for k, (review, reply, *rows) in enumerate(rounds, 1):
        doc["round"] = k
        if isinstance(review, dict) and doc.get("plan"):
            resolved = review.get(converge.RESOLVED)
            converge.add_pass(doc, review, answers=copy.deepcopy(answers), resolved=resolved if isinstance(resolved, list) else [])
        if isinstance(reply, dict) and isinstance(reply.get("plan"), list):
            doc["plan"] = rows[0] if rows else converge.plan_rows(reply["plan"])
            answers = [r for r in reply.get(converge.ANSWERS) or [] if isinstance(r, dict)]
    return doc


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
                "record": converge_record(rounds),
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

    def test_first_round_reads_empty_prior_and_null_review_alike(self):
        """空の prior は 1 周目（前の周の節も写しも無い）。2 周目の review が null でも欄が無くても、受けていない 1 文になる"""
        run = PlanRun(self)
        out = run.include(prior="")
        self.assertEqual((out["round"], out["status"]), (1, "ok"))
        self.assertNotIn(PRIOR_HEAD, writer_prompts(run)[0])
        self.assertFalse([n for n in files.PRIOR_COPIES.values() if (run.art / "r1" / n).exists()])
        for form in ("null", "absent"):
            with self.subTest(review=form):
                run = PlanRun(self)
                line = Line(run)
                line.round()
                prior = line.prior(None)
                if form == "absent":
                    del prior["review"]
                out = run.include(prior=prior)
                self.assertEqual((out["round"], out["status"]), (2, "ok"), out)
                prompt = writer_prompts(run)[-1]
                self.assertIn(PRIOR_HEAD, prompt)
                self.assertIn(NO_REVIEW, prompt)
                self.assertFalse((run.art / "r2" / files.PRIOR_COPIES["review"]).exists())

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
        prompt = writer_prompts(run)[-1]
        self.assertIn(PRIOR_HEAD, prompt)
        self.assertIn(f"- Review findings: {rnd / files.PRIOR_COPIES['review']}", prompt)
        self.assertIn("### key-a1-mean", prompt)
        self.assertIn(f"- no 1 `{MEAN}`: label=block・disposition=do-now・{brief.DUTY_FILLED}", prompt)
        self.assertIn(f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{brief.DUTY_FILLED}", prompt)
        self.assertIn(FILLED + "[1, 2]", prompt)
        self.assertIn(RIPPLE_HEAD, prompt, "前の周の項目ごとの波及の一覧")
        self.assertTrue((run.art / "r1" / files.REPLY).is_file(), "前の周のフォルダは消えない")
        self.assertIn("block の key key-a1-mean への答えが無い", rolekit.rejected(rnd, "plan")[0])
        side = json.loads((rnd / files.FIX_PLAN).read_text(encoding="utf-8"))
        self.assertEqual([p["unit_keys"] for p in side["plan"]], [[MEAN], [CLAMP]], "閉じた項目 2 を機械が差し込む")
        self.assertEqual(side["block_answers"][0]["key"], "key-a1-mean")
        trace = [json.loads(x) for x in (rnd / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["op"], r.get("id")) for r in trace if r["op"] == converge.DROPPED_OP],
                         [(converge.DROPPED_OP, converge.item_id([CLAMP]))], "前のまま書いた閉じた項目の行は捨てて trace に残す")

    def test_second_round_prompt_names_the_prior_handoff(self):
        """1 往復目の役が引き継ぎのメモつきで返した案が受かると、メモは周のフォルダに置かれ、2 往復目の指示が前の周のメモのパスを名指す
        （中身は貼らない）。メモを書けという頼みは 1 往復目の指示にも載る"""
        run = PlanRun(self)
        line = Line(run)
        self.assertIs(line.round(writer=writer_of({"plan": [item(1, 2)], "handoff": HANDOFF_NOTE}))["ok"], True)
        first = run.art / "r1"
        self.assertEqual(json.loads((first / files.HANDOFF).read_text(encoding="utf-8")), HANDOFF_NOTE)
        self.assertIn(HANDOFF_ASK, writer_prompts(run)[0])
        line.round({"faces": []})
        prompt = writer_prompts(run)[-1]
        self.assertIn(HANDOFF_ROUNDS, prompt, "前の周のメモの使い方の案内も届く")
        self.assertIn(f"- r1: {first / files.HANDOFF} (Read it)", prompt)
        self.assertNotIn(HANDOFF_NOTE["kept"][0], prompt)

    def test_third_round_prompt_names_every_prior_handoff_oldest_first(self):
        run = PlanRun(self)
        line = Line(run)
        again = {**HANDOFF_NOTE, "kept": ["二往復目で決めた訳"]}
        self.assertIs(line.round(writer=writer_of({"plan": [item(1, 2)], "handoff": HANDOFF_NOTE}))["ok"], True)
        self.assertIs(line.round({"faces": []}, writer=writer_of({"plan": [item(1, 2)], "handoff": again}))["ok"], True)
        line.round({"faces": []})
        first, second = (str(run.art / f"r{n}" / files.HANDOFF) for n in (1, 2))
        prompt = writer_prompts(run)[-1]
        self.assertIn(f"- r1: {first} (Read it)", prompt)
        self.assertIn(f"- r2: {second} (Read it)", prompt)
        self.assertLess(prompt.index(first), prompt.index(second))
        self.assertLess(prompt.index(HANDOFF_ROUNDS), prompt.index(first))
        for note in (HANDOFF_NOTE, again):
            self.assertNotIn(note["kept"][0], prompt)

    def test_second_round_prompt_says_when_the_prior_round_left_no_handoff(self):
        """前の周の役がメモを書かなかった時は、2 往復目の指示がメモの無いことを名指す（黙って落とさない）。前の周そのものが無い
        1 往復目の指示には、前の周のメモの段落を出さない（書かなかった事実が無い）"""
        run = PlanRun(self)
        line = Line(run)
        line.round()
        self.assertNotIn(HANDOFF_ROUNDS, writer_prompts(run)[0])
        line.round({"faces": []})
        prompt = writer_prompts(run)[-1]
        self.assertIn(HANDOFF_ROUNDS, prompt)
        self.assertIn("- r1: (no notes)", prompt)
        self.assertNotIn(str(run.art / "r1" / files.HANDOFF), prompt)

    def test_resubmit_without_handoff_keeps_the_first_handoff(self):
        """1 回目の返答がメモつきで拒まれ、出し直しがメモを返さずに受かると、周のメモは 1 回目の物になる"""
        run = PlanRun(self)
        role = seq({"plan": [item(1)], "handoff": HANDOFF_NOTE}, {"plan": [item(1, 2)]})
        out = run.include(writer=role, fixer=role)
        self.assertIs(out["ok"], True, out)
        rnd = run.art / "r1"
        self.assertEqual(len(rolekit.rejected(rnd, "plan")), 1)
        self.assertEqual(json.loads((rnd / files.HANDOFF).read_text(encoding="utf-8")), HANDOFF_NOTE)
        self.assertEqual(run.json(out["handoff"]), HANDOFF_NOTE)

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

    def test_second_round_prompt_opens_with_the_role_head(self):
        """元 tests/test_blk_plan.py の test_revise_prompt_names_blocks_and_keys: 2 周目の指示も役の頭から始まり、独立設計の節は無い"""
        run = PlanRun(self)
        line = Line(run)
        line.round()
        line.round({"faces": []})
        prompt = writer_prompts(run)[-1]
        self.assertIn(PRIOR_HEAD, prompt)
        self.assertTrue(prompt.startswith(ROLE_HEAD), prompt[:200])
        self.assertNotIn("independent design", prompt.lower())

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
                                                       item(2, rewrite_tests=[REWRITE], narrows=[MARKED, narrow(no_narrow=NO_NARROW)])]}))
        self.assertIs(first["ok"], True, first)
        rows = review_rows(run, first)
        self.assertNotIn(gatemarks.NO_NARROW, rows[1]["row"]["narrows"][0], "事前審査の行は決め手の欄を外した形")
        self.assertIn("limit", rows[1]["row"]["rewrite_tests"][0], "事前審査の行は機械の欄 limit を持つ")
        got = take.bare_record({"round": 1, "passes": [], "outcome": None, "open": {}, "plan": rows})["plan"]
        want = run.json(first["reply"])["plan"]
        self.assertEqual([it["row"] for it in got], want)
        self.assertEqual([it["hash"] for it in got], [converge.item_hash(r) for r in want])

    def test_closed_item_with_marked_narrows_is_not_rejected(self):
        """#849: 閉じた項目の narrows の行の決め手の欄（no_narrow など）は、往復の記録から差し込んでも、前のまま書いても欠けず、
        欠けを理由に拒まない。受けた案の閉じた項目は役の書いた形のまま。役が自分で書いた項目の no_narrow の欠けは今と同じに拒む"""
        two = item(2, rewrite_tests=[REWRITE], narrows=[MARKED])
        for name, closed in (("差し込む", []), ("前のまま書く", [two])):
            with self.subTest(name):
                run = PlanRun(self)
                line = Line(run)
                first = line.round(writer=writer_of({"plan": [item(1, narrows=[MARKED]), two]}))
                self.assertIs(first["ok"], True, first)
                bare = narrow()   # 役が no_narrow を書かなかった行
                role = seq({"plan": [item(1, approach=CHANGED_APPROACH, narrows=[bare]), *closed], "block_answers": [FIXED_MEAN]},
                           {"plan": [item(1, approach=CHANGED_APPROACH, narrows=[MARKED]), *closed]})
                out = line.round({"faces": [FACE_MEAN]}, writer=role, fixer=role, typed=False)   # 欠けを受け付けまで通す
                self.assertIs(out["ok"], True, out)
                why = rolekit.rejected(run.art / "r2", "plan")
                self.assertEqual(len(why), 1, why)
                self.assertIn(steps.NO_NARROW_REJECT, why[0])
                self.assertIn("plan[0].narrows[0]", why[0], "役の書いた行の no_narrow の欠けは拒む")
                self.assertNotIn("plan[1]", why[0])
                self.assertNotIn(steps.CLOSED_REJECT, why[0])
                self.assertEqual(run.json(out["reply"])["plan"][1], run.json(first["reply"])["plan"][1], "閉じた項目は役の書いた形のまま")

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

    def test_failed_structure_note_reaches_the_prompt(self):
        """元 tests/test_structure_eye.py の test_block_reason_reaches_the_mark: 構造の目の失敗は役を止めず、行なしで計画する"""
        run = PlanRun(self)
        reason = "構造の目の返答が 3 回とも受け付けで拒まれた"
        out = run.include(structure=structure(run, status="failed", reason=reason))
        self.assertEqual(run.status["plan-loop"], "ok")
        self.assertIs(out["ok"], True, out)
        self.assertIn(f"{structmark.MISSING}（理由: {reason}", writer_prompts(run)[0])

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
        for key in ("plan", "ripple"):
            run.pointed(out[key])
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
        """判定の問いの depends が数でも周を開け、owed は直す義務の単位だけ"""
        judge = judgment()
        judge["questions"] = [{"key": "q", "kind": "fork", "status": "held", "origin": CLAMP, "depends": 3}]
        run = PlanRun(self, judge=judge)
        out = run.include(writer=writer_of({"plan": [item(1)]}))
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["owed"], [MEAN])


class BriefCase(unittest.TestCase):
    """修正案の役の指示に元の works が渡していた節（方針の文書・考えの住処の地図・前の run で通らなかった物ほか）"""

    def prompt(self, run, n=0):
        return writer_prompts(run)[n]

    def test_head_asks_no_narrow_first(self):
        """修正案の役の指示は、narrows を書く前に狭めない案を探し、無い時だけ no_narrow に結果を書けと言う"""
        text = (base.BLOCK / "prompts" / "plan-writer.md").read_text(encoding="utf-8")
        self.assertIn("Look first for a plan that does not narrow", text)
        self.assertIn(gatemarks.NO_NARROW, text)

    def test_plan_head_has_concept_rule(self):
        """判断の 1 軸と考えの住処の観点が修正案の役の指示に載り、事前審査の頼みは載らない"""
        text = (base.BLOCK / "prompts" / "plan-writer.md").read_text(encoding="utf-8")
        self.assertIn("One axis of judgment", text)
        self.assertIn("Use the homes of concepts", text)
        self.assertIn("{shared:concept-map}", text)

    def test_prompt_carries_policy_concept_map_and_prior_failures(self):
        run = PlanRun(self)
        (run.art / "start").mkdir()
        (run.art / "start" / "policy.md").write_text("方針: 試験を先に書く\n", encoding="utf-8")
        out = run.include(policy=pointer_to("start/policy.md"), prior_failures=[{"where": "修正案の受け付け", "text": "単位の網羅が 3 回とも欠けた"}])
        self.assertIs(out["ok"], True)
        prompt = self.prompt(run)
        self.assertIn(POLICY_HEAD, prompt)
        self.assertIn("方針: 試験を先に書く", prompt.split(POLICY_HEAD, 1)[1])
        self.assertIn(PRIOR_FAILURES_HEAD, prompt)
        self.assertIn("- 修正案の受け付け: 単位の網羅が 3 回とも欠けた", prompt)
        self.assertIn(MAP_HEAD, prompt)

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

    def test_prep_passes_state_dir_cache_root(self):
        """修正案の指示のライブラリの文書の節は、STATE_DIR の下 works-factory/ の run をまたぐ控えを読む（網に出ない）"""
        from lib.tests.test_libdocs import FakeBoard, ok_http
        from tests.bin.gitkit import git
        run = PlanRun(self, judge=judgment(unit("app.py の requests の使い方")))
        (run.repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (run.repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        git(run.repo, "add", "app.py", "requirements.txt")
        git(run.repo, "commit", "-q", "-m", "app")
        state = run.tmp / "state"
        libdocs.section(FakeBoard(run.tmp / "earlier").work(""), run.repo, ["app.py"], get=ok_http(), env={},
                        shared=state / "works-factory")
        run.env_extra = {"STATE_DIR": str(state), "WORKS_LIBDOCS_WEB": "", "https_proxy": "http://127.0.0.1:9",
                         "HTTPS_PROXY": "http://127.0.0.1:9"}
        run.include(writer=writer_of({"plan": [item(1, 2, 3)]}))
        self.assertIn("ほかの run 1 本", self.prompt(run))

    def test_without_policy_or_prior_failures_neither_section(self):
        run = PlanRun(self)
        run.include()
        prompt = self.prompt(run)
        self.assertNotIn(POLICY_HEAD, prompt)
        self.assertNotIn(PRIOR_FAILURES_HEAD, prompt)

    def test_dirty_structure_rows_reach_the_prompt(self):
        run = PlanRun(self)
        out = run.include(structure=structure(run, dirty_rows()),
                          writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        self.assertIs(out["ok"], True)
        prompt = self.prompt(run)
        for word in (STRUCT_HEAD, STRUCT_ASK, DIRTY_ROW["chosen"]):
            self.assertIn(word, prompt)
        self.assertNotIn(structmark.MISSING, prompt)

    def test_prompt_carries_structure_rows(self):
        """元 structmark.plan_section の行の形: 判定・形・根拠・避け方（札は英語、判定の語は字のまま）"""
        run = PlanRun(self)
        run.include(structure=structure(run, dirty_rows()),
                    writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        prompt = self.prompt(run)
        self.assertIn(f"- {MEAN}: 汚れる (forms 5・grounds /units/0/id)", prompt)
        self.assertIn(f"Way to avoid: {DIRTY_ROW['chosen']}", prompt)

    def test_failed_structure_marks_the_prompt(self):
        run = PlanRun(self)
        out = run.include(structure=structure(run, status="failed", reason="構造の目の返答が 3 回とも受け付けで拒まれた"))
        self.assertIs(out["ok"], True, out)
        prompt = self.prompt(run)
        self.assertIn(f"{structmark.MISSING}（理由: 構造の目の返答が 3 回とも受け付けで拒まれた", prompt)
        self.assertNotIn(STRUCT_ASK, prompt)
        self.assertEqual(rolekit.rejected(run.art / "r1", "plan"), [], "構造の行への答えを求めない")

    def test_clean_only_structure_rows_need_no_answer(self):
        run = PlanRun(self)
        self.assertIs(run.include(structure=structure(run, clean_rows()))["ok"], True)
        prompt = self.prompt(run)
        self.assertIn(STRUCT_HEAD, prompt)
        self.assertNotIn(STRUCT_ASK, prompt)
        self.assertIn(STRUCT_NONE, prompt)
        self.assertIn(STRUCT_CLEAN_HEAD, prompt)
        self.assertIn(f"- {MEAN}: 汚れない (", prompt.split(STRUCT_CLEAN_HEAD, 1)[1])
        self.assertEqual(rolekit.rejected(run.art / "r1", "plan"), [], "structure を書かない案は通る")

    def test_clean_structure_rows_sit_outside_the_ask(self):
        run = PlanRun(self)
        run.include(structure=structure(run, dirty_rows()),
                    writer=writer_of({"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]}))
        prompt = self.prompt(run)
        self.assertIn(STRUCT_ASK, prompt)
        self.assertNotIn(STRUCT_NONE, prompt)
        head, tail = prompt.split(STRUCT_CLEAN_HEAD, 1)
        asked = head.split(STRUCT_ASK, 1)[1]
        self.assertIn(f"- {MEAN}: 汚れる (", asked)
        self.assertNotIn(": 汚れない (", asked)
        self.assertIn(": 汚れない (", tail)
        self.assertNotIn(": 汚れる (", tail)

    def test_prescriptions_reach_the_prompt(self):
        judge = judgment()
        judge["units"][0]["prescriptions"] = ["分母を len(xs) にする"]
        run = PlanRun(self, judge=judge)
        self.assertIs(run.include()["ok"], True)
        prompt = self.prompt(run)
        self.assertIn(PRESCRIPTION_HEAD, prompt)
        self.assertIn(f"### {MEAN}\n\n1. 分母を len(xs) にする", prompt)
        self.assertNotIn(f"### {CLAMP}", prompt)
        self.assertIn(f"Judgment record: {run.art / 'judge' / 'judgment.json'}", prompt)

    def test_prompt_opens_with_the_role_head(self):
        run = PlanRun(self)
        run.include()
        prompt = self.prompt(run)
        self.assertTrue(prompt.startswith(ROLE_HEAD), prompt[:200])
        for word in ("**Why this step exists**", "How to group items:", "Look for what already exists first:",
                     "Code comments, docstrings, and test descriptions (the target's text)", "Works fields of a plan item:",
                     "The deciding source of each approval item:", "Look first for a plan that does not narrow:",
                     RECORDED_HEAD, "Recorded policy: none", "- Answers a person gave at approval nodes: not given to this role"):
            self.assertIn(word, prompt)
        self.assertNotIn("## Why your previous answer was rejected", prompt, "拒まれていない回に却下の段落は無い")

    def test_units_section_carries_catalog_ledger_and_view(self):
        judge = judgment(unit(NIT, "nit", None))
        judge["questions"] = [{"key": "q-mean", "kind": "fork", "status": "held", "origin": CLAMP, "depends": []}]
        judge["precedents"] = [{"source": "https://example.org/mean", "verdict": "adopt"}]
        run = PlanRun(self, judge=judge)
        self.assertIs(run.include()["ok"], True)
        prompt = self.prompt(run)
        for word in (UNITS_HEAD, "  - paths: stats.py", "  - summary: mean の分母",
                     f"- Units you must not put in (the check rejects them): `{NIT}` (label=nit", "Question ledger (", '"key": "q-mean"',
                     "The judge's view: ", '"framing": "算術平均と上限の枝の取り違え"', "The judge's precedents (world solution): ",
                     "https://example.org/mean",
                     f"- no 1 `{MEAN}`: label=block・disposition=do-now・{brief.DUTY_OWED}",
                     f"- no 2 `{CLAMP}`: label=block・disposition=do-now・{brief.DUTY_MAY}"):
            self.assertIn(word, prompt)

    def test_repo_line_names_base_and_review_md(self):
        """P035: 差分の run（入口の差分の根 diff_base が読む版 review_rev と違う）では、読む版と BASE を別の値で描く"""
        run = PlanRun(self, diff_base=FORK)
        run.include()
        self.assertIn(f"Repository: {run.repo.resolve()} (version read: `{run.base}`)  BASE: `{FORK}`  "
                      f"Viewpoint source: {kit.SHARED / 'prompts' / 'REVIEW.md'}", self.prompt(run))

    def test_excluded_range_named(self):
        run = PlanRun(self)
        run.include()
        self.assertNotIn(EXCLUDED, self.prompt(run))
        run = PlanRun(self)
        run.include(excluded=run.file("judge/pr-excluded.json", {"paths": ["other.py"]}))
        self.assertIn(f"{EXCLUDED}{run.art / 'judge' / 'pr-excluded.json'}", self.prompt(run))

    def test_prompt_carries_lib_docs_section(self):
        run = PlanRun(self)
        run.include()
        prompt = self.prompt(run)
        self.assertIn("## Library documents (installed version and official)", prompt)
        self.assertIn("fetch the official documents yourself with WebSearch and WebFetch", prompt)
        self.assertIn("ライブラリの文書を取る物は無い（0 本）", prompt)

    def test_prompt_ends_with_language_rule(self):
        for lang, want in (("日本語", "日本語"), ("", "the language of the request (the user's language)")):
            with self.subTest(lang=lang):
                run = PlanRun(self, lang=lang)
                run.include()
                lines = [x for x in self.prompt(run).splitlines() if x.strip()]
                self.assertEqual(lines[-1], LAST_LINE)
                self.assertTrue(lines[-2].startswith(LANG_LINE), lines[-2])
                self.assertIn(f") in {want}. Keep keys", lines[-2])

    def test_spec_reaches_the_prompt(self):
        run = PlanRun(self)
        run.include()
        self.assertNotIn(SPEC_HEAD, self.prompt(run))
        run = PlanRun(self)
        run.include(spec=run.file("judge/spec.json", {"requirements": ["空の列の平均は 0"],
                                                      "acceptance": ["test_stats.py::TestStats::test_mean_of_empty"]}))
        prompt = self.prompt(run)
        self.assertIn(SPEC_HEAD, prompt)
        self.assertIn("test_stats.py::TestStats::test_mean_of_empty", prompt.split(SPEC_HEAD, 1)[1])

    def test_routes_spec_puts_the_route_paragraph(self):
        """入力 routes（docs/design/spec-driven.md の 7 章の 2）: spec の時だけ、固めた仕様の「TDD で直す所」が名指す行だけを tdd にする
        段落が出る。既定の auto は今の指示のまま"""
        run = PlanRun(self)
        run.include()
        self.assertNotIn(ROUTES_SPEC_HEAD, self.prompt(run))
        run = PlanRun(self)
        run.include(routes="spec")
        self.assertIn(ROUTES_SPEC_HEAD, self.prompt(run))

    def test_unknown_routes_word_is_an_unread_input(self):
        run = PlanRun(self)
        run.include(routes="tdd")
        prompt = self.prompt(run)
        self.assertNotIn(ROUTES_SPEC_HEAD, prompt)
        self.assertIn("routes:", prompt.split(UNREAD_HEAD, 1)[1])

    def test_units_ripple_reaches_the_prompt(self):
        """元 tests/test_blk_plan.py の test_units_ripple_reaches_plan_prompt"""
        run = PlanRun(self)
        run.include()
        prompt = self.prompt(run)
        self.assertIn(UNITS_RIPPLE_HEAD, prompt)
        self.assertIn(f"### Unit {MEAN}", prompt)
        self.assertIn(f"### Unit {CLAMP}", prompt)
        self.assertTrue((run.art / "r1" / files.RIPPLE_UNITS).is_file())

    def test_unit_without_paths_is_skipped_and_named(self):
        """構造の目が paths の空の単位を見なかった控え（skipped）は、その単位を名指す"""
        run = PlanRun(self, units=[*catalog(), {"id": LOOSE, "paths": [], "summary": "書き方の全体"}], judge=judgment(unit(LOOSE)))
        out = run.include(structure=structure(run, clean_rows(), skipped=[LOOSE]), writer=writer_of({"plan": [item(1, 2, 3)]}))
        self.assertIs(out["ok"], True, out)
        self.assertIn(f"- Units the structure eye did not look at (their paths were empty, so nothing was measured): `{LOOSE}`",
                      self.prompt(run))

    def test_prior_failures_of_wrong_shape_are_named_unread(self):
        run = PlanRun(self)
        self.assertIs(run.include(prior_failures=run.file("start/prior-failures-in.json", {"where": "x"}))["ok"], True)
        prompt = self.prompt(run)
        self.assertIn(UNREAD_HEAD, prompt)
        self.assertIn("- prior_failures: ", prompt.split(UNREAD_HEAD, 1)[1])
        self.assertNotIn(PRIOR_FAILURES_HEAD, prompt)


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
                 "record": converge_record([(None, reply), (review, None)]), "handoffs": [{"round": 1, "handoff": HANDOFF_NOTE}]}
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
