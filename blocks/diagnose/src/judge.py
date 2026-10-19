"""判定役の受け付けの芯（docs/design/diagnose.md の 2.8。lib/judge_accept.py の判定の部分を、place と値を引数で受ける形に写した物）。

受けた返答を、検証器の語彙（表）・作業ツリー・class_query の例と件数・先行例の出どころ・目的の外の所見・依頼の答えと作り直しの行の
結び・記録された方針の名指しで照らす。指示の文は持たない（prompts/diagnose.md が持つ）。表の文（kind と status の意味）も md が持ち、
ここは語と要る欄だけ。前の周を読む規則（前の周の R1 の削除候補・前の周の fork・defer 台帳）は写さない（1 run は 1 周）。
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import time

import accept      # lib/。Reject・guard・in_repo・resolve_rev・snapshot_tree・status_keys
import cite        # lib/。出典の照らし
import gatemarks   # lib/
import jsonfile    # lib/
import materialkit   # lib/。moved_since
import oneline     # lib/
import outpurpose  # lib/
import policy      # lib/
import querytest   # lib/
import rolekit     # lib/
import worldmark   # lib/
from judgmark import is_open, open_units   # lib/。開いた単位の選び（verify・fix と共に読む判定の行の形）
from engine.util import Reject, git as _git, repo_root, run_count   # lib/graphloops/engine/util.py

from src import files

# ---------------------------------------------------------------- 検証器の表（語と要る欄だけ。文は md）
Kind = collections.namedtuple("Kind", "domain fields")
REVIEWS = ("R1", "R2", "R3", "R4")
LABELS = ("block", "suggest", "nit", "question", "info")
QUESTION_KINDS = {
    "fork": Kind("unit", ("options",)),
    "split": Kind("unit", ()),
    "rule": Kind("unit", ()),
    "stuck": Kind("unit", ()),
    "thrash": Kind("none", ()),
    "premise": Kind("review", ()),
    "unverifiable": Kind("review", ()),
    "awaiting": Kind("material", ()),
    "field": Kind("none", ()),
}
QUESTION_FIELDS = ("key", "kind", "status", "reason", "resolution", "options", "depends", "origin")
UNIT_FIELDS = ("key", "label", "disposition", "reason", "reopen_evidence")
QUESTION_STATUS = {"held": (), "decided": ("resolution",), "resolved": ("resolution",), "escalate": ()}
NO_OPEN_ORIGIN = ("split", "rule")
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")   # 「書いていない」と同じ扱いにする語
ONE_LINE_FIELDS = ("key", "reason")
# 判定の後に機械が台帳へ立てる問いの key（依頼の答えの結びを求めない字）
ASK_KEYS = {
    "R1": "累積差分の最小性を独立に測れない（R1 unverifiable）——測る材料を人が示すか、未収束のまま報告するか",
    "R2": "元の目的を独立に取れない（R2 unverifiable）——目的の出典を人が示すか、未収束のまま報告するか",
    "R3": "文書横断の整合を独立に確かめられない（R3 unverifiable）——確かめる材料を人が示すか、未収束のまま報告するか",
    "R4": "横断リスクと消えた能力を独立に確かめられない（R4 unverifiable）——基準点の材料を人が示すか、未収束のまま報告するか",
}
COUNT_BUDGET = {"calls": 300, "seconds": 900}
PREMISE_THREE = "③"   # 人へ回す問いの先行例の undecided_because が、記録された方針の行とぶつかると名乗る印
_CASE_MARKS = re.compile(r"\s*([①②③][\s・、,]*)+")


# ---------------------------------------------------------------- 小さな助け
def _read_json(path, default=None):
    """path の JSON。無ければ default。読めない・JSON でなければ ValueError（壊れた控えを黙って空にしない）"""
    p = pathlib.Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"{p} が読めない（{type(e).__name__}: {e}）") from None


def _write_json(path, doc) -> pathlib.Path:
    return jsonfile.write(path, doc, parents=True)


def blank(s, min_len):
    """役が埋める自由文が「空同然」か（表と長さの両方で見る）"""
    t = (s or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def origin_not_awaiting(q, materials):
    """未決の問いの出どころが素材なのに、その素材が今 awaiting_human でないか"""
    k = QUESTION_KINDS.get(q.get("kind"))
    if not k or k.domain != "material" or q.get("status") not in gatemarks.ASKING:
        return False
    m = materials.get(q.get("origin"))
    return bool(m) and m.get("status") != "awaiting_human"


def targets(q):
    """この問いが指す出どころ全部を (欄名, 域, 値) で返す"""
    domain = QUESTION_KINDS[q["kind"]].domain
    out = [("origin", domain, q["origin"])] if "origin" in q else []
    out.extend(("depends", "unit", d) for d in q.get("depends", []))
    return out


def settled_state_errors(q, units):
    """決着した問いの状態が、出どころのユニットがまだ開いているかと食い違っていないか"""
    k = QUESTION_KINDS.get(q.get("kind"))
    status = q.get("status")
    by_key = {u.get("key"): u for u in units}
    if not k or k.domain != "unit" or status not in ("decided", "resolved") or q.get("origin") not in by_key:
        return []
    still_open = is_open(by_key[q["origin"]])
    if status == "resolved" and still_open:
        return ["出どころが [block] / do-now のまま resolved（決着したが欠陥が"
                "残っているなら decided。resolved は出どころも閉じた問いだけ）"]
    if status == "decided" and not still_open:
        return ["出どころが閉じているのに decided（欠陥が記録から消えたなら"
                "resolved にして、次の周の台帳から降ろせ）"]
    return []


def _keys_once(rows, label):
    """行の key が重複しないか（重複の文の一覧）"""
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            errs.append(f"{label}[{i}] の key が重複: {r['key'][:60]}")
        seen.add(r["key"])
    return errs


def _run_query(place, where, how, root, rev=None, probe=True):
    """役が書いた問い（how）を走らせる ——（件数, 拒否文）。走らせられなければ件数は None。数えた量の控えは place に置く"""
    if not root:
        return None, f"{where}: how を走らせる場所（リポジトリのルート）を引けない——確かめられない件数は受け取らない"
    place = pathlib.Path(place)
    cf, ck = place / files.COUNT_CACHE_FILE, json.dumps([how, rev], ensure_ascii=False, sort_keys=True)
    cache = (_read_json(cf, {}) or {}) if rev else {}
    if ck in cache:
        got, why = cache[ck]
        return (got, "") if got is not None else (None, f"{where}: how を機械が走らせられない（{why}）")
    bf = place / files.COUNT_BUDGET_FILE
    bud = _read_json(bf, {}) or {}
    if bud.get("round") != 1:
        bud = {"round": 1, "calls": 0, "seconds": 0.0}
    if bud["calls"] >= COUNT_BUDGET["calls"] or bud["seconds"] >= COUNT_BUDGET["seconds"]:
        return None, (f"{where}: この周に数える問いを走らせた量が上限（{COUNT_BUDGET['calls']} 回か {COUNT_BUDGET['seconds']} 秒）に達した"
                      f"（{bud['calls']} 回・{bud['seconds']:.0f} 秒）——同じ返答を出し直し続けていないか。続けるなら置き場の "
                      f"{files.COUNT_BUDGET_FILE} を消す")
    t0 = time.monotonic()
    got, why = run_count(how, root, rev=rev, probe=probe)
    bud["calls"] += 1
    bud["seconds"] += time.monotonic() - t0
    _write_json(bf, bud)
    if rev and got is not None:
        cache[ck] = [got, why]
        _write_json(cf, cache)
    if got is None:
        return None, f"{where}: how を機械が走らせられない（{why}）"
    return got, ""


# ---------------------------------------------------------------- 判定の受け付け
def _head_at_rev(repo, rev, role):
    """HEAD が数える版 rev のままか。動いていれば Reject（写しの無い見張りで、役が作った物を commit して git status を空に戻す道を塞ぐ）"""
    head = accept._git(repo, "rev-parse", "--verify", "-q", "HEAD").strip()
    if head != rev:
        raise Reject(f"HEAD が数える版から動いた（版 {rev[:12]} / 今 {head[:12]}）——{role}は作業ツリーと履歴を変えてはいけない"
                     "（commit・reset・checkout で履歴を動かさない）")


def _tree_unchanged(repo, place, rev, keys):
    """判定役が作業ツリーを変えていないか。place に tree.json（役を起こす前の写し）が在れば今と比べる（HEAD・枝の移動と git が無視する
    ファイルの増減・書き換えも見る）。無ければ作業ツリーが綺麗で、HEAD が数える版 rev のままであることを求める。違えば Reject"""
    if not (pathlib.Path(place) / materialkit.TREE).is_file():
        now = accept.snapshot_tree(repo)
        dirty = now["porcelain"].splitlines() + [f"!! {n}" for n in now["ignored"]]
        if dirty:
            raise Reject("作業ツリーに変更が在る——判定役は読むだけの役で、作業ツリーを変えてはいけない"
                         f"（git status --porcelain --ignored: {dirty[:5]}{' ほか' if len(dirty) > 5 else ''}）")
        _head_at_rev(repo, rev, "判定役")
        return
    moved = materialkit.moved_since(place, repo, keys)
    if moved:
        raise Reject("判定役を起こした後から作業ツリーが変わった——判定役は読むだけの役で、作業ツリー・HEAD・枝・git が"
                     f"無視するファイルを変えてはいけない（{'・'.join(moved)}）")


def _precedent_gap(r):
    """先行例の 1 行に足りない物（無ければ空文字）。見つからないなら何を探したか、それ以外は一次情報の出典"""
    if r.get("verdict") == "not_found":
        return "searched（何をどう探したか）が無い" if blank(r.get("searched"), 4) else ""
    return "source（一次情報の出典）が無い" if blank(r.get("source"), 4) else ""


def _precedent_errors(out):
    """先行例の行（precedents）: 今の周に直す単位と人へ回す問いの key ごとに 1 行、出典つき。人へ回す問いの行には『世界の解を当たっても
    決まらない理由』"""
    rows = out.get("precedents") or []
    errs, by = _keys_once(rows, "precedents"), {r["key"]: r for r in rows}
    for i, r in enumerate(rows):
        gap = _precedent_gap(r)
        if gap:
            errs.append(f"precedents[{i}]（{r['verdict']}）に {gap}")
    need = [(u["key"], False) for u in out["units"] if is_open(u)]
    need += [(q["key"], True) for q in out["questions"] if gatemarks.asks_human(q)]
    for k, asks in need:
        r = by.get(k)
        if r is None:
            errs.append(f"precedents に '{k[:60]}' の行が無い——今の周に直す単位と人へ回す問いには、世界の解（先行例）を当たった行が要る")
        elif asks and blank(r.get("undecided_because"), files.UNDECIDED_MIN):
            errs.append(f"precedents['{k[:60]}'] に undecided_because が無い——世界の解を当たっても決まらない理由（困っている点・残る不安）を"
                        "書け。書けないなら自明なので人に回さず、処方として採れ")
    return errs


def _awaiting_origins(questions, materials, where):
    """人待ちの問い（kind=awaiting で未決）の出どころが、今 awaiting_human の素材か"""
    errs = []
    for i, q in enumerate(questions):
        if origin_not_awaiting(q, materials):
            m = materials[q["origin"]]
            errs.append(f"{where}[{i}]（awaiting・{q['status']}）の出どころの素材 '{q['origin']}' が {m.get('status')}——awaiting の出どころは"
                        "今 awaiting_human の素材だけ。素材を書くノードは、人に諮っている最中の欄を awaiting_human のまま書け（見た結果は reason に）。"
                        "人が実地で確かめるまで決まらない問いは kind=field で立てろ（素材の欄を借りない）")
    return errs


def judge_output(out, place, root, rev, materials):
    """判定の返答を、検証器の語彙で先に見る。落ちるなら判定役に返させ直す（Reject）。あわせて 1 行の欄を 1 行に正規化し、class_query の
    件数を機械が数えた値に置き換える（out を書き換える）。返りは置き換えの注記（無ければ ""）"""
    errs = []
    # 役の自由文から改行を落とす（key / reason の中の改行が台帳の字下げの行頭を作らない）
    for row in list(out.get("units", [])) + list(out.get("questions", [])):
        for f in ONE_LINE_FIELDS:
            if isinstance(row.get(f), str):
                row[f] = oneline.one_line(row[f])
    keys = set()
    replaced, zeroed = [], []
    for i, u in enumerate(out["units"]):
        if u["key"] in keys:
            errs.append(f"units[{i}] の key が重複: {u['key']}")
        keys.add(u["key"])
        if u["label"] not in LABELS:
            errs.append(f"units[{i}] の label が不正: {u['label']}")
        if u["label"] == "suggest":
            if u.get("disposition") not in ("do-now", "defer"):
                errs.append(f"units[{i}]（suggest）に disposition（do-now / defer）が無い")
            elif u["disposition"] == "defer" and not u.get("reason"):
                errs.append(f"units[{i}] の defer に構造的理由が無い")
        # 今の周に直す単位は、同じ形を全部引ける機械の問いを持て
        if is_open(u):
            cq = u.get("class_query") or {}
            if not cq.get("how") or not isinstance(cq.get("total"), int) or isinstance(cq.get("total"), bool):
                errs.append(f"units[{i}]（今の周に直す単位）に class_query（how＝同じ形を全部引ける機械の問い・total＝その件数）が無い"
                            "——1 site しか無いなら total: 1 でそう示せ")
            else:
                # 判定役が読んだのと同じ版（この周に固定した版）で数える。修正役の after は作業ツリーで数える
                got, why = _run_query(place, f"units[{i}].class_query", cq["how"], root, rev=rev)
                if why:
                    errs.append(why)
                elif got == 0 and cq["total"] != 0:
                    # 0 件は黙って置き換えない——役の数を残し、0 だったことを note に書く
                    zeroed.append(f"units[{i}].class_query（役 {cq['total']} / engine 0）")
                    cq["note"] = (f"{cq.get('note') or ''}（engine が how を走らせると 0 件——在るべき物が無い型か、問いが対象を"
                                  f"取りこぼしている。役の書いた {cq['total']} を残した）").strip()
                elif got != cq["total"]:
                    replaced.append(f"units[{i}].class_query.total {cq['total']} → {got}")
                    cq["note"] = (f"{cq.get('note') or ''}（役の書いた total は {cq['total']}。engine が how を走らせた {got} に置き換えた）").strip()
                    cq["total"] = got
    # 一撃は反証可能に——「何が消えるはずか」を名指しする
    closes = out.get("one_shot_closes") or []
    if any(is_open(u) for u in out["units"]) and not closes:
        errs.append("one_shot_closes が空——その一撃が閉じると見込む unit の key を名指ししろ（次の周が実際の再発と突き合わせる）")
    unknown = [k for k in closes if k not in keys]
    if unknown:
        errs.append(f"one_shot_closes に今の周の units に無い key: {unknown}")
    for i, q in enumerate(out["questions"]):
        unknown = sorted(set(q) - set(QUESTION_FIELDS))
        if unknown:
            errs.append(f"questions[{i}] に知らない欄: {unknown}（書けるのは {'/'.join(QUESTION_FIELDS)}）")
        kind, status = q.get("kind"), q.get("status")
        if kind not in QUESTION_KINDS:
            errs.append(f"questions[{i}] の kind が不正: {kind}")
            continue
        if status not in QUESTION_STATUS:
            errs.append(f"questions[{i}] の status が不正: {status}")
            continue
        domain, extra = QUESTION_KINDS[kind].domain, QUESTION_KINDS[kind].fields
        for f in ("reason",) + extra + QUESTION_STATUS[status]:
            if not q.get(f):
                errs.append(f"questions[{i}]（{kind}/{status}）に '{f}' が要る")
        if kind == "fork" and not (isinstance(q.get("options"), list) and len(q["options"]) >= 2):
            errs.append(f"questions[{i}] の options は選択肢 2 つ以上（各項に帰結まで）")
        # 出どころ（origin と depends）の走査は targets 1 本
        for fld, dom, val in targets(q):
            if dom == "unit" and val not in keys:
                errs.append(f"questions[{i}] の {fld} '{val}' が units に無い")
            elif dom == "material" and val not in files.MATERIALS:
                errs.append(f"questions[{i}] の {fld} は素材名: {val}")
            elif dom == "review" and val not in REVIEWS:
                errs.append(f"questions[{i}] の {fld} は R1〜R4: {val}")
        if domain == "none" and (q.get("origin") or q.get("depends")):
            errs.append(f"questions[{i}]（{kind}）は origin / depends を持てない")
        for d in q.get("depends", []) or []:
            if d not in keys:
                errs.append(f"questions[{i}] の depends '{d}' が units に無い")
        if status in gatemarks.ASKING and kind in NO_OPEN_ORIGIN:
            for k in [q.get("origin")] + list(q.get("depends", []) or []):
                u = next((x for x in out["units"] if x["key"] == k), None)
                if u and is_open(u):
                    errs.append(f"questions[{i}]（{kind}）の出どころ '{k}' が [block] / do-now（人に聞く前に直す義務が消える。defer にして構造的理由を書け）")
        errs += [f"questions[{i}]: {m}" for m in settled_state_errors(q, out["units"])]
    awaiting = {name for name, m in (materials or {}).items() if isinstance(m, dict) and m.get("status") == "awaiting_human"}
    listed = {q.get("origin") for q in out["questions"] if q.get("kind") == "awaiting" and q.get("status") in gatemarks.ASKING}
    for name in sorted(awaiting - listed):
        errs.append(f"素材 '{name}' が awaiting_human なのに台帳に kind=awaiting で無い")
    if out.get("materials_missing"):
        errs.append("判定役が素材の欠落を報告した（当該の素材の観点を起こし直せ）: " + ", ".join(out["materials_missing"]))
    errs += _precedent_errors(out)
    if errs:
        raise Reject("judge の返答が記録の語彙に合わない（judge に返させ直す）: " + "; ".join(errs))
    notes = ([f"class_query の件数を engine が走らせた値に置き換えた: {'; '.join(replaced)}"] if replaced else []) + \
            ([f"engine の数が 0 件なので置き換えなかった: {'; '.join(zeroed)}"] if zeroed else [])
    return " / ".join(notes)


def world_ref_problems(reply, rows) -> list:
    """先行例の出どころ `world:<類の id>` が、世界の解の行 rows に在るか（worldmark.ref_problems を、控えのフォルダでなく行の並びで
    受ける形にした写し）。world: の無い出どころは見ない。行が無い run の world: は全部宙に浮いた参照"""
    got = reply.get("precedents") if isinstance(reply, dict) else None
    sources = [p.get("source") for p in got if isinstance(p, dict)] if isinstance(got, list) else []
    known = {r["class_id"] for r in rows or []}
    return [p for s in sources for p in cite.ref_problem(s, worldmark.SOURCE_PREFIX, known)]


def _judged(reply, place, repo, world_rows, materials):
    """作業ツリーと HEAD → class_query の例 → 先例の出どころ → judge_output → awaiting の出どころ。返り (正規化した返答, 例, 注記)。
    拒否は Reject"""
    repo_p = pathlib.Path(repo)
    keys = accept.status_keys(files.GUARDED)
    with accept.in_repo(repo_p):
        rev = accept.resolve_rev(repo_p, "")   # 今と同じく HEAD
        _tree_unchanged(repo_p, place, rev, keys)
        errs = querytest.problems(reply.get("units"), is_open)
        if errs:
            raise Reject("class_query の例が問いと合わない: " + "; ".join(errs))
        errs = world_ref_problems(reply, world_rows)
        if errs:
            raise Reject("precedents の出どころが世界の解の行に無い: " + "; ".join(errs))
        out, examples = querytest.split(reply, is_open)   # 例を外した写し（返答の元は触らない）
        note = judge_output(out, place, repo_root(_git) or "", rev, materials)
        errs = _awaiting_origins(out["questions"], materials, "questions")
        if errs:
            raise Reject("判定の問いの台帳が素材の状態と合わない: " + "; ".join(errs))
    return out, examples, note


def _save_examples(place, examples) -> None:
    """例の無い判定は前の例を消すだけ（ファイルが在れば空に置き換え、無ければ作らない）"""
    if examples or (pathlib.Path(place) / files.QUERY_EXAMPLES_FILE).is_file():
        querytest.save(place, examples, replace=True)


# ---------------------------------------------------------------- 依頼の答えと作り直しの行の結び
def unmeasured(materials) -> dict:
    """今の周に測れていない素材 {名: status}"""
    return gatemarks.unmeasured_of(materials)


def answer_binds(a, questions, materials) -> list:
    """依頼の答え a が当たる返答の問い（結びの行は空。字の一致だけ）"""
    return gatemarks.binds(a, questions, missing=unmeasured(materials))


def answer_tie_problems(reply, rows, materials, answers, redesign) -> list:
    """判定の返答 reply（answer_ties を外した写し）と結びの行 rows の誤り（1 件 1 文）。answers は依頼の answers の行、redesign は前の run の
    作り直しの行（どちらも受け付けが値で受ける）。行の 1 つの照らしは gatemarks._tie_row_problems"""
    if not isinstance(rows, list):
        return [f"{gatemarks.ANSWER_TIES} が配列でない（{type(rows).__name__}）"]
    body = reply if isinstance(reply, dict) else {}
    questions = [q for q in body.get("questions") or [] if isinstance(q, dict)]
    units = {u.get("key"): u for u in body.get("units") or [] if isinstance(u, dict)}
    by_answer = {a.get("question"): a for a in answers if isinstance(a, dict)}
    by_redesign = {_row_key(r): r for r in redesign}
    out, tied = [], set()
    for i, r in enumerate(rows):
        errs, got = gatemarks._tie_row_problems(i, r, by_answer, by_redesign, {q.get("key") for q in questions}, units)
        out += errs
        if got is not None and not errs:
            if got in tied:
                out.append(f"{gatemarks.ANSWER_TIES}[{i}] が同じ {got[0]} {got[1]!r} の 2 度目（1 つの答え・行に結びは 1 つ）")
            tied.add(got)
    later = set(ASK_KEYS.values())   # 判定の後に機械が台帳へ立てる問いの key
    for name, a in by_answer.items():
        if ("answer", name) in tied or name in later:
            continue
        hits = answer_binds(a, questions, materials)
        if len(hits) == 1 or (not hits and name in unmeasured(materials)):
            continue
        out.append(f"依頼の答え {name!r} が" + (f"返答の複数の問いに当たる（{'・'.join(str(q.get('key')) for q in hits)}）" if hits
                                             else "返答のどの問いにも当たらない")
                   + f"のに結びが無い——{gatemarks.ANSWER_TIES} に {{answer: {name!r}, to: <今の返答の問いの key か単位の key>}} か "
                   f"{{answer: {name!r}, none: <当たらない訳。{gatemarks.ANSWER_TIE_MIN} 字以上>}} を足す")
    for key, r in by_redesign.items():
        if ("redesign", key) not in tied:
            out.append(f"作り直しの行 {gatemarks._squeeze(r.get('text'))!r} に結びが無い——{gatemarks.ANSWER_TIES} に {{redesign: <行の text の最初の「（」まで>, "
                       f"to: <[block] か do-now の単位の key>}} か {{redesign, none: <反証で死んだか目的の外とした訳。{gatemarks.ANSWER_TIE_MIN} 字以上>}} を足す")
    return out


def _row_key(row) -> str:
    import carry   # lib/
    return carry.row_key(row)


def claims_premise_three(because) -> bool:
    """undecided_because が ③ を名乗るか: 頭に並べた場合の印に ③ が在る時だけ（本文の中の ③ は名乗りでない）"""
    head = _CASE_MARKS.match(str(because or ""))
    return head is not None and PREMISE_THREE in head.group(0)


def recorded_question_problems(out, rows) -> list:
    """人へ回す問いの先行例のうち、undecided_because が頭の印で ③ を名乗るのに記録された方針のどの行も名指さない物（1 件 1 文）"""
    asked = {q["key"]: q for q in out["questions"] if gatemarks.asks_human(q)}
    return [f"precedents['{r['key'][:60]}'] の undecided_because が頭の印で {PREMISE_THREE} を名乗るが、{policy.RECORDED_TERM}の一覧の"
            "どの行も名指さない——一覧に無いコードのコメント・docstring・テストの説明文は対象の文で、そのぶつかりは "
            f"{PREMISE_THREE} に当たらない（その文を書き換える site を単位の prescriptions に入れよ）。① か ② に当たる問いなら頭の印をそれに"
            "直せ。一覧の行とぶつかるなら、その行の名指しを字のまま写せ"
            for r in out.get("precedents") or []
            if r.get("key") in asked and claims_premise_three(r.get("undecided_because"))
            and not policy.hits(rows, r.get("undecided_because"), asked[r["key"]].get("reason"))]


# ---------------------------------------------------------------- 受け付け
def take(place, reply, repo, world_rows, answers, redesign, recorded, materials, material_rows) -> dict:
    """判定役の返答の受け付け（順は docs/design/diagnose.md の 2.8）。返り {ok, reason, open_units, judgment_file}。拒否の時は
    judgment.json を書かない"""
    def run():
        if not isinstance(reply, dict):
            raise Reject(f"判定の返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        body, outside = outpurpose.split(reply)
        body, tie_rows = gatemarks.split_answer_ties(body)
        out, examples, note = _judged(body, place, repo, world_rows, materials)
        errs = outpurpose.problems(outside, material_rows)
        if errs:
            raise Reject(f"{outpurpose.FIELD} の行が材料の行と合わない: " + "; ".join(errs))
        errs = answer_tie_problems(out, tie_rows, materials, answers, redesign)
        if errs:
            raise Reject(f"{gatemarks.ANSWER_TIES} が依頼の答えと作り直しの行に結ばれていない: " + "; ".join(errs))
        errs = recorded_question_problems(out, recorded)
        if errs:
            raise Reject("③（前の決定か方針とぶつかる）を名乗る問いが記録された方針の行を名指さない: " + "; ".join(errs))
        _save_examples(place, examples)
        outpurpose.save(place, 1, outside, material_rows)
        gatemarks.save_answer_ties(place, 1, tie_rows)
        doc = outpurpose.restore(querytest.restore(out, place), place, 1)
        path = _write_json(pathlib.Path(place) / files.JUDGMENT_FILE, doc)
        return {"ok": True, "reason": note or "", "open_units": [u["key"] for u in out["units"] if is_open(u)],
                "judgment_file": str(path)}
    return accept.guard(run, open_units=[], judgment_file="")


def accept_reply(place, raw: str, repo, world_rows, answers, redesign, recorded, materials, material_rows) -> dict:
    """判定役の返答の受け付けの輪の 1 回（rolekit.accept_round）。3 回目の拒否で done。諦めても止めの控えは書かない（出口が理由を返す）。
    返り {ok, done, reason, open_units, judgment_file}"""
    return rolekit.accept_round(place, files.DIAGNOSE_ROLE, raw, lambda reply: take(
        place, reply, repo, world_rows, answers, redesign, recorded, materials, material_rows))


# ---------------------------------------------------------------- 単位の目録
def _unit_file_paths(u: dict, repo) -> tuple:
    """単位 1 つが名指すファイル（class_query.how.paths。無ければ key の頭の語）のうち、対象の根からの相対で在るファイルのパスと、
    捨てたパス。how.paths は git の pathspec（ディレクトリ・glob・絶対パスも来る）で、構造の目は根の中のファイルしか測らないので、
    ここで捨てて数を残す（黙って空の実測にしない）"""
    how = (u.get("class_query") or {}).get("how") or {}
    raw = [p for p in how.get("paths") or [] if isinstance(p, str) and p]
    if not raw and isinstance(u.get("key"), str) and u["key"].split():
        raw = [u["key"].split()[0]]
    root = pathlib.Path(repo).resolve()
    kept, dropped = [], []
    for p in raw:
        q = pathlib.PurePosixPath(p[2:] if p.startswith("./") else p)
        ok = (not q.is_absolute() and ".." not in q.parts and not any(c in p for c in "*?[:")
              and (root / q).is_file())
        (kept if ok else dropped).append(str(q) if ok else p)
    return list(dict.fromkeys(kept)), list(dict.fromkeys(dropped))


def structure_units(judgment, repo, record=None) -> list:
    """判定の開いた単位（is_open）を全部、構造の目の入力の形 {id, paths, summary} に写した並び（判定の順）。summary は単位の reason だけ。
    paths が取れない単位も落とさない（paths: [] で返す）。record（ファイルのパス）が在れば、パスの取れない単位と捨てたパスを
    {units, paths} で書く（黙って空の実測にしない）"""
    rows, empty, dropped = [], [], []
    for u in (judgment.get("units") if isinstance(judgment, dict) else None) or []:
        if not isinstance(u, dict) or not isinstance(u.get("key"), str) or not is_open(u):
            continue
        paths, bad = _unit_file_paths(u, repo)
        dropped += bad
        if not paths:
            empty.append(u["key"])
        reason = u.get("reason") if isinstance(u.get("reason"), str) else ""
        rows.append({"id": u["key"], "paths": paths, "summary": reason})
    if record is not None:
        _write_json(record, {"units": empty, "paths": list(dict.fromkeys(dropped))})
    return rows
