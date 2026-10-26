"""型 variant（変える段。今の direct の核。docs/plans/2026-10-24-fix-weapons.md の 3.2）。

同じ決まりを共有する所を全部挙げて直し、1 か所ずつ退行を注入して赤を見て、戻して緑を見る。書き手は PR A では今の修正役（指示は
prompts/parts/fixer.md のまま）。型の義務（2.4）:
1. class_query の在る単位は sites が 1 行以上あり、どの行も at が問いの当たりの行で、fixed_by が since から tree の差分の塊と重なる
   （sites_shape。段 2 で表に足す。書き手の指示が at・fixed_by を書かせてから）
2. 単位ごとに、sites のどれかに赤を見た記録がある（unit_red。段 2 で表に足す。PR A は今の周の全体の照らし recount._after_problems の
   F135 を variant・remove・pin の単位に当てる）
"""
from __future__ import annotations

BOX = "change"


def unit_red(f: dict) -> list:
    """義務 2: 単位の行の sites のどれかが赤を見た（red_seen）"""
    return [] if f.get("red_seen") else ["sites のどれにも赤を見た記録（red_seen）が無い——1 か所ずつ退行を注入して赤を見る"]


def sites_shape(f: dict) -> list:
    """義務 1: 問いの当たりの行（f["hits"]: 起点の木の path:line の集まり。問いを行で結べない単位は None）と、差分の新しい側の塊
    （f["hunks"]: {path: [(a, b)]}）に、sites の行の at・fixed_by が結ぶか"""
    sites = list(f.get("sites") or [])
    if f.get("class_query") is None:
        return []
    if not sites:
        return ["class_query の在る単位なのに sites が無い"]
    out = []
    hits, hunks = f.get("hits"), f.get("hunks") or {}
    for s in sites:
        at = str(s.get("at") or "")
        if hits is not None and at not in hits:
            out.append(f"site {s.get('site')!r} の at {at!r} が判定の問いの当たりの行に無い")
        for rng in s.get("fixed_by") or []:
            path, _, span = str(rng).rpartition(":")
            a, _, b = span.partition("-")
            if not (a.isdigit() and (not b or b.isdigit())):
                out.append(f"site {s.get('site')!r} の fixed_by {rng!r} が path:a-b の形でない")
                continue
            lo, hi = int(a), int(b or a)
            if not any(x <= hi and lo <= y for x, y in hunks.get(path, [])):
                out.append(f"site {s.get('site')!r} の fixed_by {rng!r} が差分の塊と重ならない")
    return out


DUTIES = ()   # 段 2 で (sites_shape, unit_red)
