"""型 remove（変える段。利用者が使える機能を消す。docs/plans/2026-10-24-fix-weapons.md の 3.3）。

消す物と、それを縛る試験を消す。型の義務（2.4）: 消した試験は remove か rewrite の許しの中。消す名が返した木で引けないことは
変える段の箱の義務の 2（duties.change_named_or_gone の gone）。書き手は PR A では今の修正役。
"""
from __future__ import annotations

BOX = "change"


def removed_in_permits(f: dict) -> list:
    """消した試験（f["removed"]）が、どれも注文の permits の remove か rewrite の行の中"""
    allowed = {r.get("test") for r in f.get("permits") or [] if r.get("kind") in ("remove", "rewrite")}
    bad = [t for t in f.get("removed") or [] if t not in allowed]
    return [f"消した試験 {bad[:10]} が消す名の許し（remove）か書き換えの許し（rewrite）の中に無い"] if bad else []


DUTIES = (removed_in_permits,)
