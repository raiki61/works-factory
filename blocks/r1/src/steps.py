"""block r1 の中身（docs/design/r1.md の 1〜5 節）。入口・2 つの役の指示の値・返答の控え・出口を、port の値と place のファイルで組む。
指示の文は prompts/r1-comments.md と prompts/r1-minimality.md が持ち、ここは材料と値だけを組む。
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt

import eyekit        # lib/。独立の目の族の共通の部品
import jsonfile      # lib/
import oneline       # lib/

from src import files, material, report, scalars

NOT_GIVEN = "(not given)"                                   # 凍結した目的が渡っていない時の値（md の材料の行）
NO_CHECKS = "最後の試験の関門の証拠が渡っていない"          # 元 workflows/eyes/scripts/prep.py:87-92 の字
CHECKS_UNREAD = "入力 checks の証拠の文が読めない: {why}"
NO_INTAKE = "入口の控え intake.json が無いか読めない（入口の node が落ちた）"
UNREAD_INPUT = "入力が読めない: {why}"


# ---------------------------------------------------------------- 入口
def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def _port(name: str, read):
    """port 1 つを読む。読めなければ「入力 <名>: <訳>」の ValueError"""
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {oneline.one_line(e)}") from None


def _path(path) -> str:
    return str(path) if path is not None else ""


def _checks(raw) -> tuple[str, str]:
    """(最後の試験の関門の証拠の文の絶対パス, 無い訳)。渡っていない・読めない時は落とさず訳にする（R1 はそう書かれた材料で判じる）"""
    if _blank(raw):
        return "", NO_CHECKS
    try:
        return str(ports.file(raw)), ""
    except ValueError as e:
        return "", CHECKS_UNREAD.format(why=oneline.one_line(e))


def _read_ports(raw: dict) -> tuple[dict, list]:
    """port の値と、読めない port の訳の並び（「入力 <名>: <訳>」）"""
    doc, bad = {}, []
    readers = {
        "base": lambda v: ports.text(v).strip(),
        "purpose": lambda v: ports.text(v).strip(),
        "units": lambda v: [] if _blank(v) else ports.json(v, "shared:units.schema.json"),
        "judgment": lambda v: _path(ports.file(v)),
        "fixes": lambda v: [] if _blank(v) else ports.json(v, "r1-fixes.schema.json"),
        "x_scalars": lambda v: {} if _blank(v) else ports.json(v, "r1-scalars.schema.json"),
        "green": lambda v: True if _blank(v) else ports.flag(v),
        "after": lambda v: _path(ports.file(v)),
        "review": lambda v: {} if _blank(v) else ports.json(v, "shared:plan-verdict.schema.json"),
        "policy": lambda v: _path(ports.file(v)),
        "lang": lambda v: ports.text(v).strip(),
    }
    for name, read in readers.items():
        try:
            doc[name] = _port(name, lambda: read(raw.get(name)))
        except ValueError as e:
            bad.append(str(e))
    doc["checks"], doc["checks_why"] = _checks(raw.get("checks"))
    return doc, bad


def intake(out, repo, raw: dict, skip) -> dict:
    """port を読み、この block のファイルを名で消して累積差分を取り、intake.json を書く。返り {due, reason}。読めない port が在れば
    due: false と、どの port かを頭に付けた訳。差分が空・取れないことでは止めない（訳は差分の代わりのファイルに書き、役はそれを読む）。
    落ちない"""
    out = pathlib.Path(out)
    doc = {"due": False, "reason": ""}
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
            doc["scalars"] = scalars.scalars(diff.pop("text"), values["x_scalars"], diff["why"])
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


def comments_prompt(out, repo) -> dict:
    """1 段目の役（コメントの削除候補）の指示（docs/design/r1.md の 2.3）"""
    doc = _intake(out)
    values = {**eyekit.diff_values(doc["diff"]), "review_md": eyekit.review_md(repo)[0], "lang": prompt.lang(doc["lang"])}
    return prompt.emit(files.COMMENTS, values, {}, prompt.round_of(files.COMMENTS))


def minimality_prompt(out, repo) -> dict:
    """2 段目の役（冗長と最小性）の指示（docs/design/r1.md の 3.3）。前段の返答のファイルが在るかで段落を選ぶ"""
    out = pathlib.Path(out)
    doc = _intake(out)
    candidates = out / f"{files.COMMENTS}.json"
    concept, found = eyekit.maps(repo)
    values = {
        "after_section": eyekit.after_section(doc["after"] or None, doc["review"]),
        **concept,
        "candidates_file": str(candidates) if candidates.is_file() else "",
        "purpose": doc["purpose"] or NOT_GIVEN,
        **eyekit.diff_values(doc["diff"]),
        "units": material.units_text(doc["units"]),
        "judgment_file": doc["judgment"],
        "fixes": material.fixes_text(doc["fixes"]),
        "scalars": scalars.scalars_text(doc["scalars"]),
        "review_md": eyekit.review_md(repo)[0],
        "checks_file": doc["checks"],
        "checks_why": doc["checks_why"],
        "policy_body": eyekit.policy_body(doc["policy"] or None),
        **eyekit.status_values("r1"),
        "lang": prompt.lang(doc["lang"]),
    }
    when = {"candidates": candidates.is_file(), "judgment": bool(doc["judgment"]), "green": doc["green"] is True,
            "checks": bool(doc["checks"]), "policy": bool(doc["policy"]), "maps_found": found, "spawns": False}
    return prompt.emit(files.MINIMALITY, values, when, prompt.round_of(files.MINIMALITY))


# ---------------------------------------------------------------- 返答の控え
def save(out, name: str, reply: str) -> dict:
    """役の返答を字のまま place の <name>.json に書く。name は files.REPLIES の中だけ（place に知らない名のファイルを書かない）"""
    if name not in files.REPLIES:
        raise ValueError(f"返答の名 {name!r} は {'・'.join(files.REPLIES)} のどれでもない")
    (pathlib.Path(out) / f"{name}.json").write_text(ports.text(reply), encoding="utf-8")
    return {"saved": True}


# ---------------------------------------------------------------- 出口
def finish(out) -> dict:
    """place の intake.json と役の返答から出力を組み、finish.json にも書く（docs/design/r1.md の 4 節）"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    comments = eyekit.read_reply(out, files.COMMENTS)
    if not isinstance(doc, dict) or not doc.get("due"):
        why = (doc.get("reason") if isinstance(doc, dict) else "") or NO_INTAKE
        row = {"status": "unverifiable", "reason": UNREAD_INPUT.format(why=why)}
        got = {"ok": False, "status": "failed", "reason": why, "verdict": row, "questions": [], "report": [eyekit.headline("R1", row)]}
    else:
        reply, unread = eyekit.read_reply(out, files.MINIMALITY)
        row, took = eyekit.verdict_row("r1", reply, unread)
        got = {"ok": took, "status": "ran" if took else "failed", "reason": "" if took else row["reason"], "verdict": row,
               "questions": [], "report": report.lines(row, reply, comments)}
    try:   # Archon の JSON.parse が読めない NaN・Infinity は、控えを書く前に落とす（出口が落ちた形にする）
        json.dumps(got, allow_nan=False)
    except ValueError as e:
        raise ValueError(f"出力が JSON に書けない: {e}") from None
    jsonfile.write(out / files.FINISH, got)
    return got

