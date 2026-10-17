"""ブロックの script と YAML の字に、ほかのブロックを指すパスと、`lib/`・`workflows/.shared/` の外への相対パスが無く、
inputs: の description がほかのブロック・メイングラフ・周の鎖のノードなど作り手を名指さない（workflows/AGENTS.md の E4 の機械の行）。"""
import pathlib
import re
import unittest
from unittest import mock

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"


class BlockPathsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E4", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E4", SEEDS / "e4")
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(any("workflows/judge/scripts/a.py" in line for line in got), got)

    def test_relative_path_outside_allowed_places_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "../../../bin/tool"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "外" in line for line in got), got)

    def test_relative_path_into_lib_is_clean(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "../../../lib/x.py"\n'}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_other_block_named_in_full_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "workflows/plan/out.json"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_read_path_of_other_block_is_red(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "$SRC/.archon/workflows/plan/out.json"\n'}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_pack_path_of_other_block_is_red(self):
        for text in ('X = "$SRC/.archon/workflows/works-factory/plan/out.json"\n',
                     'X = "../../../.archon/workflows/works-factory/plan/out.json"\n'):
            with self.subTest(text=text), tree({"workflows/judge/scripts/a.py": text}) as root:
                got = scan.problems("E4", root)
                self.assertTrue(any("a.py:1" in line and "plan" in line for line in got), got)

    def test_archon_pack_path_of_own_block_is_clean(self):
        with tree({"workflows/judge/scripts/a.py": 'X = "$SRC/.archon/workflows/works-factory/judge/out.json"\n'}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_inline_script_in_yaml_pointing_at_other_block_through_pack_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: cat ../works-factory/plan/out.json\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "plan" in line for line in got), got)

    def test_inline_script_in_yaml_pointing_at_other_block_is_red(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: cat ../../plan/out.json\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "plan" in line for line in got), got)

    def test_inline_script_in_yaml_into_lib_is_clean(self):
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: run ../../lib/x.py\n"
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            self.assertEqual(scan.problems("E4", root), [])

    def test_block_names_match_root_tree(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        listed = re.search(r"<サブグラフ>/\s+(\S+) の \d+ つ", text)[1].split("・")
        self.assertIn("── line/", text)
        self.assertIn("── chain/", text)
        self.assertEqual(sorted(scan.BLOCKS), sorted(["line", "chain", *listed]))

    def test_block_only_on_disk_counts_as_other(self):
        files = {"workflows/judge/scripts/a.py": 'X = "workflows/newblock/out.json"\n', "workflows/newblock/x": ""}
        with tree(files) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("a.py:1" in line and "newblock" in line for line in got), got)

    def test_input_description_naming_an_output_is_red(self):
        """入力の description が `$<id>.output` でほかのノードを指せば赤。同じ YAML の兄弟ノードの参照は数えない"""
        yaml = ("name: works-factory-judge\nnodes: [{id: own-node, script: x}]\ninputs:\n"
                "  start: {default: 'null', description: 始めの記録のポインタ（$start.output.record）}\n"
                "  mine: {default: '', description: 兄弟の値（$own-node.output.x）}\n")
        with tree({"workflows/judge/works-factory-judge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-judge.yaml:4" in line and "入力 start" in line and "$start.output" in line
                            for line in got), got)
        self.assertFalse(any("own-node" in line for line in got), got)

    def test_input_description_naming_another_block_is_red(self):
        """入力の description がほかのブロックの名を語として書けば赤。`plan-fields.json`・`plan_review` は語の一部で数えない"""
        yaml = ("name: works-factory-merge\ninputs:\n"
                "  eyes_ok: {default: '', description: eyes の ok}\n"
                "  x: {default: '', description: plan-fields.json と plan_review}\n")
        with tree({"workflows/merge/works-factory-merge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-merge.yaml:3" in line and "入力 eyes_ok" in line and "eyes" in line for line in got), got)
        self.assertFalse(any("入力 x " in line for line in got), got)

    def test_name_glued_to_japanese_is_still_a_word(self):
        """#556: 日本語の字にくっついた名（`eyesの ok`・`（eyesが通したか）`・`gate-before-fixの答え`）も名指しに数えて赤"""
        files = {
            "workflows/line/works-factory-line.yaml": "name: works-factory-line\nnodes:\n  - id: gate-before-fix\n    script: x\n",
            "workflows/merge/works-factory-merge.yaml": ("name: works-factory-merge\ninputs:\n"
                                                         "  eyes_ok: {default: '', description: eyesの ok}\n"
                                                         "  passed: {default: '', description: （eyesが通したか）}\n"
                                                         "  answers: {default: '', description: gate-before-fixの答え}\n"),
        }
        with tree(files) as root:
            got = scan.problems("E4", root)
        for name, said in (("eyes_ok", "eyes"), ("passed", "eyes"), ("answers", "gate-before-fix")):
            with self.subTest(name=name):
                self.assertTrue(any(f"入力 {name} " in line and said in line for line in got), got)

    def test_input_description_naming_a_maker_in_words_is_red(self):
        """#683: 語「ノード」と、ほかのブロックの和名を作り手として書く形（修正役・独立の目が・修正の段）は赤。中身の語としての和名
        （判定のポインタ）と、自分のブロックの和名（merge の 取り込みが）は数えない"""
        yaml = ("name: works-factory-merge\ninputs:\n"
                "  answer: {default: '', description: 最後の承認ノードの答え}\n"
                "  objection: {default: '', description: 修正役の異議}\n"
                "  eyes_ok: {default: '', description: 独立の目が通したか}\n"
                "  diffs: {default: '', description: 修正の段ごとの diff}\n"
                "  judgment: {default: '', description: 判定のポインタ。取り込みが読む}\n")
        with tree({"workflows/merge/works-factory-merge.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        for number, (name, said) in enumerate((("answer", "ノード"), ("objection", "修正役"), ("eyes_ok", "独立の目が"),
                                               ("diffs", "修正の段")), 3):
            with self.subTest(name=name):
                self.assertTrue(any(f"works-factory-merge.yaml:{number}: 入力 {name} " in line and said in line for line in got), got)
        self.assertFalse(any("入力 judgment " in line for line in got), got)

    def test_block_titles_are_read_from_the_design(self):
        self.assertEqual(scan.BLOCK_TITLES["fix"], "修正")
        self.assertEqual(set(scan.BLOCK_TITLES) - set(scan.TOP_FOLDERS), set(scan.LAYERS["block"]["names"]))

    def test_input_description_naming_a_prefixed_block_is_red(self):
        yaml = "name: works-factory-eyes\ninputs:\n  plan: {default: 'null', description: works-factory-plan の出力}\n"
        with tree({"workflows/eyes/works-factory-eyes.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-eyes.yaml:3" in line and "入力 plan" in line and "works-factory-plan" in line
                            for line in got), got)

    def test_input_description_naming_a_line_or_chain_node_is_red(self):
        """メイングラフと周の鎖のノードの id のうち - を含む物は、説明が語として名指せば赤。- の無い id（start）は数えない"""
        files = {
            "workflows/line/works-factory-line.yaml": "name: works-factory-line\nnodes:\n  - id: gate-before-fix\n    script: x\n  - id: start\n    script: x\n",
            "workflows/chain/works-factory-chain.yaml": "name: works-factory-chain\nnodes:\n  - id: round-1-facts\n    script: x\n",
            "workflows/fix/works-factory-fix.yaml": ("name: works-factory-fix\ninputs:\n"
                                                     "  answers: {default: '', description: gate-before-fix の答え}\n"
                                                     "  notes: {default: '', description: round-1-facts の文}\n"
                                                     "  begin: {default: '', description: start を読む}\n"),
        }
        with tree(files) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("入力 answers" in line and "gate-before-fix" in line for line in got), got)
        self.assertTrue(any("入力 notes" in line and "round-1-facts" in line for line in got), got)
        self.assertFalse(any("入力 begin" in line for line in got), got)

    def test_input_description_naming_the_main_graph_is_red(self):
        """説明に語「メイングラフ」があれば赤。一番上のグラフ（line・chain）の入力の説明は見ない"""
        files = {
            "workflows/fix/works-factory-fix.yaml": ("name: works-factory-fix\ninputs:\n"
                                                     "  mode: {default: '', description: 空はサブグラフの形（メイングラフの include の中だけ）}\n"),
            "workflows/chain/works-factory-chain.yaml": ("name: works-factory-chain\ninputs:\n"
                                                         "  request: {default: '', description: メイングラフの同じ名の入力}\n"),
        }
        with tree(files) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-fix.yaml:3" in line and "入力 mode" in line and "メイングラフ" in line for line in got), got)
        self.assertFalse(any("works-factory-chain.yaml" in line for line in got), got)

    def test_input_description_that_is_not_a_string_is_red(self):
        """字でない（mapping の）説明は中に字を隠せるので赤。説明の無い入力は名指す字も無いので見ない"""
        yaml = ("name: works-factory-fix\ninputs:\n  bare: {default: ''}\n"
                "  nested: {default: '', description: {text: 始めの記録}}\n")
        with tree({"workflows/fix/works-factory-fix.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-fix.yaml:4" in line and "入力 nested" in line for line in got), got)
        self.assertFalse(any("入力 bare" in line for line in got), got)

    def test_top_graph_hyphen_ids_are_read_from_the_real_tree(self):
        """実際の木で一番上のグラフの `-` を含む id が取れている（空だと節の id の型が黙って外れる）"""
        got = scan._top_hyphen_ids(ROOT)
        self.assertTrue({"gate-before-fix", "round-1-facts"} <= got, got)

    def test_folded_input_description_naming_a_producer_is_red(self):
        """`>-` の複数行の description の 2 行目以降の名指しも、YAML として読んで赤にする"""
        yaml = ("name: works-factory-plan-review\ninputs:\n  depth_why:\n    default: ''\n    description: >-\n"
                "      depth_skip の訳\n      （メイングラフの plan-review-due の why）\n")
        with tree({"workflows/plan-review/works-factory-plan-review.yaml": yaml}) as root:
            got = scan.problems("E4", root)
        self.assertTrue(any("works-factory-plan-review.yaml:5" in line and "入力 depth_why" in line for line in got), got)

    def test_script_importing_a_sibling_script_is_red(self):
        """script は同じ scripts/ の別の script を import しない（K8）。lib のモジュールと境の口は読んでよい"""
        files = {"workflows/judge/scripts/a.py": "import os\nimport b\nfrom b import x\nimport boundary\n",
                 "workflows/judge/scripts/b.py": "x = 1\n"}
        with tree(files) as root:
            got = scan.problems("E4", root)
        self.assertEqual([line.split(": ", 1)[0] for line in got], ["workflows/judge/scripts/a.py:2", "workflows/judge/scripts/a.py:3"])
        self.assertIn("script b を import する", got[0])

    def test_script_named_like_a_lib_module_is_red(self):
        """script の名を lib のモジュールの名にしない（script のフォルダが sys.path の頭に来て lib の物を隠す。K19）"""
        with tree({"workflows/line/scripts/answer.py": "", "lib/answer.py": ""}) as root:
            got = scan.problems("E4", root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("lib/answer.py と同じ", got[0])

    def test_sibling_import_allowance_names_the_script(self):
        """ALLOWED["E4"] の `<script のパス>#<名>` の行は、名指した script のその import だけを外す（新しい script に
        import place を足すと赤）"""
        files = {"workflows/report/scripts/collect.py": "import place\nimport b\n", "workflows/report/scripts/place.py": "",
                 "workflows/report/scripts/b.py": "", "workflows/report/scripts/new.py": "import place\n"}
        with tree(files) as root, mock.patch.dict(scan.ALLOWED, {"E4": ("workflows/report/scripts/collect.py#place",)}):
            got = scan.problems("E4", root)
        self.assertEqual(len(got), 2, got)
        self.assertIn("collect.py:2: 同じ scripts/ の script b", got[0])
        self.assertIn("new.py:1: 同じ scripts/ の script place", got[1])

if __name__ == "__main__":
    unittest.main()
