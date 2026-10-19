"""承認したテストが変わったかを照らす（今の lib/judge_accept.py の spec_check・spec_questions の写し。docs/design/spec.md の 1.5）。
固めた仕様の受け入れ条件のファイルごとに（同じファイルは 1 度、初めに出た順）、今の作業ツリーの sha256 を承認の時の sha256 と
照らす。照らせなかったら黙って 0 件にせず、照らせなかったと言う。"""
from __future__ import annotations

import os
import pathlib

import gatemarks   # lib/。問いの頭の語 SPEC_CHANGED_LABEL（最後の承認ノードと報告も読む）
import oneline     # lib/

from src import files, freeze

NO_SPEC = "照らす承認済みの仕様が渡されていない——受け入れ条件のテストが変わったかを照らせない"


def failed_question(why: str) -> str:
    return f"照らしが落ちた——承認済みの受け入れ条件のテストが変わったかを確かめられない（{why}）"


def changed(spec: dict, root) -> list:
    """変わったファイルの [{file, from, to, why}]（to は今の sha256。測れなければ None で、why にその訳）。仕様の形が違えば
    KeyError・TypeError（呼び手が「読めない」の問いにする）"""
    seen, out = set(), []
    for a in spec["acceptance"]:
        f = a["file"]
        if f in seen:
            continue
        seen.add(f)
        p = pathlib.Path(root) / f
        now, why = freeze.sha_and_why(p) if os.path.lexists(p) else (None, "消えた")
        if now != a["sha256"]:
            out.append({"file": f, "from": a["sha256"], "to": now, "why": why})
    return out


def questions(spec_path, root) -> dict:
    """承認し直すかの問い（questions。1 ファイル 1 行）と、照らせなかったか（unchecked）。仕様が無い・読めない・形が違えば、
    変わった行と混ぜず「読めない」の問いを 1 行だけ返して unchecked を真にする"""
    try:
        spec = files.read(spec_path)
        if spec is None:
            raise FileNotFoundError("ファイルが無い")
        rows = changed(spec, root)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return {"questions": [f"承認済みの仕様 {spec_path} を読めない——受け入れ条件のテストが変わったかを確かめられない"
                              f"（{oneline.one_line(f'{type(e).__name__}: {e}')}）"], "unchecked": True}
    return {"questions": [f"{gatemarks.SPEC_CHANGED_LABEL}: {r['file']}（sha256 {str(r['from'])[:12]} → "
                          f"{r['why'] if r['to'] is None else r['to'][:12]}）——承認し直すか。"
                          "この run の中では答えられない: 変更を確かめて次の run の仕様の段で承認し直すか、テストを承認の版に戻して直す依頼にする"
                          for r in rows], "unchecked": False}
