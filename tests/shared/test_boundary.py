"""境の口（workflows/.shared/boundary.py）を、偽の環境と偽の run の置き場で確かめる。lib_root は止めた Archon の run の中でも確かめる（tests/archon.py）。"""
import ast
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests import archon
from tests.bin import hermetic

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = ROOT / "tests" / "layers" / "seeds"
ROOT_ENV = "WORKS_FACTORY_ROOT"


def load_boundary():
    # .shared は import の名にならないので、ファイルから読む（境の口が読む埋め skip_value も同じ置き場から）。
    # Archon が置き場をバイトで照らすので __pycache__ を作らない
    shared = str(ROOT / "workflows" / ".shared")
    if shared not in sys.path:
        sys.path.append(shared)
    spec = importlib.util.spec_from_file_location("boundary", ROOT / "workflows" / ".shared" / "boundary.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


boundary = load_boundary()


def archon_spellings(source: str) -> list[str]:
    """script の字の定数のうち、境が持つ Archon の事実を写した物（作業ツリーの中の工程の写し .archon・控えの根の STATE_DIR と
    works-factory・Archon の変数の名の 2 つ以上の並び）。docstring（式だけの文の字）は除く。注は ast に残らない"""
    tree = ast.parse(source)
    prose = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    runner = boundary.RUNNER_NAMES | set(boundary.RUNNER_PREFIXES)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose:
            if node.value.rstrip("/") == boundary.RUNTIME_COPY or node.value.startswith(boundary.RUNTIME_COPY_PREFIX) \
                    or node.value in (boundary.SHARED_CACHE_ENV, boundary.SHARED_CACHE):
                found.append(f"{node.lineno}: {node.value!r}")
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            names = [e.value for e in node.elts if isinstance(e, ast.Constant) and e.value in runner]
            if len(names) >= 2:
                found.append(f"{node.lineno}: {names!r}")
    return found


class ArchonFactsCase(unittest.TestCase):
    """Archon に向いた事実（工程の写しの置き場・run をまたぐ控えの根・Archon の変数・輪の頭の前の周の理由）は境の 1 か所が持つ"""
    maxDiff = None

    def test_runtime_copy_prefix_and_dirs_come_from_one_name(self):
        self.assertEqual(boundary.RUNTIME_COPY, ".archon")
        self.assertEqual(boundary.RUNTIME_COPY_PREFIX, boundary.RUNTIME_COPY + "/")
        self.assertEqual(boundary.RUNTIME_COPY_DIRS, ((boundary.RUNTIME_COPY,),))
        self.assertEqual(boundary.SKIP, (boundary.RUNTIME_COPY_PREFIX,))

    def test_shared_cache_is_under_state_dir_or_none(self):
        self.assertIn(boundary.SHARED_CACHE_ENV, boundary.RUNNER_NAMES)
        with mock.patch.dict(os.environ, {"STATE_DIR": "/state"}):
            self.assertEqual(boundary.shared_cache(), pathlib.Path("/state/works-factory"))
        for absent in ({"STATE_DIR": ""}, {}):
            with mock.patch.dict(os.environ, absent):
                if not absent:
                    os.environ.pop("STATE_DIR", None)
                self.assertIsNone(boundary.shared_cache())

    def test_test_children_never_get_a_runner_name(self):
        """Archon の変数の名は境の 1 か所から引く: RUNNER_NAMES の全部と、RUNNER_PREFIXES の各頭に X を付けた名は、親の環境に
        在っても hermetic.child_env の子に届かない（試験の子が run の中と手元で違う結果を返さない）"""
        runner = {*boundary.RUNNER_NAMES, *(prefix + "X" for prefix in boundary.RUNNER_PREFIXES)}
        with mock.patch.dict(os.environ, dict.fromkeys(runner, "parent")):
            self.assertEqual(sorted(runner & hermetic.child_env().keys()), [])

    def test_drop_runner_env_drops_named_and_prefixed_only(self):
        runner = {"ARCHON_NODE_EXECUTION": "{}", "INPUTS_REASON": "r", "CONTEXT": "c", "WORKFLOW_ID": "run-1", "STATE_DIR": "/s"}
        user = {"CONTEXT_PATH": "u", "MY_CONTEXT": "u", "ARCHONISH": "u", "INPUTS": "u"}
        with mock.patch.dict(os.environ, {**runner, **user}):
            boundary.drop_runner_env()
            self.assertEqual([n for n in runner if n in os.environ], [])
            self.assertEqual({n: os.environ.get(n) for n in user}, user)

    def test_drop_runner_env_aims_the_user_env_marker_at_the_line_place(self):
        """#504: 印の置き場はメイングラフの run の置き場。fix の組の子の run は入力 out_dir から辿り、辿れなければ古い値も外す"""
        stale = {boundary.USER_ENV_RAN_DIR: "/stale"}
        for name, env, want in (("メイングラフの run", {"ARTIFACTS_DIR": "/line"}, "/line"),
                                ("組の子の run", {"ARTIFACTS_DIR": "/child", "INPUTS_OUT_DIR": "/line/fix/fix/groups"}, "/line"),
                                ("形の違う out_dir", {"ARTIFACTS_DIR": "/child", "INPUTS_OUT_DIR": "/elsewhere/out"}, None)):
            with self.subTest(name), mock.patch.dict(os.environ, {**stale, **env}):
                boundary.drop_runner_env()
                self.assertEqual(os.environ.get(boundary.USER_ENV_RAN_DIR), want)

    def test_user_env_marker_name_is_lib_userenvs(self):
        sys.path.append(str(boundary.lib_root()))
        import userenv
        self.assertEqual(boundary.USER_ENV_RAN_DIR, userenv.RAN_DIR_ENV)

    def test_prev_reason_returns_the_inputs_reason(self):
        for reason in ("前の周の拒みの理由", ""):
            with mock.patch.dict(os.environ, {"INPUTS_REASON": reason}):
                self.assertEqual(boundary.prev_reason(), {"reason": reason})

    def test_block_scripts_do_not_spell_archon_facts(self):
        seeded = 'SKIP = (".archon/",)\nD = ((".archon",),)\nS = os.environ.get("STATE_DIR")\nR = Path(s) / "works-factory"\n' \
                 'N = ("ARCHON_", "CONTEXT")\n'
        self.assertEqual(len(archon_spellings(seeded)), 5, archon_spellings(seeded))
        self.assertEqual(archon_spellings('"""STATE_DIR の下 works-factory/ と .archon/"""\nX = ("WORKFLOW_ID",)\n'), [])
        found = {}
        for path in sorted((ROOT / "workflows").glob("*/scripts/**/*.py")):
            got = archon_spellings(path.read_text(encoding="utf-8"))
            if got:
                found[path.relative_to(ROOT).as_posix()] = got
        self.assertEqual(found, {})


class FakeRunTest(unittest.TestCase):
    """Archon が script の節に渡す環境（WORKFLOW_ID・ARTIFACTS_DIR）を偽の run で作る"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.artifacts = pathlib.Path(tmp.name)
        env = mock.patch.dict(os.environ, {"WORKFLOW_ID": "run-1", "ARTIFACTS_DIR": str(self.artifacts)})
        env.start()
        self.addCleanup(env.stop)


class BlockPlaceTest(FakeRunTest):
    """サブグラフの script の置き場（include ごと）と run の作業ツリー"""

    def test_place_is_the_include_folder_under_the_block(self):
        for node, want in ((json.dumps({"path": "refix__fix-prep"}), "refix"), (json.dumps({"path": "fix-prep"}), "fix"),
                           ("{", "fix"), ("", "fix"), (json.dumps({"path": "__x"}), "fix")):
            with self.subTest(node=node), mock.patch.dict(os.environ, {"ARCHON_NODE_EXECUTION": node}):
                self.assertEqual(boundary.include_name("fix"), want)
                got = boundary.place("fix")
                self.assertEqual(got, self.artifacts / "fix" / want)
                self.assertTrue(got.is_dir(), "無ければ作る")

    def test_work_tree_is_the_git_top(self):
        repo = self.artifacts / "repo"
        (repo / "sub").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        cwd = os.getcwd()
        os.chdir(repo / "sub")
        try:
            self.assertEqual(boundary.work_tree().resolve(), repo.resolve())
        finally:
            os.chdir(cwd)


class PointerTest(FakeRunTest):
    def test_pointer_names_this_run(self):
        self.assertEqual(
            boundary.pointer("plan/plan.md"),
            {"type": "archon_artifact", "run_id": "run-1", "path": "plan/plan.md"},
        )


class ResolveTest(FakeRunTest):
    def test_resolve_returns_file_in_this_run(self):
        self.assertEqual(
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": "report.md"}),
            self.artifacts / "report.md",
        )

    def test_resolve_refuses_other_run(self):
        with self.assertRaisesRegex(ValueError, "run-2"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-2", "path": "report.md"})

    def test_resolve_refuses_bad_path(self):
        for rel in ("", "a\0b", "/x", "\\x", "../x", "..\\x", "a/../../x", "report.md/"):
            with self.subTest(rel=rel), self.assertRaisesRegex(ValueError, "相対"):
                boundary.resolve({"type": "archon_artifact", "run_id": "run-1", "path": rel})

    def test_resolve_refuses_missing_path(self):
        with self.assertRaisesRegex(ValueError, "相対"):
            boundary.resolve({"type": "archon_artifact", "run_id": "run-1"})

    def test_resolve_refuses_non_pointer(self):
        with self.assertRaisesRegex(ValueError, "archon_artifact"):
            boundary.resolve({"type": "file", "run_id": "run-1", "path": "report.md"})

    def test_rel_of_is_the_inverse_of_resolve(self):
        self.assertEqual(boundary.rel_of(self.artifacts / "report" / "report.md"), "report/report.md")
        with self.assertRaises(ValueError):
            boundary.rel_of(self.artifacts.parent / "elsewhere.md")


class ReturnsTest(unittest.TestCase):
    def test_returns_writes_one_json(self):
        obj = {"outcome": "完了", "items": [1, 2], "ptr": None}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            boundary.returns(obj)
        text = out.getvalue()
        value, end = json.JSONDecoder(parse_constant=self.refuse_constant).raw_decode(text)
        self.assertEqual(value, obj)
        self.assertEqual(text[end:].strip(), "")

    def test_returns_refuses_nan(self):
        for number in (float("nan"), float("inf")):
            with self.subTest(number=number), self.assertRaises(ValueError):
                boundary.returns({"x": number})

    @staticmethod
    def refuse_constant(name):
        raise ValueError(f"JSON でない値: {name}")


class LibRootTest(unittest.TestCase):
    def test_lib_root_is_repository_lib(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(ROOT_ENV, None)
            self.assertEqual(boundary.lib_root(), ROOT / "lib")

    def test_lib_root_follows_works_factory_root(self):
        with mock.patch.dict(os.environ, {ROOT_ENV: "/elsewhere"}):
            self.assertEqual(boundary.lib_root(), pathlib.Path("/elsewhere/lib"))

    def test_script_run_by_archon_finds_repository_lib(self):
        """Archon は run の始めに工程のフォルダを写し取り、script はその写しから走る。写しからは自分の置き場を辿っても lib/ に届かない"""
        with archon.tree(["hello"], SEEDS / "e1" / "workflows") as tree:
            done = archon.archon(tree, "workflow", "run", "works-factory-hello", "--no-worktree", "--cwd", str(tree))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        returned = [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{"lib"')]
        self.assertEqual(returned, [{"lib": str(ROOT / "lib")}], done.stdout)


if __name__ == "__main__":
    unittest.main()
