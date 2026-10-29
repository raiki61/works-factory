"""事前審査の木（docs/design/plan-review.md の 5 節・9.1 の 5。src/tree.py・prompts/review-tree.md・prompts/parts/item-brief.md・
synergy-brief.md）を、script を子のプロセスで回して確かめる。下請けの答えのファイル（place の answers/）は試験が書く。

写した元は tests/workflows/test_plan_review.py の TreeCase（元 tests/test_blk_plan.py の TreeReviewCase の事前審査の側）と
lib/tests/test_boardview.py の RulesCase.test_unattended_and_tree_words の木の語の半分（試験ごとの docstring に元の名を書く）。
往復の記録は line の代わりに Flow.carry が pass.json を converge.add_pass で足して port prior に渡す。往復の番号のフォルダ
（pass-<k>/）は無い。頭の深さの段から木を引く 2 本（test_heavy_head_depth_makes_the_tree・
test_light_head_depth_keeps_one_reviewer_unless_named）は段 → on・off・auto の引きが line に移るので line の試験へ。
"""
import copy
import json
import unittest

from tests.blocks import kit
from tests.blocks.plan_review.test_take import (
    BLOCK, DESIGN_OK, NO_EFFECT, PLAN_MARK, PRECEDENTS as BARE_PRECEDENTS, RIPPLE, UNIT_CLAMP, UNIT_MEAN, Flow, answer, dump, face, fields,
    frow, item, review, summary, synergy)

# 人に回る regression の穴が名乗る、人に聞く場合の印つきの訳（持ち主の決め settle-by-standard。受け付けが印の無い行を拒む）
CASE = "②空の列の扱いは呼び手の優先で割れ、定石も 1 つに決めない"
MEAN_BLOCK = face("item1-mean-empty-division", UNIT_MEAN, kind="regression", undecided_because=CASE)
CLAMP_BLOCK = face("item2-clamp-upper-branch", UNIT_CLAMP)
STUCK_NOTE = "{key} を項目 1 の修正の中で直す範囲で通す"
STUCK_REC = {"answer": "continue", "note": STUCK_NOTE.format(key=MEAN_BLOCK["key"]), "why": "穴は案の項目 1 の直しで閉じられる"}
# 判定の先行例（共通の port の形 judgment.schema.json は problem を求める）
PRECEDENTS = [{**p, "problem": "空の列と上限の値の扱い"} for p in BARE_PRECEDENTS]
NARROW = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}
FIXED = [{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}]
# md の決まった字（試験が指示の字と突き合わせる）
BUNDLE_HEAD = "## Bundling the sub-reviews"
ONE_TYPE = "Use `subagent_type` general-purpose for every sub-agent"
DONE_HEAD = "Sub-agents already done"
REDO_HEAD = "Sub-agents to start again"
OPEN_HEAD = "Files of the open items' sub-agents:"
REREVIEW_ASK = "Answers to earlier passes:"
ORIGIN_ASK = "Origins of new blocks:"
DIFF_ASK = "How to read the diffs:"
LATER_ITEM_ASK = 'When the item file has "#### Diff since the previous pass"'
DESIGN_DIFF_ASK = "From the second pass on, compare with the design only the sentences the diffs added and removed"
SPAWNS = "If you start a sub-agent, put this whole block of rules"


def fetch_ids(text: str) -> list:
    """項目の材料のファイルが開けと言う先行例の出典の id（札 fetch の行の頭の `- P<i>`）"""
    return [line.split(":", 1)[0][2:] for line in text.splitlines() if line.startswith("- P") and line.endswith(" — fetch")]


def errors_of(text: str, head: str) -> dict:
    """項目の材料のファイルの前の答えの誤りの節の JSON"""
    return json.loads(text[text.index(head):].split("```json\n", 1)[1].split("\n```", 1)[0])


def map_row(n, symbol, ref=None) -> dict:
    return {"item": n, "path": "stats.py", "symbol": symbol, "design_ref": ref, "design_quote": None,
            "why": "設計に対の無い助け手の名だけを足す"}


class TreeBase(unittest.TestCase):
    """木の往復の場（元 TreeCase.setUp）: 先行例 2 つの判定・覆っていない当たり h1 を持つ波及の一覧・2 項目の案・tree auto"""

    def setUp(self):
        self.flow = f = Flow(self)
        f.judgment(precedents=PRECEDENTS)
        f.ripple(RIPPLE)
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")])])
        f.inputs["tree"] = "auto"
        self.tree = kit.load(BLOCK, "tree")
        self.take = self.tree.take
        self.converge = self.tree.converge
        self.material = self.tree.material
        self.heads = self.tree.ITEM_HEADS

    # ---- 回す
    def prepped(self) -> str:
        self.assertTrue(self.flow.intake()["tree"])
        return self.flow.prompt()

    def b(self, review_doc=None):
        return self.take.view.view(self.flow.place, self.flow.intake_doc(), review_doc)

    def item_text(self, n) -> str:
        return self.flow.text(f"items/item-{n}.md")

    def brief(self) -> str:
        return self.flow.text("items/brief.md")

    def write_answers(self, rows, syn=None, fetched=True):
        """下請けが書く答えのファイル。fetched なら、その項目の下請けが開く先行例の出典の確かめの行を足す"""
        b = self.b()
        pre = self.tree.precedent_plan(b, self.converge.open_items(b))
        for n, row in rows.items():
            ids = [x["id"] for x in pre.get(n) or [] if x["cached"] is None and x["fetch_by"] == n] if fetched else []
            if ids and "precedents" not in row:
                row = {**row, "precedents": [{"id": i, "found": True, "quote": "出典は在り、単位の問題に当たっている"} for i in ids]}
            p = self.tree.answer_file(b, n)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dump(row), encoding="utf-8")
        if syn is not None:
            p = self.tree.synergy_file(b)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dump(syn), encoding="utf-8")

    def surplus_rows(self) -> list:
        text = self.flow.text("trace.jsonl")
        return [r for r in (json.loads(x) for x in text.splitlines()) if r.get("op") == self.tree.SURPLUS_OP]

    def ok(self, got):
        self.assertTrue(got["ok"], got)
        return got

    def first_pass_blocks_item_2(self, notes=(), rows=None, faces1=()):
        """1 往復目（木）: 項目 2 だけ block。受けた往復を往復の記録に足し、足した行を返す"""
        f = self.flow
        if rows is not None:
            f.plan(rows)
        self.prepped()
        self.write_answers({1: answer(1, faces=list(faces1)), 2: answer(2, faces=[CLAMP_BLOCK, *notes])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        return f.carry()


class TreeCase(TreeBase):
    def test_aggregator_spawns_item_subagents_and_synergy(self):
        """元 test_aggregator_spawns_item_subagents_and_synergy（元 test_review_prompt_spawns_item_subagents_and_synergy・
        test_aggregator_names_one_subagent_type）"""
        text = self.prepped()
        b = self.b()
        self.assertIn(BUNDLE_HEAD, text)
        self.assertIn(ONE_TYPE, text)
        folder = self.flow.place / "items"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["brief.md", "item-1.md", "item-2.md", "synergy.md"])
        for name in ("brief.md", "item-1.md", "item-2.md", "synergy.md"):
            self.assertIn(str(folder / name), text)
        for n in (1, 2):
            self.assertIn(str(self.tree.answer_file(b, n)), self.item_text(n))
            self.assertFalse(str(self.tree.answer_file(b, n)).startswith(str(self.flow.repo)), "作業ツリーの外")
        syn = self.flow.text("items/synergy.md")
        self.assertIn(str(self.tree.synergy_file(b)), syn)
        self.assertIn("test_clamp_above_range", self.item_text(2))
        self.assertIn("stats.py: item 1, 2", syn)

    def test_brief_carries_only_its_item_inline(self):
        """元 test_brief_carries_only_its_item_inline: 下請けの指示（items/brief.md）は審査の決まり・独立設計の節・Repository の行と、
        根拠を読む版で取れの頼み（元 planblk.brief_head が貼った plan-review.md の :63）を持ち、項目の材料のファイルは自分の項目だけを
        持つ（全部の項目で同じ指示は 1 本のファイル）"""
        self.prepped()
        brief = self.brief()
        for part in ("## What to look at", "## How to write the holes", self.material.MAT_HEADS["design"],
                     f"Repository: {self.flow.repo}", "**Take your evidence from the read version**"):
            self.assertIn(part, brief)
        one = self.item_text(1)
        self.assertTrue(one.startswith(self.heads["item"].format(n=1)), one[:80])
        self.assertIn("分母が 1 少ない", one)
        self.assertNotIn("上限で lo を返す", one)
        self.assertNotIn("test_clamp_above_range", one)

    def test_item_brief_lists_only_its_wanted_keys(self):
        """元 test_item_brief_lists_only_its_wanted_keys: 独立設計が立つ木の往復: item-1.md には項目 1 の鍵（helper_1）だけが、item-2.md には
        項目 2 の鍵（clamp）だけが design_map の鍵の一覧として載る。一覧は項目の見出しと単位の節の後に在り、下請けの指示には鍵が無い"""
        self.flow.design()
        self.prepped()
        one, two = self.item_text(1), self.item_text(2)
        head = self.material.MAT_HEADS["map_items"]
        key1 = '{"item": 1, "path": "stats.py", "symbol": "helper_1"}'
        key2 = '{"item": 2, "path": "stats.py", "symbol": "clamp"}'
        for text, mine, other, n in ((one, key1, key2, 1), (two, key2, key1, 2)):
            self.assertEqual(text.count(head), 1)
            self.assertEqual(text.count(mine), 1)
            self.assertNotIn(other, text)
            self.assertGreater(text.index(head), text.index(self.heads["units"].format(n=n)))
            self.assertGreater(text.index(head), text.index(self.heads["item"].format(n=n)))
            self.assertGreater(text.index(mine), text.index(head))
        for key in (key1, key2):
            self.assertNotIn(key, self.brief())

    def test_machine_merges_item_answers_into_review(self):
        """元 test_machine_merges_item_answers_into_review"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1), 2: answer(2)}, syn=synergy())
        self.ok(f.accept(tree=summary({1: [], 2: []})))
        saved = f.read("review.json")
        self.assertEqual(saved["faces"], [])
        self.assertNotIn("items", saved)
        self.assertIn("item-2.json", f.read("pass.json")["files"])
        self.assertEqual(f.finish()["status"], "ok")
        row = f.carry()
        self.assertEqual(row["outcome"], self.converge.CLEAN)
        self.assertEqual([it["state"] for it in row["items"]], [self.converge.CLOSED, self.converge.CLOSED])
        self.assertEqual([h["id"] for h in row["items"][1]["hits"]], ["h1"])

    def test_summary_without_items_is_refused(self):
        """#832: 束ね役の型も根の欄を要ると書かない。items の欠けた束ね役の答えは受け付けが拒み、出し直しの items で通る"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1), 2: answer(2)}, syn=synergy())
        whole = summary({1: [], 2: []})
        got = f.accept(tree={"reason": whole["reason"]})
        self.assertEqual((got["ok"], got["reason"]), (False, self.take.rolekit.MISSING_FIELDS.format(keys="items")))
        self.ok(f.accept(tree_fix={"items": whole["items"]}))

    def test_invalid_answer_goes_back_to_its_item_only(self):
        """元 test_invalid_answer_goes_back_to_its_item_only"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1), 2: answer(2, why="同上")}, syn=synergy())
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        self.assertIn("項目 2", got["reason"])
        self.assertNotIn("項目 1（", got["reason"])
        text = f.prompt()
        redo = text[text.index(REDO_HEAD):]
        self.assertIn(str(f.place / "items" / "item-2.md"), redo)
        self.assertNotIn(str(f.place / "items" / "item-1.md"), redo)
        errs = errors_of(self.item_text(2), self.heads["errors"])
        self.assertEqual(errs["item"], 2)
        self.write_answers({2: answer(2)})
        self.ok(f.accept(tree=summary({1: [], 2: []})))

    def test_tree_policy_face_names_its_answer_file(self):
        """元 test_tree_policy_face_names_its_answer_file: 項目 2 の答えのファイルに名指しの無い kind policy の穴が在ると、拒みは TREE_REJECT で
        始まり、その項目の答えのファイルと $.faces[0] の番号を名指す。輪の中の出し直し（prev が false の review_prep の後の review_fix_prep）の指示は、その拒みの
        行を字のまま貼る。prev 無しの支度（resume）は、項目 2 の材料のファイルの誤りの節にその行を載せ、項目 1 は済んだ下請けに並べる。
        相乗りの答えの穴にも同じ照らしが当たり、拒みは相乗りの答えのファイルを名指す"""
        f = self.flow
        self.prepped()
        stray = face("item2-policy-without-row", UNIT_CLAMP, kind="policy", severity="suggest")
        self.write_answers({1: answer(1), 2: answer(2, faces=[stray])}, syn=synergy())
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        line = f"項目 2（{self.tree.answer_file(self.b(), 2)}）: $.faces[0]（{stray['key']}）"
        self.assertIn(line, got["reason"])
        self.assertNotIn("項目 1（", got["reason"])
        self.assertNotIn(self.take.FACE_REJECT, got["reason"])
        self.assertTrue(f.prep(prev="false")["resubmit"])
        again = f.run.script("review_fix_prep")["prompt"]   # 出し直しの役の指示は review-fix-prep が組む
        self.assertIn(line, again)
        text = f.prompt()
        self.assertIn(str(f.place / "items" / "item-2.md"), text[text.index(REDO_HEAD):])
        self.assertIn(str(f.place / "items" / "item-1.md"), text[text.index(DONE_HEAD):text.index(REDO_HEAD)])
        errs = errors_of(self.item_text(2), self.heads["errors"])
        self.assertIn(f"$.faces[0]（{stray['key']}）", "\n".join(map(str, errs["errors"])))
        stray_syn = face("synergy-policy-without-row", UNIT_MEAN, kind="policy", severity="suggest")
        self.write_answers({2: answer(2)}, syn=synergy([stray_syn]))
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertIn(f"相乗りの審査（{self.tree.synergy_file(self.b())}）: $.faces[0]（{stray_syn['key']}）", got["reason"])

    def test_tree_carried_policy_note_is_not_rechecked(self):
        """元 test_tree_carried_policy_note_is_not_rechecked: 1 往復目の項目 1 の答えが、依頼の answers の名指しを decided_by に書いた kind policy の
        suggest を挙げて通る。2 往復目（項目 2 だけ開く）は、持ち越しの写し（往復の記録の notes は決め手の欄を外した写し）を方針の照らしで
        拒まずに通し、写しは返答の faces に残る"""
        f = self.flow
        f.inputs["tree"] = "on"
        f.inputs["recorded"] = dump([{"source": "answer", "name": "q-mean-empty", "text": "空の列の平均は例外にする"}])
        note = face("item1-policy-note", UNIT_MEAN, kind="policy", severity="suggest", decided_by="q-mean-empty")
        self.first_pass_blocks_item_2(faces1=[note])
        two = item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                   approach="clamp の上限の枝で hi を返し、上限ちょうどの値はそのまま返す（定義どおり）")
        f.plan([item(UNIT_MEAN, 1), two], rnd=2, answers=FIXED)
        self.prepped()
        self.write_answers({2: {**answer(2, resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        self.ok(f.accept(tree=summary({2: []})))
        carried = [x for x in f.read("review.json")["faces"] if x["key"] == note["key"]]
        self.assertEqual(len(carried), 1)
        self.assertNotIn("decided_by", carried[0])

    def test_item_design_quotes_reopen_only_that_item(self):
        """元 test_item_design_quotes_reopen_only_that_item"""
        f = self.flow
        f.design()
        self.prepped()
        bad_quote = "上限は入口 2 箇所で掛け"
        design = self.tree.design
        drift = face("item1-design-drift", why=design.DRIFT_HEAD + f"設計の「{bad_quote}」に対し案の「{PLAN_MARK} 項目 1 の直し」は食い違う")
        one = {**answer(1, faces=[drift]), "design_map": [map_row(1, "helper_1", "D1")]}
        two = {**answer(2), "design_map": [{**map_row(2, "clamp"), "why": "設計は上限の枝の関数を足さないので対が無い"}]}
        self.write_answers({1: one, 2: two})
        got = f.accept(tree=summary({1: [drift["key"]], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        self.assertIn(bad_quote, got["reason"])
        self.assertNotIn("項目 2（", got["reason"])
        text = f.prompt()
        redo = text[text.index(REDO_HEAD):]
        self.assertIn(str(f.place / "items" / "item-1.md"), redo)
        self.assertNotIn(str(f.place / "items" / "item-2.md"), redo)
        self.assertIn(str(f.place / "items" / "item-2.md"), text[text.index(DONE_HEAD):text.index(REDO_HEAD)])
        brief = self.item_text(1)
        self.assertIn(bad_quote, brief[brief.index(self.heads["errors"]):])

    def designed_two_elements(self):
        """独立設計が立ち要素 2 つ（D1・D2）の 1 往復目（木）: 項目 1 が D1 を受けて閉じ、項目 2 に block が残る"""
        f = self.flow
        f.design({**DESIGN_OK, "elements": [{"id": "D1", "adds": ["上限の入口"], "removes": []},
                                            {"id": "D2", "adds": ["丸めの口"], "removes": []}]})
        self.prepped()
        self.write_answers({1: {**answer(1), "design_map": [map_row(1, "helper_1", "D1")]},
                            2: {**answer(2, faces=[CLAMP_BLOCK]), "design_map": [map_row(2, "clamp", "D2")]}})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        row = f.carry()
        self.assertEqual([it["state"] for it in row["items"]], [self.converge.CLOSED, self.converge.OPEN])

    def material_text(self) -> str:
        paths = sorted(self.flow.place.glob("review-material-*.md"))
        return paths[-1].read_text(encoding="utf-8")

    def test_tree_off_second_pass_names_the_design_map_items(self):
        """元 test_tree_off_second_pass_names_the_design_map_items: 独立設計が立つ run の 1 往復目（木）に項目 1 が閉じ、項目 2 に block が
        残った後の 2 往復目（開いた項目 1 つで木にしない）: 材料の design_map を書く項目の節が項目 2 だけを名指し、項目 1 が前の往復で
        受けた要素 D1 を数え済みと言う。項目 2 の行と設計→案の行だけの design_map も、閉じた項目 1 の行を足した design_map も 1 回目で受かる
        （#687）"""
        f = self.flow
        self.designed_two_elements()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach=f"{PLAN_MARK} 直した項目 2", files=[frow("stats.py", "clamp")])],
               rnd=2, answers=FIXED)
        self.assertFalse(f.intake()["tree"])
        f.prep()
        text = self.material_text()
        body = text[text.index(self.material.MAT_HEADS["map_items"]):].split("\n\n")[1]
        self.assertIn("Items: 2 ", body)
        self.assertNotIn("Items: 1", body)
        self.assertIn("closed or held items", body)
        self.assertIn("(already counted): D1", body)
        mine = [map_row(2, "clamp"), {"item": None, "path": None, "symbol": None, "design_ref": "D2", "design_quote": None,
                                      "why": "設計の丸めの口は案のどの行にも対が無い"}]
        self.ok(f.accept(review(design_map=[*mine, map_row(1, "helper_1", "D1")], resolved=[CLAMP_BLOCK["key"]])))

    def test_tree_off_second_pass_asks_map_only_for_new_keys(self):
        """元 test_tree_off_second_pass_asks_map_only_for_new_keys: 2 往復目（木にしない）の design_map は、前の往復の行にも在った鍵（clamp）を
        求めず、足した鍵（clamp_guard）だけを鍵の一覧に貼って求める。書き直さなかった鍵の行が前の往復で受けた要素（D2）は網羅に引き継ぎ、
        往復の記録の refs にも残す。足した鍵の行の無い design_map は拒む"""
        f = self.flow
        self.designed_two_elements()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp", "clamp_guard")])], rnd=2,
               answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝を守る助け手 clamp_guard を足した"}])
        self.assertFalse(f.intake()["tree"])
        prompt = f.prompt()
        text = self.material_text()
        keys = text[text.index(self.material.MAT_HEADS["map_items"]):].split("\n\n")[2]
        self.assertIn('"symbol": "clamp_guard"', keys)
        self.assertNotIn('"symbol": "clamp"}', keys)
        self.assertIn(DESIGN_DIFF_ASK, prompt)
        fixed = [CLAMP_BLOCK["key"]]
        got = f.accept(review(design_map=[], resolved=fixed))
        self.assertFalse(got["ok"], got)
        self.assertIn("clamp_guard", got["reason"])
        self.ok(f.accept(review(design_map=[map_row(2, "clamp_guard")], resolved=fixed)))
        self.assertEqual(f.carry()["items"][1]["refs"], ["D2"])

    def test_tree_item_answer_rows_off_its_keys_pass_first_time(self):
        """元 test_tree_item_answer_rows_off_its_keys_pass_first_time（#687）: 項目 1 の答えが自分の鍵に無い行と、項目の番号を取り違えた
        自分の鍵の行を持っても 1 回目で通る。取り違えた行は項目 1 に結び直し、その design_ref は項目 1 の refs に残る"""
        f = self.flow
        f.design()
        self.prepped()
        self.write_answers({1: {**answer(1), "design_map": [map_row(2, "helper_1", "D1"), map_row(2, "clamp"),
                                                            map_row(1, "not_in_files")]},
                            2: {**answer(2), "design_map": [map_row(2, "clamp")]}}, syn=synergy())
        self.ok(f.accept(tree=summary({1: [], 2: []})))
        self.assertEqual(f.carry()["items"][0]["refs"], ["D1"])

    def test_untree_design_map_rows_off_the_keys_pass_first_time(self):
        """元 test_untree_design_map_rows_off_the_keys_pass_first_time（#687）: 木にしない往復の design_map で、項目の番号を取り違えた行は
        鍵の項目に結び直し、要る鍵に無い行は余りとして照らさない。要る鍵の行が無い時は今どおり拒む"""
        f = self.flow
        f.inputs["tree"] = "off"
        f.design()
        self.assertFalse(f.intake()["tree"])
        f.prep()
        stray = {"item": 2, "path": "docs/notes.md", "symbol": None, "design_ref": None, "design_quote": None,
                 "why": "設計に対の無い文書の書き換え"}
        got = f.accept(review(design_map=[map_row(2, "clamp")]))
        self.assertFalse(got["ok"], got)
        self.assertIn("helper_1", got["reason"])
        self.ok(f.accept(review(design_map=[map_row(2, "helper_1", "D1"), map_row(2, "clamp"), map_row(1, "not_in_files"), stray])))
        self.assertEqual(f.carry()["items"][0]["refs"], ["D1"])

    def test_untree_design_ref_only_on_a_row_off_the_keys_is_not_coverage(self):
        """元 test_untree_design_ref_only_on_a_row_off_the_keys_is_not_coverage（#687）"""
        f = self.flow
        f.inputs["tree"] = "off"
        f.design()
        self.assertFalse(f.intake()["tree"])
        f.prep()
        notes = {"item": 1, "path": "docs/notes.md", "symbol": None, "design_ref": "D1", "design_quote": None,
                 "why": "設計の上限の入口を文書に書く"}
        got = f.accept(review(design_map=[map_row(1, "helper_1"), map_row(2, "clamp"), notes]))
        self.assertFalse(got["ok"], got)
        self.assertIn("独立設計の要素 D1", got["reason"])

    def test_tree_design_ref_only_on_a_row_off_the_keys_is_not_coverage(self):
        """元 test_tree_design_ref_only_on_a_row_off_the_keys_is_not_coverage（#687）"""
        f = self.flow
        f.design()
        self.prepped()
        notes = {"item": 1, "path": "docs/notes.md", "symbol": None, "design_ref": "D1", "design_quote": None,
                 "why": "設計の上限の入口を文書に書く"}
        self.write_answers({1: {**answer(1), "design_map": [map_row(1, "helper_1"), notes]},
                            2: {**answer(2), "design_map": [map_row(2, "clamp")]}}, syn=synergy())
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertIn("独立設計の要素 D1", got["reason"])

    def test_synergy_design_quotes_checked_against_named_items(self):
        """元 test_synergy_design_quotes_checked_against_named_items"""
        f = self.flow
        f.design()
        self.prepped()
        self.write_answers({1: {**answer(1), "design_map": [map_row(1, "helper_1", "D1")]},
                            2: {**answer(2), "design_map": [{**map_row(2, "clamp"), "why": "設計は上限の枝の関数を足さないので対が無い"}]}})

        def syn_face(quote):
            return {**face("synergy-design-drift", unit=UNIT_MEAN), "unit_keys": [UNIT_MEAN, UNIT_CLAMP],
                    "why": self.tree.design.DRIFT_HEAD + f"設計の「{quote}」に対し案の「{PLAN_MARK} 項目 1 の直し」は食い違う"}
        self.write_answers({}, syn=synergy([syn_face("上限は入口 2 箇所で掛け")]))
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"], got)
        self.assertIn("相乗りの審査", got["reason"])
        self.assertIn("上限は入口 2 箇所で掛け", got["reason"])
        self.write_answers({}, syn=synergy([syn_face("上限は入口 1 箇所で掛け")]))
        self.ok(f.accept(tree=summary({1: [], 2: []})))

    def test_aggregator_reply_is_summary_only(self):
        """元 test_aggregator_reply_is_summary_only: 受け付けは束ね役の欄を使わず、faces を下請けの答えのファイルから組む"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2)})
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("項目 1", got["reason"])
        self.ok(f.accept(tree={**summary({1: [MEAN_BLOCK["key"]], 2: []}), "faces": []}))
        self.assertEqual([x["key"] for x in f.read("review.json")["faces"]], [MEAN_BLOCK["key"]], "faces は下請けの答えのファイルの物")
        self.assertEqual(f.carry()["outcome"], self.converge.AGAIN)

    def test_bundler_stuck_push_rides_on_the_pass_row(self):
        """元 test_bundler_stuck_push_rides_on_the_pass_row: 束ね役の指示はまとめの返し方で、一番上の止まった時の推しの欄の名
        （converge.STUCK_PUSH）と推しの形と、block の項目か保留の項目の節が在る往復は頭の決まりのとおり書くこと、書く前に下請けの答えの
        ファイルの block の why と案の項目を読むことを名指す。束ね役の推しは受け付けを通って pass.json の push に乗り、review.json には無い"""
        f = self.flow
        text = self.prepped()
        merge = text[text.index("When every sub-agent has returned"):]
        shape = self.material.SLOTS["recommend_shape"](None)
        for part in (self.converge.STUCK_PUSH, shape, '"Held items"', "as the rules above say",
                     "read the `why` of the blocks in the sub-agents' answer files and the plan items"):
            with self.subTest(part=part):
                self.assertIn(part, merge)
        self.write_answers({1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2)})
        got = f.accept(tree={**summary({1: [MEAN_BLOCK["key"]], 2: []}), self.converge.STUCK_PUSH: {**STUCK_REC, "answer": "maybe"}})
        self.assertFalse(got["ok"])
        self.assertTrue(got["reason"].startswith(self.take.RECOMMEND_REJECT), got["reason"])
        self.ok(f.accept(tree={**summary({1: [MEAN_BLOCK["key"]], 2: []}), self.converge.STUCK_PUSH: STUCK_REC}))
        self.assertEqual(f.read("pass.json")["push"], STUCK_REC)
        saved = f.read("review.json")
        self.assertNotIn(self.converge.STUCK_PUSH, saved)
        self.assertEqual([x["key"] for x in saved["faces"]], [MEAN_BLOCK["key"]])
        self.assertEqual(f.carry()["push"], STUCK_REC)

    def test_all_clean_pass_needs_synergy(self):
        """元 test_all_clean_pass_needs_synergy"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1), 2: answer(2)})
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("相乗り", got["reason"])
        self.write_answers({}, syn=synergy())
        self.ok(f.accept(tree=summary({1: [], 2: []})))
        self.assertEqual(f.carry()["outcome"], self.converge.CLEAN)

    def test_item_answer_cannot_name_other_items(self):
        """元 test_item_answer_cannot_name_other_items"""
        f = self.flow
        self.prepped()
        other = face("item1-names-clamp", unit=UNIT_CLAMP)
        self.write_answers({1: answer(1, faces=[other]), 2: answer(2)})
        got = f.accept(tree=summary({1: [other["key"]], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn("項目 1", got["reason"])

    def test_item_answer_names_its_unit_by_number(self):
        """元 test_item_answer_names_its_unit_by_number（#398）: 項目の答えの face が単位を番号で名指すと名に戻して項目の単位と比べる。
        自分の単位の番号は通り、戻せない番号は番号のまま項目の単位でないと拒む"""
        f = self.flow
        self.prepped()
        names = f.intake_doc()["names"]
        for no, ok in ((len(names) + 1, False), (names.index(UNIT_MEAN) + 1, True)):
            with self.subTest(no=no):
                mine = face("item1-mean-by-number", unit=no)
                self.write_answers({1: answer(1, faces=[mine]), 2: answer(2)})
                got = f.accept(tree=summary({1: [mine["key"]], 2: []}))
                self.assertEqual(got["ok"], ok, got.get("reason"))
                if not ok:
                    self.assertIn(f"項目 1 の単位でない ['{no}']", got["reason"])

    def test_item_answer_number_is_not_read_as_a_unit_named_by_its_digits(self):
        """元 test_item_answer_number_is_not_read_as_a_unit_named_by_its_digits（#398）: 戻せない番号は番号のまま照らすので、項目の単位に
        番号と同じ字の key があっても通さない"""
        f = self.flow
        digits = "9"
        f.units.append({"key": digits, "label": "block", "reason": "番号と同じ字の key"})
        f.judgment(precedents=PRECEDENTS)
        f.plan([{**item(UNIT_MEAN, 1), "unit_keys": [UNIT_MEAN, digits]}, item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")])])
        self.prepped()
        self.assertLess(len(f.intake_doc()["names"]), int(digits))
        by_number = face("item1-by-out-of-range-number", unit=int(digits))
        self.write_answers({1: answer(1, faces=[by_number]), 2: answer(2)})
        got = f.accept(tree=summary({1: [by_number["key"]], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn(f"項目 1 の単位でない ['{digits}']", got["reason"])

    def test_second_pass_reviews_diff_and_carries_answers_and_notes(self):
        """元 test_second_pass_reviews_diff_and_carries_answers_and_notes: 2 往復目の下請けは差分と前の block の行き先だけを見て、前の往復で
        答えた当たりは機械が引き継ぎ、suggest の穴は最後の返答に残る。閉じた項目の材料のファイルは書かない"""
        f = self.flow
        f.inputs["tree"] = "on"
        self.prepped()
        note = face("item1-mean-docstring-note", severity="suggest",
                    why="mean の docstring が分母を言っていないので、直した後に読み手が分母を取り違えうる")
        self.write_answers({1: answer(1, faces=[note]), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        row = f.carry()
        self.assertEqual([it["state"] for it in row["items"]], [self.converge.CLOSED, self.converge.OPEN])
        two = item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                   approach="clamp の上限の枝で hi を返し、上限ちょうどの値はそのまま返す（定義どおり）")
        f.plan([item(UNIT_MEAN, 1), two], rnd=2, answers=FIXED)
        self.prepped()
        text = self.item_text(2)
        diff = text[text.index(self.material.LABELS["diff"]):]
        self.assertIn("上限ちょうどの値はそのまま返す", diff)
        self.assertIn(DIFF_ASK, self.brief())
        self.assertNotIn(self.material.LABELS["item_plan"].format(n=2), text, "2 往復目は項目の全体を貼らない")
        self.assertIn(CLAMP_BLOCK["key"], text)
        self.assertIn(self.heads["carried"], text)
        self.assertFalse((f.place / "items" / "item-1.md").exists(), "閉じた項目は審査しない")
        self.write_answers({2: {**answer(2, resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        self.ok(f.accept(tree=summary({2: []})))
        self.assertIn(note["key"], [x["key"] for x in f.read("review.json")["faces"]])
        row = f.carry()
        self.assertEqual(row["outcome"], self.converge.CLEAN)
        self.assertEqual([(h["id"], h.get("carried")) for h in row["items"][1]["hits"]], [("h1", 1)])

    def test_design_elements_count_all_item_answers_and_closed_item_refs(self):
        """元 test_design_elements_count_all_item_answers_and_closed_item_refs: 独立設計の要素の網羅は、今の往復の全部の項目の答えの
        design_ref に、閉じた項目が前の往復で受けた design_ref（往復の記録の refs）を合わせて数える"""
        f = self.flow
        f.inputs["tree"] = "on"
        f.design({**DESIGN_OK, "elements": [{"id": "D1", "adds": ["上限の入口"], "removes": []},
                                            {"id": "D2", "adds": ["丸めの口"], "removes": []}]})
        self.prepped()
        one = {**answer(1), "design_map": [map_row(1, "helper_1", "D1")]}

        def two(ref, **kw):
            return {**answer(2, **kw), "design_map": [map_row(2, "clamp", ref)]}
        self.write_answers({1: one, 2: two(None, faces=[CLAMP_BLOCK])})
        got = f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        self.assertIn("独立設計の要素", got["reason"])
        self.assertIn("D2", got["reason"])
        self.assertNotIn("D1 が", got["reason"], "項目 1 の答えが受けた D1 は、項目 2 の答えに無くても数える")
        self.write_answers({1: one, 2: two("D2", faces=[CLAMP_BLOCK])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        self.assertEqual([it.get("refs") for it in f.carry()["items"]], [["D1"], ["D2"]])
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                                         approach="clamp の上限の枝で hi を返し、上限ちょうどの値はそのまま返す（定義どおり）")],
               rnd=2, answers=FIXED)
        self.prepped()
        self.assertEqual(self.converge.carried_refs(self.b(), [2]), {"D1"})
        self.write_answers({2: {**two(None, resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        got = f.accept(tree=summary({2: []}))
        self.assertFalse(got["ok"], got)
        self.assertIn("D2", got["reason"])
        self.write_answers({2: {**two("D2", resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        self.ok(f.accept(tree=summary({2: []})))

    def test_carried_notes_drop_units_the_plan_dropped(self):
        """元 test_carried_notes_drop_units_the_plan_dropped（#387）: 2 往復目の案が落とした単位を指す前の往復の suggest の穴は、その単位を
        外して持ち越し、指す単位が残らなければ持ち越さない。往復の行の notes は元のまま"""
        f = self.flow
        median = "stats.py median: 偶数の長さで中央の 2 つを平均しない"
        f.units.append({"key": median, "label": "block", "reason": "中央の 2 つを平均しない"})
        f.judgment(precedents=PRECEDENTS)
        clamp = item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")])
        f.plan([{**item(UNIT_MEAN, 1), "unit_keys": [UNIT_MEAN, median]}, clamp])
        self.prepped()
        both = {**face("item1-mean-median-note", severity="suggest",
                       why="mean と median が同じ空の列の扱いを別々に書くと、後で片方だけ直りうる"), "unit_keys": [UNIT_MEAN, median]}
        only = face("item1-median-note", unit=median, severity="suggest", why="median の docstring が偶数の長さの扱いを言っていない")
        self.write_answers({1: answer(1, faces=[both, only]), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        first = f.carry()
        f.plan([item(UNIT_MEAN, 1), clamp], rnd=2, answers=FIXED)
        self.prepped()
        self.write_answers({1: answer(1), 2: {**answer(2, resolved=[CLAMP_BLOCK["key"]]), "hits": []}}, syn=synergy())
        self.ok(f.accept(tree=summary({1: [], 2: []})))
        self.assertEqual([(x["key"], x["unit_keys"]) for x in f.read("review.json")["faces"]], [(both["key"], [UNIT_MEAN])])
        self.assertEqual(f.carry()["outcome"], self.converge.CLEAN)
        self.assertEqual(f.prior["passes"][0]["notes"], [both, only])
        self.assertEqual(first["notes"], [both, only])
        b = self.b()
        self.converge.note_plan(b, [row["row"] for row in f.prior["passes"][0]["items"]])
        self.assertEqual([(x["key"], x["unit_keys"]) for x in self.converge.carried_notes(b)],
                         [(both["key"], [UNIT_MEAN, median]), (only["key"], [median])],
                         "後の案が戻した単位は、2 往復目に絞って控えた写しでなく審査役の書いた穴の単位から戻る")

    def test_tree_item_answer_relabel_to_peripheral_needs_a_new_why(self):
        """元 test_tree_item_answer_relabel_to_peripheral_needs_a_new_why: 項目の下請けの答えでも、前の往復で中央だった block の key を
        peripheral に付け替えて why が前の往復と同じ字なら拒む（converge.relabel_gaps）。why を書き直せば受ける"""
        f = self.flow
        f.inputs["tree"] = "on"
        self.first_pass_blocks_item_2()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")], approach="clamp の上限の枝で hi を返す")],
               rnd=2, answers=[{"key": CLAMP_BLOCK["key"], "handled": "fixed", "how": "上限の枝で hi を返す"}])
        self.prepped()
        same = {**CLAMP_BLOCK, "reach": self.converge.PERIPHERAL}
        self.write_answers({2: {**answer(2, faces=[same]), "hits": []}})
        got = f.accept(tree=summary({2: [same["key"]]}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        self.assertIn(f"{CLAMP_BLOCK['key']} を前の往復の中央", got["reason"])
        moved = {**same, "why": "直しの後は上限の扱いが試験の材料の言い回しだけに残り、どの害の定義にも当たらない"}
        self.write_answers({2: {**answer(2, faces=[moved]), "hits": []}})
        self.ok(f.accept(tree=summary({2: [moved["key"]]})))

    def test_resolved_suggest_not_owed_again_in_tree(self):
        """元 test_resolved_suggest_not_owed_again_in_tree: 開いた項目 2 に挙げた suggest s を 2 往復目の審査が resolved に入れた往復は通り、
        持ち越しの写しが返答の faces に残っても、その次の往復の答えも項目 2 の下請けの照らしも s を求めない。新しい block は求める。
        3 往復目の項目 2 の答えが s をもう一度 resolved に書いても通る。どの往復にも無い key は拒まれ、閉じた項目 1 の suggest は項目 2 の
        範囲の外で拒まれる。一括の入口（resolved_gaps）は同じ項目 1 の suggest を通す"""
        f = self.flow
        cv = self.converge
        f.inputs["tree"] = "on"
        second = face("item2-clamp-lower-branch", UNIT_CLAMP)
        note = face("item2-clamp-docstring-note", UNIT_CLAMP, severity="suggest",
                    why="clamp の docstring が上限ちょうどの値の扱いを言っていないので、直した後に読み手が取り違えうる")
        mean_note = face("item1-mean-docstring-note", UNIT_MEAN, severity="suggest",
                         why="mean の docstring が空の列の扱いを言っていないので、直した後に読み手が取り違えうる")
        self.prepped()
        self.write_answers({1: answer(1, faces=[mean_note]), 2: answer(2, faces=[CLAMP_BLOCK, second, note])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"], second["key"]]})))
        f.carry()
        two = item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                   approach="clamp の上限の枝で hi を、下限の枝で lo を返し、境の値はそのまま返す（定義どおり）")
        f.plan([item(UNIT_MEAN, 1), two], rnd=2,
               answers=[{"key": x["key"], "handled": "fixed", "how": "枝を直し、境の値の扱いと docstring を書いた"}
                        for x in (CLAMP_BLOCK, second, note)])
        self.prepped()
        fresh = face("item2-clamp-boundary-value", UNIT_CLAMP)
        self.write_answers({2: {**answer(2, faces=[fresh], resolved=[CLAMP_BLOCK["key"], second["key"], note["key"]]), "hits": []}})
        self.ok(f.accept(tree=summary({2: [fresh["key"]]})))
        self.assertIn(note["key"], [x["key"] for x in f.read("review.json")["faces"]], "持ち越しの写しは今のまま返答に残る")
        self.assertEqual(f.carry()["outcome"], cv.AGAIN)
        fixed = [{"key": fresh["key"], "handled": "fixed", "how": "境の値の扱いを枝を分けずに書き直した"}]
        self.assertEqual(cv.answer_gaps({**f.prior, "open": {}}, fixed), [])
        three = item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                     approach="clamp の上限の枝で hi を、下限の枝で lo を返し、境の値は枝を分けずに定義どおり返す")
        f.plan([item(UNIT_MEAN, 1), three], rnd=3, answers=fixed)
        self.prepped()
        b = self.b()
        self.assertNotIn(note["key"], cv.item_blocks(b, 2))
        self.assertIn(fresh["key"], cv.item_blocks(b, 2))
        owed = [CLAMP_BLOCK["key"], second["key"], fresh["key"]]
        allowed = {*owed, note["key"]}
        doc = cv.read(b)
        self.assertEqual(cv.resolvable_keys(doc, 2), allowed)
        self.assertEqual(cv.resolvable_keys(doc), {*allowed, mean_note["key"]})

        def tried(key):
            self.write_answers({2: {**answer(2, resolved=[*owed, key]), "hits": []}}, syn=synergy())
            return f.accept(tree=summary({2: []}))

        unknown = tried("item2-no-such-key")
        self.assertFalse(unknown["ok"], unknown)
        self.assertIn("item2-no-such-key", unknown["reason"])
        other = tried(mean_note["key"])
        self.assertFalse(other["ok"], other)
        self.assertIn(f"$.resolved: resolved の {mean_note['key']} は項目 2 の前の往復の block と suggest に無い", other["reason"])
        self.assertNotIn(mean_note["key"], "\n".join(cv.resolved_gaps(self.b(), [], [*owed, mean_note["key"]])))
        self.ok(tried(note["key"]))

    def second_pass_item(self, first=None, edit=None, edit_fields=None, notes=()) -> str:
        """2 項目の案（first。既定は setUp の案）の 1 往復目は項目 2 だけ block（notes は項目 2 に付けた suggest の穴）。項目 2 の行を
        edit が、項目 2 の works の欄を edit_fields が直した後の 2 往復目の項目 2 の材料のファイル"""
        f = self.flow
        f.inputs["tree"] = "on"
        rows = first or [item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")])]
        self.first_pass_blocks_item_2(notes=notes, rows=rows)
        fixed = copy.deepcopy(rows)
        field_rows = [fields(x["unit_keys"][0]) for x in fixed]
        if edit is not None:
            edit(fixed[1])
        if edit_fields is not None:
            edit_fields(field_rows[1])
        f.plan(fixed, rnd=2, field_rows=field_rows,
               answers=[{"key": x["key"], "handled": "fixed", "how": "上限の枝を hi に直し、境の値の扱いを書いた"}
                        for x in (CLAMP_BLOCK, *notes)])
        self.prepped()
        return self.item_text(2)

    def test_item_history_names_owed_suggest(self):
        """元 test_item_history_names_owed_suggest: 1 往復目に開いた項目 2 へ block と suggest s を挙げた後、2 往復目の項目 2 の材料のファイルは
        前の往復の答えの要る穴の見出しの下に block の行と suggest s の行と、それぞれへの修正案の役の答えを持つ"""
        note = face("item2-clamp-docstring-note", UNIT_CLAMP, severity="suggest",
                    why="clamp の docstring が上限ちょうどの値の扱いを言っていないので、直した後に読み手が取り違えうる")
        text = self.second_pass_item(notes=[note])
        history = text[text.index(self.heads["history"]):]
        self.assertIn(f"- pass 1 block {CLAMP_BLOCK['key']}: ", history)
        self.assertIn(f"- pass 1 suggest {note['key']}: {note['why']}（{note['where']}）", history)
        self.assertIn(f"  - plan role's answer {note['key']}: fixed（", history)

    def test_tree_item_contract_change_names_fields_without_the_whole(self):
        """元 test_tree_item_contract_change_names_fields_without_the_whole（#662）: 2 往復目、約束の欄（allowed_paths）に 1 行足しただけの
        開いた項目の材料のファイルは、変わった欄の名を言い、足した行を差分に載せる。項目の案の全体は貼らない"""
        text = self.second_pass_item(edit_fields=lambda row: row["allowed_paths"].append("README.md"))
        self.assertIn(self.material.LABELS["contract"].format(fields="allowed_paths"), text)
        self.assertIn("+ allowed_paths: README.md", text[text.index(self.material.LABELS["diff"]):])
        self.assertNotIn(self.material.LABELS["item_plan"].format(n=2), text)

    def test_second_pass_item_brief_has_only_changed_sentences(self):
        """元 test_second_pass_item_brief_has_only_changed_sentences: 開いた項目の approach の 1 文を書き換え、files の頭に行を 1 つ足した
        2 往復目の材料のファイルは、足した文と消した文を場所つきで持ち、変わっていない文と閉じた項目の案を持たない。頼み（元
        SUB_ITEM_DIFF_ASK）は下請けの指示の 2 往復目の段落に在る"""
        kept, gone, came = "clamp は lo より小さい値を lo に寄せる。", "上限の枝はそのまま。", "上限の枝で hi を返す。"

        def edit(row):
            row["approach"] = kept + came
            row["files"] = [frow("stats.py", "clamp_guard"), *row["files"]]
        text = self.second_pass_item(first=[item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")],
                                                                     approach=kept + gone)], edit=edit)
        diff = text[text.index(self.material.LABELS["diff"]):]
        self.assertIn(f"- approach: {gone}", diff)
        self.assertIn(f"+ approach: {came}", diff)
        self.assertIn("clamp_guard", diff)
        self.assertIn(LATER_ITEM_ASK, self.brief())
        for unchanged in (kept, "1 行の直しで済む", f"{PLAN_MARK} 項目 1 の直し"):
            self.assertNotIn(unchanged, text, unchanged)
        self.assertNotIn(self.material.LABELS["item_plan"].format(n=2), text)

    def test_narrows_gate_marks_only_change_stays_diff(self):
        """元 test_narrows_gate_marks_only_change_stays_diff: narrows の行の決め手の欄（world・recommend）の長い文を丸ごと書き直しただけの
        直しは、約束の欄の変更に数えず差分のまま（決め手の欄は差分に載らない）"""
        narrow = {**NARROW, "no_narrow": "空の列で例外を投げる今の動きを残すと直したい呼び手が成り立たない",
                  "decided_by": "", "undecided_because": "", "fences": [],
                  "world": "Python 公式の statistics.mean は空の列で例外を投げる",
                  "recommend": {"answer": "continue", "why": "空の列の例外は前から同じで、能力は減らない", "note": "今の動きのまま通す"}}
        first = [item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")], narrows=[narrow])]
        long_world = "".join(f"事例 {i}: {c} の標準の平均は空の列で StatisticsError を投げ、呼び手が捕まえて 0 を返す慣習が広い。"
                             for i, c in enumerate("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥", 1))
        long_why = "".join(f"理由 {i}: {c} の呼び手は例外の型を前から同じに受けるので、通しても能力は減らず、利用者の経路も変わらない。"
                           for i, c in enumerate("甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥", 1))

        def reword(row):
            row["narrows"][0]["world"] = long_world
            row["narrows"][0]["recommend"] = {"answer": "continue", "why": long_why, "note": "今の動きのまま通してよい"}

        text = self.second_pass_item(first=first, edit=reword)
        self.assertIn(self.material.LABELS["diff"], text)
        self.assertNotIn("contract fields changed", text)
        self.assertNotIn(long_world[:30], text, "決め手の欄は差分に載らない")

    def test_precedent_sources_are_fetched_once_per_run(self):
        """元 test_precedent_sources_are_fetched_once_per_run: 出典は run の中で 1 度だけ開く（控えは pass.json の precedent_checks で line が
        port prior に運ぶ）"""
        f = self.flow
        f.inputs["tree"] = "on"
        self.prepped()
        one, two = self.item_text(1), self.item_text(2)
        self.assertIn("statistics.mean", one)
        self.assertNotIn("numpy.clip", one)
        self.assertEqual((len(fetch_ids(one)), len(fetch_ids(two))), (1, 1))
        self.write_answers({1: answer(1), 2: answer(2, faces=[CLAMP_BLOCK])}, fetched=False)
        got = f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]}))
        self.assertFalse(got["ok"])
        self.assertIn("precedents", got["reason"])
        self.write_answers({1: answer(1), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.ok(f.accept(tree=summary({1: [], 2: [CLAMP_BLOCK["key"]]})))
        self.assertEqual(len(f.read("precedent-checks.json")), 2)
        self.assertEqual(len(f.read("pass.json")["precedent_checks"]), 2)
        f.carry()
        f.plan([item(UNIT_MEAN, 1), item(UNIT_CLAMP, 2, approach="clamp の上限の枝で hi を返す（直した）",
                                         files=[frow("stats.py", "clamp")])], rnd=2, answers=FIXED)
        self.prepped()
        text = self.item_text(2)
        self.assertIn("numpy.clip", text)
        self.assertIn(f"— {self.tree.PRECEDENT_LABELS['cached']}: found=", text)
        self.assertEqual(fetch_ids(text), [])

    def test_surplus_rows_dropped(self):
        """元 test_surplus_rows_dropped（元 test_surplus_precedent_row_dropped・test_surplus_hit_dropped）: 余りの行は拒まずに trace に残して
        捨てる"""
        f = self.flow
        self.prepped()
        b = self.b()
        pre = self.tree.precedent_plan(b, self.converge.open_items(b))
        other = next(x["id"] for x in pre[1] if x["fetch_by"] == 1)
        own = [x["id"] for x in pre[2] if x["fetch_by"] == 2]
        stray_pre = {"id": other, "found": False, "quote": "余りの確かめ（この項目の下請けが開く出典でない）"}
        stray_hit = {"id": "H-not-in-ripple", "answer": "no_effect", "why": NO_EFFECT}
        mine = [{"id": i, "found": True, "quote": "出典は在り、単位の問題に当たっている"} for i in own]
        two = answer(2)
        self.write_answers({1: answer(1), 2: {**two, "hits": two["hits"] + [stray_hit], "precedents": mine + [stray_pre]}},
                           syn=synergy())
        self.ok(f.accept(tree=summary({1: [], 2: []})))
        rows = json.dumps([x for x in self.surplus_rows() if x.get("item") == 2], ensure_ascii=False)
        self.assertIn(other, rows)
        self.assertIn(stray_hit["id"], rows)
        self.assertNotIn(stray_pre["quote"], json.dumps(f.read("precedent-checks.json"), ensure_ascii=False))
        self.assertEqual([h["id"] for h in f.carry()["items"][1]["hits"]], ["h1"])

    def test_missing_precedent_row_refused_without_surplus_lines(self):
        """元 test_missing_precedent_row_refused_without_surplus_lines"""
        f = self.flow
        self.prepped()
        b = self.b()
        pre = self.tree.precedent_plan(b, self.converge.open_items(b))
        other = next(x["id"] for x in pre[1] if x["fetch_by"] == 1)
        own = [x["id"] for x in pre[2] if x["fetch_by"] == 2]
        self.write_answers({1: answer(1)})
        stray = {"id": other, "found": False, "quote": "余りの確かめ（この項目の下請けが開く出典でない）"}
        self.write_answers({2: {**answer(2), "precedents": [stray]}}, syn=synergy(), fetched=False)
        got = f.accept(tree=summary({1: [], 2: []}))
        self.assertFalse(got["ok"])
        self.assertIn(f"先行例の出典 {own[0]} の確かめの行が無い", got["reason"])
        self.assertNotIn("開く出典でない", got["reason"])

    def test_item_and_synergy_schema_take_origins(self):
        """元 test_item_and_synergy_schema_take_origins: 項目と相乗りの下請けの答えの型は、任意の欄 origins（converge.ORIGIN_SCHEMA）を持つ"""
        self.prepped()
        b = self.b()
        for schema in (self.tree.item_schema(b), self.tree.synergy_schema(b)):
            self.assertEqual(schema["properties"][self.converge.ORIGINS], self.converge.ORIGIN_SCHEMA)
            self.assertNotIn(self.converge.ORIGINS, schema["required"])

    def test_origin_ask_only_where_writers_are(self):
        """元 test_origin_ask_only_where_writers_are: 出自の頼みは書き手の居る層にだけ置く: 1 往復目はどの指示にも頼みが無く、2 往復目の
        束ね役の指示は出自の頼みを持たない。下請けの指示は 2 往復目の頼みと出自の頼みを、相乗りのファイルは出自の頼みを持つ。往復の行の
        origins は下請けの答えのファイルの申告（束ね役の型の外の origins が受け付けまで届いても使わない）"""
        f = self.flow
        cv = self.converge
        main = self.prepped()
        for text in (main, *(p.read_text(encoding="utf-8") for p in sorted((f.place / "items").glob("*.md")))):
            self.assertNotIn(ORIGIN_ASK, text)
            self.assertNotIn(REREVIEW_ASK, text)
        self.write_answers({1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2, faces=[CLAMP_BLOCK])})
        self.ok(f.accept(tree=summary({1: [MEAN_BLOCK["key"]], 2: [CLAMP_BLOCK["key"]]})))
        f.carry()
        f.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾き、分母を len(xs) に直す"),
                item(UNIT_CLAMP, 2, approach="clamp の上限の枝で hi を返す", files=[frow("stats.py", "clamp")])],
               rnd=2, answers=[{"key": x["key"], "handled": "fixed", "how": "項目の手順を書き直して確かめた"} for x in (MEAN_BLOCK, CLAMP_BLOCK)])
        main = self.prepped()
        self.assertNotIn(ORIGIN_ASK, main, "束ね役の指示に書き手の居ない頼みを貼らない")
        self.assertIn(REREVIEW_ASK, self.brief())
        self.assertIn(ORIGIN_ASK, self.brief())
        self.assertIn(ORIGIN_ASK, f.text("items/synergy.md"))
        again = face("item1-mean-new-hole-0")
        claim = [{"key": again["key"], "origin": cv.ORIGIN_INTRODUCED}]
        self.write_answers({1: {**answer(1, faces=[again], resolved=[MEAN_BLOCK["key"]]), cv.ORIGINS: claim},
                            2: answer(2, resolved=[CLAMP_BLOCK["key"]])})
        wrong = [{"key": again["key"], "origin": cv.ORIGIN_MISSED}]
        self.ok(f.accept(tree={**summary({1: [again["key"]], 2: []}), cv.ORIGINS: wrong}))
        row = f.carry()
        self.assertEqual((row["outcome"], row["origins"], row["origins_claimed"]),
                         (cv.AGAIN, {again["key"]: cv.ORIGIN_INTRODUCED}, []))

    def test_review_tree_off_second_pass_takes_checked_origins(self):
        """元 test_review_tree_off_second_pass_takes_checked_origins: 審査役 1 つの 2 往復目: 指示に出自の頼みが在る（1 往復目には無い）。
        返答の origins の型は node の output_format が持ち、正しい申告は往復の行に照らして入る"""
        f = self.flow
        cv = self.converge
        f.inputs["tree"] = "off"
        self.assertFalse(f.intake()["tree"])
        self.assertNotIn(ORIGIN_ASK, f.prompt())
        self.ok(f.accept(review(MEAN_BLOCK)))
        f.carry()
        f.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾いて分母を直す"), item(UNIT_CLAMP, 2)], rnd=2,
               answers=[{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足した"}])
        self.assertFalse(f.intake()["tree"])
        text = f.prompt()
        self.assertIn(REREVIEW_ASK, text)
        self.assertIn(ORIGIN_ASK, text)
        new = face("mean-boundary-value-0")

        def sent(claim):
            return review(new, resolved=[MEAN_BLOCK["key"]], origins=claim)

        fmt = self.tree.files.node_schema("review")
        for claim in ([{"key": new["key"], "origin": "guessed"}], [{"key": [new["key"]], "origin": cv.ORIGIN_MISSED}]):
            with self.subTest(claim=claim):
                errs = self.tree.validate_schema(sent(claim), fmt)
                self.assertTrue(any(cv.ORIGINS in e for e in errs), errs)
        self.ok(f.accept(sent([{"key": new["key"], "origin": cv.ORIGIN_REPHRASED, "of": MEAN_BLOCK["key"]}])))
        row = f.carry()
        self.assertEqual((row["origins"], row["origins_claimed"]), ({new["key"]: cv.ORIGIN_REPHRASED}, []))

    def test_review_tree_off_is_one_reviewer(self):
        """元 test_review_tree_off_is_one_reviewer: port tree が off なら 2 項目でも審査役 1 つ"""
        f = self.flow
        f.inputs["tree"] = "off"
        self.assertFalse(f.intake()["tree"])
        got = f.prep()
        self.assertFalse(got["tree"])
        self.assertNotIn(BUNDLE_HEAD, got["prompt"])
        self.assertFalse((f.place / "items").exists())
        self.ok(f.accept(review()))

    def test_review_tree_on_one_item_is_tree(self):
        """元 test_review_tree_on_one_item_is_tree"""
        f = self.flow
        f.inputs["tree"] = "on"
        f.plan([item(UNIT_MEAN, 1)])
        self.assertTrue(f.intake()["tree"])

    def test_tree_on_one_item_without_answer_file_is_rejected(self):
        """元 test_tree_on_one_item_without_answer_file_is_rejected: 木の往復は、1 項目・覆っていない当たり無しでも答えのファイルが無ければ
        『答えのファイルが無い』で拒む（束ね役の返答を単独の審査として通さない）"""
        f = self.flow
        f.inputs["tree"] = "on"
        f.plan([item(UNIT_MEAN, 1)])
        f.ripple({"items": [], "overlaps": []})
        self.prepped()
        got = f.accept(tree=summary({1: []}))
        self.assertFalse(got["ok"], got)
        self.assertTrue(got["reason"].startswith(self.take.TREE_REJECT), got["reason"])
        self.assertIn("答えのファイルが無い", got["reason"])
        self.assertFalse((f.place / "pass.json").exists())
        self.write_answers({1: answer(1)})
        self.ok(f.accept(tree=summary({1: []})))

    def test_prep_returns_the_open_tree(self):
        """元 test_prep_returns_the_open_tree: 支度の返りの tree は、材料の枝でも出し直しの枝（prev が false）でも入口の tree と同じ値
        （review-prep の返りが束ね役の組と単独の組を振り分ける）"""
        f = self.flow
        self.assertIs(f.intake()["tree"], True)
        self.assertIs(f.prep()["tree"], True)
        self.assertFalse(f.accept(tree=summary({1: [], 2: []}))["ok"])
        again = f.prep(prev="false")
        self.assertIs(again["resubmit"], True)
        self.assertIs(again["tree"], True)
        f.inputs["tree"] = "off"
        self.assertIs(f.intake()["tree"], False)
        self.assertIs(f.prep()["tree"], False)
        self.assertFalse(f.accept(review(face("stray-policy-face-001", kind="policy")))["ok"])
        again = f.prep(prev="false")
        self.assertIs(again["resubmit"], True)
        self.assertIs(again["tree"], False)

    def test_review_tree_auto_one_item_plan_is_one_reviewer(self):
        """元 test_review_tree_auto_one_item_plan_is_one_reviewer（元 test_single_item_plan_needs_no_synergy）"""
        f = self.flow
        f.plan([item(UNIT_MEAN, 1)])
        f.ripple({"items": [], "overlaps": []})
        self.assertFalse(f.intake()["tree"])
        f.prep()
        self.ok(f.accept(review()))

    def test_review_tree_auto_counts_open_items_per_pass(self):
        """元 test_review_tree_auto_counts_open_items_per_pass: 2 項目の 1 往復目は木、項目 1 だけが開いた 2 往復目は審査役 1 つ"""
        f = self.flow
        self.prepped()
        self.write_answers({1: answer(1, faces=[MEAN_BLOCK]), 2: answer(2)})
        self.ok(f.accept(tree=summary({1: [MEAN_BLOCK["key"]], 2: []})))
        row = f.carry()
        self.assertEqual([it["state"] for it in row["items"]], [self.converge.OPEN, self.converge.CLOSED])
        f.plan([item(UNIT_MEAN, 1, approach="mean は空の列を先に弾き、分母を len(xs) に直す"),
                item(UNIT_CLAMP, 2, files=[frow("stats.py", "clamp")])], rnd=2,
               answers=[{"key": MEAN_BLOCK["key"], "handled": "fixed", "how": "空の列を先に弾く手順を案に足した"}])
        self.assertFalse(f.intake()["tree"])
        got = f.prep()
        self.assertNotIn(BUNDLE_HEAD, got["prompt"])
        self.assertFalse((f.place / "items").exists())
        self.ok(f.accept(review(resolved=[MEAN_BLOCK["key"]])))
        self.assertEqual(f.carry()["outcome"], self.converge.CLEAN)

    def test_tree_port_words(self):
        """元 lib/tests/test_boardview.py の RulesCase.test_unattended_and_tree_words の木の語の半分: port tree の on・off・auto（auto は開いた
        項目が 2 つ以上なら木）。ほかの語は入口が落とす（due が偽）"""
        f = self.flow
        for word, tree in (("on", True), ("off", False), ("auto", True), ("", True)):
            with self.subTest(tree=word):
                f.inputs["tree"] = word
                self.assertIs(f.intake()["tree"], tree)
        f.plan([item(UNIT_MEAN, 1)])
        for word, tree in (("on", True), ("auto", False)):
            with self.subTest(tree=word, items=1):
                f.inputs["tree"] = word
                self.assertIs(f.intake()["tree"], tree)
        got = f.run.script("intake", **{**f.inputs, "tree": "重厚"})
        self.assertFalse(got["due"], got)
        self.assertIn("tree", got["reason"])


class BriefCase(TreeBase):
    """下請けの指示のファイル（items/brief.md）と項目の材料のファイル（items/item-<n>.md）の分け（設計書 5.3・5.6 で足した試験）"""

    def test_brief_is_one_file_for_every_item_and_heads_the_synergy_file(self):
        """下請けの指示は全部の項目で同じバイトの 1 本のファイル（今の brief_head の「プロンプトのキャッシュのため同じバイト」）。束ね役は
        その 1 本を名指し、相乗りのファイルは同じバイトの指示で始まる"""
        text = self.prepped()
        brief = self.brief()
        self.assertIn(f"Read {self.flow.place / 'items' / 'brief.md'} and <the item's file> with Read", text)
        self.assertTrue(self.flow.text("items/synergy.md").startswith(brief))
        for n in (1, 2):
            self.assertNotIn(brief[:200], self.item_text(n))

    def test_item_files_carry_no_instruction_text(self):
        """項目の材料のファイルは指示の文を持たない: 見出しは ITEM_HEADS と材料の札だけで、下請けの指示の文（読み方・答え方・先行例の
        札の読み方）は下請けの指示のファイルにだけ在る"""
        self.flow.design()
        self.prepped()
        brief = self.brief()
        paras = [p for p in brief.split("\n\n") if len(p) > 60 and not p.startswith(("```", "{", "Repository:"))]
        self.assertGreater(len(paras), 10)
        for n in (1, 2):
            text = self.item_text(n)
            with self.subTest(item=n):
                for p in paras:
                    self.assertNotIn(p, text)
                for word in ("Read ", "Write ", "do not", "Do not"):
                    self.assertNotIn(word, text)
                heads = [line for line in text.splitlines() if line.startswith("#")]
                labels = [self.heads["item"].format(n=n), self.heads["units"].format(n=n), self.heads["precedents"],
                          self.material.LABELS["item_plan"].format(n=n), self.material.MAT_HEADS["map_items"],
                          self.material.LABELS["ripple"].format(n=n)]
                self.assertEqual([h for h in heads if h not in labels], [], heads)
        for label in ("How each sub-agent answers", "### Precedent sources of this item", "### Errors in the previous answer",
                      "### Hits answered in a previous pass", "`fetch`", "`by item <m>`"):
            self.assertIn(label, brief)

    def test_brief_carries_the_query_rule_without_spawns(self):
        """下請けの指示に外への検索の決まり（共通の断片 query-rule）が在る。下請けは下請けを起こさないので段落 spawns は無い。束ね役の
        指示も spawns を持たない（決まりは下請けの指示に在る）"""
        text = self.prepped()
        brief = self.brief()
        rule = (kit.SHARED / "prompts" / "query-rule.md").read_text(encoding="utf-8").split("\n", 1)[1]   # 1 行目は道具の印（指示には出ない）
        head = rule.split("\n<!-- if spawns -->", 1)[0].rstrip("\n")
        self.assertIn(head, brief)
        self.assertNotIn(SPAWNS, brief)
        self.assertNotIn(SPAWNS, text)


if __name__ == "__main__":
    unittest.main()
