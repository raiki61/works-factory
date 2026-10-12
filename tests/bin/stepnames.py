"""工程の YAML から、run の記録の節の id（workflow get --verbose の nodes[].nodeId）を組む（test_* でないので unittest の発見に拾われない）。

止めた Archon の名の付け方を写す。include の節は消え、差し込んだ工程の頭の節が <include の id>__<節の id> になる（include の中で
さらに差し込んだ物も同じ規則で重なる。packages/workflows/src/include-expander.ts の inlineInclude）。輪（loop_group）の中の節は
<輪の節の id>.<節の id> になり、入れ子の輪で重なる（packages/workflows/src/dag-executor.ts の bodyStepNamePrefix）。差し込みの頭は
差し込んだ工程の頭の節にだけ付くので、差し込んだ工程の中の輪の体の節は <include の id>__<輪の id>.<節の id> になる。
workflow: で起こす子の run（fix の組）は別の run なので、親の名に入らない。
"""
import pathlib
from collections.abc import Iterator

import yaml

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / "workflows"


def nodes(name: str) -> list[dict]:
    """工程 name（workflows/<ブロック>/<name>.yaml）の頭の節の並び"""
    (path,) = WORKFLOWS.glob(f"*/{name}.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["nodes"]


def walk(listed: list[dict]) -> Iterator[dict]:
    """節の並びの節を、輪の中の入れ子まで書いたままの形で出す（include を開かない）"""
    for node in listed:
        yield node
        if "loop_group" in node:
            yield from walk(node["loop_group"]["nodes"])


def _expanded(listed: list[dict]) -> list[tuple[str, dict]]:
    out = []
    for node in listed:
        if "include" in node:
            out += [(f"{node['id']}__{inner}", child) for inner, child in _expanded(nodes(node["include"]))]
        else:
            out.append((node["id"], node))
    return out


def _steps(listed: list[dict], prefix: str) -> Iterator[str]:
    for ident, node in _expanded(listed):
        yield prefix + ident
        if "loop_group" in node:
            yield from _steps(node["loop_group"]["nodes"], f"{prefix}{ident}.")


def step_names(name: str) -> set[str]:
    """工程 name を 1 つの run として回した時の、run の記録に出うる節の id の全部"""
    return set(_steps(nodes(name), ""))
