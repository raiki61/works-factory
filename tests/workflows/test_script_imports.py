"""工程の YAML の `script:` が名指す節の script は、同じ工程のほかの節の script を import しない（workflows/AGENTS.md の E4）。

節の script を import すると、その script の振る舞いが 2 つの節に跨る。共に使う物は節でないモジュール（fix の fixio.py など）か lib/ に置く。
"""
import ast
import pathlib
import unittest

import yaml

from tests.workflows.test_uv_scripts import discover, script_nodes

ROOT = pathlib.Path(__file__).resolve().parents[2]


def imported_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def node_import_faults(workflows: pathlib.Path) -> list[str]:
    faults = []
    for folder in sorted(p for p in workflows.iterdir() if p.is_dir() and not p.name.startswith(".")):
        found = discover(folder / "scripts")
        nodes = set()
        for yml in sorted(folder.glob("*.yaml")):
            doc = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
            nodes |= {name for _, name in script_nodes(doc.get("nodes")) if isinstance(name, str) and name in found}
        for name in sorted(nodes):
            for path in found[name]:
                for other in sorted(imported_names(path) & (nodes - {name})):
                    faults.append(f"{path.relative_to(workflows.parent).as_posix()} が節の script {other} を import する")
    return faults


class NodeImportsCase(unittest.TestCase):
    def test_node_scripts_import_no_other_node_script(self):
        self.assertEqual(node_import_faults(ROOT / "workflows"), [])
