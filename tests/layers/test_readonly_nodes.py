"""作業ツリーを変えない節が `mutates_checkout: false` を書き、役の節が役の決まりを守る（workflows/AGENTS.md の E7 の機械の行）。

全部のブロックと線の役の節（`prompt:`・`command:`。輪の中も）の印は道具から導く: `allowed_tools` に Bash・Edit・Write（scan.TREE_CHANGERS）
が無い役は書き、在る役は書かない（外れは表 scan.KEEP_CHECKOUT の役だけ）。script・bash の節は表 scan.CHANGE_CHECKOUT の節の外が書く。
`loop:` の節は作らない（Archon は loop: の節の mutates_checkout を無視する）。役の節は settingSources: [user]・閉じた sandbox・
表 scan.ROLE_TOOLS の中の allowed_tools を持つ（K18）。役の model は表 launchgroups.GROUPS の群の名で、役にも工程の根にも effort を書かない
（ノードの effort は群の別名の effort より先に採られ、run ごとの付け替えが効かなくなる）。Bash を持ち Edit・Write を持たない役は sandbox の denyWrite に
scan.NO_TREE_WRITE を書く（#293）。
"""
import os
import pathlib
import tempfile
import unittest

from bin._lib import isolate
from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
PLAN = "workflows/plan/works-factory-plan.yaml"
FIX = "workflows/fix/works-factory-fix.yaml"
LINE = "workflows/line/works-factory-line.yaml"
GROUP = "@wf-plan-review"
SETTINGS = f"model: '{GROUP}'\n" + "settingSources: [user]\nsandbox: {enabled: true, allowUnsandboxedCommands: false}\nidle_timeout: 1728000000\n"
NO_TREE_SETTINGS = SETTINGS.replace("false}", f"false, filesystem: {{denyWrite: ['{scan.NO_TREE_WRITE}']}}}}")


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
                 + "  - id: take\n    script: take\n    mutates_checkout: false\n")
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
                    got = self.problems({path: workflow(name, role("r", tools, mark, settings=NO_TREE_SETTINGS))})
                    self.assertEqual(len(got), int(red), got)

    def test_bash_reader_without_no_tree_write_is_red(self):
        """Bash を持つ読むだけの役は sandbox で作業ツリーへの書き込みを止める。'.' は cwd を塞がないので赤。書く役は見ない"""
        for tools, settings, red in (("[Read, Bash]", SETTINGS, 1), ("[Read, Bash]", NO_TREE_SETTINGS, 0),
                                     ("[Read, Bash]", NO_TREE_SETTINGS.replace(scan.NO_TREE_WRITE, "."), 2),
                                     ("[Read, Edit, Bash]", SETTINGS, 0)):
            with self.subTest(tools=tools, settings=settings):
                got = self.problems({PLAN: workflow("plan", role("r", tools, False, settings=settings))})
                self.assertEqual(len(got), red, got)
                self.assertTrue(all("denyWrite" in line for line in got), got)

    def test_no_tree_write_names_the_isolated_archon_home(self):
        """denyWrite の値 ~/../archon-home は、起動が隔離した HOME から解くと隔離した Archon の家そのものを指す"""
        with tempfile.TemporaryDirectory() as tmp:
            child = isolate.isolate({}, pathlib.Path(tmp))
        resolved = os.path.normpath(scan.NO_TREE_WRITE.replace("~", child["HOME"], 1))
        self.assertEqual(resolved, child["ARCHON_HOME"])

    def test_keep_checkout_roles_write_the_mark_with_a_changer_tool(self):
        """表 KEEP_CHECKOUT の役は変える道具を持っても書く（書かなければ赤）"""
        block, ident = "plan-review", "plan-review"
        self.assertIn((block, ident), scan.KEEP_CHECKOUT)
        path = f"workflows/{block}/works-factory-{block}.yaml"
        # 同じブロックの表の行（無ければ表の行が木に無い赤）。束ね役の組も単独の組と同じ表に在る
        rest = "".join(role(name, "[Read, Write]", True) for name in ("plan-review-fix", "plan-review-tree", "plan-review-tree-fix"))
        self.assertEqual(self.problems({path: workflow(block, role(ident, "[Read, Write]", True) + rest)}), [])
        got = self.problems({path: workflow(block, role(ident, "[Read, Write]", False) + rest)})
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

    def test_role_model_names_a_group_without_effort(self):
        nodes = role("r", "[Read]", True)
        loop = "  - id: g\n    loop_group:\n      nodes:\n" + role("again", "[Read]", True, indent=8)
        self.assertEqual(self.problems({FIX: workflow("fix", nodes + loop)}), [])
        for name, settings, words in (("a group not in the table", SETTINGS.replace(GROUP, "@wf-nope"), "model"),
                                      ("a literal model", SETTINGS.replace(f"'{GROUP}'", "opus"), "model"),
                                      ("no model", SETTINGS.replace(f"model: '{GROUP}'\n", ""), "model"),
                                      ("effort on the role", SETTINGS + "effort: high\n", "effort")):
            with self.subTest(name):
                for body in (role("r", "[Read]", True, settings=settings),
                             "  - id: g\n    loop_group:\n      nodes:\n" + role("r", "[Read]", True, indent=8, settings=settings)):
                    got = self.problems({FIX: workflow("fix", body)})
                    self.assertEqual(len(got), 1, got)
                    self.assertIn(words, got[0])
        for key in scan.ROOT_EFFORT_KEYS:
            with self.subTest(root=key):
                got = self.problems({FIX: workflow("fix", nodes).replace("nodes:\n", f"{key}: high\nnodes:\n", 1)})
                self.assertEqual(len(got), 1, got)
                self.assertIn(f"工程の根に {key}", got[0])
                self.assertIn(f"{FIX}:2:", got[0])

    def test_role_rule_seeds_are_one_violation_each(self):
        """違反の見本（tests/layers/seeds/k18-*）は 1 本 1 違反（元 works/tests/yaml_bad/ の形）"""
        for seed, words in (("k18-setting-sources", "settingSources"), ("k18-open-sandbox", "sandbox"),
                            ("k18-no-tools", "allowed_tools が無い"), ("k18-loop-node", "loop:"),
                            ("k3-changer-marked", "変える道具を持つ役")):
            with self.subTest(seed=seed):
                got = scan.problems("E7", SEEDS / seed)
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])

    def test_script_node_without_the_mark_is_red(self):
        """script・bash の節は表 CHANGE_CHECKOUT に無ければ書く"""
        for kind in ("script: take", "bash: echo"):
            with self.subTest(kind=kind):
                got = self.problems({PLAN: workflow("plan", f"  - id: take\n    {kind}\n")})
                self.assertEqual(len(got), 1, got)
                self.assertIn("take", got[0])

    def test_change_checkout_node_with_the_mark_is_red(self):
        self.assertIn(("line", "start"), scan.CHANGE_CHECKOUT)
        got = self.problems({LINE: workflow("line", "  - id: start\n    script: start\n    mutates_checkout: false\n")})
        self.assertEqual(len(got), 1, got)
        self.assertIn("CHANGE_CHECKOUT", got[0])

    def test_change_checkout_rows_name_code_nodes_of_the_tree(self):
        """表が名指した節は本物の工程の script・bash の節（表が古くなって黙って外さない）"""
        for block, ident in scan.CHANGE_CHECKOUT:
            with self.subTest(block=block, node=ident):
                _, document = scan._workflow_doc(ROOT / "workflows" / block)
                node = next((n for n in scan._nodes(document) if getattr(scan._top(n, "id"), "value", None) == ident), None)
                self.assertIsNotNone(node)
                self.assertTrue(any(scan._top(node, kind) is not None for kind in scan.CODE_KINDS))

if __name__ == "__main__":
    unittest.main()
