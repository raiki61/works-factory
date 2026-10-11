"""差分の封印と置くかの決まり（lib/seal.py）の検査。

- digest: sha256 の 16 進 64 字
- write_readback: 書いた物の hash を返す。読み戻しが書いた物と違えば SealError（書けたと言わない）
- seal_refusal: 緑の認証の指紋が今の木と合う・合わない・認証の指紋が無い
- unknown_row: 守りのパスを確かめられない時の 1 行の頭
- apply_refusal: 置くかの決まりの 1〜5 を上から順に。通しの答え（approve・continue）なら赤でも・R2 の作り直しのほかの目の阻害でも置く
"""
import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import seal  # noqa: E402

HASH = hashlib.sha256(b"diff").hexdigest()
OTHER = hashlib.sha256(b"other").hexdigest()
PASS = {"decision": "continue", "text": ""}


def refusal(**over) -> str:
    """答えの無い、全部が緑の run を基にして、over の欄だけ替えた apply_refusal"""
    args = {"sealed_hash": HASH, "current_hash": HASH, "answer": None, "green_ok": True, "eyes_ok": True, "r2": None,
            "fingerprint_ok": True, "protected": []}
    return seal.apply_refusal(**{**args, **over})


class DigestCase(unittest.TestCase):
    def test_sha256_hex(self):
        self.assertEqual(seal.digest(b"diff"), HASH)
        self.assertEqual(len(seal.digest(b"")), 64)


class WriteReadbackCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "merge" / "sealed.diff"

    def test_returns_hash_of_what_was_written(self):
        self.assertEqual(seal.write_readback(self.path, b"diff"), HASH)
        self.assertEqual(self.path.read_bytes(), b"diff")

    def test_readback_mismatch_is_not_a_write(self):
        def write_other(path, data):
            with open(path, "wb") as f:
                f.write(b"changed after the write")
            return len(data)

        with mock.patch.object(pathlib.Path, "write_bytes", write_other), self.assertRaises(seal.SealError):
            seal.write_readback(self.path, b"diff")


class SealRefusalCase(unittest.TestCase):
    FP = {"head": "a" * 40, "diff_hash": HASH}

    def test_matching_fingerprint_seals(self):
        self.assertEqual(seal.seal_refusal(fingerprint=self.FP, fingerprint_ok=True), "")

    def test_unmatched_fingerprint_refuses(self):
        self.assertIn("緑の認証の指紋が今の木と違う", seal.seal_refusal(fingerprint=self.FP, fingerprint_ok=False))

    def test_no_certificate_is_not_compared(self):
        self.assertEqual(seal.seal_refusal(fingerprint=None, fingerprint_ok=False), "")


class UnknownRowCase(unittest.TestCase):
    def test_row_says_the_diff_may_touch_the_list(self):
        row = seal.unknown_row("一覧が読めない")
        self.assertTrue(row.startswith("守りのパスを確かめられない（差分が一覧に触れていないとは言えない）: "))
        self.assertTrue(row.endswith("一覧が読めない"))


class ApplyRefusalOrderCase(unittest.TestCase):
    def test_all_green_without_answer_applies(self):
        self.assertEqual(refusal(), "")

    def test_1_no_sealed_hash(self):
        self.assertIn("封じた hash が無い", refusal(sealed_hash="", current_hash=""))

    def test_2_hash_mismatch(self):
        self.assertIn("封じた差分と今の差分が違う", refusal(current_hash=OTHER, answer=PASS))

    def test_3_stop_answer(self):
        self.assertIn("最後の関所で stop と答えた", refusal(answer={"decision": "stop", "text": ""}))

    def test_4_r2_redesign_even_with_pass(self):
        got = refusal(answer=PASS, r2={"status": seal.REDESIGN, "reason": "別の設計"})
        self.assertIn("R2 が作り直しと言った", got)

    def test_5_no_answer_and_red(self):
        got = refusal(green_ok=False)
        self.assertIn("人の通しの答えが無いのに", got)
        self.assertIn("緑でない", got)

    def test_order_hash_before_answer(self):
        self.assertIn("封じた差分と今の差分が違う", refusal(current_hash=OTHER, answer={"decision": "stop", "text": ""}))

    def test_order_answer_before_r2(self):
        got = refusal(answer={"decision": "stop", "text": ""}, r2={"status": seal.REDESIGN, "reason": ""})
        self.assertIn("最後の関所で stop と答えた", got)


class ApplyAnswerCase(unittest.TestCase):
    def test_pass_words_apply_even_when_red_or_eyes_blocked(self):
        for word in ("approve", "continue"):
            with self.subTest(word=word):
                self.assertEqual(refusal(answer={"decision": word, "text": ""}, green_ok=False, eyes_ok=False,
                                         fingerprint_ok=False, protected=["lib/protect.py（+1 −0）: 規則 checker"]), "")

    def test_pass_applies_with_r1_blocked(self):
        self.assertEqual(refusal(answer=PASS, eyes_ok=False), "")

    def test_non_pass_words_refuse(self):
        for answer in ({"decision": "stop", "text": ""}, {"decision": "reject", "text": ""},
                       {"decision": "hold", "text": ""}, {}):
            with self.subTest(answer=answer):
                self.assertIn("最後の関所で", refusal(answer=answer))

    def test_request_stop_card_refuses(self):
        got = refusal(answer={"decision": "stop", "text": "request: 止めて"})
        self.assertIn("最後の関所で stop と答えた", got)
        self.assertIn("止め札", got)


class ApplyR2Case(unittest.TestCase):
    def test_r2_shapes(self):
        cases = [
            ("省いた R2・目の阻害・通しの答え", {"r2": None, "eyes_ok": False, "answer": PASS}, ""),
            ("unverifiable・通しの答え", {"r2": {"status": "unverifiable", "reason": "落ちた"}, "answer": PASS}, ""),
            ("pass・通しの答え", {"r2": {"status": "pass", "reason": ""}, "answer": PASS}, ""),
            ("redesign-needed・通しの答え", {"r2": {"status": "redesign-needed", "reason": ""}, "answer": PASS},
             "R2 が作り直しと言った"),
            ("答え無し・目の阻害", {"r2": {"status": "unverifiable", "reason": ""}, "eyes_ok": False},
             "人の通しの答えが無いのに"),
        ]
        for name, over, want in cases:
            with self.subTest(name):
                got = refusal(**over)
                if want:
                    self.assertIn(want, got)
                else:
                    self.assertEqual(got, "")


class ApplyNoAnswerCase(unittest.TestCase):
    def test_each_unchecked_fact_refuses(self):
        for over, word in (({"green_ok": False}, "緑でない"), ({"eyes_ok": False}, "目が通していない"),
                           ({"fingerprint_ok": False}, "指紋"),
                           ({"protected": ["lib/protect.py（+1 −0）: 規則 checker"]}, "守りのパス")):
            with self.subTest(word):
                got = refusal(**over)
                self.assertIn("人の通しの答えが無いのに", got)
                self.assertIn(word, got)

    def test_unknown_protected_row_counts_as_hit(self):
        self.assertIn("守りのパス", refusal(protected=[seal.unknown_row("一覧が読めない")]))


if __name__ == "__main__":
    unittest.main()
