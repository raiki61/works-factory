"""block と graph の返りが 1 つのノードの構造体で、仕事の結末の欄を持つ（`workflows/AGENTS.md` の E5 の機械の行）。

- どの workflow にも `returns:` と `outcome_field:` が在り、返すノードが `output_format` を持ち、`outcome_field` の欄がその `required` に在る（止めた Archon は `required` に在る boolean の欄しか受けない）。
- 返りに `report`（報告に載せる日本語の行の配列）が在ることは `tests/layers/test_block_shape.py`（7.1 の 8）が見る。
- graph が欄つきの参照 `$<include の id>.output.<欄>` で読む欄が返すノードの `output_format` に在るかは Archon の `validate`（`tests/layers/test_archon_validate.py`）が照らすので、ここでは照らさない。まるごとの参照 `$<include の id>.output` は validate が欄を見られないので、受けてよい置き場（script のノードの `with:<鍵>` の直の字か `with:<鍵>.from` の字）と、受けた script が `ports.picked` の口 1 つで読み、宣言した名が `output_format` に在ることをここで照らす。受けた script は環境変数を字のままの鍵でだけ読み、名を組む・回す・写す・渡す読みは赤。
- 読み手ゼロなら赤（持ち主の決め `declared-io`）。block の返す節の `output_format` の欄は、どこかの graph（その block を include か
  workflow で呼ぶ物。`loop_group` の中と `$LOOP_PREV.` も）が欄つきの参照 `$<id>.output.<欄>` で読むか、まるごとの参照を受けた口
  `ports.picked` が宣言した名（受け皿の `with:` の `names` と `optional=` を含む）に在る。入口（一番上のグラフ line・chain と、どの graph も
  呼ばない workflow）の返りは人（`workflow get`）と起動の殻が読むので照らさない。block の `inputs:` の名は、その block の YAML の字の
  `$INPUTS.<名>` か、その block の `scripts/`・`src/` の Python の `INPUTS_<名>` の読みが読む（ほかの名の `with:` の鍵で script に渡した字は
  その名の読みでない）。種 `tests/layers/seeds/e5-unread-return`・`e5-unread-input`。
- 許す物の表（`ALLOWED["E5"]`）は持たない（持ち主の決め `shape-checks-only`）。
- 輪（`loop_group`）の中の役のノードは自分の `with:` を結ばない（落とし穴 K5。役の `with:` は include の時に既定の字で固まる。前の周の値は輪の頭の script のノードが `$LOOP_PREV` で結んで返す）。種 `tests/layers/seeds/k5-loop-role-with`。
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
    "  - id: verdict\n    script: stub\n"
    "    output_format:\n      type: object\n      properties:\n        ready: {type: boolean}\n        units: {type: array, items: {type: string}}\n"
    "      required: [ready, units]\n"
)
TAKE = "workflows/line/scripts/take.py"
# graph も返りを持つ（どの workflow にも returns: と outcome_field:）。線の返す節 result
RESULT = ("  - id: result\n    script: stub\n"
          "    output_format:\n      type: object\n      properties:\n        ok: {type: boolean}\n      required: [ok]\n")
LINE_TOP = "name: works-factory-line\nreturns: result\noutcome_field: ok\nnodes:\n" + RESULT
LINE_HEAD = LINE_TOP + "  - id: judge\n    include: works-factory-judge\n"
# 返りの欄を欄つきの参照で読む節（欄つきの参照は validate が照らし、ここでは数えない。まるごとの参照と並べて置く）
READS = (
    "  - id: reader\n    script: reader\n    with:\n"
    "      ready: $judge.output.ready\n      units: $judge.output.units\n"
)
GATE_NAMES = 'NAMES = ("ready", "units")\n'
GATE_CALL = 'got = ports.picked(os.environ.get("INPUTS_GOT"), NAMES)\n'
GATE = GATE_NAMES + GATE_CALL
# 受け皿の口（workflows/line/scripts/returned.py と同じ形）。名の並びは節の with: の names
DECLARED = 'got = ports.picked(os.environ.get("INPUTS_GOT"), ports.text(os.environ.get("INPUTS_NAMES")).split())\n'


def take_node(value, names=None):
    """script の節 take。with: の got に value（YAML の字）を結び、names を渡せば with: の names に結ぶ"""
    declared = "" if names is None else f"      names: {names}\n"
    return f"  - id: take\n    script: take\n    with:\n      got: {value}\n{declared}"


class BlockReturnsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E5", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E5", SEEDS / "e5")
        self.assertEqual(len(got), 1, got)
        self.assertIn(BLOCK, got[0])
        self.assertIn("outcome_field の欄 ready が返す節の required に無い", got[0])

    def problems(self, block, line):
        return self.files({BLOCK: block, LINE: line})

    def files(self, files):
        with tree(files) as root:
            return scan.problems("E5", root)

    def test_missing_returns_or_outcome_field_is_red(self):
        for drop in ("returns: verdict\n", "outcome_field: ready\n"):
            with self.subTest(drop=drop):
                got = self.problems(RETURNING.replace(drop, ""), LINE_TOP)
                self.assertTrue(any(drop.split(":")[0] in line for line in got), got)

    def test_returning_node_without_output_format_is_red(self):
        block = (
            "name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n"
            "  - id: verdict\n    script: stub\n"
        )
        got = self.problems(block, LINE_TOP)
        self.assertTrue(any("output_format" in line for line in got), got)

    def test_outcome_field_not_required_is_red(self):
        block = RETURNING.replace("required: [ready, units]", "required: [units]")
        line = (
            LINE_HEAD +
            "    when: \"$judge.output.ready == true\"\n  - id: x\n    script: x\n"
            "    with:\n      units: $judge.output.units\n"
        )
        got = self.problems(block, line)
        self.assertEqual(len(got), 1, got)
        self.assertIn("required", got[0])

    def gated(self, script, value='"$judge.output"', reads="", files=None, names=None):
        """script の節 take が with: の got でブロック judge の返りをまるごとで受ける木。script の字は workflows/line/scripts/take.py"""
        line = LINE_HEAD + reads + take_node(value, names)
        return self.files({BLOCK: RETURNING, LINE: line, TAKE: script, **(files or {})})

    def test_whole_ref_read_through_the_gate_is_clean(self):
        forms = {
            "字のまま": (GATE, '"$judge.output"', {}, None),
            "{from, if_skipped}": (GATE, '{ from: "$judge.output", if_skipped: null }', {}, None),
            "添字で読む": (GATE_NAMES + 'got = ports.picked(os.environ["INPUTS_GOT"], NAMES)\n', '"$judge.output"', {}, None),
            "* 展開の名の並び": ('BASE = ("ready",)\nNAMES = (*BASE, "units")\n' + GATE_CALL, '"$judge.output"', {}, None),
            "lib の部品の定数": ('got = ports.picked(os.environ.get("INPUTS_GOT"), board.NAMES)\n', '"$judge.output"',
                            {"lib/board.py": 'NAMES = ("ready", "units")\n'}, None),
            "受け皿の with: の names": (DECLARED, '"$judge.output"', {}, '"ready units"'),
            "別の INPUTS_ を字のままの鍵で読む": (GATE + 'plan = ports.value(os.environ.get("INPUTS_PLAN"))\n'
                                         'run = os.environ["WORKFLOW_ID"]\nhome = os.getenv("HOME", "")\n', '"$judge.output"', {}, None),
        }
        for name, (script, value, files, names) in forms.items():
            with self.subTest(name):
                self.assertEqual(self.gated(script, value, files=files, names=names), [])
        anchored = (
            "name: works-factory-line\nreturns: result\noutcome_field: ok\nx-bind: &bind\n  got: \"$judge.output\"\nnodes:\n" + RESULT +
            "  - id: judge\n    include: works-factory-judge\n"
            "  - id: take\n    script: take\n    with:\n      <<: *bind\n"
        )
        with self.subTest("<<: で引いた with: の値"):
            self.assertEqual(self.files({BLOCK: RETURNING, LINE: anchored, TAKE: GATE}), [])

    def test_role_in_a_loop_group_binding_its_own_with_is_red(self):
        """輪の中の役は自分の with: を結ばない（K5）。script の節は結んでよい"""
        yaml = ("name: works-factory-plan\nreturns: head\noutcome_field: ok\nnodes:\n  - id: g\n    loop_group:\n      nodes:\n"
                "        - id: head\n          script: head\n          with: {reason: $LOOP_PREV.take.output.reason}\n"
                "        - id: role\n          prompt: x\n          with: {reason: $LOOP_PREV.take.output.reason}\n")
        got = self.files({"workflows/plan/works-factory-plan.yaml": yaml})
        self.assertTrue(any("輪の中の役 role" in line for line in got), got)
        self.assertFalse(any("役 head" in line for line in got), got)

    def test_loop_role_seed_is_one_violation(self):
        got = scan.problems("E5", SEEDS / "k5-loop-role-with")
        self.assertEqual(len(got), 1, got)
        self.assertIn("輪の中の役", got[0])

    def test_graphs_need_returns_too(self):
        """graph（線も）も returns: と outcome_field: を持つ"""
        got = self.files({LINE: "name: works-factory-line\nreturns: result\nnodes: []\n"})
        self.assertIn(f"{LINE}:1: outcome_field: が無い", got)

    def test_unread_seeds_are_one_violation_each(self):
        for seed, why in (("e5-unread-return", "返りの欄 note に読み手が無い"), ("e5-unread-input", "入力 base に読み手が無い")):
            with self.subTest(seed):
                got = scan.problems("E5", SEEDS / seed)
                self.assertEqual(len(got), 1, got)
                self.assertIn(BLOCK, got[0])
                self.assertIn(why, got[0])

    def test_return_field_without_a_reader_is_red(self):
        """返りの欄は、どこかの graph が欄つきの参照で読むか、口が宣言した名に在る（declared-io の「読み手ゼロなら赤」）"""
        self.assertEqual(self.problems(RETURNING, LINE_HEAD + READS), [])
        got = self.problems(RETURNING, LINE_HEAD + "  - id: reader\n    script: reader\n    with:\n      ready: $judge.output.ready\n")
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{BLOCK}:11:"), got)
        self.assertIn("返りの欄 units に読み手が無い", got[0])

    def test_field_read_only_through_the_gate_counts_by_the_declared_names(self):
        """まるごとの参照だけで読む欄は、口の宣言した名（optional= と受け皿の with: の names を含む）に在れば読まれている"""
        self.assertEqual(self.gated(GATE), [])
        self.assertEqual(self.gated('NAMES = ("ready",)\ngot = ports.picked(os.environ.get("INPUTS_GOT"), NAMES, optional=("units",))\n'), [])
        for name, (script, names) in {"名の並び": ('NAMES = ("ready",)\n' + GATE_CALL, None),
                                      "受け皿の with: の names": (DECLARED, '"ready"')}.items():
            with self.subTest(name):
                got = self.gated(script, names=names)
                self.assertEqual(len(got), 1, got)
                self.assertIn("返りの欄 units に読み手が無い", got[0])

    def test_field_reads_in_any_calling_graph_count(self):
        """読み手はどの graph でもよい（include の id で引く。workflow: のノード・輪の中・$LOOP_PREV. も）"""
        r1 = ("name: works-factory-r1\nreturns: take\noutcome_field: ok\nnodes:\n  - id: j\n    include: works-factory-judge\n"
              "  - id: take\n    script: take\n    with:\n      units: $j.output.units\n"
              "    output_format:\n      type: object\n      properties:\n        ok: {type: boolean}\n      required: [ok]\n")
        line = LINE_HEAD + "  - id: x\n    script: x\n    when: \"$judge.output.ready == true\"\n"
        self.assertEqual(self.files({BLOCK: RETURNING, LINE: line, "workflows/r1/works-factory-r1.yaml": r1}), [])
        called = LINE_TOP + "  - id: w\n    workflow: works-factory-judge\n  - id: x\n    script: x\n    with:\n      a: $w.output.ready\n"
        got = self.problems(RETURNING, called)
        self.assertEqual(len(got), 1, got)
        self.assertIn("返りの欄 units に読み手が無い", got[0])
        looped = (LINE_TOP + "  - id: rounds\n    loop_group:\n      until_bash: 'true'\n      nodes:\n"
                  "        - id: judge\n          include: works-factory-judge\n"
                  "        - id: x\n          script: x\n          with: {a: $LOOP_PREV.judge.output.ready, b: $judge.output.units}\n")
        self.assertEqual(self.problems(RETURNING, looped), [])

    def test_entry_returns_are_not_checked(self):
        """どの graph も呼ばない workflow と一番上のグラフ（line・chain）の返りは人と起動の殻が読むので、読み手を照らさない"""
        self.assertEqual(self.problems(RETURNING, LINE_TOP), [])
        self.assertEqual(self.files({LINE: LINE_TOP.replace("ok: {type: boolean}\n", "ok: {type: boolean}\n        extra: {type: string}\n")}), [])

    def test_block_input_without_a_reader_is_red(self):
        """block の inputs: の名は、その block の YAML の $INPUTS.<名> か、scripts/・src/ の INPUTS_<名> の読みが読む"""
        head = ("name: works-factory-judge\ninputs:\n  request: {default: '', description: 'text: x'}\n"
                "returns: verdict\noutcome_field: ready\nnodes:\n  - id: verdict\n    script: verdict\n")
        tail = ("    output_format:\n      type: object\n      properties:\n        ready: {type: boolean}\n      required: [ready]\n")
        line = LINE_HEAD + "  - id: x\n    script: x\n    with:\n      a: $judge.output.ready\n"
        script = "workflows/judge/scripts/verdict.py"
        green = {
            "YAML の with: の $INPUTS": (head + "    with:\n      request: \"$INPUTS.request\"\n" + tail, {}),
            "script の INPUTS_": (head + tail, {script: 'raw = os.environ.get("INPUTS_REQUEST")\n'}),
            "src の INPUTS_": (head + tail, {"workflows/judge/src/steps.py": 'raw = os.environ["INPUTS_REQUEST"]\n'}),
        }
        for name, (block, files) in green.items():
            with self.subTest(name):
                self.assertEqual(self.files({BLOCK: block, LINE: line, **files}), [])
        red = {
            "読み手が無い": (head + tail, {}),
            "別の名の with: の鍵で渡した字を読む": (head + "    with:\n      text: other\n" + tail, {script: 'raw = os.environ.get("INPUTS_TEXT")\n'}),
            "ほかの block の script が読む": (head + tail, {"workflows/plan/scripts/x.py": 'raw = os.environ.get("INPUTS_REQUEST")\n'}),
        }
        for name, (block, files) in red.items():
            with self.subTest(name):
                got = self.files({BLOCK: block, LINE: line, **files})
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{BLOCK}:3:"), got)
                self.assertIn("入力 request に読み手が無い", got[0])

    def test_whole_ref_in_any_graph_is_checked(self):
        """まるごとの参照は線の外の graph（include を持つ workflow）でも照らす"""
        graph = ("name: works-factory-r1\nreturns: take\noutcome_field: ok\nnodes:\n  - id: judge\n    include: works-factory-judge\n"
                 "  - id: take\n    script: take\n    with:\n      got: \"$judge.output\"\n"
                 "    output_format:\n      type: object\n      properties:\n        ok: {type: boolean}\n      required: [ok]\n")
        files = {BLOCK: RETURNING, "workflows/r1/works-factory-r1.yaml": graph}
        self.assertEqual(self.files({**files, "workflows/r1/scripts/take.py": GATE}), [])
        got = self.files({**files, "workflows/r1/scripts/take.py": 'got = json.loads(os.environ["INPUTS_GOT"])\n'})
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("workflows/r1/scripts/take.py:"), got)
        self.assertIn("呼びが 0 個", got[0])

    def test_read_bound_once_and_passed_to_the_gate_is_clean(self):
        """読みを 1 度だけ束ねて口でだけ読む形（関数の中・組の代入）と、with: の names 以外の鍵の字・束ねた名の並び・optional= の字の tuple"""
        forms = {
            "束ねて渡す": (GATE_NAMES + 'raw = os.environ.get("INPUTS_GOT")\ngot = ports.picked(raw, NAMES)\n', None, "names"),
            "関数の中の組の代入": (GATE_NAMES + 'def f():\n    a, raw = os.environ.get("INPUTS_A"), os.environ.get("INPUTS_GOT")\n'
                              '    return ports.picked(raw, NAMES, optional=("note",))\n', None, "names"),
            "受け皿の名を束ねる": ('def f():\n    raw_names, raw_got = os.environ.get("INPUTS_NAMES"), os.environ.get("INPUTS_GOT")\n'
                              '    names = ports.text(raw_names).split()\n    return ports.picked(raw_got, names, optional=("optional",))\n',
                              '"ready units"', "names"),
            "返しの field の鍵": ('FIELDS = ports.text(os.environ.get("INPUTS_FIELD")).split()\nGOT = os.environ.get("INPUTS_GOT")\n'
                              'got = ports.picked(GOT, FIELDS)\n', '"ready units"', "field"),
        }
        for name, (script, names, key) in forms.items():
            with self.subTest(name):
                line = LINE_HEAD + take_node('"$judge.output"') + ("" if names is None else f"      {key}: {names}\n")
                self.assertEqual(self.files({BLOCK: RETURNING, LINE: line, TAKE: script}), [])

    def test_bound_read_used_elsewhere_is_red(self):
        """束ねた読みを口の外でも読むと、まるごとの値を口の外で使える。束ねが 2 つも同じ"""
        cases = {
            "口の外でも読む": GATE_NAMES + 'raw = os.environ.get("INPUTS_GOT")\ngot = ports.picked(raw, NAMES)\nx = json.loads(raw)\n',
            "束ねが 2 つ": GATE_NAMES + 'raw = os.environ.get("INPUTS_GOT")\nraw = os.environ.get("INPUTS_GOT")\ngot = ports.picked(raw, NAMES)\n',
        }
        for name, script in cases.items():
            with self.subTest(name):
                got = self.gated(script, reads=READS)
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{TAKE}:"), got)

    def test_common_field_name_declared_by_a_real_receiver_is_red(self):
        """本物の木で、線の受け皿 judge-out の names にありふれた名（note）を足すと、judge の返りに無いので赤（線の YAML の行を指す）"""
        line = "workflows/line/works-factory-line.yaml"
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for part in ("workflows", "lib"):
                shutil.copytree(ROOT / part, root / part, ignore=shutil.ignore_patterns("tests", "fixtures", "__pycache__"))
            before = scan.problems("E5", root)
            text = (root / line).read_text(encoding="utf-8")
            head = text.index("names: \"", text.index("\n  - id: judge-out\n")) + len("names: \"")
            (root / line).write_text(text[:head] + "note " + text[head:], encoding="utf-8")
            got = [p for p in scan.problems("E5", root) if p not in before]
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{line}:"), got)
        self.assertIn("宣言した欄 note が works-factory-judge の返りに無い", got[0])

    def test_declared_name_not_in_the_output_format_is_red(self):
        got = self.gated('NAMES = ("ready", "units", "extra")\n' + GATE_CALL)
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{TAKE}:2:"), got)
        self.assertIn("宣言した欄 extra が works-factory-judge の返りに無い", got[0])
        got = self.gated(DECLARED, names='"ready units extra"')
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith(f"{LINE}:"), "with: の names の宣言は YAML の行を指す")
        self.assertIn("宣言した欄 extra", got[0])

    def test_names_that_do_not_resolve_are_red(self):
        """口の名の並びは読める 3 つの形だけで、ほかは解かずに赤"""
        call = 'got = ports.picked(os.environ.get("INPUTS_GOT"), %s)\n'
        cases = {
            "関数の返り": (call % "names()", None),
            "字の tuple を直に書く": (call % '("ready", "units")', None),
            "list の定数": ('NAMES = ["ready", "units"]\n' + GATE_CALL, None),
            "頭の定数を関数の中で束ね直す": (GATE_NAMES + 'def f():\n    NAMES = ("ready", "units", "x")\n    ' + GATE_CALL, None),
            "後の += で足す": (GATE_NAMES + 'NAMES += ("x",)\n' + GATE_CALL, None),
            "引数の名": ('def f(NAMES):\n    ' + GATE_CALL, None),
            "鍵の名で渡す": ('got = ports.picked(os.environ.get("INPUTS_GOT"), names=NAMES)\n' + GATE_NAMES, None),
            "names の字に足す": (DECLARED.replace(".split())", '.split() + ["x"])'), '"ready units"'),
            "names の外の入力の字": (DECLARED.replace("INPUTS_NAMES", "INPUTS_OTHER"), '"ready units"'),
            "with: に names が無い": (DECLARED, None),
            "names が参照": (DECLARED, '"$x.output.names"'),
            "lib の定数が字の tuple でない": ('got = ports.picked(os.environ.get("INPUTS_GOT"), board.NAMES)\n', None),
        }
        for name, (script, names) in cases.items():
            with self.subTest(name):
                got = self.gated(script, reads=READS, names=names, files={"lib/board.py": "NAMES = names()\n"})
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{TAKE}:"), got)
                self.assertIn("名の並びを解けない", got[0])

    def test_whole_ref_read_outside_the_gate_is_red(self):
        """まるごとの参照は口 ports.picked の 1 つの呼びでだけ読み、その 1 つ目の引数は os.environ の読みそのもの（か、それを 1 度だけ束ねて口でだけ読む名）。ほかの読みは赤"""
        cases = {
            "口が無く json.loads で読む": ('got = json.loads(os.environ["INPUTS_GOT"])\n', "呼びが 0 個"),
            "ports.value で読む": ('got = ports.value(os.environ.get("INPUTS_GOT"))\n', "呼びが 0 個"),
            "口でない関数で読み、globals で引く": ('def f(env):\n    return {"got": ports.value(env.get("INPUTS_GOT"))}\n'
                                             'def stalled(env):\n    return globals()["f"](env)["got"].get("stall")\n', "呼びが 0 個"),
            "口の呼びが 2 つ": (GATE + 'again = ports.picked(os.environ.get("INPUTS_GOT"), NAMES)\n', "呼びが 2 個"),
            "口の外にもう 1 つ字": (GATE + 'again = os.environ.get("INPUTS_GOT")\n', "渡す読みの外"),
            "口の中で walrus で取っておく": (GATE_NAMES + 'got = ports.picked(raw := os.environ.get("INPUTS_GOT"), NAMES)\n'
                                       '_typo = json.loads(raw or "{}").get("no_such_field")\n', "口でだけ読む名でない"),
            "口の中で包む関数で取っておく": (GATE_NAMES + 'got = ports.picked(keep(os.environ.get("INPUTS_GOT")), NAMES)\n', "口でだけ読む名でない"),
            "os.environ でない物の get": (GATE_NAMES + 'got = ports.picked(kept.get("INPUTS_GOT"), NAMES)\n', "口でだけ読む名でない"),
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
        赤"""
        cases = {
            "名を組む小関数": ('def env(name):\n    return ports.value(os.environ.get(f"INPUTS_{name}"))\n'
                          'got2 = env("TESTS")["fingerprint"]\n', 2),
            "名を組む内包": ('plans = {k: ports.value(os.environ.get(f"INPUTS_{k.upper()}")) for k in ("plan", "fix")}\n', 1),
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
                line = LINE_HEAD + READS + f"  - id: take\n    script: {script}\n    with:\n      got: \"$judge.output\"\n"
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
            "name: works-factory-line\nreturns: result\noutcome_field: ok\nx-bind: &bind\n  x: \"$judge.output\"\nnodes:\n" + RESULT +
            "  - id: judge\n    include: works-factory-judge\n" + READS +
            "  - id: plan\n    include: works-factory-plan\n    with:\n      <<: *bind\n"
        )
        with self.subTest("<<: で include の with: に引いた値"):
            got = self.files({BLOCK: RETURNING, LINE: anchored})
            self.assertEqual(len(got), 1, got)
            self.assertIn("with.x", got[0])

    def test_loop_prev_whole_ref_is_read_through_the_gate(self):
        line = (
            LINE_TOP + "  - id: rounds\n    loop_group:\n      max_iterations: 3\n      until_bash: 'true'\n      nodes:\n"
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


# #851 の受け渡しの形の照らし（scan._shapes）。書き手 judge の返りを graph line が plan の入力へ結ぶ木
PLAN = "workflows/plan/works-factory-plan.yaml"
UNITS = "workflows/plan/schemas/units.schema.json"
POINTER = ("{type: object, additionalProperties: false, required: [type, run_id, path], description: '%s',"
           " properties: {type: {type: string, enum: [archon_artifact]}, run_id: {type: string}, path: {type: string}}}")


def judge_returning(fields: str) -> str:
    return ("name: works-factory-judge\nreturns: verdict\noutcome_field: ready\nnodes:\n  - id: verdict\n    script: stub\n"
            "    output_format:\n      type: object\n      required: [ready]\n      properties:\n        ready: {type: boolean}\n"
            + "".join(f"        {line}\n" for line in fields.splitlines()))


def plan_reading(name: str, form: str) -> str:
    return (f"name: works-factory-plan\ninputs:\n  {name}: {{default: '', description: '{form}: 読む物'}}\nreturns: finish\n"
            "outcome_field: ok\nnodes:\n  - id: finish\n    script: finish\n    with: {x: \"$INPUTS.%s\"}\n" % name +
            "    output_format: {type: object, required: [ok], properties: {ok: {type: boolean}}}\n")


def line_wiring(key: str, ref: str) -> str:
    return (LINE_TOP + "  - id: judge\n    include: works-factory-judge\n  - id: plan\n    include: works-factory-plan\n"
            f"    with:\n      {key}: \"{ref}\"\n")


class ShapesTest(unittest.TestCase):
    """終わりの条件（issue #851）: 中身を宣言しない object・pointer の欄の form の欠け・配線の両端の形の食い違いが赤になる"""

    def problems(self, files):
        """形の赤だけ（小さな木の返りの欄の読み手ゼロの赤は数えない）"""
        with tree(files) as root:
            return [line for line in scan.problems("E5", root) if "に読み手が無い" not in line]

    def wired(self, fields, form, key="units", ref="$judge.output.units", shape=None):
        files = {BLOCK: judge_returning(fields), PLAN: plan_reading(key, form), LINE: line_wiring(key, ref)}
        if shape is not None:
            files[UNITS] = shape
        return self.problems(files)

    UNITS_SHAPE = '{"type": "array", "items": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string"}}}}'

    def test_fitting_wire_is_clean(self):
        self.assertEqual(self.wired("units: {type: array, items: {type: object, properties: {key: {type: string}}}}",
                                    "json(units.schema.json)", shape=self.UNITS_SHAPE), [])

    def test_open_object_in_an_output_format_is_red(self):
        got = self.wired("units: {type: array, items: {type: object}}", "json(units.schema.json)", shape=self.UNITS_SHAPE)
        self.assertTrue(any("$.properties.units.items が中身を宣言しない" in line for line in got), got)

    def test_reader_needs_a_field_the_writer_does_not_declare(self):
        """graph の配線の 1 本で、書き手の宣言に無い欄を読み手が要ると赤"""
        got = self.wired("units: {type: array, items: {type: object, properties: {name: {type: string}}}}",
                         "json(units.schema.json)", shape=self.UNITS_SHAPE)
        self.assertEqual(len(got), 1, got)
        self.assertIn("読み手の要る欄 key が書き手の形に無い", got[0])

    def test_types_and_enums_must_fit(self):
        shape = '{"type": "object", "properties": {"verdict": {"type": "string", "enum": ["same", "differs"]}}, "required": ["verdict"]}'
        got = self.wired("units: {type: object, properties: {verdict: {type: string, enum: [same, other]}}}",
                         "json(units.schema.json)", shape=shape)
        self.assertTrue(any("書き手の語" in line for line in got), got)
        got = self.wired("units: {type: string}", "json(units.schema.json)", shape=shape)
        self.assertTrue(any("書き手の型 ['string']" in line for line in got), got)

    def test_pointer_field_without_a_form_is_red(self):
        got = self.wired("units: " + POINTER % "置き場のファイル", "file")
        self.assertEqual(len(got), 1, got)
        self.assertIn("description に指す先の form", got[0])

    def test_wire_ends_must_name_the_same_shape(self):
        """JSON を運ぶ辺の両端の form は字のまま同じ。名を変えた形の写し・json を file で受ける・jsonl を json で受けるは赤"""
        for writer, reader in (("json(shared:a.schema.json)", "json(shared:b.schema.json)"), ("json(shared:a.schema.json)", "file"),
                               ("jsonl(shared:a.schema.json)", "json(shared:a.schema.json)"), ("file", "json(shared:a.schema.json)")):
            with self.subTest(writer=writer, reader=reader):
                files = {BLOCK: judge_returning("units: " + POINTER % f"{writer}: 置き場のファイル"), PLAN: plan_reading("units", reader),
                         LINE: line_wiring("units", "$judge.output.units"),
                         "workflows/.shared/schemas/a.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}',
                         "workflows/.shared/schemas/b.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}'}
                got = [line for line in self.problems(files) if "with.units" in line]
                self.assertEqual(len(got), 1, got)
                self.assertIn("が違う", got[0])

    def test_inputs_pass_through_is_wired_too(self):
        line = LINE_TOP.replace("nodes:\n", "inputs:\n  units: {default: '', description: 'json(shared:a.schema.json): 単位'}\nnodes:\n") \
            + "  - id: plan\n    include: works-factory-plan\n    with:\n      units: \"$INPUTS.units\"\n"
        files = {PLAN: plan_reading("units", "json(shared:b.schema.json)"), LINE: line,
                 "workflows/.shared/schemas/a.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}',
                 "workflows/.shared/schemas/b.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}'}
        got = [p for p in self.problems(files) if "with.units" in p]
        self.assertEqual(len(got), 1, got)

    def test_script_writer_in_the_graph_is_wired_too(self):
        """配線の書き手は include の返りだけでなく、graph の script の節の output_format も（中継の節の欄）"""
        line = (LINE_TOP + "  - id: relay\n    script: relay\n    output_format:\n      type: object\n      properties:\n"
                f"        units: {POINTER % 'json(shared:a.schema.json): 中継'}\n"
                "  - id: plan\n    include: works-factory-plan\n    with:\n      units: \"$relay.output.units\"\n")
        files = {PLAN: plan_reading("units", "file"), LINE: line,
                 "workflows/.shared/schemas/a.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}'}
        got = [p for p in self.problems(files) if "with.units" in p]
        self.assertEqual(len(got), 1, got)

    def test_port_calls_name_a_declared_form_literally(self):
        """block の口の呼びの形の名と form は字のままで、その block の宣言の form の組に在る"""
        base = {PLAN: plan_reading("units", "json(shared:a.schema.json)"), LINE: LINE_TOP,
                "workflows/.shared/schemas/a.schema.json": '{"type": "object", "properties": {"x": {"type": "string"}}}'}
        script = "workflows/plan/scripts/finish.py"
        cases = {'ports.json(os.environ.get("INPUTS_UNITS"), "shared:a.schema.json")\n': [],
                 'ports.file(os.environ.get("INPUTS_UNITS"), "json(shared:a.schema.json)")\n': [],
                 'ports.json(os.environ.get("INPUTS_UNITS"), NAME)\n': ["字のままでない"],
                 'ports.file(os.environ.get("INPUTS_UNITS"), "file")\n': ["宣言の form の組に無い"],
                 'ports.json(os.environ.get("INPUTS_UNITS"), "shared:b.schema.json")\n': ["宣言の form の組に無い"],
                 'ports.returns({"p": {"type": "archon_artifact", "run_id": "r", "path": "x.json"}})\n': ["札を手で組む"],
                 'ports.returns({"p": {"type": ports.POINTER_TYPE, "run_id": "r", "path": "x.json"}})\n': ["札を手で組む"],
                 'ok = got.get("type") == ports.POINTER_TYPE\n': []}
        for code, words in cases.items():
            with self.subTest(code):
                got = [p for p in self.problems({**base, script: code}) if "finish.py" in p]
                self.assertEqual(len(got), len(words), got)
                for word, line in zip(words, got):
                    self.assertIn(word, line)
