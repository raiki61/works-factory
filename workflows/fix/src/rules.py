"""修正役と TDD の役の指示に入れる値（lib/fixrules.py の値の関数の写し。docs/design/fix.md の 1.5.1）。

写しは元の関数の中身を変えない。指示の文は prompts/ の md が持ち、元の rulebook.render に渡した節の組み立て（fix_parts・tdd_parts・
ruler_parts・write_prompt・tdd_render・ruler_prompt・start_lines）は写さない（src/prompts.py が prompt.emit に渡す値と段落の真偽を
組む）。証拠の種類の数え（kinds_now・kinds_for・remember など）と brief の行（brief_rows）は輪も使うので lib/evidencekinds.py・lib/planbrief.py
へ出た。変えた所: 範囲の相談の控え（ask_config は
控えのパスを返し、文は md）、相談の答えの続きの周の値（resume_values）。下請けの項目の値（元の implementer_values・g1_items・review_values・
g1_row など）は lib/subagents.py へ出て、ここは渡す前の計算（dispatched）だけを持つ（docs/design/fix.md の 2.3.2）。
"""
import json
import sys

sys.dont_write_bytecode = True

from src import board  # noqa: E402  （直す義務 fix_duty。元 conflict.fix_duty の値で受ける形）
import evidencekinds  # noqa: E402  （lib。証拠の種類の数え）
from src import consult  # noqa: E402  （同じ block。範囲の相談の控え・置き場・答え）
import libdocs  # noqa: E402
import oneline  # noqa: E402
import planbrief  # noqa: E402  （承認済みの修正案の項目ごとの brief の凍結・単位ごとの引き）
import planmarks  # noqa: E402  （項目の範囲: allowed_paths と受け入れのテストのファイル。並べる項目の分け方）
import planrange  # noqa: E402  （範囲の値 fix_scope・項目の glob と tests の id。行の文は下の scope_rows・tests_rows）

FIX_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file", "summary_file")
TDD_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file")
RULER_VALUES = ("conflicts_file", "ids", "judgment_file", "request_file", "policy_path")
PASSES = ("first", "ruled")   # 修正役の 1 回目と、裁定の後の 2 回目（印 continue=fix の会話の続き）
HEAD_FILES = dict(zip(PASSES, (board.FIX_HEAD_FILE, board.RULED_HEAD_FILE), strict=True))   # 段 → 段の頭の木の控え
ANSWER_NODES = dict(zip(PASSES, ("consult-answer", "ruled-consult-answer"), strict=True))   # 段 → 範囲の相談に答える役の節
PHASES = ("route", "test", "fix", "refactor")   # TDD の輪の役の段
BRIEF_BROKEN = (f"修正案の brief の控え（置き場の {planbrief.LEDGER}）か欄の控え（置き場の {planbrief.planmarks.FIELDS_FILE}）が壊れているか"
                "凍結の後に書き換えられ、承認した要求の正本が"
                "引けない——brief の無い指示書で役を起こさずに止める")
ASK_DRAFT = "draft-reply.json"   # 修正役が事前の確かめに渡す返答の下書き（相談の置き場。作業ツリーの外）


def owed_values(b, values: dict, *, owed, withheld_by=None, returned=()) -> dict:
    """指示書に埋める値の open_units を、受け付けと同じ fixboard.fix_duty の owed に替えた物（判定の出口の is_open の並びを
    保ち、関所で答えて直す義務に戻った単位を後ろに足す）。出口の値が読めなければ owed の並べ替えだけ。
    b は置き場、owed は写しの規則の直す義務の単位（元は盤面の _owed_units）、withheld_by・returned は問いの台帳の値（元は
    gatemarks の盤面の読み）。どれも呼び手が渡す"""
    try:
        keys = json.loads(values.get("open_units") or "[]")
    except (ValueError, TypeError):
        keys = []
    owed, _ = board.fix_duty(b, owed, withheld_by=withheld_by, returned=returned)
    seen = [k for k in keys if k in owed] if isinstance(keys, list) else []
    return {**values, "open_units": json.dumps(seen + sorted(owed - set(seen)), ensure_ascii=False)}


def brief_halt(err) -> str:
    """brief の控えが壊れた（planbrief.LedgerBroken の err）ことを名指す理由の 1 行（止めるのは呼び手。元は盤面を止めた）"""
    return f"{BRIEF_BROKEN}: {oneline.one_line(err)}"


def briefs_or_halt(b, **sources) -> list:
    """置き場 b の brief（planbrief.cut。修正案の欄の控えが無い run は []）。sources は planbrief.cut の材料（plan・judgment・
    purpose・structure・round_）。控えが壊れていれば理由の ValueError（黙って brief の無い指示書にしない）"""
    try:
        return planbrief.cut(b, **sources)
    except planbrief.LedgerBroken as e:
        raise ValueError(brief_halt(e)) from None


def _items(items):
    """承認済みの修正案の項目（planmarks.approved_items の形の値か、それを返す口）。引けない・控えが壊れていれば None"""
    try:
        return items() if callable(items) else items
    except (planmarks.FieldsBroken, ValueError, OSError):
        return None


def _paths_line(paths) -> str:
    return "、".join(f"`{p}`" for p in paths) or planbrief.NONE


def scope_rows(got) -> str:
    """範囲の節の行: 項目ごとの範囲（allowed_paths の glob・tests と rewrite_tests の id のファイル）・out_of_scope・合意で外したパスと、
    全部の項目に効く許し。got は planrange.fix_scope の値で、None なら空。見出しと頭の決まりの文は md（元 planrange.scope_text の行）"""
    if got is None:
        return ""
    lines = []
    for it in got["items"]:
        units = "、".join(str(k) for k in it.get("unit_keys") or []) or planbrief.NONE
        oos = [f"`{r['glob']}`" + (f"（{r['why']}）" if r.get("why") else "") for r in it.get("out_of_scope") or []
               if isinstance(r, dict) and isinstance(r.get("glob"), str) and r["glob"]]
        lines += [f"- 項目 {it.get('item')}（単位: {units}）",
                  f"  - allowed_paths: {_paths_line(planrange.globs(it))}",
                  f"  - テストのファイル（tests・rewrite_tests の id）: {_paths_line(planmarks.test_paths(it))}",
                  f"  - out_of_scope: {'、'.join(oos) or planbrief.NONE}"]
        if it.get(planrange.LIFTED):
            lines.append(f"  - 相談で out_of_scope から外したパス: {_paths_line(it[planrange.LIFTED])}")
    lines.append(f"- 全部の項目に効く許し: {_paths_line(got['permits'])}")
    return "\n".join(lines)


def tests_rows(got, edits: dict, frozen=None) -> str:
    """テストの節の行: 足してよい新しいテスト・本体を変えてよい既存のテストの名指しと範囲・凍ったテストのファイル。got は planrange.fix_scope の値
    （照らさない項目なら None で、新しいテストの行を出さない）、edits は conflict.edit_permits の値、frozen は凍ったテストの値（無ければ None）。
    見出しと頭・結びの文は md（元 planrange.tests_text の行）"""
    verified = list((frozen or {}).get("verified") or [])
    lines = []
    if got is not None:
        lines.append("- 足してよい新しいテスト（修正案の項目の tests。範囲の相談で許された物も入っている）:")
        for it in got["items"]:
            units = "、".join(str(k) for k in it.get("unit_keys") or []) or planbrief.NONE
            lines.append(f"  - 項目 {it.get('item')}（単位: {units}）: {_paths_line(planrange.test_ids(it))}")
    # 凍結の照らしは輪が確かめた書き換えを許しから外すので、事後の関門が id で許しても全体では拒まれる
    lines += [f"- 本体を変えてよい既存のテストの名指し（修正案の rewrite_tests と、修正案が消す名を名指すテスト）: "
              f"{_paths_line([t for t in edits['tests'] if t not in verified])}",
              f"- 本体を変えてよい既存のテストの範囲（範囲の相談で許された範囲と、裁定 fix_test_scope の範囲）: "
              f"{_paths_line([x for x in edits['limits'] if x not in (edits.get('broken') or [])])}"]
    if edits.get("broken"):
        lines.append(f"- 直す前から壊れていた関わる試験（ついでに直してよい。最後の承認ノードに出る）: {_paths_line(edits['broken'])}")
    files = (frozen or {}).get("files") or []
    if files:
        lines.append(f"- 凍ったテストのファイル（TDD のループが緑にした単位のテスト）: {_paths_line(files)}")
    return "\n".join(lines)


def dispatched(owed: list[str], green=frozenset()) -> list[str]:
    """修正役が下請けを起こす単位（owed の順）: TDD の輪が緑にした単位 green（支度の script が tddloop.green_units で引く。tddloop が
    fixrules を import するので、ここでは引かない）を除いた物（依頼 243 の 2）"""
    return [k for k in owed if k not in green]


def head_file(pass_: str) -> str:
    """段 pass_ の頭の木の控えのファイルの名（HEAD_FILES）。PASSES に無い段は ValueError"""
    if pass_ not in HEAD_FILES:
        raise ValueError(f"段 {pass_!r} は {PASSES} のどれでもない")
    return HEAD_FILES[pass_]


def answer_node(pass_: str) -> str:
    """段 pass_ の範囲の相談に答える役の節（ANSWER_NODES）。PASSES に無い段は ValueError"""
    if pass_ not in ANSWER_NODES:
        raise ValueError(f"段 {pass_!r} は {PASSES} のどれでもない")
    return ANSWER_NODES[pass_]


# ---------------------------------------------------------------- 修正役の値
def lib_section(b, repo, values: dict, shared=None) -> str:
    """ライブラリの文書の節（libdocs.section。控えは置き場 b、run をまたぐ控えは根 shared）: 直す義務の単位のファイルと今の差分の
    ファイルが使うライブラリ。見出しと頭の文は md が持つ（src/prompts.py が切る）"""
    try:
        keys = set(json.loads(values.get("open_units") or "[]"))
    except (ValueError, TypeError):
        keys = None
    files, why = libdocs.unit_files(repo, values.get("judgment_file") or "", keys) if repo is not None else ([], "")
    text = libdocs.section(b, repo, files + (evidencekinds.changed_paths(repo, values.get("base_rev")) if repo is not None else []),
                           shared=shared)
    return text + (f"\n- 単位のファイルの引き: {why}" if why else "")


def ask_config(b, repo, values: dict, pass_: str, *, items=None) -> str:
    """範囲の相談の控えを置き場 b に書き（consult.write_config。事前の確かめのコマンドが読み、受け付けの拒否の文が相談を言うかを
    決める）、控えのパスを返す（修正役の段落 ask と下請けの段落 ask の文は md。コマンドの字は src/prompts.py が組む）。
    入力 plan_session（相談の相手の役の名）が空・承認済みの修正案の項目 items（planmarks.approved_items の形の値か口）が引けない run は
    書かずに ""。values の tdd_record は TDD の輪の記録のファイル（空は輪の無い run）"""
    node = (values.get("plan_session") or "").strip()
    if not node or repo is None:
        return ""
    got = _items(items)
    if not got:
        return ""
    doc = {"board": str(b), "repo": str(repo), "pass": pass_,
           "base_rev": values.get("base_rev") or "",
           "tdd_record": values.get("tdd_record") or "",
           "items": consult.items_doc(got)}
    return str(consult.write_config(b, doc))


def resume_values(got: dict) -> dict:
    """範囲の相談の答えの後の周の値（consult.take の返り got）: 答えのファイル・残りの相談の周・はみ出しの答えか（答えの行の origin が
    accept。今の resume の節の選び）"""
    return {"answer_file": str(got["answer_file"]), "left": str(got["left"]), "overflow": got.get("origin") == consult.ORIGIN_ACCEPT}
