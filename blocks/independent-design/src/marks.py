"""足した行の印に要る git の 3 つ（lib/fixboard.py の pr_revs・pr_diff・pr_added_lines と、それが使う lib/unittrees.py の部分の写し。
docs/design/independent-design.md の 1.5）。審査する変更（起点 → 修正前の HEAD）が足した行 {根からのパス: 行番号の集合} を返す。

写した訳: fixboard と unittrees は組み込みで fix の block へ移るので、組み込みの後は lib に無い。git が落ちた時は MarkError
（unittrees.UnitTreeError の代わり）。
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import changemap   # lib/。split_diff・new_side

# 外から継いだ git の居場所の変数は落とす（hook や節の中から呼ばれても、渡した repo だけを見る）
_GIT_PLACE = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
              "GIT_COMMON_DIR", "GIT_PREFIX")
# 利用者の設定に左右されない差分の形（apply が読める a/・b/ の頭・外の diff と textconv なし）
_DIFF = ["-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "diff", "--binary", "--no-renames", "--no-ext-diff",
         "--no-textconv", "--no-color", "--src-prefix=a/", "--dst-prefix=b/"]


class MarkError(RuntimeError):
    """git が落ちた（どのコマンドかと標準エラーを文に載せる）"""


def _out(repo, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k not in _GIT_PLACE}
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=env)
    if done.returncode != 0:
        raise MarkError(f"git {' '.join(args[:3])} が落ちた（{repo}）: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace").strip()


def pr_revs(repo, base: str, head: str) -> tuple[str, str]:
    """審査する変更の両端（起点 base・修正前の HEAD head）の commit の名。引けなければ MarkError"""
    base_sha, head_sha = (_out(repo, "rev-parse", "--verify", f"{rev}^{{commit}}") for rev in (base, head))
    return base_sha, head_sha


def pr_diff(repo, base_sha: str, head_sha: str, *opts: str) -> str:
    """審査する変更の差分（起点 base_sha → 修正前の HEAD head_sha）を git diff の形 opts で。git が落ちれば MarkError"""
    return _out(repo, "-c", "core.quotePath=false", *_DIFF, *opts, base_sha, head_sha, "--", ":/")


def pr_added_lines(repo, base_sha: str, head_sha: str) -> dict[str, set[int]]:
    """審査する変更（pr_diff）が足した行 {根からのパス: 修正前の HEAD での行番号}。消しただけのファイルは載せない。
    ファイルの分け方と行番号の数え方は changemap.split_diff・new_side"""
    added: dict[str, set[int]] = {}
    for path, lines in changemap.split_diff(pr_diff(repo, base_sha, head_sha, "-U0"))[0].items():
        for n, ln in changemap.new_side(lines):
            if ln.startswith("+"):
                added.setdefault(path, set()).add(n)
    return added
