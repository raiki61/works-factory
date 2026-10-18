"""fix の置き場（run の作業のファイルを置くフォルダ。scripts が渡す）の読み書きの助け。

今の works の盤面の物 `b` から読んでいた値を、置き場のファイルか引数で受ける形にした物だけを置く。

- trace(place, op, **kw): 置き場の trace.jsonl に {"op": op, **kw} を 1 行足す（元の盤面の b.trace の代わり）
- base_rev(state, given=""): 突き合わせの起点の版（元 works/.shared/core/writes.py:88 の base_rev）
- gate_view(place)・gate_asks(place)・write_notes(place): 修正前の関所の答え（answers.json）と判定の写しを gatemarks の問いの口に
  渡す形と、答え待ちで外す単位・答えで戻る単位、修正役と TDD の役が読む一言のファイル（元は盤面の record と line_edge の h-fix）
- record_base_rev(place, repo)・base_rev_of(place, given=""): 修正前の版の控えと読み（並べた組の子の HEAD は親の HEAD と
  違うので、親の prep が控えて子が写す。新しい）
- marks_view(place, round_=1): planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits）に渡す読むだけの形
  （dir と round だけ。conflict の test_permits・frozen_fields が使う。fix のブロックの中だけの合わせ口）
- plan_view(place, plan, judgment, round_=1): planmarks の承認済みの修正案の読み口に渡す読むだけの形（修正案の役の返答と
  判定を値で持つ。planbrief・範囲の照らしの items が使う。fix のブロックの中だけの合わせ口）
- owed_units_but_asked(place, owed, withheld=, returned=)・fix_duty(place, owed, withheld_by=, returned=)・
  nothing_owed_but_excused(place, owed, withheld_by=, returned=): 直す義務（元 works/.shared/core/conflict.py:676・696・787。
  盤面の写しの規則と問いの台帳を読んだ所を、値の引数で受ける）
- _fix_output(reply_file)・fix_reply(reply_file=None): 修正の返答の読み口
  （元 works/.shared/core/recount.py:89・101。盤面の p3.fix の出力を読んだ所を、返答のファイルのパスで受ける）
- pr_revs(repo, base, head)・pr_diff(repo, base_sha, head_sha, skip, *opts)・pr_added_lines(repo, base_sha, head_sha, skip):
  審査する変更（起点 → 修正前の HEAD）の差分と、それが足した行（直しの差分 run_diff と分ける側。目の起点の訳と独立設計の制約の
  印が引く。新しい）
- ROLE_DEF_HEAD: 役の定義の見出し（元 works/.shared/core/rolekit.py:205 の写し。lenses.render が使う）
- write_json・out_file・output・loop_file・loop_value・snapshot・tree_moved_since・take・READONLY_MOVED: 差分の審査と手直しの
  置き場の決まった名のファイル（盤面の b.output_of_round・b.loop_state と entry.snapshot・take の代わり。元 entry.py:1228・1231・1240・1262）
- _owed_rows・_read_value・_brief・_plan_items・scope_brief・_fix_report・tie_items・hole_ties: 差分の審査と手直しの材料（元
  works/.shared/core/refix.py:189・197・219・340・362・291・308。盤面の読みを置き場のファイルと引数の値で受ける）。役の brief の範囲の欄
  （plan_items・ruled_paths・agreed）は scope_brief が planrange.scope の 1 つの口から組む
- group_result・adopt_returned・adopt_tdd_states: 組の子の結果と、戻せた組の子から親の置き場へ写す物（書き込みの記録・TDD の輪の状態・
  範囲の相談の合意）の 1 つの口

外のパッケージは使わない（startrec・gatemarks・jsonfile のほかの lib の部品は、使う関数の中で import する）。
"""
import functools
import json
import os
import pathlib
import posixpath
import types

import answer
import jsonfile
import oneline
import policy
import promptsection
import rolekit
import startrec

PREP_INPUTS = ("start", "judgment", "answer_ties", "materials", "depth_record", "plan", "fix_plan", "plan_review", "ripple", "depth", "head_depth",
               "answers", "units", "only_items", "baseline", "prior_conflicts", "notes")   # prep の入力の字 raw の名（fix の script の prep.py と group_start.py が引く）
TRACE_FILE = "trace.jsonl"
ACCEPT_TRACE_FILE = "accept-trace.json"   # 受け付けが選んだ試験を走らせた回の行の並び（[行, …]。tests_trace が足す。読むのは最後の関所と報告）


def trace(place, op: str, **kw) -> None:
    """置き場 place の trace.jsonl に {"op": op, **kw} を JSON の 1 行で足す（フォルダが無ければ作る）"""
    path = pathlib.Path(place) / TRACE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": op, **kw}, ensure_ascii=False) + "\n")


def trace_rows(place, keep) -> list[dict]:
    """置き場 place の trace.jsonl の行のうち keep(行) が真の物（行の並びのまま）。trace が無い・読めなければ []。壊れた行は飛ばす"""
    try:
        lines = (pathlib.Path(place) / TRACE_FILE).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and keep(row):
            out.append(row)
    return out


def tests_trace(place, state_file, note: str, *, pass_: str, attempt: int) -> None:
    """受け付けの回 (pass_, attempt) に選んだ試験を走らせた知らせ（tddloop.selected_problems の 2 つ目の返り。0 件しか走らなかった・
    走らせられない・実行器が無い・新しい赤なし）を、置き場 place の ACCEPT_TRACE_FILE の並びの末尾に 1 行足す。行の形は元の盤面の
    trace の行 {op: impact.ACCEPT_TRACE_OP, node, note, ci_left, final_left, final_far}（元 works/blk-fix/scripts/accept.py:708）に
    pass と attempt を足した物（回ごとに足し、受けた回の行を読み手が選ぶ）。元は受けた回だけ盤面の trace に書いた（新しい関数）"""
    import impact
    import tddloop
    path = pathlib.Path(place) / ACCEPT_TRACE_FILE
    rows = read_json(path, [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} が行の並び（JSON の array）でない")
    rows.append({"op": impact.ACCEPT_TRACE_OP, "node": FIX_ACCEPT_BY, "pass": pass_, "attempt": attempt, "note": note,
                 "ci_left": tddloop.ci_left(state_file), "final_left": tddloop.final_left(state_file),
                 "final_far": tddloop.final_far(state_file)})
    write_json(path, rows)


def accept_trace_rows(place, results=()) -> list:
    """返りの diff の隣の ACCEPT_TRACE_FILE の行: 組の子の結果 results の accept_trace の行（組の順。子の行は group_id を持つ）と、
    置き場 place の行（裁定の後の受け付けの回）と、置き場の trace.jsonl の受け付けの行（事後の関門の束が赤緑を確かめずに受けた回・
    はみ出しの決着・範囲の相談。TRACED_OPS）を重ねずに並べた物。置き場の並びが行の配列でなければ ValueError"""
    path = pathlib.Path(place) / ACCEPT_TRACE_FILE
    own = read_json(path, [])
    if not isinstance(own, list):
        raise ValueError(f"{path} が行の並び（JSON の array）でない")
    traced = trace_rows(place, lambda row: row.get("op") in traced_ops())
    out: list = []
    for row in [*(x for r in results for x in (r or {}).get("accept_trace") or []), *own, *traced]:
        if isinstance(row, dict) and row not in out:
            out.append(row)
    return out


def base_rev(state, given: str = "") -> str:
    """突き合わせの起点の版: state["inputs"]["review_rev"]（修正前に固めた版）。無ければ given、それも空なら HEAD。
    元 works/.shared/core/writes.py:88（盤面の b.state を読んだ）。state は同じ形の dict（{"inputs": {...}}）か None"""
    return ((state or {}).get("inputs") or {}).get("review_rev") or given or "HEAD"


def marks_view(place, round_: int = 1):
    """planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits。読むのは b.dir と b.round だけ）に渡す読むだけの形:
    dir は置き場 place（plan-fields.json と凍結の印の行の在る trace.jsonl を置く所）、round は round_"""
    return types.SimpleNamespace(dir=pathlib.Path(place), round=round_)



def plan_view(place, plan=None, judgment=None, round_: int = 1):
    """planmarks の承認済みの修正案の読み口（plan_items・approved_items・prescriptions。読むのは b.dir・b.round・
    b.output_of_round・b.latest_output・b.trace だけ）に渡す形: dir は置き場 place（plan-fields.json と凍結の印の行の在る
    trace.jsonl を置く所）、round は round_、output_of_round(node, rnd) は rnd が round_ の時だけ修正案の役の返答 plan
    （{"plan": [...]}。今の works の p2.fix_plan の出力。入力 fix_plan の先の写し PLAN_REPLY_FILE）、latest_output(node) は判定 judgment
    （judgment.json の dict）、trace は置き場の trace.jsonl への 1 行（trace）。fix のブロックの中だけの合わせ口（marks_view と同じ）"""
    def output_of_round(node, rnd):
        return plan if rnd == round_ else None

    def latest_output(node):
        return judgment

    def put(op, **kw):
        trace(place, op, **kw)
    return types.SimpleNamespace(dir=pathlib.Path(place), round=round_, output_of_round=output_of_round,
                                 latest_output=latest_output, trace=put)

def owed_units_but_asked(place, owed, *, withheld=(), returned=()) -> set:
    """直す義務の単位: owed（開いた単位から、人に諮っている fork の出どころ・depends を除いた物。元は盤面の写しの規則の
    _owed_units）から、関所に載せる問いのうち答えていない物の出どころ・depends（withheld。元は gatemarks.withheld）を除き、
    修正前の関所か依頼の answers で答えた問いと、無人の run が判定の推しを採った問いの出どころ・depends（returned。元は
    gatemarks.returned）を戻し、直す裁定でない裁定を受けた単位（conflict.held_by_rulings。ask_human・fix_plan_item）を除く。控えが読めなければ裁定の単位を外さない（義務を減らさない側）。
    元 works/.shared/core/conflict.py:676（盤面の b.state["graph"] の規則と b.record の問いを読んだ）"""
    import conflict
    got = (set(owed) - set(withheld)) | set(returned)
    try:
        return got - set(conflict.held_by_rulings(place))
    except ValueError:   # 控えが読めない置き場は外さない（義務を減らさない側）
        return got


def fix_duty(place, owed, *, withheld_by=None, returned=()) -> tuple:
    """(直す義務 owed_units_but_asked, 直す義務から外れた単位 {key: 理由})。外れた単位は、答えていない fork・escalate の問いの
    出どころ・depends（withheld_by {key: 問い}。元は gatemarks.withheld_by。理由はそこが組にした問い）と、直す裁定でない裁定を
    受けた単位（conflict.held_by_rulings。理由はその裁定）。1 単位が withheld と裁定の両方に当たれば裁定の理由。控えが読めなければ
    裁定の単位を外さない。
    withheld_by が None なら置き場の判定の写しと関所の答えから引く（gate_asks）。
    元 works/.shared/core/conflict.py:696（盤面の記録と問いの台帳を読んだ）"""
    import conflict
    withheld_by = gate_asks(place)[0] if withheld_by is None else withheld_by
    owed = owed_units_but_asked(place, owed, withheld=set(withheld_by), returned=returned)
    out = {k: f"答え待ちの問い {q.get('key')}（{q.get('kind')}・{q.get('status')}）" for k, q in withheld_by.items()}
    try:
        out.update(conflict.held_by_rulings(place))
    except ValueError:
        pass
    return owed, {k: why for k, why in out.items() if k not in owed}


def nothing_owed_but_excused(place, owed, *, withheld_by=None, returned=()) -> dict:
    """直す義務が空で、外れた単位（fix_duty の 2 つ目）が 1 件以上ある置き場なら外れた単位 {key: 理由}（空の changes が正しい
    返答）。違う・読めなければ空（止める側）。元 works/.shared/core/conflict.py:787"""
    try:
        owed, excused = fix_duty(place, owed, withheld_by=withheld_by, returned=returned)
        return excused if excused and not owed else {}
    except Exception:   # 置き場・控えが読めない: 空の申告は今どおり止める
        return {}


def _fix_output(reply_file) -> tuple:
    """(修正の返答, そのファイルの絶対パス)。reply_file は受け付け（fix-accept の script）が置き場に書いた今の周の返答の
    ファイル。無い・読めなければ recount.Unreadable。元 works/.shared/core/recount.py:89（盤面の state.outputs["p3.fix"] の
    今の周の file を読んだ）"""
    import recount
    if not reply_file:
        raise recount.Unreadable(f"今の周の {recount.FIX_NODE} の返答のファイルが渡されていない")
    f = pathlib.Path(reply_file).resolve()
    try:
        return json.loads(f.read_text(encoding="utf-8")), f
    except (OSError, ValueError) as e:
        raise recount.Unreadable(f"{recount.FIX_NODE} の返答 {f} が読めない: {e}") from None


def fix_reply(reply_file=None) -> tuple:
    """(修正の返答, そのファイルの絶対パス)。今の周の返答のファイル reply_file（_fix_output）。無ければ recount.Unreadable。
    元 works/.shared/core/recount.py:101（盤面の p3.fix を読んだ。2 回目の修正の段が 1 回目の段の控え fix-held-reply.json に
    倒れる道は、控えを書く節が無いので持たない。1 回目の返答を失わないのは線の fixed）"""
    return _fix_output(reply_file)


# ---------------------------------------------------------------- 読んだ証拠（fix の fix-reads の script が呼ぶ）
READS_OWNER = "fix"   # 読んだ証拠の索引の持ち主（reads.index_name。元 recount.READS の役）


def read_stages(place) -> list:
    """読んだ証拠を集める修正の段 [(役, 段の頭の印のファイル, 指示書)]: 修正役 fix と、裁定の後の修正役 fix-ruled"""
    import fixrules
    fixer = fixrules.prompt_path(place)
    return [(READS_OWNER, pathlib.Path(place) / fixrules.head_file("first"), fixer),
            ("fix-ruled", pathlib.Path(place) / fixrules.head_file("ruled"), fixer.with_name(fixer.stem + fixrules.RULED_TAIL))]


def collect_reads(place, log, *, repo) -> dict:
    """修正の段の役（read_stages）が、機械が渡したパス（その段の指示書・置き場の判定の写し judgment.json・今の周の brief の
    ファイル）を読んだ証拠を reads.collect で集め、置き場に reads-<役>.json と索引（reads.index_name(READS_OWNER)。{役: 役ごとの
    証拠のパス}）を書く（元 works/blk-fix/scripts/reads.py の節 fix-reads と fixrules.reads_more）。記録はその段の頭の印を置いた
    時刻から後の、その段の指示書を読んだ session の行で切る。指示書か頭の印の無い段（役を起こしていない・この run の形で走らない段）は
    索引に null で、訳を why に置く。受け付けの条件にしない。返り {ok: True, missing, index_file}"""
    import planbrief
    import reads
    p = pathlib.Path(place)
    shared = [str(p / JUDGMENT_FILE), *planbrief.files(p)]
    index, missing, idle = {}, [], []
    for role, head, prompt in read_stages(p):
        if not (prompt.is_file() and head.is_file()):
            index[role] = None
            idle.append(role)
            continue
        got = reads.collect(p, role, [str(prompt), *shared], log, own=[str(prompt)], since=reads.stamp(head.stat().st_mtime),
                            repo=repo)
        index[role] = got["reads_file"]
        missing += got["missing"]
    if idle:
        index[reads.INDEX_WHY] = f"{reads.NOT_LAUNCHED}: {'・'.join(idle)}"
    out = write_json(p / reads.index_name(READS_OWNER), index)
    return {"ok": True, "missing": missing, "index_file": str(out)}


# ---------------------------------------------------------------- 差分の審査と手直し（refix・lenses・rulebook が読む）
# 役の定義の見出し（元 works/.shared/core/rolekit.py:205 の写し。main の lib/rolekit.py に無いので fix の中に置く）
ROLE_DEF_HEAD = "## 役の定義（{agent}）"


# 置き場の決まった名のファイル（盤面の節の出力 b.output_of_round・loop の値 b.loop_state の代わり。refix の受け付けと切りが書く）
OUT_NAME = "out-{}.json"     # 節 nid の受け付けた返答（例 out-p3.delta_review.json）
LOOP_NAME = "loop-{}.json"   # loop の鍵の値（例 loop-fix_delta.json）
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "   # 元 works/.shared/core/entry.py:1228
# 役に見せる材料の節ごとの読む値（元 works/.shared/core/graphloops/graphs/review-loop.json の節の reads の写し。inputs.* は除く）
NODE_READS = {
    "p3.delta_review": ("loop.fix_delta.file", "loop.fix_delta.files", "out.p2.plan_review", "out.p3.fix.plan_faces"),
    "p3.delta_fix": ("loop.delta_owed", "loop.fix_delta.file"),
    "p3.delta_review2": ("loop.fix_delta2.file", "loop.fix_delta2.files", "out.p3.delta_fix.handled"),
    "p3.delta_fix2": ("loop.delta_owed2", "loop.fix_delta2.file"),
}


def write_json(path, doc) -> pathlib.Path:
    return jsonfile.write(path, doc, indent=2, parents=True)


def read_json(path, default=None):
    """JSON のファイルの値。無ければ default。読めない・JSON でなければ ValueError"""
    path = pathlib.Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{path} が読めない: {e}") from None


def _given(v):
    """引数の値: None はそのまま、口（引数なし）は呼んだ返り、パス（str・PathLike）はそのファイルの JSON（無ければ None）、
    ほかは値のまま"""
    if v is None:
        return None
    if callable(v):
        return v()
    if isinstance(v, (str, os.PathLike)):
        return read_json(v) if str(v) else None
    return v


def out_file(place, nid) -> pathlib.Path:
    return pathlib.Path(place) / OUT_NAME.format(nid)


def output(place, nid):
    """置き場の節 nid の受け付けた返答（無ければ None）。盤面の b.output_of_round(nid, b.round) の代わり"""
    return read_json(out_file(place, nid))


def loop_file(place, key) -> pathlib.Path:
    return pathlib.Path(place) / LOOP_NAME.format(key)


def loop_value(place, key):
    """置き場の loop の鍵 key の値（無ければ None）。盤面の b.loop_state.get(key) の今の周の値の代わり"""
    return read_json(loop_file(place, key))


def snapshot(place, name: str, repo) -> pathlib.Path:
    """読むだけの役を起こす前に、作業ツリーの姿（accept.tree_state）を置き場の name に書き、パスを返す。take(…, snapshot_name=name)
    がこれと今の作業ツリーを比べる。元 works/.shared/core/entry.py:1231（b.work(name) を置き場のパスに）"""
    import accept
    return write_json(pathlib.Path(place) / name, accept.tree_state(pathlib.Path(repo)))


def tree_moved_since(place, name: str, repo, keys=None) -> str:
    """置き場の name の写しと今の作業ツリーの違いを述べる文（同じなら空。keys の欄だけを比べる。None は accept.TREE_KEYS）。写しが
    無い・形が違うのは snapshot が走っていない回す側の誤りで ValueError。元 works/.shared/core/entry.py:1240（b.work(name) を置き場の
    パスに、BoardGap を ValueError に）"""
    import accept
    from engine.schema import validate_schema
    p = pathlib.Path(place) / name
    try:
        snap = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"作業ツリーの写し {p} が読めない（読むだけの役を起こす前に snapshot が走っていない）: {e}") from None
    errs = validate_schema(snap, accept.TREE_SCHEMA)
    if errs:
        raise ValueError(f"作業ツリーの写し {p} の形が違う: " + "; ".join(errs))
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, pathlib.Path(repo), keys=keys or accept.TREE_KEYS)
    if not moved:
        return ""
    return "この役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（" + "・".join(moved) + "）"


def take(place, nid: str, reply: dict, repo, *, snapshot_name: str | None = None, keys=None) -> dict:
    """役の返答を置き場に受ける: snapshot_name が在れば読むだけの役の写しと今の作業ツリーを比べ（keys は tree_moved_since）、違えば
    {ok: False, reason: READONLY_MOVED + 文}。同じなら返答を out_file(place, nid) に置いて {ok: True, reply_file}。
    元 works/.shared/core/entry.py:1262 の take のうち、写しの比べと出力の置きだけ（盤面の規則の照らし vet と settle は持ってこない。
    返答の形は実行基盤の出力の型が照らす）"""
    if snapshot_name:
        moved = tree_moved_since(place, snapshot_name, repo, keys)
        if moved:
            return {"ok": False, "reason": READONLY_MOVED + moved}
    return {"ok": True, "reply_file": str(write_json(out_file(place, nid), reply))}


def _owed_rows(place, n) -> list:
    """n 回目の手直しが答える義務 [{key, from, text}]: 置き場の n 回目の審査の返答の faces と、塞がっていない検算
    （closed が false）。元 works/.shared/core/refix.py:189（盤面の loop.<owed_key> を読んだ）と、その値を組んだ写しの規則
    works/.shared/core/graphloops/rules/review-loop.py:571 の _owed_rows（同じ式）"""
    import refix
    p = refix._pass(n)
    rv = output(place, p["review"]) or {}
    rows = [{"key": f["key"], "from": p["review"], "text": f"{f['kind']} {f['where']}:「{f['cite']}」——{f['why']}"}
            for f in rv.get("faces") or []]
    rows += [{"key": c["key"], "from": f"{p['review']}.checks", "text": f"塞いだと言われたが、差分で塞がっていない——{c['why']}"}
             for c in rv.get("checks") or [] if c["closed"] is False]
    return rows


def _read_value(values: dict, path: str):
    """reads の 1 行（out.<節>[.<欄>]・loop.<鍵>[.<欄>]）の値。values は {"out.<節>" か "loop.<鍵>": 値}（最長一致）。
    無ければ None。元 works/.shared/core/refix.py:197（盤面の今の周の値を読んだ）"""
    head = max((k for k in values if path == k or path.startswith(k + ".")), key=len, default=None)
    if head is None:
        return None
    v, sub = values[head], path[len(head) + 1:]
    if v is None or not sub:
        return v
    import sys
    _gl = str(pathlib.Path(__file__).resolve().parent / "graphloops")
    if _gl not in sys.path:
        sys.path.insert(0, _gl)
    import engine.util as _util
    try:
        return _util.get_path(v, sub)
    except KeyError:
        return None


def _brief(nid, values: dict) -> dict:
    """役に見せる材料: その節に読ませる値（NODE_READS。inputs.* を除く）の姿。元 works/.shared/core/refix.py:219（graph の節の
    reads を盤面の今の周から読んだ）"""
    return {p: _read_value(values, p) for p in NODE_READS.get(nid, ()) if not p.startswith("inputs.")}


def _plan_items(place, items, by: str = "") -> list:
    """scope_brief の plan_items（refix.accept_review の照らしが読む）。元 works/.shared/core/refix.py:340（盤面の
    planmarks.scoped_items(b) を読んだ）"""
    return scope_brief(place, items, by=by)["plan_items"]


def scope_brief(place, items, by: str = "") -> dict:
    """役の brief の範囲の欄 {plan_items, ruled_paths, agreed}（差分の審査 refix.cut と手直し prep_fix の 1 回目が載せる 1 つの口）。
    範囲の値は受け付けが照らすのと同じ planrange.scope（範囲の相談の合意を置き場 place から読む。scope の permits は使わない）から
    引く。plan_items は scope の items（合意のパスを allowed_paths に足し、許したテストの範囲は印 agreed つきで tests に足した物）の
    写しに、裁定（置き場 place の conflicts.json）で外れた項目（conflict.held_item）の held・単位の一部だけが外れた項目の held_units を
    足した物。ruled_paths は直す裁定が広げたパス（conflict.ruled_paths）、agreed は plan_items に足した合意の行（conflict.agreed の行の
    まま。出どころは各行の id と group_id）。範囲の欄の無い控え・修正案の無い run は plan_items と agreed が []。items は
    planmarks.approved_items の形の値か、それを返す口か、その JSON のパス。口が凍結の印との食い違い（planmarks.FieldsBroken）を出せば
    conflict.fields_broken の道（by の印の文の ValueError。既定は差分の審査の段 stopby.DELTA）"""
    import copy
    import conflict
    import planmarks
    import planrange
    import stopby
    by = by or stopby.DELTA
    try:
        items = _given(items)
    except planmarks.FieldsBroken as e:
        raise conflict.fields_broken(None, e, by=by) from None
    got = planrange.scope(place, items=items, ruled=False, by=by)[0]
    plan_items = copy.deepcopy(got["items"]) if got else []
    held = conflict.held_by_rulings(place) if plan_items else {}
    for it in plan_items:
        why = conflict.held_item(it.get("unit_keys"), held)
        some = conflict.held_units(it.get("unit_keys"), held)
        if why:
            it["held"] = why
        elif some:
            it["held_units"] = some
    return {"plan_items": plan_items, "ruled_paths": conflict.ruled_paths(place), "agreed": got["agreed"] if got else []}


def _fix_report(fix_reply) -> dict:
    """直した側の報告（修正の返答の changes・not_done）。返答が無ければ空。fix_reply は修正役の返答の値かその JSON のパス。
    元 works/.shared/core/refix.py:362（盤面の今の周の p3.fix の出力を読んだ）"""
    out = _given(fix_reply)
    return {k: out.get(k) or [] for k in ("changes", "not_done")} if isinstance(out, dict) else {}


def tie_items(place, items) -> list:
    """名札に使う承認済みの修正案の項目（items。_plan_items と同じ形の値・口・パス）の写しに、裁定で外れた項目の held
    （conflict.held_item）を足した物。引けない・控えが壊れている時は []（名札は材料で、止めない）。
    元 works/.shared/core/refix.py:291（盤面の planmarks.approved_items(b) を読んだ）"""
    import copy
    import conflict
    import planmarks
    try:
        items = copy.deepcopy(_given(items)) or []
        held = conflict.held_by_rulings(place) if items else {}
    except (planmarks.FieldsBroken, OSError, ValueError):
        return []
    for it in items:
        why = conflict.held_item(it.get("unit_keys"), held)
        if why:
            it["held"] = why
    return items


def hole_ties(place, n: int, *, items=None, plan_review=None, fix_reply=None) -> list:
    """n 回目の手直しの義務（_owed_rows）の穴ごとの枝の名札（holeties.tie）。義務が無ければ []。where は n 回目の審査の faces から。
    1 回目は準拠の落ちた行（置き場の deltamarks の控え）・事前審査の穴（plan_review の faces）・修正の changes（fix_reply）を、
    2 回目は 1 回目の名札と 1 回目の手直しの handled（置き場の返答。holeties.earlier）を使う。plan_review・fix_reply は値か
    JSON のパス。元 works/.shared/core/refix.py:308（盤面の loop・今の周の出力を読んだ）"""
    import deltamarks
    import holeties
    import refix
    p = refix._pass(n)
    rows = _owed_rows(place, n)
    if not rows:
        return []
    rv = output(place, p["review"]) or {}
    where = {f.get("key"): f.get("where") for f in rv.get("faces") or [] if isinstance(f, dict)}
    holes = [{"key": r.get("key"), "from": r.get("from") or "", "where": where.get(r.get("key")) or "",
              "check": str(r.get("from") or "").endswith(".checks")} for r in rows if isinstance(r, dict)]
    tied = tie_items(place, items)
    if n == 1:
        return holeties.tie(holes, tied, compliance=deltamarks.fail_rows(deltamarks.read(place)),
                            plan_faces=(_given(plan_review) or {}).get("faces") or [],
                            changes=(_given(fix_reply) or {}).get("changes") or [])
    handled = (output(place, refix._pass(n - 1)["fix"]) or {}).get("handled") or []
    return holeties.tie(holes, tied, earlier=holeties.earlier(
        hole_ties(place, n - 1, items=items, plan_review=plan_review, fix_reply=fix_reply), handled))


# ---------------------------------------------------------------- 組の分けと戻し・返す節の欄（fix の prep・join・tdd-unit・
# conflict-check・assert-changed・collect の scripts が呼ぶ。盤面の輪の配線だった所を、置き場のファイルと値の引数で受ける）

MODES = {"": False, "group": True}       # 入力 mode の語 → 組の子の run か（route が振り分け、collect が出力の形を選ぶ）
LANE_SWITCHES = ("fix_lanes", "tdd_lanes")   # 機能の切り替えの語。どちらかが off なら組を並べない（元 works/.shared/core/entry.py:421-440）
NO_RESULT = "組の子の run が結果のファイルを書かなかった（子が落ちたか、結果が読めない）"
DELTA_DIR = "delta"                       # 差分の審査の控えの置き場（置き場の下）
DELTA_REVIEW = "review-{}.json"           # n 回目の審査の控え {pass: bool}（delta-accept・review2-accept が書く）
DELTA_SKIPPED = "skipped.json"            # 審査を飛ばした印 {reason}（頭も全部の単位も軽量・差分が空で塞いだ穴も無い。delta-cut が書く）
CHANGED_MARKS = ("mechanism_changed", "premise_drift", "gates_changed", "seams_changed", "security_surface_changed",
                 "path_changed")
DRIFT_NOTE = "premise_drift_note"   # 修正役の返答と返りの changed の欄: 前提のずれの申告の文（premise_drift が真の時の測り直した制約）
X_SCALARS = "x_scalars"             # 修正役の返答と返りの欄: 修正役が足した x_ の規模の数値
NOT_CHANGED = "修正役は済んだと言ったが、申告したファイル {files} は run の始めから何も変わっていない（変わった物: {moved}）"
NOT_DECLARED = ("修正役は済んだと言ったが、触ったファイルを 1 つも申告していない（changes[].files が空。直す義務の単位が残って"
                "いるか、答え待ち・直さない裁定で外れた単位が 1 つも無い）")



def prep(folder, worktree, raw: dict, parsed, located) -> dict:
    """入力の字 raw（{入力の名: 字}。名は PREP_INPUTS。無い名は空）を置き場 folder に写し、始めの記録（startrec.adopt。字のまま）・
    git が無視するファイルの控え・始めの木を取り、組を作って返す（置く物と返りの形は fix の節 prep の docstring）。parsed は入力の字を値に戻す口（境の口の parsed）、
    located はポインタの入力の字を置き場の中のパスに戻す口（境の口の pointed）。どちらも null・空の字を None と読む。fix の節 prep と、単独の run の組の子の頭（節 group-start。ポインタは自分の run の物）が同じ写しを置くのに
    呼ぶ"""
    import baseline_red
    import groups
    import leftovers
    import planmarks

    def value(name):
        try:
            return parsed(raw.get(name))
        except ValueError as e:
            raise ValueError(f"入力 {name} が JSON として読めない: {e}") from None

    def pointed(name):
        return located(raw.get(name))

    def read_pointed(name, required=False):
        path = pointed(name)
        if path is None and required:
            raise ValueError(f"入力 {name} が無い")
        return None if path is None else json.loads(path.read_text(encoding="utf-8"))

    folder, worktree = pathlib.Path(folder), pathlib.Path(worktree)
    start_file = pointed("start")
    if start_file is None:
        raise ValueError("入力 start が無い")
    start = startrec.adopt(folder, start_file)
    judgment_file = pointed("judgment")
    if judgment_file is None:
        raise ValueError("入力 judgment が無い")
    judgment = json.loads(judgment_file.read_text(encoding="utf-8"))
    write_json(folder / JUDGMENT_FILE, judgment)
    # 判定の結びと素材の状態（直す義務の数え gatemarks.duty が読む。無い run は字の一致だけ）と頭の深さの控え。結びと素材の状態は
    # 読み手が壊れた JSON を無いと読み、結びが黙って消えるので、ここで読めるかを確かめて落とす。頭の深さの控えは壊れていれば標準と読む
    for name, file in JUDGE_COPIES.items():
        (folder / file).unlink(missing_ok=True)
        source = pointed(name)
        if source is None:
            continue
        if not source.is_file():
            raise ValueError(f"入力 {name} の先 {source} が無い")
        if file in CHECKED_COPIES:
            try:
                json.loads(source.read_text(encoding="utf-8"))
            except ValueError as e:
                raise ValueError(f"入力 {name} の先 {source.name} が JSON として読めない: {e}") from None
        (folder / file).write_bytes(source.read_bytes())

    plan_file = pointed("plan")
    if plan_file is not None:
        doc = json.loads(plan_file.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("fields"), list):
            raise ValueError(f"修正案の欄 {plan_file.name} の形が違う（{{round, fields}}）")
        amended = doc.get(planmarks.AMENDED_KEY)
        planmarks.save(folder, 1, doc["fields"], {int(n): c for n, c in amended.items()} if isinstance(amended, dict) else None)
    (folder / PLAN_REPLY_FILE).unlink(missing_ok=True)
    plan = read_pointed("fix_plan") if plan_file is not None else None
    if plan is not None:
        write_json(folder / PLAN_REPLY_FILE, plan)
    (folder / PLAN_REVIEW_FILE).unlink(missing_ok=True)
    review = read_pointed("plan_review")
    if review is not None:
        write_json(folder / PLAN_REVIEW_FILE, review)
    ripple = read_pointed("ripple")
    if ripple is not None:
        write_json(folder / RIPPLE_FILE, ripple)
    write_json(folder / HEAD_DEPTH_FILE, str(raw.get("head_depth") or "").strip())
    for name, file in (("depth", DEPTH_FILE), ("answers", ANSWERS_FILE), ("units", UNITS_FILE)):
        got = value(name)
        if got not in (None, "", [], {}) or name == "units":
            write_json(folder / file, got if got is not None else [])
    only = value("only_items") or []
    if not isinstance(only, list):
        raise ValueError("入力 only_items が配列でない")
    write_json(folder / ONLY_ITEMS_FILE, only)
    prior = pointed("prior_conflicts")
    if prior is not None:
        import conflict
        if not (prior.parent / conflict.FILE).is_file():
            raise ValueError(f"入力 prior_conflicts の先 {prior} が無い（1 回目の段の申し出と裁定を写せない）")
        adopt_prior_pass(folder, prior.parent, only, worktree)
    base = pointed("baseline")
    if base is not None:
        got = baseline_red.read_baseline(base)
        write_json(folder / BASELINE_FILE, {"cases": got["cases"], "exit": got["exit"], "how": got.get("how") or []})

    leftovers.record_ignored(folder, worktree)
    record_base_rev(folder, worktree)
    start_tree = groups.end_tree(worktree)
    items = place_items(folder) if plan is not None else None
    write_notes(folder, raw.get("notes") or "")
    grps = fix_groups(group_owed(folder), items, only)
    out_dir = folder / "groups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {"groups": grps, "count": len(grps), "par": parallel(grps, start.get("features_cut"), worktree),
           "start_tree": start_tree, "out_dir": str(out_dir)}
    write_json(folder / GROUPS_FILE, out)
    return out

def owed_keys(judgment) -> list:
    """直す義務の単位の key の並び（判定の units の順）: 判定 judgment（units・questions の dict）だけから数えた直す義務
    （gatemarks.duty。関所の答えも依頼の answers も無い時の数え: 開いた単位から人に聞く状態の fork と escalate の問いの出どころ・
    depends を除いた物）。元 works/.shared/core/graphloops/rules/review-loop.py:2645 の _owed_units と works の差し替え
    conflict.owed_units_but_asked"""
    import gatemarks
    return _in_order(judgment, gatemarks.duty(gatemarks.ledger(judgment)))


def _in_order(judgment, keys) -> list:
    """keys を判定の units の順に（重ねない）"""
    order = [u.get("key") for u in (judgment or {}).get("units") or [] if isinstance(u, dict) and isinstance(u.get("key"), str)]
    return [k for k in dict.fromkeys(order) if k in keys]


def fix_groups(owed, items, only_items=()) -> list:
    """直す義務の単位 owed（順）を、承認済みの修正案の項目 items（planmarks.approved_items の形 [{item, unit_keys, …}] か None）を
    共にする物どうしの組に分ける（lanekit.groups。つながりは推移的・組の並びは owed の順）。範囲（allowed_paths の glob と
    tests・rewrite_tests のファイル。planrange.item_globs）が交わり得る項目（planmarks.globs_meet）もつなぐ: 別の組の子が同じ
    ファイルを変えると、締めの節で後の組の差分が字で当たらない。範囲の無い項目は項目の番号だけでつなぐ。項目の間の依存（works の欄
    depends_on）は組の分け方にも組の中の並びにも入れる: only_items・owed で単位 keys を絞った後に、planmarks.depends_pairs(items, among=keys)
    （絞りの外の項目を通る依存は、中の端どうしの対に縮めた物）を lanekit.groups の after に渡す——前の項目の単位は後の項目の単位と
    同じ組に入り、組の中は前から先に直る（子の run は remote の既定の枝から切られ、別の組は前の組の変更を見ないので、依存する
    項目を別の組にしない）。依存の無い組の中は owed の順。only_items（項目の番号かその字の並び）が空でなければ、その項目に載る単位
    だけを残し、残した単位の項目の範囲だけを照らす。返り [{group_id: "g<n>", unit_ids, items: [項目の番号…]}]。
    元 works/blk-fix/lib/tddlanes.py:126・131 の items_of・groups（項目の番号を盤面の brief の行から引いた所を items の値で受ける）"""
    import lanekit
    import planmarks
    import planrange
    by: dict = {}
    ranges: dict = {}
    for it in items or []:
        if isinstance(it, dict) and isinstance(it.get("item"), int):
            for k in it.get("unit_keys") or []:
                by.setdefault(k, []).append(it["item"])
            got = planrange.item_globs(it)
            if got:
                ranges[it["item"]] = got
    keys = list(owed)
    only = {str(x) for x in only_items or ()}
    if only:
        keys = [k for k in keys if any(str(n) in only for n in by.get(k, []))]
    kept = [n for n in dict.fromkeys(n for k in keys for n in by.get(k, [])) if n in ranges]
    meets = [(a, b) for i, a in enumerate(kept) for b in kept[i + 1:]
             if any(planmarks.globs_meet(x, y) for x in ranges[a] for y in ranges[b])]
    rows = [(k, by.get(k, []) + [p for p in meets if set(p) & set(by.get(k, []))]) for k in keys]
    after = planmarks.depends_pairs(items, among=keys)
    return [{"group_id": f"g{i}", "unit_ids": list(g), "items": sorted({n for k in g for n in by.get(k, [])})}
            for i, g in enumerate(lanekit.groups(rows, after=after), 1)]


def parallel(groups, features_cut, repo) -> bool:
    """組を並べるか: 組が 2 つ以上で、始めの記録の features_cut（off の語）に LANE_SWITCHES のどちらも無く、対象のリポジトリ repo に
    git の remote が在る時だけ真（今の works は TDD の輪の並べと修正役の並べを別々に切れたが、組の子の run は両方を回すので、
    どちらかが在れば並べない。子ごとの作業ツリーは remote の既定の枝から切られ、remote の無いリポジトリでは子を 1 つも起こせない）"""
    import leftovers
    cut = set(features_cut) if isinstance(features_cut, list) else set()
    return len(groups) >= 2 and not cut & set(LANE_SWITCHES) and bool(leftovers.git(repo, "remote").strip())


SEMANTIC_CLASH = ("意味の食い違い: 前に戻した組と同じファイル {files} を変え、字では合ったが当てた後の木の試験が赤（{why}）。"
                  "後の組だけを戻す")   # 元 works/blk-fix/lib/tddlanes.py:684-685 の back の理由


def rerun_problem(place, repo, suite: str, cases, named, *, name: str = "rerun", rev: str = "HEAD", shared=(),
                  test_cmd: str = "") -> str:
    """組を親の作業ツリー repo へ当てた後の確かめ直しの問題の文（空なら通った。実行器 suite の無い run も空）。元
    works/blk-fix/lib/tddlanes.py:688-711 の _green_after（当てた単位の名指し全部と変更に直に関わる試験を 1 回走らせ、重なりの
    ファイルが在れば地図が届く試験の全部も足し、test_cmd の関門が on なら test_cmd も 1 回）を、組ごとの確かめにした物。
    1. 名指し named（前に戻せた組とこの組が赤 → 緑を確かめた名指し）が在れば先にそれだけを走らせ、実行器が走らない・名指しが結末に
       居ない（0 件を含む）・緑でなければその文（_RunnerDown を戻す理由にした所）。
    2. 名指しの無い組（修正役だけが直した組）も、変えたファイルに当たる試験の新しい赤を tddloop.selected_problems で見る（元の
       結末 cases に無い赤は版 rev の写しで確かめる）。前に戻した組とも重なったファイル shared が在れば、それを起点に地図が届く
       試験の全部（tddloop._reached の direct_only 偽。地図が一式を求める時は足さない）を選びに足す（元 tddlanes.py:695-698）。
    3. 赤が無く test_cmd（関門が on の時だけ呼び手が渡す。rerun_cmd）が在れば 1 回走らせ、緑でなければその文。
    shared の在る組の赤は意味の食い違い（SEMANTIC_CLASH）と名指す。走らせ直しの状態とログは置き場の <name>/ に置く"""
    import baseline_red
    import tddloop
    suite = (suite or "").strip()
    named = sorted({t for t in named or [] if isinstance(t, str) and t.strip()})
    shared = sorted({f for f in shared or () if isinstance(f, str) and f})
    if not suite:
        return ""
    exe = tddloop.exe_path(repo, suite)
    work = pathlib.Path(place) / name
    work.mkdir(parents=True, exist_ok=True)
    probs = []
    if named:
        ran, _, why = baseline_red.run_suite(str(exe), repo, work, "named", tddloop._abs_ids(repo, named), only=True)
        if ran is None:
            return f"当てた後の木で名指しのテストを走らせられない（{'; '.join(why)}）"
        hit = [c for t in named if (c := baseline_red.match_case(t, ran)) is not None]
        probs = baseline_red.green_problems(named, hit, 0)
        if probs:
            probs = ["当てた後の木で名指しのテストが緑でない: " + "；".join(probs)]
    if not probs:
        st = {"exe": str(exe), "work": str(work), "suite_made": [], "contract": {}, "unit_head": "",
              "baseline": {tddloop._key(c): c.get("outcome") for c in cases or [] if isinstance(c, dict)},
              "units": {name: {"tests": named, "test_files": []}}}
        if shared:
            wide, everything = tddloop._reached(st, repo, seeds=shared, direct_only=False)
            if not everything:
                st["units"][name]["test_files"] = wide
        state = write_json(work / tddloop.STATE, st)
        probs, _ = tddloop.selected_problems(str(state), repo, rev)
    if not probs and (test_cmd or "").strip():
        log = work / "test-cmd.log"
        mat, _ = tddloop._cmd_run(repo, test_cmd.strip(), log)
        if mat["status"] != "clean":
            probs = [f"run の test_cmd（{test_cmd.strip()}）が当てた後の木で緑でない（"
                     f"{mat.get('rewrote') or mat.get('reason') or f'ログ {log}'}）"]
    why = "；".join(probs)
    return SEMANTIC_CLASH.format(files="・".join(shared), why=why[:300]) if why and shared else why


def rerun_cmd(place, result, test_cmd: str) -> str:
    """当てた後に走らせ直す test_cmd（rerun_problem に渡す）: 組の子の TDD の輪が決めた関門（結果の tdd.test_cmd.gate）が on で、
    組に軽量でない単位（置き場の深さの控え。頭の深さが軽量でない run では全部の単位が軽量でない。unit_depths）が在る時だけ test_cmd、ほかは ""（元 works/blk-fix/lib/tddlanes.py:704）。
    tdd か tdd.test_cmd が在って dict でない結果は関門を読めないので on と見る（走らせ直しを飛ばして戻さない）"""
    import tddloop
    tdd = (result or {}).get("tdd") or {}
    cmd = (tdd.get("test_cmd") or {}) if isinstance(tdd, dict) else None
    gate = cmd.get("gate") if isinstance(cmd, dict) else tddloop.GATE_ON
    if gate != tddloop.GATE_ON or not (test_cmd or "").strip():
        return ""
    light = set(tddloop._light_units(unit_depths(place)))
    return test_cmd.strip() if set((result or {}).get("unit_ids") or []) - light else ""


CHECK_RAISED = "当てた後の確かめ直しが落ちた（{error}）"
UNRESTORED_HEAD = "当てた差分を戻せず、親の作業ツリーに当たったまま"
UNRESTORED = UNRESTORED_HEAD + "（{error}）。作業ツリーが信用できないので、後の組を当てずに人に回した。戻そうとした訳: {why}"
AFTER_UNRESTORED = "前の組 {group} の差分を戻せず親の作業ツリーが信用できないので、この組は当てていない"


def join_group(repo, from_tree: str, end_tree: str, kept, *, union=(), check=None):
    """組の子の差分（木 from_tree → 木 end_tree。groups.diff_since）を親の作業ツリー repo へ 3 方向で当てる（unittrees.apply。
    union の試験のファイルの挿しだけの食い違いは合わせる）。差分は kept に控える。当てた後に check（当てたパスの並び → 戻す理由か
    空。確かめ直し）が理由を返すか落ちれば（CHECK_RAISED）、当てたパスを当てる前の姿に戻して backed_out に名指す。戻せなければ
    当てていないと言わず、当たったままのパスを unrestored に名指して理由を UNRESTORED にする。返りは lanekit.Merge。
    元 works/blk-fix/lib/lanekit.py の merge（単位の worktree の差分を当てた所）を、子の run の終わりの木との差分で受ける形にした物"""
    import groups
    import lanekit
    import tddloop
    import unittrees
    patch = groups.diff_since(repo, from_tree, end_tree)
    kept = pathlib.Path(kept)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text(patch, encoding="utf-8", errors="surrogateescape")
    before = tddloop.snapshot(repo)
    got: list = []
    ok, why = unittrees.apply(repo, patch, union=union, unioned=got, check=unittrees.tests_unique)
    if not ok:
        return lanekit.Merge(f"差分が親の作業ツリーに当たらない（{oneline.one_line(why)[:300]}）", str(kept), [], [], True)
    names = unittrees.patch_names(patch)
    try:
        why = (check(names) if check else "") if names else ""
    except Exception as e:  # noqa: BLE001  落ちた確かめ直しも赤と同じく戻す（#406）
        why = CHECK_RAISED.format(error=f"{type(e).__name__}: {oneline.one_line(e)[:300]}")
    except BaseException:
        tddloop.restore_paths(repo, before, names)
        raise
    if not why:
        return lanekit.Merge("", str(kept), names, got, False)
    try:
        tddloop.restore_paths(repo, before, names)
    except Exception as e:  # noqa: BLE001  戻せない組を当てていないと言わない（#403）
        return lanekit.Merge(UNRESTORED.format(error=f"{type(e).__name__}: {oneline.one_line(e)[:300]}", why=why), str(kept), [], got,
                             False, unrestored=names)
    return lanekit.Merge(why, str(kept), [], [], False, names)


def join_rows(groups, outcomes, backed_out=None, unrestored=None) -> tuple:
    """(組の行 [{group_id, unit_ids, returned, reason, backed_out?, unrestored?}], 単位の行 [{unit_id, group_id, status, reason}])
    （返す節の約束の形）。outcomes は {group_id: (子の結果の dict か None, 戻せたか, 理由)}。戻せた組の単位は子の結果の status・reason
    （結果に無い単位・知らない status は not_done）、戻せなかった組・結果の無い組の単位は not_done と組の理由。backed_out は
    {group_id: 当ててから確かめ直しが赤か落ちて戻したパス}、unrestored は {group_id: 戻せず当たったままのパス}（lanekit.Merge の
    同じ名の欄）で、在る組の行にだけ同じ名の欄を置く（報告と後の節が当てなかった組と分ける）。新しい（元の締めの結末の並べ。p3.lane_merge）"""
    rows, units = [], []
    for g in groups:
        gid = g["group_id"]
        result, back, why = outcomes.get(gid, (None, False, NO_RESULT))
        marks = {k: list(v) for k, given in (("backed_out", backed_out), ("unrestored", unrestored)) if (v := (given or {}).get(gid))}
        rows.append({"group_id": gid, "unit_ids": list(g["unit_ids"]), "returned": bool(back), "reason": str(why or ""), **marks})
        got = {u.get("unit_id"): u for u in (result or {}).get("units") or [] if isinstance(u, dict)} if back else {}
        for k in g["unit_ids"]:
            u = got.get(k) or {}
            status = u.get("status") if u.get("status") in UNIT_STATUSES else NOT_DONE
            reason = str(u.get("reason") or "") if u else str(why or "組の結果にこの単位の行が無い")
            units.append({"unit_id": k, "group_id": gid, "status": status, "reason": reason})
    return rows, units


HELD = "戻せず親の作業ツリーに当たったままの組 {groups} が在る（作業ツリーが信用できないので、人が確かめるまで動かさない）"


def unrestored_of(place) -> dict:
    """置き場の join.json の、戻せず親の作業ツリーに当たったままの組 {group_id: 当たったままのパス}（欄 unrestored が在る行）。
    join.json が無い（組の子の形・join が当たったままの組の無いまま書く前に落ちた）なら {}"""
    joined = read_json(pathlib.Path(place) / JOIN_FILE, {}) or {}
    return {str(g.get("group_id")): list(g["unrestored"]) for g in joined.get("groups") or []
            if isinstance(g, dict) and g.get("unrestored")}


def held(place) -> str:
    """当たったままの組（unrestored_of）が在れば HELD の訳、無ければ ""。訳が在れば、後の節（裁定・後始末・差分の審査）は作業
    ツリーを動かさず、返す節は人に回す"""
    stuck = unrestored_of(place)
    return HELD.format(groups="・".join(stuck)) if stuck else ""


def with_ruled(units, ruled) -> list:
    """単位の行 units（join_rows の形）に、裁定の後の修正の段の結末 ruled（親の置き場の fix-units.json {key: {status, reason}}）を
    重ねる。重ねるのはまだ fixed でない行だけ（裁定の後の段は戻せた組の fixed でない単位を直す）。新しい"""
    ruled = ruled if isinstance(ruled, dict) else {}
    out = []
    for u in units:
        r = ruled.get(u["unit_id"])
        if u["status"] != FIXED and isinstance(r, dict) and r.get("status") in UNIT_STATUSES:
            u = {**u, "status": r["status"], "reason": str(r.get("reason") or "")}
        out.append(u)
    return out


def child_tdd(result) -> dict:
    """組の子の結果 result の欄 tdd（tddloop.exit_fields の形。dict でなければ空）"""
    tdd = (result or {}).get("tdd")
    return tdd if isinstance(tdd, dict) else {}


def child_tdd_units(result) -> list:
    """組の子の結果 result の TDD の輪の単位の行（tdd.units のうち dict の物。並びでなければ空）"""
    units = child_tdd(result).get("units")
    return [u for u in units if isinstance(u, dict)] if isinstance(units, list) else []


def child_verified(result) -> list:
    """組の子の結果 result の欄 verified（赤 → 緑を確かめた名指し。verified_tests の形）のうち空でない文字列（並びでなければ空）"""
    names = (result or {}).get("verified")
    return [t for t in names if isinstance(t, str) and t] if isinstance(names, list) else []


def tdd_units(groups, results) -> list:
    """型つきの成果物 tdd-unit の本文: 組ごとの TDD の輪の結果 [{group_id, ran, reason, suite, reused, units}]（子の結果の欄 tdd。
    tddloop.exit_fields の形）。結果の無い組・実行器の無い組は ran: false・units: []。results は {group_id: 子の結果の dict}"""
    out = []
    for g in groups:
        result = results.get(g["group_id"])
        tdd = child_tdd(result)
        ran = tdd.get("ran") is True
        out.append({"group_id": g["group_id"], "ran": ran,
                    "reason": str(tdd.get("reason") or ("" if result else NO_RESULT)), "suite": str(tdd.get("suite") or ""),
                    "reused": tdd.get("reused") if isinstance(tdd.get("reused"), dict) else {},
                    "units": child_tdd_units(result) if ran else []})
    return out


def cited_rows(rows, repo, roots=()) -> tuple:
    """(名指しが全部現物に在る申し出の行, 落とした行の理由の文)。行は conflict の申し出の形（FIELDS。kind は無くてもよい）で、
    between の名指しを 1 つずつ cite.problem で照らす（親の作業ツリー repo と roots の下）。between が空の機械の諦め
    （conflict.GAVE_UP_SOURCE。brief の無い run）は照らさずに通す（元 works も機械の諦めは照らさずに積んだ）。元
    works/blk-fix/lib/tddlanes.py・fixlanes.py の join の「枝の申し出は盤面の確かめを通った物を積む」所（conflict.problems の名指しの照らし）"""
    import cite
    import conflict
    need = [k for k in conflict.FIELDS if k != conflict.KIND_FIELD]
    ok, dropped = [], []
    for i, r in enumerate(rows or []):
        if not isinstance(r, dict) or any(k not in r for k in need):
            dropped.append(f"申し出[{i}] の欄が足りない（{need}）")
            continue
        cites = r["between"] if isinstance(r["between"], list) else []
        if not cites and r.get("source") == conflict.GAVE_UP_SOURCE:
            ok.append(r)
            continue
        bad = [e for e in (cite.problem(c, repo, roots) for c in cites) if e] if cites else ["between が空"]
        if bad:
            dropped.append(f"申し出[{i}]（{r.get('unit_key')}）: {'；'.join(bad)}")
        else:
            ok.append(r)
    return ok, dropped


def touched_since(repo, tree: str, skip=()) -> list:
    """木 tree（run の始めの木）から作業ツリーの今の姿（未追跡を含む・無視される物を除く）で変わったパス。除くパスの頭 skip の
    下は数えない。元 works/blk-fix/scripts/assert_changed.py の touched（版との git diff と未追跡を、始めの木との差に替えた）"""
    import tddloop
    return [p for p in tddloop.touched(repo, tree, tddloop.snapshot(repo)) if not p.startswith(tuple(skip))]


def declared_files(replies) -> list:
    """受け付けた修正役の返答（dict の並び）の changes[].files を、リポジトリの根からの相対に揃えた並び（重ねない・名の順）。
    形の違う行は ValueError。元 works/blk-fix/scripts/assert_changed.py の declared_files"""
    out = set()
    for reply in replies:
        changes = reply.get("changes") if isinstance(reply, dict) else None
        if not isinstance(changes, list) or not all(isinstance(c, dict) and isinstance(c.get("files"), list) for c in changes):
            raise ValueError("受け付けた返答に changes[].files が無い")
        for c in changes:
            for f in c["files"]:
                if not isinstance(f, str) or not f.strip():
                    raise ValueError(f"changes[].files に空・文字列でない物が在る（{f!r}）")
                out.add(posixpath.normpath(f.strip()))
    return sorted(out)


def changed_problem(declared, touched, excused=None) -> tuple:
    """(ok, 理由)。申告 declared が全部 touched（run の始めから変わったパス）に在れば (True, "")。申告が空でも、直す義務の単位が
    残らず外れた単位だけの置き場（excused。nothing_owed_but_excused の値）なら (True, 外れた単位と理由)。申告が空（上の場合を
    除く）・申告したのに変わっていないファイルが在れば (False, 理由)。元 works/blk-fix/scripts/assert_changed.py の main"""
    import conflict
    if not declared:
        if excused:
            return True, f"{conflict.NOTHING_OWED}: " + "・".join(f"{k}（{why}）" for k, why in sorted(excused.items()))
        return False, NOT_DECLARED
    unchanged = sorted(set(declared) - set(touched))
    if unchanged:
        return False, NOT_CHANGED.format(files=unchanged, moved=sorted(touched)[:10])
    return True, ""


def replan_items(rows, groups=()) -> list:
    """裁定 fix_plan_item が誤りとした計画の項目の id（字。重ねない・現れた順）: conflict.ruled_items（裁定の欄 plan_items）。
    欄の無い行は、その単位を持つ組の項目（groups の items）。rows は conflict の申し出の行"""
    import conflict
    out: list = []
    for r in rows or []:
        if (r.get("ruling") or {}).get("decision") != conflict.REPLAN:
            continue
        nums = conflict.ruled_items(r)
        if not nums:
            nums = [n for g in groups if r.get("unit_key") in g.get("unit_ids", []) for n in g.get("items", [])]
        for n in nums or []:
            if str(n) not in out:
                out.append(str(n))
    return out


def _allowed_row(path, permit, source):
    """許しの訳の 1 行 {path, permit, source}。path と permit が空でない字で source が ALLOWED_SOURCES の語の時だけ（ほかは None）"""
    if isinstance(path, str) and path and isinstance(permit, str) and permit and source in ALLOWED_SOURCES:
        return {"path": path, "permit": permit, "source": source}
    return None


def child_allowed_rows(result) -> list:
    """組の子の結果 result の許しの訳 allowed_tests のうち形の正しい行（_allowed_row）。collect（allowed_test_rows）と
    join の戻しの和が同じ決まりで読む口"""
    given = (result or {}).get("allowed_tests")
    rows = [_allowed_row(r.get("path"), r.get("permit"), r.get("source"))
            for r in (given if isinstance(given, list) else []) if isinstance(r, dict)]
    return [r for r in rows if r]


def allowed_test_rows(place, results=()) -> list:
    """許したテストの変更の訳 [{path, permit, source}]（返りの diff の隣の allowed-tests.json の中身。パスと許しの id の順・重ねない）:
    置き場 place のテストの変更の許し（conflict.test_permits の範囲の在る行。承認済みの修正案の rewrite_tests・files の消す名（change=remove の symbol と op=delete・op=rename の元の .py）・範囲の相談の
    合意・裁定 fix_test_scope）と、範囲の相談の合意の新しいテストのファイル（granted_new_tests）と、組の子の結果の allowed_tests の行。
    permit は許しの id、source は ALLOWED_SOURCES の語。元 works/.shared/core/conflict.py:983 ruled_test_doc（許しの id と理由を
    最後の関所の守りのファイルの行にした）を、パスごとの許しの行で受ける形にした物"""
    import conflict
    rows = []

    def add(row):
        if row and row not in rows:
            rows.append(row)
    for p in conflict.test_permits(place):
        got = conflict.parse_limit(p["limit"]) if "limit" in p else None
        if got:
            add(_allowed_row(got[0], p["id"], p["source"]))
    for r in conflict.agreed(place):
        for g in r.get("granted_new_tests") or []:
            tid = g.get("id") if isinstance(g, dict) else None
            if isinstance(tid, str) and tid:
                add(_allowed_row(tid.partition("::")[0], f"{conflict.AGREED_TEST_ID}-{r.get('item')}", ALLOWED_SOURCES[1]))
    for res in results:
        for row in child_allowed_rows(res):
            add(row)
    return sorted(rows, key=lambda r: (r["path"], r["permit"]))


def allowed_tests(place, results=()) -> list:
    """許したテストの変更のパス（名の順）: 置き場 place と組の子の結果の許しの訳（allowed_test_rows）のパス"""
    return sorted({r["path"] for r in allowed_test_rows(place, results)})


def changed_marks(results) -> dict:
    """修正役の 6 つの印（CHANGED_MARKS）の論理和と、前提のずれの申告の文 DRIFT_NOTE（組の順に改行でつなぐ。同じ文は 1 度。無ければ
    ""。比較役の頭に貼る。元 review-loop.py:1848 の loop.drift_notes）。results は印 changed を持つ dict の並び（組の子の結果・修正役の返答）"""
    marks = [((r or {}).get("changed") or {}) for r in results]
    notes = [str(m.get(DRIFT_NOTE) or "").strip() for m in marks]
    return {**{k: any(m.get(k) is True for m in marks) for k in CHANGED_MARKS},
            DRIFT_NOTE: "\n".join(dict.fromkeys(n for n in notes if n))}


def x_scalars(results) -> dict:
    """修正役が足した規模の数値 x_scalars（x_ で始まる名 → 数）を名ごとに足した物（組ごとの値の和。results は欄 x_scalars を持つ
    dict の並び）。数でない値は足さずに最初の値のまま残す（独立の目が形の外の欄として名指して落とす。eyeverdict.scalars）。
    object でない欄は読まない。無ければ {}（元 review-loop.py:2175 の p3.fix の x_scalars）"""
    out: dict = {}
    for r in results:
        got = (r or {}).get(X_SCALARS)
        for k, v in (got.items() if isinstance(got, dict) else ()):
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            if k not in out:
                out[k] = v
            elif num and isinstance(out[k], (int, float)) and not isinstance(out[k], bool):
                out[k] = out[k] + v
    return out


def objection(results) -> str:
    """修正役の異議（組の子の結果の objection と返答の rejudge_requested）を重ねずにつないだ文。無ければ ""。"""
    out: list = []
    for r in results:
        for v in ((r or {}).get("objection"), (r or {}).get("rejudge_requested")):
            if isinstance(v, str) and v.strip() and v.strip() not in out:
                out.append(v.strip())
    return "\n".join(out)


HANDOFF_HEAD = "修正役が人に回した物（壊すと分かって通した理由 breaks.accepted。役だけで決めた代償なので人が確かめる）"


def handoff_lines(replies) -> list:
    """修正役が人に回した物（1 件 1 行）: 受け付けた返答（replies。dict の並び）の changes[].breaks.accepted（壊すと分かっていて
    通す理由。空白だけの行は除く）。元 works/.shared/core/report.py:304 の handoff_lines（今の周の修正の返答を盤面から読んだ所を
    返答の値で受ける）"""
    out = []
    for reply in replies:
        for c in (reply or {}).get("changes") or [] if isinstance(reply, dict) else []:
            got = (c.get("breaks") or {}).get("accepted") if isinstance(c, dict) and isinstance(c.get("breaks"), dict) else None
            if isinstance(got, str) and got.strip():
                out.append(f"{c.get('unit_key')}: 壊すと分かって通した——{oneline.one_line(got)}")
    return out


def mismatched_lines(place) -> list:
    """置き場 place の閉鎖の表（querytest.save_closure。修正の受け付けが数え直した表）のうち、直したという申告と機械の数え直しが
    合わない単位の行（querytest.closure_lines の mismatched_only）"""
    import querytest
    return querytest.closure_lines(closure_table(place), mismatched_only=True)


def closure_table(place) -> list:
    """置き場 place の閉鎖の表の行（querytest.closure_rows。修正の段の置き場は周 1 つ）"""
    import querytest
    return querytest.closure_rows(types.SimpleNamespace(scope_root=pathlib.Path(place), round=1))


def declared_lines(place) -> list:
    """修正役が直さずに残すと答えた（plan_faces の declared）事前審査の block の 1 件 1 行「key: why（直す側の答え: how）」。問いは
    置き場の事前審査の返答の写し PLAN_REVIEW_FILE の severity block の faces、答えは組の返答の和 FIX_REPLY_FILE（裁定の後の返答
    RULED_REPLY_FILE が同じ key に答えていればそちら）。写しが無ければ []（事前審査の無い run）"""
    p = pathlib.Path(place)
    rv = read_json(p / PLAN_REVIEW_FILE)
    if not isinstance(rv, dict):
        return []
    said = {}
    for name in (FIX_REPLY_FILE, RULED_REPLY_FILE):
        doc = read_json(p / name)
        rows = doc.get("plan_faces") if isinstance(doc, dict) else None
        said.update({r.get("key"): r for r in rows or [] if isinstance(r, dict)})
    out = []
    for f in rv.get("faces") or []:
        a = said.get(f.get("key")) if isinstance(f, dict) and f.get("severity") == "block" else None
        if a is not None and a.get("handled") == "declared":
            out.append(f"{f['key']}: {oneline.one_line(f.get('why') or '')}（直す側の答え: {oneline.one_line(a.get('how') or '')}）")
    return out


def final_lines(results, field: str, more=()) -> list:
    """組の子の結果 results の欄 field（handoffs・mismatched の行の並び）と more を、重ねずに現れた順でつないだ並び"""
    out: list = []
    for line in [*(x for r in results for x in (r or {}).get(field) or []), *more]:
        if isinstance(line, str) and line.strip() and line not in out:
            out.append(line)
    return out


def delta_review(place) -> tuple:
    """({rounds, pass}, 飛ばしたか)。置き場の delta/ の下の審査の控え review-1.json・review-2.json（{pass}）の数と最後の pass。
    審査を飛ばした印 skipped.json（頭も全部の単位も軽量・差分が空で塞いだ穴も無い）が在れば ({rounds: 0, pass: True}, True)。どちらも無ければ審査は走らなかった
    （{rounds: 0, pass: False}）。控えが読めなければ ValueError"""
    d = pathlib.Path(place) / DELTA_DIR
    if (d / DELTA_SKIPPED).is_file():
        return {"rounds": 0, "pass": True}, True
    rounds, passed = 0, False
    for n in (1, 2):
        p = d / DELTA_REVIEW.format(n)
        if not p.is_file():
            break
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not isinstance(doc.get("pass"), bool):
            raise ValueError(f"審査の控え {p} の形が違う（{{pass: bool}}）")
        rounds, passed = n, doc["pass"]
    return {"rounds": rounds, "pass": passed}, False


def run_diff(repo, base: str = "HEAD", skip=()) -> str:
    """版 base から作業ツリーの今の姿（未追跡の新しいファイルも・無視される物を除く。leftovers.snapshot）への累積差分
    （unittrees._DIFF の形）。除くパスの頭 skip の下は載せない。git が落ちれば unittrees.UnitTreeError、
    作業ツリーの姿を取れなければ（読めないファイルなど）leftovers.Unreadable"""
    import leftovers
    import unittrees
    out = unittrees._git(repo, *unittrees._DIFF, base, leftovers.snapshot(repo), "--", *unittrees.pathspec_without(skip))
    return out.stdout.decode("utf-8", "surrogateescape")


def pr_revs(repo, base: str, head: str) -> tuple[str, str]:
    """審査する変更の両端（起点 base・修正前の HEAD head）の commit の名。引けなければ unittrees.UnitTreeError"""
    import unittrees
    base_sha, head_sha = (unittrees._out(repo, "rev-parse", "--verify", f"{rev}^{{commit}}") for rev in (base, head))
    return base_sha, head_sha


def pr_diff(repo, base_sha: str, head_sha: str, skip=(), *opts: str) -> str:
    """審査する変更の差分（起点 base_sha → 修正前の HEAD head_sha。この run の直しの差分 run_diff と分ける側）を git diff の
    形 opts で。除くパスの頭 skip の下は載せない。git が落ちれば unittrees.UnitTreeError"""
    import unittrees
    return unittrees._out(repo, "-c", "core.quotePath=false", *unittrees._DIFF, *opts, base_sha, head_sha, "--",
                          *unittrees.pathspec_without(skip))


def pr_added_lines(repo, base_sha: str, head_sha: str, skip=()) -> dict[str, set[int]]:
    """審査する変更（pr_diff）が足した行 {根からのパス: 修正前の HEAD での行番号}。消しただけのファイルは載せない。
    ファイルの分け方と行番号の数え方は changemap.split_diff・new_side"""
    import changemap
    added: dict[str, set[int]] = {}
    for path, lines in changemap.split_diff(pr_diff(repo, base_sha, head_sha, skip, "-U0"))[0].items():
        for n, ln in changemap.new_side(lines):
            if ln.startswith("+"):
                added.setdefault(path, set()).add(n)
    return added


DIFF_EMPTY = "累積差分は空（{base} から作業ツリーは変わっていない）"


def diff_file(repo, base, place, name: str, none_name: str, skip=()) -> tuple[pathlib.Path, str, str]:
    """(読み手に渡す累積差分のファイル, 差分の本文, 取れなかった訳)。版を引く関数 base の版から run_diff を取って place/name に書く。
    空・版が引けない・git が落ちた時は訳を place/none_name に書き、そのファイルと空の本文（読み手に空の字を渡さない）。取れなかった訳は
    版が引けない・git が落ちた時だけ在り、本当に空の時は空の字（「取れない」と「変化なし」を同じ値にしない）"""
    place = pathlib.Path(place)
    place.mkdir(parents=True, exist_ok=True)
    rev, text, why = "", "", ""
    try:
        rev = base()
        text = run_diff(repo, rev, skip)
    except Exception as e:  # noqa: BLE001  版の読みと git の誤りも訳にして読み手へ渡す
        why = f"累積差分が取れない（{type(e).__name__}: {oneline.one_line(e)}）"
    if text.strip():
        (place / name).write_text(text, encoding="utf-8", errors="surrogateescape")
        return place / name, text, ""
    (place / none_name).write_text((why or DIFF_EMPTY.format(base=rev)) + "\n", encoding="utf-8")
    return place / none_name, "", why


# ---------------------------------------------------------------- 差分の審査・レンズ・手直しの節の口（delta・lens・refix の scripts が呼ぶ）
# 置き場の決まった名（prep が写し、ここが読む）
GROUPS_FILE = "groups.json"            # {groups: [{group_id, …}], out_dir, start_tree, …}（prep の返りと同じ）
TDD_UNIT_FILE = "tdd-unit.json"        # 組ごとの TDD の記録（tdd_units の本文。tdd-unit が書き、返す節が欄 tdd_unit で返して eyes が読む）
ASSERT_FILE = "assert-changed.json"    # 変更の確かめの結果 {ok, reason}（assert-changed が書き、delta-cut・collect が読む）
RESULT_FILE = "result.json"            # 組の子の結果 <out_dir>/<group_id>/result.json（reply_file に受け付けた修正役の返答の写し）
DEPTH_FILE = "depth.json"              # 単位ごとの深さ [{unit_id, depth, why}]（plan の返り depth の写し）
HEAD_DEPTH_FILE = "head-depth.json"    # run の頭の深さの段の語（入力 head_depth の写し。空は標準）
DEPTH_RAISED_FILE = "depth-raised.json"   # 修正の後の信号で上げた深さの控え（depth.raise_doc の形。redepth が書く）
PLAN_REPLY_FILE = "fix-plan-reply.json"   # 修正案の役の返答の写し（入力 fix_plan の先。{"plan": [...]}。承認済みの項目の unit_keys の出どころ）
PLAN_REVIEW_FILE = "p2.plan_review.json"   # 事前審査の返答の写し（faces・shrink。修正役の plan_faces と差分の審査の材料 out.p2.plan_review が読む。
                                           # 修正役の指示書は修正案 PLAN_REPLY_FILE と同じフォルダに在ると書く）
JUDGMENT_FILE = "judgment.json"        # 判定の写し
TIES_FILE = "judge-ties.json"          # 判定の結びの写し（入力 answer_ties の先。answer-ties.json の形）
MATERIALS_FILE = "judge-materials.json"   # 判定の素材の状態の写し（入力 materials の先。materials.json の形）
HEAD_RECORD_FILE = "judge-depth-head.json"   # run の頭の深さの控えの写し（入力 depth_record の先。headdepth.record の形）
JUDGE_COPIES = {"answer_ties": TIES_FILE, "materials": MATERIALS_FILE, "depth_record": HEAD_RECORD_FILE}   # prep が写す入力 → 写しの名
CHECKED_COPIES = (TIES_FILE, MATERIALS_FILE)   # 読み手が壊れた JSON を無いと読むので、写す前に読めるかを確かめる写し
RIPPLE_FILE = "ripple.json"            # 波及の一覧の写し
ANSWERS_FILE = "answers.json"          # 人の関所の答えの写し（承認の節の出力 {decision, text, asked}）
UNITS_FILE = "units.json"              # 入力 units の写し
ONLY_ITEMS_FILE = "only-items.json"    # 直す項目の絞り（入力 only_items。空は全部）
BASELINE_FILE = "baseline.json"        # 直す前の結末 {cases, exit, how}（baseline_red.read_baseline の欄と、走らせ方の行 declared_checks.run_how）
NOTES_FILE = "human-notes.md"          # 修正前の関所の一言と答えで直す義務に戻った単位の行（修正役と TDD の役の notes_file）
BASE_REV_FILE = "base-rev.json"        # 修正前の版 {rev}（prep が親の作業ツリーの HEAD の sha を控え、組の子が写す）
FIX_REPLY_FILE = "fix-reply.json"      # 組ごとの修正役の返答をまとめた物（差分の審査の材料 fix_report と plan_faces）
REFIX_PROMPT = "prompt-{}.md"          # 手直しの役の指示書（節の名 p3.delta_fix・p3.delta_fix2）
LENS_PROMPT = "prompt-lens-{}.md"      # レンズの節の指示書（lenses.key）
LENSES_FILE = "lenses.json"            # レンズの集め役の事実 {collector: {ok, reason}}（返す節が数えを足して欄 lenses で返す。読み手は最後の関所と報告）
LENS_NOT_DONE = "レンズの集め役が終わらなかった: {why}"   # 集め役が落ちた・ok でない時の理由の頭（元 works/blk-lens/lib/lenses.py:130 の exit_）
LENS_NOT_DUE = "差分の審査を回さないのでレンズは起こさない（{why}）"   # delta-cut が go: false の時の理由
# 差分の審査の受け付けが拒む穴の語（元 works/.shared/core/graphloops/rules/review-loop.py:4084-4087）
HUMAN_FACE_KINDS = ("regression", policy.POLICY_KIND)
PLAN_ONLY_FACE_KINDS = HUMAN_FACE_KINDS + ("precedent",)
NONE_MIN = 20   # faces_none の字の下限（元 review-loop.py の blank(…, 20)。表の語はどれもこれより短い）


def write_text(path, text: str) -> pathlib.Path:
    """text を path に置く（一時のファイルから os.replace。フォルダが無ければ作る）"""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def policy_brief(start) -> dict:
    """人の方針 {paste, path}（policy.brief。path は始めの記録の固めた版の写し。空なら両方空）。文書が読めなければ ValueError。
    元 works/.shared/core/policy.py:26（盤面の record.process.policy.copy を読んだ）"""
    import policy
    try:
        return policy.brief(start)
    except OSError as e:
        raise ValueError(f"人の方針の文書 {policy.frozen_copy(start)} が読めない: {e}") from None


def depth_doc(place):
    """置き場の深さの控え（depth.json の [{unit_id, depth, why}]。前の版の控えの形 {units: {…}} も読む）を depth の控えの形
    {units: {key: {depth, why: [...]}}, …} にした物。控えが無ければ None。読めない・形が違えば ValueError"""
    import depth
    path = pathlib.Path(place) / DEPTH_FILE
    doc = read_json(path)
    if isinstance(doc, str):
        try:
            doc = json.loads(doc) if doc.strip() else None
        except ValueError as e:
            raise ValueError(f"深さの控え {path} の中の字が JSON でない: {e}") from None
    if doc is None:
        return None
    if isinstance(doc, list):
        units = {}
        for r in doc:
            if not isinstance(r, dict) or not isinstance(r.get("unit_id"), str) \
                    or r.get("depth") not in (depth.LIGHT, depth.STANDARD):
                raise ValueError(f"深さの控え {path} の行の形が違う（{{unit_id, depth: {depth.LIGHT}|{depth.STANDARD}, why}}）: {r!r}")
            units[r["unit_id"]] = {"depth": r["depth"], "why": [str(r.get("why") or "")]}
        doc = {"units": units}
    if not isinstance(doc, dict) or not isinstance(doc.get("units"), dict):
        raise ValueError(f"深さの控え {path} の形が違う（行の配列か units が要る）")
    return doc


def depth_signals(place) -> tuple:
    """修正の後の深さを標準へ上げる信号 ({単位: 理由}, [run の理由])。単位ごと: 食い違いの申し出の在る単位（conflict.items）・
    受け付けが最後の回に止めた単位（置き場の trace の conflict.ACCEPT_PARKED_OP と、戻せた組の結末 given_up）。run: 答えていない
    修正前の関所の問い（gatemarks.pending）・同じ run の案の直しが走った（置き場の only-items.json が空でない 2 回目の修正）・
    修正役が判定に異議を出した（組の子の結果と裁定の後の返答の objection）・TDD のループで修正役が拒まれた（置き場の tdd-<k>/
    state.json の calls。返す節が欄 tdd_refused で線の redepth へ返すのと同じ読みの fixbeside.tdd_refused）・修正役が範囲の相談をした（受け付けの行
    accept_trace_rows。consult.consulted_units）・修正役が直さずに残すと答えた事前審査の block が在る（declared_lines）。後ろの 3 つの理由の文は
    depth.late_signals が持つ（頭の深さの引用した where の
    外の差分は run の広さと同じく redepth が数える）。控えが読めなければ上げる側へ倒す（TDD の輪の状態は fixbeside.LATE_UNREAD）。
    元 works/darkfactory/lib/depth.py:268 の signals と、線の h-redepth が渡した replanned・rejudged"""
    import conflict
    import consult
    import depth
    import fixbeside
    import gatemarks
    place = pathlib.Path(place)
    units, run = {}, []
    try:
        rows = conflict.items(place)
    except ValueError:
        rows = []
        run.append("食い違いの控えが読めない")
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("unit_key"), str):
            units.setdefault(r["unit_key"], "食い違いの申し出が在る")
    parked = [k for row in conflict.plan_asks(place, conflict.ACCEPT_PARKED_OP) for k in row.get("unit_keys") or []]
    joined = read_json(place / JOIN_FILE, {}) or {}
    parked += [u.get("unit_id") for u in joined.get("units") or [] if isinstance(u, dict) and u.get("status") == GIVEN_UP]
    for k in parked:
        if isinstance(k, str):
            units.setdefault(k, "修正の受け付けが最後の回に止めた")
    run += [f"答えていない問い {q.get('key')}" for q in gatemarks.pending(gate_view(place)) if isinstance(q, dict)]
    if read_json(place / ONLY_ITEMS_FILE, []):
        run.append("同じ run の案の直しが走った")
    plan = read_json(place / GROUPS_FILE, {}) or {}
    back = [g.get("group_id") for g in joined.get("groups") or [] if isinstance(g, dict) and g.get("returned")]
    results = [read_json(pathlib.Path(plan["out_dir"]) / gid / RESULT_FILE) for gid in back if plan.get("out_dir")]
    results = [r for r in results if isinstance(r, dict)]
    if objection(results + [read_json(place / RULED_REPLY_FILE)]):
        run.append("修正役が判定に異議を出した")
    unread = []
    refused = fixbeside.tdd_refused(place, unread)
    run += depth.late_signals(refused=refused, consulted=consult.consulted_units(accept_trace_rows(place, results)),
                              declared=declared_lines(place))
    run += [fixbeside.LATE_UNREAD.format(why=why) for why in unread]
    return units, run


def redepth(place, repo, skip=()) -> str:
    """修正の後の信号で深さを標準へ上げ（depth.raise_doc）、上げた控えを置き場の DEPTH_RAISED_FILE に書き、全部の単位が軽量のまま
    で run の頭の深さの段（置き場の HEAD_DEPTH_FILE）が省く物を持てば、差分の審査を省く理由の文（depth.skip_reason）を返す。
    控えが無い・標準の単位が在る・単位が無い・頭の深さが省かない段なら空。信号は
    depth_signals、run 全体の広さ（depth.run_wide）は修正の実際の差分（run の始めの木 start_tree から今の作業ツリーへの変更。
    除くパスの頭 skip の下は数えない）と承認済みの修正案の欄で数え直し、数えたファイルの数と起点を控えの counted に 1 行残す。
    同じ差分のうち、置き場の頭の深さの控えの写し（HEAD_DEPTH_FILE でなく HEAD_RECORD_FILE。prep が入力 depth_record の先から写す）の引用した where の
    ファイルの外に出たパスは depth.outside_cited が拾い、理由は depth.late_signals（テストのファイルは run_wide と同じ除きで数えない。
    控えが無い・where の無い run は外を持たない）。
    控えが読めない・形が違えば ValueError。元 works/darkfactory/lib/depth.py:302 の raise_（線の h-redepth）"""
    import depth
    import headdepth
    import planmarks
    import writes
    doc = depth_doc(place)
    if doc is None:
        return ""
    units, run = depth_signals(place)
    items = planmarks.read(marks_view(place))
    tree = start_tree(place)
    touched = [f for f in writes.changed_from(repo, tree) if not f.startswith(tuple(skip))] if tree else []
    origin = f"修正の差分 {tree[:12]}" if tree else "計画の allowed_paths（修正の差分の起点が無い）"
    wide, paths = depth.run_wide(items, doc["units"], touched)
    run += wide
    run += depth.late_signals(outside=depth.outside_cited(items, doc["units"], touched, headdepth.cited_files(headdepth.read_file(pathlib.Path(place) / HEAD_RECORD_FILE))))
    doc["counted"] = f"触るファイル {paths} 個（起点: {origin}）"
    doc = depth.raise_doc(doc, units=units, run=run)
    write_json(pathlib.Path(place) / DEPTH_RAISED_FILE, doc)
    return depth.skip_reason(doc, read_json(pathlib.Path(place) / HEAD_DEPTH_FILE))


def delta_review_due(place, repo, skip=(), fix_reply=None) -> tuple:
    """1 回目の差分の審査を起こすか (起こすか, 訳)。修正の差分（修正前の版 base_rev_of から今の作業ツリーへの累積差分。除くパスの頭
    skip の下は数えない。run_diff）が空でないか、検算すべき『塞いだ』と言われた穴（claimed_closed の 1 回目。fix_reply は値か
    そのパス）が在れば起こす。差分の無い申告を誰も検算しない形を作らない。git が落ちれば unittrees.UnitTreeError。
    元 works/.shared/core/graphloops/rules/review-loop.py:604 の fix_delta_nonempty と :617 の delta_review_due"""
    rev = base_rev_of(place)
    if run_diff(repo, rev, skip).strip():
        return True, f"修正の差分が在る（起点 {rev[:12]}）"
    k = len(claimed_closed(place, 1, fix_reply))
    if k:
        return True, f"修正の差分は空だが、修正が塞いだと言う事前審査の穴が {k} 件在る（検算する）"
    return False, (f"差分が空で、塞いだと言われた穴も無いので差分の審査を起こさない（修正前の版 {rev[:12]} から作業ツリーは"
                   "変わっていない。修正が塞いだと言う事前審査の穴は 0 件）")


def place_items(place):
    """置き場の承認済みの修正案の項目（planmarks.approved_items。修正案の役の返答の写し PLAN_REPLY_FILE と判定の写し judgment.json
    を plan_view で渡し、凍結の欄 plan-fields.json と凍結の印は置き場から）。どれか無ければ None。凍結の印と食い違えば
    planmarks.FieldsBroken。承認済みの項目を置き場から読む口はここ 1 つで、修正の段（群の組み立て prep・修正役の指示書・
    受け付け・事前の確かめ factchecks.main）と手直しの段（refix.cut・accept_review・accept_fix・prep_fix）が同じ物を items に口（引数なし）として渡す"""
    import planmarks
    p = pathlib.Path(place)
    return planmarks.approved_items(plan_view(p, read_json(p / PLAN_REPLY_FILE), read_json(p / JUDGMENT_FILE)))


def start_tree(place) -> str:
    """run の始めの木（差分の審査の起点）: 置き場の groups.json の start_tree、無ければ控え fix-ignored-before.json の head_tree
    （leftovers.head_tree）。どちらも無ければ空"""
    import leftovers
    doc = read_json(pathlib.Path(place) / GROUPS_FILE)
    got = doc.get("start_tree") if isinstance(doc, dict) else ""
    if isinstance(got, str) and got:
        return got
    try:
        return leftovers.head_tree(place)
    except leftovers.Unreadable:
        return ""


def group_fix_reply(place):
    """組の子が受け付けた修正役の返答（groups.json の out_dir/<group_id>/result.json の reply_file）を組の順に 1 つにまとめた
    {changes, not_done, plan_faces}（差分の審査の材料 fix_report と out.p3.fix.plan_faces）を置き場の fix-reply.json に書き、
    そのパスを返す。どの組にも返答が無ければ None。結果・返答が無い・読めない組は飛ばす（子が落ちた run は組の節が落ちて join まで来ない）。
    元 works/.shared/core/refix.py:362 の _fix_report が盤面の 1 つの p3.fix を読んだ所を、組ごとの返答の和で受ける"""
    p = pathlib.Path(place)
    doc = read_json(p / GROUPS_FILE)
    if not isinstance(doc, dict):
        return None
    out_dir = pathlib.Path(str(doc.get("out_dir") or p / "groups"))
    merged, found = {"changes": [], "not_done": [], "plan_faces": []}, False
    for g in doc.get("groups") or []:
        gid = g.get("group_id") if isinstance(g, dict) else None
        if not isinstance(gid, str) or not gid:
            continue
        try:
            res = read_json(out_dir / gid / RESULT_FILE)
            reply = read_json(res.get("reply_file")) if isinstance(res, dict) and res.get("reply_file") else None
        except ValueError:
            continue
        if not isinstance(reply, dict):
            continue
        found = True
        for k in merged:
            merged[k] += [r for r in reply.get(k) or [] if isinstance(r, dict)]
    return write_json(p / FIX_REPLY_FILE, merged) if found else None


def _keys_once(rows, label) -> list:
    """行の key が重複しないか（重複の文の一覧）。元 works/.shared/core/graphloops/rules/review-loop.py:3067"""
    seen, errs = set(), []
    for i, r in enumerate(rows):
        k = r.get("key") if isinstance(r, dict) else None
        if k in seen:
            errs.append(f"{label}[{i}] の key が重複: {str(k)[:60]}")
        seen.add(k)
    return errs


def plan_review_file(place):
    """置き場の事前審査の返答の写し PLAN_REVIEW_FILE のパス（差分の審査の材料 out.p2.plan_review。無ければ None＝事前審査の無い run）"""
    p = pathlib.Path(place) / PLAN_REVIEW_FILE
    return p if p.is_file() else None


TESTS_HOW_HEAD = promptsection.Section("## 直す前のテストの走らせ方（直す前のテストの段が実際に走らせた形。機械が貼った）",
                                       source="fn:fixboard.tests_how_text")


def tests_how_text(place) -> str:
    """修正役と TDD の役の指示書に貼る節（TESTS_HOW_HEAD）: 置き場の BASELINE_FILE の走らせ方の行。行が無ければ空（直す前のテストの
    無い run と、行を持たない前の版の控え）"""
    rows = (read_json(pathlib.Path(place) / BASELINE_FILE, {}) or {}).get("how")
    lines = [f"- {r}" for r in rows or [] if isinstance(r, str) and r]
    if not lines:
        return ""
    return "\n".join([TESTS_HOW_HEAD, "", "テストを回す時は、環境や命令を探さずにこの形で回せ（絞り方は下の決まりのとおり）。", *lines])


FACES_HEAD = promptsection.Section("## 事前審査に答える key（受け付けが plan_faces で答えを求める全部）",
                                   source="fn:fixboard.plan_faces_text")


def face_units(pass_: str, duty):
    """事前審査の key を問う単位（plan_face_rows の units）: 組の子の受け付け（pass_ first）は直す義務の単位 duty、裁定の後は
    None（周の全体の欄を書く）。受け付けと修正役の指示書が同じ単位で引く"""
    return set(duty) if pass_ == "first" else None


def plan_face_rows(place, units) -> list[tuple[str, dict]] | None:
    """修正役が答える事前審査の行 [("faces" | "shrink", 行)]（ファイルの順、faces が先）: 置き場の事前審査の返答の写し
    PLAN_REVIEW_FILE の行のうち、unit_keys が units（face_units）に当たる行と unit_keys の無い行（units が None なら全部の行）。
    写しが無ければ None（事前審査の無い run）。受け付け（plan_face_errors）と指示書（plan_faces_text）の 1 か所"""
    rv = read_json(pathlib.Path(place) / PLAN_REVIEW_FILE)
    if not isinstance(rv, dict):
        return None
    return [(kind, r) for kind in ("faces", "shrink") for r in rv.get(kind) or [] if isinstance(r, dict)
            and (units is None or not r.get("unit_keys") or set(units) & set(r.get("unit_keys") or []))]


def plan_faces_text(place, units) -> str:
    """修正役の指示書に貼る節（FACES_HEAD）: plan_face_rows の key の全部を字のまま、要旨 1 行と並べる。行が無ければ空"""
    lines = []
    for kind, r in plan_face_rows(place, units) or []:
        if kind == "faces":
            tag = "・".join(str(x) for x in ("穴", r.get("severity"), r.get("kind")) if x)
            gist = r.get("why")
        else:
            tag, gist = "別案", r.get("alternative")
        lines.append(f"- `{r.get('key')}`（{tag}）: {oneline.one_line(gist or '')}")
    if not lines:
        return ""
    return "\n".join([FACES_HEAD, "", "下の key の全部に、返答の `plan_faces` で 1 つにつき 1 行ずつ答えろ（key は一字も変えずに写す。"
                      "この一覧に無い key は書くな）。", "", *lines])


def plan_face_errors(place, reply, units) -> list:
    """修正役は事前審査の穴（faces）と別案（shrink）に key ごとに 1 度だけ答える（absorbed＝取り込んだ／declared＝残す理由）。
    問う key は plan_face_rows(place, units) の行の key。返答の plan_faces の重複・問いに無い key・答えの無い key を 1 行ずつ。写しが
    無ければ空（事前審査の無い run）。
    元 works/.shared/core/graphloops/rules/review-loop.py:3115 の _plan_face_errors（1 つの p3.fix が全部に答えた。組に分けた修正役は
    自分の単位の穴に答える）"""
    rows = plan_face_rows(place, units)
    if rows is None:
        return []
    asked = {r.get("key") for _, r in rows}
    answered = [r for r in (reply or {}).get("plan_faces") or [] if isinstance(r, dict)]
    errs = _keys_once(answered, "plan_faces")
    errs += [f"plan_faces の key '{str(r.get('key'))[:40]}' は事前審査に無い" for r in answered if r.get("key") not in asked]
    errs += [f"事前審査の '{str(k)[:40]}' に応答が無い——absorbed（どう取り込んだか）か declared（残す理由）で答えろ"
             for k in sorted(asked - {r.get("key") for r in answered}, key=str)]
    return errs


def claimed_closed(place, n: int, fix_reply=None) -> set:
    """n 回目の差分の審査が検算する『塞いだ』と言われた穴の key: 1 回目は修正役が plan_faces で absorbed と答えた事前審査の穴
    （fix_reply。値かそのパス）、2 回目は 1 回目の手直しが fixed と答えた穴（置き場の受けた返答）。
    元 works/.shared/core/graphloops/rules/review-loop.py:3129・3135（_closed_keys・_claimed_closed）"""
    import refix
    if n == 1:
        rows, word = (_given(fix_reply) or {}).get("plan_faces"), "absorbed"
    else:
        rows, word = (output(place, refix._pass(n - 1)["fix"]) or {}).get("handled"), "fixed"
    return {r.get("key") for r in rows or [] if isinstance(r, dict) and r.get("handled") == word}


def delta_review_problems(place, n: int, reply: dict, repo, *, fix_reply=None) -> list:
    """n 回目の差分の審査の返答の照らし（拒む行の並び。空なら通る）: 穴の key は一意、kind は事前審査だけの語でない、where は
    この往復の差分が触ったファイル（置き場の loop-<state_key>.json の files）、cite はそのファイルの今の姿に在る字列、穴が無いなら
    faces_none（NONE_MIN 字以上）。検算 checks は『塞いだ』と言われた穴（claimed_closed）に 1 件ずつ、余り・欠け・重複なし。
    元 works/.shared/core/graphloops/rules/review-loop.py:3141 の delta_review_output（盤面の写しの規則。拒否は Reject で投げた）"""
    import refix
    _gl = str(pathlib.Path(__file__).resolve().parent / "graphloops")
    if _gl not in __import__("sys").path:
        __import__("sys").path.insert(0, _gl)
    from engine.util import READ_CAP, read_capped
    d = loop_value(place, refix._pass(n)["state_key"]) or {}
    files, root = set(d.get("files") or []), pathlib.Path(repo)
    faces = [f for f in reply.get("faces") or [] if isinstance(f, dict)]
    errs = _keys_once(faces, "faces")
    for i, f in enumerate(faces):
        kind, where, cite = f.get("kind"), str(f.get("where") or ""), str(f.get("cite") or "")
        if kind in HUMAN_FACE_KINDS:
            errs.append(f"faces[{i}] の kind '{kind}' は事前審査だけの語——修正の後の後退・方針とのぶつかりは後の段が人に聞く")
            continue
        if kind in PLAN_ONLY_FACE_KINDS:
            errs.append(f"faces[{i}] の kind '{kind}' は事前審査だけの語——判定者の先行例はこのノードに渡っていない")
            continue
        if where not in files:
            errs.append(f"faces[{i}] の where '{where[:60]}' はこの往復の差分が触ったファイルでない（{sorted(files)[:5]}）")
            continue
        data, _ = read_capped(str(root / where), READ_CAP)
        if data is None or not cite or cite.encode("utf-8") not in data:
            errs.append(f"faces[{i}] の cite '{cite[:40]}' が {where} の今の姿に無い——在る字列を写せ")
    if not faces and len(str(reply.get("faces_none") or "").strip()) < NONE_MIN:
        errs.append("穴を挙げないなら faces_none に何を読んで無いと言えるかを書け")
    claimed, checks = claimed_closed(place, n, fix_reply), [c for c in reply.get("checks") or [] if isinstance(c, dict)]
    errs += _keys_once(checks, "checks")
    errs += [f"checks の key '{str(c.get('key'))[:40]}' は塞いだと言われた穴に無い" for c in checks if c.get("key") not in claimed]
    errs += [f"塞いだと言われた穴 '{str(k)[:40]}' に検算が無い——差分で塞がったか（closed）を 1 件ずつ書け"
             for k in sorted(claimed - {c.get("key") for c in checks}, key=str)]
    return errs


def delta_fix_problems(place, n: int, reply: dict) -> list:
    """n 回目の手直しの返答の照らし（拒む行の並び）: 義務（_owed_rows）の key ごとに 1 度だけ答え、余り・欠けが無く、fixed には
    files が在る。元 works/.shared/core/graphloops/rules/review-loop.py:3174 の delta_fix_output"""
    asked = {r["key"] for r in _owed_rows(place, n)}
    rows = [r for r in reply.get("handled") or [] if isinstance(r, dict)]
    errs = _keys_once(rows, "handled")
    errs += [f"handled の key '{str(r.get('key'))[:40]}' は修正差分の審査に無い" for r in rows if r.get("key") not in asked]
    errs += [f"穴 '{k[:40]}' に応答が無い" for k in sorted(asked - {r.get("key") for r in rows})]
    errs += [f"handled '{str(r.get('key'))[:40]}' は fixed なのに files が空" for r in rows
             if r.get("handled") == "fixed" and not r.get("files")]
    return errs


def lens_route(place, lang: str = "") -> dict:
    """レンズの振り分け: 前の試みの控えを消し、置き場の 1 回目の差分（refix.fix_delta）の変わったファイルでレンズごとに起こすかを
    決め（lenses.LENSES の route）、起こすレンズは利用者が入れた役の定義の本文（engine.validator.agent_def）から指示書を組んで
    置き場の prompt-lens-<key>.md に書く。定義が引けなければ起こさない理由を残す。行を lens.json に書き（lens.write_routes）、
    {レンズの名: {go, reason, prompt_file}} を返す。差分が無ければ ValueError。
    元 works/blk-lens/lib/lenses.py:81 の route（盤面の今の周の差分と inputs を読み、出口の欄を <key>_go にした）"""
    import lens
    import lenses
    import refix
    from engine.validator import agent_def   # refix の import が写しの engine を sys.path に足した後
    p = pathlib.Path(place)
    (p / lens.LENS_FILE).unlink(missing_ok=True)   # 前の試みの控えを次の集め役に読ませない
    d = refix.fix_delta(p)
    if not d or not d.get("file"):
        raise ValueError("置き場に修正の差分（loop-fix_delta.json）が無い（差分の審査の支度が走っていない）")
    files = list(d.get("files") or [])
    out, rows = {}, []
    for row in lenses.LENSES:
        go, why = row["route"](files)
        prompt = ""
        if go:
            try:
                got = agent_def(row["agent"])
            except (Exception, SystemExit) as e:   # engine の探しが出所の曖昧さで止まる（die）時も、起こさない理由にする
                got, why = None, f"{row['agent']} の定義を引けない（{type(e).__name__}: {oneline.one_line(e)}）"
            if got is None or not got.get("body"):
                go = False
                why = why or f"{row['agent']} の定義が役の設定に無い（pr-review-toolkit が入っていない）"
            else:
                prompt = str(write_text(p / LENS_PROMPT.format(lenses.key(row)),
                                         lenses.render(row, got["body"], d["file"], files, lang)))
        rows.append({"lens": row["lens"], "agent": row["agent"], "go": go, "reason": why})
        out[row["lens"]] = {"go": go, "reason": why, "prompt_file": prompt}
    lens.write_routes(p, rows)
    return out


def lens_collector(place, ok: bool, reason: str = "") -> pathlib.Path:
    """レンズの集め役の事実を置き場の LENSES_FILE に {collector: {ok, reason}} で書く（集め役が落ちた・ok でない時は ok: false と
    理由。集め役は書いてから落ち、run は止まる。元 works/blk-lens/lib/lenses.py:126 の exit_ は盤面を止めた）"""
    return write_json(pathlib.Path(place) / LENSES_FILE, {"collector": {"ok": bool(ok), "reason": str(reason or "")}})


def brief_lens(place, n: int = 1) -> pathlib.Path:
    """n 回目の審査役の材料 review<n>-brief.json の lens の欄を、置き場の lens.json の今の行（lens.brief_rows）で書き直す
    （支度 refix.cut はレンズより先に走るので、集めた後に足す）。控えが読めなければ lens_error を足す。材料が無ければ ValueError"""
    import lens
    path = pathlib.Path(place) / f"review{n}-brief.json"
    doc = read_json(path)
    if not isinstance(doc, dict):
        raise ValueError(f"審査役の材料 {path} が無い（差分の審査の支度が走っていない）")
    doc.pop("lens_error", None)
    try:
        doc["lens"] = lens.brief_rows(place)
    except ValueError as e:
        doc["lens"], doc["lens_error"] = [], str(e)
    return write_json(path, doc)


def prep_fix(place, n: int, *, items=None, plan_review=None, fix_reply=None, policy=None) -> dict:
    """n 回目の手直しの役を起こす前の支度。義務（_owed_rows）が無ければ {ok: False, reason}。在れば前の試みの材料を消し、義務と
    差分のパス・読ませる値（_brief）・人の方針・穴ごとの枝の名札（refix.brief_ties。組めなければ理由を置いて先へ）を
    refix<n>-brief.json に書き、{ok: True, owed, diff_file, brief_file} を返す。1 回目は scope_brief の欄（plan_items・ruled_paths・
    agreed。凍結の印との食い違いは手直しの段の印 stopby.REFIX の ValueError）と審査の準拠の落ちた行 compliance も載せる。元
    works/.shared/core/refix.py:248 の prep_fix（盤面の待ち・起こした印・指示書を外した。指示書は refix_prompt）"""
    import deltamarks
    import refix
    import stopby
    p = refix._pass(n)
    rows = _owed_rows(place, n)
    if not rows:
        return {"ok": False, "reason": f"置き場に {n} 回目の審査の義務が無い（{p['review']} の受けた返答に穴も塞がっていない検算も無い）"}
    d = loop_value(place, p["state_key"]) or {}
    brief_name = f"refix{n}-brief.json"
    (pathlib.Path(place) / brief_name).unlink(missing_ok=True)
    values = {f"loop.{p['owed_key']}": {"rows": rows}, f"loop.{p['state_key']}": d}
    doc = {"node": p["fix"], "diff_file": d.get("file") or "", "owed": rows, "reads": _brief(p["fix"], values),
           "policy": _given(policy) or {"paste": "", "path": ""}}
    try:   # 穴ごとの枝の名札（材料だけで、答え方は変えない。組めなければ理由を置いて手直しは起こす）
        doc["ties"] = refix.brief_ties(hole_ties(place, n, items=items, plan_review=plan_review, fix_reply=fix_reply))
    except Exception as e:
        doc["ties"], doc["ties_error"] = [], f"{type(e).__name__}: {oneline.one_line(e)}"
    if n == 1:
        doc.update(scope_brief(place, items, by=stopby.REFIX))
        doc["compliance"] = deltamarks.fail_rows(deltamarks.read(place))
    brief = write_json(pathlib.Path(place) / brief_name, doc)
    return {"ok": True, "owed": len(rows), "diff_file": doc["diff_file"], "brief_file": str(brief)}


def refix_prompt(n: int, values: dict, *, reject_file: str = "", iteration: int = 1, lang: str = "", scope: str = "") -> str:
    """n 回目の手直しの役の指示書（純粋）: 始めの記録の 2 行（fixrules.start_lines。values の policy_path と request_file。修正役と
    TDD の役の指示書と同じ）→ 役の頭（refix-head-<n>。values の brief_file・diff_file・policy_path で穴を埋める）→
    書く役の決まりの正本（rulebook.CANON の NOT_HERE の外）→ 読み替え → 手直しだけの決まり → 返答 → 返答の後に当たる物
    （refix-tail-<n>）を rulebook.render で繋ぐ。手直しだけの決まりの後に借りたスキルの座（seat.section。receiving-code-review と
    読み替え）を置く。reject_file（この輪の拒否の理由の全部のファイル。rolekit.reject_file）が在れば 1 行目で名指す。決まりのファイルの置き場は refixrules.RULES と
    rulebook.CANON（呼び手が置き替える）。scope（受け付けが照らす範囲の節。refix.scope_text）が在れば始めの記録の 2 行の後に貼る。
    写しが固定と違えば seat の ValueError。
    元 works/blk-refix/lib/refixrules.py:36・52 の parts・build"""
    import fixrules
    import refixrules
    import rulebook
    import seat
    if n not in refixrules.ROLES:
        raise rulebook.Unfilled(f"手直しの往復 {n!r} は {sorted(refixrules.ROLES)} のどれでもない")
    r = rulebook.sections(refixrules.RULES)
    always = refixrules.ALWAYS
    canon = [(sid, text, always + "（書く役の決まりの正本）") for sid, text in rulebook.sections(rulebook.CANON).items()
             if sid not in refixrules.NOT_HERE]
    parts = [("refix-head", rulebook.fill(r[f"refix-head-{n}"], rulebook.pick(values, refixrules.VALUES)), always + "（役・材料・run の値）"),
             *canon,
             ("refix-remap", r["refix-remap"], always + "（この役での読み替え）"),
             ("refix-keep", r["refix-keep"], always + "（手直しだけの決まり）"),
             ("seat", seat.section(refixrules.ROLES[n]), always + "（座）"),
             ("refix-reply", r["refix-reply"], always + "（返答の欄）"),
             ("refix-tail", r[f"refix-tail-{n}"], always + "（返答の後に当たる物）")]
    return rulebook.render(refixrules.ROLES[n], iteration, parts, before=[*fixrules.start_lines(values), *([scope] if scope else [])],
                           reject_file=reject_file, lang=lang)["text"]


def accept_out(place, name: str, got: dict) -> dict:
    """受け付けの返り {ok, done, reason, reason_file}（輪の until が done を読む）。got の ok が真なら done。偽なら rolekit.accept_round で
    控え rejects-<name>.json に積み、rolekit.GIVE_UP_AFTER 回目の拒否で done（諦め。ok は偽のまま）。got の count が false の回は積まず、
    give_up が真なら 1 回目でも done。reason_file はこの輪の拒否の全部のファイル（rolekit.reject_file。控えが扱えない時は空）。
    拒否の控え rejects-<name>.json が読めない・書けない時は、落ちずに done 真の拒否（理由『拒否の控えが扱えない』）。
    rejects-<name>.md が書けない時は reject_file_or_blank の OSError がそのまま上がる。
    元 works/.shared/core/rolekit.py の main_accept の 3 回目の拒否で done・give_up の振る舞い（今の住処は rolekit.accept_round）"""
    if got.get("ok") is True:
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    reason = str(got.get("reason") or "受け付けが理由を書かずに拒んだ")
    out = rolekit.accept_round(place, name, None, lambda _: {**got, "reason": reason})
    return {"ok": False, "done": bool(out["done"]), "reason": out["reason"], "reason_file": rolekit.reject_file_or_blank(place, name)}


def round_number(place, name: str) -> tuple:
    """rolekit.current_round を accept_out の返りの形で: (回, None) か、控えが読めなければ (0, reason_file の空な done 真の拒否)"""
    n, stopped = rolekit.current_round(place, name)
    return n, stopped and {**stopped, "reason_file": ""}


# ---------------------------------------------------------------- 組を親の木へ当てた後の名指しのテストの照らし（fix の join の script が呼ぶ）

def _bodies(text, rel: str) -> dict:
    """ファイルの中身 text（None は無いファイル）の test 関数の id（tddloop._id_base）→ 源（tddloop.test_functions）。
    元 works/blk-fix/lib/tddlanes.py:641（単位の worktree のファイルを読んだ所を中身で受ける）"""
    import tddloop
    if text is None:
        return {}
    return {tddloop._id_base(i): body for i, body in tddloop.test_functions(text, rel).items()}


def test_file(f) -> str | None:
    """TDD の輪の単位の test_files の要素の決まり: 空でない文字列を posixpath.normpath で整えたパス（ほかは None）。書き手
    tddloop の確かめ（要素が 1 つでも外れれば並びごと拒む）と読み手 unit_test_files（外れた要素を落とす）がここから引く"""
    return posixpath.normpath(f.strip()) if isinstance(f, str) and f.strip() else None


def unit_test_files(unit) -> list:
    """TDD の輪の単位の行の test_files のうち、決まり（test_file）に合う要素だけを整えた並び（子の result.json の写しも読む口。
    並びでない test_files は空、形の違う要素は落とす）"""
    files = (unit or {}).get("test_files")
    if not isinstance(files, list):
        return []
    return [p for p in map(test_file, files) if p]


def _moved_tests(repo, tree: str, units, shared: set) -> list:
    """重なりのファイル shared（前に当てた組の差分とも重なるパス）に在る名指しのテストのうち、関数の源が組の子の終わりの木 tree と
    親の作業ツリー repo で違う・消えた物。units は TDD の輪の単位の行（tests・test_files）。元 works/blk-fix/lib/tddlanes.py:629
    （単位の worktree のファイルを読んだ所を、子の終わりの木の中身 tddloop._tree_text で読む）"""
    import tddloop
    out = []
    for u in units:
        for f in sorted(set(unit_test_files(u)) & set(shared)):
            mine = _bodies(tddloop._tree_text(repo, tree, f), f)
            p = pathlib.Path(repo) / f
            now = _bodies(p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None, f)
            out += [t for t in u.get("tests") or [] if tddloop._norm_id(t).startswith(f + "::")
                    and (mine.get(tddloop._id_base(t)) is None or mine.get(tddloop._id_base(t)) != now.get(tddloop._id_base(t)))]
    return out


def tests_moved(repo, tree: str, units, shared) -> str:
    """当てた後の名指しのテストの中身が子の終わりの木と違う時の戻す理由（_moved_tests。無ければ空）。元 works/blk-fix/lib/tddlanes.py:620
    の tests_moved（lanekit.merge の check）"""
    moved = _moved_tests(repo, tree, units, set(shared))
    return f"当てた後の名指しのテストの中身が組の子の終わりの木と違う（{moved[:5]}）" if moved else ""


# ---------------------------------------------------------------- 形 group の子の run（group-start・tdd-loop・group-end の scripts が呼ぶ）
# 子が親の置き場から自分の置き場に写す入力の写し（prep が書く物。plan-fields.json と凍結の印は adopt_inputs が別に置き直す）
ADOPTED = (startrec.REL, JUDGMENT_FILE, TIES_FILE, MATERIALS_FILE, PLAN_REPLY_FILE, PLAN_REVIEW_FILE, RIPPLE_FILE, DEPTH_FILE, HEAD_DEPTH_FILE,
           ANSWERS_FILE, UNITS_FILE, ONLY_ITEMS_FILE, BASELINE_FILE, BASE_REV_FILE, NOTES_FILE)
FIX_UNITS_FILE = "fix-units.json"        # 修正の輪の単位ごとの結末 {unit_key: {status, reason}}（fix-accept が書く）
ALLOWED_TESTS_FILE = "allowed-tests.json"   # 許したテストの変更の訳 [{path, permit, source}]（collect が書き、欄 allowed_tests で返す。allowed_test_rows）
ALLOWED_SOURCES = ("plan", "consult", "ruling")   # ALLOWED_TESTS_FILE の source の語: 承認済みの修正案・範囲の相談の合意・裁定
GROUP_START_FILE = "group-start.json"   # 組の子の始めの記録 {group, from_tree, out_dir, start_tree}（group-start が組の置き場に書く）
ADOPTED_FROM = "adopted_from"           # 親の置き場に写した TDD の輪の状態の、写し元の子の状態のパスの欄（adopt_tdd_states）
PRIOR_LOOP = "prior_pass"               # 2 回目の修正の段の置き場に写した 1 回目の段の輪の状態の印（adopt_prior_pass。新しい）
UNIT_STATUSES = (FIXED, GIVEN_UP, NOT_DONE) = ("fixed", "given_up", "not_done")
UNIT_LEFT = (GIVEN_UP, NOT_DONE)   # 直し終えなかった単位の状態
NO_UNIT_RESULT = "修正のループがこの単位の結末を残さなかった"


def adopt_inputs(parent, place, repo=None) -> list:
    """組の子の置き場 place に、親の置き場 parent の入力の写し（ADOPTED のうち在る物）を写し、凍結した修正案の欄
    （plan-fields.json）は親の凍結の印で確かめてから planmarks.save で置き直す（子の trace に印を書く）。2 回目の修正の段の親が
    adopt_prior_pass で置いた 1 回目の段の申し出と裁定（conflict.FILE）も写し、repo（子の作業ツリー）を渡せば 1 回目の段の輪の状態
    （PRIOR_LOOP の印つき）も子の輪の前の輪として写す（子の受け付けの凍結・事後の関門・機械の諦めが 1 回目の段を見る）。写した名の
    並びを返す。親の欄の控えが印と食い違えば conflict.frozen_fields の ValueError。新しい（元に無い。今の works は 1 つの盤面を枝が
    共に読んだ）"""
    import conflict
    import planmarks
    src, dst = pathlib.Path(parent), pathlib.Path(place)
    if not src.is_dir():
        raise ValueError(f"親の置き場 {src} が無い")
    out = []
    for name in ADOPTED:
        p = src / name
        if p.is_file():
            q = dst / name
            q.parent.mkdir(parents=True, exist_ok=True)
            tmp = q.with_name(q.name + ".tmp")
            tmp.write_bytes(p.read_bytes())
            os.replace(tmp, q)
            out.append(name)
    if (src / conflict.FILE).is_file() and not (dst / conflict.FILE).is_file():
        write_text(dst / conflict.FILE, (src / conflict.FILE).read_text(encoding="utf-8"))
        out.append(conflict.FILE)
    if repo is not None:
        import tddloop
        prior = [str(p) for p in tddloop.states(src) if read_json(p, {}).get(PRIOR_LOOP)]
        out += adopt_tdd_states(dst, [{"tdd_state": p} for p in prior], repo, prior=True)
    if conflict.frozen_fields(src, 1) is not None:
        doc = read_json(marks_path(src))
        amended = doc.get(planmarks.AMENDED_KEY) if isinstance(doc, dict) else None
        planmarks.save(dst, 1, doc["fields"], {int(n): c for n, c in amended.items()} if isinstance(amended, dict) else None)
        out.append(marks_path(src).name)
    return out


def adopt_prior_pass(place, prior, items, repo) -> dict:
    """2 回目の修正の段（同じブロックの 2 度目の差し込み。置き場が分かれる）の置き場 place に、1 回目の段の置き場 prior（入力
    prior_conflicts の指し札の先のフォルダ）の申し出と裁定（conflict.adopt_prior。直す項目 items の待つ行は AMENDED）と TDD の輪の
    状態（印 PRIOR_LOOP つき。実行器は作業ツリー repo で解き直す）を写す。元は 1 つの盤面に両方の段が在り、conflict.second_pass・
    輪をまたぐ凍結（factchecks.check_frozen）・2 回目の機械の諦め（conflict.park_claims）・事後の関門（fixgates）が 1 回目の段を見た
    （元 works/.shared/core/conflict.py:411・works/blk-fix/lib/fixgates.py:103・works/blk-fix/lib/tddloop.py:1816）。
    返り {rows: 写した行の id, loops: 写した状態のパス}。新しい"""
    import conflict
    import tddloop
    rows = conflict.adopt_prior(place, prior, items)
    loops = adopt_tdd_states(place, [{"tdd_state": str(p)} for p in tddloop.states(prior)], repo, prior=True)
    return {"rows": rows, "loops": loops}


def marks_path(place) -> pathlib.Path:
    """置き場の凍結した修正案の欄の控え（plan-fields.json）のパス"""
    import marks
    return marks.path_of("plan", pathlib.Path(place))


def unit_depths(place) -> str:
    """置き場の深さの控え depth.json（[{unit_id, depth, why}]）を tddloop.start の unit_depths の形（{"<単位の key>": 深さの語} の
    JSON の字）に。控えが無い・run の頭の深さの段（置き場の HEAD_DEPTH_FILE）が省く物を持たなければ ""（単位の軽量が test_cmd を
    省くのは軽量の頭の run だけ。depth.omits）。形が違えば ValueError"""
    import depth
    doc = read_json(pathlib.Path(place) / DEPTH_FILE)
    if doc is None or not depth.omits(read_json(pathlib.Path(place) / HEAD_DEPTH_FILE)):
        return ""
    if not isinstance(doc, list) or not all(isinstance(r, dict) for r in doc):
        raise ValueError(f"深さの控え {DEPTH_FILE} が行の配列でない")
    return json.dumps({str(r["unit_id"]): str(r["depth"]) for r in doc if r.get("unit_id") and r.get("depth")},
                      ensure_ascii=False)


def verified_tests(tdd) -> list:
    """TDD の輪の出口の欄 tdd（tddloop.exit_fields の形）のうち、赤 → 緑を機械が確かめた名指し（route が tdd で green が ok の
    単位の tests。重ねない・現れた順）。join が親の木で走らせ直す"""
    out: list = []
    for u in (tdd or {}).get("units") or []:
        if isinstance(u, dict) and u.get("route") == "tdd" and u.get("green") == "ok":
            out += [t for t in u.get("tests") or [] if isinstance(t, str) and t and t not in out]
    return out


def _unit_row(key, fix_units, tdd_rows) -> dict:
    """組の結果の単位の行: 修正の輪の結末（fix_units）、無ければ TDD の輪で諦めた・止めた単位は given_up、ほかは not_done"""
    got = fix_units.get(key) if isinstance(fix_units, dict) else None
    if isinstance(got, dict) and got.get("status") in UNIT_STATUSES:
        return {"unit_id": key, "status": got["status"], "reason": str(got.get("reason") or "")}
    t = tdd_rows.get(key) or {}
    if t.get("gave_up") or t.get("route") == "parked":
        return {"unit_id": key, "status": GIVEN_UP,
                "reason": str(t.get("why") or "") or f"TDD のループで諦めた（{t.get('gave_up')}）"}
    return {"unit_id": key, "status": NOT_DONE, "reason": NO_UNIT_RESULT}


def group_result(group, *, start_tree: str, end_tree: str, tdd, tdd_state: str = "", fix_units=None, reply=None,
                 reply_file: str = "", allowed_rows=(), conflicts=(), worktree: str = "", mismatched=(),
                 accept_trace=(), closure=(), place: str = "") -> dict:
    """組の子の結果（out_dir/<group_id>/result.json の中身。join・collect・tdd-unit・conflict-check が読む）:
    {group_id, unit_ids, end_tree, start_tree, units: [{unit_id, status, reason}], tdd, conflicts, objection, changed, x_scalars,
    allowed_tests, verified, reply_file, tdd_state, worktree, handoffs, mismatched, accept_trace, closure,
    claimed, place}。allowed_rows は許しの訳（allowed_test_rows の行）、handoffs は reply の handoff_lines、mismatched は子の置き場の
    mismatched_lines（最後の関所を開ける理由）、accept_trace は子の置き場の accept_trace_rows の行（group_id を足す。親の collect が
    diff の隣に集める）、closure は子の置き場の閉鎖の表の行（表を読めなければ None。fixbeside.closure_rows）と claimed は reply の
    changes の単位（親の collect が diff の隣の fixbeside.CLOSURE_FILE に合わせる）。worktree は子の作業ツリーの実パス（join がその書き込みの記録を親の記録へ写す。
    writes.carry_children）。place は子の run の置き場（読み手は 2 つ: 親の conflict-check がこの組の申し出の名指しに許す根と、join の
    fixboard.adopt_returned（consult.carry_agreed）がここから範囲の相談の合意を親の置き場へ写す）。group は {group_id, unit_ids}、tdd は tddloop.exit_fields の形、
    tdd_state は子の TDD の輪の状態のファイル（輪の無い組は空。join が親の置き場に写す。adopt_tdd_states）、fix_units は
    修正の輪の単位の結末 {unit_key: {status, reason}}、reply は最後に受け付けた修正役の返答（印 CHANGED_MARKS と rejudge_requested
    を持つ。無ければ None）、allowed_tests は reply の在る組（修正の輪の受け付けが通った組）だけ allowed_rows の行（無い組は []。join の和と親の collect の
    allowed-tests.json・allowed_test_changes が同じ 1 つの欄から読む。受け付けの行は accept_trace に残る）、conflicts は
    置き場の申し出の行（conflict.items）。新しい"""
    import fixbeside
    gid = str(group["group_id"])
    keys = [str(k) for k in group.get("unit_ids") or []]
    tdd = tdd if isinstance(tdd, dict) else {"ran": False, "suite": "", "reason": "", "units": []}
    rows = {u.get("unit_key"): u for u in tdd.get("units") or [] if isinstance(u, dict)}
    reply = reply if isinstance(reply, dict) else None
    permits = [r for r in allowed_rows or [] if isinstance(r, dict)] if reply is not None else []
    return {"group_id": gid, "unit_ids": keys, "end_tree": end_tree, "start_tree": start_tree,
            "units": [_unit_row(k, fix_units or {}, rows) for k in keys], "tdd": tdd,
            "conflicts": [r for r in conflicts or [] if isinstance(r, dict)],
            "objection": objection([reply] if reply else []),
            "changed": changed_marks([{"changed": reply}] if reply else []), X_SCALARS: x_scalars([reply] if reply else []),
            "allowed_tests": permits,
            "verified": verified_tests(tdd), "reply_file": str(reply_file or ""), "tdd_state": str(tdd_state or ""),
            "worktree": str(worktree or ""), "handoffs": handoff_lines([reply] if reply else []),
            "mismatched": list(mismatched),
            "accept_trace": [{**r, "group_id": gid} for r in accept_trace or [] if isinstance(r, dict)],
            "closure": None if closure is None else [r for r in closure if isinstance(r, dict)],
            "claimed": fixbeside.claimed_of(reply), "place": str(place or "")}


def adopt_tdd_states(place, results, repo, *, prior: bool = False) -> list:
    """戻せた組の子の結果 results（組の順）が名指す TDD の輪の状態（tdd_state）を、親の置き場 place の次の tdd-<k>/ に写す
    （state.json の work を写した先に、exe を親の作業ツリー repo で解き直した実行器に替え、輪の要約 summary.md も写す。
    並べた子の exe は子の作業ツリーの中を指し、自分の置き場から根を引く実行器だと親の試験を子の木で走らせるため）。写した状態は tddloop.states(place) に run の全部の輪として
    載り、裁定の後の修正の受け付けが凍結・範囲・変更に当たる試験に使う（ruled_states）。もう写した子の状態（状態の
    ADOPTED_FROM）は写し直さない。prior が真なら写した状態に印 PRIOR_LOOP を置く（1 回目の修正の段の輪。ruled_states が今の段の輪から
    外す）。写した状態のパスを返す。新しい（元は 1 つの盤面に輪の状態が在った）"""
    import tddloop
    place = pathlib.Path(place)
    have = {str(read_json(p, {}).get(ADOPTED_FROM) or "") for p in tddloop.states(place)}
    out = []
    for r in results:
        src = str((r or {}).get("tdd_state") or "")
        if not src or src in have or not pathlib.Path(src).is_file():
            continue
        k = 1
        while (place / f"tdd-{k}").exists():
            k += 1
        dst = place / f"tdd-{k}"
        st = read_json(pathlib.Path(src))
        write_json(dst / tddloop.STATE, {**st, "work": str(dst), "exe": str(tddloop.exe_path(repo, st["suite"])),
                                         ADOPTED_FROM: src, **({PRIOR_LOOP: True} if prior else {})})
        summary = pathlib.Path(src).parent / tddloop.SUMMARY
        if summary.is_file():
            write_text(dst / tddloop.SUMMARY, summary.read_text(encoding="utf-8"))
        out.append(str(dst / tddloop.STATE))
    return out


def adopt_returned(place, repo, results, *, log=None, applied=()) -> None:
    """戻せた組の子の結果 results（組の順）から、親の置き場 place・親の作業ツリー repo へ写す物の全部の 1 つの口（join と
    clash.settle_repaired が呼ぶ）: 子の書き込みの記録（log が在り is_file なら writes.carry_children(log, repo, applied)。applied は
    [(子の作業ツリー, 子の記録のファイル, 当てたパスの並び)]）→ TDD の輪の状態（adopt_tdd_states）→ 範囲の相談の合意
    （consult.carry_agreed。group_id つきで親の trace へ。親の範囲とテストの許しにだけ効く）"""
    import consult
    import writes
    if log is not None and pathlib.Path(log).is_file():
        writes.carry_children(log, repo, applied)
    adopt_tdd_states(place, results, repo)
    consult.carry_agreed(place, results)


def ruled_states(place) -> tuple:
    """裁定の後の修正の受け付けに渡す (今の輪の状態, 変更に当たる試験の輪の状態)。1 回目の段の輪（PRIOR_LOOP）は数えない（凍結の検査は
    前の輪として見る。factchecks.check_frozen）。置き場の輪（adopt_tdd_states が写した組ごとの輪）が
    1 つならそれを今の輪に（元の 1 つの輪の run と同じ）。幾つも在れば今の輪は無し（どの輪も同じ段に並んで走ったので、凍結は全部の輪を
    輪の後の木で見る。factchecks.check_frozen）、試験は最後の輪の実行器で走らせる。無ければ ("", "")"""
    import tddloop
    loops = [str(p) for p in tddloop.states(place) if not read_json(p, {}).get(PRIOR_LOOP)]
    if len(loops) == 1:
        return loops[0], loops[0]
    return "", loops[-1] if loops else ""


def group_dir(place, out_dir: str, gid: str) -> pathlib.Path:
    """組の子の結果と始めの記録の置き場 <out_dir>/<group_id>/（out_dir が空の単独の run は自分の置き場の groups/ の下）"""
    return pathlib.Path(out_dir or pathlib.Path(place) / "groups") / str(gid)


def usable_result(gdir):
    """組の子が使える結果を残したかの 1 つの決まり。gdir の RESULT_FILE が JSON の dict で end_tree が文字列なら（group_result が
    書く形）その dict、無い・読めない・形が違えば None。壊れた結果は結果の無いのと同じに扱う。結果が None で始めの記録
    （GROUP_START_FILE）が在る組は止まった組、始めの記録も無い組は始まっていない組（始めの記録より前に親の木を変えないので、
    戻す物が無い）"""
    doc = jsonfile.read_or(pathlib.Path(gdir) / RESULT_FILE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("end_tree"), str) else None


def halted_groups(out_dir, own: str) -> list:
    """並べない run で、out_dir の下の own 以外の組のうち、子が始めた（GROUP_START_FILE が在る）のに使える結果（usable_result）を
    残さずに止まった組の名を並べる"""
    return [g.name for g in sorted(pathlib.Path(out_dir).glob("*"))
            if g.is_dir() and g.name != own and (g / GROUP_START_FILE).is_file() and usable_result(g) is None]


def drop_unreturned(repo, gdir, skip=()) -> list:
    """並べない run（組の子が親の作業ツリーで直す）で、子が使える結果（usable_result）を残さずに落ちた組の変更を、子の始めの木
    （gdir の GROUP_START_FILE の start_tree）に戻し、戻したパス（除くパスの頭 skip の下は数えない）を返す。使える結果の在る組・
    始めの記録の無い組は何もしない（[]）。新しい（元は枝ごとの worktree で直したので、落ちた枝の直しは親の木に届かなかった）"""
    import tddloop
    gdir = pathlib.Path(gdir)
    if usable_result(gdir) is not None:
        return []
    began = read_json(gdir / GROUP_START_FILE)
    tree = began.get("start_tree") if isinstance(began, dict) else None
    if not isinstance(tree, str) or not tree:
        return []
    paths = touched_since(repo, tree, skip)
    tddloop.restore_paths(repo, tree, paths)
    return paths


# ---------------------------------------------------------------- 修正役の受け付けと範囲の相談（fix-accept・fix-ruled-accept・
# consult-check・fix-ruled-prep の scripts が呼ぶ）。元 works/blk-fix/scripts/accept.py の受け付けの手順と、元
# works/blk-fix/lib/consult.py:522 の頼みの節を、盤面の代わりに置き場のパスと値の引数で受ける形に書き直した物
RULED_REPLY_FILE = "fix-ruled-reply.json"   # 裁定の後の修正役の受け付けた返答（fix-ruled-accept が書き、assert-changed・collect が読む）
RULED_HEAD_FILE = "fix-ruled-head.json"     # 裁定の後の修正の段の頭の木 {tree}（fix-ruled-prep が 1 回目に書く）
FIX_HEAD_FILE = "fix-head.json"             # 組の修正の段の頭の木 {tree}（TDD の輪の後。fix-prep が 1 回目に書く）
REFIX_HEAD_FILE = "refix{}-head.json"       # n 回目の手直しの段の頭の木 {tree}（refix-prep・refix2-prep が 1 回目に書く）
PARKED_PATCH = "fix-parked"                 # 最後の回に止めた単位の戻した直しの控え（置き場の fix-parked-<n>.patch。元 accept.py:168）
FIX_ACCEPT_BY = "fix-accept"                # 受け付けが単位を人に回した裁定の by（元 accept.py:140 の stopby の名）
# 修正の受け付けの確かめの id → 拒否の見出しの短い名（受け付けが回す順）。元 works/blk-fix/scripts/accept.py:180
FIX_CHECKS = {
    "consult": "範囲の相談の枠",
    "frozen": "TDD のループで凍ったテストのファイル",
    "writes": "書き込みの出どころ",
    "conflict": "食い違いの申し出の形",
    "pack": "除くパスの頭の下の変更",
    "duplicate": "同じ unit_key の重なり",
    "not_opened": "今の周に直す単位に無い unit_key",
    "excused": "直す義務から外れた単位",
    "scope": "承認済みの修正案の範囲",
    "tests": "変更に当たる試験の赤",
    "gates": "事後の関門の束",
    "closure": "閉じない欠陥の数え",
    "copy": "数え直しの受け付け",
    "plan_faces": "修正案の事前審査への応答",
}
# 閉じない欠陥の数え（check closure）の文。remaining では抜けず、直すか申し出るかを求める（#313）
UNCLOSED_DEFECTS = ("単位 {key} の欠陥を数える問い（判定者の問いか、裁定が置き換えた問い）が、修正前 {total} 件・修正後 {after} 件"
                    "で閉じていない。remaining を書いても閉じない。次のどれかで出し直せ: 残った当たりも欠陥なら直して 0 件に"
                    "する / 問いが直した後の正しい行に当たるなら conflicts に {kind}: {hits}・{which}: {query}・"
                    "{correct}（その正しい行の写し）で申し出る / 範囲の中では閉じないなら conflicts に {kind}: {scope} で"
                    "申し出る")
UNCOUNTED_DEFECTS = ("単位 {key} の欠陥を数える問い（判定者の問いか、裁定が置き換えた問い）を修正後に数えられず、閉じたと確かめ"
                     "られない: {why}。その問いが数えられる木にして出し直せ")
FIX_REJECT_HEAD = ("受け付けは確かめを全部回した。見出しごとに並べた行を全部直した返答を丸ごと出し直せ（直した所だけを返すな。"
                   "1 回の出し直しで全部を直せ）:")   # 元 accept.py:195
FIX_CHECK_HEAD = "## {head}（確かめ {cid}・{count} 件）"   # 元 works/blk-fix/lib/fixlanes.py:449
DUPLICATE = "同じ unit_key を 2 行以上に分けた（直した単位ごとにちょうど 1 行。1 つの単位が複数のファイルに及ぶなら files に並べよ）: "
NOT_OPENED = ("今の周に直す単位に無い unit_key を changes に書いた（開いた単位と、承認ノードで答えた問いの出どころ・depends のほかは直さない。"
              "単位を切り直さず、貼られた単位の no か key で指せ。判定への異議は rejudge_requested に書く）: ")
EXCUSED = ("直す義務から外れた単位を changes に書いた（答えが届くまで・人が決めるまで直さない。changes から外し、not_done に"
           "理由を書け）: ")
CONFLICT_BAD = "食い違いの申し出を受けない（名指した所が現物に無いか、形が違う。直して丸ごと出し直せ）: "
JUDGE_UNREAD = f"置き場の判定の写し {JUDGMENT_FILE} が読めない（{{why}}）——判定者の問いを correct_lines に当てて試せない"
SECOND_CONFLICT = ("裁定の後の出し直しで新しく申し出た食い違い——裁定のループは 1 周に 1 回だけなので、機械が人に回した"
                   "（最後の承認ノードで人が決める）")
CONSULT_SPENT = ("範囲の相談の枠（この段のループで {n} 回）を使い切った後の consult を受けない。consult の欄を外し、範囲の中で直すか、"
                 "変えずに食い違いの申し出（kind は scope_needed）で返せ")
CONSULTED = "範囲の相談の周（返答の consult に答えの役が答えた）。受け付けは回さず、次の周の修正役が答えを読んで続けた返答を受け付ける"
BOUND_PARKED = ("修正のループの最後の回も、この単位に結んだ拒否が残った（文がこの単位か、その足跡・届く試験を名指す。どの単位にも"
                "結べない拒否は直す義務の全部の単位に結ぶ）。返答全体を拒む代わりに、機械がこの単位の直しを段の頭の木に"
                "戻して控えの patch に移し、人に回し、ほかの単位の直しを受けた。拒否の文: ")
GAVE_UP = "修正のループの {n} 回目の拒否で諦めた（直しは段の頭の木に戻し、控え {patch} に移した）: {why}"
NOT_SETTLED = "修正のループの最後の回に、止める単位が残らないのに拒否が残った（受けずに諦めた）: "
ABSORBED_OP = "fix_excused_dropped"   # 最後の回に、義務の外の単位の行を changes から外した・数えなかった拒否の文の trace の行（元 accept.py:158）
PACK_COPY = ("修正役は除くパスの頭 {skip} の下を変えてはいけない（実行基盤の置き場で、この run を動かしているグラフの写しが在りうる。"
             "写しは次の run が作り直す）: ")   # 元 accept.py:175 の PACK_COPY（頭の字は呼び手が渡す）
SKIP_BEFORE_FILE = "skip-before.json"   # 修正の段の頭の、除くパスの頭の下の姿 {パス: 中身の sha256}（fix-prep・fix-ruled-prep が 1 回目に書く）
PARKED_FOR_RULING = "食い違いの申し出を裁定へ回した（直す裁定なら裁定の後の修正役が受け付け直し、人に回れば人が決める）"
FIX_IN_DIFF_CORE = "直しは差分に在り、閉じたかの数え（判定者の問いが直した後の正しい行にも当たる）だけ"   # query_hits_fixed は直してから申し出る（common.md）。conflict.FIX_IN_DIFF も組む
QUERY_PARKED = f"{FIX_IN_DIFF_CORE}を裁定へ回した（問いが置き換われば裁定の後の修正役が受け付け直し、人に回れば人が決める）"
UNDECLARED = ("書き込みの記録が無い run で、作業ツリーの変更が返答の changes[].files にも bash_writes にも無い——直したファイルなら "
              "changes の files に足し、Bash で書いたなら bash_writes にパスと理由を書き、要らない変更なら戻せ: ")
NOT_IN_REPLY = "修正役の返答がこの単位を changes に書かなかった"
RULED_REPLY_LINE = ("1 回目の修正役の返答（機械が保存した物）: {path}——先に Read で全部読め。あなたは新しい会話なので、前の直しと"
                    "申し出はこのファイルと裁定のファイルで知れ（作業ツリーの直しはそのまま在る）")
CONSULT_HEAD = ("あなたは修正案を書いた役の続きとして答える（新しい会話）。修正案のファイル {plan} を先に Read で全部読み、"
                "あなたが書いた修正案として扱え。{ripple}")
RIPPLE_READ = "波及の一覧 {path} も読め（範囲に入っていない当たりを名指す）。"


def group_owed(place, unit_ids=None) -> list:
    """直す義務の単位の key の並び（判定の順）: 置き場の判定の写し・始めの記録の依頼の answers・修正前の関所の答え・判定の結びと
    素材の状態の写しから数えた直す義務（gate_view を gatemarks.duty に通した物。plan の 1 回目の周の必ず入れる単位と同じ口）。
    unit_ids（組の単位）を渡せばその中だけを、渡した順（組の中の依存の順）で返す（判定の順でなく）。判定の写しが無ければ ValueError。
    新しい（元は盤面の写しの規則の _owed_units と gatemarks の盤面の読みが run の全部を読んだ）"""
    import gatemarks
    judgment = read_json(pathlib.Path(place) / JUDGMENT_FILE)
    if not isinstance(judgment, dict):
        raise ValueError(f"置き場に判定の写し {JUDGMENT_FILE} が無い（{place}）")
    keys = _in_order(judgment, gatemarks.duty(gate_view(place)))
    if unit_ids is None:
        return keys
    have = set(keys)
    return [k for k in dict.fromkeys(str(u) for u in unit_ids) if k in have]


def check_unique_units(keys: list) -> list:
    """2 度以上現れる unit_key（現れた順）。元 works/blk-fix/scripts/accept.py:258"""
    seen, dup = set(), []
    for k in keys:
        if k in seen and k not in dup:
            dup.append(k)
        seen.add(k)
    return dup


def check_opened_units(keys: list, opened: set) -> list:
    """直す義務にもそこから外れた単位にも無い unit_key（現れた順・重なりは 1 つ）。元 works/blk-fix/scripts/accept.py:268"""
    return list(dict.fromkeys(k for k in keys if k not in opened))


def check_excused_units(keys: list, owed: set, excused: dict) -> dict:
    """直す義務から外れた単位の unit_key と理由 {key: 理由}（現れた順）。元 works/blk-fix/scripts/accept.py:297"""
    return {k: excused[k] for k in keys if k not in owed and k in excused}


def skip_digests(repo, skip) -> dict:
    """repo の除くパスの頭 skip の下の全部のファイルの {根からの相対パス: 中身の sha256}（symlink は辿らず "link:<先>"。
    __pycache__/ の下と .pyc は数えない。git の追跡・無視に依らない。無ければ空）。元 works/.shared/core/leftovers.py:110
    の姿の関数（工程の写しの置き場の頭を引数に）"""
    import hashlib
    repo = pathlib.Path(repo)
    out = {}
    for head in skip:
        top = repo / head.rstrip("/")
        if top.is_symlink():
            out[head.rstrip("/")] = "link:" + os.readlink(top)
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            here = pathlib.Path(dirpath)
            for name in filenames + [d for d in dirnames if (here / d).is_symlink()]:
                p = here / name
                rel = p.relative_to(repo).as_posix()
                if "/__pycache__/" in f"/{rel}" or rel.endswith(".pyc"):
                    continue
                out[rel] = "link:" + os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def record_skipped(place, repo, skip) -> pathlib.Path:
    """修正の段の頭の、除くパスの頭 skip の下の姿（skip_digests）を置き場の SKIP_BEFORE_FILE に控える（check_pack_copy が読む）。
    元は修正役の前の控え（leftovers.record_ignored）の欄の 1 つ（元 works/.shared/core/leftovers.py:134）"""
    return write_json(pathlib.Path(place) / SKIP_BEFORE_FILE, skip_digests(repo, skip))


def check_pack_copy(reply: dict, place, repo, skip) -> str:
    """除くパスの頭 skip の下を changes[].files に申告した・修正の段の頭の控え（record_skipped。無ければ申告だけを見る）から
    その下の中身が変わった・足した・消した返答を拒む文（通れば空。skip が空なら照らさない）。元 works/blk-fix/scripts/accept.py:234"""
    import parking
    if not skip:
        return ""
    declared = set()
    for c in reply.get("changes") or []:
        for f in (c.get("files") if isinstance(c, dict) else None) or []:
            if isinstance(f, str) and f.strip():
                f = parking._rel(f, repo)
                if not parking._ours(f, tuple(skip)):
                    declared.add(f)
    before = read_json(pathlib.Path(place) / SKIP_BEFORE_FILE)
    now = skip_digests(repo, skip) if isinstance(before, dict) else {}
    changed = sorted(k for k in set(before or {}) | set(now) if before.get(k) != now.get(k)) if isinstance(before, dict) else []
    parts = []
    if declared:
        parts.append(f"changes[].files に申告した {sorted(declared)}（申告から外す）")
    if changed:
        parts.append(f"修正の段の頭の控えから変わった {changed[:20]}（元の姿に戻してから出し直す: 追跡している物は "
                     "git checkout -- <パス>、足した物は消す）")
    return PACK_COPY.format(skip="・".join(skip)) + " / ".join(parts) if parts else ""


def fix_reject_rows(found: list) -> list:
    """積んだ行 (確かめの id, 文) を FIX_CHECKS の順に並べ、同じ行を 1 つにした列。元 works/blk-fix/scripts/accept.py:209"""
    seen = dict.fromkeys(found)
    return [row for check in FIX_CHECKS for row in seen if row[0] == check]


def fix_reject_text(found: list) -> str:
    """拒否の本文: FIX_REJECT_HEAD の後に、行の在る確かめごとに見出しと行 `  - <文>`。元 works/blk-fix/scripts/accept.py:215"""
    rows = fix_reject_rows(found)
    lines = [FIX_REJECT_HEAD]
    for check, head in FIX_CHECKS.items():
        texts = [t for c, t in rows if c == check]
        if texts:
            lines.append(FIX_CHECK_HEAD.format(head=head, cid=check, count=len(texts)))
            lines += ["  - " + t.replace("\n", "\n    ") for t in texts]
    return "\n".join(lines)


def undeclared_writes(reply: dict, repo, tree: str, *, made=(), skip=()) -> list:
    """書き込みの記録が無い run の書き込みの出どころ（U6 の狭め）: 木 tree（段の頭の木）から作業ツリーの今の姿で変わったパス
    （touched_since。除くパスの頭 skip の下は数えない）のうち、返答の changes[].files にも bash_writes の path にも無く、実行器が
    作った物（made）でもない物を名指す拒否の文（無ければ空の並び）。新しい（今の works は包みの書き込みの記録で縛った）"""
    import factchecks
    rows = [c for c in (reply or {}).get("changes") or [] if isinstance(c, dict)]
    told = factchecks.declared_files(rows, repo)
    told |= factchecks.declared_files([{"files": [w.get("path") for w in (reply or {}).get("bash_writes") or []
                                                  if isinstance(w, dict)]}], repo)
    left = [p for p in touched_since(repo, tree, skip) if p not in told and p not in set(made)]
    return [UNDECLARED + ", ".join(left)] if left else []


def undeclared_refix(reply: dict, repo, tree: str, *, skip=()) -> list:
    """手直しの役の返答（handled[].files と bash_writes で申告する）の書き込みの出どころ: undeclared_writes と同じ照らしを、
    handled の files を申告として当てる。新しい（U6 の狭め。今の works は包みの書き込みの記録で縛った）"""
    rows = [{"files": h.get("files") or []} for h in (reply or {}).get("handled") or [] if isinstance(h, dict)]
    return undeclared_writes({"changes": rows, "bash_writes": (reply or {}).get("bash_writes") or []}, repo, tree, skip=skip)


def reply_marks(reply, before=None) -> dict:
    """返答 reply に、修正役の 6 つの印（CHANGED_MARKS）を前の控え before（同じ形の dict か None）の印と論理和で重ね、異議
    rejudge_requested と前提のずれの申告の文 DRIFT_NOTE を前の物とつないだ dict（fix-reply.json・fix-ruled-reply.json の中身）"""
    out = dict(reply or {})
    prev = before if isinstance(before, dict) else {}
    for k in CHANGED_MARKS:
        out[k] = out.get(k) is True or prev.get(k) is True
    asks = [v.strip() for v in (prev.get("rejudge_requested"), out.get("rejudge_requested"))
            if isinstance(v, str) and v.strip()]
    if asks:
        out["rejudge_requested"] = "\n".join(dict.fromkeys(asks))
    notes = [str(v).strip() for v in (prev.get(DRIFT_NOTE), out.get(DRIFT_NOTE)) if isinstance(v, str) and v.strip()]
    out[DRIFT_NOTE] = "\n".join(dict.fromkeys(notes))
    out["changed"] = {**{k: out[k] for k in CHANGED_MARKS}, DRIFT_NOTE: out[DRIFT_NOTE]}
    return out


def unit_outcomes(owed, reply, *, excused=None, parked=None, conflicted=None) -> dict:
    """単位ごとの結末 {key: {status, reason}}（fix-units.json の中身）: 止めた単位（parked {key: 理由}）は given_up、受けた返答の
    changes の単位は fixed、裁定へ回した単位（conflicted {key: 理由}。parked_reasons）と changes に無い直す義務の単位・外れた単位
    （excused {key: 理由}）は not_done（理由は返答の not_done の why か外れた理由）"""
    out = {}
    conflicted = conflicted or {}
    why = {r.get("unit_key"): r.get("why") for r in (reply or {}).get("not_done") or [] if isinstance(r, dict)}
    done = {c.get("unit_key") for c in (reply or {}).get("changes") or [] if isinstance(c, dict)}
    for k in [*owed, *(excused or {}), *conflicted]:
        if k in done:
            out[k] = {"status": FIXED, "reason": ""}
        elif k in conflicted:
            out[k] = {"status": NOT_DONE, "reason": conflicted[k]}
        else:
            out[k] = {"status": NOT_DONE, "reason": str(why.get(k) or (excused or {}).get(k) or NOT_IN_REPLY)}
    for k, texts in (parked or {}).items():
        out[k] = {"status": GIVEN_UP, "reason": texts if isinstance(texts, str) else " / ".join(texts)}
    return out


def parked_reasons(place, keys) -> dict:
    """裁定へ回した周の単位 keys の結末の理由 {key: 理由}: 裁かれていない申し出から選んだ直しの在りか（conflict.fix_place）が
    差分に在る単位は QUERY_PARKED、ほかは PARKED_FOR_RULING"""
    import conflict
    rows = conflict.unruled(place)
    return {k: QUERY_PARKED if (mine := conflict.unit_rows(rows, k)) and conflict.fix_place(mine) == conflict.IN_DIFF
            else PARKED_FOR_RULING for k in keys}


def judge_query(place):
    """食い違いの申し出の確かめ（conflict.problems_by_entry）の try_query: 置き場の判定の写し judgment.json の units から
    querytest.judge_hits を組む（TDD の輪の道 tdd-step と同じ。裁定 replace_query が置き換えた単位は置き換えた問いを当てる）。写しが無い・読めない・dict でなければ、query の申し出ごとに
    JUDGE_UNREAD の文を返す口（読めないと名指して拒む。黙って試さずに通さない。元は盤面の判定 b.record["units"] を引き、
    無ければ落ちた）"""
    import conflict
    import querytest
    try:
        judgment = read_json(pathlib.Path(place) / JUDGMENT_FILE)
        why = "" if isinstance(judgment, dict) else ("無い" if judgment is None else "dict でない")
    except ValueError as e:
        judgment, why = None, str(e)
    if why:
        return lambda key, lines: JUDGE_UNREAD.format(why=why)
    return querytest.judge_hits(judgment.get("units") or [], conflict.replaced_queries(place))


def take_conflicts(reply: dict, place, repo, pass_: str, owed) -> tuple:
    """食い違いの申し出（欄 conflicts）を外した返答と、拒否の結果か止めた印。返り (返答, 結果 | None)。元
    works/blk-fix/scripts/accept.py:306（盤面の代わりに置き場 place、直す義務は値 owed で受ける）:
    - 裁定がもう外した単位（conflict.held_by_rulings）の申し出は先に外す
    - 申し出は機械が確かめ（conflict.problems_by_entry）、外れれば {ok: False, reason, lines: [(key|None, 文)]}。which_is_right:
      query の申し出は置き場の判定の写し judgment.json の単位の class_query を correct_lines に当てて試す（judge_query。元
      accept.py:325-326 の try_query=querytest.judge_hits(b.record["units"])）
    - first: 通った申し出を置き場の conflicts.json に積み、裁かれていない申し出が在れば（TDD の輪の分も）
      {ok: True, parked: True, units: [申し出た単位]}（返答は conflict.PARKED_REPLY に控える）
    - ruled: 裁定の後の新しい申し出は機械が ask_human に裁いて積む"""
    import conflict
    import planbrief
    reply = dict(reply)
    items = reply.pop("conflicts", None) or []
    if isinstance(items, list) and items:
        known = conflict.held_by_rulings(place)
        items = [i for i in items if not (isinstance(i, dict) and i.get("unit_key") in known)]
    owed = owed_units_but_asked(place, owed)
    if items:
        entries = conflict.problems_by_entry(items, repo=repo, board_dir=place, owed=owed, try_query=judge_query(place),
                                             briefs=planbrief.by_unit_at(place))
        lines = [(key, CONFLICT_BAD + " / ".join(texts)) for _, key, texts in entries if key and texts] \
            + [(None, CONFLICT_BAD + t) for _, key, texts in entries if not key for t in texts]
        both = sorted({i.get("unit_key") for i in items if isinstance(i, dict)}
                      & {c.get("unit_key") for c in reply.get("changes") or [] if isinstance(c, dict)})
        bad = [t for _, _, texts in entries for t in texts]
        if both:
            bad.append(f"申し出た単位を changes にも書いた: {both}（申し出た単位は直さない）")
            lines += [(k if k in owed else None, f"{CONFLICT_BAD}申し出た単位を changes にも書いた: {k}（申し出た単位は直さない）")
                      for k in both]
        if bad:
            return reply, {"ok": False, "reason": CONFLICT_BAD + " / ".join(bad), "lines": lines}
        if pass_ == "first":
            conflict.park(place, items, source=conflict.FIX_SOURCE)
        else:
            conflict.park(place, items, source=conflict.FIX_SOURCE, pass_=pass_,
                          ruling={"decision": conflict.ASK, "text": SECOND_CONFLICT, "limits": [], "by": FIX_ACCEPT_BY})
            conflict.write_rulings(place)
    if pass_ == "first" and conflict.unruled(place):
        write_json(pathlib.Path(place) / conflict.PARKED_REPLY, {**reply, "conflicts": items})
        return reply, {"ok": True, "parked": True, "reason": "",
                       "units": sorted({i.get("unit_key") for i in items if isinstance(i, dict)})}
    return reply, None


def keep_patch(place, repo, files, head: str) -> str:
    """段の頭の木 head から今の作業ツリー（未追跡の新しいファイルも）への files の差分を置き場の fix-parked-<n>.patch に控え、
    そのパスを返す。元 works/blk-fix/scripts/accept.py:402（leftovers.head_tree を引数 head に）"""
    import leftovers
    files = sorted(files)
    n = 1
    while (pathlib.Path(place) / f"{PARKED_PATCH}-{n}.patch").exists():
        n += 1
    patch = pathlib.Path(place) / f"{PARKED_PATCH}-{n}.patch"
    now = leftovers.snapshot(repo)
    patch.write_bytes(leftovers.git(repo, "diff", "--binary", "--no-renames", head, now, "--", *files, text=False)
                      if files else b"")
    return str(patch)


def revert_units(place, repo, files, head: str) -> str:
    """止めた単位の足跡 files を段の頭の木 head に戻す（先に keep_patch で控える）。返りは控えのパス。元
    works/blk-fix/scripts/accept.py:417"""
    import tddloop
    patch = keep_patch(place, repo, files, head)
    tddloop.restore_paths(repo, head, sorted(files))
    return patch


def last_settle(texts: list, rows: list, place, repo, rev: str, state: str, owed, excused: dict, parked=frozenset(), *,
                declared=None, skip=()):
    """輪の最後の回の拒否の文 texts を単位に結ぶ（parking.settle）。返り (Settlement, 義務の外の単位の集合, 足跡)。足跡は返答の行 rows と
    今の段の輪の状態 state（空なら置き場の全部の輪 tddloop.states。裁定の後の段は組ごとの輪を join が写した物）、届く試験は単位ごとの impact の地図（置き場の impact/ に控える）、義務の外は外れた単位 excused と
    もう止めた単位 parked。元 works/blk-fix/scripts/accept.py:378（盤面の代わりに置き場と値 owed・excused で受ける）"""
    import parking
    import tddloop
    import writes
    loops = [state] if state else [str(p) for p in tddloop.states(place)]
    feet = parking.footprint(rows, loops, repo, skip=tuple(skip))
    cache = pathlib.Path(place) / "impact"
    reached = {k: parking.reach(repo, rev, f, cache) for k, f in feet.items()}
    out = set(excused) | set(parked)
    keys = set(owed) | {c.get("unit_key") for c in rows if isinstance(c.get("unit_key"), str)}
    got = parking.settle(texts, keys=keys, feet=feet, reached=reached, owed=set(owed) - out, out_of_duty=out,
                         changed=set(writes.changed(repo, rev)), declared=declared, skip=tuple(skip))
    return got, out, feet


def park_units(place, repo, settled, head: str, *, iteration: int, pass_: str) -> tuple:
    """最後の回に結んだ単位を止める: 足跡（settled.files）を段の頭の木 head に戻して控えの patch に移し（revert_units。戻したファイルを
    名指す今の段 pass_ の query_hits_fixed の行に控えを置く conflict.mark_reverted）、単位ごとに
    ask_human の裁定つきの申し出を積み（conflict.park）、置き場の trace に conflict.ACCEPT_PARKED_OP の行。返り
    ({key: 結末の理由}, 控えのパス)。元 works/blk-fix/scripts/accept.py:434（通し直しは呼び手 accept_reply）"""
    import conflict
    patch = revert_units(place, repo, settled.files, head)
    conflict.mark_reverted(place, settled.files, patch, pass_)
    out = {}
    for key, texts in settled.park.items():
        why = " / ".join(texts)
        conflict.park(place, [{"unit_key": key, "between": [], "why_both_cannot_hold": why,
                               "which_is_right": conflict.UNKNOWN, "kind": conflict.NEEDS_CONTEXT}],
                      source=conflict.FIX_SOURCE,
                      ruling={"decision": conflict.ASK, "text": f"{BOUND_PARKED}{why}（戻した直しの控え {patch}）", "limits": [],
                              "by": FIX_ACCEPT_BY})
        out[key] = GAVE_UP.format(n=iteration, patch=patch, why=why)
    conflict.write_rulings(place)
    trace(place, conflict.ACCEPT_PARKED_OP, node=FIX_ACCEPT_BY, unit_keys=list(settled.park), patch=patch,
          reasons=settled.park, unbound=settled.unbound, how=settled.how)
    return out, patch


def _without_units(reply: dict, drop: set) -> dict:
    """changes と not_done から単位 drop の行を外した返答"""
    out = dict(reply)
    for field in ("changes", "not_done"):
        if isinstance(reply.get(field), list):
            out[field] = [r for r in reply[field] if not (isinstance(r, dict) and r.get("unit_key") in drop)]
    return out


def accept_reply(reply: dict, place, repo, *, pass_: str, iteration: int, owed, judged=None, suite: str = "",
                 state: str = "", tests_state: str = "", base_rev: str = "", head: str = "", skip=(), parked=None,
                 reverted=frozenset(), trail=None, log=None) -> dict:
    """修正役の返答の受け付け（fix-accept は pass_ first・fix-ruled-accept は ruled）。確かめは返さずに FIX_CHECKS の id で積み、
    最後に 1 回だけ拒む。順は 範囲の相談の枠 → 凍ったテスト（factchecks.check_frozen）→ 書き込みの出どころ（factchecks.check_writes。
    記録の無い run は undeclared_writes で段の頭の木 head からの変更を申告に縛る）→ 食い違いの申し出（take_conflicts。first で
    裁かれていない申し出が在れば輪を抜ける {ok: True, conflicted: True}）→ 除くパスの頭の下の変更（check_pack_copy）→
    単位の行（check_unique_units・check_opened_units・check_excused_units）→ 承認済みの修正案の範囲（factchecks.check_plan_scope）→ 変更に当たる試験（tddloop.selected_problems）→
    事後の関門の束（fixgates.problems）→ 閉鎖の数え直し（closure_reply。defects の問いが閉じない単位は申し出が無ければ
    戻す。通れば表を querytest.save_closure）→ 数え直し（recount.accept_fix）。積んだ行が範囲の外のはみ出し（gather_overflow）だけなら
    拒まずに settle_overflow を通す（相談に積んだ回は {ok: False, queued: True, count: false}。戻した回は戻した返答で頭から通し直す。reverted・
    trail はその通し直しが渡す）。最後の回の単位への結びは、はみ出しでない行にだけ当てる（止めた後の通し直しのはみ出しは聞かずに戻す）。
    rolekit.is_last_attempt(iteration) が真の拒否は、写しでない行を単位に結んで（last_settle）結んだ単位だけを head に戻して諦め
    （park_units）、残りの単位で頭から通し直す。義務の外の単位にだけ結んだ行は数えず、その単位の行を changes・not_done から外して
    （直しは作業ツリーに残す）写しの照らしを当て直し、受ければ trace に ABSORBED_OP。写しの拒否が残れば同じく結び、止める単位が
    残らなければ義務の残りを全部止めて通し直す（parking.park_owed。写しの拒否の時だけ）。それでも残れば受けずに諦める（NOT_SETTLED）。
    owed は直す義務の値（fixboard.fix_duty に渡す）、judged は判定の units、suite は実行器、state は今の段の
    TDD の輪の状態のファイル（無ければ空）、tests_state は state が空の時に変更に当たる試験を走らせる輪の状態（実行器と名指し。
    裁定の後の段で組の輪が幾つも在る時。ruled_states）、base_rev は修正前の版（空なら base_rev_of）、skip は除くパスの頭、log は
    書き込みの記録のファイル（factchecks.check_writes。None なら置き場の既定）。
    返り {ok, reason, rejects: [{check, text}], reply（受けた返答。bash_writes と conflicts を外した物）, units（unit_outcomes）,
    parked {key: 理由}, conflicted}。元 works/blk-fix/scripts/accept.py:611（盤面の代わりに置き場と値）"""
    import conflict
    import consult
    import factchecks
    import fixgates
    import parking
    import recount
    import tddloop
    import unitrows
    import writes
    parked = dict(parked or {})
    trail = {"reverted": []} if trail is None else trail
    rev = base_rev_of(place, base_rev)
    last = rolekit.is_last_attempt(iteration)
    found, declared = [], {}

    def note(check, texts):
        for t in [texts] if isinstance(texts, str) else texts:
            if t and t.strip():
                found.append((check, t))
    if isinstance(reply, dict) and conflict.CONSULT_FIELD in reply:
        note("consult", CONSULT_SPENT.format(n=consult.BUDGET))
        reply = {k: v for k, v in reply.items() if k != conflict.CONSULT_FIELD}
    whole = reply
    frozen_over = []   # 相談に回せる凍ったファイルの頼み（check_frozen が足す）
    note("frozen", factchecks.check_frozen(pathlib.Path(place), state, repo, pass_, asks=frozen_over, base_rev=rev))
    made = set(tddloop.suite_made(state)) | tddloop.suite_made_all(place)
    wrote = factchecks.check_writes(reply, pathlib.Path(place), rev, repo, state, log=log, since=head or None,
                                    skip=tuple(skip))
    note("writes", wrote["problems"])
    if not wrote["problems"] and wrote["note"] == writes.NO_RECORD:
        note("writes", undeclared_writes(reply, repo, head or rev, made=made, skip=skip))
    reply = wrote["reply"]
    reply, done = take_conflicts(reply, place, repo, pass_, owed)
    if done is not None:
        if done.get("ok") is True:   # 1 回目に裁かれていない申し出: 積んだ誤りが在っても輪を抜ける（裁定の後の受け付けが当て直す）
            units = unit_outcomes(owed, {}, parked=parked, conflicted=parked_reasons(place, [k for k in owed if k not in parked]))
            return {"ok": True, "reason": "", "rejects": [], "reply": reply, "units": units, "parked": parked,
                    "conflicted": True}
        for key, text in done.get("lines") or [(None, done["reason"])]:
            note("conflict", text)
            if key:
                declared.setdefault(text, set()).add(key)
    scope_note = None   # 承認済みの修正案の項目と差分を照らした記録（はみ出しの行 overflow を持つ）
    got = factchecks.fix_unit_keys(reply, pathlib.Path(place), owed)
    if got is not None:
        note("pack", check_pack_copy(reply, place, repo, skip))
        keys, duty, excused = got
        note("duplicate", [DUPLICATE + k for k in check_unique_units(keys)])
        note("not_opened", [NOT_OPENED + k for k in check_opened_units(keys, duty | set(excused))])
        note("excused", [f"{EXCUSED}{k}（{why}）" for k, why in check_excused_units(keys, duty, excused).items()])
        scope, scope_note = factchecks.check_plan_scope(reply, keys, pathlib.Path(place), rev, repo, state, pass_, since=head or None,
                                               items=functools.partial(place_items, place), consult_place=place)
        note("scope", scope)
    else:
        duty, excused = fix_duty(place, owed)
    red, tests_note = tddloop.selected_problems(state or tests_state, repo, rev)
    note("tests", red)
    tests_trace(place, state or tests_state, tests_note, pass_=pass_, attempt=iteration)   # 0 件の知らせも捨てない（F014）
    note("plan_faces", plan_face_errors(place, reply, face_units(pass_, duty)))
    gates = fixgates.problems(place, repo, rev, suite, iteration, pass_=pass_, owed=set(duty))
    note("gates", fixgates.reject_lines(gates) if gates else [])
    precedents = (read_json(pathlib.Path(place) / JUDGMENT_FILE, {}) or {}).get("precedents") or []

    def check_copy(reply):
        """閉鎖の数え直し（closure_reply）で閉じない欠陥の数え（unitrows.unclosed_defects）を closure に単位へ結んで積み、
        それを当てた返答の写しの照らし（recount.accept_fix）の誤りを copy に積む。それまでに積んだ行が無ければ写しの照らしを
        置き場に刻み、通れば表を querytest.save_closure で置き場に置く"""
        shaped, closure, zero = closure_reply(reply, place, repo, rev, judged)
        for row in unitrows.unclosed_defects(closure):
            text = UNCOUNTED_DEFECTS.format(key=row["unit_key"], why=" / ".join(row["discrepancies"])) if row["closed"] is None \
                else UNCLOSED_DEFECTS.format(key=row["unit_key"], total=row["total"], after=row["after"],
                                             kind=conflict.KIND_FIELD, hits=conflict.QUERY_HITS_FIXED, which=conflict.WHICH_FIELD,
                                             query=conflict.QUERY, correct=conflict.CORRECT, scope=conflict.SCOPE_NEEDED)
            note("closure", text)
            declared.setdefault(text, set()).add(row["unit_key"])
        commit = not found
        out = recount.accept_fix(shaped, place, rev, repo, judged=judged, owed=set(duty), zero_keys=zero,
                                 precedents=precedents, commit=commit)
        if out.get("ok") is not True:
            note("copy", out.get("problems") or [str(out.get("reason") or "")])
        elif closure and commit:
            import querytest
            querytest.save_closure(types.SimpleNamespace(scope_root=pathlib.Path(place), round=1), closure)
    check_copy(reply)
    kw = dict(pass_=pass_, iteration=iteration, owed=owed, judged=judged, suite=suite, state=state,
              tests_state=tests_state, base_rev=base_rev, head=head, skip=skip, parked=parked, log=log)

    def again(r, gone):
        return accept_reply(r, place, repo, **kw, reverted=gone, trail=trail)
    asks = gather_overflow(scope_note, frozen_over, gates, place, rev, repo)
    over, rest = split_rows(found, asks)
    if over and not rest:   # はみ出しの行だけ（写しの照らしは上で乾いた形に当ててある）: 拒まずに相談に積むか、戻して通し直す
        got = settle_overflow(asks, found, whole, place, repo, head=head or rev, reverted=reverted, trail=trail,
                              pass_=pass_, ask=not parked, again=again)
        if got is not None and got.get("queued"):   # 積んだ回: 拒否の形に単位の結末を足す（盤面の結末は前の拒否と同じ）
            return {**got, "units": unit_outcomes([k for k in owed if k not in parked], {}, excused=excused, parked=parked),
                    "parked": parked}
        if got is not None:
            return got
        over, rest = split_rows(found, asks)
    absorbed = None   # 最後の回に数えなかった物 {dropped: 外した行の単位, absorbed: 数えなかった文}（受けた時に trace へ）

    def accepted(reply):
        units = unit_outcomes([k for k in owed if k not in parked], reply, excused=excused, parked=parked)
        overflow_trace(place, trail, repo, pass_=pass_, attempt=iteration)
        gates_trace(place, pass_=pass_, attempt=iteration)
        if absorbed:
            trace(place, ABSORBED_OP, node=FIX_ACCEPT_BY, **absorbed)
        return {"ok": True, "reason": "", "rejects": [], "reply": reply, "units": units, "parked": parked,
                "conflicted": False}

    def rejected(head_text=""):
        return {"ok": False, "reason": head_text + fix_reject_text(found),
                "rejects": [{"check": c, "text": t} for c, t in fix_reject_rows(found)], "reply": reply,
                "units": unit_outcomes([k for k in owed if k not in parked], {}, excused=excused, parked=parked),
                "parked": parked, "conflicted": False}
    if not found:
        return accepted(reply)
    if not last:
        return rejected()
    # 最後の回の止めは成り立たない行にだけ当てる（はみ出しは止めた後の通し直しが聞かずに戻す）。写しでない行を先に結び、写しの
    # 拒否は義務の外の単位の行を外した返答に当て直してから結ぶ（元 accept.py:687-697・:725-740）
    rows = [c for c in whole.get("changes") or [] if isinstance(c, dict)]
    plain = [t for c, t in rest if c != "copy"]
    settled = None
    if plain:
        settled, out_of_duty, feet = last_settle(plain, rows, place, repo, rev, state, owed, excused, set(parked),
                                                 declared=declared, skip=skip)
        if not settled.park:   # 義務の外の単位にだけ結んだ行: 数えず、その単位の行を外して残りで先へ（直しは作業ツリーに残す。元 :636-645）
            absorbed = {"dropped": [c.get("unit_key") for c in reply.get("changes") or []
                                    if isinstance(c, dict) and c.get("unit_key") in out_of_duty],
                        "absorbed": settled.absorbed}
            reply = _without_units(reply, out_of_duty)
            found = list(over)
            check_copy(reply)
            over, rest = split_rows(found, asks)
            if over and not rest:   # 残ったはみ出しは聞かずに戻して通し直す（元 :693-697）
                got = settle_overflow(asks, found, whole, place, repo, head=head or rev, reverted=reverted, trail=trail,
                                      pass_=pass_, ask=False, again=again)
                if got is not None:
                    return got
                over, rest = split_rows(found, asks)
            if not found:
                return accepted(reply)
    if settled is None or not settled.park:   # 写しの拒否（by_copy）: 止める単位が残らなければ義務の残りを全部止める（元 :738-740）
        texts = [t for c, t in rest if c == "copy"]
        settled, out_of_duty, feet = last_settle(texts, rows, place, repo, rev, state, owed, excused, set(parked),
                                                 declared=declared, skip=skip)
        if not settled.park and texts and set(duty) - out_of_duty:
            settled = parking.park_owed(texts, feet=feet, owed=set(duty), out_of_duty=out_of_duty, skip=tuple(skip))
    if not settled.park:
        return rejected(NOT_SETTLED)
    now, _ = park_units(place, repo, settled, head or rev, iteration=iteration, pass_=pass_)
    return accept_reply(_without_units(whole, set(now)), place, repo, pass_=pass_, iteration=iteration, owed=owed,
                        judged=judged, suite=suite, state=state, tests_state=tests_state, base_rev=base_rev, head=head,
                        skip=skip, parked={**parked, **now}, reverted=reverted, trail=trail, log=log)


def traced_ops() -> tuple:
    """accept_trace_rows が trace.jsonl から ACCEPT_TRACE_FILE へ運ぶ受け付けの行の op（事後の関門の束が赤緑を確かめずに受けた回・
    はみ出しの決着・範囲の相談）"""
    import conflict
    import fixgates
    import impact
    return fixgates.SKIPPED_OP, impact.ACCEPT_OVERFLOW_OP, conflict.ASKED_OP


def gates_trace(place, *, pass_: str, attempt: int) -> None:
    """受けた回に、事後の関門の束が受け入れのテストの赤緑を確かめずに受けた理由（fixgates.unchecked。義務の外を除く）が在れば
    置き場の trace に fixgates.SKIPPED_OP の行を積む（元 works/blk-fix/scripts/accept.py:708-714 の traced の 2 行目。読み手は
    accept_trace_rows を通した最後の関所と報告）"""
    import fixgates
    gaps = fixgates.unchecked(place, pass_=pass_, attempt=attempt)
    if gaps:
        trace(place, fixgates.SKIPPED_OP, node=FIX_ACCEPT_BY, pass_=pass_, attempt=attempt, why=gaps)


def closure_reply(reply: dict, place, repo, rev: str, judged) -> tuple:
    """閉鎖の数え直し（unitrows.build）を当てた返答と単位ごとの表 (返答, 表の行, 判定の時に engine が 0 件と数えた単位)。判定者の
    class_query（裁定 replace_query を受けた単位は置き換えた問い。conflict.replaced_queries）を修正前の版 rev と今の作業ツリーで
    recount._run_query が数え、覆いは修正前の版からの変更（writes.changed。読めなければ何も覆わない）で数える。0 件の単位は、判定者の
    問いを同じ版で数えて 0 件なのに判定者の total が 0 でない単位（元は判定の受け付けが盤面の engine_zero に置いた物。判定は同じ固めた
    版で数える）。元 works/blk-fix/lib/unitrows.py:218 の take（盤面の代わりに置き場と値）"""
    import conflict
    import recount
    import unitrows
    import writes
    changes = reply.get("changes") or []
    queries = {u.get("key"): u.get("class_query") or {} for u in judged or [] if isinstance(u, dict)}
    if not any(isinstance(c, dict) and ((queries.get(c.get("unit_key")) or {}).get("how")
                                        or (c.get("coverage") or {}).get("how")) for c in changes):
        return ({**reply, "changes": [unitrows._unpathed(c) for c in changes]} if changes else reply), [], set()

    def count(how, at_rev):
        if at_rev:
            return recount._run_query(place, "閉鎖の数え直し（修正前）", how, str(repo), rev=rev)
        return recount._run_query(place, "閉鎖の数え直し（修正後）", {**how, "untracked": True}, str(repo), probe=False)

    def per_file(how, at_rev):
        return unitrows.file_counts(how, repo, rev) if at_rev else unitrows.file_counts({**how, "untracked": True}, repo)
    zero = set()
    for key, q in queries.items():
        if q.get("how") and isinstance(q.get("total"), int) and q["total"] != 0 and count(q["how"], True)[0] == 0:
            zero.add(key)
    try:
        touched = writes.changed(repo, rev)
    except Exception:   # 読めなければ何も覆わない（site の path も変わったと確かめられない）
        touched = None
    out, rows = unitrows.build(changes, queries, count=count, blank=recount.blank, zero_keys=zero,
                               replaced=conflict.replaced_queries(place), per_file=per_file, touched=touched)
    return {**reply, "changes": out}, rows, zero


def record_base_rev(place, repo) -> str:
    """修正前の版（repo の HEAD の sha）を置き場 place の BASE_REV_FILE に控えて返す。並べた組の子の worktree は実行基盤が
    origin の枝から切るので、子の HEAD は親の HEAD と違う。だから親の prep が控え、子は写した物を読む（base_rev_of）"""
    import leftovers
    rev = leftovers.git(repo, "rev-parse", "HEAD").strip()
    write_json(pathlib.Path(place) / BASE_REV_FILE, {"rev": rev})
    return rev


def base_rev_of(place, given: str = "") -> str:
    """受け付けの修正前の版: given、無ければ置き場 place の BASE_REV_FILE の版、それも無ければ HEAD"""
    doc = read_json(pathlib.Path(place) / BASE_REV_FILE)
    return base_rev(None, given or (str(doc.get("rev") or "") if isinstance(doc, dict) else ""))


def gate_view(place):
    """gatemarks の問いの口（asks・answered・pending・withheld_by・returned・duty・returned_lines）に渡す値の見え方（gatemarks.ledger）:
    置き場の判定の写しの questions・units、始めの記録の写しの依頼の answers、関所の答え answers.json（{decision, text, asked}。asked は
    人が見た関所の行）、判定の結びと素材の状態の写し（TIES_FILE・MATERIALS_FILE。prep が入力 answer_ties・materials の先から写す。無ければ字の一致だけ）。
    始めの記録の写しが無人の run なら、判定の推しつきの fork・held を答えとして数える（gatemarks.run_push）。
    元は盤面の b.record と写しの検証器を読んだ"""
    import gatemarks
    import gatepolicy
    p = pathlib.Path(place)
    judgment = read_json(p / JUDGMENT_FILE)
    start = startrec.read(p)
    return gatemarks.ledger_files(judgment if isinstance(judgment, dict) else {}, ties_file=p / TIES_FILE,
                                  materials_file=p / MATERIALS_FILE, answers=start.get("answers") or [],
                                  gate=read_json(p / ANSWERS_FILE), takes_push=gatepolicy.unattended_of(start))


def gate_asks(place) -> tuple:
    """(答えが無いので直す義務から外す単位 {key: 問い}, 答えで直す義務に戻る単位 set)。gatemarks.withheld_by・returned を
    gate_view で引いた物"""
    import gatemarks
    view = gate_view(place)
    return gatemarks.withheld_by(view), gatemarks.returned(view)


def write_notes(place, machine: str = "") -> str:
    """修正前の関所の一言（無人の run が推しで通した行は answer.said の印つき）と、答えで直す義務に戻った単位の行
    （gatemarks.returned_lines）と、機械の申し送り machine（2 度目の修正の段に線が渡す、採った項目の事前審査の穴のうち人に聞く種類で
    ない物の節。元 replan._notes の FACES_HEAD の節）を置き場の NOTES_FILE に書き、パスを返す。どれも無ければ書かずに ""。
    元 works/darkfactory/lib/line_edge.py:1218 の h-fix の notes_file と works/.shared/core/replan.py:677 の notes_file"""
    import gatemarks
    view = gate_view(place)
    said = [answer.said(h) for h in view.record["process"]["human_items"] if h["note"]]
    notes = "\n".join([*said, *gatemarks.returned_lines(view), *([machine.strip()] if machine.strip() else [])])
    if not notes:
        return ""
    return str(write_text(pathlib.Path(place) / NOTES_FILE, notes))


def gate_items(answers) -> list:
    """直す前の人の関所の答え answers を human_items の行にする（gatemarks.gate_items。consult.gate_notes が読む）"""
    import gatemarks
    return gatemarks.gate_items(answers)


def consult_ask(place, reply, pass_: str, items, *, node: str, human_items=(), round_: int = 1, plan_file: str = "",
                ripple_file: str = "") -> dict:
    """範囲の相談の頼みの節: 返答の consult（と受け付けが積んだ頼み・人の関所の条件）を頼みごとに先の確かめ（consult.screen・
    oos_hits）をして置き場の相談の状態（consult.state_path）に積み、聞く頼みが在れば答えの役の指示書（修正案のファイル plan_file と
    波及の一覧 ripple_file を読む新しい会話。consult.question）を置き場に書く。返り {consulted, go, prompt_file, turn, spent}。
    items は承認済みの修正案の項目（planmarks.approved_items の形）。元 works/blk-fix/lib/consult.py:522（相手の会話を写す
    alias を外し、答えの役は新しい会話にした。持ち主の決め planner-talk の狭め）"""
    import consult
    st = consult.state(place, pass_)
    turns = int(st.get("turns") or 0)
    table = consult.items_doc(items or [])
    asks = [*consult.queued(place, pass_), *(consult.requests(reply) or [])] or None
    if asks is None and turns < consult.BUDGET:
        asks = consult.gate_asks(place, table, human_items, round_) or None
    if asks is None:
        return {"consulted": False, "go": False, "prompt_file": "", "turn": 0, "spent": False}
    if turns >= consult.BUDGET:
        return {"consulted": False, "go": False, "prompt_file": "", "turn": turns, "spent": True}
    turn = turns + 1
    rows = []
    for n, a in enumerate(asks, 1):
        new_tests = a.get("new_tests") or []
        why = consult.screen(table, a["item"], a["paths"], a["tests"], a["why"], new_tests,
                             gate=a.get("origin") == consult.ORIGIN_GATE)
        hits = consult.oos_hits(table, a["item"], a["paths"] + [consult._test_file(x) for x in new_tests], a["tests"]) \
            if a["item"] in table else []
        rows.append({**a, "n": n, "out_of_scope": hits,
                     **({"status": consult.REFUSED, "why_refused": why} if why else {"status": consult.ASKED})})
    asked = [r for r in rows if r["status"] == consult.ASKED]
    qfile = ""
    if asked:
        ripple = RIPPLE_READ.format(path=ripple_file) if ripple_file else ""
        head = CONSULT_HEAD.format(plan=plan_file or "（修正案のファイルは無い）", ripple=ripple)
        path = pathlib.Path(place) / consult.QUESTION_FILE.format(pass_=pass_, turn=turn)
        path.write_text(head + "\n\n" + consult.question(table, asked), encoding="utf-8")
        qfile = str(path)
    jsonfile.write(consult.state_path(place, pass_), {"turns": turn, "turn_state": consult.ASKED, "rows": rows,
                                                           "question_file": qfile, "session": None, "node": node,
                                                           "items": table})
    return {"consulted": True, "go": bool(asked), "prompt_file": qfile, "turn": turn, "spent": False}


def ruled_reply_line(prompt_file, reply_file: str) -> None:
    """裁定の後の修正役の指示書 prompt_file の題の次の行に、1 回目の修正役の返答の保存したファイル reply_file を名指す行
    （RULED_REPLY_LINE）を差し込む（既に在れば何もしない）。新しい（今の works は修正役の会話の続きで起こした。持ち主の決め
    persona の「機械が保存した返答で渡す」の側）"""
    if not reply_file:
        return
    p = pathlib.Path(prompt_file)
    text = p.read_text(encoding="utf-8")
    line = RULED_REPLY_LINE.format(path=reply_file)
    if line in text:
        return
    head, sep, rest = text.partition("\n")
    write_text(p, f"{head}\n\n{line}\n{sep}{rest}" if sep else f"{head}\n\n{line}\n")


TDD_START_FILE = "tdd-start.json"   # TDD の輪の頭の返り（tddloop.start の {go, state_file, summary_file, …}。group-start が書く）
JOIN_FILE = "join.json"             # 組を親の木へ戻した結果 {groups, units}（join が書く）


def loop_files(place) -> tuple:
    """(今の段の TDD の輪の状態のファイル, 輪の要約のファイル)。置き場の tdd-start.json の state_file・summary_file のうち在る物
    （輪の無い run・始めていない run は ("", ""))"""
    doc = read_json(pathlib.Path(place) / TDD_START_FILE)
    doc = doc if isinstance(doc, dict) else {}
    got = [str(doc.get(k) or "") for k in ("state_file", "summary_file")]
    return tuple(p if p and pathlib.Path(p).is_file() else "" for p in got)


def stage_head(place, name: str = "") -> str:
    """段の頭の木: name（置き場の {tree} の控え。裁定の後の段の RULED_HEAD_FILE）が在ればその tree、無ければ控え
    fix-ignored-before.json の head_tree（leftovers.head_tree）。どちらも無ければ空"""
    import leftovers
    if name:
        doc = read_json(pathlib.Path(place) / name)
        if isinstance(doc, dict) and isinstance(doc.get("tree"), str) and doc["tree"]:
            return doc["tree"]
    try:
        return leftovers.head_tree(place)
    except leftovers.Unreadable:
        return ""


def fixer_head(place, pass_: str) -> str:
    """修正役が変え始めた木（段 pass_ の頭の木。stage_head）。受け付け（fix-accept・fix-ruled-accept）と修正役の事前の確かめ
    （factchecks.precheck）が since に渡す木はここ 1 か所から読む。段の頭のファイルは fixrules.head_file（PASSES に無い段は ValueError）"""
    import fixrules
    return stage_head(place, fixrules.head_file(pass_))


def ruled_owed(place) -> list:
    """裁定の後の修正の段（形 "" の置き場）の直す義務の値: 判定の直す義務の単位（group_owed）のうち、親の木へ戻せた組の単位で
    結末が fixed でない物（join.json。無ければ判定の直す義務の全部）"""
    keys = group_owed(place)
    doc = read_json(pathlib.Path(place) / JOIN_FILE)
    if not isinstance(doc, dict):
        return keys
    back = {g.get("group_id") for g in doc.get("groups") or [] if isinstance(g, dict) and g.get("returned")}
    left = {u.get("unit_id") for u in doc.get("units") or []
            if isinstance(u, dict) and u.get("group_id") in back and u.get("status") != FIXED}
    return [k for k in keys if k in left]


def brief_sources(place) -> dict:
    """planbrief.cut の材料（置き場の修正案の役の返答の写し PLAN_REPLY_FILE と判定の写し judgment.json。無ければ None）"""
    p = pathlib.Path(place)
    return {"plan": read_json(p / PLAN_REPLY_FILE), "judgment": read_json(p / JUDGMENT_FILE)}


def fix_values(place, owed, *, start, state: str = "", summary: str = "", answer_node: str = "") -> dict:
    """修正役の指示書の run の値（fixrules.FIX_VALUES と request_file・plan_session・tdd_state・ripple_file・base_rev）。始めの
    記録 start の固めた方針の写しは policy_path、request_file は startrec.request_file で読む。plan_session は範囲の相談に答える役の名（answer_node。
    空なら相談の節を載せない）"""
    p = pathlib.Path(place)

    def there(name):
        return str(p / name) if (p / name).is_file() else ""
    import policy
    start = start if isinstance(start, dict) else {}
    return {"judgment_file": there(JUDGMENT_FILE), "open_units": json.dumps(list(owed), ensure_ascii=False),
            "plan_file": there(PLAN_REPLY_FILE), "policy_path": policy.frozen_copy(start),
            "notes_file": there(NOTES_FILE), "summary_file": summary or "",
            "request_file": startrec.request_file(start), "plan_session": answer_node, "tdd_state": state or "",
            "ripple_file": there(RIPPLE_FILE), "base_rev": base_rev_of(place)}


def consult_skip(place, skip, log=None) -> None:
    """置き場の範囲の相談の控え（consult.CONFIG。fixrules.ask_config が書く）に除くパスの頭 skip と書き込みの記録のファイル log
    （在れば。受け付けと同じ物）を足す（factchecks.main が書き込みの出どころで読む）。控えが無ければ何もしない"""
    import consult
    doc = read_json(pathlib.Path(place) / consult.CONFIG)
    if isinstance(doc, dict):
        consult.write_config(place, {**doc, "skip": list(skip), **({"log": str(log)} if log else {})})


# ---------------------------------------------------------------- はみ出しの行だけの回の道筋（元 works/blk-fix/scripts/accept.py:498〜:609）
UNREVERTABLE = "はみ出しを戻せない: "   # 戻しても行が残るはみ出しの成り立たない行の頭（後ろに元の文。元 accept.py:152）
EMPTIED = "はみ出しを戻すと直しが残らない: "   # 戻すとその単位の files が空になる成り立たない行の頭（後ろに単位。元 accept.py:153）
QUEUED = ("受け付けが範囲の外のはみ出しを見つけ、修正案を書いた役への相談に回した（作業ツリーは変えていない。次の周の指示書に従い、"
          "答えが出るまで直しを足すな）: ")   # 元 accept.py:154


def _overflow_items(place) -> list:
    """承認済みの修正案の項目（範囲の相談の合意を足した物。planrange.with_agreed）。案の無い run は []。元 accept.py:498 の _items
    （盤面の代わりに置き場の控えを place_items で読む）"""
    import conflict
    import planrange
    items = place_items(place)
    return planrange.with_agreed(items, conflict.agreed(place)) if items else []


def gather_overflow(scope_note, frozen, gates: list, place, rev: str, repo) -> list:
    """受け付けが見つけた、相談に回せるはみ出し [{line, item, paths, tests, new_tests, ref}]。入口は 3 つで、見分けは持ち主が持つ:
    範囲の持ち主 planscope の記録 overflow、凍結の持ち主 tddloop の頼み（check_frozen の asks）、事後の関門の持ち主 fixgates の
    test_edits の行（fixgates.overflow_asks）。ここは束ねるだけ。rev は修正前の版。元 works/blk-fix/scripts/accept.py:505"""
    import fixgates
    import planrange
    out = [{"line": o["line"], "item": o.get("item"), "paths": list(o.get("paths") or []), "tests": [],
            "new_tests": list(o.get("new_tests") or []), "ref": None}
           for o in (scope_note or {}).get("overflow") or [] if isinstance(o, dict) and o.get("line")]
    items = _overflow_items(place) if frozen or gates else []
    out += [{"line": a["line"], "item": (planrange.owner(a["path"], items) or {}).get("item"), "paths": [],
             "tests": list(a["tests"]), "new_tests": [], "ref": a.get("ref")} for a in frozen]
    out += [{"line": a["line"], "item": a["item"], "paths": [], "tests": list(a["tests"]), "new_tests": list(a["new_tests"]),
             "ref": rev, **({"revert": True} if a.get("revert") else {})}
            for a in fixgates.overflow_asks(gates or [], repo, rev, items)]
    return out


def split_rows(found: list, asks: list) -> tuple:
    """積んだ行 (確かめの id, 文) の並び → (はみ出しの行, 成り立たない行)。はみ出しは文が asks の line を含む行（拒否の頭が付いても
    外れない）。『はみ出しを戻せない』の行は成り立たない行。元 works/blk-fix/scripts/accept.py:522"""
    over, rest = [], []
    for row in fix_reject_rows(found):
        hit = not row[1].startswith(UNREVERTABLE) and any(a["line"] in row[1] for a in asks)
        (over if hit else rest).append(row)
    return over, rest


def _covers(row: dict, ask: dict) -> bool:
    """相談の行（頼みの行）row が、同じ項目の同じ物 ask（パス・テストの範囲・新しいテストが全部入る）を名指しているか。元 accept.py:532"""
    return str(row.get("item") or "") == str(ask["item"] or "") and all(
        set(ask[k]) <= set(row.get(k) or []) for k in ("paths", "tests", "new_tests"))


def _queue_rows(asks: list) -> list:
    """項目ごとに 1 件の頼み（consult.queue の形）にまとめる。元 accept.py:538"""
    by: dict = {}
    for a in asks:
        r = by.setdefault(str(a["item"] or ""), {"item": a["item"], "paths": [], "tests": [], "new_tests": [], "lines": []})
        for k in ("paths", "tests", "new_tests"):
            r[k] += [x for x in a[k] if x not in r[k]]
        r["lines"].append(a["line"])
    return [{**{k: v for k, v in r.items() if k != "lines"}, "why": "\n".join(r["lines"])} for r in by.values()]


def _without_rows(reply: dict, rest: list, mine: set, repo) -> dict:
    """changes を rest にし、外したファイル（mine）の bash_writes の申告も外した返答。元 accept.py:425"""
    import factchecks
    out = {**reply, "changes": rest}
    if isinstance(reply.get("bash_writes"), list):
        out["bash_writes"] = [w for w in reply["bash_writes"]
                              if not (isinstance(w, dict) and factchecks.declared_files([{"files": [w.get("path")]}], repo) & mine)]
    return out


def overflow_trace(place, trail: dict, repo, *, pass_: str, attempt: int) -> None:
    """受けた回 (pass_, attempt) に、はみ出しを相談で認めた（合意の行の origin が accept）・機械が戻した物・守りのテスト・関所の
    条件の相談（origin が gate）で認めた新しいテストのうち今の木（repo）に在る物を置き場の trace の impact.ACCEPT_OVERFLOW_OP の
    行に名指す（どれも無ければ書かない）。名指しの字は元 accept.py:715 の traced の中の 1 行と同じ（報告が 1 件ずつ読む）。
    はみ出しの相談はこの置き場の受け付けが聞いた物だけを数える（agreed(carried=False)。戻せた組の子から写した行は子の置き場の
    受け付けが数えた物で、ここで二重に数えない）"""
    import conflict
    import consult
    import fixgates
    import impact
    rows = conflict.agreed(place, carried=False)
    agreed = [r.get("id") for r in rows if r.get("origin") == consult.ORIGIN_ACCEPT]
    gated = [f"{g['id']}（{g.get('red_kind')}）" for r in rows if r.get("origin") == consult.ORIGIN_GATE
             for g in r.get("granted_new_tests") or [] if isinstance(g, dict) and fixgates.present(repo, g.get("id"))]
    guards = [f"{g['id']}: 守りのテスト（base で {g['base']}）"
              for g in fixgates.guards(place, pass_=pass_, attempt=attempt)]
    row = impact.OverflowRow(agreed=agreed, reverted=trail["reverted"], guards=guards, gate_tests=gated)._asdict()
    if any(row.values()):
        trace(place, impact.ACCEPT_OVERFLOW_OP, node=FIX_ACCEPT_BY, **row)


def settle_overflow(asks: list, found: list, whole: dict, place, repo, *, head: str, reverted, trail: dict, pass_: str,
                    again, ask: bool = True):
    """はみ出しの行だけの回の道筋の選び。返りは出口の dict（積んだ {ok: False, queued: True, count: false, …}・戻して通し直した返り）か、拒む時は
    None（戻しきれない物を成り立たない行にして found に足してある）。見分けは持ち主（planscope の overflow・fixgates.overflow_asks・
    tddloop.frozen_asks）、聞いた答えは conflict.plan_asks、積みは consult.queue、戻しは keep_patch・tddloop.restore_paths・
    tddloop.restore_tests・_without_rows が持ち、ここは選ぶだけ:
    - 戻したのにまだ行が残る物（reverted に在る）は『はみ出しを戻せない』
    - まだ聞いていない物は積む（枠が足りなければ戻す側）。積んだが頼みにする前の物は積み直さず同じ出口
    - 聞いた物（allow の後も残る行・deny・defer・invalid・unavailable・refused）は戻す
    ask が偽（最後の回に成り立たない行で単位を止めた後の通し直し）は聞かずに全部を戻す（止めた後に相談の周へ回さない）。
    place は置き場のパス、head は段の頭の木（戻し先）、whole は役の返答（bash_writes を外す前）、again(返答, 戻した行の集合) は
    戻した返答で受け付けを頭から通し直す呼び手の口（accept_reply）、found は積んだ行 (確かめの id, 文) の並び。
    元 works/blk-fix/scripts/accept.py:549（呼び手 :680〜:700）。今の輪の形との違い: 元は積んだ周の次の周の確かめの節が頼みを
    答えの節に回した。今の輪（fixer → consult-check → consult-answer → consult-accept → fix-accept）では、積んだ周の後に修正役が
    もう 1 回走り（fixrules.prep が consult.queued を見て作業ツリーを変えずに前の返答と同じ JSON を返させる続きの指示書だけを書く。
    受け付けの回には数えない）、その周の consult-check（consult_ask）が積んだ頼みを答えの役に回し、その周の受け付けは相談の周として
    回らない。答えの後の周の受け付けが、ここで聞いた物を戻すか（allow なら範囲に入って行が消える）を選ぶ"""
    import conflict
    import consult
    import factchecks
    import tddloop
    answered = [r for r in conflict.plan_asks(place) if r.get("origin") == consult.ORIGIN_ACCEPT]
    pending = consult.queued(place, pass_)
    stuck = [a for a in asks if a["line"] in reverted]
    if stuck:
        for a in stuck:
            found.append(("scope", UNREVERTABLE + a["line"]))
        return None
    fresh, back, waiting = [], [], False
    for a in asks:
        if not ask or a.get("revert") or any(_covers(r, a) for r in answered):   # revert: 合意のテストが赤緑で落ちた（聞き直さず戻す）
            back.append(a)
        elif any(_covers(r, a) for r in pending):
            waiting = True
        else:
            fresh.append(a)
    if fresh and consult.queue(place, pass_, _queue_rows(fresh)) or waiting and not fresh:
        reason = QUEUED + " / ".join(a["line"] for a in asks)
        return {"ok": False, "reason": reason, "rejects": [{"check": "scope", "text": reason}], "reply": whole,
                "conflicted": False, "queued": True, "count": False}   # units・parked は呼び手が足す
    back += fresh   # 枠が足りず聞けない物
    paths = sorted({p for a in back for p in a["paths"]})
    emptied = [c.get("unit_key") for c in whole.get("changes") or [] if isinstance(c, dict)
               and factchecks.declared_files([c], repo) and factchecks.declared_files([c], repo) <= set(paths)]
    if emptied:
        for key in emptied:
            found.append(("scope", f"{EMPTIED}{key}"))
        return None
    by_ref: dict = {}
    for a in back:
        for spec in a["tests"]:
            by_ref.setdefault(a["ref"], [])
            if spec not in by_ref[a["ref"]]:
                by_ref[a["ref"]].append(spec)
    ids = sorted({i for a in back for i in a["new_tests"]})
    specs = [s for ss in by_ref.values() for s in ss]
    test_files = {posixpath.normpath(s.partition("::")[0]) if "::" in s else (conflict.parse_limit(s) or (s,))[0]
                  for s in [*specs, *ids]}
    patch = keep_patch(place, repo, {*paths, *test_files}, head)
    tddloop.restore_paths(repo, head, paths)
    for ref, ss in by_ref.items():
        tddloop.restore_tests(repo, head, ss, ref=ref)
    tddloop.restore_tests(repo, head, ids)
    trail["reverted"].append({"paths": paths, "tests": specs, "new_tests": ids, "patch": patch,
                              "lines": [a["line"] for a in back]})
    gone = set(paths)
    rows = []
    for c in whole.get("changes") or []:
        keep = [f for f in c.get("files") or [] if not isinstance(f, str) or not factchecks.declared_files([{"files": [f]}], repo) & gone] \
            if isinstance(c, dict) else None
        rows.append({**c, "files": keep} if keep is not None else c)
    return again(_without_rows(whole, rows, gone, repo), set(reverted) | {a["line"] for a in back})
