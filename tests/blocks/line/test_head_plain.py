"""報告の頭（機械が書く行）に、工場の内側の名前が訳なしで出ない（issue #687 の求め 6）。

材料は本物の run 2 本（無人で最後の承認ノードを開けずに止まった軽量の run）の記録の形: 修正前の承認ノードを推しで通し、最後の承認ノードの
2 つのノードが止めの語で止まり、独立の目 R1 が長い指摘の文つきで直しが要ると言い、直しの途中で AI が自分で決めずに人に回した物が在る。初見の読み手は報告の頭
だけを読むので、頭の行に出る内側の名前（ノードの id・止めの語・記録の欄の名・審査役の印）は、頭の中で人の言葉に訳されている形だけを許す。
訳なしの名前を 1 つずつ足して直すのでなく、頭の行の作り方（人の言葉を先に出し、名前と長い文は頭の外の節に置く）で縛る。
"""
import re
import unittest
from unittest import mock

from tests.blocks import kit
from tests.blocks.line import test_collect as base

BLOCK = "line"
R1_REASON = ("考えの住処は lib/unittrees.py:151-152（_is_marker の WHY 注記と `if m != MARKERS[2]` の判定）です。累積差分は MARKERS の定義行 "
             "lib/unittrees.py:253 の注記に書き足しました。これで知る場所が 1 つ増えています（r1-comments の候補と同じです）。もう 1 件、新しい"
             "テスト（lib/tests/test_unittrees.py:133-135）の r.md は sep.txt と同じ『区切りの単独行』の 1 例で、重複です。どちらも削除だけで"
             "閉じる零処方なので fix-needed とします。breaks.accepted の 2 件は、零処方で直せる物を人へ逃がしたものではありませんでした。")
HANDOFF = ("lib/unittrees.py markers_left 字のぶつかりで印を書いたファイルの中身の単独の ======= の行を残った印と数えて拒む: "
           "壊すと分かって通した——区切りの ======= だけを残したファイルは、直す前は拒まれたが通るようになる")
PUSH = {"item": "修正前の確認", "answer": "continue", "note": "このまま通す", "why": "範囲が小さい"}
# 頭に訳なしで出てはいけない内側の名前の形（ノードの id は nodenames.json の行。止めの語・審査役の印・記録の欄の名は字の形で見る）
INNER = (r"works:[a-z]", r"\bR[1-4]\b", r"\b(?:fix-needed|redesign-needed)\b", r"\bbreaks\.accepted\b")


def unattended_stop() -> dict:
    v = base.passing()
    v["start"] = {**v["start"], "unattended": True}
    v["answer_before_fix"] = {"go": True, "stop_reason": "", "policy": "",
                              "answer": {"decision": "continue", "text": "推しで通す", "pushed": [PUSH]}}
    v["ask_final"] = {"open": False, "go": False, "stop_reason": "works:needs-human", "text": "",
                      "reasons": ["書き換えを許したテストを触った（1 件。人の確かめが要る）", "直しの途中で AI が自分で決めずに人に回した物が在る（1 件）",
                                  "独立の目が通さなかった（R1: 直しが要る）"]}
    v["answer_final"] = {"go": False, "answer": None, "stop_reason": "works:needs-human"}
    v["eyes"] = {**v["eyes"], "r1": {"status": "fix-needed", "reason": R1_REASON}}
    v["fix"] = {**v["fix"], "handoffs": [HANDOFF]}
    return v


class HeadPlainCase(unittest.TestCase):
    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.run = kit.Run(self, BLOCK)
        base.seed(self.run)
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            self.facts = self.f.build(unattended_stop(), base.record())
        head = self.facts["head"]
        self.head = [*head["before"], *head["stopped"], *head["after"], *[f"{a['kind']}: {a['text']}" for a in self.facts["asks"]]]

    def test_no_inner_name_stands_bare_in_the_head(self):
        text = "\n".join(self.head)
        names = [n for n in self.f.node_names() if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
        found = [*names, *[m.group(0) for p in INNER for m in re.finditer(p, text)]]
        self.assertEqual(found, [], text)

    def test_long_reviewer_reason_is_not_pasted_into_the_head(self):
        self.assertFalse(any("lib/unittrees.py:151" in x for x in self.head), self.head)
        self.assertTrue(max(len(x) for x in self.head) < 300, [len(x) for x in self.head])

    def test_the_names_and_the_full_reason_are_kept_outside_the_head(self):
        """頭から外した名前と長い指摘の全文は、頭の外の節（止めたかの節の行）に残る"""
        text = "\n".join(self.facts["stop_lines"]["before"])
        for kept in ("ask-final", "answer-final", "works:needs-human", "R1", "lib/unittrees.py:151"):
            self.assertIn(kept, text)

    def test_every_node_a_stop_can_name_has_a_plain_name(self):
        names = self.f.node_names()
        for node, _ in (*self.f.LINE_STOPS, *self.f.BLOCK_STOPS, *self.f.GATES):
            self.assertTrue(names.get(node), node)
        for node in ("fix", "refix-run", "spec-check-run"):
            self.assertTrue(names.get(node), node)


class HandoffTitleCase(unittest.TestCase):
    """修正役が添えた題（fix の出力 handoff_titles。行 → 題）が、人が決める物の題（asks の title）として報告へ渡る。題が無い行は題なしのまま"""
    TITLE = "区切りの行だけが残ったファイルを、拒まずに通す検査へ緩める"

    def asks(self, titles):
        f = kit.load(BLOCK, "facts")
        run = kit.Run(self, BLOCK)
        base.seed(run)
        v = unattended_stop()
        v["fixed"] = {**v["fixed"], "handoffs": [HANDOFF], "handoff_titles": titles}
        with run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return [a for a in f.build(v, base.record())["asks"] if a["kind"].startswith("直しの途中で AI が自分で決めずに人に回した物")]

    def test_the_title_the_fixer_wrote_rides_on_the_ask(self):
        (ask,) = self.asks({HANDOFF: self.TITLE})
        self.assertEqual(ask["title"], self.TITLE)
        self.assertIn("markers_left", ask["text"], "本文は字のまま")

    def test_a_line_without_a_title_has_no_title_key(self):
        (ask,) = self.asks({})
        self.assertNotIn("title", ask)


class SuiteBrokenHeadCase(unittest.TestCase):
    """#836（docs/design/fix.md の 19 節）: 修正の段が、工場の書いた試験の起動スクリプトが書き直しても壊れたままで組を止めた run は、
    報告の冒頭の知らせの行に訳とログのパスを出す。止めていない run には出さない"""
    WHY = ("書き直した起動スクリプトも壊れている——工場が書いた試験の起動スクリプトが壊れている——関わる試験が起動スクリプト越しにだけ中身に"
           "届く前に落ちた（error 1 件。ログ /r/fix/tdd-2/suite-0.log）のに、test_cmd を単体で走らせると通る（ログ /r/fix/tdd-2/test-cmd-alone.log）")

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.run = kit.Run(self, BLOCK)
        base.seed(self.run)

    def after(self, values: dict) -> list:
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.f.build(values, base.record())["head"]["after"]

    def test_the_stop_reason_with_the_log_paths_heads_the_report(self):
        v = base.passing()
        v["fixed"] = {**v["fixed"], "tdd": [[{"group_id": "g1", "ran": False, "reason": self.WHY, "suite": "/r/runner", "units": [],
                                              "suite_broken": True, "runner_log": "/r/fix/tdd-2/suite-0.log",
                                              "cmd_log": "/r/fix/tdd-2/test-cmd-alone.log"}]]}
        lines = [x for x in self.after(v) if x.startswith("修正の段が止めた")]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("/r/fix/tdd-2/suite-0.log", lines[0])
        self.assertIn("/r/fix/tdd-2/test-cmd-alone.log", lines[0])

    def test_a_fix_that_did_not_stop_says_nothing(self):
        self.assertFalse([x for x in self.after(base.passing()) if x.startswith("修正の段が止めた")])
