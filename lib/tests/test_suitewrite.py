"""tdd_suite を省いた run で用意する TDD の実行器（lib/suitewrite.py。持ち主の決め suite-by-ai。issue #516）の検査。
関数を直に呼び、一時の置き場に始めの記録と取り置きを書くだけ（子のプロセスなし）。

見る物:
- 用意するのは base・tdd_suite が空・欄 suite_written がまだ無い時だけ
- 取り置きが在れば写して照らす印を置き、書き手を起こさない。無ければ材料の文（test_cmd を字のまま）と悲観の印を置く
- #! で始まる本文だけを実行の印つきで置き、ほかは訳を残して置かない
- 照らしは JUnit XML が出て試験が 1 件以上なら通して tdd_suite に結ぶ（終了コードは見ない）。書いた物は通った時だけ取り置き、
  取り置きが通らなければ捨てて書き直しの周を求める。照らし済みの記録は変えない
- 報告の節「2. 止めたか」の知らせの本文（頭は状態ごとの種の文）は、取り置きを使った・書いた・作れなかったのどれかを言う。状態の分け方は note_state の
  1 か所が持ち、括弧の中身は note_detail、head_note はその 2 つと作れなかった時の句 NO_LOOP を組んだ 1 行
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
STAMP, OTHER = "a1", "b2"   # 実行器を書く指示の版（lib は値の中身を知らず、取り置きの名に入れるだけ）


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

    def kept(self, stamp: str | None = STAMP) -> pathlib.Path:
        """版つきの名 <sha256(test_cmd)>.<版>（stamp が None なら版の無い前の形の名）"""
        name = hashlib.sha256(CMD.encode("utf-8")).hexdigest()
        return self.keep / (name if stamp is None else f"{name}.{stamp}")

    def put_kept(self, body: str = BODY, stamp: str | None = STAMP) -> None:
        self.kept(stamp).parent.mkdir(parents=True, exist_ok=True)
        self.kept(stamp).write_text(body, encoding="utf-8")

    def prepare(self, stamp: str = STAMP) -> dict:
        return suitewrite.prepare(self.file, self.folder, self.keep, self.root, stamp=stamp)

    def written(self) -> None:
        self.assertTrue(self.prepare()["write"])
        self.assertEqual(suitewrite.place(self.file, self.folder, {"made": True, "body": BODY, "why": ""}), {"made": True, "why": ""})

    def test_adopt_binds_a_runner_without_running_it_and_keeps_it_only_later(self):
        """直す前の版では試験を走らせない（持ち主の決め base-runs-nothing）: 照らす前の実行器を走らせずに tdd_suite に結び、印は
        checked が偽。取り置きは TDD の輪が走らせて結末が取れた時に keep_runner で置き、壊れていれば drop_runner で捨てる"""
        self.written()
        self.assertEqual(suitewrite.adopt(self.file), {"done": True, "ok": True, "why": ""})
        runner = self.record()["tdd_suite"]
        self.assertTrue(runner)
        self.assertEqual((self.mark()["ok"], self.mark()["checked"], self.mark()["stored"]), (True, False, False))
        self.assertFalse(self.kept().exists())
        self.assertIn(suitewrite.UNCHECKED, suitewrite.head_note(self.record()))
        self.assertTrue(suitewrite.keep_runner(self.keep, f"  {CMD}\n", runner, stamp=STAMP))
        self.assertTrue(self.kept().is_file())
        suitewrite.drop_runner(self.keep, CMD, runner, stamp=STAMP)
        self.assertFalse(self.kept().exists())

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
                self.assertTrue(suitewrite.prepare(self.file, self.folder, keep, self.root, stamp=STAMP)["write"])

    def test_prepare_does_not_use_a_kept_runner_with_another_stamp(self):
        """同じ test_cmd でも別の版の名の取り置きしか無ければ、書き手を起こす。その取り置きは消さずに残す"""
        self.put_kept(stamp=OTHER)
        got = self.prepare()
        self.assertTrue(got["write"])
        self.assertEqual(self.mark()["from"], suitewrite.FROM_AI)
        self.assertFalse((self.folder / suitewrite.RUNNER).exists())
        self.assertEqual(self.kept(OTHER).read_text(encoding="utf-8"), BODY)
        self.assertFalse(self.kept().exists())

    def test_prepare_does_not_use_a_kept_runner_without_a_stamp(self):
        """版の無い前の形の名 <sha256> の取り置きは使わず、書き手を起こす。その物は消さない（古い版の工場はそれを使い続ける）"""
        self.put_kept(stamp=None)
        self.assertTrue(self.prepare()["write"])
        self.assertFalse((self.folder / suitewrite.RUNNER).exists())
        self.assertEqual(self.kept(None).read_text(encoding="utf-8"), BODY)

    def test_keep_runner_keeps_one_runner_per_writer_stamp(self):
        """版ごとに 1 本の名で取り置く: 版 A と版 B は並び、前の形の名は残る。同じ版の名は置き換える（本番の道。fix の settle_kept が
        keep_runner・drop_runner で呼ぶ）。prepare は呼んだ版の物だけを写し、drop_runner は同じ版の同じバイトの物だけを消す"""
        old, new, mine, theirs = "#!/bin/sh\nold\n", "#!/bin/sh\nnew\n", self.tmp / "a", self.tmp / "b"
        self.put_kept(old, stamp=None)
        self.put_kept(old)   # 版 A の古い取り置き
        mine.write_text(new, encoding="utf-8")
        theirs.write_text("#!/bin/sh\nother\n", encoding="utf-8")
        self.assertTrue(suitewrite.keep_runner(self.keep, CMD, mine, stamp=STAMP))
        self.assertTrue(suitewrite.keep_runner(self.keep, CMD, theirs, stamp=OTHER))
        self.assertEqual(self.kept().read_text(encoding="utf-8"), new, "同じ版の名は新しい本文で置き換わる")
        self.assertEqual(self.kept(OTHER).read_text(encoding="utf-8"), "#!/bin/sh\nother\n")
        self.assertEqual(self.kept(None).read_text(encoding="utf-8"), old, "前の形の名は残る")
        self.assertEqual(self.prepare(STAMP), {"write": False, "brief_file": ""})
        self.assertEqual((self.folder / suitewrite.RUNNER).read_text(encoding="utf-8"), new)
        suitewrite.drop_runner(self.keep, CMD, theirs, stamp=STAMP)   # 同じ版の名の中身は theirs と違う
        self.assertTrue(self.kept().is_file())
        suitewrite.drop_runner(self.keep, CMD, mine, stamp=STAMP)
        self.assertFalse(self.kept().exists())
        self.assertTrue(self.kept(OTHER).is_file() and self.kept(None).is_file(), "ほかの版と前の形の名は残る")
        for bad in ("", "a/b", "..", "a b", None):   # 版の値は名に入れるだけなので、空や区切りを含む値は受けない
            with self.subTest(stamp=bad), self.assertRaises(ValueError):
                suitewrite.keep_runner(self.keep, CMD, mine, stamp=bad)

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
        self.assertEqual(suitewrite.settle(self.file, PASSED, self.keep, stamp=STAMP), {"done": True, "ok": True, "why": ""})
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
                self.assertEqual(suitewrite.settle(self.file, ran, self.keep, stamp=STAMP), {"done": True, "ok": False, "why": why})
                self.assertEqual((self.record()["tdd_suite"], self.mark()["ok"], self.mark()["why"]), ("", False, why))
                self.assertFalse(self.kept().exists())

    def test_kept_runner_that_fails_is_dropped_and_rewritten(self):
        """取り置きが照らしを通らなければ捨て（done: false）、次の周は書き手を起こし、書き直した物が通れば取り置き直す"""
        self.put_kept("#!/bin/sh\nexit 0\n")
        self.prepare()
        got = suitewrite.settle(self.file, {"exit": 0, "problems": [], "count": 0}, self.keep, stamp=STAMP)
        self.assertEqual(got, {"done": False, "ok": False, "why": suitewrite.NO_CASES})
        self.assertFalse(self.kept().exists())
        self.assertEqual(self.record()["tdd_suite"], "")
        self.written()
        self.assertEqual(self.mark()["dropped"], suitewrite.NO_CASES)
        self.assertTrue(suitewrite.settle(self.file, PASSED, self.keep, stamp=STAMP)["ok"])
        self.assertEqual(self.kept().read_text(encoding="utf-8"), BODY)
        self.assertIn(suitewrite.NO_CASES, suitewrite.head_note(self.record()))

    def test_drop_leaves_a_kept_runner_another_run_replaced(self):
        self.put_kept("#!/bin/sh\nold\n")
        self.prepare()
        self.put_kept()
        suitewrite.settle(self.file, None, self.keep, stamp=STAMP)
        self.assertEqual(self.kept().read_text(encoding="utf-8"), BODY)

    def test_settle_leaves_a_settled_mark_alone(self):
        self.prepare()
        before = self.record()
        self.assertEqual(suitewrite.settle(self.file, PASSED, self.keep, stamp=STAMP), {"done": True, "ok": False, "why": suitewrite.NO_REPLY})
        self.assertEqual(self.record(), before)
        self.assertFalse(self.kept().exists())

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
