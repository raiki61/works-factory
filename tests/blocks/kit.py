"""block の試験の助け（docs/design/README.md の 11.2。テストのモジュールではない）。

- Run(case, block): 始めの記録の無い使い捨ての run directory（ARTIFACTS_DIR）と git のリポジトリ（作業ツリー）。script(name, **inputs)
  は block の scripts/<name>.py を子のプロセスで回し、port の値（INPUTS_<名>）だけを渡して、返りの JSON を返す。include= で
  ARCHON_NODE_EXECUTION の path を渡す（place が include の道に分かれる）。other(block) は同じ run でほかの block を回す
- load(block, module): block の src/<module> を、この過程に読み込む（block ごとに src の名が重なるので、読む前に前の src を外す）。
  env(run) は script と同じ環境を、この過程の os.environ に一時に置く（src の関数が ports.place・ports.pointer を呼ぶ時）
- fixture(block, name): block の fixtures/<name>.stubs.yaml
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
from unittest import mock

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "blocks"
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
        return env

    def script(self, name: str, include: str = "", **inputs) -> dict:
        done = subprocess.run([sys.executable, str(self.block / "scripts" / f"{name}.py")], cwd=self.repo,
                              env=hermetic.child_env(**self.environ(include, **inputs)), capture_output=True, text=True,
                              encoding="utf-8")
        if done.returncode != 0:
            raise AssertionError(f"{name}.py が落ちた（{done.returncode}）: {done.stderr}")
        return json.loads(done.stdout)

    def failing(self, name: str, include: str = "", **inputs) -> str:
        """落ちるはずの script を回し、標準エラーを返す"""
        done = subprocess.run([sys.executable, str(self.block / "scripts" / f"{name}.py")], cwd=self.repo,
                              env=hermetic.child_env(**self.environ(include, **inputs)), capture_output=True, text=True,
                              encoding="utf-8")
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


def fixture(block: str, name: str) -> dict:
    return yaml.safe_load((BLOCKS / block / "fixtures" / f"{name}.stubs.yaml").read_text(encoding="utf-8"))


def tests_of(block: str, tests: pathlib.Path = ROOT / "tests" / "blocks") -> pathlib.Path:
    return tests / block.replace("-", "_")


def dry_run_traces(block: str, names, included=()) -> dict:
    """筋書きの名 → blocks/<block>/fixtures/ のその筋書きの stub で block を dry-run（exec-code）した trace（ノードの id → trace の行）。
    workflow test はノードの出力を返さないので、stub と入力をそのまま `workflow run --dry-run` に渡す（tests/e2e/test_line_scenarios.py の
    dry_run_traces の blocks/ 版。木は archon.blocks_tree）。graph は include する block の名を included に渡す（木に一緒に置く）。
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
