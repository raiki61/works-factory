"""機械の報告（workflows/report/src/machine.py。docs/design/report.md の 1.8）の節の並びと字。写す元は lib/tests/test_runreport.py の BuildCase
（冒頭 3 行・止めたか・見る所・模型・費用・注意）・DraftsCase・CarryCase・StampCase。節の中身を返りから組む試験は作り手の block と graph の試験の物"""
import json
import pathlib
import re
import unittest

from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
RUN_ID = "run-test"
SECTIONS = [{"title": "直した所", "lines": ["単位 u1: 直した", "  内訳 a"]}, {"title": "空の節", "lines": []}]
OK_RUN = {"ok": True, "failed": [], "absorbed": [], "errors": {}, "retried": [], "cost": {"fix__tdd": 0.5}, "uncosted": {}, "minutes": {"fix__tdd": 1.5},
          "models": {"fix__tdd": ["sonnet"]}, "efforts": {"fix__tdd": ["low"]}, "calls": {}, "resubmits": {}}


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
        self.assertEqual(lines[2], "起きたこと: 直して、最後のテストまで通った（fixed）。人が決めること 7 件が残っている")
        self.assertTrue(lines[3].startswith("差分を当ててよいか: "))
        self.assertTrue(lines[4].startswith("急ぎ: "))
        self.assertEqual(lines[5], "人が決めること: 7 件（下の行は種類ごと。1 件ずつの本文は見出しに「人が決めること」を持つセクション）")
        self.assertEqual(lines[6:8], ["- 保留にしたままの問い（2 件）", "- 許したテストの変更（5 件）"])

    def test_nothing_to_decide_names_what_is_carried_instead(self):
        carry = {"findings": [{"where": "a", "text": "b"}], "prior": [], "drafts": [], "constraints": []}
        _, text = self.build(carry=carry)
        self.assertEqual(text.splitlines()[5], "次の run に渡す物: 1 件")
        self.assertNotIn("人が決めること:", text.split("\n## ", 1)[0], "無いと断る決まり文句は書かない")

    def test_head_parts_go_to_the_stop_section_not_the_happened_line(self):
        head = {"before": ["半分直した"], "stopped": ["止めた訳 X"], "after": [], "notices": ["起こす前の注意 N"]}
        _, text = self.build(head=head)
        self.assertEqual(text.splitlines()[2], "起きたこと: 直して、最後のテストまで通った（fixed）")
        self.assertIn("\n\n起こす前の注意 N\n\n## 1.", text)
        self.assertIn("- 半分直した", self.section(text, "## 2. 止めたか"))
        self.assertNotIn("止めた訳 X", text, "止まった run でなければ止めた訳は出さない")
        _, text = self.build(head=head, outcome="stopped_by_human", stop="start-answer:reject")
        self.assertEqual(text.splitlines()[2], "起きたこと: 人が承認ノードで止めた（stopped_by_human）")
        stop = self.section(text, "## 2. 止めたか").splitlines()
        self.assertEqual(stop[2:4], ["- 半分直した", "- 止めた訳 X"])


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
        self.assertIn("人が決めること: 3 件（下の行は種類ごと。1 件ずつの本文は見出しに「人が決めること」を持つセクション）", top)
        self.assertEqual([x for x in top if x.startswith("- ")], ["- 題 A（k）", "- k（2 件）"])

    def test_blank_title_is_untitled(self):
        _, text = self.build(asks=[{"kind": "k", "text": "a", "title": "  "}])
        self.assertIn("- k", text.split("\n## ", 1)[0].splitlines())


class HeadFor19b99137Case(Base):
    """run 19b99137 の頭（初見の読み手が 3 回とも通さなかった）の止まる所 5 つを、yes/no で縛る。入力の形は記録の facts と同じ"""
    KIND = "直しの途中で AI が自分で決めずに人に回した物（壊すと分かって通した理由。役だけで決めた代償なので人が確かめる）"
    LONG = "lib/x.py fn_name: 単独の行を残った印と数え、正当なファイルを拒む: 壊すと分かって通した——（以下、修正役の返りの長い文）"
    ENV = "AI が書いた試験のコードを、利用者の資格に届く環境（利用者の HOME・XDG）で走らせた"
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
        self.assertEqual(line, "起きたこと: 人の判断を待ったまま止まった（needs_human）。人が決めること 1 件が残っている")
        self.assertNotIn("承認ノード", top)

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
        self.assertIn(f"知らせ（決めることではない）: {self.ENV}", top.splitlines())
        self.assertNotIn(self.ENV, next(x for x in top.splitlines() if x.startswith("起きたこと: ")))

    def test_urgency_comes_only_from_facts_the_machine_holds(self):
        _, top = self.top()
        self.assertIn("急ぎ: 急ぎでない——壊れた所は無く、対象のリポジトリには何も当てていない", top.splitlines())
        _, top = self.top(run={**OK_RUN, "failed": ["fix__tdd"], "errors": {"fix__tdd": "x"}})
        self.assertIn("急ぎ: 壊れた所がある——落ちたノードが在る。対象のリポジトリには何も当てていない", top.splitlines())
        _, top = self.top(run={**OK_RUN, "ok": False})
        self.assertFalse([x for x in top.splitlines() if x.startswith("急ぎ: ")], "run の記録が読めない時は急ぎを推して書かない")

    def test_outcome_asks_join_the_head_and_the_decisions_section(self):
        left = [{"where": "素材 a", "text": "測れていない", "unmeasured": True}]
        _, text = self.build(outcome="fixed_needs_check", left=left, decisions={"before": ["前の行"], "after": ["後の行"], "outside": ["外の行"]})
        self.assertIn("人が決めること: 1 件", text)
        self.assertIn("- 人が確かめる物", text.split("\n## ", 1)[0].splitlines())
        body = self.section(text, "## 1. 人が決めること").splitlines()
        self.assertEqual(body[:5], ["- 前の行", "- 人が確かめる物: 1 件", "  - 素材 a: 測れていない", "- 後の行", "- 次の run に渡す物: 0 件"])
        self.assertIn("- 外の行", body)

    def test_apply_answers(self):
        sealed = {"sealed": True, "placed": True}
        _, text = self.build(apply=sealed)
        self.assertIn(f"差分を当ててよいか: 当ててよい（bin/apply {RUN_ID}）", text)
        _, text = self.build(apply=sealed, outcome="round_limit", proved=False)
        self.assertIn(f"確かめてから当てる（結末が「決めた周の数のうちに直しきれずに止まった」。bin/apply {RUN_ID}）", text)
        _, text = self.build(apply={"sealed": True, "placed": False, "redesign": "redesign-needed"})
        self.assertIn("差分を当ててよいか: 当てない（R2 が redesign-needed を言った run の差分は bin/apply も当てない）", text)
        _, text = self.build(apply={"sealed": True, "placed": False}, asks=[{"kind": "k", "text": "t"}])
        self.assertIn(f"人が決めること 1 件を決めてから当てる（bin/apply {RUN_ID} --allow-stopped）", text)
        _, text = self.build(apply={**sealed, "pr": {"act": "pr", "url": "https://example.test/pr/1", "number": 1, "is_draft": True}})
        self.assertIn("差分を当ててよいか: PR を作った: https://example.test/pr/1（下書きの PR #1。merge は対象のレビューと決まりに任せる）", text)
        _, text = self.build(apply={**sealed, "pr": {"act": "stopped", "reason": "push が拒まれた"}})
        self.assertIn(f"PR を作らずに止めた: push が拒まれた。当ててよい（bin/apply {RUN_ID}）", text)

    def test_apply_lines_for_a_stopped_run(self):
        _, text = self.build(outcome="stopped_by_human", stop="start-answer:reject", apply={"sealed": True, "placed": False, "said": "やめる\n理由"})
        body = self.section(text, "## 1. 人が決めること")
        self.assertIn("- 止まった run: 人が承認ノードで止めた（start-answer:reject）で止まった: 「やめる 理由」", body)
        self.assertIn(f"- 差分を対象に当てる: bin/apply {RUN_ID} --allow-stopped", body)
        _, text = self.build(apply={"sealed": False})
        self.assertIn("- 差分を対象に当てる: 無い（差分を封じていない）", text)


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
        sections = [{"title": "直した所", "lines": ["x"], "files": [{"label": "差分", "ref": str(diff)}, {"label": "試験の記録", "ref": "/no/such/file"}]},
                    {"title": "目的", "lines": ["y"], "files": [{"label": "判定", "ref": self.run.pointer("here.json")}]}]
        (self.place / "here.json").write_text("{}", encoding="utf-8")
        _, text = self.build(sections)
        where = self.section(text, "## 3. 見る所").splitlines()
        self.assertEqual(where[0], f"- 差分（直した所）: {diff}")
        self.assertTrue(where[1].startswith("- 試験の記録（直した所）: 開けない（file の入力のファイル /no/such/file が無い"), where[1])
        self.assertEqual(where[2], f"- 判定（目的）: {self.place / 'here.json'}")
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
        self.assertIn("起きたこと: 記録が検証器を通らない（結果を名乗れない）（record_invalid）", text)
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
