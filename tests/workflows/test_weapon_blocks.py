"""書き手の型の block の写しの照らし（docs/design/fix.md の 24.6。名の表を持たない yes/no。docs/plans/2026-10-24-fix-weapons.md の 11.6 の D1 の
縛る試験の 2・11.10 の 2）。

書き手の型の block は「`script: writer_prep` の node を持つ workflow」で見分ける（型の名の表を持たない）。Archon は YAML の錨も `output_format` も
ファイルをまたいで共にできないので、書き手の AI の node の起こし方と返答の形は型の block の数だけの YAML に写る。写しを 1 つの照らしで縛る。

(i) 型の block どうし
- (a) どの block の AI の node の `output_format` も `.shared/schemas/writer-reply.schema.json` と等しい。D1 の間は、修正の block に残る variant の
  node（`variant`・`variant-ruled`）の `output_format` も等しく、起こし方（`model`・`settingSources`・`sandbox`・`idle_timeout`・`retry`・
  `Agent` を除いた `allowed_tools`）が型の block の AI の node と同じ（D2 で variant が block になれば (b) に入るので、この足しを消す）
- (b) YAML の全体が、型の名 `<w>` を置き字に替え、AI の node の `allowed_tools` から `Agent` を除くと、どの block も同じ（起こし方の鍵・
  `inputs:`・node の並び・`returns:` まで。照らす鍵の表を持たないので、後で鍵を足しても、全部が同じでなければ落ちる）。`prompts/<w>.md` も同じ形
  （`<w>` を置き字に替えた字が同じ）で照らす。
  外すのは YAML の頭の `description`（workflow の説明の文）だけ: 型ごとに役の文が違い（5 つとも違う字）、型の名を置き字にしても揃わない。
  node の `description` は型の名だけが違う決まった字なので照らしに入る
- (c) `Agent` を `allowed_tools` に持つ block の組と、表 `src/render.py` の `SPAWNS` が真の block の組が同じ
- (d) `scripts/writer_prep.py`・`writer_out.py` が、どの block でも 1 字も違わない

(ii) 修正の block の 2 つの鎖（fix-loop・fix-ruled-loop）の include の先が全部 `weapon-` の書き手の型の block で、`writers.SEQUENCE` の型ごとに鎖に
1 つずつ在る（表 `src/render.py` の `ORDER_WEAPON` が注文の型の語なので、それで型と block を結ぶ）。鎖に無い block・block の無い型を書けない。
D1 の間は variant だけ block でなく node のまま鎖に残るので、型の集まりから除く（D2 でこの除きを消す）。
"""
import json
import pathlib
import re
import unittest

import yaml

from tests.blocks import kit

PACK = kit.BLOCKS
SCHEMA = json.loads((kit.SHARED / "schemas" / "writer-reply.schema.json").read_text(encoding="utf-8"))
LAUNCH = ("model", "settingSources", "sandbox", "idle_timeout", "retry")   # 起こし方の鍵（allowed_tools は Agent を除いて比べる）
NOT_A_BLOCK_YET = {"variant"}   # D1 の間 修正の block に node のまま残る型（D2 で weapon-variant の block になり、この除きを消す）
HEAD = "works-factory-weapon-"


def load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk((n.get("loop_group") or {}).get("nodes"))


def writer_blocks() -> dict:
    """フォルダの名 → YAML（`script: writer_prep` の node を持つ workflow）"""
    out = {}
    for path in sorted(PACK.glob("*/works-factory-*.yaml")):
        doc = load(path)
        if any(n.get("script") == "writer_prep" for n in walk(doc.get("nodes"))):
            out[path.parent.name] = doc
    return out


def ai_nodes(doc: dict) -> list:
    return [n for n in walk(doc["nodes"]) if "prompt" in n and "script" not in n]


def weapon_of(block: str) -> str:
    """block の表 src/render.py の ORDER_WEAPON（注文の型の語）"""
    return kit.load(block, "render").ORDER_WEAPON


def spawns(block: str) -> bool:
    return kit.load(block, "render").SPAWNS


def without_agent(tools: list) -> list:
    return [t for t in tools if t != "Agent"]


def normal(block: str, doc: dict) -> str:
    """型の名 <w>（フォルダ weapon-<w> の末尾）を置き字 `{W}` に替え、AI の node の allowed_tools から Agent を除き、頭の description を除いた YAML の字"""
    name = block[len("weapon-"):]
    doc = json.loads(json.dumps({k: v for k, v in doc.items() if k != "description"}))
    for n in ai_nodes(doc):
        n["allowed_tools"] = without_agent(n["allowed_tools"])
    return re.sub(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", "{W}", json.dumps(doc, ensure_ascii=False, sort_keys=False))


def md_normal(block: str) -> str:
    name = block[len("weapon-"):]
    text = (PACK / block / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    return re.sub(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", "{W}", text)


class CopiesCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks = writer_blocks()

    def test_there_are_writer_blocks(self):
        """見分けが空を返して照らしが何も見なくならない"""
        self.assertGreaterEqual(len(self.blocks), 5)
        self.assertTrue(all(b.startswith("weapon-") for b in self.blocks), sorted(self.blocks))

    def test_a_the_reply_shape_of_every_writer_is_the_shape_file(self):
        for block, doc in self.blocks.items():
            [node] = ai_nodes(doc)
            with self.subTest(block=block):
                self.assertEqual(node["output_format"], SCHEMA)

    def test_a_the_variant_nodes_left_in_the_fix_block_are_written_like_the_blocks(self):
        """D1 の間は修正の block に残る variant の node の返答の形と起こし方も、型の block の AI の node と同じ（D2 で消す足し）"""
        fix = {n["id"]: n for n in walk(load(PACK / "fix" / "works-factory-fix.yaml")["nodes"])}
        [first, *rest] = [ai_nodes(doc)[0] for doc in self.blocks.values()]
        for node_id in ("variant", "variant-ruled"):
            node = fix[node_id]
            with self.subTest(node=node_id):
                self.assertEqual(node["output_format"], SCHEMA)
                for other in (first, *rest):
                    self.assertEqual({k: node[k] for k in LAUNCH}, {k: other[k] for k in LAUNCH})
                    self.assertEqual(without_agent(node["allowed_tools"]), without_agent(other["allowed_tools"]))

    def test_b_the_whole_yaml_and_the_instruction_md_are_one_text(self):
        texts = {block: normal(block, doc) for block, doc in self.blocks.items()}
        [(base, want), *rest] = texts.items()
        for block, got in rest:
            with self.subTest(block=block, against=base):
                self.assertEqual(got, want)
        mds = {block: md_normal(block) for block in self.blocks}
        [(base, want), *rest] = mds.items()
        for block, got in rest:
            with self.subTest(md=block, against=base):
                self.assertEqual(got, want)

    def test_c_agent_is_in_the_tools_of_the_blocks_whose_table_says_spawns(self):
        having = {b for b, doc in self.blocks.items() if "Agent" in ai_nodes(doc)[0]["allowed_tools"]}
        self.assertEqual(having, {b for b in self.blocks if spawns(b)})

    def test_d_the_two_scripts_are_the_same_text_in_every_block(self):
        for name in ("writer_prep.py", "writer_out.py"):
            texts = {b: (PACK / b / "scripts" / name).read_text(encoding="utf-8") for b in self.blocks}
            with self.subTest(script=name):
                self.assertEqual(len(set(texts.values())), 1, sorted(texts))


class ChainCase(unittest.TestCase):
    """(ii) 修正の block の 2 つの鎖の include の先が全部書き手の型の block で、型ごとに 1 つずつ（variant だけ D1 の間は node のまま除く）"""

    @classmethod
    def setUpClass(cls):
        cls.blocks = writer_blocks()
        cls.fix = {n["id"]: n for n in walk(load(PACK / "fix" / "works-factory-fix.yaml")["nodes"])}
        cls.writers = kit.load("fix", "writers")
        cls.by_weapon = {weapon_of(b): b for b in cls.blocks}

    def chain(self, loop: str) -> list:
        return [n for n in self.fix[loop]["loop_group"]["nodes"] if "include" in n]

    def test_every_include_of_a_chain_is_a_writer_block_and_every_type_has_one(self):
        self.assertEqual(len(self.by_weapon), len(self.blocks), "注文の型の語が書き手の型の block の間で重ならない")
        for pass_, loop in (("first", "fix-loop"), ("ruled", "fix-ruled-loop")):
            names = [n["include"] for n in self.chain(loop)]
            want = [HEAD + self.by_weapon[w][len("weapon-"):] for w in self.writers.SEQUENCE[pass_] if w not in NOT_A_BLOCK_YET]
            with self.subTest(pass_=pass_):
                self.assertTrue(all(name.startswith(HEAD) for name in names), names)
                self.assertTrue(all(name[len("works-factory-"):] in self.blocks for name in names), "pack に無い block を include している")
                self.assertEqual(names, want, "型の順に 1 つずつ（鎖に無い block・block の無い型を書けない）")
                self.assertEqual(len(set(names)), len(names))

    def test_no_writer_block_is_left_out_of_the_first_chain(self):
        """型の block のうち、注文の型の語が 1 回目の段の型の block は全部 1 回目の鎖に在る（ruled の段に無い型は ruled の鎖に無い）"""
        for pass_, loop in (("first", "fix-loop"), ("ruled", "fix-ruled-loop")):
            included = {n["include"][len("works-factory-"):] for n in self.chain(loop)}
            owed = {b for w, b in self.by_weapon.items() if w in self.writers.SEQUENCE[pass_]}
            with self.subTest(pass_=pass_):
                self.assertEqual(included, owed)


if __name__ == "__main__":
    unittest.main()
