# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""fix のブロックの script が共に読む、Archon との出入りの助け（置き場の場所・作業ツリー・控えのファイル）。

lib/ は Archon の名を持たない（lib/AGENTS.md の E3）ので、Archon に届く事（ARTIFACTS_DIR・ARCHON_NODE_EXECUTION・STATE_DIR・
CLAUDE_CONFIG_DIR・.archon/）は
ここと script の側だけが持ち、lib/ へは値を引数で渡す。節の script ではない（工程の YAML は名指さない）。
"""
import json
import os
import pathlib
import subprocess

# Archon が run の作業ツリーに写す工程の置き場。後始末・変更の確かめ・書き込みの出どころの照らしで数えない・消さないパスの頭
SKIP = (".archon/",)
BLOCK_NAME = "fix"
MODES = {"": False, "group": True}   # 入力 mode の語 → 組の子の run か（route が振り分け、collect が返りの形を選ぶ）


def include_name() -> str:
    """この節を差し込んだ include の名（節の実行の path の最初の __ より前）。fix と、案の直しの後の 2 回目の refix とで置き場を
    分ける。include の外（組の子の run・単独の run）は fix"""
    try:
        path = json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}").get("path") or ""
    except ValueError:
        path = ""
    head, sep, _ = path.partition("__")
    return head if sep and head else BLOCK_NAME


def place() -> pathlib.Path:
    """この run の置き場（run の成果物の置き場の下 fix/<include の名>/）。無ければ作る"""
    folder = pathlib.Path(os.environ["ARTIFACTS_DIR"]) / BLOCK_NAME / include_name()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def shared_cache() -> pathlib.Path | None:
    """run をまたぐ控えの根（Archon が project ごとに渡す STATE_DIR の下 works-factory/。渡されなければ None で、控えを使わない）"""
    state = os.environ.get("STATE_DIR")
    return pathlib.Path(state) / "works-factory" if state else None


def _writes_root() -> pathlib.Path | None:
    import writelog
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    root = writelog.root(config) if config else None
    return root if root is not None and root.is_dir() else None


def writes_log(cwd=None) -> pathlib.Path | None:
    """書き込みの記録のフック（bin/_lib/record-write.py）が作業の場 cwd（既定はこの節の cwd。役の節と同じ run の作業ツリー）の
    Edit・Write を残すファイル（lib/writelog.log_path）。記録の根（起動が隔離した設定 CLAUDE_CONFIG_DIR の下に作る）が無い起動は
    None で、受け付けは記録の無い run の道（writes.NO_RECORD）を通る"""
    import writelog
    root = _writes_root()
    return None if root is None else writelog.log_path(root, os.getcwd() if cwd is None else cwd)


def start_writes_log() -> None:
    """記録の根が在れば、この節の作業の場の記録を空で作る（在れば触らない。前の役の記録を残す）。置き場はフックと同じ
    writelog.open_log で作る（作業の場の控えつき）"""
    import writelog
    root = _writes_root()
    if root is not None:
        writelog.open_log(root, os.getcwd()).touch()


def repo() -> pathlib.Path:
    """作業ツリーの根（script は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return pathlib.Path(top.stdout.strip())


# Archon が script に渡す変数。対象のテストの実行器に継がせない（lib/ は環境を os.environ から継いで子を起こす）。節ごと・子の run
# ごとに値が違うので、残すと同じ run の中の試験の結果の使い回し（tree_run.reuse_run）の指紋も割れる。頭の一致は ARCHON_・INPUTS_
# だけで、ほかは名の完全一致（CONTEXT などを頭で落とすと利用者の変数まで落とす）。名は止めた Archon の
# packages/workflows/src/exec-environment.ts の buildExecNodeEnvironment。test-gate の run.py が同じ 2 つを持つ（試験が等しさを縛る）
RUNNER_PREFIXES = ("ARCHON_", "INPUTS_")
RUNNER_NAMES = frozenset({
    "ARTIFACTS_DIR", "STATE_DIR", "LOG_DIR", "ADOPTED_RUN_DIR", "WORKFLOW_ID", "BASE_BRANCH", "USER_MESSAGE", "ARGUMENTS",
    "LOOP_USER_INPUT", "LOOP_PREV_OUTPUT", "REJECTION_REASON", "CONTEXT", "EXTERNAL_CONTEXT", "ISSUE_CONTEXT", "TYPED_ARTIFACTS_FILE",
})


def drop_runner_env() -> None:
    """入力を読み終えた後、テストを走らせる lib/ の関数を呼ぶ前に呼ぶ"""
    for name in [n for n in os.environ if n.startswith(RUNNER_PREFIXES) or n in RUNNER_NAMES]:
        del os.environ[name]


def line_top(out_dir: str) -> pathlib.Path | None:
    """同じ run の中の試験の結果の控えを置く run の置き場（線の run の成果物の置き場）。組の子の run は入力 out_dir（親の置き場の
    <run の置き場>/fix/<include の名>/groups）から 3 つ上、単独の run（out_dir が空）は自分の ARTIFACTS_DIR。形が違えば None（使い回さない）"""
    if not out_dir:
        return pathlib.Path(os.environ["ARTIFACTS_DIR"])
    path = pathlib.Path(out_dir)
    if path.name != "groups" or len(path.parents) < 3 or path.parents[1].name != BLOCK_NAME:
        return None
    return path.parents[2]
