"""数える問いの欄（engine.util.COUNT_HOW_SCHEMA）と例の欄（querytest.EXAMPLES_SCHEMA）の、役の節の output_format に手で写した物が
持ち主と同じ形である事を見る（FAST。YAML だけ・プロセスなし）。

写しは Ajv が照らすので、持ち主の 1 行の欄（engine.schema が前後の空白を除いて minLength を数える `^[^\\n\\r\\x00]+$`）は、
同じ字を通す trimmed.LINE で書いてもよい。前後の空白を除いた下限の pattern（trimmed.trimmed_pattern）は外して比べる。
"""
import sys
import unittest

import yaml

from tests.archon import ROOT, WORKFLOWS
from tests.bin import trimmed

for _p in (ROOT / "lib", ROOT / "lib" / "graphloops"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))
import engine.util as engine_util  # noqa: E402
import querytest  # noqa: E402

OWNER_LINE = engine_util._TEXT["pattern"]
HOW_KEYS = set(engine_util.COUNT_HOW_SCHEMA["properties"])


def _owner_form(schema):
    """持ち主の形に戻した写し: note を外し、LINE を持ち主の 1 行の pattern に、trimmed_pattern を外す"""
    if isinstance(schema, list):
        return [_owner_form(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: _owner_form(v) for k, v in trimmed.without_trimmed(schema).items() if k != "note"}
    if out.get("pattern") == trimmed.LINE:
        out["pattern"] = OWNER_LINE
    return out


def _how_parents(schema, path=""):
    """properties に how（数える問いの欄の形）を持つ欄の (道, その欄の properties)"""
    if isinstance(schema, dict):
        how = (schema.get("properties") or {}).get("how")
        if isinstance(how, dict) and set(how.get("properties") or {}) == HOW_KEYS:
            yield path, schema["properties"]
        for k, v in schema.items():
            yield from _how_parents(v, f"{path}/{k}")
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            yield from _how_parents(v, f"{path}/{i}")


def _nodes(nodes):
    for n in nodes:
        yield n
        if "loop_group" in n:
            yield from _nodes(n["loop_group"]["nodes"])


def copies():
    """(ブロック/節/道, 写しを持つ欄の properties)。pack（tests/archon.py の WORKFLOWS）のブロックの YAML の全部の節の output_format から拾う"""
    for path in sorted(WORKFLOWS.glob("*/works-factory-*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for n in _nodes(doc.get("nodes") or []):
            for where, props in _how_parents(n.get("output_format") or {}):
                yield f"{path.parent.name}/{n['id']}{where}", props


class CountHowCopyCase(unittest.TestCase):
    def test_every_how_copy_is_the_owner(self):
        found = list(copies())   # 書き手の型の名は 2 つ（修正の block の node と、書き手の型の block weapon-<型> の node。返答の形の写し）
        self.assertEqual(sorted(name.split("/")[1] for name, _ in found), ["diagnose", "pin", "pin", "pin-ruled", "rejudge", "rejudge-fix", "remove", "remove", "remove-ruled", "ruler",
                          "static", "static", "static-ruled", "tdd-close", "tdd-close", "tidy", "tidy-ruled", "variant", "variant-ruled"])
        want = _owner_form(engine_util.COUNT_HOW_SCHEMA)
        for name, props in found:
            with self.subTest(name):
                self.assertEqual(_owner_form(props["how"]), want)

    def test_every_examples_copy_is_the_owner(self):
        """例を必須にする写し（裁定の replace_query の query。理由の欄を持たず、hits に下限 1 を足して締める）は、持ち主の例の欄
        （hits・misses）と比べる。足した下限は締めで緩めではないので、hits の minItems 1 だけを外して比べる"""
        for name, props in copies():
            examples = {k: props[k] for k in querytest.EXAMPLES_SCHEMA if k in props}
            if not examples:
                continue
            owner = querytest.EXAMPLES_SCHEMA
            if not any(k in props for k in querytest.REASON_FIELDS):
                owner = {k: owner[k] for k in querytest.EXAMPLE_FIELDS}
                hits = examples.get("hits") or {}
                if hits.get("minItems") == 1:
                    examples = {**examples, "hits": {k: v for k, v in hits.items() if k != "minItems"}}
            with self.subTest(name):
                self.assertEqual(_owner_form(examples), _owner_form(owner))

    def test_line_copy_passes_what_the_owner_passes(self):
        """写しの LINE は持ち主の 1 行の欄（前後の空白を除いた minLength 1 と OWNER_LINE）と同じ字を通す"""
        from engine.schema import validate_schema
        for text in ("a", " def foo", "x = 1  ", "", "  ", "a\nb", "a\rb", "a\x00", " \t "):
            with self.subTest(text=text):
                self.assertEqual(trimmed.matches(trimmed.LINE, text), validate_schema(text, engine_util._TEXT) == [])


if __name__ == "__main__":
    unittest.main()
