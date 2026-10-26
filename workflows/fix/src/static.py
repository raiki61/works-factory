"""型 static（段の外。試験が要らない直し。docs/plans/2026-10-24-fix-weapons.md の 3.7）。

文書・コメント・設定の値・AI のノードへの指示の言い回し・CI の設定など、試験で照らす振る舞いの無い直し。赤を求めない（今の F135 を
当てない）。型の義務（3.7 の確かめ）:
1. 注文に why_untested が在る（計画の route_why。計画の側で 10 字以上を照らす）
2. 差分の各パスの種類が、注文の変えてよい種類の中（範囲は共通の受け付けの scope の照らし）
3. 試験の関数を変えない（単位の行に試験のファイルが無い。前から通っていた試験が通ることは共通の受け付けの新しい赤の照らし）
4. evidence.kinds に差分の種類ごとに 1 行以上（kinds_rows。段 2 で表に足す。書き手の指示が書き先を教えてから。付録 A の W13）
"""
from __future__ import annotations

BOX = "outside"


def why_untested(f: dict) -> list:
    return [] if str(f.get("why_untested") or "").strip() else ["注文に試験を求めない訳（why_untested。計画の route_why）が無い"]


NO_ALLOWED = "計画の項目の files から変えてよい種類が引けない（パスの種類が分からないか、計画の控えが読めない）のに、差分の種類 {kinds} を変えた"


def kinds_allowed(f: dict) -> list:
    """差分の種類が計画の項目の files の種類の中か。計画から種類が引けない時は素通りさせず拒む（何でも通さない）"""
    allowed = set(f.get("allowed_kinds") or [])
    kinds = sorted(k for k in f.get("kinds") or [] if k is not None)
    bad = [k for k in kinds if k not in allowed]
    unknown = [p for p, k in (f.get("kind_by_path") or {}).items() if k is None]
    out = [NO_ALLOWED.format(kinds=kinds)] if kinds and not allowed else \
        ([f"差分の種類 {bad} が、計画の項目の files の種類 {sorted(allowed)} の外"] if bad else [])
    return out + ([f"種類の分からないファイル {unknown[:10]} を変えた（試験の要らない直しの型は種類の分かる物だけを変える）"] if unknown else [])


def no_test_edits(f: dict) -> list:
    tests = list(f.get("test_files") or [])
    return [f"試験のファイル {tests[:10]} を変えた（試験の要らない直しは試験を足さない・変えない。足す要る物が在れば試験で示せる直し）"] \
        if tests else []


def kinds_rows(f: dict) -> list:
    have = {r.get("kind") for r in f.get("kinds_rows") or []}
    miss = sorted(k for k in f.get("kinds") or [] if k and k not in have)
    return [f"evidence.kinds に差分の種類 {miss} の確かめの行が無い"] if miss else []


DUTIES = (why_untested, kinds_allowed, no_test_edits)   # 段 2 で kinds_rows を足す
