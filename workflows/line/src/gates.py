"""承認ノードの決め（docs/design/line.md の 2 節と 6 節。README 9.2 の MOVE）。

元 lib/gatepolicy.py の全部（最後の承認ノードの開き方と無人の方針）・元 lib/gate_axes.py（4 つの軸を軸ごとにまとめる。材料は事前審査の
返りの行に替えた）・元 lib/gatemarks.py の承認ノードの決めの部分（開くか・項目の行・通した行・無人の抜け方・row_push・_as_push・
design_only・request_answers・design_item・stuck_push・design_items・_continued・_item。integration.md の 4.5-4 (a)(b)）と、元
lib/boardview.py の方針の文書の変化（policy_change・change_row）と HUMAN_FACE_KINDS・replan_asks の「聞くか」の決め。
問いの行の形（ASKING・asks_human・ask_text・推しの尾の字の形 push_rec・_push・recommend_of・decided・gate_text・head3・pass_lines）
と問いの台帳の値の見え方（ledger・ledger_files・answered）は KEEP の lib/gatemarks.py を引く（README 9.3）。

始めの記録は src.startrec の口で読み、KEEP の lib に記録を読ませない（integration.md の 4.3-追加-6）。

- 最後の承認ノードの開き方と無人の語（元 gatepolicy）: FINAL_KEY・UNATTENDED_KEY・FINAL_GATES（ALWAYS・WHEN_NEEDED・PROTECTED_ONLY）・
  UNATTENDED・UNATTENDED_WORDS・FINAL_KIND・Refused・check・unattended_of・opens・head_words・Push・Passage・
  passage（stuck_pushable は往復の記録の住処 src.rounds が持つ）
- row_push(text)・_as_push(rec, note): 項目の推しの尾の、無人の方針の読み（元 gatemarks）
- design_only(doc)・request_answers(doc): 始めの記録の dict から、設計だけの run か・依頼が先に持っていた答え（元 gatemarks の
  startrec.read の道）
- AXES・gather(asks, deviations, design_rows) -> {軸: {ok, note}}: 4 つの軸（元 gate_axes.gather。軸ごとの訳は事前審査の返りの行の why）
- before_fix(...): 修正前の承認ノード（2 節の 2）の決め（返り {open, go, stop_reason, items, deferred, asked, pushed, passes, policy_changed}）
- replan_rows(...)・replan(...): 案の直しの承認ノード（2 節の 3）の「聞くか」と項目の行
- policy_change(record, cwd, folder)・change_row(ch): 固めた方針の文書と今の文書の版の比べ（元 boardview）
- path_of(value)・read_json(path): pointer かパスの値をファイルのパスに・ファイルの JSON
- review_verdict(...): 修正が使った案を審査した最後の往復の結論 {round, verdict, blocks, why}（独立の目の port review。元
  boardview.read_open_of の「往復と案が組むか」の照らしと eyeverdict.plan_review_line の通否）
"""
from __future__ import annotations

import difflib
import json
import os
import pathlib
from typing import Callable, NamedTuple

import answer
import gatemarks
import policy
import stopby
import structmark


# ---------------------------------------------------------------- 元 lib/gatepolicy.py
FINAL_KEY = "final_gate"
UNATTENDED_KEY = "unattended"
FINAL_GATES = ("always", "when_needed", "protected_only")
ALWAYS, WHEN_NEEDED, PROTECTED_ONLY = FINAL_GATES
UNATTENDED = "true"
UNATTENDED_WORDS = ("", UNATTENDED)
FINAL_KIND = FINAL_KEY


class Refused(ValueError):
    """入口の語が受けられない（入口が InputRefused にする）"""


def check(final, unattended, *, spec) -> dict:
    """入口の 2 つの語を確かめて {FINAL_KEY: 開き方（空は ALWAYS、無人の run の空は WHEN_NEEDED）, UNATTENDED_KEY: 語} を返す"""
    alone = (unattended or "").strip()
    if alone not in UNATTENDED_WORDS:
        raise Refused(f"{UNATTENDED_KEY}={unattended!r} は知らない値（空か {UNATTENDED}）")
    mode = (final or "").strip() or (WHEN_NEEDED if alone else ALWAYS)
    if mode not in FINAL_GATES:
        raise Refused(f"{FINAL_KEY}={final!r} は知らない値（{' / '.join(FINAL_GATES)}）")
    if spec and alone:
        raise Refused(f"spec=on と無人の run（{UNATTENDED_KEY}）は組めない——仕様の承認は承認ノードで、無人の run は承認ノードで止めるので"
                      "仕様が固まらずに止まる（人の居る run で回す）")
    return {FINAL_KEY: mode, UNATTENDED_KEY: alone}


def unattended_of(doc) -> bool:
    """始めの記録の dict（か None）が無人の run か"""
    return isinstance(doc, dict) and doc.get(UNATTENDED_KEY) == UNATTENDED


def opens(mode: str, *, reasons, guarded: bool) -> bool:
    """最後の関所を開くか: ALWAYS はいつも、WHEN_NEEDED は開ける理由が在る時、PROTECTED_ONLY は守りのファイルを触った時"""
    if mode == WHEN_NEEDED:
        return bool(reasons)
    if mode == PROTECTED_ONLY:
        return bool(guarded)
    return True


def head_words(doc: dict) -> str:
    """報告の頭の行の句（始めの記録の dict の開き方。無ければ空）"""
    mode = doc.get(FINAL_KEY) if isinstance(doc, dict) else None
    return f"最後の承認ノード: {mode}" if mode else ""


class Push(NamedTuple):
    go: bool     # 通す（continue）推しか
    note: str    # 修正役に人の一言と同じ道で届く一言（尾の字）
    rec: dict    # 答えの欄 answer.PUSHED に残す読みの全部


class Passage(NamedTuple):
    go: bool
    stop_reason: str
    asked: list
    pushed: dict | None


def passage(rows: list, read: Callable[[str], Push | None]) -> Passage:
    """無人の run で開くはずの承認ノードの抜け方。read は項目の文の推しの尾の読み（row_push。尾が無ければ None）。
    項目の全部が通す推しを持つ時だけ推しで進む（一言は推しの note を「；」で繋いだ物）。項目が無い・推しの無い項目か止める推しが
    1 つでも在れば止める（機械は推しを作らない）"""
    pushes = [read(row) for row in rows]
    if not pushes or not all(p is not None and p.go for p in pushes):
        return Passage(False, stopby.NEEDS_HUMAN, [], None)
    note = "；".join(dict.fromkeys(p.note for p in pushes))
    return Passage(True, "", list(rows), {"decision": answer.VERBS[0], "text": note, answer.PUSHED: [p.rec for p in pushes]})


# ---------------------------------------------------------------- 元 lib/gatemarks.py の承認ノードの決めの部分
DESIGN_ONLY = gatemarks.DESIGN_ONLY
AXIS_KIND = "plan_review"
POLICY_CHANGED = "policy_changed"     # 関所の項目の種類（方針の文書が固めた版から変わった。元 boardview.POLICY_CHANGED）
HUMAN_FACE_KINDS = ("regression", policy.POLICY_KIND)   # 人に回す穴の種類（元 fixboard.HUMAN_FACE_KINDS・boardview の写し）


def row_push(text) -> Push | None:
    """関所の項目の文の推しの尾（gatemarks.push_rec）の、無人の方針の読み（passage に渡す。尾が無ければ None）"""
    rec = gatemarks.push_rec(text)
    return None if rec is None else _as_push(rec, rec[gatemarks.RECOMMEND_KEYS[1]])


def _as_push(rec: dict, note: str) -> Push:
    return Push(rec[gatemarks.RECOMMEND_KEYS[0]] == gatemarks.RECOMMEND_ANSWERS[0], note, rec)


def design_only(doc) -> bool:
    """run が設計だけの run（始めの記録の dict の design_only。読めなければ今どおりの run）"""
    return isinstance(doc, dict) and doc.get("design_only") == DESIGN_ONLY


def request_answers(doc) -> list:
    """依頼が先に持っていた答え（始めの記録の dict の欄 answers。配列でなければ空。gatemarks.ledger に値で渡す）"""
    got = doc.get("answers") if isinstance(doc, dict) else None
    return [a for a in got if isinstance(a, dict)] if isinstance(got, list) else []


def _item(text: str, mark: dict, why=()) -> str:
    """人に回す行の関所の項目の文（世界の解・狭めない案・人に聞く訳・推しの尾つき）"""
    tail = f"（人に聞く訳: {' / '.join(why)}）" if why else ""
    return text + gatemarks._world(mark) + gatemarks._no_narrow(mark) + tail + gatemarks._push(mark)


def _continued(answers, text: str) -> bool:
    """修正前の承認ノードの答え（answers。{decision, text, asked} の並び）が、この文の行を通した（continue）か"""
    return any(isinstance(a, dict) and a.get("decision") in answer.GO_WORDS and text in (a.get("asked") or []) for a in answers or [])


def design_rows(structure) -> list:
    """構造の目の控え（structure の block の出力 structure の先 state.json のパス）の設計の行。控えが無い・落ちた周は []。
    控えや設計の行のファイルが壊れていれば、読めないと名指して ValueError（空の一覧にして設計の問いを黙って消さない）"""
    if not structure:
        return []
    path = pathlib.Path(structure)
    state = structmark.read(path)
    if state is None:
        raise ValueError(f"構造の目の控え {path} を読めない（JSON でないか、status が ok・failed でない。設計の問いを数えていない）")
    if state.get("status") != "ok":
        return []
    try:
        return structmark.rows(state.get("design_file") or "")
    except ValueError as error:
        raise ValueError(f"構造の目の控え {path} の設計の行を読めない（設計の問いを数えていない）: {error}") from None


def design_items(rows: list, answers=()) -> list:
    """構造の目が人に上げた行の関所の項目 [(DESIGN_KIND, 文)]（人が continue で答えた同じ文の行は除く。元 gatemarks.design_items）"""
    out = []
    for r in rows:
        if r.get("route") != structmark.ROUTE_UP:
            continue
        rej = "・".join(f"{x.get('option')}（代償: {x.get('cost')}）" for x in r.get("rejected") or [] if isinstance(x, dict))
        text = (f"{gatemarks.DESIGN_HEAD} {r.get('unit_id')}: {r.get('undecided_because') or r.get('route_reason') or ''}"
                f"／捨てた案: {rej or '（無し）'}／推し: {r.get('chosen') or '構造の目が書いていない'}"
                + (f"（{r['chosen_reason']}）" if r.get("chosen_reason") else ""))
        if not _continued(answers, text):
            out.append((gatemarks.DESIGN_KIND, text))
    return out


def stuck_push(doc: dict, *, unattended_run: bool, design: bool) -> str:
    """止まった壁打ちの行の尾に付ける、事前審査の役の推し（最後の往復の行の push）の尾 gatemarks._push。付けてよいかは
    src.rounds の stuck_push_due（元 gatepolicy.stuck_pushable。往復の記録の住処が持つ）。ほかは空（推しが無い・止める・崩れた・引用が
    欠ける時は passage が今どおり止める）"""
    from src import rounds
    if not rounds.stuck_push_due(doc, unattended=unattended_run, design_only=design):
        return ""
    return gatemarks._push({gatemarks.RECOMMEND: doc["passes"][-1].get("push")})


def design_item(*, design: bool, reason: str, tail: str = "") -> str:
    """関所に載せる設計だけの行。入力 design_only だけなら DESIGN_ONLY_ITEM のまま、事前審査の壁打ちが止まっていれば（reason が
    止まった理由。入力と重なっても 1 行で）尾に止まった理由を付ける。設計だけでない run の止まりは頭を STUCK_ITEM にし、事前審査の
    役の推しの尾 tail（stuck_push）も付けうる。どちらも無ければ空"""
    if reason:
        if design:
            return f"{gatemarks.DESIGN_ONLY_ITEM}。理由: {reason}"
        return f"{gatemarks.STUCK_ITEM}。理由: {reason}{tail}"
    return gatemarks.DESIGN_ONLY_ITEM if design else ""


# ---------------------------------------------------------------- 4 つの軸（元 lib/gate_axes.py）
AXES = gatemarks.AXES
AXIS_WORDS = {"obvious": "自明", "world": "世界の解", "clean": "汚くない", "not_overkill": "やりすぎでない"}


def _note(notes: list) -> dict:
    return {"ok": not notes, "note": "／".join(dict.fromkeys(notes))}


def _why_list(row: dict) -> list:
    """事前審査の返りの asks の行の why（{軸: [訳]}）を軸の順に並べた訳"""
    why = row.get("why") if isinstance(row.get("why"), dict) else {}
    return [w for axis in AXES for w in why.get(axis) or [] if isinstance(w, str)]


def gather(asks: list, deviations: list, design: list) -> dict:
    """関所の全部の行の軸ごとの {ok, note}（note は行の頭と訳）: 事前審査の人に回しうる行（asks の why）・世界の解の外れ
    （deviations の source world の why）・構造の目が人に上げた設計の問い（design_items の文）"""
    notes = {axis: [] for axis in AXES}
    for row in asks:
        why = row.get("why") if isinstance(row.get("why"), dict) else {}
        for axis in AXES:
            notes[axis] += [f"{row.get('text')}: {w}" for w in why.get(axis) or [] if isinstance(w, str)]
    notes["world"] += [f"{d.get('text')}: {' / '.join(d.get('why') or [])}" for d in deviations
                       if d.get("source") == "world" and d.get("why")]
    notes["clean"] += [text for _, text in design]
    return {axis: _note(rows) for axis, rows in notes.items()}


# ---------------------------------------------------------------- 方針の文書の変化（元 lib/boardview.py の policy_change・change_row）
DIFF_MISSING = "固めた版の写しが無いので差分を作っていない"


def policy_change(record: dict, cwd, folder) -> dict | None:
    """始めの記録の固めた版から今の方針の文書が変わったか（変わっていなければ None。固めた版が記録に無い run も None。変わっていれば
    今の版の写しと差分のファイルを folder に置いて {path, from, to, from_copy, to_copy, diff_file}。置き場は名指しか既定の置き場を
    引き直す（後から既定の置き場に置いた文書も変化に数える）。元 graphloops/rules/policy_input.py:82 の change）"""
    pol = policy.version(record)
    if pol is None:
        return None
    d = pathlib.Path(folder)
    path = policy.locate(cwd, pol.get("named") or "") or pol.get("path") or ""
    to, to_copy = policy.snapshot(d, path)
    frm = pol.get("sha256")
    if to == frm:
        return None
    ch = {"path": path, "from": frm, "to": to, "from_copy": pol.get("copy"), "to_copy": to_copy, "diff_file": None}
    if frm and not (ch["from_copy"] and pathlib.Path(ch["from_copy"]).is_file()):
        return {**ch, "diff_missing": DIFF_MISSING}
    diff = d / policy.DIR / f"{(frm or 'none')[:12]}-{(to or 'none')[:12]}.diff"
    diff.parent.mkdir(parents=True, exist_ok=True)
    old = pathlib.Path(ch["from_copy"]).read_text(encoding="utf-8", errors="replace") if ch["from_copy"] else ""
    new = pathlib.Path(to_copy).read_text(encoding="utf-8", errors="replace") if to_copy else ""
    diff.write_text("".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                                 ch["from_copy"] or "（固めた時点で文書が無い）", to_copy or "（今は文書が無い）")),
                    encoding="utf-8")
    return {**ch, "diff_file": str(diff)}


def change_row(ch: dict) -> str:
    """関所の行の 1 行——置き場だけで本文を載せない（元 graphloops/rules/policy_input.py:105）"""
    where = (f"差分 {ch['diff_file']}" if ch.get("diff_file") else ch.get("diff_missing", "")) + \
            f"・前の版の写し {ch.get('from_copy') or '（無い）'}・今の版の写し {ch.get('to_copy') or '（無い）'}"
    return (f"人の方針の文書 {ch['path'] or '（無い）'} が固定した版から変わった: sha256 "
            f"{str(ch['from'])[:12]} → {str(ch['to'])[:12] if ch['to'] else '消えた'}（{where}）")


# ---------------------------------------------------------------- 修正前の承認ノード（docs/design/line.md の 2 節の 2）
GIVEN_UP_FACES = "事前審査の受け付けが諦めた: "   # 元 lib/boardview.py の GIVEN_UP_FACES（諦めた往復の訳を関所の項目に載せた）
REVIEW_FAILED = "事前審査が落ちた（案を審査できていない）: "
REVIEW_FELL = {"gave_up": GIVEN_UP_FACES, "failed": REVIEW_FAILED}


def review_fell_row(rounds: dict) -> str:
    """計画は通ったのに事前審査が諦めた・落ちた周の関所の行（gatemarks.GIVEN_UP_KIND の文。ほかは空）。今の line は諦めた周を関所に
    載せて開き（無人の run は needs-human で止まった）、落ちた周は返す node が例外で run ごと止まった。新しい形はどちらも開ける理由にし、
    黙って修正を飛ばさない（閉じた側に倒す）"""
    head = REVIEW_FELL.get(str(rounds.get("review_status") or ""))
    if head is None or rounds.get("status") != "ok":
        return ""
    return head + (str(rounds.get("review_reason") or "").strip() or "（訳が返っていない）")

def _ask_kind(q) -> str:
    return gatemarks.ASK_KINDS[0] if q.get("kind") == "fork" else gatemarks.ASK_KINDS[1]


def before_fix(rounds: dict | None, *, unattended_run: bool, design: bool, ledger=None, design_rows_=(), policy_row: str = "",
               stuck_reason: str = "", record_doc: dict | None = None, answered=(), unread=()) -> dict:
    """修正前の承認ノードの決め。rounds は計画の往復の受け皿の got（plan-out の返りの欄）、ledger は問いの台帳の値の見え方
    （gatemarks.ledger。判定が無ければ None）、design_rows_ は構造の目の設計の行、policy_row は方針の文書の変化の行（変わっていなければ
    空）、stuck_reason は止まった往復の理由（止まっていなければ空）、record_doc は往復の記録（止まりの行の推しの尾を読む）、answered は
    同じ承認ノードの前の答え（resume で回し直した時に、continue で通した同じ文を聞き直さない）、unread は指す先が無いか読めない控えの訳
    （判定・結び・素材の状態・構造の目・往復の記録。読めないまま修正へ進めず、UNREAD_KIND の行で開く）。
    返り {open, go, stop_reason, items: [(種類, 文)], deferred, asked, pushed, passes, policy_changed}"""
    closed = {"open": False, "go": False, "stop_reason": "", "items": [], "deferred": [], "asked": [], "pushed": None, "passes": [],
              "policy_changed": False}
    if not isinstance(rounds, dict) or rounds.get("status") == "nothing_owed":
        return closed   # 計画ができていない・直す義務 0 件の周は開かず、修正へも進まない（直す物が無い周の印は fix-in が持つ）
    stalled = bool(rounds.get("stalled"))
    fell = review_fell_row(rounds)
    if not rounds.get("ok") and not stalled and not fell:
        return closed
    asks = [a for a in rounds.get("asks") or [] if isinstance(a, dict)]
    deviations = [d for d in rounds.get("deviations") or [] if isinstance(d, dict)]
    rnd = rounds.get("round") if isinstance(rounds.get("round"), int) else 1
    items, passes, deferred = [], [], []
    if fell and not _continued(answered, fell):
        items.append((gatemarks.GIVEN_UP_KIND, fell))
    items += [(kind, text) for kind, text in unread_items(unread) if not _continued(answered, text)]
    kept_asks, kept_devs = [], []   # 聞く行（前に continue で通した同じ文の行を除く）。軸の行はこの行だけから組む
    for a in asks:
        mark = a.get("mark") if isinstance(a.get("mark"), dict) else {}
        decided = bool(a.get("decided"))
        why = _why_list(a) if decided else [gatemarks.NOT_DECIDED_OR_FENCED]
        if why:
            text = _item(str(a.get("text") or ""), mark, why if decided else ())
            if not _continued(answered, text):
                items.append((str(a.get("kind") or AXIS_KIND), text))
                kept_asks.append(a)
        else:   # 決め手が揃う行は聞かずに通し、出どころつきで返す（L-G18・L-G19）
            passes.append({"node": gatemarks.GATE_NODE, "round": rnd, "by": gatemarks.PASSED_BY, "item": str(a.get("text") or ""),
                           "decided_by": str(mark.get("decided_by") or "")})
    ups = design_items(list(design_rows_), answered)
    items += ups
    for d in deviations:
        if d.get("source") != "world":
            continue
        mark = d.get("mark") if isinstance(d.get("mark"), dict) else {}
        if d.get("why"):
            text = f"{d.get('text')}（人に聞く訳: {' / '.join(d.get('why'))}）"
            if not _continued(answered, text):
                items.append((gatemarks.WORLD_KIND, text))
                kept_devs.append(d)
        elif mark.get("decided_by"):
            passes.append({"node": gatemarks.GATE_NODE, "round": rnd, "by": gatemarks.PASSED_BY, "item": str(d.get("text") or ""),
                           "decided_by": str(mark.get("decided_by"))})
    if policy_row and not _continued(answered, policy_row):
        items.append((POLICY_CHANGED, policy_row))
    if ledger is not None:
        for q in gatemarks.asks(ledger):
            if gatemarks.answered(ledger, q):
                continue
            if unattended_run:
                deferred.append(gatemarks.ask_text(q))   # 採れる推しの無い台帳の問いは載せず、報告と次の依頼の下書きへ（L-G33）
            else:
                items.append((_ask_kind(q), gatemarks.ask_text(q)))
    if not any(kind == gatemarks.DESIGN_ONLY_KIND for kind, _ in items):   # 同じ種類の行を 2 度載せない（L-D19・P249）
        tail = stuck_push(record_doc, unattended_run=unattended_run, design=design) if stalled and record_doc else ""
        row = design_item(design=design, reason=stuck_reason if stalled else "", tail=tail)
        if row and not _continued(answered, row):
            items.append((gatemarks.DESIGN_ONLY_KIND, row))
    if not items:   # 軸の訳は項目の尾に在るので、軸の行は項目が無い時だけ足す
        for key, axis in gather(kept_asks, kept_devs, ups).items():
            if not axis["ok"]:
                items.append((AXIS_KIND, f"{AXIS_WORDS[key]}（{key}）の軸が通らない: {axis['note'] or '（訳が無い）'}"))
    changed = any(kind == POLICY_CHANGED for kind, _ in items)
    if not items:
        # 諦めた・落ちた事前審査の行を前に continue で通した run（resume）は、計画のまま修正へ進む
        return {**closed, "go": rounds.get("ok") is True or bool(fell), "deferred": deferred, "passes": passes}
    texts = [text for _, text in items]
    if unattended_run:
        got = passage(texts, row_push)
        # 推しで抜けられずに止めた項目は誰にも見せていないので、載せなかった項目として報告と次の依頼の下書きへ（元 runreport が
        # 無人の run で関所が通さなかった事前審査の問いを下書きにしたのと同じ）
        held = deferred if got.go else [*deferred, *texts]
        return {**closed, "go": got.go, "stop_reason": got.stop_reason, "items": items, "deferred": held, "asked": got.asked,
                "pushed": got.pushed, "passes": passes, "policy_changed": changed}
    return {"open": True, "go": True, "stop_reason": "", "items": items, "deferred": deferred, "asked": texts, "pushed": None,
            "passes": passes, "policy_changed": changed}


# ---------------------------------------------------------------- 案の直しの承認ノード（docs/design/line.md の 2 節の 3・6 節）
def replan_asks(rows: list, *, unattended_run: bool) -> list:
    """事前審査の出力 replan の行 {item, units, contract_changed, human, widened} のうち聞く行（今の boardview.replan_asks の決め）:
    (contract_changed かつ 無人の run で widened でない) か human が在る。読めない行（object でない・item が無い）は聞く側に倒す"""
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get("item") in (None, ""):
            out.append(r)
            continue
        widen_only = unattended_run and bool(r.get("widened")) and not r.get("human")
        if (r.get("contract_changed") and not widen_only) or r.get("human"):
            out.append(r)
    return out


# ---------------------------------------------------------------- 独立の目へ渡す往復の結論（docs/design/line.md の 4.5 の eyes-in）
PLAN_ROUND_OTHER = "最後に開いた往復（pass-{k}）が修正案の周（round {round}）と組まない（別の周の案の往復の結論を、この案の結論と読ませない）"
NO_RECORD = "往復の記録が渡されていない"


def review_verdict(record: dict | None, *, round_: int | None, gave_up=None, replan_review: dict | None = None) -> dict:
    """修正が使った修正案を審査した最後の往復の結論 {round, verdict, blocks, why}（shared:plan-verdict.schema.json の形）。
    案の直しが走れば、その事前審査（replan_review。受け皿の got）の結論。ほかは往復の記録 record（plan-converge.json の中身）の最後の
    往復で、round_ は修正が使った案の周（往復の番号と組まなければ unread）、gave_up は事前審査が諦めた訳の並び"""
    if isinstance(replan_review, dict):
        k = replan_review.get("round") if isinstance(replan_review.get("round"), int) and replan_review["round"] >= 1 else 1
        blocks = [{"key": str(b.get("key") or ""), "why": str(b.get("why") or "")} for b in replan_review.get("blocks") or []
                  if isinstance(b, dict)]
        if replan_review.get("status") == "gave_up":
            return {"round": k, "verdict": "gave_up", "blocks": blocks, "why": str(replan_review.get("reason") or "")}
        if replan_review.get("status") != "ok":
            return {"round": k, "verdict": "unread", "blocks": [], "why": str(replan_review.get("reason") or "案の直しの事前審査が落ちた")}
        return {"round": k, "verdict": "blocked" if blocks else "accepted", "blocks": blocks, "why": ""}
    if not isinstance(record, dict) or not record.get("passes"):
        return {"verdict": "unread", "blocks": [], "why": NO_RECORD}
    from src import rounds
    last = record["passes"][-1]
    k = last.get("pass") if isinstance(last.get("pass"), int) else len(record["passes"])
    if round_ is not None and round_ != k:
        return {"round": k, "verdict": "unread", "blocks": [], "why": PLAN_ROUND_OTHER.format(k=k, round=round_)}
    blocks = [{"key": str(f.get("key") or ""), "why": str(f.get("why") or "")} for f in last.get("faces") or [] if isinstance(f, dict)]
    if gave_up:
        return {"round": k, "verdict": "gave_up", "blocks": blocks, "why": "；".join(str(g) for g in gave_up)}
    outcome = record.get("outcome")
    if rounds.proceeds(outcome):
        return {"round": k, "verdict": "accepted", "blocks": blocks, "why": ""}
    if blocks:
        return {"round": k, "verdict": "blocked", "blocks": blocks, "why": ""}
    return {"round": k, "verdict": "held", "blocks": [], "why": str(outcome or "")}


def read_json(path) -> dict | list | None:
    """ファイルの JSON（パスが無い・読めなければ None）"""
    if not path:
        return None
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def path_of(value) -> str:
    """pointer かパスの値（null・空・"null" は ""）を、在るファイルのパスの字に（ports.file。無いファイル・ほかの run の pointer は ValueError）"""
    import ports
    if value is None or value == "" or value == "null":
        return ""
    if isinstance(value, str) and value.strip().startswith("{"):
        value = json.loads(value)
    got = ports.file(json.dumps(value) if isinstance(value, dict) else str(value))
    return str(got) if got else ""


# ---------------------------------------------------------------- 指す先が無い・読めない控え（承認ノードの開ける理由にする）
UNREAD_KIND = "unread"   # 関所の項目の種類: 指す先のファイルが無いか読めない控え（読めないまま進めず、聞く側に倒す）
UNREAD_TAIL = "（読めないまま進めないので人に見せる）"


def located(value, what: str, unread: list) -> str:
    """pointer かパスの値を、在るファイルのパスの字に。null・空・"null" は ""。先のファイルが無ければ unread に「<what> の <先> が無い」を
    足して ""（設計した状態: 読めない控えは聞く側に倒す。docs/design/line.md の 2 節）。pointer の形の違い（object でない・型が違う・
    ほかの run の id・run directory の外を指す）は約束の誤りなので ValueError のまま（呼び手は落ちて works:line-script を返す）"""
    import ports
    if value is None or value == "" or value == "null":
        return ""
    if isinstance(value, str) and value.strip().startswith("{"):
        value = json.loads(value)
    if isinstance(value, dict):
        if value.get("type") != ports.POINTER_TYPE:
            raise ValueError(f"{what} の値が pointer の形でない（type {value.get('type')!r}）")
        run_id = os.environ.get("WORKFLOW_ID", "")
        if value.get("run_id") != run_id:
            raise ValueError(f"{what} の pointer がほかの run を指す: {value.get('run_id')!r}（この run は {run_id!r}）")
        path = ports.inside(value.get("path"), ports.place())   # line は include されないので place は run directory そのもの
        shown = value.get("path")
    elif isinstance(value, str):
        path = pathlib.Path(value.strip())
        path = path if path.is_absolute() else pathlib.Path.cwd() / path
        shown = value.strip()
    else:
        raise ValueError(f"{what} の値が pointer でもパスでもない（{type(value).__name__}）")
    if not path.is_file():
        unread.append(f"{what} の {shown} が無い")
        return ""
    return str(path)


def read_located(value, what: str, unread: list):
    """located の先の JSON。無い・JSON として読めなければ unread に訳を足して None（形の違う pointer は ValueError）"""
    path = located(value, what, unread)
    if not path:
        return None
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        unread.append(f"{what} の {path} が JSON として読めない（{type(error).__name__}）")
        return None


def unread_items(unread) -> list:
    """読めなかった控えの関所の項目 [(UNREAD_KIND, 文)]（同じ訳を 2 度載せない）"""
    return [(UNREAD_KIND, f"{row}{UNREAD_TAIL}") for row in dict.fromkeys(unread)]
