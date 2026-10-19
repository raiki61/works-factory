"""次の修正の段への申し送り carry.json（docs/design/fix.md の 1.4）。

形 {conflicts: <conflicts.json の中身か null>, loops: [{state: <tdd-<k>/state.json の中身>, summary: <summary.md の字か "">}]}
（この段の place の全部の輪。子から写した物を含む）。2 回目の段の prep は port prior でこの束だけを受け、place の prior/ に
置き直してから、今の adopt_prior_pass と同じ写しをする（今は前の段の place のフォルダを名で開いていた）。
"""
from __future__ import annotations

import json
import pathlib

from src import files

LOOP_DIR = "tdd-{k}"   # 置き直す輪のフォルダ（lib の tddloop.states が tdd-<k>/state.json を番号の順に読む）
SUMMARY = "summary.md"


def write(place) -> pathlib.Path | None:
    """place の申し出と輪の状態を carry.json に束ねて書き、パスを返す。どちらも無ければ書かずに None"""
    import conflict
    from src import tdd
    place = pathlib.Path(place)
    conflicts = None
    if (place / conflict.FILE).is_file():
        conflicts = json.loads((place / conflict.FILE).read_text(encoding="utf-8"))
    loops = []
    for state in tdd.states(place):
        summary = state.parent / SUMMARY
        loops.append({"state": json.loads(state.read_text(encoding="utf-8")),
                      "summary": summary.read_text(encoding="utf-8") if summary.is_file() else ""})
    if conflicts is None and not loops:
        return None
    path = place / files.CARRY_FILE
    path.write_text(json.dumps({"conflicts": conflicts, "loops": loops}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def place_prior(place, prior: dict) -> pathlib.Path:
    """束 prior を place の prior/ に置き直し（conflicts.json と tdd-<k>/state.json・summary.md）、そのフォルダを返す"""
    import conflict
    from src import tdd
    root = pathlib.Path(place) / files.PRIOR_DIR
    root.mkdir(parents=True, exist_ok=True)
    if isinstance(prior.get("conflicts"), dict):
        (root / conflict.FILE).write_text(json.dumps(prior["conflicts"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, loop in enumerate(prior.get("loops") or [], 1):
        if not isinstance(loop, dict) or not isinstance(loop.get("state"), dict):
            raise ValueError(f"入力 prior の loops[{k - 1}] に state が無い")
        d = root / LOOP_DIR.format(k=k)
        d.mkdir(parents=True, exist_ok=True)
        (d / tdd.STATE).write_text(json.dumps(loop["state"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if loop.get("summary"):
            (d / SUMMARY).write_text(str(loop["summary"]), encoding="utf-8")
    return root


def adopt(place, prior: dict, only_items, repo) -> dict:
    """束 prior を置き直し、1 回目の段の申し出と裁定と輪の状態を今の段の place に写す（board.adopt_prior_pass。今のまま）"""
    from src import board
    if not isinstance(prior, dict):
        raise ValueError("入力 prior が object でない")
    return board.adopt_prior_pass(place, place_prior(place, prior), only_items, repo)
