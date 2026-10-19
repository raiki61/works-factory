"""診断の block の入口と指示の値（docs/design/diagnose.md の 5.1〜5.4）。

port の字を読み、道（判定か再審）ごとの支度をして place に書き、2 本の AI の役（判定役・再審の役）の指示 md に渡す値を組む。指示の文は
持たない（prompts/diagnose.md と prompts/rejudge.md が持つ）。Python が組むのは値と、行の札（英語）だけ。

place のファイル（名は src/files.py）: intake.json は {mode, due, status, stop_reason, reason, values}。values は読んだ port の値と
file の port の解いた絶対パスに、指示と受け付けが使い材料のファイルに載せない値（prior_rows・redesign・recorded・material_rows）を足した物。
"""
from __future__ import annotations

import json
import pathlib

import accept        # lib/。tree_state・Reject
import baseline_red  # lib/
import carry         # lib/
import gatemarks     # lib/
import headdepth     # lib/
import jsonfile      # lib/
import materialkit   # lib/
import oneline       # lib/
import outpurpose    # lib/
import policy        # lib/
import rolekit       # lib/
import worldmark     # lib/
from engine.util import Reject, pick   # lib/graphloops/engine/util.py

import ports
import prompt
import requestrows

from src import files, judge, rejudge

HUMAN_ORIGIN = "人の依頼（依頼の行）"
EMPTY_PORTS = ("", "null")


class Stop(Exception):
    """支度が先へ進めない（status と止めの語を持つ）"""

    def __init__(self, status: str, stop_reason: str, reason: str):
        super().__init__(reason)
        self.status, self.stop_reason, self.reason = status, stop_reason, reason


def _port(name: str, read, stop_reason: str = files.JUDGE_STOP):
    try:
        return read()
    except (ValueError, KeyError, Reject) as e:
        raise Stop("failed", stop_reason, f"入力 {name}: {oneline.one_line(e)}") from None


def _blank(raw) -> bool:
    return ports.text(raw).strip() in EMPTY_PORTS


def _write(path, doc):
    return jsonfile.write(path, doc, parents=True)


def _need(place, name):
    got = jsonfile.read_or(pathlib.Path(place) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(place) / name} が無いか読めない")
    return got


def policy_body(path) -> str:
    """方針の文書の本文。policy.PASTE_CAP バイトまで。超えたら先頭を切り、続きの置き場を末尾に書く（切った後の全体が上限の内）"""
    data = pathlib.Path(path).read_bytes()
    if len(data) <= policy.PASTE_CAP:
        return data.decode("utf-8", "replace")
    note = f"\n\n［方針の文書は {len(data)} バイトで、{policy.PASTE_CAP} バイトまでを貼った。続きは {path}］\n"
    room = policy.PASTE_CAP - len(note.encode("utf-8"))
    return data[:room].decode("utf-8", "ignore") + note


def _own_files(place: pathlib.Path) -> None:
    for name in files.OWN_FILES:
        (place / name).unlink(missing_ok=True)
    for pattern in files.PROMPT_GLOBS:
        for path in place.glob(pattern):
            path.unlink()


# ---------------------------------------------------------------- 入口
def intake(place, repo, raw: dict) -> dict:
    """port を読み、道を決め、この block のファイルを名で消し、道ごとの支度をする。返り {due, mode, reason}。intake.json にも書く。
    先へ進めない時（port が読めない・対象差分が取れない・素材の観点が諦めた）は due が偽で、status と止めの語を intake.json に残す。
    思わぬ例外は上げる（script が due 偽の返りにする）"""
    place = pathlib.Path(place)
    place.mkdir(parents=True, exist_ok=True)
    _own_files(place)
    objection = ports.text(raw.get("objection"))
    mode = files.REJUDGE if objection.strip() else files.JUDGE
    doc = {"mode": mode, "due": False, "status": "ok", "stop_reason": "", "reason": "", "values": {}}
    try:
        values, gave = _rejudge_prep(place, repo, raw, objection) if mode == files.REJUDGE else _judge_prep(place, repo, raw)
        doc.update(due=not gave, values=values)
        if gave:   # 素材の観点が諦めた: 材料は書いてあるが役を起こさない
            doc.update(status="stopped", stop_reason=files.MATERIAL_STOP, reason=gave)
    except Stop as stop:
        doc.update(due=False, status=stop.status, stop_reason=stop.stop_reason, reason=stop.reason)
    _write(place / files.INTAKE_FILE, doc)
    return {"due": doc["due"], "mode": mode, "reason": doc["reason"]}


# ---------------------------------------------------------------- 判定の道
def baseline_local_checks(path) -> dict:
    """素材 local_checks を、直す前の試験の結末（baseline.json）の material から写す。修正前のテストが通れば clean、赤なら found。
    結末が読めない・素材の形が違えば not_run と理由"""
    try:
        m = baseline_red.read_baseline(path).get("material")
    except ValueError as e:
        return {"status": "not_run", "reason": f"直す前の結末が読めない: {e}"}
    rule = materialkit.STATUS.get(m.get("status")) if isinstance(m, dict) else None
    if rule is None or any(k not in m for k in rule.fields):
        return {"status": "not_run", "reason": f"直す前の結末（{path}）の素材 material の形が違う: {json.dumps(m, ensure_ascii=False)[:200]}"}
    return m


def assemble_materials(raw_items, raw_card):
    """素材の観点の block の material.json（pointer かパス）の並びを読み、並行 PR の札を足す。返り [(パスか None, doc)]。要素が読めなければ
    ValueError"""
    docs = []
    for i, item in enumerate(raw_items):
        if not (isinstance(item, dict) or (isinstance(item, str) and item.strip())):
            raise ValueError(f"materials[{i}] が pointer でもパスでもない（{item!r:.60}）")
        path = ports.file(json.dumps(item) if isinstance(item, dict) else item)
        if path is None:
            raise ValueError(f"materials[{i}] が空")
        docs.append((path, materialkit.read(path)))
    if not _blank(raw_card):
        card = ports.json(raw_card, "pr-material.schema.json")
        docs.append((None, {"role": files.PARALLEL_PR_ROLE, "status": "ran", "reason": "", "reply": None,
                            "materials": {"parallel_pr": card}, "base": None, "commits": None}))
    return docs


def _reply_of(by_role: dict, role: str):
    doc = by_role.get(role)
    return doc.get("reply") if isinstance(doc, dict) else None


def request_batches(rows: list, origin: str, spec_rows: list, spec_origin: str) -> list:
    """依頼の行を出どころごとのバッチ [{round, origin, findings}] にする（1 run は 1 周なので round は 1）。行の無いバッチは置かない"""
    return [{"round": 1, "origin": o, "findings": got} for o, got in ((origin or HUMAN_ORIGIN, rows), (spec_origin, spec_rows)) if got]


def material_rows(by_role: dict, batches: list) -> list:
    """材料の行: P1 の目の素材の観点が受けた返答の中の where・text を持つ行の全部と、依頼のバッチの行。受け付けが目的の外の行を当てる。
    出どころの節の名は p1.<役の名の - を _ にした物>（prior-decisions と purpose-review は辿らない）"""
    out, replies = [], {}
    for role in files.P1_ROLES:
        if role in by_role:
            replies[f"p1.{role.replace('-', '_')}"] = by_role[role].get("reply")
    for nid in sorted(replies):
        outpurpose._walk(replies[nid], nid, out)
    for batch in batches:
        outpurpose._walk(batch["findings"], f"依頼（{batch['origin']}）", out)
    return out


def input_doc(materials: dict, by_role: dict, batches: list, constraints: list, world_rows, answers: list, changed_files,
              diff_file: str) -> dict:
    """材料のファイル diagnose-input.json の中身（値だけ。鍵の意味は prompts/diagnose.md の Inputs が持つ）"""
    doc = {"materials": materials}
    for key, (role, field) in files.REPLY_KEYS.items():
        reply = _reply_of(by_role, role)
        doc[key] = reply if field is None else (reply.get(field) if isinstance(reply, dict) else None)
    doc.update(request_findings=batches, constraints=constraints, world_rows=world_rows, answers=answers,
               changed_files=list(changed_files), diff_file=diff_file)
    return doc


def _judge_prep(place: pathlib.Path, repo, raw: dict) -> tuple:
    request = _port("request", lambda: requestrows.parts(raw.get("request")), files.REQUEST_STOP)
    rows = request[carry.FINDINGS]
    request_origin = ports.text(raw.get("request_origin")).strip()
    base = ports.text(raw.get("base")).strip()
    purpose = _port("purpose", lambda: ports.file(raw.get("purpose")))
    constraints = _port("constraints", lambda: _constraint_rows(ports.json(raw.get("constraints"), "shared:constraints.schema.json")))
    raw_items = _port("materials", lambda: ports.json(raw.get("materials"), "materials.schema.json"))
    baseline = _port("baseline", lambda: ports.file(raw.get("baseline")))
    world_path = _port("world_rows", lambda: ports.file(raw.get("world_rows")))
    row_asks = _port("row_asks", lambda: ports.json(raw.get("row_asks"), "row-asks.schema.json"))
    spec_path = _port("spec_rows", lambda: ports.file(raw.get("spec_rows")))
    spec_origin = ports.text(raw.get("spec_origin")).strip()
    port_answers = _port("answers", lambda: ports.json(raw.get("answers"), "answer-rows.schema.json"))
    port_prior = _port("prior_failures", lambda: ports.json(raw.get("prior_failures"), "shared:prior-failures.schema.json"))
    policy_path = _port("policy", lambda: ports.file(raw.get("policy")))
    answers = port_answers or request[carry.ANSWERS]
    spec_rows = _port("spec_rows", lambda: _spec_rows(spec_path, spec_origin))
    world = _port("world_rows", lambda: worldmark.rows(world_path) if world_path else None)
    docs = _port("materials", lambda: assemble_materials(raw_items, raw.get("pr_material")))
    by_role = {str(doc.get("role") or ""): doc for _, doc in docs}
    local = baseline_local_checks(baseline) if baseline else None
    mats = materialkit.assemble([doc for _, doc in docs], local_checks=local)
    mats = {name: mats[name] for name in files.MATERIALS}   # この block が読む素材の欄だけ（files.MATERIALS。gate_efficacy は含めない）
    try:
        view = materialkit.take_view(place, repo, base)
    except Reject as e:
        raise Stop("failed", files.JUDGE_STOP, f"対象差分が取れない（{oneline.one_line(e)}）——判定役を起こさない") from None
    if mats["base_determination"].get("status") == "not_run" and not any("base_determination" in (doc.get("materials") or {}) for _, doc in docs):
        mats["base_determination"] = base_determination(view)   # 根を持つ素材の doc が無い（単独の run など）時は、見方の根で埋める
    batches = request_batches(rows, request_origin, spec_rows, spec_origin)
    _write(place / files.MATERIALS_FILE, mats)
    _write(place / files.INPUT_FILE, input_doc(mats, by_role, batches, constraints, world, answers, view.changed_files, view.diff_file))
    decisions = next((path for path, doc in docs if doc.get("role") == files.PRIOR_DECISIONS_ROLE and path is not None), None)
    start = {"policy": {"named": "", "path": "", "sha256": None, "copy": str(policy_path) if policy_path else None},
             "answers": answers}
    prior = [*request[carry.PRIOR], *port_prior]
    try:
        materialkit.snap_tree(place, repo)
    except Reject as e:
        raise Stop("failed", files.JUDGE_STOP, f"役を起こす前の作業ツリーの姿が取れない（{oneline.one_line(e)}）——判定役を起こさない") from None
    values = {
        "request_origin": request_origin, "base": base, "purpose": str(purpose) if purpose else "",
        "pr_text": ports.text(raw.get("pr_text")), "policy": str(policy_path) if policy_path else "",
        "lang": ports.text(raw.get("lang")).strip(), "row_asks": row_asks, "depth_why": ports.text(raw.get("depth_why")),
        "prior_rows": [r for r in prior if not carry.is_redesign(r)], "redesign": [r for r in prior if carry.is_redesign(r)],
        "recorded": policy.recorded(start, decisions), "material_rows": material_rows(by_role, batches),
    }
    gave = [str(doc.get("reason") or "") for _, doc in docs if doc.get("status") == "gave_up"]
    return values, "／".join(gave)


def base_determination(view) -> dict:
    """素材の doc のどれも根を持たない時の base_determination（写す元 judge_accept の素材の束ね）: 差分の見方の根と commit の数"""
    return {"status": "found", "count": int(view.commits or 0), "detail": f"{view.base}（始めの記録の差分の根。空なら HEAD）"}


def _constraint_rows(value) -> list:
    """port constraints の値（配列か、{constraints: [...]}）の行"""
    return list(value.get("constraints") if isinstance(value, dict) else value)


def _spec_rows(path, origin) -> list:
    """仕様が足した受け入れ条件の行（added-rows.json の配列）。ファイルが在るのに出どころの名が空なら落とす"""
    if path is None:
        return []
    if not origin:
        raise ValueError("spec_rows の出どころの名が要る（spec_origin が空）")
    got = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(got, list):
        raise ValueError(f"{path} が依頼の行の配列でない")
    return got


# ---------------------------------------------------------------- 再審の道
def _rejudge_prep(place: pathlib.Path, repo, raw: dict, objection: str) -> tuple:
    prior_raw = raw.get("prior")
    if _blank(prior_raw):
        raise Stop("failed", files.REJUDGE_SESSION_STOP, "1 回目の判定（judgment.json）が無い——判定の道を通っていない run。再審せずに止めた")
    judgment = _port("prior", lambda: ports.json(prior_raw, "shared:judgment.schema.json"), files.REJUDGE_STOP)
    paths = {name: _port(name, lambda name=name: ports.file(raw.get(name)), files.REJUDGE_STOP)
             for name in ("prior_brief", "prior_inputs", "world_rows", "purpose", "spec", "verify", "excluded", "policy")}
    try:
        _write(place / files.TREE_FILE, accept.tree_state(pathlib.Path(repo)))
    except Reject as e:
        raise Stop("failed", files.REJUDGE_STOP, f"作業ツリーの姿が取れない（{oneline.one_line(e)}）") from None
    units = judgment["units"]
    _write(place / files.FIRST_JUDGMENT_FILE, judgment)
    _write(place / files.UNITS_BEFORE_FILE, {"node": files.REJUDGE_NODE, "units": units, "objection": objection,
                                              "numbered_keys": [u.get("key") for u in units if isinstance(u, dict)]})
    return {"objection": objection, "lang": ports.text(raw.get("lang")).strip(),
            **{name: str(path) if path else "" for name, path in paths.items()}}, ""


# ---------------------------------------------------------------- 指示の値
def _lines(rows: list) -> str:
    return "\n".join(f"- {oneline.one_line(r.get('where', ''))}: {oneline.one_line(r.get('text', ''))}" for r in rows)


def recorded_text(rows: list) -> str:
    """記録された方針の行（policy.recorded の行）を、英語の札で並べた文。名指しの字は変えずに入れる（受け付けが字で照らす）。
    承認ノードの答えはこの役には渡っていない（札がそう言う）"""
    of = {s: [r for r in rows if r.get("source") == s] for s in ("doc", "answer", "settled")}
    cap = 120

    def head(text):
        text = oneline.one_line(text or "")
        return text if len(text) <= cap else text[:cap] + "…"

    out = []
    doc = of["doc"][0] if of["doc"] else None
    out.append("- Policy document: " + (f"name `{doc['name']}:<line>` (lines 1–{doc['lines']}; original place: none)" if doc else "none"))
    out.append("- answers of the request: " + ("" if of["answer"] else "none"))
    out += [f"  - name `{r['name']}`: {head(r['text'])}" for r in of["answer"]]
    out.append("- Answers a person gave at approval nodes: not given to this role")
    out.append("- Settled points (from the decision records): " + ("" if of["settled"] else "none"))
    out += [f"  - name `{r['name']}`: {head(r['text'])}" if r["name"] else f"  - (no where, so it cannot be named) {head(r['text'])}"
            for r in of["settled"]]
    return "\n".join(x.rstrip() for x in out)


def unknown_lines(row_asks: list) -> list:
    """頭の深さの行ごとの未知の種類の行（種類が決まっている行だけ）。種類の語は字のまま"""
    out = []
    for it in row_asks:
        if not headdepth._known(it.get("unknown")):
            continue
        where = oneline.one_line(it.get("where") or "")
        place = (f"place {where}「{oneline.one_line(it.get('code_quote') or '')}」" if where
                 else "place: none (the cause is not visible in code)")
        out.append(f"- line {it.get('item')} ({it['unknown']}): request text 「{oneline.one_line(it.get('cause_quote') or '')}」・{place}")
    return out


def diagnose_values(place) -> tuple:
    """判定役の指示の値と段落の真偽。intake.json と view.json から組む。読めなければ ValueError"""
    place = pathlib.Path(place)
    doc = _need(place, files.INTAKE_FILE)
    v = doc["values"]
    view = _need(place, files.VIEW_FILE)
    rejected = rolekit.rejected(place, files.DIAGNOSE_ROLE)
    purpose_text = ""
    if v["purpose"]:
        purpose_text = str(json.loads(pathlib.Path(v["purpose"]).read_text(encoding="utf-8")).get("purpose_text") or "")
    review_md, repo_review_md = materialkit.review_md_paths(view["repo"])
    unknown = unknown_lines(v["row_asks"])
    recorded = recorded_text(v["recorded"])
    values = {
        "rejection": rolekit.rejects_text(rejected), "inputs_file": str(place / files.INPUT_FILE), "purpose_text": purpose_text,
        "diff_file": view["diff_file"], "base": view["base"], "review_rev": view["review_rev"], "repo": view["repo"],
        "review_md": review_md, "repo_review_md": repo_review_md, "pr_text": v["pr_text"],
        "policy_body": policy_body(v["policy"]) if v["policy"] else "", "hypothesis": files.HYPOTHESIS,
        "world_prefix": worldmark.SOURCE_PREFIX, "why_min": outpurpose.MIN_WHY, "undecided_min": files.UNDECIDED_MIN,
        "tie_min": gatemarks.ANSWER_TIE_MIN, "prior_notes": _lines(v["prior_rows"]), "prior_redesign": _lines(v["redesign"]),
        "recorded_rows": recorded, "kind_none": headdepth.NONE, "kind_cause": headdepth.CAUSE, "kind_shape": headdepth.SHAPE,
        "kind_scope": headdepth.SCOPE, "unknown_rows": "\n".join(unknown),
        "unknown_why": v["depth_why"].strip() or headdepth.NO_RECORD, "lang": prompt.lang(v["lang"]),
    }
    when = {"rejected": bool(rejected), "spawns": False, "purpose": bool(purpose_text), "repo_review": bool(repo_review_md),
            "pr_text": bool(v["pr_text"].strip()), "policy": bool(v["policy"]), "prior_notes": bool(v["prior_rows"]),
            "prior_redesign": bool(v["redesign"]), "recorded_none": not any(r.get("name") for r in v["recorded"]),
            "unknown_rows": bool(unknown), "unknown_none": not unknown}
    return values, when


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def rejudge_values(place) -> tuple:
    """再審の役の指示の値と段落の真偽。intake.json と first-judgment.json から組む。読めなければ ValueError"""
    place = pathlib.Path(place)
    v = _need(place, files.INTAKE_FILE)["values"]
    first = _need(place, files.FIRST_JUDGMENT_FILE)
    rejected = rolekit.rejected(place, files.REJUDGE_ROLE)
    questions = pick(first.get("questions") or [], ["key", "kind", "status"])
    diagnosis = {k: first[k] for k in ("framing", "one_shot") if k in first}
    values = {
        "rejection": rolekit.rejects_text(rejected), "objection": v["objection"].strip(),
        "units": _json(pick(first.get("units") or [], ["key", "label", "disposition"])),
        "questions": _json(questions) if questions else "", "diagnosis": _json(diagnosis) if diagnosis else "",
        "first_judgment_file": str(place / files.FIRST_JUDGMENT_FILE),
        **{f"{name}_file": v[name] for name in ("prior_brief", "prior_inputs", "world_rows", "purpose", "spec", "verify", "excluded")},
        "facts_min": files.FACTS_MIN, "policy_body": policy_body(v["policy"]) if v["policy"] else "", "lang": prompt.lang(v["lang"]),
    }
    when = {"rejected": bool(rejected), "spawns": False, "questions": bool(questions), "diagnosis": bool(diagnosis),
            **{name: bool(v[name]) for name in ("prior_brief", "prior_inputs", "world_rows", "purpose", "spec", "verify", "excluded", "policy")}}
    return values, when


def diagnose_prompt(place) -> dict:
    values, when = diagnose_values(place)
    return prompt.emit("diagnose", values, when, prompt.round_of("diagnose"))


def rejudge_prompt(place, prev=None) -> dict:
    """再審の役の 1 回目の指示。前の周の受け付けが拒み（prev が偽）、合わせた答えの控えが在れば、出し直しの役を起こすので指示は組まない
    （resubmit 真。rejudge_fix_prompt が組む）。返り {prompt, resubmit}"""
    if rolekit.resubmitting(place, files.REJUDGE_ROLE, prev):
        return {"prompt": "", "resubmit": True}
    values, when = rejudge_values(place)
    return {**prompt.emit("rejudge", values, when, prompt.round_of("rejudge")), "resubmit": False}


def rejudge_fix_prompt(place) -> dict:
    """拒まれた後の出し直しの役の指示（拒否の理由は最後の 1 件、合わせた前の答えの控えのパス）。拒まれた欄だけを返させる"""
    place = pathlib.Path(place)
    rejected = rolekit.rejected(place, files.REJUDGE_ROLE)
    values = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(place, files.REJUDGE_ROLE))}
    return prompt.emit(files.REJUDGE_FIX_NODE, values, {}, prompt.round_of(files.REJUDGE_FIX_NODE))


def prep(place, build, *args) -> dict:
    """prep の本体: 指示を build(place) で組む。組めない（md と値の食い違い・入口の控えが読めない）時は、place に prompt-error.json
    {node, reason} を書いてから落ちる（輪が落ち、出口がその訳を reason に書く）"""
    try:
        return build(place, *args)
    except (prompt.PromptError, ValueError, KeyError, OSError) as e:
        node = {rejudge_prompt: "rejudge-prep", rejudge_fix_prompt: "rejudge-fix-prep"}.get(build, "diagnose-prep")
        _write(pathlib.Path(place) / files.PROMPT_ERROR_FILE, {"node": node, "reason": oneline.one_line(f"{type(e).__name__}: {e}")})
        raise


def accept_diagnose(place, raw: str, repo) -> dict:
    """判定役の返答の受け付け。値は diagnose-input.json（世界の解の行・依頼の答え・素材）と intake.json の values（前の run の作り直しの行・
    記録された方針・材料の行）から読む（受け付けと指示が同じ値を見る）"""
    place = pathlib.Path(place)
    doc, v = _need(place, files.INPUT_FILE), _need(place, files.INTAKE_FILE)["values"]
    got = judge.accept_reply(place, raw, repo, doc["world_rows"] or [], doc["answers"], v["redesign"], v["recorded"],
                             doc["materials"], v["material_rows"])
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


def accept_rejudge(place, raw, fix_raw, repo) -> dict:
    return rejudge.accept_reply(pathlib.Path(place), rejudge.value(raw), rejudge.value(fix_raw), repo)
