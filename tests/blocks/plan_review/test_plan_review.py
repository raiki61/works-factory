"""事前審査の block の筋（docs/design/plan-review.md の 15.3 の test_plan_review.py）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（tests/e2e/target-seed を commit した物）で、port の値だけを渡し、
script を子のプロセスで回す。入口の形の決め（pointer・JSON の値・在るファイル・方針の文、読めない pointer は failed）・入口の
写しと intake.json の欄・出口が落ちない事・YAML の照らし（輪の数・役の型・層の鎖・印）と、intake → review_prep → 台本の返答 →
review_accept → finish の 1 往復・2 往復目・出し直し・形 replan・形 text の筋を見る。筋書きを Archon の workflow test で回すのは
tests/layers/test_block_shape.py。
"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

import yaml

from tests.bin import hermetic, trimmed
from tests.blocks import kit
from tests.blocks.plan_review import values as v

BLOCK = kit.BLOCKS / "plan-review"
YAML = BLOCK / "works-factory-plan-review.yaml"
PORTS = ["proposal", "plan", "proposal_file", "fields", "judgment", "purpose", "design", "design_why", "world_rows", "means", "structure", "ripple", "prior",
         "tree", "excluded", "policy", "recorded", "request", "review_rev", "diff_base", "ruling", "conflicts", "lang", "theme_doc"]
RETURNS = ["ok", "status", "form", "round", "reason", "holes", "blocks", "pass", "asks", "deviations", "replan", "gave_up", "reads",
           "report"]
RECORDER = kit.ROOT / "bin" / "_lib" / "record-read.py"
ROUNDS = kit.load("line", "rounds")   # 往復の記録の書き手（line）。plan-review の src を読む前に読む（kit.load は前の src を外す）


def line_record(run, items=(), *, precedent_checks=None) -> str:
    """line の書き手で組んだ往復の記録（rounds.fresh に、items の項目を審査して block の無かった往復 1 つを rounds.record_pass で足した物。
    items の行は案の行に修正案の欄を重ねた物）を run の置き場に置いた pointer。手で枠を組まない"""
    import converge   # lib/（kit.load が sys.path に足した後）
    doc = ROUNDS.fresh()
    rows = converge.plan_rows([{**it, **v.fields(it["unit_keys"][0])} for it in items])
    got = {"pass": 1, "plan": rows, "answers": [], "review": {"faces": [], "shrink": [], "reason": "穴は無い"}, "resolved": []}
    if precedent_checks is not None:
        got["precedent_checks"] = precedent_checks
    ROUNDS.record_pass(doc, got, at_cap=False, dest=run.artifacts / "line" / "passes")
    return run.put("line/plan-converge.json", kit.shaped("shared:plan-converge.schema.json", doc))


def workflow() -> dict:
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))


def nodes() -> dict:
    out = {}
    for node in workflow()["nodes"]:
        out[node["id"]] = node
        for inner in (node.get("loop_group") or {}).get("nodes") or []:
            out[inner["id"]] = inner
    return out


def roles() -> dict:
    """AI の node（prompt を持つ node）を、YAML から {id: node} で（node の id を手で並べない）"""
    return {nid: node for nid, node in nodes().items() if "prompt" in node}


def first_and_fix() -> tuple[set, set]:
    """輪ごとに、出し直しの役（同じ輪の <1 回目の役>-fix）を持つ 1 回目の役と、出し直しの役の id"""
    first, fix = set(), set()
    for node in workflow()["nodes"]:
        body = {n["id"] for n in (node.get("loop_group") or {}).get("nodes") or [] if "prompt" in n}
        for nid in body:
            if nid.endswith("-fix") and nid.removesuffix("-fix") in body:
                first.add(nid.removesuffix("-fix"))
                fix.add(nid)
    return first, fix


def libs():
    """lib の KEEP のモジュール（script と同じ sys.path で読む）"""
    kit.load("plan-review", "files")
    import converge
    import gatemarks
    import rolekit
    return converge, gatemarks, rolekit


class _Case(unittest.TestCase):
    def setUp(self):
        self.run = v.Block(self)

    def doc(self, name="intake.json"):
        return self.run.read(name)

    def file(self, name, text) -> str:
        path = self.run.artifacts.parent / name
        path.write_text(text, encoding="utf-8")
        return str(path)


# ---------------------------------------------------------------- 入口
class IntakeFormCase(_Case):
    """入力の形の決め（8 節の intake の 2）: pointer・JSON の値・在るファイルは構造、ほかは方針の文。読めない pointer は failed"""

    def test_pointer_value_and_file_are_the_plan_form(self):
        inputs = self.run.plan_inputs()
        raw = json.loads((self.run.artifacts / json.loads(inputs["proposal"])["path"]).read_text(encoding="utf-8"))
        path = self.file("proposal.json", v.dump(raw))
        for name, given in (("pointer", inputs["proposal"]), ("value", v.dump(raw)), ("path", path)):
            with self.subTest(name):
                got = self.run.intake(**{**inputs, "proposal": given})
                self.assertEqual(got, {"due": True, "form": "plan", "tree": False, "k": 1, "reason": ""})
                self.assertEqual(self.doc()["plan"]["plan"], raw["plan"])

    def test_policy_text_is_the_text_form(self):
        got = self.run.intake(proposal=v.POLICY_TEXT, purpose=v.PURPOSE)
        self.assertEqual(got, {"due": True, "form": "text", "tree": False, "k": 0, "reason": ""})
        doc = self.doc()
        self.assertEqual((doc["proposal_text"], doc["purpose"], doc["world"], doc["review_rev"], doc["diff_base"]),
                         (v.POLICY_TEXT, v.PURPOSE, [], "HEAD", "HEAD"))
        self.assertFalse((self.run.artifacts / "judgment.json").exists(), "形 text は判定を読まない")
        got = self.run.intake(proposal="Keep one retry with a fixed wait.", judgment="", fields="")
        self.assertEqual(got["form"], "text", "1 行の字で在るファイルに当たらない物も方針の文")

    def test_unreadable_pointer_and_shapeless_object_fail(self):
        """読めない pointer・plan の無い object を方針の文として審査しない（黙った緩め。K15）"""
        for given, word in ((self.run.pointer("nope/p2.fix_plan.json"), "入力 proposal"),
                            ('{"steps": ["a"]}', "必須の欄 'plan'"), ('{"plan": []}', "入力 proposal")):
            with self.subTest(given):
                got = self.run.intake(proposal=given)
                self.assertEqual((got["due"], got["k"]), (False, 0))
                self.assertIn(word, got["reason"])
                self.assertFalse((self.run.artifacts / "intake.json").exists())
                self.assertEqual(self.doc("intake-error.json")["why"], got["reason"])

    def test_plan_form_needs_judgment_and_fields(self):
        for name, word in (("judgment", "入力 judgment: 判定の返りが渡されていない"), ("fields", "入力 fields: 修正案の欄が渡されていない")):
            with self.subTest(name):
                got = self.run.intake(**self.run.plan_inputs(**{name: ""}))
                self.assertEqual((got["due"], got["form"], got["reason"]), (False, "plan", word))

    def test_empty_values_read_as_absent(self):
        """graph の with: が渡しうる空の字・null・空の object・空の配列は既定と同じ「無い」"""
        for empty in ("", "null", "{}", "[]"):
            with self.subTest(empty=empty):
                got = self.run.intake(**self.run.plan_inputs(design=empty, world_rows=empty, means=empty, structure=empty,
                                                             ripple=empty, prior=empty, excluded=empty, request=empty, recorded=empty))
                self.assertTrue(got["due"], got)
                doc = self.doc()
                self.assertEqual((doc["design_why"], doc["means"], doc["request"], doc["excluded_file"]),
                                 ("独立設計の返りが渡されていない", [], "", ""))
                self.assertEqual(self.doc("structure/state.json")["status"], "failed")
                self.assertEqual(self.doc("ripple.json")["error"], "波及の一覧が渡されていない")

    def test_unreadable_soft_inputs_are_named_in_defaults(self):
        """excluded・request・means は読めなくても落とさず、無いとして読んで訳を defaults に残す"""
        got = self.run.intake(**self.run.plan_inputs(excluded=self.run.pointer("nope/excluded.json"), request="/nope/request.json",
                                                     means='{"means": 1}'))
        self.assertTrue(got["due"], got)
        defaults = self.doc()["defaults"]
        self.assertEqual(len(defaults), 3, defaults)
        self.assertTrue(any("入力 excluded" in x for x in defaults))
        self.assertTrue(any("依頼のファイル /nope/request.json" in x for x in defaults))
        self.assertTrue(any("入力 means" in x for x in defaults))

    def test_unreadable_hard_inputs_fail(self):
        """design・world_rows・structure・ripple・prior は値が在るのに読めなければ failed"""
        bad = self.run.pointer("nope/x.json")
        for name in ("design", "world_rows", "structure", "ripple", "prior"):
            with self.subTest(name):
                got = self.run.intake(**self.run.plan_inputs(**{name: bad}))
                self.assertFalse(got["due"])
                self.assertTrue(got["reason"].startswith(f"入力 {name}: "), got["reason"])
        got = self.run.intake(**self.run.plan_inputs(design=v.dump({"question_stands": True})))
        self.assertIn("入力 design", got["reason"])
        bad_values = {"structure": ("shared:structure-state.schema.json", {"status": 3}),
                      "ripple": ("shared:ripple.schema.json", {"items": "列でない"}),
                      "prior": ("shared:plan-converge.schema.json", {"passes": "列でない"})}
        for name, (shape, value) in bad_values.items():   # 値で渡しても、宣言の形に合わなければ落ちる
            with self.subTest(value=name):
                got = self.run.intake(**self.run.plan_inputs(**{name: v.dump(value)}))
                self.assertFalse(got["due"])
                self.assertTrue(got["reason"].startswith(f"入力 {name}: 入力が {shape} の形に合わない"), got["reason"])
        got = self.run.intake(**self.run.plan_inputs(tree="maybe"))
        self.assertIn("入力 tree", got["reason"])


class IntakeCopyCase(_Case):
    """入口の写し（8 節の intake の 1・5〜13）"""

    def test_marks_and_answers_are_split_off(self):
        narrow = {"what": "空の列の平均", "why": "例外にする", "decided_by": "依頼の引用", "no_narrow": "n" * 20}
        items = [v.item(v.UNIT_MEAN, 1, narrows=[narrow]), v.item(v.UNIT_CLAMP, 2)]
        answers = [{"key": "k1", "handled": "absorbed", "how": "直した"}]
        got = self.run.intake(**self.run.plan_inputs(items, answers=answers))
        self.assertTrue(got["due"], got)
        doc = self.doc()
        self.assertEqual(doc["plan"]["plan"][0]["narrows"], [{"what": "空の列の平均", "why": "例外にする"}])
        self.assertNotIn("block_answers", doc["plan"])
        self.assertEqual(doc["plan_marks"], [[{"decided_by": "依頼の引用", "no_narrow": "n" * 20}], []])
        record = self.doc("plan-converge.json")
        self.assertEqual(record["open"], {"answers": answers}, "修正案の役の答えは往復の記録の作業の写しの open に")
        self.assertEqual([r["unit_keys"] for r in record["plan"]], [[v.UNIT_MEAN], [v.UNIT_CLAMP]])
        self.assertEqual(record["plan"][0]["row"]["route"], "direct", "記録の案の行は欄を重ねた物")
        self.assertEqual((doc["units"], doc["names"]), (v.UNITS, [v.UNIT_MEAN, v.UNIT_CLAMP]))
        self.assertEqual(doc["diagnosis"], {"framing": v.FRAMING, "one_shot": v.ONE_SHOT})
        self.assertEqual(self.doc("judgment.json")["units"], v.UNITS)
        self.assertTrue((self.run.artifacts / "plan-fields.json").is_file())
        self.assertIn('"op": "plan_fields_saved"', (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8"))

    def test_record_rows_carry_the_split_marks(self):
        """#849: 往復の記録の作業の写しの案の行 row は決め手の欄を外した審査の形のまま、外した欄を項目ごとに lib の converge.PLAN_MARKS に
        添える（欄の名 "marks"。narrows の行と同じ並び。行に重ねると役の書いた narrows の行に戻る。修正案の受け付けが閉じた項目を役の書く形に戻す元）"""
        narrow = {"what": "空の列の平均", "why": "例外にする", "decided_by": "依頼の引用", "no_narrow": "n" * 20}
        items = [v.item(v.UNIT_MEAN, 1, narrows=[narrow, {"what": "負の値", "why": "弾く", "no_narrow": "m" * 20}]),
                 v.item(v.UNIT_CLAMP, 2)]
        got = self.run.intake(**self.run.plan_inputs(items))
        self.assertTrue(got["due"], got)
        plan = self.doc("plan-converge.json")["plan"]
        self.assertEqual(plan[0]["row"]["narrows"], [{"what": "空の列の平均", "why": "例外にする"}, {"what": "負の値", "why": "弾く"}])
        self.assertEqual([p.get("marks") for p in plan],
                         [[{"decided_by": "依頼の引用", "no_narrow": "n" * 20}, {"no_narrow": "m" * 20}], []])
        self.assertEqual([{**n, **m} for n, m in zip(plan[0]["row"]["narrows"], plan[0]["marks"])], items[0]["narrows"])

    def test_fields_count_apart_from_plan_rows_fails(self):
        inputs = self.run.plan_inputs()
        inputs["fields"] = v.dump(v.fields_doc(v.item(v.UNIT_MEAN)))
        got = self.run.intake(**inputs)
        self.assertFalse(got["due"])
        self.assertIn("入力 fields: 修正案の項目の数 2", got["reason"])

    def test_prior_gives_the_pass_number_and_precedent_checks(self):
        checks = {"https://x.example/a": {"found": True, "quote": "q"}}
        got = self.run.intake(**self.run.plan_inputs(prior=line_record(self.run, [v.item(v.UNIT_MEAN, 1)], precedent_checks=checks)))
        self.assertEqual((got["k"], self.doc()["k"]), (2, 2))
        self.assertEqual(self.doc("precedent-checks.json"), checks)
        self.assertEqual(len(self.doc("plan-converge.json")["passes"]), 1)
        # 往復の記録の行に書き手だけが欄を足すと、読み手の口が共有の形（shared:plan-converge.schema.json）で落とす（#845・#849・#851）
        got = self.run.intake(**self.run.plan_inputs(prior=self.run.put("line/bad.json", {"passes": [{"pass": 1, "書き手だけの欄": 1}]})))
        self.assertIn("入力 prior: 入力が shared:plan-converge.schema.json の形に合わない", got["reason"])
        self.assertIn("知らない欄 '書き手だけの欄'", got["reason"])

    def test_copies_world_structure_design_ripple_and_means(self):
        rows = [{"unit": "u1", "verdict": "汚れる", "route": "人に上げる"}]
        got = self.run.intake(**self.run.plan_inputs(world_rows=self.run.world(v.WORLD_ROW), structure=self.run.structure(rows),
                                                     design=v.dump(v.DESIGN_OK), means=v.dump(["len(xs) - 1 で割る"]),
                                                     excluded=self.run.put("judge/excluded.json", {"paths": ["x.py"]}),
                                                     review_rev="abc123", lang="English"))
        self.assertTrue(got["due"], got)
        doc = self.doc()
        self.assertEqual((doc["review_rev"], doc["diff_base"], doc["lang"]), ("abc123", "abc123", "English"))
        self.assertEqual((self.run.artifacts / "world/world.jsonl").read_text(encoding="utf-8").strip(), v.dump(v.WORLD_ROW))
        self.assertEqual(self.doc("judge-world-state.json")["status"], "ok")
        self.assertEqual(self.doc("judge-purpose-means.json"), {"means": ["len(xs) - 1 で割る"]})
        state = self.doc("structure/state.json")
        self.assertEqual((state["status"], state["design_file"]), ("ok", str(self.run.artifacts / "structure/design-rows.jsonl")))
        self.assertEqual(self.doc("design.json"), v.DESIGN_OK)
        self.assertEqual(self.doc("ripple.json")["note"], v.RIPPLE_MARK)
        self.assertEqual((doc["excluded_file"], self.doc("excluded.json")), (str(self.run.artifacts / "excluded.json"), {"paths": ["x.py"]}))
        self.assertEqual(doc["design_why"], "")
        self.assertEqual(doc["review_schema"], nodes()["review"]["output_format"])

    def test_recorded_rows_from_the_port_or_the_policy_document(self):
        policy = self.file("policy.md", "# 方針\n- 公開の口を減らさない\n- 期限を足さない\n")
        self.run.intake(**self.run.plan_inputs(policy=policy))
        self.assertEqual(self.doc()["recorded_policy"], [{"source": "doc", "name": policy, "text": "", "lines": 3, "alias": ""}])
        self.assertEqual(self.doc()["policy_copy"], policy)
        rows = [{"source": "gate", "name": "承認ノードの答え 3f2a1c", "text": "始める"}]
        self.run.intake(**self.run.plan_inputs(policy=policy, recorded=v.dump(rows)))
        self.assertEqual(self.doc()["recorded_policy"], rows)
        got = self.run.intake(**self.run.plan_inputs(recorded=v.dump([{"source": "web", "name": "x"}])))
        self.assertIn("入力 recorded", got["reason"])

    def test_tree_words(self):
        for word, want in (("on", True), ("off", False), ("auto", True), ("", True)):
            with self.subTest(word):
                self.assertEqual(self.run.intake(**self.run.plan_inputs(tree=word))["tree"], want)
        got = self.run.intake(**self.run.plan_inputs([v.item(v.UNIT_MEAN)], tree="auto"))
        self.assertFalse(got["tree"], "auto は開いた項目が 2 つ以上なら木")

    def test_own_files_are_removed_by_name(self):
        art = self.run.artifacts
        for name in ("review.json", "pass.json", "crash.json", "rejects-p2.plan_review.json", "candidate-p2.plan_review.json",
                     "rejects-p2.plan_review.text.json", "review-prompt-1.md", "review-material-1.md", "review-marks.json"):
            (art / name).write_text("{}", encoding="utf-8")
        (art / "items").mkdir()
        (art / "items" / "item-1.md").write_text("x", encoding="utf-8")
        (art / "libdocs").mkdir()
        (art / "libdocs" / "keep.json").write_text("{}", encoding="utf-8")
        (art / "rejects-other.json").write_text("[]", encoding="utf-8")
        self.run.intake(**self.run.plan_inputs())
        left = sorted(p.name for p in art.iterdir())
        for name in ("review.json", "pass.json", "crash.json", "rejects-p2.plan_review.json", "candidate-p2.plan_review.json",
                     "rejects-p2.plan_review.text.json", "review-prompt-1.md", "review-material-1.md", "review-marks.json", "items"):
            self.assertNotIn(name, left)
        self.assertTrue((art / "libdocs" / "keep.json").is_file(), "ライブラリの文書の控えは消さない")
        self.assertTrue((art / "rejects-other.json").is_file(), "ほかの受け付けの控えを広い形で消さない")


class ReplanIntakeCase(_Case):
    """形 replan の入口（8 節の intake の 6・11）"""

    def prior(self, items) -> str:
        return line_record(self.run, items)

    def test_ruled_items_and_rows(self):
        old = [v.item(v.UNIT_MEAN, 1), v.item(v.UNIT_CLAMP, 2)]
        new = [v.item(v.UNIT_MEAN, 1), v.item(v.UNIT_CLAMP, 2, approach="直した形",
                                               narrows=[{"what": "x", "why": "y", "decided_by": "依頼の引用"}])]
        conflicts = {"items": [{"id": "c1", "unit_key": v.UNIT_CLAMP, "between": ["a", "b"], "why_both_cannot_hold": "w",
                                "kind": "brief_vs_judgment", "which_is_right": "code",
                                "ruling": {"decision": "fix_plan_item", "text": "項目 2 を直す", "plan_items": [2]}}]}
        got = self.run.intake(**self.run.plan_inputs(new, ruling='["2"]', prior=self.prior(old),
                                                     conflicts=self.run.put("fix/conflicts.json", conflicts)))
        self.assertEqual(got, {"due": True, "form": "replan", "tree": False, "k": 0, "reason": ""})
        doc = self.doc()
        self.assertEqual(doc["ruled"], [2])
        [row] = doc["replan_items"]
        self.assertEqual((row["item"], row["units"], row["old"]["approach"], row["new"]["approach"]),
                         (2, [v.UNIT_CLAMP], old[1]["approach"], "直した形"))
        self.assertEqual(row["new"]["narrows"][0]["decided_by"], "依頼の引用", "直した形の narrows は決め手の欄つき")
        self.assertEqual(len(row["rows"]), 1)
        self.assertEqual(self.run.intake(**self.run.plan_inputs(new, ruling="[2]", prior=self.prior(old)))["form"], "replan")

    def test_no_approved_plan_or_stray_item_fails(self):
        got = self.run.intake(**self.run.plan_inputs(ruling='["1"]'))
        self.assertEqual((got["due"], got["form"]), (False, "replan"))
        self.assertIn("承認済みの修正案", got["reason"])
        got = self.run.intake(**self.run.plan_inputs(ruling='["3"]', prior=self.prior([v.item(v.UNIT_MEAN), v.item(v.UNIT_CLAMP)])))
        self.assertIn("入力 ruling", got["reason"])
        for bad in ('["x"]', "2", "1,2"):   # 番号でない行と、番号の配列の形（shared:replan-items.schema.json）でない字
            with self.subTest(bad=bad):
                got = self.run.intake(**self.run.plan_inputs(ruling=bad, prior=self.prior([v.item(v.UNIT_MEAN), v.item(v.UNIT_CLAMP)])))
                self.assertIn("入力 ruling", got["reason"])


# ---------------------------------------------------------------- 出口
class FinishCase(_Case):
    """出口はどの段が落ちても落ちない（8 節の finish）"""

    def finish(self) -> dict:
        got = self.run.script("finish")
        self.assertEqual(sorted(got), sorted(RETURNS))
        self.assertEqual(self.doc("finish.json"), got)
        return got

    def test_failed_intake_names_its_reason(self):
        got = self.finish()
        self.assertEqual((got["status"], got["ok"], got["reason"]), ("failed", False, "入口の控えが無い（入口の node が落ちた）"))
        self.run.intake(proposal=self.run.pointer("nope.json"))
        got = self.finish()
        self.assertEqual(got["status"], "failed")
        self.assertIn("入力 proposal", got["reason"])
        self.assertEqual(got["report"], [f"事前審査: {got['reason']}"])

    def test_loop_not_run_crash_and_last_reject(self):
        self.run.intake(**self.run.plan_inputs())
        self.assertEqual(self.finish()["reason"], "役の loop が回らなかった")
        (self.run.artifacts / "rejects-p2.plan_review.json").write_text(
            v.dump([{"at": "t", "reason": "faces・shrink[0] の key が重複"}]), encoding="utf-8")
        self.assertEqual(self.finish()["reason"], "受け付けを通らなかった（最後の却下: faces・shrink[0] の key が重複）")
        steps = kit.load("plan-review", "steps")
        steps.record_crash(self.run.artifacts, "review-prep", "FieldsBroken: 食い違い")
        got = self.finish()
        self.assertEqual((got["status"], got["round"], got["form"]), ("failed", 1, "plan"))
        self.assertEqual(got["reason"], "review-prep の node が落ちた（FieldsBroken: 食い違い）")
        self.assertEqual((got["holes"], got["pass"], got["asks"], got["gave_up"]), (None, None, [], None))

    def test_text_form_ok_and_gave_up(self):
        self.run.intake(proposal=v.POLICY_TEXT)
        hole = {"key": "fixed-wait-retry-storm", "kind": "regression", "where": "the policy", "why": "w" * 20, "severity": "block",
                "reach": "breaks_fix"}
        (self.run.artifacts / "review.json").write_text(v.dump({"faces": [hole], "shrink": [], "reason": "r" * 20}), encoding="utf-8")
        with self.run.env():
            got = self.finish()
        self.assertEqual((got["status"], got["ok"], got["blocks"], got["round"]), ("ok", True, ["fixed-wait-retry-storm"], 0))
        self.assertEqual(got["holes"]["path"], "review.json")
        self.assertEqual(got["report"], ["事前審査（方針の文）: 穴 1 件（block 1）・別案 0 件",
                                         f"- [regression] fixed-wait-retry-storm: {'w' * 20}"])
        (self.run.artifacts / "review.json").unlink()
        rows = [{"at": "t", "reason": f"拒否 {n}"} for n in range(1, 4)]
        (self.run.artifacts / "rejects-p2.plan_review.text.json").write_text(v.dump(rows), encoding="utf-8")
        got = self.finish()
        self.assertEqual((got["status"], got["ok"]), ("gave_up", False))
        self.assertTrue(got["reason"].startswith("事前審査の受け付けが諦めた: "), got["reason"])
        self.assertIn("拒否 3", got["reason"])
        self.assertEqual(self.doc("review.json")["faces"], [], "諦めた時も holes は空の返答を指す")
        self.assertEqual(got["holes"]["path"], "review.json")

    def test_finish_falls_back_without_crashing(self):
        (self.run.artifacts / "intake.json").write_text(v.dump({"form": "plan", "k": "x"}), encoding="utf-8")
        got = self.run.script("finish")
        self.assertEqual((got["status"], got["ok"]), ("failed", False))
        self.assertTrue(got["reason"].startswith("出口が落ちた"), got["reason"])


# ---------------------------------------------------------------- 筋
class FlowCase(_Case):
    """intake → review_prep → 台本の返答 → review_accept → finish（15.3 の筋）"""

    def accept(self, reply=None, **more) -> dict:
        given = {"reply": v.dump(reply) if reply is not None else "null", "status_guarded": "true", **more}
        return self.run.script("review_accept", **given)

    def one_pass(self, inputs, reply) -> dict:
        got = self.run.intake(**inputs)
        self.assertTrue(got["due"], got)
        prep = self.run.script("review_prep")
        self.assertEqual((prep["resubmit"], prep["tree"]), (False, False))
        got = self.accept(reply)
        self.assertTrue(got["ok"], got)
        return self.run.script("finish")

    def prior_from(self, got) -> str:
        """line の側の使い方の見本: 往復の記録の作業の写しに pass の材料を converge.add_pass で足し、precedent_checks を頭に置いて次の往復の prior にする"""
        converge, _, _ = libs()
        record = self.doc("plan-converge.json")
        row = self.run.read(got["pass"]["path"])
        converge.add_pass(record, row["review"], answers=row["answers"], resolved=row["resolved"], synergy=row["synergy"],
                          hits=row["hits"], origins=row["origins"], refs=row["refs"], push=row["push"])
        record["precedent_checks"] = row["precedent_checks"]
        return self.run.put(f"line/prior-{row['pass']}.json", record)

    def test_first_pass_returns_holes_and_the_pass_row(self):
        hole = v.face("item1-mean-empty-division", 1, kind="regression", decided_by="依頼の引用「平均」", severity="suggest")
        got = self.one_pass(self.run.plan_inputs(), v.review(hole))
        self.assertEqual((got["status"], got["ok"], got["form"], got["round"], got["blocks"]), ("ok", True, "plan", 1, []))
        review = self.run.read(got["holes"]["path"])
        self.assertEqual(sorted(review), ["faces", "reason", "shrink"])
        self.assertEqual(review["faces"][0]["unit_keys"], [v.UNIT_MEAN], "単位の番号は名に戻す")
        self.assertEqual(review["faces"][0]["decided_by"], "依頼の引用「平均」", "決め手の欄は review.json に残る（今と同じ形）")
        row = self.run.read(got["pass"]["path"])
        for name in ("pass", "plan", "answers", "review", "resolved", "synergy", "hits", "origins", "refs", "push", "files", "rejects",
                     "precedent_checks"):
            self.assertIn(name, row)
        self.assertEqual((row["pass"], row["rejects"]), (1, []))
        self.assertEqual([a["kind"] for a in got["asks"]], ["regression"])
        self.assertEqual(got["asks"][0]["mark"].get("decided_by"), "依頼の引用「平均」")
        self.assertEqual(got["report"], ["事前審査（1 往復目・修正案）: block 無い・suggest 1 件・別案 0 件"])
        converge, _, _ = libs()
        record = self.doc("plan-converge.json")
        added = converge.add_pass(record, row["review"], answers=row["answers"], resolved=row["resolved"])
        self.assertEqual(added["pass"], 1, "pass.json の材料で往復の行が立つ")

    def test_second_pass_reads_the_prior_record(self):
        block = v.face("item1-mean-empty-division", 1, kind="contract_drift")
        got = self.one_pass(self.run.plan_inputs(), v.review(block))
        self.assertEqual(got["blocks"], ["item1-mean-empty-division"])
        prior = self.prior_from(got)
        answers = [{"key": "item1-mean-empty-division", "handled": "absorbed", "how": "分母を直す行を足した"}]
        items = [v.item(v.UNIT_MEAN, 1, approach="直した案"), v.item(v.UNIT_CLAMP, 2)]
        got = self.run.intake(**self.run.plan_inputs(items, answers=answers, rnd=2, prior=prior))
        self.assertEqual((got["due"], got["k"]), (True, 2), got)
        prep = self.run.script("review_prep")
        material = (self.run.artifacts / "review-material-1.md").read_text(encoding="utf-8")
        self.assertIn("## Previous passes", material)
        self.assertIn("item1-mean-empty-division", material)
        self.assertIn("review-material-1.md", prep["prompt"])
        got = self.accept(v.review(resolved=["item1-mean-empty-division"]))
        self.assertTrue(got["ok"], got)
        got = self.run.script("finish")
        self.assertEqual((got["status"], got["round"]), ("ok", 2))
        self.assertEqual(self.run.read(got["pass"]["path"])["pass"], 2)

    def test_rejected_answer_is_resubmitted_in_the_same_conversation(self):
        self.run.intake(**self.run.plan_inputs())
        self.run.script("review_prep")
        twice = v.review(v.face("same-key-twice", 1, severity="suggest"), v.face("same-key-twice", 1, severity="suggest"))
        got = self.accept(twice)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        prep = self.run.script("review_prep", prev="false")
        self.assertTrue(prep["resubmit"])
        fix = self.run.script("review_fix_prep")
        self.assertIn("candidate-p2.plan_review.json", fix["prompt"])
        self.assertIn("same-key-twice", fix["prompt"], "却下の理由を字のまま貼る")
        got = self.accept(fix_reply=v.dump({"faces": [twice["faces"][0]]}))
        self.assertTrue(got["ok"], got)
        got = self.run.script("finish")
        self.assertEqual(got["status"], "ok")
        self.assertEqual([f["key"] for f in self.run.read(got["holes"]["path"])["faces"]], ["same-key-twice"])
        self.assertEqual(len(self.run.read(got["pass"]["path"])["rejects"]), 1, "この往復の事前審査の拒否だけ")

    def test_replan_flow_returns_the_item_facts(self):
        old = [v.item(v.UNIT_MEAN, 1), v.item(v.UNIT_CLAMP, 2)]
        prior = line_record(self.run, old)
        new = [old[0], v.item(v.UNIT_CLAMP, 2, approach="直した形")]
        got = self.one_pass(self.run.plan_inputs(new, ruling='["2"]', prior=prior), v.review())
        self.assertEqual((got["status"], got["form"], got["round"], got["pass"]), ("ok", "replan", 0, None))
        self.assertEqual([r["item"] for r in got["replan"]], [2])
        self.assertEqual(sorted(got["replan"][0]), ["contract_changed", "human", "item", "units", "widened"])
        self.assertEqual(self.doc("replan.json"), got["replan"])
        self.assertEqual(got["report"], ["事前審査（案の直し・項目 2）: block 無い・suggest 0 件・別案 0 件"])

    def test_replan_give_up_names_each_item(self):
        old = [v.item(v.UNIT_MEAN, 1), v.item(v.UNIT_CLAMP, 2)]
        prior = line_record(self.run, old)
        self.run.intake(**self.run.plan_inputs(old, ruling='["1", "2"]', prior=prior))
        _, _, rolekit = libs()
        given = [{"at": "t", "reason": f"拒否 {n}", "after": rolekit.NET_AFTER} for n in range(1, rolekit.NET_AFTER + 1)]
        (self.run.artifacts / "rejects-p2.plan_review.json").write_text(v.dump(given), encoding="utf-8")
        got = self.run.script("finish")
        self.assertEqual(got["status"], "gave_up")
        self.assertEqual([r["item"] for r in got["gave_up"]], [1, 2])
        self.assertIn(f"拒否 {rolekit.NET_AFTER}", got["gave_up"][0]["why"])
        self.assertEqual(self.doc("replan-gave-up.json"), got["gave_up"])

    def test_text_flow(self):
        got = self.run.intake(proposal=v.POLICY_TEXT, purpose=v.PURPOSE, world_rows=self.run.world(v.WORLD_ROW))
        self.assertEqual(got["form"], "text")
        prep = self.run.script("text_prep")
        self.assertIn(v.POLICY_TEXT.splitlines()[0], prep["prompt"])
        hole = {k: x for k, x in v.face("fixed-wait-retry-storm").items() if k != "unit_keys"}
        got = self.run.script("text_accept", reply=v.dump(v.review(hole)), status_guarded="true")
        self.assertTrue(got["ok"], got)
        got = self.run.script("finish")
        self.assertEqual((got["status"], got["blocks"], got["asks"], got["pass"]), ("ok", ["fixed-wait-retry-storm"], [], None))
        self.assertEqual(got["report"][0], "事前審査（方針の文）: 穴 1 件（block 1）・別案 0 件")


# ---------------------------------------------------------------- 読んだ証拠
class ReadsCase(_Case):
    """読んだ証拠（review-reads。今の boardview.collect_reads の写し）: 隔離した設定のフック（bin/_lib/record-read.py を実物で起こす）が
    作業の場ごとに書いた記録から、審査の役が材料のファイルと方針の写しを読んだか・束ね役が下請けを何人起こしたか・web を引いたかを集める。
    受け付けの条件にしない"""

    def setUp(self):
        super().setUp()
        import reads   # lib/（kit.load が sys.path に足した後）
        self.reads = reads
        self.config = self.run.artifacts.parent / "claude"
        (self.config / reads.ROOT).mkdir(parents=True)

    def hook(self, tool, session="s-1", **tool_input):
        event = {"session_id": session, "tool_name": tool, "tool_input": tool_input, "tool_use_id": f"toolu_{tool}",
                 "cwd": str(self.run.repo), "hook_event_name": "PostToolUse"}
        done = subprocess.run([sys.executable, str(RECORDER), str(self.config / self.reads.ROOT)], input=json.dumps(event), text=True,
                              encoding="utf-8", capture_output=True, cwd=str(self.run.repo),
                              env=hermetic.child_env(PYTHONDONTWRITEBYTECODE="1", CLAUDE_PROJECT_DIR=str(self.run.repo)))
        self.assertEqual(done.returncode, 0, done.stderr)

    def collect(self, config=None) -> tuple:
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "review_reads.py")], cwd=self.run.repo, capture_output=True,
                              text=True, encoding="utf-8",
                              env=hermetic.child_env(**self.run.environ(), CLAUDE_CONFIG_DIR=str(config or self.config)))
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(done.stdout)
        self.assertTrue(got["ok"], got)
        return got, json.loads(pathlib.Path(got["index_file"]).read_text(encoding="utf-8"))

    def material(self, **inputs) -> str:
        self.assertTrue(self.run.intake(**self.run.plan_inputs(**inputs))["due"])
        self.run.script("review_prep")
        return str(self.run.artifacts / "review-material-1.md")

    def test_reads_collected_from_the_hook_records(self):
        material = self.material()
        self.hook("Read", file_path=material)
        got, index = self.collect()
        self.assertEqual(pathlib.Path(got["index_file"]).name, "reads-plan-review-block.json")
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["rows"], [{"path": material, "hook": "read"}])
        self.assertEqual((doc["sources"]["hook"], got["missing"]), ("recorded", []))
        out = self.run.script("finish")
        self.assertEqual(out["reads"]["path"], "reads-plan-review.json")
        self.assertFalse(any("読んだ記録が無い" in line for line in out["report"]))

    def test_unread_material_and_policy_are_missing_and_named_in_the_report(self):
        policy = self.file("policy.md", "# 方針\n- 公開の口を減らさない\n")
        material = self.material(policy=policy)
        self.hook("Read", file_path=material)
        got, _ = self.collect()
        self.assertEqual(got["missing"], [policy], "方針の写しも読むパス")
        self.run.script("review_accept", reply=v.dump(v.review()), status_guarded="true")
        out = self.run.script("finish")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["report"][-1], f"事前審査の役が渡したファイルを読んだ記録が無い（{policy}）")
        got, index = self.collect(config=self.run.artifacts.parent / "no-config")
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual((doc["sources"]["hook"], doc["sources"]["why"], got["missing"]), ("none", self.reads.NO_ROOT, []))

    def test_agent_launches_counted_against_item_files(self):
        """束ね役の Agent の起動の数と subagent_type を、書いた下請けの項目の材料のファイルの数と並べて trace に残す（拒まない）"""
        material = self.material(tree="on")
        self.hook("Read", file_path=material)
        for _ in range(3):
            self.hook("Agent", subagent_type="general-purpose", prompt="項目を見よ")
        self.collect()
        rows = [json.loads(x) for x in (self.run.artifacts / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        got = [{k: x[k] for k in ("launched", "types", "item_files", "synergy_files")} for x in rows if x["op"] == "plan_review_agents"]
        self.assertEqual(got, [{"launched": 3, "types": {"general-purpose": 3}, "item_files": 2, "synergy_files": 1}])

    def test_web_calls_recorded(self):
        self.hook("Read", file_path=self.material())
        self.hook("WebFetch", url="https://docs.python.org/3/library/statistics.html", prompt="空の列")
        self.hook("WebSearch", query="statistics.mean empty")
        _, index = self.collect()
        doc = json.loads(pathlib.Path(index["plan-review"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["web"], {"fetches": ["https://docs.python.org/3/library/statistics.html"], "searches": ["statistics.mean empty"]})

    def test_records_before_the_intake_are_not_counted(self):
        """K14: 記録は入口が intake.json を書いた時刻から後の行で切る。前の往復の読みを今の往復の物に数えない"""
        material = self.material()
        self.hook("Read", file_path=material)
        log = self.reads.reads_path(self.config / self.reads.ROOT, self.run.repo)
        rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
        log.write_text("".join(json.dumps({**x, "ts": "2000-01-01T00:00:00"}) + "\n" for x in rows), encoding="utf-8")
        got, _ = self.collect()
        self.assertEqual(got["missing"], [material])

    def test_replan_and_text_forms_use_their_own_names(self):
        old = [v.item(v.UNIT_MEAN, 1), v.item(v.UNIT_CLAMP, 2)]
        prior = line_record(self.run, old)
        self.hook("Read", file_path=self.material(ruling='["2"]', prior=prior))
        got, index = self.collect()
        self.assertEqual((pathlib.Path(got["index_file"]).name, list(index)), ("reads-replan-block.json", ["replan-plan-review"]))
        self.run.intake(proposal=v.POLICY_TEXT)
        got, index = self.collect()
        self.assertEqual(index, {"plan-review-text": None, "why": kit.load("plan-review", "proof").NOTHING_HANDED},
                         "方針の写しの無い形 text は読ませるパスが無い")
        policy = self.file("policy.md", "# 方針\n")
        self.run.intake(proposal=v.POLICY_TEXT, policy=policy)
        self.hook("Read", file_path=policy, session="s-2")
        got, index = self.collect()
        self.assertEqual(got["missing"], [])
        self.assertEqual(pathlib.Path(index["plan-review-text"]).name, "reads-plan-review-text.json")

    def test_a_failed_collect_is_left_in_the_place_and_reported(self):
        self.material()
        (self.run.artifacts / "intake.json").write_text("[]", encoding="utf-8")
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / "review_reads.py")], cwd=self.run.repo, capture_output=True,
                              text=True, encoding="utf-8", env=hermetic.child_env(**self.run.environ(), CLAUDE_CONFIG_DIR=str(self.config)))
        got = json.loads(done.stdout)
        self.assertEqual((got["ok"], got["index_file"]), (False, ""))
        self.assertEqual(len(list(self.run.artifacts.glob("reads-plan-review-failed-*.json"))), 1)
        self.run.intake(**self.run.plan_inputs())
        self.assertEqual(list(self.run.artifacts.glob("reads-plan-review-failed-*.json")), [], "入口が前の落ちた記録を名の型で消す")


# ---------------------------------------------------------------- YAML
class YamlCase(unittest.TestCase):
    def test_ports_and_returns(self):
        doc = workflow()
        self.assertEqual(list(doc["inputs"]), PORTS)
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("finish", "ok"))
        fmt = nodes()["finish"]["output_format"]
        self.assertEqual((list(fmt["properties"]), fmt["required"]), (RETURNS, RETURNS))
        self.assertEqual(fmt["properties"]["status"]["enum"], ["ok", "gave_up", "failed"])

    def test_loops_count_the_accept_nets(self):
        _, _, rolekit = libs()
        got = nodes()
        self.assertEqual(got["review-loop"]["loop_group"]["max_iterations"], rolekit.NET_AFTER)
        self.assertEqual(got["text-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertEqual(got["theme-loop"]["loop_group"]["max_iterations"], rolekit.NET_AFTER)
        for loop in ("review-loop", "text-loop", "theme-loop"):
            self.assertIs(got[loop]["loop_group"]["fresh_context"], False)

    def test_loop_bodies_are_chains_of_one_node_per_layer(self):
        """会話を続ける輪の中で同じ層に 2 つの node を並べない（並んだ層は会話を切る。#571・Archon の落とし穴）"""
        for loop in ("review-loop", "text-loop", "theme-loop"):
            body = {n["id"]: n for n in nodes()[loop]["loop_group"]["nodes"]}
            layer = {}
            for nid, node in body.items():
                layer[nid] = 1 + max((layer[d] for d in node.get("depends_on") or []), default=-1)
            with self.subTest(loop):
                self.assertEqual(sorted(layer.values()), list(range(len(body))))

    def test_ai_nodes_are_the_prompt_nodes(self):
        """YAML の AI の node（prompt を持つ node）は、指示を組む口が名を持つ files.PROMPT_NODES と同じ組（下の照らしは YAML から引く）"""
        files = kit.load("plan-review", "files")
        self.assertEqual(set(roles()), set(files.PROMPT_NODES))

    def test_conversation_keys(self):
        """出し直しの役を持つ輪の 1 回目の役は context: fresh、出し直しの役と、出し直しの役を持たない輪の役（方針の文の役）は context を
        書かない（会話の続き）。どの役も指示は同じ輪の script の prep の出力で、模型の群と出し直しの鍵は同じ"""
        got = nodes()
        first, _ = first_and_fix()
        for nid, node in roles().items():
            with self.subTest(nid):
                if nid in first:
                    self.assertEqual(node.get("context"), "fresh")
                else:
                    self.assertNotIn("context", node)
                prep = node["prompt"].removeprefix("$").removesuffix(".output.prompt")
                self.assertEqual(node["prompt"], f"${prep}.output.prompt")
                self.assertIsNotNone(got[prep].get("script"), f"{nid} の指示を組む {prep} が script の node でない")
                self.assertEqual(node["model"], "@wf-plan-review")
                self.assertEqual(node["retry"], {"max_attempts": 2, "on_error": "all"})

    def test_every_node_keeps_the_checkout(self):
        for nid, node in nodes().items():
            if "loop_group" not in node:
                with self.subTest(nid):
                    self.assertIs(node.get("mutates_checkout"), False)

    def test_role_formats_are_mainline_plus_marks(self):
        converge, gatemarks, _ = libs()
        files = kit.load("plan-review", "files")
        got = nodes()
        fmt = got["review"]["output_format"]
        row = fmt["properties"]["faces"]["items"]["properties"]
        strip = lambda d: {k: x for k, x in d.items() if k not in ("note", "uniqueItems")}  # noqa: E731
        for name, schema in {**gatemarks.MARK_SCHEMA, gatemarks.NO_NARROW: gatemarks.NO_NARROW_SCHEMA}.items():
            with self.subTest(name):
                want = strip(schema)
                if name == gatemarks.RECOMMEND:
                    want = {**want, "properties": schema["properties"]}
                self.assertEqual(trimmed.without_trimmed(row[name]), want)
        self.assertEqual(trimmed.without_trimmed(fmt["properties"]["resolved"]), converge.RESOLVED_SCHEMA)
        self.assertEqual(trimmed.without_trimmed(fmt["properties"]["design_map"]), converge.DESIGN_MAP_SCHEMA)
        self.assertEqual(trimmed.without_trimmed(fmt["properties"]["origins"]), converge.ORIGIN_SCHEMA)
        self.assertEqual(trimmed.without_trimmed(got["review-tree"]["output_format"]["properties"]["items"]), converge.ITEMS_SCHEMA)
        self.assertEqual(fmt["required"], [], "根の欄は受け付けが確かめる（#832）")
        self.assertEqual(files.REVIEW_REQUIRED, ("faces", "shrink", "reason"))
        self.assertLessEqual(set(files.REVIEW_REQUIRED), set(fmt["properties"]))
        tree = got["review-tree"]["output_format"]
        self.assertEqual(tree["required"], [])
        self.assertEqual(files.TREE_REQUIRED, ("reason", "items"))
        self.assertLessEqual(set(files.TREE_REQUIRED), set(tree["properties"]))
        self.assertNotIn("items", fmt["properties"])

    def test_face_reach_and_stuck_recommend(self):
        converge, gatemarks, _ = libs()
        got = nodes()
        fmt = got["review"]["output_format"]
        row = fmt["properties"]["faces"]["items"]
        self.assertEqual(trimmed.without_trimmed(row["properties"][converge.REACH]), converge.REACH_SCHEMA)
        self.assertIn(converge.REACH, row["required"])
        schema = gatemarks.MARK_SCHEMA[gatemarks.RECOMMEND]
        self.assertEqual(trimmed.without_trimmed(fmt["properties"][converge.STUCK_PUSH]), {k: x for k, x in schema.items() if k != "note"})
        self.assertNotIn(converge.STUCK_PUSH, kit.load("plan-review", "files").REVIEW_REQUIRED)
        self.assertNotIn(gatemarks.RECOMMEND, row["required"])
        tree = got["review-tree"]["output_format"]["properties"]
        for name in ("reason", converge.STUCK_PUSH):
            self.assertEqual(tree[name], fmt["properties"][name], "束ね役の型の reason と推しは単独の役の型と同じ")

    def test_resubmit_formats_equal_the_first_role(self):
        """#832: 出し直しの役の型は 1 回目の役の型と同じ（違うと会話の続きの最初の要求でキャッシュが効かない）"""
        got = nodes()
        first, _ = first_and_fix()
        for base, fix in ((nid, f"{nid}-fix") for nid in sorted(first)):
            with self.subTest(fix):
                self.assertEqual(got[fix]["output_format"], got[base]["output_format"])
                launch = lambda node: {k: x for k, x in node.items()  # noqa: E731
                                       if k not in ("id", "depends_on", "when", "output_format", "context", "trigger_rule", "prompt")}
                self.assertEqual(launch(got[fix]), launch(got[base]), "起こし方の鍵は 1 回目の役と同じ")

    def test_text_format_has_no_plan_structure(self):
        got = nodes()
        text = got["review-text"]["output_format"]
        review = got["review"]["output_format"]["properties"]
        faces = text["properties"]["faces"]["items"]
        self.assertEqual(sorted(faces["properties"]), sorted(["key", "kind", "where", "why", "severity", "reach", "no_add", "decided_by", "fences"]))
        for name, shape in faces["properties"].items():
            self.assertEqual(shape, review["faces"]["items"]["properties"][name], name)
        self.assertEqual(faces["required"], ["key", "kind", "where", "why", "severity", "reach"])
        self.assertEqual(sorted(text["properties"]), ["faces", "faces_none", "reason", "shrink"])
        self.assertEqual(text["required"], ["faces", "shrink", "reason"])
        self.assertEqual(got["review-text"]["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])

    def test_theme_format_is_the_text_format_plus_resolved(self):
        """形 theme の役の型は形 text の型に往復の欄 resolved を足した物。根の欄は要ると書かない（出し直しの役と同じ型。#832）"""
        converge, _, _ = libs()
        got = nodes()
        theme, text = got["review-theme"]["output_format"], got["review-text"]["output_format"]
        self.assertEqual({k: x for k, x in theme["properties"].items() if k != converge.RESOLVED}, text["properties"])
        self.assertEqual(trimmed.without_trimmed(theme["properties"][converge.RESOLVED]), converge.RESOLVED_SCHEMA)
        self.assertEqual(theme["required"], [])
        self.assertEqual(got["review-theme"]["allowed_tools"], ["Read", "Grep", "Glob", "WebSearch", "WebFetch"])

    def test_theme_form_is_named(self):
        """形 plan の輪は形 theme で回らず、入口と出口の形の語に theme が在る。出口が形 theme の輪を待つかは、全部の workflow の返す節に
        当てる tests/workflows/test_returns_waits.py が照らす（読んだ証拠の review-reads は出口が待つ節の 1 つ）"""
        got = nodes()
        self.assertIn("review-reads", got["finish"]["depends_on"])
        self.assertIn("theme-loop", got["review-reads"]["depends_on"])
        self.assertIn("form != 'theme'", got["review-loop"]["when"])
        for nid in ("intake", "finish"):
            self.assertIn("theme", got[nid]["output_format"]["properties"]["form"]["enum"], nid)

    def test_formats_use_only_known_keywords(self):
        files = kit.load("plan-review", "files")
        import ports
        for nid in roles():
            with self.subTest(nid):
                self.assertEqual(ports.unknown_keywords(files.node_schema(nid)), [])
                self.assertEqual(files.node_schema(nid), nodes()[nid]["output_format"], "node_schema は YAML の型をそのまま読む")
                self.assertEqual(trimmed.missing_patterns(nodes()[nid]["output_format"]), [])

    def test_role_kinds_are_exactly_the_eight_looked_at(self):
        """役の返りの穴の種類は、断片 checks の「What to look at」の 8 つと同じ並び"""
        text = (BLOCK / "prompts" / "parts" / "checks.md").read_text(encoding="utf-8")
        looked = re.findall(r"^\d\. \*\*[^*]+\*\* \(kind=(\w+)\)", text, re.M)
        for nid in ("review", "review-text", "review-theme"):
            with self.subTest(nid):
                self.assertEqual(nodes()[nid]["output_format"]["properties"]["faces"]["items"]["properties"]["kind"]["enum"], looked)
        self.assertEqual(len(looked), 8)
        self.assertLessEqual(set(kit.load("plan-review", "gate").policy.HUMAN_FACE_KINDS), set(looked))


if __name__ == "__main__":
    unittest.main()
