"""事前審査のブロックだけの見え方（boardview）。open_pass が入力の指し札の先を置き場に写し、見え方の上で今の works の部品
（startrec.read・structmark.read・worldmark.stage_rows・planmarks.read・marks.path_of("gate", b)・converge の控え）が、置いた物を
読むこと。書き先（place）が書いた控えを見え方がそのまま読むこと。写しの rules の書き直し、方針の文書の置き場と変化、関所の答えの
控え、案の直しの項目"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
from lib.tests import test_plan_gate as TP  # noqa: E402
import boardview  # noqa: E402
import converge  # noqa: E402
import gatemarks  # noqa: E402
import marks  # noqa: E402
import planmarks  # noqa: E402
import policy  # noqa: E402
import startrec  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402
from engine.util import Reject  # noqa: E402

UNIT = "stats.py mean: 分母が len(xs) - 1 になっている"
FACES = {"type": "array", "items": {"type": "object"}}
SHRINK = {"type": "array", "items": {"type": "object", "required": ["key"]}}
R2 = {"type": "object", "required": ["question_stands", "reason", "design"],
      "properties": {"question_stands": {"type": "boolean"}, "reason": {"type": "string"}, "design": {"type": "string"}}}
REVIEW = {"type": "object", "properties": {"faces": FACES, "shrink": SHRINK}}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()
        self.src = self.tmp / "src"
        self.folder = self.tmp / "plan-review"

    def put(self, rel, doc, raw=False) -> pathlib.Path:
        p = self.src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if raw else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return p

    def open(self, *, plan_rows=None, fields=None, rnd=2, world=None, start=None, answers=None, ruling=(), structure=None,
             purpose=None, judgment=None, conflicts=None, gate_answers=None):
        rows = plan_rows or [{"unit_keys": [UNIT], "approach": "分母を直す", "adds": [], "removes": [], "shrink_first": "要らない",
                              "narrows": [{**TP.NARROW, **TP.DECIDED}]}]
        self.put("judge/judgment.json", judgment or {"units": [{"key": UNIT, "label": "block"}], "questions": [],
                                                     "framing": "見立て", "one_shot": "一撃", "precedents": []})
        self.put("judge/materials.json", {"parallel_pr": {"status": "not_run", "reason": "網に出られない"}})
        self.put(f"plan/r{rnd}/p2.fix_plan.json", {"plan": rows})
        self.put(f"plan/r{rnd}/plan-fields.json", {"round": rnd, "fields": fields or [{"route": "direct", "structure": []}]})
        self.put("plan/structure-state.json", structure or {"status": "ok", "reason": "", "design_file": "x", "wall_s": 3})
        self.put("plan/design.jsonl", json.dumps(TP.ROUTE_UP, ensure_ascii=False) + "\n", raw=True)
        self.put("plan/ripple.json", {"items": [], "overlaps": []})
        self.put("judge/purpose.json", purpose or {"purpose_text": "目的", "source_files": [], "source": "依頼"})
        return boardview.open_pass(
            self.folder, cwd=self.tmp, judgment=self.src / "judge/judgment.json", purpose=self.src / "judge/purpose.json",
            plan=self.src / f"plan/r{rnd}/plan-fields.json", structure=self.src / "plan/structure-state.json",
            ripple=self.src / "plan/ripple.json", world=world, start=start, answers=answers, ruling=list(ruling),
            conflicts=conflicts, gate_answers=gate_answers, review_schema=REVIEW, design_schema=R2)

    def view(self, review=None):
        return boardview.view(self.folder, boardview.read_open(self.folder), review)


class OpenCase(Base):
    def test_view_reads_what_open_placed(self):
        """始めの記録・構造の目の控え・世界の解の段・修正案の欄・決め手の控えを、今の works の読み口が見え方の上で読む"""
        wf = self.put("judge/world/world.jsonl", json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", raw=True)
        start = self.put("start.json", {"run_id": "r", "base_rev": "abc", "unattended": "true", "design_only": "true"})
        got = self.open(world=wf, start=start)
        self.assertEqual((got["k"], got["form"]), (2, "review"))
        b = self.view()
        self.assertEqual(startrec.read(b.dir)["unattended"], "true")
        self.assertEqual(structmark.read(b.dir)["status"], "ok")
        self.assertEqual(structmark.rows(structmark.read(b.dir)["design_file"]), [TP.ROUTE_UP])
        self.assertEqual(pathlib.Path(structmark.read(b.dir)["design_file"]).parent.parent, self.folder)
        self.assertEqual([r["class_id"] for r in worldmark.stage_rows(b.dir)], ["w-mean"])
        self.assertEqual(planmarks.read(b), [{"route": "direct", "structure": []}])
        self.assertEqual(planmarks.frozen(b), [{"route": "direct", "structure": []}])
        saved = marks.load(marks.path_of("gate", b))
        self.assertEqual(saved[boardview.PLAN_NODE]["marks"][0][0]["decided_by"], TP.DECIDED["decided_by"])
        self.assertNotIn("decided_by", b.output_of_round(boardview.PLAN_NODE, 1)["plan"][0]["narrows"][0])
        self.assertEqual(b.record["materials"]["parallel_pr"]["status"], "not_run")
        self.assertEqual(b.state["inputs"]["review_rev"], "abc")
        self.assertEqual(b.latest_output("p0.purpose")["source"], "依頼")
        self.assertEqual(b.pointer_rows("p2.plan_review")["pointers"][0]["names"], [UNIT])
        self.assertFalse(hasattr(b, "stop"))

    def test_round_is_always_one_and_k_is_the_plan_round(self):
        """見え方と書き先の周はいつも 1（同じ run の往復を 1 つの控えに積む）。差し込みの番号 k は plan-fields.json の round"""
        got = self.open(rnd=3)
        self.assertEqual(got["k"], 3)
        self.assertEqual(json.loads((self.folder / planmarks.FIELDS_FILE).read_text(encoding="utf-8"))["round"], 1)
        self.assertEqual((self.view().round, boardview.place(self.folder).round), (1, 1))

    def test_writer_record_is_read_by_view(self):
        """書き先が積んだ往復の控え（converge）を見え方がそのまま読む。open は案の項目を控えに置く"""
        self.open()
        b = self.view()
        self.assertEqual([it["unit_keys"] for it in converge.read(b)["plan"]], [[UNIT]])
        converge.record_pass(boardview.place(self.folder), {"faces": []}, resolved=[], fence=3, files={})
        self.assertEqual(converge.read(self.view())["outcome"], converge.CLEAN)
        rows = [json.loads(x) for x in (self.folder / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertIn(converge.OP, [r["op"] for r in rows])
        self.assertIn(planmarks.SAVED_OP, [r["op"] for r in rows])

    def test_world_null_removes_the_stage(self):
        wf = self.put("judge/world/world.jsonl", json.dumps(TP.WORLD_ROW, ensure_ascii=False) + "\n", raw=True)
        self.open(world=wf)
        self.assertIsNotNone(worldmark.stage_rows(self.folder))
        self.open(world=None)
        self.assertIsNone(worldmark.stage_rows(self.folder))

    def test_failed_structure_is_kept_failed(self):
        self.open(structure={"status": "failed", "reason": "構造の目が落ちた", "design_file": "", "wall_s": 0})
        self.assertEqual(structmark.read(self.folder)["status"], "failed")
        self.assertEqual(structmark.dirty(self.folder), {})

    def test_replan_form_records_no_pass(self):
        """裁かれた項目が在れば形 replan で、往復を控えに積まない（案の項目の控えは審査する直した案に置き換える）。裁かれた項目は
        番号か項目の id で引く"""
        self.open()
        got = self.open(ruling=[converge.item_id([UNIT])])
        self.assertEqual(got["form"], "replan")
        record = converge.read(self.view())
        self.assertEqual((record["passes"], record["open"]), ([], {}))
        self.assertEqual([it["unit_keys"] for it in record["plan"]], [[UNIT]])
        self.assertEqual(boardview.read_open(self.folder)["ruled"], [1])
        self.open(ruling=["1"])
        self.assertEqual(boardview.read_open(self.folder)["ruled"], [1])

    def test_answers_become_human_items(self):
        self.open(answers={"decision": "approve", "text": "例外のままにする"})
        b = self.view()
        self.assertEqual(b.record["process"]["human_items"],
                         [{"round": 1, "node": "gate-start", "kinds": [], "answer": "approve", "note": "例外のままにする"}])
        self.assertEqual(boardview.human_items(None), [])

    def test_defaults_are_named(self):
        """線が渡さない入力（start・answers が null）は既定で読み、その事実を材料に残す"""
        self.open()
        self.assertEqual(boardview.read_open(self.folder)["defaults"], [boardview.DEFAULT_START, boardview.DEFAULT_ANSWERS])
        start = self.put("start.json", {"run_id": "r"})
        self.open(start=start, answers={"decision": "approve", "text": ""})
        self.assertEqual(boardview.read_open(self.folder)["defaults"], [])

    def test_schemas_are_kept_for_the_later_nodes(self):
        """役の型は差し込みの頭が受けて材料に置き、見え方が事前審査の faces・shrink と独立設計の型を渡す"""
        self.open()
        got = boardview.read_open(self.folder)
        self.assertEqual((got["review_schema"], got["design_schema"]), (REVIEW, R2))
        self.assertEqual(self.view().faces_schema, {"faces": FACES, "shrink": SHRINK})

    def test_r2_due(self):
        """独立設計は、同じ run に設計の控えが無く、諦めていず、目的が使える時だけ回す"""
        self.assertTrue(self.open()["r2_go"])
        (self.folder / "design.json").write_text(json.dumps({"question_stands": True, "reason": "r", "design": "d"}),
                                                 encoding="utf-8")
        self.assertFalse(self.open()["r2_go"])
        (self.folder / "design.json").unlink()
        self.assertFalse(self.open(purpose={"purpose_text": "", "source_files": [], "source": "目的不明"})["r2_go"])
        narrowed = {"units": [], "questions": [], "purpose_review": {"verdict": "狭めている", "findings": [{"cite": "a.md:1"}]}}
        self.assertFalse(self.open(judgment=narrowed)["r2_go"])
        for _ in range(3):
            boardview.rolekit.with_done(self.folder, "r2.design", {"ok": False, "reason": "拒んだ"})
        self.assertFalse(self.open()["r2_go"])

    def test_policy_frozen_on_first_open_and_change_named(self):
        """方針の文書は run の最初の差し込みで固め、後で変わればその事実（固めた版と今の版の写しと差分）を返す"""
        pol = self.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        start = self.put("start.json", {"run_id": "r", "policy_md": str(pol)})
        self.open(start=start)
        first = boardview.read_open(self.folder)["policy_copy"]
        self.assertTrue(pathlib.Path(first).is_file())
        self.assertIsNone(boardview.policy_change(self.folder, self.tmp))
        pol.write_text("# 方針\n- 公開の口を減らさない\n- 足した\n", encoding="utf-8")
        self.open(start=start)
        self.assertEqual(boardview.read_open(self.folder)["policy_copy"], first)
        ch = boardview.policy_change(self.folder, self.tmp)
        self.assertIn("足した", pathlib.Path(ch["diff_file"]).read_text(encoding="utf-8"))
        self.assertIn(str(pol), boardview.change_row(ch))

    def test_missing_open_names_the_error(self):
        self.folder.mkdir(parents=True)
        (self.folder / boardview.OPEN_ERROR).write_text("読めない指し札", encoding="utf-8")
        with self.assertRaises(boardview.Missing) as cm:
            boardview.read_open(self.folder)
        self.assertIn("読めない指し札", str(cm.exception))


class RulesCase(Base):
    def test_plan_review_output(self):
        """元 rules/review-loop.py の plan_review_output: 案に無い単位・重複の key・穴も別案も無いのに faces_none が無い・入口の穴の
        no_add の欠けを拒む（元 tests/test_blk_plan.py の ScriptCase.test_plan_review_entrance_needs_no_add）"""
        self.open()
        b = self.view()
        good = {"faces": [], "shrink": [], "faces_none": "写しと入口と契約のずれを確かめて穴が無い"}
        boardview.rules.plan_review_output(b, "p2.plan_review", good, None)
        face = {"key": "entrance-key", "unit_keys": [UNIT], "kind": "entrance", "where": "stats.py", "why": "w" * 20,
                "severity": "block"}
        for bad, word in (({"faces": [], "shrink": []}, "faces_none"),
                          ({"faces": [face]}, "no_add"),
                          ({"faces": [{**face, "kind": "copy"}, {**face, "kind": "copy"}]}, "重複"),
                          ({"faces": [{**face, "kind": "copy", "unit_keys": ["判定に無い単位"]}]}, "修正案に無い")):
            with self.subTest(word=word):
                with self.assertRaises(Reject) as cm:
                    boardview.rules.plan_review_output(b, "p2.plan_review", bad, None)
                self.assertIn(word, str(cm.exception))
        boardview.rules.plan_review_output(b, "p2.plan_review", {"faces": [{**face, "no_add": "柵を足さずに 2 つの入口を 1 つの口にまとめる形"}]},
                                           None)

    def test_validator_tables(self):
        self.assertEqual(boardview.rules.validator_module(None).ASKING, ("held", "escalate"))
        self.assertTrue(boardview.rules.validator_module(None).STATUS["not_run"].blocks)
        self.assertFalse(boardview.rules.validator_module(None).STATUS["clean"].blocks)
        self.assertLessEqual(set(boardview.BLOCKING), set(gatemarks.MATERIAL_WORDS))

    def test_md_slugs_and_lines(self):
        text = "# 見出し A\n```\n# 囲いの中\n```\n## 見出し A\n"
        self.assertEqual([n for n, _ in boardview.rules._md_lines(text)], [1, 5])
        self.assertEqual(boardview.rules._md_slugs(text), {"見出し-a", "見出し-a-1"})

    def test_unattended_and_tree_words(self):
        self.assertEqual(boardview.tree_word(None), "auto")
        self.assertEqual(boardview.tree_word({"features_on": ["review_tree"]}), "on")
        self.assertEqual(boardview.tree_word({"features_off": ["review_tree"]}), "off")

    def test_review_body_names_the_run_values(self):
        """役の指示書の『リポジトリ: 』の行から末尾を、run の値（対象・読む版・BASE・観点の正本）に置き換え、人の方針の節（在れば）を
        末尾に足して渡す。行が無ければ空"""
        text = "頭\n\nリポジトリ: 材料のファイルが名指す所\n\n## 見ること\n1. 写し\n"
        got = boardview.review_body(text, repo="/r", rev="abc", base="b0", review_md="/lib/REVIEW.md")
        self.assertTrue(got.startswith("\nリポジトリ: /r（読む版: `abc`）　BASE: `b0`　観点の正本: /lib/REVIEW.md\n"), got)
        self.assertIn("## 見ること", got)
        self.assertNotIn("頭", got)
        self.assertNotIn(policy.HEAD, got)
        pol = self.tmp / "policy.md"
        pol.write_text("- 公開の口を減らさない\n", encoding="utf-8")
        got = boardview.review_body(text, repo="/r", rev="abc", base="b0", review_md="m", policy_md=str(pol))
        self.assertTrue(got.endswith(policy.section(pol)), got)
        self.assertEqual(boardview.review_body("リポジトリの行が無い", repo="/r", rev="a", base="a", review_md="m"), "")


class GateCase(Base):
    def test_gate_items_from_view(self):
        """修正案の narrows の決め手は open が gate-marks.json に置いた控えから関所に届く（欄を外した案でも聞かずに通る）"""
        self.open(plan_rows=[{"unit_keys": [UNIT], "narrows": [{**TP.NARROW, **TP.DECIDED}]}])
        b = self.view({"faces": []})
        self.assertEqual(gatemarks.plan_gate_items(b), [("design", gatemarks.design_items(b)[0][1])])
        self.assertEqual([p["by"] for p in gatemarks.passes(b)], [gatemarks.PASSED_BY])



class PolicyCase(Base):
    """人の方針の文書の置き場（名指しか git の共通の置き場の graphloops/policy.md）・固めた版の写しの守り
    （元 works/.shared/core/graphloops/rules/policy_input.py）"""

    def default_doc(self) -> pathlib.Path:
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        doc = self.tmp / ".git" / "graphloops" / "policy.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("- 既定の置き場の方針\n", encoding="utf-8")
        return doc

    def test_default_location_is_read_when_not_named(self):
        doc = self.default_doc()
        self.open(start=self.put("start.json", {"run_id": "r"}))
        got = boardview.read_open(self.folder)
        self.assertEqual(pathlib.Path(got["policy_md"]), doc.resolve())
        self.assertIn("既定の置き場の方針", pathlib.Path(got["policy_copy"]).read_text(encoding="utf-8"))

    def test_document_placed_later_at_the_default_is_a_change(self):
        """固めた時に文書が無くても、後で既定の置き場に置いた文書は変化に数える（元 policy_input.change が locate を引き直す）"""
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        self.open()
        self.assertIsNone(boardview.policy_change(self.folder, self.tmp))
        doc = self.tmp / ".git" / "graphloops" / "policy.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("- 後で置いた\n", encoding="utf-8")
        ch = boardview.policy_change(self.folder, self.tmp)
        self.assertEqual((ch["from"], pathlib.Path(ch["path"])), (None, doc.resolve()))

    def test_lost_frozen_copy_is_named_not_diffed(self):
        """固めた版の写しが消えていれば、空の文と比べた差分を作らず diff_missing を関所の行に名指す"""
        pol = self.tmp / "policy.md"
        pol.write_text("- 前\n", encoding="utf-8")
        start = self.put("start.json", {"run_id": "r", "policy_md": str(pol)})
        self.open(start=start)
        pathlib.Path(boardview.read_open(self.folder)["policy_copy"]).unlink()
        pol.write_text("- 後\n", encoding="utf-8")
        ch = boardview.policy_change(self.folder, self.tmp)
        self.assertEqual((ch["diff_missing"], ch["diff_file"]), (boardview.DIFF_MISSING, None))
        self.assertIn(boardview.DIFF_MISSING, boardview.change_row(ch))


class GateAnswersCase(Base):
    """修正前の関所の答え（入力 gate_answers）を、gatemarks が聞き直さない行として控え、方針の変化を通したら版を固め直す
    （元 works/.shared/core/graphloops/rules/review-loop.py:4134 の human_gate_answered）"""

    def test_continued_rows_are_not_asked_again(self):
        self.open(plan_rows=[{"unit_keys": [UNIT], "narrows": [{**TP.NARROW, **TP.DECIDED}]}])
        asked = gatemarks.plan_gate_items(self.view({"faces": []}))
        self.assertTrue(asked)
        boardview._note_asked(self.folder, asked, None)
        answer = {"decision": "approve", "text": "通す", "asked": [text for _, text in asked]}
        self.open(plan_rows=[{"unit_keys": [UNIT], "narrows": [{**TP.NARROW, **TP.DECIDED}]}], gate_answers=answer)
        b = self.view({"faces": []})
        row = b.record["process"]["human_items"][-1]
        self.assertEqual((row["node"], row["answer"], row["kinds"]), (gatemarks.GATE_NODE, "continue", sorted({k for k, _ in asked})))
        self.assertEqual(gatemarks.plan_gate_items(b), [])
        self.open(gate_answers=answer)
        self.assertEqual(len(json.loads((self.folder / boardview.GATE_ANSWERS_FILE).read_text(encoding="utf-8"))), 1)

    def test_continue_past_policy_change_refreezes(self):
        pol = self.tmp / "policy.md"
        pol.write_text("- 前\n", encoding="utf-8")
        start = self.put("start.json", {"run_id": "r", "policy_md": str(pol)})
        self.open(start=start)
        pol.write_text("- 後\n", encoding="utf-8")
        ch = boardview.policy_change(self.folder, self.tmp)
        row = (boardview.POLICY_CHANGED, boardview.change_row(ch))
        boardview._note_asked(self.folder, [row], ch)
        self.open(start=start, gate_answers={"decision": "stop", "text": "", "asked": [row[1]]})
        self.assertIsNotNone(boardview.policy_change(self.folder, self.tmp))
        self.open(start=start, gate_answers={"decision": "continue", "text": "後の版で進める", "asked": [row[1]]})
        self.assertIsNone(boardview.policy_change(self.folder, self.tmp))
        frozen = json.loads((self.folder / boardview.POLICY_FILE).read_text(encoding="utf-8"))
        self.assertEqual(frozen["sha256"], ch["to"])
        self.assertEqual(frozen["amendments"][0]["note"], "後の版で進める")


class ReplanItemsCase(Base):
    """案の直しの事前審査の材料: 承認済みの前の形を置き場の往復の控えから上書きの前に読み、直した形と申し出・裁定の行と並べる
    （元 works/.shared/core/replan.py:291 の material と :387 の _section）"""

    ROW = {"unit_keys": [UNIT], "approach": "分母を直す", "adds": [], "removes": [], "shrink_first": "要らない",
           "narrows": [{**TP.NARROW, **TP.DECIDED}]}

    def test_old_new_and_rows_per_ruled_item(self):
        self.open(plan_rows=[self.ROW], fields=[{"route": "direct", "structure": [], "allowed_paths": ["stats.py"]}])
        conflicts = self.put("fix/conflicts.json", {"items": [
            {"id": "c1", "unit_key": UNIT, "between": ["案", "試験"], "why_both_cannot_hold": "両方は立たない",
             "kind": "plan", "which_is_right": "test", "ruling": {"decision": "fix_plan_item", "text": "範囲を広げよ"}},
            {"id": "c2", "unit_key": "ほかの単位", "ruling": {"decision": "x", "text": "y"}}]})
        self.open(plan_rows=[{**self.ROW, "approach": "分母を len(xs) にする"}], rnd=3, ruling=["1"], conflicts=conflicts,
                  fields=[{"route": "direct", "structure": [], "allowed_paths": ["stats.py", "test_stats.py"]}])
        got = boardview.read_open(self.folder)["replan_items"]
        self.assertEqual([r["item"] for r in got], [1])
        self.assertEqual((got[0]["old"]["approach"], got[0]["new"]["approach"]), ("分母を直す", "分母を len(xs) にする"))
        self.assertEqual(got[0]["old"]["allowed_paths"], ["stats.py"])
        self.assertEqual(got[0]["new"]["narrows"][0]["decided_by"], TP.DECIDED["decided_by"])
        self.assertEqual([c["id"] for c in got[0]["rows"]], ["c1"])
        section = boardview._replan_section(got[0])
        for word in (boardview.OLD_HEAD, boardview.NEW_HEAD, boardview.ROW_HEAD.format(id="c1"), "範囲を広げよ", "両方は立たない"):
            self.assertIn(word, section)

    def test_no_approved_plan_stops_the_open(self):
        with self.assertRaises(boardview.Missing) as cm:
            self.open(ruling=["1"])
        self.assertIn(boardview.NO_APPROVED, str(cm.exception))


class LibDocsCase(Base):
    def test_cache_is_reused_across_passes(self):
        """ライブラリの文書の控えは置き場（plan-review/）の下に在り、同じ run の次の差し込み（往復）は網に出ずにそれを読む
        （今の works は同じ周の 2 つ目の役が盤面の控えを読んだ。見え方の周はいつも 1）"""
        from lib.tests import test_libdocs as TL
        import libdocs
        repo = self.tmp / "repo"
        repo.mkdir()
        (repo / "app.py").write_text("import requests\n", encoding="utf-8")
        (repo / "requirements.txt").write_text("requests==2.32.3\n", encoding="utf-8")
        self.open()
        libdocs.section(self.view().work(""), repo, ["app.py"], get=TL.ok_http(), env={})
        self.open(rnd=3)
        http = TL.FakeHttp()
        text = libdocs.section(self.view().work(""), repo, ["app.py"], get=http, env={})
        self.assertEqual(http.calls, [])
        self.assertIn("requests", text)


class Owners(unittest.TestCase):
    """欄を持つモジュールは、節と控えの名を住処の表から引く（同じ名を 2 か所で持たない。元 tests/test_marks.py:143 の
    Owners.test_owners_read_the_table のうち、このブロックが使う gatemarks・planmarks・converge・worldmark）"""

    def test_owners_read_the_table(self):
        self.assertEqual((gatemarks.NODES, gatemarks.MARKS_FILE), (marks.nodes("gate"), marks.KINDS["gate"].file))
        self.assertEqual((planmarks.NODES, planmarks.FIELDS_FILE), (marks.nodes("plan"), marks.KINDS["plan"].file))
        self.assertEqual(tuple(converge.FIELDS), marks.nodes("converge"))
        self.assertEqual(worldmark.MEANS_NODES, marks.nodes(worldmark.MEANS))


if __name__ == "__main__":
    unittest.main()
