"""承認済みの修正案を項目ごとの brief に切り出して凍結する口（lib/planbrief.py）の検査。
- 項目ごとの brief: 修正案の項目と置き場の控え（plan-fields.json）の欄と、判定の単位・目的の文・構造の目の行を 1 つのファイルに並べた文
- 凍結: 今の周に 1 度だけ書き、sha256 を控え（briefs.json）に残す。書き換えられたら控えの文で書き戻す
置き場は使い捨てのフォルダ。修正案（p2.fix_plan の返答）と判定（judgment.json の dict）は引数で渡す。
"""
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from tests.bin.gitkit import committed_copy  # noqa: E402
import fixboard  # noqa: E402
import planbrief  # noqa: E402
import planmarks  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"
FIELDS = [{"route": "tdd", "route_why": "", "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均",
           "path": "stats.mean を直に呼ぶ", "red_kind": "assertion", "red_why": "今は len-1 で割る"}], "rewrite_tests": [],
           "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py", "test_stats.py"], "out_of_scope": []}]


def plan_reply(narrows=()):
    """修正案の役の返答（元 works/tests/test_blk_fix.py の plan_reply）"""
    return {"plan": [{"unit_keys": [MEAN, CLAMP], "approach": "mean の分母を len(xs) に、clamp の上限の枝の戻り値を hi に直す",
                      "adds": [], "removes": [], "shrink_first": "足す物は無い。2 か所の式を 1 行ずつ直すだけで足りる",
                      "narrows": list(narrows)}]}


def judgment():
    """判定（元 works/tests/replies/judge_ok.json の units の key・label・disposition・reason）"""
    return {"units": [{"key": MEAN, "label": "block", "disposition": "do-now", "reason": "mean は len(xs) - 1 で割る"},
                      {"key": CLAMP, "label": "block", "disposition": "do-now", "reason": "clamp は x > hi の枝で lo を返す"}]}


def count_ops(place, op, rnd=1) -> int:
    """置き場の trace.jsonl の、周 rnd の op の行の数"""
    rows = [json.loads(line) for line in (pathlib.Path(place) / "trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return sum(1 for r in rows if r.get("op") == op and r.get("round") == rnd)


class PlaceCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="works-plan-brief-")
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = self.tmp / "repo"
        committed_copy(self.repo, SEED)
        self.place = self.tmp / "place"
        self.place.mkdir()
        self.board = self.place   # 元の試験の名（盤面の根）と同じ所を指す
        self.src = {"plan": plan_reply(), "judgment": judgment()}

    def ready(self):
        planmarks.save(self.place, 1, FIELDS)
        return self.place

    def cut(self):
        return planbrief.cut(self.place, **self.src)


class BriefCase(PlaceCase):
    def test_render_is_deterministic_and_carries_item(self):
        self.ready()
        got = self.cut()
        text = pathlib.Path(got[0]["file"]).read_text(encoding="utf-8")
        for w in ("要求の正本", "test_stats.py::TestStats::test_mean_of_two", plan_reply()["plan"][0]["approach"], MEAN, "背景"):
            self.assertIn(w, text)
        self.assertEqual(got[0]["sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
        args = (1, plan_reply()["plan"][0], FIELDS[0], {u["key"]: u for u in judgment()["units"]}, "目的の文", "")
        self.assertEqual(planbrief.render(*args), planbrief.render(*args))

    def test_brief_carries_prescriptions_and_structure_answers(self):
        """修正役の brief に、判定の処方と、修正案が構造の目の行・処方に答えた欄 structure が載る"""
        judge = judgment()
        judge["units"][0]["prescriptions"] = ["分母を len(xs) にする（既存の機構 1 つで済ませる）"]
        self.src["judgment"] = judge
        dev = {"row": MEAN, "deviation": "既存の呼び手が 3 つあり、今回は 1 か所に寄せると範囲が広がりすぎる"}
        planmarks.save(self.place, 1, [{**FIELDS[0], "structure": [dev]}])
        got = self.cut()
        text = pathlib.Path(got[0]["file"]).read_text(encoding="utf-8")
        self.assertIn("分母を len(xs) にする（既存の機構 1 つで済ませる）", text)
        self.assertIn("## 構造の目の行と処方への答え（structure）", text)
        self.assertIn(dev["deviation"], text)

    def test_brief_carries_purpose(self):
        """凍結した目的の文は引数 purpose で受けて brief に載る（元は盤面の record.process.purpose.purpose_text）"""
        self.ready()
        got = planbrief.cut(self.place, purpose="平均と範囲の丸めを定義どおりにする", **self.src)
        self.assertIn("平均と範囲の丸めを定義どおりにする", pathlib.Path(got[0]["file"]).read_text(encoding="utf-8"))

    def test_render_shows_scope(self):
        """brief に書いてよいパス（allowed_paths）と触らない物（out_of_scope）の節が並ぶ。欄の無い行（217 番の形）は無し"""
        item1 = plan_reply()["plan"][0]
        f = {**FIELDS[0], "allowed_paths": ["stats.py"], "out_of_scope": [{"glob": "test_stats.py", "why": "既存の試験は触らない"}]}
        text = planbrief.render(1, item1, f, {}, "", "")
        for w in ("## 書いてよいパス（allowed_paths）", "- stats.py", "## 触らない物（out_of_scope）", "test_stats.py——既存の試験は触らない"):
            self.assertIn(w, text)
        old = {k: v for k, v in f.items() if k not in ("allowed_paths", "out_of_scope")}
        self.assertIn("## 書いてよいパス（allowed_paths）\n\n無し", planbrief.render(1, item1, old, {}, "", ""))
        text_old = planbrief.render(1, item1, old, {}, "", "")
        for h in ("## 書いてよいパス（allowed_paths）", "## 触らない物（out_of_scope）"):
            self.assertIn(f"{h}\n\n無し（この案は範囲を決めていない。範囲では縛らない）", text_old)
        self.assertIn("## 触らない物（out_of_scope）\n\n無し\n", planbrief.render(1, item1, {**f, "out_of_scope": []}, {}, "", ""))

    def test_cut_is_frozen_and_restores_edited_file(self):
        self.ready(); first = self.cut()
        pathlib.Path(first[0]["file"]).write_text("書き換えた", encoding="utf-8")
        again = self.cut()
        self.assertEqual(again, first)
        self.assertEqual(hashlib.sha256(pathlib.Path(first[0]["file"]).read_bytes()).hexdigest(), first[0]["sha256"])
        self.assertIn(planbrief.RESTORED_OP, (self.board / "trace.jsonl").read_text(encoding="utf-8"))

    def test_cut_keeps_frozen_text_when_sources_change(self):
        self.ready(); first = self.cut()
        before = pathlib.Path(first[0]["file"]).read_bytes()
        changed = [dict(FIELDS[0], route="direct", route_why="凍結の後に控えを書き換えた理由の文", tests=[])]
        planmarks.save(self.board, 1, changed)
        again = self.cut()
        self.assertEqual(again, first)
        self.assertEqual(pathlib.Path(first[0]["file"]).read_bytes(), before)
        self.assertNotIn("凍結の後に控えを書き換えた理由の文", before.decode("utf-8"))

    def test_no_plan_or_no_fields_no_brief(self):
        self.assertEqual(self.cut(), [])
        self.assertFalse((self.board / planbrief.LEDGER).exists())
        self.ready()
        self.assertEqual(planbrief.cut(self.place, plan=None, judgment=judgment()), [])
        self.assertFalse((self.board / planbrief.LEDGER).exists())
        self.assertEqual(planbrief.cut_at(self.tmp / "no-board", **self.src), [])

    def test_cut_at_and_by_unit_at_read_the_place(self):
        self.ready()
        rows = planbrief.cut_at(self.place, **self.src)
        self.assertEqual(len(rows), 1)
        got = planbrief.by_unit_at(self.place)
        self.assertEqual(got, {MEAN: [{"item": 1, "file": rows[0]["file"]}], CLAMP: [{"item": 1, "file": rows[0]["file"]}]})
        self.assertEqual(planbrief.by_unit_at(self.place, round_=2), {}, "周の違う置き場は brief の無い側")
        self.assertEqual(planbrief.by_unit_at(self.tmp / "no-board"), {})

    def test_for_units_picks_items_of_the_units(self):
        rows = [{"item": 1, "unit_keys": [MEAN, CLAMP], "file": "/b/brief-1.md", "sha256": "a" * 64},
                {"item": 2, "unit_keys": [MEAN], "file": "/b/brief-2.md", "sha256": "b" * 64}]
        self.assertEqual([r["item"] for r in planbrief.for_units(rows, [MEAN])], [1, 2])
        self.assertEqual([r["item"] for r in planbrief.for_units(rows, [CLAMP])], [1])
        self.assertEqual(planbrief.for_units(rows, ["判定に無い単位"]), [])

    def test_head_text(self):
        self.assertEqual(planbrief.head_text([]), "")
        self.ready()
        rows = self.cut()
        head = planbrief.head_text(rows)
        for w in (planbrief.HEAD, rows[0]["file"], rows[0]["sha256"], "まず Read で全部読め"):
            self.assertIn(w, head)
        self.assertEqual(planbrief.files(self.board), [rows[0]["file"]])

    # ---------------------------------------------------------------- 凍結の破れ（LedgerBroken）と書き戻し
    def first_cut(self):
        """1 回目の cut の後の (置き場, 返り, 控えのパス)"""
        self.ready()
        rows = self.cut()
        return self.place, rows, self.board / planbrief.LEDGER

    def edit_ledger(self, ledger, change):
        doc = json.loads(ledger.read_text(encoding="utf-8"))
        change(doc["briefs"][0])
        ledger.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def assert_broken(self, pattern):
        with self.assertRaisesRegex(planbrief.LedgerBroken, pattern):
            self.cut()

    def test_ledger_not_json_is_broken(self):
        _, _, ledger = self.first_cut()
        ledger.write_text("{壊れた", encoding="utf-8")
        self.assert_broken("読めない")

    def test_ledger_row_text_not_matching_sha_is_broken(self):
        _, _, ledger = self.first_cut()
        self.edit_ledger(ledger, lambda r: r.update(text=r["text"] + "足した"))
        self.assert_broken("sha256 が合わない")

    def test_ledger_row_file_with_path_is_broken(self):
        _, _, ledger = self.first_cut()
        self.edit_ledger(ledger, lambda r: r.update(file="../x"))
        self.assert_broken("形を成さない")

    def test_ledger_row_item_and_unit_keys_shape(self):
        _, _, ledger = self.first_cut()
        self.edit_ledger(ledger, lambda r: r.update(item="1"))
        self.assert_broken("形を成さない")
        self.edit_ledger(ledger, lambda r: r.update(item=1, unit_keys=[1]))
        self.assert_broken("形を成さない")

    def test_item_count_differs_from_fields_is_broken(self):
        planmarks.save(self.board, 1, FIELDS * 2)
        self.assert_broken("数")
        self.assertFalse((self.board / planbrief.LEDGER).exists())

    def test_ledger_deleted_after_first_cut_is_broken(self):
        _, _, ledger = self.first_cut()
        ledger.unlink()
        planmarks.save(self.board, 1, [dict(FIELDS[0], route="direct", route_why="控えを消してから欄を書き換えた")])
        self.assert_broken("brief_cut")

    def test_ledger_rewritten_consistently_is_broken(self):
        _, _, ledger = self.first_cut()

        def forge(r):
            r["text"] = "役が書き換えた要求"
            r["sha256"] = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
        self.edit_ledger(ledger, forge)
        self.assert_broken("brief_cut")

    def test_first_cut_traces_ledger_sha(self):
        _, rows, ledger = self.first_cut()
        cuts = [json.loads(line) for line in (self.board / "trace.jsonl").read_text(encoding="utf-8").splitlines()
                if '"brief_cut"' in line]
        self.assertEqual(len(cuts), 1)
        self.assertEqual(cuts[0]["round"], 1)
        self.assertEqual(cuts[0]["ledger_sha256"], hashlib.sha256(ledger.read_bytes()).hexdigest())
        self.assertEqual(cuts[0]["files"], [r["file"] for r in rows])
        self.cut()
        self.assertEqual((self.board / "trace.jsonl").read_text(encoding="utf-8").count('"brief_cut"'), 1)

    def test_deleted_brief_is_restored(self):
        _, first, _ = self.first_cut()
        pathlib.Path(first[0]["file"]).unlink()
        self.assertEqual(self.cut(), first)
        self.assertEqual(hashlib.sha256(pathlib.Path(first[0]["file"]).read_bytes()).hexdigest(), first[0]["sha256"])
        self.assertIn(planbrief.RESTORED_OP, (self.board / "trace.jsonl").read_text(encoding="utf-8"))

    def test_restore_does_not_write_through_symlink(self):
        _, first, _ = self.first_cut()
        outside = self.tmp / "outside.txt"
        outside.write_text("外のファイル", encoding="utf-8")
        brief = pathlib.Path(first[0]["file"])
        brief.unlink()
        os.symlink(outside, brief)
        self.cut()
        self.assertEqual(outside.read_text(encoding="utf-8"), "外のファイル")
        self.assertFalse(brief.is_symlink())
        self.assertEqual(hashlib.sha256(brief.read_bytes()).hexdigest(), first[0]["sha256"])

    def test_restore_over_directory_is_broken(self):
        _, first, _ = self.first_cut()
        brief = pathlib.Path(first[0]["file"])
        brief.unlink()
        brief.mkdir()
        self.assert_broken("ディレクトリ")


class BriefFreezeEdgeCase(PlaceCase):
    """凍結の端: 欄の控え plan-fields.json の書き換え・cut の外で置いた控え・控えの一時ファイルのリンク"""

    def test_fields_rewritten_before_first_cut_is_broken(self):
        """受け付けの後（1 回目の cut の前）に plan-fields.json を書き換えた置き場は brief を切らず LedgerBroken（控えを名指す）"""
        self.ready()
        p = self.board / planmarks.FIELDS_FILE
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["route"] = "direct"
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(planbrief.LedgerBroken, planmarks.FIELDS_FILE):
            self.cut()
        self.assertFalse((self.board / planbrief.LEDGER).exists())

    def test_unmarked_ledger_before_first_cut_is_broken(self):
        """1 回目の cut の前に置かれた控え（行の text と sha256 は揃っているが、切った印が無い）を正本にしない"""
        self.ready()
        text = "# 要求の正本: cut の外で書いた brief\n"
        ledger = self.board / planbrief.LEDGER
        ledger.write_text(json.dumps({"briefs": [{"item": 1, "unit_keys": [MEAN], "file": "brief-1.md", "text": text,
                                                  "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}]},
                                     ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(planbrief.LedgerBroken, "印が無い"):
            self.cut()

    def test_ledger_tmp_symlink_is_not_written_through(self):
        """控えの一時ファイル（briefs.json.tmp）の置き場に先にリンクが在っても、リンクの先へ書かない"""
        self.ready()
        outside = self.tmp / "outside.json"
        outside.write_text("外のファイル", encoding="utf-8")
        os.symlink(outside, self.board / (planbrief.LEDGER + ".tmp"))
        rows = self.cut()
        self.assertEqual(len(rows), 1)
        self.assertEqual(outside.read_text(encoding="utf-8"), "外のファイル")
        self.assertFalse((self.board / planbrief.LEDGER).is_symlink())


class TestRecutAfterAmend(PlaceCase):
    """承認済みの項目の差し替え（planmarks.amend の AMEND_OP の印）の後の cut だけが、差し替えた項目の brief を切り直す"""

    def amend_first(self):
        view = fixboard.plan_view(self.place, **self.src)
        new = {k: v for k, v in planmarks.approved_items(view)[0].items() if k != "item"}
        new["tests"] = [{**new["tests"][0], "red_kind": "exception", "red_why": "今は ZeroDivisionError が出ない"}]
        planmarks.amend(view, {1: new}, self.repo)

    def test_recut_after_amend(self):
        self.ready()
        first = self.cut()
        self.amend_first()
        again = self.cut()
        text = pathlib.Path(again[0]["file"]).read_text(encoding="utf-8")
        self.assertIn("exception", text)
        self.assertNotEqual(first[0]["sha256"], again[0]["sha256"])
        self.assertEqual(count_ops(self.board, planbrief.RECUT_OP), 1)
        self.assertEqual(count_ops(self.board, planbrief.CUT_OP), 2)
        self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), again[0]["sha256"])
        # 切り直した後は凍結に戻る（もう 1 度 cut しても切り直さない・控えは新しい CUT_OP の印と合う）
        self.assertEqual(self.cut(), again)
        self.assertEqual(count_ops(self.board, planbrief.RECUT_OP), 1)
        self.assertEqual(count_ops(self.board, planbrief.CUT_OP), 2)

    def test_no_recut_without_amend(self):
        self.ready()
        self.cut(); self.cut()
        self.assertEqual(count_ops(self.board, planbrief.RECUT_OP), 0)
        self.assertEqual(count_ops(self.board, planbrief.CUT_OP), 1)

    def test_tamper_after_recut_is_restored(self):
        self.ready()
        self.cut()
        self.amend_first()
        again = self.cut()
        brief = pathlib.Path(again[0]["file"])
        brief.write_text("役が書き換えた", encoding="utf-8")
        self.assertEqual(self.cut(), again)
        self.assertEqual(hashlib.sha256(brief.read_bytes()).hexdigest(), again[0]["sha256"])
        self.assertIn("exception", brief.read_text(encoding="utf-8"))
        self.assertIn(planbrief.RESTORED_OP, (self.board / "trace.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(count_ops(self.board, planbrief.RECUT_OP), 1)


if __name__ == "__main__":
    unittest.main()
