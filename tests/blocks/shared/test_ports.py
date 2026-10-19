"""blocks/.shared/ports.py の口（docs/design/README.md の 4 節）: 入力の 3 通りの形・読めない時は理由を名指して落ちる・place は
include の道で分かれる・pointer は place の中を指す"""
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

from tests.bin import hermetic
from tests.blocks import kit

sys.dont_write_bytecode = True
sys.path.insert(0, str(kit.SHARED))
import ports  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.art = self.tmp / "art"
        self.art.mkdir()
        self.enterContext(mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(self.art), "WORKFLOW_ID": "r1"}))
        os.environ.pop("ARCHON_NODE_EXECUTION", None)
        here = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, here)

    def ptr(self, rel, run_id="r1"):
        return json.dumps({"type": "archon_artifact", "run_id": run_id, "path": rel})


class ScalarCase(Base):
    def test_text_flag_choice(self):
        self.assertEqual(ports.text(None), "")
        self.assertEqual(ports.text("a b"), "a b")
        self.assertIs(ports.flag("true"), True)
        self.assertIs(ports.flag("false"), False)
        for bad in ("", "yes", "True"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "true か false"):
                ports.flag(bad)
        self.assertEqual(ports.choice("off", ("on", "off")), "off")
        with self.assertRaisesRegex(ValueError, "on\\|off"):
            ports.choice("maybe", ("on", "off"))


class JsonCase(Base):
    def test_three_forms_give_the_same_value(self):
        value = [{"where": "README", "text": "x"}]
        (self.art / "req.json").write_text(json.dumps(value), encoding="utf-8")
        (self.tmp / "local.json").write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(ports.json(json.dumps(value)), value)
        self.assertEqual(ports.json(self.ptr("req.json")), value)
        self.assertEqual(ports.json(str(self.tmp / "local.json")), value)
        self.assertEqual(ports.json("local.json"), value, "作業ツリーからの相対のパス")

    def test_unreadable_is_named_not_emptied(self):
        cases = {"": "空", "absent.json": "absent.json が無い", self.ptr("req.json", run_id="other"): "ほかの run",
                 self.ptr("../x.json"): "相対"}
        (self.tmp / "broken.json").write_text("{", encoding="utf-8")
        cases["broken.json"] = "JSON として読めない"
        for raw, word in cases.items():
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, word):
                ports.json(raw)

    def test_schema_is_read_from_the_caller_block(self):
        """形のファイルは呼んだ block の schemas/ から引く。呼び手が block の外なら名指して落ちる（block の中からの呼びは
        tests/blocks/world の IntakeCase）"""
        with self.assertRaisesRegex(ValueError, "block の中に無い"):
            ports.json("[]", "means.schema.json")

    def test_unknown_schema_keywords_are_named(self):
        """照らしが読まない語（anyOf・oneOf・format…）を持つ形は、黙って効かないので拒む。欄の名は数えない"""
        shape = {"type": "object", "properties": {"anyOf": {"type": "string"}, "x": {"type": "string", "format": "uri"}},
                 "items": {"oneOf": []}, "anyOf": []}
        self.assertEqual(sorted(ports.unknown_keywords(shape)), ["$.anyOf", "$.items.oneOf", "$.properties.x.format"])
        shared = self.tmp / "shared"
        (shared / "schemas").mkdir(parents=True)
        (shared / "schemas" / "bad.schema.json").write_text(json.dumps({"type": "array", "anyOf": []}), encoding="utf-8")
        with mock.patch.object(ports, "SHARED", shared), self.assertRaisesRegex(ValueError, r"知らない語 \['\$\.anyOf'\]"):
            ports.json("[]", "shared:bad.schema.json")

    def test_file_form(self):
        (self.art / "a.txt").write_text("x", encoding="utf-8")
        self.assertEqual(ports.file(self.ptr("a.txt")), self.art / "a.txt")
        self.assertIsNone(ports.file(""))
        self.assertIsNone(ports.file("null"))
        with self.assertRaisesRegex(ValueError, "無い"):
            ports.file("nope.txt")


class PlaceCase(Base):
    def at(self, path):
        os.environ["ARCHON_NODE_EXECUTION"] = json.dumps({"path": path})
        return ports.place()

    def test_include_path_splits_the_place(self):
        self.assertEqual(ports.place(), self.art, "単独の run は run directory の根")
        self.assertEqual(self.at("intake"), self.art)
        self.assertEqual(self.at("world__intake"), self.art / "world")
        self.assertEqual(self.at("judge__world__intake"), self.art / "judge" / "world")
        self.assertEqual(self.at("world__world-classes-loop.world-classes-prep"), self.art / "world", "include の中の loop の本体")
        self.assertEqual(self.at("plan-rounds.plan__intake"), self.art / "plan", "loop の本体の中の include")
        self.assertTrue((self.art / "judge" / "world").is_dir())

    def test_broken_execution_record_is_refused(self):
        os.environ["ARCHON_NODE_EXECUTION"] = "{not json"
        with self.assertRaisesRegex(ValueError, "ARCHON_NODE_EXECUTION が JSON でない"):
            ports.place()

    def test_pointer_points_inside_the_run(self):
        folder = self.at("world__finish")
        (folder / "rows.jsonl").write_text("x\n", encoding="utf-8")
        self.assertEqual(ports.pointer(folder / "rows.jsonl"), {"type": "archon_artifact", "run_id": "r1", "path": "world/rows.jsonl"})
        with self.assertRaises(ValueError):
            ports.pointer(self.tmp / "outside.txt")


class HelperCase(Base):
    def test_parsed_and_picked(self):
        self.assertIsNone(ports.parsed(""))
        self.assertIsNone(ports.parsed("null"))
        self.assertEqual(ports.parsed('{"a": 1}'), {"a": 1})
        got = ports.picked('{"a": 1, "b": 2}', ("a",), optional=("c",))
        self.assertEqual(dict(got), {"a": 1, "c": None}, "optional の欄は無ければ None")
        with self.assertRaisesRegex(KeyError, "宣言の外"):
            got["b"]
        with self.assertRaisesRegex(KeyError, r"欄 \['c'\] が無い"):
            ports.picked('{"a": 1}', ("a", "c"))
        self.assertIsNone(ports.picked("null", ("a",)))

    def test_runner_names_match_the_boundary(self):
        """workflows/.shared/boundary.py と同じ約束の写し（組み込みで boundary.py を消すまで突き合わせる）"""
        runner = hermetic.runner_vars()
        self.assertEqual(ports.RUNNER_PREFIXES, tuple(runner["RUNNER_PREFIXES"]))
        self.assertEqual(ports.RUNNER_NAMES, frozenset(runner["RUNNER_NAMES"]))
        boundary = (kit.ROOT / "workflows" / ".shared" / "boundary.py").read_text(encoding="utf-8")
        self.assertIn(f'RUNTIME_COPY = "{ports.RUNTIME_COPY}"', boundary)
        self.assertIn(f'SUITE_KEEP_ENV = "{ports.SUITE_KEEP_ENV}"', boundary)
        self.assertIn(f'USER_ENV_RAN_DIR = "{ports.USER_ENV_RAN_DIR}"', boundary)

    def test_drop_runner_env_and_suite_keep(self):
        with mock.patch.dict(os.environ, {"INPUTS_X": "1", "LOG_DIR": "/l", ports.SUITE_KEEP_ENV: "/k"}):
            self.assertEqual(ports.suite_keep(), pathlib.Path("/k"))
            ports.drop_runner_env("/marks")
            self.assertNotIn("INPUTS_X", os.environ)
            self.assertNotIn("ARTIFACTS_DIR", os.environ)
            self.assertEqual(os.environ[ports.USER_ENV_RAN_DIR], "/marks")
            os.environ["ARTIFACTS_DIR"] = str(self.art)
            os.environ["WORKFLOW_ID"] = "r1"

    def test_polyfill_reads_the_shared_parts(self):
        self.assertIsNone(ports.polyfill("skip_value").parsed("null"))
        with self.assertRaisesRegex(ValueError, "無い"):
            ports.polyfill("absent")


class RunCase(Base):
    def test_run_turns_errors_into_the_fallback(self):
        with mock.patch("builtins.print") as printed:
            ports.run(lambda: 1 / 0, lambda why: {"why": why})
        self.assertIn("ZeroDivisionError", printed.call_args_list[-1].args[0])

    def test_returns_refuses_nan(self):
        with self.assertRaises(ValueError):
            ports.returns({"x": float("nan")})


if __name__ == "__main__":
    unittest.main()
