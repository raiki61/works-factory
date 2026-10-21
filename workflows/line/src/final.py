"""最後の承認ノードの開ける理由と文（docs/design/line.md の 2 節の 4・6 節・8.1。今の workflows/line/scripts/ask_final.py の中身）。

開ける理由の列 needs(got) を 1 つ組み、開くかと冒頭の 1 行目をこの列だけから作る（元 works の line_edge._final_needs）。列の行のうち
守りのパスの当たり（確かめられなかった時も）・書き換えを許したテストに触った・人に回した食い違いの申し出・申し出の控えを読めない・
修正の段の控えを読めない・承認の後に受け入れ条件のテストが変わった（spec の check の questions。照らせなかった時は「照らせなかった」）・
読めなかった控え（直した後の実測・封じた差分・問いの台帳の控えなど。got の unread。読めた控えについての注記 lost_ties は数えない）
は開き方に依らず開く（must。通すのは人の答えだけ）。ほかは開き方 final_gate で開く（src.gates.opens）。無人の run で開くはずの時は
開かずに works:needs-human で止め、merge の apply を飛ばす（L-G39・L-W25）。判定の役が保留にしたままの問いは冒頭と本文に見せるが
開ける理由に数えない（L-G36）。修正の後の並行 PR の確かめ直し（8.1）が重なりを見つけた・確かめ直せなかった時は、開き方で開く理由。

got は ask_final の script が受け皿の got と line の値から組む dict（gather の返り）。読む物は修正の事実（fixed と、その stages の
段ごとの fix・lens・delta-review の got）・試験・目・封じ・判定（judged）・仕様（spec の check）・往復の記録・修正前と案の直しの答え・
並行 PR（修正の後）。どれも受け皿の got を名指して読む（ports.picked。欄の欠けた前の版の返りを空と読まない）。

- needs(got)・final_needs(got)・ask(got, *, mode, unattended, run_id)・final_text(got, why, run_id)・keep(out, place)
- gather(...) -> got: 受け皿の got と line の値から、文と理由の材料を組む
"""
from __future__ import annotations

from pathlib import Path

import answer
import conflict
import declared_checks
import entry
import gatemarks
import green_cert
import oneline
import protect
import querytest
import replan
import runbranch
import seal
import stopby
import structmark

from src import files, gates, stages

PROTECTED_HEAD = "守りのパスを触った"
PROTECTED_UNKNOWN = "守りのパスを確かめられなかった"   # merge が確かめられなかった行（lib/seal.py の UNKNOWN_HEAD）の見出し
ALLOWED_TESTS_HEAD = "書き換えを許したテストを触った"
ALLOWED_UNCHECKED = "封じた差分が無い・読めないので、許した行が差分に在るかを照らしていない（許した行をみな並べた）"
CONFLICT_UNREAD = "食い違いの申し出の控えを読めない"
BESIDE_UNREAD = "修正の段の控えを読めない"
MISSING_HEAD = "控えの指す先が無いか読めない（読めないまま置かないので人に見せる）"
RECORD = "run の置き場の gates/gate-final.json"
HANDOFF_HEAD = "直しの途中で AI が自分で決めずに人に回した物（壊すと分かって通した理由。役だけで決めた代償なので人が確かめる）"   # 元 fixboard
HANDOFF_REASON = "直しの途中で AI が自分で決めずに人に回した物が在る"
MISMATCH_REASON = "直したという申告と機械の数え直しが合わない単位が在る"
NO_AFTER = "直した後の構造の実測: 無い（独立の目の after が無い——実測のノードが落ちたか走らなかった。メイングラフは止めずに進めた）"
SEAL_FELL = "封じの段が返らなかった（merge の seal の受け皿が飛んだ）"
EYES = ("r1", "r2", "r3", "r4")   # 元 lib/eyeverdict.py の EYES
ESCALATE = "escalate"            # 前提の検算が人に上げる語（元 eyeverdict.VERDICTS[1]。r2 の premise_check の verdict）
ADOPTED = "採る"                 # 再審が異議を採った答え（元 judge_accept.ADOPTED。diagnose の出力 rejudge_verdict の enum の頭）
PARALLEL_HEAD = "修正の後の並行 PR の確かめ直し"
PARALLEL_FOUND = "直したファイルが開いている PR と重なる（{n} 件）"
PARALLEL_UNCHECKED = "修正の後の並行 PR の確かめ直しができなかった（{why}）"
PARALLEL_UNDONE = ("not_run", "awaiting_human", "failed")
SPEC_APPLIES = ("  - 承認して報告へ進める（continue）と、差分は承認し直しを待たずに当たる（merge が run の置き場に置き、bin/apply が"
                "対象に当てる）。承認し直してから当てるなら stop で止める")


# ---------------------------------------------------------------- 開ける理由
def tests_word(got: dict) -> str:
    ok, green, red_cause = got["tests_ok"], got["green"], got["red_cause"]
    if ok and green:
        return "緑"
    cause = f"（{red_cause}）" if red_cause else ""
    note = green_cert.ran_note(green=green, red_cause=red_cause, by=got["tests"]["by"], steps=got["ran_steps"])
    return ("赤" if ok else "認証できなかった") + cause + (f"——{note}" if note else "")


def protected(got: dict) -> tuple:
    """守りのパスの行を (確かめられなかった行, 当たった行) に分ける"""
    rows = got["protected_hits"]
    unknown = [row for row in rows if str(row).startswith(seal.UNKNOWN_HEAD)]
    return unknown, [row for row in rows if row not in unknown]


def unpassed_eyes(got: dict) -> list:
    """pass でない目を『R1: 直しが要る』の形で（目の順。言い方は gatemarks.REVIEW_WORDS、表に無い語は字のまま）"""
    rows = [(name.upper(), str(row.get("status"))) for name in EYES if isinstance(row := got["eyes"].get(name), dict)]
    return [f"{label}: {gatemarks.REVIEW_WORDS.get(status, status)}" for label, status in rows if status != seal.PASSED]


def allowed_count(got: dict) -> int:
    return len({row.get("path") for row in got["allowed_tests"]})


def left_objection(got: dict) -> str:
    """止めずに残った異議（再審が採らなかった修正役の異議）。無ければ空"""
    return got["objection"] if got["objection"] and got["rejudge_verdict"] != ADOPTED else ""


def parallel_reason(got: dict) -> str:
    """修正の後の並行 PR の確かめ直しの開ける理由（回らなかった・重ならなかった run は空。8.1）"""
    after = got["parallel_after"]
    if after is None:
        return ""
    status = str(after.get("status") or "")
    if status == "found":
        material = after.get("material") if isinstance(after.get("material"), dict) else {}
        count = material.get("count") if isinstance(material.get("count"), int) else "?"
        return PARALLEL_FOUND.format(n=count)
    if status in PARALLEL_UNDONE or after.get("ok") is not True:
        return PARALLEL_UNCHECKED.format(why=oneline.one_line(after.get("reason") or after.get("stop_reason") or status or "訳が無い"))
    return ""


def needs(got: dict) -> list:
    """最後の承認ノードを開ける理由の列 [(1 句, 開き方に依らず開くか)]"""
    why = []
    if got["spec_changed"]:
        said = gatemarks.spec_words(got["spec_unchecked"]).said
        why.append((f"{said}（{len(got['spec_changed'])} 件。承認し直すかは次の run で答える）", True))
    unknown, hits = protected(got)
    if unknown:
        why.append((f"{PROTECTED_UNKNOWN}（人の確かめが要る）", True))
    if hits:
        why.append((f"{PROTECTED_HEAD}（{got['protected_count']} 件。人の確かめが要る）", True))
    if got["allowed_tests"]:
        why.append((f"{ALLOWED_TESTS_HEAD}（{allowed_count(got)} 件。人の確かめが要る）", True))
    word = tests_word(got)
    if word != "緑":
        why.append((f"最後のテストが{word}", False))
    if got["conflicts_unread"]:
        why.append((f"{CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した申し出を数えられない）", True))
    if got["asked"]:
        why.append((f"{conflict.HEAD}を人に回した（{len(got['asked'])} 件）", True))
    if got.get("missing"):
        why.append((f"{MISSING_HEAD}（{len(got['missing'])} 件: {'・'.join(got['missing'])}）", True))
    if got["beside_unread"]:
        why.append((f"{BESIDE_UNREAD}（{len(got['beside_unread'])} 件。人に回した物・数え直しの食い違いを数えられない）", True))
    if got["unread"]:
        why.append((f"読めなかった控えが在る（{len(got['unread'])} 件。数え漏れが在りうるので人の確かめが要る）", True))
    if got["handoffs"]:
        why.append((f"{HANDOFF_REASON}（{len(got['handoffs'])} 件）", False))
    parallel = parallel_reason(got)
    if parallel:
        why.append((parallel, False))
    unpassed = unpassed_eyes(got)
    if unpassed:
        why.append((f"独立の目が通さなかった（{'・'.join(unpassed)}）", False))
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict) and premise.get("verdict") == ESCALATE:
        why.append(("前提の検算が人に上げた", False))
    if got["mismatched"]:
        why.append((f"{MISMATCH_REASON}（{len(got['mismatched'])} 件）", False))
    if got["fenced"]:
        why.append((f"考えの住処の柵の数が増えた（{len(got['fenced'])} 件。住処へ寄せるか、増やすなら地図と柵の表を直す）", False))
    if got["questions"]:
        why.append((f"人に聞いている問いが在る（{len(got['questions'])} 件）", False))
    if left_objection(got):
        why.append(("止めずに残った異議が在る", False))
    if not got["sealed"]:
        why.append((f"差分を封じられなかった（{got['seal_reason'] or '訳が無い'}）", False))
    return why


def final_needs(got: dict) -> list:
    return [phrase for phrase, _ in needs(got)]


# ---------------------------------------------------------------- 文
def final_head(got: dict, why: list) -> list:
    guarded = bool(got["protected_hits"]) or bool(got["allowed_tests"])
    held = got["held"]
    happened = (f"最後のテストと独立の目が済み、報告の前で止まった。テストは{tests_word(got)}。"
                + ("開けた理由: " + "・".join(why) if why else
                   f"承認ノードはいつも開く設定（{gates.head_words({gates.FINAL_KEY: gates.ALWAYS})}）で、ほかに開けた理由は無い")
                + (f"。判定の役が人に聞くと保留にしたままの問いも在る（{len(held)} 件。承認ノードを開ける理由には数えない）" if held else "")
                + (f"。{got['split']}" if got["split"] else ""))
    decide = ("報告へ進めて run を終えるか、止めるか（打つ行は末尾の答え方）"
              + ("。守りのパスと許したテストの変更は下の最初のセクションを確かめてから通す" if guarded else ""))
    return gatemarks.head3(happened, decide, gatemarks.pushes([*held, *got["questions"]]))


def protected_section(got: dict) -> list:
    unknown, hits = protected(got)
    lines = []
    if unknown:
        lines += [f"## {PROTECTED_UNKNOWN}（差分が一覧に触れていないとは言えない）", "",
                  *[f"- 理由: {str(row).removeprefix(seal.UNKNOWN_HEAD)}" for row in unknown], f"- 一覧: {protect.MANIFEST}", ""]
    if hits:
        lines += [f"## {PROTECTED_HEAD}（{got['protected_count']} 件。works 自身の試験・柵・受け付けの口。通すのは人の答えだけ）", "",
                  *[f"- {p}" for p in hits],
                  f"- 差分: git -C {got['worktree']} diff {got['base_rev'][:12] or '<起点の版が記録に無い>'} -- <パス>（未追跡は新しいファイル）",
                  f"- 一覧: {protect.MANIFEST}", ""]
    if got["allowed_tests"]:
        lines += [f"## {ALLOWED_TESTS_HEAD}（{allowed_count(got)} 件。承認済みの案と範囲の相談と裁定が書き換えを許したテスト。"
                  "通すのは人の答えだけ）", "",
                  *[f"- {row.get('path')}（許し {row.get('permit')}・{row.get('source')}）" for row in got["allowed_tests"]],
                  *([ALLOWED_UNCHECKED] if got["allowed_untouched"] is None else []), ""]
    if got["allowed_untouched"]:
        lines += [f"- 書き換えを許したが封じた差分が触らなかったテスト: {got['allowed_untouched']} 件（確かめは要らない）", ""]
    return lines


def conflict_section(got: dict) -> list:
    lines = []
    if got["asked"]:
        lines += [f"## {conflict.HEAD}（{len(got['asked'])} 件。裁定役か機械が人に回した。直しの在りかは行ごとの末尾の括弧。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["asked"]], ""]
    if got["conflicts_unread"]:
        lines += [f"## {CONFLICT_UNREAD}（{len(got['conflicts_unread'])} 件。人に回した行かを数えられない。通すのは人の答えだけ）", "",
                  *[f"- {row}" for row in got["conflicts_unread"]], ""]
    if got["beside_unread"]:
        lines += [f"## {BESIDE_UNREAD}（{len(got['beside_unread'])} 件。人に回した物と数え直しの食い違いを数えられない。通すのは人の答えだけ）",
                  "", *[f"- {row}" for row in got["beside_unread"]], ""]
    return lines


def rows_section(head: str, rows: list, tail: str = "") -> list:
    return [f"## {head}（{len(rows)} 件{tail}）", "", *[f"- {row}" for row in rows], ""] if rows else []


def _bullet(x: str) -> str:
    return x if x[:1].isspace() else f"- {x}"


def tests_lines(got: dict) -> list:
    ev = got["tests"]
    lines = [f"- テストの一式: {ev['suites']}", f"- {ev['baseline']}"]
    if ev["by"] == declared_checks.ROLE_NEEDED:
        lines.append(f"- {declared_checks.SELF_REPORTED_NOTE}。確かめてから通すか（continue の一言に何を走らせて何色だったか）、止めるか（stop）")
    lines += [_bullet(x) for x in [*got["tests_left"], *got["gates"]]]
    lines.append(f"- ログ: {ev['log']}")
    if ev["reason"]:
        lines.append(f"- 走れなかった・認証しなかった理由: {ev['reason']}")
    if ev["unread"]:
        lines.append(f"- {ev['unread']}")
    lines.append(f"- run の作業ツリー: {got['worktree']}")
    return lines


def delta_lines(got: dict) -> list:
    """段ごとの差分の審査とレンズの行（delta-review と lens の block の report の行。回さなかった段は訳の 1 行）"""
    return [_bullet(x) for x in got["delta"]]


def eye_lines(got: dict) -> list:
    unpassed = unpassed_eyes(got)
    lines = [f"- 独立の目の判定（通さなかった目: {'・'.join(unpassed) or '無い'}）:"]
    missing = []
    for name in EYES:
        row = got["eyes"].get(name)
        if not isinstance(row, dict):
            missing.append(name.upper())
            lines.append(f"  - {gatemarks.EYES[name.upper()]}（{name.upper()}）: 結果が無い（深さで省いたか、目の graph が返さなかった）")
            continue
        reason = oneline.one_line(row.get("reason") or "")
        lines.append(f"  - {gatemarks.eye_named(name.upper(), row.get('status'))}" + (f"——理由: {reason}" if reason else ""))
        if name == "r2":
            lines += [f"    - {x}" for x in got["r2_inputs"]]
    premise = got["eyes"].get("premise_check")
    if isinstance(premise, dict):
        lines.append(f"  - 前提の検算: {premise.get('verdict') or '語が無い'}（{oneline.one_line(premise.get('reason') or '')}）")
        lines += [f"    - {x}" for x in premise.get("facts") or [] if isinstance(x, str)]
    lines.append(f"- 残り（最後の承認ノードで数えられる分）: 独立の目が通さなかった目 {len(unpassed)} 件（{'・'.join(unpassed) or '無し'}）・"
                 f"結果が無い目 {len(missing)} 件（{'・'.join(missing) or '無し'}）・最後のテストが緑でない "
                 f"{0 if tests_word(got) == '緑' else 1} 件・柵の増え {len(got['fenced'])} 件")
    lines += [_bullet(x) for x in got["always"]]
    return lines


def parallel_lines(got: dict) -> list:
    """修正の後の並行 PR の確かめ直しの行（parallel-pr の block の report。回らなかった run は行を出さない）"""
    after = got["parallel_after"]
    if after is None:
        return []
    reason = parallel_reason(got)
    return [f"- {PARALLEL_HEAD}: {reason or '重なりは無い'}", *[f"  - {x}" for x in after.get("report") or [] if isinstance(x, str)]]


def question_lines(got: dict) -> list:
    lines = []
    if got["spec_changed"]:
        head = gatemarks.spec_words(got["spec_unchecked"]).head
        lines.append(f"- {head}: {len(got['spec_changed'])} 件")
        lines += [f"  - {q}" for q in got["spec_changed"]]
        lines.append("  - この承認ノードの答えはこの問いに答えない（continue でも仕様は承認し直さない）。問いは報告の冒頭と次の run の依頼の下書きへ渡る")
        lines.append(SPEC_APPLIES)
    if got["questions"]:
        lines.append(f"- {gatemarks.named(gatemarks.R4_GATE_NODE)}が人に聞いている問い（記録のまま引く。{len(got['questions'])} 件）:")
        for q in got["questions"]:
            lines += [f"  {x}" for x in gatemarks.quote(q)]
        lines.append("  - この承認ノードの答えはこの問いに答えない。問いは報告の冒頭と次の run の依頼の下書きへ渡る")
    if got["held"]:
        lines.append(f"- 判定の役が人に聞くと保留にしたままの問い（問いの台帳・{len(got['held'])} 件。この承認ノードの答えは問いに答えない。"
                     "問いは報告の冒頭に並ぶ）:")
        lines += [f"  - {q}" for q in got["held"]]
        lines.append(f"  {gatemarks.ANSWER_HOW}")
    if got["answered"]:
        lines.append(f"- {gatemarks.ANSWERED_HEAD}（問いの台帳・{len(got['answered'])} 件。保留の件数には数えない）:")
        lines += [f"  - {x}" for x in got["answered"]]
    lines += [f"- {x}" for x in got["unmatched"]]
    lines += [f"- {x}" for x in got["unread_holds"]]
    if not (got["spec_changed"] or got["questions"] or got["held"] or got["answered"] or got["unmatched"]):
        lines.append("- 共有ボードの問い: 無い")
    return lines


def pr_line(got: dict) -> list:
    """出口の語 pr の run で報告へ進めると対象に書く事（ほかの run は行を出さない）"""
    if not got["deliver_pr"]:
        return []
    head = f"- 報告へ進める（continue）と（出口 deliver={entry.DELIVER_PR}）: "
    if not (got["sealed"] and got["hash"]):
        return [f"{head}封じた差分が無いので、承認しても積まず PR も作らない"]
    branch, base, reason = runbranch.pr_branches(Path.cwd(), runbranch.ORIGIN)
    done = (f"報告の前に run の枝 {branch} へ commit を積んで push し、{base} へ向けた PR を作る（merge はしない）" if not reason else
            f"run の枝へ commit を積んで push し PR を作るはずだが、今の作業ツリーの読みでは積む前に止まる見込み（{reason}）")
    return [f"{head}{done}。止めれば対象の repo に何も書かない"]


def final_text(got: dict, why: list, run_id: str) -> str:
    """本文の節の並びは今のまま（docs/design/line.md の 2 節の 4）。「修正の後の並行 PR の確かめ直し」を独立の目の前に足した"""
    lines = [*final_head(got, why), ""]
    lines += protected_section(got)
    lines += conflict_section(got)
    lines += rows_section(HANDOFF_HEAD, got["handoffs"], "。通すのは人の continue だけ")
    lines += rows_section(querytest.STUCK_HEAD, got["stuck"])
    lines += rows_section(querytest.UNPROVEN_HEAD, got["unproven"])
    lines += rows_section(querytest.CLOSURE_HEAD, got["closure"])
    lines += rows_section(replan.AMEND_HEAD, got["amend"])
    lines += [f"最後の承認ノード（最後のテストと独立の目の後・報告の前）: テストは{tests_word(got)}", ""]
    lines += tests_lines(got)
    lines += delta_lines(got)
    lines.append(f"- 止めずに残った異議: {left_objection(got) or '無い'}")
    lines += ["- 再審で決着した結果:", *[f"  {x}" if x.startswith("  ") else f"  - {x}" for x in got["rejudge"]]] if got["rejudge"] \
        else ["- 再審: 無い"]
    lines += [f"- 構造のサブグラフ: {got['structure_missing']}"] if got["structure_missing"] else []
    lines += [_bullet(x) for x in got["after"]]
    if got["passes"]:
        lines.append(f"- 直す前の承認ノードで通した項目（決め手が在るので聞かずに通した行と、人が通したので後の承認ノードで聞き直さなかった行。"
                     f"{len(got['passes'])} 件）:")
        lines += [f"  - {x}" for x in got["passes"]]
    lines += [_bullet(x) for x in got["converge"]]
    lines += [f"- {x}" for x in seal.deleted_lines(got["deleted"], where=got["sealed_diff"])]
    lines += parallel_lines(got)
    lines += eye_lines(got)
    lines += question_lines(got)
    lines += [f"- {why_}" for why_ in got["unread"]]
    lines += [f"- {note}" for note in got["lost_ties"]]
    lines += [f"- 封じた差分の hash: {got['hash'] or '（無い）'}", *pr_line(got),
              f"- この文の控え: run の置き場の {files.FINAL_GATE_MD}", "",
              "答え方（人が決める承認ノード。依頼者に聞いて、その言葉で答える）:",
              f"- 報告へ進める: {answer.line(run_id, 'continue', '<一言>')}（一言は {RECORD} に残る）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"


def ask(got: dict, *, mode: str, unattended: bool, run_id: str) -> dict:
    why, must = final_needs(got), any(m for _, m in needs(got))
    opens = must or gates.opens(mode or gates.ALWAYS, reasons=why, guarded=bool(got["protected_hits"]))
    if not opens:
        return {"open": False, "go": True, "stop_reason": "", "text": "", "reasons": why}
    if unattended:
        return {"open": False, "go": False, "stop_reason": stopby.NEEDS_HUMAN, "text": "", "reasons": why}
    return {"open": True, "go": True, "stop_reason": "", "text": final_text(got, why, run_id), "reasons": why}


def keep(out: dict, place: Path) -> dict:
    """開いた承認ノードの文を place の FINAL_GATE_MD に残す（書けなければ文の末尾に訳を足す）"""
    if out["open"]:
        try:
            path = Path(place) / files.FINAL_GATE_MD
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out["text"], encoding="utf-8")
        except OSError as error:
            out = {**out, "text": out["text"] + f"\n（この文の控えを書けない: {error}）\n"}
    return out


# ---------------------------------------------------------------- 材料（受け皿の got から）
def asked_conflicts(pointers) -> tuple:
    """(人に回した申し出の行, 控えを読めなかった訳)。fixed の conflicts（fix と refix の conflicts の pointer の並び）の先のフォルダごとに
    lib/conflict.py の human_lines を足す。読めない控えは訳にして数えない（黙って 0 にしない）"""
    rows, unread = [], []
    for ptr in pointers or []:
        try:
            folder = Path(gates.path_of(ptr)).parent
            if not (folder / conflict.FILE).is_file():
                raise ValueError(f"{conflict.FILE} が無い")
            rows += conflict.human_lines(folder)
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
            where = ptr.get("path") if isinstance(ptr, dict) else ptr
            unread.append(f"{where}: {type(error).__name__}: {oneline.one_line(error)}")
    return rows, unread


def ledger_rows(judged: dict | None, record: dict, before_fix, *, unattended: bool) -> tuple:
    """(問いの台帳から並べる行 {held, answered, unmatched, unread_holds, lost_ties}, 読めなかった訳の行)。lost_ties は読めた控えについての注記
    （結びの宛て先が今の問いにも単位にも無く字の一致で当てた。材料に見せるだけで、読めなかった控えには数えない）。判定・結び・素材の状態は judged の pointer、依頼の答えは
    始めの記録、修正前の答えは fix-in が運んだ物（gatemarks.ledger_files。結びの宛て先が今の問いにも単位にも無ければ字の一致に落とし、
    そのことを lost_ties の行にする）。判定が無い時は空、読めなければ読めなかった訳の行"""
    empty = {"held": [], "answered": [], "unmatched": [], "unread_holds": [], "lost_ties": []}
    if judged is None or judged.get("judgment") is None:
        return empty, []
    try:
        doc = gates.read_json(gates.path_of(judged["judgment"])) or {}
        b = gatemarks.ledger_files(doc, ties_file=gates.path_of(judged.get("answer_ties")) or None,
                                   materials_file=gates.path_of(judged.get("materials")) or None,
                                   answers=gates.request_answers(record), gate=before_fix, takes_push=unattended)
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return empty, [f"判定の問いの控えか始めの記録を読めない（保留の問いを数えていない。{type(error).__name__}: {error}）"]
    units = [u.get("key") for u in b.record["units"]]
    return ({"held": gatemarks.held_lines(b), "answered": gatemarks.answered_lines(b),
             "unmatched": gatemarks.unmatched_answer_lines(b), "unread_holds": gatemarks.unread_hold_lines(b),
             "lost_ties": gatemarks.lost_ties(b.ties, b.record["questions"], units)}, [])


def after_rows(after) -> tuple:
    """(柵の増えの行, 直した後の実測の行, 読めなかった訳)。実測が無い（after が null）時はそう言う 1 行（NO_AFTER）"""
    if after is None:
        return [], [NO_AFTER], ""
    try:
        folder = Path(gates.path_of(after)).parent
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return [], [], f"直した後の実測のポインタを読めない（柵の増えを数えていない。{type(error).__name__}: {error}）"
    if structmark.read_after(folder) is None:
        return [], [], f"直した後の実測の控え {structmark.AFTER_FILE} を読めない（柵の増えを数えていない）"
    return structmark.after_rows(folder), structmark.after_lines(folder), ""


def structure_missing(structure) -> str:
    """構造の目が落ちた run の 1 文（structmark.note）。落ちていない・控えが無ければ空。pointer が読めなければその訳"""
    if structure is None:
        return ""
    try:
        state = Path(gates.path_of(structure))
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return f"構造の目の控えのポインタを読めない（{type(error).__name__}: {error}）"
    return structmark.note(structmark.read(state))


def sealed_files(diff) -> tuple:
    """(封じた差分が消すファイル, 触るファイルの集まりか None（差分が無い・読めない）, 読めなかった訳)"""
    if diff is None:
        return [], None, ""
    try:
        text = Path(gates.path_of(diff)).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], None, (f"封じた差分を読めない（取り込むと消えるファイルと、許したテストのうち触った物を数えていない。"
                          f"{type(error).__name__}: {error}）")
    return seal.deleted_paths(text), seal.touched_paths(text), ""


def touched_allowed(rows: list, touched) -> tuple:
    if touched is None:
        return rows, None
    return [row for row in rows if row.get("path") in touched], len({row.get("path") for row in rows} - touched)


def stage_delta_lines(stage_rows: list, skip_why: str) -> list:
    """段ごとの差分の審査とレンズの行: 回った段は lens と delta-review の report の行のまま、回さなかった段は訳の 1 行"""
    out = []
    for n, s in enumerate(stage_rows or [], 1):
        if not isinstance(s, dict) or s.get("fix") is None:
            continue
        label = stages.STAGE_NAMES[n - 1] if n <= len(stages.STAGE_NAMES) else f"段 {n}"
        lens, delta = s.get("lens"), s.get("delta")
        if lens is None and delta is None:
            out.append(f"差分の審査（{label}）: 回っていない（{skip_why or '変更の確かめが通らなかったか、戻せず当たったままの組が在った'}）")
            continue
        out.append(f"差分の審査（{label}）:")
        out += [f"  - {x}" for part in (lens, delta) if isinstance(part, dict) for x in part.get("report") or [] if isinstance(x, str)]
    return out


def fix_beside(stage_rows: list) -> dict:
    """修正の段ごとの返りの控えの欄から最後の承認ノードに並べる行（src.stages の read と行の口。integration.md の 4.5-3）"""
    got = stages.read([stages.stage(s["fix"]) for s in stage_rows or [] if isinstance(s, dict) and isinstance(s.get("fix"), dict)],
                      stages.resolve)
    return {"stuck": stages.closure_lines(got, stuck_only=True), "closure": stages.closure_lines(got),
            "tests_left": stages.tests_left_lines(got), "gates": [*stages.gates_lines(got), *stages.plan_ask_lines(got)],
            "always": stages.always_rows(got), "allowed": got["allowed"], "beside_unread": got["unread"]}


def judged_rows(judged: dict | None) -> list:
    """決着した再審の結果の行（judged が組んだ lines。「再審されずに残った異議」の行は「止めずに残った異議」の 1 行が持つので外す）"""
    return [x for x in (judged or {}).get("lines") or [] if isinstance(x, str) and not x.startswith("再審されずに残った異議")]


def unproven_lines(judgment) -> list:
    """例で試していない単位の行（元 runreport.unproven_lines。判定の judgment の units から querytest.unproven で出し直す。開いた単位は
    元の検証器の is_open と同じ式 gatemarks._fix_duty）。判定が無ければ []、判定の pointer を開けなければ訳の 1 行（黙って 0 件にしない）"""
    try:
        doc = gates.read_json(gates.path_of(judgment)) if judgment is not None else None
    except (OSError, ValueError, TypeError) as error:
        return [f"判定を読めないので、例で試していない単位を数えていない（{type(error).__name__}: {error}）"]
    units = [u for u in (doc or {}).get("units") or [] if isinstance(u, dict) and isinstance(u.get("key"), str)] \
        if isinstance(doc, dict) else []
    return [f"{r['key']}: {r['why']}" for r in querytest.unproven(units, gatemarks._fix_duty)]


def split_and_unproven(fixed: dict, judgment) -> tuple:
    """(冒頭 1 行目に添える、受けた単位と止めて持ち越した単位の 1 文, 例で試していない単位の行)。1 文は報告と同じ src.facts の口"""
    from src import facts
    return facts.split_line({"fix": {"groups": fixed.get("groups") or [], "units": fixed.get("units") or []}}), unproven_lines(judgment)


def gather(*, fix_in: dict, fixed: dict, judged: dict | None, tests: dict | None, eyes: dict | None, seal_got: dict | None,
           spec_check: dict | None, parallel_after: dict | None, replan_answer, widened, record: dict, given: dict, rounds_lines: list,
           unread: list, missing=()) -> dict:
    """受け皿の got と line の値から、文と理由の材料 got を組む（docs/design/line.md の 2 節の 4 の「読む物」）。missing は指す先が
    無いか読めない控えの訳（src.gates.located。開き方に依らず開ける理由にする）"""
    missing = list(missing)
    tests_ = tests or {}
    eye = eyes or {}
    if seal_got is None:
        closing = ({"ok": True, "reason": "", "hash": "", "protected_hits": [], "protected_count": 0, "diff": None} if fixed.get("no_fix")
                   else {"ok": False, "reason": SEAL_FELL, "hash": "", "protected_hits": [], "protected_count": 0, "diff": None})
    else:
        closing = seal_got
    hits = closing.get("protected_hits") or []
    count = closing.get("protected_count")
    after_fenced, after, after_unread = after_rows(eye.get("after")) if eyes is not None else ([], [NO_AFTER], "")
    asked, conflicts_unread = asked_conflicts(fixed.get("conflicts"))
    deleted, touched, deleted_unread = sealed_files(closing.get("diff"))
    beside = fix_beside(fixed.get("stages"))
    allowed, untouched = touched_allowed(beside.pop("allowed"), touched)
    rows, ledger_unread = ledger_rows(judged, record, fix_in.get("answer"), unattended=bool(given.get("unattended")))
    split, unproven = split_and_unproven(fixed, (judged or {}).get("judgment"))
    passes = gatemarks.pass_lines([*(fix_in.get("passes") or []), *(eye.get("passes") or [])])
    return {
        "tests_ok": tests_.get("ok") is True, "green": tests_.get("green") is True, "red_cause": str(tests_.get("red_cause") or ""),
        "ran_steps": tests_.get("ran_steps"),
        "tests": {**declared_checks.gate_values(tests), "unread": "" if tests is not None else "最後のテストの証拠が無い（試験の関門が返さなかった）"},
        "worktree": str(Path.cwd().resolve()), "base_rev": str(given.get("base_rev") or ""),
        "deliver_pr": str(given.get("deliver") or "").strip() == entry.DELIVER_PR,
        "protected_hits": hits, "protected_count": count if isinstance(count, int) else len(protected({"protected_hits": hits})[1]),
        "asked": asked, "conflicts_unread": conflicts_unread,
        "handoffs": [x for x in fixed.get("handoffs") or [] if isinstance(x, str)],
        "mismatched": [x for x in fixed.get("mismatched") or [] if isinstance(x, str)],
        "eyes": {name: eye.get(name) for name in (*EYES, "premise_check")},
        "questions": [q for q in eye.get("questions") or [] if isinstance(q, str)],
        "spec_changed": [q for q in (spec_check or {}).get("questions") or [] if isinstance(q, str)],
        "spec_unchecked": (spec_check or {}).get("unchecked") is True,
        "objection": str(fixed.get("objection") or ""), "rejudge_verdict": str((judged or {}).get("rejudge_verdict") or ""),
        "rejudge": judged_rows(judged), "split": split, "unproven": unproven,
        "amend": replan.amend_lines(fixed.get("replan_items") or [], refixed=fixed.get("refixed") is True, answer=replan_answer,
                                    widened=widened or [], gate="gate-replan"),
        "delta": stage_delta_lines(fixed.get("stages"), str(fixed.get("skip_why") or "")),
        **beside, "allowed_tests": allowed, "allowed_untouched": untouched,
        "structure_missing": structure_missing(fix_in.get("structure")),
        "sealed": closing.get("ok") is True, "seal_reason": str(closing.get("reason") or ""), "hash": str(closing.get("hash") or ""),
        "deleted": deleted, "sealed_diff": gates.located(closing.get("diff"), "封じた差分", missing),
        "fenced": after_fenced, "after": after, "passes": passes,
        "r2_inputs": [x for x in eye.get("notes") or [] if isinstance(x, str)],
        "converge": rounds_lines, "parallel_after": parallel_after,
        **rows,
        "missing": list(dict.fromkeys(missing)),
        "unread": [*unread, *ledger_unread, *([after_unread] if after_unread else []), *([deleted_unread] if deleted_unread else [])],
    }


def merge_values(tests: dict | None, eyes: dict | None, seal_got: dict | None) -> dict:
    """merge の apply に渡す値（受け皿の got の中の欄は Archon の with: で読めないので、この node が返す）。封じが飛んだ・落ちた時は
    sealed_hash が空（apply は封じた hash と今の差分を照らせず拒む）"""
    sealed = seal_got is not None and seal_got.get("ok") is True
    return {"sealed_hash": str(seal_got.get("hash") or "") if sealed else "",
            "fingerprint": (tests or {}).get("fingerprint") if isinstance((tests or {}).get("fingerprint"), dict) else None,
            "green_ok": (tests or {}).get("ok") is True, "eyes_ok": (eyes or {}).get("ok") is True,
            "r2": (eyes or {}).get("r2") if isinstance((eyes or {}).get("r2"), dict) else None}

