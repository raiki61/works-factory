"""報告の頭（機械が書く行）の知らせ: 直す前の試験の関門の止め・試験の起動スクリプトが壊れて組を止めた・TDD の実行器を作れなかった
（ループを回していない）を、状態ごとの種で頭に出す（未実行を緑と読ませない）。入口が入力を断った止めの知らせに、工場の内側の名前
（ノードの id・止めの語・審査役の印）を訳なしで出さない（issue #687 の求め 6）。
"""
import json
import re
import sys
import unittest
from unittest import mock

from tests.blocks import kit
from tests.blocks.line import test_collect as base

BLOCK = "line"
# 頭に訳なしで出てはいけない内側の名前の形（ノードの id は nodenames.json の行。止めの語・審査役の印・記録の欄の名は字の形で見る）
INNER = (r"works:[a-z]", r"\bR[1-4]\b", r"\b(?:fix-needed|redesign-needed)\b", r"\bbreaks\.accepted\b")


def head_table():
    """報告の block の頭の文面表（workflows/report/src/head.py）。表は同じ block の src.title を読むので report の src で読み、
    読んだ後は前の src のモジュールを戻す（この試験のほかの所が line の src を使う）"""
    saved = {n: m for n, m in sys.modules.items() if n == "src" or n.startswith("src.")}
    try:
        return kit.load("report", "head")
    finally:
        for name in [n for n in sys.modules if n == "src" or n.startswith("src.")]:
            del sys.modules[name]
        sys.modules.update(saved)


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
    """入口が入力を断った止めの知らせは、訳と種の文のどちらにも工場の内側の名前を出さない"""
    REFUSED = "PR の head が対象の HEAD と違う——PR の head を取り出した所で始める"

    def inner_names_in(self, text: str) -> list:
        names = [n for n in self.f.node_names() if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", text)]
        return [*names, *[m.group(0) for p in INNER for m in re.finditer(p, text)]]

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
