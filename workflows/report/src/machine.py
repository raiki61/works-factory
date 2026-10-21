"""機械の報告を組む（docs/design/report.md の 1.8。lib/runreport.py の build・head_lines・ask_counts・_apply_lines・apply_said・_apply_answer・
_bullets・fallback_report と lib/gatemarks.py の draft_line を、graph が渡す sections と facts で受ける形に写した物）。

- open_files(sections) -> (開いた節の並び, 開けない訳の行): 節の files の ref を ports の読み方で開けたパスにする
- build(sections, facts, outcome, stop_reason, run, *, place, run_id, run_why, repo, notes) -> {report, next_request, prior_failures,
  ai_go, decisions}: 機械の報告・次の依頼・前の失敗を place に書く。次の依頼と前の失敗は約束の Schema に合うことを照らしてから書く
- fallback_report(place, why) -> パス: 思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）を UNWRITTEN_FILE に書く
"""
import json
import pathlib

import carry     # lib/
import oneline   # lib/
import report    # lib/

import ports
from src import facts_in, files, outcome as outcomelib, transcript, writer

STOP_OUTCOMES = ("stopped_by_request", "stopped_by_human", "stopped_by_line", "needs_human")   # 止まった run の結末
HAPPENED = "起きたこと: "
APPLY_ASK = "差分を当ててよいか: "
DECIDE_HEAD = "人が決めること: "
URGENT_HEAD = "急ぎ: "
INFO_HEAD = "知らせ（決めることではない）: "
APPLY_HEAD = "差分を対象に当てる"
NO_DIFF = "当てる差分が無い（この run は差分を確定していない）"
APPLY_COMMAND = "保存した差分を対象に当てる命令"
STOPPED_FLAG = "（--allow-stopped は止まった run の差分を当てる指定）"
PR_MADE = "PR を作った: "
PR_STOPPED = "PR を作らずに止めた: "
PR_UNCONFIRMED = "PR を作ったと確かめられなかった: "
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
    """節の files の ref（Archon の pointer か、ファイルの絶対パスの字）を ports の読み方で開ける。{label, path} の path は開けたファイルの
    パスの字、開けなければ None と訳 why。返りは (files を開いた形にした節の並び, 開けない物の行 `ラベル（節の見出し）: 開けない（訳）`)"""
    out, unopened = [], []
    for section in sections:
        opened = []
        for item in section.get("files") or []:
            ref = item["ref"]
            try:
                path = ports.file(json.dumps(ref) if isinstance(ref, dict) else ref)
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


UNTOUCHED = {"pr": "PR を作っただけで、対象の既定の枝には当てていない", "stopped": "PR は作らず、対象の既定の枝には当てていない",
             "unconfirmed": "PR を作ったかは確かめられていないが、対象の既定の枝には当てていない"}


def urgent_said(apply: dict, outcome: str, run: dict) -> str:
    """冒頭の「急ぎ」の句。機械が持つ事実（落ちたノードが在るか・結末が記録の誤りか途中の終わりか・出口の語 pr の道の渡しの結果。
    run は対象に差分を当てない）だけで書く。run の記録が読めない時は事実が無いので空の字"""
    if not run.get("ok"):
        return ""
    untouched = UNTOUCHED.get(_dict(apply["pr"]).get("act"), "対象のリポジトリには何も当てていない")
    if run.get("failed") or run.get("absorbed"):
        return f"壊れた所がある——落ちたノードが在る。{untouched}"
    if outcome in ("record_invalid", "interrupted"):
        return f"壊れた所がある——結末が{report.OUTCOME_WORDS.get(outcome, outcome)}。{untouched}"
    return f"急ぎでない——壊れた所は無く、{untouched}"


def ask_rows(asks: list, counts: dict) -> list:
    """頭の種ごとの行。asks は [(種, 題)]（題は書いた所が本文と一緒に書いた短い題。無ければ空）。題の在る物は 1 件 1 行 `題（種の頭の言い方）`、
    題の無い物（古い記録・題を返さなかった役）は今の種の名に戻し、種ごとにまとめて `種`（2 件以上は `（n 件）`）。黙って行を落とさない"""
    rows, seen = [], set()
    for kind, title in asks:
        label = ask_label(kind)
        if title.strip():
            rows.append(f"- {title.strip()}（{label}）")
        elif label not in seen:
            seen.add(label)
            n = counts[label] - sum(1 for k, t in asks if ask_label(k) == label and t.strip())
            rows.append(f"- {label}" + (f"（{n} 件）" if n > 1 else ""))
    return rows


def head_lines(happened: str, apply: str, urgent: str, counts: dict, other: str, info: list, rows: list) -> list:
    """報告の冒頭（機械が組む）: 起きたこと・差分を当ててよいか・急ぎ（事実が在れば）・人が決めること（件数は和の 1 つ）の行と、その下に種ごとの行、
    最後に知らせだけの行。決める物が無ければ「人が決めること」の行に other（次に大事な事実）を置く（「無い」と断る決まり文句は書かない）。
    決める物の本文と種の訳は頭に出さない（見出しに「人が決めること」を持つセクションに在る）"""
    decide = (DECIDE_HEAD + f"{sum(counts.values())} 件（下の行は種類ごと。1 件ずつの本文は見出しに「{writer.DECISIONS_HEAD}」を持つセクション）"
              if counts else other)
    return [HAPPENED + happened, APPLY_ASK + apply, *([URGENT_HEAD + urgent] if urgent else []), decide, *rows, *[INFO_HEAD + x for x in info]]


def _apply_answer(apply: dict, outcome: str, run_id: str, decisions: int) -> str:
    if not apply["sealed"]:
        return NO_DIFF
    if not apply["placed"] and apply["redesign"]:
        return f"当てない（独立の目が {apply['redesign']} を言った run の差分は、{APPLY_COMMAND}: bin/apply も当てない）"
    command = f"{APPLY_COMMAND}: bin/apply {run_id}" + ("" if apply["placed"] else f" --allow-stopped{STOPPED_FLAG}")
    if decisions:
        return f"人が決めること {decisions} 件を決めてから当てる（{command}）"
    if not apply["placed"]:
        return f"差分を置かずに止まった run。止めた訳を確かめてから当てる（{command}）"
    if outcome in outcomelib.OK_OUTCOMES:   # 人の確かめが残る結末は、その残りを人が決める物に数えて上で返る
        return f"当ててよい（{command}）"
    return f"確かめてから当てる（結末が「{report.OUTCOME_WORDS.get(outcome, outcome)}」。{command}）"


def apply_said(apply: dict, outcome: str, run_id: str, decisions: int) -> str:
    """冒頭の 2 行目の「差分を当ててよいか」の答え。出口の語 pr の run は、頭に PR を作ったか・作らずに止めた訳・作ったと確かめられなかった訳を言う"""
    pr = _dict(apply["pr"])
    if pr.get("act") == "pr":
        kind = "下書きの PR" if pr.get("is_draft") else "PR"
        return f"{PR_MADE}{pr.get('url')}（{kind} #{pr.get('number')}。merge は対象のレビューと決まりに任せる）"
    said = _apply_answer(apply, outcome, run_id, decisions)
    head = {"stopped": PR_STOPPED, "unconfirmed": PR_UNCONFIRMED}.get(pr.get("act"))
    if head:
        return f"{head}{oneline.one_line(pr.get('reason') or '訳の記録が無い')}。{said}"
    return said


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
    """結末で決まる人が決める物の塊: 種ごとに `{種}: {n} 件` と `  - {文}`"""
    lines = []
    for kind in dict.fromkeys(k for k, _ in rows):
        items = [text for k, text in rows if k == kind]
        lines.append(f"{kind}: {len(items)} 件")
        lines += [f"  - {text}" for text in items]
    return lines


# ---------------------------------------------------------------- 機械の報告
def _stop_section(facts: dict, outcome: str, stop_reason: str, run: dict, said: list) -> list:
    out = [f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", f"止めた段と理由の語: {stop_reason or '止めていない'}",
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
    asks = [(a["kind"], a["text"]) for a in facts["asks"]] + own
    titles = [(a["kind"], a.get("title") or "") for a in facts["asks"]] + [(k, "") for k, _ in own]
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
    head = facts["head"]
    said = [*head["before"], *(head["stopped"] if outcome in STOP_OUTCOMES else [])]
    decisions = sum(counts.values())
    happened = "。".join([report.OUTCOME_WORDS.get(outcome, "結末が決まらない"),
                          *([f"人が決めること {decisions} 件が残っている"] if decisions else [])])
    top = head_lines(happened, apply_said(facts["apply"], outcome, run_id or "—", decisions), urgent_said(facts["apply"], outcome, run), counts,
                     other=f"次の run に渡す物: {n_carried} 件", info=head["after"], rows=ask_rows(titles, counts))
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
        (files.STOP_HEADING, _stop_section(facts, outcome, stop_reason, run, said)),
        (files.WHERE_HEADING, _where_lines(sections)),
        (files.CALLS_HEADING, transcript.calls_lines(run, run_why, repo)),
        *[(f"## {s['title']}", s["lines"] or [NO_LINES]) for s in sections],
        (files.PRIOR_HEADING, report.prior_lines(prior, next_file)),
        (files.MODEL_HEADING, [*transcript.node_model_lines(run), model_end]),
        (files.COST_HEADING, transcript.head_cost(run, run_why)),
        (files.NOTES_HEADING, [oneline.one_line(n) for n in note_rows] or ["無い"]),
    ]
    notices = [oneline.one_line(n) for n in head["notices"]]
    text = "\n\n".join([files.TITLE.format(run=run_id or "—") + "\n\n" + "\n".join(top),
                        *(["\n".join(notices)] if notices else []),
                        *(f"{h}\n\n" + "\n".join(bullets(lines)) for h, lines in body)]) + "\n"
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
