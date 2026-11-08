"""block r2 の中身（docs/design/r2.md の 1〜5 節）。入口・2 つの役の指示の値・返答の控え・出口を、port の値と place のファイルで組む。
指示の文は prompts/ の md が持ち、ここは材料と値だけを組む。
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt

import eyekit        # lib/。独立の目の族の共通の部品
import gatemarks     # lib/。推しの形（recommend_shape）
import jsonfile      # lib/
import oneline       # lib/
import seal          # lib/。判定の語
import worldmark     # lib/。頼みの解き方の番号（means_hints）

from src import conflicts, due, files, measured, notes, premises, report

NO_INTAKE = "入口の控え intake.json が無いか読めない（入口の node が落ちた）"
NOT_DUE = "入口の控えが {kind} の道を起こすと言っていない"
UNREAD_INPUT = "入力が読めない: {why}"
OFF_CONTRACT = "出力の判定の語が約束の外"
UNFINISHED_KIND = "作り残し"   # 比べの返答の違いの種のうち、設計の向きは合っていて直しが作り切れていない行
STRUCTURE_KIND = "構造"       # 同じく、本質的な構造の違いの行（1 つでも在れば作り直し）
# 比べの役が reason の頭に書いて、設計違いを名指さずに作り直しを言う 3 つの字（役の指示 r2-compare.md へはここから入れる）。
# reason がこれで始まる返答は、違いの行に依らず redesign-needed のままにする（settle の 1）
KEEP_HEADS = ("累積差分を読めなかった: ", "設計の前提が変わった: ", "問いが立たない: ")
_FIX, _REDESIGN = map(gatemarks.status_named, (seal.FIX_NEEDED, seal.REDESIGN))
RAISED_BY_UNFINISHED = "構造の違いが無く作り残しの行が在るので" + _FIX + "にした（目は{word}と書いた）: "
NO_UNFINISHED = f"目は{_FIX}と書いたが、作り残しの行の名指しが無いので{_REDESIGN}にした: "


# ---------------------------------------------------------------- 入口
def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def _port(name: str, read):
    """port 1 つを読む。読めなければ「入力 <名>: <訳>」の ValueError"""
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {oneline.one_line(e)}") from None


def _request(raw) -> tuple[str, bool]:
    """(依頼のファイルの本文, 読めたか)。渡っていない・読めない時は止めず、読めなかった印にする（名指しの節は渡されなかったと役に言う）"""
    if _blank(raw):
        return "", False
    try:
        path = ports.file(raw, "json(shared:request.schema.json)")
        return path.read_text(encoding="utf-8"), True
    except (ValueError, OSError, UnicodeDecodeError):
        return "", False


def _read_ports(raw: dict) -> tuple[dict, list]:
    """port の値と、読めない port の訳の並び（「入力 <名>: <訳>」）"""
    readers = {
        "base": lambda v: ports.text(v).strip(),
        "head": lambda v: ports.text(v).strip(),
        "base_label": lambda v: ports.text(v).strip(),
        "purpose": lambda v: ports.text(v).strip(),
        "means": lambda v: [] if _blank(v) else ports.json(v, "shared:stated-means.schema.json"),
        "design": lambda v: None if _blank(v) else ports.json(v, "shared:design.schema.json"),
        "design_reason": lambda v: ports.text(v).strip(),
        "design_premises": lambda v: None if _blank(v) else ports.json(v, "shared:design-premises.schema.json"),
        "answers": lambda v: {} if _blank(v) else ports.json(v, "shared:gate-answers.schema.json"),
        "changed": lambda v: {} if _blank(v) else ports.json(v, "shared:fix-marks.schema.json"),
        "constraints": lambda v: [] if _blank(v) else ports.json(v, "shared:constraints.schema.json"),
        "test_outcomes": lambda v: None if _blank(v) else ports.json(v, "shared:outcomes.schema.json"),
        "tdd": lambda v: None if _blank(v) else ports.json(v, "shared:tdd.schema.json"),
        "lang": lambda v: ports.text(v).strip(),
    }
    doc, bad = {}, []
    for name, read in readers.items():
        try:
            doc[name] = _port(name, lambda: read(raw.get(name)))
        except ValueError as e:
            bad.append(str(e))
    doc["request_text"], doc["request_read"] = _request(raw.get("request"))
    return doc, bad


def intake(out, repo, raw: dict, skip) -> dict:
    """port を読み、この block のファイルを名で消して累積差分を取り、独立設計の返答からどの役を起こすかを決めて intake.json を書く。
    返り {compare, premise, reason}。読めない port が在れば両方偽と、どの port かを頭に付けた訳。差分が空・取れないことでは止めない。落ちない"""
    out = pathlib.Path(out)
    doc = {"read": False, "compare": False, "premise": False, "reason": ""}
    try:
        for name in files.OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in files.OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        values, bad = _read_ports(raw)
        doc.update(values)
        if bad:
            doc["reason"] = "；".join(bad)
        else:
            diff = eyekit.take_diff(out, repo, values["base"], skip, files.DIFF, files.DIFF_NONE)
            diff.pop("text")
            doc["diff"] = diff
            doc["design"] = due.read_design(values["design"], values["design_reason"])
            doc["compare"] = due.compare_due(doc["design"], values["purpose"])
            doc["premise"] = due.premise_invalid(doc["design"])
            doc["read"] = True
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        doc.update(read=False, compare=False, premise=False, reason=oneline.one_line(f"{type(e).__name__}: {e}"))
    jsonfile.write(out / files.INTAKE, doc)
    return {"compare": doc["compare"], "premise": doc["premise"], "reason": doc["reason"]}


# ---------------------------------------------------------------- 指示
def _intake(out, kind: str) -> dict:
    doc = jsonfile.read_or(pathlib.Path(out) / files.INTAKE)
    if not isinstance(doc, dict) or not doc.get("read"):
        raise ValueError(NO_INTAKE)
    if not doc.get(kind):
        raise ValueError(NOT_DUE.format(kind=kind))
    return doc


def _measured_values(doc: dict, repo, out) -> dict:
    """部品 measured の値。名を貼るテストの範囲は、累積差分の起点から地図を r2 が自分で作って決める（置き場は place の files.IMPACT）"""
    diff = doc["diff"]
    origin = measured.origin_section(repo, diff["base"], doc["head"] or "HEAD", doc["base_label"],
                                     cumulative_empty=diff["lines"] == 0 and not diff["why"], skip=(ports.RUNTIME_COPY_PREFIX,))
    scope = measured.named_scope(repo, diff["base"], None if diff["why"] else diff["changed"], pathlib.Path(out) / files.IMPACT,
                                 doc["tdd"])
    return {"outcomes": "\n".join(measured.outcome_lines(doc["test_outcomes"], scope)),
            "tdd_records": "\n".join(measured.tdd_record_lines(doc["tdd"])), "origin": origin}


def compare_prompt(out, repo) -> dict:
    """比べの役の指示と system prompt（docs/design/r2.md の 2.3）を組み、貼った前提の控え r2-premises.json を書く。返り {prompt, system}"""
    out = pathlib.Path(out)
    doc = _intake(out, "compare")
    got = premises.material(premises.view_of(doc["answers"], doc["request_text"]), repo)
    said = worldmark.means_hints(doc.get("means"))
    post = premises.after(got["ledger"], doc["request_read"], doc["design_premises"], doc["changed"], doc["constraints"], said)
    diff, dv = doc["diff"], eyekit.diff_values(doc["diff"])
    st = eyekit.status_values("r2")
    head_unread, head_premise, head_no_question = KEEP_HEADS
    values = {"diff_file": dv["diff_file"], "diff_lines": str(diff["lines"]), "changed_files": dv["changed_files"],
              "answers": got["answers"], "named": got["named"], "map": got["map"],
              "late": post["late"], "drift": post["drift"], "constraints": post["constraints"],
              **_measured_values(doc, repo, out),
              "purpose": doc["purpose"], "design_text": str(doc["design"].get("design") or ""),
              "st_pass": st["st_pass"], "st_fix": st["st_fix"], "st_redesign": st["st_redesign"],
              "head_unread": head_unread, "head_premise": head_premise, "head_no_question": head_no_question, "lang": prompt.lang(doc["lang"]),
              "means_rows": "\n".join(f"- {k}: {oneline.one_line(t)}" for k, t in said.items()), "recommend_shape": gatemarks.recommend_shape()}
    when = {"answers": bool(got["answers"]), "named": bool(got["named"]), "request_unread": not doc["request_read"],
            "late": bool(post["late"]), "means": bool(said)}
    jsonfile.write(out / files.PREMISES, {"node": "r2.compare", **post["ledger"]})
    return prompt.emit(files.COMPARE, values, when, prompt.round_of(files.COMPARE))


def premise_prompt(out, repo) -> dict:
    """検算の役の指示（docs/design/r2.md の 3.3）。返り {prompt}"""
    out = pathlib.Path(out)
    doc = _intake(out, "premise")
    values = {"design_reply": json.dumps(doc["design"], ensure_ascii=False, indent=1), "purpose": doc["purpose"],
              "constraints": premises.constraints_text(doc["constraints"]), "repo": str(pathlib.Path(repo).resolve()),
              **_measured_values(doc, repo, out), "fix_diff_row": measured.FIX_DIFF_ROW,
              "resolved": due.VERDICTS[0], "escalate": due.VERDICTS[1], "lang": prompt.lang(doc["lang"])}
    return prompt.emit(files.PREMISE, values, {"spawns": False}, prompt.round_of(files.PREMISE))


# ---------------------------------------------------------------- 返答の控え
def save(out, name: str, reply: str) -> dict:
    """役の返答を字のまま place の <name>.json に書く。name は files.REPLIES の中だけ（place に知らない名のファイルを書かない）"""
    if name not in files.REPLIES:
        raise ValueError(f"返答の名 {name!r} は {'・'.join(files.REPLIES)} のどれでもない")
    (pathlib.Path(out) / f"{name}.json").write_text(ports.text(reply), encoding="utf-8")
    return {"saved": True}


# ---------------------------------------------------------------- 出口
def _premise_check(reply, unread: str) -> dict:
    """検算の役の返答から premise_check を組む。語が約束の外・返答が無ければ escalate と落ちた訳（key・resolution・facts は空）"""
    if isinstance(reply, dict) and reply.get("verdict") in due.VERDICTS:
        facts = notes.premise_facts(reply)
        return {"verdict": reply["verdict"], "reason": str(reply.get("reason")), **facts}
    return {"verdict": "escalate", "reason": eyekit.fell_text(files.PREMISE, unread or OFF_CONTRACT), "key": "", "resolution": "", "facts": []}


def _failed(why: str) -> dict:
    row = {"status": "unverifiable", "reason": UNREAD_INPUT.format(why=why)}
    return {"ok": False, "status": "failed", "reason": why, "verdict": row, "questions": [], "premise_check": None, "notes": [],
            "findings": [], "report": [eyekit.headline("R2", row)]}


def _diff_text(out) -> str:
    """入口が書いた累積差分の本文（無い・読めなければ空。引用の照らしの材料）"""
    try:
        return (pathlib.Path(out) / files.DIFF).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _rows(compare, kind: str) -> list:
    """比べの返答の違いのうち、種が kind の行（dict でない項・知らない種は数えない）"""
    diffs = compare.get("differences") if isinstance(compare, dict) else None
    return [d for d in diffs if isinstance(d, dict) and d.get("kind") == kind] if isinstance(diffs, list) else []


def _tail(label: str, rows: list, with_where: bool = False) -> str:
    """reason の尾「（<label>: <行の text を ／ でつなぐ>）」。with_where なら where の在る行は「<where>: <text>」"""
    texts = [(f"{d['where']}: " if with_where and d.get("where") else "") + oneline.one_line(d.get("text") or "") for d in rows]
    return f"（{label}: {'／'.join(texts)}）"


def settle(doc: dict) -> dict:
    """R2 の比べの返答の判定の行の決め直し（eyekit.verdict_row の settle。docs/design/r2.md の 5 節）。語の確かめは済んだ返答 doc の
    status と違いの行の種（構造・表現・作り残し）から、上から順に:
    0. status が unverifiable ならそのまま（役の型には無い語）
    1. reason が KEEP_HEADS のどれかで始まれば redesign-needed（行に依らず作り直しのまま）
    2. status が pass でなく、種が構造の行が在れば redesign-needed（行の text を reason の尾「（構造の違い: …）」に足す）
    3. 種が作り残しの行が在れば fix-needed（返答が別の語なら頭に RAISED_BY_UNFINISHED。尾「（作り残し: …）」に行の where と text を足す）
    4. status が fix-needed なのに作り残しの行が無ければ redesign-needed（頭に NO_UNFINISHED。名指しが無い物は修正の段へ返せない）
    5. ほかは返答のまま（pass に本質でない構造の行だけ・redesign-needed に表現の行だけ・行が無い時）"""
    status, reason = doc["status"], str(doc.get("reason"))
    structure, unfinished = _rows(doc, STRUCTURE_KIND), _rows(doc, UNFINISHED_KIND)
    if status == seal.UNVERIFIABLE:
        return {"status": status, "reason": reason}
    if reason.startswith(KEEP_HEADS):
        return {"status": seal.REDESIGN, "reason": reason}
    if status != seal.PASSED and structure:
        return {"status": seal.REDESIGN, "reason": reason + _tail("構造の違い", structure)}
    if unfinished:
        head = "" if status == seal.FIX_NEEDED else RAISED_BY_UNFINISHED.format(word=gatemarks.status_named(status))
        return {"status": seal.FIX_NEEDED, "reason": head + reason + _tail("作り残し", unfinished, with_where=True)}
    if status == seal.FIX_NEEDED:
        return {"status": seal.REDESIGN, "reason": NO_UNFINISHED + reason}
    return {"status": status, "reason": reason}


def findings(row: dict, compare) -> list:
    """修正の段へ返す項目（出口の欄 findings）。比べの道で判定が fix-needed の時だけ、返答の違いのうち種が作り残しの行を
    {where（無ければ空の字）, text（修正の段の notes に行ごとに入るので 1 行）} にして順に並べる。ほかは空"""
    if row["status"] != seal.FIX_NEEDED:
        return []
    return [{"where": str(d.get("where") or ""), "text": oneline.one_line(d.get("text") or "")} for d in _rows(compare, UNFINISHED_KIND)]


def finish(out) -> dict:
    """place の intake.json と役の返答から出力を組み、finish.json にも書く（docs/design/r2.md の 5 節）"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    if not isinstance(doc, dict) or not doc.get("read"):
        got = _failed((doc.get("reason") if isinstance(doc, dict) else "") or NO_INTAKE)
        jsonfile.write(out / files.FINISH, got)
        return got
    design = doc["design"]
    compare, unread_compare = eyekit.read_reply(out, files.COMPARE)
    check, unread_check = eyekit.read_reply(out, files.PREMISE)
    try:
        note_lines = notes.input_lines(notes.write(out, doc["design_premises"], compare))
    except OSError:
        note_lines = [notes.NO_INPUTS]
    status, why, premise_check, replied, asks, owed = "ran", "", None, True, [], []
    if "missing" in design:
        status = "skipped"
        row = {"status": "unverifiable", "reason": due.R2_MISSING_HEAD + str(design["missing"])}
    elif doc["premise"]:
        row = {"status": "unverifiable", "reason": due.R2_PREMISE_HEAD + due.premise_reason(design)}
        premise_check = _premise_check(check, unread_check)
        replied = check is not None
        if premise_check["verdict"] == "escalate" and not (isinstance(check, dict) and check.get("verdict") in due.VERDICTS):
            status, why = "failed", premise_check["reason"]
    elif doc["compare"]:
        row, took = eyekit.verdict_row("r2", compare, unread_compare, settle=settle)
        if not took:
            status, why = "failed", row["reason"]
        else:
            asks = conflicts.questions(compare, doc.get("means"), str(design.get("design") or ""), _diff_text(out))
            owed = findings(row, compare)
    else:
        status = "skipped"
        row = {"status": "unverifiable", "reason": due.R2_NO_PURPOSE}   # 問いが立つかの欄は port の形（shared:design）が要る
    got = {"ok": status != "failed", "status": status, "reason": why, "verdict": row, "questions": asks, "premise_check": premise_check,
           "notes": note_lines, "findings": owed, "report": report.lines(row, note_lines, premise_check, replied, asks)}
    jsonfile.write(out / files.FINISH, got)
    return got
