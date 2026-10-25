"""形 entry（docs/design/spec-driven.md の 2.3・2.6・6.2 の足す node の 1）: 人と固めた仕様の表を入口で確かめ、判定の役と計画の部品に
渡す値を表と設計書から組む。

確かめ（どれも yes/no。どれかが欠ければ ok: false で、欠けた物を全部名指して止める。AI を起こさない）:
1〜4 は lib/spectable.problems（表の形・設計書が対象に在る・設計書の見出しに表の欄の名が無い・必ず回す 5 つの部品の記録が 1 件ずつ）。
5 は起動の殻が会話で回した審査の記録を Archon の run の記録と照らした結果のファイル（環境変数 files.REVIEWS_ENV）が在り、今の表と
設計書の物で、表の reviews の行と同じ並びで、全部の行が合っている（照らしそのものは殻の側。この block は Archon の記録を読まない）。

組む物（place に置き、pointer で返す）: 判定の役の依頼の行（設計書の頭の行と節の行と、受け入れの行）・目的のファイル・計画の部品の
固めた仕様（設計書の本文と、表から reviews を除いた字）。ほかに表と設計書のパス・「TDD で直す所」の有無・表の触らない物の写し。

- entry(place, repo, table) -> 返り（finish が返す形の entry の欄）。ENTRY にも写す
- reviews_problems(spec, path) -> [訳]: 入口の確かめの 5
"""
from __future__ import annotations

import json
import pathlib

import jsonfile    # lib/
import spectable   # lib/。PyYAML を読む（この script は PyYAML を宣言した uv の script）

import ports
from src import files


def _sha(path: pathlib.Path) -> str:
    return spectable.sha256(path.read_text(encoding="utf-8"))


def reviews_problems(spec: spectable.Spec, raw_path: str) -> list:
    """入口の確かめの 5（2.6 の 2 の「block の形 entry は、env の結果ファイルが在り、全部の行が合っていることだけを照らす」）"""
    if not raw_path.strip():
        return [files.NO_REVIEWS]
    path = pathlib.Path(raw_path)
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"審査の記録を照らした結果のファイル {path} を読めない（{type(error).__name__}）"]
    if not isinstance(got, dict) or not isinstance(got.get("rows"), list):
        return [f"審査の記録を照らした結果のファイル {path} の形が違う（rows の並びが無い）"]
    out = []
    if got.get("table_sha256") != _sha(spec.root / spec.table_rel) or got.get("design_sha256") != _sha(spec.root / spec.design_rel):
        out.append("審査の記録を照らした結果が、今の表か設計書の物でない（起動の殻を通して起動し直す）")
    want = [(r.get("part"), r.get("run")) for r in spec.table.get("reviews") or [] if isinstance(r, dict)]
    have = [(r.get("part"), r.get("run")) for r in got["rows"] if isinstance(r, dict)]
    if want != have:
        out.append("審査の記録を照らした結果の行が、表の reviews の行と違う（起動の殻を通して起動し直す）")
    for r in got["rows"]:
        if isinstance(r, dict) and r.get("ok") is not True:
            why = "・".join(str(w) for w in r.get("why") or []) or "合わない訳が書かれていない"
            out.append(f"審査の記録 {r.get('part')}（run {r.get('run')}）が照らしに合わない: {why}")
    return out


PURPOSE_SOURCE = "②計画・タスク記述"   # 人と固めた仕様の表は計画・タスクの記述（固めた目的の source の語）


def _purpose(spec: spectable.Spec) -> dict:
    # source は固めた目的の形（shared:purpose.schema.json）の語の 1 つ。表のパスは source_files が持つ
    return {"purpose_text": str(spec.table["purpose"]).strip(), "source": PURPOSE_SOURCE,
            "known_weaknesses": [], "source_files": [spec.table_rel, spec.design_rel]}


def _report(spec: spectable.Spec) -> list:
    lines = [f"- 仕様駆動の道の入口: 表 {spec.table_rel} と設計書 {spec.design_rel} を確かめた（会話で回した審査の記録 "
             f"{len(spec.table.get('reviews') or [])} 件を起動の殻が照らした）"]
    for r in spec.table.get("reviews") or []:
        found = r.get("findings") or []
        tail = "・".join(f"{f.get('key')}（受け入れた言葉: {f.get('owner_words')}）" for f in found) or "残った指摘なし"
        lines.append(f"  - {r.get('part')}（run {r.get('run')}）: {tail}")
    return lines


def stopped(problems: list, report_head: str) -> dict:
    return {"ok": False, "stop_reason": files.STOP_ENTRY, "reason": "；".join(problems), "request": None, "origin": "", "purpose": None,
            "spec": None, "spec_files": [], "tdd": False, "out_of_scope": [],
            "report": [f"- 止めた（{files.STOP_ENTRY}）: {report_head}", *(f"  - {p}" for p in problems)]}


def entry(place, repo, table, reviews_file: str) -> dict:
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    for name in files.OWN_FILES:
        (place / name).unlink(missing_ok=True)
    try:
        path = ports.file(table, "file")
    except ValueError as error:
        path, unread = None, f"入力 table を読めない: {error}"
    else:
        unread = ""
    if unread:
        got = stopped([unread], "仕様駆動の道の表を読めない")
    elif path is None:
        got = stopped(["入力 table が空（仕様駆動の道の表のパスを渡す）"], "仕様駆動の道の表が渡されていない")
    else:
        spec = spectable.read(repo, path)
        problems = spectable.problems(spec)
        if spec.table is not None and spec.design is not None:   # 5 は 1〜4 の欠けと一緒に名指す（表と設計書が読めた時）
            problems += reviews_problems(spec, reviews_file)
        if problems:
            got = stopped(problems, "仕様駆動の道の入口の確かめが通らない（AI を起こす前に止めた）")
        else:
            rows = [*spectable.design_rows(spec), *spectable.acceptance_rows(spec)]
            jsonfile.write(place / files.REQUEST, rows)
            jsonfile.write(place / files.PURPOSE, _purpose(spec))
            (place / files.SPEC).write_text(spectable.proposal_text(spec) + "\n", encoding="utf-8")
            got = {"ok": True, "stop_reason": "", "reason": "", "request": ports.pointer(place / files.REQUEST, "json(shared:request.schema.json)"),
                   "origin": f"人と固めた仕様（{spec.table_rel}）", "purpose": ports.pointer(place / files.PURPOSE, "json(shared:purpose.schema.json)"),
                   "spec": ports.pointer(place / files.SPEC, "file"), "spec_files": [spec.table_rel, spec.design_rel],
                   "tdd": spectable.has_tdd(spec.design), "out_of_scope": list(spec.table.get("out_of_scope") or []),
                   "report": _report(spec)}
    jsonfile.write(place / files.ENTRY, got)
    return got
