"""出力 report と freeze_off の行（docs/design/fix.md の 11 節）。どれも今の lib が組む日本語の字のまま。"""
from __future__ import annotations

import pathlib

import oneline   # lib/
import reads     # lib/
import report    # lib/

NO_TDD = "組の TDD の記録が無い。修正の出力の単位の行で出す:"   # 今の runreport._tdd_lines の代わりの行（成果物の名を持たない字）


def stages(tdd_rows: list) -> list:
    """report.tdd_lines・freeze_lines に渡す [(組の名, 組の TDD の記録)]"""
    return [(f"組 {g.get('group_id')}", g) for g in tdd_rows if isinstance(g, dict)]


def tdd_lines(tdd_rows: list, units: list) -> list:
    got = stages(tdd_rows)
    if got:
        return report.tdd_lines(got)
    rows = [u for u in units or [] if isinstance(u, dict)]
    if not rows:
        return []
    return [NO_TDD, *(f"  - {u.get('unit_id')}: {u.get('status')}（{oneline.one_line(u.get('reason') or '理由なし')}）" for u in rows)]


def freeze_off(tdd_rows: list) -> list:
    return report.freeze_lines(stages(tdd_rows))


def _shown(path: str, repo) -> str:
    if repo:
        try:
            return pathlib.Path(path).relative_to(pathlib.Path(repo)).as_posix()
        except ValueError:
            pass
    return path


def evidence_lines(place, repo=None) -> list:
    """読んだ証拠の索引と役ごとの証拠の 1 行（今の runreport._index_lines・_evidence_line と同じ字。rel は place からの相対）"""
    place = pathlib.Path(place)
    out = []
    for p in sorted(place.glob(reads.EVIDENCE_GLOB)):
        rel = p.relative_to(place).as_posix()
        if reads.is_index(p.name):
            why = reads.index_why(p)
            if why:
                out.append(f"{rel}: {oneline.one_line(why)}")
            continue
        doc, why = reads.read_evidence(p)
        if doc is None:
            out.append(f"{rel}: 読めない（{why}）")
        elif doc["sources"].get("hook") == reads.FAILED:
            out.append(f"{doc['role']}（{rel}）: 読んだ証拠のノードが落ちた（{doc['sources'].get('why') or '訳の記録が無い'}）")
        elif doc["sources"].get("hook") != reads.RECORDED:
            out.append(f"{doc['role']}（{rel}）: 測れない（{doc['sources'].get('why') or '訳の記録が無い'}）")
        else:
            missing = [str(m) for m in doc["missing"]]
            out.append(f"{doc['role']}（{rel}）: 渡した {len(doc['rows'])}・読んだ跡の無い {len(missing)}"
                       + (f"（{'・'.join(_shown(m, repo) for m in missing)}）" if missing else ""))
    return out


def lines(place, tdd_rows: list, units: list, repo=None) -> list:
    return [*tdd_lines(tdd_rows, units), *evidence_lines(place, repo)]
