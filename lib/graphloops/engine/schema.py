"""返答の型検査。**JSON Schema そのものではなく engine 固有の型検査**（語を借りているだけ）。

pip 依存を持たない配布方針（issue #6）で jsonschema を使わない。見る語は type / enum / const /
required / properties / patternProperties / additionalProperties / items / minItems / maxItems / minimum / maximum /
minLength / maxLength / pattern だけで、これ以外は無視する（展開されていない $ref だけは無視せず拒む）。本家と意味が違う点を明記する:
  - enum / const は値だけでなく真偽値かどうかも見る（True を [0, 1] に一致させない）
  - minLength は**前後の空白を除いた長さ**（空白だけの返答を「在る」と数えないため）
  - maxLength は**素の長さ**（空白も数える）——上限は「役が作れる大きさ」を縛るもので、
    前後の空白を削ってから測ると、空白で水増しした値が上限をすり抜ける
  - pattern と patternProperties の鍵は Python の re で当てる。本家（JSON Schema 2020-12 validation §6.3.3）の方言は ECMA-262 で、
    揃えてあるのは `$` だけ（入力の末尾にだけ一致する——end_anchored）。\\d・\\w が Unicode の数字・語の字に一致する、`.` が CR や
    U+2028 にも一致する、といった差は残る（graph の pattern はこの差に当たらない字のクラスで書く）
この schema は役に貼るプロンプトにも「返答の形」として載るので、意味の差はここに書いて 1 か所にする。
エラーの一覧を返す（空なら合格）。
"""
import functools
import re


@functools.lru_cache(maxsize=None)
def end_anchored(pat):
    """pattern の `$`（エスケープの後と文字クラスの中を除く）を `\\Z` に読み替えた、コンパイル済みの正規表現。
    Python の `$` は末尾の改行の手前でも一致するので、`^[^\\n]+$` が改行 1 つで終わる値を通し、その値が git grep の -e で
    空の検索語に割れて全行に一致した（実測 2026-09-24: run_count が 2910 を返し、改行が無ければ 0）。ECMA-262 の `$` は入力の末尾だけ。
    検査（validate_schema）と graph の検査（graphcheck）は、同じこの関数を通した物を使う"""
    # 文字クラスの状態は「クラスの最初の字の位置」で持つ（Python の re の文書: `]` がクラスの中の字になるのは先頭に
    # 置いたときだけ——`[` の直後か、否定の `[^` の直後）。直前の 1 字で見ていたとき、エスケープした `\\[` の直後の `]` を
    # 字と読んでクラスを閉じ損ね、後ろの `$` を読み替えずに素通しした（`[\\[]a$`）
    out, esc, first = [], False, None   # first: クラスの中なら、その最初の字の位置。外なら None
    for i, ch in enumerate(pat):
        out.append("\\Z" if first is None and not esc and ch == "$" else ch)
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif first is None:
            if ch == "[":
                first = i + 2 if pat[i + 1:i + 2] == "^" else i + 1
        elif ch == "]" and i != first:
            first = None
    return re.compile("".join(out))


def _same(a, b):
    """== に真偽値の型も足す（True == 1 を一致にしない）。"""
    return a == b and isinstance(a, bool) == isinstance(b, bool)


def validate_schema(value, schema, path="$"):
    if "$ref" in schema:
        # 展開されていない参照を「知らない語」として無視すると、その欄の型検査が丸ごと消えて何でも通る
        return [f"{path}: schema の $ref {schema['$ref']!r} が展開されていない（graph は load_graph を通して読め）"]
    errs = []
    types = schema.get("type")
    if types:
        if isinstance(types, str):
            types = [types]
        if not any(_is_type(value, t) for t in types):
            return [f"{path}: 型が {'/'.join(types)} でない（{type(value).__name__}）"]
    # 真偽値は int の部分型なので、素の `in` / `==` だと True が語彙 [0, 1] に一致する（実測）。型でも見る。
    if "enum" in schema and not any(_same(value, w) for w in schema["enum"]):
        errs.append(f"{path}: 値 {value!r} が語彙 {schema['enum']} に無い")
    if "const" in schema and not _same(value, schema["const"]):
        errs.append(f"{path}: 値 {value!r} が {schema['const']!r} でない")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: 必須の欄 '{k}' が無い")
        props = schema.get("properties", {})
        pats = schema.get("patternProperties", {})
        for k, v in value.items():
            # properties と patternProperties は両方当てる（JSON Schema 2020-12 と同じ）。どちらにも当たらない名前だけが
            # additionalProperties に回る
            hit = [s for pat, s in pats.items() if end_anchored(pat).search(k)]
            if k in props:
                errs += validate_schema(v, props[k], f"{path}.{k}")
            for s in hit:
                errs += validate_schema(v, s, f"{path}.{k}")
            if k not in props and not hit and schema.get("additionalProperties") is False:
                errs.append(f"{path}: 知らない欄 '{k}'")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errs.append(f"{path}: 要素が {schema['minItems']} 個未満")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path}: 要素が {schema['maxItems']} 個を超えている")
        if "items" in schema:
            for i, v in enumerate(value):
                errs += validate_schema(v, schema["items"], f"{path}[{i}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: {schema['minimum']} 未満")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: {schema['maximum']} 超")
    if isinstance(value, str):
        if "minLength" in schema and len(value.strip()) < schema["minLength"]:
            errs.append(f"{path}: 空か短すぎる")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errs.append(f"{path}: {schema['maxLength']} 字を超えている")
        if "pattern" in schema and not end_anchored(schema["pattern"]).search(value):
            errs.append(f"{path}: 形が合わない（{schema['pattern']}）")
    return errs


# engine が読む語の全部。これ以外（oneOf / not / format / uniqueItems、綴り違い）は validate_schema が黙って無視するので、
# graph に書いても効かない。graphcheck がこの集合で節の schema を走査して落とす（注記で守るのをやめ、仕組みで守る）。
# note / description は説明のための欄で、検査には使わないが書いてよい。
KNOWN_KEYWORDS = frozenset({"type", "enum", "const", "required", "properties", "patternProperties", "additionalProperties", "items",
                            "minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "pattern", "note", "description"})


# 節の鍵のうち engine（と graphcheck の実行の形の検査）が読む物と、人が読むための説明の鍵。ループ固有の鍵は rules が NODE_KEYS
# （rules が読む）と NODE_NOTE_KEYS（説明）で宣言する——engine はループ固有の語を持たない。この 4 つの和に無い節の鍵は、綴り違いか
# 誰も読まなくなった鍵で、書いても黙って効かないので graphcheck が落とす（KNOWN_KEYWORDS と同じ閉じた集合。JSON Schema の
# additionalProperties: false と同じ形）。ENGINE_NODE_KEYS の各鍵を engine か graphcheck が読んでいることは 試験が見る
ENGINE_NODE_KEYS = frozenset({
    "active_in", "agent_type", "applies_cond", "builtin", "cond", "delegate", "deps", "engine_run", "fan_out", "forbidden_inputs",
    "fresh_context", "instance_deps", "once", "optional", "outputs", "pointers", "post_check", "pre", "prompt_append", "prompt_file",
    "reads", "run_by", "runner_judgment_by_design", "same_context_as", "save_text_as", "schema", "skills", "text", "thickness_from",
    "thickness_reason_from", "verdict_is_copy", "writes"})
DOC_NODE_KEYS = frozenset({"note", "does", "source", "stage"})


def _is_type(v, t):
    return {
        "object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str),
        "boolean": isinstance(v, bool), "integer": isinstance(v, int) and not isinstance(v, bool),
        "number": isinstance(v, (int, float)) and not isinstance(v, bool), "null": v is None,
    }.get(t, False)
