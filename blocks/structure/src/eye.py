"""structure-eye の node の中身（docs/design/structure.md の 2・4 節。lib/eye.py の prep・problems・accept・state の写し）。

目は道具を持たない独立の会話の役で、見せるのは view.json の単位ごとの {id, summary, measure, concepts} と、
問いと 6 つの形（文は prompts/structure-eye.md）。行き先 route は「自分で決める」か「人に上げる」。人に上げるのは決め手を当たっても
1 つに決まらない汚れる行だけで、決まらない訳（undecided_because）と捨てた案と代償（rejected）が要る。受け付けは返答を機械で確かめ、
通れば設計の行を design.jsonl に書く。拒めば理由を返し、同じ会話で出し直させる（3 回目の拒否で done・give_up。線は止めない）。

控え eye.json: {started_at, status: pending|ok|gave_up, wall_s}。回の数えと拒否の文は rolekit の拒否の控え rejects-structure-eye.json だけが持つ。
"""
from __future__ import annotations

import json
import pathlib
import time

import ports  # noqa: F401  （lib/ を読めるようにする）
import prompt

import jsonfile   # lib/
import structmark   # lib/。設計の行を読み直す
import rolekit    # lib/。拒否の控えと輪の回の数え
import listcut    # lib/。duplicates の件数（指示の {shown}）

from src import files, intent

ROUTES = ("自分で決める", "人に上げる")
ROUTE, ROUTE_UP = ROUTES
ROUTE_REASON = "目が決め手から 1 つに決めた（決めきれない訳を書かなかった）"
MIN_UNDECIDED = 20   # 決まらない訳の字の下限（承認ノードの項目の訳になる）
VERDICTS = ("汚れる", "汚れない")
DIRTY, CLEAN = VERDICTS
FORM_COUNT = 6   # prompts/structure-eye.md の見る形の数（output_format の faces の範囲の上限と同じ。試験が突き合わせる）
MIN_QUOTE = 20       # 抜き書きの字の下限
DIFF_CAP = 40000     # after の指示に入れる差分のバイト数の上限（全体は after.diff に残す）
UNREADABLE = "design_unreadable"   # 目の控えの status: 書いた設計の行を読み直せなかった
WALL = "wall_s"   # 時間の欄の名（lib/eye.py の WALL と同じ字）


def state(out) -> dict:
    got = jsonfile.read_or(pathlib.Path(out) / files.EYE_FILE)
    return got if isinstance(got, dict) else {}


def _put(out, doc: dict) -> None:
    jsonfile.write(pathlib.Path(out) / files.EYE_FILE, doc)


def _view(out) -> dict:
    got = jsonfile.read_or(pathlib.Path(out) / files.VIEW_FILE)
    if not isinstance(got, dict):
        raise ValueError(f"{pathlib.Path(out) / files.VIEW_FILE} が無いか読めない（measure が走っていない）")
    return got


def _docs(out) -> list:
    got = jsonfile.read_or(pathlib.Path(out) / files.INTENT_FILE, [])
    return [d for d in got if isinstance(d, dict)] if isinstance(got, list) else []


def _diff(out) -> str:
    """after.diff の先頭 DIFF_CAP バイト（UTF-8。読めない字は置き換える）。切った時は末尾に印の 1 行"""
    raw = (pathlib.Path(out) / files.DIFF_FILE).read_bytes()
    text = raw[:DIFF_CAP].decode("utf-8", "replace")
    return text if len(raw) <= DIFF_CAP else f"{text}\n(cut: the first {DIFF_CAP} bytes are shown; {len(raw) - DIFF_CAP} more were left out)"


def prepare(out, mode="before", lang="") -> dict:
    """指示を md から組んで place に書く。前の回までの却下は place の控えから全部。返り {prompt, attempt}"""
    out = pathlib.Path(out)
    after = ports.choice(mode or "before", files.MODES) == "after"
    shown = _view(out)
    st = state(out)
    rejects = rolekit.rejected(out, files.NAME)
    n = len(rejects) + 1
    docs = _docs(out)
    values = {"rejection": rolekit.rejects_text(rejects), "dirty": DIRTY, "clean": CLEAN, "route_self": ROUTE, "route_up": ROUTE_UP,
              "min_undecided": MIN_UNDECIDED, "min_quote": MIN_QUOTE, "shown": listcut.SHOWN, "lang": prompt.lang(lang),
              "intent_docs": intent.shown_docs(docs), "diff": _diff(out) if after else "",
              "view": json.dumps(shown, ensure_ascii=False, separators=(",", ":"))}
    when = {"rejected": bool(rejects), "intent": any(d.get("text") for d in docs), "after": after}
    got = prompt.emit(files.NAME, values, when, n)
    _put(out, {"started_at": st.get("started_at") or time.time(), "status": "pending", WALL: st.get(WALL, 0)})
    return {"prompt": got["prompt"], "attempt": n}


def _pointer(doc, ptr: str) -> bool:
    """ptr（RFC 6901）が doc の中の在る欄（値が null でない。null の欄は根拠にならない）を指すか"""
    if not isinstance(ptr, str) or not ptr.startswith("/"):
        return False
    cur = doc
    for raw in ptr[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif isinstance(cur, list) and key.isdigit() and int(key) < len(cur) and (key == "0" or not key.startswith("0")):
            cur = cur[int(key)]
        else:
            return False
    return cur is not None


def problems(shown: dict, reply, docs=()) -> list:
    """返答の外れ（空なら通る。型は目の node の output_format が照らす）。単位と 1 対 1・根拠の実在・汚れる行の避け方・人に上げる道の
    無さと、書いた意図の抜き書きを見る。shown は view.json の中身、docs は intent.json の文書"""
    rows = reply.get("rows") if isinstance(reply, dict) else None
    if not isinstance(rows, list):
        return ["返答に rows（行の配列）が無い"]
    want = [u["id"] for u in shown.get("units") or []]
    seen, out = [], []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            out.append(f"行 {i} が JSON のオブジェクトでない")
            continue
        uid = r.get("unit_id")
        head = f"行 {i}（{uid}）"
        if uid not in want:
            out.append(f"{head}: 実測した単位に無い id（在るのは {want}）")
        elif uid in seen:
            out.append(f"{head}: 同じ単位の 2 行目")
        seen.append(uid)
        if r.get("verdict") == DIRTY and not r.get("faces"):
            out.append(f"{head}: 汚れると見たのに当たった形の番号が無い")
        ev = r.get("evidence")
        if not isinstance(ev, list) or not ev:
            out.append(f"{head}: evidence（根拠にした実測の欄）が空")
        else:
            out += [f"{head}: evidence {p!r} が実測の中の在る欄を指さない" for p in ev if not _pointer(shown, p)]
        if not isinstance(r.get("reason"), str) or not r["reason"].strip():
            out.append(f"{head}: reason が空")
        if r.get("verdict") == DIRTY and not all(isinstance(r.get(k), str) and r[k].strip() for k in ("chosen", "chosen_reason")):
            out.append(f"{head}: 汚れると見た行に chosen（推しの避け方）と chosen_reason が無い")
        if r.get("route", ROUTE) == ROUTE_UP:
            if r.get("verdict") != DIRTY:
                out.append(f"{head}: {ROUTE_UP}のは汚れると見た行だけ")
            why = r.get("undecided_because")
            if not isinstance(why, str) or len(why.strip()) < MIN_UNDECIDED:
                out.append(f"{head}: {ROUTE_UP}行は undecided_because（決め手を当たっても決まらない訳。{MIN_UNDECIDED} 字以上）が要る")
            rej = r.get("rejected")
            if not isinstance(rej, list) or not rej:
                out.append(f"{head}: {ROUTE_UP}行は rejected（捨てた案と代償）が 1 つ以上要る")
        elif r.get("undecided_because"):
            out.append(f"{head}: undecided_because は {ROUTE_UP}行だけに書く")
        out += _quotes(head, r, docs)
    missing = [u for u in want if u not in seen]
    if missing:
        out.append(f"行の無い単位: {missing}（汚れないと見た単位も 1 行ずつ）")
    return out


def _squeezed(text: str) -> str:
    return " ".join(str(text).split())


def _quotes(head: str, row: dict, docs) -> list:
    """書いた意図の照らし。本文の在る文書が 1 つ以上なら、汚れる行は intent を 1 つ以上持ち、どの intent も path が見せた文書で、
    quote が MIN_QUOTE 字以上で見せた本文（切った後）に字のまま在る（空白の並びは 1 つに詰めて比べる）。無ければ intent を拒む"""
    shown = {d["path"]: d["text"] for d in docs if d.get("text")}
    given = row.get("intent")
    given = given if isinstance(given, list) else []
    if not shown:
        return [f"{head}: 書いた意図の文書は見せていない（intent は空にする）"] if given else []
    out = []
    if row.get("verdict") == DIRTY and not given:
        out.append(f"{head}: 汚れると見た行に intent（反する書いた意図の抜き書き）が無い")
    for item in given:
        path, quote = (item.get("path"), item.get("quote")) if isinstance(item, dict) else (None, None)
        if path not in shown:
            out.append(f"{head}: intent の path {path!r} が見せた文書に無い（在るのは {list(shown)}）")
        elif not isinstance(quote, str) or len(_squeezed(quote)) < MIN_QUOTE:
            out.append(f"{head}: intent の {path} の抜き書きが {MIN_QUOTE} 字未満")
        elif _squeezed(quote) not in _squeezed(shown[path]):
            out.append(f"{head}: intent の {path} の抜き書きが、見せた本文に字のまま無い（頭: {_squeezed(quote)[:40]}）")
    return out


def accept(out, reply) -> dict:
    """構造の目の返答 reply（読めなければ None）の受け付け。拒否は rolekit.accept_round が控えに積み、3 回目で done・give_up。控えが
    読めない・書けなければ、落ちずに done 真・give_up 真の拒否（理由『拒否の控えが扱えない』）。返り {ok, done, give_up, reason, attempt}"""
    out = pathlib.Path(out)
    st = state(out)
    started = st.get("started_at") or time.time()
    shown = _view(out)
    docs = _docs(out)
    attempt, stopped = rolekit.current_round(out, files.NAME)

    def take(_):
        bad = problems(shown, reply, docs)
        return {"ok": False, "reason": " / ".join(bad)} if bad else {"ok": True, "reason": ""}
    got = rolekit.round_outcome(stopped or rolekit.accept_round(out, files.NAME, None, take))
    wall = round(time.time() - started, 3)
    if not got["ok"]:
        _put(out, {"started_at": started, "status": "gave_up" if got["give_up"] else "pending", WALL: wall})
        return {**got, "attempt": attempt}
    rows = [{**r, "route": r.get("route", ROUTE),
             "route_reason": r["undecided_because"].strip() if r.get("route") == ROUTE_UP else ROUTE_REASON}
            for r in reply["rows"]]
    design = out / files.DESIGN_FILE
    design.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    try:
        structmark.rows(str(design))   # 読み手が読めるかを、書いた直後に確かめる（読めない行を持つ控えを ok にしない）
    except ValueError as e:
        _put(out, {"started_at": started, "status": UNREADABLE, "reason": str(e), WALL: wall})
        return {"ok": False, "done": True, "give_up": False, "reason": f"設計の行が読めない: {e}", "attempt": attempt}
    _put(out, {"started_at": started, "status": "ok", WALL: wall})
    return {"ok": True, "done": True, "give_up": False, "reason": "", "attempt": attempt}
