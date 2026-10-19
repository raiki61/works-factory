"""tdd_suite を省いた run で用意する TDD の実行器（lib/suitewrite.py。持ち主の決め suite-by-ai。issue #516）の検査。
関数を直に呼び、一時の置き場に始めの記録と取り置きを書くだけ（子のプロセスなし）。

見る物:
- 用意するのは base・tdd_suite が空・欄 suite_written がまだ無い時だけ
- 取り置きが在れば写して照らす印を置き、書き手を起こさない。無ければ材料の文（test_cmd を字のまま）と悲観の印を置く
- #! で始まる本文だけを実行の印つきで置き、ほかは訳を残して置かない
- 照らしは JUnit XML が出て試験が 1 件以上なら通して tdd_suite に結ぶ（終了コードは見ない）。書いた物は通った時だけ取り置き、
  取り置きが通らなければ捨てて書き直しの周を求める。照らし済みの記録は変えない
- 報告の冒頭の句は取り置きを使った・書いた・作れなかったのどれかを言う
"""
import hashlib
import os
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import jsonfile  # noqa: E402
import suitewrite  # noqa: E402

CMD = "make check"
BODY = "#!/bin/sh\nmake check JUNIT=\"$1\"\n"
PASSED = {"exit": 1, "problems": [], "count": 1}


class SuiteWriteCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.folder = self.tmp / "art" / "suite"
        self.keep = self.tmp / "home" / "suites"
        self.file = self.tmp / "art" / "record.json"
        jsonfile.write(self.file, {"run_id": "r", "test_cmd": f"  {CMD}\n", "tdd_suite": ""}, indent=2, parents=True)

    def record(self) -> dict:
        return jsonfile.read_dict(self.file)

    def mark(self) -> dict:
        return self.record()[suitewrite.KEY]

    def kept(self) -> pathlib.Path:
        return self.keep / hashlib.sha256(CMD.encode("utf-8")).hexdigest()

    def put_kept(self, body: str = BODY) -> None:
        self.kept().parent.mkdir(parents=True, exist_ok=True)
        self.kept().write_text(body, encoding="utf-8")

    def prepare(self) -> dict:
        return suitewrite.prepare(self.file, self.folder, self.keep, self.root)

    def written(self) -> None:
        self.assertTrue(self.prepare()["write"])
        self.assertEqual(suitewrite.place(self.file, self.folder, {"made": True, "body": BODY, "why": ""}), {"made": True, "why": ""})

    def test_need_only_for_base_without_suite_and_without_mark(self):
        for mode, suite, marked, want in (("base", "", False, True), ("final", "", False, False), ("base", "x.sh", False, False),
                                          ("base", "", True, False)):
            start = {"tdd_suite": suite, **({suitewrite.KEY: {"ok": False}} if marked else {})}
            with self.subTest(mode=mode, suite=suite, marked=marked):
                self.assertIs(suitewrite.need(start, mode), want)

    def test_prepare_without_a_kept_runner_writes_the_brief_and_a_pessimistic_mark(self):
        cmd = "make check ARGS='`x` ```y```'"
        jsonfile.write(self.file, {**self.record(), "test_cmd": cmd}, indent=2, parents=True)
        got = self.prepare()
        self.assertTrue(got["write"])
        brief = pathlib.Path(got["brief_file"]).read_text(encoding="utf-8")
        self.assertIn(f"````text\n{cmd}\n````", brief)
        self.assertIn(f"{suitewrite.declared_checks.DECL_NAME}: 無い", brief)
        self.assertEqual(self.mark(), {"from": suitewrite.FROM_AI, "path": "", "ok": False, "why": suitewrite.NO_REPLY,
                                       "dropped": "", "stored": False})
        self.assertEqual(self.record()["tdd_suite"], "")

    def test_prepare_uses_the_kept_runner_for_the_same_test_cmd_without_the_writer(self):
        """鍵は test_cmd の前後の空白を除いた字。写しは run の置き場の中で、照らす前は tdd_suite に結ばない"""
        self.put_kept()
        self.assertEqual(self.prepare(), {"write": False, "brief_file": ""})
        runner = self.folder / suitewrite.RUNNER
        self.assertEqual(runner.read_text(encoding="utf-8"), BODY)
        self.assertTrue(os.access(runner, os.X_OK))
        self.assertEqual((self.mark()["from"], self.mark()["ok"]), (suitewrite.FROM_KEEP, None))
        self.assertEqual(suitewrite.pending(self.file), str(runner.resolve()))
        self.assertEqual(self.record()["tdd_suite"], "")
        self.assertFalse((self.folder / suitewrite.BRIEF).exists())

    def test_prepare_does_not_reuse_without_a_test_cmd_or_a_keep(self):
        self.put_kept()
        for test_cmd, keep in (("", self.keep), (CMD, None)):
            with self.subTest(test_cmd=test_cmd, keep=keep):
                jsonfile.write(self.file, {"run_id": "r", "test_cmd": test_cmd, "tdd_suite": ""}, indent=2, parents=True)
                self.assertTrue(suitewrite.prepare(self.file, self.folder, keep, self.root)["write"])

    def test_prepare_does_nothing_with_a_named_suite(self):
        jsonfile.write(self.file, {"run_id": "r", "test_cmd": CMD, "tdd_suite": "run-tests.sh"}, indent=2, parents=True)
        self.assertEqual(self.prepare(), {"write": False, "brief_file": ""})
        self.assertNotIn(suitewrite.KEY, self.record())
        self.assertFalse(self.folder.exists())

    def test_place_puts_an_executable_runner_to_check(self):
        self.written()
        runner = self.folder / suitewrite.RUNNER
        self.assertEqual(runner.read_text(encoding="utf-8"), BODY)
        self.assertTrue(os.access(runner, os.X_OK))
        self.assertEqual((self.mark()["path"], self.mark()["ok"]), (str(runner.resolve()), None))
        self.assertEqual(self.record()["tdd_suite"], "", "照らす前は結ばない")

    def test_place_keeps_nothing_when_not_made(self):
        for reply, why in (({"made": False, "body": "", "why": "CI の定義が無い"}, "CI の定義が無い"),
                           ({"made": True, "body": "make check\n", "why": ""}, suitewrite.NO_SHEBANG),
                           ({"made": False, "body": "", "why": ""}, suitewrite.NO_WHY),
                           (None, suitewrite.NO_REPLY)):
            with self.subTest(why=why):
                jsonfile.write(self.file, {"run_id": "r", "test_cmd": CMD, "tdd_suite": ""}, indent=2, parents=True)
                self.prepare()
                self.assertEqual(suitewrite.place(self.file, self.folder, reply), {"made": False, "why": why})
                self.assertEqual((self.mark()["ok"], self.mark()["why"], self.mark()["path"]), (False, why, ""))
                self.assertFalse((self.folder / suitewrite.RUNNER).exists())
                self.assertEqual(suitewrite.pending(self.file), "")

    def test_settle_binds_and_keeps_a_written_runner_with_cases_whatever_its_exit(self):
        self.written()
        self.assertEqual(suitewrite.settle(self.file, PASSED, self.keep), {"done": True, "ok": True, "why": ""})
        runner = str((self.folder / suitewrite.RUNNER).resolve())
        self.assertEqual((self.record()["tdd_suite"], self.mark()["ok"], self.mark()["stored"]), (runner, True, True))
        self.assertEqual(self.kept().read_text(encoding="utf-8"), BODY)
        self.assertTrue(os.access(self.kept(), os.X_OK))

    def test_settle_drops_a_written_runner_without_xml_or_cases_and_keeps_nothing(self):
        problem = "テストの実行器が JUnit XML を書かなかった（exit 2。ログ x）"
        for ran, why in ((None, suitewrite.NOT_RUN), ({"exit": 2, "problems": [problem], "count": None}, problem),
                         ({"exit": 0, "problems": [], "count": 0}, suitewrite.NO_CASES)):
            with self.subTest(why=why):
                jsonfile.write(self.file, {"run_id": "r", "test_cmd": CMD, "tdd_suite": ""}, indent=2, parents=True)
                self.written()
                self.assertEqual(suitewrite.settle(self.file, ran, self.keep), {"done": True, "ok": False, "why": why})
                self.assertEqual((self.record()["tdd_suite"], self.mark()["ok"], self.mark()["why"]), ("", False, why))
                self.assertFalse(self.kept().exists())

    def test_kept_runner_that_fails_is_dropped_and_rewritten(self):
        """取り置きが照らしを通らなければ捨て（done: false）、次の周は書き手を起こし、書き直した物が通れば取り置き直す"""
        self.put_kept("#!/bin/sh\nexit 0\n")
        self.prepare()
        got = suitewrite.settle(self.file, {"exit": 0, "problems": [], "count": 0}, self.keep)
        self.assertEqual(got, {"done": False, "ok": False, "why": suitewrite.NO_CASES})
        self.assertFalse(self.kept().exists())
        self.assertEqual(self.record()["tdd_suite"], "")
        self.written()
        self.assertEqual(self.mark()["dropped"], suitewrite.NO_CASES)
        self.assertTrue(suitewrite.settle(self.file, PASSED, self.keep)["ok"])
        self.assertEqual(self.kept().read_text(encoding="utf-8"), BODY)
        self.assertIn(suitewrite.NO_CASES, suitewrite.head_note(self.record()))

    def test_drop_leaves_a_kept_runner_another_run_replaced(self):
        self.put_kept("#!/bin/sh\nold\n")
        self.prepare()
        self.put_kept()
        suitewrite.settle(self.file, None, self.keep)
        self.assertEqual(self.kept().read_text(encoding="utf-8"), BODY)

    def test_settle_leaves_a_settled_mark_alone(self):
        self.prepare()
        before = self.record()
        self.assertEqual(suitewrite.settle(self.file, PASSED, self.keep), {"done": True, "ok": False, "why": suitewrite.NO_REPLY})
        self.assertEqual(self.record(), before)

    def test_head_note_names_kept_written_or_not_made(self):
        def note(**mark):
            return suitewrite.head_note({suitewrite.KEY: {"from": suitewrite.FROM_AI, "path": "", "ok": True, "why": "", "dropped": "",
                                                          "stored": False, **mark}})
        self.assertTrue(note(**{"from": suitewrite.FROM_KEEP}).startswith(suitewrite.USED))
        self.assertTrue(note().startswith(suitewrite.WROTE))
        self.assertIn("取り置いた", note(stored=True))
        self.assertTrue(note(ok=False, why="w").startswith(f"{suitewrite.NOT_MADE}（w）"))
        self.assertIn(suitewrite.NOT_CHECKED, note(ok=None))
        self.assertEqual(suitewrite.head_note({}), "")


if __name__ == "__main__":
    unittest.main()
