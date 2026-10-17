"""役の指示書が名指す skill・agent と、節の skills:・plugins: の宣言の照らし（落とし穴 K4）。

Archon は工程の節に、節が名指した skill とプラグインしか渡さない（止めた Archon の packages/providers/src/claude/provider.ts
627-638 行。`options.skills = nodeConfig.skills ?? []`）。指示書が使えと書いた skill を節が名指さないと、役は黙ってそれを持たない。
- 役の節（`prompt:`・`command:`。`loop_group` の中も）の指示書（直に書いた `prompt:` か `workflows/<ブロック>/commands/<名>.md`）
  の行に、借りる skill（BORROWED_SKILLS）・同梱の skill（BUILTIN_SKILLS）・`pr-review-toolkit` の名が在れば、節の `skills:`
  （skill の名）か `plugins:`（`pr-review-toolkit@…`）が名指す
- 説明だけの言及は表 ALLOWED に行ごとに名指して許す。表の行が今の木に当たらなければ赤
"""
import pathlib
import re
import tempfile
import unittest

import yaml

from tests.archon import BORROWED_SKILLS, BUILTIN_SKILLS
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = "pr-review-toolkit"
NAMES = sorted(BORROWED_SKILLS | BUILTIN_SKILLS | {PLUGIN})
NAMED = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, NAMES)) + r")(?![\w-])")
OVERLAY = ("元の unattended.md（借りた superpowers を無人の役で読む時の読み替え）の写しで、K9 により元の字のまま（手直しは写しの台帳 lib/borrow/COPIED_FROM の物だけ）。"
           "借りる skill を読める役の一覧と読み替えを述べるだけで、local-review に借りる skill を使えとは言わない。"
           "写しを載せる所（借りる skill を名指す役の指示書の末尾）を直す。区分 J。区分の issue で外す")

# (指示書, 行, 名) -> 訳
ALLOWED = {
    ("workflows/eyes/commands/r1-comments.md", 4, PLUGIN):
        "役の定義の出どころ（pr-review-toolkit:comment-analyzer の文を字のまま写した）を見出しで述べるだけ。"
        "agent は起こさず、写した定義を役自身が読む",
    ("workflows/eyes/commands/r1-minimality.md", 50, "simplify"):
        "「simplify は制約付き」は単純にする直しの考え方を言う語で、skill の呼び出しではない",
    ("workflows/fix/commands/delta-review.md", 11, PLUGIN):
        "入力の材料 `lens` の出どころ（修正の後のレンズの節が起こした agent）の説明で、この役は agent を起こさない",
    ("workflows/judge/commands/material-local-review.md", 100, "systematic-debugging"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 116, "receiving-code-review"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 117, "test-driven-development"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 143, "requesting-code-review"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 167, "receiving-code-review"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 167, "systematic-debugging"): OVERLAY,
    ("workflows/judge/commands/material-local-review.md", 175, "systematic-debugging"): OVERLAY,
}


def role_nodes(nodes: list) -> list[dict]:
    """節の並び（loop_group の中も）から役の節（prompt:・command:）を集める。"""
    out = []
    for node in nodes or []:
        if any(k in node for k in scan.ROLE_KINDS):
            out.append(node)
        if isinstance(node.get("loop_group"), dict):
            out.extend(role_nodes(node["loop_group"].get("nodes")))
    return out


def declares(node: dict, name: str) -> bool:
    if name == PLUGIN:
        return any(str(p).split("@")[0] == PLUGIN for p in node.get("plugins") or [])
    return name in (node.get("skills") or [])


def undeclared(root: pathlib.Path) -> set[tuple[str, int, str]]:
    """役の指示書が名指すのに節が宣言しない (指示書, 行, 名)。直に書いた prompt: の指示書は `<YAML>#<節の id>`。"""
    found = set()
    for spec in sorted((root / "workflows").glob("*/*.yaml")):
        doc = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
        for node in role_nodes(doc.get("nodes")):
            if "command" in node:
                path = spec.parent / "commands" / f"{node['command']}.md"
                where, text = path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
            else:
                where, text = f"{spec.relative_to(root).as_posix()}#{node.get('id')}", str(node["prompt"])
            for number, line in enumerate(text.splitlines(), 1):
                for hit in NAMED.finditer(line):
                    if not declares(node, hit.group(1)):
                        found.add((where, number, hit.group(1)))
    return found


class RoleSkillsCase(unittest.TestCase):
    def test_prompt_naming_a_skill_or_agent_declares_it(self):
        found = undeclared(ROOT)
        self.assertEqual(sorted(found - ALLOWED.keys()), [], "指示書が名指す skill・agent を節が宣言しない")
        self.assertEqual(sorted(ALLOWED.keys() - found), [], "表の行が今の木に当たらない")

    def test_every_allowed_row_has_a_reason(self):
        for row, reason in ALLOWED.items():
            with self.subTest(row=row):
                self.assertTrue(reason.strip())

    def test_an_undeclared_name_is_red(self):
        """command の指示書・直に書いた prompt・loop_group の中の役が名指して宣言しない名を拾い、宣言した名と語の一部は拾わない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            block = root / "workflows" / "blk"
            (block / "commands").mkdir(parents=True)
            (block / "commands" / "a.md").write_text(
                "前置き\nsystematic-debugging を使え。code-reviewer.md は読むな\n", encoding="utf-8")
            (block / "blk.yaml").write_text(yaml.safe_dump({"nodes": [
                {"id": "a", "command": "a"},
                {"id": "a-ok", "command": "a", "skills": ["systematic-debugging"]},
                {"id": "loop", "loop_group": {"nodes": [
                    {"id": "b", "prompt": "pr-review-toolkit:silent-failure-hunter を起こせ"},
                    {"id": "c", "prompt": "pr-review-toolkit を起こせ", "plugins": ["pr-review-toolkit@works-local"]},
                    {"id": "d", "prompt": "/simplify を呼べ", "skills": ["code-review"]},
                ]}},
            ]}), encoding="utf-8")
            self.assertEqual(undeclared(root), {
                ("workflows/blk/commands/a.md", 2, "systematic-debugging"),
                ("workflows/blk/blk.yaml#b", 1, PLUGIN),
                ("workflows/blk/blk.yaml#d", 1, "simplify"),
            })


if __name__ == "__main__":
    unittest.main()
