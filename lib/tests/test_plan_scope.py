"""承認済みの修正案の項目と修正の差分の照らし（blk-fix の planscope。依頼 218）。純粋な関数 problems・new_test_ids・
added_removed を直に呼んで見る（FAST。盤面・git・子のプロセスなし）。単位の key は元の試験の返答 judge_ok の物を写した"""
import pathlib
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import planscope  # noqa: E402

MEAN, CLAMP = "stats.py mean: 分母が len(xs) - 1 になっている", "stats.py clamp: 上限を超えた値に lo を返す"   # 元 tests/replies/judge_ok.json の units の key

ITEM = {"item": 1, "unit_keys": [MEAN], "files": [], "route": "direct", "tests": [], "rewrite_tests": [],
        "allowed_paths": ["stats.py"], "out_of_scope": []}
ROW = {"unit_key": MEAN, "files": ["stats.py"]}
STATS = {"stats.py": ("def mean(xs):\n    return 0\n", "def mean(xs):\n    return 1\n")}


def item(**over):
    return {**ITEM, **over}


def add(name):
    """files の symbols の行（足す）"""
    return {"name": name, "change": "add"}


def rm(name):
    """files の symbols の行（消す。消す訳 why つき）"""
    return {"name": name, "change": "remove", "why": "古い名で、呼び手は新しい名に寄せた"}


def frow(path, *symbols, op="modify", **extra):
    """files の行（path・操作・symbols）。受け持ちは照らしに関わらない固定の字。home・considered は照らしに当たらない既定"""
    return {"path": path, "op": op, "responsibility": "この行の受け持ち", "symbols": list(symbols),
            "home": {"concept": f"{path} の考え", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}], **extra}


class ProblemsCase(unittest.TestCase):
    def test_inside_allowed_passes(self):
        self.assertEqual(planscope.problems([ITEM], [ROW], STATS)[0], [])

    def test_file_outside_allowed_names_unit_and_item(self):
        got, _ = planscope.problems([ITEM], [{"unit_key": MEAN, "files": ["other.py"]}], {**STATS, "other.py": (None, "x = 1\n")})
        self.assertTrue(any(MEAN in p and "other.py" in p and "項目 1" in p for p in got), got)

    def test_out_of_scope_wins_over_allowed(self):
        it = item(allowed_paths=["*.py"], out_of_scope=[{"glob": "test_*.py", "why": "既存の試験は触らない"}])
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": ["test_stats.py"]}], {"test_stats.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "test_*.py" in p for p in got), got)

    def test_undeclared_change_outside_every_item(self):
        got, _ = planscope.problems([ITEM], [ROW], {**STATS, "stray.py": (None, "x\n")})
        self.assertTrue(any("stray.py" in p for p in got), got)

    def test_item_without_footprint_is_missing(self):
        got, _ = planscope.problems([ITEM], [ROW], {})
        self.assertTrue(any("範囲の中に変えたファイルが無い" in p and MEAN in p for p in got), got)

    def test_adds_identifier_must_appear_in_added_lines(self):
        it = item(files=[frow("stats.py", add("median"))])
        self.assertTrue(any("median" in p for p in planscope.problems([it], [ROW], STATS)[0]))
        ok = {"stats.py": ("", "def median(xs):\n    return xs[0]\n")}
        self.assertEqual(planscope.problems([it], [ROW], ok)[0], [])

    def test_files_rows_check_same_name_per_path(self):
        """同じ名 median を stats.py と other.py の 2 行で足すと言い、差分が stats.py にだけ median を足した時、other.py の行だけが
        欠けとして名指される（名だけで数えると 2 行が潰れ、stats.py の足しで other.py の欠けも通る）。同じ path で名の違う 2 行も
        1 行ずつ照らされる"""
        two = item(allowed_paths=["*.py"], files=[frow("stats.py", add("median")), frow("other.py", add("median"))])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "other.py"]}]
        only_stats = {"stats.py": ("", "def median(xs):\n    return xs[0]\n"), "other.py": ("a\n", "b\n")}
        got, _ = planscope.problems([two], rows, only_stats)
        self.assertEqual([p for p in got if "median" in p and "other.py" in p and "足した行に無い" in p].__len__(), 1, got)
        self.assertFalse(any("stats.py の add median" in p for p in got), got)
        both = {**only_stats, "other.py": ("a\n", "def median(xs):\n    return xs[-1]\n")}
        self.assertEqual(planscope.problems([two], rows, both)[0], [])
        pair = item(files=[frow("stats.py", add("median"), add("mode"))])
        got, _ = planscope.problems([pair], [ROW], {"stats.py": ("", "def median(xs):\n    return xs[0]\n")})
        self.assertEqual([p for p in got if "足した行に無い" in p and "mode" in p].__len__(), 1, got)
        self.assertFalse(any("add median" in p for p in got), got)

    def test_files_ops_create_and_delete_follow_the_diff(self):
        """op=create の path が差分で新設されていない時と、op=delete の path が差分で消えていない時に、それぞれ行を名指して拒む。
        op=rename は元のパスが消え、移し先が新設されていることを見る（modify の差分は test_files_modify_path_must_change_in_diff）"""
        mk = item(allowed_paths=["*.py"], files=[frow("app.py", op="create")])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "app.py"]}]
        exists = {**STATS, "app.py": ("x = 1\n", "x = 2\n")}
        self.assertTrue(any("app.py" in p and "op=create" in p for p in planscope.problems([mk], rows, exists)[0]))
        self.assertTrue(any("app.py" in p and "op=create" in p for p in planscope.problems([mk], rows, STATS)[0]), "差分に無い")
        self.assertEqual(planscope.problems([mk], rows, {**STATS, "app.py": (None, "x = 1\n")})[0], [])
        rm_ = item(allowed_paths=["*.py"], files=[frow("old.py", op="delete", why="呼び手は stats に寄せたので要らない")])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "old.py"]}]
        self.assertTrue(any("old.py" in p and "op=delete" in p
                            for p in planscope.problems([rm_], rows, {**STATS, "old.py": ("a\n", "b\n")})[0]))
        self.assertEqual(planscope.problems([rm_], rows, {**STATS, "old.py": ("a\n", None)})[0], [])
        mv = item(allowed_paths=["*.py"], files=[frow("new.py", op="rename", **{"from": "old.py"}, why="名を実体に合わせた")])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "old.py", "new.py"]}]
        moved = {**STATS, "old.py": ("a\n", None), "new.py": (None, "a\n")}
        self.assertEqual(planscope.problems([mv], rows, moved)[0], [])
        got, _ = planscope.problems([mv], rows, {**STATS, "old.py": ("a\n", "b\n"), "new.py": ("c\n", "d\n")})
        self.assertTrue(any("old.py" in p and "op=rename" in p for p in got), got)
        self.assertTrue(any("new.py" in p and "op=rename" in p for p in got), got)

    def test_files_modify_path_must_change_in_diff(self):
        """op=modify の行は symbols が無くても、path が差分に無ければ欠けとして名指して拒む（前の欄 adds に既存の foo.py を書いた時と
        同じ照らし）。path を変えれば通る"""
        it = item(allowed_paths=["*.py"], files=[frow("foo.py")])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "foo.py"]}]
        got, _ = planscope.problems([it], rows, STATS)
        self.assertTrue(any("foo.py" in p and "op=modify" in p and MEAN in p for p in got), got)
        self.assertEqual(planscope.problems([it], rows, {**STATS, "foo.py": ("a\n", "b\n")})[0], [])

    def test_definition_outside_add_paths_is_extra(self):
        """同名の定義が足す行の path の外に在れば余分に数える"""
        it = item(allowed_paths=["*.py"], files=[frow("stats.py", add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "util.py": ("", "def median(xs):\n    pass\n")}
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": ["stats.py", "util.py"]}], ch)
        self.assertTrue(any("util.py" in p and "足す行の path" in p for p in got), got)
        both = item(allowed_paths=["*.py"], files=[frow("stats.py", add("median")), frow("util.py", add("median"))])
        self.assertEqual(planscope.problems([both], [{"unit_key": MEAN, "files": ["stats.py", "util.py"]}], ch)[0], [],
                         "同じ名を足すと言った行の path は、どれも足す先")

    def test_removes_identifier_must_be_gone(self):
        it = item(files=[frow("stats.py", rm("old_mean"))])
        kept = {"stats.py": ("def old_mean():\n    pass\n", "def old_mean():\n    return 1\n")}
        self.assertTrue(any("old_mean" in p for p in planscope.problems([it], [ROW], kept)[0]))
        gone = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n")}
        self.assertEqual(planscope.problems([it], [ROW], gone)[0], [])

    def test_prose_names_not_checked(self):
        it = item(files=[frow("stats.py", add("平均の定義の注記"), rm("古い注記の文"))])
        got, note = planscope.problems([it], [ROW], STATS)
        self.assertEqual(got, [])
        self.assertEqual(note["unchecked"], ["平均の定義の注記", "古い注記の文"])

    def test_new_test_must_be_named_in_tests(self):
        """tests に無い新しいテストは拒み、記録の overflow に名指す（申告した単位が無くても同じ）。tests に名指せば拒否の行も
        overflow も空"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        it = item(allowed_paths=["stats.py", "test_stats.py"])
        got, note = planscope.problems([it], [ROW], ch)
        self.assertTrue(any("test_stats.py::TestStats::test_extra" in p and "tests にも無い" in p for p in got), got)
        self.assertEqual([t for o in note.get("overflow") or [] for t in o["new_tests"]], ["test_stats.py::TestStats::test_extra"])
        named = item(tests=[{"id": "test_stats.py::TestStats::test_extra"}])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems([named], rows, ch)
        self.assertEqual((got, note.get("overflow")), ([], []))

    def test_new_test_in_unit_files_is_recorded_not_rejected(self):
        """run 75d8ed4e: 人の関所の条件に合わせて、単位が申告したファイルに tests に無いテストを足した。赤を確かめずに通さず、
        拒否の行にして記録の overflow に（その id・項目・単位を）並べる。unproven の欄は無い"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        it = item(allowed_paths=["stats.py", "test_stats.py"])
        got, note = planscope.problems([it], rows, ch)
        tid = "test_stats.py::TestStats::test_extra"
        self.assertTrue(any(tid in p for p in got), got)
        (over,) = note["overflow"]
        self.assertEqual((over["item"], over["unit_key"], over["new_tests"]), (1, MEAN, [tid]))
        self.assertIn(over["line"], got)
        self.assertNotIn("unproven", note)

    def test_new_test_outside_plan_is_overflow(self):
        """単位が申告したファイルに、どの項目の tests にも無いテストを足すと、拒否の行に入り、記録の overflow にその id と項目の
        番号と単位が並ぶ（応急処置の unproven の欄は無い）"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems([item(allowed_paths=["stats.py", "test_stats.py"])], rows, ch)
        tid = "test_stats.py::TestStats::test_extra"
        self.assertTrue(any(tid in p for p in got), got)
        over = note.get("overflow")
        self.assertEqual([(o["item"], o["unit_key"], o["new_tests"]) for o in over or []], [(1, MEAN, [tid])], note)
        self.assertTrue(all(o["line"] in got for o in over), (over, got))
        self.assertNotIn("unproven", note)

    def test_outside_path_is_overflow_with_item(self):
        """行の申告したパスが項目の allowed_paths の外なら、拒否の行と同じ文が overflow の line に入り、item はその単位の項目、
        paths はそのパス"""
        got, note = planscope.problems([ITEM], [{"unit_key": MEAN, "files": ["other.py"]}], {**STATS, "other.py": (None, "x = 1\n")})
        line = next(p for p in got if MEAN in p and "other.py" in p and "項目 1" in p)
        over = note.get("overflow")
        self.assertEqual([(o["line"], o["item"], o["unit_key"], o["paths"]) for o in over or []], [(line, 1, MEAN, ["other.py"])], note)

    def agreed_items(self, *kinds, tid="test_stats.py::TestStats::test_extra"):
        """項目 1 に、範囲の相談の合意で新しいテスト tid が入った写し（kinds の順に合意を重ねる）"""
        rows = [{"item": "1", "granted_paths": [], "granted_tests": [], "granted_new_tests": [{"id": tid, "red_kind": k}]}
                for k in kinds]
        return planscope.with_agreed([item(allowed_paths=["stats.py", "test_stats.py"])], rows)

    def test_agreed_test_not_written_is_not_missing(self):
        """合意で入ったテストは許しで義務でない: 修正役が書かなくても『tests の X が修正の後の木に無い』の欠けにしない"""
        rows = [{"unit_key": MEAN, "files": ["stats.py"]}]
        self.assertEqual(planscope.problems(self.agreed_items("red"), rows, STATS)[0], [])

    def test_agreed_test_written_under_other_name_is_overflow_not_missing(self):
        """合意の id と別の名で書いたテストは、案の外のテスト（はみ出し。相談に回る）で、合意の id の欠けにはしない"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_other(self):\n        pass\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        got, note = planscope.problems(self.agreed_items("red"), rows, ch)
        self.assertFalse([p for p in got if "修正の後の木に無い" in p], got)
        self.assertEqual([o["new_tests"] for o in note["overflow"]], [["test_stats.py::TestStats::test_other"]])

    def test_later_agreement_wins_for_same_id(self):
        """同じ id の合意を重ねると、後の合意の赤の種類が勝つ（相談で種類を直せる）"""
        (row,) = self.agreed_items("red", "guard")[0]["tests"]
        self.assertEqual(row["red_kind"], "guard")

    def test_agreed_new_test_joins_item_tests(self):
        """範囲の相談の合意（granted_new_tests）を持つ行を with_agreed に通した項目では、その新しいテストが項目の写しの tests に
        印 agreed と red_kind つきで並び、tests に無いテストの拒否の行（6）にならない"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_extra(self):\n        pass\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        tid = "test_stats.py::TestStats::test_extra"
        agreed = [{"item": "1", "granted_paths": [], "granted_tests": [],
                   "granted_new_tests": [{"id": tid, "red_kind": "red"}]}]
        got = planscope.with_agreed([ITEM], agreed)
        (row,) = got[0]["tests"]
        self.assertEqual((row["id"], row["red_kind"]), (tid, "red"))
        self.assertTrue(row.get("agreed"), row)
        self.assertEqual(ITEM["tests"], [], "元の項目は変えない")
        self.assertEqual(planscope.problems(got, rows, ch)[0], [])

    def test_named_test_missing_after_fix(self):
        it = item(tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        self.assertTrue(any("test_mean_of_two" in p and MEAN in p for p in planscope.problems([it], [ROW], STATS)[0]))

    def test_out_of_scope_wins_over_permits(self):
        """out_of_scope は permits（テストの変更の許し・直す裁定の limits）にも勝つ（案が外したパスが要るのは案の項目の誤りで、
        fix_plan_item の道）。行の申告したパスも、申告の無い変わったパスも拒む"""
        it = item(allowed_paths=["*.py"], out_of_scope=[{"glob": "legacy.py", "why": "古い置き場は触らない"}])
        ch = {**STATS, "legacy.py": ("a\n", "b\n")}
        for rows in ([{"unit_key": MEAN, "files": ["stats.py", "legacy.py"]}], [ROW]):
            got, _ = planscope.problems([it], rows, ch, permits=("legacy.py",))
            self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), (rows, got))

    def test_agreed_paths_join_their_item_only(self):
        """範囲の相談の合意（conflict.agreed の行）は、その項目の allowed_paths に足す（ほかの項目・out_of_scope は変えない）"""
        other = item(item=2, unit_keys=[CLAMP], allowed_paths=["clamp.py"])
        agreed = [{"item": "1", "granted_paths": ["CHANGELOG.md"], "granted_tests": ["test_stats.py:3"]}]
        got = planscope.with_agreed([ITEM, other], agreed)
        self.assertEqual(got[0]["allowed_paths"], ["stats.py", "CHANGELOG.md"])
        self.assertEqual(got[1]["allowed_paths"], ["clamp.py"])
        self.assertEqual(ITEM["allowed_paths"], ["stats.py"], "元の項目は変えない")
        ch = {**STATS, "CHANGELOG.md": ("a\n", "b\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "CHANGELOG.md"]}]
        self.assertTrue(planscope.problems([ITEM], rows, ch)[0], "合意の無い時は拒む")
        self.assertEqual(planscope.problems(got, rows, ch)[0], [])

    def test_permit_paths_are_in_scope(self):
        ch = {**STATS, "test_stats.py": ("a\n", "b\n")}
        self.assertEqual(planscope.problems([ITEM], [ROW], ch, permits=("test_stats.py",))[0], [])

    def test_new_test_ids_only_test_modules(self):
        src = "def test_x():\n    pass\n"
        self.assertEqual(planscope.new_test_ids("util.py", None, src), [], "試験のモジュールの名でない .py は数えない")
        self.assertEqual(planscope.new_test_ids("test_util.py", None, src), ["test_util.py::test_x"])
        self.assertEqual(planscope.new_test_ids("util_test.py", "", src), ["util_test.py::test_x"])
        self.assertEqual(planscope.new_test_ids("test_util.py", None, "def test_x(:\n"), [], "構文の壊れた now は []")
        self.assertEqual(planscope.new_test_ids("test_util.md", None, src), [])

    def test_added_removed_replace(self):
        self.assertEqual(planscope.added_removed("a\nb\n", "a\nc\n"), (["c"], ["b"]))
        self.assertEqual(planscope.added_removed(None, "x\n"), (["x"], []), "None は空の中身")
        self.assertEqual(planscope.added_removed("x\n", None), ([], ["x"]))

    def test_note_records_checked_items(self):
        _, note = planscope.problems([ITEM, item(item=2, unit_keys=[CLAMP])], [ROW], STATS)
        self.assertEqual((note["checked"], note["items"]), (True, [1]), "見る項目は rows の単位と重なる項目だけ")

    def test_problem_lines_carry_unit_keys_for_binding(self):
        """拒否の行は単位の key か項目の unit_keys の全部を字のまま含める（3 回目の拒否で単位に結ぶ）"""
        it = item(unit_keys=[MEAN, CLAMP], files=[frow("stats.py", add("median"), rm("old_mean"))],
                  tests=[{"id": "test_stats.py::TestStats::test_two"}])
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": ["other.py"]}, {"unit_key": CLAMP, "files": ["stats.py"]}],
                                    {"other.py": (None, "x\n")})
        unit_lines = [p for p in got if "どの項目の allowed_paths にも無い" not in p]
        self.assertTrue(unit_lines)
        for p in unit_lines:
            self.assertTrue(MEAN in p or CLAMP in p, p)


class HeldItemCase(unittest.TestCase):
    """裁定で外れた単位の項目も範囲を与える（依頼 241。外れた単位を直させない守りは受け付けの check_excused_units）"""

    def test_held_item_grants_like_any_item(self):
        mean = item(allowed_paths=["stats.py", "mean_util.py"], out_of_scope=[{"glob": "legacy.py", "why": "古い置き場は触らない"}],
                    tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        clamp = item(item=2, unit_keys=[CLAMP], allowed_paths=["stats.py", "test_stats.py", "legacy.py"])
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "mean_util.py": (None, "x = 1\n"),
              "test_stats.py": (base, base + "    def test_mean_of_two(self):\n        pass\n")}
        rows = [{"unit_key": CLAMP, "files": ["stats.py", "test_stats.py"]}]
        self.assertEqual(planscope.problems([mean, clamp], rows, ch)[0], [], "外れた項目 1 の範囲と tests にも入る")
        got, _ = planscope.problems([mean, clamp], [{"unit_key": MEAN, "files": ["legacy.py"]}], {"legacy.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), "外れた項目の単位には今どおり拒む")
        got, _ = planscope.problems([mean, clamp], [{"unit_key": CLAMP, "files": ["stats.py"]}],
                                    {"stats.py": STATS["stats.py"], "legacy.py": ("a\n", "b\n")})
        self.assertTrue(any("out_of_scope" in p and "legacy.py" in p for p in got), "単位に結べない変更は今どおり拒む")
        self.assertEqual(planscope.problems([mean, clamp], [{"unit_key": CLAMP, "files": ["legacy.py"]}],
                                            {"legacy.py": ("a\n", "b\n")})[0], [],
                         "項目 2 が明示に許したパスは、項目 2 の単位では項目 1 の out_of_scope に負けない（run 249b）")


class FalseRejectCase(unittest.TestCase):
    """正しい修正を誤って拒まない（審査の Important 2・3）"""

    def test_absent_partner_unit_does_not_reject_live_unit(self):
        """項目 [MEAN, CLAMP] の MEAN が行に無い（止めた・外した）とき、足す物・消す物・tests の欠けで CLAMP を拒まない
        （Missing 側は項目の単位が全部生きている時だけ見る）。範囲の検査は残る"""
        it = item(unit_keys=[MEAN, CLAMP], files=[frow("stats.py", add("median"), rm("old_mean"))],
                  tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}])
        rows = [{"unit_key": CLAMP, "files": ["stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, STATS)[0], [])
        got, _ = planscope.problems([it], [{"unit_key": CLAMP, "files": ["other.py"]}], {"other.py": (None, "x\n")})
        self.assertTrue(any(CLAMP in p and "other.py" in p for p in got), got)
        both = [{"unit_key": MEAN, "files": ["stats.py"]}, {"unit_key": CLAMP, "files": ["stats.py"]}]
        self.assertTrue(any("median" in p for p in planscope.problems([it], both, STATS)[0]), "全部の単位が生きていれば見る")

    def test_mentioned_removed_name_is_gone(self):
        """消した名が足した行に定義でなく現れる（消えたことを確かめる hasattr・CHANGELOG の注記）だけなら、残ったと見ない"""
        it = item(allowed_paths=["*.py", "CHANGELOG.md"], files=[frow("stats.py", rm("old_mean"))])
        ch = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n"),
              "check_gone.py": (None, "import stats\nassert not hasattr(stats, 'old_mean')\n"),
              "CHANGELOG.md": ("# 変更\n", "# 変更\n- `old_mean` を消した\n")}
        rows = [{"unit_key": MEAN, "files": sorted(ch)}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])
        again = {**ch, "util.py": (None, "def old_mean():\n    pass\n")}
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": sorted(again)}], again)
        self.assertTrue(any("old_mean" in p for p in got), "足した行に定義が在れば残ったと見る")

    CONCEPTS_LINE = '  "pattern": "def where_paths|def lead_path",\n'

    def test_definition_text_in_data_file_is_not_outside_add_paths(self):
        """行の頭（字下げは許す）で始まる定義だけを定義と数える: 表（JSON）の文字列の中の `def <名>` は足す行の path の外の定義でなく、
        字下げした本物の定義（async def）は数え続ける"""
        it = item(allowed_paths=["stats.py", "util.py", "docs/**"],
                  files=[frow("stats.py", add("where_paths"))])
        ch = {"stats.py": ("", "def where_paths(xs):\n    return xs\n"),
              "docs/concepts.json": ("", self.CONCEPTS_LINE),
              "util.py": ("", "    async def where_paths(xs):\n        return xs\n")}
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": sorted(ch)}], ch)
        outside = [p for p in got if "足す行の path" in p]
        self.assertTrue(any("util.py" in p for p in outside), got)
        self.assertFalse(any("docs/concepts.json" in p for p in got), got)

    def test_removed_name_in_data_file_string_is_gone(self):
        """files の change=remove の名を消した差分に、その名を `def <名>` の字で含む表（JSON）の文字列を足しても、足した行に定義が残ったと見ない"""
        it = item(allowed_paths=["stats.py", "docs/**"], files=[frow("stats.py", rm("lead_path"))])
        ch = {"stats.py": ("def lead_path(xs):\n    return xs\n", "def where_paths(xs):\n    return xs\n"),
              "docs/concepts.json": ("", self.CONCEPTS_LINE)}
        got, _ = planscope.problems([it], [{"unit_key": MEAN, "files": sorted(ch)}], ch)
        self.assertEqual(got, [])

    def test_dotted_name_found_by_last_segment(self):
        """名は :: と . で割った最後の段で探す。/ を含む名は確かめず unchecked に回す"""
        it = item(files=[frow("stats.py", add("Stats.median"), add("平均の注記"))])
        ch = {"stats.py": ("", "class Stats:\n    def median(self):\n        pass\n")}
        got, note = planscope.problems([it], [ROW], ch)
        self.assertEqual(got, [])
        self.assertEqual(note["unchecked"], ["平均の注記"])

    def test_py_file_name_is_module_not_extension(self):
        """.py のファイルは symbols の名でなく、行の path と op で見る: op=create の行は path が差分で新設されたか（足した行の 'py' の
        語で通さない）、op=delete の行は path が差分で消えたか（ファイルの中身が自分の名を書かないので語では探せない）"""
        it = item(allowed_paths=["*.py", "app/**"], files=[frow("app/receivers.py", op="create")])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "app/receivers.py"]}]
        word_only = {"stats.py": ("a\n", "a\np = \"data.py\"\n")}
        self.assertTrue(any("app/receivers.py" in p for p in planscope.problems([it], rows, word_only)[0]),
                        "モジュールのファイルが無ければ、足した行の 'py' の語で通さない")
        added = {"stats.py": ("a\n", "b\n"), "app/receivers.py": (None, "def handle():\n    pass\n")}
        self.assertEqual(planscope.problems([it], rows, added)[0], [], "モジュールのファイルを足せば、中身に自分の名が無くても通る")
        pkg = item(allowed_paths=["*.py", "app/**"], files=[frow("app/receivers/__init__.py", op="create")])
        files = {"stats.py": ("a\n", "b\n"), "app/receivers/__init__.py": (None, "X = 1\n")}
        self.assertEqual(planscope.problems([pkg], [{"unit_key": MEAN, "files": sorted(files)}], files)[0], [])
        rm_ = item(allowed_paths=["*.py"], files=[frow("old.py", op="delete", why="呼び手は stats に寄せたので要らない")])
        gone = {"stats.py": ("a\n", "b\n"), "old.py": ("def f():\n    pass\n", None)}
        self.assertEqual(planscope.problems([rm_], [{"unit_key": MEAN, "files": sorted(gone)}], gone)[0], [])
        kept = {"stats.py": ("a\n", "b\n"), "old.py": ("import x.py\n", "y = 1\n")}
        self.assertTrue(any("old.py" in p for p in planscope.problems([rm_], [{"unit_key": MEAN, "files": sorted(kept)}], kept)[0]),
                        "ファイルが残れば、消した行の 'py' の語で通さない")

    def test_py_file_name_edge_shapes(self):
        """空の __init__.py で新設したパッケージも新設に数える（新しいファイルは足した行が無くてもよい）。パスは op=create の行の path
        そのもので見る（拡張子の前に . を含む名も、名の字の読み分けでなく path の一致）"""
        it = item(allowed_paths=["*.py", "app/**"],
                  files=[frow("app/receivers/__init__.py", op="create"), frow("app/receivers/core.py", op="create")])
        pkg = {"stats.py": ("a\n", "b\n"), "app/receivers/__init__.py": (None, ""), "app/receivers/core.py": (None, "X = 1\n")}
        self.assertEqual(planscope.problems([it], [{"unit_key": MEAN, "files": sorted(pkg)}], pkg)[0], [])
        dotted = item(allowed_paths=["*.py"], files=[frow("app.receivers.py", op="create")])
        got, note = planscope.problems([dotted], [{"unit_key": MEAN, "files": ["stats.py", "app.receivers.py"]}],
                                       {**STATS, "app.receivers.py": (None, "")})
        self.assertEqual((got, note["unchecked"]), ([], []))

    # docstring の __doc__（run 35ad1c2a: stats.mode.__doc__ を足すと言った案を、def の直下に足した docstring の差分で拒んだ）
    SRC = "def mean(xs):\n    return 0\n\n\ndef mode(xs):\n    return max(xs, key=xs.count)\n"

    def test_doc_attribute_found_by_docstring(self):
        """名の最後の段が __doc__ なら、足した行の語でなく、その前の段の def・class が差分で docstring を得たかを ast で見る
        （docstring の字は __doc__ を書かない）"""
        it = item(files=[frow("stats.py", add("mode.__doc__"))])
        now = self.SRC.replace("def mode(xs):\n", "def mode(xs):\n    \"\"\"最頻値。空の xs は ValueError\"\"\"\n")
        got, note = planscope.problems([it], [ROW], {"stats.py": (self.SRC, now)})
        self.assertEqual((got, note["unchecked"]), ([], []))

    def test_doc_attribute_missing_when_owner_gains_no_docstring(self):
        """名指した def が docstring を得なければ Missing（ほかの関数の docstring・本体の変更では通さない）"""
        it = item(files=[frow("stats.py", add("mode.__doc__"))])
        body = self.SRC.replace("key=xs.count", "key=xs.count)  # 最頻値\n    (0")
        other = self.SRC.replace("def mean(xs):\n", "def mean(xs):\n    \"\"\"平均\"\"\"\n")
        for now in (body, other):
            got, _ = planscope.problems([it], [ROW], {"stats.py": (self.SRC, now)})
            self.assertTrue(any("mode.__doc__" in p and MEAN in p for p in got), got)

    def test_doc_attribute_same_docstring_is_not_added(self):
        """版に既に在る docstring と同じ字のままなら足していない（変えた docstring は足した物に数える）"""
        it = item(files=[frow("stats.py", add("mode.__doc__"))])
        base = self.SRC.replace("def mode(xs):\n", "def mode(xs):\n    \"\"\"最頻値\"\"\"\n")
        same = base.replace("key=xs.count", "key=lambda x: xs.count(x)")
        self.assertTrue(planscope.problems([it], [ROW], {"stats.py": (base, same)})[0])
        changed = base.replace("最頻値", "最頻値。空の xs は ValueError")
        self.assertEqual(planscope.problems([it], [ROW], {"stats.py": (base, changed)})[0], [])

    def test_doc_attribute_of_method_module_and_path_forms(self):
        """クラスの中の def（Stats.median.__doc__）・モジュール（名だけの __doc__）は行の path のファイルで同じに見る。パスは行の
        path 欄に移ったので、<パス>::<名>.__doc__ の形は要らない"""
        base = "class Stats:\n    def median(self):\n        pass\n"
        meth = item(files=[frow("stats.py", add("Stats.median.__doc__"))])
        now = base.replace("def median(self):\n", "def median(self):\n        \"\"\"中央値\"\"\"\n")
        self.assertEqual(planscope.problems([meth], [ROW], {"stats.py": (base, now)})[0], [])
        mod = item(files=[frow("stats.py", add("__doc__"))])
        self.assertEqual(planscope.problems([mod], [ROW], {"stats.py": (base, "\"\"\"数の道具\"\"\"\n" + base)})[0], [])
        self.assertTrue(planscope.problems([mod], [ROW], {"stats.py": (base, now)})[0], "def の docstring はモジュールの物でない")
        other = item(allowed_paths=["*.py"], files=[frow("other.py", add("Stats.median.__doc__"))])
        got, _ = planscope.problems([other], [{"unit_key": MEAN, "files": ["stats.py", "other.py"]}],
                                    {"stats.py": (base, now), "other.py": ("a\n", "b\n")})
        self.assertTrue(any("other.py" in p and "Stats.median.__doc__" in p for p in got), "別の path の docstring では通さない")

    def test_doc_attribute_literal_assignment_still_passes(self):
        """__doc__ の字を書いて足す形（mode.__doc__ = ...）は今までどおり足した行の語で通る"""
        it = item(files=[frow("stats.py", add("mode.__doc__"))])
        now = self.SRC + "\n\nmode.__doc__ = \"最頻値\"\n"
        self.assertEqual(planscope.problems([it], [ROW], {"stats.py": (self.SRC, now)})[0], [])


class LoopFrozenCase(unittest.TestCase):
    """TDD の輪が凍らせたファイル（loop: パス → 凍った時の中身）。修正役に問うのは凍った後に変えた分だけ、欠けは版から見る"""
    BASE = "class TestStats:\n    def test_a(self):\n        pass\n"
    FROZEN = BASE + "    def test_new(self):\n        pass\n"

    def test_untouched_frozen_file_not_charged(self):
        it = item(tests=[{"id": "test_stats.py::TestStats::test_new"}])
        ch = {**STATS, "test_stats.py": (self.BASE, self.FROZEN), "data.json": (None, "[]\n")}
        loop = {"test_stats.py": self.FROZEN, "data.json": "[]\n"}
        self.assertEqual(planscope.problems([it], [ROW], ch, loop=loop)[0], [])
        got = planscope.problems([it], [ROW], ch)[0]
        self.assertTrue(any("data.json" in p for p in got), "輪の無い run なら範囲の外")

    def test_test_added_after_freeze_counts(self):
        it = item(tests=[{"id": "test_stats.py::TestStats::test_new"}])
        now = self.FROZEN + "    def test_after(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (self.BASE, now)}
        got = planscope.problems([it], [ROW], ch, loop={"test_stats.py": self.FROZEN}, permits=("test_stats.py",))[0]
        self.assertTrue(any("test_after" in p for p in got), got)
        self.assertFalse(any("test_new" in p for p in got), got)

    def test_qualified_remove_sees_other_class(self):
        """消す名 Stats.median は、Legacy.median を消して Stats.median を残した差分を拒む（ast の名で見る）"""
        base = "class Legacy:\n    def median(self):\n        pass\n\n\nclass Stats:\n    def median(self):\n        pass\n"
        now = "class Legacy:\n    pass\n\n\nclass Stats:\n    def median(self):\n        pass\n"
        ch = {"stats.py": (base, now)}
        got = planscope.problems([item(files=[frow("stats.py", rm("Stats.median"))])], [ROW], ch)[0]
        self.assertTrue(any("Stats.median" in p for p in got), got)
        self.assertEqual(planscope.problems([item(files=[frow("stats.py", rm("Legacy.median"))])], [ROW], ch)[0], [])

    def test_removed_call_with_kept_definition_remains(self):
        """呼び出しの行だけを消して定義を残した差分は、消えていない"""
        base = "def old_mean():\n    pass\n\n\nx = old_mean()\n"
        now = "def old_mean():\n    pass\n\n\nx = 1\n"
        got = planscope.problems([item(files=[frow("stats.py", rm("old_mean"))])], [ROW], {"stats.py": (base, now)})[0]
        self.assertTrue(any("old_mean" in p for p in got), got)


class Round3Case(unittest.TestCase):
    """修飾子をファイルごとに解く規則・凍った時の中身が無いファイル・凍ったファイルの外れと余分（審査の M1〜M4）"""
    FROZEN_HELPER = "def median(xs):\n    return xs[0]\n"

    def test_module_qualified_moved_definition_remains(self):
        """stats.old_mean（モジュール名の修飾子）・stats.py::old_mean の定義を同じファイルの中で移しただけの差分は拒む"""
        base = "def old_mean():\n    pass\n\n\ndef a():\n    pass\n\n\ndef b():\n    pass\n"
        now = "def a():\n    pass\n\n\ndef b():\n    pass\n\n\ndef old_mean():\n    pass\n"
        self.assertIn("def old_mean():", planscope.added_removed(base, now)[1], "定義の行は消した行にも出る（移した）")
        for raw in ("stats.old_mean", "stats.py::old_mean"):
            with self.subTest(raw):
                got = planscope.problems([item(files=[frow("stats.py", rm(raw))])], [ROW], {"stats.py": (base, now)})[0]
                self.assertTrue(any(raw in p for p in got), got)

    def test_module_qualified_other_module_keeps_own_name(self):
        """legacy.median を消し、stats.py が自前の median を残す（その名を含む行は消した）差分は通る"""
        it = item(allowed_paths=["*.py"], files=[frow("legacy.py", rm("legacy.median"))])
        ch = {"legacy.py": ("def median(xs):\n    return 0\n", "x = 1\n"),
              "stats.py": ("def median(xs):\n    return 0\n\n\ny = median([1])\n", "def median(xs):\n    return 0\n")}
        rows = [{"unit_key": MEAN, "files": ["legacy.py", "stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])

    def test_unreadable_frozen_content_falls_back_to_base(self):
        """凍った時の中身が無い（None）ファイルは、版からの差分で数える（版から在るテストを足した物と見ない）"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        ch = {**STATS, "test_stats.py": (base, base + "    def test_b(self):\n        pass\n")}
        it = item(allowed_paths=["stats.py", "test_stats.py"], tests=[{"id": "test_stats.py::TestStats::test_b"}])
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_stats.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch, loop={"test_stats.py": None})[0], [])

    def test_definition_outside_add_paths_in_frozen_file(self):
        """輪が書いて凍らせたファイルの同名の定義は足す行の path の外として問わない。凍った後に修正役が足した物は拒む"""
        it = item(allowed_paths=["*.py"], files=[frow("stats.py", add("median"))])
        stats = ("", "def median(xs):\n    return xs[0]\n")
        rows = [{"unit_key": MEAN, "files": ["stats.py"]}]
        loop_written = {"stats.py": stats, "helper.py": (None, self.FROZEN_HELPER)}
        self.assertEqual(planscope.problems([it], rows, loop_written, loop={"helper.py": self.FROZEN_HELPER})[0], [])
        after = {"stats.py": stats, "helper.py": (None, "x = 1\n" + self.FROZEN_HELPER)}
        got = planscope.problems([it], rows, after, loop={"helper.py": "x = 1\n"})[0]
        self.assertTrue(any("helper.py" in p and "足す行の path" in p for p in got), got)

    def test_tdd_shape_with_test_adds_passes(self):
        """TDD の形: 試験のファイルの行の symbol test_mean_of_two は輪が書いて凍らせ、凍った後に変わっていなくても、版からの差分で在る"""
        base = "class TestStats:\n    def test_a(self):\n        pass\n"
        frozen = base + "    def test_mean_of_two(self):\n        pass\n"
        it = item(allowed_paths=["stats.py"], tests=[{"id": "test_stats.py::TestStats::test_mean_of_two"}],
                  files=[frow("test_stats.py", add("TestStats::test_mean_of_two"))])
        ch = {**STATS, "test_stats.py": (base, frozen)}
        self.assertEqual(planscope.problems([it], [ROW], ch, loop={"test_stats.py": frozen})[0], [])

    def test_declared_untouched_frozen_file_not_rejected(self):
        """行が凍った後に変わっていないファイル（範囲の外）を申告しても拒まない"""
        ch = {**STATS, "data.json": (None, "[]\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "data.json"]}]
        self.assertEqual(planscope.problems([ITEM], rows, ch, loop={"data.json": "[]\n"})[0], [])

    def test_same_name_in_untouched_lines_of_other_file_is_gone(self):
        """名を含む行に触れていない別の .py に同じ名の定義が在っても、残ったとは見ない"""
        it = item(allowed_paths=["*.py"], files=[frow("stats.py", rm("old_mean"))])
        ch = {"stats.py": ("def old_mean():\n    pass\n", "def mean():\n    pass\n"),
              "util.py": ("def old_mean():\n    pass\n\n\nA = 1\n", "def old_mean():\n    pass\n\n\nA = 2\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "util.py"]}]
        self.assertEqual(planscope.problems([it], rows, ch)[0], [])


class CrossItemScopeCase(unittest.TestCase):
    """ほかの項目の out_of_scope は、行の単位の項目が明示に許したパス（allowed_paths・tests の id のファイル・範囲の相談の合意）を
    拒まない（run 249b: 項目 1 の out_of_scope の core/** が、項目 2 の allowed_paths の core の 1 ファイルを直した項目 2 の
    単位を 2 回拒み、単位が止まった）。単位に結べない変更と、単位の項目が許していないパスは今どおり全部の項目の out_of_scope で拒む"""
    ONE = item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "core/**", "why": "項目 1 は共有の core を変えない"}])
    TWO = item(item=2, unit_keys=[CLAMP], allowed_paths=["core/seam.py"])
    CH = {**STATS, "core/seam.py": ("a\n", "b\n")}

    def test_owner_item_allowed_path_passes(self):
        rows = [ROW, {"unit_key": CLAMP, "files": ["core/seam.py"]}]
        self.assertEqual(planscope.problems([self.ONE, self.TWO], rows, self.CH)[0], [])

    def test_owner_item_test_file_passes(self):
        two = item(item=2, unit_keys=[CLAMP], allowed_paths=["clamp.py"], tests=[{"id": "core/test_seam.py::test_clamp"}])
        ch = {**STATS, "clamp.py": ("a\n", "b\n"), "core/test_seam.py": ("", "def test_clamp():\n    pass\n")}
        rows = [ROW, {"unit_key": CLAMP, "files": ["clamp.py", "core/test_seam.py"]}]
        self.assertEqual(planscope.problems([self.ONE, two], rows, ch)[0], [])

    def test_owner_item_granted_path_passes(self):
        """範囲の相談で項目 2 に許したパス（with_agreed が allowed_paths に足す）も、項目 2 の単位では項目 1 の out_of_scope に負けない"""
        items = planscope.with_agreed([self.ONE, self.TWO], [{"item": "2", "granted_paths": ["core/doc.md"]}])
        ch = {**self.CH, "core/doc.md": ("a\n", "b\n")}
        rows = [ROW, {"unit_key": CLAMP, "files": ["core/seam.py", "core/doc.md"]}]
        self.assertEqual(planscope.problems(items, rows, ch)[0], [])

    def test_excluding_item_unit_still_rejected(self):
        """項目 1 の単位が同じパスを申告すれば、項目 1 の out_of_scope で拒む"""
        rows = [{"unit_key": MEAN, "files": ["stats.py", "core/seam.py"]}]
        got, _ = planscope.problems([self.ONE, self.TWO], rows, self.CH)
        self.assertTrue(any(MEAN in p and "core/seam.py" in p and "項目 1 の out_of_scope" in p for p in got), got)

    def test_path_outside_owner_scope_still_rejected(self):
        """行の単位の項目が許していないパスは、ほかの項目の out_of_scope で今どおり拒む（permits に入っていても）"""
        ch = {**self.CH, "core/other.py": ("a\n", "b\n")}
        rows = [ROW, {"unit_key": CLAMP, "files": ["core/seam.py", "core/other.py"]}]
        got, _ = planscope.problems([self.ONE, self.TWO], rows, ch, permits=("core/other.py",))
        self.assertTrue(any(CLAMP in p and "core/other.py" in p and "out_of_scope" in p for p in got), got)
        self.assertFalse(any("core/seam.py" in p for p in got), got)

    def test_own_item_out_of_scope_still_wins(self):
        two = item(item=2, unit_keys=[CLAMP], allowed_paths=["core/**"],
                   out_of_scope=[{"glob": "core/seam.py", "why": "項目 2 も継ぎ目は変えない"}])
        got, _ = planscope.problems([self.ONE, two], [ROW, {"unit_key": CLAMP, "files": ["core/seam.py"]}], self.CH)
        self.assertTrue(any(CLAMP in p and "項目 2 の out_of_scope" in p for p in got), got)

    def test_unattributed_change_still_rejected_and_names_owner(self):
        """どの行も申告していない変わったパスは単位に結べないので、全部の項目の out_of_scope で拒む。行は許す項目を名指し、
        その項目の単位の files に申告する道を言う"""
        got, _ = planscope.problems([self.ONE, self.TWO], [ROW], self.CH)
        hit = [p for p in got if "core/seam.py" in p]
        self.assertTrue(hit and "項目 1 の out_of_scope" in hit[0] and "項目 2" in hit[0] and "files" in hit[0], got)



class AgreedOverridesOutOfScopeCase(unittest.TestCase):
    """範囲の相談で修正案を書いた役が、その項目の out_of_scope に当たるパスを考え直して許した時（持ち主 2026-10-07「相談で
    考え直させる」）、許したパスに限ってその項目の out_of_scope を外す（with_agreed）。許したパスと字のまま同じパスだけを外し
    （glob の許しで広げない）、ほかの項目の out_of_scope は外さない。合意の無い時は今どおり拒む"""
    ONE = item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "CHANGELOG.md", "why": "記録は別の依頼でまとめて書く"},
                                                         {"glob": "docs/**", "why": "文書は触らない"}])
    CH = {**STATS, "CHANGELOG.md": ("a\n", "b\n")}
    ROWS = [{"unit_key": MEAN, "files": ["stats.py", "CHANGELOG.md"]}]

    def test_without_agreement_still_rejected(self):
        got, _ = planscope.problems(planscope.with_agreed([self.ONE], []), self.ROWS, self.CH)
        self.assertTrue(any("CHANGELOG.md" in p and "out_of_scope" in p for p in got), got)

    def test_granted_path_overrides_own_out_of_scope(self):
        items = planscope.with_agreed([self.ONE], [{"item": "1", "granted_paths": ["CHANGELOG.md"]}])
        self.assertEqual(planscope.problems(items, self.ROWS, self.CH)[0], [])
        self.assertEqual(planscope.problems(items, [ROW], self.CH)[0], [], "申告の無い変更も、外した項目の out_of_scope では拒まない")
        self.assertEqual(self.ONE["out_of_scope"][0]["glob"], "CHANGELOG.md", "元の項目は変えない")

    def test_override_is_exact_path_only(self):
        """docs/a.md を許しても、同じ glob docs/** の docs/b.md は外さない"""
        items = planscope.with_agreed([self.ONE], [{"item": "1", "granted_paths": ["docs/a.md"]}])
        ch = {**STATS, "docs/a.md": ("a\n", "b\n"), "docs/b.md": ("a\n", "b\n")}
        got, _ = planscope.problems(items, [{"unit_key": MEAN, "files": ["stats.py", "docs/a.md", "docs/b.md"]}], ch)
        self.assertFalse(any("docs/a.md" in p for p in got), got)
        self.assertTrue(any("docs/b.md" in p and "out_of_scope" in p for p in got), got)

    def test_granted_test_file_overrides_own_out_of_scope(self):
        """書き換えを許したテスト（granted_tests。permits に入る）のファイルも、その項目の out_of_scope から外す"""
        one = item(allowed_paths=["stats.py"], out_of_scope=[{"glob": "test_old.py", "why": "古い試験は触らない"}])
        items = planscope.with_agreed([one], [{"item": "1", "granted_paths": [], "granted_tests": ["test_old.py:3"]}])
        ch = {**STATS, "test_old.py": ("a\n", "b\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "test_old.py"]}]
        self.assertTrue(planscope.problems([one], rows, ch, permits=("test_old.py",))[0])
        self.assertEqual(planscope.problems(items, rows, ch, permits=("test_old.py",))[0], [])

    def test_other_item_out_of_scope_is_not_lifted(self):
        """項目 2 に許したパスは項目 1 の out_of_scope を外さない: 項目 2 の単位では通り（e7906845）、項目 1 の単位と申告の無い
        変更は項目 1 の out_of_scope で今どおり拒む"""
        two = item(item=2, unit_keys=[CLAMP], allowed_paths=["clamp.py"])
        items = planscope.with_agreed([self.ONE, two], [{"item": "2", "granted_paths": ["CHANGELOG.md"]}])
        ch = {**self.CH, "clamp.py": ("a\n", "b\n")}
        ok = [ROW, {"unit_key": CLAMP, "files": ["clamp.py", "CHANGELOG.md"]}]
        self.assertEqual(planscope.problems(items, ok, ch)[0], [])
        got, _ = planscope.problems(items, [ROW, {"unit_key": CLAMP, "files": ["clamp.py"]}], ch)
        self.assertTrue(any("CHANGELOG.md" in p and "項目 1 の out_of_scope" in p for p in got), got)


class NameOverlapCase(unittest.TestCase):
    """名が字で同じでも、言語・テストかの種類と在り処の違う物は別の物と読み、人に回る申し出を作らない（#664。本物の run で人に
    回った 3 件と、無関係な局所の助け手の改名を強いた 1 件の形）。種類の同じ別のファイルの同名は今どおり拒み、裁定が許したパスなら通す"""
    UNIT = [{"unit_key": MEAN, "files": ["deploy/values.yaml", ".env.sample"]}]

    def test_env_var_in_deploy_values_and_local_sample_is_not_outside_add_paths(self):
        it = item(allowed_paths=["deploy/values.yaml", ".env.sample"], files=[frow("deploy/values.yaml", add("APP_NOTICE_FILE"))])
        ch = {"deploy/values.yaml": ("env:\n", "env:\n  APP_NOTICE_FILE: /data/notice.json\n"),
              ".env.sample": ("", "APP_NOTICE_FILE=./notice.json\n")}
        self.assertEqual(planscope.problems([it], self.UNIT, ch)[0], [])

    def test_same_type_name_in_other_language_is_not_outside_add_paths(self):
        model, iface = ("api/models.py", "class Notice(BaseModel):\n    title: str\n"), \
            ("web/src/notice.ts", "export interface Notice {\n  title: string\n}\n")
        for (path, _), (other, text) in ((model, iface), (iface, model)):
            with self.subTest(add=path):
                it = item(allowed_paths=["api/**", "web/**"], files=[frow(path, add("Notice"))])
                ch = {model[0]: ("", model[1]), iface[0]: ("", iface[1])}
                rows = [{"unit_key": MEAN, "files": sorted(ch)}]
                self.assertEqual(planscope.problems([it], rows, ch)[0], [], other)

    def test_test_function_named_like_product_function_is_another_thing(self):
        it = item(allowed_paths=["stats.py", "test_stats.py"], files=[frow("stats.py", add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "test_stats.py": ("", "def median():\n    pass\n")}
        self.assertEqual(planscope.problems([it], [{"unit_key": MEAN, "files": sorted(ch)}], ch)[0], [])

    def test_same_kind_other_file_still_rejected_until_ruled(self):
        """種類の同じ別のファイルの同名の定義は拒み、裁定が許したパス（permits）なら別の物と裁いた物として通す"""
        it = item(allowed_paths=["*.py"], files=[frow("stats.py", add("median"))])
        ch = {"stats.py": ("", "def median(xs):\n    pass\n"), "util.py": ("", "def median(xs):\n    pass\n")}
        rows = [{"unit_key": MEAN, "files": ["stats.py", "util.py"]}]
        self.assertTrue(any("util.py" in p and "足す行の path" in p for p in planscope.problems([it], rows, ch)[0]))
        self.assertEqual(planscope.problems([it], rows, ch, permits=("util.py",))[0], [])

    def test_unrelated_local_helper_with_removed_name(self):
        """消す名と同じ字の局所の助け手を別のファイルに足した: 種類の同じファイルは拒み、裁定が許せば通す。種類の違う文書の
        字下げのコード例は残りに数えない。行の path に残る名は許しがあっても拒む"""
        it = item(allowed_paths=["*.py", "docs/**"], files=[frow("stats.py", rm("_entry"))])
        gone = ("def _entry():\n    pass\n", "def mean():\n    pass\n")
        ch = {"stats.py": gone, "report.py": (None, "def _entry(row):\n    return row\n")}
        rows = [{"unit_key": MEAN, "files": sorted(ch)}]
        self.assertTrue(any("_entry" in p for p in planscope.problems([it], rows, ch)[0]))
        self.assertEqual(planscope.problems([it], rows, ch, permits=("report.py",))[0], [])
        doc = {"stats.py": gone, "docs/howto.md": (None, "例:\n\n    def _entry():\n        pass\n")}
        self.assertEqual(planscope.problems([it], [{"unit_key": MEAN, "files": sorted(doc)}], doc)[0], [])
        kept = {"stats.py": ("def _entry():\n    pass\n", "def _entry():\n    return 1\n")}
        self.assertTrue(any("_entry" in p for p in planscope.problems([it], [ROW], kept, permits=("stats.py",))[0]))


class RejectHeadCase(unittest.TestCase):
    """拒否の行の頭（reject_head）: 範囲の相談がその段に在れば、範囲の外が要る時の先の道を相談と言い、申し出は聞けない・
    許されない・out_of_scope の時の道に下げる（run 249・249b は相談の控えが在ったのに、拒否の文が申し出の道だけを言った）"""

    def test_without_ask_keeps_conflict_route(self):
        self.assertEqual(planscope.reject_head(False), planscope.REJECT)

    def test_with_ask_puts_planner_first(self):
        head = planscope.reject_head(True)
        self.assertIn("範囲の相談", head)
        self.assertLess(head.index("範囲の相談"), head.index("食い違いの申し出"))
        self.assertIn("out_of_scope", head)
        self.assertNotIn("範囲の外が要るなら変えずに食い違いの申し出で返せ", head)
        self.assertNotIn("out_of_scope に当たる物が要る時だけ", head,
                         "out_of_scope の物も先に相談する（持ち主 2026-10-07。案を書いた役が考え直す）")
        self.assertTrue(head.startswith("承認済みの修正案の項目から外れた"), "拒否の行を単位に結ぶ・見出しで探す頭の語は同じ")

if __name__ == "__main__":
    unittest.main()
