"""run の頭の深さの段の語と控えの読み（lib/headdepth.py。issue #441）の検査。関数を直に呼び、一時の置き場に控えを書くだけ。

見る物:
- 段の語と並び（前は lib/depth.py。integration.md 4.5-6）と控えの名（integration.md 4.3-5）
- 控えが無い・壊れた時は標準。控えは群の選びを持つ
- 報告の ## 模型 の群の選びの行
行ごとの未知の種類・機械の止め・引用の照らしは head-depth の試験、報告の冒頭 2 の行は line の試験へ移った。
"""
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import headdepth  # noqa: E402
import launchgroups  # noqa: E402


class WordsTest(unittest.TestCase):
    def test_tier_words_and_record_name(self):
        self.assertEqual(headdepth.HEADS, (headdepth.LIGHT, headdepth.STANDARD, headdepth.HEAVY))
        self.assertEqual(headdepth.HEADS, ("軽量", "標準", "重厚"))
        self.assertEqual(headdepth.RECORD, "depth-head.json")


class RecordTest(unittest.TestCase):
    def test_missing_or_broken_record_reads_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            (pathlib.Path(tmp) / headdepth.RECORD).write_text("{", encoding="utf-8")
            self.assertEqual(headdepth.read(tmp)["depth"], "標準")
            headdepth.write(tmp, headdepth.record("軽量", "根拠"))
            self.assertEqual(headdepth.read(tmp)["depth"], "軽量")

    def test_record_keeps_the_checked_groups(self):
        groups = launchgroups.choices([{"group": "@wf-judge-core", "model": "opus", "effort": "max", "why": "多段の根拠"},
                                       {"group": "@wf-nope", "model": "opus", "effort": "high", "why": "x"}])
        self.assertEqual(len(groups), 2)
        with tempfile.TemporaryDirectory() as tmp:
            headdepth.write(tmp, headdepth.record("標準", "根拠", groups=groups))
            self.assertEqual(headdepth.read(tmp)["groups"], groups)
            headdepth.write(tmp, headdepth.record("標準", "根拠"))
            self.assertEqual(headdepth.read(tmp)["groups"], [])
        self.assertEqual(headdepth.record("軽量", "根拠")["groups"], [])


class GroupsLinesTest(unittest.TestCase):
    def test_groups_lines_show_only_changed_groups_or_one_line(self):
        none = [headdepth.NO_CHOICE, headdepth.RUN_SWITCH]
        self.assertEqual(none[0], "役の選びは無い（呼ぶ人の名指しと層の付け替えの後の値は下のノードごとの行）")
        for name, doc in (("no groups", headdepth.record("標準", "x")), ("empty groups", {"groups": []}), ("no record", None),
                          ("groups not a list", {"groups": "x"}), ("rows not objects", {"groups": ["x", 3]})):
            with self.subTest(name):
                got = headdepth.groups_lines(doc)
                self.assertEqual(got, none)
                self.assertNotIn("既定のまま", "".join(got))
        rows = launchgroups.choices([
            {"group": "@wf-fix-writers", "model": "opus", "effort": "high", "why": "広い書き換え"},
            {"group": "@wf-eyes-core", "model": "gpt", "effort": "high", "why": "強く"},
            {"group": "@wf-nothing", "model": "opus", "effort": "high", "why": "x"},
        ])
        doc = headdepth.record("重厚", "設計の選び", groups=rows)
        self.assertEqual(headdepth.groups_lines(doc), [
            "@wf-fix-writers: 既定 sonnet・high → 役の選び opus・high（上げ。訳: 広い書き換え）",
            "@wf-eyes-core: 役の選びを既定 opus・high に戻した（訳: 許さない語（model 'gpt'・effort 'high'。許すのは "
            "haiku・sonnet・opus と low・medium・high・max））",
            "@wf-nothing: 表に無い群を既定に戻した（訳: 群 '@wf-nothing' が表に無い）",
            headdepth.RUN_SWITCH])
        lines = "".join(headdepth.groups_lines(doc))
        for group in launchgroups.GROUPS:
            if group not in ("@wf-fix-writers", "@wf-eyes-core"):
                self.assertNotIn(group, lines, "選ばれていない群の行は出ない")
        with mock.patch.dict(launchgroups.GROUPS, {"@wf-fix-writers": {"model": "haiku", "effort": "low", "what": "替えた表"}}):
            self.assertEqual(headdepth.groups_lines(doc)[0], "@wf-fix-writers: 既定 sonnet・high → 役の選び opus・high（上げ。訳: 広い書き換え）",
                             "控えた時の既定を出し、後で替えた表から引き直さない")
        same = launchgroups.choices([{"group": "@wf-report", "model": "sonnet", "effort": "medium", "why": ""}])
        self.assertEqual(headdepth.groups_lines({"groups": same})[0],
                         "@wf-report: 既定 sonnet・medium → 役の選び sonnet・medium（同じ。訳: 訳の記録が無い）")
        no_effort = [{**same[0], "default": {"model": "sonnet"}, "fallback": "x"}]
        self.assertEqual(headdepth.groups_lines({"groups": no_effort})[0], "@wf-report: 役の選びを既定 sonnet に戻した（訳: x）",
                         "控えの既定に effort が無ければ出さない")

    def test_groups_lines_say_up_and_down_are_record_only_with_the_launch_switch(self):
        self.assertEqual(headdepth.RUN_SWITCH,
                         "役の選びは記録だけで、この run にも子の run にも次の周にも効かない。走りの模型を替えるには、run を起こす時に "
                         "--model @wf-<群>=<模型> を渡す（effort も替えるなら <模型> の代わりに effort を持つ別名 @<名> を書く）。")
        for want, row in ((launchgroups.UP, {"group": "@wf-fix-writers", "model": "opus", "effort": "max", "why": "x"}),
                          (launchgroups.DOWN, {"group": "@wf-fix-writers", "model": "haiku", "effort": "low", "why": "x"})):
            with self.subTest(want):
                chosen = launchgroups.choices([row])
                self.assertEqual(chosen[0]["direction"], want)
                got = headdepth.groups_lines(headdepth.record("標準", "x", groups=chosen))
                self.assertEqual(len(got), 2)
                self.assertEqual(got[-1], headdepth.RUN_SWITCH)


if __name__ == "__main__":
    unittest.main()
