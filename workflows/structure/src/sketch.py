"""構造を描く役（system-sketch）と一般の構造を描く目（general-structure）の node の中身（docs/design/structure.md の 2.7・2.8 節）。

before の時だけ、構造の目の前に 2 つの役を回す。構造を描く役は Read・Grep・Glob で単位の周りを読み、触る部品を含むシステムを
部品・流れ・正本・依存の向き・境目で描き（system）、どんな種類のシステムで触る部品が何を揃えたいかを 1 文で言う（kind）。
一般の構造を描く目は道具を持たず、番号つきの kind の文だけを受けて、その種類のシステムの一般の構造を理由つきで描く。頼み・単位・
差分・対象の名を運ぶ値を持たない形で独立を守る（受け付けが、kind の文に単位の id とパスとファイルの名〔拡張子を外した名とパスの各段も〕が無いことを照らす）。
受け付けた行は sketches.json・general.json に書き、構造の目が単位ごとに system・kind・general を並べて見る（eye.shown）。
指示の文は prompts/system-sketch.md・prompts/general-structure.md（と .system.md）が持ち、ここは材料と値と照らしだけを持つ。
"""
from __future__ import annotations

import json
import pathlib
import re

import ports  # noqa: F401  （lib/ を読めるようにする）
import prompt

import jsonfile   # lib/
import rolekit    # lib/。拒否の控えと輪の回の数え

from src import files


def _rows_of(out, name: str) -> list:
    got = jsonfile.read_or(pathlib.Path(out) / name, [])
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


def units(out) -> list:
    """描く単位 [{id, paths, summary}]: 構造の目が見る単位（view.json）の順で、paths は units.json から"""
    out = pathlib.Path(out)
    view = jsonfile.read_or(out / files.VIEW_FILE)
    if not isinstance(view, dict):
        raise ValueError(f"{out / files.VIEW_FILE} が無いか読めない（measure が走っていない）")
    paths = {u.get("id"): u.get("paths") or [] for u in _rows_of(out, files.UNITS_FILE)}
    return [{"id": u["id"], "paths": paths.get(u["id"], []), "summary": u.get("summary", "")} for u in view.get("units") or []]


def sketches(out) -> list:
    return _rows_of(out, files.SKETCH_FILE)


def generals(out) -> list:
    return _rows_of(out, files.GENERAL_FILE)


def _emit(out, name: str, values: dict, when: dict) -> dict:
    rejects = rolekit.rejected(pathlib.Path(out), name)
    n = len(rejects) + 1
    got = prompt.emit(name, {"rejection": rolekit.rejects_text(rejects), **values}, {"rejected": bool(rejects), **when}, n)
    return {**got, "attempt": n}


def sketch_prompt(out, lang="") -> dict:
    """構造を描く役の指示を組んで place に書く。返り {prompt, attempt}"""
    shown = units(out)
    got = _emit(out, files.SKETCH, {"units": json.dumps(shown, ensure_ascii=False, separators=(",", ":")), "lang": prompt.lang(lang)}, {})
    return {"prompt": got["prompt"], "attempt": got["attempt"]}


def _blank(v) -> bool:
    return not isinstance(v, str) or not v.strip()


def _names(shown: list) -> list:
    """kind の文に在ってはいけない字: 単位の id・パス・ファイルの名・拡張子を外したファイルの名・パスの各段"""
    out = []
    for u in shown:
        out.append(u["id"])
        for p in u["paths"]:
            path = pathlib.PurePosixPath(p)
            out += [p, path.name, path.stem, *path.parts]
    return sorted({n for n in out if isinstance(n, str) and n.strip()}, key=len, reverse=True)


def _named(name: str, text: str) -> bool:
    """text が name を英数字の続きでない所に持つ（大文字小文字を見ない。chart は charts の中では数えない）"""
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


def _one_to_one(rows, want: list, key: str, what: str) -> list:
    if not isinstance(rows, list):
        return ["返答に rows（行の配列）が無い"]
    out, seen = [], []
    for i, r in enumerate(rows):
        got = r.get(key) if isinstance(r, dict) else None
        if got not in want:
            out.append(f"行 {i}: {key} {got!r} が{what}に無い（在るのは {want}）")
        elif got in seen:
            out.append(f"行 {i}: {key} {got!r} の 2 行目")
        seen.append(got)
    missing = [w for w in want if w not in seen]
    if missing:
        out.append(f"行の無い{what}: {missing}")
    return out


def sketch_problems(shown: list, reply) -> list:
    """構造を描く役の返答の外れ（空なら通る）。単位と 1 対 1・system と kind が空でない・kind に単位の id とパスとファイルの名（拡張子を外した名とパスの各段も）が無い"""
    rows = reply.get("rows") if isinstance(reply, dict) else None
    out = _one_to_one(rows, [u["id"] for u in shown], "unit_id", "単位")
    if not isinstance(rows, list):
        return out
    names = _names(shown)
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        head = f"行 {i}（{r.get('unit_id')}）"
        for key in ("system", "kind"):
            if _blank(r.get(key)):
                out.append(f"{head}: {key} が空")
        kind = r.get("kind") if isinstance(r.get("kind"), str) else ""
        hit = [n for n in names if _named(n, kind)]
        if hit:
            out.append(f"{head}: kind が対象の名を持つ（{hit[0]!r}。kind は対象を知らない目に渡すので、単位の id・パス・ファイルの名・フォルダの名を書かない）")
    return out


def _accept(out, name: str, reply, bad, write) -> dict:
    """受け付けの輪の 1 回。bad(reply) が空なら write(reply) で控えを書く。3 回目の拒否で done・give_up。返り {ok, done, give_up, reason, attempt}"""
    out = pathlib.Path(out)
    attempt, stopped = rolekit.current_round(out, name)

    def take(_):
        got = bad(reply)
        return {"ok": False, "reason": " / ".join(got)} if got else {"ok": True, "reason": ""}
    got = rolekit.round_outcome(stopped or rolekit.accept_round(out, name, None, take))
    if got["ok"]:
        write(reply)
        return {"ok": True, "done": True, "give_up": False, "reason": "", "attempt": attempt}
    return {**got, "attempt": attempt}


def sketch_accept(out, reply) -> dict:
    """構造を描く役の返答の受け付け。通れば sketches.json に単位の順で書く"""
    out = pathlib.Path(out)
    shown = units(out)

    def write(r):
        by = {row["unit_id"]: row for row in r["rows"]}
        jsonfile.write(out / files.SKETCH_FILE, [{"unit_id": u["id"], "system": by[u["id"]]["system"].strip(),
                                                  "kind": by[u["id"]]["kind"].strip()} for u in shown])
    return _accept(out, files.SKETCH, reply, lambda r: sketch_problems(shown, r), write)


def sketched(out) -> dict:
    """一般の構造を描く目を起こすか: 構造を描く役の行が受け付けられている。返り {general, reason}"""
    got = sketches(out)
    return {"general": bool(got), "reason": "" if got else "構造を描く役の行が無い（役が走らなかったか、3 回とも拒まれた）"}


def general_prompt(out, lang="") -> dict:
    """一般の構造を描く目の指示と system prompt を組んで place に書く。見せるのは番号つきの kind の文だけ。返り {prompt, system, attempt}"""
    rows = sketches(out)
    if not rows:
        raise ValueError(f"{pathlib.Path(out) / files.SKETCH_FILE} に行が無い（構造を描く役の行が受け付けられていない）")
    kinds = "\n".join(f"{i}. {r['kind']}" for i, r in enumerate(rows, 1))
    got = _emit(out, files.GENERAL, {"kinds": kinds, "lang": prompt.lang(lang)}, {})
    return {"prompt": got["prompt"], "system": got["system"], "attempt": got["attempt"]}


def general_problems(count: int, reply) -> list:
    """一般の構造を描く目の返答の外れ（空なら通る）。番号と 1 対 1・structure と why が空でない"""
    rows = reply.get("rows") if isinstance(reply, dict) else None
    out = _one_to_one(rows, list(range(1, count + 1)), "index", "番号")
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        for key in ("structure", "why"):
            if isinstance(r, dict) and _blank(r.get(key)):
                out.append(f"行 {i}（{r.get('index')}）: {key} が空")
    return out


def general_accept(out, reply) -> dict:
    """一般の構造を描く目の返答の受け付け。通れば general.json に、番号を単位に戻して書く"""
    out = pathlib.Path(out)
    rows = sketches(out)

    def write(r):
        by = {row["index"]: row for row in r["rows"]}
        jsonfile.write(out / files.GENERAL_FILE, [{"unit_id": s["unit_id"], "kind": s["kind"], "structure": by[i]["structure"].strip(),
                                                   "why": by[i]["why"].strip()} for i, s in enumerate(rows, 1)])
    return _accept(out, files.GENERAL, reply, lambda r: general_problems(len(rows), r), write)
