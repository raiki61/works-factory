"""修正の block（workflows/fix/）の組の合わせ: src/clash.py（lib/clash.py の写し）と、合わせの申し出・裁定の語（conflict.JOIN_SOURCE・
conflict.REJUDGE。持ち主の決め clash-goes-to-ruling）と、join から裁定の後の合わせのループまで script を順に起こす筋書き
（docs/design/fix.md の 14.2 の test_clash.py）。

今の lib/tests/test_clash.py と tests/workflows/test_fix.py の ClashScenarioCase を写した。役の手は試験がファイルを書いて模す。
指示は prompt_file の代わりに返りの prompt の字で見る。返す node は今の collect の代わりに finish（全体の形の intake の後）。
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests.bin.gitkit import committed_copy
from tests.blocks.fix import test_join as joinkit
from tests.blocks.fix.test_join import Whole, result, write

import conflict  # noqa: E402  （lib。test_join の kit.load の後に届く）


def src():
    """fix の src を読み直して (board, clash, ruling, tdd) を返す"""
    joinkit.load_src()
    from src import clash, ruling, tdd
    return joinkit.board, clash, ruling, tdd


def write_rulings(place):
    joinkit.load_src()
    from src import rulings
    rulings.write(place)


WHY = "組 g2 の直しを親の作業ツリーで前の組と合わせると試験が赤"


class Place(unittest.TestCase):
    def setUp(self):
        self.board, self.clash, self.ruling, self.tdd = src()
        self.place = pathlib.Path(tempfile.mkdtemp(prefix="works-clash-"))
        self.addCleanup(shutil.rmtree, self.place, True)

    def parked(self, units=("B", "C")) -> list:
        return conflict.park(self.place, conflict.clash_claims(list(units), ["e.py:1"], WHY), source=conflict.JOIN_SOURCE)


class ClashClaimsCase(Place):
    def test_one_claim_per_unit_with_machine_values(self):
        rows = conflict.clash_claims(["B", "C"], ["e.py:1", "b.py:4"], WHY)
        self.assertEqual([r["unit_key"] for r in rows], ["B", "C"])
        self.assertEqual({(r[conflict.KIND_FIELD], r[conflict.WHICH_FIELD]) for r in rows}, {(conflict.NEEDS_CONTEXT, conflict.UNKNOWN)})

    def test_patch_marks_the_fix_as_kept_in_the_patch(self):
        ids = self.parked()
        conflict.mark_clash_patch(self.place, ids, "/p/join/g2.diff")
        conflict.apply_rulings(self.place, {i: {"decision": conflict.ASK, "text": "人が決める", "limits": []} for i in ids}, by="t")
        rows = conflict.asked(self.place)
        self.assertEqual(conflict.place_words(rows), conflict.FIX_REVERTED.format(patch="/p/join/g2.diff"))

    def test_rulings_file_tells_the_ruled_fixer_not_to_fix_clash_units(self):
        [rid] = self.parked(["B"])
        conflict.apply_rulings(self.place, {rid: {"decision": "fix_code_as", "text": "b.py をこう直す", "limits": []}}, by="t")
        write_rulings(self.place)
        self.assertIn("A ruling to fix, on a claim from the join between groups", (self.place / conflict.RULINGS_FILE).read_text(encoding="utf-8"))


class RejudgeCase(Place):
    def test_rejudge_holds_the_unit_without_asking_a_human(self):
        [rid] = self.parked(["B"])
        conflict.apply_rulings(self.place, {rid: {"decision": conflict.REJUDGE, "text": "B と A は 1 つの問題", "limits": []}}, by="t")
        self.assertIn("B", conflict.held_by_rulings(self.place))
        self.assertEqual(conflict.asked(self.place), [])
        self.assertEqual(conflict.human_lines(self.place), [])
        self.assertEqual(conflict.rejudge_texts(conflict.items(self.place)), ["B と A は 1 つの問題"])
        self.assertEqual(conflict.counts(self.place)[conflict.REJUDGE], 1)

    def test_counts_omit_rejudge_when_none_was_ruled(self):
        self.assertNotIn(conflict.REJUDGE, conflict.counts_of([]))


class RulingProblemsCase(unittest.TestCase):
    """裁定役の返答の照らし（src/ruling.problems）の合わせの申し出の決まり"""
    TODO = {"c1-1": {"id": "c1-1", "unit_key": "B", "source": conflict.JOIN_SOURCE, conflict.WHY_FIELD: WHY},
            "c1-2": {"id": "c1-2", "unit_key": "C", "source": conflict.JOIN_SOURCE, conflict.WHY_FIELD: WHY},
            "c1-3": {"id": "c1-3", "unit_key": "D", "source": conflict.FIX_SOURCE, conflict.WHY_FIELD: "別の申し出の理由"}}

    def setUp(self):
        _, _, self.ruling, _ = src()

    def problems(self, *rows):
        todo = {r["id"]: self.TODO[r["id"]] for r in rows}
        return self.ruling.problems({"rulings": list(rows)}, todo, "/nonexistent")

    def ruled(self, rid, decision, limits=()):
        return {"id": rid, "decision": decision, "text": "裁きの理由の文", "limits": list(limits)}

    def test_rejudge_only_for_clash_claims(self):
        self.assertEqual(self.problems(self.ruled("c1-1", conflict.REJUDGE), self.ruled("c1-2", conflict.REJUDGE)), [])
        got = self.problems(self.ruled("c1-3", conflict.REJUDGE))
        self.assertTrue(any(conflict.JOIN_SOURCE in e for e in got), got)

    def test_rejudge_has_no_limits(self):
        got = self.problems(self.ruled("c1-1", conflict.REJUDGE, ["b.py"]), self.ruled("c1-2", conflict.REJUDGE))
        self.assertTrue(any("範囲を持たない" in e for e in got), got)

    def test_replace_query_is_refused_for_clash_claims(self):
        """合わせの申し出の which_is_right は機械が unknown に埋めるので、問いの置き換えは裁けない（決まり principles の 8）"""
        [claim] = conflict.clash_claims(["B"], ["e.py:1"], WHY)
        query = {"how": {}, "counts": "defects", "hits": ["x"], "misses": []}
        got = self.ruling.problems({"rulings": [{**self.ruled("c1-1", conflict.REPLACE), "query": query}]},
                                   {"c1-1": {**claim, "id": "c1-1", "source": conflict.JOIN_SOURCE}}, "/nonexistent")
        self.assertTrue(any(f"which_is_right が {conflict.QUERY} の申し出だけ" in e for e in got), got)

    def test_rows_of_one_group_share_one_ruling(self):
        got = self.problems(self.ruled("c1-1", conflict.REJUDGE), self.ruled("c1-2", conflict.ASK))
        self.assertTrue(any("同じ組の合わせの申し出" in e for e in got), got)


class CitesCase(unittest.TestCase):
    def test_first_hunk_new_side_line_per_file(self):
        _, clash, _, _ = src()
        patch = ("diff --git a/e.py b/e.py\n--- a/e.py\n+++ b/e.py\n@@ -11,1 +12,1 @@\n-E8 = 8\n+E8 = 80\n@@ -20 +30 @@\n"
                 "diff --git a/n.py b/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/n.py\n@@ -0,0 +1 @@\n+N = 1\n")
        self.assertEqual(clash.cites(patch, ["e.py", "n.py", "x.py"]), ["e.py:12", "n.py:1", "x.py:1"])


class StageCase(Place):
    def test_patch_that_does_not_apply_leaves_the_tree_alone(self):
        repo = self.place / "repo"
        committed_copy(repo, joinkit.SEED)
        tree = self.tdd.snapshot(repo)
        patch = self.place / "join" / "g2.diff"
        patch.parent.mkdir()
        patch.write_text("diff --git a/stats.py b/stats.py\n--- a/stats.py\n+++ b/stats.py\n@@ -1,1 +1,1 @@\n-nothing like this\n+X\n",
                         encoding="utf-8")
        out_dir = self.place / "groups"
        self.board.write_json(self.place / self.board.GROUPS_FILE, {"groups": [], "out_dir": str(out_dir)})
        self.board.write_json(out_dir / "g2" / self.board.RESULT_FILE, {"end_tree": tree, "verified": []})
        self.clash.record(self.place, [{"group_id": "g2", "unit_ids": ["B"], "patch": str(patch), "names": ["stats.py"],
                                        "shared": [], "why": WHY}])
        ok, why = self.clash.stage(self.place, repo, "g2", self.clash.FIRST)
        self.assertFalse(ok)
        self.assertIn("当たらない", why)
        self.assertEqual(self.tdd.snapshot(repo), tree)
        self.assertEqual(self.clash.todo(self.place, self.clash.FIRST), ["g2"], "当たらなかった組はまだ直し待ち（呼び手が申し出へ回す）")


class ClashScenarioCase(Whole):
    """#382（持ち主の決め clash-goes-to-ruling）の筋書き: 2 つの組を並べて直し、親の木で合わせると後の組 g2 の名指しが赤になる
    （g1 が e.py の E1 を変え、g2 の b.py が前の E1 を当てにする）。join・合わせのループ・申し出の照らし・裁定の輪・裁定の後の
    合わせのループの script を順に起こし、役の手は試験がファイルを書いて模す"""

    FILLER = "".join(f"# {i}\n" for i in range(10))
    FIXED_B = "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 10\n"
    TEST_B = ("import unittest\n\nfrom b import triple\n\n\nclass TestB(unittest.TestCase):\n"
              "    def test_triple(self):\n        self.assertEqual(triple(2), 6)\n")

    def setUp(self):
        super().setUp()
        self.board, self.clash, _, _ = src()

    def judgment(self):
        write(self.place / "judgment.json", {"units": [{"key": "A", "label": "block"}, {"key": "B", "label": "block"}],
                                             "questions": []})

    def joined_with_clash(self, g2_extra=None, g2_result=None, *, test_b=None, suite_text=None):
        """種を組んで join を回し、g2 を赤で戻して直し待ちに控えた所まで進める（test_b は種の test_b.py、suite_text は実行器）"""
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{self.FILLER}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": test_b or self.TEST_B}, suite_text=suite_text)
        self.judgment()
        t1 = self.tree_with({"e.py": f"E1 = 10\n{self.FILLER}E8 = 8\n"})
        t2 = self.tree_with({"e.py": f"E1 = 1\n{self.FILLER}E8 = 80\n",
                             "b.py": "from e import E1\n\n\ndef triple(x):\n    return x * 3 + E1 - 1\n", **(g2_extra or {})})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"],
                                                     **(g2_result or {})))
        code, out, err = self.go("join")
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 1}), err)
        self.green_tree = self.snapshot()

    def prep(self, pass_="first"):
        code, out, err = self.go("clash_prep", **{"pass": pass_})
        self.assertEqual(code, 0, err)
        return out

    def accept(self, reply, iteration, pass_="first"):
        raw = "null" if reply is None else json.dumps(reply, ensure_ascii=False)
        code, out, err = self.go("clash_accept", reply=raw, iteration=str(iteration), limit="9", **{"pass": pass_})
        self.assertEqual(code, 0, err)
        return out

    def fixed_reply(self, files=("b.py",)):
        return {"handled": "fixed", "how": "b.py の triple が前の組の E1 = 10 でも 6 を返すように直し、test_triple を回して緑",
                "files": list(files)}

    def group_row(self, gid="g2"):
        return next(g for g in self.joined()["groups"] if g["group_id"] == gid)

    def to_ruling(self, decision="fix_code_as"):
        """1 回目の合わせ役が直せないと答え、申し出が裁定役に届いて decision で裁かれるまで進める。申し出の id を返す"""
        self.joined_with_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        got = self.accept({"handled": "cannot", "how": "b.py だけでは前の組の E1 と両立させる直し方が決められない", "files": []},
                          out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, True), got)
        self.assertEqual(self.snapshot(), self.green_tree, "直せなかった組は当て直す前の緑の木へ戻す")
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        self.assertEqual(self.group_row()["clash"]["outcome"], "parked")
        code, out, err = self.go("conflict_check")
        self.assertEqual((code, out), (0, {"go": True, "count": 1}), err)
        code, out, err = self.go("rule_prep")
        self.assertEqual(code, 0, err)
        self.assertIn(rows[0]["id"], out["prompt"])
        ruled = {"rulings": [{"id": rows[0]["id"], "decision": decision, "limits": [],
                              "text": "b.py の triple を、前の組が変えた E1 = 10 の上でも triple(2) が 6 になるように直せ",
                              **({"ask_why": {"changes": "direction", "line": "E1 と triple のどちらを正とするかで直しの向きが変わる"}}
                                 if decision == conflict.ASK else {})}]}
        code, out, err = self.go("rule_accept", reply=json.dumps(ruled, ensure_ascii=False), iteration="1")
        self.assertEqual((code, out["ok"]), (0, True), (err, out))
        return rows[0]["id"]

    def test_join_clash_repaired_inside_the_groups_files(self):
        """閉じる条件 1: 組を当てて赤になった run で、合わせ役が影響したファイルだけを直し、緑で進む"""
        self.joined_with_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        self.assertIn("E8 = 80", (self.repo / "e.py").read_text(encoding="utf-8"), "控えの差分を当て直した")
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["files"], brief["named_tests"]), (["b.py", "e.py"], ["test_b.py::TestB::test_triple"]))
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["reason"], g2["clash"]["outcome"]), (True, "", "repaired"), g2)
        self.assertEqual({u["unit_id"]: u["status"] for u in self.joined()["units"]}, {"A": "fixed", "B": "fixed"})
        e = (self.repo / "e.py").read_text(encoding="utf-8")
        self.assertIn("E1 = 10\n", e, "前の組の直しは残る")
        self.assertIn("E8 = 80\n", e, "後の組の直しも残る")
        code, out, err = self.go("conflict_check")
        self.assertEqual((code, out), (0, {"go": False, "count": 0}), err)

    def test_join_clash_repaired_with_an_uncompared_red_asks_a_human(self):
        """#855: 合わせ役の受け付けの確かめ直しも、組を当てるノードと同じに直す前の版と比べられなかった赤（実行器が名指しを聞かず、
        直す前の版で走らせても結末に出ない test_env）を戻す理由にしない。組は戻せた組になり、組の行の uncompared に名指す（報告が
        人に聞く）。名指しの赤は今どおり拒む"""
        from tests.blocks.fix.support import DIFF_SUITE
        env = self.TEST_B + "\n    def test_env(self):\n        import no_such_module_855  # noqa: F401\n"
        self.joined_with_clash(test_b=env, suite_text=DIFF_SUITE.replace("{heed}", "False"))
        out = self.prep()
        self.assertTrue(out["go"], out)
        got = self.accept(self.fixed_reply(), out["iteration"])
        self.assertFalse(got["ok"], "名指しの test_triple が赤のままなら拒む")
        self.assertIn("test_triple", got["reason"])
        out = self.prep()
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"]), (True, "repaired"), g2)
        self.assertEqual(g2["uncompared"], ["test_b.TestB::test_env"], g2)

    def test_join_clash_repaired_carries_the_childs_agreed_scope(self):
        """合わせ役の直しが通って戻せた組になった組の子の place の allow の相談の行は、親の conflict.agreed に group_id つきで
        1 行だけ出る（deny の行は写さない）。join で赤のまま戻した間は、まだ届いていない"""
        child = self.tmp / "child-g2"
        row = {"id": 3, "item": "2", "status": "answered", "decision": "allow", "origin": "",
               "granted_paths": ["c.py"], "granted_tests": [], "granted_new_tests": [], "reason": "b.py の直しに c.py が要る"}
        self.board.trace(child, conflict.ASKED_OP, **row)
        self.board.trace(child, conflict.ASKED_OP, **{**row, "id": 4, "decision": "deny", "granted_paths": []})
        self.joined_with_clash(g2_result={"place": str(child)})
        self.assertEqual(conflict.agreed(self.place), [], "戻した組の合意はまだ親に無い")
        out = self.prep()
        self.assertTrue(out["go"], out)
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        self.assertEqual([(r["id"], r["group_id"], r["granted_paths"]) for r in conflict.agreed(self.place)], [(3, "g2", ["c.py"])])
        self.assertEqual(conflict.plan_asks(self.place), [], "写した行は親が自分で聞いた行ではない")

    def joined_with_text_clash(self, seed=None, g1=None, g2=None):
        """種を組んで join を回し、g1 と同じ行（e.py の E1）を別の値に変えた g2 を字で当たらない組として控えた所まで進める"""
        start = self.rerun_seed({
            "e.py": f"E1 = 1\n{self.FILLER}E8 = 8\n",
            "b.py": "def triple(x):\n    return x * 3 + 1\n",
            "test_b.py": self.TEST_B, **(seed or {})})
        self.judgment()
        t1 = self.tree_with({"e.py": f"E1 = 10\n{self.FILLER}E8 = 8\n", **(g1 or {})})
        t2 = self.tree_with({"e.py": f"E1 = 1  # B が読む\n{self.FILLER}E8 = 8\n",
                             "b.py": "def triple(x):\n    return x * 3\n", **(g2 or {})})
        out_dir = self.groups_file([{"group_id": "g1", "unit_ids": ["A"], "items": [1]},
                                    {"group_id": "g2", "unit_ids": ["B"], "items": [2]}], start)
        write(out_dir / "g1" / "result.json", result("g1", ["A"], t1, start))
        write(out_dir / "g2" / "result.json", result("g2", ["B"], t2, start, verified=["test_b.py::TestB::test_triple"]))
        code, out, err = self.go("join")
        self.assertEqual((code, out), (0, {"groups": 2, "returned": 1}), err)
        self.green_tree = self.snapshot()

    def test_join_text_clash_is_redone_on_the_current_tree(self):
        """#598: 2 つの組が同じ行を別の値に変えて後の組が字で当たらなくても、単位を落とさない。合わせのループが後の組を親の今の
        木へ食い違いの印つきで当て直し、印を残した返答は拒み、印を解いた返答で両方の組の直しが残る"""
        self.joined_with_text_clash()
        out = self.prep()
        self.assertTrue(out["go"], out)
        e = self.repo / "e.py"
        self.assertIn("<<<<<<< ", e.read_text(encoding="utf-8"))
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3\n")
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual((brief["kind"], brief["conflicted"]), ("text", ["e.py"]))
        got = self.accept(self.fixed_reply(("e.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("食い違いの印", got["reason"])
        out = self.prep()
        e.write_text(f"E1 = 10  # B が読む\n{self.FILLER}E8 = 8\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("e.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"]), (True, "repaired"), g2)
        self.assertEqual({u["unit_id"]: u["status"] for u in self.joined()["units"]}, {"A": "fixed", "B": "fixed"})
        self.assertIn("E1 = 10  # B が読む\n", e.read_text(encoding="utf-8"))
        self.assertEqual((self.repo / "b.py").read_text(encoding="utf-8"), "def triple(x):\n    return x * 3\n")

    def test_join_text_clash_rejects_a_left_separator_in_a_document(self):
        """文書のファイル d.md（setext の見出しの下線 ======= を持つ）で、g1 と g2 が本文の同じ行を変えて印が書かれた後:
        (1) 名の付く 3 つの印の行と base の行だけを消し、区切りと両側の本文を残した返答は UNRESOLVED で拒まれ、拒みの文に
        長さの違う下線で書く道が添えられる。(2) 印を全部解いて g2 の見出しと下線を採った返答は通る"""
        seed = "Title\n=======\nbody\n"
        self.joined_with_text_clash(seed={"d.md": seed}, g1={"d.md": "Title\n=======\ng1 body\n"},
                                    g2={"d.md": "Title\n=======\nSub\n=======\n"})
        out = self.prep()
        self.assertTrue(out["go"], out)
        d, e = self.repo / "d.md", self.repo / "e.py"
        marked = d.read_text(encoding="utf-8")
        self.assertIn("<<<<<<<< ", marked)
        self.assertIn("g1 body\n", marked)
        e.write_text(f"E1 = 10  # B が読む\n{self.FILLER}E8 = 8\n", encoding="utf-8")
        d.write_text("Title\n=======\ng1 body\n========\nSub\n=======\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("e.py", "d.md")), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("食い違いの印", got["reason"])
        self.assertIn("d.md（8 字）", got["reason"])
        self.assertIn("an underline whose length differs from the markers", (pathlib.Path(__file__).resolve().parents[3] / "workflows" / "fix" / "prompts" / "parts" / "clash.md").read_text(encoding="utf-8"))
        out = self.prep()
        d.write_text("Title\n=======\nSub\n=======\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("e.py", "d.md")), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (True, True), got)

    def test_join_text_clash_brief_carries_each_file_marker_and_the_rule(self):
        """setext の 7 字の下線を持つ d.md と、= の行の無い e.py が字で当たらずに印つきで当て直された時、brief はファイルごとの
        印の 4 つの頭（d.md は 8 字・e.py は 7 字）を載せ（拒みの決まりは md が持つ）、clash.json の行の marked はパス→印の長さを持つ"""
        self.joined_with_text_clash(seed={"d.md": "Title\n=======\nbody\n"}, g1={"d.md": "Title\n=======\ng1 body\n"},
                                    g2={"d.md": "Title\n=======\nSub\n=======\n"})
        out = self.prep()
        self.assertTrue(out["go"], out)
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual(brief["conflicted"], ["d.md", "e.py"])
        self.assertEqual(brief["markers"], {"d.md": ["<" * 8, "|" * 8, "=" * 8, ">" * 8],
                                            "e.py": ["<" * 7, "|" * 7, "=" * 7, ">" * 7]})
        self.assertNotIn("marker_rule", brief)
        [row] = self.clash.load(self.place)
        self.assertEqual(row["marked"], {"d.md": 8, "e.py": 7})

    def test_join_text_clash_the_role_cannot_fix_reaches_ruling_as_a_text_clash(self):
        """字で当たらない組を合わせ役が直せないと答えると、申し出は字の食い違いとして裁定役に届く（赤の文の申し出と言わない）"""
        self.joined_with_text_clash()
        out = self.prep()
        got = self.accept({"handled": "cannot", "how": "E1 をどちらの値にするか決められない", "files": []}, out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, True), got)
        self.assertEqual(self.snapshot(), self.green_tree, "直せなかった組は印つきで当て直す前の木へ戻す")
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        said = rows[0][conflict.WHY_FIELD]
        self.assertIn("前の組の直しと同じ所を変え、字で当たらない", said)
        self.assertNotIn("試験が赤", said)

    def test_join_text_clash_marking_a_locked_test_file_goes_to_ruling_at_once(self):
        """字で当たらない所が許しの無いテストのファイルに在れば、合わせ役を起こさずに、そのファイルを名指して裁定役へ回す"""
        test_e = "import unittest\n\n\nclass TestE(unittest.TestCase):\n    def test_e(self):\n        pass  # E\n"
        self.joined_with_text_clash(seed={"test_e.py": test_e}, g1={"test_e.py": test_e.replace("# E", "# g1")},
                                    g2={"test_e.py": test_e.replace("# E", "# g2")})
        out = self.prep()
        self.assertFalse(out["go"], out)
        self.assertEqual(self.snapshot(), self.green_tree)
        rows = [r for r in conflict.items(self.place) if r["source"] == conflict.JOIN_SOURCE]
        self.assertEqual([r["unit_key"] for r in rows], ["B"], rows)
        self.assertIn("許しの無いテストのファイルに在り", rows[0][conflict.WHY_FIELD])
        self.assertIn("test_e.py", rows[0][conflict.WHY_FIELD])
        self.assertEqual(self.group_row()["clash"]["outcome"], "parked")

    def test_join_clash_rejects_writes_outside_the_group_and_test_rewrites(self):
        """受け付けは修正役と同じ軸: 組が変えたファイルの外の変更と、許しの無いテストのファイルの書き換えを拒む"""
        self.joined_with_clash()
        out = self.prep()
        (self.repo / "x.py").write_text("X = 1\n", encoding="utf-8")
        got = self.accept(self.fixed_reply(("x.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("組が変えたファイルの外", got["reason"])
        (self.repo / "x.py").unlink()
        test_b = self.repo / "test_b.py"
        test_b.write_text(test_b.read_text(encoding="utf-8").replace("6)", "15)"), encoding="utf-8")
        out = self.prep()
        self.assertEqual(out["iteration"], 2)
        self.assertIn("## Why your previous answer was rejected", out["prompt"], "指示の却下の段落（md は英語）")
        self.assertIn("組が変えたファイルの外", out["prompt"], "前の回の拒否の理由を渡す")
        got = self.accept(self.fixed_reply(("test_b.py",)), out["iteration"])
        self.assertFalse(got["ok"], got)
        self.assertIn("許しの無いテストのファイル", got["reason"])
        self.assertIn("test_b.py", got["reason"])

    def test_join_clash_rejects_rewriting_the_groups_own_test(self):
        """組が自分で変えたテストのファイルも、許しが無ければ合わせ役は書き換えられない"""
        self.joined_with_clash({"test_b.py": self.TEST_B + "\n    def test_triple_zero(self):\n        triple(0)\n"})
        out = self.prep()
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertIn("test_b.py", brief["files"])
        test_b = self.repo / "test_b.py"
        test_b.write_text(test_b.read_text(encoding="utf-8").replace("6)", "15)"), encoding="utf-8")
        got = self.accept(self.fixed_reply(("test_b.py",)), out["iteration"])
        self.assertEqual((got["ok"], got["done"]), (False, False), got)
        self.assertIn("許しの無いテストのファイル", got["reason"])
        self.assertIn("test_b.py", got["reason"])
        self.assertNotIn("組が変えたファイルの外", got["reason"])

    def test_join_clash_goes_to_ruling_and_the_ruling_fixes_it(self):
        """閉じる条件 2: 直せない形では、申し出が裁定役に届き、裁定の答えで解ける"""
        rid = self.to_ruling()
        out = self.prep("ruled")
        self.assertTrue(out["go"], out)
        brief = json.loads((self.place / "clash-brief-g2.json").read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in brief["rulings"]], [rid])
        write_rulings(self.place)
        self.assertIn("A ruling to fix, on a claim from the join between groups", (self.place / conflict.RULINGS_FILE).read_text(encoding="utf-8"))
        (self.repo / "b.py").write_text(self.FIXED_B, encoding="utf-8")
        got = self.accept(self.fixed_reply(), out["iteration"], "ruled")
        self.assertEqual((got["ok"], got["done"]), (True, True), got)
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"], g2["clash"]["requests"]), (True, "repaired", [rid]), g2)
        code, out, err = self.go("fix_ruled_prep")
        self.assertEqual((code, out["go"]), (0, False), ("合わせの申し出への直す裁定は裁定の後の修正役を起こさない", err))
        self.assertEqual(conflict.human_lines(self.place), [])

    def test_join_clash_reaches_a_human_only_when_the_ruling_cannot_fix_it(self):
        """閉じる条件 3: 裁定でも解けない形だけ、人に回る（裁定の後の合わせ役が 3 回拒まれる）"""
        rid = self.to_ruling()
        for n in (1, 2, 3):
            out = self.prep("ruled")
            self.assertTrue(out["go"], out)
            got = self.accept(self.fixed_reply(), out["iteration"], "ruled")
            self.assertEqual((got["ok"], got["done"]), (False, n == 3), got)
        self.assertEqual(self.snapshot(), self.green_tree, "人に回す組は当て直す前の緑の木へ戻す")
        g2 = self.group_row()
        self.assertEqual((g2["returned"], g2["clash"]["outcome"]), (False, "parked"), g2)
        self.assertIn("人に回した", g2["reason"])
        lines = conflict.human_lines(self.place)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("B: 裁定 " + rid), lines)
        self.assertIn("戻した直しの控え", lines[0])
        self.assertEqual([r["ruling"]["by"] for r in conflict.asked(self.place)], [self.clash.BY_RULED_GIVE_UP])
        self.assertEqual(self.prep("ruled")["go"], False, "人に回した組はもう当て直さない")

    def test_join_clash_ruled_ask_human_goes_to_a_human_without_reapplying(self):
        """裁定役が ask_human と裁いた合わせの申し出は、裁定の後の合わせのループが当て直さずに人の行になる"""
        self.to_ruling("ask_human")
        self.assertEqual(self.prep("ruled")["go"], False)
        self.assertEqual(self.snapshot(), self.green_tree)
        lines = conflict.human_lines(self.place)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("B: "), lines)

    def test_join_clash_rejudge_ruling_becomes_the_fix_objection(self):
        """裁定 rejudge は単位を直す義務から外し、裁定の文を修正の出力の異議にする（メイングラフが再審を回す）"""
        self.to_ruling("rejudge")
        self.assertEqual(self.prep("ruled")["go"], False)
        self.assertEqual(conflict.human_lines(self.place), [], "rejudge は人の行にしない")
        self.assertIn("B", conflict.held_by_rulings(self.place))
        self.intake()
        code, out, err = self.go("finish")
        self.assertEqual(code, 0, err)
        self.assertIn("triple(2) が 6 になるように直せ", out["objection"], out)


if __name__ == "__main__":
    unittest.main()
