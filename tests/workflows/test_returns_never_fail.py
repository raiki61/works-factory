"""返す節と、返す節が結ぶ節は落ちない（落とし穴 K1・K13・K16。docs/plans/2026-10-13-capabilities/pitfalls.md）。

止めた Archon は、落ちた節の出力を結んだ節を trigger_rule: all_done でも落とす（packages/workflows/src/dag-executor.ts の
resolveBindingDirective・output-ref.ts の resolveNodeOutputField・assertProducerNotFailed）。返りの指し札の先が無い・空でも節を落とす（artifact-pointer.ts の checkPointer）。
返りは JSON.parse で読むので NaN・Infinity を書けない。
- 線と全ブロックの返す節の script を、境の口（.shared）も lib も隣の script も無い一時のフォルダへ単独で写し、入力無しで走らせる。
  終了の値 0 で、標準出力の JSON が節の output_format に合う
- 返す節が with:・when:・本文で読む $<id>.output の <id> は表 NEVER_FAIL に在り、表の行はその節を lib 無しで走らせる試験を名指す
- 単独で走らせた返りの指し札の先は在って空でない
- 表 LIBLESS_EXITS の script も、単独で走らせた返りが節の output_format に合う
- scripts/ から標準出力へ書く道は境の口（boundary.returns）だけ。外は表 LIBLESS_EXITS の script の
  json.dumps(..., allow_nan=False) だけ（境の口も lib も読めない時にも返す道）
"""
import ast
import contextlib
import importlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / "workflows"
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))
import chain  # noqa: E402  （周の鎖の周の数の上限 MAX_ROUNDS）
RUN_ID = "run-alone"
HERE = "tests.workflows.test_returns_never_fail.ReturnScriptCase."
ALONE_RETURN = HERE + "test_every_returns_script_runs_alone_and_fits_its_output_format"
ALONE_BOUND = HERE + "test_every_bound_script_runs_alone_and_fits_its_output_format"

# 返す節が結ぶ節: (工程のフォルダ, 節の id) → その節を lib 無しで走らせる試験。include の節は差し込むブロックの返す節の試験
NEVER_FAIL = {
    ("plan", "round"): ALONE_BOUND,
    ("report", "facts"): ALONE_BOUND,
    ("line", "report"): ALONE_RETURN,
    ("line", "collect"): ALONE_BOUND,
    ("line", "sweep-children"): ALONE_BOUND,
    ("chain", "chain-start"): ALONE_BOUND,
    ("chain", "final-diff"): ALONE_BOUND,
    **{("chain", f"round-{k}-decide"): ALONE_BOUND for k in range(1, chain.MAX_ROUNDS + 1)},
}

# 境の口を読めない時にも返すため、標準出力へ直に書く script（パス → 訳）
LIBLESS_EXITS = {
    "workflows/line/scripts/result.py": "線の返す節",
    "workflows/line/scripts/collect.py": "線の返す節が $collect.output で結ぶ",
    "workflows/line/scripts/sweep_children.py": "線の返す節が $sweep-children.output で結ぶ",
    "workflows/judge/scripts/verdict.py": "judge の返す節",
    "workflows/plan/scripts/plan_collect.py": "plan の返す節",
    "workflows/plan/scripts/round.py": "plan の返す節が $round.output.dir で結ぶ",
    "workflows/plan/scripts/plan_reads.py": "読んだ証拠の節。受け付けの条件でないので、境の口を読めない時も ok: false で返す（線を止めない）",
    "workflows/plan-review/scripts/result.py": "plan-review の返す節",
    "workflows/plan-review/scripts/review_reads.py": "読んだ証拠の節。受け付けの条件でないので、境の口を読めない時も ok: false で返す（線を止めない）",
    "workflows/fix/scripts/fix_reads.py": "読んだ証拠の節。受け付けの条件でないので、境の口を読めない時も ok: false で返す（ブロックを止めない）",
    "workflows/judge/scripts/pr_reads.py": "読んだ証拠の節。受け付けの条件でないので、境の口を読めない時も ok: false で返す（ブロックを止めない）",
    "workflows/plan-review/scripts/pass_open.py": "差し込みの頭。境の口を読めない時も ok: false で返す今の振る舞いを残す",
    "workflows/fix/scripts/collect.py": "fix の返す節",
    "workflows/test-gate/scripts/result.py": "test-gate の返す節",
    "workflows/eyes/scripts/verdict.py": "eyes の返す節",
    "workflows/merge/scripts/merge.py": "merge の返す節",
    "workflows/report/scripts/collect.py": "report の返す節",
    "workflows/report/scripts/facts.py": "report の返す節が $facts.output で結ぶ",
    "workflows/chain/scripts/result.py": "周の鎖の返す節",
    "workflows/chain/scripts/chain_start.py": "周の鎖の返す節が $chain-start.output で結ぶ",
    "workflows/chain/scripts/decide.py": "周の鎖の返す節が $round-k-decide.output で結ぶ",
    "workflows/chain/scripts/final_diff.py": "周の鎖の返す節が $final-diff.output で結ぶ",
}

BOUND = re.compile(r"\$([A-Za-z][\w-]*)\.output\b")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def load(block: str) -> dict:
    return yaml.safe_load((WORKFLOWS / block / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))


def blocks() -> list[str]:
    """線と全ブロック（works-factory-<名>.yaml を持つフォルダ）"""
    return sorted(p.parent.name for p in WORKFLOWS.glob("*/works-factory-*.yaml") if p.stem == f"works-factory-{p.parent.name}")


def all_nodes(value) -> list[dict]:
    """工程の中の節を全部（loop_group の中も）"""
    if isinstance(value, list):
        return [n for v in value for n in all_nodes(v)]
    if isinstance(value, dict):
        own = [value] if "id" in value else []
        return own + [n for v in value.values() for n in all_nodes(v)]
    return []


def node(block: str, nid: str) -> dict | None:
    return next((n for n in all_nodes(load(block)["nodes"]) if n["id"] == nid), None)


def return_node(block: str) -> dict:
    doc = load(block)
    return next(n for n in doc["nodes"] if n["id"] == doc["returns"])


def script_of(block: str, n: dict) -> pathlib.Path:
    return WORKFLOWS / block / "scripts" / f"{n['script']}.py"


def is_type(value, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[name])


def misfits(value, schema: dict, at: str = "$") -> list[str]:
    """output_format（素の JSON Schema）の required・type・enum・const・anyOf・properties・items に合わない所"""
    if "anyOf" in schema:
        return [] if any(not misfits(value, s, at) for s in schema["anyOf"]) else [f"{at}: anyOf のどれにも合わない: {value!r}"]
    names = schema.get("type")
    names = [names] if isinstance(names, str) else names
    if names and not any(is_type(value, t) for t in names):
        return [f"{at}: 型が {names} でない: {value!r}"]
    out = []
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{at}: {value!r} が {schema['enum']} に無い")
    if "const" in schema and value != schema["const"]:
        out.append(f"{at}: {value!r} が {schema['const']!r} でない")
    if isinstance(value, dict):
        out += [f"{at}: 欄 {k} が無い" for k in schema.get("required", []) if k not in value]
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                out += misfits(v, props[k], f"{at}.{k}")
            elif schema.get("additionalProperties") is False:
                out.append(f"{at}: 知らない欄 {k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += misfits(v, schema["items"], f"{at}[{i}]")
    return out


def run_alone(script: pathlib.Path, place: pathlib.Path) -> tuple[subprocess.CompletedProcess, pathlib.Path]:
    """script だけを place/workflows/<工程>/scripts/ に写し（.shared も lib も隣の script も無い）、入力無しで走らせる"""
    alone = place / "workflows" / script.parents[1].name / "scripts" / script.name
    alone.parent.mkdir(parents=True)
    shutil.copyfile(script, alone)
    artifacts = place / "artifacts"
    artifacts.mkdir()
    env = {"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": RUN_ID, "PATH": os.environ.get("PATH", ""),
           "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([sys.executable, str(alone)], cwd=place, env=env, capture_output=True, text=True, encoding="utf-8")
    return done, artifacts


def alone_problems(done: subprocess.CompletedProcess, schema: dict | None) -> list[str]:
    """単独で走らせた結果が、終了の値 0 で JSON 1 つを書き、output_format に合うか"""
    if done.returncode != 0:
        return [f"終了の値 {done.returncode}: {done.stderr.strip()[-400:]}"]
    try:
        got = json.loads(done.stdout)
    except ValueError as e:
        return [f"標準出力が JSON 1 つでない（{e}）: {done.stdout[:400]!r}"]
    return misfits(got, schema) if schema else []


def pointers(value):
    """返りの中の指し札（入れ子も）。指し札は run_id と path を持つ物で見分け、type の字は見分けに使わない（字を書き違えた
    指し札も resolve が拒んで赤になる）"""
    if isinstance(value, dict):
        if {"run_id", "path"} <= set(value):
            yield value
        else:
            for v in value.values():
                yield from pointers(v)
    elif isinstance(value, list):
        for v in value:
            yield from pointers(v)


def pointer_problems(value, artifacts: pathlib.Path) -> list[str]:
    """指し札を境の口の resolve で解き、先が在って空でないか"""
    shared = str(WORKFLOWS / ".shared")
    if shared not in sys.path:
        sys.path.append(shared)
    import boundary

    out = []
    with mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": RUN_ID}):
        for ptr in pointers(value):
            try:
                path = boundary.resolve(ptr)
            except (KeyError, ValueError) as e:
                out.append(f"{ptr}: 解けない（{e}）")
                continue
            if not path.is_file() or path.stat().st_size == 0:
                out.append(f"{ptr['path']}: 先が無いか空")
    return out


def unlisted_bindings(block: str, n: dict, table: dict) -> list[str]:
    """返す節が読む $<id>.output の <id> のうち、表に無い物"""
    text = yaml.safe_dump({k: v for k, v in n.items() if k != "output_format"}, allow_unicode=True)
    return [f"{block} の返す節 {n['id']} が ${nid}.output を読むが NEVER_FAIL に無い"
            for nid in sorted(set(BOUND.findall(text))) if (block, nid) not in table]


def missing_test(dotted: str) -> str:
    """名指した試験が無ければ訳（在れば空）"""
    module, cls, method = dotted.rsplit(".", 2)
    try:
        found = getattr(getattr(importlib.import_module(module), cls), method)
    except (ImportError, AttributeError) as e:
        return f"試験 {dotted} が無い（{e}）"
    return "" if callable(found) else f"試験 {dotted} が呼べない"


def stdout_writes(tree: ast.AST) -> list[tuple[int, bool]]:
    """標準出力へ書く呼び出しの (行, json.dumps(..., allow_nan=False) を書くか)"""
    def is_stdout(x) -> bool:
        return isinstance(x, ast.Attribute) and x.attr == "stdout" and isinstance(x.value, ast.Name) and x.value.id == "sys"

    def strict(call: ast.Call) -> bool:
        arg = call.args[0] if call.args else None
        return (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "dumps"
                and any(k.arg == "allow_nan" and isinstance(k.value, ast.Constant) and k.value.value is False
                        for k in arg.keywords))

    out = []
    for call in (c for c in ast.walk(tree) if isinstance(c, ast.Call)):
        f = call.func
        if isinstance(f, ast.Name) and f.id == "print":
            dest = next((k.value for k in call.keywords if k.arg == "file"), None)
            if dest is None or is_stdout(dest):
                out.append((call.lineno, strict(call)))
        elif isinstance(f, ast.Attribute) and f.attr == "write" and (
                is_stdout(f.value) or (isinstance(f.value, ast.Attribute) and is_stdout(f.value.value))):
            out.append((call.lineno, False))
        elif isinstance(f, ast.Attribute) and f.attr == "dump" and any(is_stdout(a) for a in call.args):
            out.append((call.lineno, False))
    return out


def exit_problems(files: list[pathlib.Path], table: dict, root: pathlib.Path) -> list[str]:
    """境の口の外で標準出力へ書く所（表に無い script か、allow_nan=False の json.dumps でない物）"""
    out = []
    for path in files:
        name = path.relative_to(root).as_posix()
        for line, ok in stdout_writes(ast.parse(path.read_text(encoding="utf-8"))):
            if name not in table:
                out.append(f"{name}:{line}: 境の口（boundary.returns）の外で標準出力に書く")
            elif not ok:
                out.append(f"{name}:{line}: 境の口の外の道は json.dumps(..., allow_nan=False) だけを書く")
    return out


def block_scripts(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.glob("workflows/*/scripts/**/*.py") if "__pycache__" not in p.parts)


class ReturnScriptCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        base = pathlib.Path(tmp.name)
        cls.returns, cls.bound = {}, {}
        for block in blocks():
            n = return_node(block)
            done, artifacts = run_alone(script_of(block, n), base / "returns" / block)
            cls.returns[block] = (n, done, artifacts)
        for block, nid in NEVER_FAIL:
            n = node(block, nid)
            if n is not None and "script" in n:
                done, artifacts = run_alone(script_of(block, n), base / "bound" / f"{block}-{nid}")
                cls.bound[(block, nid)] = (n, done, artifacts)

    def test_every_returns_script_runs_alone_and_fits_its_output_format(self):
        self.assertGreaterEqual(set(self.returns), {"line", "judge", "plan", "plan-review", "fix", "test-gate", "eyes", "merge",
                                                    "report"})
        for block, (n, done, _) in self.returns.items():
            with self.subTest(block):
                self.assertIn("output_format", n)
                self.assertEqual(alone_problems(done, n["output_format"]), [], f"{block}/scripts/{n['script']}.py")

    def test_every_bound_script_runs_alone_and_fits_its_output_format(self):
        self.assertEqual({k for k, v in NEVER_FAIL.items() if v == ALONE_BOUND}, set(self.bound))
        for (block, nid), (n, done, _) in self.bound.items():
            with self.subTest(f"{block}:{nid}"):
                self.assertEqual(alone_problems(done, n.get("output_format")), [], f"{block}/scripts/{n['script']}.py")

    def test_every_libless_exit_runs_alone_and_fits_its_output_format(self):
        """LIBLESS_EXITS の script は、境の口も lib も読めない時に直に返す道の返りも、節の output_format に合う"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        used = [(block, n) for block in blocks() for n in all_nodes(load(block)["nodes"])
                if "script" in n and script_of(block, n).relative_to(ROOT).as_posix() in LIBLESS_EXITS]
        self.assertEqual({script_of(b, n).relative_to(ROOT).as_posix() for b, n in used}, set(LIBLESS_EXITS))
        for block, n in used:
            with self.subTest(f"{block}:{n['id']}"):
                done, _ = run_alone(script_of(block, n), pathlib.Path(tmp.name) / block / n["id"])
                self.assertEqual(alone_problems(done, n.get("output_format")), [], f"{block}/scripts/{n['script']}.py")

    def test_return_node_binds_only_never_failing_nodes(self):
        for block in blocks():
            with self.subTest(block):
                self.assertEqual(unlisted_bindings(block, return_node(block), NEVER_FAIL), [])
        for (block, nid), dotted in NEVER_FAIL.items():
            with self.subTest(f"{block}:{nid}"):
                self.assertIsNotNone(node(block, nid), f"表の行 {block}:{nid} の節が無い")
                self.assertEqual(missing_test(dotted), "")
                self.assertIn(f"${nid}.output", yaml.safe_dump(return_node(block), allow_unicode=True),
                              f"表の行 {block}:{nid} を返す節が読まない（古い行）")

    def test_every_pointer_in_a_fallback_return_names_a_nonempty_file(self):
        runs = {**{b: v for b, v in self.returns.items()}, **{f"{b}:{i}": v for (b, i), v in self.bound.items()}}
        for name, (_, done, artifacts) in runs.items():
            with self.subTest(name):
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(pointer_problems(json.loads(done.stdout), artifacts), [])

    def test_returns_leave_only_through_the_boundary(self):
        self.assertEqual(exit_problems(block_scripts(ROOT), LIBLESS_EXITS, ROOT), [])
        for name in LIBLESS_EXITS:
            with self.subTest(name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertTrue(stdout_writes(ast.parse(text)), f"{name} は標準出力へ直に書かない（古い行）")


class ReadsFailureCase(unittest.TestCase):
    """#371: 読んだ証拠の 4 つの節は、集める中で誤りが起きても終了の値 0 で ok: false を返し、置き場に落ちた記録
    （lib/reads.guarded）を残す。返りは誰も読まないので、報告はこの記録で「役を起こしていない」と分ける"""
    # (script, 集める lib の口, 置き場の run の置き場からの相対)
    TABLE = [("workflows/fix/scripts/fix_reads.py", "fixboard.collect_reads", "fix/fix"),
             ("workflows/judge/scripts/pr_reads.py", "judge_accept.pr_reads", "judge"),
             ("workflows/plan/scripts/plan_reads.py", "planfile.collect_reads", "plan/r1"),
             ("workflows/plan-review/scripts/review_reads.py", "boardview.collect_reads", "plan-review")]

    def test_failed_collection_leaves_a_failed_evidence(self):
        if str(ROOT / "lib") not in sys.path:
            sys.path.append(str(ROOT / "lib"))
        import reads
        for rel, target, place in self.TABLE:
            with self.subTest(rel), tempfile.TemporaryDirectory() as tmp:
                artifacts = pathlib.Path(tmp)
                spec = importlib.util.spec_from_file_location(f"reads_failure_{pathlib.Path(rel).stem}", ROOT / rel)
                script = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(script)
                module, name = target.split(".")
                out = io.StringIO()
                env = {"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": RUN_ID, "INPUTS_DIR": "plan/r1", "INPUTS_START": "null"}
                with mock.patch.dict(os.environ, env), mock.patch.object(importlib.import_module(module), name, side_effect=OSError("壊れた")), \
                        contextlib.redirect_stdout(out):
                    self.assertEqual(script.main(), 0)
                got = json.loads(out.getvalue())
                self.assertEqual((got["ok"], got["reason"]), (False, "OSError: 壊れた"))
                [path] = (artifacts / place).glob(reads.EVIDENCE_GLOB)
                doc, _ = reads.read_evidence(path)
                self.assertEqual(doc["sources"]["hook"], reads.FAILED)
                why = doc["sources"]["why"]
                if place == "plan-review":   # 見え方の材料を置いていないので、往復の番号と形を読めないと添える（#405）
                    self.assertTrue(why.startswith(f"OSError: 壊れた（{reads.UNREAD_PASS}: "), why)
                else:
                    self.assertEqual(why, "OSError: 壊れた")


class SeedCase(unittest.TestCase):
    """違反の見本で、上の照らしが赤になる"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def seed(self, rel: str, text: str) -> pathlib.Path:
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_seed_return_script_that_needs_the_boundary_is_red(self):
        schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
        top = self.seed("src/blk/scripts/a.py", "import boundary\nboundary.returns({'ok': True})\n")
        done, _ = run_alone(top, self.dir / "a")
        self.assertNotEqual(alone_problems(done, schema), [])
        shape = self.seed("src/blk/scripts/b.py", "import json\nprint(json.dumps({'ok': 'yes'}, allow_nan=False))\n")
        done, _ = run_alone(shape, self.dir / "b")
        self.assertNotEqual(alone_problems(done, schema), [])

    def test_seed_unlisted_binding_and_missing_test_are_red(self):
        n = {"id": "r", "script": "r", "with": {"dir": "$round.output.dir"}, "when": "$gate.output.ok == true"}
        self.assertEqual(len(unlisted_bindings("blk", n, {("blk", "round"): ALONE_BOUND})), 1)
        self.assertNotEqual(missing_test(HERE + "test_no_such_test"), "")

    def test_seed_pointer_to_a_missing_or_empty_file_is_red(self):
        (self.dir / "empty.txt").write_text("", encoding="utf-8")
        (self.dir / "full.txt").write_text("x", encoding="utf-8")
        got = {"a": {"type": "archon_artifact", "run_id": RUN_ID, "path": "none.txt"},
               "b": [{"type": "archon_artifact", "run_id": RUN_ID, "path": "empty.txt"}],
               "c": {"type": "archon_artifact", "run_id": RUN_ID, "path": "full.txt"}}
        self.assertEqual(len(pointer_problems(got, self.dir)), 2)

    def test_seed_stdout_outside_the_boundary_is_red(self):
        self.seed("workflows/b/scripts/raw.py", "import json, sys\nprint(json.dumps({}))\nsys.stdout.write('{}')\n")
        self.seed("workflows/b/scripts/loose.py", "import json\nprint(json.dumps({}, ensure_ascii=False), flush=True)\n")
        self.seed("workflows/b/scripts/fine.py", "import json, sys\nprint('x', file=sys.stderr)\n"
                  "print(json.dumps({}, allow_nan=False))\n")
        got = exit_problems(block_scripts(self.dir), {"workflows/b/scripts/loose.py": "見本",
                                                      "workflows/b/scripts/fine.py": "見本"}, self.dir)
        self.assertEqual([p.split(":")[0:2] for p in got],
                         [["workflows/b/scripts/loose.py", "2"], ["workflows/b/scripts/raw.py", "2"],
                          ["workflows/b/scripts/raw.py", "3"]])


if __name__ == "__main__":
    unittest.main()
