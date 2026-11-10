"""考えの住処の柵の道具 lib/conceptfence.py の試験（仮の置き場で数え方・歯止め・地図の読みを見る Synthetic、main の表を引く main_table と
分かれ目の fork_ref の MainTableCase）。

works-factory 自身の地図と表の全部を本物の木に当てる試験（tests/layers の同じ名のファイル）は #765 で、工場自身の表 docs/concepts.json の
住処ありの柵を本物の木に当てる FenceCase は 2026-11-10 の削りで消した（書き込みも承認も守らない。持ち主の決め tests-guard-writes）。
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
        lines が空の行か 1 字の行に当たる（ほぼどの行も写しになり柵が見えなくなる）・by が無い表を拒む（ValueError か re.error）"""
        import re
        cf().check_table({"concepts": {"a": {"fences": [self.BOUND]}}})
        for bad in ("x", ["x"], [{"paths": "x", "lines": "a", "by": "t"}], [{"paths": ["x"], "lines": "(", "by": "t"}],
                    [{"paths": ["x"], "lines": "a"}], [{"paths": ["x"], "lines": "", "by": "t"}],
                    [{"paths": ["x"], "lines": ".*", "by": "t"}], [{"paths": ["x"], "lines": "^", "by": "t"}]) + tuple(
                        [{"paths": ["x"], "lines": lines, "by": "t"}] for lines in (".", r"\S", r"\w", r"[\s\S]", "^.", "[^\n]")):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, re.error)):
                    cf().check_table({"concepts": {"a": {"fences": [dict(self.BOUND, bound=bad)]}}})

    def test_check_table_refuses_loosened_not_a_table(self):
        """loosened（緩めの鍵と理由）が表でない表は、growth が落ちる前に形の外れとして拒む"""
        for bad in (["pattern:a:w"], "x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    cf().check_table({"concepts": {}, "loosened": bad})

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
        self.assertEqual(cf().growth({"concepts": {}}, dict(now, exclude=["docs/**"])), [])   # main に柵が無ければ exclude も比べない

    @staticmethod
    def fenced():
        """緩めを比べる main の表: 柵を 1 つ持つ考え a と表の exclude"""
        fence = {"what": "語", "pattern": r"\bx\b", "allowed": ["home.py", "lib/h.py"], "known": {},
                 "bound": [{"paths": ["blk-*/*.yaml"], "lines": r"^\s*x:", "by": "t.py", "why": "縛る"}]}
        return {"exclude": ["docs/**", "fixtures/**"], "concepts": {"a": {"status": "住処あり", "fences": [fence]}}}

    def loosen(self, change):
        now = self.fenced()
        change(now, now["concepts"]["a"]["fences"][0])
        return now

    LOOSENINGS = {
        "concept:a": lambda t, f: t["concepts"].pop("a"),
        "fence:a:語": lambda t, f: t["concepts"]["a"]["fences"].clear(),
        "allowed:a:語:lib/y.py": lambda t, f: f["allowed"].append("lib/y.py"),
        "pattern:a:語": lambda t, f: f.update(pattern=r"\bxx\b"),
        "exclude:lib/**": lambda t, f: t["exclude"].append("lib/**"),
        "bound:a:語:lib/*.py:^y": lambda t, f: f["bound"].append({"paths": ["lib/*.py"], "lines": "^y", "by": "t.py"}),
        "bound:a:語:wf/*.yaml:^\\s*x:": lambda t, f: f["bound"][0]["paths"].append("wf/*.yaml"),
        "bound:a:語:blk-*/*.yaml:x": lambda t, f: f["bound"][0].update(lines="x"),
    }

    def test_growth_loosening_is_red(self):
        """考え・柵を消す・allowed・exclude・bound を広げる・pattern を変えるのは、main の表より緩めたので赤（鍵を名指す）"""
        for key, change in self.LOOSENINGS.items():
            with self.subTest(key=key):
                got = cf().growth(self.fenced(), self.loosen(change))
                self.assertTrue(got)
                self.assertTrue(any(f'"{key}"' in m for m in got), got)

    def test_growth_tightening_is_quiet(self):
        """減らす・並べ替える・bound の why を変えるのは緩めでない"""
        for name, change in {"allowed を減らす": lambda t, f: f["allowed"].pop(),
                             "exclude を減らす": lambda t, f: t["exclude"].pop(),
                             "bound を消す": lambda t, f: f["bound"].clear(),
                             "allowed の並べ替え": lambda t, f: f["allowed"].reverse(),
                             "bound の why": lambda t, f: f["bound"][0].update(why="別の訳")}.items():
            with self.subTest(name=name):
                self.assertEqual(cf().growth(self.fenced(), self.loosen(change)), [])

    def test_growth_loosening_passes_only_with_new_reason(self):
        """緩めは loosened の新しい理由の行で通す。理由が空・main に同じ行が在る（入った行の使い回し）なら赤"""
        key = "allowed:a:語:lib/y.py"
        now = self.loosen(self.LOOSENINGS[key])
        self.assertEqual(cf().growth(self.fenced(), dict(now, loosened={key: "住処を lib/y.py に移した"})), [])
        self.assertTrue(cf().growth(self.fenced(), dict(now, loosened={key: " "})))
        main = dict(self.fenced(), loosened={key: "住処を lib/y.py に移した"})
        self.assertTrue(cf().growth(main, dict(now, loosened={key: "住処を lib/y.py に移した"})))
        self.assertEqual(cf().growth(main, dict(now, loosened={key: "住処を lib/y.py にもう一度移した"})), [])

    def test_growth_duplicate_what_is_red(self):
        """柵は what で引くので、1 つの考えの中で what が重なれば赤（重なった片方が比べられない）"""
        now = self.fenced()
        fences = now["concepts"]["a"]["fences"]
        fences.append(dict(fences[0], allowed=["*"]))
        self.assertTrue(any("重なる" in m for m in cf().growth(self.fenced(), now)))

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



class MainTableCase(unittest.TestCase):
    """main_table: 版は在って表のファイルが無ければ空の表（表を置く最初の差分は比べない）・表が読めなければ (None, 理由)。版を引けない時の (None, 理由) を
    見た tests/layers の同じ名のファイルの NotAboveMain は #765 で消した"""

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

    def test_unreadable_table_is_none_not_empty(self):
        """表のファイルは在るのに読めなければ (None, 理由)（空の表にすると比べずに通る）"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git(root, "init", "-q")
            (root / "docs").mkdir()
            (root / "docs" / "concepts.json").write_text("{ 壊れた", encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "broken table")
            got, why = cf().main_table(root, "HEAD")
            self.assertIsNone(got)
            self.assertIn("JSON", why)

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
