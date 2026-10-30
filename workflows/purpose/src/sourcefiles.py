"""目的の出典のファイル（返答の source_files）の照らし（docs/design/purpose.md の 1.5。指し先の綴りと版の照らしは lib/cite の
_resolve_target・_in_version の 1 か所を使う）。

- errors(files, repo): source_files のうち、作業ツリーの根からの相対の正規形で、版の一覧に在り、作業ツリーに通常のファイルとして在る
  物でない名前（並びは返答のまま）。後の周の突き合わせは `git diff --name-only` の名前（根からの相対）と字のまま比べるので、絶対パス・
  リポジトリの外・無い名前・正規形でない名前は決して当たらず、走り直しが黙って止まる。根は engine.util.repo_root（repo が
  サブディレクトリでも作業ツリーの根）、git の向き先は accept.in_repo(repo)。git が動かなければ Reject（『分からない』を合格に倒さない）
"""
from __future__ import annotations

import pathlib

import accept                 # lib/。in_repo
import cite                   # lib/。_resolve_target・_in_version（指し先の照らしの 1 か所）
from engine import util       # lib/graphloops/engine/util.py。git・repo_root・Reject


def errors(files, repo) -> list:
    with accept.in_repo(repo):
        root = util.repo_root(util.git)
        if root is None:
            raise util.Reject(f"source_files を確かめられない（{repo} で作業ツリーの根を git から引けない）")
        bad, rels = [], []
        for f in files:
            rel, _ = cite._resolve_target(f, root) if f else (None, "")
            (rels if rel is not None else bad).append(f)
        seen = cite._in_version(rels) if rels else {}
        if seen is None:
            raise util.Reject("source_files を確かめられない（git ls-files が動かない）")
    bad += [f for f in rels if f not in seen or not (pathlib.Path(root) / f).is_file()]
    return [f for f in files if f in bad]
