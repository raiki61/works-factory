"""判定の裏取りの block の中身（docs/design/verify.md。lib/judgeverify.py と lib/judge_accept.py の裏取りの部分を、port の値で
受ける形に写した物）。

判定の開いた単位ごとの下請けのファイルと、相乗りの下請けのファイル、それを並べて起こす束ね役の指示を、prompts/judge-verify.md
1 本から段落を選んで組む。束ね役を起こす前の作業ツリーの写しを置き、出口で答えのファイルを型と番号で確かめて申し送りにまとめる。
指示の文は md が持ち、ここは材料と値だけを組む。

place のファイル（名はこのモジュールだけが持つ。verify.md の 1.4）:
- prep.json: {go, failed, reason}（支度の決めの控え）
- unit-<n>.md・synergy.md: 下請けのファイル
- judge-verify-prompt-<n>.md: 束ね役の指示（prompt.emit が書く）
- plan.json: {units: [{n, key}], answers}（番号の控え）
- tree.json: 束ね役を起こす前の作業ツリーの写し（accept.tree_state の形）
- answers/unit-<n>.json・answers/synergy.json: 下請けが Write で書く答え
- verify.json: 申し送り
"""
from __future__ import annotations

import copy
import json
import pathlib

import ports
import prompt

import accept     # lib/。作業ツリーの写しと比べ・in_repo・TREE_SCHEMA
import jsonfile   # lib/
import materialkit   # lib/。moved_since（作業ツリーの写しとの比べ）
import oneline    # lib/
import stopby     # lib/
from judgmark import is_open, open_units   # lib/。開いた単位の選び（diagnose・fix と共に読む判定の行の形）
from engine.schema import validate_schema   # lib/graphloops/engine/schema.py
from engine.util import Reject              # lib/graphloops/engine/util.py

from src import report

NODE = "judge-verify"                  # AI の node の id（prompts/judge-verify.md）
PREP_FILE = "prep.json"
PLAN_FILE = "plan.json"
TREE_FILE = materialkit.TREE   # 束ね役を起こす前の作業ツリーの写しの名（moved_since が読む名と同じ）
VERIFY_FILE = "verify.json"
SYNERGY_BRIEF = "synergy.md"
ANSWERS_DIR = "answers"
UNIT_BRIEF = "unit-{n}.md"
ANSWER_FILE = "unit-{n}.json"
SYNERGY_FILE = "synergy.json"
OWN_FILES = (PREP_FILE, PLAN_FILE, TREE_FILE, VERIFY_FILE, SYNERGY_BRIEF, f"{ANSWERS_DIR}/{SYNERGY_FILE}")
OWN_PROMPTS = (f"{NODE}-prompt-*.md",)
MIN_UNITS = 2                          # 回す開いた単位の数の下限（1 単位は相乗りが無く、事前審査の下請けと重なる）
SUBAGENT_TYPE = "general-purpose"      # 下請けの型は 1 つ（答えのファイルを書ける型）
CHECKED, UNVERIFIED = "checked", "unverified"
VERDICTS = ("root", "not_root", "unsure")
PLACES = ("same", "apart")             # 関わりの行の place: 同じ行・同じ塊（か前提を変える）・同じファイルの別の所だけ
WAITING = "裏取りの答えがまだ無い（束ね役が落ちたか、下請けを起こさなかった）"
STOP = stopby.declare("judge-verify", "判定の裏取りの束ね役か下請けが作業ツリーを変えた")
UNIT_LABEL, SYNERGY_LABEL = "Unit", "Synergy"   # 下請けのファイルの一覧の札（機械は読まない）
VALUE_NAMES = ("subagent_type", "files", "reply_schema", "view", "n", "unit_row", "all_units", "answer", "unit_schema",
               "synergy_schema")


# ---------------------------------------------------------------- 型
def output_format() -> dict:
    """束ね役の返答の型。答えの中身は答えのファイルにあり、返答は要約だけ（束ね役に写させない）"""
    return {"type": "object", "additionalProperties": False, "required": ["summary"],
            "properties": {"summary": {"type": "string", "minLength": 10}}}


def unit_schema() -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": ["unit", "verdict", "evidence_found", "evidence", "location_ok", "location", "why"],
            "properties": {"unit": {"type": "integer", "minimum": 1}, "verdict": {"type": "string", "enum": list(VERDICTS)},
                           "evidence_found": {"type": "boolean"}, "evidence": {"type": "string", "minLength": 10},
                           "location_ok": {"type": "boolean"}, "location": {"type": "string", "minLength": 1},
                           "why": {"type": "string", "minLength": 10}, "real_root": {"type": "string"}}}


def synergy_schema() -> dict:
    pair = {"type": "object", "additionalProperties": False, "required": ["units", "why"],
            "properties": {"units": {"type": "array", "minItems": 2, "items": {"type": "integer", "minimum": 1}},
                           "why": {"type": "string", "minLength": 4}}}
    relation = copy.deepcopy(pair)   # 関わりの行は place（PLACES）を持つ
    relation["required"] = relation["required"] + ["place"]
    relation["properties"]["place"] = {"type": "string", "enum": list(PLACES)}
    order = {"type": "object", "additionalProperties": False, "required": ["first", "then", "why"],
             "properties": {"first": {"type": "integer", "minimum": 1}, "then": {"type": "integer", "minimum": 1},
                            "why": {"type": "string", "minLength": 4}}}
    return {"type": "object", "additionalProperties": False, "required": ["why", "duplicates", "relations", "order"],
            "properties": {"why": {"type": "string", "minLength": 10}, "duplicates": {"type": "array", "items": pair},
                           "relations": {"type": "array", "items": relation},
                           "order": {"type": "array", "items": order}}}


JUDGMENT_SCHEMA = "shared:judgment.schema.json"   # 2 つ以上の block が使う判定の形（docs/design/verify.md の 1.2）


# ---------------------------------------------------------------- 判定の単位
def read_judgment(raw):
    """port judgment を共通の形で読み、この block が要る欄を足して照らす。共通の形（shared:judgment.schema.json）は単位の label を
    必須にしないが、開いた単位を選ぶ is_open が label を読むので、label が字でない単位はここで拒む（KeyError で落とさない）"""
    doc = ports.json(raw, JUDGMENT_SCHEMA)
    for n, u in enumerate(doc["units"], 1):
        if not isinstance(u, dict) or not isinstance(u.get("label"), str):
            raise ValueError(f"units の {n} 行目に label（字）が無い")
    return doc


def _unit_row(u: dict) -> dict:
    return {k: u[k] for k in ("key", "label", "disposition", "reason", "origin_analysis", "why_chain", "prescriptions") if k in u}


def _initial(units: list) -> dict:
    return {"units": [{"n": n, "key": u["key"], "state": UNVERIFIED, "errors": [WAITING]} for n, u in enumerate(units, 1)],
            "synergy": {"state": UNVERIFIED, "errors": [WAITING]}}


def _not_run(reason: str) -> dict:
    return {"units": [], "synergy": {"state": UNVERIFIED, "errors": [str(reason)]}}


def _load(path: pathlib.Path, schema: dict) -> tuple:
    """(答え, 誤りの行)"""
    if not path.is_file():
        return None, [f"答えのファイルが無い（{path}）"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, [f"答えのファイルが JSON として読めない（{oneline.one_line(e)}）"]
    errs = validate_schema(doc, schema)
    return (None, errs) if errs else (doc, [])


# ---------------------------------------------------------------- 支度
def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def _clean(out: pathlib.Path, judgment) -> None:
    """この block の名のファイルだけを名で引いて消す。前の起動の答えを今の判定の答えに数えない。answers/ と place は消さない"""
    ns = set()
    try:
        ns.update(range(1, len(open_units(read_judgment(judgment))) + 1))
    except ValueError:
        pass
    plan = jsonfile.read_or(out / PLAN_FILE)
    if isinstance(plan, dict) and isinstance(plan.get("units"), list):   # 前の控えの番号と今の番号の和（今の単位が多くても古い答えを残さない）
        ns.update(r["n"] for r in plan["units"] if isinstance(r, dict) and isinstance(r.get("n"), int))
    ns = sorted(ns)
    names = [*OWN_FILES, *(UNIT_BRIEF.format(n=n) for n in ns), *(f"{ANSWERS_DIR}/{ANSWER_FILE.format(n=n)}" for n in ns)]
    for name in names:
        (out / name).unlink(missing_ok=True)
    for pattern in OWN_PROMPTS:
        for path in out.glob(pattern):
            path.unlink()


def _values(lang: str, **given) -> dict:
    """全部の組で同じ口の組。入らない段落の口には空の字"""
    values = {name: "" for name in VALUE_NAMES}
    values.update(given)
    return {**values, "root": VERDICTS[0], "not_root": VERDICTS[1], "unsure": VERDICTS[2], "same": PLACES[0], "apart": PLACES[1],
            "lang": lang}


def _when(*, aggregator=False, view=False, unit=False, synergy=False) -> dict:
    return {"aggregator": aggregator, "view": view, "unit": unit, "synergy": synergy, "spawns": False}


def _build(out: pathlib.Path, judgment: dict, units: list, lang: str) -> dict:
    """4 通りの組を全部先に組む（組めなければ PromptError。ファイルは書かない）"""
    answers = out / ANSWERS_DIR
    view = json.dumps({k: judgment[k] for k in ("framing", "one_shot") if isinstance(judgment.get(k), str)},
                      ensure_ascii=False, indent=1)
    has_view = view != "{}"
    shown = view if has_view else ""
    briefs = {}
    for n, u in enumerate(units, 1):
        values = _values(lang, subagent_type=SUBAGENT_TYPE, view=shown, n=str(n),
                         unit_row=json.dumps(_unit_row(u), ensure_ascii=False, indent=1),
                         answer=str(answers / ANSWER_FILE.format(n=n)),
                         unit_schema=json.dumps(unit_schema(), ensure_ascii=False))
        briefs[out / UNIT_BRIEF.format(n=n)] = prompt.render(NODE, values, _when(view=has_view, unit=True))["prompt"]
    rows = "\n".join(f"- {UNIT_LABEL} {n}: {json.dumps(_unit_row(u), ensure_ascii=False)}" for n, u in enumerate(units, 1))
    values = _values(lang, subagent_type=SUBAGENT_TYPE, view=shown, all_units=rows, answer=str(answers / SYNERGY_FILE),
                     synergy_schema=json.dumps(synergy_schema(), ensure_ascii=False))
    briefs[out / SYNERGY_BRIEF] = prompt.render(NODE, values, _when(view=has_view, synergy=True))["prompt"]
    files = [f"- {UNIT_LABEL} {n}: {out / UNIT_BRIEF.format(n=n)}" for n in range(1, len(units) + 1)]
    files.append(f"- {SYNERGY_LABEL}: {out / SYNERGY_BRIEF}")
    agg = _values(lang, subagent_type=SUBAGENT_TYPE, files="\n".join(files), reply_schema=json.dumps(output_format(), ensure_ascii=False))
    prompt.render(NODE, agg, _when(aggregator=True))
    return {"briefs": briefs, "aggregator": agg}


def _off(out: pathlib.Path, reason: str, *, failed: bool) -> dict:
    (out / PLAN_FILE).unlink(missing_ok=True)
    jsonfile.write(out / VERIFY_FILE, _not_run(reason))
    jsonfile.write(out / PREP_FILE, {"go": False, "failed": failed, "reason": reason})
    return {"go": False, "prompt": "", "reason": reason}


def prep(out, *, judgment, lang) -> dict:
    """返り {go, prompt, reason}。開いた単位が MIN_UNITS 未満・port が読めない・指示が組めない時は go 偽（判定は消さない）"""
    out = pathlib.Path(out)
    _clean(out, judgment)
    try:
        doc = _port("judgment", lambda: read_judgment(judgment))
        text = prompt.lang(lang)
        units = open_units(doc)
    except ValueError as e:
        return _off(out, oneline.one_line(str(e)), failed=True)
    if len(units) < MIN_UNITS:
        return _off(out, f"開いた単位が {len(units)} つ（{MIN_UNITS} つ未満は相乗りが無く、裏取りを回さない）", failed=False)
    try:
        built = _build(out, doc, units, text)
        (out / ANSWERS_DIR).mkdir(parents=True, exist_ok=True)
        for path, body in built["briefs"].items():
            path.write_text(body, encoding="utf-8")
        emitted = prompt.emit(NODE, built["aggregator"], _when(aggregator=True), prompt.round_of(NODE))
        jsonfile.write(out / TREE_FILE, accept.tree_state(pathlib.Path.cwd()))
        jsonfile.write(out / PLAN_FILE, {"units": [{"n": n, "key": u["key"]} for n, u in enumerate(units, 1)],
                                          "answers": str(out / ANSWERS_DIR)})
        jsonfile.write(out / VERIFY_FILE, _initial(units))
        jsonfile.write(out / PREP_FILE, {"go": True, "failed": False, "reason": ""})
    except Exception as e:  # noqa: BLE001 — 支度は落ちない（出口が status: failed にする）
        return _off(out, oneline.one_line(f"判定の裏取りの支度の中で例外（{type(e).__name__}: {e}）"), failed=True)
    return {"go": True, "prompt": emitted["prompt"], "reason": ""}


# ---------------------------------------------------------------- 出口
def _check_unit(answers, n: int, key: str) -> dict:
    got, errs = _load(pathlib.Path(answers) / ANSWER_FILE.format(n=n), unit_schema())
    if got is not None:
        if got["unit"] != n:
            errs.append(f"$.unit: {n} でない（{got['unit']}）")
        if got["verdict"] == "not_root" and len(str(got.get("real_root") or "").strip()) < 4:
            errs.append("$.real_root: not_root なのに本当の根が書かれていない")
    if errs:
        return {"n": n, "key": key, "state": UNVERIFIED, "errors": errs}
    return {"n": n, "key": key, "state": CHECKED, **{k: v for k, v in got.items() if k != "unit"}}


def _check_synergy(answers, keys: dict) -> dict:
    got, errs = _load(pathlib.Path(answers) / SYNERGY_FILE, synergy_schema())
    if got is not None:
        nums = [x for row in got["duplicates"] + got["relations"] for x in row["units"]]
        nums += [x for row in got["order"] for x in (row["first"], row["then"])]
        errs += [f"単位 {x} は無い（単位は 1〜{len(keys)}）" for x in sorted(set(nums)) if x not in keys]
        errs += [f"$.duplicates・relations: 同じ単位だけを並べた行（{row['units']}）" for row in got["duplicates"] + got["relations"]
                 if len(set(row["units"])) < 2]
    if errs:
        return {"state": UNVERIFIED, "errors": errs}

    def group(rows):
        return [{"units": [keys[x] for x in dict.fromkeys(r["units"])], "why": r["why"],
                 **({"place": r["place"]} if "place" in r else {})} for r in rows]
    return {"state": CHECKED, "why": got["why"], "duplicates": group(got["duplicates"]), "relations": group(got["relations"]),
            "order": [{"first": keys[r["first"]], "then": keys[r["then"]], "why": r["why"]} for r in got["order"]]}


def _moved_since(out: pathlib.Path) -> list:
    """写しから今の作業ツリーが変わった所の文。写しが無い・読めない・形が違う時はその訳（閉じた側に倒す）。比べる欄は porcelain を除く
    （node が mutates_checkout: false で、Archon が前後の git status を照らすため）"""
    try:
        return materialkit.moved_since(out, pathlib.Path.cwd(), accept.status_keys(True))   # 写しの名は materialkit.TREE（TREE_FILE と同じ字）
    except (OSError, ValueError, Reject) as e:
        return [oneline.one_line(f"作業ツリーの写し {out / TREE_FILE} を使えない（{e}）——役を起こす前の作業ツリーと比べられない")]


def _result(out, status, stop_reason, reason, doc, ran) -> dict:
    return {"ok": status == "ok", "status": status, "stop_reason": stop_reason, "reason": reason,
            "verify": ports.pointer(out / VERIFY_FILE), "report": report.lines(doc, ran)}


def finish(out) -> dict:
    out = pathlib.Path(out)
    prep_doc = jsonfile.read_or(out / PREP_FILE)
    if not isinstance(prep_doc, dict):
        prep_doc = {"go": False, "failed": True, "reason": "判定の裏取りの支度が走らなかった（番号の控えが無い）"}
    plan = jsonfile.read_or(out / PLAN_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("units"), list):
        reason = str(prep_doc.get("reason") or "")
        if not (out / VERIFY_FILE).is_file():
            jsonfile.write(out / VERIFY_FILE, _not_run(reason))
        doc = jsonfile.read_or(out / VERIFY_FILE)
        return _result(out, "failed" if prep_doc.get("failed") else "ok", "", reason, doc, False)
    moved = _moved_since(out)
    answers = pathlib.Path(plan.get("answers") or out / ANSWERS_DIR)
    keys = {r["n"]: r["key"] for r in plan["units"]}
    rows = [_check_unit(answers, n, key) for n, key in keys.items()]
    syn = _check_synergy(answers, keys)
    doc = {"units": rows, "synergy": syn}
    jsonfile.write(out / VERIFY_FILE, doc)   # 作業ツリーが変わっていても書く
    if moved:
        reason = "判定の裏取りの束ね役か下請けが作業ツリーを変えた（読むだけの役）: " + "・".join(moved)
        return _result(out, "failed", STOP, reason, doc, True)
    bad = sum(r["state"] != CHECKED for r in rows)
    reason = "" if not bad and syn["state"] == CHECKED else (
        f"確かめられなかった物がある（単位 {bad} / {len(rows)}・相乗り {'確かめた' if syn['state'] == CHECKED else '確かめられなかった'}）")
    return _result(out, "ok", "", reason, doc, True)
