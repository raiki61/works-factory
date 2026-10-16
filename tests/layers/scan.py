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
    """pattern（正規表現の断片）を語として当てる式。前後が `[\\w\\-/.]` の時は語の一部（plan-fields.json・fix_plan・plan/r1）で数えない。
    `\\w` は ASCII だけ（日本語の字に続く名 `eyesの` も語として当てる）"""
    return re.compile(rf"(?<!(?a:[\w\-/.]))(?:{pattern})(?!(?a:[\w\-/.]))")


BOUNDARY = "boundary.py"
# 「（予定）」は語の境の外に置く。後ろに字が続いても（予定）を落とさない
POLYFILL_ROW = re.compile(word(r"((?:workflows|bin|lib|tests)/[^\s`（）()、・。]+)").pattern + r"(`?（予定）)?")
# 名簿の `- 埋め:` の行の頭の欄（group 1）。`- 埋め:` の直後から続くパスの並びで、backtick で囲んでも素でもよい。欄を続けるのはパスの直後の「（予定）」と区切りの `、` だけ。それ以外の最初の字で欄が終わる（頭が文で始まる行は空）
_POLYFILL_HEAD_PATH = "`?(?:" + POLYFILL_ROW.pattern + ")`?"
POLYFILL_HEAD = re.compile(rf"\s*- 埋め:\s*((?:{_POLYFILL_HEAD_PATH}(?:、{_POLYFILL_HEAD_PATH})*)?)")
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
    "E21": (
        # 試験の子の環境の唯一の作り手
        "tests/bin/hermetic.py",
        # 本物の run・較正の命令の道具。利用者の環境（認証・PATH）を継ぐのが用途
        "tests/calibration/run.py",
        "tests/calibration/reviewbench.py",
        "tests/calibration/swepro.py",
        "tests/e2e/evidence.py",
        "tests/e2e/make_target.py",
        # 試験を回す口。子の tests.shard は自分の過程の環境を hermetic.scrub で外し、Archon の源の置き場の名を継ぐのが要る
        "tests/changed.py",
        # 受けた環境を控えるだけの偽の起動
        "tests/bin/fakelaunch.py",
        # 偽の script の字の中の os.environ で、子の環境を組む口ではない
        "tests/shared/test_fence.py#os.environ.items()",
        # この表の上の行の字そのもの（許しの行が名指す字は、走査器自身の字として当たる）
        "tests/layers/scan.py#os.environ.items()",
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
    listed = {}  # 行の全部のパス。木に在るかを照らす
    covered = set()  # 頭の欄のパスだけ。説明の文にだけ出る名は覆いに数えない
    rows, out = _lines(root, registry) if registry.is_file() else ([], [])
    for number, line in enumerate(rows, 1):
        head = POLYFILL_HEAD.match(line)
        if head:
            covered.update(match[1] for match in POLYFILL_ROW.finditer(head[1]))
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
            if name != f"workflows/.shared/{BOUNDARY}" and name not in covered:
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


def _node_ids(document) -> set[str]:
    """グラフの YAML の節の id（字の物だけ）"""
    return {i.value for node in _nodes(document) if isinstance(i := _top(node, "id"), yaml.ScalarNode)}


def _top_hyphen_ids(root: Path) -> set[str]:
    """一番上のグラフ（line・chain）の節の id のうち `-` を含む物。`-` の無い id は普通の語と重なるので入れない"""
    ids = set()
    for name in TOP_FOLDERS:
        _, top = _workflow_doc(root / "workflows" / name)
        if top is not None:
            ids |= {i for i in _node_ids(top) if "-" in i}
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
        own_ids = _node_ids(document)
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


# 環境をその場で差し替える patch.dict は親の環境を写さない（dict( の前に . が付く形は当てない）。dict に足し書きを付けた形・辞書の
# 合併・env の引数へ丸ごと渡す形・名に env を含む関数（outside_env など）の位置引数へ渡す形も、親を丸ごと子へ渡す
COPIED_ENVIRON = re.compile(
    r"os\.environ\.items\(\)|\*\*os\.environ\b|(?<!\.)dict\(os\.environ\b|os\.environ\.copy\(\)|os\.environ\s*\||\benv\s*=\s*os\.environ\b"
    r"|\b\w*env\w*\(\s*os\.environ\s*[,)]"
)


# 子を起こす呼び出し（モジュールの名 → 関数の名）。env を渡さないと親の環境を丸ごと受け継ぐ。os.system・os.popen は env を受けない
SPAWNS = {
    "subprocess": frozenset({"run", "Popen", "call", "check_call", "check_output"}),
    "asyncio": frozenset({"create_subprocess_exec", "create_subprocess_shell"}),
    "os": frozenset({"system", "popen"}),
}


def _envless_spawns(root: Path, path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []   # 読めない字は _grep が UTF-8 の行で出す。構文の誤りは試験そのものが落ちる
    # 既定が None の引数を差し替えずに env へ渡す形も、呼び手が渡さなければ env の無い子になる
    unset = {id(call): _none_default_params(fn) for fn in ast.walk(tree)
             if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) for call in ast.walk(fn)}
    out = []
    for node in ast.walk(tree):
        func = getattr(node, "func", None)
        if not (isinstance(node, ast.Call) and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.attr in SPAWNS.get(func.value.id, ())):
            continue
        env = next((k.value for k in node.keywords if k.arg == "env"), None)
        if (env is None or (isinstance(env, ast.Constant) and env.value is None)
                or (isinstance(env, ast.Name) and env.id in unset.get(id(node), ()))):
            out.append(f"{_rel(root, path)}:{node.lineno}: 子の環境は hermetic.child_env で作る。env の無い子の起こし "
                       f"{func.value.id}.{func.attr}")
    return out


def _none_default_params(fn) -> frozenset:
    args = fn.args
    pairs = [*zip(reversed(args.posonlyargs + args.args), reversed(args.defaults)), *zip(args.kwonlyargs, args.kw_defaults)]
    rebound = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    return frozenset(a.arg for a, d in pairs if isinstance(d, ast.Constant) and d.value is None and a.arg not in rebound)


def _hermetic_env(root: Path) -> list[str]:
    """E21: tests/ と lib/tests/ の試験の子の環境は hermetic.child_env で作る。os.environ を写す形と、env を渡さない子の起こし
    （開発者のシェルや親の run が立てた名が子へ漏れて、同じ試験が場で違う結果を返す）を赤にする"""
    paths = [p for folder in (("tests",), ("lib", "tests")) for p in _files(root, *folder) if p.suffix == ".py"]
    copies = _grep(root, paths, (COPIED_ENVIRON, lambda m: f"子の環境は hermetic.child_env で作る。os.environ を写す {m[0]}"))
    return copies + [line for path in paths for line in _envless_spawns(root, path)]


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


# Archon の出力の参照（355f1867 の packages/workflows/src/output-ref.ts の CURRENT_OUTPUT_PATH_SOURCE と PRIOR_OUTPUT_PATH_SOURCE）と同じ形の 1 本。
# match[2] は任意の欄の道 `a.b`（入れ子も通る）で、頭の欄が返す節の欄。match[2] が None の一致がまるごとの参照。だから `.output-x`・`.outputs`・
# `.output.`・`.output.0` も欄の無い側（まるごと）に入り、欄つきとの間に隙間が開かない
OUTPUT_REF = re.compile(r"\$(?:LOOP_PREV\.)?([A-Za-z_][\w-]*)\.output(?:\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))?")
# 境の口（workflows/.shared/boundary.py）の呼びの名と、受け皿の素通しの宣言の名。scan.py が script について知るのはこれと環境の名の頭だけ
GATE_MODULE = "boundary"
GATE_PICKED = "picked"
GATE_PASSED = "passed"
INPUT_HEAD = "INPUTS_"


def _workflow_doc(folder: Path):
    """フォルダの工程 `works-factory-<フォルダの名>.yaml` の (パス, 頭の node)。無い・読めなければ (パス, None)"""
    path = folder / f"{OURS_PREFIX}{folder.name}.yaml"
    if not path.is_file():
        return path, None
    documents, broken = _documents(folder.parents[1], path)
    return path, (documents[0] if documents and not broken else None)


def _scalars(node, path=(), skip=frozenset()):
    """node の下の字の値を、merge key を _pairs で解いた鍵の道と字の組で全部（鍵は除く）。list の項は添字を道に足す。道が skip に在る物の下は回さない"""
    if path in skip:
        return
    if isinstance(node, yaml.ScalarNode):
        yield path, node.value
    elif isinstance(node, yaml.SequenceNode):
        for index, item in enumerate(node.value):
            yield from _scalars(item, (*path, index), skip)
    elif isinstance(node, yaml.MappingNode):
        for key, value in _pairs(node):
            yield from _scalars(value, (*path, key), skip)


def _line_reads(root: Path) -> tuple[dict, dict, list[str]]:
    """線のメイングラフの節ごとに、字を鍵の道つきで 1 回の走査で読む。返りは (reads, whole, 赤の行):
    reads は `$<include の id>.output.<欄>` で読む欄を、差し込んだ工程の名ごとに {名: {欄…}}。
    whole は、まるごとの参照 `$<include の id>.output` を受けてよい置き場（script の節の with:<鍵> の直の字か with:<鍵>.from の字が、
    参照そのもの）で受けた script の口の読みを、工程の名ごとに {名: [(script のパス, 行, 鍵, 口の名の並び（受け皿の素通しは None）, 節の id)…]}。
    受けてよい置き場の外のまるごとの参照と、口を引けない・読まない・迂回して読む受け手は、列挙せずに全部赤（既定の拒み）"""
    path = root / LINE_YAML
    documents, broken = _documents(root, path) if path.is_file() else ([], [])
    if broken or not documents:
        return {}, {}, []
    document = documents[0]
    target = {
        _top(node, "id").value: value.value
        for node in _nodes(document)
        if isinstance(value := _top(node, "include"), yaml.ScalarNode) and isinstance(_top(node, "id"), yaml.ScalarNode)
    }
    reads, whole, out = {}, {}, []
    for node in _nodes(document):
        ident = getattr(_top(node, "id"), "value", "?")
        received = {}   # 受けてよい置き場の鍵 → まるごとの参照が指す include の id
        for keys, text in _scalars(node, skip={("loop_group", "nodes")}):   # loop_group の中の節は別の節として回す
            refs = []
            for match in OUTPUT_REF.finditer(text):
                if match[1] not in target:
                    continue
                if match[2] is None:
                    refs.append(match)
                else:
                    reads.setdefault(target[match[1]], set()).add(match[2].partition(".")[0])
            if refs and _takes_whole(node, keys, text):
                received[keys[1]] = refs[0][1]
            elif refs:
                out.append(f"{_rel(root, path)}:{_line(node)}: 節 {ident} の {'.'.join(map(str, keys))} のまるごとの参照 {refs[0][0]} は受けられない"
                           "（受けてよいのは script の節の with:<鍵> の直の字と with:<鍵>.from の字だけ）")
        for key, include in received.items():
            entry, problems = _gated(root, path, node, ident, key)
            out += problems
            if entry is not None:
                whole.setdefault(target[include], []).append(entry)
    return reads, whole, out


def _takes_whole(node, keys: tuple, text: str) -> bool:
    """節 node の鍵の道 keys の字 text が、受けてよい置き場のまるごとの参照そのものか"""
    place = len(keys) in (2, 3) and keys[0] == "with" and isinstance(keys[1], str) and (len(keys) == 2 or keys[2] == "from")
    whole = OUTPUT_REF.fullmatch(text)
    return _top(node, "script") is not None and place and whole is not None and whole[2] is None


def _gated(root: Path, line_path: Path, node, ident: str, key: str):
    """まるごとの参照を with:<key> で受ける script の節 node の口の読み。(whole の組か None, 赤の行の並び)"""
    here = f"節 {ident} の with.{key}"
    scripts = [p for p in node_scripts(line_path.parent, node) if p.suffix == ".py"]
    if len(scripts) != 1:
        return None, [f"{_rel(root, line_path)}:{_line(node)}: {here} を受ける script のファイルを引けない（直に書いた script: | か名の取り違え）"]
    script = scripts[0]
    rel = _rel(root, script)
    if not script_reads(script.read_text(encoding="utf-8", errors="replace"), key, root / "lib"):
        return None, [f"{rel}:1: {here} を受ける script が {_input_env(key)} を読まない"]
    names, line, reasons = _gate_reads(script, key, root / "lib")
    if reasons:
        return None, [f"{rel}:{line}: {here} を受ける script が口を通らずに読む: " + "／".join(reasons)]
    return (rel, line, key, names, ident), []


def _block_returns(root: Path) -> list[str]:
    """返りの欄の読み手に加えて、ブロックの入力の読み手（K12）と、輪の中の役が自分の with: を結ばないこと（K5）も照らす。
    まるごとの参照を受ける script の口の名は、順方向（返す節の output_format に在る）と逆向き（読み手に数える）の両方で照らす"""
    reads, whole, problems = _line_reads(root)
    line_nodes = [n for d in _documents(root, root / LINE_YAML)[0] for n in _nodes(d)] if whole else []
    out = _inputs_read(root) + _loop_roles(root) + problems
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
        name = f"{OURS_PREFIX}{folder.name}"
        fields = list(_pairs(_top(schema, "properties")))
        known = {k for k, _ in fields}
        read = set(reads.get(name, ()))
        for script, line, key, names, receiver in whole.get(name, ()):
            read |= _relayed_reads(root, line_nodes, receiver) if names is None else set(names)
            out += [f"{script}:{line}: script {script} が {key} で読む欄 {n} が {name} の返りに無い" for n in names or () if n not in known]
        for key, value in fields:
            if key not in read:
                out.append(f"{rel}:{_line(value)}: 返りの欄 {key} に読み手が無い"
                           "（線の with:・when:・返しの節の from の欄つきの参照も、まるごとの参照を受ける script の口の名も、受け皿の先の名指しも読まない）")
    return out


def _relayed_reads(root: Path, nodes: list, receiver: str) -> set[str]:
    """受け皿の節 receiver（欄を読まずに運ぶだけの中継）の先が名指しで読む名。先は、receiver の出力を参照する線の節と、その節の出力を
    参照する節と…の閉包（nodes は線の節の全部）。名は、先の節の字の参照の道 `.output.<a>.<b>` の名と、先の script（差し込んだ工程なら、その scripts/ の全部）と
    それらが import する lib の部品（入れ子も）の、読む位置の字の定数（_read_names）"""
    path = root / LINE_YAML
    reached, names, files = {receiver}, set(), set()
    grew = True
    while grew:
        grew = False
        for node in nodes:
            ident = getattr(_top(node, "id"), "value", None)
            refs = [m for _, text in _scalars(node, skip={("loop_group", "nodes")}) for m in OUTPUT_REF.finditer(text) if m[1] in reached]
            if not refs:
                continue
            names.update(part for m in refs if m[2] for part in m[2].split("."))
            if ident is not None and ident not in reached:
                reached.add(ident)
                grew = True
            files.update(p for p in node_scripts(path.parent, node) if p.suffix == ".py")
            include = _top(node, "include")
            if isinstance(include, yaml.ScalarNode) and include.value.startswith(OURS_PREFIX):
                files.update((root / "workflows" / include.value.removeprefix(OURS_PREFIX) / "scripts").glob("*.py"))
    for file in _imported(root / "lib", files):
        names |= _read_names(file)
    return names


def _imported(lib: Path, files: set) -> set[Path]:
    """files と、それらが import する lib の部品の閉包"""
    seen, todo = set(), list(files)
    while todo:
        file = todo.pop()
        if file not in seen:
            seen.add(file)
            todo += _lib_imports(lib, file)
    return seen


@functools.cache
def _lib_imports(lib: Path, file: Path) -> tuple:
    """file が import する lib の部品（`import <部品>`・`from <部品> import …`・`from lib import <部品>`）のパス"""
    source, parts = _source(file), []
    for node in ast.walk(source.tree) if source else ():
        if isinstance(node, ast.Import):
            parts += [a.name.partition(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts += [node.module.partition(".")[0]] + ([a.name for a in node.names] if node.module == "lib" else [])
    return tuple(lib / f"{part}.py" for part in dict.fromkeys(parts) if (lib / f"{part}.py").is_file())


@functools.cache
def _read_names(path: Path) -> frozenset:
    """script か lib の部品 path の、読む位置の字の定数。書く位置（dict の literal の鍵・代入と del の添字）と docstring と f 字の欄は数えない"""
    source = _source(path)
    if source is None:
        return frozenset()
    written = set()
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Dict):
            written.update(id(k) for k in node.keys if k is not None)
        elif isinstance(node, ast.Subscript) and not isinstance(node.ctx, ast.Load):
            written.add(id(node.slice))
        elif isinstance(node, ast.JoinedStr):
            written.update(id(v) for v in node.values)
        elif isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(node, clean=False) is not None:
            written.add(id(node.body[0].value))
    return frozenset(n.value for n in ast.walk(source.tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in written)


def script_reads(text: str, name: str, lib: Path = LIB) -> bool:
    """script の字が入力 name を読むか。Archon は名の - を _ にして大文字の INPUTS_<名> で渡す。`INPUTS_{…}` を組んで読む script は
    名の字を持つ物と、INPUTS_{…} を組む内包の for で名を持つ lib の部品の字の並びの定数（BUILT_FROM。部品は lib の下）を回す物を読み手に数える。
    定数の字の並びは名の組を解く唯一の所 _str_names で解く"""
    if re.search(rf"INPUTS_{re.escape(name.replace('-', '_').upper())}(?![A-Z0-9_])", text):
        return True
    if "INPUTS_{" not in text:
        return False
    if re.search(rf"[\"']{re.escape(name)}[\"']", text):
        return True
    return any(name in _lib_names(lib / f"{module}.py", const, lib) for module, const in BUILT_FROM.findall(text))


@functools.cache
def _lib_names(path: Path, const: str, lib: Path) -> tuple:
    """lib の部品か script の頭の定数 const（path の module の頭の代入）を _str_names で解いた字の並び（解けなければ空）"""
    source = _source(path)
    value = _top_value(source, const) if source else None
    return (_str_names(value, path, lib, sequence=True) or ()) if value is not None else ()


def _input_env(name: str) -> str:
    """入力 name を Archon が script に渡す環境の名（- は _ にして大文字）"""
    return INPUT_HEAD + name.replace("-", "_").upper()


class _Source:
    """名の組みを解く相手の module の木と、親の結びと、頭の代入（名 → 値の並び。1 つに定まらない束縛は None を足す）"""

    def __init__(self, tree: ast.Module):
        self.tree = tree
        self.parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        self.top: dict = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    plain = isinstance(target, ast.Name)
                    for name in ([target] if plain else [n for n in ast.walk(target) if isinstance(n, ast.Name)]):
                        self.top.setdefault(name.id, []).append(stmt.value if plain else None)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                self.top.setdefault(stmt.target.id, []).append(stmt.value)
            else:
                bound = [stmt.target.id] if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name) else []
                bound += [a.asname or a.name.partition(".")[0] for a in getattr(stmt, "names", []) if isinstance(stmt, (ast.Import, ast.ImportFrom))]
                bound += [stmt.name] if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else []
                for name in bound:
                    self.top.setdefault(name, []).append(None)


@functools.cache
def _source(path: Path):
    """script か lib の部品 path の module の _Source（無い・読めない・構文の誤りは None）"""
    try:
        return _Source(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return None


def _top_value(source, name: str):
    """module の頭で name に 1 度だけ置いた式（無い・何度も束縛される物は None）"""
    values = source.top.get(name, [])
    return values[0] if len(values) == 1 else None


STR, SEQ = "str", "seq"   # 解いた物の種類: 取りうる字（f 字・連結・名）か、字の並び（tuple・list・set）
MAX_NAMES = 4096
LIB_PART = re.compile(r"[a-z_][a-z0-9_]*")
LIB_CONST = re.compile(r"[A-Z][A-Z0-9_]*")


def _str_names(node, path: Path, lib: Path, sequence: bool = False):
    """式 node（path の module の木の中の node）が取りうる名の集まり（字の並びの tuple）を解く唯一の所。解けなければ None。
    sequence なら字の並び（tuple・list・set）の式だけを解く。解くのは次の形:
    字の定数・字の tuple・list・set の literal・`*` 展開・`+` の連結・同じ module の頭の定数の名（再帰で）・lib の部品の定数 `<module>.<CONST>`・
    `.upper()` と `.lower()` の呼び・内包の生成の変数（回す並びを解く）・関数の引数の名（同じ module のその関数の全部の呼びの引数を解き、
    関数が呼び以外で使われる時と引数が解けない時は解けない）。f 字は字の欄と解いた欄の積で名を組む。
    関数の返り・添字・属性の連なり・`%` と `.format` で組む形は解けない。どの字の定数にも INPUTS_ の字を持たない組み方（字を割る形）は数えない"""
    source = _source(path)
    got = _solve(node, source, lib) if source else None
    return got[1] if got is not None and (got[0] == SEQ or not sequence) else None


def _solve(node, source, lib: Path, seen=frozenset()):
    """(STR か SEQ, 字の tuple) か、解けなければ None。seen は解いている途中の式（回る定義を解けない側に倒す）"""
    if id(node) in seen:
        return None
    seen = seen | {id(node)}
    if isinstance(node, ast.Constant):
        return (STR, (node.value,)) if isinstance(node.value, str) else None
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        names = []
        for item in node.elts:
            spread = isinstance(item, ast.Starred)
            got = _solve(item.value if spread else item, source, lib, seen)
            if got is None or got[0] != (SEQ if spread else STR):
                return None
            names += got[1]
        return SEQ, tuple(dict.fromkeys(names))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _solve(node.left, source, lib, seen), _solve(node.right, source, lib, seen)
        if left is None or right is None or left[0] != right[0]:
            return None
        return (SEQ, tuple(dict.fromkeys(left[1] + right[1]))) if left[0] == SEQ else _product([left[1], right[1]])
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append((value.value,))
            elif isinstance(value, ast.FormattedValue) and value.conversion == -1 and value.format_spec is None:
                got = _solve(value.value, source, lib, seen)
                if got is None or got[0] != STR:
                    return None
                parts.append(got[1])
            else:
                return None
        return _product(parts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("upper", "lower") \
            and not node.args and not node.keywords:
        got = _solve(node.func.value, source, lib, seen)
        return (STR, tuple(dict.fromkeys(getattr(v, node.func.attr)() for v in got[1]))) if got is not None and got[0] == STR else None
    if isinstance(node, ast.Name):
        return _solve_name(node, source, lib, seen)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and LIB_PART.fullmatch(node.value.id) and LIB_CONST.fullmatch(node.attr):
        part = _source(lib / f"{node.value.id}.py")
        value = _top_value(part, node.attr) if part else None
        return _solve(value, part, lib, seen) if value is not None else None
    return None


def _product(parts):
    """字の欄の並び parts（それぞれ取りうる字の tuple）の積の (STR, 字の tuple)。大きすぎる積は解けない側に倒す"""
    names = ("",)
    for options in parts:
        names = tuple(dict.fromkeys(a + b for a in names for b in options))
        if len(names) > MAX_NAMES:
            return None
    return STR, names


def _solve_name(node, source, lib: Path, seen):
    """名 node を、内包の生成の変数・関数の引数・module の頭の定数の順に内側から解く"""
    name, child, parent, in_iter = node.id, node, source.parents.get(node), False
    while parent is not None:
        if isinstance(parent, ast.comprehension):
            in_iter = child is parent.iter
        elif isinstance(parent, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            generators = parent.generators
            if child in generators:   # 回す並び（先頭の生成の iter は内包の外で、後の生成の iter は前の変数が見える）
                at = generators.index(child)
                generators = generators[:at] if in_iter else generators[:at + 1]
            for generator in reversed(generators):
                if any(n.id == name for n in ast.walk(generator.target) if isinstance(n, ast.Name)):
                    got = _solve(generator.iter, source, lib, seen) if isinstance(generator.target, ast.Name) else None
                    return (STR, got[1]) if got is not None and got[0] == SEQ else None
            in_iter = False
        elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            inside = child is parent.body if isinstance(parent, ast.Lambda) else any(child is stmt for stmt in parent.body)
            if inside and name in {a.arg for a in ast.walk(parent.args) if isinstance(a, ast.arg)}:
                return _solve_param(parent, name, source, lib, seen)
            if inside and _assigns(parent, name, source):
                return None
        child, parent = parent, source.parents.get(parent)
    value = _top_value(source, name)
    return _solve(value, source, lib, seen) if value is not None else None


def _assigns(function, name: str, source) -> bool:
    """関数の中で name を（内包の生成の変数以外で）束縛するか。束縛するなら同じ名の頭の定数は見えない"""
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del)) and not _in_comprehension_target(node, source):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not function and node.name == name:
            return True
    return False


def _in_comprehension_target(node, source) -> bool:
    while True:
        parent = source.parents.get(node)
        if parent is None or isinstance(parent, ast.stmt):
            return False
        if isinstance(parent, ast.comprehension):
            return parent.target is node
        node = parent


def _solve_param(function, name: str, source, lib: Path, seen):
    """関数 function の引数 name を、同じ module のその関数の全部の呼びの引数で解く。呼び以外で使われる・呼びが無い・引数が解けなければ None"""
    scope = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)   # module の頭か、関数の中に入れ子にした関数（メソッドは属性の呼びで追えない）
    if not isinstance(function, scope[1:]) or not isinstance(source.parents.get(function), scope):
        return None
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    where = [a.arg for a in positional].index(name) if name in [a.arg for a in positional] else None
    keyword_only = [a.arg for a in args.kwonlyargs]
    if where is None and name not in keyword_only:
        return None   # *args・**kwargs
    default = None
    if where is not None and where >= len(positional) - len(args.defaults):
        default = args.defaults[where - (len(positional) - len(args.defaults))]
    elif where is None:
        default = args.kw_defaults[keyword_only.index(name)]
    calls = []
    for use in ast.walk(source.tree):
        if isinstance(use, ast.Name) and use.id == function.name and isinstance(use.ctx, ast.Load):
            call = source.parents.get(use)
            if not (isinstance(call, ast.Call) and call.func is use):
                return None
            calls.append(call)
    if not calls:
        return None
    solved = []
    for call in calls:
        if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            return None
        given = call.args[where] if where is not None and where < len(call.args) else next((k.value for k in call.keywords if k.arg == name), default)
        got = _solve(given, source, lib, seen) if given is not None else None
        if got is None:
            return None
        solved.append(got)
    kinds = {kind for kind, _ in solved}
    if len(kinds) != 1:
        return None
    return kinds.pop(), tuple(dict.fromkeys(n for _, names in solved for n in names))


def _norm(name: str) -> str:
    return name.replace("-", "_").upper()


def _is_name_head(node) -> bool:
    """INPUTS_ で始まる字の定数か（大文字・小文字を問わない）"""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and _norm(node.value).startswith(INPUT_HEAD)


def _name_head(node):
    """INPUTS_ で始まる名を組む式 node の頭の字の定数（そうでなければ None）: 頭の字の欄が INPUTS_ で始まる f 字・頭の字が INPUTS_ で始まる
    `+` の連結・`%` と `.format` で組む形。名を組まない式（辞書の鍵・比べの字・ほかの引数）は数えない"""
    head = None
    if isinstance(node, ast.JoinedStr):
        head = node.values[0] if node.values else None
    elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        head = node.left
        while isinstance(head, ast.BinOp) and isinstance(head.op, ast.Add):
            head = head.left
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        head = node.func.value
    return head if _is_name_head(head) else None


def _holds(node, env: str) -> bool:
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and _norm(n.value) == env for n in ast.walk(node))


def _boundary_calls(source, attr: str) -> list:
    return [n for n in ast.walk(source.tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr
            and isinstance(n.func.value, ast.Name) and n.func.value.id == GATE_MODULE]


def _gate_calls(source, attr: str, env: str) -> list:
    """`boundary.<attr>(…)` の呼びのうち、どれかの引数が env の字を持つ物"""
    return [c for c in _boundary_calls(source, attr) if any(_holds(a, env) for a in (*c.args, *(k.value for k in c.keywords)))]


def _returned_as_is(node, parents: dict) -> bool:
    """式 node が return の dict・tuple の literal の値に直に置かれているか（欄を引かずに出力へ運ぶだけの形）"""
    literal = parents.get(node)
    if isinstance(literal, ast.Dict):
        placed = any(value is node for value in literal.values)
    else:
        placed = isinstance(literal, ast.Tuple) and any(item is node for item in literal.elts)
    return placed and isinstance(parents.get(literal), ast.Return)


def _passed_uses(source, call) -> list:
    """`boundary.passed` の呼び call の値の使い方の誤り (行, 訳) の並び。許す形は 2 つだけで、ほかは形を並べず既定の拒み:
    呼びそのものを return の literal に直に置く形と、呼びを 1 度だけ名に代入し、同じ有効範囲のその名の読みが全部、return の literal に
    直に置く形か `<名> is None`・`<名> is not None` の形。添字・.get・属性・関数への引数・別の名への代入は欄を読みうるので赤。
    その return を持つ関数の返りも、_returner_uses の形の外で使えない"""
    why = f"boundary.{GATE_PASSED} で受けた値を return の literal に直に置く外で使う（欄を引くなら boundary.{GATE_PICKED} で名指す）"
    parents = source.parents
    if _returned_as_is(call, parents):
        return _returner_uses(source, call)
    bound = parents.get(call)
    if not (isinstance(bound, ast.Assign) and bound.value is call and len(bound.targets) == 1 and isinstance(bound.targets[0], ast.Name)):
        return [(call.lineno, why)]
    name = bound.targets[0].id
    scope = parents.get(bound)
    while scope is not None and not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        scope = parents.get(scope)
    out = []
    for node in ast.walk(scope):
        if not (isinstance(node, ast.Name) and node.id == name) or node is bound.targets[0]:
            continue
        test = parents.get(node)
        checked = (isinstance(test, ast.Compare) and test.left is node and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Is, ast.IsNot))
                   and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None)
        if not (isinstance(node.ctx, ast.Load) and (checked or _returned_as_is(node, parents))):
            out.append((node.lineno, why))
        elif not checked:
            out += _returner_uses(source, node)
    return list(dict.fromkeys(out))


def _returner_uses(source, placed) -> list:
    """素通しの値 placed を置いた return の関数の返りの使い方の誤り (行, 訳) の並び。関数は module の頭の飾りの無い def で、その名を読んでよいのは
    `boundary.run(…)` の第 1 引数の中（関数の名そのものか、それを呼ぶだけの lambda の呼びの頭）だけ。ほかの読み（返りの添字・.get・展開・
    lib への引数・別の名への代入）は返りの欄を読みうるので、形を並べず既定の拒み"""
    parents = source.parents
    function = parents.get(placed)
    while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)):
        function = parents.get(function)
    why = (f"boundary.{GATE_PASSED} の値を返す関数の返りを boundary.run の第 1 引数の外で使う"
           "（その関数か、それを呼ぶだけの lambda を boundary.run に渡すだけにする）")
    if not (isinstance(function, ast.FunctionDef) and isinstance(parents.get(function), ast.Module) and not function.decorator_list
            and len(source.top.get(function.name, [])) == 1):
        return [(placed.lineno, why)]
    handed = set()
    for run in _boundary_calls(source, "run"):
        compute = run.args[0] if run.args else None
        if isinstance(compute, ast.Lambda) and isinstance(compute.body, ast.Call):
            compute = compute.body.func
        if isinstance(compute, ast.Name):
            handed.add(id(compute))
    uses = [n for n in ast.walk(source.tree) if isinstance(n, ast.Name) and n.id == function.name]
    stray = [n.lineno for n in uses if id(n) not in handed]
    if stray or not uses:
        return [(min(stray, default=function.lineno), why)]
    return []


def _gate_reads(path: Path, key: str, lib: Path) -> tuple:
    """まるごとの参照を with:<key> で受ける script path が入力 key を読む口を AST で読む。返りは (口の名の並び, 行, 赤の訳の並び)。
    口は `boundary.picked(<字の定数 "INPUTS_<key>" を持つ式>, <名の並び>)` か `boundary.passed(<同じ式>)` の呼び 1 つだけ。
    欄を読む口は picked だけで、名の並びは _str_names で解く。passed は受け皿の素通しで欄を読まず、名の並びは None（全部の欄を運ぶ）。
    素通しの値は _passed_uses の形の外で使えない（欄を引く・lib に渡すと赤）。
    迂回の判じは形を並べず既定の拒み: (i) 値がちょうど INPUTS_<key> の字の定数が口の呼びの外に在る、(ii) INPUTS_ で始まる名を組む式
    （_str_names で組みうる名を全部解き、INPUTS_<key> が在るか解けなければ赤）、(iii) INPUTS_ で始まるが名の全部でも組む式の頭でもない
    字の定数で INPUTS_<key> がその字で始まる（前置きで環境を舐める形）"""
    source = _source(path)
    if source is None:
        return (), 1, ["script を UTF-8 の構文として読めない"]
    env = _input_env(key)
    reasons = []   # (行, 訳)
    picks, passes = _gate_calls(source, GATE_PICKED, env), _gate_calls(source, GATE_PASSED, env)
    gates = sorted(picks + passes, key=lambda c: (c.lineno, c.col_offset))
    allowed = {id(n) for c in gates for a in (*c.args, *(k.value for k in c.keywords)) for n in ast.walk(a)}
    names = ()
    if not gates:
        reasons.append((1, f"boundary.{GATE_PICKED} の呼びが無い（{env} は boundary.{GATE_PICKED}(<{env} の字を持つ式>, <名の並び>) で読み、"
                           f"受け皿の素通しは boundary.{GATE_PASSED}(<{env} の字を持つ式>) で運ぶ）"))
    elif len(gates) > 1:
        reasons.append((gates[1].lineno, f"boundary.{GATE_PICKED}・boundary.{GATE_PASSED} の呼びが 2 つ以上ある（{env} の口は 1 つだけ）"))
    elif passes:
        names = None
        if len(passes[0].args) != 1 or passes[0].keywords:
            reasons.append((passes[0].lineno, f"boundary.{GATE_PASSED} の引数は {env} の字を持つ式の 1 つだけ"))
        reasons += _passed_uses(source, passes[0])
    else:
        gate = picks[0]
        solved = _str_names(gate.args[1], path, lib) if len(gate.args) == 2 and not gate.keywords and _holds(gate.args[0], env) else None
        if solved is None:
            reasons.append((gate.lineno, f"口の名の並びを解けない（boundary.{GATE_PICKED} は {env} の字を持つ式と名の並びの 2 つの引数で、"
                                         "名の並びは定数に解ける形）"))
        else:
            names = solved
    heads, inner = set(), set()
    for node in ast.walk(source.tree):
        if id(node) in inner or (head := _name_head(node)) is None:
            continue
        heads.add(id(head))
        spine = node.left if isinstance(node, ast.BinOp) else None
        while isinstance(spine, ast.BinOp) and isinstance(spine.op, ast.Add):
            inner.add(id(spine))
            spine = spine.left
        built = _str_names(node, path, lib)
        if built is None:
            reasons.append((node.lineno, f"{INPUT_HEAD} で始まる名を組む式 {ast.unparse(node)} を解けない"))
        elif any(_norm(name) == env for name in built):
            reasons.append((node.lineno, f"{INPUT_HEAD} で始まる名を組む式 {ast.unparse(node)} が {env} を組みうる"))
    for node in ast.walk(source.tree):
        if not _is_name_head(node) or id(node) in heads:
            continue
        spelled = _norm(node.value)
        if spelled == env and id(node) not in allowed:
            reasons.append((node.lineno, f"{env} の字が口の呼びの外にある"))
        elif spelled != env and env.startswith(spelled):
            reasons.append((node.lineno, f"字 {node.value!r} が {env} の前置きにあたり、環境を舐めうる"))
    line = min((n for n, _ in reasons), default=gates[0].lineno if gates else 1)
    return names, line, list(dict.fromkeys(why for _, why in reasons))


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
                for name in _lib_names(root / "lib" / f"{module}.py", const, root / "lib"):
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
    ("plan-review", "plan-review-fix"): "plan-review の会話の続きの出し直しの役。項目ごとの下請けが答えのファイルを run の置き場に Write で"
                                        "書く。作業ツリーは書かない（元の keep_checkout）",
    ("test-gate", "ci"): "Bash でテストを走らせるが作業ツリーは書かない。sandbox の denyWrite が書き込みを止め、false と ci-accept の"
                         "作業ツリーの比べが重ねて守る（#69・#293）",
    ("test-gate", "ci-fix"): "ci の会話の続きの出し直しの役。Bash でテストを走らせるが作業ツリーは書かない（ci と同じ起こし方・同じ守り）",
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


# 差し込まれるブロックが工程の頭に書かない鍵（E16）。run の形は差し込む一番上の工程が決める
BLOCK_HEAD_KEYS = ("worktree", "container", "evidence_policy", "mutates_checkout")
# 止めた Archon が非推奨にし、効かない工程の頭の鍵（読み込みの警告。packages/workflows/src/loader.ts の「workflow-level 'interactive:'
# is deprecated and has no effect」）。一番上の工程も書かない
DEAD_HEAD_KEYS = ("interactive",)


def _gates(root: Path) -> list[str]:
    out = []
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        rel = _rel(root, path)
        for key, value in _pairs(document):
            if key in DEAD_HEAD_KEYS:
                out.append(f"{rel}:{_line(value)}: 工程の頭に効かない {key} を書く")
            elif key in BLOCK_HEAD_KEYS and folder.name not in TOP_FOLDERS:
                out.append(f"{rel}:{_line(value)}: 差し込まれるブロックが工程の頭に {key} を書く")
    return out + _gate_words(root)


def _human_gate(node) -> bool:
    """人に答えを聞く節: wait: の attention か、非推奨の approval:"""
    return _top(_top(node, "wait"), "attention") is not None or _top(node, "approval") is not None


def _gate_words(root: Path) -> list[str]:
    """関所は wait: の attention を form: select で書き、options に答えの語（lib/answer.py の GO_WORDS・STOP_WORDS。STOP_WORDS は
    REJECT を含む）を全部持つ（K10。止めた Archon は options に無い答えを拒み、run は関所で止まったまま。実測 2026-10-16）。
    approval: は書かない（止めた Archon が非推奨にした。packages/workflows/src/loader.ts の LEGACY_PAUSE_REPLACEMENTS）。
    輪（loop_group）の本体に関所を置かない（K18。本体が関所で終わる輪の再開は会話を引き継がない。元 works/tests/test_yaml_rules.py 43-45 行）"""
    out = []
    for path in _workflow_yamls(root):
        rel = _rel(root, path)
        documents, broken = _documents(root, path)
        out += broken
        for document in documents:
            for node in _nodes(document):
                for inner in getattr(_top(_top(node, "loop_group"), "nodes"), "value", []):
                    if _human_gate(inner):
                        out.append(f"{rel}:{_line(inner)}: 輪の本体に関所 {getattr(_top(inner, 'id'), 'value', '?')} を置いた")
                ident = getattr(_top(node, "id"), "value", "?")
                if _top(node, "approval") is not None:
                    out.append(f"{rel}:{_line(node)}: 関所 {ident} を非推奨の approval: で書く（wait: の attention で書く）")
                    continue
                wait = _top(node, "wait")
                if _top(wait, "attention") is None:
                    continue
                if getattr(_top(wait, "form"), "value", None) != "select":
                    out.append(f"{rel}:{_line(node)}: 関所 {ident} の form が select でない")
                words = {getattr(_top(o, "id"), "value", None) for o in getattr(_top(wait, "options"), "value", [])}
                for word in answer.GO_WORDS + answer.STOP_WORDS:
                    if word not in words:
                        out.append(f"{rel}:{_line(node)}: 関所 {ident} の options に {word} が無い")
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
    "E21": _hermetic_env,
}
