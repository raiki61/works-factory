"""関所の項目の推し（gatemarks の recommend）と、無人の run が関所で止まった時の答えの下書き（gatemarks.answer_drafts）。
FAST: test_plan_gate の偽の盤面で写しの RL の human_gate を直に呼ぶ（盤面・git・子のプロセスなし）。

実の利用者の run ac9e02ab は無人の run で、直す前の関所に 2 件（方針の文書の柵 policy_doc）が挙がって止まった。関所の文の推しは
「判定の役が書いていない」と出て、機械が読める推しの答えはどこにも無く、次の run の依頼の下書き next-request.json は空だった。
役が関所に回す行に構造の推し recommend {answer, note, why} を書き、無人の run が関所で止まったら、項目ごとの答えの下書きを
next-request.json の answers に draft: true と出どころ source つきで置く。機械は関所に答えない（下書きを使う前に人が見直す）。
"""
import json
import pathlib
import sys
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
from lib.tests import test_plan_gate as TP  # noqa: E402
import gatemarks  # noqa: E402
import carry  # noqa: E402
import converge  # noqa: E402
import planblk  # noqa: E402

REC = {"answer": "continue", "note": "daemon だけを Recreate にする範囲で通す", "why": "Dagster 公式の chart が同じ分け方"}
NO_NARROW = "daemon を別の Deployment に分け、webserver は RollingUpdate に残す形を当たったが、決着済みの配置を組み替える"


class SchemaCase(unittest.TestCase):
    def test_recommend_schema_is_built_from_the_keys(self):
        """推しの欄の名は RECOMMEND_KEYS の 1 か所（頭が答えの enum、残りが RECOMMEND_MIN 字以上の文）"""
        schema = gatemarks.MARK_SCHEMA[gatemarks.RECOMMEND]
        self.assertEqual((schema["required"], list(schema["properties"])), (list(gatemarks.RECOMMEND_KEYS),) * 2)
        self.assertEqual(schema["properties"][gatemarks.RECOMMEND_KEYS[0]]["enum"], list(gatemarks.RECOMMEND_ANSWERS))

    def test_check_and_tail_read_the_keys(self):
        rec = {"pick": "stop", "scope": "daemon だけを止める", "because": "chart が同じ分け方"}
        with mock.patch.object(gatemarks, "RECOMMEND_KEYS", tuple(rec)):
            self.assertEqual(gatemarks._recommend_gap(rec), "")
            self.assertIn("（stop）——daemon だけを止める（理由: chart が同じ分け方）", gatemarks._push({gatemarks.RECOMMEND: rec}))
            draft = gatemarks._gate_draft("t", {gatemarks.RECOMMEND: rec}, gatemarks.NODES[0])
            self.assertIn("stop: daemon だけを止める（推す理由: chart が同じ分け方）", json.dumps(draft, ensure_ascii=False))

    def test_shape_text_is_built_from_the_keys(self):
        """役への頭と受け付けの拒み（planblk の 1 つを planfile・boardview が読む）が書かせる推しの形は 1 つの文 RECOMMEND_SHAPE
        で、その文は欄の名・答え・字の下限を持ち主から組む"""
        shape = gatemarks.RECOMMEND_SHAPE
        for word in (*gatemarks.RECOMMEND_KEYS, *gatemarks.RECOMMEND_ANSWERS, f"{gatemarks.RECOMMEND_MIN} 字以上"):
            self.assertIn(word, shape)
        self.assertIn(shape, planblk.RECOMMEND_REJECT)
        self.assertFalse(hasattr(gatemarks, "RECOMMEND_REJECT"))


class GapsCase(unittest.TestCase):
    def plan(self, rec):
        return {"plan": [{"narrows": [{**TP.NARROW, "no_narrow": NO_NARROW, **({"recommend": rec} if rec is not None else {})}]}]}

    def test_absent_and_good_recommend_pass(self):
        self.assertEqual(gatemarks.recommend_gaps("p2.fix_plan", self.plan(None)), [])
        self.assertEqual(gatemarks.recommend_gaps("p2.fix_plan", self.plan(REC)), [])

    def test_malformed_recommend_is_named(self):
        for bad in ({**REC, "answer": "maybe"}, {k: v for k, v in REC.items() if k != "why"}, "通す", {**REC, "note": ""}):
            with self.subTest(bad=bad):
                got = gatemarks.recommend_gaps("p2.fix_plan", self.plan(bad))
                self.assertEqual(len(got), 1, got)
                self.assertIn("plan[0].narrows[0]", got[0])

    def test_review_faces_are_checked_too(self):
        got = gatemarks.recommend_gaps("p2.plan_review", {"faces": [{**TP.FACE, "recommend": {"answer": "x"}}]})
        self.assertEqual(len(got), 1, got)
        self.assertIn("faces[0]", got[0])

    def test_review_stuck_recommend_is_checked_too(self):
        """返答の一番上の止まった時の推し（converge.STUCK_PUSH）も faces の行と同じ形で照らし、崩れていれば 1 行で名指す。
        整った推しと、欄の無い返答は通す"""
        reply = {"faces": [TP.FACE]}
        self.assertEqual(gatemarks.recommend_gaps("p2.plan_review", reply), [])
        self.assertEqual(gatemarks.recommend_gaps("p2.plan_review", {**reply, converge.STUCK_PUSH: REC}), [])
        for bad in ({**REC, "answer": "maybe"}, {k: v for k, v in REC.items() if k != "why"}, "通す", {**REC, "note": ""}):
            with self.subTest(bad=bad):
                got = gatemarks.recommend_gaps("p2.plan_review", {**reply, converge.STUCK_PUSH: bad})
                self.assertEqual(len(got), 1, got)
                self.assertIn(converge.STUCK_PUSH, got[0])
        self.assertEqual(gatemarks.recommend_gaps("p2.fix_plan", {**self.plan(REC), converge.STUCK_PUSH: "x"}), [])

    def test_split_takes_recommend_off_and_save_keeps_it(self):
        reply = self.plan(REC)
        bare, marks = gatemarks.split("p2.fix_plan", reply)
        self.assertNotIn(gatemarks.RECOMMEND, bare["plan"][0]["narrows"][0])
        self.assertEqual(marks[0][0][gatemarks.RECOMMEND], REC)


class IntakeCase(unittest.TestCase):
    def test_draft_answers_are_refused_with_how_to_use_them(self):
        """下書きのまま次の run の依頼に渡すと、機械の下書きが人の答えとして関所の問いに当たる。依頼の入口は draft・source の
        欄の在る行を拒み、見直し方を言う"""
        for row in ({"question": "q", "text": "t", "draft": True, "source": "s"}, {"question": "q", "text": "t", "source": "s"}):
            with self.subTest(row=row):
                with self.assertRaises(ValueError) as cm:
                    carry.parts({"findings": [], "answers": [row]})
                self.assertIn("下書き", str(cm.exception))
                self.assertIn("draft", str(cm.exception))

    def test_refusal_tells_gate_rows_from_ledger_rows(self):
        """拒否の文は、台帳の問いの行（draft と source を消せば使える）と関所の項目の行（次の run の関所の一言の材料で、依頼では
        何にも当たらないので消す）を分けて言う（審査の指摘）"""
        with self.assertRaises(ValueError) as cm:
            carry.parts({"findings": [], "answers": [{"question": "q", "text": "t", "draft": True, "source": "s"}]})
        self.assertIn("台帳の問い", str(cm.exception))
        self.assertIn("承認ノードの項目", str(cm.exception))

    def test_carry_ci_keeps_drafts_as_they_are(self):
        """CI の赤を足す口（carry_ci）は下書きの行で止まらず、そのまま残す（審査の再現: 無人の run の下書きで exit 2 だった）"""
        draft = {"question": "q", "text": "t", "draft": True, "source": "s"}
        got = carry.carry_ci({"findings": [], "prior_failures": [], "answers": [draft]}, ["tests/test_x.py::t"])
        self.assertEqual(got["answers"], [draft])
        self.assertEqual(len(got["prior_failures"]), 1)

    def test_reviewed_answer_passes(self):
        got = carry.parts({"findings": [], "answers": [{"question": "q", "text": "t"}]})
        self.assertEqual(got["answers"], [{"question": "q", "text": "t"}])


if __name__ == "__main__":
    unittest.main()
