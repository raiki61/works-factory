"""run の置き場の中の報告の置き場と、そこのパスの指し札（facts.py・report_accept.py・collect.py が import する部品。節の script でない）。
三つの script が同じ置き場を読み書きして、AI の報告を受け渡す。"""
import os
from pathlib import Path

import boundary

OUT = "report"


def out_dir() -> Path:
    """報告の置き場（run の置き場の OUT）"""
    return Path(os.environ["ARTIFACTS_DIR"]) / OUT


def rel(path) -> dict | None:
    """置き場の中のパスを、置き場からの相対の指し札に（None は None）"""
    if path is None:
        return None
    return boundary.pointer(Path(path).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix())
