"""承認ノードの項目の推し（gatemarks の recommend）の欄の形と照らし（recommend_gaps）と、下書きの答えを依頼の入口が拒むこと（carry）。

元は今の lib/tests/test_gate_drafts.py（docs/design/README.md の 9.5）。元の 13 本のうち、lib に残る物の試験をここに戻す:
SchemaCase の 2 本（推しの欄の型と、照らし・尾・下書きが欄の名を 1 か所から読む）・GapsCase の 5 本・IntakeCase の 4 本。
元は test_plan_gate の偽の盤面の行（TP.NARROW・TP.FACE）を借りたが、その試験は組み込みで消えたので、行はここに置く。
移った先の在る物: SchemaCase の test_rule_text_asks_for_recommend と test_shape_text_is_built_from_the_keys（役の頭の文
gatemarks.HEAD は plan の block の指示書へ、拒みの文 planblk.RECOMMEND_REJECT は plan の src/steps.py へ）は
tests/blocks/plan/test_shape.py の RecommendShapeCase。無人の run が推しで修正前の承認ノードを抜けるかは
tests/blocks/line/test_gate_drafts.py。
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
import carry  # noqa: E402
import converge  # noqa: E402
import gatemarks  # noqa: E402

REC = {"answer": "continue", "note": "daemon だけを Recreate にする範囲で通す", "why": "Dagster 公式の chart が同じ分け方"}
NO_NARROW = "daemon を別の Deployment に分け、webserver は RollingUpdate に残す形を当たったが、決着済みの配置を組み替える"
# 元 lib/tests/test_plan_gate.py の NARROW・FACE（修正案の狭める行と事前審査の穴の行）
NARROW = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}
FACE = {"key": "clamp の上限の意味が変わる", "unit_keys": ["u"], "kind": "regression", "where": "stats.py clamp",
        "why": "上限を超えた値に lo を返す今の振る舞いに頼る呼び手が在れば結果が変わる", "severity": "block"}
BAD = ({**REC, "answer": "maybe"}, {k: v for k, v in REC.items() if k != "why"}, "通す", {**REC, "note": ""})


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


class GapsCase(unittest.TestCase):
    def plan(self, rec):
        return {"plan": [{"narrows": [{**NARROW, "no_narrow": NO_NARROW, **({"recommend": rec} if rec is not None else {})}]}]}

    def test_absent_and_good_recommend_pass(self):
        self.assertEqual(gatemarks.recommend_gaps("p2.fix_plan", self.plan(None)), [])
        self.assertEqual(gatemarks.recommend_gaps("p2.fix_plan", self.plan(REC)), [])

    def test_malformed_recommend_is_named(self):
        for bad in BAD:
            with self.subTest(bad=bad):
                got = gatemarks.recommend_gaps("p2.fix_plan", self.plan(bad))
                self.assertEqual(len(got), 1, got)
                self.assertIn("plan[0].narrows[0]", got[0])

    def test_review_faces_are_checked_too(self):
        got = gatemarks.recommend_gaps("p2.plan_review", {"faces": [{**FACE, "recommend": {"answer": "x"}}]})
        self.assertEqual(len(got), 1, got)
        self.assertIn("faces[0]", got[0])

    def test_review_stuck_recommend_is_checked_too(self):
        """返答の一番上の止まった時の推し（converge.STUCK_PUSH）も faces の行と同じ形で照らし、崩れていれば 1 行で名指す。
        整った推しと、欄の無い返答は通す"""
        reply = {"faces": [FACE]}
        self.assertEqual(gatemarks.recommend_gaps("p2.plan_review", reply), [])
        self.assertEqual(gatemarks.recommend_gaps("p2.plan_review", {**reply, converge.STUCK_PUSH: REC}), [])
        for bad in BAD:
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
