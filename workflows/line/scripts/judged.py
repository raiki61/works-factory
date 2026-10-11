"""判定の単位と判定を後の段へ渡す返しの節 judged（埋め P2）。

再審（rejudge）が走ればその返りから、走らなければ判定（judge）の返りから返す。後の段は単位と判定をここから読む。
再審が開いた単位（new_open_units）と下げた単位（lowered）は、単位の id を比べて出し、collect から報告へ渡す
（今の works の rejudge.py の new_open_units・lowered）。

入力（with:）: judge_<欄>（judge の返り）・rejudge_<欄>（rejudge の返り。`{from, if_skipped: null}`）
"""
import os

import linekit

FIELDS = ("units", "judgment", "purpose", "world", "rejudge_verdict")


def ids(units) -> list:
    return [u.get("id") for u in units or [] if isinstance(u, dict)]


def judged(judge: dict, rejudge: dict | None) -> dict:
    took = rejudge if rejudge is not None else judge
    before, after = ids(judge.get("units")), ids(took.get("units"))
    return {**{key: took.get(key) for key in FIELDS}, "rejudged": rejudge is not None,
            "new_open_units": [u for u in after if u not in before], "lowered": [u for u in before if u not in after]}


def of_env(prefix: str) -> dict:
    return {key: linekit.value(os.environ.get(f"INPUTS_{prefix}_{key.upper()}")) for key in FIELDS}


def from_env() -> tuple:
    rejudge = of_env("REJUDGE")
    return of_env("JUDGE"), (None if rejudge["units"] is None else rejudge)


def fallback(reason: str) -> dict:
    return {**{key: None for key in FIELDS}, "rejudged": False, "new_open_units": [], "lowered": []}


if __name__ == "__main__":
    linekit.run(lambda: judged(*from_env()), fallback)
