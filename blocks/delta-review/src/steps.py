"""差分の審査の block の script の node の中身（docs/design/delta-review.md の 6 節）。script は port の字を読んでここへ渡すだけ。

- intake: port を読み、この block のファイルを消し、材料を写し、審査が要るかを決め、要れば 1 回目の差分と材料を置く
- review_prompt・refix_prompt: 審査役・手直しの役の指示を prompts/<node>.md から組む（組めなければ errors.json に積んで落ちる）
- owed: n 回目の審査が義務を出したかを決め、出していれば手直しの材料と段の頭の木を置く
- cut2: 1 回目の手直しが fixed と答えた穴が在る時だけ、手直しだけの差分と 2 回目の材料を置く
"""
import json
import pathlib

import ports
import prompt

import jsonfile  # lib/
import leftovers  # lib/
import lens  # lib/
import oneline  # lib/
import report  # lib/
import rolekit  # lib/
import writelog  # lib/

from src import borrowed, cut, files, materials, review, touchup, verdicts


def round_input(raw) -> int:
    """script の入力 n（1 か 2）。ほかは名指して ValueError"""
    if str(raw) not in tuple(str(n) for n in files.ROUNDS):
        raise ValueError(f"入力 n は {' か '.join(str(n) for n in files.ROUNDS)}: {raw!r}")
    return int(raw)


def read_intake(place) -> dict:
    doc = jsonfile.read_or(pathlib.Path(place) / files.INTAKE)
    if not isinstance(doc, dict):
        raise ValueError(f"{files.INTAKE} が無いか読めない（入口の node が落ちた）")
    return doc


def broke(place, node: str, reason: str) -> None:
    """壊れた段の訳を errors.json に積む（finish が status: failed の理由にする）"""
    path = pathlib.Path(place) / files.ERRORS
    jsonfile.write(path, [*(jsonfile.read_or(path) or []), {"node": node, "reason": oneline.one_line(reason)}])


def guarded(place, node: str, compute, fallback: dict) -> dict:
    """落ちない node の本体: 例外は errors.json に積んで fallback を返す"""
    try:
        return compute()
    except Exception as error:  # noqa: BLE001
        broke(place, node, f"{type(error).__name__}: {error}")
        return fallback


# ---------------------------------------------------------------- 入口
def _port(name: str, read):
    try:
        return read()
    except ValueError as error:
        raise ValueError(f"入力 {name}: {error}") from None


def _tree_of(repo, base: str) -> str:
    if not base.strip():
        raise ValueError("空（修正の前の版を渡す）")
    try:
        return leftovers.git(repo, "rev-parse", "--verify", f"{base.strip()}^{{tree}}").strip()
    except leftovers.Unreadable:
        raise ValueError(f"版として読めない: {base.strip()!r}") from None


def _declared_at(repo, base: str) -> str:
    """対象の守りの宣言を読む commit。base が commit ならそれ、木だけなら今の HEAD（役は commit しないので run の間は動かない）。
    commit が 1 つも無ければ空（自分の一覧だけで守りを照らす）"""
    for rev in (base.strip(), "HEAD"):
        try:
            return leftovers.git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").strip()
        except leftovers.Unreadable:
            continue
    return ""


def intake(place, repo, *, base, plan, lens_rows, fix_reply, permits, plan_review, policy, request, lang) -> dict:
    place = pathlib.Path(place)
    for name in files.OWN_FILES:
        (place / name).unlink(missing_ok=True)
    for pattern in files.OWN_PROMPTS:
        for path in place.glob(pattern):
            path.unlink()
    doc = {"due": False, "failed": False, "reason": "", "base": "", "declared_at": "", "lens_error": "", "policy": "", "lang": prompt.lang(lang)}
    try:
        doc["base"] = _port("base", lambda: _tree_of(repo, ports.text(base)))
        doc["declared_at"] = _declared_at(repo, ports.text(base))
        scope = _port("plan", lambda: materials.scope(plan))
        reply = _port("fix_reply", lambda: materials.fix_reply(fix_reply))
        paths = _port("permits", lambda: materials.permit_paths(permits))
        review_of_plan = _port("plan_review", lambda: materials.plan_review(plan_review))
        found = _port("policy", lambda: ports.file(policy))
        _port("request", lambda: materials.request_copy(place, request))
        doc["lens_error"] = materials.lens_copy(place, lens_rows)
        doc["policy"] = str(found) if found is not None else ""
        if doc["policy"]:
            _port("policy", lambda: materials.policy_body(doc["policy"]))   # 読めない文書は入口で名指す
        jsonfile.write(place / files.SCOPE, scope)
        jsonfile.write(place / files.PERMITS, paths)
        materials.seal(place)
        if reply is not None:
            jsonfile.write(place / files.FIX_REPLY, reply)
        if review_of_plan is not None:
            jsonfile.write(place / files.PLAN_REVIEW, review_of_plan)
        writelog.open_here()
        need, why = cut.due(repo, doc["base"], reply)
        if not need:
            jsonfile.write(place / files.SKIPPED, {"reason": why})
            doc["reason"] = why
        else:
            cut.cut(place, 1, repo, doc["base"])
            cut.brief(place, 1, repo, doc["declared_at"], scope=scope, reply=reply, plan_review=review_of_plan, lens_error=doc["lens_error"])
            cut.freeze(place, 1, repo)
            doc["due"] = True
    except (ValueError, leftovers.Unreadable, OSError) as error:
        doc.update(due=False, failed=True, reason=oneline.one_line(error))
    jsonfile.write(place / files.INTAKE, doc)
    return {"due": doc["due"], "reason": doc["reason"]}


# ---------------------------------------------------------------- 指示
def _emit(place, node: str, values: dict, when: dict) -> dict:
    """prompt.emit。組めなければ（md と値の食い違い・借りた写しが固定と違う）理由を errors.json に積んでから落ちる"""
    try:
        return prompt.emit(node, values, when, prompt.round_of(node))
    except (prompt.PromptError, ValueError) as error:
        broke(place, node, f"指示が組めない: {error}")
        raise


def _faces_values(change: str) -> dict:
    return {"change": change, "copy": review.FACE_KINDS[0], "entrance": review.FACE_KINDS[1], "contract_drift": review.FACE_KINDS[2],
            "dead_path": review.FACE_KINDS[3], "scope_creep": review.FACE_KINDS[4], "regression": review.HUMAN_FACE_KINDS[0],
            "policy_kind": review.HUMAN_FACE_KINDS[1], "precedent": review.PLAN_ONLY_FACE_KINDS[-1], "min_key": review.MIN_KEY,
            "min_cite": review.MIN_CITE, "min_why": review.MIN_WHY, "min_none": review.NONE_MIN}


def review_prompt(place, n: int) -> dict:
    place = pathlib.Path(place)
    doc = read_intake(place)
    role = files.REVIEW[n]
    rejected = rolekit.rejected(place, role)
    d = cut.read_cut(place, n)
    values = {"rejection": rolekit.rejects_text(rejected), "diff_file": d["file"], "files": json.dumps(d["files"], ensure_ascii=False),
              "brief_file": str(place / files.review_brief(n)), "lang": doc["lang"], **_faces_values("fix" if n == 1 else "touch-up"),
              "policy_body": materials.policy_body(doc["policy"]) if doc["policy"] else ""}
    if n == 1:
        reply = place / files.FIX_REPLY
        try:
            seat = borrowed.review_values(brief_file=values["brief_file"], policy_file=doc["policy"], report_file=str(reply) if reply.is_file() else "",
                                          base=d["base"], head=d["rev"], diff_file=d["file"])
        except ValueError as error:
            broke(place, role, f"借りた写しが使えない: {error}")
            raise
        values.update(seat, failed=lens.STATES[2], not_routed=lens.STATES[3], absorbed=review.CLAIMED[1],
                      missing=verdicts.KINDS[0], extra=verdicts.KINDS[1], misunderstood=verdicts.KINDS[2], unverifiable=verdicts.KINDS[3],
                      pass_word=verdicts.COMPLIANCE[0], fail_word=verdicts.COMPLIANCE[1], not_applicable=verdicts.COMPLIANCE[3])
    else:
        values["fixed"] = review.CLAIMED[2]
    return _emit(place, role, values, {"rejected": bool(rejected), "first": n == 1, "policy": bool(doc["policy"])})


def refix_prompt(place, n: int) -> dict:
    place = pathlib.Path(place)
    doc = read_intake(place)
    role = files.REFIX[n]
    rejected = rolekit.rejected(place, role)
    scope = jsonfile.read_or(place / files.SCOPE) or {}
    items, permits = touchup.scope_lines(scope.get("plan_items") or [], touchup.permit_union(place))
    request = place / files.REQUEST
    try:
        seat = borrowed.refix_values()
    except ValueError as error:
        broke(place, role, f"借りた写しが使えない: {error}")
        raise
    values = {"rejection": rolekit.rejects_text(rejected), "policy_path": doc["policy"], "request_file": str(request) if request.is_file() else "",
              "scope_items": items, "scope_permits": permits, "brief_file": str(place / files.refix_brief(n)),
              "diff_file": cut.read_cut(place, n)["file"], "inner_word": report.INNER_FACE_KIND, "fixed": touchup.HANDLED[0],
              "declared": touchup.HANDLED[1], "min_how": touchup.MIN_HOW, "lang": doc["lang"], **seat}
    when = {"rejected": bool(rejected), "policy": bool(doc["policy"]), "request": request.is_file(), "scope": bool(items),
            "conflict": False, "docs": True, "prompts_kind": True, "config": True, "code": True, "spawns": False}
    return _emit(place, role, values, when)


# ---------------------------------------------------------------- 審査の後
def owed(place, n: int, repo) -> dict:
    """n 回目の審査が義務を出したかを決める。出していれば手直しの段の頭の木と材料を置く"""
    place = pathlib.Path(place)

    def compute() -> dict:
        record = jsonfile.read_or(place / files.review_record(n))
        if not isinstance(record, dict):
            return {"due": False, "reason": f"{n} 回目の審査が直す義務を出していない（審査を受けていない）"}
        if record.get("gave_up"):
            return {"due": False, "reason": f"{n} 回目の審査を諦めた"}
        if record.get("pass") is not False:
            return {"due": False, "reason": f"{n} 回目の審査が直す義務を出していない（通った）"}
        head = place / files.refix_head(n)
        if not head.is_file():
            jsonfile.write(head, {"tree": leftovers.snapshot(repo)})
        touchup.write_brief(place, n)
        return {"due": True, "reason": ""}

    return guarded(place, f"owed-{n}", compute, {"due": False, "reason": f"{n} 回目の手直しの支度が落ちた"})


def cut2(place, repo) -> dict:
    """1 回目の手直しが fixed と答えた穴が在る時だけ、手直しだけの差分（1 回目に固めた修正後の姿 → 今の作業ツリー）を切る"""
    place = pathlib.Path(place)

    def compute() -> dict:
        reply = jsonfile.read_or(place / files.refix_reply(1)) or {}
        handled = [h for h in reply.get("handled") or [] if isinstance(h, dict)]
        if not any(h.get("handled") == "fixed" for h in handled):
            return {"due": False, "reason": "1 回目の手直しが fixed と答えた穴が無い"}
        first = cut.read_cut(place, 1)
        cut.cut(place, 2, repo, first["rev"])
        cut.brief(place, 2, repo, read_intake(place)["declared_at"], scope={}, reply=None, plan_review=None, handled=handled)
        cut.freeze(place, 2, repo)
        return {"due": True, "reason": ""}

    return guarded(place, "cut-2", compute, {"due": False, "reason": "2 回目の差分を切れなかった"})
