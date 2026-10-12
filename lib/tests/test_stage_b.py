"""直しの後の実測（段 B。lib/stage_b.py の run）の試験。

場の出どころ: 今の works（2aa7c66c）の works/tests/test_blk_structure.py:633-720 の AfterCase。元はブロックの script を走らせて
after.json を読んだ。ここは run を直に呼び、返る after.json の中身を見る（書き出しは eyes の structure-after の節。
tests/workflows/test_eyes.py）。元の「実行基盤の写しを数えない」試験は、写しの頭を引数 skip_prefix で受ける形に替えたので、
test_runtime_copy_is_not_measured の名で持つ。元の test_after_stage_keeps_first_eye_rows は、
構造の目の 1 度目の行と同じ置き場に書いた元の形の試験で、段 B の run の外なので持ってこない
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import stage_b  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402

RUNTIME_COPY = ".runner/"
MAP = ("# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n\n"
       "### `halt` 止め札\n\n- 状態: 住処あり\n- 住処: `src/halt.py`\n")
TABLE = {"exclude": ["docs/**"], "concepts": {
    "outcome": {"status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"",
                                                 "allowed": ["src/report.py"], "known": {}}]},
    "halt": {"status": "住処あり", "fences": [{"what": "止め札", "pattern": "\"STOP\"", "allowed": ["src/halt.py"],
                                              "known": {}}]}}}


class AfterCase(unittest.TestCase):
    """始めの版と今の作業ツリーの差分を測る（柵の表が在れば知る場所の増え・新しい名・増えた写しの塊）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)

    def write(self, repo, rel, text):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def target(self, with_table=True):
        repo = self.tmp / "target"
        repo.mkdir()
        git(repo, "init", "-q")
        self.write(repo, "src/report.py", 'OUT = "round_limit"\n')
        self.write(repo, "src/edge.py", 'x = "round_limit"\n')
        self.write(repo, "src/halt.py", 'S = "STOP"\n')
        self.write(repo, "POLICY.md", "決まり: 結末の語は report.py だけが持つ\n")
        self.write(repo, "AGENTS.md", "# 対象の決まり\n\n層は下へだけ依存する\n")
        if with_table:
            self.write(repo, "docs/concepts.md", MAP)
            self.write(repo, "docs/concepts.json", json.dumps(TABLE, ensure_ascii=False))
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "c0")
        return repo

    def after(self, repo, base):
        return stage_b.run(repo, base, skip_prefix=RUNTIME_COPY)

    def test_after_stage_counts_real_diff(self):
        repo = self.target()
        base = git(repo, "rev-parse", "HEAD")
        self.write(repo, "src/edge.py", 'x = "round_limit"\ny = "round_limit"\nNEW_KNOB_NAME = 1\n')   # 住処の外に 1 行・新しい名
        self.write(repo, "src/fresh.py", 'z = "round_limit"\n')                                            # 追跡前の新しいファイル
        self.write(repo, "src/report.py", 'OUT = "round_limit"\nOTHER = "round_limit"\n')                 # 住処の中は数えない
        got = self.after(repo, base)
        self.assertEqual(got["status"], "ok", got)
        self.assertEqual(sorted((f["path"], f["before"], f["after"]) for f in got["fence_up"]),
                         [("src/edge.py", 1, 2), ("src/fresh.py", 0, 1)])
        self.assertIn("NEW_KNOB_NAME", [n["name"] for n in got["new_names"]])
        self.assertEqual(got["tables"], ["docs/concepts.json"])
        self.assertEqual(git(repo, "status", "--porcelain", "--untracked-files=no").count("\n") + 1, 2)   # 対象の index を動かさない

    def test_no_table_reports_only(self):
        """表の無い対象は柵を数えない（fence_up は空。作らない）が、差分の実測は出す"""
        repo = self.target(with_table=False)
        base = git(repo, "rev-parse", "HEAD")
        self.write(repo, "src/edge.py", 'x = "round_limit"\ny = "round_limit"\n')
        got = self.after(repo, base)
        self.assertEqual((got["status"], got["fence_up"], got["tables"]), ("ok", [], []))
        self.assertEqual(got["changed"], ["src/edge.py"])
        self.assertFalse((repo / "docs").exists())

    def test_non_utf8_diff_is_measured(self):
        repo = self.target()
        base = git(repo, "rev-parse", "HEAD")
        (repo / "src" / "latin.txt").write_bytes("caf\xe9 round_limit\n".encode("latin-1"))
        self.write(repo, "src/edge.py", 'x = "round_limit"\ny = "round_limit"\n')
        got = self.after(repo, base)
        self.assertEqual(got["status"], "ok", got)
        self.assertIn("src/latin.txt", got["changed"])
        self.assertEqual([f["path"] for f in got["fence_up"]], ["src/edge.py"])

    def test_runtime_copy_is_not_measured(self):
        """run の作業ツリーに置かれた実行基盤の写し（未追跡）は直しの差分に数えない"""
        repo = self.target()
        base = git(repo, "rev-parse", "HEAD")
        self.write(repo, RUNTIME_COPY + "workflows/x/src/y.py", 'z = "round_limit"\n')
        got = self.after(repo, base)
        self.assertEqual((got["changed"], got["fence_up"]), ([], []))

    def test_table_widened_by_fix_still_counts(self):
        """直しが柵の表の知ってよい所を広げても、数えは直しの前の版の表で行い、表が変わったことを名指す"""
        repo = self.target()
        base = git(repo, "rev-parse", "HEAD")
        wide = json.loads(json.dumps(TABLE))
        wide["concepts"]["outcome"]["fences"][0]["allowed"].append("src/edge.py")
        self.write(repo, "docs/concepts.json", json.dumps(wide, ensure_ascii=False))
        self.write(repo, "src/edge.py", 'x = "round_limit"\ny = "round_limit"\n')
        got = self.after(repo, base)
        self.assertEqual([f["path"] for f in got["fence_up"]], ["src/edge.py"])
        self.assertEqual(got["tables_changed"], ["docs/concepts.json"])

    def test_unknown_base_does_not_stop_the_line(self):
        got = self.after(self.target(), "0" * 40)
        self.assertEqual(got["status"], "failed")
        self.assertTrue(got["reason"].strip())


if __name__ == "__main__":
    unittest.main()
