"""選んだ物だけの隔離した Claude の設定（bin/_lib/toolset.py）の検査。

AI の節は全部 settingSources: [user] で、bin/ の起動が隔離した CLAUDE_CONFIG_DIR（bin/_lib/isolate.py）を読む。そこに置くのは
許す一覧（lib/borrow/borrow.json）の物だけ。借りる物の取り元は 2 つに分かれる:
- superpowers: works に写した固定の版（lib/borrow/superpowers/<版>/。VENDORED）だけから入れる。利用者の
  installed_plugins.json の superpowers の行は読まない（入っていなくても、別の版でも同じに組む）。写しが borrow.json の pin の
  sha256 と合わなければ、違うファイルを名指して何も写さずに止まる。5 つのスキルを skills/<名>/ へ、部品（parts）を
  works-parts/superpowers/<相対パス> へバイトのまま写す（プラグインとしては入れない。有効にすると SessionStart の hook が
  using-superpowers を差し込むため。裁定 P1-R8）。
- coldwrite・pr-review-toolkit: 利用者が Claude Code に入れたプラグインから取る（works は写しを持たない。版は Claude Code が
  今に保つ）。探す所は利用者の設定の置き場の plugins/installed_plugins.json の <名>@<marketplace> の行（user の行、次に
  projectPath が cwd の project・local の行）。入っていない・works が名前で頼る物（agent・hook）が無い借りる物は、1 物 1 行の
  理由と入れるコマンドを並べて止まる。中身・版・バイトは確かめない（試験が中身を見るのは、ここで作った偽のプラグインだけ）。
- pr-review-toolkit を、設定の中の手元の marketplace works-local（works-marketplace/）に写し、Claude Code の CLI
  （claude plugin marketplace add・install）で入れる。Claude Code のキャッシュの印（.in_use/・.orphaned_at）は写さない。
- coldwrite はプラグインとして入れず、hooks/hooks.json の表を settings.json の hooks に置く。書き込みの記録のフック
  （record-write.py）と読んだ証拠のフック（record-read.py）の行も同じ所に置き、記録の根 works-writes/・works-reads/ を作る。
柵（guard）は一覧の外（CLAUDE.md・rules/・agents/・commands/・output-styles/・settings.json 以外の settings*.json・
一覧の外のスキル・settings.json の許す鍵の外・一覧の外の marketplace）を名前で並べ、CLI は終了コード 2 で止まる。
Claude Code が自分で書く状態（projects/・.claude.json・backups/・remote-settings.json など）は見ない。

本物の claude も、利用者の本物の設定も使わない。偽の利用者の設定（make_user_config。偽のプラグインを入れた形）と、偽の claude
（FAKE_CLAUDE。受けた argv を記録し、本物の 2.1.283 と同じ形で settings.json・plugins/ の状態のファイルを書く）を渡す。
形は本物の CLI で一時の置き場に入れて確かめた（報告 $S/r61/cfg-report.md）。
"""
import datetime
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[2] / "bin" / "_lib"
TOOLSET = LIB / "toolset.py"
sys.dont_write_bytecode = True
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import toolset  # noqa: E402
import gitkit  # noqa: E402
import hermetic  # noqa: E402
import spseam  # noqa: E402
from tests import archon  # noqa: E402
from tests.bin import copyledger  # noqa: E402

BORROW = spseam.BORROW_DIR

BORROW_SKILLS = ["test-driven-development", "systematic-debugging", "verification-before-completion",
                 "receiving-code-review", "requesting-code-review"]
# 隔離した設定の superpowers の取り元（works に写した固定の版。本物の写しを読む）
VENDORED = spseam.vendored_dir(toolset.load_borrow(BORROW)["superpowers"])
LENSES = ["code-reviewer", "silent-failure-hunter", "type-design-analyzer", "pr-test-analyzer", "comment-analyzer"]
MP = "works-local"
# 偽の利用者の設定に入れる偽のプラグイン: 名 → (marketplace, キャッシュの版の置き場の名・installed_plugins.json の version)
# 利用者の設定が名指す coldwrite の marketplace（borrow.json には書かない。toolset.user_borrow）
COLDWRITE_MP, COLDWRITE_REPO = "cw-market", "someone/cw-plugins"
COLDWRITE_ENV = {"WORKS_FACTORY_COLDWRITE_MARKETPLACE": COLDWRITE_MP, "WORKS_FACTORY_COLDWRITE_MARKETPLACE_REPO": COLDWRITE_REPO}
FAKE_INSTALLED = {"superpowers": ("superpowers-marketplace", "9.9.0"), "coldwrite": (COLDWRITE_MP, "1.2.3"),
                  "pr-review-toolkit": ("claude-plugins-official", "abc123def456")}


def user_borrow() -> dict:
    """利用者の設定に coldwrite の marketplace が在る時の借りる物"""
    borrow, skipped = toolset.user_borrow(toolset.load_borrow(BORROW), COLDWRITE_ENV)
    assert skipped == [], skipped
    return borrow


def _put(p: pathlib.Path, body: str, mode=None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    if mode is not None:
        p.chmod(mode)


def make_user_config(base: pathlib.Path, only=None, scope="user", project=None) -> pathlib.Path:
    """偽の利用者の Claude の設定の置き場を base に作って返す（test_dev も使う）。plugins/installed_plugins.json に
    FAKE_INSTALLED の偽のプラグイン（only があればその名だけ）を scope の行で載せ、キャッシュの版の置き場に works が名前で頼る物
    （スキルの SKILL.md・agent の .md・hook）と、Claude Code の印（.in_use/・.orphaned_at）を置く"""
    base = pathlib.Path(base)
    rows = {}
    for name, (mp, ver) in FAKE_INSTALLED.items():
        if only is not None and name not in only:
            continue
        d = base / "plugins" / "cache" / mp / name / ver
        if name == "superpowers":
            _put(d / ".claude-plugin" / "plugin.json", json.dumps({"name": name, "version": ver}))
            for s in BORROW_SKILLS + ["brainstorming"]:
                _put(d / "skills" / s / "SKILL.md", f"---\nname: {s}\n---\n偽の {s}\n")
            _put(d / "skills" / "systematic-debugging" / "find-polluter.sh", "#!/bin/sh\n", 0o755)
            _put(d / "LICENSE", "MIT License\n\nCopyright (c) 2025 Test\n")
            for f in ("SKILL.md", "implementer-prompt.md", "task-reviewer-prompt.md"):   # 部品（parts）は 2 本だけを借りる
                _put(d / "skills" / "subagent-driven-development" / f, f"偽の {f}\n")
        elif name == "coldwrite":
            _put(d / ".claude-plugin" / "plugin.json", json.dumps({"name": name, "version": ver}))
            _put(d / "hooks" / "hooks.json", json.dumps({"hooks": COLDWRITE_HOOKS}))
        else:
            _put(d / ".claude-plugin" / "plugin.json", json.dumps({"name": name}))   # 本物と同じく version を持たない
            for a in LENSES + ["code-simplifier"]:
                _put(d / "agents" / f"{a}.md", f"---\nname: {a}\n---\n偽の {a}\n")
        _put(d / ".in_use" / "4242", "{}")
        _put(d / ".orphaned_at", "1790054446372")
        row = {"scope": scope, "installPath": str(d), "version": ver, "installedAt": "2026-09-28T00:00:00.000Z"}
        if project is not None:
            row["projectPath"] = str(project)
        rows[f"{name}@{mp}"] = [row]
    _put(base / "plugins" / "installed_plugins.json", json.dumps({"version": 2, "plugins": rows}, indent=2))
    return base


def installed_dir(user: pathlib.Path, name: str) -> pathlib.Path:
    mp, ver = FAKE_INSTALLED[name]
    return pathlib.Path(user) / "plugins" / "cache" / mp / name / ver


# 本物の claude 2.1.283 の `plugin marketplace add|update`・`plugin install|uninstall` が隔離した設定に残す形を真似る
FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
cfg = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"])
with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cfg": str(cfg)}) + "\n")
if os.environ.get("FAKE_CLAUDE_NOOP"):
    sys.exit(0)
def load(p, d):
    return json.loads(p.read_text()) if p.exists() else d
def save(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2))
st, km, ip = cfg / "settings.json", cfg / "plugins" / "known_marketplaces.json", cfg / "plugins" / "installed_plugins.json"
a = sys.argv[1:]
if a == ["--version"]:
    print("9.9.9 (Claude Code)")
elif a[:3] == ["plugin", "marketplace", "add"]:
    src = pathlib.Path(a[3])
    name = json.loads((src / ".claude-plugin" / "marketplace.json").read_text())["name"]
    s = load(st, {}); s.setdefault("extraKnownMarketplaces", {})[name] = {"source": {"source": "directory", "path": str(src)}}; save(st, s)
    k = load(km, {}); k[name] = {"source": {"source": "directory", "path": str(src)}, "installLocation": str(src)}; save(km, k)
elif a[:3] == ["plugin", "marketplace", "update"]:
    pass
elif a[:2] == ["plugin", "install"]:
    plugin, mp = a[2].split("@")
    src = pathlib.Path(load(km, {})[mp]["installLocation"])
    entry = next(p for p in json.loads((src / ".claude-plugin" / "marketplace.json").read_text())["plugins"] if p["name"] == plugin)
    psrc = (src / entry["source"]).resolve()
    ver = json.loads((psrc / ".claude-plugin" / "plugin.json").read_text()).get("version") or "unknown"
    dest = cfg / "plugins" / "cache" / mp / plugin / ver
    shutil.rmtree(dest, ignore_errors=True); shutil.copytree(psrc, dest)
    i = load(ip, {"version": 2, "plugins": {}}); i["plugins"][a[2]] = [{"scope": "user", "installPath": str(dest), "version": ver}]; save(ip, i)
    s = load(st, {}); s.setdefault("enabledPlugins", {})[a[2]] = True; save(st, s)
elif a[:2] == ["plugin", "uninstall"]:
    i = load(ip, {"version": 2, "plugins": {}}); i["plugins"].pop(a[2], None); save(ip, i)
    s = load(st, {}); s.setdefault("enabledPlugins", {}).pop(a[2], None); save(st, s)
else:
    print("fake claude: 知らない引数 " + " ".join(a), file=sys.stderr); sys.exit(1)
'''


def write_fake_claude(where: pathlib.Path) -> pathlib.Path:
    """偽の claude を where/claude に置いて返す（呼んだ記録は env の FAKE_CLAUDE_LOG へ）。test_dev も使う"""
    where.mkdir(parents=True, exist_ok=True)
    p = where / "claude"
    p.write_text(FAKE_CLAUDE, encoding="utf-8")
    p.chmod(0o755)
    return p


def files_under(base: pathlib.Path) -> list:
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())


def plugin_version(src: pathlib.Path) -> str:
    """偽の claude がキャッシュの置き場に使う版（plugin.json に version が無ければ unknown）"""
    return json.loads((src / ".claude-plugin" / "plugin.json").read_text()).get("version") or "unknown"


def fake_pack(root: pathlib.Path) -> pathlib.Path:
    """偽のリポジトリの木 root（bin/_lib/toolset.py と、toolset が import する lib/spseam.py・読む lib/borrow/ の写しだけ）。
    試験が写しの固定を書き換えても本物の borrow.json に触れない"""
    shutil.copytree(BORROW, root / "lib" / "borrow")
    shutil.copy2(spseam.__file__, root / "lib" / "spseam.py")
    (root / "bin" / "_lib").mkdir(parents=True)
    shutil.copy2(TOOLSET, root / "bin" / "_lib" / "toolset.py")
    return root


def upstream_redirect(to) -> dict:
    """newer が tag を読む上流（toolset.UPSTREAM_URL）への git の接続を to（手元のリポジトリのパス。無いパスなら届かない上流）へ
    向け替える env の差分。定数が欠ければ AttributeError で落ちる（向け替えが黙って外れて本物の網に出ない）。test_dev も使う"""
    return gitkit.git_url_redirect(toolset.UPSTREAM_URL, to)


PLUGINS = ("pr-review-toolkit",)   # 手元の marketplace に並ぶ名の順（sorted。coldwrite はフックの行で置く）
COLDWRITE_HOOKS = {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "prompt", "prompt": "偽の初見検査"}]}]}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.cfg = self.tmp / "claude-config"
        self.cfg.mkdir()
        self.claude = write_fake_claude(self.tmp / "bin")
        self.log = self.tmp / "claude-calls.jsonl"
        self._env = mock.patch.dict(os.environ, {"FAKE_CLAUDE_LOG": str(self.log)})
        self._env.start()
        self.borrow = user_borrow()
        self.user = make_user_config(self.tmp / "user")

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def calls(self):
        """偽の claude が受けた argv の一覧（どれも隔離した設定の置き場で起きたこと）"""
        if not self.log.exists():
            return []
        rows = [json.loads(ln) for ln in self.log.read_text().splitlines()]
        for r in rows:
            self.assertEqual(r["cfg"], str(self.cfg))
        return [r["argv"] for r in rows]

    def sources(self):
        return toolset.installed_sources(self.user, self.borrow)

    def install(self, chosen=None, versions=None):
        found, vers = self.sources()
        return toolset.install(self.cfg, chosen or found, self.borrow, claude_bin=str(self.claude),
                               versions=vers if versions is None else versions)

    def cli(self, *args, **env):
        """CLI を子で起こす。利用者の設定の置き場は env の CLAUDE_CONFIG_DIR（既定は偽の利用者の設定）"""
        return subprocess.run([sys.executable, str(TOOLSET), *args], capture_output=True, text=True, encoding="utf-8",
                              env=hermetic.child_env(**{"CLAUDE_CONFIG_DIR": str(self.user), **COLDWRITE_ENV, **env}))



def plain_files(base: pathlib.Path) -> list:
    """files_under から Claude Code のキャッシュの印（.in_use/・.orphaned_at）を除いた物（隔離した設定に写る物）"""
    return [f for f in files_under(base) if not toolset.MARKERS & set(f.split("/"))]


class BorrowListCase(unittest.TestCase):
    def test_borrow_json_names_installed_plugins(self):
        """借りる物は利用者が入れたプラグインの <名>@<marketplace> で名指し、入れるコマンドの marketplace の元（GitHub）を持つ。
        works が名前で頼る物（スキル・agent・hook）だけを並べる。写しを示す印（pinned）は無い"""
        b = user_borrow()
        self.assertEqual(sorted(b), ["coldwrite", "pr-review-toolkit", "superpowers"])
        self.assertEqual(sorted(b["superpowers"]["skills"]), sorted(BORROW_SKILLS))
        want = {"superpowers": ("superpowers-marketplace", "obra/superpowers-marketplace"),
                "coldwrite": (COLDWRITE_MP, COLDWRITE_REPO),
                "pr-review-toolkit": ("claude-plugins-official", "anthropics/claude-plugins-official")}
        for name, (mp, repo) in want.items():
            with self.subTest(name):
                self.assertEqual((b[name]["marketplace"], b[name]["marketplace_repo"]), (mp, repo))
                self.assertNotIn("pinned", b[name])
        self.assertEqual(b["superpowers"]["kind"], "skills")
        self.assertEqual(b["coldwrite"], {"kind": "plugin", "marketplace": COLDWRITE_MP, "marketplace_repo": COLDWRITE_REPO,
                                          "hooks": {"PreToolUse": ["Write"]}})
        self.assertEqual(b["pr-review-toolkit"]["agents"], LENSES)

    def test_coldwrite_marketplace_is_not_in_the_repo(self):
        """coldwrite の marketplace は持ち主の物（E14）なので borrow.json に書かず、利用者の設定の名だけを持つ。名と repo の
        どちらかが無ければ止めずに見送り、見送った 1 行が両方の名を名指す。ほかの借りる物は変えない"""
        raw = toolset.load_borrow(BORROW)
        self.assertNotIn("marketplace", raw["coldwrite"])
        self.assertNotIn("marketplace_repo", raw["coldwrite"])
        for env in ({}, {"WORKS_FACTORY_COLDWRITE_MARKETPLACE": COLDWRITE_MP},
                    {"WORKS_FACTORY_COLDWRITE_MARKETPLACE_REPO": COLDWRITE_REPO}):
            with self.subTest(env=env):
                b, skipped = toolset.user_borrow(raw, env)
                self.assertEqual(sorted(b), ["pr-review-toolkit", "superpowers"])
                self.assertEqual(b["pr-review-toolkit"], raw["pr-review-toolkit"])
                self.assertEqual(len(skipped), 1, skipped)
                self.assertIn("coldwrite", skipped[0])
                for k in COLDWRITE_ENV:
                    self.assertIn(k, skipped[0])

    def test_no_vendored_copies(self):
        """works は coldwrite・pr-review-toolkit の写しを持たない（利用者が入れた版に従う）。superpowers の写しは VendorCase と
        test_sp_skills の VendoredCopyCase が縛る"""
        for name in ("pr-review-toolkit", "coldwrite"):
            self.assertFalse((BORROW / name).exists(), name)
        self.assertFalse((BORROW / "NOTICE").exists())


SHA = "a" * 40   # 偽の superpowers の commit（vendor は commit の分からない写しを拒む）


class VendorCase(Base):
    """vendor: 利用者のキャッシュの superpowers の 1 つの版から、包むファイルだけを lib/borrow/superpowers/<版>/ へ写し、
    写しの台帳（COPIED_FROM）と borrow.json の pin を書き直す。偽の pack（borrow.json だけ）と偽の superpowers 9.9.0 で回す"""

    def setUp(self):
        super().setUp()
        self.borrow_dir = self.tmp / "borrow"
        self.borrow_dir.mkdir()
        shutil.copy2(BORROW / "borrow.json", self.borrow_dir / "borrow.json")

    def test_vendor_writes_copy_ledger_and_pin(self):
        src = installed_dir(self.user, "superpowers")
        pin = toolset.vendor(self.borrow_dir, src, "9.9.0", SHA, "2026-10-02")
        base = self.borrow_dir / "superpowers"
        item = json.loads((self.borrow_dir / "borrow.json").read_text())["superpowers"]
        self.assertEqual(item["pin"], pin)
        self.assertEqual(spseam.pin_problems(base / "9.9.0", item), [])
        self.assertIn("LICENSE", pin["files"])
        self.assertFalse((base / "9.9.0" / "skills" / "brainstorming").exists())        # 借りないスキルは写さない
        self.assertFalse((base / "9.9.0" / "skills" / "subagent-driven-development" / "SKILL.md").exists())   # 部品だけ
        led = copyledger.read(base / "COPIED_FROM")
        self.assertEqual(sorted(r for r, _ in led.rows), sorted(f"9.9.0/{f}" for f in pin["files"]))
        self.assertEqual(led.deviations, {})
        self.assertIn("Copyright (c) 2025 Test", led.head)

    def test_vendor_replaces_the_old_version(self):
        toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), "9.9.0", SHA, "2026-10-02")
        newer = installed_dir(self.user, "superpowers").parent / "9.10.0"
        shutil.copytree(installed_dir(self.user, "superpowers"), newer)
        toolset.vendor(self.borrow_dir, newer, "9.10.0", "f" * 40, "2026-10-03")
        self.assertEqual(sorted(p.name for p in (self.borrow_dir / "superpowers").iterdir()), ["9.10.0", "COPIED_FROM"])

    def test_vendor_skips_markers(self):
        """Claude Code の印（.in_use/）と .DS_Store が借りるスキルの中に在っても、写さず固定にも数えない"""
        src = installed_dir(self.user, "superpowers")
        _put(src / "skills" / "test-driven-development" / ".in_use" / "1", "{}")
        _put(src / "skills" / "test-driven-development" / ".DS_Store", "x")
        pin = toolset.vendor(self.borrow_dir, src, "9.9.0", SHA, "2026-10-02")
        self.assertFalse(any(".in_use" in f or f.endswith(".DS_Store") for f in pin["files"]))
        copied = self.borrow_dir / "superpowers/9.9.0/skills/test-driven-development"
        self.assertEqual(sorted(p.name for p in copied.iterdir()), ["SKILL.md"])

    def test_vendor_refuses_without_mit_licence(self):
        (installed_dir(self.user, "superpowers") / "LICENSE").write_text("Proprietary\n", encoding="utf-8")
        before = (self.borrow_dir / "borrow.json").read_bytes()
        with self.assertRaises(toolset.ToolsetError):
            toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), "9.9.0", SHA, "2026-10-02")
        self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
        self.assertFalse((self.borrow_dir / "superpowers").exists())

    def test_cli_vendor_missing_version_is_2(self):
        r = self.cli("vendor", "0.0.1")
        self.assertEqual(r.returncode, 2)
        self.assertIn(str(installed_dir(self.user, "superpowers").parent / "0.0.1"), r.stderr)

    def test_vendor_refuses_unknown_commit_and_writes_nothing(self):
        """固定は写し元の commit を名指す。分からない（None・空・40 桁の 16 進でない）なら何も書かずに止まる"""
        before = (self.borrow_dir / "borrow.json").read_bytes()
        for commit in (None, "", "unknown", "abc"):
            with self.subTest(commit):
                with self.assertRaises(toolset.ToolsetError) as cm:
                    toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), "9.9.0", commit, "2026-10-02")
                self.assertIn("commit", str(cm.exception))
                self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
                self.assertFalse((self.borrow_dir / "superpowers").exists())

    def test_vendor_failure_leaves_no_empty_folder(self):
        """写している途中で落ちたら、初めての写しなら superpowers/ を残さず、borrow.json も変えない"""
        before = (self.borrow_dir / "borrow.json").read_bytes()
        with mock.patch.object(toolset.shutil, "copy2", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), "9.9.0", SHA, "2026-10-02")
        self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
        self.assertFalse((self.borrow_dir / "superpowers").exists())

    def test_vendor_failure_keeps_the_old_version(self):
        """入れ替えの途中（borrow.json を書く所）で落ちても、前の版の写し・台帳・borrow.json はそのまま残る"""
        src = installed_dir(self.user, "superpowers")
        toolset.vendor(self.borrow_dir, src, "9.9.0", SHA, "2026-10-02")
        base = self.borrow_dir / "superpowers"
        snap = {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}
        before = (self.borrow_dir / "borrow.json").read_bytes()
        newer = src.parent / "9.10.0"
        shutil.copytree(src, newer)
        real = os.replace

        def fail_on_borrow(a, b):
            if pathlib.Path(b).name == "borrow.json":
                raise OSError("disk full")
            return real(a, b)
        with mock.patch.object(toolset.os, "replace", side_effect=fail_on_borrow):
            with self.assertRaises(OSError):
                toolset.vendor(self.borrow_dir, newer, "9.10.0", "f" * 40, "2026-10-03")
        self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
        self.assertEqual({p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}, snap)
        self.assertEqual(sorted(p.name for p in base.iterdir()), ["9.9.0", "COPIED_FROM"])

    @unittest.skipIf(os.name == "nt", "SKIP posix-mode: 実行の権限は POSIX だけ")
    def test_vendor_keeps_exec_bit(self):
        toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), "9.9.0", SHA, "2026-10-02")
        sh = self.borrow_dir / "superpowers/9.9.0/skills/systematic-debugging/find-polluter.sh"
        self.assertTrue(os.access(sh, os.X_OK))
        self.assertFalse(os.access(sh.parent / "SKILL.md", os.X_OK))

    def test_commit_of_reads_the_row_of_the_install_path(self):
        """commit は installed_plugins.json の行のうち installPath が版のフォルダの行の gitCommitSha。無ければ None"""
        src = installed_dir(self.user, "superpowers")
        other = src.parent / "9.8.0"
        other.mkdir()
        rows = [{"scope": "user", "installPath": str(other), "version": "9.8.0", "gitCommitSha": "b" * 40},
                {"scope": "project", "projectPath": "/x", "installPath": str(src), "version": "9.9.0", "gitCommitSha": "c" * 40}]
        _put(self.user / "plugins" / "installed_plugins.json",
             json.dumps({"version": 2, "plugins": {"superpowers@superpowers-marketplace": rows}}))
        self.assertEqual(toolset._commit_of(self.user, src), "c" * 40)
        self.assertEqual(toolset._commit_of(self.user, other), "b" * 40)
        self.assertIsNone(toolset._commit_of(self.user, src.parent / "9.7.0"))

    def test_vendor_refuses_version_names_that_point_outside(self):
        for bad in ("../9.9.0", "9.9.0/x", ".hidden", ""):
            with self.subTest(bad):
                with self.assertRaises(toolset.ToolsetError) as cm:
                    toolset.vendor(self.borrow_dir, installed_dir(self.user, "superpowers"), bad, SHA, "2026-10-02")
                self.assertIn("版の名", str(cm.exception))
                self.assertFalse((self.borrow_dir / "superpowers").exists())

    def test_vendor_refuses_missing_part_or_symlink_and_writes_nothing(self):
        """部品が無い・包むファイルが symlink、のどちらでも名指して止まり、borrow.json も写しも書かない"""
        src = installed_dir(self.user, "superpowers")
        before = (self.borrow_dir / "borrow.json").read_bytes()
        part = src / "skills" / "subagent-driven-development" / "task-reviewer-prompt.md"
        cases = {"task-reviewer-prompt.md": lambda: part.unlink(),
                 "symlink": lambda: (src / "skills" / "test-driven-development" / "x.md").symlink_to(src / "LICENSE")}
        for said, breakit in cases.items():
            with self.subTest(said):
                breakit()
                with self.assertRaises(toolset.ToolsetError) as cm:
                    toolset.vendor(self.borrow_dir, src, "9.9.0", SHA, "2026-10-02")
                self.assertIn(said, str(cm.exception))
                self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
                self.assertFalse((self.borrow_dir / "superpowers").exists())
                part.write_text("偽\n", encoding="utf-8")

    def test_vendor_names_absent_listed_file_without_suggesting_vendor(self):
        """写し元に借りる一覧の部品が無い時の拒みは『写し元の版のフォルダに無い』と言い、vendor を打ち直せとも pin.files とも言わない"""
        src = installed_dir(self.user, "superpowers")
        before = (self.borrow_dir / "borrow.json").read_bytes()
        (src / "skills" / "subagent-driven-development" / "task-reviewer-prompt.md").unlink()
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.vendor(self.borrow_dir, src, "9.9.0", SHA, "2026-10-02")
        msg = str(cm.exception)
        self.assertIn("task-reviewer-prompt.md: 写し元の版のフォルダに無い", msg)
        self.assertNotIn("bin/_lib/toolset.py vendor で写し直す", msg)
        self.assertNotIn("pin.files", msg)
        self.assertEqual((self.borrow_dir / "borrow.json").read_bytes(), before)
        self.assertFalse((self.borrow_dir / "superpowers").exists())


class ResolveCase(unittest.TestCase):
    """installed_sources: 利用者が入れたプラグインからだけ取る。無ければ 1 物 1 行の理由と入れるコマンドで止まる"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.borrow = user_borrow()

    def tearDown(self):
        self._tmp.cleanup()

    def test_user_scope_rows_are_used(self):
        user = make_user_config(self.tmp / "user")
        chosen, versions = toolset.installed_sources(user, self.borrow)
        self.assertEqual(chosen, {n: installed_dir(user, n) for n in FAKE_INSTALLED if n != "superpowers"}
                         | {"superpowers": VENDORED})
        self.assertEqual(versions, {n: v for n, (_, v) in FAKE_INSTALLED.items() if n != "superpowers"}
                         | {"superpowers": self.borrow["superpowers"]["pin"]["version"]})

    def test_project_rows_count_only_for_their_project(self):
        target = self.tmp / "target"
        target.mkdir()
        user = make_user_config(self.tmp / "user", scope="project", project=target)
        chosen, _ = toolset.installed_sources(user, self.borrow, cwd=target)
        self.assertEqual(chosen["coldwrite"], installed_dir(user, "coldwrite"))
        with self.assertRaises(toolset.ToolsetError):
            toolset.installed_sources(user, self.borrow, cwd=self.tmp)

    def test_missing_tools_are_listed_one_line_each_with_install_commands(self):
        """何も入っていない利用者: 利用者の入れた物から借りる 2 つが 1 行ずつ、入れる marketplace と install のコマンドつきで並ぶ。
        superpowers は works の写しから入れるので並ばない"""
        user = self.tmp / "empty"
        user.mkdir()
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(user, self.borrow)
        lines = str(cm.exception).splitlines()[1:]
        self.assertEqual(len(lines), 2, lines)
        self.assertNotIn("superpowers", str(cm.exception))
        for key, repo in ((f"coldwrite@{COLDWRITE_MP}", COLDWRITE_REPO),
                          ("pr-review-toolkit@claude-plugins-official", "anthropics/claude-plugins-official")):
            line = next(ln for ln in lines if key in ln)
            self.assertIn(f"claude plugin marketplace add {repo}", line)
            self.assertIn(f"claude plugin install {key}", line)

    def test_only_the_missing_one_is_named(self):
        user = make_user_config(self.tmp / "user", only={"superpowers", "coldwrite"})
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(user, self.borrow)
        lines = str(cm.exception).splitlines()[1:]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("pr-review-toolkit が入っていない", lines[0])

    def test_install_path_that_is_gone_counts_as_not_installed(self):
        user = make_user_config(self.tmp / "user")
        shutil.rmtree(installed_dir(user, "coldwrite"))
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(user, self.borrow)
        self.assertIn("coldwrite が入っていない", str(cm.exception))

    def test_missing_names_stop_with_the_name(self):
        """works が名前で頼る物が無い版は止める（名前が API）。無い名前を出す"""
        cases = {   # superpowers のスキルの欠けは写しの照合が名指す（test_tampered_vendored_copy_stops_before_writing）
            "agent comment-analyzer": lambda u: (installed_dir(u, "pr-review-toolkit") / "agents" / "comment-analyzer.md").unlink(),
            "hook PreToolUse:Write": lambda u: _put(installed_dir(u, "coldwrite") / "hooks" / "hooks.json",
                                                    json.dumps({"hooks": {"PreToolUse": [{"matcher": "Edit"}]}})),
        }
        for want, breakit in cases.items():
            with self.subTest(want):
                user = make_user_config(self.tmp / want.split()[1])
                breakit(user)
                with self.assertRaises(toolset.ToolsetError) as cm:
                    toolset.installed_sources(user, self.borrow)
                lines = str(cm.exception).splitlines()[1:]
                self.assertEqual(len(lines), 1, lines)
                self.assertIn(want, lines[0])

    def test_superpowers_comes_from_the_vendored_copy(self):
        """利用者のキャッシュの superpowers が別の中身・別の版でも、取り元は works の写しで、版は pin の版"""
        user = make_user_config(self.tmp / "user")
        _put(installed_dir(user, "superpowers") / "skills" / "test-driven-development" / "SKILL.md", "新しい版\n")
        chosen, versions = toolset.installed_sources(user, self.borrow)
        self.assertEqual((chosen["superpowers"], versions["superpowers"]), (VENDORED, self.borrow["superpowers"]["pin"]["version"]))

    def test_plugins_content_is_not_checked(self):
        """coldwrite・pr-review-toolkit は今どおり名前だけ: 名前が在れば、中身が変わった新しい版でも通る（役は読むだけ）"""
        user = make_user_config(self.tmp / "user")
        _put(installed_dir(user, "pr-review-toolkit") / "agents" / "code-reviewer.md", "新しい版の文\n")
        chosen, _ = toolset.installed_sources(user, self.borrow)
        self.assertEqual(chosen["pr-review-toolkit"], installed_dir(user, "pr-review-toolkit"))

    def test_user_config_dir_follows_env(self):
        self.assertEqual(toolset.user_config_dir({"CLAUDE_CONFIG_DIR": "/x/cfg"}), pathlib.Path("/x/cfg"))
        self.assertEqual(toolset.user_config_dir({}), pathlib.Path(os.path.expanduser("~/.claude")))


class ScopeCase(unittest.TestCase):
    """同じプラグインが複数の scope に入っていれば、Claude Code と同じく local > project > user の行を取る
    （https://code.claude.com/docs/en/discover-plugins の Which scope wins）。enabledPlugins の無効は拒まずに借り、
    元が有効だったか無効だったかを記録に残す（人の答え: 利用者は借りる物のフックを普段効かせないために無効にしておく）"""

    FROM_USER = [n for n in FAKE_INSTALLED if n != "superpowers"]   # 利用者の入れた物から借りる物（superpowers は写しから）

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.borrow = user_borrow()
        self.target = self.tmp / "target"
        self.target.mkdir()
        self.user = make_user_config(self.tmp / "user")

    def tearDown(self):
        self._tmp.cleanup()

    def add_rows(self, scope: str) -> pathlib.Path:
        """scope の行（projectPath は対象）を、別の置き場に入れた物として利用者の installed_plugins.json に足す"""
        other = make_user_config(self.tmp / scope, scope=scope, project=self.target)
        ip_path = self.user / "plugins" / "installed_plugins.json"
        ip = json.loads(ip_path.read_text())
        for key, rows in json.loads((other / "plugins" / "installed_plugins.json").read_text())["plugins"].items():
            ip["plugins"][key] = ip["plugins"].get(key, []) + rows
        ip_path.write_text(json.dumps(ip, indent=2))
        return other

    def test_project_row_wins_over_user_row(self):
        project = self.add_rows("project")
        chosen, _ = toolset.installed_sources(self.user, self.borrow, cwd=self.target)
        for n in self.FROM_USER:
            self.assertEqual(chosen[n], installed_dir(project, n), n)

    def test_local_row_wins_over_project_and_user_rows(self):
        self.add_rows("project")
        local = self.add_rows("local")
        chosen, _ = toolset.installed_sources(self.user, self.borrow, cwd=self.target)
        for n in self.FROM_USER:
            self.assertEqual(chosen[n], installed_dir(local, n), n)

    def test_disabled_plugin_is_borrowed_and_the_source_state_is_recorded(self):
        """利用者の settings.json で無効でも借りる。対象の .claude/settings.local.json・settings.json が利用者の値に勝つ。
        記録の source_enabled は、元で勝った enabledPlugins の値（どこにも鍵が無ければ null）。superpowers は写しから入れるので、
        利用者の側の有効・無効を載せない"""
        _put(self.user / "settings.json", json.dumps({"enabledPlugins": {
            f"coldwrite@{COLDWRITE_MP}": False, "superpowers@superpowers-marketplace": False}}))
        _put(self.target / ".claude" / "settings.json", json.dumps({"enabledPlugins": {
            "superpowers@superpowers-marketplace": True}}))
        cfg = self.tmp / "claude-config"
        cfg.mkdir()
        r = subprocess.run([sys.executable, str(TOOLSET), "install", "--no-plugins", "--user-config", str(self.user), str(cfg)],
                           capture_output=True, text=True, encoding="utf-8", cwd=self.target,
                           env=hermetic.child_env(**COLDWRITE_ENV))
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = json.loads((cfg / toolset.RECORD).read_text())
        self.assertEqual(rec["coldwrite"]["source"], str(installed_dir(self.user, "coldwrite")))
        self.assertEqual({n: rec[n].get("source_enabled", "無い") for n in FAKE_INSTALLED},
                         {"coldwrite": False, "superpowers": "無い", "pr-review-toolkit": None})


class InstalledShapeCase(unittest.TestCase):
    """installed_plugins.json は Claude Code の内部の状態で、形の約束（文書）が無い。知らない形は『入っていない』に潰さず、
    形を知らないと名指しして止まる（入れ直しても直らない install のコマンドを勧めない）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.borrow = user_borrow()

    def tearDown(self):
        self._tmp.cleanup()

    def test_unknown_shape_stops_with_named_reason_not_as_missing(self):
        def reshape(ip, how):
            if how == "version 1":
                ip["version"] = 1
            elif how == "version 無し":
                del ip["version"]
            elif how == "行が表（古い 1 行の形）":
                ip["plugins"] = {k: rows[0] for k, rows in ip["plugins"].items()}
            elif how == "plugins が一覧":
                ip["plugins"] = [dict(r, key=k) for k, rows in ip["plugins"].items() for r in rows]
            return ip
        for how in ("version 1", "version 無し", "行が表（古い 1 行の形）", "plugins が一覧"):
            with self.subTest(how):
                user = make_user_config(self.tmp / f"u{len(how)}{how[:3]}")
                p = user / "plugins" / "installed_plugins.json"
                p.write_text(json.dumps(reshape(json.loads(p.read_text()), how)))
                try:
                    toolset.installed_sources(user, self.borrow)
                except toolset.ToolsetError as e:
                    msg = str(e)
                except Exception as e:   # 形を確かめずに読んで落ちるのも、名指しの理由で止まらない欠陥
                    self.fail(f"ToolsetError でなく {type(e).__name__}: {e}")
                else:
                    self.fail("知らない形なのに止まらなかった")
                self.assertIn("知らない", msg)
                self.assertIn(str(p), msg)
                self.assertNotIn("入っていない", msg)
                self.assertNotIn("claude plugin install", msg)


class InstallCase(Base):
    def test_install_builds_exactly_the_chosen_config(self):
        """一時の置き場に組んだ設定の中身が、ちょうど 5 つのスキル・2 つの部品・手元の marketplace の pr-review-toolkit・その入れた
        状態・フックの行だけ。superpowers の写す元は works の写し、ほかは利用者が入れた置き場で、キャッシュの印は写さない"""
        rec = self.install()
        srcs = {"pr-review-toolkit": installed_dir(self.user, "pr-review-toolkit")}
        sp = VENDORED
        want = sorted(
            [f"skills/{n}/{f}" for n in BORROW_SKILLS for f in files_under(sp / "skills" / n)]
            + [f"works-parts/superpowers/{rel}" for rel in self.borrow["superpowers"]["parts"]]
            + [f"works-marketplace/{n}/{f}" for n, s in srcs.items() for f in plain_files(s)]
            + ["works-marketplace/.claude-plugin/marketplace.json", "settings.json", ".works-toolset.json",
               "plugins/known_marketplaces.json", "plugins/installed_plugins.json"]
            + [f"plugins/cache/{MP}/{n}/{plugin_version(s)}/{f}" for n, s in srcs.items() for f in plain_files(s)])
        self.assertEqual(files_under(self.cfg), want)
        # スキルとプラグインの写しはバイトのまま・権限つき・symlink でない
        for n in BORROW_SKILLS:
            for rel in files_under(sp / "skills" / n):
                a, b = self.cfg / "skills" / n / rel, sp / "skills" / n / rel
                self.assertEqual(a.read_bytes(), b.read_bytes(), rel)
                self.assertFalse(a.is_symlink())
                self.assertEqual(os.access(a, os.X_OK), os.access(b, os.X_OK), rel)
        for n, s in srcs.items():
            for rel in plain_files(s):
                self.assertEqual((self.cfg / "works-marketplace" / n / rel).read_bytes(), (s / rel).read_bytes(), rel)
        self.assertEqual(json.loads((self.cfg / "works-marketplace" / ".claude-plugin" / "marketplace.json").read_text()),
                         {"name": MP, "owner": {"name": "works"},
                          "plugins": [{"name": n, "source": f"./{n}", "strict": False} for n in PLUGINS]})
        self.assertEqual(json.loads((self.cfg / "settings.json").read_text()),
                         {"extraKnownMarketplaces": {MP: {"source": {"source": "directory",
                                                                     "path": str(self.cfg / "works-marketplace")}}},
                          "enabledPlugins": {f"{n}@{MP}": True for n in PLUGINS},
                          "hooks": {"PostToolUse": toolset.recorder_rows(self.cfg), **COLDWRITE_HOOKS},
                          "permissions": toolset.permissions(deny_web=False)})
        self.assertEqual(self.calls(), [["plugin", "marketplace", "add", str(self.cfg / "works-marketplace")]]
                         + [["plugin", "install", f"{n}@{MP}"] for n in PLUGINS])
        # 記録: 版は installed_plugins.json の行の物、source は利用者が入れた置き場（versions.json の borrowed に載る）。
        # superpowers は pin の版と写しのフォルダ
        self.assertEqual(sorted(rec), ["coldwrite", "pr-review-toolkit", "superpowers"])
        self.assertEqual({k: (v["version"], v["source"], v["loaded"]) for k, v in rec.items()},
                         {n: (ver, str(installed_dir(self.user, n)), True) for n, (_, ver) in FAKE_INSTALLED.items()
                          if n != "superpowers"}
                         | {"superpowers": (self.borrow["superpowers"]["pin"]["version"], str(VENDORED), True)})
        self.assertEqual(rec["coldwrite"]["hooks"], COLDWRITE_HOOKS)
        self.assertEqual(json.loads((self.cfg / ".works-toolset.json").read_text()), rec)
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])

    def test_second_install_calls_nothing_and_changes_nothing(self):
        """キャッシュの印が変わっても（Claude Code が pid を書き換える）、入れ直さない"""
        self.install()
        before = {f: (self.cfg / f).read_bytes() for f in files_under(self.cfg)}
        self.log.unlink()
        _put(installed_dir(self.user, "pr-review-toolkit") / ".in_use" / "9999", "{}")
        self.install()
        self.assertEqual(self.calls(), [])
        self.assertEqual({f: (self.cfg / f).read_bytes() for f in files_under(self.cfg)}, before)

    def test_changed_plugin_is_recopied_and_reinstalled(self):
        """利用者のプラグインが新しい版になれば（Claude Code が今に保つ）、写し直して入れ直す"""
        src = installed_dir(self.user, "pr-review-toolkit")
        self.install()
        self.log.unlink()
        (src / "agents" / "code-reviewer.md").write_text("新しい版\n", encoding="utf-8")
        self.install()
        key = f"pr-review-toolkit@{MP}"
        self.assertEqual(self.calls(), [["plugin", "marketplace", "update", MP], ["plugin", "uninstall", key],
                                        ["plugin", "install", key]])
        self.assertEqual((self.cfg / "works-marketplace" / "pr-review-toolkit" / "agents" / "code-reviewer.md").read_text(),
                         "新しい版\n")

    def test_stale_skill_copy_and_exec_bit_are_fixed(self):
        sp = VENDORED
        self.install()
        tdd = self.cfg / "skills" / "test-driven-development"
        (tdd / "SKILL.md").write_text("古い\n", encoding="utf-8")
        (tdd / "extra.md").write_text("余分\n", encoding="utf-8")
        polluter = self.cfg / "skills" / "systematic-debugging" / "find-polluter.sh"
        polluter.chmod(0o644)
        part = self.borrow["superpowers"]["parts"][0]
        (self.cfg / "works-parts" / "superpowers" / part).write_text("古い\n", encoding="utf-8")
        self.install()
        self.assertEqual((self.cfg / "works-parts" / "superpowers" / part).read_bytes(), (sp / part).read_bytes())
        self.assertEqual(files_under(tdd), files_under(sp / "skills" / "test-driven-development"))
        self.assertEqual((tdd / "SKILL.md").read_bytes(), (sp / "skills" / "test-driven-development" / "SKILL.md").read_bytes())
        self.assertTrue(os.access(polluter, os.X_OK))
        self.assertEqual(sorted(p.name for p in (self.cfg / "skills").iterdir()), sorted(BORROW_SKILLS),
                         "作業の一時の置き場か、借りない物が残っている")

    def test_no_superpowers_installed_still_installs(self):
        """利用者が superpowers を入れていなくても組め、スキルは写しのバイトと同じ"""
        self.user = make_user_config(self.tmp / "user2", only={"coldwrite", "pr-review-toolkit"})
        rec = self.install()
        for s in self.borrow["superpowers"]["skills"]:
            for f in files_under(VENDORED / "skills" / s):
                self.assertEqual((self.cfg / "skills" / s / f).read_bytes(), (VENDORED / "skills" / s / f).read_bytes())
        self.assertEqual(rec["superpowers"]["source"], str(VENDORED))

    def test_tampered_vendored_copy_stops_before_writing(self):
        """写しのファイルが pin の sha256 と違えば、違うファイルを名指して何も写す前に止まる（写しを一時の置き場に写して向ける）"""
        copy = self.tmp / "vendored"
        shutil.copytree(VENDORED, copy)
        (copy / "skills" / "test-driven-development" / "SKILL.md").write_text("書き換え\n", encoding="utf-8")
        with mock.patch.object(toolset.spseam, "vendored_dir", return_value=copy), self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(self.user, self.borrow)
        self.assertIn("skills/test-driven-development/SKILL.md: 中身が固定と違う", str(cm.exception))
        self.assertEqual(files_under(self.cfg), [])

    def test_vendored_copy_breaks_are_named_in_one_group(self):
        """写しの壊れ方ごとに、superpowers のまとまりの中で該当の行を名指し、直し方を添えて、何も写す前に止まる"""
        def no_skill_dir(copy, item):
            shutil.rmtree(copy / "skills" / "verification-before-completion")
            return item

        def listed_but_not_pinned(copy, item):
            return dict(item, skills=[*item["skills"], "brainstorming"])

        def no_pin(copy, item):
            return {k: v for k, v in item.items() if k != "pin"}

        def no_copy_dir(copy, item):
            shutil.rmtree(copy)
            return item

        cases = {
            "skills/verification-before-completion/SKILL.md: 固定に在るのに手元に無い": no_skill_dir,
            "skills/brainstorming/SKILL.md: 借りる一覧（borrow.json の skills・parts）が名指すのに、固定（pin.files）にその sha256 が無い（bin/_lib/toolset.py vendor で写し直す）": listed_but_not_pinned,
            "borrow.json の superpowers に pin が無い": no_pin,
            "写しのフォルダが無い": no_copy_dir,
        }
        for want, breakit in cases.items():
            with self.subTest(want):
                copy = self.tmp / f"vendored-{breakit.__name__}"
                shutil.copytree(VENDORED, copy)
                borrow = dict(self.borrow, superpowers=breakit(copy, dict(self.borrow["superpowers"])))
                with mock.patch.object(toolset.spseam, "vendored_dir", return_value=copy), \
                        self.assertRaises(toolset.ToolsetError) as cm:
                    toolset.installed_sources(self.user, borrow)
                msg = str(cm.exception)
                group = msg[msg.index("- superpowers の写し"):]
                self.assertIn("が borrow.json の pin と合わない:\n", group)
                self.assertTrue(any(ln.startswith("  - ") and want in ln for ln in group.splitlines()), msg)
                self.assertIn("git checkout -- :/lib/borrow", group)
                self.assertEqual(files_under(self.cfg), [])

    def test_vendored_copy_break_and_missing_plugins_join_in_one_error(self):
        """写しの食い違いと、入っていないプラグインの行は、同じ 1 つの ToolsetError に並ぶ"""
        copy = self.tmp / "vendored"
        shutil.copytree(VENDORED, copy)
        (copy / "skills" / "test-driven-development" / "SKILL.md").write_text("書き換え\n", encoding="utf-8")
        empty = self.tmp / "empty"
        empty.mkdir()
        with mock.patch.object(toolset.spseam, "vendored_dir", return_value=copy), self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(empty, self.borrow)
        heads = [ln for ln in str(cm.exception).splitlines() if ln.startswith("- ")]
        self.assertEqual(len(heads), 3, heads)
        self.assertTrue(heads[0].startswith("- superpowers の写し"), heads)
        self.assertIn("coldwrite が入っていない", heads[1])
        self.assertIn("pr-review-toolkit が入っていない", heads[2])
        self.assertIn("  - skills/test-driven-development/SKILL.md: 中身が固定と違う", str(cm.exception))

    def test_install_names_missing_part_before_writing(self):
        """install に渡した写しに部品が無ければ、名指して何も写さずに止まる"""
        found, vers = self.sources()
        copy = self.tmp / "vendored"
        shutil.copytree(VENDORED, copy)
        part = self.borrow["superpowers"]["parts"][0]
        (copy / part).unlink()
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.install(self.cfg, dict(found, superpowers=copy), self.borrow, claude_bin=str(self.claude), versions=vers)
        self.assertIn(f"{part}: 固定に在るのに手元に無い", str(cm.exception))
        self.assertEqual(files_under(self.cfg), [])

    def test_dropped_part_is_pruned_on_reinstall(self):
        """版上げで部品が一覧から外れても、入れ直しは柵に止まらずに通り、古い部品と空になったフォルダは消える"""
        self.install()
        dropped = self.borrow["superpowers"]["parts"][1]
        _put(self.cfg / "works-parts" / "superpowers" / "old" / "gone.md", "前の版の部品\n")
        # 版上げでは vendor が一覧と pin を一緒に取り直すので、外れた部品は pin.files からも外れる
        sp = self.borrow["superpowers"]
        pin = dict(sp["pin"], files={f: h for f, h in sp["pin"]["files"].items() if f != dropped})
        smaller = dict(self.borrow, superpowers=dict(sp, parts=sp["parts"][:1], pin=pin))
        found, vers = self.sources()
        toolset.install(self.cfg, found, smaller, claude_bin=str(self.claude), versions=vers)
        self.assertFalse((self.cfg / "works-parts" / "superpowers" / dropped).exists())
        self.assertFalse((self.cfg / "works-parts" / "superpowers" / "old").exists())
        self.assertTrue((self.cfg / "works-parts" / "superpowers" / smaller["superpowers"]["parts"][0]).is_file())
        self.assertEqual(toolset.guard(self.cfg, smaller), [])

    def test_prune_does_not_follow_symlinks_outside_the_config(self):
        """works-parts・works-parts/superpowers が設定の外を指す symlink なら、外のファイルを消さずに柵が止める。
        works-parts/superpowers/ の下の symlink のファイルも消さず、柵が名指す"""
        def parts_dir_link(outside):
            _put(outside / "precious.md", "外の大事なファイル\n")
            (self.cfg / "works-parts").mkdir()
            (self.cfg / "works-parts" / "superpowers").symlink_to(outside)
            return outside / "precious.md"

        def root_link(outside):
            _put(outside / "superpowers" / "precious.md", "外の大事なファイル\n")
            (self.cfg / "works-parts").symlink_to(outside)
            return outside / "superpowers" / "precious.md"

        for make in (parts_dir_link, root_link):
            with self.subTest(make.__name__):
                shutil.rmtree(self.cfg)
                self.cfg.mkdir()
                precious = make(self.tmp / f"outside-{make.__name__}")
                with self.assertRaises(toolset.ToolsetError):
                    self.install()
                self.assertTrue(precious.is_file(), "設定の外のファイルを消した")
        shutil.rmtree(self.cfg)
        self.cfg.mkdir()
        _put(self.tmp / "outside-file.md", "外の大事なファイル\n")
        link = self.cfg / "works-parts" / "superpowers" / "link.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(self.tmp / "outside-file.md")
        with self.assertRaises(toolset.ToolsetError):
            self.install()
        self.assertTrue(link.is_symlink() and (self.tmp / "outside-file.md").is_file())
        self.assertEqual(toolset.guard(self.cfg, self.borrow), ["works-parts/superpowers/link.md"])

    def test_parts_go_to_works_parts_and_record_has_commit(self):
        """部品は works-parts/superpowers/<相対パス> へバイトのまま写り、スキルとしては入らない。記録は pin の commit を持ち、
        source_enabled を持たない。works-parts/ の下の部品の外のファイルは柵が名指す"""
        rec = self.install()
        for rel in self.borrow["superpowers"]["parts"]:
            self.assertEqual((self.cfg / "works-parts" / "superpowers" / rel).read_bytes(), (VENDORED / rel).read_bytes())
        self.assertFalse((self.cfg / "skills" / "subagent-driven-development").exists())   # スキルとしては入れない
        self.assertEqual(rec["superpowers"]["commit"], self.borrow["superpowers"]["pin"]["commit"])
        self.assertNotIn("source_enabled", rec["superpowers"])
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        _put(self.cfg / "works-parts" / "superpowers" / "skills" / "subagent-driven-development" / "SKILL.md", "x\n")
        self.assertEqual(toolset.guard(self.cfg, self.borrow), ["works-parts/superpowers/skills/subagent-driven-development/SKILL.md"])

    def test_plugin_not_enabled_after_cli_fails_closed(self):
        """CLI が 0 で終わっても pr-review-toolkit が有効になっていなければ、入ったことにしない（レンズの無い役を起こさない）"""
        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_NOOP": "1"}):
            with self.assertRaises(toolset.ToolsetError) as cm:
                self.install()
        self.assertIn("pr-review-toolkit", str(cm.exception))

    def test_cli_error_is_reported(self):
        bad = self.tmp / "bin" / "claude-bad"
        bad.write_text("#!/bin/sh\necho 'boom' >&2\nexit 7\n", encoding="utf-8")
        bad.chmod(0o755)
        chosen, versions = self.sources()
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.install(self.cfg, chosen, self.borrow, claude_bin=str(bad), versions=versions)
        self.assertIn("boom", str(cm.exception))


class HooksCase(Base):
    """フックの行（書き込みの記録と読んだ証拠のフックと coldwrite）は隔離した設定の settings.json の hooks に置く。Archon は節が plugins: で
    名指さないプラグインを切るが、settingSources: [user] の節は利用者の設定のフックを読む"""

    def hooks(self):
        return json.loads((self.cfg / "settings.json").read_text())["hooks"]

    def test_install_puts_recorder_hook_in_settings(self):
        self.install()
        row = self.hooks()["PostToolUse"][0]
        self.assertEqual(row, {"matcher": "Edit|Write|NotebookEdit", "hooks": [{"type": "command", "command": shlex.join(
            (sys.executable, str(LIB / "record-write.py"), str(self.cfg / "works-writes")))}]})
        self.assertNotIn("timeout", json.dumps(row), "期限の鍵を書かない（E12）")
        self.assertTrue((self.cfg / "works-writes").is_dir(), "記録の根を作る")

    def test_install_puts_read_recorder_hook_in_settings(self):
        """読んだ証拠のフック（record-read.py）を Read と Agent・WebFetch・WebSearch に掛け、記録の根 works-reads/ を作る。
        無ければ計画と事前審査の読んだ証拠の節は「記録の根が無い」としか書けない"""
        self.install()
        row = self.hooks()["PostToolUse"][1]
        self.assertEqual(row, {"matcher": "Read|Agent|WebFetch|WebSearch", "hooks": [{"type": "command", "command": shlex.join(
            (sys.executable, str(LIB / "record-read.py"), str(self.cfg / "works-reads")))}]})
        self.assertNotIn("timeout", json.dumps(row), "期限の鍵を書かない（E12）")
        self.assertTrue((self.cfg / "works-reads").is_dir(), "記録の根を作る")

    def test_coldwrite_hooks_go_to_settings_not_plugin_names(self):
        """coldwrite の hooks.json の表を settings.json に置き、プラグインとしては入れない（前の版が入れた物は外す）。
        表がプラグインの置き場を指す字を持てば、置かずに名指して止まる"""
        stale = f"coldwrite@{MP}"
        _put(self.cfg / "plugins" / "installed_plugins.json",
             json.dumps({"version": 2, "plugins": {stale: [{"scope": "user", "installPath": "/x", "version": "0"}]}}))
        _put(self.cfg / "works-marketplace" / "coldwrite" / ".claude-plugin" / "plugin.json", "{}")
        rec = self.install()
        self.assertEqual(self.hooks()["PreToolUse"], COLDWRITE_HOOKS["PreToolUse"])
        self.assertNotIn(stale, json.loads((self.cfg / "settings.json").read_text()).get("enabledPlugins", {}))
        self.assertIn(["plugin", "uninstall", stale], self.calls())
        self.assertNotIn(["plugin", "install", stale], self.calls())
        self.assertFalse((self.cfg / "works-marketplace" / "coldwrite").exists())
        self.assertEqual((rec["coldwrite"]["loaded"], rec["coldwrite"]["hooks"]), (True, COLDWRITE_HOOKS))
        hooks_json = installed_dir(self.user, "coldwrite") / "hooks" / "hooks.json"
        hooks_json.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [
            {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/check.sh"}]}]}}), encoding="utf-8")
        before = (self.cfg / "settings.json").read_bytes()
        with self.assertRaises(toolset.ToolsetError) as cm:
            self.install()
        self.assertIn("CLAUDE_PLUGIN_", str(cm.exception))
        self.assertIn("coldwrite", str(cm.exception))
        self.assertEqual((self.cfg / "settings.json").read_bytes(), before, "置かずに止める")

    def test_coldwrite_skipped_leaves_no_hooks(self):
        """coldwrite を見送る利用者（E14）の設定には coldwrite の行を置かない（前の起動が置いた行も消える）"""
        self.install()
        r = self.cli("install", "--claude", str(self.claude), str(self.cfg), WORKS_FACTORY_COLDWRITE_MARKETPLACE="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.hooks(), {"PostToolUse": toolset.recorder_rows(self.cfg)})
        self.assertNotIn("coldwrite", json.loads((self.cfg / toolset.RECORD).read_text()))

    def test_guard_allows_only_the_known_hooks(self):
        """柵が通すのは記録のフックの行と、記録に載せた借りる物の行だけ。ほかの行は名指す"""
        self.install()
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        settings = json.loads((self.cfg / "settings.json").read_text())
        other_root = dict(toolset.recorder_row(self.tmp / "elsewhere"))
        cases = {
            "settings.json の hooks の行 PostToolUse:Edit|Write|NotebookEdit": ("PostToolUse", other_root),
            "settings.json の hooks の行 PreToolUse:Write": ("PreToolUse", {"matcher": "Write", "hooks": [
                {"type": "prompt", "prompt": "別の判定"}]}),
            "settings.json の hooks の行 SessionStart:（matcher なし）": ("SessionStart", {"hooks": [
                {"type": "command", "command": "echo hi"}]}),
        }
        for name, (event, row) in cases.items():
            with self.subTest(name):
                hooks = {k: list(v) for k, v in settings["hooks"].items()}
                hooks.setdefault(event, []).append(row)
                (self.cfg / "settings.json").write_text(json.dumps({**settings, "hooks": hooks}), encoding="utf-8")
                self.assertEqual(toolset.guard(self.cfg, self.borrow), [name])
        (self.cfg / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (self.cfg / toolset.RECORD).unlink()
        self.assertEqual(toolset.guard(self.cfg, self.borrow), ["settings.json の hooks の行 PreToolUse:Write"],
                         "記録に載っていない借りる物の行は知らない行")

    def test_guard_allows_the_read_recorder_hook(self):
        """柵は読んだ証拠のフックの行を、別の works-factory の置き場の記録器でも通す。別の根・相対パスの記録器の行と、フォルダでない
        works-reads は名指す"""
        self.install()
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        settings = json.loads((self.cfg / "settings.json").read_text())
        row = toolset.read_recorder_row(self.cfg)

        def with_command(*argv):
            return {**row, "hooks": [{"type": "command", "command": shlex.join(argv)}]}

        named = "settings.json の hooks の行 PostToolUse:Read|Agent|WebFetch|WebSearch"
        cases = {
            "別の置き場の記録器": (with_command(sys.executable, str(self.tmp / "other" / "bin" / "_lib" / "record-read.py"),
                                              str(self.cfg / "works-reads")), []),
            "別の根": (toolset.read_recorder_row(self.tmp / "elsewhere"), [named]),
            "相対パスの記録器": (with_command(sys.executable, "other/record-read.py", str(self.cfg / "works-reads")), [named]),
            "書き込みの根を指す": (with_command(sys.executable, str(LIB / "record-read.py"), str(self.cfg / "works-writes")),
                                  [named]),
        }
        for name, (put, want) in cases.items():
            with self.subTest(name):
                hooks = {**settings["hooks"], "PostToolUse": [toolset.recorder_row(self.cfg), put]}
                (self.cfg / "settings.json").write_text(json.dumps({**settings, "hooks": hooks}), encoding="utf-8")
                self.assertEqual(toolset.guard(self.cfg, self.borrow), want)
        (self.cfg / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (self.cfg / "works-reads").rmdir()
        (self.cfg / "works-reads").write_text("x\n", encoding="utf-8")
        self.assertEqual(toolset.guard(self.cfg, self.borrow), ["works-reads（フォルダでない）"])

    def test_install_over_recorder_row_of_another_checkout(self):
        """同じ対象を別の works-factory の置き場（clone・worktree）から起動した後でも、柵は記録のフックの行を通し、
        install が今の置き場の行に書き直す"""
        self.install()
        settings = json.loads((self.cfg / "settings.json").read_text())
        other = shlex.join([sys.executable, str(self.tmp / "other-checkout" / "bin" / "_lib" / "record-write.py"),
                            str(self.cfg / "works-writes")])
        settings["hooks"]["PostToolUse"][0] = {"matcher": toolset.WRITE_MATCHER,
                                               "hooks": [{"type": "command", "command": other}]}
        (self.cfg / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        self.install()
        self.assertEqual(self.hooks()["PostToolUse"], toolset.recorder_rows(self.cfg))
        settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = shlex.join(
            [sys.executable, "other-checkout/record-write.py", str(self.cfg / "works-writes")])
        (self.cfg / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        self.assertEqual(toolset.guard(self.cfg, self.borrow),
                         ["settings.json の hooks の行 PostToolUse:Edit|Write|NotebookEdit"], "相対パスの記録器は通さない")


class DenyCase(Base):
    """隔離した設定の settings.json の permissions は、いつも役の git push を拒み（#505。今の works の adapter.NO_POST_DENY）、
    公開ベンチの run（WORKS_FACTORY_DENY_WEB=1）では WebFetch・WebSearch も拒む（#435）。柵は install が置く形の時だけ受ける"""

    def settings(self):
        return json.loads((self.cfg / "settings.json").read_text())

    def test_deny_web_install_writes_exact_permissions(self):
        found, vers = self.sources()
        toolset.install(self.cfg, found, self.borrow, claude_bin=str(self.claude), versions=vers, deny_web=True)
        self.assertEqual(self.settings()["permissions"], {"deny": ["Bash(git push:*)", "WebFetch", "WebSearch"]})
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        self.install()
        self.assertEqual(self.settings()["permissions"], {"deny": ["Bash(git push:*)"]}, "同じ家を普段の run に使い回しても web の拒みを残さない")

    def test_plain_install_denies_push_only(self):
        self.install()
        self.assertEqual(self.settings()["permissions"], {"deny": ["Bash(git push:*)"]})
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])

    def test_web_only_permissions_of_the_former_install_are_known(self):
        self.install()
        _put(self.cfg / "settings.json", json.dumps({**self.settings(), "permissions": {"deny": ["WebFetch", "WebSearch"]}}))
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])

    def test_other_permissions_are_outside(self):
        self.install()
        _put(self.cfg / "settings.json", json.dumps({**self.settings(), "permissions": {"allow": ["Bash"]}}))
        self.assertEqual(toolset.guard(self.cfg, self.borrow), ["settings.json の鍵 permissions"])

    def test_cli_install_denies_web_by_env(self):
        r = self.cli("install", "--no-plugins", str(self.cfg), **{toolset.DENY_WEB_ENV: "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.settings()["permissions"], toolset.permissions(deny_web=True))
        self.assertEqual(self.cli("guard", str(self.cfg)).returncode, 0)


class GuardCase(Base):
    def put(self, rel, body="x\n"):
        p = self.cfg / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    def test_official_marketplace_is_not_outside(self):
        """Claude Code が起動の時に隔離した設定へ足す公式の marketplace（名と GitHub の repo が合う行）は、選んだ物の外に数えない
        （登録だけでプラグインは増えない。これを拒むと wait・show が全部落ちていた）"""
        self.put("plugins/known_marketplaces.json",
                 '{"claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"}}}')
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])

    def test_guard_refuses_foreign(self):
        """一覧の外を 1 つずつ置くと、そのたびにちょうど 1 つ、名前つきで並ぶ"""
        cases = {
            "CLAUDE.md": lambda: self.put("CLAUDE.md"),
            "settings.local.json": lambda: self.put("settings.local.json", "{}"),
            "rules/": lambda: self.put("rules/a.md"),
            "agents/": lambda: self.put("agents/a.md"),
            "commands/": lambda: self.put("commands/a.md"),
            "output-styles/": lambda: self.put("output-styles/a.md"),
            "skills/mine/": lambda: self.put("skills/mine/SKILL.md"),
            "works-parts/other/a.md": lambda: self.put("works-parts/other/a.md"),
            "works-parts（フォルダでない）": lambda: self.put("works-parts"),
            "works-parts/superpowers/link": lambda: (self.put("target.md"),
                                                     (self.cfg / "works-parts" / "superpowers").mkdir(parents=True),
                                                     (self.cfg / "works-parts" / "superpowers" / "link").symlink_to(
                                                         self.cfg / "target.md")),
            "settings.json の鍵 permissions": lambda: self.put("settings.json", '{"permissions": {"allow": []}}'),
            "settings.json の hooks の行 PreToolUse:Bash": lambda: self.put(
                "settings.json", '{"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}'),
            "settings.json の hooks（表でない）": lambda: self.put("settings.json", '{"hooks": []}'),
            "works-writes（フォルダでない）": lambda: self.put("works-writes"),
            "marketplace x（settings.json）": lambda: self.put("settings.json", '{"extraKnownMarketplaces": {"x": {}}}'),
            "marketplace x（plugins/known_marketplaces.json）": lambda: self.put("plugins/known_marketplaces.json",
                                                                                  '{"x": {}}'),
            "settings.json（JSON の表として読めない）": lambda: self.put("settings.json", "{"),
            # 公式の名でも repo が違えば外に数える（名だけで通さない）
            "marketplace claude-plugins-official（plugins/known_marketplaces.json）": lambda: self.put(
                "plugins/known_marketplaces.json",
                '{"claude-plugins-official": {"source": {"source": "github", "repo": "someone/claude-plugins-official"}}}'),
        }
        for name, make in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.cfg)
                self.cfg.mkdir()
                make()
                found = toolset.guard(self.cfg, self.borrow)
                self.assertEqual(found, [name])
                r = self.cli("guard", str(self.cfg))
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn(name, r.stderr)
                self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_guard_leaves_foreign_plugins_to_archon(self):
        """一覧の外のプラグインを有効にしても入れても、guard は名指さない（ノードの plugins: の照合が、名指さない物を切り、
        読み込まれた物があればノードを落とす）。CLI も何も出さずに終了コード 0"""
        self.put("settings.json", '{"enabledPlugins": {"other@x": true}}')
        self.put("plugins/installed_plugins.json", '{"version": 2, "plugins": {"other@x": []}}')
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        r = self.cli("guard", str(self.cfg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")

    def test_guard_ignores_claude_state(self):
        for rel in ("projects/p/s.jsonl", ".claude.json", "backups/.claude.json.backup.1", "remote-settings.json",
                    "policy-limits.json", "plugins/cache/x/y/1/a", "plugins/marketplaces/x/a", "skills/.DS_Store"):
            self.put(rel)
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        self.assertEqual(self.cli("guard", str(self.cfg)).returncode, 0)

    def test_install_refuses_before_writing(self):
        self.put("CLAUDE.md")
        r = self.cli("install", "--claude", str(self.claude), str(self.cfg))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("CLAUDE.md", r.stderr)
        self.assertEqual(files_under(self.cfg), ["CLAUDE.md"], "止まる前に写した")
        self.assertEqual(self.calls(), [])


class CliCase(Base):
    def test_cli_install_matches_api(self):
        r = self.cli("install", "--claude", str(self.claude), str(self.cfg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        self.assertEqual(json.loads((self.cfg / "settings.json").read_text())["enabledPlugins"],
                         {f"{n}@{MP}": True for n in PLUGINS})
        self.assertEqual(sorted(p.name for p in (self.cfg / "skills").iterdir()), sorted(BORROW_SKILLS))

    def test_cli_no_plugins_copies_skills_and_calls_no_claude(self):
        """認証の要らない道（validate・テスト）は claude を起こさない。スキルは写す（Archon の validate も同じ置き場で探す）"""
        r = self.cli("install", "--no-plugins", str(self.cfg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(sorted(p.name for p in (self.cfg / "skills").iterdir()), sorted(BORROW_SKILLS))
        self.assertEqual(json.loads((self.cfg / "settings.json").read_text()),
                         {"hooks": {"PostToolUse": toolset.recorder_rows(self.cfg), **COLDWRITE_HOOKS},
                          "permissions": toolset.permissions(deny_web=False)},
                         "フックの行と拒みはプラグインでないので、CLI を呼ばない道でも置く")
        self.assertFalse((self.cfg / "works-marketplace").exists())

    def test_cli_missing_tools_stop_before_writing(self):
        """借りる物が入っていなければ、1 物 1 行の理由と入れるコマンドを出して終了コード 2。何も写さず claude も起こさない。
        --user-config が env の CLAUDE_CONFIG_DIR より勝つ。superpowers は works の写しから入れるので、入れるコマンドを出さない"""
        empty = self.tmp / "empty"
        empty.mkdir()
        for args, env in ((["--user-config", str(empty)], {}), ([], {"CLAUDE_CONFIG_DIR": str(empty)})):
            with self.subTest(args=args):
                r = self.cli("install", "--claude", str(self.claude), *args, str(self.cfg), **env)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertEqual(len([ln for ln in r.stderr.splitlines() if ln.startswith("- ")]), 2, r.stderr)
                self.assertNotIn("superpowers@superpowers-marketplace", r.stderr)
                self.assertEqual(files_under(self.cfg), [])
                self.assertEqual(self.calls(), [])
        r = self.cli("install", "--no-plugins", str(self.cfg), CLAUDE_CONFIG_DIR=str(empty))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(f"coldwrite@{COLDWRITE_MP}", r.stderr)

    def test_cli_install_skips_coldwrite_without_its_marketplace(self):
        """利用者の設定に coldwrite の marketplace が無い（普通の利用者）: 止めずに 1 行で名指して見送り、ほかは組む"""
        r = self.cli("install", "--claude", str(self.claude), str(self.cfg), WORKS_FACTORY_COLDWRITE_MARKETPLACE="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("coldwrite は借りずに見送る", r.stderr)
        self.assertEqual(json.loads((self.cfg / "settings.json").read_text())["enabledPlugins"],
                         {f"pr-review-toolkit@{MP}": True})
        self.assertEqual(sorted(json.loads((self.cfg / toolset.RECORD).read_text())), ["pr-review-toolkit", "superpowers"])
        r = self.cli("guard", str(self.cfg), WORKS_FACTORY_COLDWRITE_MARKETPLACE="")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_cli_refuses_relative_user_config(self):
        """利用者の設定の置き場は絶対パスだけを受ける（相対は殻が cd の前に直す。cd の後に対象から解くと別の置き場を読む）。
        --user-config も env の CLAUDE_CONFIG_DIR も、相対なら何も写さずに名指しで止まる（読める置き場が cwd に在っても）"""
        for args, env in ((["--user-config", "user"], {}), ([], {"CLAUDE_CONFIG_DIR": "user"})):
            with self.subTest(args=args, env=env):
                r = subprocess.run([sys.executable, str(TOOLSET), "install", "--no-plugins", *args, str(self.cfg)],
                                   capture_output=True, text=True, encoding="utf-8", cwd=self.tmp,
                                   env=hermetic.child_env(**{"CLAUDE_CONFIG_DIR": str(self.user), **COLDWRITE_ENV, **env}))
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("絶対", r.stderr)
                self.assertEqual(files_under(self.cfg), [])

    def test_cli_refuses_user_config_that_is_the_isolated_config(self):
        """殻の中から入れ子で打つと、利用者の設定の置き場が隔離した置き場そのものになる。『入っていない』でなく、それを名指しして
        止まる（symlink を挟んでも同じ置き場と見る）"""
        link = self.tmp / "cfg-link"
        link.symlink_to(self.cfg)
        for where in (self.cfg, link):
            for args, env in ((["--user-config", str(where)], {}), ([], {"CLAUDE_CONFIG_DIR": str(where)})):
                with self.subTest(where=where.name, args=args):
                    r = self.cli("install", "--no-plugins", *args, str(self.cfg), **env)
                    self.assertEqual(r.returncode, 2, r.stderr)
                    self.assertIn("隔離", r.stderr)
                    self.assertNotIn("入っていない", r.stderr)
                    self.assertEqual(files_under(self.cfg), [])

    def test_cli_usage(self):
        for args in ([], ["install"], ["install", str(self.cfg)], ["bogus", str(self.cfg)], ["guard"], ["contract", "a", "b"]):
            with self.subTest(args):
                r = self.cli(*args)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("toolset.py", r.stderr)

    def test_cli_contract_on_the_vendored_copy_is_0(self):
        r = self.cli("contract")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("全部そろう", r.stdout)

    def test_cli_contract_on_a_cache_version_names_broken_anchors(self):   # 偽のキャッシュの 9.9.0 は錨の文を持たない
        r = self.cli("contract", "9.9.0")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("tdd: 錨 SUITE", r.stdout)


    def test_cli_contract_on_a_missing_version_is_2_and_names_it(self):
        r = self.cli("contract", "8.8.8")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("8.8.8", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_cli_contract_without_pin_is_2_and_says_how_to_fix(self):
        """borrow.json に superpowers の pin が無ければ、写しの版が決まらない。版を名指しても名指さなくても、トレースバックで
        なく 1 行で 2（偽の pack を一時の置き場に組む）"""
        pack = fake_pack(self.tmp / "pack")
        bj = pack / "lib" / "borrow" / "borrow.json"
        borrow = json.loads(bj.read_text(encoding="utf-8"))
        del borrow["superpowers"]["pin"]
        bj.write_text(json.dumps(borrow, ensure_ascii=False), encoding="utf-8")
        for args in ([], ["9.9.0"]):
            with self.subTest(args):
                r = subprocess.run([sys.executable, str(pack / "bin" / "_lib" / "toolset.py"), "contract", *args],
                                   capture_output=True, text=True, encoding="utf-8",
                                   env=hermetic.child_env(CLAUDE_CONFIG_DIR=str(self.user)))
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("toolset.py: borrow.json の superpowers に pin が無い（写しの版が決まらない。"
                              "bin/_lib/toolset.py vendor で写す）", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

if __name__ == "__main__":
    unittest.main()


class McpCase(Base):
    """借りる MCP は無い（持ち主 2026-10-09 に Context7 をやめ、kind "mcp" の借りる物と works-mcp.json を書く口を消した）。前の版が
    隔離した設定の置き場に書いた works-mcp.json は、Claude Code も包みも読まない物なので、柵は数えず、組むのも止めない（消しもしない）"""

    def test_borrow_has_no_mcp(self):
        self.assertNotIn("context7", self.borrow)
        self.assertEqual({i["kind"] for i in self.borrow.values()}, {"skills", "plugin"})
        self.assertFalse(hasattr(toolset, "MCP_FILE"))

    def test_kind_mcp_is_no_longer_known(self):
        bad = {"context7": {"kind": "mcp", "transport": "http", "url": "https://mcp.context7.com/mcp", "licence": "MIT"}}
        with self.assertRaises(toolset.ToolsetError) as cm:
            toolset.installed_sources(self.tmp / "user", bad)
        self.assertIn("kind 'mcp' を知らない（skills・plugin）", str(cm.exception))

    def test_leftover_mcp_file_does_not_stop_install(self):
        self.cfg.mkdir(parents=True, exist_ok=True)
        left = self.cfg / "works-mcp.json"
        left.write_text(json.dumps({"mcpServers": {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}}))
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])
        rec = self.install()
        self.assertNotIn("context7", rec)
        self.assertEqual(toolset.guard(self.cfg, self.borrow), [])


PIN_V = toolset.load_borrow(BORROW)["superpowers"]["pin"]["version"]


def _bumped(pin):
    """pin の最後の段に 1 を足した、固定より新しい版（数で読めなければ None）"""
    key = toolset._version_key(pin)
    return None if key is None else ".".join(str(n) for n in (*key[:-1], key[-1] + 1))


def _newer_than(pin):
    """数の組では pin より新しく、字の順では pin より古い版（頭に 0 を付けて割る。作れなければ None）"""
    bumped = _bumped(pin)
    if bumped is None:
        return None
    parts = bumped.split(".")
    i = next((i for i, p in enumerate(parts) if not p.startswith("0")), None)
    if i is None:
        return None
    parts[i] = "0" + parts[i]
    return ".".join(parts)


def _older_than(pin):
    """pin の 0 でない最後の段から 1 を引いた、固定より古い版（作れなければ None）"""
    key = toolset._version_key(pin)
    if key is None or not any(key):
        return None
    i = max(i for i, n in enumerate(key) if n)
    return ".".join(str(n) for n in (*key[:i], key[i] - 1, *key[i + 1:]))


class NewerCase(Base):
    """newer（開発の再開の確かめ）: 利用者のキャッシュの superpowers の版のフォルダ・installed_plugins.json の行・marketplace の
    一覧の版を、写した固定の版と数の組で比べ、新しい版には固定との違いと節の契約の破れと、増えた人に聞く文を出す。何も書かず、
    読めない物は 1 行で名指して続け、終了コードは 0（使い方の誤りだけ 2）。偽の利用者の設定には偽の superpowers 9.9.0 を置かない"""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.tmp / "user")   # Base の偽の superpowers 9.9.0 のフォルダも消す（版のフォルダは候補に数える）
        self.user = make_user_config(self.tmp / "user", only={"coldwrite", "pr-review-toolkit"})
        self.item = toolset.load_borrow(BORROW)["superpowers"]
        # newer が読む pack は偽の物（写しの固定の commit を試験が書き換えても本物の borrow.json に触れない）
        self.pack = fake_pack(self.tmp / "pack")
        self.borrow_dir = self.pack / "lib" / "borrow"
        self.upstream = self.make_upstream(PIN_V)

    def make_upstream(self, *versions, name="upstream", light=False):
        """手元に、versions の tag v<版>（light なら軽量の tag、既定は注釈つき）を打った git リポジトリを作って返す（上流の代わり）。
        固定の版の tag を打ったら、その tag が指す commit を偽の pack の borrow.json の pin の commit に書く"""
        repo = self.tmp / name
        repo.mkdir()
        gitkit.git(repo, "init", "-q")
        gitkit.git(repo, "commit", "-q", "--allow-empty", "-m", "upstream")
        for v in versions:
            self.tag(repo, v, light)
        if PIN_V in versions:
            self.set_pin_commit(gitkit.git(repo, "rev-parse", f"v{PIN_V}^{{commit}}"))
        return repo

    def tag(self, repo, v, light=False):
        gitkit.git(repo, "tag", "-f", f"v{v}", *(() if light else ("-a", "-m", f"v{v}")))

    def set_pin_commit(self, commit):
        p = self.borrow_dir / "borrow.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["superpowers"]["pin"]["commit"] = commit
        p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def repoint(self, v, light=False):
        """上流の tag v<版> を、新しい空の commit に付け直す。その commit を返す"""
        gitkit.git(self.upstream, "commit", "-q", "--allow-empty", "-m", "moved")
        self.tag(self.upstream, v, light)
        return gitkit.git(self.upstream, "rev-parse", "HEAD")

    def cli(self, *args, **env):
        """偽の pack の toolset.py を、上流の URL を self.upstream（リポジトリのパス。無いパスなら届かない上流）へ向け替えて起こす"""
        return subprocess.run([sys.executable, str(self.pack / "bin" / "_lib" / "toolset.py"), *args], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env(
                                  **{"CLAUDE_CONFIG_DIR": str(self.user), **upstream_redirect(self.upstream), **env}))

    def newer_out(self, **env):
        """newer を起こし、終了コード 0 を確かめて標準出力を返す"""
        r = self.cli("newer", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def assert_unchecked(self, out, what):
        """what を『確かめられなかった』と名指し、締めの『無い』を出さず、最後の行を出している"""
        self.assertIn(f"確かめられなかった: {what}", out)
        self.assertNotIn("より新しい版・違う中身は", out)
        self.assertIn(toolset.NEWER_LAST, out)

    def add_version(self, v, edit=None):
        """写しを <user>/plugins/cache/superpowers-marketplace/superpowers/<v>/ に写し、edit の相対パスを書き換え、
        installed_plugins.json に user の行を足す"""
        d = self.user / "plugins" / "cache" / self.item["marketplace"] / "superpowers" / v
        shutil.copytree(spseam.vendored_dir(self.item), d)
        for rel, body in (edit or {}).items():
            _put(d / rel, body)
        ip = self.user / "plugins" / "installed_plugins.json"
        doc = json.loads(ip.read_text(encoding="utf-8"))
        doc["plugins"].setdefault(f"superpowers@{self.item['marketplace']}", []).append(
            {"scope": "user", "installPath": str(d), "version": v, "installedAt": "2026-10-02T00:00:00.000Z"})
        ip.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return d

    def put_marketplace_raw(self, text):
        loc = self.tmp / "marketplaces" / self.item["marketplace"]
        _put(self.user / "plugins" / "known_marketplaces.json",
             json.dumps({self.item["marketplace"]: {"source": {"source": "github", "repo": self.item["marketplace_repo"]},
                                                    "installLocation": str(loc)}}))
        _put(loc / ".claude-plugin" / "marketplace.json", text)

    def put_marketplace(self, doc):
        self.put_marketplace_raw(json.dumps(doc))

    def test_newer_compares_numerically_and_applies_the_contract(self):
        newer, older = _newer_than(PIN_V), _older_than(PIN_V)
        if newer is None or older is None:
            self.fail(f"固定 {PIN_V} からは字と数の割れる版か古い版を作れない")
        self.assertLess(newer, PIN_V)   # 字の順では古い（字で比べる実装なら飛ばしてしまう版）
        self.assertGreater(toolset._version_key(newer), toolset._version_key(PIN_V))
        self.add_version(newer, edit={"skills/test-driven-development/SKILL.md": "Ask your human partner now.\n"})
        self.add_version(older)
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"superpowers {newer}", r.stdout)
        self.assertNotIn(f"superpowers {older}", r.stdout)
        self.assertIn("skills/test-driven-development/SKILL.md: 中身が固定と違う", r.stdout)
        self.assertIn("人に聞く文が増えた: skills/test-driven-development/SKILL.md: Ask your human partner now.", r.stdout)
        self.assertIn("tdd: 錨", r.stdout)
        self.assertIn("版を上げるかは人が決める", r.stdout)

    def test_newer_reports_same_version_with_other_content(self):
        self.add_version(PIN_V, edit={"skills/receiving-code-review/SKILL.md": "x\n"})
        self.assertIn("写しと同じ版なのに中身が違う", self.cli("newer").stdout)

    def test_newer_lists_marketplace_only_versions(self):
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.add_version(PIN_V)
        self.put_marketplace({"plugins": [{"name": "superpowers", "version": newer}]})
        self.assertIn(f"superpowers {newer}: marketplace の一覧に在る", self.cli("newer").stdout)

    def test_newer_with_nothing_newer_says_one_line(self):
        self.add_version(PIN_V)
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("より新しい版・違う中身は、上流の tag にも手元にも marketplace の一覧にも無い", r.stdout)
        self.assertNotIn("確かめられなかった", r.stdout)

    def test_newer_names_upstream_tags_newer_than_the_pin(self):
        """手元に固定の版しか無くても、上流の tag に固定より新しい版が在れば名指し、固定と同じ・古い tag は名指さず、締めの『無い』を出さない"""
        newer, older = _bumped(PIN_V), _older_than(PIN_V)
        if newer is None or older is None:
            self.fail(f"固定 {PIN_V} から新しい版と古い版を作れない")
        self.upstream = self.make_upstream(older, PIN_V, newer, name="upstream-tags")
        self.add_version(PIN_V)
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"superpowers {newer}: 上流の tag に在る", r.stdout)
        self.assertNotIn(f"superpowers {older}", r.stdout)
        self.assertNotIn(f"superpowers {PIN_V}", r.stdout)
        self.assertNotIn("確かめられなかった", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)

    def test_newer_unreachable_upstream_is_named_and_not_closed_as_nothing(self):
        """上流に届かない時は『確かめられなかった: 上流の tag』を 1 行出し、締めの『無い』を出さず、終了コード 0 で最後の行を出す"""
        self.upstream = self.tmp / "no-such-upstream"
        self.add_version(PIN_V)
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("確かめられなかった: 上流の tag", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)
        self.assertIn(toolset.NEWER_LAST, r.stdout)

    def test_newer_upstream_without_the_pinned_tag_is_named_and_not_closed_as_nothing(self):
        """上流が tag を 1 本も返さない（空のリポジトリ・向け先の誤り）時も、固定の版の tag すら見えないので
        『確かめられなかった: 上流の tag』を出し、締めの『無い』を出さない"""
        self.upstream = self.make_upstream(name="upstream-empty")
        self.add_version(PIN_V)
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("確かめられなかった: 上流の tag", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)
        self.assertIn(toolset.NEWER_LAST, r.stdout)

    def test_newer_unreadable_marketplace_is_not_closed_as_nothing(self):
        """上流に新しい tag が無くても、marketplace の一覧が読めない時は『確かめられなかった: marketplace の一覧』を出し、締めの『無い』を出さない"""
        self.add_version(PIN_V)
        self.put_marketplace_raw("{壊れた")
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("確かめられなかった: marketplace の一覧", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)

    def test_newer_names_the_marketplace_list_as_a_local_copy_with_its_time(self):
        """一覧にだけ在る版の行は、一覧が手元の写しであることと、一覧の更新の時刻（marketplace.json の mtime）を添える"""
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.add_version(PIN_V)
        self.put_marketplace({"plugins": [{"name": "superpowers", "version": newer}]})
        at = datetime.datetime(2026, 3, 5, 12, 34, 56, tzinfo=datetime.timezone.utc)
        os.utime(self.tmp / "marketplaces" / self.item["marketplace"] / ".claude-plugin" / "marketplace.json",
                 (at.timestamp(), at.timestamp()))
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"superpowers {newer}: marketplace の一覧に在る", r.stdout)
        self.assertIn("手元の写し", r.stdout)
        self.assertIn("2026-03-05", r.stdout)

    def test_newer_names_unparsable_versions(self):
        self.add_version("latest")
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        # 数で読めない名の版のフォルダでも、中身が固定と同じで違いが無ければ名指さず、締めの『違いは無い』を出す
        self.assertNotIn("superpowers latest", r.stdout)
        self.assertIn("より新しい版・違う中身は、上流の tag にも手元にも marketplace の一覧にも無い", r.stdout)
        # 中身が違う版は、名が数で読めなくても素通しせず、pin と節の契約を当てて名指し、締めの『違いは無い』を出さない
        self.add_version("8ca22dba9a94", edit={"skills/test-driven-development/SKILL.md": "x\n"})
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("superpowers 8ca22dba9a94", r.stdout)
        self.assertIn("skills/test-driven-development/SKILL.md: 中身が固定と違う", r.stdout)
        self.assertIn("tdd: 錨", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)

    def test_newer_without_superpowers_installed(self):
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("superpowers が入っていない", r.stdout)

    def test_newer_unreadable_marketplace_is_named_not_fatal(self):
        self.add_version(PIN_V)
        self.put_marketplace_raw("{壊れた")
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("marketplace の一覧を読めない", r.stdout)

    def test_newer_writes_nothing(self):
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.add_version(newer)
        moved = self.repoint(PIN_V)   # 上流の固定の tag が別の commit を指しても、写しの pin を取り直さない
        before = {p: p.read_bytes() for p in self.user.rglob("*") if p.is_file()}
        pack = {p: p.read_bytes() for p in self.borrow_dir.rglob("*") if p.is_file()}
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"superpowers {newer}", r.stdout)
        self.assertIn(f"と違う（{moved}）", r.stdout)
        self.assertEqual({p: p.read_bytes() for p in self.user.rglob("*") if p.is_file()}, before)
        self.assertEqual({p: p.read_bytes() for p in self.borrow_dir.rglob("*") if p.is_file()}, pack)

    def test_newer_takes_no_version(self):
        """newer は版を名指さない（比べる元は写し）。版を渡すのは使い方の誤りで 2"""
        r = self.cli("newer", "6.10.0")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("toolset.py", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_newer_unreadable_installed_plugins_is_named_not_fatal(self):
        """installed_plugins.json が JSON として読めなくても、1 行で名指して版のフォルダの確かめを続ける"""
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.add_version(newer)
        (self.user / "plugins" / "installed_plugins.json").write_text("{壊れた", encoding="utf-8")
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("installed_plugins.json", r.stdout)
        self.assertIn(f"superpowers {newer}", r.stdout)

    def test_newer_names_added_asks_whatever_the_case(self):
        """人に聞く文は大文字・小文字を問わずに拾う（原文には行頭の Human partner が在る）"""
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.add_version(newer, edit={"skills/receiving-code-review/SKILL.md": "Human partner decides this.\n"})
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("人に聞く文が増えた: skills/receiving-code-review/SKILL.md: Human partner decides this.", r.stdout)

    def test_newer_unlistable_version_folders_still_exit_0(self):
        """版のフォルダの一覧を読めない（権限が無い）時も、1 行で名指して最後の行を出し、終了コード 0"""
        base = self.add_version(PIN_V).parent
        base.chmod(0)
        try:
            r = self.cli("newer")
        finally:
            base.chmod(0o755)   # tearDown が一時の置き場を消せるように、ここで戻す
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("読めない物に当たった", r.stdout)
        self.assertIn("版を上げるかは人が決める", r.stdout)
        self.assertNotIn("Traceback", r.stderr)

    def test_newer_marketplace_unparsable_version_is_not_closed_as_nothing(self):
        """一覧にだけ在る数で読めない版も、同じ決まりで名指し、締めの『違いは無い』を出さない"""
        self.add_version(PIN_V)
        self.put_marketplace({"plugins": [{"name": "superpowers", "version": "nightly"}]})
        r = self.cli("newer")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("superpowers nightly: marketplace の一覧に在る", r.stdout)
        self.assertNotIn("より新しい版・違う中身は", r.stdout)

    def assert_pinned_tag_moved(self, light):
        """上流の v<固定の版> を、写した commit と別の commit へ付け直すと、その commit を名指し、締めの『無い』を出さない"""
        self.upstream = self.make_upstream(PIN_V, name="upstream-moved", light=light)
        self.add_version(PIN_V)
        moved = self.repoint(PIN_V, light)
        out = self.newer_out()
        self.assertIn(f"上流の tag v{PIN_V} が写した commit", out)
        self.assertIn(f"と違う（{moved}）", out)
        self.assertNotIn("より新しい版・違う中身は", out)

    def test_newer_names_pinned_tag_moved_to_another_commit(self):
        self.assert_pinned_tag_moved(light=False)

    def test_newer_reads_lightweight_pinned_tag_commit(self):
        self.assert_pinned_tag_moved(light=True)

    def test_newer_names_every_source_of_the_same_version(self):
        """同じ新しい版が上流の tag と marketplace の一覧の両方に在る時は、その版の 1 行に両方の源を名指し、
        入れるコマンドと一覧の写しの時刻を添える（どちらかの行が畳まれて消えない）"""
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.upstream = self.make_upstream(PIN_V, newer, name="upstream-tags")
        self.add_version(PIN_V)
        self.put_marketplace({"plugins": [{"name": "superpowers", "version": newer}]})
        rows = [ln for ln in self.newer_out().splitlines() if ln.startswith(f"superpowers {newer}:")]
        self.assertEqual(len(rows), 1, rows)
        for want in ("上流の tag", "marketplace の一覧", f"claude plugin update superpowers@{self.item['marketplace']}", "手元の写し"):
            self.assertIn(want, rows[0])

    def test_newer_without_git_is_unchecked_not_nothing(self):
        self.add_version(PIN_V)
        no_git = self.tmp / "no-git"
        no_git.mkdir()
        self.assert_unchecked(self.newer_out(PATH=str(no_git)), "上流の tag（git が見つからない")

    def test_newer_unreadable_installed_plugins_alone_is_not_closed_as_nothing(self):
        """新しい版がどこにも無く、読めないのが installed_plugins.json だけでも、締めの『無い』を出さない"""
        self.add_version(PIN_V)
        (self.user / "plugins" / "installed_plugins.json").write_text("{壊れた", encoding="utf-8")
        self.assert_unchecked(self.newer_out(), "installed_plugins.json を読めない")

    def test_newer_broken_known_marketplaces_is_not_closed_as_nothing(self):
        self.add_version(PIN_V)
        mp = self.item["marketplace"]
        for label, text in (("壊れた JSON", "{壊れた"), ("installLocation が文字列でない", json.dumps({mp: {"installLocation": 5}}))):
            with self.subTest(label):
                _put(self.user / "plugins" / "known_marketplaces.json", text)
                self.assert_unchecked(self.newer_out(), "marketplace の一覧を読めない")

    def test_newer_unreadable_ls_remote_line_is_not_closed_as_nothing(self):
        """固定の tag の行が先に出ても、後ろに読めない行が在れば、読めたことにせず『確かめられなかった』と名指す"""
        self.add_version(PIN_V)
        commit = toolset.load_borrow(self.borrow_dir)["superpowers"]["pin"]["commit"]
        bindir = self.tmp / "fake-bin"
        _put(bindir / "git", f"#!/bin/sh\nprintf '%s\\trefs/tags/v%s\\n' {commit} {PIN_V}\necho 'no tab here'\n", 0o755)
        out = self.newer_out(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
        self.assert_unchecked(out, "上流の tag（git ls-remote の行を読めない")

    def test_upstream_versions_calls_git_directly(self):
        """偽の pack は toolset.py と spseam.py だけで、git の口の写しを持たない。git には ls-remote --tags <上流> だけを渡し、
        端末に認証を聞かせず（GIT_TERMINAL_PROMPT=0）、標準入力を閉じる"""
        commit = toolset.load_borrow(self.borrow_dir)["superpowers"]["pin"]["commit"]
        bindir, seen = self.tmp / "fake-bin", self.tmp / "seen"
        _put(bindir / "git", "#!/bin/sh\n"
             f"printf '%s\\n' \"$*\" \"$GIT_TERMINAL_PROMPT\" > {shlex.quote(str(seen))}\n"
             f"if read -r _; then echo open >> {shlex.quote(str(seen))}; else echo closed >> {shlex.quote(str(seen))}; fi\n"
             f"printf '%s\\trefs/tags/v%s\\n' {commit} {PIN_V}\n", 0o755)
        self.assertEqual([sorted(p.name for p in (self.pack / d).iterdir()) for d in ("bin/_lib", "lib")],
                         [["toolset.py"], ["borrow", "spseam.py"]])
        self.add_version(PIN_V)
        out = self.newer_out(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
        self.assertNotIn("確かめられなかった", out)
        self.assertEqual(seen.read_text(encoding="utf-8").splitlines(),
                         [f"ls-remote --tags {toolset.UPSTREAM_URL}", "0", "closed"])

    def test_upstream_versions_names_missing_git(self):
        no_git = self.tmp / "no-git"
        no_git.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(no_git)}):
            self.assertEqual(toolset._upstream_versions(toolset._version_key(PIN_V)), ([], "git が見つからない", None))

    def test_newer_names_new_tag_and_unchecked_when_pinned_tag_is_missing(self):
        newer = _bumped(PIN_V)
        if newer is None:
            self.fail(f"固定 {PIN_V} から新しい版を作れない")
        self.upstream = self.make_upstream(newer, name="upstream-newer-only")
        self.add_version(PIN_V)
        out = self.newer_out()
        self.assertIn(f"superpowers {newer}: 上流の tag に在る", out)
        self.assert_unchecked(out, "上流の tag")


class RecordNameCase(unittest.TestCase):
    def test_record_name_is_what_lib_versions_reads(self):
        """借りた物の記録の名は、run の版の控え（line の src/versions.py。L-E45）が読む名と同じ（graph は bin を読まないので名を
        2 か所に持つ。docs/design/integration.md の 4.5-7）"""
        versions = archon.src_module("line", "versions")
        self.assertEqual(versions.TOOLSET_RECORD, toolset.RECORD)
