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


def load(root: Path) -> dict:
    """root/pack.json を読む。配置に使う鍵が 1 つでも欠けたら、欠けた鍵を全部名指して ValueError"""
    path = root / "pack.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if not _has(data, key.split("."))]
    if missing:
        raise ValueError(f"{path} に鍵が無い: {', '.join(missing)}")
    return data


def _has(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return False
        data = data[key]
    return True
