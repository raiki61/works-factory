"""AI ノードの群の表（lib/launchgroups.py）の形の検査。表を直に読むだけ。

見る物:
- 群の名は全部 '@wf-' で始まり、what が空でない
- default_of が返す (model, effort) は表の値と同じで、旧来の字の値の 4 つの組のどれか
- 表に無い名は KeyError
- 役の群の選びの照らし（choices）: 表に無い群・許さない語・同じ群の 2 行目・形の壊れた行はその行だけ既定に戻って訳が残り、
  向き（direction）は上げ・下げ・同じ・混ざる。役に貼るセクション（brief_section）は表から描く
"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import launchgroups  # noqa: E402

BASE_PAIRS = {("opus", "high"), ("opus", "medium"), ("sonnet", "high"), ("sonnet", "medium")}


class GroupTableTest(unittest.TestCase):
    def test_defaults_are_the_base_pairs(self):
        self.assertEqual(len(launchgroups.GROUPS), 15)
        for name, row in launchgroups.GROUPS.items():
            with self.subTest(group=name):
                self.assertTrue(name.startswith("@wf-"), name)
                self.assertTrue(row["what"].strip())
                pair = launchgroups.default_of(name)
                self.assertEqual(pair, (row["model"], row["effort"]))
                self.assertIn(pair, BASE_PAIRS)
        for name in ("@wf-nope", "opus", ""):
            with self.subTest(name=name), self.assertRaises(KeyError):
                launchgroups.default_of(name)


JUDGE = "@wf-judge-core"      # 既定 opus・high
WRITERS = "@wf-fix-writers"   # 既定 sonnet・high


def row(group, model, effort, why="訳"):
    return {"group": group, "model": model, "effort": effort, "why": why}


class ChoiceTest(unittest.TestCase):
    def test_unknown_group_or_word_falls_back_with_reason(self):
        got = launchgroups.choices([
            row(JUDGE, "opus", "max"),              # 通る
            row("@wf-nope", "opus", "high"),        # 表に無い群
            row(WRITERS, "gpt", "high"),            # 許さない模型
            row("@wf-report", "sonnet", "extreme"),  # 許さない effort
            row(JUDGE, "haiku", "low"),             # 同じ群の 2 行目
        ])
        self.assertEqual(len(got), 5)
        self.assertEqual((got[0]["model"], got[0]["effort"], got[0]["fallback"]), ("opus", "max", ""))
        self.assertEqual(got[0]["why"], "訳")
        self.assertEqual(got[0]["default"], {"model": "opus", "effort": "high"})
        self.assertEqual((got[1]["group"], got[1]["model"], got[1]["effort"]), ("@wf-nope", None, None))
        self.assertIn("が表に無い", got[1]["fallback"])
        self.assertEqual((got[2]["group"], got[2]["model"], got[2]["effort"]), (WRITERS, "sonnet", "high"))
        self.assertIn("gpt", got[2]["fallback"])
        self.assertEqual((got[3]["model"], got[3]["effort"]), ("sonnet", "medium"))
        self.assertIn("extreme", got[3]["fallback"])
        self.assertEqual((got[4]["group"], got[4]["model"], got[4]["effort"]), (JUDGE, "opus", "high"))
        self.assertIn("2 行目", got[4]["fallback"])
        for fell in got[1:]:
            self.assertEqual(fell["direction"], "同じ")
        self.assertEqual({r["group"] for r in got if not r["fallback"]}, {JUDGE})

    def test_direction_is_recorded_for_up_and_down(self):
        d = launchgroups.direction
        base = ("sonnet", "medium")
        self.assertEqual(d(base, ("sonnet", "medium")), "同じ")
        self.assertEqual(d(base, ("opus", "medium")), "上げ")
        self.assertEqual(d(base, ("sonnet", "max")), "上げ")
        self.assertEqual(d(base, ("opus", "high")), "上げ")
        self.assertEqual(d(base, ("haiku", "medium")), "下げ")
        self.assertEqual(d(base, ("sonnet", "low")), "下げ")
        self.assertEqual(d(base, ("haiku", "low")), "下げ")
        self.assertEqual(d(base, ("opus", "low")), "混ざる")
        self.assertEqual(d(base, ("haiku", "high")), "混ざる")
        self.assertEqual(launchgroups.MODELS, ("haiku", "sonnet", "opus"))
        self.assertEqual(launchgroups.EFFORTS, ("low", "medium", "high", "max"))
        for model, effort in (launchgroups.default_of(g) for g in launchgroups.GROUPS):
            self.assertIn(model, launchgroups.MODELS)
            self.assertIn(effort, launchgroups.EFFORTS)
        got = launchgroups.choices([row(JUDGE, "opus", "max"), row(WRITERS, "haiku", "medium"), row("@wf-report", "opus", "low")])
        self.assertEqual([r["direction"] for r in got], ["上げ", "下げ", "混ざる"])
        self.assertEqual([(r["model"], r["effort"], r["fallback"]) for r in got],
                         [("opus", "max", ""), ("haiku", "medium", ""), ("opus", "low", "")])

    def test_no_choice_and_malformed_input_fall_back_without_raising(self):
        for empty in (None, [], (), {}, "x", 3, {"group": JUDGE}):
            with self.subTest(empty=empty):
                self.assertEqual(launchgroups.choices(empty), [])
        got = launchgroups.choices(["x", None, {"group": 3, "model": "opus", "effort": "high"}, {},
                                    {"group": JUDGE, "model": ["opus"], "effort": None}, row(WRITERS, "opus", "high")])
        self.assertEqual(len(got), 6)
        for bad in got[:3]:
            self.assertTrue(bad["fallback"])
            self.assertEqual((bad["group"], bad["model"], bad["effort"]), ("", None, None))
        self.assertTrue(got[3]["fallback"])
        self.assertEqual((got[4]["model"], got[4]["effort"]), ("opus", "high"))
        self.assertTrue(got[4]["fallback"])
        self.assertEqual((got[5]["fallback"], got[5]["direction"]), ("", "上げ"))


if __name__ == "__main__":
    unittest.main()
