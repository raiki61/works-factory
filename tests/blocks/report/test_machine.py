"""機械の報告（workflows/report/src/machine.py。docs/design/report.md の 1.8）。人が差分を当てるかを決める頭の行（差分を当ててよいか・急ぎ・
人が決めることの件数）の答えと、次の run に運ぶファイル・予備の報告・開けないファイルと読めない記録の注を見る。行の字と形の照らしは
2026-11-10 に落とした（docs/design/report.md の 8 節）"""
import json
import re
import unittest

from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
import report    # noqa: E402  lib/

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

    def test_pr_stopped_keeps_the_apply_answer(self):
        """出口の語 pr の道で PR を作らずに止めた・PR を作ったと確かめられなかった run の「差分を当ててよいか」の行は、PR の道でない同じ場面の答え
        （差分が無い・作り直しが要るので当てない・決めてから当てる・--allow-stopped つき・確かめてから当てる）を変えず、PR の道の結果を前に足す
        だけ（bin/apply が断る命令を案内しない）。答えの分かれ（machine._apply_row）の枝ごとに 1 場面"""
        lead = "差分を当ててよいか: "
        said = {"stopped": "PR を作らずに止めた。対象の既定の枝には当てていない。",
                "unconfirmed": "PR を作ったと確かめられなかった。対象の既定の枝には当てていない。"}
        sealed = {"sealed": True, "placed": True}
        asks = [{"kind": "k", "text": "t"}]
        scenes = ({"apply": {"sealed": False}}, {"apply": {"sealed": True, "placed": False, "redesign": "redesign-needed"}},
                  {"apply": sealed, "asks": asks}, {"apply": {"sealed": True, "placed": False}, "asks": asks},
                  {"apply": {"sealed": True, "placed": False}}, {"apply": sealed},
                  {"apply": sealed, "outcome": "round_limit", "proved": False})

        def apply_row(kw) -> str:
            _, text = self.build(**kw)
            [row] = [x for x in M.writer.machine_head(text).splitlines() if x.startswith(lead)]
            return row

        rows = set()
        for kw in scenes:
            plain = apply_row(kw)
            rows.add(plain)
            for act, front in said.items():
                with self.subTest(act=act, scene=kw):
                    got = apply_row({**kw, "apply": {**kw["apply"], "pr": {"act": act, "reason": "訳"}}})
                    self.assertEqual(got, lead + front + plain.removeprefix(lead))
        self.assertEqual(len(rows), len(scenes), "場面ごとに答えが分かれる")


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


class SectionsCase(Base):
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

    def test_facts_notes_reach_the_notes_section(self):
        """graph が facts の notes に渡した読めなかった物の行は、注意の節にそのまま載る（読めなかった控えを黙って落とさない）"""
        _, text = self.build(notes=["読めなかった物 N"])
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


class FactsShapeCase(Base):
    def test_notice_kinds_match_the_facts_schema(self):
        """graph が渡す facts の知らせの種（共通の形 facts.schema.json の head.after・head.notices の kind の enum）が頭の文面表の Notice と等しい。
        食い違うと、graph が形どおりに渡した知らせで facts の読みが落ち、run が結果を名乗れない（record_invalid）"""
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


class FallbackCase(Base):
    def test_fallback_report_names_its_own_file_and_leaves_the_report_alone(self):
        built, _ = self.build()
        path = M.machine.fallback_report(self.place, "思わぬ誤り")
        self.assertEqual(path.name, "report-unwritten.md")
        text = path.read_text(encoding="utf-8")
        self.assertTrue([x for x in text.splitlines() if x.startswith(f"起きたこと: {report.OUTCOME_WORDS['record_invalid']}")], text)
        self.assertIn("結果を名乗れない訳: 思わぬ誤り", text)
        self.assertIn("直して、最後のテストまで通った", built["report"].read_text(encoding="utf-8"), "facts の report.md を上書きしない")


if __name__ == "__main__":
    unittest.main()
