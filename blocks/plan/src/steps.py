"""plan の block の中身のうち、入口（周を開く）・直す義務の数え・案に入れてよい単位・判定の処方・波及の一覧・出口（docs/design/plan.md の 4 節）。
今の lib/planfile.py と lib/planblk.py の修正案の役の部分を、port の値で受ける形に写した物。指示の文は prompts/ の md が持ち、ここは値と、
受け付けが拒否に使う日本語の理由（README の 5.3）だけを組む。

place のファイルの名と、標準ライブラリだけの落ちない道は src/files.py。
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess

import ports

import accept     # lib/
import carry      # lib/
import converge   # lib/
import gatemarks  # lib/
import handoff    # lib/
import judgmark   # lib/。開いた単位の選びと、直す義務・周が役を起こすかの決め（diagnose・verify・fix・line と共に読む判定の行の形）
from judgmark import (LEDGER, NOTHING_OWED, PLAN_STUCK, STUCK_WHY, held_why, is_open, plan_slots, slots, units_of,   # noqa: F401
                      plan_stuck_reason as stuck_reason)
import jsonfile   # lib/
import planmarks  # lib/
import rolekit    # lib/
import structmark  # lib/
import worldmark  # lib/

from src import files, ripple

RUNTIME_COPY_DIRS = ((ports.RUNTIME_COPY,),)   # 波及の一覧が飛ぶ、Archon が作業ツリーに写す置き場（lib/ の boundary.RUNTIME_COPY_DIRS と同じ値）
WHOLE_PLAN = "whole_plan"          # 出し直しの役の型だけが持つ欄。真なら plan が前の案を丸ごと置き換える（合わせた後も控えに残す）
BASE_TESTS_UNREAD_OP = "writes_base_tests_unread"   # 修正前の版のテストを読み損ねた trace の行 {rev, unread}

# 受け付けと出口の文。拒否の理由は日本語のまま（網の回まで拒まれた時に reason を通って報告に載り、出し直しの役の指示に字のまま入る）
COVERS_REJECT = "単位の網羅に誤りが在る（直す義務の単位は全部、どれか 1 つの項目にちょうど 1 度入れる）。案に入れてよい no は"
MALFORMED_REJECT = "修正案の返答の形が崩れている（plan は項目の object の配列で、各項目の narrows は配列）。指示書の JSON Schema に合う形で出し直せ"
NO_ROWS = "申し出と裁定の行が見つからない（conflicts の中に、この項目を名指す行が無い）"
NO_NARROW_REJECT = (f"narrows の行に狭めない案を探した結果（{gatemarks.NO_NARROW}）が無いか短い（直して出し直せ）。狭めを避ける形が"
                    "在ればそれを案に採ってその行を消し、無い時だけ、どの形を当たりなぜ採れないかを書け:")
RECOMMEND_REJECT = (f"承認ノードの項目の行の推し（{gatemarks.RECOMMEND}）の形が崩れている（直して出し直せ）。"
                    f"書くなら {gatemarks.RECOMMEND_SHAPE} の形で:")
REPLAN_REJECT = "直した項目の返答に誤りが在る（下の行を全部直して出し直せ）:"   # lib/replan.py の REPLAN_REJECT と同じ字（案の直しの拒否の頭）
NOT_OWED_REJECT = "案に、直す義務の無い単位が入っている（nit・info・defer など。受け付けが受けない）。案から外せ。案に入れてよい no（必ず入れる物を含む）は"
ANSWERS_REJECT = "答えの要る穴への答えに誤りが在る（下の行を全部直して出し直せ）:"
CLOSED_REJECT = "閉じた・開いた項目の行が合わない（下の行を直して出し直せ）:"
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "
NO_TREE = "役を起こす前の作業ツリーの控え {name} が無い（支度のノードが走っていない）"
PLAN_GAVE_UP_WHY = f"修正案の役の直しが受け付けの網 {rolekit.NET_AFTER} 回まで拒まれ続けた: {{reason}}"


def _git(repo, *args) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise OSError(p.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} が終了コード {p.returncode}")
    try:
        return p.stdout.decode("utf-8")
    except UnicodeDecodeError as e:
        raise OSError(f"git {args[0]} の出力が utf-8 で読めない: {e}") from None


def rows_of(doc, key: str) -> list:
    got = doc.get(key) if isinstance(doc, dict) else None
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


# ---------------------------------------------------------------- port の値を解く
def nested_file(value, folder, name: str):
    """入れ子の値（prior の欄）のパス。pointer の object と字（パス）は解き、ほかの値は周のフォルダ folder に name で写しを書いてそのパス。
    null は None"""
    if value is None:
        return None
    if isinstance(value, dict) and value.get("type") == ports.POINTER_TYPE:
        return ports.file(json.dumps(value))
    if isinstance(value, str):
        return ports.file(value)
    return files.write_json(pathlib.Path(folder) / name, value)


def _located(raw: str, schema: str, folder, name: str):
    """pointer・パス・値のどれかで渡された JSON の入力を (値, パス) に。値で渡された物は周のフォルダに name で写しを書く"""
    value = ports.json(raw, schema)
    try:
        path = ports.file(raw)
    except ValueError:   # 値そのもの
        path = None
    return value, path if path is not None else files.write_json(pathlib.Path(folder) / name, value)


def _optional_file(raw, name: str, unread: list):
    try:
        path = ports.file(raw)
    except ValueError as e:
        unread.append(f"{name}: {e}")
        return ""
    return str(path) if path else ""


def _optional_json(raw, schema: str, name: str, unread: list, default):
    try:
        text = ports.text(raw)
        return ports.json(text, schema) if text.strip() else default
    except ValueError as e:
        unread.append(f"{name}: {e}")
        return default


def _prior(raw, folder) -> dict | None:
    """port prior を値に。空は None（前の周が無い）。欄はパスにそろえる（pointer・パス・値のどれでも受ける）。読めなければ ValueError"""
    text = ports.text(raw)
    if not text.strip():
        return None
    doc = ports.json(text, "plan-prior.schema.json")
    out = {"round": doc["round"], "record": doc.get("record")}
    for field, name in files.PRIOR_COPIES.items():
        try:
            out[field] = nested_file(doc.get(field), folder, name)
        except ValueError:
            if field in ("reply", "fields"):
                raise
            out[field] = None   # 無い指摘・前の周の控えは『受けていない』と読んで進む（今と同じ）
        out[field] = str(out[field]) if out[field] is not None else None
    if out["reply"] is None or out["fields"] is None:
        raise ValueError("prior の reply・fields が無い")
    out["handoffs"] = []
    for row in doc.get("handoffs") or []:
        try:
            path = nested_file(row.get("handoff"), folder, f"prior-handoff-r{row['round']}.json")
        except ValueError:
            path = None   # 控えが無い周は『メモ無し』と名指す（今と同じ）
        out["handoffs"].append({"round": row["round"], "handoff": str(path) if path else None})
    return out


# ---------------------------------------------------------------- 入口
def _unreadable(mode: str, why: list, unread: list, name: str, error, *, holds: bool = False) -> None:
    """形 plan で読めない judgment と、どちらの形でも読めない world_rows（holds）は役を起こさない訳に、形 replan の judgment は読めなかった入力に残す"""
    if mode == "plan" or holds:
        why.append(f"{name} が読めない（{error}）")
    else:
        unread.append(f"{name}: {error}")


def intake(place, repo, k: int, raw: dict) -> dict:
    """全部の port を読み、周を開く（docs/design/plan.md の 4 節）。raw は port の名 → INPUTS_<名> の字。返り {go, mode, round, reason}。
    周のフォルダ r<k>/（k は files.next_round が決めた周の番号。prior が読めない時は在る周の一番大きい番号 + 1 で、前の周のフォルダを開き直さない）
    を作り、在れば名のファイルだけを消す。読めない port の扱い: 形 plan の judgment と、どちらの形でも world_rows・prior・ruling は役を起こさず（go 偽）、ほかは intake.json の unread に名指して役を起こす"""
    place = pathlib.Path(place)
    why: list[str] = []
    unread: list[str] = []
    ruling: list = []
    try:
        text = ports.text(raw["ruling"])
        ruling = ports.json(text, "replan-items.schema.json") if text.strip() else []
    except ValueError as e:
        why.append(f"ruling が読めない（{e}）")
    mode = "replan" if ruling else "plan"
    folder = files.round_dir(place, k)
    folder.mkdir(parents=True, exist_ok=True)
    for brief in files.read_round(folder).get("items") or []:
        (folder / files.ITEM_BRIEF.format(no=brief)).unlink(missing_ok=True)
    for name in files.OWN_FILES:
        (folder / name).unlink(missing_ok=True)
    files.write_json(place / files.CURRENT_ROUND, {"round": k})
    prior = None
    if not why:
        try:
            prior = _prior(raw["prior"], folder)
        except (ValueError, KeyError, OSError) as e:
            why.append(f"prior が読めない（{e}）")
    ctx = {"round": k, "mode": mode, "ruling": ruling, "prior": prior}
    # 判定
    judgment_text = ports.text(raw["judgment"])
    judgment_doc = None
    ctx["judgment"] = ""
    if judgment_text.strip():
        try:
            judgment_doc, path = _located(judgment_text, "shared:judgment.schema.json", folder, files.JUDGMENT_COPY)
            ctx["judgment"] = str(path)
        except ValueError as e:
            _unreadable(mode, why, unread, "judgment", e)
    elif mode == "plan":
        why.append("judgment が読めない（空）")
    for name in ("answer_ties", "materials", "verify", "excluded", "depth_record", "decisions", "structure", "spec", "policy", "conflicts"):
        ctx[name] = _optional_file(raw[name], name, unread)
    ctx["world_rows"] = ""
    try:
        path = ports.file(raw["world_rows"])
        if path:
            worldmark.rows(str(path))   # 行の形を先に照らす（読めなければ ValueError）
            ctx["world_rows"] = str(path)
    except ValueError as e:
        _unreadable(mode, why, unread, "world_rows", e, holds=True)
    ctx["units"] = _optional_json(raw["units"], "unit-catalog.schema.json", "units", unread, [])
    ctx["answers"] = _optional_json(raw["answers"], "request-answers.schema.json", "answers", unread, [])
    ctx["prior_failures"] = _optional_json(raw["prior_failures"], "shared:prior-failures.schema.json", "prior_failures", unread, [])
    try:
        ctx["takes_push"] = ports.flag(raw["takes_push"])
    except ValueError as e:
        unread.append(f"takes_push: {e}")
        ctx["takes_push"] = False
    for name in ("base", "review_rev", "diff_base", "lang"):
        ctx[name] = ports.text(raw[name]).strip()
    try:
        carry.place_prior(folder, ctx["prior_failures"])
    except ValueError as e:
        unread.append(f"prior_failures: {e}")
    ctx["unread"] = unread
    items: list = []
    if not why and mode == "plan":
        judgment = with_ledger(ctx, judgment_doc)
        held = held_why(judgment)
        if held:
            why.append(held)
        else:
            files.write_json(folder / files.SLOTS, slots(judgment))
    elif not why:
        old = rows_of(jsonfile.read_or(prior["reply"]) if prior else None, "plan")
        if prior is None:
            why.append("直す元の承認済みの修正案が無い")
        else:
            items, bad = planmarks.handed(ruling, len(old))
            if bad:
                why.append(bad)
    reason = "。".join(why)
    files.write_json(folder / files.INTAKE, ctx)
    files.write_json(folder / files.ROUND, {"round": k, "mode": mode, "go": not reason, "why": reason, "items": items})
    return {"go": not reason, "mode": mode, "round": k, "reason": reason}


def load(place) -> tuple:
    """(周のフォルダ, intake.json の値)。入口が落ちた周は読めず ValueError"""
    folder = files.current_dir(place)
    ctx = files.read_json(folder / files.INTAKE)
    if not isinstance(ctx, dict):
        raise ValueError(f"{folder / files.INTAKE} が無いか読めない（入口が落ちた）")
    return folder, ctx


def with_ledger(ctx: dict, doc) -> dict | None:
    """判定の dict に、直す義務の数え（gatemarks.duty）が読む問いの台帳の見え方を添える（judgmark.with_ledger）: 依頼の answers と、結び・素材の
    状態のファイルと、無人の run の推しを答えとして数えるか。plan に承認ノードの答えは届かない"""
    return judgmark.with_ledger(doc, ties_file=ctx.get("answer_ties"), materials_file=ctx.get("materials"), answers=ctx.get("answers") or [],
                                takes_push=bool(ctx.get("takes_push")))


def read_judgment(ctx: dict) -> dict | None:
    """判定（問いの台帳の見え方つき）。判定が無い・読めなければ None"""
    path = ctx.get("judgment")
    return with_ledger(ctx, jsonfile.read_or(path)) if path else None


def prior_rows(ctx: dict, which: str = "reply") -> list:
    """前の周の受け付けた案（prior.reply の plan）の項目の並び。前の周が無ければ []"""
    prior = ctx.get("prior")
    return rows_of(jsonfile.read_or(prior[which]) if prior else None, "plan")


# ---------------------------------------------------------------- 直す義務の単位（本体は lib/judgmark.py。plan の周を開く口と line の node owed が共に引く）
_owed_units = judgmark.owed_units


def shut(judgment, reply) -> list:
    """返答（id に戻した物）が案に入れた単位のうち、判定に在るが入れてよくも必ず入れるでもない物の key"""
    owed, opened, units = plan_slots(judgment)
    plan = reply.get("plan") if isinstance(reply, dict) else None
    return [k for k in converge.plan_keys(plan) if isinstance(k, str) and k in units and k not in opened and k not in owed]


def not_allowed(judgment, reply) -> list:
    """修正案の返答（no を id に戻した物）が案に入れた単位のうち、受け付けが受けない物の理由の行"""
    units = units_of(judgment)
    return [f"{k[:40]} は label={units[k].get('label')}（disposition={units[k].get('disposition', '無し')}）で直す対象でない"
            for k in shut(judgment, reply)]


def unit_name(names: list, k):
    """役が返した単位の番号（1 から）を names の単位の名に戻す唯一の口。戻せない値は k のまま"""
    return names[k - 1] if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(names) else k


def named(reply, slot_list):
    """no の整数を slots の id に戻した返答の写し（単位を持つ欄は planmarks.UNIT_REFS の unit_keys と depends_on[].unit）"""
    got = copy.deepcopy(reply)
    for p in got.get("plan") if isinstance(got, dict) and isinstance(got.get("plan"), list) else []:
        if isinstance(p, dict):
            planmarks.renumber(p, lambda k: unit_name(slot_list, k))
    return got


def fix_plan_covers_units(plan, owed, opened) -> list:
    """修正案は今の周に直す単位を全部、どれか 1 つの案に入れる。例外の代わりに拒否の行を返す"""
    got = converge.plan_keys(plan)
    errs = []
    unknown = sorted({str(k) for k in got if k not in opened})   # 免除の単位（答えていない問いの出どころ・depends）は入れても入れなくてもよい
    if unknown:
        errs.append(f"今の周に直す単位に無い key {[k[:40] for k in unknown[:3]]}（写さずに、貼られた単位の no で指せ）")
    missing = sorted(set(owed) - set(got))
    if missing:
        errs.append(f"どの案にも入っていない単位 {[k[:40] for k in missing[:3]]}——直す義務の単位は全部どれかの案に入れる")
    dup = sorted({str(k) for k in got if got.count(k) > 1})
    if dup:
        errs.append(f"2 つの案に入った単位 {[k[:40] for k in dup[:3]]}——1 単位は 1 案")
    return errs


def owed_order(judgment) -> list:
    """直す義務の単位の key を判定の順に（line が単位ごとの深さを決める元）"""
    owed = _owed_units(judgment)
    return [k for k in slots(judgment) if k in owed]


def round_slots(folder, judgment) -> list:
    """形 plan の周の、案に入れてよい単位の名の並び（no は 1 始まりの位置）。周の slots.json が読めなければ判定から組む"""
    got = jsonfile.read_or(pathlib.Path(folder) / files.SLOTS)
    return got if isinstance(got, list) else slots(judgment)


# ---------------------------------------------------------------- 判定の処方
def prescriptions(judgment) -> dict:
    """{単位の key: [処方の文]}（判定の返答から。空の処方の単位は入れない）"""
    got = {}
    for u in rows_of(judgment, "units"):
        if isinstance(u.get("key"), str):
            rx = [x for x in u.get("prescriptions") or [] if isinstance(x, str) and x.strip()]
            if rx:
                got[u["key"]] = rx
    return got


# ---------------------------------------------------------------- 作業ツリーの姿
def snap_tree(path, repo) -> pathlib.Path:
    """読むだけの役を起こす前の作業ツリーの姿を path に置く"""
    return files.write_json(path, accept.tree_state(pathlib.Path(repo)))


def moved(path, repo, keys=accept.TREE_KEYS) -> str:
    """役が作業ツリーを変えた・HEAD や枝を動かした訳（keys の欄で比べる。変えていなければ空）。起こす前の姿 path が読めなければその訳"""
    before = jsonfile.read_or(path)
    if not isinstance(before, dict):
        return NO_TREE.format(name=pathlib.Path(path).name)
    changes = accept.tree_moved(before, pathlib.Path(repo), keys=keys)
    return READONLY_MOVED + "；".join(changes) if changes else ""


# ---------------------------------------------------------------- 波及の一覧
def ripple_units(place, repo) -> dict:
    """案の前の波及の一覧（単位の key の名の呼び出し元と試験）を ripple-units.json に書く"""
    folder, ctx = load(place)
    judgment = read_judgment(ctx)
    owed, _, _ = plan_slots(judgment)
    names = slots(judgment)
    doc = ripple.for_units(repo, names + sorted(owed - set(names)), skip_dirs=RUNTIME_COPY_DIRS)
    files.write_json(folder / files.RIPPLE_UNITS, doc)
    return {"ok": True}


def accepted_fields(folder):
    """受け付けた案の項目の欄（無い・空なら None）"""
    folder = pathlib.Path(folder)
    if not (folder / files.REPLY).is_file():
        return None
    fields = jsonfile.read_or(folder / files.FIELDS, {}).get("fields")
    return fields if isinstance(fields, list) and fields else None


def why_not_ready(folder) -> str:
    """この周に案が無い訳（役を起こさなかった訳・網の回まで続いた拒否の最後の理由・拒否の控えが読めない・輪が回らなかった）"""
    why = files.read_round(folder)["why"]
    if why:
        return str(why)
    try:
        return rolekit.given_up_reason(pathlib.Path(folder), files.ROLE) or files.NO_PLAN
    except rolekit.BoardGap as e:
        return f"拒否の控えが扱えない（{e}）"


def ripple_items(place, repo) -> dict:
    """受け付けた案の項目ごとの波及の一覧を ripple.json に書く。案が無い周は {"items": [], "error": <訳>}"""
    folder = files.current_dir(place)
    fields = accepted_fields(folder)
    doc = ripple.build(repo, fields, skip_dirs=RUNTIME_COPY_DIRS) if fields else {"items": [], "error": why_not_ready(folder)}
    files.write_json(folder / files.RIPPLE, doc)
    return {"ok": True}


# ---------------------------------------------------------------- 出口
def note_gave_up(folder, ctx: dict) -> list | None:
    """形 replan の周で修正案の役が受け付けの網の回まで拒まれ続けたら、渡した項目ごとの諦めの行 {item, why, ruling（裁定の文を字のまま）} を
    replan-gave-up.json に置いて返す。諦めていなければ None"""
    folder = pathlib.Path(folder)
    rnd = files.read_round(folder)
    try:
        reason = rolekit.given_up_reason(folder, files.ROLE)
    except rolekit.BoardGap:
        reason = ""
    if rnd["mode"] != "replan" or not reason or (folder / files.REPLY).is_file():
        return None
    old = prior_rows(ctx)
    conflicts = jsonfile.read_or(ctx.get("conflicts")) if ctx.get("conflicts") else None
    why = PLAN_GAVE_UP_WHY.format(reason=reason)
    rows = [{"item": n, "why": why, "ruling": ruling_text(conflict_rows(conflicts, n, old[n - 1]))}
            for n in rnd["items"] if 1 <= n <= len(old)]
    files.write_json(folder / files.REPLAN_GAVE_UP, rows)
    return rows


def conflict_rows(conflicts, n: int, old: dict) -> list:
    """修正の段の conflicts.json の行のうち、裁定が fix_plan_item で項目 n を名指す物"""
    import conflict   # lib/
    return conflict.replan_rows(rows_of(conflicts, "items"), n, old.get("unit_keys"))


def ruling_text(rows: list) -> str:
    """申し出と裁定の行の裁定の文（字のまま。2 行以上は「／」で繋ぐ）"""
    return "／".join(str((c.get("ruling") or {}).get("text") or "") for c in rows) or NO_ROWS


def placeholders(folder, reason: str) -> dict:
    """pointer の先（plan-fields.json・ripple.json）が在って空でないようにし、{plan, ripple} のパスを返す。無い物は「無い」を表す形で書く"""
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    plan, rip = folder / files.FIELDS, folder / files.RIPPLE
    if not files.filled(plan):
        files.write_json(plan, {"round": files.read_round(folder)["round"], "fields": []})
    if not files.filled(rip):
        files.write_json(rip, {"items": [], "error": reason or files.NO_PLAN})
    return {"plan": plan, "ripple": rip}


def _pointer(folder, name: str):
    path = pathlib.Path(folder) / name
    return ports.pointer(path) if path.is_file() else None


def status_of(folder, rnd: dict, fields) -> tuple:
    """(status, reason)。status は ok・nothing_owed・held・gave_up・failed（docs/design/plan.md の 1.2）"""
    folder = pathlib.Path(folder)
    if rnd.get("error"):   # 周を開く途中で落ちた周は、フォルダに何が残っていても failed
        return "failed", str(rnd["why"])
    if fields:
        return "ok", ""
    if not rnd["go"]:
        if not rnd["why"]:
            return "failed", str(rnd["why"] or "入口の控え round.json が無い（入口の node が落ちた）")
        return ("nothing_owed" if rnd["why"] == NOTHING_OWED else "held"), str(rnd["why"])
    error = files.read_json(folder / files.PROMPT_ERROR)
    if isinstance(error, dict):
        return "failed", f"指示が組めない（{error.get('node')}: {error.get('why')}）"
    if rnd.get("halt"):   # 受けた案の控えを置けない機械の故障。役が回数を使い切った gave_up ではない
        return "failed", str(rnd["why"])
    try:
        given = rolekit.given_up_reason(folder, files.ROLE)
    except rolekit.BoardGap as e:
        return "failed", f"拒否の控えが扱えない（{e}）"   # 機械の故障。役の使い切りではない
    if rnd["why"] or given:
        return "gave_up", str(rnd["why"] or given)
    return "failed", files.NO_PLAN


def report_lines(status: str, reason: str, rnd: dict, fields, rejects: list, gave_up) -> list:
    """報告の節「修正案」の日本語の行。狭める能力の行と承認ノードの文は、ここに組まない（fix_plan を読む graph が組む）"""
    k = rnd["round"]
    if status == "ok":
        what = "案の直し" if rnd["mode"] == "replan" else "案を書く"
        out = [f"修正案: 周 {k}（{what}）・項目 {len(fields)} 件・受け付けの拒否 {len(rejects)} 回"]
        if rnd["mode"] == "replan":
            out.append("案の直しで直した項目: " + "・".join(str(n) for n in rnd["items"]))
        return out
    if status == "nothing_owed":
        return [f"修正案: 周 {k}・直す義務の単位が無いので修正案の役を起こさなかった（{reason}）"]
    out = [f"修正案: 周 {k}・修正案を出せなかった（{status}）: {reason}"]
    out += [f"案の直しを終えられなかった 項目 {g['item']}: {g['why']}。裁定の文: {g['ruling']}" for g in gave_up or []]
    return out


def finish(place) -> dict:
    """block の返り（docs/design/plan.md の 1.2 の出力）。受けた案の有無・諦めた時の項目ごとの行・pointer の先の補い・status を決める"""
    place = pathlib.Path(place)
    folder = files.current_dir(place)
    rnd = files.read_round(folder)
    ctx = files.read_json(folder / files.INTAKE)
    ctx = ctx if isinstance(ctx, dict) else {}
    fields = accepted_fields(folder)
    status, reason = status_of(folder, rnd, fields)
    gave_up = None
    if not fields:
        gave_up = note_gave_up(folder, ctx) if ctx else None
    paths = placeholders(folder, reason)
    try:
        rejects = rolekit.reject_rows(folder, files.ROLE)
    except rolekit.BoardGap:
        rejects = []
    judgment = read_judgment(ctx) if ctx and rnd["mode"] == "plan" else None
    owed = owed_order(judgment) if isinstance(judgment, dict) else []
    return {"ok": status == "ok", "status": status, "reason": reason, "mode": rnd["mode"], "round": rnd["round"], "owed": owed,
            "plan": ports.pointer(paths["plan"]), "fix_plan": _pointer(folder, files.FIX_PLAN), "reply": _pointer(folder, files.REPLY),
            "handoff": _pointer(folder, files.HANDOFF), "replan": _pointer(folder, files.REPLAN), "ripple": ports.pointer(paths["ripple"]),
            "rejects": rejects, "gave_up": gave_up, "report": report_lines(status, reason, rnd, fields, rejects, gave_up)}


def record_crash(place, node: str, why: str) -> None:
    """指示が組めなかった node と訳を、今の周のフォルダの prompt-error.json に書く（出口が failed と訳を返す）。書けなくても落とし直さない"""
    try:
        files.write_json(files.current_dir(place) / files.PROMPT_ERROR, {"node": node, "why": why})
    except OSError:
        pass


def value(raw):
    """出し直しの入力の JSON の値。null・空・無い入力は None。JSON でなければ字のまま（受け付けが『JSON として読めない』と拒む）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw
