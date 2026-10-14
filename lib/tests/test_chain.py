"""周の鎖の決め lib/chain.py と、結末の種の表 report.OUTCOME_KINDS の検査（純粋な関数を直に呼ぶ。ファイル・git は使わない）。

今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/tests/test_chain.py の Decide・NextRequest・Fences を元の試験名のまま写した。
起こした次の周の状態を読む 2 本（test_launched_pending_waits_while_child_lives・test_relaunch_is_capped_and_names_the_child_log）は、
起動と待ちをグラフの側が持つようになったので写さない。
"""
import ast
import pathlib
import re
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import carry  # noqa: E402


class _LibChain:
    """chain.py を使う時に読み込む（無い版でも試験の収集は落ちず、使った試験の中で読み込みに落ちる）"""

    def __getattr__(self, name):
        import importlib
        return getattr(importlib.import_module("chain"), name)


chain = _LibChain()

FINDING = {"where": "a.py:1", "text": "mean が空で落ちる"}


def row(n, kind=None, **kw):
    """周の行の見本（決めが読む欄）。kind を省けば open"""
    kind = kind or chain.KIND_OPEN
    base = {"n": n, "run": f"run-{n}", "outcome": "x", "kind": kind, "same_tree": False, "cost": 1.0, "cost_read": True,
            "keys": [f"k{n}"], "held": 0}
    base.update(kw)
    return base


def doc_of(rows, rounds_max=3, budget_usd=None):
    return {"rounds_max": rounds_max, "budget_usd": budget_usd, "rounds": rows}


class Decide(unittest.TestCase):
    def go(self, rows, facts=None, **kw):
        facts = rows[-1] if facts is None else facts
        return chain.decide(doc_of(rows, kw.get("rounds_max", 3), kw.get("budget_usd")), facts, kw.get("budget"))

    def test_closed_round_stops_with_closed(self):
        """結末の種が closed の周の後は、周の数が残っていても止め、止めの語は closed になる"""
        got = self.go([row(1, chain.KIND_CLOSED)])
        self.assertEqual((got["act"], got["word"]), ("stop", "closed"))
        self.assertIn(got["word"], chain.STOPS)

    def test_open_round_below_limit_goes_on(self):
        """結末の種が open で周の数が残り、木が前と違い残りの鍵も前と違えば、次の周へ進む"""
        rows = [row(1, keys=["a"]), row(2, keys=["b"])]
        got = self.go(rows, rounds_max=3)
        self.assertEqual(got["act"], "launch", got)
        self.assertEqual(got["word"], "")

    def test_rounds_reached_stops(self):
        """周の数に達したら、結末の種に依らず rounds_reached で止める（周の数が結末の種より先に効く）"""
        for kind in (chain.KIND_OPEN, chain.KIND_CLOSED, chain.KIND_HUMAN):
            with self.subTest(kind=kind):
                got = self.go([row(1), row(2, kind)], rounds_max=2)
                self.assertEqual((got["act"], got["word"]), ("stop", "rounds_reached"))

    def test_halted_human_and_wait_kinds(self):
        """止まった周は halted、人が要る周は human で止まり、途中で落ちた周（wait）は次の周を起こさない（aborted）"""
        self.assertEqual(self.go([row(1, chain.KIND_HALTED)])["word"], "halted")
        self.assertEqual(self.go([row(1, chain.KIND_HUMAN)])["word"], "human")
        got = self.go([row(1, chain.KIND_WAIT)])
        self.assertEqual(got["act"], "aborted")
        self.assertNotEqual(got["act"], "launch")

    def test_halted_names_missing_and_unknown_outcome(self):
        """種が引けない周は halted で止め、文が結末の語の無さか、表に無い語を名指す"""
        got = self.go([row(1)], {**row(1), "kind": None, "outcome": ""})
        self.assertEqual((got["act"], got["word"]), ("stop", "halted"))
        self.assertIn("結末の語が無い", got["text"])
        got = self.go([row(1)], {**row(1), "kind": None, "outcome": "見知らぬ語"})
        self.assertEqual(got["word"], "halted")
        self.assertIn("'見知らぬ語' が表に無い", got["text"])

    def test_draft_rows_stop_for_human(self):
        """前の周の次の依頼に下書きの印の行が在れば human で止め、下書きを答えに替えない（findings の下書きも answers の下書きも）"""
        draft = carry.draft({"question": "q", "text": ""}, "gate")
        for nxt in ({"findings": [carry.draft(FINDING, "purpose")]}, {"findings": [FINDING], "answers": [draft]}):
            with self.subTest(nxt=nxt):
                got = self.go([row(1)], {**row(1), "held_rows": chain.held_rows(nxt)})
                self.assertEqual((got["act"], got["word"]), ("stop", "human"))
                self.assertIn("下書き", got["text"])

    def test_human_beats_no_change(self):
        """下書きの行と、木が周の頭と同じことが同時に在れば human（人が要るが進みが無いより先に効く）"""
        held = [carry.draft(FINDING, "purpose")]
        got = self.go([row(1, same_tree=True)], {**row(1, same_tree=True), "held_rows": held})
        self.assertEqual(got["word"], "human")

    def test_same_tree_and_same_items_stop(self):
        """周の結果の木が周の頭と同じなら no_change。残りの行の鍵の集合が前の周と同じなら same_items"""
        got = self.go([row(1, same_tree=True)])
        self.assertEqual(got["word"], "no_change")
        got = self.go([row(1, keys=["a", "b"]), row(2, keys=["b", "a"])])
        self.assertEqual(got["word"], "same_items")
        got = self.go([row(1, keys=["a", "b"]), row(2, keys=["a"])])
        self.assertEqual(got["act"], "launch")
        got = self.go([row(1, keys=[]), row(2, keys=[])])   # 鍵の無い残りは「同じ」と言えない
        self.assertEqual(got["act"], "launch")

    def test_budget_and_unreadable_cost(self):
        """上限が在る時だけ、累計＋最大の周の費用が上限を越えれば budget、読めない周が在れば cost_unread で止める。上限が無ければ費用で止めない"""
        rows = [row(1, cost=6.0), row(2, cost=8.0)]
        self.assertEqual(self.go(rows, budget_usd=20.0)["word"], "budget")      # 14 + 8 > 20
        self.assertEqual(self.go(rows, budget_usd=22.0)["act"], "launch")       # 14 + 8 = 22
        self.assertEqual(chain.decide(doc_of(rows), rows[-1], 20.0)["word"], "budget")   # 引数の上限が控えの値に勝つ
        unread = [row(1, cost=None, cost_read=False), row(2)]
        self.assertEqual(self.go(unread, budget_usd=100.0)["word"], "cost_unread")
        self.assertEqual(self.go([row(1, cost=0.0, cost_read=False)], budget_usd=100.0)["word"], "cost_unread")   # 0 と読まない
        self.assertEqual(self.go(unread)["act"], "launch")                       # 上限が無ければ読めなくても止めない
        self.assertEqual(self.go(rows)["act"], "launch")

    def test_stops_table_is_not_stopby(self):
        """鎖の止めの語は run の中の止めの理由（stopby）とは別の表。起動を殻が持った時の 2 語は持たない"""
        import stopby
        self.assertFalse(set(chain.STOPS) & set(getattr(stopby, "REASONS", {})))
        self.assertEqual(set(chain.STOPS), {"rounds_reached", "closed", "halted", "human", "no_change", "same_items", "budget",
                                            "cost_unread"})


class Step(unittest.TestCase):
    def test_error_halts_with_the_reason(self):
        """周の事実を読めなかった周は、決めの順に依らず halted で止め、文に訳が載る"""
        got = chain.step(doc_of([row(1)]), {**row(1), "error": "子の次の依頼が読めない", "request": "/r.json"})
        self.assertEqual((got["act"], got["word"]), ("stop", "halted"))
        self.assertIn("子の次の依頼が読めない", got["text"])

    def test_launch_without_a_request_halts(self):
        """次を起こす決めでも、運ぶ次の依頼が無ければ halted で止める"""
        self.assertEqual(chain.step(doc_of([row(1)]), {**row(1), "request": "/r.json"})["act"], "launch")
        got = chain.step(doc_of([row(1)]), {**row(1), "request": ""})
        self.assertEqual((got["act"], got["word"]), ("stop", "halted"))
        self.assertIn("運ぶ所見が無い", got["text"])

    def test_stop_is_not_turned_into_halted(self):
        got = chain.step(doc_of([row(1, chain.KIND_CLOSED)]), {**row(1, chain.KIND_CLOSED), "request": ""})
        self.assertEqual(got["word"], "closed")


class NextRequest(unittest.TestCase):
    def test_carries_findings_prior_and_first_answers(self):
        """前の周の下書きでない findings・prior_failures・constraints と、1 周目の answers・pr・issue を持ち、carry.parts で解ける。下書きは運ばない"""
        prior = [{"where": "受け付け x", "text": "R2 が redesign-needed: 作り直し"}]
        measured = [{"text": "設定は 3 つ", "measured_how": "前の run の前提の検算（run r1）", "kind": carry.MEASURED}]
        prev = {"findings": [FINDING, carry.draft({"where": "b.py", "text": "目的の外"}, "purpose")], "prior_failures": prior,
                "constraints": measured, "answers": [carry.draft({"question": "q2", "text": ""}, "gate")]}
        first = {"findings": [{"where": "z", "text": "1 周目の所見"}], "pr": [12], "issue": [3],
                 "answers": [{"question": "q1", "text": "依頼者の答え"}], "prior_failures": [{"where": "w", "text": "t"}]}
        got = chain.next_request(prev, first)
        parts = carry.parts(got)
        self.assertEqual(parts["findings"], [FINDING])
        self.assertEqual(parts["prior_failures"], prior)
        self.assertEqual(parts["constraints"], measured)
        self.assertEqual((parts["pr"], parts["issue"]), ([12], [3]))
        self.assertEqual(parts["answers"], first["answers"])
        self.assertEqual(len(chain.held_rows(prev)), 2)

    def test_without_first_request(self):
        """1 周目の依頼が無い（変更だけ）鎖は、前の周の残りだけで組む。1 周目の答えは無い"""
        got = chain.next_request({"findings": [FINDING], "prior_failures": []}, None)
        self.assertEqual(carry.parts(got)["answers"], [])
        self.assertEqual(got["findings"], [FINDING])
        self.assertEqual(chain.next_request(None, None), {"findings": [], "prior_failures": []})

    def test_first_pr_is_carried_in_the_pr_field(self):
        """1 周目に名指した PR の番号は、1 周目の依頼の pr の欄に重ねずに足す（次の周の入力 pr には使わない）"""
        self.assertEqual(chain.first_of({"findings": [FINDING], "pr": [7]}, 7)["pr"], [7])
        self.assertEqual(chain.first_of({"findings": [FINDING], "pr": [3]}, 7)["pr"], [3, 7])
        self.assertEqual(chain.first_of([FINDING], 7), {"findings": [FINDING], "pr": [7]})
        self.assertEqual(chain.first_of(None, 7), {"findings": [], "pr": [7]})
        self.assertIsNone(chain.first_of(None, 0))
        got = chain.next_request({"findings": [FINDING]}, chain.first_of(None, 7))
        self.assertEqual(carry.parts(got)["pr"], [7])

    def test_keys_are_the_non_draft_findings(self):
        nxt = {"findings": [FINDING, carry.draft({"where": "b.py", "text": "目的の外"}, "purpose")]}
        self.assertEqual(chain.keys_of(nxt), [carry.row_key(FINDING)])
        self.assertEqual(chain.keys_of(None), [])


class Limits(unittest.TestCase):
    def test_rounds_are_one_to_max(self):
        for raw in ("1", "5", " 3 "):
            with self.subTest(raw=raw):
                self.assertEqual(chain.limits(raw, ""), (int(raw), None))
        for raw in ("", "0", "6", "2.0", "x", "-1", None):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "rounds"):
                    chain.limits(raw, "")
        self.assertEqual(chain.MAX_ROUNDS, 5)

    def test_budget_is_empty_or_positive(self):
        self.assertEqual(chain.limits("2", ""), (2, None))
        self.assertEqual(chain.limits("2", "3.5"), (2, 3.5))
        self.assertEqual(chain.limits("2", "10"), (2, 10.0))
        for raw in ("0", "-1", ".", "1.2.3", "x", "1.", "0.0"):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "budget_usd"):
                    chain.limits("2", raw)


class Pick(unittest.TestCase):
    def test_last_halted_round_is_skipped_and_named(self):
        rows = [row(1, head="h1"), row(2, head="h2"), row(3, chain.KIND_HALTED, head="h3")]
        kept, skipped = chain.pick(rows)
        self.assertEqual((kept["n"], [r["n"] for r in skipped]), (2, [3]))

    def test_round_without_a_commit_is_skipped_and_named(self):
        kept, skipped = chain.pick([row(1, head="h1"), row(2, chain.KIND_HUMAN, head="")])
        self.assertEqual((kept["n"], [r["n"] for r in skipped]), (1, [2]))

    def test_no_round_to_take(self):
        kept, skipped = chain.pick([row(1, chain.KIND_HALTED, head="h1")])
        self.assertEqual((kept, [r["n"] for r in skipped]), (None, [1]))
        self.assertEqual(chain.pick([]), (None, []))


class Render(unittest.TestCase):
    def doc(self, rows, **kw):
        return {"run": "parent", "rounds_max": 3, "rounds": rows, "stop": {"word": "halted", "text": "run が止まった"},
                "original_base": "b" * 40, "final": "/runs/parent/chain/final.diff", "apply": "bin/apply parent", **kw}

    def table(self, text):
        return [ln for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith(("| 周", "| ---"))]

    def test_rows_and_total(self):
        rows = [row(1, head="h1", minutes=10.2, cost=1.5, files=2), row(2, head="h2", minutes=4.9, cost=2.25, files=1)]
        text = chain.render(self.doc(rows, stop={"word": "closed", "text": "閉じた"}))
        self.assertEqual(self.table(text), ["| 1 | run-1 | x | 10 | 1.50 | 1 | 2 |", "| 2 | run-2 | x | 5 | 2.25 | 1 | 1 |"])
        self.assertIn("合計: 2 周・15 分・$3.75\n", text)
        self.assertIn("周 2 の結果までを最後の差分にした", text)
        self.assertIn("取り込む: bin/apply parent", text)

    def test_unread_cost_is_named_and_left_out_of_the_total(self):
        rows = [row(1, head="h1", cost=1.5), row(2, head="h2", cost=None, cost_read=False), row(3, head="h3", cost=2.0)]
        text = chain.render(self.doc(rows))
        self.assertEqual(self.table(text)[1].split(" | ")[4], "読めない")
        self.assertIn("$3.50（費用が読めない周 1 本を除く）", text)
        self.assertNotIn("0.00", text)

    def test_halted_round_is_named_with_its_diff(self):
        rows = [row(1, head="h1"), row(2, head="h2"), row(3, chain.KIND_HALTED, head="h3", diff="/runs/parent/chain/round-3.diff")]
        text = chain.render(self.doc(rows))
        self.assertIn("周 2 の結果までを最後の差分にした", text)
        self.assertIn("止まった周 周 3（run run-3。差分 /runs/parent/chain/round-3.diff） は最後の差分に採らなかった", text)
        self.assertIn("止まった周 3: 差分 /runs/parent/chain/round-3.diff", text)

    def test_round_whose_commit_failed_names_the_worktree_not_a_kept_diff(self):
        rows = [row(1, head="h1"), row(2, chain.KIND_HUMAN, head="")]
        text = chain.render(self.doc(rows, worktree="/wt/parent"))
        self.assertIn("周 1 の結果までを最後の差分にした", text)
        self.assertIn("止まった周 周 2（run run-2。commit できなかった。作業は作業ツリー /wt/parent に残り、片付けで消える）", text)
        self.assertIn("止まった周 2: commit できなかった", text)
        self.assertNotIn("差分 無し", text)

    def test_human_stop_names_the_draft_and_the_steps(self):
        rows = [row(1, head="h1", held=2, source="/runs/c1/report/next-request.json")]
        text = chain.render(self.doc(rows, stop={"word": "human", "text": "人の判断が要る"}))
        self.assertIn("運ばなかった下書きの行 2 件", text)
        self.assertIn("1. 下書き /runs/c1/report/next-request.json の", text)
        self.assertIn("2. 取り込むなら bin/apply parent", text)
        self.assertIn("3. 見直した依頼を request に渡して", text)

    def test_nothing_to_take_has_no_apply_line(self):
        text = chain.render(self.doc([row(1, chain.KIND_HALTED, head="h1")], final=""))
        self.assertIn("採れる周が無かった", text)
        self.assertNotIn("取り込む", text)


class OutcomeKindsTest(unittest.TestCase):
    def test_keys_match_outcomes_and_values_are_kinds(self):
        """結末の種の表は結末の語の 10 語ちょうどを鍵に持ち、値は鎖の 5 つの種のどれか"""
        import report
        self.assertEqual(set(report.OUTCOME_KINDS), set(report.OUTCOMES))
        self.assertEqual(len(report.OUTCOMES), 10)
        self.assertLessEqual(set(report.OUTCOME_KINDS.values()), set(chain.KINDS))

    def test_kinds_group_the_outcomes(self):
        """種の分け方は鎖の安全に効く: open だけが次の周を起こし、closed だけが閉じ、人の止めは止まり、要確認は人へ回る"""
        import report
        groups = {kind: {o for o, k in report.OUTCOME_KINDS.items() if k == kind} for kind in chain.KINDS}
        self.assertEqual(groups, {
            chain.KIND_OPEN: {"round_limit"},
            chain.KIND_CLOSED: {"fixed", "no_fix_needed"},
            chain.KIND_HUMAN: {"fixed_needs_check", "needs_human"},
            chain.KIND_WAIT: {"interrupted"},
            chain.KIND_HALTED: {"stopped_by_request", "stopped_by_human", "stopped_by_line", "record_invalid"},
        })


class Fences(unittest.TestCase):
    def test_chain_names_no_outcome_word(self):
        """結末の語を字で持てるのは結末の住処だけ。鎖は種（OUTCOME_KINDS）だけを引く"""
        import report
        text = (LIB / "chain.py").read_text(encoding="utf-8")
        for word in report.OUTCOMES:
            self.assertIsNone(re.search(rf"[\"']{word}[\"']", text), word)

    def test_layer_one_imports(self):
        """chain は標準ライブラリと持ち越しの住処 carry・見出しの宣言 promptsection だけを import する"""
        tree = ast.parse((LIB / "chain.py").read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertLessEqual(names - set(sys.stdlib_module_names), {"carry", "promptsection"})


if __name__ == "__main__":
    unittest.main()
