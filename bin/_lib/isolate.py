"""HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR・XDG_* を run の置き場の下へ向けた、Archon を起こす子の環境を組む。

今の works の works/dev/archon.sh の同じ所を Python に移した物（E15）。Archon と Claude Code が利用者の家の設定・状態を
読み書きしないようにする。keychain は利用者の HOME で読み（macOS の security はログイン keychain を $HOME 基準で探す）、
Claude Code 自身の keychain の項目の名は利用者の CLAUDE_CONFIG_DIR から決まるので、その 2 つ（auth_launch.py の
--user-home・--user-config）や hostgh.py write の --home・--gh-config-dir・--xdg-config-home は、呼ぶ側が隔離の前の env から取る。
そのために env は変えずに写しを返す。
"""
from collections.abc import Mapping
from pathlib import Path

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
    """env の DIRS の名を run_home の下のフォルダ（作る）へ向けた子の環境。env は変えない"""
    if not run_home.is_absolute():
        raise ValueError(f"run の置き場は絶対パスにする（受けた値: {run_home}）")
    child = dict(env)
    for name, sub in DIRS.items():
        target = run_home / sub
        target.mkdir(parents=True, exist_ok=True)
        child[name] = str(target)
    return child
