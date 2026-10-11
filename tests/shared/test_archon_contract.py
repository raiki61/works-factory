"""Archon と ASF から手で写した約束（workflows/.shared/boundary.py・bin/_lib/place.py・bin/_lib/pack.py）を、写した元の字に照らす。

行ごとに「写しの値」と「元の中のその値の在り処（ファイルと正規表現）」を持ち、正規表現で引いた値と写しの値を比べる。
元に行の形が見つからない時も赤にする（元の形が変わった合図）。写しは直さず、ずれを赤にするだけ。

- ASF の消費者 factory/consumer.py は木に在るので常に照らす。
- 止めた Archon の源は、環境変数 WORKS_FACTORY_ARCHON_CACHE の置き場に <cache>/archon/<commit> が在る時だけ照らす。
  在れば place._verify を当て、壊れていれば赤にする。環境変数か置き場が無い時だけ見送る。試験の中では取りに行かない。
"""
import os
import pathlib
import json
import re
import tempfile
import unittest
from collections.abc import Callable
from typing import Any, NamedTuple
from unittest import mock

from bin._lib import pack, place
from tests.bin.gitkit import git
from tests.shared.test_boundary import boundary

ROOT = pathlib.Path(__file__).resolve().parents[2]
CACHE_ENV = "WORKS_FACTORY_ARCHON_CACHE"


class Row(NamedTuple):
    name: str
    copy: Callable[[], Any]
    file: str
    pattern: str
    value: Callable[[re.Match], Any] = lambda m: m[1]


def _rejects(rel: str) -> bool:
    """写しの resolve が、この run の指し札でパス rel を拒むか"""
    env = {"WORKFLOW_ID": "run-1", "ARTIFACTS_DIR": "/artifacts"}
    with mock.patch.dict(os.environ, env, clear=True):
        try:
            boundary.resolve({"type": boundary.POINTER_TYPE, "run_id": "run-1", "path": rel})
        except ValueError:
            return True
    return False


def _env_read_by(call: Callable[[], Any], env: dict) -> str:
    """env だけの環境で call を走らせ、写しが読もうとして無かった環境変数の名を返す"""
    with mock.patch.dict(os.environ, env, clear=True):
        try:
            call()
        except KeyError as missing:
            return missing.args[0]
    raise AssertionError(f"{call} が env {sorted(env)} の外の環境変数を読まなかった")


def _pointer_fields() -> list[str]:
    with mock.patch.dict(os.environ, {"WORKFLOW_ID": "run-1"}, clear=True):
        return sorted(boundary.pointer("p"))


def _same_run_fields() -> list[str]:
    """札のどの欄を別の値に変えると、ほかの run の札として拒まれるか"""
    env = {"WORKFLOW_ID": "run-1", "ARTIFACTS_DIR": "/artifacts"}
    with mock.patch.dict(os.environ, env, clear=True):
        ptr = boundary.pointer("p")
        refused = []
        for key in ptr:
            try:
                boundary.resolve({**ptr, key: "run-2"})
            except ValueError as error:
                if "ほかの run" in str(error):
                    refused.append(key)
    return refused


def _min_path_length() -> int:
    return next(n for n in range(3) if not _rejects("a" * n))


def _ts_chars(literal: str) -> set[str]:
    """TS の字の並び（'\\\\'・'\\0' などのエスケープ）を字の集まりに戻す"""
    return set(literal.encode().decode("unicode_escape"))


def _asf_folder_key() -> str:
    """pack.load が asf.folder に入れる factory/pack.json の鍵（鍵ごとに自分の名を値にして読ませる）"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "factory").mkdir()
        (root / "pack.json").write_text(json.dumps({"ours": {"folder": "ours"}}), encoding="utf-8")
        asf = {key: key for key in pack.REQUIRED["factory/pack.json"]} | {"integration_revision_required": "0" * 40}
        (root / "factory/pack.json").write_text(json.dumps(asf), encoding="utf-8")
        return pack.load(root)["asf"]["folder"]


def pinned_source(cache: str | None, commit: str) -> pathlib.Path:
    """取り置いた Archon の源 <cache>/archon/<commit> を照らして返す。cache が無いか置き場が無ければ名前つきで見送る。
    源の字を読むだけなので bun は要らず、archon_source を通さない（無い置き場を作らない）"""
    if not cache:
        raise unittest.SkipTest(f"Archon の源が無い: 置き場の環境変数 {CACHE_ENV} が無い")
    source = pathlib.Path(cache) / "archon" / commit
    if not source.is_dir():
        raise unittest.SkipTest(f"Archon の源が無い: {source} が無い")
    place._verify(source, commit)
    return source


def _workflow_run_shape() -> list[str]:
    argv = place.workflow_run(pathlib.Path("/S"), pathlib.Path("/W"), pathlib.Path("/C"), "NAME", "ARG")
    placeholders = {"/S/" + place.ENTRY: "<source>/ENTRY", "/C": "<cwd>", "/W": "<workflow-source>"}
    shape = [placeholders.get(arg, arg) for arg in argv]
    if shape[-2:] == ["NAME", "ARG"]:
        shape[-2:] = ["<args>"]
    return shape


SEPARATOR_CANDIDATES = "/\\:"

# consumer にあって写し（place.workflow_run は bun を固定し、いつも --workflow-source を付ける）に無い分かれ道。
# 食い違いは直さず名前をつけて置き（#36）、元の字が変われば赤にする。
CONSUMER_ONLY = {
    "起こす bun を設定で差し替える": 'settings.get("bun", "bun")',
    "resume の時は --workflow-source を付けない": "if not resuming:",
    "工程の既定の入力を引数に差し込む": "args = with_default_inputs(name, args, options, root)",
}

CONSUMER = "factory/consumer.py"
CONSUMER_ROWS = (
    Row("本体の入口 ENTRY", lambda: place.ENTRY, CONSUMER, r'^ENTRY = "([^"]+)"$'),
    Row("工程の置き場 WORKFLOW_FOLDER", lambda: place.WORKFLOW_FOLDER, CONSUMER,
        r'source / "([^"]+)"\)\.rglob\("\*"\):\n\s+if path\.suffix not in \(".yaml", ".yml"\) or path in found'),
    Row("工程を起こす引数の並び（bun の設定も resume も無い時）", _workflow_run_shape, CONSUMER,
        r'return \[settings\.get\("bun", "([^"]+)"\), str\(source / ENTRY\)\]'
        r'.*native = \["(workflow)", action, "(--cwd)", str\(root\)\]'
        r'.*native \+= \["(--workflow-source)", str\(source\)\]'
        r'.*native \+= args\n',
        lambda m: [m[1], "<source>/ENTRY", m[2], "run", m[3], "<cwd>", m[4], "<workflow-source>", "<args>"]),
    Row("写しに無い consumer の分かれ道", lambda: list(CONSUMER_ONLY.values()), CONSUMER,
        r'return \[([^\n]+?), str\(source / ENTRY\)\]'
        r'.*\n\s+(if [^\n]+:)\n\s+native \+= \["--workflow-source", str\(source\)\]'
        r'\n\s+(args = [^\n]+)\n\s+native \+= args\n',
        lambda m: list(m.groups())),
    Row("commit は 40 字の小文字の hash", lambda: pack.FULL_SHA.pattern, CONSUMER,
        r'not re\.fullmatch\(r"([^"]+)", revision\)'),
    Row("ASF の工程の置き場の鍵", _asf_folder_key, CONSUMER,
        r'\(ENTRY, "package\.json", "bun\.lock", MANIFEST\["(\w+)"\]\)'),
)

POINTER = "packages/workflows/src/artifact-pointer.ts"
POINTER_SCHEMA = "packages/workflows/src/schemas/artifact-pointer.ts"
ARCHON_ROWS = (
    Row("指し札の型", lambda: boundary.POINTER_TYPE, POINTER_SCHEMA,
        r"export const ARTIFACT_POINTER_TYPE = '([^']+)';"),
    Row("指し札の欄", _pointer_fields, POINTER_SCHEMA,
        r"export const artifactPointerSchema = z\.object\(\{([^}]*)\}\);",
        lambda m: sorted(re.findall(r"^\s*(\w+):", m[1], re.M))),
    Row("指し札のパスの最短の長さ", _min_path_length, POINTER_SCHEMA,
        r"^\s*path: z\.string\(\)\.min\((\d+)\),$", lambda m: int(m[1])),
    Row("同じ run の決まり（照らす欄）", _same_run_fields, POINTER,
        r"if \(pointer\.(\w+) !== currentRun\.id\)", lambda m: [m[1]]),
    Row("パスの NUL を拒む", lambda: _rejects("a\0b"), POINTER,
        r"if \(pointer\.path\.includes\('\\0'\)\) return", lambda m: True),
    Row("パスの頭の区切りを拒む", lambda: {c for c in SEPARATOR_CANDIDATES if _rejects(c + "a")}, POINTER,
        r"if \(isAbsolute\(pointer\.path\) \|\| pointer\.path\.startsWith\('(.+?)'\) \|\| pointer\.path\.startsWith\('(.+?)'\)\)",
        lambda m: _ts_chars(m[1]) | _ts_chars(m[2])),
    Row(".. を探す区切り", lambda: {c for c in SEPARATOR_CANDIDATES if _rejects(f"a{c}..{c}b")}, POINTER,
        r"if \(pointer\.path\.split\(/\[(.+?)\]/\)\.includes\('\.\.'\)\)", lambda m: _ts_chars(m[1])),
    Row("末尾の / を拒む（stat が ENOTDIR で拒む）", lambda: _rejects("a/"), POINTER,
        r"if \(code === 'ENOENT' \|\| code === 'ENOTDIR'\) \{\n\s*return `\$\{where\} refers to a file that does not exist",
        lambda m: True),
    Row("run の id の環境変数", lambda: _env_read_by(lambda: boundary.pointer("p"), {}),
        "packages/workflows/src/exec-environment.ts", r"^\s*(\w+): context\.workflowId,$"),
    Row("run の成果物の置き場の環境変数",
        lambda: _env_read_by(lambda: boundary.resolve({"type": boundary.POINTER_TYPE, "run_id": "r", "path": "p"}),
                             {"WORKFLOW_ID": "r"}),
        "packages/workflows/src/exec-environment.ts", r"^\s*(\w+): context\.artifactsDir,$"),
    Row("入力の環境変数の鍵", lambda: re.search(r"入力は環境変数 (\w+)<UPPER_SNAKE>", boundary.__doc__)[1],
        "packages/workflows/src/schemas/dag-node.ts",
        r"export function inputEnvKey\(name: string\): string \{\n\s*return `(\w+)\$\{name\.replace\(/-/g, '_'\)\.toUpperCase\(\)\}`;"),
    Row("工程の置き場 WORKFLOW_FOLDER", lambda: place.WORKFLOW_FOLDER, "packages/paths/src/archon-paths.ts",
        r"export function getWorkflowFolderSearchPaths\(\): string\[\] \{\n\s*return \['([^']+)'\];"),
)


class ContractTest(unittest.TestCase):
    def check(self, source: pathlib.Path, rows: tuple[Row, ...]) -> None:
        for row in rows:
            with self.subTest(row.name):
                found = re.search(row.pattern, (source / row.file).read_text(encoding="utf-8"), re.M | re.S)
                if found is None:
                    self.fail(f"{source / row.file} に「{row.name}」の形が無い（元の形が変わった）: {row.pattern}")
                self.assertEqual(row.copy(), row.value(found), f"「{row.name}」の写しが {row.file} とずれた")


class ConsumerContractTest(ContractTest):
    def test_copies_match_asf_consumer(self):
        self.check(ROOT, CONSUMER_ROWS)


class ArchonContractTest(ContractTest):
    def test_copies_match_pinned_archon_source(self):
        source = pinned_source(os.environ.get(CACHE_ENV), pack.load(ROOT)["archon"]["commit"])
        self.check(source, ARCHON_ROWS)


class PinnedSourceTest(unittest.TestCase):
    """置き場は使い捨ての git リポジトリ。commit はその HEAD"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache = pathlib.Path(tmp.name)

    def held(self) -> tuple[pathlib.Path, str]:
        source = self.cache / "archon" / "pending"
        (source / "node_modules").mkdir(parents=True)
        (source / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        git(source, "init", "-q")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "seed")
        commit = git(source, "rev-parse", "HEAD")
        return source.rename(source.with_name(commit)), commit

    def test_held_source_is_returned(self):
        source, commit = self.held()
        self.assertEqual(pinned_source(str(self.cache), commit), source)

    def test_other_head_is_red_not_skipped(self):
        source, _ = self.held()
        other = "0" * 40
        source.rename(source.with_name(other))
        with self.assertRaisesRegex(RuntimeError, "HEAD"):
            pinned_source(str(self.cache), other)

    def test_dirty_source_is_red_not_skipped(self):
        source, commit = self.held()
        (source / "edited").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "変更が在る"):
            pinned_source(str(self.cache), commit)

    def test_skips_with_the_reason_and_creates_nothing(self):
        for name, cache, said in (("環境変数が無い", None, CACHE_ENV), ("置き場が無い", str(self.cache), "archon")):
            with self.subTest(name):
                with self.assertRaisesRegex(unittest.SkipTest, f"Archon の源が無い: .*{said}"):
                    pinned_source(cache, "0" * 40)
        self.assertEqual(list(self.cache.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
