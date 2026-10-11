"""run の置き場の中のパスを指し札にする部品。節の script でなく、facts.py・collect.py が import する。"""
import os
from pathlib import Path

import boundary


def rel(path) -> dict | None:
    """置き場の中のパスを、置き場からの相対の指し札に（None は None）"""
    if path is None:
        return None
    return boundary.pointer(Path(path).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix())
