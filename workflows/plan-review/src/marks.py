"""返答の行から決め手の欄と壁打ちの欄を外す純粋な関数（docs/design/plan-review.md の 1.5）。

今の gatemarks.split・converge.split・converge.tree_split と同じ欄を外す。住処 lib/marks.py は README 9.1 で消えるので使わず、
素の dict の操作で行う。外す欄の名は lib の KEEP のモジュール（gatemarks・converge）の物を使う。

- MARK_KEYS: 決め手の欄（gatemarks.FIELDS）と狭めない案（gatemarks.NO_NARROW）
- split_marks(rows) -> (行の写し, 行と同じ並びの外した欄): 行ごとに MARK_KEYS を外す。dict でない行は写しのまま、外した欄は {}
- split_plan(reply) -> (返答の写し, 項目ごとの narrows の行の外した欄 [[{…}…]…]): 修正案の役の返答の plan[].narrows[] から外す
  （今の gatemarks.split("p2.fix_plan", …) の形）
- split_answers(reply) -> (返答の写し, block_answers の値か []): 修正案の役の返答の前の往復の穴への答え（今の converge.split("plan-revise", …)）
- split_review(reply) -> (返答の写し, resolved の値か [], {木の欄: 値か None}): 事前審査の返答の壁打ちの欄 resolved と木の欄
  （converge.TREE_KEYS: items・design_map・origins・synergy・stuck_recommend）を外す（今の converge.split("plan-review", …) と tree_split）
- split_faces(reply) -> (返答の写し, faces と同じ並びの外した欄): 事前審査の返答の faces[] から MARK_KEYS を外す
  （今の gatemarks.split("p2.plan_review", …)）
"""
from __future__ import annotations

import copy

import converge    # lib/。RESOLVED・ANSWERS・TREE_KEYS
import gatemarks   # lib/。FIELDS・NO_NARROW

MARK_KEYS = (*gatemarks.FIELDS, gatemarks.NO_NARROW)


def split_marks(rows) -> tuple[list, list]:
    out, got = [], []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict):
            out.append({k: copy.deepcopy(v) for k, v in row.items() if k not in MARK_KEYS})
            got.append({k: copy.deepcopy(row[k]) for k in MARK_KEYS if k in row})
        else:
            out.append(copy.deepcopy(row))
            got.append({})
    return out, got


def split_plan(reply) -> tuple:
    out = copy.deepcopy(reply)
    marks = []
    for item in (out.get("plan") if isinstance(out, dict) else None) or []:
        if isinstance(item, dict) and isinstance(item.get("narrows"), list):
            item["narrows"], got = split_marks(item["narrows"])
            marks.append(got)
        else:
            marks.append([])
    return out, marks


def split_answers(reply) -> tuple:
    out = copy.deepcopy(reply)
    got = out.pop(converge.ANSWERS, None) if isinstance(out, dict) else None
    return out, got if isinstance(got, list) else []


def split_review(reply) -> tuple:
    out = copy.deepcopy(reply)
    if not isinstance(out, dict):
        return out, [], {name: None for name in converge.TREE_KEYS}
    resolved = out.pop(converge.RESOLVED, None)
    tree = {name: out.pop(name, None) for name in converge.TREE_KEYS}
    return out, resolved if isinstance(resolved, list) else [], tree


def split_faces(reply) -> tuple:
    out = copy.deepcopy(reply)
    if not isinstance(out, dict) or not isinstance(out.get("faces"), list):
        return out, []
    out["faces"], got = split_marks(out["faces"])
    return out, got
