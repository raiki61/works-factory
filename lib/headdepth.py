"""run の頭の深さ（issue #441。docs/design.md の「深さの段の表」）。使うのは判定と線の script。

単位ごとの深さ（depth.py）の上に、run 全体の深さの段（軽量・標準・重厚。段の定義は depth.TIERS）を run の頭で 1 度決める。
易しいか・難しいかは意味の問いなので役が決め、ここは事実を測って役に渡し、役の引用が依頼の字とリポジトリの行に実在するかを
照らす。照らしが通らない・根拠が引けない時は標準。深さで飛ばすノードは無い（計画の往復の事前審査は段に依らず走る）。段が省く物と
足す機能は depth.TIERS から引き、機能の切り替えの式は entry に在る。

- facts(rows, start, repo): 依頼の行ごとの字と番地の実在・試験のコマンドの有無・仕様の段・設計だけ・入力 thickness の名指し
- gate(facts): 役を起こす前の機械の止め (go, 深さ, 訳)。go が偽なら決めた深さと訳で控えを書き、役を起こさない
- brief(facts): 役に貼る材料の本文
- check(reply, rows, repo): 役の返答の照らし。拒む訳の並び（空なら受ける）。番地の規則と引用の照らしと引用の字数の下限は cite
  （problem・quoted_in・QUOTE_MIN）。軽量と重厚は依頼の行が在り、引用が通る時だけ受ける。軽量は where の行の範囲が WHERE_SPAN
  行までに限る（重厚は設計の選びなどを示すので範囲の幅は問わない）
- write(jdir, doc)・read(jdir): 控え RECORD の読み書き。read は無い・読めない時に標準の控え
- record(depth, why, *, items, facts): 控えの形
- report_line(depth_word, why, cut=()): 報告の冒頭 2 の 1 行。段の名・根拠と、その段の省く物（単位がどれも軽量の時だけ省く。実際に
  省いたかは depth.lines の行が言う）・足す物（depth.TIERS）。cut に在る足しは名指しで切ったと添える
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import cite  # noqa: E402
import depth  # noqa: E402
import gatemarks  # noqa: E402
import jsonfile  # noqa: E402
import startrec  # noqa: E402

LIGHT = depth.LIGHT
STANDARD = depth.STANDARD
RECORD = "depth-head.json"
BRIEF = "depth-head-brief.md"
NO_RECORD = "run の頭の深さの控えが無い"
NO_REPLY = "役の返答が受け付けに届いていない（役が走らなかったか落ちた）"
REJUDGE_WHY = "再審の判定（run の頭の深さは 1 回目の判定が決めた）"
NOT_ACCEPTED = "役の返答が受け付けを通らない（{why}）"
WHERE_SPAN = 30   # 軽量の根拠の where の行の範囲の幅の上限。直す所を 1 画面で名指せない範囲はファイルを指すのと変わらない
NO_ROWS = "依頼の行が無い（軽量・重厚の根拠を引けない）"


def _squash(text) -> str:
    return "".join(str(text or "").split())


def _place(repo, where) -> dict:
    """番地 where（`<パス>` か cite の名指し）のファイルが根の中に在るか・行の範囲がその中か（規則は cite.file_problem・cite.problem）"""
    where = str(where or "").strip()
    m = cite.CITE.match(where)
    path_ok = bool(where) and not cite.file_problem(m["path"] if m else where, repo)
    return {"path_ok": path_ok, "lines_ok": path_ok and not (m and cite.problem(where, repo))}


def facts(rows, start, repo) -> dict:
    start = start if isinstance(start, dict) else {}
    items = [{"item": n, "text": str(r.get("text") or ""), "where": str(r.get("where") or ""), **_place(repo, r.get("where"))}
             for n, r in enumerate((r for r in rows or [] if isinstance(r, dict)), start=1)]
    return {"items": items,
            "test_cmd": depth.has_checks(start),
            "spec": (startrec.shape(start) or {}).get("spec") is True,
            "design_only": start.get("design_only") == gatemarks.DESIGN_ONLY,
            "forced": depth.named(start.get("thickness"))}


def gate(f: dict) -> tuple:
    if f["forced"]:
        return False, f["forced"], depth.named_why(f["forced"])
    for stop, why in ((f["spec"], "仕様の段を挟む run"),
                      (f["design_only"], "設計だけの run"),
                      (not f["items"], "依頼の行が無い（差分だけの run）"),
                      (not f["test_cmd"], f"{depth.UNCHECKED}——代わりの最後のテストが測れない")):
        if stop:
            return False, STANDARD, why
    return True, "", ""


def brief(f: dict) -> str:
    rows = [f"- 行 {it['item']}: {it['text']}\n  - 番地: {it['where'] or '（無い）'}"
            f"（ファイル {'在る' if it['path_ok'] else '無い'}・行の範囲 {'ファイルの中' if it['lines_ok'] else '外か読めない'}）"
            for it in f["items"]]
    return "\n".join(["# run の頭の深さの材料（機械が測った）", "", f"依頼の行 {len(f['items'])} 個:", *rows, "",
                      f"機械の確かめ（試験のコマンド）: {'在る' if f['test_cmd'] else '無い'}", ""])


def _check_item(it: dict, rows: list, repo, span=WHERE_SPAN) -> list:
    n = it.get("item")
    head = f"行 {n}: "
    out = [head + f"{name} が {cite.QUOTE_MIN} 字より短い" for name in ("cause_quote", "code_quote")
           if len(_squash(it.get(name))) < cite.QUOTE_MIN]
    if not cite.quoted_in(it.get("cause_quote"), rows[n - 1].get("text"), norm=_squash):
        out.append(head + "cause_quote が依頼のその行の字の部分でない")
    where = str(it.get("where") or "").strip()
    bad = cite.problem(where, repo)
    if bad:
        return out + [head + f"where が通らない（{bad}）"]
    m = cite.CITE.match(where)
    first, last = int(m["a"]), int(m["b"] or m["a"])
    if span is not None and last - first + 1 > span:
        return out + [head + f"where の行の範囲が {span} 行より広い（直す所を名指していない）"]
    lines = cite.resolved(m["path"], pathlib.Path(repo).resolve()).read_text(encoding="utf-8", errors="replace").splitlines()
    if not cite.quoted_in(it.get("code_quote"), "\n".join(lines[first - 1:last]), norm=_squash):
        out.append(head + f"code_quote が {where} の字に無い")
    return out


def check(reply, rows, repo) -> list:
    if not isinstance(reply, dict):
        return ["返答が object でない"]
    if reply.get("depth") not in depth.HEADS:
        return [f"depth が {'・'.join(depth.HEADS)} のどれでもない（{reply.get('depth')!r}）"]
    if not str(reply.get("why") or "").strip():
        return ["why が空"]
    if reply["depth"] == STANDARD:
        return []
    rows = [r for r in rows or [] if isinstance(r, dict)]
    if not rows:
        return [NO_ROWS]
    items = [it for it in reply.get("items") or [] if isinstance(it, dict)]
    named = [it.get("item") for it in items]
    want = list(range(1, len(rows) + 1))
    if sorted(n for n in named if isinstance(n, int) and not isinstance(n, bool)) != want or len(named) != len(want):
        return [f"items が依頼の行 {len(rows)} 個をちょうど 1 度ずつ指していない（指した行: {named}）"]
    span = None if reply["depth"] == depth.HEAVY else WHERE_SPAN
    return [why for it in items for why in _check_item(it, rows, repo, span)]


def record(depth_word: str, why: str, *, items=(), facts_doc=None) -> dict:
    return {"depth": depth_word, "why": why, "items": list(items), "facts": facts_doc or {}}


def write(jdir, doc: dict) -> pathlib.Path:
    return jsonfile.write(pathlib.Path(jdir) / RECORD, doc, parents=True)


def read(jdir) -> dict:
    try:
        doc = json.loads((pathlib.Path(jdir) / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return record(STANDARD, NO_RECORD)
    if not isinstance(doc, dict) or doc.get("depth") not in depth.HEADS:
        return record(STANDARD, NO_RECORD)
    return doc


def report_line(depth_word, why, cut=()) -> str:
    tier = depth_word if depth_word in depth.HEADS else STANDARD
    spec = depth.TIERS[tier]
    head = f"run の頭の深さ: {tier}" + (f"（根拠: {why}）" if why else "")
    omits = f"（単位がどれも軽量の時）: {'・'.join(spec['omits'])}" if spec["omits"] else ": 無い"
    adds = "・".join(f"{name}（名指しで切った）" if name in cut else name for name in spec["adds"]) or "無い"
    return f"{head}／省く物{omits}／足した物: {adds}"
