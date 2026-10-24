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
- 認証が無い時の案内は API キーの道（ANTHROPIC_API_KEY）と、設定の env の接続の値（接続先・資格・proxy・証明書・alias と、選んだ
  Bedrock・Mantle・Vertex の公式の名）は子に運び、フック・権限・プラグインは運ばないことも言う（動きは ConnectionProfile が照らす）
- 設定の env（親の env でも同じ）が選んだ Bedrock・Mantle・Vertex は、公式の名の許可リストで子に運ぶ。既定のログインへ黙って替えない。
  運べない物（設定の Foundry・相対パスの資格ファイル）だけ止めて名指す。HOME 基準の AWS の資格は、本当の HOME で資格を出す包み
  （awsCredentialExport）にくるんで運び、渡せない物は止めずに告知で名指す。管理者の awsCredentialExport・awsAuthRefresh・gcpAuthRefresh は
  Claude Code 自身が走らせるので、殻は運ばず止めず、包みを置くかの判断にも数えない
- 会社が配る設定の置き場は、環境変数 WORKS_FACTORY_MANAGED_DIR で替えられる（殻の既定は OS ごとの本物の置き場のまま。この口は変えない）。
  試験の子の環境（hermetic.child_env）は、この口を空の一時フォルダへ向ける（会社が apiKeyHelper を配った機械でも、殻を通る試験が
  本物の設定を読まない）
security は偽の runner に差し替え、本物の keychain には触らない。
"""
import io
import json
import os
import pathlib
import shlex
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
import hostgh  # noqa: E402
import place  # noqa: E402
from tests.bin import hermetic  # noqa: E402


def _forbid_the_real_managed_dir(platform=None):
    raise AssertionError("本物の会社の設定の置き場を読みに行った。試験は managed_dir（空の一時フォルダ）を渡すか、default_managed_dir を差し替える")


# 全部の試験の前に差し替える。会社が apiKeyHelper を配った機械で試験を回すと、本物の helper が起きてしまう（#798 の再レビュー）
auth_launch.default_managed_dir_real = auth_launch.default_managed_dir
auth_launch.default_managed_dir = _forbid_the_real_managed_dir

TOKEN = "sk-ant-oat01-fake-for-test"
# 偽の aws。包みが本当の HOME と --profile で起こしたことを、標準出力で見せる
FAKE_AWS = '#!/bin/sh\necho "home=$HOME xdg=$XDG_CONFIG_HOME args=$*"\n'


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


class ConnectionProfile(unittest.TestCase):
    """必要な接続設定だけを抽出し、秘密は env、alias だけを inline に運ぶ。資格・隔離の競合を縛る。"""

    def setUp(self):
        self.tmp = hermetic.tmpdir(self)

    def profile(self, body, env=None):
        write_settings(self.tmp, body)
        return auth_launch.connection_profile(self.tmp, env or {})

    def test_direct_credentials_replace_parent_without_copying_user_behaviour(self):
        secret = "dummy-selected-secret"
        p, deferred = self.profile({"env": {"ANTHROPIC_API_KEY": secret,
                                            "ANTHROPIC_BASE_URL": "https://dummy.invalid",
                                            "ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model",
                                            "HOME": "/user", "XDG_CACHE_HOME": "/user-cache", "UNNEEDED": "no"},
                                    "hooks": {"Stop": []}, "permissions": {"allow": ["Bash(*)"]},
                                    "sandbox": {"enabled": False}, "enabledPlugins": {"unneeded": True},
                                    "apiKeyHelper": "never-executed"})
        self.assertIn(str(self.tmp / "settings.json"), deferred)   # 親の資格を外すことと、その出どころのファイルを言う
        self.assertIn("ANTHROPIC_API_KEY", deferred)
        self.assertNotIn(secret, deferred)
        out = auth_launch.profile_env({"HOME": "/factory", "ANTHROPIC_AUTH_TOKEN": "parent",
                                       "CLAUDE_CODE_OAUTH_TOKEN": "parent-oauth", "CLAUDE_API_KEY": "other"}, p)
        self.assertEqual(out, {"HOME": "/factory", "ANTHROPIC_API_KEY": secret,
                               "ANTHROPIC_BASE_URL": "https://dummy.invalid"})
        self.assertEqual(p["settings"], {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"}})
        self.assertNotIn(secret, json.dumps(p["settings"]))
        self.assertNotIn("apiKeyHelper", p["settings"])

    def test_notice_names_the_file_of_each_explicit_credential_that_drops_the_parent_ones(self):
        """設定の env が直接の資格を明示して親の資格を外す時、告知は資格の名と出どころのファイル（利用者のか管理者の）を言い、値は言わない。
        明示が無い時（alias だけ）は何も告げない"""
        managed = self.tmp / "managed"
        managed.mkdir()
        write_settings(self.tmp, {"env": {"ANTHROPIC_API_KEY": "user-secret"}})
        (managed / "managed-settings.json").write_text(json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "managed-secret"}}), encoding="utf-8")
        p, notice = auth_launch.connection_profile(self.tmp, {}, managed)
        self.assertTrue(p["drop"])
        for word in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", str(self.tmp / "settings.json"), str(managed / "managed-settings.json")):
            self.assertIn(word, notice)
        for secret in ("user-secret", "managed-secret"):
            self.assertNotIn(secret, notice)
        write_settings(self.tmp, {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"}})
        (managed / "managed-settings.json").unlink()
        p, notice = auth_launch.connection_profile(self.tmp, {}, managed)
        self.assertEqual((p["drop"], notice), ([], ""))

    def cloud_world(self):
        """選ばれた provider の試験の場: 偽の本当の HOME（空白を含む）・PATH に置く空のフォルダ・管理者の置き場・包みの置き口"""
        self.real = self.tmp / "real home"
        self.config = self.real / ".claude"
        self.config.mkdir(parents=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.managed = self.tmp / "managed"
        self.managed.mkdir()
        self.put = lambda name, body: hostgh.place_shim(self.tmp / "fence dir", name, body)

    def fake_aws(self):
        aws = self.bin / "aws"
        aws.write_text(FAKE_AWS, encoding="utf-8")
        aws.chmod(0o755)

    def connect(self, parent=None, settings=None):
        """親の env（本当の HOME と PATH つき）と利用者の settings.json で、本物の connection_profile を呼ぶ"""
        if settings is not None:
            write_settings(self.config, settings)
        env = {"HOME": str(self.real), "PATH": str(self.bin), **(parent or {})}
        return auth_launch.connection_profile(self.config, env, self.managed, self.put)

    def run_wrapper(self, command, **env):
        """置いた包みを、隔離した HOME・XDG の env で走らせる（役の Claude Code が起こす形）"""
        (path,) = shlex.split(command)
        env = hermetic.child_env(PATH="/usr/bin:/bin", HOME=str(self.tmp / "iso"), XDG_CONFIG_HOME="/iso-xdg", **env)
        return subprocess.run([path], env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_provider_settings_are_carried_not_silently_changed_to_direct(self):
        """設定の env が選んだ Bedrock・Mantle・Vertex は、旗と公式の名の許可リストの名が profile['env'] に入る。direct の資格は運ばず
        drop は空。許可リストの外の名は入らない。設定の Foundry と、相対パスの資格ファイルは、名とファイルを言って止まる（値は言わない）"""
        self.cloud_world()
        region = {"CLAUDE_CODE_USE_BEDROCK": ("AWS_REGION", "us-east-1"), "CLAUDE_CODE_USE_MANTLE": ("AWS_REGION", "us-east-1"),
                  "CLAUDE_CODE_USE_VERTEX": ("CLOUD_ML_REGION", "us-east5")}
        for flag in claude_auth.FLAGS:
            with self.subTest(flag=flag):
                name, value = region[flag]
                p, notice = self.connect(settings={"env": {flag: "1", name: value, "VERTEX_REGION_CLAUDE_HAIKU": "global",
                                                           "ANTHROPIC_API_KEY": "not-direct", "ANTHROPIC_BASE_URL": "https://gw.invalid",
                                                           "ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model", "UNNEEDED": "no",
                                                           "HOME": "/must-not-restore"}})
                want = {flag: "1", name: value, "ANTHROPIC_BASE_URL": "https://gw.invalid"}
                if flag == "CLAUDE_CODE_USE_VERTEX":
                    want["VERTEX_REGION_CLAUDE_HAIKU"] = "global"
                self.assertEqual(p["env"], want)
                self.assertEqual(p["drop"], [])
                self.assertEqual(p["settings"], {"env": {"ANTHROPIC_DEFAULT_SONNET_MODEL": "dummy-model"}})
                self.assertIn(flag, notice)
                self.assertIn(str(self.config / "settings.json"), notice)
                self.assertNotIn("未対応", notice)
        parent = {"CLAUDE_CODE_USE_BEDROCK": "1", "ANTHROPIC_API_KEY": "parent", "HOME": "/factory"}
        p, _ = auth_launch.connection_profile(self.config, parent, self.managed)
        self.assertEqual(auth_launch.profile_env(parent, p), parent)
        for body, word in (({"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_API_KEY": "dummy-foundry-secret"}, "CLAUDE_CODE_USE_FOUNDRY"),
                           ({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_SHARED_CREDENTIALS_FILE": "rel/creds-secret"}, "AWS_SHARED_CREDENTIALS_FILE"),
                           ({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_CONFIG_FILE": "rel/config-secret"}, "AWS_CONFIG_FILE"),
                           ({"CLAUDE_CODE_USE_VERTEX": "1", "GOOGLE_APPLICATION_CREDENTIALS": "rel/adc-secret"}, "GOOGLE_APPLICATION_CREDENTIALS")):
            with self.subTest(stops=word):
                with self.assertRaises(ValueError) as error:
                    self.connect(settings={"env": body})
                self.assertIn(word, str(error.exception))
                self.assertIn(str(self.config / "settings.json"), str(error.exception))
                self.assertNotIn("secret", str(error.exception))
        managed = self.managed / "managed-settings.json"
        managed.write_text(json.dumps({"env": {"CLAUDE_CODE_USE_FOUNDRY": "1"}}), encoding="utf-8")
        with self.assertRaises(ValueError) as error:
            self.connect(settings={"env": {}})
        self.assertIn(str(managed), str(error.exception))

    def test_settings_provider_is_resolved_before_the_saved_login(self):
        """設定で Bedrock を選び、保存済みのログインも在る時、resolve は旗を出どころに採り、既定のログインのトークンを足さない"""
        self.cloud_world()
        write_credentials(self.config)
        p, _ = self.connect(settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-east-1"}})
        env = auth_launch.profile_env({"HOME": str(self.real)}, p)
        got, name, why = auth_launch.resolve(env, str(self.real), "", platform="linux", runner=keychain({}), managed_dir=self.managed)
        self.assertIsNone(why)
        self.assertEqual(name, "CLAUDE_CODE_USE_BEDROCK")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", got)
        self.assertEqual(got["CLAUDE_CODE_USE_BEDROCK"], "1")

    def test_parent_cloud_values_are_carried_through_the_profile(self):
        """親の env の Mantle・Bedrock の旗と SKIP_*_AUTH と地域は profile['env'] に入り、Archon が CLAUDE_CODE_* を消した後も
        fence の connection_env で戻る。許可リストの外の名は入らない"""
        self.cloud_world()
        fence = place.shared("fence")
        for flag, skip in (("CLAUDE_CODE_USE_MANTLE", "CLAUDE_CODE_SKIP_MANTLE_AUTH"),
                           ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_SKIP_BEDROCK_AUTH")):
            with self.subTest(flag=flag):
                p, _ = self.connect({flag: "1", skip: "1", "AWS_REGION": "us-west-2", "UNRELATED": "no", "ANTHROPIC_API_KEY": "k"})
                self.assertEqual(p["env"], {flag: "1", skip: "1", "AWS_REGION": "us-west-2"})
                after_archon = {"HOME": "/factory/home", "UNRELATED": "no"}   # Archon の掃除の後（CLAUDE_CODE_* は無い）
                profile = fence.connection({fence.PROFILE_ENV: json.dumps(p)})
                fence.connection_env(after_archon, profile)
                self.assertEqual((after_archon[flag], after_archon[skip], after_archon["AWS_REGION"]), ("1", "1", "us-west-2"))
        p, _ = self.connect({"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_API_KEY": "dummy", "UNRELATED": "no"})
        self.assertEqual(p["env"], {"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_API_KEY": "dummy"})

    def test_parent_flag_names_the_settings_connection_values_it_does_not_carry(self):
        """旗を親の env で立てた道は、設定の env の接続先・alias・proxy を運ばない。黙らず、名だけを告知に言う（値は言わない）。
        設定の direct の資格は provider が勝つので名指さない。名指す物が無ければ告知に足さない"""
        self.cloud_world()
        settings = {"env": {"ANTHROPIC_BASE_URL": "https://gw.invalid", "ANTHROPIC_DEFAULT_SONNET_MODEL": "alias-sonnet",
                            "HTTPS_PROXY": "http://proxy.invalid", "ANTHROPIC_API_KEY": "settings-key"}}
        p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-west-2"}, settings)
        self.assertEqual(p["env"], {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_REGION": "us-west-2"})
        self.assertEqual(p["settings"], {})
        for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "HTTPS_PROXY"):
            self.assertIn(name, notice)
        self.assertNotIn("ANTHROPIC_API_KEY", notice)
        for value in ("gw.invalid", "alias-sonnet", "proxy.invalid", "settings-key"):
            self.assertNotIn(value, notice)
        _, quiet = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1"}, {"env": {"ANTHROPIC_API_KEY": "settings-key"}})
        self.assertNotIn("運ばない", quiet)

    @unittest.skipIf(sys.platform == "win32", "SKIP windows: sh の包み")
    def test_home_based_aws_profile_gets_an_export_wrapper(self):
        """AWS_PROFILE と本当の HOME の ~/.aws/config と PATH の aws が在れば、置き口に包みが書かれ、settings の awsCredentialExport がその
        パスを shlex でくくった字（HOME が空白を含んでも 1 語）になる。包みは本当の HOME・XDG と --profile で aws を起こす"""
        self.cloud_world()
        self.fake_aws()
        (self.real / ".aws").mkdir()
        (self.real / ".aws" / "config").write_text("[profile dev]\n", encoding="utf-8")
        p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "dev", "AWS_SESSION_TOKEN": "dummy-session-token",
                                  "XDG_CONFIG_HOME": "/real-xdg"})
        command = p["settings"]["awsCredentialExport"]
        (path,) = shlex.split(command)
        self.assertEqual(command, shlex.quote(path))
        self.assertTrue(path.startswith(str(self.tmp / "fence dir")) and os.access(path, os.X_OK))
        self.assertEqual(p["env"]["AWS_CONFIG_FILE"], str(self.real / ".aws" / "config"))
        self.assertNotIn("AWS_SHARED_CREDENTIALS_FILE", p["env"])
        done = self.run_wrapper(command)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(),
                         "home=%s xdg=/real-xdg args=configure export-credentials --format process --profile dev" % self.real)
        for text in (pathlib.Path(path).read_text(encoding="utf-8"), json.dumps(p["settings"]), notice):
            self.assertNotIn("dummy-session-token", text)
        self.assertIn("既定の aws の包み", notice)

    def test_aws_without_the_cli_passes_files_and_names_an_unresolvable_profile(self):
        """aws が無くても止まらない。渡せる物は渡し、渡せない物は告知で名指す（値は言わない）"""
        self.cloud_world()
        (self.real / ".aws").mkdir()
        (self.real / ".aws" / "credentials").write_text("dummy-credentials-body", encoding="utf-8")
        with self.subTest("a: aws が無い"):
            p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1"})
            self.assertEqual(p["env"]["AWS_SHARED_CREDENTIALS_FILE"], str(self.real / ".aws" / "credentials"))
            self.assertNotIn("awsCredentialExport", p["settings"])
            self.assertIn("aws の CLI が無い", notice)
            self.assertNotIn("dummy-credentials-body", notice)
        (self.real / ".aws" / "credentials").unlink()
        (self.real / ".aws").rmdir()
        elsewhere = self.tmp / "elsewhere-credentials"
        with self.subTest("b: 親が絶対パスで置いた"):
            p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "dev", "AWS_SHARED_CREDENTIALS_FILE": str(elsewhere)})
            self.assertEqual(p["env"]["AWS_SHARED_CREDENTIALS_FILE"], str(elsewhere))
            self.assertNotIn("MDM", notice)
        self.fake_aws()
        with self.subTest("c: HOME に頼らない資格が在れば包みは書かない"):
            p, _ = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "dev", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/credentials/x"})
            self.assertNotIn("awsCredentialExport", p["settings"])
            self.assertFalse((self.tmp / "fence dir").exists())
        with self.subTest("d: 解けない AWS_PROFILE は止めずに名指す"):
            p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "prod-profile"})
            self.assertEqual(p["env"], {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "prod-profile"})
            for word in ("prod-profile", "MDM", "awsCredentialExport", "~/.aws", "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "settings.json"):
                self.assertIn(word, notice)
        managed = self.managed / "managed-settings.json"
        managed.write_text(json.dumps({"awsCredentialExport": "managed-secret-command"}), encoding="utf-8")
        (self.real / ".aws").mkdir()
        (self.real / ".aws" / "config").write_text("[default]\n", encoding="utf-8")
        with self.subTest("e: 管理者の awsCredentialExport は包みを置くかの判断に使わない"):
            p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1"})
            self.assertIn("awsCredentialExport", p["settings"])
            self.assertIn(str(managed), notice)
            self.assertIn("Claude Code 自身が管理者の設定", notice)
            self.assertIn("から走らせる", notice)
            self.assertIn("remote や MDM", notice)
            self.assertNotIn("AWS_PROFILE は解かない", notice)
            self.assertNotIn("managed-secret-command", notice)

    @unittest.skipIf(sys.platform == "win32", "SKIP windows: sh の包み")
    def test_user_credential_export_is_wrapped_with_the_real_home(self):
        """利用者の settings.json の awsCredentialExport は、旗を設定の env で立てても親の env で立てても、包みにくるまれる。包みはコマンドの字を
        持たず、走るたびに元ファイルから読み直し、本当の HOME と元ファイルの env で走る。管理者も同じ鍵を持てば告知で名指す"""
        self.cloud_world()
        user = {"awsCredentialExport": "echo \"$MY_SSO_URL home=$HOME\"", "env": {"MY_SSO_URL": "https://sso.invalid"}}
        for where in ("設定の env", "親の env"):
            with self.subTest(flag=where):
                settings = {**user, "env": {**user["env"], **({"CLAUDE_CODE_USE_BEDROCK": "1"} if where == "設定の env" else {})}}
                p, notice = self.connect({} if where == "設定の env" else {"CLAUDE_CODE_USE_BEDROCK": "1"}, settings)
                self.assertNotIn("MY_SSO_URL", p["env"])
                command = p["settings"]["awsCredentialExport"]
                (path,) = shlex.split(command)
                self.assertNotIn("MY_SSO_URL", pathlib.Path(path).read_text(encoding="utf-8"))
                done = self.run_wrapper(command)
                self.assertEqual((done.returncode, done.stdout.strip()), (0, "https://sso.invalid home=%s" % self.real), done.stderr)
                self.assertIn("利用者の設定", notice)
        write_settings(self.config, {**user, "awsCredentialExport": "echo changed"})
        self.assertEqual(self.run_wrapper(command).stdout.strip(), "changed")
        managed = self.managed / "managed-settings.json"
        managed.write_text(json.dumps({"awsCredentialExport": "managed-secret-command"}), encoding="utf-8")
        p, notice = self.connect({"CLAUDE_CODE_USE_BEDROCK": "1"}, user)
        self.assertEqual(p["settings"]["awsCredentialExport"], command)   # 管理者が同じ鍵を持っても、包みと settings は同じに置く
        self.assertIn(str(managed), notice)
        self.assertIn("Claude Code 自身が管理者の設定", notice)
        self.assertNotIn("managed-secret-command", notice)
        managed.unlink()
        broken = self.config / "settings.json"
        broken.write_text("not json", encoding="utf-8")
        p, notice = auth_launch.connection_profile(self.config, {"HOME": str(self.real), "PATH": str(self.bin), "CLAUDE_CODE_USE_BEDROCK": "1"},
                                                   self.managed, self.put)
        self.assertEqual(p["env"], {"CLAUDE_CODE_USE_BEDROCK": "1"})
        self.assertNotIn("awsCredentialExport", p["settings"])
        self.assertEqual(notice.count(str(broken)), 1)
        # 包みの子は、元ファイルに awsCredentialExport が無い・aws を起こせない時、標準エラーに 1 行（コマンドの字・資格は言わない）で 2。
        # --source と --aws のどちらも無い起動は使い方の誤りで 2
        write_settings(self.config, {"env": {"MY_SECRET": "dummy-secret-env"}})
        base = [sys.executable, "-I", str(CORE / "auth_launch.py"), "credential-export", "--user-home", str(self.real),
                "--user-config", str(self.config)]
        for extra in (["--source", str(self.config / "settings.json")], ["--aws", str(self.bin / "no-such-aws")], []):
            with self.subTest(extra=extra):
                done = subprocess.run([*base, *extra], env=hermetic.child_env(PATH="/usr/bin:/bin"), capture_output=True, text=True,
                                      encoding="utf-8", timeout=60)
                self.assertEqual((done.returncode, done.stdout), (2, ""), done.stderr)
                self.assertTrue(done.stderr.strip())
                self.assertNotIn("dummy-secret-env", done.stderr)

    def test_vertex_adc_file_is_passed_by_absolute_path(self):
        """Vertex で GOOGLE_APPLICATION_CREDENTIALS も SKIP も無く、本当の HOME（か CLOUDSDK_CONFIG）の ADC ファイルが在れば、その絶対パスを渡す。
        中身は読まない。無ければ止めずに名指す"""
        self.cloud_world()
        adc = self.real / ".config" / "gcloud" / "application_default_credentials.json"
        p, notice = self.connect({"CLAUDE_CODE_USE_VERTEX": "1"})
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", p["env"])
        self.assertIn("ADC", notice)
        adc.parent.mkdir(parents=True)
        adc.write_text("dummy-adc-body", encoding="utf-8")
        p, notice = self.connect({"CLAUDE_CODE_USE_VERTEX": "1"})
        self.assertEqual(p["env"]["GOOGLE_APPLICATION_CREDENTIALS"], str(adc))
        self.assertNotIn("dummy-adc-body", json.dumps(p) + notice)
        p, _ = self.connect({"CLAUDE_CODE_USE_VERTEX": "1", "GOOGLE_APPLICATION_CREDENTIALS": "/own/adc.json"})
        self.assertEqual(p["env"]["GOOGLE_APPLICATION_CREDENTIALS"], "/own/adc.json")
        other = self.tmp / "gcloud-config"
        other.mkdir()
        (other / "application_default_credentials.json").write_text("{}", encoding="utf-8")
        p, _ = self.connect({"CLAUDE_CODE_USE_VERTEX": "1", "CLOUDSDK_CONFIG": str(other)})
        self.assertEqual(p["env"]["GOOGLE_APPLICATION_CREDENTIALS"], str(other / "application_default_credentials.json"))

    def test_auth_refresh_settings_are_named_not_carried(self):
        """利用者の awsAuthRefresh は運ばず止めず、鍵の名と出どころを言って「工場では走らせない」と言う。管理者の物（gcpAuthRefresh も）は
        Claude Code 自身が走らせる（工場は止めない）と言う。どちらもコマンドの字は言わない"""
        self.cloud_world()
        p, notice = self.connect(settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}, "awsAuthRefresh": "aws sso login secret-user-command"})
        self.assertEqual(p["env"], {"CLAUDE_CODE_USE_BEDROCK": "1"})
        self.assertNotIn("awsAuthRefresh", json.dumps(p))
        for word in ("awsAuthRefresh", str(self.config / "settings.json"), "工場では走らせない"):
            self.assertIn(word, notice)
        self.assertNotIn("secret-user-command", notice)
        managed = self.managed / "managed-settings.json"
        managed.write_text(json.dumps({"awsAuthRefresh": "secret-managed-aws", "gcpAuthRefresh": "secret-managed-gcp"}), encoding="utf-8")
        p, notice = self.connect(settings={"env": {"CLAUDE_CODE_USE_BEDROCK": "1"}, "awsAuthRefresh": "secret-user-command"})
        self.assertNotIn("Refresh", json.dumps(p))
        for word in ("awsAuthRefresh", "gcpAuthRefresh", str(managed), "Claude Code 自身が管理者の設定", "工場は止めない"):
            self.assertIn(word, notice)
        self.assertNotIn("工場では走らせない", notice)
        self.assertNotIn("AWS_PROFILE は解かない", notice)
        for secret in ("secret-managed-aws", "secret-managed-gcp", "secret-user-command"):
            self.assertNotIn(secret, notice)

    def test_foundry_parent_values_are_restored_without_fetching_credentials(self):
        parent = {"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_API_KEY": "dummy",
                  "ANTHROPIC_FOUNDRY_RESOURCE": "dummy-resource"}
        p, _ = self.profile({}, parent)
        self.assertEqual(p["env"], parent)
        got, name, why = auth_launch.resolve(parent, str(self.tmp), "", platform="linux", runner=keychain({}))
        self.assertEqual((got, name, why), (parent, "CLAUDE_CODE_USE_FOUNDRY", None))

    def test_named_item_remains_above_settings_credentials(self):
        p, deferred = self.profile({"env": {"ANTHROPIC_API_KEY": "selected"}}, {auth_launch.ITEM_ENV: "named"})
        self.assertEqual(p, {"settings": {}, "env": {}, "drop": []})

    def test_managed_connection_fields_override_user_in_existing_file_order(self):
        managed = self.tmp / "managed"
        (managed / "managed-settings.d").mkdir(parents=True)
        write_settings(self.tmp, {"env": {"ANTHROPIC_API_KEY": "user", "ANTHROPIC_BASE_URL": "https://user.invalid"}})
        (managed / "managed-settings.json").write_text(json.dumps({"env": {"ANTHROPIC_API_KEY": "managed"},
                                                                    "hooks": {"Stop": []}}))
        (managed / "managed-settings.d" / "20.json").write_text(json.dumps({"env": {"ANTHROPIC_API_KEY": "last"}}))
        (managed / "managed-settings.d" / "10.json").write_text(json.dumps({"env": {"ANTHROPIC_API_KEY": "first"}}))
        p, deferred = auth_launch.connection_profile(self.tmp, {}, managed)
        self.assertIn("20.json", deferred)   # 外す資格の出どころは、最後に効く管理者のファイル
        self.assertEqual(p["env"], {"ANTHROPIC_API_KEY": "last", "ANTHROPIC_BASE_URL": "https://user.invalid"})
        self.assertNotIn("hooks", p["settings"])

    def test_helper_dependencies_only_enter_the_helper_process(self):
        source = self.tmp / "settings.json"
        write_settings(self.tmp, {"apiKeyHelper": "NEVER_RUN", "env": {"HELPER_INPUT": "dummy-secret",
                                                                       "HOME": "/unsafe", "UNNEEDED": "helper-only"}})
        ai = {"HOME": "/factory", "CLAUDE_CONFIG_DIR": "/factory/config", "ARCHON_HOME": "/factory/archon",
              auth_launch.userenv.RECORD: json.dumps({"HOME": "/user", "XDG_CONFIG_HOME": "/user/xdg"})}
        env = auth_launch.helper_settings_env(ai, "/user", str(self.tmp), str(source))
        self.assertEqual(env["HELPER_INPUT"], "dummy-secret")
        self.assertEqual(env["HOME"], "/user")
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(self.tmp))
        self.assertEqual(env["XDG_CONFIG_HOME"], "/user/xdg")
        self.assertNotIn("HELPER_INPUT", ai)
        self.assertEqual(ai["HOME"], "/factory")
        self.assertNotIn(auth_launch.userenv.RECORD, set(env))

    def test_actual_helper_spawn_receives_dependencies_without_mutating_ai_env(self):
        source = self.tmp / "settings.json"
        write_settings(self.tmp, {"apiKeyHelper": "NEVER_RUN", "env": {"HELPER_INPUT": "dummy-private-input"}})
        ai = {"HOME": "/factory", "CLAUDE_CONFIG_DIR": "/factory/config"}
        with mock.patch.object(auth_launch.os, "environ", ai), mock.patch.object(auth_launch.subprocess, "run") as run, \
                mock.patch.object(sys, "stderr", io.StringIO()):
            auth_launch.user_helper_runner("NEVER_RUN", "/user", str(self.tmp), str(source))
        self.assertEqual(run.call_args.kwargs["env"]["HELPER_INPUT"], "dummy-private-input")
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], "/user")
        self.assertEqual(ai, {"HOME": "/factory", "CLAUDE_CONFIG_DIR": "/factory/config"})
        self.assertEqual(run.call_args.args, ("NEVER_RUN",))
        self.assertNotIn("dummy-private-input", str(run.call_args.args))

    def test_managed_helper_receives_split_env_in_file_order_only_in_its_child(self):
        """E15・E24: 管理者の helper は同じ層の分割 env を継ぐ。user 設定・AI の家・argv へ秘密を混ぜない。"""
        managed = self.tmp / "managed"
        parts = managed / "managed-settings.d"
        parts.mkdir(parents=True)
        write_settings(self.tmp, {"env": {"USER_ONLY": "not-for-managed-helper"}})
        (managed / "managed-settings.json").write_text(json.dumps({"env": {"HELPER_INPUT": "first"}}))
        source = parts / "10.json"
        source.write_text(json.dumps({"apiKeyHelper": "NEVER_RUN", "env": {"HELPER_INPUT": "middle"}}))
        (parts / "20.json").write_text(json.dumps({"env": {"HELPER_INPUT": "dummy-last-secret", "ARCHON_HOME": "/unsafe"}}))
        ai = {"HOME": "/factory", "CLAUDE_CONFIG_DIR": "/factory/config", "ARCHON_HOME": "/factory/archon",
              auth_launch.userenv.RECORD: json.dumps({"HOME": str(self.tmp), "XDG_CONFIG_HOME": "/user/xdg"})}
        with mock.patch.object(auth_launch.os, "environ", ai), mock.patch.object(auth_launch.subprocess, "run") as run, \
                mock.patch.object(sys, "stderr", io.StringIO()):
            run.return_value = types.SimpleNamespace(stdout="dummy-key", returncode=0)
            got, name, why = auth_launch.resolve(ai, str(self.tmp), str(self.tmp), platform="linux",
                                                runner=keychain({}), managed_dir=managed)
        self.assertEqual(got, {"ANTHROPIC_API_KEY": "dummy-key"})
        self.assertIsNone(why)
        self.assertIn(str(source), name)
        child = run.call_args.kwargs["env"]
        self.assertEqual(child["HELPER_INPUT"], "dummy-last-secret")
        self.assertEqual(child["HOME"], str(self.tmp))
        self.assertEqual(child["CLAUDE_CONFIG_DIR"], str(self.tmp))
        self.assertEqual(child["ARCHON_HOME"], "/factory/archon")
        self.assertEqual(child["XDG_CONFIG_HOME"], "/user/xdg")
        self.assertNotIn("USER_ONLY", child)
        self.assertNotIn("HELPER_INPUT", ai)
        self.assertEqual(ai["HOME"], "/factory")
        self.assertNotIn("dummy-last-secret", str(run.call_args.args))
        self.assertEqual(run.call_count, 1)

    def test_split_helper_skips_absent_siblings_but_not_its_selected_source(self):
        source = self.tmp / "managed-settings.json"
        source.write_text(json.dumps({"apiKeyHelper": "NEVER_RUN", "env": {"HELPER_INPUT": "dummy"}}))
        absent = self.tmp / "absent.json"
        env = auth_launch.helper_settings_env({}, "/user", "/config", str(source), [absent, source])
        self.assertEqual(env["HELPER_INPUT"], "dummy")
        source.unlink()
        with self.assertRaises(ValueError):
            auth_launch.helper_settings_env({}, "/user", "/config", str(source), [absent, source])
        with self.assertRaises(ValueError):
            auth_launch.helper_settings_env({}, "/user", "/config", str(source), [absent])

    def test_bad_split_helper_env_stops_without_spawn_or_login_fallback(self):
        managed = self.tmp / "managed"
        parts = managed / "managed-settings.d"
        parts.mkdir(parents=True)
        (managed / "managed-settings.json").write_text(json.dumps({"apiKeyHelper": "NEVER_RUN"}))
        (parts / "20.json").write_text(json.dumps({"env": {"HELPER_INPUT": ["dummy-secret"]}}))
        write_credentials(self.tmp)
        with mock.patch.object(auth_launch.os, "environ", {}), mock.patch.object(auth_launch.subprocess, "run") as run, \
                mock.patch.object(sys, "stderr", io.StringIO()):
            got, name, why = auth_launch.resolve({}, str(self.tmp), str(self.tmp), platform="linux",
                                                runner=keychain({}), managed_dir=managed)
        self.assertIsNone(got)
        self.assertIn("apiKeyHelper", name)
        self.assertIn("ValueError", why)
        self.assertNotIn("dummy-secret", why)
        run.assert_not_called()

    def test_invalid_needed_value_fails_without_printing_values(self):
        with self.assertRaises(ValueError) as error:
            self.profile({"env": {"ANTHROPIC_API_KEY": ["dummy-secret"]}})
        self.assertNotIn("dummy-secret", str(error.exception))


class Howto(unittest.TestCase):
    """案内は名を毎回付けずに済ます道（Claude Code の settings.json の env）と、値を出さずに項目の在りかを確かめる命令を言う。
    持ち主の項目の名は書かず、置き場の字で言う"""

    def test_names_the_settings_env_route(self):
        self.assertIn('settings.json の env に "%s": "<項目の名>"' % auth_launch.ITEM_ENV, auth_launch.HOWTO)

    def test_names_the_api_key_route(self):
        """API キーの道（ANTHROPIC_API_KEY）と、apiKeyHelper の道を言い、設定の env の接続の値は子に運ぶことを言う（運ばないとは言わない）"""
        for word in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "apiKeyHelper"):
            self.assertIn(word, auth_launch.HOWTO)
        self.assertNotIn("子には運ばない", auth_launch.HOWTO)
        for word in ("設定の env に書いた接続の値", "Bedrock・Mantle・Vertex", "は子に運ぶ", "フック・権限・プラグインは運ばない"):
            self.assertIn(word, auth_launch.HOWTO)

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
        """控えが無い時（殻を通らない単独の check など）は、環境の XDG_* をそのまま渡す"""
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

    def fake_runtime(self, tmp, status, code=0, ask=False):
        """auth status に status（字）を返す起動方法の偽（sh のファイル）。ask なら標準エラーに問いの 1 行を書き、標準入力を読み切ってから返す。
        auth status 以外で呼ばれたら 9 で終わる"""
        runtime = tmp / "wrapper"
        runtime.write_text("#!/bin/sh\nif [ \"$1\" = auth ] && [ \"$2\" = status ]; then\n"
                           + ("  echo FAKE-ASK >&2\n  cat >/dev/null\n" if ask else "")
                           + "  printf '%s\\n' '" + status + "'\n  exit " + str(code) + "\nfi\nexit 9\n", encoding="utf-8")
        runtime.chmod(0o755)
        return runtime

    def with_saved_login(self, tmp):
        """Claude Code の保存済みのログインを偽で置く（macOS は keychain の項目、ほかは .credentials.json）。返すのは PATH の頭の置き場"""
        write_credentials(tmp / "user-config")
        return self.fake_security(tmp, "Claude Code-credentials")

    def start(self, cmd, tmp, runtime, bin_dir, *rest, **env):
        args = [sys.executable, "-I", str(CORE / "auth_launch.py"), cmd, "--for", "bin/start", "--user-home", str(tmp / "user"),
                "--user-config", str(tmp / "user-config"), "--managed-dir", str(tmp / "managed"), "--runtime", str(runtime), *rest]
        env = hermetic.child_env(HOME=str(tmp / "iso"), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), **env)
        return subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)

    def test_runtime_with_its_own_auth_starts_without_the_saved_login(self):
        """起動方法が auth status で自分の認証を言えば、他の出どころが無くても check は 0 で、出どころに起動方法のパスを言う。
        exec は、保存済みのログインが在っても子に CLAUDE_CODE_OAUTH_TOKEN を足さない。claude.ai の時は、ラッパーが設定の置き場を替えている見込みと
        役が利用者の設定で走りうることを、出どころの字に添える（止めない）。email は出さない"""
        probe = "import os; print(os.environ.get('CLAUDE_CODE_OAUTH_TOKEN'))"
        for method in ("api_key", "claude.ai"):
            with self.subTest(method=method):
                tmp = hermetic.tmpdir(self)
                bin_dir = self.with_saved_login(tmp)
                runtime = self.fake_runtime(tmp, '{"authMethod":"%s","email":"someone@example.invalid"}' % method)
                checked = self.start("check", tmp, runtime, bin_dir)
                self.assertEqual(checked.returncode, 0, checked.stderr)
                line = checked.stdout.strip()
                self.assertIn(str(runtime), line)
                self.assertIn(method, line)
                self.assertNotIn("someone@example.invalid", checked.stdout + checked.stderr)
                if method == "claude.ai":
                    self.assertIn("CLAUDE_CONFIG_DIR か HOME を替えている見込み", line)
                    self.assertIn("hooks・permissions・plugins", line)
                    self.assertEqual(line, "起動方法 %s の認証（claude.ai。注意: ラッパーが CLAUDE_CONFIG_DIR か HOME を替えている見込み。"
                                           "役は利用者の設定（hooks・permissions・plugins）で走りうる。鍵を環境変数に置く形にする）" % runtime)
                else:
                    self.assertNotIn("見込み", line)
                started = self.start("exec", tmp, runtime, bin_dir, "--", sys.executable, "-I", "-c", probe)
                self.assertEqual((started.returncode, started.stdout.strip()), (0, "None"), started.stderr)
                self.assertNotIn(TOKEN, started.stdout + started.stderr)

    def test_runtime_without_auth_stops_instead_of_the_saved_login(self):
        """起動方法が none を言う・JSON でない・終了コードが 0 でない時は、保存済みのログインが在っても check は HOWTO で 2。
        理由は起動方法のパスと逃げ道を名指す。逃げ道は RUNTIME_ESCAPES の 1 か所だけが言い、止める 1 行に 1 度だけ出る。exec も子を起こさない"""
        cases = (('{"authMethod":"none"}', 0), ("not json", 0), ('{"loggedIn":true}', 0), ('{"authMethod":"api_key"}', 1))
        for status, code in cases:
            with self.subTest(status=status, code=code):
                tmp = hermetic.tmpdir(self)
                bin_dir = self.with_saved_login(tmp)
                runtime = self.fake_runtime(tmp, status, code)
                for cmd, rest in (("check", ()), ("exec", ("--", sys.executable, "-c", "print('started')"))):
                    done = self.start(cmd, tmp, runtime, bin_dir, *rest)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertEqual(done.stdout, "")
                    lines = done.stderr.strip().splitlines()
                    self.assertTrue(lines[-1].startswith("bin/start: " + auth_launch.HOWTO), done.stderr)
                    self.assertEqual(len(lines), 2, done.stderr)   # 起動方法を待つ 1 行と、止める 1 行
                    for word in (str(runtime), "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_BIN_PATH"):
                        self.assertIn(word, lines[-1])
                    self.assertEqual(lines[-1].count(auth_launch.RUNTIME_ESCAPES), 1, done.stderr)
                    self.assertEqual(lines[-1].count("保存済みのログイン"), 1, done.stderr)
                    self.assertNotIn(TOKEN, done.stderr)
        self.assertTrue(auth_launch.HOWTO.startswith("認証が無いか、確かめられない"))
        self.assertIn("ラッパーを CLAUDE_BIN_PATH で渡せる", auth_launch.HOWTO)

    def test_runtime_probe_shows_its_stderr_and_gets_no_stdin(self):
        """起動方法の確かめは標準エラーを捕まえず端末へ流し（問いが見える）、起動方法を待つ 1 行を出し、標準入力は渡さない
        （閉じない管を渡されても待たずに終わる）"""
        tmp = hermetic.tmpdir(self)
        bin_dir = self.with_saved_login(tmp)
        runtime = self.fake_runtime(tmp, '{"authMethod":"api_key"}', ask=True)
        args = [sys.executable, "-I", str(CORE / "auth_launch.py"), "check", "--user-home", str(tmp / "user"),
                "--managed-dir", str(tmp / "managed"), "--runtime", str(runtime)]
        env = hermetic.child_env(HOME=str(tmp / "iso"), PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        proc = subprocess.Popen(args, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")
        try:
            proc.wait(timeout=30)
            out, err = proc.stdout.read(), proc.stderr.read()
        finally:
            proc.kill()
            proc.wait()
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                pipe.close()
        self.assertEqual(proc.returncode, 0, err)
        self.assertIn(str(runtime), out)
        self.assertIn("FAKE-ASK", err)
        self.assertIn(str(runtime), err)
        self.assertIn("終わるまで待つ", err)


if __name__ == "__main__":
    unittest.main()
