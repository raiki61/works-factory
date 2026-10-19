"""結末の語と止めの語の決め（docs/design/report.md の 1.7。lib/outcome.py の decide_outcome・_human_stop・_line_stop・_waits・cut_at・
absorbed_rows を、返りの欄でなく facts の欄を読む形に書き直した写し）。

語の正本（10 語）は lib/report.py の OUTCOMES。どの block の欄が止め・人待ち・残りに当たるかの読み分けは graph が facts に入れる。

- decide(facts, run) -> (結末の語, 止めの語): facts は facts_in.read の返り、run は transcript.facts の返り
- left_all(facts, run) -> 残りの行 [{where, text, unmeasured}]: facts.left に、受け止めた落ちの行を足した物
- outcome_asks(outcome, facts, left) -> 結末で決まる人が決める物 [(種, 1 件の文)]
"""
import answer      # lib/
import oneline     # lib/
import report      # lib/
import stopby      # lib/

OK_OUTCOMES = ("fixed", "fixed_needs_check", "no_fix_needed")
NODE_ERROR = "node-error"
RECORD_INVALID = "record-invalid"
ROUND_LIMIT_REST = "直しきれずに残った物"
RECORD_INVALID_KIND = "記録が通らないこと"


def _at(row: dict) -> str:
    return f"{row['at']}:{row['word']}"


def _human_stop(facts: dict) -> tuple:
    """1. 人の止め: 承認ノードの止める語（文が request: で始まれば止め札）か、止めの語が request:・human: で始まる"""
    for gate in facts["gates"]:
        if gate["decision"] in answer.STOP_WORDS:
            word = "stopped_by_request" if str(gate["text"]).startswith(report.REQUEST_BY) else "stopped_by_human"
            return word, f"{gate['at']}:{gate['decision']}"
    for stop in facts["stops"]:
        if stop["word"].startswith(report.REQUEST_BY):
            return "stopped_by_request", _at(stop)
        if stop["word"].startswith(report.HUMAN_BY):
            return "stopped_by_human", _at(stop)
    return ()


def _line_stop(facts: dict) -> str:
    """2. 線の止め: 機械の語（人待ちの語を除く）の止め、無ければ graph が返りの欄から読んだ止め"""
    for stop in facts["stops"]:
        if stopby.is_line(stop["word"]) and stop["word"] not in stopby.WAITING:
            return _at(stop)
    return _at(facts["halts"][0]) if facts["halts"] else ""


def _cut(facts: dict, run: dict) -> str:
    """3. 途中で終わった所の「<段>:<語>」。run の記録で落ちて先へ進まなかったノードが先、無ければ graph が段の表で決めた切れ目"""
    if run["failed"]:
        return f"{run['failed'][0]}:{NODE_ERROR}"
    return _at(facts["cut"]) if facts["cut"] else ""


def _wait(facts: dict, cut: str) -> str:
    """4. 人待ち: 人に回した申し出 → （途中で終わっていなければ）案の直しを待つ申し出 → 人待ちの語の止め → ほか"""
    waits = facts["waits"]
    rows = [*waits["conflicts"], *([] if cut else waits["conflicts_if_closed"]),
            *(s for s in facts["stops"] if s["word"] in stopby.WAITING), *waits["others"]]
    return _at(rows[0]) if rows else ""


def _include(node: str) -> str:
    head, sep, _ = str(node).partition("__")
    return head if sep else ""


def absorbed_rows(facts: dict, run: dict) -> list:
    """落ちたが受け止められて先へ進んだノードの残りの行（その段が見るはずだった物は確かめていない）。返りの在る include の中の落ちは、
    その block が自分の出力で言うので重ねない"""
    return [{"where": f"{report.ABSORBED_WHERE} {a.get('node')}",
             "text": f"{a.get('node')} が落ちた（誤り: {report._first_error(a)}）——メイングラフは受け止めて先へ進んだが、その段の結果は"
                     "確かめていない（再実行の要あり）",
             "unmeasured": False}
            for a in run["absorbed"] if _include(a.get("node")) not in facts["returned"]]


def left_all(facts: dict, run: dict) -> list:
    return [*facts["left"], *absorbed_rows(facts, run)]


def decide(facts: dict, run: dict) -> tuple[str, str]:
    """結末の語と止めの語。上から順に、最初に当たった物を返す

    1. 人の止め → stopped_by_request / stopped_by_human   2. 線の止め → stopped_by_line   3. 切れ目 cut を決める（返さない）
    4. 人待ち → needs_human   5. 記録が通らない → record_invalid   6. 途中で終わった → interrupted
    7. 残り left_all   8. 直す物が無い → no_fix_needed   9. 残りが測れていない行だけで証が在る → fixed_needs_check
    10. 残りが在るか証が無い → round_limit   11. ほか → fixed"""
    stopped = _human_stop(facts)
    if stopped:
        return stopped
    line = _line_stop(facts)
    if line:
        return "stopped_by_line", line
    cut = _cut(facts, run)
    wait = _wait(facts, cut)
    if wait:
        return "needs_human", wait
    if not facts["start_ok"]:
        return "record_invalid", f"start:{RECORD_INVALID}"
    if facts["problems"]:
        return "record_invalid", f"report:{RECORD_INVALID}"
    if cut:
        return "interrupted", cut
    left = left_all(facts, run)
    if facts["no_fix"] and not left:
        return "no_fix_needed", ""
    if left and all(row["unmeasured"] for row in left) and facts["proved"]:
        return "fixed_needs_check", ""
    if left or not facts["proved"]:
        return "round_limit", ""
    return "fixed", ""


def outcome_asks(outcome: str, facts: dict, left: list) -> list:
    """結末で決まる人が決める物 [(種, 文)]（facts.asks の後ろに足す。fixed_needs_check の確かめ・round_limit の残り・record_invalid）"""
    def said(row):
        return oneline.one_line(f"{row['where']}: {row['text']}")
    if outcome == "fixed_needs_check":
        return [(report.CHECKS_LEFT, said(row)) for row in left]
    if outcome == "round_limit":
        return [(ROUND_LIMIT_REST, said(row)) for row in left if row["where"] not in facts["counted_left"]]
    if outcome == "record_invalid":
        return [(RECORD_INVALID_KIND, outcome)]
    return []
