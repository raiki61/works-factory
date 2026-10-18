"""版の取り寄せと置かずに起こす形（bin/_lib/pack.py・place.py）の試験。網には出ない（偽の fetch・install を渡す）。"""
import copy
import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from bin._lib import pack, place
from lib import headdepth, launchgroups
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASF_YAML = ".archon/workflows/sdlc/archon-a.yaml"


def files(root):
    """root の下のファイルを、root からの相対パス → 中身のバイトで返す"""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class PackTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        for rel in ("pack.json", "factory/pack.json"):
            write(self.tmp / rel, (ROOT / rel).read_bytes())

    def change(self, rel, edit):
        path = self.tmp / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        edit(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_archon_version_comes_from_the_asf_pin_only(self):
        asf_pin = json.loads((ROOT / "factory/pack.json").read_text(encoding="utf-8"))
        loaded = pack.load(ROOT)
        self.assertEqual(loaded["archon"]["commit"], asf_pin["integration_revision_required"])
        self.assertEqual(loaded["archon"]["repo"], asf_pin["repository"])
        self.assertEqual(loaded["asf"]["folder"], asf_pin["source_directory"])
        self.assertNotIn(asf_pin["integration_revision_required"], (ROOT / "pack.json").read_text(encoding="utf-8"))

    def test_asf_moving_its_pin_moves_ours(self):
        self.change("factory/pack.json", lambda data: data.update(integration_revision_required="0" * 40))
        self.assertEqual(pack.load(self.tmp)["archon"]["commit"], "0" * 40)

    def test_load_rejects_missing_keys(self):
        self.change("factory/pack.json", lambda data: data.pop("integration_revision_required"))
        self.change("pack.json", lambda data: data.update(ours={}))
        with self.assertRaisesRegex(ValueError, r"ours\.folder.*ours\.pack.*integration_revision_required"):
            pack.load(self.tmp)

    def test_load_rejects_commit_that_is_not_a_full_sha(self):
        for value in ("factory/sdlc-on-dev", "d97d00ef", "D97D00EF15CCE4B15D39E42635E4E86996EC1351", 1, None):
            with self.subTest(value=value):
                self.change("factory/pack.json", lambda data: data.update(integration_revision_required=value))
                with self.assertRaisesRegex(ValueError, "integration_revision_required"):
                    pack.load(self.tmp)


class ArchonSourceTest(unittest.TestCase):
    """源は手元の使い捨ての git リポジトリから本物の git_fetch で取る。install（bun）は偽"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.cache = self.tmp / "cache"
        self.installed = []
        which = mock.patch.object(place.shutil, "which", return_value="/bin/bun")
        self.which = which.start()
        self.addCleanup(which.stop)
        self.pack = self.upstream("up", {place.ENTRY: b"cli", ASF_YAML: b"a"})

    def upstream(self, name, files_by_path):
        """files_by_path を 1 本の commit にした git リポジトリを作り、それを指す pack を返す"""
        repo = self.tmp / name
        for rel, data in {".gitignore": b"node_modules/\n", **files_by_path}.items():
            write(repo / rel, data)
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        loaded = pack.load(ROOT)
        loaded["archon"] = {"repo": repo.as_uri(), "commit": git(repo, "rev-parse", "HEAD")}
        return loaded

    def install(self, source):
        self.installed.append(source.name)
        write(source / "node_modules/.installed", b"")

    def source(self, pack_=None, fetch=place.git_fetch):
        return place.archon_source(pack_ or self.pack, self.cache, fetch, self.install)

    def test_fetches_installs_and_holds_entry_and_asf(self):
        source = self.source()
        self.assertEqual(source, self.cache / "archon" / self.pack["archon"]["commit"])
        self.assertTrue((source / place.ENTRY).is_file())
        self.assertTrue((source / self.pack["asf"]["folder"] / "archon-a.yaml").is_file())
        self.assertTrue((source / "node_modules/.installed").is_file())

    def test_cached_no_fetch(self):
        first = self.source()

        def fetch(repo, commit, dest):
            self.fail("同じ commit の源が在るのに fetch を呼んだ")

        self.assertEqual(self.source(fetch=fetch), first)
        self.assertEqual(len(self.installed), 1)

    def test_broken_cache_is_refused_with_the_way_back(self):
        def edit(source):
            (source / place.ENTRY).write_bytes(b"edited")

        def move_head(source):
            write(source / "extra", b"x")
            git(source, "add", "extra")
            git(source, "commit", "-q", "-m", "moved")

        def drop_deps(source):
            (source / "node_modules/.installed").unlink()
            (source / "node_modules").rmdir()

        for name, breaks, said in (("edited", edit, place.ENTRY), ("moved", move_head, "HEAD"),
                                   ("no deps", drop_deps, "node_modules")):
            with self.subTest(name):
                shutil.rmtree(self.cache, ignore_errors=True)
                source = self.source()
                breaks(source)
                with self.assertRaisesRegex(RuntimeError, said) as caught:
                    self.source()
                self.assertIn(f'rm -rf "{source}"', str(caught.exception))

    def test_without_bun_stops_before_fetching(self):
        self.which.return_value = None

        def fetch(repo, commit, dest):
            self.fail("bun が無いのに fetch を呼んだ")

        with self.assertRaisesRegex(RuntimeError, r"bun が無い.*https://bun\.sh"):
            self.source(fetch=fetch)
        self.assertFalse(self.cache.exists())

    def test_incomplete_source_is_refused(self):
        for missing in (place.ENTRY, ASF_YAML):
            with self.subTest(missing=missing):
                partial = {place.ENTRY: b"cli", ASF_YAML: b"a"}
                del partial[missing]
                partial_pack = self.upstream(f"partial-{len(missing)}", partial)
                with self.assertRaisesRegex(RuntimeError, missing.rsplit("/", 1)[0]):
                    self.source(partial_pack)
                self.assertFalse((self.cache / "archon" / partial_pack["archon"]["commit"]).exists())

    def test_failure_leaves_previous_source(self):
        before = files(self.source())
        newer = copy.deepcopy(self.pack)
        newer["archon"]["commit"] = "0" * 40

        def broken_fetch(repo, commit, dest):
            write(dest / "half", b"half")
            raise OSError("network is unreachable")

        def broken_install(source):
            raise OSError("bun: command not found")

        commit = self.pack["archon"]["commit"]
        newest = self.upstream("newest", {place.ENTRY: b"cli2", ASF_YAML: b"a"})
        for name, pack_, fetch, install in (("fetch", newer, broken_fetch, self.install),
                                            ("install", newest, place.git_fetch, broken_install)):
            with self.subTest(step=name):
                with self.assertRaisesRegex(RuntimeError, pack_["archon"]["commit"]) as caught:
                    place.archon_source(pack_, self.cache, fetch, install)
                self.assertNotIn("\n", str(caught.exception))
                self.assertEqual(files(self.cache / "archon" / commit), before)
                self.assertEqual(sorted(p.name for p in (self.cache / "archon").iterdir()), [commit])


class WorkflowSourceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.pack = pack.load(ROOT)
        self.cache = self.tmp / "cache"
        self.root = self.tmp / "repo"
        write(self.root / "workflows/line/works-factory-line.yaml", b"name: works-factory-line\r\n")
        write(self.root / "workflows/.shared/boundary.py", b"\x00\xff bytes\n")

    def test_archon_reads_the_repo_workflows_as_one_pack(self):
        shim = place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual(files(place.pack_folder(self.pack, shim)), files(self.root / "workflows"))
        self.assertEqual([p.name for p in (shim / place.WORKFLOW_FOLDER).iterdir()], [self.pack["ours"]["pack"]])

    def test_edits_in_the_repo_show_without_placing_again(self):
        shim = place.workflow_source(self.pack, self.root, self.cache)
        write(self.root / "workflows/line/added.yaml", b"added")
        self.assertEqual((place.pack_folder(self.pack, shim) / "line/added.yaml").read_bytes(), b"added")

    def test_same_root_same_place_and_other_root_other_place(self):
        first = place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual(place.workflow_source(self.pack, self.root / "workflows" / "..", self.cache), first)
        other = self.tmp / "other"
        write(other / "workflows/x.yaml", b"x")
        self.assertNotEqual(place.workflow_source(self.pack, other, self.cache), first)

    def test_foreign_entry_is_not_used(self):
        link = place.pack_folder(self.pack, place.workflow_source(self.pack, self.root, self.cache))
        link.unlink()
        write(link / "x.yaml", b"foreign")
        with self.assertRaisesRegex(RuntimeError, str(link)):
            place.workflow_source(self.pack, self.root, self.cache)

    def test_place_of_the_flat_shape_stops_with_the_way_back(self):
        """前の形は .archon/workflows が直に workflows/ を指す symlink。そのまま使うと pack の symlink をリポジトリの中に作る"""
        folder = place.workflow_source(self.pack, self.root, self.cache) / place.WORKFLOW_FOLDER
        shutil.rmtree(folder)
        folder.symlink_to((self.root / "workflows").resolve(), target_is_directory=True)
        before = files(self.root)
        with self.assertRaisesRegex(RuntimeError, f'前の形.*rm "{folder}"') as caught:
            place.workflow_source(self.pack, self.root, self.cache)
        self.assertNotIn("\n", str(caught.exception))
        self.assertEqual(files(self.root), before)
        self.assertEqual(sorted(p.name for p in (self.root / "workflows").iterdir()), [".shared", "line"])

    def test_symlink_refusal_names_the_place(self):
        with mock.patch.object(pathlib.Path, "symlink_to", side_effect=OSError(1, "Operation not permitted")):
            with self.assertRaisesRegex(RuntimeError, r"workflow-source.*Operation not permitted"):
                place.workflow_source(self.pack, self.root, self.cache)

    def test_repo_and_archon_home_are_untouched(self):
        home = self.tmp / "archon-home"
        write(home / "workflows/archon-foo.yaml", b"foo")
        before = files(self.root), files(home)
        place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual((files(self.root), files(home)), before)


class CacheDirTest(unittest.TestCase):
    def test_xdg_cache_home_wins_over_home(self):
        self.assertEqual(place.cache_dir({"XDG_CACHE_HOME": "/xdg", "HOME": "/h"}), pathlib.Path("/xdg/works-factory"))

    def test_home_cache_when_xdg_is_unset_or_empty(self):
        for env in ({"HOME": "/h"}, {"XDG_CACHE_HOME": "", "HOME": "/h"}):
            with self.subTest(env=env):
                self.assertEqual(place.cache_dir(env), pathlib.Path("/h/.cache/works-factory"))


class RunConfigTest(unittest.TestCase):
    """新しい run に --config で渡す層は、run のノードへの環境変数・群の表の既定・使用枠の方針を持ち、中身が同じなら同じファイル。
    壊れた中身は書き直す"""

    ENV = {"WORKS_FACTORY_ROOT": "/factory", "WORKS_ANSWER_CMD": "respond"}

    def test_layer_holds_env_groups_and_quota_policy_and_heals(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = pathlib.Path(tmp)
            path = place.run_config(cache, self.ENV)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"env": self.ENV, "workflows": {"autoResumeOnQuotaReset": False}, "aliases": place.group_presets()})
            self.assertEqual(list(place.group_presets()), list(launchgroups.GROUPS))
            for name, preset in place.group_presets().items():
                self.assertEqual((preset["model"], preset["effort"]), launchgroups.default_of(name))
            written = path.read_bytes()
            path.write_text('{"aliases": {}}\n', encoding="utf-8")
            self.assertEqual(place.run_config(cache, self.ENV), path)
            self.assertEqual(path.read_bytes(), written)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), [path.name])

    def test_head_choice_up_or_down_leaves_the_groups_at_the_table_defaults(self):
        """頭の深さの役の選びは記録だけ（持ち主の決め head-choice-record-only）。上げる向きの控えも下げる向きの控えも、起動の層の
        群の値を替えない。子の run と次の周はこの層を受け継ぐので、そちらも替わらない"""
        rows = ({"group": "@wf-fix-writers", "model": "opus", "effort": "max", "why": "上げ"},
                {"group": "@wf-fix-writers", "model": "haiku", "effort": "low", "why": "下げ"})
        with tempfile.TemporaryDirectory() as tmp:
            cache = pathlib.Path(tmp)
            plain = place.run_config(cache, self.ENV).read_bytes()
            for row, way in zip(rows, (launchgroups.UP, launchgroups.DOWN)):
                with self.subTest(way):
                    chosen = launchgroups.choices([row])
                    self.assertEqual(chosen[0]["direction"], way)
                    headdepth.write(cache / "judge", headdepth.record("標準", "x", groups=chosen))
                    self.assertEqual(place.run_config(cache, self.ENV).read_bytes(), plain)

    def test_users_layer_is_kept_factory_env_and_groups_win_and_users_quota_policy_wins(self):
        """利用者の --config の層はそのまま渡り、同じ名の env と群の別名だけ工場の値に替わる。使用枠の方針は利用者の値が勝つ。
        env の値も入りうるので持ち主だけが読める"""
        group = next(iter(launchgroups.GROUPS))
        mine = {"env": {"A": "1", "WORKS_FACTORY_ROOT": "/mine"}, "assistant": "claude",
                "workflows": {"autoResumeOnQuotaReset": True, "toolCallAttentionMs": 0},
                "aliases": {group: {"provider": "claude", "model": "haiku"}, "mine": {"provider": "claude", "model": "opus"}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = place.run_config(pathlib.Path(tmp), self.ENV, mine)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {"env": {"A": "1", **self.ENV}, "assistant": "claude",
                              "workflows": {"autoResumeOnQuotaReset": True, "toolCallAttentionMs": 0},
                              "aliases": {"mine": {"provider": "claude", "model": "opus"}, **place.group_presets()}})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_layer_without_aliases_leaves_the_users_aliases_alone(self):
        """--adopt の層は群の別名を足さない（Archon が記録した AI の設定の上書きとして拒む）"""
        mine = {"aliases": {"mine": {"provider": "claude", "model": "opus"}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = place.run_config(pathlib.Path(tmp), self.ENV, mine, aliases=False)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             {**mine, "env": self.ENV, "workflows": {"autoResumeOnQuotaReset": False}})


@unittest.skipIf(shutil.which("bun") is None, "bun が無い")
class ReadRunConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / "bunfig.toml").write_text("", encoding="utf-8")

    def read(self, text: str) -> dict:
        (self.dir / "mine.yaml").write_text(text, encoding="utf-8")
        return place.read_run_config(shutil.which("bun"), self.dir, self.dir / "mine.yaml")

    def test_yaml_is_read_as_archon_reads_it(self):
        self.assertEqual(self.read("env:\n  A: '1'\naliases:\n  x: {provider: claude, model: haiku}\n"),
                         {"env": {"A": "1"}, "aliases": {"x": {"provider": "claude", "model": "haiku"}}})
        self.assertEqual(self.read(""), {})

    def test_unreadable_or_misshapen_layer_stops(self):
        for text in ("a: [", "- 1\n", "aliases: [1]\n", "env: [1]\n", "workflows: 1\n"):
            with self.subTest(text=text), self.assertRaisesRegex(RuntimeError, "--config"):
                self.read(text)
        with self.assertRaisesRegex(RuntimeError, "読めない"):
            place.read_run_config(shutil.which("bun"), self.dir, self.dir / "none.yaml")


class WorkflowRunTest(unittest.TestCase):
    def test_source_flags_come_before_caller_arguments(self):
        source, shim, config, cwd = pathlib.Path("/src"), pathlib.Path("/shim"), pathlib.Path("/run.json"), pathlib.Path("/target")
        self.assertEqual(
            place.workflow_run(source, shim, config, cwd, "works-factory-line", "--", "--workflow-source", "x"),
            [
                "bun", str(source / place.ENTRY),
                "workflow", "run", "--cwd", str(cwd), "--workflow-source", str(shim), "--config", str(config),
                "works-factory-line", "--", "--workflow-source", "x",
            ],
        )
        self.assertNotIn("--config", place.workflow_run(source, shim, None, cwd, "works-factory-line"))


if __name__ == "__main__":
    unittest.main()
