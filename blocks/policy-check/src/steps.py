"""方針の文だけを入れる入口の中身（docs/design/world.md の 9 節）。

- request(policy, problem) -> 依頼の行の配列: problem が空でなければ [{where: "依頼", text: problem}]、空なら [{where: "方針", text: policy}]
- means(policy) -> 解き方の配列: 方針の文の箇条（-・*・+・数字. で始まる行）ごとに 1 つ。箇条が無ければ全体を 1 つ
- result(world) -> {ok, world, holes, report}: world の返りをまとめ、定石と違う行（依頼は X、定石は Y）を報告の先頭に並べる
"""
import re

import worldmark  # lib/

ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
REQUEST_FILE = "request.json"


def request(policy: str, problem: str) -> list:
    if problem.strip():
        return [{"where": "依頼", "text": problem.strip()}]
    return [{"where": "方針", "text": policy.strip()}]


def means(policy: str) -> list:
    items = [m.group(1) for line in policy.splitlines() if (m := ITEM.match(line))]
    return items or ([policy.strip()] if policy.strip() else [])


def _differs(world: dict) -> list:
    path = world.get("rows_file")
    if not path:
        return []
    try:
        rows = worldmark.rows(path)
    except ValueError as e:
        return [f"- 世界の解の行が読めない: {e}"]
    return [f"- 定石と違う（依頼の行 {r['finding']}）: {r['versus']['challenge'] or r['practice']}" for r in rows
            if r["versus"]["verdict"] == worldmark.DIFFERS]


def result(world: dict | None) -> dict:
    if not isinstance(world, dict):
        return {"ok": False, "world": None, "holes": [], "report": ["- 世界の解の段が走らなかった"]}
    lines = _differs(world)
    body = world.get("report") if isinstance(world.get("report"), list) else []
    shown = {k: v for k, v in world.items() if k != "rows_file"}
    return {"ok": world.get("ok") is True, "world": shown, "holes": [], "report": [*lines, *[str(x) for x in body]]}
