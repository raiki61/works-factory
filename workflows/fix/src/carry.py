"""次の修正の段への申し送り carry.json（docs/design/fix.md の 1.4）。

形 {conflicts: <conflicts.json の中身か null>, loops: [{record: <tdd-<k>/record.json の中身>, summary: <summary.md の字か "">}],
accept: <accept.json の中身か null>, bases: [{base: <bases/<k>/base.json の中身か null>, accept: <bases/<k>/accept.json の中身か null>}],
returns: [<returns/<k>.json の中身>]}（この段の place の全部の輪・元の結末の写し・返しの控え。子から写した物を含む。accept・bases・
returns は下書き docs/plans/2026-10-24-fix-weapons.md の 2.1 の「2 回目の block の置き場へ写す」道）。2 回目の段の prep は port prior でこの束だけを受け、place の prior/ に
置き直してから、今の adopt_prior_pass と同じ写しをする（今は前の段の place のフォルダを名で開いていた）。
"""
from __future__ import annotations

import json
import pathlib

from src import files

LOOP_DIR = "tdd-{k}"   # 置き直す輪のフォルダ（common.records が tdd-<k>/record.json を番号の順に読む）
SUMMARY = "summary.md"


def write(place) -> pathlib.Path | None:
    """place の申し出と輪の状態を carry.json に束ねて書き、パスを返す。どちらも無ければ書かずに None"""
    import conflict
    from src import common
    place = pathlib.Path(place)
    conflicts = None
    if (place / conflict.FILE).is_file():
        conflicts = json.loads((place / conflict.FILE).read_text(encoding="utf-8"))
    loops = []
    for record in common.records(place):
        summary = record.parent / SUMMARY
        loops.append({"record": json.loads(record.read_text(encoding="utf-8")),
                      "summary": summary.read_text(encoding="utf-8") if summary.is_file() else ""})
    from src import board
    accept = _read(place / files.ACCEPT_FILE)
    bases = [{"base": _read(d / files.BASE_FILE), "accept": _read(d / files.ACCEPT_FILE)} for d in board.base_dirs(place)]
    rets = place / files.RETURNS_DIR
    returns = [_read(p) for p in sorted(rets.glob("*.json"), key=lambda q: (len(q.stem), q.stem))] if rets.is_dir() else []
    if conflicts is None and not loops and accept is None and not bases and not returns:
        return None
    path = place / files.CARRY_FILE
    path.write_text(json.dumps({"conflicts": conflicts, "loops": loops, "accept": accept, "bases": bases, "returns": returns},
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def _read(path: pathlib.Path):
    """JSON のファイルの中身（無ければ None）"""
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _put(path: pathlib.Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def place_prior(place, prior: dict) -> pathlib.Path:
    """束 prior を place の prior/ に置き直し（conflicts.json と tdd-<k>/record.json・summary.md、accept.json・bases/<k>/・returns/<k>.json）、そのフォルダを返す"""
    import conflict
    from src import tdd
    root = pathlib.Path(place) / files.PRIOR_DIR
    root.mkdir(parents=True, exist_ok=True)
    if isinstance(prior.get("conflicts"), dict):
        (root / conflict.FILE).write_text(json.dumps(prior["conflicts"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, loop in enumerate(prior.get("loops") or [], 1):
        if not isinstance(loop, dict) or not isinstance(loop.get("record"), dict):
            raise ValueError(f"入力 prior の loops[{k - 1}] に record が無い")
        d = root / LOOP_DIR.format(k=k)
        d.mkdir(parents=True, exist_ok=True)
        (d / tdd.RECORD).write_text(json.dumps(loop["record"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if loop.get("summary"):
            (d / SUMMARY).write_text(str(loop["summary"]), encoding="utf-8")
    if isinstance(prior.get("accept"), dict):
        _put(root / files.ACCEPT_FILE, prior["accept"])
    for k, b in enumerate(prior.get("bases") or [], 1):
        if not isinstance(b, dict):
            raise ValueError(f"入力 prior の bases[{k - 1}] が object でない")
        for name, key in ((files.BASE_FILE, "base"), (files.ACCEPT_FILE, "accept")):
            if isinstance(b.get(key), dict):
                _put(root / files.BASES_DIR / str(k) / name, b[key])
    for k, ret in enumerate(prior.get("returns") or [], 1):
        if not isinstance(ret, dict):
            raise ValueError(f"入力 prior の returns[{k - 1}] が object でない")
        _put(root / files.RETURNS_DIR / f"{k}.json", ret)
    return root


def adopt(place, prior: dict, only_items, repo) -> dict:
    """束 prior を置き直し、1 回目の段の申し出と裁定と輪の状態・元の結末・返しの控えを今の段の place に写す（board.adopt_prior_pass）"""
    from src import board
    if not isinstance(prior, dict):
        raise ValueError("入力 prior が object でない")
    return board.adopt_prior_pass(place, place_prior(place, prior), only_items, repo)
