"""9 つの AI の node の指示に渡す値と段落の真偽（docs/design/fix.md の 2.3・3.3・4.3・5.3・6.3 の差し込み口の一覧）。

指示の文は prompts/ の md が持ち、ここは値を集めて prompt.emit に渡すだけ（書き手の指示と下請けのファイルは型の block が組む。ここは writer_slots で slots を渡す）。材料の行（brief・穴・範囲・
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
CLASH = {"first": "clash-fix", "ruled": "clash-ruled"}
CONSULT = {"first": "consult-answer", "ruled": "ruled-consult-answer"}
WRITER_KINDS = {"docs": "docs", "prompts": "prompts_kind", "config": "config", "code": "code"}   # 種類 → writer-rules の段落の名


class Broken(ValueError):
    """指示が組めない（brief の控えが壊れた・借りた写しが固定と違う・md と値の食い違い）"""


def shown(value) -> str:
    return str(value) if str(value or "").strip() else EMPTY


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
    """writer-rules の証拠の段落の真偽。続きの周は種類が全部偽で、見出しと頭の文ごと落とす。role は答えを書く場所の段落の名（この block は writer・tdd）"""
    got = {name: kind in kinds for kind, name in WRITER_KINDS.items()}
    return {**got, "evidence": any(got.values()), **{f"where_{r}": r == role for r in ("writer", "tdd", "rework")}}


def _check_cmd(config: str) -> str:
    return f"{sys.executable} {FACTS} {config}" if config else ""


# ---------------------------------------------------------------- 型ごとの書き手（tdd-close・pin・tidy・static・variant・remove と <型>-ruled）
SITES_WEAPONS = ("variant", "pin")   # 同じ決まりを共有する所を 1 か所ずつ壊して赤を見る証明（付録 A の F123）を書き手に言う型


def writer_when(weapon: str) -> dict:
    """型 weapon の書き手の指示で、型が選ぶ段落の真偽のうち義務の表から引く物（付録 A の行き先: 変える段の義務・壊して赤の証明・赤を見ない
    clean の拒否）。箱は duties.BOXES、赤を見ない clean を拒む型は受け付けと同じ board.RED_WEAPONS から引く（指示と照らしをそろえる）"""
    from src import duties
    return {"change": duties.box_of(weapon) == "change", "sites": weapon in SITES_WEAPONS, "red": weapon in board.RED_WEAPONS}


def writer_paragraphs(weapon: str) -> dict:
    """型 weapon が選ぶ書き手の md の段落の真偽のうち、義務の表から引く物（DUTY_WHEN。_slots が slots の when に入れ、
    tests/workflows/test_weapon_assets.py が組んだ指示の照らしに使う）。前の 4 つは writer_when を段落の名に引いた物、後ろの TABLE_WHEN は
    型の義務の表（duties.table_of）の関数の属性 paragraph が名指す段落（照らしを表に足せば指示も出る。書き手の返答の欄を読む義務の関数は
    paragraph を持つ。tests/blocks/fix/test_duty_paragraphs.py）。下請けの段落 spawns・g1・ask_variant は型の block の
    表 SPAWNS から本体 .shared/writerblock.paragraphs が引く（型の block は義務の表を知らず、修正の block は表 SPAWNS を知らない）"""
    from src import duties
    k = writer_when(weapon)
    table = {getattr(fn, "paragraph", None) for fn in duties.table_of(weapon)}
    return {"rules_change": k["change"], "rules_sites": k["sites"], "rules_red": k["red"], "conflict_change": k["change"],
            **{name: name in table for name in TABLE_WHEN}}


# 型の block の slots の values・when の鍵（形 .shared/schemas/writer-slots.schema.json の required と等しい。tests/blocks/fix/test_prompts.py が照らす）。
# 型が持つ値と段落（first_prompt・unattended・overlay_file・summary_file・g1_items と spawns・g1・ask_variant）は slots に入れない
SLOT_VALUES = ("rejection rulings_file saved_reply brief_rows faces_rows scope_rows tests_rows tests_how policy_path request_file "
               "judgment_file open_units plan_file notes_file budget draft check_cmd ripple_file libdocs_rows answer_file left lang").split()
SLOT_WHEN = ("rejected rulings_first ruled_reply briefs faces scope tests tests_new tests_tail tests_broken frozen_files tests_how rules ask "
             "ask_ripple libdocs resume queued overflow_answer conflict docs prompts_kind config code evidence where_writer where_tdd "
             "where_rework rules_change rules_sites rules_red conflict_change rules_sites_at rules_sites_test rules_red_unit rules_named policy no_policy "
             "request no_request").split()
TABLE_WHEN = ("rules_sites_at", "rules_sites_test", "rules_red_unit", "rules_named")   # 型の義務の表の関数の属性 paragraph から引く段落（where_writer は書き手に型を問わず載るので入れない）
DUTY_WHEN = ("rules_change", "rules_sites", "rules_red", "conflict_change", *TABLE_WHEN)   # 義務の表から引く段落（型の block は義務の表を知らない）


def no_subagents() -> dict:
    """slots の subagents の、下請けを起こす単位が無い周・続きの周の形（欄は全部置く。形 writer-slots.schema.json の required）"""
    return {"owed": [], "briefs": [], "all_items": [], "seat_brief_rows": "", "judgment_file": "", "policy_path": "", "base_rev": "",
            "check_cmd": "", "directory": ""}


def subagents_slot(values: dict, repo, briefs: list, owed_keys: list[str], green, config: str) -> dict:
    """slots の subagents（データだけ。下請けの値の関数は lib/subagents.py）: 下請けを起こす単位 owed（TDD の輪が緑にした単位 green を
    除く。rules.dispatched）・それに当たる凍結した brief の行・凍結した項目の全部の番号・直す義務の単位の brief を名指す行・判定のファイル・
    方針の文書・修正前の版（board.base_rev）・範囲の相談の確かめのコマンド・作業ツリーの根。型の block が下請けを起こすかは型の block の表
    （SPAWNS）が決め、ここは型を問わず同じ組み方で渡す"""
    owed = rules.dispatched(owed_keys, green)
    mine = planbrief.for_units(briefs, owed)
    return {"owed": owed, "briefs": [{"item": r["item"], "file": r["file"], "unit_keys": list(r.get("unit_keys") or [])} for r in mine],
            "all_items": [r["item"] for r in briefs], "seat_brief_rows": rules.brief_rows(mine, owed),
            "judgment_file": values.get("judgment_file") or "", "policy_path": values.get("policy_path") or "",
            "base_rev": board.base_rev(None, values.get("base_rev") or ""), "check_cmd": _check_cmd(config),
            "directory": "" if repo is None else str(repo)}


def _slots(place, repo, pass_: str, weapon: str, values: dict, *, owed, items=None, sources=None, frozen=None, shared=None,
           saved_reply: str = "", green=frozenset(), **_unused) -> tuple[dict, dict, dict]:
    """型 weapon の書き手の slots {values, when, subagents, summary_file} と周の控え {iteration, kinds, ledger}、writer の続きが要る物
    {briefs, config, owed_keys, values, continuing}。今の修正役の組み立ての順のまま（fixrules.prep）。型が持つ値と段落は組まない。
    範囲の相談の答えの後・はみ出しを相談に積んだ周は続きの段落だけ（回の数え直しをしない）。brief の控えが壊れていれば Broken"""
    from src import writers
    place = pathlib.Path(place)
    kind = writer_paragraphs(weapon)
    try:
        briefs = rules.briefs_or_halt(place, **(sources or {}))   # 裁定の文を書くより前に凍結する
    except ValueError as e:
        raise Broken(str(e)) from None
    ledger = writers.ledger(place, pass_, weapon)
    vals = {k: "" for k in SLOT_VALUES}
    when = {k: False for k in SLOT_WHEN}
    when["conflict"] = True
    when["conflict_change"] = kind["conflict_change"]   # 申し出の種類 not_red は変える段の書き手だけ（付録 A の W24）
    start_vals, start_when = _starts(values)
    vals.update(start_vals, lang=prompt.lang(runvals.read(place)["lang"]))
    when.update({k: False for k in start_when})
    slots = {"values": vals, "when": when, "subagents": no_subagents(), "summary_file": ""}   # 続きの周は下請けを組まない
    from src import consult
    got = consult.take(place, pass_)
    if got is not None:   # 範囲の相談の答えの後の周: 答えのファイルを名指すだけ（受け付けの回は数え直さない）
        rv = rules.resume_values(got)
        vals.update(answer_file=rv["answer_file"], left=rv["left"])
        when["overflow_answer" if rv["overflow"] else "resume"] = True
        return slots, {"iteration": max(1, rules.iteration_next(ledger) - 1), "kinds": None, "ledger": ledger}, {"continuing": True}
    if consult.queued(place, pass_):   # 受け付けがはみ出しを相談に積んだ周
        when["queued"] = True
        return slots, {"iteration": max(1, rules.iteration_next(ledger) - 1), "kinds": None, "ledger": ledger}, {"continuing": True}
    n = rules.iteration_next(ledger)
    when.update(start_when, rules=True, tests=True, tests_tail=True)   # テストの節は修正案の有無によらずいつも載る
    when.update({k: kind[k] for k in ("rules_change", "rules_sites", "rules_red", *TABLE_WHEN)})
    rejects = rolekit.rejected(place, writers.accept_name(pass_, weapon))
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
    vals["tests_how"] = board.tests_how_text(place)
    when["tests_how"] = bool(vals["tests_how"])
    for key in ("judgment_file", "open_units", "plan_file", "notes_file"):
        vals[key] = shown(values.get(key))
    if weapon == "tdd":   # 輪の要約を読むのは tdd の閉じの書き手だけ（付録 A の F26 の前半）。続きの周は組まない
        slots["summary_file"] = shown(values.get("summary_file"))
    config = rules.ask_config(place, repo, values, pass_, items=items)
    slots["subagents"] = subagents_slot(values, repo, briefs, owed_keys, green, config)
    if config:
        vals.update(budget=str(consult.BUDGET), draft=str(pathlib.Path(config).parent / rules.ASK_DRAFT), check_cmd=_check_cmd(config))
        when["ask"] = True
        ripple = str(values.get("ripple_file") or "").strip()
        if ripple:
            vals["ripple_file"] = ripple
            when["ask_ripple"] = True
    vals["libdocs_rows"] = _libdocs_rows(rules.lib_section(place, repo, values, shared))
    when["libdocs"] = bool(vals["libdocs_rows"])
    kinds = rules.kinds_for(ledger, values, repo)
    when.update(_kinds_when(kinds, "writer"))
    return (slots, {"iteration": n, "kinds": kinds, "ledger": ledger},
            {"continuing": False, "briefs": briefs, "config": config, "owed_keys": owed_keys, "values": values})


def writer_slots(place, repo, pass_: str, weapon: str, values: dict, **kw) -> tuple[dict, dict]:
    """型 weapon の書き手の slots（形 .shared/schemas/writer-slots.schema.json）と周の控え {iteration, kinds, ledger}。型を問わない値と
    段落だけを組む（型が持つ物は型の block の本体 .shared/writerblock.py が足す）。義務の表から引く段落（DUTY_WHEN）はここで引く。
    **kw は owed（今直す単位。必須）・items・sources・green（TDD の輪が緑にした単位。slots の subagents の下請けを起こす単位から除く）・frozen・
    shared・saved_reply。slots の subagents は型を問わず同じ組み方で渡す（下請けを起こすかは型の block の表 SPAWNS が決める）。控えは呼び手が
    slots を型の block に渡せた後に rules.remember に渡す"""
    slots, rnd, _ = _slots(place, repo, pass_, weapon, values, **kw)
    return slots, rnd


# ---------------------------------------------------------------- 相談の答えの役（consult-answer・ruled-consult-answer）
def consult_values(place, table: dict, asked: list, *, plan_file: str, ripple_file: str) -> tuple[dict, dict]:
    from src import consult
    import planmarks
    vals = {"plan_file": plan_file or "（修正案のファイルは無い）", "ripple_file": ripple_file, "count": len(asked),
            "asks": consult.asks_text(table, asked), "red": planmarks.AGREED_RED, "guard": planmarks.GUARD_KIND,
            "min_why": consult.MIN_WHY, "lang": prompt.lang(runvals.read(place)["lang"]), "history": consult.history_text(place)}
    gate = [a for a in asked if a.get("origin") == consult.ORIGIN_GATE]
    when = {"ripple": bool(ripple_file), "gate": bool(gate), "plain": len(gate) < len(asked), "history": bool(vals["history"]), "spawns": False}
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
    from src import common, tdd
    place = pathlib.Path(place)
    st, briefs = view["state"], view["briefs"]
    phase = st["phase"]
    owed = common._owed(st)
    vals = {k: "" for k in ("iteration phase brief_rows rejection policy_path request_file judgment_file open_units plan_file "
                            "notes_file skill seat_applies seat_not_applies unattended overlay_file test_cmd owed_units current_unit "
                            "together_rows named_rows handoff_rows later_rows tests_how runner_cmd lang").split()}
    when = {k: False for k in ("briefs rejected rules conflict docs prompts_kind config code phase_route phase_test phase_fix "
                               "phase_refactor gate current together named handoff later tests_how evidence where_writer where_tdd where_rework spawns "
                               "rules_change conflict_change").split()}
    when.update(rules=True, conflict=True, rules_change=True, conflict_change=True, **{f"phase_{phase}": True})
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
    if phase in ("fix", "refactor") and st.get("test_cmd_gate") == common.GATE_ON and tdd._cur(st)["unit_key"] not in st.get("light", []):
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
    ledger = place / (files.ROUTE_DELIVERED if phase == "route" else files.TDD_DELIVERED)   # 控えは振り分けと輪で分ける（輪は st["kinds"] から始める）
    kinds = rules.kinds_for(ledger, {**values, "open_units": vals["open_units"]}, repo, start=st.get("kinds") or ())
    when.update(_kinds_when(kinds, "tdd"))
    return vals, when, {"iteration": st["iterations"] + 1, "kinds": kinds, "ledger": ledger}


def tdd(place, repo, view: dict, values: dict) -> dict:
    """TDD の役と振り分けの役の指示を組んで place に書く（node は view の node か、単位が替わった周は tdd-new・続きは tdd。振り分けの
    段は src/route.prep が node route を渡す。どれも prompts/parts/tdd.md を組む）。返り {prompt}"""
    node = view.get("node") or ("tdd-new" if view["new_unit"] else "tdd")
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
            "judgment_file": shown(v.get("judgment_file")), "lang": prompt.lang(runvals.read(place)["lang"]),
            "red_at_base_decisions": " or ".join(f"`{d}`" for d in conflict.RED_AT_BASE_DECISIONS)}   # 受け付けの表のまま
    return vals, {**start_when, "rejected": bool(rejection), "spawns": False}


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
