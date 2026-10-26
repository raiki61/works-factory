"""型 variant（変える段。今の direct の核。docs/plans/2026-10-24-fix-weapons.md の 3.2）。

同じ決まりを共有する所を全部挙げて直し、1 か所ずつ退行を注入して赤を見て、戻して緑を見る。書き手は PR A では今の修正役（指示は
prompts/parts/fixer.md のまま）。型の義務（2.4）:
1. class_query の在る単位は sites が 1 行以上あり、どの行も at が問いの当たりの行（count: files の問いは当たりのファイル）で、fixed_by が
   1 つ以上あって since から tree の差分の塊と重なる（sites_shape。書き手の指示 rules_sites_at が at・fixed_by を書かせる）。問いを行で
   結べない単位（hits が None）は at と fixed_by の在る無しを照らさず、書いた fixed_by が塊と重なるかだけを照らす
2. 単位ごとに、sites のどれかに赤を見た記録がある（unit_red。書き手の指示 rules_red_unit が書かせる。周の全体の照らし
   recount._after_problems の F135 は board.RED_WEAPONS の型の単位に当て続ける）
"""
from __future__ import annotations

BOX = "change"


def unit_red(f: dict) -> list:
    """義務 2: 単位の行の sites のどれかが赤を見た（red_seen）"""
    return [] if f.get("red_seen") else ["sites のどれにも赤を見た記録（red_seen）が無い——1 か所ずつ退行を注入して赤を見る"]


def sites_shape(f: dict) -> list:
    """義務 1: 問いの当たりの行（f["hits"]: 起点の木の path:line の集まり。問いを行で結べない単位は None）と、差分の新しい側の塊
    （f["hunks"]: {path: [(a, b)]}）に、sites の行の at・fixed_by が結ぶか。count: files の問いは at のパスが当たりのファイルに在るかで照らす"""
    sites = list(f.get("sites") or [])
    if f.get("class_query") is None:
        return []
    if not sites:
        return ["class_query の在る単位なのに sites が無い"]
    out = []
    hits, hunks = f.get("hits"), f.get("hunks") or {}
    by_file = ((f["class_query"] or {}).get("how") or {}).get("count") == "files"
    for s in sites:
        at = str(s.get("at") or "")
        if hits is not None and by_file and _path(at) not in {_path(h) for h in hits}:
            out.append(f"site {s.get('site')!r} の at {at!r} が判定の問いの当たりのファイルに無い")
        elif hits is not None and not by_file and at not in hits:
            out.append(f"site {s.get('site')!r} の at {at!r} が判定の問いの当たりの行に無い")
        if hits is not None and not s.get("fixed_by"):
            out.append(f"site {s.get('site')!r} に fixed_by が無い——直した範囲を path:a-b で 1 つ以上書く")
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


def _path(at: str) -> str:
    """path:line の path（行の番号が無ければ全体）"""
    path, _, line = at.rpartition(":")
    return path if path and line.isdigit() else at


sites_shape.paragraph = "rules_sites_at"   # 書き手が at・fixed_by を書く段落（.shared/prompts/writer.md。duties.REPLY_FACTS を読む関数は持つ）
unit_red.paragraph = "rules_red_unit"
DUTIES = (sites_shape, unit_red)
