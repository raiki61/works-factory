"""方針の文だけを入れる入口の中身（docs/design/world.md の 9 節）。

- request(policy, problem) -> 依頼の行の配列: problem が空でなければ [{where: "依頼", text: problem}]、空なら [{where: "方針", text: policy}]
- means(policy) -> 解き方の配列: 方針の文の箇条（-・*・+・数字. で始まる行）ごとに 1 つ。箇条が無ければ全体を 1 つ
- result(world, review=None, faces=()) -> {ok, world, holes, report}: world と review（事前審査の block の形 text）の返りをまとめる。
  holes は事前審査が受けた返答の faces（review の holes の先）。ok は world と review の両方の ok。報告は事前審査の行（頭の 1 行と
  block の穴の行）・定石と違う行（依頼は X、定石は Y）・world の報告の順
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


REVIEW_NOT_RUN = "- 事前審査の段が走らなかった"
WORLD_NOT_RUN = "- 世界の解の段が走らなかった"


def _review_lines(review) -> list:
    if not isinstance(review, dict):
        return [REVIEW_NOT_RUN]
    return [str(x) for x in review.get("report") or []] if isinstance(review.get("report"), list) else []


def result(world: dict | None, review: dict | None = None, faces=()) -> dict:
    head = _review_lines(review)
    holes = [f for f in faces if isinstance(f, dict)]
    review_ok = isinstance(review, dict) and review.get("ok") is True
    if not isinstance(world, dict):
        return {"ok": False, "world": None, "holes": holes, "report": [*head, WORLD_NOT_RUN]}
    lines = _differs(world)
    body = world.get("report") if isinstance(world.get("report"), list) else []
    shown = {k: v for k, v in world.items() if k != "rows_file"}
    return {"ok": world.get("ok") is True and review_ok, "world": shown, "holes": holes,
            "report": [*head, *lines, *[str(x) for x in body]]}
