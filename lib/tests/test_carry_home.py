"""次の run への持ち越しの住処（.shared/core/carry.py。考え carry-over）の検査。

書き手（報告）と読み手（依頼の入口）が同じ欄の名と同じ JSON Schema を引くこと・住処の外に持ち越しの字が漏れないこと・
下書きの行の作りと依頼の解き方が往復すること・行の鍵の決まりを見る（計画 docs/plans/2026-10-09-chained-rounds.md の Task 1）。
関数を直に呼ぶだけ（一時の置き場のファイルのほか、git・盤面・子のプロセスなし。柵の照らしは git ls-files を読む）。
"""
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))


def carry():
    import carry as m   # 住処（遅らせて読む。無ければその試験だけが落ちる）
    return m


class Fence(unittest.TestCase):
    def test_ghreads_keeps_only_github_reads(self):
        """ghreads は名指した PR・issue の読みだけを持つ（依頼の容器の形は carry へ移った）"""
        import ghreads
        for name in ("KEYS", "ANSWER_KEYS", "DRAFT_KEYS", "PRIOR_KEYS", "CI_WHERE", "request_parts", "without_prior", "carry_ci"):
            self.assertFalse(hasattr(ghreads, name), name)


class Contract(unittest.TestCase):
    def test_constants_match_schemas(self):
        """欄の名の定数が約束の Schema の欄と揃う（書き手と読み手が同じ約束を読む）"""
        c = carry()
        nxt, prior = c.schema(c.NEXT_SCHEMA), c.schema(c.PRIOR_SCHEMA)
        self.assertEqual(tuple(prior["items"]["properties"]), c.PRIOR_KEYS)
        self.assertEqual(nxt["properties"][c.PRIOR]["items"], prior["items"])
        self.assertEqual(set(nxt["required"]), {c.FINDINGS, c.PRIOR})
        self.assertLessEqual(set(nxt["properties"]), set(c.KEYS))
        for key in (c.FINDINGS, c.ANSWERS):
            self.assertLessEqual(set(c.DRAFT_KEYS), set(nxt["properties"][key]["items"]["properties"]), key)
        self.assertEqual(c.DRAFT_KEYS, (c.DRAFT, c.SOURCE))
        # ANSWER_KEYS（人が見直した答えの欄）と Schema の answers（下書きの欄）は別の物で、揃えない

    def test_reader_checks_prior_rows_against_schema(self):
        """読み手も prior_failures の行を同じ Schema で照らす（手書きの確かめの後。文は今のまま）"""
        c = carry()
        self.assertEqual(c.errors([{"where": "a", "text": "b"}], c.PRIOR_SCHEMA), [])
        self.assertTrue(c.errors([{"where": "a"}], c.PRIOR_SCHEMA))
        with self.assertRaises(ValueError):
            c.parts({"findings": [], "prior_failures": [{"where": "a"}]})


class Shape(unittest.TestCase):
    def test_compose_then_parts_roundtrip(self):
        """compose の返りから下書きの行を外すと parts が通る。下書きの行が残れば拒む"""
        c = carry()
        finding = {"where": "a.py:1", "text": "穴"}
        carried = c.draft({"where": "b.py", "text": "外の所見", "mechanism": "m"}, "前の run の判定が目的の外とした所見（R1）")
        ans = c.draft({"question": "q-1", "text": ""}, "台帳の問い q-1 の選択肢", "選択肢から書く")
        doc = c.compose([finding, carried], [{"where": "受け付け fix", "text": "理由"}], [ans])
        self.assertEqual(list(doc), ["findings", "prior_failures", "answers"])
        self.assertEqual(list(ans), ["question", "text", "draft", "source", "note"])
        self.assertTrue(c.is_draft(carried) and c.is_draft(ans) and not c.is_draft(finding))
        with self.assertRaises(ValueError):
            c.parts(doc)
        bare = {**doc, "findings": [r for r in doc["findings"] if not c.is_draft(r)], "answers": []}
        got = c.parts(bare)
        self.assertEqual(got["findings"], [finding])
        self.assertEqual(got["prior_failures"], doc["prior_failures"])

    def test_compose_without_drafts_has_no_answers(self):
        self.assertEqual(carry().compose([], [], []), {"findings": [], "prior_failures": []})

    def test_is_redesign_reads_where(self):
        """作り直しの行かは where だけで読む（独立の目 R2 の行だけが真。受け付け・CI・独立の目 R1 の行は偽）"""
        c = carry()
        self.assertEqual(c.REDESIGN_WHERE, "独立の目 R2")
        self.assertTrue(c.is_redesign({"where": "独立の目 R2", "text": "R2 が redesign-needed"}))
        self.assertTrue(c.is_redesign({"where": "独立の目  R2", "text": "空白は詰めて比べる"}))
        for where in ("受け付け fix", c.CI_WHERE, "独立の目 R1", "独立の目"):
            self.assertFalse(c.is_redesign({"where": where, "text": "R2 が redesign-needed"}), where)
        self.assertFalse(c.is_redesign("独立の目 R2"))
        self.assertFalse(c.is_redesign({}), "where の無い行は作り直しの行でない")

    def test_row_key_ignores_reason_tail(self):
        """行の鍵は where と、text の最初の「（」までを空白を詰めて \\t でつないだ物（理由だけ違う行は同じ鍵）"""
        c = carry()
        a = {"where": "a.py", "text": "k1（修正がやらなかった: 理由 A）"}
        b = {"where": "a.py", "text": "k1  （修正がやらなかった: 理由 B）"}
        self.assertEqual(c.row_key(a), c.row_key(b))
        self.assertEqual(c.row_key(a), "a.py\tk1")
        self.assertNotEqual(c.row_key(a), c.row_key({"where": "b.py", "text": "k1（理由 A）"}))


if __name__ == "__main__":
    unittest.main()
