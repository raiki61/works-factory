"""出口（finish）: 往復の控えから status・holes.json・delta.diff・次の run の依頼の行 carry・報告の行 report を組む
（docs/design/delta-review.md の 6 節の 9。写す元は lib/fixboard.py の delta_review と lib/fixbeside.py の _ties・branch_rows・next_items・
always_rows のレンズの行）。どの段が落ちていても落ちない（呼び手の ports.run が fallback を返す）。
"""
import pathlib

import ports

import gatemarks  # lib/。HANDLED_WORDS
import holeties  # lib/
import jsonfile  # lib/
import leftovers  # lib/
import lens  # lib/
import oneline  # lib/
import rolekit  # lib/
import unittrees  # lib/

from src import files, touchup

STATUSES = ("ok", "gave_up", "failed")
BRANCH_HEAD = "差分の審査の穴の枝（機械が修正案の項目に結んだ名札。手直しの役にも同じ名札を渡した）"   # 1 回目の往復の頭
LENS_WHERE = "レンズ"


def _read(place, name):
    return jsonfile.read_or(pathlib.Path(place) / name)


def _branch_head(n: int) -> str:
    return BRANCH_HEAD if n == files.ROUNDS[0] else f"{n} 回目の審査の穴の枝"


def _handled_head(n: int) -> str:
    return "手直しの結果" if n == files.ROUNDS[0] else f"{n} 回目の手直しの結果"


def _last(place, role) -> str:
    rows = rolekit.rejected(pathlib.Path(place), role)
    return oneline.one_line(rows[-1]) if rows else ""


# ---------------------------------------------------------------- 往復の読み
def rounds(place) -> dict:
    """往復の状態 {rounds, pass, gave_up: [(役の名, 往復, 訳)], missing: [訳], errors: [訳]}。
    - rounds: 審査の控え review-<n>.json か、受け付けずに輪が終わった往復（拒否の控えが在る）の数
    - pass: 最後に数えた往復の審査の控えの pass（控えが無ければ false）
    - gave_up: 諦めた役（審査の控えの gave_up・審査の控えが無く拒否だけが在る往復・3 回拒まれた手直し・受け付けずに輪が終わった手直し）
    - missing: 回るはずの輪の控えも拒否も無い往復（役が走らなかったか落ちた）"""
    place = pathlib.Path(place)
    out = {"rounds": 0, "pass": False, "gave_up": [], "missing": [], "errors": []}
    for row in _read(place, files.ERRORS) or []:
        out["errors"].append(f"{row.get('node')}: {row.get('reason')}")
    expected_review = {1: True, 2: (place / files.cut(2)).is_file()}
    for n in files.ROUNDS:
        if not expected_review[n]:
            continue
        role, record = files.REVIEW[n], _read(place, files.review_record(n))
        rejected = rolekit.rejected(place, role)
        if isinstance(record, dict):
            out["rounds"], out["pass"] = n, bool(record.get("pass"))
            if record.get("gave_up"):
                out["gave_up"].append((role, n, str(record.get("reason") or "") or _last(place, role)))
        elif rejected:
            out["rounds"], out["pass"] = n, False
            out["gave_up"].append((role, n, _last(place, role)))
        else:
            out["missing"].append(f"{n} 回目の審査の受け付けの控えが無い（役が走らなかったか落ちた）")
            continue
        if not (place / files.refix_head(n)).is_file():
            continue   # 手直しを起こさなかった（義務が無い・諦めた）
        role = files.REFIX[n]
        if (place / files.refix_reply(n)).is_file():
            continue
        if rolekit.rejected(place, role):
            out["gave_up"].append((role, n, _last(place, role)))
        else:
            out["missing"].append(f"{n} 回目の手直しの受け付けの控えが無い（役が走らなかったか落ちた）")
    return out


def ties_and_handled(place) -> tuple:
    """({往復: 名札の並び | 組めない訳の字}, {往復: 手直しの handled の行})。名札は材料なので、組めない訳を置いて先へ進む"""
    ties, handled = {}, {}
    for n in files.ROUNDS:
        try:
            ties[str(n)] = touchup.hole_ties(place, n)
        except Exception as error:  # noqa: BLE001
            ties[str(n)] = f"{type(error).__name__}: {oneline.one_line(error)}"
        reply = _read(place, files.refix_reply(n)) or {}
        handled[str(n)] = [h for h in reply.get("handled") or [] if isinstance(h, dict)]
    return ties, handled


def cumulative_diff(place, repo, base: str):
    """base から手直しの後の今の作業ツリーの姿までの累積の差分を delta.diff に書いて pointer を返す。空なら書かずに None"""
    snap = leftovers.snapshot(repo)
    raw = leftovers.git(repo, "diff", base, snap, "--", *unittrees.pathspec_without(files.SKIP), text=False)
    if not raw.strip():
        return None
    target = pathlib.Path(place) / files.DIFF
    target.write_bytes(raw)
    return ports.pointer(target)


# ---------------------------------------------------------------- 報告の行と次の run の依頼の行
def _lens_state(place, intake: dict) -> dict:
    """レンズの控えの読み {state: 'none'|'unreadable'|'ran', summary?, reason?}"""
    if intake.get("lens_error"):
        return {"state": "unreadable", "reason": intake["lens_error"]}
    if not (pathlib.Path(place) / files.LENS).is_file():
        return {"state": "none"}
    reply = pathlib.Path(place) / files.review_reply(1)
    s = lens.summary(place, str(reply) if reply.is_file() else None)
    if not s["readable"]:
        return {"state": "unreadable", "reason": s["reason"]}
    return {"state": "ran", "summary": s} if s["ran"] else {"state": "none"}


def lens_lines(state: dict) -> list:
    if state["state"] == "unreadable":
        return [f"- レンズの控えが読めない（{oneline.one_line(state['reason'])}）。どのレンズが見たかを確かめられない", f"- {lens.REFIX_NOTE}"]
    if state["state"] == "none":
        return ["- レンズを走らせていない（控えが無い）"]
    s = state["summary"]
    rows = [f"- {lens.count_line(s)}"]
    for r in s.get("rows") or []:
        taken = "調べていない" if r.get("adopted") is None else f"採った {r['adopted']}・採らなかった {r['not_adopted']}"
        rows.append(f"  - {r.get('lens')}: {taken}・形の誤りで捨てた {r.get('dropped')}（出した発見 {r.get('findings')}）")
    rows += [f"  - 落ちたレンズ {f.get('lens')}（再実行の要あり）: {oneline.one_line(f.get('reason'))}" for f in s.get("failed") or []]
    return [*rows, f"- {lens.REFIX_NOTE}"]


def branch_lines(ties: dict, handled: dict) -> list:
    """往復ごとの穴の枝の名札（件数の 1 行と穴ごとの行。組めなければ訳の 1 行）と手直しの結果（handled の行）"""
    rows = []
    for n in files.ROUNDS:
        t = ties.get(str(n))
        if isinstance(t, str):
            rows.append(f"- {_branch_head(n)}: 組めない（{t}）")
        elif t:
            rows.append(f"- {_branch_head(n)}: {holeties.count_line(t)}")
            rows += [f"  - {x}" for x in holeties.lines(t)]
        h = handled.get(str(n)) or []
        if h:
            rows.append(f"- {_handled_head(n)}（{len(h)} 件）:")
            rows += [f"  - {x.get('key')}: {gatemarks.HANDLED_WORDS.get(x.get('handled'), '')}（{x.get('handled')}）——{oneline.one_line(x.get('how') or '')}"
                     for x in h]
    return rows


def carry_items(ties: dict, handled: dict, state: dict) -> list:
    """次の run の依頼の行 [{where, text}]: 手直しが declared で残した穴と、最後の往復の手直しが fixed と言った穴（次の審査が無いので検算が要る。
    どちらも枝の名札を添える）、落ちたレンズ・読めなかったレンズの控え（再実行の要あり）"""
    items = []
    for n in files.ROUNDS:
        t = ties.get(str(n))
        tags = {x["key"]: holeties.note(x) for x in t if isinstance(x, dict) and "key" in x} if isinstance(t, list) else {}
        for h in handled.get(str(n)) or []:
            if not isinstance(h.get("key"), str):
                continue
            where = (h.get("files") or [None])[0] or h["key"]
            tag = f"（枝: {tags[h['key']]}）" if h["key"] in tags else ""
            if h.get("handled") == "declared":
                items.append({"where": str(where), "text": f"{h['key']}（手直しが declared で残した穴: {h.get('how') or ''}）{tag}"})
            elif h.get("handled") == "fixed" and n == files.ROUNDS[-1]:
                items.append({"where": str(where), "text": f"{h['key']}（手直し {n} 回目が fixed と言ったが、{n + 1} 回目の審査は無い——検算が要る: "
                                                           f"{h.get('how') or ''}）{tag}"})
    if state["state"] == "unreadable":
        items.append({"where": LENS_WHERE, "text": f"レンズの控えが読めない——再実行の要あり: {oneline.one_line(state['reason'])}"})
    elif state["state"] == "ran":
        items += [{"where": f"{LENS_WHERE} {f.get('lens')}",
                   "text": f"{f.get('lens')}（再実行の要あり: 落ちて観点を誰も見ていない。理由: {oneline.one_line(f.get('reason'))}）"}
                  for f in state["summary"].get("failed") or [] if isinstance(f, dict)]
    return items


# ---------------------------------------------------------------- 出口
def _out(status, reason, rnds, passed, holes, diff, carry, report) -> dict:
    return {"ok": status != "failed", "status": status, "reason": reason, "rounds": rnds, "pass": passed, "holes": holes, "diff": diff,
            "carry": carry, "report": report}


def finish(place, repo) -> dict:
    """block の返り {ok, status, reason, rounds, pass, holes, diff, carry, report}"""
    place = pathlib.Path(place)
    intake = _read(place, files.INTAKE)
    if not isinstance(intake, dict) or intake.get("failed"):
        why = (intake or {}).get("reason") if isinstance(intake, dict) else ""
        why = why or "入口の控えが無い（入口の node が落ちた）"
        return _out("failed", why, 0, False, None, None, [], [f"- 差分の審査: 落ちた（{why}）"])
    state = _lens_state(place, intake)
    skipped = _read(place, files.SKIPPED)
    if isinstance(skipped, dict):
        why = str(skipped.get("reason") or "")
        return _out("ok", why, 0, True, None, cumulative_diff(place, repo, intake["base"]), carry_items({}, {}, state),
                    [f"- 差分の審査: 回っていない（{why}）", *lens_lines(state)])
    got = rounds(place)
    errors, missing = got["errors"], got["missing"]
    if errors:
        status, reason = "failed", errors[0]
    elif missing:
        status, reason = "failed", missing[0]
    elif got["gave_up"]:
        status = "gave_up"
        reason = "／".join(f"{role}（{n} 回目）: {why}" for role, n, why in got["gave_up"])
    else:
        status, reason = "ok", ""
    ties, handled = ties_and_handled(place)
    holes = jsonfile.write(place / files.HOLES, {"ties": ties, "handled": handled})
    head = (f"- 差分の審査: {got['rounds']} 回（最後の審査は{'通った' if got['pass'] else '通らなかった'}）" if got["rounds"]
            else f"- 差分の審査: 落ちた（{reason}）")
    gave = [f"- {'差分の審査' if role.startswith('review') else '手直し'}（{n} 回目）が {rolekit.GIVE_UP_AFTER} 回拒まれて諦めた: {why}"
            for role, n, why in got["gave_up"]]
    return _out(status, reason, got["rounds"], got["pass"] and not got["gave_up"] and status != "failed", ports.pointer(holes),
                cumulative_diff(place, repo, intake["base"]), carry_items(ties, handled, state),
                [head, *branch_lines(ties, handled), *gave, *lens_lines(state)])
