"""目的の文（graph の節 p0.purpose）の部品。判定のブロックの受け付け（lib/judge_accept の check_purpose）が読む。実行基盤を知らない関数だけを出す。

- _source_files_errors(files, repo): 目的の出典 source_files のうち、作業ツリーの根からの相対の正規形で版に在るファイルでない名前
- NODE・PREMISES_NODE・PURPOSE_FILE・REQUEST_COPY: 節の名と置き場のファイルの名

受け付け（凍結 → 作業ツリー → 足し欄 means を外す → source_files）は lib/judge_accept.check_purpose に在る。
"""
import pathlib
import sys

sys.dont_write_bytecode = True   # accept.py と同じ（下で import する物の .pyc を止める）

from accept import _in_repo  # noqa: E402
from engine.util import Reject  # noqa: E402

NODE = "p0.purpose"
PREMISES_NODE = "p0.premises"
PURPOSE_FILE = "purpose.json"             # 受け付けた目的の返答（graph の process.purpose と同じ中身）
PURPOSE_REVIEW_FILE = "purpose-review.json"   # 判定の隣の目的の監査の役の受けた返答（plan-review が独立設計を回すかを決める）
REQUEST_COPY = "purpose-request.json"     # 目的の役に渡す依頼の写し（前の run の判断 prior_failures を外した物。carry.without_prior）


def _source_files_errors(files, repo) -> list:
    """source_files のうち、作業ツリーの根からの相対の正規形で、版の一覧に在り、かつ作業ツリーに通常のファイルとして在る
    物でない名前（works が足す検査）。
    写しの purpose_sources_changed は、前の周の修正が触ったファイル（_files_changed_since の `git diff --name-only -z`
    の名前＝根からの相対）と source_files の完全一致の積で目的監査を走り直す。絶対パス・リポジトリの外・無い名前・
    正規形でない名前はその積に決して当たらず、走り直しが黙って止まる（p0.purpose は once なので、通せば run の全周で凍る）。
    判定は写しの rules の正本に任せ、ここで組み直さない: 根は _repo_root（repo がサブディレクトリでも作業ツリーの根）、
    綴りは _resolve_target（正規形と違えば拒む）、在るかは _in_version（`--full-name`・`:(top,literal)`）と is_file の組
    （rules が指し先を確かめる組と同じ）。git が動かなければ Reject（受け付けは『分からない』を合格に倒さない）"""
    import judge_accept as rules   # 写しの rules の _repo_root・_resolve_target・_in_version の書き直しの住処
    with _in_repo(repo):
        root = rules._repo_root()
        if root is None:
            raise Reject(f"source_files を確かめられない（{repo} で作業ツリーの根を git から引けない）")
        bad, rels = [], []
        for f in files:
            rel, _ = rules._resolve_target(f, root) if f else (None, "")
            (rels if rel is not None else bad).append(f)
        seen = rules._in_version(rels) if rels else {}
        if seen is None:
            raise Reject("source_files を確かめられない（git ls-files が動かない）")
    bad += [f for f in rels if f not in seen or not (pathlib.Path(root) / f).is_file()]
    return [f for f in files if f in bad]

