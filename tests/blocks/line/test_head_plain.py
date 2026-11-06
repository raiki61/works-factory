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


class HeadAfterBase(unittest.TestCase):
    """頭の after を組む試験の共通の準備（試験は持たない）。facts_of が本物の build を呼び、after がその頭の after を返す"""

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.run = kit.Run(self, BLOCK)
        base.seed(self.run)

    def facts_of(self, values: dict) -> dict:
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.f.build(values, base.record())

    def after(self, values: dict) -> list:
        return self.facts_of(values)["head"]["after"]


class SuiteBrokenHeadCase(HeadAfterBase):
    """#836（docs/design/fix.md の 19 節）: 修正の段が、工場の書いた試験の起動スクリプトが書き直しても壊れたままで組を止めた run は、
    報告の冒頭の知らせの行に訳とログのパスを出す。止めていない run には出さない"""
    WHY = ("書き直した起動スクリプトも壊れている——工場が書いた試験の起動スクリプトが壊れている——関わる試験が起動スクリプト越しにだけ中身に"
           "届く前に落ちた（error 1 件。ログ /r/fix/tdd-2/suite-0.log）のに、test_cmd を単体で走らせると通る（ログ /r/fix/tdd-2/test-cmd-alone.log）")

    def test_the_stop_reason_with_the_log_paths_heads_the_report(self):
        v = base.passing()
        v["fixed"] = {**v["fixed"], "tdd": [[{"group_id": "g1", "ran": False, "reason": self.WHY, "suite": "/r/runner", "units": [],
                                              "suite_broken": True, "runner_log": "/r/fix/tdd-2/suite-0.log",
                                              "cmd_log": "/r/fix/tdd-2/test-cmd-alone.log"}]]}
        lines = [x for x in self.after(v) if x.startswith("修正の段が止めた")]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("/r/fix/tdd-2/suite-0.log", lines[0])
        self.assertIn("/r/fix/tdd-2/test-cmd-alone.log", lines[0])

    def test_a_group_stopped_for_no_suite_heads_the_report(self):
        """試験の実行器が無い・走らないで止めた組（止めの語 no-suite。docs/plans/2026-10-24-fix-weapons.md の 3.9）も、訳を冒頭に出す"""
        v = base.passing()
        v["fixed"] = {**v["fixed"], "tdd": [[{"group_id": "g1", "ran": False, "reason": "試験の実行器が無いか走らない組", "units": [],
                                              "no_suite": True}]]}
        lines = [x for x in self.after(v) if x.startswith("修正の段が止めた")]
        self.assertEqual(lines, ["修正の段が止めた（試験の実行器が無い・走らない。組 g1）: 試験の実行器が無いか走らない組"])

    def test_a_fix_that_did_not_stop_says_nothing(self):
        self.assertFalse([x for x in self.after(base.passing()) if x.startswith("修正の段が止めた")])


class BaseStopHeadCase(HeadAfterBase):
    """持ち主の決め base-runs-nothing の足し: 直す前の試験の関門が止めた run（試験のコマンドの最初の語を起こせない）は、報告の冒頭の
    知らせの行に止めた訳を出す。止めていない run には出さない"""
    WHY = "素材が not_run——緑を仮定しない（試験のコマンド（no-such-tool）の最初の語を起こせない（PATH に no-such-tool が無い）。試験は走らせずに確かめた）"

    def test_the_stop_reason_of_the_base_gate_heads_the_report(self):
        v = base.passing()
        v["test_gate_base"] = {**v["test_gate_base"], "ok": False, "green": False, "reason": self.WHY}
        for name in ("judge", "fix_in", "fixed", "eyes", "merge_seal", "merge_apply", "test_gate_final"):
            v[name] = None
        lines = [x for x in self.after(v) if x.startswith("直す前の試験の関門が止めた")]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("起こせない", lines[0])

    def test_the_base_gate_reason_keeps_the_whole_setup_guide_in_the_head(self):
        import green_cert
        _, reason = green_cert.certify(mode="base", material_status="not_run", material_reason="試験のコマンド（no-such-tool）の最初の語を起こせない",
                                       green=None, before=None, after=None, now=None)
        v = base.passing()
        v["test_gate_base"] = {**v["test_gate_base"], "ok": False, "green": False, "reason": reason}
        facts = self.facts_of(v)
        lines = [x for x in facts["head"]["after"] if x.startswith("直す前の試験の関門が止めた")]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(green_cert.RAN_GUIDE, lines[0])
        self.assertFalse([x for x in facts["notes"] if "報告の頭では切った訳の全文" in x], facts["notes"])

    def test_a_base_gate_that_went_on_says_nothing(self):
        self.assertFalse([x for x in self.after(base.passing()) if x.startswith("直す前の試験の関門が止めた")])


class StopReasonHeadCase(HeadAfterBase):
    """報告の冒頭の知らせの行に訳が出る止めは、入口が入力を断った止め（次にすることの句が尾に付く）と直す前の試験の関門が止めた止めだけ。
    line の script の落ちと block の止めの訳は頭に出さない（script の落ちは problems に在る）。止めていない run には出さない"""
    REFUSED = "PR の head が対象の HEAD と違う——PR の head を取り出した所で始める"
    NEXT = "次にすること: 訳が名指した入力を直して、run を起こし直す"

    def inner_names_in(self, text: str) -> list:
        names = [n for n in self.f.node_names() if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
        return [*names, *[m.group(0) for p in INNER for m in re.finditer(p, text)]]

    def stopped_values(self, node, name, word):
        v = base.passing()
        v[name] = {**(v.get(name) or {}), "ok": False, "stop_reason": word, "reason": f"R-{node}"}
        return v

    def stage_lines(self, node, name, word):
        """段 node が止めの語 word で止めた run の、訳 R-<node> を含む (頭の after の行, problems の行)"""
        facts = self.facts_of(self.stopped_values(node, name, word))
        return ([x for x in facts["head"]["after"] if f"R-{node}" in x], [x for x in facts["problems"] if f"R-{node}" in x])

    def test_a_stop_without_its_reason_in_the_head_still_says_where_it_stopped_and_what_the_word_means(self):
        import stopby
        cases = [(node, name, stopby.LINE_SCRIPT) for node, name in self.f.LINE_STOPS if node != "start"]
        cases += [(node, name, stopby.PREMISES) for node, name in self.f.BLOCK_STOPS]
        cases += [("theme-descend", "theme_descend", stopby.NEEDS_HUMAN), ("theme-descend", "theme_descend", stopby.HUMAN + "gate-theme")]
        for node, name, word in cases:
            with self.subTest(node=node, word=word):
                facts = self.facts_of(self.stopped_values(node, name, word))
                self.assertEqual([x for x in facts["head"]["after"] if f"R-{node}" in x], [], "訳の本文は頭に出さない")
                lines = [x for x in facts["head"]["stopped"] if x.startswith(f"{self.f.plain(node)}が止めた: ")]
                self.assertEqual(len(lines), 1, facts["head"]["stopped"])
                self.assertEqual(self.f.WAITS_FOR_HUMAN in lines[0], word in stopby.WAITING or word.startswith(stopby.HUMAN), lines[0])
        with self.subTest(word="human"):
            facts = self.facts_of(self.stopped_values("theme-descend", "theme_descend", stopby.HUMAN + "gate-theme"))
            self.assertIn(f"{self.f.HUMAN_STOP}{self.f.WAITS_FOR_HUMAN}", "\n".join(facts["head"]["stopped"]))

    def test_the_design_stage_reason_stays_in_the_theme_section(self):
        import stopby
        reason = "人が設計の段の承認ノードで止めた（R-theme-descend）"
        descend = kit.load(BLOCK, "descend")._stopped(reason, stopby.HUMAN + "gate-theme")
        sections = kit.load(BLOCK, "sections")
        section = sections.theme_section({"theme_descend": descend})
        self.assertIn(f"設計の段: {reason}", "\n".join(map(str, section["lines"])))

    def test_only_the_refused_start_and_the_base_gate_put_their_reason_in_the_head(self):
        import stopby
        for node, name in self.f.LINE_STOPS:
            word = stopby.START_REFUSED if node == "start" else stopby.LINE_SCRIPT
            with self.subTest(node=node):
                head, problems = self.stage_lines(node, name, word)
                if node == "start":
                    self.assertEqual(len(head), 1, head)
                    self.assertIn(self.NEXT, head[0])
                    self.assertEqual(self.inner_names_in(head[0].replace(f"R-{node}", "")), [], head[0])
                else:
                    self.assertEqual(head, [], "line の script の落ちの訳は頭に出さない（problems に在る）")
                    self.assertEqual(len(problems), 1, problems)
        for node, name in self.f.BLOCK_STOPS:
            with self.subTest(node=node):
                head, _ = self.stage_lines(node, name, stopby.PREMISES)
                self.assertEqual(head, [], "block の止めの訳は頭に出さない")

        with self.subTest(node="test-gate-base"):
            v = base.passing()
            v["test_gate_base"] = {**v["test_gate_base"], "ok": False, "green": False, "reason": "R-test-gate-base"}
            lines = [x for x in self.after(v) if "R-test-gate-base" in x]
            self.assertEqual(len(lines), 1, lines)
            self.assertEqual(self.inner_names_in(lines[0].replace("R-test-gate-base", "")), [], lines[0])
            self.assertNotIn(self.NEXT, lines[0])
        with self.subTest(node="none"):
            after = self.after(base.passing())
            self.assertFalse([x for x in after if "R-" in x or self.NEXT in x], after)

    def test_a_block_stop_reason_stays_in_the_stopped_section(self):
        import stopby
        for node, name in self.f.BLOCK_STOPS:
            with self.subTest(node=node):
                facts = self.facts_of(self.stopped_values(node, name, stopby.PREMISES))
                lines = [x for x in facts["stop_lines"]["before"] if f"R-{node}" in x]
                self.assertEqual(lines, [f"{self.f.named(node)} の止めた訳: R-{node}"])
        for node, name in self.f.LINE_STOPS:
            with self.subTest(node=node, kind="line"):
                facts = self.facts_of(self.stopped_values(node, name, stopby.LINE_SCRIPT))
                self.assertEqual([x for x in facts["stop_lines"]["before"] if f"R-{node}" in x], [], "line の script の落ちの訳は problems に在る")

    def test_the_refused_line_says_what_to_do_next_without_inner_names(self):
        import stopby
        v = {name: None for name in base.INPUTS} | {"notices": "", "optional": []}
        v["start"] = {"ok": False, "stop_reason": stopby.START_REFUSED, "reason": self.REFUSED, "record": None}
        lines = [x for x in self.after(v) if x.startswith(stopby.REASONS["start-refused"])]
        self.assertEqual(len(lines), 1, lines)
        line = lines[0]
        self.assertIn(self.REFUSED, line)
        self.assertIn(self.NEXT, line)
        self.assertLess(line.index(self.REFUSED), line.index(self.NEXT), "訳が先、次にすることが尾")
        self.assertEqual(self.inner_names_in(line.replace(self.REFUSED, "")), [], line)


class StopMeaningCase(unittest.TestCase):
    """止めの語から人が読む意味を引く読みは 1 つ（stop_meaning）。頭の止めの行・頭の外の全部の行・止めた段の残りの行が同じ読みを使う"""

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")

    def test_the_meaning_of_a_stop_word_is_read_from_the_table_with_or_without_the_head(self):
        import stopby
        for key, meaning in stopby.REASONS.items():
            with self.subTest(word=key):
                self.assertEqual(self.f.stop_meaning(stopby.HEAD + key), meaning)
                self.assertEqual(self.f.stop_meaning(key), meaning)

    def test_a_word_with_no_recorded_meaning_reads_as_the_unknown_stop_text(self):
        self.assertEqual(self.f.stop_meaning("works:no-such-stop"), self.f.UNKNOWN_STOP)
        self.assertEqual(self.f.stop_meaning(None), self.f.UNKNOWN_STOP)
