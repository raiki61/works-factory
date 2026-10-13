"""修正役の指示書の組み立て（blk-fix。裁定 R65）。AI を通さず、機械が決まりの正本と道ごとの決まりと run の値を繋いで書く。
節に切る・穴を埋める・形を描く口は lib/rulebook（ほかのブロックの書く役も同じ正本から組む）。
決まりの文の本体の置き場（RULES_DIR・SHARED・PROMPT_DIRS）は、呼び手の script が import の後に工程の決まりのフォルダへ置き替える。

置き場。どれも `<!-- セクション <id> -->` の行で節に切り、組むときに節を選ぶ（印の行は指示書に入れない）:
- 修正の決まりの正本（SHARED = rulebook.CANON。決まりのフォルダの common.md）: core-fix（直し方）・core-keep（守ること）は
  本線の核でいつも載せる。evidence・evidence-<種類>（テストで赤→緑を示せない直しの証拠。決定 C8）は、単位のファイルと差分に在る
  変更の種類（KINDS）の物だけを載せる
- rules/brief.md: 要求の正本の決まり（節 brief-canon）。頭に並んだ brief（承認済みの修正案の項目を planbrief が切り出して凍結した物）を
  要求の正本とし、判定のファイルを背景に下げる。修正役と TDD の輪の役にだけ、頭の節の次にいつも載せる（裁定役と手直しの役には
  載せない。頭に brief の節が無い run では、節の 6 で判定のファイルが正本のまま）
- rules/direct.md: 直す役（節 fix）の道。fix-head（役・読む物。run の値の穴 <<名>>）・fix-keep・fix-reply（返答の欄の書き方）。
  受け付けが見つけたはみ出しを相談に回した周の続き（fix-overflow-queued）と、その答えの後の続き（fix-overflow-resume）も、この道の節
  （指示書は組み直さず、前に読んだ指示書を名指して前の返答と同じ JSON を返させる）
- rules/tdd.md: TDD の輪の役（節 tdd）の道。tdd-head・tdd-remap（この輪での読み替え）・tdd-phase-<段>（今の段の約束だけ）・tdd-end
- rules/ruler.md・principles.md: 食い違いの申し出の裁定役（節 rule。読むだけ）の道と、持ち主の決まり（裁定の拠り所）。
  修正役と TDD の輪の役の両方に、正本の core-conflict（緑にするために曲げず、食い違いとして返す）をいつも載せる

支度の節は毎回、決まりを全部載せた指示書 <名>.md（役の節の 1 行が Read させるパス）を書く（write_prompt）。どの節を載せたか・
なぜかは 1 行目（HEADER）に機械の事実として書く（役ごとの量を前後で測る）。この輪で渡した証拠の種類と回の番号は
<名>.delivered.json に積む（輪の中で証拠の種類を減らさない・次の回の番号を数える）。

型の穴は <<名>>。run の値は `値`（空は EMPTY）。埋めた値はもう一度読まない（1 回の置き換え）。穴に値が無い時は Unfilled。
同じ入力からはバイト単位で同じ指示書になる（時刻を書かない）。
指示書の題の次（拒否の理由の後）に始めの記録の値の 2 行（start_lines: 人の方針の文書と依頼の文のファイル。無ければ無いと 1 行ずつ）を置く。
言語の 1 行は呼び手が組んで引数 lang で渡す（元は盤面の inputs から rolekit.lang_line で取った）。

- prep: 節 fix-prep・fix-ruled-prep の中身（置き場 b に指示書を書く）。tddloop.prep は tdd_render を使う。
  指示書の頭（題の次）に、直す義務の単位の brief（planbrief.cut。承認済みの修正案の項目を凍結した物）を名指す節を置く。
  brief の控えが壊れていれば理由の ValueError（brief_halt。brief の無い指示書として続けない。止めるのは呼び手）
- ruler_prompt: 裁定役の指示書（ruling.prep が書く）
- head_file: 段（PASSES）ごとの段の頭の木の控えのファイルの名（HEAD_FILES。fixboard.fixer_head と fix-prep・fix-ruled-prep が引く）
- 同じ run に修正役を 2 度起こす段（依頼 226 の 2 回目の修正の段）の指示書（と隣の .delivered.json）・裁定の後の尾・裁定の文・
  申し出の回の控えは、名を変えずに置き場（呼び手が渡す b。fix/fix/ と fix/refix/）で 1 回目の物と分かれる。2 回目の段は自分の
  数えから始まり、3 回の諦めを回ごとに数える
"""
import json
import pathlib
import posixpath
import re
import sys

sys.dont_write_bytecode = True

import conflict  # noqa: E402
import fixboard  # noqa: E402  （直す義務 fix_duty。元 conflict.fix_duty の値で受ける形）
from leftovers import Unreadable, git_names  # noqa: E402
import consult  # noqa: E402  （同じブロックの lib。範囲の相談の控え・置き場・答え）
import jsonfile  # noqa: E402
import libdocs  # noqa: E402
import oneline  # noqa: E402
import planbrief  # noqa: E402  （同じブロックの lib。承認済みの修正案の項目ごとの brief の凍結）
import planmarks  # noqa: E402  （項目の範囲: allowed_paths と受け入れのテストのファイル。並べる項目の分け方）
import recount  # noqa: E402
import rulebook  # noqa: E402
import seat as seatkit  # noqa: E402  （借りたスキルの座。引数の名 seat と分ける）
from rulebook import EMPTY, MARK, Unfilled, fill, join, render, shared  # noqa: E402,F401
import promptsection  # noqa: E402

RULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "rules"
SHARED = rulebook.CANON
DIRECT, TDD = "direct.md", "tdd.md"
BRIEF = "brief.md"   # brief の決まり（要求の正本と背景）（修正役と TDD の輪の役にだけ載せる）
BRIEF_WHY = "（要求の正本と背景）"
RULER, PRINCIPLES = "ruler.md", "principles.md"   # 裁定役の道と、持ち主の決まり（裁定の拠り所）
FIX_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file", "summary_file")
TDD_VALUES = ("judgment_file", "open_units", "plan_file", "policy_path", "notes_file")
RULER_VALUES = ("conflicts_file", "ids", "judgment_file", "request_file", "policy_path")
CONFLICT_WHY = "（食い違いの申し出。緑にするために曲げない）"
PASSES = ("first", "ruled")   # 修正役の 1 回目と、裁定の後の 2 回目（印 continue=fix の会話の続き）
HEAD_FILES = dict(zip(PASSES, (fixboard.FIX_HEAD_FILE, fixboard.RULED_HEAD_FILE), strict=True))   # 段 → 段の頭の木の控え
ANSWER_NODES = dict(zip(PASSES, ("consult-answer", "ruled-consult-answer"), strict=True))   # 段 → 範囲の相談に答える役の節
RULED_TAIL = "-ruled.md"      # 2 回目の指示書の名の尾（1 回目の <名>.md の隣。輪の控えを分ける）
RULINGS_LINE = ("食い違いの申し出への裁定を書いたファイル {path} を、先に Read で全部読め。裁定に従って直し、返答を丸ごと出し直せ"
                "（裁定の文そのものはここに貼らない）")
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
DELIVERED = ".delivered.json"   # この輪で渡した証拠の種類と回の番号の控え（<名>.md の隣）
G1_IMPL, G1_REVIEW = "g1-impl-{n}.md", "g1-review-{n}.md"   # 修正役が起こす下請けのファイル（置き場のファイル。n は項目の番号）
G1_PATCH_FILE = "g1-{n}.patch"   # 下請けの審査役の差分のファイル（置き場のファイル。修正役が seat.G1_PATCH で書く）
G1_REST = "修正案のどの項目にも無い直す義務の単位 {keys}（判定のファイルが要求の正本）"   # 下請けの残りの項目の実装役の型の題
SEAT_BRIEFS = "seat-briefs.md"   # 修正役の座の型の [BRIEF_FILE]（置き場のファイル。直す義務の単位の brief を名指す節）
BRIEF_BROKEN = (f"修正案の brief の控え（置き場の {planbrief.LEDGER}）か欄の控え（置き場の {planbrief.planmarks.FIELDS_FILE}）が壊れているか"
                "凍結の後に書き換えられ、承認した要求の正本が"
                "引けない——brief の無い指示書で役を起こさずに止める")
FACTCHECKS = pathlib.Path(__file__).resolve().parent / "factchecks.py"   # 事前の確かめのコマンド（import しない: factchecks → tddloop → fixrules の輪）
ASK_DRAFT = "draft-reply.json"   # 修正役が事前の確かめに渡す返答の下書き（相談の置き場。作業ツリーの外）
RIPPLE_LINE = ("波及の一覧: {path}（承認済みの修正案の項目が変える名の呼び出し元と試験。範囲に入っていない当たりを名指す。その当たりを"
               "直しで触る必要が出たら、書く前に上の範囲の相談で聞け）")
RESUME_FILE = "consult-{pass_}-{turn}-resume.md"   # 範囲の相談の答えの後の続きの指示書（置き場のファイル）
OVERFLOW_QUEUED_FILE = "consult-{pass_}-overflow-queued.md"   # 受け付けがはみ出しを相談に積んだ周の続きの指示書（同じ）
ASK_WHY = "範囲の相談の控えが在る（相談の相手の会話の印の名 plan_session と承認済みの修正案の項目が在る run）"
PROMPT_NAME = f"prompt-{recount.FIX_NODE}.md"   # 修正役の指示書（置き場のファイル。元 rolekit.prompt_name(recount.FIX_NODE)）
# 始めの記録の値の 2 行（start_lines。計画 fix の「指示書に始めの記録の値を差し込む所」。欄が無い・空でも黙って抜かない）
POLICY_LINE = "人の方針の文書: `{path}`（先に全部読め）"
NO_POLICY_LINE = "人の方針の文書は無い"
REQUEST_LINE = "依頼の文のファイル: `{path}`（先に全部読め）"
NO_REQUEST_LINE = "依頼の文のファイルは無い"
_sha = rulebook.sha
_pick = rulebook.pick


# ---------------------------------------------------------------- 節
def sections(name) -> dict:
    """rules/<name> の節 {id: 本文}。SHARED は .shared/core の正本（rulebook.sections）"""
    return rulebook.sections(SHARED if name == SHARED else RULES_DIR / name)


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


# ---------------------------------------------------------------- 組み立て（純粋）
ALWAYS = "いつも"


def _evidence(common: dict, kinds: dict) -> list:
    if not kinds:
        return []
    return [("evidence", common["evidence"], "変更の種類: " + "・".join(k for k in KINDS if k in kinds))] + \
           [(f"evidence-{k}", common[f"evidence-{k}"], kinds[k]) for k in KINDS if k in kinds]


def _all_kinds() -> dict:
    return {k: "種類を選ばない組み立て（全部）" for k in KINDS}


def start_lines(values: dict) -> list:
    """始めの記録の値の 2 行: 人の方針の文書（values の policy_path）と依頼の文のファイル（values の request_file）。欄が無い・空なら
    NO_POLICY_LINE・NO_REQUEST_LINE（計画 fix の決めた直し。元の指示書は空の方針を fix-head の穴に（空）と埋めるだけだった）"""
    policy = str((values or {}).get("policy_path") or "").strip()
    request = str((values or {}).get("request_file") or "").strip()
    return [POLICY_LINE.format(path=policy) if policy else NO_POLICY_LINE,
            REQUEST_LINE.format(path=request) if request else NO_REQUEST_LINE]


def _seat(seat: str) -> list:
    """座の節（呼び手が渡す座の文。空なら載せない）"""
    return [("seat", seat, ALWAYS + "（座）")] if seat else []


def fix_parts(values: dict, kinds: dict | None = None, libdocs: str = "", seat: str = "", ask: str = "") -> list:
    """直す役の決まりの節 [(id, 本文, 理由)]（順は指示書の順）。libdocs はライブラリの文書の節（libdocs.section。空なら載せない）。
    seat は座の文（呼び手が渡す。空なら載せない）で、返答の欄の直前に置く。
    ask は範囲の相談と事前の確かめの節（ask_text。空なら載せない）で、守ることの後に置く"""
    c, d = sections(SHARED), sections(DIRECT)
    kinds = _all_kinds() if kinds is None else kinds
    return [("fix-head", fill(d["fix-head"], _pick(values, FIX_VALUES)), ALWAYS + "（役・読む物・run の値）"),
            ("brief-canon", sections(BRIEF)["brief-canon"], ALWAYS + BRIEF_WHY),
            ("core-fix", c["core-fix"], ALWAYS + "（元の graphloops の核）"), *_evidence(c, kinds),
            ("core-conflict", c["core-conflict"], ALWAYS + CONFLICT_WHY), ("core-keep", c["core-keep"], ALWAYS + "（元の graphloops の核）"),
            ("fix-keep", d["fix-keep"], ALWAYS + "（直す役）"),
            *([("ask", ask, ASK_WHY)] if ask else []),
            *([("libdocs", libdocs, "機械が引いた（手元の版・公式。見つけた数と取れた数はセクションの頭）")] if libdocs else []),
            *_seat(seat),
            ("fix-reply", d["fix-reply"], ALWAYS + "（返答の欄）")]


def tdd_parts(values: dict, kinds: dict | None = None, seat: str = "") -> list:
    """TDD の輪の役の決まりの節（段によらない物）。seat は借りたスキルの座（空なら載せない）で、この輪での読み替えの後に置く"""
    c, t = sections(SHARED), sections(TDD)
    kinds = _all_kinds() if kinds is None else kinds
    return [("tdd-head", fill(t["tdd-head"], _pick(values, TDD_VALUES)), ALWAYS + "（役・読む物・run の値）"),
            ("brief-canon", sections(BRIEF)["brief-canon"], ALWAYS + BRIEF_WHY),
            ("core-fix", c["core-fix"], ALWAYS + "（元の graphloops の核）"), *_evidence(c, kinds),
            ("core-conflict", c["core-conflict"], ALWAYS + CONFLICT_WHY), ("core-keep", c["core-keep"], ALWAYS + "（元の graphloops の核）"),
            ("tdd-remap", t["tdd-remap"], ALWAYS + "（このループでの読み替え）"), *_seat(seat)]


def tdd_phase_rules(phase: str) -> str:
    """今の段の約束（その段の行と、どの段にも当たる行だけ）"""
    if phase not in PHASES:
        raise Unfilled(f"段 {phase!r} は {PHASES} のどれでもない")
    t = sections(TDD)
    return join([t["tdd-phase"], t[f"tdd-phase-{phase}"], t["tdd-phase-all"]])


def ruler_parts(values: dict) -> list:
    """裁定役の決まりの節（役・読む物・run の値 → 持ち主の決まり → 返す JSON）"""
    r, pr = sections(RULER), sections(PRINCIPLES)
    return [("ruler-head", fill(r["ruler-head"], _pick(values, RULER_VALUES)), ALWAYS + "（役・読む物・run の値）"),
            ("principles", pr["principles"], ALWAYS + "（持ち主の決まり）"), ("ruler-reply", r["ruler-reply"], ALWAYS + "（返答の欄）")]


def ruler_prompt(values: dict, *, reject_file: str = "", iteration: int = 1, lang: str = "") -> str:
    """裁定役の指示書（純粋。いつも全部——輪は 3 回までで、出し直しは同じ会話）。lang は言語の 1 行（呼び手が組む）。
    頭に始めの記録の値の 2 行（start_lines）"""
    return render("rule", iteration, ruler_parts(values), reject_file=reject_file, before=start_lines(values),
                  lang=lang)["text"]


TDD_REJECT_HEAD = promptsection.Section("## 前の回の返答を機械が拒んだ理由（直して、この段の返答を丸ごと出し直せ）\n\n", source="fn:fixrules.tdd_render")


def tdd_render(values, phase, phase_text, *, title, reason="", kinds=None, iteration=1, lang="", brief="", seat="") -> dict:
    """TDD の段の指示書の {text, head}（rulebook.render）。並び: 題 → [brief の節（planbrief.head_text）] → [拒んだ理由] → 始めの記録の値の
    2 行（start_lines）→ 決まり → 今の段の約束 → 今の段（tddloop が書く）→ 結び → [言語の 1 行（呼び手が組む）]"""
    before = [title, *([brief] if brief else [])]
    if reason:
        before.append(TDD_REJECT_HEAD + reason.rstrip("\n"))
    before += start_lines(values)
    after = [tdd_phase_rules(phase), phase_text.rstrip("\n"), sections(TDD)["tdd-end"]]
    return render("tdd", iteration, tdd_parts(values, kinds, seat), before=before, after=after, lang=lang)


# ---------------------------------------------------------------- 指示書を書く（支度の節）
def beside(prompt: pathlib.Path, tail: str) -> pathlib.Path:
    """<名>.md の隣の <名><tail>"""
    return prompt.with_name(prompt.name[:-len(".md")] + tail if prompt.name.endswith(".md") else prompt.name + tail)


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


def iteration_next(prompt: pathlib.Path) -> int:
    """この輪で次に組む回の番号（<名>.delivered.json の iterations の数 + 1）"""
    return len((jsonfile.read_or(beside(prompt, DELIVERED)) or {}).get("iterations") or []) + 1


def write_prompt(prompt: pathlib.Path, repo, values: dict, build, iteration: int) -> None:
    """指示書 prompt を書く。build(kinds) -> rulebook.render の返り。この輪で前に渡した証拠の種類（<名>.delivered.json）を
    kinds_now に足して組み、渡した後の種類と回を積む。repo が None なら差分を見ない"""
    ledger = beside(prompt, DELIVERED)
    done = jsonfile.read_or(ledger)
    done = done if isinstance(done, dict) else {}
    kinds = kinds_now(values, repo, done.get("kinds") or ())
    prompt.write_text(build(kinds)["text"], encoding="utf-8")
    jsonfile.write(ledger, {"kinds": sorted(kinds), "iterations": [*(done.get("iterations") or []), iteration]})


# ---------------------------------------------------------------- 節 fix-prep
def lib_section(b, repo, values: dict, shared=None) -> str:
    """ライブラリの文書の節（libdocs.section。控えは置き場 b、run をまたぐ控えは根 shared）: 直す義務の単位のファイルと今の差分の
    ファイルが使うライブラリ"""
    try:
        keys = set(json.loads(values.get("open_units") or "[]"))
    except (ValueError, TypeError):
        keys = None
    files, why = libdocs.unit_files(repo, values.get("judgment_file") or "", keys) if repo is not None else ([], "")
    text = libdocs.section(b, repo, files + (changed_paths(repo, values.get("base_rev")) if repo is not None else []),
                           shared=shared)
    return text + (f"\n- 単位のファイルの引き: {why}" if why else "")


def prompt_path(b) -> pathlib.Path:
    """修正役の指示書（置き場 b の PROMPT_NAME）"""
    return pathlib.Path(b) / PROMPT_NAME


def owed_values(b, values: dict, *, owed, withheld_by=None, returned=()) -> dict:
    """指示書に埋める値の open_units を、受け付けと同じ fixboard.fix_duty の owed に替えた物（判定の出口の is_open の並びを
    保ち、関所で答えて直す義務に戻った単位を後ろに足す）。出口の値が読めなければ owed の並べ替えだけ。
    b は置き場、owed は写しの規則の直す義務の単位（元は盤面の _owed_units）、withheld_by・returned は問いの台帳の値（元は
    gatemarks の盤面の読み）。どれも呼び手が渡す"""
    try:
        keys = json.loads(values.get("open_units") or "[]")
    except (ValueError, TypeError):
        keys = []
    owed, _ = fixboard.fix_duty(b, owed, withheld_by=withheld_by, returned=returned)
    seen = [k for k in keys if k in owed] if isinstance(keys, list) else []
    return {**values, "open_units": json.dumps(seen + sorted(owed - set(seen)), ensure_ascii=False)}


def brief_halt(err) -> str:
    """brief の控えが壊れた（planbrief.LedgerBroken の err）ことを名指す理由の 1 行（止めるのは呼び手。元は盤面を止めた）"""
    return f"{BRIEF_BROKEN}: {oneline.one_line(err)}"


def briefs_or_halt(b, **sources) -> list:
    """置き場 b の brief（planbrief.cut。修正案の欄の控えが無い run は []）。sources は planbrief.cut の材料（plan・judgment・
    purpose・structure_dir・round_）。控えが壊れていれば理由の ValueError（黙って brief の無い指示書にしない）"""
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


def ask_text(config, python: str) -> str:
    """範囲の相談と事前の確かめの節（rules/direct.md の節 fix-ask）を、控え config と実行ファイル python で埋めた文"""
    place = pathlib.Path(config).parent
    return fill(sections(DIRECT)["fix-ask"], {
        "check_cmd": f"{python} {FACTCHECKS} {config}",
        "draft": str(place / ASK_DRAFT),
        "budget": str(consult.BUDGET)})


def ask_sub_text(config, python: str) -> str:
    """下請け（g1・g3 の実装役のファイル）の範囲の外の決まり（rules/direct.md の節 fix-ask-sub）。下請けは自分で相談せず、
    まとめ役に頼みを報告する（相談は修正役の返答の欄 consult でだけ起きる）"""
    return fill(sections(DIRECT)["fix-ask-sub"], {"check_cmd": f"{python} {FACTCHECKS} {config}"})


def ask_config(b, repo, values: dict, pass_: str, *, items=None) -> tuple:
    """範囲の相談の控えを置き場 b に書き（consult.write_config。事前の確かめのコマンドが読み、受け付けの拒否の文が相談を言うかを
    決める）、(修正役の節の文（ask_text）, 下請けの節の文（ask_sub_text）) を返す。入力 plan_session（相談の相手の会話の印の名）が
    空・承認済みの修正案の項目 items（planmarks.approved_items の形の値か口。元は盤面から読んだ）が引けない run は書かずに ("", "")。
    実行ファイルはこの節の python。values の tdd_state は TDD の輪の状態のファイル（空は輪の無い run）。values の ripple_file（波及の
    一覧のパス）が在れば修正役の節の終わりに RIPPLE_LINE で名指す"""
    node = (values.get("plan_session") or "").strip()
    if not node or repo is None:
        return "", ""
    got = _items(items)
    if not got:
        return "", ""
    doc = {"board": str(b), "repo": str(repo), "pass": pass_,
           "base_rev": values.get("base_rev") or "",
           "tdd_state": values.get("tdd_state") or "",
           "items": consult.items_doc(got)}
    path = consult.write_config(b, doc)
    ripple = (values.get("ripple_file") or "").strip()
    return (ask_text(path, sys.executable) + (f"\n\n{RIPPLE_LINE.format(path=ripple)}" if ripple else ""),
            ask_sub_text(path, sys.executable))


def resume(b, path: pathlib.Path, got: dict, pass_: str, lang: str = "") -> pathlib.Path:
    """範囲の相談の答えの後の続きの指示書（rules/direct.md の節 fix-consult-resume。答えのファイル・前の指示書 path・残りの枠）を
    置き場 b の RESUME_FILE に書いてそのパスを返す。決まりは貼り直さない（前の指示書を名指す）。言語の 1 行 lang（呼び手が組む）だけ足す"""
    # 受け付けが見つけたはみ出しの相談（答えの行の origin が accept）の答えには、はみ出し用の続き（戻すのは機械）を選ぶ
    node = "fix-overflow-resume" if got.get("origin") == consult.ORIGIN_ACCEPT else "fix-consult-resume"
    text = fill(sections(DIRECT)[node], {"answer_file": got["answer_file"], "prompt_file": str(path), "left": str(got["left"])})
    out = pathlib.Path(b) / RESUME_FILE.format(pass_=pass_, turn=got["turn"])
    out.write_text(text.rstrip("\n") + "\n" + (f"\n{lang}\n" if lang else ""), encoding="utf-8")
    return out


def overflow_queued(b, path: pathlib.Path, pass_: str, lang: str = "") -> pathlib.Path:
    """受け付けがはみ出しを相談に積んだ周の続きの指示書（rules/direct.md の節 fix-overflow-queued。前の指示書 path）を置き場 b に
    書いてそのパスを返す。指示書は組み直さない（作業ツリーを変えずに前の返答と同じ JSON を返す）"""
    text = fill(sections(DIRECT)["fix-overflow-queued"], {"prompt_file": str(path)})
    out = pathlib.Path(b) / OVERFLOW_QUEUED_FILE.format(pass_=pass_)
    out.write_text(text.rstrip("\n") + "\n" + (f"\n{lang}\n" if lang else ""), encoding="utf-8")
    return out


def implementer_values(b, values: dict, repo, owed: list[str], briefs: list) -> dict[str, str]:
    """修正役の座（節 implementer の型）の 5 つの穴の値。owed は今直す単位の key、briefs は凍結した brief（briefs_or_halt）。
    直す義務の単位の brief を名指す節（planbrief.head_text）を置き場 b の SEAT_BRIEFS に書いて [BRIEF_FILE] にする（brief の無い
    run は判定のファイル）。[directory] は repo。元 works/blk-fix/lib/fixrules.py:421"""
    mine = planbrief.for_units(briefs, owed)
    head = planbrief.head_text(mine, owed)
    brief_file = values.get("judgment_file") or ""
    if head:
        path = pathlib.Path(b) / SEAT_BRIEFS
        path.write_text(head + "\n", encoding="utf-8")
        brief_file = str(path)
    items = "、".join(str(r["item"]) for r in mine)
    summary = values.get("summary_file") or ""
    return {"[task name]": f"直す義務の単位 {len(owed)} 件" + (f"（修正案の項目 {items}）" if items else ""),
            "[BRIEF_FILE]": brief_file,
            "[Scene-setting: where this fits, dependencies, architectural context]":
                seatkit.SCENE + (f"。ループの要約のファイル: {summary}" if summary else ""),
            "[directory]": "" if repo is None else str(repo),
            "[REPORT_FILE]": seatkit.NO_REPORT_FILE}


def g1_values(b, values: dict, repo, owed: list[str], briefs: list, ask: str = "") -> list[dict]:
    """修正役が起こす下請けのファイルを、直す義務の単位の brief の項目ごとに置き場 b に 2 つ書き、項目の順の
    [{item, impl_file, review_file, base, patch}] を返す（seat.g1_section が並べる）。どの項目にも無い直す義務の単位（brief の無い
    run は全部）は、判定のファイルを [BRIEF_FILE] にした 1 単位 1 項目（番号は修正案の項目の後。題は G1_REST）。
    実装役は節 implementer の型（[BRIEF_FILE] はその項目の brief、[task name] はその項目の直す義務の単位、[REPORT_FILE] は
    seat.G1_IMPL_REPORT、ほかは implementer_values と同じ）、審査役は節 task-review の型（review_text。[BASE_SHA] は values の
    修正前の版 base_rev、[DIFF_FILE] は置き場の G1_PATCH_FILE）。ask（下請けの範囲の外の決まり。ask_sub_text）が空でなければ実装役の
    ファイルの終わりに足す。写しが固定と違う・穴が埋まらなければ ValueError。元 works/blk-fix/lib/fixrules.py:523"""
    common = implementer_values(b, values, repo, owed, briefs)
    mine = planbrief.for_units(briefs, owed)
    items = [(r["item"], r["file"], _g1_task(r, owed)) for r in mine]
    covered = {k for r in mine for k in r.get("unit_keys") or []}
    rest = [k for k in owed if k not in covered]
    n = max((r["item"] for r in briefs), default=0) + 1
    items += [(n + i, values.get("judgment_file") or "", G1_REST.format(keys=k)) for i, k in enumerate(rest)]
    base = fixboard.base_rev(None, values.get("base_rev") or "")
    rows = []
    for n, brief, task in items:
        impl, review = pathlib.Path(b) / G1_IMPL.format(n=n), pathlib.Path(b) / G1_REVIEW.format(n=n)
        patch = str(pathlib.Path(b) / G1_PATCH_FILE.format(n=n))
        impl.write_text(seatkit.g1_prompt("implementer", {**common, "[task name]": task, "[BRIEF_FILE]": brief,
                                                           "[REPORT_FILE]": seatkit.G1_IMPL_REPORT})
                        + (f"\n\n{ask}\n" if ask else ""), encoding="utf-8")
        review.write_text(review_text(brief, values, base, patch), encoding="utf-8")
        rows.append({"item": n, "impl_file": str(impl), "review_file": str(review), "base": base, "patch": patch})
    return rows


def review_text(brief: str, values: dict, base: str, patch: str) -> str:
    """審査役の下請けのファイルの中身（節 task-review の型。[BASE_SHA] は base、[DIFF_FILE] は patch）"""
    return seatkit.g1_prompt("task-review", {
        "[BRIEF_FILE]": brief, "[GLOBAL_CONSTRAINTS]": values.get("policy_path") or seatkit.NONE,
        "[REPORT_FILE]": seatkit.G1_REPORT, "[BASE_SHA]": base, "[HEAD_SHA]": seatkit.G1_HEAD_SHA, "[DIFF_FILE]": patch})


def _g1_task(brief: dict, owed: list[str]) -> str:
    """下請けの実装役の型の [task name]: 修正案の項目の番号と、その項目のうち今直す単位（ほかの単位は『今は直すな』）"""
    return f"修正案の項目 {brief['item']}（直す義務の単位 {planbrief.unit_note(brief.get('unit_keys'), owed)}）"


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


def prep(b, repo, values: dict, pass_: str = PASSES[0], *, owed, withheld_by=None, returned=(), items=None, sources=None,
         reject_file: str = "", lang: str = "", green=frozenset(), shared=None) -> dict:
    """節 fix-prep（pass_ first）と fix-ruled-prep（pass_ ruled）: 置き場 b に指示書を書き、{prompt_file, iteration}（iteration は
    この輪の何回目か。受け付けが 3 回目の拒否で done を立てる。R50）を返す。
    reject_file はこの輪の拒否の理由の全部のファイル（fixboard.rejects_file。同じ試行の出し直し。呼び手が渡す。見出しの次の 1 行で名指す。R44）。
    ruled は指示書を <名>-ruled.md に分け（輪の回を別に数える）、1 回目は裁定の文のファイル（conflict.RULINGS_FILE）を見出しの
    次の 1 行で名指す（裁定の文は貼らない。R44）。
    題の次（ruled の 1 回目は裁定の文のファイルの行の後）に、直す義務の単位の brief を名指す節（planbrief.head_text。義務から外れた
    単位には「今は直すな」）を置く。brief は sources（planbrief.cut の材料）で置き場に凍結する。控えが壊れていれば理由の ValueError
    （briefs_or_halt。指示書を書かない）。
    範囲の相談の答えがまだ渡っていない周（consult.take）は、指示書を組み直さずに答えのファイルを名指す続きの指示書（resume）だけを
    書き、iteration は前の回のまま（相談の周は受け付けの回に数えない）。受け付けがはみ出しを相談に積んだ周（consult.queued）も
    組み直さず、続きの指示書（overflow_queued）だけを書く。
    owed・withheld_by・returned は直す義務（owed_values → fixboard.fix_duty）、items は承認済みの項目（ask_config）、lang は言語の
    1 行（呼び手が組む）。green は TDD の輪が緑にした単位（呼び手が tddloop.green_units で引く）。shared はライブラリの文書の
    run をまたぐ控えの根（lib_section。None なら使わない）。
    修正役が下請けを起こす単位（dispatched。輪が緑にした単位の外）が在れば、下請けを回す節（seat.g1_section。下請けのファイルは
    g1_values）を載せ、輪が全部を緑にした周は借りたスキルの座（seat.section。型の穴は implementer_values）を載せる。写しが固定と
    違う・穴が埋まらなければ ValueError のまま上げる（指示書を書かない）。
    元 works/blk-fix/lib/fixrules.py:681 の盤面の待ちの確かめ（b.rd の instance）・起こした印（mark_launched）・拒否のファイルの
    探し（script_io.last_reject）は外した（実行基盤の輪が持つ）"""
    if pass_ not in PASSES:
        raise Unfilled(f"pass {pass_!r} は {PASSES} のどれでもない")
    briefs = briefs_or_halt(b, **(sources or {}))   # 裁定の文を書くより前に凍結する
    name = PROMPT_NAME
    before = ()
    if pass_ == "ruled":
        name = name[:-len(".md")] + RULED_TAIL
    path = pathlib.Path(b) / name
    got = consult.take(b, pass_)
    if got is not None:   # 範囲の相談の答えの後の周: 答えのファイルを名指すだけ（受け付けの回は数え直さない）
        return {"prompt_file": str(resume(b, path, got, pass_, lang)), "iteration": max(1, iteration_next(path) - 1)}
    if consult.queued(b, pass_):   # 受け付けがはみ出しを相談に積んだ周: 指示書を組み直さず、前の返答と同じ JSON を返させる
        return {"prompt_file": str(overflow_queued(b, path, pass_, lang)), "iteration": max(1, iteration_next(path) - 1)}
    n = iteration_next(path)
    reject = reject_file
    if pass_ == "ruled" and n == 1:
        rulings = pathlib.Path(b) / conflict.RULINGS_FILE
        if not rulings.is_file():
            rulings = conflict.write_rulings(b)
        reject, before = "", (RULINGS_LINE.format(path=rulings),)
    values = owed_values(b, values, owed=owed, withheld_by=withheld_by, returned=returned)
    owed_keys = json.loads(values["open_units"])
    head = planbrief.head_text(planbrief.for_units(briefs, owed_keys), owed_keys)
    before = tuple(x for x in (*before, head) if x)   # ruled の裁定の文の行は見出しの次の 1 行のまま（R44）。brief はその後
    before += tuple(start_lines(values))
    ask, ask_sub = ask_config(b, repo, values, pass_, items=items)
    mark = "fix" if pass_ == PASSES[0] else "fix-ruled"
    subs = dispatched(owed_keys, green)
    seatkit.pinned()   # 写しの照合を、下請けのファイルの書き込みとライブラリの文書の引きより前に
    if subs:
        seat = seatkit.g1_section(g1_values(b, values, repo, subs, briefs, ask=ask_sub))
    else:
        seat = seatkit.section(mark, implementer_values(b, values, repo, owed_keys, briefs))
    docs = lib_section(b, repo, values, shared)

    def build(kinds):
        return render("fix", n, fix_parts(values, kinds, docs, seat, ask), reject_file=reject,
                      before=before, lang=lang)
    write_prompt(path, repo, values, build, n)
    return {"prompt_file": str(path), "iteration": n}
