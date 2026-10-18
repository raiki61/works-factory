"""`archon validate workflows` が自分の工程（works-factory-*）に誤りも警告も出さない（workflows/AGENTS.md の E1 の機械の行）。

木は tests/archon.py の使い捨ての木に workflows/ の全部（線とブロック）を pack の形で置いた物。
同梱の skill の警告は数えない（tests/archon.py の counted）。
Archon の源か bun が無ければ見送る。
"""
import json
import pathlib
import re
import unittest

import yaml

from tests import archon
from tests.bin.gitkit import git
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
# loop_group の中で include すると validate が誤りか警告を出すブロック: 親の工程の名 -> (誤りと警告の行, 訳)
IN_LOOP_REFUSED = {
    f"{scan.OURS_PREFIX}probe-fix": (
        ["error: loop_group 'rounds' body: 'workflow' (sub-run) is not supported inside a loop_group body"],
        "fix は組の子の run を workflow: の節で起こす。Archon は loop_group の本体に workflow: の節を置けない（止めた Archon の "
        "packages/workflows/src/loader.ts の validateDagStructure）。Archon で不可の形で、線は fix を輪の外でだけ include するので、"
        "線の能力は落ちない（狭めでない）"),
    f"{scan.OURS_PREFIX}probe-judge": (
        ["error: loop_group 'rounds' body: wait node 'block__spec-gate' must be the body's sole terminal sink"],
        "judge の関所 spec-gate（wait: の attention）は本体の終わりでないので、Archon は輪の本体に置けない（止めた Archon の "
        "packages/workflows/src/loader.ts の loop_group の本体の照らし）。線は judge を輪の外でだけ include する。輪の中で include "
        "できる形（関所を本体の終わりに置く）にするかは区分 J。区分の issue で外す"),
}


def validate(tree: pathlib.Path) -> dict[str, list[str]]:
    """木の自分の工程の名 → 誤りと警告の行"""
    done = archon.archon(tree, "validate", "workflows", "--json", "--cwd", str(tree))
    try:
        results = json.loads(done.stdout)["results"]
    except (json.JSONDecodeError, KeyError) as error:
        raise AssertionError(f"validate の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
    found = {}
    for result in results:
        if result["workflowName"].startswith(scan.OURS_PREFIX):
            issues = [f"{issue['level']}: {issue['message']}" for issue in result["issues"] if archon.counted(issue)]
            found[result["workflowName"]] = issues or ([] if result["valid"] else ["valid が false"])
    return found


class ArchonValidateTest(unittest.TestCase):
    maxDiff = None

    def test_own_workflows_have_no_errors_or_warnings(self):
        names = [folder.name for folder in scan._blocks(ROOT)]
        workflows = {f"{scan.OURS_PREFIX}{name}" for name in names}
        with archon.tree(names) as tree:
            found = validate(tree)
        self.assertEqual(sorted(found), sorted(workflows))
        self.assertEqual({name: issues for name, issues in found.items() if issues}, {})

    def test_every_block_loads_when_included(self):
        """どのブロックも、線のように include された形で読み込める。ブロック 1 つを include するだけの親の工程を木に足し、必須の
        入力には仮の字を渡して validate する。ブロックを単独で照らすだけでは見えない、include の時だけの誤り（輪の中の節の with: の名を
        $INPUTS で読む指示書が「入力が無い」で止まる。止めた Archon の packages/workflows/src/include-expander.ts の applyInputsMacro・inlineInclude）を捕まえる"""
        self.assertEqual(self.probe_includes(lambda include: [include]), {})

    def test_every_block_loads_when_included_inside_a_loop_group(self):
        """線の plan-rounds のように、親の工程の loop_group の中で include した形でも読み込める。輪の中の節は輪の外の節と同じ
        走査で指示書の名を解く（止めた Archon の packages/workflows/src/include-expander.ts の applyInputsMacro）"""
        found = self.probe_includes(lambda include: [{
            "id": "rounds", "loop_group": {"max_iterations": 2, "until_bash": 'test -n "x"', "nodes": [include]}}])
        self.assertEqual(found, {name: issues for name, (issues, _) in IN_LOOP_REFUSED.items()})

    def probe_includes(self, wrap) -> dict[str, list[str]]:
        """ブロックごとに、include の節を wrap で包んだ親の工程を木に足して validate し、誤りか警告の在る親の工程を返す"""
        names = [folder.name for folder in scan._blocks(ROOT) if folder.name not in scan.TOP_FOLDERS]
        with archon.tree(names) as tree:
            placed = tree / ".archon" / "workflows" / archon.PACK["ours"]["pack"]
            for name in names:
                block = yaml.safe_load((placed / name / f"{scan.OURS_PREFIX}{name}.yaml").read_text(encoding="utf-8"))
                needed = {key: "x" for key, spec in (block.get("inputs") or {}).items()
                          if not (isinstance(spec, dict) and "default" in spec)}
                include = {"id": "block", "include": f"{scan.OURS_PREFIX}{name}", **({"with": needed} if needed else {})}
                probe = {"name": f"{scan.OURS_PREFIX}probe-{name}", "description": "include の確かめ",
                         "nodes": wrap(include)}
                folder = placed / f"probe-{name}"
                folder.mkdir()
                (folder / f"{scan.OURS_PREFIX}probe-{name}.yaml").write_text(yaml.safe_dump(probe, allow_unicode=True), encoding="utf-8")
            git(tree, "add", "-A")
            git(tree, "commit", "-q", "-m", "probes")
            found = validate(tree)
        probes = {f"{scan.OURS_PREFIX}probe-{name}" for name in names}
        self.assertEqual(sorted(probes - set(found)), [])
        return {name: issues for name, issues in found.items() if name in probes and issues}

    def test_named_script_and_shared_resolve_in_the_pack(self):
        """名前の script は pack の形の工程の時だけ工程のフォルダの scripts/ から探される（止めた Archon の
        packages/workflows/src/script-discovery.ts の discoverPackScripts）。見つからなければ validate が誤りにする"""
        with archon.tree(["hello"], SEEDS / "e1" / "workflows") as tree:
            self.assertEqual(validate(tree), {"works-factory-hello": []})

    def test_only_builtin_and_borrowed_skill_warnings_go_uncounted(self):
        """名指した skill のうち、同梱の名と借りる superpowers の名の「ディスクに無い」の警告だけを数えない。一覧に無い名の警告と、
        別の置き場に入っていて節から届かない時の誤り（同梱の名でも）は数える"""
        with archon.tree(["skills"], SEEDS / "e1" / "workflows") as tree:
            elsewhere = tree / ".claude" / "skills" / "security-review" / "SKILL.md"
            elsewhere.parent.mkdir(parents=True)
            elsewhere.write_text("---\nname: security-review\ndescription: seed\n---\n", encoding="utf-8")
            found = validate(tree)
        roots = re.compile(r"^(warning: Skill '[^']+' not found in ).+$")   # 探した置き場は場の HOME で変わる
        self.assertEqual({name: [roots.sub(r"\1<置き場>", line) for line in lines] for name, lines in found.items()},
                         {"works-factory-skills": [
            "error: Claude (Anthropic) skill 'security-review' not found in an enabled skill directory, though it is installed elsewhere",
            "warning: Skill 'unlisted-skill' not found in <置き場>"]})


if __name__ == "__main__":
    unittest.main()
