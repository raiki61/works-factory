"""差分の審査（delta）の支度と受け付け。元 works/tests/test_blk_tests_delta.py の TestDeltaBoard の場合のうち、盤面を使わずに
回る物を、置き場のフォルダと引数の形に写した物（審査の材料に載せる値は呼び手が値で渡す）。最後の試験の段（TestTestsBlock・
TestTestsModes）とブロックの YAML の試験は盤面と blk-* を使うので持ってこない。
"""
import json
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin import hermetic  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402
from lib.tests import test_blk_refix as RF  # noqa: E402
import accept  # noqa: E402
import conflict  # noqa: E402
import deltamarks  # noqa: E402
import fixboard  # noqa: E402
import planmarks  # noqa: E402
import protect  # noqa: E402
import refix  # noqa: E402

POLICY = {"paste": "方針の本文", "path": "/home/x/policy.md"}


class TestDeltaPlace(RF.DeltaPlaceCase):
    def test_cut_writes_the_fix_only_diff_and_brief(self):
        """cut(1) は run の始めの版から今の作業ツリー（未追跡も）までの差分を置き場に書き、状態の loop-fix_delta.json と
        役に見せる材料（事前審査の穴と修正役の plan_faces）を brief に書き、作業ツリーの写しを撮る"""
        self.fixed()
        got = self.cut(policy=POLICY)
        d = refix.fix_delta(self.place)
        self.assertEqual((got["diff_file"], got["files"], got["rev"]), (d["file"], ["stats.py"], d["rev"]))
        self.assertEqual(d["base"], self.base)
        patch = pathlib.Path(got["diff_file"]).read_text(encoding="utf-8")
        self.assertIn("-    return sum(xs) / (len(xs) - 1)", patch)
        brief = self.brief(got)
        self.assertEqual([f["key"] for f in brief["reads"]["out.p2.plan_review"]["faces"]], [RF.PR_KEY])
        self.assertEqual([(r["key"], r["handled"]) for r in brief["reads"]["out.p3.fix.plan_faces"]], [(RF.PR_KEY, "absorbed")])
        self.assertEqual(brief["reads"]["loop.fix_delta.files"], ["stats.py"])
        self.assertEqual(got["must"], [got["brief_file"], d["file"], brief["seat_file"]])
        self.assertIn("task-reviewer-prompt.md", pathlib.Path(brief["seat_file"]).read_text(encoding="utf-8"),
                      "1 回目の審査役の座（seat.section の task-review）")
        self.assertEqual(brief["policy"], POLICY)
        snap = json.loads((self.place / refix.snapshot_name(1)).read_text(encoding="utf-8"))
        self.assertEqual(snap, accept.tree_state(self.repo))
        self.assertEqual(self.cut()["diff_file"], d["file"])   # 呼び直しても同じ置き場の名

    def test_cut_writes_the_seat_file(self):
        """1 回目の審査の支度は task-review の型を埋めた座を review1-seat.md に書き、brief の seat_file と must に名指す（型の穴は
        brief・方針・直した側の返答のファイル・切った版・差分のファイル。無い物は seat.NONE）。2 回目の審査には座が無い
        （元 works/tests/test_blk_tests_delta.py:563 の test_cut_writes_seat_file の写し）"""
        import seat
        self.fixed()
        reply = self.tmp / "fix-reply.json"
        reply.write_text(json.dumps(RF.fix_reply(), ensure_ascii=False), encoding="utf-8")
        got = self.cut(fix_reply=str(reply))
        brief = self.brief(got)
        path = pathlib.Path(brief["seat_file"])
        self.assertEqual(path, self.place / "review1-seat.md")
        self.assertIn(str(path), got["must"])
        text = path.read_text(encoding="utf-8")
        d = refix.fix_delta(self.place)
        for w in (seat.HEAD, got["brief_file"], d["file"], d["rev"], self.base, str(reply), seat.NONE,
                  seat.words_table("task-review")):
            self.assertIn(w, text)
        self.assertNotRegex(text.split(seat.skill_overlay("review").strip())[0], r"\[[A-Z][A-Z_]+\]", "型の穴が残らない")
        RF.apply_refix(self.repo)
        refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1)
        self.assertTrue(refix.accept_fix(RF.fix_ok(), self.place, self.base, self.repo, n=1)["ok"])
        got2 = self.cut(2)
        self.assertEqual(self.brief(got2)["seat_file"], "")
        self.assertFalse((self.place / "review2-seat.md").exists())
        self.assertEqual(len(got2["must"]), 2)

    def test_cut_reads_values_from_files(self):
        """審査の材料の値は、呼び手が置き場に置いたファイルのパスでも渡せる。方針が無ければ両方空"""
        self.fixed()
        pr = self.tmp / "plan-review.json"
        pr.write_text(json.dumps(RF.plan_review_reply(), ensure_ascii=False), encoding="utf-8")
        brief = self.brief(self.cut(plan_review=str(pr), fix_reply=None))
        self.assertEqual(brief["reads"]["out.p2.plan_review"], RF.plan_review_reply())
        self.assertIsNone(brief["reads"]["out.p3.fix.plan_faces"])
        self.assertEqual(brief["fix_report"], {})
        self.assertEqual(brief["policy"], {"paste": "", "path": ""})

    def test_cut_needs_the_start_rev(self):
        self.fixed()
        got = refix.cut(self.place, 1, self.repo, "")
        self.assertFalse(got["ok"])
        self.assertIn("版", got["reason"])

    def test_cut_brief_lists_protected_files(self):
        """変わったファイルのうち守りのファイルに当たる物を brief の protected_files に並べる"""
        self.fixed()
        self.assertEqual(self.brief(self.cut())["protected_files"], [])
        path = self.tmp / "protected.json"
        path.write_text(json.dumps({"rules": [{"id": "seed-core", "glob": "stats.py", "why": "種の芯"}]}), encoding="utf-8")
        with mock.patch.object(protect, "MANIFEST", path):
            brief = self.brief(self.cut())
        self.assertEqual(brief["protected_files"], [{"path": "stats.py", "id": "seed-core", "glob": "stats.py", "why": "種の芯"}])

    def test_cut_brief_lists_files_the_target_declares_protected(self):
        """対象のリポジトリが修正前の版で守ると宣言したファイルも protected_files に並ぶ（修正役が作業ツリーで宣言を消しても）"""
        (self.repo / protect.TARGET_FILE).write_text(
            json.dumps({"rules": [{"id": "core", "glob": "stats.py", "why": "対象の芯"}]}), encoding="utf-8")
        git(self.repo, "add", protect.TARGET_FILE)
        git(self.repo, "commit", "-q", "-m", "declare")
        self.base = fixboard.record_base_rev(self.place, self.repo)
        self.fixed(before_fix=lambda repo: (repo / protect.TARGET_FILE).unlink())
        rows = self.brief(self.cut())["protected_files"]
        self.assertEqual([(r["path"], r["id"]) for r in rows],
                         [(protect.TARGET_FILE, protect.TARGET_SELF["id"]), ("stats.py", protect.TARGET_ID + "core")])

    def test_cut_brief_carries_plan_items_and_fix_report(self):
        """1 回目の brief に範囲の欄の在る承認済みの修正案の項目（無ければ空）と直した側の報告（changes・not_done）"""
        self.fixed()
        brief = self.brief(self.cut())
        self.assertEqual(brief["plan_items"], [])
        self.assertEqual(set(brief["fix_report"]), {"changes", "not_done"})
        self.assertEqual([c["unit_key"] for c in brief["fix_report"]["changes"]], [RF.K1, RF.K2])
        brief = self.brief(self.cut(items=RF.ITEMS))
        self.assertEqual((brief["plan_items"][0]["item"], brief["plan_items"][0]["allowed_paths"]), (1, ["stats.py"]))
        self.assertEqual(brief["plan_items"][0]["unit_keys"], [RF.K1])
        unscoped = [{k: v for k, v in it.items() if k not in ("allowed_paths", "out_of_scope")} for it in RF.ITEMS]
        self.assertEqual(self.brief(self.cut(items=unscoped))["plan_items"], [])   # 範囲の欄の無い控えは修正案の無い run と同じ

    def held_place(self):
        """裁定 2 件（項目 2 の単位 K2 に fix_plan_item、K1 に fix_code_as と範囲 test_stats.py:3）を置き場に置く"""
        self.fixed()
        base = {"between": ["stats.py:3", "test_stats.py:2"], "why_both_cannot_hold": "テストと依頼が両方は成り立たない",
                "which_is_right": "request", "kind": "scope_needed", "round": 1, "source": "fix", "status": "ruled"}
        rows = [{**base, "id": "c1-1", "unit_key": RF.K2,
                 "ruling": {"decision": "fix_plan_item", "text": "案の項目 2 の範囲が誤り", "limits": [], "by": "x",
                            conflict.PLAN_ITEMS: [2], conflict.PLAN_UNITS: [RF.K2]},
                 conflict.REPLAN_STATE: conflict.WAITING},
                {**base, "id": "c1-2", "unit_key": RF.K1,
                 "ruling": {"decision": "fix_code_as", "text": "式を定義どおりに直す", "limits": ["test_stats.py:3"], "by": "x"}}]
        (self.place / conflict.FILE).write_text(json.dumps({"items": rows}, ensure_ascii=False), encoding="utf-8")

    def test_cut_brief_marks_held_items_and_ruled_paths(self):
        """裁定で外れた項目は番号を保ったまま held を持ち、直す裁定の limits のパスは ruled_paths に並ぶ"""
        self.held_place()
        brief = self.brief(self.cut(items=RF.ITEMS))
        self.assertEqual([it["item"] for it in brief["plan_items"]], [1, 2])
        self.assertNotIn("held", brief["plan_items"][0])
        self.assertIn("fix_plan_item の裁定 c1-1", brief["plan_items"][1]["held"])
        self.assertEqual(brief["ruled_paths"], ["test_stats.py"])
        self.assertNotIn("held", RF.ITEMS[1])   # 渡した値は書き換えない

    def test_missing_on_held_item_is_rejected(self):
        """審査役が外れた項目 2 を missing と書いて穴に結ぶ → 受け付けが拒み、返答を置き場に置かない"""
        self.held_place()
        self.cut(items=RF.ITEMS)
        reply = RF.review_faces()
        reply["compliance"] = {"verdict": "fail", "read": "修正案の項目 2 と差分の stats.py を読み、項目と差分を照らした",
                               "items": [{"item": 2, "kind": "missing", "face_key": RF.F1,
                                          "why": "項目 2 の clamp の直しが差分に無いので、項目どおりに直していない"}]}
        reply["quality"] = {"verdict": "pass", "why": "準拠に結ばれていない穴は無く、テストの形の問題も見当たらない"}
        got = refix.accept_review(reply, self.place, self.base, self.repo, n=1, items=RF.ITEMS)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(deltamarks.REJECT), got["reason"])
        self.assertIn("held", got["reason"])
        self.assertIsNone(fixboard.output(self.place, "p3.delta_review"))

    def test_accept_review_strips_and_saves_verdicts(self):
        """修正案の欄が無い run（not_applicable）: 2 判定の欄を外した返答を置き場に置き、欄は控え delta-verdicts.json に置く"""
        self.fixed()
        self.cut()
        self.assertTrue(refix.accept_review(RF.review_faces(), self.place, self.base, self.repo, n=1)["ok"])
        self.assertNotIn("compliance", fixboard.output(self.place, "p3.delta_review"))
        self.assertEqual(deltamarks.read(self.place)["compliance"]["verdict"], "not_applicable")

    def test_accept_review_rejects_missing_verdicts(self):
        """2 判定の欄が欠けた返答 → 拒否の文の頭は deltamarks.REJECT、置き場は前のまま"""
        self.fixed()
        self.cut()
        reply = RF.review_none()
        del reply["quality"]
        got = refix.accept_review(reply, self.place, self.base, self.repo, n=1)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(deltamarks.REJECT), got["reason"])
        self.assertIsNone(fixboard.output(self.place, "p3.delta_review"))
        self.assertIsNone(deltamarks.read(self.place))

    def test_old_plan_fields_accept_not_applicable(self):
        """範囲の欄が無い項目は範囲の無い run と同じ: not_applicable を受ける。範囲の在る項目では拒む"""
        self.fixed()
        self.cut()
        got = refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1, items=RF.ITEMS)
        self.assertFalse(got["ok"])
        self.assertIn("compliance.verdict（not_applicable）", got["reason"])
        unscoped = [{k: v for k, v in it.items() if k not in ("allowed_paths", "out_of_scope")} for it in RF.ITEMS]
        got = refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1, items=unscoped)
        self.assertTrue(got["ok"], got)

    def test_broken_plan_fields_name_the_stage(self):
        """承認済みの項目を返す口が凍結の印との食い違いを出す → 差分の審査の段の文の ValueError（照らしを黙って緩めない）"""
        self.fixed()
        self.cut()

        def broken():
            raise planmarks.FieldsBroken(f"{planmarks.FIELDS_FILE} が読めない")
        with self.assertRaises(ValueError) as cm:
            refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1, items=broken)
        self.assertTrue(str(cm.exception).startswith(conflict.FIELDS_TAMPERED), cm.exception)
        self.assertIn(planmarks.FIELDS_FILE, str(cm.exception))

    def test_unsaved_verdicts_raise(self):
        """審査を受けた後で 2 判定の控えを置けない → 控えを名指す ValueError（控えの無いまま先へ進ませない）"""
        self.fixed()
        self.cut()
        (self.place / deltamarks.VERDICTS_FILE).mkdir()
        with self.assertRaises(ValueError) as cm:
            refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1)
        self.assertIn(deltamarks.VERDICTS_FILE, str(cm.exception))

    def test_review_readonly_tree_changed(self):
        """写しの後に作業ツリーを変える → 拒む（読むだけの役が作業ツリーを変えた）。戻せば通る"""
        self.fixed()
        self.cut()
        (self.repo / "stray.txt").write_text("審査役が書いた\n", encoding="utf-8")
        got = refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1)
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(fixboard.READONLY_MOVED), got["reason"])
        (self.repo / "stray.txt").unlink()
        self.assertTrue(refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1)["ok"])

    def test_accept_review_needs_the_snapshot(self):
        self.fixed()
        with self.assertRaises(ValueError):
            refix.accept_review(RF.review_none(), self.place, self.base, self.repo, n=1)

    def test_cut_removes_stale_outputs(self):
        """新しい審査の前に、前の試みの自分の出力（brief・2 判定の控え・受けた返答）を消す"""
        self.fixed()
        stale = {"faces": [{"key": f"前の審査の穴 {i}"} for i in range(5)], "checks": []}
        planted = [self.place / "review1-brief.json", self.place / deltamarks.VERDICTS_FILE,
                   fixboard.out_file(self.place, "p3.delta_review")]
        for p in planted:
            p.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
        got = self.cut()
        self.assertEqual([p for p in planted if p.exists() and str(p) != got["brief_file"]], [])
        self.assertNotIn("前の審査の穴", pathlib.Path(got["brief_file"]).read_text(encoding="utf-8"))
        self.assertEqual(fixboard._owed_rows(self.place, 1), [])

    def test_cut_untracked_japanese_bytecode(self):
        """修正が足した未追跡のファイルと日本語の名前も差分と files にそのままの名前で載る。テストが作ったバイトコード
        （種の .gitignore が無視する）は載らない"""
        def extra(repo):
            (repo / "日本.py").write_text("def 日付():\n    return 1\n", encoding="utf-8")
            git(repo, "add", "日本.py")
            (repo / "未追跡.py").write_text("x = 1\n", encoding="utf-8")
            env = {k: v for k, v in hermetic.child_env().items() if k != "PYTHONDONTWRITEBYTECODE"}
            subprocess.run([sys.executable, "-m", "unittest", "-q", "test_stats"], cwd=str(repo), env=env,
                           capture_output=True, stdin=subprocess.DEVNULL)
            self.assertTrue(list(repo.rglob("*.pyc")))
        self.fixed(before_fix=extra)
        got = self.cut()
        self.assertTrue({"stats.py", "日本.py", "未追跡.py"} <= set(got["files"]), got["files"])
        self.assertFalse([f for f in got["files"] if f.endswith(".pyc") or "__pycache__" in f], got["files"])
        patch = pathlib.Path(got["diff_file"]).read_text(encoding="utf-8", errors="replace")
        self.assertIn("+x = 1", patch)
        self.assertIn("+def 日付():", patch)
        self.assertNotIn(".pyc", patch)


if __name__ == "__main__":
    unittest.main()
