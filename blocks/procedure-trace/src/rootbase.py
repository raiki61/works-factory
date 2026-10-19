"""差分の根に空の木の id を渡せる口（最初の commit だけの対象リポジトリなど、根にできる前の commit が無い時に、木の全部を対象差分にする）。

git が知っている空の木から親の無い commit を 1 つ作って（枝も index も動かさない。物を 1 つ足すだけ）その id を返す。それ以外の
base は触れずに返す。作れなければ base をそのまま返し、あとで差分を取る口が「版として引けない」と拒む。
"""
import os
import subprocess

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
IDENT = {"GIT_AUTHOR_NAME": "works-factory", "GIT_AUTHOR_EMAIL": "works-factory@localhost",
         "GIT_COMMITTER_NAME": "works-factory", "GIT_COMMITTER_EMAIL": "works-factory@localhost"}


def resolve(repo, base):
    if base != EMPTY_TREE:
        return base
    done = subprocess.run(["git", "commit-tree", EMPTY_TREE, "-m", "works-factory empty root"], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, **IDENT})
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else base
