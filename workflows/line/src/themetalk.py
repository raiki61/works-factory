"""設計の段の往復（テーマの run の loop theme-rounds。docs/design/line.md の 3.3 節。設計の下書き docs/plans/2026-10-27-design-stage.md の
2.2〜2.4・7 章）の、計画の往復と違う所だけ。周の頭と終わりの決め（受け箱・承認の生き死に・revise・空の revise・上限の周）は src.talk の
同じ口を段 THEME で使い、ここは設計の段の物だけを持つ。

- record(design, review, prior_raw, *, place) -> dict: 周の終わりの手前の theme-out（書き手の案と事前審査の形 theme の返答を往復の記録
  THEME_CONVERGE に足し、止め時を src.rounds.decide で決める。計画の往復の plan-out と同じ口）
- failed() -> dict: 設計の案ができなかった形の theme-out の返り（欄の名の正本）
- design_of(po)・design_asks(po): その周の設計の案と、持ち主に聞く問い
- items(po) -> [(種類, 文)]: 関所 gate-theme の項目（持ち主に聞く問い・往復の止まり・書き手か事前審査の諦めと落ち）。どの行も通す推しの尾を
  持たない（asks の pick は案の中の選びで、関所を通す推しではない。機械は推しを作らない）ので、無人の run は項目が 1 つでも在れば止まる
- gate_text(...)・round_text(...): 関所の文と周ごとの控えの文
- answer_rows(talks, request_answers=()) -> list: 人の答えの行（id H<n>。shared:human-answers.schema.json）。関所の答えの text の見出しの
  セクション（持ち主の言葉・調べもの・問いへの答え・取り次ぐ会話の読み）を行に分け、見出しの無い字は一言の行にする
- check(said, asks) -> str: 答えの text のセクションが読めるか（読めない訳か空の字。src.talk.turn の check）
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import answer
import gatemarks
import oneline
import ports

ASK_KIND = "theme_ask"        # 関所の項目の種類: 最後の設計の案に残った持ち主への問い
STUCK_KIND = "theme_stuck"    # 関所の項目の種類: 設計の往復が止まった（PERSISTED・UNSETTLED）か上限の周
GAVE_UP_KIND = gatemarks.GIVEN_UP_KIND   # 書き手か事前審査が諦めた・落ちた周
WRITER_FELL = {"gave_up": "設計の案の書き手の受け付けが諦めた: ", "failed": "設計の案の書き手が落ちた（案を作れていない）: "}
# 関所の答えの text の見出し（設計の下書きの 7.2）→ 人の答えの行の kind
HEADS = {"持ち主の言葉": "owner_words", "調べもの": "research", "問いへの答え": "ask_answer", "取り次ぐ会話の読み": "reading"}
ASK_LINE = re.compile(r"^(Q[0-9]+)\s*[:：=]\s*(A[0-9]+)\b\s*(.*)$")
BAD_HEAD = "答えの text の見出しのセクションが読めない: {why}。設計し直していない。直して答え直す"
REQUEST_ROW = "依頼の答え（{question}）: {text}"


def failed() -> dict:
    from src import guard
    return {"done": True, "ok": False, "status": "failed", "round": 0, "prior_design": None, "record": None, "design": None,
            "design_md": None, "review": None, "stalled": False, "capped": False, "review_status": "", "review_reason": "",
            "reason": "", "report": [], "stop_reason": guard.LINE_SCRIPT}


def _design(ptr):
    """書き手の block の返りの設計（pointer）の中身。読めなければ None"""
    if not isinstance(ptr, dict):
        return None
    try:
        return json.loads(ports.file(json.dumps(ptr), "json(shared:theme-design.schema.json)").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def design_of(po: dict) -> dict | None:
    got = _design((po or {}).get("design"))
    return got if isinstance(got, dict) else None


def design_asks(po: dict) -> list:
    got = design_of(po)
    return [a for a in (got or {}).get("asks") or [] if isinstance(a, dict)]


def record(design: dict, review: dict | None, prior_raw, *, place: Path) -> dict:
    """theme-out。design は書き手の block の返り（ok・status・design・design_md・reason・report。report はこの周の書き手の報告の行で、
    そのまま返して報告の「設計の段」の節に出す）、review は事前審査の返り（飛んだ周は None。
    ok・status・holes・reason）、prior_raw はこの周の往復の記録の pointer（1 周目は空）。事前審査が通った周は、返答（holes の先。faces と
    resolved）と書き手の block_answers で往復の行を THEME_CONVERGE に足す（項目の無い記録。往復の安全の上限の周は at_cap）。done は、
    書き手が ok でない・事前審査が ok でない・抜け方が降りる語（CLEAN・SETTLED）・止まった・上限の周、のどれか"""
    from src import files, rounds
    prior = ports.file(prior_raw, "json(shared:plan-converge.schema.json)") if ports.parsed(prior_raw) is not None else None
    doc = rounds.read(prior)
    k = len(doc["passes"]) + 1
    wrote = design.get("ok") is True and isinstance(design.get("design"), dict)
    reviewed = wrote and review is not None and review.get("ok") is True and isinstance(review.get("holes"), dict)
    if reviewed:
        holes = json.loads(ports.file(json.dumps(review["holes"]), "json(shared:plan-review-reply.schema.json)").read_text(encoding="utf-8"))
        drawn = json.loads(ports.file(json.dumps(design["design"]), "json(shared:theme-design.schema.json)").read_text(encoding="utf-8"))
        rounds.add_pass(doc, holes, answers=[a for a in drawn.get("block_answers") or [] if isinstance(a, dict)],
                        resolved=[r for r in holes.get("resolved") or [] if isinstance(r, str)], at_cap=k >= rounds.LIMIT)
    path = rounds.write(place / files.THEME_CONVERGE, doc)
    outcome = doc["outcome"] if reviewed else None
    stalled = outcome in rounds.STUCK
    done = not wrote or not reviewed or rounds.proceeds(outcome) or stalled or k >= rounds.LIMIT
    status = str(design.get("status") or "failed")
    return {"done": done, "ok": reviewed and rounds.proceeds(outcome), "status": status, "round": k,
            "prior_design": design["design"] if wrote else None, "record": ports.pointer(path, "json(shared:plan-converge.schema.json)"),
            "design": design.get("design") if wrote else None, "design_md": design.get("design_md") if wrote else None,
            "review": review.get("holes") if reviewed else None, "stalled": stalled, "capped": rounds.capped(doc),
            "review_status": "" if not wrote else str((review or {}).get("status") or "failed"),
            "review_reason": str((review or {}).get("reason") or "") if wrote else "",
            "reason": "" if wrote else str(design.get("reason") or "設計の案の書き手が訳を返していない"),
            "report": [str(x) for x in design.get("report") or []], "stop_reason": ""}


def _ask_row(a: dict) -> str:
    opts = "・".join(f"{o.get('id')} {oneline.one_line(str(o.get('what') or ''))}（得: {oneline.one_line(str(o.get('gain') or ''))}"
                     f"／代償: {oneline.one_line(str(o.get('cost') or ''))}）" for o in a.get("options") or [] if isinstance(o, dict))
    return (f"設計の問い {a.get('id')}: {oneline.one_line(str(a.get('ask') or ''))}／推し: {a.get('pick')}"
            f"（{oneline.one_line(str(a.get('pick_why') or ''))}）／案: {opts}")


def items(po: dict) -> list:
    """関所 gate-theme の項目（モジュールの頭の docstring）。無人の run はこの行を src.gates.passage に掛ける（設計の下書きの 2.4 の 2）"""
    from src import gates, rounds
    out = []
    fell = WRITER_FELL.get(str(po.get("status") or ""))
    if fell and not po.get("ok"):
        out.append((GAVE_UP_KIND, fell + (str(po.get("reason") or "").strip() or "（訳が返っていない）")))
    review = gates.review_fell_row(po)
    if review:
        out.append((GAVE_UP_KIND, review))
    if po.get("stalled") or po.get("capped"):
        doc = rounds.read(ports.file(json.dumps(po["record"]), "json(shared:plan-converge.schema.json)")) if isinstance(po.get("record"), dict) else rounds.fresh()
        out.append((STUCK_KIND, "設計の往復が止まった: " + (rounds.stuck_reason(doc) or "往復の安全の上限の周に届いた")))
    out += [(ASK_KIND, _ask_row(a)) for a in design_asks(po)]
    return out


def _design_lines(po: dict) -> list:
    d = design_of(po)
    if d is None:
        return ["- （設計の案の控えが無い。下の項目と事前審査の結果を見る）"]
    md = (po.get("design_md") or {}).get("path") if isinstance(po.get("design_md"), dict) else ""
    out = [f"- 全文（問い・前提・今在る物・設計・作り変えの照らし）: {md or '（無い）'}",
           f"- 問い: {oneline.one_line(str(d.get('question') or ''))}",
           f"- 前提: 人が決めた {sum(1 for p in d.get('premises') or [] if p.get('by') == 'owner')} 件・仮に置いた "
           f"{sum(1 for p in d.get('premises') or [] if p.get('by') == 'assumed')} 件"]
    out += [f"- 変える所 {c.get('id')}（{c.get('op')}）: {c.get('where')}——{oneline.one_line(str(c.get('what') or ''))}"
            for c in d.get("changes") or []]
    out += [f"- 部署の決め {r.get('id')}: {oneline.one_line(str(r.get('what') or ''))}（出どころ {r.get('by')}）" for r in d.get("decided") or []]
    return out


ANSWER_HOW = ["答えの text には、見出しのセクションを書いてよい（どれも無くてよい。見出しの無い字は一言として読む）:",
              "  ## 持ち主の言葉 ／ ## 調べもの ／ ## 問いへの答え（1 行に 1 つ「- Q1: A2（足し: …）」）／ ## 取り次ぐ会話の読み"]


def gate_text(po: dict, items_: list, *, run_id: str, consult: bool, ways: dict) -> str:
    """設計の段の承認ノードの文: 冒頭 3 行 → 設計の案（在りかと要約）→ 事前審査の結果 → 持ち主に聞く問いと項目 → 答え方"""
    from src import rounds, talk
    k = po.get("round")
    doc = talk._record(po)
    texts = [t for _, t in items_]
    lines = gatemarks.head3(
        f"設計の段の承認ノード（gate-theme）が開いた。設計の周 {k} の設計の案と事前審査の結果を見せる"
        + ("（相談の結果だけ。降りない）" if consult else ""),
        "この設計で計画の段へ降りてよいか（合意）、直してほしい所を一言に書いて設計し直させるか、止めるか（打つ行は末尾の答え方）",
        f"設計の案の推しは問いごとの「推し」。事前審査の抜け方は {rounds.WORDS.get(doc.get('outcome'), 'まだ無い')}") + [""]
    lines += [f"設計の案（設計の周 {k}）:", *_design_lines(po), "", "事前審査の結果（独立設計との差・世界の解との差を含む）:",
              *talk.review_lines(po, doc), ""]
    lines += [f"持ち主に聞く問いと項目（{len(texts)} 件。合意すると、答えの無い問いは推しを採る）:", *([f"- {t}" for t in texts] or [talk.NO_ITEMS]), ""]
    lines += ["答え方（依頼者に聞いて、その言葉で答える。答えるまで run は待つ）:",
              f"- 合意する: {answer.line(run_id, 'continue', '<条件と問いへの答え>')}（{ways['agree']}。見せた設計と、答えの無い問いは推しを"
              "採って合意する。条件が無ければ approve でもよい）",
              f"- 設計し直させる: {answer.line(run_id, answer.REVISE, '<直してほしい所>', verbs=(*answer.VERBS, answer.REVISE))}（{ways['revise']}）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（{ways['stop']}）", *ANSWER_HOW]
    return "\n".join(lines) + "\n"


def round_text(po: dict, doc: dict, *, inbox: Path) -> str:
    """設計の往復ごとの控え（待たずに進む周に書く。人が読む）"""
    from src import rounds, talk
    k = po.get("round")
    lines = [f"# 設計の周 {k} の設計の案（テーマの run。待たずに進んでいる）", "",
             f"事前審査の抜け方: {rounds.WORDS.get(doc.get('outcome'), 'まだ無い')}。指摘は下の入れ方でいつでも入れられ、次の周の頭で拾われる。", "",
             f"設計の案（設計の周 {k}）:", *_design_lines(po), "", "持ち主に聞く問い:",
             *([f"- {_ask_row(a)}" for a in design_asks(po)] or [talk.NO_ITEMS]), "",
             "事前審査の結果（審査の穴と人の指摘の block）:", *talk.review_lines(po, doc), "",
             "人の指摘への書き手の答え:", *(talk.person_answer_lines(doc) or [talk.NO_ITEMS]), "",
             "指摘の入れ方（1 行に 1 つ。設計のやり直しが要る指摘として扱う。端の細かい調整なら頭に「端:」を付ける。受け箱は足すだけ）:",
             f"- printf '%s\\n' '<指摘>' >> {inbox}",
             "設計を承認して最後に待たずに計画の段へ降りる: 頭が「承認:」の行を足す（持ち主に聞く問いが残っていれば、承認が在っても関所を開く）",
             f"- printf '%s\\n' '承認: <条件>' >> {inbox}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 人の答えの行（設計の下書きの 7.2。docs/design/theme.md の 7 章）
def _sections(text: str) -> list:
    """答えの text を (見出し, 本文の行) の並びに。見出しの前の字は見出し None"""
    out, head, body = [], None, []
    for line in str(text or "").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            out.append((head, body))
            head, body = m.group(1), []
        else:
            body.append(line)
    out.append((head, body))
    return [(h, [b for b in lines if b.strip()]) for h, lines in out if h is not None or any(b.strip() for b in lines)]


def _items(lines: list) -> list:
    """セクションの本文を行に（頭が「- 」の行が在れば箇条ごと、無ければ本文を 1 行に）"""
    bullets = [b.strip()[2:].strip() for b in lines if b.strip().startswith("- ")]
    return bullets if bullets else ["\n".join(b.strip() for b in lines)] if lines else []


def _ask_items(lines: list) -> list:
    """問いへの答えのセクションの本文を行に（1 行に 1 つ。頭の「- 」は有っても無くてもよい）"""
    return [b.strip()[2:].strip() if b.strip().startswith("- ") else b.strip() for b in lines]


def check(said: dict, asks: list) -> str:
    """答えの text の見出しのセクションが読めるか。読めない訳（知らない見出し・問いへの答えの行の形・見せた問いに無い Q・案に無い A）か空の字"""
    shown = {str(a.get("id")): {str(o.get("id")) for o in a.get("options") or [] if isinstance(o, dict)} for a in asks}
    for head, lines in _sections(said.get("text")):
        if head is None:
            continue
        if head not in HEADS:
            return BAD_HEAD.format(why=f"知らない見出し「{head}」（使えるのは {'・'.join(HEADS)}）")
        if HEADS[head] != "ask_answer":
            continue
        for row in _ask_items(lines):
            m = ASK_LINE.match(row)
            if m is None:
                return BAD_HEAD.format(why=f"問いへの答えの行「{row}」が「Q<n>: A<n>（足し）」の形でない")
            if m.group(1) not in shown:
                return BAD_HEAD.format(why=f"{m.group(1)} は見せた問いに無い（見せた問い: {'・'.join(shown) or '無し'}）")
            if m.group(2) not in shown[m.group(1)]:
                return BAD_HEAD.format(why=f"{m.group(1)} の案に {m.group(2)} が無い（案: {'・'.join(sorted(shown[m.group(1)]))}）")
    return ""


def answer_rows(talks: list, request_answers=()) -> list:
    """人の答えの行。依頼の answers（取り次ぐ会話が始めに依頼のファイルに書いた答え）を一言の行にし、続けて関所の答え（talks。読めずに聞き直した
    答えと止める答えは除く）の text をセクションごとの行にする。番号は通し"""
    rows = [{"kind": "note", "text": REQUEST_ROW.format(question=a.get("question"), text=a.get("text"))}
            for a in request_answers or [] if isinstance(a, dict) and str(a.get("text") or "").strip()]
    for t in talks:
        if not isinstance(t, dict) or t.get("bad") or t.get("decision") in answer.STOP_WORDS:
            continue
        for head, lines in _sections(t.get("text")):
            kind = HEADS.get(head, "note") if head is not None else "note"
            for row in _ask_items(lines) if kind == "ask_answer" else _items(lines):
                if kind == "ask_answer":
                    m = ASK_LINE.match(row)
                    rows.append({"kind": kind, "text": row, "ask": m.group(1), "pick": m.group(2)} if m else {"kind": "note", "text": row})
                elif row.strip():
                    rows.append({"kind": kind, "text": row})
    return [{"id": f"H{n}", **r} for n, r in enumerate(rows, 1)]
