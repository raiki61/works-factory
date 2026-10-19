"""run の頭の深さの block の中身（docs/design/head-depth.md。lib/headdepth.py の facts・gate・brief・check と、判定の
head_depth_prep・head_depth_accept を、port の値で受ける形に写した物）。

依頼の行ごとの字と番地の実在を測り、役を起こす前の機械の止めを通す。役は行ごとに「まだ決まっていない事の種類」を依頼の字と
リポジトリの行の引用で選び、受け付けが引用の実在を照らして、一番重い種類から段を引く。照らしが通らない・役が走らない時は標準。
群の選び（既定の模型か effort を替える群）は照らして控えに残すだけで、走りには効かない。指示の文は prompts/head-depth.md が持ち、
ここは材料と値だけを組む。

place のファイル（名はこのモジュールだけが持つ。head-depth.md の 1.4）:
- intake.json: {facts, due, failed, reason, lang}
- depth-head.json: 控え（headdepth.record の形。入口が標準か止めの段で先に書き、受け付けが書き直す）
- head-depth-prompt-<n>.md（prompt.emit が書く）・rejects-head-depth.json（lib/rolekit の accept_round が積む拒否の控え）
"""
from __future__ import annotations

import pathlib

import ports
import prompt
import requestrows

import cite          # lib/。番地の規則と引用の照らし
import headdepth     # lib/。段の語 LIGHT・STANDARD・HEAVY・HEADS と控えの形・読み
import jsonfile      # lib/
import launchgroups  # lib/。群の表と群の選びの照らし
import oneline       # lib/
import rolekit       # lib/。loop の数え・却下の控え・諦め

from src import report

INTAKE_FILE = "intake.json"
RECORD_FILE = "depth-head.json"
ROLE = "head-depth"        # 却下の控えの名（rejects-head-depth.json）
NODE = "head-depth"        # AI の node の id（prompts/head-depth.md）
LIGHT, STANDARD, HEAVY, HEADS = headdepth.LIGHT, headdepth.STANDARD, headdepth.HEAVY, headdepth.HEADS
# port thickness の語（choice の語は ASCII だけ。形の検査 FORM）→ 名指しの段（auto は名指さない）。段の並びは HEADS と同じ
THICKNESS = {"auto": "", "light": LIGHT, "standard": STANDARD, "heavy": HEAVY}
NONE, CAUSE, SHAPE, SCOPE = "無し", "原因", "形", "範囲"
UNKNOWNS = {NONE: LIGHT, CAUSE: STANDARD, SHAPE: STANDARD, SCOPE: HEAVY}   # 未知の種類 → 段。役の output_format の unknown の enum の並び
WHERE_SPAN = 30   # 軽量の根拠の where の行の範囲の幅の上限。直す所を 1 画面で名指せない範囲はファイルを指すのと変わらない
NO_ROWS = "依頼の行が無い（行ごとの未知の種類を引けない）"
NO_REPLY = "役の返答が受け付けに届いていない（役が走らなかったか落ちた）"
NOT_ACCEPTED = "役の返答が受け付けを通らない（{why}）"
UNCHECKED = "機械の確かめが無い（tdd_suite も test_cmd も空）"
OWN_FILES = (INTAKE_FILE, RECORD_FILE, rolekit.rejects_path(pathlib.Path(), ROLE).name)
OWN_PROMPTS = (f"{NODE}-prompt-*.md",)


# ---------------------------------------------------------------- 置き場
def _need(out, name):
    got = jsonfile.read_or(pathlib.Path(out) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(out) / name} が無いか読めない")
    return got


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def _write_record(out, doc) -> None:
    jsonfile.write(pathlib.Path(out) / RECORD_FILE, doc)


# ---------------------------------------------------------------- 事実と機械の止め
def _squash(text) -> str:
    return "".join(str(text or "").split())


def _place(repo, where) -> dict:
    """番地 where（`<パス>` か cite の名指し）のファイルが根の中に在るか・行の範囲がその中か（規則は cite.file_problem・cite.problem）"""
    where = str(where or "").strip()
    m = cite.CITE.match(where)
    path_ok = bool(where) and not cite.file_problem(m["path"] if m else where, repo)
    return {"path_ok": path_ok, "lines_ok": path_ok and not (m and cite.problem(where, repo))}


def facts(rows, *, has_checks: bool, spec: bool, design_only: bool, forced: str, repo) -> dict:
    """依頼の行ごとの字と番地の実在・機械の確かめの有無・仕様の段・設計だけ・呼ぶ人の段の名指し forced（段の語か空）"""
    items = [{"item": n, "text": str(r.get("text") or ""), "where": str(r.get("where") or ""), **_place(repo, r.get("where"))}
             for n, r in enumerate((r for r in rows or [] if isinstance(r, dict)), start=1)]
    return {"items": items, "test_cmd": has_checks, "spec": spec, "design_only": design_only,
            "forced": forced}


def gate(f: dict) -> tuple:
    """役を起こす前の機械の止め (go, 段, 訳)。go が偽なら決めた段と訳で控えを書き、役を起こさない"""
    if f["forced"]:
        return False, f["forced"], f"入力 thickness の名指し（{f['forced']}）"
    for stop, why in ((f["spec"], "仕様の段を挟む run"),
                      (f["design_only"], "設計だけの run"),
                      (not f["items"], "依頼の行が無い（差分だけの run）"),
                      (not f["test_cmd"], f"{UNCHECKED}——代わりの最後のテストが測れない")):
        if stop:
            return False, STANDARD, why
    return True, "", ""


# ---------------------------------------------------------------- 入口
def intake(out, *, request, has_checks, thickness, spec, design_only, lang, repo) -> dict:
    """port を読み、この block のファイルを消して、事実と機械の止めの控えを書く。返り {due, reason}。落ちた時は控えを標準で書き、
    intake.json に failed と訳を書き、due は偽（深さは判定を止めない）"""
    out = pathlib.Path(out)
    doc = {"facts": {}, "due": False, "failed": False, "reason": "", "lang": ""}
    try:
        rows = _port("request", lambda: requestrows.findings(request))
        flags = {"has_checks": _port("has_checks", lambda: ports.flag(has_checks)),
                 "spec": _port("spec", lambda: ports.flag(spec)),
                 "design_only": _port("design_only", lambda: ports.flag(design_only))}
        forced = THICKNESS[_port("thickness", lambda: ports.choice(ports.text(thickness).strip() or "auto", tuple(THICKNESS)))]
        doc["lang"] = ports.text(lang).strip()
        for name in OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        doc["facts"] = facts(rows, forced=forced, repo=repo, **flags)
        go, tier, why = gate(doc["facts"])
        _write_record(out, headdepth.record(tier or STANDARD, why or NO_REPLY, facts_doc=doc["facts"]))
        doc.update(due=go, reason=why)
        jsonfile.write(out / INTAKE_FILE, doc)
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（深さは判定を止めない。出口が status: failed にする）
        reason = oneline.one_line(f"run の頭の深さの支度が落ちた（{type(e).__name__}: {e}）")
        _write_record(out, headdepth.record(STANDARD, reason))
        jsonfile.write(out / INTAKE_FILE, {**doc, "due": False, "failed": True, "reason": reason})
        return {"due": False, "reason": reason}
    return {"due": go, "reason": why}


# ---------------------------------------------------------------- 指示
def rows_text(f: dict) -> str:
    """材料の行（機械が測った物）。行ごとに 2 行"""
    return "\n".join(f"- Line {it['item']}: {it['text']}\n  - Location: {it['where'] or '(none)'} "
                     f"(file {'exists' if it['path_ok'] else 'missing'}, "
                     f"line range {'inside the file' if it['lines_ok'] else 'outside or unreadable'})"
                     for it in f["items"])


def groups_text() -> str:
    """群の行（launchgroups.GROUPS の並びのまま）"""
    return "\n".join(f"- `{name}`: {spec['what']} (default {spec['model']}, {spec['effort']})"
                     for name, spec in launchgroups.GROUPS.items())


def depth_prompt(out) -> dict:
    """役の指示を組んで place に書く。前の回までの却下は place の控えから全部。返り {prompt}"""
    out = pathlib.Path(out)
    doc = _need(out, INTAKE_FILE)
    rejected = rolekit.rejected(out, ROLE)
    values = {"rejection": rolekit.rejects_text(rejected), "light": LIGHT, "standard": STANDARD, "heavy": HEAVY,
              "none": NONE, "cause": CAUSE, "shape": SHAPE, "scope": SCOPE,
              "row_count": str(len(doc["facts"]["items"])), "rows": rows_text(doc["facts"]),
              "models": ", ".join(launchgroups.MODELS), "efforts": ", ".join(launchgroups.EFFORTS), "groups": groups_text(),
              "quote_min": str(cite.QUOTE_MIN), "where_span": str(WHERE_SPAN), "lang": prompt.lang(doc["lang"])}
    return prompt.emit(NODE, values, {"rejected": bool(rejected)}, prompt.round_of(NODE))


# ---------------------------------------------------------------- 受け付け
def _known(kind) -> bool:
    return isinstance(kind, str) and kind in UNKNOWNS


def tier_of(items) -> str:
    """行の並びの一番重い種類の段（HEADS の順）。引けない（行が無い・表に無い種類しか無い）時は標準"""
    tiers = [UNKNOWNS[it["unknown"]] for it in items or [] if isinstance(it, dict) and _known(it.get("unknown"))]
    return max(tiers, key=HEADS.index, default=STANDARD)


def _check_item(it: dict, rows: list, repo, span=WHERE_SPAN, code_optional=False) -> list:
    n = it.get("item")
    head = f"行 {n}: "
    where = str(it.get("where") or "").strip()
    quotes = ("cause_quote",) if code_optional and not where else ("cause_quote", "code_quote")
    out = [head + f"{name} が {cite.QUOTE_MIN} 字より短い" for name in quotes
           if len(_squash(it.get(name))) < cite.QUOTE_MIN]
    if not cite.quoted_in(it.get("cause_quote"), rows[n - 1].get("text"), norm=_squash):
        out.append(head + "cause_quote が依頼のその行の字の部分でない")
    if len(quotes) == 1:
        return out
    bad = cite.problem(where, repo)
    if bad:
        return out + [head + f"where が通らない（{bad}）"]
    m = cite.CITE.match(where)
    first, last = int(m["a"]), int(m["b"] or m["a"])
    if span is not None and last - first + 1 > span:
        return out + [head + f"where の行の範囲が {span} 行より広い（直す所を名指していない）"]
    lines = cite.resolved(m["path"], pathlib.Path(repo).resolve()).read_text(encoding="utf-8", errors="replace").splitlines()
    if not cite.quoted_in(it.get("code_quote"), "\n".join(lines[first - 1:last]), norm=_squash):
        out.append(head + f"code_quote が {where} の字に無い")
    return out


def check(reply, rows, repo) -> list:
    """役の返答の照らし。拒む訳の並び（空なら受ける）。rows は facts の items（text の欄で cause_quote を照らす）"""
    if not isinstance(reply, dict):
        return ["返答が object でない"]
    if not str(reply.get("why") or "").strip():
        return ["why が空"]
    rows = [r for r in rows or [] if isinstance(r, dict)]
    if not rows:
        return [NO_ROWS]
    items = [it for it in reply.get("items") or [] if isinstance(it, dict)]
    named = [it.get("item") for it in items]
    want = list(range(1, len(rows) + 1))
    if sorted(n for n in named if isinstance(n, int) and not isinstance(n, bool)) != want or len(named) != len(want):
        return [f"items が依頼の行 {len(rows)} 個をちょうど 1 度ずつ指していない（指した行: {named}）"]
    out = []
    for it in items:
        kind = it.get("unknown")
        if not _known(kind):
            out.append(f"行 {it['item']}: unknown が {'・'.join(UNKNOWNS)} のどれでもない（{kind!r}）")
        elif kind == NONE:
            out += _check_item(it, rows, repo)
        else:
            out += _check_item(it, rows, repo, span=None, code_optional=kind == CAUSE)
    return out


def take(out, raw, repo) -> dict:
    """受け付けの輪の 1 回（rolekit.accept_round）。返り {ok, done, reason}。3 回目の拒否で done（run は止めない）"""
    out = pathlib.Path(out)
    facts_doc = _need(out, INTAKE_FILE)["facts"]

    def refuse(why: str, role_why: str = "") -> dict:
        """控えは標準と拒みの訳。役の訳（返答の why）が在れば添える（3 回目で標準に落ちた時に報告の根拠に役の訳が残る）"""
        kept = f"{why}／役の訳: {role_why}" if role_why else why
        _write_record(out, headdepth.record(STANDARD, NOT_ACCEPTED.format(why=kept), facts_doc=facts_doc))
        return {"ok": False, "reason": why}

    def accept(reply) -> dict:
        gaps = check(reply, facts_doc["items"], repo)
        if gaps:
            said = reply.get("why") if isinstance(reply, dict) else ""
            return refuse("／".join(gaps), said.strip() if isinstance(said, str) else "")
        items = reply.get("items") or []
        _write_record(out, headdepth.record(tier_of(items), reply["why"].strip(), items=items, facts_doc=facts_doc,
                                            groups=launchgroups.choices(reply.get("groups"))))
        return {"ok": True, "reason": ""}

    got = rolekit.accept_round(out, ROLE, raw, accept, reject=refuse)
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


# ---------------------------------------------------------------- 出口
def _result(out, *, status: str, reason: str, doc: dict) -> dict:
    return {"ok": status == "ok", "status": status, "reason": reason, "tier": doc["depth"], "why": doc["why"],
            "rows": doc["items"], "record": ports.pointer(pathlib.Path(out) / RECORD_FILE),
            "report": [report.report_line(doc["depth"], doc["why"])]}


def fallback(out, why: str) -> dict:
    """出口が落ちた時: 控えを標準と訳で書き直し、status: failed で返す"""
    doc = headdepth.record(STANDARD, why)
    _write_record(out, doc)
    return _result(out, status="failed", reason=why, doc=doc)


def finish(out) -> dict:
    """block の返り。落ちた段が在っても落ちない（段は標準に倒れている）"""
    out = pathlib.Path(out)
    intake_doc = jsonfile.read_or(out / INTAKE_FILE)
    if not (out / RECORD_FILE).is_file():
        return fallback(out, "入口の控えが無い（入口の node が落ちた）")
    doc = headdepth.read_file(out / RECORD_FILE)
    if not isinstance(intake_doc, dict):
        return fallback(out, "入口の控えが無い（入口の node が落ちた）")
    if intake_doc.get("failed"):
        return _result(out, status="failed", reason=str(intake_doc.get("reason") or "入口が落ちた"), doc=doc)
    if intake_doc.get("due") and not doc["items"]:
        return _result(out, status="failed", doc=doc,
                       reason=rolekit.given_up_reason(out, ROLE) or str(doc["why"]))
    return _result(out, status="ok", reason="", doc=doc)
