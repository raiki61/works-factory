"""役の指示が名指す skill・agent と、node の skills:・plugins: の宣言の照らし（落とし穴 K4。docs/design/integration.md の 4.2-4）。

Archon は工程の node に、node が名指した skill とプラグインしか渡さない（止めた Archon の packages/providers/src/claude/provider.ts
の applyNodeConfig。`options.skills = nodeConfig.skills ?? []`）。指示が使えと書いた skill を node が名指さないと、役は黙ってそれを持たない。
- AI の node（`loop_group` の中も）の指示（pack の `<block>/prompts/<node-id>.md` と `<node-id>.system.md`。共通の断片
  `{shared:…}`（pack の `.shared/prompts/`）と `{part:…}`（`prompts/parts/`）を入れた後）の行に、借りる skill（BORROWED_SKILLS）・
  同梱の skill（BUILTIN_SKILLS）・`pr-review-toolkit` の名が在れば、node の `skills:`（skill の名）か `plugins:`（`pr-review-toolkit@…`）が名指す
- 許す表は持たない（持ち主の決め shape-checks-only）。説明だけの言及は md の言い方を替える。値で渡る skill（prep が `{skill}` に
  入れる物）は、その block の試験が「入れうる名が全部 node の skills: に在る」で照らす
- pack は tests/archon.py の WORKFLOWS（入れ替えの前も後も同じ口）
"""
import pathlib
import re
import tempfile
import unittest

from tests.archon import BORROWED_SKILLS, BUILTIN_SKILLS, WORKFLOWS
from tests.layers.test_block_shape import _expand, ai_nodes, folders, load

PLUGIN = "pr-review-toolkit"
NAMES = sorted(BORROWED_SKILLS | BUILTIN_SKILLS | {PLUGIN})
NAMED = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, NAMES)) + r")(?![\w-])")


def declares(node: dict, name: str) -> bool:
    if name == PLUGIN:
        return any(str(p).split("@")[0] == PLUGIN for p in node.get("plugins") or [])
    return name in (node.get("skills") or [])


def undeclared(pack: pathlib.Path) -> set[tuple[str, int, str]]:
    """役の指示が名指すのに node が宣言しない (md のパス, 断片を入れた後の行, 名)"""
    found = set()
    for folder in folders(pack):
        for node in ai_nodes(load(folder)):
            for name in (f"{node['id']}.md", f"{node['id']}.system.md"):
                path = folder / "prompts" / name
                if not path.is_file():
                    continue
                text = _expand(path.read_text(encoding="utf-8"), pack, folder)
                for number, line in enumerate(text.splitlines(), 1):
                    for hit in NAMED.finditer(line):
                        if not declares(node, hit.group(1)):
                            found.add((path.relative_to(pack).as_posix(), number, hit.group(1)))
    return found


class RoleSkillsCase(unittest.TestCase):
    def test_prompt_naming_a_skill_or_agent_declares_it(self):
        self.assertEqual(sorted(undeclared(WORKFLOWS)), [], "指示が名指す skill・agent を node が宣言しない")

    def test_an_undeclared_name_is_red(self):
        """node の md・共通の断片・部品の md・loop_group の中の役が名指して宣言しない名を拾い、宣言した名と語の一部は拾わない"""
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            pack = pathlib.Path(tmp)
            (pack / ".shared" / "prompts").mkdir(parents=True)
            (pack / ".shared" / "prompts" / "look.md").write_text("pr-review-toolkit:silent-failure-hunter を起こせ\n", encoding="utf-8")
            block = pack / "blk"
            (block / "prompts" / "parts").mkdir(parents=True)
            (block / "prompts" / "a.md").write_text("前置き\nreceiving-code-review を使え。code-reviewer.md は読むな\n", encoding="utf-8")
            (block / "prompts" / "a-ok.md").write_text("receiving-code-review を使え\n", encoding="utf-8")
            (block / "prompts" / "b.md").write_text("{shared:look}\n", encoding="utf-8")
            (block / "prompts" / "c.md").write_text("{shared:look}\n", encoding="utf-8")
            (block / "prompts" / "d.md").write_text("頭\n{part:tail}\n", encoding="utf-8")
            (block / "prompts" / "parts" / "tail.md").write_text("/simplify を呼べ\n", encoding="utf-8")
            (block / "works-factory-blk.yaml").write_text(yaml.safe_dump({"nodes": [
                {"id": "a", "prompt": "$p.output.prompt"},
                {"id": "a-ok", "prompt": "$p.output.prompt", "skills": ["receiving-code-review"]},
                {"id": "loop", "loop_group": {"nodes": [
                    {"id": "b", "prompt": "$p.output.prompt"},
                    {"id": "c", "prompt": "$p.output.prompt", "plugins": ["pr-review-toolkit@works-local"]},
                    {"id": "d", "prompt": "$p.output.prompt", "skills": ["code-review"]},
                ]}},
            ]}), encoding="utf-8")
            self.assertEqual(undeclared(pack), {
                ("blk/prompts/a.md", 2, "receiving-code-review"),
                ("blk/prompts/b.md", 1, PLUGIN),
                ("blk/prompts/d.md", 2, "simplify"),
            })


if __name__ == "__main__":
    unittest.main()
