"""設計の材料の部品（lib/design.py。README 9.3 の KEEP）のうち、根拠の名指しと『渡されていない』の文の当て方の試験。元 main の
lib/tests/test_blk_eyes.py の 6 本（独立の目のブロックの試験のうち、KEEP の design を直に呼ぶ物。README 9.5）。

- anchors: パス:行（範囲も）を名指しに拾い、host:port・URL・時刻・コードでない拡張子のドット付きの名は拾わない
- anchor_note: 名指しの無い文に UNANCHORED の札
- claims_given: 貼った設計書の節には、文がそのパスか節番号を含む時だけ当てる。地図の文は貼った地図に当てる
"""
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import design  # noqa: E402


class AnchorCase(unittest.TestCase):
    """問いが立たない根拠の名指し（パス:行）の拾い方（依頼 238）"""

    def test_path_line_and_range_are_anchors(self):
        self.assertEqual(design.anchors("design.py:70 と works/.shared/core/design.py:70-75 を見よ"),
                         [("design.py", 70, 70), ("works/.shared/core/design.py", 70, 75)])

    def test_command_output_reads_the_grep_form(self):
        out = "$ grep -n median stats.py\nstats.py:44:def median(xs):"
        self.assertEqual(design.anchors(out), [])
        self.assertEqual(design.anchors(out, output=True), [("stats.py", 44, 44)])

    def test_host_port_and_dotted_names_are_not_anchors(self):
        """拡張子がコード・文書・設定の物（impact の表）でないドット付きの名と番号（host:port など）は名指しに数えない"""
        self.assertEqual(design.anchors("db.internal:5432 と foo.bar:12 に繋ぐ"), [])

    def test_url_and_time_are_not_anchors(self):
        self.assertEqual(design.anchors("https://example.com:443/a の応答の時刻 10:15 を使う"), [])
        self.assertEqual(design.anchor_note("https://example.com:443/a"), f"（{design.UNANCHORED}）")



class PathCase(unittest.TestCase):
    def test_named_section_claim_matches_only_by_path_or_number(self):
        """貼った設計書の節には、『渡されていない』の文がそのパスか節番号を含む時だけ当てる。「設計書」の一般語だけの文
        （別の設計書の節のことかもしれない）や、番号の違う節の文は当てない"""
        given = [{"kind": "named_section", "what": "docs/spec.md#2-上限"},
                 {"kind": "named_section", "what": "docs/spec.md 3 節"}]
        hit = ["docs/spec.md の本文が渡されていない", "§3 の撤収が渡っていない", "2 節の上限が渡されていない"]
        miss = ["別の設計書の節が渡されていない", "設計書が渡っていない", "12 節が渡されていない", "§3.1 が渡っていない"]
        got = {c for c in hit + miss if design.claims_given([c], given)}
        self.assertEqual(got, set(hit))

    def test_unpassed_map_claim_matches_repo_map(self):
        """『地図が渡されていない』の文は、貼った地図（kind repo_map）の行に当たる"""
        self.assertEqual(len(design.claims_given(["地図が渡されていない"], [{"kind": "repo_map", "what": "ARCHITECTURE.md:1-3"}])), 1)


class MeansDriftQuoteCase(unittest.TestCase):
    """事前審査の means_drifts の引用の照らし（計画 means-answers の 3.2 の 5）: design_quote は独立設計の文に、plan_quote は項目 item の
    案の行に字のまま要る。同じ食い違いを穴にも書いた行と、設計の立たない run の行は誤り"""
    PLAN = [{"approach": "分母を len(xs) にして stats.py の中で直す"}, {"approach": "clamp の上限の枝を hi に直す"}]
    DESIGN = {"question_stands": True, "reason": "", "design": "平均は集計の層の助け手に置き、stats.py は呼ぶだけにする"}

    def setUp(self):
        import json
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = pathlib.Path(self._tmp.name)
        (self.dir / design.DESIGN_FILE).write_text(json.dumps(self.DESIGN, ensure_ascii=False), encoding="utf-8")

    def gaps(self, drift, faces=()):
        return design.means_drift_gaps(self.dir, {"type": "object"}, [drift], self.PLAN, faces)

    def drift(self, **kw):
        return {"item": 1, "means": "M1", "design_quote": "平均は集計の層の助け手に置き", "plan_quote": "stats.py の中で直す",
                "why": "独立設計は別の層に置く", **kw}

    def test_good_row(self):
        self.assertEqual(self.gaps(self.drift()), [])

    def test_quotes_must_be_in_their_texts(self):
        self.assertTrue(any("design_quote" in g for g in self.gaps(self.drift(design_quote="設計に無い字"))))
        self.assertTrue(any("plan_quote" in g for g in self.gaps(self.drift(item=2))), "plan_quote は項目 item の字から引く")

    def test_same_drift_in_a_face_is_refused(self):
        face = {"key": "f1", "why": f"{design.DRIFT_HEAD}「stats.py の中で直す」と「平均は集計の層の助け手に置き」が食い違う"}
        self.assertTrue(any("どちらか 1 つ" in g for g in self.gaps(self.drift(), [face])))

    def test_no_design_refuses_the_row(self):
        (self.dir / design.DESIGN_FILE).unlink()
        self.assertTrue(any("独立設計が無い" in g for g in self.gaps(self.drift())))


if __name__ == "__main__":
    unittest.main()
