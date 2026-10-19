"""事前審査の木の部品（docs/design/plan-review.md の 5 節と 1.5。今の lib/planblk.py の木の部分〔:465-1030〕の写し）。

木の往復では、束ね役（node review-tree）が案の項目を自分で見ずに、開いた項目ごとの下請けと（開いた項目の全部が clean なら）相乗りの
下請けを Agent の道具で並べて起こす。下請けは指示のファイル items/brief.md（全部の項目で同じバイト。prompts/parts/item-brief.md から
prompt.render_part で組む）と、自分の項目の材料のファイル items/item-<n>.md（指示の文を持たない）を Read で読み、答えを
answers/item-<n>.json に Write で書く。相乗りの下請けは items/synergy.md（頭は prompts/parts/synergy-brief.md、後ろは全部の項目の
材料）を読み、answers/synergy.json に書く。受け付け（tree_merge）がそのファイルを項目ごとに確かめ（check_item）、faces・shrink・
resolved・当たりの答え・相乗り・出自の申告を審査の返答にまとめる。束ね役の返答は項目ごとの判定の要約（converge.ITEMS）だけ。

確かめを通らない項目は、次の支度（write_tree）がその項目の材料のファイルにだけ機械の読める誤りの一覧を載せて起こし直させ、
通った項目は済んだ下請けに並べて起こし直させない。

- write_tree(place, b, intake, material_path, n) -> (values, when): items/ と answers/ を書き、prompts/review-tree.md の値と when を返す
- tree_merge(b, bare, tree, resolved) -> {review, resolved, synergy, hits, refs, origins, files, gaps, precedents}
- check_item・item_answer_gaps・item_schema・synergy_schema・precedent_plan・save_precedents・carried_hits・answer_file・synergy_file
"""
from __future__ import annotations

import copy
import json
import pathlib

import prompt

import converge    # lib/
import design      # lib/。refs_of
import jsonfile    # lib/
import oneline     # lib/
import policy      # lib/。RECORDED_KEY
from engine.schema import validate_schema   # lib/graphloops/engine/schema.py

from src import files, material, take

SURPLUS_OP = "plan_review_surplus"
# 下請けの型は 1 つ（答えのファイルを Write で書ける型。読むだけの Explore は Write を持たない。run 68f35d6b は往復 1 が
# general-purpose・往復 2・3 が Explore で、型ごとに道具と深さが違った）
SUBAGENT_TYPE = "general-purpose"
PRECEDENT_VERDICTS = ("adopt", "adapt")
NO_RIPPLE = "波及の一覧のノードがこの往復の一覧を置いていない"
BRIEF = "item-brief"           # 下請けの指示の断片の名（prompts/parts/item-brief.md）
SYNERGY_BRIEF = "synergy-brief"
# 項目の材料のファイルの見出しと札（英語の短い札。指示の文は持たない。prompts/parts/item-brief.md がこの見出しを名指す）
ITEM_HEADS = {
    "item": "## This sub-agent's item: item {n}",
    "answer": "Answer file: {path}",
    "units": "### Units of item {n} (judgment)",
    "precedents": "### Precedent sources of this item",
    "carried": "### Hits answered in a previous pass",
    "history": "### Previous passes' owed holes of this item",
    "errors": "### Errors in the previous answer",
    "synergy": "## This sub-agent's review: synergy",
    "all_items": "### All items (closed items too)",
    "overlaps": "### Overlaps between items",
}
# 先行例の出典の行の札（下請けの指示が読み方を 1 度書く）
PRECEDENT_LABELS = {"fetch": "fetch", "cached": "cached", "other": "by item {m}"}
NONE_LABEL = "none"


# ---------------------------------------------------------------- 置き場
def answers_dir(b) -> pathlib.Path:
    return pathlib.Path(b.dir) / files.ANSWERS_DIR


def answer_file(b, n: int) -> pathlib.Path:
    return pathlib.Path(b.dir) / files.ITEM_ANSWER.format(n=n)


def synergy_file(b) -> pathlib.Path:
    return pathlib.Path(b.dir) / files.SYNERGY_ANSWER


def _ripple_of(b):
    """今の往復の項目ごとの波及の一覧（無い・読めなければ None）"""
    got = jsonfile.read_or(pathlib.Path(b.dir) / files.RIPPLE)
    return got if isinstance(got, dict) else None


uncovered = material.uncovered   # 今の ripple.uncovered の写し（src/material.py）


# ---------------------------------------------------------------- 型
def _faces_schema(b) -> tuple[dict, dict]:
    props = b.faces_schema
    return copy.deepcopy(props["faces"]), copy.deepcopy(props["shrink"])


def item_schema(b) -> dict:
    """項目の下請けの答えのファイルの型（faces・shrink は事前審査の役の型の物。precedents は開けと言われた先行例の出典の確かめ）"""
    faces, shrink = _faces_schema(b)
    return {"type": "object", "additionalProperties": False,
            "required": ["item", "checked", "hits", "faces", "shrink", "resolved"],
            "properties": {"item": {"type": "integer", "minimum": 1}, "checked": {"type": "string", "minLength": 10},
                           "hits": copy.deepcopy(converge.HITS_SCHEMA), "faces": faces, "shrink": shrink,
                           "resolved": {"type": "array", "items": {"type": "string"}},
                           converge.DESIGN_MAP: copy.deepcopy(converge.DESIGN_MAP_SCHEMA),
                           converge.ORIGINS: copy.deepcopy(converge.ORIGIN_SCHEMA),
                           "precedents": {"type": "array", "items": {
                               "type": "object", "additionalProperties": False, "required": ["id", "found", "quote"],
                               "properties": {"id": {"type": "string"}, "found": {"type": "boolean"},
                                              "quote": {"type": "string", "minLength": 10}}}}}}


def synergy_schema(b) -> dict:
    """相乗りの審査の下請けの答えのファイルの型"""
    faces, _ = _faces_schema(b)
    return {"type": "object", "additionalProperties": False, "required": ["why", "faces"],
            "properties": {"why": {"type": "string", "minLength": 10}, "faces": faces,
                           converge.ORIGINS: copy.deepcopy(converge.ORIGIN_SCHEMA)}}


def _load(path: pathlib.Path, schema: dict) -> tuple:
    """(答え, 誤りの行)。読めない・型に合わない時は誤りの行（型の誤りは engine の validate_schema の $ から始まる行）"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, [f"JSON として読めない（{oneline.one_line(e)}）"]
    errs = validate_schema(doc, schema)
    return (None, errs) if errs else (doc, [])


# ---------------------------------------------------------------- 先行例の出典（run の中で 1 度だけ開く）
def precedent_checks(b) -> dict:
    """控えた先行例の出典の確かめ {出典: {found, quote, round, pass, item}}（無い・読めなければ {}。入口が port prior の
    precedent_checks から置き、受け付けが足す）"""
    doc = jsonfile.read_or(pathlib.Path(b.dir) / files.PRECEDENT_CHECKS)
    return doc if isinstance(doc, dict) else {}


def precedent_plan(b, opened: list) -> dict:
    """開いた項目ごとの先行例の出典の行 {項目: [{id, row, cached | None, fetch_by}]}。id は判定の先行例の並びの P<i>。控えの無い
    出典は、それを持つ開いた項目のうち一番小さい番号の項目の下請けが開く（fetch_by）"""
    plan = converge.read(b).get("plan") or []
    rows = (b.record.get("process") or {}).get("precedents") or []
    cache = precedent_checks(b)
    owner: dict = {}
    out: dict = {}
    for n in opened:
        mine = converge.item_units(plan, n)
        for i, r in enumerate(rows, 1):
            if not isinstance(r, dict) or r.get("key") not in mine or r.get("verdict") not in PRECEDENT_VERDICTS:
                continue
            src = str(r.get("source") or "")
            hit = cache.get(src)
            if hit is None:
                owner.setdefault(src, n)
            out.setdefault(n, []).append({"id": f"P{i}", "row": r, "cached": hit, "fetch_by": owner.get(src)})
    return out


def _precedent_part(rows: list, n: int) -> str:
    """項目の材料の先行例の出典の行（札 fetch・cached・by item <m> の読み方は下請けの指示に在る）"""
    if not rows:
        return ""
    lines = [ITEM_HEADS["precedents"], ""]
    for x in rows:
        r = x["row"]
        what = f"{x['id']}: {r.get('source')}（verdict {r.get('verdict')}・unit {r.get('key')}・judge's reason {r.get('reason')}）"
        if x["cached"] is not None:
            c = x["cached"]
            lines.append(f"- {what} — {PRECEDENT_LABELS['cached']}: found={str(c.get('found')).lower()}・{c.get('quote')}")
        elif x["fetch_by"] == n:
            lines.append(f"- {what} — {PRECEDENT_LABELS['fetch']}")
        else:
            lines.append(f"- {what} — {PRECEDENT_LABELS['other'].format(m=x['fetch_by'])}")
    return "\n".join(lines)


def _precedent_wanted(rows: list, n: int) -> list:
    return [x["id"] for x in rows if x["cached"] is None and x["fetch_by"] == n]


def _precedent_gaps(rows: list, n: int, got: dict) -> list[str]:
    ids = [r.get("id") for r in got.get("precedents") or []]
    return [f"$.precedents: 先行例の出典 {i} の確かめの行が無い（WebFetch で 1 度開いて {{id, found, quote}} を書け）"
            for i in _precedent_wanted(rows, n) if i not in ids]


def _surplus(b, n: int, got: dict, rip: dict, pre_rows: list) -> dict:
    """型の合った項目 n の答えの余りの行の id {precedents, hits}: この項目の下請けが開く出典でない precedents の行・波及の一覧の
    項目 n の覆っていない当たりに無い hits の行。拒まずに捨てる（check_item が取り除く）"""
    want_p = _precedent_wanted(pre_rows, n)
    want_h = [h["id"] for h in uncovered(rip, n)]
    return {"precedents": [r.get("id") for r in got.get("precedents") or [] if r.get("id") not in want_p],
            "hits": [h.get("id") for h in got["hits"] if h.get("id") not in want_h]}


def save_precedents(b, plan_rows: dict, answers: dict, k: int) -> dict:
    """受けた答えの先行例の出典の確かめを控えに足す（控えに在る出典は書き換えない）。返りは足した後の控え（pass.json に載る）"""
    cache = precedent_checks(b)
    for n, got in answers.items():
        by_id = {x["id"]: x["row"] for x in plan_rows.get(n) or []}
        for r in got.get("precedents") or []:
            src = str((by_id.get(r.get("id")) or {}).get("source") or "")
            if src and src not in cache:
                cache[src] = {"found": r.get("found"), "quote": r.get("quote"), "round": b.round, "pass": k, "item": n}
    jsonfile.write(pathlib.Path(b.dir) / files.PRECEDENT_CHECKS, cache, indent=2)
    return cache


# ---------------------------------------------------------------- 当たりの答え
def carried_hits(b, n: int, rip: dict) -> dict:
    """項目 n の今の往復の覆っていない当たりのうち、前の往復で同じ当たり（種類・場所・名が同じ）に block でない答えが在る物
    {当たりの id: 引き継ぐ答えの行（carried に答えた往復）}"""
    prev = {}
    for h in converge.answered_hits(b, n):
        key = (h.get("kind"), h.get("at"), h.get("name"))
        if key not in prev and h.get("answer") in converge.HIT_ANSWERS:
            prev[key] = h
    out = {}
    for h in uncovered(rip, n):
        old = prev.get((h["kind"], h["at"], h["name"]))
        if old is not None and old["answer"] != "block":
            out[h["id"]] = {"id": h["id"], "answer": old["answer"], "why": old.get("why", ""), "kind": h["kind"],
                            "at": h["at"], "name": h["name"], "carried": old.get("carried") or old["pass"]}
    return out


def _hit_rows(b, n: int, rip: dict, answered: list) -> list:
    """往復の記録に置く項目 n の当たりの答え（下請けの答えに当たりの種類・場所・名を足し、答えの無い当たりは引き継いだ答え）"""
    where = {h["id"]: {"kind": h["kind"], "at": h["at"], "name": h["name"]} for h in uncovered(rip, n)}
    got = {h["id"]: {**h, **where.get(h["id"], {})} for h in answered}
    carried = carried_hits(b, n, rip)
    return [got.get(i) or carried[i] for i in where if i in got or i in carried]


# ---------------------------------------------------------------- 項目ごとの確かめ
def _recorded_rows(b) -> list:
    return (b.record.get("process") or {}).get(policy.RECORDED_KEY) or []


def item_answer_gaps(b, n: int, got: dict, rip: dict) -> list[str]:
    """型の合った項目 n の答えの中身の誤り: 覆っていない当たり（前の往復の答えを引き継ぐ物 carried_hits は除く）の全部に
    ちょうど 1 つの答え・block と答えた当たりには block の face・face は項目 n の単位だけを名指す・前の往復の答えの要る穴
    （求める側 converge.item_blocks。block と開いた項目の suggest）は resolved か同じ key の face・resolved に書いてよい側は
    converge.resolvable_keys（拒否の行は converge.stray_resolved）・穴の行ごとの照らし（take.face_row_gaps。誤りは『$.faces[j]（key）: …』で、
    tree_merge が項目 n の答えのファイルを名指す行に載せる）・独立設計の引用と design_map"""
    errs = [] if got.get("item") == n else [f"$.item: {n} でない（{got.get('item')!r}）"]
    want = [h["id"] for h in uncovered(rip, n)]
    carried = carried_hits(b, n, rip)
    ids = [h.get("id") for h in got["hits"]]
    errs += [f"$.hits: 覆っていない当たり {h} への答えが無い" for h in want if h not in ids and h not in carried]
    errs += [f"$.hits: {h} に答えが {ids.count(h)} つある（1 つだけ）" for h in sorted(set(ids)) if ids.count(h) > 1]
    blocks = converge.block_faces(got)
    if any(h.get("answer") == "block" for h in got["hits"]) and not blocks:
        errs.append("$.faces: 当たりに block と答えたのに severity block の face が無い")
    plan = converge.read(b).get("plan") or []
    mine = converge.item_units(plan, n)
    names = take._names(b)
    for i, f in enumerate(got["faces"]):
        out = [str(k) for k in f["unit_keys"] if take.unit_name(names, k) not in mine]
        if out:
            errs.append(f"$.faces[{i}].unit_keys: 項目 {n} の単位でない {out}（項目どうしの穴は相乗りの審査が挙げる。"
                        "unit_keys は項目の unit_keys を字のまま）")
    prev = converge.item_blocks(b, n)
    keys = {f["key"] for f in got["faces"]}
    block_keys = {f["key"] for f in blocks}
    errs += [f"$.resolved: 前の穴 {k} を resolved に入れるか、同じ key で faces に挙げ直せ"
             for k in prev if k not in got["resolved"] and k not in keys]
    errs += [f"$.resolved: {line}" for line in converge.stray_resolved(converge.read(b), got["resolved"], n)]
    errs += [f"$.resolved: {k} が resolved と block の face の両方に在る（消えたか残ったかのどちらか 1 つ）"
             for k in got["resolved"] if k in block_keys]
    errs += [f"$.faces: {line}" for line in converge.relabel_gaps(converge.read(b), got["faces"])]
    errs += [f"$.{e}" for e in take.face_row_gaps(got["faces"], _recorded_rows(b))]
    return errs + [f"$.faces・design_map: {e}" for e in take.design_gaps(b, got["faces"], [n], got.get(converge.DESIGN_MAP) or [],
                                                                          take.kept_keys(b, [n]))]


def check_item(b, n: int, rip: dict, pre: list | None = None) -> tuple:
    """(通った答え | None, 誤りの行, ファイルが無いか, 捨てた余りの行 _surplus)。通った答えは余りの行を取り除いた写し。
    pre は先行例の出典の開き手を決める開いた項目の並び（precedent_plan）"""
    path = answer_file(b, n)
    dropped = {"precedents": [], "hits": []}
    if not path.is_file():
        return None, [], True, dropped
    got, errs = _load(path, item_schema(b))
    if got is not None:
        if converge.DESIGN_MAP in got:
            got = {**got, converge.DESIGN_MAP: take.bound_map(b, [n], got[converge.DESIGN_MAP])}
        rows = precedent_plan(b, [n] if pre is None else pre).get(n) or []
        dropped = _surplus(b, n, got, rip, rows)
        got = {**got, "hits": [h for h in got["hits"] if h.get("id") not in dropped["hits"]],
               **({"precedents": [r for r in got["precedents"] if r.get("id") not in dropped["precedents"]]}
                  if "precedents" in got else {})}
        errs = item_answer_gaps(b, n, got, rip) + _precedent_gaps(rows, n, got)
    return (None if errs else got), errs, False, dropped


def tree_merge(b, bare: dict, tree: dict, resolved: list) -> dict:
    """事前審査の受け付けの木のまとめ（機械）。intake の tree が真の往復（束ね役の組 review-tree／review-tree-fix の返答）だけで
    呼ばれる。束ね役の返答の外した写し bare・束ね役の欄 tree（items・推し）・束ね役の resolved から、
    {review, resolved, synergy（相乗りの審査の face の key）, hits（{項目: 当たりの答え}）, refs（{項目: 答えの対応表の design_ref の並び}）,
    origins（新しい block の出自の申告の行。下請けと相乗りの答えの物を集める）, files（往復の記録に写す答えのファイル）,
    gaps（拒む理由の行。在れば他は使わない）, precedents（save_precedents に渡す物）} を返す。faces・shrink・origins・resolved は
    下請けの答えのファイルから組み、束ね役の型はそれらを持たない（node の output_format が拒む）。開いた項目の答えのファイルが
    無ければ、その項目の下請けを起こせと拒む"""
    k = converge.pass_no(b)
    rip = _ripple_of(b) or {}
    base = {"review": bare, "resolved": resolved, "synergy": [], "hits": {}, "origins": [], "files": {}, "gaps": []}
    plan = converge.read(b)["plan"]
    opened = converge.open_items(b)
    gaps, answers = [], {}
    for n in opened:
        got, errs, missing, dropped = check_item(b, n, rip, opened)
        for field, ids in dropped.items():
            for i in ids:
                b.trace(SURPLUS_OP, round=b.round, pass_=k, item=n, field=field, id=i)
        where = f"項目 {n}（{answer_file(b, n)}）"
        if missing:
            gaps.append(f"{where}: 答えのファイルが無い（その項目の下請けを起こせ）")
        gaps += [f"{where}: {e}" for e in errs]
        if got is not None:
            answers[n] = got
    refs = {n: take.item_refs(b, n, design.refs_of(a.get(converge.DESIGN_MAP)), take.kept_keys(b, [n]), a.get(converge.DESIGN_MAP))
            for n, a in answers.items()}
    if len(answers) == len(opened):   # 独立設計の要素の網羅は、全部の項目の答えと閉じた項目の控えを合わせて数える
        gaps += [f"独立設計の要素（項目の答え {'・'.join(str(n) for n in opened)} を合わせて数えた）: {e}"
                 for e in take.coverage_gaps(b, [r for rs in refs.values() for r in rs], opened)]
    rows = tree.get(converge.ITEMS)
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    for n in opened:
        mine = [r for r in rows if r.get("item") == n]
        if len(mine) != 1:
            gaps.append(f"束ね役の items に項目 {n} の行が {len(mine)} 行ある（開いた項目ごとに 1 行）")
        elif n in answers:
            keys = [f["key"] for f in converge.block_faces(answers[n])]
            said = [x.get("key") for x in mine[0].get("blocks") or [] if isinstance(x, dict)]
            verdict = converge.VERDICTS[1] if keys else converge.VERDICTS[0]
            if mine[0].get("verdict") != verdict or sorted(map(str, said)) != sorted(keys):
                gaps.append(f"束ね役の items の項目 {n} が答えのファイルと食い違う（ファイルは {verdict}・block "
                            f"{'、'.join(keys) or '無し'}。下請けの要約のとおりに書け）")
    gaps += [f"束ね役の items の項目 {r.get('item')} は審査しない項目（閉じた・保留・案に無い）" for r in rows
             if r.get("item") not in opened]
    syn = None
    if (len(plan) >= 2 and opened and len(answers) == len(opened)
            and not any(converge.block_faces(a) for a in answers.values())):
        path = synergy_file(b)
        if not path.is_file():
            gaps.append(f"相乗りの審査（{path}）: 開いた項目の全部が clean の往復は、相乗りの審査の下請けを起こせ")
        else:
            syn, errs = _load(path, synergy_schema(b))
            gaps += [f"相乗りの審査（{path}）: {e}" for e in errs]
            if syn is not None:
                gaps += [f"相乗りの審査（{path}）: $.{e}" for e in take.face_row_gaps(syn["faces"], _recorded_rows(b))]
                gaps += [f"相乗りの審査（{path}）: {e}" for e in take.design_gaps(b, syn["faces"], list(range(1, len(plan) + 1)))]
    faces = [f for n in opened if n in answers for f in answers[n]["faces"]] + list((syn or {}).get("faces") or [])
    keys = [f["key"] for f in faces]
    gaps += [f"face の key {key} が 2 つの答えに在る（後に書いた項目の key を変えよ）" for key in sorted(set(keys))
             if keys.count(key) > 1]
    if gaps:
        return {**base, "gaps": gaps}
    now = {f["key"] for f in faces}
    # suggest は resolved に入っても後の往復の返答に残す（修正の段へ。答えと照らしは converge.owed_faces が除く）
    faces += [f for f in converge.carried_notes(b) if f.get("key") not in now]
    review = {**bare, "faces": faces, "shrink": [x for n in opened for x in answers[n]["shrink"]]}
    if not faces and not review.get("faces_none"):
        review["faces_none"] = " / ".join(f"項目 {n}: {answers[n]['checked']}" for n in opened)
    names = {n: pathlib.PurePath(files.ITEM_ANSWER.format(n=n)).name for n in opened}
    out_files = {names[n]: str(answer_file(b, n)) for n in opened}
    if syn is not None:
        out_files[pathlib.PurePath(files.SYNERGY_ANSWER).name] = str(synergy_file(b))
    return {"review": review, "resolved": list(dict.fromkeys(x for n in opened for x in answers[n]["resolved"])),
            "synergy": [f["key"] for f in (syn or {}).get("faces") or []],
            "origins": [o for x in [*(answers[n] for n in opened), syn or {}] for o in x.get(converge.ORIGINS) or []],
            "hits": {n: _hit_rows(b, n, rip, answers[n]["hits"]) for n in opened}, "files": out_files, "gaps": [],
            "refs": {n: refs[n] for n in opened}, "precedents": (precedent_plan(b, opened), answers, k)}


# ---------------------------------------------------------------- 項目の材料のファイル（指示の文を持たない）
def _item_units(b, unit_keys) -> list:
    keys = {str(k) for k in unit_keys or []}
    return [{k: u[k] for k in ("key", "label", "disposition", "reason") if k in u}
            for u in b.record.get("units") or [] if u.get("key") in keys]


def _json(doc) -> str:
    return "```json\n" + json.dumps(doc, ensure_ascii=False, indent=1) + "\n```"


def _item_history(b, unit_keys: list) -> str:
    """前の往復でこの項目に挙がった答えの要る穴（converge.owed_faces。block と開いた項目の suggest）と修正案の役の答え（1 往復目と、
    答えの要る穴の無い項目は空）。頼みの文（今の converge.REREVIEW_ASK・ORIGIN_ASK）は下請けの指示に在る"""
    doc = converge.read(b)
    if not doc["passes"]:
        return ""
    mine = {str(k) for k in unit_keys}
    lines = []
    replies = [p.get("answers", []) for p in doc["passes"][1:]] + [doc["open"].get("answers", [])]
    for p, answers in zip(doc["passes"], replies):
        owed = [f for f in converge.owed_faces(doc, p) if set(f["unit_keys"]) & mine or not f["unit_keys"]]
        lines += [f"- pass {p['pass']} {f['severity']} {f['key']}: {f.get('why')}（{f.get('where')}）" for f in owed]
        keys = {f["key"] for f in owed}
        lines += [f"  - plan role's answer {a.get('key')}: {a.get('handled')}（{a.get('how')}）" for a in answers
                  if isinstance(a, dict) and a.get("key") in keys]
    return "\n".join([ITEM_HEADS["history"], "", *lines]) if lines else ""


def _carried_part(b, n: int, rip: dict) -> str:
    rows = carried_hits(b, n, rip)
    if not rows:
        return ""
    return ITEM_HEADS["carried"] + "\n\n" + "\n".join(f"- {i}: {h['answer']}（{h['why']}）" for i, h in rows.items())


def _errors_part(n: int, path: pathlib.Path, errs: list) -> str:
    doc = {"item": n, "file": str(path), "errors": errs}
    return f"{ITEM_HEADS['errors']}\n\n{_json(doc)}"


def _item_material(b, n: int, it: dict, doc: dict, pre: list, errs: list) -> str:
    """項目 n の材料のファイルの本文: 項目の見出し・答えのファイル・案（2 往復目からは差分）・単位・design_map の鍵の一覧・
    先行例の出典の行・波及の一覧の項目の節・前の往復で答えた当たり・前の往復の答えの要る穴と修正案の役の答え・前の答えの誤り"""
    return "\n\n".join(x for x in (
        ITEM_HEADS["item"].format(n=n), ITEM_HEADS["answer"].format(path=answer_file(b, n)),
        material._item_plan_part(b, n, it),
        f"{ITEM_HEADS['units'].format(n=n)}\n\n{_json(_item_units(b, it.get('unit_keys')))}",
        material.map_items_section(b, [n], material.ITEM_MAP_OTHERS, carried=False, kept=material.kept_keys(b, [n])),
        _precedent_part(pre, n), material.ripple_section(doc, n), _carried_part(b, n, doc),
        _item_history(b, it.get("unit_keys") or []),
        _errors_part(n, answer_file(b, n), errs) if errs else "") if x) + "\n"


def _synergy_material(b, rows: list, last: dict, doc: dict) -> str:
    """相乗りの材料（全部の項目の状態と行・重なりの行）"""
    states = [f"- item {n}（{(last.get(n) or {}).get('state', converge.OPEN)}）: {json.dumps(it, ensure_ascii=False)}"
              for n, it in enumerate(rows, 1)]
    over = "\n".join(f"- {o['at']}: item {', '.join(map(str, o['items']))}" for o in doc.get("overlaps") or []) or f"- {NONE_LABEL}"
    return "\n\n".join([ITEM_HEADS["synergy"], ITEM_HEADS["all_items"] + "\n\n" + "\n".join(states),
                        ITEM_HEADS["overlaps"] + "\n\n" + over]) + "\n"


# ---------------------------------------------------------------- 支度
def _fill(fragment: str, place, intake: dict, repo, b, own: dict, own_when: dict, material_path=None) -> tuple[dict, dict]:
    """md（"node:<id>" か "part:<名>"）の差し込み口と段落の名の全部の値と真偽: この木の口（own・own_when）はここで、ほかは
    src/material.py の作り手（SLOTS・WHEN。名ごとに 1 つの作り手）で埋める。作り手の無い名は KeyError（名を挙げる）"""
    slots, marks = material.names_of([fragment])
    c = material._Ctx(place, intake, repo, b=b, material=material_path, spawns=False)
    unknown = sorted(n for n in slots if n not in own and n not in material.SLOTS) + \
        sorted(n for n in marks if n not in own_when and n not in material.WHEN)
    if unknown:
        raise KeyError(f"{fragment} の作り手の無い差し込み口・段落の名: {unknown}")
    values = {n: own[n] if n in own else material.SLOTS[n](c) for n in sorted(slots)}
    when = {n: bool(own_when[n]) if n in own_when else bool(material.WHEN[n](c)) for n in sorted(marks)}
    return values, when


def brief_text(place, b, intake: dict, repo) -> str:
    """下請けの指示（prompts/parts/item-brief.md。全部の項目と相乗りで同じバイト）"""
    framing = material.SLOTS["framing"](material._Ctx(place, intake, repo, b=b))
    values, when = _fill("part:" + BRIEF, place, intake, repo, b, {"item_schema": json.dumps(item_schema(b), ensure_ascii=False)},
                         {"spawns": False, "framing": bool(framing)})
    return prompt.render_part("item-brief", values, when)


def write_tree(place, b, intake: dict, material_path, n: int, repo=None) -> tuple[dict, dict]:
    """木の往復の支度: items/brief.md（下請けの指示）・items/item-<m>.md（開いた項目ごとの材料。済んだ項目は書かない）・
    items/synergy.md（項目が 2 つ以上。下請けの指示と相乗りの頼みと全部の項目の材料）を書き、answers/ を作り、prompts/review-tree.md の
    値と when を返す。n は輪の何回目か（材料のファイルの名と同じ。値には入らない）。項目の控えが無ければ ValueError"""
    place = pathlib.Path(place)
    repo = pathlib.Path(repo or intake.get("cwd") or ".")
    rows = material._item_rows(b)
    if not rows:
        raise ValueError("木の往復なのに修正案の項目が無い")
    doc = _ripple_of(b) or {"items": [], "overlaps": [], "error": NO_RIPPLE}
    folder = place / files.ITEMS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    answers_dir(b).mkdir(parents=True, exist_ok=True)
    plan = converge.read(b).get("plan")
    opened = material._opened(b, rows)
    pre = precedent_plan(b, opened) if plan else {}
    head = brief_text(place, b, intake, repo)
    brief = place / files.BRIEF
    brief.write_text(head, encoding="utf-8")
    done, todo, retry = [], [], False
    for m in opened:
        path = place / files.ITEM.format(n=m)
        got, errs, missing, _ = check_item(b, m, doc, opened) if plan else (None, [], True, {})
        if got is not None:
            done.append(f"- item {m}: {path}")
            continue
        retry = retry or not missing
        path.write_text(_item_material(b, m, rows[m - 1], doc, pre.get(m) or [], errs), encoding="utf-8")
        todo.append(f"- item {m}: {path}")
    passes = converge.read(b)["passes"]
    last = {it["n"]: it for it in (passes[-1].get("items") or [])} if passes else {}
    rest = [f"- item {m}（{last[m]['state']}）" for m in range(1, len(rows) + 1) if m not in opened and m in last]
    synergy = place / files.SYNERGY_ITEM
    if len(rows) >= 2:
        sv, sw = _fill("part:" + SYNERGY_BRIEF, place, intake, repo, b,
                       {"synergy_schema": json.dumps(synergy_schema(b), ensure_ascii=False), "answer_file": str(synergy_file(b))}, {})
        synergy.write_text(head + "\n" + prompt.render_part("synergy-brief", sv, sw) + "\n" + _synergy_material(b, rows, last, doc),
                           encoding="utf-8")
    else:
        synergy.unlink(missing_ok=True)
    again = bool(done or retry)
    return _fill("node:review-tree", place, intake, repo, b, {
        "subagent_type": SUBAGENT_TYPE, "brief_file": str(brief), "done_items": "\n".join(done), "todo_items": "\n".join(todo),
        "rest_items": "\n".join(rest), "synergy_file": str(synergy), "clean": converge.VERDICTS[0], "block": converge.VERDICTS[1]},
        {"spawns": False, "done_items": bool(done), "redo": bool(todo) and again, "fresh": bool(todo) and not again,
         "rest": bool(rest), "synergy": len(rows) >= 2}, material_path=material_path)
