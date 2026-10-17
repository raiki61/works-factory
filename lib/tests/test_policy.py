"""人の方針を役に届ける形（policy）。盤面の写しから組む brief と、盤面の無いブロックが貼る節 section が同じ上限で本文を切ること
（元 works/.shared/core/gl-prompts/prompts/policy-paste.md・policy.md）"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import boardview  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import judge_accept  # noqa: E402
import policy  # noqa: E402
from engine.render import MATERIAL_NOTE  # noqa: E402
from tests.bin import hermetic  # noqa: E402


class SectionCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pol = pathlib.Path(tmp.name) / "policy.md"

    def test_section_carries_preface_material_and_rule_only_when_present(self):
        self.pol.write_text("- 公開の口を減らさない\n", encoding="utf-8")
        got = policy.section(self.pol)
        self.assertTrue(got.startswith(f"{policy.HEAD}\n\n{policy.PREFACE}{MATERIAL_NOTE}\n"), got)
        self.assertIn("- 公開の口を減らさない", got)
        self.assertTrue(got.endswith(policy.RULE))
        self.assertIn("自分の判断で通すな", policy.RULE)
        self.assertEqual(policy.section(""), "")
        self.assertEqual(policy.section(self.pol.parent / "無い.md"), "")

    def test_section_cuts_the_body_at_the_paste_cap_and_names_the_rest(self):
        """上限を越えた方針は先頭だけを貼り、続きの置き場を書く（貼った本文は上限の内。brief と同じ切り方）"""
        self.pol.write_bytes(("- 決まり\n" * 6000).encode("utf-8") + "TAIL-MARK".encode("utf-8"))
        got = policy.section(self.pol)
        body = got.split(f"{MATERIAL_NOTE}\n", 1)[1].rsplit(f"\n{MATERIAL_NOTE}", 1)[0]
        self.assertLessEqual(len(body.encode("utf-8")), policy.PASTE_CAP)
        self.assertNotIn("TAIL-MARK", got)
        self.assertIn(f"{policy.PASTE_CAP} バイトまでを貼った。続きは {self.pol}", body)
        self.assertEqual(body, policy.brief({"policy_md": str(self.pol)})["paste"])
        self.assertTrue(got.endswith(policy.RULE))


class FreezeCase(unittest.TestCase):
    """run の始めに 1 度だけ固める版 {named, path, sha256, copy}（元 graphloops/rules/policy_input.py の locate・snapshot）と、
    ブロックが読む写し frozen_copy"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo, self.run = self.tmp / "repo", self.tmp / "run"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, env=hermetic.child_env())

    def assert_copied(self, got, named, path, body: bytes):
        sha = hashlib.sha256(body).hexdigest()
        self.assertEqual((got["named"], got["path"], got["sha256"]), (named, path, sha))
        self.assertEqual(pathlib.Path(got["copy"]), self.run / policy.DIR / f"{sha}.md")
        self.assertEqual(pathlib.Path(got["copy"]).read_bytes(), body)

    def test_freeze_named_default_and_absent(self):
        self.assertEqual(policy.freeze(self.run, self.repo, ""), {"named": "", "path": "", "sha256": None, "copy": None})
        default = self.repo / ".git" / "graphloops" / "policy.md"
        default.parent.mkdir(parents=True)
        default.write_bytes("- 既定の置き場の方針\n".encode("utf-8"))
        self.assert_copied(policy.freeze(self.run, self.repo, ""), "", str(default.resolve()), default.read_bytes())
        named = self.tmp / "named.md"
        named.write_bytes("- 名指した方針\n".encode("utf-8"))
        self.assert_copied(policy.freeze(self.run, self.repo, str(named)), str(named), str(named), named.read_bytes())

    def test_version_reads_back_what_freeze_writes(self):
        """書く側（freeze）と読む側（version）の欄が合う。合わないと version が None を返し、frozen_copy が黙って生の policy_md に戻る"""
        named = self.tmp / "named.md"
        named.write_text("- 名指した方針\n", encoding="utf-8")
        for doc in (str(named), ""):
            with self.subTest(named=doc):
                frozen = policy.freeze(self.run, self.repo, doc)
                self.assertEqual(policy.version({"policy": frozen}), frozen)

    def test_frozen_copy_reads_the_version_and_falls_back_to_policy_md(self):
        """欄 policy の在る記録は写し copy（文書が無い版は空）、欄の無い・壊れた記録は今どおり policy_md"""
        frozen = {"named": "/p.md", "path": "/p.md", "sha256": "a" * 64, "copy": "/run/policy/a.md"}
        self.assertEqual(policy.frozen_copy({"policy_md": "/p.md", "policy": frozen}), "/run/policy/a.md")
        self.assertEqual(policy.frozen_copy({"policy_md": "/p.md", "policy": {**frozen, "sha256": None, "copy": None}}), "")
        for start in ({"policy_md": "/p.md"}, {"policy_md": "/p.md", "policy": "壊れた"},
                      {"policy_md": "/p.md", "policy": {"copy": 3}}):
            with self.subTest(start=start):
                self.assertEqual(policy.frozen_copy(start), "/p.md")
        self.assertEqual(policy.frozen_copy(None), "")


class NameOwnerCase(unittest.TestCase):
    """#454: 方針の 3 つの名（決定記録の突合の返答のファイル名・方針の文書の柵の語・方針の穴の kind）は policy が持ち、使う部品は
    ここから引く。どちらか片方だけを替えると赤（policy の PRIOR_DECISIONS_FILE だけを替えると役の名が変わり、
    tests/workflows/test_judge.py の YAML の節 id との突き合わせが赤）"""

    def test_fence_word_is_a_gatemarks_fence(self):
        self.assertIn(policy.POLICY_DOC_FENCE, gatemarks.FENCES)
        face = {"key": "f", "kind": "regression", "where": "a.py", "fences": [policy.POLICY_DOC_FENCE]}
        self.assertEqual(len(policy.face_gaps([face], [])), 1)

    def test_policy_kind_is_a_human_face_kind(self):
        self.assertIn(policy.POLICY_KIND, fixboard.HUMAN_FACE_KINDS)
        self.assertIs(boardview.HUMAN_FACE_KINDS, fixboard.HUMAN_FACE_KINDS)
        self.assertIn(policy.POLICY_KIND, gatemarks.KIND_WORDS)

    def test_prior_decisions_file_is_the_material_file_of_its_role(self):
        self.assertEqual(judge_accept.material_file(judge_accept.PRIOR_DECISIONS_ROLE), policy.PRIOR_DECISIONS_FILE)
        self.assertIn(judge_accept.PRIOR_DECISIONS_ROLE, judge_accept.MATERIAL_ROLES)


if __name__ == "__main__":
    unittest.main()


class RecordedCase(unittest.TestCase):
    """記録された方針の一覧（issue #427）: 4 つの出どころの行・名指しの照らし・事前審査の受け付けが拒む穴・役に貼るセクション"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        pol = self.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        self.frozen = policy.freeze(self.tmp / "run", self.tmp, str(pol))
        self.start = {"policy": self.frozen, "answers": [{"question": "q-mean-empty", "text": "空の列は例外"}, {"question": ""}]}
        self.jdir = self.tmp / "judge"
        self.jdir.mkdir()
        settled = [{"topic": "公開の口", "decision": "減らさない", "where": "docs/adr/0002.md"},
                   {"topic": "where の無い論点", "decision": "決めた"}, "壊れた行"]
        (self.jdir / policy.PRIOR_DECISIONS_FILE).write_text(
            json.dumps({"role": "prior-decisions", "reply": {"settled": settled}}, ensure_ascii=False), encoding="utf-8")
        self.human = [{"note": "通す"}, {"note": ""}, {"note": "名前を残す"}]
        self.rows = policy.recorded(self.start, self.jdir, human_items=self.human)
        self.gates = [r["name"] for r in self.rows if r["source"] == "gate"]

    def test_rows_of_the_four_sources(self):
        """note の無い承認ノードの答えは数えない。where の無い論点と question の空の答えは名指しにならない。決定記録の突合の返答の
        dict でない行は読まない"""
        self.assertEqual([(r["source"], r["name"]) for r in self.rows], [
            ("doc", self.frozen["copy"]), ("answer", "q-mean-empty"), ("gate", self.gates[0]),
            ("gate", self.gates[1]), ("settled", "docs/adr/0002.md"), ("settled", "")])
        self.assertEqual((self.rows[0]["lines"], self.rows[0]["alias"]), (2, self.frozen["path"]))
        self.assertEqual([r["source"] for r in policy.recorded(self.start)], ["doc", "answer"])

    def test_gate_name_follows_the_answer_not_its_place_in_the_list(self):
        """#427: plan-review は修正前の承認ノードの答えを積み、eyes は最後の答えだけを持つ。同じ答えはどちらの並びでも同じ名指し"""
        latest = [h["name"] for h in policy.recorded({}, human_items=[{"note": "名前を残す"}])]
        self.assertEqual(latest, [self.gates[1]])
        self.assertTrue(self.gates[0].startswith("承認ノードの答え ") and self.gates[0] != self.gates[1], self.gates)

    def test_hits_name_rows_literally(self):
        copy, path = self.frozen["copy"], self.frozen["path"]
        for text, want in ((f"{copy}:2", [copy]), (f"{path}:1", [copy]), (f"{copy}:3", []), (f"{copy}:0", []),
                           ("q-mean-empty の答え", ["q-mean-empty"]), ("docs/adr/0002.md の節", ["docs/adr/0002.md"]),
                           (self.gates[0], [self.gates[0]]), (self.gates[0] + "0", []),
                           ("tests/calibration/seed/test_stats.py:1", [])):
            with self.subTest(text=text):
                self.assertEqual(policy.hits(self.rows, text), want)

    def test_face_gaps_refuse_unrecorded_policy_and_policy_doc_without_doc(self):
        docstring = {"key": "seed", "kind": "policy", "where": "tests/calibration/seed/test_stats.py:1", "decided_by": "test_stats.py:1"}
        fenced = {"key": "fenced", "kind": "regression", "where": "stats.py", "fences": ["policy_doc"]}
        named = {"key": "named", "kind": "policy", "where": "stats.py", "decided_by": "q-mean-empty"}
        no_doc = policy.recorded({"answers": self.start["answers"]})
        got = policy.face_gaps([docstring, fenced, named], no_doc)
        self.assertEqual(len(got), 2, got)
        self.assertTrue(got[0].startswith("faces[0]（seed）") and policy.RECORDED_TERM + "に無い" in got[0], got)
        self.assertTrue(got[1].startswith("faces[1]（fenced）") and "policy_doc" in got[1], got)
        self.assertEqual(policy.face_gaps([fenced, named], self.rows), [])

    @staticmethod
    def example_faces(text) -> list:
        return [{"key": "example", **json.loads(x)} for x in text.splitlines() if x.startswith("{")]

    def test_face_example_passes_face_gaps_for_each_source(self):
        """出どころごとの 1 行だけの一覧から描いた例の JSON の行は、policy.face_gaps を通る。方針の文書の行が在る時だけ policy_doc の句が
        載る。lines=0 の方針の文書の行（写しが空）は名指しが当たらないので例に採らず、次の名指せる行で描く"""
        by = {s: next(r for r in self.rows if r["source"] == s and r["name"]) for s in ("doc", "answer", "gate", "settled")}
        by["push"] = policy.recorded({}, pushes=["この条件で進める"])[0]
        empty_doc = {"source": "doc", "name": str(self.tmp / "empty.md"), "text": "", "lines": 0, "alias": ""}
        for source, rows, want in (*((s, [r], r["name"] + ":1" if s == "doc" else r["name"]) for s, r in by.items()),
                                   ("empty-doc-then-answer", [empty_doc, by["answer"]], "q-mean-empty")):
            with self.subTest(source):
                text = policy.face_example(rows)
                faces = self.example_faces(text)
                self.assertEqual([f["decided_by"] for f in faces], [want], text)
                self.assertEqual([(f["kind"], f["severity"]) for f in faces], [("policy", "suggest")])
                self.assertEqual(policy.face_gaps(faces, rows), [])
                self.assertEqual(policy.POLICY_DOC_FENCE in text, any(r["source"] == "doc" for r in rows), text)

    def test_face_example_without_names_says_no_policy_face(self):
        """名指せる行が無い一覧（空・where の無い論点だけ・写しが空の方針の文書だけ）では例の JSON を描かず、kind policy の穴は挙げないと
        書く。対象の文を contract_drift で挙げる決まりは RECORDED_RULE・HANDOFF_REVIEW・face_gaps が持ち、ここでは言い直さない"""
        empty_doc = {"source": "doc", "name": str(self.tmp / "empty.md"), "text": "", "lines": 0, "alias": ""}
        for name, rows in (("empty", []), ("settled-without-where", [r for r in self.rows if r["source"] == "settled" and not r["name"]]),
                           ("empty-doc", [empty_doc])):
            with self.subTest(name):
                text = policy.face_example(rows)
                self.assertEqual(self.example_faces(text), [], text)
                self.assertIn(policy.FACE_NONE, text)
                self.assertNotIn("contract_drift", text)

    def test_section_says_none_when_nothing_can_be_named(self):
        got = policy.recorded_text({})
        self.assertTrue(got.startswith(policy.RECORDED_HEAD), got)
        self.assertIn(policy.RECORDED_NONE, got)
        self.assertIn("承認ノードの人の答え: この役には渡っていない", got)
        got = policy.recorded_section(self.rows)
        self.assertNotIn(policy.RECORDED_NONE, got)
        for want in (f"`{self.frozen['copy']}:<行>`（1〜2 行", '`q-mean-empty`', f"`{self.gates[1]}`", '`docs/adr/0002.md`',
                     "（where が無いので名指せない）where の無い論点"):
            self.assertIn(want, got)

    def test_names_copied_from_the_section_hit_their_rows(self):
        """役はセクションの名指しを字のまま写す。引用符・バックスラッシュ・Windows のパスを持つ名も、写した字が一覧に当たる"""
        rows = policy.recorded({"answers": [{"question": 'Use "foo" API?', "text": "使う"}]})
        rows.append({"source": "settled", "name": "C:\\repo\\docs\\adr.md", "text": "決めた"})
        copied = re.findall(r"名指し `([^`]+)`", policy.recorded_section(rows))
        self.assertEqual(copied, [r["name"] for r in rows])
        for name in copied:
            with self.subTest(name):
                self.assertEqual(policy.hits(rows, f"ぶつかる: {name}"), [name])

    def test_text_tells_a_role_without_gate_answers_so(self):
        """承認ノードの答えを入力に持たない役（human_items が None）には「渡っていない」、持つ役には行か「無い」"""
        self.assertIn("承認ノードの人の答え: この役には渡っていない", policy.recorded_text(self.start, self.jdir))
        self.assertIn("承認ノードの人の答え: 無い", policy.recorded_text(self.start, self.jdir, []))
        self.assertIn(f"`{self.gates[0]}`", policy.recorded_text(self.start, self.jdir, self.human))
        self.assertNotIn("docs/adr/0002.md", policy.recorded_text(self.start))
