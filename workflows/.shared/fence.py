"""埋め P5（docs/polyfills.md）: 読むだけの役の claude を起こす直前に、書き込みを禁じるパスの一覧を組んで sandbox の denyWrite に足す包み。

止めた Archon は役の sandbox を置き換えずに SDK へ渡す（packages/workflows/src/dag-executor.ts:1847・
packages/providers/src/claude/provider.ts:801-803）ので、YAML の固定の値では run ごとに違うパス（cwd・共通の .git・worktree の根）を
名指せない。Archon が起こす claude の実行ファイルは CLAUDE_BIN_PATH で替えられる（packages/providers/src/claude/binary-resolver.ts:172-178）
ので、起動の殻（bin/_lib/launcher.py の write_fence）がこの包みをそこに置く。SDK は sandbox を `--settings <JSON>` に入れて渡す。

形は今の works の role_run.protected_paths（works/.shared/core/graphloops/engine/role_run.py:102-117）と、包み claude-adapter の
「旗 no-tree-write の起動に denyWrite を足す」を採った。旗の代わりに、YAML が読むだけの役に書く固定の値
（tests/layers/scan.py の NO_TREE_WRITE。~ を HOME で解くと Archon の家）を印に読む。印の無い起動は argv を変えずに起こす。
標準ライブラリだけを使う（起動の殻が `python -I -B` で起こす）。
"""
import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence

SETTINGS = "--settings"
REFUSED_EXIT = 3


class Refused(Exception):
    """書き込みを禁じる一覧を決められない。claude を起こさずに止める"""


def protected(cwd: str, archon_home: str, claude_config: str, own: Sequence[str]) -> list[str]:
    """書き込みを禁じるパスの一覧（実パス。順はそろえ、重複は除く）: cwd・共通の .git・全部の worktree の根（本体の根を含むので、
    worktree.path で本体の下へ移した worktree も入る）・Archon の家（artifacts と既定の置き場の worktree）・Claude の設定（読んだ証拠と
    書き込みの記録とフック）・own（起動の殻が書いた口と、この包み自身）。cwd が git の作業ツリーでなければ git から引く物は足さない"""
    paths = [cwd]
    common = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common is not None:
        paths.append(common.strip())
        listed = _git(cwd, "worktree", "list", "--porcelain") or ""
        paths += [line[len("worktree "):] for line in listed.splitlines() if line.startswith("worktree ")]
    paths += [archon_home, claude_config, *own]
    return list(dict.fromkeys(os.path.realpath(p) for p in paths))


def _git(cwd: str, *args: str) -> str | None:
    """git の出力。cwd が git の作業ツリーでなければ None"""
    try:
        done = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "LC_ALL": "C"})
    except OSError as error:
        raise Refused(f"git を起こせない（{error}）") from None
    if done.returncode == 0:
        return done.stdout
    if "not a git repository" in done.stderr:
        return None
    raise Refused(f"git {args[0]} が終了の値 {done.returncode} で落ちた: {' '.join(done.stderr.split())[:200]}")


def fenced_argv(argv: list[str], archon_home: str, paths: Callable[[], list[str]]) -> list[str]:
    """argv の --settings の sandbox.filesystem.denyWrite が印（~ を解くと archon_home）を持つ時だけ、paths() の一覧のうち無い物を
    後ろに足した argv。印が無ければ argv のまま"""
    at = [i for i, a in enumerate(argv) if a == SETTINGS or a.startswith(SETTINGS + "=")]
    if len(at) > 1:
        raise Refused(f"{SETTINGS} が {len(at)} 個ある。印が在るかを決められない")
    if not at:
        return argv
    i = at[0]
    joined = argv[i] != SETTINGS
    if not joined and i + 1 == len(argv):
        raise Refused(f"{SETTINGS} に値が無い")
    raw = argv[i][len(SETTINGS) + 1:] if joined else argv[i + 1]
    if not raw.lstrip().startswith("{"):
        return argv
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Refused(f"{SETTINGS} の JSON を読めない（{error}）") from None
    if not isinstance(settings, dict):
        raise Refused(f"{SETTINGS} の JSON が object でない")
    deny = settings
    for key in ("sandbox", "filesystem", "denyWrite"):
        deny = deny.get(key) if isinstance(deny, dict) else None
    if not (isinstance(deny, list) and any(marks(item, archon_home) for item in deny)):
        return argv
    deny += [p for p in paths() if p not in deny]
    value = json.dumps(settings, ensure_ascii=False)
    return [*argv[:i], f"{SETTINGS}={value}", *argv[i + 1:]] if joined else [*argv[:i + 1], value, *argv[i + 2:]]


def marks(item, archon_home: str) -> bool:
    return isinstance(item, str) and os.path.realpath(os.path.expanduser(item)) == os.path.realpath(archon_home)


def main(argv: list[str]) -> int:
    cut = argv.index("--") if "--" in argv else len(argv)
    ap = argparse.ArgumentParser(prog="fence.py")
    ap.add_argument("--real", required=True)
    ap.add_argument("--archon-home", required=True)
    ap.add_argument("--claude-config", required=True)
    ap.add_argument("--own", action="append", default=[])
    opts = ap.parse_args(argv[:cut])
    rest = argv[cut + 1:]
    try:
        rest = fenced_argv(rest, opts.archon_home,
                           lambda: protected(os.getcwd(), opts.archon_home, opts.claude_config, opts.own))
    except Refused as refused:
        print(f"works-factory fence: {refused}", file=sys.stderr)
        return REFUSED_EXIT
    os.execv(opts.real, [opts.real, *rest])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
