"""初見の読み手の返答の読み（docs/design/cold-read.md の 1.5。lib/runreport.py の _cold_of・COLD_UNREADABLE・COLD_EMPTY・_cold_lines の写し）。

- read(reply) -> {verdict, stops, guessed, decidable}: 返答（JSON の字か dict）を読む。読めない・語の外の判定は verdict が ""
- stuck(c) -> 書き直す側へ渡す 1 件ずつの行の配列（pass で欄が空なら空。redesign-needed で欄が空なら COLD_EMPTY の 1 行）
"""
import json

VERDICTS = ("pass", "redesign-needed")   # YAML の cold の output_format の verdict の enum と同じ（試験が突き合わせる）
PASSED, REDESIGN = VERDICTS
LANG_OF_TEXT = "the language of the text"   # port lang が空の時の言語（共通の lang-default は依頼の言語を言うので使わない。10 節）
COLD_UNREADABLE = "初見の読み手の返答を読めない（判定の語が無い）"
COLD_EMPTY = "（止まった所・推測の欄が空）"


def _list(value) -> list:
    return value if isinstance(value, list) else []


def read(reply) -> dict:
    got = reply
    if isinstance(reply, str):
        try:
            got = json.loads(reply) if reply.strip() else None
        except ValueError:
            got = None
    got = got if isinstance(got, dict) else {}
    verdict = got.get("verdict") if got.get("verdict") in VERDICTS else ""
    return {"verdict": verdict, "stops": [str(s) for s in _list(got.get("stops"))],
            "guessed": [str(g) for g in _list(got.get("guessed"))], "decidable": got.get("decidable") is True}


def stuck(c: dict) -> list:
    if not c["verdict"]:
        return [COLD_UNREADABLE]
    rows = [f"止まった所: {s}" for s in c["stops"]] + [f"推測で埋めた所: {g}" for g in c["guessed"]]
    return rows or ([COLD_EMPTY] if c["verdict"] != PASSED else [])
