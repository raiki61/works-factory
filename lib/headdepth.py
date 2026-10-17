"""run の頭の深さ（issue #441。docs/design.md の「深さの段の表」）。使うのは判定と線の script と、判定・修正案・修正・報告の lib
（judge_accept・planfile・planblk・fixboard・runreport）。

単位ごとの深さ（depth.py）の上に、run 全体の深さの段（軽量・標準・重厚。段の定義は depth.TIERS）を run の頭で 1 度決める。
依頼の行ごとに何が決まっていないか（未知の種類）は意味の問いなので役が引用つきで選び、段はその種類から機械が引く（tier_of）。
ここは事実を測って役に渡し、役の引用が依頼の字とリポジトリの行に実在するかを照らす。照らしが通らない・根拠が引けない時は標準。
深さで飛ばすノードは無い（計画の往復の事前審査は段に依らず走る）。段が省く物と足す機能は depth.TIERS から引き、機能の切り替えの式は
entry に在る。

- facts(rows, start, repo): 依頼の行ごとの字と番地の実在・試験のコマンドの有無・仕様の段・設計だけ・入力 thickness の名指し
- gate(facts): 役を起こす前の機械の止め (go, 深さ, 訳)。go が偽なら決めた深さと訳で控えを書き、役を起こさない
- brief(facts): 役に貼る材料の本文。依頼の行の事実に、群の表から描いた群のセクション（launchgroups.brief_section）も貼る
- UNKNOWNS・tier_of(items): 依頼の行ごとに残っている未知の種類（無し・原因・形・範囲）とその段の表と、行の並びの一番重い種類の段
  （depth.HEADS の順）を引く関数。役は段を返さず、段は受け付けがここから引く
- ASKS・UNKNOWN_HEAD・section(record_file): 種類ごとの指示の表（鍵は UNKNOWNS と同じ。受け手の役に依らない字）と、節の見出し
  （promptsection.Section）と、控えのパス（在ればパス・無ければ空の字）から行ごとの『行 n（種類）: 依頼の字・番地と引用・指示』を
  描く節。種類が決まっていない run は見出しと訳の 1 行。使うのは判定の材料（lib/judge_accept.py の brief）と修正案の材料
  （lib/planfile.py の write_brief）
- check(reply, rows, repo): 役の返答の照らし。拒む訳の並び（空なら受ける）。番地の規則と引用の照らしと引用の字数の下限は cite
  （problem・quoted_in・QUOTE_MIN）。どの段にも why が空でないこと・依頼の行が在ること・items が依頼の全部の行をちょうど 1 度ずつ
  指すこと・各行の unknown が UNKNOWNS に在ることを求め、行を種類で照らす: 無しは cause_quote と where の行の範囲が WHERE_SPAN 行
  までの code_quote、形・範囲は範囲の幅を問わない同じ照らし、原因は cause_quote を必ず照らし、where を書いた行だけ where と
  code_quote も範囲の幅を問わず照らす
- write(jdir, doc)・read(jdir): 判定の置き場の控え RECORD の読み書き。read_file(path): 控えのファイルの読み（判定の外の読み手は
  判定の出力の欄 depth_record のパスで読む）。どちらの読みも無い・読めない時に標準の控え
- cited_files(doc): 控えの items の where が指すファイル（cite.CITE で読む）。修正の後に差分が引用の外に出たかを数える口
  （depth.outside_cited の cited）。使うのは修正のブロック（fixboard.redepth。prep が入力 depth_record の先を親の置き場へ写す）と
  線の redepth（入力 depth_record。workflows/line/scripts/redepth.py の fix_signals）
- record(depth, why, *, items, facts, groups): 控えの形。groups は役の群の選びを launchgroups.choices で照らした行（既定のまま・
  拒んだ時は空）。この run では効かず記録だけで、段の check には混ぜない
- report_line(depth_word, why, cut=()): 報告の冒頭 2 の 1 行。段の名・根拠と、その段の省く物（単位がどれも軽量の時だけ省く。実際に
  省いたかは depth.lines の行が言う）・足す物（depth.TIERS）。cut に在る足しは名指しで切ったと添える
- groups_lines(doc): 報告の ## 模型 のセクションに並べる群ごとの選びの行（lib/runreport.py の _model_lines が読む）。選びか既定への
  戻しの在る群だけを 1 群 1 行で描き、無ければ NO_CHOICE の 1 行。記録だけの 1 文（launchgroups.RECORD_ONLY）を添える
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
import launchgroups  # noqa: E402
import oneline  # noqa: E402
import promptsection  # noqa: E402
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
NO_ROWS = "依頼の行が無い（行ごとの未知の種類を引けない）"
NONE, CAUSE, SHAPE, SCOPE = "無し", "原因", "形", "範囲"
UNKNOWNS = {NONE: depth.LIGHT, CAUSE: depth.STANDARD, SHAPE: depth.STANDARD, SCOPE: depth.HEAVY}


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
                      f"機械の確かめ（試験のコマンド）: {'在る' if f['test_cmd'] else '無い'}", "", launchgroups.brief_section()])


def _known(kind) -> bool:
    return isinstance(kind, str) and kind in UNKNOWNS


def tier_of(items) -> str:
    """行の並び（各行の `unknown` が UNKNOWNS の鍵）から、一番重い種類の段を depth.HEADS の順で引く。引けない（行が無い・
    表に無い種類しか無い）時は標準"""
    tiers = [UNKNOWNS[it["unknown"]] for it in items or [] if isinstance(it, dict) and _known(it.get("unknown"))]
    return max(tiers, key=depth.HEADS.index, default=STANDARD)


def _check_item(it: dict, rows: list, repo, span=WHERE_SPAN, code_optional=False) -> list:
    n = it.get("item")
    head = f"行 {n}: "
    where = str(it.get("where") or "").strip()
    quotes = ("cause_quote",) if code_optional and not where else ("cause_quote", "code_quote")
    out = [head + f"{name} が {cite.QUOTE_MIN} 字より短い" for name in quotes
           if len(_squash(it.get(name))) < cite.QUOTE_MIN]
    if not cite.quoted_in(it.get("cause_quote"), rows[n - 1].get("text"), norm=_squash):
        out.append(head + "cause_quote が依頼のその行の字の部分でない")
    if len(quotes) == 1:
        return out
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
    if not str(reply.get("why") or "").strip():
        return ["why が空"]
    rows = [r for r in rows or [] if isinstance(r, dict)]
    if not rows:
        return [NO_ROWS]
    items = [it for it in reply.get("items") or [] if isinstance(it, dict)]
    named = [it.get("item") for it in items]
    want = list(range(1, len(rows) + 1))
    if sorted(n for n in named if isinstance(n, int) and not isinstance(n, bool)) != want or len(named) != len(want):
        return [f"items が依頼の行 {len(rows)} 個をちょうど 1 度ずつ指していない（指した行: {named}）"]
    out = []
    for it in items:
        kind = it.get("unknown")
        if not _known(kind):
            out.append(f"行 {it['item']}: unknown が {'・'.join(UNKNOWNS)} のどれでもない（{kind!r}）")
        elif kind == NONE:
            out += _check_item(it, rows, repo)
        else:
            out += _check_item(it, rows, repo, span=None, code_optional=kind == CAUSE)
    return out


def record(depth_word: str, why: str, *, items=(), facts_doc=None, groups=()) -> dict:
    return {"depth": depth_word, "why": why, "items": list(items), "facts": facts_doc or {}, "groups": list(groups)}


def write(jdir, doc: dict) -> pathlib.Path:
    return jsonfile.write(pathlib.Path(jdir) / RECORD, doc, parents=True)


def read_file(path) -> dict:
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return record(STANDARD, NO_RECORD)
    if not isinstance(doc, dict) or doc.get("depth") not in depth.HEADS:
        return record(STANDARD, NO_RECORD)
    return doc


def read(jdir) -> dict:
    return read_file(pathlib.Path(jdir) / RECORD)


def cited_files(doc) -> list:
    """頭の深さの控え doc（read の返り）の items の where が指すファイル（cite.CITE の `<パス>:<行>` のパスか、行の無い `<パス>`。
    現れた順・重なりは 1 つ）。where の無い行・items の無い控え（標準・名指し・機械の止め）は何も足さない。修正の後に、差分が
    引用の外に出たかを数える口（depth.outside_cited の cited）"""
    out = []
    for it in (doc.get("items") if isinstance(doc, dict) else None) or []:
        where = str(it.get("where") or "").strip() if isinstance(it, dict) else ""
        m = cite.CITE.match(where)
        path = m["path"] if m else where
        if path and path not in out:
            out.append(path)
    return out


UNKNOWN_HEAD = promptsection.Section("## 頭の深さの行ごとの未知の種類と指示（依頼の行ごと。機械が頭の深さの控えから貼った）", source="fn:headdepth.section")
CHOOSE = "形を 2 つ以上並べ、選んだ訳と退けた訳を書け。"
ASKS = {
    NONE: "引用した番地が本当に直す所かを先に確かめよ。外れていれば黙って広げず、外れた訳と本当の直す所を引用で返答に名指せ。",
    CAUSE: "症状の行から原因の行まで引用で辿って原因を探せ。",
    SHAPE: CHOOSE,
    SCOPE: "触る約束（型・設定の鍵・入出力の形・サブグラフ）を並べ、それぞれへの響きを名指せ。選びが要る時は、" + CHOOSE,
}
NO_KINDS = "行ごとの未知の種類は決まっていない（訳: {why}）"


def _row(it: dict) -> str:
    where = oneline.one_line(it.get("where") or "")
    place = f"番地 {where}「{oneline.one_line(it.get('code_quote') or '')}」" if where else "番地: 無い（原因がコードに見えない）"
    return (f"- 行 {it.get('item')}（{it['unknown']}）: 依頼の字「{oneline.one_line(it.get('cause_quote') or '')}」・{place}"
            f"・指示: {ASKS[it['unknown']]}")


def section(record_file) -> str:
    """判定と修正案の役の材料に貼る、依頼の行ごとの未知の種類と番地と指示の節。入力 record_file は頭の深さの控え RECORD のパス
    （在ればパス・無ければ空の字）。控えが無い・行に種類が無い run（機械の止め・名指しの thickness・受け付けを通らなかった・
    止めの道の空の控え）は、黙って空にせず見出しと訳の 1 行"""
    doc = read_file(record_file) if record_file else record(STANDARD, NO_RECORD)
    rows = [_row(it) for it in doc.get("items") or [] if isinstance(it, dict) and _known(it.get("unknown"))]
    if not rows:
        return f"{UNKNOWN_HEAD}\n\n{NO_KINDS.format(why=str(doc.get('why') or NO_RECORD))}\n"
    return "\n".join([UNKNOWN_HEAD, "", *rows]) + "\n"


NO_CHOICE = "役の選びは無い（呼ぶ人の名指しと層の付け替えの後の値は下のノードごとの行）"


def _group_line(row: dict) -> str:
    group = oneline.one_line(row.get("group") or "") or "（群の名が無い）"
    why = oneline.one_line(row.get("fallback") or row.get("why") or "") or "訳の記録が無い"
    pair = row.get("default") if isinstance(row.get("default"), dict) else {}
    if not pair.get("model"):
        return f"{group}: 表に無い群を既定に戻した（訳: {why}）"
    default = "・".join(filter(None, [pair["model"], pair.get("effort")]))
    if row.get("fallback"):
        return f"{group}: 役の選びを既定 {default} に戻した（訳: {why}）"
    return f"{group}: 既定 {default} → 役の選び {row.get('model')}・{row.get('effort')}（{row.get('direction')}。訳: {why}）"


def groups_lines(doc) -> list:
    """報告の ## 模型 のセクションに並べる、役の選びの行。控え doc（read が読んだ物。控えの無い run は None）の groups の行ごとに 1 行
    （1 群 1 行。選ばれていない群の行は出さない）: 選びは既定の (model, effort)・役の選び・向き・訳、既定に戻した行は戻した訳。
    選びも戻した行も無い・控えの無い run は NO_CHOICE の 1 行。どちらの形も最後に launchgroups.RECORD_ONLY の 1 文を添える。
    既定の値は控えの行の default（控えた時の表の既定）を使い、表を後で替えても控えと食い違わない"""
    groups = doc.get("groups") if isinstance(doc, dict) else None
    rows = [_group_line(r) for r in groups if isinstance(r, dict)] if isinstance(groups, list) else []
    return [*(rows or [NO_CHOICE]), launchgroups.RECORD_ONLY]


def report_line(depth_word, why, cut=()) -> str:
    tier = depth_word if depth_word in depth.HEADS else STANDARD
    spec = depth.TIERS[tier]
    head = f"run の頭の深さ: {tier}" + (f"（根拠: {why}）" if why else "")
    omits = f"（単位がどれも軽量の時）: {'・'.join(spec['omits'])}" if spec["omits"] else ": 無い"
    adds = "・".join(f"{name}（名指しで切った）" if name in cut else name for name in spec["adds"]) or "無い"
    return f"{head}／省く物{omits}／足した物: {adds}"
