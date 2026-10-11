"""版の止め pack.json を読む。Archon の版は ASF の取り付け命令が置いた factory/pack.json から読む。
中身の説明は docs/design.md の「pack.json」の節。"""
import json
import re
from pathlib import Path

REQUIRED = {
    "pack.json": ("ours.folder",),
    "factory/pack.json": ("repository", "integration_revision_required", "source_directory"),
}
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def load(root: Path) -> dict:
    """root/pack.json を読み、ASF の止めた Archon の源を archon.repo・archon.commit・asf.folder として足して返す。

    ASF の止め（root/factory/pack.json）が版の正本で、root/pack.json には Archon の版を書かない（持ち主の決め
    archon-same-as-asf。ASF が版を進めたら、ここも同じ版になる）。鍵が 1 つでも欠けたら、欠けた鍵を全部名指して ValueError。
    commit は取った源の置き場の名に使うので、40 字の小文字の commit の hash だけを通す（ASF の factory/consumer.py と同じ。
    枝や短い hash は指す物が動く）。
    """
    files = {rel: _read(root / rel) for rel in REQUIRED}
    missing = [f"{rel} の {key}" for rel, keys in REQUIRED.items() for key in keys if not _has(files[rel], key.split("."))]
    if missing:
        raise ValueError(f"{root} に鍵が無い: {', '.join(missing)}")
    data, asf = files["pack.json"], files["factory/pack.json"]
    commit = asf["integration_revision_required"]
    if not isinstance(commit, str) or not FULL_SHA.fullmatch(commit):
        raise ValueError(f"{root / 'factory/pack.json'} の integration_revision_required は 40 字の小文字の commit の hash でない: {commit!r}")
    data["archon"] = {"repo": asf["repository"], "commit": commit}
    data.setdefault("asf", {})["folder"] = asf["source_directory"]
    return data


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _has(data, keys):
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return False
        data = data[key]
    return True
