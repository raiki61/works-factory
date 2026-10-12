"""作業ツリーを変えない節が `mutates_checkout: false` を書き、役の節が役の決まりを守る（workflows/AGENTS.md の E7 の機械の行）。

全部のブロックと線の役の節（`prompt:`・`command:`。輪の中も）の印は道具から導く: `allowed_tools` に Bash・Edit・Write（scan.TREE_CHANGERS）
が無い役は書き、在る役は書かない（外れは表 scan.KEEP_CHECKOUT の役だけ）。script の節は表 scan.READONLY_NODES で名指した節が書く。
`loop:` の節は作らない（Archon は loop: の節の mutates_checkout を無視する）。役の節は settingSources: [user]・閉じた sandbox・
表 scan.ROLE_TOOLS の中の allowed_tools を持つ（K18）。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
PLAN = "workflows/plan/works-factory-plan.yaml"
FIX = "workflows/fix/works-factory-fix.yaml"
LINE = "workflows/line/works-factory-line.yaml"
SETTINGS = "settingSources: [user]\nsandbox: {enabled: true, allowUnsandboxedCommands: false}\nidle_timeout: 1728000000\n"


def role(ident: str, tools: str | None, mark: bool, indent: int = 2, settings: str = SETTINGS) -> str:
    """役の節 1 つ（道具 tools は YAML の並びの字。None なら allowed_tools を書かない）"""
    lines = [f"id: {ident}", "prompt: x", *settings.splitlines()]
    lines += [f"allowed_tools: {tools}"] if tools is not None else []
    lines += ["mutates_checkout: false"] if mark else []
    pad = " " * indent
    return f"{pad}- {lines[0]}\n" + "".join(f"{pad}  {line}\n" for line in lines[1:])


def workflow(name: str, nodes: str) -> str:
    return f"name: works-factory-{name}\nnodes:\n{nodes}"


class ReadonlyNodesTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E7", ROOT), [])

    def test_seed_caught(self):
        got = scan.problems("E7", SEEDS / "e7")
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"{PLAN}:3", got[0])

    def problems(self, files):
        with tree(files) as root:
            return scan.problems("E7", root)

    def test_role_nodes_with_the_mark_are_clean(self):
        nodes = (role("diagnose", "[Read, Grep]", True)
                 + "  - id: g\n    loop_group:\n      nodes:\n" + role("again", "[Read]", True, indent=8)
                 + "  - id: take\n    script: take\n    timeout: 1728000000\n")
        self.assertEqual(self.problems({PLAN: workflow("plan", nodes)}), [])

    def test_nested_role_node_without_the_mark_is_red(self):
        nodes = "  - id: g\n    loop_group:\n      nodes:\n" + role("again", "[Read]", False, indent=8)
        got = self.problems({PLAN: workflow("plan", nodes)})
        self.assertEqual(len(got), 1, got)
        self.assertIn("again", got[0])

    def test_role_node_mark_follows_its_tools(self):
        """どのブロックでも、変える道具の無い役は書き、在る役は書かない（元 test_yaml_rules の
        test_pack_read_only_ai_nodes_do_not_mutate_checkout・test_changer_node_with_mutates_checkout_false_is_red）"""
        for path, name in ((FIX, "fix"), (PLAN, "plan"), ("workflows/eyes/works-factory-eyes.yaml", "eyes")):
            for tools, mark, red in (("[Read, Grep]", False, True), ("[Read, Grep]", True, False), ("[]", True, False),
                                     ("[Read, Bash]", True, True), ("[Read, Edit]", True, True), ("[Read, Write]", True, True),
                                     ("[Read, Bash]", False, False)):
                with self.subTest(block=name, tools=tools, mark=mark):
                    got = self.problems({path: workflow(name, role("r", tools, mark))})
                    self.assertEqual(len(got), int(red), got)

    def test_keep_checkout_roles_write_the_mark_with_a_changer_tool(self):
        """表 KEEP_CHECKOUT の役は変える道具を持っても書く（書かなければ赤）"""
        block, ident = "plan-review", "plan-review"
        self.assertIn((block, ident), scan.KEEP_CHECKOUT)
        path = f"workflows/{block}/works-factory-{block}.yaml"
        self.assertEqual(self.problems({path: workflow(block, role(ident, "[Read, Write]", True))}), [])
        got = self.problems({path: workflow(block, role(ident, "[Read, Write]", False))})
        self.assertEqual(len(got), 1, got)

    def test_keep_checkout_row_missing_from_its_workflow_is_red(self):
        block, ident = "plan-review", "plan-review"
        got = self.problems({f"workflows/{block}/works-factory-{block}.yaml": workflow(block, role("other", "[Read]", True))})
        self.assertTrue(any(ident in line and "KEEP_CHECKOUT" in line for line in got), got)

    def test_mark_set_to_true_is_red(self):
        got = self.problems({"workflows/plan/works-factory-plan.yaml": workflow("plan", role("plan", "[Read]", False)
                                                                                + "    mutates_checkout: true\n")})
        self.assertEqual(len(got), 1, got)

    def test_read_only_role_as_loop_node_is_red(self):
        """loop: の節は Archon が mutates_checkout を無視するので、読むだけの役を loop: で書くと守りが黙って消える。loop_group で書く"""
        got = self.problems({PLAN: workflow("plan", "  - id: again\n    loop:\n      prompt: x\n    mutates_checkout: false\n")})
        self.assertEqual(len(got), 1, got)
        self.assertIn("loop:", got[0])

    def test_role_settings_are_red_when_missing(self):
        for settings, words in ((SETTINGS.replace("settingSources: [user]\n", ""), "settingSources"),
                                (SETTINGS.replace("settingSources: [user]", "settingSources: [project, user]"), "settingSources"),
                                (SETTINGS.replace("allowUnsandboxedCommands: false", "allowUnsandboxedCommands: true"), "sandbox"),
                                (SETTINGS.replace("sandbox: {enabled: true, allowUnsandboxedCommands: false}\n", ""), "sandbox")):
            with self.subTest(words=words, settings=settings):
                got = self.problems({FIX: workflow("fix", role("r", "[Read]", True, settings=settings))})
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])

    def test_role_without_or_outside_the_tool_table_is_red(self):
        got = self.problems({FIX: workflow("fix", role("r", None, False))})
        self.assertEqual(len(got), 1, got)
        self.assertIn("allowed_tools が無い", got[0])
        got = self.problems({FIX: workflow("fix", role("r", "[Read, mcp__x]", True))})
        self.assertEqual(len(got), 1, got)
        self.assertIn("ROLE_TOOLS の外", got[0])

    def test_role_rule_seeds_are_one_violation_each(self):
        """違反の見本（tests/layers/seeds/k18-*）は 1 本 1 違反（元 works/tests/yaml_bad/ の形）"""
        for seed, words in (("k18-setting-sources", "settingSources"), ("k18-open-sandbox", "sandbox"),
                            ("k18-no-tools", "allowed_tools が無い"), ("k18-loop-node", "loop:"),
                            ("k3-changer-marked", "変える道具を持つ役")):
            with self.subTest(seed=seed):
                got = scan.problems("E7", SEEDS / seed)
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])

    def test_named_line_node_without_the_mark_is_red(self):
        named = scan.READONLY_NODES["line"]
        nodes = "".join(f"  - id: {name}\n    script: x\n    mutates_checkout: false\n" for name in named[1:])
        got = self.problems({LINE: f"name: works-factory-line\nnodes:\n  - id: {named[0]}\n    script: x\n" + nodes})
        self.assertEqual(len(got), 1, got)
        self.assertIn(named[0], got[0])

    def test_named_node_missing_from_its_workflow_is_red(self):
        """表が名指した節が工程に無ければ赤（表が古くなって黙って照らさなくならない）"""
        got = self.problems({LINE: "name: works-factory-line\nnodes: []\n"})
        self.assertEqual(len(got), len(scan.READONLY_NODES["line"]), got)


if __name__ == "__main__":
    unittest.main()
