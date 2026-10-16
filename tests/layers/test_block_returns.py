"""ブロックの返りが 1 つの節の構造体で、返りの欄に読み手が在る（workflows/AGENTS.md の E5 の機械の行）。

在るブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。
返りの欄のうち、線の `with:`・`when:`・返しの節の `from` の誰も `$<include の id>.output.<欄>` で読まず、まるごとの参照
`$<include の id>.output` を受ける script の口（boundary.picked の名の並び）も受け皿の素通し（PASSES）も数えない物は赤。
欄つきの参照の読む欄が返す節に在るかは Archon の `validate` が照らす（tests/layers/test_archon_validate.py）ので、ここでは照らさない。
まるごとの参照は validate が欄を見られないので、ここで照らす: 受けてよい置き場は script の節の `with:<鍵>` の直の字か `with:<鍵>.from` の字で、
ほかは赤。受けた script は口の呼びで読む名が返す節の output_format に在り、口を迂回して読まない。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
BLOCK = "workflows/judge/works-factory-judge.yaml"
LINE = "workflows/line/works-factory-line.yaml"
RETURNING = (
    "name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n"
    "  - id: verdict\n    script: stub\n    timeout: 1728000000\n"
    "    output_format:\n      type: object\n      properties:\n        ready: {type: boolean}\n        units: {type: array}\n"
    "      required: [ready, units]\n"
)
TAKE = "workflows/line/scripts/take.py"
LINE_HEAD = "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
# 返りの欄を欄つきの参照で読む節。まるごとの参照の試験で、読み手の無い欄の赤を消すのに足す
READS = (
    "  - id: reader\n    script: reader\n    timeout: 1728000000\n    with:\n"
    "      ready: $judge.output.ready\n      units: $judge.output.units\n"
)
GATE_NAMES = 'NAMES = ("ready", "units")\n'
GATE_CALL = 'got = boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)\n'
GATE = GATE_NAMES + GATE_CALL


def take_node(value):
    """script の節 take。with: の got に value（YAML の字）を結ぶ"""
    return f"  - id: take\n    script: take\n    timeout: 1728000000\n    with:\n      got: {value}\n"


class BlockReturnsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E5", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E5", SEEDS / "e5")
        self.assertEqual(len(got), 1, got)
        self.assertIn(BLOCK, got[0])
        self.assertIn("unread", got[0])

    def problems(self, block, line):
        return self.files({BLOCK: block, LINE: line})

    def files(self, files):
        with tree(files) as root:
            return scan.problems("E5", root)

    def test_every_field_read_by_the_line_is_clean(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: plan\n    include: works-factory-plan\n    when: \"$judge.output.ready == true\"\n"
            "    with:\n      units: $judge.output.units\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_field_read_through_another_include_of_the_same_block_counts(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: rejudge\n    include: works-factory-judge\n"
            "  - id: collect\n    script: collect\n    timeout: 1728000000\n    with:\n"
            "      ready: $judge.output.ready\n      units: { from: \"$rejudge.output.units\", if_skipped: null }\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_field_read_inside_a_loop_group_body_counts(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: rounds\n    loop_group:\n      max_iterations: 3\n"
            "      until_bash: '[ $out.output.done = \"true\" ]'\n      nodes:\n"
            "        - id: judge\n          include: works-factory-judge\n"
            "        - id: out\n          script: out\n          depends_on: [judge]\n          with:\n"
            "            ready: $judge.output.ready\n            units: $LOOP_PREV.judge.output.units\n"
        )
        self.assertEqual(self.problems(RETURNING, line), [])

    def test_unread_field_is_red(self):
        line = "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n    when: \"$judge.output.ready\"\n"
        got = self.problems(RETURNING, line)
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:", got[0])
        self.assertIn("units", got[0])

    def test_same_field_name_of_another_node_is_not_a_reader(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: x\n    script: x\n    timeout: 1728000000\n    with:\n      ready: $judge.output.ready\n"
            "      units: $x.output.units\n"
        )
        got = self.problems(RETURNING, line)
        self.assertTrue(any("units" in line for line in got), got)

    def test_missing_returns_or_outcome_field_is_red(self):
        for drop in ("returns: verdict\n", "outcome_field: ready\n"):
            with self.subTest(drop=drop):
                got = self.problems(RETURNING.replace(drop, ""), "name: works-factory-line\nnodes: []\n")
                self.assertTrue(any(drop.split(":")[0] in line for line in got), got)

    def test_returning_node_without_output_format_is_red(self):
        block = (
            "name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n"
            "  - id: verdict\n    script: stub\n    timeout: 1728000000\n"
        )
        got = self.problems(block, "name: works-factory-line\nnodes: []\n")
        self.assertTrue(any("output_format" in line for line in got), got)

    def test_outcome_field_not_required_is_red(self):
        block = RETURNING.replace("required: [ready, units]", "required: [units]")
        line = (
            "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "    when: \"$judge.output.ready == true\"\n  - id: x\n    script: x\n    timeout: 1728000000\n"
            "    with:\n      units: $judge.output.units\n"
        )
        got = self.problems(block, line)
        self.assertEqual(len(got), 1, got)
        self.assertIn("required", got[0])

    def test_the_line_itself_is_not_a_block(self):
        line = "name: works-factory-line\nreturns: result\nnodes: []\n"
        with tree({LINE: line}) as root:
            self.assertEqual(scan.problems("E5", root), [])


    def test_declared_input_without_a_reader_is_red(self):
        """ブロックの入力は、その script の INPUTS_<名> か役の指示書の $INPUTS.<名> に読み手を持つ（K12）"""
        block = RETURNING.replace("nodes:\n", "inputs:\n  plan: {default: ''}\n  ripple-list: {default: ''}\nnodes:\n", 1)
        files = {BLOCK: block, LINE: "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
                                     "  - id: r\n    script: r\n    with: {a: $judge.output.ready, b: $judge.output.units}\n"}
        got = self.files(files)
        self.assertEqual(sorted(line.split("入力 ")[1].split(" ")[0] for line in got), ["plan", "ripple-list"], got)
        files["workflows/judge/scripts/s.py"] = 'P = os.environ["INPUTS_PLAN"]\n'
        files["workflows/judge/commands/c.md"] = "波及は $INPUTS.ripple-list\n"
        self.assertEqual(self.files(files), [])

    def test_input_named_by_a_lib_constant_has_a_reader(self):
        """INPUTS_{…} を組んで読む script が名の並びを lib の部品の定数から引けば、並びに在る名は読み手を持つ"""
        block = RETURNING.replace("nodes:\n", "inputs:\n  plan: {default: ''}\n  ripple: {default: ''}\nnodes:\n", 1)
        files = {BLOCK: block, LINE: "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
                                     "  - id: r\n    script: r\n    with: {a: $judge.output.ready, b: $judge.output.units}\n",
                 "lib/board.py": 'NAMES = ("plan",)\nREAD = "ripple"\n',
                 "workflows/judge/scripts/s.py": 'raw = {n: os.environ[f"INPUTS_{n.upper()}"] for n in board.NAMES}\n'
                                                 "x = board.READ\n"}
        got = self.files(files)
        self.assertEqual([line.split("入力 ")[1].split(" ")[0] for line in got], ["ripple"], got)

    def test_lib_constant_name_not_declared_as_input_is_red(self):
        """逆向き: INPUTS_{…} を組む script が回す lib の部品の定数の名は、どれもブロックの inputs: に在る（無い名は空の字で届く。#344）"""
        block = RETURNING.replace("nodes:\n", "inputs:\n  plan: {default: ''}\nnodes:\n", 1)
        files = {BLOCK: block, LINE: "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
                                     "  - id: r\n    script: r\n    with: {a: $judge.output.ready, b: $judge.output.units}\n",
                 "lib/board.py": 'NAMES = ("plan", "world")\nOTHER = ("elsewhere",)\n',
                 "workflows/judge/scripts/s.py": 'raw = {n: os.environ.get(f"INPUTS_{n.upper()}", "") for n in board.NAMES}\n'
                                                 "x = board.OTHER\n"}
        got = self.files(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn("workflows/judge/scripts/s.py:1: board.NAMES の名 world", got[0])
        files["lib/board.py"] = 'NAMES = ("plan",)\nOTHER = ("elsewhere",)\n'
        self.assertEqual(self.files(files), [], "組む内包が回さない定数の名は照らさない")

    def test_input_passed_by_with_only_is_red(self):
        """YAML の with: で script へ渡すだけの $INPUTS.<名> は読み手に数えない（merge の diff を merge.py が読まないと赤）。
        YAML の役の節の prompt: の $INPUTS.<名> は数える"""
        block = RETURNING.replace("nodes:\n", "inputs:\n  diff: {default: ''}\nnodes:\n", 1)
        block += "  - id: s\n    script: s\n    with: {diff: $INPUTS.diff}\n"
        files = {BLOCK: block, LINE: "name: works-factory-line\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
                                     "  - id: r\n    script: r\n    with: {a: $judge.output.ready, b: $judge.output.units}\n"}
        got = self.files(files)
        self.assertEqual(len(got), 1, got)
        self.assertIn("入力 diff に読み手が無い", got[0])
        files[BLOCK] = block + "  - id: role\n    prompt: 差分は $INPUTS.diff\n"
        self.assertEqual(self.files(files), [])

    def test_role_in_a_loop_group_binding_its_own_with_is_red(self):
        """輪の中の役は自分の with: を結ばない（K5）。script の節は結んでよい"""
        yaml = ("name: works-factory-plan\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n"
                "        - id: head\n          script: head\n          with: {reason: $LOOP_PREV.take.output.reason}\n"
                "        - id: role\n          prompt: x\n          with: {reason: $LOOP_PREV.take.output.reason}\n")
        got = self.files({"workflows/plan/works-factory-plan.yaml": yaml})
        self.assertTrue(any("輪の中の役 role" in line for line in got), got)
        self.assertFalse(any("head" in line for line in got), got)

    def test_loop_role_seed_is_one_violation(self):
        got = scan.problems("E5", SEEDS / "k5-loop-role-with")
        self.assertEqual(len(got), 1, got)
        self.assertIn("輪の中の役", got[0])

    def gated(self, script, value='"$judge.output"', reads="", files=None):
        """script の節 take が with: の got でブロック judge の返りをまるごとで受ける木。script の字は workflows/line/scripts/take.py"""
        line = LINE_HEAD + reads + take_node(value)
        return self.files({BLOCK: RETURNING, LINE: line, TAKE: script, **(files or {})})

    def test_whole_ref_read_through_the_gate_is_clean(self):
        board = "NAMES = ('ready', 'units')\n"
        forms = {
            "字のまま": (GATE, '"$judge.output"', {}),
            "{from, if_skipped}": (GATE, '{ from: "$judge.output", if_skipped: null }', {}),
            "* 展開の名の並び": ("BASE = ('ready',)\nNAMES = (*BASE, 'units')\n" + GATE_CALL, '"$judge.output"', {}),
            "鍵と同じ字を辞書の鍵に持つ": (GATE_NAMES + 'out = {"got": boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)}\n', '"$judge.output"', {}),
            "別の INPUTS_{…} の内包": (GATE + 'PLANS = ("plan", "ripple")\n'
                                      'vals = {k: boundary.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in (*PLANS, "replanned")}\n',
                                      '"$judge.output"', {}),
            "+ の連結": (GATE + 'PLAN = ("a", "b")\nREVIEW = ("c",)\n'
                              'vals = {k: boundary.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in PLAN + REVIEW}\n', '"$judge.output"', {}),
            "接頭辞つき f 字": (GATE + 'FIELDS = ("units", "ready")\n'
                                      "def with_prefix(prefix):\n"
                                      '    return {k: boundary.field(k, os.environ.get(f"INPUTS_{prefix}_{k.upper()}")) for k in FIELDS}\n'
                                      'judge = with_prefix("JUDGE")\n', '"$judge.output"', {}),
            "env(名)": (GATE + "def env(name):\n"
                              '    return boundary.value(os.environ.get(f"INPUTS_{name}"))\n'
                              'r1 = env("R1")\n', '"$judge.output"', {}),
            "別の部品の定数": (GATE + 'vals = {k: boundary.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in board.NAMES}\n',
                            '"$judge.output"', {"lib/board.py": board}),
            "前置き INPUTS_GOT_ で環境を舐める": (GATE + 'HEAD = "INPUTS_GOT_"\n'
                                          "rest = {k.removeprefix(HEAD): raw for k, raw in names.items() if k.startswith(HEAD)}\n",
                                          '"$judge.output"', {}),
        }
        for name, (script, value, files) in forms.items():
            with self.subTest(name):
                self.assertEqual(self.gated(script, value, files=files), [])
        anchored = (
            "name: works-factory-line\nx-bind: &bind\n  got: \"$judge.output\"\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: take\n    script: take\n    timeout: 1728000000\n    with:\n      <<: *bind\n"
        )
        with self.subTest("<<: で引いた with: の値"):
            self.assertEqual(self.files({BLOCK: RETURNING, LINE: anchored, TAKE: GATE}), [])

    def test_gate_name_not_in_the_output_format_is_red(self):
        got = self.gated("NAMES = ('ready', 'units', 'extra')\n" + GATE_CALL)
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{TAKE}:"), got)
        self.assertIn("got で読む欄 extra が works-factory-judge の返りに無い", got[0])

    def test_field_not_named_by_the_gate_is_red(self):
        got = self.gated("NAMES = ('ready',)\n" + GATE_CALL)
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{BLOCK}:", got[0])
        self.assertIn("units", got[0])
        self.assertIn("読み手が無い", got[0])

    def test_passed_through_whole_ref_counts_every_field(self):
        passed = 'PASSES = ("got",)\nout = boundary.value(os.environ.get("INPUTS_GOT"))\n'
        self.assertEqual(self.gated(passed), [])
        for name, script, why in (
            ("PASSES に鍵が無い", 'PASSES = ("other",)\nout = boundary.value(os.environ.get("INPUTS_GOT"))\n', "boundary.picked の呼びが無い"),
            ("口の呼びの外で読む", 'PASSES = ("got",)\nout = json.loads(os.environ["INPUTS_GOT"])\n', "口の呼びの外"),
            ("boundary.value の外にも読み", passed + 'again = os.environ.get("INPUTS_GOT")\n', "口の呼びの外"),
        ):
            with self.subTest(name):
                got = self.gated(script, reads=READS)
                self.assertEqual(len(got), 1, got)
                self.assertIn(why, got[0])

    def test_whole_ref_read_outside_the_gate_is_red(self):
        looped = 'vals = {k: boundary.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in %s}\n'
        env_def = 'def env(name):\n    return boundary.value(os.environ.get(f"INPUTS_{name}"))\n'
        cases = {
            "口が無く json.loads で読む": ("NAMES = ('ready', 'units')\ngot = json.loads(os.environ[\"INPUTS_GOT\"])\n", "boundary.picked の呼びが無い"),
            "PASSES 無しで boundary.value": ('got = boundary.value(os.environ.get("INPUTS_GOT"))\n', "boundary.picked の呼びが無い"),
            "口の外にもう 1 つ字": (GATE + 'again = os.environ.get("INPUTS_GOT")\n', "口の呼びの外"),
            "口の呼びが 2 つ": (GATE + 'GATE_AGAIN = boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)\n', "2 つ以上"),
            "env(GOT) で読む": (GATE + env_def + 'r = env("GOT")\n', "INPUTS_GOT を組みうる"),
            "内包の並びの literal に got": (GATE + looped % '("got", "x")', "INPUTS_GOT を組みうる"),
            "連結の定数に got": (GATE + 'PLAN = ("a", "got")\nREVIEW = ("c",)\n' + looped % "PLAN + REVIEW", "INPUTS_GOT を組みうる"),
            "* 展開の定数に got": (GATE + 'PLANS = ("got", "b")\n' + looped % '(*PLANS, "x")', "INPUTS_GOT を組みうる"),
            "INPUTS_ + key.upper()": (GATE + 'KEYS = ("a", "got")\n'
                                      'vals = {k: os.environ.get("INPUTS_" + k.upper()) for k in KEYS}\n', "INPUTS_GOT を組みうる"),
            "内包の並びが関数の返り": (GATE + looped % "names()", "を解けない"),
            "stop_key(node).upper()": (GATE + 'vals = {n: os.environ.get(f"INPUTS_{stop_key(n).upper()}") for n in ("a",)}\n', "を解けない"),
            "% で組む": (GATE + 'vals = {k: os.environ.get("INPUTS_%s" % k) for k in ("a",)}\n', "を解けない"),
            ".format で組む": (GATE + 'vals = {k: os.environ.get("INPUTS_{}".format(k)) for k in ("a",)}\n', "を解けない"),
            "env(変数) で呼ぶ": (GATE + env_def + "r = env(which)\n", "を解けない"),
            "渡さない引数の既定の値": (GATE + 'def env(name="GOT"):\n    return boundary.value(os.environ.get(f"INPUTS_{name}"))\nr = env()\n',
                                "INPUTS_GOT を組みうる"),
            "鍵の名で渡す引数": (GATE + env_def + 'r = env(name="GOT")\n', "INPUTS_GOT を組みうる"),
            "* で展開して渡す引数": (GATE + env_def + 'r = env(*("GOT",))\n', "を解けない"),
            "後の += で足した名": (GATE + 'KEYS = ("a",)\nKEYS += ("got",)\n' + looped % "KEYS", "を解けない"),
            "再代入した名の並び": (GATE + 'KEYS = ("a",)\nKEYS = ("got",)\n' + looped % "KEYS", "を解けない"),
            "小文字の前置きを upper で組む": (GATE + 'vals = {k: boundary.value(os.environ.get(f"inputs_{k}".upper())) for k in ("got",)}\n',
                                    "INPUTS_GOT を組みうる"),
            "前置き INPUTS_ で環境を舐める": (GATE + 'rest = [raw for k, raw in names.items() if k.startswith("INPUTS_")]\n', "前置き"),
            "名の並びが定数に解けない": ('boundary.picked(os.environ.get("INPUTS_GOT"), names())\n', "口の名の並びを解けない"),
        }
        for name, (script, why) in cases.items():
            with self.subTest(name):
                got = self.gated(script, reads=READS)
                self.assertEqual(len(got), 1, got)
                self.assertIn(TAKE, got[0])
                self.assertIn("節 take", got[0])
                self.assertIn("got", got[0])
                self.assertIn(why, got[0])

    def test_whole_ref_to_a_script_that_does_not_read_it_is_red(self):
        cases = {
            "INPUTS_GOT を読まない script": ({TAKE: "NAMES = ('ready', 'units')\nx = 1\n"}, "take", "INPUTS_GOT を読まない"),
            "直に書いた script": ({}, "|\n      print(1)", "script のファイルを引けない"),
            "名の取り違え": ({"workflows/line/scripts/other.py": GATE}, "take", "script のファイルを引けない"),
        }
        for name, (files, script, why) in cases.items():
            with self.subTest(name):
                line = LINE_HEAD + READS + f"  - id: take\n    script: {script}\n    timeout: 1728000000\n    with:\n      got: \"$judge.output\"\n"
                got = self.files({BLOCK: RETURNING, LINE: line, **files})
                self.assertEqual(len(got), 1, got)
                self.assertIn("節 take", got[0])
                self.assertIn("with.got", got[0])
                self.assertIn(why, got[0])

    def test_whole_ref_outside_a_script_with_is_red(self):
        places = {
            "include の with:": ("  - id: plan\n    include: works-factory-plan\n    with:\n      x: \"$judge.output\"\n", "with.x"),
            "workflow の with:": ("  - id: plan\n    workflow: works-factory-plan\n    with:\n      x: \"$judge.output\"\n", "with.x"),
            "bash": ("  - id: plan\n    bash: echo $judge.output\n", "bash"),
            "prompt": ("  - id: plan\n    prompt: see $judge.output\n", "prompt"),
            "when": ("  - id: plan\n    script: plan\n    when: \"$judge.output == 1\"\n", "when"),
            "approval の message": ("  - id: plan\n    approval:\n      message: \"$judge.output\"\n", "approval.message"),
            "loop_group の until_bash": ("  - id: plan\n    loop_group:\n      until_bash: '[ \"$judge.output\" = x ]'\n      nodes: []\n",
                                         "loop_group.until_bash"),
            "with: の値の入れ子の mapping": ("  - id: plan\n    script: plan\n    with:\n      x:\n        y: \"$judge.output\"\n", "with.x.y"),
            "with: の list の中": ("  - id: plan\n    script: plan\n    with:\n      x: [\"$judge.output\"]\n", "with.x.0"),
            "文の終わりの .": ("  - id: plan\n    script: plan\n    with:\n      x: \"$judge.output.\"\n", "with.x"),
            ".0": ("  - id: plan\n    script: plan\n    with:\n      x: \"$judge.output.0\"\n", "with.x"),
            "-x": ("  - id: plan\n    script: plan\n    with:\n      x: \"$judge.output-x\"\n", "with.x"),
            "outputs": ("  - id: plan\n    script: plan\n    with:\n      x: \"$judge.outputs\"\n", "with.x"),
            "文の中のまるごと": ("  - id: plan\n    script: plan\n    with:\n      x: \"a $judge.output b\"\n", "with.x"),
            "from の中の入れ子": ("  - id: plan\n    script: plan\n    with:\n      x: { from: { from: \"$judge.output\" } }\n", "with.x.from.from"),
        }
        for name, (node, where) in places.items():
            with self.subTest(name):
                got = self.files({BLOCK: RETURNING, LINE: LINE_HEAD + READS + node})
                self.assertEqual(len(got), 1, got)
                self.assertIn("節 plan", got[0])
                self.assertIn(where, got[0])
        anchored = (
            "name: works-factory-line\nx-bind: &bind\n  x: \"$judge.output\"\nnodes:\n  - id: judge\n    include: works-factory-judge\n" + READS +
            "  - id: plan\n    include: works-factory-plan\n    with:\n      <<: *bind\n"
        )
        with self.subTest("<<: で include の with: に引いた値"):
            got = self.files({BLOCK: RETURNING, LINE: anchored})
            self.assertEqual(len(got), 1, got)
            self.assertIn("with.x", got[0])

    def test_loop_prev_whole_ref_is_read_through_the_gate(self):
        line = (
            "name: works-factory-line\nnodes:\n  - id: rounds\n    loop_group:\n      max_iterations: 3\n      until_bash: 'true'\n      nodes:\n"
            "        - id: judge\n          include: works-factory-judge\n"
            "        - id: take\n          script: take\n          depends_on: [judge]\n          with:\n"
            "            got: \"$LOOP_PREV.judge.output\"\n"
        )
        self.assertEqual(self.files({BLOCK: RETURNING, LINE: line, TAKE: GATE}), [])
        got = self.files({BLOCK: RETURNING, LINE: line + READS, TAKE: 'got = json.loads(os.environ["INPUTS_GOT"])\n'})
        self.assertEqual(len(got), 1, got)
        self.assertIn("節 take", got[0])
        self.assertIn("boundary.picked の呼びが無い", got[0])


if __name__ == "__main__":
    unittest.main()
