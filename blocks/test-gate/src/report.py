"""報告に載せる日本語の行（出力の欄 report。docs/design/test-gate.md の 10 節）。

今の lib/runreport.py が試験の関門の返りから組む行（_base_word・_evidence_lines・_green_lines・_tests_head_lines）を、この block の返りの値
だけで組む。字は今と同じ。line の中の名（node の id）は block が知らないので、行の頭の札は外す。どの行を報告のどの節に載せるかは
この後の段が決め、ここは行を返すだけ。出力の node の中の誤り（by が空）は、試験が走らなかったとは言わず、誤りの 1 行だけを返す。
"""
from __future__ import annotations

import pathlib

import baseline_red     # lib/
import declared_checks  # lib/
import gatemarks        # lib/
import green_cert       # lib/
import oneline          # lib/

from src import files

RED_KEPT = (green_cert.INHERITED, green_cert.ENVIRONMENT)   # 認証が通した赤（元から赤・環境の赤）


def lines(mode: str, out: dict, place) -> list:
    """block の返り out（report 以外の欄）から、報告の行の並び（by が空の誤りの回は certify.failed が 1 行だけ返す）"""
    v = declared_checks.gate_values(out)
    if mode == "base":
        rows = [f"直す前のテスト: {_base_word(out, place)}",
                f"直す前のテストの走らせ方: {v['suites']}",
                f"直す前のテストのログ: {v['log']}",
                _green_line(mode, out)]
        return rows + ([out["suite_note"]] if out.get("suite_note") else [])
    rows = [f"最後のテストの走らせ方: {v['suites']}",
            f"最後のテストのログ: {v['log']}",
            f"最後のテストの{v['baseline']}",
            f"最後のテストの一式: {v['suites']}・ログ {v['log']}"]
    if v["by"] == declared_checks.ROLE_NEEDED:
        rows.append(declared_checks.SELF_REPORTED_NOTE)
    return rows + [_green_line(mode, out)]


def _green_line(mode: str, out: dict) -> str:
    cause = out.get("red_cause") or ""
    line = f"試験の関門（{mode}）: {'緑' if out.get('green') is True else '緑でない'}・ok {out.get('ok')}" + (f"・赤の原因 {cause}" if cause else "")
    if out.get("ok") is True and cause in RED_KEPT:
        line += f"——赤のまま通した（{cause} の赤。直しが起こした赤でないと認証が見た）"
    return line


def _base_word(base: dict, place) -> str:
    """直す前のテストの語。認証されなかった（ok 偽）base の赤の原因が走らなかった事を言う句（green_cert.RAN_BY_CAUSE が NOT_RAN:
    environment・incomplete）なら、素材が測った結果でない・1 段も走らなかった・素材が無い・返す node の中の誤りの回の語「走らせられなかった」。
    返りの reason（認証しなかった訳）が在れば 1 行にして添える。認証された incomplete の base は、素材が not_applicable か
    awaiting_human なら元の結末のファイルの素材の語で言い、awaiting_human は走らせられなかった系統を名指す素材の reason を添える"""
    if base.get("green"):
        return "緑"
    cause = base.get("red_cause")
    if green_cert.RAN_BY_CAUSE.get(cause) == green_cert.NOT_RAN and base.get("ok") is not True:
        why = oneline.one_line(declared_checks.gate_values(base)["reason"])
        return f"走らせられなかった（{cause}）——{gatemarks.BASELINE_NOT_RUN}" + (f"——{why}" if why else "")
    if cause == green_cert.INCOMPLETE:
        material = _base_material(place)
        status = material.get("status")
        if status in (green_cert.NOT_APPLICABLE, green_cert.AWAITING_HUMAN):
            why = oneline.one_line(material.get("reason") or "") if status == green_cert.AWAITING_HUMAN else ""
            return f"{gatemarks.MATERIAL_WORDS[status]}（{status}）" + (f"——{why}" if why else "")
    return "赤" + (f"（赤の原因 {base.get('red_cause')}）" if base.get("red_cause") else "")


def _base_material(place) -> dict:
    """place の baseline.json（直す前の結末のファイル）の素材。読めなければ空"""
    try:
        material = baseline_red.read_baseline(pathlib.Path(place) / files.BASELINE).get("material")
    except ValueError:
        return {}
    return material if isinstance(material, dict) else {}
