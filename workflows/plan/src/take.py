"""修正案の役の返答の受け付け（docs/design/plan.md の 5 節）。今の lib/planfile.py の take_plan・take_replan と、その部品の写し。

拒否は理由を全部 1 回で並べて {ok: False, reason}。通れば no を id に戻した返答を planmarks.split で works の欄と分け、p2.fix_plan.json・
plan-fields.json・reply.json・handoff.json の順に置く。どれかを置けなければ置いた物を消し、拒否に数えずに輪を止める
（{ok: False, halt: True, count: False, give_up: True}）。拒否の理由の文は日本語のまま（網の回まで拒まれた時に reason を通って報告に載り、出し直しの役の
指示に字のまま入る）。
"""
from __future__ import annotations

import copy
import json
import pathlib
import posixpath

import ports

import accept as accept_  # lib/
import converge   # lib/
import gatemarks  # lib/
import handoff    # lib/
import impact     # lib/
import jsonfile   # lib/
import planmarks  # lib/
import replan     # lib/
import rolekit    # lib/
import structmark  # lib/
import worldmark  # lib/

from src import files, steps

EMPTY_RECORD = {"round": 0, "passes": [], "outcome": None, "open": {}}


def pop_field(reply, names) -> tuple:
    """(names の欄を外した reply の写し, 外した欄 {名: 値})。reply は変えない。reply が dict でなければ写しと {}"""
    out = copy.deepcopy(reply)
    if not isinstance(out, dict):
        return out, {}
    return out, {k: out.pop(k) for k in tuple(names) if k in out}


def _section(head: str, lines) -> str:
    return head + "\n" + "\n".join(f"  - {g}" for g in lines) if lines else ""


# ---------------------------------------------------------------- 修正前の版
def base_test_texts(repo, rev: str) -> tuple:
    """修正前の版 rev に在ったテストの .py（名の慣習 impact.is_test の module）の中身 {パス: 中身} と、読めなかった物の並び
    （版が読めなければ ["<版>"]）"""
    try:
        names = steps._git(repo, "ls-tree", "-r", "--name-only", rev).splitlines()
    except OSError:
        return {}, ["<版>"]
    out, unread = {}, []
    for path in sorted(names):
        if path.endswith(".py") and impact.is_test(path) == "module":
            try:
                out[path] = steps._git(repo, "show", f"{rev}:{path}")
            except OSError:
                unread.append(path)
    return out, unread


def exists_at(repo, rev: str):
    """受け入れのテストの定義を版 rev の木で引く口（planmarks.gaps の exists）。版が引けなければ ValueError（『分からない』を在ると・無いとに倒さない）"""
    try:
        steps._git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    except OSError as e:
        raise ValueError(f"修正の起点の版 {rev} が引けない: {e}") from None
    cache: dict = {}

    def exists(test_id):
        path = posixpath.normpath(str(test_id).split("::", 1)[0])
        if path not in cache:
            try:
                cache[path] = steps._git(repo, "show", f"{rev}:{path}")
            except OSError:   # その版に無いファイル
                cache[path] = None
        return planmarks.line_in(cache[path], test_id) if cache[path] is not None else None
    return exists


# ---------------------------------------------------------------- 案の直し
def _replaced(whole, rows, plan) -> list:
    """承認済みの案の全体 whole の、rows の項目の番号の所に返答の項目 plan（rows と同じ並び）を差し替えた並び（whole は変えない）"""
    out = list(whole)
    for row, got in zip(rows, plan if isinstance(plan, list) else []):
        if 1 <= row["item"] <= len(out):
            out[row["item"] - 1] = got
    return out


def plan_errors(rows, reply, repo, exists, tables, whole) -> list:
    """修正案の役の直した項目の返答の誤りの行の全部（数・unit_keys の字・works の欄・項目の間の依存・構造と世界の解の行への答え・狭めない案）。
    rows は渡した項目の行（old を持つ）。whole は承認済みの案の全体で、依存と考えの住処の照らしは、直した番号の所に返答の項目を差し替えた並びに当てる。
    返答は unit_keys を字で写すので、depends_on[].unit も単位の字で書く"""
    plan = reply.get("plan") if isinstance(reply, dict) else None
    out = []
    if not isinstance(plan, list) or len(plan) != len(rows):
        out.append(f"plan[] は {len(rows)} 項目（貼った項目の数）")
    for i, (row, got) in enumerate(zip(rows, plan if isinstance(plan, list) else [])):
        want = row["old"].get("unit_keys")
        if not isinstance(got, dict) or got.get("unit_keys") != want:
            out.append(f"plan[{i}].unit_keys が貼った {json.dumps(want, ensure_ascii=False)} と違う（一字も変えずに写す）")
    if not replan._malformed(reply):
        out += planmarks.gaps(reply, pathlib.Path(repo), exists=exists)
        replaced = _replaced(whole, rows, plan)
        out += planmarks.depends_gaps(replaced)
        out += planmarks.home_gaps(replaced)
        out += planmarks.structure_gaps(reply.get("plan"), tables)
        out += gatemarks.narrow_gaps(planmarks.NODE, reply)
        out += gatemarks.recommend_gaps(planmarks.NODE, reply)
        out += gatemarks.plain_gaps(planmarks.NODE, reply)
    return out


def revised_fields(fields, rows, repo, *, base_tests=None) -> list:
    """直した項目（rows の行の new。決め手の欄は new_marks から戻す）を planmarks.split の欄に差し替えた項目の欄の並び。fields は書き換えない"""
    out = copy.deepcopy(fields)
    for row in rows:
        n = row["item"]
        if isinstance(row.get("new"), dict) and 1 <= n <= len(out):
            out[n - 1] = planmarks.split({"plan": [replan.new_item(row)]}, pathlib.Path(repo), base_tests=base_tests)[1][0]
    return out


# ---------------------------------------------------------------- 控えを置く・止める
MACHINE_ROWS_HALT = "往復の記録から差し込んだ閉じた項目の行が受け付けの形に合わない（機械の誤りなので役へ返さず止める）:"


def halt(folder, why: str, *, held: bool = False) -> dict:
    """輪を止める返り {ok: False, halt: True, count: False, give_up: True, reason}（拒否ではない。役に出し直させず、回数に数えない）。
    止める訳を round.json の why に残す（出口は halt の周を failed と読み、held も真の周は held と読む）。書けなくても止める訳は返す"""
    try:
        files.write_json(pathlib.Path(folder) / files.ROUND, {**files.read_round(folder), "why": why, "halt": True, **({"held": True} if held else {})})
    except OSError as again:
        why += f"（止めの控えも書けなかった: {again}）"
    return {"ok": False, "halt": True, "count": False, "give_up": True, "reason": why}


def save(folder, k: int, plan: dict, fields: list, bare: dict, *, amended=None, memo=None) -> dict:
    """受けた案の控えを置く（案の控えの後に、引き継ぎのメモ memo を handoff.save で置く。memo が空なら周のフォルダに残る前のメモを消す）。
    置けなければ置いた控えを消し、置けなかった控えの名を round.json の why に残して、輪を止める（halt。欄の無い案で進ませない）"""
    folder = pathlib.Path(folder)
    note = handoff.path_of(folder)
    steps_ = [(files.FIX_PLAN, lambda: jsonfile.write(folder / files.FIX_PLAN, bare, parents=True)),
              (files.FIELDS, lambda: planmarks.save(folder, k, fields, amended=amended)),
              (files.REPLY, lambda: jsonfile.write(folder / files.REPLY, plan, parents=True)),
              (note.name, lambda: handoff.save(folder, memo))]
    for name, step in steps_:
        try:
            step()
        except OSError as e:
            why = f"受けた修正案の控え {name} を置けない: {e}"
            try:
                for done, _ in steps_:
                    (folder / done).unlink(missing_ok=True)
            except OSError as again:   # 巻き戻しも書けなくても、止める訳は返す（出口は round.json に無ければ rejects の訳で failed を返す）
                why += f"（巻き戻しも書けなかった: {again}）"
            return halt(folder, why)
    return {"ok": True, "reason": ""}


def machine_row_errors(record: dict, whole: list, plan: dict, repo) -> list[str]:
    """往復の記録から機械が差し込んだ閉じた項目の行（役が直せない行）に帰る受け付けの誤り。行を 1 本ずつ、受け付けの形（planmarks.gaps）・
    narrows の決め手と狭めない案（gatemarks.narrow_gaps）・推し（gatemarks.recommend_gaps）に当て、同じ照らしを案の全体 plan に当てた誤りと
    交わる（1 本の誤りの文の位置 plan[0] は、その行の whole の中の位置に読み替える）。項目の間の照らし（足すテストの宣言・範囲の重なり）を
    同じ 1 本に当てた分は引く（役の行の変化が生む誤りなので、今どおり役へ拒む）。返りは「閉じた項目 <控えの番号>: <誤り>」の行"""
    closed = converge.closed_ids(record)
    rows = [(n, it["id"], it["row"]) for n, it in enumerate(record.get("plan") or [], 1)
            if isinstance(it, dict) and it.get("id") in closed and "row" in it]
    if not rows:
        return []
    at = {converge.item_id(w.get("unit_keys")): i for i, w in enumerate(whole) if isinstance(w, dict)}
    shape = set(planmarks.gaps(plan, pathlib.Path(repo)))
    narrow = set(gatemarks.narrow_gaps(planmarks.NODE, plan))
    recommend = set(gatemarks.recommend_gaps(planmarks.NODE, plan))
    out = []
    for n, item_id, row in rows:
        if item_id not in at:
            continue
        one = {"plan": [row]}
        alone = set(planmarks.gaps(one, pathlib.Path(repo))) - set(planmarks._added_test_gaps([row])) - set(planmarks._scope_overlaps([row]))
        here = f"plan[{at[item_id]}]"
        for got, whole_errors in ((alone, shape), (set(gatemarks.narrow_gaps(planmarks.NODE, one)), narrow),
                                  (set(gatemarks.recommend_gaps(planmarks.NODE, one)), recommend)):
            out += [f"閉じた項目 {n}: {e}" for e in sorted(e.replace("plan[0]", here) for e in got) if e in whole_errors]
    return out


def role_rows(rows: list, whole: list) -> list:
    """案の全体 whole の、往復の記録から機械が差し込んだ行（役の返答の行 rows のどれでもない行）を {} に替えた並び（位置は変えない）。
    人に聞く文の照らし（gatemarks.plain_gaps）は役の書いた行だけに当てる（照らしを足す前の往復の記録の行が run の中の参照を持っていても、
    役は差し込まれた行を直せず、止める誤りでもない）。項目の id でなく位置で見分けるので、閉じた項目と同じ単位で役が書いた行も照らす"""
    mine = {id(r) for r in rows}
    return [w if id(w) in mine else {} for w in whole]


# ---------------------------------------------------------------- 往復の記録
def bare_record(record: dict) -> dict:
    """往復の記録 record の写しで、案の行 row を役が書く形に戻し、hash を戻した row で付け直した物。閉じた項目を差し込む・前のまま
    書いた閉じた項目を見分ける・出し直しの控えに書く行を、役が書く形に揃える（役の書いた欄の照らしは緩めない）。row は事前審査が
    planmarks.joined で欄の行を重ね、narrows の行の決め手の欄を外した物なので、機械が足した欄（rewrite_tests の各行の範囲 limit。
    planmarks.split が欄の行に足す。#845）を外し、事前審査が converge.PLAN_MARKS に添えた決め手の欄を narrows の行に戻す（#849）"""
    out = copy.deepcopy(record)
    for it in out.get("plan") or []:
        row = it.get("row") if isinstance(it, dict) else None
        if not isinstance(row, dict):
            continue
        rewrites = row.get("rewrite_tests")
        for r in rewrites if isinstance(rewrites, list) else []:
            if isinstance(r, dict):
                r.pop("limit", None)
        narrows, marks = row.get("narrows"), it.get(converge.PLAN_MARKS)
        if isinstance(narrows, list) and isinstance(marks, list):
            row["narrows"] = [gatemarks.joined(n, m) if isinstance(n, dict) else n for n, m in zip(narrows, marks)] + narrows[len(marks):]
        it["hash"] = converge.item_hash(row)
    return out


# ---------------------------------------------------------------- 受け付け
def take_plan(folder, ctx: dict, *, judgment, reply, repo, tables, base_rev: str, keys=accept_.TREE_KEYS) -> dict:
    """修正案の役の返答（形 plan）を受け付ける。役が作業ツリーを動かしていれば先にそれだけで拒む。拒否は理由を全部 1 回で並べて
    {ok: False, reason}。通れば p2.fix_plan.json・plan-fields.json・reply.json・handoff.json を置いて {ok: True, reason: ""}。
    返答の欄 whole_plan と handoff は照らす前に外す。往復の記録（ctx の prior.record）が在れば block_answers を外して前の往復の答えの要る穴への答えを
    照らし、返答に無い項目に前の往復の行を差し込んだ案の全体を照らす（whole_plan を立てた答えは案の全部なので、閉じた項目の行だけを差し込む）。
    差し込んだ案の全体は、次の出し直しを合わせる元の控え rolekit.candidate_path にも書く。返答から捨てた閉じた項目の行は trace に converge.DROPPED_OP"""
    folder = pathlib.Path(folder)
    why = steps.moved(folder / files.TREE, repo, keys)
    if why:
        return {"ok": False, "reason": why}
    given = reply
    reply, mark = pop_field(reply, (steps.WHOLE_PLAN,))
    whole_plan = mark.get(steps.WHOLE_PLAN) is True
    reply, note = pop_field(reply, (handoff.FIELD,))
    memo = note.get(handoff.FIELD)
    if replan._malformed(reply):
        return {"ok": False, "reason": steps.MALFORMED_REJECT}
    record = bare_record((ctx.get("prior") or {}).get("record") or EMPTY_RECORD)
    bare, answers = converge.split("plan-revise", reply)
    got = steps.named(bare, steps.round_slots(folder, judgment))
    whole, closed, dropped = converge.splice(record, got["plan"], fill=not whole_plan)
    if record["passes"]:
        jsonfile.write(rolekit.candidate_path(folder, files.ROLE), {**given, "plan": whole}, indent=2)
    plan = {**got, "plan": whole}
    owed, opened, _ = steps.plan_slots(judgment)
    shut = set(steps.shut(judgment, plan))
    allowed = list(range(1, len(steps.slots(judgment)) + 1))
    reasons = [
        _section(steps.ANSWERS_REJECT, converge.answer_gaps(record, answers) + converge.fixed_unchanged(record, whole, answers)),
        _section(steps.CLOSED_REJECT, closed),
        _section(steps.NO_NARROW_REJECT, gatemarks.narrow_gaps(planmarks.NODE, plan)),
        _section(steps.RECOMMEND_REJECT, gatemarks.recommend_gaps(planmarks.NODE, plan)),
        _section(steps.PLAIN_REJECT, gatemarks.plain_gaps(planmarks.NODE, {**plan, "plan": role_rows(got["plan"], whole)})),
        _section(f"{steps.NOT_OWED_REJECT} {allowed}。外す単位:", steps.not_allowed(judgment, plan)),
        _section(f"{steps.COVERS_REJECT} {allowed}:", steps.fix_plan_covers_units(
            [{**p, "unit_keys": [k for k in p["unit_keys"] if k not in shut]} if isinstance(p.get("unit_keys"), list) else p
             for p in whole], owed, opened)),
        _section(planmarks.REJECT, planmarks.gaps(plan, pathlib.Path(repo)) + planmarks.home_gaps(whole)),
        _section(planmarks.DEPENDS_REJECT, planmarks.depends_gaps(whole)),
        _section(planmarks.STRUCTURE_REJECT, planmarks.structure_gaps(whole, tables)),
    ]
    machine = machine_row_errors(record, whole, plan, repo)
    if machine:
        return halt(folder, _section(MACHINE_ROWS_HALT, machine))
    reason = "\n".join(r for r in reasons if r)
    if reason:
        return {"ok": False, "reason": reason}
    texts, unread = base_test_texts(repo, base_rev or "HEAD")
    if unread:
        planmarks.append_trace(folder, steps.BASE_TESTS_UNREAD_OP, rev=base_rev or "HEAD", unread=unread)
    out, fields = planmarks.split(plan, pathlib.Path(repo), base_tests=texts)
    extra = {converge.ANSWERS: answers} if record["passes"] else {}
    k = ctx["round"]
    saved = save(folder, k, {**plan, **extra}, fields, {**out, **extra}, memo=memo)
    if saved["ok"]:
        for item_id in dropped:
            planmarks.append_trace(folder, converge.DROPPED_OP, round=k, pass_=len(record["passes"]) + 1, id=item_id)
    return saved


def take_replan(folder, ctx: dict, *, reply, repo, tables, base_rev: str, keys=accept_.TREE_KEYS) -> dict:
    """修正案の役の直した項目の返答（形 replan）を受け付ける。拒否は REPLAN_REJECT と誤りの全部。通れば replan.json（行は replan.TRIP_KEYS の形。
    contract_changed・widened は事実だけ）と、直した項目を差し替えた案の全体を p2.fix_plan.json・plan-fields.json（amended に直した項目の核の欄）・
    reply.json に書き、trace に planmarks.AMEND_OP を書く。返答の欄 handoff は take_plan と同じく照らす前に外し、この周の handoff.json に書く。
    直す元の案は prior.reply、前の周の欄は prior.fields"""
    folder = pathlib.Path(folder)
    why = steps.moved(folder / files.TREE, repo, keys)
    if why:
        return {"ok": False, "reason": why}
    reply, note = pop_field(reply, (handoff.FIELD,))
    memo = note.get(handoff.FIELD)
    prior = ctx.get("prior")
    old = steps.prior_rows(ctx)
    if prior is None or not old:
        return {"ok": False, "reason": f"{steps.REPLAN_REJECT}\n  - 直す元の承認済みの修正案が無い"}
    items = files.read_round(folder)["items"]
    rows = [{**dict.fromkeys(replan.TRIP_KEYS), "item": n, "units": list(old[n - 1].get("unit_keys") or []),
             "old": copy.deepcopy(old[n - 1])} for n in items if 1 <= n <= len(old)]
    rev = base_rev or "HEAD"
    try:
        errs = plan_errors(rows, reply, repo, exists_at(repo, rev), tables, old)
    except ValueError as e:
        errs = [str(e)]
    if errs:
        return {"ok": False, "reason": _section(steps.REPLAN_REJECT, errs)}
    for row, got in zip(rows, reply["plan"]):
        bare, row_marks = gatemarks.split(planmarks.NODE, {"plan": [got]})
        row["new"], row["new_marks"] = bare["plan"][0], row_marks[0]
        before, after = replan.bare(row["old"]), replan.bare(replan.new_item(row))
        row["contract_changed"] = planmarks.contract_diff(before, after)
        row["widened"] = planmarks.widened(before, after) if row["contract_changed"] else None
    texts, unread = base_test_texts(repo, rev)
    if unread:
        planmarks.append_trace(folder, steps.BASE_TESTS_UNREAD_OP, rev=rev, unread=unread)
    kept = jsonfile.read_or(prior["fields"], {})
    fields = revised_fields(kept.get("fields") or [], rows, repo, base_tests=texts)
    amended = {int(n): core for n, core in (kept.get(planmarks.AMENDED_KEY) or {}).items()}
    whole = copy.deepcopy(old)
    for row in rows:
        it = replan.new_item(row)
        whole[row["item"] - 1] = it
        amended[row["item"]] = {k: it[k] for k in planmarks.CORE_KEYS if k in it}
    out, _ = planmarks.split({"plan": whole}, pathlib.Path(repo))
    k = ctx["round"]
    saved = save(folder, k, {"plan": whole}, fields, out, amended=dict(sorted(amended.items())), memo=memo)
    if not saved["ok"]:
        return saved
    planmarks.append_trace(folder, planmarks.AMEND_OP, round=k, items=sorted(row["item"] for row in rows))
    files.write_json(folder / files.REPLAN, {"round": k, "items": rows})
    return saved


# ---------------------------------------------------------------- 出し直しを前の答えと合わせる
def merge_plan_items(old: list, new: list, slot_list: list) -> list:
    """前の案の項目 old に出し直しの項目 new（どちらも named で単位の名に戻した物）を合わせた並び: unit_keys が 1 つでも重なる前の
    項目は消え、出し直しの項目がその前の項目の最初の位置に入る（同じ位置に入る出し直しの項目は出し直しの順）。どれとも重ならない
    出し直しの項目は後ろに足す。今の周に直す単位 slot_list を 1 つも持たない前の項目は、受け付けが必ず拒む物なので消し、ほかの
    重ならない前の項目は残す。単位は converge.planned_units と同じく字にして比べる"""
    units = [converge.planned_units([it]) for it in new]
    hit = [[i for i, it in enumerate(old) if converge.planned_units([it]) & mine] for mine in units]
    known = {str(k) for k in slot_list}
    gone = {i for rows in hit for i in rows} | {i for i, it in enumerate(old) if not converge.planned_units([it]) & known}
    out = []
    for i, it in enumerate(old):
        out += [new[j] for j, rows in enumerate(hit) if rows and rows[0] == i]
        if i not in gone:
            out.append(it)
    return out + [new[j] for j, rows in enumerate(hit) if not rows]


def merge_resubmit(prev: dict, part: dict, slot_list: list) -> dict:
    """前の回の答え prev に修正案（形 plan）の出し直し part を合わせた答え。両方の unit_keys を、受け付けと同じく named で今の周の
    単位 slot_list の名に戻してから合わせる。欄は rolekit.merge_fields で置き換え、plan だけは whole_plan が偽で両方が list なら
    merge_plan_items で合わせる。whole_plan は一度真になれば控えに残り（この後の出し直しも全部の案に合わせる）、take_plan が外して読む"""
    prev, part = steps.named(prev, slot_list), steps.named(part, slot_list)
    whole = part.get(steps.WHOLE_PLAN) is True
    out = rolekit.merge_fields(prev, part)
    out.pop(steps.WHOLE_PLAN, None)
    if not whole and isinstance(prev.get("plan"), list) and isinstance(part.get("plan"), list):
        out["plan"] = merge_plan_items(prev["plan"], part["plan"], slot_list)
    return {**out, steps.WHOLE_PLAN: True} if whole or prev.get(steps.WHOLE_PLAN) is True else out


def merge_replan_resubmit(prev: dict, part: dict) -> dict:
    """前の回の答え prev に修正案（形 replan）の出し直し part を合わせた答え。形 replan の受け付けは項目を貼った位置で照らすので、
    plan は項目で合わせずに丸ごと置き換える（rolekit.merge_fields。whole_plan は読まずに外す）"""
    return rolekit.merge_fields(prev, {k: v for k, v in part.items() if k != steps.WHOLE_PLAN})


# ---------------------------------------------------------------- 受け付けの 1 回
def accept(place, repo, reply, fix_reply) -> dict:
    """受け付けの 1 回（docs/design/plan.md の 4 節 plan_accept）。周を読む → 拒否の控えが読めなければ照らさずに done の拒否 → 出し直しを前の答えと
    合わせる → take → 控えに積む。返り {ok, done, give_up, reason, attempt}"""
    place = pathlib.Path(place)
    folder, ctx = steps.load(place)
    tables = [planmarks.design_need(structmark.dirty(ctx["structure"] or None)), worldmark.need(_world_rows(ctx))]
    mode, keys = ctx["mode"], accept_.status_keys("true")   # Archon の状態の照らしと重なる git status の行は比べない
    n, stopped = rolekit.current_round(folder, files.ROLE)
    if stopped:
        return {**rolekit.round_outcome(stopped), "attempt": 0}
    if mode == "replan":
        merge = merge_replan_resubmit
    else:
        judgment = steps.read_judgment(ctx)
        merge = lambda prev, part: merge_resubmit(prev, part, steps.round_slots(folder, judgment))   # noqa: E731
    unread = steps.cannot_read(fix_reply if fix_reply is not None else reply)
    if unread:   # 照らせと指された文書を役が読めない: 要約から組み直させず、拒まずに止めて人に返す
        out = halt(folder, steps.CANNOT_READ_HOLD.format(rows=unread), held=True)
    else:
        got_reply, why = rolekit.resubmitted(folder, files.ROLE, reply, fix_reply, merge, required=files.REQUIRED,
                                             fix_only=(steps.WHOLE_PLAN,))
        if got_reply is None:
            out = {"ok": False, "reason": why}
        elif mode == "replan":
            out = take_replan(folder, ctx, reply=got_reply, repo=repo, tables=tables, base_rev=ctx["base"], keys=keys)
        else:
            out = take_plan(folder, ctx, judgment=judgment, reply=got_reply, repo=repo, tables=tables, base_rev=ctx["base"], keys=keys)
    got = rolekit.accept_round(folder, files.ROLE, None, lambda _: out, net=True)
    tries = n - (1 if out.get("halt") else 0)   # 受けた・拒んだ回は今の回、halt は前の拒否の数
    return {**rolekit.round_outcome(got), "attempt": tries}


def _world_rows(ctx: dict) -> list:
    return worldmark.rows(ctx["world_rows"]) if ctx.get("world_rows") else []
