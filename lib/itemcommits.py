"""修正案の項目ごとの commit の決め（出口の語 pr の run が、照らした差分を項目〔1 つの論理の変更〕ごとの commit に積むための記録と分け方）。

記録は修正の段ごとに 1 つ {"items": [{item, unit_keys, approach, after}] か null, "claims": [{unit_key, files}], "unread": [訳]}:
items は承認済みの修正案の項目（planmarks.approved_items の形。修正案の無い run は null）で、after はその項目の depends_on が指す前の
項目の番号（planmarks.depends_pairs の単位の対を項目に戻した物）。claims は単位ごとの触ったファイル（受け付けた修正役の返答の
changes[].files と、TDD の輪の単位の test_files）。unread は記録を組めなかった訳。

- record(items, replies, tdd_units, root, unread=()): 1 つの修正の段の記録（files はリポジトリの根 root からの相対に揃える）
- merged(records): 段の記録（1 回目・2 度目の修正の順。None は走らなかった段）を合わせる。項目は後の段の物（案の直しの後は直した
  案）、claims と unread は和。どの段も無ければ None
- declared_files(rows, repo): changes の行の files を、リポジトリの根からの相対パスに揃えた集合（前は factchecks。修正の受け付けと
  この記録が同じ規則で揃えるための 1 か所。fix の src/facts.py もここを呼ぶ。integration.md 4.3-2）
- split(record, paths): 差分のパス paths を項目ごとの Part の並びに分ける。並びは依存の位相順（依存の無い物どうしは項目の番号の順）
  で、パスの無い項目は載せない。分けられなければ ([], 訳): 記録が無い・読めない、どの項目も申告していないパスか複数の項目が
  触ったパスが在る（1 つの commit に倒す）
"""
from __future__ import annotations

import graphlib
import os
import posixpath
from typing import NamedTuple

import planmarks

SHOWN = 5   # 訳に名指すパスの数（残りは件数）


class Part(NamedTuple):
    item: int
    approach: str
    after: list    # この項目が依存する前の項目のうち commit の在る物の番号（積む並びでは前に在る）
    paths: list    # この項目の commit に積むパス


def record(items, replies, tdd_units, root, unread=()) -> dict:
    """1 つの修正の段の記録（頭の注記）。replies は受け付けた修正役の返答（dict の並び）、tdd_units は TDD の輪の単位の行"""
    claims = [{"unit_key": c["unit_key"], "files": _files(c.get("files"), root)}
              for reply in replies or [] if isinstance(reply, dict)
              for c in reply.get("changes") or [] if isinstance(c, dict) and isinstance(c.get("unit_key"), str)]
    claims += [{"unit_key": u["unit_key"], "files": _files(u.get("test_files"), root)}
               for u in tdd_units or [] if isinstance(u, dict) and isinstance(u.get("unit_key"), str)]
    return {"items": None if items is None else _item_rows(items), "claims": claims, "unread": list(unread)}


def declared_files(rows, repo) -> set:
    """changes の行の files を、リポジトリの根からの相対パスに揃えた集合。絶対パスは、親のフォルダと根のリンク（macOS の /var と
    /private/var など）を解いてから比べる（ファイルそのもののリンクは解かない）"""
    out, root = set(), os.path.realpath(repo)
    for c in rows:
        for f in c.get("files") or []:
            if isinstance(f, str) and f.strip():
                f = f.strip()
                if os.path.isabs(f):
                    f = os.path.relpath(os.path.join(os.path.realpath(os.path.dirname(f)), os.path.basename(f)), root)
                out.add(posixpath.normpath(f))
    return out


def _files(files, root) -> list:
    # 受け付け（fix の範囲の照らし）が返答の files を読んだのと同じ規則で揃える
    return sorted(declared_files([{"files": files if isinstance(files, list) else []}], root))


def _item_rows(items) -> list:
    items = [it for it in items if isinstance(it, dict) and isinstance(it.get("item"), int)]
    owner = {k: it["item"] for it in items for k in it.get("unit_keys") or [] if isinstance(k, str)}
    after: dict = {it["item"]: set() for it in items}
    for a, b in planmarks.depends_pairs(items):
        if owner.get(a) is not None and owner.get(b) is not None and owner[a] != owner[b]:
            after[owner[b]].add(owner[a])
    return [{"item": it["item"], "unit_keys": [k for k in it.get("unit_keys") or [] if isinstance(k, str)],
             "approach": str(it.get("approach") or ""), "after": sorted(after[it["item"]])} for it in items]


def merged(records) -> dict | None:
    """段の記録を合わせる（頭の注記）"""
    got = [r for r in records or [] if isinstance(r, dict)]
    if not got:
        return None
    items = next((r["items"] for r in reversed(got) if r.get("items") is not None), None)
    return {"items": items, "claims": [c for r in got for c in r.get("claims") or []],
            "unread": [w for r in got for w in r.get("unread") or []]}


def split(record, paths) -> tuple[list[Part], str]:
    """差分のパス paths を項目ごとに分ける（頭の注記）"""
    if not isinstance(record, dict) or not isinstance(record.get("items"), list):
        return [], "修正案の項目の記録が無い（修正案の無い run か、修正の段の記録が渡されていない）"
    if record.get("unread"):
        return [], f"修正の段の記録を読めない: {'；'.join(map(str, record['unread']))}"
    items = {it["item"]: it for it in record["items"]}
    of_unit: dict = {}
    for it in record["items"]:
        for k in it["unit_keys"]:
            of_unit.setdefault(k, set()).add(it["item"])
    owners: dict = {}
    for c in record.get("claims") or []:
        for f in c["files"]:
            owners.setdefault(f, set()).update(of_unit.get(c["unit_key"]) or {None})
    unclaimed = [p for p in paths if not owners.get(p)]
    shared = [p for p in paths if len(owners.get(p) or ()) > 1 or None in (owners.get(p) or ())]
    if unclaimed or shared:
        return [], "差分のパスを 1 つの項目に決められない（" + "／".join(
            [*([f"どの項目も申告していない: {_named(unclaimed)}"] if unclaimed else []),
             *([f"複数の項目か項目の外の単位が触った: {_named(shared)}"] if shared else [])]) + "）"
    by_item: dict = {}
    for p in paths:
        by_item.setdefault(next(iter(owners[p])), []).append(p)
    try:
        order = _ordered(items)
    except graphlib.CycleError:
        return [], "修正案の項目の依存が循環している"
    return [Part(n, items[n]["approach"], [m for m in items[n]["after"] if m in by_item], by_item[n])
            for n in order if n in by_item], ""


def _named(paths) -> str:
    rest = len(paths) - SHOWN
    return "・".join(paths[:SHOWN]) + (f" ほか {rest} 件" if rest > 0 else "")


def _ordered(items: dict) -> list:
    sorter = graphlib.TopologicalSorter({n: [m for m in it["after"] if m in items] for n, it in items.items()})
    sorter.prepare()
    order = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order += ready
        sorter.done(*ready)
    return order
