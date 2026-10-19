"""block r4 の中身（docs/design/r4.md の 1〜5 節）。入口・範囲の役と出し直しの役の指示・受け付け・出口を、port の値と place のファイルで
組む。指示の文は prompts/r4-scope.md と prompts/r4-scope-fix.md が持ち、ここは材料と値だけを組む。
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt
import requestrows

import concepthome   # lib/。PREFIX
import eyekit        # lib/。独立の目の族の共通の部品
import jsonfile      # lib/
import oneline       # lib/
import rolekit       # lib/

from src import files, gate, report, take

NOT_GIVEN = "(not given)"                                          # 渡っていない材料の値（md の材料の行）
NO_INTAKE = "入口の控え intake.json が無いか読めない（入口の node が落ちた）"
UNREAD_INPUT = "入力が読めない: {why}"
NO_R3 = "出力の欄 r3 が無い"
ACCEPT_CRASHED = "（受け付けが落ちた: {why}）"                       # 判定の行の reason の尾


def value(raw):
    """script が with: で受けた入力の字を値に戻す（Archon が運ぶ字。飛ばされた node の null と空の字は None。JSON でなければ字のまま）"""
    if raw is None or not raw.strip() or raw.strip() == "null":
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


# ---------------------------------------------------------------- 入口
def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def _path(path) -> str:
    return str(path) if path is not None else ""


def _read_ports(raw: dict) -> tuple[dict, list]:
    """port の値と、読めない port の訳の並び（「入力 <名>: <訳>」）。after と review はまとめた形の時だけ読む"""
    doc, bad = {}, []
    readers = {
        "base": lambda v: ports.text(v).strip(),
        "lang": lambda v: ports.text(v).strip(),
        "purpose": lambda v: ports.text(v).strip(),
        "green": lambda v: True if _blank(v) else ports.flag(v),
        "coherence": lambda v: False if _blank(v) else ports.flag(v),
        "policy": lambda v: _path(ports.file(v)),
        "ripple": lambda v: _path(ports.file(v)),
        "world_rows": lambda v: _path(ports.file(v)),
        "decisions": lambda v: _path(ports.file(v)),
        "answers": lambda v: {} if _blank(v) else ports.json(v, "shared:gate-answers.schema.json"),
        "changed": lambda v: {} if _blank(v) else ports.json(v, "shared:fix-marks.schema.json"),
        "pushes": lambda v: [] if _blank(v) else ports.json(v, "shared:pushes.schema.json"),
        "asked": lambda v: [] if _blank(v) else ports.json(v, "r4-asked.schema.json"),
        "declared": lambda v: [] if _blank(v) else ports.json(v, "r4-declared.schema.json"),
        "request": lambda v: [] if _blank(v) else requestrows.parts(v)["answers"],   # 依頼の answers
    }
    coherence = {"after": lambda v: _path(ports.file(v)),
                 "review": lambda v: {} if _blank(v) else ports.json(v, "shared:plan-verdict.schema.json")}

    def read(name, fn):
        try:
            doc[name] = fn(raw.get(name))
        except ValueError as e:
            bad.append(f"入力 {name}: {oneline.one_line(e)}")

    for name, fn in readers.items():
        read(name, fn)
    for name, fn in coherence.items():
        if doc.get("coherence") is True:
            read(name, fn)
        else:
            doc[name] = fn(None) if name == "after" else {}
    return doc, bad


def intake(out, repo, raw: dict, skip) -> dict:
    """port を読み、この block のファイルを名で消して累積差分を取り、記録された方針の行を組んで intake.json を書く。返り {due, reason}。
    読めない port が在れば due: false と、どの port かを頭に付けた訳。差分が空・取れないことでは止めない（訳は差分の代わりのファイルに
    書き、役はそれを読む）。落ちない"""
    out = pathlib.Path(out)
    doc = {"due": False, "reason": ""}
    try:
        for path in files.own_files(out):
            path.unlink(missing_ok=True)
        for pattern in files.OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        values, bad = _read_ports(raw)
        doc.update(values)
        doc["request_answers"] = doc.pop("request", [])
        doc["before_fix"] = (doc.get("answers") or {}).get("before_fix")
        if bad:
            doc["reason"] = "；".join(bad)
        else:
            decisions = pathlib.Path(doc["decisions"]) if doc["decisions"] else None
            doc["recorded"] = eyekit.recorded_rows(doc["policy"] or None, doc["request_answers"], eyekit.human_items(doc["answers"]),
                                                   doc["pushes"], decisions)
            doc["diff"] = {k: v for k, v in eyekit.take_diff(out, repo, doc["base"], skip, files.DIFF, files.DIFF_NONE).items()
                           if k != "text"}
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


def _marks(changed) -> str:
    """修正の印（真偽の欄）を `<名>=<true|false>` にして `・` でつないだ字か (not given)"""
    marks = [f"{k}={str(v).lower()}" for k, v in (changed if isinstance(changed, dict) else {}).items() if isinstance(v, bool)]
    return "・".join(marks) or NOT_GIVEN


def scope_prompt(out, repo, doc: dict) -> dict:
    """範囲の役の 1 回目の指示（docs/design/r4.md の 2.3）。前の回の拒否が在る回（resume の 1 周目）だけ、拒否の段落が入る"""
    out = pathlib.Path(out)
    rejects = rolekit.rejected(out, files.R4_NODE)
    passed = gate.human_passed(doc["asked"], doc["before_fix"])
    carried, declared = gate.carried_rows(passed), gate.declared_rows(doc["declared"])
    coherence = doc["coherence"] is True
    concept, found = eyekit.maps(repo)
    recorded, none = eyekit.recorded_rows_text(doc["recorded"])
    values = {
        "rejection": rolekit.rejects_text(rejects),
        "carried": carried,
        "declared": declared,
        **eyekit.diff_values(doc["diff"]),
        "purpose": doc["purpose"] or NOT_GIVEN,
        **eyekit.review_md_values(repo),
        "ripple": doc["ripple"] or NOT_GIVEN,
        "world_rows": doc["world_rows"] or NOT_GIVEN,
        "marks": _marks(doc["changed"]),
        **eyekit.status_values("r4"),
        "home_prefix": concepthome.PREFIX,
        "after_section": eyekit.after_section(doc["after"] or None, doc["review"]) if coherence else "",
        **concept,
        "policy_body": eyekit.policy_body(doc["policy"] or None),
        "recorded_rows": recorded,
        "lang": prompt.lang(doc["lang"]),
    }
    when = {"rejected": bool(rejects), "carried": bool(carried), "declared": bool(declared), "green": doc["green"] is True,
            "coherence": coherence, "coherence_map": coherence and found, "coherence_nomap": coherence and not found,
            "policy": bool(doc["policy"]), "recorded_none": none}
    return prompt.emit(files.R4_NODE, values, when, prompt.round_of(files.R4_NODE))


def scope_prep(out, repo, prev) -> dict:
    """範囲の役の輪の頭。前の周が拒まれ（prev が前の周の受け付けの ok の false）、合わせた答えの控えが在れば出し直しの周（resubmit: true。
    1 回目の役の指示 prompt は空で、出し直しの役の指示は scope_fix_prep が組む）。ほかは 1 回目の役の指示を組む。resume で輪が 1 周目から
    回り直すと prev は空で、拒否の控えが在れば拒否の段落つきの全部の指示を組む。返り {prompt, resubmit, attempt}"""
    out = pathlib.Path(out)
    doc = _intake(out)
    resubmit = rolekit.resubmitting(out, files.R4_NODE, value(prev))
    text = "" if resubmit else scope_prompt(out, repo, doc)["prompt"]
    return {"prompt": text, "resubmit": resubmit, "attempt": rolekit.attempt(out, files.R4_NODE)}


def scope_fix_prompt(out) -> dict:
    """出し直しの役（1 回目の役の会話の続き）の指示（docs/design/r4.md の 3.3）。最後の拒否の文と、機械が合わせた前の答えの控えのパス。
    材料とリポジトリは会話に在るので貼らない"""
    out = pathlib.Path(out)
    doc = _intake(out)
    rejects = rolekit.rejected(out, files.R4_NODE)
    values = {"rejection": rejects[-1] if rejects else "", "candidate": str(files.candidate(out)), "lang": prompt.lang(doc["lang"])}
    return prompt.emit(files.FIX_NODE, values, None, prompt.round_of(files.FIX_NODE))


# ---------------------------------------------------------------- 受け付け
def accept(out, reply, fix_reply) -> dict:
    """範囲の役の返答を受け付ける（docs/design/r4.md の 4 節）。reply は 1 回目の役の返答、fix_reply は出し直しの役の返答（直す欄だけ。
    どちらも JSON に戻した値で、起きなかった役は None）。出し直しは前の答えの控えと欄ごとに合わせてから照らす。読めた最後の答えは
    r4-scope.json に毎回書く。返り {ok, done, give_up, reason}"""
    out = pathlib.Path(out)
    doc = _intake(out)
    got = rolekit.resubmitted(out, files.R4_NODE, reply, fix_reply, rolekit.merge_fields)
    if got[0] is not None:
        jsonfile.write(out / files.REPLY, got[0])
    return take.scope(out, got, doc)


def record_crash(out, why: str) -> None:
    """受け付けが中の誤りで落ちた訳を place に残す（出口が読む。ここ自体は落ちない）"""
    try:
        jsonfile.write(pathlib.Path(out) / files.ACCEPT_CRASH, {"why": oneline.one_line(why)})
    except Exception:  # noqa: BLE001 — 落ちた訳を残す口が落ちても、受け付けの返りは返す
        pass


def _crash_why(out) -> str:
    crash = jsonfile.read_or(pathlib.Path(out) / files.ACCEPT_CRASH)
    return str(crash.get("why") or "") if isinstance(crash, dict) else ""


# ---------------------------------------------------------------- 出口
def finish(out) -> dict:
    """place の intake.json と範囲の役の返答から出力を組み、finish.json にも書く（docs/design/r4.md の 5 節）。受け付けが中の誤りで
    落ちた印が在れば、読めた返答が在っても failed にし、判定の行の reason の尾に落ちた訳を足す"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    if not isinstance(doc, dict) or not doc.get("due"):
        why = (doc.get("reason") if isinstance(doc, dict) else "") or NO_INTAKE
        row = {"status": "unverifiable", "reason": UNREAD_INPUT.format(why=why)}
        coherent = isinstance(doc, dict) and doc.get("coherence") is True
        got = {"ok": False, "status": "failed", "reason": why, "verdict": row, "questions": [], "passes": [],
               "coherence": dict(row) if coherent else None, "report": [eyekit.headline("R4", row)]}
    else:
        reply, unread = eyekit.read_reply(out, files.R4_NODE)
        row, took = eyekit.verdict_row("r4", reply, unread)
        gave_up = rolekit.given_up_reason(out, files.R4_NODE)
        if gave_up:
            row["reason"] += gate.R4_GAVE_UP.format(why=gave_up)
        crashed = _crash_why(out)
        if crashed:
            row["reason"] += ACCEPT_CRASHED.format(why=crashed)
            took = False
        passed = gate.human_passed(doc["asked"], doc["before_fix"])
        questions = gate.r4_gate_items(reply, passed)
        passes = gate.gate_passes(reply, passed, gate.passed_by(doc["before_fix"]))
        coherence = None
        if doc["coherence"] is True:
            coherence = eyekit.verdict_row("r3", reply.get("r3") if reply else None, unread if reply is None else NO_R3)[0]
        got = {"ok": took, "status": "ran" if took else "failed", "reason": "" if took else row["reason"], "verdict": row,
               "questions": questions, "passes": passes, "coherence": coherence,
               "report": report.lines(row, coherence, passes, reply is not None)}
    jsonfile.write(out / files.FINISH, got)
    return got
