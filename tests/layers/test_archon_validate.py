"""`archon validate workflows` が自分の工程（works-factory-*）に誤りも警告も出さない（workflows/AGENTS.md の E1 の機械の行）。

木は tests/archon.py の使い捨ての木に workflows/ の全部（線と在るブロック）を pack の形で置いた物。
線が include: する工程が 1 つでも木に無い間は、線の `include target … not found` の誤りだけを数えず、
無い工程を名指して見送る（ほかの工程は照らし続ける）。同梱の skill の警告は数えない（tests/archon.py の counted）。
Archon の源か bun が無ければ見送る。
"""
import json
import pathlib
import re
import unittest

from tests import archon
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDS = pathlib.Path(__file__).resolve().parent / "seeds"
MISSING_INCLUDE = re.compile(r"include target '[^']+' not found")


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
    def test_own_workflows_have_no_errors_or_warnings(self):
        names = [folder.name for folder in scan._blocks(ROOT)]
        workflows = {f"{scan.OURS_PREFIX}{name}" for name in names}
        line = scan.OURS["line"]
        missing = sorted(set(scan.includes(ROOT, scan.LINE_YAML)) - workflows) if (ROOT / scan.LINE_YAML).is_file() else []
        with archon.tree(names) as tree:
            found = validate(tree)
        self.assertEqual(sorted(found), sorted(workflows))
        if missing:
            found[line] = [issue for issue in found[line] if not MISSING_INCLUDE.search(issue)]
        self.assertEqual({name: issues for name, issues in found.items() if issues}, {})
        if missing:
            self.skipTest(f"ブロックがまだ無い: {', '.join(name.removeprefix(scan.OURS_PREFIX) for name in missing)}")

    def test_named_script_and_shared_resolve_in_the_pack(self):
        """名前の script は pack の形の工程の時だけ工程のフォルダの scripts/ から探される（止めた Archon の
        packages/workflows/src/script-discovery.ts の discoverPackScripts）。見つからなければ validate が誤りにする"""
        with archon.tree(["hello"], SEEDS / "e1" / "workflows") as tree:
            self.assertEqual(validate(tree), {"works-factory-hello": []})

    def test_only_builtin_skill_warnings_go_uncounted(self):
        """名指した skill のうち、同梱の名の「ディスクに無い」の警告だけを数えない。一覧に無い名の警告と、
        別の置き場に入っていて節から届かない時の誤り（同梱の名でも）は数える"""
        with archon.tree(["skills"], SEEDS / "e1" / "workflows") as tree:
            elsewhere = tree / ".claude" / "skills" / "security-review" / "SKILL.md"
            elsewhere.parent.mkdir(parents=True)
            elsewhere.write_text("---\nname: security-review\ndescription: seed\n---\n", encoding="utf-8")
            found = validate(tree)
        self.assertEqual(found, {"works-factory-skills": [
            "error: Claude skill 'security-review' not found in an enabled .claude/skills/ directory, though it is installed elsewhere",
            "warning: Claude skill 'unlisted-skill' not found on disk — expected for built-in and plugin-qualified skills, "
            "which Claude resolves itself"]})


if __name__ == "__main__":
    unittest.main()
