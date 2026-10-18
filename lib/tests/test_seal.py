"""差分の封印と置くかの決まり（lib/seal.py）の検査。

- digest: sha256 の 16 進 64 字
- write_readback: 書いた物の hash を返す。読み戻しが書いた物と違えば SealError（書けたと言わない・前の物も一時ファイルも残る物を変えない）
- diff_files: 差分のバイトに載るファイルと行数。バイナリ・利用者の apply.whitespace=error の設定・読めない差分
- seal_refusal: 緑の認証の指紋が今の木と合う・合わない・認証の指紋が無い
- unknown_row: 守りのパスを確かめられない時の 1 行の頭
- deleted_lines: 取り込むと消えるファイルの行（SHOWN 件までは 1 本ずつ・超える分は件数と封じた差分のパス）
- apply_refusal: 置くかの決まりの 1〜5 を上から順に。通しの答え（approve・continue）なら赤でも・R2 の作り直しのほかの目の阻害でも置く
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import listcut  # noqa: E402
import seal  # noqa: E402
from tests.bin import hermetic  # noqa: E402

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

        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b"earlier")
        with mock.patch.object(pathlib.Path, "write_bytes", write_other), self.assertRaises(seal.SealError):
            seal.write_readback(self.path, b"diff")
        self.assertEqual(self.path.read_bytes(), b"earlier")
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["sealed.diff"])


class DiffFilesCase(unittest.TestCase):
    """一時の git の木で git diff --binary を組み、その差分のバイトを数える"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
        self.git("add", "a.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")

    def git(self, *args) -> bytes:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True, env=hermetic.child_env()).stdout

    def diff(self) -> bytes:
        self.git("add", "-A")
        return self.git("diff", "--cached", "--binary", "HEAD")

    def test_counts_lines_and_binary(self):
        (self.repo / "a.txt").write_text("one\nthree\nfour\n", encoding="utf-8")
        (self.repo / "b.bin").write_bytes(b"\0\1\2")
        self.assertEqual(seal.diff_files(self.repo, self.diff()), {"a.txt": (2, 1), "b.bin": (None, None)})

    def test_user_whitespace_setting_does_not_break_the_count(self):
        (self.repo / "a.txt").write_text("one \ntwo\n", encoding="utf-8")
        data = self.diff()
        strict = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "apply.whitespace", "GIT_CONFIG_VALUE_0": "error"}
        with mock.patch.dict(os.environ, strict):
            self.assertEqual(seal.diff_files(self.repo, data), {"a.txt": (1, 1)})

    def test_unreadable_diff_is_value_error(self):
        with self.assertRaises(ValueError):
            seal.diff_files(self.repo, b"not a diff\n")


class DeletedPathsCase(unittest.TestCase):
    def test_deleted_files_are_named_by_their_real_path(self):
        """取り込むと消えるファイル（deleted file mode の節）のパスは、git が引用した非 ASCII・空白入りの名と中身の無いファイルの
        削除（--- 行が無い）も実の名で読む（simplify F1: 前の写しは diff --git の見出しを " b/" で割り、引用を解かなかった）"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            git = lambda *a: subprocess.run(["git", "-C", tmp, "-c", "user.email=a@b", "-c", "user.name=a", *a],  # noqa: E731
                                            capture_output=True, text=True, check=True, env=hermetic.child_env()).stdout
            git("init", "-q")
            (repo / "d").mkdir()
            names = ["d/日本.txt", "a b.txt", "empty", "kept.txt"]
            for name in names:
                (repo / name).write_text("" if name == "empty" else "x\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-qm", "seed")
            for name in names[:3]:
                (repo / name).unlink()
            (repo / "kept.txt").write_text("y\n", encoding="utf-8")
            self.assertEqual(sorted(seal.deleted_paths(git("diff"))), sorted(names[:3]))


class TouchedPathsCase(unittest.TestCase):
    def test_every_side_of_the_diff_is_touched(self):
        """差分が触るファイルは、変える・足す・消すファイルと、改名の元と先（git の引用した名も実の名で）"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            git = lambda *a: subprocess.run(["git", "-C", tmp, "-c", "user.email=a@b", "-c", "user.name=a", *a],  # noqa: E731
                                            capture_output=True, text=True, check=True, env=hermetic.child_env()).stdout
            git("init", "-q")
            for name in ("changed.py", "gone.py", "old name.py", "kept.py"):
                (repo / name).write_text(f"{name}\n" * 5, encoding="utf-8")
            git("add", "-A")
            git("commit", "-qm", "seed")
            (repo / "changed.py").write_text("y\n", encoding="utf-8")
            (repo / "gone.py").unlink()
            (repo / "old name.py").rename(repo / "新.py")
            (repo / "added.py").write_text("z\n", encoding="utf-8")
            git("add", "-A")
            self.assertEqual(seal.touched_paths(git("diff", "--cached", "-M")),
                             {"changed.py", "gone.py", "old name.py", "新.py", "added.py"})


class DeletedLinesCase(unittest.TestCase):
    def test_lines_cut_past_shown(self):
        """取り込むと消えるファイルの行: SHOWN 件以下なら『取り込むと消えるファイル: <パス>』を全件、超えるなら先頭 SHOWN 件と、
        残りの件数と where（封じた差分の実のパス）を添えた 1 行だけ（行の数は本数に依らない）"""
        self.assertEqual(seal.deleted_lines(["old.py"], where="/run/merge/sealed.diff"), [f"{seal.DELETED_HEAD}: old.py"])
        self.assertEqual(seal.deleted_lines([], where="/run/merge/sealed.diff"), [])
        names = [f"gen/{i}.o" for i in range(20000)]
        got = seal.deleted_lines(names, where="/run/merge/sealed.diff")
        self.assertEqual(len(got), listcut.SHOWN + 1)
        self.assertEqual(got[:listcut.SHOWN], [f"{seal.DELETED_HEAD}: {n}" for n in names[:listcut.SHOWN]])
        self.assertEqual(got[-1], f"{seal.DELETED_HEAD}: ほか 19995 件（全件: /run/merge/sealed.diff）")
        edge = names[:listcut.SHOWN]
        self.assertEqual(seal.deleted_lines(edge, where="x"), [f"{seal.DELETED_HEAD}: {n}" for n in edge])


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

    def test_2_names_both_hashes(self):
        got = refusal(current_hash=OTHER, answer=PASS)
        self.assertIn(HASH, got)
        self.assertIn(OTHER, got)

    def test_3_stop_answer(self):
        self.assertIn("最後の承認ノードで stop と答えた", refusal(answer={"decision": "stop", "text": ""}))

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
        self.assertIn("最後の承認ノードで stop と答えた", got)


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
                self.assertIn("最後の承認ノードで", refusal(answer=answer))

    def test_request_stop_card_refuses(self):
        got = refusal(answer={"decision": "stop", "text": "request: 止めて"})
        self.assertIn("最後の承認ノードで stop と答えた", got)
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


class EyeStatusWordsCase(unittest.TestCase):
    def test_fix_needed_is_a_word_only_r1_says(self):
        self.assertIn("fix-needed", seal.STATUSES)
        self.assertEqual(seal.FIX_NEEDED, "fix-needed")
        self.assertEqual(seal.eye_statuses("r1"), seal.STATUSES)
        rest = {seal.PASSED, seal.REDESIGN, seal.UNVERIFIABLE}
        for eye in ("r2", "r3", "r4"):
            with self.subTest(eye):
                got = seal.eye_statuses(eye)
                self.assertNotIn(seal.FIX_NEEDED, got)
                self.assertEqual(set(got), rest)
        self.assertEqual(set(seal.STATUS_WORDS), set(seal.STATUSES))
        self.assertNotEqual(seal.STATUS_WORDS[seal.FIX_NEEDED], seal.STATUS_WORDS[seal.REDESIGN])


class ApplyNoAnswerCase(unittest.TestCase):
    def test_each_unchecked_fact_refuses(self):
        for over, word in (({"green_ok": False}, "緑でない"), ({"eyes_ok": False}, "目が通していない"),
                           ({"fingerprint_ok": False}, "指紋"),
                           ({"protected": ["lib/protect.py（+1 −0）: 規則 checker"]}, "守りのパス")):
            with self.subTest(word):
                got = refusal(**over)
                self.assertIn("人の通しの答えが無いのに", got)
                self.assertIn(word, got)

    def test_unknown_protected_row_refuses_as_unverified_not_hit(self):
        got = refusal(protected=[seal.unknown_row("一覧が読めない")])
        self.assertIn("守りのパスを確かめられない", got)
        self.assertNotIn("当たった", got)

    def test_hit_and_unknown_are_named_apart(self):
        got = refusal(protected=["lib/protect.py（+1 −0）: 規則 checker", seal.unknown_row("一覧が読めない")])
        self.assertIn("守りのパスに当たった（1 行）", got)
        self.assertIn("守りのパスを確かめられない", got)


if __name__ == "__main__":
    unittest.main()
