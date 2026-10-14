"""run の作業ツリーの起点: 新しい run の Archon に渡す --from <commit> を、対象の今の姿（HEAD と、commit していない変更）から決める。

作業ツリーを切るのは Archon（--from の commit から git worktree add）で、ここは起点の commit を決めるだけ。汚れた対象は一時の index で
包んだ commit（親は HEAD）を作り、対象の作業ツリー・index・枝・ref は動かさない。包んだ commit に ref は付けない: Archon が起動の内に
そこから枝を切って守り、Archon が拒んだ時は利用者の clone に何も残さない（到達できない object は git の gc が既定 2 週間残す）。
今の works の dev/use.sh の start の包み（refs/works/wraps/ の ref と clean の片付け）の代わり。origin の無い対象の拒みと既定の枝の
求めは Archon が持つ。
"""
import os
import subprocess
import tempfile
from pathlib import Path

# 名指しが勝つ旗と、Archon が --from と組むのを拒むか作業ツリーを作らない旗
SKIP_FLAGS = ("--from", "--from-branch", "--no-worktree", "--folder", "--container", "--adopt", "--dry-run")
WRAP_MESSAGE = "works-factory: 起動の殻が包んだ対象の手元の姿（run の作業ツリーの起点）"
# 包んだ commit の作者と commit した者。利用者の git の名の設定に頼らない
WRAP_IDENTITY = {"GIT_AUTHOR_NAME": "works-factory", "GIT_AUTHOR_EMAIL": "works-factory@localhost",
                 "GIT_COMMITTER_NAME": "works-factory", "GIT_COMMITTER_EMAIL": "works-factory@localhost"}


def choose(flags: list[str], workflow: str, target: Path, prefix: str) -> tuple[list[str], str]:
    """足す引数（["--from", <commit>] か []）と、人に出す 1 行（足さない時は ""）。flags は -- の前の利用者の引数。
    自分のグラフ（名が prefix で始まる）の時だけ足す。git の木でない・commit の無い木も足さない"""
    if not workflow.startswith(prefix) or any(a == f or a.startswith(f + "=") for a in flags for f in SKIP_FLAGS):
        return [], ""
    head = subprocess.run(["git", "-C", str(target), "rev-parse", "--verify", "-q", "HEAD^{commit}"], capture_output=True,
                          text=True, encoding="utf-8")
    if head.returncode != 0:
        return [], ""
    sha = head.stdout.strip()
    if not _git(target, "status", "--porcelain", "--untracked-files=normal"):
        return ["--from", sha], f"run の作業ツリーは対象の HEAD {sha[:12]} から切る"
    wrapped, changes = wrap(target)
    return ["--from", wrapped], (f"commit していない変更・未追跡のファイル {len(changes)} 件を commit {wrapped[:12]} に包み、"
                                 f"run の作業ツリーはそこから切る（対象の作業ツリー・index・枝は動かさない）: {' '.join(changes)}")


def wrap(target: Path) -> tuple[str, list[str]]:
    """対象の作業ツリーの今の姿（未追跡も。git が無視する物は入れない）を、親が HEAD の commit にする。返す物は commit と、HEAD
    との差の name-status の行（区切りは空白）"""
    with tempfile.TemporaryDirectory(prefix="works-factory-wrap-") as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index"), **WRAP_IDENTITY}
        _git(target, "read-tree", "HEAD", env=env)
        _git(target, "add", "-A", env=env)
        tree = _git(target, "write-tree", env=env)
        commit = _git(target, "commit-tree", "--no-gpg-sign", tree, "-p", "HEAD", "-m", WRAP_MESSAGE, env=env)
    changes = _git(target, "diff", "--name-status", "--no-renames", "HEAD", commit)
    return commit, [" ".join(line.split("\t")) for line in changes.splitlines()]


def _git(target: Path, *args: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, encoding="utf-8", env=env)
    if done.returncode != 0:
        raise RuntimeError(f"run の作業ツリーの起点を決める git {args[0]} が落ちた: {' '.join(done.stderr.split())}")
    return done.stdout.strip()
