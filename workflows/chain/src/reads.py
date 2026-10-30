"""script が Archon から受けた入力の字を値に戻す読み（workflows/.shared/boundary.py の text・value・items と埋め skip_value の後継の
うち、ports に無い部分）。飛ばされた節の出力は字の "null" か空の字で届く。"""
import os
import re
import subprocess
from pathlib import Path

import ports

SKIPPED = "null"
DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>（round-k-decide の出力）。周の数はグラフの with: が持つ


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


def decisions() -> list:
    """周の決めの入力 d<k> を周の番号の順に値で読む（final-diff と result が読む）。飛ばされた周（null）と dict でない物は外す"""
    names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
    return [d for d in (value(os.environ[name]) for name in names) if isinstance(d, dict)]


def work_tree() -> Path:
    """run の作業ツリーの根（script の node は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(top.stdout.strip())


def head() -> str:
    """作業ツリーの今の HEAD。commit の無い木なら空"""
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip() if done.returncode == 0 else ""
