"""層の決まりの「機械」の行を照らす。`problems(rule, root)` は 1 行に 1 つ `<パス>:<行>: <何が>` を返す（無ければ空）。

決まりの本文と機械の行の置き場:
- E2・E4・E12: `workflows/AGENTS.md`
- E3: `lib/AGENTS.md`
- E8・E9・E13・E14: 根の `AGENTS.md`

字の形でしか見ないので、次は人が見る:
- E3: 節の id（字の形で見分けられない）
- E4: `pathlib` などで部品を継いで組むパス
- E12: script の中で置く期限
"""
import posixpath
import re
from collections.abc import Callable
from pathlib import Path

import yaml

BOUNDARY = "boundary.py"
POLYFILL_ROW = re.compile(r"workflows/\.shared/([^\s`（）()、・。]+)(`?（予定）)?")

ARCHON_WORDS = re.compile(r"(?i:archon)|ARTIFACTS_DIR|TYPED_ARTIFACTS_FILE|output_type")
LAYER_IMPORT = re.compile(r"^\s*(from|import)\s+(workflows|bin)\b")

# 根の AGENTS.md の「リポジトリの形」の木と合わせる。
BLOCKS = ("line", "judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")
RELATIVE_PATH = re.compile(r"(?:\.\./)+[^\s'\"`)]*")

FOREIGN_PREFIX = "works-factory-"
CALL_KEYS = ("include", "workflow")

NO_DEADLINE = "1728000000"
DEADLINE_KEYS = ("timeout", "idle_timeout")
YAML_INT = "tag:yaml.org,2002:int"

# 持ち主の決め lang-neutral により、事実上の標準の形式（junit など）は表に入れない。
LANG_WORDS = (
    "pytest", "unittest", "jest", "vitest", "mocha", "rspec", "minitest", "phpunit",
    "go test", "cargo test", "npm test", "yarn test", "pnpm test", "gradle", "maven", "mvn", "tox", "nox",
    "python", "javascript", "typescript", "ruby", "rust", "golang", "java", "kotlin", "php", "swift", "perl", "scala",
)
LANG_WORD = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(w) for w in LANG_WORDS) + r")(?![A-Za-z0-9_])", re.I
)

OWNER_ENV = ("raiki61", "claude-code-oauth-", "/Users/")


def problems(rule: str, root: Path) -> list[str]:
    try:
        check = RULES[rule]
    except KeyError:
        raise ValueError(f"知らない決まり: {rule}（{', '.join(RULES)} のどれか）") from None
    return check(Path(root))


def _files(root: Path, *parts: str):
    base = root.joinpath(*parts)
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _lines(path: Path) -> list[str] | None:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return None


def _grep(root: Path, paths, *checks: tuple[re.Pattern, Callable[[re.Match], str]]) -> list[str]:
    """各 (正規表現, 当たりを文にする関数) を、ファイルの順・行の順に当てる"""
    out = []
    for path in paths:
        for number, line in enumerate(_lines(path) or [], 1):
            for pattern, what in checks:
                for match in pattern.finditer(line):
                    out.append(f"{_rel(root, path)}:{number}: {what(match)}")
    return out


def _workflow_yamls(root: Path):
    for path in _files(root, "workflows"):
        if path.suffix in (".yaml", ".yml") and "fixtures" not in path.relative_to(root).parts:
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
    """入れ子のどこでも、mapping の鍵が scalar の (鍵, 値の node) を出す"""
    if isinstance(node, yaml.MappingNode):
        for key, value in node.value:
            if isinstance(key, yaml.ScalarNode):
                yield key.value, value
            yield from _pairs(value)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _pairs(item)


def _top(node, key: str):
    if isinstance(node, yaml.MappingNode):
        for k, value in node.value:
            if isinstance(k, yaml.ScalarNode) and k.value == key:
                return value
    return None


def _line(node) -> int:
    return node.start_mark.line + 1


def _polyfills_listed(root: Path) -> list[str]:
    registry = root / "docs" / "archon-polyfills.md"
    listed = {}
    rows = _lines(registry) if registry.is_file() else []
    for number, line in enumerate(rows or [], 1):
        if line.strip().startswith("- 埋め:"):
            for match in POLYFILL_ROW.finditer(line):
                listed.setdefault(match[1], (number, bool(match[2])))
    out = []
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
    paths = [p for p in _files(root, "lib") if _rel(root, p) != "lib/AGENTS.md"]
    return _grep(
        root,
        paths,
        (ARCHON_WORDS, lambda m: f"Archon の名 {m[0]}"),
        (LAYER_IMPORT, lambda m: f"{m[2]} の中の物を import する"),
    )


def _block_paths(root: Path) -> list[str]:
    out = []
    workflows = root / "workflows"
    blocks = sorted(p.name for p in workflows.iterdir() if p.is_dir() and p.name != ".shared") if workflows.is_dir() else []
    for own in blocks:
        others = [b for b in BLOCKS if b != own]
        named = re.compile(r"workflows/(" + "|".join(re.escape(b) for b in others) + r")/")
        allowed = (f"workflows/{own}/", "lib/", "workflows/.shared/")
        for path in _files(root, "workflows", own, "scripts"):
            rel = _rel(root, path)
            here = posixpath.dirname(rel)
            for number, line in enumerate(_lines(path) or [], 1):
                for match in named.finditer(line):
                    out.append(f"{rel}:{number}: ほかのブロック {match[1]} を指す")
                for match in RELATIVE_PATH.finditer(line):
                    target = match[0]
                    first = next((part for part in target.split("/") if part not in ("..", "")), "")
                    resolved = posixpath.normpath(posixpath.join(here, target)) + "/"
                    if first in others:
                        out.append(f"{rel}:{number}: 相対パス {target} がほかのブロック {first} を指す")
                    elif not resolved.startswith(allowed):
                        out.append(f"{rel}:{number}: 相対パス {target} が lib/・workflows/.shared/・自分のブロックの外を指す")
    return out


def _no_asf(root: Path) -> list[str]:
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for key, value in _pairs(document):
                if key not in CALL_KEYS:
                    continue
                if not isinstance(value, yaml.ScalarNode):
                    out.append(f"{rel}:{_line(value)}: {key}: の形が読めない")
                elif not value.value.startswith(FOREIGN_PREFIX):
                    out.append(f"{rel}:{_line(value)}: {key}: の値 {value.value} が {FOREIGN_PREFIX} で始まらない")
    return out


def _names(root: Path) -> list[str]:
    out = []
    workflows = root / "workflows"
    if not workflows.is_dir():
        return out
    for folder in sorted(p for p in workflows.iterdir() if p.is_dir() and p.name != ".shared"):
        expected = f"{FOREIGN_PREFIX}{folder.name}"
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
            for key, value in _pairs(document):
                if key in DEADLINE_KEYS and not (
                    isinstance(value, yaml.ScalarNode) and value.tag == YAML_INT and value.value == NO_DEADLINE
                ):
                    out.append(f"{rel}:{_line(value)}: {key} が {NO_DEADLINE} でない")
            nodes = _top(document, "nodes")
            for node in nodes.value if isinstance(nodes, yaml.SequenceNode) else []:
                if not isinstance(node, yaml.MappingNode):
                    continue
                keys = {k.value for k, _ in node.value if isinstance(k, yaml.ScalarNode)}
                if keys & {"script", "bash"} and "timeout" not in keys:
                    out.append(f"{rel}:{_line(node)}: script・bash の節に timeout が無い（Archon の既定の期限が当たる）")
                if keys & {"prompt", "command"} and "idle_timeout" not in keys:
                    out.append(f"{rel}:{_line(node)}: AI の節に idle_timeout が無い（Archon の既定の期限が当たる）")
    return out


def _lang_neutral(root: Path) -> list[str]:
    commands = []
    workflows = root / "workflows"
    if workflows.is_dir():
        for folder in sorted(p for p in workflows.iterdir() if p.is_dir()):
            commands += _files(folder, "commands")
    lib = [
        p for p in _files(root, "lib")
        if _rel(root, p) != "lib/AGENTS.md" and not _rel(root, p).startswith("lib/tests/")
    ]
    return _grep(root, sorted(commands) + lib, (LANG_WORD, lambda m: f"言語か実行器の名 {m[0]}"))


def _no_owner_env(root: Path) -> list[str]:
    pattern = re.compile("|".join(re.escape(s) for s in OWNER_ENV))
    paths = [p for layer in ("bin", "workflows", "lib") for p in _files(root, layer)]
    return _grep(root, paths, (pattern, lambda m: f"持ち主の環境の字 {m[0]}"))


RULES = {
    "E2": _polyfills_listed,
    "E3": _lib_blind,
    "E4": _block_paths,
    "E8": _no_asf,
    "E9": _names,
    "E12": _no_timeouts,
    "E13": _lang_neutral,
    "E14": _no_owner_env,
}
