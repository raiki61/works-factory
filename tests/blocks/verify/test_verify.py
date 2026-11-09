"""判定の裏取りの block を、script を子のプロセスで回して確かめる（docs/design/verify.md の 7.2）。

prep → 台本の下請けとして答えのファイルを書く → finish と回し、返りの 6 欄と申し送りと報告の行を照らす。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

MEAN, CLAMP = "stats.py mean: 分母", "stats.py clamp: 上限"
JUDGMENT = json.dumps({"framing": "根は 1 つ", "units": [
    {"key": MEAN, "label": "block", "reason": "分母が違う"}, {"key": CLAMP, "label": "block", "reason": "上限が違う"}]}, ensure_ascii=False)
OK = {"verdict": "root", "evidence_found": True, "evidence": "stats.py:2 に分母が在る", "location_ok": True, "location": "stats.py:2",
      "why": "ここを直せば症状が消える"}


class RunCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "verify")
        (self.run.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def go(self, include=""):
        prep = self.run.script("prep", include, judgment=JUDGMENT, lang="")
        self.assertIs(prep["go"], True)
        place = self.run.artifacts.joinpath(*include.split("__")[:-1])
        answers = place / "answers"
        answers.mkdir(exist_ok=True)
        for n in (1, 2):
            (answers / f"unit-{n}.json").write_text(json.dumps({"unit": n, **OK}), encoding="utf-8")
        (answers / "synergy.json").write_text(json.dumps(
            {"why": "単位どうしを見て順番だけ在った", "duplicates": [], "relations": [],
             "order": [{"first": 1, "then": 2, "why": "mean を先に直す"}]}, ensure_ascii=False), encoding="utf-8")
        return place, self.run.script("finish", include)

    def test_prep_then_answers_then_finish(self):
        place, got = self.go()
        self.assertEqual(set(got), {"ok", "status", "stop_reason", "reason", "verify", "report"})
        self.assertEqual((got["ok"], got["status"], got["stop_reason"], got["reason"]), (True, "ok", "", ""))
        self.assertEqual(got["verify"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "verify.json"})
        doc = json.loads((place / "verify.json").read_text(encoding="utf-8"))
        self.assertEqual([u["state"] for u in doc["units"]], ["checked", "checked"])
        self.assertEqual(got["report"][1], f"  - 順番: {MEAN} → {CLAMP}（mean を先に直す）")

    def test_place_follows_the_include_path(self):
        place, got = self.go("judge__verify__prep")
        self.assertEqual(place, self.run.artifacts / "judge" / "verify")
        self.assertEqual(got["verify"]["path"], "judge/verify/verify.json")
        self.assertFalse((self.run.artifacts / "verify.json").exists())

    def test_script_failure_returns_the_fallback(self):
        got = self.run.script("prep", judgment="{壊れた", lang="")
        self.assertEqual(got["go"], False)
        self.assertTrue(got["reason"])


if __name__ == "__main__":
    unittest.main()
