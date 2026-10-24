"""起動の認証の起こし役（bin/_lib/auth_launch.py）の柵。

- 順の真ん中は claude_auth.auth_env を丸ごと呼ぶ（部品を並べ直すと claude_auth の試験は緑のままなので、ここで縛る）
- 名指し（WORKS_FACTORY_KEYCHAIN_ITEM）は受け継いだ認証より先に効き、取れなければ次へ進まない
- 項目の名を設定の置き場から導かない。名指しが無ければ Claude Code 自身の項目だけを読む（E14）
- macOS 以外では利用者の <CLAUDE_CONFIG_DIR>/.credentials.json のトークンを子に渡す（keychain の無い OS で claude /login しただけの人が
  動く。E14）。どの道でも子の CLAUDE_CONFIG_DIR は隔離した置き場のまま。出どころが無ければ止まる
- python3 -I で起こした check は起こし役のフォルダ（試験の持つ写し）に __pycache__ を作らない（-I は PYTHONDONTWRITEBYTECODE を
  見ず、__pycache__ は .gitignore に隠れて git status に出ない）。共有の bin/_lib/ はどの試験も見ない（別の実行の残り物で揺れる）。
  試験自身の import の分は各試験の頭の sys.dont_write_bytecode に任せ、試験では縛らない
- 認証が無い時の案内は、名を settings.json の env に置く道と、値を出さずに項目の在りかを確かめる命令を言う
- 利用者の settings.json に apiKeyHelper が在れば、利用者の HOME で起こしてキーを得て ANTHROPIC_API_KEY として子に渡す。
  受け継いだ認証・名指し・CLAUDE_KEYCHAIN_SERVICE の項目の後、Claude Code 自身のログインの前に効く。失敗したら黙って
  ほかの段へ移らず、apiKeyHelper を名指して止まる。キーの値は出さない（#795）
- 認証が無い時の案内は API キーの道（ANTHROPIC_API_KEY・ゲートウェイの値は子に運ばないこと）も言う
- 会社が配る設定の置き場は、環境変数 WORKS_FACTORY_MANAGED_DIR で替えられる（殻の既定は OS ごとの本物の置き場のまま。この口は変えない）。
  試験の子の環境（hermetic.child_env）は、この口を空の一時フォルダへ向ける（会社が apiKeyHelper を配った機械でも、殻を通る試験が
  本物の設定を読まない）
security は偽の runner に差し替え、本物の keychain には触らない。
"""
import io
import json
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
from tests.bin import hermetic  # noqa: E402


def _forbid_the_real_managed_dir(platform=None):
    raise AssertionError("本物の会社の設定の置き場を読みに行った。試験は managed_dir（空の一時フォルダ）を渡すか、default_managed_dir を差し替える")


# 全部の試験の前に差し替える。会社が apiKeyHelper を配った機械で試験を回すと、本物の helper が起きてしまう（#798 の再レビュー）
auth_launch.default_managed_dir_real = auth_launch.default_managed_dir
auth_launch.default_managed_dir = _forbid_the_real_managed_dir

TOKEN = "sk-ant-oat01-fake-for-test"


def write_credentials(config_dir, body='{"claudeAiOauth": {"accessToken": "%s", "refreshToken": "r"}}' % TOKEN):
    """Claude Code が keychain の無い OS で置く保存済みのログイン（<config_dir>/.credentials.json）を偽で置く"""
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / ".credentials.json"
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        path.write_text(body, encoding="utf-8")


def keychain(items):
    """-s の名ごとに items の値を返す偽の security（呼ばれた名は calls に残る）"""
    calls = []

    def run(args, **kw):
        service = args[args.index("-s") + 1]
        calls.append(service)
        return types.SimpleNamespace(stdout=items.get(service, ""), returncode=0 if service in items else 44)
    run.calls = calls
    return run


class Howto(unittest.TestCase):
    """案内は名を毎回付けずに済ます道（Claude Code の settings.json の env）と、値を出さずに項目の在りかを確かめる命令を言う。
    持ち主の項目の名は書かず、置き場の字で言う"""

    def test_names_the_settings_env_route(self):
        self.assertIn('settings.json の env に "%s": "<項目の名>"' % auth_launch.ITEM_ENV, auth_launch.HOWTO)

    def test_names_the_api_key_route(self):
        """API キーの道（ANTHROPIC_API_KEY）と、ゲートウェイの値は子に運ばないこと、apiKeyHelper の道を言う"""
        for word in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "apiKeyHelper"):
            self.assertIn(word, auth_launch.HOWTO)
        self.assertIn("子には運ばない", auth_launch.HOWTO)

    def test_check_command_does_not_print_the_value(self):
        self.assertIn("security find-generic-password -s <項目の名> で", auth_launch.HOWTO)
        command = auth_launch.HOWTO.split("security find-generic-password", 1)[1].split(" で", 1)[0]
        self.assertNotIn("-w", command.split())


KEY = "sk-ant-api03-fake-for-test"


def write_settings(config_dir, body):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "settings.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")


def helper(stdout=KEY, returncode=0, error=None):
    """偽の apiKeyHelper の runner（呼ばれた時の command・HOME・CLAUDE_CONFIG_DIR は calls に残る）"""
    calls = []

    def run(command, home, config):
        calls.append((command, home, config))
        if error:
            raise error
        return types.SimpleNamespace(stdout=stdout, returncode=returncode)
    run.calls = calls
    return run


class ApiKeyHelper(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.home = str(self.tmp)
        write_settings(self.tmp / ".claude", {"apiKeyHelper": "print-key"})
        self.managed = self.tmp / "managed"   # 会社が配る設定の置き場（空。本物の置き場は読まない）
        self.managed.mkdir()

    def resolve(self, env=None, helper_runner=None, platform="linux", cfg="", sec=None):
        return auth_launch.resolve(env or {}, self.home, cfg, platform=platform, runner=sec or keychain({}),
                                   helper_runner=helper_runner, managed_dir=self.managed)

    def write_managed(self, name, body):
        path = self.managed / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
        return path

    def test_helper_key_goes_to_the_child_as_anthropic_api_key(self):
        h = helper()
        got, name, why = self.resolve(helper_runner=h)
        self.assertIsNone(why)
        self.assertEqual(got, {"ANTHROPIC_API_KEY": KEY})
        self.assertIn("apiKeyHelper", name)
        self.assertNotIn(KEY, name)
        self.assertEqual(h.calls, [("print-key", self.home, str(self.tmp / ".claude"))])

    def test_helper_runs_in_the_users_config_dir_when_given(self):
        write_settings(self.tmp / "cfg", {"apiKeyHelper": "from-cfg"})
        h = helper()
        self.resolve(helper_runner=h, cfg=str(self.tmp / "cfg"))
        self.assertEqual(h.calls, [("from-cfg", self.home, str(self.tmp / "cfg"))])

    def test_helper_beats_the_claude_code_login_and_never_reads_it(self):
        """apiKeyHelper が在れば、保存済みのログイン（macOS の keychain 項目・ほかの OS の資格のファイル）へ落ちない"""
        write_credentials(self.tmp / ".claude")
        sec = keychain({"Claude Code-credentials": TOKEN})
        for platform in ("darwin", "linux"):
            with self.subTest(platform=platform):
                got, _name, why = self.resolve(helper_runner=helper(), platform=platform, sec=sec)
                self.assertIsNone(why)
                self.assertEqual(got, {"ANTHROPIC_API_KEY": KEY})
        self.assertEqual(sec.calls, [])

    def test_inherited_auth_and_named_item_stay_above_the_helper(self):
        h = helper()
        got, name, _ = self.resolve({"ANTHROPIC_API_KEY": "env-key"}, helper_runner=h)
        self.assertEqual((got, name), ({"ANTHROPIC_API_KEY": "env-key"}, "ANTHROPIC_API_KEY"))
        got, _name, _ = self.resolve({"WORKS_FACTORY_KEYCHAIN_ITEM": "named"}, helper_runner=h, platform="darwin",
                                     sec=keychain({"named": TOKEN}))
        self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertEqual(h.calls, [])

    def test_helper_failure_stops_naming_it_without_trying_other_stages(self):
        """終了コードが 0 でない・空の出力・起こせない時は、ログインや keychain に移らず apiKeyHelper を名指して止まる"""
        write_credentials(self.tmp / ".claude")
        sec = keychain({"Claude Code-credentials": TOKEN, "svc": TOKEN})
        cases = (helper(returncode=1), helper(stdout="  \n"), helper(error=FileNotFoundError()))
        for h in cases:
            for platform in ("darwin", "linux"):
                with self.subTest(platform=platform):
                    got, _name, why = self.resolve({"CLAUDE_KEYCHAIN_SERVICE": "gone"}, helper_runner=h, platform=platform, sec=sec)
                    self.assertIsNone(got)
                    self.assertIn("apiKeyHelper", why)
        self.assertNotIn("Claude Code-credentials", sec.calls)

    def test_helper_value_never_appears_in_messages(self):
        got, name, why = self.resolve(helper_runner=helper(stdout=KEY, returncode=3))
        self.assertIsNone(got)
        self.assertNotIn(KEY, "%s %s" % (name, why))

    def test_settings_without_a_usable_helper_fall_through_as_before(self):
        write_credentials(self.tmp / ".claude")
        for body in ({"env": {}}, {"apiKeyHelper": ""}, {"apiKeyHelper": None}):
            with self.subTest(body=body):
                write_settings(self.tmp / ".claude", body)
                h = helper()
                got, _name, why = self.resolve(helper_runner=h)
                self.assertIsNone(why)
                self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
                self.assertEqual(h.calls, [])

    def test_unusable_user_settings_stop_naming_the_file_without_falling_to_the_login(self):
        """JSON として壊れている・object でない・apiKeyHelper が文字列でない設定は、保存済みのログインへ落ちずに壊れたファイルを名指して止まる"""
        write_credentials(self.tmp / ".claude")
        path = self.tmp / ".claude" / "settings.json"
        for body in ("not json", "[]", {"apiKeyHelper": 3}, {"apiKeyHelper": ["x"]}):
            for platform in ("darwin", "linux"):
                with self.subTest(body=body, platform=platform):
                    write_settings(self.tmp / ".claude", body)
                    h = helper()
                    sec = keychain({"Claude Code-credentials": TOKEN})
                    got, _name, why = self.resolve(helper_runner=h, platform=platform, sec=sec)
                    self.assertIsNone(got)
                    self.assertIn(str(path), why)
                    self.assertEqual((h.calls, sec.calls), ([], []))

    def test_unusable_settings_do_not_stop_a_launch_a_higher_stage_decides(self):
        write_settings(self.tmp / ".claude", "not json")
        got, name, _ = self.resolve({"ANTHROPIC_API_KEY": "env-key"}, helper_runner=helper())
        self.assertEqual((got, name), ({"ANTHROPIC_API_KEY": "env-key"}, "ANTHROPIC_API_KEY"))

    def test_inherited_oauth_token_sits_below_the_helper(self):
        """Claude Code 自身の優先順は apiKeyHelper が CLAUDE_CODE_OAUTH_TOKEN より上。親の環境の OAuth トークンだけが在る時は helper のキーを採る"""
        h = helper()
        got, name, why = self.resolve({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, helper_runner=h)
        self.assertIsNone(why)
        self.assertEqual(got, {"ANTHROPIC_API_KEY": KEY})
        self.assertIn("apiKeyHelper", name)
        self.assertEqual(len(h.calls), 1)

    def test_oauth_token_without_a_helper_is_inherited_as_before(self):
        write_settings(self.tmp / ".claude", {})
        h = helper()
        got, name, _ = self.resolve({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, helper_runner=h)
        self.assertEqual((got, name, h.calls), ({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, "CLAUDE_CODE_OAUTH_TOKEN", []))

    def test_other_inherited_credentials_stay_above_the_helper_even_with_an_oauth_token(self):
        for other in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
            with self.subTest(other=other):
                h = helper()
                got, _name, _ = self.resolve({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN, other: "1"}, helper_runner=h)
                self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN, other: "1"})
                self.assertEqual(h.calls, [])

    def test_helper_failure_with_an_inherited_oauth_token_stops(self):
        got, _name, why = self.resolve({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, helper_runner=helper(returncode=1))
        self.assertIsNone(got)
        self.assertIn("apiKeyHelper", why)

    def test_managed_settings_helper_is_read_when_the_user_has_none(self):
        """会社が配る managed-settings.json にだけ apiKeyHelper が在っても、保存済みのログインへ落ちずに採る"""
        write_settings(self.tmp / ".claude", {})
        write_credentials(self.tmp / ".claude")
        path = self.write_managed("managed-settings.json", {"apiKeyHelper": "managed-cmd"})
        h = helper()
        got, name, why = self.resolve(helper_runner=h)
        self.assertIsNone(why)
        self.assertEqual(got, {"ANTHROPIC_API_KEY": KEY})
        self.assertEqual([c[0] for c in h.calls], ["managed-cmd"])
        self.assertIn(str(path), name)

    def test_managed_settings_win_over_the_users(self):
        self.write_managed("managed-settings.json", {"apiKeyHelper": "managed-cmd"})
        h = helper()
        self.resolve(helper_runner=h)
        self.assertEqual([c[0] for c in h.calls], ["managed-cmd"])

    def test_managed_drop_ins_follow_alphabetical_order_and_the_later_one_wins(self):
        """managed-settings.json の後に managed-settings.d/*.json を名前順に重ね、単一の値は後が勝つ。隠しファイルと .json でない物は読まない"""
        self.write_managed("managed-settings.json", {"apiKeyHelper": "base"})
        self.write_managed("managed-settings.d/20-b.json", {"apiKeyHelper": "second"})
        self.write_managed("managed-settings.d/10-a.json", {"apiKeyHelper": "first"})
        self.write_managed("managed-settings.d/30-other.json", {"env": {}})
        self.write_managed("managed-settings.d/.40-hidden.json", {"apiKeyHelper": "hidden"})
        self.write_managed("managed-settings.d/50-note.txt", {"apiKeyHelper": "text"})
        h = helper()
        self.resolve(helper_runner=h)
        self.assertEqual([c[0] for c in h.calls], ["second"])

    def test_managed_drop_in_alone_is_read(self):
        write_settings(self.tmp / ".claude", {})
        self.write_managed("managed-settings.d/10-a.json", {"apiKeyHelper": "dropin"})
        h = helper()
        self.resolve(helper_runner=h)
        self.assertEqual([c[0] for c in h.calls], ["dropin"])

    def test_unusable_managed_settings_stop_naming_the_file(self):
        for name, body in (("managed-settings.json", "not json"), ("managed-settings.d/10-a.json", {"apiKeyHelper": 3})):
            with self.subTest(name=name):
                path = self.write_managed(name, body)
                h = helper()
                got, _name, why = self.resolve(helper_runner=h)
                self.assertIsNone(got)
                self.assertIn(str(path), why)
                self.assertEqual(h.calls, [])
                path.unlink()

    def test_managed_dir_per_platform(self):
        self.assertEqual(str(auth_launch.default_managed_dir_real("darwin")), "/Library/Application Support/ClaudeCode")
        self.assertEqual(str(auth_launch.default_managed_dir_real("linux")), "/etc/claude-code")
        self.assertEqual(str(auth_launch.default_managed_dir_real("win32")), "C:\\Program Files\\ClaudeCode")

    def test_default_runner_does_not_capture_stderr(self):
        """標準エラーは捕まえずに端末へ流す（期限が無いので、helper の問いが見えないまま待ち続けない）"""
        with mock.patch.object(auth_launch.subprocess, "run") as run, mock.patch.object(sys, "stderr", io.StringIO()):
            auth_launch.user_helper_runner("cmd", "/users-home", "/users-home/.claude")
        kw = run.call_args.kwargs
        self.assertNotIn("capture_output", kw)
        self.assertNotIn("stderr", kw)
        self.assertEqual(kw["stdout"], subprocess.PIPE)

    def test_default_runner_restores_the_recorded_user_env(self):
        """exec の時（子の環境は隔離済み）は、殻が控えた隔離の前の XDG_* を戻す。控えに無い名（null）は外す"""
        record = json.dumps({"HOME": "/u", "XDG_CONFIG_HOME": "/u/.config", "XDG_DATA_HOME": None,
                             "XDG_CACHE_HOME": "/u/.cache", "XDG_STATE_HOME": None})
        env = {"HOME": "/iso", "XDG_CONFIG_HOME": "/iso/c", "XDG_DATA_HOME": "/iso/d", "XDG_STATE_HOME": "/iso/s",
               "WORKS_FACTORY_USER_ENV": record}
        with mock.patch.object(auth_launch.os, "environ", env), mock.patch.object(auth_launch.subprocess, "run") as run, \
                mock.patch.object(sys, "stderr", io.StringIO()):
            auth_launch.user_helper_runner("cmd", "/u", "/u/.claude")
        got = run.call_args.kwargs["env"]
        self.assertEqual((got["HOME"], got["XDG_CONFIG_HOME"], got["XDG_CACHE_HOME"]), ("/u", "/u/.config", "/u/.cache"))
        self.assertNotIn("XDG_DATA_HOME", got)
        self.assertNotIn("XDG_STATE_HOME", got)

    def test_default_runner_leaves_the_env_alone_without_a_record(self):
        """控えが無い時（check は利用者の環境で起こされる）は、環境の XDG_* をそのまま渡す"""
        env = {"HOME": "/u", "XDG_CONFIG_HOME": "/u/.config"}
        with mock.patch.object(auth_launch.os, "environ", env), mock.patch.object(auth_launch.subprocess, "run") as run, \
                mock.patch.object(sys, "stderr", io.StringIO()):
            auth_launch.user_helper_runner("cmd", "/u", "/u/.claude")
        self.assertEqual(run.call_args.kwargs["env"]["XDG_CONFIG_HOME"], "/u/.config")

    def test_check_names_the_helper_source_without_running_it(self):
        """check は helper を起こさず、出どころの名とパスだけを返す（helper は exec の 1 回だけ。使い捨てのキーや指紋の確かめを求める helper のため）"""
        h = helper()
        got, name, why = auth_launch.resolve({}, self.home, "", platform="linux", runner=keychain({}), helper_runner=h,
                                             managed_dir=self.managed, fetch=False)
        self.assertIsNone(why)
        self.assertEqual(got, {})
        self.assertIn(str(self.tmp / ".claude" / "settings.json"), name)
        self.assertEqual(h.calls, [])

    def test_check_still_stops_on_unusable_settings(self):
        write_settings(self.tmp / ".claude", "not json")
        got, _name, why = auth_launch.resolve({}, self.home, "", platform="linux", runner=keychain({}), helper_runner=helper(),
                                              managed_dir=self.managed, fetch=False)
        self.assertIsNone(got)
        self.assertIn(str(self.tmp / ".claude" / "settings.json"), why)

    @unittest.skipIf(sys.platform == "win32", "SKIP windows: sh の 1 行")
    def test_a_launch_runs_the_helper_once_in_exec_only(self):
        """起動 1 回で helper は 1 回だけ、exec で起こされる（check では起こさない）。exec の helper は隔離の前の XDG_CONFIG_HOME で
        起こされる。README と決め api-key-helper-relay に書いた回数を縛る"""
        tmp = hermetic.tmpdir(self)
        count = tmp / "count"
        script = tmp / "helper.sh"
        script.write_text('#!/bin/sh\necho "$XDG_CONFIG_HOME" >> "%s"\necho %s\n' % (count, KEY))
        script.chmod(0o755)
        write_settings(tmp / "user" / ".claude", {"apiKeyHelper": str(script)})
        record = json.dumps({"HOME": str(tmp / "user"), "XDG_CONFIG_HOME": "/user-xdg", "XDG_DATA_HOME": None,
                             "XDG_CACHE_HOME": None, "XDG_STATE_HOME": None})
        base = ["--user-home", str(tmp / "user"), "--managed-dir", str(tmp / "managed")]
        run = lambda args, env: subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), *args],
                                               env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        r = run(["check", *base], hermetic.child_env(HOME=str(tmp / "user"), XDG_CONFIG_HOME="/checker"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("apiKeyHelper", r.stdout)
        self.assertIn(str(tmp / "user" / ".claude" / "settings.json"), r.stdout)
        self.assertFalse(count.exists())
        r = run(["exec", *base, "--", sys.executable, "-I", "-c", "pass"],
                hermetic.child_env(HOME=str(tmp / "iso"), XDG_CONFIG_HOME="/iso-xdg", WORKS_FACTORY_USER_ENV=record))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(count.read_text().split(), ["/user-xdg"])

    def test_a_managed_file_the_os_denies_is_skipped_like_claude_code(self):
        """OS が読ませない（PermissionError）会社の設定のファイルは無いものとして次の出どころへ進む（Claude Code と同じ。
        https://code.claude.com/docs/en/managed-settings）。壊れた JSON・字でない値で止まるのは今のまま。利用者の設定は読めなければ止まる"""
        denied = self.write_managed("managed-settings.json", {"apiKeyHelper": "managed-cmd"})
        real = pathlib.Path.read_text

        def read_text(path, *a, **kw):
            if path == denied:
                raise PermissionError(13, "denied")
            return real(path, *a, **kw)
        h = helper()
        with mock.patch.object(pathlib.Path, "read_text", read_text):
            got, _name, why = self.resolve(helper_runner=h)
            self.assertIsNone(why)
            self.assertEqual([c[0] for c in h.calls], ["print-key"])
            user = self.tmp / ".claude" / "settings.json"
            real_managed = denied
            real_managed.unlink()
            denied = user
            got, _name, why = self.resolve(helper_runner=helper())
        self.assertIsNone(got)
        self.assertIn(str(user), why)

    def test_default_runner_uses_the_users_home_and_config_dir(self):
        err = io.StringIO()
        with mock.patch.object(auth_launch.subprocess, "run") as run, mock.patch.object(sys, "stderr", err):
            auth_launch.user_helper_runner("cmd", "/users-home", "/users-home/.claude")
        self.assertEqual(run.call_args.args[0], "cmd")
        self.assertNotIn("timeout", run.call_args.kwargs)   # 期限を足さない（持ち主の決め no-timeouts）。止めるのは起動した人
        self.assertIn("apiKeyHelper", err.getvalue())       # 待っているコマンドが分かる 1 行（キーの値は出さない）
        self.assertTrue(run.call_args.kwargs["shell"])
        env = run.call_args.kwargs["env"]
        self.assertEqual((env["HOME"], env["CLAUDE_CONFIG_DIR"]), ("/users-home", "/users-home/.claude"))

    @unittest.skipIf(sys.platform == "win32", "SKIP windows: sh の 1 行")
    def test_exec_hands_the_helper_key_only_to_the_child(self):
        tmp = hermetic.tmpdir(self)
        write_settings(tmp / "user" / ".claude", {"apiKeyHelper": "echo %s" % KEY})
        env = hermetic.child_env(HOME=str(tmp / "iso"), CLAUDE_CONFIG_DIR=str(tmp / "iso-config"))
        probe = "import os; print(os.environ.get('ANTHROPIC_API_KEY') == %r, os.environ['HOME'])" % KEY
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--user-home", str(tmp / "user"),
                            "--managed-dir", str(tmp / "managed"), "--", sys.executable, "-I", "-c", probe],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ["True", str(tmp / "iso")])
        self.assertNotIn(KEY, r.stderr)

    @unittest.skipIf(sys.platform == "win32", "SKIP windows: sh の 1 行")
    def test_exec_stops_with_howto_when_the_helper_fails(self):
        tmp = hermetic.tmpdir(self)
        write_settings(tmp / ".claude", {"apiKeyHelper": "exit 7"})
        write_credentials(tmp / ".claude")
        env = hermetic.child_env(HOME=str(tmp))
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--for", "bin/start",
                            "--user-home", str(tmp), "--managed-dir", str(tmp / "managed"), "--", sys.executable, "-c",
                            "print('started')"],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertTrue(r.stderr.splitlines()[-1].startswith("bin/start: " + auth_launch.HOWTO), r.stderr)
        self.assertIn("apiKeyHelper（", r.stderr.splitlines()[-1])


class ManagedDirEnv(unittest.TestCase):
    """会社が配る設定の置き場の差し替えの口（環境変数 WORKS_FACTORY_MANAGED_DIR）"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.managed = self.tmp / "managed"
        self.managed.mkdir()
        (self.managed / "managed-settings.json").write_text(json.dumps({"apiKeyHelper": "managed-cmd"}), encoding="utf-8")

    def check(self, **env):
        """python3 -I で check を起こす（殻と同じ起こし方）。ANTHROPIC_API_KEY など前の段の認証は無い環境"""
        return subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "check", "--user-home", str(self.tmp / "user")],
                              env=hermetic.child_env(HOME=str(self.tmp / "iso"), **env), capture_output=True, text=True,
                              encoding="utf-8")

    def test_the_env_names_the_folder_the_shell_reads(self):
        done = self.check(**{auth_launch.MANAGED_DIR_ENV: str(self.managed)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("apiKeyHelper", done.stdout)
        self.assertIn(str(self.managed / "managed-settings.json"), done.stdout)

    def test_the_flag_wins_over_the_env(self):
        other = self.tmp / "other"
        other.mkdir()
        done = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "check", "--user-home", str(self.tmp / "user"),
                               "--managed-dir", str(other)],
                              env=hermetic.child_env(HOME=str(self.tmp / "iso"), **{auth_launch.MANAGED_DIR_ENV: str(self.managed)}),
                              capture_output=True, text=True, encoding="utf-8")
        self.assertNotIn("apiKeyHelper", done.stdout)

    def test_unset_env_reads_the_default_folder(self):
        """口が無い時の道は変わらない: OS ごとの既定の置き場（default_managed_dir）を読む（E14）"""
        out = io.StringIO()
        with mock.patch.object(auth_launch, "default_managed_dir", lambda platform=None: self.managed), \
                mock.patch.dict(os.environ, {}, clear=True), mock.patch("sys.stdout", out):
            self.assertEqual(auth_launch.main(["check", "--user-home", str(self.tmp / "user")]), 0)
        self.assertIn("apiKeyHelper", out.getvalue())

    def test_child_env_points_the_env_at_an_empty_folder(self):
        """殻を通る試験の子の環境は、本物の会社の設定を読まない（空の既存のフォルダ）。試験が意図して渡せば、その値が勝つ"""
        folder = pathlib.Path(hermetic.child_env()[auth_launch.MANAGED_DIR_ENV])
        self.assertTrue(folder.is_dir())
        self.assertEqual(list(folder.iterdir()), [])
        self.assertEqual(hermetic.child_env(**{auth_launch.MANAGED_DIR_ENV: "x"})[auth_launch.MANAGED_DIR_ENV], "x")


class NoRealManagedDir(unittest.TestCase):
    """会社の設定の置き場を空の一時フォルダにする（本物の置き場は読まない）"""

    def setUp(self):
        empty = hermetic.tmpdir(self) / "no-managed"
        patch = mock.patch.object(auth_launch, "default_managed_dir", lambda platform=None: empty)
        patch.start()
        self.addCleanup(patch.stop)


class ResolveOrder(NoRealManagedDir):
    def test_oauth_token_in_the_env_beats_a_named_keychain_service_without_a_helper(self):
        """親の環境に CLAUDE_CODE_OAUTH_TOKEN が在り CLAUDE_KEYCHAIN_SERVICE も名指し、helper が無い時は、環境のトークンを採り
        keychain の項目を読まない"""
        run = keychain({"svc": TOKEN})
        env = {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-env", "CLAUDE_KEYCHAIN_SERVICE": "svc"}
        got, name, why = auth_launch.resolve(env, "/u", "", platform="darwin", runner=run)
        self.assertIsNone(why)
        self.assertEqual((got, name), ({"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-env"}, "CLAUDE_CODE_OAUTH_TOKEN"))
        self.assertEqual(run.calls, [])

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

    def test_darwin_without_claude_codes_item_stops(self):
        """macOS で Claude Code の keychain の項目も無ければ止まる（保存済みのファイルは読まない）"""
        tmp = hermetic.tmpdir(self)
        write_credentials(tmp / ".claude")
        got, name, why = auth_launch.resolve({}, str(tmp), "", platform="darwin", runner=keychain({}))
        self.assertEqual((got, name), (None, None))
        self.assertIn("Claude Code-credentials", why)

    def test_off_darwin_reads_the_users_saved_login_file(self):
        """macOS 以外では利用者の <CLAUDE_CONFIG_DIR>/.credentials.json（無ければ <HOME>/.claude の）のトークンを渡し、
        出どころの名はそのファイルを名指す。keychain は読まない"""
        tmp = hermetic.tmpdir(self)
        for platform in ("linux", "win32"):
            for cfg, where in (("", tmp / ".claude"), (str(tmp / "cfg"), tmp / "cfg")):
                with self.subTest(platform=platform, cfg=cfg):
                    write_credentials(where)
                    run = keychain({})
                    got, name, why = auth_launch.resolve({}, str(tmp), cfg, platform=platform, runner=run)
                    self.assertIsNone(why)
                    self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
                    self.assertIn(str(where / ".credentials.json"), name)
                    self.assertNotIn(TOKEN, name)
                    self.assertEqual(run.calls, [])

    def test_off_darwin_without_a_usable_saved_login_stops(self):
        """macOS 以外で資格のファイルが無い・トークンでない値・読めない字なら止まり、理由はそのファイルを名指す"""
        for body in (None, '{"claudeAiOauth": {"accessToken": "not-a-token"}}', b"\xff\xfe"):
            with self.subTest(body=body):
                tmp = hermetic.tmpdir(self)
                if body is not None:
                    write_credentials(tmp / ".claude", body)
                got, _name, why = auth_launch.resolve({}, str(tmp), "", platform="linux", runner=keychain({}))
                self.assertIsNone(got)
                self.assertIn(str(tmp / ".claude" / ".credentials.json"), why)

    def test_named_item_beats_inherited_auth(self):
        """WORKS_FACTORY_KEYCHAIN_ITEM は受け継いだ CLAUDE_CODE_OAUTH_TOKEN・ANTHROPIC_API_KEY より先に効く"""
        env = {"WORKS_FACTORY_KEYCHAIN_ITEM": "named", "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-env", "ANTHROPIC_API_KEY": "k"}
        run = keychain({"named": TOKEN})
        got, name, why = auth_launch.resolve(env, "/u", "", platform="darwin", runner=run)
        self.assertIsNone(why)
        self.assertEqual(got, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertIn("WORKS_FACTORY_KEYCHAIN_ITEM", name)
        self.assertEqual(run.calls, ["named"])

    def test_flag_set_to_off_is_not_a_credential(self):
        """受け継いだ認証に、値が「使わない」の旗は入らない（子の環境には受けた環境のまま残る）"""
        for off in ("0", "false"):
            with self.subTest(off=off):
                env = {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_USE_BEDROCK": off, "CLAUDE_CODE_USE_VERTEX": "1"}
                got, _name, why = auth_launch.resolve(env, "/u", "", platform="linux", runner=keychain({}))
                self.assertIsNone(why)
                self.assertEqual(got, {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_USE_VERTEX": "1"})

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


class ChildEnv(NoRealManagedDir):
    ISOLATED = {"HOME": "/run/home", "CLAUDE_CONFIG_DIR": "/run/claude-config"}

    def test_every_source_keeps_the_isolated_config_dir(self):
        """受け継いだ認証でも利用者の資格のファイルでも、子の HOME・CLAUDE_CONFIG_DIR は隔離した置き場のまま"""
        tmp = hermetic.tmpdir(self)
        write_credentials(tmp / "cfg")
        for env in ({"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, {"ANTHROPIC_API_KEY": "k"}, {}):
            with self.subTest(env=list(env)):
                got, _name, why = auth_launch.resolve(env, str(tmp), str(tmp / "cfg"), platform="linux", runner=keychain({}))
                self.assertIsNone(why)
                child = auth_launch.child_env(self.ISOLATED, got, False)
                self.assertEqual((child["HOME"], child["CLAUDE_CONFIG_DIR"]), ("/run/home", "/run/claude-config"))

    def test_named_drops_credentials_that_outrank_the_token(self):
        """名指しで決めた時は、Claude Code が CLAUDE_CODE_OAUTH_TOKEN より先に使う資格（claude_auth の INHERITED と FOUNDRY の旗）を外す"""
        env = {"HOME": "/iso", "ANTHROPIC_API_KEY": "k", "ANTHROPIC_AUTH_TOKEN": "t", "CLAUDE_CODE_USE_FOUNDRY": "1",
               "CLAUDE_CODE_USE_BEDROCK": "1", "CLAUDE_CODE_OAUTH_TOKEN": "old"}
        self.assertEqual(auth_launch.child_env(env, {"CLAUDE_CODE_OAUTH_TOKEN": TOKEN}, True),
                         {"HOME": "/iso", "CLAUDE_CODE_OAUTH_TOKEN": TOKEN})
        self.assertTrue(auth_launch.child_env(env, {"ANTHROPIC_API_KEY": "k"}, False) == env)


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
                            "--managed-dir", str(tmp / "managed"), "--", sys.executable, "-I", "-c", probe], env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), '{"CLAUDE_CODE_OAUTH_TOKEN": true, "ANTHROPIC_API_KEY": null, "HOME": "%s"}'
                         % (tmp / "iso"))
        self.assertEqual((bin_dir / "security.home").read_text().strip(), str(tmp / "user"))

    def test_exec_stops_with_howto_and_does_not_start_the_child(self):
        """名指しの項目を読めない時と、出どころが何も無い時（macOS は Claude Code の項目、ほかの OS は資格のファイルが無い）は、
        子を起こさず 1 行の案内（呼び手の名つき）で 2"""
        for extra in ({"WORKS_FACTORY_KEYCHAIN_ITEM": "named"}, {}):
            with self.subTest(env=list(extra)):
                tmp = hermetic.tmpdir(self)
                bin_dir = self.fake_security(tmp, "nothing-here")
                env = hermetic.child_env(HOME=str(tmp), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), **extra)
                r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--for", "bin/start",
                                    "--user-home", str(tmp), "--managed-dir", str(tmp / "managed"), "--", sys.executable, "-c",
                                    "print('started')"],
                                   env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, "")
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
                self.assertTrue(r.stderr.startswith("bin/start: " + auth_launch.HOWTO), r.stderr)

    @unittest.skipIf(sys.platform == "darwin", "SKIP macos: 資格のファイルの段は macOS 以外だけ")
    def test_exec_off_darwin_hands_the_saved_login_to_the_isolated_child(self):
        """macOS 以外で --user-config の .credentials.json が在れば、子にトークンを渡し、子の CLAUDE_CONFIG_DIR・HOME は隔離のまま。
        起こし役自身は値を出さない"""
        tmp = hermetic.tmpdir(self)
        write_credentials(tmp / "user-config")
        env = hermetic.child_env(HOME=str(tmp / "iso"), CLAUDE_CONFIG_DIR=str(tmp / "iso-config"))
        probe = ("import os; print(os.environ.get('CLAUDE_CODE_OAUTH_TOKEN') == %r, os.environ['CLAUDE_CONFIG_DIR'], "
                 "os.environ['HOME'])" % TOKEN)
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--for", "bin/start",
                            "--user-home", str(tmp / "user"), "--user-config", str(tmp / "user-config"), "--managed-dir", str(tmp / "managed"), "--",
                            sys.executable, "-I", "-c", probe],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(r.stdout.split(), ["True", str(tmp / "iso-config"), str(tmp / "iso")])

    def test_exec_with_no_auth_starts_the_child_without_reading_the_keychain(self):
        """WORKS_FACTORY_NO_AUTH=1 なら認証を読まずに子を起こす（security を起こせば $0.home が残る）"""
        tmp = hermetic.tmpdir(self)
        bin_dir = self.fake_security(tmp, "named")
        env = hermetic.child_env(HOME=str(tmp), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                                 WORKS_FACTORY_NO_AUTH="1", WORKS_FACTORY_KEYCHAIN_ITEM="named")
        r = subprocess.run([sys.executable, "-I", str(CORE / "auth_launch.py"), "exec", "--user-home", str(tmp),
                            "--managed-dir", str(tmp / "managed"), "--",
                            sys.executable, "-I", "-c", "import os; print('started', os.environ.get('CLAUDE_CODE_OAUTH_TOKEN'))"],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "started None"), r.stderr)
        self.assertFalse((bin_dir / "security.home").exists())

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
        core = tmp / "pack" / "bin" / "_lib"   # auth_launch.py は ../../lib の userenv を import する
        shutil.copytree(CORE, core, ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "pack" / "lib").mkdir()
        shutil.copy(ROOT / "lib" / "userenv.py", tmp / "pack" / "lib" / "userenv.py")
        home = tmp / "home"
        home.mkdir()
        env = hermetic.child_env(CLAUDE_CODE_OAUTH_TOKEN=TOKEN, HOME=str(home))
        r = subprocess.run([sys.executable, "-I", str(core / "auth_launch.py"), "check", "--user-home", str(home),
                            "--managed-dir", str(tmp / "managed")],
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "CLAUDE_CODE_OAUTH_TOKEN"), r.stderr)
        self.assertNotIn(TOKEN, r.stdout + r.stderr)
        self.assertEqual(list(core.rglob("__pycache__")), [])


if __name__ == "__main__":
    unittest.main()
