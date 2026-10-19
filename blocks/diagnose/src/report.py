"""診断の block の報告の行（docs/design/diagnose.md の 5.7）。人に見せる日本語の行。lib の読み口（outpurpose・querytest・gatemarks）が
書く字と、今の報告（lib/runreport.py）の字をそのまま使う。再審が直す単位にした単位の行（修正の事実が要る）と「再審されずに残った異議」
の行は、つなぐ graph が組む。"""
from __future__ import annotations

import json
import pathlib

import gatemarks   # lib/
import jsonfile    # lib/
import oneline     # lib/
import outpurpose  # lib/
import querytest   # lib/

from src import files


def head(mode: str, reason: str) -> str:
    return f"{'再審' if mode == files.REJUDGE else '判定'}: {reason}"


def unproven_lines(judgment) -> list:
    """例で証明できない判定の問いの行（件数と 1 件 1 行）"""
    units = [u for u in (judgment.get("units") if isinstance(judgment, dict) else None) or [] if isinstance(u, dict)]
    rows = querytest.unproven(units, gatemarks._fix_duty)
    return [f"{querytest.UNPROVEN_HEAD}: {len(rows)} 件", *[f"  - {r['key']}: {r['why']}" for r in rows]] if rows else []


def rejudge_changes(rows) -> list:
    """再審で単位が変わった行（単位の前後の差。異議に名指されていない物は「争点でない」と印を付ける）"""
    lines = []
    for row in rows if isinstance(rows, list) else []:
        for c in row.get("changed") or []:
            if not isinstance(c, dict):
                continue
            who = "異議に名指された単位" if c.get("named") else "争点でない単位"
            if c.get("kind") == "changed":
                lines.append(f"再審（{row.get('pass')}）で{who}が変わった: {c.get('key')} の {c.get('field')}: "
                             f"{json.dumps(c.get('before'), ensure_ascii=False)} → {json.dumps(c.get('after'), ensure_ascii=False)}")
            else:
                lines.append(f"再審（{row.get('pass')}）で{who}が{'足された' if c.get('kind') == 'added' else '消えた'}: {c.get('key')}")
    return lines


def rejudge_lines(place: pathlib.Path, judgment) -> list:
    """再審の出口の往復の数と答えの並びと異議の 1 行、block から下げた単位の行、単位の前後の差の行"""
    doc = jsonfile.read_or(place / files.REJUDGE_EXIT_FILE)
    if not isinstance(doc, dict):
        return []
    raw = doc.get("verdicts") if isinstance(doc.get("verdicts"), list) else []
    obj = oneline.one_line(doc.get("objection") or "")
    now = {u.get("key"): u for u in (judgment.get("units") if isinstance(judgment, dict) else None) or [] if isinstance(u, dict)}
    lowered = [(k, str(now.get(k, {}).get("label") or "（判定に無い）")) for k in doc.get("lowered") or []]
    verdicts = "・".join(v if isinstance(v, str) and v else "（判定の欄が無い）" for v in raw) or "（判定の往復が無い）"
    return [f"再審の結果（{len(raw)} 往復）: {verdicts}" + (f"（異議: {obj}）" if obj else ""),
            *[f"  - 再審が block から {label} に下げた（拒まずに見せる——人が確かめる）: {k}" for k, label in lowered],
            *rejudge_changes(jsonfile.read_or(place / files.REJUDGE_DIFF_FILE, []))]


def lines(place, mode: str, status: str, reason: str, judgment) -> list:
    """報告に載せる行。status が ok でなければ頭に理由の行"""
    place = pathlib.Path(place)
    out = [] if status == "ok" else [head(mode, reason)]
    if status != "ok":
        return out
    if mode == files.REJUDGE:
        return out + rejudge_lines(place, judgment)
    return out + outpurpose.report_lines(place) + unproven_lines(judgment)
