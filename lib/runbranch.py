"""run の作業ツリーの枝へ commit を積む 1 か所（周の鎖の周の結果と、出口の語 pr の差分の commit が使う）。標準ライブラリと lib の oneline だけ。

積むのは本体でない作業ツリー（git-dir と git-common-dir が違う）の、枝を指す HEAD だけ。本体の作業ツリーは利用者の物で、切り離された
HEAD に積んだ commit は枝に残らない。呼び手が exclude に名指したパス（工程の写しの置き場など）は積まない。作者は利用者の git の設定に
依らない固定の名で、署名しない。対象の commit の hooks は呼び手が選ぶ: 周の結果は run の中の途中の commit なので飛ばし（--no-verify）、
対象へ出す commit は呼び手が渡す環境（対象のコマンドの環境）で走らせる（落ちれば GitFailed）。

- refusal(repo) -> str: 積まない訳（積める木なら空）
- commit(repo, message, exclude, hook_env=None) -> (changed, head): 今の変更を 1 つの commit に積み、(積んだか, 今の HEAD)。変更が
  無ければ積まない。hook_env が None なら対象の commit の hooks を飛ばし、在ればその環境で commit して hooks を走らせる
- branch(repo) -> str: HEAD が指す枝の短い名
- default_branch(repo, remote) -> str: remote の既定の枝（remote の HEAD が指す枝）の短い名。git ls-remote --symref で読む
- pr_branches(repo, remote) -> (branch, base, reason): PR の push 先の run の枝と向け先の既定の枝。積めない・既定の枝を読めない・
  run の枝が既定の枝と同じ名なら reason が訳（枝は空）
- git(repo, *args, environ=None) -> str: git を repo で 1 回走らせた標準出力（0 でなければ GitFailed）。environ の既定は os.environ
"""
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import oneline

AUTHOR = ("-c", "user.name=works-factory", "-c", "user.email=works-factory@localhost", "-c", "commit.gpgsign=false")
MAIN_TREE = "本体の作業ツリーでは commit しない（積むのは run のために切った作業ツリーだけ）"
DETACHED = "HEAD が枝を指していない（切り離された HEAD には commit しない）"
HEADS = "refs/heads/"
ORIGIN = "origin"   # PR を出す remote（merge が積む前に照らし、最後の承認ノードが同じ枝を見せる）


class GitFailed(RuntimeError):
    """git が 0 でない終了の値で終わった（文は 1 行）"""


def git(repo: Path, *args: str, environ: Mapping[str, str] | None = None) -> str:
    # 資格の問い合わせで止まらないように、端末にも ssh にも聞かせない
    env = {**(os.environ if environ is None else environ), "GIT_TERMINAL_PROMPT": "0"}
    if "GIT_SSH_COMMAND" not in env and "GIT_SSH" not in env:
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", env=env)
    if done.returncode != 0:
        raise GitFailed(f"git {' '.join(args)} が終了の値 {done.returncode}: {oneline.one_line(done.stderr)}")
    return done.stdout.strip()


def refusal(repo: Path) -> str:
    own, common = (Path(repo, git(repo, "rev-parse", path)).resolve() for path in ("--git-dir", "--git-common-dir"))
    if own == common:
        return MAIN_TREE
    if subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo, capture_output=True).returncode != 0:
        return DETACHED
    return ""


def commit(repo: Path, message: str, exclude: str, hook_env: Mapping[str, str] | None = None) -> tuple:
    """refusal が空の木でだけ呼ぶ（呼び手が訳を返すため、ここでは照らし直さない）"""
    git(repo, "add", "-A", "--", ".", f":(exclude){exclude}")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo, capture_output=True).returncode == 0:
        return False, git(repo, "rev-parse", "HEAD")
    if hook_env is None:
        git(repo, *AUTHOR, "commit", "--no-verify", "-q", "-m", message)
    else:
        git(repo, *AUTHOR, "commit", "-q", "-m", message, environ=hook_env)
    return True, git(repo, "rev-parse", "HEAD")


def branch(repo: Path) -> str:
    return git(repo, "symbolic-ref", "--short", "HEAD")


def default_branch(repo: Path, remote: str) -> str:
    for line in git(repo, "ls-remote", "--symref", remote, "HEAD").splitlines():
        ref, _, name = line.partition("\t")
        if name == "HEAD" and ref.startswith("ref: " + HEADS):
            return ref[len("ref: " + HEADS):]
    raise GitFailed(f"{remote} の HEAD が枝を指していない（git ls-remote --symref {remote} HEAD）")


def pr_branches(repo: Path, remote: str) -> tuple:
    try:
        reason = refusal(repo)
        name = "" if reason else branch(repo)
    except GitFailed as error:
        return "", "", f"run の枝を読めない: {error}"
    if reason:
        return "", "", reason
    try:
        base = default_branch(repo, remote)
    except GitFailed as error:
        return "", "", f"対象の既定の枝を読めない（既定の枝へ push しないことを確かめられない）: {error}"
    if name == base:
        return "", "", f"run の枝 {name} が対象の既定の枝と同じ名（既定の枝へは push しない）"
    return name, base, ""
