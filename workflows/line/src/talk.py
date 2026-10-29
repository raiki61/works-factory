"""設計の相談（対話モードの run の計画の往復の末尾。docs/design/line.md の 3.1 節。issue #822）。

対話モードは入力 design_talk が true で無人でない run（新しい旗は足さない）。計画の往復 plan-rounds の本体を
design-turn → plan → plan-review-run → plan-out → design-talk → gate-design（wait。本体の唯一の終わり）にし、往復が止まる周
（plan-out の done）で設計案と事前審査の結果を人に見せる。答えは止めた Archon（a972888a）の形のまま、次の周の頭の design-turn が
$LOOP_PREV.gate-design.output で読む（ASF の archon-plan・archon-attention と同じ。until_bash は飛びうる関所の出力を読まず、
design-talk の done だけを読む）。

- 合意（GO_WORDS）: 次の周は plan も事前審査も回さず、design-talk が前の周の返りを写して done にし、答えを agreed に置く。修正前の
  承認ノードは agreed を受けて、合意した行を聞き直さない（src.gates.before_fix）
- 修正要望（answer.REVISE と一言）: 一言を往復の記録の最後の往復に人の中央の block として差し込み（src.rounds.ask_again）、全部の項目を
  開き直した記録と、それを持つ plan の prior を書く。次の周の plan はその block に答え、事前審査が消えたか残ったかを照らす。一言は
  依頼の答えの行（ASK_NAME）としても plan と事前審査に渡す（往復の無い記録・計画の失敗の周にも届く）。一言が空なら設計し直さずに
  同じ文で聞き直す（未回答を承認と読まない。計画を回さずにループの周を使うので EMPTY_LIMIT 回まで。その次は止める）。往復の安全の上限（rounds.LIMIT）の周の修正要望は、設計し直さずに止める（plan-converge）
- 止める（STOP_WORDS と知らない語）: 次の周は回さず done にし、答えを agreed に置く（修正前の承認ノードが human:gate-design で止める）
- 相談の結果を返す: 直す義務が無い（nothing_owed）・計画ができなかった周も、done の周なら関所を開いて訳を見せる（黙って終わらない）
- 人の指摘の受け箱（issue #830。持ち主の決め `human-notes-in-rounds`）: 人は往復の間いつでも、受け箱（files.NOTES）に 1 行 1 つの指摘を
  足せる（待たない）。周の頭の design-turn が、前の周までに取った数より後の行を拾い、人の block（中央。頭が EDGE_HEAD の行だけ端）として
  往復の記録の最後の往復に差し込み（往復が無ければ依頼の答えの行だけ）、計画の役に答えさせ、事前審査に照らし直させる。往復が収まる周
  でも新しい指摘が在れば終えずに次の周で拾う。周の終わりの design-talk は、その周の設計（案・事前審査の穴と人の block・人の指摘への計画の
  役の答え）を files.TALK_ROUND に書いて在りかを告げる。受け箱の承認の行（頭が APPROVE_HEADS。指摘とは別の印）が在り、その後に新しい
  中央の指摘（人の行でも、審査役が後の往復で出した中央の block でも。端は数えない）が無ければ（approval）、止まる周に関所を開かず、承認を
  合意（agreed）として修正へ進む。ほかは止まる周に関所を開いて待つ

通常の run（対話モードでない）は design-turn が前の周の値をそのまま運び、design-talk が plan-out の返りをそのまま写す（関所はいつも
飛ぶ。往復の返りの欄は今と同じ値で、足した欄 open・text・asked・agreed・talks は空）。

段（stage）: 同じ周の頭と終わりを、計画の往復（PLAN。関所 gate-design）と設計の往復（THEME。テーマの run の設計の段の関所 gate-theme。
docs/design/line.md の 3.3 節）の 2 つの loop で使う。段ごとに違うのは関所の id・前の周の案の欄の名・答えの控えと往復の記録と周ごとの控えの
ファイル・依頼の答えの行の名・関所の文と項目（設計の段の物は src/themetalk.py）だけで、受け箱・承認の生き死に・revise・空の revise の
聞き直し・上限の周の止めは同じ決まり。受け箱は 2 つの段で 1 つ（取った行の数は設計の段から計画の段へ運ぶ。承認と出来事の並びは段ごとに
数え直す）。答え REDESIGN（設計へ戻す）は、テーマの run の計画の段でだけ止める答えと同じ道（agreed に置いて done）で受け、ほかの段・
ほかの run では設計し直さずに訳を添えて同じ文で聞き直す（空の revise と同じ数え）。

- dialogue(given) -> bool: 配る値から対話モードの run か
- PLAN・THEME: 段
- turn(...) -> dict: 周の頭 design-turn の返り
- settle(...) -> dict: 周の終わり design-talk の返り
- talk_text(...) -> str: 設計の相談の承認ノードの文
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

import answer
import gatemarks
import jsonfile
import oneline
import ports
import stopby

ASK_NAME = "設計の相談で人が求めた {n} 番目の直し"   # 依頼の答えの行の question（記録された方針の行の名指し）
KEY = "person-{n}"   # 往復の記録に差し込む人の block の key（converge.KEY_CHAR の字だけ）
TALK_FIELDS = ("open", "text", "asked", "agreed", "talks", "notes", "shown", "timeline")   # plan-out の返りに足す欄
NOTE_NAME = "設計の相談で人が入れた {n} 番目の指摘"   # 受け箱の指摘の依頼の答えの行の question（ASK_NAME と番号を分け合う）
NOTE_WHERE = "人の指摘の受け箱"   # 受け箱の指摘を差し込む人の block の where
EDGE_HEAD = "端:"   # 受け箱の行の頭がこの字なら、端（修正の段へ申し送れば済む細かい調整）の指摘として差し込む
UNPICKED_HEAD = "受け箱に入ったが、まだ計画の役に回していない指摘（{what}）:"   # 関所の文の末尾に、回していない受け箱の行の前に置く
CONSULT_AGREE = "修正へ進まずに報告を出す"   # 相談の結果の周に合意した時の結末の句（outcomes と相談の結果の行が同じ字を使う）
NOTES_ATTACHED = "受け箱に入った、まだ計画の役に回していない指摘:"   # 答えの一言・受け箱の承認の一言の後ろに足す見出し
# 承認の後に、前の往復で審査役が出して消えた中央の block が挙げ直された（ぶり返した）時に承認を取り消すか。持ち主の答えを待つ間は今の作り
# （取り消さない）。替える時はこの 1 か所（review_events が、ぶり返しを新しい中央の出来事として並べる）
REVIVED_CANCELS = False
APPROVE_HEADS = ("承認:", "もういいよ")   # 受け箱の行の頭がこのどれかなら、設計への承認（指摘でない。block にしない）
EMPTY_REVISE = "前の答え revise の一言が空だった（直してほしい所が分からないので設計し直していない）。直してほしい所を一言に書いて答え直す"
CAPPED_REVISE = "往復の安全の上限 {n} 周に届いたので設計し直せない（revise は止める答えと同じに扱う）"
EMPTY_LIMIT = 2   # 一言の空の revise で聞き直す回数の上限（計画を回さずにループの周を 1 つ使う。plan-rounds の max_iterations は rounds.LIMIT にこの数を足す）
EMPTY_CAPPED = ("一言の空の revise（か読めない答え）での聞き直しが {n} 回続いたので、もう聞き直さずに止める（直してほしい所を書いて新しい run で"
                "頼み直す）")
REDESIGN_ELSEWHERE = ("前の答え redesign（設計へ戻す）はテーマの run の計画の承認ノードでだけ選べる（この run には戻る設計の段が無い）。"
                      "設計し直させるなら revise と一言、止めるなら stop で答え直す")
REDESIGN_WAY = "修正へ進まずに run を閉じ、続きの run のテーマの md・依頼のファイル・起動の 1 行を書き出す（報告は出る）"
NO_ITEMS = "- （無し）"


class Stage(NamedTuple):
    """往復の段（周の頭と終わりを 2 つの loop で使い回す。モジュールの頭の docstring）"""
    name: str        # plan・theme
    gate: str        # 本体の唯一の終わりの承認ノードの id
    prior_key: str   # 周の頭と終わりの返りの、次の周の書き手に渡す前の周の案の欄の名
    ask_name: str    # 関所の revise の一言を依頼の答えの行にする時の question
    note_name: str   # 受け箱の指摘を依頼の答えの行にする時の question


PLAN = Stage("plan", "gate-design", "plan_prior", ASK_NAME, NOTE_NAME)
THEME = Stage("theme", "gate-theme", "prior_design", "設計の段で人が求めた {n} 番目の直し", "設計の段で人が入れた {n} 番目の指摘")


def stage_files(stage: Stage) -> tuple:
    """段の (答えの控え, 往復の記録, 周ごとの控え) のファイルの名（src.files）"""
    from src import files
    if stage.name == THEME.name:
        return files.THEME_ANSWERS, files.THEME_CONVERGE, files.THEME_ROUND
    return files.TALK_ANSWERS, files.PLAN_CONVERGE, files.TALK_ROUND


def theme_run(given: dict) -> bool:
    """テーマの run か（配る値の theme が空でない）"""
    return bool(str(given.get("theme") or "").strip())


def misplaced(said: dict, given: dict, stage: Stage) -> bool:
    """答えの語 REDESIGN が、受けられない所（テーマの run の計画の段でない）に来たか。選び肢は run ごとに変えられないので届きうる"""
    return said.get("decision") == answer.REDESIGN and not (stage.name == PLAN.name and theme_run(given))


def dialogue(given: dict) -> bool:
    return bool(given.get("design_talk")) and not bool(given.get("unattended"))


def _obj(raw):
    got = ports.parsed(raw)
    return got if isinstance(got, dict) else None


def _read(ptr, opened):
    """pointer の指すファイルの JSON。opened は pointer の字を宣言の form で照らしてパスを返す読み（ports.file）。pointer でない・無い・
    JSON として読めなければ None。形に合わない控えは飲まずに落とす（ShapeError）"""
    if not isinstance(ptr, dict):
        return None
    try:
        return json.loads(opened(json.dumps(ptr)).read_text(encoding="utf-8"))
    except ports.ShapeError:
        raise
    except (OSError, ValueError):
        return None


def _capped(po: dict) -> bool:
    """往復の安全の上限の周か（修正要望で設計し直せない）"""
    from src import rounds
    return (po.get("round") or 0) >= rounds.LIMIT or bool(po.get("capped"))


def _empties(talks: list) -> int:
    """聞き直した答えの数（一言の空の revise と、読めずに聞き直した答え〔欄 bad〕。計画を回さずに使ったループの周。周の番号とループの周の差）"""
    return sum(1 for t in talks if (t.get("decision") == answer.REVISE and not str(t.get("text") or "").strip()) or t.get("bad"))


def _pointer_or_null(value):
    return value if isinstance(value, dict) else None


def turn(*, answer_raw, previous_raw, last_raw, given: dict, recorded, place: Path, stage: Stage = PLAN, before=(), check=None) -> dict:
    """周の頭 design-turn。answer_raw は前の周の関所の出力（$LOOP_PREV.gate-design.output。1 周目と飛んだ周は空）、previous_raw は前の周の
    design-talk の返り、last_raw は前の周の自分の返り。返り {plan, answer, plan_prior, record, answers, recorded, asks, talks, notes, timeline,
    stop_reason, reason}: notes は受け箱の取った行（read_new がどの周でも新しい行を全部読む）、timeline は承認の生き死にを決める出来事の
    並び（受け箱の行・revise の一言。審査役の中央の block は周の終わりの settle が足す）、plan はこの周に plan と事前審査を回すか、plan_prior・record はこの周の plan と事前審査と plan-out の port prior（前の周の値。
    修正要望なら差し込んだ写し）、answers・recorded は依頼の答えと記録された方針の行に人の修正要望を足した物。stage は段（前の周の案の欄は
    stage.prior_key の名で返す）、before は 1 周目の前に前の段が取った受け箱の行（設計の段から計画の段へ運ぶ。取った行を 2 度読まない）、
    check は答え {decision, text} を読めるかの照らし（読めない訳か空の字。設計の段の text の見出しのセクション）。届かない redesign と読めない
    答えは、答えの欄 bad に訳を置き、設計し直さずに同じ文で聞き直す（空の revise と同じ数え EMPTY_LIMIT）"""
    from src import rounds
    answers_file = stage_files(stage)[0]

    prev, last = _obj(previous_raw), _obj(last_raw)
    asks = [a for a in (last or {}).get("asks") or [] if isinstance(a, dict)]
    talks = [t for t in (prev or {}).get("talks") or [] if isinstance(t, dict)]
    plan_prior = (prev or {}).get(stage.prior_key)
    if prev is not None and not isinstance(plan_prior, dict):   # 計画ができなかった周は prior を書かないので、その周が受けた prior を使い直す
        plan_prior = (last or {}).get(stage.prior_key)
    record = (prev or {}).get("record")
    out = {"plan": True, "answer": None, stage.prior_key: _pointer_or_null(plan_prior), "record": _pointer_or_null(record), "asks": asks,
           "talks": talks, "stop_reason": "", "reason": ""}
    taken = [str(t) for t in ((last or {}).get("notes") if last is not None else before) or []]
    timeline = [e for e in ((prev or {}).get("timeline") or (last or {}).get("timeline") or []) if isinstance(e, dict)]
    new = read_new(place, taken) if dialogue(given) else []   # 受け箱の新しい行は、どの周でもここで全部読む（読まない道を作らない）
    events = [event_of(line, n) for n, line in enumerate(new, len(taken))]
    taken += new
    placed = {e.get("n") for e in timeline if e.get("by") == "notes"}   # 前の周の終わりが、審査の前に並べ済みの行（2 度並べない）
    notes = [e for e in events if e["kind"] != APPROVE]   # 承認でない行（中央と端の指摘）
    got = ports.parsed(answer_raw)
    if got not in (None, "") and prev is not None:
        said = answer.decision(got)
        text = said["text"]
        if notes:   # 関所が開いている間に足された指摘は、答えの一言の後ろに付けて残す（合意なら修正役に、止めるなら報告に届く）
            text = "\n".join([t for t in (text.strip(), NOTES_ATTACHED, *(f"- {e['line']}" for e in notes)) if t])
        entry = {"round": prev.get("round"), "decision": said["decision"], "text": text,
                 "asked": [t for t in prev.get("asked") or [] if isinstance(t, str)]}
        bad = REDESIGN_ELSEWHERE if misplaced(said, given, stage) else check(said) if check is not None else ""
        if bad:
            entry["bad"] = bad
        talks.append(entry)
        out["answer"] = entry
        out["plan"] = False
        jsonfile.write(place / answers_file, talks, parents=True)
        timeline += [e for e in events if e["n"] not in placed]
        if bad:   # 届かない redesign・読めない答え: 設計し直さずに訳を添えて聞き直す（空の revise と同じ数え）
            if _empties(talks[:-1]) >= EMPTY_LIMIT:
                out.update(stop_reason=stopby.HUMAN + stage.gate, reason=EMPTY_CAPPED.format(n=EMPTY_LIMIT + 1))
            else:
                out["reason"] = bad
        elif said["decision"] == answer.REVISE:
            if not said["text"].strip() and not notes and _empties(talks[:-1]) >= EMPTY_LIMIT:
                out.update(stop_reason=stopby.HUMAN + stage.gate, reason=EMPTY_CAPPED.format(n=EMPTY_LIMIT + 1))
            elif not said["text"].strip() and not notes:
                out["reason"] = EMPTY_REVISE
            elif _capped(prev):
                out.update(stop_reason=stopby.word("plan-converge"), reason=CAPPED_REVISE.format(n=rounds.LIMIT))
            else:   # 一言と、関所の間に入った指摘で設計し直す（一言の空の revise も、指摘が在れば指摘で設計し直す）
                out["plan"] = True
                if said["text"].strip():
                    n = len(asks) + 1
                    asks.append({"n": n, "key": KEY.format(n=n), "round": prev.get("round"), "text": said["text"]})
                    out.update(_ask_again(place, key=KEY.format(n=n), text=said["text"], n=n, record=record, plan_prior=plan_prior,
                                          stage=stage))
                    timeline.append({"kind": CENTRAL, "by": "revise", "line": said["text"]})
                _put_notes(out, notes, asks=asks, place=place, record=record, plan_prior=plan_prior, round_=prev.get("round"), stage=stage)
    else:
        timeline += [e for e in events if e["n"] not in placed]
        if out["plan"]:
            _put_notes(out, notes, asks=asks, place=place, record=record, plan_prior=plan_prior, round_=(prev or {}).get("round"),
                       stage=stage)
    out["notes"] = taken
    out["timeline"] = timeline
    out["answers"] = [*_list(given.get("request_answers")), *({"question": _ask_name(a, stage), "text": a["text"]} for a in asks)]
    out["recorded"] = [*_list(recorded), *({"source": "answer", "name": _ask_name(a, stage), "text": a["text"]} for a in asks)]
    return out


def _ask_name(a: dict, stage: Stage = PLAN) -> str:
    return (stage.note_name if a.get("note") else stage.ask_name).format(n=a["n"])


APPROVE, CENTRAL, EDGE = "approve", "central", "edge"   # 並び（timeline）の出来事の種類


def event_of(line: str, n: int | None = None) -> dict:
    """受け箱の 1 行を並びの出来事 {kind, by: notes, line, n} に（頭が APPROVE_HEADS なら承認、EDGE_HEAD なら端、ほかは中央。n は受け箱の
    行の位置で、同じ行を並びに 2 度足さないための印）"""
    kind = APPROVE if line.startswith(APPROVE_HEADS) else EDGE if line.startswith(EDGE_HEAD) else CENTRAL
    return {"kind": kind, "by": "notes", "line": line, "n": n}


def review_events(doc: dict, timeline: list) -> list:
    """往復の記録 doc の往復に初めて出た、審査役の中央の block（人の block は受け箱と revise の出来事で並んでいるので除く）のうち、まだ
    並び timeline に無い物を、出た順の出来事 {kind: central, by: review, key, pass} にする（pass は出た往復の位置）。前の往復に在った block の
    挙げ直しは新しくない。ただし REVIVED_CANCELS が真なら、直前の往復で消えていた block の挙げ直し（ぶり返し）も出来事にする。
    呼び手 settle は計画を回した周ごとに、その周の往復が足された所で呼ぶ（往復が出た順に並べる）"""
    from src import rounds
    passes = doc.get("passes") or []
    have = {(e.get("key"), e.get("pass")) for e in timeline if e.get("by") == "review"}
    seen, before, out = set(), set(), []
    for i, p in enumerate(passes):
        people = {f.get("key") for f in p.get("faces") or [] if f.get("kind") == rounds.PERSON_KIND}
        for key in rounds.central_keys(passes, p.get("blocks") or []):
            fresh = key not in seen or (REVIVED_CANCELS and key not in before)
            if fresh and key not in people and (key, i) not in have:
                out.append({"kind": CENTRAL, "by": "review", "key": key, "pass": i})
                have.add((key, i))
        before = set(p.get("blocks") or [])
        seen.update(before)
    return out


def approval(timeline: list) -> str | None:
    """並び timeline（人の受け箱の行・revise の一言・審査役の中央の block を出た順に並べた 1 本）の上で、生きている承認の一言。最後の承認
    より後に中央の出来事が在れば取り消されたと見て None（出し手を問わない。端は数えない。持ち主の決め human-notes-in-rounds）"""
    said = None
    for e in timeline:
        if e.get("kind") == APPROVE:
            line = str(e.get("line") or "")
            said = next((line.removeprefix(h).strip() for h in APPROVE_HEADS if line.startswith(h)), "")
        elif e.get("kind") == CENTRAL:
            said = None
    return said


def read_new(place: Path, taken: list) -> list:
    """受け箱の、取った行の数 taken より後の行（読む口はここ 1 つ。周の頭も周の終わりもこれで読む）"""
    return read_notes(place)[len(taken):]


def _put_notes(out: dict, notes: list, *, asks: list, place: Path, record, plan_prior, round_, stage: Stage = PLAN) -> None:
    """受け箱の指摘を人の block として往復の記録に差し込み（中央。端の行は端）、依頼の答えの行の材料 asks に足す（out を書き換える）"""
    from src import rounds
    for e in notes:
        edge = e["kind"] == EDGE
        text = e["line"].removeprefix(EDGE_HEAD).strip() if edge else e["line"]
        n = len(asks) + 1
        asks.append({"n": n, "key": KEY.format(n=n), "round": round_, "text": text, "note": True})
        out.update(_ask_again(place, key=KEY.format(n=n), text=text, n=n, record=out["record"] or record,
                              plan_prior=out[stage.prior_key] or plan_prior, reach=rounds.PERIPHERAL if edge else rounds.PERSON_REACH,
                              where=NOTE_WHERE, stage=stage))


THEME_AGREE = "承認した設計の変える所を依頼の行にして、判定と計画の往復へ降りる"   # 設計の段の合意の結末の句


def outcomes(po: dict, *, notes: bool = False, stage: Stage = PLAN) -> dict:
    """この周の関所に答えた時に実際に起きること（答え方の文と、回していない指摘の案内は、どれもこの値から組む。周の種類ごとに字を書き分けない）。
    agree・revise・stop: 合意・設計し直し・止めるの結末の句。notes は回していない受け箱の指摘が在るか（在れば、それが答えでどうなるかの句 held）"""
    capped, consult = _capped(po), bool(_consult_row(po))
    agree = CONSULT_AGREE if consult else THEME_AGREE if stage.name == THEME.name else "修正・試験・レビューへ進む"
    revise = ("設計し直さずに止める（往復の安全の上限の周。報告は出る）" if capped else
              "一言を事前審査の block として計画の役に返し、事前審査をやり直して、もう一度ここで聞く（一言が空なら聞き直す）")
    out = {"agree": agree, "revise": revise, "stop": "止める（報告は出る）", "capped": capped}
    if notes:
        out["held"] = (f"合意すると、この指摘は答えの一言に付けて残り（{agree}。計画には入らない）、"
                       + ("revise は止める答えになる" if capped else
                          "revise すると、一言が空でもこの指摘を計画の役に返して設計し直す（一言に書き写さなくてよい）")
                       + "。止めると報告に残る")
    return out


def read_notes(place: Path) -> list:
    """人の指摘の受け箱（files.NOTES）の空でない行（無い・読めなければ []。人が書く字のファイルなので形は照らさない）"""
    from src import files
    try:
        text = (place / files.NOTES).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _list(value) -> list:
    got = ports.parsed(value) if isinstance(value, str) else value
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


def _ask_again(place: Path, *, key: str, text: str, n: int, record, plan_prior, reach: str = "", where: str = "",
               stage: Stage = PLAN) -> dict:
    """人の修正要望を往復の記録に差し込み（往復が在れば）、記録と plan の prior の写しを書いて {record, plan_prior} の pointer を返す。
    設計の段の前の周の案（設計の案）は往復の記録を持たないので写さない"""
    from src import files, rounds
    out = {}
    if isinstance(record, dict):
        doc = rounds.ask_again(rounds.read(ports.file(json.dumps(record), "json(shared:plan-converge.schema.json)")), key=key, text=text,
                               reach=reach or rounds.PERSON_REACH, where=where or (rounds.PERSON_WHERE if stage.name == PLAN.name else
                                                                                   f"設計の相談の承認ノード（{stage.gate}）"))
        out["record"] = ports.pointer(rounds.write(place / stage_files(stage)[1], doc), "json(shared:plan-converge.schema.json)")
        if isinstance(plan_prior, dict) and stage.name == PLAN.name:
            prior = json.loads(ports.file(json.dumps(plan_prior), "json(shared:plan-prior.schema.json)").read_text(encoding="utf-8"))
            written = jsonfile.write(place / files.PLAN_TALK.format(n=n), {**prior, "record": doc}, parents=True)
            out["plan_prior"] = ports.pointer(written, "json(shared:plan-prior.schema.json)")
    return out


def settle(*, turn_got: dict, plan_out: dict | None, previous: dict | None, given: dict, materials, run_id: str,
           place: Path | None = None, stage: Stage = PLAN) -> dict:
    """周の終わり design-talk。turn_got は design-turn の返り、plan_out は plan-out の返り（回さなかった周は None）、previous は前の周の
    design-talk の返り、materials は修正前の承認ノードの材料を読む口（rounds → before_fix の材料。src.asking.materials を包んだ物）。
    返りは plan-out の返りの欄と TALK_FIELDS"""
    from src import gates, rounds

    if turn_got.get("plan"):
        if plan_out is None:   # plan の include が落ちて plan-out が飛んだ: 計画ができなかった形で止める（輪を落とさない）
            return {**failed(stage), **talk_fields(turn_got)}
        out = {**plan_out, **talk_fields(turn_got)}
        if not dialogue(given):
            return out
        # 並べる順: まず、この周の計画が回っている間に受け箱へ入った行（この周の審査を見ずに書かれた物）、その後にこの周の審査役の block
        start = len(turn_got.get("notes") or [])
        fresh = [event_of(line, n) for n, line in enumerate(read_new(place, turn_got.get("notes") or []) if place is not None else [], start)]
        placed = {e.get("n") for e in out["timeline"] if e.get("by") == "notes"}
        timeline = [*out["timeline"], *(e for e in fresh if e["n"] not in placed)]
        timeline += review_events(_record(plan_out), timeline)
        out["timeline"] = timeline
        if place is not None:
            out["shown"] = show_round(plan_out, place=place, stage=stage)
        if not plan_out.get("done"):
            return out
        held = [e for e in fresh if e["kind"] != APPROVE]   # まだ計画の役に回していない指摘
        if held and (plan_out.get("ok") or plan_out.get("stalled")) and not _capped(plan_out):
            return {**out, "done": False}   # 収まる周でも新しい人の指摘が在れば、次の周の頭が拾って計画の役に答えさせる
        consult = _consult_row(plan_out)
        said = approval(timeline)
        # 承認は往復が収まった周にだけ当てる（相談の結果を見せる周と、回せない中央の指摘が在る周は関所を開く。黙って終わらない）
        # 設計の段は、最後の設計の案に持ち主に聞く問いが残れば承認が生きていても関所を開く（推しを黙って採らない）
        if not consult and not any(e["kind"] == CENTRAL for e in fresh) and said is not None and not _open_asks(plan_out, stage):
            if held:   # 承認で進む周に入った端の行は、承認の一言の後ろに付けて修正役に届ける（黙って落とさない）
                said = "\n".join([t for t in (said, NOTES_ATTACHED, *(f"- {e['line']}" for e in held)) if t])
            agreed = {"round": plan_out.get("round"), "decision": "approve", "text": said, "asked": [], "by": "notes"}
            return {**out, "agreed": agreed, "talks": [*out["talks"], agreed]}
        doc = None
        ways = outcomes(plan_out, notes=bool(held), stage=stage)
        if stage.name == THEME.name:
            from src import themetalk
            items = [(gatemarks.DESIGN_ONLY_KIND, consult)] if consult else themetalk.items(plan_out)
            text = themetalk.gate_text(plan_out, items, run_id=run_id, consult=bool(consult), ways=ways)
        else:
            if consult:
                items = [(gatemarks.DESIGN_ONLY_KIND, consult)]
            else:
                kw = materials(plan_out)
                doc = kw["record_doc"] if kw["record_doc"] is not None else rounds.fresh()   # 材料が読めないと名指した記録を読み直さない（unread の行が関所に届く）
                items = gates.before_fix(plan_out, unattended_run=False, design=False, **kw)["items"]
            text = talk_text(plan_out, items, run_id=run_id, consult=bool(consult), doc=doc, ways=ways, back=theme_run(given))
        if held:   # まだ計画の役に回していない受け箱の行と、答えでそれがどうなるか
            text += "\n" + "\n".join([UNPICKED_HEAD.format(what=ways["held"]), *(f"- {e['line']}" for e in held)]) + "\n"
        return {**out, "done": False, "open": True, "text": text, "asked": [t for _, t in items]}
    base = {k: v for k, v in (previous or failed(stage)).items() if k not in TALK_FIELDS}
    said = turn_got.get("answer") or {}
    if turn_got.get("stop_reason"):   # 上限の周の修正要望・空の revise の続き・周の頭の落ち: 設計し直さずに止める
        why = "。".join(t for t in (str(turn_got.get("reason") or ""), f"人の一言: {said['text']}" if said.get("text") else "") if t)
        return {**base, **talk_fields(turn_got), "done": True, "stop_reason": turn_got["stop_reason"],
                "agreed": {**said, "text": why} if said else None}
    if said.get("decision") == answer.REVISE or said.get("bad"):   # 一言の空の修正要望・読めない答え: 同じ文で聞き直す
        again = str((previous or {}).get("text") or "")
        for t in (previous or {}).get("talks") or []:   # 前に添えた訳を外す（訳を重ねない）
            if isinstance(t, dict) and t.get("bad"):
                again = again.removeprefix(f"{t['bad']}\n\n")
        again = again.removeprefix(f"{EMPTY_REVISE}\n\n")
        return {**base, **talk_fields(turn_got), "done": False, "open": True, "text": f"{turn_got.get('reason')}\n\n{again}",
                "asked": list((previous or {}).get("asked") or [])}
    return {**base, **talk_fields(turn_got), "done": True, "agreed": said or None}


def talk_fields(turn_got: dict) -> dict:
    """TALK_FIELDS の閉じた値（関所を開かない周の欄。talks は周の頭が運んだ物）"""
    return {"open": False, "text": "", "asked": [], "agreed": None, "talks": list(turn_got.get("talks") or []),
            "notes": [str(t) for t in turn_got.get("notes") or []], "shown": "",
            "timeline": [e for e in turn_got.get("timeline") or [] if isinstance(e, dict)]}


def _open_asks(po: dict, stage: Stage) -> bool:
    """設計の段で、最後の設計の案に持ち主に聞く問いが残っているか（計画の段はいつも偽）"""
    if stage.name != THEME.name:
        return False
    from src import themetalk
    return bool(themetalk.design_asks(po))


OPTIONAL = ("pointed",)   # failed の欄のうち plan-out の返りに無くてよい物（plan-out の output_format で required でない）


def failed(stage: Stage = PLAN) -> dict:
    """計画ができなかった形の plan-out の返り（plan-out の落ちた時・plan-out が飛んだ周・design-talk の落ちた時。欄の名の正本）。
    設計の段は theme-out の返りの形（src.themetalk.failed）"""
    from src import guard
    if stage.name == THEME.name:
        from src import themetalk
        return themetalk.failed()
    return {"done": True, "ok": False, "status": "failed", "round": 0, "plan_prior": None, "record": None, "plan": None, "fix_plan": None,
            "reply": None, "handoffs": [], "ripple": None, "owed": [], "gave_up": None, "stalled": False, "capped": False, "review": None,
            "asks": [], "deviations": [], "review_status": "", "review_reason": "", "stop_reason": guard.LINE_SCRIPT, "pointed": []}


def _consult_row(po: dict) -> str:
    """直す義務が無い・計画ができなかった周の相談の結果の行（修正前の承認ノードが開かずに修正へ進まない周。ほかは空）"""
    from src import gates
    if po.get("status") == "nothing_owed":
        return f"相談の結果: 直す義務の単位が無い（{po.get('status')}）。合意すると{CONSULT_AGREE}"
    if not po.get("ok") and not po.get("stalled") and not gates.review_fell_row(po):
        why = po.get("review_reason") or po.get("stop_reason") or "訳が返っていない"
        return f"相談の結果: 設計案を作れなかった（{po.get('status') or 'failed'}）: {why}。合意すると{CONSULT_AGREE}"
    return ""


def plan_lines(po: dict) -> list:
    """設計案の行（修正案の項目ごとに、単位・やり方・書く所）。案の控えが無い・読めなければその訳の 1 行"""
    bare = _read(po.get("fix_plan"), lambda raw: ports.file(raw, "json(shared:fix-plan.schema.json)"))
    fields = _read(po.get("plan"), lambda raw: ports.file(raw, "json(shared:plan-fields.schema.json)"))
    items = bare.get("plan") if isinstance(bare, dict) else None
    if not isinstance(items, list) or not items:
        return ["- （設計案の控えが無い。下の相談の結果を見る）"]
    works = fields.get("fields") if isinstance(fields, dict) and isinstance(fields.get("fields"), list) else []
    out = []
    for n, it in enumerate(items, 1):
        it = it if isinstance(it, dict) else {}
        w = works[n - 1] if n <= len(works) and isinstance(works[n - 1], dict) else {}
        units = "、".join(str(k) for k in it.get("unit_keys") or [])
        out.append(f"- 項目 {n}（{units}）: {oneline.one_line(str(it.get('approach') or '（やり方が無い）'))}")
        if w.get("allowed_paths") or w.get("route"):
            out.append(f"  - 書く所: {'・'.join(str(p) for p in w.get('allowed_paths') or []) or '（無い）'}・直し方: {w.get('route') or '（無い）'}")
    return out


def _record_of(ptr) -> dict:
    """往復の記録の pointer の中身（pointer でなければ往復の無い記録）。読めない・形の違う記録は往復の無い記録にすり替えず、理由を名指して
    落とす（src.rounds.read。設計の相談の節は落ちて止まる）"""
    from src import rounds
    return rounds.read(ports.file(json.dumps(ptr), "json(shared:plan-converge.schema.json)")) if isinstance(ptr, dict) else rounds.fresh()


def _record(po: dict) -> dict:
    return _record_of(po.get("record"))


def review_lines(po: dict, doc: dict) -> list:
    """事前審査の結果の行（往復の記録 doc の報告の行と、最後の往復の block の穴）"""
    from src import rounds
    if not doc["passes"]:
        status = po.get("review_status") or "（回っていない）"
        return [f"- 事前審査の往復の記録が無い（事前審査の状態: {status}" + (f"。訳: {po['review_reason']}" if po.get("review_reason") else "") + "）"]
    out = [f"- {line.strip()}" for line in rounds.lines(doc)]
    out += [f"- 最後の往復の block {f.get('key')}（{f.get('kind')}）: {oneline.one_line(str(f.get('why') or ''))}"
            for f in doc["passes"][-1].get("faces") or []]
    return out


def talk_text(po: dict, items: list, *, run_id: str, consult: bool, doc: dict | None = None, ways: dict | None = None,
              back: bool = False) -> str:
    """設計の相談の承認ノードの文: 冒頭 3 行 → 設計案 → 事前審査の結果 → 人が決める項目（合意で修正前に聞き直さない行）→ 答え方"""
    from src import gates, rounds
    k = po.get("round")
    doc = doc if isinstance(doc, dict) else _record(po)   # 材料が読んだ往復の記録（相談の結果だけの周は渡されないので読む）
    texts = [t for _, t in items]
    ways = ways or outcomes(po)
    lines = gatemarks.head3(
        f"設計の相談の承認ノード（{gates.TALK_GATE}）が開いた。計画の周 {k} の設計案と事前審査の結果を見せる"
        + ("（相談の結果だけ。修正へは進まない）" if consult else ""),
        "この設計で修正・試験・レビューへ進めてよいか（合意）、直してほしい所を一言に書いて設計し直させるか、止めるか（打つ行は末尾の答え方）",
        gatemarks.push_of(texts) if texts else
        f"人が決める項目は無い。事前審査の抜け方は {rounds.WORDS.get(doc.get('outcome'), 'まだ無い')}") + [""]
    lines += [f"設計案（計画の周 {k}）:", *plan_lines(po), "", "事前審査の結果:", *review_lines(po, doc), ""]
    lines += [f"人が決める項目（{len(texts)} 件。合意すると修正前の承認ノードでは聞き直さない）:", *([f"- {t}" for t in texts] or [NO_ITEMS]), ""]
    lines += ["答え方（依頼者に聞いて、その言葉で答える。答えるまで run は待つ）:",
              f"- 合意する: {answer.line(run_id, 'continue', '<通す範囲と条件>')}（{ways['agree']}。一言は run の記録 {gates.TALK_GATE} と"
              "修正前の答えに残り、修正役に届く。条件が無ければ approve でもよい）",
              f"- 設計し直させる: {answer.line(run_id, answer.REVISE, '<直してほしい所>', verbs=(*answer.VERBS, answer.REVISE))}（{ways['revise']}）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（{ways['stop']}）"]
    if back:   # テーマの run の計画の段だけ: 設計の欠けが見つかったら設計へ戻す（docs/design/line.md の 3.3 節）
        lines += [f"- 設計へ戻す（承認した設計そのものの欠けが見つかった時）: "
                  f"{answer.line(run_id, answer.REDESIGN, '<見つかった欠け>', verbs=(*answer.VERBS, answer.REVISE, answer.REDESIGN))}"
                  f"（{REDESIGN_WAY}）"]
    if any(kind in gatemarks.ASK_KINDS for kind, _ in items):   # 台帳の問いは合意の一言で答える（修正前の答えとして台帳が読む）
        lines += [f"- {gatemarks.ASK_GATE_HEAD}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 往復ごとの設計の控え（issue #830）
def person_answer_lines(doc: dict) -> list:
    """人の block（設計の相談の修正要望と受け箱の指摘）への計画の役の答えの行（往復の行の answers のうち key が人の block の物）"""
    from src import rounds
    people = {str(f.get("key")): f for p in doc.get("passes") or [] for f in p.get("faces") or [] if f.get("kind") == rounds.PERSON_KIND}
    out = []
    for p in doc.get("passes") or []:
        for a in p.get("answers") or []:
            if isinstance(a, dict) and str(a.get("key")) in people:
                why = oneline.one_line(str(people[str(a["key"])].get("why") or ""))
                out.append(f"- {a['key']}（{why}）: {a.get('handled') or '答えが無い'}——{oneline.one_line(str(a.get('how') or ''))}")
    return out


def round_text(po: dict, doc: dict, *, inbox: Path) -> str:
    """往復ごとの設計の控えの文: 頭 → 設計案 → 事前審査の結果（審査の穴と人の block）→ 人の指摘への答え → 指摘の入れ方"""
    from src import rounds
    k = po.get("round")
    word = rounds.WORDS.get(doc.get("outcome"), "まだ無い")
    lines = [f"# 計画の周 {k} の設計（対話モード。待たずに進んでいる）", "",
             f"事前審査の抜け方: {word}。指摘は下の入れ方でいつでも入れられ、次の周の頭で拾われる。", "",
             f"設計案（計画の周 {k}）:", *plan_lines(po), "", "事前審査の結果（審査の穴と人の指摘の block）:", *review_lines(po, doc), "",
             "人の指摘への計画の役の答え:", *(person_answer_lines(doc) or [NO_ITEMS]), "",
             "指摘の入れ方（1 行に 1 つ。設計のやり直しが要る指摘として扱う。端の細かい調整なら頭に「端:」を付ける。受け箱は足すだけで、"
             "前の行を消さない・直さない。工場は取った行の数で読み進めるので、消すと新しい行を飛ばし、直すと読み直さない）:",
             f"- printf '%s\\n' '<指摘>' >> {inbox}",
             "設計を承認して最後に待たずに修正へ進ませる（もういいよ）: 同じ受け箱に頭が「承認:」の行を足す。承認の後に中央の指摘を足すと"
             "承認は取り消され、往復が収まった所で聞いて待つ。往復が終わった後（修正へ進んだ後）に足した行は読まれない",
             f"- printf '%s\\n' '承認: <条件>' >> {inbox}"]
    return "\n".join(lines) + "\n"


def show_round(po: dict, *, place: Path, stage: Stage = PLAN) -> str:
    """その周の設計の控えを段の周ごとの控え（files.TALK_ROUND・THEME_ROUND）に書き、在りかを標準エラーに 1 行告げて、パスの字を返す
    （書けなければ空。往復は止めない）"""
    import sys
    from src import files
    path = place / stage_files(stage)[2].format(k=po.get("round") or 0)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if stage.name == THEME.name:
            from src import themetalk
            text = themetalk.round_text(po, _record(po), inbox=place / files.NOTES)
        else:
            text = round_text(po, _record(po), inbox=place / files.NOTES)
        path.write_text(text, encoding="utf-8")
    except OSError:
        return ""
    what = "設計の段: 設計の周" if stage.name == THEME.name else "設計の相談: 計画の周"
    print(f"{what} {po.get('round')} の設計を {path} に書いた。指摘は {place / files.NOTES} に 1 行ずつ足す", file=sys.stderr)
    return str(path)
