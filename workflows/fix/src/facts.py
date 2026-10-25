"""修正の受け付けの事実の確かめ（blk-fix。受け付けの script（fix-accept・fix-ruled-accept）と、修正役の事前の確かめが同じ口で回す。設計
docs/plans/2026-10-06-ask-planner.md）。規則はここ 1 か所で、受け付けはここから import する。
board はどの口でも fix の run の置き場のフォルダ（scripts が渡す。範囲の相談の合意の trace.jsonl・1 回目に受け付けた返答の控え・
TDD の輪の状態 tdd-<k>/ を置く所）。返答の番号を名前に戻す仕事は呼び手（script）が先に済ませ、ここは名前の返答を受ける。

口（受け付けの手順の番号）:
- fix_unit_keys(reply, board, owed, ...): 返答の changes の単位の名前と直す義務（fixboard.fix_duty）（手順 0）
- check_writes: 書き込みの出どころ（-2）。log は書き込みの記録（既定は置き場の writelog.LOG）、skip は除くパスの頭
- check_frozen: TDD の輪で凍ったテストのファイル（1b）。agreed は範囲の相談の合意の行（None は置き場の trace。conflict.agreed）
- frozen_tests(board, state, pass_): 凍ったテストのファイルと、輪が確かめた書き換えの名指しと、裁定の範囲で凍結が解けない今の輪のファイル
  （check_frozen と修正役の指示書が同じ値を引く）
- check_plan_scope: 承認済みの修正案の範囲（1d）。agreed は同じ。items は承認済みの修正案の項目（planmarks.approved_items の
  形の値か口。None は照らさない）。ask は拒否の頭で相談を先の道に言うか（None は consult_place の相談の控えで決める）
- precheck(cfg, reply, items=, skip=): 修正役が sandbox の中の Bash で返答の前に回す事前の確かめ。上の 3 つ（凍結・書き込み・範囲）と書いた指し（recount.ref_problems）だけを、
  試験を回さずに当てる（変更に当たる試験と事後の関門の束は受け付けだけ）。修正役が変え始めた木 since は受け付けと同じ口
  （fixboard.fixer_head。置き場の段の頭の控え）から読む。置き場は読むだけ。
  範囲の相談の合意は、修正の輪の確かめの節が置き場の trace に書いた物（conflict.agreed）を受け付けと同じに読む。
  返り {ok, rejects: [{check, text}]}
- main(argv): `<python> <block>/src/facts.py <相談の控え> [--reply <下書きの返答の JSON>]`。控えの board（置き場）の修正案の控えから項目を
  引き（fixboard.place_items）、控えの skip（除くパスの頭。無ければ ()）を渡して precheck を回す。終了コード 0（通る）・1（拒否の行が在る）・
  2（回す側の誤り）。出力は precheck の返りの 1 行
"""
import argparse
import functools
import json
import os
import posixpath
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）
if __name__ == "__main__":   # 修正役が事前の確かめのコマンドとして単独で起こす（docs/design/fix.md の 1.5.5。script の頭と同じ）
    # 単独で起こすと Python が自分のフォルダ src/ を頭に置き、lib の同じ名のモジュール（carry など）を隠すので外す
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
    import ports  # noqa: E402,F401  （lib/ を sys.path に足す）

from src import consult  # noqa: E402   範囲の相談の控え（同じブロックの lib）
import conflict  # noqa: E402
from src import board as fixboard  # noqa: E402  （直す義務・突き合わせの起点の版・承認済みの修正案の項目の読み口）
from src import scope as planscope  # noqa: E402
import recount  # noqa: E402  （書いた指しの照らし。受け付けと同じ口）
from src import common  # noqa: E402
import writelog  # noqa: E402
import writes  # noqa: E402



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
                 skip: tuple = ()) -> dict:
    """書き込みの出どころ（writes.check。欄 bash_writes を外した返答は reply に）。実行器が作ったファイルは run の全部の輪の物を
    外す（common.suite_made_all）。盤面は書かない（申告の記録は writes.check が足す）。
    書き込みの記録は log（既定は置き場の writelog.LOG）。skip は除くパスの頭（writes.check）。
    since は見る変更の起点（受け付けと事前の確かめは fixboard.fixer_head の段の頭。前の段が書いた物を修正役に求めない）"""
    made = set(common.suite_made(state)) | common.suite_made_all(board)
    rev = fixboard.base_rev(None, base_rev)
    return writes.check(reply, repo, [p for p in _changed(repo, rev, since) if p not in made],
                        Path(board) / writelog.LOG if log is None else Path(log), skip=tuple(skip))


def _changed(repo, rev: str, since=None) -> list:
    """見る変わったパス: since（修正役が変え始めた木。fixboard.fixer_head）が在ればそこからの変更（writes.changed_from。段の頭は
    HEAD でも index でもない木）、無ければ版 rev からの変更（writes.changed）"""
    return writes.changed_from(repo, since) if since else writes.changed(repo, rev)


def _loop_states(board, state) -> list:
    """run の全部の輪の状態のファイル（盤面の tdd-<k> の番号の順。今の輪 state は最後。無ければ空）"""
    if not state:
        return common.states(board)
    return [p for p in common.states(board) if p.resolve() != Path(state).resolve()] + [state]


def check_frozen(board: Path, state: str, repo: Path, pass_: str, agreed=None, asks=None, base_rev: str = "") -> list:
    """手順 1b: 凍ったテストのファイル（common.frozen_problems）を run の全部の輪で見た拒否の文。今の輪（state）は今どおり、前の輪
    （1 回目の修正の段の輪）は今の輪の状態の handoff の木（since）からの変更で見て、直した項目の単位（テストの変更の許しの単位の行。conflict.permitted_units）の前の
    輪の受け入れのテストの関数（common.test_spans）の中の変更は通す。テストの変更の許し（conflict.ruled_test_limits）は輪ごとに、
    凍結の検査が比べる木で修正案の行を引き直す（今の輪は輪の後の木、前の輪は since の木。common.frozen_source）。輪が赤→緑を
    確かめた書き換えは、どの輪の物でも許しから外す。今の輪が無い（2 回目の段の輪が走らなかった）時、前の輪は輪の後の木で見る。
    裁定の範囲は今の輪だけ pass_ で決め（1 回目の受け付けは含めない）、前の輪はいつも含める（前の段で裁いた fix_test_scope の
    直しは、今の段の受け付けが first でも許し）。輪が 1 つも無ければ空。盤面は書かない。
    範囲の相談の合意の範囲の行は修正前の版（base_rev。呼び手が fixboard.base_rev で選ぶ）の行で、凍結の検査が比べる木の行へ
    移して読む（conflict.test_permits の base。読む木は 1 つ）。
    asks に list を渡せば、相談に回せる凍ったファイル（範囲の外の塊が全部、輪の受け入れのテストでない既存のテストの関数の幅に
    収まる物。common.frozen_asks）の頼み {path, tests, line, ref} を足す（line は返す文のどれかと同じ。tests の行は修正前の版の行）"""
    loops = _loop_states(board, state)
    if not loops:
        return []
    b = board
    skip = _verified(loops)
    rev = fixboard.base_rev(None, base_rev)
    before = common.rev_source(repo, rev)

    def allowed(source, rulings):
        return conflict.ruled_test_limits(b, rulings=rulings, source=source, skip_ids=skip, agreed_rows=agreed, base=before)
    now = allowed(common.frozen_source(state, repo), _now_rulings(pass_)) if state else []
    out = common.frozen_problems(state, repo, now) if state else []
    if asks is not None and state:
        try:
            asks += common.frozen_asks(state, repo, now, rev=rev)
        except common.Broken:   # 状態が読めないのは frozen_problems の側が拒む。頼みは作れないだけ
            pass
    old = loops[:-1] if state else loops
    if old:
        since = common.load_state(state).get("handoff") if state else None
        amended = conflict.permitted_units(b)
        for p in old:
            lims, spans = allowed(common.frozen_source(p, repo, since=since), True), common.test_spans(p, amended)
            out += common.frozen_problems(p, repo, lims, since=since, skip_spans=spans)
            if asks is not None:
                try:
                    asks += common.frozen_asks(p, repo, lims, since, spans, rev=rev)
                except common.Broken:
                    pass
    return out


def _loop_freeze(board, state) -> tuple:
    """(一番後の輪の frozen_tree, run の全部の輪が凍らせたファイル)。輪が無ければ (None, [])"""
    tree, files = None, set()
    for p in _loop_states(board, state):
        st = common.load_state(p)
        files |= set(st.get("frozen") or {})
        tree = st.get("frozen_tree") or tree
    return tree, sorted(files)


def _verified(loops) -> list:
    """輪が赤→緑を確かめた書き換えの名指し（common.verified_rewrites）。凍結の許しから外す"""
    return [i for p in loops for i in common.verified_rewrites(p)]


def _now_rulings(pass_: str) -> bool:
    """今の輪の凍結の許し（check_frozen）に裁定 fix_test_scope の範囲を入れるか: 段 ruled だけ（前の輪はいつも入れる）"""
    return pass_ == "ruled"


def frozen_tests(board, state, pass_: str) -> dict:
    """修正役の指示書の「テストの行」（fix の rules.tests_rows）に貼る凍ったテスト {files: run の全部の輪が凍らせたテストのファイル（_loop_freeze。
    check_plan_scope と同じ和で、凍結の照らし common.frozen_problems が輪ごとに読む frozen の和と一致する）, verified: check_frozen
    が許しから外すのと同じ名指し（_verified）, unruled: 事後の関門が裁定の範囲を許す（conflict.edit_rulings）のに、check_frozen が
    その範囲で凍結を解かない今の輪（state）の凍ったファイル（2 回目の修正の段の first）}"""
    loops = _loop_states(board, state)
    unruled = bool(state) and conflict.edit_rulings(board, pass_) and not _now_rulings(pass_)
    return {"files": _loop_freeze(board, state)[1], "verified": _verified(loops),
            "unruled": sorted(common.load_state(state).get("frozen") or {}) if unruled else []}


def check_plan_scope(reply: dict, keys: list, board: Path, base_rev: str, repo: Path, state: str, pass_: str,
                     agreed=None, ask=None, since=None, *, items=None, consult_place=None) -> tuple:
    """承認済みの修正案の項目と差分の照らし（planscope.check）。行は changes と keys（単位の名前）を並べ、files を根からの相対に
    揃えた物。変わったパスは版からの変更（writes.changed）と since からの変更（版と同じ中身に戻した・版に無く since の後に消した
    ファイルも修正役に問う）の和から、実行器が作ったファイル（common.suite_made）を除いた物。TDD の輪が
    凍らせたファイル（輪の状態の frozen と frozen_tree）は planscope.check に渡し、欠けは版からの
    差分の全部で、修正役に問う外れと余分は凍った後に変えた分だけで見させる。
    返り (拒否の行（最初の行の頭に planscope.reject_head）, 記録)。盤面は書かない（控えの食い違いで止めるのは planscope.check）。
    items は承認済みの修正案の項目（planmarks.approved_items の形の値か口。修正案の無い run は None で、照らさない）。
    頭は、範囲の相談がこの段に在れば相談を先の道に言う。ask が None なら consult_place（相談の控えの在るフォルダ）の控えで決める
    （consult.offered。None なら言わない）。
    凍らせたファイルと実行器が作ったファイルは run の全部の輪の物（_loop_freeze・common.suite_made_all）で、凍った後は一番後の
    輪の frozen_tree から見る（前の輪の後に 1 回目の段と後の輪が書いた物を、2 回目の修正役のせいにしない）。
    since は修正役が変え始めた木（受け付けと事前の確かめは fixboard.fixer_head の段の頭）: 欠けは版からの差分の全部で見て、
    修正役に問う外れと余分は since の後に変えた分（git の比べ）だけで見る（planscope.check。
    輪が直し終えた単位を修正役が変えずに返しても欠けにしない。段の頭より前に変わったファイルを out_of_scope で照らさない。
    run 97fd532f）"""
    b = board
    rows = [{"unit_key": k, "files": sorted(declared_files([c], repo))} for c, k in zip(reply.get("changes") or [], keys)]
    made = set(common.suite_made(state)) | common.suite_made_all(board)
    rev = fixboard.base_rev(None, base_rev)
    after = set(writes.changed_from(repo, since)) if since else None
    paths = sorted(p for p in set(writes.changed(repo, rev)) | (after or set()) if p not in made)
    tree, frozen = (since, paths) if since else _loop_freeze(board, state)
    problems, note = planscope.check(rows, b, repo, rev, paths, pass_=pass_, loop_tree=tree, frozen=frozen, touched=after,
                                     agreed=agreed, items=items)
    if problems:
        if ask is None:
            ask = consult.offered(consult_place, pass_)
        problems = [planscope.reject_head(ask) + problems[0], *problems[1:]]
    return problems, note


def declared_files(rows, repo) -> set:
    """changes の行の files を、リポジトリの根からの相対パスに揃えた集合。絶対パスは、親のフォルダと根のリンク（macOS の /var と
    /private/var など）を解いてから比べる（ファイルそのもののリンクは解かない）"""
    out, root = set(), os.path.realpath(repo)
    for c in rows:
        for f in c.get("files") or []:
            if isinstance(f, str) and f.strip():
                f = f.strip()
                if os.path.isabs(f):
                    f = os.path.relpath(os.path.join(os.path.realpath(os.path.dirname(f)), os.path.basename(f)), root)
                out.add(posixpath.normpath(f))
    return out


def precheck(cfg: dict, reply=None, *, items=None, skip: tuple = ()) -> dict:
    """事前の確かめ（モジュールの頭）。cfg は相談の控え（consult.load_config。board・repo・pass・base_rev・tdd_state と、在れば
    書き込みの記録のファイル log）。修正役が変え始めた木は控えでなく置き場の段の頭（fixboard.fixer_head）。items は承認済みの修正案の項目（check_plan_scope）、skip は除くパスの頭（check_writes）"""
    board, repo = Path(cfg["board"]), Path(cfg["repo"])
    state, pass_, base_rev = cfg.get("tdd_state") or "", cfg.get("pass") or "first", cfg.get("base_rev") or ""
    log, since = cfg.get("log") or None, fixboard.fixer_head(board, pass_) or None
    reply = reply if isinstance(reply, dict) else {"changes": []}
    agreed = conflict.agreed(board)
    found = [("frozen", t) for t in check_frozen(board, state, repo, pass_, agreed=agreed, base_rev=base_rev)]
    wrote = check_writes(reply, board, base_rev, repo, state, log=log, since=since, skip=skip)
    found += [("writes", t) for t in wrote["problems"]]
    keys = [c.get("unit_key") for c in wrote["reply"].get("changes") or [] if isinstance(c, dict)]   # 返答は単位の名前で書く
    scope, _ = check_plan_scope(wrote["reply"], keys, board, base_rev, repo, state,
                                pass_, agreed=agreed, ask=True, since=since,
                                items=items)
    found += [("scope", t) for t in scope]
    found += [("refs", t) for t in recount.ref_problems(wrote["reply"], board, fixboard.base_rev_of(board, base_rev), repo)]
    return {"ok": not found, "rejects": [{"check": c, "text": t} for c, t in found]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="factchecks.py", description="受け付けの事実の確かめ（凍結・書き込み・範囲・書いた指し）を試験なしで回す")
    ap.add_argument("config", help="相談の控え（指示書に書かれたパス）")
    ap.add_argument("--reply", default="", help="下書きの返答の JSON のファイル（無ければ changes の無い返答として見る）")
    a = ap.parse_args(argv)
    try:
        cfg = consult.load_config(a.config)
        reply = json.loads(Path(a.reply).read_text(encoding="utf-8")) if a.reply else None
        out = precheck(cfg, reply, items=functools.partial(fixboard.place_items, cfg["board"]), skip=tuple(cfg.get("skip") or ()))
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
