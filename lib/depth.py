"""単位ごとの深さ（計画 docs/plans/2026-10-06-variable-depth.md。ライン darkfactory のモジュール・層 L6）。使うのはブロックの script。

判定が切った単位ごとに、修正案の項目の欄（plan-fields.json）の形から深さ（軽量か標準）を機械が決め、修正の後の信号で標準へ上げる。
標準は今の振る舞いのすべて。軽量は、測りで何も見つけなかった確かめ（SKIPPED: 差分の審査とレンズ・手直し、独立の目の R1〜R4 と
コメントの削除候補）を省く。省くのは graph の外の物と graph が optional と言う物だけ（R1〜R4 本体と差分の審査は持ち主の決定
2026-10-06 で写しの graph の ! 行で optional にした）。ブロックはこの控えを読まない——線が省く理由の文（skip_reason）を平の入力
として渡し、差分の審査だけは線の h-redepth が盤面で省く（差分の審査のブロックを起こす前に、境の節 h-review が盤面の待ちを見るため）。

- unit_depth(items, key, *, checked): 単位 1 つの (深さ, 理由の並び)。決め 3 の 5 つの条件を全部満たす時だけ軽量。
  配線だけの単位（触るファイルが全部 wiring の物）は条件 4（約束の形のファイル）に数えない（決め 3 の補い）
- wiring(path): 配線のファイルか（線とブロックの YAML＝<名>/<名>.yaml・.yml と manifest.json。schemas/ の下は除く）
- decide_doc(items, open_units, *, forced, checked): 直す義務の単位の全部の深さ（控えの形）。forced は入力 thickness の語
  （空・自動は機械が決める。軽量・標準は全部をその深さに固定）
- has_checks(start): 始めの記録 start に機械の確かめ（tdd_suite か test_cmd）が在るか（unit_depth の checked に渡す。訳は UNCHECKED）
- named(thickness): 入力 thickness が名指す深さ（軽量・標準。ほかの語・空は空）。訳は named_why(深さ)
- raise_doc(doc, *, units, run): 信号で標準へ上げた控え。units は {単位: 理由}（その単位だけ）、run は理由の並び（全部の単位）。下げない
- run_wide(items, keys, touched=()): 控えの単位 keys を合わせた run 全体の広さ（触るファイルの和集合と、受け入れと書き換えの
  テストの和）が単位ごとの上限 MAX_PATHS・MAX_TESTS を超えた理由の並びと、触るファイルの数。触るファイルは計画の allowed_paths に、修正の実際の差分
  （touched。呼び手が渡す）のうちテストのファイルを除いた物を足して数える。呼び手が run の信号に足し、単位ごとには軽量の集まりも
  標準へ上げる（raise_doc の run）
- run_depth(doc): 切った後の run 全体の段の深さ（全部の単位が軽量の時だけ軽量。単位が無ければ標準）
- skip_reason(doc): run が軽量なら省く理由の文、標準なら空（ブロックの平の入力 skip・skip_optional に渡す）
- lines(doc): 報告の冒頭 2 の行（単位ごとの深さの数・上げた理由・run の広さの数え・軽量で省いた物。doc の eyes_kept が真なら、
  事前審査の代わりに回した独立の目を省いた物に数えない）
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import impact  # noqa: E402
import planmarks  # noqa: E402

LIGHT = "軽量"
STANDARD = "標準"
MAX_PATHS = 3         # 測り: 何も見つけなかった単位は allowed_paths 1〜3 個、見つけた単位は 4 個（MAX_PATHS を超える）
MAX_TESTS = 2         # 測り: 同じく受け入れのテストと書き換える既存のテストが合わせて 1 本、見つけた単位は 4 本（MAX_TESTS を超える）
CONTRACT_SUFFIXES = (".json", ".yaml", ".yml", ".toml")
CONTRACT_DIR = "schemas/"
GLOB_CHARS = ("*", "?", "[")
WIRING_FILES = ("manifest.json",)   # 配線のファイルの名（部品の consumes・produces の宣言）
WIRING_SUFFIXES = (".yaml", ".yml")  # <名>/<名>.yaml の形の物が線とブロックの配線（nodes・include・with）
# 軽量の run で省く物（報告の冒頭 2 に 1 行ずつ名指す）。どれも 2026-10-05 の自分食いの小さい run で何も見つけなかった
# 決め 6 は 2026-10-05 の測り、決め 9 は持ち主の決定 2026-10-06（写しの graph の ! 行で optional にした節）。AI の報告は省かない（決め 10）
DELTA_SKIPPED = "差分の審査（p3.delta_review）と、それに続くレンズ・手直し（修正の後の局所レビューの全部を含む）"
EYES_SKIPPED = ("独立の目の r1.comment_candidates（コメントの削除候補）",
                "独立の目 R1（r1.minimality。冗長と最小性）",
                "独立の目 R2（r2.compare。独立設計との突き合わせ。独立設計そのものは修正の前に作る）",
                "独立の目 R3（r3.coherence。全体の整合）",
                "独立の目 R4（r4.hidden_scope。見えていない範囲）")
SKIPPED = (DELTA_SKIPPED, *EYES_SKIPPED)
UNCHECKED = "機械の確かめが無い（tdd_suite も test_cmd も空）"


def _items_of(items, key: str) -> list:
    return [it for it in items or [] if isinstance(it, dict) and key in (it.get("unit_keys") or [])]


def _paths(items: list) -> list:
    return [p for it in items for p in it.get("allowed_paths") or [] if isinstance(p, str)]


def _tests(items: list) -> int:
    return sum(len(it.get("tests") or []) + len(it.get("rewrite_tests") or []) for it in items)


def _wide(items, keys, touched=()) -> tuple:
    """(run 全体で触るファイルの集合, 受け入れと書き換えのテストの本数)。keys の単位を載せる項目を重ねずにまとめ、触るファイルは
    計画の allowed_paths と touched（テストのファイルを除く）の和集合（重なりは 1 個）。テストのファイルの見分けは impact.is_test_file
    （宣言＝項目の tests・rewrite_tests の id のファイルか、名の慣習。TDD の輪が凍らせるテストのファイルの見分けと同じ口）"""
    mine = list({id(it): it for key in keys for it in _items_of(items, key)}.values())
    declared = {p for it in mine for p in planmarks.test_paths(it)}
    return set(_paths(mine)) | {p for p in touched if isinstance(p, str) and not impact.is_test_file(p, declared)}, _tests(mine)


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
    return word if word in (LIGHT, STANDARD) else ""


def named_why(word: str) -> str:
    return f"入力 thickness の名指し（{word}）"


def decide_doc(items, open_units, *, forced: str, checked: bool) -> dict:
    forced = (forced or "").strip()
    units = {}
    for key in open_units or []:
        if named(forced):
            units[key] = {"depth": forced, "why": [named_why(forced)]}
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


def skip_reason(doc) -> str:
    if run_depth(doc) != LIGHT:
        return ""
    return f"軽量で省いた（直す義務の単位 {len(doc['units'])} 個がすべて軽量。計画 2026-10-06-variable-depth の決め 6）"


def lines(doc) -> list:
    rows = ((doc or {}).get("units") or {})
    if not rows:
        return [f"深さ: {STANDARD}（直す義務の単位が無い）"]
    light = sum(1 for r in rows.values() if r.get("depth") == LIGHT)
    head = f"深さ: {run_depth(doc)}（単位ごと: {LIGHT} {light} 個・{STANDARD} {len(rows) - light} 個"
    head += f"。入力 thickness の名指し {doc['forced']}）" if named(doc.get("forced")) else "。機械が決めた）"
    out = [head]
    out += [f"  - {k[:80]}: {r.get('depth')}（{' / '.join(r.get('why') or [])}）" for k, r in rows.items()]
    out += [f"  - 標準へ上げた信号: {why}" for why in doc.get("raised") or []]
    if doc.get("counted"):
        out.append(f"run の広さの数え: {doc['counted']}")
    if run_depth(doc) == LIGHT:   # 事前審査を run の頭の深さで飛ばした run（eyes_kept）は、代わりの独立の目を省かない
        skipped = (DELTA_SKIPPED,) if doc.get("eyes_kept") else SKIPPED
        out.append("軽量で省いた: " + "／".join(skipped))   # 1 行にまとめる（項目の中に「・」が在るので区切りは「／」）
    return out


# ---------------------------------------------------------------- 盤面を読む口（線の節 h-depth・h-redepth）