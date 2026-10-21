"""形 check（docs/design/spec-driven.md の 6.4）: 判定の役と計画の部品を 1 回ずつ通した後に、仕様とリポジトリの食い違いを照らす。

どれも yes/no。1 つでも当たれば ok: false で、当たった物を mismatches に名指して止める（仕様を書き換えない。人が仕様を直したら新しい
run）。番号は設計書 6.4 の番号（1 と 5 は外した。判定の役の問いと能力を狭める行は、今の本線と同じく修正前の承認ノードで人に見せる）。

2. 判定の役が直す単位を返さなかった（ready が真でない）か、計画の部品が落ちた（plan_ok が真でない）
3. 計画の行のファイルの行で、op が modify・delete なのにパスが base の版に無い・create なのに在る・rename で from が無いか path が在る
4. 表の out_of_scope の glob が、計画の行のどれの out_of_scope にも無い
6. 設計書に「TDD で直す所」が無いのに route が tdd の行が在る、か在るのに tdd の行が 1 つも無い
7. 判定の役が目的の外とした行（out_of_purpose の控えの最後の周の行）が在る

表は読み直さない（形 entry の返りの tdd と out_of_scope の写しを受ける。PyYAML を持たない）。

- check(place, repo, *, ready, plan_ok, plan, out_of_scope, tdd, out_of_purpose, base) -> 返り（finish が返す形の check の欄）。CHECK にも写す
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import jsonfile   # lib/

from src import files

SKIPPED = "（判定か計画が回らなかったので照らしていない）"


def _rows(path) -> list:
    """計画の項目ごとの欄の控え（{round, fields}）の行。無い・読めなければ []"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8")) if path else None
    except (OSError, ValueError):
        return []
    rows = doc.get("fields") if isinstance(doc, dict) else None
    return [r for r in rows or [] if isinstance(r, dict)]


def _in_base(repo, base: str, path: str) -> bool:
    """パスが base の版（空は HEAD）に在るか"""
    done = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{base or 'HEAD'}:{path}"], capture_output=True)
    return done.returncode == 0


def file_mismatches(repo, base: str, rows: list) -> list:
    out = []
    for n, row in enumerate(rows, 1):
        for f in row.get("files") or []:
            if not isinstance(f, dict):
                continue
            op, path, old = f.get("op"), str(f.get("path") or ""), str(f.get("from") or "")
            if op in ("modify", "delete") and not _in_base(repo, base, path):
                out.append(f"計画の行 {n} のファイルの行 {path} は {op} だが、作業ツリーの版に無い")
            elif op == "create" and _in_base(repo, base, path):
                out.append(f"計画の行 {n} のファイルの行 {path} は create だが、作業ツリーの版に既に在る")
            elif op == "rename" and (not old or not _in_base(repo, base, old) or _in_base(repo, base, path)):
                out.append(f"計画の行 {n} のファイルの行 {path} は rename だが、元のパス {old or '（無い）'} が作業ツリーの版に無いか、"
                           "新しいパスが既に在る")
    return out


def scope_mismatches(table_scope: list, rows: list) -> list:
    planned = {str(o.get("glob")) for r in rows for o in r.get("out_of_scope") or [] if isinstance(o, dict)}
    return [f"表の触らない物 {o.get('glob')} が、計画の行のどれの out_of_scope にも無い"
            for o in table_scope if isinstance(o, dict) and str(o.get("glob")) not in planned]


def tdd_mismatches(tdd: bool, rows: list) -> list:
    routed = [n for n, r in enumerate(rows, 1) if r.get("route") == "tdd"]
    if not tdd and routed:
        return [f"設計書に「TDD で直す所」が無いのに、計画の行 {'・'.join(map(str, routed))} の route が tdd"]
    if tdd and not routed:
        return ["設計書に「TDD で直す所」が在るのに、route が tdd の計画の行が 1 つも無い"]
    return []


def purpose_mismatches(path) -> list:
    """判定の役が目的の外とした行（控え {rounds: {周: [行]}} の最後の周）。読めない控えは読めないと名指す（無かった物と読まない）"""
    if not path:
        return []
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        rounds = doc["rounds"]
        last = rounds[max(rounds, key=int)] if rounds else []
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f"判定の目的の外の控え {path} を読めない（{type(error).__name__}。目的の外の行が無いとは読まない）"]
    return [f"判定の役が目的の外とした行: {r.get('where')}——{r.get('why_outside')}（設計書が表の目的と受け入れの条件の外を書いている）"
            for r in last if isinstance(r, dict)]


def check(place, repo, *, ready: bool, plan_ok: bool, plan, out_of_scope: list, tdd: bool, out_of_purpose, base: str) -> dict:
    place = pathlib.Path(place)
    (place / files.CHECK).unlink(missing_ok=True)
    out = []
    if not ready:
        out.append("判定の役が直す単位を返さなかった" + SKIPPED)
    elif not plan_ok:
        out.append("計画の部品が落ちた（計画の行が無い）" + SKIPPED)
    else:
        rows = _rows(plan)
        out += file_mismatches(repo, base, rows) + scope_mismatches(out_of_scope, rows) + tdd_mismatches(tdd, rows)
    out += purpose_mismatches(out_of_purpose)
    if out:
        got = {"ok": False, "stop_reason": files.STOP_MISMATCH, "reason": "；".join(out), "mismatches": out,
               "report": [f"- 止めた（{files.STOP_MISMATCH}）: 仕様とリポジトリが食い違う（仕様を直して新しい run で回す）",
                          *(f"  - {m}" for m in out)]}
    else:
        got = {"ok": True, "stop_reason": "", "reason": "", "mismatches": [],
               "report": ["- 仕様とリポジトリの食い違いの照らし: 当たり無し（ファイルの行・触らない物・TDD の印・目的の外）"]}
    jsonfile.write(place / files.CHECK, got)
    return got
