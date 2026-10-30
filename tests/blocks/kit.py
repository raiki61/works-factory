"""block の試験の助け（docs/design/README.md の 11.2。テストのモジュールではない）。

- Run(case, block): 始めの記録の無い使い捨ての run directory（ARTIFACTS_DIR）と git のリポジトリ（作業ツリー）。script(name, **inputs)
  は block の scripts/<name>.py を子のプロセスで回し、port の値（INPUTS_<名>）だけを渡して、返りの JSON を返す。include= で
  ARCHON_NODE_EXECUTION の path を渡す（place が include の道に分かれる）。other(block) は同じ run でほかの block を回す
- load(block, module): block の src/<module> を、この過程に読み込む（block ごとに src の名が重なるので、読む前に前の src を外す）。
  env(run) は script と同じ環境を、この過程の os.environ に一時に置く（src の関数が ports.place・ports.pointer を呼ぶ時）
- shaped(schema, value, block=None): 手で組んだ受け渡しの値 value を、port の形の名 schema（block の schemas/ の名・shared:<名>・
  lib:<名>）で照らしてから返す。合わなければ AssertionError（試験の作り物が本物の書き手の形から外れたまま読み手へ渡らない）
- returned(block, value): ほかの block の返りを手で書いた物 value を、その block の返す節の output_format で照らしてから返す
- fixture(block, name): block の fixtures/<name>.stubs.yaml
- WriterBlockCase: 書き手の型の block（workflows/weapon-<型>/）の薄い試験が継ぐ試験の組。属性 block に block の名を置くだけで、その block の
  筋書き（fixtures/standalone.stubs.yaml）で指示が組める・注文の型の食い違いで落ちる・返答が pointer で返り形に合わない返答で落ちる・
  下請けの段落が表の SPAWNS の偽で入らない、を回す（docs/design/fix.md の 11.10 の 3。本体の事は tests/blocks/shared/test_writerblock.py）
- tests_of(block): block の試験のフォルダ tests/blocks/<名の - を _ にした物>/（Python の package の名は - を持てない。
  tests/layers/test_block_shape.py の 10 が在ることを照らす）
"""
import contextlib
import copy
import importlib
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

import yaml

from tests.archon import WORKFLOWS
from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = WORKFLOWS   # pack のフォルダ（pack.json の ours.folder。入れ替えの前も後も同じ口。docs/design/integration.md の 4.5-11）
SHARED = BLOCKS / ".shared"
RUN_ID = "run-test"


class Run:
    def __init__(self, case, block: str):
        tmp = hermetic.tmpdir(case)
        self.block = BLOCKS / block
        self.artifacts = tmp / "artifacts"
        self.artifacts.mkdir()
        self.repo = tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")

    def other(self, block: str) -> "Run":
        """同じ run directory と作業ツリーで、ほかの block の script を回す（graph の中の受け渡しを確かめる時）"""
        twin = copy.copy(self)
        twin.block = BLOCKS / block
        return twin

    def environ(self, include: str = "", **inputs) -> dict:
        env = {"ARTIFACTS_DIR": str(self.artifacts), "WORKFLOW_ID": RUN_ID, "WORKS_FACTORY_ROOT": str(ROOT),
               **{f"INPUTS_{name.upper()}": value for name, value in inputs.items()}}
        if include:
            env["ARCHON_NODE_EXECUTION"] = json.dumps({"runId": RUN_ID, "path": include})
        if "INPUTS_REPLY_VARIANT" in env:   # 修正の block の受け付けへ渡す書き手の返答の字を、型 variant の書き手の block の返りに包む
            from tests.blocks.fix import support
            env = support.variant_return(env)
        return env

    def _spawn(self, name: str, include: str, inputs: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.block / "scripts" / f"{name}.py")], cwd=self.repo,
                              env=hermetic.child_env(**self.environ(include, **inputs)), capture_output=True, text=True,
                              encoding="utf-8")

    def script(self, name: str, include: str = "", **inputs) -> dict:
        done = self._spawn(name, include, inputs)
        if done.returncode != 0:
            raise AssertionError(f"{name}.py が落ちた（{done.returncode}）: {done.stderr}")
        return json.loads(done.stdout)

    def failing(self, name: str, include: str = "", **inputs) -> str:
        """落ちるはずの script を回し、標準エラーを返す"""
        done = self._spawn(name, include, inputs)
        if done.returncode == 0:
            raise AssertionError(f"{name}.py が落ちなかった: {done.stdout}")
        return done.stderr

    @contextlib.contextmanager
    def env(self, include: str = ""):
        """この過程で src の関数を呼ぶ間、script と同じ環境を置く（作業ツリーにも移る）"""
        here = os.getcwd()
        with mock.patch.dict(os.environ, self.environ(include)):
            os.chdir(self.repo)
            try:
                yield
            finally:
                os.chdir(here)

    def pointer(self, rel: str) -> str:
        return json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": rel})


def load(block: str, module: str):
    sys.dont_write_bytecode = True   # block のフォルダに __pycache__ を作らない（Archon は pack を写し取る）
    for name in [n for n in sys.modules if n == "src" or n.startswith("src.")]:
        del sys.modules[name]
    for path in (str(BLOCKS / block), str(SHARED)):
        while path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    importlib.import_module("ports")   # lib/ を sys.path に足す（script と同じ）
    try:
        return importlib.import_module(f"src.{module}")
    finally:
        sys.path.remove(str(BLOCKS / block))


def _gate():
    if str(SHARED) not in sys.path:
        sys.path.append(str(SHARED))
    return importlib.import_module("ports")


def shaped(schema: str, value, block: str | None = None):
    gate = _gate()
    errors = gate.shape_errors(value, schema, BLOCKS / block if block else None)
    if errors:
        raise AssertionError(f"試験の作り物が {schema} の形に合わない: {' / '.join(errors[:5])}")
    return value


def returned(block: str, value: dict) -> dict:
    from engine.schema import validate_schema
    gate = _gate()
    [path] = (BLOCKS / block).glob("works-factory-*.yaml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    nodes, stack = {}, list(doc.get("nodes") or [])
    while stack:
        node = stack.pop()
        nodes[node.get("id")] = node
        stack += (node.get("loop_group") or {}).get("nodes") or []
    errors = validate_schema(value, gate._expanded(nodes[doc["returns"]]["output_format"], BLOCKS / block))
    if errors:
        raise AssertionError(f"試験の作り物が {block} の返りの形に合わない: {' / '.join(errors[:5])}")
    return value


def fixture(block: str, name: str) -> dict:
    return yaml.safe_load((BLOCKS / block / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))


def tests_of(block: str, tests: pathlib.Path = ROOT / "tests" / "blocks") -> pathlib.Path:
    return tests / block.replace("-", "_")


def dry_run_traces(block: str, names, included=()) -> dict:
    """筋書きの名 → workflows/<block>/fixtures/ のその筋書きの stub で block を dry-run（exec-code）した trace（ノードの id → trace の行）。
    workflow test はノードの出力を返さないので、stub と入力をそのまま `workflow run --dry-run` に渡す（元 tests/e2e/test_line_scenarios.py の
    dry_run_traces の移し。木は archon.blocks_tree）。graph は include する block の名を included に渡す（木に一緒に置く）。
    Archon の源か bun が無ければ archon.absent の見送り"""
    from tests import archon
    out = {}
    with archon.blocks_tree([block, *included]) as tree:
        for name in names:
            given = fixture(block, name)
            stubs = tree.parent / f"{name}.stubs.yaml"
            stubs.write_text(yaml.safe_dump({k: v for k, v in given.items() if k not in ("fixture", "exec-code")},
                                            allow_unicode=True), encoding="utf-8")
            args = [arg for k, v in (given["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
            done = archon.archon(tree, "workflow", "run", f"works-factory-{block}", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                 "--json", *args, "--cwd", str(tree))
            try:
                # 落ちた dry-run は trace の後ろに {ok: false, error} を足して出すので、頭の 1 つの JSON だけを読む
                out[name] = {n["nodeId"]: n for n in json.JSONDecoder().raw_decode(done.stdout.lstrip())[0]["trace"]}
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise AssertionError(f"{name} の dry-run の trace が読めない（{error}）: {done.stdout[-2000:]}{done.stderr[-2000:]}") from None
    return out


class WriterBlockCase(unittest.TestCase):
    """書き手の型の block 1 つの試験（属性 block に block の名を置いて継ぐ）。筋書きの order・slots を JSON の字で渡して script を回す"""
    block = ""

    def setUp(self):
        self.assertTrue(self.block.startswith("weapon-"), "継ぐ時に属性 block に block の名を置く")
        self.weapon = self.block[len("weapon-"):]
        self.fixture = fixture(self.block, "standalone")
        self.inputs = self.fixture["fixture"]["inputs"]
        self.run_ = Run(self, self.block)

    def prep(self, **inputs):
        return self.run_.script("writer_prep", **{**self.inputs, **inputs})

    def reply(self):
        return self.fixture[self.weapon]

    def test_the_scenario_builds_the_prompt_with_the_head_paragraph(self):
        """(i) 筋書きの order・slots で指示が組め、頭の段落の 1 文が在る。指示は place の <w>-prompt-1.md に書かれる"""
        out = self.prep()
        [(node, sentence)] = self.fixture["fixture"]["resolved-text-contains"].items()
        self.assertEqual(node, self.weapon)
        self.assertIn(sentence, out["prompt"])
        self.assertEqual((self.run_.artifacts / f"{self.weapon}-prompt-1.md").read_text(encoding="utf-8"), out["prompt"])

    def test_an_order_of_another_type_stops_the_prep(self):
        """(ii) order.weapon が表の ORDER_WEAPON と違えば prep が落ちる"""
        order = json.loads(self.inputs["order"])
        order["weapon"] = next(w for w in ("pin", "tidy", "remove") if w != order["weapon"])
        self.assertIn("注文の型は", self.run_.failing("writer_prep", **{**self.inputs, "order": json.dumps(order)}))

    def test_the_save_and_out_scripts_return_the_reply_by_pointer_and_not_ok_without_it(self):
        """(iii)（縛る試験の 10 の block の側）<w>-save が形に合う返答を reply-<n>.json に置き、必須の欄を欠いた返答で落ちる。<w>-out は
        置いた返答を pointer で返し、返答が無い周は落ちずに ok: false を返す（本体の場合ごとの照らしは tests/blocks/shared/test_writerblock.py）"""
        self.prep()
        self.assertEqual(self.run_.script("writer_out"), {"ok": False, "reply": None, "reason": mock.ANY, "report": [mock.ANY]})
        self.prep()
        bad = {k: v for k, v in self.reply().items() if k != "fix_closure"}
        self.assertIn("fix_closure", self.run_.failing("writer_save", reply=json.dumps(bad)))
        self.assertEqual(self.run_.script("writer_save", reply=json.dumps(self.reply())), {"saved": True})
        self.assertEqual(json.loads((self.run_.artifacts / "reply-2.json").read_text(encoding="utf-8")), self.reply())
        self.assertEqual(self.run_.script("writer_out"), {"ok": True, "reason": "", "report": [],
                                                          "reply": {"type": "archon_artifact", "run_id": RUN_ID, "path": "reply-2.json"}})

    def test_the_paragraphs_about_subagents_follow_the_table(self):
        """(iv) 下請けの段落は表の SPAWNS で決まる（名の表を持たない）。偽の型は spawns・g1・ask_variant が偽で足され、指示に下請けの文が入らず、
        下請けのファイルも組まれない。真の型は spawns が真、g1 が slots の subagents.owed の有無、ask_variant が slots の段落 ask に従い、
        項目ごとの下請けのファイル 2 つが place に書かれる"""
        table = load(self.block, "render")
        _gate()
        import writerblock
        want = {"spawns": table.SPAWNS, "g1": table.SPAWNS, "ask_variant": table.SPAWNS}
        self.assertEqual(writerblock.paragraphs(table), want)
        given = json.loads(self.inputs["slots"])
        items = bool(given["subagents"]["owed"])
        files = lambda: sorted(p.name for p in self.run_.artifacts.glob("g1-*"))   # noqa: E731
        asked = "A subagent (an implementer started with Agent) cannot consult itself"
        for ask in (False, True):
            with self.subTest(ask=ask):
                slots = {**given, "when": {**given["when"], "ask": ask}}
                text = self.prep(slots=json.dumps(slots))["prompt"]
                self.assertEqual("## Running subagents" in text, table.SPAWNS and items)
                self.assertEqual(asked in text, table.SPAWNS and ask)
        self.assertEqual(files(), ["g1-impl-1.md", "g1-review-1.md"] if table.SPAWNS and items else [])
        if table.SPAWNS:   # 下請けを起こす単位が無い周は、真の型でも項目の段落もファイルも無い
            self.run_ = Run(self, self.block)
            none = {**given, "subagents": {**given["subagents"], "owed": [], "briefs": []}}
            self.assertNotIn("## Running subagents", self.prep(slots=json.dumps(none))["prompt"])
            self.assertEqual(files(), [])

    def test_the_head_paragraph_is_handed_to_the_subagents_as_the_rule_of_the_type(self):
        """(v) 下請けを起こす型（表の SPAWNS が真。名の表を持たない）は、block の prompts/parts/head.md を空の値で組めて、組んだ字が、本体が書いた
        下請けの実装役の指示 g1-impl-<n>.md の works rules の節に在る（docs/plans/2026-10-24-fix-weapons.md の 11.6 の D2 の {weapon_rule}。
        head.md に {名} が増えれば空の値では組めず落ちる）。偽の型は下請けを起こさないので g1-impl を組まない"""
        table = load(self.block, "render")
        _gate()
        import ports
        import prompt
        given = json.loads(self.inputs["slots"])
        owed = {**given["subagents"], "owed": ["stats.py:4 mean"], "judgment_file": "/p/judgment.json", "base_rev": "abc123", "directory": "/repo"}
        self.prep(slots=json.dumps({**given, "subagents": owed}))
        written = sorted(p.name for p in self.run_.artifacts.glob("g1-impl-*.md"))
        if not table.SPAWNS:
            self.assertEqual(written, [])
            return
        self.assertEqual(written, ["g1-impl-1.md"])
        with mock.patch.object(ports, "caller_block", return_value=BLOCKS / self.block):
            head = prompt.render_part("head", {}).strip()
        self.assertTrue(head)
        impl = (self.run_.artifacts / "g1-impl-1.md").read_text(encoding="utf-8")
        self.assertIn(head, impl, "型の頭の段落（型の決まり）が下請けの実装役の指示に渡っていない")
