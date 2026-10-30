"""段 → 回す物の表と単位の深さと修正の後の上げ直し（docs/design/line.md の 5 節。元 lib/depth.py と lib/latedepth.py と、
lib/headdepth.py の report_line〔integration.md 4.5-6〕と lib/consult.py の consulted_units の写し。名は元のまま）。

run 全体の深さの段（軽量・標準・重厚）の定義は表 TIERS 1 か所。単位の深さの語は軽量・標準の 2 つ。段の省く物（TIERS の omits）は、
その段の頭の run で直す義務の単位がどれも軽量の時だけ省く（skip_reason。issue #561 の答え）。省くかを when: に渡す時は、ここで
引いた結果の真偽（raise の checks・eyes_due）だけにする（when: は深さの語を読まない。tests/layers/test_depth_skip.py）。
段の語 4 つ（LIGHT・STANDARD・HEAVY・HEADS）の住処は lib/headdepth（README 11.3 の 5）。

- unit_depth(items, key, *, checked)・wiring(path)・decide_doc(items, open_units, *, forced, checked)・has_checks(start)・named(thickness)・
  named_why(word)・tier_adds(head)・tier_auto(head)・raise_doc(doc, *, units, run)・run_paths・outside_cited・late_signals・
  run_depth(doc)・omits(head)・skip_reason(doc, head)・lines(doc, head, *, cmd_skipped): 元 lib/depth.py のまま
- signals(items, keys, touched, *, origin, head_record, late, declared)・PLAN_ORIGIN・LATE_UNREAD・NO_LATE_RECORD: 元 lib/latedepth.py
- late_records(fix): fix の返り（欄 tdd_refused・accept_trace）から signals の late を組む（元 lib/fixbeside.py の late_records を、
  fix の出力の欄を直に読む形にした物）
- consulted_units(rows): 元 lib/consult.py
- switches(tier, tree_named, record): 段の切り替え {tier, omits, merge, tree, adds, lines}（node tiers と、固定材料の run の fix-in）
- docs_of(rows)・rows_of(doc): 単位の深さの行 [{unit_id, depth, why}] と控えの形 {units: {key: {depth, why}}} の行き来
"""
from __future__ import annotations

import json
import pathlib
import posixpath

import entry
import headdepth
import impact
import planmarks

LIGHT = headdepth.LIGHT
STANDARD = headdepth.STANDARD
HEAVY = headdepth.HEAVY
CONTRACT_SUFFIXES = (".json", ".yaml", ".yml", ".toml")
CONTRACT_DIR = "schemas/"
GLOB_CHARS = ("*", "?", "[")
WIRING_FILES = ("manifest.json",)   # 配線のファイルの名（部品の consumes・produces の宣言）
WIRING_SUFFIXES = (".yaml", ".yml")  # <名>/<名>.yaml の形の物が線とブロックの配線（nodes・include・with）
# 段が省く確かめの名 → 報告の文（報告の冒頭 2 に 1 行で名指す）
OMITS = {"p3.delta_review": "差分の審査（p3.delta_review）と、それに続くレンズ・手直し（修正の後の局所レビューの全部を含む）",
         "r1.comment_candidates": "独立の目の r1.comment_candidates（コメントの削除候補）",
         "r1.minimality": "独立の目 R1（r1.minimality。冗長と最小性）",
         "r2.compare": "独立の目 R2（r2.compare。独立設計との突き合わせ。独立設計そのものは修正の前に作る）",
         "r3.coherence": "独立の目 R3（r3.coherence。全体の整合）",
         "r4.hidden_scope": "独立の目 R4（r4.hidden_scope。見えていない範囲）"}
UNIT_OMIT = "軽量の単位の、緑の後と親の作業ツリーに当てた後の test_cmd の走らせ直し（TDD の名指しのテストは走らせる）"
UNCHECKED = "機械の確かめが無い（tdd_suite も test_cmd も空）"

# run 全体の深さの段の定義（ただ 1 つの表。元 lib/depth.py の TIERS のまま）。omits は段の頭の run で単位がどれも軽量の時に省く確かめ
# （OMITS の名）。adds は段が足す機能の語（entry.FEATURE_DEFAULTS の名で引く）。auto は名指しの無い auto の機能を読む語で、軽量は
# 足す物が無いので事前審査の木も off（#687）。merges は省かずに回す時に 1 つの役にまとめる目（持ち主の決め eyes-by-reason）
TIERS = {
    LIGHT: {"omits": tuple(OMITS), "adds": (), "auto": entry.SWITCH_OFF,
            "merges": ("r3.coherence", "r4.hidden_scope")},
    STANDARD: {"omits": (), "adds": (), "auto": entry.SWITCH_AUTO, "merges": ()},
    HEAVY: {"omits": (), "adds": tuple(entry.FEATURE_DEFAULTS), "auto": entry.SWITCH_AUTO, "merges": ()},
}
HEADS = headdepth.HEADS
UNKNOWN_TIER = "段の語 {word!r} は表に無いので標準と読んだ"
TREE_FEATURE = "review_tree"
ORIGIN_GATE = "gate"              # 元 consult.ORIGIN_GATE（人の関所の continue の条件を機械が相談にした頼み）
ACCEPT_TRACE = "accept-trace.json"   # 元 fixnames.ACCEPT_TRACE_FILE（fix の出力の欄 accept_trace の先の名。無い訳に名指す）


def _items_of(items, key: str) -> list:
    return [it for it in items or [] if isinstance(it, dict) and key in (it.get("unit_keys") or [])]


def _paths(items: list) -> list:
    return [p for it in items for p in it.get("allowed_paths") or [] if isinstance(p, str)]


def _tests(items: list) -> int:
    return sum(len(it.get("tests") or []) + len(it.get("rewrite_tests") or []) for it in items)


def _mine(items, keys) -> list:
    return list({id(it): it for key in keys for it in _items_of(items, key)}.values())


def _code_touched(items, keys, touched) -> list:
    """touched のうち、テストのファイルでない物（現れた順・重なりは 1 つ。impact.is_test_file）"""
    declared = {p for it in _mine(items, keys) for p in planmarks.test_paths(it)}
    return list(dict.fromkeys(p for p in touched if isinstance(p, str) and not impact.is_test_file(p, declared)))


def run_paths(items, keys, touched=()) -> int:
    """run 全体で触るファイルの数（keys の単位を載せる項目の allowed_paths と touched〔テストのファイルを除く〕の和集合）"""
    return len(set(_paths(_mine(items, keys))) | set(_code_touched(items, keys, touched)))


def outside_cited(items, keys, touched, cited) -> list:
    """touched のうち、頭の深さの役が引用した where のファイル cited の外に出たパス（テストのファイルは除く。cited が空なら空）"""
    named_ = {posixpath.normpath(p) for p in cited or [] if isinstance(p, str) and p}
    if not named_:
        return []
    return [p for p in _code_touched(items, keys, touched) if posixpath.normpath(p) not in named_]


def late_signals(*, outside=(), refused=(), consulted=(), declared=()) -> list:
    """修正の後に標準へ上げる 4 つの事実の run の理由（raise_doc の run）。空の欄からは理由を出さない。上げる先は標準で、下げない"""
    out = []
    for names, head in ((outside, "修正の差分が頭の深さの引用した where の外に出た"),
                        (refused, "TDD のループで修正役が拒まれた"),
                        (consulted, "修正役が範囲の相談をした"),
                        (declared, "修正役が直さずに残すと答えた事前審査の block が在る")):
        names = list(dict.fromkeys(str(n) for n in names or []))
        if names:
            out.append(f"{head}（{', '.join(names)}）")
    return out


def _contract(path: str) -> bool:
    return path.endswith(CONTRACT_SUFFIXES) or CONTRACT_DIR in path


def wiring(path: str) -> bool:
    if CONTRACT_DIR in path:
        return False
    p = pathlib.PurePosixPath(path)
    if p.name in WIRING_FILES:
        return True
    return p.suffix in WIRING_SUFFIXES and len(p.parts) >= 2 and p.stem == p.parent.name


def unit_depth(items, key: str, *, checked: bool) -> tuple:
    """単位 key の (深さ, 理由の並び)。外れた条件が 1 つでも在れば標準で、外れた条件を全部並べる"""
    mine = _items_of(items, key)
    if not mine:
        return STANDARD, ["単位を載せる修正案の項目が無い（形が分からない）"]
    paths, tests = _paths(mine), _tests(mine)
    out = []
    globs = [p for p in paths if any(c in p for c in GLOB_CHARS)]
    if globs:
        out.append(f"触るファイルに glob が在る（{', '.join(globs)}）")
    wired = bool(paths) and all(wiring(p) for p in paths)
    contracts = [] if wired else [p for p in paths if _contract(p)]
    if contracts:
        out.append(f"約束の形のファイルを触る（{', '.join(contracts)}）")
    if not checked:
        out.append(UNCHECKED)
    if out:
        return STANDARD, out
    shape = "配線だけ（メイングラフとサブグラフの YAML と manifest.json）" if wired else "約束の形のファイルなし"
    return LIGHT, [f"触るファイル {len(paths)} 個・テスト {tests} 本・{shape}・機械の確かめあり"]


def has_checks(start) -> bool:
    start = start if isinstance(start, dict) else {}
    return bool(start.get("test_cmd") or start.get("tdd_suite"))


def named(thickness) -> str:
    word = str(thickness or "").strip()
    return word if word in HEADS else ""


def tier_adds(head) -> tuple:
    """段 head が足す機能の語の並び（知らない語・空は空）"""
    return tuple((TIERS.get(head) or {}).get("adds") or ())


def tier_auto(head) -> str:
    return (TIERS.get(head) or {}).get("auto") or entry.SWITCH_AUTO


def named_why(word: str) -> str:
    return f"入力 thickness の名指し（{word}）"


def decide_doc(items, open_units, *, forced: str, checked: bool) -> dict:
    forced = (forced or "").strip()
    units = {}
    for key in open_units or []:
        if named(forced):
            unit = forced if forced in (LIGHT, STANDARD) else STANDARD
            units[key] = {"depth": unit, "why": [named_why(forced)]}
        else:
            d, why = unit_depth(items, key, checked=checked)
            units[key] = {"depth": d, "why": why}
    return {"units": units, "forced": forced, "raised": []}


def raise_doc(doc: dict, *, units: dict, run: list) -> dict:
    out = json.loads(json.dumps(doc))
    raised = list(out.get("raised") or [])
    for key, why in units.items():
        if key not in out["units"]:
            raised.append(f"{key}: {why}（直す義務の単位の外）")
            continue
        row = out["units"][key]
        if row["depth"] != STANDARD:
            row["depth"] = STANDARD
            row["why"] = [*row["why"], f"標準へ上げた: {why}"]
    for why in run:
        raised.append(why)
        for row in out["units"].values():
            if row["depth"] != STANDARD:
                row["depth"] = STANDARD
                row["why"] = [*row["why"], f"標準へ上げた: {why}"]
    out["raised"] = raised
    return out


def run_depth(doc) -> str:
    rows = list(((doc or {}).get("units") or {}).values())
    return LIGHT if rows and all(r.get("depth") == LIGHT for r in rows) else STANDARD


def omits(head) -> tuple:
    return TIERS[head]["omits"] if head in HEADS and head in TIERS else TIERS[STANDARD]["omits"]


def skip_reason(doc, head) -> str:
    if not omits(head) or run_depth(doc) != LIGHT:
        return ""
    return (f"軽量で省いた（run の頭の深さが {head} で、直す義務の単位 {len(doc['units'])} 個がすべて軽量。"
            "計画 2026-10-06-variable-depth の決め 6）")


def lines(doc, head, *, cmd_skipped: int) -> list:
    rows = ((doc or {}).get("units") or {})
    if not rows:
        return [f"深さ: {STANDARD}（直す義務の単位が無い）"]
    light = sum(1 for r in rows.values() if r.get("depth") == LIGHT)
    head_line = f"深さ: {run_depth(doc)}（単位ごと: {LIGHT} {light} 個・{STANDARD} {len(rows) - light} 個"
    head_line += f"。入力 thickness の名指し {doc['forced']}）" if named(doc.get("forced")) else "。機械が決めた）"
    out = [head_line]
    out += [f"  - {k[:80]}: {r.get('depth')}（{' / '.join(r.get('why') or [])}）" for k, r in rows.items()]
    out += [f"  - 標準へ上げた信号: {why}" for why in doc.get("raised") or []]
    if doc.get("counted"):
        out.append(f"run の広さの数え: {doc['counted']}")
    if skip_reason(doc, head):
        named_omits = [*(OMITS[name] for name in omits(head)), *([UNIT_OMIT] if cmd_skipped else [])]
        out.append("軽量で省いた: " + "／".join(named_omits))   # 項目の中に「・」が在るので区切りは「／」
    elif cmd_skipped:
        out.append(f"軽量の単位 {cmd_skipped} 個で省いた: {UNIT_OMIT}")
    elif run_depth(doc) == LIGHT:
        out.append(f"単位はどれも軽量だが、run の頭の深さが {named(head) or STANDARD} なので省かない")
    return out


# ---------------------------------------------------------------- 段の切り替え（node tiers と固定材料の run の fix-in）
def switches(tier, tree_named: str, record) -> dict:
    """段の語 tier（判定のまとめの出力 tier）から {tier, omits, merge, tree, adds, lines}。tree は名指し（features の review_tree。
    tree_named が on・off）ならその語、無ければ entry.switch(記録, review_tree, tier_adds(段), tier_auto(段))（重厚は on・軽量は off・
    標準は auto。今の boardview.py:426-429 と同じ式）。段の語が表に無ければ標準と読み、lines に訳（今の named の倒し方）。
    record は始めの記録の dict（features の切り替えを読む。None なら既定）"""
    word = str(tier or "").strip()
    head = word if word in TIERS else STANDARD
    out_lines = [] if word in TIERS else [UNKNOWN_TIER.format(word=word)]
    named_tree = str(tree_named or "").strip()
    if named_tree in (entry.SWITCH_ON, entry.SWITCH_OFF):
        tree = named_tree
    else:
        tree = entry.switch(record if isinstance(record, dict) else {}, TREE_FEATURE, tier_adds(head), tier_auto(head))
    adds = list(tier_adds(head))
    spec = TIERS[head]
    out_lines += [f"段 {head} が省く物（単位がどれも軽量の時）: {'・'.join(spec['omits'])}" if spec["omits"]
                  else f"段 {head} が省く物: 無い",
                  f"段 {head} が足した物: {'・'.join(adds) or '無い'}"]
    return {"tier": head, "omits": bool(spec["omits"]), "merge": bool(spec["merges"]), "tree": tree, "adds": adds, "lines": out_lines}


def rows_of(doc: dict) -> list:
    """控えの形 {units: {key: {depth, why}}} → 行 [{unit_id, depth, why}]（why は「 / 」で継いだ字）"""
    return [{"unit_id": key, "depth": row.get("depth"), "why": " / ".join(row.get("why") or [])}
            for key, row in ((doc or {}).get("units") or {}).items()]


def docs_of(rows, *, forced: str = "") -> dict:
    """行 [{unit_id, depth, why}] → 控えの形（why は 1 つの字を 1 行に）"""
    return {"units": {r["unit_id"]: {"depth": r.get("depth"), "why": [r["why"]] if r.get("why") else []}
                      for r in rows or [] if isinstance(r, dict) and r.get("unit_id")},
            "forced": forced, "raised": []}


def skip_rerun(doc: dict, head) -> list:
    """緑の後の試験の走らせ直しを省く単位の key（段が省く物を持つ時だけ、軽量の単位。ほかは []。今の depth.omits の軽量の単位）"""
    if not omits(head):
        return []
    return [key for key, row in ((doc or {}).get("units") or {}).items() if row.get("depth") == LIGHT]


# ---------------------------------------------------------------- 修正の後の上げ直しの信号（元 lib/latedepth.py）
PLAN_ORIGIN = "計画の allowed_paths"
LATE_UNREAD = "修正の後の信号の控えが読めない（{why}）"
NO_LATE_RECORD = "修正の後の信号の控えが無い（{name}）——範囲の相談を数えていない"


def consulted_units(rows) -> list:
    """受け付けの行 rows（fix の出力の欄 accept_trace の先の行）のうち、修正役か受け付けが範囲の相談を頼んだ行（op が conflict の
    ASKED_OP。人の関所の条件の相談 ORIGIN_GATE は機械が立てた物なので除く）の単位の名（現れた順・重なりは 1 つ）。unit_keys の
    無い行は『項目 n』（元 lib/consult.py）"""
    import conflict
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("op") != conflict.ASKED_OP or row.get("origin") == ORIGIN_GATE:
            continue
        keys = [k for k in row.get("unit_keys") or [] if isinstance(k, str) and k]
        for name in keys or [f"項目 {row.get('item')}"]:
            if name not in out:
                out.append(name)
    return out


def late_records(fix, resolve) -> dict:
    """fix の返り（欄 tdd_refused {refused, unread} と accept_trace の pointer）の、修正の後に深さを上げる信号の元
    {refused, trace, missing, unread}（元 lib/fixbeside.py の late_records。fix の出力の欄を直に読む）。accept_trace が null なら
    missing に名を、在るのに読めない・{"error"}・行の配列でない時は unread に訳を足す。resolve は (pointer, 欄の名) → パス（stages.resolve）"""
    got: dict = {"refused": [], "trace": None, "missing": [], "unread": []}
    if not isinstance(fix, dict):
        got["unread"].append("修正の段の出力が dict でない")
        return got
    refused = fix.get("tdd_refused")
    if isinstance(refused, dict) and isinstance(refused.get("refused"), list) and isinstance(refused.get("unread"), list):
        got["refused"] = [str(k) for k in refused["refused"]]
        got["unread"] += [str(x) for x in refused["unread"]]
    else:
        got["unread"].append("修正の控え tdd_refused の形が違う（{refused, unread} でない）")
    if fix.get("accept_trace") is None:
        got["missing"].append(ACCEPT_TRACE)
        return got
    try:
        path = pathlib.Path(resolve(fix["accept_trace"], "accept_trace"))
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError) as e:
        got["unread"].append(f"修正の控え accept_trace が読めない（{type(e).__name__}: {e}）")
        return got
    if isinstance(doc, dict) and "error" in doc:
        got["unread"].append(f"修正の控え accept_trace を組めなかった（{doc['error']}）")
    elif not isinstance(doc, list):
        got["unread"].append("修正の控え accept_trace の形が違う（行の配列でない）")
    else:
        got["trace"] = [r for r in doc if isinstance(r, dict)]
    return got


def signals(items, keys, touched, *, origin: str, head_record, late, declared=()) -> tuple:
    """(run の信号の並び, counted の 1 行)。元 lib/latedepth.py の signals のまま（headdepth の控えの読み口は KEEP）"""
    late = late or {"refused": [], "trace": None, "missing": [], "unread": []}
    cited = headdepth.cited_files(headdepth.read_file(head_record)) if head_record is not None else []
    out = [*late_signals(outside=outside_cited(items, keys, touched, cited), refused=late["refused"],
                         consulted=consulted_units(late["trace"] or []), declared=declared),
           *(LATE_UNREAD.format(why=why) for why in late["unread"])]
    counted = (f"触るファイル {run_paths(items, keys, touched)} 個（起点: {origin}）"
               + "".join(f"／{NO_LATE_RECORD.format(name=name)}" for name in late["missing"]))
    return out, counted
