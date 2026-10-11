"""差分の審査（delta）と 2 往復の手直し（refix）の口（線 A の仕様 3.3・3.4。計画 Task 13）。

差分を切り（run の始めの版、2 回目は 1 回目に固めた修正後の姿から、今の作業ツリーの姿まで。未追跡のファイルも）、役に見せる材料を
置き場（fix の run の作業のファイルを置くフォルダ。scripts が渡す）に書き、役の返答を照らして置き場に受ける。手直しの義務は
置き場に受けた審査の返答から組む（fixboard._owed_rows）。節の名前は DELTA_PASSES からだけ引く（passes()）。

- passes():                  {n: {cut, review, owed, fix, state_key, owed_key}}（DELTA_PASSES から）
- fix_delta(b):              1 回目の修正の差分（置き場の loop-fix_delta.json。{file, files, rev, base}）か None
- cut(board, n, repo, base_rev, …): n 回目の審査役を起こす前の支度。差分を切って置き場の loop-<state_key>.json に置き、
                             差分のファイルと触ったファイルを返し、役に見せる材料（brief）を書き、読むだけの役の前の作業ツリーの写しを撮る
- accept_review・accept_fix: 役の返答を置き場に受ける（fixboard.take。審査は読むだけの役の写しと比べる。手直しは先に修正案の項目の
                             範囲で変更を照らして外れを拒み（planrange.check_paths。修正の段と同じ決まり）、書き込みの
                             記録と申告（欄 bash_writes）に突き合わせ、どちらにも無い変更を拒む）。1 回目の審査は準拠と品質の 2 判定の欄
                             （deltamarks）を承認済みの修正案の項目（fixboard._plan_items）と照らし、欠けと誤りは受けずに拒み、
                             通れば欄を外して受け、受けた時だけ欄を置き場の delta-verdicts.json に控える
- brief_ties(ties):          手直しの役の brief の穴ごとの枝の名札の欄（名札は fixboard.hole_ties。線の木の段 4a）

作業ファイル（置き場 b のフォルダ）: review<n>-snapshot.json（計画の予約の名）・review<n>-brief.json（役に見せる材料: その節に
読ませる値（fixboard.NODE_READS）と、人の方針 {paste, path}。審査役の brief には、変わったファイルのうち守りのファイル
（protect.hits）の protected_files も、1 回目の審査役の brief には修正の差分に当てたレンズの行（lens.brief_rows）の lens も
（手直しの差分にはレンズが当たらないので 2 回目には載せない）。
1 回目の審査役の brief には範囲の欄の在る承認済みの修正案の項目 plan_items（fixboard._plan_items。無ければ空。裁定で外れた項目は held
つき）と直す裁定が広げたパス ruled_paths と直した側の報告 fix_report（修正の返答の changes・not_done。無ければ空）も載せる）・
差分 <state_key>.patch・状態 loop-<state_key>.json・受けた返答 out-<節>.json（fixboard.out_file）。
支度は前の試みの自分の出力（brief・受けた審査の返答・1 回目の審査の 2 判定の控え delta-verdicts.json）を先に消す——新しい
審査の義務が前の審査の穴を数えない（darkfactory の自分食いで 1 本目の blk-delta が踏んだ形）。
"""
import functools
import json
import os
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:   # 写しの engine の置き場（carry.py と同じ足し方）
    sys.path.insert(0, str(_CORE / "graphloops"))
import conflict  # noqa: E402
import deltamarks  # noqa: E402
import fixboard  # noqa: E402
import holeties  # noqa: E402
import leftovers  # noqa: E402
import lens  # noqa: E402
import planrange  # noqa: E402
import protect  # noqa: E402
import recount  # noqa: E402
import stopby  # noqa: E402  （L1。止めの理由の住処）
import writes  # noqa: E402

PASS_KEYS = ("cut", "review", "owed", "fix", "state_key", "owed_key")
# 修正差分の往復の表（元 works/.shared/core/graphloops/rules/review-loop.py:551 の DELTA_PASSES の写し。節の名前の対応はここだけ）
DELTA_PASSES = {1: {"state_key": "fix_delta", "cut": "p3.fix_delta", "review": "p3.delta_review", "owed": "p3.delta_owed",
                    "owed_key": "delta_owed", "fix": "p3.delta_fix"},
                2: {"state_key": "fix_delta2", "cut": "p3.fix_delta2", "review": "p3.delta_review2", "owed": "p3.delta_owed2",
                    "owed_key": "delta_owed2", "fix": "p3.delta_fix2"}}
REVIEW_ROLE = {1: "review", 2: "review2"}   # 審査役の名
FIX_ROLE = {1: "refix", 2: "refix2"}        # 手直しの役の名
# 手直しの変更が承認済みの修正案の項目の範囲から外れた時の拒否の頭（planrange.check_paths の行を続ける。修正の段と同じ決まり）
SCOPE_REJECT = ("手直しが承認済みの修正案の項目の範囲から外れた（項目の範囲の外で変えてよいのは、材料の ruled_paths と、範囲の相談で"
                "合意したパス・テストの変更の許しのパスだけ。外れた変更を戻して返答を丸ごと出し直せ。試験を回して出来たファイル"
                "（キャッシュ・結果の XML）も消せ。範囲の外が要る穴は直さずに declared で残し、how に理由を書け）: ")
WRITES_LOG = "writes.jsonl"   # 書き込みの記録（Edit・Write の行）の置き場の既定の名。無ければ記録の無い run（writes.NO_RECORD）
PLAN_REVIEW = "p2.plan_review"   # 事前審査の節（穴の unit_keys。塞がっていない検算を枝に結ぶ）


@functools.lru_cache(maxsize=1)
def _table() -> tuple:
    """DELTA_PASSES の (n, ((鍵, 値), …)) の並び"""
    return tuple((n, tuple((k, p[k]) for k in PASS_KEYS)) for n, p in DELTA_PASSES.items())


def passes() -> dict:
    """DELTA_PASSES を {n: {cut, review, owed, fix, state_key, owed_key}} にする（節の名前はここ 1 か所で引く）"""
    return {n: dict(kv) for n, kv in _table()}


def _pass(n) -> dict:
    ps = passes()
    if n not in ps:
        raise ValueError(f"差分の往復 {n!r} は DELTA_PASSES に無い（{sorted(ps)}）")
    return ps[n]


def snapshot_name(n: int) -> str:
    """n 回目の審査役を起こす前の作業ツリーの写し（計画の予約の名 review1-snapshot.json・review2-snapshot.json）"""
    return f"review{n}-snapshot.json"


# ---------------------------------------------------------------- 置き場の読み
def fix_delta(b) -> dict | None:
    return fixboard.loop_value(b, _pass(1)["state_key"])


def _write_text(path: pathlib.Path, text: str) -> pathlib.Path:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def _write_json(path: pathlib.Path, doc) -> pathlib.Path:
    return _write_text(path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")


def _drop_stale(b, *names):
    """前の試みの自分の出力を消す（置き場の作業ファイルの names）"""
    for p in [pathlib.Path(b) / x for x in names]:
        p.unlink(missing_ok=True)


def _cut_delta(b, n: int, repo: pathlib.Path, rev: str) -> dict:
    """n 回目の差分（版 rev → 今の作業ツリーの姿）を切って置き場に置く: 作業ツリーの姿（未追跡の新しいファイルも。.gitignore に
    当たる物は除く）を木に固め（leftovers.snapshot）、git diff を <state_key>.patch に、{file, files, rev（固めた木）, base}
    を loop-<state_key>.json に書いて返す。git が効かなければ leftovers.Unreadable。
    元 works/.shared/core/graphloops/rules/review-loop.py:1567 の fix_delta（盤面の機械の節。周の頭に固めた版から）"""
    key = _pass(n)["state_key"]
    snap = leftovers.snapshot(repo)
    raw = leftovers.git(repo, "diff", rev, snap, text=False)
    files = leftovers.git_names(repo, "diff", "--name-only", rev, snap)
    f = pathlib.Path(b) / f"{key.replace('_', '-')}.patch"
    f.write_bytes(raw)
    d = {"file": str(f), "files": files, "rev": snap, "base": rev}
    fixboard.write_json(fixboard.loop_file(b, key), d)
    return d


# ---------------------------------------------------------------- 支度（役を起こす前）
def cut(board: pathlib.Path, n: int, repo: pathlib.Path, base_rev: str = "", *, plan_review=None, fix_reply=None,
        items=None, policy=None) -> dict:
    """n 回目の差分の審査役を起こす前の支度。差分の起点（1 回目は run の始めの版 base_rev、2 回目は 1 回目に固めた修正後の姿）が
    無い・差分を切れないなら {ok: False, reason}（配線の誤り）。在れば、前の試みの自分の出力を消し、差分を切って置き場に置き
    （_cut_delta）、役に見せる材料を review<n>-brief.json に書き、作業ツリーの写し（review<n>-snapshot.json）を撮って
    {ok: True, files, diff_file, rev, brief_file, must} を返す。材料の値は呼び手が渡す（値か、置き場に置いた JSON のパス）:
    plan_review（事前審査の返答）・fix_reply（修正役の返答）・items（承認済みの修正案の項目。planmarks.approved_items の形か、それを
    返す口）・policy（人の方針 {paste, path}。無ければ両方空）。1 回目は修正案の欄の控えが凍結の印と食い違えば、差分の審査の段の印
    stopby.DELTA の文で控えを名指す ValueError（conflict.fields_broken）"""
    p = _pass(n)
    if n == 1:
        rev = base_rev
        if not rev:
            return {"ok": False, "reason": "差分の起点の版が無い（run の始めの版 base_rev を渡す）"}
    else:
        rev = (fixboard.loop_value(board, _pass(n - 1)["state_key"]) or {}).get("rev")
        if not rev:
            return {"ok": False, "reason": f"置き場に loop.{_pass(n - 1)['state_key']} が無い（{n - 1} 回目の差分を切っていない）"}
    brief_name = f"review{n}-brief.json"
    _drop_stale(board, brief_name, fixboard.out_file(board, p["review"]).name)
    if n == 1:
        (pathlib.Path(board) / deltamarks.VERDICTS_FILE).unlink(missing_ok=True)
    try:
        d = _cut_delta(board, n, pathlib.Path(repo), rev)
    except leftovers.Unreadable as e:
        return {"ok": False, "reason": f"差分を切れない: {e}"}
    values = {f"loop.{p['state_key']}": d, f"out.{PLAN_REVIEW}": fixboard._given(plan_review),
              f"out.{recount.FIX_NODE}": fixboard._given(fix_reply)}
    if n > 1:
        values[f"out.{_pass(n - 1)['fix']}"] = fixboard.output(board, _pass(n - 1)["fix"])
    pol = fixboard._given(policy) or {"paste": "", "path": ""}
    doc = {"node": p["review"], "diff_file": d["file"], "files": d.get("files") or [], "rev": d.get("rev"),
           "reads": fixboard._brief(p["review"], values), "policy": pol}
    try:   # 変わったファイルのうち守りのファイル（protect）。審査役が検査を緩める変更を見る材料（最後の人の関所にも必ず出る）
        doc["protected_files"] = protect.hits(doc["files"])
    except protect.Broken as e:
        doc["protected_files"], doc["protected_files_error"] = [], str(e)
    if n == 1:
        try:
            doc["lens"] = lens.brief_rows(board)
        except ValueError as e:
            doc["lens"], doc["lens_error"] = [], str(e)
        doc["plan_items"] = fixboard._plan_items(board, items)
        doc["ruled_paths"] = conflict.ruled_paths(board)
        doc["fix_report"] = fixboard._fix_report(fix_reply)
    brief = _write_json(pathlib.Path(board) / brief_name, doc)
    fixboard.snapshot(board, snapshot_name(n), repo)
    return {"ok": True, "files": list(d.get("files") or []), "diff_file": d["file"], "rev": d.get("rev") or "",
            "brief_file": str(brief), "must": [str(brief), d["file"]]}


def brief_ties(ties: list) -> list[dict]:
    """手直しの役の brief の ties の欄: 穴ごとの {key, branches（人が読む枝の名）, note（holeties.note）, via}"""
    return [{"key": t["key"], "branches": [holeties.label(x) for x in t["branches"]], "note": holeties.note(t),
             "via": t["via"]} for t in ties]


# ---------------------------------------------------------------- 受け付け
def accept_review(reply: dict, board: pathlib.Path, base_rev: str, repo: pathlib.Path, *, n: int, items=None) -> dict:
    """n 回目の審査役の返答（読むだけの役。cut が撮った写しと今の作業ツリーを比べる）。fixboard.take の返り {ok, reply_file}
    に、受けた時は owed（手直しが答える義務の数。fixboard._owed_rows）を足す。節が deltamarks.NODES に在れば、先に 2 判定の欄を
    承認済みの修正案の項目（items。cut と同じ形）と照らし、欠けと誤りが在れば受けずに {ok: False, reason: deltamarks.REJECT と行}。
    無ければ欄を外した返答を受け、受けた時だけ欄を控える（置けなければ控えを名指す ValueError）。修正案の欄の控えが凍結の印と
    食い違えば conflict.fields_broken の道（差分の審査の段の印 stopby.DELTA の文の ValueError）。faces が穴の並びの形でない返答は
    照らさずに、欄を外して受ける（返答の型は実行基盤の出力の型が照らす。守る 2 つの欄を知らない欄と言わせない）"""
    nid = _pass(n)["review"]
    if nid not in deltamarks.NODES:
        return _owed(fixboard.take(board, nid, reply, repo, snapshot_name=snapshot_name(n)), board, n)
    if deltamarks.malformed(reply):
        return _owed(fixboard.take(board, nid, deltamarks.split(reply)[0], repo, snapshot_name=snapshot_name(n)), board, n)
    gaps = deltamarks.gaps(reply, fixboard._plan_items(board, items))
    bare, verdicts = deltamarks.split(reply)
    if gaps:
        return {"ok": False, "reason": deltamarks.REJECT + "\n" + "\n".join(f"  - {g}" for g in gaps)}
    out = fixboard.take(board, nid, bare, repo, snapshot_name=snapshot_name(n))
    if out.get("ok") is True:   # 受けた時だけ（拒否では置き場の控えも前のまま）
        try:
            deltamarks.save(board, verdicts)
        except Exception as e:   # 書けない・形にできない: 受けた審査に欄が無いまま進ませない
            raise ValueError(f"審査の返答を受けた後で、受け付けが外した欄の控え {deltamarks.VERDICTS_FILE} を置けない"
                             f"（控えの無いまま先へ進ませない）: {type(e).__name__}: {' '.join(str(e).split())}") from None
    return _owed(out, board, n)


def _owed(out: dict, board, n: int) -> dict:
    return {**out, "owed": len(fixboard._owed_rows(board, n))} if out.get("ok") is True else out


def accept_fix(reply: dict, board: pathlib.Path, base_rev: str, repo: pathlib.Path, *, n: int, items=None, log=None,
               skip: tuple = ()) -> dict:
    """n 回目の手直しの役の返答（書く役）。fixboard.take の返り。先に、版 base_rev（run の始めの版。空なら HEAD）からの変更の
    うち修正の段が触ったファイル（1 回目の差分の files。その段の受け付けが照らした）の外を、承認済みの修正案の項目（items）の
    範囲で照らす（planrange.check_paths。修正の段と同じ決まり。この役は単位を申告しないので全部の項目の範囲の和と out_of_scope で
    見る。修正案の範囲の欄が無い run は照らさない）。外れが在れば受けずに {ok: False, reason}（同じ会話で直させる）。次に変更を
    書き込みの記録 log（Edit・Write の行。既定は置き場の WRITES_LOG）と申告（欄 bash_writes）に突き合わせ（writes.check。skip は
    除くパスの頭）、どちらにも無い変更を拒む（keep-essence の 5。修正の段と同じ）。通れば欄 bash_writes を外した返答を置き場に受け、
    記録の無い run は知らせを置き場の trace.jsonl に残す"""
    rev = fixboard.base_rev(None, base_rev)
    paths = writes.changed(repo, rev)
    fixed = set((fix_delta(board) or {}).get("files") or [])
    bad, _note = planrange.check_paths(board, [p for p in paths if p not in fixed], items=items, ruled=True, by=stopby.REFIX)
    if bad:
        return {"ok": False, "reason": SCOPE_REJECT + "\n" + "\n".join(f"  - {x}" for x in bad)}
    got = writes.check(reply, repo, paths, pathlib.Path(log) if log else pathlib.Path(board) / WRITES_LOG, skip=tuple(skip))
    if got["problems"]:
        return {"ok": False, "reason": "\n".join(got["problems"])}
    out = fixboard.take(board, _pass(n)["fix"], got["reply"], repo)
    if out.get("ok") is True:   # 受けた時だけ（拒否では置き場を前のままにする）
        writes.trace(board, FIX_ROLE[n], got)
    return out
