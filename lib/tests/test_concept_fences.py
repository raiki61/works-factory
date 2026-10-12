"""考えの住処の柵の道具 lib/conceptfence.py の試験（仮の置き場で数え方・歯止め・地図の読みを見る Synthetic、表 docs/concepts.json の
住処ありの柵が本当に当たることと entry-kind が既知の漏れを持たないことを見る FenceCase、main の表を引く main_table と分かれ目の fork_ref の MainTableCase）。

works-factory 自身の地図と表の全部を本物の木に当てる試験は tests/layers/test_concept_fences.py。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import git  # noqa: E402

PATH_HEADS = (".shared/", "blk-", "darkfactory/", "dev/", "tests/", "skills/")   # works の地図の行のパスの頭（works の並べ方）


def cf():
    import conceptfence   # 柵の中身（遅らせて読む。無ければその試験だけが落ちる）
    return conceptfence


class Synthetic(unittest.TestCase):
    """仮の置き場で柵そのものを見る（git を使わず、scan にパスの一覧を渡す）"""

    FENCE = {"what": "語", "pattern": r"\bWORD\b", "allowed": ["home.py"], "known": {}}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.put("a.py", "x = 'WORD'\ny = 1\nz = WORD\nWORDS = 2\n")
        self.put("home.py", "WORD = 1\n")
        self.put("tests/t.py", "WORD\n")

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_counts_only_outside_allowed_and_exclude(self):
        self.assertEqual(cf().scan(self.root, ["a.py", "home.py", "tests/t.py"], self.FENCE, ["tests/**"]), {"a.py": 2})

    def test_star_crosses_slash(self):
        self.put("blk-x/deep/b.py", "WORD\n")
        fence = dict(self.FENCE, allowed=["blk-*/b.py"])
        self.assertEqual(cf().scan(self.root, ["blk-x/deep/b.py"], fence, []), {})

    def test_skips_binary_and_missing(self):
        (self.root / "bin.dat").write_bytes(b"\xff\xfeWORD\x00")
        self.assertEqual(cf().scan(self.root, ["bin.dat", "gone.py"], self.FENCE, []), {})

    BOUND = {"what": "語", "pattern": r"\bmodel\b", "allowed": [], "known": {},
             "bound": [{"paths": ["blk-*/*.yaml"], "lines": r"^\s*model:", "by": "tests/test_b.py", "why": "試験が源と縛る"}]}

    def test_bound_copy_lines_are_not_counted(self):
        """結んだ写し: bound の paths のファイルで lines に当たる行は数えない（源に試験で縛られた写し）。ほかの行・ほかのファイルは数える"""
        self.put("blk-a/a.yaml", "  model: opus\n# model の説明\nmodel: sonnet\n")
        self.put("lib/b.py", "model: x\n")
        got = cf().scan(self.root, ["blk-a/a.yaml", "lib/b.py"], self.BOUND, [])
        self.assertEqual(got, {"blk-a/a.yaml": 1, "lib/b.py": 1})
        self.assertEqual(cf().count_lines("  model: opus\nmodel x\n", self.BOUND, "blk-z/z.yaml"), 1)
        self.assertEqual(cf().count_lines("  model: opus\n", self.BOUND, "other/z.yaml"), 1)
        self.assertEqual(cf().count_lines("  model: opus\n", self.FENCE | {"pattern": r"\bmodel\b"}, "blk-z/z.yaml"), 1)

    def test_check_table_refuses_broken_bound(self):
        """表の読み（tables が対象の表に当てる確かめ）は、bound が配列でない・paths が配列でない・lines が正規表現でない・
        by が無い表を拒む（ValueError か re.error）"""
        import re
        cf().check_table({"concepts": {"a": {"fences": [self.BOUND]}}})
        for bad in ("x", ["x"], [{"paths": "x", "lines": "a", "by": "t"}], [{"paths": ["x"], "lines": "(", "by": "t"}],
                    [{"paths": ["x"], "lines": "a"}]):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, re.error)):
                    cf().check_table({"concepts": {"a": {"fences": [dict(self.BOUND, bound=bad)]}}})

    def test_ratchet(self):
        m = cf()
        self.assertEqual(m.verdict({"a.py": 2}, {"a.py": [2, "理由"]}), [])
        self.assertTrue(m.verdict({"a.py": 1}, {"a.py": [2, "理由"]}))              # 減ったのに表が残る
        self.assertTrue(m.verdict({"a.py": 3}, {"a.py": [2, "理由"]}))              # 増えた
        self.assertTrue(m.verdict({"a.py": 2, "b.py": 1}, {"a.py": [2, "理由"]}))   # 表に無い漏れ

    @staticmethod
    def table(**concepts):
        return {"concepts": {k: {"status": "散らばり", "fences": [{"what": "語", "pattern": "x", "allowed": [], "known": kn}]}
                             for k, kn in concepts.items()}}

    def test_growth_same_or_less_is_quiet(self):
        main = self.table(a={"x.py": [2, "理由"], "y.py": [1, "理由"]})
        self.assertEqual(cf().growth(main, main), [])
        self.assertEqual(cf().growth(main, self.table(a={"x.py": [2, "理由"]})), [])          # 減った
        self.assertEqual(cf().growth(main, self.table(a={"x.py": [1, "理由"], "y.py": [2, "理由"]})), [])  # 和が同じ

    def test_growth_more_lines_or_new_path_is_red(self):
        main = self.table(a={"x.py": [2, "理由"]})
        self.assertTrue(cf().growth(main, self.table(a={"x.py": [3, "理由"]})))               # 和が増えた
        self.assertTrue(cf().growth(main, self.table(a={"x.py": [1, "理由"], "z.py": [1, "理由"]})))  # main に無いパス

    def test_growth_skips_concepts_without_main_fence(self):
        main = {"concepts": {"a": {"status": "散らばり", "fences": []}}}
        now = self.table(a={"x.py": [5, "理由"]}, b={"y.py": [1, "理由"]})
        self.assertEqual(cf().growth(main, now), [])   # 初めて柵を掛ける差分（main は柵が空・考えが無い）は比べない

    def test_map_ids_take_first_status_word(self):
        md = ("### `a` 一つ\n\n- 状態: 住処あり（写し）\n- 住処: x\n\n"
              "### `b` 二つ\n- 住処: y\n- 状態: 散らばり（部分の住処あり）\n- 状態: 住処あり\n")
        self.assertEqual(cf().map_ids(md), {"a": "住処あり", "b": "散らばり"})

    def test_map_rows_take_first_labeled_line(self):
        md = "### `a` 一つ\n- 住処: `x.py`\n- 住処: `y.py`\n### `b` 二つ\n- 状態: 散らばり\n"
        self.assertEqual(cf().map_rows(md, "住処"), {"a": "`x.py`"})

    def test_map_paths_skip_planned_and_branch_lines(self):
        md = ("- 住処: `.shared/core/x.py` と `blk-a/` と `dev/*.sh`、`OUTCOMES`、`docs/y.md`\n"
              "- 予定の住処: `blk-entry`（予定）\n"
              "- 計画: `docs/p.md`（枝 `wip/x`）と `darkfactory/schemas/in.json`\n"
              "- 繰り返し: `.shared/core/x.py`\n")
        self.assertEqual(cf().map_paths(md, PATH_HEADS), [".shared/core/x.py", "blk-a", "dev/*.sh"])



class FenceCase(unittest.TestCase):
    # 住処ありの柵ごとに、柵が当たるはずの 1 行（表の fences の順）。表の柵が正規表現の書き損じで何にも当たらなくなると、
    # 本物の木の FencesHold は「漏れが無い」と見分けがつかず緑のまま。柵を足したらここにも 1 行足す（足さなければ赤）
    HITS = {
        "entry-kind": ['b = _word(raw, "base")', 'if base["from"] == "pr":'],
        "web-get": ["from urllib.request import urlopen"],
        "cite": ["from cite import quoted_in", "ok = cite.fold(a) in cite.fold(b)"],
        "prompt-sections": ["class Section:"],
    }

    def test_every_home_fence_hits_its_line(self):
        table = cf().load(LIB.parent)
        homes = {k: v["fences"] for k, v in table["concepts"].items() if v["status"] == "住処あり"}
        self.assertEqual(set(self.HITS), set(homes))
        for k, fences in homes.items():
            self.assertEqual(len(self.HITS[k]), len(fences), k)
            for line, fence in zip(self.HITS[k], fences):
                with self.subTest(concept=k, what=fence["what"]):
                    self.assertEqual(cf().count_lines(line, fence, "lib/x.py"), 1)

    def test_entry_kind_read_only_by_entryshape(self):
        """L-E55: 入口の種類（依頼・base・PR）を知るのは入口の変換（lib/entryshape.py とメイングラフの start）だけ（元 works/tests/
        test_entry_block.py の ConversionLayerCase.test_only_conversion_layer_knows_entry_kind）。既知の漏れは 0 件（本物の木の
        当たりが既知と揃うことは tests/layers/test_concept_fences.py の FencesHold が照らす）。
        柵の正本は表 docs/concepts.json の entry-kind（2 つ目の「base.from での分岐」の形は、比べる相手を入口の種の語
        （head・base・pr）に限る: 元の形は判定の受け付けの写しの道の指し先 lib/judge_accept.py の w["from"] != "$" にも当たる）"""
        table = cf().load(LIB.parent)
        concept = table["concepts"]["entry-kind"]
        self.assertEqual(concept["status"], "住処あり")
        fences = concept["fences"]
        self.assertEqual([f["known"] for f in fences], [{}, {}])
        self.assertEqual([cf().count_lines('w = step["from"] != "$"', fence, "lib/x.py") for fence in fences], [0, 0])


class MainTableCase(unittest.TestCase):
    """main_table: 版は在って表のファイルが無ければ空の表（表を置く最初の差分は比べない）。版を引けない時の (None, 理由) は
    tests/layers/test_concept_fences.py の NotAboveMain が見る"""

    def test_missing_table_is_empty_and_present_table_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git(root, "init", "-q")
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "no table")
            self.assertEqual(cf().main_table(root, "HEAD"), ({"concepts": {}}, None))
            table = {"concepts": {"a": {"status": "散らばり", "fences": []}}}
            (root / "docs").mkdir()
            (root / "docs" / "concepts.json").write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "table")
            self.assertEqual(cf().main_table(root, "HEAD"), (table, None))

    def test_fork_ref_is_none_without_fork_point(self):
        """分かれ目を引けなければ None（ref の頭に比べ直さない。比べ直すと別の版か空の表と比べて黙って通る）"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git(root, "init", "-q", "-b", "main")
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "a")
            self.assertIsNone(cf().fork_ref(root))            # origin/main が無い
            git(root, "checkout", "-q", "--orphan", "other")
            git(root, "commit", "-q", "-m", "b")
            self.assertIsNone(cf().fork_ref(root, "main"))    # 共通の祖先が無い


if __name__ == "__main__":
    unittest.main()
