"""工程の YAML の `script:` が名指す節の script は、同じ工程のほかの節の script を import しない（workflows/AGENTS.md の E4）。

節の script を import すると、その script の振る舞いが 2 つの節に跨る。共に使う物は lib/ か境の口（workflows/.shared/boundary.py）に置く。
同じ scripts/ の import を拾う規則は K8 の tests/layers/scan.py の 1 か所が持ち、ここは K8 の許しの表を通さずに節どうしだけを見る。
"""
import pathlib
import unittest

import yaml

from tests.layers import scan
from tests.workflows.test_uv_scripts import script_nodes

ROOT = pathlib.Path(__file__).resolve().parents[2]


def node_names(folder: pathlib.Path) -> set[str]:
    names = set()
    for yml in sorted(folder.glob("*.yaml")):
        doc = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        names |= {name for _, name in script_nodes(doc.get("nodes")) if isinstance(name, str)}
    return names


def node_import_faults(root: pathlib.Path) -> list[str]:
    found, broken = scan.sibling_imports(root)
    nodes = {block: node_names(block) for block in {path.parent.parent for path, _, _ in found}}
    faults = list(broken)
    for path, _, other in found:
        names = nodes[path.parent.parent]
        if path.stem in names and other in names:
            faults.append(f"{path.relative_to(root).as_posix()} が節の script {other} を import する")
    return faults


class NodeImportsCase(unittest.TestCase):
    def test_node_scripts_import_no_other_node_script(self):
        self.assertEqual(node_import_faults(ROOT), [])
