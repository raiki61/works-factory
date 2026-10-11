"""版の取り寄せと置かずに起こす形（bin/_lib/pack.py・place.py）の試験。網には出ない（偽の fetch・install を渡す）。"""
import copy
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from bin._lib import pack, place

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

    def write_pack(self, change):
        data = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))
        change(data)
        (self.tmp / "pack.json").write_text(json.dumps(data), encoding="utf-8")

    def test_archon_version_is_written_once(self):
        text = (ROOT / "pack.json").read_text(encoding="utf-8")
        commit = pack.load(ROOT)["archon"]["commit"]
        self.assertEqual(text.count(commit), 1)
        self.assertNotIn("commit", pack.load(ROOT)["asf"])

    def test_load_rejects_missing_keys(self):
        self.write_pack(lambda data: data["archon"].pop("commit"))
        with self.assertRaisesRegex(ValueError, r"archon\.commit"):
            pack.load(self.tmp)

    def test_load_rejects_commit_that_is_not_a_full_sha(self):
        for value in ("factory/sdlc-on-dev", "d97d00ef", "D97D00EF15CCE4B15D39E42635E4E86996EC1351", 1, None):
            with self.subTest(value=value):
                self.write_pack(lambda data: data["archon"].update(commit=value))
                with self.assertRaisesRegex(ValueError, r"archon\.commit"):
                    pack.load(self.tmp)


class ArchonSourceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.pack = pack.load(ROOT)
        self.cache = self.tmp / "cache"
        self.installed = []

    def fake_fetch(self, files_by_path):
        def fetch(repo, commit, dest):
            for rel, data in files_by_path.items():
                write(dest / rel, data)
        return fetch

    def complete(self, extra=None):
        return self.fake_fetch({place.ENTRY: b"cli", ASF_YAML: b"a", **(extra or {})})

    def install(self, source):
        self.installed.append(source.name)
        write(source / "node_modules/.installed", b"")

    def source(self, pack_=None, fetch=None):
        return place.archon_source(pack_ or self.pack, self.cache, fetch or self.complete(), self.install)

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

    def test_refetches_when_repo_changes(self):
        self.source(fetch=self.complete({"old": b"old"}))
        forked = copy.deepcopy(self.pack)
        forked["archon"]["repo"] = "someone/fork"
        source = self.source(forked, self.complete({"new": b"new"}))
        self.assertTrue((source / "new").is_file())
        self.assertFalse((source / "old").exists())

    def test_refetches_when_record_missing_or_broken(self):
        record = self.cache / "archon" / f"{self.pack['archon']['commit']}.json"
        damages = {"missing": record.unlink, "broken": lambda: record.write_text("{", encoding="utf-8")}
        for name, damage in damages.items():
            with self.subTest(record=name):
                self.source(fetch=self.complete({"old": b"old"}))
                damage()
                source = self.source(fetch=self.complete({"new": b"new"}))
                self.assertTrue((source / "new").is_file())
                self.assertFalse((source / "old").exists())

    def test_record_write_failure_does_not_vouch_for_new_tree(self):
        self.source(fetch=self.complete({"old": b"old"}))
        forked = copy.deepcopy(self.pack)
        forked["archon"]["repo"] = "someone/fork"
        with mock.patch.object(pathlib.Path, "write_text", side_effect=OSError("disk full")), \
                self.assertRaisesRegex(OSError, "disk full"):
            self.source(forked, self.complete({"forked": b"forked"}))
        source = self.source(fetch=self.complete({"again": b"again"}))
        self.assertTrue((source / "again").is_file())

    def test_incomplete_source_is_refused(self):
        for missing in (place.ENTRY, ASF_YAML):
            with self.subTest(missing=missing):
                partial = {place.ENTRY: b"cli", ASF_YAML: b"a"}
                del partial[missing]
                with self.assertRaisesRegex(RuntimeError, missing.rsplit("/", 1)[0]):
                    self.source(fetch=self.fake_fetch(partial))
                self.assertFalse((self.cache / "archon" / self.pack["archon"]["commit"]).exists())

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
        for name, fetch, install in (("fetch", broken_fetch, self.install), ("install", self.complete(), broken_install)):
            with self.subTest(step=name):
                with self.assertRaisesRegex(RuntimeError, "0{40}") as caught:
                    place.archon_source(newer, self.cache, fetch, install)
                self.assertNotIn("\n", str(caught.exception))
                self.assertEqual(files(self.cache / "archon" / commit), before)
                self.assertEqual(sorted(p.name for p in (self.cache / "archon").iterdir()), [commit, f"{commit}.json"])


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

    def test_archon_reads_the_repo_workflows_through_it(self):
        shim = place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual(files(shim / place.WORKFLOW_FOLDER), files(self.root / "workflows"))

    def test_edits_in_the_repo_show_without_placing_again(self):
        shim = place.workflow_source(self.pack, self.root, self.cache)
        write(self.root / "workflows/line/added.yaml", b"added")
        self.assertEqual((shim / place.WORKFLOW_FOLDER / "line/added.yaml").read_bytes(), b"added")

    def test_same_root_same_place_and_other_root_other_place(self):
        first = place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual(place.workflow_source(self.pack, self.root / "workflows" / "..", self.cache), first)
        other = self.tmp / "other"
        write(other / "workflows/x.yaml", b"x")
        self.assertNotEqual(place.workflow_source(self.pack, other, self.cache), first)

    def test_foreign_entry_is_not_used(self):
        shim = place.workflow_source(self.pack, self.root, self.cache)
        link = shim / place.WORKFLOW_FOLDER
        link.unlink()
        write(link / "x.yaml", b"foreign")
        with self.assertRaisesRegex(RuntimeError, str(link)):
            place.workflow_source(self.pack, self.root, self.cache)

    def test_repo_and_archon_home_are_untouched(self):
        home = self.tmp / "archon-home"
        write(home / "workflows/archon-foo.yaml", b"foo")
        before = files(self.root), files(home)
        place.workflow_source(self.pack, self.root, self.cache)
        self.assertEqual((files(self.root), files(home)), before)


class WorkflowRunTest(unittest.TestCase):
    def test_source_flags_come_before_caller_arguments(self):
        source, shim, cwd = pathlib.Path("/src"), pathlib.Path("/shim"), pathlib.Path("/target")
        self.assertEqual(
            place.workflow_run(source, shim, cwd, "works-factory-line", "--", "--workflow-source", "x"),
            [
                "bun", str(source / place.ENTRY),
                "workflow", "run", "--cwd", str(cwd), "--workflow-source", str(shim),
                "works-factory-line", "--", "--workflow-source", "x",
            ],
        )


if __name__ == "__main__":
    unittest.main()
