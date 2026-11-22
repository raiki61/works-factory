"""計画の項目の型（converge.PlanItem・ItemState）に作り手の出力を照らす助け（lib/tests/test_plan_item_shape.py と
tests/blocks/line/test_rounds.py が `from tests.bin.itemshape import ...` で読む。test_* でないので unittest の発見に拾われない）"""
import typing


def missing_required(td, row: dict) -> set:
    """型 td の必須の鍵のうち、作り手が作った row に無い物（空なら置いている）。型に無い鍵を置いていても不足にしない"""
    return set(td.__required_keys__) - set(row)


def undeclared(td, row: dict) -> set:
    """作り手が作った row の鍵のうち、型（必須と任意）に無い物"""
    return set(row) - set(td.__annotations__)


def dropped_row(plan: list, states: list) -> list:
    """渡した plan の行に row が在るのに、作った往復の行（同じ並び）に row が無い項目の id（空なら全部写している）"""
    return [p["id"] for p, s in zip(plan, states) if "row" in p and "row" not in s]


def schema_key_diffs(td, schema: dict, path: str = "") -> list:
    """型 td の鍵の組と schema の properties の鍵の組を比べ、食い違いの行を返す（空なら同じ）。型の欄が TypedDict なら、schema の同じ欄の
    入れ子の properties と再帰で比べる（`dict | None` のような TypedDict でない欄は鍵の組を持たないので、そこで止める）"""
    props = schema.get("properties", {})
    here = set(td.__annotations__)
    out = []
    if here - set(props):
        out.append(f"{path or '.'}: 型にだけ在る {sorted(here - set(props))}")
    if set(props) - here:
        out.append(f"{path or '.'}: schema にだけ在る {sorted(set(props) - here)}")
    for key, hint in typing.get_type_hints(td).items():
        if key in props and typing.is_typeddict(hint):
            out += schema_key_diffs(hint, props[key], f"{path}.{key}" if path else key)
    return out
