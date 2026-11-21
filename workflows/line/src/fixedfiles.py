"""修正の段の合わせ fixed の返りの伸びる欄を place のファイルに置く書き口 stored と、読む口 opened・value（docs/design/line.md の 4.3）。

fixed の返りの段の返り stages・単位 units・止めの訳 stop_why・差分のパスを修正案の項目に決める記録 item_claims は、直しの単位の数だけ伸びる
（直しの単位が多い run で返り全体が 148KB）。Archon は script の入力を 1 本ずつ環境変数で渡し、Linux では 1 本が 128KB を越えると起動が
E2BIG で落ちるので、返りをまるごと結ぶ読み手（ask-final・back-k・collect）が落ちた。伸びる欄は値で返さず、place の fixed/<k>/ に書いて
そのファイルを指す pointer を返す（試験の関所の test_outcomes と同じ形。k は返した段の数で、fixed は 0、back-k-fixed は k。周ごとに別の
ファイルなので、返す前の状態を封じる周が前の周の pointer を運んでも、指す先は書き換わらない）。空の値（空の配列・null・空の字）は書かずに null。

- GROWN: 伸びる欄の名 → ファイルの名（form は欄ごとに _pointer・value が字で持つ。output_format の description と同じ字）
- stored(out, place) -> 伸びる欄を書いて pointer に替えた返り（fixed の script が返す前に通す）
- value(fixed, name) -> 欄 1 つの中身（pointer なら先を form で照らして読み、null は空の値。値のままの欄は形で照らして返す）。
  読めない・形に合わない先は ValueError
- opened(fixed) -> 伸びる欄を全部中身に替えた写し（読み手が合わせの返りを src に渡す前に通す。dict でなければそのまま）
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import ports

GROWN = {"stages": "stages.json", "units": "units.json", "item_claims": "items.json", "stop_why": "stop-why.txt"}


def _blank(name: str):
    return None if name in ("item_claims",) else "" if name == "stop_why" else []


def _pointer(name: str, path: Path) -> dict:
    """書いたファイルを、欄の form（output_format の description と同じ字）で照らして指す"""
    if name == "stages":
        return ports.pointer(path, "json(stages.schema.json)")
    if name == "units":
        return ports.pointer(path, "json(shared:fixes.schema.json)")
    if name == "item_claims":
        return ports.pointer(path, "json(shared:item-claims.schema.json)")
    return ports.pointer(path, "file")


def stored(out: dict, place) -> dict:
    from src import files, stages
    folder = Path(place) / files.FIXED_FILES.format(k=len(out.get(stages.MORE) or []))
    got = dict(out)
    for name, file_name in GROWN.items():
        if got.get(name) is None or got[name] == _blank(name):
            got[name] = None
            continue
        path = folder / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got[name] if name == "stop_why" else json.dumps(got[name], ensure_ascii=False), encoding="utf-8")
        got[name] = _pointer(name, path)
    return got


def value(fixed: dict, name: str):
    got = fixed.get(name)
    if got is None:
        return copy.deepcopy(_blank(name))
    raw = json.dumps(got, ensure_ascii=False)
    if name == "stop_why":
        return got if isinstance(got, str) else ports.file(raw, "file").read_text(encoding="utf-8")
    if name == "stages":
        return ports.json(raw, "stages.schema.json")
    if name == "units":
        return ports.json(raw, "shared:fixes.schema.json")
    if name == "item_claims":
        return ports.json(raw, "shared:item-claims.schema.json")
    raise KeyError(f"伸びる欄でない名 {name!r}（GROWN: {', '.join(GROWN)}）")


def opened(fixed):
    if not isinstance(fixed, dict):
        return fixed
    return {**fixed, **{name: value(fixed, name) for name in GROWN if name in fixed}}
