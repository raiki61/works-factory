"""plan が読む、ほかのブロックが書いたファイルの鍵（線への申し送り S20）。

judge・plan-review・fix の書き手の関数で作ったファイルを、plan の読み手（lib/planfile.py）に通す。書き手と読み手が別々に鍵の字を
持つので、片方だけ字を変えると欄が黙って空に読まれる（plan-review の review.json が壁打ちの欄 resolved を落とし、plan の往復の控えが
前の往復の答えの要る穴（block と開いた項目の suggest）の行き先を読めなかった）。
"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

from lib.tests import test_judge_accept as TJ  # noqa: E402
from tests.workflows import test_plan_review as TR  # noqa: E402
import boardview  # noqa: E402
import conflict  # noqa: E402
import converge  # noqa: E402
import planfile  # noqa: E402


class CrossKeysCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()

    def judged(self) -> tuple:
        """判定のブロックの受け付け（judge_accept.take）が書いた judgment.json と、その返りの開いた単位"""
        case = TJ._JudgeBase("run")
        case.setUp()
        self.addCleanup(case.doCleanups)
        reply = TJ._judge_ok()   # 1 つ目の単位を出どころにした保留の fork（判定の問いの台帳の kind・status・origin）
        reply["questions"] = [{"key": "岐路", "kind": "fork", "status": "held", "reason": "推し: A——安い", "origin": TJ._MEAN,
                               "options": ["A: 安い", "B: 堅い"]}]
        reply["precedents"].append({"key": "岐路", "problem": "選び方の問題", "source": "文書の節", "verdict": "adopt",
                                    "reason": "当たった", "undecided_because": "先例が割れて決まらない（①）"})
        got = case.take(reply)
        self.assertIs(got["ok"], True, got["reason"])
        return case.judgment(), got["open_units"]

    def reviewed(self) -> list:
        """事前審査のブロックの受け付けと返す節が 2 往復で書いた review.json（1 往復目は block、2 往復目はそれを resolved に）"""
        case = TR.ConvergeCase("test_clean_first_pass")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.first()
        run = case.run_
        run.open()
        run.out("review_prep")
        self.assertTrue(run.accept(TR.review(resolved=[TR.MEAN_BLOCK["key"]]))["ok"])
        run.out("result")
        return [json.loads((boardview.pass_dir(run.folder, k) / boardview.REVIEW_FILE).read_text(encoding="utf-8")) for k in (1, 2)]

    def put_round(self, plan_dir: pathlib.Path, k: int, review, reply) -> None:
        d = plan_dir / f"r{k}"
        planfile._write_json(d / planfile.ROUND_FILE, {"round": k, "mode": "plan", "go": True, "why": "", "items": [],
                                                        "structure": "structure"})
        if review is not None:
            planfile._write_json(d / planfile.REVIEW_FILE, review)
        if reply is not None:
            planfile._write_json(d / planfile.REPLY_FILE, reply)

    def test_plan_reads_what_judge_review_fix_write(self):
        # judge: 判定の units（key・label・disposition）と問いの台帳（kind・status・origin）を plan の直す義務が同じに読む
        judgment, opened = self.judged()
        owed, slots, _ = planfile.plan_slots(judgment)
        self.assertEqual((owed, slots), (set(opened) - {TJ._MEAN}, set(opened)))
        self.assertIn(TJ._MEAN, opened)

        # plan-review: 受け付けた返答の resolved（前の往復の答えの要る穴（block と開いた項目の suggest）の行き先）を plan の往復の控えが読む
        first, second = self.reviewed()
        plan_dir = self.tmp / "plan"
        plan1 = {"plan": [TR.item(TR.UNIT_MEAN, 1), TR.item(TR.UNIT_CLAMP, 2)]}
        self.put_round(plan_dir, 1, None, plan1)
        self.put_round(plan_dir, 2, first, {**plan1, converge.ANSWERS: TR.ConvergeCase.ANSWERS})
        self.put_round(plan_dir, 3, second, None)
        record = planfile.converge_record(plan_dir)
        self.assertEqual([p["resolved"] for p in record["passes"]], [[], [TR.MEAN_BLOCK["key"]]])
        self.assertEqual(record["outcome"], converge.CLEAN)

        # fix: 申し出と裁定（conflict.park・apply_rulings が書く conflicts.json）の行を、案の直しの材料が項目ごとに引く
        place = self.tmp / "fix"
        place.mkdir()
        claim = {"unit_key": TR.UNIT_MEAN, "between": ["案の項目 1", "test_stats.py"], conflict.WHY_FIELD: "案は分母を変えるが試験は旧い分母を断言する",
                 conflict.WHICH_FIELD: "plan", conflict.KIND_FIELD: "plan"}
        ids = conflict.park(place, [claim], source=conflict.FIX_SOURCE)
        conflict.apply_rulings(place, {ids[0]: {"decision": conflict.REPLAN, "text": "案の項目 1 を直す", "limits": [],
                                                conflict.PLAN_ITEMS: [1], conflict.PLAN_UNITS: [TR.UNIT_MEAN]}}, by="ruler")
        doc = json.loads((place / conflict.FILE).read_text(encoding="utf-8"))
        rows = planfile.conflict_rows(doc, 1, plan1["plan"][0])
        self.assertEqual([r["id"] for r in rows], ids)
        text = planfile.replan_section(1, plan1["plan"][0], rows)
        for word in ("案の項目 1 を直す", claim[conflict.WHY_FIELD], TR.UNIT_MEAN, conflict.REPLAN):
            self.assertIn(word, text)
        shutil.rmtree(place)


if __name__ == "__main__":
    unittest.main()
