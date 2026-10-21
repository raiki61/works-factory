"""run の値の控え values.json（docs/design/fix.md の 1.4。今の始めの記録の写し r1/start.json の代わり）。読み書きはここだけ。

欄: tdd_suite・test_cmd・reuse_key・reuse_dir・user_env_dir・lang・policy（人の方針の文書のパス）・request_file（依頼のファイルの
パス）・answers（依頼のファイルが先に持っていた問いへの答えの行。今の始めの記録の answers）・unattended・parallel・skip_rerun・
excluded（並行 PR に回した hunk の行 {pr, file, start, end, why}。受け付けが触った返答を拒む）・routes（単位ごとの道の決め方。auto か plan）。
組の子は親の物を写す（adopt。子の with: は mode・from_tree・out_dir・group だけ）。
"""
from __future__ import annotations

import json
import os
import pathlib

from src import files

KEYS = ("tdd_suite", "test_cmd", "reuse_key", "reuse_dir", "user_env_dir", "lang", "policy", "request_file", "answers",
        "unattended", "parallel", "skip_rerun", "excluded", "routes")
DEFAULTS = {"tdd_suite": "", "test_cmd": "", "reuse_key": "", "reuse_dir": "", "user_env_dir": "", "lang": "", "policy": "",
            "request_file": "", "answers": [], "unattended": False, "parallel": True, "skip_rerun": [],
            "excluded": [], "routes": "auto"}


def _save(path: pathlib.Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write(place, values: dict) -> dict:
    """values（KEYS の値。無い鍵は DEFAULTS）を place の values.json と lib の始めの記録の形の写しに置き、置いた値を返す"""
    doc = {k: values.get(k, DEFAULTS[k]) for k in KEYS}
    place = pathlib.Path(place)
    _save(place / files.VALUES, doc)
    return doc


def read(place) -> dict:
    """place の values.json（無い・読めない・欄の欠けは DEFAULTS で埋める）"""
    try:
        got = json.loads((pathlib.Path(place) / files.VALUES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        got = {}
    got = got if isinstance(got, dict) else {}
    return {k: got.get(k, DEFAULTS[k]) for k in KEYS}


def adopt(parent, place) -> dict:
    """親の place の values.json を子の place に置き直す（lib の写しも）。親に無ければ子の物のまま"""
    if not (pathlib.Path(parent) / files.VALUES).is_file():
        return read(place)
    return write(place, read(parent))
