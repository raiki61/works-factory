"""報告の頭（機械が書く行）に、工場の内側の名前が訳なしで出ない（issue #687 の求め 6）。

材料は本物の run 2 本（無人で最後の承認ノードを開けずに止まった軽量の run）の記録の形: 修正前の承認ノードを推しで通し、最後の承認ノードの
2 つのノードが止めの語で止まり、独立の目 R1 が長い指摘の文つきで直しが要ると言い、直しの途中で AI が自分で決めずに人に回した物が在る。初見の読み手は報告の頭
だけを読むので、頭の行に出る内側の名前（ノードの id・止めの語・記録の欄の名・審査役の印）は、頭の中で人の言葉に訳されている形だけを許す。
訳なしの名前を 1 つずつ足して直すのでなく、頭の行の作り方（人の言葉を先に出し、名前と長い文は頭の外の節に置く）で縛る。
"""
import importlib.util
import json
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


def head_table():
    """報告の block の頭の文面表（workflows/report/src/head.py）。表は lib だけを import するので、src の入れ替えに触れず単独で読む"""
    spec = importlib.util.spec_from_file_location("report_head_table", kit.BLOCKS / "report" / "src" / "head.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def head_strings(facts: dict) -> list:
    """facts の組のうち報告の頭に出る字: before・stopped の字（念のため）、after の知らせの差し込み口の値、asks の題（無ければ種）。
    知らせの本文 text と asks の本文は頭に出ない（節「2. 止めたか」と節「1. 人が決めること」に在る）"""
    head = facts["head"]
    return [*head["before"], *head["stopped"], *[str(v) for item in head["after"] for v in item["slots"].values()],
            *[a.get("title") or a["kind"] for a in facts["asks"]]]


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
        self.head = head_strings(self.facts)

    def test_no_inner_name_stands_bare_in_the_head(self):
        text = "\n".join(self.head)
        names = [n for n in self.f.node_names() if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
        found = [*names, *[m.group(0) for p in INNER for m in re.finditer(p, text)]]
        self.assertEqual(found, [], text)

    def test_long_reviewer_reason_is_not_pasted_into_the_head(self):
        self.assertFalse(any("lib/unittrees.py:151" in x for x in self.head), self.head)
        self.assertTrue(max(len(x) for x in self.head) < 300, [len(x) for x in self.head])
        pasted = {**self.facts, "head": {**self.facts["head"], "after": [
            {"kind": "answer_redirected", "slots": {"quote": R1_REASON}, "text": ""}]}}
        self.assertTrue(any("lib/unittrees.py:151" in x for x in head_strings(pasted)), "差し込み口に長い訳を入れた facts は赤になる")
        self.assertGreater(max(len(x) for x in head_strings(pasted)), 300)

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


class AskTitleCase(unittest.TestCase):
    """人が決める物の題（asks[].title）の出どころ。題は本文を書いた所が本文と同じ行の欄として書き（判定の役の問いの title・独立の目の問いと載せなかった
    修正前の問いの {text, title} の行・修正の役の申し送りの題）、機械が本文を組む種は組むコードが決まった字の題を出す。出どころの表 ASK_SOURCES に
    人が決める物の種ごとに出どころが 1 つ在り、decisions は表の鍵の順にだけ種を並べる（表に無い種は並べられない）。仕様を確かめる役の問いは題を
    持たず種の名に戻る（その見出しは入力で 2 つに分かれるので、表に 2 つとも在る）"""
    FORK = {"key": "q-a", "kind": "fork", "status": "held", "origin": "u1", "options": ["例外", "0"], "reason": "割れる"}

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.gm = __import__("gatemarks")
        self.fix = __import__("fixboard")
        self.run = kit.Run(self, BLOCK)
        base.seed(self.run)

    def put(self, rel: str, doc) -> dict:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return base.ptr(rel)

    def asks(self, values: dict, table=None) -> list:
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            if table is None:
                return self.f.build(values, base.record())["asks"]
            with mock.patch.object(self.f, "ASK_SOURCES", table):
                return self.f.build(values, base.record())["asks"]

    def of_kind(self, asks: list, kind: str) -> list:
        return [a for a in asks if a["kind"] == kind]

    def with_judgment(self, questions, units=({"key": "u1", "label": "block"},), **over) -> dict:
        v = base.passing()
        v["judge"] = {**v["judge"], "judgment": self.put("judge/judgment.json", {"units": list(units), "questions": list(questions)})}
        v.update(over)
        return v

    def test_every_ask_kind_has_one_title_source(self):
        """ASK_SOURCES の鍵 = 空の入力で集めた種から仕様の見出しを除き、仕様を確かめる役の 2 つの見出しを足した物。2 つの仕様の見出しの出どころは
        『題を持たず種の名に戻す』印で、行の欄の印ではない（見出しは入力で変わるので、どちらの run でも並ぶ）。表から 1 種を外した写しでは、その種の行が
        並ばずに落ちる"""
        for name in ("ASK_SOURCES", "ask_groups", "ROW_TITLE", "KIND_NAME"):
            self.assertTrue(hasattr(self.f, name), f"出どころの表の部品 {name} が無い")
        with self.run.env():
            collected = set(self.f.ask_groups({}, {}, {}, unattended=False, closed=False))
        spec = {self.gm.spec_words(True).head, self.gm.spec_words(False).head}
        self.assertEqual(set(self.f.ASK_SOURCES), (collected - spec) | spec)
        for head in spec:
            self.assertIs(self.f.ASK_SOURCES[head], self.f.KIND_NAME, head)
            self.assertIsNot(self.f.ASK_SOURCES[head], self.f.ROW_TITLE, head)
        for kind, source in self.f.ASK_SOURCES.items():
            with self.subTest(kind=kind):
                self.assertTrue(source is self.f.ROW_TITLE or source is self.f.KIND_NAME or (isinstance(source, str) and source.strip()), source)
        # 機械が組む種の決まった題は報告の頭に出るので、語の表 glossary.json の語を使わない
        terms = [r["term"] for r in json.loads((kit.BLOCKS / "report" / "src" / "glossary.json").read_text(encoding="utf-8"))["terms"]]
        for kind, source in self.f.ASK_SOURCES.items():
            if isinstance(source, str):
                self.assertEqual([t for t in terms if t in source.format(unit_id="u1")], [], f"{kind}: {source}")
        # 照らせなかった run でも、仕様の問いは種の名のまま asks に並ぶ（2 つの見出しのどちらでも）
        for unchecked in (True, False):
            with self.subTest(unchecked=unchecked):
                v = base.passing()
                v["spec_check"] = {"questions": ["受け入れ条件のテストが変わった"], "unchecked": unchecked}
                [ask] = self.asks(v)
                self.assertEqual((ask["kind"], "title" in ask), (self.gm.spec_words(unchecked).head, False))
        # 表から 1 種を外した写しでは、その種の行が落ちる（表に無い種は並べられない）
        held = self.with_judgment([self.FORK])
        kind = "保留にしたままの問い"
        self.assertTrue(self.of_kind(self.asks(held), kind))
        short = {k: v for k, v in self.f.ASK_SOURCES.items() if k != kind}
        self.assertEqual(self.of_kind(self.asks(held, short), kind), [])
        self.assertEqual(list(self.f.ASK_SOURCES)[:2], [self.f.UNRESTORED_GROUP_HEAD, self.f.BACKED_OUT_HEAD], "並びは今の asks の並びのまま")

    def test_a_judge_question_title_rides_on_the_ask(self):
        """人の居る run で保留のまま残った判定の台帳の問いが title を持てば、その題が『保留にしたままの問い』の asks の題になる。2 行の題は 1 行に
        畳み、空白だけの題は題なしとして種の名に戻る。台帳の問いを持たない後ろの行（修正前の承認ノードで答えたが、origin が判定の単位に無く直す義務に
        戻せなかった問いの行 unreturned_lines）は題なし"""
        kind = "保留にしたままの問い"
        folded = {**self.FORK, "title": "空の列で\n例外を投げるか決める"}
        blank = {**self.FORK, "key": "q-b", "title": " \n "}
        gone = {**self.FORK, "key": "q-c", "origin": "gone-unit", "title": "題があっても後ろの行には移らない"}
        v = self.with_judgment([folded, blank, gone])
        v["answer_before_fix"] = {"go": True, "stop_reason": "", "policy": "",
                                  "answer": {"decision": "continue", "text": "通す", "asked": [self.gm.ask_text(gone)]}}
        rows = self.of_kind(self.asks(v), kind)
        self.assertEqual(len(rows), 3, rows)
        self.assertEqual(rows[0].get("title"), "空の列で 例外を投げるか決める")
        self.assertIn("q-a", rows[0]["text"])
        self.assertNotIn("title", rows[1], "空白だけの題は題なし")
        self.assertIn("q-b", rows[1]["text"])
        self.assertIn("q-c", rows[2]["text"], "後ろの行は直す義務に戻せなかった単位の行")
        self.assertIn("直す単位に入れられなかった", rows[2]["text"])
        self.assertNotIn("title", rows[2], "問いを持たない後ろの行は題なし（種の名に戻る）")

    def test_an_eye_question_title_rides_on_the_ask(self):
        """独立の目の問いが {text, title} で届けば、その題が題になり、本文は text。字の問いは題なし"""
        v = base.passing()
        v["eyes"] = {**v["eyes"], "questions": [{"text": "範囲の外の変更を通してよいか", "title": "範囲の外の変更を\n通してよいか"}, "字の問い"],
                     "means_questions": [{"text": "R2: 食い違う", "title": "頼みどおりにするか決める"}]}
        v["answer_final"] = {"go": False, "answer": None, "stop_reason": ""}   # 最後の承認ノードに答えが無い間だけ頼みどおりの違いの問いが残る
        eye = self.of_kind(self.asks(v), self.f.EYE_ASK_HEAD)
        self.assertEqual([("title" in a, a["text"].split("——")[0]) for a in eye], [(True, "範囲の外の変更を通してよいか"), (False, "字の問い")])
        self.assertEqual(eye[0]["title"], "範囲の外の変更を 通してよいか")
        [means] = self.of_kind(self.asks(v), self.f.MEANS_ASK_HEAD)
        self.assertEqual((means["title"], means["text"].split("——")[0]), ("頼みどおりにするか決める", "R2: 食い違う"))

    def test_a_deferred_question_title_rides_on_the_ask(self):
        """載せなかった修正前の問いが {text, title} で届けば、その題が題になる。字の問いは題なし（前の記録）"""
        v = base.passing()
        v["ask_before_fix"] = {**v["ask_before_fix"], "open": False,
                               "deferred": [{"text": "載せなかった問い", "title": "空の列の扱いを決める"}, "字だけの問い", {"text": "題の無い行"}]}
        rows = self.of_kind(self.asks(v), "修正前の問い")
        self.assertEqual([(a["text"].split("——")[0], a.get("title")) for a in rows],
                         [("載せなかった問い", "空の列の扱いを決める"), ("字だけの問い", None), ("題の無い行", None)])

    def test_a_machine_built_kind_gets_its_fixed_title(self):
        """機械が本文を組む種の行は、種ごとの決まった字の題を持つ。単位の id を差し込む種は id を入れた題"""
        self.assertTrue(hasattr(self.f, "ASK_SOURCES"), "人が決める物の種ごとの題の出どころの表 ASK_SOURCES が無い")
        v = base.passing()
        v["fixed"] = {**v["fixed"], "units": [{"unit_id": "u1", "status": "fixed"}, {"unit_id": "u9", "status": self.fix.NOT_DONE, "reason": "直せなかった"}]}
        v["merge_seal"] = {**v["merge_seal"], "protected_hits": ["lib/protected.json"], "protected_count": 4}
        asks = self.asks(v)
        [unit] = self.of_kind(asks, "直しの対象に戻せなかった項目")
        self.assertEqual(unit.get("title"), self.f.ASK_SOURCES["直しの対象に戻せなかった項目"].format(unit_id="u9"))
        self.assertIn("u9", unit["title"])
        [hit] = self.of_kind(asks, self.f.PROTECTED_HITS_HEAD)
        self.assertEqual(hit.get("title"), self.f.ASK_SOURCES[self.f.PROTECTED_HITS_HEAD])
        for ask in asks:
            self.assertEqual("title" in ask, self.f.ASK_SOURCES[ask["kind"]] is not self.f.KIND_NAME, ask)


class HeadAfterBase(unittest.TestCase):
    """頭の after を組む試験の共通の準備（試験は持たない）。facts_of が本物の build を呼び、after がその頭の after を返す"""

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.run = kit.Run(self, BLOCK)
        base.seed(self.run)

    def facts_of(self, values: dict, record: dict | None = None) -> dict:
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.f.build(values, record or base.record())

    def after(self, values: dict, record: dict | None = None) -> list:
        """頭の after の知らせの行 {kind, slots, text}"""
        return self.facts_of(values, record)["head"]["after"]

    @staticmethod
    def kinds(after: list, *kinds: str) -> list:
        """after の要素のうち種が kinds のどれかの物（要素が行でも字でも読む。字の要素は種を持たないので数えない）"""
        return [x for x in after if isinstance(x, dict) and x.get("kind") in kinds]


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
        [note] = self.kinds(self.after(v), "suite_broken")
        self.assertEqual(note["slots"], {"group": "g1", "runner_log": "/r/fix/tdd-2/suite-0.log", "cmd_log": "/r/fix/tdd-2/test-cmd-alone.log"})
        self.assertEqual(note["text"], self.WHY, "本文は返りの訳だけ（種の意味の句は表の文）")
        self.assertFalse(note["text"].startswith("修正の段が止めた"))

    def test_a_group_stopped_for_no_suite_heads_the_report(self):
        """試験の実行器が無い・走らないで止めた組（止めの語 no-suite。docs/plans/2026-10-24-fix-weapons.md の 3.9）も、種つきで知らせる"""
        v = base.passing()
        v["fixed"] = {**v["fixed"], "tdd": [[{"group_id": "g1", "ran": False, "reason": "試験の実行器が無いか走らない組", "units": [],
                                              "no_suite": True}]]}
        self.assertEqual(self.kinds(self.after(v), "suite_broken", "no_suite"),
                         [{"kind": "no_suite", "slots": {"group": "g1"}, "text": "試験の実行器が無いか走らない組"}])

    def test_a_fix_that_did_not_stop_says_nothing(self):
        self.assertEqual(self.kinds(self.after(base.passing()), "suite_broken", "no_suite"), [])
        stopped = [{"kind": "suite_broken", "slots": {"group": "g", "runner_log": "a", "cmd_log": "b"}, "text": ""}]
        self.assertTrue(self.kinds(stopped, "suite_broken", "no_suite"), "その種の要素を入れた facts は赤になる")
        self.assertEqual(self.kinds(["修正の段が止めた（古い形の字）"], "suite_broken"), [], "字の要素は種を持たない")


class BaseStopHeadCase(HeadAfterBase):
    """持ち主の決め base-runs-nothing の足し: 直す前の試験の関門が止めた run（試験のコマンドの最初の語を起こせない）は、報告の冒頭の
    知らせの行に止めた訳を出す。止めていない run には出さない"""
    WHY = "素材が not_run——緑を仮定しない（試験のコマンド（no-such-tool）の最初の語を起こせない（PATH に no-such-tool が無い）。試験は走らせずに確かめた）"

    def test_the_stop_reason_of_the_base_gate_heads_the_report(self):
        v = base.passing()
        v["test_gate_base"] = {**v["test_gate_base"], "ok": False, "green": False, "reason": self.WHY}
        for name in ("judge", "fix_in", "fixed", "eyes", "merge_seal", "merge_apply", "test_gate_final"):
            v[name] = None
        [note] = self.kinds(self.after(v), "base_gate_stopped")
        self.assertIn("起こせない", note["text"])

    def test_the_base_gate_reason_keeps_the_whole_setup_guide_in_the_head(self):
        """設定の手引きの全文は知らせの本文 text に在り（報告では節「2. 止めたか」に載る）、頭に出る差し込み口には試験のコマンドの最初の語だけが在る"""
        import green_cert
        _, reason = green_cert.certify(mode="base", material_status="not_run", material_reason="試験のコマンド（no-such-tool）の最初の語を起こせない",
                                       green=None, before=None, after=None, now=None)
        v = base.passing()
        v["test_gate_base"] = {**v["test_gate_base"], "ok": False, "green": False, "reason": reason}
        facts = self.facts_of(v, {**base.record(), "test_cmd": "WORKS_SECRET=x no-such-tool --flag"})
        [note] = self.kinds(facts["head"]["after"], "base_gate_stopped")
        self.assertIn(green_cert.RAN_GUIDE, note["text"])
        self.assertEqual(note["slots"], {"cmd": "no-such-tool"})
        self.assertNotIn("WORKS_SECRET", json.dumps(note["slots"]), "前置きの環境変数の値は頭に出さない")

    def test_a_base_gate_that_went_on_says_nothing(self):
        self.assertEqual(self.kinds(self.after(base.passing()), "base_gate_stopped"), [])
        gate = [{"kind": "base_gate_stopped", "slots": {"cmd": "x"}, "text": ""}]
        self.assertTrue(self.kinds(gate, "base_gate_stopped"), "その種の要素を入れた facts は赤になる")


class StopReasonHeadCase(HeadAfterBase):
    """報告の冒頭の知らせの行に訳が出る止めは、入口が入力を断った止め（次にすることの句が尾に付く）と直す前の試験の関門が止めた止めだけ。
    line の script の落ちと block の止めの訳は頭に出さない（script の落ちは problems に、block の止めの訳はその block の報告の行に在る）。止めていない run には出さない"""
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
        """段 node が止めの語 word で止めた run の、訳 R-<node> を本文に持つ (頭の after の知らせの行, problems の行)"""
        facts = self.facts_of(self.stopped_values(node, name, word))
        return ([x for x in facts["head"]["after"] if f"R-{node}" in x["text"]], [x for x in facts["problems"] if f"R-{node}" in x])

    def test_a_stop_without_its_reason_in_the_head_still_says_where_it_stopped_and_what_the_word_means(self):
        import stopby
        cases = [(node, name, stopby.LINE_SCRIPT) for node, name in self.f.LINE_STOPS if node != "start"]
        cases += [(node, name, stopby.PREMISES) for node, name in self.f.BLOCK_STOPS]
        cases += [("theme-descend", "theme_descend", stopby.NEEDS_HUMAN), ("theme-descend", "theme_descend", stopby.HUMAN + "gate-theme")]
        for node, name, word in cases:
            with self.subTest(node=node, word=word):
                facts = self.facts_of(self.stopped_values(node, name, word))
                self.assertEqual([x for x in facts["head"]["after"] if f"R-{node}" in json.dumps(x, ensure_ascii=False)], [],
                                 "訳の本文は頭の知らせに無い（本文にも差し込み口にも）")
                lines = [x for x in facts["head"]["stopped"] if x.startswith(f"{self.f.plain(node)}が止めた: ")]
                self.assertEqual(len(lines), 1, facts["head"]["stopped"])

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
                    self.assertEqual([(x["kind"], x["slots"], x["text"]) for x in head], [("start_refused", {}, f"R-{node}")])
                    self.assertNotIn("次にすること", head[0]["text"], "次にすることの句は facts に無い（種の文が持つ）")
                    self.assertEqual(self.inner_names_in(head[0]["text"].replace(f"R-{node}", "")), [], head[0])
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
            lines = [x for x in self.after(v) if "R-test-gate-base" in x["text"]]
            self.assertEqual([(x["kind"], x["text"]) for x in lines], [("base_gate_stopped", "R-test-gate-base")])
            self.assertEqual(self.inner_names_in(lines[0]["text"].replace("R-test-gate-base", "")), [], lines[0])
            self.assertNotIn("次にすること", lines[0]["text"])
        with self.subTest(node="none"):
            after = self.after(base.passing())
            self.assertFalse([x for x in after if "R-" in x["text"] or "次にすること" in x["text"]], after)
        with self.subTest(node="table"):   # 次にすることの句は種で引く表の文に在る（入口が入力を断った種は起こし直す、一言の向きの種は見直して計画し直す）
            table = head_table()
            self.assertIn("起こし直す", table.NOTICES[table.Notice.START_REFUSED])
            self.assertIn(self.REDIRECT_NEXT.removeprefix("次にすること: "), table.NOTICES[table.Notice.ANSWER_REDIRECTED])

    REDIRECTED = "判定: redirected（計画は 0 を返すが一言は例外を選んでいる）。一言: 空の列は例外を投げる形にして"
    REDIRECT_NEXT = "次にすること: 下書きの一言を見直し、その向きで計画し直す依頼にするか、計画どおりなら continue と書いて回し直す"

    def test_the_redirected_answer_says_its_reason_and_what_to_do_next(self):
        """修正前の承認の一言の向きで止めた run（止めの語 answer-redirected）は、知らせの行に種と人の一言の引用（差し込み口）と判定の訳（本文）を持つ。
        次にすることの句は facts に無く、種で引く表の文が持つ。node の id は出さない（仕様駆動の道と写しの道の答えの返りは collect が今の欄の名に
        重ねて渡す）"""
        import stopby
        meaning = stopby.REASONS.get("answer-redirected")
        self.assertTrue(meaning, "止めの語 answer-redirected の意味が stopby の表に在る")
        v = base.passing()
        v["answer_before_fix"] = {"go": False, "answer": {"decision": "continue", "text": "一言", "asked": ["項目"]},
                                  "stop_reason": "works:answer-redirected", "reason": self.REDIRECTED, "policy": ""}
        [note] = self.kinds(self.after(v), "answer_redirected")
        self.assertEqual(note["slots"], {"quote": "一言"})
        self.assertEqual(note["text"], self.REDIRECTED)
        self.assertNotIn("次にすること", note["text"])
        self.assertEqual(self.inner_names_in(note["text"].replace(self.REDIRECTED, "")), [], note)

    def test_the_refused_line_says_what_to_do_next_without_inner_names(self):
        import stopby
        v = {name: None for name in base.INPUTS} | {"notices": "", "optional": []}
        v["start"] = {"ok": False, "stop_reason": stopby.START_REFUSED, "reason": self.REFUSED, "record": None}
        [note] = self.kinds(self.after(v), "start_refused")
        self.assertEqual((note["slots"], note["text"]), ({}, self.REFUSED))
        self.assertEqual(self.inner_names_in(note["text"].replace(self.REFUSED, "")), [], note)
        table = head_table()
        self.assertEqual(self.inner_names_in(table.NOTICES[table.Notice.START_REFUSED]), [], "種の文にも内側の名が無い")
        self.assertIn("起こし直す", table.NOTICES[table.Notice.START_REFUSED])


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


class TddNoticeHeadCase(HeadAfterBase):
    """TDD の実行器の用意の状態（取り置きを使った・AI が書いた・作れなかった）は、状態ごとの種になって頭に出る。

    この場面の試験を足す訳: 頭の全体の検査（tests/blocks/report/test_machine.py の HeadTableCase の (a)〜(f)）は、表に行が在ること・差し込みの名が型と
    合うこと・頭の行が表の行に読み戻せること・語の表の語が無いことしか見ない。どの状態にどの種の文を当てるか（作れなかった run に『作れなかった』
    と言い、TDD のループを回していないと言うか）は表の行の意味で、3 つの種の文を取り違えても (a)〜(f) は全部緑のままになる。取り違えると、作れなかった
    run の頭が『取り置きを使った』と言って、ループを回していない事実が頭から消える。そこで本物の facts の build に状態ごとの記録を渡し、種と表の文の組を見る"""

    def mark(self, **over) -> dict:
        return {**base.record(), "suite_written": {"from": "ai", "path": "", "ok": True, "why": "", "dropped": "", "stored": False, **over}}

    def notes(self, record: dict) -> list:
        return self.kinds(self.after(base.passing(), record), "suite_used", "suite_wrote", "suite_not_made")

    def test_a_runner_that_was_not_made_says_the_loop_did_not_run(self):
        import suitewrite
        self.assertTrue(hasattr(suitewrite, "note_state") and hasattr(suitewrite, "NO_LOOP"), "状態の語を返す note_state と NO_LOOP が無い")
        table = head_table()
        why = "実行器を書く役が作らなかった（訳を書いていない）"
        [note] = self.notes(self.mark(ok=False, why=why, dropped="壊れていた"))
        self.assertEqual(note["kind"], "suite_not_made")
        self.assertEqual(note["text"], f"{why}。取り置きは照らしを通らず捨てた: 壊れていた", "本文は括弧の中身だけ（作れなかった訳と捨てた取り置き）")
        said = table.NOTICES[table.Notice(note["kind"])]
        self.assertIn(suitewrite.NOT_MADE, said)
        self.assertIn("TDD のループは回さない", said, "作れなかった run の頭は TDD のループを回していないと言う")
        for other in (suitewrite.USED, suitewrite.WROTE):
            self.assertNotIn(other, said)
        self.assertNotIn("工場が用意", said)
        for record, kind, state, other in ((self.mark(**{"from": "keep"}), "suite_used", suitewrite.USED, suitewrite.WROTE),
                                           (self.mark(stored=True), "suite_wrote", suitewrite.WROTE, suitewrite.USED)):
            with self.subTest(kind=kind):   # 取り置きを使った run と AI が書いた run は、それぞれ自分の種になる
                [note] = self.notes(record)
                self.assertEqual((note["kind"], note["slots"]), (kind, {}))
                said = table.NOTICES[table.Notice(kind)]
                self.assertIn(state, said)
                self.assertNotIn(other, said)
                self.assertNotIn("TDD のループは回さない", said)
        self.assertEqual(self.notes(self.mark(**{"from": "keep"}))[0]["text"], suitewrite.note_detail(self.mark(**{"from": "keep"})))
        self.assertEqual(self.notes(base.record()), [], "実行器を用意しなかった run には知らせが無い")
