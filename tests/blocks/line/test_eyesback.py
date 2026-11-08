"""独立の目から修正の段へ返す輪の、周の頭の決めと周の記録の行の形と最後の周の状態の選び（src/eyesback.py。docs/design/line.md の 1.3・5.4）。

周の頭の script は薄い口で、決めは turn に在る。ここは turn・last・current・lines を値で回し、返す条件・抜ける訳の順・案の選び・上限・記録の形を
確かめる（周の節の並びは test_wiring.py、筋書きは test_scenarios.py）。
"""
import json
import re
import unittest

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
        self.assertEqual((later["go"], later["exit"], later["sealable"]), (False, self.e.EXITS["fell"], False), "2 周目以降の欠けは封じない")
        first = self.run_turn(eyes=None)
        self.assertEqual((first["go"], first["exit"], first["sealable"]), (False, self.e.NO_RETURN, False), "1 周目に目が返らなかっただけでは落ちたと言わない")
        self.assertFalse(self.e.fell({"exit": first["exit"]}))
        prev = self.run_turn()
        got = self.run_turn(k=2, prev=prev, fixed=fixed(go=False, stop_reason="works:unrestored"), tests=None, eyes=None)
        self.assertTrue(got["exit"].startswith(self.e.EXITS["stop"]), got["exit"])
        self.assertEqual(script_const("eyes_back", "EXIT_FELL"), self.e.EXITS["fell"], "script の fallback の字")
        self.assertEqual(script_const("eyes_back_end", "EXIT_FELL"), self.e.EXITS["fell"])

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
        """current は、輪の記録が在り、その exit が『輪の節が落ちた』でなく、記録の fixed が null でない時だけ記録の fixed・tests・eyes を返す。
        記録が無い・集めの fallback の記録・fixed の欠けた記録の時は、渡された最初の fixed・tests・eyes を返す"""
        first = ("first-fixed", "first-tests", "first-eyes")
        done = {"rows": [], "exit": "返す物が無い", "left": [], "fixed": "last-fixed", "tests": "last-tests", "eyes": "last-eyes"}
        self.assertEqual(self.e.current(done, *first), ("last-fixed", "last-tests", "last-eyes"))
        self.assertEqual(self.e.current(None, *first), first)
        self.assertEqual(self.e.current({**done, "exit": self.e.EXITS["fell"], "fixed": None, "tests": None, "eyes": None}, *first), first)
        self.assertEqual(self.e.current({**done, "exit": self.e.EXITS["fell"]}, *first), first, "落ちた記録は状態が在っても使わない")
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


if __name__ == "__main__":
    unittest.main()
