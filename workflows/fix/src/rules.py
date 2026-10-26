"""修正役と TDD の役の指示に入れる値（lib/fixrules.py の値の関数の写し。docs/design/fix.md の 1.5.1）。

写しは元の関数の中身を変えない。指示の文は prompts/ の md が持ち、元の rulebook.render に渡した節の組み立て（fix_parts・tdd_parts・
ruler_parts・write_prompt・tdd_render・ruler_prompt・start_lines）は写さない（src/prompts.py が prompt.emit に渡す値と段落の真偽を
組む）。変えた所: 渡した証拠の種類の控えのパス（kinds_now・iteration_next は控えのファイルを受ける）、範囲の相談の控え（ask_config は
控えのパスを返し、文は md）、相談の答えの続きの周の値（resume_values）。下請けの項目の値（元の implementer_values・g1_items・review_values・
g1_row など）は lib/subagents.py へ出て、ここは渡す前の計算（dispatched・brief_rows）だけを持つ（docs/design/fix.md の 2.3.2）。
"""
import json
import pathlib
import posixpath
import re
import sys

sys.dont_write_bytecode = True

from src import board  # noqa: E402  （直す義務 fix_duty。元 conflict.fix_duty の値で受ける形）
from leftovers import Unreadable, git_names  # noqa: E402
from src import consult  # noqa: E402  （同じ block。範囲の相談の控え・置き場・答え）
import jsonfile  # noqa: E402
import libdocs  # noqa: E402
import oneline  # noqa: E402
import planbrief  # noqa: E402  （承認済みの修正案の項目ごとの brief の凍結・単位ごとの引き）
import planmarks  # noqa: E402  （項目の範囲: allowed_paths と受け入れのテストのファイル。並べる項目の分け方）
import planrange  # noqa: E402  （範囲の値 fix_scope・項目の glob と tests の id。行の文は下の scope_rows・tests_rows）
import rulebook  # noqa: E402  （決まりの正本のフォルダの名。変更の種類の見分けが読む）

FIX_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file", "summary_file")
TDD_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file")
RULER_VALUES = ("conflicts_file", "ids", "judgment_file", "request_file", "policy_path")
PASSES = ("first", "ruled")   # 修正役の 1 回目と、裁定の後の 2 回目（印 continue=fix の会話の続き）
HEAD_FILES = dict(zip(PASSES, (board.FIX_HEAD_FILE, board.RULED_HEAD_FILE), strict=True))   # 段 → 段の頭の木の控え
ANSWER_NODES = dict(zip(PASSES, ("consult-answer", "ruled-consult-answer"), strict=True))   # 段 → 範囲の相談に答える役の節
KINDS = ("docs", "prompts", "config", "code")   # 変更の種類 → 節 evidence-<種類>
PHASES = ("route", "test", "fix", "refactor")   # TDD の輪の役の段
# 種類の見分け（パスの形だけで決める。当たらない物は種類なし）
PROMPT_DIRS = frozenset({"commands", "prompts", "agents", "skills", "rules", rulebook.CANON.parent.name})
PROMPT_NAMES = frozenset({"CLAUDE.md", "AGENTS.md", "SKILL.md", "GEMINI.md"})
DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".adoc"})
CONFIG_SUFFIXES = frozenset({".yaml", ".yml", ".toml", ".json", ".ini", ".cfg", ".conf"})
CONFIG_NAMES = frozenset({"Dockerfile", "Makefile", ".gitignore", ".gitattributes", ".editorconfig"})
CODE_SUFFIXES = frozenset({".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".rb",
                           ".sh", ".bash", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".php", ".scala", ".lua"})
PATH_TOKEN = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]\.[A-Za-z][A-Za-z0-9]*")
BRIEF_BROKEN = (f"修正案の brief の控え（置き場の {planbrief.LEDGER}）か欄の控え（置き場の {planbrief.planmarks.FIELDS_FILE}）が壊れているか"
                "凍結の後に書き換えられ、承認した要求の正本が"
                "引けない——brief の無い指示書で役を起こさずに止める")
ASK_DRAFT = "draft-reply.json"   # 修正役が事前の確かめに渡す返答の下書き（相談の置き場。作業ツリーの外）


# ---------------------------------------------------------------- 変更の種類
def kind_of(path: str):
    """パスの形から変更の種類（KINDS のどれか。分からなければ None）"""
    p = posixpath.normpath(str(path).strip())
    name = posixpath.basename(p)
    suffix = posixpath.splitext(name)[1].lower()
    dirs = set(p.split("/")[:-1])
    if name in PROMPT_NAMES or (suffix in DOC_SUFFIXES and dirs & PROMPT_DIRS):
        return "prompts"
    if suffix in DOC_SUFFIXES:
        return "docs"
    if suffix in CONFIG_SUFFIXES or name in CONFIG_NAMES or "/.github/workflows/" in f"/{p}":
        return "config"
    if suffix in CODE_SUFFIXES:
        return "code"
    return None


def unit_paths(judgment_file: str, open_units: str) -> tuple:
    """判定の直す義務の単位が指すパス（class_query の how の paths と、key の中のパスの形の語）。(パスの一覧, 読めない理由)"""
    try:
        doc = json.loads(pathlib.Path(judgment_file).read_text(encoding="utf-8"))
        keys = set(json.loads(open_units))
    except (OSError, ValueError, TypeError) as e:
        return [], f"判定か義務の単位が読めない（{type(e).__name__}）"
    out = []
    for u in (doc.get("units") if isinstance(doc, dict) else None) or []:
        if not isinstance(u, dict) or u.get("key") not in keys:
            continue
        how = (u.get("class_query") or {}).get("how") or {}
        out += [p for p in how.get("paths") or [] if isinstance(p, str)]
        out += PATH_TOKEN.findall(u["key"])
    return list(dict.fromkeys(out)), ""


def changed_paths(repo, rev: str = "HEAD") -> list:
    """作業ツリーの今の差分（修正前の版 rev からの変更と未追跡。.gitignore に当たる物は除く）のパス。git が効かなければ空"""
    try:
        got = git_names(repo, "diff", "--name-only", "--no-renames", rev or "HEAD", "--")
        got += git_names(repo, "ls-files", "--others", "--exclude-standard", "--full-name", "--", ":/")
    except Unreadable:
        return []
    return list(dict.fromkeys(got))


def select_kinds(sources: dict) -> dict:
    """{出どころ: パスの一覧} から {種類: 理由}（理由はどの出どころのどのパスか。機械の事実）。どの種類も見つからなければ
    全部の種類を「分からない」の理由で選ぶ（証拠の決まりを落とさない側）"""
    got = {}
    for src, paths in sources.items():
        for p in paths:
            k = kind_of(p)
            if k:
                got.setdefault(k, []).append(f"{src} {p}")
    if not got:
        seen = sum(len(v) for v in sources.values())
        return {k: f"変更の種類が分からない（パス {seen} 本から見分けられない）——全部載せる" for k in KINDS}
    return {k: "; ".join(got[k][:5]) + (f" ほか {len(got[k]) - 5} 本" if len(got[k]) > 5 else "") for k in KINDS if k in got}


def kinds_now(values: dict, repo, before=()) -> dict:
    """今の組み立てで載せる証拠の種類: 判定の単位のパスと今の差分から選び、この輪で前に渡した種類を足す（輪の中で減らさない）"""
    paths, why = unit_paths(values.get("judgment_file") or "", values.get("open_units") or "")
    sources = {"判定": paths, "差分": changed_paths(repo, values.get("base_rev")) if repo is not None else []}
    got = select_kinds(sources)
    if why and not any(sources.values()):
        got = {k: f"{why}——全部載せる" for k in KINDS}
    for k in before:
        got.setdefault(k, "このループで前に渡した")
    return got


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


def brief_rows(briefs: list, owed=None) -> str:
    """指示に入れる brief の行（項目ごとに 1 行。brief が無ければ空）。見出しと結びの文は md の brief-head（元 planbrief.head_text の行）"""
    return "\n".join(f"- 項目 {r['item']}: {r['file']}（sha256 {r['sha256']}・単位 {planbrief.unit_note(r.get('unit_keys'), owed)}）" for r in briefs)


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


# ---------------------------------------------------------------- この輪で渡した証拠の種類と回の控え（今の <名>.delivered.json）
def delivered(ledger) -> dict:
    """控えのファイル ledger の {kinds, iterations}（無い・読めなければ空）"""
    done = jsonfile.read_or(pathlib.Path(ledger))
    return done if isinstance(done, dict) else {}


def iteration_next(ledger) -> int:
    """この輪で次に組む回の番号（控え ledger の iterations の数 + 1）"""
    return len(delivered(ledger).get("iterations") or []) + 1


def kinds_for(ledger, values: dict, repo, start=()) -> dict:
    """今の組み立てで載せる証拠の種類（kinds_now に、控え ledger の前に渡した種類と、控えの前の段が渡した種類 start を足す。輪の中で減らさない。
    start は TDD の輪の最初の周が振り分けの段の渡した種類を受ける口で、注文の型ごとの欄 orders.tdd の kinds）"""
    return kinds_now(values, repo, [*start, *(delivered(ledger).get("kinds") or ())])


def remember(ledger, kinds, iteration: int) -> None:
    """渡した後の種類と回を控え ledger に積む（今の write_prompt の後半）"""
    done = delivered(ledger)
    jsonfile.write(pathlib.Path(ledger), {"kinds": sorted(kinds), "iterations": [*(done.get("iterations") or []), iteration]})


# ---------------------------------------------------------------- 修正役の値
def lib_section(b, repo, values: dict, shared=None) -> str:
    """ライブラリの文書の節（libdocs.section。控えは置き場 b、run をまたぐ控えは根 shared）: 直す義務の単位のファイルと今の差分の
    ファイルが使うライブラリ。見出しと頭の文は md が持つ（src/prompts.py が切る）"""
    try:
        keys = set(json.loads(values.get("open_units") or "[]"))
    except (ValueError, TypeError):
        keys = None
    files, why = libdocs.unit_files(repo, values.get("judgment_file") or "", keys) if repo is not None else ([], "")
    text = libdocs.section(b, repo, files + (changed_paths(repo, values.get("base_rev")) if repo is not None else []),
                           shared=shared)
    return text + (f"\n- 単位のファイルの引き: {why}" if why else "")


def ask_config(b, repo, values: dict, pass_: str, *, items=None) -> str:
    """範囲の相談の控えを置き場 b に書き（consult.write_config。事前の確かめのコマンドが読み、受け付けの拒否の文が相談を言うかを
    決める）、控えのパスを返す（修正役の段落 ask と下請けの段落 ask の文は md。コマンドの字は src/prompts.py が組む）。
    入力 plan_session（相談の相手の役の名）が空・承認済みの修正案の項目 items（planmarks.approved_items の形の値か口）が引けない run は
    書かずに ""。values の tdd_state は TDD の輪の状態のファイル（空は輪の無い run）"""
    node = (values.get("plan_session") or "").strip()
    if not node or repo is None:
        return ""
    got = _items(items)
    if not got:
        return ""
    doc = {"board": str(b), "repo": str(repo), "pass": pass_,
           "base_rev": values.get("base_rev") or "",
           "tdd_state": values.get("tdd_state") or "",
           "items": consult.items_doc(got)}
    return str(consult.write_config(b, doc))


def resume_values(got: dict) -> dict:
    """範囲の相談の答えの後の周の値（consult.take の返り got）: 答えのファイル・残りの相談の周・はみ出しの答えか（答えの行の origin が
    accept。今の resume の節の選び）"""
    return {"answer_file": str(got["answer_file"]), "left": str(got["left"]), "overflow": got.get("origin") == consult.ORIGIN_ACCEPT}
