"""承認ノードの形（`workflows/AGENTS.md` の E16 の機械の行。持ち主の決め `asf-way-gates-fanout`）。

- 全部の graph と block の承認ノードが `wait:` の `attention` で `form: select` を持ち、`options` に `lib/answer.py` の答えの語（`GO_WORDS`・`STOP_WORDS`。`STOP_WORDS` は `REJECT` を含む）を全部持つ（止めた Archon は `options` に無い答えを拒み、run は承認ノードで止まったまま）。
- `approval:` のノードが無い。どのグラフも頭に `interactive` を書かない（止めた Archon は読み込みで非推奨の警告を出し、効かない）。
- ループ（`loop_group`）の本体の承認ノードは本体の唯一の終わりだけで、ループの `until_bash` はその出力を読まない（止めた Archon の正式な形。
  ほかの置き場は読み込みの誤り、飛んだ関所の出力を読む `until_bash` は輪を落とす。持ち主の決め `dialogue-gate-in-loop`）。
- include されるグラフ（block と、メイングラフと周の鎖のほかの graph）は頭に `worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（一番上のグラフ〔メイングラフ・周の鎖〕は書いてよい）。
- 筋書きの stub は `workflow test` が照らす（答えの stub の無い承認ノードで止まると赤）。並べ（`fan_out:`）の形は人が見る。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
JUDGE = "workflows/judge/works-factory-judge.yaml"
PLAN = "workflows/plan/works-factory-plan.yaml"
LINE = "workflows/line/works-factory-line.yaml"
GATE = ("  - id: g\n    wait:\n      attention: m\n      form: select\n"
        "      options: [{id: approve}, {id: continue}, {id: stop}, {id: reject}]\n")


def in_loop(nodes: str) -> str:
    """節の並び（2 字下げ）を、輪 l の本体に入れた節の並びにする"""
    return "  - id: l\n    loop_group:\n      nodes:\n" + "".join(f"      {line}\n" for line in nodes.splitlines())


class GatesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E16", ROOT), [])

    def test_seed_caught(self):
        """種: 関所を持つ judge は通し、plan の頭の worktree を赤にする"""
        got = scan.problems("E16", SEEDS / "e16")
        self.assertEqual(len(got), 1, got)
        self.assertIn(PLAN, got[0])
        self.assertIn("worktree", got[0])

    def problems(self, files):
        with tree(files) as root:
            return scan.problems("E16", root)

    def test_gates_need_no_head_key(self):
        self.assertEqual(self.problems({LINE: "name: works-factory-line\nnodes:\n" + GATE,
                                        JUDGE: "name: works-factory-judge\nnodes:\n" + GATE}), [])

    def test_interactive_is_red_on_every_workflow(self):
        """止めた Archon で interactive は効かず、読み込みの警告になる"""
        for rel, name in ((LINE, "line"), (JUDGE, "judge")):
            for value in ("true", "false"):
                with self.subTest(rel=rel, value=value):
                    got = self.problems({rel: f"name: works-factory-{name}\ninteractive: {value}\nnodes:\n" + GATE})
                    self.assertEqual(len(got), 1, got)
                    self.assertIn(f"{rel}:2", got[0])

    def test_block_head_keys_are_red(self):
        for key in scan.BLOCK_HEAD_KEYS:
            with self.subTest(key=key):
                got = self.problems({JUDGE: f"name: works-factory-judge\n{key}: x\nnodes: []\n"})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{JUDGE}:2", got[0])
                self.assertEqual(self.problems({LINE: f"name: works-factory-line\n{key}: x\nnodes: []\n"}), [])

    def test_workflow_without_gates_needs_nothing(self):
        self.assertEqual(self.problems({LINE: "name: works-factory-line\nnodes: []\n"}), [])

    def test_waits_without_attention_are_not_gates(self):
        wait = "  - id: w\n    wait: {event: ci, deadline_ms: 1728000000}\n"
        self.assertEqual(self.problems({LINE: "name: works-factory-line\nnodes:\n" + in_loop(wait)}), [])

    def test_gate_without_an_answer_word_is_red(self):
        """options に答えの語が 1 つでも無い関所は赤（Archon は options に無い答えを拒み、run は関所で止まったまま）"""
        for word in ("approve", "continue", "stop", "reject"):
            with self.subTest(word=word):
                gate = GATE.replace(f"{{id: {word}}}, ", "").replace(f", {{id: {word}}}", "")
                self.assertNotIn(word, gate)
                got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + gate})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"{word} が無い", got[0])

    def test_gate_not_in_select_form_is_red(self):
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + GATE.replace("form: select", "form: multi_select")})
        self.assertEqual(len(got), 1, got)
        self.assertIn("select でない", got[0])

    def test_approval_gate_is_red(self):
        gate = ("  - id: g\n    approval:\n      message: m\n"
                "      decisions: [{id: approve}, {id: continue}, {id: stop}, {id: reject}]\n    idle_timeout: 1728000000\n")
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + gate})
        self.assertEqual(len(got), 1, got)
        self.assertIn("approval:", got[0])

    def test_gate_as_the_sole_end_of_a_loop_body_is_green(self):
        """止めた Archon の正式な形: 本体の唯一の終わりの関所（答えは次の周の頭が $LOOP_PREV で読む）"""
        head = "  - id: head\n    bash: 'true'\n"
        gate = GATE.replace("    wait:", "    depends_on: [head]\n    when: \"$head.output == 'x'\"\n    wait:", 1)
        self.assertEqual(self.problems({LINE: "name: works-factory-line\nnodes:\n" + in_loop(head + gate)}), [])

    def test_gate_inside_a_loop_body_is_red(self):
        """関所の後ろに節が在る・関所のほかにも終わりの節が在る本体は赤"""
        after = "  - id: after\n    bash: 'true'\n    depends_on: [g]\n"
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + in_loop(GATE + after)})
        self.assertEqual(len(got), 1, got)
        self.assertIn("輪の本体の関所 g が本体の唯一の終わりでない", got[0])
        beside = "  - id: beside\n    bash: 'true'\n"
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + in_loop(beside + GATE)})
        self.assertEqual(len(got), 1, got)
        self.assertIn("依られない節: beside, g", got[0])

    def test_until_bash_reading_the_body_gate_is_red(self):
        """when: で飛んだ関所は出力を持たないので、until_bash が読むと輪が落ちる（止めた Archon の説明書 loop-nodes.md）"""
        loop = in_loop(GATE).replace("      nodes:\n", "      until_bash: 'd=$g.output.decision; [ \"$d\" = approve ]'\n      nodes:\n", 1)
        got = self.problems({LINE: "name: works-factory-line\nnodes:\n" + loop})
        self.assertEqual(len(got), 1, got)
        self.assertIn("until_bash が本体の関所 g の出力を読む", got[0])

    def test_gate_seeds_are_one_violation_each(self):
        """違反の見本（tests/layers/seeds/k10・k18）は 1 本 1 違反"""
        for seed, words in (("k10-no-reject", "reject が無い"), ("k10-approval", "approval:"), ("k18-gate-in-loop", "輪の本体")):
            with self.subTest(seed=seed):
                got = scan.problems("E16", SEEDS / seed)
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])


if __name__ == "__main__":
    unittest.main()
