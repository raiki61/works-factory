"""port excluded（並行 PR の確かめが外した hunk）と修正の受け付けの関門（docs/design/fix.md の 1.2・8.1。line の設計書の 8.2 の決め）:
修正の段の始めの木からの変更が外した hunk の行に触れた返答は、hunk を名指して拒む。触れなければ、この確かめでは拒まない"""
import json
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

KEY = "stats.py:2 mean"
JUDGMENT = json.dumps({"units": [{"key": KEY, "label": "block", "reason": "空の並びで 0 除算する"}], "questions": []})
GROUP = json.dumps({"group_id": "g1", "unit_ids": [KEY], "items": []})
SOURCE = "def mean(xs):\n    return sum(xs) / len(xs)\n\n\ndef total(xs):\n    return sum(xs)\n"
EXCLUDED = json.dumps({"node": "pr-check", "head": "", "excluded": [
    {"pr": 7, "file": "stats.py", "start": 5, "end": 6, "why": "PR 7 が同じ total を書き換える"}]})


def reply_for(files):
    return {"changes": [{"unit_key": KEY, "files": files, "what": "空の並びを先に返す",
                         "closure": {"mechanism": "0 除算", "fix_mechanism": "空を先に返す", "verified_how": "走らせた",
                                     "sites": [{"site": "mean", "red_seen": True, "path": "stats.py"}]},
                         "root_or_symptom": {"kind": "root", "why": "根を塞いだ"}, "bypass_tried": "空の並びを渡した",
                         "breaks": {"how": "grep mean", "result": "呼び元は動く"},
                         "precedent": {"verdict": "does_not_apply", "reason": "当たらない", "problem": "0 除算の守り",
                                       "source": "Python の文書"}}],
            "not_done": [], "fix_closure": {"status": "clean", "checked": "赤を見た"}, "mechanism_changed": False,
            "premise_drift": False, "gates_changed": False, "seams_changed": False, "security_surface_changed": False,
            "path_changed": False, "interactions": [], "wrote_refs": [], "plan_faces": []}


class ExcludedCase(unittest.TestCase):
    def started(self, excluded=EXCLUDED) -> kit.Run:
        run = kit.Run(self, "fix")
        (run.repo / "stats.py").write_text(SOURCE, encoding="utf-8")
        git(run.repo, "add", ".")
        git(run.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
        self.assertTrue(run.script("intake", mode="group", group=GROUP, judgment=JUDGMENT, excluded=excluded)["ok"])
        run.script("group_start")
        self.assertTrue(run.script("fix_prep")["go"])
        return run

    def edit(self, run, old, new):
        path = run.repo / "stats.py"
        path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_port_lands_in_values(self):
        run = self.started()
        doc = json.loads((run.artifacts / "values.json").read_text(encoding="utf-8"))
        self.assertEqual([(r["pr"], r["file"], r["start"], r["end"]) for r in doc["excluded"]], [(7, "stats.py", 5, 6)])

    def test_touching_an_excluded_hunk_is_rejected_naming_it(self):
        run = self.started()
        self.edit(run, "    return sum(xs)\n", "    return sum(xs) + 0\n")
        out = run.script("fix_accept", reply=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertFalse(out["ok"], out)
        self.assertIn("並行 PR #7 に回した hunk stats.py:5-6（PR 7 が同じ total を書き換える）を変えた", out["reason"])

    def test_change_outside_the_hunk_passes_this_check(self):
        run = self.started()
        self.edit(run, "    return sum(xs) / len(xs)\n", "    return sum(xs) / len(xs) if xs else 0\n")
        out = run.script("fix_accept", reply=json.dumps(reply_for(["stats.py"])), consulted="false")
        self.assertNotIn("並行 PR", out["reason"], out)

    def test_bare_rows_and_null_are_read(self):
        intake = kit.load("fix", "intake")
        rows = [{"pr": 1, "file": "a.py", "start": 1, "end": 2, "why": "w"}]
        self.assertEqual(intake.excluded_rows(rows), rows)
        self.assertEqual(intake.excluded_rows({"excluded": rows}), rows)
        self.assertEqual(intake.excluded_rows(None), [])


if __name__ == "__main__":
    unittest.main()
