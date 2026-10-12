"""修正前の関所の 4 つの軸を軸ごとに分ける（能力の名 gate_axes。元に無い部品）。

今の works の gatemarks.axes（works/.shared/core/gatemarks.py:576）は、関所の行を聞かずに通してよいかの 4 つの軸のうち揃わない物の
訳を 1 つの並びで返す。線の修正前の関所（線 6）は軸ごとの {ok, note} を読むので、軸ごとの訳（gatemarks.axis_reasons。axes も
これを並べる。軸の決まりの持ち主）を {ok, note} にまとめる。軸の決まりは書き足さない（gatemarks.py の頭の文と今の works の
CHANGELOG の 2026-10-09 の行）:
- obvious（自明）: 決め手の出どころ decided_by が在り、決まらない訳 undecided_because が空で、出どころが現物に在る
- world（世界の解）: 世界の解の段の行の在る run はこの軸で見ない（外れは world_items が聞く）。行の無い run は world か URL の決め手
- clean（汚くない）: 行の単位に構造の目が人に上げた行が無く、汚れると見た単位には修正案の欄 structure の答えが在る
- not_overkill（やりすぎでない）: 柵の印 fences が無く、修正案の単位の外を名指さない

- split(b, mark, units) -> {軸: {ok, note}}: 関所の行 1 つ
- gather(b) -> {軸: {ok, note}}: 関所の全部の行（gatemarks._gate_rows）と、世界の解の外れの行（world_items）と構造の目が人に上げた
  設計の問い（design_items）。項目の無い軸は {ok: True, note: ""}
"""
from __future__ import annotations

import gatemarks

AXES = gatemarks.AXES


def _note(notes: list) -> dict:
    return {"ok": not notes, "note": "／".join(dict.fromkeys(notes))}


def split(b, mark: dict, units) -> dict:
    """関所の行 1 つ（決め手の欄 mark・行の単位 units）の軸ごとの {ok, note}。全部 ok の時だけ gatemarks.axes が空"""
    return {axis: _note(notes) for axis, notes in gatemarks.axis_reasons(b, mark, units).items()}


def gather(b) -> dict:
    """関所の全部の行の軸ごとの {ok, note}（note は行の頭と訳）"""
    notes = {axis: [] for axis in AXES}
    for _, text, mark, _, units in gatemarks._gate_rows(b):
        for axis, why in gatemarks.axis_reasons(b, mark, units).items():
            notes[axis] += [f"{text}: {w}" for w in why]
    notes["world"] += [f"{text}: {' / '.join(why)}" for text, _, why in gatemarks.world_items(b) if why]
    notes["clean"] += [text for _, text in gatemarks.design_items(b)]
    return {axis: _note(rows) for axis, rows in notes.items()}
