"""run の中で利用者の gh のログインを継ぐ口（bin/_lib/hostgh.py）の検査。

実の利用者の run 97fd532f の事実: 今の works の開発の殻（dev/archon.sh）は HOME・XDG_* を隔離して Archon を起こすので、run の中の gh は
利用者のログインが見えず、並行 PR の確かめ（写しの parallel-pr.py）が毎回 gh の失敗で人待ちになり、1 周の run が単位を
閉じ最後の試験も緑なのに round_limit で終わった。持ち主の決定（2026-10-08）: run の中の gh は利用者の gh を継ぐ（本流の
review-graph は利用者の環境のまま gh を打つ）。gh の設定の置き場は隔離の前に解き（GH_CONFIG_DIR、無ければ
$XDG_CONFIG_HOME/gh、無ければ ~/.config/gh）、macOS の keychain に置いたトークン（gh の既定）は keychain を HOME から探す
（隔離した HOME では login の keychain が探す先に無い。2026-10-08 に security list-keychains で確かめた）ので、gh だけを
利用者の HOME で起こす口を PATH の頭に置く。トークンは写さない・出さない・置かない（口は gh・HOME・設定の置き場のパスだけ）。

環境変数だけで gh にログインする利用者（#132）: 起動は 4 つのトークンの名を子から外したまま、値を gh の読まない名
（hostgh.RELAY）で子に渡す。口は本物の gh を起こす時だけそれを gh の名へ戻し、渡しの名は本物の gh に見せない。口のファイルには名
だけを書き、値は書かない。

偽の gh（受けた HOME・GH_CONFIG_DIR・引数と、トークンが期待の値で届いたかを記録し、GH_CONFIG_DIR の hosts.yml が在る時だけ 0）で
縛る。本物の gh・GitHub に
触れない。関数を直に呼ぶ・sh の口を子で起こすだけ（git・盤面なし）。
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TESTS = pathlib.Path(__file__).resolve().parent
DEV = TESTS.parents[1] / "bin" / "_lib"
sys.dont_write_bytecode = True
sys.path.insert(0, str(DEV))
sys.path.insert(0, str(TESTS))

import hostgh  # noqa: E402
from tests.bin import hermetic  # noqa: E402

NO_POST_BIN = DEV / "no-post-bin"
GITHUB_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
FAKE = "ghp_fake-for-hostgh"


def fake_gh(bindir: pathlib.Path, log: pathlib.Path) -> pathlib.Path:
    """偽の gh。<log>.tokens に「GH_TOKEN|GH_ENTERPRISE_TOKEN|渡しの名の数」を 1 行で書く。トークンは値を書かず、FAKE と
    同じなら ok・違えば other・無ければ missing"""
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text("#!/bin/sh\n"
                  f'printf \'%s|%s|%s\\n\' "$HOME" "${{GH_CONFIG_DIR-(unset)}}" "$*" >> "{log}"\n'
                  'state() { if [ -z "$2" ]; then echo missing; elif [ "$2" = "$1" ]; then echo ok; else echo other; fi; }\n'
                  f'printf \'%s|%s|%s\\n\' "$(state {FAKE} "${{GH_TOKEN-}}")" "$(state {FAKE} "${{GH_ENTERPRISE_TOKEN-}}")" '
                  f'"$(env | grep -c \'^WORKS_FACTORY_HOST_\')" >> "{log}.tokens"\n'
                  '[ -f "${GH_CONFIG_DIR:-/nonexistent}/hosts.yml" ] || { echo "You are not logged into any GitHub hosts." >&2; exit 4; }\n'
                  'echo "Logged in to github.com"\n', encoding="utf-8")
    gh.chmod(0o755)
    return gh


class ConfigDirCase(unittest.TestCase):
    def test_order(self):
        """GH_CONFIG_DIR、無ければ $XDG_CONFIG_HOME/gh、無ければ $HOME/.config/gh（gh 自身の決め方。空は無いのと同じ）"""
        self.assertEqual(hostgh.config_dir({"GH_CONFIG_DIR": "/g", "XDG_CONFIG_HOME": "/x", "HOME": "/h"}), "/g")
        self.assertEqual(hostgh.config_dir({"GH_CONFIG_DIR": "", "XDG_CONFIG_HOME": "/x", "HOME": "/h"}), "/x/gh")
        self.assertEqual(hostgh.config_dir({"XDG_CONFIG_HOME": "", "HOME": "/h"}), "/h/.config/gh")


class RelayCase(unittest.TestCase):
    """起動が子に渡すトークン: gh 自身の先後（GH_TOKEN が GITHUB_TOKEN より先）で 1 つ。GHES の名は GHES の名の行へ。空は無いのと同じ"""

    def test_github_row_prefers_gh_token(self):
        self.assertEqual(hostgh.relay({"GH_TOKEN": "a", "GITHUB_TOKEN": "b"}), {"WORKS_FACTORY_HOST_GH_TOKEN": "a"})
        self.assertEqual(hostgh.relay({"GH_TOKEN": "", "GITHUB_TOKEN": "b"}), {"WORKS_FACTORY_HOST_GH_TOKEN": "b"})

    def test_enterprise_row_is_its_own(self):
        self.assertEqual(hostgh.relay({"GITHUB_ENTERPRISE_TOKEN": "e", "GITHUB_TOKEN": "b"}),
                         {"WORKS_FACTORY_HOST_GH_TOKEN": "b", "WORKS_FACTORY_HOST_GH_ENTERPRISE_TOKEN": "e"})

    def test_no_token_relays_nothing(self):
        self.assertEqual(hostgh.relay({"HOME": "/h", "GH_TOKEN": ""}), {})

    def test_relay_names_are_not_read_by_gh(self):
        """渡しの名は gh の読む名（GH_・GITHUB_ で始まる）でない"""
        for relay, _ in hostgh.RELAY:
            self.assertFalse(relay.startswith(("GH_", "GITHUB_")), relay)

    def test_relay_names_end_with_token(self):
        """Archon の記録の伏せ字は名が TOKEN で終わる値に効く。名を変えると黙って伏せ字から外れる"""
        for relay, _ in hostgh.RELAY:
            self.assertTrue(relay.endswith("_TOKEN"), relay)


class ShimCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = pathlib.Path(self._td.name).resolve()
        self.log = self.tmp / "gh-log.txt"
        self.user_home = self.tmp / "user home"   # 空白を持つパスも口の中で崩れない
        self.config = self.user_home / ".config" / "gh"
        self.config.mkdir(parents=True)
        (self.config / "hosts.yml").write_text("github.com:\n    user: someone\n", encoding="utf-8")
        self.real = fake_gh(self.tmp / "real bin", self.log)
        self.shim_dir = self.tmp / "host-gh"

    def write(self, path=None):
        return hostgh.write(self.shim_dir, path if path is not None else f"{self.real.parent}{os.pathsep}/usr/bin:/bin",
                            str(self.user_home), str(self.config))

    def isolated_env(self, shim):
        iso = self.tmp / "iso"
        env = hermetic.child_env(HOME=str(iso / "home"), XDG_CONFIG_HOME=str(iso / "xdg"),
                                 PATH=f"{os.path.dirname(shim)}{os.pathsep}/usr/bin:/bin")
        for name in ("GH_CONFIG_DIR", *GITHUB_TOKENS):
            env.pop(name, None)
        env["GH_TOKEN_PROBE"] = "ghp_SHOULDNOTAPPEAR"
        return env

    def tokens_seen(self, shim, **env):
        subprocess.run(["gh", "pr", "list"], env={**self.isolated_env(shim), **env}, capture_output=True, check=False)
        return pathlib.Path(f"{self.log}.tokens").read_text(encoding="utf-8").splitlines()[-1]

    def test_relayed_token_reaches_the_real_gh_as_gh_token(self):
        """環境変数だけでログインする利用者: 渡しの名の値が本物の gh に GH_TOKEN で届き、渡しの名は本物の gh に見えない"""
        shim = self.write()
        self.assertEqual(self.tokens_seen(shim, WORKS_FACTORY_HOST_GH_TOKEN=FAKE), "ok|missing|0")
        self.assertEqual(self.tokens_seen(shim, WORKS_FACTORY_HOST_GH_ENTERPRISE_TOKEN=FAKE), "missing|ok|0")

    def test_token_already_set_wins(self):
        """子に GH_TOKEN が在れば（Archon が節に渡したなど）口は上書きしない"""
        shim = self.write()
        self.assertEqual(self.tokens_seen(shim, GH_TOKEN=FAKE, WORKS_FACTORY_HOST_GH_TOKEN="ghp_other"), "ok|missing|0")

    def test_without_relay_the_shim_adds_no_token(self):
        """keychain・hosts.yml でログインする利用者は今のまま（口は値を足さない）"""
        self.assertEqual(self.tokens_seen(self.write()), "missing|missing|0")

    def test_isolated_env_sees_the_users_login_through_the_shim(self):
        """隔離した HOME・XDG の下でも、口の gh は利用者の HOME と gh の設定の置き場で本物の gh を起こす（引数・終了コードはそのまま）"""
        shim = self.write()
        self.assertEqual(os.path.dirname(os.path.dirname(shim)), str(self.shim_dir))
        r = subprocess.run(["gh", "auth", "status"], env=self.isolated_env(shim), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Logged in", r.stdout)
        home, conf, args = self.log.read_text(encoding="utf-8").splitlines()[-1].split("|")
        self.assertEqual((home, conf, args), (str(self.user_home), str(self.config), "auth status"))

    def test_no_user_login_behaves_as_today(self):
        """利用者の gh がどこにもログインしていなければ、gh の言葉と終了コードのまま（run の中は今どおり人待ち）"""
        (self.config / "hosts.yml").unlink()
        shim = self.write()
        r = subprocess.run(["gh", "pr", "list"], env=self.isolated_env(shim), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 4)
        self.assertIn("not logged", r.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").splitlines()[-1].split("|")[0], str(self.user_home))   # 口を通った

    def test_shim_holds_paths_only(self):
        """口はパスと名だけを持つ（トークンの値は env のどの名に在っても書かない）"""
        names = ("GH_TOKEN_PROBE", *GITHUB_TOKENS, *(relay for relay, _ in hostgh.RELAY))
        with mock.patch.dict(os.environ, dict.fromkeys(names, "ghp_SHOULDNOTAPPEAR")):
            text = pathlib.Path(self.write()).read_text(encoding="utf-8")
        self.assertNotIn("ghp_", text)

    def test_no_gh_on_path_writes_no_shim(self):
        """PATH に gh が無ければ口を置かない（run の中は今どおり gh が無い扱い。前の口は消さない——別の run が使っているかもしれない）"""
        first = self.write()
        self.assertIsNone(self.write(path=str(self.tmp / "empty")))
        self.assertTrue(os.path.isfile(first))

    def test_each_login_has_its_own_shim(self):
        """口の置き場は中身ごとに分かれる: 同じ家から並べた起動・入れ子の起動（隔離した HOME を継いだ殻）が、走っている run の口を
        書き換えない。同じ中身なら同じ口"""
        first = self.write()
        self.assertEqual(self.write(), first)
        other = hostgh.write(self.shim_dir, f"{self.real.parent}{os.pathsep}/usr/bin:/bin", str(self.tmp / "iso-home"),
                             str(self.tmp / "iso-home" / ".config" / "gh"))
        self.assertNotEqual(other, first)
        self.assertIn(str(self.user_home), pathlib.Path(first).read_text(encoding="utf-8"))

    def test_quoting_survives_quotes_and_dollars(self):
        """パスの ' と $ も口の中で崩れない（sh に解かせない）"""
        odd = self.tmp / "it's $HOME"
        odd.mkdir()
        shim = hostgh.write(self.shim_dir, f"{self.real.parent}{os.pathsep}/usr/bin:/bin", str(odd), str(self.config))
        subprocess.run(["gh", "x"], env=self.isolated_env(shim), capture_output=True, check=False)
        self.assertEqual(self.log.read_text(encoding="utf-8").splitlines()[-1].split("|")[0], str(odd))

    def test_skips_itself_and_the_read_only_gate(self):
        """PATH の上の口自身（入れ子の起動）と読むだけの口の置き場（no-post-bin）は本物と取り違えない"""
        first = self.write()
        path = os.pathsep.join([os.path.dirname(first), str(NO_POST_BIN), str(self.real.parent), "/usr/bin"])
        text = pathlib.Path(self.write(path=path)).read_text(encoding="utf-8")
        self.assertIn(str(self.real), text)
        self.assertNotIn(str(NO_POST_BIN), text)
        self.assertNotIn(os.path.dirname(first), text)


if __name__ == "__main__":
    unittest.main()
