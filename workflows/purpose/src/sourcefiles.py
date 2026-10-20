"""目的の出典のファイル（返答の source_files）の照らし（docs/design/purpose.md の 1.5。lib/purpose.py の _source_files_errors と、
それが頼る lib/judge_accept.py の _resolve_target・_in_version の写し）。

- errors(files, repo): source_files のうち、作業ツリーの根からの相対の正規形で、版の一覧に在り、作業ツリーに通常のファイルとして在る
  物でない名前（並びは返答のまま）。後の周の突き合わせは `git diff --name-only` の名前（根からの相対）と字のまま比べるので、絶対パス・
  リポジトリの外・無い名前・正規形でない名前は決して当たらず、走り直しが黙って止まる。根は engine.util.repo_root（repo が
  サブディレクトリでも作業ツリーの根）、git の向き先は accept.in_repo(repo)。git が動かなければ Reject（『分からない』を合格に倒さない）
"""
from __future__ import annotations

import pathlib

import accept                 # lib/。in_repo
from engine import util       # lib/graphloops/engine/util.py。git・repo_root・Reject


def in_version(rels) -> dict | None:
    """指し先の候補を版の一覧で引く——{rel: "text" | "binary"}（無い rel は入らない）。git が動かなければ None"""
    got = util.git("ls-files", "-z", "--full-name", "--cached", "--others", "--exclude-standard", "--eol",
                   "--", *[f":(top,literal){r}" for r in rels])
    if got is None:
        return None
    want, found = set(rels), {}
    for ent in got.split("\0"):
        meta, sep, path = ent.partition("\t")
        if sep and path in want:
            found[path] = "binary" if "w/-text" in meta.split() else "text"
    return found


def resolve_target(tgt, root) -> tuple:
    """役が書いたパス 1 つを、リポジトリ相対の正規形 1 つに解く ——（rel, 理由）。綴りが正規形と違えば拒む"""
    rootp = pathlib.Path(root).resolve()
    try:
        real = (rootp / tgt).resolve()
        rel = real.relative_to(rootp).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None, "リポジトリの外を指している（リポジトリ相対のパスで書け。絶対パスや '..' で外へ出る指しは受け取らない）"
    if rel != tgt:
        return None, f"正規形で書け: '{rel}'（'./' 付き・'..' で戻る綴り・symlink 経由は、指し先が 1 つに決まらない）"
    return rel, ""


def errors(files, repo) -> list:
    with accept.in_repo(repo):
        root = util.repo_root(util.git)
        if root is None:
            raise util.Reject(f"source_files を確かめられない（{repo} で作業ツリーの根を git から引けない）")
        bad, rels = [], []
        for f in files:
            rel, _ = resolve_target(f, root) if f else (None, "")
            (rels if rel is not None else bad).append(f)
        seen = in_version(rels) if rels else {}
        if seen is None:
            raise util.Reject("source_files を確かめられない（git ls-files が動かない）")
    bad += [f for f in rels if f not in seen or not (pathlib.Path(root) / f).is_file()]
    return [f for f in files if f in bad]
