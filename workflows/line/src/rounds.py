"""計画の往復の記録と止め（docs/design/line.md の 3 節。形の直し 6: 往復の記録と止め時は line が持つ）。

往復の記録 plan-converge.json（src.files.PLAN_CONVERGE）の形は今の lib/converge.py の控えのまま
（{round, passes, outcome, plan?, precedent_checks?}。往復の行の形は converge の docstring）。plan-review は前の往復までの記録を
port prior（PRIOR_SHAPE）で受け、1 往復分の材料を pass.json（plan-review の設計書の 9.3）で返す。line はそれを add_pass で記録に足す。

写した物（元 lib/converge.py。名は元のまま。往復の記録と止め時の部分。盤面 b を受けていた口は、記録の dict と place のパスを
受ける形にした）: decide・proceeds・add_pass（と _item_states・_origins・_quoted・_attributed）・held・capped・stuck_keys・uncited・
stuck_faces・stuck_reason・lines・open_items と、文の定数（PERSISTED_WHY・UNSETTLED_WHY・CAP_WHY・LINE_*・WORDS・ITEMS_WHY）。
止まった案を推しで越えてよいかの決め stuck_pushable（元 lib/gatepolicy.py。無人の run の印を引数で受ける形）も持つ。
読み口（block_faces・central・central_keys・sentences・sentence_diff・plan_rows・planned_units と語の定数）は KEEP の lib/converge を
import する（plan と plan-review も使う。README 9.3）。

- fresh() / read(raw) / write(path, doc): 記録の読み書き（raw は pointer かパスか空。読めない・形が違えば往復の無い記録）
- record_pass(doc, got, *, at_cap, dest, plan_rejects): pass.json の中身 got を往復の行として足し、files を dest へ写し、拒否の行を積む
- stuck_push_due(doc, *, unattended, design_talk): 止まった案を推しで修正へ進めるか（今の gatemarks.stuck_push の条件）
- ask_again(doc, *, key, text): 設計の相談の承認ノードで人が設計し直しを求めた時、その求めを最後の往復の中央の block に差し込み、全部の項目を
  開き直して抜け方を AGAIN にする（次の周の plan が答え、事前審査が消えたか残ったかを照らす。src/talk.py が呼ぶ）
- LIMIT: 往復の安全の上限（YAML の plan-rounds の max_iterations と同じ数。試験が突き合わせる）
- suspicion(passes) / suspected(doc): 往復が長引いた・審査の穴の中身が移ったと見る印（issue #838。打ち切りでなく、人に聞く合図。
  add_pass が AGAIN の往復を止まりに替え、行に suspect を置く。対話モードは設計の相談で、ほかの run は修正前の承認ノードで人に聞き、
  無人の run は推しで越えずに止まる）
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
import shutil

import cite
from converge import (AGAIN, CLEAN, CLOSED, FACE_KEYS, HELD, HELD_MARK, KEY_CHAR, OPEN, ORIGIN_INTRODUCED, ORIGIN_MISSED,
                      ORIGIN_REPHRASED, ORIGIN_UNSPLIT, ORIGIN_WORDS, PERIPHERAL, PERSISTED, QUOTE, REACH, SETTLED, STUCK, UNSETTLED,
                      block_faces, central, central_keys, sentence_diff, sentences)

LIMIT = 20
# 怪しいと見る往復の数（issue #838・持ち主の言葉「3回往復すれば怪しいとみる」）。人の答えの後（無ければ往復の頭）から数えて、閉じない
# まま回した往復がこの数に届いたら、次の往復を始める前に人に聞く（対話モード）か止まる（無人の run）。打ち切りの上限ではない: 人が
# 設計し直しを求めれば数え直して往復を続ける（docs/design/line.md の 3.2 節。憲法 6 との関係もそこ）
SUSPECT_ROUNDS = 3
SUSPECT_LONG = "long"     # 印の語: 閉じないまま SUSPECT_ROUNDS 往復を回した
SUSPECT_DRIFT = "drift"   # 印の語: 審査の穴の中身が移った（前の往復の中央の block が全部消え、新しい中央の block が全部、直しが持ち込んだ物）
SUSPECT_WHY = {SUSPECT_LONG: "人の答えの後（無ければ往復の頭）から {n} 往復しても閉じない",
               SUSPECT_DRIFT: "審査の穴の中身が移った（前の往復の中央の block {gone} が全部消え、この往復の新しい中央の block {came} が全部、"
                              "直しが持ち込んだ物）"}
SUSPECT_HEAD = ("怪しいと見て往復を止めた（打ち切りでなく人に聞く合図。人が設計し直しを求めれば数え直して往復を続ける）: {why}")
PLAN_ROLE = "plan"   # 修正案の役の拒否の行の role（元 lib/planfile.py の ROLE）

PERSISTED_WHY = ("事前審査（記録の名 p2.plan_review）の同じ block が、案を直した後も残った（{keys}。壁打ち {n} 往復。"
                 "往復ごとの案と審査: {path}）")
UNSETTLED_WHY = ("事前審査（記録の名 p2.plan_review）の block が、壁打ち {n} 往復でも消えない（往復ごとに別の穴が出た。"
                 "最後の block: {keys}。往復ごとの案と審査: {path}）")
CAP_WHY = ("壁打ちのループの安全の上限 {n} 往復に届いた（中央の新しい穴が出続ける往復は普通は届かないので、工場の不具合として"
           "止めた）。往復ごとの開いた数: {counts}")
LINE_HEAD = ("事前審査の壁打ち: {n} 往復・抜け方は{word}（記録の名 {outcome}）・続いた block: {persists}・{share}"
             "（往復ごとの案と審査: {path}）")
# 1 回目の割合の分母に言い換えを入れないのは、言い換えが 1 回目の block の言い直しで新しい穴でないから。持ち込みを 1 回目の割合の
# 分母に入れないのは、直しが後で作った穴が 1 回目の見つける力を下げて見せるから（止めた全部のうちの割合には入れる）
LINE_SHARE = ("1 回目の block {first} 件・後の回の新しい block: 見落とし {missed}・持ち込み {introduced}・言い換え {rephrased}・"
              "分けられない {unsplit}。1 回目に出た割合は {share}（後の回が審査した所の見落としだけを数えるので、閉じた項目の取りこぼしは"
              "数えない上限。run の後で見つかった穴は割合に入らない）、止めた全部のうちでは {total}")
LINE_NO_BLOCK = "止めた block なし"
LINE_PASS = ("  - {k} 往復目: block {keys}・答えの要る穴（block と suggest）への答え fixed {f} 件・disputed {d} 件・審査が消えたと言った key {resolved}"
             "・審査が suggest か peripheral に下げた key {down}")
ITEMS_WHY = "固まった項目: {closed}。保留の項目: {held}。開いたままの項目: {open}"
LINE_DISPUTED = "    退けた答え {key}: {how}"
LINE_ITEMS = "    項目: 閉じた {closed}・開いた {open}・保留 {held}・相乗りの審査の block {synergy}"
WORDS = {CLEAN: "block が消えた", SETTLED: "中央の穴が無くなった（端の block を申し送った）", PERSISTED: "同じ block が続いた",
         UNSETTLED: "開いた block が残ったまま止めた", AGAIN: "途中"}
NONE = "無い"


def _faces(review) -> list[dict]:
    """審査の返答の face の行（返答が dict でない・faces が list でない・行が dict でない物は読まない）"""
    faces = review.get("faces") if isinstance(review, dict) else None
    return [f for f in faces if isinstance(f, dict)] if isinstance(faces, list) else []


def decide(passes: list[dict]) -> str:
    """往復の止め時の決まりの正本。最後の往復の block が無ければ CLEAN。最後の往復の中央の block（central_keys）が前のどれかの
    往復の block と重なれば PERSISTED。2 往復目から、最後の往復の開いた block に中央が無ければ SETTLED（端の block は直しへ進めない
    穴でなく、review.json の faces に載ったまま修正の段へ申し送る。1 往復目の端の block は一度は修正案の役に返して答えさせる）。
    ほかは往復の数と block の数に依らず AGAIN（中央の新しい block が出続ける間は続ける）。
    最後の行に items が在れば項目ごと（_decide_items）: 開いた項目が無ければ、保留の項目が在れば PERSISTED・無ければ CLEAN。
    2 往復目から開いた項目の block に中央が無ければ、保留の項目が在れば PERSISTED・無ければ SETTLED。ほかは AGAIN（保留の項目は
    中央の block が続いた項目だけ。_item_states）。
    輪が回せる往復の静的な上限は決まりに入れない（add_pass の at_cap が、AGAIN の往復をその周で止める）。
    止め時が数えるのは block だけ: 開いた項目の suggest（答えは要る。owed_faces）に disputed と答え、審査が suggest のまま挙げ直しても、
    block が無ければ CLEAN（残った suggest は carried_notes が修正の段へ運ぶ）"""
    last = passes[-1]
    if last.get("items") is not None:
        return _decide_items(passes)
    if not last["blocks"]:
        return CLEAN
    hard = set(central_keys(passes, last["blocks"]))
    if any(hard & set(p["blocks"]) for p in passes[:-1]):
        return PERSISTED
    return SETTLED if len(passes) >= 2 and not hard else AGAIN


def proceeds(outcome) -> bool:
    """抜け方の語 outcome で案が直しへ進むか（CLEAN と SETTLED）。事前審査の通否（boardview.verdict）はこれだけを読む"""
    return outcome in (CLEAN, SETTLED)


def _decide_items(passes: list[dict]) -> str:
    states = [it.get("state") for it in passes[-1]["items"]]
    if OPEN not in states:
        return PERSISTED if HELD in states else CLEAN
    if len(passes) >= 2 and not central_keys(passes, _open_blocks(passes[-1])):
        return PERSISTED if HELD in states else SETTLED
    return AGAIN


def _label(it: dict) -> str:
    return f"項目 {it['n']}（{'、'.join(str(k) for k in it.get('unit_keys') or [])}）"


def _attributed(units: list, items: list) -> list[int]:
    """face の unit_keys が重なる項目の位置（どの項目とも重ならなければ全部）"""
    hit = [i for i, it in enumerate(items) if set(units) & set(it["unit_keys"])]
    return hit or list(range(len(items)))


def _origins(new: list, claimed: list, *, rows: list, prev: list, face_units: dict, earlier: set, earlier_units: dict,
             resolved: list) -> tuple[dict, list]:
    """（新しい block の key ごとの出自の語, 採らなかった申告の行）。mine＝face の単位が重なる項目（重ならなければ全部の項目）。
    項目が変わったかは項目の行の hash で決める（前の往復に無い項目も変わった物に数える）。
    既定: mine の項目の id が全部前の往復の案に無ければ introduced・mine の項目の hash が全部前と同じなら missed。ほかは、変わった
    mine の項目の中の文で照らす（_quoted）: 申告の引用 quote（QUOTE。穴が指す案の文の字のまま）が、残った文（sentence_diff。
    hash の同じ mine の項目の文も残った文）だけに当たれば missed、足した文だけに当たれば introduced、ほか（2 つ以上に当たる・消した
    文に当たる・どれにも当たらない・引用が無いか QUOTE_MIN 字より短い・変わった項目のどれかの文の組が前と同じで変化が並びだけ）は
    unsplit。
    申告: introduced は今の往復でどれかの項目の行が変わった時に採る（引用は見ない。ほかの項目の行が変わって mine の項目に穴が
    できる、項目どうしの関わりの持ち込みを含む）。rephrased は of が前の往復の block で今の往復の resolved に在り、かつ of の前の
    往復の単位（earlier_units）が今の block の単位と重なる時に採る。missed の申告は既定と同じ時だけ採る（引用で照らした既定）。
    同じ key に (origin, of, quote) の違う申告が 2 つ以上在れば、どれも採らず、引用の無い既定に落とす。項目の控えが前の往復と
    今の往復の両方に無ければ（mine が空）、どの申告も採らずに unsplit"""
    said = {}
    for c in claimed:
        said.setdefault(c["key"], set()).add((c["origin"], c.get("of"), c.get(QUOTE) or ""))
    conflicted = {key for key, claims in said.items() if len(claims) > 1}
    before = {it["id"]: it for it in prev}
    changed = {r["id"] for r in rows if (before.get(r["id"]) or {}).get("hash") != r["hash"]}
    out = {}
    for key in new:
        mine = [rows[i] for i in _attributed(face_units.get(key) or [], rows)] if rows and prev else []
        if not mine:
            out[key] = ORIGIN_UNSPLIT
            continue
        origin, of, quote = next(iter(said[key])) if key in said and key not in conflicted else (None, None, "")
        ids = {r["id"] for r in mine}
        out[key] = (ORIGIN_INTRODUCED if all(i not in before for i in ids)
                    else ORIGIN_MISSED if not ids & changed else _quoted(quote, mine, before, changed))
        if origin == ORIGIN_INTRODUCED and changed:
            out[key] = ORIGIN_INTRODUCED
        elif (origin == ORIGIN_REPHRASED and of in earlier and of in resolved
              and set(earlier_units.get(of) or []) & set(face_units.get(key) or [])):
            out[key] = ORIGIN_REPHRASED
    return out, [copy.deepcopy(c) for c in claimed if c["key"] in conflicted or out.get(c["key"]) != c["origin"]]


def _quoted(quote: str, mine: list, before: dict, changed: set) -> str:
    """変わった項目を含む mine の出自を、引用 quote が当たる文で決める（_origins の既定の最後の段）。前の往復に無い項目は前の行を
    空として全部の文を足した文に数える"""
    if len(quote.strip()) < cite.QUOTE_MIN:
        return ORIGIN_UNSPLIT
    kept, added, removed = [], [], []
    for r in mine:
        if r["id"] not in changed:
            kept += sentences(r.get("row") or {})
            continue
        gone, came, stayed = sentence_diff((before.get(r["id"]) or {}).get("row") or {}, r.get("row") or {})
        if r["id"] in before and not gone and not came:   # 変化が並びだけ: 文から見えない
            return ORIGIN_UNSPLIT
        added += came
        removed += gone
        kept += stayed
    hit = [any(cite.quoted_in(quote, text, norm=cite.fold) for _, text in pairs) for pairs in (kept, added, removed)]
    return {(True, False, False): ORIGIN_MISSED, (False, True, False): ORIGIN_INTRODUCED}.get(tuple(hit), ORIGIN_UNSPLIT)


def _item_states(plan: list, faces: list, face_units: dict, prev: list, earlier: set) -> list[dict]:
    before = {it["id"]: it for it in prev}
    rows = [{"n": n, "id": it["id"], "unit_keys": list(it["unit_keys"]), "hash": it["hash"], "state": OPEN, "blocks": [],
             "reopened": False, **({"row": copy.deepcopy(it["row"])} if "row" in it else {})} for n, it in enumerate(plan, 1)]
    hard = {f.get("key") for f in faces if central(f)}
    for f in faces:
        for i in _attributed(face_units.get(f.get("key")) or [], rows):
            rows[i]["blocks"].append(f.get("key"))
    for r in rows:
        was = (before.get(r["id"]) or {}).get("state")
        if was == HELD:
            r["state"], r["blocks"] = HELD, (before[r["id"]].get("blocks") or [])
        elif not r["blocks"]:
            r["state"] = CLOSED
        elif set(r["blocks"]) & hard & earlier:   # 端の block が続いても保留にしない（2 往復目から開いた block が端だけなら SETTLED）
            r["state"] = HELD
        r["reopened"] = was == CLOSED and r["state"] != CLOSED
    return rows


def _last_items(doc: dict) -> dict:
    return {it["id"]: it for it in (doc["passes"][-1].get("items") or [])} if doc["passes"] else {}


def add_pass(doc: dict, review: dict, *, answers: list, resolved: list, synergy: list | None = None,
             hits: dict | None = None, origins: list | None = None, at_cap: bool = False, refs: dict | None = None,
             push=None) -> dict:
    """控え doc に事前審査の返答 1 つを往復の行として足し、decide で抜け方を決めて doc と行の outcome に置く（ファイルの写し・
    書き込み・trace はしない）。at_cap（呼び手が渡す、輪がもう 1 周回せない事実）が真で decide が AGAIN の往復は、行に
    capped: true を立てて UNSETTLED（保留の項目が在れば PERSISTED）で止める（決まりは decide のまま。CLEAN と止める往復は
    変えない）。抜け方が AGAIN の往復で怪しい印（suspicion。人の答えの後から SUSPECT_ROUNDS 往復・審査の穴の中身が移った）が立てば、
    行に suspect を置いて同じく止まりにする（人に聞く合図。数の上限で打ち切るのでなく、人の答えで数え直す）。origins（審査の出自の申告の行。型は節の output_format か、受け付けが答えのファイルの型（ORIGIN_SCHEMA の写し）で照らし済み）は
    _origins が照らして、2 往復目からの新しい block の出自を行の origins に置く（採らなかった申告は origins_claimed）。refs（{項目の番号:
    その項目の答えの対応表の design_ref の並び}）は審査した項目の items の行に置く（carried_refs が、閉じた項目が受けた要素を後の往復の
    網羅に数える。carried_refs）。push（返答の一番上の止まった時の推し STUCK_PUSH の値。形は照らさず、読む gatemarks が照らす）は、
    在れば行の push に置く。返りは足した行"""
    passes = doc["passes"]
    k = len(passes) + 1
    faces = block_faces(review)
    blocks = [f.get("key") for f in faces]
    earlier = {key for p in passes for key in p.get("blocks", [])}
    suggests = [f.get("key") for f in _faces(review) if f.get("severity") != "block"]
    row = {"pass": k, "blocks": blocks, "faces": [_face_row(f) for f in faces],
           "suggests": list(dict.fromkeys(suggests)), "answers": answers,
           "notes": list({f.get("key"): copy.deepcopy(f) for f in _faces(review) if f.get("severity") != "block"}.values()),
           "resolved": list(resolved), "persists": [key for key in blocks if key in earlier], "outcome": None,
           "origins": {}, "origins_claimed": [], "files": {}, "rejects": []}
    if push is not None:
        row["push"] = copy.deepcopy(push)
    if doc.get("plan"):
        row["face_units"] = {f.get("key"): [str(k) for k in f.get("unit_keys") or []] for f in faces}
        row["items"] = _item_states(doc["plan"], faces, row["face_units"],
                                    list(_last_items(doc).values()), earlier)
        for it in row["items"]:
            if it["n"] in (hits or {}):
                it["hits"] = copy.deepcopy(hits[it["n"]])
            if it["n"] in (refs or {}):
                it["refs"] = list(refs[it["n"]])
        row["synergy"] = list(synergy or [])
    row["origins"], row["origins_claimed"] = _origins(
        [key for key in blocks if key not in earlier] if passes else [], origins if isinstance(origins, list) else [],
        rows=row.get("items") or [], prev=list(_last_items(doc).values()), face_units=row.get("face_units") or {},
        earlier=earlier, earlier_units={key: units for p in passes for key, units in (p.get("face_units") or {}).items()},
        resolved=list(resolved))
    passes.append(row)
    row["outcome"] = decide(passes)
    if row["outcome"] == AGAIN:
        suspect = suspicion(passes)
        if suspect:   # 怪しいと見た: 次の往復を始めず、止まりにして人に聞く（決まり decide は変えない。印は行の suspect）
            row["suspect"] = suspect
        if at_cap:   # 輪がもう 1 周回せない: 抜けないと輪が尽きて節が落ちるので、ここで止める
            row["capped"] = True
        if suspect or at_cap:
            row["outcome"] = PERSISTED if HELD in [it.get("state") for it in row.get("items") or []] else UNSETTLED
    doc["outcome"] = row["outcome"]
    return row


def since_person(passes: list[dict]) -> list[dict]:
    """人の答えの後の往復（最後に人の求め person を差し込んだ往復より後の行。差し込みが無ければ全部）。怪しいと見る印はこの中だけで数える
    （人が設計し直しを求めた所から数え直す）"""
    marked = [i for i, p in enumerate(passes) if p.get("person")]
    return passes[marked[-1] + 1:] if marked else list(passes)


def _drift(passes: list[dict], seg: list[dict]) -> tuple[list, list]:
    """（前の往復の中央の block, この往復の新しい中央の block）。審査の穴の中身が移った時だけ両方が空でない: 人の答えの後の往復が 2 つ以上・
    前の往復の中央の block が 1 つ以上在り、そのどれもこの往復の block に無い・この往復の新しい（前のどの往復にも無い）中央の block が
    1 つ以上在り、その出自（origins）が全部 ORIGIN_INTRODUCED。ほかは ([], [])"""
    if len(seg) < 2:
        return [], []
    prev, last = seg[-2], seg[-1]
    gone = central_keys(passes[:-1], prev.get("blocks") or [])
    earlier = {k for p in passes[:-1] for k in p.get("blocks") or []}
    came = [k for k in central_keys(passes, last.get("blocks") or []) if k not in earlier]
    origins = last.get("origins") or {}
    if gone and came and not set(gone) & set(last.get("blocks") or []) and all(origins.get(k) == ORIGIN_INTRODUCED for k in came):
        return gone, came
    return [], []


def suspicion(passes: list[dict]) -> list[str]:
    """往復が怪しいと見る印の語の並び（issue #838。どちらも yes/no の決まり。無ければ []）。数えるのは人の答えの後の往復（since_person）:
    SUSPECT_LONG はその数が SUSPECT_ROUNDS 以上、SUSPECT_DRIFT は最後の往復で穴の中身が移った（_drift）。呼び手 add_pass は抜け方が
    AGAIN の往復だけに当てる（CLEAN・SETTLED・止まりは変えない）"""
    seg = since_person(passes)
    out = [SUSPECT_LONG] if len(seg) >= SUSPECT_ROUNDS else []
    return out + ([SUSPECT_DRIFT] if _drift(passes, seg)[1] else [])


def suspected(doc: dict) -> bool:
    """往復の記録が、怪しいと見て止めた物か（最後の往復の行に suspect が在り、抜け方が止まり。人が設計し直しを求めれば AGAIN に戻る）"""
    return bool(doc.get("outcome") in STUCK and doc.get("passes") and doc["passes"][-1].get("suspect"))


def suspect_text(doc: dict) -> str:
    """怪しいと見て止めた訳の 1 文（SUSPECT_HEAD。止めていなければ空）"""
    if not suspected(doc):
        return ""
    passes = doc["passes"]
    seg = since_person(passes)
    gone, came = _drift(passes, seg)
    why = [SUSPECT_WHY[w].format(n=len(seg), gone=_keys(gone), came=_keys(came)) for w in passes[-1]["suspect"] if w in SUSPECT_WHY]
    return SUSPECT_HEAD.format(why="・".join(why))


PERSON_KIND = "person"   # 人が設計の相談の承認ノードで求めた直しの穴の kind（審査役の穴の kind と分ける）
PERSON_WHERE = "設計の相談の承認ノード（gate-design）"
PERSON_REACH = "forces_redesign"   # converge.CENTRAL の 1 つ。人の求めは中央の block として数える（端へ下げて素通りさせない）


def ask_again(doc: dict, *, key: str, text: str) -> dict:
    """人が設計の相談の承認ノードで設計し直しを求めた（答え revise と一言 text）時に、記録 doc の最後の往復の行へ、その求めを中央の block の穴
    {key, kind: PERSON_KIND, where, why: text, reach} として足し、全部の項目を開き直して（保留も開く。人が直せと言った）、抜け方を AGAIN に
    する。穴は face_units を持たないので全部の項目の物（converge._touches）になり、次の周の plan は block_answers でこの key に答え、
    事前審査は resolved に入れるか同じ key で挙げ直す（converge.answer_gaps・resolved_gaps）。挙げ直せば前の往復の中央の block と重なり、
    止め時の決まりのまま PERSISTED で止まる（人の求めを消えたことにしない）。往復の無い記録は変えずに返す（呼び手は一言を依頼の答えの
    行として plan に渡す）。行の person に {key, text} を積む（報告と照らしの控え）。返りは doc"""
    if not doc.get("passes"):
        return doc
    last = doc["passes"][-1]
    face = {"key": key, "kind": PERSON_KIND, "where": PERSON_WHERE, "why": text, REACH: PERSON_REACH}
    last["blocks"] = [*[k for k in last.get("blocks") or [] if k != key], key]
    last["faces"] = [*[f for f in last.get("faces") or [] if f.get("key") != key], face]
    last.setdefault("person", []).append({"key": key, "text": text})
    for it in last.get("items") or []:
        it["reopened"] = it.get("reopened") or it.get("state") == CLOSED
        it["state"] = OPEN
        it["blocks"] = [*[k for k in it.get("blocks") or [] if k != key], key]
    last["outcome"] = AGAIN
    doc["outcome"] = AGAIN
    return doc


def held(doc: dict) -> dict | None:
    """抜け方が AGAIN（修正案の役に返す）時の最後の往復の行"""
    return doc["passes"][-1] if doc.get("outcome") == AGAIN and doc.get("passes") else None


def _open_blocks(row: dict) -> list:
    """往復の行の block のうち、開いた項目の物（items の無い行は全部）"""
    if row.get("items") is None:
        return list(row["blocks"])
    mine = {k for it in row["items"] if it.get("state") == OPEN for k in it.get("blocks") or []}
    return [k for k in row["blocks"] if k in mine]


def _face_row(f: dict) -> dict:
    """穴の行の FACE_KEYS と、札 REACH（在る時だけ。札の無い行は今までの形のまま）"""
    return {**{n: f.get(n, "") for n in FACE_KEYS}, **({REACH: f[REACH]} if REACH in f else {})}


def _keys(keys) -> str:
    return "、".join(keys) if keys else NONE


def stuck_keys(doc: dict) -> list:
    """止まった壁打ち（PERSISTED・UNSETTLED）の、止めた block の key（stuck_reason・uncited・stuck_faces が読む 1 つの式）。
    項目の無い控えは PERSISTED なら最後の往復の続いた key・UNSETTLED なら最後の往復の block。項目の在る控えは、保留の項目の
    block（前の往復の物。今の往復は審査しない）と開いた項目の block。止まっていなければ []"""
    if doc["outcome"] not in STUCK:
        return []
    last = doc["passes"][-1]
    keys = last["persists"] if doc["outcome"] == PERSISTED else last["blocks"]
    if last.get("items") is not None:
        keys = list(dict.fromkeys(k for it in last["items"] if it.get("state") in (HELD, OPEN) for k in it["blocks"]))
    return keys


def _stuck_items(doc: dict) -> list:
    """止まった控えの最後の往復の、保留・開いた項目の番号（項目の無い控えは []）"""
    last = doc["passes"][-1] if doc["outcome"] in STUCK else {}
    return [it["n"] for it in last.get("items") or [] if it.get("state") in (HELD, OPEN)]


def uncited(note: str, doc: dict) -> list[str]:
    """止まった時の推し（STUCK_PUSH）の note が字のまま引いていない物の並び: stuck_keys の key（前後に key の字 KEY_CHAR が続かない
    一致。長い key の断片は引用に数えない）と、最後の往復の保留・開いた項目の『項目 n』（後ろに数字が続かない一致。『項目 12』は
    『項目 1』の引用に数えない）。止まっていなければ []。
    修正役に届くのは note だけなので、推しが修正の義務（止まった key と項目）に触れているかをここで照らす"""
    note = str(note or "")
    out = [k for k in stuck_keys(doc) if not re.search(rf"(?<!{KEY_CHAR})" + re.escape(k) + rf"(?!{KEY_CHAR})", note)]
    out += [name for n in _stuck_items(doc) for name in [f"項目 {n}"] if not re.search(re.escape(name) + r"(?!\d)", note)]
    return out


def stuck_faces(doc: dict) -> list[dict]:
    """止まった壁打ちの stuck_keys のうち、最後の往復の faces に無い key（保留の項目の前の往復の block）を、その key を最後に挙げた
    往復の faces と face_units から owed_faces と同じ形 {key, kind, where, why, reach?, severity: block, unit_keys} に印 HELD_MARK を足して
    返す（stuck_keys の順。挙げた往復が控えに無い key は返さない）。review.json の faces に足すと、修正役が事前審査の穴に key ごとに
    答える道（fixboard.plan_face_rows）に、保留の項目の block も義務として乗る"""
    keys = stuck_keys(doc)
    if not keys:
        return []
    passes = doc["passes"]
    now = {f.get("key") for f in passes[-1]["faces"]}
    out = []
    for key in keys:
        if key in now:
            continue
        for p in reversed(passes):
            f = next((x for x in p["faces"] if x.get("key") == key), None)
            if f is not None:
                out.append({**_face_row(f), "severity": "block",
                            "unit_keys": [str(k) for k in (p.get("face_units") or {}).get(key) or []], HELD_MARK: True})
                break
    return out


def capped(doc: dict) -> bool:
    """最後の往復が輪の安全の上限の周で止めた物か（capped を立てるのは add_pass で、止める往復の行だけなので、最後の行を見れば足りる）"""
    return bool(doc["passes"] and doc["passes"][-1].get("capped"))


def _items_text(items: list) -> str:
    def named(state, blocks=False):
        rows = [_label(it) + (f"・最後の block: {_keys(it['blocks'])}" if blocks else "")
                for it in items if it.get("state") == state]
        return "、".join(rows) or NONE
    return ITEMS_WHY.format(closed=named(CLOSED), held=named(HELD, True), open=named(OPEN, True))


def _share_text(passes: list) -> str:
    """頭の行の割合の句: 1 回目の block の数と、後の回の新しい block の出自ごとの数（往復の行の origins だけから数える）。
    1 回目に出た割合の分母は 1 回目・見落とし・分けられない（持ち込みと言い換えは入れない）、止めた全部のうちの割合の分母は
    それに持ち込みを足した数。止めた block が 0 件なら割らない。見落としは後の往復が審査した所の物だけなので、閉じて後の往復が
    見ない項目の取りこぼしは分母に入らず、1 回目に出た割合は実際より高く出うる（上限）。run の後で見つかった穴も割合に入らない"""
    people = {str(r.get("key")) for r in passes[0].get("person") or [] if isinstance(r, dict)}   # 人の求め（ask_again）は審査役の block でない
    first = len([k for k in passes[0].get("blocks", []) if k not in people])
    made = [w for p in passes[1:] for w in (p.get("origins") or {}).values()]
    n = {w: made.count(w) for w in ORIGIN_WORDS}
    seen = first + n[ORIGIN_MISSED] + n[ORIGIN_UNSPLIT]
    total = seen + n[ORIGIN_INTRODUCED]
    if not total:
        return LINE_NO_BLOCK
    return LINE_SHARE.format(first=first, missed=n[ORIGIN_MISSED], introduced=n[ORIGIN_INTRODUCED],
                             rephrased=n[ORIGIN_REPHRASED], unsplit=n[ORIGIN_UNSPLIT],
                             share=f"{first}/{seen}" if seen else NONE, total=f"{first}/{total}")


# ---------------------------------------------------------------- 記録の読み書き（盤面でなく記録の dict と place のパス）
def fresh() -> dict:
    return {"round": 1, "passes": [], "outcome": None}


def read(path) -> dict:
    """記録のファイル path（None・無い・読めない・形が違うなら往復の無い記録）。plan と precedent_checks は在れば残す"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8")) if path else None
    except (OSError, UnicodeDecodeError, ValueError):
        return fresh()
    if not isinstance(doc, dict) or not isinstance(doc.get("passes"), list) or not all(isinstance(p, dict) for p in doc["passes"]):
        return fresh()
    out = {"round": 1, "passes": doc["passes"], "outcome": doc.get("outcome")}
    for key, kind in (("plan", list), ("precedent_checks", dict)):
        if isinstance(doc.get(key), kind):
            out[key] = doc[key]
    return out


def write(path, doc: dict) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _int_keys(got) -> dict:
    """{"1": …} の鍵を整数に（JSON の object の鍵は字。add_pass は項目の番号の整数で引く）"""
    return {int(k) if isinstance(k, str) and k.isdigit() else k: v for k, v in got.items()} if isinstance(got, dict) else {}


def record_pass(doc: dict, got: dict, *, at_cap: bool, dest, plan_rejects=()) -> dict:
    """pass.json の中身 got（{pass, plan, answers, review, resolved, synergy, hits, origins, refs, push, files, rejects,
    precedent_checks}）を往復の行として記録 doc に足す（今の converge.record_pass と stash_rejects と planblk.save_precedents を
    line が当てる）。plan（converge.plan_rows の行）を記録の plan に置いてから足し、files の在るファイルを dest（往復のフォルダ）へ
    写して行に写した先を置き、計画の拒否 plan_rejects（role plan）と事前審査の拒否 got.rejects を行の rejects に積み、
    precedent_checks を記録の頭に重ねる（控えに在る出典は書き換えない）。返りは足した行"""
    if isinstance(got.get("plan"), list):
        doc["plan"] = got["plan"]
    row = add_pass(doc, got.get("review") if isinstance(got.get("review"), dict) else {},
                   answers=got.get("answers") if isinstance(got.get("answers"), list) else [],
                   resolved=got.get("resolved") if isinstance(got.get("resolved"), list) else [],
                   synergy=got.get("synergy") if isinstance(got.get("synergy"), list) else None,
                   hits=_int_keys(got.get("hits")), origins=got.get("origins") if isinstance(got.get("origins"), list) else None,
                   at_cap=at_cap, refs=_int_keys(got.get("refs")), push=got.get("push"))
    dest = pathlib.Path(dest)
    for name, src in (got.get("files") or {}).items() if isinstance(got.get("files"), dict) else ():
        if isinstance(src, str) and os.path.isfile(src):
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / pathlib.Path(name).name)
            row["files"][name] = str(dest / pathlib.Path(name).name)
    row["rejects"] = [*({"role": PLAN_ROLE, **r} for r in plan_rejects or [] if isinstance(r, dict)),
                      *(r for r in got.get("rejects") or [] if isinstance(r, dict))]
    checks = got.get("precedent_checks")
    if isinstance(checks, dict):
        doc["precedent_checks"] = {**checks, **(doc.get("precedent_checks") or {})}
    return row


def open_items(doc: dict) -> list[int]:
    """次の事前審査が見る項目の番号（今の案の項目のうち、最後の往復で閉じた・保留にした項目でない物）。項目の控えが無ければ []"""
    last = _last_items(doc)
    return [n for n, it in enumerate(doc.get("plan") or [], 1) if (last.get(it["id"]) or {}).get("state") not in (CLOSED, HELD)]


def stuck_reason(doc: dict, path="") -> str:
    """止まった壁打ちの承認ノードの理由（PERSISTED・UNSETTLED の時だけ。ほかは空）。path は往復ごとの案と審査の置き場"""
    if doc.get("outcome") not in STUCK:
        return ""
    passes = doc["passes"]
    last = passes[-1]
    text = PERSISTED_WHY if doc["outcome"] == PERSISTED else UNSETTLED_WHY
    why = text.format(keys=_keys(stuck_keys(doc)), n=len(passes), path=path)
    why += "。" + _items_text(last["items"]) if last.get("items") is not None else ""
    if suspected(doc):
        why += "。" + suspect_text(doc)
    if capped(doc):
        why += "。" + CAP_WHY.format(n=len(passes), counts=" → ".join(f"{p['pass']} 往復目 {len(_open_blocks(p))}" for p in passes))
    return why


def lines(doc: dict, path="") -> list[str]:
    """報告の行（往復が無ければ []。在れば頭の 1 行と往復ごとの 1 行）"""
    passes = doc.get("passes") or []
    if not passes:
        return []
    persists = list(dict.fromkeys(key for p in passes for key in p.get("persists", [])))
    out = [LINE_HEAD.format(n=len(passes), word=WORDS.get(doc["outcome"], doc["outcome"]), outcome=doc["outcome"],
                            persists=_keys(persists), share=_share_text(passes), path=path)]
    out += [f"  - {suspect_text(doc)}"] if suspected(doc) else []
    earlier, hard = set(), set()
    for p in passes:
        handled = [a.get("handled") for a in p.get("answers", []) if isinstance(a, dict)]
        down = [key for key in p.get("suggests", []) if key in earlier]
        down += [f.get("key") for f in p.get("faces") or [] if f.get("key") in hard and not central(f)]
        out.append(LINE_PASS.format(k=p["pass"], keys=_keys(p["blocks"]), f=handled.count("fixed"),
                                    d=handled.count("disputed"), resolved=_keys(p.get("resolved", [])), down=_keys(down)))
        out += [LINE_DISPUTED.format(key=a.get("key"), how=a.get("how")) for a in p.get("answers", [])
                if isinstance(a, dict) and a.get("handled") == "disputed"]
        if p.get("items") is not None:
            count = {st: [str(it["n"]) for it in p["items"] if it.get("state") == st] for st in (CLOSED, OPEN, HELD)}
            out.append(LINE_ITEMS.format(closed=_keys(count[CLOSED]), open=_keys(count[OPEN]), held=_keys(count[HELD]),
                                         synergy=_keys(p.get("synergy") or [])))
        earlier.update(p.get("blocks", []))
        hard.update(central_keys([p], p.get("blocks", [])))
    return out


# ---------------------------------------------------------------- 止まった案を推しで進める（元 gatepolicy.stuck_pushable・gatemarks.stuck_push）
def stuck_pushable(doc: dict, push, *, unattended: bool, design_talk: bool) -> bool:
    """止まった事前審査の壁打ち（記録 doc）の行に、事前審査の役の推し push（{go, note}。無ければ None）の尾を付けてよいか。全部が
    揃う時だけ: 無人の run・設計だけの run でない・抜け方が止まり・最後の往復が輪の安全の上限の周で止めた物でない（上限での止まりは
    工場の不具合 CAP_WHY で、人が見る）・怪しいと見て止めた物でない（suspected。人に聞く合図なので、無人の run は推しで越えずに止まる）・通す推しで、その note が止まった key と保留・開いた項目の番号の全部を字のまま引く
    （uncited が空。修正役に届くのは note だけ）。元 lib/gatepolicy.py の stuck_pushable（無人の印を始めの記録でなく引数で受ける）"""
    go = getattr(push, "go", None) if not isinstance(push, dict) else push.get("go")
    note = getattr(push, "note", None) if not isinstance(push, dict) else push.get("note")
    return (unattended and not design_talk and doc.get("outcome") in STUCK and not capped(doc) and not suspected(doc)
            and push is not None and go is True and not uncited(note, doc))


def last_push(doc: dict) -> dict | None:
    """最後の往復の行の推し（形の整った recommend だけ）の {go, note}（note は尾の字。今の gatemarks.stuck_push の読み）。無ければ None"""
    import gatemarks
    mark = {gatemarks.RECOMMEND: doc["passes"][-1].get("push") if doc.get("passes") else None}
    rec = gatemarks.recommend_of(mark)
    if rec is None:
        return None
    return {"go": rec[gatemarks.RECOMMEND_KEYS[0]] == gatemarks.RECOMMEND_ANSWERS[0],
            "note": gatemarks._tail_text(rec[gatemarks.RECOMMEND_KEYS[1]])}


def stuck_push_due(doc: dict, *, unattended: bool, design_talk: bool) -> bool:
    return stuck_pushable(doc, last_push(doc), unattended=unattended, design_talk=design_talk)


# ---------------------------------------------------------------- 計画の周の前の支度（node owed）
# 計画の 1 回目の周が修正案の役を起こすかを、plan の block の周を開く口（plan の block の intake）と同じ式で決める。式は lib/judgmark.py
# の held_why（plan・diagnose・verify と共に使う。使い手 2 つ以上は lib）。line の stuck_reason（往復の記録）とは別物


def _pointed(raw):
    """pointer かパスの字の先のパス（null・空は None）。読めなければ ValueError"""
    import ports
    return None if ports.parsed(raw) is None else ports.file(raw)


def owed_why(judgment_raw, ties_raw, materials_raw, world_raw, *, answers, takes_push: bool) -> str:
    """計画の 1 回目の周が修正案の役を起こさない訳（起こすなら空）。入力が読めない（判定・世界の解の行）なら「<名>が読めない（<訳>）」を
    「。」で繋いだ訳、読めれば judgmark.held_why（問いの台帳の見え方は、依頼の answers と結びと素材の状態と無人の推し。judgmark.with_ledger）"""
    import judgmark
    import worldmark
    bad, doc = [], None
    try:
        path = _pointed(judgment_raw)
        doc = json.loads(path.read_text(encoding="utf-8")) if path is not None else None
        if path is None:
            bad.append("判定が読めない（空）")
    except (OSError, ValueError) as e:
        bad.append(f"判定が読めない（{e}）")
    try:
        world = _pointed(world_raw)
        if world is not None:
            worldmark.rows(str(world))
    except (OSError, ValueError) as e:
        bad.append(f"world が読めない（{e}）")
    if bad:
        return "。".join(bad)
    judgment = judgmark.with_ledger(doc, ties_file=_pointed(ties_raw), materials_file=_pointed(materials_raw), answers=answers,
                                    takes_push=takes_push)
    return judgmark.held_why(judgment)


def start_items(answer) -> list:
    """起動の承認ノードの答え（{decision, text} か null）を、記録された方針の行の人の答えの行 [{round, node, kinds, answer, note}] に
    （元 lib/boardview.py の human_items）"""
    import gatemarks
    rows = answer if isinstance(answer, list) else [answer] if isinstance(answer, dict) else []
    return [{"round": 1, "node": gatemarks.START_GATE_NODE, "kinds": [], "answer": a["decision"], "note": a.get("text") or ""}
            for a in rows if isinstance(a, dict) and a.get("decision")]


def recorded_rows(record, dealt: dict, *, decisions, answer) -> list:
    """事前審査に渡す記録された方針の行（policy.recorded。始めの記録の欄 policy の固めた版と依頼の answers・起動の承認ノードの答え・
    判定の決着済みの論点）。record は始めの記録の dict（無ければ配る値の方針の写しと依頼の answers から同じ形を組む）"""
    import policy
    start = record if isinstance(record, dict) else {"policy_md": dealt.get("policy") or "", "answers": dealt.get("request_answers") or []}
    return policy.recorded(start, decisions, human_items=start_items(answer))
