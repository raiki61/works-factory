"""Archon と ASF から手で写した約束（workflows/.shared/boundary.py・bin/_lib/place.py・bin/_lib/pack.py）を、写した元の字に照らす。

行ごとに「写しの値」と「元の中のその値の在り処（ファイルと正規表現）」を持ち、正規表現で引いた値と写しの値を比べる。
元に行の形が見つからない時も赤にする（元の形が変わった合図）。写しは直さず、ずれを赤にするだけ。

- ASF の消費者 factory/consumer.py は木に在るので常に照らす。
- 止めた Archon の源は、place.archon_source に渡した置き場（環境変数 WORKS_FACTORY_ARCHON_CACHE）の
  <置き場>/archon/<factory/pack.json の integration_revision_required>/ に取り置き済みの時だけ照らす。試験の中では取りに行かない。
"""
import os
import pathlib
import re
import unittest
from collections.abc import Callable
from typing import Any, NamedTuple
from unittest import mock

from bin._lib import pack, place
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


def _workflow_run_shape() -> list[str]:
    argv = place.workflow_run(pathlib.Path("/S"), pathlib.Path("/W"), pathlib.Path("/C"), "NAME", "ARG")
    placeholders = {"/S/" + place.ENTRY: "<source>/ENTRY", "/C": "<cwd>", "/W": "<workflow-source>"}
    shape = [placeholders.get(arg, arg) for arg in argv]
    if shape[-2:] == ["NAME", "ARG"]:
        shape[-2:] = ["<args>"]
    return shape


SEPARATOR_CANDIDATES = "/\\:"

CONSUMER = "factory/consumer.py"
CONSUMER_ROWS = (
    Row("本体の入口 ENTRY", lambda: place.ENTRY, CONSUMER, r'^ENTRY = "([^"]+)"$'),
    Row("工程の置き場 WORKFLOW_FOLDER", lambda: place.WORKFLOW_FOLDER, CONSUMER,
        r'source / "([^"]+)"\)\.rglob\("\*"\):\n\s+if path\.suffix not in \(".yaml", ".yml"\) or path in found'),
    Row("工程を起こす引数の並び", _workflow_run_shape, CONSUMER,
        r'return \[settings\.get\("bun", "([^"]+)"\), str\(source / ENTRY\)\]'
        r'.*native = \["(workflow)", action, "(--cwd)", str\(root\)\]'
        r'.*native \+= \["(--workflow-source)", str\(source\)\]'
        r'.*native \+= args\n',
        lambda m: [m[1], "<source>/ENTRY", m[2], "run", m[3], "<cwd>", m[4], "<workflow-source>", "<args>"]),
    Row("commit は 40 字の小文字の hash", lambda: pack.FULL_SHA.pattern, CONSUMER,
        r'not re\.fullmatch\(r"([^"]+)", revision\)'),
    Row("ASF の工程の置き場の鍵", lambda: pack.REQUIRED["factory/pack.json"][2], CONSUMER,
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
        cache = os.environ.get(CACHE_ENV)
        if not cache:
            self.skipTest(f"Archon の源が無い: 置き場の環境変数 {CACHE_ENV} が無い")
        source = pathlib.Path(cache) / "archon" / pack.load(ROOT)["archon"]["commit"]
        if not source.is_dir():
            self.skipTest(f"Archon の源が無い: {source}")
        self.check(source, ARCHON_ROWS)


if __name__ == "__main__":
    unittest.main()
