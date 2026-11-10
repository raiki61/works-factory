"""sandbox の掛かった役の claude の包み（pack の .shared/fence.py。埋め P5）を確かめる。起動ごとの cache の足し込みの試験もここに収める。

一覧の組み方・argv の書き換え・main は使い捨ての git の木と偽の claude で確かめる。RealClaudeTest は本物の claude を偽の API で起こし、
sandbox が包みの足した一覧への書き込みを本当に止めることを確かめる。起こす前に、共有の部品 tests/bin/sandbox_probe.py で sandbox の
Bash と Grep が立つかを 1 回確かめる（sandbox_refused）。本物の claude か sandbox の道具が無い所と、Linux で名前空間が立たない所は名前つきで
見送り、ほかの層の壊れは赤にする。
"""
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

from bin._lib import isolate, launcher, place
from lib import writelog
from tests.bin import hermetic, sandbox_probe
from tests.bin.gitkit import git
from tests.archon import WORKFLOWS
from tests.layers import scan

FENCE = WORKFLOWS / ".shared" / "fence.py"


fence = place.shared("fence")   # 起動の殻と同じ読み（.shared は import の名にならず、__pycache__ を作らない）


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


class ConnectionTest(unittest.TestCase):
    """殻で組んだ値だけを最終 hop に適用。秘密を inline に置かず、柵と工場の設定を落とさない。"""

    def profile(self):
        return {"settings": {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"}},
                "env": {"ANTHROPIC_API_KEY": "dummy-secret", "ANTHROPIC_BASE_URL": "https://dummy.invalid"},
                "drop": ["ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"]}

    def test_single_settings_preserves_sandbox_plugins_hooks_permissions(self):
        original = {"sandbox": {"enabled": True, "filesystem": {"denyWrite": ["/factory/archon"]}},
                    "enabledPlugins": {"factory-dummy": False}, "hooks": {"Stop": []},
                    "permissions": {"deny": ["Bash(unsafe)"]}, "env": {"FACTORY_DUMMY": "1"}}
        for argv in (["--settings", json.dumps(original)], ["--settings=" + json.dumps(original)]):
            out = fence.fenced_argv(argv, "/factory/archon", lambda: ["/protected"], self.profile()["settings"])
            raw = out[1] if out[0] == "--settings" else out[0].split("=", 1)[1]
            got = json.loads(raw)
            self.assertEqual(sum(x == "--settings" or x.startswith("--settings=") for x in out), 1)
            for name in ("enabledPlugins", "hooks", "permissions"):
                self.assertEqual(got[name], original[name])
            self.assertEqual(got["sandbox"]["filesystem"]["denyWrite"], ["/factory/archon", "/protected"])
            self.assertNotIn("dummy-secret", raw)
            self.assertEqual(got["env"], {"FACTORY_DUMMY": "1", "ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"})

    def test_final_environment_drops_parent_credentials_but_not_factory_directories(self):
        env = {fence.PROFILE_ENV: json.dumps(self.profile()), "HOME": "/factory/home",
               "CLAUDE_CONFIG_DIR": "/factory/config", "ARCHON_HOME": "/factory/archon",
               "XDG_CONFIG_HOME": "/factory/xdg", "ANTHROPIC_AUTH_TOKEN": "dummy-parent",
               "CLAUDE_CODE_OAUTH_TOKEN": "dummy-oauth"}
        p = fence.connection(env)
        fence.connection_env(env, p)
        self.assertNotIn(fence.PROFILE_ENV, set(env))
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", set(env))
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", set(env))
        self.assertEqual(env["ANTHROPIC_API_KEY"], "dummy-secret")
        for name in ("HOME", "CLAUDE_CONFIG_DIR", "ARCHON_HOME", "XDG_CONFIG_HOME"):
            self.assertTrue(env[name].startswith("/factory/"))

    def test_bad_contract_does_not_echo_secret_or_restore_user_directories(self):
        for body in ("dummy-secret", {"settings": {"hooks": {}}, "env": {}, "drop": []},
                     {"settings": {}, "env": {"HOME": "/dummy-secret"}, "drop": []},
                     {"settings": {}, "env": {}, "drop": ["XDG_CACHE_HOME"]}):
            with self.assertRaises(fence.Refused) as error:
                fence.connection({fence.PROFILE_ENV: json.dumps(body)})
            self.assertNotIn("dummy-secret", str(error.exception))

    def test_aws_credential_export_is_composed_into_the_single_settings(self):
        """殻の settings の awsCredentialExport（空白を含むパスを shlex でくくった字）は、既存の 1 個の --settings（無ければ足した 1 個）に
        重なる。sandbox・hooks・権限は保つ。connection は 1 語の絶対パスにならない値を Refused で断る"""
        self.assertEqual(fence.PROFILE_SETTINGS, ("env", "awsCredentialExport"))   # 契約が許す鍵（toolset の SETTINGS_KEYS とは別）
        command = shlex.quote("/factory home/claude-fence/abc/aws-credential-export")
        extra = {"awsCredentialExport": command}
        original = {"sandbox": {"enabled": True, "filesystem": {"denyWrite": ["/factory/archon"]}},
                    "enabledPlugins": {"factory-dummy": False}, "hooks": {"Stop": []}, "permissions": {"deny": ["Bash(unsafe)"]}}
        for argv in (["--settings", json.dumps(original)], ["--settings=" + json.dumps(original)]):
            out = fence.fenced_argv(argv, "/factory/archon", lambda: ["/protected"], extra)
            raw = out[1] if out[0] == "--settings" else out[0].split("=", 1)[1]
            got = json.loads(raw)
            self.assertEqual(sum(x == "--settings" or x.startswith("--settings=") for x in out), 1)
            self.assertEqual(got["awsCredentialExport"], command)
            self.assertEqual(shlex.split(got["awsCredentialExport"]), ["/factory home/claude-fence/abc/aws-credential-export"])
            self.assertEqual(got["sandbox"]["filesystem"]["denyWrite"], ["/factory/archon", "/protected"])
            for name in ("enabledPlugins", "hooks", "permissions"):
                self.assertEqual(got[name], original[name])
        both = fence.fenced_argv(["--settings", json.dumps({"env": {"KEEP": "1"}})], "/factory/archon", lambda: [],
                                 {**extra, "env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"}})
        self.assertEqual(json.loads(both[1]), {"env": {"KEEP": "1", "ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"},
                                               "awsCredentialExport": command})
        for argv in ([], ["--version"]):   # --settings が無い時は、1 個を足す
            out = fence.fenced_argv(argv, "/factory", lambda: self.fail("must not compute protective paths"), extra)
            self.assertEqual(out, [*argv, "--settings", json.dumps(extra)])
        self.assertEqual(fence.fenced_argv(["--version"], "/factory", lambda: [], {"env": {}}), ["--version"])
        profile = {"settings": extra, "env": {}, "drop": []}
        self.assertEqual(fence.connection({fence.PROFILE_ENV: json.dumps(profile)}), profile)
        plain = {"settings": {"awsCredentialExport": shlex.quote("/factory/plain")}, "env": {}, "drop": []}
        self.assertEqual(fence.connection({fence.PROFILE_ENV: json.dumps(plain)}), plain)
        for bad in ("relative/export", "/factory home/export", "'/factory'", "/a b' c", "", 3, ["/x"], "/x; rm -rf /",
                    shlex.quote("/x") + " --flag"):
            with self.subTest(bad=bad):
                with self.assertRaises(fence.Refused) as error:
                    fence.connection({fence.PROFILE_ENV: json.dumps({"settings": {"awsCredentialExport": bad}, "env": {}, "drop": []})})
                self.assertNotIn("rm -rf", str(error.exception))

    def test_unmarked_and_missing_settings_still_compose(self):
        for argv in (["--version"], ["--settings", "{}"]):
            out = fence.fenced_argv(argv, "/factory", lambda: self.fail("must not compute protective paths"),
                                    self.profile()["settings"])
            raw = out[out.index("--settings") + 1]
            self.assertEqual(json.loads(raw), self.profile()["settings"])


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

    def fenced(self, argv, cache=None):
        with mock.patch.dict(os.environ, {"HOME": self.HOME}):
            return fence.fenced_argv(argv, self.ARCHON, lambda: self.PATHS, **({"cache": cache} if cache else {}))

    def cached(self, argv, folder="/c/launch-x"):
        """cache の口（呼ばれた回数を数える）を渡して組んだ argv の --settings の JSON と、口が呼ばれた回数"""
        calls = []

        def cache():
            calls.append(folder)
            return folder

        got = self.fenced(argv, cache)
        at = next(i for i, a in enumerate(got) if a == "--settings" or a.startswith("--settings="))
        raw = got[at].removeprefix("--settings=") if got[at] != "--settings" else got[at + 1]
        return json.loads(raw), len(calls)

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
        """sandbox の無い起動は argv が同一物のまま返り、cache の口も呼ばれない。sandbox が有効な起動は、印が無くても allowWrite に
        口のフォルダが足される以外は同じで、印の denyWrite の足し込みは起きない"""
        writer = {"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}}
        denied = json.loads(settings_with(["~/../other"]))
        elsewhere = json.loads(settings_with(["/elsewhere"]))
        for argv in (["--version"], ["-p", "x", "--settings", json.dumps({"permissions": {"deny": ["Bash(x)"]}})]):
            with self.subTest(argv=argv):
                calls = []
                self.assertIs(self.fenced(argv, lambda: calls.append(1) or "/c/launch-x"), argv)
                self.assertEqual(calls, [])
        want_writer = {"sandbox": {**writer["sandbox"], "filesystem": {"allowWrite": ["/c/launch-x"]}}}
        want_denied = json.loads(settings_with(["~/../other"]))
        want_denied["sandbox"]["filesystem"]["allowWrite"].append("/c/launch-x")
        want_elsewhere = json.loads(settings_with(["/elsewhere"]))
        want_elsewhere["sandbox"]["filesystem"]["allowWrite"].append("/c/launch-x")
        for argv, want in ((["-p", "x", "--settings", json.dumps(writer)], want_writer),
                           (["-p", "x", "--settings", json.dumps(denied)], want_denied),
                           (["--settings=" + json.dumps(elsewhere)], want_elsewhere)):
            with self.subTest(argv=argv):
                got, called = self.cached(argv)
                self.assertEqual(got, want)
                self.assertEqual(called, 1)

    def test_sandboxed_launch_gets_its_own_writable_cache(self):
        """sandbox が有効な --settings は、印の無い書き手の形・印の在る形・allowWrite が ['/'] の形・既存の allowWrite を持つ形のどれも、
        cache の口が返したフォルダが allowWrite の後ろに 1 つ足される（置き換えない）。denyWrite・印・ほかの鍵は保たれる。口は 1 起動に 1 回"""
        writer = {"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}, "permissions": {"deny": ["Bash(x)"]}}
        with self.subTest("印の無い書き手の形は filesystem ごと作る"):
            got, called = self.cached(["-p", "x", "--settings", json.dumps(writer)])
            self.assertEqual(got["sandbox"], {"enabled": True, "allowUnsandboxedCommands": False,
                                              "filesystem": {"allowWrite": ["/c/launch-x"]}})
            self.assertEqual(got["permissions"], writer["permissions"])
            self.assertEqual(called, 1)
        with self.subTest("印の在る形は一覧の足し込みと両立する"):
            got, called = self.cached(["--settings", settings_with(["/w", scan.NO_TREE_WRITE])])
            fs = got["sandbox"]["filesystem"]
            self.assertEqual(fs["denyWrite"], ["/w", scan.NO_TREE_WRITE, "/w/.git"])
            self.assertEqual(fs["allowWrite"], ["/", "/c/launch-x"])
            self.assertEqual(called, 1)
        with self.subTest("既存の allowWrite の値は残す"):
            kept = {"sandbox": {"enabled": True, "filesystem": {"allowWrite": ["/keep"], "denyRead": ["/r"]}}}
            got, called = self.cached(["--settings", json.dumps(kept)])
            self.assertEqual(got["sandbox"]["filesystem"], {"allowWrite": ["/keep", "/c/launch-x"], "denyRead": ["/r"]})
        with self.subTest("allowWrite が list でなければ決められない"):
            for bad in ("/", {"a": 1}, None):
                with self.assertRaises(fence.Refused):
                    self.cached(["--settings", json.dumps({"sandbox": {"enabled": True, "filesystem": {"allowWrite": bad}}})])
        with self.subTest("sandbox の無い起動では口が呼ばれず argv がそのまま返る"):
            for argv in (["--version"], ["--settings", "{}"], ["--settings", json.dumps({"sandbox": {"enabled": False}})],
                         ["--settings", json.dumps({"sandbox": {"filesystem": {"allowWrite": ["/"]}}})]):
                calls = []
                self.assertIs(self.fenced(argv, lambda: calls.append(1) or "/c/launch-x"), argv)
                self.assertEqual(calls, [], argv)

    def test_cache_inside_a_denied_place_is_refused(self):
        """cache の口が返したフォルダが、組み上がった denyWrite のどれか（~ を解いた実パス）の下なら Refused で止める（denyWrite は
        allowWrite に勝つので書けない）。名の前方が同じだけの兄弟は止めない"""
        for name, settings, folder in (
                ("印の在る起動で一覧に足された置き場の下", settings_with([scan.NO_TREE_WRITE]), "/w/.git/cache"),
                ("印の在る起動で一覧の置き場そのもの", settings_with([scan.NO_TREE_WRITE]), "/w"),
                ("印の無い起動の denyWrite の下", settings_with(["/denied"]), "/denied/sub/cache"),
                ("~ を解いた denyWrite の下", settings_with(["~/blocked"]), f"{self.HOME}/blocked/c")):
            with self.subTest(name):
                with self.assertRaises(fence.Refused):
                    self.cached(["--settings", settings], folder)
        for settings, folder in ((settings_with(["/denied"]), "/denied-sibling/cache"),
                                 (settings_with([scan.NO_TREE_WRITE]), "/wx/cache")):
            with self.subTest(sibling=folder):
                got, _ = self.cached(["--settings", settings], folder)
                self.assertEqual(got["sandbox"]["filesystem"]["allowWrite"], ["/", folder])

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
with open(os.environ["FAKE_REAL_LOG"] + ".cache", "w", encoding="utf-8") as f:
    json.dump(os.environ.get("XDG_CACHE_HOME"), f)
"""


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.tree = make_tree(self.tmp)
        self.real = self.tmp / "real-claude"
        self.real.write_text(FAKE_REAL, encoding="utf-8")
        self.real.chmod(0o755)
        self.log = self.tmp / "argv.json"

    def run_fence(self, *argv, path=None, heads=(), role_root=None, xdg=None):
        child = self.tree["child"]
        env = hermetic.child_env(HOME=child["HOME"], FAKE_REAL_LOG=str(self.log), **({"PATH": path} if path else {}),
                                 **({"XDG_CACHE_HOME": xdg} if xdg else {}))
        return subprocess.run([sys.executable, str(FENCE), "--real", str(self.real), "--archon-home", child["ARCHON_HOME"],
                               "--claude-config", child["CLAUDE_CONFIG_DIR"], "--own", self.tree["own"][0],
                               *(["--role-cache", str(role_root)] if role_root else []),
                               *(a for h in heads for a in ("--path-head", h)),
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
        """印の無い sandbox の起動は、allowWrite に起動ごとのフォルダが足される以外は渡した argv のまま届く"""
        settings = {"sandbox": {"enabled": True}}
        done = self.run_fence("-p", "x", "--settings", json.dumps(settings), role_root=self.tmp / "role-cache")
        self.assertEqual(done.returncode, 0, done.stderr)
        got = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual(got[:3], ["-p", "x", "--settings"])
        folder = json.loads(pathlib.Path(f"{self.log}.cache").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(got[3]), {"sandbox": {"enabled": True, "filesystem": {"allowWrite": [folder]}}})

    def test_sandboxed_launch_reaches_claude_with_its_own_cache(self):
        """--role-cache の根（symlink を通した根も含む）の下の、作業の場ごとの置き場（控え cwd つき）の中の空のフォルダの実パスが、偽の
        claude が受けた XDG_CACHE_HOME で、--settings の allowWrite の最後の項目と等しい。起動ごとに別のフォルダ。sandbox の無い起動は渡した
        XDG_CACHE_HOME のまま"""
        real_root = self.tmp / "real-role-cache"
        real_root.mkdir()
        link = self.tmp / "link-role-cache"
        link.symlink_to(real_root)
        settings = json.dumps({"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}})
        seen = []
        for _ in range(2):
            done = self.run_fence("-p", "x", "--settings", settings, role_root=link, xdg="/shell/xdg-cache")
            self.assertEqual(done.returncode, 0, done.stderr)
            got = json.loads(self.log.read_text(encoding="utf-8"))
            folder = json.loads(pathlib.Path(f"{self.log}.cache").read_text(encoding="utf-8"))
            allow = json.loads(got[got.index("--settings") + 1])["sandbox"]["filesystem"]["allowWrite"]
            self.assertEqual(allow[-1], folder)
            self.assertEqual(folder, os.path.realpath(folder))
            self.assertTrue(pathlib.Path(folder).is_relative_to(real_root.resolve()), folder)
            self.assertEqual(os.listdir(folder), [])
            place = pathlib.Path(folder).parent
            self.assertEqual(place.parent, real_root.resolve())
            self.assertEqual((place / writelog.WHERE).read_text(encoding="utf-8"), os.path.realpath(self.tree["linked"]))
            seen.append(folder)
        self.assertEqual(len(set(seen)), 2, "起動ごとに別のフォルダになっていない")
        with self.subTest("sandbox の無い起動"):
            done = self.run_fence("-p", "x", role_root=link, xdg="/shell/xdg-cache")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(self.log.read_text(encoding="utf-8")), ["-p", "x"])
            self.assertEqual(json.loads(pathlib.Path(f"{self.log}.cache").read_text(encoding="utf-8")), "/shell/xdg-cache")
            self.assertEqual(set(os.listdir(pathlib.Path(seen[0]).parent)), {writelog.WHERE, *map(os.path.basename, seen)},
                             "sandbox の無い起動がフォルダを足した")

    def test_without_git_stops_before_claude(self):
        done = self.run_fence("--settings", settings_with([scan.NO_TREE_WRITE]), path=str(self.tmp / "no-tools"))
        self.assertEqual(done.returncode, fence.REFUSED_EXIT, done.stderr)
        self.assertTrue(done.stderr.startswith("works-factory fence: "), done.stderr)
        self.assertFalse(self.log.exists(), "止まるはずが claude が起きた")


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
        self.keep = self.tmp / "state" / "works-factory" / "suites"
        self.keep.mkdir(parents=True)
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
            "TDD の実行器の取り置き": self.keep,
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
        got = self.probe([launcher.write_fence(home, self.claude, self.tree["child"], self.cache, self.keep, [])])
        for what, place in self.blocked.items():
            with self.subTest(what=what):
                self.assertEqual(got[str(place)], "BLOCKED")
        self.assertEqual(got[str(self.outside)], "WROTE", "柵の外まで書けない（試験の道具が書き込みを試していない）")

    def test_fenced_role_writes_its_own_cache_but_not_the_run_cache(self):
        """書き手の形の sandbox（enabled・allowUnsandboxedCommands: false だけ）の役の Bash は、包み越しに起きると $XDG_CACHE_HOME の下に
        書けて、run の置き場の xdg-cache には書けない"""
        home = self.tmp / "run-home"
        child = self.tree["child"]
        run_cache = pathlib.Path(child["XDG_CACHE_HOME"])
        wrote, blocked = sandbox_probe.WROTE, sandbox_probe.BLOCKED
        targets = ['"$XDG_CACHE_HOME/fence-probe"', shlex.quote(str(run_cache / "fence-probe"))]
        command = "; ".join(f"if (echo x > {t}) 2>/dev/null; then echo {wrote} {i}; else echo {blocked} {i}; fi"
                            for i, t in enumerate(targets))
        env = hermetic.child_env(HOME=child["HOME"], CLAUDE_CONFIG_DIR=child["CLAUDE_CONFIG_DIR"],
                                 XDG_CACHE_HOME=child["XDG_CACHE_HOME"])
        shell = launcher.write_fence(home, self.claude, child, self.cache, self.keep, [])
        talk = sandbox_probe.converse([shell], {"sandbox": {"enabled": True, "allowUnsandboxedCommands": False}}, ("Bash",),
                                      [("Bash", {"command": command, "description": "probe"})], self.tree["linked"], env)
        self.assertEqual(talk.returncode, 0, talk.error or talk.stdout + talk.stderr)
        text = "".join(sandbox_probe.text_of(r) for r in talk.results)
        said = {}
        for line in text.splitlines():
            verdict, _, index = line.partition(" ")
            if verdict in (wrote, blocked):
                said[index] = verdict
        self.assertEqual(said, {"0": wrote, "1": blocked}, text)

    def test_without_the_fence_the_main_tree_is_writable(self):
        got = self.probe([self.claude])
        self.assertEqual(got[str(self.tree["main"])], "WROTE")


if __name__ == "__main__":
    unittest.main()
