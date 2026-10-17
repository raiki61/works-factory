"""入口の殻 bin/works-factory（bin/_lib/launcher.py）の試験。

殻を子のプロセスとして、tests/bin/fakelaunch.py の使い捨ての木（偽の Archon の源）で走らせる。PATH には偽の bun・claude・gh・
security と、python3・git だけを置く。偽の bun は受けた引数と環境を JSON に書き、試験がそれを照らす（トークンは在るかだけを見る。環境は名の一覧で照らし、落ちた時に値を
試験の出力に出さない）。
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from bin._lib import launcher, place, toolset
from lib import answer, launchgroups, reads, userenv, writelog
from tests.bin import fakelaunch, hermetic
from tests.bin.fakelaunch import ENTRY, FAKE_BUN, put
from tests.bin.gitkit import git
from tests.bin.test_toolset import make_user_config, write_fake_claude

TOKEN = "sk-ant-oat01-fake-for-launcher"
API_KEY = "sk-ant-api03-fake-for-launcher"
GH_FAKE = "ghp_fake-for-launcher"
GITHUB_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
# 利用者の場から漏れると照らしが揺れる名（hermetic が外さない物）
USER_SPECIFIC = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "GH_CONFIG_DIR", *GITHUB_TOKENS)

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


# 利用者の --config を読む bun -e だけ本物の bun に回し、ほかは FAKE_BUN と同じに記録する
def read_with_real_bun(bun: str) -> str:
    return (f"#!/usr/bin/env python3\nimport os, sys\nif '-e' in sys.argv:\n    os.execv({bun!r}, [{bun!r}, *sys.argv[1:]])\n"
            + FAKE_BUN.split("\n", 1)[1])


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
        self.assertEqual(argv[9], "--config")
        self.assertEqual(json.loads(pathlib.Path(argv[10]).read_text(encoding="utf-8")), {"aliases": place.group_presets()})
        self.assertEqual(argv[11:], ["works-factory-line", "--input", "request=x"])
        with self.subTest("利用者の --cwd は対象に使い、二重に足さない"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--cwd", str(self.target / "sub"),
                                            "--input", "request=x", cwd=self.tmp))["argv"]
            self.assertEqual(argv.count("--cwd"), 1)
            self.assertEqual(argv[3:7], ["workflow", "run", "--cwd", str(self.target)])
            self.assertEqual(argv[11:], ["works-factory-line", "--input", "request=x"])

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
        self.commit_target()
        for args in (["workflow", "approve", "run-1", "--cwd", str(self.target)],
                     ["workflow", "run", "works-factory-line", "--resume", "--cwd", str(self.target)],
                     ["workflow", "status"]):
            with self.subTest(args=args):
                argv = self.reached(self.launch(*args))["argv"]
                self.assertEqual(argv[3:], args)

    def commit_target(self) -> str:
        (self.target / "kept.txt").write_text("kept\n", encoding="utf-8")
        git(self.target, "add", "-A")
        git(self.target, "commit", "-q", "-m", "seed")
        return git(self.target, "rev-parse", "HEAD")

    def test_run_starts_from_the_targets_current_state(self):
        head = self.commit_target()
        with self.subTest("汚れていない対象は HEAD から"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--input", "request=x"))["argv"]
            self.assertEqual(argv[11:], ["works-factory-line", "--from", head, "--input", "request=x"])
        with self.subTest("未追跡のファイルは HEAD を親に包んだ commit から"):
            (self.target / "untracked.txt").write_text("u\n", encoding="utf-8")
            done = self.launch("workflow", "run", "works-factory-line", "--input", "request=x")
            argv = self.reached(done)["argv"]
            self.assertEqual(argv[12], "--from")
            self.assertNotEqual(argv[13], head)
            self.assertEqual(git(self.target, "rev-parse", f"{argv[13]}^"), head)
            self.assertIn(argv[13][:12], done.stderr)
        with self.subTest("利用者の --from が勝ち、殻は足さない"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--from", "x", "--input", "request=x"))["argv"]
            self.assertEqual(argv[11:], ["works-factory-line", "--from", "x", "--input", "request=x"])

    def test_test_cmd_running_the_checkout_stops_before_archon(self):
        """#495: test_cmd が対象の手元を絶対パスで指すと、Archon を起こさずに止める（run の試験が直しでなく手元を試す偽の緑）。
        WORKS_FACTORY_ALLOW_TESTCMD=1 なら知らせて起こす。git が無視する物を相対で指す形は注意だけで起こす"""
        self.commit_target()
        (self.target / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        runner = self.target / ".venv" / "bin" / "run-tests"
        runner.parent.mkdir(parents=True)
        runner.write_text("#!/bin/sh\n", encoding="utf-8")
        git(self.target, "add", ".gitignore")
        git(self.target, "commit", "-q", "-m", "ignore")
        run = ("workflow", "run", "works-factory-line", "--input", "request=x")
        err = self.stopped(self.launch(*run, "--input", f"test_cmd={runner} -q"))
        self.assertIn("止める（test_cmd）", err)
        self.assertIn(f"test_cmd が対象の手元（{self.target}）を走らせる形", err)
        self.assertIn(launcher.ALLOW_TESTCMD_ENV, err)
        done = self.launch(*run, f"--input=test_cmd={runner} -q", **{launcher.ALLOW_TESTCMD_ENV: "1"})
        self.reached(done)
        self.assertIn("注意（test_cmd）", done.stderr)
        self.assertIn("=1 なので止めずに起こす", done.stderr)
        done = self.launch(*run, "--input", "test_cmd=.venv/bin/run-tests -q")
        self.reached(done)
        self.assertIn("注意（test_cmd）", done.stderr)

    def test_test_cmd_through_home_always_stops_unless_allowed(self):
        """PR #503 の見直し: 対象のコマンドは利用者の HOME で走る（旗は無い）ので、~・$HOME で手元を指す test_cmd も run の中で
        手元を指す。いつも止め、WORKS_FACTORY_ALLOW_TESTCMD=1 なら起こす"""
        self.commit_target()
        (self.target / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        runner = self.target / ".venv" / "bin" / "run-tests"
        runner.parent.mkdir(parents=True)
        runner.write_text("#!/bin/sh\n", encoding="utf-8")
        git(self.target, "add", ".gitignore")
        git(self.target, "commit", "-q", "-m", "ignore")
        run = ("workflow", "run", "works-factory-line", "--input", "request=x")
        via_home = f"~/{os.path.relpath(runner, self.home)} -q"
        err = self.stopped(self.launch(*run, "--input", f"test_cmd={via_home}"))
        self.assertIn("止める（test_cmd）", err)
        self.reached(self.launch(*run, "--input", f"test_cmd={via_home}", **{launcher.ALLOW_TESTCMD_ENV: "1"}))

    def test_test_cmd_check_that_fails_stops_unless_allowed(self):
        def failing(*_, **__):
            return subprocess.CompletedProcess([], 1, stdout="")
        with self.assertRaises(launcher.Stop):
            launcher.check_test_cmd({}, self.target, ["make test"], run=failing)
        with contextlib.redirect_stderr(io.StringIO()) as said:
            launcher.check_test_cmd({launcher.ALLOW_TESTCMD_ENV: "1"}, self.target, ["make test"], run=failing)
        self.assertIn("終了の値 1", said.getvalue())
        launcher.check_test_cmd({}, self.target, ["", "  "], run=failing)

    def test_flag_values_reads_both_forms_in_order(self):
        self.assertEqual(launcher.flag_values(["--input", "test_cmd=a b", "--input=test_cmd=c", "--input", "request=x"], "--input"),
                         ["test_cmd=a b", "test_cmd=c", "request=x"])
        self.assertEqual(launcher.flag_values(["--input", "--input", "x"], "--input"), ["--input"], "値に取った字は旗として読まない")

    def test_user_workflow_source_is_refused(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--workflow-source", str(self.tmp)))
        self.assertIn("--workflow-source", err)

    def test_users_run_config_is_merged_under_the_factory_groups(self):
        """利用者の --config は殻の層に合わせて 1 つで渡る: env などは効き、同じ名の群の別名は工場の値に替わる。相対のパスは対象から引く。
        合わせた物（env の秘密が入りうる）は取り置き cache に置かず対象の家に置き、群の別名だけの層は cache に置く"""
        if shutil.which("bun") is None:
            self.skipTest("bun が無い（利用者の --config は Archon と同じ Bun.YAML.parse で読む）")
        self.bun.write_text(read_with_real_bun(shutil.which("bun")), encoding="utf-8")
        group = next(iter(launchgroups.GROUPS))
        (self.target / "mine.yaml").write_text(f"env:\n  MINE: '1'\naliases:\n  '{group}': {{provider: claude, model: haiku}}\n",
                                               encoding="utf-8")
        for flag in (["--config", "mine.yaml"], [f"--config={self.target / 'mine.yaml'}"]):
            with self.subTest(flag=flag):
                done = self.launch("workflow", "run", "works-factory-line", *flag, "--input", "request=x")
                argv = self.reached(done)["argv"]
                self.assertEqual(argv.count("--config"), 1)
                self.assertNotIn(flag[-1], argv)
                merged = pathlib.Path(argv[argv.index("--config") + 1])
                self.assertTrue(merged.is_relative_to(self.default_home(self.target)), merged)
                self.assertFalse(merged.is_relative_to(self.cache_home), merged)
                layer = json.loads(merged.read_text(encoding="utf-8"))
                self.assertEqual(layer, {"env": {"MINE": "1"}, "aliases": place.group_presets()})
                self.assertIn(group, done.stderr)
                self.assertEqual(argv[11:], ["works-factory-line", "--input", "request=x"])
        with self.subTest("利用者の --config が無ければ群の別名だけの層を cache に置く"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line"))["argv"]
            self.assertTrue(pathlib.Path(argv[argv.index("--config") + 1]).is_relative_to(self.cache_home))
        self.assertEqual([json.loads(p.read_text(encoding="utf-8")) for p in self.cache_home.rglob("run-config/*.json")],
                         [{"aliases": place.group_presets()}])
        with self.subTest("読めない --config は起こさずに止める"):
            self.assertIn("none.yaml", self.stopped(self.launch("workflow", "run", "works-factory-line", "--config", "none.yaml")))

    def test_adopt_gets_no_run_config(self):
        """--adopt は記録した AI の設定を受け継ぐ。Archon は aliases を持つ --config の層をその時に拒むので、殻は足さず、利用者の物も触らない"""
        for args in (["--adopt", "run-1"], ["--adopt=run-1", "--config", "mine.yaml"]):
            with self.subTest(args=args):
                argv = self.reached(self.launch("workflow", "run", "works-factory-line", *args))["argv"]
                self.assertEqual(argv[3:9], ["workflow", "run", "--cwd", str(self.target), "--workflow-source", argv[8]])
                self.assertEqual(argv[9:], ["works-factory-line", *args])

    def test_unknown_group_in_model_is_refused_with_the_known_groups(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--model", "@wf-judge-cor=haiku"))
        self.assertIn("@wf-judge-cor", err)
        for name in launchgroups.GROUPS:
            self.assertIn(name, err)
        with self.subTest("表に在る群と、工場の接頭辞でない名は通す"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--model=@wf-judge-core=haiku",
                                            "--model", "large=opus"))["argv"]
            self.assertEqual(argv[-3:], ["--model=@wf-judge-core=haiku", "--model", "large=opus"])

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
        self.assertEqual(json.loads(env[userenv.RECORD])["HOME"], str(self.home))   # 対象のコマンドにだけ利用者の HOME・XDG を戻す控え（持ち主の決め target-user-env）
        self.assertEqual(env["ARCHON_TELEMETRY_DISABLED"], "1")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertEqual(env["WORKS_FACTORY_ROOT"], str(self.repo))
        self.assertIn("defaultAssistant: claude", (pathlib.Path(env["ARCHON_HOME"]) / "config.yaml").read_text(encoding="utf-8"))

    def test_rebuilt_home_gets_the_factory_settings_and_users_archon_is_untouched(self):
        """工場の Archon の家を消して作り直しても家の config.yaml に工場の決める値が入り、利用者の ~/.archon には書かない"""
        users = put(self.home / ".archon" / "config.yaml", "workflows:\n  autoResumeOnQuotaReset: true\n")
        before = users.read_bytes()
        for attempt in ("new", "rebuilt"):
            with self.subTest(attempt):
                archon_home = pathlib.Path(self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]["ARCHON_HOME"])
                self.assertNotEqual(archon_home.resolve(), (self.home / ".archon").resolve())
                self.assertEqual((archon_home / "config.yaml").read_text(encoding="utf-8"),
                                 "defaultAssistant: claude\nworkflows:\n  autoResumeOnQuotaReset: false\n")
                shutil.rmtree(self.default_home(self.target))
        self.assertEqual(users.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in (self.home / ".archon").iterdir()), ["config.yaml"])

    def test_users_home_reaches_target_commands_whether_or_not_a_switch_is_set(self):
        """旗に依らず、起動はいつも対象のコマンドに戻す利用者の HOME を控え、AI が書いた試験のコードを利用者の権限で走らせる告知の 1 行を
        言う。役と Archon の HOME は隔離のまま。旗の名は出力に出ない"""
        for switch in ({}, {"WORKS_FACTORY_TARGET_USER_ENV": "1"}):
            with self.subTest(switch=switch):
                done = self.launch("workflow", "run", "works-factory-line", **switch)
                env = self.reached(done)["env"]
                self.assertEqual(json.loads(env[userenv.RECORD])["HOME"], str(self.home))
                self.assertTrue(pathlib.Path(env["HOME"]).is_relative_to(self.default_home(self.target)), env["HOME"])
                self.assertIn(launcher.TARGET_ENV_NOTICE, done.stderr)
                self.assertNotIn("WORKS_FACTORY_TARGET_USER_ENV", done.stderr)

    def test_target_commands_get_the_users_home_without_a_switch(self):
        """旗を置かない起動の子の env に userenv.RECORD が在り、その HOME が利用者の HOME。子の HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR は
        家の下に隔離したまま"""
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        self.assertIn(userenv.RECORD, env)
        self.assertEqual(json.loads(env[userenv.RECORD])["HOME"], str(self.home))
        home = self.default_home(self.target)
        for name in ("HOME", "ARCHON_HOME", "CLAUDE_CONFIG_DIR"):
            with self.subTest(name=name):
                self.assertTrue(pathlib.Path(env[name]).is_relative_to(home), env[name])

    def test_executing_run_says_ai_test_code_runs_with_the_users_rights(self):
        """旗を置かない workflow run の標準エラーに、AI が書いた試験のコードを利用者の権限で走らせる・書く物も利用者の家に入る・コンテナか
        VM で回す道の 1 行が出る。走らせない命令（workflow status）には出ない"""
        done = self.launch("workflow", "run", "works-factory-line")
        self.reached(done)
        self.assertIn(launcher.TARGET_ENV_NOTICE, done.stderr)
        for word in ("AI が書いた試験のコード", "権限", "利用者の家", "コンテナ", "VM"):
            self.assertIn(word, launcher.TARGET_ENV_NOTICE)
        self.assertEqual(done.stderr.count(launcher.TARGET_ENV_NOTICE), 1)
        quiet = self.launch("workflow", "status")
        self.reached(quiet)
        self.assertNotIn("AI が書いた試験のコード", quiet.stderr)
        # README は同じ告知を書き（旗は無い）、準備の宣言 setup の書き方を test_cmd の節に書く
        readme = (pathlib.Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
        self.assertIn(launcher.TARGET_ENV_NOTICE, readme)
        self.assertNotIn("WORKS_FACTORY_TARGET_USER_ENV", readme)
        section = readme.split("### test_cmd と作業ツリー\n", 1)[1].split("\n#", 1)[0]
        for word in ("`setup`", ".review-checks.json", "`suite`", ".gitignore", "`test_cmd` だけの対象"):
            self.assertIn(word, section)

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

    def test_child_gets_the_archon_head_it_runs(self):
        """線の節が殻を入れ子にせず同じ Archon を起こせるよう、殻が自分を起こした命令の頭を子に渡す"""
        reached = self.reached(self.launch("workflow", "status"))
        head = json.loads(reached["env"][place.shared("childsweep").CLI_ENV])
        self.assertEqual(head, [str(self.bun), f"--config={self.source / 'bunfig.toml'}", str(self.source / ENTRY)])
        self.assertEqual(reached["argv"][:len(head)], head)

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

    def test_deny_web_reaches_the_isolated_settings(self):
        """ベンチのランナーが頼む WebFetch・WebSearch の拒み（toolset.DENY_WEB_ENV）は、殻が toolset の install まで運ぶ"""
        def permissions(env):
            settings = json.loads((pathlib.Path(env["CLAUDE_CONFIG_DIR"]) / "settings.json").read_text(encoding="utf-8"))
            return settings.get("permissions")

        env = self.reached(self.launch("validate", "workflows", **{toolset.DENY_WEB_ENV: "1"}))["env"]
        self.assertEqual(permissions(env), toolset.permissions(deny_web=True))
        env = self.reached(self.launch("validate", "workflows"))["env"]
        self.assertEqual(permissions(env), toolset.permissions(deny_web=False))

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
                     ["workflow", "respond", "run-1", "continue", "x"], ["workflow", "answer", "run-1", "x"],
                     ["workflow", "wake", "run-1"], ["workflow", "signal", "run-1", "done"]):
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

    def test_home_inside_the_factory_checkout_is_refused(self):
        """家が工場の checkout（ROOT。ここでは使い捨ての木の self.repo）の下だと、柵が ROOT を丸ごと禁じて読むだけの役が家に書けない。
        どの命令でも起こさずに 1 行で拒む（#358）"""
        link = self.tmp / "to-factory"
        link.symlink_to(self.repo)
        for name, value in (("WORKS_FACTORY_HOME", str(self.repo / "h")), ("WORKS_FACTORY_HOME", str(self.repo)),
                            ("WORKS_FACTORY_HOME", str(link / "h2")), ("XDG_STATE_HOME", str(self.repo / "state"))):
            with self.subTest(name=name, value=value):
                err = self.stopped(self.launch("workflow", "status", **{name: value}))
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn(name, err)
                self.assertIn("checkout の外", err)
                if value != str(self.repo):
                    self.assertFalse(os.path.lexists(value), "拒んだ置き場に物を作った")

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
        records = str(self.default_home(self.target) / launcher.FENCE_DIR / "launches.jsonl")
        self.assertEqual(argv[argv.index("--records") + 1], records)
        self.assertEqual(env[launcher.FENCE_RECORDS_ENV], records, "script のノードが包みの記録を読めない（包みの宣言が無い）")

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

    def test_env_file_naming_the_fence_records_stops_the_run(self):
        """env のファイルが包みの記録（受け付けが読む包みの宣言）を名指すと、宣言が消えるかほかを指すので起こさない"""
        for where, name in ((self.target, ".env"), (self.default_home(self.target) / "archon-home", ".env")):
            with self.subTest(file=str(where / name)):
                env_file = put(where / name, f"{launcher.FENCE_RECORDS_ENV}=/elsewhere.jsonl\n")
                err = self.stopped(self.launch("workflow", "run", "works-factory-line"))
                env_file.unlink()
                self.assertEqual(len(err.strip().splitlines()), 1, err)
                self.assertIn(launcher.FENCE_RECORDS_ENV, err)

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
                self.assertNotIn(launcher.FENCE_RECORDS_ENV, list(env))

    def test_no_auth_run_without_claude_stops(self):
        """柵を掛けられない run は起こさない（認証の要らない道でも、役は claude で起きる）"""
        (self.fake / "claude").unlink()
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None,
                                       WORKS_FACTORY_NO_AUTH="1"))
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertIn("CLAUDE_BIN_PATH", err)

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
        self.assertEqual(launcher.NO_AUTH_ENV, entryshape.NO_AUTH_ENV)
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


class ReadmeUsageTest(unittest.TestCase):
    """#495: README の「使い方」が、依頼のファイルの形（例が入口の照らしを通る）・test_cmd・作業ツリーの起点を書き、殻の案内が
    指すセクションの名が見出しに在る"""
    README = (pathlib.Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")

    def section(self, name: str) -> str:
        head = f"### {name}\n"
        self.assertIn(head, self.README)
        return self.README.split(head, 1)[1].split("\n#", 1)[0]

    def test_request_example_passes_the_entry_check(self):
        lib = str(pathlib.Path(__file__).resolve().parents[2] / "lib")
        if lib not in sys.path:
            sys.path.append(lib)
        import carry
        import entry
        [example] = [block.split("\n", 1)[1] for block in self.section("依頼のファイル").split("```")[1::2]
                     if block.startswith("json\n")]
        parts = carry.parts(json.loads(example))
        self.assertTrue(parts[carry.FINDINGS])
        self.assertEqual(entry.request_problems(parts[carry.FINDINGS]), [])

    def test_test_cmd_and_start_point_are_documented(self):
        from bin._lib import testcmd_check
        self.assertIn("「test_cmd と作業ツリー」", testcmd_check.HOW)
        test_cmd = self.section("test_cmd と作業ツリー")
        for word in ("--input test_cmd=", launcher.ALLOW_TESTCMD_ENV, "止める（test_cmd）", "注意（test_cmd）"):
            self.assertIn(word, test_cmd)
        start = self.section("作業ツリーの起点")
        for flag in ("--from", "--from-branch", "--base", "--branch", "--no-worktree", "--adopt"):
            self.assertIn(f"`{flag}", start)


if __name__ == "__main__":
    unittest.main()
