"""機械の報告を組む（docs/design/report.md の 1.8。元の runreport の build・head_lines・ask_counts・_apply_lines・apply_said・_apply_answer・
_bullets・fallback_report と lib/gatemarks.py の draft_line を、graph が渡す sections と facts で受ける形に写した物）。

- open_files(sections) -> (開いた節の並び, 開けない訳の行): 節の files の ref を ports の読み方で開けたパスにする
- build(sections, facts, outcome, stop_reason, run, *, place, run_id, run_why, repo, notes) -> {report, next_request, prior_failures,
  ai_go, decisions}: 機械の報告・次の依頼・前の失敗を place に書く。次の依頼と前の失敗は約束の Schema に合うことを照らしてから書く。
  頭の行は事実から head.Line と差し込み口の値を決めて head.render で描くだけ（文は head.py の表の 1 か所）。知らせの本文 text は notice_lines が
  節「2. 止めたか」の頭に並べる
- fallback_report(place, why) -> パス: 思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）を UNWRITTEN_FILE に書く
"""
import json
import pathlib

import carry     # lib/
import oneline   # lib/
import report    # lib/

import ports
from src import facts_in, files, head, outcome as outcomelib, transcript, writer

STOP_OUTCOMES = ("stopped_by_request", "stopped_by_human", "stopped_by_line", "needs_human")   # 止まった run の結末
APPLY_HEAD = "差分を対象に当てる"
NO_LINES = "この段は報告の行を返していない"
NO_POINTER = "出力にポインタが無い"
DRAFT_HEAD = "人の判断を待つ項目への答えの下書き"


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def bullets(lines: list) -> list:
    """節の行に「- 」を付ける（字下げした内訳の行はそのまま）"""
    return [r if r.startswith("  ") else f"- {r}" for r in lines]


# ---------------------------------------------------------------- 節の files
def open_files(sections: list) -> tuple[list, list]:
    """節の files の ref（Archon の pointer か、ファイルの絶対パスの字）を、行の form で中身を照らして開ける（ports.carried_file）。{label, path} の path は開けたファイルの
    パスの字、開けなければ None と訳 why。返りは (files を開いた形にした節の並び, 開けない物の行 `ラベル（節の見出し）: 開けない（訳）`)"""
    out, unopened = [], []
    for section in sections:
        opened = []
        for item in section.get("files") or []:
            try:
                path = ports.carried_file(item)
                if path is None:
                    raise ValueError("ref が空")
                opened.append({"label": item["label"], "path": str(path), "why": ""})
            except (ValueError, OSError) as e:
                why = oneline.one_line(e)
                opened.append({"label": item["label"], "path": None, "why": why})
                unopened.append(f"{item['label']}（{section['title']}）: 開けない（{why}）")
        out.append({**section, "files": opened})
    return out, unopened


def _where_lines(sections: list) -> list:
    rows = [f"{f['label']}（{s['title']}）: {f['path']}" if f["path"] else f"{f['label']}（{s['title']}）: 開けない（{f['why']}）"
            for s in sections for f in s.get("files") or []]
    return rows or [NO_POINTER]


# ---------------------------------------------------------------- 冒頭
def ask_label(kind: str) -> str:
    """人が決める物の種の頭の言い方（括弧の中の訳は、頭の下の節の種の行に在る）"""
    return kind.partition("（")[0]


def ask_counts(asks: list, tallied: dict) -> dict:
    """人が決める物の種（頭の言い方）ごとの件数（冒頭に並べる順）。tallied に在る種は行の数でなくその件数"""
    counts = {}
    for kind in dict.fromkeys(k for k, _ in asks):
        counts[ask_label(kind)] = counts.get(ask_label(kind), 0) + tallied.get(kind, sum(1 for x, _ in asks if x == kind))
    return counts


def _handover(apply: dict) -> head.Handover:
    """出口の語 pr の道の渡しの結果（run は対象に差分を当てない）。頭の急ぎの行の受け渡しの句を選ぶ"""
    return {"pr": head.Handover.PR, "stopped": head.Handover.STOPPED,
            "unconfirmed": head.Handover.UNCONFIRMED}.get(_dict(apply["pr"]).get("act"), head.Handover.NONE)


def urgent_said(apply: dict, outcome: str, run: dict) -> str:
    """冒頭の「急ぎ」の行。機械が持つ事実（落ちた段が在るか・結末が記録の誤りか途中の終わりか・出口の語 pr の道の渡しの結果）だけで選ぶ。
    機械は試験の外で対象が動くかを知らないので、段が落ちていなければ「確かめていない」と言う。run の記録が読めない時は事実が無いので空の字"""
    if not run.get("ok"):
        return ""
    handover = _handover(apply)
    if run.get("failed") or run.get("absorbed"):
        return head.render(head.Line.URGENT_FAILED, head.UrgentSlot(handover))
    if outcome in ("record_invalid", "interrupted"):
        return head.render(head.Line.URGENT_RECORD, head.UrgentEndSlot(head.Outcome(outcome), handover))
    return head.render(head.Line.URGENT_NEITHER, head.UrgentSlot(handover))


def ask_rows(asks: list, counts: dict) -> list:
    """頭の種ごとの行。asks は [(種, 題)]（題は書いた所が本文と一緒に書いた短い題、または機械が組む種の決まった字の題。無ければ空）。
    題の在る物は `題（種の頭の言い方）`。同じ種の同じ字の題（機械が組む種の決まった字。1 件ごとの値を差し込まない）は 1 行にまとめ、
    括弧の中に件数を添える（`題（種、n 件）`）。件数は、その種の行が全部その題ならその種の件数 counts（tallied に在る種は行の数でなくその件数）、
    そうでなければその題の行の数。題の無い物（古い記録・題を返さなかった役）は今の種の名に戻し、種ごとにまとめて `種`（2 件以上は `（n 件）`）。
    黙って行を落とさない"""
    titles = [(ask_label(kind), oneline.one_line(title)) for kind, title in asks]
    rows, seen = [], set()
    for label, title in titles:
        if title:
            if (label, title) in seen:
                continue
            seen.add((label, title))
            of_kind = [t for k, t in titles if k == label]
            n = counts[label] if all(t == title for t in of_kind) else of_kind.count(title)
            shown = head.OneLine(f"{label}、{n} 件") if n > 1 else head.OneLine(label)
            rows.append(head.render(head.Line.ASK_TITLED, head.TitledSlot(head.OneLine(title), shown)))
        elif label not in seen:
            seen.add(label)
            n = counts[label] - sum(1 for k, t in titles if k == label and t)
            rows.append(head.render(head.Line.ASK_KIND_COUNT, head.KindCountSlot(head.OneLine(label), n)) if n > 1
                        else head.render(head.Line.ASK_KIND, head.KindSlot(head.OneLine(label))))
    return rows


def notice_rows(items: list) -> list:
    """知らせの行（head.after・head.notices の要素 {kind, slots, text}）の頭の行。種の文だけで、本文 text は出さない。同じ行は 1 度だけ"""
    rows = []
    for item in items:
        kind = head.Notice(item["kind"])
        row = head.notice_row(kind, head.slots_of(kind, item["slots"]))
        if row not in rows:
            rows.append(row)
    return rows


def notice_lines(items: list) -> list:
    """知らせの本文 text（返りの訳を 1 行に畳んだ字）の節「2. 止めたか」の行 `<種の句>: <本文>`。本文の無い知らせ（利用者の環境）は出さない"""
    rows = [f"{head.NOTICE_TOPIC[head.Notice(item['kind'])]}: {oneline.one_line(item['text'])}" for item in items if str(item["text"]).strip()]
    return list(dict.fromkeys(rows))


def head_lines(run_id: str, outcome: str, apply: dict, run: dict, counts: dict, n_carried: int, notices: list, rows: list) -> list:
    """報告の冒頭（機械が組む。どの行も head.TABLE・head.NOTICES の行）: 題・起きたこと・差分を当ててよいか・急ぎ（事実が在れば）・人が決めること
    （件数は和の 1 つ）の行と、その下に種ごとの行、最後に知らせの行。決める物が無ければ「人が決めること」の行に次の run に渡す物の件数を置く
    （「無い」と断る決まり文句は書かない）。決める物の本文・止めた訳・知らせの本文は頭に出さない（節の見出しに「人が決めること」を持つセクションと、
    節「2. 止めたか」に在る）"""
    decisions = sum(counts.values())
    outcome_word = head.Outcome(outcome)
    happened = (head.render(head.Line.HAPPENED_WITH_ASKS, head.OutcomeAsksSlot(outcome_word, decisions)) if decisions
                else head.render(head.Line.WHAT_HAPPENED, head.OutcomeSlot(outcome_word)))
    decide = (head.render(head.Line.DECIDE, head.CountSlot(decisions)) if counts
              else head.render(head.Line.NEXT_RUN, head.CountSlot(n_carried)))
    urgent = urgent_said(apply, outcome, run)
    return [head.render(head.Line.RUN_TITLE, head.RunSlot(head.RunId(run_id))), "", happened, apply_said(apply, outcome, run_id, decisions),
            *([urgent] if urgent else []), decide, *rows, *notice_rows(notices)]


def apply_said(apply: dict, outcome: str, run_id: str, decisions: int) -> str:
    """冒頭の「差分を当ててよいか」の行。出口の語 pr の run は、PR を作った・作らずに止めた・作ったと確かめられなかったのどれかを言う
    （作らなかった訳は merge の節の 1 か所にだけ在る）"""
    pr, run = _dict(apply["pr"]), head.RunId(run_id)
    number = pr.get("number")
    number = int(number) if isinstance(number, str) and number.isdigit() else number
    if pr.get("act") == "pr" and pr.get("url") and isinstance(number, int) and not isinstance(number, bool):
        return head.render(head.Line.APPLY_PR_DRAFT if pr.get("is_draft") else head.Line.APPLY_PR, head.PrSlot(head.Url(pr["url"]), number))
    if pr.get("act") in ("pr", "unconfirmed"):   # PR を作ったと言いながら在りかか番号が読めない時も、作ったと言い切らない
        return head.render(head.Line.APPLY_PR_UNCONFIRMED, head.RunSlot(run))
    if pr.get("act") == "stopped":
        return head.render(head.Line.APPLY_PR_STOPPED, head.RunSlot(run))
    return _apply_answer(apply, outcome, run, decisions)


def _apply_answer(apply: dict, outcome: str, run: head.RunId, decisions: int) -> str:
    if not apply["sealed"]:
        return head.render(head.Line.APPLY_NO_DIFF)
    if not apply["placed"] and apply["redesign"]:
        return head.render(head.Line.APPLY_REFUSED)
    if decisions:
        return head.render(head.Line.APPLY_DECIDE_FIRST if apply["placed"] else head.Line.APPLY_DECIDE_FIRST_STOPPED,
                           head.DecideApplySlot(decisions, run))
    if not apply["placed"]:
        return head.render(head.Line.APPLY_NOT_PLACED, head.RunSlot(run))
    if outcome in outcomelib.OK_OUTCOMES:   # 人の確かめが残る結末は、その残りを人が決める物に数えて上で返る
        return head.render(head.Line.APPLY_OK, head.RunSlot(run))
    return head.render(head.Line.APPLY_CHECK_FIRST, head.CheckApplySlot(head.Outcome(outcome), run))


def apply_lines(apply: dict, outcome: str, stop_reason: str, run_id: str) -> list:
    """差分を対象に当てる 1 行。止まった run には止まりの 1 行（結末の語・止めた所・人の一言）と --allow-stopped の要ることを出す。
    生の git apply の行は出さない（止まった run の拒みを素通りさせない）"""
    if not apply["sealed"]:
        return [f"{APPLY_HEAD}: 無い（差分を封じていない）"]
    if apply["placed"]:
        return [f"{APPLY_HEAD}: bin/apply {run_id}（置いた差分の hash を封じた hash と照らしてから当てる）"]
    out = []
    if outcome in STOP_OUTCOMES:
        said = oneline.one_line(apply["said"]) if apply["said"] else "一言なし"
        out.append(f"止まった run: {report.OUTCOME_WORDS.get(outcome, outcome)}（{stop_reason or outcome}）で止まった: 「{said}」")
    if apply["redesign"]:
        return [*out, f"{APPLY_HEAD}: しない（R2 が {apply['redesign']} を言った run の差分は bin/apply も当てない）"]
    return [*out, f"{APPLY_HEAD}: bin/apply {run_id} --allow-stopped（差分を置かずに止まった run。止めの訳を確かめてから当てる）"]


def draft_line(drafts: list, next_file: str) -> str:
    """人が決めることのセクションの 1 行（下書きが無ければ空）"""
    if not drafts:
        return ""
    return (f"{DRAFT_HEAD}: {len(drafts)} 件——次の run の依頼の下書き{f' {next_file}' if next_file else ''} の answers に置いた"
            "（draft: true・出どころ source つき。機械は答えていない。推しの無い行は text が空で、材料は note に在る。見直して、台帳の"
            "問いと素材の行（question が問いの key か素材の名）は採るなら draft と source（と note）を消して text を答えにし、採らないなら行を消す。"
            "承認ノードの項目の行（question が承認ノードの項目の文）は次の run の承認ノードの continue の一言の材料で、"
            "依頼ではどの問いにも当たらないので、一言に写してから行を消す）")


def _asks_block(rows: list) -> list:
    """結末で決まる人が決める物の塊（outcome_asks の (種, 文, 題)）: 種ごとに `{種}: {n} 件` と `  - {文}`。題は頭の行に出る"""
    lines = []
    for kind in dict.fromkeys(k for k, _, _ in rows):
        items = [text for k, text, _ in rows if k == kind]
        lines.append(f"{kind}: {len(items)} 件")
        lines += [f"  - {text}" for text in items]
    return lines


# ---------------------------------------------------------------- 機械の報告
def _stop_section(facts: dict, outcome: str, stop_reason: str, run: dict, said: list, notices: list) -> list:
    out = [*notice_lines(notices), f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", f"止めた段と理由の語: {stop_reason or '止めていない'}",
           *said, *facts["stop_lines"]["before"]]
    if run.get("ok"):
        out += [f"{report.INTERRUPTED_HEAD}: ノード {s} が落ちた（誤り: {report._first_error({'error': (run.get('errors') or {}).get(s)})}）"
                for s in run.get("failed") or []]
        out += [f"子の run {c['child']} " + (f"の{c['why']}" if "why" in c else f"のノード {c['node']} が落ちた（誤り: {c['error']}）")
                for c in run.get("children") or []]
        out += [f"{report.RETRIED_HEAD}: {r['node']}（落ちた回 {r['failures']}。最後の誤り: {r['error'] or '（誤りの文が無い）'}）"
                for r in run.get("retried") or []]
        out += [f"{report.ABSORBED_HEAD}: {a['node']}（誤り: {report._first_error(a)}）" for a in run.get("absorbed") or []]
    out += facts["stop_lines"]["after"]
    return [*out, *[f"結果を名乗れない訳: {oneline.one_line(p)}" for p in facts["problems"]]]


def build(sections: list, facts: dict, outcome: str, stop_reason: str, run: dict, *, place, run_id: str = "", run_why: str = "",
          repo=None, notes=(), report_name: str = files.REPORT_FILE) -> dict:
    """機械の報告・次の依頼（next-request.json。空なら書かない）・前の失敗（prior-failures.json。空なら書かない）を place に書き、
    {report, next_request, prior_failures, ai_go, decisions} を返す。sections は open_files を通した節の並び、notes は開けない files の訳の行。
    notes（facts.notes の後ろ）と run の記録の読めなさが注意のセクションに載る"""
    place = pathlib.Path(place)
    place.mkdir(parents=True, exist_ok=True)
    left = outcomelib.left_all(facts, run)
    own = outcomelib.outcome_asks(outcome, facts, left)
    asks = [(a["kind"], a["text"]) for a in facts["asks"]] + [(kind, text) for kind, text, _ in own]
    titles = [(a["kind"], a.get("title") or "") for a in facts["asks"]] + [(kind, title) for kind, _, title in own]
    counts = ask_counts(asks, facts["tallied"])
    carried = facts["carry"]
    findings, prior, drafts, constraints = carried["findings"], carried["prior"], carried["drafts"], carried["constraints"]
    next_file = carry.NEXT_REQUEST_FILE if findings or drafts or constraints else ""
    n_carried = len(findings) + len(drafts) + len(constraints)

    doc = carry.compose(findings, prior, drafts, constraints)
    if next_file:   # 2 つとも照らしてから、報告も含めて何も書かない（片方だけ合わない時に、もう片方を残さない）
        errs = carry.errors(doc, carry.NEXT_SCHEMA)
        if errs:
            raise ValueError(f"次の依頼が約束の Schema に合わない: {errs}")
    if prior:
        errs = carry.errors(prior, carry.PRIOR_SCHEMA)
        if errs:
            raise ValueError(f"前の失敗が約束の Schema に合わない: {errs}")
    head_doc = facts["head"]
    said = [*head_doc["before"], *(head_doc["stopped"] if outcome in STOP_OUTCOMES else [])]
    notices = [*head_doc["after"], *head_doc["notices"]]
    decisions = sum(counts.values())
    top = head_lines(run_id or "—", outcome, facts["apply"], run, counts, n_carried, notices, ask_rows(titles, counts))
    parts = facts["outcome_parts"]
    model_end = "／".join(x for x in (f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", parts["gate"], parts["eyes"],
                                       f"次の run に渡す物: {n_carried} 件", f"持ち越した失敗: {len(prior)} 件", parts["data"]) if x)
    note_rows = [*facts["notes"], *notes, *([run_why] if not run.get("ok") and run_why else [])]
    dec = facts["decisions"]
    draft = draft_line(drafts, next_file)
    body = [
        (files.DECISIONS_HEADING, [*dec["before"], *_asks_block(own), *dec["after"],
                                   f"次の run に渡す物: {n_carried} 件" + (f"（{next_file}）" if next_file else ""), *dec["outside"],
                                   *[f"次の run の制約に足す実測（前提の検算）: {c['text']}" for c in constraints],
                                   *([draft] if draft else []), *apply_lines(facts["apply"], outcome, stop_reason, run_id or "—"),
                                   *facts["apply"]["commits"]]),
        (files.STOP_HEADING, _stop_section(facts, outcome, stop_reason, run, said, notices)),
        (files.WHERE_HEADING, _where_lines(sections)),
        (files.CALLS_HEADING, transcript.calls_lines(run, run_why, repo)),
        *[(f"## {s['title']}", s["lines"] or [NO_LINES]) for s in sections],
        (files.PRIOR_HEADING, report.prior_lines(prior, next_file)),
        (files.MODEL_HEADING, [*transcript.node_model_lines(run), model_end]),
        (files.COST_HEADING, transcript.head_cost(run, run_why)),
        (files.NOTES_HEADING, [oneline.one_line(n) for n in note_rows] or ["無い"]),
    ]
    text = "\n\n".join(["\n".join(top).rstrip(), *(f"{h}\n\n" + "\n".join(bullets(lines)) for h, lines in body)]) + "\n"
    paths = {"report": writer.write_text(place / report_name, text), "next_request": None, "prior_failures": None}
    if next_file:
        paths["next_request"] = place / next_file
        carry.write(paths["next_request"], doc)
    if prior:
        paths["prior_failures"] = place / carry.PRIOR_FAILURES_FILE
        carry.write(paths["prior_failures"], prior)
    return {**paths, "ai_go": outcome != "record_invalid", "decisions": decisions}


def fallback_report(place, why: str) -> pathlib.Path:
    """思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）を UNWRITTEN_FILE に書く（facts の report.md を上書きしない）。
    組めなければ誤りが上がり、呼び手がライブラリに頼らない訳だけのファイルに落ちる"""
    return build([], facts_in.read({"problems": [why]}), "record_invalid", f"report:{why}", transcript.facts(None), place=place,
                 report_name=files.UNWRITTEN_FILE)["report"]
