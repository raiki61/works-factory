"""層の地図 docs/layers.json に反する頼りが、地図の既知の漏れの表（known）とちょうど揃う（根の AGENTS.md の E22 の機械の行）。

照らしは 5 つ（tests/layers/scan.py の layer_hits）: Python の import の向き・ほかのブロックの隣のファイルの名・lib とブロックの中の
メイングラフのノードの id・指示書と入力の説明の中のほかのブロックと役の名・メイングラフと周の鎖の字の中の、
ブロックの中のノードの id とその頭。ファイルごとの当たりの数が表より増えても・減っても・表に無いファイルが出ても赤（直したら表から消す）。表そのものも、HEAD と origin/main の分かれ目の表より、照らしごとの当たりの数の和が増えず、
分かれ目の表に無いファイルも、分かれ目より多い当たりの数も出ない。地図を緩めた所は、地図の loosened に新しい訳の行が無ければ赤
（考えの住処の柵の NotAboveMain と loosened と同じ歯止め）。分かれ目に地図が無ければ
比べない（柵を初めて入れる差分）。分かれ目を引けなければ見送らずに赤（CI は全履歴を取る）。
"""
import collections
import copy
import pathlib
import re
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
                out.append(f"{check}: {path} は表 {rows.get(path, 0)}、木 {found[path]} {lines}")
    return out


def growth(main: dict, now: dict) -> list[str]:
    """main の地図より増えた・緩めた所: known の照らしごとの当たりの数の和・main に無いファイル・ファイルごとの当たりの数と、
    loosened の緩めのうち地図の loosened に新しい訳の行が無い物"""
    out = []
    for check in scan.LAYER_CHECKS:
        before = {path: n for path, (n, _why) in main["known"].get(check, {}).items()}
        after = {path: n for path, (n, _why) in now["known"].get(check, {}).items()}
        if sum(after.values()) > sum(before.values()):
            out.append(f"{check}: 当たりの数の和が {sum(before.values())} から {sum(after.values())} に増えた")
        out += [f"{check}: {path} が {before.get(path, 0)} から {n} に増えた" for path, n in sorted(after.items())
                if n > before.get(path, 0)]
    return out + cf.unexplained(main, now, loosened(main, now))


def loosened(main: dict, now: dict) -> list[tuple[str, str]]:
    """main の地図より緩めた所の (鍵, 文): 層が足された・消えた・並びが変わった（最初に当たる層がそのファイルの層）、
    層の paths が変わった・may_use が増えた・independent が外れた・names が減った、outside が増えた、
    beside の名が減った・main に在った名に持ち主が増えた。known を減らさずに地図の側で違反を通す道を塞ぐ"""
    layers = {layer["id"]: layer for layer in now["layers"]}
    old_ids = [layer["id"] for layer in main["layers"]]
    out = [(f"layer-new:{lid}", f"層 {lid} が地図に足された") for lid in layers if lid not in old_ids]
    if [lid for lid in layers if lid in old_ids] != [lid for lid in old_ids if lid in layers]:
        out.append(("layer-order", "層の並びが変わった"))
    for old in main["layers"]:
        lid = old["id"]
        new = layers.get(lid)
        if new is None:
            out.append((f"layer:{lid}", f"層 {lid} が地図から消えた"))
            continue
        if new["paths"] != old["paths"]:
            out.append((f"paths:{lid}", f"層 {lid} の paths が {old['paths']} から {new['paths']} に変わった"))
        out += [(f"may_use:{lid}:{u}", f"層 {lid} の may_use に {u} が増えた") for u in new["may_use"] if u not in old["may_use"]]
        if old.get("independent") and not new.get("independent"):
            out.append((f"independent:{lid}", f"層 {lid} の independent が外れた"))
        out += [(f"names:{lid}:{n}", f"層 {lid} の names から {n} が減った") for n in old.get("names", [])
                if n not in new.get("names", [])]
    out += [(f"outside:{p}", f"outside に {p} が増えた") for p in now["outside"] if p not in main["outside"]]
    out += [(f"beside:{block}:{n}", f"beside の {block} から {n} が減った") for block, names in main["beside"].items()
            for n in names if n not in now["beside"].get(block, [])]
    old_names = {n for names in main["beside"].values() for n in names}
    out += [(f"beside-owner:{block}:{n}", f"beside の {n} に持ち主 {block} が増えた") for block, names in now["beside"].items()
            for n in names if n in old_names and n not in main["beside"].get(block, [])]
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

    def test_beside_names_match_the_design_promise(self):
        """地図の beside の名は docs/design.md の「サブグラフの出力の約束」から読める。judge の外の名の集まりは、まだ出力の欄に直して
        いないのでほかのサブグラフも名で開く隣のファイルの文の名（`*.json`・`*.jsonl`。欄の指す先 `<欄>`（`<ファイル>`）の形は除く）と
        等しい。judge の名は欄で返したので約束の文から外れ、「judge の出力」の置き場のファイルの欄の先に在る（地図に残すのは柵のため）"""
        lines = (ROOT / "docs/design.md").read_text(encoding="utf-8").splitlines()
        line = next(line for line in lines if "ほかのサブグラフとメイングラフもこの名で開く" in line)
        named = set(re.findall(r"`([^`\s]+\.jsonl?)`", line))
        pointed = set(re.findall(r"`[\w-]+`（`([^`\s]+\.jsonl?)`）", line))
        beside = scan.LAYER_MAP["beside"]
        self.assertEqual({n for block, names in beside.items() if block != "judge" for n in names}, named - pointed)
        start = lines.index("### judge の出力")
        section = lines[start + 1:next(i for i in range(start + 1, len(lines)) if lines[i].startswith("### "))]
        ports = {m[1] for line in section if (m := re.match(r"    - `\w+`: [^`]*?（`([^`\s]+\.jsonl?)`", line))}
        self.assertLessEqual(set(beside["judge"]), ports)

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
        """script・境・lib と、YAML に直に書いた script のどれから bin を読んでも赤"""
        for rel in ("workflows/line/scripts/a.py", "workflows/judge/scripts/a.py", "workflows/.shared/a.py", "lib/a.py",
                    "workflows/judge/works-factory-judge.yaml"):
            with self.subTest(rel=rel):
                got = hits({rel: "def f():\n    from bin._lib import childsweep\n"}, "import")
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{rel}:2:") and "層 shell" in got[0], got)
        yaml = "name: works-factory-judge\nnodes:\n  - id: a\n    script: |\n      import bin._lib.place\n"
        got = hits({"workflows/judge/works-factory-judge.yaml": yaml}, "import")
        self.assertEqual(len(got), 1, got)

    def test_block_importing_another_block_is_red(self):
        got = hits({"workflows/judge/scripts/a.py": "from workflows.plan.scripts import b\n"}, "import")
        self.assertEqual(len(got), 1, got)
        self.assertIn("workflows/plan/", got[0])

    def test_lib_importing_the_shared_parts_is_red(self):
        got = hits({"lib/a.py": "import os, boundary\n", "workflows/.shared/boundary.py": ""}, "import")
        self.assertEqual(len(got), 1, got)
        self.assertIn("層 shared", got[0])

    def test_downward_imports_are_clean(self):
        files = {"workflows/judge/scripts/a.py": "import boundary\nimport startrec\nimport os\nimport binascii\n",
                 "workflows/.shared/boundary.py": "",
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

    def test_name_beside_two_blocks_is_clean_in_both(self):
        files = {"workflows/plan/scripts/a.py": 'X = "replan-gave-up.json"\n',
                 "workflows/plan-review/scripts/a.py": 'X = "replan-gave-up.json"\n'}
        self.assertEqual(hits(files, "beside"), [])
        got = hits({"lib/a.py": 'X = "replan-gave-up.json"\n'}, "beside")
        self.assertEqual(len(got), 1, got)
        self.assertIn("ブロック plan・plan-review の隣のファイル replan-gave-up.json", got[0])

    def test_name_with_a_step_matches_any_step(self):
        for text in ('"tdd-<k>/state.json"', 'f"tdd-{k}/state.json"', "tdd-g1/state.json"):
            with self.subTest(text=text):
                got = hits({"lib/a.py": f"X = {text}\n"}, "beside")
                self.assertEqual(len(got), 1, got)
                self.assertIn("tdd-<k>/state.json", got[0])
        self.assertEqual(hits({"workflows/fix/scripts/a.py": 'X = "tdd-g1/state.json"\n', "lib/a.py": 'X = "state.json"\n'},
                              "beside"), [])

    def test_path_into_another_place_still_counts(self):
        got = hits({"workflows/line/scripts/a.py": "# R/rejudge-exit.json を読む\n"}, "beside")
        self.assertEqual(len(got), 1, got)

    def test_input_description_of_block_yaml_is_not_counted(self):
        """ブロックの YAML の inputs: の description: はポインタの先のファイルの名を書く決まりなので数えない（flow・`>-` の形も）。
        prompt や with: に書いた名は数える"""
        yaml = ("name: works-factory-plan\ninputs:\n"
                "  answer_ties:\n    default: \"null\"\n    description: ポインタ（answer-ties.json）。null は無い\n"
                "  premises: {default: \"null\", description: \"ポインタ（premises.json）\"}\n"
                "  materials:\n    description: >-\n      ポインタ\n      （materials.json）\n"
                "nodes:\n  - id: a\n    prompt: |\n      $ARTIFACTS_DIR/premises.json を読む\n")
        got = hits({"workflows/plan/works-factory-plan.yaml": yaml}, "beside")
        self.assertEqual([line.split(": ", 1)[0] for line in got], ["workflows/plan/works-factory-plan.yaml:14"], got)


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


def inner_hits(files: dict) -> list[str]:
    """inner-id の照らしの当たり。照らしが無ければ空（その時は当たり 1 つの断言が落ちる）"""
    with tree(files) as root:
        return scan.layer_hits(root).get("inner-id", [])


class InnerIdCase(unittest.TestCase):
    """メイングラフと周の鎖の字の中の、ブロックの中のノードの id とその頭"""

    LINE_JUDGE = LINE + "  - id: judge\n    include: works-factory-judge\n    with:\n"
    JUDGE = "name: works-factory-judge\nnodes:\n  - id: world-judge\n    script: x\n  - id: gate-final\n    script: x\n"
    BASE = {"workflows/line/works-factory-line.yaml": LINE_JUDGE + "      x: y\n", "workflows/judge/works-factory-judge.yaml": JUDGE}

    def test_top_naming_a_block_inner_id_is_red(self):
        line, script = "workflows/line/works-factory-line.yaml", "workflows/line/scripts/a.py"
        shots = (
            (line, self.LINE_JUDGE + '      x: "judge__world-judge"\n', "judge__world-judge"),
            (line, self.LINE_JUDGE + '      x: "judge__world-"\n', "judge__world-"),
            (line, self.LINE_JUDGE + '      x: "judge__loop.world-judge"\n', "judge__loop"),
            (line, self.LINE_JUDGE + "      x: y\n  # 中の節（world-judge- など）を名指す\n", "world-judge"),
            (script, 'X = "world-judge"\n', "world-judge"),
            (script, 'X = "world-judge-"\n', "world-judge"),
            ("workflows/chain/scripts/a.py", 'X = "judge__world-judge"\n', "judge__world-judge"),
        )
        for rel, text, said in shots:
            with self.subTest(rel=rel, text=text):
                got = inner_hits({**self.BASE, rel: text})
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith(f"{rel}:") and said in got[0], got)
        clean = {**self.BASE,
                 script: 'A = "judge__"\nB = "gate-final"\nC = "world-judge.json"\nD = "gate-final-x"\n',
                 "workflows/judge/scripts/a.py": 'X = "world-judge"\nY = "judge__world-judge"\n',
                 "lib/a.py": 'X = "world-judge"\n'}
        self.assertEqual(inner_hits(clean), [])
        self.assertIn("inner-id", scan.LAYER_CHECKS)


class RoleCase(unittest.TestCase):
    """指示書と入力の説明の中のほかのブロックと役の名"""

    EYES = "name: works-factory-eyes\nnodes:\n  - id: r2-compare\n    prompt: x\n  - id: r2-prep\n    script: x\n"

    def test_command_naming_another_role_or_block_is_red(self):
        for text, said in (("r2-compare の答えを読む\n", "r2-compare"), ("works-factory-eyes が読む\n", "works-factory-eyes"),
                           ("blk-fix の fix が直す\n", "blk-fix"), ("`blk-delta/commands/delta-review.md` を読む\n", "blk-delta"),
                           ("blk-fix.yaml の節\n", "blk-fix")):
            with self.subTest(said=said):
                got = hits({"workflows/eyes/works-factory-eyes.yaml": self.EYES, "workflows/judge/commands/a.md": text}, "role")
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith("workflows/judge/commands/a.md:1:") and said in got[0], got)

    def test_old_name_followed_by_path_is_red_in_overlay(self):
        got = hits({"workflows/eyes/works-factory-eyes.yaml": self.EYES, scan.OVERLAY_COPY: "`blk-delta/commands/x.md` の決まり\n"}, "role")
        self.assertEqual(len(got), 1, got)

    def test_own_role_script_node_bare_name_and_old_path_are_clean(self):
        files = {"workflows/eyes/works-factory-eyes.yaml": self.EYES,
                 "workflows/eyes/commands/a.md": "r2-compare の役\n",
                 "workflows/judge/commands/a.md": "r2-prep と eyes の fix。元 works/blk-fix/lib/a.py\n"}
        self.assertEqual(hits(files, "role"), [])

    FIX = ("name: works-factory-fix\nnodes:\n  - id: tdd\n    prompt: x\n  - id: refix\n    prompt: x\n  - id: refix2\n    prompt: x\n"
           "  - id: prep\n    script: x\n")
    OLD_SENTENCE = "借りたスキルを読める役（素材集めの局所レビューと、TDD の役・手直しの役（`tdd`・`refix`・`refix2`））\n"

    def test_quoted_role_without_hyphen_is_red(self):
        """`-` の無い役の id も backtick で囲めば名指しに数える（素の語の tdd・refix は普通の語と重なるので数えない）"""
        for rel in ("workflows/judge/commands/a.md", scan.OVERLAY_COPY):
            with self.subTest(rel=rel):
                got = hits({"workflows/fix/works-factory-fix.yaml": self.FIX, rel: self.OLD_SENTENCE}, "role")
                self.assertEqual([line.rsplit(" ", 2)[1] for line in got], ["`tdd`", "`refix`", "`refix2`"], got)
        clean = {"workflows/fix/works-factory-fix.yaml": self.FIX, "workflows/judge/commands/a.md": "tdd の役と refix の役\n",
                 "workflows/fix/commands/a.md": "`refix2` と `tdd`\n", scan.OVERLAY_COPY: "TDD の役・手直しの役\n"}
        self.assertEqual(hits(clean, "role"), [])

    def test_path_into_another_block_is_red(self):
        files = {"workflows/fix/works-factory-fix.yaml": self.FIX,
                 "workflows/judge/commands/a.md": "正本 `workflows/fix/commands/fix-rules/common.md` と同じ\n",
                 scan.OVERLAY_COPY: "[正本](../../workflows/fix/commands/fix-rules/common.md)\n",
                 "workflows/fix/commands/a.md": "`workflows/fix/commands/b.md` を読め\n"}
        got = hits(files, "role")
        self.assertEqual(sorted(line.split(":", 1)[0] for line in got), [scan.OVERLAY_COPY, "workflows/judge/commands/a.md"], got)

    def test_own_yaml_word_equal_to_another_role_is_clean(self):
        """自分の YAML の字の値（返答の enum の語）と同じ字は、ほかのブロックの役の id と同じでも自分の語"""
        judge = "name: works-factory-judge\nnodes:\n  - id: verdict\n    prompt: x\n    output_format: {enum: [refix]}\n"
        files = {"workflows/fix/works-factory-fix.yaml": self.FIX, "workflows/judge/works-factory-judge.yaml": judge,
                 "workflows/judge/commands/a.md": "`refix` を選ぶ\n"}
        self.assertEqual(hits(files, "role"), [])

    def test_command_naming_another_block_by_title_is_red(self):
        """#698: 指示書の中の、ほかのブロックの和名に「役」「の役」「の段」が続く形は赤"""
        for text, said in (("修正役が覆せない\n", "修正役"), ("修正の段で答える\n", "修正の段"), ("独立の目役が読む\n", "独立の目役"),
                           ("計画の役が `narrows` に書き戻す\n", "計画の役")):
            with self.subTest(said=said):
                got = hits({"workflows/judge/commands/a.md": text}, "role")
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith("workflows/judge/commands/a.md:1:") and said in got[0], got)

    def test_command_title_as_content_or_own_title_is_clean(self):
        """中身の語の主語（修正が・判定が）・役の種類（判定をする役）と、自分のブロックの和名（judge の 判定役）は数えない"""
        files = {"workflows/judge/commands/a.md": "この役は判定役。修正が露呈させた欠陥。報告があれば読む\n",
                 "workflows/fix/commands/a.md": "判定が正本で、判定の問いを数え直す\n",
                 "workflows/eyes/commands/a.md": "この役は判定をする役なので、書く先は reason\n"}
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
        self.assertEqual(growth(main, scan.LAYER_MAP), [])

    def test_growth_is_red(self):
        main = self.map({"import": {"a.py": [1, "訳"]}, "role": {"b.md": [2, "訳"]}})
        self.assertEqual(growth(main, self.map({"role": {"b.md": [1, "訳"]}})), [])
        self.assertTrue(growth(main, self.map({"import": {"a.py": [2, "訳"]}})))
        self.assertTrue(growth(main, self.map({"import": {"c.py": [1, "訳"]}, "role": {"b.md": [1, "訳"]}})),
                        "和が増えなくても main に無いファイルは赤")

    def test_loosening_the_map_is_red_without_a_new_reason(self):
        """地図を緩めて known を減らす道（outside に足して表の行を消す、など）も赤。地図の loosened に新しい訳が在れば通す"""
        main = self.map({})
        cases = {
            "outside:lib/answer.py": lambda m: m["outside"].append("lib/answer.py"),
            "may_use:lib:shell": lambda m: m["layers"][-1]["may_use"].append("shell"),
            "paths:lib": lambda m: m["layers"][-1]["paths"].append("bin/x/"),
            "independent:block": lambda m: m["layers"][0].pop("independent"),
            "names:block:plan": lambda m: m["layers"][0]["names"].remove("plan"),
            "layer:lib": lambda m: m["layers"].pop(),
            "beside:fix:tdd-unit.json": lambda m: m["beside"]["fix"].remove("tdd-unit.json"),
            "beside-owner:plan:tdd-unit.json": lambda m: m["beside"].update(plan=["tdd-unit.json"]),
            "beside-owner:report:tdd-unit.json": lambda m: m["beside"].update(report=["tdd-unit.json"]),
            "layer-new:any": lambda m: m["layers"].insert(0, {"id": "any", "paths": ["lib/"], "may_use": ["block", "lib"]}),
            "layer-order": lambda m: m["layers"].reverse(),
        }
        for key, loosen in cases.items():
            with self.subTest(key=key):
                now = copy.deepcopy(main)
                loosen(now)
                got = growth(main, now)
                self.assertEqual(len(got), 1, got)
                self.assertIn(key, got[0])
                now["loosened"] = {key: "訳"}
                self.assertEqual(growth(main, now), [])
                self.assertTrue(growth(main | {"loosened": {key: "訳"}}, now), "main に在る訳の行では通さない")
        tightened = copy.deepcopy(main)
        tightened["outside"].clear()
        tightened["layers"][0]["names"].append("new")
        tightened["beside"]["plan"] = ["new.json"]
        self.assertEqual(growth(main, tightened), [])

    @staticmethod
    def map(known: dict) -> dict:
        return {"layers": [{"id": "block", "paths": ["workflows/*/"], "may_use": ["lib"], "independent": True,
                            "names": ["plan", "fix"]},
                           {"id": "lib", "paths": ["lib/"], "may_use": []}],
                "outside": ["lib/tests/"], "beside": {"fix": ["tdd-unit.json"]}, "known": known}

if __name__ == "__main__":
    unittest.main()
