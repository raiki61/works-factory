"""役の節を回す共通の口（.shared/core/rolekit.py。P1 計画 Task 13）の検査（FAST: git・盤面の再生・子のプロセスを使わない）。

- render_prompt: 頭の行（前の拒否の理由のファイルのパス）→ head → engine と同じ描き方の本文 → schema の断り、の順で
  今の周の作業ファイル prompt-<節>.md に書く。理由の文そのものは本文に無い（R44）
- accept_role: 拒否ごとに reject-take_<節>-<連番>.txt と控えの行、GIVE_UP_AFTER 回目で done・give_up（R50）
- script_main・main_accept の終了コード（予定の状態は 0 の 1 行、配線の誤りは 2 で標準出力は空）
- 写しが残っていない: works の中で script_main・parse_reply・render_prompt を定義し Renderer を呼ぶのは rolekit だけ（AST）
実物の盤面での描画（本線の p2.fix_plan・p2.plan_review）は test_blk_plan（HEAVY）、rejudge.render の本文の一致は test_rejudge が見る。
盤面はここでは小さな偽物（rolekit が触る欄だけ）で、entry の口は mock で差し替える。
"""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

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


class AgentDefCase(unittest.TestCase):
    """agent_def: 写しの plugin（rolekit.AGENTS_PLUGIN）の役は lib の agents/<役>.md から本文を引き、無い役は None。
    置き場の環境変数は呼びの間だけ置く"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {k: v for k, v in os.environ.items() if k != rolekit.env_root(rolekit.AGENTS_PLUGIN)}
        env["CLAUDE_CONFIG_DIR"] = tmp.name   # 利用者の plugin のキャッシュを見ない
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_known_role_returns_its_body(self):
        got = rolekit.agent_def(f"{rolekit.AGENTS_PLUGIN}:judge")
        self.assertIsNotNone(got)
        self.assertEqual(pathlib.Path(got["file"]), LIB / "agents" / "judge.md")
        text = (LIB / "agents" / "judge.md").read_text(encoding="utf-8")
        self.assertEqual(got["body"], text.split("---", 2)[2].strip())
        self.assertTrue(got["body"])
        self.assertEqual(got["model"], "opus")
        self.assertNotIn(rolekit.env_root(rolekit.AGENTS_PLUGIN), os.environ)

    def test_unknown_role_is_none(self):
        self.assertIsNone(rolekit.agent_def(f"{rolekit.AGENTS_PLUGIN}:no-such-role"))
        self.assertIsNone(rolekit.agent_def("no-plugin-role"))
        self.assertNotIn(rolekit.env_root(rolekit.AGENTS_PLUGIN), os.environ)


if __name__ == "__main__":
    unittest.main()
