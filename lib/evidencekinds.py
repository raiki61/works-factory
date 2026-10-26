"""証拠の種類の数え（変更の種類ごとの証拠の決まりを、指示のどの段落に載せるかの元）。修正の block（書き手の slots・振り分け）と
TDD の輪の周が共に使う（docs/plans/2026-10-27-fix-weapons-stage2-e2.md の 1 節）。パスの形から種類を見分ける表は lib/impact.py の kind_of。
実行基盤を知らず、置き場は引数のパスで受ける。

- KINDS: 変更の種類（節 evidence-<種類> の名）
- kinds_now(values, repo, before=()) / kinds_for(ledger, values, repo, start=()): 今の組み立てで載せる証拠の種類（判定の単位のパスと
  今の差分から選び、前に渡した種類を足す。輪の中で減らさない）
- delivered(ledger) / iteration_next(ledger) / remember(ledger, kinds, iteration): この輪で渡した種類と回の控え（<名>.delivered.json）
- unit_paths・changed_paths・select_kinds: 種類を選ぶ材料（判定の単位が指すパス・今の差分のパス・出どころごとのパスから {種類: 理由}）
- kinds_when(kinds, role): 書き手の決まりの証拠の段落の真偽（見出しと頭の文ごと落とす続きの周は種類が全部偽）
"""
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True

import impact  # noqa: E402  （kind_of。パスの形から種類を見分ける表）
import jsonfile  # noqa: E402
from leftovers import Unreadable, git_names  # noqa: E402


KINDS = ("docs", "prompts", "config", "code")   # 変更の種類 → 節 evidence-<種類>


PATH_TOKEN = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.[A-Za-z][A-Za-z0-9]*")


def unit_paths(judgment_file: str, open_units: str) -> tuple:
    """判定の直す義務の単位が指すパス（class_query の how の paths と、key の中のパスの形の語）。(パスの一覧, 読めない理由)"""
    try:
        doc = json.loads(pathlib.Path(judgment_file).read_text(encoding="utf-8"))
        keys = set(json.loads(open_units))
    except (OSError, ValueError, TypeError) as e:
        return [], f"判定か義務の単位が読めない（{type(e).__name__}）"
    out = []
    for u in (doc.get("units") if isinstance(doc, dict) else None) or []:
        if not isinstance(u, dict) or u.get("key") not in keys:
            continue
        how = (u.get("class_query") or {}).get("how") or {}
        out += [p for p in how.get("paths") or [] if isinstance(p, str)]
        out += PATH_TOKEN.findall(u["key"])
    return list(dict.fromkeys(out)), ""


def changed_paths(repo, rev: str = "HEAD") -> list:
    """作業ツリーの今の差分（修正前の版 rev からの変更と未追跡。.gitignore に当たる物は除く）のパス。git が効かなければ空"""
    try:
        got = git_names(repo, "diff", "--name-only", "--no-renames", rev or "HEAD", "--")
        got += git_names(repo, "ls-files", "--others", "--exclude-standard", "--full-name", "--", ":/")
    except Unreadable:
        return []
    return list(dict.fromkeys(got))


def select_kinds(sources: dict) -> dict:
    """{出どころ: パスの一覧} から {種類: 理由}（理由はどの出どころのどのパスか。機械の事実）。どの種類も見つからなければ
    全部の種類を「分からない」の理由で選ぶ（証拠の決まりを落とさない側）"""
    got = {}
    for src, paths in sources.items():
        for p in paths:
            k = impact.kind_of(p)
            if k:
                got.setdefault(k, []).append(f"{src} {p}")
    if not got:
        seen = sum(len(v) for v in sources.values())
        return {k: f"変更の種類が分からない（パス {seen} 本から見分けられない）——全部載せる" for k in KINDS}
    return {k: "; ".join(got[k][:5]) + (f" ほか {len(got[k]) - 5} 本" if len(got[k]) > 5 else "") for k in KINDS if k in got}


def kinds_now(values: dict, repo, before=()) -> dict:
    """今の組み立てで載せる証拠の種類: 判定の単位のパスと今の差分から選び、この輪で前に渡した種類を足す（輪の中で減らさない）"""
    paths, why = unit_paths(values.get("judgment_file") or "", values.get("open_units") or "")
    sources = {"判定": paths, "差分": changed_paths(repo, values.get("base_rev")) if repo is not None else []}
    got = select_kinds(sources)
    if why and not any(sources.values()):
        got = {k: f"{why}——全部載せる" for k in KINDS}
    for k in before:
        got.setdefault(k, "このループで前に渡した")
    return got


def delivered(ledger) -> dict:
    """控えのファイル ledger の {kinds, iterations}（無い・読めなければ空）"""
    done = jsonfile.read_or(pathlib.Path(ledger))
    return done if isinstance(done, dict) else {}


def iteration_next(ledger) -> int:
    """この輪で次に組む回の番号（控え ledger の iterations の数 + 1）"""
    return len(delivered(ledger).get("iterations") or []) + 1


def kinds_for(ledger, values: dict, repo, start=()) -> dict:
    """今の組み立てで載せる証拠の種類（kinds_now に、控え ledger の前に渡した種類と、控えの前の段が渡した種類 start を足す。輪の中で減らさない。
    start は TDD の輪の最初の周が振り分けの段の渡した種類を受ける口で、注文の型ごとの欄 orders.tdd の kinds）"""
    return kinds_now(values, repo, [*start, *(delivered(ledger).get("kinds") or ())])


def remember(ledger, kinds, iteration: int) -> None:
    """渡した後の種類と回を控え ledger に積む（今の write_prompt の後半）"""
    done = delivered(ledger)
    jsonfile.write(pathlib.Path(ledger), {"kinds": sorted(kinds), "iterations": [*(done.get("iterations") or []), iteration]})


WRITER_KINDS = {"docs": "docs", "prompts": "prompts_kind", "config": "config", "code": "code"}   # 種類 → writer-rules の段落の名


def kinds_when(kinds, role: str) -> dict:
    """writer-rules の証拠の段落の真偽。続きの周は種類が全部偽で、見出しと頭の文ごと落とす。role は答えを書く場所の段落の名（この block は writer・tdd）"""
    got = {name: kind in kinds for kind, name in WRITER_KINDS.items()}
    return {**got, "evidence": any(got.values()), **{f"where_{r}": r == role for r in ("writer", "tdd", "rework")}}
