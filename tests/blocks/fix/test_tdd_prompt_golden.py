"""振り分けと輪の指示の字の控え（golden。docs/plans/2026-10-24-fix-weapons.md の 11.6 の E2 の縛る試験「振り分けと輪の指示が、値の
組み立てを割る前と同じ字に組める」。割る前の字を控えて比べる）。

組の子の run の道どおり、script を子のプロセスで回す（intake → group-start → route-go → route-prep・route-step → orders →
tdd-prep・tdd-step。手本は test_group.py の GroupChildScriptsCase）。in-process の呼びも mock も使わない。単位は 2 つ（target-seed の
stats.py の mean と clamp）。組んだ指示の字を、run ごとに変わる字を印に替えてから、控えのファイル tdd_prompt_golden.json と比べる。

場面（控えの鍵）。run A は修正案の 1 つの項目に 2 つの単位が載る形（brief・together・named の段落が入る）で、方針・依頼・notes と run の
test_cmd の関門も置く。run B は項目が単位ごとに別の形（later・handoff が入る）:
- a1-route: 振り分けの 1 周目（route-prep）
- a2-route-rejected: 振り分けの返答を 1 度拒ませた後（route-prep。rejected）
- a3-test-new-unit: 2 つとも tdd にした後の最初の単位の test の段（tdd-prep。new_unit 真）
- a4-test-rejected: test の段の返答を 1 度拒ませた後（tdd-prep。同じ単位の続き。rejected）
- a5-fix-gated: 赤が通った後の fix の段（tdd-prep。test_cmd の関門 gate。名指しの試験 named は test の段が受かった後の fix の段から入る）
- b1-first-unit: 最初の単位の test の段（later）
- b2-second-unit-handoff: 最初の単位を緑にした後の 2 つ目の単位の test の段（handoff）

印に替える字（これ以外は 1 字も替えない）:
- 一時のフォルダの根（この run の tmp。実パスと resolve した物の両方）→ <TMP>
- リポジトリの根（kit.ROOT。借りた座の overlay のパスなど）→ <ROOT>
- 輪の置き場 <子の place>/tdd-<k> と <子の place>/w-tdd/tdd-<k>（次の段で輪が block weapon-tdd へ出ると後者になる）→ <LOOP>
- 子の place（<TMP>/child-art）→ <PLACE>
これで <TMP>・<ROOT>・<PLACE>・<LOOP> のほか、指示の本文は 1 字も替わらない（比べが空にならない守りとして、各場面の段落の印が字に在ることも見る）。

控えの書き出しは試験の実行の中ではしない。手で `python -m tests.blocks.fix.test_tdd_prompt_golden --write` と打つ。

次の段（輪を block weapon-tdd へ出す）で替えるのは LoopCase の loop_prep・loop_step（輪の段の prep・step をどの script で回すか）だけで、
控えのファイルは 1 字も変えずに通らなければならない。
"""
import json
import pathlib
import re
import subprocess
import sys
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import committed_copy
from tests.blocks import kit
from tests.blocks.fix import support, test_group as tg

ROOT = kit.ROOT
BLOCK = kit.BLOCKS / "fix"
GOLDEN = pathlib.Path(__file__).with_name("tdd_prompt_golden.json")
RUN = "wf-golden"
MEAN = tg.MEAN
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
MEAN_ID = "test_stats.py::TestStats::test_mean_of_two"
CLAMP_ID = "test_stats.py::TestStats::test_clamp_far_above"
GROUP = {"group_id": "g1", "unit_ids": [MEAN, CLAMP], "items": []}
JUDGMENT = {"units": [{"key": MEAN, "label": "block"}, {"key": CLAMP, "label": "block"}], "questions": []}
BOTH_TESTS = tg.NEW_TEST + '''
    def test_clamp_far_above(self):
        self.assertEqual(clamp(20, 0, 10), 10)
'''
MEAN_FIX = ("(len(xs) - 1)", "len(xs)")
CLAMP_FIX = ("    if x > hi:\n        return lo", "    if x > hi:\n        return hi")


def _fields(*items):
    """修正案の欄（planmarks.save の行）。items は (unit_keys, tests の id)"""
    return [{"unit_keys": keys, "route": "tdd", "route_why": "", "tests": [{"id": i, "red_kind": "assertion"} for i in ids],
             "rewrite_tests": [], "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py", "test_stats.py"],
             "out_of_scope": []} for keys, ids in items]


def _plan(*items):
    """修正案の役の返答の写し（board.PLAN_REPLY_FILE）"""
    return {"plan": [{"unit_keys": keys, "approach": f"{' と '.join(keys)} を直す", "adds": [], "removes": []} for keys, _ in items]}


class LoopCase(unittest.TestCase):
    """組の子の run を子のプロセスで回す助け。輪の段の prep・step を回す所は loop_prep・loop_step の 1 か所に閉じる"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self, prefix="works-fix-golden-")
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, tg.SEED)
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(support.SUITE, encoding="utf-8")
        self.parent = self.tmp / "parent-art"
        (self.parent / "groups").mkdir(parents=True)
        self.place = self.tmp / "child-art"
        self.place.mkdir()

    # ---- 子のプロセス
    def run_script(self, script, **inputs):
        env = hermetic.child_env()
        env.update({"ARTIFACTS_DIR": str(self.place), "WORKFLOW_ID": RUN, "WORKS_FACTORY_ROOT": str(ROOT),
                    "PYTHONDONTWRITEBYTECODE": "1", **{f"INPUTS_{k.upper()}": v for k, v in inputs.items()}})
        done = subprocess.run([sys.executable, str(BLOCK / "scripts" / f"{script}.py")], cwd=self.repo, env=support.variant_return(env),
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def route_prep(self):
        return self.run_script("route_prep")["prompt"]

    def route_step(self, reply):
        """振り分けの返答を受ける（済めば注文の node orders まで）"""
        out = self.run_script("route_step", reply=json.dumps(reply, ensure_ascii=False))
        if out["done"]:
            self.run_script("orders")
            started = json.loads((self.place / "tdd-start.json").read_text(encoding="utf-8"))
            out = {**out, "phase": json.loads(pathlib.Path(started["state_file"]).read_text(encoding="utf-8"))["phase"]}
        return out

    def loop_prep(self):
        """輪の段の指示を組む script（次の段で weapon-tdd の script に替わる所）。返り (指示, 新しい単位か)"""
        out = self.run_script("tdd_prep")
        return out["prompt"], out["new_unit"]

    def loop_step(self, reply):
        """輪の段の返答を受ける script（次の段で weapon-tdd の script に替わる所）"""
        return self.run_script("tdd_step", reply=json.dumps(reply, ensure_ascii=False))

    # ---- 置き方
    def start(self, plan_items, **values):
        """親の place に写しと修正案の欄・返答を置き、子の頭（intake → group-start → route-go）を回す"""
        import planmarks
        from src import runvals
        runvals.write(self.parent, {"tdd_suite": str(self.suite), "reuse_key": RUN, **values})
        tg._write(self.parent / "judgment.json", JUDGMENT)
        tg._write(self.parent / "baseline.json", {"cases": [], "exit": 1})
        from src import board
        tg._write(self.parent / board.PLAN_REPLY_FILE, _plan(*plan_items))
        (self.parent / board.NOTES_FILE).write_text("平均の直しは分母だけに留める\n", encoding="utf-8")
        planmarks.save(self.parent, 1, _fields(*plan_items))
        out = self.run_script("intake", mode="group", group=json.dumps(GROUP, ensure_ascii=False),
                              out_dir=str(self.parent / "groups"), from_tree="")
        self.assertTrue(out["ok"], out)
        self.assertTrue(self.run_script("group_start")["tdd"])
        self.assertTrue(self.run_script("route_go")["route"])

    def edit(self, name, *pairs, add=""):
        path = self.repo / name
        text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            self.assertIn(old, text)
            text = text.replace(old, new)
        if add:
            text = text.replace("\n\nif __name__", add + "\n\nif __name__")
        path.write_text(text, encoding="utf-8")

    def settle(self, text: str) -> str:
        """run ごとに変わる字を印に替える（docstring の一覧のとおり）"""
        place = re.escape(str(self.place))
        text = re.sub(rf"{place}/(?:w-tdd/)?tdd-\d+", "<LOOP>", text)
        text = text.replace(str(self.place), "<PLACE>")
        for tmp in dict.fromkeys([str(self.tmp), str(self.tmp.resolve())]):
            text = text.replace(tmp, "<TMP>")
        return text.replace(str(ROOT), "<ROOT>")

    # ---- 場面
    def scenes_a(self) -> dict:
        """run A: 1 つの項目に 2 つの単位。方針・依頼・notes・test_cmd の関門つき"""
        policy, request = self.tmp / "policy.md", self.tmp / "request.md"
        policy.write_text("- 平均は算術平均\n", encoding="utf-8")
        request.write_text("平均と clamp の直し\n", encoding="utf-8")
        self.start([([MEAN, CLAMP], [MEAN_ID, CLAMP_ID])], policy=str(policy), request_file=str(request), test_cmd="true")
        got = {"a1-route": self.route_prep()}
        self.assertFalse(self.route_step({"phase": "route", "units": []})["ok"])
        got["a2-route-rejected"] = self.route_prep()
        both = [{"unit_key": MEAN, "route": "tdd"}, {"unit_key": CLAMP, "route": "tdd"}]
        self.assertEqual(self.route_step({"phase": "route", "units": both})["phase"], "test")
        got["a3-test-new-unit"], new_unit = self.loop_prep()
        self.assertTrue(new_unit)
        reply = {"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID, CLAMP_ID]}
        self.assertFalse(self.loop_step(reply)["ok"])   # テストのファイルを書く前の返答は拒む
        got["a4-test-rejected"], new_unit = self.loop_prep()
        self.assertFalse(new_unit)
        self.edit("test_stats.py", add=BOTH_TESTS)
        self.assertEqual(self.loop_step(reply)["phase"], "fix")
        got["a5-fix-gated"], _ = self.loop_prep()
        return got

    def scenes_b(self) -> dict:
        """run B: 項目が単位ごとに別（項目 1 が mean・項目 2 が clamp）"""
        self.start([([MEAN], [MEAN_ID]), ([CLAMP], [CLAMP_ID])])
        both = [{"unit_key": MEAN, "route": "tdd"}, {"unit_key": CLAMP, "route": "tdd"}]
        self.assertEqual(self.route_step({"phase": "route", "units": both})["phase"], "test")
        got = {}
        got["b1-first-unit"], _ = self.loop_prep()
        self.edit("test_stats.py", add=tg.NEW_TEST)
        self.assertEqual(self.loop_step({"phase": "test", "unit_key": MEAN, "test_files": ["test_stats.py"], "tests": [MEAN_ID]})["phase"], "fix")
        self.edit("stats.py", MEAN_FIX)
        out = self.loop_step({"phase": "fix", "unit_key": MEAN, "files": ["stats.py"], "what": "分母を len(xs) にした"})
        self.assertEqual((out["ok"], out["done"], out["phase"]), (True, False, "test"), out)
        got["b2-second-unit-handoff"], new_unit = self.loop_prep()
        self.assertTrue(new_unit)
        return got


# 場面ごとに字に在るべき段落の印（控えが空や別の場面の字にすり替わっていない守り）
MARKS = {
    "a1-route": ["## The requirement (briefs)", "- 項目 1:", "## Units you owe a fix", "The policy document:", "The request file:"],
    "a2-route-rejected": ["## Why the machine rejected your previous answer", "## The requirement (briefs)"],
    "a3-test-new-unit": ["## The requirement (briefs)", "## Units to fix together with the current unit", f"- {CLAMP}",
                         "## The current unit"],
    "a4-test-rejected": ["## Why the machine rejected your previous answer", "## Units to fix together with the current unit"],
    "a5-fix-gated": ["After green the machine also runs the run's test_cmd (`true`)", "## Units to fix together with the current unit",
                     "- 名指しのテスト:", "## The requirement (briefs)"],
    "b1-first-unit": ["The later tdd units (do not touch them now):", CLAMP, "## The current unit"],
    "b2-second-unit-handoff": ["The earlier units' fixes are in the working tree (the green tree).", "直したファイル stats.py・緑にしたテスト", "## The current unit"],
}


class GoldenCase(LoopCase):
    def run_scenes(self, name):
        got = {k: self.settle(v) for k, v in getattr(self, name)().items()}
        self.collected = got
        return got

    def check(self, name):
        got = self.run_scenes(name)
        want = json.loads(GOLDEN.read_text(encoding="utf-8"))
        for key, text in got.items():
            with self.subTest(scene=key):
                for mark in MARKS[key]:
                    self.assertIn(mark, text, f"{key}: 段落の印が字に無い")
                    self.assertIn(mark, want[key], f"{key}: 段落の印が控えに無い")
                self.assertGreater(len(text), 2000, "印に替えた後に本文が残っている")
                if text != want[key]:
                    old, new = want[key].splitlines(), text.splitlines()
                    at = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
                    self.fail(f"{key}: 控えの字と違う（{at + 1} 行目から）\n控え: {old[at:at + 3]}\n今: {new[at:at + 3]}")

    def test_run_a_prompts_match_the_golden(self):
        self.check("scenes_a")

    def test_run_b_prompts_match_the_golden(self):
        self.check("scenes_b")



if __name__ == "__main__":
    if "--write" not in sys.argv:
        raise SystemExit("控えを書き出す時は --write を付ける。試験は python -m unittest で回す")
    out = {}
    for method in ("scenes_a", "scenes_b"):
        case = GoldenCase("test_run_a_prompts_match_the_golden")   # 試験の名は組み立てのための物（回すのは method の場面）
        case.setUp()
        try:
            out.update(case.run_scenes(method))
        finally:
            case.doCleanups()
    GOLDEN.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{GOLDEN} に {len(out)} 場面を書いた")
