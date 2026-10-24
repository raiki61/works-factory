"""修正案の役の指示に入れる値と段落の真偽を組む（docs/design/plan.md の 2.3・3.3）。決まった文（見出し・頼み・決まり）は持たず
prompts/plan-writer.md と prompts/plan-writer-fix.md と共通の断片に置く。ここは材料の行（単位ごと・項目ごとの行）と値だけを組む。
項目ごとに繰り返す短い札は英語にして残す（README の 5.3）。lib/ の KEEP のモジュール（libdocs・planbrief・structmark の控えの節）が組む
日本語の材料は、そのまま入れる（設計書の 10 節の 4）。

- prep(place, repo, prev): 修正案の役の指示（1 回目の役の会話）。前の周が拒まれ、合わせた答えの控えが在れば出し直しにして指示は組まない
- fix_prep(place): 出し直しの役の指示（最後の拒否の理由と、合わせた前の答えの控えのパス）
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt

import carry      # lib/
import concepthome  # lib/
import converge   # lib/
import headdepth  # lib/
import jsonfile   # lib/
import libdocs    # lib/
import oneline    # lib/
import planbrief  # lib/
import policy     # lib/
import rolekit    # lib/
import structmark  # lib/
import worldmark  # lib/

from src import files, ripple, steps

NOT_WEB = "not checked on the web"   # md と世界の解の行の印が同じ字を持つ
DUTY_OWED = "owed"           # 単位の行の末の札。意味は md が持つ（plan-writer.md の units の段落）
DUTY_MAY = "optional"
DUTY_FILLED = "machine-filled"
NO_ROWS = "No row of objection and ruling was found (no row in conflicts names this item)"
VERDICT_WORDS = {"root": "the root", "not_root": "not the root", "unsure": "cannot tell if it is the root"}
PLACE_WORDS = {"same": "related (same place)", "apart": "related (different place)"}
WHEN_NAMES = ("rejected", "replan", "excluded", "prior_notes", "prior_redesign", "recorded_none", "maps_found", "handoff_rounds", "units",
              "filled", "skipped", "questions", "view", "precedents", "prescriptions", "structure_missing", "structure_dirty",
              "structure_clean_only", "structure_clean", "world", "ripple_units", "ripple_units_error", "verify", "verify_unreadable",
              "unknown_rows", "unknown_none", "spec", "prior", "prior_review", "no_prior_review", "revise", "owed_suggests", "revise_notes",
              "revise_keys", "closed_items", "held_items", "prior_ripple", "prior_ripple_error", "policy", "unread", "prior_fix_plan", "prior_fields_only",
              "routes_spec")


def _dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False)


HEAD_CAP = 120   # 並べる答え・論点の頭の字数（元 lib/policy.py の _CAP。lib の policy から消えた）


def _head(text) -> str:
    text = oneline.one_line(text or "")
    return text if len(text) <= HEAD_CAP else text[:HEAD_CAP] + "…"


def _exists(path) -> str:
    return str(path) if path and pathlib.Path(path).is_file() else ""


# ---------------------------------------------------------------- 単位と処方
def units_rows(judgment: dict, catalog, filled) -> tuple:
    """(単位ごとの行, 機械が差し込む no の並び, 入れてはいけない単位の行)。filled の単位は『必ず案に入れる』から外し、差し込む no に分ける"""
    owed, opened, all_units = steps.plan_slots(judgment)
    by_id = {u.get("id"): u for u in catalog if isinstance(u, dict)} if isinstance(catalog, list) else {}
    names = steps.slots(judgment)
    lines = []
    for n, k in enumerate(names, 1):
        u, c = all_units[k], by_id.get(k) or {}
        duty = DUTY_FILLED if k in filled else DUTY_OWED if k in owed else DUTY_MAY
        lines.append(f"- no {n} `{k}`: label={u.get('label')}・disposition={u.get('disposition', 'none')}・{duty}")
        if c.get("paths"):
            lines.append(f"  - paths: {', '.join(map(str, c['paths']))}")
        if c.get("summary"):
            lines.append(f"  - summary: {c['summary']}")
    nos = sorted(names.index(k) + 1 for k in set(filled) if k in names)
    shut = [f"`{k}` (label={u.get('label')}・disposition={u.get('disposition', 'none')})" for k, u in all_units.items() if k not in opened]
    return "\n".join(lines), nos, ", ".join(shut) or "none"


def prescription_rows(judgment: dict) -> str:
    """案に入れる単位ごとの `### <key>` と番号つきの処方"""
    owed, opened, _ = steps.plan_slots(judgment)
    given = steps.prescriptions(judgment)
    keys = [k for k in steps.slots(judgment) if k in owed | opened]
    return "\n\n".join(f"### {k}\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(given[k], 1)) for k in keys if k in given)


# ---------------------------------------------------------------- 構造の目と世界の解
def structure_rows(path) -> dict:
    """構造の目の控えから、{note, dirty, clean}（note は控えが読めない訳、dirty・clean は行の字。控えが無ければ全部空）"""
    state = structmark.read(path)
    out = {"note": "", "dirty": "", "clean": "", "has": False}
    if state is None:
        return out
    if state["status"] == "failed":
        return {**out, "note": structmark.note(state), "has": True}
    try:
        rows = structmark.rows(state.get("design_file") or "")
    except ValueError as e:
        return {**out, "note": structmark.note({"status": "failed", "reason": str(e)}), "has": True}
    if not rows:
        return out
    is_dirty = structmark._is_dirty
    return {**out, "has": True, "dirty": _bullets([r for r in rows if is_dirty(r)]), "clean": _bullets([r for r in rows if not is_dirty(r)])}


def _json_block(doc) -> list:
    """JSON を字のまま貼る塊の行（```json の囲い）"""
    return ["```json", json.dumps(doc, ensure_ascii=False, indent=1), "```"]


def structure_parts(path) -> tuple:
    """構造の目の行の節（prompts/parts/structure-rows.md）に入れる値と段落の真偽。修正案の役の指示と、案の直しの項目の brief が共に使う"""
    got = structure_rows(path)
    return ({"structure_note": got["note"], "dirty_rows": got["dirty"], "clean_rows": got["clean"]},
            {"structure_missing": bool(got["note"]), "structure_dirty": bool(got["dirty"]),
             "structure_clean_only": got["has"] and not got["note"] and not got["dirty"], "structure_clean": bool(got["clean"])})


def structure_section(path) -> str:
    """案の直しの項目の brief に貼る構造の目の行の節（行も控えも無ければ空）"""
    values, marks = structure_parts(path)
    return prompt.render_part("structure-rows", values, marks).strip()


def _row_line(r: dict) -> str:
    faces = "・".join(str(f) for f in r.get("faces") or []) or "none"
    evidence = "・".join(str(e) for e in r.get("evidence") or []) or "none"
    text = f"{r.get('unit_id', '')}: {r.get('verdict', '')} (forms {faces}・grounds {evidence})——{r.get('reason', '')}"
    if r.get("chosen"):
        text += f". Way to avoid: {r['chosen']}"
        if r.get("chosen_reason"):
            text += f" ({r['chosen_reason']})"
    return text


def _bullets(rows: list) -> str:
    return "\n".join(f"- {_row_line(r)}" for r in rows)


def world_lines(rows: list) -> str:
    """世界の解の行の字（類ごとに、定石・出どころ・当たる所・依頼の解き方との比べ）"""
    words = {worldmark.SAME: "the same as the practice", worldmark.DIFFERS: "different from the practice",
             worldmark.NONE: "the request shows no way to solve it"}
    lines = []
    for r in rows:
        v = r.get("versus") or {}
        word = words.get(v.get("verdict"), str(v.get("verdict")))
        head = f"The request's way 「{v.get('proposed')}」 is {word}" if v.get("proposed") else word
        versus = f"{head}——{v['challenge']}" if v.get("verdict") == worldmark.DIFFERS and v.get("challenge") else head
        mark = f" ({NOT_WEB})" if r.get("basis") != worldmark.WEB else ""
        applies = r["applies"] or "none (a row that needs no answer)"
        lines += [f"- Class {r['class_id']} (request line {r['finding']}・{r['where']}): {r['problem']} (activity: {r['activity']})",
                  f"  - Practice: {r['practice']}{mark}",
                  *[f"  - Source {s.get('id')}: {s.get('url')}「{s.get('excerpt')}」" for s in r["sources"] if isinstance(s, dict)],
                  f"  - Applies: {applies}" + (f"／Does not apply: {r['not_applies']}" if r["not_applies"] else ""),
                  f"  - {versus}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 裏取り・頭の深さ
def verify_rows(doc: dict) -> str:
    lines = []
    for u in (x for x in doc["units"] if isinstance(x, dict)):
        head = f"- Unit {u.get('n')} `{u.get('key')}`: "
        if u.get("state") != "checked":
            lines.append(head + "could not be checked (" + "・".join(str(e) for e in u.get("errors") or []) + ")")
            continue
        parts = [VERDICT_WORDS.get(u.get("verdict"), str(u.get("verdict")))]
        if u.get("verdict") == "not_root":
            parts[0] += f" (real root: {u.get('real_root')})"
        parts.append(f"evidence {'found' if u.get('evidence_found') else 'missing'} ({u.get('evidence')})")
        parts.append(f"place {'matches' if u.get('location_ok') else 'differs'} ({u.get('location')})")
        lines.append(head + "・".join(parts) + f". {u.get('why')}")
    syn = doc.get("synergy") if isinstance(doc.get("synergy"), dict) else {}
    if syn.get("state") == "checked":
        lines += ["", f"Synergy between units: {syn.get('why')}"]
        for label, field in (("duplicate", "duplicates"), ("related", "relations")):
            for r in (x for x in syn.get(field) or [] if isinstance(x, dict)):
                word = PLACE_WORDS.get(r.get("place"), "related") if label == "related" else label
                lines.append(f"- {word}: " + "・".join(f"`{k}`" for k in r.get("units") or []) + f" ({r.get('why')})")
        lines += [f"- order: `{r.get('first')}` first, then `{r.get('then')}` ({r.get('why')})" for r in syn.get("order") or [] if isinstance(r, dict)]
    else:
        lines += ["", "Synergy between units: could not be checked (" + "・".join(str(e) for e in syn.get("errors") or []) + ")"]
    return "\n".join(lines)


def unknown_rows(record_file) -> tuple:
    """(行の字, 控えの訳)。行が無ければ ("", 訳)"""
    doc = headdepth.read_file(record_file) if record_file else headdepth.record(headdepth.STANDARD, headdepth.NO_RECORD)
    rows = []
    for it in doc.get("items") or []:
        if not (isinstance(it, dict) and headdepth.known(it.get("unknown"))):
            continue
        where = oneline.one_line(it.get("where") or "")
        place = (f"place {where}「{oneline.one_line(it.get('code_quote') or '')}」" if where
                 else "place: none (the cause is not visible in code)")
        rows.append(f"- line {it.get('item')} ({it['unknown']}): request text 「{oneline.one_line(it.get('cause_quote') or '')}」・{place}")
    return "\n".join(rows), str(doc.get("why") or headdepth.NO_RECORD)


# ---------------------------------------------------------------- 方針・地図・前の run の失敗
def recorded_rows(policy_file: str, answers: list, decisions_file: str) -> tuple:
    """(記録された方針の行の字, 名指せる行が無いか)。承認ノードの答えはいつも『この役には渡っていない』（plan に承認ノードの答えは届かない）"""
    rows = policy.recorded({"policy_md": policy_file, "answers": answers}, decisions_file or None, human_items=None)
    of = {s: [r for r in rows if r.get("source") == s] for s in ("doc", "answer", "settled")}
    doc = of["doc"][0] if of["doc"] else None
    out = ["- Policy document: " + (f"name `{doc['name']}:<line>` (lines 1–{doc['lines']}; original place: {doc['alias'] or 'none'})"
                                    if doc else "none"),
           "- answers of the request: " + ("" if of["answer"] else "none"),
           *[f"  - name `{r['name']}`: {_head(r['text'])}" for r in of["answer"]],
           "- Answers a person gave at approval nodes: not given to this role",
           "- Settled points (from the decision records): " + ("" if of["settled"] else "none"),
           *[f"  - name `{r['name']}`: {_head(r['text'])}" if r["name"] else f"  - (no where, so it cannot be named) {_head(r['text'])}"
             for r in of["settled"]]]
    return "\n".join(x.rstrip() for x in out), not any(r.get("name") for r in rows)


def concept_rows(repo) -> tuple:
    """(地図の行の字, 見つからない時の尾, 地図が見つかったか)"""
    names, why = concepthome.tracked_names(pathlib.Path(repo))
    maps, total = concepthome.pick_maps(names)
    if not maps:
        return "", f" (the tree could not be read: {why})" if why else "", False
    lines = [f"- {m}" for m in maps]
    if total > len(maps):
        lines.append(f"- and {total - len(maps)} more")
    return "\n".join(lines), "", True


def prior_failure_rows(rows) -> tuple:
    """(作り直しでない行, 作り直しの行)。1 件 1 行 `- <where>: <text>`"""
    rows = [r for r in rows if isinstance(r, dict)]
    line = lambda r: f"- {oneline.one_line(r.get('where', ''))}: {oneline.one_line(r.get('text', ''))}"   # noqa: E731
    return ("\n".join(line(r) for r in rows if not carry.is_redesign(r)), "\n".join(line(r) for r in rows if carry.is_redesign(r)))


def handoff_rows(prior) -> str:
    """前の周までの引き継ぎのメモの行（1 周 1 行。メモの無い周・読めない周も名指す）"""
    lines = []
    for row in (prior or {}).get("handoffs") or []:
        path = row.get("handoff")
        if not path:
            note = "(no notes)"
        elif not isinstance(jsonfile.read_or(path), dict):
            note = "(unreadable)"
        else:
            note = f"{path} (Read it)"
        lines.append(f"- r{row['round']}: {note}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 前の周
def face_text(f: dict) -> str:
    return "\n".join([f"### {f['key']}", *(f"- {n}: {f[n]}" for n in converge.FACE_KEYS[1:]),
                      *([f"- {converge.REACH}: {f[converge.REACH]}"] if converge.REACH in f else [])])


def _label(it: dict) -> str:
    return f"Item {it['n']} ({', '.join(str(k) for k in it.get('unit_keys') or [])})"


def revise_values(record: dict) -> dict:
    """事前審査が返した block への答えの頼みの材料（修正案の役に返す往復の時。converge.held が行を返す時）"""
    row = converge.held(record)
    out = {"revise": False, "owed_suggests": False, "revise_notes": False, "revise_keys": False, "closed_items": False, "held_items": False,
           "values": {"revise_blocks": "", "revise_pass": "", "owed_suggests": "", "revise_notes": "", "suggest_keys": "",
                      "closed_items": "", "held_items": ""}}
    if row is None:
        return out
    owed = converge.owed_faces(record, row)
    suggests = [f for f in owed if f["severity"] != "block"]
    notes = row.get("notes")
    asked = {f["key"] for f in owed}
    rest = [f for f in notes or [] if f.get("key") not in asked]
    keys = row.get("suggests") or []
    named = {state: [it for it in row.get("items") or [] if it.get("state") == state] for state in (converge.CLOSED, converge.HELD)}
    values = {"revise_blocks": "\n\n".join(face_text(f) for f in owed if f["severity"] == "block"),
              "revise_pass": str(row["pass"]), "owed_suggests": "\n\n".join(face_text(f) for f in suggests),
              "revise_notes": "\n\n".join(face_text(f) for f in rest), "suggest_keys": ", ".join(keys) if keys else "none",
              "closed_items": "\n".join(f"- {_label(it)}" for it in named[converge.CLOSED]),
              "held_items": "\n".join(f"- {_label(it)}" for it in named[converge.HELD])}
    return {"revise": True, "owed_suggests": bool(suggests), "revise_notes": bool(notes) and bool(rest), "revise_keys": not notes,
            "closed_items": bool(named[converge.CLOSED]), "held_items": bool(named[converge.HELD]), "values": values}


# ---------------------------------------------------------------- 形 replan
def replan_rows(folder, ctx: dict, judgment, repo) -> str:
    """直す項目ごとの節（番号・unit_keys・その項目の brief のパス・前の項目・申し出の行と裁定の文）。項目の brief は planbrief.render で
    item-brief-<no>.md に書く"""
    old = steps.prior_rows(ctx)
    fields = (jsonfile.read_or(ctx["prior"]["fields"], {}) if ctx.get("prior") else {}).get("fields") or []
    conflicts = jsonfile.read_or(ctx["conflicts"]) if ctx.get("conflicts") else None
    units = steps.units_of(judgment) if isinstance(judgment, dict) else {}
    parts = []
    for n in [i for i in files.read_round(folder)["items"] if 1 <= i <= len(old)]:
        item = old[n - 1]
        path = pathlib.Path(folder) / files.ITEM_BRIEF.format(no=n)
        path.write_text(planbrief.render(n, item, fields[n - 1] if n <= len(fields) else {}, units, "",
                                         structure_section(ctx.get("structure") or None)), encoding="utf-8")
        lines = [f"## Item to fix {n} (its number in the approved plan)", "",
                 f"- unit_keys (copy this text as is): {json.dumps(item.get('unit_keys'), ensure_ascii=False)}",
                 f"- Brief of this item: {path}", "",
                 "### The previous item (approved; pasted by the machine)", "", *_json_block(item)]
        rows = steps.conflict_rows(conflicts, n, item)
        for i, c in enumerate(rows, 1):
            ru = c.get("ruling") or {}
            lines += ["", f"### Objection and ruling from the fixing step ({c.get('id') or i})", "",
                      f"- Unit of the objection: {c.get('unit_key')}",
                      f"- Named by the objection (between): {', '.join(map(str, c.get('between') or []))}",
                      f"- Reason of the objection (why_both_cannot_hold): {c.get('why_both_cannot_hold')}",
                      f"- Kind of the objection (kind): {c.get('kind') or '(none)'}",
                      f"- Side judged right (which_is_right): {c.get('which_is_right')}",
                      f"- Text of the ruling ({ru.get('decision')}): {ru.get('text')}"]
        if not rows:
            lines += ["", NO_ROWS]
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


# ---------------------------------------------------------------- 値の全体
def values(place, repo) -> tuple:
    """修正案の役の指示の (値, 段落の真偽)。いつも同じ組（入らない段落の口には空の字）"""
    place = pathlib.Path(place)
    folder, ctx = steps.load(place)
    plan_form = ctx["mode"] == "plan"
    judgment = steps.read_judgment(ctx)
    prior = ctx.get("prior")
    record = (prior or {}).get("record") or {"round": 0, "passes": [], "outcome": None, "open": {}}
    rejected = rolekit.rejected(folder, files.ROLE)
    v = {name: "" for name in (
        "rejection", "excluded_file", "lib_docs", "prior_notes", "prior_redesign", "recorded_rows", "concept_maps", "map_tail",
        "handoff_rounds", "units", "filled", "shut", "skipped", "questions", "view", "precedents", "repo", "read_rev", "diff_base",
        "review_md", "judgment_file", "prescriptions", "structure_note", "dirty_rows", "clean_rows", "world_rows", "ripple_units",
        "ripple_units_error", "verify_rows", "verify_file", "kind_none", "kind_cause", "kind_shape", "kind_scope", "unknown_rows",
        "unknown_why", "spec", "prior_fix_plan", "prior_fields", "prior_review", "revise_blocks", "revise_pass", "owed_suggests",
        "revise_notes", "suggest_keys", "closed_items", "held_items", "prior_ripple", "prior_ripple_error", "policy_body",
        "replan_items", "unread", "lang", "not_web", "duty_owed", "duty_may", "duty_filled")}
    w = dict.fromkeys(WHEN_NAMES, False)
    v["rejection"], w["rejected"] = rolekit.rejects_text(rejected), bool(rejected)
    w["replan"] = not plan_form
    v["not_web"] = NOT_WEB
    v["duty_owed"], v["duty_may"], v["duty_filled"] = DUTY_OWED, DUTY_MAY, DUTY_FILLED
    v["kind_none"], v["kind_cause"], v["kind_shape"], v["kind_scope"] = headdepth.NONE, headdepth.CAUSE, headdepth.SHAPE, headdepth.SCOPE
    # 並行 PR の範囲・ライブラリの文書
    v["excluded_file"] = _exists(ctx.get("excluded"))
    w["excluded"] = bool(v["excluded_file"])
    keys = set(steps.slots(judgment)) if isinstance(judgment, dict) else None
    lib_files, why = libdocs.unit_files(repo, ctx["judgment"], keys) if ctx.get("judgment") else ([], "判定のファイルが無い")
    rows = libdocs.section(place, repo, lib_files, shared=ports.shared_cache()) + (f"\n- 単位のファイルの引き: {why}" if why else "")
    v["lib_docs"] = prompt.render_part("lib-docs", {"rows": rows}).strip()
    # 前の run の失敗の行・記録された方針・地図・引き継ぎのメモ
    v["prior_notes"], v["prior_redesign"] = prior_failure_rows(ctx.get("prior_failures") or [])
    w["prior_notes"], w["prior_redesign"] = bool(v["prior_notes"]), bool(v["prior_redesign"])
    v["recorded_rows"], w["recorded_none"] = recorded_rows(ctx.get("policy") or "", ctx.get("answers") or [], ctx.get("decisions") or "")
    v["concept_maps"], v["map_tail"], w["maps_found"] = concept_rows(repo)
    v["handoff_rounds"] = handoff_rows(prior)
    w["handoff_rounds"] = bool(v["handoff_rounds"])
    # 形 plan の材料
    if plan_form and isinstance(judgment, dict):
        filled = converge.filled_units(record)
        v["units"], nos, v["shut"] = units_rows(judgment, ctx.get("units"), filled)
        w["units"] = True
        v["filled"], w["filled"] = str(nos), bool(nos)
        skipped = structmark.skipped(ctx.get("structure") or None)
        v["skipped"], w["skipped"] = ", ".join(f"`{k}`" for k in skipped), bool(skipped)
        questions = [{k: q.get(k) for k in ("key", "kind", "status", "origin", "depends") if k in q} for q in steps.rows_of(judgment, "questions")]
        v["questions"], w["questions"] = _dump(questions), bool(questions)
        view = {k: judgment[k] for k in ("framing", "one_shot", "one_shot_closes") if k in judgment}
        v["view"], w["view"] = _dump(view), bool(view)
        v["precedents"], w["precedents"] = _dump(judgment.get("precedents")), bool(judgment.get("precedents"))
        v["repo"] = str(repo)
        v["read_rev"] = ctx.get("review_rev") or ctx.get("base") or "HEAD"
        v["diff_base"] = ctx.get("diff_base") or ctx.get("base") or v["read_rev"]
        v["review_md"] = str(ports.SHARED / "prompts" / "REVIEW.md")   # 観点の正本（工場の物。lib は経由しない）
        v["judgment_file"] = ctx.get("judgment") or ""
        v["prescriptions"] = prescription_rows(judgment)
        w["prescriptions"] = bool(v["prescriptions"])
        v["unknown_rows"], v["unknown_why"] = unknown_rows(ctx.get("depth_record") or "")
        w["unknown_rows"], w["unknown_none"] = bool(v["unknown_rows"]), not v["unknown_rows"]
    if plan_form:
        values, marks = structure_parts(ctx.get("structure") or None)
        v.update(values)
        w.update(marks)
        rows = worldmark.rows(ctx["world_rows"]) if ctx.get("world_rows") else []
        v["world_rows"], w["world"] = world_lines(rows), bool(rows)
        doc = jsonfile.read_or(folder / files.RIPPLE_UNITS)
        if isinstance(doc, dict):
            v["ripple_units_error"], w["ripple_units_error"] = str(doc.get("error") or ""), bool(doc.get("error"))
            v["ripple_units"], w["ripple_units"] = ripple.units_rows(doc), not doc.get("error")
        verify = ctx.get("verify") or ""
        if verify:
            got_verify = jsonfile.read_or(verify)
            if isinstance(got_verify, dict) and isinstance(got_verify.get("units"), list):
                v["verify_rows"], w["verify"] = verify_rows(got_verify), True
            else:
                v["verify_file"], w["verify_unreadable"] = verify, True
        texts = []
        if ctx.get("spec"):   # 固めた仕様（spec.json。入口が形で照らした JSON）
            texts.append("\n".join(_json_block(json.loads(pathlib.Path(ctx["spec"]).read_text(encoding="utf-8")))))
        if ctx.get("spec_doc"):   # 人と固めた仕様の本文（字のまま貼る）
            texts.append(pathlib.Path(ctx["spec_doc"]).read_text(encoding="utf-8", errors="replace"))
        if texts:
            v["spec"], w["spec"] = "\n\n".join(texts), True
        w["routes_spec"] = ctx.get("routes") == "spec"
        if prior:
            w["prior"] = True
            v["prior_fix_plan"], v["prior_fields"] = prior.get("fix_plan") or "", prior["fields"]
            w["prior_fix_plan"], w["prior_fields_only"] = bool(prior.get("fix_plan")), not prior.get("fix_plan")
            v["prior_review"] = prior.get("review") or ""
            w["prior_review"], w["no_prior_review"] = bool(prior.get("review")), not prior.get("review")
            extra = revise_values(record) if prior.get("review") else revise_values({"passes": []})
            for name in ("revise", "owed_suggests", "revise_notes", "revise_keys", "closed_items", "held_items"):
                w[name] = extra[name]
            v.update(extra["values"])
            rip = jsonfile.read_or(prior.get("ripple")) if prior.get("ripple") else None
            if isinstance(rip, dict):
                v["prior_ripple_error"], w["prior_ripple_error"] = str(rip.get("error") or ""), bool(rip.get("error"))
                v["prior_ripple"], w["prior_ripple"] = ripple.rows(rip), not rip.get("error")
        copy = policy.brief({"policy_md": ctx["policy"]}) if ctx.get("policy") else {"paste": ""}
        v["policy_body"], w["policy"] = copy["paste"], bool(copy["paste"])
    else:
        v["replan_items"] = replan_rows(folder, ctx, judgment, repo)
    v["unread"], w["unread"] = "\n".join(f"- {u}" for u in ctx.get("unread") or []), bool(ctx.get("unread"))
    v["lang"] = prompt.lang(ctx.get("lang"))
    v["whole_plan"] = steps.WHOLE_PLAN
    return v, w


def prep(place, repo, prev) -> dict:
    """修正案の役の指示を組む（返り {prompt, resubmit}）。前の回の受け付けが拒み、合わせた答えの控えが在れば（rolekit.resubmitting）出し直しの役を起こすので
    指示は組まない。どちらの道でも、役を起こす前の作業ツリーの姿を tree.json に置き直す（受け付けが比べる）"""
    folder, ctx = steps.load(place)
    if rolekit.resubmitting(folder, files.ROLE, prev):
        steps.snap_tree(folder / files.TREE, repo)
        return {"prompt": "", "resubmit": True}
    vals, when = values(place, repo)
    out = prompt.emit("plan-writer", vals, when, prompt.round_of("plan-writer"))
    steps.snap_tree(folder / files.TREE, repo)
    return {"prompt": out["prompt"], "resubmit": False}


def fix_prep(place) -> dict:
    """出し直しの役の指示を組む（最後の拒否の理由と、合わせた前の答えの控えのパス）。返り {prompt}"""
    folder, ctx = steps.load(place)
    rejected = rolekit.rejected(folder, files.ROLE)
    vals = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(folder, files.ROLE)),
            "whole_plan": steps.WHOLE_PLAN}
    return {"prompt": prompt.emit("plan-writer-fix", vals, {"replan": ctx["mode"] == "replan"}, prompt.round_of("plan-writer-fix"))["prompt"]}
