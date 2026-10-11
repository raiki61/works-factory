"""fix の置き場（run の作業のファイルを置くフォルダ。scripts が渡す）の読み書きの助け。

今の works の盤面の物 `b` から読んでいた値を、置き場のファイルか引数で受ける形にした物だけを置く。

- trace(place, op, **kw): 置き場の trace.jsonl に {"op": op, **kw} を 1 行足す（元の盤面の b.trace の代わり）
- base_rev(state, given=""): 突き合わせの起点の版（元 works/.shared/core/writes.py:88 の base_rev）
- marks_view(place, round_=1): planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits）に渡す読むだけの形
  （dir と round だけ。conflict の test_permits・frozen_fields が使う。fix のブロックの中だけの合わせ口）
- plan_view(place, plan, judgment, round_=1): planmarks の承認済みの修正案の読み口に渡す読むだけの形（修正案の役の返答と
  判定を値で持つ。planbrief・範囲の照らしの items が使う。fix のブロックの中だけの合わせ口）
- owed_units_but_asked(place, owed, withheld=, returned=)・fix_duty(place, owed, withheld_by=, returned=)・
  nothing_owed_but_excused(place, owed, withheld_by=, returned=): 直す義務（元 works/.shared/core/conflict.py:676・696・787。
  盤面の写しの規則と問いの台帳を読んだ所を、値の引数で受ける）
- _fix_output(reply_file)・fix_reply(place, reply_file=None)・_coverage(place, round_=1)・
  collect(place, accepted, changed, reply_file=, owed=, withheld_by=, returned=, reads_file=): 修正の返答の読み口と集める節の中身
  （元 works/.shared/core/recount.py:89・101・142・149。盤面の p3.fix の出力と loop.coverage_after を読んだ所を、置き場と
  返答のファイルのパスで受ける）
- compose・REJECT_LINE・ROLE_DEF_HEAD: 役の指示書の組み立て（元 works/.shared/core/rolekit.py:64・168・205 の写し。rulebook.render・
  lenses.render が使う）
- write_json・out_file・output・loop_file・loop_value・snapshot・tree_moved_since・take・READONLY_MOVED: 差分の審査と手直しの
  置き場の決まった名のファイル（盤面の b.output_of_round・b.loop_state と entry.snapshot・take の代わり。元 entry.py:1228・1231・1240・1262）
- _owed_rows・_read_value・_brief・_plan_items・_fix_report・tie_items・hole_ties: 差分の審査と手直しの材料（元
  works/.shared/core/refix.py:189・197・219・340・362・291・308。盤面の読みを置き場のファイルと引数の値で受ける）

標準ライブラリだけ。
"""
import json
import os
import pathlib
import types

TRACE_FILE = "trace.jsonl"


def trace(place, op: str, **kw) -> None:
    """置き場 place の trace.jsonl に {"op": op, **kw} を JSON の 1 行で足す（フォルダが無ければ作る）"""
    path = pathlib.Path(place) / TRACE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": op, **kw}, ensure_ascii=False) + "\n")


def base_rev(state, given: str = "") -> str:
    """突き合わせの起点の版: state["inputs"]["review_rev"]（修正前に固めた版）。無ければ given、それも空なら HEAD。
    元 works/.shared/core/writes.py:88（盤面の b.state を読んだ）。state は同じ形の dict（{"inputs": {...}}）か None"""
    return ((state or {}).get("inputs") or {}).get("review_rev") or given or "HEAD"


def marks_view(place, round_: int = 1):
    """planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits。読むのは b.dir と b.round だけ）に渡す読むだけの形:
    dir は置き場 place（plan-fields.json と凍結の印の行の在る trace.jsonl を置く所）、round は round_"""
    return types.SimpleNamespace(dir=pathlib.Path(place), round=round_)



def plan_view(place, plan=None, judgment=None, round_: int = 1):
    """planmarks の承認済みの修正案の読み口（plan_items・approved_items・prescriptions・amend。読むのは b.dir・b.round・
    b.output_of_round・b.latest_output・b.trace だけ）に渡す形: dir は置き場 place（plan-fields.json と凍結の印の行の在る
    trace.jsonl を置く所）、round は round_、output_of_round(node, rnd) は rnd が round_ の時だけ修正案の役の返答 plan
    （{"plan": [...]}。今の works の p2.fix_plan の出力・plan の隣の p2.fix_plan.json）、latest_output(node) は判定 judgment
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
    修正前の関所で人が答えた問いの出どころ・depends（returned。元は gatemarks.returned）を戻し、直す裁定でない裁定を受けた単位
    （conflict.held_by_rulings。ask_human・fix_plan_item）を除く。控えが読めなければ裁定の単位を外さない（義務を減らさない側）。
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
    裁定の単位を外さない。1 回目に受け付けた返答の控え（conflict.held_reply）が在れば、その単位を直す義務から引き、理由
    conflict.ACCEPTED_WHY で外れた単位に足す（ほかの理由より先）。控えが壊れていれば held_reply の ValueError。
    元 works/.shared/core/conflict.py:696（盤面の記録と問いの台帳を読んだ）"""
    import conflict
    withheld_by = withheld_by or {}
    owed = owed_units_but_asked(place, owed, withheld=set(withheld_by), returned=returned)
    out = {k: f"答え待ちの問い {q.get('key')}（{q.get('kind')}・{q.get('status')}）" for k, q in withheld_by.items()}
    try:
        out.update(conflict.held_by_rulings(place))
    except ValueError:
        pass
    held, path = conflict.held_reply(place)
    accepted = conflict._held_keys(held)
    owed = owed - accepted
    out.update({k: conflict.ACCEPTED_WHY.format(path=path) for k in accepted})
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


def fix_reply(place, reply_file=None) -> tuple:
    """(修正の返答, そのファイルの絶対パス)。今の周の返答のファイル reply_file（_fix_output）か、無ければ置き場 place の
    1 回目に受け付けた返答の控え（conflict.held_reply を conflict.handed の形にした物）。どちらも無ければ recount.Unreadable。
    控えが壊れていれば held_reply の ValueError。元 works/.shared/core/recount.py:101（盤面の p3.fix を読んだ）"""
    import conflict
    import recount
    try:
        return _fix_output(reply_file)
    except recount.Unreadable as e:
        held, path = conflict.held_reply(place)
        if held is None:
            raise recount.Unreadable(f"{e}。1 回目に受け付けた返答の控え {path} も無い") from None
    return conflict.handed(held), path


def _coverage(place, round_: int = 1) -> dict:
    """単位ごとの {before, after}（recount.accept_fix が置き場 place に書いた coverage-after.json の今の周の行。before は修正前の
    版で数えた母数 total）。無い・周が違えば空。元 works/.shared/core/recount.py:142（盤面の loop.coverage_after を読んだ）"""
    import recount
    try:
        cov = json.loads((pathlib.Path(place) / recount.COVERAGE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(cov, dict) or cov.get("round") != round_:
        return {}
    return {i["unit_key"]: {"before": i["total"], "after": i["after"]} for i in cov.get("items") or []}


def collect(place, accepted: dict, changed: dict, *, reply_file=None, owed=(), withheld_by=None, returned=(),
            reads_file="", round_: int = 1) -> dict:
    """集める節の中身。1 本目の {ok, files, changes_file} を全部残し、fix_file（fix_reply が読んだ方のファイル）・not_done（件数）・
    coverage（単位ごとの {before, after}。_coverage）・reads_file（読んだ証拠のファイル。呼び手が渡す。在るファイルだけ、無ければ空）
    を足す。受け付けた changes を置き場 place の changes.json（{"changes": [...]}。1 本目の形）に書く。
    受け付けが通っていない・assert-changed の出力が読めない・返答も控えも無い・changes が空（直す義務の単位が残らず、外れた単位が
    在る置き場 nothing_owed_but_excused(place, owed, …) を除く）ときは recount.Unreadable（何も書かない）。
    元 works/.shared/core/recount.py:149（盤面を開いて loop.coverage_after・state.outputs・写しの規則の義務を読んだ所を、
    置き場と返答のファイル・直す義務 owed・問いの台帳 withheld_by／returned の引数で受ける）"""
    import recount
    if not isinstance(accepted, dict) or accepted.get("ok") is not True:
        raise recount.Unreadable(f"受け付けが通っていない（{(accepted or {}).get('reason') if isinstance(accepted, dict) else accepted!r}）")
    changes = accepted.get("changes")
    if not isinstance(changes, list):
        raise recount.Unreadable("受け付けの出力に changes が無い")
    files = changed.get("files") if isinstance(changed, dict) else None
    if not isinstance(changed, dict) or changed.get("ok") is not True or not isinstance(files, list) \
            or not all(isinstance(f, str) for f in files):
        raise recount.Unreadable(f"assert-changed の出力に files が無い（{changed!r}）")
    if not changes and not nothing_owed_but_excused(place, owed, withheld_by=withheld_by, returned=returned):
        raise recount.Unreadable("受け付けの出力に changes が無い")
    out, fix_file = fix_reply(place, reply_file)
    path = pathlib.Path(place) / recount.CHANGES_FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"changes": changes}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    reads_p = pathlib.Path(reads_file) if reads_file else None
    return {"ok": True, "files": files, "changes_file": str(path), "fix_file": str(fix_file),
            "not_done": len(out.get("not_done") or []), "coverage": _coverage(place, round_),
            "reads_file": str(reads_p) if reads_p and reads_p.is_file() else ""}


# ---------------------------------------------------------------- 差分の審査と手直し（refix・lenses・rulebook が読む）
# 役の指示書の組み立て（元 works/.shared/core/rolekit.py:64・168・205 の写し。main の lib/rolekit.py に無いので fix の中に置く）
REJECT_LINE = ("前の回の返答は受け付けで拒まれた。理由はファイル {path} に在る。先に Read で読み、そこを直した返答を丸ごと"
               "出し直せ（直した所だけを返すな）。")
ROLE_DEF_HEAD = "## お前の役の定義（{agent}）"


def compose(parts, *, reject_file: str = "") -> str:
    """役に読ませる指示書の組み立て（AI を通さない）: 空でない部分を字のまま空行 1 つで繋ぐ。reject_file（前の拒否の理由の
    ファイル）が在れば 1 行目でそのパスを名指す（理由の文そのものは貼らない）。同じ入力からは同じバイト。
    元 works/.shared/core/rolekit.py:168 の写し"""
    out = [REJECT_LINE.format(path=reject_file)] if reject_file else []
    return "\n\n".join(out + [s for s in parts if s])


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
    """doc を JSON で path に置く（一時のファイルから os.replace）"""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def _read(path):
    """JSON のファイルの値。無ければ None。読めない・JSON でなければ ValueError"""
    path = pathlib.Path(path)
    if not path.is_file():
        return None
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
        return _read(v) if str(v) else None
    return v


def out_file(place, nid) -> pathlib.Path:
    return pathlib.Path(place) / OUT_NAME.format(nid)


def output(place, nid):
    """置き場の節 nid の受け付けた返答（無ければ None）。盤面の b.output_of_round(nid, b.round) の代わり"""
    return _read(out_file(place, nid))


def loop_file(place, key) -> pathlib.Path:
    return pathlib.Path(place) / LOOP_NAME.format(key)


def loop_value(place, key):
    """置き場の loop の鍵 key の値（無ければ None）。盤面の b.loop_state.get(key) の今の周の値の代わり"""
    return _read(loop_file(place, key))


def snapshot(place, name: str, repo) -> pathlib.Path:
    """読むだけの役を起こす前に、作業ツリーの姿（accept.tree_state）を置き場の name に書き、パスを返す。take(…, snapshot_name=name)
    がこれと今の作業ツリーを比べる。元 works/.shared/core/entry.py:1231（b.work(name) を置き場のパスに）"""
    import accept
    return write_json(pathlib.Path(place) / name, accept.tree_state(pathlib.Path(repo)))


def tree_moved_since(place, name: str, repo) -> str:
    """置き場の name の写しと今の作業ツリーの違いを述べる文（同じなら空）。写しが無い・形が違うのは snapshot が走っていない
    回す側の誤りで ValueError。元 works/.shared/core/entry.py:1240（b.work(name) を置き場のパスに、BoardGap を ValueError に）"""
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
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, pathlib.Path(repo))
    if not moved:
        return ""
    return "この役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（" + "・".join(moved) + "）"


def take(place, nid: str, reply: dict, repo, *, snapshot_name: str | None = None) -> dict:
    """役の返答を置き場に受ける: snapshot_name が在れば読むだけの役の写しと今の作業ツリーを比べ、違えば
    {ok: False, reason: READONLY_MOVED + 文}。同じなら返答を out_file(place, nid) に置いて {ok: True, reply_file}。
    元 works/.shared/core/entry.py:1262 の take のうち、写しの比べと出力の置きだけ（盤面の規則の照らし vet と settle は持ってこない。
    返答の形は実行基盤の出力の型が照らす）"""
    if snapshot_name:
        moved = tree_moved_since(place, snapshot_name, repo)
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
    """範囲の欄の在る承認済みの修正案の項目（planmarks.scoped の時だけ。修正案の無い run・範囲の欄の無い控えは空）。全部の項目を
    番号のまま写して返し、裁定で外れた項目（conflict.held_item）には held を、単位の一部だけが外れた項目には held_units を足す
    （裁定は置き場 place の conflicts.json）。items は planmarks.approved_items の形の値か、それを返す口か、その JSON のパス。
    口が凍結の印との食い違い（planmarks.FieldsBroken）を出せば conflict.fields_broken の道（by の印の文の ValueError。既定は
    差分の審査の段 stopby.DELTA）。元 works/.shared/core/refix.py:340（盤面の planmarks.scoped_items(b) を読んだ）"""
    import copy
    import conflict
    import planmarks
    import stopby
    by = by or stopby.DELTA
    try:
        items = _given(items)
    except planmarks.FieldsBroken as e:
        raise conflict.fields_broken(None, e, by=by) from None
    items = copy.deepcopy(items) if planmarks.scoped(items) else []
    held = conflict.held_by_rulings(place) if items else {}
    for it in items:
        why = conflict.held_item(it.get("unit_keys"), held)
        some = conflict.held_units(it.get("unit_keys"), held)
        if why:
            it["held"] = why
        elif some:
            it["held_units"] = some
    return items


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
