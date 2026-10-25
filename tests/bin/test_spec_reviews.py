"""起動の殻が、会話で回した審査の記録を Archon の run の記録と照らす所（bin/_lib/specreviews.py と、表を読む bin/_lib/spec-inputs.py。
docs/design/spec-driven.md の 2.6 の 2 の a〜f）。

Archon の記録は、`workflow get <run> --json` の形（workflow_name・status・outcome・metadata.inputs・terminal_record の returns と
artifacts.root）を試験が組んで渡す。表は一時のフォルダに置き、spec-inputs.py はこの過程の Python で読む（殻は uv で起こす）。
殻の起動を通した道（表を名指さない起動は表も記録も読まない・uv が無ければ止まる・照らした結果が run の設定の層に載る）は
tests/bin/test_launcher.py。
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest

import sys

from bin._lib import specreviews
from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))   # lib のモジュールは互いを名で import する（lib/tests と同じ足し方）

import spectable  # noqa: E402
_spec = importlib.util.spec_from_file_location("spec_inputs", ROOT / "bin" / "_lib" / "spec-inputs.py")
spec_inputs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spec_inputs)

DESIGN = "# 設計書\n\n- 何の話か: 置き場。\n- 決めたこと: 1 つ読む。\n\n## 背景\n\n今はホーム。\n"
TABLE = """design: docs/d.md
purpose: 置き場が思う所
acceptance:
  - {key: a1, when: 起こす, then: 置く}
reviews:
""" + "".join(f"  - {{part: {p}, run: r{n}, findings: []}}\n" for n, p in enumerate(spectable.PARTS))


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "d.md").write_text(DESIGN, encoding="utf-8")
        (self.root / "t.yaml").write_text(TABLE, encoding="utf-8")
        self.artifacts = self.root / "runs"

    def built(self) -> dict:
        return spec_inputs.build(self.root, "t.yaml")

    def world_rows(self, request=None, edit=None, name="world") -> dict:
        """世界の解の行のファイルを置き、それを指す返す値 {rows: pointer}。行は request（既定は今の表から組んだ依頼の行）の行ごとに
        1 つで、edit(rows) が返す並びに差し替えられる"""
        request = self.built()["inputs"][spectable.WORLD]["request"] if request is None else request
        rows = [{"finding": n, "where": r["where"], "class_id": f"c{n}", "problem": "置き場", "activity": "設計", "practice": "1 つ読む",
                 "sources": [], "applies": "置き場の決め", "not_applies": "", "basis": "knowledge",
                 "versus": {"proposed": "1 つ読む", "verdict": "same", "challenge": ""}} for n, r in enumerate(request, 1)]
        rows = edit(rows) if edit else rows
        (self.artifacts / name).mkdir(parents=True, exist_ok=True)
        (self.artifacts / name / "world.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return {"rows": {"type": "archon_artifact", "run_id": "x", "path": f"{name}/world.jsonl"}}

    def record(self, part, *, inputs=None, value=None, **over) -> dict:
        """部品の run の記録（workflow get の形）。入力は今の表から組んだ物、返りは ok（世界の解は依頼の行ごとに 1 行の行のファイル）"""
        got = self.built()
        named = {name: spectable.input_text(v) for name, v in got["inputs"][part].items()}
        if part == spectable.PLAN_REVIEW:
            named["proposal_file"] = str(self.root / "gone" / f"spec-proposal-{got['proposal_sha256']}.md")   # 会話の後に消えた一時のファイル
        if part == spectable.WORLD and value is None:
            value = self.world_rows()
        ret = {"ok": True, **(value or {})}
        return {"workflow_name": part, "status": "completed", "outcome": "succeeded",
                "metadata": {"inputs": named if inputs is None else inputs},
                "terminal_record": {"returns": {"availability": "available", "node_id": "finish", "value": ret},
                                    "artifacts": {"root": str(self.artifacts)}}, **over}

    def records(self, **over) -> dict:
        return {f"r{n}": over[p] if p in over else self.record(p) for n, p in enumerate(spectable.PARTS)}

    def check(self, records) -> dict:
        return specreviews.check(self.root, "t.yaml", lambda root, table: spec_inputs.build(root, table), records.get)


class CheckCase(Base):
    def test_matching_records_pass(self):
        doc = self.check(self.records())
        self.assertEqual(specreviews.problems(doc), [])
        self.assertEqual([r["ok"] for r in doc["rows"]], [True] * 5)
        self.assertEqual(doc["table_sha256"], spectable.sha256(TABLE))

    def test_a_missing_record(self):
        records = self.records()
        del records["r1"]
        self.assertIn("a: run r1 の記録が無い", specreviews.problems(self.check(records))[0])

    def test_b_other_workflow(self):
        bad = self.record(spectable.INDEPENDENT_DESIGN, workflow_name="works-factory-purpose")
        self.assertIn("b: 記録の部品の名が works-factory-purpose", specreviews.problems(self.check(self.records(**{spectable.INDEPENDENT_DESIGN: bad})))[0])

    def test_c_not_succeeded(self):
        bad = self.record(spectable.PREMISES, value={"ok": False})
        self.assertIn("c: 記録が成功で終わっていない", specreviews.problems(self.check(self.records(**{spectable.PREMISES: bad})))[0])

    def test_d_inputs_of_another_version(self):
        """d: 審査した後に仕様が変わった（組んだ入力と記録の入力が違う）。名指したほかの入力（web など）は比べない"""
        part = spectable.WORLD
        named = {name: spectable.input_text(v) for name, v in self.built()["inputs"][part].items()}
        ok = self.record(part, inputs={**named, "web": "on", "lang": "ja"})
        self.assertEqual(specreviews.problems(self.check(self.records(**{part: ok}))), [])
        bad = self.record(part, inputs={**named, "purpose": "前の目的"})
        self.assertIn("d: 入力 purpose が", specreviews.problems(self.check(self.records(**{part: bad})))[0])

    def test_d_json_inputs_are_compared_as_values(self):
        part = spectable.PREMISES
        rows = self.built()["inputs"][part]["request"]
        spaced = self.record(part, inputs={"request": json.dumps(rows, ensure_ascii=False, indent=2)})
        self.assertEqual(specreviews.problems(self.check(self.records(**{part: spaced}))), [])

    def test_d_plan_review_needs_the_proposal_file_of_this_version(self):
        """計画の審査は、方針の文を spec-inputs.py が書いたファイル（中身の sha256 を名に持つ）で受けた記録だけを通す。ファイルが
        残っていれば中身も照らす。字の proposal で受けた記録は通さない"""
        part = spectable.PLAN_REVIEW
        purpose = self.built()["inputs"][part]["purpose"]
        sha = self.built()["proposal_sha256"]
        for named, why in ((f"/x/spec-proposal-{'0' * 64}.md", "前の版の名"), ("/x/proposal.md", "名に sha256 が無い")):
            bad = self.record(part, inputs={"purpose": purpose, "proposal_file": named})
            with self.subTest(why):
                self.assertIn("d: 方針の文が", specreviews.problems(self.check(self.records(**{part: bad})))[0])
        kept = spec_inputs.build(self.root, "t.yaml", str(self.root))["args"][part][-1].split("=", 1)[1]
        ok = self.record(part, inputs={"purpose": purpose, "proposal_file": kept})
        self.assertEqual(specreviews.problems(self.check(self.records(**{part: ok}))), [])
        pathlib.Path(kept).write_text("書き換えた字", encoding="utf-8")
        self.assertIn("d: 方針の文が", specreviews.problems(self.check(self.records(**{part: ok})))[0])
        inline = self.record(part, inputs={"purpose": purpose, "proposal": "字"})
        self.assertIn("d: 方針の文が", specreviews.problems(self.check(self.records(**{part: inline})))[0])
        self.assertTrue(sha)

    def test_e_findings_must_hold_every_counted_finding(self):
        """e: 計画の審査の faces の key と、世界の解の differs の class_id は、どれも findings に在る"""
        (self.artifacts / "pr").mkdir(parents=True)
        (self.artifacts / "pr" / "review.json").write_text(json.dumps({"faces": [{"key": "k1"}, {"key": "k2"}]}), encoding="utf-8")
        ptr = {"type": "archon_artifact", "run_id": "x"}
        differs = self.world_rows(edit=lambda rows: [{**rows[0], "versus": {**rows[0]["versus"], "verdict": "differs"}}, *rows[1:]])
        records = self.records(**{
            spectable.PLAN_REVIEW: self.record(spectable.PLAN_REVIEW, value={"holes": {**ptr, "path": "pr/review.json"}}),
            spectable.WORLD: self.record(spectable.WORLD, value=differs)})
        got = specreviews.problems(self.check(records))
        self.assertEqual(len(got), 2, got)
        self.assertIn("返す値の指摘 k1・k2 が findings に無い", got[0])
        self.assertIn("返す値の指摘 c1 が findings に無い", got[1])
        accepted = TABLE.replace("{part: works-factory-plan-review, run: r0, findings: []}",
                                 "{part: works-factory-plan-review, run: r0, findings: [{key: k1, text: t, handling: accepted, owner_words: よい},"
                                 " {key: k2, text: t, handling: accepted, owner_words: よい}]}")
        (self.root / "t.yaml").write_text(accepted, encoding="utf-8")
        got = specreviews.problems(self.check(records))
        self.assertEqual(len(got), 1, "findings を書き足しても組む入力は変わらない（reviews は組む字に入れない）。残るのは世界の解の c1")
        self.assertIn("c1", got[0])

    def test_e_pointer_without_a_root_or_outside_it_is_unreadable(self):
        """e: 返す値に指摘のファイルの pointer が在るのに、記録の置き場の根（terminal_record.artifacts.root）が無い・空か、pointer が根の
        外を指す時は、指摘を 0 件と読まずに読めない訳で止める（bin/_lib/apply.py の同じ場面と同じ向き）"""
        ptr = {"type": "archon_artifact", "run_id": "x", "path": "pr/review.json"}
        rootless = self.record(spectable.PLAN_REVIEW, value={"holes": ptr})
        rootless["terminal_record"]["artifacts"]["root"] = None
        got = specreviews.problems(self.check(self.records(**{spectable.PLAN_REVIEW: rootless})))
        self.assertEqual(len(got), 1, got)
        self.assertIn("e: 返す値の指摘のファイルを読めない", got[0])
        self.assertIn("artifacts.root", got[0])
        (self.root / "outside.json").write_text(json.dumps({"faces": []}), encoding="utf-8")
        outside = self.record(spectable.PLAN_REVIEW, value={"holes": {**ptr, "path": "../outside.json"}})
        got = specreviews.problems(self.check(self.records(**{spectable.PLAN_REVIEW: outside})))
        self.assertEqual(len(got), 1, got)
        self.assertIn("置き場の外", got[0])

    def test_e_premises_contradicts_and_prior_conflicts_are_findings(self):
        """e: 前提の実測の contradicts の在る行（premises-<行の番号>）と前の決めの確かめの conflicts の行（prior-<行の番号>）も、
        findings に在る key でなければ合わない"""
        (self.artifacts / "p").mkdir(parents=True)
        (self.artifacts / "p" / "premises.json").write_text(json.dumps({"constraints": [
            {"text": "a", "measured_how": "b", "kind": "仮説"}, {"text": "c", "measured_how": "d", "kind": "仮説", "contradicts": "docs/d.md"}]},
            ensure_ascii=False), encoding="utf-8")
        (self.artifacts / "d").mkdir()
        (self.artifacts / "d" / "material.json").write_text(json.dumps({"reply": {"conflicts": [
            {"decision": "x", "where": "docs/d.md", "why": "y"}]}}, ensure_ascii=False), encoding="utf-8")
        ptr = {"type": "archon_artifact", "run_id": "x"}
        records = self.records(**{
            spectable.PREMISES: self.record(spectable.PREMISES, value={"constraints": {**ptr, "path": "p/premises.json"}}),
            spectable.PRIOR_DECISIONS: self.record(spectable.PRIOR_DECISIONS, value={"material": {**ptr, "path": "d/material.json"}})})
        got = specreviews.problems(self.check(records))
        self.assertEqual(len(got), 2, got)
        self.assertIn("返す値の指摘 premises-2 が findings に無い", got[0])
        self.assertIn("返す値の指摘 prior-1 が findings に無い", got[1])

    def test_f_world_rows_answer_every_request_line_once(self):
        """f: 世界の解の行は、今の表から組んだ依頼の行（頭の設計の行と全部の受け入れの行）の行ごとに 1 つずつ在り、where がその行の
        where。欠け・重なり・余分な行・違う where・行のファイルの無い返りは、ok の記録でも合わない（入力が合い指摘が全部受け入れ済みでも、
        全部の行を審査した証拠にならない）。未評価の行は形の照らしが e で止める（test_e_returned_files_off_the_declared_shape_are_unreadable）"""
        part = spectable.WORLD
        self.assertEqual(len(self.built()["inputs"][part]["request"]), 2, "頭の設計の行と受け入れの行 a1")
        cases = (
            ("欠け", lambda rows: rows[:1], "f: 依頼の行 2 に世界の解の行が無い"),
            ("重なり", lambda rows: [*rows, rows[1]], "f: 依頼の行 2 に世界の解の行が 2 つ在る"),
            ("余分な行", lambda rows: [*rows, {**rows[1], "finding": 3}], "f: 依頼の行に無い番号 3 の世界の解の行が在る"),
            ("違う where", lambda rows: [rows[0], {**rows[1], "where": "t.yaml#zz"}], "f: 依頼の行 2 の世界の解の行の where が t.yaml#zz"),
        )
        for why, edit, want in cases:
            with self.subTest(why):
                bad = self.record(part, value=self.world_rows(edit=edit, name=why))
                got = specreviews.problems(self.check(self.records(**{part: bad})))
                self.assertEqual(len(got), 1, got)
                self.assertIn(want, got[0])
        rowless = self.record(part, value={"rows": None})
        self.assertIn("f: 世界の解の返す値に行のファイルが無い", specreviews.problems(self.check(self.records(**{part: rowless})))[0])
        self.assertEqual(specreviews.problems(self.check(self.records())), [], "依頼の行ごとに 1 行の記録は通る")

    def test_f_unreadable_world_rows_stop_once_in_e(self):
        """世界の解の行のファイルが読めない時は e の読めない訳 1 つで止まり、f は同じ訳を重ねない（黙って通る道は無い）"""
        part = spectable.WORLD
        broken = self.world_rows(name="broken")
        (self.artifacts / "broken" / "world.jsonl").write_text("{読めない\n", encoding="utf-8")
        got = specreviews.problems(self.check(self.records(**{part: self.record(part, value=broken)})))
        self.assertEqual(len(got), 1, got)
        self.assertIn("e: 返す値の指摘のファイルを読めない", got[0])
        self.assertNotIn("f:", got[0])

    def test_e_returned_files_off_the_declared_shape_are_unreadable(self):
        """e: 返す値の指す先の中身は、部品の返す節が宣言した form の形（RETURN_READS）で照らしてから読む。形に合わない中身
        （世界の解の未評価の行・欄の欠けた行・型の違う穴の key）は、指摘を数えずに読めない訳で止める（#851 の落ちるはずの所の 10 番）"""
        part = spectable.WORLD
        cases = (
            ("未評価", lambda rows: [rows[0], {**rows[1], "versus": {**rows[1]["versus"], "verdict": ""}}]),
            ("欄の欠け", lambda rows: [rows[0], {k: v for k, v in rows[1].items() if k != "class_id"}]),
        )
        for why, edit in cases:
            with self.subTest(why):
                bad = self.record(part, value=self.world_rows(edit=edit, name=why))
                got = specreviews.problems(self.check(self.records(**{part: bad})))
                self.assertEqual(len(got), 1, got)
                self.assertIn("e: 返す値の指摘のファイルを読めない", got[0])
                self.assertIn("jsonl(lib:world-row.schema.json) の形に合わない", got[0])
                self.assertNotIn("f:", got[0])
        (self.artifacts / "pr").mkdir(parents=True)
        (self.artifacts / "pr" / "review.json").write_text(json.dumps({"faces": [{"key": 1}]}), encoding="utf-8")
        holes = self.record(spectable.PLAN_REVIEW, value={"holes": {"type": "archon_artifact", "run_id": "x", "path": "pr/review.json"}})
        got = specreviews.problems(self.check(self.records(**{spectable.PLAN_REVIEW: holes})))
        self.assertEqual(len(got), 1, got)
        self.assertIn("json(shared:plan-review-reply.schema.json) の形に合わない", got[0])

    def test_f_a_split_helper_run_is_not_the_official_review(self):
        """依頼の行の一部だけを入力に回した補助の run（分けた run）は、その一部の行に全部答えていても、公式の全入力の審査として
        通らない（d で入力が違い、f で残りの行が欠ける）"""
        part = spectable.WORLD
        built = self.built()["inputs"][part]
        head = built["request"][:1]
        helper = self.record(part, inputs={"request": spectable.input_text(head), "purpose": built["purpose"]},
                             value=self.world_rows(request=head, name="helper"))
        got = specreviews.problems(self.check(self.records(**{part: helper})))
        self.assertEqual(len(got), 1, got)
        self.assertIn("d: 入力 request が", got[0])
        self.assertIn("f: 依頼の行 2 に世界の解の行が無い", got[0])

    def test_table_problems_stop_without_reading_records(self):
        (self.root / "t.yaml").write_text("purpose: x\n", encoding="utf-8")
        doc = specreviews.check(self.root, "t.yaml", lambda root, table: spec_inputs.build(root, table), lambda run: self.fail(run))
        self.assertEqual(doc["rows"], [])
        self.assertTrue(specreviews.problems(doc))


class PlumbingCase(Base):
    def test_named_table(self):
        self.assertEqual(specreviews.named_table("works-factory-line", ["request=x", "spec_table=t.yaml"]), "t.yaml")
        self.assertEqual(specreviews.named_table("works-factory-spec-driven", ["mode=entry", "table=t.yaml"]), "t.yaml")
        self.assertIsNone(specreviews.named_table("works-factory-line", ["request=x", "spec_table="]))
        self.assertIsNone(specreviews.named_table("works-factory-line", ["table=t.yaml"]))
        self.assertIsNone(specreviews.named_table("works-factory-world", ["table=t.yaml"]))
        self.assertIsNone(specreviews.named_table(None, ["spec_table=t.yaml"]))

    def test_the_env_name_is_the_one_the_block_reads(self):
        self.assertEqual(specreviews.RESULT_ENV, kit.load("spec-driven", "files").REVIEWS_ENV)

    def test_write_names_the_file_by_its_content(self):
        doc = self.check(self.records())
        path = specreviews.write(self.root / "home", doc)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), doc)
        self.assertEqual(specreviews.write(self.root / "home", doc), path)

    def test_inputs_script_writes_the_proposal_and_its_args(self):
        got = spec_inputs.build(self.root, "t.yaml", str(self.root))
        out = self.root / f"spec-proposal-{got['proposal_sha256']}.md"
        self.assertEqual(spectable.sha256(out.read_text(encoding="utf-8")), got["proposal_sha256"])
        self.assertIn(f"proposal_file={out}", got["args"][spectable.PLAN_REVIEW])
        self.assertIn("entry=仕様を固める会話（docs/d.md と t.yaml）", got["args"][spectable.PRIOR_DECISIONS])


if __name__ == "__main__":
    unittest.main()
