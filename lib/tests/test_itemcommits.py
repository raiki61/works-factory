"""修正案の項目ごとの commit の決め（lib/itemcommits.py）の純粋な口の検査。

縛る事:
- record: 承認済みの項目の depends_on を前の項目の番号 after に戻し、修正役の返答の changes[].files と TDD の輪の test_files を単位ごとの
  claims にする（files は根からの相対）
- merged: 項目は後の段の物、claims と unread は和
- split: 差分のパスを項目ごとに分け、依存の位相順に並べる。どの項目も申告していないパス・複数の項目が触ったパス・記録の無い run・
  読めない記録・依存の循環は分けずに訳を返す
"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import itemcommits  # noqa: E402

ITEMS = [{"item": 1, "unit_keys": ["A"], "approach": "読み口を足す", "depends_on": []},
         {"item": 2, "unit_keys": ["B"], "approach": "読み口を使う", "depends_on": [{"unit": "A", "receives": ["lib/rows.py::read_rows"]}]}]


def claims(*rows):
    return [{"unit_key": k, "files": list(f)} for k, f in rows]


class Record(unittest.TestCase):
    def test_depends_become_earlier_items_and_files_become_claims(self):
        replies = [{"changes": [{"unit_key": "A", "files": ["/repo/lib/rows.py", "lib/./x.py"]}]}, None,
                   {"changes": [{"unit_key": "B", "files": ["lib/use.py"]}]}]
        got = itemcommits.record(ITEMS, replies, [{"unit_key": "A", "test_files": ["lib/tests/test_rows.py"]}], "/repo", ["訳"])
        self.assertEqual(got["items"], [{"item": 1, "unit_keys": ["A"], "approach": "読み口を足す", "after": []},
                                        {"item": 2, "unit_keys": ["B"], "approach": "読み口を使う", "after": [1]}])
        self.assertEqual(got["claims"], claims(("A", ["lib/rows.py", "lib/x.py"]), ("B", ["lib/use.py"]),
                                               ("A", ["lib/tests/test_rows.py"])))
        self.assertEqual(got["unread"], ["訳"])

    def test_run_without_a_plan_has_no_items(self):
        self.assertIsNone(itemcommits.record(None, [], [], "/repo")["items"])


class Merged(unittest.TestCase):
    def test_later_stage_items_and_all_claims(self):
        first = {"items": [{"item": 1, "unit_keys": ["A"], "approach": "前", "after": []}], "claims": claims(("A", ["a"])), "unread": []}
        second = {"items": [{"item": 1, "unit_keys": ["A"], "approach": "直した", "after": []}], "claims": claims(("A", ["b"])),
                  "unread": ["読めない"]}
        got = itemcommits.merged([first, None, second])
        self.assertEqual(got["items"][0]["approach"], "直した")
        self.assertEqual(got["claims"], claims(("A", ["a"]), ("A", ["b"])))
        self.assertEqual(got["unread"], ["読めない"])
        self.assertEqual(itemcommits.merged([first, {"items": None, "claims": [], "unread": []}])["items"], first["items"])
        self.assertIsNone(itemcommits.merged([None, None]))


class Split(unittest.TestCase):
    def record(self, *rows):
        items = [{"item": 1, "unit_keys": ["A"], "approach": "使う", "after": [2]},
                 {"item": 2, "unit_keys": ["B"], "approach": "足す", "after": []},
                 {"item": 3, "unit_keys": ["C"], "approach": "直さなかった", "after": []}]
        return {"items": items, "claims": claims(*rows), "unread": []}

    def test_two_items_are_two_parts_in_dependency_order(self):
        parts, why = itemcommits.split(self.record(("A", ["use.py"]), ("B", ["rows.py", "test_rows.py"])),
                                       ["rows.py", "test_rows.py", "use.py"])
        self.assertEqual(why, "")
        self.assertEqual(parts, [itemcommits.Part(2, "足す", [], ["rows.py", "test_rows.py"]), itemcommits.Part(1, "使う", [2], ["use.py"])])

    def test_paths_owned_by_no_single_item_are_not_split(self):
        for rows, paths, words in (((("A", ["a.py"]), ("B", ["a.py"])), ["a.py"], "複数の項目か項目の外の単位が触った: a.py"),
                                   ((("A", ["a.py"]),), ["a.py", "b.py"], "どの項目も申告していない: b.py"),
                                   ((("A", ["a.py"]), ("Z", ["b.py"])), ["a.py", "b.py"], "複数の項目か項目の外の単位が触った: b.py")):
            with self.subTest(words=words):
                self.assertEqual(itemcommits.split(self.record(*rows), paths), ([], f"差分のパスを 1 つの項目に決められない（{words}）"))

    def test_missing_or_unread_record_is_not_split(self):
        for record, words in ((None, "修正案の項目の記録が無い"), ({"items": None, "claims": [], "unread": []}, "修正案の項目の記録が無い"),
                              ({**self.record(), "unread": ["組 g1 の返答を読めない"]}, "組 g1 の返答を読めない")):
            with self.subTest(words=words):
                parts, why = itemcommits.split(record, ["a.py"])
                self.assertEqual(parts, [])
                self.assertIn(words, why)

    def test_cyclic_dependencies_are_not_split(self):
        record = self.record(("A", ["use.py"]), ("B", ["rows.py"]))
        record["items"][1]["after"] = [1]
        self.assertEqual(itemcommits.split(record, ["rows.py", "use.py"]), ([], "修正案の項目の依存が循環している"))

    def test_many_unclaimed_paths_are_counted(self):
        _, why = itemcommits.split(self.record(), [f"p{i}" for i in range(7)])
        self.assertIn("p4 ほか 2 件", why)


class DeclaredFiles(unittest.TestCase):
    """返答の files をリポジトリの根からの相対に揃える 1 か所（前は factchecks。元 test_fix_seams の test_declared_files。integration.md 4.3-2）"""

    def test_declared_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            repo = tmp / "repo"
            (repo / "docs").mkdir(parents=True)
            (repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
            rows = [{"files": [str(repo / "a" / ".." / "stats.py"), " docs/x.md ", "", 3]}]
            self.assertEqual(itemcommits.declared_files(rows, repo), {"stats.py", "docs/x.md"})
            linked = tmp / "linked"
            linked.symlink_to(repo)
            (repo / "alias.py").symlink_to(repo / "stats.py")
            rows = [{"files": [str(linked / "stats.py"), str(repo / "alias.py")]}]
            self.assertEqual(itemcommits.declared_files(rows, repo), {"stats.py", "alias.py"}, "根のリンクは解き、ファイルのリンクは解かない")


if __name__ == "__main__":
    unittest.main()
