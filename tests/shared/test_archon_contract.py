"""Archon と ASF から手で写した約束（workflows/.shared/boundary.py・bin/_lib/place.py・bin/_lib/pack.py・bin/_lib/launcher.py・
bin/_lib/startpoint.py・bin/_lib/childsweep.py・tests/workflows/test_uv_scripts.py・lib/answer.py が launcher の頭で組む答えの行・
tests/layers/scan.py の役の節の鍵・test-gate の run.py が対象のテストの前に落とす Archon の変数の名）を、写した元の字に照らす。

行ごとに「写しの値」と「元の中のその値の在り処（ファイルと正規表現）」を持ち、正規表現で引いた値と写しの値を比べる。
元に行の形が見つからない時も赤にする（元の形が変わった合図）。写しは直さず、ずれを赤にするだけ。

- ASF の消費者 factory/consumer.py は木に在るので常に照らす。
- 止めた Archon の源は、tests/archon.py の決まりで見つかる時だけ照らす（壊れていれば赤）。
"""
import ast
import os
import pathlib
import json
import re
import shlex
import sys
import tempfile
import unittest
from collections.abc import Callable
from typing import Any, NamedTuple
from unittest import mock

from bin._lib import childsweep, launcher, pack, place, startpoint
from lib import answer
from tests import archon
from tests.archon import CACHE_ENV, pinned_source
from tests.bin.gitkit import git
from tests.layers import scan
from tests.shared.test_boundary import boundary
from tests.shared.test_fence import fence
from tests.workflows import test_uv_scripts

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:   # 後ろに足す（頭に入れると lib/tests が根の tests を隠す）
    sys.path.append(str(ROOT / "lib"))
import runreport  # noqa: E402


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
        ours = {key.removeprefix("ours."): key for key in pack.REQUIRED["pack.json"]}
        (root / "pack.json").write_text(json.dumps({"ours": ours}), encoding="utf-8")
        asf = {key: key for key in pack.REQUIRED["factory/pack.json"]} | {"integration_revision_required": "0" * 40}
        (root / "factory/pack.json").write_text(json.dumps(asf), encoding="utf-8")
        return pack.load(root)["asf"]["folder"]


def _workflow_run_shape() -> list[str]:
    argv = place.workflow_run(pathlib.Path("/S"), pathlib.Path("/W"), pathlib.Path("/C"), "NAME", "ARG")
    placeholders = {"/S/" + place.ENTRY: "<source>/ENTRY", "/C": "<cwd>", "/W": "<workflow-source>"}
    shape = [placeholders.get(arg, arg) for arg in argv]
    if shape[-2:] == ["NAME", "ARG"]:
        shape[-2:] = ["<args>"]
    return shape


def _answer_argv() -> list[str]:
    """関所の答えの行のうち、殻が Archon にそのまま渡す引数（殻のパスの後ろ）"""
    env = {answer.ENV: launcher.answer_head(pathlib.Path("/H"), pathlib.Path("/T"))}
    argv = shlex.split(answer.line("RUN", "continue", "TEXT", env=env))
    return argv[argv.index(str(launcher.ROOT / "bin" / launcher.NAME)) + 1:]


def _answer_options() -> list[str]:
    return [arg.removeprefix("--") for arg in _answer_argv() if arg.startswith("--")]


def _answer_positions() -> list[int]:
    """Archon が旗とその値を抜いた位置引数の中の、run の id・答えの語・一言の位置"""
    argv = _answer_argv()
    values = {i + 1 for i, arg in enumerate(argv) if arg.startswith("--")}
    positionals = [arg for i, arg in enumerate(argv) if i not in values and not arg.startswith("--")]
    return [positionals.index(arg) for arg in ("RUN", "continue", "TEXT")]


def _runner_vars() -> dict:
    """境 boundary.py の RUNNER_PREFIXES・RUNNER_NAMES（字から読む）"""
    tree = ast.parse((ROOT / "workflows/.shared/boundary.py").read_text(encoding="utf-8"))
    return {t.id: ast.literal_eval(n.value.args[0] if isinstance(n.value, ast.Call) else n.value)
            for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
            if isinstance(t, ast.Name) and t.id in ("RUNNER_PREFIXES", "RUNNER_NAMES")}


def _exec_node_names(body: str) -> list[str]:
    """buildExecNodeEnvironment が返す物の鍵のうち、頭の一致（RUNNER_PREFIXES）で落ちない物"""
    return sorted(k for k in re.findall(r"^    (\w+):", body, re.M) if not k.startswith(_runner_vars()["RUNNER_PREFIXES"]))


def _agent_guards(transform: str) -> list[str]:
    """節の形を組む transform の if の分かれのうち kind: 'agent' を返す物の、照らす data の欄。
    data.<欄> で始まらない分かれは、その if の行を値にして赤にする（新しい AI の節の形を黙って見落とさない）"""
    guards = []
    for branch in re.split(r"^    if \(", transform, flags=re.M):
        if "kind: 'agent'" in branch:
            field = re.match(r"data\.(\w+) !== undefined", branch)
            guards.append(field[1] if field else branch.split("\n", 1)[0])
    return sorted(guards)


def _string_options(block: str) -> set[str]:
    return set(re.findall(r"^\s*'?([\w-]+)'?: \{ type: 'string'", block, re.M))


def _skip_names() -> list[str]:
    return sorted(flag.removeprefix("--") for flag in startpoint.SKIP_FLAGS)


def _skip_short() -> list[str]:
    """殻が --from を足さない短い名の字（大小の英字のうち、-<字> が SKIP_SHORT に当たる物）"""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return [c for c in letters + letters.upper() if startpoint.SKIP_SHORT.fullmatch(f"-{c}")]


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
SDK = "packages/providers/node_modules/@anthropic-ai/claude-agent-sdk/sdk.mjs"
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
    Row("script の節に立つ変数の名（test-gate・fix が対象のテストの前に落とす）", lambda: sorted(_runner_vars()["RUNNER_NAMES"]),
        "packages/workflows/src/exec-environment.ts",
        r"export function buildExecNodeEnvironment\(context: ExecNodeEnvironmentContext\): NodeJS\.ProcessEnv \{\n.*?"
        r"  return \{\n(.*?)\n  \};\n\}", lambda m: _exec_node_names(m[1])),
    Row("入力の環境変数の鍵", lambda: re.search(r"入力は環境変数 (\w+)<UPPER_SNAKE>", boundary.__doc__)[1],
        "packages/workflows/src/schemas/dag-node.ts",
        r"export function inputEnvKey\(name: string\): string \{\n\s*return `(\w+)\$\{name\.replace\(/-/g, '_'\)\.toUpperCase\(\)\}`;"),
    Row("AI の節（agent）の形を決める節の鍵（scan の役の節）", lambda: sorted(scan.ROLE_KINDS),
        "packages/workflows/src/schemas/dag-node.ts",
        r"^  \.transform\(\(data\): DagNode \| IncludeDirective => \{\n(.*?)^  \}\)", lambda m: _agent_guards(m[1])),
    Row("output_format で宣言した欄の null は空の解決（境の口は空の字を null と読む）", lambda: boundary.value("") is None,
        "packages/workflows/src/output-ref.ts",
        r"if \(paths !== undefined && \(value === undefined \|\| value === null\)\) return \{ kind: 'empty' \};",
        lambda m: True),
    Row("include の入力は節の返りの欄を字に差し込み、空の解決は空の字で届く（境の口はそれを null と読む）", lambda: None,
        "packages/workflows/src/dag-executor.ts",
        r"readComposedMeta\(node\)\?\.inputs \?\? \{\}\)\) \{\n.*?\? substituteNodeOutputRefs\(\n"
        r".*?^export function substituteNodeOutputRefs\(\n"
        r".*?resolution = resolveNodeOutputField\(nodeOutput, nodeId, field, match\);\n"
        r".*?if \(resolution\.kind === 'empty'\) return escapedForBash \? \"''\" : '([^']*)';",
        lambda m: boundary.value(m[1])),
    Row("工程の置き場 WORKFLOW_FOLDER", lambda: place.WORKFLOW_FOLDER, "packages/paths/src/archon-paths.ts",
        r"export function getWorkflowFolderSearchPaths\(\): string\[\] \{\n\s*return \['([^']+)'\];"),
    Row("工程を走らせる命令", lambda: sorted(launcher.EXECUTING - launcher.CONTINUING), "packages/cli/src/cli.ts",
        r"const executesWorkflow = \[([^\]]+)\]\.includes\(", lambda m: sorted(re.findall(r"'(\w+)'", m[1]))),
    Row("工程を続ける命令", lambda: sorted(launcher.CONTINUING), "packages/cli/src/cli.ts",
        r"if \(command === 'workflow' && \(subcommand === '(\w+)' \|\| subcommand === '(\w+)'\)\) \{\n"
        r"\s*const schedule", lambda m: sorted(m.groups())),
    Row("起こす claude の実行ファイルを替える環境変数（殻が書き込みの柵の包みを置く）", lambda: launcher.CLAUDE_BIN_ENV,
        "packages/providers/src/claude/binary-resolver.ts", r"^\s*const envPath = process\.env\.(\w+);$"),
    Row("節の sandbox は置き換えずに SDK へ渡す（包みが起動の直前に足す）", lambda: None,
        "packages/workflows/src/dag-executor.ts", r"^\s*sandbox: node\.sandbox \?\? workflowLevelOptions\.sandbox,$",
        lambda m: None),
    Row("節の設定は object のまま SDK へ渡す（SDK が JSON の字にする）", lambda: None,
        "packages/providers/src/claude/provider.ts", r"^\s*options\.settings = buildClaudePluginSettings\(", lambda m: None),
    Row("SDK は sandbox を設定の JSON の字の鍵に入れて --settings で渡す。設定のパスとは併せず、object の設定も JSON の字にする（包みが読む形）",
        lambda: (fence.SETTINGS, fence.DENY_WRITE[0]), SDK,
        r"function qje\(e\)\{let t=e\.trim\(\);return t\.startsWith\(\"\{\"\)&&t\.endsWith\(\"\}\"\)\}"
        r"function n2\(e,t\)\{let n=\{\.\.\.e\};if\(!t\)return n;.*?"
        r"if\(o&&!qje\(o\)\)throw Error\(\"Cannot use both a settings file path and the sandbox option\..*?"
        r"let s=\{(\w+):r\};if\(o\)try\{s=\{\.\.\.Ge\(o\),\1:r\}\}catch\{\}return n\.(\w+)=ie\(s\),n\}"
        r"function Rx\(e,t,n\)\{let r=String\(n\);if\(r\.length>1&&r\.startsWith\(\"-\"\)\)e\.push\(`--\$\{t\}=\$\{r\}`\);"
        r"else e\.push\(`--\$\{t\}`,r\)\}.*?"
        r"let (\w+)=n2\(\w+,\w+\);for\(let\[(\w+),(\w+)\]of Object\.entries\(\3\)\)if\(\5===null\)\w+\.push\(`--\$\{\4\}`\);"
        r"else Rx\(\w+,\4,\5\).*?"
        r"\2:typeof (\w+)===\"object\"\?ie\(\6\):\6,",
        lambda m: (f"--{m[2]}", m[1])),
    Row("script を探すフォルダの深さ", lambda: test_uv_scripts.DISCOVERY_DEPTH, "packages/workflows/src/script-discovery.ts",
        r"^const MAX_SCRIPT_DISCOVERY_DEPTH = (\d+);$", lambda m: int(m[1])),
    Row("答えの行の run の id・答えの語・一言の位置", _answer_positions, "packages/cli/src/cli.ts",
        r"case 'respond': \{\n\s*const respondRunId = positionals\[(\d+)\];\n\s*const decision = positionals\[(\d+)\];"
        r".*?positionals\.slice\((\d+)\)\.join\(' '\)", lambda m: [int(n) for n in m.groups()]),
    Row("答えの行の旗は上の段の値を取る旗", _answer_options, "packages/cli/src/args.ts",
        r"export const cliArgOptions: CliArgOptions = \{\n(.*?)\n\};",
        lambda m: [name for name in _answer_options() if name in _string_options(m[1])]),
    Row("殻が --from を足さない旗は Archon の旗", _skip_names, "packages/cli/src/args.ts",
        r"export const cliArgOptions: CliArgOptions = \{\n(.*?)\n\};",
        lambda m: sorted(set(_skip_names()) & set(re.findall(r"^\s*'?([\w-]+)'?: \{ type:", m[1], re.M)))),
    Row("殻が --from を足さない短い名は枝の旗の短い名", _skip_short, "packages/cli/src/args.ts",
        r"^\s*branch: \{ type: 'string', short: '(\w)' \},$", lambda m: [m[1]]),
    Row("子の枝の頭", lambda: childsweep.BRANCH_HEAD, "packages/isolation/src/providers/worktree.ts",
        r"return `(archon/task-)\$\{this\.slugify\(request\.identifier\)\}`;"),
    Row("子の枝の名の親の run の id の長さ", lambda: childsweep.RUN_HEAD,
        "packages/core/src/workflows/child-isolation-resolver.ts",
        r"return \[parentRunId\.slice\(0, (\d+)\), nodeSlug", lambda m: int(m[1])),
    Row("子の run の枝の名の鍵", lambda: childsweep.BRANCH_KEY, "packages/workflows/src/executor.ts",
        r"^\s*(branch_name): childIsolationEnv\.branchName,$"),
    Row("子の run の親の節の鍵", lambda: childsweep.NODE_KEY, "packages/workflows/src/schemas/workflow-run.ts",
        r"^\s*parentNodeId: '(\w+)',$"),
    Row("complete が消せた行", lambda: childsweep.COMPLETED, "packages/cli/src/commands/isolation.ts",
        r"console\.log\(`  (Completed: )\$\{branch\}`\);"),
    Row("complete の警告の行", lambda: childsweep.WARNING, "packages/cli/src/commands/isolation.ts",
        r"console\.warn\(`  (Warning: )\$\{warning\}`\);"),
    Row("子の run の親の run の鍵", lambda: childsweep.PARENT_KEY, "packages/workflows/src/schemas/workflow-run.ts",
        r"^\s*(parent_run_id): z\.string\(\)\.nullable\(\),$"),
    Row("run が終わった status", lambda: childsweep.DONE, "packages/workflows/src/schemas/workflow-run.ts",
        r"export const workflowRunStatusSchema = z\.enum\(\[[^\]]*'(completed)',"),
    Row("節が済んだ状態", lambda: childsweep.DONE, "packages/cli/src/commands/workflow.ts",
        r"case 'node_completed': \{\n[^}]*?state: '(\w+)',"),
    Row("include した節の id の継ぎ", lambda: childsweep.INCLUDE_SEP, "packages/workflows/src/include-expander.ts",
        r"const prefix = `\$\{includeNode\.id\}(\w+)`;"),
    Row("workflow get --json --verbose の節の一覧の鍵", lambda: childsweep.NODES, "packages/cli/src/commands/workflow.ts",
        r"^\s*(nodes): buildNodeSummaries\(events\),$"),
    Row("節の一覧の行の id と状態の鍵", lambda: [childsweep.NODE_ID, childsweep.STATE], "packages/cli/src/commands/workflow.ts",
        r"case 'node_completed': \{\n.*?summaries\.set\((\w+), \{\n\s*\1,\n\s*(\w+): 'completed',",
        lambda m: list(m.groups())),
    Row("run の記録の道具の呼びの行の型と節の欄", lambda: runreport.PROVIDER_ROW, "packages/workflows/src/logger.ts",
        r"type: '(provider_event)',\s*step: stepName,"),
    Row("道具の呼びの行の出来事の欄", lambda: runreport.PROVIDER_EVENT, "packages/workflows/src/schemas/provider-event.ts",
        r"^\s*(event): providerEventSchema,"),
    Row("出来事の道具の呼びの型", lambda: runreport.TOOL_CALL, "packages/provider-contract/src/events.ts",
        r"type: z\.literal\('(tool_call)'\)"),
    Row("道具の呼びの道具の名と入力の欄", lambda: [runreport.TOOL_NAME, runreport.TOOL_INPUT], "packages/provider-contract/src/events.ts",
        r"export const toolCallSchema = z\.object\(\{.*?^\s*(name): z\.string\(\),$.*?^\s*(rawInput): z$",
        lambda m: list(m.groups())),
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
        self.check(archon.source(), ARCHON_ROWS)


class BoundCopyTest(unittest.TestCase):
    """考えの柵の表（docs/concepts.json）がこの試験に縛らせた写しの行（bound）は、上の行が Archon に照らす写しのちょうど 1 行"""

    def test_bound_lines_are_the_copies_checked_against_archon(self):
        bounds = [(path, b["lines"]) for v in json.loads((ROOT / "docs/concepts.json").read_text(encoding="utf-8"))["concepts"].values()
                  for f in v["fences"] for b in f.get("bound") or [] if b["by"] == "tests/shared/test_archon_contract.py"
                  for path in b["paths"]]
        self.assertEqual(bounds, [("bin/_lib/startpoint.py", r"^SKIP_FLAGS = \(")])
        for path, lines in bounds:
            found = [line for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if re.search(lines, line)]
            self.assertEqual(len(found), 1, found)
            self.assertEqual(ast.literal_eval(found[0].split("=", 1)[1].strip()), startpoint.SKIP_FLAGS)


class PinnedSourceTest(unittest.TestCase):
    """置き場は使い捨ての git リポジトリ。commit はその HEAD"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache = pathlib.Path(tmp.name)

    def held(self) -> tuple[pathlib.Path, str]:
        source = place.archon_folder(self.cache, "pending")
        (source / "node_modules").mkdir(parents=True)
        (source / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        git(source, "init", "-q")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "seed")
        commit = git(source, "rev-parse", "HEAD")
        return source.rename(source.with_name(commit)), commit

    def assert_red(self, commit: str, said: str):
        """assertRaises(RuntimeError) は SkipTest を素通しして見送りに数えるので、見送りもここで落とす"""
        with self.assertRaises(Exception) as caught:
            pinned_source(str(self.cache), commit)
        self.assertIsInstance(caught.exception, RuntimeError)
        self.assertRegex(str(caught.exception), said)

    def test_held_source_is_returned(self):
        source, commit = self.held()
        self.assertEqual(pinned_source(str(self.cache), commit), source)

    def test_other_head_is_red_not_skipped(self):
        source, _ = self.held()
        other = "0" * 40
        source.rename(source.with_name(other))
        self.assert_red(other, "HEAD")

    def test_dirty_source_is_red_not_skipped(self):
        source, commit = self.held()
        (source / "edited").write_text("x", encoding="utf-8")
        self.assert_red(commit, "変更が在る")

    def assert_absent_raises(self, required: dict[str, str], raised: type[BaseException]):
        for name, cache, said in (("環境変数が無い", None, CACHE_ENV), ("置き場が無い", str(self.cache), "archon")):
            with self.subTest(name), mock.patch.dict(os.environ, required):
                if not required:
                    os.environ.pop(archon.REQUIRED_ENV, None)
                with self.assertRaises(BaseException) as caught:
                    pinned_source(cache, "0" * 40)
                self.assertIs(type(caught.exception), raised)
                self.assertRegex(str(caught.exception), f"Archon の源が無い: .*{said}")
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_skips_with_the_reason_and_creates_nothing(self):
        self.assert_absent_raises({}, unittest.SkipTest)

    def test_required_fails_with_the_reason_instead_of_skipping(self):
        """CI は REQUIRED_ENV を立てる。用意が崩れても Archon の要る試験が黙って見送られない"""
        self.assert_absent_raises({archon.REQUIRED_ENV: "1"}, AssertionError)


if __name__ == "__main__":
    unittest.main()
