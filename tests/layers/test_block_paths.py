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


class JudgeNamesTest(unittest.TestCase):
    """判定の置き場のファイルを、判定の外（住処でない lib とほかのブロックの script）が名指さず、判定の出力の欄のポインタで受ける
    （issue #680。workflows/AGENTS.md の E4）"""

    HOMES = {"lib/gatemarks.py": 'MATERIALS_FILE = "materials.json"\n',
             "lib/marks.py": 'KINDS = {"answers": Kind({}, "answer-ties.json", ROOT)}\n',
             "lib/prcheck.py": 'EXCLUDED = marks.KINDS["pr"].file\n'}

    def judge_names(self, files: dict) -> list:
        with tree({**self.HOMES, **files}) as root:
            return [line for line in scan.problems("E4", root) if "判定の置き場のファイル" in line]

    def test_names_come_from_the_judge_ports(self):
        import judge_accept
        self.assertEqual(scan.judge_port_files(), {*judge_accept.PORTS.values(), *judge_accept.FIRST_PORTS.values()})
        self.assertIn("materials.json", scan.judge_port_files())

    def test_every_port_file_has_a_home(self):
        """判定の出力の欄のファイルの名は、どれも住処のモジュールが字か定数で持つ（住処の表が欄の足しに遅れていない）"""
        text = "".join((ROOT / home).read_text(encoding="utf-8") for home in scan.JUDGE_NAME_HOMES)
        for name in scan.judge_port_files():
            with self.subTest(name=name):
                self.assertIn(f'"{name}"', text)

    def test_other_block_script_opening_a_judge_file_by_name_is_red(self):
        for body in ('import os\nX = os.path.join(d, "materials.json")\n', "import gatemarks\nX = d / gatemarks.MATERIALS_FILE\n",
                     "import gatemarks as g\nX = d.with_name(g.MATERIALS_FILE)\n", "from gatemarks import MATERIALS_FILE\n",
                     'import marks\nX = marks.path_of("answers", d)\n', 'import marks\nX = marks.KINDS["answers"].file\n',
                     "import prcheck\nX = d / prcheck.EXCLUDED\n"):
            with self.subTest(body=body):
                got = self.judge_names({"workflows/plan/scripts/a.py": body})
                self.assertEqual(len(got), 1, got)
                self.assertIn("workflows/plan/scripts/a.py:", got[0])

    def test_passing_beside_the_judge_pointer_to_an_opener_is_red(self):
        """判定のポインタの隣（`.parent`・`.with_name(…)`）を、住処の中の判定の置き場を名で開く関数に渡すと赤。開かない関数は通す"""
        homes = {"lib/worldmark.py": 'import marks\nSTATE_FILE = "world-state.json"\nMEANS = "means"\n'
                                     "def read(d):\n    return d / STATE_FILE\n"
                                     "def means_of(d):\n    return marks.path_of(MEANS, d)\n"
                                     "def read_file(p):\n    return p\n",
                 "lib/marks.py": 'KINDS = {"means": Kind({}, "purpose-means.json", ROOT)}\n'}
        for body in ("import worldmark\nX = worldmark.read(j.parent)\n", "import worldmark\nX = worldmark.means_of(Path(j).parent)\n",
                     "from worldmark import read\nX = read(board=j.with_name('x'))\n"):
            with self.subTest(body=body):
                got = self.judge_names({**homes, "workflows/eyes/scripts/a.py": body})
                self.assertEqual(len(got), 1, got)
                self.assertIn("(<判定のポインタの隣>)", got[0])
        clean = "import worldmark\nX = worldmark.read_file(j)\nY = worldmark.read_file(j.parent / 'x')\nZ = worldmark.read(j)\n"
        self.assertEqual(self.judge_names({**homes, "workflows/eyes/scripts/a.py": clean}), [])

    def test_importing_the_writer_or_getattr_of_a_name_is_red(self):
        """判定の外は書き手の judge_accept を import しない（PORTS の鍵を引く形も塞ぐ）。住処の定数を getattr で名で引くのも赤"""
        for body in ("import judge_accept\nX = judge_accept.PORTS['decisions']\n", "from judge_accept import PORTS\n",
                     'import gatemarks\nX = getattr(gatemarks, "MATERIALS_FILE")\n'):
            with self.subTest(body=body):
                got = self.judge_names({"workflows/plan/scripts/a.py": body})
                self.assertEqual(len(got), 1, got)

    def test_lib_subfolders_and_shared_are_read(self):
        """lib の下のフォルダと workflows/.shared/ も判定の外。lib の試験は名を字で持って照らすので見ない"""
        files = {"lib/graphloops/a.py": 'X = "materials.json"\n', "workflows/.shared/b.py": 'X = "materials.json"\n',
                 "lib/tests/test_c.py": 'X = "materials.json"\n'}
        got = self.judge_names(files)
        self.assertEqual(sorted(line.split(":")[0] for line in got), ["lib/graphloops/a.py", "workflows/.shared/b.py"], got)

    def test_main_graph_script_and_lib_reader_are_red(self):
        got = self.judge_names({"workflows/line/scripts/a.py": 'X = "rejudge-exit.json"\n',
                                "lib/reader.py": "import gatemarks\nX = gatemarks.MATERIALS_FILE\n"})
        self.assertEqual(sorted(line.split(":")[0] for line in got), ["lib/reader.py", "workflows/line/scripts/a.py"], got)

    def test_judge_and_homes_and_prose_are_clean(self):
        """判定の script・書き手の judge_accept・住処は名を持ってよい。長い文の中の名は名指しに数えない"""
        files = {"workflows/judge/scripts/a.py": 'X = "materials.json"\n',
                 "lib/judge_accept.py": "import gatemarks\nX = gatemarks.MATERIALS_FILE\n",
                 "workflows/plan/scripts/b.py": 'X = "判定の materials.json の先"\nY = "judge-materials.json"\n'}
        self.assertEqual(self.judge_names(files), [])


if __name__ == "__main__":
    unittest.main()
