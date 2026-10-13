"""役の節を回す共通の口（.shared/core/rolekit.py。P1 計画 Task 13）の検査（FAST: git・盤面の再生・子のプロセスを使わない）。

- render_prompt: 頭の行（前の拒否の理由のファイルのパス）→ head → engine と同じ描き方の本文 → schema の断り、の順で
  今の周の作業ファイル prompt-<節>.md に書く。理由の文そのものは本文に無い（R44）
- accept_role: 拒否ごとに reject-take_<節>-<連番>.txt と控えの行、GIVE_UP_AFTER 回目で done・give_up（R50）
- script_main・main_accept の終了コード（予定の状態は 0 の 1 行、配線の誤りは 2 で標準出力は空）
- 写しが残っていない: works の中で script_main・parse_reply・render_prompt を定義し Renderer を呼ぶのは rolekit だけ（AST）
実物の盤面での描画（本線の p2.fix_plan・p2.plan_review）は test_blk_plan（HEAVY）、rejudge.render の本文の一致は test_rejudge が見る。
盤面はここでは小さな偽物（rolekit が触る欄だけ）で、entry の口は mock で差し替える。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import rolekit  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()


class ScriptMainCase(Base):
    def test_parse_reply(self):
        self.assertEqual(rolekit.parse_reply('{"a": 1}'), ({"a": 1}, ""))
        self.assertIsNone(rolekit.parse_reply("{x")[0])
        self.assertIn("オブジェクトでない", rolekit.parse_reply("[1]")[1])


class PointedLangLineCase(Base):
    """#367: 始めの記録の指し札の字から言語の 1 行を組む 1 か所。指し札が読めない時は落ちずに既定の言語の 1 行に訳を添える"""

    def test_reads_the_pointed_record(self):
        path = self.tmp / "start.json"
        path.write_text(json.dumps({"lang": "English"}), encoding="utf-8")
        self.assertEqual(rolekit.pointed_lang_line("札", lambda raw: path), rolekit.lang_line({"lang": "English"}))
        self.assertEqual(rolekit.pointed_lang_line("", lambda raw: None), rolekit.lang_line({}))

    def test_unreadable_pointer_degrades(self):
        for error in (ValueError("ほかの run"), TypeError("t"), AttributeError("a"), KeyError("k")):
            def locate(raw, error=error):
                raise error
            with self.subTest(type(error).__name__):
                got = rolekit.pointed_lang_line("札", locate)
                self.assertTrue(got.startswith(rolekit.lang_line({})), got)
                self.assertIn(rolekit.POINTER_UNREAD, got)


class GivenUpCase(Base):
    def test_count_and_at_once_give_up_lines(self):
        """回数で諦めた時と出し直させずに諦めた時（with_done の give_up）で、諦めの 1 行の文が分かれる"""
        for _ in range(2):
            rolekit.with_done(self.tmp, "a", {"ok": False, "reason": "欠け"}, give_up_after=3)
        self.assertEqual(rolekit.given_up_reason(self.tmp, "a", give_up_after=3), "")
        rolekit.with_done(self.tmp, "a", {"ok": False, "reason": "欠け\n2 行目"}, give_up_after=3)
        self.assertEqual(rolekit.given_up_reason(self.tmp, "a", give_up_after=3),
                         "a の返答が 3 回とも受け付けで拒まれた（最後の拒否: 欠け 2 行目）")
        out = rolekit.with_done(self.tmp, "b", {"ok": False, "reason": "無い"}, give_up=True)
        self.assertTrue(out["done"])
        self.assertEqual(rolekit.given_up_reason(self.tmp, "b"), "b の返答を受け付けが出し直させずに諦めた（拒否: 無い）")


class RejectWordsCase(unittest.TestCase):
    def test_no_board_done_in_lib(self):
        """役に返る拒みの文は「出し直せ」と言う（works-factory に盤面の命令 done は無い。古い「直して done し直す」を残さない）"""
        hits = [f"{p.name}:{n}" for p in sorted(LIB.glob("*.py"))
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if "done し直す" in line]
        self.assertEqual(hits, [])
class RejectLedgerCase(Base):
    def test_attempt_counts_the_kept_rejects(self):
        """輪の今の回は控え rejects-<名>.json の拒否の数 + 1。控えはファイルなので、同じ置き場で数え直さない。通った返答は積まない"""
        self.assertEqual(rolekit.attempt(self.tmp, "eye"), 1)
        for n in range(1, rolekit.GIVE_UP_AFTER + 1):
            got = rolekit.with_done(self.tmp, "eye", {"ok": False, "reason": f"拒否 {n}"})
            self.assertEqual((got["done"], rolekit.attempt(self.tmp, "eye")), (n == rolekit.GIVE_UP_AFTER, n + 1))
        self.assertTrue(rolekit.with_done(self.tmp, "other", {"ok": True})["done"])
        self.assertEqual(rolekit.attempt(self.tmp, "other"), 1)
        self.assertIn(f"拒否 {rolekit.GIVE_UP_AFTER}", rolekit.given_up_reason(self.tmp, "eye"))

    def test_reject_file_carries_every_reject_oldest_first(self):
        """次の回の役が名指すファイルに輪の拒否の全部が古い順に在る（#345）。報告の最後の拒否の読み
        （last_reject）はそのファイルを最後の拒否と取り違えない"""
        self.assertEqual(rolekit.reject_file(self.tmp, "plan"), "")
        for n in (1, 2):
            rolekit.with_done(self.tmp, "plan", {"ok": False, "reason": f"拒否 {n}\n2 行目"})
        path = pathlib.Path(rolekit.reject_file(self.tmp, "plan"))
        self.assertEqual(path.name, "rejects-plan.md")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text, rolekit.rejects_text(["拒否 1\n2 行目", "拒否 2\n2 行目"]) + "\n")
        self.assertLess(text.index("1 回目の拒否:\n拒否 1"), text.index("2 回目の拒否:\n拒否 2"))
        self.assertEqual(rolekit.last_reject(self.tmp), "拒否 2 2 行目")
        pasted = rolekit.with_reject("本文", rolekit.rejects_text(rolekit.rejected(self.tmp, "plan")))
        self.assertIn("拒否 1", pasted, "道具ゼロの役に貼る文も全部")


if __name__ == "__main__":
    unittest.main()
