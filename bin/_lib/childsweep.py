"""線の後始末（issue #113）: fix の並べ（groups-par）の子の run が残した作業ツリーと枝を、止めた Archon の complete --force で消す。

Archon は fan_out の子の作業ツリーを子が終わっても消さない（Archon の authoring-workflows.md の「It is not removed when the child
finishes」）。この部品は線の最後の節から呼ばれ、この run の子だけを選んで消し、返り {cleaned, left, error} に消した物と残した物を
名と理由つきで書く。落ちる代わりに error に書く（何も消さずに返す）。

- 選び: workflow runs --json --all の行の parent_run_id がこの run（WORKFLOW_ID）で、metadata の branch_name（作業ツリーを
  持つ子だけに在る。Archon の packages/workflows/src/executor.ts）が archon/task-<この run の id の頭 8 字>- で始まる物
  （packages/core/src/workflows/child-isolation-resolver.ts）。一覧は新しい順なので、この run の行が一覧に在れば子は全部入っている。
- status が completed の子だけを消す。再開は completed の子を起こし直さず記録だけを使うが、failed などの子は作業ツリーを
  使い回して起こし直す（packages/workflows/src/dag-executor.ts の fan_out の再開）。
- --force は commit していない変更の照らしを越えるために要る（子は修正を commit せず木の sha で親へ渡す）。越えないのは
  Archon が作った証の照らしで、人の作業ツリーは Archon が拒む（packages/isolation/src/providers/worktree.ts）。
  complete は終了の値で成否を言わないので、標準出力の「  Completed: <枝>」の行で読む（packages/cli/src/commands/isolation.ts）。
  作業ツリーを消した後に手元か遠くの枝を消せなかった時も Completed: を出し、標準エラーの「  Warning: 」の行でだけ言う
  （packages/isolation/src/providers/worktree.ts の deleteBranchTracked）ので、その時は警告を理由に残した物へ入れる。
- 起こし方: 入口の殻を入れ子にすると別の ARCHON_HOME を開き源を取り直しに行くので、殻が渡す源のパス（place.SOURCE_ENV）の
  CLI を bun で直に起こす。Archon の CLI は git の木の中でしか動かない（packages/cli/src/cli.ts の requiresGitRepo）ので
  --cwd に run の作業ツリーを渡し、打つ場所は ARTIFACTS_DIR にする（Archon は打った場所の .archon/.env を読む。
  packages/cli/src/load-cli-env.ts）。complete は遠くの枝も消しにいく（子の枝は push されないので遠くは変わらない）ため、git の資格の
  問い合わせで止まらないよう GIT_TERMINAL_PROMPT=0 と ssh の BatchMode を付ける。
"""
import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from bin._lib import place

BRANCH_HEAD = "archon/task-"
RUN_HEAD = 8
BRANCH_KEY = "branch_name"
NODE_KEY = "parent_node_id"
PARENT_KEY = "parent_run_id"
DONE = "completed"
COMPLETED = "Completed: "
WARNING = "Warning: "
LIST_LIMIT = 1000
REASON_LIMIT = 300

Run = Callable[..., subprocess.CompletedProcess]


def select(run_id: str, listing: object) -> tuple[list[dict], list[dict]]:
    """workflow runs --json の返りから、この run の作業ツリーを持つ子を（消す物, 理由つきで残す物）に分ける。読めなければ ValueError"""
    runs = listing.get("runs") if isinstance(listing, dict) and listing.get("ok") is not False else None
    if not isinstance(runs, list):
        raise ValueError(f"workflow runs の返りに runs の一覧が無い: {_clip(json.dumps(listing, ensure_ascii=False))}")
    if not any(r.get("id") == run_id for r in runs):
        raise ValueError(f"一覧にこの run が無い（新しい順の {LIST_LIMIT} 件を越えた）")
    remove, left = [], []
    for r in runs:
        if r.get(PARENT_KEY) != run_id:
            continue
        metadata = _metadata(r.get("metadata"))
        branch = metadata.get(BRANCH_KEY)
        if not branch:
            continue
        found = {"branch": branch, "run_id": r.get("id"), "node": metadata.get(NODE_KEY) or ""}
        if not branch.startswith(f"{BRANCH_HEAD}{run_id[:RUN_HEAD]}-"):
            left.append({**found, "reason": "枝の名がこの run の子の形でない"})
        elif r.get("status") != DONE:
            left.append({**found, "reason": f"子の run が {r.get('status')}。再開が作業ツリーを使い回しうるので残す"})
        else:
            remove.append(found)
    return remove, left


def outcome(branch: str, stdout: str, stderr: str) -> str | None:
    """complete <branch> の出力から、作業ツリーも枝も消せたなら None、消せなかったならその理由"""
    if any(line.strip() == f"{COMPLETED}{branch}" for line in stdout.splitlines()):
        warnings = [line.strip() for line in stderr.splitlines() if line.strip().startswith(WARNING)]
        return _clip(f"作業ツリーは消えたが枝が残りうる: {' / '.join(warnings)}") if warnings else None
    said = " / ".join(line.strip() for line in (stderr + "\n" + stdout).splitlines() if line.strip())
    return _clip(said) or "complete が何も言わなかった"


def sweep(run_id: str, checkout: str, env: Mapping[str, str], run: Run = subprocess.run) -> dict:
    """この run の completed の子の作業ツリーと枝を消し、{cleaned, left, error} を返す。checkout は run の作業ツリー（節の cwd）"""
    result = {"cleaned": [], "left": [], "error": ""}
    source = env.get(place.SOURCE_ENV)
    if not source:
        result["error"] = f"{place.SOURCE_ENV} が無い（入口の殻 bin/works-factory から起こした run でない）"
        return result
    bun = shutil.which("bun", path=env.get("PATH"))
    if not bun:
        result["error"] = "bun が PATH に無い。Archon を起こせない"
        return result
    child_env = {**env, "GIT_TERMINAL_PROMPT": "0"}
    if "GIT_SSH_COMMAND" not in env and "GIT_SSH" not in env:
        child_env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    head = place.archon(bun, Path(source))

    def archon(*args: str) -> subprocess.CompletedProcess:
        return run([*head, *args, "--cwd", checkout], env=child_env, cwd=env.get("ARTIFACTS_DIR") or None,
                   capture_output=True, text=True, encoding="utf-8")

    listed = archon("workflow", "runs", "--json", "--all", "--limit", str(LIST_LIMIT))
    try:
        remove, result["left"] = select(run_id, _last_json(listed.stdout))
    except ValueError as error:
        result["error"] = f"{error}（終了の値 {listed.returncode}、標準エラー: {_clip(listed.stderr)}）"
        return result
    for found in remove:
        done = archon("complete", "--force", found["branch"])
        reason = outcome(found["branch"], done.stdout, done.stderr)
        if reason is None:
            result["cleaned"].append(found)
        else:
            result["left"].append({**found, "reason": reason})
    return result


def _last_json(stdout: str) -> object:
    """標準出力の最後の JSON（ログの行の後ろに 1 行で出る物も、字下げして複数行で出る誤りの物も読む）"""
    lines = stdout.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("{")]
    if not starts:
        raise ValueError(f"workflow runs が JSON を出さなかった: {_clip(stdout)}")
    try:
        return json.loads("\n".join(lines[starts[-1]:]))
    except json.JSONDecodeError as error:
        raise ValueError(f"workflow runs の JSON が読めない: {error}") from None


def _metadata(value: object) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _clip(text: str) -> str:
    return " ".join(text.split())[:REASON_LIMIT]
