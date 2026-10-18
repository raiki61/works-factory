"""構造のブロック（workflows/structure/）の試験。

- 形: YAML を PyYAML で読み、返りの約束（docs/design.md の「structure の出力」）・役の節の決まり（E7・E12・E16）・輪の数を見る。
- script: 節の script を子のプロセスで Archon と同じ順に回す（計画のブロックの試験の Run の型。構造の目は試験が返答を渡す）。
  元の works の tests/test_blk_structure.py の BlockCase・EyeInputsCase の当たる場合を写す。
- 筋書き: Archon の `workflow test` で fixtures/*.stubs.yaml を回す（配線だけ。止めた Archon の源が無ければ見送る。tests/archon.py）。
"""
import copy
import importlib.util
import json
import pathlib
import re
import shutil
import unittest

from tests import archon
from tests.bin import trimmed
from tests.bin.gitkit import git
from tests.layers import scan
from tests.workflows import copied
from tests.workflows.test_plan import (CLAMP, LIB, LOOSE, MEAN, NO_DEADLINE, RUN_ID, STRUCTURE, Run, _NodeFailed, eye_dirty,
                                       load, node, nodes)

import context  # noqa: E402  （test_plan が lib を sys.path に足す）
import eye  # noqa: E402
import launchgroups  # noqa: E402
import rolekit  # noqa: E402
import structfile  # noqa: E402
import structmark  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

SCRIPTS = STRUCTURE / "scripts"
COMMANDS = STRUCTURE / "commands"
INPUTS = {"start": "", "units": "[]"}
RETURNED = ["ok", "structure"]
# 役の指示書の写しの台帳（K9。tests/workflows/copied.py）。元は今の works（raiki61/claude-plugins の
# 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/ の下
COPIED = {
    "structure-eye.md": (
        [("works/blk-structure/commands/structure-eye.md",
          "e6927788ec3f660e996d8c723fc86792f4929495afc2b68fb97b0d75610ca98f", 1238)],
        []),
}


def structure_run(case, **kw) -> Run:
    return Run(case, block=STRUCTURE, **kw)


def loaded(name):
    spec = importlib.util.spec_from_file_location(f"structure_script_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ShapeCase(unittest.TestCase):
    """返りの約束と入力（docs/design.md の「structure の出力」）"""

    def test_name_inputs_and_return(self):
        doc = load(STRUCTURE)
        self.assertEqual(doc["name"], "works-factory-structure")
        self.assertEqual({k: v["default"] for k, v in doc["inputs"].items()}, INPUTS)
        self.assertEqual((doc["returns"], doc["outcome_field"]), ("structure", "ok"))

    def test_return_node_carries_exactly_the_contract(self):
        fmt = node(load(STRUCTURE), "structure")["output_format"]
        self.assertEqual(fmt["required"], RETURNED)
        self.assertEqual(sorted(fmt["properties"]), sorted(RETURNED + ["optional"]), "optional は required に無い欄（差し替えの返りに無くても落ちない）")
        self.assertIs(fmt["additionalProperties"], False)
        ptr = fmt["properties"]["structure"]
        self.assertEqual((ptr["type"], sorted(ptr["required"])), ("object", ["path", "run_id", "type"]))
        self.assertEqual(set(structfile.PORTS), {"structure"}, "名の表の欄は返す節の欄")

    def test_composed_block_declares_no_run_owned_keys(self):
        doc = load(STRUCTURE)
        for key in ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout"):
            self.assertNotIn(key, doc, key)

    def test_eye_is_a_toolless_isolated_role(self):
        """構造の目は道具ゼロ・opus・effort high・設定は user だけ・sandbox 有効・作業ツリーを変えない独立の会話"""
        roles = [n for n in nodes(load(STRUCTURE)) if any(k in n for k in scan.ROLE_KINDS)]
        self.assertEqual([n["id"] for n in roles], ["structure-eye"])
        eye_node = roles[0]
        self.assertIs(eye_node["mutates_checkout"], False)
        self.assertEqual(eye_node["settingSources"], ["user"])
        self.assertEqual(eye_node["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False})
        self.assertEqual((eye_node["allowed_tools"], launchgroups.default_of(eye_node["model"])), ([], ("opus", "high")))

    def test_eye_command_reads_only_its_prep(self):
        """構造の目は道具なしの独立の会話: 指示書が読むのは支度の節の出力だけ"""
        text = (COMMANDS / "structure-eye.md").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"\$[A-Za-z][\w.-]*", text)), {"$structure-eye-prep.output.prompt"})

    def test_eye_command_is_the_original(self):
        """構造の目の指示書は元の blk-structure/commands/structure-eye.md の字のまま（台帳の直しは無く、書き直しは copied_rewrites.json の件だけ）"""
        self.assertEqual(copied.restore_problems(COMMANDS / "structure-eye.md", *COPIED["structure-eye.md"]), [])

    def test_every_command_is_in_the_ledger(self):
        self.assertEqual(sorted(p.name for p in COMMANDS.glob("*.md")), sorted(COPIED))
        self.assertLessEqual(copied.rewritten(COMMANDS), set(COPIED), "台帳に無い指示書の書き直し")

    def test_ai_deadlines_are_twenty_days_and_others_have_none(self):
        for n in nodes(load(STRUCTURE)):
            self.assertNotIn("timeout", n, n["id"])
            if "command" in n or "prompt" in n:
                self.assertEqual(n.get("idle_timeout"), NO_DEADLINE, n["id"])

    def test_eye_loop_gives_up_in_the_body_before_max_iterations(self):
        """構造の目の輪は諦めの数 GIVE_UP_AFTER と同じ max_iterations で、受け付けの done で抜ける"""
        lg = node(load(STRUCTURE), "structure-eye-loop")["loop_group"]
        self.assertEqual(lg["max_iterations"], rolekit.GIVE_UP_AFTER)
        self.assertIs(lg["fresh_context"], False)
        self.assertEqual(lg["until_bash"], 'done=$structure-eye-accept.output.done; test "$done" = true')

    def test_eye_schema_is_the_design_row_owner(self):
        """役の型は lib の持ち主の型（design-row.schema.json）の写し（Archon の YAML は lib を読めない）"""
        def bare(schema):
            if isinstance(schema, dict):
                return {k: bare(v) for k, v in schema.items() if not (k in ("note", "description") and isinstance(v, str))}
            return [bare(v) for v in schema] if isinstance(schema, list) else schema

        owner = json.loads((LIB / "design-row.schema.json").read_text(encoding="utf-8"))
        added = {"route_reason"}           # 受け付けが足す
        dropped = {"precedents"}           # 今の works の structure-eye の型に無い
        unrequired = {"route"}             # 今の works の structure-eye の型は任意（受け付けが既定の行き先を足す）
        rows = node(load(STRUCTURE), "structure-eye")["output_format"]["properties"]["rows"]["items"]
        self.assertEqual(trimmed.without_trimmed(rows["properties"]),
                         {k: v for k, v in bare(owner["properties"]).items() if k not in added | dropped})
        self.assertEqual(rows["required"], [k for k in owner["required"] if k not in added | unrequired])
        self.assertIs(rows["additionalProperties"], owner["additionalProperties"])

    def test_scripts_are_read_only_uv_scripts(self):
        for n in nodes(load(STRUCTURE)):
            if "script" in n:
                self.assertIs(n.get("mutates_checkout"), False, n["id"])
                text = (SCRIPTS / f"{n['script']}.py").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("# /// script\n"), n["script"])
                self.assertIn("sys.dont_write_bytecode = True", text, n["script"])

    def test_script_names_differ_from_lib_modules(self):
        lib = {p.stem for p in LIB.glob("*.py")}
        mine = {p.stem for p in SCRIPTS.glob("*.py")}
        self.assertEqual(mine & lib, set())
        self.assertEqual(mine, {n["script"] for n in nodes(load(STRUCTURE)) if "script" in n})

    def test_fallback_names_match_lib(self):
        """落ちない返す節は lib を読めない時に標準ライブラリだけで同じ置き場に書く。その字が lib と同じ"""
        col = loaded("structure_collect")
        self.assertEqual((col.DIR, col.STATE_FILE, col.DESIGN_FILE), (structfile.DIR, structfile.STATE_FILE, eye.DESIGN_FILE))


class EyeTypeCase(unittest.TestCase):
    """構造の目の返答の型の正本は目の節の output_format だけ（受け付けの eye.problems は行の意味だけを見る）"""

    def fmt(self) -> dict:
        return node(load(STRUCTURE), "structure-eye")["output_format"]

    def test_trimmed_min_length_kept_by_pattern(self):
        self.assertEqual(trimmed.missing_patterns(self.fmt()), [])

    def test_vocabulary_matches_output_format(self):
        """受け付けと指示書が使う語（eye.VERDICTS・eye.ROUTES）と形の数（eye.FORMS）は、目の節の output_format の enum と faces の範囲"""
        row = self.fmt()["properties"]["rows"]["items"]["properties"]
        self.assertEqual(row["verdict"]["enum"], list(eye.VERDICTS))
        self.assertEqual(row["route"]["enum"], list(eye.ROUTES))
        self.assertEqual((row["faces"]["items"]["minimum"], row["faces"]["items"]["maximum"]), (1, len(eye.FORMS)))

    def test_rows_outside_the_type_are_rejected(self):
        """元 lib/tests/test_structure_eye.py の test_bad_rows_are_named の型の側: 知らない行き先・形の外の欄・形の番号の型"""
        clean = {"unit_id": "u-1", "verdict": "汚れない", "faces": [], "evidence": ["/units/0/measure"], "reason": "形が増えない"}
        self.assertEqual(validate_schema({"rows": [clean]}, self.fmt()), [])
        for name, row in (("知らない行き先", {**clean, "route": "後で"}), ("形の外の欄", {**clean, "note": "x"}),
                          ("真偽を形の番号に", {**clean, "faces": [True]}), ("形の番号の外", {**clean, "faces": [7]})):
            with self.subTest(name):
                self.assertTrue(validate_schema({"rows": [row]}, self.fmt()))


class StageACase(unittest.TestCase):
    """段 A（元 tests/test_blk_structure.py の BlockCase・EyeInputsCase）"""

    def measure(self, run, **inputs):
        run.inputs.update(inputs)
        return run.script("structure_measure")

    def test_measures_units_and_writes_empty_design_rows(self):
        run = structure_run(self)
        got = self.measure(run)
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "ok", doc)
        self.assertEqual([u["id"] for u in doc["units"]], [MEAN, CLAMP])
        self.assertEqual(pathlib.Path(got["design_file"]).stat().st_size, 0)
        self.assertIs(got["eye"], True)
        self.assertEqual(pathlib.Path(got["structure_file"]).parent, run.art / structfile.DIR)

    def test_measure_failure_and_unreadable_units_do_not_stop(self):
        run = structure_run(self)
        shutil.rmtree(run.repo / ".git")   # git の無い対象では実測が落ちる
        doc = json.loads(pathlib.Path(self.measure(run)["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed", doc)
        self.assertTrue(doc["reason"])
        run = structure_run(self)
        got = self.measure(run, units="{壊れた")
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["status"], "failed", doc)
        self.assertFalse(got["eye"])

    def test_unit_without_paths_is_skipped_and_named(self):
        run = structure_run(self, units=[{"id": MEAN, "paths": ["stats.py"], "summary": "mean の分母"},
                                         {"id": LOOSE, "paths": [], "summary": "書き方の全体"}])
        out = run.include()
        doc = json.loads((run.art / structfile.DIR / structfile.STRUCTURE_FILE).read_text(encoding="utf-8"))
        self.assertEqual([u["id"] for u in doc["units"]], [MEAN])
        self.assertEqual(structmark.skipped(run.file(out["structure"])), [LOOSE])

    def test_eye_sees_concept_rows_and_policy(self):
        run = structure_run(self, units=[{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}],
                            start={"policy_md": "POLICY.md"})
        files = {"src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n',
                 "POLICY.md": "決まり: 結末の語は report.py だけが持つ\n",
                 "docs/concepts.md": "# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n",
                 "docs/concepts.json": json.dumps({"exclude": ["docs/**"], "concepts": {"outcome": {
                     "status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"",
                                                     "allowed": ["src/report.py"], "known": {}}]}}}, ensure_ascii=False)}
        self.target(run, files)
        got = self.measure(run)
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("### `outcome` run の結末", prompt)
        self.assertIn("known_places", prompt)
        self.assertIn("結末の語は report.py だけが持つ", prompt)

    MAP = ("# 地図\n\n### `outcome` run の結末\n\n- 状態: 住処あり\n- 住処: `src/report.py`\n\n"
           "### `halt` 止め札\n\n- 状態: 住処あり\n- 住処: `src/halt.py`\n")
    TABLE = {"exclude": ["docs/**"], "concepts": {
        "outcome": {"status": "住処あり", "fences": [{"what": "結末の語", "pattern": "\"round_limit\"",
                                                     "allowed": ["src/report.py"], "known": {}}]},
        "halt": {"status": "住処あり", "fences": [{"what": "止め札", "pattern": "\"STOP\"", "allowed": ["src/halt.py"],
                                                  "known": {}}]}}}

    def target(self, run, files):
        """元 tests/test_blk_structure.py の EyeInputsCase.target の形を種に commit する"""
        for rel, text in files.items():
            (run.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (run.repo / rel).write_text(text, encoding="utf-8")
        git(run.repo, "add", "-A")
        git(run.repo, "commit", "-q", "-m", "target")

    def edge_run(self, **start):
        return structure_run(self, units=[{"id": MEAN, "paths": ["src/edge.py"], "summary": "境の節が結末の語を書く"}], start=start)

    def test_fresh_measure_drops_old_eye_state(self):
        run = structure_run(self)
        out = run.art / structfile.DIR
        out.mkdir(parents=True)
        (out / eye.EYE_FILE).write_text('{"status": "gave_up"}', encoding="utf-8")
        (out / eye.DESIGN_FILE).write_text('{"unit_id": "前の行"}\n', encoding="utf-8")
        got = self.measure(run)
        self.assertFalse((out / eye.EYE_FILE).exists())
        self.assertEqual(pathlib.Path(got["design_file"]).read_bytes(), b"")

    def test_concept_rows_only_for_unit_paths(self):
        """元 tests/test_blk_structure.py の test_eye_sees_concept_rows_for_unit_paths"""
        run = self.edge_run()
        self.target(run, {"src/report.py": 'OUT = "round_limit"\n', "src/edge.py": 'x = "round_limit"\n',
                          "src/halt.py": 'S = "STOP"\n', "docs/concepts.md": self.MAP,
                          "docs/concepts.json": json.dumps(self.TABLE, ensure_ascii=False)})
        got = self.measure(run)
        unit_ = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))["units"][0]
        self.assertEqual([r["id"] for r in unit_["concepts"]["rows"]], ["outcome"])
        self.assertEqual([(x["concept"], x["path"], x["home"], x["known_places"]) for x in unit_["concepts"]["places"]],
                         [("outcome", "src/edge.py", False, 2)])
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("### `outcome` run の結末", prompt)
        self.assertNotIn("### `halt`", prompt)

    def test_no_map_no_table_measures_only(self):
        run = self.edge_run()
        self.target(run, {"src/edge.py": 'x = "round_limit"\n'})
        got = self.measure(run)
        doc = json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))
        self.assertEqual(doc["units"][0]["concepts"], {"rows": [], "places": []})
        self.assertFalse((run.repo / "docs").exists())

    def test_eye_sees_root_map_and_cut_policy(self):
        """元 tests/test_blk_structure.py の test_eye_sees_policy_text（根の地図の文書）と、長い方針の文書の切りの印"""
        run = self.edge_run(policy_md="POLICY.md")
        long_policy = "決まり: 結末の語は report.py だけが持つ\n" + "あ" * context.TEXT_CAP
        self.target(run, {"src/edge.py": 'x = "round_limit"\n', "POLICY.md": long_policy,
                          "AGENTS.md": "# 対象の決まり\n\n層は下へだけ依存する\n"})
        got = self.measure(run)
        prompt = run.script("eye_prep", {"structure_file": got["structure_file"]})["prompt"]
        self.assertIn("結末の語は report.py だけが持つ", prompt)
        self.assertIn("層は下へだけ依存する", prompt)
        cut = len(long_policy) - context.TEXT_CAP
        self.assertIn(f"…（{cut} 字を切った）", prompt)

    def test_measure_reads_the_frozen_policy_copy(self):
        """構造の目が名指す方針は、始めの記録の固めた版の写し（policy_md の生の文書ではない）"""
        frozen = {"named": "POLICY.md", "path": "/repo/POLICY.md", "sha256": "a" * 64, "copy": "/run/policy/frozen.md"}
        got = self.measure(structure_run(self, start={"policy_md": "POLICY.md", "policy": frozen}))
        self.assertEqual(json.loads(pathlib.Path(got["structure_file"]).read_text(encoding="utf-8"))["policy_path"],
                         "/run/policy/frozen.md")

    def test_measure_records_timing(self):
        doc = json.loads(pathlib.Path(self.measure(structure_run(self))["structure_file"]).read_text(encoding="utf-8"))
        timing = doc["timing"]
        self.assertIsInstance(timing[eye.WALL], float)
        for key in ("started_at", "finished_at"):
            self.assertRegex(timing[key], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$", key)


class CollectCase(unittest.TestCase):
    """返す節: 構造の目の控えをいつも書いて指す。中の節が落ちても・目が諦めても、計画は構造の目の行なしで進める"""

    def test_clean_eye_gives_ok_state(self):
        run = structure_run(self)
        out = run.include()
        self.assertIs(out["ok"], True, out)
        self.assertEqual(out["structure"]["path"], f"{structfile.DIR}/{structfile.STATE_FILE}")
        state = run.json(out["structure"])
        self.assertEqual((state["status"], state["skipped"]), ("ok", []))
        self.assertEqual(len(structmark.rows(state["design_file"])), 2)

    def test_route_up_row_reaches_the_state(self):
        """構造の目が「人に上げる」とした行は控えの design_file の行に残る（事前審査が修正前の承認ノードの問いにする）"""
        run = structure_run(self)
        out = run.include(eye=lambda f: eye_dirty(f, route=True))
        self.assertIs(out["ok"], True, out)
        rows = structmark.rows(run.json(out["structure"])["design_file"])
        self.assertEqual(rows[0]["route"], structmark.ROUTE_UP)

    def test_eye_without_rows_leaves_failed_state(self):
        run = structure_run(self)
        out = run.include(eye=lambda f: {"rows": []})
        self.assertEqual(run.out["structure-eye-accept"]["give_up"], True)
        self.assertIs(out["ok"], False)
        state = run.json(out["structure"])
        self.assertEqual(state["status"], "failed", state)
        self.assertIn("回とも受け付けで拒まれた", state["reason"])

    def test_failed_measure_node_still_returns_a_failed_state(self):
        """実測の節そのものが落ちた run も返す節は走り（all_done）、訳つきの failed の控えを返す"""
        run = structure_run(self)
        run.doc = copy.deepcopy(run.doc)
        node(run.doc, "structure-measure")["script"] = "no_such_script"
        script = run.script

        def failing(name, bound=None, **kw):
            if name == "no_such_script":
                raise _NodeFailed
            return script(name, bound, **kw)

        run.script = failing
        out = run.include(eye=lambda f: self.fail("目を起こした"))
        self.assertEqual((run.status["structure-measure"], run.status["structure-eye-loop"]), ("failed", "skipped"))
        self.assertIs(out["ok"], False)
        self.assertIn(structfile.STRUCTURE_FILE, run.json(out["structure"])["reason"])

    def test_unwritable_state_goes_to_the_spare_place(self):
        """控えを置き場に書けない run も節を落とさず、別の置き場に「控えを書けない」の訳で failed の控えを置いて返す
        （計画は構造の目の行なしで進む。元 works/darkfactory/lib/line_edge.py の structure_edge）"""
        run = structure_run(self)
        (run.art / structfile.DIR / structfile.STATE_FILE).mkdir(parents=True)
        out = run.include()
        self.assertEqual(run.status["structure"], "ok")
        self.assertEqual(out["structure"]["path"], f"{structfile.SPARE_DIR}/{structfile.STATE_FILE}")
        state = run.json(out["structure"])
        self.assertEqual(state["status"], "failed")
        self.assertIn(structfile.UNWRITABLE_STATE, state["reason"])

    def test_return_survives_a_lib_that_does_not_load(self):
        run = structure_run(self)
        broken = run.tmp / "no-lib"
        broken.mkdir()
        out = run.script("structure_collect", root=broken)
        self.assertEqual(validate_schema(out, node(load(STRUCTURE), "structure")["output_format"]), [])
        self.assertIs(out["ok"], False)
        self.assertIn("ModuleNotFoundError", run.json(out["structure"])["reason"])
        self.assertEqual(out["structure"]["run_id"], RUN_ID)

    def test_return_echoes_the_declared_optional(self):
        declared = node(load(STRUCTURE), "structure")["with"]["optional"]
        want = json.loads(declared)
        self.assertEqual(sorted((row["node"], row["bare"]) for row in want),
                         [("structure-", False), ("structure-eye", True), ("structure-eye-", True)])
        run = structure_run(self)
        self.assertEqual(run.include()["optional"], want, "ブロックを通した返す節の返り")
        broken = run.tmp / "no-lib"
        broken.mkdir()
        self.assertEqual(run.script("structure_collect", {"optional": declared}, root=broken)["optional"], want, "失敗の形")
        self.assertEqual(run.script("structure_collect")["optional"], [], "宣言を渡されない呼び手")


class FixtureCase(unittest.TestCase):
    """Archon の `workflow test` で筋書き（fixtures/*.stubs.yaml）を回す（配線だけ）"""

    def test_fixtures_pass(self):
        names = sorted(p.name.removesuffix(".stubs.yaml") for p in (STRUCTURE / "fixtures").glob("*.stubs.yaml"))
        self.assertEqual(names, ["eye-gave-up", "eye-skipped", "measured"])
        with archon.tree(["structure"]) as tree:
            done = archon.archon(tree, "workflow", "test", "works-factory-structure", "--json", "--cwd", str(tree))
        try:
            report = json.loads(done.stdout)
        except json.JSONDecodeError:
            self.fail(f"workflow test の返りが読めない: {done.stdout}{done.stderr}")
        self.assertEqual(report.get("errors"), [], report)
        self.assertEqual((report["failed"], report["passed"]), (0, len(names)), json.dumps(report, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    unittest.main()
