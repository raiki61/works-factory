"""読むだけの役の claude の包み（workflows/.shared/fence.py。埋め P5）を確かめる。

一覧の組み方・argv の書き換え・main は使い捨ての git の木と偽の claude で確かめる。RealClaudeTest は本物の claude を偽の API で起こし、
sandbox が包みの足した一覧への書き込みを本当に止めることを確かめる。起こす前に、共有の部品 tests/bin/sandbox_probe.py で sandbox の
Bash と Grep が立つかを 1 回確かめる（sandbox_refused）。本物の claude か sandbox の道具が無い所と、Linux で名前空間が立たない所は名前つきで
見送り、ほかの層の壊れは赤にする。
"""
import datetime
import importlib.util
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from bin._lib import isolate, launcher
from tests.bin import hermetic, sandbox_probe
from tests.bin.gitkit import git
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
FENCE = ROOT / "workflows" / ".shared" / "fence.py"


def load_fence():
    # .shared は import の名にならないので、ファイルから読む。Archon が置き場をバイトで照らすので __pycache__ を作らない
    spec = importlib.util.spec_from_file_location("fence", FENCE)
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


fence = load_fence()


def make_tree(tmp: pathlib.Path) -> dict:
    """本体の repo・linked worktree・本体の下の worktree（worktree.path で置き場を替えた形）と、隔離した run の置き場"""
    main = tmp / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "f").write_text("x\n", encoding="utf-8")
    git(main, "add", "f")
    git(main, "commit", "-q", "-m", "seed")
    linked = tmp / "linked"
    git(main, "worktree", "add", "-q", "-b", "a", str(linked))
    nested = main / ".worktrees" / "x"
    git(main, "worktree", "add", "-q", "-b", "b", str(nested))
    child = isolate.isolate({}, tmp / "run-home")
    return {"main": main, "linked": linked, "nested": nested, "child": child, "own": [str(tmp / "run-home" / "claude-fence")]}


def settings_with(deny: list) -> str:
    return json.dumps({"sandbox": {"enabled": True, "filesystem": {"allowWrite": ["/"], "denyWrite": deny}}})


class ProtectedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)

    def test_lists_every_tree_of_the_repository(self):
        t = make_tree(self.tmp)
        got = fence.protected(str(t["linked"]), t["child"]["ARCHON_HOME"], t["child"]["CLAUDE_CONFIG_DIR"], t["own"])
        self.assertEqual(got, [*sorted([str(t["linked"]), str(t["main"] / ".git"), str(t["main"]), str(t["nested"]),
                                        t["child"]["ARCHON_HOME"]]),
                               t["child"]["CLAUDE_CONFIG_DIR"], *t["own"]])

    def test_outside_git_lists_only_the_given_paths(self):
        cwd = self.tmp / "plain"
        cwd.mkdir()
        got = fence.protected(str(cwd), "/a", "/c", ["/o"])
        self.assertEqual(got, [*sorted([str(cwd), "/a"]), "/c", "/o"])

    def test_without_git_refuses(self):
        with mock.patch.dict(os.environ, {"PATH": str(self.tmp)}):
            with self.assertRaises(fence.Refused):
                fence.protected(str(self.tmp), "/a", "/c", [])


class ProtectedPathsCopiedTest(unittest.TestCase):
    """写した protected_paths を縛る、今の works（raiki61/claude-plugins@2aa7c66cf7ab）の試験の写し: graphloops/tests/simulate.py の
    test_tooled_launch_fence の守る場所の 2 つの check と、graphloops/tests/py/test_role_run_stop.py の
    test_protected_paths_is_undecided_when_git_answers_partly（pytest の parametrize を subTest に直した）"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)

    def test_tooled_launch_fence(self):
        repo, other, board = self.tmp / "repo", self.tmp / "wt2", self.tmp / "board"
        board.mkdir()
        for args in (["init", "-q", str(repo)], ["-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                                                      "--allow-empty", "-m", "x"], ["-C", str(repo), "worktree", "add", "-q", str(other)]):
            subprocess.run(["git", *args], capture_output=True, check=True, env=hermetic.child_env())
        real = os.path.realpath
        want_deny = sorted({real(repo), real(repo / ".git"), real(other), real(board)})
        self.assertEqual(fence.protected_paths(repo, board), want_deny,
                         "書き込みを止める場所は、自分を含む作業ツリーの根の全部・共有の .git・盤面の置き場")
        plain_dir = self.tmp / "plain"
        plain_dir.mkdir()
        self.assertEqual(fence.protected_paths(plain_dir, board), sorted({real(plain_dir), real(board)}),
                         "git の作業ツリーでない場所では cwd と盤面だけを守る")

    def test_protected_paths_is_undecided_when_git_answers_partly(self):
        """共有の .git か作業ツリーの一覧のどちらかが引けなければ、守る場所は決まらない（None——sandbox の形を選ばない）"""
        for name, worktrees in (("worktree-list-fails", (False, [], "失敗")), ("no-common-dir", (True, ["worktree /w"], ""))):
            with self.subTest(name):
                common = (True, [], "") if worktrees[0] else (True, [str(self.tmp / ".git")], "")
                with mock.patch.object(fence, "_git", lambda cwd, *args: common if "rev-parse" in args else worktrees):
                    self.assertIsNone(fence.protected_paths(self.tmp))


class FencedArgvTest(unittest.TestCase):
    HOME = "/h/home"
    ARCHON = "/h/archon-home"
    PATHS = ["/w", "/w/.git"]

    def fenced(self, argv):
        with mock.patch.dict(os.environ, {"HOME": self.HOME}):
            return fence.fenced_argv(argv, self.ARCHON, lambda: self.PATHS)

    def test_marked_settings_get_the_list_in_both_spellings(self):
        settings = settings_with(["/w", scan.NO_TREE_WRITE])
        for argv, at in ((["-p", "x", "--settings", settings, "--model", "m"], 3),
                         (["-p", "x", f"--settings={settings}", "--model", "m"], 2)):
            with self.subTest(argv=argv[at - 1:at + 1]):
                got = self.fenced(argv)
                self.assertEqual(len(got), len(argv))
                self.assertEqual(got[-2:], ["--model", "m"])
                value = got[at].removeprefix("--settings=")
                fs = json.loads(value)["sandbox"]["filesystem"]
                self.assertEqual(fs["denyWrite"], ["/w", scan.NO_TREE_WRITE, "/w/.git"])
                self.assertEqual(fs["allowWrite"], ["/"])

    def test_unmarked_launches_are_unchanged(self):
        writer = json.dumps({"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
        for argv in (["-p", "x", "--settings", writer],
                     ["-p", "x", "--settings", settings_with(["~/../other"])],
                     ["--settings=" + settings_with(["/elsewhere"])],
                     ["--version"]):
            with self.subTest(argv=argv):
                self.assertIs(self.fenced(argv), argv)

    def test_undecidable_settings_are_refused(self):
        marked = settings_with([scan.NO_TREE_WRITE])
        for argv in (["--settings", marked, "--settings", marked], ["--settings", "{not json"], ["--settings"],
                     ["--settings", "/path/to/settings.json"], ["--settings=[]"]):
            with self.subTest(argv=argv):
                with self.assertRaises(fence.Refused):
                    self.fenced(argv)

    def test_mark_is_the_yaml_value_under_the_isolated_home(self):
        """YAML が読むだけの役に書く値（scan.NO_TREE_WRITE）は、起動が隔離した HOME の下で印になる"""
        child = isolate.isolate({}, hermetic.tmpdir(self))
        with mock.patch.dict(os.environ, {"HOME": child["HOME"]}):
            self.assertTrue(fence.marks(scan.NO_TREE_WRITE, child["ARCHON_HOME"]))
            self.assertFalse(fence.marks("~/../other", child["ARCHON_HOME"]))


FAKE_REAL = f"""#!{sys.executable}
import json, os, sys
with open(os.environ["FAKE_REAL_LOG"], "w", encoding="utf-8") as f:
    json.dump(sys.argv[1:], f)
with open(os.environ["FAKE_REAL_LOG"] + ".env", "w", encoding="utf-8") as f:
    json.dump({{k: v for k, v in os.environ.items() if k.startswith("GRAPHLOOPS_")}}, f)
with open(os.environ["FAKE_REAL_LOG"] + ".path", "w", encoding="utf-8") as f:
    f.write(os.environ.get("PATH", ""))
"""


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.tree = make_tree(self.tmp)
        self.real = self.tmp / "real-claude"
        self.real.write_text(FAKE_REAL, encoding="utf-8")
        self.real.chmod(0o755)
        self.log = self.tmp / "argv.json"
        self.records = self.tmp / "run-home" / launcher.FENCE_DIR / "launches.jsonl"

    def run_fence(self, *argv, path=None, records=None, heads=()):
        child = self.tree["child"]
        env = hermetic.child_env(HOME=child["HOME"], FAKE_REAL_LOG=str(self.log), **({"PATH": path} if path else {}))
        return subprocess.run([sys.executable, str(FENCE), "--real", str(self.real), "--archon-home", child["ARCHON_HOME"],
                               "--claude-config", child["CLAUDE_CONFIG_DIR"], "--own", self.tree["own"][0],
                               "--records", str(records or self.records), *(a for h in heads for a in ("--path-head", h)),
                               "--", *argv],
                              cwd=self.tree["linked"], env=env, capture_output=True, text=True, encoding="utf-8",
                              timeout=60)

    def test_marked_launch_reaches_claude_with_the_list(self):
        done = self.run_fence("-p", "x", "--settings", settings_with([scan.NO_TREE_WRITE]))
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(self.log.read_text(encoding="utf-8"))
        deny = json.loads(got[3])["sandbox"]["filesystem"]["denyWrite"]
        self.assertIn(str(self.tree["main"] / ".git"), deny)
        self.assertIn(str(self.tree["nested"]), deny)

    def test_marked_launch_is_recorded_with_its_cwd(self):
        """印の在る起動は、起こす前に起動の記録へ 1 行（時刻と cwd の実パス）を足す。受け付けはそれで柵が掛かったかを見る（T49）"""
        for _ in range(2):
            self.assertEqual(self.run_fence("--settings", settings_with([scan.NO_TREE_WRITE])).returncode, 0)
        rows = [json.loads(line) for line in self.records.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["cwd"] for r in rows], [os.path.realpath(self.tree["linked"])] * 2)
        self.assertTrue(all(datetime.datetime.fromisoformat(r["at"]).tzinfo for r in rows), rows)

    def test_every_launch_marks_claude_as_an_engine_child(self):
        """#505: 包みが起こす役の claude と、その子（対象のテスト）は GRAPHLOOPS_ENGINE_CHILD=1 を持つ（元 works の SKILL.md 96 行。
        対象の重い一式がこの名で AI の役からの起動を見分けて拒む）。印の有無に依らない"""
        for argv in (["-p", "x"], ["--settings", settings_with([scan.NO_TREE_WRITE])]):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_fence(*argv).returncode, 0)
                got = json.loads(pathlib.Path(f"{self.log}.env").read_text(encoding="utf-8"))
                self.assertEqual(got, {fence.ENGINE_CHILD_ENV: "1"})

    def test_path_heads_lead_the_path_of_claude_only(self):
        """役の claude の PATH の頭には --path-head の置き場（読むだけの gh の口）が来る。包みの外（script のノード）の PATH は変えない"""
        heads = [str(self.tmp / "read-only"), str(self.tmp / "second")]
        for argv in (["-p", "x"], ["--settings", settings_with([scan.NO_TREE_WRITE])]):
            with self.subTest(argv=argv):
                self.assertEqual(self.run_fence(*argv, path="/usr/bin:/bin", heads=heads).returncode, 0)
                path = pathlib.Path(f"{self.log}.path").read_text(encoding="utf-8").split(os.pathsep)
                self.assertEqual(path, [*heads, "/usr/bin", "/bin"])

    def test_unmarked_launch_reaches_claude_unchanged(self):
        argv = ["-p", "x", "--settings", json.dumps({"sandbox": {"enabled": True}})]
        done = self.run_fence(*argv)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(self.log.read_text(encoding="utf-8")), argv)
        self.assertFalse(self.records.exists(), "印の無い起動を記録した")

    def test_unwritable_record_stops_before_claude(self):
        """記録を書けなければ、柵が掛かった証が残らないので claude を起こさない"""
        blocker = self.tmp / "not-a-dir"
        blocker.write_text("", encoding="utf-8")
        done = self.run_fence("--settings", settings_with([scan.NO_TREE_WRITE]), records=blocker / "launches.jsonl")
        self.assertEqual(done.returncode, fence.REFUSED_EXIT, done.stderr)
        self.assertIn(str(blocker), done.stderr)
        self.assertFalse(self.log.exists(), "止まるはずが claude が起きた")

    def test_without_git_stops_before_claude(self):
        done = self.run_fence("--settings", settings_with([scan.NO_TREE_WRITE]), path=str(self.tmp / "no-tools"))
        self.assertEqual(done.returncode, fence.REFUSED_EXIT, done.stderr)
        self.assertTrue(done.stderr.startswith("works-factory fence: "), done.stderr)
        self.assertFalse(self.log.exists(), "止まるはずが claude が起きた")



class ReadmeTest(unittest.TestCase):
    def test_readme_names_the_engine_child_marker(self):
        """#526: 対象のリポジトリの書き手が頼れるよう、README.md が役の子に立つ印を名指す"""
        self.assertIn(f"`{fence.ENGINE_CHILD_ENV}=1`", (ROOT / "README.md").read_text(encoding="utf-8"))


class FencedSinceTest(unittest.TestCase):
    """受け付けが読む側（fence.fenced_since）: since より後に root の中を cwd にした印の在る起動が 1 行でも在れば空、無ければ訳"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.root = self.tmp / "work"
        (self.root / "sub").mkdir(parents=True)
        self.records = self.tmp / "launches.jsonl"
        self.since = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=datetime.timezone.utc)

    def write(self, *rows):
        self.records.write_text("".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows), encoding="utf-8")

    def row(self, minutes, cwd):
        return {"at": (self.since + datetime.timedelta(minutes=minutes)).isoformat(), "cwd": str(cwd)}

    def since_of(self, text=None):
        return fence.fenced_since(self.records, self.root, self.since.isoformat() if text is None else text)

    def test_launch_after_since_in_root_is_fenced(self):
        for cwd in (self.root, self.root / "sub"):
            with self.subTest(cwd=cwd):
                self.write("{broken", self.row(-5, self.root), self.row(1, cwd))
                self.assertEqual(self.since_of(), "")

    def test_missing_old_or_elsewhere_launches_are_not(self):
        self.assertIn(str(self.records), self.since_of())
        for name, rows in (("前の回", [self.row(-1, self.root)]), ("ほかの木", [self.row(1, self.tmp / "work2")]),
                           ("読めない行だけ", ["{broken", json.dumps({"at": "x", "cwd": str(self.root)})])):
            with self.subTest(name):
                self.write(*rows)
                self.assertNotEqual(self.since_of(), "")

    def test_unreadable_since_is_not_fenced(self):
        self.write(self.row(1, self.root))
        for text in ("", "not a time", "2026-10-13T12:00:00"):
            with self.subTest(since=text):
                self.assertNotEqual(self.since_of(text), "")

    def test_rows_written_by_the_fence_are_read_back(self):
        """書く側（fence.record）の行を読む側が読む。行の形を片方だけ変えると、宣言した run の CI の役は毎回諦める"""
        before = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        fence.record(str(self.records), str(self.root / "sub"))
        self.assertEqual(self.since_of(before.isoformat()), "")

    def test_only_an_absolute_declaration_is_readable(self):
        self.assertEqual(fence.bad_declaration(str(self.records)), "")
        self.assertIn(fence.RECORDS_ENV, fence.bad_declaration("launches.jsonl"))

    def test_declaration_name_is_shared_with_the_launcher(self):
        self.assertEqual(fence.RECORDS_ENV, launcher.FENCE_RECORDS_ENV)


NO_TOOLS = "sandbox が立たない（macOS の sandbox-exec か、Linux の bwrap と socat が要る）"
LAYERS = {sandbox_probe.START_FAILED: "start", sandbox_probe.BASH_FAILED: "Bash", sandbox_probe.GREP_EMPTY: "Grep",
          sandbox_probe.UNCONFINED: "unconfined", sandbox_probe.NO_TOOL_RESULT: "tool_result"}


def sandbox_refused(claude: str, platform: str = sys.platform) -> str:
    """本物の claude の sandbox の柵の試験を見送る訳（見送らないなら空）。道具が無い時（macOS は sandbox-exec、Linux は bwrap と
    socat）と、Linux で名前空間が立たず Bash が落ちた時（kernel の制限に依る台の問題）、Linux で claude が要求を送らず終わり、
    kernel の名前空間の制限の値が 1 の時（役の設定の failIfUnavailable が起動の時に拒む。層は start）は見送りの訳を返す。道具が在るのに
    ほかの層（start・Grep・unconfined・tool_result が返らない、macOS の Bash）が壊れている時は、層と要の行を添えた AssertionError で赤にする"""
    if platform == "darwin":
        if shutil.which("sandbox-exec") is None:
            return NO_TOOLS
    elif shutil.which("bwrap") is None or shutil.which("socat") is None:
        return NO_TOOLS
    with tempfile.TemporaryDirectory(prefix="works-fence-probe-") as tmp:
        code, clues = sandbox_probe.probe(claude, sandbox_probe.role_sandbox(), tmp, hermetic.child_env())
    if code == 0:
        return ""
    said = f"sandbox の {LAYERS.get(code, f'終わりの値 {code}')} の層が立たない: {' / '.join(clues)}"
    if platform != "darwin":
        if code == sandbox_probe.BASH_FAILED:
            return said
        limit = sandbox_probe.userns_limit()
        if code == sandbox_probe.START_FAILED and limit == "1":
            return f"{said}（kernel の名前空間の制限 {sandbox_probe.USERNS_LIMIT} = {limit}）"
    raise AssertionError(said)


class SharedProbeTest(unittest.TestCase):
    def setUp(self):
        which = mock.patch.object(shutil, "which", return_value="/usr/bin/tool")
        which.start()
        self.addCleanup(which.stop)

    def probe_says(self, code, *clues):
        patcher = mock.patch.object(sandbox_probe, "probe", return_value=(code, list(clues)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def limit_is(self, value):
        patcher = mock.patch.object(sandbox_probe, "userns_limit", return_value=value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fence_check_runs_the_shared_probe(self):
        seen = []

        class Reached(Exception):
            pass

        def spy(claude, settings, place, env):
            seen.append((claude, settings))
            raise Reached

        with mock.patch.object(sandbox_probe, "probe", spy), self.assertRaises(Reached):
            sandbox_refused("/path/claude")
        self.assertEqual(seen, [("/path/claude", sandbox_probe.role_sandbox())])

    def test_skip_reason_names_the_failed_layer(self):
        with self.subTest("tools missing"):
            with mock.patch.object(shutil, "which", return_value=None):
                for platform in ("darwin", "linux"):
                    self.assertEqual(sandbox_refused("claude", platform=platform), NO_TOOLS)
        self.probe_says(sandbox_probe.BASH_FAILED, "bwrap: No permissions to create new namespace")
        with self.subTest("linux bash"):
            why = sandbox_refused("claude", platform="linux")
            self.assertIn("Bash", why)
            self.assertIn("bwrap: No permissions to create new namespace", why)
        self.probe_says(sandbox_probe.START_FAILED, "config error")
        with self.subTest("linux start with the namespace limit at 1"):
            self.limit_is("1")
            why = sandbox_refused("claude", platform="linux")
            self.assertIn("start", why)
            self.assertIn("config error", why)
            self.assertIn(f"{sandbox_probe.USERNS_LIMIT} = 1", why)
        with self.subTest("passing probe"):
            self.probe_says(0)
            self.assertEqual(sandbox_refused("claude", platform="linux"), "")

    def test_broken_sandbox_with_tools_present_is_red(self):
        for name, platform, code, limit in (
                ("start without a limit", "linux", sandbox_probe.START_FAILED, None),
                ("start with the limit at 0", "linux", sandbox_probe.START_FAILED, "0"),
                ("start on macos even with 1", "darwin", sandbox_probe.START_FAILED, "1"),
                ("grep on linux", "linux", sandbox_probe.GREP_EMPTY, "1"),
                ("grep on macos", "darwin", sandbox_probe.GREP_EMPTY, None),
                ("unconfined on linux", "linux", sandbox_probe.UNCONFINED, "1"),
                ("unconfined on macos", "darwin", sandbox_probe.UNCONFINED, None),
                ("bash on macos", "darwin", sandbox_probe.BASH_FAILED, "1"),
                ("no tool_result on linux", "linux", sandbox_probe.NO_TOOL_RESULT, "1"),
                ("no tool_result on macos", "darwin", sandbox_probe.NO_TOOL_RESULT, None)):
            with self.subTest(name):
                self.probe_says(code, "the stderr line", "the key line")
                self.limit_is(limit)
                with self.assertRaises(AssertionError) as caught:
                    sandbox_refused("claude", platform=platform)
                self.assertIn(LAYERS[code], str(caught.exception))
                self.assertIn("the key line", str(caught.exception))


class RealClaudeTest(unittest.TestCase):
    """本物の claude の sandbox が、起動の殻の書いた包み（launcher.write_fence）の足した一覧への Bash の書き込みを止める
    （#305 の見直しの R2・#348）"""

    @classmethod
    def setUpClass(cls):
        cls.claude = shutil.which("claude")
        if cls.claude is None:
            raise unittest.SkipTest("本物の claude が無い")
        why = sandbox_refused(cls.claude)
        if why:
            raise unittest.SkipTest(why)

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.tree = make_tree(self.tmp)
        self.outside = self.tmp / "outside"
        self.outside.mkdir()
        self.cache = self.tmp / "cache" / "works-factory"
        self.cache.mkdir(parents=True)
        child = self.tree["child"]
        main = self.tree["main"]
        self.blocked = {
            "作業ツリー（cwd）": self.tree["linked"],
            "共通の .git": main / ".git",
            "共通の .git の worktrees": main / ".git" / "worktrees" / self.tree["linked"].name,
            "本体の作業ツリー": main,
            "置き場を替えた worktree": self.tree["nested"],
            "Archon の家": pathlib.Path(child["ARCHON_HOME"]),
            "Claude の設定": pathlib.Path(child["CLAUDE_CONFIG_DIR"]),
            "取り置いた Archon の源": self.cache,
            "テストのキャッシュの置き場（cwd の下）": self.tree["linked"] / ".pytest_cache",
        }
        self.blocked["テストのキャッシュの置き場（cwd の下）"].mkdir()
        self.settings = {"sandbox": sandbox_probe.role_sandbox()}

    def probe(self, launcher: list[str]) -> dict[str, str]:
        """launcher で claude を起こし、Bash で各置き場に書かせた結果（置き場 → WROTE か BLOCKED）"""
        places = [*self.blocked.values(), self.outside]
        wrote, blocked = sandbox_probe.WROTE, sandbox_probe.BLOCKED
        command = "; ".join(f"if (echo x > {shlex.quote(str(p / 'fence-probe'))}) 2>/dev/null; then echo {wrote} {i}; "
                            f"else echo {blocked} {i}; fi" for i, p in enumerate(places))
        child = self.tree["child"]
        env = hermetic.child_env(HOME=child["HOME"], CLAUDE_CONFIG_DIR=child["CLAUDE_CONFIG_DIR"])
        talk = sandbox_probe.converse(launcher, self.settings, ("Bash",), [("Bash", {"command": command, "description": "probe"})],
                                      self.tree["linked"], env)
        self.assertEqual(talk.returncode, 0, talk.error or talk.stdout + talk.stderr)
        text = "".join(sandbox_probe.text_of(r) for r in talk.results)
        said = {}
        for line in text.splitlines():
            verdict, _, index = line.partition(" ")
            if verdict in (wrote, blocked):
                said[index] = verdict
        self.assertEqual(len(said), len(places), text)
        return {str(p): said[str(i)] for i, p in enumerate(places)}

    def test_fenced_role_cannot_write_the_listed_places(self):
        home = self.tmp / "run-home"
        got = self.probe([launcher.write_fence(home, self.claude, self.tree["child"], self.cache, [])])
        for what, place in self.blocked.items():
            with self.subTest(what=what):
                self.assertEqual(got[str(place)], "BLOCKED")
        self.assertEqual(got[str(self.outside)], "WROTE", "柵の外まで書けない（試験の道具が書き込みを試していない）")
        rows = [json.loads(line) for line in launcher.fence_records(home).read_text(encoding="utf-8").splitlines()]
        self.assertIn(os.path.realpath(self.tree["linked"]), [r["cwd"] for r in rows])

    def test_without_the_fence_the_main_tree_is_writable(self):
        got = self.probe([self.claude])
        self.assertEqual(got[str(self.tree["main"])], "WROTE")


if __name__ == "__main__":
    unittest.main()
