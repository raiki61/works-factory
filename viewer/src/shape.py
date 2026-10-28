"""工場の作りの読み（graph と block の YAML・AI のノードの指示の md・script の頭の docstring・設計書の在り処）。

根（pack のフォルダ。今の木なら `<clone>/workflows`、run の写しなら `<写し>/project/.archon/workflows/<pack>`）を引数で受け、
どちらも同じ形で読む。読み分けられない物は黙って落とさず `problems` に 1 行ずつ出す（`tests/viewer/test_shape.py` が今の木で 0 を照らす）。

- read(workflows, prefix, design=None) -> {"graphs": {フォルダ: graph}, "problems": [行]}
- locate(graphs, folder, tokens) -> 記録のノードの道（`tokens`）が当たる所と、そこまでに通った include・workflow: のノード。当たらなければ None
- tokens(path) -> Archon の記録のノードの道（`a__b.c`）を id の並びにする
"""
import json
import re
from pathlib import Path

import yaml

# ノードの種類を決める鍵（Archon の節の種類）と、見る道具の読み分け。どれか 1 つだけを持つノードを読み分けられる
KINDS = {
    "loop_group": "loop",
    "include": "block",
    "workflow": "child",
    "approval": "gate",
    "wait": "gate",
    "prompt": "ai",
    "command": "ai",
    "loop": "ai",
    "cancel": "halt",
    "bash": "bash",
    "script": "script",
}
OUTSIDE = "outside"   # 工場の名の頭で始まらない workflow: の先（Archon 同梱の archon-pr など）。木に無くても当たり先の無い物に数えない
REF = re.compile(r"\$([A-Za-z0-9_-]+)\.output((?:\.[A-Za-z0-9_]+)*)")
INPUT_REF = re.compile(r"\$INPUTS\.([A-Za-z0-9_]+)")
DESIGN_REF = re.compile(r"docs/design/[A-Za-z0-9_.-]+\.md")
INCLUDED = "__"   # include で開いた子の id の区切り（Archon の include-expander.ts）
IN_LOOP = "."     # loop_group の本体のノードの区切り


def tokens(path: str) -> list[str]:
    return [part for seg in path.split(IN_LOOP) for part in seg.split(INCLUDED)]


def read(workflows: Path, prefix: str, design: Path | None = None) -> dict:
    """workflows の直下のフォルダの `<prefix><フォルダ>.yaml` を全部読む。design（`docs/design/`）が在れば設計書の在り処を拾う"""
    problems, raw = [], {}
    for folder in sorted(p for p in workflows.iterdir() if p.is_dir()):
        path = folder / f"{prefix}{folder.name}.yaml"
        if not path.is_file():
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            problems.append(f"{_rel(workflows, path)}: YAML が読めない（{str(error).splitlines()[0]}）")
            continue
        if not isinstance(doc, dict):
            problems.append(f"{_rel(workflows, path)}: YAML の頭が mapping でない")
            continue
        raw[folder.name] = (path, doc)
    names = {doc.get("name"): folder for folder, (_, doc) in raw.items()}
    graphs = {}
    for folder, (path, doc) in raw.items():
        reader = _Graph(workflows, folder, prefix, names, problems)
        items = [reader.item(node, []) for node in _list(doc.get("nodes"))]
        graphs[folder] = _graph(workflows, path, doc, items, design)
    for folder, graph in graphs.items():
        graph["used_by"] = [{"graph": other, "node": item["id"], "kind": item["kind"]}
                            for other, og in graphs.items() for item in walk(og["items"])
                            if item["kind"] in ("block", "child") and item.get("target") == folder]
        graph["kind"] = "graph" if graph["subs"] else "block"
    return {"graphs": graphs, "problems": problems}


def walk(items):
    for item in items:
        yield item
        yield from walk(item.get("kids") or [])


def locate(graphs: dict, folder: str, ids: list[str], via: tuple = ()) -> dict | None:
    """graph folder の中で、記録のノードの道 ids（tokens が返す物）が当たる所 {"graph", "node"（graph の中の道。/ 区切り）, "via"}。
    include・workflow: の先へは、そのノードの先の graph の頭のノードから続けて辿る。via は通った include・workflow: のノードを外から順に
    並べた [{"graph", "node"}]（見る道具の図が、入れ子の graph へ外から入る道）。工場の外の graph の中は {"outside": 名}"""
    graph = graphs.get(folder)
    if graph is None or not ids:
        return None
    items, trail = graph["items"], []
    for index, ident in enumerate(ids):
        item = next((i for i in items if i["id"] == ident), None)
        if item is None:
            return None
        trail.append(ident)
        rest = ids[index + 1:]
        if not rest:
            return {"graph": folder, "node": "/".join(trail), "via": list(via)}
        if item["kind"] == "loop":
            items = item["kids"]
        elif item["kind"] in ("block", "child") and item.get("target"):
            return locate(graphs, item["target"], rest, (*via, {"graph": folder, "node": "/".join(trail)}))
        elif item["kind"] == "child" and item.get("outside"):
            return {"outside": item["outside"]}
        else:
            return None
    return None


class _Graph:
    def __init__(self, workflows: Path, folder: str, prefix: str, names: dict, problems: list):
        self.workflows, self.folder, self.prefix, self.names, self.problems = workflows, folder, prefix, names, problems
        self.yaml = f"{folder}/{prefix}{folder}.yaml"

    def item(self, node, trail: list[str]) -> dict:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            self.problems.append(f"{self.yaml}: id の無いノード（{_clip(_text(node), 80)}）")
            return {"id": "", "kind": "", "path": trail, "kids": []}
        path = [*trail, node["id"]]
        where = f"{self.yaml}: {'/'.join(path)}"
        keys = [key for key in KINDS if key in node]
        item = {"id": node["id"], "path": path, "deps": _list(node.get("depends_on")), "when": _text(node.get("when") or ""),
                "trigger": node.get("trigger_rule") or "", "always": bool(node.get("always_run")),
                "desc": _text(node.get("description") or ""),
                "with": {k: _text(v) for k, v in _dict(node.get("with")).items()},
                "refs": {k: refs(v) for k, v in _dict(node.get("with")).items()},
                "outs": fields(_dict(node.get("output_format")).get("properties"))}
        if len(keys) != 1:
            self.problems.append(f"{where}: 読み分けられないノード（種類の鍵 {'・'.join(keys) or '無し'}）")
            item["kind"] = ""
            return item
        key = keys[0]
        item["kind"] = KINDS[key]
        getattr(self, f"_{item['kind']}")(node, key, item, where)
        return item

    def _loop(self, node, key, item, where):
        group = _dict(node[key])
        item.update(max=group.get("max_iterations"), until=_text(group.get("until_bash") or group.get("until") or ""),
                    fresh=group.get("fresh_context", True))
        item["kids"] = [self.item(kid, item["path"]) for kid in _list(group.get("nodes"))]

    def _block(self, node, key, item, where):
        self._target(node[key], key, item, where)

    def _child(self, node, key, item, where):
        self._target(node[key], key, item, where)
        item.update(fan_out=_text(node.get("fan_out") or ""), isolation=_text(node.get("isolation") or ""))

    def _target(self, name, key, item, where):
        item["name"] = _text(name)
        if isinstance(name, str) and name in self.names:
            item["target"] = self.names[name]
        elif isinstance(name, str) and not name.startswith(self.prefix):
            item["outside"] = name
        else:
            self.problems.append(f"{where}: {key}: の先 {_text(name)} が木に無い")

    def _gate(self, node, key, item, where):
        item.update(gate=key, ask=_clip(json.dumps(node[key], ensure_ascii=False, indent=1), 2000))

    def _ai(self, node, key, item, where):
        prompts = self.workflows / self.folder / "prompts"
        md, system = prompts / f"{node['id']}.md", prompts / f"{node['id']}.system.md"
        if not md.is_file():
            self.problems.append(f"{where}: AI のノードの指示の md {_rel(self.workflows, md)} が無い")
        item.update(model=node.get("model") or "", tools=_list(node.get("allowed_tools")), denied=_list(node.get("denied_tools")),
                    skills=_list(node.get("skills")), prompt=_text(node.get(key) or ""), system=_text(node.get("systemPrompt") or ""),
                    retry=_text(node.get("retry") or ""), md=_file(self.workflows, md), system_md=_file(self.workflows, system))
        item["refs"]["prompt"] = refs(node.get(key) or "")

    def _halt(self, node, key, item, where):
        item["halt"] = _text(node[key])

    def _bash(self, node, key, item, where):
        item["bash"] = _clip(_text(node[key]), 3000)

    def _script(self, node, key, item, where):
        script = self.workflows / self.folder / "scripts" / f"{node[key]}.py"
        if not script.is_file():
            self.problems.append(f"{where}: script のノードの script {_rel(self.workflows, script)} が無い")
        item.update(script=_text(node[key]), runtime=node.get("runtime") or "",
                    script_file=_rel(self.workflows, script) if script.is_file() else "", doc=docstring(script))


def _graph(workflows: Path, path: Path, doc: dict, items: list, design: Path | None) -> dict:
    every = list(walk(items))
    returns = doc.get("returns")
    returned = next((i for i in every if i["id"] == returns), None) if isinstance(returns, str) else None
    inputs = []
    for name, value in _dict(doc.get("inputs")).items():
        value = value if isinstance(value, dict) else {"default": value}
        inputs.append({"name": name, "required": bool(value.get("required")), "desc": _text(value.get("description") or ""),
                       "default": _text(value.get("default", ""))})
    desc = _text(doc.get("description") or "").strip()
    folder = path.parent.name
    docs = []
    if design is not None:
        own = f"docs/design/{folder}.md"
        for name in [own, *DESIGN_REF.findall(desc)]:
            if name not in docs and (design.parent.parent / name).is_file():
                docs.append(name)
    return {"name": doc.get("name"), "file": _rel(workflows, path), "desc": desc, "inputs": inputs,
            "returns": returns if isinstance(returns, str) else _text(returns or ""), "outcome": doc.get("outcome_field") or "",
            "return_fields": (returned or {}).get("outs") or [], "worktree": _text(doc.get("worktree") or ""), "items": items,
            "docs": docs, "ai": [i["id"] for i in every if i["kind"] == "ai"],
            "subs": sorted({i["target"] for i in every if i.get("target") and i["target"] != folder}), "nodes": len(every)}


def refs(value) -> list[dict]:
    """値の中の `$<ノード>.output[.<欄>]` と `$INPUTS.<名>` の参照"""
    text = _text(value)
    got = [{"node": m[1], "field": m[2][1:] or "*"} for m in REF.finditer(text)]
    return got + [{"node": "INPUTS", "field": m[1]} for m in INPUT_REF.finditer(text)]


def fields(props, head: str = "", depth: int = 0) -> list[list[str]]:
    """出力の形の欄を 1 段まで開いた [[欄, 型, 説明]]"""
    out = []
    for name, spec in _dict(props).items():
        if not isinstance(spec, dict):
            continue
        kind = spec.get("type")
        kind = "|".join(kind) if isinstance(kind, list) else (kind or "")
        about = spec.get("description") or ""
        if spec.get("enum"):
            about = (about + " " if about else "") + "（" + "・".join(map(str, spec["enum"][:8])) + "）"
        out.append([head + name, kind, about])
        sub = spec.get("properties") or _dict(spec.get("items")).get("properties")
        if sub and depth < 1:
            out += fields(sub, head + name + ("[]." if kind == "array" else "."), depth + 1)
    return out


def docstring(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    found = re.search(r'"""(.*?)"""', text, re.S)
    return _clip(found[1].strip(), 1500) if found else ""


def _file(workflows: Path, path: Path) -> dict:
    """md の在り処と字（無ければ空の欄）"""
    if not path.is_file():
        return {"file": "", "text": ""}
    return {"file": _rel(workflows, path), "text": path.read_text(encoding="utf-8", errors="replace")}


def _rel(workflows: Path, path: Path) -> str:
    return path.relative_to(workflows).as_posix()


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _clip(text: str, size: int) -> str:
    return text if len(text) <= size else text[:size] + f"\n…（残り {len(text) - size} 字）"


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []
