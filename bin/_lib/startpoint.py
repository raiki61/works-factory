"""run の作業ツリーの起点: 新しい run の Archon に渡す --from <commit> を、対象の今の姿（HEAD と、commit していない変更）から決める。

作業ツリーを切るのは Archon（--from の commit から git worktree add）で、ここは起点の commit を決めるだけ。汚れた対象は一時の index で
包んだ commit（親は HEAD）を作り、対象の作業ツリー・index・枝・ref は動かさない。包んだ commit に ref は付けない: Archon が起動の内に
そこから枝を切って守り、Archon が拒んだ時は利用者の clone に何も残さない（到達できない object は git の gc が既定 2 週間残す）。
今の works の dev/use.sh の start の包み（refs/works/wraps/ の ref と clean の片付け）の代わり。origin の無い対象の拒みと既定の枝の
求めは Archon が持つ。

remote に届くかの確かめ（unreachable）: Archon は新しい作業ツリーを切る前に、--from が在っても remote（設定の worktree.remote、無ければ origin、
それも無ければただ 1 つの remote）へ必ず問い合わせ（既定の枝の
ls-remote と fetch。packages/isolation/src/providers/worktree/create.ts の syncWorkspaceBeforeCreate）、届かなければ run を記録する前に
落ちる。殻はその前に Archon と同じ ls-remote を、Archon に渡すのと同じ env で打ち、一時の拒みは打ち直し、駄目なら訳を返す（殻は
Archon を起こさずに止める）。起こした後に Archon が落ちた時も、同じ確かめを 1 回打って訳を足す（bin/_lib/recordroot.py）。
"""
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path

# 利用者が起点か枝を名指した旗（名指しが勝つ。枝の名指しは Archon が既に在る枝を --from と組むのを拒み、在る作業ツリーを使う時は
# --from を捨てる）と、Archon が --from と組むのを拒むか作業ツリーを作らない旗。tests/shared/test_archon_contract.py が Archon の旗に照らす
SKIP_FLAGS = ("--from", "--from-branch", "--branch", "--base", "--no-worktree", "--folder", "--container", "--adopt", "--dry-run")
# 枝の短い名 -b（-b 値・-b値・-b=値と、真偽の短い名と組んだ -vb 値。Archon の parseArgs が受ける形）
SKIP_SHORT = re.compile(r"-[A-Za-z]*b")
WRAP_MESSAGE = "works-factory: 起動の殻が包んだ対象の手元の姿（run の作業ツリーの起点）"
# 包んだ commit の作者と commit した者。利用者の git の名の設定に頼らない
# origin への問い合わせを打つ回数と、打ち直しの前の待ち（秒。i 回目の後に WAITS[i-1]）
TRIES = 3
WAITS = (1.0, 2.0)
# 端末で資格を尋ねない（Archon の packages/git/src/credentials.ts の gitCredentialOptions と同じ）
QUIET_ENV = {"GIT_TERMINAL_PROMPT": "0"}
WRAP_IDENTITY = {"GIT_AUTHOR_NAME": "works-factory", "GIT_AUTHOR_EMAIL": "works-factory@localhost",
                 "GIT_COMMITTER_NAME": "works-factory", "GIT_COMMITTER_EMAIL": "works-factory@localhost"}


def choose(flags: list[str], workflow: str, target: Path, prefix: str) -> tuple[list[str], str]:
    """足す引数（["--from", <commit>] か []）と、人に出す 1 行（足さない時は ""）。flags は -- の前の利用者の引数。
    自分のグラフ（名が prefix で始まる）の時だけ足す。git の木でない・commit の無い木も足さない"""
    if not workflow.startswith(prefix) or any(_skips(a) for a in flags):
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


def unreachable(target: Path, env: Mapping[str, str], sleep: Callable[[float], object] = time.sleep, tries: int = TRIES,
                configured: str | None = None, say: Callable[[str], object] | None = None) -> str:
    """Archon が作業ツリーを切る前に問い合わせる remote に届かなければ、その訳の 1 行。届けば・確かめる remote が無ければ ""。
    remote は Archon と同じに選ぶ（対象の .archon/config.yaml の worktree.remote〔configured。殻が読んで渡す〕、無ければ origin が
    在れば origin、無ければただ 1 つの remote。packages/isolation/src/providers/worktree/create.ts の resolveRemote と
    packages/git/src/repo.ts の getDefaultRemote）。remote が無い・選べない対象は Archon が自分の文で拒むので、ここは確かめない。
    問い合わせは Archon と同じ ls-remote（packages/git/src/remote-branches.ts の inspectRemoteBranches）を env（Archon に渡す env）で
    打ち、tries 回まで打ち直す。say が在れば、問い合わせる前に待つ物を 1 行渡す（期限は付けない。持ち主の決め no-timeouts。前例は runtime-auth-gate の確かめ）"""
    names = _remotes(target, env)
    remote = (configured or "").strip() or _default(names)
    if remote is None:
        return ""
    if say is not None:
        say(f"{remote} に届くかを確かめている（待ちの上限は無い。止めるなら Ctrl-C）")
    reason = ""
    for attempt in range(tries):
        if attempt:
            sleep(WAITS[min(attempt, len(WAITS)) - 1])
        done = subprocess.run(["git", "-C", str(target), "ls-remote", "--symref", "--quiet", "--", remote, "HEAD", "refs/heads/*"],
                              capture_output=True, text=True, encoding="utf-8", env={**env, **QUIET_ENV})
        if done.returncode == 0:
            return ""
        reason = " ".join(done.stderr.split()) or f"git ls-remote の終了の値 {done.returncode}"
    check = "網・ssh の鍵・資格を確かめて打ち直す" if remote in names else (
        f"{remote} は対象の git の remote に無い。remote の設定（対象の .archon/config.yaml の worktree.remote と git remote -v）を確かめて打ち直す")
    return (f"{remote} に届かない（git ls-remote {remote} を {tries} 回打って全部落ちた: {reason}）。"
            f"Archon は run の作業ツリーを切る前に {remote} へ問い合わせる。{check}")


def _remotes(target: Path, env: Mapping[str, str]) -> list[str]:
    done = subprocess.run(["git", "-C", str(target), "remote"], capture_output=True, text=True, encoding="utf-8", env=dict(env))
    return done.stdout.split() if done.returncode == 0 else []


def _default(names: list[str]) -> str | None:
    """設定の名指しが無い時に Archon が使う remote: origin が在れば origin、無ければただ 1 つの remote（2 つ以上なら選べない）"""
    return "origin" if "origin" in names else names[0] if len(names) == 1 else None


def _skips(arg: str) -> bool:
    return any(arg == f or arg.startswith(f + "=") for f in SKIP_FLAGS) or SKIP_SHORT.match(arg) is not None


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
