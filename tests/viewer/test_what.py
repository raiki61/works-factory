"""札の「何をする物か」の 1 行の選び（viewer/src/what.py。docs/design/viewer.md の 4.5 と照らしの 7）。

- 今の木: 1 行を選ぶ部品が読めない設計書の節（「役」の見出しの下に段落が無い）が 0。1 行が無いノードの数は照らさない（書き足しを試験で
  強いない。下書き docs/plans/2026-10-29-viewer-overview.md の 5.6.3）
- 小さな木: 種類ごとの出どころの順（設計シートの役 → node の並びの行 → YAML の description → 指示の md の You の段落の写し）・script の
  docstring と配線・include の呼ぶ先の 1 行と呼ぶ側での役・繰り返しの形・1 行が無い物は空・役の見出しの下が空なら problems。node の並びの
  行は「並び」の節の囲みのコードの外だけ（port の節の同じ id の行を拾わない）。役の下が箇条書きなら頭の印を落とした最初の項。共有の設計書の
  フォルダの節の役（judge-eyes.md の形）が、入口の build を通して graph の what に付く
"""
import json
import pathlib
import unittest
from unittest import mock

from tests.layers.trees import tree
from viewer import flowview
from viewer.src import ja, shape, what

ROOT = pathlib.Path(__file__).resolve().parents[2]
OURS = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
P = OURS["name_prefix"]

FILES = {
    "docs/design/a.md": """# a

## 1 block の全体

### 1.1 役

a の役の 1 文目（括弧の中の。は切らない）。2 文目はなぜ。

### 1.2 port

- `b`: `flag: port の行は呼ぶ側での役にしない`。
- `gate`: `flag: port の行は承認の 1 行にしない`。

### 1.3 node の並び

```markdown
- `stop`: 囲みのコードの中の行は拾わない。
```

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
    "docs/design/c.md": "# c\n\n### 1.1 役\n\n- one: 1 つ目の形の役。続き。\n  折り返し。\n- two: 2 つ目の形の役。\n",
    "docs/design/shared.md": "# d と e\n\n## 1 d（共有の 1 つ目）\n\n### 1.1 役\n\nd の役。\n\n## 2 e\n\n### 2.1 役\n\ne の役。\n",
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
    f"workflows/c/{P}c.yaml": f"name: {P}c\ndescription: c の YAML の説明。\nnodes:\n  - id: n\n    script: n\n",
    "workflows/c/scripts/n.py": "",
    **{f"workflows/{x}/{P}{x}.yaml": f"name: {P}{x}\ndescription: {x} の説明（docs/design/shared.md）。\nnodes:\n  - id: n\n    script: n\n"
       for x in "de"},
    "workflows/d/scripts/n.py": "", "workflows/e/scripts/n.py": "",
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
        self.assertEqual((graphs["c"]["what"]["line"], graphs["c"]["what"]["why"]), ("one: 1 つ目の形の役。", "続き。 折り返し。"))
        self.assertEqual(graphs["e"]["what"]["line"], "e の役。")
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

    def test_build_attaches_the_line_from_a_shared_design(self):
        with tree(FILES) as root, mock.patch.object(flowview, "ROOT", root), mock.patch.object(flowview, "TREE", root / "workflows"), \
                mock.patch.object(ja, "REPO", root / "none.json"):
            data, _ = flowview.build(None, "", {"HOME": str(root), "XDG_CACHE_HOME": str(root / "cache")}, root)
        graphs = data["shape"]["graphs"]
        self.assertEqual(graphs["d"]["what"], {"line": "d の役。", "why": "", "from": "設計書 docs/design/shared.md の「1.1 役」"})
        self.assertEqual(graphs["e"]["what"]["line"], "e の役。")
        self.assertIn("b.md: 「1.1 役」の見出しの下に段落が無い", " ".join(data["shape"]["problems"]))


if __name__ == "__main__":
    unittest.main()
