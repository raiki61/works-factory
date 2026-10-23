"""再審の役の受け付け（src/rejudge.py）の試験。写す元は lib/tests/test_judge_accept.py の RejudgeCase・RejudgeDiffCase と
tests/workflows/test_judge.py の再審の場面。受け付けの決まりは docs/design/diagnose.md の 3.8。"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.diagnose import support

UNIT_A = "src/a.py:f — 上限を超えた値を黙って切る"
UNIT_B = "src/b.py:g — 名前が紛らわしい"
OBJECTION = f"{UNIT_A} の処方が誤り。12 行は切らずに拒んでいる"
FIRST = {"framing": "上限の扱いが根", "one_shot": "切らずに拒む", "questions": [{"key": "q1", "kind": "stuck", "status": "held", "reason": "割れる"}],
         "units": [{"key": UNIT_A, "label": "block", "disposition": "do-now", "reason": "切る"},
                   {"key": UNIT_B, "label": "suggest", "disposition": "do-now", "reason": "読み手が迷う"}],
         "materials_missing": [], "carried_r1": [], "one_shot_closes": [UNIT_A], "precedents": []}


def reply(verdict="一部採る", **over):
    units = [{"key": UNIT_A, "label": "block", "disposition": "do-now", "reason": "12 行を切らずに拒むよう直す"},
             {"key": UNIT_B, "label": "nit", "reason": "読み手は迷わない"}]
    return {"verdict": verdict, "new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた", "units": units,
            "reason": "上限の単位は採り、名前の単位は下げた", **over}


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "diagnose")
        support.seeded(self.run)
        self.mod = support.modules()
        self.rejudge, self.files = self.mod["rejudge"], self.mod["files"]
        self.repo, self.place = self.run.repo, self.run.artifacts

    def intake(self, objection=OBJECTION, prior=None, **extra):
        prior = json.dumps(FIRST if prior is None else prior, ensure_ascii=False)
        return self.run.script("intake", objection=objection, prior=prior, **extra)

    def saved(self, name):
        return json.loads((self.place / name).read_text(encoding="utf-8"))

    def take(self, rep):
        return self.rejudge.take(self.place, rep, self.repo)


class RejudgeCase(_Base):
    def test_intake_writes_first_judgment_and_units_before(self):
        self.assertEqual(self.intake(), {"due": True, "mode": "rejudge", "reason": ""})
        self.assertEqual(self.saved("first-judgment.json"), FIRST)
        before = self.saved("units-before.json")
        self.assertEqual(before["node"], "p2.rejudge")
        self.assertEqual(before["numbered_keys"], [UNIT_A, UNIT_B])
        self.assertEqual(before["objection"], OBJECTION)
        self.assertTrue((self.place / "tree.json").is_file())

    def test_empty_facts_rejected(self):
        self.intake()
        got = self.take(reply(new_facts="確かめた"))
        self.assertFalse(got["ok"])
        self.assertIn("new_facts", got["reason"])
        self.assertFalse((self.place / "rejudge-diff.json").exists())

    def test_tree_changed_rejected(self):
        self.intake()
        (self.repo / "a.txt").write_text("x\n", encoding="utf-8")
        got = self.take(reply())
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])

    def test_reply_shape_error_is_a_rejection(self):
        self.intake()
        got = self.take({"verdict": "採る", "new_facts": "x" * 30, "units": [{"label": "block"}]})
        self.assertFalse(got["ok"])
        self.assertIn("key", got["reason"])
        self.assertFalse((self.place / "judgment.json").exists(), "拒んだ返答は judgment.json を書かない")
        self.assertFalse(self.take([1])["ok"])
        self.assertIn("返答の形が違う", self.take({"verdict": "採る", "new_facts": "x" * 30})["reason"])

    def test_accept_writes_judgment_and_diff(self):
        self.intake()
        got = self.take(reply())
        self.assertEqual((got["ok"], got["verdict"]), (True, "一部採る"), got)
        self.assertEqual(self.saved("first-judgment.json"), FIRST, "1 回目の判定は上書きしない")
        now = self.saved("judgment.json")
        self.assertEqual(set(now), set(FIRST), "1 回目の全部の欄を持ち、単位だけが替わる")
        self.assertEqual(now["framing"], FIRST["framing"])
        self.assertEqual(now["units"][1], {"key": UNIT_B, "label": "nit", "reason": "読み手は迷わない"})
        rows = self.saved("rejudge-diff.json")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["pass"], row["node"], row["verdict"]), ("rejudge", "p2.rejudge", "一部採る"))
        self.assertEqual(row["unnamed_changed"], [UNIT_B])
        named = {(c["key"], c["field"]): c["named"] for c in row["changed"] if c["kind"] == "changed"}
        self.assertEqual(named[(UNIT_B, "label")], False)
        self.assertEqual(named[(UNIT_A, "reason")], True)
        self.assertEqual(self.saved("rejudge-reply.json"), [reply()])

    def test_lowered_block_named_in_diff_and_exit(self):
        self.intake()
        rep = reply(verdict="採る")
        rep["units"][0] = {**rep["units"][0], "label": "suggest", "disposition": "do-now"}
        self.assertTrue(self.take(rep)["ok"])
        self.assertEqual(self.saved("rejudge-diff.json")[0]["lowered"], [UNIT_A])
        got = self.rejudge.collect(self.place)
        self.assertTrue(got["ok"], got)
        self.assertEqual((got["passes"], got["verdicts"], got["lowered"]), (1, ["採る"], [UNIT_A]))
        self.assertIn(UNIT_A, got["objection"])
        self.assertEqual(got["unsettled"], {"text": "", "settled": True})
        self.assertEqual(self.saved("rejudge-exit.json"), got)
        self.assertEqual(self.rejudge.verdict_of(self.place), "採る")

    def test_new_open_units(self):
        self.intake()
        rep = reply()
        rep["units"].append({"key": "src/c.py:h — 上限の抜け道がもう 1 つ", "label": "block"})
        self.assertTrue(self.take(rep)["ok"])
        got = self.rejudge.collect(self.place)
        self.assertEqual(got["new_open_units"], ["src/c.py:h — 上限の抜け道がもう 1 つ"])
        self.assertFalse(got["unsettled"]["settled"], "一部採るは異議を降ろさない")

    def test_collect_after_give_up(self):
        self.intake()
        outs = [self.rejudge.accept_reply(self.place, reply(new_facts="確かめた"), None, self.repo) for _ in range(3)]
        self.assertEqual([o["done"] for o in outs], [False, False, True])
        got = self.saved("rejudge-exit.json")
        self.assertFalse(got["ok"])
        self.assertIn("3 回", got["reason"])
        self.assertIsNone(self.rejudge.verdict_of(self.place))
        self.assertEqual(sorted(p.name for p in self.place.glob("stop*")), [], "止めの控えは書かない")

    def test_accepted_round_writes_the_exit_when_the_loop_ends(self):
        self.intake()
        got = self.rejudge.accept_reply(self.place, reply(verdict="退ける"), None, self.repo)
        self.assertEqual((got["ok"], got["done"]), (True, True))
        self.assertEqual(self.saved("rejudge-exit.json")["verdicts"], ["退ける"])

    def test_resubmit_returns_only_the_rejected_fields(self):
        """拒まれた後の出し直しの役は拒まれた欄だけを返し、受け付けが前の答えの控えと欄ごとに合わせて照らす"""
        self.intake()
        first = self.rejudge.accept_reply(self.place, reply(new_facts="確かめた"), None, self.repo)
        self.assertEqual((first["ok"], first["done"]), (False, False))
        self.assertEqual(self.saved("candidate-rejudge.json")["verdict"], "一部採る", "合わせた答えの控えが残る")
        fix = {"new_facts": "src/a.py の 12 行を読み、上限の超過で黙って切ることを確かめた"}
        got = self.rejudge.accept_reply(self.place, reply(new_facts="確かめた"), fix, self.repo)
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        self.assertEqual(self.saved("rejudge-reply.json")[0]["units"], reply()["units"], "返さなかった欄は前のまま")

    def test_missing_root_field_is_refused_then_resubmitted_alone(self):
        """#832: 再審の役の型は根の欄を要ると書かない（出し直しの役と同じ形）。units の欠けた答えは受け付けが拒み、出し直しの units で通る"""
        self.intake()
        bare = reply()
        bare.pop("units")
        first = self.rejudge.accept_reply(self.place, bare, None, self.repo)
        self.assertEqual((first["ok"], first["reason"]), (False, self.rejudge.rolekit.MISSING_FIELDS.format(keys="units")))
        got = self.rejudge.accept_reply(self.place, None, {"units": reply()["units"]}, self.repo)
        self.assertEqual((got["ok"], got["done"]), (True, True), got)

    def test_resubmit_with_a_non_object_part_is_rejected(self):
        self.intake()
        self.rejudge.accept_reply(self.place, reply(new_facts="確かめた"), None, self.repo)
        got = self.rejudge.accept_reply(self.place, None, "これは JSON でない", self.repo)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("出し直しの返答が JSON として読めない", got["reason"])

    def test_class_query_examples_tried(self):
        self.intake()
        rep = reply()
        rep["units"][0]["class_query"] = {
            "how": {"patterns": ["truncate("], "fixed": True, "paths": ["src"], "count": "lines"},
            "counts": "defects", "total": 1, "hits": ["x = truncate(v)"], "misses": ["x = reject_over(truncate(v))"]}
        got = self.take(rep)
        self.assertFalse(got["ok"])
        self.assertIn("class_query", got["reason"])
        rep["units"][0]["class_query"]["misses"] = ["x = reject_over(v)"]
        got = self.take(rep)
        self.assertTrue(got["ok"], got)
        self.assertIn(UNIT_A, self.saved("query-examples.json"))
        self.assertNotIn("class_query", self.saved("judgment.json")["units"][0], "再審の後の単位は class_query を残さない（今のまま）")

    def test_session_stop_when_there_is_no_first_judgment(self):
        for blank in ("", "null"):
            with self.subTest(blank):
                got = self.run.script("intake", objection="異議", prior=blank)
                self.assertEqual((got["due"], got["mode"]), (False, "rejudge"))
                doc = self.saved("intake.json")
                self.assertEqual((doc["status"], doc["stop_reason"]), ("failed", "works:rejudge-session"))
                self.assertIn("1 回目の判定（judgment.json）が無い", doc["reason"])

    def test_unreadable_prior_stops_as_rejudge(self):
        got = self.run.script("intake", objection="異議", prior=json.dumps({"units": [{"label": "block"}]}))
        self.assertFalse(got["due"])
        doc = self.saved("intake.json")
        self.assertEqual(doc["stop_reason"], "works:rejudge")
        self.assertIn("入力 prior", doc["reason"])


class RejudgeDiffCase(unittest.TestCase):
    BEFORE = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "suggest", "disposition": "do-now"},
              {"key": "k3", "label": "info"}]

    def setUp(self):
        self.rejudge = support.modules()["rejudge"]

    def test_named_by_number(self):
        after = [{"key": "k1", "label": "block"}, {"key": "k2", "label": "nit"}, {"key": "k3", "label": "info"}]
        for text in ("#2 の判定を見直せ", "no 2 は誤り", "No.2 は誤り", "2 番の単位", "２番の単位"):
            with self.subTest(text):
                got = self.rejudge.diff_units(self.BEFORE, after, text, ["k1", "k2", "k3"])
                self.assertEqual(got["unnamed_changed"], [], got)
                self.assertTrue(all(c["named"] for c in got["changed"]))
        got = self.rejudge.diff_units(self.BEFORE, after, "#12 と #1 を見直せ", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k2"])

    def test_no_names_all_unnamed(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k2", "label": "nit"},
                 {"key": "k3", "label": "info", "reason": "足した"}]
        got = self.rejudge.diff_units(self.BEFORE, after, "判定がおかしい", ["k1", "k2", "k3"])
        self.assertEqual(got["unnamed_changed"], ["k1", "k2", "k3"])
        self.assertEqual(got["lowered"], ["k1"])

    def test_removed_and_lowered(self):
        after = [{"key": "k1", "label": "suggest", "disposition": "do-now"}, {"key": "k4", "label": "block"}]
        got = self.rejudge.diff_units(self.BEFORE, after, "k1 は block でない", [])
        kinds = {(c["key"], c["kind"]) for c in got["changed"]}
        self.assertTrue({("k2", "removed"), ("k3", "removed"), ("k4", "added"), ("k1", "changed")} <= kinds)
        self.assertEqual(got["lowered"], ["k1"])
        self.assertEqual(got["unnamed_changed"], ["k2", "k3", "k4"])

    def test_fields_are_the_writes_pick(self):
        after = [dict(self.BEFORE[0], origin_analysis="書き足した"), self.BEFORE[1], self.BEFORE[2]]
        self.assertEqual(self.rejudge.diff_units(self.BEFORE, after, "", [])["changed"], [])
        self.assertEqual(list(self.rejudge.REJUDGE_UNIT_FIELDS), ["key", "label", "disposition", "reason", "reopen_evidence"])
        self.assertEqual(self.rejudge.REJUDGE_VERDICTS, ("採る", "退ける", "一部採る"))
