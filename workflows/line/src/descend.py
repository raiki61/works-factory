"""設計の段から計画の段へ降りる道と、計画の段から設計へ戻す道（docs/design/line.md の 3.3 節。設計の下書き
docs/plans/2026-10-27-design-stage.md の 2.2 の 7〜9・2.4・8 章）。

- descend(got, *, given, record, place) -> dict: theme-descend。設計の往復の返り got（theme-rounds-out の got）から、承認された設計の変える所を
  依頼の行に、関所の答えと推しを採った問いを依頼の答えの行にした依頼のファイル（files.THEME_DESCENDED）と、承認された設計の md の写し
  （files.THEME_APPROVED）を書く。人の居る run は関所の合意（agreed が通す語）だけで降り、止める答え・往復の止めは止めの語を返す。無人の
  run は関所の項目（src.themetalk.items）が無い時だけ降り（推しで進んだ印 answer.PUSHED を gates/gate-theme.json に残す）、項目が在れば
  src.gates.passage のとおり works:needs-human で止める。変える所が無ければ降りずに設計だけの結末（no_change）
- request_in(given, theme) -> dict: request-in。依頼の出どころを 1 つに選ぶ（テーマの run は theme-descend の返り、ほかの run は start の
  配る値）。判定から後ろは依頼をここからだけ読む
- dealt(given, request_raw) -> dict: 配る値の依頼の欄を request-in の返りの物に替えた写し（配る値まるごとを受ける script の読み口）
- back(rounds_got, *, given, record, descended, place, env) -> dict: theme-return。テーマの run の計画の承認ノードで redesign と答えた時だけ、
  続きの run のテーマの md・依頼のファイル・起動の 1 行を files.THEME_NEXT_DIR に書く
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path

import answer
import jsonfile
import oneline
import ports
import stopby

REQUEST_FIELDS = ("request", "request_file", "request_answers", "entry", "request_origin", "request_scope", "prior_rows")
APPROVED_Q = "設計の段で承認された設計"
ASK_Q = "設計の段の問い {id}"
TALK_Q = "設計の段の承認ノードの {n} 番目の答え（{decision}）"
OWNER = "持ち主の承認"
ROW_TEXT = "{what}（設計の段 {id}。部品 {parts}）"
NO_CHANGE = "承認された設計に変える所が無い（設計だけの結末。降りずに報告を出す）"
NO_ROUNDS = "設計の往復の返りが無い（設計の段が落ちたか飛んだ）"
ORIGIN = "設計の段で承認された設計（{path}）"
RESUME_RUN = " workflow run works-factory-line "
# 続きの run の起動の行に運ぶ、前の run の起動の入力（続きでも同じ値が要る物。設計の下書きの 14 章の 15）
CARRIED_INPUTS = ("test_cmd", "tdd_suite", "final_gate", "thickness", "features_off", "features_on", "policy_md", "lang", "spec", "deliver")


def _design(got: dict) -> dict | None:
    from src import themetalk
    return themetalk.design_of(got)


def _rows(design: dict) -> list:
    return [{"where": str(c.get("where") or ""), "text": ROW_TEXT.format(what=oneline.one_line(str(c.get("what") or "")), id=c.get("id"),
                                                                       parts="・".join(c.get("parts") or []) or "無し")}
            for c in design.get("changes") or [] if isinstance(c, dict)]


def _answers(design: dict, got: dict, given: dict, *, pushed: bool, approved: Path) -> list:
    """降りた依頼の answers: 依頼が先に持っていた答え → 関所の答え → 推しを採った問い → 承認された設計の在りか（question は重ねない）"""
    origin = answer.PUSHED_NOTE if pushed else OWNER
    out = [a for a in given.get("request_answers") or [] if isinstance(a, dict)]
    out += [{"question": TALK_Q.format(n=n, decision=t.get("decision")), "text": str(t.get("text") or "").strip() or "（一言なし）"}
            for n, t in enumerate((t for t in got.get("talks") or [] if isinstance(t, dict) and not t.get("bad")), 1)]
    out += [{"question": ASK_Q.format(id=a.get("id")), "text": f"{oneline.one_line(str(a.get('ask') or ''))}——推しの {a.get('pick')} を採った"
             f"（{origin}。答えの一言に別の案が在ればそれが先）"} for a in design.get("asks") or [] if isinstance(a, dict)]
    out.append({"question": APPROVED_Q, "text": f"承認された設計の md: {approved}（{origin}。計画はこの設計から外れない。外れは事前審査の中央の穴）"})
    seen, kept = set(), []
    for a in out:
        if a["question"] not in seen:
            seen.add(a["question"])
            kept.append(a)
    return kept


def _stopped(reason: str, word: str, said=None, *, notes=()) -> dict:
    return {"go": False, "stop_reason": word, "reason": reason, "answer": said, "no_change": False, "request": None, "request_file": "",
            "request_answers": [], "approved": "", "rows": 0, "notes": list(notes), "report": [f"設計の段: {reason}"]}


def descend(got, *, given: dict, place: Path) -> dict:
    from src import files, gates, talk, themetalk
    if not isinstance(got, dict):
        return _stopped(NO_ROUNDS, stopby.LINE_SCRIPT)
    notes = [str(n) for n in got.get("notes") or []]
    if got.get("stop_reason") and not isinstance(got.get("agreed"), dict):
        return _stopped(str(got.get("reason") or got["stop_reason"]), str(got["stop_reason"]), notes=notes)
    pushed = None
    if talk.dialogue(given):
        said = got.get("agreed") if isinstance(got.get("agreed"), dict) else None
        if said is None:
            return _stopped("設計の段の承認ノードの答えが無いまま往復が終わった", str(got.get("stop_reason") or stopby.LINE_SCRIPT), notes=notes)
        if said.get("decision") not in answer.GO_WORDS:
            word = str(got.get("stop_reason") or "") if said.get("decision") == answer.REVISE else ""
            return _stopped(f"人が設計の段の承認ノードで止めた（{oneline.one_line(str(said.get('text') or ''))}）",
                            word or stopby.HUMAN + talk.THEME.gate, said, notes=notes)
    else:
        rows = [t for _, t in themetalk.items(got)]
        if rows or not got.get("ok"):
            got_ = gates.passage(rows, gates.row_push) if rows else gates.Passage(False, stopby.NEEDS_HUMAN, [], None)
            why = "無人の run で、設計の段の承認ノードの項目に通す推しが無い（" + ("・".join(oneline.one_line(r) for r in rows) or "設計の往復が収まらなかった") + "）"
            return _stopped(why, got_.stop_reason or stopby.NEEDS_HUMAN)
        pushed = {"decision": answer.VERBS[0], "text": answer.PUSHED_NOTE + " 持ち主に聞く問いが残らず、設計の往復が収まった", answer.PUSHED: []}
        said = answer.taken(None, go=True, stop_reason="", place=talk.THEME.gate, folder=place, pushed=pushed)["answer"]
    design = _design(got)
    if design is None:
        return _stopped("承認された設計の案が読めない", stopby.LINE_SCRIPT, said, notes=notes)
    approved = place / files.THEME_APPROVED
    approved.parent.mkdir(parents=True, exist_ok=True)
    md = got.get("design_md")
    approved.write_text(ports.file(json.dumps(md), "file").read_text(encoding="utf-8") if isinstance(md, dict) else "", encoding="utf-8")
    rows = _rows(design)
    if not rows:
        return {**_stopped(NO_CHANGE, "", said, notes=notes), "no_change": True, "approved": str(approved)}
    answers = _answers(design, got, given, pushed=pushed is not None, approved=approved)
    request = jsonfile.write(place / files.THEME_DESCENDED, {"findings": rows, "answers": answers}, parents=True)
    rounds_n = got.get("round") if isinstance(got.get("round"), int) else 0
    return {"go": True, "stop_reason": "", "reason": "", "answer": said, "no_change": False,
            "request": ports.pointer(request, "json(shared:request.schema.json)"), "request_file": str(request), "request_answers": answers,
            "approved": str(approved), "rows": len(rows), "notes": notes,
            "report": [f"設計の段: 設計の往復 {rounds_n} 周・{'無人の run が推しで降りた（持ち主は承認していない）' if pushed else '持ち主が承認した'}"
                       f"・降りた依頼の行 {len(rows)} 行（承認された設計: {approved}）"]}


def request_in(given: dict, theme) -> dict:
    """依頼の出どころ（モジュールの頭の docstring）。返り {go, stop_reason, reason, REQUEST_FIELDS…, notes}"""
    base = {name: given.get(name) for name in REQUEST_FIELDS}
    if not str(given.get("theme") or "").strip():
        return {"go": True, "stop_reason": "", "reason": "", **base, "notes": []}
    if not isinstance(theme, dict):
        return {"go": False, "stop_reason": stopby.LINE_SCRIPT, "reason": NO_ROUNDS, **base, "notes": []}
    if not theme.get("go"):
        return {"go": False, "stop_reason": str(theme.get("stop_reason") or ""), "reason": str(theme.get("reason") or ""), **base,
                "notes": list(theme.get("notes") or [])}
    path = theme.get("request_file") or ""
    origin = ORIGIN.format(path=path)
    return {"go": True, "stop_reason": "", "reason": "", "request": theme.get("request"), "request_file": path,
            "request_answers": list(theme.get("request_answers") or []), "entry": origin, "request_origin": origin, "request_scope": True,
            "prior_rows": list(given.get("prior_rows") or []), "notes": list(theme.get("notes") or [])}


def dealt(given, request_raw) -> dict:
    """配る値 given の依頼の欄を、request-in の返り（request_raw）の物に替えた写し（配る値まるごとを受ける script が依頼を読む口。読めなければ
    ValueError。判定から後ろは依頼を request-in からだけ読む）"""
    got = ports.picked(request_raw, REQUEST_FIELDS)
    if got is None:
        raise ValueError("依頼の出どころ（request-in の返り）が読めない。with: の鍵の結びを確かめる")
    return {**(given if isinstance(given, dict) else {}), **{name: got[name] for name in REQUEST_FIELDS}}


# ---------------------------------------------------------------- 設計へ戻す（設計の下書きの 8.4）
def _gaps(rounds_got: dict) -> list:
    """計画の段の最後の往復で開いていた中央の穴の行（鍵と文）"""
    import converge
    from src import rounds
    ptr = rounds_got.get("record")
    if not isinstance(ptr, dict):
        return []
    doc = rounds.read(ports.file(json.dumps(ptr), "json(shared:plan-converge.schema.json)"))
    if not doc["passes"]:
        return []
    return [f"- {f.get('key')}: {oneline.one_line(str(f.get('why') or ''))}" for f in doc["passes"][-1].get("faces") or []
            if converge.central(f)]


def command(record: dict, request: Path, env=None) -> str:
    """続きの run の起動の 1 行（答えの行の頭の respond を run works-factory-line に替え、依頼と design_talk と前の run の入力を足す）"""
    inputs = record.get("inputs") if isinstance(record.get("inputs"), dict) else {}
    carried = [f"--input {name}={shlex.quote(str(inputs[name]))}" for name in CARRIED_INPUTS if str(inputs.get(name) or "").strip()]
    head = answer.head(env).replace(answer.RESPOND, RESUME_RUN, 1)
    return " ".join([head, f"--input request={shlex.quote(str(request))}", "--input design_talk=true", *carried])


def back(rounds_got, *, given: dict, record: dict, descended, place: Path, env=None) -> dict:
    from src import files
    agreed = (rounds_got or {}).get("agreed") if isinstance(rounds_got, dict) else None
    if not (isinstance(agreed, dict) and agreed.get("decision") == answer.REDESIGN):
        return {"back": False, "next": "", "command": "", "reason": "", "report": []}
    theme_path = Path(str(given.get("theme") or ""))
    approved = Path(str((descended or {}).get("approved") or ""))
    said = str(agreed.get("text") or "").strip() or "（一言なし）"
    parts = ["# テーマ（設計へ戻した続き）", "", "## 前の run のテーマ", "",
             theme_path.read_text(encoding="utf-8").strip() if theme_path.is_file() else "（読めない）", "",
             "## 前の run で承認した設計", "", approved.read_text(encoding="utf-8").strip() if approved.is_file() else "（読めない）", "",
             "## 計画の段で見つかった欠け（最後の往復で開いていた中央の穴）", "", *(_gaps(rounds_got) or ["- （無し）"]), "",
             "## 持ち主の一言（設計へ戻した答え）", "", said, ""]
    theme_md = place / files.THEME_NEXT_THEME
    theme_md.parent.mkdir(parents=True, exist_ok=True)
    theme_md.write_text("\n".join(parts), encoding="utf-8")
    answers = [a for a in (descended or {}).get("request_answers") or [] if isinstance(a, dict) and a.get("question") != APPROVED_Q]
    answers += [{"question": f"計画の段の承認ノードの {n} 番目の答え（{t.get('decision')}）", "text": str(t.get("text") or "").strip() or "（一言なし）"}
                for n, t in enumerate((t for t in rounds_got.get("talks") or [] if isinstance(t, dict) and not t.get("bad")), 1)]
    request = jsonfile.write(place / files.THEME_NEXT_REQUEST, {"findings": [], "theme": str(theme_md), "answers": answers}, parents=True)
    line = command(record, request, env)
    (place / files.THEME_NEXT_COMMAND).write_text(line + "\n", encoding="utf-8")
    return {"back": True, "next": str(theme_md.parent), "command": line, "reason": said,
            "report": [f"設計の段: 計画の承認ノードで設計へ戻した（{oneline.one_line(said)}）。続きの run の材料: {theme_md.parent}",
                       f"設計の段: 続きの run の起動の 1 行: {line}"]}
