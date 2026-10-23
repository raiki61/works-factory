"""範囲の宣言と照らす変更の決めと、関わる試験の選びの起点（元の workflows/test-gate/scripts/run.py の changed を port の値で受ける形に写した物）。

範囲の宣言 .works-checks.json の段ごとの paths_ignore は、変更が全部その下に在る段を回さないために、変更のパスと照らす。
変更は base から今の作業ツリーまでに触ったファイルから、Archon が作業ツリーに置く工程の写しを除いた物（範囲の宣言と照らすのは
最後のテストだけ。直す前は段を走らせない。持ち主の決め base-selfcheck-only）。依頼の行の where は関わる試験の選びの起点に足す（related_wheres）。
"""
from __future__ import annotations

import pathlib

import ports

import accept       # lib/
import checkscope   # lib/


def related_wheres(request, request_scope: bool) -> list:
    """関わる試験の選びの起点に足す依頼の行の where の並び。base と final の両方に足す（final の選びが base の選びを含むように。
    docs/design/test-gate.md の 14.3）。request_scope が偽・依頼が無い時は []"""
    if request_scope is not True or not isinstance(request, list):
        return []
    return [row["where"] for row in request if isinstance(row, dict) and isinstance(row.get("where"), str)]


def related_pick(root, doc: dict, cache_dir) -> dict:
    """関わる試験の選び（lib/related.pick）。起点の版は入口の差分の根 entry_base（空なら修正前の版 base、それも無ければ HEAD）から
    今の作業ツリーまでに触ったファイルと、依頼の where が名指す追跡中のパス（related_wheres）"""
    import related   # lib/
    root = pathlib.Path(root)
    seeds = checkscope.request_files(root, related_wheres(doc["request"], doc["request_scope"]))
    return related.pick(root, rev=doc["entry_base"] or doc["base"] or "HEAD", seeds=seeds, cache_dir=cache_dir)


def changed(root, base: str, wheres=()):
    """範囲の宣言と照らす変更（根からのパス）。base から今の作業ツリーまでに触ったファイルと、依頼の where が名指す追跡中のパス
    （wheres）の和から Archon の置き場を除いた物。測れない（git の誤り・空）なら None（絞らない）"""
    root = pathlib.Path(root)
    files = set(checkscope.request_files(root, wheres))
    if base:
        try:
            files |= set(accept.touched_files(root, base))
        except accept.Reject:
            return None
    return sorted(f for f in files if not f.startswith(ports.RUNTIME_COPY_PREFIX)) or None
