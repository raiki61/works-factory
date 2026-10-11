"""人が読む関所の文の冒頭 3 行（lib/gatemarks.py の head3・gate_text・pushes）を、線の script で照らす。
元は今の works の works/tests/test_gate_head.py の AskGateCase と FinalHeadCase（関所の文を線が持つので、線の script の試験に置く）。

- 修正前の関所（ask_before_fix.gate_text）は 1〜3 行目が 起きたこと・決めてほしいこと・推し
- 最後の関所の冒頭（ask_final.final_head）は開けた理由（ask_final.final_needs）を 1 行目に並べ、守りのパスはそこで名指す
- 推しは判定の役が問いの理由に書いた物だけ（機械は作らない）。3 行を足しても中身は 1 つも落ちない
盤面に届く物（残りの行・報告の冒頭 report.head3・仕様の関所）を読む元の試験は持ってこない。保留にしたままの問いは判定の指し札の
先から読む（ask_final.held_questions）。
"""
import re
import unittest

from tests.bin.linescripts import load

ask_before_fix = load("ask_before_fix")
ask_final = load("ask_final")

import answer  # noqa: E402  （線の script が lib/ を sys.path に足した後に読む）
import gatemarks  # noqa: E402
import seal  # noqa: E402

HEADS = [gatemarks.HAPPENED, gatemarks.DECIDE, gatemarks.PUSH]
NARROW_ITEM = "修正案 1 が狭める能力: 空の列の mean——0 割りの例外のまま"

# 元 works/tests/test_plan_gate.py 324-327 行
FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "空の列の意味が 2 つに割れる。推し: 例外——呼び手が既に例外を捕まえている"}

# 元 works/tests/test_plan_gate.py 716-750 行
RECORD_NAME = re.compile(r"(?<![A-Za-z0-9_.])(?:(?:p\d|spec|report)\.[a-z0-9_]+|process\.[a-z_.]+[a-z]|fix_test_scope|fix_code_as|ask_human)")
EYE_OR_STATE = re.compile(r"(?<![A-Za-z0-9_-])(?:R[1-4]|pass|redesign-needed|unverifiable|premise-invalid|carried_over|not_applicable"
                          r"|not_run)(?![A-Za-z0-9_-])")


def _spans(line: str) -> list:
    """行の外側の括弧（（）と ()）の (始め, 終わり)"""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(line):
        if ch in "（(":
            if depth == 0:
                start = i
            depth += 1
        elif ch in "）)" and depth:
            depth -= 1
            if depth == 0:
                out.append((start, i))
    return out


def internal_subjects(text: str) -> list:
    """人が読む文の行のうち、盤面の内部の名が主語になっている行。記録の名（節の名・記録の欄・裁定の語）は括弧の中の『記録の名』の
    後ろにだけ、目の名と状態の語は括弧の中にだけ置いてよい（平易な名が主語で、内部の名は括弧に回す）"""
    bad = []
    for line in text.splitlines():
        spans = _spans(line)
        inside = lambda m: next(((s, e) for s, e in spans if s < m.start() < e), None)  # noqa: E731
        for m in EYE_OR_STATE.finditer(line):
            if inside(m) is None:
                bad.append(line)
        for m in RECORD_NAME.finditer(line):
            span = inside(m)
            if span is None or "記録の名" not in line[span[0]:m.start()]:
                bad.append(line)
    return list(dict.fromkeys(bad))


def heads(text: str) -> list:
    return [next((h for h in HEADS if x.startswith(h)), x) for x in text.splitlines()[:3]]


class AskGateCase(unittest.TestCase):
    def asking(self, items, kinds=("regression",)):
        return {"node": "p2.human_gate", "kinds": list(kinds), "question": "狭まる能力を代償に採るか", "items": list(items)}

    def test_plan_gate_starts_with_three_lines(self):
        text = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1")
        self.assertEqual(heads(text), HEADS)
        first = text.splitlines()[0]
        self.assertIn("直す前の関所", first)
        self.assertIn("1 件", first)
        self.assertEqual(internal_subjects("\n".join(text.splitlines()[:3])), [])

    def test_nothing_is_dropped_behind_the_head(self):
        """3 行の後ろに問いの文・項目・両方の答えの行が残る（依頼 4: 情報を 1 つも減らさない）"""
        text = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1")
        rest = "\n".join(text.splitlines()[3:])
        for want in ("> 狭まる能力を代償に採るか", f"- {NARROW_ITEM}", answer.line("run-1", "continue", "<通す範囲と条件>"),
                     answer.line("run-1", "stop", "<理由>"), f"記録の名 {ask_before_fix.RECORD}"):
            self.assertIn(want, rest)

    def test_push_comes_only_from_the_record(self):
        """推しは項目（判定の問いの理由）に書かれた物だけ。無ければ NO_PUSH、推しの無い項目が混じればそう断る"""
        none = ask_before_fix.gate_text(self.asking([NARROW_ITEM]), run_id="run-1").splitlines()[2]
        self.assertEqual(none, gatemarks.PUSH + gatemarks.NO_PUSH)
        ask = gatemarks.ask_text(FORK)
        only = ask_before_fix.gate_text(self.asking([ask], kinds=("fork",)), run_id="run-1").splitlines()[2]
        self.assertEqual(only, gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")
        mixed = ask_before_fix.gate_text(self.asking([ask, NARROW_ITEM], kinds=("fork", "regression")), run_id="run-1").splitlines()[2]
        self.assertTrue(mixed.startswith(only), mixed)
        self.assertIn(gatemarks.NO_PUSH, mixed)
        unsaid = gatemarks.ask_text({**FORK, "reason": "空の列の意味が 2 つに割れる"})
        self.assertEqual(gatemarks.pushes([unsaid]), gatemarks.NO_PUSH, "ask_text の断りの句を推しと読まない")


def final_got(**kw) -> dict:
    """最後の関所の材料（ask_final.got_of_env の形）。既定は緑で、目は全部通り、申し出も守りのパスの当たりも無い"""
    eye = {"status": "pass", "reason": ""}
    got = {"tests_ok": True, "green": True, "red_cause": "", "protected_hits": [], "conflicts": [], "allowed_test_changes": [],
           "eyes": {"r1": eye, "r2": eye, "r3": eye, "r4": eye, "premise_check": None}, "questions": [], "objection": "",
           "rejudge_verdict": "", "sealed": True, "seal_reason": "", "hash": "a" * 64, "fenced": [], "held": [], "unread": ""}
    got.update(kw)
    return got


class FinalHeadCase(unittest.TestCase):
    def head(self, got):
        return ask_final.final_head(got, ask_final.final_needs(got))

    def test_three_lines_and_reasons(self):
        blocked = {"status": "redesign-needed", "reason": ""}
        got = self.head(final_got(green=False, red_cause="introduced", conflicts=[{"path": "fix/conflicts.json"}],
                                  eyes={**final_got()["eyes"], "r3": blocked}))
        self.assertEqual(heads("\n".join(got)), HEADS)
        for want in ("テストは赤", "食い違いの申し出を人に回した（1 件）", "独立の目が阻害を返した（R3）"):
            self.assertIn(want, got[0])
        self.assertEqual(got[2], gatemarks.PUSH + gatemarks.NO_PUSH)
        self.assertEqual(internal_subjects("\n".join(got)), [])

    def test_protected_named_in_the_first_line(self):
        got = self.head(final_got(protected_hits=["tests/test_stats.py"]))
        self.assertIn(ask_final.PROTECTED_HEAD, got[0])
        self.assertIn("人の確かめが要る", got[0])
        self.assertIn("守りのパス", got[1])
        unknown = self.head(final_got(protected_hits=[seal.unknown_row("一覧が読めない")]))
        self.assertIn(ask_final.PROTECTED_UNKNOWN, unknown[0])
        self.assertNotIn(ask_final.PROTECTED_HEAD, unknown[0])
        self.assertNotIn("守りのパス", "".join(self.head(final_got())[:2]))

    def test_final_edge_puts_the_head_before_the_sections(self):
        """最後の関所の文: 冒頭 3 行 → 空行 → 守りのパスの節（最初の見出し）→ 残りの節"""
        text = ask_final.final_text(final_got(protected_hits=["tests/test_stats.py"]), ["理由"], "run-1")
        lines = text.splitlines()
        self.assertEqual(heads(text), HEADS)
        self.assertEqual(lines[3], "")
        self.assertTrue(lines[4].startswith("## " + ask_final.PROTECTED_HEAD), lines[4])

    def test_when_needed_opens_on_the_same_reasons_as_the_first_line(self):
        """when_needed で開くかと 1 行目の開けた理由は同じ 1 つの列（final_needs）: 列が空なら開かず、在れば全部が 1 行目に載る"""
        self.assertFalse(ask_final.ask(final_got(), mode="when_needed", unattended=False, run_id="run-1")["open"])
        got = ask_final.ask(final_got(green=False, questions=["q"]), mode="when_needed", unattended=False, run_id="run-1")
        self.assertTrue(got["open"])
        self.assertIn("開けた理由: " + "・".join(got["reasons"]), got["text"].splitlines()[0])

    def test_unknown_eye_status_opens_when_needed(self):
        """表に無い status を返した目（R3）は『独立の目が阻害を返した』を開ける理由に入れる（when_needed で関所が開く）"""
        odd = {"status": "not-in-the-status-table", "reason": "表に無い"}
        got = final_got(eyes={**final_got()["eyes"], "r3": odd})
        self.assertEqual(ask_final.final_needs(got), ["独立の目が阻害を返した（R3）"])

    def test_held_questions_shown_but_not_a_reason(self):
        """保留にしたままの問いは 1 行目に出るが、開けた理由には数えない（when_needed で関所を開けない）"""
        got = final_got(held=[gatemarks.ask_text(FORK)])
        self.assertEqual(ask_final.final_needs(got), [])
        first = self.head(got)[0]
        self.assertIn("保留にしたままの問いも在る（1 件。関所を開ける理由には数えない）", first)
        self.assertNotIn("開けた理由: ", first)
        self.assertFalse(ask_final.ask(got, mode="when_needed", unattended=False, run_id="run-1")["open"])

    def test_push_from_held_questions(self):
        got = self.head(final_got(held=[gatemarks.ask_text(FORK)]))
        self.assertEqual(got[2], gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")
        got = self.head(final_got(questions=[gatemarks.ask_text(FORK)]))
        self.assertEqual(got[2], gatemarks.PUSH + "例外——呼び手が既に例外を捕まえている")

    def test_fence_rise_is_a_reason(self):
        row = {"where": "a.py", "text": "考えの住処: 止め（語）を知る場所が a.py で増えた"}
        self.assertEqual(ask_final.final_needs(final_got(fenced=[row])),
                         ["考えの住処の柵の数が増えた（1 件。住処へ寄せるか、増やすなら地図と柵の表を直す）"])


if __name__ == "__main__":
    unittest.main()
