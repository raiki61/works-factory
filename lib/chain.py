"""周の鎖の決め（考え chain）。標準ライブラリと持ち越しの住処 carry だけを import する。

元は今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/.shared/core/chain.py。鎖は、1 回の起動が周ごとの run を最大 MAX_ROUNDS 本つなぐ並び。
起こす・待つ・承認・再開・費用の合算はグラフの側が持ち、ここは周の間の決め（次を起こすか・止めの語・次の依頼）だけを持つ。
結末の語は書かず、結末の住処 report.OUTCOME_KINDS が引いた種だけを受ける。

- KIND_*: 結末の種（report.OUTCOME_KINDS の値）。closed＝直し済み・直す物が無い、halted＝止まった、human＝人の判断が要る、
  wait＝途中で落ちた、open＝残りが在る（次の周へ進める）
- STOPS: 鎖の止めの語の表（run の中の止めの理由 stopby とは別の考え）
- decide(doc, facts, budget=None) -> {act, word, text}: 見る順は 周の数 → 結末の種 → 人が要る → 進みが無い → 費用
- step(doc, facts): 周の事実を読めなかった周と、運ぶ依頼の無い launch を halted にしてから decide を呼ぶ
- next_request(prev_next_doc, first_doc)・held_rows(next_doc)・keys_of(next_doc)・first_of(first_doc, pr): 次の周の依頼と、運ばない
  下書きの行と、残りの行の鍵と、1 周目に名指した PR を足した 1 周目の依頼
- limits(rounds_raw, budget_raw): 周の数と費用の上限の入力の確かめ

元から変えた所:
- decide は起こした次の周の状態（facts が None の枝・pending・alive）を見ない。起こした周を待つのはグラフの側になった
- 下書きの行は facts["held_rows"] から読む（次の依頼の文書を読むのが別のノードになった）
- 種が読めない時の文で結末の語を名指す（語が無い・語が表に無い）
- next_request は前の周の constraints（前提の検算の実測）も運ぶ
外した物: 起動の手続きと印（pending・pid・launched・tries・LAUNCH_TRIES・_alive）、止めの語 launch_unbound・launch_failed、
鎖の控えと錠（new_doc・load・save・update・path・locked・_HELD・FILE・LOCK・ENV_KEY）、殻の口（_step・main ほか）、
pick・render・build_row・REPORT・REPORT_HEAD・FINAL・_count_files（最後の差分と報告は別の課題で移す）。
"""
import pathlib
import re
import sys

_HERE = str(pathlib.Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import carry  # noqa: E402

KIND_CLOSED, KIND_HALTED, KIND_HUMAN, KIND_WAIT, KIND_OPEN = "closed", "halted", "human", "wait", "open"
KINDS = (KIND_CLOSED, KIND_HALTED, KIND_HUMAN, KIND_WAIT, KIND_OPEN)
# 周の数の上限。元の review-loop の max_rounds と同じ。越える時は最後の次の依頼で鎖を起こし直す
MAX_ROUNDS = 5

STOPS = {
    "rounds_reached": "指定の周の数に達した",
    "closed": "結末が閉じた（直し済みか、直す物が無い）",
    "halted": "run が止まった（止め札・人が承認ノードで stop・メイングラフの止め・記録が検証器を通らない・周の事実を読めなかった）",
    "human": "人の判断が要る（承認ノードで人に聞いたまま・見直していない下書きの行が残った）",
    "no_change": "進みが無い（周の結果の木が周の頭と同じ）",
    "same_items": "進みが無い（残りの行が前の周と同じ）",
    "budget": "次の周で費用の上限を越えうる",
    "cost_unread": "費用が読めない周が在り、上限を守れると言えない",
}
ROUNDS = re.compile(r"[1-9][0-9]*")
BUDGET = re.compile(r"[0-9]+(\.[0-9]+)?|\.[0-9]+")


def _stop(word: str, extra: str = "") -> dict:
    return {"act": "stop", "word": word, "text": STOPS[word] + (f"（{extra}）" if extra else "")}


def drafts_in(next_doc) -> list:
    """次の依頼の下書きの中の、下書きの印の在る行（findings と answers。人が見直して印を消すまで依頼の入口が拒む行）"""
    if not isinstance(next_doc, dict):
        return []
    return [r for key in (carry.FINDINGS, carry.ANSWERS) for r in (next_doc.get(key) or []) if carry.is_draft(r)]


def _unread_kind(facts: dict) -> str:
    outcome = facts.get("outcome")
    return "結末の語が無い" if not outcome else f"結末の語 {outcome!r} が表に無い"


def decide(doc: dict, facts: dict, budget=None) -> dict:
    """鎖の次の一手 {act, word, text}。doc は {rounds_max, budget_usd, rounds}（rounds は終わった周の行の並びで、最後が facts の周）。
    facts は終わった周の事実 {kind, outcome, same_tree, keys, held_rows, cost, cost_read}。見る順は 周の数 → 結末の種 → 人が要る →
    進みが無い → 費用で、どれにも当たらなければ launch。途中で落ちた周（wait）は aborted で、次の周を起こさない。
    budget は費用の上限 USD（無ければ doc の budget_usd）"""
    rows = doc.get("rounds") or []
    if len(rows) >= int(doc.get("rounds_max") or 0):
        return _stop("rounds_reached")
    kind = facts.get("kind")
    if kind == KIND_CLOSED:
        return _stop("closed")
    if kind == KIND_WAIT:
        return {"act": "aborted", "word": "", "text": "run が途中で落ちた（その周の run を resume で続ける）"}
    if kind == KIND_HUMAN:
        return _stop("human")
    if kind != KIND_OPEN:
        return _stop("halted", "" if kind == KIND_HALTED else _unread_kind(facts))
    held = facts.get("held_rows") or []
    if held:
        return _stop("human", f"下書きの行 {len(held)} 件")
    if facts.get("same_tree"):
        return _stop("no_change")
    keys = set(facts.get("keys") or [])
    if keys and len(rows) >= 2 and keys == set(rows[-2].get("keys") or []):
        return _stop("same_items")
    limit = doc.get("budget_usd") if budget is None else budget
    if limit is not None:
        if any(not r.get("cost_read") or r.get("cost") is None for r in rows):
            return _stop("cost_unread")
        costs = [float(r["cost"]) for r in rows]
        if sum(costs) + max(costs) > float(limit):
            return _stop("budget", f"累計 ${sum(costs):.2f}・最大の周 ${max(costs):.2f}・上限 ${float(limit):.2f}")
    return {"act": "launch", "word": "", "text": f"{len(rows) + 1} 周目を起こす"}


def step(doc: dict, facts: dict) -> dict:
    """周の事実の読みの誤り facts["error"] が在れば halted に訳を付けて返す。無ければ decide。launch になっても運ぶ次の依頼
    facts["request"] が空なら halted"""
    if facts.get("error"):
        return _stop("halted", facts["error"])
    got = decide(doc, facts)
    if got["act"] == "launch" and not facts.get("request"):
        return _stop("halted", "次の周の依頼に運ぶ所見が無い")
    return got


def next_request(prev_next_doc, first_doc) -> dict:
    """次の周の依頼（carry.KEYS の形）。前の周の下書きでない findings・prior_failures・constraints と、1 周目の依頼の answers・pr・
    issue を並べる。下書きの行は運ばない（held_rows が名指して人が見る物へ回す）。first_doc が無ければ 1 周目の答えは無い"""
    prev = prev_next_doc if isinstance(prev_next_doc, dict) else {}
    first = carry.parts(first_doc) if first_doc is not None else {}
    out = {carry.FINDINGS: [r for r in prev.get(carry.FINDINGS) or [] if not carry.is_draft(r)],
           carry.PRIOR: list(prev.get(carry.PRIOR) or [])}
    if prev.get(carry.CONSTRAINTS):
        out[carry.CONSTRAINTS] = list(prev[carry.CONSTRAINTS])
    for key in (carry.PR, carry.ISSUE, carry.ANSWERS):
        if first.get(key):
            out[key] = first[key]
    return out


def held_rows(next_doc) -> list:
    """運ばなかった下書きの行（findings の目的の外の所見と answers の答えの下書き）"""
    return drafts_in(next_doc)


def keys_of(next_doc) -> list:
    """次の依頼の下書きでない findings の鍵（carry.row_key）の並び。前の周と同じかを比べる"""
    nxt = next_doc if isinstance(next_doc, dict) else {}
    return [carry.row_key(r) for r in nxt.get(carry.FINDINGS) or [] if isinstance(r, dict) and not carry.is_draft(r)]


def first_of(first_doc, pr: int):
    """1 周目の依頼に、1 周目に名指した PR の番号 pr（0 なら無し）を pr の欄として重ねずに足した物。次の周の入力 pr には使わず、
    依頼の欄で運ぶ"""
    if not pr:
        return first_doc
    first = dict(first_doc) if isinstance(first_doc, dict) else {carry.FINDINGS: list(first_doc or [])}
    first[carry.PR] = sorted(set(first.get(carry.PR) or []) | {pr})
    return first


def limits(rounds_raw, budget_raw) -> tuple:
    """周の数（1〜MAX_ROUNDS の整数）と費用の上限 USD（空なら None、ほかは正の数）。範囲の外は ValueError（1 行）"""
    rounds = str(rounds_raw if rounds_raw is not None else "").strip()
    if not ROUNDS.fullmatch(rounds) or int(rounds) > MAX_ROUNDS:
        raise ValueError(f"rounds は 1〜{MAX_ROUNDS} の整数（1 は 1 周で止める。受けた値: {rounds_raw!r}）")
    budget = str(budget_raw if budget_raw is not None else "").strip()
    if not budget:
        return int(rounds), None
    if not BUDGET.fullmatch(budget) or float(budget) <= 0:
        raise ValueError(f"budget_usd は正の数（受けた値: {budget_raw!r}）")
    return int(rounds), float(budget)
