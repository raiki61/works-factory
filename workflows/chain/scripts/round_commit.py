# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の結果の commit のノード round-k-commit。

子の run（メイングラフ）は親の作業ツリーを共有し、run の中で HEAD を動かさない。だから作業ツリーの今の変更が、その周の頭からの
変更になる。それを親の run の枝へ commit し、次の周の頭にする（changed: true・head: 新しい HEAD）。変更が無ければ commit せず
changed: false（決めが no_change で止める）。Archon が run の作業ツリーに写す置き場（boundary.RUNTIME_COPY）は積まない。
利用者の枝には書かない: 鎖のグラフの頭の worktree.enabled: true が、run の作業ツリーを Archon が切った worktree に限る
（--no-worktree の起動は Archon が拒む）。重ねて、git-dir と git-common-dir が同じ（本体の作業ツリー）か HEAD が切り離されている
時は commit せずに ok: false で返す。対象の hooks に止めさせないため --no-verify で commit する。
落ちない: git の誤りも ok: false と訳に畳み、決めが halted で止める。

入力: 無し（ノードの cwd が run の作業ツリー）
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

AUTHOR = ("-c", "user.name=works-factory", "-c", "user.email=works-factory@localhost", "-c", "commit.gpgsign=false")
MESSAGE = "works-factory-chain の周の結果"


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} が終了の値 {done.returncode}: {' '.join(done.stderr.split())}")
    return done.stdout.strip()


def refused(reason: str) -> dict:
    return {"ok": False, "changed": None, "head": "", "reason": reason}


def commit() -> dict:
    here = Path.cwd()
    own, common = (Path(here, git("rev-parse", path)).resolve() for path in ("--git-dir", "--git-common-dir"))
    if own == common:
        return refused("本体の作業ツリーでは commit しない（周の結果を積むのは Archon が切った run の作業ツリーだけ）")
    if subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], capture_output=True).returncode != 0:
        return refused("HEAD が枝を指していない（切り離された HEAD には commit しない）")
    git("add", "-A", "--", ".", f":(exclude){boundary.RUNTIME_COPY}")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True).returncode == 0:
        return {"ok": True, "changed": False, "head": git("rev-parse", "HEAD"), "reason": ""}
    git(*AUTHOR, "commit", "--no-verify", "-q", "-m", MESSAGE)
    return {"ok": True, "changed": True, "head": git("rev-parse", "HEAD"), "reason": ""}


if __name__ == "__main__":
    boundary.run(commit, refused)
