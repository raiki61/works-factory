"""plan の block の受け付け・案の直し・直す義務の試験（docs/design/plan.md の 5 節・9.2）。

今の tests/workflows/test_plan.py の AcceptCase・ReplanCase・ReplanWithoutPlanCase・OwedAnswersCase を、base.PlanRun（block の YAML の
node を Archon と同じ順に回す）に写した物。写し替え: 始めの記録の pointer `start` は port（answers・takes_push・base・review_rev）に、
`plan/r<k>/` は place の `r<k>/` に、材料のファイル `brief-<n>.md` は役に渡った指示の字に、返りの `ready` は `ok`・`status` に、
返りの `depth` は `owed` に、案の直しの元の周（今は周のフォルダを数えて読んだ）は port `prior` に替えた。
指示の md は英語なので、指示の照らしは英語の見出し・札か、値（パス・key）で見る。
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.plan import base
from tests.blocks.plan.base import (CLAMP, DIRTY_ROW, HANDOFF_NOTE, MEAN, NIT, WORLD_ROW, PlanRun, item, judgment, narrow,
                                    unit)

brief = kit.load("plan", "brief")
steps, files = brief.steps, brief.files
import planbrief  # noqa: E402  （lib/。kit.load が sys.path に足す）
import planmarks  # noqa: E402
import replan     # noqa: E402
import rolekit    # noqa: E402

ROLE = files.ROLE
NO_NARROW = "狭めない案として空の列に 0 を返す形を当たったが、呼び手が例外を捕まえている"
UNITS_HEAD = "## Units to fix in this round"
CONCEPT_HEAD = "## Map of where concepts live"
ITEM_HEAD = "## Item to fix {n}"
HANDOFF_ROUNDS = "Notes that earlier rounds of you wrote"
REJECTED_HEAD = (kit.SHARED / "prompts" / "rejected.md").read_text(encoding="utf-8").splitlines()[0]
RESUBMIT_HEAD = (kit.SHARED / "prompts" / "resubmit.md").read_text(encoding="utf-8").splitlines()[0]


class Turns:
    """役の返答を、修正案の役（plan-writer）と出し直しの役（plan-writer-fix）を通した回の順に返す（足りなければ最後の物）。PlanRun の writer と
    fixer の両方に渡す（今の試験の writer_of は役を分けずに回を数えた。PlanRun は node ごとに数えるので、ここで通しの数に戻す）。fn を渡せば
    fn(通しの回, 指示の字) を呼ぶ。prompts に (node の id は分からないので) 渡った指示の字を回の順に残す"""

    def __init__(self, *replies, fn=None):
        self.replies, self.fn, self.prompts = replies, fn, []

    def __call__(self, n, prompt):
        self.prompts.append(prompt)
        k = len(self.prompts)
        if self.fn is not None:
            return self.fn(k, prompt)
        return copy.deepcopy(self.replies[min(k, len(self.replies)) - 1])


def go(run, *replies, fn=None, typed=True, **inputs):
    """block を 1 度回し、(出口の返り, 役に渡った指示の並び) を返す"""
    turns = Turns(*replies, fn=fn)
    out = run.include(writer=turns, fixer=turns, typed=typed, **inputs)
    return out, turns.prompts


def never(case):
    return lambda n, prompt: case.fail("役を起こした")


def reasons(run, k=1):
    return rolekit.rejected(run.round_dir(k), ROLE)


def structure_file(run, rows) -> str:
    """構造の目の控え（structmark.read の形）と、行の JSON Lines を place に置き、port structure に渡す pointer の字を返す"""
    design = run.art / "structure" / "design.jsonl"
    design.parent.mkdir(parents=True, exist_ok=True)
    design.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return run.file("structure/state.json", {"status": "ok", "reason": "", "design_file": str(design), "skipped": []})


def dirty_rows():
    return [{"unit_id": MEAN, **DIRTY_ROW},
            {"unit_id": CLAMP, "verdict": "汚れない", "faces": [], "evidence": ["/units/1/id"], "reason": "足す形が増えない"}]


def prior_of(out, *, handoffs=None) -> str:
    """出口の返り out の周を、次の周の port prior の値に（line が書く前の周のファイルと同じ中身を値で）"""
    rows = handoffs if handoffs is not None else [{"round": out["round"], "handoff": out["handoff"]}]
    return json.dumps({"round": out["round"], "reply": out["reply"], "fields": out["plan"], "fix_plan": out["fix_plan"],
                       "ripple": out["ripple"], "handoffs": rows}, ensure_ascii=False)


class AcceptCase(unittest.TestCase):
    """受け付け（欠けごとに名指して拒む・受け付けの網の回で諦める・通った案の置き方）"""

    def test_accepted_plan_files(self):
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2, narrows=[narrow(no_narrow=NO_NARROW)])]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["status"], "ok")
        fields = run.json(out["plan"])
        self.assertEqual(sorted(fields), ["fields", "round"])
        self.assertEqual(fields["round"], 1)
        self.assertEqual(fields["fields"][0]["unit_keys"], [MEAN, CLAMP], "役が番号で返した単位が id に戻る")
        self.assertEqual(fields["fields"][0]["route"], "tdd")
        side = run.json(out["fix_plan"])
        self.assertEqual(run.pointed(out["fix_plan"]).parent, run.pointed(out["plan"]).parent)
        self.assertEqual(side["plan"][0]["unit_keys"], [MEAN, CLAMP])
        self.assertNotIn("route", side["plan"][0])
        self.assertIn("no_narrow", side["plan"][0]["narrows"][0], "narrows の行に関所の決め手の欄が残る")
        self.assertEqual(run.read("r1/slots.json"), [MEAN, CLAMP])
        self.assertEqual(run.json(out["ripple"])["error"], "")
        self.assertEqual(out["owed"], [MEAN, CLAMP], "今の返りの depth の代わりに、直す義務の単位を判定の順に返す")

    def test_dependent_items_stay_two_items_and_cycle_rejected(self):
        """受け付けで、依存する 2 項目の案は 2 項目のまま受かり（後の項目の depends_on の unit は no で書いても単位の名に戻る）、
        輪の案は依存の輪を名指して拒まれる。自分指し・案に無い単位・前の項目に無い受ける物も拒む"""
        later = item(2, depends_on=[{"unit": 1, "receives": ["stats.py::clamp"]}])
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1), later]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(reasons(run), [])
        side = run.json(out["fix_plan"])
        self.assertEqual([p["unit_keys"] for p in side["plan"]], [[MEAN], [CLAMP]], "2 項目のまま")
        self.assertNotIn(planmarks.DEPENDS_KEY, side["plan"][1], "依存は works の欄として外れ、控えに置く")
        fields = run.json(out["plan"])["fields"]
        self.assertEqual(fields[1][planmarks.DEPENDS_KEY], [{"unit": MEAN, "receives": ["stats.py::clamp"]}], "no が単位の名に戻る")
        loop = [item(1, depends_on=[{"unit": 2, "receives": ["stats.py"]}]), item(2, depends_on=[{"unit": 1, "receives": ["stats.py"]}])]
        why = self.reject_once(PlanRun(self), {"plan": loop})
        self.assertIn(planmarks.DEPENDS_REJECT, why)
        self.assertIn("依存が循環している", why)
        for label, bad, word in (("自分指し", item(2, depends_on=[{"unit": 2, "receives": ["stats.py"]}]), "自分の項目の単位"),
                                 ("案に無い単位", item(2, depends_on=[{"unit": 7, "receives": ["stats.py"]}]), "どの項目の unit_keys にも無い"),
                                 ("前の項目に無い受ける物", item(2, depends_on=[{"unit": 1, "receives": ["other.py::nope"]}]), "files に無い")):
            with self.subTest(label):
                why = self.reject_once(PlanRun(self), {"plan": [item(1), bad]})
                self.assertIn(planmarks.DEPENDS_REJECT, why)
                self.assertIn(word, why)

    def test_ripple_skips_the_runtime_copy(self):
        """作業ツリーの中の工程の写し（ports.RUNTIME_COPY の .archon/）の当たりは、項目ごとの波及にも単位の波及にも数えない"""
        run = PlanRun(self)
        runtime = run.repo / ".archon" / "workflows" / "x" / "y.py"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("from stats import clamp\nclamp(1, 0, 2)\n", encoding="utf-8")
        git(run.repo, "add", "-f", ".archon")
        git(run.repo, "commit", "-qm", "工程の写し")
        out, _ = go(run, {"plan": [item(1, 2)]})
        items = run.json(out["ripple"])["items"]
        self.assertEqual([h["at"] for h in items[0]["uncovered"] if h["at"].startswith(".archon/")], [], items)
        # 単位の波及: 単位の key の `+` の後の名（clamp）を引く判定で周を開き直し、案の前の波及の一覧だけを作る
        plus = run.pointer("judge/plus.json", judgment(unit("stats.py +clamp: 上限の枝")))
        self.assertIs(run.script("intake", {"judgment": plus})["go"], True)
        run.script("ripple_units")
        rows = run.read("r1/ripple-units.json")["units"]
        hits = [at for u in rows for r in u["names"] for at in r["code"] + r["tests"]]
        self.assertTrue(hits, rows)
        self.assertEqual([at for at in hits if str(at).startswith(".archon/")], [], rows)

    def reject_once(self, run, bad):
        out, _ = go(run, bad, {"plan": [item(1, 2)]})
        self.assertIs(out["ok"], True, out)
        return reasons(run)[0]

    def test_missing_unit_rejected(self):
        why = self.reject_once(PlanRun(self), {"plan": [item(1)]})
        self.assertIn("どの案にも入っていない単位", why)
        self.assertIn(CLAMP[:40], why)

    def test_unknown_number_names_allowed_numbers(self):
        why = self.reject_once(PlanRun(self), {"plan": [item(1, 2, 7)]})
        self.assertIn("今の周に直す単位に無い key ['7']", why)
        self.assertIn("案に入れてよい no は [1, 2]", why)

    def test_unit_without_duty_rejected_by_label(self):
        run = PlanRun(self, judge=judgment(unit(NIT, "nit", None)))
        why = self.reject_once(run, {"plan": [item(1, 2, NIT)]})
        self.assertIn("label=nit", why)

    def test_works_field_gaps_rejected(self):
        """型は役の node の output_format が照らす。型に合っても欠けた・誤った works の欄（tdd なのに受け入れテストが無い・direct の訳が無い・
        根の外の範囲）を受け付けが名指す"""
        run = PlanRun(self)
        bad = {"plan": [item(1, tests=[]), item(2, route="direct", allowed_paths=["../outside.py"])]}
        out, _ = go(run, bad, {"plan": [item(1, 2)]})
        self.assertIs(out["ok"], True)
        why = reasons(run)[0]
        self.assertIn(planmarks.REJECT, why)
        for word in ("plan[0].tests: route が tdd", "plan[1].route_why", "plan[1].allowed_paths[0]"):
            self.assertIn(word, why)

    def test_dirty_structure_row_needs_answer(self):
        """構造の目が汚れると見た行（port structure の控え）の単位を持つ項目は、行に従うか訳を書く。答えの無い案を拒む"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2)]}, {"plan": [item(1, 2, structure=[{"row": MEAN, "follows": True}])]},
                    structure=structure_file(run, dirty_rows()))
        self.assertIs(out["ok"], True, out)
        self.assertIn(f"設計の行 {MEAN} に従うか", reasons(run)[0])

    def test_world_row_needs_answer(self):
        run = PlanRun(self, world=[WORLD_ROW])
        out, prompts = go(run, {"plan": [item(1, 2)]}, {"plan": [item(1, 2, structure=[{"world": "mean-denominator", "follows": True}])]})
        self.assertIs(out["ok"], True, out)
        self.assertIn("世界の解の行 mean-denominator にどの項目も答えていない", reasons(run)[0])
        self.assertIn("## Rows of the world solution", prompts[0])
        self.assertIn("Class mean-denominator", prompts[0])

    def test_narrow_without_no_narrow_rejected(self):
        run = PlanRun(self)
        # Archon の型（JSON Schema の minLength）は空白も数えるので、空白で埋めた短い答えは型を通って受け付けに届く。
        # 試験の型の照らし（engine.schema）は空白を除いて数えるので、ここでは外す
        short = " " * 18 + "無い"
        out, _ = go(run, {"plan": [item(1, 2, narrows=[narrow(no_narrow=short)])]}, {"plan": [item(1, 2)]}, typed=False)
        self.assertIs(out["ok"], True)
        self.assertIn("narrows の行に狭めない案を探した結果", reasons(run)[0])
        self.assertEqual((run.status["plan-writer"], run.status["plan-writer-fix"]), ("skipped", "ok"))

    def test_resubmit_prompt_carries_the_last_reject_and_the_merged_answer(self):
        """#571: 拒まれた後の回は出し直しの役の短い指示: 今の周の最後の拒否の文を字のまま貼り、受け付けが合わせた前の答えの控えを名指す
        （材料は会話に在るので貼らない）。前の回の拒否は会話に在るので最後の 1 件だけ"""
        run = PlanRun(self)
        out, prompts = go(run, {"plan": [item(1)]}, {"plan": [item(1, 2), item(2)]}, {"plan": [item(1, 2)]})
        self.assertIs(out["ok"], True)
        first, second = reasons(run)
        self.assertEqual([r["reason"] for r in out["rejects"]], [first, second], "#681: 周の拒否の行は欄 rejects で返す")
        rnd = run.round_dir(1)
        self.assertEqual([nid for nid, _ in run.prompts], ["plan-writer", "plan-writer-fix", "plan-writer-fix"])
        self.assertTrue(prompts[2].startswith(RESUBMIT_HEAD), prompts[2][:200])
        self.assertIn(second, prompts[2])
        self.assertNotIn(first, prompts[2])
        self.assertIn(str(rolekit.candidate_path(rnd, ROLE)), prompts[2])
        self.assertNotIn(UNITS_HEAD, prompts[2])
        self.assertFalse(rolekit.rejects_text_path(rnd, ROLE).exists(), "拒否の全部は指示に貼り、ファイルに書かない")

    def test_resume_prompt_names_every_reject_of_the_round(self):
        """resume で輪が 1 周目から回り直すと、前の回の値（prev）が空で、1 回目の役が新しい会話で全部の材料から起きる。その指示の頭に、
        この周の拒否の全部が古い順に貼られる（#345。{shared:rejected}）"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1)]})
        self.assertIs(out["ok"], False)
        got = run.script("plan_prep", {"prev": ""})
        self.assertIs(got["resubmit"], False)
        self.assertTrue(got["prompt"].startswith(REJECTED_HEAD), got["prompt"][:200])
        self.assertIn(rolekit.rejects_text(reasons(run)), got["prompt"])
        self.assertIn(UNITS_HEAD, got["prompt"])

    def test_partial_resubmit_is_merged_into_the_one_shot_shape(self):
        """#571: 出し直しの役は拒まれた項目だけを返し、受け付けが前の答えの控えと合わせてから照らす。合わせた答え（reply.json・
        p2.fix_plan.json）は 1 回で書いた答えと同じ形"""
        once = PlanRun(self)
        whole = {"plan": [item(1), item(2)]}
        self.assertIs(go(once, whole)[0]["ok"], True)
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1), item(2, tests=[])]}, {"plan": [item(2)]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(len(reasons(run)), 1)
        for name in (files.REPLY, files.FIX_PLAN):
            with self.subTest(name):
                self.assertEqual(run.read(f"r1/{name}"), once.read(f"r1/{name}"))
        slot_list = run.read(f"r1/{files.SLOTS}")
        self.assertEqual(json.loads(rolekit.candidate_path(run.round_dir(1), ROLE).read_text(encoding="utf-8")),
                         steps.named(whole, slot_list), "控えは受け付けと同じく単位の名に戻した形")

    def test_empty_resubmit_rechecks_the_previous_answer(self):
        """空の出し直しは前の答えのまま全体を照らし直す（直っていなければ同じ理由で拒む）"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1)]}, {}, {"plan": [item(1, 2)]})
        self.assertIs(out["ok"], True, out)
        first, again = reasons(run)
        self.assertEqual(again, first)

    def test_missing_plan_is_refused_then_resubmitted_alone(self):
        """#832: 修正案の役の型は根の欄 plan を要ると書かない（出し直しの役と同じ形）。plan の欠けた答えは受け付けが拒み、出し直しの
        plan で通る"""
        run = PlanRun(self)
        out, _ = go(run, {}, {"plan": [item(1), item(2)]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(reasons(run), [rolekit.MISSING_FIELDS.format(keys="plan")])

    def test_whole_plan_in_the_first_reply_is_refused(self):
        """#832: whole_plan は出し直しの役だけが書く欄（型は 1 回目の役と同じなので型は拒まない）。1 回目の答えに在れば受け付けが拒み、
        控えには残さない"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1), item(2)], steps.WHOLE_PLAN: False}, {})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(reasons(run), [rolekit.FIX_ONLY_FIELDS.format(keys=steps.WHOLE_PLAN)])
        self.assertNotIn(steps.WHOLE_PLAN, json.loads(rolekit.candidate_path(run.round_dir(1), ROLE).read_text(encoding="utf-8")))

    def test_whole_plan_resubmit_drops_items(self):
        """項目を消す出し直しは whole_plan: true と案の全部（plan が丸ごと置き換わる。whole_plan は控えに残り、受けた案には残らない）"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2), item(2)]}, {"whole_plan": True, "plan": [item(1, 2)]})
        self.assertIs(out["ok"], True, out)
        slot_list = run.read(f"r1/{files.SLOTS}")
        self.assertEqual(json.loads(rolekit.candidate_path(run.round_dir(1), ROLE).read_text(encoding="utf-8")),
                         {**steps.named({"plan": [item(1, 2)]}, slot_list), steps.WHOLE_PLAN: True})
        self.assertNotIn(steps.WHOLE_PLAN, run.read(f"r1/{files.REPLY}"))

    def test_unit_in_two_items_rejected(self):
        why = self.reject_once(PlanRun(self), {"plan": [item(1, 2), item(2)]})
        self.assertIn("2 つの案に入った単位", why)
        self.assertIn(CLAMP[:40], why)

    def test_string_number_is_a_name_and_asks_for_no(self):
        """字の "1" は番号に戻さず、知らない名として拒む"""
        why = self.reject_once(PlanRun(self), {"plan": [item("1", "2")]})
        self.assertIn("今の周に直す単位に無い key ['1', '2']", why)
        self.assertIn("no で指せ", why)
        self.assertNotIn("key を字面のまま写せ", why)

    def test_info_defer_question_rejected_by_label(self):
        info, defer, question = "stats.py: 補足の情報", "stats.py clamp: 引数の順が読みにくい", "stats.py: 空の列をどう扱うか"
        run = PlanRun(self, judge=judgment(unit(info, "info", None), unit(defer, "suggest", "defer"), unit(question, "question", None)))
        why = self.reject_once(run, {"plan": [item(1, 2, info, defer, question)]})
        self.assertIn(steps.NOT_OWED_REJECT, why)
        for word in ("label=info", "label=suggest（disposition=defer）", "label=question"):
            self.assertIn(word, why)
        self.assertIn("案に入れてよい no（必ず入れる物を含む）は [1, 2]", why)

    def test_every_reason_in_one_rejection(self):
        """網羅と works の欄の欠けを 1 回の拒否に並べる"""
        why = self.reject_once(PlanRun(self), {"plan": [item(1, tests=[])]})
        self.assertIn(steps.COVERS_REJECT, why)
        self.assertIn(planmarks.REJECT, why)

    def test_malformed_recommend_rejected(self):
        run = PlanRun(self)
        bad = narrow(no_narrow=NO_NARROW, recommend={"answer": "たぶん通す", "note": "空の列は残す", "why": "呼び手が捕まえる"})
        out, _ = go(run, {"plan": [item(1, 2, narrows=[bad])]}, {"plan": [item(1, 2)]}, typed=False)
        self.assertIs(out["ok"], True)
        why = reasons(run)[0]
        self.assertIn(steps.RECOMMEND_REJECT, why)
        self.assertIn("plan[0].narrows[0]", why)

    def test_rewrite_limit_resolved(self):
        rewrite = {"id": "test_stats.py::TestStats::test_clamp_above_range", "behavior": "上限を超えた値に上限を返す",
                   "old": "lo を返す", "new": "上限を超えたら hi を返す"}
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2, rewrite_tests=[rewrite])]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual(run.json(out["plan"])["fields"][0]["rewrite_tests"][0]["limit"], "test_stats.py:14")

    def test_fields_are_frozen_in_the_round_trace(self):
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2)]})
        raw = run.pointed(out["plan"]).read_bytes()
        trace = [json.loads(x) for x in (run.round_dir(1) / files.TRACE).read_text(encoding="utf-8").splitlines()]
        saved = [r for r in trace if r["op"] == planmarks.SAVED_OP]
        self.assertEqual([(r["round"], r["sha256"]) for r in saved], [(1, hashlib.sha256(raw).hexdigest())])

    def test_role_that_moved_the_tree_is_refused(self):
        """役を起こす前の作業ツリーの姿と比べ、書き換え・commit を拒んで出し直させる（次の回の支度が姿を取り直す）"""
        def edit(repo):
            (repo / "stats.py").write_text((repo / "stats.py").read_text(encoding="utf-8") + "\n# 役が書いた\n", encoding="utf-8")

        def commit(repo):
            edit(repo)
            git(repo, "commit", "-qam", "役が commit した")

        for name, move in (("書き換え", edit), ("commit", commit)):
            with self.subTest(name):
                run = PlanRun(self)

                def writer(n, prompt, run=run, move=move):
                    if n == 1:
                        move(run.repo)
                    return {"plan": [item(1, 2)]}

                out, _ = go(run, fn=writer)
                self.assertIs(out["ok"], True, out)
                why = reasons(run)
                self.assertEqual(len(why), 1, why)
                self.assertTrue(why[0].startswith(steps.READONLY_MOVED), why[0])
                self.assertTrue((run.round_dir(1) / files.TREE).is_file())

    def test_status_guarded_leaves_index_only_change_to_the_status_check(self):
        """修正案の役は mutates_checkout: false なので、受け付けは Archon の状態の照らし（git status の行の違い）が見る index だけの変化では
        拒まない（accept.status_keys("true")）。行の字が同じままの、既に変わっていたファイルの書き換えは拒む"""
        def stage(repo):
            git(repo, "add", "stats.py")

        def rewrite(repo):
            with open(repo / "stats.py", "a", encoding="utf-8") as f:
                f.write("# 役が書いた\n")

        for name, move, refused in (("index だけ", stage, False), ("書き換え", rewrite, True)):
            with self.subTest(name):
                run = PlanRun(self)
                with open(run.repo / "stats.py", "a", encoding="utf-8") as f:
                    f.write("# 前から在った変更\n")

                def writer(n, prompt, run=run, move=move):
                    if n == 1:
                        move(run.repo)
                    return {"plan": [item(1, 2)]}

                out, _ = go(run, fn=writer)
                self.assertIs(out["ok"], True, out)
                why = reasons(run)
                self.assertEqual(len(why), 1 if refused else 0, why)
                if refused:
                    self.assertIn("中身が変わった", why[0])

    def test_unsavable_plan_halts_without_counting_a_rejection(self):
        """P025: 受けた案の控えを置けない周は、役の拒否に数えず（出し直させず）に輪を止める（受け付けの halt の道）"""
        run = PlanRun(self)

        def writer(n, prompt):
            (run.round_dir(1) / (planmarks.FIELDS_FILE + ".tmp")).mkdir(exist_ok=True)
            return {"plan": [item(1, 2)]}

        out, prompts = go(run, fn=writer)
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up")},
                         {"ok": False, "done": True, "give_up": True})
        self.assertIn(planmarks.FIELDS_FILE, run.out["plan-accept"]["reason"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(reasons(run), [])
        self.assertIs(out["ok"], False)
        # 試験の邪魔（一時のファイルの名のディレクトリ）が残る間は、出口も plan-fields.json を置けずに落ちない道（failed）を返す。
        # 邪魔を除いた出口は、止めた周を機械の故障（failed。役の諦め gave_up ではない）と読み、置けなかった控えの名を訳に返す
        (run.round_dir(1) / (planmarks.FIELDS_FILE + ".tmp")).rmdir()
        again = run.script("finish")
        self.assertEqual((again["ok"], again["status"]), (False, "failed"))
        self.assertIn(planmarks.FIELDS_FILE, again["reason"])
        self.assertEqual(run.json(again["plan"]), {"round": 1, "fields": []})

    def test_unsavable_handoff_halts_without_counting_a_rejection(self):
        """引き継ぎのメモの控えを置けない周（置く時の一時のファイルの名がディレクトリ）も、役の拒否に数えず（出し直させず）に輪を止める。
        先に置いた案の控えは消え、置けなかった控えの名が round.json の why に残る"""
        run = PlanRun(self)

        def writer(n, prompt):
            (run.round_dir(1) / "handoff.json.tmp").mkdir(exist_ok=True)
            return {"plan": [item(1, 2)], "handoff": HANDOFF_NOTE}

        out, prompts = go(run, fn=writer)
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up")},
                         {"ok": False, "done": True, "give_up": True})
        self.assertIn("handoff.json", run.out["plan-accept"]["reason"])
        self.assertEqual(len(prompts), 1)
        self.assertEqual(reasons(run), [])
        self.assertEqual((out["ok"], out["status"]), (False, "failed"))
        self.assertIn("handoff.json", out["reason"])
        rnd = run.round_dir(1)
        for name in (files.FIX_PLAN, files.REPLY, files.HANDOFF):
            self.assertFalse((rnd / name).exists(), name)
        self.assertIsNone(out["fix_plan"])
        self.assertEqual(run.json(out["plan"]), {"round": 1, "fields": []},
                         "置いた欄の控えは消え、返りの pointer のための空の控えだけが残る")
        self.assertIn("handoff.json", run.read(f"r1/{files.ROUND}")["why"])

    def test_unusable_ledger_is_a_done_give_up_reject(self):
        """拒否の控えが読めない周（控えの名がディレクトリ）でも、受け付けの script は非 0 で落ちず、done・give_up 真の拒否で輪を止める。
        回を先に読むので、返答を照らさず案のファイルも書かない"""
        run = PlanRun(self)

        def writer(n, prompt):
            (run.round_dir(1) / files.REJECTS).mkdir(exist_ok=True)
            return {"plan": [item(1, 2)]}

        out, _ = go(run, fn=writer)
        got = run.out["plan-accept"]
        self.assertEqual({k: got[k] for k in ("ok", "done", "give_up")}, {"ok": False, "done": True, "give_up": True})
        self.assertIn("拒否の控えが扱えない", got["reason"])
        self.assertFalse((run.round_dir(1) / files.FIX_PLAN).exists())
        self.assertEqual(out["status"], "failed")
        self.assertIn("拒否の控えが扱えない", out["reason"])

    def test_accepted_plan_has_item_ripple(self):
        """種の 1 回目の受け付けの後の ripple.json: 項目ごとに、変える名の呼び出し元と試験の覆っていない当たり"""
        run = PlanRun(self)
        out, _ = go(run, {"plan": [item(1, 2)]})
        doc = run.json(out["ripple"])
        self.assertEqual(doc["error"], "")
        self.assertEqual(doc["items"][0]["unit_keys"], [MEAN, CLAMP])
        self.assertIn("request_ok.json:8", [h["at"] for h in doc["items"][0]["uncovered"]])

    def test_net_rejections_give_up_with_every_pointer(self):
        """拒否の回数では諦めず、受け付けの網 rolekit.NET_AFTER 回目の拒否で done・give_up（工場の不具合として NET_WHY を添える）。
        until_bash で輪を抜け、出口は status gave_up と、在って空でない plan・ripple の pointer を返す"""
        run = PlanRun(self)
        out, prompts = go(run, {"plan": [item(1)]})
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up", "attempt")},
                         {"ok": False, "done": True, "give_up": True, "attempt": rolekit.NET_AFTER})
        self.assertEqual(len(prompts), rolekit.NET_AFTER)
        self.assertEqual((out["ok"], out["status"]), (False, "gave_up"))
        self.assertEqual(run.json(out["plan"]), {"round": 1, "fields": []})
        self.assertEqual(run.json(out["ripple"])["items"], [])
        error = run.json(out["ripple"])["error"]
        self.assertIn(f"{rolekit.NET_AFTER} 回とも受け付けで拒まれた", error)
        self.assertIn(rolekit.NET_WHY.format(n=rolekit.NET_AFTER), error)
        self.assertEqual(out["reason"], error)
        self.assertEqual(len(out["rejects"]), rolekit.NET_AFTER)
        self.assertIsNone(out["gave_up"], "項目ごとの諦めの行は形 replan だけ")


CONFLICTS = {"items": [
    {"id": "c1", "unit_key": CLAMP, "kind": "scope", "between": ["stats.py", "test_stats.py"],
     "why_both_cannot_hold": "試験を直さないと上限の枝を直した証が立たない", "which_is_right": "plan",
     "ruling": {"decision": "fix_plan_item", "text": "項目 1 の allowed_paths に request_ok.json を足せ", "limits": [], "plan_items": [1]}},
    {"id": "c2", "unit_key": MEAN, "kind": "scope", "between": ["stats.py"],
     "why_both_cannot_hold": "人が決める", "which_is_right": "human",
     "ruling": {"decision": "ask_human", "text": "人に聞く裁定の文", "limits": []}}]}
RULING_TEXT = CONFLICTS["items"][0]["ruling"]["text"]


class ReplanCase(unittest.TestCase):
    """案の直し（ruling と conflicts と、直す元の承認済みの案の周を port prior で受ける 2 度目の include）"""

    def setUp(self):
        self.run_ = PlanRun(self)
        first, _ = go(self.run_, {"plan": [item(1, 2)]})
        self.assertIs(first["ok"], True, first)
        self.first = first
        self.conflicts = self.run_.file("fix/conflicts.json", CONFLICTS)

    def fixed(self, **more):
        return item(MEAN, CLAMP, allowed_paths=["stats.py", "test_stats.py", "request_ok.json"], **more)

    def replan(self, *replies, run=None, first=None, conflicts=None, ruling='["1"]', fn=None):
        run = run or self.run_
        return go(run, *replies, fn=fn, ruling=ruling, conflicts=conflicts or self.conflicts, prior=prior_of(first or self.first))

    def test_replan_rejects_extra_items_and_changed_keys_then_amends(self):
        run = self.run_
        out, prompts = self.replan({"plan": [self.fixed(), self.fixed()]}, {"whole_plan": True, "plan": [item(1, 2)]},
                                   {"whole_plan": True, "plan": [self.fixed()]})
        self.assertIs(out["ok"], True, out)
        self.assertEqual((out["round"], out["mode"], run.out["intake"]["mode"]), (2, "replan", "replan"))
        self.assertEqual(run.status["ripple-units"], "skipped")
        rnd = run.round_dir(2)
        why = reasons(run, 2)
        self.assertIn("plan[] は 1 項目", why[0])
        self.assertIn("一字も変えずに写す", why[1])
        self.assertIn(RULING_TEXT, prompts[0])
        self.assertIn(ITEM_HEAD.format(n=1), prompts[0])
        for phrase in ("the brief wins", "could not be looked up", "did not decide a scope"):
            self.assertIn(phrase, prompts[0], "直し直す回の指示に brief の読み方の句が無い")
        self.assertNotIn("人に聞く裁定の文", prompts[0], "fix_plan_item でない裁定の行は渡さない")
        self.assertIn(CONCEPT_HEAD, prompts[0])
        trace = [json.loads(x) for x in (rnd / files.TRACE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["items"] for r in trace if r["op"] == planmarks.AMEND_OP], [[1]])
        fields = run.json(out["plan"])
        self.assertEqual(fields["round"], 2)
        self.assertEqual(sorted(fields["amended"]["1"]), sorted(["unit_keys", "approach", "files", "shrink_first", "narrows"]))
        self.assertEqual(fields["fields"][0]["allowed_paths"], ["stats.py", "test_stats.py", "request_ok.json"])
        trip = run.json(out["replan"])
        self.assertEqual(run.pointed(out["replan"]), rnd / replan.TRIP_FILE)
        row = trip["items"][0]
        self.assertEqual((row["item"], row["contract_changed"]), (1, ["allowed_paths"]))
        self.assertEqual(row["widened"], {"allowed_paths": ["request_ok.json"], "out_of_scope": []})
        before = [h["at"] for h in run.json(self.first["ripple"])["items"][0]["uncovered"]]
        after = [h["at"] for h in run.json(out["ripple"])["items"][0]["uncovered"]]
        self.assertIn("request_ok.json:8", before, "1 回目の案は request_ok.json の当たりを覆っていない")
        self.assertNotIn("request_ok.json:8", after, "波及の一覧が直した項目で作り直される")
        self.assertEqual(out["owed"], [], "形 replan は直す義務の単位を返さない")

    def test_net_rejections_give_up_without_amending(self):
        """案の直しの役も受け付けの網の回まで拒まれ続けたら諦めて ok: false。承認済みの案（前の周の控え）は書き換えない"""
        run = self.run_
        before = (run.round_dir(1) / files.FIELDS).read_bytes()
        out, _ = self.replan({"plan": [item(1, 2)]})
        self.assertEqual({k: run.out["plan-accept"][k] for k in ("ok", "done", "give_up", "attempt")},
                         {"ok": False, "done": True, "give_up": True, "attempt": rolekit.NET_AFTER})
        self.assertEqual((out["ok"], out["status"]), (False, "gave_up"))
        self.assertEqual((run.round_dir(1) / files.FIELDS).read_bytes(), before)
        self.assertEqual(run.json(out["plan"]), {"round": 2, "fields": []})
        error = run.json(out["ripple"])["error"]
        self.assertIn(f"{rolekit.NET_AFTER} 回とも受け付けで拒まれた", error)
        self.assertIn(steps.REPLAN_REJECT, error)
        rows = json.loads((run.pointed(out["plan"]).parent / files.REPLAN_GAVE_UP).read_text(encoding="utf-8"))
        self.assertEqual([(r["item"], r["ruling"]) for r in rows], [(1, RULING_TEXT)])
        self.assertTrue(rows[0]["why"].startswith(steps.PLAN_GAVE_UP_WHY.split("{")[0]), rows[0]["why"])
        self.assertEqual(out["gave_up"], rows, "諦めの行は欄 gave_up でも返す（報告は置き場の控えを開かない）")
        self.assertEqual(len(out["rejects"]), rolekit.NET_AFTER)
        self.assertIsNone(out["fix_plan"], "受け付けを通った返答が無い周の欄 fix_plan は null")
        self.assertIsNone(out["replan"])

    def test_replan_writer_that_moved_the_tree_is_refused(self):
        """案の直しの役が作業ツリーを書き換えれば、直した項目を照らす前に拒み、直した案を置かない"""
        run = self.run_

        def writer(n, prompt):
            stats = run.repo / "stats.py"
            stats.write_text(stats.read_text(encoding="utf-8") + f"\n# 役が書いた {n}\n", encoding="utf-8")
            return {"plan": [self.fixed()]}

        out, _ = self.replan(fn=writer)
        self.assertIs(out["ok"], False)
        rnd = run.round_dir(2)
        why = reasons(run, 2)
        self.assertEqual(len(why), rolekit.NET_AFTER, why)
        for w in why:
            self.assertTrue(w.startswith(steps.READONLY_MOVED), w)
        for name in (files.REPLY, replan.TRIP_FILE):
            self.assertFalse((rnd / name).exists(), name)

    def test_brief_of_the_item_is_named(self):
        """案の直しの指示が、承認済みの項目と判定から組んだ項目の brief（item-brief-<no>.md）を名指す"""
        run = self.run_
        out, prompts = self.replan({"plan": [self.fixed()]})
        self.assertIs(out["ok"], True, out)
        item_brief = run.round_dir(2) / files.ITEM_BRIEF.format(no=1)
        self.assertIn(f"- Brief of this item: {item_brief}", prompts[0])
        text = item_brief.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(planbrief.TITLE.format(n=1)), text[:200])
        self.assertIn(f"### {MEAN}", text)
        self.assertIn("mean の分母を len(xs) に", text)

    def test_replan_reads_the_same_structure_after_the_tree_moved(self):
        """案の直しは構造を測り直さず、1 回目と同じ port structure（構造の目の控え）を受けて項目の brief と受け付けに使う。作業ツリーが
        動いた（修正が commit した）後でも同じ控えを読む"""
        run = PlanRun(self)
        structure = structure_file(run, dirty_rows())
        answer = [{"row": MEAN, "follows": True}]
        first, _ = go(run, {"plan": [item(1, 2, structure=answer)]}, structure=structure)
        self.assertIs(first["ok"], True, first)
        (run.repo / "stats.py").write_text((run.repo / "stats.py").read_text(encoding="utf-8") + "\n# 直した\n", encoding="utf-8")
        git(run.repo, "commit", "-qam", "修正")
        conflicts = run.file("fix/conflicts.json", CONFLICTS)
        out, _ = self.replan({"plan": [self.fixed()]}, {"plan": [self.fixed(structure=answer)]}, run=run, first=first,
                             conflicts=conflicts)
        self.assertIs(out["ok"], True, out)
        self.assertIn(f"設計の行 {MEAN} に従うか", reasons(run, 2)[0], "受け付けが同じ構造の目の行への答えを求める")
        self.assertIn(DIRTY_ROW["reason"], (run.round_dir(2) / files.ITEM_BRIEF.format(no=1)).read_text(encoding="utf-8"))
        self.assertEqual(set(run.status) - {n["id"] for n in base.nodes(run.doc)}, set(), "block は構造を測る node を持たない")

    def test_replan_prompt_names_the_handoff_of_the_plan_it_revises(self):
        """メモつきで受かった案を直す時、案の直しの指示は直す元の周のメモのパスを名指し、案の直しの役の返すメモは案の直しの周に置かれる"""
        run = PlanRun(self)
        first, _ = go(run, {"plan": [item(1, 2)], "handoff": HANDOFF_NOTE})
        self.assertIs(first["ok"], True)
        conflicts = run.file("fix/conflicts.json", {"items": CONFLICTS["items"][:1]})
        again = {**HANDOFF_NOTE, "kept": ["項目 1 の allowed_paths に request_ok.json を足した"]}
        out, prompts = self.replan({"plan": [self.fixed()], "handoff": again}, run=run, first=first, conflicts=conflicts)
        self.assertIs(out["ok"], True, out)
        r1, r2 = run.round_dir(1), run.round_dir(2)
        self.assertIn(HANDOFF_ROUNDS, prompts[0])
        self.assertIn(f"- r1: {r1 / files.HANDOFF}", prompts[0])
        self.assertEqual(run.json(out["handoff"]), again)
        self.assertEqual(run.pointed(out["handoff"]), r2 / files.HANDOFF)
        self.assertEqual(json.loads((r1 / files.HANDOFF).read_text(encoding="utf-8")), HANDOFF_NOTE, "直す元の周のメモは変えない")

    def test_ruling_outside_the_plan_skips_the_role(self):
        run = self.run_
        out = run.include(ruling='["5"]', conflicts=self.conflicts, prior=prior_of(self.first), writer=never(self))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertEqual((out["ok"], out["status"]), (False, "held"))
        self.assertIn("ruling の項目 '5' が承認済みの修正案（1 項目）の番号でない", run.json(out["ripple"])["error"])


class ReplanWithoutPlanCase(unittest.TestCase):
    def test_replan_without_an_accepted_plan_skips_the_role(self):
        run = PlanRun(self)
        out = run.include(ruling='["1"]', writer=never(self))
        self.assertEqual(run.status["plan-loop"], "skipped")
        self.assertEqual((out["ok"], out["status"], out["mode"]), (False, "held", "replan"))
        self.assertIn("直す元の承認済みの修正案が無い", run.json(out["ripple"])["error"])


class OwedAnswersCase(unittest.TestCase):
    """依頼の answers（port answers）が答えた関所の問いの出どころ・depends は、plan の直す義務に戻る（P002。fix と同じ gatemarks.duty
    の口で数える。plan に関所の答えは届かない——行き止まりの判定は 1 回目の周で、修正前の関所より前に走る）。無人の run の推しは port takes_push"""

    FORK = {"key": "q-mean", "kind": "fork", "status": "held", "origin": MEAN, "options": ["a", "b"], "reason": "割れる"}
    PUSHED = "割れる。推し: a——呼び手が a を前提にしている"

    def duty_line(self, prompt) -> str:
        return next(line for line in prompt.splitlines() if line.startswith("- no ") and f"`{MEAN}`" in line)

    def test_answered_fork_origin_returns_to_duty(self):
        """P002: 答えの無い fork の出どころは「入れてもよい」、依頼の answers がその fork に答えれば「必ず案に入れる」（外せば網羅の拒否）"""
        for answers, duty in (([], brief.DUTY_MAY), ([{"question": "q-mean", "text": "a を選ぶ"}], brief.DUTY_OWED)):
            with self.subTest(answers=answers):
                run = PlanRun(self, judge={**judgment(), "questions": [self.FORK]}, answers=answers)
                out, prompts = go(run, {"plan": [item(1, 2)]})
                self.assertIs(out["ok"], True)
                self.assertIn(duty, self.duty_line(prompts[0]))

    def test_answered_origin_that_is_not_open_is_stuck(self):
        """P010: 依頼の答えで直す義務に戻った出どころが開いていない（defer）なら行き止まり。役を起こさず、理由 PLAN_STUCK に no と key"""
        judge = {"units": [unit(MEAN), unit(CLAMP, "suggest", "defer")], "questions": [{**self.FORK, "origin": CLAMP}]}
        run = PlanRun(self, judge=judge, answers=[{"question": "q-mean", "text": "a を選ぶ"}])
        out = run.include(writer=never(self))
        self.assertEqual((out["ok"], out["status"]), (False, "held"))
        error = run.json(out["ripple"])["error"]
        self.assertIn(steps.PLAN_STUCK, error)
        self.assertIn(CLAMP, error)

    def test_unattended_push_owes_the_sole_unit(self):
        """#593: 唯一の単位の出どころが推しつきの保留の問いの時、推しを答えに採る run（takes_push）は役を起こす。推しの無い問いと
        推しを採らない run は今どおり義務 0 件で止まる（status nothing_owed）"""
        pushed = {**self.FORK, "reason": self.PUSHED}
        run = PlanRun(self, judge={"units": [unit(MEAN)], "questions": [pushed]}, takes_push="true")
        out, prompts = go(run, {"plan": [item(1)]})
        self.assertIs(out["ok"], True)
        self.assertIn(brief.DUTY_OWED, self.duty_line(prompts[0]))
        for takes_push, question in (("true", self.FORK), ("false", pushed)):
            with self.subTest(takes_push=takes_push, question=question):
                run = PlanRun(self, judge={"units": [unit(MEAN)], "questions": [question]}, takes_push=takes_push)
                out = run.include(writer=never(self))
                self.assertEqual(run.status["plan-loop"], "skipped")
                self.assertEqual((out["ok"], out["status"]), (False, "nothing_owed"))
                self.assertIn(steps.NOTHING_OWED, run.json(out["ripple"])["error"])

    def test_unattended_push_on_a_deferred_origin_stays_held(self):
        """#593: 推しつきの保留の問いの出どころが開いていない（defer）なら、推しを採る run も推しを採らずに保留のまま残し、行き止まらずに
        ほかの開いた単位で役を起こす"""
        pushed = {**self.FORK, "origin": CLAMP, "reason": self.PUSHED}
        judge = {"units": [unit(MEAN), unit(CLAMP, "suggest", "defer")], "questions": [pushed]}
        run = PlanRun(self, judge=judge, takes_push="true")
        out, prompts = go(run, {"plan": [item(1)]})
        self.assertIs(out["ok"], True)
        self.assertIn(brief.DUTY_OWED, self.duty_line(prompts[0]))


if __name__ == "__main__":
    unittest.main()
