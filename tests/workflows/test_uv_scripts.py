"""ブロックの script（pack の <ブロック>/scripts/*.py と、Archon が見つける 1 段下のフォルダの物）の頭の uv の script の宣言の試験。

Archon は script の節（runtime: uv）を対象の作業ツリーを cwd に `uv run <ファイル>` で起こす。宣言が無いと uv は対象の
pyproject.toml を拾い、作業ツリーに .venv と uv.lock を作る（作業ツリーを変えない約束が破れる）。
- どの script も頭の 4 行が同じ宣言
- Archon が探す所（scripts/ と、その 1 段下のフォルダ）の .py が全部同じ宣言を持ち、YAML の `script:` の名が全部探した
  ファイルに当たり、`script:` に本体を直に書かない（止めた Archon の packages/workflows/src/script-discovery.ts の
  MAX_SCRIPT_DISCOVERY_DEPTH・scanScriptDir、executor-shared.ts の isInlineScript）
- pyproject.toml を置いた種の写しを cwd に `uv run` で起こしても、`git status --porcelain --ignored` が前後で同じ
- pack は tests/archon.py の WORKFLOWS（入れ替えの前も後も同じ口。docs/design/integration.md の 4.5-11）
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.archon import ROOT, WORKFLOWS
from tests.bin import hermetic
from tests.bin.gitkit import committed_copy, git

SEED = ROOT / "tests" / "e2e" / "target-seed"


# Archon の MAX_SCRIPT_DISCOVERY_DEPTH の写し（tests/shared/test_archon_contract.py が止めた Archon の源に照らす）
DISCOVERY_DEPTH = 1


def scripts(workflows: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for depth in range(DISCOVERY_DEPTH + 1) for p in workflows.glob("*/scripts/" + "*/" * depth + "*.py"))


SCRIPTS = scripts(WORKFLOWS)
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import tree_run  # noqa: E402

HEADER = ["# /// script", '# requires-python = ">=3.12"', "# dependencies = []", "# ///"]
# 外し（lib/AGENTS.md の E3）: 仕様駆動の道の表（YAML）を読む script は PyYAML を宣言する。pack の中は block の入口の 1 本だけで、
# 起動の殻の側の 1 本（YAML_READER_BIN）と根の pyproject.toml と同じ版の字を持つ（docs/design/spec-driven.md の 6.7）
YAML_READERS = ("spec-driven/scripts/intake.py",)
YAML_READER_BIN = ROOT / "bin" / "_lib" / "spec-inputs.py"
PIN = re.compile(r'"(PyYAML==[^"]+)"')


def header_of(script: pathlib.Path, workflows: pathlib.Path) -> list[str]:
    """script の頭に要る 4 行（表を読む script だけ、PyYAML を根の pyproject.toml と同じ版で宣言する）"""
    if script.relative_to(workflows).as_posix() not in YAML_READERS:
        return HEADER
    return [HEADER[0], HEADER[1], f'# dependencies = ["{root_pin()}"]', HEADER[3]]


def root_pin() -> str:
    """根の pyproject.toml の PyYAML の版の字（PyYAML==x.y.z）"""
    return PIN.search((ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
PYPROJECT = '[project]\nname = "target"\nversion = "0"\nrequires-python = ">=3.12"\n'
RUNTIMES = {".py": "uv", ".ts": "bun", ".js": "bun"}
INLINE = re.compile(r"[;(){}&|<>$`\"' ]")
WAIT = 120   # uv が script の環境を初めて組む回も入る上限（秒）


def discover(scripts: pathlib.Path, depth: int = 0) -> dict[str, list[pathlib.Path]]:
    """Archon の scanScriptDir と同じく、scripts/ から DISCOVERY_DEPTH 段下までの script を名ごとに集める（同じ名の重なりも残す）。"""
    found: dict[str, list[pathlib.Path]] = {}
    if not scripts.is_dir():
        return found
    for entry in sorted(scripts.iterdir()):
        if entry.is_dir():
            if depth < DISCOVERY_DEPTH:
                for name, paths in discover(entry, depth + 1).items():
                    found.setdefault(name, []).extend(paths)
        elif entry.suffix in RUNTIMES:
            found.setdefault(entry.stem, []).append(entry)
    return found


def script_nodes(nodes: list) -> list[tuple[str, object]]:
    """節の並び（loop_group の中も）から (節の id, `script:` の値) を集める。"""
    out = []
    for node in nodes or []:
        if "script" in node:
            out.append((node.get("id"), node["script"]))
        if isinstance(node.get("loop_group"), dict):
            out.extend(script_nodes(node["loop_group"].get("nodes")))
    return out


def script_faults(workflows: pathlib.Path) -> list[str]:
    """工程のフォルダごとに、Archon が探す script と YAML の `script:` の食い違いを 1 行ずつ返す。"""
    faults = []
    for folder in sorted(p for p in workflows.iterdir() if p.is_dir() and not p.name.startswith(".")):
        found = discover(folder / "scripts")
        for name, paths in found.items():
            if len(paths) > 1:
                faults.append(f"{folder.name}: 同じ名の script が 2 つ: {name}")
            for path in paths:
                if path.suffix == ".py" and path.read_text(encoding="utf-8").splitlines()[:4] != header_of(path, workflows):
                    faults.append(f"{folder.name}: 頭の宣言が無い: {path.relative_to(workflows)}")
        for spec in sorted(folder.glob("*.yaml")):
            doc = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
            for node_id, value in script_nodes(doc.get("nodes")):
                if not isinstance(value, str) or "\n" in value or INLINE.search(value):
                    faults.append(f"{spec.relative_to(workflows)}: {node_id} が script に本体を直に書く")
                elif value not in found:
                    faults.append(f"{spec.relative_to(workflows)}: {node_id} の script {value} が scripts/ に無い")
    return faults


class HeaderTest(unittest.TestCase):
    def test_one_subfolder_down_is_collected_two_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            flows = pathlib.Path(tmp)
            for rel in ("b/scripts/a.py", "b/scripts/g/c.py", "b/scripts/g/h/d.py"):
                (flows / rel).parent.mkdir(parents=True, exist_ok=True)
                (flows / rel).write_text("", encoding="utf-8")
            self.assertEqual([p.relative_to(flows).as_posix() for p in scripts(flows)],
                             ["b/scripts/a.py", "b/scripts/g/c.py"])

    def test_scripts_exist(self):
        self.assertTrue(SCRIPTS, "pack の */scripts/ に script が 1 本も無い")

    def test_every_script_declares_itself(self):
        for script in SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                self.assertEqual(script.read_text(encoding="utf-8").splitlines()[:4], header_of(script, WORKFLOWS))

    def test_yaml_readers_pin_the_same_pyyaml(self):
        """表を読む 2 本（block の入口の script と起動の殻の script）の PyYAML の版は、根の pyproject.toml と同じ字（6.7 の版の縛り）"""
        for script in [WORKFLOWS / rel for rel in YAML_READERS] + [YAML_READER_BIN]:
            with self.subTest(script=str(script.relative_to(ROOT))):
                self.assertEqual(script.read_text(encoding="utf-8").splitlines()[:4],
                                 [HEADER[0], HEADER[1], f'# dependencies = ["{root_pin()}"]', HEADER[3]])

    def test_every_named_script_archon_can_find_declares_itself(self):
        self.assertEqual(script_faults(WORKFLOWS), [])

    def test_a_tree_with_each_fault_is_named(self):
        """1 段下の宣言の無い script・当たらない名・直に書いた本体・同じ名の 2 つを、それぞれ名指す。"""
        with tempfile.TemporaryDirectory() as tmp:
            block = pathlib.Path(tmp) / "blk"
            (block / "scripts" / "sub" / "deeper").mkdir(parents=True)
            good = "\n".join(HEADER) + "\n"
            (block / "scripts" / "top.py").write_text(good, encoding="utf-8")
            (block / "scripts" / "sub" / "bare.py").write_text("print(1)\n", encoding="utf-8")
            (block / "scripts" / "sub" / "top.py").write_text(good, encoding="utf-8")
            (block / "scripts" / "sub" / "deeper" / "deep.py").write_text(good, encoding="utf-8")
            (block / "blk.yaml").write_text(yaml.safe_dump({"nodes": [
                {"id": "a", "script": "top"},
                {"id": "b", "script": "deep"},
                {"id": "loop", "loop_group": {"nodes": [{"id": "c", "script": "print('x')"}]}},
            ]}), encoding="utf-8")
            self.assertEqual(script_faults(pathlib.Path(tmp)), [
                "blk: 頭の宣言が無い: blk/scripts/sub/bare.py",
                "blk: 同じ名の script が 2 つ: top",
                "blk/blk.yaml: b の script deep が scripts/ に無い",
                "blk/blk.yaml: c が script に本体を直に書く",
            ])


class UvRunTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("uv") is None:
            self.skipTest("uv が無い")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        (self.repo / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
        git(self.repo, "add", "pyproject.toml")
        git(self.repo, "commit", "-q", "-m", "pyproject")

    def status(self) -> str:
        return git(self.repo, "status", "--porcelain", "--ignored")

    def test_uv_run_leaves_the_tree_alone(self):
        env = tree_run.outside_env(hermetic.child_env())
        env.pop("VIRTUAL_ENV", None)
        for script in SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                artifacts = self.tmp / "artifacts" / script.relative_to(WORKFLOWS).with_suffix("")
                artifacts.mkdir(parents=True)
                before = self.status()
                done = subprocess.run(["uv", "run", str(script)], cwd=self.repo, stdin=subprocess.DEVNULL,
                                      capture_output=True, text=True, encoding="utf-8", timeout=WAIT,
                                      env={**env, "WORKFLOW_ID": "run-uv", "ARTIFACTS_DIR": str(artifacts),
                                           "WORKS_FACTORY_ROOT": str(ROOT)})
                self.assertEqual(self.status(), before, f"作業ツリーを変えた\n{done.stderr}")


if __name__ == "__main__":
    unittest.main()
