"""範囲の宣言と照らす変更の決めと、関わる試験の選びの起点（元の workflows/test-gate/scripts/run.py の changed を port の値で受ける形に写した物）。

範囲の宣言 .works-checks.json の段ごとの paths_ignore は、変更が全部その下に在る段を回さないために、変更のパスと照らす。
変更は base から今の作業ツリーまでに触ったファイルから、Archon が作業ツリーに置く工程の写しを除いた物（範囲の宣言と照らすのは
最後のテストだけ。直す前は試験を走らせない。持ち主の決め base-runs-nothing）。依頼の行の where は関わる試験の選びの起点に足す（related_wheres）。
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


def cannot_launch(root, test_cmd: str) -> str:
    """直す前の確かめ（持ち主の決め base-runs-nothing の足し。試験は走らせない）: test_cmd の最初の語が作業ツリーで起こせるか。起こせれば
    ""、起こせなければ訳の 1 行。shell で起こす形は lib/tree_run.prove_launchable（bash の command -v）、直に起こす形は最初の語を
    PATH（対象のテストと同じ tree_run.outside_env の環境）か作業ツリーからのパスで引く。展開を含むなど字面から引けない語は確かめずに
    起こせると読む（prove_launchable と同じ限界）。test_cmd が空なら ""（確かめる物が無い）"""
    import os
    import shutil
    import tree_run   # lib/
    cmd = (test_cmd or "").strip()
    if not cmd:
        return ""
    root = pathlib.Path(root)
    argv, how = tree_run.command_argv(cmd)
    env = tree_run.outside_env(os.environ)
    try:
        if how == "shell":
            tree_run.prove_launchable(argv, cwd=str(root), env=env)
        else:
            word = argv[0]
            if "/" in word:
                path = pathlib.Path(word) if pathlib.Path(word).is_absolute() else root / word
                if not (path.is_file() and os.access(path, os.X_OK)):
                    raise FileNotFoundError(f"作業ツリーから引いた {path} が無いか実行できない")
            elif shutil.which(word, path=env.get("PATH")) is None:
                raise FileNotFoundError(f"PATH に {word} が無い")
    except OSError as e:
        return f"試験のコマンド（{cmd}）の最初の語を起こせない（{e}）。試験は走らせずに確かめた"
    return ""
