"""再審の役の受け付けの芯（docs/design/diagnose.md の 3.8。lib/judge_accept.py の再審の部分を、place と値を引数で受ける形に写した物）。

修正役の異議と 1 回目の判定を読んだ再審の役の返答を、作業ツリー・class_query の例・確かめた事実の長さで受け付け、単位の前後の差と出口を
place に書く。指示の文は持たない（prompts/rejudge.md が持つ）。
"""
from __future__ import annotations

import json
import pathlib
import re

import accept      # lib/
import jsonfile    # lib/
import materialkit   # lib/
import querytest   # lib/
import rolekit     # lib/
from engine.util import Reject   # lib/graphloops/engine/util.py

import ports

from src import files
from src.judge import blank, is_open

REJUDGE_VERDICTS = ("採る", "退ける", "一部採る")   # 再審の役の output_format の verdict の enum
ADOPTED = REJUDGE_VERDICTS[0]                     # 異議を採る答え
REJUDGE_SETTLED = ("採る", "退ける")               # 決着して異議を降ろす答え
# 再審が単位を置き換える時に残す欄で、前後の差もこの欄だけを比べる
REJUDGE_UNIT_FIELDS = ("key", "label", "disposition", "reason", "reopen_evidence")
# 修正役に貼った番号の書き方（no N・No.N・#N・N 番）。全角の数字も \d に当たる
_NUMBERS = (re.compile(r"(?<![A-Za-z])no\.?\s*(\d+)", re.IGNORECASE), re.compile(r"[#＃]\s*(\d+)"), re.compile(r"(\d+)\s*番"))


def _read_json(path, default=None):
    p = pathlib.Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"{p} が読めない（{type(e).__name__}: {e}）") from None


def _write_json(path, doc) -> pathlib.Path:
    return jsonfile.write(path, doc, parents=True)


def rejudge_output(out):
    """擦り合わせの返答: 新しい事実を自分で確かめたことを要求する（反論は新しい事実を伴う時だけ通す）。確かめた事実が空同然なら Reject"""
    fact = (out.get("new_facts") or "").strip()
    if blank(fact, files.FACTS_MIN):
        raise Reject(f"{files.REJUDGE_NODE}: new_facts が空同然——回す側が出した事実を**自分で確かめた結果**を書け"
                     "（確かめずに採る／退けるのは、どちらも判定を都合よく使うことになる）")


def _named_numbers(text):
    got = set()
    for rx in _NUMBERS:
        for m in rx.finditer(text or ""):
            got.add(int(m.group(1)))
    return got


def diff_units(before, after, objection_text, numbered, fields=None) -> dict:
    """前後の単位を key で比べる。{changed: [{key, kind, field?, before?, after?, named}], unnamed_changed: [key], lowered: [key]}
    - kind: changed（fields の欄が変わった。欄ごとに 1 行）・added・removed
    - named: key が異議の文に部分一致で現れるか、修正役に貼った番号（numbered の i 番目が番号 i+1）が no N・#N・N 番の形で現れるか。
      名指しを読み取れなければ偽（変化は争点外として強調する側に倒す）
    - lowered: block から他のラベルに下げた単位（指示は禁じるが受け付けは拒まない）"""
    fields = [f for f in (fields or REJUDGE_UNIT_FIELDS) if f != "key"]
    bmap = {u.get("key"): u for u in before or []}
    amap = {u.get("key"): u for u in after or []}
    nums = _named_numbers(objection_text)
    by_number = {numbered[n - 1] for n in nums if 1 <= n <= len(numbered or [])}

    def named(k):
        return bool(objection_text) and (k in objection_text or k in by_number)

    def pick_(u):
        return {f: u[f] for f in ["key", *fields] if f in u}

    changed, unnamed, lowered = [], [], []
    for k in [*bmap, *(k for k in amap if k not in bmap)]:
        nm = named(k)
        rows = []
        if k not in amap:
            rows.append({"key": k, "kind": "removed", "before": pick_(bmap[k]), "named": nm})
        elif k not in bmap:
            rows.append({"key": k, "kind": "added", "after": pick_(amap[k]), "named": nm})
        else:
            for f in fields:
                if bmap[k].get(f) != amap[k].get(f):
                    rows.append({"key": k, "kind": "changed", "field": f, "before": bmap[k].get(f), "after": amap[k].get(f),
                                 "named": nm})
            if bmap[k].get("label") == "block" and amap[k].get("label") != "block":
                lowered.append(k)
        changed += rows
        if rows and not nm:
            unnamed.append(k)
    return {"changed": changed, "unnamed_changed": unnamed, "lowered": lowered}


def take(place, reply, repo) -> dict:
    """再審の役の返答を受け付ける。返り {ok, reason, verdict}。順: 作業ツリーを tree.json と比べる → class_query の例で問いを試して例を
    外す（例は query-examples.json に足す）→ rejudge_output。拒否は {ok: False, reason}（place を変えない）。通れば:
    - judgment.json: 1 回目の判定（first-judgment.json）の全部の欄に、返答の単位（REJUDGE_UNIT_FIELDS）を units に入れた物
    - rejudge-reply.json に受けた返答を足し、rejudge-diff.json に単位の前後の差を 1 行足す
    返答の形の誤り・支度の欠けも拒否として返す（投げない）"""
    place = pathlib.Path(place)
    no = {"ok": False, "verdict": ""}
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{files.REJUDGE_NODE}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        moved = materialkit.moved_since(place, repo, accept.status_keys(files.GUARDED))
        if moved:
            raise Reject("読むだけの役が作業ツリーを変えた: 再審の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                         "ファイルを変えてはいけない（" + "・".join(moved) + "）")
        before_doc = _read_json(place / files.UNITS_BEFORE_FILE)
        if not isinstance(before_doc, dict):
            raise Reject(f"{files.REJUDGE_ROLE} の前の単位の写しが無い（入口が先に走る）")
        errs = querytest.problems(reply.get("units"), is_open)
        if errs:
            raise Reject("class_query の例が問いと合わない: " + "; ".join(errs))
        reply, examples = querytest.split(reply, is_open)
        rejudge_output(reply)
        if not all(isinstance(u, dict) and isinstance(u.get("key"), str) and u.get("key") for u in reply["units"]):
            raise Reject(f"{files.REJUDGE_NODE}: units の行に key（空でない字）が要る")
        first = _read_json(place / files.FIRST_JUDGMENT_FILE) or {}
    except Reject as e:
        return {**no, "reason": str(e)}
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return {**no, "reason": f"{files.REJUDGE_NODE}: 返答の形が違う（{type(e).__name__}: {e}）"}
    if examples:
        querytest.save(place, examples)
    units = [{f: u[f] for f in REJUDGE_UNIT_FIELDS if f in u} for u in reply["units"]]
    _write_json(place / files.JUDGMENT_FILE, {**(first if isinstance(first, dict) else {}), "units": units})
    _write_json(place / files.REJUDGE_REPLY_FILE, (_read_json(place / files.REJUDGE_REPLY_FILE, []) or []) + [reply])
    verdict = reply.get("verdict", "")
    row = {"round": 1, "pass": files.REJUDGE_ROLE, "node": files.REJUDGE_NODE, "verdict": verdict,
           **diff_units(before_doc.get("units") or [], units, before_doc.get("objection") or "",
                        before_doc.get("numbered_keys") or [])}
    _write_json(place / files.REJUDGE_DIFF_FILE, (_read_json(place / files.REJUDGE_DIFF_FILE, []) or []) + [row])
    return {"ok": True, "reason": "", "verdict": verdict}


def collect(place) -> dict:
    """再審の出口 rejudge-exit.json（{ok, reason, passes, verdicts, unsettled, objection, new_open_units, lowered, unnamed_changed,
    diff_file, reads_file}）を書いて返す。
    - 受けた再審の判定（judgment.json）が無い（輪が 3 回とも拒まれた）: ok false と諦めた理由。止めの控えは書かない（finish が理由を返す）
    new_open_units と lowered は最初の再審の前の単位（units-before.json）と今の単位の比べ。unsettled は最後の答えが 採る・退ける なら
    決着（異議を降ろす）。reads_file は読んだ証拠を持ち込まないので空"""
    place = pathlib.Path(place)
    judgment = _read_json(place / files.JUDGMENT_FILE)
    rows = _read_json(place / files.REJUDGE_DIFF_FILE, []) or []
    before = _read_json(place / files.UNITS_BEFORE_FILE)
    ok, reason = True, ""
    if judgment is None:
        ok = False
        reason = rolekit.given_up_reason(place, files.REJUDGE_ROLE) or (
            f"{files.REJUDGE_NODE} の返答を受けないまま再審のループを抜けた（ループが回らなかった）")
    verdicts = [r.get("verdict", "") for r in rows]
    new_open, lowered = [], []
    if before is not None and judgment is not None:
        was = {u.get("key"): u for u in before.get("units") or []}
        now_units = judgment.get("units") or []
        new_open = [u["key"] for u in now_units if is_open(u) and not (u["key"] in was and is_open(was[u["key"]]))]
        lowered = [u["key"] for u in now_units
                   if (was.get(u["key"]) or {}).get("label") == "block" and u.get("label") != "block"]
    objection = (before or {}).get("objection") or ""
    settled = not objection or bool(verdicts and verdicts[-1] in REJUDGE_SETTLED)
    unnamed = list(dict.fromkeys(k for r in rows for k in r.get("unnamed_changed") or []))
    diff_p = place / files.REJUDGE_DIFF_FILE
    out = {"ok": ok, "reason": reason, "passes": len(rows), "verdicts": verdicts,
           "unsettled": {"text": "" if settled else objection, "settled": settled},
           "objection": objection, "new_open_units": new_open, "lowered": lowered, "unnamed_changed": unnamed,
           "diff_file": str(diff_p) if diff_p.exists() else "", "reads_file": ""}
    _write_json(place / files.REJUDGE_EXIT_FILE, out)
    return out


def value(raw):
    """入力の JSON の値。null・空・無い入力は None。JSON でなければ字のまま（受け付けが『JSON として読めない』と拒む）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw


def accept_reply(place, reply, fix_reply, repo) -> dict:
    """再審の役の返答の受け付けの輪の 1 回。reply は 1 回目の役の返答、fix_reply は拒まれた後の出し直しの役の返答（拒まれた欄だけ。
    どちらも JSON に戻した値で、起きなかった役は None）。出し直しは前の答えの控え candidate-rejudge.json と欄ごとに合わせてから照らす。
    3 回目の拒否で done。輪を抜ける時（done）は出口 rejudge-exit.json を書く（書けなくても落ちない。finish が書き直す）。
    返り {ok, done, reason}"""
    got = rolekit.resubmitted(place, files.REJUDGE_ROLE, reply, fix_reply, rolekit.merge_fields)
    out = rolekit.accept_parsed(place, files.REJUDGE_ROLE, got, lambda r: take(place, r, repo))
    if out.get("done"):
        try:
            collect(place)
        except Exception:   # noqa: BLE001
            pass
    return {"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])}


def verdict_of(place):
    """再審の答えの語（採る・退ける・一部採る）。rejudge-exit.json の最後の verdicts（受けた再審が無い・出口が読めなければ None）"""
    try:
        doc = _read_json(pathlib.Path(place) / files.REJUDGE_EXIT_FILE)
    except ValueError:
        return None
    got = (doc.get("verdicts") or [None])[-1] if isinstance(doc, dict) and doc.get("ok") else None
    return got if got in REJUDGE_VERDICTS else None
