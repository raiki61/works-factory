"""層の決まりの「機械」の行を照らす。`problems(rule, root)` は 1 行に 1 つ `<パス>:<行>: <何が>` を返す（無ければ空）。

字の形でしか見ないので、次は人が見る:
- E3: 節の id（字の形で見分けられない）
- E12: script の中で置く期限
E4（名の住処の柵 NAME_HOMES）と E22（層の地図の既知の漏れの表）の照らしは、組み込みで消えた古いサブグラフと名の住処の lib に
当てる物だったので外した（docs/design/README.md の 9.4・docs/design/integration.md の 4.5-9）。
"""
import ast
import collections
import dataclasses
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


# pack の口（workflows/AGENTS.md の E2）。2 つ以上の block が使う断片と形（prompts/・schemas/ の下の全部）と AGENTS.md も口の側に数える
PACK_PORTS = ("ports.py", "prompt.py", "requestrows.py", "AGENTS.md")
PACK_PORT_FOLDERS = ("prompts", "schemas")
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

REPO = Path(__file__).resolve().parents[2]
# 層の地図（根の AGENTS.md の E22）。試験の小さな木にも、このリポジトリの地図を当てる
LAYER_MAP_FILE = "docs/layers.json"
LAYER_MAP = json.loads((REPO / LAYER_MAP_FILE).read_text(encoding="utf-8"))
LAYERS = {layer["id"]: layer for layer in LAYER_MAP["layers"]}
TOP_FOLDERS = tuple(path.split("/")[1] for path in LAYERS["top"]["paths"])
# まだ木に無いブロックを指す字も捕まえるための名の表。木に在るブロックは木から読む。
BLOCKS = (*TOP_FOLDERS, *LAYERS["block"]["names"])
# lib/ が頼ってはならない層の頭のフォルダ（E3。地図の lib の may_use の外の層）
LAYER_IMPORT = re.compile(r"^\s*(from|import)\s+(" + "|".join(sorted(
    {path.split("/")[0] for layer in LAYERS.values() if layer["id"] not in ("lib", *LAYERS["lib"]["may_use"])
     for path in layer["paths"]})) + r")\b")

LIB = REPO / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import chain  # noqa: E402  （周の鎖の周の数の上限 MAX_ROUNDS）
import launchgroups  # noqa: E402  （AI ノードの群の表 GROUPS）
OURS = json.loads((REPO / "pack.json").read_text(encoding="utf-8"))["ours"]
OURS_PREFIX = OURS["name_prefix"]
LINE_FOLDER = OURS["line"].removeprefix(OURS_PREFIX)
LINE_YAML = f"workflows/{LINE_FOLDER}/{OURS['line']}.yaml"
CALL_KEYS = ("include", "workflow")

NO_DEADLINE = "1728000000"
# 止めた Archon（docs/design/archon.md の「語」）の節の種類の鍵の全部と、その種類の節に Archon が既定の期限を当てる鍵（workflows/AGENTS.md の E12）。
# ここに無い種類の節は赤にする。鍵は tests/shared/test_archon_contract.py が Archon の源に照らす（種類が足されたら赤になる）。
# 足す時は期限を持つかを確かめてから足す。
NODE_KINDS = {
    "script": (),
    "bash": (),
    "prompt": ("idle_timeout",),
    "command": ("idle_timeout",),
    "loop": ("idle_timeout",),
    "loop_group": (),
    "approval": ("idle_timeout",),
    "wait": (),
    "cancel": (),
    "include": (),
    "workflow": (),
}
DEADLINE_KEYS = frozenset(key for keys in NODE_KINDS.values() for key in keys)
# 書かなければ期限の無い鍵（script・bash の節と until_bash の確かめ）。書けば期限になる
UNSET_DEADLINE_KEY = "timeout"
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
# だけ。
ALLOWED = {
    "E2": (
        # bin/_lib/ の埋めでない物（起動の認証と隔離を今の works から持ってきた入口の部品。bin/AGENTS.md の E15）。埋めは名簿の行が持つ
        "bin/_lib/auth_launch.py",
        "bin/_lib/claude_auth.py",
        "bin/_lib/hostgh.py",
        "bin/_lib/isolate.py",
        "bin/_lib/pack.py",
        "bin/_lib/startpoint.py",
        "bin/_lib/no-post-bin/",
        # 仕様駆動の道の表を読み、会話で回した審査の記録を照らす入口の部品（docs/design/spec-driven.md の 2.6 の 2。bin/AGENTS.md の E15 の外し）
        "bin/_lib/spec-inputs.py",
        "bin/_lib/specreviews.py",
    ),
    "E3": (
        "lib/AGENTS.md",
        # 借りたスキルを無人の役で読む時の読み替え（役が読む文）。役の skills: の宣言と受け付けのループを、役に名指して説く
        "lib/borrow/unattended.md#Archon",
        # 消した文の原文の記録（台帳の ! 行の old）に残る字。記録は元の字のまま残す物
        "lib/borrow/COPIED_FROM#loop_group",
        # Archon の run の記録（$LOG_DIR/<WORKFLOW_ID>.jsonl）を読む口。report と chain の 2 つが使うので lib に上げた
        # （docs/design/integration.md の 4.5-2 の決め）
        "lib/runlog.py",
        "lib/tests/test_runlog.py",
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
        # 偽の script の字の中の os.environ。起動の殻が組んだ子の環境から、対象のコマンドの環境の作り手が組む物を確かめる
        "tests/bin/test_launcher.py#outside_env(os.environ)",
        # この表の上の行の字そのもの（許しの行が名指す字は、走査器自身の字として当たる）
        "tests/layers/scan.py#os.environ.items()",
        "tests/layers/scan.py#outside_env(os.environ)",
    ),
    "E13": (
        "lib/AGENTS.md",
        "lib/tests/",
        "lib/impact.py",
        "lib/changemap.py",
        "lib/libdocs.py",
        "lib/libdocs_local.py",
        "lib/borrow/superpowers/",
    ),
}


def problems(rule: str, root: Path) -> list[str]:
    try:
        check = RULES[rule]
    except KeyError:
        raise ValueError(f"知らない決まり: {rule}（{', '.join(RULES)} のどれか）") from None
    return [line for line in check(Path(root)) if not _allowed(rule, line)]


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
            if not _pack_port(name) and name not in covered:
                out.append(f"{name}:1: 名簿にも pack の口にも当たらない")
    return out


def _pack_port(name: str) -> bool:
    """name（根からの相対）が pack の口の側（`workflows/.shared/` の PACK_PORTS か PACK_PORT_FOLDERS の下）か"""
    head, _, rest = name.partition("workflows/.shared/")
    return not head and bool(rest) and (rest in PACK_PORTS or rest.split("/")[0] in PACK_PORT_FOLDERS and "/" in rest)


def _lib_blind(root: Path) -> list[str]:
    return _grep(
        root,
        _files(root, "lib"),
        (ARCHON_WORDS, lambda m: f"Archon の名 {m[0]}"),
        (LAYER_IMPORT, lambda m: f"{m[2]} の中の物を import する"),
    )


IMPORT_NAMES = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+(?:\s*,\s*[\w.]+)*))")


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


# E8 の外し: Archon 同梱のグラフを workflow: で呼んでよい節（サブグラフのフォルダ, 節の id）→ 呼ぶグラフの名（持ち主の決め deliver-via-archon-pr）
ARCHON_CALLS = {("merge", "pr-open"): "archon-pr"}


def _archon_call(path: Path, node, key: str, value: str) -> bool:
    """節 node の workflow: の値 value が、E8 の外しの表 ARCHON_CALLS の節（YAML の置き場のフォルダと節の id）に当たるか"""
    ident = dict(_pairs(node)).get("id")
    name = ident.value if isinstance(ident, yaml.ScalarNode) else None
    return key == "workflow" and ARCHON_CALLS.get((path.parent.name, name)) == value


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
                    elif not value.value.startswith(OURS_PREFIX) and not _archon_call(path, node, key, value.value):
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
                if UNSET_DEADLINE_KEY in keys:
                    out.append(f"{rel}:{_line(keys[UNSET_DEADLINE_KEY])}: {UNSET_DEADLINE_KEY} を書かない（書かなければ期限が無い）")
                for key, value in set_deadlines:
                    if not (isinstance(value, yaml.ScalarNode) and value.tag == YAML_INT and value.value == NO_DEADLINE):
                        out.append(f"{rel}:{_line(value)}: {key} が {NO_DEADLINE} でない")
                needed = {key for kind in kinds for key in NODE_KINDS[kind]}
                for key in sorted(needed - keys.keys()):
                    out.append(f"{rel}:{_line(node)}: 節に {key} が無い（Archon の既定の期限が当たる）")
    return out


def _lang_neutral(root: Path) -> list[str]:
    """AI のノードへの指示の md（各 block の prompts/ と .shared/prompts/ の下の全部）と lib/"""
    prompts = [p for folder in _blocks(root) for p in _files(folder, "prompts")]
    prompts += list(_files(root, "workflows", ".shared", "prompts"))
    return _grep(root, prompts + list(_files(root, "lib")), (LANG_WORD, lambda m: f"言語か実行器の名 {m[0]}"))


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
    # 入れ子の関数の中の呼び出しは、いちばん内の関数の引数で見る（ast.walk は外の関数を先に訪ねるので、内の関数が上書きする）
    unset = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            unset.update(dict.fromkeys(map(id, ast.walk(fn)), _none_default_params(fn)))
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
# match[2] は任意の欄の道 `a.b`（入れ子も通る）。match[2] が None の一致がまるごとの参照。だから `.output-x`・`.outputs`・`.output.`・
# `.output.0` も欄の無い側（まるごと）に入り、欄つきとの間に隙間が開かない
OUTPUT_REF = re.compile(r"\$(?:LOOP_PREV\.)?([A-Za-z_][\w-]*)\.output(?:\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))?")
# 返りまるごとを読む唯一の口 ports.picked（workflows/.shared/ports.py）。名の並びを YAML の with: の字で渡す時は ports.text(...).split() で読む
GATE_MODULE = "ports"
GATE_PICKED = "picked"
GATE_TEXT = "text"
GATE_OPTIONAL = "optional"
INPUT_HEAD = "INPUTS_"
# 口を通らないまるごとの読み（赤は 1 つ出す）。どの欄を読むか分からないので、読み手の照らしでは全部の欄を読むと数え、赤を重ねない
UNGATED = (None, None, ())
# 環境変数を読む os の名（まるごとの参照を受ける script では、鍵が字のままの読みだけを許す）
ENV_NAMES = ("environ", "environb", "getenv", "getenvb")


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


def _whole_refs(root: Path, path: Path, document) -> tuple[dict, dict, list[str]]:
    """graph の YAML（path）の節の字のうち、まるごとの参照 `$<include の id>.output` を照らす。返りは (named, reads, 赤の行):
    named は、まるごとの参照を受けた script の口が宣言した名を、差し込んだ工程の名ごとに {名: [(宣言の場所, 名の並び, optional の名)…]}。
    reads は、欄つきの参照 `$<include か workflow の id>.output.<欄>` で読む欄の頭を、呼んだ工程の名ごとに {名: {欄…}}（読み手の照らし）。
    まるごとの参照を受けてよいのは script の節の with:<鍵> の直の字か with:<鍵>.from の字が参照そのものの時だけで、ほかは赤。
    欄つきの参照の欄が返りに在るかは Archon の validate が照らすので見ない"""
    called = {
        _top(node, "id").value: (key, value.value)
        for node in _nodes(document) for key in CALL_KEYS
        if isinstance(value := _top(node, key), yaml.ScalarNode) and isinstance(_top(node, "id"), yaml.ScalarNode)
    }
    target = {ident: name for ident, (key, name) in called.items() if key == "include"}
    named, reads, out = {}, {}, []
    if not called:
        return named, reads, out
    for node in _nodes(document):
        ident = getattr(_top(node, "id"), "value", "?")
        for keys, text in _scalars(node, skip={("loop_group", "nodes")}):   # loop_group の中の節は別の節として回す
            for match in OUTPUT_REF.finditer(text):
                if match[1] in called and match[2] is not None:
                    reads.setdefault(called[match[1]][1], set()).add(match[2].partition(".")[0])
            whole = next((m for m in OUTPUT_REF.finditer(text) if m[1] in target and m[2] is None), None)
            if whole is None:
                continue
            if not _takes_whole(node, keys, text):
                out.append(f"{_rel(root, path)}:{_line(node)}: 節 {ident} の {'.'.join(map(str, keys))} のまるごとの参照 {whole[0]} は受けられない"
                           "（受けてよいのは script の節の with:<鍵> の直の字と with:<鍵>.from の字だけ）")
                entry, problem = UNGATED, ""
            else:
                entry, problem = _gated(root, path, node, f"節 {ident} の with.{keys[1]}", keys[1])
            if problem:
                out.append(problem)
                entry = UNGATED
            named.setdefault(target[whole[1]], []).append(entry)
    return named, reads, out


def _takes_whole(node, keys: tuple, text: str) -> bool:
    """節 node の鍵の道 keys の字 text が、受けてよい置き場のまるごとの参照そのものか"""
    place = len(keys) in (2, 3) and keys[0] == "with" and isinstance(keys[1], str) and (len(keys) == 2 or keys[2] == "from")
    whole = OUTPUT_REF.fullmatch(text)
    return _top(node, "script") is not None and place and whole is not None and whole[2] is None


def _gated(root: Path, yaml_path: Path, node, here: str, key: str):
    """まるごとの参照を with:<key> で受ける script の節 node の口。返りは ((宣言の場所, 名の並び, optional の名), "") か (None, 赤の行)。
    口は `ports.picked(<"INPUTS_<KEY>" の読み>, <名の並び>[, optional=<字の tuple>])` の呼び 1 つ。<読み> は
    `os.environ.get("INPUTS_<KEY>")`・`os.environ["INPUTS_<KEY>"]` そのものか、それを 1 度だけ束ねて口でだけ 1 度読む名
    （`raw = os.environ.get(...)`・`a, raw = os.environ.get(...), os.environ.get(...)`）。"INPUTS_<KEY>" の字はその読みの外に無い
    （まるごとの値を口の外で読めない）。名の並びは _declared が読む形だけで、ほかの形は解かずに赤"""
    scripts = [p for p in node_scripts(yaml_path.parent, node) if p.suffix == ".py"]
    if len(scripts) != 1:
        return None, f"{_rel(root, yaml_path)}:{_line(node)}: {here} を受ける script のファイルを引けない（直に書いた script: | か名の取り違え）"
    rel = _rel(root, scripts[0])
    try:
        tree = ast.parse(scripts[0].read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None, f"{rel}:1: {here} を受ける script を UTF-8 の構文として読めない"
    raw = _raw_env_reads(tree)
    if raw:
        return None, (f"{rel}:{raw[0]}: {here} を受ける script が環境変数を字のままでない鍵で読むか、回す・写す・渡す（許すのは "
                      'os.environ.get("<字>")・os.environ["<字>"]・os.getenv("<字>") だけ）')
    env = _input_env(key)
    gates = [n for n in ast.walk(tree) if _port_call(n, GATE_PICKED) and n.args and _feeds(tree, n.args[0], env)]
    if len(gates) != 1:
        return None, (f"{rel}:{gates[1].lineno if gates else 1}: {here} を受ける script が {env} を ports.{GATE_PICKED}"
                      f'(<os.environ.get("{env}") の読み>, <名の並び>) の 1 つの呼びで読まない（呼びが {len(gates)} 個）')
    gate = gates[0]
    read = _env_read_of(tree, gate.args[0], env)
    if read is None:
        return None, (f"{rel}:{gate.lineno}: {here} を受ける script の ports.{GATE_PICKED} の 1 つ目の引数が、"
                      f'os.environ.get("{env}") か os.environ["{env}"] そのものか、それを 1 度だけ束ねて口でだけ読む名でない')
    inside = {id(n) for n in ast.walk(read)}
    stray = [n.lineno for n in ast.walk(tree) if _spells(n, env) and id(n) not in inside]
    if stray:
        return None, f"{rel}:{stray[0]}: {here} を受ける script の {env} の字が ports.{GATE_PICKED} に渡す読みの外にある"
    where, names = _declared(root, yaml_path, node, rel, tree, gate)
    if names is None:
        return None, (f"{rel}:{gate.lineno}: {here} を受ける script の ports.{GATE_PICKED} の名の並びを解けない（許すのは module の頭の"
                      "字の tuple の名・lib の部品の字の tuple の定数 <部品>.<定数>・with: の字の値を読む "
                      f"ports.{GATE_TEXT}(<INPUTS_<鍵> の読み>).split()（その式を 1 度だけ束ねた名も可）と、鍵 {GATE_OPTIONAL}= の字の tuple だけ）")
    optional = tuple(e.value for k in gate.keywords for e in k.value.elts)
    return (where, names, optional), ""


def _binds(tree, name: str) -> list:
    """name を束ねる所（代入の的・引数・import・def・class・walrus・for など。字の Load でない名の全部）"""
    out = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load)]
    out += [n for n in ast.walk(tree) if isinstance(n, ast.arg) and n.arg == name]
    out += [n for n in ast.walk(tree) if isinstance(n, ast.alias) and (n.asname or n.name) == name]
    out += [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == name]
    return out


def _bound_value(tree, name: str):
    """name を 1 度だけ代入で束ねた時の値の式（`a, b = x, y` の組の項も解く）。束ねが 1 つの代入でなければ None"""
    binds = _binds(tree, name)
    if len(binds) != 1:
        return None
    for stmt in ast.walk(tree):
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        target, value = stmt.targets[0], stmt.value
        if target is binds[0]:
            return value
        if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts) \
                and not any(isinstance(e, ast.Starred) for e in target.elts + value.elts):
            for part, item in zip(target.elts, value.elts):
                if part is binds[0]:
                    return item
    return None


def _loads(tree, name: str) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load))


def _env_read_of(tree, node, env: str):
    """node が env の読み（`os.environ.get("<env>")`・`os.environ["<env>"]`）そのものならその式、読みを 1 度だけ束ねて 1 度だけ読む
    名ならその束ねの値の式。どちらでもなければ None"""
    if _environ_read(node, env):
        return node
    if isinstance(node, ast.Name) and _loads(tree, node.id) == 1:
        value = _bound_value(tree, node.id)
        if value is not None and _environ_read(value, env):
            return value
    return None


def _feeds(tree, node, env: str) -> bool:
    """口の 1 つ目の引数 node が env の字を持つか（直にか、束ねた名の値に）"""
    if _holds(node, env):
        return True
    value = _bound_value(tree, node.id) if isinstance(node, ast.Name) else None
    return value is not None and _holds(value, env)


def _declared(root: Path, yaml_path: Path, node, rel: str, tree, gate) -> tuple:
    """口の呼び gate の名の並び。返りは (宣言の場所, 名の tuple)。解けなければ (None, None)。2 つ目の引数の読む形は 3 つだけ:
    module の頭の字の tuple の名（_top_names）・lib の部品の字の tuple の定数 `<部品>.<定数>`・節の with: の字の値を
    `ports.text(<"INPUTS_<鍵>" の読み>).split()` で読む形（受け皿。名は YAML の字で、`$` の参照を持たない。この式を 1 度だけ束ねた名も可）。
    鍵は `optional=` だけで、値は字の tuple（無くてよい欄。宣言の名には数えない）"""
    if len(gate.args) != 2 or any(k.arg != GATE_OPTIONAL for k in gate.keywords):
        return None, None
    for keyword in gate.keywords:
        if not (isinstance(keyword.value, ast.Tuple) and all(_is_text(e) for e in keyword.value.elts)):
            return None, None
    arg = gate.args[1]
    where = f"{rel}:{gate.lineno}"
    if isinstance(arg, ast.Name):
        names = _top_names(tree, arg.id)
        if names is not None:
            return where, names
        value = _bound_value(tree, arg.id)
        return _yaml_names(root, yaml_path, node, tree, value) if value is not None else (None, None)
    if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and (root / "lib" / f"{arg.value.id}.py").is_file():
        return where, _lib_names(root / "lib" / f"{arg.value.id}.py", arg.attr) or None
    return _yaml_names(root, yaml_path, node, tree, arg)


def _yaml_names(root: Path, yaml_path: Path, node, tree, expr) -> tuple:
    """expr が `ports.text(<"INPUTS_<鍵>" の読み>).split()` で、節の with:<鍵> が `$` の参照を持たない字なら (YAML の場所, 名の tuple)"""
    text = expr.func.value if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "split" \
        and not expr.args and not expr.keywords else None
    if not (_port_call(text, GATE_TEXT) and len(text.args) == 1 and not text.keywords):
        return None, None
    arg = text.args[0]
    if isinstance(arg, ast.Name) and _loads(tree, arg.id) == 1:
        arg = _bound_value(tree, arg.id)
    for key, value in _pairs(_top(node, "with")):
        if isinstance(key, str) and arg is not None and _environ_read(arg, _input_env(key)):
            if isinstance(value, yaml.ScalarNode) and "$" not in value.value:
                return f"{_rel(root, yaml_path)}:{_line(value)}", tuple(value.value.split())
    return None, None


def _top_names(tree, name: str) -> tuple | None:
    """module の頭で name に 1 度だけ置き、ほかで束ねない字の tuple（項は字か、同じ形の名の `*` 展開）。そうでなければ None"""
    binds = _binds(tree, name)
    top = next((s for s in tree.body if isinstance(s, ast.Assign) and len(s.targets) == 1 and s.targets[0] in binds), None)
    if top is None or len(binds) != 1 or not isinstance(top.value, ast.Tuple):
        return None
    names = []
    for item in top.value.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            names.append(item.value)
        elif isinstance(item, ast.Starred) and isinstance(item.value, ast.Name) and item.value.id != name \
                and (spread := _top_names(tree, item.value.id)) is not None:
            names += spread
        else:
            return None
    return tuple(names)


def _raw_env_reads(tree) -> list[int]:
    """環境変数の読みのうち、鍵が字のままの get・添字・getenv の外の物の行。名を組んで読む・回す・写す・ほかの名へ渡す読みは、値の
    流れを解かずに全部ここに入る（`environ`・`getenv` の名を from import する物と、名を字で引く物も）"""
    parent = {id(child): n for n in ast.walk(tree) for child in ast.iter_child_nodes(n)}
    out = []
    for n in ast.walk(tree):
        name = n.attr if isinstance(n, ast.Attribute) else n.id if isinstance(n, ast.Name) else None
        if isinstance(n, ast.ImportFrom) and any(alias.name in ENV_NAMES for alias in n.names) \
                or isinstance(n, ast.Constant) and n.value in ENV_NAMES \
                or name in ENV_NAMES and not _literal_env_read(n, name, parent):
            out.append(n.lineno)
    return sorted(out)


def _literal_env_read(node, name: str, parent: dict) -> bool:
    """環境変数の名 node が `os.getenv("<字>")`・`os.environ.get("<字>")`・`os.environ["<字>"]` の頭か"""
    up = parent.get(id(node))
    if name.startswith("getenv"):
        return isinstance(up, ast.Call) and up.func is node and _literal_key(up)
    if isinstance(up, ast.Subscript) and up.value is node:
        return _is_text(up.slice)
    call = parent.get(id(up))
    return isinstance(up, ast.Attribute) and up.attr == "get" and isinstance(call, ast.Call) and call.func is up and _literal_key(call)


def _literal_key(call) -> bool:
    return 1 <= len(call.args) <= 2 and not call.keywords and _is_text(call.args[0])


def _is_text(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _port_call(node, attr: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr \
        and isinstance(node.func.value, ast.Name) and node.func.value.id == GATE_MODULE


def _spells(node, env: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == env


def _holds(node, env: str) -> bool:
    return any(_spells(n, env) for n in ast.walk(node))


def _environ_read(node, env: str) -> bool:
    """node が `os.environ.get("<env>")` か `os.environ["<env>"]` か"""
    environ = node.func.value if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) else getattr(node, "value", None)
    return _reads_env(node, env) and isinstance(environ, ast.Attribute) and environ.attr == "environ" \
        and isinstance(environ.value, ast.Name) and environ.value.id == "os"


def _reads_env(node, env: str) -> bool:
    """node が `<式>.get("<env>")` か `<式>["<env>"]` か"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
        return len(node.args) == 1 and not node.keywords and _spells(node.args[0], env)
    return isinstance(node, ast.Subscript) and _spells(node.slice, env)


# INPUTS_{…} を組む内包の for が回す lib の部品の定数（`for name in fixboard.PREP_INPUTS`）。script_reads が読む
BUILT_FROM = re.compile(r"INPUTS_\{[^}\n]*\}[^\n]*\bfor\s+\w+\s+in\s+([a-z_][a-z0-9_]*)\.([A-Z][A-Z0-9_]*)\b")


def script_reads(text: str, name: str, lib: Path = LIB) -> bool:
    """script の字が入力 name を読むか（E5 の照らしは使わない。tests/workflows/test_unread_named.py が読む）。Archon は名の - を _ に
    して大文字の INPUTS_<名> で渡す。`INPUTS_{…}` を組んで読む script は、名の字を持つ物と、INPUTS_{…} を組む内包の for で名を持つ
    lib の部品の字の並びの定数（BUILT_FROM。部品は lib の下）を回す物を読み手に数える"""
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


def _input_env(name: str) -> str:
    """入力 name を Archon が script に渡す環境の名（- は _ にして大文字）"""
    return INPUT_HEAD + name.replace("-", "_").upper()


def _loop_roles(root: Path) -> list[str]:
    """輪（loop_group）の中の役の節は自分の with: を結ばない（落とし穴 K5）。前の周の値は輪の頭の script の節が $LOOP_PREV で結んで返し、
    役はその出力を読む（PR #100。Archon の include-expander.ts の applyInputsMacro: 役の with: は include の時に既定の字で固まる）"""
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


INPUT_REF = re.compile(r"\$INPUTS\.([A-Za-z_][\w-]*)")


def _block_returns(root: Path) -> list[str]:
    """どの workflow（block と graph）にも returns: と outcome_field: が在り、返す節が output_format を持ち、outcome_field の欄がその
    required に在る。graph のまるごとの参照を受けた script の口が宣言した名は、返す節の output_format の properties に在る。
    返りの欄は読み手を持つ（持ち主の決め declared-io の「読み手ゼロなら赤」）: どこかの graph が欄つきの参照で読むか、まるごとの参照の
    口が宣言した名（optional を含む）に在る。入口（一番上のグラフ line・chain と、どの graph も include:・workflow: で呼ばない workflow）の
    返りは人（workflow get）と起動の殻が読むので照らさない。block の入力の読み手（_inputs_read）と、輪の中の役が自分の with: を結ばない
    こと（K5）も照らす"""
    out, named, reads, called, schemas = _loop_roles(root) + _inputs_read(root), {}, {}, set(), {}
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        rel = _rel(root, path)
        found, read, problems = _whole_refs(root, path, document)
        out += problems
        for name, entries in found.items():
            named.setdefault(name, []).extend(entries)
        for name, fields in read.items():
            reads.setdefault(name, set()).update(fields)
        called |= {value.value for node in _nodes(document) for key in CALL_KEYS if isinstance(value := _top(node, key), yaml.ScalarNode)}
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
        schemas[f"{OURS_PREFIX}{folder.name}"] = (rel, list(_pairs(_top(schema, "properties"))), folder.name)
    for name, (rel, fields, folder) in schemas.items():
        known = {key for key, _ in fields}
        read = set(reads.get(name, ()))
        for where, names, optional in named.get(name, ()):
            if names is None:
                read |= known
                continue
            read |= {*names, *optional}
            out += [f"{where}: 宣言した欄 {n} が {name} の返りに無い" for n in names if n not in known]
        if folder in TOP_FOLDERS or name not in called:   # 入口の返りを読むのは人（workflow get）と起動の殻で、graph の読み手は無い
            continue
        out += [f"{rel}:{_line(value)}: 返りの欄 {key} に読み手が無い（どの graph の欄つきの参照 $<id>.output.{key} も、"
                f"まるごとの参照の口 ports.{GATE_PICKED} の宣言も読まない）" for key, value in fields if key not in read]
    return out


def _inputs_read(root: Path) -> list[str]:
    """block の inputs: の名は、その block の YAML の字が $INPUTS.<名> で読むか（with: で include・script・役へ渡す字を含む）、その block の
    scripts/ と src/ の Python が INPUTS_<名> で読む（script_reads）。宣言しただけで誰も読まない入力を残さない（declared-io）"""
    out = []
    for folder in _blocks(root):
        path, document = _workflow_doc(folder)
        if document is None:
            continue
        refs = {m[1] for node in _nodes(document) for _, text in _scalars(node, skip={("loop_group", "nodes")})
                for m in INPUT_REF.finditer(text)}
        codes = ["\n".join(_lines(root, p)[0]) for part in ("scripts", "src") for p in _files(folder, part) if p.suffix == ".py"]
        for key, value in _pairs(_top(document, "inputs")):
            if key not in refs and not any(script_reads(text, key, root / "lib") for text in codes):
                out.append(f"{_rel(root, path)}:{_line(value)}: 入力 {key} に読み手が無い（YAML の $INPUTS.{key} も、"
                           f"scripts/・src/ の {_input_env(key)} も無い）")
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
    ("verify", "judge-verify"): "単位ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない（元の keep_checkout。blocks/ の block の名での同じ行）",
    ("plan-review", "plan-review"): "束ね役と同じ起こし方の錨 review_launch から Write を持つが、作業ツリーも run の置き場も書かない（単独の審査）",
    ("plan-review", "plan-review-fix"): "plan-review の会話の続きの出し直しの役。束ね役と同じ起こし方の錨 review_launch から Write を持つが、"
                                        "作業ツリーも run の置き場も書かない（単独の審査）",
    ("plan-review", "plan-review-tree"): "項目ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない（元の keep_checkout）",
    ("plan-review", "plan-review-tree-fix"): "plan-review-tree の会話の続きの出し直しの役。項目ごとの下請けが答えのファイルを run の置き場に"
                                             " Write で書く。作業ツリーは書かない（元の keep_checkout）",
    # blocks/plan-review/（作り直しの block。役の id が違う）。workflows/plan-review/ の上の 4 つと、folder の名が同じなので両方を置き、
    # 在る方だけを照らす（ALTERNATE_ROLES）
    ("plan-review", "review"): "束ね役と同じ起こし方の錨から Write を持つが、作業ツリーも run の置き場も書かない（単独の審査）",
    ("plan-review", "review-fix"): "review の会話の続きの出し直しの役。review と同じ起こし方で、作業ツリーも run の置き場も書かない（単独の審査）",
    ("plan-review", "review-tree"): "項目ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない",
    ("plan-review", "review-tree-fix"): "review-tree の会話の続きの出し直しの役。項目ごとの下請けが答えのファイルを run の置き場に Write で書く。作業ツリーは書かない",
    ("test-gate", "suite-write"): "TDD の実行器の書き手。Bash を持つが、使い方の表示を読むだけで作業ツリーは書かない"
                                  "（sandbox の denyWrite と false が守る。#516）",
}
# 同じ folder の名で役の id が違う 2 組（今の工程と作り直しの block）。どちらかが全部在れば、もう一方の組が無くても欠けとしない
ALTERNATE_ROLES = {"plan-review": ({"plan-review", "plan-review-fix", "plan-review-tree", "plan-review-tree-fix"},
                                   {"review", "review-fix", "review-tree", "review-tree-fix"})}
CHANGE_CHECKOUT = {
    ("line", "start"): "始めの記録を run の置き場に書くだけだが、今の線は印を持たない。足すと Archon の照らしが増えて振る舞いが変わるので部分 0 では足さない",
    ("spec", "spec-freeze"): "人が通した受け入れ条件を作業ツリーで /bin/sh -c で走らせる（blocks/spec/src/freeze.py の run_command）",
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
    ("test-gate", "run"): "対象のテストを作業ツリーで走らせる（declared_checks.run_ci）",
    ("merge", "pr-commit"): "出口の語 pr の時に、照らした差分を run の枝へ修正案の項目ごとの commit で積む（index と HEAD を変える。runbranch.commit・commit_parts）",
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
# 工程の根に書くと effort の無いノードの全部へ写る鍵（止めた Archon の include-expander.ts と loader.ts）。写った effort は群の別名の effort より先に採られる
ROOT_EFFORT_KEYS = ("effort", "modelReasoningEffort")


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
        for key in ROOT_EFFORT_KEYS:
            if (value := _top(document, key)) is not None:
                out.append(f"{rel}:{_line(value)}: 工程の根に {key} が在る（工程の根の effort は effort の無いノードへ写り、群の別名の effort より先に採られる。"
                           "run ごとの付け替えが効かなくなるので、effort は群の既定に任せて書かない）")
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
            sets = ALTERNATE_ROLES.get(folder.name, ())
            absent_pair = any(ident in group and not group <= seen and any(other <= seen for other in sets if other is not group)
                              for group in sets)
            if block == folder.name and ident not in seen and not absent_pair:
                out.append(f"{rel}:1: 表 KEEP_CHECKOUT が名指した役 {ident} が工程に無い")
    return out


def _role_settings(at: str, ident: str, node, tools) -> list[str]:
    out = []
    model = getattr(_top(node, "model"), "value", None)
    if model not in launchgroups.GROUPS:
        out.append(f"{at}: 役 {ident} の model が表 launchgroups.GROUPS の群の名でない（字の模型は run ごとの付け替えの的にならない。'@wf-<群>' を書く）")
    if _top(node, "effort") is not None:
        out.append(f"{at}: 役 {ident} に effort が在る（ノードの effort は群の別名の effort より先に採られ、run ごとの付け替えが効かない。群の既定に任せる）")
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


DEPTH_TABLE = "docs/design/line.md"   # 16 章の「### 深さの段の表」（docs/design.md は組み込みで docs/design/ に置き換えた）
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


@functools.cache
def tiers() -> dict:
    """段 → 回す物の表（line の src/tiers.py の TIERS。docs/design/line.md の 1.5。今の lib/depth.py の TIERS の行き先）"""
    from tests import archon  # noqa: PLC0415  （tests.archon は bin と試験の助けを読むので、使う時だけ読む）
    return archon.src_module(LINE_FOLDER, "tiers").TIERS


def _depth_when(root: Path) -> list[str]:
    """E20: どのノードの when も、出力の深さの欄を読む句（DEPTH_WHEN）を持たない（深さで飛ばす道を作らない）。docs/design/line.md の
    深さの段の表の行（段・省く物・足す物）は line の段の表 TIERS（tiers()）と等しい"""
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
                               "（深さで飛ばす道を作らない。深さの段は docs/design/line.md の表 1 か所）")
    listed = {tier: (omits, adds, n) for n, tier, omits, adds in rows}
    for tier, spec in tiers().items():
        want = (tuple(spec["omits"]), tuple(spec["adds"]))
        if tier not in listed:
            out.append(f"{DEPTH_TABLE}:1: 段の表に段 {tier} の行が無い")
        elif listed[tier][:2] != want:
            out.append(f"{DEPTH_TABLE}:{listed[tier][2]}: 段 {tier} の省く物・足す物が line の TIERS と違う"
                       f"（表: {listed[tier][:2]}、line の TIERS: {want}）")
    out += [f"{DEPTH_TABLE}:{n}: 表の段 {tier} が line の TIERS に無い" for n, tier, _, _ in rows if tier not in tiers()]
    return out


def _scalar(value) -> str:
    return value.value if isinstance(value, yaml.ScalarNode) else ""


RULES = {
    "E2": _polyfills_listed,
    "E3": _lib_blind,
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
