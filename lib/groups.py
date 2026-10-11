"""組ごとの作業ツリーの間で姿と差分を渡す口（fix の組の並べ。元に無い所だけ。組の作りそのものは lanekit.groups）。

親の作業ツリーの今の姿を木の sha で子に渡して写し、子の差分を 2 つの木の差分で戻す。
- adopt_tree(repo, tree): repo の作業ツリーと index を木 tree の姿にする
- end_tree(repo) -> sha: 作業ツリーの今の姿の木（leftovers.snapshot）
- diff_since(repo, from_tree, end_tree) -> str: 2 つの木の差分（unittrees.apply が当てられる形）
"""
import leftovers
import unittrees


def adopt_tree(repo, tree: str) -> None:
    """repo の作業ツリーと index を木 tree の姿にする（git read-tree -u --reset）。HEAD・枝は動かさない。
    木に在る名の追跡外のファイルが作業ツリーに在っても落ちずに木の中身で上書きする。木に無い追跡外のファイルは残す。
    git が落ちれば leftovers.Unreadable"""
    leftovers.git(repo, "read-tree", "-u", "--reset", tree)


def end_tree(repo) -> str:
    """repo の作業ツリーの今の姿（未追跡の新しいファイルも。無視される物は除く）の木の sha。本物の index は触らない"""
    return leftovers.snapshot(repo)


def diff_since(repo, from_tree: str, end_tree: str) -> str:
    """木 from_tree から木 end_tree への差分。unittrees.diff と同じ形（unittrees._DIFF: a/・b/ の頭・--binary・改名なし・
    外の diff と textconv なし）で取るので、unittrees.apply がそのまま当てられる。木は repo の git の物から読む
    （同じ clone の worktree の間なら共有）。git が落ちれば unittrees.UnitTreeError"""
    return unittrees._git(repo, *unittrees._DIFF, from_tree, end_tree).stdout.decode("utf-8", "surrogateescape")
