"""起動の認証の起こし役（bin/_lib/auth_launch.py）の柵。

- 順の真ん中は claude_auth.auth_env を丸ごと呼ぶ（部品を並べ直すと claude_auth の試験は緑のままなので、ここで縛る）
- 名指し（WORKS_FACTORY_KEYCHAIN_ITEM）は受け継いだ認証より先に効き、取れなければ次へ進まない
- 項目の名を設定の置き場から導かない。名指しが無ければ Claude Code 自身の項目だけを読む（E14）
- トークンの出どころが無ければ止めずにホストのログインへ進み、子の CLAUDE_CONFIG_DIR だけを利用者の物に戻す（keychain の無い OS で
  claude /login しただけの人が動く。E14）。トークンが在る時は隔離した CLAUDE_CONFIG_DIR のまま
- python3 -I で起こした check は起こし役のフォルダ（試験の持つ写し）に __pycache__ を作らない（-I は PYTHONDONTWRITEBYTECODE を
  見ず、__pycache__ は .gitignore に隠れて git status に出ない）。共有の bin/_lib/ はどの試験も見ない（別の実行の残り物で揺れる）。
  試験自身の import の分は各試験の頭の sys.dont_write_bytecode に任せ、試験では縛らない
security は偽の runner に差し替え、本物の keychain には触らない。
"""
import os
import pathlib
import shutil
import subprocess
import sys
import types
import unittest
from unittest import mock

TESTS = pathlib.Path(__file__).resolve().parent
ROOT = TESTS.parents[1]
CORE = ROOT / "bin" / "_lib"
sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(TESTS))

import auth_launch  # noqa: E402
import claude_auth  # noqa: E402
import hermetic  # noqa: E402

TOKEN = "sk-ant-oat01-fake-for-test"


def keychain(items):
    """-s の名ごとに items の値を返す偽の security（呼ばれた名は calls に残る）"""
    calls = []

    def run(args, **kw):
        service = args[args.index("-s") + 1]
        calls.append(service)
        return types.SimpleNamespace(stdout=items.get(service, ""), returncode=0 if service in items else 44)
    run.calls = calls
    return run


class ResolveOrder(unittest.TestCase):
    def test_middle_stage_follows_the_copys_auth_env(self):
        """真ん中は写しの auth_env の結果にそのまま従う（番兵に差し替えると出どころの名と子に渡す値が変わる）"""
        seen = {}

        def sentinel(env, platform=None, runner=None, service=None):
            seen["env"] = env
            return dict(env, CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-sentinel"), "keychain(sentinel-svc)"
        with mock.patch.object(claude_auth, "auth_env", sentinel):
            got, name, why = auth_launch.resolve({}, "/u", "/u/.claude-p9", platform="darwin", runner=keychain({}))
        self.assertIsNone(why)
        self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-sentinel"})
        self.assertIn("sentinel-svc", name)
        self.assertEqual((seen["env"]["HOME"], seen["env"]["CLAUDE_CONFIG_DIR"]), ("/u", "/u/.claude-p9"))

    def test_back_stage_only_when_the_copy_adds_nothing(self):
        """写しの auth_env が足せなかった時だけ Claude Code 自身の項目を読む。足せた時はその項目を聞きもしない"""
        run = keychain({"Claude Code-credentials": '{"claudeAiOauth": {"accessToken": "%s"}}' % TOKEN})
        with mock.patch.object(claude_auth, "auth_env", lambda env, **kw: (dict(env), "keychain-miss(x)")):
            got, name, _ = auth_launch.resolve({}, "/u", "", platform="darwin", runner=run)
        self.assertEqual((got, name), ({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, "Claude Code の keychain の項目 Claude Code-credentials"))
        run2 = keychain({"Claude Code-credentials": TOKEN})
        with mock.patch.object(claude_auth, "auth_env",
                               lambda env, **kw: (dict(env, CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-m"), "keychain(m)")):
            auth_launch.resolve({}, "/u", "", platform="darwin", runner=run2)
        self.assertEqual(run2.calls, [])

    def test_middle_stage_reads_the_item_named_by_claude_keychain_service(self):
        """真ん中は CLAUDE_KEYCHAIN_SERVICE で名指した項目を読む"""
        run = keychain({"svc": TOKEN})
        got, name, why = auth_launch.resolve({"CLAUDE_KEYCHAIN_SERVICE": "svc"}, "/u", "", platform="darwin", runner=run)
        self.assertIsNone(why)
        self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertIn("svc", name)
        self.assertEqual(run.calls, ["svc"])

    def test_without_a_named_item_only_claude_codes_own_items_are_read(self):
        """名指しが無ければ設定の置き場から項目の名を導かず、Claude Code 自身の項目だけを読む（E14）"""
        for cfg in ("", "/u/.claude-p3"):
            with self.subTest(cfg=cfg):
                run = keychain({})
                auth_launch.resolve({}, "/u", cfg, platform="darwin", runner=run)
                self.assertEqual(run.calls, auth_launch.claude_code_items(cfg))

    def test_no_token_source_goes_on_with_the_host_login(self):
        """トークンの出どころが無ければ止めずに、子を利用者の保存済みのログイン（隔離の前の CLAUDE_CONFIG_DIR、無ければ
        <HOME>/.claude）に任せる。macOS 以外は keychain を読まない"""
        for platform in ("linux", "win32", "darwin"):
            for cfg, want in (("", "/u/.claude"), ("/u/cfg", "/u/cfg")):
                with self.subTest(platform=platform, cfg=cfg):
                    run = keychain({})
                    got, name, why = auth_launch.resolve({}, "/u", cfg, platform=platform, runner=run)
                    self.assertIsNone(why)
                    self.assertEqual(got, {"CLAUDE_CONFIG_DIR": want})
                    self.assertEqual(name, "host-login（%s）" % want)
                    if platform != "darwin":
                        self.assertEqual(run.calls, [])

    def test_named_item_beats_inherited_auth(self):
        """WORKS_FACTORY_KEYCHAIN_ITEM は受け継いだ CLAUDE_CODE_OAUTH_TOKEN・ANTHROPIC_API_KEY より先に効く"""
        env = {"WORKS_FACTORY_KEYCHAIN_ITEM": "named", "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-env", "ANTHROPIC_API_KEY": "k"}
        run = keychain({"named": TOKEN})
        got, name, why = auth_launch.resolve(env, "/u", "", platform="darwin", runner=run)
        self.assertIsNone(why)
        self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertIn("WORKS_FACTORY_KEYCHAIN_ITEM", name)
        self.assertEqual(run.calls, ["named"])

    def test_named_item_empty_or_malformed_stops(self):
        """名指しの項目が空・壊れた値なら次の段（受け継いだ認証・CLAUDE_KEYCHAIN_SERVICE の項目・Claude Code の項目）へ進まずに止まる"""
        for value in ("", "not-a-token"):
            with self.subTest(value=value):
                run = keychain({"named": value, "svc": TOKEN, "Claude Code-credentials": TOKEN})
                got, _name, why = auth_launch.resolve({"WORKS_FACTORY_KEYCHAIN_ITEM": "named", "CLAUDE_CODE_OAUTH_TOKEN": TOKEN,
                                                       "CLAUDE_KEYCHAIN_SERVICE": "svc"},
                                                      "/u", "", platform="darwin", runner=run)
                self.assertIsNone(got)
                self.assertIn("named", why)
                self.assertEqual(run.calls, ["named"])

    def test_user_runner_reads_keychain_with_users_home(self):
        """security はログイン keychain を $HOME 基準で探すので、隔離前の利用者の HOME で起こす"""
        with mock.patch.object(auth_launch.subprocess, "run") as run:
            auth_launch.user_runner("/users-home")(["security"], capture_output=True)
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/users-home")


class ChildEnv(unittest.TestCase):
    ISOLATED = {"HOME": "/run/home", "CLAUDE_CONFIG_DIR": "/run/claude-config"}

    def test_host_login_hands_the_child_the_users_config_dir(self):
        """ホストのログインの時だけ、子の CLAUDE_CONFIG_DIR は利用者の元の置き場（保存済みのログインが在る所）。HOME は隔離のまま"""
        got, _name, _why = auth_launch.resolve({}, "/u", "/u/cfg", platform="linux", runner=keychain({}))
        self.assertEqual(auth_launch.child_env(self.ISOLATED, got, False), {"HOME": "/run/home", "CLAUDE_CONFIG_DIR": "/u/cfg"})

    def test_a_token_keeps_the_isolated_config_dir(self):
        for env in ({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, {"ANTHROPIC_API_KEY": "k"}):
            with self.subTest(env=list(env)):
                got, _name, why = auth_launch.resolve(env, "/u", "/u/cfg", platform="linux", runner=keychain({}))
                self.assertIsNone(why)
                self.assertEqual(auth_launch.child_env(self.ISOLATED, got, False)["CLAUDE_CONFIG_DIR"], "/run/claude-config")

    def test_named_drops_credentials_that_outrank_the_token(self):
        """名指しで決めた時は、Claude Code が CLAUDE_CODE_OAUTH_TOKEN より先に使う資格（claude_auth の INHERITED と FOUNDRY の旗）を外す"""
        env = {"HOME": "/iso", "ANTHROPIC_API_KEY": "k", "ANTHROPIC_AUTH_TOKEN": "t", "CLAUDE_CODE_USE_FOUNDRY": "1",
               "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_OAUTH_TOKEN": "old"}
        self.assertEqual(auth_launch.child_env(env, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, True),
                         {"HOME": "/iso", "CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertEqual(auth_launch.child_env(env, {"ANTHROPIC_API_KEY": "k"}, False), env)


class IsolatedLaunch(unittest.TestCase):
    def fake_security(self, tmp, service):
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "security").write_text(
            '#!/bin/sh\necho "$HOME" > "$0.home"\nprev=\nfor a in "$@"; do\n'
            f'  if [ "$prev" = -s ] && [ "$a" = "{service}" ]; then echo {TOKEN}; exit 0; fi\n'
            '  prev=$a\ndone\nexit 44\n')
        (bin_dir / "security").chmod(0o755)
        return bin_dir

    @unittest.skipUnless(sys.platform == "darwin", "SKIP macos: keychain の段は macOS だけ")
    def test_exec_hands_the_named_token_only_to_the_child(self):
        """exec は同じプロセスを実行ファイルに置き換え、子の環境にだけ名指しのトークンを置く（上位の資格は外し、隔離した HOME は
        そのまま）。起こし役自身は値を出さず、security は利用者の HOME で起こす"""
        tmp = hermetic.tmpdir(self)
        bin_dir = self.fake_security(tmp, "named")
        probe = ("import os, json; print(json.dumps({k: os.environ.get(k) == %r if k == 'CLAUDE_CODE_OAUTH_TOKEN' "
                 "else os.environ.get(k) for k in ('CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_API_KEY', 'HOME')}))" % TOKEN)
        env = hermetic.child_env(HOME=str(tmp / "iso"), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                                 WORKS_FACTORY_KEYCHAIN_ITEM="named", ANTHROPIC_API_KEY="k", CLAUDE_CODE_OAUTH_TOKEN="inherited")
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--user-home", str(tmp / "user"),
                            "--", sys.executable, "-I", "-c", probe], env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '{"CLAUDE_CODE_OAUTH_TOKEN": true, "ANTHROPIC_API_KEY": null, "HOME": "%s"}'
                         % (tmp / "iso"))
        self.assertEqual((bin_dir / "security.home").read_text().strip(), str(tmp / "user"))

    def test_exec_stops_with_howto_and_does_not_start_the_child(self):
        """名指しの項目を読めなければ、子を起こさず 1 行の案内（呼び手の名つき）で 2"""
        tmp = hermetic.tmpdir(self)
        bin_dir = self.fake_security(tmp, "nothing-here")
        env = hermetic.child_env(HOME=str(tmp), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                                 WORKS_FACTORY_KEYCHAIN_ITEM="named")
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--for", "bin/start",
                            "--user-home", str(tmp), "--", sys.executable, "-c", "print('started')"],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("bin/start: " + auth_launch.HOWTO), r.stderr)

    def test_exec_without_a_token_starts_the_child_on_the_host_login(self):
        """トークンの出どころが無ければ子を起こし、子の CLAUDE_CONFIG_DIR は --user-config。静かな落ち方の注意を標準エラーに出す"""
        tmp = hermetic.tmpdir(self)
        bin_dir = self.fake_security(tmp, "nothing-here")
        env = hermetic.child_env(HOME=str(tmp / "iso"), CLAUDE_CONFIG_DIR=str(tmp / "iso-config"),
                                 PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--for", "bin/start",
                            "--user-home", str(tmp / "user"), "--user-config", str(tmp / "user-config"), "--",
                            sys.executable, "-I", "-c", "import os; print(os.environ['CLAUDE_CONFIG_DIR'], os.environ['HOME'])"],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), [str(tmp / "user-config"), str(tmp / "iso")])
        self.assertEqual(r.stderr.strip(), "bin/start: " + claude_auth.QUIET_FAILURE_NOTE)

    def test_shells_do_not_read_the_keychain_themselves(self):
        """認証の順と keychain の読み出しは起こし役だけが持つ。入口と隔離に書き戻したら赤（語で見る）"""
        shells = [p for p in (ROOT / "bin").iterdir() if p.is_file()] + [CORE / "isolate.py"]
        for sh in sorted(shells):
            body = sh.read_text(encoding="utf-8")
            for word in ("security find-generic-password", 'CLAUDE_CODE_OAUTH_TOKEN="$('):
                with self.subTest(sh=sh.name, word=word):
                    self.assertNotIn(word, body)

    def test_check_prints_only_the_name_and_leaves_no_pycache(self):
        """python3 -I で check を起こす（殻と同じ起こし方）。標準出力は出どころの名だけでトークンを出さず、
        終わった後に起こし役のフォルダの写しの下に __pycache__ が無い"""
        tmp = hermetic.tmpdir(self)
        # 共有の作業ツリーを見ると別の実行が残した __pycache__ を拾うので、この試験だけが持つ写しで起こす。
        # symlink は不可（auth_launch.py は __file__.resolve() の親を sys.path に入れ、本物の CORE に書く）
        core = tmp / "core"
        shutil.copytree(CORE, core, ignore=shutil.ignore_patterns("__pycache__"))
        home = tmp / "home"
        home.mkdir()
        env = hermetic.child_env(CLAUDE_CODE_OAUTH_TOKEN=TOKEN, HOME=str(home))
        r = subprocess.run([sys.executable, "-I", str(core / "auth_launch.py"), "check", "--user-home", str(home)],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "CLAUDE_CODE_OAUTH_TOKEN"), r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(list(core.rglob("__pycache__")), [])


if __name__ == "__main__":
    unittest.main()
