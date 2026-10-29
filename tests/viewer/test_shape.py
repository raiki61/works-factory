"""見る道具の作りの読み（viewer/src/shape.py）が、今の木の全部の graph を読み分けられる（docs/design/viewer.md の照らしの 1）。

読み分けられないノード（種類の鍵が 0 個か 2 個以上）・md の見つからない AI のノード・script の無い script のノード・当たり先の無い
include: と workflow:（工場の名の頭で始まる先が木に無い）が 0。工場の YAML の形を変える PR がこれを赤にするので、見る道具の直しが同じ PR に
入る。小さな木は、照らしが赤を出せることの見本。

記録のノードの道を図に当てる時（shape.locate）、include: の先の graph の中のノードには、外から入る道 via（通った include: の
ノード）が付く。今の木の line の最初の block の頭のノードで見る（Archon を起こさずに照らす。本物の run での照らしは test_real_run）。
"""
import json
import pathlib
import unittest

from tests.layers.trees import tree
from viewer.src import shape

ROOT = pathlib.Path(__file__).resolve().parents[2]
OURS = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
PREFIX = OURS["name_prefix"]


class ShapeTest(unittest.TestCase):
    def test_every_graph_of_the_tree_is_read(self):
        got = shape.read(ROOT / OURS["folder"], PREFIX, ROOT / "docs" / "design")
        self.assertEqual(got["problems"], [])
        folders = {p.parent.name for p in (ROOT / OURS["folder"]).glob(f"*/{PREFIX}*.yaml")}
        self.assertEqual(set(got["graphs"]), folders)

    def test_unreadable_shapes_are_problems(self):
        files = {f"a/{PREFIX}a.yaml": f"""name: {PREFIX}a
nodes:
  - id: two
    script: s
    bash: "true"
  - id: none
    depends_on: [two]
  - id: talk
    prompt: "$x.output.prompt"
  - id: gone
    include: {PREFIX}gone
  - id: run
    script: missing
  - id: pr
    workflow: archon-pr
""", "a/scripts/s.py": ""}
        with tree(files) as root:
            got = shape.read(root, PREFIX)
        self.assertEqual(len(got["problems"]), 5, got["problems"])
        for words in ("two: 読み分けられないノード（種類の鍵 bash・script）", "none: 読み分けられないノード（種類の鍵 無し）",
                      "talk: AI のノードの指示の md a/prompts/talk.md が無い", f"gone: include: の先 {PREFIX}gone が木に無い",
                      "run: script のノードの script a/scripts/missing.py が無い"):
            self.assertTrue(any(words in line for line in got["problems"]), (words, got["problems"]))

    def test_a_node_inside_an_included_graph_carries_the_way_in(self):
        graphs = shape.read(ROOT / OURS["folder"], PREFIX, ROOT / "docs" / "design")["graphs"]
        outer = next(item for item in graphs["line"]["items"] if item["kind"] == "block" and item.get("target"))
        inner = graphs[outer["target"]]["items"][0]["id"]
        self.assertEqual(shape.locate(graphs, "line", [outer["id"], inner]),
                         {"graph": outer["target"], "node": inner, "via": [{"graph": "line", "node": outer["id"]}]})


if __name__ == "__main__":
    unittest.main()
