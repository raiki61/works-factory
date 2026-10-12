"""役の節の output_format が、前後の空白を除いた長さの下限を pattern で持つ事を見る試験の助け。

型の正本は役の節の output_format だけ（持ち主の決め io-in-output-format）で、照らすのは Archon と Claude Code の Ajv。Ajv は
minLength を素の長さで数えるので、空白だけ・空白で水増しした字も通る。lib の型検査（engine.schema）が前後の空白を除いて数えて
いた下限は、欄ごとの pattern が持つ:
- minLength 1 の欄: `\\S`
- minLength N（2 以上）の欄: `\\S[\\s\\S]{N-2,}\\S`（前後の空白を除いた長さが N 以上の時だけ当たる）
- 1 行の欄（元 `^[^\\n\\r\\x00]+$`）: LINE。生成の縛りの側が先読みを受けない恐れがあるので先読みを使わない
Ajv の pattern は RegExp の test（字のどこかに当たれば通る）なので、ここは re.search で当てる。
"""
import re

LINE = r"^[^\n\r\x00]*[^\s\x00][^\n\r\x00]*$"


def trimmed_pattern(n: int) -> str:
    return r"\S" if n <= 1 else r"\S[\s\S]{%d,}\S" % (n - 2)


def matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def _min_length_fields(schema, path: str = ""):
    if isinstance(schema, dict):
        types = schema.get("type")
        if "minLength" in schema and "string" in (types if isinstance(types, list) else [types]):
            yield path or "/", schema
        for k, v in schema.items():
            yield from _min_length_fields(v, f"{path}/{k}")
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            yield from _min_length_fields(v, f"{path}/{i}")


def missing_patterns(schema) -> list:
    """minLength を持つ字の欄のうち、空白を除いた下限の pattern を持たない欄の道と、持つ pattern"""
    return [(path, f.get("pattern")) for path, f in _min_length_fields(schema)
            if f.get("pattern") not in (trimmed_pattern(f["minLength"]), LINE)]


def without_trimmed(schema):
    """schema の写しから、minLength の下限を持つ trimmed_pattern の pattern だけを外した物（lib の持ち主の型と比べる時。持ち主は
    engine.schema で前後の空白を除いて数えるので pattern を持たない）"""
    if isinstance(schema, list):
        return [without_trimmed(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: without_trimmed(v) for k, v in schema.items()}
    if "minLength" in out and out.get("pattern") == trimmed_pattern(out["minLength"]):
        del out["pattern"]
    return out
