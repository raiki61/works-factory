"""版の止めの正本 pack.json を読む。中身の説明は docs/design.md の「pack.json」の節。"""
import json
from pathlib import Path

REQUIRED = (
    "archon.repo",
    "archon.release",
    "archon.assets",
    "asf.repo",
    "asf.commit",
    "asf.folder",
    "asf.placed_at",
    "ours.folder",
    "ours.placed_at",
)
PLACED_AT = ("ours.placed_at", "asf.placed_at")


def load(root: Path) -> dict:
    """root/pack.json を読む。配置に使う鍵が 1 つでも欠けたら、欠けた鍵を全部名指して ValueError。

    placed_at は place が中身ごと入れ替えるので、workflows/<名 1 つ> で互いに違う物だけを通す。
    そうでないと $ARCHON_HOME/workflows ごと（ほかの工程ごと）消える。
    """
    path = root / "pack.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if not _has(data, key.split("."))]
    if missing:
        raise ValueError(f"{path} に鍵が無い: {', '.join(missing)}")
    for key in PLACED_AT:
        if not _is_own_folder(_get(data, key)):
            raise ValueError(f"{path} の {key} は workflows/<名 1 つ> でない: {_get(data, key)!r}")
    if _get(data, PLACED_AT[0]) == _get(data, PLACED_AT[1]):
        raise ValueError(f"{path} の {' と '.join(PLACED_AT)} が同じ: {_get(data, PLACED_AT[0])!r}")
    return data


def _is_own_folder(value) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split("/")
    return len(parts) == 2 and parts[0] == "workflows" and parts[1] not in ("", ".", "..")


def _get(data, key):
    for part in key.split("."):
        data = data[part]
    return data


def _has(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return False
        data = data[key]
    return True
