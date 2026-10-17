"""層の地図 docs/layers.json に反する頼りが、地図の既知の漏れの表（known）とちょうど揃う（根の AGENTS.md の E22 の機械の行）。

照らしは 4 つ（tests/layers/scan.py の layer_hits）: Python の import の向き・ほかのブロックの隣のファイルの名・lib とブロックの中の
メイングラフのノードの id・指示書と入力の説明の中のほかのブロックと役の名。ファイルごとの行の数が表より増えても・減っても・表に無い
ファイルが出ても赤（直したら表から消す）。表そのものも、HEAD と origin/main の分かれ目の表より、照らしごとの行の数の和が増えず、
分かれ目の表に無いファイルも、分かれ目より多い行の数も出ない（考えの住処の柵の NotAboveMain と同じ歯止め）。分かれ目に地図が無ければ
比べない（柵を初めて入れる差分）。分かれ目を引けなければ見送らずに赤（CI は全履歴を取る）。
"""
import collections
import pathlib
import sys
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import conceptfence as cf  # noqa: E402

LINE = "name: works-factory-line\nnodes:\n  - id: gate-final\n    approval: {}\n"


def verdict(hits: dict, known: dict) -> list[str]:
    """照らしごとの当たりの行と表の食い違い（無ければ空）"""
    out = []
    for check in scan.LAYER_CHECKS:
        found = collections.Counter(line.split(":", 1)[0] for line in hits[check])
        rows = {path: n for path, (n, _why) in known.get(check, {}).items()}
        for path in sorted(set(found) | set(rows)):
            if found[path] != rows.get(path, 0):
                lines = [line for line in hits[check] if line.startswith(f"{path}:")]
                out.append(f"{check}: {path} は表 {rows.get(path, 0)} 行、木 {found[path]} 行 {lines}")
    return out


def growth(main: dict, now: dict) -> list[str]:
    """main の表より増えた所（照らしごとの行の数の和・main に無いファイル・ファイルごとの行の数）"""
    out = []
    for check in scan.LAYER_CHECKS:
        before = {path: n for path, (n, _why) in main.get(check, {}).items()}
        after = {path: n for path, (n, _why) in now.get(check, {}).items()}
        if sum(after.values()) > sum(before.values()):
            out.append(f"{check}: 行の数の和が {sum(before.values())} から {sum(after.values())} に増えた")
        out += [f"{check}: {path} が {before.get(path, 0)} 行から {n} 行に増えた" for path, n in sorted(after.items())
                if n > before.get(path, 0)]
    return out


def hits(files: dict, check: str) -> list[str]:
    with tree(files) as root:
        return scan.layer_hits(root)[check]


class MapCase(unittest.TestCase):
    """地図の形"""

    def test_layers_and_contracts(self):
        ids = [layer["id"] for layer in scan.LAYER_MAP["layers"]]
        self.assertEqual(len(ids), len(set(ids)))
        for layer in scan.LAYER_MAP["layers"]:
            with self.subTest(layer=layer["id"]):
                self.assertLessEqual(set(layer["may_use"]), set(ids) - {layer["id"]})
                self.assertTrue(layer["what"].strip())
                for path in layer["paths"]:
                    self.assertTrue(path.endswith("/"), path)
                    self.assertTrue(list(ROOT.glob(path)), f"地図の置き場 {path} が木に無い")

    def test_top_folders_are_line_and_chain(self):
        self.assertEqual(set(scan.TOP_FOLDERS), {scan.LINE_FOLDER, scan.CHAIN_FOLDER})

    def test_every_real_file_has_one_layer(self):
        """bin・workflows・lib の下のファイルは、地図の outside の外ならどれかの層に入る（置き場の書き漏れで照らしの外に落ちない）"""
        heads = {path.split("/")[0] for layer in scan.LAYER_MAP["layers"] for path in layer["paths"]}
        for head in sorted(heads):
            for path in scan._files(ROOT, head):
                rel = path.relative_to(ROOT).as_posix()
                if not any(scan.place_match(p, rel) for p in scan.LAYER_MAP["outside"]):
                    self.assertIsNotNone(scan.layer_of(rel), rel)

    def test_layer_of(self):
        self.assertEqual(scan.layer_of("bin/_lib/x.py"), ("shell", "bin/"))
        self.assertEqual(scan.layer_of("workflows/line/scripts/x.py"), ("top", "workflows/line/"))
        self.assertEqual(scan.layer_of("workflows/.shared/boundary.py"), ("shared", "workflows/.shared/"))
        self.assertEqual(scan.layer_of("workflows/judge/scripts/x.py"), ("block", "workflows/judge/"))
        self.assertEqual(scan.layer_of("lib/x.py"), ("lib", "lib/"))
        self.assertIsNone(scan.layer_of("lib/tests/test_x.py"))
        self.assertIsNone(scan.layer_of("workflows/judge/fixtures/a.yaml"))

    def test_beside_owners_are_blocks(self):
        self.assertLessEqual(set(scan.LAYER_MAP["beside"]), set(scan.LAYERS["block"]["names"]))

    def test_known_rows_have_count_and_reason(self):
        self.assertEqual(set(scan.LAYER_MAP["known"]), set(scan.LAYER_CHECKS))
        for check, rows in scan.LAYER_MAP["known"].items():
            for path, (n, why) in rows.items():
                with self.subTest(check=check, path=path):
                    self.assertGreater(n, 0)
                    self.assertTrue(why.strip())


class KnownCase(unittest.TestCase):
    """本物の木: 地図に反する頼りは表の既知の漏れとちょうど揃う"""

    def test_real_tree_matches_known(self):
        self.assertEqual(verdict(scan.layer_hits(ROOT), scan.LAYER_MAP["known"]), [])

    def test_rule_lists_every_check(self):
        with tree({"lib/x.py": 'import boundary\nX = "premises.json"\n', "workflows/.shared/boundary.py": ""}) as root:
            got = scan.problems("E22", root)
        self.assertEqual(len(got), 2, got)

    def test_verdict_is_red_both_ways(self):
        found = {check: [] for check in scan.LAYER_CHECKS} | {"import": ["a.py:1: x", "a.py:2: y"]}
        self.assertEqual(verdict(found, {"import": {"a.py": [2, "訳"]}}), [])
        self.assertTrue(verdict(found, {"import": {"a.py": [3, "訳"]}}))
        self.assertTrue(verdict(found, {}))


class ImportCase(unittest.TestCase):
    """Python の import の向き"""

    def test_graph_importing_the_shell_is_red(self):
        for rel in ("workflows/line/scripts/a.py", "workflows/judge/scripts/a.py", "workflows/.shared/a.py", "lib/a.py"):
            with self.subTest(rel=rel):
                got = hits({rel: "def f():\n    from bin._lib import childsweep\n"}, "import")
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{rel}:2:") and "層 shell" in got[0], got)

    def test_block_importing_another_block_is_red(self):
        got = hits({"workflows/judge/scripts/a.py": "from workflows.plan.scripts import b\n"}, "import")
        self.assertEqual(len(got), 1, got)
        self.assertIn("workflows/plan/", got[0])

    def test_lib_importing_the_shared_parts_is_red(self):
        got = hits({"lib/a.py": "import os, boundary\n", "workflows/.shared/boundary.py": ""}, "import")
        self.assertEqual(len(got), 1, got)
        self.assertIn("層 shared", got[0])

    def test_downward_imports_are_clean(self):
        files = {"workflows/judge/scripts/a.py": "import boundary\nimport startrec\nimport os\n", "workflows/.shared/boundary.py": "",
                 "lib/startrec.py": "import json\n", "bin/_lib/x.py": "from lib import startrec\n"}
        self.assertEqual(hits(files, "import"), [])


class BesideCase(unittest.TestCase):
    """ほかのブロックの隣のファイルの名"""

    def test_other_block_naming_the_file_is_red(self):
        for rel in ("workflows/plan/scripts/a.py", "workflows/line/scripts/a.py", "lib/a.py"):
            with self.subTest(rel=rel):
                got = hits({rel: 'X = "premises.json"\n'}, "beside")
                self.assertEqual(len(got), 1, got)
                self.assertIn("ブロック judge の隣のファイル premises.json", got[0])

    def test_owner_and_other_names_are_clean(self):
        files = {"workflows/judge/scripts/a.py": 'X = "premises.json"\n',
                 "workflows/plan/scripts/a.py": 'X = "rejects-premises.json"\nY = "premises.jsonl"\n'}
        self.assertEqual(hits(files, "beside"), [])

    def test_path_into_another_place_still_counts(self):
        got = hits({"workflows/line/scripts/a.py": "# R/rejudge-exit.json を読む\n"}, "beside")
        self.assertEqual(len(got), 1, got)


class MainIdCase(unittest.TestCase):
    """lib とブロックの中のメイングラフのノードの id"""

    def test_lib_and_block_holding_a_main_id_are_red(self):
        for rel in ("lib/a.py", "workflows/report/scripts/a.py", "workflows/report/commands/a.md"):
            with self.subTest(rel=rel):
                got = hits({"workflows/line/works-factory-line.yaml": LINE, rel: 'FINAL = "gate-final"\n'}, "main-id")
                self.assertEqual(len(got), 1, got)
                self.assertIn("gate-final", got[0])

    def test_own_id_and_top_graph_are_clean(self):
        files = {"workflows/line/works-factory-line.yaml": LINE, "workflows/line/scripts/a.py": 'X = "gate-final"\n',
                 "workflows/eyes/works-factory-eyes.yaml": "name: works-factory-eyes\nnodes:\n  - id: gate-final\n    script: x\n",
                 "workflows/eyes/scripts/a.py": 'X = "gate-final"\n', "lib/a.py": 'X = "gate-finally"\n'}
        self.assertEqual(hits(files, "main-id"), [])


class RoleCase(unittest.TestCase):
    """指示書と入力の説明の中のほかのブロックと役の名"""

    EYES = "name: works-factory-eyes\nnodes:\n  - id: r2-compare\n    prompt: x\n  - id: r2-prep\n    script: x\n"

    def test_command_naming_another_role_or_block_is_red(self):
        for text, said in (("r2-compare の答えを読む\n", "r2-compare"), ("works-factory-eyes が読む\n", "works-factory-eyes"),
                           ("blk-fix の fix が直す\n", "blk-fix")):
            with self.subTest(said=said):
                got = hits({"workflows/eyes/works-factory-eyes.yaml": self.EYES, "workflows/judge/commands/a.md": text}, "role")
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith("workflows/judge/commands/a.md:1:") and said in got[0], got)

    def test_own_role_script_node_bare_name_and_old_path_are_clean(self):
        files = {"workflows/eyes/works-factory-eyes.yaml": self.EYES,
                 "workflows/eyes/commands/a.md": "r2-compare の役\n",
                 "workflows/judge/commands/a.md": "r2-prep と eyes の fix。元 works/blk-fix/lib/a.py\n"}
        self.assertEqual(hits(files, "role"), [])

    def test_input_description_naming_another_role_is_red(self):
        judge = "name: works-factory-judge\ninputs:\n  objection: {default: '', description: r2-compare の異議}\n"
        got = hits({"workflows/eyes/works-factory-eyes.yaml": self.EYES, "workflows/judge/works-factory-judge.yaml": judge}, "role")
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("workflows/judge/works-factory-judge.yaml:3:") and "入力 objection" in got[0], got)


class NotAboveMain(unittest.TestCase):
    """表そのものが増えない"""

    def test_known_not_above_main(self):
        fork = cf.fork_ref(ROOT)
        if fork is None:
            self.fail(f"HEAD と {cf.MAIN_REF} の分かれ目を引けない（浅い clone か ref が無い。手元では git fetch origin main。"
                      f"CI は fetch-depth: 0 で全履歴を取る）")
        main, why = cf.main_table(ROOT, fork, scan.LAYER_MAP_FILE)
        if main is None:
            self.fail(f"分かれ目 {fork} の層の地図を引けない: {why}")
        if "known" not in main:
            return
        self.assertEqual(growth(main["known"], scan.LAYER_MAP["known"]), [])

    def test_growth_is_red(self):
        main = {"import": {"a.py": [1, "訳"]}, "role": {"b.md": [2, "訳"]}}
        self.assertEqual(growth(main, {"role": {"b.md": [1, "訳"]}}), [])
        self.assertTrue(growth(main, {"import": {"a.py": [2, "訳"]}}))
        self.assertTrue(growth(main, {"import": {"c.py": [1, "訳"]}, "role": {"b.md": [1, "訳"]}}),
                        "和が増えなくても main に無いファイルは赤")


if __name__ == "__main__":
    unittest.main()
