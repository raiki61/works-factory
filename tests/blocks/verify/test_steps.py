"""判定の裏取りの block の src/steps を、この過程で呼んで確かめる（docs/design/verify.md の 7.2。今の lib/tests/test_judge_accept.py の
VerifyPrepCase・VerifyMergeCase から写した）。git のリポジトリは初めの commit を置いてから使う。"""
import json
import pathlib
import shutil
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

MEAN = "stats.py mean: 分母"
CLAMP = "stats.py clamp: 上限"
FMT = "stats.py fmt: 桁"


def unit(key, label="block", **extra):
    return {"key": key, "label": label, "reason": "事実: 分母が違う", **extra}


def judgment(*units, **extra):
    return json.dumps({"framing": "根は 1 つ", "one_shot": "照らしを足す", "units": list(units), **extra}, ensure_ascii=False)


TWO = judgment(unit(MEAN), unit(CLAMP), unit(FMT, "info", disposition="defer"))
UNIT_OK = {"unit": 1, "verdict": "root", "evidence_found": True, "evidence": "stats.py:4 に分母 len(xs) - 1 が在る",
           "location_ok": True, "location": "stats.py:4", "why": "ここを直せば症状が消える"}


class _Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "verify")
        (self.run.repo / "stats.py").write_text("def mean(xs):\n    return sum(xs) / (len(xs) - 1)\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.steps = kit.load("verify", "steps")
        self.out = self.run.artifacts

    def prep(self, raw=TWO, lang="", include=""):
        with self.run.env(include):
            return self.steps.prep(self.place(include), judgment=raw, lang=lang)

    def place(self, include=""):
        with self.run.env(include):
            import ports
            return ports.place()

    def finish(self, include=""):
        with self.run.env(include):
            return self.steps.finish(self.place(include))

    def notes(self):
        return json.loads((self.out / "verify.json").read_text(encoding="utf-8"))

    def answer(self, n, key, **over):
        path = self.out / "answers" / f"unit-{n}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({**UNIT_OK, "unit": n, **over}, ensure_ascii=False), encoding="utf-8")

    def synergy(self, doc):
        path = self.out / "answers" / "synergy.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


class OpenUnitsCase(_Base):
    def test_open_unit_selection(self):
        rows = [unit("a"), unit("b", "suggest", disposition="do-now"), unit("c", "suggest", disposition="defer"), unit("d", "nit"),
                unit("e", "info"), {"label": "block", "reason": "key が無い"}, "字"]
        self.assertEqual([u["key"] for u in self.steps.open_units({"units": rows})], ["a", "b"])
        self.assertEqual(self.steps.open_units(None), [])


class PrepCase(_Base):
    def test_one_open_unit_does_not_go_and_writes_not_run(self):
        got = self.prep(judgment(unit(MEAN), unit(CLAMP, "nit")))
        self.assertEqual((got["go"], got["prompt"]), (False, ""))
        self.assertTrue(got["reason"])
        self.assertEqual(self.notes()["units"], [])
        self.assertEqual(self.notes()["synergy"]["state"], "unverified")
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["stop_reason"]), (True, "ok", ""))
        self.assertEqual(done["report"], [f"判定の単位の裏取り: 回さなかった（{got['reason']}）"])

    def test_unreadable_port_does_not_go_and_finish_fails(self):
        for raw in ("{壊れた", '{"framing": "x"}', "null"):
            with self.subTest(raw=raw):
                got = self.prep(raw)
                self.assertIs(got["go"], False)
                done = self.finish()
                self.assertEqual((done["ok"], done["status"]), (False, "failed"))
                self.assertTrue(done["reason"].startswith("入力 judgment: "), done["reason"])
                self.assertEqual(self.notes()["units"], [])

    def test_two_open_units_write_briefs_and_prompt(self):
        got = self.prep(lang="日本語")
        self.assertIs(got["go"], True)
        names = sorted(p.name for p in self.out.glob("*.md"))
        self.assertEqual(names, ["judge-verify-prompt-1.md", "synergy.md", "unit-1.md", "unit-2.md"])
        one = (self.out / "unit-1.md").read_text(encoding="utf-8")
        self.assertIn(MEAN, one)
        self.assertNotIn(CLAMP, one)
        self.assertIn(str(self.out / "answers" / "unit-1.json"), one)
        agg = (self.out / "judge-verify-prompt-1.md").read_text(encoding="utf-8")
        self.assertEqual(agg, got["prompt"])
        self.assertIn("general-purpose", agg)
        for name in ("unit-1.md", "unit-2.md", "synergy.md"):
            self.assertIn(str(self.out / name), agg)
        self.assertNotIn("## Rules", agg)
        self.assertIn("日本語", one)
        self.assertEqual([(u["key"], u["state"]) for u in self.notes()["units"]], [(MEAN, "unverified"), (CLAMP, "unverified")])
        self.assertEqual(self.notes()["units"][0]["errors"], [self.steps.WAITING])

    def test_briefs_share_head_and_carry_query_rule(self):
        self.prep()
        texts = [(self.out / n).read_text(encoding="utf-8") for n in ("unit-1.md", "unit-2.md", "synergy.md")]
        heads = [t.split("## This sub-agent's")[0] for t in texts]
        self.assertEqual(len(set(heads)), 1)
        for t in texts:
            self.assertIn("Do not put the target's names in queries", t)
            self.assertIn("The judge's view", t)
        self.assertIn("### All units", texts[2])

    def test_no_view_drops_the_section(self):
        self.prep(json.dumps({"units": [unit(MEAN), unit(CLAMP)]}))
        self.assertNotIn("The judge's view", (self.out / "unit-1.md").read_text(encoding="utf-8"))

    def test_previous_answers_are_not_counted(self):
        self.prep()
        self.answer(1, MEAN)
        (self.out / "keep.txt").write_text("別の物\n", encoding="utf-8")
        self.prep()
        self.assertFalse((self.out / "answers" / "unit-1.json").exists())
        self.assertTrue((self.out / "keep.txt").exists())
        self.assertTrue((self.out / "answers").is_dir())
        self.assertEqual(sorted(p.name for p in self.out.glob("judge-verify-prompt-*.md")), ["judge-verify-prompt-1.md"])

    def test_answers_above_the_recorded_numbers_are_deleted_too(self):
        self.prep()   # 控えは番号 1・2
        self.answer(3, FMT)
        self.prep(judgment(unit(MEAN), unit(CLAMP), unit(FMT), unit("stats.py x: y")))   # 今回は 4 つ
        self.assertFalse((self.out / "answers" / "unit-3.json").exists())

    def test_without_a_record_answers_are_deleted_by_this_runs_count(self):
        self.answer(1, MEAN)
        self.answer(2, CLAMP)
        self.answer(3, FMT)
        self.assertFalse((self.out / "plan.json").exists())
        self.prep(judgment(unit(MEAN), unit(CLAMP)))
        self.assertEqual(sorted(p.name for p in (self.out / "answers").glob("unit-*.json")), ["unit-3.json"])

    def test_exception_in_prep_gives_not_run_and_keeps_the_judgment(self):
        (self.out / "judgment.json").write_text("判定\n", encoding="utf-8")
        shutil.rmtree(self.run.repo / ".git")   # git の外になり、作業ツリーの写しが取れず例外
        got = self.prep()
        self.assertIs(got["go"], False)
        self.assertIn("例外", got["reason"])
        self.assertEqual(self.notes()["units"], [])
        self.assertFalse((self.out / "plan.json").exists())
        self.assertEqual((self.out / "judgment.json").read_text(encoding="utf-8"), "判定\n")
        self.assertEqual(json.loads((self.out / "prep.json").read_text(encoding="utf-8"))["failed"], True)

    def test_stop_word_is_declared_once(self):
        import stopby
        self.assertEqual(self.steps.STOP, stopby.HEAD + "judge-verify")
        self.assertEqual(stopby.declare("judge-verify", "判定の裏取りの束ね役か下請けが作業ツリーを変えた"), self.steps.STOP)


class FinishCase(_Base):
    def setUp(self):
        super().setUp()
        self.assertIs(self.prep(judgment(unit(MEAN), unit(CLAMP)))["go"], True)

    def test_good_answers_are_merged_with_keys(self):
        self.answer(1, MEAN)
        self.answer(2, CLAMP, verdict="not_root", real_root=f"単位 1（{MEAN}）と同じ根")
        self.synergy({"why": "2 つの単位は同じ関数の群の取り違え", "duplicates": [{"units": [1, 2], "why": "同じ根の別の現れ"}],
                      "relations": [{"units": [1, 2], "why": "同じ行を触る", "place": "same"}],
                      "order": [{"first": 1, "then": 2, "why": "mean を先に直す"}]})
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["stop_reason"], done["reason"]), (True, "ok", "", ""))
        doc = self.notes()
        self.assertEqual([(u["key"], u["state"], u["verdict"]) for u in doc["units"]], [(MEAN, "checked", "root"), (CLAMP, "checked", "not_root")])
        self.assertNotIn("unit", doc["units"][0])
        self.assertEqual(doc["synergy"]["duplicates"], [{"units": [MEAN, CLAMP], "why": "同じ根の別の現れ"}])
        self.assertEqual(doc["synergy"]["relations"][0]["place"], "same")
        self.assertEqual(done["verify"]["path"], "verify.json")
        self.assertIn("  - 順番: " + MEAN + " → " + CLAMP + "（mean を先に直す）", done["report"])

    def test_verification_never_deletes_units(self):
        self.answer(2, CLAMP, verdict="not_root")
        self.synergy({"why": "短い"})
        done = self.finish()
        doc = self.notes()
        self.assertEqual([u["key"] for u in doc["units"]], [MEAN, CLAMP], "単位は消さない")
        self.assertTrue(any("答えのファイルが無い" in e for e in doc["units"][0]["errors"]))
        self.assertTrue(any("real_root" in e for e in doc["units"][1]["errors"]))
        self.assertEqual(doc["synergy"]["state"], "unverified")
        self.assertEqual((done["status"], done["reason"]), ("ok", "確かめられなかった物がある（単位 2 / 2・相乗り 確かめられなかった）"))

    def test_bad_missing_and_out_of_range_answers_are_unverified(self):
        self.answer(1, MEAN, unit=2)
        self.answer(2, CLAMP, verdict="maybe")
        self.synergy({"why": "単位 3 と単位 1 が重なる", "duplicates": [{"units": [1, 3], "why": "同じ根の別の現れ"}],
                      "relations": [{"units": [1, 1], "why": "同じ単位だけ", "place": "apart"}], "order": []})
        self.finish()
        doc = self.notes()
        self.assertEqual([u["state"] for u in doc["units"]], ["unverified", "unverified"])
        self.assertIn("$.unit: 1 でない（2）", doc["units"][0]["errors"])
        self.assertTrue(any("verdict" in e for e in doc["units"][1]["errors"]))
        self.assertIn("単位 3 は無い（単位は 1〜2）", doc["synergy"]["errors"])
        self.assertTrue(any("同じ単位だけを並べた行" in e for e in doc["synergy"]["errors"]))
        (self.out / "answers" / "unit-1.json").write_text("{壊れた", encoding="utf-8")
        self.finish()
        self.assertTrue(any("JSON として読めない" in e for e in self.notes()["units"][0]["errors"]))

    def test_tree_moved_returns_stop_reason(self):
        self.answer(1, MEAN)
        (self.run.repo / "stats.py").write_text("書き換えた\n", encoding="utf-8")
        done = self.finish()
        self.assertEqual((done["ok"], done["status"], done["stop_reason"]), (False, "failed", "works:judge-verify"))
        self.assertIn("作業ツリーを変えた", done["reason"])
        self.assertEqual(len(self.notes()["units"]), 2, "止めても申し送りは書く")

    def test_missing_tree_copy_counts_as_moved(self):
        (self.out / "tree.json").unlink()
        done = self.finish()
        self.assertEqual((done["status"], done["stop_reason"]), ("failed", "works:judge-verify"))
        self.assertIn("tree.json", done["reason"])

    def test_malformed_tree_copy_counts_as_moved(self):
        for raw in ('{"head": 1}', "[]", "{壊れた", json.dumps({"head": "x"})):
            with self.subTest(raw=raw):
                (self.out / "tree.json").write_text(raw, encoding="utf-8")
                done = self.finish()
                self.assertEqual((done["status"], done["stop_reason"]), ("failed", "works:judge-verify"))
                self.assertIn("tree.json", done["reason"])

    def test_finish_without_prep_record_writes_not_run(self):
        for name in ("plan.json", "verify.json", "prep.json"):
            (self.out / name).unlink()
        done = self.finish()
        self.assertEqual((done["ok"], done["status"]), (False, "failed"))
        self.assertEqual(self.notes(), {"units": [], "synergy": {"state": "unverified", "errors": ["判定の裏取りの支度が走らなかった（番号の控えが無い）"]}})
        self.assertEqual(done["report"], ["判定の単位の裏取り: 回さなかった（判定の裏取りの支度が走らなかった（番号の控えが無い））"])

    def test_answers_dir_falls_back_to_place(self):
        self.answer(1, MEAN)
        plan = json.loads((self.out / "plan.json").read_text(encoding="utf-8"))
        plan.pop("answers")
        (self.out / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        self.finish()
        self.assertEqual(self.notes()["units"][0]["state"], "checked")


if __name__ == "__main__":
    unittest.main()
