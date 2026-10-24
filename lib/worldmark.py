"""世界の解の行の住処（考え world。地図 docs/concepts.md。計画 docs/plans/2026-10-09-world-solution.md の 5.3 節・5.7 節）。

世界の解の段のブロックが、依頼の行ごとに「問題の類・世の中の定石・依頼の解き方との比べ」を 1 行に書いた JSON Lines（WORLD_FILE）と、
線がその出口を盤面の根に写した控え（STATE_FILE）を読む口の 1 か所。判定・構造の目・修正案・事前審査・関所・報告はここから読み、
行の欄の名と語を自分で持たない。実行基盤を知らない関数だけを出す。行の形の約束はこの置き場の JSON Schema（world-row.schema.json。
port の宣言は jsonl(lib:world-row.schema.json)）の 1 つで、欄 FIELDS・語 VERDICTS・BASES・VERSUS_FIELDS はそこから引き、行の照らしは
形の照らし（engine.schema.validate_schema）で当てる。

行: {finding（依頼の行の番号。1 始まり）, where（その行の where の字のまま）, class_id（問題の類の id。対象の名を持たない）,
problem（問題の類の 1 文）, activity（作業の種類の名）, practice（定石）, sources（[{id, url, excerpt}]。照らして残った抜き書き）,
applies（この依頼にどう当たるか。空なら答えの要らない行）, not_applies, versus（{proposed（依頼の解き方）, verdict, challenge}）,
basis（web: 照らした抜き書きが 1 つ以上・knowledge: 抜き書きが残らず模型の知識だけ）}。
knowledge の行は、頭の節・関所の行に NOT_WEB と名指して並べる（答えと関所の決まりは web の行と同じに掛ける）。

控え: {status: ok|failed, reason, world_file, classes, dropped}（数は類・落とした抜き書き）。段の時間は持たない（流れの道具の
出来事から作れる値は控えに持ち直さない）。

- rows(path)・read(board_dir)・read_file(path): 行（読めない・形が違えば ValueError）と控え（無い・読めない・形が違えば None）
- write(board_dir, …)・stage_rows(board_dir): 控えを書く（線の境）・控えが指す行（段が行を出さなかった周を None で分ける＝関所の軸。
  盤面の根から読む判定の支度・修正案の頭・関所が使う。呼び手は None と [] の違いを `stage_rows(d) or []` の 1 式で書く）。
  read・write・stage_rows の name は控えのファイルの名（既定は判定の STATE_FILE。事前審査の盤面の写しは COPY_STATE）
- ref_problems(reply, board_dir): 判定の返答の先例の出どころ world:<類の id> が控えの指す行に無い誤りの文（判定の受け付けが拒む）
- need(rows)・challenges(rows): 修正案の受け付けに渡す答えの要る行の表（planmarks.Need。答えの仕組みは構造の目の汚れる
  行と同じ 1 つ。行は項目に場所で結ばず、どの項目も答えていない行だけを欠けにする）・類ごとの依頼の解き方との比べの文（事前審査の
  外れの訳に添える）
- needs(row)・answered(item)・unanswered(rows, items): 答えの要る行（applies が空でない）と、修正案の
  項目の欄 structure の答え {world: <類の id>, follows: true} か {world, deviation}
- world_ok(answer, row, request_file, means, cite_ok, repo): 関所の軸「世界の解か」（答えの要らない行・従う・依頼の外の出どころで訳の立つ外れ。
  依頼の出どころは依頼のファイルのパス（パス全体で照らす）・依頼の引用・依頼の解き方 means で、目的の文の出典 source_files は入れない。
  依頼が解き方を示していない行（verdict none）の外れは依頼の出どころにならない。
  web で確かめていない行（knowledge）は従う答えだけが揃い、外れは人に聞く——計画の 5.5 節「知識だけの定石に従うのは自明側、外れは人へ」）
- gate_line(row, answer): 関所の項目の行
行を役に見せる節と行ごとの答えを頼む文は block の md（integration.md 4.3-追加-1）、報告の節「世界の解」の行は world の src/report.py。

依頼の解き方（足し欄 means。計画の W6・5.3 節の 1）: 目的の役は目的の文に解き方を書かず、依頼が示した解き方（手段）を役の型の
足し欄 MEANS に分ける。欄の意味（型・読んだ後の使い方）と控えの名 MEANS_FILE をここが持つ。
目的の文の型は写しのまま。控えは世界の解の段の入力（言い直す役が依頼の解き方として見る）で、独立設計には渡さない（目的だけから設計する）。
- split_means(reply): （欄を外した返答の写し, 手段の並び）
- write_means(board_dir, means)・means_of(board_dir, name): 控えを置く（空なら置かない）・読む（無い・読めなければ []。name は写しの名）
- copy_means(src_file, board_dir): 控えのファイル（判定の外の読み手は判定の出力の欄 purpose_means のパス）を別の置き場に写しの名
  COPY_MEANS で写す（事前審査の置き場の関所が世界の解の外れの出どころを照らす）
"""
import json
import pathlib
import shutil
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE / "graphloops") not in sys.path:
    sys.path.append(str(_HERE / "graphloops"))   # 写しの engine（carry と同じ足し方）

from engine.schema import validate_schema  # noqa: E402

import cite   # 依頼の引用「…」の形と語（決め手の出どころの照らしの住処）
import jsonfile
import planmarks  # 修正案の欄 structure の答えの仕組み（答えの要る行の表 Need）

WORLD_FILE = "world.jsonl"
STATE_FILE = "world-state.json"
ROW_SCHEMA_FILE = "world-row.schema.json"   # 行の形（この置き場。port の宣言は jsonl(lib:world-row.schema.json)）
ROW_SCHEMA = json.loads((_HERE / ROW_SCHEMA_FILE).read_text(encoding="utf-8"))
FIELDS = tuple(ROW_SCHEMA["required"])
_VERSUS = ROW_SCHEMA["properties"]["versus"]
VERSUS_FIELDS = tuple(_VERSUS["required"])
VERDICTS = tuple(_VERSUS["properties"]["verdict"]["enum"])
SAME, DIFFERS, NONE = VERDICTS
BASES = tuple(ROW_SCHEMA["properties"]["basis"]["enum"])
WEB, KNOWLEDGE = BASES
NOT_WEB = "web で確かめていない"
ANSWER_KEY = "world"   # 修正案の項目の欄 structure の答えの行で類の id を持つ鍵
SOURCE_PREFIX = "world:"   # 判定の先例の出どころで世界の行を指す頭の字（world:<類の id>）。ANSWER_KEY とは別の約束
VERDICT_WORDS = {SAME: "定石と同じ", DIFFERS: "定石と違う", NONE: "依頼は解き方を示していない"}
STATES = ("ok", "failed")
MEANS = "means"
MEANS_FILE = "purpose-means.json"
# 判定の外の盤面（事前審査）が、受けた控えを自分の置き場に写す名（判定の置き場の名と分ける。workflows/AGENTS.md の E4）
COPY_STATE = f"judge-{STATE_FILE}"
COPY_MEANS = f"judge-{MEANS_FILE}"


# ---------------------------------------------------------------- 読む
def _row_problem(r) -> str:
    return " / ".join(validate_schema(r, ROW_SCHEMA)[:5])


def rows(path) -> list:
    if not path:
        raise ValueError("世界の解の行のファイルの名が空")
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"世界の解の行のファイルが読めない: {e}") from None
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        try:
            r = json.loads(line)
        except ValueError as e:
            raise ValueError(f"世界の解の行 {i} が JSON でない: {e}") from None
        bad = _row_problem(r)
        if bad:
            raise ValueError(f"世界の解の行 {i}: {bad}")
        out.append(r)
    return out


def read(board_dir, name: str = STATE_FILE) -> dict | None:
    return read_file(pathlib.Path(board_dir) / name)


def read_file(path) -> dict | None:
    """段の控えのファイル path（判定の外の読み手は判定の出力の欄 world_state のパス）。無い・読めない・形が違えば None"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) and doc.get("status") in STATES else None


def write(board_dir, *, status: str, reason: str, world_file: str, classes, dropped, name: str = STATE_FILE) -> pathlib.Path:
    """控えを盤面の根に書く（線の境が 1 回。書けなければ OSError。受ける側が理由にして返す）"""
    path = pathlib.Path(board_dir) / name
    doc = {"status": status, "reason": reason, "world_file": world_file, "classes": classes, "dropped": dropped}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def stage_rows(board_dir, name: str = STATE_FILE) -> list | None:
    """盤面の根の控え name が指す行。段が行を出した周（控えが ok。行の無い段は []）だけ並びで、控えが無い・落ちた・行が読めない周は
    None（関所の軸が今どおりの決まりに戻る目印。拒まない）"""
    st = read(board_dir, name)
    if st is None or st["status"] != "ok":
        return None
    try:
        return rows(st["world_file"]) if st.get("world_file") else []
    except ValueError:
        return None


def ref_problems(reply, board_dir) -> list:
    """判定の返答（reply）の先例 precedents の出どころ source の world:<類の id> が、盤面の根の控えが指す行の class_id に在るかの
    誤りの文の並び（通れば空）。段の行が無い周（控えが無い・落ちた・行が空）の world: は全部宙に浮いた参照として数える。
    world: の無い出どころは見ない"""
    got = reply.get("precedents") if isinstance(reply, dict) else None
    sources = [p.get("source") for p in got if isinstance(p, dict)] if isinstance(got, list) else []
    known = {r["class_id"] for r in stage_rows(board_dir) or []}
    return [p for s in sources for p in cite.ref_problem(s, SOURCE_PREFIX, known)]


# ---------------------------------------------------------------- 依頼の解き方（足し欄 means）


def _means_path(board_dir) -> pathlib.Path:
    return pathlib.Path(getattr(board_dir, "dir", board_dir)) / MEANS_FILE


def split_means(reply) -> tuple:
    """（欄を外した返答の写し, 手段の並び。欄が無ければ []）。dict でない返答はそのまま"""
    if not isinstance(reply, dict):
        return reply, []
    out, got = jsonfile.split(reply, (), (MEANS,))
    return out, [m for m in got.get(MEANS) or [] if isinstance(m, str) and m.strip()]


def write_means(board_dir, means) -> None:
    """手段の並びを盤面の根の控えに置く（空なら置かない）"""
    got = [m for m in means or [] if isinstance(m, str) and m.strip()]
    if got:
        jsonfile.dump(_means_path(board_dir), {MEANS: got})


def copy_means(src_file, board_dir) -> None:
    """目的の役が置いた控えのファイル src_file（None 可）を board_dir に写しの名 COPY_MEANS で写す（無ければ board_dir の前の写しを消す）"""
    dest = pathlib.Path(board_dir) / COPY_MEANS
    src = pathlib.Path(src_file) if src_file is not None else None
    if src is not None and src.is_file():
        shutil.copyfile(src, dest)
    else:
        dest.unlink(missing_ok=True)


def means_of(board_dir, name: str | None = None) -> list:
    doc = jsonfile.read_or(pathlib.Path(board_dir) / name if name else _means_path(board_dir))
    got = doc.get(MEANS) if isinstance(doc, dict) else None
    return [m for m in got if isinstance(m, str) and m.strip()] if isinstance(got, list) else []


# ---------------------------------------------------------------- 文
def _mark(r: dict) -> str:
    return f"（{NOT_WEB}）" if r.get("basis") != WEB else ""


def _versus(r: dict) -> str:
    v = r.get("versus") or {}
    word = VERDICT_WORDS.get(v.get("verdict"), str(v.get("verdict")))
    head = f"依頼の解き方「{v.get('proposed')}」は{word}" if v.get("proposed") else word
    return f"{head}——{v['challenge']}" if v.get("verdict") == DIFFERS and v.get("challenge") else head




# ---------------------------------------------------------------- 答え
def need(rows) -> planmarks.Need:
    """答えの要る行の表（planmarks.structure_gaps が受ける）。行は項目に場所で結ばない（of は空）。どの項目も答えていない行だけを
    欠け（missing）にする"""
    got = [r for r in rows or [] if needs(r)]
    return planmarks.Need(ANSWER_KEY, "世界の解の行", {r["class_id"]: r["practice"] for r in got}, "定石",
                          "答えの要る世界の解の行の類でない", lambda item: [],
                          lambda items: unanswered(got, items))


def challenges(rows) -> dict:
    """{類の id: 依頼の解き方との比べの文}（事前審査の外れの訳に添える）"""
    return {r["class_id"]: _versus(r) for r in rows or [] if isinstance(r, dict) and r.get("class_id")}


def needs(row) -> bool:
    return isinstance(row, dict) and isinstance(row.get("applies"), str) and bool(row["applies"].strip())


def answered(item) -> list:
    rows_ = item.get("structure") if isinstance(item, dict) and isinstance(item.get("structure"), list) else []
    return [a[ANSWER_KEY] for a in rows_ if isinstance(a, dict) and isinstance(a.get(ANSWER_KEY), str)]


def unanswered(rows, items) -> list:
    done = {cid for it in items or [] for cid in answered(it)}
    out = []
    for r in rows or []:
        if needs(r) and r["class_id"] not in done and r["class_id"] not in out:
            out.append(r["class_id"])
    return out


def _names_path(text: str, path: str, repo) -> bool:
    """文がパス path をパス全体（と :行）で名指すか（別のファイルの名の一部として在るだけでは名指さない）。書き方の違い（./・..・
    symlink・作業ツリーの根からの相対）は cite.resolved で解いて照らす（出どころの照らし cite.problem と同じ規則）"""
    if not path:
        return False
    want = cite.resolved(path, repo)
    return any(cite.resolved(m["path"] if (m := cite.CITE.match(w.rstrip("."))) else w.rstrip("."), repo) == want
               for w in cite.TOKEN.findall(text))


def _from_request(text: str, request_file: str, means, repo) -> bool:
    """決め手の文が依頼（依頼のファイルのパス・依頼の引用「…」・依頼の解き方 means の文か、その引用）を出どころにしているか"""
    if _names_path(text, request_file, repo):
        return True
    if cite.REQUEST_WORD in text and cite.QUOTE.search(text) is not None:
        return True
    return any(cite.quoted_in(m, text, norm=cite.fold) or any(cite.quoted_in(q, m, norm=cite.fold) for q in cite.quotes(text))
               for m in means or ())


def world_ok(answer, row, request_file, means, cite_ok, repo) -> tuple:
    if not needs(row):
        return True, "答えの要らない行（この依頼に当たる所が無い）"
    if not isinstance(answer, dict):
        return False, f"世界の解の行 {row.get('class_id')} への答えが無い"
    if answer.get("follows") is True:
        return True, "定石に従う"
    text = str(answer.get("decided_by") or answer.get("deviation") or "").strip()
    if not text:
        return False, "定石から外れる訳が無い"
    if row.get("basis") != WEB:
        return False, f"{NOT_WEB}定石からの外れ（定石を照らしていないので、外れてよいかを人に聞く）"
    bad = cite_ok(text)
    if bad:
        return False, bad
    # 依頼が解き方を示していない行の外れは、依頼の解き方を疑う形にならない
    if (row.get("versus") or {}).get("verdict") != NONE and _from_request(text, request_file, means, repo):
        return False, "依頼（依頼のファイル・依頼の引用・依頼の解き方）を出どころにした外れ（定石と比べて疑う案なので人に聞く）"
    return True, "依頼の外の出どころで訳の立つ外れ"


def gate_line(row, answer) -> str:
    head = f"世界の解 {row.get('class_id')}（依頼の行 {row.get('finding')}）: 定石「{row.get('practice')}」{_mark(row)}／{_versus(row)}"
    if not isinstance(answer, dict):
        return f"{head}／答えが無い"
    if answer.get("follows") is True:
        return f"{head}／案は定石に従う"
    return f"{head}／案は外れる——{answer.get('deviation')}"

