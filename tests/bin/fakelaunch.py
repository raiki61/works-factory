"""殻 bin/works-factory を子のプロセスで走らせる試験の木（テストのモジュールではない。test_*.py に当たらない）。

リポジトリの bin/・lib/・workflows/・pack.json を使い捨ての木に写し、その factory/pack.json は、同じ木の取り置きの置き場に作った
偽の Archon の源の commit を名指す（本物の源は取らない・網に出ない）。偽の bun は受けた引数と環境を JSON に書く。
"""
import json
import pathlib
import shutil
import sys
import uuid
from dataclasses import dataclass

from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENTRY = "packages/cli/src/cli.ts"

FAKE_BUN = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_BUN_LOG"], "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv, "env": dict(os.environ)}, f)
"""


@dataclass(frozen=True)
class Tree:
    repo: pathlib.Path         # 写したリポジトリの根（bin/works-factory・bin/apply と、bin/apply の使う lib/ が在る）
    cache_home: pathlib.Path   # XDG_CACHE_HOME に渡す置き場
    source: pathlib.Path       # 偽の Archon の源
    tools: pathlib.Path        # python3 と git だけを置いた PATH の置き場


def unique_run_id() -> str:
    """殻の workflow cancel は、env の WORKFLOW_ID がこの id のプロセスを、この機械のこの利用者のプロセスの中から探して止める。
    殻に本物の ps の上で cancel を打たせる試験は、並べて回す別の試験のプロセス（run-1 などを使う）を止めないよう、この字を使う"""
    return f"test-run-{uuid.uuid4().hex}"


def put(path: pathlib.Path, body: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def build(base: pathlib.Path) -> Tree:
    """base（空の実体のパス）の下に、写したリポジトリ・偽の Archon の源・道具の置き場を作る"""
    repo = base / "repo"
    no_cache = shutil.ignore_patterns("__pycache__")
    shutil.copytree(ROOT / "bin", repo / "bin", ignore=no_cache)
    shutil.copytree(ROOT / "lib", repo / "lib", ignore=no_cache)
    shutil.copytree(ROOT / "workflows", repo / "workflows", ignore=no_cache)
    shutil.copytree(ROOT / "blocks", repo / "blocks", ignore=no_cache)
    shutil.copy(ROOT / "pack.json", repo / "pack.json")
    cache_home = base / "cache"
    asf = json.loads((ROOT / "factory" / "pack.json").read_text(encoding="utf-8"))
    staging = base / "archon-staging"
    put(staging / ENTRY, "// 偽の Archon の入口\n")
    (staging / "bunfig.toml").write_text("# 偽の Archon の bun の設定\n", encoding="utf-8")
    put(staging / asf["source_directory"] / "archon-x.yaml", "name: archon-x\n")
    (staging / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    git(staging, "init", "-q")
    git(staging, "add", "-A")
    git(staging, "commit", "-q", "-m", "fake archon")
    commit = git(staging, "rev-parse", "HEAD")
    source = cache_home / "works-factory" / "archon" / commit
    source.parent.mkdir(parents=True)
    staging.rename(source)
    (source / "node_modules").mkdir()
    asf.update(integration_revision_required=commit, repository=str(source))
    (repo / "factory").mkdir()
    (repo / "factory" / "pack.json").write_text(json.dumps(asf), encoding="utf-8")
    tools = base / "tools"
    tools.mkdir()
    for name, real in (("python3", sys.executable), ("git", shutil.which("git"))):
        (tools / name).symlink_to(real)
    return Tree(repo=repo, cache_home=cache_home, source=source, tools=tools)
