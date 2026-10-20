"""考えの地図・柵の表の探し方（計画 docs/plans/2026-10-09-clean-whole.md の 3.2 節・Task 2.1）。

地図と表は対象のリポジトリの追跡されたファイルから、決まった名（MAP_NAME・TABLE_NAME。根か、どのフォルダの下でも）で探す
（.editorconfig と同じ「決まった名のファイルが在れば読む」形。対象を名指さない。無ければ役は対象自身の構造から住処を探す）。
地図や表を作らない。役への指示の文は持たない（md が持つ）。

- 定数: MAP_NAME・TABLE_NAME・PREFIX（考えの住処の指摘の頭の語）・MAX_MAPS
- pick_maps(names) -> (先頭 MAX_MAPS 件, 全件の数): 名の並びから地図を浅い順・名の順に選ぶ
- pick_tables(names) -> list: 名の並びから柵の表を浅い順・名の順に選ぶ（件数で切らない）
- base_of(name) -> str: 地図か表のパスの持ち主のフォルダ（docs/ の親。根なら ""）。表の中のパスはここからの相対
- tracked_names(repo) -> (名の並び, 落ちた訳): `git ls-files` の行（投げない。落ちたら ([], 訳)）

標準ライブラリだけ。works の物を何も import しない。
"""
from __future__ import annotations

import pathlib
import subprocess

MAP_NAME = "docs/concepts.md"
TABLE_NAME = "docs/concepts.json"
PREFIX = "考えの住処: "
MAX_MAPS = 5

def pick_maps(names: list[str]) -> tuple[list[str], int]:
    """名が MAP_NAME か "/" + MAP_NAME で終わる物を、/ の数の少ない順・同じなら名の順に並べ、(先頭 MAX_MAPS 件, 全件の数)"""
    got = sorted(_named(names, MAP_NAME), key=lambda n: (n.count("/"), n))
    return got[:MAX_MAPS], len(got)


def pick_tables(names: list[str]) -> list[str]:
    """名が TABLE_NAME か "/" + TABLE_NAME で終わる物を、/ の数の少ない順・同じなら名の順に（件数で切らない）"""
    return sorted(_named(names, TABLE_NAME), key=lambda n: (n.count("/"), n))


def _named(names, tail: str) -> list[str]:
    return [n for n in names if isinstance(n, str) and (n == tail or n.endswith("/" + tail))]


def base_of(name: str) -> str:
    """地図か表のパス（…/docs/concepts.*）の持ち主のフォルダ（docs/ の親。根の docs なら ""）"""
    head = name.rsplit("/", 2)
    return head[0] if len(head) == 3 else ""


def tracked_names(repo) -> tuple[list[str], str]:
    """(追跡されたファイルの名の並び, 落ちた訳)。git が落ちても投げず ([], 訳)"""
    try:
        p = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, text=True, encoding="utf-8",
                           stdin=subprocess.DEVNULL)
    except (OSError, ValueError) as e:
        return [], f"git を起こせない: {e}"
    if p.returncode != 0:
        return [], (p.stderr.strip() or f"git ls-files が終了コード {p.returncode}")[-300:]
    return [n for n in p.stdout.split("\0") if n], ""
