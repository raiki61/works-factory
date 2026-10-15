"""層の決まりの「機械」の行を照らす。`problems(rule, root)` は 1 行に 1 つ `<パス>:<行>: <何が>` を返す（無ければ空）。

字の形でしか見ないので、次は人が見る:
- E3: 節の id（字の形で見分けられない）
- E4: `pathlib` などで部品を継いで組むパス
- E12: script の中で置く期限
"""
import ast
import functools
import json
import posixpath
import re
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from bin._lib import isolate
from bin._lib.place import WORKFLOW_FOLDER
from lib import answer


def word(pattern: str) -> re.Pattern:
    """pattern（正規表現の断片）を語として当てる式。前後が `[\\w\\-/.]` の時は語の一部（plan-fields.json・fix_plan・plan/r1）で数えない"""
    return re.compile(rf"(?<![\w\-/.])(?:{pattern})(?![\w\-/.])")


BOUNDARY = "boundary.py"
# 「（予定）」は語の境の外に置く。後ろに字が続いても（予定）を落とさない
POLYFILL_ROW = re.compile(word(r"((?:workflows|bin|lib|tests)/[^\s`（）()、・。]+)").pattern + r"(`?（予定）)?")
POLYFILL_FOLDERS = (("workflows", ".shared"), ("bin", "_lib"))

ARCHON_WORDS = re.compile(
    r"(?i:archon)|ARTIFACTS_DIR|TYPED_ARTIFACTS_FILE|output_type|(?<![A-Za-z0-9_])INPUTS_[A-Z0-9_]+|WORKFLOW_ID|\$LOOP_PREV"
    r"|loop_group|\$[A-Za-z_][\w-]*\.output\b"
)
LAYER_IMPORT = re.compile(r"^\s*(from|import)\s+(workflows|bin)\b")

# まだ木に無いブロックを指す字も捕まえるための名の表。根の AGENTS.md の「リポジトリの形」の木との一致は test_block_paths が縛る。木に在るブロックは木から読む。
BLOCKS = ("line", "chain", "judge", "plan", "plan-review", "fix", "test-gate", "eyes", "report", "merge")
RELATIVE_PATH = re.compile(r"(?:\.\./)+[^\s'\"`)]*")

LIB = Path(__file__).resolve().parents[2] / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import chain  # noqa: E402  （周の鎖の周の数の上限 MAX_ROUNDS）
import depth  # noqa: E402  （深さの段の表 TIERS）
# INPUTS_{…} を組む内包の for が回す lib の部品の定数（`for name in fixboard.PREP_INPUTS`）
BUILT_FROM = re.compile(r"INPUTS_\{[^}\n]*\}[^\n]*\bfor\s+\w+\s+in\s+([a-z_][a-z0-9_]*)\.([A-Z][A-Z0-9_]*)\b")
OURS = json.loads((Path(__file__).resolve().parents[2] / "pack.json").read_text(encoding="utf-8"))["ours"]
OURS_PREFIX = OURS["name_prefix"]
OURS_PACK = OURS["pack"]
LINE_FOLDER = OURS["line"].removeprefix(OURS_PREFIX)
LINE_YAML = f"workflows/{LINE_FOLDER}/{OURS['line']}.yaml"
# 周の鎖。メイングラフを workflow: のノードで子の run として起こす一番上の親のグラフ（人が Archon の命令で名指して起こす）
CHAIN_FOLDER = "chain"
TOP_FOLDERS = (LINE_FOLDER, CHAIN_FOLDER)
CALL_KEYS = ("include", "workflow")

NO_DEADLINE = "1728000000"
# 止めた Archon（docs/design.md の「語」）の節の種類の鍵の全部と、その種類の節に Archon が既定の期限を当てる鍵（workflows/AGENTS.md の E12）。
# ここに無い種類の節は赤にする。鍵は tests/shared/test_archon_contract.py が Archon の源に照らす（種類が足されたら赤になる）。
# 足す時は期限を持つかを確かめてから足す。
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

# 決まりごとに照らしから外すパス。`/` で終わる行はそのフォルダの下の全部。`<パス>#<字>` の行は、そのパスの問題のうちその字を名指す物
# だけ。どの行も本物の木の何かに当たる（stale_allowances）。
ALLOWED = {
    "E2": (
        # bin/_lib/ の埋めでない物（起動の認証と隔離を今の works から持ってきた入口の部品。bin/AGENTS.md の E15）。埋めは名簿の行が持つ
        "bin/_lib/auth_launch.py",
        "bin/_lib/claude_auth.py",
        "bin/_lib/copyledger.py",
        "bin/_lib/hostgh.py",
        "bin/_lib/isolate.py",
        "bin/_lib/pack.py",
        "bin/_lib/spseam.py",
        "bin/_lib/startpoint.py",
        "bin/_lib/testcmd_check.py",
        "bin/_lib/borrow/",
        "bin/_lib/no-post-bin/",
    ),
    "E3": (
        "lib/AGENTS.md",
        # 役に届く文に $LOOP_PREV が無いことを確かめる試験の字。語の不在を試すので残る
        "lib/tests/test_blk_fix.py#$LOOP_PREV",
        "lib/tests/test_blk_plan.py#$LOOP_PREV",
        "lib/tests/test_fix_rules.py#$LOOP_PREV",
    ),
    "E5": (
        # 宣言したが誰も読まない入力（K12）。行ごとに外す区分の issue
        "workflows/plan-review/works-factory-plan-review.yaml#units",  # 区分 P #120
    ),
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
    return [line for line in check(Path(root)) if not _allowed(rule, line)]


def stale_allowances(root: Path) -> list[str]:
    """`ALLOWED` の行のうち、木の何にも当たらない物"""
    root = Path(root)
    found = {}

    def hits(rule: str, entry: str) -> bool:
        path, _, word = entry.partition("#")
        if word:
            found.setdefault(rule, RULES[rule](root))
            return any(_matches(entry, line) for line in found[rule])
        return any(_files(root, path)) if path.endswith("/") else (root / path).is_file()

    return [f"{rule}: {entry} が木の何にも当たらない" for rule, entries in ALLOWED.items() for entry in entries if not hits(rule, entry)]


def _allowed(rule: str, line: str) -> bool:
    return any(_matches(entry, line) for entry in ALLOWED.get(rule, ()))


def _matches(entry: str, line: str) -> bool:
    """問題の行 `<パス>:<行>: <何が>` が許しの行に当たるか"""
    path, _, word = entry.partition("#")
    rel, _, rest = line.partition(":")
    if not (rel.startswith(path) if path.endswith("/") else rel == path):
        return False
    return not word or re.search(rf"(?<!\S){re.escape(word)}(?!\S)", rest.partition(": ")[2]) is not None


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


YAML_MERGE = "tag:yaml.org,2002:merge"


def _pairs(node):
    """mapping の (鍵, 値)。merge key `<<:` は Archon（Bun.YAML）の読み方と同じく解き、字で書いた鍵が勝つ"""
    if not isinstance(node, yaml.MappingNode):
        return
    own = [(key.value, value) for key, value in node.value if isinstance(key, yaml.ScalarNode) and key.tag != YAML_MERGE]
    merged = [value for key, value in node.value if key.tag == YAML_MERGE]
    sources = [m for value in merged for m in (value.value if isinstance(value, yaml.SequenceNode) else [value])]
    seen = {key for key, _ in own}
    for source in sources:
        for key, value in _pairs(source):
            if key not in seen:
                seen.add(key)
                yield key, value
    yield from own


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
    return dict(_pairs(node)).get(key)


def _line(node) -> int:
    return node.start_mark.line + 1


def nodes(root: Path, rel: str) -> list:
    """root/rel の工程の節の node（`loop_group` の中も）。読めない YAML は ValueError"""
    documents, broken = _documents(root, root / rel)
    if broken:
        raise ValueError(broken[0])
    return [node for document in documents for node in _nodes(document)]


def text_nodes(text: str) -> list:
    """YAML の字の工程の節の node（`loop_group` の中も）。読めない YAML は yaml.YAMLError"""
    return [node for document in yaml.compose_all(text, Loader=yaml.SafeLoader) for node in _nodes(document)]


def includes(root: Path, rel: str) -> list[str]:
    """root/rel の工程の `include:` の先の工程の名（`loop_group` の中も）。読めない YAML は ValueError"""
    return [value.value for node in nodes(root, rel) if isinstance(value := _top(node, "include"), yaml.ScalarNode)]


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
        if not planned and not (root / name).exists():
            out.append(f"{_rel(root, registry)}:{number}: 名簿の {name} が木に無い")
    for folder in POLYFILL_FOLDERS:
        for path in _files(root, *folder):
            name = _rel(root, path)
            if name != f"workflows/.shared/{BOUNDARY}" and name not in listed:
                out.append(f"{name}:1: 名簿にも境の口にも当たらない")
    return out


def _lib_blind(root: Path) -> list[str]:
    return _grep(
        root,
        _files(root, "lib"),
        (ARCHON_WORDS, lambda m: f"Archon の名 {m[0]}"),
        (LAYER_IMPORT, lambda m: f"{m[2]} の中の物を import する"),
    )


IMPORT_NAMES = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))")


def _block_paths(root: Path) -> list[str]:
    """ブロックの `scripts/` の字と、YAML の字（直に書いた script）を照らす。

    YAML の中の script は Archon が写し取った所のどこから走るかが字から分からないので、相対パスは行き先のブロックの名だけを見る。
    script は同じ `scripts/` の別の script を import せず（K8）、script の名は lib のモジュールの名と重ならない（script のフォルダが
    sys.path の頭に来るので、`import <名>` が lib の物でなく script を読む。K19）。
    """
    out = _script_imports(root) + _script_names(root) + _input_producers(root)
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


MAIN_GRAPH_WORD = "メイングラフ"
OUTPUT_OF_NODE = re.compile(r"\$([\w-]+)\.output")


def _top_hyphen_ids(root: Path) -> set[str]:
    """一番上のグラフ（line・chain）の節の id のうち `-` を含む物。`-` の無い id は普通の語と重なるので入れない"""
    ids = set()
    for name in TOP_FOLDERS:
        _, top = _workflow_doc(root / "workflows" / name)
        if top is not None:
            ids |= {i.value for node in _nodes(top) if isinstance(i := _top(node, "id"), yaml.ScalarNode) and "-" in i.value}
    return ids


def _input_producers(root: Path) -> list[str]:
    """ブロック（一番上のグラフ line・chain を除く）の inputs: の description が、値の作り手を名指さない。

    名指しに数えるのは、`$<id>.output`（そのブロック自身の YAML の節の id は兄弟の参照なので数えない）・語「メイングラフ」・ほかのブロックの名
    （`works-factory-` の頭が付いてもよい）・一番上のグラフの節の id のうち `-` を含む物。結びはメイングラフの with: だけが持つ。
    description は YAML の値として読むので、flow の形も `>-`・`|` の複数行の形も 1 つの字になる。
    説明の無い入力は名指す字も無いので見ない。字でない（mapping の）説明は中に字を隠せるので、問題の行にする
    """
    folders = _blocks(root)
    top_ids = _top_hyphen_ids(root)
    ids = word("|".join(re.escape(i) for i in sorted(top_ids, key=len, reverse=True))) if top_ids else None
    out = []
    for folder in folders:
        if folder.name in TOP_FOLDERS:
            continue
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        own_ids = {i.value for node in _nodes(document) if isinstance(i := _top(node, "id"), yaml.ScalarNode)}
        others = (set(BLOCKS) | {p.name for p in folders}) - {folder.name}
        names = word(rf"(?:{re.escape(OURS_PREFIX)})?(?:" + "|".join(re.escape(n) for n in sorted(others, key=len, reverse=True)) + ")")
        for key, spec in _pairs(_top(document, "inputs")):
            description = _top(spec, "description")
            if description is None:
                continue
            if not isinstance(description, yaml.ScalarNode):
                out.append(f"{_rel(root, path)}:{_line(description)}: 入力 {key} の説明が字でない")
                continue
            text = description.value
            found = [m[0] for m in OUTPUT_OF_NODE.finditer(text) if m[1] not in own_ids]
            found += [MAIN_GRAPH_WORD] * (MAIN_GRAPH_WORD in text)
            found += [m[0] for m in names.finditer(text)]
            found += [m[0] for m in ids.finditer(text)] if ids else []
            for hit in found:
                out.append(f"{_rel(root, path)}:{_line(description)}: 入力 {key} の説明が作り手 {hit} を名指す")
    return out


def sibling_imports(root: Path) -> tuple[list[tuple[Path, int, str]], list[str]]:
    """ブロックの scripts/ の script が同じ scripts/ のほかの script を import する所（script、行、import する script の名）と、
    読めないファイルの問題の行。K8 と、節の script どうしの import の試験（tests/workflows/test_script_imports.py）が共に読む"""
    found, broken = [], []
    for folder in _blocks(root):
        scripts = folder / "scripts"
        siblings = {p.stem for p in scripts.glob("*.py")} if scripts.is_dir() else set()
        for path in sorted(scripts.glob("*.py")) if scripts.is_dir() else []:
            lines, unread = _lines(root, path)
            broken += unread
            for number, line in enumerate(lines, 1):
                match = IMPORT_NAMES.match(line)
                if not match:
                    continue
                names = [match[1]] if match[1] else [name.strip() for name in match[2].split(",")]
                for name in names:
                    head = name.split(".")[0]
                    if head in siblings - {path.stem}:
                        found.append((path, number, head))
    return found, broken


def _script_imports(root: Path) -> list[str]:
    found, broken = sibling_imports(root)
    return broken + [f"{_rel(root, path)}:{number}: 同じ scripts/ の script {head} を import する" for path, number, head in found]


def _script_names(root: Path) -> list[str]:
    lib = root / "lib"
    modules = {p.stem for p in lib.glob("*.py")} if lib.is_dir() else set()
    out = []
    for folder in _blocks(root):
        scripts = folder / "scripts"
        for path in sorted(scripts.glob("*.py")) if scripts.is_dir() else []:
            if path.stem in modules:
                out.append(f"{_rel(root, path)}:1: script の名 {path.stem} が lib/{path.stem}.py と同じ")
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


OUTPUT_REF = re.compile(r"\$(?:LOOP_PREV\.)?([A-Za-z_][\w-]*)\.output\.([A-Za-z_]\w*)")


def _workflow_doc(folder: Path):
    """フォルダの工程 `works-factory-<フォルダの名>.yaml` の (パス, 頭の node)。無い・読めなければ (パス, None)"""
    path = folder / f"{OURS_PREFIX}{folder.name}.yaml"
    if not path.is_file():
        return path, None
    documents, broken = _documents(folder.parents[1], path)
    return path, (documents[0] if documents and not broken else None)


def _scalars(node):
    """node の下の字の値を全部（鍵は除く）"""
    if isinstance(node, yaml.ScalarNode):
        yield node.value
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _scalars(item)
    elif isinstance(node, yaml.MappingNode):
        for _, value in node.value:
            yield from _scalars(value)


def _line_reads(root: Path) -> dict:
    """線が `$<include の id>.output.<欄>` で読む欄を、差し込んだ工程の名ごとに {名: {欄…}}"""
    path = root / LINE_YAML
    documents, broken = _documents(root, path) if path.is_file() else ([], [])
    if broken or not documents:
        return {}
    document = documents[0]
    target = {
        _top(node, "id").value: value.value
        for node in _nodes(document)
        if isinstance(value := _top(node, "include"), yaml.ScalarNode) and isinstance(_top(node, "id"), yaml.ScalarNode)
    }
    reads = {}
    for text in _scalars(_top(document, "nodes")):
        for match in OUTPUT_REF.finditer(text):
            if match[1] in target:
                reads.setdefault(target[match[1]], set()).add(match[2])
    return reads


def _block_returns(root: Path) -> list[str]:
    """返りの欄の読み手に加えて、ブロックの入力の読み手（K12）と、輪の中の役が自分の with: を結ばないこと（K5）も照らす"""
    out = _inputs_read(root) + _loop_roles(root)
    reads = _line_reads(root)
    for folder in _blocks(root):
        if folder.name == LINE_FOLDER:
            continue
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        rel = _rel(root, path)
        returns, outcome = _top(document, "returns"), _top(document, "outcome_field")
        for key, value in (("returns", returns), ("outcome_field", outcome)):
            if not isinstance(value, yaml.ScalarNode):
                out.append(f"{rel}:1: {key}: が無い")
        if not isinstance(returns, yaml.ScalarNode):
            continue
        node = next((n for n in _nodes(document) if getattr(_top(n, "id"), "value", None) == returns.value), None)
        schema = _top(node, "output_format")
        if not isinstance(schema, yaml.MappingNode):
            out.append(f"{rel}:{_line(node) if node is not None else _line(returns)}: 返す節 {returns.value} に output_format が無い")
            continue
        required = [item.value for item in getattr(_top(schema, "required"), "value", []) if isinstance(item, yaml.ScalarNode)]
        if isinstance(outcome, yaml.ScalarNode) and outcome.value not in required:
            out.append(f"{rel}:{_line(outcome)}: outcome_field の欄 {outcome.value} が返す節の required に無い")
        if folder.name == CHAIN_FOLDER:   # 鎖の出力を読むのは人（workflow get）で、グラフの読み手は無い
            continue
        read = reads.get(f"{OURS_PREFIX}{folder.name}", set())
        for key, value in _pairs(_top(schema, "properties")):
            if key not in read:
                out.append(f"{rel}:{_line(value)}: 返りの欄 {key} に読み手が無い（線の with:・when:・返しの節の from の誰も読まない）")
    return out


def script_reads(text: str, name: str, lib: Path = LIB) -> bool:
    """script の字が入力 name を読むか。Archon は名の - を _ にして大文字の INPUTS_<名> で渡す。`INPUTS_{…}` を組んで読む script は
    名の字を持つ物と、INPUTS_{…} を組む内包の for で名を持つ lib の部品の字の並びの定数（BUILT_FROM。部品は lib の下）を回す物を読み手に数える"""
    if re.search(rf"INPUTS_{re.escape(name.replace('-', '_').upper())}(?![A-Z0-9_])", text):
        return True
    if "INPUTS_{" not in text:
        return False
    if re.search(rf"[\"']{re.escape(name)}[\"']", text):
        return True
    return any(name in _lib_names(lib / f"{module}.py", const) for module, const in BUILT_FROM.findall(text))


@functools.cache
def _lib_names(path: Path, const: str) -> tuple:
    """lib の部品 path の頭で const に置いた字の並び（無い・字の並びでなければ空）"""
    if not path.is_file():
        return ()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == [const]:
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return ()
            return value if isinstance(value, tuple) and all(isinstance(v, str) for v in value) else ()
    return ()


def _role_reads(text: str, name: str) -> bool:
    return re.search(rf"\$INPUTS\.{re.escape(name)}(?![\w-])", text) is not None


def _inputs_read(root: Path) -> list[str]:
    """ブロックの inputs: の名は、そのブロックの script が INPUTS_<名> で読むか、役の指示書（commands/ と YAML の prompt:）が
    $INPUTS.<名> で読む（宣言しただけで誰も読まない入力を残さない）。YAML の with: で script へ渡すだけの字は読み手に数えない。
    逆向きに、script が INPUTS_{…} を組んで回す lib の部品の定数（BUILT_FROM）の名は、どれもそのブロックの inputs: に在る
    （宣言の無い名は Archon が渡さず、script は空の字を黙って読む）"""
    out = []
    for folder in _blocks(root):
        if folder.name in TOP_FOLDERS:   # 一番上のグラフの入力は起動が渡し、鎖はメイングラフへ写すだけ（tests/workflows/test_chain.py が縛る）
            continue
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        scripts = {p: "\n".join(_lines(root, p)[0]) for p in _files(folder, "scripts") if p.suffix == ".py"}
        roles = [p.read_text(encoding="utf-8", errors="replace") for p in _files(folder, "commands")]
        roles += [value.value for node in _nodes(document) if isinstance(value := _top(node, "prompt"), yaml.ScalarNode)]
        for key, value in _pairs(_top(document, "inputs")):
            if not any(script_reads(text, key, root / "lib") for text in scripts.values()) \
                    and not any(_role_reads(text, key) for text in roles):
                env = "INPUTS_" + key.replace("-", "_").upper()
                out.append(f"{_rel(root, path)}:{_line(value)}: 入力 {key} に読み手が無い（script の {env} も指示書の $INPUTS.{key} も無い）")
        declared = {key for key, _ in _pairs(_top(document, "inputs"))}
        for script, text in scripts.items():
            for module, const in BUILT_FROM.findall(text):
                for name in _lib_names(root / "lib" / f"{module}.py", const):
                    if name not in declared:
                        out.append(f"{_rel(root, script)}:1: {module}.{const} の名 {name} が {_rel(root, path)} の inputs: に無い"
                                   f"（INPUTS_{name.upper()} は空の字で届く）")
    return out


def _loop_roles(root: Path) -> list[str]:
    """輪（loop_group）の中の役の節は自分の with: を結ばない。前の周の値は輪の頭の script の節が $LOOP_PREV で結んで返し、役はその
    出力を読む（PR #100。Archon の include-expander.ts 566・579・596・627 行: 役の with: は include の時に既定の字で固まる）"""
    out = []
    for path in _workflow_yamls(root):
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for group in _nodes(document):
                for node in getattr(_top(_top(group, "loop_group"), "nodes"), "value", []):
                    if any(_top(node, kind) is not None for kind in ROLE_KINDS) and _top(node, "with") is not None:
                        ident = getattr(_top(node, "id"), "value", "?")
                        out.append(f"{_rel(root, path)}:{_line(node)}: 輪の中の役 {ident} が自分の with: を結ぶ")
    return out


# 外への書き込み（E6）: GitHub への gh と、対象のリポジトリの main への git push・git merge。
OUTWARD = re.compile(r"(?<![\w./-])gh(?![\w./-])|\bgit[\"'\s,]+(?:push|merge)\b")
NAMED_SCRIPT = re.compile(r"[\w.-]+")


def node_scripts(folder: Path, node) -> list[Path]:
    """名前の script の節（`script: <名>`）の走らせる folder/scripts/<名>.* のファイル。そうでない節は空"""
    value = _top(node, "script")
    if not (isinstance(value, yaml.ScalarNode) and NAMED_SCRIPT.fullmatch(value.value) and (folder / "scripts").is_dir()):
        return []
    return sorted((folder / "scripts").glob(f"{value.value}.*"))


def _node_code(folder: Path, node) -> str | None:
    """節の走らせる字（直に書いた script・bash か、名前の script のファイルの中身）。script・bash の節でなければ None"""
    for key in CODE_KINDS:
        value = _top(node, key)
        if isinstance(value, yaml.ScalarNode):
            if key == "script" and NAMED_SCRIPT.fullmatch(value.value):
                return "".join(p.read_text(encoding="utf-8", errors="replace") for p in node_scripts(folder, node))
            return value.value
    return None


def _outward_write(root: Path) -> list[str]:
    out = []
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        writers = [node for node in _nodes(document) if OUTWARD.search(_node_code(folder, node) or "")]
        if len(writers) > 1:
            names = "・".join(getattr(_top(n, "id"), "value", "?") for n in writers)
            out.append(f"{_rel(root, path)}:{_line(writers[1])}: 外へ書く節が {len(writers)} つ（{names}）。ブロックに 1 つまで")
    return out


# 読むだけの節と役の節の決まり（E7）。
# 役の節（prompt:・command:）の印は道具から導く: allowed_tools に作業ツリーを変える道具（TREE_CHANGERS）が無い役は
# mutates_checkout: false を書き、在る役は書かない（元 works/tests/test_yaml_rules.py の TREE_CHANGERS と keep_checkout）。
# 外れは KEEP_CHECKOUT の役だけ（変える道具を持つが作業ツリーは変えない役で、false で Archon に守らせる）。
# script・bash の節は全部 false を書く。外れは CHANGE_CHECKOUT の節だけ（作業ツリーを変えるか、印を足すと振る舞いが変わる節）。
ROLE_KINDS = ("prompt", "command")
CODE_KINDS = ("script", "bash")
TREE_CHANGERS = frozenset({"Bash", "Edit", "Write"})
KEEP_CHECKOUT = {
    ("judge", "judge-verify"): "単位ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない（元の keep_checkout）",
    ("plan-review", "plan-review"): "項目ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない（元の keep_checkout）",
    ("test-gate", "ci"): "Bash でテストを走らせるが作業ツリーは書かない。sandbox の denyWrite が書き込みを止め、false と ci-accept の"
                         "作業ツリーの比べが重ねて守る（#69・#293）",
}
CHANGE_CHECKOUT = {
    ("line", "start"): "始めの記録を run の置き場に書くだけだが、今の線は印を持たない。足すと Archon の照らしが増えて振る舞いが変わるので部分 0 では足さない",
    ("judge", "spec-freeze"): "人が通した受け入れ条件を作業ツリーで /bin/sh -c で走らせる（lib/judge_accept._spec_run）",
    ("fix", "group-start"): "親の姿の木を作業ツリーと index に写す（groups.adopt_tree）",
    ("fix", "join"): "並べた組の子の差分を親の作業ツリーへ当て、当たらない組は戻す（unittrees.apply）",
    ("fix", "clash-prep"): "join が確かめ直しの赤で戻した組の控えの差分を作業ツリーへ当て直し、当たらなければ当てる前の木へ戻す（clash.stage・settle_parked）",
    ("fix", "clash-accept"): "合わせ役の直しが通らなければ当て直す前の木へ戻す（clash.settle_parked）",
    ("fix", "clash-ruled-prep"): "直す裁定を受けた組の控えの差分を作業ツリーへ当て直す（clash.stage の段 ruled）",
    ("fix", "clash-ruled-accept"): "裁定の後の合わせ役の直しが通らなければ当て直す前の木へ戻す（clash.settle_parked の段 ruled）",
    ("fix", "clean"): "修正役が残した git の無視するファイルを消す（leftovers.remove_new_ignored）",
    ("fix", "tdd-step"): "諦めた単位を単位の頭の木に戻す（tddloop.step）",
    ("fix", "fix-accept"): "3 回目の拒否で名指しの単位を戻す（fixboard.accept_reply）",
    ("fix", "fix-ruled-accept"): "3 回目の拒否で名指しの単位を戻す（fixboard.accept_reply の ruled）",
    ("fix", "refix-accept"): "3 回目の拒否で手直しを戻す（refix.accept_fix）",
    ("fix", "refix2-accept"): "3 回目の拒否で手直しを戻す（refix.accept_fix）",
    ("test-gate", "run"): "対象のテストを作業ツリーで走らせる（declared_checks.run_ci）",
    **{("chain", f"round-{k}-commit"): "周の結果を親の run の枝へ commit する（index と HEAD を変える）" for k in range(1, chain.MAX_ROUNDS + 1)},
}
# 役の節に要る鍵（K18。元 works/tests/test_yaml_rules.py の決まり）: settingSources: [user]・閉じた sandbox・道具の表の中の allowed_tools
ROLE_TOOLS = frozenset({"Read", "Grep", "Glob", "Edit", "Write", "Bash", "WebSearch", "WebFetch", "Agent", "Skill"})
CLOSED_SANDBOX = (("enabled", "true"), ("allowUnsandboxedCommands", "false"))
# Bash を持ち Edit・Write を持たない役の sandbox の denyWrite に書く場所（#293）。~ は起動が隔離した HOME で、
# その隣が Archon の家＝全部の run の worktree と artifacts。相対のパス '.' は cwd でなく設定の一時ファイルのフォルダに解かれ、
# 作業ツリーを塞がない（実測 2026-10-13）。包み（workflows/.shared/fence.py。埋め P5）はこの値を読むだけの役の印に読み、起こす直前に
# cwd・共通の .git・worktree の根などを足す（#309）。包みの無い起動にはこの値だけが残る。Edit・Write を持つ役（直す役・書く役）に
# 書かないのは、作業ツリーを変えるのがその役の仕事で、cwd を禁じると仕事ができないため（今の works の柵も道具に書き込みの無い役だけに
# 掛けた: role_run.py の tooled_permission と DELEGATE_TOOLS）
NO_TREE_WRITE = f"~/../{isolate.DIRS['ARCHON_HOME']}"
YAML_BOOL = "tag:yaml.org,2002:bool"


def _is_bool(node, word: str) -> bool:
    return isinstance(node, yaml.ScalarNode) and node.tag == YAML_BOOL and node.value.lower() == word


def _readonly_nodes(root: Path) -> list[str]:
    out = []
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        rel = _rel(root, path)
        seen = set()
        for node in _nodes(document):
            ident = getattr(_top(node, "id"), "value", "")
            seen.add(ident)
            at = f"{rel}:{_line(node)}"
            marked = _is_bool(_top(node, "mutates_checkout"), "false")
            if _top(node, "loop") is not None:
                out.append(f"{at}: 節 {ident} が loop: で書かれた（Archon は loop: の節の mutates_checkout を無視する。loop_group で書く）")
            if any(_top(node, kind) is not None for kind in ROLE_KINDS):
                tools = _top(node, "allowed_tools")
                names = {item.value for item in tools.value if isinstance(item, yaml.ScalarNode)} if isinstance(tools, yaml.SequenceNode) else None
                out += _role_settings(at, ident, node, names)
                if names is not None and names & TREE_CHANGERS == {"Bash"}:
                    out += _tree_write_denied(at, ident, node)
                changer = names is None or bool(names & TREE_CHANGERS)
                keep = (folder.name, ident) in KEEP_CHECKOUT
                if marked and changer and not keep:
                    out.append(f"{at}: 作業ツリーを変える道具を持つ役 {ident} に mutates_checkout: false が在る")
                elif not marked and (not changer or keep):
                    out.append(f"{at}: 読むだけの役 {ident} に mutates_checkout: false が無い")
            elif any(_top(node, kind) is not None for kind in CODE_KINDS):
                changes = (folder.name, ident) in CHANGE_CHECKOUT
                if marked and changes:
                    out.append(f"{at}: 表 CHANGE_CHECKOUT の節 {ident} に mutates_checkout: false が在る")
                elif not marked and not changes:
                    out.append(f"{at}: script の節 {ident} に mutates_checkout: false が無い（作業ツリーを変えるなら表 CHANGE_CHECKOUT に訳を書く）")
        for block, ident in KEEP_CHECKOUT:
            if block == folder.name and ident not in seen:
                out.append(f"{rel}:1: 表 KEEP_CHECKOUT が名指した役 {ident} が工程に無い")
    return out


def _role_settings(at: str, ident: str, node, tools) -> list[str]:
    out = []
    sources = _top(node, "settingSources")
    if not (isinstance(sources, yaml.SequenceNode) and [getattr(i, "value", None) for i in sources.value] == ["user"]):
        out.append(f"{at}: 役 {ident} に settingSources: [user] が無い")
    sandbox = _top(node, "sandbox")
    if not all(_is_bool(_top(sandbox, key), word) for key, word in CLOSED_SANDBOX):
        out.append(f"{at}: 役 {ident} の sandbox が閉じていない（enabled: true・allowUnsandboxedCommands: false）")
    if tools is None:
        out.append(f"{at}: 役 {ident} に allowed_tools が無い（無いと全部の道具を持つ）")
    elif tools - ROLE_TOOLS:
        out.append(f"{at}: 役 {ident} の allowed_tools に表 ROLE_TOOLS の外の道具 {sorted(tools - ROLE_TOOLS)}")
    return out


def _tree_write_denied(at: str, ident: str, node) -> list[str]:
    deny = _top(_top(_top(node, "sandbox"), "filesystem"), "denyWrite")
    paths = [item.value for item in deny.value if isinstance(item, yaml.ScalarNode)] if isinstance(deny, yaml.SequenceNode) else []
    out = []
    if NO_TREE_WRITE not in paths:
        out.append(f"{at}: Bash を持つ読むだけの役 {ident} の sandbox に denyWrite: ['{NO_TREE_WRITE}'] が無い（作業ツリーに書ける）")
    if "." in paths:
        out.append(f"{at}: 役 {ident} の denyWrite の '.' は cwd を塞がない（設定の一時ファイルのフォルダに解かれる）")
    return out


# 役の節が持つ retry の形（E19）。on_error を書かないと Archon の既定の transient になり、種類が unknown の失敗を出し直さない
ROLE_RETRY = {"max_attempts": 2, "on_error": "all"}
# 役の節が retry を持たない時に、節の頭の行の真上に書く 1 行の頭（E19）。この後ろに外す理由を書く
NO_RETRY = "# retry なし:"


def _retry_value(retry) -> dict | None:
    if not isinstance(retry, yaml.MappingNode):
        return None
    construct = yaml.constructor.SafeConstructor().construct_object
    return {key: construct(value) if isinstance(value, yaml.ScalarNode) else None for key, value in _pairs(retry)}


def _role_retry(root: Path) -> list[str]:
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        lines, unreadable = _lines(root, path)
        out += broken or unreadable
        for document in documents:
            for node in _nodes(document):
                if not any(_top(node, kind) is not None for kind in ROLE_KINDS):
                    continue
                ident = getattr(_top(node, "id"), "value", "?")
                above = lines[_line(node) - 2].strip() if _line(node) >= 2 else ""
                reason = above.removeprefix(NO_RETRY).strip() if above.startswith(NO_RETRY) else None
                retry = _top(node, "retry")
                if retry is not None and reason is not None:
                    out.append(f"{rel}:{_line(node)}: 役 {ident} は retry を持つのに、外す理由の行が在る")
                elif retry is None and not reason:
                    out.append(f"{rel}:{_line(node)}: 役 {ident} に retry も、真上の「{NO_RETRY} <理由>」の行も無い")
                elif retry is not None and _retry_value(retry) != ROLE_RETRY:
                    out.append(f"{rel}:{_line(retry)}: 役 {ident} の retry が {ROLE_RETRY} でない")
    return out


# 差し込まれるブロックが工程の頭に書かない鍵（E16）。run の形は差し込む一番上の工程が決める。ただし自分の節に approval: を持つ
# ブロックの interactive: true だけは許す: 外すと止めた Archon の単独の validate が警告を出す（workflows/AGENTS.md の E16）
BLOCK_HEAD_KEYS = ("interactive", "worktree", "container", "evidence_policy", "mutates_checkout")


def _gates(root: Path) -> list[str]:
    out = []
    docs = {}
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is not None:
            docs[f"{OURS_PREFIX}{folder.name}"] = (path, document)

    def own_gate(name: str) -> bool:
        return any(_top(n, "approval") is not None for n in _nodes(docs[name][1]))

    def gated(name: str, trail: frozenset = frozenset()) -> bool:
        if name not in docs or name in trail:
            return False
        return own_gate(name) or any(
            gated(value.value, trail | {name})
            for n in _nodes(docs[name][1]) if isinstance(value := _top(n, "include"), yaml.ScalarNode)
        )

    tops = {f"{OURS_PREFIX}{folder}" for folder in TOP_FOLDERS}
    for name, (path, document) in docs.items():
        rel = _rel(root, path)
        if name not in tops:
            for key, value in _pairs(document):
                if key in BLOCK_HEAD_KEYS and not (key == "interactive" and _is_bool(value, "true") and own_gate(name)):
                    out.append(f"{rel}:{_line(value)}: 差し込まれるブロックが工程の頭に {key} を書く")
        elif gated(name):
            if not _is_bool(_top(document, "interactive"), "true"):
                out.append(f"{rel}:1: 人の関所を持つ一番上の工程に interactive: true が無い")
    return out + _gate_words(root)


def _gate_words(root: Path) -> list[str]:
    """関所（approval:）は decisions に答えの語（lib/answer.py の GO_WORDS・STOP_WORDS。STOP_WORDS は REJECT を含む）を全部持ち、on_reject を持たない
    （K10。止めた Archon の core/src/operations/workflow-operations.ts 1625-1700 行: decisions に reject が無いか on_reject が在る
    関所の reject は run の取り消しになり、報告が出ない。ほかの語が無いと、その答えを関所が受けない）。
    輪（loop_group）の本体に関所を置かない（K18。本体が関所で終わる輪の再開は会話を引き継がない。元 works/tests/test_yaml_rules.py 43-45 行）"""
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for node in _nodes(document):
                for inner in getattr(_top(_top(node, "loop_group"), "nodes"), "value", []):
                    if _top(inner, "approval") is not None:
                        out.append(f"{rel}:{_line(inner)}: 輪の本体に関所 {getattr(_top(inner, 'id'), 'value', '?')} を置いた")
                gate = _top(node, "approval")
                if gate is None:
                    continue
                ident = getattr(_top(node, "id"), "value", "?")
                words = {getattr(_top(d, "id"), "value", None) for d in getattr(_top(gate, "decisions"), "value", [])}
                for word in answer.GO_WORDS + answer.STOP_WORDS:
                    if word not in words:
                        out.append(f"{rel}:{_line(node)}: 関所 {ident} の decisions に {word} が無い")
                if _top(gate, "on_reject") is not None or _top(node, "on_reject") is not None:
                    out.append(f"{rel}:{_line(node)}: 関所 {ident} が on_reject を持つ")
    return out


DEPTH_TABLE = "docs/design.md"
DEPTH_HEAD = "### 深さの段の表"
DEPTH_WHEN = re.compile(r"\.output\.\w*depth\w*")
DEPTH_NAMED = re.compile(r"`([^`]+)`")
DEPTH_NONE = "無し"


def _tier_rows(root: Path) -> tuple[list, list[str]]:
    """段の表の行 [(行番号, 段, 省く物, 足す物)] と問題の行"""
    path = root / DEPTH_TABLE
    lines, broken = _lines(root, path) if path.is_file() else ([], [])
    if broken:
        return [], broken
    if DEPTH_HEAD not in lines:
        return [], [f"{DEPTH_TABLE}:1: 「{DEPTH_HEAD}」のセクションが無い"]
    rows, out = [], []
    for n, line in enumerate(lines[lines.index(DEPTH_HEAD) + 1:], start=lines.index(DEPTH_HEAD) + 2):
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "段" or not cells[0].strip("-: "):
            continue
        names = [DEPTH_NAMED.findall(c) for c in cells[1:3]]
        if len(cells) != 4 or any(not found and c != DEPTH_NONE for found, c in zip(names, cells[1:3])):
            out.append(f"{DEPTH_TABLE}:{n}: 表の行が「| 段 | 省く物 | 足す物 | 理由 |」の形でない（省く物・足す物は `名` を並べるか {DEPTH_NONE}）")
            continue
        rows.append((n, cells[0], tuple(names[0]), tuple(names[1])))
    return rows, out


def _graph(root: Path, rel: str) -> list:
    """工程の節の (node, 輪の中か)。読めなければ空"""
    documents, broken = _documents(root, root / rel)
    out = []
    for document in [] if broken else documents:
        body = _top(document, "nodes")
        for item in body.value if isinstance(body, yaml.SequenceNode) else []:
            out.append((item, False))
            out.extend((inner, True) for inner in _nodes(_top(item, "loop_group")))
    return out


def _depth_when(root: Path) -> list[str]:
    """E20: どのノードの when も、出力の深さの欄を読む句（DEPTH_WHEN）を持たない（深さで飛ばす道を作らない）。docs/design.md の
    深さの段の表の行（段・省く物・足す物）は depth.TIERS と等しい"""
    rows, out = _tier_rows(root)
    line = _graph(root, LINE_YAML)
    includes = {}   # サブグラフの YAML → [include の id]
    for node, _ in line:
        name = _scalar(_top(node, "include"))
        if name.startswith(OURS_PREFIX):
            includes.setdefault(f"workflows/{name.removeprefix(OURS_PREFIX)}/{name}.yaml", []).append(_scalar(_top(node, "id")))
    for rel in [LINE_YAML, *sorted(includes)]:
        for node, inside in line if rel == LINE_YAML else _graph(root, rel):
            ident = _scalar(_top(node, "id"))
            ids = [ident] if rel == LINE_YAML or inside else [f"{inc}__{ident}" for inc in includes[rel]]
            when = _scalar(_top(node, "when"))
            for atom in (a.strip() for part in when.split("||") for a in part.split("&&")):
                if DEPTH_WHEN.search(atom):
                    out.append(f"{rel}:{_line(node)}: ノード {', '.join(ids)} の when の句 `{atom}` が出力の深さの欄を読む"
                               "（深さで飛ばす道を作らない。深さの段は docs/design.md の表 1 か所）")
    listed = {tier: (omits, adds, n) for n, tier, omits, adds in rows}
    for tier, spec in depth.TIERS.items():
        want = (tuple(spec["omits"]), tuple(spec["adds"]))
        if tier not in listed:
            out.append(f"{DEPTH_TABLE}:1: 段の表に段 {tier} の行が無い")
        elif listed[tier][:2] != want:
            out.append(f"{DEPTH_TABLE}:{listed[tier][2]}: 段 {tier} の省く物・足す物が depth.TIERS と違う"
                       f"（表: {listed[tier][:2]}、depth.TIERS: {want}）")
    out += [f"{DEPTH_TABLE}:{n}: 表の段 {tier} が depth.TIERS に無い" for n, tier, _, _ in rows if tier not in depth.TIERS]
    return out


def _scalar(value) -> str:
    return value.value if isinstance(value, yaml.ScalarNode) else ""


RULES = {
    "E2": _polyfills_listed,
    "E3": _lib_blind,
    "E4": _block_paths,
    "E5": _block_returns,
    "E6": _outward_write,
    "E7": _readonly_nodes,
    "E8": _no_asf,
    "E9": _names,
    "E12": _no_timeouts,
    "E13": _lang_neutral,
    "E14": _no_owner_env,
    "E16": _gates,
    "E18": _origin_names,
    "E19": _role_retry,
    "E20": _depth_when,
}
