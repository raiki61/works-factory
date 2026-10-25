"""修正の block（workflows/fix/）の裁定の輪の試験（docs/design/fix.md の 14.2 の test_ruling.py）。

今の lib/tests/test_fix_seams.py の RulingSeamCase・ConflictSeamCase、tests/workflows/test_fix.py の RulerTypeCase と
FixLoopScriptsCase の rule の部分を写した物。写す時に置き場を place（standalone の run は $ARTIFACTS_DIR）に、始めの記録の値を
port（intake の values.json）に、`prompt_file` を `prompt` に替えた。

- ruling.prep・accept_rule（src/ruling.py）: place のファイルで回り、作業ツリーの控えは board.snapshot。prep は {values, iteration}
  （指示の文は prompts/ruler.md を src/prompts.ruler_values が組む）。配線の誤りは ValueError
- conflict（lib のまま呼ぶ）: 申し出の控えは place の conflicts.json、trace は place の trace.jsonl、壊れた控えは ValueError
- 節 ruler の output_format が裁定役の返答の型の正本（受け付けの ruling.problems は裁きの意味だけを見る）
- scripts rule_prep・rule_accept を子のプロセスで回す（始めの記録の無い使い捨ての run directory と target-seed の写し）
"""
import importlib
import json
import pathlib
import shutil
import unittest
from unittest import mock

import yaml

from tests.bin import hermetic, trimmed
from tests.bin.gitkit import committed_copy
from tests.blocks import kit

ROOT = kit.ROOT
SEED = ROOT / "tests" / "e2e" / "target-seed"
YAML_PATH = kit.BLOCKS / "fix" / "works-factory-fix.yaml"

ruling = kit.load("fix", "ruling")
board = importlib.import_module("src.board")       # ruling が読んだ物と同じ src（kit.load は読むたびに前の src を外す）
prompts = importlib.import_module("src.prompts")

import conflict  # noqa: E402  （lib のまま。kit.load が lib を sys.path に足した）
import rolekit  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

KEY_A = "stats.py clamp: 上限を超えた値に lo を返す"
KEY_B = "stats.py mean: 分母が len - 1"
CLAIM = {"unit_key": KEY_A, "between": ["stats.py:3", "test_stats.py:2"],
         "why_both_cannot_hold": "テストは上限 hi を期待し、今のコードは lo を返す——両方は成り立たない",
         "which_is_right": "request", "kind": "brief_vs_judgment"}
MEAN = "u-mean"
JUDGMENT = {"units": [
    {"key": MEAN, "label": "block", "class_query": {
        "how": {"patterns": ["(len(xs) - 1)"], "fixed": True, "paths": ["stats.py"], "count": "lines"},
        "counts": "defects", "total": 1}},
    {"key": "u-bound", "label": "block"}], "questions": []}
MEAN_CLAIM = {"unit_key": MEAN, "between": ["stats.py:9", "test_stats.py:8"],
              "why_both_cannot_hold": "テストの期待が誤った平均を前提にしている",
              "which_is_right": "request", "kind": "unnamed_test_broke"}


def _trace_rows(place) -> list:
    p = pathlib.Path(place) / "trace.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def all_nodes(doc) -> dict:
    out = {}
    for node in doc["nodes"]:
        out[node["id"]] = node
        for inner in (node.get("loop_group") or {}).get("nodes") or []:
            out[inner["id"]] = inner
    return out


class RulerTypeCase(unittest.TestCase):
    """裁定役の返答の型の正本は節 ruler の output_format だけ（受け付けの ruling.problems は裁きの意味だけを見る）"""

    def fmt(self) -> dict:
        return all_nodes(yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")))["ruler"]["output_format"]

    def test_trimmed_min_length_kept_by_pattern(self):
        self.assertEqual(trimmed.missing_patterns(self.fmt()), [])

    def test_decision_vocabulary_matches_output_format(self):
        """受け付けが裁きを分ける語（conflict.DECISIONS）は、節 ruler の output_format の decision の enum と同じ"""
        row = self.fmt()["properties"]["rulings"]["items"]["properties"]
        self.assertEqual(row["decision"]["enum"], list(conflict.DECISIONS))

    def test_ruling_outside_the_type_is_rejected(self):
        good = {"id": "c-1", "decision": conflict.ASK, "text": "材料から決められないので人に回す", "limits": []}
        self.assertEqual(validate_schema({"rulings": [good]}, self.fmt()), [])
        for name, reply in (("裁きが無い", {"rulings": []}), ("知らない語", {"rulings": [{**good, "decision": "later"}]}),
                            ("知らない欄", {"rulings": [{**good, "note": "x"}]}),
                            ("範囲が無い", {"rulings": [{k: v for k, v in good.items() if k != "limits"}]})):
            with self.subTest(name):
                self.assertTrue(validate_schema(reply, self.fmt()))


class RedAtBaseRulingCase(unittest.TestCase):
    """申し出の種類 red_at_base（下ごしらえが足した試験が起点の木で落ちる）に許す裁定は fix_plan_item・ask_human だけ（下書き 3.6）。
    fix_code_as は変えない段の注文でコードを変えさせるので、受け付け（ruling.problems）が拒む"""

    TODO = {"p-1": {"id": "p-1", "unit_key": "A", "source": conflict.FIX_SOURCE, "kind": conflict.RED_AT_BASE,
                    conflict.WHY_FIELD: "足した試験が起点の木で落ちる"}}

    def problems(self, decision):
        row = {"id": "p-1", "decision": decision, "text": "裁きの理由の文", "limits": []}
        return [e for e in ruling.problems({"rulings": [row]}, self.TODO, "/nonexistent") if conflict.RED_AT_BASE in e]

    def test_only_fix_plan_item_and_ask_human(self):
        for decision in conflict.DECISIONS:
            with self.subTest(decision=decision):
                if decision in (conflict.REPLAN, conflict.ASK):
                    self.assertEqual(self.problems(decision), [])
                else:
                    self.assertTrue(self.problems(decision))


class ConflictSeamCase(unittest.TestCase):
    """conflict の継ぎ目: 申し出の控えは place の conflicts.json {"items": [...]}、trace は place の trace.jsonl（board.trace）、
    周は引数 round_（既定 1）、壊れた控えは ValueError。直す義務の数え（board.fix_duty）は src の写し"""

    def setUp(self):
        self.place = hermetic.tmpdir(self)

    def test_park_writes_and_reads_the_places_json(self):
        c = conflict
        ids = c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        self.assertEqual(ids, ["c1-1"])
        doc = json.loads((self.place / "conflicts.json").read_text(encoding="utf-8"))
        self.assertEqual(list(doc), ["items"])
        self.assertEqual([r["unit_key"] for r in doc["items"]], [KEY_A])
        self.assertEqual(c.items(str(self.place))[0]["kind"], "brief_vs_judgment")   # 文字列のパスでも同じ置き場
        self.assertEqual([r["id"] for r in c.unruled(self.place)], ["c1-1"])
        self.assertEqual(c.park(self.place, [CLAIM], source=c.FIX_SOURCE), ["c1-1"], "同じ申し出は積み増さない")
        self.assertEqual([r["op"] for r in _trace_rows(self.place)], [c.PARK_OP])
        self.assertEqual(c.park(self.place, [{**CLAIM, "unit_key": KEY_B}], source=c.TDD_SOURCE, round_=2), ["c2-2"])

    def test_ruling_leaves_duty_and_fix_plan_item_gets_replan(self):
        c = conflict
        c.park(self.place, [CLAIM, {**CLAIM, "unit_key": KEY_B}], source=c.FIX_SOURCE)
        self.assertEqual(board.fix_duty(self.place, {KEY_A, KEY_B}), ({KEY_A, KEY_B}, {}))
        c.apply_rulings(self.place, {"c1-1": {"decision": c.REPLAN, "text": "案の項目 1 の受け入れのテストが誤り",
                                              "limits": [], "plan_items": [1], "plan_units": [KEY_A]},
                                     "c1-2": {"decision": "fix_code_as", "text": "コードを hi を返す形に直せ",
                                              "limits": ["stats.py"]}}, by="t")
        rows = {r["id"]: r for r in c.items(self.place)}
        self.assertEqual(rows["c1-1"][c.REPLAN_STATE], c.WAITING)
        self.assertEqual(rows["c1-1"]["ruling"]["decision"], c.REPLAN)
        self.assertNotIn(c.REPLAN_STATE, rows["c1-2"])
        self.assertEqual([r["id"] for r in c.waiting(self.place)], ["c1-1"])
        self.assertEqual([r["id"] for r in c.ruled_fix(self.place)], ["c1-2"])
        self.assertEqual(c.asked(self.place), [])
        owed, excused = board.fix_duty(self.place, {KEY_A, KEY_B})
        self.assertEqual(owed, {KEY_B})
        self.assertIn("fix_plan_item の裁定 c1-1", excused[KEY_A])
        self.assertEqual(board.nothing_owed_but_excused(self.place, {KEY_A}), {KEY_A: excused[KEY_A]})
        self.assertEqual(board.nothing_owed_but_excused(self.place, {KEY_A, KEY_B}), {})
        self.assertEqual([r["op"] for r in _trace_rows(self.place)], [c.PARK_OP, c.PARK_OP, c.RULE_OP, c.RULE_OP])

    def test_replan_readers_take_the_items_from_the_stored_ruling(self):
        """apply_rulings が積んだ fix_plan_item の行から、board.replan_items と conflict.replan_rows が同じ案の項目を読む
        （項目の番号は裁定の欄の中。組の項目に落ちない）"""
        c = conflict
        c.park(self.place, [CLAIM], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": c.REPLAN, "text": "案の項目 1 の受け入れのテストが誤り",
                                              "limits": [], "plan_items": [1], "plan_units": [KEY_A, KEY_B]}}, by="t")
        rows = c.items(self.place)
        self.assertEqual(board.replan_items(rows, [{"unit_ids": [KEY_A, KEY_B], "items": [1, 2]}]), ["1"])
        self.assertEqual(board.replan_items(rows), ["1"])
        self.assertEqual([r["id"] for r in c.replan_rows(rows, 1, [])], ["c1-1"])
        self.assertEqual(c.replan_rows(rows, 2, [KEY_B]), [])

    def test_ask_human_is_asked_and_amended_returns_to_duty(self):
        c = conflict
        c.park(self.place, [CLAIM, {**CLAIM, "unit_key": KEY_B}], source=c.FIX_SOURCE)
        c.apply_rulings(self.place, {"c1-1": {"decision": c.ASK, "text": "方針の変更で人が決める", "limits": []},
                                     "c1-2": {"decision": c.REPLAN, "text": "案の項目 2 の範囲が誤り", "limits": []}},
                        by="t")
        self.assertEqual([r["id"] for r in c.asked(self.place)], ["c1-1"])
        c.set_replan(self.place, ["c1-2"], c.AMENDED)
        self.assertEqual(c.amended_keys(self.place), {KEY_B})
        self.assertEqual(board.fix_duty(self.place, {KEY_A, KEY_B})[0], {KEY_B})
        self.assertEqual(_trace_rows(self.place)[-1], {"op": c.REPLAN_OP, "id": "c1-2", "unit_key": KEY_B,
                                                       "state": c.AMENDED, "why": ""})
        with self.assertRaises(ValueError):
            c.set_replan(self.place, ["c1-1"], c.AMENDED)

    def test_withheld_and_returned_are_arguments(self):
        owed, excused = board.fix_duty(self.place, {KEY_A, KEY_B},
                                       withheld_by={KEY_B: {"key": "q1", "kind": "fork", "status": "held"}})
        self.assertEqual(owed, {KEY_A})
        self.assertIn("答え待ちの問い q1", excused[KEY_B])
        owed, _ = board.fix_duty(self.place, {KEY_A}, withheld_by={}, returned={KEY_B})
        self.assertEqual(owed, {KEY_A, KEY_B})

    def test_broken_store_is_value_error(self):
        c = conflict
        for text in ("{", "[]", '{"items": {}}'):
            with self.subTest(text=text):
                (self.place / "conflicts.json").write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    c.items(self.place)
        with self.assertRaises(ValueError):
            c.park(self.place, [CLAIM], source="other")

    def test_plan_asks_read_the_places_trace(self):
        c = conflict
        board.trace(self.place, c.ASKED_OP, id="a1", item=1, status="answered", decision="allow", granted_paths=["docs/x.md"])
        board.trace(self.place, c.ASKED_OP, id="a2", item=1, status="answered", decision="deny")
        self.assertEqual([r["id"] for r in c.plan_asks(self.place)], ["a1", "a2"])
        self.assertEqual([r["id"] for r in c.agreed(self.place)], ["a1"])

    def test_permits_read_the_frozen_fields_in_the_place(self):
        import planmarks
        c = conflict
        fields = [{"unit_keys": [KEY_A], "rewrite_tests": [{"id": "test_stats.py::test_clamp", "new": "hi を期待する",
                                                            "limit": "test_stats.py:1"}]}]
        planmarks.save(self.place, 1, fields)
        got = c.test_permits(self.place)
        self.assertEqual([(p["id"], p["limit"]) for p in got], [(f"{c.PLAN_TEST_ID}-1", "test_stats.py:1")])
        self.assertEqual(c.test_permits(self.place, round_=2), [], "周の違う控えは読まない")
        self.assertEqual(c.frozen_fields(self.place), fields)
        (self.place / planmarks.FIELDS_FILE).write_text("{}", encoding="utf-8")   # 受け付けの後に書き換えた
        stopped = []
        with self.assertRaises(ValueError) as cm:
            c.test_permits(self.place)
        self.assertIn(c.FIELDS_TAMPERED, str(cm.exception))
        err = c.fields_broken(self.place, planmarks.FieldsBroken("x"), stop=lambda why, by: stopped.append(by))
        self.assertIsInstance(err, ValueError)
        self.assertEqual(stopped, [c.stopby.FIX])


class RulingSeamCase(unittest.TestCase):
    """ruling の継ぎ目: prep・accept_rule は place の conflicts.json・rule-tree.json・rejects-rule.json で回る。作業ツリーの控えは
    board.snapshot、prep は指示の値 {values, iteration} を返し（文は md）、配線の誤りは ValueError"""

    VALUES = {"judgment_file": "/home/x/j.json", "policy_path": ""}
    ASK_WHY = {"ask_why": {"changes": "direction", "line": "上限を超えた値を hi と lo のどちらに倒すかで直しの向きが変わる"}}

    def setUp(self):
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        self.rev = committed_copy(self.run.repo, SEED)
        self.repo, self.place = self.run.repo, self.run.artifacts
        conflict.park(self.place, [CLAIM], source=conflict.FIX_SOURCE)

    def reply(self, **extra):
        return {"rulings": [{"id": "c1-1", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": [],
                             **self.ASK_WHY, **extra}]}

    def test_prep_returns_the_values_and_writes_the_tree_in_the_place(self):
        """prep は指示の値（裁く id・申し出の控え・依頼のファイル）と周を返し、作業ツリーの姿を place に控える。拒否の回の後は周が
        2 になり、指示の値（prompts.ruler_values）が前の拒否の文を持つ（1 回目は持たない）"""
        r = ruling
        got = r.prep(self.place, self.repo, self.VALUES)
        self.assertEqual(got, {"values": {**self.VALUES, "conflicts_file": str(self.place / conflict.FILE), "ids": "c1-1",
                                          "request_file": ""}, "iteration": 1})
        self.assertTrue((self.place / r.TREE).is_file(), "作業ツリーの姿の控えは place")
        with self.run.env():
            values, when = prompts.ruler_values(self.place, got)
        self.assertEqual((values["rejection"], when["rejected"]), ("", False), "1 回目は拒否の理由を持たない")
        bad = {"rulings": [{"id": "c9-9", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": []}]}
        refused = r.accept_rule(bad, self.place, self.rev, self.repo)   # 回の数えは拒否の控え（rolekit）
        self.assertFalse(refused["ok"])
        again = r.prep(self.place, self.repo, self.VALUES)
        self.assertEqual(again["iteration"], 2)
        with self.run.env():
            values, when = prompts.ruler_values(self.place, again)
        self.assertTrue(when["rejected"])
        self.assertIn(refused["reason"], values["rejection"], "2 回目は前の拒否の文を渡す")

    def test_accept_rule_applies_rulings_to_the_place(self):
        r = ruling
        r.prep(self.place, self.repo, self.VALUES)
        got = r.accept_rule(self.reply(), self.place, self.rev, self.repo)
        self.assertEqual((got["ok"], got["done"], got["reason"]), (True, True, ""), got)
        self.assertEqual(got["rulings_file"], str(self.place / conflict.RULINGS_FILE))
        self.assertEqual(conflict.unruled(self.place), [])
        row, = conflict.items(self.place)
        self.assertEqual(row["ruling"]["decision"], conflict.ASK)
        self.assertIn(conflict.RULE_OP, [x["op"] for x in _trace_rows(self.place)])

    def test_accept_rule_rejects_then_gives_up_to_the_human(self):
        r = ruling
        r.prep(self.place, self.repo, self.VALUES)
        bad = {"rulings": [{"id": "c9-9", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": []}]}
        for _ in range(rolekit.GIVE_UP_AFTER - 1):
            got = r.accept_rule(bad, self.place, self.rev, self.repo)
            self.assertEqual((got["ok"], got["done"]), (False, False))
            self.assertIn("c9-9", got["reason"])
        self.assertEqual(len(conflict.unruled(self.place)), 1, "拒んだ回は積まない")
        (self.repo / "stats.py").write_text("# 変えた\n", encoding="utf-8")
        got = r.accept_rule(self.reply(), self.place, self.rev, self.repo)
        self.assertTrue(got["reason"].startswith(r.READONLY), got)
        self.assertEqual((got["ok"], got["done"]), (False, True))
        row, = conflict.items(self.place)
        self.assertEqual((row["ruling"]["decision"], row["ruling"]["text"]), (conflict.ASK, r.GIVE_UP_TEXT))

    def test_unusable_ledger_does_not_hand_the_give_up_ruling(self):
        """裁定の控え rejects-rule.json が読めない時、accept_rule は例外を上げず done 真の拒否を返し、裁かれていない申し出に
        GIVE_UP_TEXT（役が 3 回通らなかった）の ask_human を積まない"""
        r = ruling
        r.prep(self.place, self.repo, self.VALUES)
        (self.place / "rejects-rule.json").mkdir()
        bad = {"rulings": [{"id": "c9-9", "decision": "ask_human", "text": "方針の変更で人が決める", "limits": []}]}
        try:
            got = r.accept_rule(bad, self.place, self.rev, self.repo)
        except rolekit.BoardGap as e:
            self.fail(f"控えの誤りで落ちた: {e}")
        self.assertEqual((got["ok"], got["done"]), (False, True))
        self.assertIn("拒否の控えが扱えない", got["reason"])
        self.assertEqual(len(conflict.unruled(self.place)), 1, "裁かれていない申し出を人に回さない")
        row, = conflict.items(self.place)
        self.assertIsNone(row["ruling"])

    def test_wiring_errors_are_value_errors(self):
        r = ruling
        with self.assertRaises(ValueError):
            r.accept_rule(self.reply(), self.place, self.rev, self.repo)   # rule-prep が走っていない
        conflict.apply_rulings(self.place, {"c1-1": {"decision": "ask_human", "text": "方針の変更で人が決める",
                                                     "limits": []}}, by="t")
        with self.assertRaises(ValueError):
            r.prep(self.place, self.repo, self.VALUES)   # 裁く申し出が無い

    def _rule_errs(self, row, item, briefs=None):
        """裁定 1 行 row を、申し出 item（id c1-1）への返答として ruling.problems に当てた文（grounds は place の中も名指せる。
        accept_rule と同じ roots）"""
        return ruling.problems({"rulings": [{"id": "c1-1", **row}]}, {"c1-1": {"id": "c1-1", **item}}, self.repo, "",
                               (str(self.place),), briefs=briefs)

    def test_ask_human_states_what_the_answer_changes(self):
        """#664: ask_human は人の答えで変わる物（直しの向きか範囲）と 1 行の訳を持つ。訳の無い ask_human と、訳を ask_human
        でない裁定に書いた物は拒む。直しの向きが変わる申し出は今どおり人に回る（keep-essence の人に回す能力）"""
        ask = self.reply()["rulings"][0]
        self.assertEqual(self._rule_errs(ask, CLAIM), [])
        self.assertTrue(any("ask_why" in e for e in self._rule_errs({k: v for k, v in ask.items() if k != "ask_why"}, CLAIM)))
        code_as = {"decision": "fix_code_as", "text": "コードの返り値を hi に直せ", "limits": [], **self.ASK_WHY}
        self.assertTrue(any("ask_why は ask_human の裁定だけ" in e for e in self._rule_errs(code_as, CLAIM)))
        ruling.prep(self.place, self.repo, self.VALUES)
        got = ruling.accept_rule(self.reply(), self.place, self.rev, self.repo)
        self.assertTrue(got["ok"], got)
        line, = conflict.human_lines(self.place)
        self.assertIn(f"人に回す訳（直しの向き） {self.ASK_WHY['ask_why']['line']}", line)

    def test_name_overlap_is_ruled_without_the_human(self):
        """#664: 訳が名の重なりだけ（name_only）の ask_human は拒み、人に回さない。別の物と裁く fix_code_as（もう一方の在り処を
        limits に）と、衝突を避けた改名で項目の path を変える fix_plan_item は通る"""
        name_only = {"decision": "ask_human", "text": "同じ名の定義が 2 つのファイルに在るので人に決めてもらう", "limits": [],
                     "ask_why": {"changes": "name_only", "line": "足す名と同じ字の定義が別のファイルに在る"}}
        self.assertEqual(self._rule_errs(name_only, CLAIM), [f"申し出 c1-1: {ruling.NAME_ONLY_REJECT}"])
        brief = self.place / "brief-1.md"
        brief.write_text("# brief 1\n新しいテストのファイル tests/test_notice.py を作る\n", encoding="utf-8")
        rename = {"decision": conflict.REPLAN, "text": "テストのファイルの名がほかの物と衝突するので、項目の path を改名した名に直す",
                  "limits": [], "grounds": [f"{brief}:2"]}
        self.assertEqual(self._rule_errs(rename, CLAIM, {KEY_A: [{"item": 1, "file": str(brief)}]}), [])
        ruling.prep(self.place, self.repo, self.VALUES)
        got = ruling.accept_rule({"rulings": [{"id": "c1-1", **name_only}]}, self.place, self.rev, self.repo)
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn(ruling.NAME_ONLY_REJECT, got["reason"])
        self.assertEqual(conflict.asked(self.place), [], "名の重なりだけでは人に回さない")
        other = {"decision": "fix_code_as", "text": "test_stats.py の同名は別の物。そのまま残して直しを続けよ",
                 "limits": ["test_stats.py"]}
        got = ruling.accept_rule({"rulings": [{"id": "c1-1", **other}]}, self.place, self.rev, self.repo)
        self.assertTrue(got["ok"], got)
        self.assertEqual((conflict.asked(self.place), conflict.ruled_paths(self.place)), ([], ["test_stats.py"]))

    def test_replace_query_is_tried_on_hits_misses_and_correct_lines(self):
        """F212: 裁定 replace_query の新しい問いは、hits に全部当たり、misses にも申し出の correct_lines にも当たらない時だけ通る
        （Semgrep の規則の試験の形）。which_is_right が query でない申し出には裁けない"""
        item = {**CLAIM, "which_is_right": "query", "kind": "query_hits_fixed", "correct_lines": ["        return lo"]}

        def row(patterns, hits, misses):
            how = {"patterns": patterns, "fixed": True, "paths": ["stats.py"], "count": "lines"}
            return {"decision": "replace_query", "limits": [], "text": "上限の枝だけに当たる問いに置き換える",
                    "query": {"how": how, "counts": "defects", "hits": hits, "misses": misses}}
        good = row(["return lo  # hi"], ["        return lo  # hi"], ["        return hi"])
        self.assertEqual(self._rule_errs(good, item), [], "全部を満たす問いは通す")
        cases = ((row(["return lo  # hi"], ["        return hi"], []), "hits に当たらない"),
                 (row(["return lo  # hi"], ["        return lo  # hi"], ["        return lo  # hi"]), "misses に当たる"),
                 (row(["return lo"], ["        return lo  # hi"], ["        return hi"]), "correct_lines"))
        for bad, word in cases:
            with self.subTest(word=word):
                errs = self._rule_errs(bad, item)
                self.assertTrue(any(word in e for e in errs), errs)
        errs = self._rule_errs(good, {**CLAIM, "which_is_right": "request"})
        self.assertTrue(any("which_is_right が query の申し出だけ" in e for e in errs), errs)

    def test_fix_plan_item_needs_brief_grounds_and_no_limits(self):
        """F213: 裁定 fix_plan_item は範囲 limits を持たず、grounds にその単位の brief の行を名指す時だけ通り、受けた裁定には機械が
        plan_items（brief の項目の番号）と plan_units（その項目に載る単位の全部）を足す。機械が諦めた単位の申し出
        （source tdd-gave-up）への fix_code_as は grounds を要る"""
        c = conflict
        brief = self.place / "brief-1.md"
        brief.write_text("# brief 1\n受け入れのテストは assertion で赤\n", encoding="utf-8")
        briefs = {KEY_A: [{"item": 1, "file": str(brief)}], KEY_B: [{"item": 1, "file": str(brief)}]}
        row = {"decision": c.REPLAN, "text": "受け入れのテストの赤の種類を exception に直す", "limits": [],
               "grounds": [f"{brief}:2"]}
        self.assertEqual(self._rule_errs(row, CLAIM, briefs), [])
        self.assertTrue(any("brief が無い" in e for e in self._rule_errs(row, CLAIM, {})))
        self.assertTrue(any("範囲を持たない" in e for e in self._rule_errs({**row, "limits": ["test_stats.py:2"]}, CLAIM, briefs)))
        for grounds in ([], ["stats.py:3"]):
            errs = self._rule_errs({**row, "grounds": grounds}, CLAIM, briefs)
            self.assertTrue(any(c.REPLAN in e and "grounds" in e and str(brief) in e for e in errs), (grounds, errs))
        code_as = {"decision": "fix_code_as", "text": "コードの返り値を hi に直せ", "limits": []}
        gave_up = {**CLAIM, "source": c.GAVE_UP_SOURCE, "which_is_right": "unknown", "kind": "needs_context"}
        self.assertTrue(any("grounds" in e and "fix_code_as" in e for e in self._rule_errs(code_as, gave_up)))
        self.assertEqual(self._rule_errs({**code_as, "grounds": ["stats.py:3", "test_stats.py:2"]}, gave_up), [])
        self.assertEqual(self._rule_errs(code_as, {**gave_up, "source": c.TDD_SOURCE}), [], "役の申し出は grounds なしで通る")
        ruling.prep(self.place, self.repo, self.VALUES)
        with mock.patch.object(ruling.planbrief, "by_unit_at", return_value=briefs):
            got = ruling.accept_rule({"rulings": [{"id": "c1-1", **row}]}, self.place, self.rev, self.repo)
        self.assertTrue(got["ok"], got)
        stored, = c.items(self.place)
        self.assertEqual((stored["ruling"][c.PLAN_ITEMS], stored["ruling"][c.PLAN_UNITS]), ([1], [KEY_A, KEY_B]))
        self.assertEqual(set(c.held_by_rulings(self.place)), {KEY_A, KEY_B}, "項目の単位の全部を直す義務から外す")


class FixAcceptConflictCase(unittest.TestCase):
    """修正役の受け付け（board.accept_reply）の申し出の照らし（take_conflicts）: 直す義務の外の単位の申し出と、申し出た単位を
    changes にも書いた返答を拒む（lib の test_conflict_kinds.py の FixAcceptSeamCase から。place は 1 つのフォルダ）"""

    def setUp(self):
        root = hermetic.tmpdir(self)
        self.repo, self.place = root / "repo", root / "place"
        self.rev = committed_copy(self.repo, SEED)
        self.place.mkdir()
        (self.place / "judgment.json").write_text(json.dumps({"units": [{"key": MEAN}, {"key": KEY_A}]}), encoding="utf-8")

    def accept(self, conflicts, changes=()):
        import leftovers
        reply = {"changes": [{"unit_key": k, "what": "直した", "files": ["stats.py"]} for k in changes], "conflicts": conflicts}
        return board.accept_reply(reply, self.place, self.repo, pass_="first", iteration=1, owed=[MEAN, KEY_A], judged=[],
                                  head=leftovers.snapshot(self.repo), base_rev=self.rev)

    def rejects(self, got) -> str:
        return " ".join(r["text"] for r in got["rejects"] if r["check"] == "conflict")

    def test_conflict_unit_also_in_changes_is_rejected(self):
        got = self.accept([MEAN_CLAIM], changes=[MEAN, KEY_A])
        self.assertEqual((got["ok"], got["conflicted"]), (False, False), got)
        self.assertIn(f"申し出た単位を changes にも書いた: {MEAN}", self.rejects(got))
        self.assertEqual(conflict.items(self.place), [], "拒んだ申し出は積まない")
        got = self.accept([{**MEAN_CLAIM, "unit_key": "stats.py ghost: 作り話の単位"}])
        self.assertFalse(got["ok"], got)
        self.assertIn("今の直す義務の単位に無い", self.rejects(got))
        self.assertEqual(conflict.items(self.place), [])
        got = self.accept([MEAN_CLAIM])
        self.assertEqual((got["ok"], got["conflicted"]), (True, True), got)


class RuleScriptsCase(unittest.TestCase):
    """裁定の輪の scripts（rule_prep・rule_accept）を子のプロセスで回す。place は intake と prep が書く（全体の形）"""

    def setUp(self):
        self.run = kit.Run(self, "fix")
        shutil.rmtree(self.run.repo)
        committed_copy(self.run.repo, SEED)
        self.repo, self.place = self.run.repo, self.run.artifacts

    def start(self, **inputs):
        got = self.run.script("intake", mode="whole", judgment=json.dumps(JUDGMENT, ensure_ascii=False), **inputs)
        self.assertEqual((got["ok"], got["whole"]), (True, True), got)
        self.run.script("prep")
        conflict.park(self.place, [MEAN_CLAIM], source=conflict.FIX_SOURCE)

    def test_rule_prep_renders_the_ruler_prompt(self):
        """rule_prep は prompts/ruler.md を組んだ指示（裁く id・申し出の控え・判定の写し）と周を返し、place に指示の控えを書く"""
        self.start()
        out = self.run.script("rule_prep")
        self.assertEqual(set(out), {"prompt", "iteration"})
        self.assertEqual(out["iteration"], 1)
        for word in ("c1-1", str(self.place / conflict.FILE), str(self.place / board.JUDGMENT_FILE),
                     "There is no policy document.", "There is no request file."):
            self.assertIn(word, out["prompt"])
        self.assertNotIn("Why your previous answer was rejected", out["prompt"], "1 回目は拒否の段落を持たない")
        self.assertEqual((self.place / "ruler-prompt-1.md").read_text(encoding="utf-8"), out["prompt"])
        self.assertTrue((self.place / ruling.TREE).is_file())

    def test_rule_accept_reason_file_is_the_rule_ledger(self):
        """rule_accept の拒否の reason_file は rolekit の rejects-rule.md（ruling.ROLE の控えの全部）。rejects-rule.json の拒否と
        同じ文を持ち、reject-rule-accept-<k>.md は作らない。次の rule_prep は同じ拒否の文を指示に入れる"""
        self.start()
        self.run.script("rule_prep")
        out = self.run.script("rule_accept", reply=json.dumps({"rulings": []}), iteration="1")
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        self.assertEqual(out["reason_file"], str(rolekit.rejects_text_path(self.place, ruling.ROLE)))
        rows = json.loads((self.place / "rejects-rule.json").read_text(encoding="utf-8"))
        self.assertEqual([r["reason"] for r in rows], [out["reason"]])
        self.assertIn(out["reason"], pathlib.Path(out["reason_file"]).read_text(encoding="utf-8"))
        self.assertEqual(list(self.place.glob("reject-rule-accept-*.md")), [])
        nxt = self.run.script("rule_prep")
        self.assertIn(out["reason"].strip().split("\n")[0], nxt["prompt"])

    def test_rule_prompt_names_the_policy_and_request_ports(self):
        """裁定役の指示が名指す方針の文書・依頼のファイルは、port policy・request で渡したファイル（line が固めた写し。今の
        始めの記録の固めた版の写しの代わり）"""
        policy = self.run.artifacts.parent / "frozen-policy.md"
        policy.write_text("- 固めた版\n", encoding="utf-8")
        request = self.run.artifacts.parent / "request.json"
        request.write_text(json.dumps([{"where": "stats.py", "text": "平均を直して"}], ensure_ascii=False), encoding="utf-8")
        self.start(policy=str(policy), request=str(request))
        out = self.run.script("rule_prep")
        self.assertIn(f"The policy document: {policy}", out["prompt"])
        self.assertIn(f"The request file: {request}", out["prompt"])
        self.assertNotIn("There is no policy document.", out["prompt"])

    def test_rule_loop_writes_the_reject_and_names_it_next(self):
        self.start()
        out = self.run.script("rule_prep")
        self.assertEqual(out["iteration"], 1)
        out = self.run.script("rule_accept", reply=json.dumps({"rulings": []}), iteration="1")
        self.assertEqual((out["ok"], out["done"]), (False, False), out)
        reason = out["reason"]
        out = self.run.script("rule_prep")
        self.assertEqual(out["iteration"], 2)
        self.assertIn("Why your previous answer was rejected", out["prompt"])
        self.assertIn(reason.strip().split("\n")[0], out["prompt"])

    def test_rule_accept_with_an_unusable_ledger_does_not_fail(self):
        """拒否の控えの名のディレクトリ（読めない控え）でも、rule_accept は非 0 で落ちず、done 真の拒否（理由『拒否の控えが
        扱えない』・reason_file は空）を返す"""
        self.start()
        self.run.script("rule_prep")
        (self.place / "rejects-rule.json").unlink(missing_ok=True)
        (self.place / "rejects-rule.json").mkdir()
        out = self.run.script("rule_accept", reply=json.dumps({"rulings": []}), iteration="1")
        self.assertEqual((out["ok"], out["done"], out["reason_file"]), (False, True, ""), out)
        self.assertIn("拒否の控えが扱えない", out["reason"])

    def test_rule_accept_takes_a_ruling(self):
        """通る裁定は申し出の控えに積まれ、done 真で抜ける"""
        self.start()
        self.run.script("rule_prep")
        reply = {"rulings": [{"id": "c1-1", "decision": "fix_test_scope", "text": "テストの期待が誤った平均を前提にしている",
                              "limits": ["test_stats.py"]}]}
        out = self.run.script("rule_accept", reply=json.dumps(reply, ensure_ascii=False), iteration="1")
        self.assertEqual(out, {"ok": True, "done": True, "reason": "", "reason_file": ""})
        self.assertEqual(conflict.unruled(self.place), [])
        self.assertEqual(conflict.ruled_paths(self.place), ["test_stats.py"])


if __name__ == "__main__":
    unittest.main()
