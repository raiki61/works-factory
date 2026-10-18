"""差分の審査の後の手直し（refix）の往復。元 works/tests/test_blk_refix.py の場合のうち、盤面を使わずに回る物を、置き場の
フォルダ（fix の run の作業のファイルを置く所）と引数の形に写した物。

置き場は試験ごとの一時のフォルダ。種（tests/e2e/target-seed/）を写したリポジトリで、修正役の代わり（apply_fix）と手直しの役の
代わり（apply_refix）が作業ツリーを書き換える。審査役・手直しの役の返答は元の tests/replies/ の見本を字のまま持つ。
"""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy, git  # noqa: E402
import deltamarks  # noqa: E402
import fixboard  # noqa: E402
import refix  # noqa: E402
import writes  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
K1 = "stats.py mean: 分母が len(xs) - 1 になっている"
K2 = "stats.py clamp: 上限を超えた値に lo を返す"
PR_KEY = "stats.py clamp: docstring が上限の枝の約束を書いていない"   # 事前審査の穴（修正が absorbed と答える）
F1 = "stats.py clamp: docstring が下限の枝の約束を書いていない"       # 差分の審査の穴（fix2_delta_review_faces）
F2 = "stats.py clamp: docstring が境の値の扱いを書いていない"         # 2 回目の審査の穴（fix2_delta_review2_faces）
FIXED_DOC = '    """上限を超えた値は hi を返す"""\n'
REFIXED_DOC = '    """下限を下回った値は lo を、上限を超えた値は hi を返す"""\n'
ITEMS = [{"item": n, "unit_keys": [k], "route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
          "out_of_scope": []} for n, k in ((1, K1), (2, K2))]


def plan_review_reply() -> dict:
    return {"faces": [{"key": PR_KEY, "unit_keys": [K2], "kind": "contract_drift", "where": "stats.py clamp",
                       "why": "上限の枝を直しても docstring が約束を書かないので読む側が古い想定のまま残る", "severity": "suggest"}],
            "shrink": [], "reason": "2 つの案を読み、足す物が無いことと、docstring のずれを 1 件見た"}


def fix_reply() -> dict:
    """修正役の返答のうち差分の審査の材料が読む欄（changes・not_done・plan_faces）"""
    return {"changes": [{"unit_key": K1, "what": "式を定義どおりに直した", "files": ["stats.py"]},
                        {"unit_key": K2, "what": "式を定義どおりに直した", "files": ["stats.py"]}],
            "not_done": [],
            "plan_faces": [{"key": PR_KEY, "handled": "absorbed", "how": "clamp に上限を超えた値は hi を返すと docstring を書いた"}]}


def review_faces() -> dict:
    """元 tests/replies/fix2_delta_review_faces.json"""
    return {"faces": [{"key": F1, "kind": "contract_drift", "where": "stats.py", "cite": "上限を超えた値は hi を返す",
                       "why": "修正が足した docstring は上限の枝だけを書き、下限を下回った値に lo を返す約束が読む側に見えない"}],
            "checks": [{"key": PR_KEY, "closed": False,
                        "why": "docstring は上限の枝を書いたが下限の枝を書いておらず、事前審査が言った約束のずれが片方残る"}],
            "compliance": {"verdict": "not_applicable", "items": [],
                           "read": "修正案の works の欄の控えが無い run なので、照らす承認済みの項目は無い。差分の stats.py を読んだ"},
            "quality": {"verdict": "fail", "why": "faces に挙げた穴は修正案の項目への準拠の外の品質の穴で、準拠の行には結ばない"}}


def review_none() -> dict:
    """元 tests/replies/fix2_delta_review_none.json"""
    return {"faces": [], "faces_none": "stats.py の差分 3 行と、呼び元の test_stats.py を読んだ。写し・入口・宣言とのずれは無い",
            "checks": [{"key": PR_KEY, "closed": True,
                        "why": "clamp の docstring に上限を超えた値は hi を返すと書かれ、事前審査が言った約束のずれは塞がった"}],
            "compliance": {"verdict": "not_applicable", "items": [],
                           "read": "修正案の works の欄の控えが無い run なので、照らす承認済みの項目は無い。差分の stats.py を読んだ"},
            "quality": {"verdict": "pass", "why": "差分は mean の分母と clamp の上限の枝を直すだけで、faces に挙げる穴は無い"}}


def review2_faces() -> dict:
    """元 tests/replies/fix2_delta_review2_faces.json"""
    return {"faces": [{"key": F2, "kind": "contract_drift", "where": "stats.py", "cite": "下限を下回った値は lo を",
                       "why": "docstring は 2 つの枝だけを書き、x が lo か hi に等しい境の値をそのまま返す約束が読む側に見えない"}],
            "checks": [{"key": F1, "closed": True, "why": "docstring に下限を下回った値は lo を返すと書かれ、下限の枝の約束のずれは塞がった"},
                       {"key": PR_KEY, "closed": True, "why": "docstring に上限と下限の両方の枝が書かれ、事前審査のずれは塞がった"}]}


def fix_ok() -> dict:
    """元 tests/replies/fix2_delta_fix_ok.json"""
    return {"handled": [
        {"key": F1, "handled": "fixed", "how": "clamp の docstring を下限を下回った値は lo を、上限を超えた値は hi を返すに書き直した",
         "files": ["stats.py"]},
        {"key": PR_KEY, "handled": "fixed", "how": "同じ docstring の書き直しで、上限と下限の両方の枝の約束を書いた",
         "files": ["stats.py"]}]}


def apply_fix(repo: pathlib.Path) -> None:
    """修正役の代わり: 種の 2 つのバグを直し、clamp に docstring を足す"""
    p = repo / "stats.py"
    s = p.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)")
    s = s.replace("    if x > hi:\n        return lo", "    if x > hi:\n        return hi")
    s = s.replace("def clamp(x, lo, hi):\n", "def clamp(x, lo, hi):\n" + FIXED_DOC)
    p.write_text(s, encoding="utf-8")


def apply_refix(repo: pathlib.Path) -> None:
    """手直しの役の代わり: clamp の docstring の 1 行だけを書き直す"""
    p = repo / "stats.py"
    p.write_text(p.read_text(encoding="utf-8").replace(FIXED_DOC, REFIXED_DOC), encoding="utf-8")


class DeltaPlaceCase(unittest.TestCase):
    """種の写しのリポジトリ（self.repo。run の始めの版 self.base）と、fix の run の置き場（self.place）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-refix-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.base = committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()

    def cut(self, n=1, **kw):
        kw.setdefault("plan_review", plan_review_reply())
        kw.setdefault("fix_reply", fix_reply())
        got = refix.cut(self.place, n, self.repo, self.base, **kw)
        self.assertTrue(got["ok"], got)
        return got

    def brief(self, got) -> dict:
        return json.loads(pathlib.Path(got["brief_file"]).read_text(encoding="utf-8"))

    def fixed(self, *, before_fix=None):
        """修正役が作業ツリーを直した後（before_fix(repo) は修正の後に作業ツリーへ当てる）"""
        apply_fix(self.repo)
        if before_fix:
            before_fix(self.repo)
        return self.repo

    def reviewed(self, reply=None, *, items=None, **kw):
        """1 回目の差分の審査（reply。既定は穴 1 件・塞がっていない検算 1 件）まで受けた置き場"""
        self.fixed(**kw)
        self.cut(items=items)
        got = refix.accept_review(reply or review_faces(), self.place, self.base, self.repo, n=1, items=items)
        self.assertTrue(got["ok"], got)
        return got

    def refixed(self, reply=None, *, edit=True):
        """1 回目の手直し（reply。既定は義務 2 件に fixed）まで受けた置き場。edit なら docstring の 1 行を書き直す"""
        self.reviewed()
        if edit:
            apply_refix(self.repo)
        got = refix.accept_fix(reply or fix_ok(), self.place, self.base, self.repo, n=1)
        self.assertTrue(got["ok"], got)
        return got


class RefixCase(DeltaPlaceCase):
    def test_owed_rows_come_from_the_accepted_review(self):
        """穴 1 件・塞がっていない検算 1 件の審査 → 手直しの義務は 2 件（F1 と PR_KEY）。受け付けの返りの owed も 2。
        審査の返答は 2 判定の欄を外して置き場に置く"""
        got = self.reviewed()
        self.assertEqual(got["owed"], 2)
        rows = fixboard._owed_rows(self.place, 1)
        self.assertEqual({r["key"] for r in rows}, {F1, PR_KEY})
        self.assertEqual({r["from"] for r in rows}, {"p3.delta_review", "p3.delta_review.checks"})
        took = json.loads(pathlib.Path(got["reply_file"]).read_text(encoding="utf-8"))
        self.assertNotIn("compliance", took)
        self.assertEqual(fixboard.output(self.place, "p3.delta_review"), took)

    def test_review_none_owes_nothing(self):
        got = self.reviewed(review_none())
        self.assertEqual(got["owed"], 0)
        self.assertEqual(fixboard._owed_rows(self.place, 1), [])

    def test_compliance_fail_reaches_ties(self):
        """準拠の外れを穴 F1 に結んだ審査 → 穴の枝の名札で F1 が項目 1 の枝に結ぶ（手直しの材料）"""
        self.fixed()
        self.cut(items=ITEMS)
        reply = review_faces()
        reply["compliance"] = {"verdict": "fail", "read": "修正案の項目 1 と差分の stats.py を読み、項目と差分を照らした",
                               "items": [{"item": 1, "kind": "misunderstood", "face_key": F1,
                                          "why": "brief は docstring も直すと書くが、差分は式だけを直した"}]}
        reply["quality"] = {"verdict": "pass", "why": "準拠に結ばれていない穴は無く、テストの形の問題も見当たらない"}
        got = refix.accept_review(reply, self.place, self.base, self.repo, n=1, items=ITEMS)
        self.assertTrue(got["ok"], got)
        self.assertEqual([r["face_key"] for r in deltamarks.fail_rows(deltamarks.read(self.place))], [F1])
        ties = refix.brief_ties(fixboard.hole_ties(self.place, 1, items=ITEMS, plan_review=plan_review_reply(),
                                                   fix_reply=fix_reply()))
        self.assertEqual([x["key"] for x in ties], [r["key"] for r in fixboard._owed_rows(self.place, 1)])
        self.assertIn("項目 1", {x["key"]: x["branches"] for x in ties}.get(F1) or [])

    def _scoped_refix(self, *, before_fix=None, out_of_scope=()):
        """範囲の欄の在る修正案（どの項目も stats.py だけを許す）で、1 回目の手直しの前まで進めた作業ツリーと項目"""
        items = copy.deepcopy(ITEMS)
        if out_of_scope:
            items[0]["out_of_scope"] = [{"glob": g, "why": "見本。この項目は触らない"} for g in out_of_scope]
        self.fixed(before_fix=before_fix)
        self.cut(items=items)
        reply = review_faces()
        reply["compliance"] = {"verdict": "pass", "read": "修正案の項目 1・2 と差分の stats.py を読み、項目と差分を照らした",
                               "items": []}
        reply["quality"] = {"verdict": "fail", "why": "docstring が下限の枝の約束を書いていない穴が準拠の外に残っている"}
        got = refix.accept_review(reply, self.place, self.base, self.repo, n=1, items=items)
        self.assertTrue(got["ok"], got)
        apply_refix(self.repo)
        return items

    def test_refix_outside_plan_scope_rejected(self):
        """手直しも修正の段と同じ範囲の照らし（承認済みの修正案の項目の範囲の和）。外れは拒み、返答を置き場に置かない"""
        items = self._scoped_refix()
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=items)
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(refix.SCOPE_REJECT), got["reason"])
        self.assertIn("extra.py", got["reason"])
        self.assertIn("allowed_paths", got["reason"])
        self.assertIsNone(fixboard.output(self.place, "p3.delta_fix"))

    def test_refix_out_of_scope_glob_rejected(self):
        items = self._scoped_refix(out_of_scope=["test_stats.py"])
        p = self.repo / "test_stats.py"
        p.write_text(p.read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8")
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=items)
        self.assertFalse(got["ok"], got)
        self.assertIn("out_of_scope", got["reason"])

    def test_refix_inside_plan_scope_passes(self):
        items = self._scoped_refix()
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=items)
        self.assertTrue(got["ok"], got)
        self.assertEqual(fixboard.output(self.place, "p3.delta_fix"), fix_ok())

    def test_refix_pastes_and_accepts_the_ruled_paths(self):
        """#570: 手直しの指示書の範囲の節（refix.scope_text）と受け付け（accept_fix）は、同じ引数（refix.SCOPE）で直す裁定の
        パスを許す。片方だけ裁定の前の値にすれば、貼ったパスを拒むか、許すパスを貼らない"""
        import conflict
        items = self._scoped_refix()
        conflict.park(self.place, [{"unit_key": items[0]["unit_keys"][0], "between": ["stats.py:3", "test_stats.py:2"],
                                    "why_both_cannot_hold": "テストと今のコードの両方は成り立たない",
                                    "which_is_right": "request", "kind": "brief_vs_judgment"}], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(self.place, {"c1-1": {"decision": "fix_code_as", "text": "設定のファイルも直してよい",
                                                     "limits": ["conf.ini"]}}, by="t")
        (self.repo / "conf.ini").write_text("[x]\n", encoding="utf-8")
        self.assertIn("`conf.ini`", refix.scope_text(self.place, items))
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=items)
        self.assertTrue(got["ok"], got)

    def test_refix_is_not_blamed_for_the_fix_files(self):
        """修正の段が触ったファイル（1 回目の差分の files）は手直しの照らしに入れない"""
        items = self._scoped_refix(before_fix=lambda r: (r / "fixextra.py").write_text("Y = 2\n", encoding="utf-8"))
        self.assertIn("fixextra.py", refix.fix_delta(self.place)["files"])
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=items)
        self.assertTrue(got["ok"], got)

    def test_refix_unrecorded_write_rejected_and_declared_write_passes(self):
        """手直しの変更も書き込みの記録か申告（bash_writes）が要る。どちらも無ければ拒む。申告すれば通し、欄は置く前に外す"""
        self.reviewed()
        apply_refix(self.repo)
        log = self.tmp / "writes.jsonl"
        log.write_text("", encoding="utf-8")
        got = refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, log=log)
        self.assertFalse(got["ok"], got)
        self.assertIn("bash_writes", got["reason"])
        self.assertIn("stats.py", got["reason"])
        self.assertIsNone(fixboard.output(self.place, "p3.delta_fix"))
        reply = fix_ok()
        reply["bash_writes"] = [{"path": p, "why": "整形の道具で docstring を書き直した（試験の見本）"}
                                for p in writes.changed(self.repo, "HEAD")]
        got = refix.accept_fix(reply, self.place, self.base, self.repo, n=1, log=log)
        self.assertTrue(got["ok"], got)
        self.assertNotIn("bash_writes", fixboard.output(self.place, "p3.delta_fix"))

    def test_refix_without_record_notes_the_run(self):
        """書き込みの記録の無い run は突き合わせずに通し、置き場の trace.jsonl に知らせの行を残す"""
        self.reviewed()
        apply_refix(self.repo)
        self.assertTrue(refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1)["ok"])
        rows = [json.loads(x) for x in (self.place / fixboard.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertIn({"op": writes.NO_RECORD_OP, "node": "refix", "note": writes.NO_RECORD}, rows)

    def test_refix_without_plan_scope_is_not_checked(self):
        """修正案の範囲の欄が無い run（修正案の無い run）は照らさない"""
        self.reviewed()
        apply_refix(self.repo)
        (self.repo / "extra.py").write_text("X = 1\n", encoding="utf-8")
        self.assertTrue(refix.accept_fix(fix_ok(), self.place, self.base, self.repo, n=1, items=None)["ok"])

    def test_cut2_is_refix_only_diff(self):
        """手直しで docstring の 1 行を変えた後 → cut(2) の差分は手直しの行だけ（修正の mean・clamp の行が無い）"""
        self.refixed()
        got = self.cut(2)
        self.assertEqual(got["diff_file"], fixboard.loop_value(self.place, "fix_delta2")["file"])
        self.assertEqual(got["files"], ["stats.py"])
        patch = pathlib.Path(got["diff_file"]).read_text(encoding="utf-8")
        self.assertIn("+" + REFIXED_DOC.rstrip("\n"), patch)
        self.assertIn("-" + FIXED_DOC.rstrip("\n"), patch)
        changed = [x for x in patch.splitlines() if x[:1] in "+-" and not x.startswith(("+++", "---"))]
        self.assertEqual(len(changed), 2, patch)   # 手直しの 1 行の前と後だけ
        for line in ("len(xs)", "return hi", "return lo"):
            self.assertFalse([x for x in changed if line in x], (line, patch))
        self.assertNotEqual(got["diff_file"], refix.fix_delta(self.place)["file"])
        self.assertTrue((self.place / refix.snapshot_name(2)).is_file())
        brief = self.brief(got)
        self.assertEqual([r["key"] for r in brief["reads"]["out.p3.delta_fix.handled"]], [F1, PR_KEY])
        self.assertNotIn("plan_items", brief)
        self.assertNotIn("lens", brief)

    def test_cut_leaves_out_the_runtime_copy(self):
        """差分の審査に渡す差分は、実行基盤が作業ツリーに写した置き場（除くパスの頭 skip の下）を載せない（ほかの差分の作り手と同じ）"""
        self.fixed()
        (self.repo / "runtime-copy" / "workflows").mkdir(parents=True)
        (self.repo / "runtime-copy" / "workflows" / "x.yaml").write_text("name: x\n", encoding="utf-8")
        for n in (1, 2):
            with self.subTest(n=n):
                got = self.cut(n, skip=("runtime-copy/",))
                self.assertNotIn("runtime-copy/workflows/x.yaml", got["files"])
                self.assertNotIn("runtime-copy/", pathlib.Path(got["diff_file"]).read_text(encoding="utf-8"))
        self.assertIn("stats.py", self.cut(1, skip=("runtime-copy/",))["files"])

    def test_cut2_needs_the_first_cut(self):
        self.fixed()
        got = refix.cut(self.place, 2, self.repo, self.base)
        self.assertFalse(got["ok"])
        self.assertIn("fix_delta", got["reason"])

    def test_review2_then_ties2(self):
        """2 回目の審査の穴 F2 → 2 回目の義務は 1 件。名札は 1 回目の名札と手直しの handled から引く"""
        self.refixed()
        self.cut(2)
        got = refix.accept_review(review2_faces(), self.place, self.base, self.repo, n=2)
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["owed"], 1)
        self.assertEqual([r["key"] for r in fixboard._owed_rows(self.place, 2)], [F2])
        ties = fixboard.hole_ties(self.place, 2, items=ITEMS, plan_review=plan_review_reply(), fix_reply=fix_reply())
        self.assertEqual([t["key"] for t in ties], [F2])
        self.assertEqual(deltamarks.read(self.place)["quality"]["verdict"], "fail")   # 2 判定の控えは 1 回目の審査の物のまま

    def test_inner_word_in_an_added_line_is_owed(self):
        """修正の差分が足した行に works の内側の語（この単位）が在れば、穴の無い審査を受けても義務は 1 件。run の始めの版で
        対象が既に使う語（作業ツリー）と、表の語にならない「この周辺」は義務にならない"""
        (self.repo / "notes.txt").write_text("作業ツリーの写しを取る\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "notes")
        self.base = git(self.repo, "rev-parse", "HEAD")

        def add_lines(repo):
            p = repo / "stats.py"
            p.write_text(p.read_text(encoding="utf-8") + "# この単位の分母を直した\n# 作業ツリーで確かめた\n# この周辺も読んだ\n",
                         encoding="utf-8")
        got = self.reviewed(review_none(), before_fix=add_lines)
        self.assertEqual(got["owed"], 1)
        rows = fixboard._owed_rows(self.place, 1)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["from"], "p3.delta_review")
        self.assertIn("この単位", rows[0]["text"])
        self.assertTrue(rows[0]["key"].startswith("inner_word stats.py:"), rows[0])
        for word in ("作業ツリー", "この周辺"):
            self.assertNotIn(word, rows[0]["text"].split("——", 1)[1])

    def test_inner_word_added_by_the_first_refix_is_owed_in_review2(self):
        """1 回目の手直しが足した行の内側の語（この run）は、2 回目の審査の受け付けが穴に足し、2 回目の義務に入る"""
        self.refixed()
        p = self.repo / "stats.py"
        p.write_text(p.read_text(encoding="utf-8") + "# この run で直した\n", encoding="utf-8")
        self.cut(2)
        got = refix.accept_review(review2_faces(), self.place, self.base, self.repo, n=2)
        self.assertTrue(got["ok"], got)
        keys = [r["key"] for r in fixboard._owed_rows(self.place, 2)]
        self.assertEqual(got["owed"], 2)
        self.assertEqual(keys[0], F2)
        self.assertEqual(len(keys), 2)
        self.assertTrue(keys[1].startswith("inner_word stats.py:"), keys)

    def test_no_third_pass(self):
        self.assertEqual(sorted(refix.passes()), [1, 2])
        with self.assertRaises(ValueError):
            refix._pass(3)


if __name__ == "__main__":
    unittest.main()
