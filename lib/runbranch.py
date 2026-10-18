"""run の作業ツリーの枝へ commit を積む 1 か所（周の鎖の周の結果と、出口の語 pr の差分の commit が使う）。標準ライブラリだけ。

積むのは本体でない作業ツリー（git-dir と git-common-dir が違う）の、枝を指す HEAD だけ。本体の作業ツリーは利用者の物で、切り離された
HEAD に積んだ commit は枝に残らない。呼び手が exclude に名指したパス（工程の写しの置き場など）は積まない。対象の hooks に止めさせない
ため --no-verify で commit し、作者は利用者の git の設定に依らない固定の名で、署名しない。

- refusal(repo) -> str: 積まない訳（積める木なら空）
- commit(repo, message, exclude) -> (changed, head): 今の変更を 1 つの commit に積み、(積んだか, 今の HEAD)。変更が無ければ積まない
- branch(repo) -> str: HEAD が指す枝の短い名
- default_branch(repo, remote) -> str: remote の既定の枝（remote の HEAD が指す枝）の短い名。git ls-remote --symref で読む
- git(repo, *args) -> str: git を repo で 1 回走らせた標準出力（0 でなければ GitFailed）
"""
import os
import subprocess
from pathlib import Path

AUTHOR = ("-c", "user.name=works-factory", "-c", "user.email=works-factory@localhost", "-c", "commit.gpgsign=false")
MAIN_TREE = "本体の作業ツリーでは commit しない（積むのは run のために切った作業ツリーだけ）"
DETACHED = "HEAD が枝を指していない（切り離された HEAD には commit しない）"
HEADS = "refs/heads/"


class GitFailed(RuntimeError):
    """git が 0 でない終了の値で終わった（文は 1 行）"""


def git(repo: Path, *args: str) -> str:
    # 資格の問い合わせで止まらないように、端末にも ssh にも聞かせない
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if "GIT_SSH_COMMAND" not in env and "GIT_SSH" not in env:
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", env=env)
    if done.returncode != 0:
        raise GitFailed(f"git {' '.join(args)} が終了の値 {done.returncode}: {' '.join(done.stderr.split())}")
    return done.stdout.strip()


def refusal(repo: Path) -> str:
    own, common = (Path(repo, git(repo, "rev-parse", path)).resolve() for path in ("--git-dir", "--git-common-dir"))
    if own == common:
        return MAIN_TREE
    if subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo, capture_output=True).returncode != 0:
        return DETACHED
    return ""


def commit(repo: Path, message: str, exclude: str) -> tuple:
    """refusal が空の木でだけ呼ぶ（呼び手が訳を返すため、ここでは照らし直さない）"""
    git(repo, "add", "-A", "--", ".", f":(exclude){exclude}")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo, capture_output=True).returncode == 0:
        return False, git(repo, "rev-parse", "HEAD")
    git(repo, *AUTHOR, "commit", "--no-verify", "-q", "-m", message)
    return True, git(repo, "rev-parse", "HEAD")


def branch(repo: Path) -> str:
    return git(repo, "symbolic-ref", "--short", "HEAD")


def default_branch(repo: Path, remote: str) -> str:
    for line in git(repo, "ls-remote", "--symref", remote, "HEAD").splitlines():
        ref, _, name = line.partition("\t")
        if name == "HEAD" and ref.startswith("ref: " + HEADS):
            return ref[len("ref: " + HEADS):]
    raise GitFailed(f"{remote} の HEAD が枝を指していない（git ls-remote --symref {remote} HEAD）")
