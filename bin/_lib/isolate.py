"""HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR・XDG_* を run の置き場の下へ向けた、Archon を起こす子の環境を組む。

今の works の works/dev/archon.sh の同じ所を Python に移した物（E15）。Archon と Claude Code が利用者の家の設定・状態を
読み書きしないようにする。keychain は利用者の HOME で読み（macOS の security はログイン keychain を $HOME 基準で探す）、
Claude Code 自身の keychain の項目の名と、macOS 以外の保存済みのログイン（.credentials.json）の置き場は利用者の CLAUDE_CONFIG_DIR
から決まるので、その 2 つ（auth_launch.py の --user-home・--user-config）や hostgh.py write の --home・--gh-config-dir・
--xdg-config-home は、呼ぶ側が隔離の前の env から取る。そのために env は変えずに写しを返す。auth_launch.py はこの子の環境に認証の
変数だけを足すので、どの認証の道でも子の CLAUDE_CONFIG_DIR は隔離した置き場のまま。
利用者が lib/userenv.py の OPT_IN を立てた時だけ、隔離の前の HOME・XDG_* を子の userenv.RECORD に控える（対象のコマンドにだけ
戻す。決めと訳は userenv）。立てなければ、利用者の env から継いだ控えも子に残さない。戻した印の置き場（userenv.RAN_DIR_ENV）も、利用者の env から継いだ値は
子に残さない（印はメイングラフの run の置き場にだけ置く）。
"""
from collections.abc import Mapping
from pathlib import Path

from lib import userenv

DIRS = {
    "HOME": "home",
    "ARCHON_HOME": "archon-home",
    "CLAUDE_CONFIG_DIR": "claude-config",
    "XDG_CONFIG_HOME": "xdg-config",
    "XDG_DATA_HOME": "xdg-data",
    "XDG_CACHE_HOME": "xdg-cache",
    "XDG_STATE_HOME": "xdg-state",
}


def isolate(env: Mapping[str, str], run_home: Path) -> dict[str, str]:
    """env の DIRS の名を run_home の下のフォルダ（作る）へ向けた子の環境（控えは userenv.record の時だけ）。env は変えない"""
    if not run_home.is_absolute():
        raise ValueError(f"run の置き場は絶対パスにする（受けた値: {run_home}）")
    child = dict(env)
    child.pop(userenv.RECORD, None)
    child.pop(userenv.RAN_DIR_ENV, None)
    if (record := userenv.record(env)) is not None:
        child[userenv.RECORD] = record
    for name, sub in DIRS.items():
        target = run_home / sub
        target.mkdir(parents=True, exist_ok=True)
        child[name] = str(target)
    return child
