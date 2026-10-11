"""版の取り寄せと Archon の家への配置（bin/_lib/pack.py・place.py）の試験。網には出ない（偽の download・fetch を渡す）。"""
import copy
import hashlib
import json
import os
import pathlib
import re
import tempfile
import unittest
from unittest import mock

from bin._lib import pack, place

ROOT = pathlib.Path(__file__).resolve().parents[2]
BINARY = b"fake archon binary"


def files(root):
    """root の下のファイルを、root からの相対パス → 中身のバイトで返す"""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class PlaceTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.pack = pack.load(ROOT)
        self.pack["archon"]["assets"] = {place.asset_name(): hashlib.sha256(BINARY).hexdigest()}
        self.cache = self.tmp / "cache"
        self.home = self.tmp / "archon-home"
        self.root = self.tmp / "repo"
        write(self.root / "workflows/line/works-factory-line.yaml", b"name: works-factory-line\r\n")
        write(self.root / "workflows/.shared/boundary.py", b"\x00\xff bytes\n")
        write(self.root / "pack.json", b"{}")

    def fake_fetch(self, files_by_path):
        def fetch(repo, commit, folder, dest):
            for rel, data in files_by_path.items():
                write(dest / rel, data)
        return fetch

    def test_load_rejects_missing_keys(self):
        data = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))
        del data["asf"]["commit"]
        (self.tmp / "pack.json").write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"asf\.commit"):
            pack.load(self.tmp)

    def write_pack(self, ours_placed_at, asf_placed_at):
        data = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))
        data["ours"]["placed_at"] = ours_placed_at
        data["asf"]["placed_at"] = asf_placed_at
        (self.tmp / "pack.json").write_text(json.dumps(data), encoding="utf-8")

    def test_load_rejects_placed_at_outside_own_folder(self):
        for value in ("workflows", "workflows/", "", "..", "/tmp/asf", "workflows/..", "workflows/asf/sub", None):
            with self.subTest(value=value):
                self.write_pack("workflows/works-factory", value)
                with self.assertRaisesRegex(ValueError, r"asf\.placed_at"):
                    pack.load(self.tmp)

    def test_load_rejects_equal_placed_at(self):
        self.write_pack("workflows/same", "workflows/same")
        with self.assertRaisesRegex(ValueError, r"ours\.placed_at と asf\.placed_at"):
            pack.load(self.tmp)

    def test_binary_sha_mismatch_names_path(self):
        def download(repo, release, dest_dir):
            path = dest_dir / place.asset_name()
            write(path, b"something else")
            return path

        with self.assertRaises(RuntimeError) as caught:
            place.archon_binary(self.pack, self.cache, download)
        expected = self.cache / "archon" / self.pack["archon"]["release"] / place.asset_name()
        self.assertIn(str(expected), str(caught.exception))

    def test_binary_cached_no_download(self):
        cached = self.cache / "archon" / self.pack["archon"]["release"] / place.asset_name()
        write(cached, BINARY)

        def download(repo, release, dest_dir):
            self.fail("キャッシュに正しい中身が在るのに download を呼んだ")

        self.assertEqual(place.archon_binary(self.pack, self.cache, download), cached)

    def test_binary_cached_sha_mismatch_keeps_file(self):
        cached = self.cache / "archon" / self.pack["archon"]["release"] / place.asset_name()
        write(cached, b"truncated")

        def download(repo, release, dest_dir):
            self.fail("キャッシュに在るのに download を呼んだ")

        with self.assertRaisesRegex(RuntimeError, re.escape(str(cached))):
            place.archon_binary(self.pack, self.cache, download)
        self.assertEqual(cached.read_bytes(), b"truncated")

    def test_binary_is_executable(self):
        def download(repo, release, dest_dir):
            path = dest_dir / place.asset_name()
            write(path, BINARY)
            path.chmod(0o644)
            return path

        self.assertTrue(os.access(place.archon_binary(self.pack, self.cache, download), os.X_OK))

    def test_asf_cached_no_fetch(self):
        first = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))

        def fetch(repo, commit, folder, dest):
            self.fail("同じ commit の ASF が在るのに fetch を呼んだ")

        self.assertEqual(place.asf_tree(self.pack, self.cache, fetch), first)
        self.assertEqual(files(first), {"archon-a.yaml": b"a"})

    def test_asf_refetches_when_folder_changes(self):
        place.asf_tree(self.pack, self.cache, self.fake_fetch({"old.yaml": b"old"}))
        moved = copy.deepcopy(self.pack)
        moved["asf"]["folder"] = ".archon/workflows/other"
        asf_dir = place.asf_tree(moved, self.cache, self.fake_fetch({"new.yaml": b"new"}))
        self.assertEqual(files(asf_dir), {"new.yaml": b"new"})

    def test_place_is_byte_identical(self):
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        self.assertEqual(files(self.home / "workflows/works-factory"), files(self.root / "workflows"))
        self.assertEqual(files(self.home / "workflows/asf"), {"archon-a.yaml": b"a"})

    def test_place_touches_only_own_folders(self):
        write(self.home / "workflows/other/x.yaml", b"other")
        write(self.home / "workflows/archon-foo.yaml", b"foo")
        write(self.home / "workflows/works-factory/stale.yaml", b"stale")
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        self.assertEqual((self.home / "workflows/other/x.yaml").read_bytes(), b"other")
        self.assertEqual((self.home / "workflows/archon-foo.yaml").read_bytes(), b"foo")
        self.assertEqual(
            sorted(p.name for p in (self.home / "workflows").iterdir()),
            ["archon-foo.yaml", "asf", "other", "works-factory"],
        )
        self.assertEqual(files(self.home / "workflows/works-factory"), files(self.root / "workflows"))

    def test_place_copy_failure_leaves_previous_placement(self):
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        before = files(self.home / "workflows")
        write(self.root / "workflows/line/added.yaml", b"added")

        def broken_copy(src, dest, **kwargs):
            write(dest / "half.yaml", b"half")
            raise OSError("disk full")

        with mock.patch.object(place.shutil, "copytree", broken_copy), self.assertRaisesRegex(OSError, "disk full"):
            place.place(self.pack, self.root, self.home, asf_dir)
        self.assertEqual(files(self.home / "workflows"), before)
        self.assertEqual(sorted(p.name for p in (self.home / "workflows").iterdir()), ["asf", "works-factory"])

    def test_fetch_failure_leaves_previous_placement(self):
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"before"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        before = files(self.home / "workflows/asf")

        newer = copy.deepcopy(self.pack)
        newer["asf"]["commit"] = "0" * 40

        def fetch(repo, commit, folder, dest):
            write(dest / "half.yaml", b"half")
            raise OSError("network is unreachable")

        with self.assertRaisesRegex(RuntimeError, "0{40}") as caught:
            place.asf_tree(newer, self.cache, fetch)
        self.assertNotIn("\n", str(caught.exception))
        self.assertEqual(files(self.home / "workflows/asf"), before)
        commit = self.pack["asf"]["commit"]
        self.assertEqual(sorted(p.name for p in (self.cache / "asf").iterdir()), [commit, f"{commit}.json"])

    def test_repo_never_gets_asf_files(self):
        before = files(self.root)
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        self.assertEqual(files(self.root), before)


if __name__ == "__main__":
    unittest.main()
