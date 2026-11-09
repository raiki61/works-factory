"""機械の報告（workflows/report/src/machine.py。docs/design/report.md の 1.8）の節の並びと字。写す元は test_runreport.py の BuildCase
（冒頭 3 行・止めたか・見る所・模型・費用・注意）・DraftsCase・CarryCase・StampCase。節の中身を返りから組む試験は作り手の block と graph の試験の物。
頭の行の文面表（src/head.py）全体の検査は HeadTableCase（表と列挙の一致・差し込み口・頭の読み戻し・schema の種・語の表の語・描く口の拒み）"""
import ast
import json
import pathlib
import re
import string
import typing
import unittest
from unittest import mock

from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
import report    # noqa: E402  lib/
import userenv   # noqa: E402  lib/
import oneline   # noqa: E402  lib/

RUN_ID = "run-test"
SECTIONS = [{"title": "直した所", "lines": ["単位 u1: 直した", "  内訳 a"]}, {"title": "空の節", "lines": []}]
OK_RUN = {"ok": True, "failed": [], "absorbed": [], "errors": {}, "retried": [], "cost": {"fix__tdd": 0.5}, "uncosted": {}, "minutes": {"fix__tdd": 1.5},
          "models": {"fix__tdd": ["sonnet"]}, "efforts": {"fix__tdd": ["low"]}, "calls": {}, "resubmits": {}}


def notice(kind: str, text: str = "", **slots) -> dict:
    """facts の head.after・head.notices の要素 {kind, slots, text}"""
    return {"kind": kind, "slots": slots, "text": text}


class Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "report")
        self.place = self.run.artifacts

    def build(self, sections=SECTIONS, run=OK_RUN, outcome="fixed", stop="", **facts):
        got = M.facts_in.read({**base.READY, **facts})
        with self.run.env():
            opened, notes = M.machine.open_files(sections)
            built = M.machine.build(opened, got, outcome, stop, run, place=self.place, run_id=RUN_ID, run_why="", repo=self.run.repo, notes=notes)
        return built, built["report"].read_text(encoding="utf-8")

    @staticmethod
    def section(text, heading):
        return text.split(f"{heading}\n\n", 1)[1].split("\n## ", 1)[0].rstrip("\n")


class HeadCase(Base):
    def test_three_lines_and_one_line_per_kind(self):
        asks = [{"kind": "保留にしたままの問い", "text": "A を決める"}, {"kind": "保留にしたままの問い", "text": "B を決める"},
                {"kind": "許したテストの変更", "text": "t.py"}]
        _, text = self.build(asks=asks, tallied={"許したテストの変更": 5})
        lines = text.splitlines()
        self.assertEqual(lines[0], f"# 報告（run {RUN_ID}）")
        self.assertEqual(lines[2], "起きたこと: 直して、最後のテストまで通った。人が決めること 7 件が残っている")
        self.assertTrue(lines[3].startswith("差分を当ててよいか: "))
        self.assertTrue(lines[4].startswith("急ぎ: "))
        self.assertEqual(lines[5], "人が決めること: 7 件（下の行は種類ごと。題のある物は 1 件ずつ）")
        self.assertEqual(lines[6:8], ["- 保留にしたままの問い（2 件）", "- 許したテストの変更（5 件）"])

    def test_title_carries_the_request_row_after_the_run_id(self):
        said = "報告の 1 行目に\n依頼の字を出す"
        _, text = self.build(request_texts=[said])
        first = text.splitlines()[0]
        self.assertEqual(first, f"# 報告（run {RUN_ID}）: {M.head.OneLine(said)}")
        row = M.head.parse(first)
        self.assertEqual((row.kind, row.slots), (M.head.Line.REQUEST_TITLE, M.head.RequestTitleSlot(M.head.RunId(RUN_ID), M.head.OneLine(said))))

    def test_title_counts_the_other_request_rows(self):
        rows = ["1 行目の依頼", "2 行目の依頼", "3 行目の依頼"]
        _, text = self.build(request_texts=rows)
        first = text.splitlines()[0]
        self.assertEqual(first, f"# 報告（run {RUN_ID}）: 1 行目の依頼（ほかの依頼の行 2 件）")
        row = M.head.parse(first)
        self.assertEqual((row.kind, row.slots.more), (M.head.Line.REQUEST_TITLE_MORE, 2))

    def test_nothing_to_decide_names_what_is_carried_instead(self):
        carry = {"findings": [{"where": "a", "text": "b"}], "prior": [], "drafts": [], "constraints": []}
        _, text = self.build(carry=carry)
        self.assertEqual(text.splitlines()[5], "次の run に渡す物: 1 件")
        self.assertNotIn("人が決めること:", text.split("\n## ", 1)[0], "無いと断る決まり文句は書かない")

    def test_head_parts_go_to_the_stop_section_not_the_happened_line(self):
        head = {"before": ["半分直した"], "stopped": ["止めた訳 X"], "after": [], "notices": [notice("test_cmd_note", "起こす前の注意 N")]}
        _, text = self.build(head=head)
        top = text.split("\n## ", 1)[0].splitlines()
        self.assertEqual(top[2], "起きたこと: 直して、最後のテストまで通った")
        self.assertIn(M.head.notice_row(M.head.Notice.TEST_CMD_NOTE), top, "頭には種の決まった文が出る")
        self.assertNotIn("起こす前の注意 N", "\n".join(top), "注意の本文は頭に出さない")
        stop = self.section(text, "## 2. 止めたか").splitlines()
        self.assertEqual(stop[0], "- 試験のコマンドの注意: 起こす前の注意 N", "本文は節 2 の頭に在る")
        self.assertIn("- 半分直した", stop)
        self.assertNotIn("止めた訳 X", text, "止まった run でなければ止めた訳は出さない")
        _, text = self.build(head=head, outcome="stopped_by_human", stop="start-answer:reject")
        self.assertEqual(text.splitlines()[2], f"起きたこと: {report.OUTCOME_WORDS['stopped_by_human']}")
        self.assertNotIn("承認ノード", text.splitlines()[2], "起きたことの行は工場の語を使わない")
        stop = self.section(text, "## 2. 止めたか").splitlines()
        self.assertEqual(stop[3:5], ["- 半分直した", "- 止めた訳 X"])


class TitleCase(Base):
    """決める物の題（facts.asks の title。それを書く所が本文と一緒に書く）。頭の種ごとの行は、題が在れば 1 件 1 行で題を出し、
    無ければ今の種の名に戻して件数でまとめる（黙って行を落とさない）"""
    def test_titled_ask_is_one_row_with_its_title_and_kind(self):
        asks = [{"kind": "直しの途中で AI が自分で決めずに人に回した物（訳）", "text": "長い本文", "title": "検査を緩めてよいか"}]
        _, text = self.build(asks=asks)
        top = text.split("\n## ", 1)[0].splitlines()
        self.assertIn("- 検査を緩めてよいか（直しの途中で AI が自分で決めずに人に回した物）", top)
        self.assertNotIn("長い本文", "\n".join(top))
        self.assertIn("人が決めること: 1 件（", text)

    def test_untitled_asks_fall_back_to_the_kind_and_are_still_counted(self):
        asks = [{"kind": "k", "text": "a", "title": "題 A"}, {"kind": "k", "text": "b"}, {"kind": "k", "text": "c"}]
        _, text = self.build(asks=asks)
        top = text.split("\n## ", 1)[0].splitlines()
        self.assertIn("人が決めること: 3 件（下の行は種類ごと。題のある物は 1 件ずつ）", top)
        self.assertEqual([x for x in top if x.startswith("- ")], ["- 題 A（k）", "- k（2 件）"])

    def test_blank_title_is_untitled(self):
        _, text = self.build(asks=[{"kind": "k", "text": "a", "title": "  "}])
        self.assertIn("- k", text.split("\n## ", 1)[0].splitlines())

    def test_outcome_asks_show_their_title_in_the_head(self):
        """結末で決まる物（outcome_asks）の行は、頭で種の名だけでなく決まった題の行で出る。節の本文の行は今のまま"""
        left = [{"where": "素材 a", "text": "測れていない", "unmeasured": True}]
        _, text = self.build(outcome="fixed_needs_check", left=left)
        titles = getattr(M.outcome, "OUTCOME_TITLES", None)
        self.assertIsNotNone(titles, "結末で決まる物の決まった題の表 OUTCOME_TITLES が無い")
        title = titles["人が確かめる物"]
        top = text.split("\n## ", 1)[0].splitlines()
        self.assertIn(f"- {title}（人が確かめる物）", top)
        self.assertNotIn("- 人が確かめる物", top, "種の名だけの行には戻らない")
        self.assertIn("  - 素材 a: 測れていない", self.section(text, "## 1. 人が決めること").splitlines())

    def test_same_fixed_title_rows_fold_into_one_with_the_count(self):
        """差し込み口の無い同じ字の題を持つ行は、頭で 1 行にまとめて件数を添える。件数はその種の数え（tallied）が在ればそれ、無ければ行の数。
        題の違う行や題の無い行は畳まない"""
        fixed = "守ると決めたファイルに当たった差分を確かめる"
        asks = [{"kind": "守りの種", "text": f"差分 {n}", "title": fixed} for n in range(3)]
        _, text = self.build(asks=asks, tallied={"守りの種": 7})
        top = text.split("\n## ", 1)[0].splitlines()
        rows = [x for x in top if fixed in x]
        self.assertEqual(len(rows), 1, top)
        self.assertEqual(rows, [f"- {fixed}（守りの種、7 件）"])
        self.assertIn("人が決めること: 7 件（", text, "和の件数と畳んだ行の件数が合う")
        _, text = self.build(asks=asks)
        self.assertIn(f"- {fixed}（守りの種、3 件）", text.split("\n## ", 1)[0].splitlines(), "tallied が無ければ行の数")
        mixed = [{"kind": "k", "text": "a", "title": "題 A"}, {"kind": "k", "text": "b", "title": "題 B"}, {"kind": "k", "text": "c", "title": "題 A"},
                 {"kind": "k", "text": "d"}]
        _, text = self.build(asks=mixed)
        self.assertEqual([x for x in text.split("\n## ", 1)[0].splitlines() if x.startswith("- ")], ["- 題 A（k、2 件）", "- 題 B（k）", "- k"])


class HeadFor19b99137Case(Base):
    """run 19b99137 の頭（初見の読み手が 3 回とも通さなかった）の止まる所 5 つを、yes/no で縛る。入力の形は記録の facts と同じ"""
    KIND = "直しの途中で AI が自分で決めずに人に回した物（壊すと分かって通した理由。役だけで決めた代償なので人が確かめる）"
    LONG = "lib/x.py fn_name: 単独の行を残った印と数え、正当なファイルを拒む: 壊すと分かって通した——（以下、修正役の返りの長い文）"
    ENV = notice("user_env")
    HEAD = {"before": ["無人の run で推しを採って通した承認ノード: 修正前の承認ノード（推し 3 件。中身は「1. 人が決めること」のセクション）"],
            "stopped": ["最後の承認ノードを開ける所が止めた: 無人の run で承認ノードを開くはずだった（開かずに止めた）",
                        "開けた理由: 書き換えを許したテストを触った（1 件）・直しの途中で AI が自分で決めずに人に回した物が在る（1 件）"],
            "after": [ENV], "notices": []}

    def top(self, **over):
        _, text = self.build(outcome="needs_human", stop="gate-final:needs_human", asks=[{"kind": self.KIND, "text": self.LONG}],
                             head=self.HEAD, decisions={"before": [f"{self.KIND}: 1 件", f"  - {self.LONG}"], "after": [], "outside": []}, **over)
        return text, text.split("\n## ", 1)[0]

    def test_one_decision_is_counted_once_in_the_head(self):
        _, top = self.top()
        self.assertIn("人が決めること: 1 件", top)
        self.assertNotIn("推し", top, "推しと開けた理由は別の件数として頭に並べない")
        self.assertNotIn("開けた理由", top)
        counted = [x for x in top.splitlines() if re.search(r"\d+ 件", x)]
        self.assertEqual(len(counted), 2, "数は「起きたこと」と「人が決めること」の同じ 1 つだけ: " + top)
        self.assertTrue(all("1 件" in x for x in counted))

    def test_the_happened_line_is_one_short_sentence_without_inner_names(self):
        _, top = self.top()
        line = next(x for x in top.splitlines() if x.startswith("起きたこと: "))
        self.assertEqual(line, "起きたこと: 人の判断を待ったまま止まった。人が決めること 1 件が残っている")
        self.assertNotIn("承認ノード", top)
        self.assertNotIn("needs_human", top, "結末の英字の語は頭に出さない")
        self.assertNotIn("封じ", top)

    def test_the_long_text_and_inner_names_stay_below_the_head(self):
        text, top = self.top()
        self.assertNotIn("fn_name", top)
        self.assertNotIn("修正役", top, "AI の役名は頭に出さない")
        self.assertNotIn("壊すと分かって通した", top)
        self.assertIn("- 直しの途中で AI が自分で決めずに人に回した物", top.splitlines())
        self.assertIn(self.LONG, self.section(text, "## 1. 人が決めること"))
        stop = self.section(text, "## 2. 止めたか")
        self.assertIn("推し 3 件", stop)
        self.assertIn("開けた理由", stop)

    def test_notice_only_line_starts_with_a_word_that_says_so(self):
        _, top = self.top()
        [line] = [x for x in top.splitlines() if userenv.NOTE in x]
        self.assertEqual(line, M.head.notice_row(M.head.Notice.USER_ENV), "利用者の環境の種の文は lib の userenv の句")
        self.assertTrue(line.startswith("知らせ（決めることではない）: "))
        self.assertNotIn(userenv.NOTE, next(x for x in top.splitlines() if x.startswith("起きたこと: ")))

    NEITHER = "急ぎ: この run の段はどれも落ちていない。試験の外で対象が動くかは、機械は確かめていない。"

    def test_urgent_line_of_a_pr_run_says_the_default_branch_was_not_touched(self):
        for act, said in (("pr", "PR を作っただけで、対象の既定の枝には当てていない"), ("stopped", "PR は作らず、対象の既定の枝には当てていない"),
                          ("unconfirmed", "PR を作ったかは確かめられていないが、対象の既定の枝には当てていない")):
            with self.subTest(act=act):
                _, top = self.top(apply={"sealed": True, "placed": True, "pr": {"act": act, "url": "u", "number": 1, "reason": "訳"}})
                self.assertIn(f"{self.NEITHER}{said}", top.splitlines())
        _, top = self.top(apply={"sealed": True, "placed": True})
        self.assertIn(f"{self.NEITHER}対象のリポジトリには何も当てていない", top.splitlines())
        for word in ("壊れた所は無く", "直ったかは分からない"):
            self.assertNotIn(word, top, "機械が知らない対象の状態を言い切らず、1 行目の『直して、最後のテストまで通った』と食い違わない")

    def test_a_pr_without_its_place_is_unconfirmed_in_both_head_lines(self):
        """出口の語が pr でも PR の在りかか番号が読めない run は、差分の行も急ぎの行も PR を作ったと確かめられなかったと言う（頭の中で食い違わない）"""
        for pr in ({"act": "pr", "url": None, "number": None}, {"act": "pr", "url": "u", "number": None}, {"act": "pr", "url": "", "number": 1}):
            with self.subTest(pr=pr):
                _, top = self.top(apply={"sealed": True, "placed": True, "pr": pr})
                lines = top.splitlines()
                self.assertTrue(any(x.startswith("差分を当ててよいか: PR を作ったと確かめられなかった。") for x in lines), top)
                self.assertIn(f"{self.NEITHER}PR を作ったかは確かめられていないが、対象の既定の枝には当てていない", lines)

    def test_apply_command_is_said_with_what_it_does_in_the_same_line(self):
        _, top = self.top(apply={"sealed": True, "placed": False})
        line = next(x for x in top.splitlines() if x.startswith("差分を当ててよいか: "))
        self.assertIn("当てる命令: bin/apply", line)
        self.assertIn("--allow-stopped は止まった run の差分を当てる指定", line)
        self.assertLess(line.index("決めてから当てる"), line.index("当てる命令: bin/apply"), "命令は答えの文の後ろに置く")
        self.assertNotRegex(line, r"（[^）]*bin/apply", "命令は括弧に詰めない")

    def test_urgency_comes_only_from_facts_the_machine_holds(self):
        _, top = self.top()
        self.assertEqual([x for x in top.splitlines() if x.startswith("急ぎ: ")], [f"{self.NEITHER}対象のリポジトリには何も当てていない"])
        _, top = self.top(run={**OK_RUN, "failed": ["fix__tdd"], "errors": {"fix__tdd": "x"}})
        failed = "急ぎ: 壊れた所がある。この run の段が落ちた。対象のリポジトリには何も当てていない"
        self.assertEqual([x for x in top.splitlines() if x.startswith("急ぎ: ")], [failed])
        _, text = self.build(outcome="interrupted", stop="fix__tdd:node-error")
        ended = f"急ぎ: 壊れた所がある。この run の結末: {report.OUTCOME_WORDS['interrupted']}。対象のリポジトリには何も当てていない"
        self.assertEqual([x for x in text.split("\n## ", 1)[0].splitlines() if x.startswith("急ぎ: ")], [ended])
        for line in (f"{self.NEITHER}対象のリポジトリには何も当てていない", failed, ended):
            for word in ("ノード", "壊れた所は無く", "直ったかは分からない"):
                self.assertNotIn(word, line)
        _, top = self.top(run={**OK_RUN, "ok": False})
        self.assertFalse([x for x in top.splitlines() if x.startswith("急ぎ: ")], "run の記録が読めない時は急ぎを推して書かない")

    def test_outcome_asks_join_the_head_and_the_decisions_section(self):
        left = [{"where": "素材 a", "text": "測れていない", "unmeasured": True}]
        _, text = self.build(outcome="fixed_needs_check", left=left, decisions={"before": ["前の行"], "after": ["後の行"], "outside": ["外の行"]})
        self.assertIn("人が決めること: 1 件", text)
        titles = getattr(M.outcome, "OUTCOME_TITLES", None)
        self.assertIsNotNone(titles, "結末で決まる物の決まった題の表 OUTCOME_TITLES が無い")
        self.assertIn(f"- {titles['人が確かめる物']}（人が確かめる物）", text.split("\n## ", 1)[0].splitlines())
        body = self.section(text, "## 1. 人が決めること").splitlines()
        self.assertEqual(body[:5], ["- 前の行", "- 人が確かめる物: 1 件", "  - 素材 a: 測れていない", "- 後の行", "- 次の run に渡す物: 0 件"])
        self.assertIn("- 外の行", body)

    def test_apply_answers(self):
        sealed = {"sealed": True, "placed": True}
        _, text = self.build(apply=sealed)
        self.assertIn(f"差分を当ててよいか: 当ててよい。当てる命令: bin/apply {RUN_ID}", text)
        _, text = self.build(apply=sealed, outcome="round_limit", proved=False)
        self.assertIn("差分を当ててよいか: 確かめてから当てる。この run の結末: 決めた回数のうちに直しきれずに止まった。"
                      f"当てる命令: bin/apply {RUN_ID}", text)
        self.assertNotIn("周", text.split("\n## ", 1)[0], "round_limit の結末は『周』を使わない言い方")
        _, text = self.build(apply={"sealed": True, "placed": False, "redesign": "redesign-needed"})
        top = text.split("\n## ", 1)[0]
        self.assertNotIn("redesign-needed", top, "見直しの状態の英字は頭に出さない")
        self.assertNotIn("独立の目", top, "独立の目は工場の語")
        self.assertIn("差分を当ててよいか: 当てない。修正に関わっていない AI の見直しが「作り直しが要る」と言った run の差分は、bin/apply でも当てない", top)
        _, text = self.build(apply={"sealed": True, "placed": False}, asks=[{"kind": "k", "text": "t"}])
        self.assertIn(f"差分を当ててよいか: 人が決めること 1 件を決めてから当てる。差分を置かずに止まった run なので、当てる命令: bin/apply {RUN_ID} "
                      "--allow-stopped（--allow-stopped は止まった run の差分を当てる指定）", text)
        _, text = self.build(apply={**sealed, "pr": {"act": "pr", "url": "https://example.test/pr/1", "number": 1, "is_draft": True}})
        self.assertIn("差分を当ててよいか: PR を作った: https://example.test/pr/1（下書きの PR #1。merge は対象のレビューと決まりに任せる）", text)
        for act, said in (("stopped", "PR を作らずに止めた。対象の既定の枝には当てていない。当ててよい。当てる命令"),
                          ("unconfirmed", "PR を作ったと確かめられなかった。対象の既定の枝には当てていない。当ててよい。当てる命令")):
            _, text = self.build(apply={**sealed, "pr": {"act": act, "reason": "push が拒まれた"}})
            self.assertIn(f"差分を当ててよいか: {said}: bin/apply {RUN_ID}", text)
            self.assertNotIn("push が拒まれた", text, "PR を作らなかった訳は merge の節の 1 か所だけ。頭にも 2 節にも写さない")

    def test_apply_lines_for_a_stopped_run(self):
        _, text = self.build(outcome="stopped_by_human", stop="start-answer:reject", apply={"sealed": True, "placed": False, "said": "やめる\n理由"})
        body = self.section(text, "## 1. 人が決めること")
        self.assertIn(f"- 止まった run: {report.OUTCOME_WORDS['stopped_by_human']}（start-answer:reject）で止まった: 「やめる 理由」", body)
        self.assertIn(f"- 差分を対象に当てる: bin/apply {RUN_ID} --allow-stopped", body)
        _, text = self.build(apply={"sealed": False})
        self.assertIn("- 差分を対象に当てる: 無い（差分を封じていない）", text)


LINE_FACTS = kit.BLOCKS / "line" / "src" / "facts.py"
ASK_HEADS = ("PROTECTED_HITS_HEAD", "MEANS_ASK_HEAD", "EYE_ASK_HEAD", "CONFLICT_ASK_HEAD", "UNCOMPARED_HEAD", "BACKED_OUT_HEAD",
             "UNRESTORED_GROUP_HEAD")
ASK_KINDS = ("保留にしたままの問い", "修正前の問い", "直しの対象に戻せなかった項目", "前提の検算が人に上げた物")   # facts.py が定数にせず直に書く種の頭の言い方


def line_facts_heads() -> list:
    """line の facts.py が人が決める物の種（asks の kind）に使う頭の言い方（定数の字。facts.py を読み込まず、構文木から読む）"""
    tree = ast.parse(LINE_FACTS.read_text(encoding="utf-8"))
    found = {n.targets[0].id: n.value.value for n in tree.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    return [found[name] for name in ASK_HEADS]


def table_orphans(enum, table: dict) -> list:
    """列挙の値と表の鍵の食い違い（表に行が無い値・列挙に無い鍵）"""
    return [f"表に行が無い: {k}" for k in enum if k not in table] + [f"列挙に無い鍵: {k!r}" for k in table if not isinstance(k, enum)]


def slot_problems(table: dict, slots: dict, allowed: tuple) -> list:
    """表の各行の文の差し込みの名の集合と、その行の差し込み口の型の欄の集合の食い違い。型の欄は読み手の世界の型だけ"""
    out = []
    for key, text in table.items():
        named = {name for _, name, _, _ in string.Formatter().parse(text) if name}
        shape = slots.get(key)
        if shape is None:
            out.append(f"{key}: 差し込み口の型が無い")
            continue
        if named != set(shape._fields):
            out.append(f"{key}: 文の差し込み {sorted(named)} と型の欄 {list(shape._fields)} が違う")
        out += [f"{key}.{name}: 許す型でない（{kind}）" for name, kind in shape.__annotations__.items() if kind not in allowed]
    return out


def unreadable(head_text: str) -> list:
    """機械の報告の頭の行のうち、表の行に読み戻せない行"""
    return [x for x in head_text.splitlines() if x.strip() and M.head.parse(x) is None]


def pack_hits(text: str) -> dict:
    """text にある語の表（glossary.json）の語と回数（人に向けた報告で言い換える物と同じ当て方）"""
    return M.writer.plain_words(text)[1]


class HeadTableCase(Base):
    """頭の機械の行の文面表（head.py）全体の検査。どれも、わざと孤児の行か表の外の行を入れると赤になることを、同じ試験の中で見せる"""
    def head(self):
        """頭の文面表の部品。無い版では、読み込みでなく試験の中の検査で落とす"""
        self.assertIsNotNone(M.head, "頭の文面表 workflows/report/src/head.py が無い")
        return M.head

    def sample_slots(self, kind) -> dict:
        shape = M.head.SLOTS[kind]
        return {name: (2 if ann is int else "サンプル") for name, ann in shape.__annotations__.items()}

    def scenarios(self):
        """結末・差分の状態・PR の道・急ぎ・知らせ・人が決める物を変えた build の引数と、差分の状態を変えたどの場面にも出口の語 pr の道で
        PR を作らずに止めた（act stopped）写しと PR を作ったと確かめられなかった（act unconfirmed）写しを足した物。全部の行の種に当たることは
        試験の中で照らす"""
        for kw in self.base_scenarios():
            yield kw
            if self.pr_variable(kw):
                yield from (self.pr_variant(kw, act) for act in self.PR_SAID)

    # PR の道で PR を作れなかった・作ったと確かめられなかった run の、差分の答えの前に足す句
    PR_SAID = {"stopped": "PR を作らずに止めた。対象の既定の枝には当てていない。",
               "unconfirmed": "PR を作ったと確かめられなかった。対象の既定の枝には当てていない。"}

    @staticmethod
    def pr_variable(kw) -> bool:
        return "apply" in kw and "pr" not in kw["apply"]

    @staticmethod
    def pr_variant(kw, act: str) -> dict:
        """場面 kw を、出口の語 pr の道で merge が PR を作る前に止めた（stopped）か、PR を作ったと確かめられなかった（unconfirmed）run にした写し"""
        return {**kw, "apply": {**kw["apply"], "pr": {"act": act, "reason": "訳"}}}

    def base_scenarios(self):
        sealed = {"sealed": True, "placed": True}
        notices = [notice(n.value, "訳", **self.sample_slots(n)) for n in M.head.Notice]
        pr = {"url": "https://example.test/pr/1", "number": 1}
        kinds = [*line_facts_heads(), *ASK_KINDS, "直しの途中で AI が自分で決めずに人に回した物（壊すと分かって通した理由）"]
        asks = [{"kind": k, "text": f"本文 {n}", **({"title": "題 A\n二行目"} if n == 0 else {})} for n, k in enumerate(kinds)]
        yield {"apply": sealed}
        yield {"request_texts": ["依頼の 1 行目"]}
        yield {"request_texts": ["依頼の 1 行目\n改行を含む", "依頼の 2 行目", "依頼の 3 行目"]}
        yield {"apply": {"sealed": False}}
        yield {"apply": {"sealed": True, "placed": False}}
        yield {"apply": {"sealed": True, "placed": False, "redesign": "redesign-needed"}}
        yield {"apply": {"sealed": True, "placed": False}, "asks": asks[:1]}
        yield {"apply": sealed, "asks": asks}
        yield {"apply": sealed, "asks": asks[:1], "tallied": {kinds[0]: 5}}
        yield {"apply": sealed, "asks": [{"kind": "種 k", "text": "a"}, {"kind": "種 k", "text": "b"}]}
        for act in ("pr", "stopped", "unconfirmed"):
            yield {"apply": {**sealed, "pr": {**pr, "act": act, "reason": "訳"}}}
        yield {"apply": {**sealed, "pr": {**pr, "act": "pr", "is_draft": True}}}
        yield {"apply": {**sealed, "pr": {"act": "pr", "url": None, "number": None}}}
        yield {"head": {"before": [], "stopped": [], "after": notices[:6], "notices": notices[6:]}}
        yield {"carry": {"findings": [{"where": "a", "text": "b"}], "prior": [], "drafts": [], "constraints": []}}
        for outcome in report.OUTCOMES:
            yield {"outcome": outcome, "stop": "x:y", "apply": sealed, "left": [{"where": "素材 a", "text": "測れていない", "unmeasured": True}]}
        for run in ({**OK_RUN, "failed": ["fix__tdd"], "errors": {"fix__tdd": "x"}}, {**OK_RUN, "absorbed": [{"node": "eyes__r1", "error": ""}]},
                    {**OK_RUN, "ok": False}):
            yield {"run": run}

    def heads(self):
        """(行の見出しの字, 機械の報告の頭) を、場面ごとと、書き手が落ちた場合も足して"""
        for kw in self.scenarios():
            _, text = self.build(**kw)
            yield M.writer.machine_head(text)
        for quota in (True, False):
            _, text = self.build()
            M.writer.note_writer_fell(self.place / "report.md", {"error": "Loop-group node failed: x", "quota": quota}, run_id=RUN_ID)
            yield M.writer.machine_head((self.place / "report.md").read_text(encoding="utf-8"))

    def title_module(self):
        """題の型の字の部品。無い版では、読み込みでなく試験の中の検査で落とす"""
        title = getattr(M, "title", None)
        self.assertIsNotNone(title, "題の型の字の部品 workflows/report/src/title.py が無い")
        return title

    REQUEST_SETS = ([], ["依頼の 1 行目"], ["依頼の 1 行目\n改行を含む", "依頼の 2 行目", "依頼の 3 行目"], ["  ", "\n\t"], ["  ", "依頼 A", ""],
                    ["  A \t B  ", "C"])

    def test_title_writers_outside_build_match_the_title_row(self):
        """build の外で題を書く所（予備の機械の報告・訳だけのファイル・題の部品の render）の 1 行目は、依頼の字が 0 件・1 件・2 件以上・空白だけの
        どれでも machine.title_row と同じ字で、head.parse で題の行に読み戻せる。畳み方は lib の one_line と同じ字にする"""
        title = self.title_module()
        H = self.head()
        titles = {H.Line.RUN_TITLE, H.Line.REQUEST_TITLE, H.Line.REQUEST_TITLE_MORE}
        for n, requests in enumerate(self.REQUEST_SETS):
            want = M.machine.title_row(RUN_ID, requests)
            with self.subTest(requests=requests):
                self.assertIn(H.parse(want).kind, titles)
                made = {"render": title.render(RUN_ID, requests)}
                (self.place / f"fb{n}").mkdir()
                with self.run.env():
                    made["fallback_report"] = M.machine.fallback_report(self.place / f"fb{n}", "訳", RUN_ID, requests).read_text(encoding="utf-8").splitlines()[0]
                    made["unwritten"] = M.steps.unwritten(self.place / f"un{n}", "u.md", "訳", RUN_ID, requests).read_text(encoding="utf-8").splitlines()[0]
                for writer, got in made.items():
                    self.assertEqual(got, want, writer)
                    self.assertEqual(H.parse(got), H.parse(want), writer)
        for text in ("  A \t B\n C ", "", "   ", "改行\r\n入り", "全角\u3000空白"):
            self.assertEqual(title.fold(text), oneline.one_line(text), repr(text))

    def test_no_title_text_outside_the_title_module(self):
        """題の型の字「報告（run」を持つのは title.py だけ（scripts と src の .py）"""
        found = sorted(str(p.relative_to(base.BLOCK)) for folder in ("scripts", "src") for p in (base.BLOCK / folder).glob("*.py")
                       if "報告（run" in p.read_text(encoding="utf-8"))
        self.assertEqual(found, ["src/title.py"])

    def test_unreadable_request_input_falls_to_the_run_id_title(self):
        """依頼の字が読めない入力（壊れた JSON・別の run を指す pointer・無いファイルのパス・字の配列でない request_texts）では、
        requests_in は誤りを上げずに空を返し、題は run の id だけの行になる"""
        title = self.title_module()
        place = self.run.artifacts
        (place / "broken.json").write_text("{壊れた", encoding="utf-8")
        (place / "notlist.json").write_text(json.dumps({"request_texts": "文字列"}), encoding="utf-8")
        (place / "mixed.json").write_text(json.dumps({"request_texts": ["a", 3]}), encoding="utf-8")
        (place / "scalar.json").write_text("3", encoding="utf-8")
        other = json.dumps({"type": "archon_artifact", "run_id": "other-run", "path": "broken.json"})
        inputs = {"broken file": str(place / "broken.json"), "broken value": "{壊れた", "other run pointer": other,
                  "missing path": str(place / "nothing.json"), "request_texts not a list": json.dumps({"request_texts": "文字列"}),
                  "request_texts mixed": json.dumps({"request_texts": ["a", 3]}), "not an object": "[1]", "scalar file": str(place / "scalar.json"),
                  "string file": str(place / "notlist.json"), "mixed file": str(place / "mixed.json"), "empty": "", "none": None}
        with self.run.env():
            for name, raw in inputs.items():
                with self.subTest(name):
                    got = title.requests_in(raw)
                    self.assertEqual(tuple(got), ())
                    self.assertEqual(title.render(RUN_ID, got), M.machine.title_row(RUN_ID, []))
            readable = title.requests_in(json.dumps({"request_texts": ["依頼 A"]}))
            self.assertEqual(tuple(readable), ("依頼 A",), "読める入力は読む")

    def test_pr_stopped_keeps_the_apply_answer(self):
        """出口の語 pr の道で PR を作らずに止めた・PR を作ったと確かめられなかった run の「差分を当ててよいか」の行は、PR の道でない同じ場面の答え
        （差分が無い・作り直しが要るので当てない・決めてから当てる・--allow-stopped つき…）を変えず、PR の道の結果を前に足すだけ（bin/apply が
        断る命令を案内しない）"""
        lead = "差分を当ててよいか: "

        def apply_row(kw) -> str:
            _, text = self.build(**kw)
            [row] = [x for x in M.writer.machine_head(text).splitlines() if x.startswith(lead)]
            return row

        for kw in self.base_scenarios():
            if self.pr_variable(kw):
                base = apply_row(kw)
                for act, said in self.PR_SAID.items():
                    with self.subTest(act=act, apply=kw["apply"], asks=bool(kw.get("asks")), outcome=kw.get("outcome")):
                        self.assertEqual(apply_row(self.pr_variant(kw, act)), lead + said + base.removeprefix(lead))

    def test_every_line_and_notice_has_exactly_one_row(self):
        H = self.head()
        self.assertEqual(table_orphans(H.Line, H.TABLE), [])
        self.assertEqual(table_orphans(H.Notice, H.NOTICES), [])
        self.assertEqual(set(H.SLOTS), {*H.Line, *H.Notice}, "差し込み口の型の表も、どの値にもちょうど 1 行")
        self.assertEqual(table_orphans(H.Notice, H.NOTICE_TOPIC), [])
        with mock.patch.dict(H.TABLE, {"orphan": "孤児の行"}):
            self.assertEqual(table_orphans(H.Line, H.TABLE), ["列挙に無い鍵: 'orphan'"])
        short = {k: v for k, v in H.NOTICES.items() if k is not H.Notice.USER_ENV}
        self.assertEqual(table_orphans(H.Notice, short), [f"表に行が無い: {H.Notice.USER_ENV}"])

    def test_row_text_names_exactly_its_slots(self):
        H = self.head()
        for table in (H.TABLE, H.NOTICES):
            self.assertEqual(slot_problems(table, H.SLOTS, H.SLOT_TYPES), [])
        self.assertEqual(slot_problems({H.Line.RUN_TITLE: "# 報告（run {run}）{extra}"}, H.SLOTS, H.SLOT_TYPES),
                         ["Line.RUN_TITLE: 文の差し込み ['extra', 'run'] と型の欄 ['run'] が違う"])
        self.assertEqual(slot_problems({H.Line.RUN_TITLE: "# 報告"}, H.SLOTS, H.SLOT_TYPES), ["Line.RUN_TITLE: 文の差し込み [] と型の欄 ['run'] が違う"])

        class Loose(typing.NamedTuple):
            run: str
        self.assertEqual(slot_problems({H.Line.RUN_TITLE: "{run}"}, {H.Line.RUN_TITLE: Loose}, H.SLOT_TYPES), ["Line.RUN_TITLE.run: 許す型でない（<class 'str'>）"],
                         "素の字の差し込み口は読み手の世界の値でない")

    def test_every_head_line_of_the_built_report_is_a_table_row(self):
        H = self.head()
        seen = set()
        for head_text in self.heads():
            self.assertEqual(unreadable(head_text), [], head_text)
            for line in head_text.splitlines():
                if line.strip():
                    row = H.parse(line)
                    seen.add(row.kind)
                    self.assertEqual((H.render if isinstance(row.kind, H.Line) else H.notice_row)(row.kind, row.slots), line)
        self.assertEqual(seen, {*H.Line, *H.Notice}, "場面が表のどの行にも当たる")
        _, blank = self.build(request_texts=[" \n\t ", ""])
        self.assertEqual(H.parse(blank.splitlines()[0]).kind, H.Line.RUN_TITLE, "空白と改行だけの依頼は id だけの題")
        self.assertEqual(blank.splitlines()[0], f"# 報告（run {RUN_ID}）")
        self.assertEqual(unreadable("# 報告（run x）\n\n起きたこと: 自由な字で組んだ行"), ["起きたこと: 自由な字で組んだ行"], "表の外の行は赤")
        self.assertEqual(unreadable("# 報告（run x）\n\n知らせ（決めることではない）: 表に無い知らせ"), ["知らせ（決めることではない）: 表に無い知らせ"])

    def test_notice_kinds_match_the_facts_schema(self):
        self.head()
        shape = json.loads((kit.SHARED / "schemas" / "facts.schema.json").read_text(encoding="utf-8"))["properties"]["head"]["properties"]
        kinds = {n.value for n in M.head.Notice}
        for where in ("after", "notices"):
            self.assertEqual(set(shape[where]["items"]["properties"]["kind"]["enum"]), kinds, where)
            self.assertEqual(shape[where]["items"]["required"], ["kind", "slots", "text"])
        bad = {"kind": "unknown", "slots": {}, "text": ""}
        with self.assertRaises(ValueError):
            M.facts_in.read({"head": {"after": [bad]}})
        with self.assertRaises(ValueError):
            self.build(head={"notices": [notice("answer_redirected", "訳")]})   # 差し込み口の欄が足りない

    def test_head_text_uses_no_pack_term(self):
        """頭の全文（場面ごとの差し込み口の値と、人が決めることの行の種の頭の言い方を含む）・表の文・結末の言い方に、語の表の語が無い。例外の一覧は持たない"""
        H = self.head()
        self.assertTrue(M.writer.pack_terms(), "語の表を読めている")
        for head_text in self.heads():
            self.assertEqual(pack_hits(head_text), {}, head_text)
        self.assertEqual(pack_hits("\n".join([*H.TABLE.values(), *H.NOTICES.values(), *H.HANDOVER_WORDS.values()])), {})
        self.assertEqual(pack_hits("\n".join(report.OUTCOME_WORDS.values())), {})
        # plain_words は漢字に続く片仮名で始まる語（出力ノードの中のノード）を飛ばすので、字のまま含むかも別に照らす
        everything = "\n".join([*H.TABLE.values(), *H.NOTICES.values(), *H.HANDOVER_WORDS.values(), *report.OUTCOME_WORDS.values(),
                                *self.heads()])
        self.assertEqual(sorted(r["term"] for r in M.writer.pack_terms() if r["term"] in everything), [])
        self.assertTrue(pack_hits("独立の目が止めた。守りのパスに当たった差分"), "検査が語を見つける（赤になる形）")
        _, text = self.build(asks=[{"kind": "守りのパスに当たった差分", "text": "t"}])
        self.assertTrue(pack_hits(M.writer.machine_head(text)))

    def test_render_refuses_a_key_outside_the_table(self):
        H = self.head()
        run = H.RunSlot(H.RunId("r"))
        for key, slots in (("title", run), ("not a line", run), (H.Notice.USER_ENV, H.Plain()), (None, None),
                           (H.Line.RUN_TITLE, None), (H.Line.RUN_TITLE, H.RunSlot("素の字")), (H.Line.RUN_TITLE, H.CountSlot(1)), (H.Line.RUN_TITLE, ("r",)),
                           (H.Line.ASK_KIND, H.KindSlot("素の字")), (H.Line.DECIDE, H.CountSlot(True)), (H.Line.DECIDE, H.CountSlot("2"))):
            with self.subTest(key=key, slots=slots), self.assertRaises(TypeError):
                H.render(key, slots)
        for key, slots in (("user_env", H.Plain()), (H.Line.RUN_TITLE, run), (H.Notice.ANSWER_REDIRECTED, H.QuoteSlot("素の字")),
                           (H.Notice.SUITE_BROKEN, H.GroupSlot(H.GroupId("g")))):
            with self.subTest(notice=key), self.assertRaises(TypeError):
                H.notice_row(key, slots)
        with mock.patch.dict(H.TABLE, clear=False):
            del H.TABLE[H.Line.RUN_TITLE]
            with self.assertRaises(TypeError):
                H.render(H.Line.RUN_TITLE, run)
        self.assertEqual(H.render(H.Line.RUN_TITLE, run), "# 報告（run r）")


class SectionsCase(Base):
    HEADINGS = ["1. 人が決めること", "2. 止めたか", "3. 見る所", "4. 役が呼んだ道具", "直した所", "空の節", "次の run に引き継ぐ落ちた理由", "模型", "費用",
                "注意（読めなかった物）"]

    def test_headings_in_order(self):
        _, text = self.build()
        self.assertEqual([x.removeprefix("## ") for x in text.splitlines() if x.startswith("## ")], self.HEADINGS)
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))

    def test_lines_get_bullets_and_indented_lines_stay(self):
        _, text = self.build()
        self.assertEqual(self.section(text, "## 直した所"), "- 単位 u1: 直した\n  内訳 a")

    def test_empty_section_is_kept_with_one_line(self):
        _, text = self.build()
        self.assertEqual(self.section(text, "## 空の節"), "- この段は報告の行を返していない")

    def test_stop_section(self):
        run = {**OK_RUN, "failed": ["fix__tdd"], "errors": {"fix__tdd": "boom\n二行目"},
               "retried": [{"node": "judge", "failures": 2, "error": "timeout"}], "absorbed": [{"node": "eyes__r1", "error": ""}]}
        _, text = self.build(run=run, outcome="interrupted", stop="fix__tdd:node-error", problems=["入力が読めない"],
                             stop_lines={"before": ["承認ノード start: 開かなかった"], "after": ["出力の続きが切れている: x"]})
        body = self.section(text, "## 2. 止めたか").splitlines()
        self.assertEqual(body[:3], ["- 結末: run が途中で終わった（interrupted）", "- 止めた段と理由の語: fix__tdd:node-error",
                                    "- 承認ノード start: 開かなかった"])
        self.assertIn("- run が途中で終わった: ノード fix__tdd が落ちた（誤り: boom）", body)
        self.assertIn("- 前の試みで落ち、続きで済んだノード: judge（落ちた回 2。最後の誤り: timeout）", body)
        self.assertIn("- 落ちたが、メイングラフが宣言のとおり受け止めたノード: eyes__r1（誤り: （誤りの文が無い））", body)
        self.assertEqual(body[-2:], ["- 出力の続きが切れている: x", "- 結果を名乗れない訳: 入力が読めない"])

    def test_where_lines_open_files_and_name_the_unopenable(self):
        diff = self.run.repo / "a.patch"
        diff.write_text("x", encoding="utf-8")
        judged = "json(shared:judgment.schema.json)"
        sections = [{"title": "直した所", "lines": ["x"], "files": [{"label": "差分", "ref": str(diff), "form": "file"},
                                                                  {"label": "試験の記録", "ref": "/no/such/file", "form": "file"}]},
                    {"title": "目的", "lines": ["y"], "files": [{"label": "判定", "ref": self.run.pointer("here.json"), "form": judged},
                                                              {"label": "形の違う判定", "ref": self.run.pointer("off.json"), "form": judged}]}]
        (self.place / "here.json").write_text('{"units": []}', encoding="utf-8")
        (self.place / "off.json").write_text("{}", encoding="utf-8")
        _, text = self.build(sections)
        where = self.section(text, "## 3. 見る所").splitlines()
        self.assertEqual(where[0], f"- 差分（直した所）: {diff}")
        self.assertTrue(where[1].startswith("- 試験の記録（直した所）: 開けない（file の入力のファイル /no/such/file が無い"), where[1])
        self.assertEqual(where[2], f"- 判定（目的）: {self.place / 'here.json'}", "JSON のファイルは行の form で照らして開く")
        self.assertTrue(where[3].startswith("- 形の違う判定（目的）: 開けない（"), where[3])
        self.assertIn("units", where[3], "行の form の形に合わない中身は開かずに訳を名指す")
        self.assertIn(where[1].removeprefix("- "), self.section(text, "## 注意（読めなかった物）"), "開けない訳は注意にも載る")

    def test_no_files_is_named(self):
        _, text = self.build()
        self.assertEqual(self.section(text, "## 3. 見る所"), "- 出力にポインタが無い")

    def test_model_cost_and_notes(self):
        _, text = self.build(outcome_parts={"gate": "最後の承認ノード final: continue", "eyes": "独立の目: R1 pass", "data": "データ D"},
                             notes=["読めなかった物 N"], carry={"prior": [{"where": "w", "text": "t"}]})
        model = self.section(text, "## 模型").splitlines()
        self.assertEqual(model[0], "- fix__tdd: sonnet（effort: low）")
        self.assertEqual(model[1], "- 結末: 直して、最後のテストまで通った（fixed）／最後の承認ノード final: continue／独立の目: R1 pass／"
                                   "次の run に渡す物: 0 件／持ち越した失敗: 1 件／データ D")
        cost = self.section(text, "## 費用")
        self.assertIn("費用の合計: $0.5000", cost)
        self.assertIn("- fix__tdd: $0.5000・1.5 分", cost)
        self.assertEqual(self.section(text, "## 注意（読めなかった物）"), "- 読めなかった物 N")

    def test_unreadable_record_is_a_note_and_a_cost_line(self):
        run = M.transcript.facts(None)
        got = M.facts_in.read(base.READY)
        built = M.machine.build([], got, "fixed", "", run, place=self.place, run_id=RUN_ID, run_why="記録が無い")
        text = built["report"].read_text(encoding="utf-8")
        self.assertIn("- 記録が無い", self.section(text, "## 注意（読めなかった物）"))
        self.assertIn("- 費用: 取れない（記録が無い）", text)
        self.assertIn("- run の記録が読めない", self.section(text, "## 模型"))


class CarryCase(Base):
    def test_next_request_and_prior_failures_are_written_and_named(self):
        carry = {"findings": [{"where": "stats.py:4", "text": "mean が 3 を返さない"}], "prior": [{"where": "受け付け 計画", "text": "拒まれた"}],
                 "drafts": [], "constraints": [{"text": "呼び手は 1 つ", "measured_how": "grep", "kind": "実測"}]}
        built, text = self.build(carry=carry)
        doc = base.read(built["next_request"])
        self.assertEqual(doc["findings"], carry["findings"])
        self.assertEqual(doc["prior_failures"], carry["prior"])
        self.assertEqual(base.read(built["prior_failures"]), carry["prior"])
        self.assertEqual((built["next_request"].name, built["prior_failures"].name), ("next-request.json", "prior-failures.json"))
        body = self.section(text, "## 1. 人が決めること")
        self.assertIn("- 次の run に渡す物: 2 件（next-request.json）", body)
        self.assertIn("- 次の run の制約に足す実測（前提の検算）: 呼び手は 1 つ", body)
        self.assertIn("1 件（prior-failures.json に書いた。次の run の依頼の下書き next-request.json の prior_failures にも載せた", text)

    def test_nothing_carried_writes_no_file(self):
        built, _ = self.build()
        self.assertEqual((built["next_request"], built["prior_failures"]), (None, None))
        self.assertFalse((self.place / "next-request.json").exists())

    def test_drafts_get_one_line_and_the_file_name(self):
        carry = {"findings": [], "prior": [], "drafts": [{"question": "q", "text": "", "draft": True, "source": "素材 a", "note": "n"}],
                 "constraints": []}
        built, text = self.build(carry=carry)
        self.assertIn("- 人の判断を待つ項目への答えの下書き: 1 件——次の run の依頼の下書き next-request.json の answers に置いた", text)
        self.assertEqual(len(base.read(built["next_request"])["answers"]), 1)

    def test_a_row_that_breaks_the_schema_writes_nothing(self):
        for carry in ({"findings": [], "prior": [{"where": "w"}], "drafts": [], "constraints": []},
                      {"findings": [], "prior": [], "drafts": [], "constraints": [{"text": "t", "measured_how": "h", "kind": "実測", "extra": 1}]}):
            with self.subTest(carry), self.assertRaises(ValueError):
                self.build(carry=carry)
            self.assertEqual([p.name for p in self.place.iterdir()], [], "2 つとも照らしてから書く（報告も残さない）")


class FallbackCase(Base):
    def test_fallback_report_names_its_own_file_and_leaves_the_report_alone(self):
        built, _ = self.build()
        path = M.machine.fallback_report(self.place, "思わぬ誤り")
        self.assertEqual(path.name, "report-unwritten.md")
        text = path.read_text(encoding="utf-8")
        self.assertTrue([x for x in text.splitlines() if x.startswith(f"起きたこと: {report.OUTCOME_WORDS['record_invalid']}")], text)
        self.assertIn("結果を名乗れない訳: 思わぬ誤り", text)
        self.assertIn("直して、最後のテストまで通った", built["report"].read_text(encoding="utf-8"), "facts の report.md を上書きしない")


class StampCase(unittest.TestCase):
    def test_parts(self):
        yaml_path = base.BLOCK / "works-factory-report.yaml"
        got = M.writer.stamp(RUN_ID, yaml_path, 2, "a" * 40, True)
        parts = got.split(" / ")
        self.assertEqual(parts[:3], ["works-factory-report", f"run {RUN_ID}", "周 2"])
        self.assertRegex(parts[3], r"^グラフの版 [0-9a-f]{12}$")
        self.assertEqual(parts[4], f"メイングラフの版 {'a' * 12}")
        self.assertIn("周 —", M.writer.stamp(RUN_ID, yaml_path, None, "", True))
        self.assertTrue(M.writer.stamp(RUN_ID, yaml_path, None, "", True).endswith("メイングラフの版 始めの記録に無い"))
        self.assertTrue(M.writer.stamp(RUN_ID, yaml_path, None, "", False).endswith("メイングラフの版 読めない（始めの記録が読めない）"))
        self.assertIn("グラフの版 読めない（FileNotFoundError）", M.writer.stamp(RUN_ID, "/no/such.yaml", None, "", True))


if __name__ == "__main__":
    unittest.main()
