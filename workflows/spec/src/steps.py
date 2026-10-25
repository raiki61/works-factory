"""spec の block の中身（docs/design/spec.md。今の judge の仕様の段と line の spec-check を、port の値で受ける形に写した物）。

mode write: 依頼が完成と言える要件と受け入れ条件のテストを書く役・別の目で穴を挙げる役・穴に答えて直す役の 3 つの輪、人の承認ノード、
承認の後の固めを回す。mode check: 固めた仕様の受け入れ条件のテストが承認の版から変わったかを照らす。指示の文は prompts/ の md が
持ち、ここは材料と値だけを組む。

place のファイルの名は src/files.py だけが持つ。
"""
from __future__ import annotations

import pathlib

import ports
import prompt
import requestrows

import accept     # lib/。status_keys
import oneline    # lib/
import rolekit    # lib/。輪の数え・却下の控え・出し直し
import stopby     # lib/。HUMAN

from src import check, files, gate, report, take


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


# ---------------------------------------------------------------- 入口
def intake(place, *, mode, request, pr_text, lang) -> dict:
    """port を読み、mode を決める。write なら place のこの block のファイルを消し、依頼の行を request.json に書く。check は place を
    消さない（check の include は自分の place を持つ）。返り {mode, go, reason}。読めなければ落ちず、go 偽と理由（write では
    止めの控えにも works:spec で書く）"""
    place = pathlib.Path(place)
    doc = {"mode": "", "go": False, "reason": "", "pr_text": "", "lang": ""}
    try:
        doc["mode"] = _port("mode", lambda: ports.choice(mode, files.MODES))
        if doc["mode"] == "write":
            for name in files.own_files():
                (place / name).unlink(missing_ok=True)
            for pattern in files.own_prompts():
                for path in place.glob(pattern):
                    path.unlink()
            rows = _port("request", lambda: requestrows.findings(request))
            doc.update(pr_text=ports.text(pr_text), lang=ports.text(lang).strip())
            files.write(place / files.REQUEST, rows)
        doc["go"] = True
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        doc["reason"] = oneline.one_line(f"仕様の段の支度が落ちた（{type(e).__name__}: {e}）")
        files.write_stop(place, files.STOP, doc["reason"])
    files.write(place / files.INTAKE, doc)
    return {"mode": doc["mode"], "go": doc["go"], "reason": doc["reason"]}


# ---------------------------------------------------------------- 指示
def prep(place, role: str, prev) -> dict:
    """役 role の 1 回目の指示を組む。前の周の受け付けが拒み、合わせた答えの控えが在れば、出し直しの役を起こすので指示は組まない
    （resubmit 真。fix_prep が組む）。返り {prompt, resubmit}"""
    place = pathlib.Path(place)
    if rolekit.resubmitting(place, files.ROLES[role], prev):
        return {"prompt": "", "resubmit": True}
    return {**_first_prompt(place, role), "resubmit": False}


def _first_prompt(place: pathlib.Path, role: str) -> dict:
    doc = files.need(place, files.INTAKE)
    nid = files.node_id(role)
    rejected = rolekit.rejected(place, files.ROLES[role])
    values = {"rejection": rolekit.rejects_text(rejected), "request_file": str(place / files.REQUEST), "pr_text": doc["pr_text"],
              "lang": prompt.lang(doc["lang"])}
    if role in ("review", "revise"):
        values["spec_file"] = str(files.role_file(place, "write"))
    if role == "review":
        values.update(zip(("missing", "ambiguous", "out_of_scope"), files.FACE_KINDS), min_why=files.MIN_WHY, min_reason=files.MIN_REASON)
    if role == "revise":
        values.update(review_file=str(files.role_file(place, "review")), absorbed=files.HANDLED[0], declared=files.HANDLED[1], min_how=files.MIN_HOW)
    # この block の役は Agent の道具を持たない（下請けを起こさない）ので、検索の決まりの段落 spawns は入れない
    when = {"rejected": bool(rejected), "pr_text": bool(doc["pr_text"].strip()), "spawns": False}
    return prompt.emit(nid, values, when, prompt.round_of(nid))


def fix_prompt(place, role: str) -> dict:
    """拒まれた後の出し直しの役の指示を組む（拒否の理由は最後の 1 件、合わせた前の答えの控えのパス）。返り {prompt}"""
    place = pathlib.Path(place)
    name = files.ROLES[role]
    rejected = rolekit.rejected(place, name)
    nid = files.node_id(role, fix=True)
    values = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(place, name))}
    return prompt.emit(nid, values, {"spawns": False}, prompt.round_of(nid))


# ---------------------------------------------------------------- 受け付け
def take_reply(place, role: str, status_guarded: bool, reply, fix_reply, repo) -> dict:
    """役の返答の受け付けの 1 回。出し直しの役の返答 fix_reply（直す欄だけ）は、前の答えの控えと欄ごとに合わせてから照らす。
    要る根の欄 files.REPLY_REQUIRED の欠けは合わせた後に拒む。
    返り {ok, done, reason, revise}"""
    name = files.ROLES[role]
    got = rolekit.resubmitted(place, name, reply, fix_reply, rolekit.merge_fields, required=files.REPLY_REQUIRED[role])
    keys = accept.status_keys(status_guarded)
    out = rolekit.accept_parsed(place, name, got, lambda r: take.take(place, role, r, repo, keys=keys))
    return {"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"]), "revise": bool(out.get("revise"))}


# ---------------------------------------------------------------- 承認ノード・固め
def ask(place, repo) -> dict:
    """承認ノードを開くか・文 {ask, message}。文を組めない誤りは works:spec の止めにして開かない"""
    place = pathlib.Path(place)
    try:
        return gate.ask(place, repo, ports.pointer(place / files.SPEC_ASK)["run_id"])
    except Exception as e:  # noqa: BLE001
        files.write_stop(place, files.STOP, f"仕様の承認ノードの文を組めない（{type(e).__name__}: {e}）")
        return {"ask": False, "message": ""}


def freeze_answer(place, repo, reply, user_env_dir: str) -> dict:
    """承認ノードの答えを受け、通す語なら受け入れ条件を走らせて仕様を固める。固められない誤りは works:spec の止めにする。
    受け入れ条件のコマンドを利用者の HOME・XDG に戻した印は user_env_dir（空なら place）に置く"""
    place = pathlib.Path(place)
    ports.drop_runner_env(user_env_dir.strip() or str(place))
    try:
        return gate.answer(place, repo, reply)
    except Exception as e:  # noqa: BLE001
        why = f"仕様を固められない（{type(e).__name__}: {e}）"
        files.write_stop(place, files.STOP, why)
        return {"go": False, "reason": why}


# ---------------------------------------------------------------- 照らし
def no_spec() -> dict:
    return {"questions": [check.NO_SPEC], "unchecked": True}


def check_failed(why: str) -> dict:
    return {"questions": [check.failed_question(why)], "unchecked": True}


# ---------------------------------------------------------------- 出口
def _pointer(place: pathlib.Path, name: str):
    return ports.pointer(place / name) if (place / name).is_file() else None


def failed(reason: str, stop_reason: str = files.STOP) -> dict:
    return {"ok": False, "status": "failed", "stop_reason": stop_reason, "reason": reason, "spec": None, "added_rows": None,
            "added_origin": "", "questions": [], "unchecked": False, "report": report.failed(reason)}


def finish(place, checked) -> dict:
    """block の返り。どの段が落ちても落ちない。write は stop.json と spec.json から、check は spec-check の返りから決める"""
    place = pathlib.Path(place)
    doc = files.read(place / files.INTAKE)
    if not isinstance(doc, dict):
        return failed("入口の控えが無い（入口の node が落ちた）")
    if doc.get("mode") == "check":
        return _finish_check(checked)
    stop = files.read_stop(place)
    spec = files.read(place / files.SPEC)
    if stop and stop["stop_reason"].startswith((stopby.HUMAN, files.FLAG_BY_PREFIX)):
        reason = str(stop.get("reason") or "")
        return {**failed(reason, stop["stop_reason"]), "status": "stopped", "report": report.stopped(reason)}
    if stop or not isinstance(spec, dict):
        return failed(str((stop or {}).get("reason") or doc.get("reason") or files.NOT_RUN))
    added = _pointer(place, files.ADDED_ROWS)
    return {"ok": True, "status": "approved", "stop_reason": "", "reason": "", "spec": _pointer(place, files.SPEC),
            "added_rows": added, "added_origin": files.ORIGIN if added else "", "questions": [], "unchecked": False,
            "report": report.approved(spec)}


def _finish_check(checked) -> dict:
    if not isinstance(checked, dict):
        checked = check_failed("照らしの node が返りを返さなかった")
    questions, unchecked = [str(q) for q in checked["questions"]], bool(checked["unchecked"])
    return {"ok": not unchecked, "status": "unchecked" if unchecked else "checked", "stop_reason": "", "reason": questions[0] if unchecked else "",
            "spec": None, "added_rows": None, "added_origin": "", "questions": questions, "unchecked": unchecked,
            "report": report.checked(questions, unchecked)}
