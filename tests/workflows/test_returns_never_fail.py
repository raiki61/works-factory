"""返す節と、返す節が結ぶ節は落ちない（落とし穴 K1・K13・K16。docs/plans/2026-10-13-capabilities/pitfalls.md）。

止めた Archon は、落ちた節の出力を結んだ節を trigger_rule: all_done でも落とす（packages/workflows/src/dag-executor.ts の
resolveBindingDirective・output-ref.ts の resolveNodeOutputField・assertProducerNotFailed）。返りの指し札の先が無い・空でも節を落とす（artifact-pointer.ts の checkPointer）。
返りは JSON.parse で読むので NaN・Infinity を書けない。pack は tests/archon.py の WORKFLOWS。

落ちてはいけない節（NeverFail。表を持たず YAML から組む。持ち主の決め shape-checks-only）:
- どの graph でも、返す節が with:・when:・本文で読む $<id>.output の節（返す節はどれも trigger_rule: all_done で、落ちた節の後にも走る）
- 落ちた節の後にも走る節（trigger_rule が all_done・one_success か always_run）が include の節の出力を直に読めば、include した
  block の返す節。受け皿（埋め P8。既定の trigger_rule で受ける節。docs/design/line.md の頭の語）を通して読む block の返す節は、
  落ちても受け皿が飛ぶだけなので入らない
- ほかの run を workflow: で起こす graph と、起こされる graph（周の鎖・line・fix・merge）の返す節。run の結果を殻と鎖が読む
- 結ばれた include の節は、その block の返す節に置き換えて同じ照らしを当てる

照らし:
- どの workflow の返す節も trigger_rule: all_done で、落ちた節の後にも走る。既定の trigger_rule の返す節は、上流が落ちると飛び、
  block が値を返さない（docs/plans/2026-10-24-fix-weapons.md の 11.0 の 10。one_success・always_run は上流の全部を待たないので入れない）
- 落ちてはいけない節は script の節で（AI の節は retry の後に落ちうる）、一時のフォルダへ単独で写して入力無しで走らせると、終了の値 0 で、
  標準出力の JSON が節の output_format に合い、返りの指し札の先が在って空でない。単独とは lib も隣の script も無い木で、口
  （.shared/ports.py。docs/design/README.md の 4 節）と自分の block の src/ だけを置く（block のコードは block のフォルダに在り、
  lib は起動の殻が渡す根から読むので、読めない時が在る）
- scripts/ から標準出力へ書く道は口（ports.returns）だけ。口を読めない時に直に書く script（口の外の道）は json.dumps(...,
  allow_nan=False) だけを書き、単独で走らせても節の output_format に合う
"""
import ast
import importlib.util
import io
import contextlib
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

from tests.archon import ROOT, WORKFLOWS, src_module

RUN_ID = "run-alone"
PREFIX = "works-factory-"
LENIENT = ("all_done", "one_success")   # 落ちた節の後にも走る trigger_rule
RETURN_RULE = "all_done"   # 返す節の trigger_rule（上流の全部が終わってから、落ちた節の後にも走る）
AI_KEYS = ("prompt", "command")
BOUND = re.compile(r"\$([A-Za-z][\w-]*)\.output\b")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def load(block: str, pack: pathlib.Path = WORKFLOWS) -> dict:
    return yaml.safe_load((pack / block / f"{PREFIX}{block}.yaml").read_text(encoding="utf-8"))


def blocks(pack: pathlib.Path = WORKFLOWS) -> list[str]:
    """pack の graph と block（works-factory-<名>.yaml を持つフォルダ）"""
    return sorted(p.parent.name for p in pack.glob(f"*/{PREFIX}*.yaml") if p.stem == f"{PREFIX}{p.parent.name}")


def all_nodes(listed) -> list[dict]:
    """工程の中の節を全部（loop_group の中も）。節の並びと loop_group の nodes だけを辿る（形の欄 id・承認ノードの options の id は節でない）"""
    out = []
    for n in listed or []:
        out += [n, *all_nodes((n.get("loop_group") or {}).get("nodes"))]
    return out


def node(doc: dict, nid: str) -> dict | None:
    return next((n for n in all_nodes(doc["nodes"]) if n["id"] == nid), None)


def return_node(doc: dict) -> dict:
    return next(n for n in doc["nodes"] if n["id"] == doc["returns"])


def bound_ids(n: dict) -> list[str]:
    """節が with:・when:・本文で読む $<id>.output の <id>"""
    text = yaml.safe_dump({k: v for k, v in n.items() if k != "output_format"}, allow_unicode=True)
    return sorted(set(BOUND.findall(text)))


def lenient(n: dict) -> bool:
    return n.get("trigger_rule") in LENIENT or n.get("always_run") is True


def target(n: dict) -> str | None:
    """include の節が差し込む block の名"""
    name = n.get("include")
    return name[len(PREFIX):] if isinstance(name, str) and name.startswith(PREFIX) else None


def never_fail(pack: pathlib.Path = WORKFLOWS) -> dict[tuple[str, str], str]:
    """落ちてはいけない (block, 節の id) → 訳（docstring の 3 つ）。結ばれた include の節は差し込む block の返す節に置き換える"""
    docs = {b: load(b, pack) for b in blocks(pack)}
    out: dict[tuple[str, str], str] = {}

    def add(block: str, nid: str, why: str) -> None:
        n = node(docs[block], nid)
        inner = target(n) if n else None
        if inner in docs:
            add(inner, docs[inner]["returns"], f"{why}（{block} の include {nid} の返す節）")
        else:
            out.setdefault((block, nid), why)

    for block, doc in docs.items():
        ret = return_node(doc)
        for nid in bound_ids(ret):
            add(block, nid, f"{block} の返す節 {ret['id']} が ${nid}.output を読む")
        for n in all_nodes(doc["nodes"]):
            if n is ret or not lenient(n):
                continue
            for nid in bound_ids(n):
                m = node(doc, nid)
                if m is not None and target(m) in docs:
                    add(block, nid, f"{block} の {n['id']}（{n.get('trigger_rule') or 'always_run'}）が ${nid}.output を直に読む")
    called = {n["workflow"][len(PREFIX):] for doc in docs.values() for n in all_nodes(doc["nodes"])
              if isinstance(n.get("workflow"), str) and n["workflow"].startswith(PREFIX)}
    callers = {b for b, doc in docs.items() if any(isinstance(n.get("workflow"), str) for n in all_nodes(doc["nodes"]))}
    for block in sorted((called | callers) & set(docs)):
        add(block, docs[block]["returns"], f"{block} は workflow: で run を起こすか起こされ、その返りを殻か親の run が読む")
    return out


def strict_returns(pack: pathlib.Path = WORKFLOWS) -> list[str]:
    """返す節が落ちた節の後に走らない workflow（返す節が既定の trigger_rule の物）の誤りの行"""
    out = []
    for block in blocks(pack):
        ret = return_node(load(block, pack))
        if ret.get("trigger_rule") != RETURN_RULE:
            out.append(f"{block}: 返す節 {ret['id']} の trigger_rule が {ret.get('trigger_rule') or '既定'}（落ちた節の後にも走る"
                       f" {RETURN_RULE} にする）")
    return out


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


def writes_stdout(script: pathlib.Path) -> bool:
    return bool(stdout_writes(ast.parse(script.read_text(encoding="utf-8"))))


def run_alone(script: pathlib.Path, place: pathlib.Path, pack: pathlib.Path = WORKFLOWS
              ) -> tuple[subprocess.CompletedProcess, pathlib.Path]:
    """script を place/workflows/<block>/scripts/ に写して入力無しで走らせる。lib も隣の script も置かず、口（pack の .shared/）と
    自分の block の src/ だけを置く"""
    block = script.parents[1]
    alone = place / "workflows" / block.name / "scripts" / script.name
    alone.parent.mkdir(parents=True)
    shutil.copyfile(script, alone)
    skip = shutil.ignore_patterns("__pycache__")
    if (block / "src").is_dir():
        shutil.copytree(block / "src", alone.parents[1] / "src", ignore=skip)
    if (pack / ".shared").is_dir():
        shutil.copytree(pack / ".shared", place / "workflows" / ".shared", ignore=skip)
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
    指し札も照らしが拒んで赤になる）"""
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
    """指し札を口の照らし（ports.inside と run の id）で解き、先が在って空でないか"""
    import ports
    out = []
    for ptr in pointers(value):
        try:
            if ptr.get("type") != ports.POINTER_TYPE or ptr.get("run_id") != RUN_ID:
                raise ValueError(f"この run の {ports.POINTER_TYPE} でない")
            path = ports.inside(ptr.get("path"), artifacts)
        except ValueError as e:
            out.append(f"{ptr}: 解けない（{e}）")
            continue
        if not path.is_file() or path.stat().st_size == 0:
            out.append(f"{ptr['path']}: 先が無いか空")
    return out


def exit_problems(files: list[pathlib.Path], root: pathlib.Path) -> list[str]:
    """口の外で標準出力へ書く所のうち、allow_nan=False の json.dumps でない物"""
    return [f"{path.relative_to(root).as_posix()}:{line}: 口の外の道は json.dumps(..., allow_nan=False) だけを書く"
            for path in files for line, ok in stdout_writes(ast.parse(path.read_text(encoding="utf-8"))) if not ok]


def block_scripts(pack: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in pack.glob("*/scripts/**/*.py") if "__pycache__" not in p.parts)


sys.dont_write_bytecode = True
if str(WORKFLOWS / ".shared") not in sys.path:
    sys.path.insert(0, str(WORKFLOWS / ".shared"))


class ReturnScriptCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        base = pathlib.Path(tmp.name)
        cls.table = never_fail()
        cls.runs = {}
        for (block, nid) in cls.table:
            n = node(load(block), nid)
            if n is not None and "script" in n:
                script = WORKFLOWS / block / "scripts" / f"{n['script']}.py"
                cls.runs[(block, nid)] = (n, *run_alone(script, base / "never" / f"{block}-{nid}"))

    def test_never_failing_nodes_are_found(self):
        """line と周の鎖の返す節・返す節が結ぶ節・include の返す節を拾えなければ、下の照らしは空回りする"""
        self.assertLessEqual({("line", "result"), ("chain", "result"), ("line", "sweep-children"), ("report", "finish")},
                             set(self.table))

    def test_every_return_node_runs_after_a_failed_node(self):
        self.assertEqual(strict_returns(), [])

    def test_never_failing_nodes_are_scripts(self):
        """落ちてはいけない節は script の節（AI の節は retry の後にも落ちうる。承認ノードの答えも script の節で受ける）"""
        for (block, nid), why in self.table.items():
            with self.subTest(f"{block}:{nid}"):
                n = node(load(block), nid)
                self.assertIsNotNone(n, f"節が無い（{why}）")
                self.assertIn("script", n, f"{why}が、{nid} は script の節でない（{sorted(k for k in n if k in AI_KEYS)}）")

    def test_never_failing_scripts_run_alone_and_fit_their_output_format(self):
        for (block, nid), (n, done, _) in self.runs.items():
            with self.subTest(f"{block}:{nid}"):
                self.assertEqual(alone_problems(done, n.get("output_format")), [],
                                 f"{block}/scripts/{n['script']}.py（{self.table[(block, nid)]}）")

    def test_every_pointer_in_a_fallback_return_names_a_nonempty_file(self):
        for (block, nid), (_, done, artifacts) in self.runs.items():
            with self.subTest(f"{block}:{nid}"):
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(pointer_problems(json.loads(done.stdout), artifacts), [])

    def test_direct_stdout_scripts_run_alone_and_fit_their_output_format(self):
        """口の外で標準出力へ直に書く script も、単独で走らせた返りが節の output_format に合う"""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        used = [(block, n) for block in blocks() for n in all_nodes(load(block)["nodes"])
                if "script" in n and writes_stdout(WORKFLOWS / block / "scripts" / f"{n['script']}.py")]
        self.assertTrue(used, "直に書く script を 1 つも拾えなければ照らしは空回りする")
        for block, n in used:
            with self.subTest(f"{block}:{n['id']}"):
                done, _ = run_alone(WORKFLOWS / block / "scripts" / f"{n['script']}.py", pathlib.Path(tmp.name) / block / n["id"])
                self.assertEqual(alone_problems(done, n.get("output_format")), [], f"{block}/scripts/{n['script']}.py")

    def test_returns_leave_only_through_the_ports(self):
        self.assertEqual(exit_problems(block_scripts(WORKFLOWS), ROOT), [])


class ReadsFailureCase(unittest.TestCase):
    """#371: 読んだ証拠の節は、集める中で誤りが起きても終了の値 0 で ok: false を返し、place に落ちた記録（lib/reads.guarded）を
    残す。返りは誰も読まないので、報告はこの記録で「役を起こしていない」と分ける。fix・plan-review・parallel-pr の 3 つ
    （plan は役に読ませるパスが無いので持たない。docs/design/integration.md の 4.1-2）"""
    # (block, script, 集める src の口)
    TABLE = [("fix", "fix_reads", "board.collect_reads"),
             ("plan-review", "review_reads", "proof.collect"),
             ("parallel-pr", "read_proof", "proof.collect")]

    def test_failed_collection_leaves_a_failed_evidence(self):
        if str(ROOT / "lib") not in sys.path:
            sys.path.append(str(ROOT / "lib"))
        import reads
        for block, name, target in self.TABLE:
            with self.subTest(block), tempfile.TemporaryDirectory() as tmp:
                artifacts = pathlib.Path(tmp)
                module, attr = target.split(".")
                src = src_module(block, module)
                path = WORKFLOWS / block / "scripts" / f"{name}.py"
                spec = importlib.util.spec_from_file_location(f"reads_failure_{name}", path)
                script = importlib.util.module_from_spec(spec)
                out = io.StringIO()
                env = {"ARTIFACTS_DIR": str(artifacts), "WORKFLOW_ID": RUN_ID}
                saved = list(sys.path)
                try:
                    with mock.patch.dict(os.environ, env), mock.patch.object(src, attr, side_effect=OSError("壊れた")), \
                            contextlib.redirect_stdout(out):
                        os.environ.pop("ARCHON_NODE_EXECUTION", None)
                        spec.loader.exec_module(script)
                        if hasattr(script, "main"):
                            self.assertEqual(script.main(), 0)
                finally:
                    sys.path[:] = saved
                got = json.loads(out.getvalue())
                self.assertEqual((got["ok"], got["reason"]), (False, "OSError: 壊れた"))
                [evidence] = artifacts.glob(reads.EVIDENCE_GLOB)
                doc, _ = reads.read_evidence(evidence)
                self.assertEqual(doc["sources"]["hook"], reads.FAILED)
                self.assertEqual(doc["sources"]["why"], "OSError: 壊れた")


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

    def test_seed_return_script_that_needs_lib_or_a_wrong_shape_is_red(self):
        schema = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
        pack = self.dir / "pack"
        self.seed("pack/.shared/ports.py", "import json\n\ndef returns(obj):\n    print(json.dumps(obj, allow_nan=False))\n")
        head = ("import sys\nfrom pathlib import Path\n"
                "sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.shared'))\nimport ports\n")
        fine = self.seed("pack/blk/scripts/fine.py", head + "ports.returns({'ok': True})\n")
        done, _ = run_alone(fine, self.dir / "fine", pack)
        self.assertEqual(alone_problems(done, schema), [])
        lib = self.seed("pack/blk/scripts/a.py", head + "import jsonfile\nports.returns({'ok': True})\n")
        done, _ = run_alone(lib, self.dir / "a", pack)
        self.assertNotEqual(alone_problems(done, schema), [])
        shape = self.seed("pack/blk/scripts/b.py", "import json\nprint(json.dumps({'ok': 'yes'}, allow_nan=False))\n")
        done, _ = run_alone(shape, self.dir / "b", pack)
        self.assertNotEqual(alone_problems(done, schema), [])

    def test_seed_bindings_make_never_failing_nodes(self):
        """返す節が結ぶ節・落ちた後にも走る節が直に読む include の返す節・workflow: で起こす graph の返す節を拾い、受け皿を通して
        読む include の返す節と、既定の trigger_rule の節が読む節は拾わない"""
        pack = self.dir / "pack"

        def graph(name: str, doc: dict) -> None:
            self.seed(f"pack/{name}/{PREFIX}{name}.yaml", yaml.safe_dump({"name": f"{PREFIX}{name}", **doc}))

        graph("leaf", {"returns": "end", "nodes": [{"id": "work", "script": "work"},
                                                   {"id": "end", "script": "end", "trigger_rule": "all_done",
                                                    "with": {"w": "$work.output.x"}}]})
        graph("other", {"returns": "end", "nodes": [{"id": "end", "script": "end"}]})
        graph("top", {"returns": "result", "nodes": [
            {"id": "leaf", "include": f"{PREFIX}leaf"},
            {"id": "other", "include": f"{PREFIX}other"},
            {"id": "other-out", "script": "returned", "depends_on": ["other"], "with": {"got": "$other.output"}},
            {"id": "plain", "script": "plain", "with": {"x": "$leaf.output.x"}},
            {"id": "result", "script": "result", "trigger_rule": "all_done",
             "with": {"leaf": "$leaf.output", "other": "$other-out.output.got"}}]})
        graph("caller", {"returns": "done", "nodes": [{"id": "child", "workflow": f"{PREFIX}leaf"},
                                                      {"id": "done", "script": "done", "trigger_rule": "all_done"}]})
        self.assertEqual(sorted(never_fail(pack)), [("caller", "done"), ("leaf", "end"), ("leaf", "work"), ("top", "other-out")])

    def test_seed_return_node_with_the_default_trigger_rule_is_red(self):
        pack = self.dir / "pack"
        for name, ret in (("strict", {"id": "end", "script": "end", "depends_on": ["work"]}),
                          ("done", {"id": "end", "script": "end", "depends_on": ["work"], "trigger_rule": "all_done"}),
                          ("one", {"id": "end", "script": "end", "depends_on": ["work"], "trigger_rule": "one_success"}),
                          ("always", {"id": "end", "script": "end", "depends_on": ["work"], "always_run": True})):
            self.seed(f"pack/{name}/{PREFIX}{name}.yaml", yaml.safe_dump(
                {"name": f"{PREFIX}{name}", "returns": "end", "nodes": [{"id": "work", "script": "work"}, ret]}))
        self.assertEqual([p.split(":")[0] for p in strict_returns(pack)], ["always", "one", "strict"])

    def test_seed_pointer_to_a_missing_or_empty_file_is_red(self):
        (self.dir / "empty.txt").write_text("", encoding="utf-8")
        (self.dir / "full.txt").write_text("x", encoding="utf-8")
        got = {"a": {"type": "archon_artifact", "run_id": RUN_ID, "path": "none.txt"},
               "b": [{"type": "archon_artifact", "run_id": RUN_ID, "path": "empty.txt"}],
               "c": {"type": "archon_artifact", "run_id": RUN_ID, "path": "full.txt"},
               "d": {"type": "archon_artifact", "run_id": RUN_ID, "path": "../full.txt"}}
        self.assertEqual(len(pointer_problems(got, self.dir)), 3)

    def test_seed_stdout_outside_the_ports_is_red(self):
        self.seed("pack/b/scripts/raw.py", "import json, sys\nprint(json.dumps({}))\nsys.stdout.write('{}')\n")
        self.seed("pack/b/scripts/loose.py", "import json\nprint(json.dumps({}, ensure_ascii=False), flush=True)\n")
        self.seed("pack/b/scripts/fine.py", "import json, sys\nprint('x', file=sys.stderr)\n"
                  "print(json.dumps({}, allow_nan=False))\n")
        got = exit_problems(block_scripts(self.dir / "pack"), self.dir)
        self.assertEqual([p.split(":")[0:2] for p in got],
                         [["pack/b/scripts/loose.py", "2"], ["pack/b/scripts/raw.py", "2"], ["pack/b/scripts/raw.py", "3"]])


if __name__ == "__main__":
    unittest.main()
