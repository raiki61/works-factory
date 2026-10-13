"""全部のブロックの YAML（workflows/<ブロック>/works-factory-<ブロック>.yaml）の節の印の照らし。

- coldwrite を節の plugins: に名指さない。coldwrite は隔離した設定の settings.json の hooks で全部の役に効かせる
  （bin/_lib/toolset.py）。節に名指すと、入れていない普通の利用者（E14）の run でその節が落ちる
- 作業ツリーの姿を比べる受け付けの節の with: の status_guarded が真 ⇔ 受ける役の節（depends_on のただ 1 つの prompt・command の
  節）が mutates_checkout: false。真の節の script は INPUTS_STATUS_GUARDED を読む。同じ script を回すほかの節は偽を書く
  （Archon の validate は、script が読む INPUTS_* を全部の節が結ぶことを求める。だからブロックの中で印を持つ節の script が、
  そのブロックの作業ツリーを比べる受け付けの script の全部になる）
- 役の output_format は JSON Schema の決まった鍵だけで書く。Claude Code は役を起こす時に output_format を strict で照らし、
  知らない鍵（例: 訳の文を入れた note:）が 1 つでも在ると節が起動で落ちる（#282）。訳は YAML のコメントに書く
"""
import pathlib
import unittest

import yaml

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / "workflows"
DOCS = {p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(WORKFLOWS.glob("*/works-factory-*.yaml"))}


# JSON Schema Draft 2020-12 の鍵の全部。出典: https://json-schema.org/draft/2020-12/json-schema-core（8 Core・
# 10 Applicator・11 Unevaluated）と https://json-schema.org/draft/2020-12/json-schema-validation（6 Validation・
# 7 Format・8 Content・9 Meta-Data）
SCHEMA_KEYWORDS = frozenset({
    "$schema", "$vocabulary", "$id", "$anchor", "$dynamicAnchor", "$ref", "$dynamicRef", "$defs", "$comment",
    "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "dependentSchemas",
    "prefixItems", "items", "contains", "properties", "patternProperties", "additionalProperties", "propertyNames",
    "unevaluatedItems", "unevaluatedProperties",
    "type", "enum", "const", "multipleOf", "maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum",
    "maxLength", "minLength", "pattern", "maxItems", "minItems", "uniqueItems", "maxContains", "minContains",
    "maxProperties", "minProperties", "required", "dependentRequired",
    "format", "contentEncoding", "contentMediaType", "contentSchema",
    "title", "description", "default", "deprecated", "readOnly", "writeOnly", "examples",
})
# 値が名前から schema への表の鍵・schema 1 つの鍵・schema の並びの鍵。ほかの鍵の値（enum・const・default など）は schema でない
NAMED_SCHEMAS = ("$defs", "properties", "patternProperties", "dependentSchemas")
ONE_SCHEMA = ("not", "if", "then", "else", "items", "contains", "additionalProperties", "propertyNames",
              "unevaluatedItems", "unevaluatedProperties", "contentSchema")
SCHEMA_LISTS = ("allOf", "anyOf", "oneOf", "prefixItems")


def unknown_keywords(schema, at: str) -> list:
    """schema の木を形に沿って降り、決まった鍵の外の鍵を `場所: 鍵` で返す。properties の子は名前で鍵でない"""
    if isinstance(schema, bool):
        return []
    if not isinstance(schema, dict):
        return [f"{at}: schema が object でも真偽でもない（{type(schema).__name__}）"]
    out = [f"{at}: {k}" for k in schema if k not in SCHEMA_KEYWORDS]
    for k in NAMED_SCHEMAS:
        for name, sub in (schema.get(k) or {}).items():
            out += unknown_keywords(sub, f"{at}.{k}.{name}")
    for k in ONE_SCHEMA:
        if k in schema:
            out += unknown_keywords(schema[k], f"{at}.{k}")
    for k in SCHEMA_LISTS:
        for i, sub in enumerate(schema.get(k) or []):
            out += unknown_keywords(sub, f"{at}.{k}[{i}]")
    return out


def output_formats(doc) -> dict:
    return {n["id"]: n["output_format"] for n in walk(doc["nodes"]) if "output_format" in n}


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk((n.get("loop_group") or {}).get("nodes") or [])


def guarded_nodes(doc) -> list:
    return [n for n in walk(doc["nodes"]) if "status_guarded" in (n.get("with") or {})]


def coldwrite_named(doc) -> list:
    return [n["id"] for n in walk(doc["nodes"]) if any("coldwrite" in str(p) for p in n.get("plugins") or [])]


def guarded_mismatches(doc, block: str) -> list:
    nodes = {n["id"]: n for n in walk(doc["nodes"])}
    tree_accepts = {n["script"] for n in guarded_nodes(doc)}
    out = []
    for n in nodes.values():
        if n.get("script") not in tree_accepts:
            continue
        flag = (n.get("with") or {}).get("status_guarded")
        roles = [nodes[d] for d in n.get("depends_on") or [] if d in nodes and ("prompt" in nodes[d] or "command" in nodes[d])]
        if not roles:
            if flag not in (None, False):
                out.append(f"{n['id']}: 役を受けない節の status_guarded が {flag!r}")
            continue
        if len(roles) != 1:
            out.append(f"{n['id']}: 受ける役が 1 つでない（{[r['id'] for r in roles]}）")
            continue
        want = roles[0].get("mutates_checkout") is False
        if (flag is True) != want or flag not in (None, True, False):
            out.append(f"{n['id']}: status_guarded {flag!r} だが役 {roles[0]['id']} の mutates_checkout は "
                       f"{roles[0].get('mutates_checkout')!r}")
        script = WORKFLOWS / block / "scripts" / f"{n['script']}.py"
        if flag is True and "INPUTS_STATUS_GUARDED" not in script.read_text(encoding="utf-8"):
            out.append(f"{n['id']}: script {script.name} が INPUTS_STATUS_GUARDED を読まない")
    return out


class NodeFlagsCase(unittest.TestCase):

    def test_no_node_names_coldwrite(self):
        for block, doc in DOCS.items():
            with self.subTest(block):
                self.assertEqual(coldwrite_named(doc), [])

    def test_guarded_accepts_flag_matches_role(self):
        for block, doc in DOCS.items():
            with self.subTest(block):
                self.assertEqual(guarded_mismatches(doc, block), [])

    def test_some_accepts_are_guarded(self):
        """印を持つ節が 1 つも無ければ上の照らしは空回りする"""
        self.assertTrue(any(n["with"]["status_guarded"] is True for doc in DOCS.values() for n in guarded_nodes(doc)))

    def test_output_formats_use_only_schema_keywords(self):
        for block, doc in DOCS.items():
            for node, schema in output_formats(doc).items():
                with self.subTest(block=block, node=node):
                    self.assertEqual(unknown_keywords(schema, node), [])

    def test_unknown_keyword_is_caught(self):
        """properties の子の名前は鍵として数えず、名前の下の schema の知らない鍵は数える"""
        schema = {"type": "object", "properties": {"note": {"type": "string", "note": "訳"}},
                  "items": {"anyOf": [{"type": "string", "x": 1}]}}
        self.assertEqual(unknown_keywords(schema, "n"), ["n.properties.note: note", "n.items.anyOf[0]: x"])

    def test_output_formats_are_found(self):
        """output_format を 1 つも拾えなければ上の照らしは空回りする"""
        self.assertIn("r1-minimality", output_formats(DOCS["eyes"]))


if __name__ == "__main__":
    unittest.main()
