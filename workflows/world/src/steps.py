"""世界の解の block の中身（docs/design/world.md。lib/worldblk.py と lib/judge_accept.py の world_* を、port の値で受ける形に写した物）。

依頼の行ごとに、依頼の解き方と対象の名を外した問題の類に言い直させ（言い直す役。道具ゼロ）、言い直した問題の類・作業・検索語・
依頼の解き方だけを見せた web の役に、世の中の定石の抜き書きを集めさせて類ごとの定石と依頼の解き方との比べを判断させ（web の役。
web の検索と取得だけ）、抜き書きを機械が取り直した本文で照らし（src/excerpts）、行を place の行のファイル（WORLD_FILE）に書く。指示の文は
prompts/ の md が持ち、ここは材料の行と値だけを組む。

place のファイル（名はこのモジュールだけが持つ。world.md の 1.4）:
- intake.json: {findings, purpose_text, means, web, lang, reason}
- classes.json（言い直す役の受け付けが通した行）: [{finding, where, class_id, problem, activity, proposed, queries}]
- plan.json（類を決めた後）: {over, taken}
- judge-input.json・judged.json（web の役の材料と、受け付けが通した行）
- verified.json（web の役の受け付けが抜き書きを照らした結果）: {kept, dropped, offline, over_excerpts}
- rejects-classes.json・rejects-judge.json: 出し直しの輪の拒否の控え（lib/rolekit の accept_round が積む）。拒めば同じ会話で出し直させ、
  rolekit.GIVE_UP_AFTER 回目の拒否で輪を抜ける（run は止めない。出口の status: failed と reason に残す）
- world-classes-prompt-<n>.md・world-judge-prompt-<n>.md（prompt.emit が書く）・WORLD_FILE（行）・state.json（段の控え）

上限（元の計画の 5.4 節）: 類は MAX_CLASSES・検索語は類ごとに MAX_QUERIES（全部の行に 1 本以上）・抜き書きは返答の全部で
MAX_EXCERPTS × 取った類の数（越えた分は頭から取り、取らなかった数を残す）。類の id は問題の類の文を正規化した字の hash で、対象の名を
持たない。web の役の返答の根拠（sources）と印（basis）は機械だけが決める: 取り直した本文に字のまま在る抜き書きを指す根拠だけ残し、
残れば basis: web、残りが無い行は basis: knowledge。web に出ない run（web が off・取り直しが全部網に届かない）も止めない。
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import ports
import prompt
import requestrows

import jsonfile   # lib/
import oneline    # lib/
import rolekit    # lib/。loop の数え・却下の控え・諦め
import webget     # lib/。取り直しの口
import worldmark  # lib/。行の欄と語（ほかの block も読む行の形の正本）

from src import excerpts, report

INTAKE, CLASSES, PLAN, VERIFIED, JUDGE_INPUT, JUDGED, STATE = (
    "intake.json", "classes.json", "plan.json", "verified.json", "judge-input.json", "judged.json", "state.json")
WORLD_FILE = worldmark.WORLD_FILE
CLASSES_ROLE, JUDGE_ROLE = "classes", "judge"   # 却下の控えの名（rejects-<名>.json）
CLASSES_NODE, JUDGE_NODE, OFFLINE_NODE = "world-classes", "world-judge", "world-judge-offline"   # AI の node の id（prompts/<id>.md）
PROMPT_ERROR = "prompt-error.json"   # 指示が組めなかった node と理由（prep が書き、出口の理由に載せる）
OWN_FILES = (INTAKE, CLASSES, PLAN, VERIFIED, JUDGE_INPUT, JUDGED, STATE, WORLD_FILE, PROMPT_ERROR,
             *(rolekit.rejects_path(pathlib.Path(), r).name for r in (CLASSES_ROLE, JUDGE_ROLE)))
OWN_PROMPTS = tuple(f"{node}-prompt-*.md" for node in (CLASSES_NODE, JUDGE_NODE, OFFLINE_NODE))
MAX_CLASSES, MAX_QUERIES, MAX_EXCERPTS = 5, 3, 6
MIN_CHALLENGE = 20   # differs の challenge の字の下限
MAX_BODY = 2 * 1024 * 1024
HEADERS = {"User-Agent": "works-world/1", "Accept": "text/html, text/plain;q=0.9, */*;q=0.5"}
NOT_GIVEN = "(not given)"
EMPTY = "依頼の行が無い"   # 空の依頼の出口の reason（status は ok・rows は null。docs/design/world.md の 1.2）
NO_MEANS = "(none proposed)"


# ---------------------------------------------------------------- 置き場
def _read(path, default=None):
    return jsonfile.read_or(path, default)


def _write(path, doc) -> None:
    jsonfile.write(path, doc)


def _need(out, name):
    got = _read(pathlib.Path(out) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(out) / name} が無いか読めない")
    return got


def class_id(problem: str) -> str:
    """問題の類の id（正規化した文の sha256 の頭 12 字）。同じ字の類は同じ id になる"""
    return "w-" + hashlib.sha256(excerpts.normalize(problem).encode("utf-8")).hexdigest()[:12]


def fetch(url):
    """機械が同じ URL を取り直す口（抜き書きの照らしの get）"""
    return webget.http_get(url, HEADERS, MAX_BODY)


# ---------------------------------------------------------------- 入口
def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def intake(out, *, request, purpose, means, web, lang) -> dict:
    """port の字を読み、置き場のこの block のファイルを消してから intake.json を書く。返り {due, findings, reason}（due は言い直す役を
    起こすか）。port が読めない時も止めない（reason に残し、due は偽。出口が status: failed にする）"""
    out = pathlib.Path(out)
    for name in OWN_FILES:
        (out / name).unlink(missing_ok=True)
    for pattern in OWN_PROMPTS:
        for path in out.glob(pattern):
            path.unlink()
    doc = {"findings": [], "purpose_text": "", "means": [], "web": True, "lang": prompt.lang(lang), "reason": ""}
    try:
        doc["web"] = _port("web", lambda: ports.choice(web, ("on", "off"))) == "on"
        doc["findings"] = _port("request", lambda: requestrows.findings(request))
        doc["purpose_text"] = ports.text(purpose).strip()
        doc["means"] = [m.strip() for m in _port("means", lambda: ports.json(means, "means.schema.json")) if m.strip()]
    except ValueError as e:
        doc["reason"] = oneline.one_line(e)
    _write(out / INTAKE, doc)
    return {"due": bool(doc["findings"]) and not doc["reason"], "findings": len(doc["findings"]), "reason": doc["reason"]}


# ---------------------------------------------------------------- 輪の控え（拒否は rolekit の控えに積む）
def _emit(out, node: str, values: dict, when: dict) -> dict:
    """prompt.emit。組めなければ理由を place に残してから落ちる（出口の理由に載る）"""
    try:
        return prompt.emit(node, values, when, prompt.round_of(node))
    except prompt.PromptError as e:
        _write(pathlib.Path(out) / PROMPT_ERROR, {"node": node, "reason": oneline.one_line(e)})
        raise


def _why_failed(out, role) -> str:
    """輪が通らなかった役の理由（指示が組めなかった訳か、諦めた文か、落ちた周の最後の拒否の文。どれも無ければ走らなかった）"""
    broken = _read(pathlib.Path(out) / PROMPT_ERROR)
    if isinstance(broken, dict):
        return f"{broken.get('node')} の指示が組めない: {broken.get('reason')}"
    rejected = rolekit.rejected(out, role)
    return rolekit.given_up_reason(out, role) or (rejected[-1] if rejected else "ループが走らなかったか落ちた")


# ---------------------------------------------------------------- 言い直す役
def _finding_lines(findings) -> str:
    out = []
    for i, f in enumerate(findings, 1):
        out.append(f"{i}. where: {f.get('where')}")
        out += [f"   {k}: {f[k]}" for k in ("text", "mechanism", "measured", "false_positive_if") if isinstance(f.get(k), str)]
    return "\n".join(out)


def classes_prompt(out) -> dict:
    """言い直す役の指示を組んで place に書く。返り {prompt}"""
    doc = _need(out, INTAKE)
    rejected = rolekit.rejected(out, CLASSES_ROLE)
    values = {"rejection": rolekit.rejects_text(rejected), "findings": _finding_lines(doc["findings"]),
              "purpose": doc["purpose_text"] or NOT_GIVEN, "means": "\n".join(f"- {m}" for m in doc["means"]),
              "finding_count": len(doc["findings"]), "max_queries": MAX_QUERIES, "lang": doc["lang"]}
    return _emit(out, CLASSES_NODE, values, {"rejected": bool(rejected), "means": bool(doc["means"])})


def class_problems(doc: dict, reply) -> list:
    rows = reply.get("classes") if isinstance(reply, dict) else None
    if not isinstance(rows, list):
        return ["返答に classes（行の配列）が無い"]
    findings = doc["findings"]
    banned = excerpts.banned_tokens(findings)
    seen, out = [], []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            out.append(f"classes[{i}] が JSON のオブジェクトでない")
            continue
        n = r.get("finding")
        head = f"classes[{i}]（依頼の行 {n}）"
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(findings):
            out.append(f"{head}: finding は依頼の行の番号 1〜{len(findings)}")
            continue
        if n in seen:
            out.append(f"{head}: 同じ依頼の行の 2 つ目")
        seen.append(n)
        for key in ("problem", "activity"):
            if not isinstance(r.get(key), str) or not r[key].strip():
                out.append(f"{head}: {key} が空")
        if not isinstance(r.get("proposed"), str):
            out.append(f"{head}: proposed が字でない（示していなければ空の字）")
        qs = r.get("queries")
        if not isinstance(qs, list) or not all(isinstance(q, str) and q.strip() for q in qs) or len(qs) > MAX_QUERIES:
            out.append(f"{head}: queries は空でない字の配列（{MAX_QUERIES} 本まで）")
            qs = []
        elif not qs:
            out.append(f"{head}: queries が無い（全部の行に 1 本以上）")
        texts = [("problem", r.get("problem")), ("activity", r.get("activity")), ("proposed", r.get("proposed"))]
        for key, text in texts + [("queries", q) for q in qs]:   # web の役に渡る文は全部、対象の名を持たない
            hit = excerpts.text_problems(text, banned)
            if hit:
                out.append(f"{head}: {key} に依頼の行の識別子 {hit} が在る")
    missing = [n for n in range(1, len(findings) + 1) if n not in seen]
    if missing:
        out.append(f"行の無い依頼の行: {missing}（全部の行に 1 つずつ）")
    return out


def _take_classes(out, reply) -> dict:
    doc = _need(out, INTAKE)
    bad = class_problems(doc, reply)
    if not bad:
        rows = []
        for r in sorted(reply["classes"], key=lambda x: x["finding"]):
            rows.append({"finding": r["finding"], "where": doc["findings"][r["finding"] - 1]["where"],
                         "class_id": class_id(r["problem"]), "problem": r["problem"].strip(), "activity": r["activity"].strip(),
                         "proposed": r["proposed"].strip(), "queries": [q.strip() for q in r["queries"]]})
        _write(pathlib.Path(out) / CLASSES, rows)
    return {"ok": not bad, "reason": " / ".join(bad)}


# ---------------------------------------------------------------- 類を決める
def pick(out) -> dict:
    """言い直しの行から、取る類（MAX_CLASSES まで）を決めて plan.json に書く。返り {due, reason}（due は web の役を起こすか）"""
    out = pathlib.Path(out)
    doc = _read(out / INTAKE)
    if doc is None:
        return {"due": False, "web": False, "reason": "入口の控えが無い（入口の node が落ちた）"}
    rows = _read(out / CLASSES)
    if not isinstance(rows, list):
        _write(out / PLAN, {"over": [], "taken": []})
        return {"due": False, "web": bool(doc.get("web", True)),
                "reason": doc.get("reason") or (EMPTY if not doc.get("findings") else _why_failed(out, CLASSES_ROLE))}
    taken, over = [], []
    for r in rows:
        if r["class_id"] not in taken and len(taken) >= MAX_CLASSES:
            over.append(r["finding"])
        elif r["class_id"] not in taken:
            taken.append(r["class_id"])
    _write(out / PLAN, {"over": over, "taken": taken})
    return {"due": bool(taken), "web": bool(doc.get("web", True)), "reason": "" if taken else "取る類が無い"}


# ---------------------------------------------------------------- web の役
def _judge_rows(out) -> list:
    """web の役に渡す行（取った類の、依頼の行ごと）。言い直しの行の問題の類・作業・検索語・依頼の解き方だけで、依頼の行の本文は持たない
    （where は機械が行に写すために持ち、役の指示には貼らない）"""
    out = pathlib.Path(out)
    rows, pl = _need(out, CLASSES), _need(out, PLAN)
    return [{k: r[k] for k in ("finding", "where", "class_id", "problem", "activity", "proposed", "queries")}
            for r in rows if r["class_id"] in pl["taken"]]


def _class_lines(rows) -> str:
    by_class = {}
    for r in rows:
        by_class.setdefault(r["class_id"], []).append(r)
    lines = []
    for cid, group in by_class.items():
        first = group[0]
        lines += [f"### Class {cid}", "", f"- Problem class: {first['problem']}", f"- Activity: {first['activity']}",
                  *[f"- Query: {q}" for q in first["queries"]],
                  *[f"- Means of request line {r['finding']}: {r['proposed'] or NO_MEANS}" for r in group], ""]
    return "\n".join(lines).rstrip("\n")


def judge_prompt(out, node: str = JUDGE_NODE) -> dict:
    """web の役の指示を組んで place に書く。返り {prompt}。web が on の run は node JUDGE_NODE（web の検索と取得を持つ）、off の run は
    OFFLINE_NODE（道具を持たない）で、どちらも同じ部品 md（prompts/parts/world-judge.md）から組む。外への検索の決まり（query-rule）は JUDGE_NODE の md だけが持つ。run の web と node が食い違えば配線の誤り"""
    out = pathlib.Path(out)
    doc = _need(out, INTAKE)
    if (node == OFFLINE_NODE) == bool(doc["web"]):
        raise ValueError(f"web が {'on' if doc['web'] else 'off'} の run で {node} の指示を組もうとした（pick の web で輪を選ぶ配線の誤り）")
    if not (out / JUDGE_INPUT).is_file():
        _write(out / JUDGE_INPUT, _judge_rows(out))
    rows = _need(out, JUDGE_INPUT)
    rejected = rolekit.rejected(out, JUDGE_ROLE)
    values = {"rejection": rolekit.rejects_text(rejected), "classes": _class_lines(rows),
              "max_excerpts": MAX_EXCERPTS * len({r["class_id"] for r in rows}), "min_excerpt": excerpts.MIN_EXCERPT,
              "same": worldmark.SAME, "differs": worldmark.DIFFERS, "none": worldmark.NONE, "min_challenge": MIN_CHALLENGE,
              "lang": doc["lang"]}
    when = {"rejected": bool(rejected), "web": bool(doc["web"])}
    if node == JUDGE_NODE:
        when["spawns"] = False   # query-rule は道具を持つ node の md だけが持つ（offline の md には無い）
    return _emit(out, node, values, when)


def _excerpts(reply) -> tuple:
    """返答の excerpts（無ければ抜き書き無し）。(抜き書きの配列, 形の問題の文の配列)"""
    got = reply.get("excerpts", []) if isinstance(reply, dict) else []
    if not isinstance(got, list):
        return [], ["excerpts は {id, url, excerpt} の配列"]
    took, bad, ids = [], [], set()
    for i, e in enumerate(got):
        if not isinstance(e, dict) or not all(isinstance(e.get(k), str) for k in ("id", "url", "excerpt")) or not e["id"].strip():
            bad.append(f"excerpts[{i}] が {{id, url, excerpt}} の字の組でない（id は空でない字）")
        elif e["id"] in ids:
            bad.append(f"excerpts[{i}]: id {e['id']} が返答の中で重なる")
        else:
            ids.add(e["id"])
            took.append({k: e[k] for k in ("id", "url", "excerpt")})
    return took, bad


def judge_problems(rows: list, findings: list, reply, web: bool = True) -> list:
    """web の役の返答の拒否の文。web が off の run は抜き書きと根拠を見ない（機械が捨てる）。印 basis は見ない（機械が付ける）"""
    got = reply.get("rows") if isinstance(reply, dict) else None
    if not isinstance(got, list):
        return ["返答に rows（行の配列）が無い"]
    want = {r["finding"]: r for r in rows}
    banned = excerpts.banned_tokens(findings)
    took, out = _excerpts(reply) if web else ([], [])
    ids = {e["id"] for e in took}
    seen = []
    for i, r in enumerate(got):
        if not isinstance(r, dict):
            out.append(f"rows[{i}] が JSON のオブジェクトでない")
            continue
        n = r.get("finding")
        head = f"rows[{i}]（依頼の行 {n}）"
        if n not in want:
            out.append(f"{head}: finding は渡した依頼の行の番号（{sorted(want)}）")
            continue
        if n in seen:
            out.append(f"{head}: 同じ依頼の行の 2 つ目")
        seen.append(n)
        base = want[n]
        if not isinstance(r.get("practice"), str) or not r["practice"].strip():
            out.append(f"{head}: practice が空")
        else:
            hit = excerpts.text_problems(r["practice"], banned)
            if hit:
                out.append(f"{head}: practice に依頼の行の識別子 {hit} が在る")
        src = r.get("sources")
        if not isinstance(src, list) or not all(isinstance(s, str) for s in src):
            out.append(f"{head}: sources は抜き書きの id の配列")
            src = []
        stray = [s for s in src if s not in ids] if web else []
        if stray:
            out.append(f"{head}: sources {stray} は返答の excerpts の id でない（在るのは {sorted(ids) or '無し'}）")
        for key in ("applies", "not_applies", "challenge"):
            if not isinstance(r.get(key), str):
                out.append(f"{head}: {key} が字でない（無ければ空の字）")
        verdict = r.get("verdict")
        if verdict not in worldmark.VERDICTS:
            out.append(f"{head}: verdict は {'・'.join(worldmark.VERDICTS)} のどれか")
        elif (verdict == worldmark.NONE) != (not base["proposed"]):
            out.append(f"{head}: verdict {worldmark.NONE} は依頼が解き方を示していない行だけ（この行の依頼の解き方: "
                       f"{base['proposed'] or '無し'}）")
        elif verdict == worldmark.DIFFERS and len(str(r.get("challenge") or "").strip()) < MIN_CHALLENGE:
            out.append(f"{head}: verdict {worldmark.DIFFERS} は challenge（「依頼は X、定石は Y。…でない限り Y を選ぶ」。"
                       f"{MIN_CHALLENGE} 字以上）が要る")
    missing = sorted(set(want) - set(seen))
    if missing:
        out.append(f"行の無い依頼の行: {missing}（全部の行に 1 つずつ）")
    return out


def _check_excerpts(out, reply, web: bool, get, classes: int) -> dict:
    """返答の抜き書きを、機械が取り直した本文で照らして verified.json に書く。返り {抜き書きの id: {id, url, excerpt}}（残った物）。
    web が off の run は取り直さず、残る抜き書きは無い"""
    took = _excerpts(reply)[0] if web else []
    capped = took[:MAX_EXCERPTS * classes]
    got = excerpts.verify(capped, get)
    _write(pathlib.Path(out) / VERIFIED, {"kept": got["kept"], "dropped": got["dropped"], "offline": got["offline"],
                                          "over_excerpts": len(took) - len(capped)})
    return {k["id"]: k for k in got["kept"]}


def _take_judge(out, reply, get) -> dict:
    out = pathlib.Path(out)
    rows = _need(out, JUDGE_INPUT)
    doc = _need(out, INTAKE)
    bad = judge_problems(rows, doc["findings"], reply, doc["web"])
    if not bad:
        kept = _check_excerpts(out, reply, doc["web"], get, len({r["class_id"] for r in rows}))
        judged = []
        for j in sorted(reply["rows"], key=lambda r: r["finding"]):
            sources = [kept[s] for s in dict.fromkeys(j["sources"]) if s in kept]
            judged.append({**j, "sources": sources, "basis": worldmark.WEB if sources else worldmark.KNOWLEDGE})
        _write(out / JUDGED, judged)
    return {"ok": not bad, "reason": " / ".join(bad)}


def accept(out, role: str, raw, get=None) -> dict:
    """言い直す役（role CLASSES_ROLE）か web の役（JUDGE_ROLE）の返答の字 raw を受け付ける。返り {ok, done, reason}。返答が JSON で
    ない・置き場の控えが無い時も拒否として返す。get は抜き書きの取り直しの口（既定は fetch。試験が差し替える）"""
    def take(reply):
        try:
            if role == CLASSES_ROLE:
                return _take_classes(out, reply)
            return _take_judge(out, reply, get or fetch)
        except (ValueError, OSError) as e:
            return {"ok": False, "reason": f"置き場の控えが読めない: {e}"}
    got = rolekit.accept_round(out, role, raw, take, reject=lambda why: {"ok": False, "reason": why})
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


# ---------------------------------------------------------------- 出口
def _rows(out) -> list:
    base = {r["finding"]: r for r in _read(pathlib.Path(out) / JUDGE_INPUT) or []}
    rows = []
    for j in _read(pathlib.Path(out) / JUDGED) or []:
        b = base[j["finding"]]
        rows.append({"finding": b["finding"], "where": b["where"], "class_id": b["class_id"], "problem": b["problem"],
                     "activity": b["activity"], "practice": j["practice"].strip(), "sources": j["sources"],
                     "applies": j["applies"].strip(), "not_applies": j["not_applies"].strip(),
                     "versus": {"proposed": b["proposed"], "verdict": j["verdict"],
                                "challenge": j["challenge"].strip() if j["verdict"] == worldmark.DIFFERS else ""},
                     "basis": j["basis"]})
    return rows


def finish(out) -> dict:
    """行を WORLD_FILE に、段の控えを state.json に書き、block の返り {ok, status, reason, rows, classes, dropped, report} を返す。
    落ちた段が在っても落ちない（status: failed と reason）。行は書いた後に lib/worldmark の行の形で読み戻して確かめる"""
    out = pathlib.Path(out)
    intake_doc = _read(out / INTAKE) or {}
    pl = _read(out / PLAN) or {}
    ver = _read(out / VERIFIED) or {}
    world = out / WORLD_FILE
    reasons, status = [], "ok"
    if not intake_doc:
        status, reasons = "failed", ["入口の控えが無い（入口の node が落ちた）"]
    elif intake_doc.get("reason"):
        status, reasons = "failed", [intake_doc["reason"]]
    elif intake_doc.get("findings"):
        if not (out / CLASSES).is_file():
            status = "failed"
            reasons.append(f"言い直す役の返答が受け付けを通らなかった: {_why_failed(out, CLASSES_ROLE)}")
        elif not pl:
            status = "failed"
            reasons.append("類を決める node が落ちた（類を決めた控えが無い）")
        elif pl.get("taken") and not (out / JUDGED).is_file():
            status = "failed"
            reasons.append(f"集めて判断する役の返答が受け付けを通らなかった: {_why_failed(out, JUDGE_ROLE)}")
    rows = _rows(out) if status == "ok" else []
    world.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    try:
        worldmark.rows(world)
    except ValueError as e:
        status, rows = "failed", []
        reasons.append(f"書いた行が行の形に合わない: {e}")
        world.write_text("", encoding="utf-8")
    if intake_doc and not intake_doc.get("reason") and not intake_doc.get("findings"):
        reasons.append(EMPTY)
    if not intake_doc.get("web", True) and pl.get("taken"):
        reasons.append(f"web が off（{worldmark.NOT_WEB}）")
    elif ver.get("offline"):
        reasons.append(f"網に届かなかった（{worldmark.NOT_WEB}）")
    if pl.get("over"):
        reasons.append(f"類の上限 {MAX_CLASSES} を越えた依頼の行 {pl['over']} は行を書いていない")
    reason = "／".join(reasons)
    classes = len(pl.get("taken") or [])
    dropped = len(ver.get("dropped") or []) + int(ver.get("over_excerpts") or 0)
    _write(out / STATE, {"status": status, "reason": reason, "world_file": WORLD_FILE, "classes": classes, "dropped": dropped})
    return {"ok": status == "ok", "status": status, "reason": reason, "rows": ports.pointer(world) if rows else None,
            "classes": classes, "dropped": dropped,
            "report": report.lines(status=status, reason=reason, rows=rows, classes=classes, dropped=dropped)}

