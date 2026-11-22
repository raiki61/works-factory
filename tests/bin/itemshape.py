"""計画の項目の型（converge.PlanItem・ItemState）に作り手の出力を照らす助け（lib/tests/test_plan_item_shape.py と
tests/blocks/line/test_rounds.py が `from tests.bin.itemshape import ...` で読む。test_* でないので unittest の発見に拾われない）"""


def missing_required(td, row: dict) -> set:
    """型 td の必須の鍵のうち、作り手が作った row に無い物（空なら置いている）。型に無い鍵を置いていても不足にしない"""
    return set(td.__required_keys__) - set(row)


def undeclared(td, row: dict) -> set:
    """作り手が作った row の鍵のうち、型（必須と任意）に無い物"""
    return set(row) - set(td.__annotations__)


def dropped_row(plan: list, states: list) -> list:
    """渡した plan の行に row が在るのに、作った往復の行（同じ並び）に row が無い項目の id（空なら全部写している）"""
    return [p["id"] for p, s in zip(plan, states) if "row" in p and "row" not in s]
