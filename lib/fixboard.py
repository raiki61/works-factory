"""fix の置き場（run の作業のファイルを置くフォルダ）の読み書きの助けのうち、2 つ以上の使い手が lib から呼ぶ物（fix.md 1.5.2 の名。
README 9.3 の KEEP。integration.md 4.3-1）。使い手は KEEP の writes・conflict・planbrief・r1〜r4 の eyekit と、fix・delta-review・
independent-design の src/。fix だけが使う物は fix の src/board.py、差分の審査と手直しの材料は delta-review、レンズは lens の src/ に在る。

- trace(place, op, **kw)・trace_rows(place)・TRACE_FILE: 置き場の trace.jsonl に {"op": op, **kw} を 1 行足す・読む
- read_json・write_json・write_text: 置き場のファイルの読み書き
- marks_view(place, round_=1)・plan_view(place, plan, judgment, round_=1): planmarks の凍結した欄と承認済みの修正案の読み口に渡す
  読むだけの形（dir と round と値だけ）
- allowed_test_rows・_allowed_row・child_allowed_rows・ALLOWED_SOURCES・scope_brief: テストの変更を許す行（出どころの語つき）と、
  役の brief の範囲の欄（planrange.scope の 1 つの口から組む）
- overflow_trace(place, trail, *, agreed, guards, gate_tests): はみ出しを認めた物を trace の行に名指す（値は呼び手が渡す）
- run_diff・DIFF_EMPTY・diff_file・FIX_IN_DIFF_CORE: 直しの差分とその置き場
- pr_revs(repo, base, head)・pr_diff(repo, base_sha, head_sha, skip, *opts)・pr_added_lines(repo, base_sha, head_sha, skip):
  審査する変更（起点 → 修正前の HEAD）の差分と、それが足した行（目の起点の訳と独立設計の制約の印が引く）
- HUMAN_FACE_KINDS・UNIT_STATUSES・FIXED・GIVEN_UP・NOT_DONE・UNIT_LEFT・HANDOFF_HEAD: 単位の状態の語と人に回す穴の種類
- accept_out・round_number・snapshot・touched_since・undeclared_writes・UNDECLARED: 受け付けの出口の形・輪の回・作業ツリーの木と
  そこからの変更・申告の無い書き込みの拒否の文

外のパッケージは使わない（lib のほかの部品は、使う関数の中で import する）。
"""
import json
import os
import pathlib
import types

import jsonfile
import oneline
import policy
import rolekit

TRACE_FILE = "trace.jsonl"


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


def snapshot(place, name: str, repo) -> pathlib.Path:
    """読むだけの役を起こす前に、作業ツリーの姿（accept.tree_state）を置き場の name に書き、パスを返す。take(…, snapshot_name=name)
    がこれと今の作業ツリーを比べる。元 works/.shared/core/entry.py:1231（b.work(name) を置き場のパスに）"""
    import accept
    return write_json(pathlib.Path(place) / name, accept.tree_state(pathlib.Path(repo)))


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


def touched_since(repo, tree: str, skip=()) -> list:
    """木 tree（run の始めの木）から作業ツリーの今の姿（未追跡を含む・無視される物を除く）で変わったパス。除くパスの頭 skip の
    下は数えない。元 works/blk-fix/scripts/assert_changed.py の touched（版との git diff と未追跡を、始めの木との差に替えた）"""
    import leftovers
    now = leftovers.snapshot(repo)
    touched = sorted(set(leftovers.git_names(repo, "diff-tree", "-r", "--name-only", "--no-renames", tree, now)))
    return [p for p in touched if not p.startswith(tuple(skip))]


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
    """許したテストの変更の訳 [{path, permit, source}]（返りの diff の隣の ALLOWED_TESTS_FILE の中身。パスと許しの id の順・重ねない）:
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


HANDOFF_HEAD = "直しの途中で AI が自分で決めずに人に回した物（壊すと分かって通した理由。役だけで決めた代償なので人が確かめる）"


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


# 差分の審査の受け付けが拒む穴の語（元 works/.shared/core/graphloops/rules/review-loop.py:4084-4087）
HUMAN_FACE_KINDS = ("regression", policy.POLICY_KIND)


def write_text(path, text: str) -> pathlib.Path:
    """text を path に置く（一時のファイルから os.replace。フォルダが無ければ作る）"""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


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


ALLOWED_SOURCES = ("plan", "consult", "ruling")   # ALLOWED_TESTS_FILE の source の語: 承認済みの修正案・範囲の相談の合意・裁定
UNIT_STATUSES = (FIXED, GIVEN_UP, NOT_DONE) = ("fixed", "given_up", "not_done")
UNIT_LEFT = (GIVEN_UP, NOT_DONE)   # 直し終えなかった単位の状態
FIX_ACCEPT_BY = "fix-accept"                # 受け付けが単位を人に回した裁定の by（元 accept.py:140 の stopby の名）
FIX_IN_DIFF_CORE = "直しは差分に在り、閉じたかの数え（判定者の問いが直した後の正しい行にも当たる）だけ"   # query_hits_fixed は直してから申し出る（common.md）。conflict.FIX_IN_DIFF も組む
UNDECLARED = ("書き込みの記録が無い run で、作業ツリーの変更が返答の changes[].files にも bash_writes にも無い——直したファイルなら "
              "changes の files に足し、Bash で書いたなら bash_writes にパスと理由を書き、要らない変更なら戻せ: ")


def undeclared_writes(reply: dict, repo, tree: str, *, made=(), skip=()) -> list:
    """書き込みの記録が無い run の書き込みの出どころ（U6 の狭め）: 木 tree（段の頭の木）から作業ツリーの今の姿で変わったパス
    （touched_since。除くパスの頭 skip の下は数えない）のうち、返答の changes[].files にも bash_writes の path にも無く、実行器が
    作った物（made）でもない物を名指す拒否の文（無ければ空の並び）。新しい（今の works は包みの書き込みの記録で縛った）"""
    import itemcommits
    rows = [c for c in (reply or {}).get("changes") or [] if isinstance(c, dict)]
    told = itemcommits.declared_files(rows, repo)
    told |= itemcommits.declared_files([{"files": [w.get("path") for w in (reply or {}).get("bash_writes") or []
                                                  if isinstance(w, dict)]}], repo)
    left = [p for p in touched_since(repo, tree, skip) if p not in told and p not in set(made)]
    return [UNDECLARED + ", ".join(left)] if left else []


JOIN_FILE = "join.json"             # 組を親の木へ戻した結果 {groups, units}（join が書く）


def overflow_trace(place, trail: dict, *, agreed=(), guards=(), gate_tests=()) -> None:
    """受けた回に、はみ出しを相談で認めた物（agreed: 合意の行の origin が accept の id）・機械が戻した物（trail の reverted）・守りの
    テスト（guards: {id, base} の行）・関所の条件の相談で認めた新しいテストのうち今の木に在る物（gate_tests: {id, red_kind} の行）を
    置き場の trace の impact.ACCEPT_OVERFLOW_OP の行に名指す（どれも無ければ書かない）。名指しの字は元 accept.py:715 の traced の中の
    1 行と同じ（報告が 1 件ずつ読む）。値の選び（相談の合意の origin・守りのテスト・在るか）は fix の src/ が持ち、値で渡す
    （integration.md 4.3-1。fix の部品を lib から読まない）"""
    import impact
    gated = [f"{g['id']}（{g.get('red_kind')}）" for g in gate_tests if isinstance(g, dict)]
    guard_rows = [f"{g['id']}: 守りのテスト（base で {g['base']}）" for g in guards if isinstance(g, dict)]
    row = impact.OverflowRow(agreed=list(agreed), reverted=trail["reverted"], guards=guard_rows, gate_tests=gated)._asdict()
    if any(row.values()):
        trace(place, impact.ACCEPT_OVERFLOW_OP, node=FIX_ACCEPT_BY, **row)
