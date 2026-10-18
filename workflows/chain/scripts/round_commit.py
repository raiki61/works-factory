# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の結果の commit のノード round-k-commit。

子の run（メイングラフ）は親の作業ツリーを共有し、run の中で HEAD を動かさない。だから作業ツリーの今の変更が、その周の頭からの
変更になる。それを親の run の枝へ commit し、次の周の頭にする（changed: true・head: 新しい HEAD）。変更が無ければ commit せず
changed: false（決めが no_change で止める）。Archon が run の作業ツリーに写す置き場（boundary.RUNTIME_COPY）は積まない。
利用者の枝には書かない: 鎖のグラフの頭の worktree.enabled: true が、run の作業ツリーを Archon が切った worktree に限る
（--no-worktree の起動は Archon が拒む）。重ねて、本体の作業ツリーと切り離された HEAD には commit せずに ok: false で返す
（積む所の照らしと積み方は lib/runbranch.py）。
落ちない: git の誤りも ok: false と訳に畳み、決めが halted で止める。

入力: 無し（ノードの cwd が run の作業ツリー）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import runbranch

MESSAGE = "works-factory-chain の周の結果"


def refused(reason: str) -> dict:
    return {"ok": False, "changed": None, "head": "", "reason": reason}


def commit() -> dict:
    here = Path.cwd()
    reason = runbranch.refusal(here)
    if reason:
        return refused(reason)
    changed, head = runbranch.commit(here, MESSAGE, boundary.RUNTIME_COPY)
    return {"ok": True, "changed": changed, "head": head, "reason": ""}


if __name__ == "__main__":
    boundary.run(commit, refused)
