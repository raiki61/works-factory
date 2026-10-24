"""入口の殻 bin/works-factory（bin/_lib/launcher.py）の試験。

殻を子のプロセスとして、tests/bin/fakelaunch.py の使い捨ての木（偽の Archon の源）で走らせる。PATH には偽の bun・claude・gh・
security と、python3・git だけを置く。偽の bun は受けた引数と環境を JSON に書き、試験がそれを照らす（トークンは在るかだけを見る。環境は名の一覧で照らし、落ちた時に値を
試験の出力に出さない）。
"""
import hashlib
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

from bin._lib import auth_launch, launcher, place, recordroot, specreviews, toolset
from lib import answer, launchgroups, reads, userenv, writelog
from tests import archon
from tests.bin import fakelaunch, hermetic
from tests.bin.fakelaunch import ENTRY, FAKE_BUN, put, unique_run_id
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
        for name in (*USER_SPECIFIC, *launcher.CHOSEN_TTL_ENVS):
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

    def layer(self, argv) -> dict:
        """殻が Archon に --config で渡した run の層"""
        return json.loads(pathlib.Path(argv[argv.index("--config") + 1]).read_text(encoding="utf-8"))

    def factory_layer(self, home=None) -> dict:
        """利用者の --config の無い新しい run に殻が渡す層"""
        head = ["env", f"WORKS_FACTORY_HOME={home or self.default_home(self.target)}", str(self.repo / "bin" / "works-factory"),
                "workflow", "respond", "--cwd", str(self.target)]
        return {"env": {"WORKS_FACTORY_ROOT": str(self.repo), answer.ENV: shlex.join(head), "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"},
                "workflows": {"autoResumeOnQuotaReset": False}, "aliases": place.group_presets()}

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
        self.assertEqual(self.layer(argv), self.factory_layer())
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

    def test_test_cmd_running_the_checkout_reaches_archon(self):
        """#678: test_cmd の形はメイングラフの頭のノード testcmd が確かめる。殻は対象の手元を絶対パスで指す test_cmd も照らさずに Archon
        へ渡し、確かめの部品も持たない"""
        self.commit_target()
        runner = self.target / "run-tests"
        done = self.launch("workflow", "run", "works-factory-line", "--input", "request=x", "--input", f"test_cmd={runner} -q")
        self.assertIn(f"test_cmd={runner} -q", self.reached(done)["argv"])
        self.assertNotIn("test_cmd）", done.stderr)
        self.assertFalse((launcher.LIB / "testcmd_check.py").exists())

    def test_flag_values_reads_both_forms_in_order(self):
        self.assertEqual(launcher.flag_values(["--input", "test_cmd=a b", "--input=test_cmd=c", "--input", "request=x"], "--input"),
                         ["test_cmd=a b", "test_cmd=c", "request=x"])
        self.assertEqual(launcher.flag_values(["--input", "--input", "x"], "--input"), ["--input"], "値に取った字は旗として読まない")

    def test_user_workflow_source_is_refused(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--workflow-source", str(self.tmp)))
        self.assertIn("--workflow-source", err)

    def test_users_run_config_is_merged_under_the_factory_groups(self):
        """利用者の --config は殻の層に合わせて 1 つで渡る: env などは効き、同じ名の群の別名は工場の値に替わる。相対のパスは対象から引く。
        合わせた物（env の秘密が入りうる）は取り置き cache に置かず対象の家に置き、工場の値だけの層は cache に置く"""
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
                factory = self.factory_layer()
                self.assertEqual(self.layer(argv), {**factory, "env": {"MINE": "1", **factory["env"]}})
                self.assertIn(group, done.stderr)
                self.assertEqual(argv[11:], ["works-factory-line", "--input", "request=x"])
        with self.subTest("利用者の --config が無ければ工場の値だけの層を cache に置く"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line"))["argv"]
            self.assertTrue(pathlib.Path(argv[argv.index("--config") + 1]).is_relative_to(self.cache_home))
        cached = [json.loads(p.read_text(encoding="utf-8")) for p in self.cache_home.rglob("run-config/*.json")]
        self.assertEqual([layer for layer in cached if layer["env"] == self.factory_layer()["env"]], [self.factory_layer()])
        with self.subTest("読めない --config は起こさずに止める"):
            self.assertIn("none.yaml", self.stopped(self.launch("workflow", "run", "works-factory-line", "--config", "none.yaml")))

    def test_adopt_gets_the_run_config_without_groups(self):
        """--adopt は記録した AI の設定を受け継ぐ。Archon は aliases を持つ --config の層をその時に拒むので、殻は群の別名を除いた層を渡す。
        利用者の --config はその層に合わせる"""
        if shutil.which("bun") is None:
            self.skipTest("bun が無い（利用者の --config は Archon と同じ Bun.YAML.parse で読む）")
        self.bun.write_text(read_with_real_bun(shutil.which("bun")), encoding="utf-8")
        (self.target / "mine.yaml").write_text("env:\n  MINE: '1'\n", encoding="utf-8")
        factory = {k: v for k, v in self.factory_layer().items() if k != "aliases"}
        factory["env"] = {k: v for k, v in factory["env"].items() if k != "CLAUDE_CODE_PROMPT_CACHE_TTL"}
        for args, rest, layer in ((["--adopt", "run-1"], ["--adopt", "run-1"], factory),
                                  (["--adopt=run-1", "--config", "mine.yaml"], ["--adopt=run-1"],
                                   {**factory, "env": {"MINE": "1", **factory["env"]}})):
            with self.subTest(args=args):
                argv = self.reached(self.launch("workflow", "run", "works-factory-line", *args))["argv"]
                self.assertEqual(argv[3:9], ["workflow", "run", "--cwd", str(self.target), "--workflow-source", argv[8]])
                self.assertEqual(argv[9], "--config")
                self.assertEqual(self.layer(argv), layer)
                self.assertEqual(argv[11:], ["works-factory-line", *rest])

    def test_run_layer_carries_the_prompt_cache_ttl(self):
        """役の claude の会話のキャッシュの寿命の既定（5 分）は、新しい run の設定の層の env で運ぶ（Archon は起動の最初に CLAUDE_CODE_* を消すので、
        子の env に置いても役に届かない）。誰かが寿命を選んでいれば工場は載せない: 利用者の shell の env・利用者の --config の env:・
        対象の .archon/config.yaml の env:。--adopt の起動では、その選びを殻が見られないので載せない"""
        name = "CLAUDE_CODE_PROMPT_CACHE_TTL"
        real = shutil.which("bun")

        def env_of(*args, **env) -> dict:
            return self.layer(self.reached(self.launch("workflow", "run", "works-factory-line", *args, **env))["argv"])["env"]

        def repo_config(text):
            (self.target / ".archon").mkdir(exist_ok=True)
            (self.target / ".archon" / "config.yaml").write_text(text, encoding="utf-8")

        with self.subTest("選びが無ければ 5 分（対象に .archon/config.yaml が無ければ、殻は bun も起こさない）"):
            self.assertEqual(env_of()[name], "5m")
        with self.subTest("利用者の shell の寿命の選びは、Archon が消すのでそのまま運ぶ"):
            self.assertEqual(env_of(**{name: "1h"})[name], "1h")
        for chosen in launcher.CHOSEN_TTL_ENVS[1:]:
            with self.subTest(f"利用者の shell の {chosen} は Archon を通って届くので、工場は名を足さない"):
                self.assertNotIn(name, env_of(**{chosen: "1"}))
        with self.subTest("続ける命令（--resume）は層を足さない"):
            self.assertNotIn("--config", self.reached(self.launch("workflow", "run", "works-factory-line", "--resume"))["argv"])
        with self.subTest("--adopt は repo の選びを殻が見られないので、名を載せない（repo の config.yaml があっても読まない）"):
            repo_config("env:\n  MINE: '1'\n")
            for args in (["--adopt", "run-1"], ["--adopt=run-1"]):
                self.assertNotIn(name, env_of(*args))
                self.assertNotIn(name, env_of(*args, **{name: "1h"}))
            (self.target / ".archon" / "config.yaml").unlink()
        if real is None:
            self.skipTest("bun が無い（利用者の --config と対象の .archon/config.yaml は Archon と同じ Bun.YAML.parse で読む）")
        self.bun.write_text(read_with_real_bun(real), encoding="utf-8")
        (self.target / "mine.yaml").write_text("env:\n  MINE: '1'\n", encoding="utf-8")
        (self.target / "chosen.yaml").write_text("env:\n  ENABLE_PROMPT_CACHING_1H: '1'\n", encoding="utf-8")
        (self.target / "named.yaml").write_text(f"env:\n  {name}: 1h\n", encoding="utf-8")
        with self.subTest("利用者の --config の env: に寿命の選びが無ければ 5 分"):
            self.assertEqual(env_of("--config", "mine.yaml")[name], "5m")
        with self.subTest("利用者の --config の env: に ENABLE_PROMPT_CACHING_1H が在れば、工場は名を足さない"):
            got = env_of("--config", "chosen.yaml")
            self.assertNotIn(name, got)
            self.assertEqual(got["ENABLE_PROMPT_CACHING_1H"], "1")
        with self.subTest("利用者の --config の env: の寿命はそのまま運ぶ。利用者の shell の寿命では上書きしない"):
            self.assertEqual(env_of("--config", "named.yaml", **{name: "5m"})[name], "1h")
        for text, why in ((f"env:\n  {name}: 1h\n", "寿命の名"), ("env:\n  ENABLE_PROMPT_CACHING_1H: '1'\n", "ENABLE_PROMPT_CACHING_1H")):
            with self.subTest(f"対象の .archon/config.yaml の env: の {why}は、工場の 5 分で潰さない"):
                repo_config(text)
                got = env_of()
                self.assertNotIn(name, got)
                self.assertEqual(self.layer(self.reached(self.launch("workflow", "run", "works-factory-line"))["argv"]), {
                    **self.factory_layer(), "env": {k: v for k, v in self.factory_layer()["env"].items() if k != name}})
        for text in ("", "env:\n  MINE: '1'\n", "assistant: claude\n", "env: {}\n"):
            with self.subTest(f"対象の .archon/config.yaml に寿命の選びが無ければ 5 分: {text!r}"):
                repo_config(text)
                self.assertEqual(env_of()[name], "5m")
        with self.subTest("対象の .archon/config.yaml の選びは、利用者の shell の寿命にも勝つ（Archon が重ねるのは run の層より下）"):
            repo_config(f"env:\n  {name}: 1h\n")
            self.assertNotIn(name, env_of(**{name: "5m"}))
        with self.subTest("対象の .archon/config.yaml が読めなければ名を足さず、その訳を 1 行で言う"):
            repo_config("env: [unclosed\n")
            done = self.launch("workflow", "run", "works-factory-line")
            self.assertNotIn(name, self.layer(self.reached(done)["argv"])["env"])
            said = [line for line in done.stderr.splitlines() if ".archon/config.yaml" in line]
            self.assertEqual(len(said), 1, done.stderr)
            self.assertIn("読めない", said[0])

    def test_unknown_group_in_model_is_refused_with_the_known_groups(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--model", "@wf-judge-cor=haiku"))
        self.assertIn("@wf-judge-cor", err)
        for name in launchgroups.GROUPS:
            self.assertIn(name, err)
        with self.subTest("表に在る群と、工場の接頭辞でない名は通す"):
            argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--model=@wf-judge-core=haiku",
                                            "--model", "large=opus"))["argv"]
            self.assertEqual(argv[-3:], ["--model=@wf-judge-core=haiku", "--model", "large=opus"])

    def test_old_design_only_input_is_refused_with_the_new_name(self):
        """#827: 対話モードの入力は design_only から design_talk に名が替わった。古い名は Archon を起こさずに止め、新しい名を案内する"""
        for workflow in ("works-factory-line", "works-factory-chain"):
            for args in (["--input", "design_only=true"], ["--input=design_only=true"]):
                with self.subTest(workflow=workflow, args=args):
                    err = self.stopped(self.launch("workflow", "run", workflow, *args))
                    self.assertIn("design_only", err)
                    self.assertIn("--input design_talk=true", err)
        with self.subTest("新しい名と、名の替わっていない block の同じ名の入力は通す"):
            self.reached(self.launch("workflow", "run", "works-factory-line", "--input", "design_talk=true"))
            self.reached(self.launch("workflow", "run", "works-factory-judge", "--input", "design_only=true"))

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
        self.assertEqual(env[place.PROVIDER_ENV], "claude")
        self.assertNotIn("WORKS_FACTORY_ROOT", set(env), "run のノードへは --config の層で渡す")

    def test_continuing_commands_keep_the_root_for_runs_sealed_without_it(self):
        """#679 より前に始めた run の封じた層には WORKS_FACTORY_ROOT が無い。前の run を続ける命令の時だけ子の環境に置き、そうした run の
        script ノードも lib/ を見つける（層を持つ run では層の値が勝つ）。新しい run・run を走らせない命令には置かない"""
        continuing = [["workflow", verb, "run-1"] for verb in sorted(launcher.RESUMING | launcher.CONTINUING)]
        for args in [*continuing, ["workflow", "run", "works-factory-line", "--resume"]]:
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, WORKS_FACTORY_HOME=str(self.tmp / "home-of" / args[1])))["env"]
                self.assertEqual(env["WORKS_FACTORY_ROOT"], str(self.repo))
        for args in (["workflow", "run", "works-factory-line"], ["workflow", "status"]):
            with self.subTest(args=args):
                self.assertNotIn("WORKS_FACTORY_ROOT", self.reached(self.launch(*args))["env"])

    def test_factory_writes_nothing_in_either_archon_home(self):
        """工場の値は run の層と環境変数で渡し、工場の Archon の家にも利用者の ~/.archon にも書かない"""
        users = put(self.home / ".archon" / "config.yaml", "workflows:\n  autoResumeOnQuotaReset: true\n")
        before = users.read_bytes()
        archon_home = pathlib.Path(self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]["ARCHON_HOME"])
        self.assertNotEqual(archon_home.resolve(), (self.home / ".archon").resolve())
        self.assertFalse((archon_home / "config.yaml").exists())
        self.assertEqual(users.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in (self.home / ".archon").iterdir()), ["config.yaml"])

    def test_claude_concurrency_cap_reaches_archon_home_only_when_asked(self):
        """WORKS_FACTORY_CLAUDE_CONCURRENCY を渡した時だけ、隔離した Archon の家の config.yaml の concurrency.providers.claude に上限が届く
        （越える分を待たせるのは Archon。持ち主の決め provider-cap-on-ask）。利用者の ~/.archon には書かない。一度も渡さなければ何も書かない。
        書くのは run を走らせる命令だけ"""
        users = put(self.home / ".archon" / "config.yaml", "workflows:\n  autoResumeOnQuotaReset: true\n")
        before = users.read_bytes()
        run = ("workflow", "run", "works-factory-line")
        archon_home = pathlib.Path(self.reached(self.launch(*run))["env"]["ARCHON_HOME"])
        self.assertFalse((archon_home / "config.yaml").exists())
        done = self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="1")
        self.assertEqual(pathlib.Path(self.reached(done)["env"]["ARCHON_HOME"]), archon_home)
        self.assertEqual((archon_home / "config.yaml").read_text(encoding="utf-8"), "concurrency:\n  providers:\n    claude: 1\n")
        self.assertEqual(users.read_bytes(), before)
        with self.subTest("続ける命令にも届く"):
            self.reached(self.launch("workflow", "resume", "run-1", WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
            self.assertIn("    claude: 2\n", (archon_home / "config.yaml").read_text(encoding="utf-8"))
        with self.subTest("実行しない命令は書かない"):
            (archon_home / "config.yaml").unlink()
            self.reached(self.launch("workflow", "list", WORKS_FACTORY_CLAUDE_CONCURRENCY="1"))
            self.assertFalse((archon_home / "config.yaml").exists())

    def test_claude_concurrency_cap_touches_only_its_own_key(self):
        """上限の鍵だけを足すか書き換え、ほかの鍵・コメント・並びを残す。既に別の値なら渡した値に書き換わる"""
        run = ("workflow", "run", "works-factory-line")
        archon_home = pathlib.Path(self.reached(self.launch(*run))["env"]["ARCHON_HOME"])
        config = archon_home / "config.yaml"
        mine = "# 利用者の設定\nassistant: claude\nmodels:\n  tiers:\n    fast: haiku\nconcurrency:\n  maxConversations: 4\n# 末尾のコメント\n"
        put(config, mine)
        self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
        added = config.read_text(encoding="utf-8")
        self.assertEqual(added, mine.replace("  maxConversations: 4\n", "  maxConversations: 4\n  providers:\n    claude: 2\n"))
        with self.subTest("別の値は渡した値に書き換わる"):
            self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="3"))
            self.assertEqual(config.read_text(encoding="utf-8"), added.replace("claude: 2", "claude: 3"))
        with self.subTest("providers の中のほかの provider も残る"):
            put(config, "concurrency:\n  providers:\n    other: 5\n")
            self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
            self.assertEqual(config.read_text(encoding="utf-8"), "concurrency:\n  providers:\n    other: 5\n    claude: 2\n")
        with self.subTest("鍵が値を持つ形（flow）なら、書き換えずに止める"):
            put(config, "concurrency: {}\n")
            self.assertIn("config.yaml", self.stopped(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2")))
            self.assertEqual(config.read_text(encoding="utf-8"), "concurrency: {}\n")

    def test_launch_without_the_variable_leaves_the_cap_and_says_it(self):
        """変数を渡さない起動（続きの命令も）は config.yaml に何もしない（バイト単位で同じ）。上限の鍵が在れば、標準エラーに効いている値を 1 行出す"""
        run = ("workflow", "run", "works-factory-line")
        archon_home = pathlib.Path(self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))["env"]["ARCHON_HOME"])
        config = archon_home / "config.yaml"
        written = config.read_bytes()
        for args in (run, ("workflow", "resume", "run-1"), ("workflow", "approve", "run-1")):
            with self.subTest(args=args):
                done = self.launch(*args)
                self.reached(done)
                self.assertEqual(config.read_bytes(), written)
                self.assertIn(f"claude の同時数の上限 2 が効いている（{config}）", done.stderr)
        with self.subTest("空の値は渡していないのと同じ"):
            done = self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="")
            self.reached(done)
            self.assertEqual(config.read_bytes(), written)
        with self.subTest("上限の鍵が無ければ何も言わない"):
            config.unlink()
            self.assertNotIn("同時数の上限", self.launch(*run).stderr)

    def cap_config(self, text: bytes) -> pathlib.Path:
        """上限を一度も渡していない置き場の config.yaml に text を置く（Archon の命令が書いた形の再現）"""
        archon_home = pathlib.Path(self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]["ARCHON_HOME"])
        config = archon_home / "config.yaml"
        config.write_bytes(text)
        return config

    def test_claude_concurrency_cap_stops_on_a_flow_form_file_without_touching_it(self):
        """Archon の ai tier set などは config.yaml 全体を 1 行の形で書く。そこへ block の形を足すと Archon が読めなくなるので、書かずに
        Archon を起こさず止め、ファイルは 1 バイトも変わらない。止める文にパスと手で入れる形と変数を外す道が出る"""
        run = ("workflow", "run", "works-factory-line")
        for text in (b"{models: {tiers: {fast: haiku}}}\n", b"# user\n\n{assistant: claude}\n"):
            with self.subTest(text=text):
                config = self.cap_config(text)
                said = self.stopped(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
                self.assertIn(str(config), said)
                self.assertIn("concurrency: {providers: {claude: 2}}", said)
                self.assertIn("WORKS_FACTORY_CLAUDE_CONCURRENCY", said)
                self.assertEqual(config.read_bytes(), text)

    def test_launch_says_when_a_flow_form_file_may_hold_the_cap(self):
        """上限を書いた後に ai tier set などでファイルが 1 行の形になると、上限は中で効き続けるが殻は値を読めない。concurrency の字が在れば、
        効いている値の代わりに読めない旨の 1 行を標準エラーに出す。字が無ければ何も言わない"""
        run = ("workflow", "run", "works-factory-line")
        config = self.cap_config(b'{"concurrency":{"providers":{"claude":2}},"assistant":"claude"}\n')
        done = self.launch(*run)
        self.reached(done)
        self.assertIn(f"上限の設定が 1 行の形で在るかもしれず、殻は値を読めない（{config}）", done.stderr)
        self.assertNotIn("が効いている", done.stderr)
        config.write_bytes(b"{assistant: claude}\n")
        self.assertNotIn("上限の設定が", self.launch(*run).stderr)

    def test_claude_concurrency_cap_is_not_rewritten_when_the_value_is_the_same(self):
        """値が今と同じなら config.yaml に触らない（走り中の run が書きかけを読む余地を作らない）。違う時は置き換え、一時ファイルを残さない"""
        run = ("workflow", "run", "works-factory-line")
        config = self.cap_config(b"concurrency:\n  providers:\n    claude: 2\n")
        before = config.stat().st_mtime_ns
        self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
        self.assertEqual(config.stat().st_mtime_ns, before)
        self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="3"))
        self.assertEqual(config.read_bytes(), b"concurrency:\n  providers:\n    claude: 3\n")
        self.assertEqual(sorted(p.name for p in config.parent.glob("config.yaml*")), ["config.yaml"])

    def test_claude_concurrency_cap_keeps_the_line_ending_of_the_file(self):
        """CRLF のファイルに書いても CRLF のまま（足した行も CRLF）。末尾に改行の無いファイルも同じ形で足す"""
        run = ("workflow", "run", "works-factory-line")
        config = self.cap_config(b"assistant: claude\r\nconcurrency:\r\n  maxConversations: 4")
        self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
        self.assertEqual(config.read_bytes(), b"assistant: claude\r\nconcurrency:\r\n  maxConversations: 4\r\n"
                                              b"  providers:\r\n    claude: 2\r\n")
        config.write_bytes(b"assistant: claude\r\n")
        self.reached(self.launch(*run, WORKS_FACTORY_CLAUDE_CONCURRENCY="2"))
        self.assertEqual(config.read_bytes(), b"assistant: claude\r\nconcurrency:\r\n  providers:\r\n    claude: 2\r\n")

    def test_claude_concurrency_cap_must_be_a_positive_integer(self):
        """1 以上の整数でない値は、Archon を起こさずに止める（Archon は上限が壊れていると provider の起動を拒むので、run の途中で落ちる前に言う）"""
        for bad in ("0", "-1", "two", "1.5", " "):
            with self.subTest(value=bad):
                said = self.stopped(self.launch("workflow", "run", "works-factory-line", WORKS_FACTORY_CLAUDE_CONCURRENCY=bad))
                self.assertIn("WORKS_FACTORY_CLAUDE_CONCURRENCY", said)

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
        self.assertIn(userenv.RECORD, set(env))
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
        readme = (pathlib.Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
        self.assertIn(launcher.TARGET_ENV_NOTICE, readme)
        self.assertNotIn("WORKS_FACTORY_TARGET_USER_ENV", readme)
        section = readme.split("### test_cmd and worktrees\n", 1)[1].split("\n#", 1)[0]
        for word in ("`setup`", ".review-checks.json", "`suite`", ".gitignore", "target with only `test_cmd`"):
            self.assertIn(word, section)

    def test_run_says_where_its_record_is_after_it_ends(self):
        """workflow run が終わったら、Archon の記録（その run の番号を持ち主にする run の置き場）の置き場を標準エラーに 1 行で告げる。
        命令は殻が入れ替わらず子で走らせるので、子の終了の値は殻の終了の値になる"""
        root = self.tmp / "runs" / "run-fake"
        done = self.launch("workflow", "run", "works-factory-line", FAKE_BUN_RUN_ROOT=str(root))
        self.reached(done)
        self.assertIn(f"{launcher.NAME}: 記録の置き場: {root}\n", done.stderr)
        reads = [json.loads(line) for line in pathlib.Path(f"{self.bun_log}.reads").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r[3:5] for r in reads], [["workflow", "runs"], ["workflow", "get"]])
        self.assertEqual(reads[1][5], "run-fake")
        self.assertEqual(reads[1][reads[1].index("--cwd") + 1], str(self.target))

    def test_record_place_of_a_paused_run_comes_from_the_project_root(self):
        """承認ノードで止まった run は終わりの記録が無い。run の行の output_root の下の artifacts/runs/<id> を告げる。どちらも無ければ読めない"""
        self.assertEqual(recordroot.root_of({"id": "r1", "output_root": "/h/ws/p", "terminal_record": None}), "/h/ws/p/artifacts/runs/r1")
        self.assertEqual(recordroot.root_of({"id": "r1", "output_root": "/h/ws/p", "terminal_record": {"artifacts": {"root": "/x/r1"}}}),
                         "/x/r1")
        self.assertIsNone(recordroot.root_of({"id": "r1", "terminal_record": None}))
        self.assertIsNone(recordroot.root_of("not a record"))

    def test_run_that_cannot_be_found_in_the_record_says_so(self):
        done = self.launch("workflow", "run", "works-factory-line")
        self.reached(done)
        self.assertIn(f"{launcher.NAME}: 記録の置き場を特定できない", done.stderr)

    def test_detached_run_and_other_commands_say_no_record_place(self):
        for args in (["workflow", "run", "works-factory-line", "--detach"], ["workflow", "approve", "run-1"]):
            with self.subTest(args=args):
                done = self.launch(*args, FAKE_BUN_RUN_ROOT=str(self.tmp / "x"))
                self.reached(done)
                self.assertNotIn("記録の置き場", done.stderr)

    def test_run_layer_carries_answer_head(self):
        """関所の答えの行の頭は家を名指して殻を通す respond。新しい run の層で渡り、利用者の値より殻の値"""
        chosen = self.tmp / "chosen-home"
        for user_value, home in (({}, self.default_home(self.target)),
                                 ({answer.ENV: "sh use.sh answer x", "WORKS_FACTORY_HOME": str(chosen)}, chosen)):
            with self.subTest(user=user_value):
                argv = self.reached(self.launch("workflow", "run", "works-factory-line", cwd=self.target / "sub",
                                                **user_value))["argv"]
                head = shlex.split(self.layer(argv)["env"][answer.ENV])
                self.assertEqual(head, ["env", f"WORKS_FACTORY_HOME={home}", str(self.repo / "bin" / "works-factory"),
                                        "workflow", "respond", "--cwd", os.path.realpath(self.target)])
                self.assertIn(shlex.join(["bin/works-factory", *head[3:-1]]), answer.HOLE)
                resume = shlex.split(answer.resume("RUN", env=self.layer(argv)["env"]))
                self.assertEqual(resume, [f"{auth_launch.ITEM_ENV}={answer.KEYCHAIN_HOLE}", *head[:4], "resume", *head[5:], "RUN"],
                                 "resume の行は同じ頭の respond を resume に替え、殻が認証に読む keychain の項目名を前に置く")

    def test_answer_line_reaches_the_run_home_from_another_shell(self):
        """一度だけ選んだ家（WORKS_FACTORY_HOME・XDG_STATE_HOME）で起こした run の答えの行は、その値の無いシェルで打っても同じ家に届く"""
        chosen = self.tmp / "chosen-home"
        for chooses, home in (({"WORKS_FACTORY_HOME": str(chosen)}, chosen),
                              ({"XDG_STATE_HOME": str(self.tmp / "state")},
                               self.tmp / "state" / "works-factory" / "targets" / short(self.target))):
            with self.subTest(chooses=chooses):
                got = self.reached(self.launch("workflow", "run", "works-factory-line", **chooses))
                self.assertEqual(got["env"]["HOME"], str(home / "home"))
                line = answer.line("run-1", "continue", "x", env=self.layer(got["argv"])["env"])
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

    def test_gh_shim_heads_the_path_of_script_nodes(self):
        """script のノード（archon-pr の publish も）が打つ gh は、利用者のログインを継ぐ口"""
        env = self.reached(self.launch("workflow", "status"))["env"]
        head = pathlib.Path(env["PATH"].split(os.pathsep)[0])
        self.assertEqual(pathlib.Path(shutil.which("gh", path=env["PATH"])).parent, head)
        self.assertTrue(head.is_relative_to(self.default_home(self.target)), head)
        shim = (head / "gh").read_text(encoding="utf-8")
        self.assertIn(str(self.gh), shim)
        self.assertIn(str(self.home), shim)

    def test_role_path_starts_with_read_only_gh(self):
        """役が打つ gh は読むだけの口 works-gh（役の claude を起こす包みが PATH の頭に足す）: 書く命令とトークンの読み出しを拒み、
        読む命令は利用者の gh を継ぐ口へ渡す"""
        gh_log = self.tmp / "gh.txt"
        put(self.gh, f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{gh_log}"\n')
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        argv = self.fence_of(env)
        heads = [argv[i + 1] for i, a in enumerate(argv) if a == "--path-head"]
        self.assertEqual(heads, [str(self.repo / "bin" / "_lib" / "no-post-bin")])
        env = {**env, "PATH": os.pathsep.join([*heads, env["PATH"]])}
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

    def test_target_commands_hit_the_read_only_gh(self):
        """script のノードが起こす対象のコマンド（AI が書いた試験のコードも走る。環境は tree_run.outside_env）が打つ gh は、PATH の頭の
        書ける口でなく読むだけの口 works-gh: 書く命令を拒み、読む命令は利用者の gh を継ぐ口へ渡す"""
        gh_log = self.tmp / "gh.txt"
        put(self.gh, f'#!/bin/sh\nprintf \'%s\\n\' "$*" >> "{gh_log}"\n')
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        self.assertEqual(env[userenv.READ_GH_ENV], str(self.repo / "bin" / "_lib" / "no-post-bin"))
        probe = ("import os, subprocess, sys\n"
                 f"sys.path.append({str(self.repo / 'lib')!r})\n"
                 "import tree_run\n"
                 "env = tree_run.outside_env(os.environ)\n"
                 "for args in (['pr', 'create', '-R', 'o/r'], ['pr', 'view', '1', '-R', 'o/r']):\n"
                 "    print(subprocess.run(['gh', *args], env=env, capture_output=True).returncode)\n")
        done = subprocess.run([sys.executable, "-c", probe], env={**env, userenv.RAN_DIR_ENV: str(self.tmp / "ran")},
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split(), ["2", "0"], "書く命令は読むだけの口が拒み、読む命令は通る")
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
        """環境変数だけで gh にログインする利用者: run の中の gh（script のノードが打つ口。役の読むだけの口もこの口へ渡す）が、
        利用者の gh に GH_TOKEN 付きで届く（#132）"""
        log = self.token_probe()
        for name in ("GH_TOKEN", "GITHUB_TOKEN"):
            with self.subTest(name=name):
                env = self.reached(self.launch("workflow", "status", **{name: GH_FAKE}))["env"]
                done = subprocess.run(["gh", "pr", "view", "1", "-R", "o/r"], env=env, capture_output=True, text=True,
                                      encoding="utf-8", timeout=60)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(log.read_text(encoding="utf-8").splitlines()[-1], "token-ok")

    def test_token_readout_is_refused_without_the_value(self):
        """役の gh（包みが PATH の頭に読むだけの口を足す）の auth token は拒まれ、トークンの値は出ない"""
        env = self.reached(self.launch("workflow", "status", GH_TOKEN=GH_FAKE))["env"]
        env = {**env, "PATH": os.pathsep.join([str(self.repo / "bin" / "_lib" / "no-post-bin"), env["PATH"]])}
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
        TDD の実行器の取り置き〔次の run の試験の関門が走らせる〕・工場の checkout の根の全体〔根に置いた .py も次の起動の import に勝つ〕）は、
        禁じる一覧に入る"""
        env = self.reached(self.launch("workflow", "run", "works-factory-line"))["env"]
        argv = self.fence_of(env)
        own = {argv[i + 1] for i, a in enumerate(argv) if a == "--own"}
        home = self.default_home(self.target)
        self.assertEqual(own, {str(home / launcher.FENCE_DIR), str(home / launcher.HOST_GH_DIR),
                               str(self.cache_home / "works-factory"),
                               str(self.home / ".local" / "state" / "works-factory" / launcher.SUITE_KEEP),
                               str(self.repo),
                               sys.prefix, sys.base_prefix, os.path.realpath(self.fake / "claude")})

    def test_runner_keep_is_shared_across_targets_and_made_by_the_launch(self):
        """#516: TDD の実行器の取り置きは利用者ごとに 1 つで、対象をまたいで使い回す（持ち主の決め suite-by-ai）。既定の家では別の対象 2 つが
        同じ取り置き（対象ごとの家 targets/ の兄弟）を引き、家を選べばその下。殻が作って script のノードに渡す"""
        other = self.tmp / "other-target"
        other.mkdir()
        git(other, "init", "-q")
        default = self.home / ".local" / "state" / "works-factory" / launcher.SUITE_KEEP
        for cwd in (self.target, other):
            with self.subTest(target=str(cwd)):
                env = self.reached(self.launch("workflow", "run", "works-factory-line", cwd=cwd))["env"]
                self.assertEqual(env[launcher.SUITE_KEEP_ENV], str(default))
        self.assertTrue(default.is_dir())
        chosen = self.tmp / "chosen-home"
        env = self.reached(self.launch("workflow", "run", "works-factory-line", WORKS_FACTORY_HOME=str(chosen)))["env"]
        self.assertEqual(env[launcher.SUITE_KEEP_ENV], str(chosen / launcher.SUITE_KEEP))
        self.assertTrue((chosen / launcher.SUITE_KEEP).is_dir())

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

    # ---------------------------------------------------------------- 仕様駆動の道（docs/design/spec-driven.md の 2.6 の 2・6.7）
    SPEC_DESIGN = "# 設計書\n\n- 何の話か: 置き場。\n- 決めたこと: 1 つ読む。\n\n## 背景\n\n今はホーム。\n"

    def put_spec(self) -> dict:
        """対象に表と設計書を置き、部品ごとの記録（workflow get の形）を偽の bun が返す置き場に置く。返りは記録の置き場の env"""
        if str(self.repo / "lib") not in sys.path:
            sys.path.append(str(self.repo / "lib"))
        import spectable
        (self.target / "docs").mkdir(exist_ok=True)
        (self.target / "docs" / "d.md").write_text(self.SPEC_DESIGN, encoding="utf-8")
        (self.target / "t.yaml").write_text(
            "design: docs/d.md\npurpose: 置き場が思う所\nacceptance:\n  - {key: a1, when: 起こす, then: 置く}\nreviews:\n"
            + "".join(f"  - {{part: {p}, run: r{n}, findings: []}}\n" for n, p in enumerate(spectable.PARTS)), encoding="utf-8")
        reader = importlib.util.spec_from_file_location("spec_inputs", self.repo / "bin" / "_lib" / "spec-inputs.py")
        mod = importlib.util.module_from_spec(reader)
        reader.loader.exec_module(mod)
        built = mod.build(self.target, "t.yaml")
        records = self.tmp / "records"
        records.mkdir()
        for n, part in enumerate(spectable.PARTS):
            named = {k: spectable.input_text(v) for k, v in built["inputs"][part].items()}
            value, root = {"ok": True}, None
            if part == spectable.PLAN_REVIEW:
                named["proposal_file"] = f"/gone/spec-proposal-{built['proposal_sha256']}.md"
            if part == spectable.WORLD:   # 世界の解は依頼の行ごとに 1 行の行のファイルを返す（2.6 の 2 の f）
                root = str(records / "world-run")
                (records / "world-run").mkdir()
                (records / "world-run" / "world.jsonl").write_text("".join(
                    json.dumps({"finding": i, "where": r["where"], "versus": {"verdict": "same"}}, ensure_ascii=False) + "\n"
                    for i, r in enumerate(built["inputs"][part]["request"], 1)), encoding="utf-8")
                value["rows"] = {"type": "archon_artifact", "run_id": "w", "path": "world.jsonl"}
            (records / f"r{n}.json").write_text(json.dumps({
                "workflow_name": part, "status": "completed", "outcome": "succeeded", "metadata": {"inputs": named},
                "terminal_record": {"returns": {"availability": "available", "value": value}, "artifacts": {"root": root}}},
                ensure_ascii=False), encoding="utf-8")
        put(self.fake / "bun", "#!/usr/bin/env python3\nimport json, os, pathlib, sys\n"
            "if 'get' in sys.argv:\n"
            "    p = pathlib.Path(os.environ['FAKE_RECORDS']) / (sys.argv[sys.argv.index('get') + 1] + '.json')\n"
            "    print(p.read_text() if p.is_file() else json.dumps({'ok': False, 'error': 'not_found'}))\n"
            "    sys.exit(0 if p.is_file() else 1)\n" + FAKE_BUN.split("\n", 2)[2])
        # 偽の uv は、この試験の Python（PyYAML を持つ）で script を回す（本物の uv は script の宣言から PyYAML を入れる）
        put(self.fake / "uv", "#!/usr/bin/env python3\nimport os, sys\nargs = sys.argv[1:]\n"
            f"assert args[:2] == ['run', '--script'], args\nos.execv({sys.executable!r}, [{sys.executable!r}, *args[2:]])\n")
        return {"FAKE_RECORDS": str(records)}

    def test_runs_without_a_spec_table_read_no_table_and_need_no_uv(self):
        """表を名指さない起動は表も審査の記録も読まず、uv も起こさない（PATH に uv が無くても今どおり起こす）。run の層も今のまま"""
        argv = self.reached(self.launch("workflow", "run", "works-factory-line", "--input", "request=x"))["argv"]
        self.assertEqual(self.layer(argv), self.factory_layer())

    def test_spec_table_without_uv_stops_before_archon(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--input", "spec_table=t.yaml"))
        self.assertIn("uv が要る", err)

    def test_spec_table_records_reach_the_run_layer(self):
        """表を名指す起動は、審査の記録 5 件を照らした結果のファイルを run の設定の層の env で渡す（resume しても同じ値）。block の
        単独の run（table）も同じ"""
        env = self.put_spec()
        for workflow, name in (("works-factory-line", "spec_table"), ("works-factory-spec-driven", "table")):
            with self.subTest(workflow):
                got = self.reached(self.launch("workflow", "run", workflow, "--input", "mode=entry", "--input", f"{name}=t.yaml", **env))
                layer = self.layer(got["argv"])
                result = json.loads(pathlib.Path(layer["env"][specreviews.RESULT_ENV]).read_text(encoding="utf-8"))
                self.assertEqual([r["ok"] for r in result["rows"]], [True] * 5, result)
                self.assertEqual({k: v for k, v in layer["env"].items() if k != specreviews.RESULT_ENV}, self.factory_layer()["env"])

    def test_spec_records_that_do_not_match_stop_before_archon(self):
        env = self.put_spec()
        (pathlib.Path(env["FAKE_RECORDS"]) / "r2.json").unlink()
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", "--input", "spec_table=t.yaml", **env))
        self.assertIn("照らしに合わない", err)
        self.assertIn("a: run r2 の記録が無い", err)

    def test_missing_auth_stops_before_archon(self):
        err = self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None))
        self.assertIn("認証が無い", err)

    def test_reading_commands_reach_archon_without_auth(self):
        """工程を走らせない命令（run を読む・一覧を見る）は認証を通さない。認証の無い利用者も bin/apply で run を読める"""
        for args in (["workflow", "get", "run-1"], ["workflow", "status"], ["validate", "workflows"], ["version"], ["help"]):
            with self.subTest(args=args):
                env = self.reached(self.launch(*args, ANTHROPIC_API_KEY=None))["env"]
                self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", list(env))

    def test_cancel_reads_the_run_then_passes_the_cancel_to_archon(self):
        """workflow cancel は run と子の run を読んでから同じ引数で Archon を起こし、その終了の値で抜ける（後に残った木を止める。
        bin/_lib/runstop.py。本物の Archon での止めは tests/bin/test_runstop.py）。殻は本物の ps の上で止めるので、cancel に渡る
        run の id は回すたびに違う（fakelaunch.unique_run_id）"""
        entry = str(self.source / ENTRY)
        cancelled = []
        for n in range(2):
            run_id = unique_run_id()
            calls = self.tmp / f"bun-calls-{n}.jsonl"
            put(self.fake / "bun", "#!/usr/bin/env python3\nimport json, os, sys\n"
                f"open({str(calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\nsys.exit(3 if 'cancel' in sys.argv else 0)\n")
            done = self.launch("workflow", "cancel", run_id, "--json", "--cwd", str(self.target), ANTHROPIC_API_KEY=None)
            self.assertEqual(done.returncode, 3, done.stderr)
            got = [argv[argv.index(entry) + 1:] for argv in map(json.loads, calls.read_text(encoding="utf-8").splitlines())]
            self.assertEqual(got, [["workflow", "get", run_id, "--json", "--cwd", str(self.target)],
                                   ["workflow", "runs", "--all", "--limit", "1000", "--json", "--cwd", str(self.target)],
                                   ["workflow", "cancel", run_id, "--json", "--cwd", str(self.target)]])
            cancelled.append(got[-1][2])
        self.assertNotEqual(cancelled[0], cancelled[1])

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

    def test_managed_settings_folder_comes_from_the_env_and_the_default_stays(self):
        """会社が配る設定の置き場は WORKS_FACTORY_MANAGED_DIR で替えられ、その中の apiKeyHelper がキーになる。この口は殻の既定の道を
        変えない: 試験の子の環境が向ける空のフォルダでは、helper が無く、API キーの無い利用者は認証の案内で止まる（E14）"""
        managed = self.tmp / "managed"
        managed.mkdir()
        (managed / "managed-settings.json").write_text(json.dumps({"apiKeyHelper": "echo helper-made-key"}), encoding="utf-8")
        env = self.reached(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None,
                                       WORKS_FACTORY_MANAGED_DIR=str(managed)))["env"]
        self.assertEqual(env["ANTHROPIC_API_KEY"], "helper-made-key")
        self.assertIn("認証が無い", self.stopped(self.launch("workflow", "run", "works-factory-line", ANTHROPIC_API_KEY=None)))

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
    """#495: README の「Usage」が、依頼のファイルの形（例が入口の照らしを通る）・test_cmd・作業ツリーの起点を書き、殻の案内が
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
        [example] = [block.split("\n", 1)[1] for block in self.section("Request file").split("```")[1::2]
                     if block.startswith("json\n")]
        parts = carry.parts(json.loads(example))
        self.assertTrue(parts[carry.FINDINGS])
        self.assertEqual(entry.request_problems(parts[carry.FINDINGS]), [])

    def test_test_cmd_and_start_point_are_documented(self):
        testcmd_check = archon.src_module("line", "testcmd_check")   # 今の lib/testcmd_check.py の行き先（line の src。4.5-7）
        self.assertIn("「test_cmd and worktrees」", testcmd_check.HOW)
        test_cmd = self.section("test_cmd and worktrees")
        for word in ("--input test_cmd=", testcmd_check.ALLOW_ENV, "止める（test_cmd）", "注意（test_cmd）"):
            self.assertIn(word, test_cmd)
        start = self.section("Worktree start point")
        for flag in ("--from", "--from-branch", "--base", "--branch", "--no-worktree", "--adopt"):
            self.assertIn(f"`{flag}", start)


if __name__ == "__main__":
    unittest.main()
