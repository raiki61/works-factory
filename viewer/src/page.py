"""出力の 1 枚の HTML の組み立て（雛形 viewer/page.tpl.html へのデータの埋め）。

ページは 1 枚で完結し、別のファイルからスクリプトを読まない（viewer/AGENTS.md の E25 の 3）ので、データをページの中に埋める。
図の並べは雛形の中のスクリプトが持ち、外の道具を取り寄せない（網に出ない）。

- render(data) -> ページの字
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TEMPLATE = HERE / "page.tpl.html"
DATA_MARK = "__DATA__"


def render(data: dict) -> str:
    return fill(TEMPLATE.read_text(encoding="utf-8"), {
        # JSON の字の < を全部 < にし、記録の字の </script> や <!-- が script の中身を閉じない・読み方を変えないようにする
        DATA_MARK: json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"),
    })


def fill(template: str, values: dict[str, str]) -> str:
    """雛形の印を 1 度ずつ埋める。埋めた字の中に印の字が在っても埋め直さない（データは雛形の字でない）"""
    pattern = re.compile("|".join(map(re.escape, values)))
    found = pattern.findall(template)
    if sorted(found) != sorted(values):
        raise ValueError(f"雛形の印が 1 つずつでない（{found}）")
    return pattern.sub(lambda hit: values[hit[0]], template)
