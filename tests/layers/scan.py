"""層の決まりの「機械」の行を照らす。`problems(rule, root)` は 1 行に 1 つ `<パス>:<行>: <何が>` を返す（無ければ空）。

字の形でしか見ないので、次は人が見る:
- E3: 節の id（字の形で見分けられない）
- E4: `pathlib` などで部品を継いで組むパス
- E12: script の中で置く期限
"""
import json
import posixpath
import re
from collections.abc import Callable
from pathlib import Path

import yaml

from bin._lib.place import WORKFLOW_FOLDER

BOUNDARY = "boundary.py"
POLYFILL_ROW = re.compile(r"workflows/\.shared/([^\s`（）()、・。]+)(`?（予定）)?")

ARCHON_WORDS = re.compile(r"(?i:archon)|ARTIFACTS_DIR|TYPED_ARTIFACTS_FILE|output_type")
LAYER_IMPORT = re.compile(r"^\s*(from|import)\s+(workflows|bin)\b")

# まだ木に無いブロックを指す字も捕まえるための名の表。根の AGENTS.md の「リポジトリの形」の木との一致は test_block_paths が縛る。木に在るブロックは木から読む。
BLOCKS = ("line", "judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")
RELATIVE_PATH = re.compile(r"(?:\.\./)+[^\s'\"`)]*")

OURS = json.loads((Path(__file__).resolve().parents[2] / "pack.json").read_text(encoding="utf-8"))["ours"]
OURS_PREFIX = OURS["name_prefix"]
OURS_PACK = OURS["pack"]
LINE_YAML = f"workflows/{OURS['line'].removeprefix(OURS_PREFIX)}/{OURS['line']}.yaml"
CALL_KEYS = ("include", "workflow")

NO_DEADLINE = "1728000000"
# 止めた Archon（docs/design.md の「語」）の節の種類の鍵の全部と、その種類の節に Archon が既定の期限を当てる鍵（workflows/AGENTS.md の E12）。
# ここに無い種類の節は赤にする。Archon が種類を足したら、期限を持つかを確かめてからここに足す。
NODE_KINDS = {
    "script": ("timeout",),
    "bash": ("timeout",),
    "prompt": ("idle_timeout",),
    "command": ("idle_timeout",),
    "loop": ("idle_timeout", "timeout"),
    "loop_group": ("timeout",),
    "approval": ("idle_timeout",),
    "wait": (),
    "cancel": (),
    "include": (),
    "workflow": (),
}
DEADLINE_KEYS = frozenset(key for keys in NODE_KINDS.values() for key in keys)
WAIT_DEADLINE_KEY = "deadline_ms"
YAML_INT = "tag:yaml.org,2002:int"

# 持ち主の決め lang-neutral により、事実上の標準の形式（junit など）は表に入れない。
LANG_WORDS = (
    "pytest", "unittest", "jest", "vitest", "mocha", "rspec", "minitest", "phpunit",
    "go test", "cargo test", "npm test", "yarn test", "pnpm test", "gradle", "maven", "mvn", "tox", "nox",
    "javascript", "typescript", "ruby", "rust", "golang", "java", "kotlin", "php", "swift", "perl", "scala",
)
LANG_WORD = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(w) for w in LANG_WORDS) + r")(?![A-Za-z_])", re.I
)

OWNER_ENV = ("raiki61", "claude-code-oauth-", "/Users/")

# 決まりごとに照らしから外すパス。`/` で終わる行はそのフォルダの下の全部。どの行も本物の木の何かに当たる（stale_allowances）。
ALLOWED = {
    "E3": ("lib/AGENTS.md",),
    "E13": (
        "lib/AGENTS.md",
        "lib/tests/",
        "lib/impact.py",
        "lib/changemap.py",
        "lib/tddloop.py",
        "lib/fixrules.py",
        "lib/libdocs.py",
        "lib/libdocs_local.py",
    ),
}

# E13 の例外（根の AGENTS.md の E13 の「例外」）: 拡張子と言語の対応・テストのファイルの名の慣習の表を持つ、今の works から元のまま持ってきたファイルと、その元。
# ALLOWED["E13"] に足してよいのは、上の 2 つとここに在るファイルだけ（test_scan_rules が縛る）。ファイルを入れる PR が ALLOWED["E13"] に 1 行ずつ足す
# （木に無いファイルの行は stale_allowances が赤にするので、ここには先に名だけを置く）。docs/owner-decisions.md の「2026-10-11 の決めから導いた事」の仮の判断。
E13_TABLES = {
    "lib/impact.py": "元 works/.shared/core/impact.py。掃除の段で言語の知識を外へ出す",
    "lib/changemap.py": "元 works/.shared/core/changemap.py。掃除の段で言語の知識を外へ出す",
    "lib/tddloop.py": "元 works/blk-fix/lib/tddloop.py。掃除の段で言語の知識を外へ出す",
    "lib/fixrules.py": "元 works/blk-fix/lib/fixrules.py。掃除の段で言語の知識を外へ出す",
    "lib/libdocs.py": "元 works/.shared/core/libdocs.py。掃除の段で言語の知識を外へ出す",
    "lib/libdocs_local.py": "元 works/.shared/core/libdocs_local.py。掃除の段で言語の知識を外へ出す",
}


def problems(rule: str, root: Path) -> list[str]:
    try:
        check = RULES[rule]
    except KeyError:
        raise ValueError(f"知らない決まり: {rule}（{', '.join(RULES)} のどれか）") from None
    return [line for line in check(Path(root)) if not _allowed(rule, line.split(":", 1)[0])]


def stale_allowances(root: Path) -> list[str]:
    """`ALLOWED` の行のうち、木の何にも当たらない物"""
    root = Path(root)
    return [
        f"{rule}: {entry} が木の何にも当たらない"
        for rule, entries in ALLOWED.items()
        for entry in entries
        if not (any(_files(root, entry)) if entry.endswith("/") else (root / entry).is_file())
    ]


def _allowed(rule: str, rel: str) -> bool:
    return any(_matches(entry, rel) for entry in ALLOWED.get(rule, ()))


def _matches(entry: str, rel: str) -> bool:
    return rel.startswith(entry) if entry.endswith("/") else rel == entry


def _files(root: Path, *parts: str):
    base = root.joinpath(*parts)
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _lines(root: Path, path: Path) -> tuple[list[str], list[str]]:
    """ファイルの行と、読めない時の問題の行（どちらかが空）。読めないファイルを黙って通さない"""
    try:
        return path.read_text(encoding="utf-8").splitlines(), []
    except UnicodeDecodeError:
        return [], [f"{_rel(root, path)}:1: UTF-8 で読めない"]


def _grep(root: Path, paths, *checks: tuple[re.Pattern, Callable[[re.Match], str]]) -> list[str]:
    """各 (正規表現, 当たりを文にする関数) を、ファイルの順・行の順に当てる"""
    out = []
    for path in paths:
        lines, broken = _lines(root, path)
        out += broken
        for number, line in enumerate(lines, 1):
            for pattern, what in checks:
                for match in pattern.finditer(line):
                    out.append(f"{_rel(root, path)}:{number}: {what(match)}")
    return out


def _workflow_yamls(root: Path):
    for path in _files(root, "workflows"):
        if path.suffix in (".yaml", ".yml"):
            yield path


def _documents(root: Path, path: Path):
    """YAML の文書の node の列と、読めない時の問題の行（どちらかが空）"""
    try:
        return list(yaml.compose_all(path.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)), []
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark else 1
        reason = getattr(error, "problem", None) or str(error).splitlines()[0]
        return [], [f"{_rel(root, path)}:{line}: YAML が読めない: {reason}"]


def _pairs(node):
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            if isinstance(key, yaml.ScalarNode):
                yield key.value, value


def _nodes(document):
    """工程の節を、`loop_group` の中の入れ子まで出す。Archon が節を入れ子にできるのは `loop_group.nodes` だけ。

    `output_format` の JSON Schema や `with:` の値の中の同じ名の鍵は、節の鍵でない。
    """
    body = _top(document, "nodes")
    if isinstance(body, yaml.SequenceNode):
        for item in body.value:
            yield item
            yield from _nodes(_top(item, "loop_group"))


def _blocks(root: Path) -> list[Path]:
    workflows = root / "workflows"
    if not workflows.is_dir():
        return []
    return sorted(p for p in workflows.iterdir() if p.is_dir() and p.name != ".shared")


def _top(node, key: str):
    if isinstance(node, yaml.MappingNode):
        for k, value in node.value:
            if isinstance(k, yaml.ScalarNode) and k.value == key:
                return value
    return None


def _line(node) -> int:
    return node.start_mark.line + 1


def includes(root: Path, rel: str) -> list[str]:
    """root/rel の工程の `include:` の先の工程の名（`loop_group` の中も）。読めない YAML は ValueError"""
    documents, broken = _documents(root, root / rel)
    if broken:
        raise ValueError(broken[0])
    return [
        value.value
        for document in documents
        for node in _nodes(document)
        if isinstance(value := _top(node, "include"), yaml.ScalarNode)
    ]


def _polyfills_listed(root: Path) -> list[str]:
    registry = root / "docs" / "polyfills.md"
    listed = {}
    rows, out = _lines(root, registry) if registry.is_file() else ([], [])
    for number, line in enumerate(rows, 1):
        if line.strip().startswith("- 埋め:"):
            for match in POLYFILL_ROW.finditer(line):
                planned = bool(match[2])
                if match[1] not in listed or listed[match[1]][1] and not planned:
                    listed[match[1]] = (number, planned)
    for name, (number, planned) in listed.items():
        if not planned and not (root / "workflows" / ".shared" / name).is_file():
            out.append(f"{_rel(root, registry)}:{number}: 名簿の workflows/.shared/{name} が木に無い")
    shared = root / "workflows" / ".shared"
    for path in _files(root, "workflows", ".shared"):
        name = path.relative_to(shared).as_posix()
        if name != BOUNDARY and name not in listed:
            out.append(f"{_rel(root, path)}:1: 名簿にも境の口にも当たらない")
    return out


def _lib_blind(root: Path) -> list[str]:
    return _grep(
        root,
        _files(root, "lib"),
        (ARCHON_WORDS, lambda m: f"Archon の名 {m[0]}"),
        (LAYER_IMPORT, lambda m: f"{m[2]} の中の物を import する"),
    )


def _block_paths(root: Path) -> list[str]:
    """ブロックの `scripts/` の字と、YAML の字（直に書いた script）を照らす。

    YAML の中の script は Archon が写し取った所のどこから走るかが字から分からないので、相対パスは行き先のブロックの名だけを見る。
    """
    out = []
    blocks = [p.name for p in _blocks(root)]
    for own in blocks:
        others = sorted((set(BLOCKS) | set(blocks)) - {own})
        named = re.compile(
            rf"workflows/(?:{re.escape(OURS_PACK)}/)?(" + "|".join(re.escape(b) for b in others) + r")/"
        )
        allowed = (f"workflows/{own}/", "lib/", "workflows/.shared/")
        folder = root / "workflows" / own
        scripts = [(p, True) for p in _files(root, "workflows", own, "scripts")]
        yamls = [(p, False) for p in sorted(folder.iterdir()) if p.is_file() and p.suffix in (".yaml", ".yml")]
        for path, is_script in scripts + yamls:
            rel = _rel(root, path)
            here = posixpath.dirname(rel)
            lines, broken = _lines(root, path)
            out += broken
            for number, line in enumerate(lines, 1):
                for match in named.finditer(line):
                    out.append(f"{rel}:{number}: ほかのブロック {match[1]} を指す")
                for match in RELATIVE_PATH.finditer(line):
                    target = match[0]
                    pointed = _pointed_block(target)
                    resolved = posixpath.normpath(posixpath.join(here, target)) + "/"
                    if pointed in others:
                        out.append(f"{rel}:{number}: 相対パス {target} がほかのブロック {pointed} を指す")
                    elif is_script and not resolved.startswith(allowed):
                        out.append(f"{rel}:{number}: 相対パス {target} が lib/・workflows/.shared/・自分のブロックの外を指す")
    return out


def _pointed_block(target: str) -> str:
    """相対パスの `..` の後の最初の名。`workflows/` と Archon が読む所（`.archon/workflows/<pack>/`）の頭は飛ばす"""
    parts = [part for part in target.split("/") if part not in ("..", ".", "")]
    for head in (*WORKFLOW_FOLDER.split("/"), OURS_PACK):
        if parts and parts[0] == head:
            parts.pop(0)
    return parts[0] if parts else ""


def _no_asf(root: Path) -> list[str]:
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for node in _nodes(document):
                for key, value in _pairs(node):
                    if key not in CALL_KEYS:
                        continue
                    if not isinstance(value, yaml.ScalarNode):
                        out.append(f"{rel}:{_line(value)}: {key}: の形が読めない")
                    elif not value.value.startswith(OURS_PREFIX):
                        out.append(f"{rel}:{_line(value)}: {key}: の値 {value.value} が {OURS_PREFIX} で始まらない")
    return out


def _names(root: Path) -> list[str]:
    out = []
    for folder in _blocks(root):
        expected = f"{OURS_PREFIX}{folder.name}"
        for path in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in (".yaml", ".yml")):
            rel = _rel(root, path)
            documents, broken = _documents(root, path)
            out += broken
            if broken:
                continue
            name = _top(documents[0], "name") if documents else None
            if not isinstance(name, yaml.ScalarNode):
                out.append(f"{rel}:1: 工程の名が無い")
            elif name.value.startswith("archon-"):
                out.append(f"{rel}:{_line(name)}: 工程の名が archon- で始まる（{name.value}）")
            elif name.value != expected:
                out.append(f"{rel}:{_line(name)}: 工程の名は {expected} のはず（{name.value}）")
    return out


def _no_timeouts(root: Path) -> list[str]:
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for node in _nodes(document):
                keys = dict(_pairs(node))
                kinds = [kind for kind in NODE_KINDS if kind in keys]
                if not kinds:
                    out.append(f"{rel}:{_line(node)}: 節の種類が {'・'.join(NODE_KINDS)} のどれでもない")
                set_deadlines = [(key, keys[key]) for key in sorted(DEADLINE_KEYS & keys.keys())]
                set_deadlines += [(key, value) for key, value in _pairs(keys.get("wait")) if key == WAIT_DEADLINE_KEY]
                for key, value in set_deadlines:
                    if not (isinstance(value, yaml.ScalarNode) and value.tag == YAML_INT and value.value == NO_DEADLINE):
                        out.append(f"{rel}:{_line(value)}: {key} が {NO_DEADLINE} でない")
                needed = {key for kind in kinds for key in NODE_KINDS[kind]}
                for key in sorted(needed - keys.keys()):
                    out.append(f"{rel}:{_line(node)}: 節に {key} が無い（Archon の既定の期限が当たる）")
    return out


def _lang_neutral(root: Path) -> list[str]:
    commands = [p for folder in _blocks(root) for p in _files(folder, "commands")]
    return _grep(root, commands + list(_files(root, "lib")), (LANG_WORD, lambda m: f"言語か実行器の名 {m[0]}"))


def _no_owner_env(root: Path) -> list[str]:
    pattern = re.compile("|".join(re.escape(s) for s in OWNER_ENV))
    paths = [p for layer in ("bin", "workflows", "lib") for p in _files(root, layer)]
    return _grep(root, paths, (pattern, lambda m: f"持ち主の環境の字 {m[0]}"))


ORIGIN_NAME = re.compile(r"^(factory|FACTORY|harness|\.factory|archon-)")
OWN_LAYERS = ("bin", "workflows", "lib", "tests", "docs")


def _origin_names(root: Path) -> list[str]:
    out = []
    for layer in OWN_LAYERS:
        for path in _files(root, layer):
            rel = path.relative_to(root)
            hit = next((part for part in rel.parts[1:] if ORIGIN_NAME.match(part)), None)
            if hit:
                out.append(f"{rel.as_posix()}:1: パスの部分 {hit} が ASF の物の名で始まる")
    return out


RULES = {
    "E2": _polyfills_listed,
    "E3": _lib_blind,
    "E4": _block_paths,
    "E8": _no_asf,
    "E9": _names,
    "E12": _no_timeouts,
    "E13": _lang_neutral,
    "E14": _no_owner_env,
    "E18": _origin_names,
}
