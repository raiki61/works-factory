"""script が Archon から受けた入力の字を値に戻す読み（workflows/.shared/boundary.py の text・value・items と埋め skip_value の後継の
うち、ports に無い部分）。飛ばされた節の出力は字の "null" か空の字で届く。"""
import subprocess
from pathlib import Path

import ports

SKIPPED = "null"


def text(raw) -> str:
    """字の入力。飛ばされた節（null）と無い入力は空の字"""
    return "" if raw is None or raw == SKIPPED else ports.text(raw)


def value(raw):
    """JSON の値。null・空の字・無い入力は None。JSON でなければ字のまま（字の欄 r2_status など）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw


def items(raw) -> list:
    got = value(raw)
    return got if isinstance(got, list) else []


def work_tree() -> Path:
    """run の作業ツリーの根（script の node は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(top.stdout.strip())


def head() -> str:
    """作業ツリーの今の HEAD。commit の無い木なら空"""
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip() if done.returncode == 0 else ""
