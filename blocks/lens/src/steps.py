"""lens の block の中身（docs/design/lens.md の 3 節。lib/fixboard.py の lens_route・lens_collector と lib/lenses.py の collect を、
port の値で受ける形に写した物）。

修正の前の版 base から今の作業ツリーまでの差分を切り、表のレンズのうち入力が名指した物を、変わったファイルが在り定義が引ける時だけ起こす。
レンズごとの node（prep・役・受け取り）が指示を組み、返答を place に置き、出口が控え lens.json の行を埋めて数える。控え lens.json の形と読み書きは
lib/lens.py だけが持つ。指示の文は prompts/parts/lens.md が持ち、ここは値だけを組む。

place のファイル（名は src/files.py。lens.md の 1.4）:
- intake.json: {base, files, lang, routes: {<レンズ>: {go, reason, agent, body}}, failed, reason}
- lens.diff: 差分
- lens.json: レンズの行（lib/lens.py）
- reply-<key>.json: 受け取ったレンズの返答
- <レンズ>-prompt-<n>.md（prompt.emit が書く）・errors.json: 段が壊れた訳 [{node, reason}]
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt

import jsonfile   # lib/
import leftovers  # lib/。作業ツリーの木・git
import lens       # lib/。控え lens.json
import oneline    # lib/
import unittrees  # lib/。pathspec_without

from src import files, lenses

OPTIONAL = [entry for row in lenses.LENSES
            for entry in ({"node": row["lens"], "bare": False}, {"node": f"{row['lens']}-take", "bare": False})]


# ---------------------------------------------------------------- 置き場
def add_error(out, node: str, reason: str) -> None:
    path = pathlib.Path(out) / files.ERRORS
    rows = jsonfile.read_or(path, [])
    rows = rows if isinstance(rows, list) else []
    jsonfile.write(path, [*rows, {"node": node, "reason": oneline.one_line(reason)}])


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def _own(out: pathlib.Path) -> None:
    for name in (files.INTAKE, files.DIFF, files.ERRORS, lens.LENS_FILE, *[files.reply(lenses.key(r["lens"])) for r in lenses.LENSES]):
        (out / name).unlink(missing_ok=True)
    for row in lenses.LENSES:
        for path in out.glob(files.prompts(row["lens"])):
            path.unlink()


def _asked(raw) -> list:
    """port lenses の行。表に無い名・同じ名が 2 つは拒む"""
    rows = ports.json(raw, "lenses.schema.json")
    known = [r["lens"] for r in lenses.LENSES]
    names = [r["lens"] for r in rows]
    for name in names:
        if name not in known:
            raise ValueError(f"知らないレンズ {name}（この block のレンズは {', '.join(known)}）")
        if names.count(name) > 1:
            raise ValueError(f"レンズ {name} が 2 つ在る")
    return rows


def _tree(repo, base: str) -> None:
    try:
        leftovers.git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{tree}}")
    except leftovers.Unreadable:
        raise ValueError(f"git の版（木か commit）として読めない: {base!r}") from None


def cut(out: pathlib.Path, repo, base: str) -> list:
    """base から今の作業ツリーの姿（未追跡の新しいファイルも。.gitignore に当たる物は除く）までの差分を lens.diff に書き、
    変わったファイルを返す（files.SKIP の下は除く）"""
    snap = leftovers.snapshot(repo)
    spec = unittrees.pathspec_without(files.SKIP)
    (out / files.DIFF).write_bytes(leftovers.git(repo, "diff", base, snap, "--", *spec, text=False))
    return leftovers.git_names(repo, "diff", "--name-only", base, snap, "--", *spec)


# ---------------------------------------------------------------- 入口
def intake(out, repo, *, base, lenses_raw, lang) -> dict:
    """この block のファイルを消し、port を読み、差分を切って振り分ける。返り {due, reason, <key>_go…}。落ちない:
    壊れたら errors.json に積み、intake.json に failed を書き、全部の <key>_go を偽にして返す"""
    out = pathlib.Path(out)
    _own(out)
    doc = {"base": "", "files": [], "lang": "", "routes": {}, "failed": False, "reason": ""}
    gos = {lenses.key(r["lens"]) + "_go": False for r in lenses.LENSES}
    try:
        doc["base"] = ports.text(base).strip()
        _port("base", lambda: _tree(repo, doc["base"]))
        asked = {r["lens"]: r for r in _port("lenses", lambda: _asked(lenses_raw))}
        doc["lang"] = ports.text(lang).strip()
        doc["files"] = cut(out, repo, doc["base"])
        rows = []
        for table in lenses.LENSES:
            name, row = table["lens"], asked.get(table["lens"])
            agent, body = (row or {}).get("agent") or table["agent"], (row or {}).get("body") or ""
            if row is None:
                go, why = False, lenses.NOT_NAMED
            else:
                go, why = lenses.route(table, doc["files"])
                if go and not body:
                    body, why = lenses.definition(agent)
                    go = body is not None
            doc["routes"][name] = {"go": go, "reason": why, "agent": agent, "body": body or ""}
            gos[lenses.key(name) + "_go"] = go
            rows.append({"lens": name, "agent": agent, "go": go, "reason": why})
        lens.write_routes(out, rows)
        jsonfile.write(out / files.INTAKE, doc)
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        reason = oneline.one_line(f"{type(e).__name__}: {e}")
        add_error(out, "intake", reason)
        jsonfile.write(out / files.INTAKE, {**doc, "routes": {}, "failed": True, "reason": reason})
        return {"due": False, "reason": reason, **{k: False for k in gos}}
    return {"due": any(gos.values()), "reason": "", **gos}


# ---------------------------------------------------------------- 指示・受け取り
def lens_prompt(out, name: str) -> dict:
    """レンズ name の指示を組んで place に書く。返り {prompt}"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    route = doc.get("routes", {}).get(name) if isinstance(doc, dict) else None
    if not isinstance(route, dict) or not route.get("body"):
        raise ValueError(f"入口の控えにレンズ {name} の振り分けが無い")
    values = {"agent": route["agent"], "body": route["body"], "lens": name, "diff_file": str(out / files.DIFF),
              "files": json.dumps(doc["files"], ensure_ascii=False), "min_cite": lenses.MIN_CITE, "min_why": lenses.MIN_WHY,
              "lang": prompt.lang(doc["lang"])}
    return prompt.emit(name, values, None, prompt.round_of(name))


def take(out, name: str, raw) -> dict:
    """レンズの返答を place の reply-<key>.json に書く。返り {ok}"""
    jsonfile.write(pathlib.Path(out) / files.reply(lenses.key(name)), ports.parsed(raw))
    return {"ok": True}


# ---------------------------------------------------------------- 出口
def _failed(reason: str) -> dict:
    return {"ok": False, "status": "failed", "reason": reason, "rows": None, "ran": 0, "failed": 0, "not_routed": 0, "carry": [],
            "report": [f"レンズ: 落ちた（{reason}）"], "optional": OPTIONAL}


def finish(out) -> dict:
    """受け取った返答で控えの行を埋めて数える。レンズが落ちても ok。控えが書けない・入口が壊れた・指示が組めなかった時は status: failed"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    if not isinstance(doc, dict):
        return _failed("入口の控えが無い（入口の node が落ちた）")
    if doc.get("failed"):
        return _failed(str(doc.get("reason") or "入口が落ちた"))
    try:
        rows = lens.collect(out, {r["lens"]: jsonfile.read_or(out / files.reply(lenses.key(r["lens"]))) for r in lenses.LENSES})
    except (OSError, ValueError) as e:
        return _failed(f"レンズの集め役が終わらなかった: {oneline.one_line(e)}")
    errors = jsonfile.read_or(out / files.ERRORS, [])
    broken = [e for e in errors if isinstance(e, dict)] if isinstance(errors, list) else []
    count = {s: sum(1 for r in rows if r["state"] == s) for s in ("ran", "failed", "not_routed")}
    left = [f"{r['lens']}: {lens.UNSEEN[r['state']]}（{r.get('reason') or '理由の記録が無い'}）" for r in rows if r["state"] in lens.UNSEEN]
    seen = [f"{r['lens']}: 出した発見 {len(r.get('findings') or [])} 件・形の誤りで捨てた {r.get('dropped') or 0} 件"
            for r in rows if r["state"] == "ran"]
    carry = [{"where": f"レンズ {r['lens']}",
              "text": f"{r['lens']}（再実行の要あり: 落ちて観点を誰も見ていない。理由: {oneline.one_line(r.get('reason') or '理由の記録が無い')}）"}
             for r in rows if r["state"] == "failed"]
    status = "failed" if broken else "ok"
    reason = "レンズの指示が組めなかった: " + "・".join(f"{e.get('node')}（{e.get('reason')}）" for e in broken) if broken else ""
    return {"ok": not broken, "status": status, "reason": reason, "rows": ports.pointer(out / lens.LENS_FILE), **count, "carry": carry,
            "report": [*(left or ["なし（振り分けたレンズは全部走った）"]), *seen], "optional": OPTIONAL}
