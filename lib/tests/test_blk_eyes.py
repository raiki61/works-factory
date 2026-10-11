"""独立の目のブロック（blk-eyes。BLOCKS.md の R11）の検査。

中の節は写しの graph のまま: 入口の機械の節 p4.assemble・目 6 つ（r1.comment_candidates → r1.minimality・
r2.compare → stop.premise_check・r3.coherence・r4.hidden_scope）・関所の機械の節 r4.human_gate。どの目を回すか（条件・依存）は
盤面の settle だけが決め、ブロックは ready の目を起こして返答を盤面に渡し、出口を組むだけ。R2 の設計の半分（r2.design）は修正の前に
先に作られ（core の design）、ラインの境の節がこのブロックの前に盤面へ渡す——試験の盤面も同じ口（design.hand）で渡してから入る。

- 表: 6 つの目を absent から role（where blk-eyes）へ替える行（tests/boards/tables/eyes-rows.json。ラインの nodes.json に写す案）が
  表の縛りを通る。r1.comment_candidates だけ skippable（graph で optional。3 回とも拒まれたら省いて R1 の本体へ進む）
- 盤面: 手本（graphloops 0.21.0 の台本を engine の中で撮った物）の p4.assemble の後から、上の行に替えた表で作る。表の置き場は
  一時の pack（.shared と blk-eyes の写しと、試験のライン eyes-line/nodes.json）
- 描画: 指示書は engine と同じ描き方（写しの graph の reads だけ）。先に作る道具ゼロの r2.design には差分・リポジトリの置き場が
  届かない。r2.compare の頭には設計の後に分かった前提（前提のずれ・記録の制約）と『設計の前提が変わった』の指示が載る
- 設計が無い: 設計の役が 3 回とも拒まれた盤面では比較の目が残り、出口が『独立設計が取れなかった』を理由に止める
- 受け付け: 起こす前の作業ツリーの写しと比べ、盤面の done（schema・post_check・writes・記録の整合）。3 回拒まれたら諦めの印
- 並び: 目は並んで走る（実行基盤の同じ層の輪）。盤面の書き込みは 1 本の錠（board.lock）で順に並べる
- 出口: 入口の周の箱だけを見る（最後の目の受け付けの settle が周を進めても読み違えない）。欄は固定（EXIT_FIELDS）
- YAML: 役の output_format は写しの schema に印（道具ゼロの役は旗 isolated）・道具は役ごと・輪は done で抜ける・with: と
  スクリプトの INPUTS が同じ・筋書き（pass と give-up）
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

    def test_host_port_and_dotted_names_are_not_anchors(self):
        """拡張子がコード・文書・設定の物（impact の表）でないドット付きの名と番号（host:port など）は名指しに数えない"""
        self.assertEqual(design.anchors("db.internal:5432 と foo.bar:12 に繋ぐ"), [])

    def test_url_and_time_are_not_anchors(self):
        self.assertEqual(design.anchors("https://example.com:443/a の応答の時刻 10:15 を使う"), [])
        self.assertEqual(design.anchor_note("https://example.com:443/a"), f"（{design.UNANCHORED}）")


if __name__ == "__main__":
    unittest.main()
