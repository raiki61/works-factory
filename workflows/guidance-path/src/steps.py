"""案内の道の目の中身（docs/design/guidance-path.md）。

文脈を持たない読み手（guidance-walk の役）に、典型の変更の頼みを 1 つずつ渡し、リポジトリの入口から案内と手本だけを頼りに辿らせ、
辿った道・変更を置く所・写す手本を記録する。置いた所が頼みの閉じるべき所（closes）の中なら当たり。外れた頼みは、案内を見直す役
（guidance-fix の役）に、外れた道を見せて案内の直しを出させる。読み手には閉じるべき所を見せない（見せると案内の試しにならない）。

place のファイル（名はこのモジュールだけが持つ）:
- intake.json: {requests, entry, lang, reason}
- walks.json: {<頼みの id>: {steps, placed, copied, stuck, guessed} か {gave_up: 理由}}
- compare.json: [{id, hit, placed, closes}]
- fixes.json: [{request, kind, where, change, why}]
- paths.json: 出力 paths の pointer の先（[{id, request, closes, hit, steps, placed, copied, stuck, guessed, gave_up}]）
- rejects-walk-<id>.json・rejects-fix.json: 出し直しの輪の却下の控え（lib/rolekit）。入口は名で引いて消す（ほかの block の控えを消さない）
- guidance-walk-prompt-<n>.md・guidance-fix-prompt-<n>.md（prompt.emit が書く）
"""
from __future__ import annotations

import json
import pathlib
import re

import ports
import prompt

import jsonfile   # lib/
import oneline    # lib/
import rolekit    # lib/

INTAKE, WALKS, COMPARE, FIXES, PATHS = "intake.json", "walks.json", "compare.json", "fixes.json", "paths.json"
WALK_NODE, FIX_NODE = "guidance-walk", "guidance-fix"
FIX_ROLE = "fix"
KINDS = ("guide", "model", "block")   # 案内の直しの種類（README の 8.6: 案内を足す・手本を替える・間違った道を置き場で塞ぐ）
ENTRY_DEFAULT = ("README.md", "AGENTS.md")
NEW, NEW_ = "{new}", "{new_}"   # 閉じるべき所の中の、新しい block の名の口（{new_} は - を _ にした形）
# 読み手に見せない所（この目そのものの block・試験・設計書と、Archon が写した pack）。YAML の guidance-walk の denied_tools が
# Read(./<所>) で塞ぎ、受け付けは開いたと言う返答を拒む。tests/blocks/guidance_path が YAML と突き合わせる
HIDDEN = ("blocks/guidance-path", "tests/blocks/guidance_path", "docs/design/guidance-path.md", ".archon")
NONE = "(none)"


def _read(path, default=None):
    return jsonfile.read_or(path, default)


def _need(out, name):
    got = _read(pathlib.Path(out) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(out) / name} が無いか読めない")
    return got


def is_hidden(path: str) -> bool:
    return under(path, HIDDEN)


def walk_role(request_id: str) -> str:
    """頼みごとの却下の控えの名（頼みごとに 3 回で諦める）"""
    return f"walk-{request_id}"


def norm(path: str) -> str:
    """作業ツリーの根からのパスの比べの形（頭の ./ と尾の / を落とす）"""
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def under(path: str, closes) -> bool:
    path = norm(path)
    return any(path == norm(c) or path.startswith(norm(c) + "/") for c in closes)


def _close_pattern(close: str) -> re.Pattern:
    """閉じるべき所 1 つの形。{new} は新しい block の名（小文字・数字・-）、{new_} は同じ名の - を _ にした物（試験のフォルダ）"""
    rx = re.escape(norm(close)).replace(re.escape(NEW_), r"(?P<under>[a-z0-9][a-z0-9_]*)").replace(re.escape(NEW),
                                                                                                 r"(?P<name>[a-z0-9][a-z0-9-]*)")
    return re.compile(rf"^{rx}(?:/.*)?$")


def judge_placed(placed: list, closes: list, root: pathlib.Path) -> tuple[bool, str]:
    """置いた所が全部、閉じるべき所のどれかの中か。返り (当たりか, 外れの訳)。{new}・{new_} を持つ所は、置いた所の全部で同じ 1 つの名に
    結ばれ、その名で埋めた所（新しい block のフォルダなど）が作業ツリーにまだ無い時だけ当たる"""
    if not placed:
        return False, "置いた所が無い"
    names, outside = set(), []
    for path in map(norm, placed):
        match = next((m for c in closes if (m := _close_pattern(c).match(path))), None)
        if match is None:
            outside.append(path)
            continue
        bound = match.groupdict()
        if bound.get("name"):
            names.add(bound["name"].replace("-", "_"))
        if bound.get("under"):
            names.add(bound["under"])
    if outside:
        return False, f"閉じるべき所の外: {outside}"
    if len(names) > 1:
        return False, f"新しい名が 1 つに結ばれない: {sorted(names)}"
    for name in names:
        hyphen = next((m.group("name") for path in map(norm, placed) for c in closes
                       if (m := _close_pattern(c).match(path)) and m.groupdict().get("name")), name.replace("_", "-"))
        for close in closes:
            if NEW in close or NEW_ in close:
                spot = norm(close.replace(NEW_, name).replace(NEW, hyphen))
                if (root / spot).exists():
                    return False, f"新しい所のはずの {spot} が作業ツリーに既に在る"
    return True, ""


# ---------------------------------------------------------------- 入口
def _own_files(out: pathlib.Path, ids) -> list[pathlib.Path]:
    """place の中でこの block が名を持つファイル（頼みの id ごとの却下の控えも名で引く。ほかの物は消さない）"""
    names = [INTAKE, WALKS, COMPARE, FIXES, PATHS, rolekit.rejects_path(out, FIX_ROLE).name,
             *[rolekit.rejects_path(out, walk_role(i)).name for i in ids]]
    return [out / n for n in names] + [p for node in (WALK_NODE, FIX_NODE) for p in out.glob(f"{node}-prompt-*.md")]


def _inline_or_pointer(raw) -> str:
    """頼みは値そのものか pointer だけで受ける。ファイルのパスで受けると、頼みと閉じるべき所が読み手の作業ツリーに在りうる"""
    raw = ports.text(raw)
    if not raw.strip():
        return raw
    try:
        json.loads(raw)
    except ValueError:
        raise ValueError("入力 requests はパスで受けない（値そのものの JSON か、この run の pointer で渡す。閉じるべき所を読み手の"
                         "作業ツリーに置かない）") from None
    return raw


def intake(out, *, requests, entry, lang) -> dict:
    out = pathlib.Path(out)
    before = (_read(out / INTAKE) or {}).get("requests") or []
    doc = {"requests": [], "entry": [], "lang": prompt.lang(lang), "reason": ""}
    try:
        doc["requests"] = ports.json(_inline_or_pointer(requests), "requests.schema.json")
        ids = [r["id"] for r in doc["requests"]]
        twice = sorted({i for i in ids if ids.count(i) > 1})
        if twice:
            raise ValueError(f"頼みの id {twice} が重なる")
        doc["entry"] = ports.text(entry).split() or list(ENTRY_DEFAULT)
        absent = [e for e in doc["entry"] if not (pathlib.Path.cwd() / e).is_file()]
        if absent:
            raise ValueError(f"入口のファイル {absent} が作業ツリーに無い")
        hidden = [e for e in doc["entry"] if is_hidden(e)]
        if hidden:
            raise ValueError(f"入口のファイル {hidden} は読み手に見せない所（{'・'.join(HIDDEN)}）の中")
    except ValueError as e:
        doc["reason"] = oneline.one_line(e)
    ids = {r.get("id") for r in [*before, *doc["requests"]] if isinstance(r, dict) and isinstance(r.get("id"), str)}
    for path in _own_files(out, sorted(ids)):
        path.unlink(missing_ok=True)
    jsonfile.write(out / INTAKE, doc)
    return {"due": not doc["reason"], "requests": len(doc["requests"]), "reason": doc["reason"]}


# ---------------------------------------------------------------- 読み手
def _next(out) -> dict | None:
    doc, walks = _need(out, INTAKE), _read(pathlib.Path(out) / WALKS, {})
    return next((r for r in doc["requests"] if r["id"] not in walks), None)


def walk_prompt(out) -> dict:
    """まだ辿っていない頭の頼みの指示を組む。返り {prompt}"""
    doc = _need(out, INTAKE)
    req = _next(out)
    if req is None:
        raise ValueError("辿る頼みが残っていない（輪の done の配線の誤り）")
    rejected = rolekit.rejected(out, walk_role(req["id"]))
    values = {"rejection": rolekit.rejects_text(rejected), "request": req["request"],
              "entry": "\n".join(f"- {e}" for e in doc["entry"]), "lang": doc["lang"]}
    return prompt.emit(WALK_NODE, values, {"rejected": bool(rejected)}, prompt.round_of(WALK_NODE))


def _rows(reply, key: str, fields: tuple, bad: list) -> list:
    rows = reply.get(key)
    if not isinstance(rows, list) or not all(isinstance(r, dict) and all(isinstance(r.get(f), str) for f in fields) for r in rows):
        bad.append(f"{key} は {{{', '.join(fields)}}} の字の組の配列")
        return []
    return rows


def _path_problem(path: str) -> str:
    p = pathlib.PurePosixPath(norm(path))
    if not str(p) or p.is_absolute() or ".." in p.parts:
        return f"パス {path!r} は作業ツリーの根からの相対で、.. を持たない"
    return ""


def walk_problems(reply) -> list:
    if not isinstance(reply, dict):
        return ["返答が JSON のオブジェクトでない"]
    bad = []
    steps = _rows(reply, "steps", ("file", "why"), bad)
    placed = _rows(reply, "placed", ("path", "change"), bad)
    copied = _rows(reply, "copied", ("path", "why"), bad)
    for key in ("stuck", "guessed"):
        if not isinstance(reply.get(key), list) or not all(isinstance(x, str) for x in reply[key]):
            bad.append(f"{key} は字の配列")
    if not steps:
        bad.append("steps が空（入口から開いたファイルを順に書く）")
    if not placed:
        bad.append("placed が空（変更を置く所を 1 つ以上書く）")
    for row in steps:
        why = _path_problem(row["file"]) or ("" if (pathlib.Path.cwd() / norm(row["file"])).is_file()
                                            else f"steps の {row['file']!r} が作業ツリーに無い（開いたファイルだけを書く）")
        if not why and is_hidden(row["file"]):
            why = f"steps の {row['file']!r} は読み手に見せない所の中（読めないはずの所を開いたと書いた）"
        if why:
            bad.append(why)
    for row in [*placed, *copied]:
        why = _path_problem(row["path"])
        if why:
            bad.append(why)
    return bad


def walk_accept(out, raw) -> dict:
    """読み手の返答の字 raw を受け付ける。通るか 3 回目の却下で、その頼みを済みにする。返り {ok, done, reason}（done は全部の頼みが済んだか）"""
    out = pathlib.Path(out)
    req = _next(out)
    if req is None:
        return {"ok": False, "done": True, "reason": "辿る頼みが残っていない（輪の done の配線の誤り）"}
    role = walk_role(req["id"])

    def take(reply):
        bad = walk_problems(reply)
        return {"ok": not bad, "reason": " / ".join(bad)}
    got = rolekit.accept_round(out, role, raw, take)
    walks = _read(out / WALKS, {})
    if got["ok"]:
        reply = rolekit.parse_reply(raw)[0]
        walks[req["id"]] = {k: reply[k] for k in ("steps", "placed", "copied", "stuck", "guessed")}
    elif got["done"]:
        walks[req["id"]] = {"gave_up": rolekit.given_up_reason(out, role) or str(got["reason"])}
    jsonfile.write(out / WALKS, walks)
    left = [r for r in _need(out, INTAKE)["requests"] if r["id"] not in walks]
    return {"ok": bool(got["ok"]), "done": not left, "reason": str(got["reason"])}


# ---------------------------------------------------------------- 比べ
def compare(out) -> dict:
    """置いた所を閉じるべき所と比べる。返り {due, misses, reason}（due は案内を見直す役を起こすか）"""
    out = pathlib.Path(out)
    doc = _read(out / INTAKE)
    if doc is None or doc.get("reason"):
        return {"due": False, "misses": 0, "reason": (doc or {}).get("reason") or "入口の控えが無い（入口の node が落ちた）"}
    walks = _read(out / WALKS, {})
    rows = []
    for req in doc["requests"]:
        walk = walks.get(req["id"])
        if not walk or "gave_up" in walk:
            continue
        placed = [norm(p["path"]) for p in walk["placed"]]
        hit, why = judge_placed(placed, req["closes"], pathlib.Path.cwd())
        rows.append({"id": req["id"], "hit": hit, "why": why, "placed": placed, "closes": [norm(c) for c in req["closes"]]})
    jsonfile.write(out / COMPARE, rows)
    misses = sum(not r["hit"] for r in rows)
    return {"due": misses > 0, "misses": misses, "reason": ""}


# ---------------------------------------------------------------- 案内を見直す役
def _miss_lines(out) -> str:
    doc, walks = _need(out, INTAKE), _need(out, WALKS)
    missed = {r["id"]: r.get("why", "") for r in _need(out, COMPARE) if not r["hit"]}
    lines = []
    for req in doc["requests"]:
        if req["id"] not in missed:
            continue
        walk = walks[req["id"]]
        lines += [f"### Request {req['id']}", "", f"- Request: {req['request']}", f"- Should close in: {', '.join(req['closes'])}",
                  *([f"- Why it missed (machine): {missed[req['id']]}"] if missed[req["id"]] else []),
                  "- Reader opened:", *[f"  {i}. {s['file']} — {s['why']}" for i, s in enumerate(walk["steps"], 1)],
                  "- Reader placed:", *[f"  - {p['path']} — {p['change']}" for p in walk["placed"]],
                  "- Reader copied:", *([f"  - {c['path']} — {c['why']}" for c in walk["copied"]] or [f"  - {NONE}"]),
                  "- Reader got stuck:", *([f"  - {s}" for s in walk["stuck"]] or [f"  - {NONE}"]),
                  "- Reader guessed:", *([f"  - {g}" for g in walk["guessed"]] or [f"  - {NONE}"]), ""]
    return "\n".join(lines).rstrip("\n")


def fix_prompt(out) -> dict:
    doc = _need(out, INTAKE)
    rejected = rolekit.rejected(out, FIX_ROLE)
    values = {"rejection": rolekit.rejects_text(rejected), "misses": _miss_lines(out),
              "entry": "\n".join(f"- {e}" for e in doc["entry"]), "guide": KINDS[0], "model": KINDS[1], "block": KINDS[2],
              "lang": doc["lang"]}
    return prompt.emit(FIX_NODE, values, {"rejected": bool(rejected)}, prompt.round_of(FIX_NODE))


def fix_problems(out, reply) -> list:
    if not isinstance(reply, dict) or not isinstance(reply.get("fixes"), list):
        return ["返答に fixes（直しの配列）が無い"]
    missed = {r["id"] for r in _need(out, COMPARE) if not r["hit"]}
    bad, seen = [], set()
    for i, fix in enumerate(reply["fixes"]):
        if not isinstance(fix, dict) or not all(isinstance(fix.get(k), str) and fix[k].strip()
                                                for k in ("request", "kind", "where", "change", "why")):
            bad.append(f"fixes[{i}] は {{request, kind, where, change, why}} の空でない字の組")
            continue
        if fix["request"] not in missed:
            bad.append(f"fixes[{i}]: request {fix['request']!r} は外れた頼みの id でない（外れた頼み: {sorted(missed)}）")
        if fix["kind"] not in KINDS:
            bad.append(f"fixes[{i}]: kind は {'・'.join(KINDS)} のどれか")
        why = _path_problem(fix["where"])
        if why:
            bad.append(f"fixes[{i}]: {why}")
        seen.add(fix["request"])
    left = sorted(missed - seen)
    if left:
        bad.append(f"直しの無い外れた頼み: {left}（全部の外れた頼みに 1 つ以上）")
    return bad


def fix_accept(out, raw) -> dict:
    out = pathlib.Path(out)

    def take(reply):
        try:
            bad = fix_problems(out, reply)
        except ValueError as e:
            return {"ok": False, "reason": f"置き場の控えが読めない: {e}"}
        if not bad:
            jsonfile.write(out / FIXES, reply["fixes"])
        return {"ok": not bad, "reason": " / ".join(bad)}
    got = rolekit.accept_round(out, FIX_ROLE, raw, take)
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


# ---------------------------------------------------------------- 出口
def finish(out) -> dict:
    out = pathlib.Path(out)
    doc = _read(out / INTAKE) or {}
    walks = _read(out / WALKS, {})
    compared = {r["id"]: r for r in _read(out / COMPARE, [])}
    fixes = _read(out / FIXES, [])
    reasons, status = [], "ok"
    if not doc:
        status, reasons = "failed", ["入口の控えが無い（入口の node が落ちた）"]
    elif doc.get("reason"):
        status, reasons = "failed", [doc["reason"]]
    rows = []
    for req in doc.get("requests", []) if status == "ok" else []:
        walk = walks.get(req["id"])
        if walk is None:
            status = "failed"
            reasons.append(f"頼み {req['id']} を辿っていない（読み手の輪が落ちたか尽きた）")
            continue
        if "gave_up" in walk:
            status = "failed"
            reasons.append(f"頼み {req['id']} の読み手の返答を諦めた: {walk['gave_up']}")
        rows.append({"id": req["id"], "request": req["request"], "closes": req["closes"],
                     "hit": compared.get(req["id"], {}).get("hit"), **{k: walk.get(k, []) for k in
                                                                     ("steps", "placed", "copied", "stuck", "guessed")},
                     "gave_up": walk.get("gave_up", "")})
    missed = [r["id"] for r in rows if r["hit"] is False]
    if missed and not (out / FIXES).is_file():
        status = "failed"
        reasons.append(f"外れた頼み {missed} の案内の直しが受け付けを通らなかった: "
                       f"{rolekit.given_up_reason(out, FIX_ROLE) or 'ループが走らなかったか落ちた'}")
    paths = None
    if rows:
        jsonfile.write(out / PATHS, rows)
        paths = ports.pointer(out / PATHS)
    hits = sum(r["hit"] is True for r in rows)
    report = [f"- 頼み {r['id']}: " + ("当たり" if r["hit"] else "外れ" if r["hit"] is False else "辿れなかった")
              + (f"（置いた所 {', '.join(norm(p['path']) for p in r['placed'])}。閉じるべき所 {', '.join(r['closes'])}）"
                 if r["hit"] is not None else "") for r in rows]
    report += [f"- 案内の直し（頼み {f['request']}・{f['kind']}）: {f['where']} — {f['change']}" for f in fixes]
    if status != "ok":
        report.append(f"- 案内の道の目が最後まで回らなかった: {'／'.join(reasons)}")
    return {"ok": status == "ok", "status": status, "reason": "／".join(reasons), "paths": paths, "fixes": fixes,
            "hits": hits, "misses": len(missed), "report": report}
