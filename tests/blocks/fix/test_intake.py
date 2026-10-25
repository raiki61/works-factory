"""修正の block（workflows/fix/）の入口 intake の試験（docs/design/fix.md の 1.2・1.4・7 節の intake.py・14.2）。

script intake.py を子のプロセスで回し（始めの記録の無い使い捨ての run directory と git のリポジトリ。port の値だけを渡す）、
- 形ごとの必須（whole は judgment・group は group・out_dir の無い group は judgment も）を ok: false と「入力 <名>: …」の理由で返す
- 読めない port（壊れた JSON・形に合わない値・無いファイル・ほかの run の pointer・flag と choice の語）の理由
- place に書く intake.json と values.json（src/runvals.py）の中身
- reuse_key の既定がこの run の id（WORKFLOW_ID）
を照らす。src の関数（intake.read・intake.load・runvals.read・runvals.adopt）は kit.load で読んで直に呼ぶ。
"""
import json
import pathlib
import unittest

import yaml

from tests.blocks import kit

YAML_PATH = kit.BLOCKS / "fix" / "works-factory-fix.yaml"
JUDGMENT = {"units": [{"key": "A", "label": "block"}], "questions": []}
GROUP = {"group_id": "g1", "unit_ids": ["A"], "items": []}


def intake_format() -> dict:
    doc = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    return next(n for n in doc["nodes"] if n["id"] == "intake")["output_format"]


def _j(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class IntakeCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "fix")
        self.place = self.run.artifacts   # 単独の run の place は $ARTIFACTS_DIR
        kit.load("fix", "intake")
        from engine.schema import validate_schema
        self.validate = validate_schema
        self.fmt = intake_format()

    def intake(self, **inputs) -> dict:
        out = self.run.script("intake", **inputs)
        self.assertEqual(self.validate(out, self.fmt), [], out)
        return out

    def read(self, name):
        return json.loads((self.place / name).read_text(encoding="utf-8"))

    def write(self, rel, doc) -> pathlib.Path:
        path = self.place / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else _j(doc), encoding="utf-8")
        return path


class NeededCase(IntakeCase):
    """形ごとの必須（docs/design/fix.md の 7 節の intake.py）"""

    def test_whole_needs_the_judgment(self):
        out = self.intake(mode="whole")
        self.assertEqual(out, {"ok": False, "whole": True, "reason": "入力 judgment: whole の形には要る"})
        self.assertFalse((self.place / "intake.json").exists(), "読めない run は intake.json を書かない")
        self.assertFalse((self.place / "values.json").exists())

    def test_whole_with_the_judgment_is_ok(self):
        out = self.intake(mode="whole", judgment=_j(JUDGMENT))
        self.assertEqual(out, {"ok": True, "whole": True, "reason": ""})
        self.assertEqual(self.read("intake.json")["judgment"], JUDGMENT)

    def test_group_needs_the_group(self):
        out = self.intake(mode="group", judgment=_j(JUDGMENT))
        self.assertEqual(out, {"ok": False, "whole": False, "reason": "入力 group: group の形には要る"})

    def test_group_without_out_dir_needs_the_judgment(self):
        """単独の run の組（out_dir が空）は親の写しが無いので判定が要る"""
        out = self.intake(mode="group", group=_j(GROUP))
        self.assertEqual(out, {"ok": False, "whole": False, "reason": "入力 judgment: out_dir の無い group の形には要る"})

    def test_group_with_out_dir_reads_the_parent_and_needs_no_judgment(self):
        out = self.intake(mode="group", group=_j(GROUP), out_dir=str(self.place / "parent" / "groups"))
        self.assertEqual(out, {"ok": True, "whole": False, "reason": ""})
        doc = self.read("intake.json")
        self.assertIsNone(doc["judgment"])
        self.assertEqual((doc["group"], doc["out_dir"]), (GROUP, str(self.place / "parent" / "groups")))

    def test_mode_defaults_to_group(self):
        """mode が空（YAML の既定 group と同じ）は組の形"""
        out = self.intake(group=_j(GROUP), judgment=_j(JUDGMENT))
        self.assertEqual(out, {"ok": True, "whole": False, "reason": ""})
        self.assertEqual(self.read("intake.json")["mode"], "group")

    def test_whole_reads_no_group(self):
        """whole の形は group を要らない（空でよい）"""
        out = self.intake(mode="whole", judgment=_j(JUDGMENT))
        self.assertTrue(out["ok"])
        self.assertIsNone(self.read("intake.json")["group"])


class UnreadableCase(IntakeCase):
    """読めない port は落ちずに ok: false と「入力 <名>: …」の理由（world の 9.1 の 3）"""

    def assert_refused(self, name, out, *parts):
        self.assertFalse(out["ok"], out)
        self.assertTrue(out["reason"].startswith(f"入力 {name}: "), out["reason"])
        for part in parts:
            self.assertIn(part, out["reason"])
        self.assertFalse((self.place / "intake.json").exists())

    def test_unknown_mode(self):
        out = self.intake(mode="both", judgment=_j(JUDGMENT))
        self.assert_refused("mode", out, "whole|group")
        self.assertFalse(out["whole"])

    def test_unknown_routes(self):
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), routes="spec")
        self.assert_refused("routes", out, "auto|plan")

    def test_broken_json(self):
        out = self.intake(mode="whole", judgment='{"units": [')
        self.assert_refused("judgment", out)
        self.assertTrue(out["whole"], "形は mode の字のまま返す")

    def test_json_out_of_its_shape(self):
        out = self.intake(mode="whole", judgment=_j({"questions": []}))
        self.assert_refused("judgment", out, "judgment.schema.json")
        out = self.intake(mode="group", judgment=_j(JUDGMENT), group=_j({"group_id": "", "unit_ids": ["A"]}))
        self.assert_refused("group", out, "group.schema.json")
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), skip_rerun=_j([""]))
        self.assert_refused("skip_rerun", out, "skip-rerun.schema.json")

    def test_json_file_that_is_missing_or_broken(self):
        out = self.intake(mode="whole", judgment=str(self.place / "no-such.json"))
        self.assert_refused("judgment", out, "no-such.json")
        self.write("in/broken.json", '{"units": [')
        out = self.intake(mode="whole", judgment=self.run.pointer("in/broken.json"))
        self.assert_refused("judgment", out, "broken.json")

    def test_pointer_of_another_run(self):
        self.write("in/judgment.json", JUDGMENT)
        other = _j({"type": "archon_artifact", "run_id": "run-other", "path": "in/judgment.json"})
        out = self.intake(mode="whole", judgment=other)
        self.assert_refused("judgment", out, "run-other")

    def test_file_port_that_is_missing(self):
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), policy=str(self.place / "no-policy.md"))
        self.assert_refused("policy", out, "no-policy.md")
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), baseline='{"cases": []}')
        self.assert_refused("baseline", out)

    def test_flag_word(self):
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), unattended="yes")
        self.assert_refused("unattended", out, "true か false")
        out = self.intake(mode="whole", judgment=_j(JUDGMENT), parallel="1")
        self.assert_refused("parallel", out, "true か false")


class ValuesCase(IntakeCase):
    """place の intake.json と values.json（docs/design/fix.md の 1.4）"""

    def full_inputs(self):
        self.policy = self.write("in/policy.md", "- 方針\n")
        self.request = self.write("in/request.json", [{"where": "stats.py", "text": "直して"}])
        self.ripple = self.write("in/ripple.json", {"items": [{"item": 1, "unit_keys": ["A"]}], "overlaps": []})
        self.baseline = self.write("in/baseline.json", {"suite": "", "test_cmd": "", "rev": "x", "cases": [], "exit": 0})
        self.write("in/judgment.json", JUDGMENT)
        return {"mode": "whole", "judgment": self.run.pointer("in/judgment.json"), "plan": _j({"round": 1, "fields": [{"allowed_paths": ["**"], "out_of_scope": []}]}),
                "fix_plan": _j({"plan": [{"unit_keys": ["A"]}]}), "answer_ties": _j({"rounds": {}}),
                "materials": _j({"ci": {"status": "not_run"}}), "skip_rerun": _j(["A"]),
                "answers": _j({"decision": "continue", "text": "そのまま", "asked": []}),
                "request_answers": _j([{"q": "分母は", "a": "len(xs)"}]), "plan_review": _j({"faces": [], "shrink": []}),
                "only_items": _j([1]), "ripple": str(self.ripple), "baseline": self.run.pointer("in/baseline.json"),
                "policy": str(self.policy), "request": str(self.request), "unattended": "true", "parallel": "false",
                "notes": "  申し送り\n", "test_cmd": " python3 -m unittest ", "tdd_suite": " /x/suite.py ",
                "reuse_dir": " /x/reuse ", "reuse_key": " run-first ", "user_env_dir": " /x/env ", "from_tree": "",
                "out_dir": "", "lang": " ja "}

    def test_values_json_holds_the_run_values(self):
        self.intake(**self.full_inputs())
        self.assertEqual(self.read("values.json"), {
            "tdd_suite": "/x/suite.py", "test_cmd": " python3 -m unittest ", "reuse_key": "run-first", "reuse_dir": "/x/reuse",
            "user_env_dir": "/x/env", "lang": "ja", "policy": str(self.policy), "request_file": str(self.request),
            "answers": [{"q": "分母は", "a": "len(xs)"}], "unattended": True, "parallel": False, "skip_rerun": ["A"],
            "excluded": [], "routes": "auto", "suite_made": False})

    def test_routes_reach_the_values(self):
        """入力 routes（docs/design/spec-driven.md の 7 章の 1）: 空は auto、plan は values.json に運ばれ、組の子も同じ値を読む"""
        self.intake(mode="whole", judgment=_j(JUDGMENT), routes="plan")
        self.assertEqual((self.read("intake.json")["routes"], self.read("values.json")["routes"]), ("plan", "plan"))

    def test_no_start_record_copy_is_written(self):
        """lib の conflict は依頼のファイルを値で受けるので、始めの記録の形の写し r1/start.json は置かない"""
        self.intake(**self.full_inputs())
        self.assertFalse((self.place / "r1" / "start.json").exists())

    def test_intake_json_holds_what_it_read(self):
        """json の port は値（pointer・パスの先を開いた物）、file の port は字のパス、flag は真偽、text は前後の空白を落とす
        （test_cmd と notes は字のまま）"""
        self.intake(**self.full_inputs())
        doc = self.read("intake.json")
        self.assertEqual(doc["judgment"], JUDGMENT)
        self.assertEqual((doc["plan"], doc["only_items"], doc["skip_rerun"]), ({"round": 1, "fields": [{"allowed_paths": ["**"], "out_of_scope": []}]}, [1], ["A"]))
        self.assertEqual((doc["ripple"], doc["baseline"], doc["policy"], doc["request"]),
                         (str(self.ripple), str(self.place / "in" / "baseline.json"), str(self.policy), str(self.request)))
        self.assertEqual((doc["unattended"], doc["parallel"]), (True, False))
        self.assertEqual((doc["notes"], doc["test_cmd"], doc["tdd_suite"], doc["lang"]),
                         ("  申し送り\n", " python3 -m unittest ", "/x/suite.py", "ja"))

    def test_blank_ports_read_as_their_defaults(self):
        """空の字は渡されていない（既定）と読む。json の null も値の null"""
        self.intake(mode="whole", judgment=_j(JUDGMENT), answer_ties="null", materials="")
        doc = self.read("intake.json")
        self.assertEqual({k: doc[k] for k in ("plan", "fix_plan", "answer_ties", "materials", "answers", "plan_review", "prior",
                                              "group", "skip_rerun", "request_answers", "only_items")},
                         {"plan": None, "fix_plan": None, "answer_ties": None, "materials": None, "answers": None,
                          "plan_review": None, "prior": None, "group": None, "skip_rerun": [], "request_answers": [],
                          "only_items": []})
        self.assertEqual({k: doc[k] for k in ("ripple", "baseline", "policy", "request")},
                         {"ripple": "", "baseline": "", "policy": "", "request": ""})
        self.assertEqual((doc["unattended"], doc["parallel"]), (False, True))
        values = self.read("values.json")
        self.assertEqual((values["request_file"], values["answers"], values["unattended"], values["parallel"]), ("", [], False, True))

    def test_reuse_key_defaults_to_the_run_id(self):
        self.intake(mode="whole", judgment=_j(JUDGMENT))
        self.assertEqual(self.read("values.json")["reuse_key"], kit.RUN_ID)
        self.intake(mode="whole", judgment=_j(JUDGMENT), reuse_key="  ")
        self.assertEqual(self.read("values.json")["reuse_key"], kit.RUN_ID, "空白だけも空")
        self.assertEqual(self.read("intake.json")["reuse_key"], "", "intake.json は読んだ字のまま")
        self.intake(mode="whole", judgment=_j(JUDGMENT), reuse_key="run-first")
        self.assertEqual(self.read("values.json")["reuse_key"], "run-first")

    def test_place_is_not_cleared(self):
        """place は作るだけで消さない（前の node の物・resume の前の物を残す）"""
        keep = self.write("groups/g1/result.json", {"group_id": "g1"})
        self.intake(mode="whole", judgment=_j(JUDGMENT))
        self.assertTrue(keep.is_file())

    def test_include_place(self):
        """include の中の intake は include の道の place に書く"""
        out = self.run.script("intake", include="line__fix__intake", mode="whole", judgment=_j(JUDGMENT))
        self.assertTrue(out["ok"], out)
        self.assertTrue((self.place / "line" / "fix" / "intake.json").is_file())
        self.assertFalse((self.place / "intake.json").exists())


class SourceCase(unittest.TestCase):
    """src/intake.py と src/runvals.py を直に呼ぶ"""

    def setUp(self):
        self.intake = kit.load("fix", "intake")
        self.runvals = kit.load("fix", "runvals")
        self.run = kit.Run(self, "fix")

    def test_read_raises_with_the_port_name(self):
        with self.run.env():
            with self.assertRaisesRegex(ValueError, r"^入力 materials: "):
                self.intake.read({"mode": "whole", "judgment": _j(JUDGMENT), "materials": "[1"})

    def test_every_port_of_the_yaml_is_read(self):
        """YAML の inputs の名と、intake.read が読む名が同じ（足した port を読み忘れない）"""
        doc = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(self.intake.NAMES), set(doc["inputs"]))
        with self.run.env():
            got = self.intake.read({"mode": "whole", "judgment": _j(JUDGMENT)})
        self.assertEqual(set(got), set(doc["inputs"]))

    def test_load_without_intake_says_so(self):
        with self.assertRaisesRegex(ValueError, "intake が走らなかった"):
            self.intake.load(self.run.artifacts)

    def test_runvals_read_fills_defaults(self):
        place = self.run.artifacts
        self.assertEqual(self.runvals.read(place), self.runvals.DEFAULTS)
        (place / "values.json").write_text(_j({"test_cmd": "make test"}), encoding="utf-8")
        self.assertEqual(self.runvals.read(place), {**self.runvals.DEFAULTS, "test_cmd": "make test"})
        (place / "values.json").write_text("[", encoding="utf-8")
        self.assertEqual(self.runvals.read(place), self.runvals.DEFAULTS)

    def test_runvals_adopt_copies_the_parent(self):
        """組の子は親の values.json を写す。親に無ければ子の物のまま"""
        parent, child = self.run.artifacts / "parent", self.run.artifacts / "child"
        parent.mkdir()
        child.mkdir()
        mine = self.runvals.write(child, {"test_cmd": "child"})
        self.assertEqual(self.runvals.adopt(parent, child), mine)
        theirs = self.runvals.write(parent, {"test_cmd": "parent", "request_file": "/r.md", "answers": [{"a": 1}]})
        self.assertEqual(self.runvals.adopt(parent, child), theirs)
        self.assertFalse((child / "r1" / "start.json").exists())



class GateAsksCase(unittest.TestCase):
    """P241: 修正の置き場の判定の写しと関所の答え（answers.json の {decision, text, asked}）から引く、答えで戻る単位と外れる単位
    （元 lib/tests/test_fix_seams.py の GateAsksCase。入口が置く写し judgment.json・answers.json を board が読む）"""

    FORK = {"key": "q1", "kind": "fork", "status": "held", "origin": "u1", "options": ["a", "b"], "reason": "割れる"}

    def setUp(self):
        self.run = kit.Run(self, "fix")
        self.place = self.run.artifacts
        self.board = kit.load("fix", "board")

    def put(self, answers):
        (self.place / self.board.JUDGMENT_FILE).write_text(
            _j({"units": [{"key": "u1", "label": "block"}], "questions": [self.FORK]}), encoding="utf-8")
        (self.place / self.board.ANSWERS_FILE).write_text(_j(answers), encoding="utf-8")

    def test_continue_returns_the_fork_origin(self):
        import gatemarks
        self.put({"decision": "approve", "text": "", "asked": [gatemarks.ask_text(self.FORK)]})
        self.assertEqual(self.board.gate_asks(self.place), ({}, {"u1"}))
        self.assertEqual(self.board.group_owed(self.place), ["u1"])
        self.put({"decision": "approve", "text": "", "asked": []})
        withheld, back = self.board.gate_asks(self.place)
        self.assertEqual((set(withheld), back, self.board.group_owed(self.place)), ({"u1"}, set(), []))


if __name__ == "__main__":
    unittest.main()
