"""事前審査の材料のファイルと、指示の差し込み口の値と段落の真偽（docs/design/plan-review.md の 2 節・3.3・7.3）。

材料のファイル（review-material-<n>.md）は機械が貼る材料だけを持ち、指示の文を持たない。指示の文は全部 prompts/ の md と断片に在り、
ここは材料の行と短い英語の札（MAT_HEADS・LABELS）と、md と受け付け・読み手が同じ字を持つ値だけを持つ。

- write_material(place, intake, repo, *, n) -> (path, values, when): 材料のファイルを書き、prompts/review.md の差し込み口の値と段落の真偽
- fragment_values(fragments, place, intake, repo, *, b=None, material=None, spawns=False) -> (values, when): 名指した断片（"part:<名>"・
  "shared:<名>"・"node:<id>"）を prompt.py と同じ決まりで広げ、その中の差し込み口 {…} と段落の名の全部を、名ごとに 1 つの作り手
  （SLOTS・WHEN）で埋める。知らない名は KeyError（名を挙げる）。木の束ね役・下請けの指示（src/tree.py）と形 text（src/textform.py）も使う
- 写した部品（盤面 b を引数に取る形のまま。元の名のまま。b は src/view.view の見え方）: _names・unit_name・_item_rows・_opened・
  _map_rows・kept_keys・_later・_map_items・_counts_coverage・MAP_OTHERS・ITEM_MAP_OTHERS・TREE_AUTO_MIN・design_only・
  map_items_section・lib_section・_units_text・_defaults_line・_json_block・_replan_section・_shown_plan・_diff_part・
  _item_plan_part・rereview_part・_cross_part・ripple_section・uncovered・previous_passes・fields_section・deviations_section・
  recorded_rows・policy_example・concept_maps・policy_body・repository_line（写した元は lib/planblk.py・lib/boardview.py・
  lib/ripple.py・lib/converge.py・lib/planmarks.py・lib/policy.py・lib/concepthome.py。どの関数の docstring にも元を書く）

写した元と違う所: 元の関数が材料と一緒に貼っていた指示の文（DESIGN_ASK・DIFF_ASK・CROSS_ASK・SCOPE_ASK・REREVIEW_ASK・
planmarks.REVIEW_ASK・NO_MAP_KEYS・UNITS_LINE など）は md へ移し、ここは行と札だけを書く。日本語の見出しは英語の短い札にした。
lib の KEEP のモジュールが組む字（planmarks.answer_line・libdocs.section・design.element_lines の行）は、その字のまま貼る
（受け付けがその字で照らす物がある: design._pasted は要素の一覧の行を design.element_lines の字で見分ける）。
"""
from __future__ import annotations

import json
import pathlib
import re

import ports
import prompt

import concepthome   # lib/
import converge      # lib/
import design        # lib/
import gatemarks     # lib/
import libdocs       # lib/
import planmarks     # lib/
import policy        # lib/
import rolekit       # lib/
import worldmark     # lib/

from src import files, steps, view

BLOCK = pathlib.Path(__file__).resolve().parents[1]
PLAN_NODE = files.PLAN_NODE
REVIEW_NODE = files.REVIEW_NODE
# 入力 tree が auto の時に木にする開いた項目の数の下限（元 planblk.TREE_AUTO_MIN）
TREE_AUTO_MIN = 2
UNIT_ROW_KEYS = ("key", "label", "disposition", "reason")

# 材料のファイルの見出し（md が字のまま名指す。試験が md と材料の両方に在ることを照らす）
MAT_HEADS = {
    "defaults": "## Inputs read with defaults",
    "excluded": "## Excluded ranges",
    "libdocs": "## Library documents",
    "design": "## Independent design",
    "deviations": "## Deviations recorded in the plan",
    "fields": "## Works fields of the plan items",
    "map_items": "## Items that write design_map",
    "passes": "## Previous passes",
    "replan": "## Replan items",
    "machine": "## Machine-pasted material",
}
# 材料の中の札（英語の短い札。値の前に置く）
LABELS = {
    "fields_item": "### Plan item {n}",
    "machine_rows": f"{planmarks.MACHINE_KEY} (added by the machine)",
    "pass_blocks": "### Pass {n} blocks",
    "pass_owed": "### Pass {n} owed suggests",
    "face": "#### {key}",
    "answers": "Plan role's answers:",
    "held": "### Held items",
    "held_row": "- item {n} ({units}): {keys}",
    "replan_item": "### Item {n}",
    "replan_units": "- unit_keys: {keys}",
    "approved": "#### Approved item",
    "objection": "#### Objection and ruling ({id})",
    "revised": "#### Revised item",
    "plan": "Plan:",
    "open_item": "### Open item {n} ({units})",
    "item_plan": "#### Plan of item {n}",
    "diff": "#### Diff since the previous pass",
    "contract": "contract fields changed: {fields}",
    "unchanged": "(unchanged)",
    "ripple": "#### Ripple list of item {n} (the machine's git grep: callers and tests of the names the item changes)",
    "ripple_missing": "ripple list missing: {error}",
    "cross": "### Overlaps and other items' scope",
    "overlaps": "Overlaps:",
    "others": "Other items:",
    "none": "none",
    "units": "Units:",
    "view": "Judge's view:",
    "precedents": "Judge's precedents (world):",
    "map_items": "Items: {items} (rows for the other items — {others} — are not needed)",
    "map_carried": "Elements the other items received in earlier passes (already counted): {refs}",
    "map_keys": "Keys (one row each):",
    "no_keys": "no keys",
    "design_reason": "Designer's reason: {reason}",
    "design_not_stands": "The designer returned that the question does not stand: {reason}",
    "design_none": "None: {why}",
    "unit_files": "- reading the units' files: {why}",
    "versus": " (versus the standard practice: {note})",
}
REPO_LINE = "Repository: {repo} (read version: `{rev}`) BASE: `{base}` canonical rules: {review_md}"
# 形ごとの、この往復で design_map を照らさない項目を言う札（元 boardview.MAP_OTHERS。形 review は plan に名が変わった）
MAP_OTHERS = {"plan": "closed or held items", "replan": "items not ruled (approved before)"}
ITEM_MAP_OTHERS = "the other items"   # 木の下請けの項目のファイルが言う、その項目の外（元 planblk.ITEM_MAP_OTHERS）
WORLD_WORDS = {"same": "same", "differs": "differs", "none": "none"}


# ---------------------------------------------------------------- 写した部品（盤面 b の読み）
def _names(b, nid: str) -> list:
    """単位の名の並び（元 planblk._names。見え方の pointer_rows が入口の names を返す）"""
    return next((p.get("names") or [] for p in b.pointer_rows(nid)["pointers"] or []), [])


def unit_name(names: list, k):
    """役が返した単位の番号（1 から）を names の単位の名に戻す唯一の口（元 planblk.unit_name）。戻せない値は k のまま（範囲の外の
    番号は int のまま残り、字の名と比べる照らしが必ず拒む。数字の字の名に化けさせない）"""
    return names[k - 1] if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(names) else k


def _item_rows(b) -> list:
    """今の案の項目（見え方の修正案の役の返答の行に、項目の works の欄を重ねた物。番号は並びの順。元 planblk._item_rows）"""
    doc = b.output_of_round(PLAN_NODE, b.round)
    plan = doc.get("plan") if isinstance(doc, dict) else None
    fields = planmarks.read(b) or []
    rows = plan if isinstance(plan, list) else []
    return [{**(r if isinstance(r, dict) else {}), **(f if isinstance(f, dict) else {})}
            for r, f in zip(rows + [{}] * (len(fields) - len(rows)), fields + [{}] * (len(rows) - len(fields)))]


def _opened(b, rows: list) -> list:
    """今の往復の事前審査が見る項目の番号（項目の控えが在れば開いた項目 converge.open_items、無ければ案の全部の項目。元 planblk._opened）"""
    plan = converge.read(b).get("plan")
    return [n for n in (converge.open_items(b) if plan else range(1, len(rows) + 1)) if n <= len(rows)]


def _map_rows(b, items: list) -> list:
    """design_map を照らす案の行: 往復の記録の作業の写しの案の項目 items の行に item の番号を足した物（範囲の外の番号は捨てる）。
    受け付けの照らし（src/take.py の design_gaps）と、材料の design_map を書く項目の節（map_items_section）が同じ行から組む（元 planblk._map_rows）"""
    plan = converge.read(b).get("plan") or []
    return [{**plan[n - 1].get("row", {}), "item": n} for n in items if 1 <= n <= len(plan)]


def kept_keys(b, items: list) -> set:
    """2 往復目からの形 plan で、項目 items の design_map の鍵のうち、前の往復のその項目の行（converge.prev_row）にも在った鍵
    （design.kept_keys。変わっていない行の突き合わせは書き直させない。前の行の無い項目と 1 往復目は空。元 planblk.kept_keys）"""
    out = set()
    for n in items:
        old = converge.prev_row(b, n)
        if old is not None:
            out |= design.kept_keys([{**old, "item": n}], _map_rows(b, [n]))
    return out


def _later(b, intake: dict) -> bool:
    """2 往復目からの形 plan か（材料は開いた項目の差分と波及の一覧だけにし、design_map は変わっていない鍵を求めない。元 boardview._later）"""
    return intake.get("form") == "plan" and bool(converge.read(b)["passes"])


def _map_items(b, intake: dict) -> list:
    """この往復で design_map を照らす項目の番号（受け付けと、木にしない往復の材料の節 map_items_section が引く。元 boardview._map_items）:
    形 replan は裁かれた項目 ruled、形 plan は開いた項目 converge.open_items"""
    return list(intake.get("ruled") or []) if intake.get("form") == "replan" else converge.open_items(b)


def _counts_coverage(intake: dict) -> bool:
    """独立設計の要素の網羅を数える往復か（受け付けの coverage_gaps と、材料の節の数え済みの行が引く。元 boardview._counts_coverage）。
    網羅は案の全部の項目を審査する往復（形 plan）だけで数える。形 replan は裁かれた項目だけを見るので、鍵・重なり・design_ref の実在・引用だけ"""
    return intake.get("form") == "plan"


def _json_block(doc) -> list:
    """JSON の囲いの行（元 boardview._json_block）"""
    return ["```json", json.dumps(doc, ensure_ascii=False, indent=1), "```"]


def _units_text(b) -> str:
    """直す単位（番号 no つき。元 boardview._units_text）"""
    rows = [{"no": n, **{k: u[k] for k in UNIT_ROW_KEYS if k in u}} for n, u in enumerate(b.record["units"], 1)]
    return json.dumps(rows, ensure_ascii=False, indent=1)


def _defaults_line(intake: dict) -> str:
    """既定で読んだ入力の訳の節（無ければ空。元 boardview._defaults_line）"""
    rows = [str(x) for x in intake.get("defaults") or [] if str(x).strip()]
    return f"{MAT_HEADS['defaults']}\n\n" + "\n".join(f"- {x}" for x in rows) if rows else ""


def _shown_plan(intake: dict) -> list:
    """材料に貼る修正案の項目（1 往復目の形 plan と形 replan。2 往復目からの形 plan は rereview_part）: 形 plan は全部、形 replan は裁かれた
    項目だけ（直していない項目の案を見せない。元 boardview._shown_plan）"""
    rows = (intake.get("plan") or {}).get("plan") or []
    if intake.get("form") != "replan":
        return rows
    ruled = set(intake.get("ruled") or [])
    return [r for n, r in enumerate(rows, 1) if n in ruled]


def _given_design(b):
    """(設計の返答 | None, 壊れた訳)。design.made の写しの読み"""
    return design.made(b.dir, b.design_schema)


def design_only(b, intake: dict | None = None) -> str:
    """材料の独立設計の節（元 planblk.design_only の材料の部分。突き合わせの頼み DESIGN_ASK は md の parts/design-ask.md へ）。
    設計が立つ時は設計の役の理由・本文の印 design.BODY_OPEN と BODY_CLOSE で挟んだ本文・要素の行（design.element_lines の行の字）。
    立たない時は premise_invalid_reason（空なら reason）に design.anchor_note。無い時は訳の 1 行（port design_why、空なら DESIGN_NOT_GIVEN）"""
    got, broken = _given_design(b)
    head = MAT_HEADS["design"]
    if got is None:
        why = broken or str((intake or {}).get("design_why") or "").strip() or steps.DESIGN_NOT_GIVEN
        return f"{head}\n\n" + LABELS["design_none"].format(why=why)
    if not got["question_stands"]:
        r = got.get("premise_invalid_reason") or got["reason"]
        return f"{head}\n\n" + LABELS["design_not_stands"].format(reason=r + design.anchor_note(r))
    rows = design.element_lines(got).split("\n\n", 1)
    elements = rows[1] if len(rows) == 2 else ""
    return (f"{head}\n\n" + LABELS["design_reason"].format(reason=got["reason"])
            + f"\n\n{design.BODY_OPEN}\n{got['design']}\n{design.BODY_CLOSE}" + (f"\n\n{elements}" if elements else ""))


def design_state(b) -> str:
    """独立設計の 3 つの段落のどれか（stands・not_stands・none）"""
    got, _ = _given_design(b)
    if got is None:
        return "none"
    return "stands" if got["question_stands"] else "not_stands"


def map_items_section(b, items: list, others: str, *, carried: bool, kept=()) -> str:
    """design_map を書く項目の節（独立設計が立たない run では ""。元 planblk.map_items_section の材料の部分。読み方の文と NO_MAP_KEYS は
    review.md の段落 map_items へ）。items は受け付けが design_map を照らす項目の番号、others はそれ以外の項目を言う札（MAP_OTHERS か
    ITEM_MAP_OTHERS）。carried が真なら、ほかの項目が前の往復で受けた独立設計の要素（converge.carried_refs）を数え済みの行に並べる。
    鍵の一覧は design.wanted_lines（受け付けと同じ案の行 _map_rows と同じ kept から）。鍵が無く kept も無ければ札 no keys"""
    if design.stands(b.dir, b.design_schema) is None:
        return ""
    names = "・".join(str(n) for n in sorted(items or [])) or LABELS["none"]
    lines = [MAT_HEADS["map_items"], "", LABELS["map_items"].format(items=names, others=others)]
    refs = sorted(converge.carried_refs(b, items or [])) if carried else []
    if refs:
        lines.append(LABELS["map_carried"].format(refs="・".join(refs)))
    keys = design.wanted_lines(_map_rows(b, items or []), kept)
    if keys:
        lines += ["", LABELS["map_keys"], *keys]
    elif items and not kept:
        lines += ["", LABELS["no_keys"]]
    return "\n".join(lines)


def lib_section(b, repo, shared=None) -> str:
    """判定の単位のファイルが使うライブラリの文書の節（元 planblk.lib_section）。本文は libdocs.section の字（控えは place の libdocs/。
    shared は run をまたぐ控えの根。None なら使わない）"""
    judgment = pathlib.Path(b.dir) / files.JUDGMENT
    files_, why = libdocs.unit_files(repo, str(judgment)) if judgment.is_file() else ([], f"{files.JUDGMENT} が無い")
    text = libdocs.section(pathlib.Path(b.dir) / files.LIBDOCS, repo, files_, shared=shared)
    title = str(libdocs.TITLE)
    body = text[len(title):].lstrip("\n") if text.startswith(title) else text
    return f"{MAT_HEADS['libdocs']}\n\n{body}" + (f"\n{LABELS['unit_files'].format(why=why)}" if why else "")


def deviations_section(b, place: pathlib.Path) -> str:
    """修正案の欄 structure の外れの訳の節（元 planmarks.review_section の外れの行の部分）。行は planmarks.answer_line の字、世界の解の類の
    行には定石との比べ（worldmark.challenges）を尾に。外れが無ければ空。控えは planmarks.frozen で読む（凍結の印と食い違えば FieldsBroken）"""
    fields = planmarks.frozen(b)
    devs = planmarks.deviations(fields)
    if not devs:
        return ""
    notes = worldmark.challenges(worldmark.stage_rows(place, worldmark.COPY_STATE) or [])
    return f"{MAT_HEADS['deviations']}\n\n" + "\n".join(
        f"- {planmarks.answer_line(d)}" + (LABELS["versus"].format(note=notes[d["world"]]) if notes.get(d.get("world")) else "")
        for d in devs)


def fields_section(b) -> str:
    """項目ごとの works の欄の節（元 planmarks.review_section の欄の部分と _item_block。見る点の頼み REVIEW_ASK と MACHINE_LABEL の説明は
    review.md の段落 fields へ）。機械の足した欄 planmarks.MACHINE_KEY は役の書いた欄から外し、空でなければ札の後に別の JSON。
    控えが無ければ空。凍結の印と食い違えば FieldsBroken"""
    fields = planmarks.frozen(b)
    if fields is None:
        return ""
    parts = [MAT_HEADS["fields"]]
    for n, f in enumerate(fields, 1):
        f = f if isinstance(f, dict) else {}
        rows = [LABELS["fields_item"].format(n=n), "", *_json_block({k: v for k, v in f.items() if k != planmarks.MACHINE_KEY})]
        if f.get(planmarks.MACHINE_KEY):
            rows += ["", LABELS["machine_rows"], "", *_json_block({planmarks.MACHINE_KEY: f[planmarks.MACHINE_KEY]})]
        parts.append("\n".join(rows))
    return "\n\n".join(parts)


def _face_rows(f: dict) -> str:
    """前の往復の穴の行（元 converge._face_text。見出しの段だけ下げた）"""
    return "\n".join([LABELS["face"].format(key=f["key"]), *(f"- {k}: {f[k]}" for k in converge.FACE_KEYS[1:] if k in f),
                      *([f"- {converge.REACH}: {f[converge.REACH]}"] if converge.REACH in f else [])])


def _units_of(it: dict) -> str:
    return "、".join(str(k) for k in it.get("unit_keys") or [])


def previous_passes(b) -> str:
    """2 往復目からの前の往復の節（元 converge.review_section の行の部分。頼み REREVIEW_ASK と HELD_CITES は md へ）: 往復ごとの block の穴・
    答えの要る suggest（converge.owed_faces）・修正案の役の答え。最後の往復に保留の項目が在れば、保留の項目ごとの block の key。1 往復目は空"""
    doc = converge.read(b)
    passes = doc["passes"]
    if not passes:
        return ""
    replies = [p.get("answers", []) for p in passes[1:]] + [doc["open"].get("answers", [])]
    parts = [MAT_HEADS["passes"]]
    for p, answers in zip(passes, replies):
        parts.append(LABELS["pass_blocks"].format(n=p["pass"]))
        parts += [_face_rows(f) for f in p["faces"]] or [f"- {LABELS['none']}"]
        suggests = [f for f in converge.owed_faces(doc, p) if f["severity"] != "block"]
        if suggests:
            parts.append(LABELS["pass_owed"].format(n=p["pass"]))
            parts += [_face_rows(f) for f in suggests]
        parts.append(LABELS["answers"] + "\n" + ("\n".join(f"- {a.get('key')}: {a.get('handled')}（{a.get('how')}）"
                                                         for a in answers if isinstance(a, dict)) or f"- {LABELS['none']}"))
    held = [it for it in passes[-1].get("items") or [] if it.get("state") == converge.HELD]
    if held:
        parts.append("\n".join([LABELS["held"], *(LABELS["held_row"].format(
            n=it["n"], units=_units_of(it), keys="、".join(it.get("blocks") or []) or LABELS["none"]) for it in held)]))
    return "\n\n".join(parts)


def _replan_section(row: dict) -> str:
    """案の直しの項目ごとの節: 番号・unit_keys（字のまま）・承認済みの前の項目・申し出と裁定の行（字のまま）・直した項目（決め手の欄つき）
    （元 boardview._replan_section。6 つの札は今の札を英語にした物で、欄の名は字のまま）"""
    old = row["old"]
    lines = [LABELS["replan_item"].format(n=row["item"]), "",
             LABELS["replan_units"].format(keys=json.dumps(old.get("unit_keys"), ensure_ascii=False)), "",
             LABELS["approved"], "", *_json_block(old)]
    for c in row.get("rows") or []:
        ru = c.get("ruling") or {}
        lines += ["", LABELS["objection"].format(id=c.get("id")), "",
                  f"- unit of the objection: {c.get('unit_key')}",
                  f"- named by the objection (between): {', '.join(c.get('between') or [])}",
                  f"- reason of the objection (why_both_cannot_hold): {c.get('why_both_cannot_hold')}",
                  f"- kind of the objection (kind): {c.get('kind') or LABELS['none']}",
                  f"- side seen as right (which_is_right): {c.get('which_is_right')}",
                  f"- text of the ruling ({ru.get('decision')}): {ru.get('text')}"]
    lines += ["", LABELS["revised"], "", *_json_block(row["new"])]
    return "\n".join(lines)


def uncovered(doc: dict, n: int) -> list[dict]:
    """項目 n（1 始まり）の覆っていない当たり（一覧に項目が無ければ []。元 ripple.uncovered。ripple は plan へ移るので写す）"""
    for it in (doc or {}).get("items") or []:
        if it.get("item") == n:
            return list(it.get("uncovered") or [])
    return []


def _ripple_names(rows: list) -> list[str]:
    out = []
    for r in rows:
        if r.get("common"):
            out.append(f"- {r['name']}: hits in {r['files']} files (common name: only the count)")
            continue
        out.append(f"- {r['name']}: hits in {r['files']} files")
        out += [f"  - code {at}" for at in r.get("code") or []]
        out += [f"  - test {at}" for at in r.get("tests") or []]
    return out


def ripple_section(doc: dict, n: int) -> str:
    """項目 n の波及の一覧の節（元 ripple.section(doc, n) と item_text。札は英語。頼み SCOPE_ASK と ERROR_NOTE は md の parts/diff-ask.md へ）。
    一覧に誤りが在れば札 ripple list missing と訳"""
    head = LABELS["ripple"].format(n=n)
    if (doc or {}).get("error"):
        return f"{head}\n\n" + LABELS["ripple_missing"].format(error=doc["error"])
    it = next((x for x in (doc or {}).get("items") or [] if x.get("item") == n), None)
    if it is None:
        return f"{head}\n\nNo name the item changes was found in the target (no hits)."
    lines = [head, "", f"unit_keys: {'、'.join(map(str, it.get('unit_keys') or []))}", "", "Names it changes and their hits:"]
    lines += _ripple_names(it.get("names") or []) or ["- no name of the target"]
    lines += ["", "Uncovered hits:"]
    removed = {"removed", "removed_test"}
    lines += [f"- {h['id']}: {h['kind']} {h['at']} (name {h['name']})" + (" (left over after a removed name)" if h["kind"] in removed else "")
              for h in it.get("uncovered") or []] or [f"- {LABELS['none']}"]
    return "\n".join(lines)


def _ripple(place: pathlib.Path) -> dict:
    """place の波及の一覧の写し（無い・読めなければ一覧が無い訳。入口が空の port でも写しを置く）"""
    try:
        doc = json.loads((place / files.RIPPLE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"items": [], "overlaps": [], "error": steps.NO_RIPPLE}
    return doc if isinstance(doc, dict) else {"items": [], "overlaps": [], "error": steps.NO_RIPPLE}


def _diff_part(b, n: int) -> str:
    """2 往復目から: 前の往復のこの項目の案の行と今の行の文の差（converge.sentence_diff。消した文を -、足した文を + で、場所を添える。
    変わっていない文は載せない）。約束の欄（planmarks.contract_diff）が変わった項目は札で変わった欄の名を言う。前の行が無ければ空
    （呼び手が項目の全体を貼る。元 planblk._diff_part。頼み DIFF_ASK は md の parts/diff-ask.md へ）"""
    old = converge.prev_row(b, n)
    plan = converge.read(b).get("plan") or []
    new = plan[n - 1].get("row") if 1 <= n <= len(plan) else None
    if old is None or new is None:
        return ""
    gone, came, _ = converge.sentence_diff(old, new)
    lines = [f"- {at}: {text}" for at, text in gone] + [f"+ {at}: {text}" for at, text in came]
    fields = planmarks.contract_diff(old, new)
    head = [LABELS["diff"], ""] + ([LABELS["contract"].format(fields="・".join(fields)), ""] if fields else [])
    return "\n".join(head) + "\n```diff\n" + ("\n".join(lines) or LABELS["unchanged"]) + "\n```"


def _item_plan_part(b, n: int, it: dict) -> str:
    """項目 n の案の節: 前の往復の行が在れば差分（_diff_part）、無ければ（1 往復目・組み替えた新しい項目）行の全体（元 planblk._item_plan_part）"""
    return _diff_part(b, n) or "\n".join([LABELS["item_plan"].format(n=n), "", *_json_block(it)])


def _cross_part(rows: list, opened: list, rip: dict) -> str:
    """単独の審査役が項目どうしの食い違いを見る節（木の道では相乗りの審査が持つ。元 planblk._cross_part。頼み CROSS_ASK は md へ）: 波及の
    一覧の重なりのうち開いた項目に当たる行と、開いた項目から見たほかの項目の unit_keys・allowed_paths・files の path。一覧が誤りなら
    重なりは「無い」でなく一覧が無い訳を書く"""
    over = [f"- {o['at']}: item {', '.join(map(str, o['items']))}" for o in rip.get("overlaps") or [] if set(o["items"]) & set(opened)]
    if rip.get("error"):
        over = [f"- {LABELS['ripple_missing'].format(error=rip['error'])}"]
    others = [m for m in range(1, len(rows) + 1) if any(m != n for n in opened)]
    scope = []
    for m in others:
        it = rows[m - 1]
        scope += [f"- item {m} ({_units_of(it)})",
                  f"  - allowed_paths: {'、'.join(str(x) for x in it.get('allowed_paths') or []) or LABELS['none']}",
                  f"  - files: {'、'.join(str(f.get('path')) for f in it.get('files') or [] if isinstance(f, dict)) or LABELS['none']}"]
    return "\n".join([LABELS["cross"], "", LABELS["overlaps"], *(over or [f"- {LABELS['none']}"]), "", LABELS["others"], *scope])


def rereview_part(b, place: pathlib.Path | None = None) -> str:
    """木にしない 2 往復目からの形 plan の材料で、修正案の全体の代わりに貼る節（元 planblk.rereview_part）: 開いた項目ごとに、案の差分
    （前の行の無い項目は全体。_item_plan_part）と波及の一覧（ripple_section）。項目が 2 つ以上なら項目どうしの節（_cross_part）を足す"""
    rows = _item_rows(b)
    rip = _ripple(pathlib.Path(place or b.dir))
    opened = _opened(b, rows)
    parts = []
    for n in opened:
        parts += [LABELS["open_item"].format(n=n, units=_units_of(rows[n - 1])), _item_plan_part(b, n, rows[n - 1]),
                  ripple_section(rip, n)]
    if len(rows) >= 2 and opened:
        parts.append(_cross_part(rows, opened, rip))
    return "\n\n".join(parts)


def repository_line(repo, intake: dict) -> str:
    """材料と方針の文の指示の Repository の行（元 planfile.repo_line。BASE が空なら読む版）"""
    rev = str(intake.get("review_rev") or "HEAD")
    return REPO_LINE.format(repo=repo, rev=rev, base=str(intake.get("diff_base") or rev), review_md=files.REVIEW_MD)


# ---------------------------------------------------------------- 記録された方針・方針・考えの住処の地図
def _recorded(intake: dict) -> list:
    return [r for r in intake.get(policy.RECORDED_KEY) or [] if isinstance(r, dict)]


def _cut(text) -> str:
    """一覧に並べる答え・論点の頭（元 policy._head の 120 字）"""
    text = " ".join(str(text or "").split())
    return text if len(text) <= 120 else text[:120] + "…"


def recorded_rows(rows: list) -> str:
    """共通の断片 recorded-policy の {recorded_rows}（元 policy._section の行の部分を英語の札にした物。名指しの字 name は変えない）"""
    of = {s: [r for r in rows if r.get("source") == s] for s in ("doc", "answer", "gate", "push", "settled")}
    doc = of["doc"][0] if of["doc"] else None
    out = ["- policy document: " + (f"named `{doc['name']}:<line>` (lines 1-{doc.get('lines', 0)}; original place "
                                    f"{doc.get('alias') or 'none'})" if doc else "none")]
    out.append("- request answers:" + ("" if of["answer"] else " none"))
    out += [f"  - named `{r['name']}`: {_cut(r.get('text'))}" for r in of["answer"]]
    out.append("- a person's answers at approval nodes:" + ("" if of["gate"] else " none"))
    out += [f"  - named `{r['name']}`: {_cut(r.get('text'))}" for r in of["gate"]]
    if of["push"]:
        out.append("- recommendations an unattended run adopted at an approval node or a held question (not a person's answers):")
        out += [f"  - named `{r['name']}`: {_cut(r.get('text'))}" for r in of["push"]]
    out.append("- settled points (decision records):" + ("" if of["settled"] else " none"))
    out += [f"  - named `{r['name']}`: {_cut(r.get('text'))}" if r.get("name")
            else f"  - (no `where`, so it cannot be named) {_cut(r.get('text'))}" for r in of["settled"]]
    return "\n".join(out)


def policy_example(rows: list) -> str:
    """kind policy の穴の書き方の例の JSON 1 行（元 policy.face_example の行の部分）。rows の最初の名指せる行で作る（方針の文書の行は
    <写し>:1、ほかは名指しの字のまま。名指せるかは受け付けの policy.face_gaps と同じ policy.hits で決める）。名指せる行が無ければ空"""
    for r in rows:
        by = f"{r['name']}:1" if r.get("source") == "doc" and r.get("name") else r.get("name")
        if by and policy.hits([r], by):
            return json.dumps({"kind": policy.POLICY_KIND, "severity": "suggest", "decided_by": by}, ensure_ascii=False)
    return ""


def _named_rows(rows: list) -> bool:
    return any(r.get("name") for r in rows)


def _doc_row(rows: list) -> bool:
    return any(r.get("source") == "doc" for r in rows)


def policy_body(path) -> str:
    """方針の文書の本文。policy.PASTE_CAP バイトまで。超えたら先頭を切り、続きの置き場を末尾に書く（元 policy._capped。
    independent-design の steps.policy_body と同じ）"""
    data = pathlib.Path(path).read_bytes()
    if len(data) <= policy.PASTE_CAP:
        return data.decode("utf-8", "replace")
    note = f"\n\n［方針の文書は {len(data)} バイトで、{policy.PASTE_CAP} バイトまでを貼った。続きは {path}］\n"
    room = policy.PASTE_CAP - len(note.encode("utf-8"))
    return data[:room].decode("utf-8", "ignore") + note


def concept_maps(repo) -> tuple[list[str], str]:
    """考えの住処の地図の行と、木を読めなかった訳（元 concepthome.section の行の部分）。行は `- <パス>`（最大 concepthome.MAX_MAPS、
    超えた分は `- N more`）"""
    names, why = concepthome.tracked_names(pathlib.Path(repo))
    maps, total = concepthome.pick_maps(names)
    lines = [f"- {m}" for m in maps]
    if total > len(maps):
        lines.append(f"- {total - len(maps)} more")
    return lines, why


# ---------------------------------------------------------------- 差し込み口と段落の作り手
class _Ctx:
    """作り手が読む物（place・intake・repo・見え方 b・材料のファイル）。重い読みは 1 回だけ"""

    def __init__(self, place, intake, repo, b=None, material=None, spawns=False):
        self.place = pathlib.Path(place)
        self.intake = intake
        self.repo = pathlib.Path(repo)
        self._b = b
        self.material = material
        self.spawns = spawns
        self._maps = None

    @property
    def b(self):
        if self._b is None:
            self._b = view.view(self.place, self.intake)
        return self._b

    @property
    def text(self) -> bool:
        return self.intake.get("form") == "text"

    @property
    def node(self) -> str:
        return files.TEXT_NODE if self.text else REVIEW_NODE

    @property
    def rows(self) -> list:
        return _recorded(self.intake)

    @property
    def maps(self):
        if self._maps is None:
            self._maps = concept_maps(self.repo)
        return self._maps

    def stands(self) -> str:
        return "none" if self.text else design_state(self.b)

    def later(self) -> bool:
        return not self.text and _later(self.b, self.intake)


def _policy_path(c: _Ctx) -> str:
    path = str(c.intake.get("policy_copy") or "")
    return path if path and pathlib.Path(path).is_file() else ""


def _world_rows(c: _Ctx) -> str:
    rows = [r for r in c.intake.get("world") or [] if isinstance(r, dict)]
    rows.sort(key=lambda r: ((r.get("versus") or {}).get("verdict") != "differs"))
    out = []
    for r in rows:
        v = r.get("versus") or {}
        urls = ", ".join(str(s.get("url")) for s in r.get("sources") or [] if isinstance(s, dict) and s.get("url")) or LABELS["none"]
        mark = "" if r.get("basis") == worldmark.WEB else " (not confirmed on the web)"
        out.append(f"- {r.get('problem')}: practice {r.get('practice')}{mark} (sources: {urls})"
                   f" · versus {WORLD_WORDS.get(v.get('verdict'), v.get('verdict'))}"
                   + (f" · proposed {v.get('proposed')}" if v.get("proposed") else "")
                   + (f" · challenge {v.get('challenge')}" if v.get("challenge") else ""))
    return "\n".join(out)


def _framing(c: _Ctx) -> str:
    diag = c.intake.get("diagnosis") or {}
    got = {k: diag[k] for k in ("framing", "one_shot") if k in diag}
    return json.dumps(got, ensure_ascii=False) if got else ""


def _recommend_shape() -> str:
    """推しの形（gatemarks の RECOMMEND_KEYS・RECOMMEND_ANSWERS・RECOMMEND_MIN から。欄の意味は md の head.md が書く）"""
    head, *rest = gatemarks.RECOMMEND_KEYS
    return ("{" + f"{head}: " + " | ".join(gatemarks.RECOMMEND_ANSWERS)
            + "".join(f", {k}: … ({gatemarks.RECOMMEND_MIN} characters or more)" for k in rest) + "}")


# 差し込み口の名 → 作り手（名ごとに 1 つ）
SLOTS = {
    "rejection": lambda c: rolekit.rejects_text(rolekit.rejected(c.place, c.node)),
    "material_file": lambda c: str(c.material or ""),
    "purpose": lambda c: str(c.intake.get("purpose") or "").strip(),
    "proposal": lambda c: str(c.intake.get("proposal_text") or "").strip(),
    "world": _world_rows,
    "repository_line": lambda c: repository_line(c.repo, c.intake),
    "framing": _framing,
    "design_body": lambda c: design_only(c.b, c.intake),
    "lang": lambda c: prompt.lang(c.intake.get("lang") or ""),
    "home_prefix": lambda c: concepthome.PREFIX,
    "no_narrow": lambda c: gatemarks.NO_NARROW,
    "no_narrow_min": lambda c: gatemarks.NO_NARROW_MIN,
    "recommend": lambda c: gatemarks.RECOMMEND,
    "recommend_shape": lambda c: _recommend_shape(),
    "stuck_push": lambda c: converge.STUCK_PUSH,
    "policy_doc_fence": lambda c: policy.POLICY_DOC_FENCE,
    "drift_head": lambda c: design.DRIFT_HEAD,
    "unpaired_head": lambda c: design.UNPAIRED_HEAD,
    "row_quote_keys": lambda c: ", ".join(f"`{k}`" for k in design.ROW_QUOTE_KEYS),
    "body_open": lambda c: design.BODY_OPEN,
    "body_close": lambda c: design.BODY_CLOSE,
    "machine_key": lambda c: planmarks.MACHINE_KEY,
    "minimal_head": lambda c: files.MINIMAL_HEAD,
    "short_head": lambda c: files.SHORT_HEAD,
    "recorded_rows": lambda c: recorded_rows(c.rows),
    "policy_example": lambda c: policy_example(c.rows),
    "policy_body": lambda c: policy_body(_policy_path(c)) if _policy_path(c) else "",
    "concept_maps": lambda c: "\n".join(c.maps[0]),
    "map_tail": lambda c: f" (could not read the tree: {c.maps[1]})" if c.maps[1] else "",
}
# 段落の名 → 作り手
WHEN = {
    "rejected": lambda c: bool(rolekit.rejected(c.place, c.node)),
    "excluded": lambda c: bool(c.intake.get("excluded_file")) and (c.place / files.EXCLUDED).is_file(),
    "defaults": lambda c: any(str(x).strip() for x in c.intake.get("defaults") or []),
    "purpose": lambda c: bool(str(c.intake.get("purpose") or "").strip()),
    "world": lambda c: bool(_world_rows(c)),
    "design_stands": lambda c: c.stands() == "stands",
    "design_not_stands": lambda c: c.stands() == "not_stands",
    "design_none": lambda c: c.stands() == "none",
    "design_diff": lambda c: c.stands() == "stands" and c.later(),
    "map_items": lambda c: c.stands() == "stands" and not c.intake.get("tree"),
    "fields": lambda c: c.intake.get("form") == "replan" or (c.intake.get("form") == "plan" and not c.later()
                                                             and planmarks.frozen(c.b) is not None),
    "later": lambda c: c.later(),
    "replan": lambda c: c.intake.get("form") == "replan",
    "recorded_none": lambda c: not _named_rows(c.rows),
    "policy_example": lambda c: bool(policy_example(c.rows)),
    "doc_row": lambda c: _doc_row(c.rows),
    "policy": lambda c: bool(_policy_path(c)),
    "maps_found": lambda c: bool(c.maps[0]),
    "spawns": lambda c: c.spawns,
    "framing": lambda c: bool(_framing(c)),
}


def _fragment_text(name: str) -> str:
    """名指した断片の字を prompt.py と同じ決まりで広げた物（中の断片も差し込む）"""
    kind, _, short = name.partition(":")
    if kind == "node":
        path = BLOCK / "prompts" / f"{short}.md"
        return prompt._expand(prompt._read(path, "指示の md"), BLOCK, (), False)
    if kind not in ("part", "shared"):
        raise KeyError(f"断片の名 {name!r} の頭が part・shared・node のどれでもない")
    return prompt._expand(f"{{{kind}:{short}}}", BLOCK, (), False)


def names_of(fragments) -> tuple[set, set]:
    """名指した断片の差し込み口の名と段落の名（prompt._compose と同じく {{ }} を字として外して数える）"""
    slots, marks = set(), set()
    for name in fragments:
        text = _fragment_text(name).replace("{{", prompt.OPEN).replace("}}", prompt.CLOSE)
        slots |= set(prompt.SLOT.findall(text))
        marks |= {m.group(2) for line in text.split("\n") if (m := prompt.MARK.match(line.strip()))}
    return slots, marks


def fragment_values(fragments, place, intake: dict, repo, *, b=None, material=None, spawns: bool = False) -> tuple[dict, dict]:
    """名指した断片の差し込み口の値と段落の真偽を、SLOTS・WHEN の作り手で埋めた (values, when)。呼び手は自分の md だけの差し込み口と
    合わせて prompt.emit に渡す。知らない名は KeyError（名を挙げる）。material は材料のファイルのパス（{material_file}）、spawns は
    外への検索の決まりの段落 spawns（Agent を持つ役だけ真）"""
    slots, marks = names_of(fragments)
    unknown = sorted(n for n in slots if n not in SLOTS) + sorted(n for n in marks if n not in WHEN)
    if unknown:
        raise KeyError(f"作り手の無い差し込み口・段落の名: {unknown}")
    c = _Ctx(place, intake, repo, b=b, material=material, spawns=spawns)
    return {n: SLOTS[n](c) for n in sorted(slots)}, {n: bool(WHEN[n](c)) for n in sorted(marks)}


def brief_extra(place, b, intake: dict, repo, values: dict, when: dict, *, part: str = "item-brief") -> tuple[dict, dict]:
    """木の下請けの指示（prompts/parts/<part>.md）の差し込み口と段落のうち、呼び手（src/tree.py）がまだ埋めていない名を SLOTS・WHEN の
    作り手で足した (values, when)。呼び手の値が先に勝つ。作り手の無い名は足さない（呼び手が埋める。埋め残しは prompt が名を挙げて落ちる）"""
    slots, marks = names_of([f"part:{part}"])
    c = _Ctx(place, intake, repo, b=b)
    return ({**{n: SLOTS[n](c) for n in sorted(slots) if n not in values and n in SLOTS}, **values},
            {**{n: bool(WHEN[n](c)) for n in sorted(marks) if n not in when and n in WHEN}, **when})


# ---------------------------------------------------------------- 材料のファイル
def material_text(place: pathlib.Path, intake: dict, repo, b) -> str:
    """材料のファイルの字（2 節の 1〜11 の順。指示の文を持たない）"""
    form = intake.get("form")
    later = _later(b, intake)
    tree = bool(intake.get("tree"))
    parts = [_defaults_line(intake)]
    if intake.get("excluded_file") and (place / files.EXCLUDED).is_file():
        parts.append(f"{MAT_HEADS['excluded']}\n\n{place / files.EXCLUDED}")
    parts.append(lib_section(b, pathlib.Path(repo), ports.shared_cache()))
    parts.append(design_only(b, intake))
    if form == "plan" and not later:
        parts += [deviations_section(b, place), fields_section(b)]
    else:
        planmarks.frozen(b)   # 2 往復目からと形 replan も、凍結の印と食い違う欄の控えは審査に見せない（FieldsBroken）
    if not tree:
        items = _map_items(b, intake)
        parts.append(map_items_section(b, items, MAP_OTHERS.get(form, MAP_OTHERS["plan"]), carried=_counts_coverage(intake),
                                       kept=kept_keys(b, items) if later else ()))
    if later:
        parts.append(previous_passes(b))
    if form == "replan":
        parts.append("\n\n".join([MAT_HEADS["replan"], *(_replan_section(r) for r in intake.get("replan_items") or [])]))
    machine = [MAT_HEADS["machine"]]
    machine.append(rereview_part(b, place) if later
                   else LABELS["plan"] + " " + json.dumps(_shown_plan(intake), ensure_ascii=False, indent=1))
    machine.append(f"{LABELS['units']} {_units_text(b)}")
    diag = b.record["process"].get("diagnosis") or {}
    machine.append(f"{LABELS['view']} {json.dumps(diag, ensure_ascii=False)}")
    if b.record["process"].get("precedents"):
        machine.append(f"{LABELS['precedents']} {json.dumps(b.record['process']['precedents'], ensure_ascii=False)}")
    machine.append(repository_line(repo, intake))
    parts.append("\n\n".join(machine))
    return "\n\n".join(x for x in parts if x).rstrip("\n") + "\n"


def write_material(place, intake: dict, repo, *, n: int, b=None) -> tuple[pathlib.Path, dict, dict]:
    """材料のファイル review-material-<n>.md を書き、prompts/review.md の差し込み口の値と段落の真偽を返す（2 節・3.3）。欄の控えが凍結の
    印と食い違えば planmarks.FieldsBroken（呼び手の review_prep が crash.json に訳を残して落ちる）"""
    place = pathlib.Path(place)
    if b is None:
        b = view.view(place, intake)
    path = place / files.MATERIAL.format(n=n)
    path.write_text(material_text(place, intake, repo, b), encoding="utf-8")
    values, when = fragment_values(["node:review"], place, intake, repo, b=b, material=path, spawns=True)
    return path, values, when


def heads_named(text: str) -> list[str]:
    """字の中の材料の見出しの札（試験と md の照らし）"""
    return [h for h in MAT_HEADS.values() if re.search(rf"^{re.escape(h)}$", text, re.M)]
