"""裁定の文のファイル conflict-rulings.md（修正役が Read する）を書く。

裁定ごとの約束（修正役への命令）の文は prompts/parts/ruling-promise.md が持ち、ここは単位・名指し・理由・範囲の行（材料）を
conflict の盤面から組んで繋ぐだけ。lib/conflict は裁定の行の読み書きだけを持つ（指示の文を持たない）。
"""
from __future__ import annotations

import json
import os
import pathlib

import prompt

import conflict  # lib/

KINDS = ("fix_test_scope", "fix_code_as", "ask_human", conflict.REPLACE, conflict.REJUDGE, conflict.REPLAN)   # 裁定の decision → 約束の段落
ROW_HEAD = "## {id}: {unit_key}"


def promise(row: dict, second_pass: bool) -> str:
    """裁定の行の約束。fix_plan_item の行のうち案を直した行（AMENDED）は直す義務に戻る・諦めた行（GAVE_UP）は最後の関所へ・2 回目の
    修正の段で案の直しを待つ行（WAITING。この段で新しく裁いた行）は修正の段を抜ける時に諦めた行になる。組どうしの合わせの申し出
    （JOIN_SOURCE）への直す裁定は合わせ役が直し、裁定の後の修正役は直さない"""
    decision, state = row["ruling"]["decision"], conflict.replan_state(row)
    pick = ("clash" if row.get("source") == conflict.JOIN_SOURCE and decision in conflict.FIX_DECISIONS
            else "late_replan" if second_pass and state == conflict.WAITING
            else state if state in (conflict.AMENDED, conflict.GAVE_UP) else decision)
    names = {"clash", "late_replan", conflict.AMENDED, conflict.GAVE_UP, *KINDS}
    return prompt.render_part("ruling-promise", {}, {name: name == pick for name in names}).strip()


def write(b) -> pathlib.Path:
    """裁定の文（1 件ずつ単位・名指し・理由・裁定・範囲と、裁定ごとの約束）を置き場 b の RULINGS_FILE に書いてパスを返す。
    ファイルと、名指す申し出の回の控え（PARKED_REPLY）は今の scope の周の置き場の物（同じブロックの 2 度目の include である
    2 回目の修正の段は 1 回目の物を上書きも名指しもしない）"""
    rows = [r for r in conflict.items(b) if r.get("ruling")]
    second = conflict.second_pass(b)
    lines = [prompt.render_part("ruling-title", {"head": conflict.HEAD}).strip(), ""]
    for r in rows:
        ru = r["ruling"]
        state = conflict.replan_state(r)
        amended = state == conflict.AMENDED
        lines += [ROW_HEAD.format(id=r["id"], unit_key=r["unit_key"]), "",
                  f"- 裁定: {ru['decision']}（{ru.get('by') or ''}）——{promise(r, second)}",
                  f"- 裁定の文: {ru['text']}",
                  f"- 範囲: {', '.join(ru.get('limits') or []) or '（無い）'}",
                  *([f"- 案の項目: {', '.join(map(str, ru[conflict.PLAN_ITEMS]))}"] if ru.get(conflict.PLAN_ITEMS) else []),
                  *([f"- 項目の単位（{'直す義務に戻った' if amended else 'どれも直すな'}）: {', '.join(ru[conflict.PLAN_UNITS])}"]
                    if ru.get(conflict.PLAN_UNITS) else []),
                  *([f"- 案の直しを諦めた理由: {r.get(conflict.REPLAN_WHY) or '（無し）'}"] if state == conflict.GAVE_UP else []),
                  *([f"- 裁きの出どころ: {', '.join(ru['grounds'])}"] if ru.get("grounds") else []),
                  *([f"- 依頼で探して答えが無かったこと: {ru['request_searched']}"] if ru.get("request_searched") else []),
                  *([f"- 置き換えた問い: {json.dumps(ru['query'], ensure_ascii=False)}"] if ru.get("query") else []),
                  *([f"- 申し出の正しい行: {json.dumps(r[conflict.CORRECT], ensure_ascii=False)}"] if r.get(conflict.CORRECT) else []),
                  f"- 申し出の名指し: {', '.join(r['between'])}",
                  f"- 申し出の理由: {r[conflict.WHY_FIELD]}（正しいと見た側: {r[conflict.WHICH_FIELD]}）",
                  f"- 申し出の種類: {r.get(conflict.KIND_FIELD) or '（無し）'}", ""]
    parked = pathlib.Path(b) / conflict.PARKED_REPLY
    if parked.is_file():
        lines += [prompt.render_part("ruling-previous-reply", {"parked": str(parked)}).strip(), ""]
    path = pathlib.Path(b) / conflict.RULINGS_FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp, path)
    return path


def park(place, rows: list) -> None:
    """輪の状態の未送の行 {source, item} を place に積む（conflict.park_claims）。作り直した後にまた止まった単位（案を直して直す義務に戻った
    単位の、機械が諦めた申し出）は裁定に回さず ask_human つきで積まれるので、裁定の文のファイルを書き直す"""
    repeated = conflict.repeat_gave_up(place, rows)
    conflict.park_claims(place, rows)
    if repeated:
        write(place)
