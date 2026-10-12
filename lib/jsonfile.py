"""JSON のファイルの読み書きの口。前は lib の多くのモジュールが同じ中身の写しを持っていた。振る舞いが同じ写しだけをここに寄せ、
振る舞いの違う読み書き（無い時は既定の値で壊れた時は拒む fixboard.read_json・judge_accept.read_json・rolekit・factchecks、
型も見る tddloop.load_json、詰めて書く impact、控えの書き方の marks.write）は持ち主のモジュールに名で残す。

- read_or(path, default=None): JSON の値。無い・読めない・JSON でない時は default（拒まない）
- write(path, doc, *, indent=1, parents=False): 隣の一時のファイル <名>.tmp に書いて置き換える（読み手が書きかけを読まない。
  末尾に改行）。parents が真なら親のフォルダを作る（偽なら無い親は FileNotFoundError）。返りは書いたパス

標準ライブラリだけ（lib のほかの物を import しない）。
"""
import json
import os
import pathlib


def read_or(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(path, doc, *, indent: int = 1, parents: bool = False) -> pathlib.Path:
    path = pathlib.Path(path)
    if parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path
