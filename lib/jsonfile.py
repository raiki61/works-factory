"""JSON のファイルの読み書きの口。前は lib の多くのモジュールが同じ中身の写しを持っていた。振る舞いが同じ写しだけをここに寄せ、
振る舞いの違う読み書き（無い時は既定の値で壊れた時は拒む fixboard.read_json・judge_accept.read_json・rolekit・factchecks、
型も見る tddloop.load_json、詰めて書く impact）は持ち主のモジュールに名で残す。返答の足し欄の控えの読み書きと、欄の道を辿って外す口
（前の marks。integration.md 4.3-追加-2）もここに置く。控えのファイルの名と欄の道は使い手が自分の定数で持つ。

- read_or(path, default=None): JSON の値。無い・読めない・JSON でない時は default（拒まない）
- write(path, doc, *, indent=1, parents=False): 隣の一時のファイル <名>.tmp に書いて置き換える（読み手が書きかけを読まない。
  末尾に改行）。parents が真なら親のフォルダを作る（偽なら無い親は FileNotFoundError）。返りは書いたパス
- read_dict(path): JSON のオブジェクト。無い・読めない時は OSError、JSON でない・オブジェクトでない時は ValueError（拒む読み。前の
  startrec.load）
- dump(path, doc): 字下げ 1 で、一時のファイル <名>.tmp を消してから書いて置き換える（リンクは置き換え、先へ書かない）。返りは置いたバイト
- EACH・rows(doc, steps)・split(doc, steps, names): 欄の道（鍵の名か EACH＝並びの各行の並び）を辿る口。rows は欄を持つ行（写さずに
  その場の物）を道の形で返す。split は（names の欄を外した doc の写し, 外した欄）。外した欄は道の EACH の段だけ入れ子の並びで、葉は
  外した欄の dict。形の崩れた doc（dict でない・並びでない）でも落ちず、その所は空（{} か []）。doc は変えない

標準ライブラリだけ（lib のほかの物を import しない）。
"""
import copy
import json
import os
import pathlib

EACH = "[]"


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


def read_dict(path) -> dict:
    p = pathlib.Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{p} が JSON のオブジェクトでない")
    return doc


def dump(path, doc) -> bytes:
    p = pathlib.Path(path)
    raw = (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    tmp = p.with_name(p.name + ".tmp")
    tmp.unlink(missing_ok=True)
    tmp.write_bytes(raw)
    os.replace(tmp, p)
    return raw


def _walk(obj, steps, leaf):
    """道を辿り、行ごとに leaf(行) を呼んだ値を EACH の段だけ入れ子の並びで返す（並びでない所は []、dict でない所は None で辿る）"""
    if not steps:
        return leaf(obj)
    k, rest = steps[0], steps[1:]
    if k == EACH:
        return [_walk(x, rest, leaf) for x in obj] if isinstance(obj, list) else []
    return _walk(obj.get(k) if isinstance(obj, dict) else None, rest, leaf)


def rows(doc, steps):
    return _walk(doc, tuple(steps), lambda row: row)


def split(doc, steps, names) -> tuple:
    out = copy.deepcopy(doc)
    names = tuple(names)
    return out, _walk(out, tuple(steps), lambda row: {k: row.pop(k) for k in names if k in row} if isinstance(row, dict) else {})
