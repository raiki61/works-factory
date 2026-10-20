"""ブロックの時間の欄（壁時計の秒）。段 A・段 B の timing は stamp で書き、出口は wall で読んで足す。使い手は structure の
src/survey.py と structmark（README 9.3 の eye の時間の欄。integration.md 4.3-8・4.4-J）。構造の目の役の部分（前の prep・accept・
problems・ROUTES・VERDICTS など）は structure の src/eye.py に在る。

- WALL: 時間の欄の名（秒）
- stamp(doc, t0, **more): doc の timing に t0（time.monotonic）からの秒を WALL の欄で書く（more は timing に並べる欄）
- wall(doc): doc の timing（無ければ doc そのもの）の WALL の秒（無い・空なら 0）

標準ライブラリだけ。
"""
import time

WALL = "wall_s"   # ブロックの時間の欄の名（壁時計の秒。段 A・段 B の timing・目の控え・出口が同じ名で持つ）


def stamp(doc: dict, t0: float, **more) -> None:
    doc["timing"] = {**more, WALL: round(time.monotonic() - t0, 3)}


def wall(doc) -> float:
    if not isinstance(doc, dict):
        return 0
    t = doc.get("timing") if isinstance(doc.get("timing"), dict) else doc
    return t.get(WALL) or 0
