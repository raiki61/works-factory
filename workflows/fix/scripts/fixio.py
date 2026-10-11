# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""fix のブロックの script が共に読む、Archon との出入りの助け（置き場の場所・作業ツリー・控えのファイル）。

lib/ は Archon の名を持たない（lib/AGENTS.md の E3）ので、Archon に届く事（ARTIFACTS_DIR・ARCHON_NODE_EXECUTION・.archon/）は
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


def repo() -> pathlib.Path:
    """作業ツリーの根（script は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return pathlib.Path(top.stdout.strip())


# Archon が script に渡す変数の頭。対象のテストの実行器に継がせない（lib/ は環境を os.environ から継いで子を起こす）
RUNNER_VARS = ("ARCHON_", "INPUTS_", "ARTIFACTS_DIR", "TYPED_ARTIFACTS_FILE", "WORKFLOW_ID")


def drop_runner_env() -> None:
    """入力を読み終えた後、テストを走らせる lib/ の関数を呼ぶ前に呼ぶ"""
    for name in [n for n in os.environ if n.startswith(RUNNER_VARS)]:
        del os.environ[name]
