"""workflows/.shared/ports.py の口（docs/design/README.md の 4 節）: 入力の 3 通りの形・読めない時は理由を名指して落ちる・place は
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
    def setUp(self):
        super().setUp()
        self.shared = self.tmp / "shared"
        (self.shared / "schemas").mkdir(parents=True)
        self.enterContext(mock.patch.object(ports, "SHARED", self.shared))
        self.shape("rows.schema.json", {"type": "array", "items": {"type": "object", "properties": {"where": {"type": "string"}}}})

    def shape(self, name, shape):
        (self.shared / "schemas" / name).write_text(json.dumps(shape), encoding="utf-8")

    def test_three_forms_give_the_same_value(self):
        value = [{"where": "README", "text": "x"}]
        (self.art / "req.json").write_text(json.dumps(value), encoding="utf-8")
        (self.tmp / "local.json").write_text(json.dumps(value), encoding="utf-8")
        for raw in (json.dumps(value), self.ptr("req.json"), str(self.tmp / "local.json"), "local.json"):
            with self.subTest(raw=raw):
                self.assertEqual(ports.json(raw, "shared:rows.schema.json"), value)

    def test_unreadable_is_named_not_emptied(self):
        cases = {"": "空", "absent.json": "absent.json が無い", self.ptr("req.json", run_id="other"): "ほかの run",
                 self.ptr("../x.json"): "相対"}
        (self.tmp / "broken.json").write_text("{", encoding="utf-8")
        cases["broken.json"] = "JSON として読めない"
        for raw, word in cases.items():
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, word):
                ports.json(raw, "shared:rows.schema.json")

    def test_off_shape_value_is_a_shape_error_holding_the_value(self):
        """形に合わない値は ShapeError（読めない入力の ValueError と分ける）で、読んだ値を持つ"""
        with self.assertRaises(ports.ShapeError) as caught:
            ports.json('[{"where": 3}]', "shared:rows.schema.json")
        self.assertEqual(caught.exception.value, [{"where": 3}])
        self.assertIn("$[0].where", str(caught.exception))

    def test_schema_is_read_from_the_caller_block(self):
        """形のファイルは呼んだ block の schemas/ から引く。呼び手が block の外なら名指して落ちる（block の中からの呼びは
        tests/blocks/world の IntakeCase）"""
        with self.assertRaisesRegex(ValueError, "block の中に無い"):
            ports.json("[]", "means.schema.json")

    def test_unknown_schema_keywords_are_named(self):
        """照らしが読まない語（anyOf・oneOf・format…）を持つ形は、黙って効かないので拒む。欄の名は数えない。知らない語を開きより先に見る"""
        shape = {"type": "object", "properties": {"anyOf": {"type": "string"}, "x": {"type": "string", "format": "uri"}},
                 "items": {"oneOf": []}, "anyOf": []}
        self.assertEqual(sorted(ports.unknown_keywords(shape)), ["$.anyOf", "$.items.oneOf", "$.properties.x.format"])
        self.shape("bad.schema.json", {"type": "array", "anyOf": []})
        with self.assertRaisesRegex(ValueError, r"知らない語 \['\$\.anyOf'\]"):
            ports.json("[]", "shared:bad.schema.json")

    def test_open_schema_is_refused(self):
        """中身を宣言しない形（properties の無い object・items の無い array・型の無い所）は、何でも通すので形のファイルごと拒む"""
        cases = {"object": {"type": "object"}, "empty-properties": {"type": "object", "properties": {}},
                 "array": {"type": "array"}, "untyped-item": {"type": "array", "items": {}},
                 "deep": {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": ["object", "null"]}}}},
                 "true-extra": {"type": "object", "additionalProperties": True},
                 "shaped-extra": {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": {"type": "string"}}}
        for name, shape in cases.items():
            with self.subTest(name):
                self.assertTrue(ports.open_shapes(shape))
                self.shape(f"{name}.schema.json", shape)
                with self.assertRaisesRegex(ValueError, "中身を宣言しない"):
                    ports.json("{}", f"shared:{name}.schema.json")

    def test_declared_any_is_not_open(self):
        """閉じは照らしが読む語だけ: properties・空でない patternProperties・additionalProperties: false・items・enum・const。
        6 つの型を全部書いた所は「何でも受ける」の明示"""
        closed = [{"type": "object", "properties": {"a": {"type": "string"}}},
                  {"type": "object", "patternProperties": {"^.+$": {"type": "integer"}}},
                  {"type": "object", "additionalProperties": False},
                  {"type": "array", "items": {"type": "string"}},
                  {"enum": ["a", "b"]}, {"const": 1},
                  {"type": ["object", "array", "string", "number", "boolean", "null"]}]
        for shape in closed:
            with self.subTest(shape):
                self.assertEqual(ports.open_shapes(shape), [])

    def test_named_sub_shape_is_checked(self):
        """description の json(<名>) は所が運ぶ値の形: 照らしは名の形に置き換えてから 1 度で当てる。pointer の所の名は先のファイルの形で、
        値は pointer のまま照らす"""
        self.shape("record.schema.json", {"type": "object", "properties": {"round": {"type": "integer"}}, "additionalProperties": False})
        self.shape("prior.schema.json", {"type": "object", "properties": {
            "record": {"type": ["object", "null"], "description": "json(shared:record.schema.json): 記録"},
            "file": {"type": "object", "description": "json(shared:record.schema.json): 記録のファイル",
                     "properties": {"type": {"const": "archon_artifact"}, "run_id": {"type": "string"}, "path": {"type": "string"}}}}})
        ptr = {"type": "archon_artifact", "run_id": "r1", "path": "x"}
        self.assertEqual(ports.json(json.dumps({"record": {"round": 1}, "file": ptr}), "shared:prior.schema.json")["record"], {"round": 1})
        ports.json(json.dumps({"record": None}), "shared:prior.schema.json")
        with self.assertRaisesRegex(ports.ShapeError, r"知らない欄 'extra'"):
            ports.json(json.dumps({"record": {"round": 1, "extra": 1}}), "shared:prior.schema.json")

    def test_path_text_names_the_file_it_carries(self):
        """型が string だけの所の json(<名>) は、パスの字が運ぶファイルの形（値の形に置き換えない。読み手が file で開いて照らす）"""
        self.shape("record.schema.json", {"type": "object", "properties": {"round": {"type": "integer"}}})
        self.shape("carry.schema.json", {"type": "object", "properties": {
            "request": {"type": "string", "description": "json(shared:record.schema.json): 依頼のファイルのパス"}}})
        self.assertTrue(ports.carries_file({"type": "string"}))
        self.assertEqual(ports.json('{"request": "/tmp/r.json"}', "shared:carry.schema.json"), {"request": "/tmp/r.json"})

    def test_named_shape_missing_or_open_is_open(self):
        self.shape("open.schema.json", {"type": "object"})
        for name in ("shared:absent.schema.json", "shared:open.schema.json"):
            with self.subTest(name):
                self.assertTrue(ports.open_shapes({"type": "object", "description": f"json({name}): x"}))

    def test_form_of_is_the_one_home_of_the_form_words(self):
        self.assertEqual(ports.form_of("json(shared:a.schema.json): 意味"), ("json", "shared:a.schema.json"))
        self.assertEqual(ports.form_of("jsonl(lib:row.schema.json): 行"), ("jsonl", "lib:row.schema.json"))
        self.assertEqual(ports.form_of("choice(on|off): x"), ("choice", "on|off"))
        self.assertEqual(ports.form_of("file"), ("file", None))
        for bad in ("files: x", "json(a b): x", "なにか", None):
            with self.subTest(bad):
                self.assertIsNone(ports.form_of(bad))

    def test_pointer_shape_has_two_spellings_and_one_judge(self):
        for kind in ({"const": "archon_artifact"}, {"type": "string", "enum": ["archon_artifact"]}):
            self.assertTrue(ports.is_pointer_shape({"type": "object", "properties": {"type": kind}}))
        self.assertFalse(ports.is_pointer_shape({"type": "object", "properties": {"type": {"type": "string"}}}))


class FileCase(JsonCase):
    def test_file_form(self):
        (self.art / "a.txt").write_text("x", encoding="utf-8")
        self.assertEqual(ports.file(self.ptr("a.txt"), "file"), self.art / "a.txt")
        self.assertIsNone(ports.file("", "file"))
        self.assertIsNone(ports.file("null", "file"))
        with self.assertRaisesRegex(ValueError, "無い"):
            ports.file("nope.txt", "file")

    def test_json_file_is_checked_and_its_path_returned(self):
        (self.art / "rows.json").write_text('[{"where": "a"}]', encoding="utf-8")
        self.assertEqual(ports.file(self.ptr("rows.json"), "json(shared:rows.schema.json)"), self.art / "rows.json")
        (self.art / "bad.json").write_text('[{"where": 1}]', encoding="utf-8")
        with self.assertRaises(ports.ShapeError):
            ports.file(self.ptr("bad.json"), "json(shared:rows.schema.json)")

    def test_json_file_is_not_carried_as_a_text_document(self):
        """form file は字の文書: JSON のファイルを形を名指さずに運ぶ道を口が塞ぐ（読みも指しも）"""
        for name in ("x.json", "x.jsonl"):
            (self.art / name).write_text("{}", encoding="utf-8")
            with self.subTest(name), self.assertRaisesRegex(ValueError, "form file で運ばない"):
                ports.file(self.ptr(name), "file")
            with self.subTest(name), self.assertRaisesRegex(ValueError, "form file で運ばない"):
                ports.pointer(self.art / name, "file")

    def test_jsonl_rows_are_checked_one_by_one(self):
        self.shape("row.schema.json", {"type": "object", "properties": {"n": {"type": "integer"}}})
        (self.art / "rows.jsonl").write_text('{"n": 1}\n\n{"n": "x"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ports.ShapeError, "2 行目"):
            ports.file(self.ptr("rows.jsonl"), "jsonl(shared:row.schema.json)")

    def test_pointer_checks_what_it_points_at(self):
        """書き手は書いた時に読み手と同じ形で照らす: 形に合わないファイルは指さない"""
        (self.art / "good.json").write_text('[]', encoding="utf-8")
        self.assertEqual(ports.pointer(self.art / "good.json", "json(shared:rows.schema.json)")["path"], "good.json")
        (self.art / "bad.json").write_text('{"x": 1}', encoding="utf-8")
        with self.assertRaises(ports.ShapeError):
            ports.pointer(self.art / "bad.json", "json(shared:rows.schema.json)")

    def test_form_must_be_a_file_form(self):
        (self.art / "a.txt").write_text("x", encoding="utf-8")
        for bad in ("text", "json", "json(x): y", ""):
            with self.subTest(bad), self.assertRaisesRegex(ValueError, "ファイルの form"):
                ports.file(self.ptr("a.txt"), bad)


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
        (folder / "rows.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(ports.pointer(folder / "rows.md", "file"), {"type": "archon_artifact", "run_id": "r1", "path": "world/rows.md"})
        with self.assertRaises(ValueError):
            ports.pointer(self.tmp / "outside.txt", "file")


class InsideCase(Base):
    def test_inside_joins_a_clean_relative_path_under_the_root(self):
        self.assertEqual(ports.inside("a/b.json", self.art), self.art / "a" / "b.json")
        self.assertEqual(ports.inside("a/b.json", str(self.art)), self.art / "a" / "b.json")

    def test_inside_refuses_what_archon_refuses(self):
        for rel in ("", None, 3, "/abs", "\\abs", "a/", "../x", "a/../b", "a\\..\\b", "a\0b"):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                ports.inside(rel, self.art)

    def test_pointer_reading_uses_it(self):
        (self.art / "x.md").write_text("x", encoding="utf-8")
        self.assertEqual(ports.file(self.ptr("x.md"), "file"), self.art / "x.md")
        with self.assertRaises(ValueError):
            ports.file(self.ptr("../x.md"), "file")


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
        with self.assertRaisesRegex(ValueError, "pointer"):
            ports.picked(self.ptr("x.json"), ("a",))

    def test_runner_names_match_the_hermetic_runner(self):
        """試験の殻（tests/bin/hermetic.py）が落とす Archon の変数と同じ名（boundary.py は組み込みで消え、ports が正本）"""
        runner = hermetic.runner_vars()
        self.assertEqual(ports.RUNNER_PREFIXES, tuple(runner["RUNNER_PREFIXES"]))
        self.assertEqual(ports.RUNNER_NAMES, frozenset(runner["RUNNER_NAMES"]))

    def test_drop_runner_env_and_suite_keep(self):
        with mock.patch.dict(os.environ, {"INPUTS_X": "1", "LOG_DIR": "/l", ports.SUITE_KEEP_ENV: "/k"}):
            self.assertEqual(ports.suite_keep(), pathlib.Path("/k"))
            ports.drop_runner_env("/marks")
            self.assertNotIn("INPUTS_X", set(os.environ))
            self.assertNotIn("ARTIFACTS_DIR", set(os.environ))
            self.assertEqual(os.environ[ports.USER_ENV_RAN_DIR], "/marks")
            os.environ["ARTIFACTS_DIR"] = str(self.art)
            os.environ["WORKFLOW_ID"] = "r1"

    def test_shared_cache(self):
        with mock.patch.dict(os.environ, {ports.SHARED_CACHE_ENV: "/state"}):
            self.assertEqual(ports.shared_cache(), pathlib.Path("/state") / "works-factory")
        with mock.patch.dict(os.environ):
            os.environ.pop(ports.SHARED_CACHE_ENV, None)
            self.assertIsNone(ports.shared_cache(), "渡されなければ控えを使わない")

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
