"""周の鎖の決め（考え chain）。標準ライブラリと持ち越しの住処 carry・報告の見出しの宣言 promptsection だけを import する。

元は今の works（版 2aa7c66cf7abe1fe09699ac2942d107123214168）の works/.shared/core/chain.py。鎖は、1 回の起動が周ごとの run を最大 MAX_ROUNDS 本つなぐ並び。
起こす・待つ・承認・再開・費用の合算はグラフの側が持ち、ここは周の間の決め（次を起こすか・止めの語・次の依頼・最後の差分に採る周）と、
報告 chain.md の描きだけを持つ。git に触れる手続き（周の結果の commit・最後の差分）はグラフの script が持つ。
結末の語は書かず、結末の住処 report.OUTCOME_KINDS が引いた種だけを受ける。

- KIND_*: 結末の種（report.OUTCOME_KINDS の値）。closed＝直し済み・直す物が無い、halted＝止まった、human＝人の判断が要る、
  wait＝途中で落ちた、open＝残りが在る（次の周へ進める）
- STOPS: 鎖の止めの語の表（run の中の止めの理由 stopby とは別の考え）
- decide(doc, facts, budget=None) -> {act, word, text}: 見る順は 周の数 → 結末の種 → 人が要る → 進みが無い → 費用
- step(doc, facts): 周の事実を読めなかった周と、運ぶ依頼の無い launch を halted にしてから decide を呼ぶ
- next_request(prev_next_doc, first_doc)・held_rows(next_doc)・keys_of(next_doc)・first_of(first_doc, pr): 次の周の依頼と、運ばない
  下書きの行と、残りの行の鍵と、1 周目に名指した PR を足した 1 周目の依頼
- limits(rounds_raw, budget_raw): 周の数と費用の上限の入力の確かめ
- pick(rounds) -> (採る周, 採らずに名指す止まった周の並び)・render(doc) -> chain.md の本文（REPORT・REPORT_HEAD・FINAL）

元から変えた所:
- decide は起こした次の周の状態（facts が None の枝・pending・alive）を見ない。起こした周を待つのはグラフの側になった
- 下書きの行は facts["held_rows"] から読む（次の依頼の文書を読むのが別のノードになった）
- 種が読めない時の文で結末の語を名指す（語が無い・語が表に無い）
- next_request は前の周の constraints（前提の検算の実測）も運ぶ
- pick は止まった周を、印 stopped でなく結末の種 halted で見分け、周の結果を result でなく周の commit の head で読む
- render は鎖の控えの代わりに周の決めの行を受け、取り込みの命令を bin/apply <親の run> にする。人が要る時の手順は下書きの在りか
  （行の source）を名指す。独立の目 R2 の作り直しの残りは書かない（bin/apply が R2 の語で拒む）
外した物: 起動の手続きと印（pending・pid・launched・tries・LAUNCH_TRIES・_alive）、止めの語 launch_unbound・launch_failed、
鎖の控えと錠（new_doc・load・save・update・path・locked・_HELD・FILE・LOCK・ENV_KEY）、殻の口（_step・main ほか）、
build_row・_count_files（周の行は決めのノードの script が組み、ファイルの数は最後の差分のノードが周の commit の差分から数える）。
"""
import pathlib
import re
import sys

_HERE = str(pathlib.Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.append(_HERE)

import carry  # noqa: E402
import promptsection  # noqa: E402

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
REPORT, FINAL = "chain.md", "chain/final.diff"   # 親の run の置き場からの相対（bin/apply も引く）
REPORT_HEAD = promptsection.Section("# 周の鎖の報告（run {run}）", human="人が読む鎖の報告 chain.md の見出し。役の指示書には貼らない")
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


def pick(rounds: list):
    """最後の周から戻り、止まりと言われていない（結末の種が halted でなく、周の結果の commit の head が在る）最初の周を採る。
    (採る周か None, 採らずに飛ばした周の並び)。飛ばした周（止まった周と commit できなかった周）は捨てずに名指す（chain.md が
    差分のパスか、作業の残る作業ツリーを添える）"""
    skipped = []
    for r in reversed(rounds):
        if r.get("kind") != KIND_HALTED and r.get("head"):
            return r, skipped
        skipped.append(r)
    return None, skipped


def _left(r: dict, worktree: str) -> str:
    """飛ばした周の作業の在りか: 残した差分のパス・差分が空・commit できず作業ツリーに残る（片付けで消える）"""
    if not r.get("head"):
        return f"commit できなかった。作業は作業ツリー {worktree or '（親の run の作業ツリー）'} に残り、片付けで消える"
    return f"差分 {r.get('diff') or '無し'}"


def _cell(v, fmt="{}", none="読めない"):
    return none if v is None else fmt.format(v)


def render(doc: dict) -> str:
    """chain.md の本文: 頭の 3 行（何が起きたか・止めた訳・人が見る物）、周ごとの表（周・run・結末・分・$・残り・ファイル）、合計、
    最後の差分と取り込み、人が要る時の手順。読めない費用は 0 と書かず「読めない」と名指す。
    doc は {run（親の run）, rounds_max, rounds（周の行。files・diff は最後の差分のノードが足す）, stop（{word, text} か None）,
    original_base, final（最後の差分のパス。書けなければ空）, apply（取り込む命令）, worktree（周の commit を積む親の run の作業ツリー）}"""
    rows = doc.get("rounds") or []
    kept, skipped = pick(rows)
    stop = doc.get("stop") or {}
    final, apply, worktree = doc.get("final") or "", doc.get("apply") or "", doc.get("worktree") or ""
    held = sum(int(r.get("held") or 0) for r in rows)
    notes = []
    if skipped:
        notes.append("止まった周 " + "・".join(f"周 {r['n']}（run {r.get('run') or '—'}。{_left(r, worktree)}）"
                                          for r in skipped) + " は最後の差分に採らなかった")
    if held:
        notes.append(f"運ばなかった下書きの行 {held} 件（見直して新しい依頼に入れる）")
    done = f"{len(rows)} 周のうち{('周 ' + str(kept['n']) + ' の結果までを最後の差分にした') if kept else '採れる周が無かった'}"
    lines = [REPORT_HEAD.format(run=doc.get("run", "")), "",
             f"- 何が起きたか: 指定 {doc.get('rounds_max')} 周のうち {done}（元の基 {(doc.get('original_base') or '—')[:12]}）",
             f"- 止めた訳: {stop.get('word') or '（語なし）'}——{stop.get('text', '')}" if stop
             else "- 止めた訳: 止めていない（次の周の子の run か、その周のノードが落ちた）",
             f"- 人が見る物: {'。'.join(notes) if notes else '無し'}", "",
             "| 周 | run | 結末 | 分 | $ | 残り | ファイル |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(
            r["n"], str(r.get("run", ""))[:8], r.get("outcome") or "（結末を読めない）", _cell(r.get("minutes"), "{:.0f}"),
            _cell(r.get("cost") if r.get("cost_read") else None, "{:.2f}"), len(r.get("keys") or []), _cell(r.get("files"))))
    minutes = [r["minutes"] for r in rows if r.get("minutes") is not None]
    costs = [r["cost"] for r in rows if r.get("cost_read") and r.get("cost") is not None]
    unread = sum(1 for r in rows if not r.get("cost_read") or r.get("cost") is None)
    lines += ["", "合計: {} 周・{} 分・{}".format(
        len(rows), f"{sum(minutes):.0f}" if minutes else "読めない",
        (f"${sum(costs):.2f}" if costs else "読めない") + (f"（費用が読めない周 {unread} 本を除く）" if costs and unread else ""))]
    if kept:
        lines += ["", f"最後の差分: {final or '（書けなかった）'}"]
        if final:
            lines.append(f"取り込む: {apply}")
    if stop.get("word") == "human" or held:
        source = next((r.get("source") for r in reversed(rows) if r.get("source")), "")
        steps = [f"下書き {source or '（子の run の next-request.json）'} の draft・source の行を、採る物は印を消し、採らない物は消す",
                 *([f"取り込むなら {apply}"] if kept and final else []), "見直した依頼を request に渡して周の鎖を起こし直す"]
        lines += ["", "続けずに、下書きを見直して新しい鎖を起こす（保留して続ける口は作らない）:",
                  *(f"{i}. {step}" for i, step in enumerate(steps, 1))]
    for r in skipped:
        lines.append(f"止まった周 {r['n']}: {_left(r, worktree)}（結末 {r.get('outcome') or '読めない'}）")
    return "\n".join(lines) + "\n"
