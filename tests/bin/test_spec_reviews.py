"""起動の殻が、会話で回した審査の記録を Archon の run の記録と照らす所（bin/_lib/specreviews.py と、表を読む bin/_lib/spec-inputs.py。
docs/design/spec-driven.md の 2.6 の 2 の a〜e）。

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

    def record(self, part, *, inputs=None, value=None, **over) -> dict:
        """部品の run の記録（workflow get の形）。入力は今の表から組んだ物、返りは ok"""
        got = self.built()
        named = {name: spectable.input_text(v) for name, v in got["inputs"][part].items()}
        if part == spectable.PLAN_REVIEW:
            named["proposal_file"] = str(self.root / "gone" / f"spec-proposal-{got['proposal_sha256']}.md")   # 会話の後に消えた一時のファイル
        ret = {"ok": True, **(value or {})}
        return {"workflow_name": part, "status": "completed", "outcome": "succeeded",
                "metadata": {"inputs": named if inputs is None else inputs},
                "terminal_record": {"returns": {"availability": "available", "node_id": "finish", "value": ret},
                                    "artifacts": {"root": str(self.artifacts)}}, **over}

    def records(self, **over) -> dict:
        return {f"r{n}": over.get(p, self.record(p)) for n, p in enumerate(spectable.PARTS)}

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
        (self.artifacts / "w").mkdir()
        (self.artifacts / "w" / "world.jsonl").write_text(
            json.dumps({"class_id": "c1", "versus": {"verdict": "differs"}}) + "\n"
            + json.dumps({"class_id": "c2", "versus": {"verdict": "same"}}) + "\n", encoding="utf-8")
        ptr = {"type": "archon_artifact", "run_id": "x"}
        records = self.records(**{
            spectable.PLAN_REVIEW: self.record(spectable.PLAN_REVIEW, value={"holes": {**ptr, "path": "pr/review.json"}}),
            spectable.WORLD: self.record(spectable.WORLD, value={"rows": {**ptr, "path": "w/world.jsonl"}})})
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
