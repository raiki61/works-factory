"""独立の目から修正の段へ返す輪の、周の頭の決めと周の記録の行の形と最後の周の状態の選び（src/eyesback.py。docs/design/line.md の 1.3・5.4）。

周の頭の script は薄い口で、決めは turn に在る。ここは turn・last・current・lines を値で回し、返す条件・抜ける訳の順・案の選び・上限・記録の形を
確かめる（周の節の並びは test_wiring.py、筋書きは test_scenarios.py）。turn の引数 snap（返す時だけ呼んで新しい周の行 tree に置く木の控え）は
数える関数で渡し、script が渡す tree_now は本物の git の写しで照らす。返した段が止まった・落ちた周の頭が、前の周の試験と目を通った状態を
checkpoint 付きで持ち越すことと、script の既定の記録が RECORD・FIELDS の欄を全部持つことも、ここで値のまま確かめる。
RestoreCase は、写しの repo（本物の git）で封じる前の戻しの門 restore_before_seal と節 eyes-back-restore の script を回し、作業ツリーが
返す前の木へ戻ることと、返した段の書き換えが置き場の控えに残ることと、戻せない訳の語を確かめる。
"""
import ast
import contextlib
import inspect
import io
import json
import os
import re
import runpy
import tempfile
import unittest
from unittest import mock

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git
from tests.blocks import kit

BLOCK = "line"
FIXED_PLAN = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "fix/plan-fields.json"}
FIRST_RIPPLE = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "fix-in/ripple.json"}
REMADE_RIPPLE = {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "replan/ripple.json"}
PLAN_FIELDS = [{"allowed_paths": ["src/a.py"], "tests": [], "rewrite_tests": []}, {"allowed_paths": ["docs/*.md"], "tests": [], "rewrite_tests": []}]
ITEMS = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}, {"eye": "r2", "where": "", "text": "入口が足りない"}]


def fixed(**over) -> dict:
    """合わせ（stages.fixed）の出力のうち周の頭が読む欄"""
    got = {"go": True, "stop_reason": "", "objection": "", "refixed": False, "plan": FIXED_PLAN, "ripple": FIRST_RIPPLE, "more": [],
           "stages": [{"stage": 1, "kind": "first", "fix": {"carry": {"loops": []}}, "lens": None, "delta": None}], "item_claims": {"items": [], "claims": []}}
    return {**got, **over}


def gate_got(diff_hash="h1", **over) -> dict:
    return {"ok": True, "green": True, "fingerprint": {"head": "abc", "diff_hash": diff_hash}, **over}


def eyes(route="fix", items=ITEMS, **over) -> dict:
    return {"ok": route != "fix", "r1": {"status": "fix-needed", "reason": "写し"}, "r2": {"status": "pass", "reason": ""},
            "findings": items, "route": route, "route_why": "" if route == "fix" else "返す物が無い（どの目も通った）", **over}


SEALED = ("diff", "diffed", "changed", "units", "groups", "item_claims")
SEED = kit.ROOT / "tests" / "e2e" / "target-seed"


class Snaps:
    def __init__(self, tree="t1"):
        self.tree, self.calls = tree, 0

    def __call__(self) -> str:
        self.calls += 1
        return self.tree


def before_fixed() -> dict:
    return fixed(diff="diff-before", diffed=True, changed=["a.py"], units=[{"key": "u1"}], groups=[{"group": 1}],
                 item_claims={"items": [1], "claims": ["claim-before"]})


def back_fixed(**over) -> dict:
    """返した段の合わせ。封じる差分を語る欄は返す前と違う値、異議・段の並び・more は返した段の物"""
    stages = [*fixed()["stages"], {"stage": 2, "kind": "back", "fix": {"carry": {"loops": ["back"]}}, "lens": None, "delta": None}]
    return fixed(diff="diff-after", diffed=False, changed=["a.py", "b.py"], units=[{"key": "u1"}, {"key": "u2"}], groups=[],
                 item_claims={"items": [], "claims": []}, stages=stages, more=[{"ok": False, "stage": "back"}], **over)


def script_const(name: str, const: str) -> str:
    """script の標準ライブラリだけで書いた字（fallback が使う）"""
    text = (kit.BLOCKS / BLOCK / "scripts" / f"{name}.py").read_text(encoding="utf-8")
    return re.search(rf'^{const} = "([^"]+)"', text, re.M).group(1)


class _Case(unittest.TestCase):
    def setUp(self):
        self.assertTrue((kit.BLOCKS / BLOCK / "src" / "eyesback.py").exists(), "周の頭の決めの src/eyesback.py が無い")
        self.e = kit.load(BLOCK, "eyesback")

    def run_turn(self, **over) -> dict:
        args = {"k": 1, "prev": None, "fixed": fixed(), "judged": {"stop_reason": ""}, "fix_in": FIX_IN, "tests": gate_got(),
                "eyes": eyes(), "replan": None, "answer_replan": None, "plan_fields": PLAN_FIELDS}
        return self.e.turn(**{**args, **over})


FIX_IN = {"fix_plan": {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "fix-in/fix-plan.json"}, "review": {"verdict": "ok"},
          "answer": {"decision": "approve", "text": "", "asked": []}, "skip_rerun": ["u9"]}
REPLAN = {"fix_plan": {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "replan/fix-plan.json"}}
ANSWER_REPLAN = {"plan_review": {"verdict": "replan"}, "fix_answers": {"decision": "approve", "text": "案の直し", "asked": []},
                 "fix_ripple": FIRST_RIPPLE, "skip_rerun": ["u1"]}


class TurnCase(_Case):
    def test_fix_route_returns_with_the_named_items(self):
        """目の route が fix で findings を持ち、前の段に止めの語が無い時、go を真にし、findings の where を修正案の項目に結んだ番号を
        only_items に、指摘の文を notes に、前の段の carry を prior に入れる。返した周を 1 行記録に足す"""
        got = self.run_turn()
        self.assertTrue(got["go"])
        self.assertEqual(got["exit"], "")
        self.assertEqual(got["only_items"], [1], "src/a.py:12 は項目 1 の範囲。where の無い指摘は結べない")
        self.assertEqual(got["notes"].splitlines(), ["独立の目 R1: src/a.py:12: 写しが残っている", "独立の目 R2: 入口が足りない"])
        self.assertEqual(got["prior"], {"loops": []})
        self.assertEqual(got["rows"], [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": ITEMS}])
        self.assertEqual(set(got), set(self.e.FIELDS))
        self.assertEqual(json.loads(json.dumps(got)), got, "JSON に書ける")
        got = self.run_turn(eyes=eyes(items=[{"eye": "r2", "where": "", "text": "入口が足りない"}]))
        self.assertEqual(got["only_items"], [])
        self.assertIn(self.e.UNTIED, got["notes"].splitlines())
        both = self.run_turn(eyes=eyes(items=[*ITEMS, {"eye": "r1", "where": "docs/a.md", "text": "文書"}]))
        self.assertEqual(both["only_items"], [1, 2])
        self.assertNotIn(self.e.UNTIED, both["notes"])
        self.assertEqual(self.run_turn(plan_fields=None)["only_items"], [])
        got = self.run_turn()
        self.assertEqual((got["fixed"], got["tests"], got["eyes"]), (fixed(), gate_got(), eyes()))
        self.assertEqual((got["fingerprint"], got["green_ok"], got["eyes_ok"], got["sealable"], got["item_claims"]),
                         ({"head": "abc", "diff_hash": "h1"}, True, False, True, {"items": [], "claims": []}))

    def test_returned_items_carry_their_kinds_by_item_number(self):
        """返す項目の種を修正案の項目の番号ごとに item_kinds へ運ぶ。R1 と R2 が同じ項目に結ばれれば 2 行・結べず全部を対象にした時は
        全部の項目に返した種を並べ・種の無い指摘は行を作らない。結べなかった指摘に作り残し（unfinished）が在れば、notes で渡る
        その指摘を赤なしで直させないよう、結べた項目を全部 unfinished にする（整えの指摘だけが結ばれた項目も。持ち主の決め
        no-silent-loosen）。結べなかった指摘が整えだけなら結べた項目の種のまま。返さない抜け方と script の落ちた時の形では空の配列になる"""
        r1 = {"eye": "r1", "kind": "trim", "where": "src/a.py:12", "text": "写しが残っている"}
        r2 = {"eye": "r2", "kind": "unfinished", "where": "", "text": "入口が足りない"}
        r2_tied = {**r2, "where": "src/a.py:30"}
        got = self.run_turn(eyes=eyes(items=[r1, r2]))
        self.assertEqual(got.get("item_kinds"), [{"item": 1, "kind": "unfinished"}],
                         "結べたのは R1 の整えだけでも、結べなかった R2 の作り残しが在るので項目 1 は赤を求める側に倒す")
        r2_trim = {**r2, "kind": "trim"}
        self.assertEqual(self.run_turn(eyes=eyes(items=[r1, r2_trim])).get("item_kinds"), [{"item": 1, "kind": "trim"}],
                         "結べなかった指摘が整えだけなら結べた項目の種のまま")
        both = self.run_turn(eyes=eyes(items=[r1, r2_tied]))
        self.assertCountEqual(both.get("item_kinds") or [], [{"item": 1, "kind": "trim"}, {"item": 1, "kind": "unfinished"}])
        untied = self.run_turn(eyes=eyes(items=[r2]))
        self.assertCountEqual(untied.get("item_kinds") or [], [{"item": 1, "kind": "unfinished"}, {"item": 2, "kind": "unfinished"}],
                              "結べず全部を対象にした時は全部の項目に返した種を並べる")
        plain = {k: v for k, v in r1.items() if k != "kind"}
        self.assertEqual(self.run_turn(eyes=eyes(items=[plain])).get("item_kinds"), [], "種の無い指摘は行を作らない")
        self.assertEqual(self.run_turn(eyes=eyes("stay")).get("item_kinds"), [], "返さない抜け方では空")
        self.assertEqual(self.run_turn(fixed=None).get("item_kinds"), [])
        self.assertIn("item_kinds", self.e.FIELDS)
        text = (kit.BLOCKS / BLOCK / "scripts" / "eyes_back.py").read_text(encoding="utf-8")
        fallen = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == "fallen")
        built = next(n.value for n in ast.walk(fallen) if isinstance(n, ast.Return))
        keys = {k.value: ast.literal_eval(v) for k, v in zip(built.keys, built.values) if isinstance(k, ast.Constant) and isinstance(v, (ast.List, ast.Constant))}
        self.assertEqual(keys.get("item_kinds"), [], "落ちた時の形の item_kinds は空の配列")
        spec = yaml.safe_load((kit.BLOCKS / BLOCK / "works-factory-line.yaml").read_text(encoding="utf-8"))
        node = next(n for n in spec["nodes"] if n["id"] == "back-1")
        self.assertIn("item_kinds", node["output_format"]["required"])
        self.assertLessEqual(set(node["output_format"]["required"]), {k.value for k in built.keys})

    def test_no_prior_returns_without_kinds(self):
        """前の段の修正が申し送り carry を null で返した段（持ち越す物が無い段。static の単位だけの段など）の後に返す時は、種を渡さず
        item_kinds を空にして元の案の route で回す（修正の block の受け付けは prior の無い段への種を拒むので、渡すと輪の節が落ちて人に回る。
        種を落としても元の route のままで、赤の義務は緩まない）。返すこと・only_items・notes は変えない。どの返す出力も『種が在れば prior が在る』"""
        r1 = {"eye": "r1", "kind": "trim", "where": "src/a.py:12", "text": "写しが残っている"}
        bare = fixed(stages=[{"stage": 1, "kind": "first", "fix": {"carry": None}, "lens": None, "delta": None}])
        got = self.run_turn(fixed=bare, eyes=eyes(items=[r1]))
        self.assertEqual((got["go"], got["prior"], got["only_items"], got["item_kinds"]), (True, None, [1], []))
        self.assertEqual(got["notes"].splitlines(), ["独立の目 R1: src/a.py:12: 写しが残っている"])
        self.assertEqual(self.run_turn(fixed=fixed(stages=[]), eyes=eyes(items=[r1]))["item_kinds"], [])
        with_prior = self.run_turn(eyes=eyes(items=[r1]))
        self.assertEqual((with_prior["prior"], with_prior["item_kinds"]), ({"loops": []}, [{"item": 1, "kind": "trim"}]))
        for out in (got, with_prior):
            self.assertTrue(not out["item_kinds"] or out["prior"] is not None)

    def test_stay_route_stop_word_or_fallen_round_does_not_return(self):
        """目の route が stay・前の段の修正が止めの語か異議を返した・前の周の返りが欠けた時は go が偽で、抜けた訳が route_why か EXITS の語になる"""
        stay = self.run_turn(eyes=eyes("stay"))
        self.assertEqual((stay["go"], stay["exit"], stay["rows"]), (False, "返す物が無い（どの目も通った）", []))
        no_items = self.run_turn(eyes=eyes(items=[]))
        self.assertEqual((no_items["go"], no_items["exit"]), (False, self.e.NOTHING))
        for over, why in (({"fixed": fixed(stop_reason="works:unrestored")}, "works:unrestored"), ({"fixed": fixed(objection="設計に異議")}, "設計に異議"),
                          ({"judged": {"stop_reason": "works:rejudge"}}, "works:rejudge"), ({"fixed": fixed(go=False)}, "進めなかった")):
            with self.subTest(over=sorted(over)):
                got = self.run_turn(**over)
                self.assertFalse(got["go"])
                self.assertTrue(got["exit"].startswith(self.e.EXITS["stop"]) and why in got["exit"], got["exit"])
        self.assertEqual(self.run_turn(k=2, prev=None)["exit"], self.e.EXITS["fell"])
        self.assertEqual(self.run_turn(fixed=None)["exit"], self.e.EXITS["fell"])
        carried = self.run_turn(k=3, prev=self.run_turn(k=2, prev=self.run_turn(eyes=eyes("stay")), fixed=None, tests=None, eyes=None))
        self.assertEqual((carried["go"], carried["round"], carried["exit"], carried["rows"]), (False, 3, "返す物が無い（どの目も通った）", []))
        self.assertEqual((carried["fixed"], carried["tests"], carried["eyes"]), (fixed(), gate_got(), eyes("stay")), "前の周が返さなかった周は前の記録の状態をそのまま運ぶ")
        later = self.run_turn(k=2, prev=self.run_turn(), tests=None)
        self.assertEqual((later["go"], later["exit"], later["sealable"]), (False, self.e.EXITS["fell"], True),
                         "前の周の頭が返した後の欠けは、返す前に試験と目を通った状態を持ち越して封じる")
        orphan = self.run_turn(k=2, prev=None, tests=None)
        self.assertEqual((orphan["go"], orphan["exit"], orphan["sealable"]), (False, self.e.EXITS["fell"], False), "前の周の記録が読めなければ封じない")
        first = self.run_turn(eyes=None)
        self.assertEqual((first["go"], first["exit"], first["sealable"]), (False, self.e.NO_RETURN, False), "1 周目に目が返らなかっただけでは落ちたと言わない")
        self.assertFalse(self.e.fell({"exit": first["exit"]}))
        prev = self.run_turn()
        got = self.run_turn(k=2, prev=prev, fixed=fixed(go=False, stop_reason="works:unrestored"), tests=None, eyes=None)
        self.assertTrue(got["exit"].startswith(self.e.EXITS["stop"]), got["exit"])
        self.assertEqual(script_const("eyes_back", "EXIT_FELL"), self.e.EXITS["fell"], "script の fallback の字")
        self.assertEqual(script_const("eyes_back_end", "EXIT_FELL"), self.e.EXITS["fell"])

    def test_the_fix_stage_why_reaches_the_exit_line(self):
        """合わせが止めた訳 stop_why を持つ時、止めの語の有無によらず抜けた訳に載り、輪を抜けた訳の行（最後の承認ノードと報告が読む）に出る。
        差分が変わらなかった時は、その字を修正の段の訳で包んで残し、包んでも返す前と同じ状態だと言う。stop_why が無ければ今の字のまま"""
        why = "直しが入った木では落ちる試験を書けない"
        first = self.run_turn()
        stopped = self.run_turn(k=2, prev=first, fixed=fixed(go=False, stop_reason="works:no-suite", stop_why=why))
        self.assertEqual(stopped["exit"], f"{self.e.EXITS['stop']}（works:no-suite：{why}）")
        self.assertIn(f"輪を抜けた訳: {stopped['exit']}", self.e.lines(first["rows"], stopped["exit"]))
        wordless = self.run_turn(k=2, prev=first, fixed=fixed(go=False, stop_why=why))
        self.assertEqual(wordless["exit"], f"{self.e.EXITS['stop']}（修正の段の合わせが進めなかった：{why}）")
        undone = self.run_turn(k=2, prev=first, fixed=fixed(stop_why=why), tests=gate_got("h1"))
        self.assertEqual(undone["exit"], f"{self.e.EXITS['unchanged']}（修正の段が直さなかった訳: {why}）")
        self.assertIn(f"輪を抜けた訳: {undone['exit']}", self.e.lines(first["rows"], undone["exit"]))
        self.assertIn(self.e.SAME_AS_BEFORE, self.e.lines(first["rows"], undone["exit"]))
        bare = self.run_turn(k=2, prev=first, fixed=fixed(stop_reason="works:unrestored"))
        self.assertEqual(bare["exit"], f"{self.e.EXITS['stop']}（works:unrestored）")
        self.assertEqual(self.run_turn(k=2, prev=first, tests=gate_got("h1"))["exit"], self.e.EXITS["unchanged"])

    def test_unchanged_diff_or_past_the_limit_leaves_the_loop(self):
        """返しの修正の後の指紋の diff_hash がその前と同じなら『差分が変わらない』で、周の番号が LIMIT を越えれば上限の訳 CAP_WHY で抜け、
        残った作り残しを記録に運ぶ"""
        first = self.run_turn(tests=gate_got("h1"))
        same = self.run_turn(k=2, prev=first, tests=gate_got("h1"))
        self.assertEqual((same["go"], same["exit"]), (False, self.e.EXITS["unchanged"]))
        changed = self.run_turn(k=2, prev=first, tests=gate_got("h2"))
        self.assertTrue(changed["go"])
        self.assertEqual([r["round"] for r in changed["rows"]], [1, 2])
        capped = self.run_turn(k=4, prev=self.run_turn(k=3, prev=changed, tests=gate_got("h3")), tests=gate_got("h4"))
        self.assertEqual((capped["go"], capped["exit"], capped["left"]), (False, self.e.CAP_WHY, ITEMS))
        self.assertTrue(self.e.capped(capped))
        self.assertFalse(self.e.capped(same))
        within = self.run_turn(k=3, prev=changed, tests=gate_got("h3"))
        self.assertTrue(within["go"], "LIMIT 周目までは返す")

    def test_third_round_limit_is_a_normal_exit(self):
        """3 周目の後に route fix が残った時、go が偽になり、exit が上限の語で、残った findings が記録に在り、その exit は『輪の節が落ちた』と別
        （current が記録の側を取る）。上限の語に『安全の上限』『工場の不具合』の字を使わない"""
        self.assertEqual(self.e.LIMIT, 3)
        record = None
        for k in (1, 2, 3):
            record = self.run_turn(k=k, prev=record, tests=gate_got(f"h{k}"))
            self.assertTrue(record["go"], k)
        last = self.run_turn(k=4, prev=record, tests=gate_got("h4"))
        self.assertEqual((last["go"], last["exit"], len(last["rows"])), (False, self.e.CAP_WHY, 3))
        self.assertEqual(last["left"], ITEMS)
        self.assertNotEqual(last["exit"], self.e.EXITS["fell"])
        self.assertTrue(last["sealable"])
        for word in ("安全の上限", "工場の不具合"):
            self.assertNotIn(word, self.e.cap_text(last["left"]))
        self.assertIn("R1: src/a.py:12: 写しが残っている", self.e.cap_text(last["left"]))
        chosen = self.e.current(self.e.last([last]), "first-fixed", "first-tests", "first-eyes")
        self.assertEqual(chosen, (last["fixed"], last["tests"], last["eyes"]), "上限で抜けた記録は最後の周の状態を選ぶ")

    def test_first_round_takes_the_plan_and_answers_the_fixed_stage_used(self):
        """1 周目の turn は plan を合わせの出力のまま運び、fix_plan・plan_review・answers・skip_rerun を、合わせの refixed が真なら案の直しの
        受け皿の got と答えの node から、偽なら fix-in から取る。ripple は最後の修正の段が使った物（refixed が真なら答えの node の fix_ripple）。
        refixed が真なのに案の直しの返りが無ければ、返さずに輪の節が落ちたとして抜ける。照らしは返す時だけ（返さない周は抜けた訳のまま）"""
        plain = self.run_turn()
        self.assertEqual((plain["plan"], plain["fix_plan"], plain["ripple"]), (FIXED_PLAN, FIX_IN["fix_plan"], FIRST_RIPPLE))
        self.assertEqual((plain["plan_review"], plain["answers"], plain["skip_rerun"]), (FIX_IN["review"], FIX_IN["answer"], ["u9"]))
        remade = {**ANSWER_REPLAN, "fix_ripple": FIRST_RIPPLE}
        again = self.run_turn(fixed=fixed(refixed=True, ripple=REMADE_RIPPLE), replan=REPLAN, answer_replan=remade)
        self.assertEqual((again["plan"], again["fix_plan"]), (FIXED_PLAN, REPLAN["fix_plan"]))
        self.assertEqual((again["plan_review"], again["answers"], again["skip_rerun"]), (ANSWER_REPLAN["plan_review"], ANSWER_REPLAN["fix_answers"], ["u1"]))
        self.assertEqual(again["ripple"], FIRST_RIPPLE, "案の直しが作り直せなかった時、2 度目の修正が使った 1 回目の一覧を返しの修正も使う")
        self.assertNotEqual(again["ripple"], REMADE_RIPPLE)
        for over in ({"replan": None}, {"answer_replan": None}):
            with self.subTest(over=sorted(over)):
                lost = self.run_turn(fixed=fixed(refixed=True), **{"replan": REPLAN, "answer_replan": remade, **over})
                self.assertEqual((lost["go"], lost["exit"]), (False, self.e.EXITS["fell"]))
        stay = self.run_turn(fixed=fixed(refixed=True), eyes=eyes("stay"))
        self.assertEqual(stay["exit"], "返す物が無い（どの目も通った）", "返さない周は案の直しの返りを照らさない")
        first = self.run_turn(fixed=fixed(refixed=True), replan=REPLAN, answer_replan=ANSWER_REPLAN)
        second = self.run_turn(k=2, prev=first, tests=gate_got("h2"), replan=None, answer_replan=None, fix_in=None)
        self.assertTrue(second["go"])
        for key in ("plan", "fix_plan", "ripple", "plan_review", "answers", "skip_rerun"):
            self.assertEqual(second[key], first[key], key)
        self.assertEqual(second["more"], [], "more は合わせが運ぶ返した段の並び")
        more = self.run_turn(fixed=fixed(more=[{"ok": True}]))
        self.assertEqual(more["more"], [{"ok": True}])

    def test_no_fix_run_does_not_return(self):
        """直す物が無い run（合わせの no_fix が真）は、目が作り残しを言っても修正の段へ返さずに抜ける（計画の無いまま修正役を起こさない）"""
        got = self.run_turn(fixed=fixed(no_fix=True))
        self.assertEqual((got["go"], got["exit"], got["rows"]), (False, "直す物が無い run は返さない", []))

    def test_later_round_without_its_own_tests_or_eyes_seals_the_state_before_the_return(self):
        """2 周目以降に、返した段が止まった・落ちたせいで試験か目の返りが無い周の頭は、返す前に試験と独立の目を通った状態（前の周の頭が運ぶ）を
        封じる。封じる差分を語る合わせの欄は前の周の物、異議と段の並びは返した段の物。戻す先は前の周の頭が返す時に取った木。異議だけで止まり
        試験と目が揃う周・差分が変わらない周・返す周・返さない周は今の周の状態のままで、戻す先は無い。合わせが読めない周は封じない"""
        self.assertIn("snap", inspect.signature(self.e.turn).parameters, "turn が返す時の木の控え snap を受けない")
        snaps = Snaps("t1")
        prev = self.run_turn(fixed=before_fixed(), tests=gate_got("h1"), snap=snaps)
        self.assertEqual((prev["go"], snaps.calls, [r.get("tree") for r in prev["rows"]]), (True, 1, ["t1"]), "返す時に 1 回だけ木を取って周の行に置く")
        for name, over, exit_ in (("a 合わせが進めず試験も目も無い", {"fixed": back_fixed(go=False, objection="返した段の異議"), "tests": None, "eyes": None}, "stop"),
                                  ("b 合わせは進んだが試験が無い", {"fixed": back_fixed(), "tests": None}, "fell")):
            with self.subTest(name):
                got = self.run_turn(k=2, prev=prev, **over)
                self.assertEqual((got["go"], got["sealable"]), (False, True))
                self.assertEqual((got["tests"], got["eyes"], got["fingerprint"], got["item_claims"]),
                                 (prev["tests"], prev["eyes"], {"head": "abc", "diff_hash": "h1"}, {"items": [1], "claims": ["claim-before"]}))
                self.assertEqual((got["green_ok"], got["eyes_ok"]), (prev["green_ok"], prev["eyes_ok"]))
                self.assertEqual({key: got["fixed"][key] for key in SEALED}, {key: before_fixed()[key] for key in SEALED})
                for key in ("objection", "stages", "more", "go", "plan"):
                    self.assertEqual(got["fixed"][key], over["fixed"][key], f"{key} は返した段の物のまま")
                if exit_ == "stop":
                    self.assertTrue(got["exit"].startswith(self.e.EXITS["stop"]) and "返した段の異議" in got["exit"], got["exit"])
                else:
                    self.assertEqual(got["exit"], self.e.EXITS["fell"])
                self.assertEqual(got["checkpoint"], {"round": 1, "tree": "t1"})
                self.assertEqual(got["left"], ITEMS)
                self.assertEqual(set(got), set(self.e.FIELDS))
                self.assertEqual(json.loads(json.dumps(got)), got)
        self.assertEqual(snaps.calls, 1, "返さない周は木を取らない")
        for name, over, left in (("c 異議だけで止まり試験と目が揃う", {"fixed": back_fixed(objection="設計に異議"), "tests": gate_got("h2"), "eyes": eyes()}, ITEMS),
                                 ("d 差分が変わらない", {"fixed": back_fixed(), "tests": gate_got("h1"), "eyes": eyes(items=ITEMS[:1])}, ITEMS[:1])):
            with self.subTest(name):
                got = self.run_turn(k=2, prev=prev, snap=snaps, **over)
                self.assertEqual((got["go"], got["sealable"], got["checkpoint"]), (False, True, None))
                self.assertEqual((got["fixed"], got["tests"], got["eyes"]), (over["fixed"], over["tests"], over["eyes"]), "今の周の状態のまま")
                self.assertEqual(got["left"], left)
        first = self.run_turn(snap=Snaps("t0"))
        self.assertEqual((first["go"], first["checkpoint"], [r.get("tree") for r in first["rows"]]), (True, None, ["t0"]), "返す周の戻す先はまだ無く、新しい行が木を持つ")
        quiet = Snaps("t9")
        stay = self.run_turn(eyes=eyes("stay"), snap=quiet)
        capped = self.run_turn(k=4, prev=self.run_turn(k=3, prev=self.run_turn(k=2, prev=prev, tests=gate_got("h2")), tests=gate_got("h3")), tests=gate_got("h4"), snap=quiet)
        self.assertEqual((stay["checkpoint"], capped["checkpoint"], capped["exit"], quiet.calls), (None, None, self.e.CAP_WHY, 0), "返さない抜け方は木を取らない")
        for name, over in (("f1 合わせが無い", {"prev": prev, "fixed": None}), ("f2 前の周が無い", {"prev": None})):
            with self.subTest(name):
                got = self.run_turn(k=2, tests=None, eyes=None, **over)
                self.assertEqual((got["sealable"], got["fixed"], got["tests"], got["eyes"], got["checkpoint"]), (False, None, None, None, None))

    def test_script_fallbacks_carry_every_record_field(self):
        """周の頭の script の落ちた時の記録 fallen と集めの script の落ちた時の記録 fallback が、FIELDS・RECORD と同じ鍵の組を持ち、戻す先 checkpoint は
        null になる"""
        self.assertIn("checkpoint", self.e.FIELDS)
        self.assertIn("checkpoint", self.e.RECORD)
        run = {}
        for name in ("eyes_back", "eyes_back_end"):
            env = {"INPUTS_ROUND": "null", **{f"INPUTS_BACK_{n}": "null" for n in range(1, 5)}}
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                run[name] = runpy.run_path(str(kit.BLOCKS / BLOCK / "scripts" / f"{name}.py"), run_name="__main__")
        fallen, fallback = run["eyes_back"]["fallen"]("落ちた"), run["eyes_back_end"]["fallback"]("落ちた")
        self.assertEqual(set(fallen), set(self.e.FIELDS))
        self.assertEqual(set(fallback), set(self.e.RECORD))
        self.assertEqual((fallen["checkpoint"], fallback["checkpoint"]), (None, None))
        self.assertEqual(self.e.last([fallen])["checkpoint"], None)

    def test_tree_now_reads_the_tree_or_nothing(self):
        """tree_now は git の写しでは leftovers.snapshot と同じ木の sha を返し、作業ツリーと本物の index を変えない。git でないフォルダでは
        誤りを上げずに空の字を返す"""
        self.assertTrue(hasattr(self.e, "tree_now"), "木を読む口 tree_now が無い")
        import leftovers
        repo = hermetic.tmpdir(self) / "repo"
        committed_copy(repo, SEED)
        (repo / "added-by-the-fix.txt").write_text("new\n", encoding="utf-8")
        before = (git(repo, "status", "--porcelain=v1", "-uall"), git(repo, "diff", "--cached", "--name-only"), git(repo, "ls-files", "-s"))
        tree = self.e.tree_now(repo)
        self.assertEqual(tree, leftovers.snapshot(repo))
        self.assertRegex(tree, r"^[0-9a-f]{40,64}$")
        self.assertEqual((git(repo, "status", "--porcelain=v1", "-uall"), git(repo, "diff", "--cached", "--name-only"), git(repo, "ls-files", "-s")), before)
        with tempfile.TemporaryDirectory() as bare:
            self.assertEqual(self.e.tree_now(bare), "")

    def test_items_left_unreturned_are_named_even_with_no_round(self):
        """1 周目に返さずに抜けた時（修正の段が止めた・直す物が無い run）も、目が返そうとした項目と抜けた訳を、承認ノードと報告が読む lines の
        1 行に出す。目が返す物を言わなかった run は今どおり空"""
        for over in ({"fixed": fixed(objection="設計に異議")}, {"fixed": fixed(no_fix=True)}):
            with self.subTest(over=over):
                got = self.run_turn(**over)
                out = self.e.lines(got["rows"], got["exit"], got["left"])
                self.assertEqual(len(out), 1, out)
                self.assertIn(got["exit"], out[0])
                self.assertIn("R2: 入口が足りない", out[0])
        stay = self.run_turn(eyes=eyes("stay"))
        self.assertEqual(self.e.lines(stay["rows"], stay["exit"], stay["left"]), [])


class LastCase(_Case):
    def head(self, k, **over) -> dict:
        return {**self.run_turn(k=k, prev=None if k == 1 else self.run_turn(), tests=gate_got(f"h{k}")), **over}

    def test_last_takes_the_latest_round_and_keeps_the_first_when_none_returned(self):
        """last は最後に走った周の頭の状態（fixed・tests・eyes・指紋・sealable・rows）を返し、1 度も返さなかった run では最初の状態をそのまま返す。
        1 つも走っていなければ None"""
        none_returned = self.run_turn(eyes=eyes("stay"))
        got = self.e.last([none_returned, None, None, None])
        self.assertEqual(got["exit"], none_returned["exit"])
        self.assertEqual((got["fixed"], got["tests"], got["eyes"], got["rows"]), (fixed(), gate_got(), eyes("stay"), []))
        self.assertEqual(set(got), set(self.e.RECORD))
        first, second = self.run_turn(tests=gate_got("h1")), self.run_turn(k=2, prev=self.run_turn(), tests=gate_got("h2"), eyes=eyes("stay"))
        latest = self.e.last([first, second, None, None])
        self.assertEqual((latest["tests"], latest["eyes"], latest["fingerprint"]), (gate_got("h2"), eyes("stay"), {"head": "abc", "diff_hash": "h2"}))
        self.assertTrue(latest["sealable"])
        self.assertIsNone(self.e.last([None, None, None, None]))
        self.assertIsNone(self.e.last([]))

    def test_current_prefers_the_loop_record_and_falls_back_to_the_first(self):
        """current は、輪の記録が在り、記録の fixed が null でない時だけ記録の fixed・tests・eyes を返す（exit が『輪の節が落ちた』でも、
        返す前の検証済みの状態を持ち越した記録は使う）。記録が無い・fixed の欠けた記録（集めの fallback の記録も）の時は、渡された最初の
        fixed・tests・eyes を返す"""
        first = ("first-fixed", "first-tests", "first-eyes")
        done = {"rows": [], "exit": "返す物が無い", "left": [], "fixed": "last-fixed", "tests": "last-tests", "eyes": "last-eyes"}
        self.assertEqual(self.e.current(done, *first), ("last-fixed", "last-tests", "last-eyes"))
        self.assertEqual(self.e.current(None, *first), first)
        self.assertEqual(self.e.current({**done, "exit": self.e.EXITS["fell"], "fixed": None, "tests": None, "eyes": None}, *first), first)
        self.assertEqual(self.e.current({**done, "exit": self.e.EXITS["fell"]}, *first), ("last-fixed", "last-tests", "last-eyes"),
                         "輪の節が落ちた周でも、記録が持ち越した検証済みの状態は使う")
        self.assertEqual(self.e.current({**done, "fixed": None}, *first), first)
        self.assertEqual(self.e.current({**done, "eyes": None}, *first), ("last-fixed", "last-tests", None), "最後の周に目の got が無いのはそのまま")


class LinesCase(_Case):
    def test_lines_name_each_round_and_the_exit(self):
        """lines が返した周ごとの目の判定（REVIEW_WORDS の言い方）と項目と、返した段が通っていない確かめの 1 行と、最後の抜けた訳を並べ、
        返した周が 0 なら空を返す"""
        gatemarks = __import__("gatemarks")
        rows = [self.e.row(1, eyes(), ITEMS), self.e.row(2, eyes(r2={"status": "fix-needed", "reason": "x"}), ITEMS[:1])]
        out = self.e.lines(rows, "返す物が無い（どの目も通った）")
        fix, passed = gatemarks.REVIEW_WORDS["fix-needed"], gatemarks.REVIEW_WORDS["pass"]
        self.assertEqual(out[0], f"1 周目: 返した（R1: {fix}・R2: {passed}）——返した項目: R1: src/a.py:12: 写しが残っている／R2: 入口が足りない")
        self.assertEqual(out[1], f"2 周目: 返した（R1: {fix}・R2: {fix}）——返した項目: R1: src/a.py:12: 写しが残っている")
        self.assertEqual(out[2:], [self.e.NOT_REVIEWED, "輪を抜けた訳: 返す物が無い（どの目も通った）"])
        self.assertEqual(self.e.count(rows), 2)
        self.assertEqual(self.e.lines([], "返す物が無い"), [], "返した周が 0 なら空")
        self.assertEqual(self.e.lines(None, ""), [])
        capped = self.e.lines(rows, self.e.CAP_WHY, ITEMS)
        self.assertEqual(capped[-1], f"輪を抜けた訳: {self.e.cap_text(ITEMS)}")
        self.assertIn("R2: 入口が足りない", capped[-1])
        self.assertNotIn("工場の不具合", "".join(capped))

    UNFIXED = "返したが直せなかった項目: "

    def unfixed(self, out) -> list:
        return [line for line in out if self.UNFIXED in line]

    def test_lines_follow_each_exit_through_the_turn(self):
        """k=2 で前の周の頭が返す前の状態を運ぶ時、周の頭の返り（rows・exit・left・checkpoint）を lines に渡すと、止まった・落ちた・差分が変わらない・
        異議だけで止まった抜け方では返して直せなかった項目を名指し、止まった・落ちたでは封じたのが 1 周目に返す前の状態であることを言い、
        差分が変わらない時は返す前と同じ状態だと言う。上限の抜け方は上限の訳の 1 行だけで、直せなかった項目の行を重ねない"""
        prev = self.run_turn(fixed=before_fixed(), tests=gate_got("h1"), snap=Snaps("t1"))
        stopped = self.run_turn(k=2, prev=prev, fixed=back_fixed(go=False, objection="返した段の異議"), tests=None, eyes=None)
        fell = self.run_turn(k=2, prev=prev, fixed=back_fixed(), tests=None)
        same = self.run_turn(k=2, prev=prev, fixed=back_fixed(), tests=gate_got("h1"), eyes=eyes(items=ITEMS[:1]))
        objected = self.run_turn(k=2, prev=prev, fixed=back_fixed(objection="設計に異議"), tests=gate_got("h2"), eyes=eyes())
        cases = (("止まった", stopped, ITEMS, True, False), ("落ちた", fell, ITEMS, True, False),
                 ("差分が変わらない", same, ITEMS[:1], False, True), ("異議だけで止まった", objected, ITEMS, False, False))
        for name, got, items, sealed_before, same_state in cases:
            with self.subTest(name):
                out = self.e.lines(got["rows"], got["exit"], got["left"])
                found = self.unfixed(out)
                self.assertEqual(len(found), 1, out)
                self.assertTrue(found[0].startswith(self.UNFIXED), found[0])
                self.assertIn(self.e.left_text(items), found[0])
                self.assertIn("src/a.py:12: 写しが残っている", found[0])
        self.assertIn("checkpoint", inspect.signature(self.e.lines).parameters, "lines が封じた周の checkpoint を受けない")
        for name, got, items, sealed_before, same_state in cases:
            with self.subTest(name, part="sealed state"):
                out = self.e.lines(got["rows"], got["exit"], got["left"], checkpoint=got["checkpoint"])
                self.assertEqual(any("1 周目に返す前の状態" in line for line in out), sealed_before, out)
                self.assertEqual(any("返す前と同じ状態" in line for line in out), same_state, out)
        cap = self.run_turn(k=4, prev=self.run_turn(k=3, prev=self.run_turn(k=2, prev=prev, tests=gate_got("h2")), tests=gate_got("h3")), tests=gate_got("h4"))
        out = self.e.lines(cap["rows"], cap["exit"], cap["left"], checkpoint=cap["checkpoint"])
        self.assertEqual(self.unfixed(out), [], "上限の抜け方は上限の訳の行が残った作り残しを名指す。直せなかった項目の行を重ねない")
        self.assertEqual([line for line in out if self.e.cap_text(ITEMS) in line], [f"輪を抜けた訳: {self.e.cap_text(ITEMS)}"])
        self.assertFalse(any("返す前と同じ状態" in line or "1 周目に返す前の状態" in line for line in out), out)

    def test_lines_name_the_restore_outcome_without_foretelling_the_seal(self):
        """封じた周の checkpoint が在る時、lines は戻しの結末を言う。戻して控えを書いた時は控えのパスと git apply を、作業ツリーを変えていなかった時は
        変えていなかったと、戻せなかった時は訳を（封じが拒むとは先取りせず）、結末の記録が無い（null）時は記録が無いと言う。空の dict と null は別"""
        params = inspect.signature(self.e.lines).parameters
        self.assertTrue({"checkpoint", "back_restore"} <= set(params), f"lines の引数 {sorted(params)} に checkpoint・back_restore が無い")
        rows = [self.e.row(1, eyes(), ITEMS)]
        exit_ = f"{self.e.EXITS['stop']}（修正の段の合わせが進めなかった）"

        def say(back_restore) -> list:
            return self.e.lines(rows, exit_, ITEMS, checkpoint={"round": 1, "tree": "t1"}, back_restore=back_restore)

        kept = say({"restored": True, "kept": "/place/eyes-back-kept.patch", "reason": ""})
        self.assertTrue(any("1 周目に返す前の状態" in line for line in kept), kept)
        self.assertTrue(any("/place/eyes-back-kept.patch" in line and "git apply" in line for line in kept), kept)
        untouched = say({"restored": False, "kept": "", "reason": ""})
        self.assertTrue(any("変えていなかった" in line for line in untouched), untouched)
        self.assertFalse(any("git apply" in line for line in untouched), untouched)
        failed = say({"restored": False, "kept": "/place/eyes-back-kept.patch", "reason": self.e.RESTORE_DIFFERS})
        self.assertTrue(any(self.e.RESTORE_DIFFERS in line and "戻せなかった" in line for line in failed), failed)
        self.assertFalse(any("変えていなかった" in line for line in failed), failed)
        self.assertNotIn("拒まれる", "".join(failed), "封じの結末は merge の返りに任せ、ここで先取りしない")
        missing = say(None)
        self.assertTrue(any("戻しの結末の記録が無い" in line for line in missing), missing)
        self.assertFalse(any("変えていなかった" in line for line in missing), "null は空の dict と別（変えていなかったとは読まない）")
        self.assertNotEqual(missing, untouched)


if __name__ == "__main__":
    unittest.main()


class RestoreCase(_Case):
    """封じる前の戻し（restore_before_seal と節 eyes-back-restore の script）。写しの repo は本物の git で、返した段の書き換えは追跡のファイルの
    書き換えと新しいファイルで作る"""

    def setUp(self):
        super().setUp()
        self.repo = hermetic.tmpdir(self) / "repo"
        committed_copy(self.repo, SEED)
        import green_cert
        import leftovers
        self.green_cert, self.leftovers = green_cert, leftovers
        self.fingerprint = green_cert.fingerprint(self.repo)
        self.tree = self.e.tree_now(self.repo) if hasattr(self.e, "tree_now") else ""
        self.checkpoint = {"round": 1, "tree": self.tree}
        self.kept = hermetic.tmpdir(self) / self.KEPT

    KEPT = "eyes-back-kept.patch"

    def rewrite(self):
        """返した段の書き換え: 追跡のファイルを書き換え、新しいファイルを足す"""
        with (self.repo / "stats.py").open("a", encoding="utf-8") as f:
            f.write("\n# 返した段の書き換え\n")
        (self.repo / "added-by-the-back-round.txt").write_text("new\n", encoding="utf-8")

    def needs_gate(self):
        self.assertTrue(hasattr(self.e, "restore_before_seal"), "封じる前の戻しの門 restore_before_seal が無い")

    def test_restore_returns_the_tree_and_keeps_the_rewrite(self):
        """追跡のファイルの書き換えと新しいファイルを足した作業ツリーで restore_before_seal を呼ぶと、restored が真になり、作業ツリーの指紋が
        取った指紋と合い、kept のファイルを git apply すると書き換えが戻る"""
        self.needs_gate()
        self.rewrite()
        rewritten = (self.repo / "stats.py").read_text(encoding="utf-8")
        self.assertFalse(self.green_cert.matches(self.fingerprint, self.repo))
        got = self.e.restore_before_seal(self.repo, self.checkpoint, self.fingerprint, self.kept)
        self.assertEqual((got["restored"], got["reason"]), (True, ""))
        self.assertEqual(got["kept"], str(self.kept))
        self.assertTrue(self.green_cert.matches(self.fingerprint, self.repo))
        self.assertEqual(self.e.tree_now(self.repo), self.tree)
        self.assertFalse((self.repo / "added-by-the-back-round.txt").exists())
        git(self.repo, "apply", str(self.kept))
        self.assertEqual((self.repo / "stats.py").read_text(encoding="utf-8"), rewritten)
        self.assertEqual((self.repo / "added-by-the-back-round.txt").read_text(encoding="utf-8"), "new\n")

    def test_restore_leaves_a_matching_tree_or_a_missing_checkpoint_alone(self):
        """指紋が今の木と合う時と、checkpoint が dict でない時は、作業ツリーにも kept にも触らず、restored 偽・kept 空・reason 空を返す"""
        self.needs_gate()
        nothing = {"restored": False, "kept": "", "reason": ""}
        self.assertEqual(self.e.restore_before_seal(self.repo, self.checkpoint, self.fingerprint, self.kept), nothing)
        self.assertEqual(self.e.tree_now(self.repo), self.tree)
        self.assertFalse(self.kept.exists())
        self.rewrite()
        rewritten = self.e.tree_now(self.repo)
        for checkpoint in (None, "x", []):
            with self.subTest(checkpoint=checkpoint):
                self.assertEqual(self.e.restore_before_seal(self.repo, checkpoint, self.fingerprint, self.kept), nothing)
                self.assertEqual(self.e.tree_now(self.repo), rewritten)
                self.assertFalse(self.kept.exists())

    def test_restore_names_why_it_could_not_return(self):
        """戻す先の木が空なら木を変えずに RESTORE_NO_TREE、HEAD が動いて戻した後も指紋が合わなければ RESTORE_DIFFERS、戻しが OSError で
        落ちれば RESTORE_ERROR で、どの時も restored は偽。戻しを試みた時は kept の控えが先に書かれている"""
        self.needs_gate()
        for word in ("RESTORE_NO_TREE", "RESTORE_DIFFERS", "RESTORE_ERROR"):
            self.assertTrue(isinstance(getattr(self.e, word, None), str) and getattr(self.e, word), f"{word} が無い")
        self.assertEqual(len({self.e.RESTORE_NO_TREE, self.e.RESTORE_DIFFERS, self.e.RESTORE_ERROR}), 3)
        self.rewrite()
        rewritten = self.e.tree_now(self.repo)
        got = self.e.restore_before_seal(self.repo, {"round": 1, "tree": ""}, self.fingerprint, self.kept)
        self.assertEqual((got["restored"], got["reason"]), (False, self.e.RESTORE_NO_TREE))
        self.assertEqual(self.e.tree_now(self.repo), rewritten)
        self.assertFalse(self.kept.exists(), "木を触らない時は控えも書かない")
        with mock.patch.object(self.leftovers, "restore_paths", side_effect=OSError("書けない")):
            got = self.e.restore_before_seal(self.repo, self.checkpoint, self.fingerprint, self.kept)
        self.assertEqual((got["restored"], got["reason"]), (False, self.e.RESTORE_ERROR))
        self.assertEqual(got["kept"], str(self.kept))
        self.assertIn("added-by-the-back-round.txt", self.kept.read_text(encoding="utf-8"), "控えは戻しの前に書かれる")
        self.assertEqual(self.e.tree_now(self.repo), rewritten)
        self.kept.unlink()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "返した段が commit した")
        got = self.e.restore_before_seal(self.repo, self.checkpoint, self.fingerprint, self.kept)
        self.assertEqual((got["restored"], got["reason"]), (False, self.e.RESTORE_DIFFERS))
        self.assertEqual(got["kept"], str(self.kept))
        self.assertTrue(self.kept.is_file())

    def test_restore_script_reads_both_inputs_and_keeps_the_patch_in_the_place(self):
        """節 eyes-back-restore の script は、写しの repo を cwd にして checkpoint と指紋を読み、restored が真で、置き場に eyes-back-kept.patch が
        在り、指紋が合う。checkpoint が null の時も指紋を読み、木に触らない"""
        script = kit.BLOCKS / BLOCK / "scripts" / "eyes_back_restore.py"
        self.assertTrue(script.is_file(), "節 eyes-back-restore の script eyes_back_restore.py が無い")
        run = kit.Run(self, BLOCK)
        run.repo = self.repo
        self.rewrite()
        rewritten = self.e.tree_now(self.repo)
        got = run.script("eyes_back_restore", checkpoint="null", fingerprint=json.dumps(self.fingerprint))
        self.assertEqual(got, {"restored": False, "kept": "", "reason": ""})
        self.assertEqual(self.e.tree_now(self.repo), rewritten)
        got = run.script("eyes_back_restore", checkpoint=json.dumps(self.checkpoint), fingerprint=json.dumps(self.fingerprint))
        self.assertEqual((got["restored"], got["reason"]), (True, ""))
        self.assertEqual(got["kept"], str(run.artifacts / self.KEPT))
        self.assertTrue((run.artifacts / self.KEPT).is_file())
        self.assertTrue(self.green_cert.matches(self.fingerprint, self.repo))
