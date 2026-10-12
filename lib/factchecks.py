"""修正の受け付けの事実の確かめ（blk-fix。受け付けの script（fix-accept・fix-ruled-accept）と、修正役の事前の確かめが同じ口で回す。設計
docs/plans/2026-10-06-ask-planner.md）。規則はここ 1 か所で、受け付けはここから import する。
board はどの口でも fix の run の置き場のフォルダ（scripts が渡す。範囲の相談の合意の trace.jsonl・1 回目に受け付けた返答の控え・
TDD の輪の状態 tdd-<k>/ を置く所）。返答の番号を名前に戻す仕事は呼び手（script）が先に済ませ、ここは名前の返答を受ける。

口（受け付けの手順の番号）:
- fix_unit_keys(reply, board, owed, ...): 返答の changes の単位の名前と直す義務（fixboard.fix_duty）（手順 0）
- check_writes: 書き込みの出どころ（-2）。log は書き込みの記録（既定は置き場の WRITES_LOG）、skip は除くパスの頭
- check_frozen: TDD の輪で凍ったテストのファイル（1b）。agreed は範囲の相談の合意の行（None は置き場の trace。conflict.agreed）
- check_plan_scope: 承認済みの修正案の範囲（1d）。agreed は同じ。items は承認済みの修正案の項目（planmarks.approved_items の
  形の値か口。None は照らさない）。ask は拒否の頭で相談を先の道に言うか（None は consult_place の相談の控えで決める）
- precheck(cfg, reply, items=, skip=): 修正役が sandbox の中の Bash で返答の前に回す事前の確かめ。上の 3 つ（凍結・書き込み・範囲）だけを、
  試験を回さずに当てる（変更に当たる試験と事後の関門の束は受け付けだけ）。修正役の並べの枝の控え（fixlanes が書く）は repo が単位の
  worktree で、since（枝の今の項目の頭の木。枝の支度が回ごとに書き直す）を持つ（枝の確かめと同じ照らし）。置き場は読むだけ。
  範囲の相談の合意は、修正の輪の確かめの節が置き場の trace に書いた物（conflict.agreed）を受け付けと同じに読む。
  返り {ok, rejects: [{check, text}]}
- place_items(place): 置き場の修正案の控え（plan-fields.json と凍結の印・p2.fix_plan.json・judgment.json）から承認済みの修正案の
  項目を引く口（planmarks.approved_items。check_plan_scope の items に渡す）
- main(argv): `<python> factchecks.py <相談の控え> [--reply <下書きの返答の JSON>]`。控えの board（置き場）の修正案の控えから項目を
  引き（place_items）、控えの skip（除くパスの頭。無ければ ()）を渡して precheck を回す。終了コード 0（通る）・1（拒否の行が在る）・
  2（回す側の誤り）。出力は precheck の返りの 1 行
"""
import argparse
import json
import os
import posixpath
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）
_CORE = Path(__file__).resolve().parents[2] / ".shared" / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
_LIB = str(Path(__file__).resolve().parent)
if _LIB not in sys.path:
    sys.path.append(_LIB)

import consult  # noqa: E402   範囲の相談の控え（同じブロックの lib）
import conflict  # noqa: E402
import fixboard  # noqa: E402  （直す義務・突き合わせの起点の版）
import planmarks  # noqa: E402  （承認済みの修正案の項目の読み口）
import planscope  # noqa: E402
import tddloop  # noqa: E402
import writes  # noqa: E402

WRITES_LOG = "writes.jsonl"   # 書き込みの記録（Edit・Write の行）の置き場の既定の名（refix.WRITES_LOG と同じ）。無ければ記録の無い run（writes.NO_RECORD）


def fix_unit_keys(reply: dict, board: Path, owed, *, withheld_by=None, returned=()):
    """(changes[].unit_key の列（changes と同じ順）, 直す義務の key の集合, 直す義務から外れた単位 {key: 理由})（fixboard.fix_duty。
    owed・withheld_by・returned はそこへ渡す）。changes の形が崩れている・単位の名前が文字列でないときは None（検査せず受け付けの
    型の照らしに任せる）。返答の番号は呼び手が名前に戻してから渡す"""
    rows = reply.get("changes") if isinstance(reply, dict) else None
    if not isinstance(rows, list) or not all(isinstance(c, dict) for c in rows):
        return None
    keys = [c.get("unit_key") for c in rows]
    if not all(isinstance(k, str) for k in keys):
        return None
    return (keys, *fixboard.fix_duty(board, owed, withheld_by=withheld_by, returned=returned))


def check_writes(reply: dict, board: Path, base_rev: str, repo: Path, state: str, *, log=None, since=None,
                 made=(), skip: tuple = ()) -> dict:
    """書き込みの出どころ（writes.check。欄 bash_writes を外した返答は reply に）。実行器が作ったファイルは run の全部の輪の物を
    外す（tddloop.suite_made_all）。盤面は書かない（申告の記録は writes.check が足す）。
    書き込みの記録は log（既定は置き場の WRITES_LOG）。skip は除くパスの頭（writes.check）。
    修正役の並べの枝（fixlanes）は repo に単位の worktree を渡し、log（run の作業ツリーの記録。単位の worktree の
    書き込みも run の作業ツリーの記録に載る）と since（見る変更の起点。枝の今の項目の頭の木。前の段が run の作業ツリーで書いた物は
    単位の worktree の実パスの記録を持たず、同じ枝の前の項目が書いた物はその項目の確かめが見たので見ない）と made（枝の実行器が作ったファイル）を渡す"""
    made = set(tddloop.suite_made(state)) | tddloop.suite_made_all(board) | set(made)
    rev = fixboard.base_rev(None, base_rev)
    return writes.check(reply, repo, [p for p in _changed(repo, rev, since) if p not in made],
                        Path(board) / WRITES_LOG if log is None else Path(log), skip=tuple(skip))


def _changed(repo, rev: str, since=None) -> list:
    """見る変わったパス: since（修正役の並べの枝の今の項目の頭の木）が在ればそこからの変更（writes.changed_from。項目の頭は HEAD でも
    index でもない木）、無ければ版 rev からの変更（writes.changed）"""
    return writes.changed_from(repo, since) if since else writes.changed(repo, rev)


def _loop_states(board, state) -> list:
    """run の全部の輪の状態のファイル（盤面の tdd-<k> の番号の順。今の輪 state は最後。無ければ空）"""
    if not state:
        return tddloop.states(board)
    return [p for p in tddloop.states(board) if p.resolve() != Path(state).resolve()] + [state]


def check_frozen(board: Path, state: str, repo: Path, pass_: str, agreed=None, asks=None, base_rev: str = "") -> list:
    """手順 1b: 凍ったテストのファイル（tddloop.frozen_problems）を run の全部の輪で見た拒否の文。今の輪（state）は今どおり、前の輪
    （1 回目の修正の段の輪）は今の輪の状態の handoff の木（since）からの変更で見て、直した項目の単位（テストの変更の許しの単位の行。conflict.permitted_units）の前の
    輪の受け入れのテストの関数（tddloop.test_spans）の中の変更は通す。テストの変更の許し（conflict.ruled_test_limits）は輪ごとに、
    凍結の検査が比べる木で修正案の行を引き直す（今の輪は輪の後の木、前の輪は since の木。tddloop.frozen_source）。輪が赤→緑を
    確かめた書き換えは、どの輪の物でも許しから外す。今の輪が無い（2 回目の段の輪が走らなかった）時、前の輪は輪の後の木で見る。
    裁定の範囲は今の輪だけ pass_ で決め（1 回目の受け付けは含めない）、前の輪はいつも含める（前の段で裁いた fix_test_scope の
    直しは、今の段の受け付けが first でも許し）。輪が 1 つも無ければ空。盤面は書かない。
    範囲の相談の合意の範囲の行は修正前の版（base_rev。呼び手が fixboard.base_rev で選ぶ）の行で、凍結の検査が比べる木の行へ
    移して読む（conflict.test_permits の base。読む木は 1 つ）。
    asks に list を渡せば、相談に回せる凍ったファイル（範囲の外の塊が全部、輪の受け入れのテストでない既存のテストの関数の幅に
    収まる物。tddloop.frozen_asks）の頼み {path, tests, line, ref} を足す（line は返す文のどれかと同じ。tests の行は修正前の版の行）"""
    loops = _loop_states(board, state)
    if not loops:
        return []
    b = board
    skip = [i for p in loops for i in tddloop.verified_rewrites(p)]
    rev = fixboard.base_rev(None, base_rev)
    before = tddloop.rev_source(repo, rev)

    def allowed(source, rulings):
        return conflict.ruled_test_limits(b, rulings=rulings, source=source, skip_ids=skip, agreed_rows=agreed, base=before)
    now = allowed(tddloop.frozen_source(state, repo), pass_ == "ruled") if state else []
    out = tddloop.frozen_problems(state, repo, now) if state else []
    if asks is not None and state:
        try:
            asks += tddloop.frozen_asks(state, repo, now, rev=rev)
        except tddloop.Broken:   # 状態が読めないのは frozen_problems の側が拒む。頼みは作れないだけ
            pass
    old = loops[:-1] if state else loops
    if old:
        since = tddloop.load_state(state).get("handoff") if state else None
        amended = conflict.permitted_units(b)
        for p in old:
            lims, spans = allowed(tddloop.frozen_source(p, repo, since=since), True), tddloop.test_spans(p, amended)
            out += tddloop.frozen_problems(p, repo, lims, since=since, skip_spans=spans)
            if asks is not None:
                try:
                    asks += tddloop.frozen_asks(p, repo, lims, since, spans, rev=rev)
                except tddloop.Broken:
                    pass
    return out


def _loop_freeze(board, state) -> tuple:
    """(一番後の輪の frozen_tree, run の全部の輪が凍らせたファイル)。輪が無ければ (None, [])"""
    tree, files = None, set()
    for p in _loop_states(board, state):
        st = tddloop.load_state(p)
        files |= set(st.get("frozen") or {})
        tree = st.get("frozen_tree") or tree
    return tree, sorted(files)


def check_plan_scope(reply: dict, keys: list, board: Path, base_rev: str, repo: Path, state: str, pass_: str,
                     agreed=None, ask=None, since=None, made=(), *, items=None, consult_place=None) -> tuple:
    """承認済みの修正案の項目と差分の照らし（planscope.check）。行は changes と keys（単位の名前）を並べ、files を根からの相対に
    揃えた物。変わったパスは版からの変更（writes.changed）から実行器が作ったファイル（tddloop.suite_made）を除いた物。TDD の輪が
    凍らせたファイル（輪の状態の frozen と frozen_tree）は planscope.check に渡し、欠けは版からの
    差分の全部で、修正役に問う外れと余分は凍った後に変えた分だけで見させる。
    返り (拒否の行（最初の行の頭に planscope.reject_head）, 記録)。盤面は書かない（控えの食い違いで止めるのは planscope.check）。
    items は承認済みの修正案の項目（planmarks.approved_items の形の値か口。修正案の無い run は None で、照らさない）。
    頭は、範囲の相談がこの段に在れば相談を先の道に言う。ask が None なら consult_place（相談の控えの在るフォルダ）の控えで決める
    （consult.offered。None なら言わない）。
    凍らせたファイルと実行器が作ったファイルは run の全部の輪の物（_loop_freeze・tddloop.suite_made_all）で、凍った後は一番後の
    輪の frozen_tree から見る（前の輪の後に 1 回目の段と後の輪が書いた物を、2 回目の修正役のせいにしない）。
    修正役の並べの枝（fixlanes）は repo に単位の worktree を、since に枝の今の項目の頭の木を渡す: 照らす変わったパスはその項目が変えた物だけ
    （同じ枝の前の項目が変えたファイルを、後の項目の out_of_scope で照らさない。run 97fd532f。版との比べの中身は今どおり版から）。made は枝の実行器が作ったファイル"""
    b = board
    rows = [{"unit_key": k, "files": sorted(declared_files([c], repo))} for c, k in zip(reply.get("changes") or [], keys)]
    tree, frozen = _loop_freeze(board, state)
    made = set(tddloop.suite_made(state)) | tddloop.suite_made_all(board) | set(made)
    rev = fixboard.base_rev(None, base_rev)
    paths = [p for p in _changed(repo, rev, since) if p not in made]
    problems, note = planscope.check(rows, b, repo, rev, paths, pass_=pass_, loop_tree=tree, frozen=frozen,
                                     agreed=agreed, items=items)
    if problems:
        if ask is None:
            ask = consult.offered(consult_place, pass_)
        problems = [planscope.reject_head(ask) + problems[0], *problems[1:]]
    return problems, note


def split_overflow(texts, overflow) -> tuple:
    """拒否の文 texts のうち、はみ出しの行（overflow の各行の line。planscope の記録・凍ったファイルの頼み・事後の関門の頼みの形）を
    含む文（頭に reject_head が付いても外れない）を外す。返り (残りの文, 文が当たったはみ出し)。範囲の外の変更は、拒まずに相談に
    回すか、機械が戻す物（修正の輪の受け付け）。修正役の並べの枝は枝の拒否に積まず、結末に名指して本線の受け付けに任せる"""
    rest, hit = [], []
    for text in texts:
        rows = [o for o in overflow if isinstance(o, dict) and o.get("line") and o["line"] in text]
        if rows:
            hit += [o for o in rows if o not in hit]
        else:
            rest.append(text)
    return rest, hit


def declared_files(rows, repo) -> set:
    """changes の行の files を、リポジトリの根からの相対パスに揃えた集合"""
    out = set()
    for c in rows:
        for f in c.get("files") or []:
            if isinstance(f, str) and f.strip():
                f = f.strip()
                out.add(posixpath.normpath(os.path.relpath(f, repo) if os.path.isabs(f) else f))
    return out


def _read_json(path):
    """path の JSON（無ければ None。読めなければ ValueError）"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise ValueError(f"置き場のファイル {path} が読めない: {e}") from None


def place_items(place):
    """置き場 place の承認済みの修正案の項目を返す口（引数なし。planmarks.approved_items の形の値か、修正案の無い run は None）。
    修正案の役の返答は置き場の <planmarks.NODE>.json（{"plan": [...]}）、判定は judgment.json、凍結した欄は planmarks.save が置いた
    plan-fields.json と凍結の印（fixboard.plan_view で planmarks に渡す）。控えが凍結の印と食い違えば planmarks.FieldsBroken
    （planscope.check が conflict.fields_broken の ValueError にする）。元 entry.open_board の盤面から planmarks.approved_items(b)
    を読んだ所（元 blk-fix/lib/factchecks.py:184 の planscope.check の中）"""
    def items():
        plan = _read_json(Path(place) / f"{planmarks.NODE}.json")
        if plan is None:
            return None
        return planmarks.approved_items(fixboard.plan_view(place, plan, _read_json(Path(place) / "judgment.json")))
    return items


def precheck(cfg: dict, reply=None, *, items=None, skip: tuple = ()) -> dict:
    """事前の確かめ（モジュールの頭）。cfg は相談の控え（consult.load_config。board・repo・pass・base_rev・tdd_state と、修正役の
    並べの枝の控えなら since・log）。items は承認済みの修正案の項目（check_plan_scope）、skip は除くパスの頭（check_writes）"""
    board, repo = Path(cfg["board"]), Path(cfg["repo"])
    state, pass_, base_rev = cfg.get("tdd_state") or "", cfg.get("pass") or "first", cfg.get("base_rev") or ""
    log, since = cfg.get("log") or None, cfg.get("since") or None   # 修正役の並べの枝の控え（fixlanes が書く）
    reply = reply if isinstance(reply, dict) else {"changes": []}
    agreed = conflict.agreed(board)
    found = [("frozen", t) for t in check_frozen(board, state, repo, pass_ if pass_ in ("first", "ruled") else "first",
                                                 agreed=agreed, base_rev=base_rev)]
    wrote = check_writes(reply, board, base_rev, repo, state, log=log, since=since, skip=skip)
    found += [("writes", t) for t in wrote["problems"]]
    keys = [c.get("unit_key") for c in wrote["reply"].get("changes") or [] if isinstance(c, dict)]   # 返答は単位の名前で書く
    scope, _ = check_plan_scope(wrote["reply"], keys, board, base_rev, repo, state,
                                pass_ if pass_ in ("first", "ruled") else "first", agreed=agreed, ask=True, since=since,
                                items=items)
    found += [("scope", t) for t in scope]
    return {"ok": not found, "rejects": [{"check": c, "text": t} for c, t in found]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="factchecks.py", description="受け付けの事実の確かめ（凍結・書き込み・範囲）を試験なしで回す")
    ap.add_argument("config", help="相談の控え（指示書に書かれたパス）")
    ap.add_argument("--reply", default="", help="下書きの返答の JSON のファイル（無ければ changes の無い返答として見る）")
    a = ap.parse_args(argv)
    try:
        cfg = consult.load_config(a.config)
        reply = json.loads(Path(a.reply).read_text(encoding="utf-8")) if a.reply else None
        out = precheck(cfg, reply, items=place_items(cfg["board"]), skip=tuple(cfg.get("skip") or ()))
    except (ValueError, OSError, KeyError) as e:
        print(f"factchecks: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    sys.exit(main())
