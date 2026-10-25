"""script の node の中身（docs/design/report.md の 4 節）。scripts/ は ports.run でここを呼ぶだけの薄い皮にする。

- facts(place, *, sections, facts, lang, run_id, workflow_file, repo) -> 返り: port を読み、run の記録を読み、結末を決め、機械の報告・次の依頼・
  前の失敗を書く。読めない入力は落とさず、その訳を problems に足す（結末は record_invalid）
- write_prompt(place, *, run_id) / cold_prompt(place, raw): 書き手の指示と初見の読み手の指示を md から組む
- finish(place, *, run_id): 書き手のループが落ちた訳を機械の報告に置き、人に向けた報告と詳細のファイルを書き、出力を返す
- unwritten(place, name, why): ライブラリに頼らず訳だけの 1 ファイルを書く
"""
import json
import pathlib

import jsonfile   # lib/
import rolekit    # lib/
import report     # lib/
import carry      # lib/

import ports
import prompt
from src import facts_in, files, machine, outcome as outcomelib, transcript, writer


def unwritten(place, name: str, why: str, run_id: str = "") -> pathlib.Path:
    """ライブラリに頼らず訳だけの 1 ファイルを書く（書けなくてもパスは返す。先の無い pointer は実行基盤が終わりに拒む）"""
    path = pathlib.Path(place) / name
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 報告（run {run_id or '—'}）\n\n報告を組めなかった: {why}\n", encoding="utf-8")
    except OSError:
        pass
    return path


# ---------------------------------------------------------------- facts
def facts(place, *, sections, facts, lang, run_id: str, workflow_file, repo) -> dict:
    """返り {outcome, ok, stop_reason, machine, next_request, prior_failures, ai_go, stamp}。place に facts.json を書く"""
    place = pathlib.Path(place)
    problems = []
    try:
        rows = ports.json(sections, "shared:sections.schema.json")
    except ValueError as e:
        problems.append(f"入力 sections: {e}")
        rows = []
    try:
        got = facts_in.from_port(facts)
    except ValueError as e:
        problems.append(f"入力 facts: {e}")
        got = facts_in.read({})
    got["problems"] = [*got["problems"], *problems]
    log, log_why = transcript.read()
    run = transcript.facts(log, exclude_prefix=transcript.own_prefix(), optional=got["optional"])
    run["children"] = transcript.child_falls(run)
    word, stop = outcomelib.decide(got, run)
    opened, unopened = machine.open_files(rows)
    built = machine.build(opened, got, word, stop, run, place=place, run_id=run_id, run_why=log_why, repo=repo, notes=unopened)
    stamp = writer.stamp(run_id, workflow_file, got["round"], got["line_rev"], got["start_ok"])
    ok = word in outcomelib.OK_OUTCOMES
    jsonfile.write(place / files.FACTS_FILE, {"outcome": word, "stop_reason": stop, "ok": ok, "ai_go": built["ai_go"], "stamp": stamp,
                                              "lang": ports.text(lang).strip(), "run_id": run_id, "decisions": built["decisions"]})
    nxt, prior = built["next_request"], built["prior_failures"]
    return {"outcome": word, "ok": ok, "stop_reason": stop, "machine": ports.pointer(built["report"], "file"),
            "next_request": None if nxt is None else ports.pointer(nxt, "json(lib:next-request.schema.json)"),
            "prior_failures": None if prior is None else ports.pointer(prior, "json(lib:prior-failures.schema.json)"),
            "ai_go": built["ai_go"], "stamp": stamp}


def facts_fallback(place, why: str, run_id: str = "") -> dict:
    """facts が思わぬ誤りで落ちた時の返り: 訳を載せた機械の報告（ライブラリを読めない・書けない時は訳だけのファイル）を指す record_invalid。
    facts.json も書く（出口が読む）"""
    place = pathlib.Path(place)
    try:
        path = machine.fallback_report(place, why)
    except Exception:  # noqa: BLE001 — ライブラリを読めなくても、置き場に書けなくても返る
        path = unwritten(place, files.FACTS_UNWRITTEN_FILE, why, run_id)
    stop = f"report:{why}"
    try:
        (place / files.FACTS_FILE).write_text(json.dumps({"outcome": "record_invalid", "stop_reason": stop, "ok": False, "ai_go": False,
                                                          "stamp": "", "lang": "", "run_id": run_id, "decisions": 0},
                                                         ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        pass
    return {"outcome": "record_invalid", "ok": False, "stop_reason": stop, "machine": ports.pointer(path, "file"), "next_request": None,
            "prior_failures": None, "ai_go": False, "stamp": ""}


# ---------------------------------------------------------------- 指示
def _facts_doc(place) -> dict:
    got = jsonfile.read_or(pathlib.Path(place) / files.FACTS_FILE)
    if not isinstance(got, dict):
        raise ValueError(f"{files.FACTS_FILE} が無いか読めない（facts が先に走る）")
    return got


def write_prompt(place, *, run_id: str) -> dict:
    """書き手の指示を組んで place に書く。機械の報告の冒頭から、resume の前に出口が置いた「本文は無い」の行を先に外す。前の回までの拒否は
    place の控えから全部（受け付けが残した物）。返り {prompt}"""
    place = pathlib.Path(place)
    doc = _facts_doc(place)
    machine_file = place / files.REPORT_FILE
    writer.note_writer_fell(machine_file, None, run_id=run_id)
    rejected = rolekit.rejected(place, files.ROLE)
    candidate = rolekit.candidate_path(place, files.ROLE)
    prev = bool(rejected) and candidate.is_file() and not rolekit.given_up_reason(place, files.ROLE)
    notes = writer.handoff_rounds(place)
    values = {"rejection": rolekit.rejects_text(rejected), "outcome": doc["outcome"], "stop_reason": doc["stop_reason"],
              "facts_file": str(machine_file), "where_heading": files.bare(files.WHERE_HEADING),
              "stop_heading": files.bare(files.STOP_HEADING), "prev_file": str(candidate) if prev else "",
              "decisions_head": writer.DECISIONS_HEAD, "lang": prompt.lang(doc.get("lang")),
              "decisions_heading": files.bare(files.DECISIONS_HEADING), "cell_limit": writer.CELL_LIMIT, "handoff_rounds": notes}
    when = {"rejected": bool(rejected), "prev": prev, "handoff_rounds": bool(notes), "spawns": False}
    out = prompt.emit(files.WRITE_NODE, values, when, prompt.round_of(files.WRITE_NODE))
    return {"prompt": out["prompt"]}


def cold_prompt(place, raw) -> dict:
    """初見の読み手の指示を組んで place に書く（本文は人に向けた報告の頭と同じ物を、機械が組んだ行と書き手の頭に分けて貼る）。返り {prompt}"""
    place = pathlib.Path(place)
    machine, body = writer.cold_parts(raw, place=place)
    values = {"machine": machine, "body": body, "machine_heading": files.bare(writer.MACHINE_HEADING)}
    out = prompt.emit(files.COLD_NODE, values, {}, prompt.round_of(files.COLD_NODE))
    return {"prompt": out["prompt"]}


# ---------------------------------------------------------------- 出口
def _carried(place) -> dict:
    """次の run に運ぶ控えの pointer（無いファイルは null）"""
    nxt, prior = pathlib.Path(place) / carry.NEXT_REQUEST_FILE, pathlib.Path(place) / carry.PRIOR_FAILURES_FILE
    return {"next_request": ports.pointer(nxt, "json(lib:next-request.schema.json)") if nxt.is_file() else None,
            "prior_failures": ports.pointer(prior, "json(lib:prior-failures.schema.json)") if prior.is_file() else None}


def _machine_file(place) -> pathlib.Path | None:
    for name in (files.REPORT_FILE, files.UNWRITTEN_FILE, files.FACTS_UNWRITTEN_FILE):
        if (pathlib.Path(place) / name).is_file():
            return pathlib.Path(place) / name
    return None


def _report_lines(outcome: str, human, why: str, machine_pointer) -> list:
    return [f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）",
            f"人に向けた報告: {human['path']}" if human else f"人に向けた報告: 無い（{why}）",
            f"機械の報告: {machine_pointer['path']}"]


def finish(place, *, run_id: str) -> dict:
    """出力 {ok, outcome, stop_reason, machine, human, detail, next_request, prior_failures, report}。書き手のループが落ちていれば、その訳を
    機械の報告の冒頭に置く（resume で書き直した run では外す）。人に向けた報告と詳細のファイルは ai.json が在る時だけ書く"""
    place = pathlib.Path(place)
    doc = _facts_doc(place)
    machine_file = _machine_file(place)
    if machine_file is None:
        raise ValueError("機械の報告が place に無い（facts が先に走る）")
    rows, _ = transcript.read()
    fell = transcript.writer_fell(rows, transcript.own_prefix() + files.WRITE_LOOP)
    ai_path = None
    if machine_file.name == files.REPORT_FILE:
        writer.note_writer_fell(machine_file, fell, run_id=run_id)
        ai_path = writer.collect(machine_file.read_text(encoding="utf-8"), place=place, stamp=doc["stamp"])
    human = ports.pointer(ai_path, "file") if ai_path else None
    if human:
        why = ""
    elif not doc["ai_go"]:
        why = f"結果を名乗れない（結末 {doc['outcome']}）ので書き手を起こしていない"
    else:
        why = f"書き手のノードが落ちた（{fell['error']}）" if fell else "書き手の返答が無い"
    machine_pointer = ports.pointer(machine_file, "file")
    detail = place / files.DETAIL_FILE
    return {"ok": doc["ok"] is True, "outcome": doc["outcome"], "stop_reason": doc["stop_reason"], "machine": machine_pointer,
            "human": human, "detail": ports.pointer(detail, "file") if human and detail.is_file() else None, **_carried(place),
            "report": _report_lines(doc["outcome"], human, why, machine_pointer)}


def finish_fallback(place, why: str, run_id: str = "") -> dict:
    """出口が思わぬ誤りで落ちた時の返り: facts の機械の報告が在ればそれを指す record_invalid。無ければ訳だけのファイルを指す"""
    place = pathlib.Path(place)
    stop = f"report:{why}"
    path = _machine_file(place) or unwritten(place, files.FINISH_UNWRITTEN_FILE, why, run_id)
    pointer = ports.pointer(path, "file")
    try:
        carried = _carried(place)
    except ValueError:   # 落ちない出口の中: 形の外れた控えは運ばない（指さずに null。訳は機械の報告の側に在る）
        carried = {"next_request": None, "prior_failures": None}
    return {"ok": False, "outcome": "record_invalid", "stop_reason": stop, "machine": pointer, "human": None, "detail": None,
            **carried,
            "report": _report_lines("record_invalid", None, why, pointer)}
