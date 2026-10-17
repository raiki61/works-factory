"""ブロックの返りが 1 つの節の構造体で、返りの欄に読み手が在る（workflows/AGENTS.md の E5 の機械の行）。

在るブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。
返りの欄のうち、線の `with:`・`when:`・返しの節の `from` の誰も `$<include の id>.output.<欄>` で読まず、まるごとの参照
`$<include の id>.output` を受ける script の口（boundary.picked）の宣言した名にも無い物は赤。
欄つきの参照の読む欄が返す節に在るかは Archon の `validate` が照らす（tests/layers/test_archon_validate.py）ので、ここでは照らさない。
まるごとの参照は validate が欄を見られないので、ここで照らす: 受けてよい置き場は script の節の `with:<鍵>` の直の字か `with:<鍵>.from` の字で、
ほかは赤。受けた script は口の呼び 1 つで読み、口の名の並びは module の頭の字の tuple・lib の部品の定数・with: の names の字のどれかで、
宣言した名は返す節の output_format に在る。宣言の外の欄は口が値を返さない（tests/workflows/test_input_reads.py）。
受けた script は環境変数を字のままの鍵でだけ読み、名を組む・回す・写す・渡す読みは赤。
"""
import pathlib
import shutil
import tempfile
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
# 受け皿の口（workflows/line/scripts/returned.py と同じ形）。名の並びは節の with: の names
DECLARED = 'got = boundary.picked(os.environ.get("INPUTS_GOT"), boundary.text(os.environ.get("INPUTS_NAMES")).split())\n'


def take_node(value, names=None):
    """script の節 take。with: の got に value（YAML の字）を結び、names を渡せば with: の names に結ぶ"""
    declared = "" if names is None else f"      names: {names}\n"
    return f"  - id: take\n    script: take\n    timeout: 1728000000\n    with:\n      got: {value}\n{declared}"


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

    def gated(self, script, value='"$judge.output"', reads="", files=None, names=None):
        """script の節 take が with: の got でブロック judge の返りをまるごとで受ける木。script の字は workflows/line/scripts/take.py"""
        line = LINE_HEAD + reads + take_node(value, names)
        return self.files({BLOCK: RETURNING, LINE: line, TAKE: script, **(files or {})})

    def test_whole_ref_read_through_the_gate_is_clean(self):
        forms = {
            "字のまま": (GATE, '"$judge.output"', {}, None),
            "{from, if_skipped}": (GATE, '{ from: "$judge.output", if_skipped: null }', {}, None),
            "* 展開の名の並び": ('BASE = ("ready",)\nNAMES = (*BASE, "units")\n' + GATE_CALL, '"$judge.output"', {}, None),
            "lib の部品の定数": ('got = boundary.picked(os.environ.get("INPUTS_GOT"), board.NAMES)\n', '"$judge.output"',
                            {"lib/board.py": 'NAMES = ("ready", "units")\n'}, None),
            "受け皿の with: の names": (DECLARED, '"$judge.output"', {}, '"ready units"'),
            "別の INPUTS_ を字のままの鍵で読む": (GATE + 'plan = boundary.value(os.environ.get("INPUTS_PLAN"))\n'
                                         'run = os.environ["WORKFLOW_ID"]\nhome = os.getenv("HOME", "")\n', '"$judge.output"', {}, None),
        }
        for name, (script, value, files, names) in forms.items():
            with self.subTest(name):
                self.assertEqual(self.gated(script, value, files=files, names=names), [])
        anchored = (
            "name: works-factory-line\nx-bind: &bind\n  got: \"$judge.output\"\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
            "  - id: take\n    script: take\n    timeout: 1728000000\n    with:\n      <<: *bind\n"
        )
        with self.subTest("<<: で引いた with: の値"):
            self.assertEqual(self.files({BLOCK: RETURNING, LINE: anchored, TAKE: GATE}), [])

    def test_declared_name_not_in_the_output_format_is_red(self):
        got = self.gated('NAMES = ("ready", "units", "extra")\n' + GATE_CALL)
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{TAKE}:2:"), got)
        self.assertIn("宣言した欄 extra が works-factory-judge の返りに無い", got[0])
        got = self.gated(DECLARED, names='"ready units extra"')
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{LINE}:"), "with: の names の宣言は YAML の行を指す")
        self.assertIn("宣言した欄 extra", got[0])

    def test_field_not_declared_is_red(self):
        for name, (script, names) in {"script の名の並び": ('NAMES = ("ready",)\n' + GATE_CALL, None),
                                      "with: の names": (DECLARED, '"ready"')}.items():
            with self.subTest(name):
                got = self.gated(script, names=names)
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{BLOCK}:", got[0])
                self.assertIn("返りの欄 units に読み手が無い", got[0])

    def test_common_field_name_in_a_real_block_behind_a_receiver_is_red(self):
        """ありふれた名（note）の欄を fix の output_format に足すと、ほかのどこかの字に同じ名が在っても、受け皿の names に無いので赤"""
        fix = "workflows/fix/works-factory-fix.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for part in ("workflows", "lib"):
                shutil.copytree(ROOT / part, root / part, ignore=shutil.ignore_patterns("tests", "fixtures", "__pycache__"))
            text = (root / fix).read_text(encoding="utf-8")
            schema = text.index("properties:\n", text.index("output_format:", text.index("\n  - id: fix\n")))
            head = schema + len("properties:\n")
            indent = text[head:len(text) - len(text[head:].lstrip(" "))]
            (root / fix).write_text(text[:head] + f"{indent}note: {{ type: string }}\n" + text[head:], encoding="utf-8")
            got = scan.problems("E5", root)
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{fix}:"), got)
        self.assertIn("返りの欄 note に読み手が無い", got[0])

    def test_names_that_do_not_resolve_are_red(self):
        """口の名の並びは読める 3 つの形だけで、ほかは解かずに赤"""
        call = 'got = boundary.picked(os.environ.get("INPUTS_GOT"), %s)\n'
        cases = {
            "関数の返り": (call % "names()", None),
            "字の tuple を直に書く": (call % '("ready", "units")', None),
            "list の定数": ('NAMES = ["ready", "units"]\n' + GATE_CALL, None),
            "頭の定数を関数の中で束ね直す": (GATE_NAMES + 'def f():\n    NAMES = ("ready", "units", "x")\n    ' + GATE_CALL, None),
            "後の += で足す": (GATE_NAMES + 'NAMES += ("x",)\n' + GATE_CALL, None),
            "引数の名": ('def f(NAMES):\n    ' + GATE_CALL, None),
            "鍵の名で渡す": ('got = boundary.picked(os.environ.get("INPUTS_GOT"), names=NAMES)\n' + GATE_NAMES, None),
            "names の字に足す": (DECLARED.replace(".split())", '.split() + ["x"])'), '"ready units"'),
            "names の外の入力の字": (DECLARED.replace("INPUTS_NAMES", "INPUTS_OTHER"), '"ready units"'),
            "with: に names が無い": (DECLARED, None),
            "names が参照": (DECLARED, '"$x.output.names"'),
            "lib の定数が字の tuple でない": ('got = boundary.picked(os.environ.get("INPUTS_GOT"), board.NAMES)\n', None),
        }
        for name, (script, names) in cases.items():
            with self.subTest(name):
                got = self.gated(script, reads=READS, names=names, files={"lib/board.py": "NAMES = names()\n"})
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{TAKE}:"), got)
                self.assertIn("名の並びを解けない", got[0])

    def test_whole_ref_read_outside_the_gate_is_red(self):
        """前の目の反例の素通しの口 boundary.passed は無く、口を通らない読みは赤"""
        cases = {
            "口が無く json.loads で読む": ('got = json.loads(os.environ["INPUTS_GOT"])\n', "呼びが 0 個"),
            "boundary.value で読む": ('got = boundary.value(os.environ.get("INPUTS_GOT"))\n', "呼びが 0 個"),
            "素通しの boundary.passed": ('def f(env):\n    return {"got": boundary.passed(env.get("INPUTS_GOT"))}\n'
                                       'def stalled(env):\n    return globals()["f"](env)["got"].get("stall")\n', "呼びが 0 個"),
            "口の呼びが 2 つ": (GATE + 'again = boundary.picked(os.environ.get("INPUTS_GOT"), NAMES)\n', "呼びが 2 個"),
            "口の外にもう 1 つ字": (GATE + 'again = os.environ.get("INPUTS_GOT")\n', "呼びの外"),
        }
        for name, (script, why) in cases.items():
            with self.subTest(name):
                got = self.gated(script, reads=READS)
                self.assertEqual(len(got), 1, got)
                self.assertIn(TAKE, got[0])
                self.assertIn("節 take の with.got", got[0])
                self.assertIn(why, got[0])

    def test_env_read_by_a_built_name_or_walked_is_red(self):
        """まるごとの参照を受ける script は、環境変数を字のままの鍵でだけ読む。名を組む・回す・写す・ほかへ渡す読みは、値の流れを解かずに
        赤（前の目の反例 4 つ: 名を組む小関数・名を組む内包・頭の字で絞って回す・字をつなぐ）"""
        cases = {
            "名を組む小関数": ('def env(name):\n    return boundary.value(os.environ.get(f"INPUTS_{name}"))\n'
                          'got2 = env("TESTS")["fingerprint"]\n', 2),
            "名を組む内包": ('plans = {k: boundary.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in ("plan", "fix")}\n', 1),
            "頭の字で絞って回す（os を別の名で import）": ('more = {k: v for k, v in system.environ.items() if k.startswith("INPUTS_G")}\n', 1),
            "字をつなぐ": ('again = os.getenv("INPUTS_" + "REJUDGE")\n', 1),
            "添字の鍵を組む": ('again = os.environ["INPUTS_" + "X"]\n', 1),
            "keys": ('names = list(os.environ.keys())\n', 1),
            "values": ('vals = list(os.environ.values())\n', 1),
            "for で回す": ('for k in os.environ:\n    pass\n', 1),
            "dict で写す（os を別の名で import）": ('copy = dict(system.environ)\n', 1),
            "ほかの名へ渡す": ('e = os.environ\nmore = e.get("INPUTS_GOT_X")\n', 1),
            "引数で渡す": ('def f(env):\n    return env.get("INPUTS_X")\nf(os.environ)\n', 3),
            "from import": ('from os import environ as e\n', 1),
            "名を字で引く": ('more = getattr(os, "environ")\n', 1),
        }
        for name, (extra, line) in cases.items():
            with self.subTest(name):
                got = self.gated(GATE + extra, reads=READS)
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{TAKE}:{line + 2}:"), got)
                self.assertIn("字のままでない鍵で読むか、回す・写す・渡す", got[0])

    def test_whole_ref_to_a_script_that_cannot_be_read_is_red(self):
        cases = {
            "直に書いた script": ({}, "|\n      print(1)", "script のファイルを引けない"),
            "名の取り違え": ({"workflows/line/scripts/other.py": GATE}, "take", "script のファイルを引けない"),
            "構文の誤り": ({TAKE: "def (\n"}, "take", "構文として読めない"),
        }
        for name, (files, script, why) in cases.items():
            with self.subTest(name):
                line = LINE_HEAD + READS + f"  - id: take\n    script: {script}\n    timeout: 1728000000\n    with:\n      got: \"$judge.output\"\n"
                got = self.files({BLOCK: RETURNING, LINE: line, **files})
                self.assertEqual(len(got), 1, got)
                self.assertIn("節 take の with.got", got[0])
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
        self.assertIn("呼びが 0 個", got[0])

if __name__ == "__main__":
    unittest.main()
