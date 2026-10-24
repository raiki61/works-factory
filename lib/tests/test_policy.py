"""人の方針を役に届ける形（policy）。写しから組む brief が上限 PASTE_CAP（listcut.FILE_CAP と同じ値）で本文を切ること。
節の文は共通の断片 workflows/.shared/prompts/policy.md（integration.md 4.5-4(c)）"""
import hashlib
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
import gatemarks  # noqa: E402
import policy  # noqa: E402
import listcut  # noqa: E402
from tests.bin import hermetic  # noqa: E402


class BriefCapCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pol = pathlib.Path(tmp.name) / "policy.md"

    def test_paste_cap_is_the_listcut_cap(self):
        self.assertEqual(policy.PASTE_CAP, listcut.FILE_CAP)

    def test_brief_cuts_the_body_at_the_paste_cap_and_names_the_rest(self):
        """上限を越えた方針は先頭だけを貼り、続きの置き場を書く（貼った本文は上限の内）"""
        self.pol.write_bytes(("- 決まり\n" * 6000).encode("utf-8") + "TAIL-MARK".encode("utf-8"))
        body = policy.brief({"policy_md": str(self.pol)})["paste"]
        self.assertLessEqual(len(body.encode("utf-8")), policy.PASTE_CAP)
        self.assertNotIn("TAIL-MARK", body)
        self.assertIn(f"{policy.PASTE_CAP} バイトまでを貼った。続きは {self.pol}", body)


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
        self.assertIn(policy.POLICY_KIND, policy.HUMAN_FACE_KINDS)
        self.assertIn(policy.POLICY_KIND, gatemarks.KIND_WORDS)


if __name__ == "__main__":
    unittest.main()


class RecordedCase(unittest.TestCase):
    """記録された方針の一覧（issue #427）: 4 つの出どころの行・名指しの照らし・事前審査の受け付けが拒む穴（役に貼る節の文は共通の断片）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        pol = self.tmp / "policy.md"
        pol.write_text("# 方針\n- 公開の口を減らさない\n", encoding="utf-8")
        self.frozen = policy.freeze(self.tmp / "run", self.tmp, str(pol))
        self.start = {"policy": self.frozen, "answers": [{"question": "q-mean-empty", "text": "空の列は例外"}, {"question": ""}]}
        self.decisions = self.tmp / "judge" / "material-prior-decisions.json"
        self.decisions.parent.mkdir()
        settled = [{"topic": "公開の口", "decision": "減らさない", "where": "docs/adr/0002.md"},
                   {"topic": "where の無い論点", "decision": "決めた"}, "壊れた行"]
        self.decisions.write_text(
            json.dumps({"role": "prior-decisions", "reply": {"settled": settled}}, ensure_ascii=False), encoding="utf-8")
        self.human = [{"note": "通す"}, {"note": ""}, {"note": "名前を残す"}]
        self.rows = policy.recorded(self.start, self.decisions, human_items=self.human)
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
