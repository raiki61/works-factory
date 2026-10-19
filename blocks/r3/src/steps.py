"""block r3 の中身（docs/design/r3.md の 1〜5 節）。入口・整合の役の指示の値・返答の控え・出口を、port の値と place のファイルで組む。
指示の文は prompts/r3-coherence.md と共通の断片 eye-coherence が持ち、ここは材料と値だけを組む。
"""
from __future__ import annotations

import pathlib

import ports
import prompt
import requestrows

import concepthome   # lib/。PREFIX
import eyekit        # lib/。独立の目の族の共通の部品
import jsonfile      # lib/
import oneline       # lib/

from src import files, report

NO_INTAKE = "入口の控え intake.json が無いか読めない（入口の node が落ちた）"
UNREAD_INPUT = "入力が読めない: {why}"
REQUEST_UNREAD = "依頼のファイルの中身が読めない（answers は空にした）: {why}"


# ---------------------------------------------------------------- 入口
def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def _path(path) -> str:
    return str(path) if path is not None else ""


def _request_answers(raw) -> tuple[str, list, str]:
    """(依頼のファイルのパス, 依頼の answers, 中身が読めない訳)。ファイルが無い・指せないのは port の誤り（ValueError）。中身が読めない
    だけなら止めず、answers を空にして訳を返す（answers は記録された方針の行の出どころの 1 つにすぎない）"""
    path = ports.file(raw)
    if path is None:
        return "", [], ""
    try:
        return str(path), list(requestrows.parts(str(path))["answers"] or []), ""
    except Exception as e:  # noqa: BLE001 — 読めない中身は役を止めない（訳は intake.json の unread に残す）
        return str(path), [], oneline.one_line(f"{type(e).__name__}: {e}")


def _read_ports(raw: dict) -> tuple[dict, list]:
    """port の値と、読めない port の訳の並び（「入力 <名>: <訳>」）"""
    doc, bad = {}, []
    readers = {
        "base": lambda v: ports.text(v).strip(),
        "lang": lambda v: ports.text(v).strip(),
        "green": lambda v: True if _blank(v) else ports.flag(v),
        "after": lambda v: _path(ports.file(v)),
        "review": lambda v: {} if _blank(v) else ports.json(v, "shared:plan-verdict.schema.json"),
        "policy": lambda v: _path(ports.file(v)),
        "answers": lambda v: {} if _blank(v) else ports.json(v, "shared:gate-answers.schema.json"),
        "request": _request_answers,
        "pushes": lambda v: [] if _blank(v) else ports.json(v, "shared:pushes.schema.json"),
        "decisions": lambda v: _path(ports.file(v)),
    }
    for name, read in readers.items():
        try:
            doc[name] = read(raw.get(name))
        except ValueError as e:
            bad.append(f"入力 {name}: {oneline.one_line(e)}")
    return doc, bad


def intake(out, repo, raw: dict, skip) -> dict:
    """port を読み、この block のファイルを名で消して累積差分を取り、記録された方針の行を組んで intake.json を書く。返り {due, reason}。
    読めない port が在れば due: false と、どの port かを頭に付けた訳。依頼のファイルの中身が読めないこと・差分が空か取れないことでは
    止めない（訳は intake.json の unread か差分の代わりのファイルに書く）。落ちない"""
    out = pathlib.Path(out)
    doc = {"due": False, "reason": ""}
    try:
        for name in files.OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in files.OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        values, bad = _read_ports(raw)
        request_file, request_answers, unread = values.pop("request", ("", [], ""))
        doc.update(values, request=request_file, unread=unread)
        if bad:
            doc["reason"] = "；".join(bad)
        else:
            items = eyekit.human_items(values["answers"])
            doc["recorded"] = eyekit.recorded_rows(values["policy"] or None, request_answers, items, values["pushes"],
                                                   values["decisions"] or None)
            diff = eyekit.take_diff(out, repo, values["base"], skip, files.DIFF, files.DIFF_NONE)
            diff.pop("text")
            doc["diff"] = diff
            doc["due"] = True
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        doc.update(due=False, reason=oneline.one_line(f"{type(e).__name__}: {e}"))
    jsonfile.write(out / files.INTAKE, doc)
    return {"due": doc["due"], "reason": doc["reason"]}


# ---------------------------------------------------------------- 指示
def _intake(out) -> dict:
    doc = jsonfile.read_or(pathlib.Path(out) / files.INTAKE)
    if not isinstance(doc, dict) or not doc.get("due"):
        raise ValueError(NO_INTAKE)
    return doc


def coherence_prompt(out, repo) -> dict:
    """整合の役の指示（docs/design/r3.md の 2.3）。いつも全部の値を渡し、選ぶ段落は when で決める"""
    doc = _intake(out)
    concept, found = eyekit.maps(repo)
    rows, none = eyekit.recorded_rows_text(doc["recorded"])
    values = {
        "home_prefix": concepthome.PREFIX,
        "after_section": eyekit.after_section(doc["after"] or None, doc["review"]),
        **concept,
        **eyekit.review_md_values(repo),
        **eyekit.diff_values(doc["diff"]),
        "policy_body": eyekit.policy_body(doc["policy"] or None),
        "recorded_rows": rows,
        **eyekit.status_values("r3"),
        "lang": prompt.lang(doc["lang"]),
    }
    when = {"maps_found": found, "green": doc["green"] is True, "policy": bool(doc["policy"]), "recorded_none": none}
    return prompt.emit(files.COHERENCE, values, when, prompt.round_of(files.COHERENCE))


# ---------------------------------------------------------------- 返答の控え
def save(out, name: str, reply: str) -> dict:
    """役の返答を字のまま place の <name>.json に書く。name は files.REPLIES の中だけ（place に知らない名のファイルを書かない）"""
    if name not in files.REPLIES:
        raise ValueError(f"返答の名 {name!r} は {'・'.join(files.REPLIES)} のどれでもない")
    (pathlib.Path(out) / f"{name}.json").write_text(ports.text(reply), encoding="utf-8")
    return {"saved": True}


# ---------------------------------------------------------------- 出口
def finish(out) -> dict:
    """place の intake.json と役の返答から出力を組み、finish.json にも書く（docs/design/r3.md の 3・4 節）"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    if not isinstance(doc, dict) or not doc.get("due"):
        why = (doc.get("reason") if isinstance(doc, dict) else "") or NO_INTAKE
        row = {"status": "unverifiable", "reason": UNREAD_INPUT.format(why=why)}
        got = {"ok": False, "status": "failed", "reason": why, "verdict": row, "questions": [], "report": report.lines(row)}
    else:
        reply, unread = eyekit.read_reply(out, files.COHERENCE)
        row, took = eyekit.verdict_row("r3", reply, unread)
        got = {"ok": took, "status": "ran" if took else "failed", "reason": "" if took else row["reason"], "verdict": row,
               "questions": [], "report": report.lines(row)}
    jsonfile.write(out / files.FINISH, got)
    return got
