"""版の取り寄せと Archon の家への配置（bin/_lib/pack.py・place.py）の試験。網には出ない（偽の download・fetch を渡す）。"""
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

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
        self.assertEqual(sorted(p.name for p in (self.cache / "asf").iterdir()), [self.pack["asf"]["commit"]])

    def test_repo_never_gets_asf_files(self):
        before = files(self.root)
        asf_dir = place.asf_tree(self.pack, self.cache, self.fake_fetch({"archon-a.yaml": b"a"}))
        place.place(self.pack, self.root, self.home, asf_dir)
        self.assertEqual(files(self.root), before)


if __name__ == "__main__":
    unittest.main()
