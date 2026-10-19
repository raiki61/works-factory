"""引き継ぎのメモ（考え handoff）の住処: 役が次の周の自分へ書くメモの型と控えの書き読み。

役は周ごとに新しい会話で起きて、前の周で読んだ所も考えも持たない。そこで役の返答に、本文・案とは別の欄 handoff を持たせ、
受け付けが外して周のフォルダに置き（控えの名は FILE）、次の周の材料が前の周のメモをパスで名指す。メモを書けという頼みと前の周の
節の文は共通の断片 blocks/.shared/prompts/handoff.md に在る（integration.md 4.3-追加-1）。

- FIELD・KEYS・SCHEMA: 返答の欄の名・4 つの欄（read・kept・set_aside・open）・欄の型
- FILE・path_of(board)・save(board, note): 控えの名・周のフォルダ board の控えのパス・控えを置く（空なら前の控えを消す）
- unreadable(rounds): 在るのに読めない控えのパスの並び
"""
from __future__ import annotations

import pathlib
import sys

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import jsonfile  # noqa: E402

FIELD = "handoff"
FILE = "handoff.json"
KEYS = ("read", "kept", "set_aside", "open")
_TEXT = {"type": "string", "minLength": 1}
SCHEMA = {"type": "object", "additionalProperties": False, "required": list(KEYS),
          "properties": {
              "read": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["path", "lines", "why"],
                  "properties": {"path": _TEXT, "lines": _TEXT, "why": _TEXT}}},
              "kept": {"type": "array", "items": _TEXT},
              "set_aside": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["option", "why"],
                  "properties": {"option": _TEXT, "why": _TEXT}}},
              "open": {"type": "array", "items": _TEXT}}}


def path_of(board) -> pathlib.Path:
    """周のフォルダ board の引き継ぎのメモの控えのパス"""
    return pathlib.Path(board) / FILE


def save(board, note) -> None:
    """周のフォルダ board にメモ note を置く。note が空でない時だけ、無い周のフォルダも作ってから置く。空なら前から残る控えを消すだけで、
    フォルダは作らない（メモの無い周に空のフォルダを残さない）。置けなければ OSError をそのまま上げる"""
    path = path_of(board)
    if note:
        path.parent.mkdir(parents=True, exist_ok=True)
        jsonfile.dump(path, note)
    else:
        path.unlink(missing_ok=True)


def unreadable(rounds) -> list:
    """周のフォルダの並び rounds のうち、控えが在るのに読めない（JSON でない・オブジェクトでない）周の控えのパスの並び（並びの順）。
    控えの無い周は数えない"""
    out = []
    for board in rounds:
        path = path_of(board)
        if path.exists() and not isinstance(jsonfile.read_or(path), dict):
            out.append(path)
    return out
