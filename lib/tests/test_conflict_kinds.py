"""食い違いの申し出の種類の欄 kind（conflict.DIV_KINDS の 6 つ）と、which_is_right との対の確かめ（依頼 211）。

- kind は申し出の必須の欄（conflict.FIELDS の末尾）。語の外の値は拒み、文に種類の名を並べる
- 対: kind query_hits_fixed ⇔ which_is_right query、kind needs_context なら which_is_right unknown。外れは両方の欄を名指して拒む
- 語の定数 conflict.WORD（216 の seams.json の words と同じ綴り）・TDD の輪の申し出の見本と決まりの節が種類を全部言う
- 控えの行と trace の行に kind が載り、種類の内訳（kind_counts）が数える。kind の無い前の形の行も読めて「無し」と出る
- brief_vs_judgment は、その単位の brief の行（planbrief.by_unit_at の形）を between に名指す時だけ通す。brief の無い run・
  ほかの項目の brief だけの名指しは拒む。brief の控えが壊れていれば brief は無い側（通さない側）に倒す
- 裁定 fix_plan_item（案の項目そのものの誤り）は直す裁定でなく、範囲 limits を持たず、grounds にその単位の brief の行を
  名指す時だけ通る（brief_vs_judgment と同じ 1 つの決まり）。役の返答の形・裁定役の決まりの節がこの語を持つ
- 直す義務から外す単位は「直す裁定でない裁定を受けた単位」の 1 つの決まりで、2 つ当たれば DECISIONS の順で先の理由
- fix_plan_item の行の案の直しの状態（waiting・amended・gave_up。依頼 226）: 裁定で waiting に置き、set_replan の 1 か所で
  amended か gave_up に移す。amended の単位は直す義務に戻り、gave_up の行は ask_human の行として字のまま並ぶ。欄の無い前の形の
  行は waiting と読む
- （fix の試験へ移った）修正役の受け付け（fixboard.accept_reply）は、直す義務の外の単位の申し出と、申し出た単位を changes にも書いた返答を
  食い違いの申し出の拒否（check conflict）にし、積まない（FixAcceptSeamCase。元 works/blk-fix/scripts/accept.py:319-333）
盤面・子のプロセスは使わない（関数を直に呼ぶ。一時の置き場に種のファイルと控えを書くだけ。git は FixAcceptSeamCase の
受け付けが段の頭の木と版を引く小さなリポジトリだけ）。
"""
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
import fixboard  # noqa: E402
import rulebook  # noqa: E402

# 決まりの文の本体の置き場（scripts が import の後にする置き替えと同じ。lib/ の字にパスを書かない）
FR = LIB.parent / "workflows" / "fix" / "commands" / "fix-rules"
rulebook.CANON = FR / "common.md"

KEY = "stats.py clamp: 上限を超えた値に lo を返す"
ITEM = {"unit_key": KEY, "between": ["stats.py:3", "test_stats.py:2"],
        "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
        "which_is_right": "request", "kind": "unnamed_test_broke"}
OTHER = "stats.py mean: 分母が len - 1"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
BRIEFS: dict = {}   # BriefKindCase.setUp が一時の置き場の brief で埋める（planbrief.by_unit_at の形）


def seed(repo: pathlib.Path) -> None:
    """名指しの種（stats.py は 4 行・test_stats.py は 2 行）"""
    (repo / "stats.py").write_text("def clamp(x, lo, hi):\n    if x > hi:\n        return lo\n    return x\n",
                                   encoding="utf-8")
    (repo / "test_stats.py").write_text("def test_clamp():\n    assert clamp(11, 0, 10) == 10\n", encoding="utf-8")


class KindCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        seed(self.repo)

    def errs(self, **over):
        return conflict.problems([{**ITEM, **over}], repo=self.repo, board_dir=self.repo, owed={KEY})

    def test_kind_is_a_required_field(self):
        self.assertEqual(conflict.FIELDS[-1], "kind")
        self.assertIn("kind", conflict.ITEM_SCHEMA["required"])
        item = dict(ITEM)
        item.pop("kind")
        got = conflict.problems([item], repo=self.repo, board_dir=self.repo, owed={KEY})
        self.assertTrue(any("kind" in e for e in got), got)

    def test_design_kinds_and_two_kept(self):
        self.assertEqual(conflict.DIV_KINDS, ("brief_vs_judgment", "unnamed_test_broke", "not_red", "scope_needed",
                                              "query_hits_fixed", "needs_context"))
        self.assertEqual(self.errs(), [])
        got = self.errs(kind="other")
        self.assertTrue(any("kind" in e and "needs_context" in e for e in got), got)

    def test_kind_and_which_must_pair(self):
        for over in ({"which_is_right": "query", "correct_lines": ["        return hi"]},   # kind が query_hits_fixed でない
                     {"kind": "query_hits_fixed"},                                          # which_is_right が query でない
                     {"kind": "needs_context", "which_is_right": "request"}):
            got = self.errs(**over)
            self.assertTrue(any("kind" in e and "which_is_right" in e for e in got), (over, got))
        self.assertEqual(self.errs(kind="needs_context", which_is_right="unknown"), [])

    def test_problems_by_entry_names_the_unit_of_each_entry(self):
        # 申し出ごとに (i, 読めた unit_key か None, 文の並び)。key は dict の unit_key が str で owed に在る時だけ読める
        items = [{**ITEM, "kind": "other"},                        # 欄は揃う（key は読める）が kind の文
                 {**ITEM, "unit_key": "stats.py ghost: 無い単位"},   # owed に無い key
                 {"unit_key": KEY},                                 # 欄の崩れ
                 "dict でない"]
        got = conflict.problems_by_entry(items, repo=self.repo, board_dir=self.repo, owed={KEY})
        self.assertEqual([(i, k) for i, k, _ in got], [(0, KEY), (1, None), (2, None), (3, None)])
        self.assertTrue(all(lines for _, _, lines in got), got)
        self.assertTrue(all(line.startswith(f"食い違い[{i}]") for i, _, lines in got for line in lines), got)
        flat = [line for _, _, lines in got for line in lines]
        self.assertEqual(conflict.problems(items, repo=self.repo, board_dir=self.repo, owed={KEY}), flat)
        self.assertEqual(conflict.problems_by_entry([ITEM], repo=self.repo, board_dir=self.repo, owed={KEY}), [(0, KEY, [])])
        self.assertEqual([(i, k) for i, k, _ in conflict.problems_by_entry([], repo=self.repo, board_dir=self.repo, owed={KEY})],
                         [(None, None)], "配列全体の誤りは i も None")

    def test_word_names_the_outlet(self):
        self.assertEqual(conflict.WORD, "divergence")


class FakeBoard:
    """置き場（fix の run の置き場のフォルダ。conflict は pathlib.Path(b) で受ける）の試験の口: work(name) は置き場のファイル、
    traced は置き場の trace.jsonl の行 (op, その外の欄)（fixboard.trace が足した物）"""

    def __init__(self, root: pathlib.Path):
        self.root = self.dir = root

    def __fspath__(self) -> str:
        return str(self.root)

    def work(self, name) -> pathlib.Path:
        return self.root / name

    @property
    def traced(self) -> list:
        p = self.root / fixboard.TRACE_FILE
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []
        return [(r.pop("op"), r) for r in rows]


class KindRowsCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.b = FakeBoard(pathlib.Path(tmp.name))

    def write_items(self, rows):
        self.b.work(conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")

    def test_park_keeps_kind_and_traces_it(self):
        conflict.park(self.b, [ITEM], source="fix")
        self.assertEqual(conflict.items(self.b)[0]["kind"], "unnamed_test_broke")
        self.assertEqual(self.b.traced[0][1]["kind"], "unnamed_test_broke")
        self.assertEqual(conflict.kind_counts(self.b)["unnamed_test_broke"], 1)

    def test_rows_without_kind_still_read(self):
        legacy = {k: ITEM[k] for k in ("unit_key", "between", "why_both_cannot_hold", "which_is_right")}
        self.write_items([{"id": "c1-1", "round": 1, "source": "fix", **legacy, "status": "ruled",
                           "ruling": {"decision": "ask_human", "text": "方針の変更で人が決める", "limits": [], "by": "x"}}])
        self.assertEqual(conflict.kind_counts(self.b)["unset"], 1)
        self.assertIn("種類 無し", conflict.human_lines(self.b)[0])


class HeldByRulingsCase(KindRowsCase):
    """直す義務から外す単位の 1 つの決まり（直す裁定でない裁定を受けた単位）と、理由の文"""

    def test_one_rule_with_sorted_reasons(self):
        ruled = {"text": "裁きの文を十字以上で書く", "limits": [], "by": "x"}
        self.write_items([
            {"id": "c1-1", "unit_key": KEY, "ruling": {**ruled, "decision": "fix_plan_item", "plan_items": [2]},
             conflict.REPLAN_STATE: conflict.WAITING},
            {"id": "c1-2", "unit_key": OTHER, "ruling": {**ruled, "decision": "fix_plan_item", "plan_items": [1, 3]},
             conflict.REPLAN_STATE: conflict.WAITING},
            {"id": "c1-3", "unit_key": OTHER, "ruling": {**ruled, "decision": "ask_human"}},
            {"id": "c1-4", "unit_key": "u-code", "ruling": {**ruled, "decision": "fix_code_as"}},
            {"id": "c1-5", "unit_key": "u-open", "ruling": None}])
        self.assertEqual(conflict.held_by_rulings(self.b),
                         {KEY: "fix_plan_item の裁定 c1-1（案の項目 2）", OTHER: "ask_human の裁定 c1-3"})


class BriefKindCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.dir = pathlib.Path(tmp.name) / "board"
        self.repo.mkdir()
        self.dir.mkdir()
        seed(self.repo)
        self.brief1, self.brief2 = self.dir / "brief-1.md", self.dir / "brief-2.md"
        self.brief1.write_text("# brief 1\n上限を超えた値に hi を返す\n範囲は stats.py だけ\n", encoding="utf-8")
        self.brief2.write_text("# brief 2\n", encoding="utf-8")
        BRIEFS.clear()
        BRIEFS.update({KEY: [{"item": 1, "file": str(self.brief1)}], OTHER: [{"item": 2, "file": str(self.brief2)}]})

    def errs(self, item, briefs):
        return conflict.problems([item], repo=self.repo, board_dir=self.dir, owed={KEY}, briefs=briefs)

    def test_brief_kind_needs_the_units_brief(self):
        item = {**ITEM, "kind": "brief_vs_judgment", "between": [f"{self.brief1}:2", "stats.py:3"]}
        self.assertEqual(self.errs(item, briefs=BRIEFS), [])
        got = self.errs(item, briefs=None)
        self.assertTrue(any("brief_vs_judgment" in e and "brief が無い" in e for e in got), got)
        other = {**item, "between": [f"{self.brief2}:1", "stats.py:3"]}
        got = self.errs(other, briefs=BRIEFS)
        self.assertTrue(any("brief_vs_judgment" in e and str(self.brief1) in e for e in got), got)

    def test_other_kinds_ignore_briefs(self):
        self.assertEqual(self.errs(ITEM, briefs=None), [])

    def test_broken_ledger_gives_no_briefs(self):
        # 壊れた控え・無い置き場は brief の無い側（{}）。元は盤面を開く口も mock したが、今は置き場のパスで読む
        from unittest import mock
        import planbrief
        with mock.patch.object(planbrief, "_ledger", side_effect=planbrief.LedgerBroken("x")):
            self.assertEqual(planbrief.by_unit_at(self.dir), {})
        self.assertEqual(planbrief.by_unit_at(self.dir / "no-board"), {})


def fake_with_rows(rows):
    """一時の置き場（FakeBoard）に、申し出の行 rows を置いた物。一時の置き場はモジュールの終わりに消す"""
    root = pathlib.Path(tempfile.mkdtemp())
    unittest.addModuleCleanup(shutil.rmtree, root, ignore_errors=True)
    b = FakeBoard(root)
    b.work(conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")
    return b


def row(rid, key, decision, *, state=None, text="受け入れのテストの赤の種類を exception に直す", plan_units=()):
    """申し出の行 1 つ（decision が None なら裁いていない行。state は欄 replan の値で、None なら欄を置かない）"""
    out = {"id": rid, "round": 1, "source": "fix", "unit_key": key, "between": ["stats.py:3", "test_stats.py:2"],
           "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
           "which_is_right": "request", "kind": "brief_vs_judgment", "status": "ruled" if decision else "parked",
           "ruling": None if decision is None else
           {"decision": decision, "text": text, "limits": [], "by": "t",
            **({"plan_items": [1], "plan_units": list(plan_units)} if plan_units else {})}}
    if state is not None:
        out["replan"] = state
    return out


class TestReplanState(unittest.TestCase):
    def test_ruling_starts_waiting_and_holds(self):
        b = fake_with_rows([row("c1-1", MEAN, None)])                # 裁いていない申し出の行
        conflict.apply_rulings(b, {"c1-1": {"decision": "fix_plan_item", "text": "x" * 20, "limits": [],
                                            "plan_items": [1], "plan_units": [MEAN, CLAMP]}}, by="t")
        self.assertEqual(conflict.items(b)[0]["replan"], "waiting")
        self.assertEqual([r["id"] for r in conflict.waiting(b)], ["c1-1"])
        self.assertEqual(set(conflict.held_by_rulings(b)), {MEAN, CLAMP})
        self.assertEqual(conflict.asked(b), [])

    def test_other_rulings_have_no_state(self):
        b = fake_with_rows([row("c1-1", MEAN, None), row("c1-2", CLAMP, None)])
        conflict.apply_rulings(b, {"c1-1": {"decision": "ask_human", "text": "x" * 20, "limits": []},
                                   "c1-2": {"decision": "fix_code_as", "text": "x" * 20, "limits": []}}, by="t")
        self.assertTrue(all("replan" not in r for r in conflict.items(b)))
        self.assertEqual([conflict.replan_state(r) for r in conflict.items(b)], [None, None])
        self.assertEqual(conflict.waiting(b), [])
        self.assertEqual([r["id"] for r in conflict.asked(b)], ["c1-1"])

    def test_amended_rows_return_units_to_duty(self):
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="waiting")])
        conflict.set_replan(b, ["c1-1"], conflict.AMENDED)
        self.assertEqual(conflict.held_by_rulings(b), {})
        self.assertEqual(conflict.amended_keys(b), {MEAN})
        self.assertEqual(conflict.waiting(b), [])
        self.assertEqual(conflict.asked(b), [])
        self.assertEqual(b.traced, [(conflict.REPLAN_OP, {"id": "c1-1", "unit_key": MEAN, "state": "amended", "why": ""})])

    def test_amended_keys_cover_the_items_units(self):
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="amended", plan_units=[MEAN, CLAMP]),
                            row("c1-2", "u-wait", "fix_plan_item", state="waiting")])
        self.assertEqual(conflict.amended_keys(b), {MEAN, CLAMP})
        self.assertEqual(set(conflict.held_by_rulings(b)), {"u-wait"})

    def test_amended_units_are_one_of_the_test_permits(self):
        """keep-essence の 3: テストの変更を許す道は conflict.test_permits の 1 つ。案の直しで直した項目の単位（前の輪の受け入れの
        テストの関数を変えてよい）もその行として返る（units を持ち、範囲の文字列 limit は持たない）。範囲の読み ruled_test_limits と
        最後の関所の一覧 ruled_test_doc は範囲の行だけを読む"""
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="amended", plan_units=[MEAN, CLAMP]),
                            row("c1-2", "u-wait", "fix_plan_item", state="waiting")])
        rows = conflict.test_permits(b)
        self.assertEqual([sorted(r["units"]) for r in rows if "units" in r], [sorted([MEAN, CLAMP])])
        self.assertTrue(all("limit" not in r and r["why"].strip() and r["id"] for r in rows if "units" in r))
        self.assertEqual(conflict.ruled_test_limits(b), [])
        self.assertIsNone(conflict.ruled_test_doc(b))
        self.assertEqual(conflict.permitted_units(b), {MEAN, CLAMP})

    def test_permit_sources_are_read_in_one_place(self):
        """keep-essence の 3: 許す元（修正案の rewrite_tests・範囲の相談の合意・裁定 fix_test_scope・案の直しで直した項目）を読むのは
        conflict.test_permits の 1 か所。凍結の検査・事後の関門・範囲の照らしはその行を読み、元を直に読まない"""
        root = LIB
        direct = re.compile(r"\b(?:planmarks\.rewrites|amended_keys|agreed_permits|ruled_limits)\(")
        found = [f"{p.relative_to(root)}:{i}" for p in sorted(root.rglob("*.py"))
                 if p.relative_to(root).parts[0] != "tests" and p.name not in ("conflict.py", "planmarks.py")
                 for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if direct.search(line)]
        self.assertEqual(found, [])

    def test_gave_up_rows_join_ask_human_verbatim(self):
        text = "受け入れのテストの id を\nクラス付きにする（test_tiers.py:136-143）"
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="waiting", text=text),
                            row("c1-2", CLAMP, "ask_human")])
        conflict.set_replan(b, ["c1-1"], conflict.GAVE_UP, why="修正案の役の直しが 3 回とも拒まれた: 数が違う")
        line = conflict.human_lines(b)[0]
        self.assertIn(text, line)                                  # 字のまま（改行も）
        self.assertIn("案の直し: 修正案の役の直しが 3 回とも拒まれた: 数が違う", line)
        self.assertTrue(line.endswith(f"・案の直し: 修正案の役の直しが 3 回とも拒まれた: 数が違う・{conflict.HELD_WORK_KEPT}）"), line)
        self.assertNotIn("案の直し", conflict.human_lines(b)[1])
        self.assertEqual([r["id"] for r in conflict.asked(b)], ["c1-1", "c1-2"])
        self.assertIn(MEAN, conflict.held_by_rulings(b))           # 諦めた行の単位は直す義務の外のまま
        self.assertEqual(conflict.items(b)[0]["replan_why"], "修正案の役の直しが 3 回とも拒まれた: 数が違う")
        self.assertEqual(b.traced[-1][1]["state"], "gave_up")

    def test_human_lines_say_where_the_fix_is_by_kind(self):
        """query_hits_fixed は修正役が直してから申し出るので、人に回った行は直しが差分に在り閉じたかの数えだけが決め待ちと言い、
        直さずに残したと言わない。ほかの種類は直さずに残した（#355）"""
        query = {**row("c1-1", CLAMP, "ask_human"), "which_is_right": "query", "kind": "query_hits_fixed",
                 "correct_lines": ["        return lo"]}
        b = fake_with_rows([query, row("c1-2", MEAN, "ask_human")])
        fixed_first, left = conflict.human_lines(b)
        self.assertIn(conflict.FIX_IN_DIFF, fixed_first)
        self.assertNotIn(conflict.UNFIXED_LEFT, fixed_first)
        self.assertIn(conflict.UNFIXED_LEFT, left)
        self.assertNotIn(conflict.FIX_IN_DIFF, left)

    def test_mixed_unit_is_one_place_for_every_reader(self):
        """#368: 1 単位に query_hits_fixed とほかの種類の人に回した行が混ざる時、直しの在りかは conflict.fix_place の 1 つ（直していない
        直しを差分に在ると言わない LEFT）で、関所の行・直す義務から外す理由・裁定へ回した理由が同じ事を言う"""
        query = {**row("c1-1", CLAMP, "ask_human"), "which_is_right": "query", "kind": "query_hits_fixed",
                 "correct_lines": ["        return lo"]}
        broke = {**row("c1-2", CLAMP, "ask_human"), "kind": "unnamed_test_broke"}
        b = fake_with_rows([query, broke])
        self.assertEqual(conflict.fix_place([query, broke]), conflict.LEFT)
        self.assertEqual(conflict.fix_place([query]), conflict.IN_DIFF)
        self.assertEqual(conflict.fix_place([{**query, conflict.REVERTED_FIELD: "p.patch"}]), conflict.REVERTED)
        self.assertEqual(conflict.fix_place([{**broke, conflict.REPLAN_WHY: "諦めた"}]), conflict.KEPT)
        for line in conflict.human_lines(b):
            with self.subTest(line):
                self.assertIn(conflict.UNFIXED_LEFT, line)
                self.assertNotIn(conflict.FIX_IN_DIFF, line)
        self.assertNotIn(conflict.FIX_IN_DIFF, conflict.held_by_rulings(b)[CLAMP])

    def test_gave_up_row_keeps_the_unit_fix_in_the_tree(self):
        """諦めた fix_plan_item の行（修正役に直した分を戻すなと約束した。GAVE_UP_PROMISE）と別の ask_human の行が同じ単位に並ぶ時、
        単位の直しの在りかは KEPT で、関所の両方の行が直した分を作業ツリーに残したと言う（直さずに残したと言わない）"""
        b = fake_with_rows([row("c1-1", CLAMP, "fix_plan_item", state="waiting"),
                            {**row("c1-2", CLAMP, "ask_human"), "kind": "unnamed_test_broke"}])
        conflict.set_replan(b, ["c1-1"], conflict.GAVE_UP, why="直せなかった")
        self.assertEqual(conflict.fix_place(conflict.unit_rows(conflict.asked(b), CLAMP)), conflict.KEPT)
        for line in conflict.human_lines(b):
            with self.subTest(line):
                self.assertIn(conflict.HELD_WORK_KEPT, line)
                self.assertNotIn(conflict.UNFIXED_LEFT, line)

    def test_fix_place_is_chosen_in_one_place(self):
        """#368: 直しの在りかを種類と控えの欄から選ぶのは conflict.fix_place だけ。読み手は fix_place・place_words を引き、欄を直に見ない"""
        direct = re.compile(r"\bconflict\.(REVERTED_FIELD|FIX_IN_DIFF|UNFIXED_LEFT|FIX_REVERTED|left_words)\b|QUERY_HITS_FIXED\s*\}")
        found = [f"{p.relative_to(LIB)}:{i}" for p in sorted(LIB.rglob("*.py"))
                 if p.relative_to(LIB).parts[0] != "tests" and p.name != "conflict.py"
                 for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if direct.search(line.split("#")[0])]
        self.assertEqual(found, [])

    def test_bad_transition_is_board_gap(self):
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="gave_up"),
                            row("c1-2", CLAMP, "fix_plan_item", state="waiting"),
                            row("c1-3", "u-ask", "ask_human")])
        before = b.work(conflict.FILE).read_text(encoding="utf-8")
        for ids, state, why in ((["c1-1"], conflict.AMENDED, ""),       # 諦めた行は戻さない
                                (["c1-2"], conflict.GAVE_UP, ""),       # why の無い諦め
                                (["c1-2"], conflict.GAVE_UP, "  "),
                                (["c1-2"], conflict.WAITING, ""),       # waiting へは移さない
                                (["c1-3"], conflict.AMENDED, ""),       # fix_plan_item でない行
                                (["c9-9"], conflict.AMENDED, ""),       # 知らない id
                                (["c1-2", "c1-1"], conflict.AMENDED, "")):   # 1 つでも外れれば何も移さない
            with self.subTest(ids=ids, state=state, why=why), self.assertRaises(ValueError):
                conflict.set_replan(b, ids, state, why=why)
        self.assertEqual(b.work(conflict.FILE).read_text(encoding="utf-8"), before)
        self.assertEqual(b.traced, [])

    def test_same_state_is_a_no_op(self):
        b = fake_with_rows([row("c1-1", MEAN, "fix_plan_item", state="amended"),
                            row("c1-2", CLAMP, "fix_plan_item", state="gave_up")])
        conflict.set_replan(b, ["c1-1"], conflict.AMENDED)               # 再開で同じ移りが 2 度来る
        conflict.set_replan(b, ["c1-2"], conflict.GAVE_UP, why="別の理由")
        self.assertEqual(b.traced, [])
        self.assertNotIn("replan_why", conflict.items(b)[1])


if __name__ == "__main__":
    unittest.main()
