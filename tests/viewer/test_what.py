"""札の「何をする物か」の 1 行の選び（viewer/src/what.py。docs/design/viewer.md の 4.5 と照らしの 7）。

- 今の木: 1 行を選ぶ部品が読めない設計書の節（「役」の見出しの下に段落が無い）が 0。1 行が無いノードの数は照らさない（書き足しを試験で
  強いない。下書き docs/plans/2026-10-29-viewer-overview.md の 5.6.3）
- 小さな木: 種類ごとの出どころの順（設計シートの役 → node の並びの行 → YAML の description → 指示の md の You の段落の写し）・script の
  docstring と配線・include の呼ぶ先の 1 行と呼ぶ側での役・繰り返しの形・1 行が無い物は空・役の見出しの下が空なら problems
"""
import json
import pathlib
import unittest

from tests.layers.trees import tree
from viewer.src import shape, what

ROOT = pathlib.Path(__file__).resolve().parents[2]
OURS = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
P = OURS["name_prefix"]

FILES = {
    "docs/design/a.md": """# a

## 1 block の全体

### 1.1 役

a の役の 1 文目（括弧の中の。は切らない）。2 文目はなぜ。

### 1.3 node の並び

1. `listed`（AI。`x: y`）: 並びの行の説明。続き。
2. `gate`（`wait:`）: 人に聞く。
3. `b`（include）: ここでの役。
4. `first` → `second`: 鎖の形は 1 行にしない。

## 2 node の設計シート: sheet と sheet-2（役の名）

### 2.1 役

設計シートの役。

## 3 node の設計シート: listed

```markdown
### 3.1 役
```

### 3.2 port
""",
    "docs/design/b.md": "# b\n\n### 1.1 役\n\n",
    f"workflows/a/{P}a.yaml": f"""name: {P}a
description: a の YAML の説明。
nodes:
  - id: sheet
    prompt: p
    description: 使わない。
  - id: listed
    prompt: p
  - id: desc
    prompt: p
    description: YAML の説明の 1 文目。2 文目。
  - id: you
    prompt: p
  - id: none
    prompt: p
  - id: tool
    script: tool
  - id: wire
    script: wire
  - id: b
    include: {P}b
  - id: b-again
    include: {P}b
    with:
      mode: before
  - id: loop
    loop_group:
      max_iterations: 3
      nodes:
        - id: kid
          script: tool
  - id: gate
    wait: {{attention: x}}
  - id: stop
    cancel: x
""",
    "workflows/a/prompts/sheet.md": "x", "workflows/a/prompts/listed.md": "x", "workflows/a/prompts/desc.md": "x",
    "workflows/a/prompts/you.md": "# Head\n\nYou measure the claims. Then you return.\n",
    "workflows/a/prompts/none.md": "no paragraph starts with the word.",
    "workflows/a/scripts/tool.py": '"""道具の 1 文目。\n\n残り。\n"""\n',
    "workflows/a/scripts/wire.py": '"""受け皿 x: 受け直す。"""\n',
    f"workflows/b/{P}b.yaml": f"name: {P}b\ndescription: b の YAML の説明。\nnodes:\n  - id: n\n    script: n\n",
    "workflows/b/scripts/n.py": "",
}


class WhatTest(unittest.TestCase):
    def test_no_unreadable_section_in_the_tree(self):
        got = shape.read(ROOT / OURS["folder"], P, ROOT / "docs" / "design")
        self.assertEqual(what.attach(got, ROOT / "docs" / "design"), [])

    def test_sources_follow_the_order_of_each_kind(self):
        with tree(FILES) as root:
            got = shape.read(root / "workflows", P, root / "docs" / "design")
            problems = what.attach(got, root / "docs" / "design", lambda s: "主張を測る。返す。" if s.startswith("You ") else s)
        graphs = got["graphs"]
        a = {i["id"]: i["what"] for i in shape.walk(graphs["a"]["items"])}
        self.assertEqual(graphs["a"]["what"]["line"], "a の役の 1 文目（括弧の中の。は切らない）。")
        self.assertEqual(graphs["a"]["what"]["why"], "2 文目はなぜ。")
        self.assertEqual(graphs["b"]["what"]["line"], "b の YAML の説明。")
        self.assertEqual(a["sheet"]["line"], "設計シートの役。")
        self.assertEqual(a["listed"]["line"], "並びの行の説明。")
        self.assertEqual(a["desc"]["line"], "YAML の説明の 1 文目。")
        self.assertEqual(a["you"]["line"], "主張を測る。")
        self.assertIn("日本語の写し", a["you"]["from"])
        self.assertEqual(a["none"]["line"], "")
        self.assertEqual(a["tool"]["line"], "道具の 1 文目。")
        self.assertFalse(a["tool"].get("wire"))
        self.assertTrue(a["wire"].get("wire"))
        self.assertEqual((a["b"]["line"], a["b"]["role"]), ("b の YAML の説明。", "ここでの役。"))
        self.assertEqual(a["b-again"]["role"], "形 before")
        self.assertEqual(a["loop"]["line"], "下の 1 ノードを最大 3 周回す器。")
        self.assertEqual(a["gate"]["line"], "人に聞く。")
        self.assertEqual(a["stop"]["line"], "")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("b.md: 「1.1 役」の見出しの下に段落が無い", problems[0])


if __name__ == "__main__":
    unittest.main()
