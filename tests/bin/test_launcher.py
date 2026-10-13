"""入口の殻 bin/works-factory（bin/_lib/launcher.py）の試験。

殻を子のプロセスとして、tests/bin/fakelaunch.py の使い捨ての木（偽の Archon の源）で走らせる。PATH には偽の bun・claude・gh・
security（と mise）と、python3・git だけを置く。偽の bun は受けた引数と環境を JSON に書き、試験がそれを照らす（トークンは在るかだけを見る。環境は名の一覧で照らし、落ちた時に値を
試験の出力に出さない）。
"""
import hashlib
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from bin._lib import launcher, place
from lib import answer, reads, writelog
from tests.bin import fakelaunch, hermetic
from tests.bin.fakelaunch import ENTRY, FAKE_BUN, put
from tests.bin.gitkit import git
from tests.bin.test_toolset import make_user_config, write_fake_claude

TOKEN = "sk-ant-oat01-fake-for-launcher"
API_KEY = "sk-ant-api03-fake-for-launcher"
GH_FAKE = "ghp_fake-for-launcher"
GITHUB_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
# 利用者の場から漏れると照らしが揺れる名（hermetic が外さない物）
USER_SPECIFIC = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "GH_CONFIG_DIR", *GITHUB_TOKENS,
                 "MISE_TRUSTED_CONFIG_PATHS")

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
# 本物の mise と同じく、HOME の下のパスは ~/… と出す
FAKE_MISE = """#!/bin/sh
case "$FAKE_MISE_TRUSTED" in
  "$HOME"/*) shown="~${FAKE_MISE_TRUSTED#"$HOME"}" ;;
  *) shown="$FAKE_MISE_TRUSTED" ;;
esac
[ "$1 $2" = "trust --show" ] && echo "$shown: trusted"
exit 0
"""


def short(path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:8]


class LauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if launcher.sandbox_writable(tempfile.gettempdir()):
            raise unittest.SkipTest("一時の置き場が /tmp/claude-* の下（Claude の sandbox の中）で、ここの起動は殻が全部拒む。"
                                    "CI か、TMPDIR をほかへ向けて走らせる")
        cls._tmp = tempfile.TemporaryDirectory(prefix="works-launcher-")
        tree = fakelaunch.build(pathlib.Path(os.path.realpath(cls._tmp.name)))
        cls.repo, cls.cache_home, cls.source, cls.tools = tree.repo, tree.cache_home, tree.source, tree.tools

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
        self.assertEqual(argv[1], f"--config={self.source / 'bunfig.toml'}")
        self.assertEqual(argv[2], str(self.source / ENTRY))
        self.assertEqual(argv[3:7], ["workflow", "run", "--cwd", str(self.target)])
        self.assertEqual(argv[7], "--workflow-source")
        self.assertEqual((pathlib.Path(argv[8]) / ".archon" / "workflows" / "works-factory").resolve(), self.repo / "workflows")
        self.assertEqual(argv[9:], ["works-factory-line", "--input", "request=x"])
        with self.subTest("利用者の --cwd は対象に使い、二重に足さない"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--cwd", str(self.target / "sub"),
                                            "--input", "request=x", cwd=self.tmp))["argv"]
            self.assertEqual(argv.count("--cwd"), 1)
            self.assertEqual(argv[3:7], ["workflow", "run", "--cwd", str(self.target)])
            self.assertEqual(argv[9:], ["works-factory-line", "--input", "request=x"])

    def test_run_without_workflow_name_stops(self):
        err = self.stopped(self.launch("workflow", "run", "--input", "request=x"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_option_before_command_stops(self):
        """殻は命令を位置で見分ける。旗が前に在ると --workflow-source も認証の確かめも抜けるので、起こさずに止まる"""
        for args in (["--cwd", str(self.target), "workflow", "run", "works-factory-line"],
                     ["workflow", "--cwd", str(self.target), "run", "works-factory-line"],
                     ["workflow", "--cwd", str(self.target), "approve", "run-1"]):
            with self.subTest(args=args):
                err = self.stopped(self.launch(*args))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn("使い方", err)

    def test_resume_and_approve_pass_through_unchanged(self):
        for args in (["workflow", "approve", "run-1", "--cwd", str(self.target)],
                     ["workflow", "run", "works-factory-line", "--resume", "--cwd", str(self.target)],
                     ["workflow", "status"]):
            with self.subTest(args=args):
                argv = self.reached(self.launch(*args))["argv"]
                self.assertEqual(argv[3:], args)

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

    def test_sandbox_writable_home_and_target_are_refused(self):
        """役の sandbox の Bash が書ける /tmp/claude-* の下（実パスで照らす）の家・対象・Archon の源の取り置きは、どの命令でも起こさずに拒む
        （今の works の dev/guard.sh の works_dev_refuse_claude_tmp と同じ形）"""
        # 直しが無い時に作られても他と混ざらず後で消えるように、試験ごとの名にする
        sandbox = f"/tmp/claude-works-test-{self.tmp.name}"
        self.addCleanup(shutil.rmtree, sandbox, ignore_errors=True)
        link = self.tmp / "to-claude-tmp"
        link.symlink_to(sandbox)
        for name, value in (("WORKS_FACTORY_HOME", f"{sandbox}/h"), ("WORKS_FACTORY_HOME", f"/private{sandbox}/h2"),
                            ("XDG_STATE_HOME", f"{sandbox}/state"), ("WORKS_FACTORY_HOME", str(link / "h3")),
                            ("XDG_CACHE_HOME", f"{sandbox}/cache")):
            with self.subTest(name=name, value=value):
                err = self.stopped(self.launch("workflow", "status", **{name: value}))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn(name, err)
                self.assertFalse(os.path.lexists(value), "拒んだ置き場に物を作った")
        target = pathlib.Path(sandbox) / "t"
        target.mkdir(parents=True)
        err = self.stopped(self.launch("workflow", "status", "--cwd", str(target)))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("対象", err)
        self.assertFalse(self.default_home(pathlib.Path(os.path.realpath(target))).exists(), "拒んだ対象の家を作った")
        for path in (self.tmp, "/tmp/claudex", "/tmp/other/claude-1"):
            with self.subTest(path=path):
                self.assertFalse(launcher.sandbox_writable(path))
        self.assertTrue(launcher.sandbox_writable("/private/tmp/claude-501/x/y"))

    def test_executing_launch_sweeps_write_logs_of_gone_workspaces(self):
        """工程を走らせる命令は、作業の場が無くなった run の書き込みと読んだ証拠の記録だけを片付ける（生きた run・控えの無い記録は残す）"""
        root = self.default_home(self.target) / "claude-config" / writelog.ROOT
        root.mkdir(parents=True)

        def dead_log(name):
            w = self.tmp / name
            w.mkdir()
            log = writelog.open_log(root, w)
            log.touch()
            w.rmdir()
            return log

        dead, live = dead_log("gone-run"), writelog.open_log(root, self.target)
        live.touch()
        legacy = writelog.log_path(root, self.tmp / "legacy-run")
        legacy.parent.mkdir()
        legacy.touch()
        done = self.launch("workflow", "run", "works-factory-line")
        self.reached(done)
        self.assertFalse(dead.parent.exists(), "作業の場の無い記録が残った")
        self.assertTrue(live.exists())
        self.assertTrue(legacy.exists())
        self.assertIn("書き込みの記録を 1 件片付けた", done.stderr)
        with self.subTest("読んだ証拠の記録も同じ決め方で片付ける"):
            reads_root = root.parent / reads.ROOT
            reads_root.mkdir(exist_ok=True)
            w = self.tmp / "gone-reader"
            w.mkdir()
            gone, kept = reads.open_log(reads_root, w), reads.open_log(reads_root, self.target)
            w.rmdir()
            done = self.launch("workflow", "run", "works-factory-line")
            self.reached(done)
            self.assertFalse(gone.parent.exists(), "作業の場の無い読んだ証拠の記録が残った")
            self.assertTrue(kept.parent.exists())
            self.assertIn("読んだ証拠の記録を 1 件片付けた", done.stderr)
        with self.subTest("工程を走らせない命令は片付けない"):
            later = dead_log("gone-later")
            done = self.launch("workflow", "status")
            self.reached(done)
            self.assertTrue(later.exists())
            self.assertNotIn("片付けた", done.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root は書けないフォルダの中も消せる")
    def test_write_log_sweep_failure_does_not_stop_the_run(self):
        """片付けがしくじっても（記録の根が読めない・置き場が消せない）、1 行で言って run は起こす"""
        root = self.default_home(self.target) / "claude-config" / writelog.ROOT
        root.mkdir(parents=True)
        w = self.tmp / "gone-run"
        w.mkdir()
        dead = writelog.open_log(root, w)
        dead.touch()
        w.rmdir()
        for mode, said in ((0o000, "書き込みの記録を片付けられなかった"), (0o500, "書き込みの記録を 1 件片付けられなかった")):
            with self.subTest(mode=oct(mode)):
                root.chmod(mode)
                self.addCleanup(root.chmod, 0o700)
                done = self.launch("workflow", "run", "works-factory-line")
                root.chmod(0o700)
                self.reached(done)
                self.assertIn(said, done.stderr)
                self.assertIn("run は続ける", done.stderr)
                self.assertTrue(dead.parent.exists())

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

    def test_child_env_carries_answer_head(self):
        """関所の答えの行の頭は家を名指して殻を通す respond。利用者の値より殻の値"""
        chosen = self.tmp / "chosen-home"
        for user_value, home in (({}, self.default_home(self.target)),
                                 ({answer.ENV: "sh use.sh answer x", "WORKS_FACTORY_HOME": str(chosen)}, chosen)):
            with self.subTest(user=user_value):
                env = self.reached(self.launch("workflow", "status", cwd=self.target / "sub", **user_value))["env"]
                head = shlex.split(env[answer.ENV])
                self.assertEqual(head, ["env", f"WORKS_FACTORY_HOME={home}", str(self.repo / "bin" / "works-factory"),
                                        "workflow", "respond", "--cwd", os.path.realpath(self.target)])
                self.assertIn(shlex.join(["bin/works-factory", *head[3:-1]]), answer.HOLE)

    def test_answer_line_reaches_the_run_home_from_another_shell(self):
        """一度だけ選んだ家（WORKS_FACTORY_HOME・XDG_STATE_HOME）で起こした run の答えの行は、その値の無いシェルで打っても同じ家に届く"""
        chosen = self.tmp / "chosen-home"
        for chooses, home in (({"WORKS_FACTORY_HOME": str(chosen)}, chosen),
                              ({"XDG_STATE_HOME": str(self.tmp / "state")},
                               self.tmp / "state" / "works-factory" / "targets" / short(self.target))):
            with self.subTest(chooses=chooses):
                got = self.reached(self.launch("workflow", "run", "works-factory-line", **chooses))
                self.assertEqual(got["env"]["HOME"], str(home / "home"))
                line = answer.line("run-1", "continue", "x", env=got["env"])
                self.bun_log.unlink()
                argv = shlex.split(line)
                done = subprocess.run([shutil.which(argv[0]), *argv[1:]], env=self.env, cwd=self.tmp,
                                      capture_output=True, text=True, encoding="utf-8", timeout=120)
                answered = self.reached(done)
                self.assertEqual(answered["env"]["HOME"], str(home / "home"))
                self.assertEqual(answered["argv"][3:], ["workflow", "respond", "--cwd", str(self.target), "run-1",
                                                        "continue", "x"])

    def test_child_gets_the_archon_source_it_runs(self):
        """線の節が殻を入れ子にせず同じ Archon を起こせるよう、殻が起こした源のパスを子に渡す"""
        reached = self.reached(self.launch("workflow", "status"))
        source = reached["env"][place.SOURCE_ENV]
        self.assertIn(str(pathlib.Path(source) / ENTRY), reached["argv"])

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

    def test_gh_shim_follows_read_only_gh(self):
        env = self.reached(self.launch("workflow", "status"))["env"]
        head = pathlib.Path(env["PATH"].split(os.pathsep)[1])
        self.assertTrue(head.is_relative_to(self.default_home(self.target)), head)
        shim = (head / "gh").read_text(encoding="utf-8")
        self.assertIn(str(self.gh), shim)
        self.assertIn(str(self.home), shim)

    def test_child_path_starts_with_read_only_gh(self):
        """役が打つ gh は読むだけの口 works-gh: 書く命令とトークンの読み出しを拒み、読む命令は利用者の gh を継ぐ口へ渡す"""
        gh_log = self.tmp / "gh.txt"
        put(self.gh, f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{gh_log}"\n')
        env = self.reached(self.launch("workflow", "status"))["env"]
        first = shutil.which("gh", path=env["PATH"])
        self.assertEqual(pathlib.Path(first).parent, self.repo / "bin" / "_lib" / "no-post-bin")
        for args in (["pr", "create", "-R", "o/r"], ["api", "-X", "POST", "repos/o/r/issues"], ["auth", "token"]):
            with self.subTest(args=args):
                done = subprocess.run([first, *args], env=env, capture_output=True, text=True, encoding="utf-8",
                                      timeout=60)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertTrue(done.stderr.startswith("works-gh: 通さない"), done.stderr)
        self.assertFalse(gh_log.exists(), "拒むはずの命令が利用者の gh に届いた")
        done = subprocess.run([first, "pr", "view", "1", "-R", "o/r"], env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(gh_log.read_text(encoding="utf-8").splitlines(), ["pr view 1 -R o/r"])

    def test_no_gh_without_a_real_gh(self):
        """gh の無い利用者の子に読むだけの口も置かない（並行 PR の確かめの「gh が無い → 役に任せる」を、口の拒否の人待ちに変えない）。
        トークンを読む口も無いので、トークンも渡さない"""
        self.gh.unlink()
        env = self.reached(self.launch("workflow", "status", GH_TOKEN=GH_FAKE))["env"]
        self.assertIsNone(shutil.which("gh", path=env["PATH"]))
        self.assertEqual([n for n in env if n.startswith("WORKS_FACTORY_HOST_")], [])

    def test_child_env_has_no_github_tokens(self):
        """子の環境に gh の 4 つのトークンの名は無い。値は gh の読まない渡しの名で在る（在るかだけを見る）"""
        tokens = dict.fromkeys(GITHUB_TOKENS, GH_FAKE)
        for args in (["workflow", "status"], ["workflow", "run", "works-factory-line"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, **tokens))["env"]
                self.assertEqual([n for n in tokens if n in env], [])
                self.assertEqual(sorted(n for n in env if n.startswith("WORKS_FACTORY_HOST_")),
                                 ["WORKS_FACTORY_HOST_GH_ENTERPRISE_TOKEN", "WORKS_FACTORY_HOST_GH_TOKEN"])

    def token_probe(self):
        """利用者の gh を、受けた GH_TOKEN が GH_FAKE かだけを記録する偽物に替える（値は書かない）。記録のファイルを返す"""
        log = self.tmp / "gh-token.txt"
        put(self.gh, f'#!/bin/sh\nif [ "${{GH_TOKEN-}}" = "{GH_FAKE}" ]; then echo token-ok; else echo token-missing; fi >> "{log}"\n')
        return log

    def test_env_only_login_reaches_the_users_gh(self):
        """環境変数だけで gh にログインする利用者: 役が打つ読む gh が、利用者の gh に GH_TOKEN 付きで届く（#132）"""
        log = self.token_probe()
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            with self.subTest(name=name):
                env = self.reached(self.launch("workflow", "status", **{name: GH_FAKE}))["env"]
                done = subprocess.run(["gh", "pr", "view", "1", "-R", "o/r"], env=env, capture_output=True, text=True,
                                      encoding="utf-8", timeout=60)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(log.read_text(encoding="utf-8").splitlines()[-1], "token-ok")

    def test_token_readout_is_refused_without_the_value(self):
        """役の gh の auth token は拒まれ、トークンの値は出ない"""
        env = self.reached(self.launch("workflow", "status", GH_TOKEN=GH_FAKE))["env"]
        done = subprocess.run(["gh", "auth", "token"], env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertNotIn(GH_FAKE, done.stdout + done.stderr)

    def test_login_outside_env_gets_no_token(self):
        """keychain・hosts.yml でログインする利用者（トークンの環境変数が無い）は今のまま: 渡しの名も無く、口は値を足さない"""
        log = self.token_probe()
        env = self.reached(self.launch("workflow", "status"))["env"]
        self.assertEqual([n for n in env if n.startswith("WORKS_FACTORY_HOST_")], [])
        subprocess.run(["gh", "pr", "view", "1", "-R", "o/r"], env=env, capture_output=True, timeout=60)
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["token-missing"])

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

    def test_continuing_commands_check_auth_and_install_plugins(self):
        """workflow wake・signal も止めた Archon が工程を走らせる（packages/cli/src/cli.ts が executesWorkflow の前で捌く）"""
        for args in (["workflow", "wake", "run-1"], ["workflow", "signal", "run-1", "done"]):
            with self.subTest(args=args):
                claude_log = self.tmp / "claude.jsonl"
                claude_log.unlink(missing_ok=True)
                done = self.launch(*args, WORKS_FACTORY_HOME=str(self.tmp / "home-of" / args[1]))
                self.reached(done)
                self.assertIn("認証は ANTHROPIC_API_KEY", done.stderr)
                self.assertTrue(claude_log.exists(), f"{args} で claude の plugin の CLI を呼んでいない")

    def test_continuing_commands_carry_the_login_to_archon(self):
        """関所に答える・run を続ける命令も AI の節を走らせるので、ログインだけの利用者のトークンが Archon に届く"""
        (self.home / ".claude" / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"accessToken": TOKEN}}), encoding="utf-8")
        login = {"ANTHROPIC_API_KEY": None, "FAKE_SECURITY_HOME": str(self.home), "FAKE_SECURITY_VALUE": TOKEN,
                 "FAKE_SECURITY_SERVICE": "Claude Code-credentials"}
        for args in (["workflow", "resume", "run-1"], ["workflow", "approve", "run-1"], ["workflow", "reject", "run-1"],
                     ["workflow", "respond", "run-1", "continue", "x"], ["workflow", "wake", "run-1"],
                     ["workflow", "signal", "run-1", "done"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, WORKS_FACTORY_HOME=str(self.tmp / "home-of" / args[1]), **login))["env"]
                self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))

    def test_commands_not_known_to_only_read_carry_the_login_to_archon(self):
        """AI を走らせる上の命令（trigger・chat・serve）と殻の知らない命令は、前どおり認証を通してトークンを Archon に渡す"""
        (self.home / ".claude" / ".credentials.json").write_text(
            json.dumps({"claudeAiOauth": {"accessToken": TOKEN}}), encoding="utf-8")
        login = {"ANTHROPIC_API_KEY": None, "FAKE_SECURITY_HOME": str(self.home), "FAKE_SECURITY_VALUE": TOKEN,
                 "FAKE_SECURITY_SERVICE": "Claude Code-credentials"}
        for args in (["trigger", "x"], ["chat", "x"], ["serve"], ["unknown-command"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, **login))["env"]
                self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))

    def test_claude_on_relative_path_is_not_used(self):
        """PATH の相対の置き場（打った場所の下）の claude は、隔離した設定にプラグインを入れる本物として使わない"""
        (self.fake / "claude").unlink()
        write_fake_claude(self.target / "rel-bin")
        err = self.stopped(self.launch("workflow", "run", "works-factory-line",
                                       PATH=os.pathsep.join(["rel-bin", str(self.fake), str(self.tools)])))
        self.assertIn("CLAUDE_BIN_PATH", err)
        self.assertFalse((self.tmp / "claude.jsonl").exists(), "相対の置き場の claude を呼んだ")

    def fence_of(self, env) -> list[str]:
        """子の CLAUDE_BIN_PATH の殻が起こす包みの命令（exec の後ろ）"""
        shell = pathlib.Path(env["CLAUDE_BIN_PATH"])
        self.assertTrue(shell.is_relative_to(self.default_home(self.target) / launcher.FENCE_DIR), shell)
        line = next(l for l in shell.read_text(encoding="utf-8").splitlines() if l.startswith("exec "))
        return shlex.split(line)[1:]

    def test_executing_launch_puts_the_fence_before_claude(self):
        """役を起こす claude は書き込みの柵の包み（workflows/.shared/fence.py）を通る。包みは本物の claude と隔離した置き場を名指す"""
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        argv = self.fence_of(env)
        self.assertEqual(argv[1:3], ["-I", "-B"])
        self.assertEqual(argv[3], str(self.repo / "workflows" / ".shared" / "fence.py"))
        self.assertEqual(argv[argv.index("--real") + 1], str(self.fake / "claude"))
        self.assertEqual(argv[argv.index("--archon-home") + 1], env["ARCHON_HOME"])
        self.assertEqual(argv[argv.index("--claude-config") + 1], env["CLAUDE_CONFIG_DIR"])
        self.assertEqual(argv[-2:], ["--", "$@"])

    def test_fence_denies_what_later_launches_run_outside_the_sandbox(self):
        """後の役の起動と次の起動が sandbox の外で走らせる物（殻・gh の口・本物の claude・包みを起こす Python・取り置いた Archon の源・
        工場の checkout の根の全体〔根に置いた .py も次の起動の import に勝つ〕）は、禁じる一覧に入る"""
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        argv = self.fence_of(env)
        own = {argv[i + 1] for i, a in enumerate(argv) if a == "--own"}
        home = self.default_home(self.target)
        self.assertEqual(own, {str(home / launcher.FENCE_DIR), str(home / launcher.HOST_GH_DIR),
                               str(self.cache_home / "works-factory"),
                               str(self.repo),
                               sys.prefix, sys.base_prefix, os.path.realpath(self.fake / "claude")})

    def test_env_file_naming_claude_bin_path_stops_the_run(self):
        """Archon が起きる場所の .env* か .archon/.env、ARCHON_HOME の .env が CLAUDE_BIN_PATH を名指すと、包みが外れるので起こさない"""
        for where, name, line in ((self.target, ".archon/.env", "CLAUDE_BIN_PATH=/usr/local/bin/claude"),
                                  (self.target / "sub", ".env.local", "export CLAUDE_BIN_PATH = /x"),
                                  (self.target, ".env", "CLAUDE_BIN_PATH:"),
                                  (self.default_home(self.target) / "archon-home", ".env", "CLAUDE_BIN_PATH=/usr/local/bin/claude")):
            with self.subTest(file=str(where / name)):
                env_file = put(where / name, f"A=1\n{line}\n")
                err = self.stopped(self.launch("workflow", "run", "works-factory-line", cwd=self.target / "sub"))
                env_file.unlink()
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn(str(env_file), err)
        put(self.target / ".archon" / ".env", "CLAUDE_BIN_PATHS=/x\nOTHER=CLAUDE_BIN_PATH=/x\n")
        self.reached(self.launch("workflow", "run", "works-factory-line"))

    def test_users_claude_bin_path_is_the_real_claude_behind_the_fence(self):
        real = write_fake_claude(self.tmp / "my-claude")
        env = self.reached(self.launch("workflow", "run", "works-factory-line", CLAUDE_BIN_PATH=str(real)))["env"]
        self.assertNotEqual(env["CLAUDE_BIN_PATH"], str(real))
        argv = self.fence_of(env)
        self.assertEqual(argv[argv.index("--real") + 1], str(real))

    def test_reading_commands_get_no_fence(self):
        for args in (["workflow", "get", "run-1"], ["workflow", "status"], ["validate", "workflows"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args))["env"]
                self.assertNotIn("CLAUDE_BIN_PATH", list(env))

    def test_no_auth_run_without_claude_stops(self):
        """柵を掛けられない run は起こさない（認証の要らない道でも、役は claude で起きる）"""
        (self.fake / "claude").unlink()
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None,
                                       WORKS_FACTORY_NO_AUTH="1"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("CLAUDE_BIN_PATH", err)

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
        with self.subTest("HOME の下の対象（mise は ~/… と出す）"):
            under_home = self.home / "proj"
            under_home.mkdir()
            git(under_home, "init", "-q")
            workspaces = os.path.realpath(self.default_home(under_home) / "archon-home" / "workspaces")
            env = self.reached(self.launch("workflow", "status", cwd=under_home,
                                           FAKE_MISE_TRUSTED=str(under_home)))["env"]
            self.assertEqual(env.get("MISE_TRUSTED_CONFIG_PATHS"), workspaces)

    def test_toolset_failure_stops_before_archon(self):
        shutil.rmtree(self.home / ".claude")
        make_user_config(self.home / ".claude", only=("superpowers",))
        err = self.stopped(self.launch("workflow", "run", "works-factory-line"))
        self.assertIn("pr-review-toolkit", err)

    def test_missing_auth_stops_before_archon(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None))
        self.assertIn("認証が無い", err)

    def test_reading_commands_reach_archon_without_auth(self):
        """工程を走らせない命令（run を読む・一覧を見る）は認証を通さない。認証の無い利用者も bin/apply で run を読める"""
        for args in (["workflow", "get", "run-1"], ["workflow", "status"], ["validate", "workflows"], ["version"], ["help"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, ANTHROPIC_API_KEY=None))["env"]
                self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))

    def test_no_auth_runs_without_auth_check_or_plugins(self):
        done = self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None, WORKS_FACTORY_NO_AUTH="1")
        env = self.reached(done)["env"]
        self.assertNotIn("認証は", done.stderr)
        self.assertTrue((pathlib.Path(env["CLAUDE_CONFIG_DIR"]) / ".works-toolset.json").is_file())
        self.assertFalse((self.tmp / "claude.jsonl").exists(), "NO_AUTH で claude の plugin の CLI を呼んだ")

    def test_no_auth_name_matches_entryshape(self):
        """L-E15: 殻が読む認証の要らない起動の名は、線の入口（lib/entryshape.py の NO_AUTH_ENV）が見る名と同じで、run の環境に届く
        （名が違うと、認証の要らない起動で PR を名指した run が gh を呼びに行く）"""
        lib = str(pathlib.Path(__file__).resolve().parents[2] / "lib")
        if lib not in sys.path:
            sys.path.append(lib)
        import entryshape
        env = self.reached(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None,
                                       **{entryshape.NO_AUTH_ENV: "1"}))["env"]
        self.assertEqual(env.get(entryshape.NO_AUTH_ENV), "1")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", list(env), "殻が認証の要らない起動と読んでいない")

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

    def test_missing_home_or_git_stops_with_one_line(self):
        only_python = self.tmp / "only-python"
        only_python.mkdir()
        (only_python / "python3").symlink_to(sys.executable)
        for missing, env in (("HOME", {"HOME": None}),
                             ("git", {"PATH": os.pathsep.join([str(self.fake), str(only_python)])})):
            with self.subTest(missing=missing):
                err = self.stopped(self.launch("workflow", "status", **env))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn(f"{missing} が無い", err)

    def test_old_python_stops_before_loading_parts(self):
        """持ってきた部品は 3.12 の書き方で、古い Python では読み込みで落ちる。その前に 1 行で止まる"""
        pretend = ("import runpy, sys; sys.version_info = (3, 9, 6, 'final', 0); "
                   f"runpy.run_path({str(self.repo / 'bin' / 'works-factory')!r}, run_name='__main__')")
        done = subprocess.run([sys.executable, "-c", pretend, "workflow", "status"], env=self.env, cwd=self.target,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(done.stderr.strip(), "works-factory: Python 3.12 以上が要る")
        self.assertFalse(self.bun_log.exists())

    @unittest.skipIf(shutil.which("bun") is None, "本物の bun が無い")
    def test_target_bunfig_preload_does_not_run(self):
        """bun は打った場所の bunfig.toml の preload を走らせる。対象の物を認証つきの Archon の中で走らせない"""
        mark = self.tmp / "preload-ran"
        (self.target / "bunfig.toml").write_text('preload = ["./plant.ts"]\n', encoding="utf-8")
        (self.target / "plant.ts").write_text(f"require('fs').writeFileSync({json.dumps(str(mark))}, 'x')\n",
                                              encoding="utf-8")
        self.bun.unlink()
        self.bun.symlink_to(shutil.which("bun"))
        done = self.launch("workflow", "status")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(mark.exists(), "対象の bunfig.toml の preload が走った")

    def test_bun_missing_stops_with_one_line(self):
        self.bun.unlink()
        err = self.stopped(self.launch("workflow", "status"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("bun が無い", err)


if __name__ == "__main__":
    unittest.main()
