"""下ごしらえ（型ではない段。機械の名 pin。docs/plans/2026-10-24-fix-weapons.md の 3.6）。

今の振る舞いを試験で固める。コードを変えない。箱は keep（同じ結果の照らし）。義務（2.4 の pin）:
1. 差分は試験のファイルだけで、足した試験が 1 つ以上（tests_only）。例外は 1 つ: base.json の no_tests が真の注文では、起点の木に
   無い設定のファイル（rules.kind_of が config）を新しく作る物も許す。起点の木に在る設定のファイルの書き換え・消しは拒む（9.1 の 13）
2. 足した試験が起点の木で 2 回走らせて 2 回とも通る（twice。受け付けが走らせた結果の問題の文を読む）
3. 足した試験ごとに、sites に壊して赤・戻して緑の記録（行の test がその試験。sites_per_test。PR B で表に足す。PR A は今の周の全体の
   F135 を当てる）
"""
from __future__ import annotations

BOX = "keep"
KEPT_CONFIG = "起点の版に在る設定のファイルは下ごしらえで書き換えない"


def tests_only(f: dict) -> list:
    tests = set(f.get("test_files") or [])
    kinds = f.get("kind_by_path") or {}
    absent = set(f.get("absent_at_base") or [])
    out = []
    for p in f.get("files") or []:
        if p in tests:
            continue
        if kinds.get(p) == "config" and f.get("no_tests") is True:
            if p not in absent:
                out.append(f"{p}: {KEPT_CONFIG}")
            continue
        out.append(f"{p}: 下ごしらえは試験のファイルだけを書く（コードを変える要る物が在れば別の型の直し）")
    if not f.get("added"):
        out.append("足した試験が無い（下ごしらえは今の振る舞いを留める試験を足す）")
    return out


def twice(f: dict) -> list:
    got = f.get("twice")
    return list(got) if got else []


def sites_per_test(f: dict) -> list:
    proven = {s.get("test") for s in f.get("sites") or [] if s.get("red_seen")}
    miss = [t for t in f.get("added") or [] if t not in proven]
    return [f"足した試験 {miss[:10]} に、縛るコードを壊して赤を見た sites の行（test にその id）が無い"] if miss else []


DUTIES = (tests_only, twice)   # PR B で sites_per_test を足す
