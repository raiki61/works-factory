"""組の部品（fix の組の並べ。元 works/blk-fix/lib/lanekit.py の、段に依らない部分のうち fix の組が使う物）。
組ごとの子の run（fan_out）が直し、締めの節 join（fixboard.join_group）が子の差分を親の作業ツリーへ組の順に当てる。

口:
- groups(rows): [(id, タグの並び)] をタグを共にする物どうしの組に（つながりは推移的。組の中と組の並びは rows の順。純粋）
- Merge: 組の差分を当てた結末（why・patch・names・unioned・clash）
- merge_in_order(lanes, merge_one): 組を順に当てる。merge_one(lane, earlier) が Merge を返し、earlier は前に当てた組の差分の
  パス（当てなかった組の物は入らない）。[(lane, Merge)]
"""
from __future__ import annotations

from typing import NamedTuple


class Merge(NamedTuple):
    why: str          # 当てなかった理由（当てたら空）
    patch: str        # 控えた枝の差分のファイル（差分を作る前に戻した時は空）
    names: list       # 当てた差分のパス（当てなかったら []）
    unioned: list     # 試験のファイルの挿しだけの食い違いを合わせたパス
    clash: bool       # 字の食い違いで当たらなかった
    backed_out: list = []   # 当ててから確かめ直しが赤で戻したパス（当てなかった・当てたままなら []）


def groups(rows) -> list:
    """[(id, タグの並び)] をタグを共にする物どうしの組に（頭の注記）。返りは id の並びの並び"""
    rows = [(i, list(tags or [])) for i, tags in rows]
    parent = {i: i for i, _ in rows}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    first = {}
    for i, tags in rows:
        for t in tags:
            if t in first:
                parent[find(i)] = find(first[t])
            else:
                first[t] = i
    out = {}
    for i, _ in rows:
        out.setdefault(find(i), []).append(i)
    return list(out.values())


def merge_in_order(lanes, merge_one) -> list:
    """枝を順に当てる（頭の注記）"""
    earlier, out = set(), []
    for lane in lanes:
        got = merge_one(lane, frozenset(earlier))
        if not got.why:
            earlier |= set(got.names)
        out.append((lane, got))
    return out

