"""固定材料の写しと取り込み（workflows/line/src/fixture.py。元 lib/fixture.py とその試験 lib/tests/test_fixture.py の写し。docs/design/line.md の 1.5 の MOVE。その元 works/.shared/core/fixture.py）の検査。

写した run と取り込む run は、同じ木の別の作業ツリー（取り込む側は起動が切った包みの commit を 1 つ積んだ形）と別の置き場で照らす。
"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

fixture = kit.load("line", "fixture")
startrec = fixture.startrec

OLD, NEW = "run-aaa", "run-bbb"
INPUTS = {"request": "req.json", "test_cmd": "make test", "fix_fixture": "", "features_off": "", "features_on": ""}


def ptr(run_id: str, path: str) -> dict:
    """運ぶ値の中のポインタの形（run の id と置き場からのパス）"""
    return {"run_id": run_id, "path": path}


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "seed")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.request = self.tmp / "req.json"
        self.request.write_text('[{"where": "a.txt", "text": "直す"}]\n', encoding="utf-8")
        self.place = self.tmp / "art-1"
        self.carried = {"judge": {"judgment": ptr(OLD, "judge/judgment.json")}, "deferred": []}
        startrec.write(self.place, {"run_id": OLD, "inputs": INPUTS, "request_file": str(self.request), "base_rev": self.head,
                                    "policy": {"copy": str(self.place / "policy" / "copy.md")}})
        (self.place / "judge").mkdir()
        (self.place / "judge" / "judgment.json").write_text(
            json.dumps({"self": ptr(OLD, "judge/judgment.json"), "repo": str(self.repo / "a.txt"), "head": self.head}),
            encoding="utf-8")
        (self.place / "judge" / "blob.bin").write_bytes(b"\xff\xfe")

    def captured(self) -> pathlib.Path:
        self.assertIsNotNone(fixture.capture(self.place, self.repo, run_id=OLD, carried=self.carried))
        return self.place / fixture.DIR

    def wrapped(self) -> pathlib.Path:
        """同じ木の別の作業ツリーに、起動が切ったような包みの commit を 1 つ積む（木は同じ・HEAD は違う）"""
        other = self.tmp / "repo-2"
        git(self.repo, "worktree", "add", "-q", "--detach", str(other), "HEAD")
        git(other, "commit", "-q", "--allow-empty", "-m", "wrap")
        return other

    def adopt(self, src, repo, place=None, **kw):
        args = {"run_id": NEW, "inputs": {**INPUTS, "fix_fixture": str(src)}, "request_text": self.request.read_text(encoding="utf-8")}
        return fixture.adopt(place or self.tmp / "art-2", src, repo, **{**args, **kw})


class CaptureCase(Fixture):
    def test_capture_writes_the_copy_and_the_manifest_once(self):
        man = fixture.capture(self.place, self.repo, run_id=OLD, carried=self.carried)
        dest = self.place / fixture.DIR
        self.assertEqual((man["format"], man["source_run"], man["head"], man["carried"]), (fixture.FORMAT, OLD, self.head, self.carried))
        self.assertIn(f"{fixture.COPY}/{startrec.REL}", man["files"])
        self.assertFalse((dest / fixture.COPY / fixture.DIR).exists(), "写しは自分のフォルダを含まない")
        before = (dest / fixture.MANIFEST).read_bytes()
        self.assertEqual(fixture.capture(self.place, self.repo, run_id="other", carried={}), man, "2 度目は書き直さずに返す")
        self.assertEqual((dest / fixture.MANIFEST).read_bytes(), before)

    def test_noted_capture_records_the_folder_or_why_not(self):
        fixture.noted_capture(self.place, self.repo, run_id=OLD, carried=self.carried)
        self.assertEqual(startrec.read(self.place)[fixture.CAPTURED_KEY], {"dir": str(self.place / fixture.DIR), "error": ""})
        self.assertIn(f"固定材料: {self.place / fixture.DIR}", fixture.lines(startrec.read(self.place))[0])
        shutil.rmtree(self.place / fixture.DIR)
        fixture.noted_capture(self.place, self.tmp / "not-a-repo", run_id=OLD, carried=self.carried)
        note = startrec.read(self.place)[fixture.CAPTURED_KEY]
        self.assertEqual(note["dir"], "")
        self.assertIn("git", note["error"])
        self.assertTrue(fixture.lines(startrec.read(self.place))[0].startswith("固定材料を写せなかった: "))

    def test_noted_capture_does_not_overwrite_a_broken_start_record(self):
        """読めない始めの記録は captured だけの記録で上書きせず、ファイルの名を言って止まる（fail closed）"""
        broken = startrec.path(self.place)
        broken.write_text("{壊れた", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, str(broken)):
            fixture.noted_capture(self.place, self.repo, run_id=OLD, carried=self.carried)
        self.assertEqual(broken.read_text(encoding="utf-8"), "{壊れた")


class AdoptCase(Fixture):
    def test_adopt_rewrites_paths_run_and_head(self):
        src, other = self.captured(), self.wrapped()
        new_head = git(other, "rev-parse", "HEAD")
        place = self.tmp / "art-2"
        doc, carried = self.adopt(src, other, place)
        self.assertEqual((doc["run_id"], doc["base_rev"], doc["inputs"]["fix_fixture"]), (NEW, new_head, str(src)))
        self.assertEqual(doc["policy"]["copy"], str(place / "policy" / "copy.md"))
        self.assertEqual(doc[fixture.KEY]["source_run"], OLD)
        self.assertNotIn(fixture.KEY, startrec.read(place), "始めの記録を書くのは呼び手")
        judgment = json.loads((place / "judge" / "judgment.json").read_text(encoding="utf-8"))
        self.assertEqual(judgment, {"self": ptr(NEW, "judge/judgment.json"), "repo": str(other / "a.txt"), "head": new_head})
        self.assertEqual((place / "judge" / "blob.bin").read_bytes(), b"\xff\xfe", "UTF-8 で読めないファイルはそのまま")
        self.assertEqual(carried["judge"]["judgment"], ptr(NEW, "judge/judgment.json"))
        self.assertEqual(json.loads((place / fixture.CARRIED).read_text(encoding="utf-8")), carried)
        self.assertEqual(fixture.lines({fixture.KEY: doc[fixture.KEY]})[0][:len("固定材料から: run run-aaa")], "固定材料から: run run-aaa")

    def test_missing_commit_is_remade_from_its_tree(self):
        tree = git(self.repo, "rev-parse", "HEAD^{tree}")
        dangling = git(self.repo, "commit-tree", tree, "-m", "only here")
        (self.place / "judge" / "rev.txt").write_text(dangling, encoding="utf-8")
        src = self.captured()
        self.assertEqual(json.loads((src / fixture.MANIFEST).read_text(encoding="utf-8"))["commits"], {dangling: tree})
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-q", "--no-local", str(self.repo), str(clone))
        with self.assertRaises(Exception):
            git(clone, "cat-file", "-e", f"{dangling}^{{commit}}")
        place = self.tmp / "art-2"
        self.adopt(src, clone, place)
        remade = (place / "judge" / "rev.txt").read_text(encoding="utf-8")
        self.assertNotEqual(remade, dangling)
        self.assertEqual(git(clone, "rev-parse", f"{remade}^{{tree}}"), tree)

    def refused(self, words: str, src=None, repo=None, place=None, **kw):
        place = place or self.tmp / "art-2"
        before = sorted(p.relative_to(place) for p in place.rglob("*")) if place.exists() else []
        with self.assertRaises(fixture.FixtureRefused) as caught:
            self.adopt(src or self.place / fixture.DIR, repo or self.repo, place, **kw)
        self.assertIn(words, str(caught.exception))
        self.assertEqual(sorted(p.relative_to(place) for p in place.rglob("*")) if place.exists() else [], before, "拒む時は何も書かない")

    def test_refusals_name_what_differs(self):
        src = self.captured()
        self.refused("無いか読めない", src=self.tmp)
        older = self.tmp / "older"
        shutil.copytree(src, older)
        man = json.loads((older / fixture.MANIFEST).read_text(encoding="utf-8"))
        (older / fixture.MANIFEST).write_text(json.dumps({**man, "format": 0}), encoding="utf-8")
        self.refused("前の版", src=older)
        edited = self.tmp / "edited"
        shutil.copytree(src, edited)
        (edited / fixture.COPY / "judge" / "judgment.json").write_text("{}", encoding="utf-8")
        self.refused("書き換わった: place/judge/judgment.json", src=edited)
        self.refused("依頼の文の sha256", request_text="ほかの依頼")
        self.refused("test_cmd", inputs={**INPUTS, "test_cmd": "make other"})
        started = self.tmp / "art-3"
        startrec.write(started, {"run_id": NEW})
        self.refused("既に在る", place=started)
        (self.repo / "a.txt").write_text("b\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "change")
        self.refused("対象の木", src=src)

    def test_current_inputs_may_differ(self):
        """CURRENT の欄（名指しの字・機能の切り替え）は今の値にする"""
        doc, _ = self.adopt(self.captured(), self.wrapped(),
                            inputs={**INPUTS, "request": str(self.request), "features_off": "tdd_lanes", "fix_fixture": "x"})
        self.assertEqual((doc["inputs"]["request"], doc["inputs"]["features_off"]), (str(self.request), "tdd_lanes"))


if __name__ == "__main__":
    unittest.main()
