"""組の部品（fix の組の並べ。元 works/blk-fix/lib/lanekit.py の、段に依らない部分のうち fix の組が使う物）。
組ごとの子の run（fan_out）が直し、締めの節 join（fixboard.join_group）が子の差分を親の作業ツリーへ組の順に当てる。

口:
- groups(rows, after=()): [(id, タグの並び)] をタグを共にする物どうしの組に（つながりは推移的。組の並びは rows の順）。
  after は [(前の id, 後の id)] の依存の対で、対の 2 つを同じ組に繋ぎ、組の中は前を先に並べる（graphlib.TopologicalSorter の
  prepare・get_ready。get_ready の返りは並びの約束が無いので rows の位置で並べ直す）。rows の外の端を持つ対は捨てる。
  依存の循環は graphlib.CycleError（循環は案の受け付けが先に拒む）。純粋
- Merge: 組の差分を当てた結末（why・patch・names・unioned・clash・backed_out・unrestored）
- merge_in_order(lanes, merge_one): 組を順に当てる。merge_one(lane, earlier) が Merge を返し、earlier は前に当てた組の差分の
  パス（当てなかった組の物は入らない）。[(lane, Merge)]
"""
from __future__ import annotations

import graphlib
from typing import NamedTuple


class Merge(NamedTuple):
    why: str          # 当てなかった理由（当てたら空）
    patch: str        # 控えた枝の差分のファイル（差分を作る前に戻した時は空）
    names: list       # 当てた差分のパス（当てなかったら []）
    unioned: list     # 試験のファイルの挿しだけの食い違いを合わせたパス
    clash: bool       # 字の食い違いで当たらなかった
    backed_out: list = []   # 当ててから確かめ直しが赤か落ちて戻したパス（当てなかった・当てたままなら []）
    unrestored: list = []   # 当ててから戻そうとして戻せず、親の作業ツリーに当たったままのパス（戻せた・戻さなかったなら []）


def groups(rows, after=()) -> list:
    """[(id, タグの並び)] をタグを共にする物どうしの組に（頭の注記）。after の対（前, 後）も同じ組に繋ぎ、組の中を前から後へ並べる。
    返りは id の並びの並び（組は rows の先頭の順）"""
    rows = [(i, list(tags or [])) for i, tags in rows]
    parent = {i: i for i, _ in rows}
    place = {i: n for n, (i, _) in enumerate(rows)}
    pairs = [(a, b) for a, b in after if a in place and b in place and a != b]

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
    for a, b in pairs:
        parent[find(a)] = find(b)
    out = {}
    for i, _ in rows:
        out.setdefault(find(i), []).append(i)
    return [_ordered(g, pairs, place) for g in out.values()]


def _ordered(group, pairs, place) -> list:
    """組 group の中を pairs の依存の順に（準備できた物は rows の位置 place の順）。依存の無い組は rows の順のまま"""
    inside = [(a, b) for a, b in pairs if a in group and b in group]
    if not inside:
        return group
    sorter = graphlib.TopologicalSorter({i: [a for a, b in inside if b == i] for i in group})
    sorter.prepare()
    order = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready(), key=place.__getitem__)
        order += ready
        sorter.done(*ready)
    return order


def merge_in_order(lanes, merge_one) -> list:
    """枝を順に当てる（頭の注記）"""
    earlier, out = set(), []
    for lane in lanes:
        got = merge_one(lane, frozenset(earlier))
        if not got.why:
            earlier |= set(got.names)
        out.append((lane, got))
    return out

