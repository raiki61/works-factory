"""run の頭の深さ（issue #441。docs/design.md の「深さで飛ばすノードの表」）。使うのは判定と線の script。

単位ごとの深さ（depth.py）の上に、run 全体の深さ（軽量・標準）を run の頭で 1 度決める。易しいかは意味の問いなので役が決め、ここは
事実を測って役に渡し、役の引用が依頼の字とリポジトリの行に実在するかを照らす。照らしが通らない・根拠が引けない時は標準。
軽量の run は、表に載せたノードだけを線の when が飛ばす。ここが持つ飛ばす先の名は報告に出す SKIPPED_NODE だけ（表の行と同じ字。
tests/layers/test_depth_skip.py が突き合わせる）。

- parse_where(where): `<パス>`・`<パス>:<行>`・`<パス>:<行>-<行>` の (パス, 始めの行, 終わりの行)。行が無ければ (パス, None, None)、読めなければ None
- facts(rows, start, repo): 依頼の行ごとの字と番地の実在・試験のコマンドの有無・仕様の段・設計だけ・入力 thickness の名指し
- gate(facts): 役を起こす前の機械の止め (go, 深さ, 訳)。go が偽なら決めた深さと訳で控えを書き、役を起こさない
- brief(facts): 役に貼る材料の本文
- check(reply, rows, repo): 役の返答の照らし。拒む訳の並び（空なら受ける）
- write(jdir, doc)・read(jdir): 控え RECORD の読み書き。read は無い・読めない時に標準の控え
- record(depth, why, *, items, facts): 控えの形
- due(head_depth, ready, plan_rows): 計画の往復の 1 周で事前審査を飛ばすか {skip, why}。頭が軽量でも計画の単位が全部軽量でなければ
  上げ、why は RAISED（単位ごとの訳は報告の次の行の depth.lines が出す）
- report_line(depth, why, skipped, raised): 報告の冒頭 2 の 1 行
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import depth  # noqa: E402
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
RAISED = "計画の単位がすべて軽量ではない"
SKIPPED_NODE = "plan-review-run__review-loop"   # due が飛ばすノードの run の記録の id
DESIGN_ONLY = "true"   # 始めの記録の design_only の語（gatemarks.DESIGN_ONLY と同じ）


def _squash(text) -> str:
    return "".join(str(text or "").split())


def parse_where(where):
    text = str(where or "").strip()
    if not text:
        return None
    path, sep, lines = text.rpartition(":")
    if not sep:
        return text, None, None
    first, dash, last = lines.partition("-")
    if not first.isdigit() or (dash and not last.isdigit()):
        return text, None, None
    first = int(first)
    last = int(last) if dash else first
    if not path or first < 1 or last < first:
        return None
    return path, first, last


def _file_lines(repo, path: str):
    """リポジトリ repo の中の通常のファイル path の行の並び（根の外・無い・読めなければ None）"""
    root = pathlib.Path(repo).resolve()
    target = (root / path).resolve()
    if pathlib.PurePosixPath(path).is_absolute() or not target.is_relative_to(root) or not target.is_file():
        return None
    try:
        return target.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _place(repo, where) -> dict:
    parsed = parse_where(where)
    lines = _file_lines(repo, parsed[0]) if parsed else None
    in_range = lines is not None and (parsed[1] is None or parsed[2] <= len(lines))
    return {"path_ok": lines is not None, "lines_ok": in_range}


def facts(rows, start, repo) -> dict:
    start = start if isinstance(start, dict) else {}
    items = [{"item": n, "text": str(r.get("text") or ""), "where": str(r.get("where") or ""), **_place(repo, r.get("where"))}
             for n, r in enumerate((r for r in rows or [] if isinstance(r, dict)), start=1)]
    return {"items": items,
            "test_cmd": bool(start.get("test_cmd") or start.get("tdd_suite")),
            "spec": (startrec.shape(start) or {}).get("spec") is True,
            "design_only": start.get("design_only") == DESIGN_ONLY,
            "forced": str(start.get("thickness") or "").strip()}


def gate(f: dict) -> tuple:
    if f["forced"] in (LIGHT, STANDARD):
        return False, f["forced"], f"入力 thickness の名指し（{f['forced']}）"
    for stop, why in ((f["spec"], "仕様の段を挟む run"),
                      (f["design_only"], "設計だけの run"),
                      (not f["items"], "依頼の行が無い（差分だけの run）"),
                      (not f["test_cmd"], "機械の確かめが無い（tdd_suite も test_cmd も空。代わりの最後のテストが測れない）")):
        if stop:
            return False, STANDARD, why
    return True, "", ""


def brief(f: dict) -> str:
    rows = [f"- 行 {it['item']}: {it['text']}\n  - 番地: {it['where'] or '（無い）'}"
            f"（ファイル {'在る' if it['path_ok'] else '無い'}・行の範囲 {'ファイルの中' if it['lines_ok'] else '外か読めない'}）"
            for it in f["items"]]
    return "\n".join(["# run の頭の深さの材料（機械が測った）", "", f"依頼の行 {len(f['items'])} 個:", *rows, "",
                      f"機械の確かめ（試験のコマンド）: {'在る' if f['test_cmd'] else '無い'}", ""])


def _check_item(it: dict, rows: list, repo) -> list:
    n = it.get("item")
    head = f"行 {n}: "
    out = []
    if not _squash(it.get("cause_quote")) or _squash(it.get("cause_quote")) not in _squash(rows[n - 1].get("text")):
        out.append(head + "cause_quote が依頼のその行の字の部分でない")
    parsed = parse_where(it.get("where"))
    if parsed is None or parsed[1] is None:
        return out + [head + f"where が <パス>:<行> か <パス>:<行>-<行> の形でない（{it.get('where')!r}）"]
    path, first, last = parsed
    lines = _file_lines(repo, path)
    if lines is None:
        return out + [head + f"where のファイル {path} が対象のリポジトリの中に無い"]
    if last > len(lines):
        return out + [head + f"where の行 {first}-{last} が {path} の {len(lines)} 行の外"]
    if not _squash(it.get("code_quote")) or _squash(it.get("code_quote")) not in _squash("\n".join(lines[first - 1:last])):
        out.append(head + f"code_quote が {path}:{first}-{last} の字に無い")
    return out


def check(reply, rows, repo) -> list:
    if not isinstance(reply, dict):
        return ["返答が object でない"]
    if reply.get("depth") not in (LIGHT, STANDARD):
        return [f"depth が {LIGHT}・{STANDARD} のどちらでもない（{reply.get('depth')!r}）"]
    if not str(reply.get("why") or "").strip():
        return ["why が空"]
    if reply["depth"] == STANDARD:
        return []
    rows = [r for r in rows or [] if isinstance(r, dict)]
    items = [it for it in reply.get("items") or [] if isinstance(it, dict)]
    named = [it.get("item") for it in items]
    want = list(range(1, len(rows) + 1))
    if sorted(n for n in named if isinstance(n, int) and not isinstance(n, bool)) != want or len(named) != len(want):
        return [f"items が依頼の行 {len(rows)} 個をちょうど 1 度ずつ指していない（指した行: {named}）"]
    return [why for it in items for why in _check_item(it, rows, repo)]


def record(depth_word: str, why: str, *, items=(), facts_doc=None) -> dict:
    return {"depth": depth_word, "why": why, "items": list(items), "facts": facts_doc or {}}


def write(jdir, doc: dict) -> pathlib.Path:
    return jsonfile.write(pathlib.Path(jdir) / RECORD, doc, parents=True)


def read(jdir) -> dict:
    try:
        doc = json.loads((pathlib.Path(jdir) / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return record(STANDARD, NO_RECORD)
    if not isinstance(doc, dict) or doc.get("depth") not in (LIGHT, STANDARD):
        return record(STANDARD, NO_RECORD)
    return doc


def due(head_depth, ready, plan_rows) -> dict:
    if head_depth != LIGHT or ready is not True:
        return {"skip": False, "why": ""}
    rows = [r for r in plan_rows or [] if isinstance(r, dict)]
    if depth.run_depth({"units": dict(enumerate(rows))}) != LIGHT:
        return {"skip": False, "why": RAISED}
    return {"skip": True, "why": f"run の頭の深さが{LIGHT}で、計画の単位 {len(rows)} 個がすべて{LIGHT}"}


def report_line(depth_word, why, skipped: bool, raised: str) -> str:
    head = f"run の頭の深さ: {depth_word or STANDARD}"
    if raised:
        head += f" → {STANDARD}へ上げた（{raised}）"
    elif why:
        head += f"（根拠: {why}）"
    return f"{head}／飛ばしたノード: {SKIPPED_NODE if skipped else '無い'}"
