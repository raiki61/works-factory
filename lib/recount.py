"""修正の受け付けの時の数え直し（線 A。仕様 3.2・計画 Task 12）。

1 本目の受け付け（accept.check_fix: changes[].unit_key を修正案に読み替えて fix_plan_covers_units）を、受け付けの時の
数え直しに替える。今の works では盤面の done("p3.fix") の検査（写しの fix_covers_open_units）が当てた物のうち、数え直しの欄を
ここで当てる: 直す義務の単位（[block] と do-now）を全部覆うか・判定役の class_query を修正前の版（base_rev）と修正後の作業ツリーで
数え直し、closure.sites の数と母数が合うか・欠陥の形の数が減ったか。
数え直した件数は置き場の coverage-after.json（COVERAGE_FILE。fixboard._coverage が読む）に残る。

ここに在る物:
- FIX_NODE・ROLE・RULED_ROLE: 節の名前、役の名前（印の名）。RULED_ROLE は裁定の後の 2 回目の修正役
- SITE_PATH・SITE_PATH_SCHEMA・PRECEDENT_MIN_LEN・_precedent_conditions: 修正役の返答の型に足す欄（closure.sites[] の欄 path・
  changes[].precedent の条件付き必須 allOf）。型は呼び手（ブロックの型の定義）が貼る
- accept_fix(reply, place, base_rev, repo, *, judged=, owed=, ...): 受け付けの時の数え直し。1 本目の出口のための changes を足す（v1_changes）
- 修正の返答を読む口（fix_reply・_fix_output）・集める節の中身（collect）・数え直した件数の読み口（_coverage）は、盤面を読んだ所を
  置き場のファイルのパスで受ける形にして lib/fixboard.py に置いた
"""
import json
import os
import pathlib
import sys
import time

sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

_GL = CORE / "graphloops"   # 写しの engine（数える問いの argv と走らせ方。querytest と同じ足し方）
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine.util import read_json, run_count, write_json  # noqa: E402

FIX_NODE = "p3.fix"
ROLE = "fix"
RULED_ROLE = "fix-ruled"   # 裁定の後の 2 回目の修正役
SITE_PATH = "path"   # closure.sites[] の works だけの欄: site が在るファイルの対象の根からの相対パス（unitrows が問いの当たりに結ぶ）
SITE_PATH_SCHEMA = {"type": "string"}


PRECEDENT_MIN_LEN = 4 # 写しの _precedent_gap・blank(problem, 4) の下限（テストが写しと突き合わせる）


def _precedent_conditions() -> list:
    """changes[].precedent の条件付き必須（draft-07 の if/then）。写しの受け付け（_precedent_gap）と同じ決まり:
    from_judge_row が真でない限り problem を求め、verdict が not_found なら searched、それ以外なら source を求める。
    写しの engine の型検査は if/then を読まないので、役に渡る型（claude の起動の引数で渡る型）にだけ効く"""
    not_judge_row = {"not": {"required": ["from_judge_row"], "properties": {"from_judge_row": {"const": True}}}}
    is_not_found = {"required": ["verdict"], "properties": {"verdict": {"const": "not_found"}}}
    isnt_not_found = {"required": ["verdict"], "properties": {"verdict": {"not": {"const": "not_found"}}}}

    def needs(field: str) -> dict:
        return {"required": [field], "properties": {field: {"type": "string", "minLength": PRECEDENT_MIN_LEN}}}
    return [{"if": not_judge_row, "then": needs("problem")},
            {"if": {"allOf": [not_judge_row, is_not_found]}, "then": needs("searched")},
            {"if": {"allOf": [not_judge_row, isnt_not_found]}, "then": needs("source")}]


V1_CHANGE_KEYS = ("unit_key", "files", "what")   # 1 本目の出口の changes の欄（assert-changed・changes.json が読む）
CHANGES_FILE = "changes.json"
COVERAGE_FILE = "coverage-after.json"   # 受け付けが数え直した件数 {"round", "items": [{unit_key, how, counts, total, closed, after}]}
COUNT_CACHE_FILE = "count-cache.json"
COUNT_BUDGET_FILE = "count-budget.json"
# 1 周に数える問いを走らせてよい回数と時間の上限（元 works/.shared/core/graphloops/rules/review-loop.py:3304 の COUNT_BUDGET）
COUNT_BUDGET = {"calls": 300, "seconds": 900}
# 「書いていない」と同じ扱いにする語（元 works/.shared/core/graphloops/rules/review-loop.py:467 の EMPTY）
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")
REJECT_HEADING = "下の行を直した返答を丸ごと出し直せ:"   # 写しの FIX_REJECT_HEADING（engine/util.py）と同じ文


class Unreadable(Exception):
    """集める節の入力が読めない・修正の返答が置き場に無い（回す側の誤り。スクリプトは 2）"""


def v1_changes(rows) -> list:
    """1 本目の出口のための changes（[{unit_key, files, what}]）"""
    return [{k: c[k] for k in V1_CHANGE_KEYS} for c in rows]


def blank(s, min_len) -> bool:
    """役が埋める自由文が「空同然」か（表と長さの両方で見る）。元 works/.shared/core/graphloops/rules/review-loop.py:480"""
    t = (s or "").strip() if isinstance(s, str) else ""
    return t.lower() in EMPTY or len(t) < min_len


def _run_query(place, where, how, root, rev=None, probe=True, round_: int = 1) -> tuple:
    """問い（how）を engine の run_count で走らせる ——（件数, 拒否文）。走らせられなければ件数は None。
    固定した版で数えた結果は置き場の count-cache.json に取っておき、走らせた量は置き場の count-budget.json に刻む
    （拒否でも刻む）。元 works/.shared/core/graphloops/rules/review-loop.py:3307（盤面の b.dir・b.round を読んだ所を
    置き場 place と round_ に）"""
    place = pathlib.Path(place)
    cf, ck = place / COUNT_CACHE_FILE, json.dumps([how, rev], ensure_ascii=False, sort_keys=True)
    cache = (read_json(cf) if cf.is_file() else {}) if rev else {}
    if ck in cache:
        got, why = cache[ck]
        return (got, "") if got is not None else (None, f"{where}: how を機械が走らせられない（{why}）")
    bf = place / COUNT_BUDGET_FILE
    bud = read_json(bf) if bf.is_file() else {}
    if bud.get("round") != round_:
        bud = {"round": round_, "calls": 0, "seconds": 0.0}
    if bud["calls"] >= COUNT_BUDGET["calls"] or bud["seconds"] >= COUNT_BUDGET["seconds"]:
        return None, (f"{where}: この周に数える問いを走らせた量が上限（{COUNT_BUDGET['calls']} 回か {COUNT_BUDGET['seconds']} 秒）に達した"
                      f"（{bud['calls']} 回・{bud['seconds']:.0f} 秒）——同じ返答を出し直し続けていないか。続けるなら置き場の count-budget.json を消す")
    t0 = time.monotonic()
    got, why = run_count(how, str(root), rev=rev, probe=probe)
    bud["calls"] += 1
    bud["seconds"] += time.monotonic() - t0
    place.mkdir(parents=True, exist_ok=True)
    write_json(bf, bud)
    if rev and got is not None:   # 取っておくのは数えられた答えだけ——時間切れ・標準エラーは一時的でありうる
        cache[ck] = [got, why]
        write_json(cf, cache)
    if got is None:
        return None, f"{where}: how を機械が走らせられない（{why}）"
    return got, ""


def recount_problems(reply: dict, place, base_rev: str, repo, *, judged=None, owed=None, zero_keys=(),
                     round_: int = 1) -> tuple:
    """数え直しの欄の照らし ——（誤りの行の一覧, 数え直した件数の行の一覧）。元は盤面の写しの fix_covers_open_units
    （元 works/.shared/core/graphloops/rules/review-loop.py:2658）のうち、直す義務の覆いと coverage の数え直しの所。
    judged は判定の units（[{key, class_query: {how, counts, total}}]。judgment.json の process.diagnosis.units の形）、
    owed は直す義務の単位の key の集まり（fixboard.fix_duty の 1 つ目。None なら覆いを照らさない）、zero_keys は判定の時に
    engine が 0 件と数えた単位の key（判定者の母数を 0 と見る）。役が how を書かなければ判定者の how を reply に書き戻す"""
    errs = []
    changes = reply.get("changes") or []
    changed = {c.get("unit_key") for c in changes}
    if owed is not None:
        waiting = {c.get("unit_key"): c.get("why") for c in reply.get("not_done") or [] if isinstance(c, dict)}
        missing = [f"{k}（理由: {waiting[k]}）——fork の出どころでないなら直す義務がある" if k in waiting else k
                   for k in sorted(set(owed) - changed)]
        if missing:
            errs.append("直していない [block] / do-now がある（writer の裁量で defer に覆せない。異議は新しい judge に再判定させる）: "
                        + "; ".join(missing))
    by_key = {u.get("key"): (u.get("class_query") or {}) for u in judged or [] if isinstance(u, dict)}
    afters = []
    for c in changes:
        head = str(c.get("unit_key"))[:60]
        jq = by_key.get(c.get("unit_key")) or {}
        cov = c.get("coverage") or {}
        if not cov.get("how") and jq.get("how"):
            cov = c["coverage"] = {**cov, "how": jq["how"]}
        if not cov.get("how"):
            errs.append(f"{head}: 判定者の class_query が無い単位なのに coverage.how（同じ形を全部引ける機械の問い）が無い"
                        "——名指しの 1 site だけを塞いでいないことは母数でしか示せない")
            continue
        counts = jq.get("counts") or cov.get("counts")
        if counts not in ("defects", "population"):
            errs.append(f"{head}: 数えるものの向きが決まらない——判定者の class_query が無い単位は coverage.counts（defects / population）を書け")
            continue
        remaining = "" if blank(cov.get("remaining"), 10) else cov["remaining"].strip()
        total, why = _run_query(place, f"{head}: coverage（修正前）", cov["how"], repo, rev=base_rev or None, round_=round_)
        if why:
            errs.append(why)
            continue
        closed = len((c.get("closure") or {}).get("sites", []) or [])   # 塞いだ数は closure.sites から機械が数える
        after, why = _run_query(place, f"{head}: coverage（修正後）", {**cov["how"], "untracked": True}, repo, probe=False,
                                round_=round_)
        if why:
            errs.append(why)
            continue
        cap = total if total else after   # 修正前が 0 件の問いは、修正で生まれた数まで site を書ける
        if closed > cap:
            errs.append(f"{head}: closure.sites が {closed} 件なのに、engine が how を修正前の版で数えた母数は {total}"
                        f"（修正前が 0 件なら修正後の {after}）——母数を超えて塞げない"
                        "（問いが対象を取りこぼしている）。判定者の how が根の 1 行だけを数えているなら、直す site になる行を全部数える how に作り直せ")
        if closed < cap and not remaining:
            errs.append(f"{head}: 母数 {cap} のうち閉鎖を実証した site が {closed} 件で、残りが在るのに remaining（残した理由）が無い"
                        "——残すこと自体は禁じないが、黙って残すのは禁じる")
        jt = 0 if c.get("unit_key") in set(zero_keys) else jq.get("total")
        if isinstance(jt, int) and not isinstance(jt, bool) and total < jt and not remaining:
            errs.append(f"{head}: 判定者が数えた母数は {jt} なのに、この how は修正前の版で {total} しか数えない（問いを狭めている）"
                        "——狭める理由（問いが対象を取りこぼしていた等）を remaining に書け")
        if counts == "defects" and after and closed >= total and not remaining:
            errs.append(f"{head}: 欠陥の形を数える問い（判定者の counts: defects）が、母数 {total} を全部塞いだと言う修正の後も {after} 件を数える"
                        "——塞ぎ損ねた site が在る（向きは判定者が決めるので、修正役が population と書いても外れない）")
        afters.append({"unit_key": c.get("unit_key"), "how": cov["how"], "counts": counts, "total": total, "closed": closed,
                       "after": after})
    return errs, afters


def accept_fix(reply: dict, place, base_rev: str, repo, *, judged=None, owed=None, zero_keys=(), round_: int = 1,
               commit: bool = True) -> dict:
    """受け付けの時の数え直し（recount_problems）を当て、結果に 1 本目の出口のための changes（[{unit_key, files, what}]。返答の
    changes[] から写す）を足す。拒否のときの changes は空（1 本目と同じ）、誤りの行は problems に並べ、reason は見出しと行。
    通れば数え直した件数を置き場 place の coverage-after.json（{"round", "items"}）に書く。
    commit が偽なら乾いた照らし（置き場に件数を書かない。数えた量と版の答えの取り置きは刻む）で、返りに dry: True と changes: []。
    元 works/.shared/core/recount.py:115（盤面の entry.take(board, "p3.fix", …) に渡し、写しの fix_covers_open_units が
    盤面の判定と state.inputs.review_rev を読んで数え直した所を、引数の判定 judged・直す義務 owed・修正前の版 base_rev で受ける）"""
    if not isinstance(reply, dict) or not isinstance(reply.get("changes", []), list):
        return {"ok": False, "reason": "修正の返答に changes の並びが無い", "problems": ["修正の返答に changes の並びが無い"],
                "changes": [], **({"dry": True} if not commit else {})}
    errs, afters = recount_problems(reply, place, base_rev, repo, judged=judged, owed=owed, zero_keys=zero_keys, round_=round_)
    if errs:
        got = {"ok": False, "reason": REJECT_HEADING + "\n" + "\n".join(f"- {e}" for e in errs), "problems": errs, "changes": []}
        return {**got, "dry": True} if not commit else got
    if not commit:
        return {"ok": True, "dry": True, "problems": [], "changes": []}
    path = pathlib.Path(place) / COVERAGE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"round": round_, "items": afters}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True, "problems": [], "changes": v1_changes(reply.get("changes") or []), "coverage_file": str(path)}
