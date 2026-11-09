"""事前審査の block の形 text（方針の文だけ）の試験（docs/design/plan-review.md の 7 節・9.4・12 節・15.3）。

script（intake → text_prep → 台本の返答 → text_accept → finish）を子のプロセスで回す。指示の字は照らさない（値が md の印に
渡ることは workflows/.shared/prompt.py の emit が全体に照らす）。受け付けは作業ツリー・穴の行ごとの照らし・返答の全体を見て、
rolekit.GIVE_UP_AFTER 回目で諦める。
"""
import unittest

from tests.blocks import kit
from tests.blocks.plan_review import values as V

textform = kit.load("plan-review", "textform")
files = textform.files
import rolekit   # noqa: E402  lib/


def face(key, kind="contract_drift", severity="block", **extra) -> dict:
    """方針の文の審査の穴の行（unit_keys を持たない）"""
    return {"key": key, "kind": kind, "where": "workflows/merge/scripts/pr_commit.py hook_env",
            "why": f"{key} の穴になる筋道を 20 字以上で書いた行", "severity": severity, "reach": "breaks_fix", **extra}


def reply(*faces, **extra) -> dict:
    out = {"faces": list(faces), "shrink": [], "reason": V.REASON}
    if not faces:
        out["faces_none"] = V.FACES_NONE
    return {**out, **extra}


class _Case(unittest.TestCase):
    def setUp(self):
        self.r = V.Block(self)

    def intake(self, **inputs) -> dict:
        got = self.r.intake(**{"proposal": V.POLICY_TEXT, "purpose": V.PURPOSE, **inputs})
        self.assertEqual((got["due"], got["form"]), (True, "text"), got)
        return got

    def accept(self, doc) -> dict:
        raw = doc if isinstance(doc, str) else V.dump(doc)
        return self.r.script("text_accept", reply=raw, status_guarded="true")


class TextAcceptCase(_Case):
    def setUp(self):
        super().setUp()
        self.intake(recorded=V.dump([{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}]))
        self.r.script("text_prep")

    def rejected(self, doc, want: str) -> dict:
        got = self.accept(doc)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(want, got["reason"])
        self.assertFalse((self.r.artifacts / files.REVIEW).exists())
        return got

    def test_pass_writes_the_review(self):
        """通れば review.json に {faces, shrink, reason}。出口は ok で、報告の頭の行と block の穴の行"""
        got = self.accept(reply(face("hook-env-drift-block")))
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (True, True, False), got)
        saved = self.r.read(files.REVIEW)
        self.assertEqual([f["key"] for f in saved["faces"]], ["hook-env-drift-block"])
        self.assertEqual(saved["reason"], V.REASON)
        out = self.r.script("finish")
        self.assertEqual((out["ok"], out["status"], out["form"], out["pass"], out["asks"]), (True, "ok", "text", None, []))
        self.assertEqual(out["report"][0], "事前審査（方針の文）: 穴 1 件（block 1）・別案 0 件")
        self.assertTrue(out["report"][1].startswith("- [contract_drift] hook-env-drift-block: "), out["report"])

    def test_policy_face_must_name_a_recorded_row(self):
        """kind policy の穴は記録された方針の行を名指す（名指さなければ拒む。名指せば通る）"""
        self.rejected(reply(face("policy-unnamed-face", kind="policy", severity="suggest")), "policy")
        got = self.accept(reply(face("policy-named-face", kind="policy", severity="suggest", decided_by="q-mean-empty")))
        self.assertTrue(got["ok"], got)

    def test_policy_doc_fence_needs_a_policy_document(self):
        """方針の文書の無い run で fences に policy_doc を立てた穴は拒む"""
        self.rejected(reply(face("fenced-without-doc", fences=["policy_doc"])), "policy_doc")

    def test_entrance_needs_no_add(self):
        self.rejected(reply(face("entrance-without-no-add", kind="entrance")), "no_add")
        got = self.accept(reply(face("entrance-with-no-add", kind="entrance", no_add="柵を足さずに 2 つの入口を 1 つの口にまとめる形")))
        self.assertTrue(got["ok"], got)

    def test_fences_twice_rejected(self):
        self.rejected(reply(face("fences-twice-face", fences=["irreversible", "irreversible"])), "fences")

    def test_keys_once(self):
        doc = reply(face("same-key-twice-face"))
        doc["shrink"] = [{"key": "same-key-twice-face", "alternative": "柵を足さずに今の口 1 つで閉じる形にする",
                          "why": "口を増やさないので次の周の入口の指摘にならない"}]
        self.rejected(doc, "key が重複")

    def test_faces_none_needed_without_holes(self):
        self.rejected({"faces": [], "shrink": [], "reason": V.REASON, "faces_none": "無い"}, "faces_none")
        self.assertTrue(self.accept(reply())["ok"])

    def test_read_only_tree_changed_rejected(self):
        """役が作業ツリーを変えた返答は拒む"""
        (self.r.repo / "stray.txt").write_text("役が足した\n", encoding="utf-8")
        self.rejected(reply(), "読むだけの役が作業ツリーを変えた")

    def test_give_up_on_the_third_reject(self):
        """rolekit.GIVE_UP_AFTER 回目の拒否で done・give_up。review.json は受け付けが書かず、出口が gave_up と諦めの訳"""
        bad = reply(face("entrance-without-no-add", kind="entrance"))
        for _ in range(rolekit.GIVE_UP_AFTER - 1):
            self.rejected(bad, "no_add")
        got = self.accept(bad)
        self.assertEqual((got["ok"], got["done"], got["give_up"]), (False, True, True), got)
        out = self.r.script("finish")
        self.assertEqual((out["ok"], out["status"]), (False, "gave_up"))
        self.assertIn("no_add", out["reason"])
        self.assertTrue(out["report"][0].startswith("事前審査: "), out["report"])


class ProposalFileCase(_Case):
    """入力 proposal_file（方針の文のファイル。docs/design/spec-driven.md の 2.5 の詰まった所の 2 の行き先）"""

    def put(self, text: str) -> str:
        path = self.r.artifacts / "proposal.md"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_file_is_read_as_the_policy_text(self):
        """在るファイルの中身を、JSON の形でも方針の文として読む（入力 proposal の「在るファイルは JSON」の読みは変えない）"""
        text = '{"plan": []}\n\n設計書の本文\n'
        got = self.r.intake(proposal_file=self.put(text), purpose=V.PURPOSE)
        self.assertEqual((got["due"], got["form"]), (True, "text"), got)
        self.assertEqual(self.r.read(files.INTAKE)["proposal_text"], text.strip())

    def test_proposal_and_proposal_file_together_are_refused(self):
        got = self.r.intake(proposal=V.POLICY_TEXT, proposal_file=self.put("x"), purpose=V.PURPOSE)
        self.assertFalse(got["due"])
        self.assertIn("proposal_file", got["reason"])

    def test_neither_is_refused(self):
        got = self.r.intake(purpose=V.PURPOSE)
        self.assertFalse(got["due"])
        self.assertIn("審査する物が空", got["reason"])
