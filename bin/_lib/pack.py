"""版の止めの正本 pack.json を読む。中身の説明は docs/design.md の「pack.json」の節。"""
import json
import re
from pathlib import Path

REQUIRED = (
    "archon.repo",
    "archon.commit",
    "asf.folder",
    "ours.folder",
)
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def load(root: Path) -> dict:
    """root/pack.json を読む。取り寄せと起動に使う鍵が 1 つでも欠けたら、欠けた鍵を全部名指して ValueError。

    archon.commit は取った源の置き場の名と照らしに使うので、40 字の小文字の commit の hash だけを通す
    （枝や短い hash は指す物が動く）。
    """
    path = root / "pack.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if not _has(data, key.split("."))]
    if missing:
        raise ValueError(f"{path} に鍵が無い: {', '.join(missing)}")
    commit = data["archon"]["commit"]
    if not isinstance(commit, str) or not FULL_SHA.fullmatch(commit):
        raise ValueError(f"{path} の archon.commit は 40 字の小文字の commit の hash でない: {commit!r}")
    return data


def _has(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return False
        data = data[key]
    return True
