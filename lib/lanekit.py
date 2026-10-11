"""並べの枝の部品（blk-fix。依頼 243 の並べ。設計 docs/plans/2026-10-07-fix-lane-nodes.md の「枝の部品」の節）。
TDD の輪の並べ（tddlanes。docs/plans/2026-10-07-lane-nodes.md）と修正役の並べ（fixlanes）が同じ形で使う、段に依らない部分だけを
持つ。どちらの段も実行基盤の節の形は同じ:

  組を作る（groups）→ 組ごとの枝（支度 → 枝の役 → … → 確かめ）→ 締める（merge_in_order）→ 順の輪

順の輪が受けるのは締めが戻した物と、枝に入らない物だけ

段が持つのは、何を枝に分けるか（TDD は項目を共にする単位の組、修正役は単位を共にする修正案の項目の組）・枝の役の指示書・枝の
確かめ（TDD は tddloop.step の赤・緑、修正役は受け付けと同じ事実の確かめと範囲の相談）・当てた後の確かめ（TDD は合わせた木の緑と
意味の食い違いの逃げ道、修正役は修正の輪の受け付け）だけ。ここはそれ以外を持つ:

口:
- JOINED・MERGED・BACK: 締めの出口を残す欄の名と、締めた後の結末の語（当てた・順に戻した）
- groups(rows): [(id, タグの並び)] をタグを共にする物どうしの組に（つながりは推移的。組の中と組の並びは rows の順。純粋）
- relocate(path, repo, tree): run の作業ツリーの中のパス（実行器など）を単位の worktree の同じ所へ（外ならそのまま）
- plant(repo, ns, place, manifest, union=()): 前の単位の worktree を片付け、run の作業ツリーの今の姿を base に枝ごとの単位の
  worktree（place/item-<n>）を切る（unitlanes.plant）。{n: {tree, git, base}}
- tree_ok(row): 行の単位の worktree（tree）の `.git` の 1 行が切った時（git）と同じなら空、違えば理由（役が指しを書き換えた枝は当てない）
- revert_strays(repo, base, keep=()): 枝の間に run の作業ツリーで変わったファイル（keep の外）を base の姿に戻す（枝の役は包みの
  柵で書けない。受け止め）。戻したパス
- merge(repo, tree, *, since, base, log, declared, made, kept, union, earlier, check, skip): 枝の差分を run の作業ツリーへ 3 方向で当てる
  （書き込みの記録の無い変更・当たらない差分・当てた中身が単位の worktree と違う物は当てない。枝の実行器が作ったファイル made は
  base の姿に戻して差分に入れない。除くパスの頭 skip（既定 ()）の下は書き込みの記録と突き合わせない）。Merge（why・patch・names・unioned・clash）
- merge_in_order(lanes, merge_one): 枝を順に当てる。merge_one(lane, earlier) が Merge を返し、earlier は前に当てた枝の差分の
  パス（当てなかった枝の物は入らない）。[(lane, Merge)]
- shared(patches): 2 本以上の枝の差分に出たファイル
- carry(log, repo, applied, shared): 当てた枝の書き込みの記録を run の作業ツリーへ写す（unitlanes.carry_records）
- remove(repo, trees): 単位の worktree と守りの参照を片付ける（git が断った物は理由を返し、次の plant の sweep に任せる）
"""
from __future__ import annotations

import pathlib
import sys
from typing import NamedTuple

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE.parents[1] / ".shared" / "core", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import tddloop  # noqa: E402  （木の固め・戻し）
import unitlanes  # noqa: E402
import unittrees  # noqa: E402
import writes  # noqa: E402

JOINED = "joined"                   # 締めの出口を残す欄（resume で回し直された締めはこれを返す）
MERGED = "merged"                   # 締めた後の結末: 枝の差分を当てた
BACK = "serial"                     # 締めた後の結末: 順に戻した（順の輪が直す）


class Merge(NamedTuple):
    why: str          # 当てなかった理由（当てたら空）
    patch: str        # 控えた枝の差分のファイル（差分を作る前に戻した時は空）
    names: list       # 当てた差分のパス（当てなかったら []）
    unioned: list     # 試験のファイルの挿しだけの食い違いを合わせたパス
    clash: bool       # 字の食い違いで当たらなかった


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


def relocate(path, repo, tree) -> pathlib.Path:
    """run の作業ツリーの中のパスを単位の worktree の同じ所へ（頭の注記）"""
    path = pathlib.Path(path)
    try:
        return pathlib.Path(tree) / path.absolute().relative_to(pathlib.Path(repo).absolute())
    except ValueError:
        return path


def plant(repo, ns, place, manifest, union=()) -> dict:
    """枝ごとの単位の worktree を切る（頭の注記）"""
    trees = unitlanes.plant(repo, list(ns), place, manifest, union)
    return {n: {**row, "git": unitlanes._git_line(row["tree"])} for n, row in trees.items()}


def tree_ok(row) -> str:
    """単位の worktree の指しの確かめ（頭の注記）。row は tree と git を持つ行（目録の行・枝の控え）"""
    tree, git = row["tree"], row.get("git") or ""
    if git and unitlanes._git_line(tree) == git:
        return ""
    return f"単位の worktree {tree} の .git の指しが切った時と違う（この枝は当てず、順に戻す）"


def revert_strays(repo, base: str, keep=()) -> list:
    """枝の間に run の作業ツリーで変わったファイルを戻す（頭の注記）"""
    stray = sorted(set(tddloop.touched(repo, base, tddloop.snapshot(repo))) - set(keep))
    if stray:
        tddloop.restore_paths(repo, base, stray)
    return stray


def merge(repo, tree, *, since: str, base: str, log, declared=(), made=(), kept, union=(), earlier=(), check=None,
          skip=()) -> Merge:
    """枝の差分を当てる（頭の注記）。since は枝の役が書いた変更の起点（書き込みの記録と突き合わせる）、base は差分の起点（切った時の
    run の作業ツリーの姿）、kept は差分を控えるファイル、earlier は前に当てた枝の差分のパス（そのファイルは中身の照らしから外す）。
    check（段の照らし。当てたパスの並び → 戻す理由か空）が理由を返せば、当てた物を戻して当てない。skip は除くパスの頭（書き込みの
    記録と突き合わせない。writes.unrecorded に渡す。既定 ()）"""
    repo, tree, log = pathlib.Path(repo), pathlib.Path(tree), pathlib.Path(log)
    touched = set(tddloop.touched(tree, since, tddloop.snapshot(tree)))
    if touched & set(made):   # 枝の実行器が作った・変えたファイルは差分に入れない（役の直しでない。記録も無い）
        tddloop.restore_paths(tree, since, touched & set(made))
    moved = sorted(touched - set(made))
    if log.is_file():
        left = writes.unrecorded(tree, moved, log, list(declared), skip)
        if left:
            return Merge(writes.REJECT + ", ".join(left[:10]), "", [], [], False)
        writes.keep_declared(log, tree, list(declared))
    patch = unittrees.diff(tree, base)
    kept = pathlib.Path(kept)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(patch, encoding="utf-8", errors="surrogateescape")
    before = tddloop.snapshot(repo)
    got = []
    ok, why = unittrees.apply(repo, patch, union=union, unioned=got, check=unitlanes.tests_unique)
    if not ok:
        return Merge(f"差分が run の作業ツリーに当たらない（{' '.join(why.split())[:300]}）", str(kept), [], [], True)
    names = unitlanes._names(patch)
    differ = [n for n in names if n not in set(earlier) and not unitlanes._same(repo / n, tree / n)]
    why = f"当てた中身が単位の worktree と違う（{differ[:5]}）" if differ else (check(names) if check else "")
    if why:
        tddloop.restore_paths(repo, before, names)
        return Merge(why, str(kept), [], [], False)
    return Merge("", str(kept), names, got, False)


def merge_in_order(lanes, merge_one) -> list:
    """枝を順に当てる（頭の注記）"""
    earlier, out = set(), []
    for lane in lanes:
        got = merge_one(lane, frozenset(earlier))
        if not got.why:
            earlier |= set(got.names)
        out.append((lane, got))
    return out


def shared(patches) -> list:
    """2 本以上の枝の差分に出たファイル（patches は差分のファイルの並び）"""
    seen = {}
    for patch in patches:
        for n in unitlanes._names(pathlib.Path(patch).read_text(encoding="utf-8", errors="surrogateescape")):
            seen[n] = seen.get(n, 0) + 1
    return sorted(n for n, c in seen.items() if c > 1)


def carry(log, repo, applied, shared_files) -> None:
    """当てた枝の書き込みの記録を写す（applied は [(単位の worktree, 差分のファイル)]）"""
    unitlanes.carry_records(log, repo, applied, shared_files)


def remove(repo, trees) -> list:
    """単位の worktree を片付ける。git が断った worktree の理由の並び（残った物は次の plant の sweep が消す。締めを落とさない）"""
    left = []
    for t in trees:
        try:
            unittrees.remove(repo, t)
        except (unittrees.UnitTreeError, OSError) as e:
            left.append(f"{t}: {' '.join(str(e).split())[:200]}")
    return left
