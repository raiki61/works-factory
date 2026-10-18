"""単位ごとの深さ（計画 docs/plans/2026-10-06-variable-depth.md。ライン darkfactory のモジュール・層 L6）。使うのはブロックの script。

判定が切った単位ごとに、修正案の項目の欄（plan-fields.json）の形から深さ（軽量か標準）を機械が決め、修正の後の信号で標準へ上げる。
run 全体の深さの段（軽量・標準・重厚）の定義は表 TIERS 1 か所（docs/design.md の「深さの段の表」の正本）。単位の深さの語は軽量・標準の 2 つ。
標準は今の振る舞いのすべて。段の省く物（TIERS の omits。OMITS の確かめ: 差分の審査とレンズ・手直し、独立の目の R1〜R4 とコメントの
削除候補）は、測りで何も見つけなかった確かめで、その段の頭の run で直す義務の単位がどれも軽量の時だけ省く。省くのは graph の外の物と
graph が optional と言う物だけ（R1〜R4 本体と差分の審査は持ち主の決定 2026-10-06 で写しの graph の ! 行で optional にした）。
同じ段の頭の run では、軽量の単位ごとに緑の後と親に当てた後の test_cmd の走らせ直し（UNIT_OMIT）も省く（omits が段の口）。
省くかを決めるのはこのモジュールだけで、呼ぶのは差分の審査が修正のブロックの delta-cut（fixboard.redepth）、R1〜R4 とコメントの
削除候補が目のブロックの prep（skip_reason）、test_cmd が修正のブロックの TDD の輪と組の当て（fixboard.unit_depths）。

- unit_depth(items, key, *, checked): 単位 1 つの (深さ, 理由の並び)。決め 3 の 5 つの条件を全部満たす時だけ軽量。
  配線だけの単位（触るファイルが全部 wiring の物）は条件 4（約束の形のファイル）に数えない（決め 3 の補い）
- wiring(path): 配線のファイルか（線とブロックの YAML＝<名>/<名>.yaml・.yml と manifest.json。schemas/ の下は除く）
- decide_doc(items, open_units, *, forced, checked): 直す義務の単位の全部の深さ（控えの形）。forced は入力 thickness の語
  （空・自動は機械が決める。軽量・標準は全部をその深さに固定。重厚は単位では標準に固定する——重厚は単位でなく run に足す物）
- has_checks(start): 始めの記録 start に機械の確かめ（tdd_suite か test_cmd）が在るか（unit_depth の checked に渡す。訳は UNCHECKED）
- named(thickness): 入力 thickness が名指す深さの段（HEADS の語。ほかの語・空は空）。訳は named_why(深さ)
- tier_adds(head): 段 head が足す機能の語の並び（TIERS の足す物。知らない語・空は空）。機能の名と切り替えの式は entry
  （entry.feature_words・entry.switch の adds に渡す）
- tier_auto(head): 段 head で、名指しの無い auto の機能（事前審査の木）を読む語（TIERS の auto。軽量は off、ほかと知らない語・空は auto。
  entry.feature_words・entry.switch の auto に渡す）
- merges(head): 段 head の頭の run で、目を省かずに回す時に 1 つの役にまとめる独立の目の名の並び（TIERS の merges。OMITS の名。知らない語・
  空は空）。目のブロックの prep が読み、R3・R4 を 1 つの会話で見る役 eyes-one を起こす
- raise_doc(doc, *, units, run): 信号で標準へ上げた控え。units は {単位: 理由}（その単位だけ）、run は理由の並び（全部の単位）。下げない
- run_wide(items, keys, touched=()): 控えの単位 keys を合わせた run 全体の広さ（触るファイルの和集合と、受け入れと書き換えの
  テストの和）が単位ごとの上限 MAX_PATHS・MAX_TESTS を超えた理由の並びと、触るファイルの数。触るファイルは計画の allowed_paths に、修正の実際の差分
  （touched。呼び手が渡す）のうちテストのファイルを除いた物を足して数える。呼び手が run の信号に足し、単位ごとには軽量の集まりも
  標準へ上げる（raise_doc の run）
- outside_cited(items, keys, touched, cited): 修正の差分 touched のうち、頭の深さの役が引用した where のファイル cited の外に出たパス
  （テストのファイルは run_wide と同じ除き _code_touched で除く。cited が空なら空）
- late_signals(*, outside, refused, consulted, declared): 修正の後の 4 つの事実（引用の外の差分・TDD のループで修正役が拒まれた単位・範囲の相談をした
  単位・直す側が直さずに残すと答えた案の審査の block）の run の理由の並び。空の欄からは理由を出さない。呼ぶのは修正のブロックの fixboard.depth_signals・redepth と、線の redepth
  （raise_doc の run に足す。上げるだけで下げない）
- run_depth(doc): 切った後の単位の深さの全体（全部の単位が軽量の時だけ軽量。単位が無ければ標準）
- omits(head): 段 head が省く確かめの名の並び（TIERS の omits。知らない語・空は標準の段の物）。空でない段だけが単位の軽量で
  test_cmd を省く
- skip_reason(doc, head): run の頭の深さの段 head が省く物を持ち、単位の深さの全体が軽量なら省く理由の文、ほかは空
  （差分の審査と目の R1〜R4 を省く訳。線の redepth の skip_optional）。知らない語・空の head は標準
- lines(doc, head, *, cmd_skipped): 報告の冒頭 2 の行（単位ごとの深さの数・上げた理由・run の広さの数え・省いた物か、頭の深さで省かなかった訳）。
  cmd_skipped は TDD の輪が軽量で test_cmd を走らせなかった単位の数（省いた時点の記録から数える。上げ直しの後の深さは
  省いた時の深さと違いうる）。0 なら test_cmd の省きを言わない（test_cmd が空・関門が off の run は何も省いていない）
"""
import json
import pathlib
import posixpath
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import entry  # noqa: E402
import impact  # noqa: E402
import planmarks  # noqa: E402

LIGHT = "軽量"
STANDARD = "標準"
HEAVY = "重厚"
MAX_PATHS = 3         # 測り: 何も見つけなかった単位は allowed_paths 1〜3 個、見つけた単位は 4 個（MAX_PATHS を超える）
MAX_TESTS = 2         # 測り: 同じく受け入れのテストと書き換える既存のテストが合わせて 1 本、見つけた単位は 4 本（MAX_TESTS を超える）
CONTRACT_SUFFIXES = (".json", ".yaml", ".yml", ".toml")
CONTRACT_DIR = "schemas/"
GLOB_CHARS = ("*", "?", "[")
WIRING_FILES = ("manifest.json",)   # 配線のファイルの名（部品の consumes・produces の宣言）
WIRING_SUFFIXES = (".yaml", ".yml")  # <名>/<名>.yaml の形の物が線とブロックの配線（nodes・include・with）
# 段が省く確かめの名 → 報告の文（報告の冒頭 2 に 1 行で名指す）。どれも 2026-10-05 の自分食いの小さい run で何も見つけなかった
# 決め 6 は 2026-10-05 の測り、決め 9 は持ち主の決定 2026-10-06（写しの graph の ! 行で optional にした節）。AI の報告は省かない（決め 10）
OMITS = {"p3.delta_review": "差分の審査（p3.delta_review）と、それに続くレンズ・手直し（修正の後の局所レビューの全部を含む）",
         "r1.comment_candidates": "独立の目の r1.comment_candidates（コメントの削除候補）",
         "r1.minimality": "独立の目 R1（r1.minimality。冗長と最小性）",
         "r2.compare": "独立の目 R2（r2.compare。独立設計との突き合わせ。独立設計そのものは修正の前に作る）",
         "r3.coherence": "独立の目 R3（r3.coherence。全体の整合）",
         "r4.hidden_scope": "独立の目 R4（r4.hidden_scope。見えていない範囲）"}
UNIT_OMIT = "軽量の単位の、緑の後と親の作業ツリーに当てた後の test_cmd の走らせ直し（TDD の名指しのテストは走らせる）"
UNCHECKED = "機械の確かめが無い（tdd_suite も test_cmd も空）"

# run 全体の深さの段の定義（ただ 1 つの表。docs/design.md の「深さの段の表」はこの写しで、tests/layers の E20 が一致を縛る）。
# omits は段の頭の run で単位がどれも軽量の時に省く確かめ（OMITS の名）。標準・重厚の頭の run は単位の深さに依らず全部を通す
# （issue #561 の承認ノードの答え。記録された方針 dynamic-depth の当て方）。adds は段が足す機能の語（字を持たず
# entry.FEATURE_DEFAULTS の名で引く）。auto は名指しの無い auto の機能を読む語で、軽量は足す物が無いので事前審査の木も off（#687）。
# merges は省かずに回す時に 1 つの役にまとめる目（#687 の持ち主の決め: 別の会話にする訳が在る目だけを分ける。R2 は修正を見ない独立設計と
# 突き合わせ、ほかの観点の結論を見ると偏るので分けたまま。R1 はほかの目と重ならない穴を一番多く拾った目なので分けたまま。R3 は分ける訳に
# 当たらないので、R4 の会話に入れる）
TIERS = {
    LIGHT: {"omits": tuple(OMITS), "adds": (), "auto": entry.SWITCH_OFF,
            "merges": ("r3.coherence", "r4.hidden_scope")},
    STANDARD: {"omits": (), "adds": (), "auto": entry.SWITCH_AUTO, "merges": ()},
    HEAVY: {"omits": (), "adds": tuple(entry.FEATURE_DEFAULTS), "auto": entry.SWITCH_AUTO, "merges": ()},
}
HEADS = tuple(TIERS)


def _items_of(items, key: str) -> list:
    return [it for it in items or [] if isinstance(it, dict) and key in (it.get("unit_keys") or [])]


def _paths(items: list) -> list:
    return [p for it in items for p in it.get("allowed_paths") or [] if isinstance(p, str)]


def _tests(items: list) -> int:
    return sum(len(it.get("tests") or []) + len(it.get("rewrite_tests") or []) for it in items)


def _mine(items, keys) -> list:
    return list({id(it): it for key in keys for it in _items_of(items, key)}.values())


def _code_touched(items, keys, touched) -> list:
    """touched のうち、テストのファイルでない物（現れた順・重なりは 1 つ）。テストのファイルの見分けは impact.is_test_file
    （宣言＝keys の単位を載せる項目の tests・rewrite_tests の id のファイルか、名の慣習。TDD の輪が凍らせるテストのファイルの見分けと
    同じ口）。_wide と outside_cited が同じ除きを引く 1 か所"""
    declared = {p for it in _mine(items, keys) for p in planmarks.test_paths(it)}
    return list(dict.fromkeys(p for p in touched if isinstance(p, str) and not impact.is_test_file(p, declared)))


def _wide(items, keys, touched=()) -> tuple:
    """(run 全体で触るファイルの集合, 受け入れと書き換えのテストの本数)。keys の単位を載せる項目を重ねずにまとめ、触るファイルは
    計画の allowed_paths と touched（テストのファイルを除く。_code_touched）の和集合（重なりは 1 個）"""
    mine = _mine(items, keys)
    return set(_paths(mine)) | set(_code_touched(items, keys, touched)), _tests(mine)


def outside_cited(items, keys, touched, cited) -> list:
    """touched のうち、頭の深さの役が引用した where のファイル cited の外に出たパス（テストのファイルは除く。_code_touched。
    現れた順）。cited が空（where の無い run）なら空——省く物の無い段で上げても効かない"""
    named = {posixpath.normpath(p) for p in cited or [] if isinstance(p, str) and p}
    if not named:
        return []
    return [p for p in _code_touched(items, keys, touched) if posixpath.normpath(p) not in named]


def late_signals(*, outside=(), refused=(), consulted=(), declared=()) -> list:
    """修正の後に標準へ上げる 4 つの事実の run の理由（raise_doc の run）。outside は outside_cited の返り、refused は TDD のループで
    修正役が拒まれた単位の名（tddloop.refused_units）、consulted は範囲の相談をした単位の名（consult.consulted_units）、declared は
    修正役が直さずに残すと答えた事前審査の block の行（fixboard.declared_lines。その block を読むのは差分の審査と目の R4 だけなので、
    軽量で両方を省くと誰にも届かない）。空の欄からは理由を出さない。上げる先は標準で、下げない（raise_doc）"""
    out = []
    for names, head in ((outside, "修正の差分が頭の深さの引用した where の外に出た"),
                        (refused, "TDD のループで修正役が拒まれた"),
                        (consulted, "修正役が範囲の相談をした"),
                        (declared, "修正役が直さずに残すと答えた事前審査の block が在る")):
        names = list(dict.fromkeys(str(n) for n in names or []))
        if names:
            out.append(f"{head}（{', '.join(names)}）")
    return out


def run_wide(items, keys, touched=()) -> tuple:
    """(_wide の広さが単位ごとの上限を超えた理由の並び, 触るファイルの数)。理由は単位ごとには軽量の集まりを標準へ上げる信号"""
    paths, tests = _wide(items, keys, touched)
    paths = len(paths)
    out = []
    if paths > MAX_PATHS:
        out.append(f"run 全体で触るファイル {paths} 個（{MAX_PATHS} 個まで）")
    if tests > MAX_TESTS:
        out.append(f"run 全体の受け入れと書き換えのテストが {tests} 本（{MAX_TESTS} 本まで）")
    return out, paths


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
    if len(paths) > MAX_PATHS:
        out.append(f"触るファイルが {len(paths)} 個（{MAX_PATHS} 個まで）")
    globs = [p for p in paths if any(c in p for c in GLOB_CHARS)]
    if globs:
        out.append(f"触るファイルに glob が在る（{', '.join(globs)}）")
    if tests > MAX_TESTS:
        out.append(f"受け入れと書き換えのテストが {tests} 本（{MAX_TESTS} 本まで）")
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


def merges(head) -> tuple:
    return tuple((TIERS.get(head) or {}).get("merges") or ())


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
    return TIERS[head]["omits"] if head in HEADS else TIERS[STANDARD]["omits"]


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


# ---------------------------------------------------------------- 盤面を読む口（線の節 h-depth・h-redepth）