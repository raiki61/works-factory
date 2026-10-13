"""全部の役の返答の形（`output_format`）が、その役の指示書が `"欄":` の形で返せと書く欄を全部持つことの照らし。

形に無い欄は Archon の構造化の出力が拒むので、役は指示書が求める欄を返せない（依頼 290: TDD の役の `red_quotes`）。

- 指示書は、節の `prompt`・`command:` の `commands/<名>.md`・節の `prompt` が `$<x>.output.prompt_file` を読ませるだけの節は
  `READ_SOURCES` に並べた、その指示書を書く元（決まりの文書と lib の字）
- 欄の名は形のどの深さの `properties` の名でもよい（`patternProperties` の値・`items`・`anyOf` などの中も）
"""
import functools
import importlib
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
if str(LIB / "graphloops") not in sys.path:
    sys.path.append(str(LIB / "graphloops"))

from engine.schema import validate_schema  # noqa: E402
from tests.workflows.test_prompt_contracts import JSON_KEY, graph_nodes  # noqa: E402

FIX = "workflows/fix/works-factory-fix.yaml"
FR = "workflows/fix/commands/fix-rules/"
INDIRECT = re.compile(r"\.output\.prompt_file")
# 指示書を機械が書く節（`<YAML のパス>#<id>`）→ その指示書の元。`<模組>:<名>` は lib の字か、lib の dict の値の全部
_TDD = [FR + "common.md", FR + "brief.md", FR + "tdd.md", "tddloop:RETURN", "tddloop:RETURN_CONFLICT"]
_FIXER = [FR + "common.md", FR + "brief.md", FR + "direct.md"]
_REFIX = [FR + "common.md", FR + "refix.md"]
_CONSULT = ["consult:QUESTION", "consult:ASK_TEXT", "consult:ASK_GATE_TEXT"]
READ_SOURCES = {
    f"{FIX}#tdd": _TDD,
    f"{FIX}#tdd-new": _TDD,
    f"{FIX}#ruler": [FR + "ruler.md", FR + "principles.md"],
    f"{FIX}#fixer": _FIXER,
    f"{FIX}#fix-ruled": _FIXER,
    f"{FIX}#refix": _REFIX,
    f"{FIX}#refix2": _REFIX,
    f"{FIX}#consult-answer": _CONSULT,
    f"{FIX}#ruled-consult-answer": _CONSULT,
}
# 返答でない JSON の欄を書く指示書 → その欄
NOT_REPLY = {"workflows/judge/commands/purpose.md": {"findings", "pr", "issue"}}  # 依頼の入力の形を書いた欄で、返答の欄でない


def source_text(source) -> str:
    if ":" not in source:
        return (ROOT / source).read_text(encoding="utf-8")
    module, name = source.split(":")
    value = getattr(importlib.import_module(module), name)
    return "\n".join(value.values()) if isinstance(value, dict) else str(value)


def shape_names(shape) -> set:
    """形のどの深さの `properties` の名も（`patternProperties` の鍵は名でない）"""
    if isinstance(shape, list):
        return set().union(*map(shape_names, shape))
    if not isinstance(shape, dict):
        return set()
    names = set((shape.get("properties") or {}).keys())
    for key in ("properties", "patternProperties"):
        names |= shape_names(list((shape.get(key) or {}).values()))
    for key in ("items", "additionalProperties", "anyOf", "oneOf", "allOf"):
        names |= shape_names(shape.get(key))
    return names


def missing_keys(texts, shape, exempt=frozenset()) -> set:
    return {k for t in texts for k in JSON_KEY.findall(t)} - shape_names(shape) - set(exempt)


@functools.cache
def roles():
    """返答の形を持つ役の節 `<YAML のパス>#<id>` → (節, 指示書の元の並び)"""
    out = {}
    for rel, node in graph_nodes(ROOT):
        if "output_format" not in node or not ("prompt" in node or "command" in node):
            continue
        key = f"{rel}#{node['id']}"
        sources = list(READ_SOURCES.get(key, []))
        if "command" in node:
            sources.append(f"{pathlib.PurePosixPath(rel).parent}/commands/{node['command']}.md")
        out[key] = (node, sources)
    return out


def tdd_shapes():
    return {key: roles()[key][0]["output_format"] for key in (f"{FIX}#tdd", f"{FIX}#tdd-new")}


class ReplyFieldsTest(unittest.TestCase):
    def test_tdd_test_reply_with_red_quotes_fits_the_shape(self):
        reply = {"phase": "test", "unit_key": "u", "test_files": ["t.py"], "tests": ["t.py::T::test_a"],
                 "red_quotes": {"t.py::T::test_a": {"quote": "ZeroDivisionError: division by zero",
                                                    "why": "分母が 0 になるので期待どおりに落ちる"}}}
        no_why = {**reply, "red_quotes": {"t.py::T::test_a": {"quote": "ZeroDivisionError: division by zero"}}}
        for key, shape in tdd_shapes().items():
            with self.subTest(key):
                self.assertEqual(validate_schema(reply, shape), [])
                self.assertTrue(validate_schema(no_why, shape))

    def test_every_role_reply_shape_holds_the_keys_its_instructions_write(self):
        missing = {}
        for key, (node, sources) in roles().items():
            texts = [node.get("prompt", "")] + [source_text(s) for s in sources]
            exempt = set().union(*(NOT_REPLY.get(s, set()) for s in sources))
            got = missing_keys(texts, node["output_format"], exempt)
            if got:
                missing[key] = sorted(got)
        self.assertEqual(missing, {})

    def test_every_indirect_role_names_its_sources(self):
        indirect = {key for key, (node, _) in roles().items() if INDIRECT.search(node.get("prompt", ""))}
        self.assertEqual(indirect, set(READ_SOURCES))
        for sources in READ_SOURCES.values():
            for source in sources:
                with self.subTest(source):
                    self.assertTrue(source_text(source))

    def test_missing_key_is_red(self):
        self.assertEqual(missing_keys(['{"a": 1, "b": 2}'], {"properties": {"a": {}}}), {"b"})
        nested = {"properties": {"m": {"patternProperties": {"^.+$": {"properties": {"b": {}}}}}}}
        self.assertEqual(missing_keys(['{"m": {}, "b": 1, "c": 0}'], nested), {"c"})


if __name__ == "__main__":
    unittest.main()
