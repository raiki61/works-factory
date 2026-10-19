"""規模の数値（R1 だけが使う）。lib/eyeverdict.py の scalars・scalars_text・X_SCALAR・DOC_SUFFIXES（:84・:101・:132-163）の写し"""
import re

import changemap   # lib/

X_SCALAR = re.compile(r"^x_[a-z0-9_]+$")   # 元 graphs/review-loop.json の p3.fix の x_scalars の patternProperties
DOC_SUFFIXES = (".md",)


def scalars(diff_text: str, x_scalars=None, not_taken: str = "") -> dict:
    """元 eyeverdict.scalars。差分から数えられる規模の数値（足した行・消した行・文書の足した行・変わったファイル）に、修正役が
    足した x_ の数値 x_scalars を足す。測れた分は返し、測れない物は 0 にせず unmeasured に訳を置く（差分が取れなかった訳 not_taken が
    在れば差分の数は測れない）"""
    out, why = {}, []
    files = changemap.split_diff(diff_text)[0]
    if not_taken:
        why.append(not_taken)
    elif diff_text.strip() and not files:
        why.append("累積差分が git の差分の形でない")
    else:
        rows = [(path, line[:1]) for path, lines in files.items() for line in lines]
        out = {"added_lines": sum(mark == "+" for _, mark in rows),
               "deleted_lines": sum(mark == "-" for _, mark in rows),
               "doc_lines": sum(mark == "+" and path.endswith(DOC_SUFFIXES) for path, mark in rows),
               "files": list(files)}
    if x_scalars is not None and not isinstance(x_scalars, dict):
        why.append("修正役の x_scalars が object でない")
    x = x_scalars if isinstance(x_scalars, dict) else {}
    bad = [str(k) for k, v in x.items() if not (X_SCALAR.match(str(k)) and isinstance(v, (int, float)) and not isinstance(v, bool))]
    if bad:
        why.append("修正役の x_scalars の形でない欄: " + "・".join(bad))
    out.update({k: v for k, v in x.items() if str(k) not in bad})
    return {**out, "unmeasured": why} if why else out


def scalars_text(s: dict) -> str:
    """元 eyeverdict.scalars_text。規模の数値の 1 文"""
    parts = ([f"足した行 {s['added_lines']}・消した行 {s['deleted_lines']}・文書の足した行 {s['doc_lines']}・"
              f"変わったファイル {len(s['files'])} 本"] if "added_lines" in s else [])
    parts += [f"{k} {v}" for k, v in s.items() if k.startswith("x_")]
    text = "・".join(parts) if parts else "測れた値は無い"
    return text + ("（測れなかった: " + "／".join(s["unmeasured"]) + "）" if s.get("unmeasured") else "")
