"""9 つの AI の node の指示に渡す値と段落の真偽（docs/design/fix.md の 2.3・3.3・4.3・5.3・6.3 の差し込み口の一覧）。

指示の文は prompts/ の md が持ち、ここは値を集めて prompt.emit（下請けの頼みは prompt.render_part）に渡すだけ。材料の行（brief・穴・範囲・
テスト・ライブラリ・相談の頼み・単位・引き継ぎ）は今の lib が組む日本語の字のまま入る（13.2 の 5）。組んだ指示は place の
<node-id>-prompt-<n>.md に書く。
"""
from __future__ import annotations

import json
import pathlib
import sys

import prompt

import conflict   # lib/（写さずに呼ぶ。1.5.2）
import planbrief  # lib/
import planrange  # lib/
import rolekit    # lib/
import seat       # lib/
import spseam     # lib/
import unittrees  # lib/

from src import board, files, rules, runvals
from src.rulings import write as write_rulings

EMPTY = "(empty)"
BLOCK = pathlib.Path(__file__).resolve().parents[1]
OVERLAY_FILE = str(spseam.BORROW_DIR / spseam.OVERLAY_FILE)   # 下請けに Read させる無人の読み替え（今の seat.OVERLAY_HEAD の後半）
FACTS = BLOCK / "src" / "facts.py"   # 事前の確かめのコマンド（1.5.5）
FIXER = {"first": "fixer", "ruled": "fix-ruled"}
ACCEPT = {"first": "fix-accept", "ruled": "fix-ruled-accept"}
LEDGER = {"first": files.FIXER_DELIVERED, "ruled": files.RULED_DELIVERED}
CLASH = {"first": "clash-fix", "ruled": "clash-ruled"}
CONSULT = {"first": "consult-answer", "ruled": "ruled-consult-answer"}
WRITER_KINDS = {"docs": "docs", "prompts": "prompts_kind", "config": "config", "code": "code"}   # 種類 → writer-rules の段落の名


class Broken(ValueError):
    """指示が組めない（brief の控えが壊れた・借りた写しが固定と違う・md と値の食い違い）"""


def shown(value) -> str:
    return str(value) if str(value or "").strip() else EMPTY


def round_file(place, node_id: str) -> pathlib.Path | None:
    """node の組んだ 1 回目の指示のファイル（無ければ None。読んだ証拠が段を起こしたかを見る）"""
    path = pathlib.Path(place) / f"{node_id}-prompt-1.md"
    return path if path.is_file() else None


def _starts(values: dict) -> tuple[dict, dict]:
    """方針の文書と依頼のファイルの値と段落（今の fixrules.start_lines）"""
    policy = str(values.get("policy_path") or "").strip()
    request = str(values.get("request_file") or "").strip()
    return ({"policy_path": shown(policy), "request_file": shown(request)},
            {"policy": bool(policy), "no_policy": not policy, "request": bool(request), "no_request": not request})


def _rejection(place, name: str) -> str:
    return rolekit.rejects_text(rolekit.rejected(place, name))


def _libdocs_rows(text: str) -> str:
    """libdocs.section は材料の行だけを返す（見出しと頭の文は md が持つ）"""
    return text.strip("\n")


def _kinds_when(kinds, role: str) -> dict:
    """writer-rules の証拠の段落の真偽。続きの周は種類が全部偽で、見出しと頭の文ごと落とす。role は答えを書く場所の段落の名（この block は fixer・tdd）"""
    got = {name: kind in kinds for kind, name in WRITER_KINDS.items()}
    return {**got, "evidence": any(got.values()), **{f"where_{r}": r == role for r in ("fixer", "tdd", "rework")}}


def _check_cmd(config: str) -> str:
    return f"{sys.executable} {FACTS} {config}" if config else ""


# ---------------------------------------------------------------- 修正役（fixer・fix-ruled）
def fixer_values(place, repo, pass_: str, values: dict, *, owed, items=None, sources=None, green=frozenset(), frozen=None,
                 shared=None, saved_reply: str = "") -> tuple[dict, dict, dict]:
    """修正役の指示の (値, 段落, 周の控え {iteration, kinds, ledger})。今の fixrules.prep の組み立ての順のまま。
    範囲の相談の答えの後・はみ出しを相談に積んだ周は続きの段落だけ（回の数え直しをしない）。brief の控えが壊れていれば Broken"""
    place = pathlib.Path(place)
    try:
        briefs = rules.briefs_or_halt(place, **(sources or {}))   # 裁定の文を書くより前に凍結する
    except ValueError as e:
        raise Broken(str(e)) from None
    ledger = place / LEDGER[pass_]
    slots = ("rejection rulings_file saved_reply brief_rows faces_rows scope_rows tests_rows tests_how policy_path request_file "
             "judgment_file open_units plan_file summary_file notes_file budget draft check_cmd ripple_file libdocs_rows g1_items "
             "seat_file seat_body unattended overlay_file first_prompt answer_file left lang").split()
    vals = {k: "" for k in slots}
    when = {k: False for k in ("rejected rulings_first ruled_reply briefs faces scope tests tests_new tests_tail tests_broken frozen_files frozen_verified frozen_unruled tests_how rules ask ask_ripple libdocs g1 "
                               "seat_one resume queued overflow_answer conflict docs prompts_kind config code evidence where_fixer where_tdd where_rework").split()}
    when["conflict"] = True
    start_vals, start_when = _starts(values)
    vals.update(start_vals, lang=prompt.lang(runvals.read(place)["lang"]))
    when.update({k: False for k in start_when})
    from src import consult
    vals["first_prompt"] = str(place / f"{FIXER[pass_]}-prompt-1.md")   # 続きの周が読み直す、1 回目に組んだ指示のファイル
    got = consult.take(place, pass_)
    if got is not None:   # 範囲の相談の答えの後の周: 答えのファイルを名指すだけ（受け付けの回は数え直さない）
        rv = rules.resume_values(got)
        vals.update(answer_file=rv["answer_file"], left=rv["left"])
        when["overflow_answer" if rv["overflow"] else "resume"] = True
        return vals, when, {"iteration": max(1, rules.iteration_next(ledger) - 1), "kinds": None, "ledger": ledger}
    if consult.queued(place, pass_):   # 受け付けがはみ出しを相談に積んだ周
        when["queued"] = True
        return vals, when, {"iteration": max(1, rules.iteration_next(ledger) - 1), "kinds": None, "ledger": ledger}
    n = rules.iteration_next(ledger)
    when.update(start_when, rules=True, tests=True, tests_tail=True)   # テストの節は修正案の有無によらずいつも載る
    rejects = rolekit.rejected(place, ACCEPT[pass_])
    if pass_ == "ruled" and n == 1:
        rulings = place / conflict.RULINGS_FILE
        if not rulings.is_file():
            rulings = write_rulings(place)
        vals["rulings_file"] = str(rulings)
        when["rulings_first"] = True
        rejects = []
    if rejects:
        vals["rejection"] = rolekit.rejects_text(rejects)
        when["rejected"] = True
    if pass_ == "ruled" and saved_reply:
        vals["saved_reply"] = board.ruled_reply_line(saved_reply)
        when["ruled_reply"] = True
    values = rules.owed_values(place, values, owed=owed)
    owed_keys = json.loads(values["open_units"])
    vals["brief_rows"] = rules.brief_rows(planbrief.for_units(briefs, owed_keys), owed_keys)
    when["briefs"] = bool(vals["brief_rows"])
    vals["faces_rows"] = board.plan_faces_text(place, board.face_units(pass_, owed_keys))
    when["faces"] = bool(vals["faces_rows"])
    got_scope = planrange.fix_scope(place, pass_, items=items)[0]
    edits = conflict.edit_permits(place, pass_)
    vals["scope_rows"] = rules.scope_rows(got_scope)
    vals["tests_rows"] = rules.tests_rows(got_scope, edits, frozen)
    when["scope"] = got_scope is not None
    when["tests_new"] = got_scope is not None
    when["tests_broken"] = bool(edits.get("broken"))
    when["frozen_files"] = bool((frozen or {}).get("files"))
    when["frozen_verified"] = bool(when["frozen_files"] and (frozen or {}).get("verified"))
    when["frozen_unruled"] = bool(when["frozen_files"] and (frozen or {}).get("unruled"))
    vals["tests_how"] = board.tests_how_text(place)
    when["tests_how"] = bool(vals["tests_how"])
    for key in ("judgment_file", "open_units", "plan_file", "summary_file", "notes_file"):
        vals[key] = shown(values.get(key))
    config = rules.ask_config(place, repo, values, pass_, items=items)
    if config:
        vals.update(budget=str(consult.BUDGET), draft=str(pathlib.Path(config).parent / rules.ASK_DRAFT), check_cmd=_check_cmd(config))
        when["ask"] = True
        ripple = str(values.get("ripple_file") or "").strip()
        if ripple:
            vals["ripple_file"] = ripple
            when["ask_ripple"] = True
    subs = rules.dispatched(owed_keys, green)
    try:
        seat.pinned()   # 写しの照合を、下請けのファイルの書き込みとライブラリの文書の引きより前に
        if subs:
            vals["g1_items"] = "\n".join(f"- {rules.g1_row(r)}" for r in g1_files(place, values, repo, subs, briefs, config))
            when["g1"] = True
        else:
            sec = spseam.load_seams()[seat.SEATS["fix"]]
            vals["seat_file"] = sec["files"][0]
            vals["seat_body"] = seat.fill(seat.SEATS["fix"], rules.implementer_values(place, values, repo, owed_keys, briefs)).rstrip("\n")
            when["seat_one"] = True
        vals["unattended"] = seat.overlay_body(seat.OVERLAY_KINDS["fix"]).rstrip("\n")
        vals["overlay_file"] = OVERLAY_FILE
    except ValueError as e:
        raise Broken(f"修正役の座を組めない: {e}") from None
    vals["libdocs_rows"] = _libdocs_rows(rules.lib_section(place, repo, values, shared))
    when["libdocs"] = bool(vals["libdocs_rows"])
    kinds = rules.kinds_for(ledger, values, repo)
    when.update(_kinds_when(kinds, "fixer"))
    return vals, when, {"iteration": n, "kinds": kinds, "ledger": ledger}


def fixer(place, repo, pass_: str, values: dict, **kw) -> dict:
    """修正役の指示を組んで place に書く。返り {prompt, iteration}"""
    vals, when, rnd = fixer_values(place, repo, pass_, values, **kw)
    node = FIXER[pass_]
    try:
        out = prompt.emit(node, vals, when, prompt.round_of(node))
    except prompt.PromptError as e:
        raise Broken(f"{node} の指示を組めない: {e}") from None
    if rnd["kinds"] is not None:
        rules.remember(rnd["ledger"], rnd["kinds"], rnd["iteration"])
    return {"prompt": out["prompt"], "iteration": rnd["iteration"]}


def g1_files(place, values: dict, repo, owed: list[str], briefs: list, config: str = "") -> list[dict]:
    """修正役が起こす下請けのファイルを、項目ごとに place に 2 つ書き（prompt.render_part。名は今のまま g1-impl-<n>.md・g1-review-<n>.md）、
    項目の順の [{item, impl_file, review_file, base, patch}] を返す（今の fixrules.g1_values）。実装役は implementer の型
    （[BRIEF_FILE] はその項目の brief、[task name] はその項目の直す義務の単位、[REPORT_FILE] は md の g1-impl-report）、審査役は
    task-review の型（[BASE_SHA] は修正前の版、[DIFF_FILE] は place の g1-<n>.patch。型の <base>..<head> は <base> に直す）"""
    place = pathlib.Path(place)
    common = rules.implementer_values(place, values, repo, owed, briefs)
    base = board.base_rev(None, values.get("base_rev") or "")
    rows = []
    for n, brief, task in rules.g1_items(place, values, owed, briefs):
        impl, review = place / rules.G1_IMPL.format(n=n), place / rules.G1_REVIEW.format(n=n)
        patch = str(place / rules.G1_PATCH_FILE.format(n=n))
        template = seat.fill("implementer", {**common, "[task name]": task, "[BRIEF_FILE]": brief,
                                              "[REPORT_FILE]": prompt.render_part("g1-impl-report", {}).strip()})
        impl.write_text(prompt.render_part("g1-impl", {"template": template.rstrip("\n"), "check_cmd": _check_cmd(config)},
                                   {"spawns": False, "ask": bool(config)}), encoding="utf-8")
        rv = rules.review_values(brief, values, base, patch)
        filled = seat.fill("task-review", rv).replace(f"{rv['[BASE_SHA]']}..{rv['[HEAD_SHA]']}", rv["[BASE_SHA]"])
        review.write_text(prompt.render_part("g1-review", {"template": filled.rstrip("\n")}, {"spawns": False}), encoding="utf-8")
        rows.append({"item": n, "impl_file": str(impl), "review_file": str(review), "base": base, "patch": patch})
    return rows


# ---------------------------------------------------------------- 相談の答えの役（consult-answer・ruled-consult-answer）
def consult_values(place, table: dict, asked: list, *, plan_file: str, ripple_file: str) -> tuple[dict, dict]:
    from src import consult
    import planmarks
    vals = {"plan_file": plan_file or "（修正案のファイルは無い）", "ripple_file": ripple_file, "count": len(asked),
            "asks": consult.asks_text(table, asked), "red": planmarks.AGREED_RED, "guard": planmarks.GUARD_KIND,
            "min_why": consult.MIN_WHY, "lang": prompt.lang(runvals.read(place)["lang"])}
    gate = [a for a in asked if a.get("origin") == consult.ORIGIN_GATE]
    when = {"ripple": bool(ripple_file), "gate": bool(gate), "plain": len(gate) < len(asked)}
    return vals, when


def consult_render(place, pass_: str, *, plan_file: str, ripple_file: str):
    """board.consult_ask に渡す口: (項目の表, 聞く頼み) → 答えの役の指示の字（prompt.emit で place に書く）"""
    node = CONSULT[pass_]

    def render(table, asked):
        vals, when = consult_values(place, table, asked, plan_file=plan_file, ripple_file=ripple_file)
        return prompt.emit(node, vals, when, prompt.round_of(node))["prompt"]
    return render


# ---------------------------------------------------------------- TDD の役（tdd・tdd-new）
def tdd_values(place, repo, view: dict, values: dict) -> tuple[dict, dict, dict]:
    """TDD の役の指示の (値, 段落, 周の控え)。view は src/tdd.prep の返り（go が真の物）。values は run の値（判定・修正案・方針・依頼・
    notes の写しのパスと base_rev）。今の tddloop.prep の組み立ての順のまま"""
    from src import tdd
    place = pathlib.Path(place)
    st, briefs = view["state"], view["briefs"]
    phase = st["phase"]
    owed = tdd._owed(st)
    vals = {k: "" for k in ("iteration phase brief_rows rejection policy_path request_file judgment_file open_units plan_file "
                            "notes_file skill seat_applies seat_not_applies unattended overlay_file test_cmd owed_units current_unit "
                            "together_rows named_rows handoff_rows later_rows tests_how runner_cmd lang").split()}
    when = {k: False for k in ("briefs rejected rules conflict docs prompts_kind config code phase_route phase_test phase_fix "
                               "phase_refactor gate current together named handoff later tests_how evidence where_fixer where_tdd where_rework").split()}
    when.update(rules=True, conflict=True, **{f"phase_{phase}": True})
    start_vals, start_when = _starts(values)
    vals.update(start_vals)
    when.update(start_when)
    vals.update(iteration=st["iterations"] + 1, phase=phase, lang=prompt.lang(runvals.read(place)["lang"]),
                judgment_file=shown(values.get("judgment_file")), plan_file=shown(values.get("plan_file")),
                notes_file=shown(values.get("notes_file")), open_units=json.dumps(owed, ensure_ascii=False),
                runner_cmd=st["exe"])
    if st.get("reason"):
        vals["rejection"] = st["reason"].rstrip("\n")
        when["rejected"] = True
    if phase in ("fix", "refactor") and st.get("test_cmd_gate") == tdd.GATE_ON and tdd._cur(st)["unit_key"] not in st.get("light", []):
        vals["test_cmd"] = st["test_cmd"]
        when["gate"] = True
    if phase == "route":
        vals["owed_units"] = "\n".join(f"- {k}" for k in owed)
        brief = rules.brief_rows(planbrief.for_units(briefs, owed), owed)
    else:
        u = st["units"][st["queue"][st["cur"]]]
        both = tdd.together(st, u["unit_key"])
        brief = rules.brief_rows(planbrief.for_units(briefs, [u["unit_key"]]), [u["unit_key"], *both])
        vals["current_unit"] = f"- {u['unit_key']}"
        when["current"] = True
        if both:
            vals["together_rows"] = "\n".join(tdd.together_rows(st, u["unit_key"]))
            when["together"] = True
        if u["tests"]:
            vals["named_rows"] = f"- 名指しのテスト: {', '.join(u['tests'])}\n- テストのファイル（凍っている）: {', '.join(u['test_files'])}"
            when["named"] = True
        left = [q for q in st["queue"][st["cur"] + 1:] if q not in both]
        if left:
            vals["later_rows"] = " / ".join(left)
            when["later"] = True
    had, rows = tdd.handoff_rows(st)
    vals["handoff_rows"] = "\n".join(rows)
    when["handoff"] = had
    vals["brief_rows"] = brief
    when["briefs"] = bool(vals["brief_rows"])
    vals["tests_how"] = board.tests_how_text(place)
    when["tests_how"] = bool(vals["tests_how"])
    try:
        seat.pinned()
        sec = spseam.load_seams()[seat.SEATS["tdd"]]
        vals["skill"] = seat.skill_of(sec)
        vals["seat_applies"] = "\n".join(f"- {r}" for r in sec.get("applies") or [])
        vals["seat_not_applies"] = "\n".join(f"- {r}" for r in sec.get("not_applies") or [])
        vals["unattended"] = seat.overlay_body(seat.OVERLAY_KINDS["tdd"]).rstrip("\n")
        vals["overlay_file"] = OVERLAY_FILE
    except (ValueError, KeyError) as e:
        raise Broken(f"TDD のループの座を組めない: {e}") from None
    ledger = place / files.TDD_DELIVERED
    kinds = rules.kinds_for(ledger, {**values, "open_units": vals["open_units"]}, repo)
    when.update(_kinds_when(kinds, "tdd"))
    return vals, when, {"iteration": st["iterations"] + 1, "kinds": kinds, "ledger": ledger}


def tdd(place, repo, view: dict, values: dict) -> dict:
    node = "tdd-new" if view["new_unit"] else "tdd"
    vals, when, rnd = tdd_values(place, repo, view, values)
    try:
        out = prompt.emit(node, vals, when, prompt.round_of(node))
    except prompt.PromptError as e:
        raise Broken(f"TDD のループの指示を組めない: {e}") from None
    rules.remember(rnd["ledger"], rnd["kinds"], rnd["iteration"])
    return {"prompt": out["prompt"]}


# ---------------------------------------------------------------- 裁定役（ruler）
def ruler_values(place, got: dict) -> tuple[dict, dict]:
    """裁定役の指示の値。got は src/ruling.prep の返り {values, iteration}"""
    v = got["values"]
    start_vals, start_when = _starts(v)
    rejection = _rejection(place, "rule")
    vals = {**start_vals, "rejection": rejection, "conflicts_file": v["conflicts_file"], "ids": v["ids"],
            "judgment_file": shown(v.get("judgment_file")), "lang": prompt.lang(runvals.read(place)["lang"])}
    return vals, {**start_when, "rejected": bool(rejection)}


def ruler(place, got: dict) -> dict:
    """裁定役の指示を組んで place に書く。返り {prompt}"""
    vals, when = ruler_values(place, got)
    return {"prompt": prompt.emit("ruler", vals, when, prompt.round_of("ruler"))["prompt"]}


# ---------------------------------------------------------------- 合わせ役（clash-fix・clash-ruled）
def clash_values(place, pass_: str, accept: str, brief_file: str, patch_file: str) -> tuple[dict, dict]:
    v = runvals.read(place)
    start_vals, start_when = _starts({"policy_path": v["policy"], "request_file": v["request_file"]})
    rejection = _rejection(place, accept)
    vals = {**start_vals, "rejection": rejection, "brief_file": brief_file, "patch_file": patch_file,
            "marker_size": unittrees.DEFAULT_MARKER_SIZE, "lang": prompt.lang(v["lang"])}
    return vals, {**start_when, "rejected": bool(rejection), "first": pass_ == "first", "ruled": pass_ == "ruled"}


def clash(place, pass_: str, accept: str, brief_file: str, patch_file: str) -> dict:
    """合わせ役の指示を組んで place に書く。返り {prompt}"""
    node = CLASH[pass_]
    vals, when = clash_values(place, pass_, accept, brief_file, patch_file)
    return {"prompt": prompt.emit(node, vals, when, prompt.round_of(node))["prompt"]}


def error(place, node: str, why: str) -> None:
    """指示が組めなかった node と訳を place の prompt-error.json に足す"""
    path = pathlib.Path(place) / files.PROMPT_ERROR
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    rows = rows if isinstance(rows, list) else []
    path.write_text(json.dumps([*rows, {"node": node, "why": why}], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
