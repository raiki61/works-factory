"""入口の殻 bin/works-factory（bin/_lib/launcher.py）の試験。

殻を子のプロセスとして走らせる。リポジトリの bin/・workflows/・pack.json を使い捨ての木に写し、その factory/pack.json は、
同じ木の取り置きの置き場に作った偽の Archon の源の commit を名指す（本物の源は取らない・網に出ない）。PATH には偽の bun・claude・gh・
security（と mise）と、python3・git だけを置く。偽の bun は受けた引数と環境を JSON に書き、試験がそれを照らす（トークンは在るかだけを見る。環境は名の一覧で照らし、落ちた時に値を
試験の出力に出さない）。
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.bin.test_toolset import make_user_config, write_fake_claude

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOKEN = "sk-ant-oat01-fake-for-launcher"
API_KEY = "sk-ant-api03-fake-for-launcher"
ENTRY = "packages/cli/src/cli.ts"
# 利用者の場から漏れると照らしが揺れる名（hermetic が外さない物）
USER_SPECIFIC = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "GH_CONFIG_DIR", "GH_TOKEN", "GITHUB_TOKEN",
                 "MISE_TRUSTED_CONFIG_PATHS")

FAKE_BUN = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_BUN_LOG"], "w", encoding="utf-8") as f:
    json.dump({"argv": sys.argv, "env": dict(os.environ)}, f)
"""
FAKE_GH = "#!/bin/sh\nexit 0\n"
# 名指した項目を、名指した HOME で引いた時だけトークンを返す（ほかは本物の security の「無い」と同じ 44）
FAKE_SECURITY = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_SECURITY_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "home": os.environ.get("HOME")}) + "\\n")
service = sys.argv[sys.argv.index("-s") + 1] if "-s" in sys.argv else None
if service and service == os.environ.get("FAKE_SECURITY_SERVICE") and os.environ.get("HOME") == os.environ.get("FAKE_SECURITY_HOME"):
    print(os.environ["FAKE_SECURITY_VALUE"])
    sys.exit(0)
sys.exit(44)
"""
FAKE_MISE = """#!/bin/sh
[ "$1 $2" = "trust --show" ] && echo "$FAKE_MISE_TRUSTED: trusted"
exit 0
"""


def put(path: pathlib.Path, body: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def short(path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:8]


class LauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="works-launcher-")
        cls.base = pathlib.Path(os.path.realpath(cls._tmp.name))
        cls.repo = cls.base / "repo"
        no_cache = shutil.ignore_patterns("__pycache__")
        shutil.copytree(ROOT / "bin", cls.repo / "bin", ignore=no_cache)
        shutil.copytree(ROOT / "workflows", cls.repo / "workflows", ignore=no_cache)
        shutil.copy(ROOT / "pack.json", cls.repo / "pack.json")
        cls.cache_home = cls.base / "cache"
        asf = json.loads((ROOT / "factory" / "pack.json").read_text(encoding="utf-8"))
        staging = cls.base / "archon-staging"
        put(staging / ENTRY, "// 偽の Archon の入口\n")
        put(staging / asf["source_directory"] / "archon-x.yaml", "name: archon-x\n")
        (staging / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        git(staging, "init", "-q")
        git(staging, "add", "-A")
        git(staging, "commit", "-q", "-m", "fake archon")
        commit = git(staging, "rev-parse", "HEAD")
        cls.source = cls.cache_home / "works-factory" / "archon" / commit
        cls.source.parent.mkdir(parents=True)
        staging.rename(cls.source)
        (cls.source / "node_modules").mkdir()
        asf.update(integration_revision_required=commit, repository=str(cls.source))
        (cls.repo / "factory").mkdir()
        (cls.repo / "factory" / "pack.json").write_text(json.dumps(asf), encoding="utf-8")
        cls.tools = cls.base / "tools"
        cls.tools.mkdir()
        for name, real in (("python3", sys.executable), ("git", shutil.which("git"))):
            (cls.tools / name).symlink_to(real)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.home = self.tmp / "user-home"
        make_user_config(self.home / ".claude", only=("superpowers", "pr-review-toolkit"))
        self.fake = self.tmp / "fake-bin"
        self.bun = put(self.fake / "bun", FAKE_BUN)
        write_fake_claude(self.fake)
        self.gh = put(self.fake / "gh", FAKE_GH)
        put(self.fake / "security", FAKE_SECURITY)
        self.target = self.tmp / "target"
        (self.target / "sub").mkdir(parents=True)
        git(self.target, "init", "-q")
        self.bun_log = self.tmp / "bun.json"
        self.security_log = self.tmp / "security.jsonl"
        self.env = hermetic.child_env(
            HOME=str(self.home), PATH=f"{self.fake}{os.pathsep}{self.tools}", XDG_CACHE_HOME=str(self.cache_home),
            FAKE_BUN_LOG=str(self.bun_log), FAKE_CLAUDE_LOG=str(self.tmp / "claude.jsonl"),
            FAKE_SECURITY_LOG=str(self.security_log), ANTHROPIC_API_KEY=API_KEY)
        for name in USER_SPECIFIC:
            self.env.pop(name, None)

    def launch(self, *args, cwd=None, **env):
        merged = {k: v for k, v in {**self.env, **env}.items() if v is not None}
        if self.bun_log.exists():
            self.bun_log.unlink()
        return subprocess.run([sys.executable, str(self.repo / "bin" / "works-factory"), *args], env=merged,
                              cwd=cwd or self.target, capture_output=True, text=True, encoding="utf-8", timeout=120)

    def reached(self, done) -> dict:
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.bun_log.exists(), f"bun が起きていない: {done.stderr}")
        return json.loads(self.bun_log.read_text(encoding="utf-8"))

    def stopped(self, done) -> str:
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertFalse(self.bun_log.exists(), "止まるはずが bun が起きた")
        return done.stderr

    def default_home(self, target) -> pathlib.Path:
        return self.home / ".local" / "state" / "works-factory" / "targets" / short(target)

    def test_run_gets_cwd_and_workflow_source_before_user_args(self):
        got = self.reached(self.launch("workflow", "run", "works-factory-line", "--input", "request=x", cwd=self.target / "sub"))
        argv = got["argv"]
        self.assertEqual(argv[0], str(self.bun))
        self.assertEqual(argv[1], str(self.source / ENTRY))
        self.assertEqual(argv[2:6], ["workflow", "run", "--cwd", str(self.target)])
        self.assertEqual(argv[6], "--workflow-source")
        self.assertEqual((pathlib.Path(argv[7]) / ".archon" / "workflows" / "works-factory").resolve(), self.repo / "workflows")
        self.assertEqual(argv[8:], ["works-factory-line", "--input", "request=x"])
        with self.subTest("利用者の --cwd は対象に使い、二重に足さない"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--cwd", str(self.target / "sub"),
                                            "--input", "request=x", cwd=self.tmp))["argv"]
            self.assertEqual(argv.count("--cwd"), 1)
            self.assertEqual(argv[2:6], ["workflow", "run", "--cwd", str(self.target)])
            self.assertEqual(argv[8:], ["works-factory-line", "--input", "request=x"])

    def test_run_without_workflow_name_stops(self):
        err = self.stopped(self.launch("workflow", "run", "--input", "request=x"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_resume_and_approve_pass_through_unchanged(self):
        for args in (["workflow", "approve", "run-1", "--cwd", str(self.target)],
                     ["workflow", "run", "works-factory-line", "--resume", "--cwd", str(self.target)],
                     ["workflow", "status"]):
            with self.subTest(args=args):
                argv = self.reached(self.launch(*args))["argv"]
                self.assertEqual(argv[2:], args)

    def test_user_workflow_source_is_refused(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--workflow-source", str(self.tmp)))
        self.assertIn("--workflow-source", err)

    def test_home_is_stable_per_target(self):
        def home_of(**kw):
            return self.reached(self.launch("workflow", "status", **kw))["env"]["HOME"]

        first = home_of()
        self.assertEqual(first, str(self.default_home(self.target) / "home"))
        self.assertEqual(home_of(), first)
        self.assertEqual(home_of(cwd=self.target / "sub"), first)
        other = self.tmp / "other"
        other.mkdir()
        self.assertNotEqual(self.reached(self.launch("workflow", "status", "--cwd", str(other)))["env"]["HOME"], first)
        chosen = self.tmp / "chosen-home"
        self.assertEqual(home_of(WORKS_FACTORY_HOME=str(chosen)), str(chosen / "home"))
        err = self.stopped(self.launch("workflow", "status", WORKS_FACTORY_HOME="relative/home"))
        self.assertIn("WORKS_FACTORY_HOME", err)

    def test_child_is_isolated(self):
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        home = self.default_home(self.target)
        for name in ("HOME", "ARCHON_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
                     "XDG_STATE_HOME"):
            with self.subTest(name=name):
                self.assertTrue(pathlib.Path(env[name]).is_relative_to(home), env[name])
        self.assertNotIn(str(self.home), [env[n] for n in ("HOME", "CLAUDE_CONFIG_DIR", "XDG_CACHE_HOME")])
        self.assertEqual(env["ARCHON_TELEMETRY_DISABLED"], "1")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["WORKS_FACTORY_ROOT"], str(self.repo))

    def test_user_values_are_taken_before_isolation(self):
        """利用者の HOME と生の CLAUDE_CONFIG_DIR（相対なら打った場所から絶対に直した物）で認証を引き、埋めた値でプラグインを探す"""
        work = self.tmp / "work"
        config = work / "my-claude"
        make_user_config(config, only=("superpowers", "pr-review-toolkit"))
        shutil.rmtree(self.home / ".claude")
        (config / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"accessToken": TOKEN}}), encoding="utf-8")
        env = self.reached(self.launch(
            "workflow", "run", "works-factory-line", "--cwd", str(self.target), cwd=work, ANTHROPIC_API_KEY=None,
            CLAUDE_CONFIG_DIR="my-claude", FAKE_SECURITY_HOME=str(self.home), FAKE_SECURITY_VALUE=TOKEN,
            FAKE_SECURITY_SERVICE="Claude Code-credentials-" + short(config)))["env"]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))
        self.assertTrue(pathlib.Path(env["CLAUDE_CONFIG_DIR"]).is_relative_to(self.default_home(self.target)))
        self.assertTrue((pathlib.Path(env["CLAUDE_CONFIG_DIR"]) / ".works-toolset.json").is_file())

    def test_gh_shim_heads_child_path(self):
        env = self.reached(self.launch("workflow", "status"))["env"]
        head = pathlib.Path(env["PATH"].split(os.pathsep)[0])
        self.assertTrue(head.is_relative_to(self.default_home(self.target)), head)
        shim = (head / "gh").read_text(encoding="utf-8")
        self.assertIn(str(self.gh), shim)
        self.assertIn(str(self.home), shim)
        self.assertNotIn("GH_TOKEN", list(env))

    def test_toolset_and_auth_check_only_for_workflow_executing_commands(self):
        def config_of(env):
            return pathlib.Path(env["CLAUDE_CONFIG_DIR"])

        done = self.launch("workflow", "status")
        env = self.reached(done)["env"]
        self.assertNotIn("認証は", done.stderr)
        self.assertFalse((config_of(env) / ".works-toolset.json").exists())
        claude_log = self.tmp / "claude.jsonl"
        done = self.launch("validate", "workflows")
        env = self.reached(done)["env"]
        self.assertNotIn("認証は", done.stderr)
        self.assertTrue((config_of(env) / ".works-toolset.json").is_file())
        self.assertFalse(claude_log.exists(), "validate で claude の plugin の CLI を呼んだ")
        done = self.launch("workflow", "run", "works-factory-line")
        self.reached(done)
        self.assertIn("認証は ANTHROPIC_API_KEY", done.stderr)
        self.assertTrue(claude_log.exists(), "run で claude の plugin の CLI を呼んでいない")

    def test_mise_trust_only_when_user_trusts_target(self):
        put(self.fake / "mise", FAKE_MISE)
        workspaces = os.path.realpath(self.default_home(self.target) / "archon-home" / "workspaces")
        env = self.reached(self.launch("workflow", "status", FAKE_MISE_TRUSTED=str(self.target),
                                       MISE_TRUSTED_CONFIG_PATHS="/before"))["env"]
        self.assertEqual(env["MISE_TRUSTED_CONFIG_PATHS"], f"/before:{workspaces}")
        env = self.reached(self.launch("workflow", "status", FAKE_MISE_TRUSTED=str(self.tmp)))["env"]
        self.assertNotIn("MISE_TRUSTED_CONFIG_PATHS", list(env))
        env = self.reached(self.launch("workflow", "status", FAKE_MISE_TRUSTED=str(self.target),
                                       WORKS_FACTORY_NO_AUTH="1"))["env"]
        self.assertNotIn("MISE_TRUSTED_CONFIG_PATHS", list(env))

    def test_toolset_failure_stops_before_archon(self):
        shutil.rmtree(self.home / ".claude")
        make_user_config(self.home / ".claude", only=("superpowers",))
        err = self.stopped(self.launch("workflow", "run", "works-factory-line"))
        self.assertIn("pr-review-toolkit", err)

    def test_missing_auth_stops_before_archon(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None))
        self.assertIn("認証が無い", err)

    @unittest.skipIf(sys.platform == "darwin", "macOS 以外の道: macOS は Claude Code のログインを keychain から読む")
    def test_claude_login_only_user_reaches_archon(self):
        """keychain の項目を名指さず、<CLAUDE_CONFIG_DIR>/.credentials.json にだけログインが在る利用者（E14）"""
        (self.home / ".claude" / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"accessToken": TOKEN, "refreshToken": "r"}}), encoding="utf-8")
        env = self.reached(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None))["env"]
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))
        self.assertTrue(pathlib.Path(env["CLAUDE_CONFIG_DIR"]).is_relative_to(self.default_home(self.target)))

    def test_api_key_user_reaches_archon(self):
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        self.assertIn("ANTHROPIC_API_KEY", list(env))
        self.assertFalse(self.security_log.exists(), "API キーの利用者で keychain を読んだ")

    def test_bun_missing_stops_with_one_line(self):
        self.bun.unlink()
        err = self.stopped(self.launch("workflow", "status"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("bun が無い", err)


if __name__ == "__main__":
    unittest.main()
