"""機械が組む短い報告（P1 計画 Task 27・〔線A計〕T15。仕様 6 節・裁定 TA12・TA15）。AI は書かない。文は機械の定型だけ。

**記録が検証器を通らない run に fixed・no_fix_needed を出す道を作らない**（審査 I3）: build は必ず gate_record で
settle → finalize → run_validator を 1 度踏み、受理集合（report_accepts）の外か、今の周の記録（record_round と converge）が
済んでいなければ record_invalid にする。検証器は validator_runner の包み（board_hook.py）が効く b.run_validator で回す。
**残り（検証器の阻害・最後のテストが緑でない・独立の目の阻害と走っていない目と結果が無い目）が在る run に fixed を出さない**: 直した周で residue が 1 行でも
返せば round_limit（残りが今の周に測れていない素材の行だけなら fixed_needs_check）にし、冒頭 1 と次の run の依頼に残りの行を字のまま出す（直す物が無い周は no_fix_needed のまま。赤は冒頭 1 に出る）。

口（線 B の報告も呼ぶ。線 B の申し送り 3・TA18。どの head_* も盤面を書かない）:
- OUTCOMES・COST_FIELD_VERIFIED・FIRST_ROUND_LINE
- OUTCOME_KINDS（結末の語 → 周の鎖が見る種）・header_outcome(board_dir)（報告の冒頭の結末の語）・round_facts(board_dir, events, run_doc) -> 終わった周の結末・種・費用・分・止まり・起点の版
  （鎖 chain.py が読む。結末の語と費用の欄の名を知る場所は増やさず、ここが束ねる）
- gate_record(b) -> {exit, accepted, out, tail, traces, round_closed}
- residue(b, gate, *, tests=None, eyeing=None, absorbed=()) -> fixed を名乗らせない残り [{where, text}]
- decide_outcome(b, gate, *, tests=None, judged=None, eyeing=None, absorbed=()) -> OUTCOMES の 1 つ
- stop_outcome(b) -> 盤面の止めの (結末の語, by, 一言) か ()・stopped_run(board_dir) -> 当てる前に見る記録の止まり（記録が無いか読めなければ None）
- head_decisions(b, gate, …)（冒頭 1）・head_entry(b, start, *, cleaned_runs="")（冒頭 2）・head_stop(b, *, interrupted=None, failed=None, retried=None)（冒頭 3）・
  head_reads(board_dir, run_id, *, ci=None)（冒頭 4）・head_where(b)（冒頭 5）・head_models(board_dir, launches)・head_cost(board_dir, run_id, *, events, launches)
- declared_downgrades(line) -> [{node, what, versus}]（PACK/<line>/downgrades.json。無ければ []）
- cost_rows(events, launches) -> [{node, reported, actual, continued_from, base, aggregate}]
- next_request(b, *, tests=None, left=None, interrupted=None) -> 次の run に渡す依頼の findings [{where, text}]（依頼の型のまま。R2 の作り直しの行は除く。
  interrupted が None でない（途中で落ちた run）時だけ、案の直しを待つ行（未完了）の単位の行を足す。
  判定が目的の外として単位にしなかった材料の所見は材料の行の任意の欄 mechanism・measured・false_positive_if と、下書きの印
  draft・source も持つ。印の在る行は依頼の入口が拒むので、人が見直すまで次の run の目的にならない）
- next_doc(b, items, prior) -> next-request.json の中身 {findings, prior_failures, answers?}（answers は人の判断を待つ項目への答えの下書き）
- prior_failures(b, left=None) -> この run で最後まで通らなかった受け付けと R2 の作り直しの理由 [{where, text}]（次の依頼の prior_failures）
- handoff_lines(b) -> 修正役が人に回した物の行（breaks.accepted。冒頭 1・冒頭 3 行と最後の関所が同じ行を出す）
- rejudge_lines(b) -> 決着した再審の結果の行（冒頭 1 と最後の関所の文が同じ行を出す）
- branch_rows(b)・eye_ties(b) -> 差分の審査の穴と独立の目が場所を挙げた行の枝の名札の行（線の木の段 4a。冒頭 1 と最後の関所の文が同じ行を出す。穴も行も無ければ空）
- verify_lines(b) -> 判定の単位の裏取りの行（周ごと。根本でない・証拠が無い・場所が違う・確かめられなかった単位と単位どうしの重複・
  順番。全部の単位が根本で合えば件数の 1 行。単位は消さないので、人が単位を減らすかを決める材料）
- tests_word(b, tests)・eye_counts(b, reviews) -> EyeCounts(blocked, not_run, missing)・rest_outside_validator(b, *, tests, counts, exit_problem="", absorbed=()) -> Rest(tests_word, counts, rows)
  （検証器の外の残りの数えの正本。最後の関所と冒頭 1・次の依頼が同じ口を読む。NOT_RUN_GATE_NOTE が not_run の例外の理由）
- always_rows(b, left=None, *, rest=None) -> clean が消したファイル・レンズ・仕組みの異常・残りの件数の行（0 件も、
  走らせていない・調べていない・読めないも。冒頭 1 は left を渡し、最後の関所は rest を渡して数えられる分を言う。どちらも無い呼びは渡し忘れを名指す）・anomalies(b)・anomaly_lines(b, *, full=False, found_only=False)（仕組みの異常。報告の「仕組みの異常」の節）
- build(board_dir, *, judged, tests, start, ci=None, run_id="", events=None, launches=None, interrupted=None,
  failed=None, retried=None, eyeing=None, cleaned_runs="", depth_lines=(), tdd=(), absorbed=None) -> dict（盤面を読む前に、落ちの無い run（interrupted が None）だけ replan.close_at で案の直しを待つ行を諦めた行にする。落ちた run は待つ行のまま未完了と報告し、resume で続ける）
- tdd_lines(stages) -> 修正の段ごとの TDD の輪の単位の結末の行（keep-essence の 11。修正のブロックの出口 tdd を読む）
- freeze_lines(stages) -> 冒頭 2 の行: TDD の輪を回していない修正の段はテストの凍結が効いていないと言う（keep-essence の 3）
- final_result(machine, ai) -> dict（ラインの出口: 機械の報告の出口に AI の報告の結果を足し、最後の報告のファイルを選ぶ）

盤面の上の名前（最後の関所の答え final-gate-answer.json と止めた口 human:final-gate、止め札の trace の op stop_flag_seen、
再審の差分 rejudge-diff.json と出口 rejudge-exit.json、判定の単位の裏取りの申し送り
judge-verify.json）は書き手のモジュール（ライン・ブロック）を import せずに
ファイルの名前として読む（層 L3 は上の層を import しない。裁定 R59）。書き手と名前を揃えるのは試験（test_report）。
並行 PR の外した範囲の名は住処 marks の KINDS から引く。

この版で持たない物（報告に書く）: 版の一覧の行（P1 Task 18・19 の works_version・書き出しの manifest が無い）、
第三の目の「方針の岐路」の争点（写し a1202d0 の graph に欄が無い）。費用は書き出し（Task 19）の run_facts の代わりに
実行基盤の出来事（節の data.spend.costUsd）と包みの起動の記録から組む（欄の形は実物で確かめた。COST_FIELD_VERIFIED が偽なら「欄の形は未確認」を添える）。
報告は run の中で走るので run の和は読まず、合計は節の和を「途中」として出す。
"""
import datetime
import json
import os
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import carry  # noqa: E402  （L1。次の run への持ち越しの形の住処: ファイルの名・欄の名・約束の Schema）
import promptsection  # noqa: E402

OUTCOMES = ("fixed", "fixed_needs_check", "no_fix_needed", "round_limit", "stopped_by_request", "stopped_by_human", "stopped_by_line",
            "needs_human", "record_invalid", "interrupted")


EYES = ("R1", "R2", "R3", "R4")
CHECKS_LEFT = "人が確かめる物"   # fixed_needs_check の残り（冒頭 3 行の件数と冒頭 1 の見出し）
EYES_WHERE = "独立の目"
REPORT_FILE = "report.md"
FOR_READERS = "人が読む報告の本文の見出し。役の指示書には貼らない"
PRIOR_HEADING = promptsection.Section("## 次の run に引き継ぐ落ちた理由", human=FOR_READERS)
OUTSIDE_HEADING = promptsection.Section("## 判定が目的の外とした所見", human=FOR_READERS)   # 1 件ずつの行（outpurpose.report_lines）。冒頭 1 は件数の行だけ（outpurpose.count_line）
WORLD_HEADING = promptsection.Section("## 世界の解", human=FOR_READERS)   # 依頼の行ごとの定石と依頼の解き方との比べ（worldmark.report_lines。控えの無い run は節を出さない）
TDD_HEADING = promptsection.Section("## TDD の輪の単位ごとの結末", human=FOR_READERS)   # keep-essence の 11（修正のブロックの出口 tdd を、修正の段ごとに単位の行で）
TDD_STAGES = ("修正の段", "案を直した後の修正の段")   # build の tdd の並び（ラインの report の with の fix_tdd・refit_tdd の順）
FREEZE_OFF_HEAD = "テストの凍結"   # 冒頭 2 の行の頭（TDD の輪を回していない修正の段は、凍結が効いていないと言う。freeze_lines）
R2_REDESIGN = "R2 が redesign-needed"      # 検証器と独立の目が R2 の作り直しの行に付ける頭（findings から外し prior_failures にだけ載せる）
FINAL_GATE_STOPS = ("stop", "reject")           # 最後の関所の答えのうち止める語（書き手 line_edge の GATE_STOP）
REQUEST_BY = "request:"                        # 止め札で止めた盤面の state.stop.by の頭
HUMAN_BY = "human:"
DECISIONS_HEADING = promptsection.Section("## 1. 人が決めること", human=FOR_READERS)
ENTRY_HEADING = promptsection.Section("## 2. 入口・段・決めた人", human=FOR_READERS)
STOP_HEADING = promptsection.Section("## 3. 止めたか", human=FOR_READERS)
READS_HEADING = promptsection.Section("## 4. 読んだ証拠と包み", human=FOR_READERS)
WHERE_HEADING = promptsection.Section("## 5. 見る所", human=FOR_READERS)
HEADINGS = (DECISIONS_HEADING, ENTRY_HEADING, STOP_HEADING, READS_HEADING, WHERE_HEADING)
TITLE_HEADING = promptsection.Section("# 報告（run {run}）", human=FOR_READERS)
INTERRUPTED_HEAD = "run が途中で終わった"
RETRIED_HEAD = "前の試みで落ち、続きで済んだ節"


# ---------------------------------------------------------------- 小道具
def _read_json(path: pathlib.Path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: pathlib.Path, doc) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _write_text(path: pathlib.Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _one_line(text) -> str:
    return " ".join(str(text).split())


# ---------------------------------------------------------------- 次の run に渡す依頼
def _r2_redesign(row) -> bool:
    return str(row.get("text") or "").startswith(R2_REDESIGN)


def prior_lines(rows: list) -> list:
    """報告の節 PRIOR_HEADING の行（次の run に運んだ行の件数と 1 件 1 行）"""
    return [f"{len(rows)} 件（次の run の依頼の下書き {carry.NEXT_REQUEST_FILE} の prior_failures に載せた。判定役と修正案の役の材料に"
            "貼る。受け付けの拒否の行は直す穴ではない注意で、R2 の作り直しの行は次の周の先頭で直す穴）"] + [f"{r['where']}: {r['text']}" for r in rows]


# ---------------------------------------------------------------- 冒頭 3 行と 1〜5
# 結末の語（decide_outcome の返り）→ 平易な言い方（冒頭 3 行の 1 行目。語は括弧に残す）
OUTCOME_WORDS = {"fixed": "直して、最後のテストまで通った",
                 "fixed_needs_check": "直して、最後のテストまで通った。run の中で測れなかった確かめが残る（人の確かめ待ち）",
                 "no_fix_needed": "直す物が無かった",
                 "round_limit": "決めた周の数のうちに直しきれずに止まった", "stopped_by_request": "止め札で止めた",
                 "stopped_by_human": "人が関所で止めた", "stopped_by_line": "ラインが途中で止めた",
                 "needs_human": "人の判断を待ったまま止まった", "record_invalid": "記録が検証器を通らない（結果を名乗れない）",
                 "interrupted": "run が途中で終わった"}


def _time(s):
    try:
        t = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None


# ---------------------------------------------------------------- 組む


def _red_evidence(u: dict) -> str:
    """単位の行に足す、赤の証拠の句（人が報告で赤の理由の正しさを見る。最後の関所の文には載らない）: 名指しごとの引用と理由（役の引用。引用が結末の
    failure の文に在ることは輪が照らし済みで、理由の正しさは機械が見ない）・test の段が足した仮の実装のファイル（stub_files）・
    引用を照らせなかった名指し（quote_unchecked。failure の文もログも空）"""
    out = []
    for test, q in (u.get("red_quotes") or {}).items():
        if isinstance(q, dict):
            out.append(f"赤の引用 {test}: 「{_one_line(q.get('quote', ''))[:200]}」（理由: {_one_line(q.get('why', ''))[:200]}）")
    if u.get("stub_files"):
        out.append(f"仮の実装 {', '.join(u['stub_files'])}")
    if u.get("quote_unchecked"):
        out.append(f"引用を照らせなかった名指し {', '.join(u['quote_unchecked'])}")
    return "。" + "。".join(out) if out else ""


def _tdd_unit(u: dict) -> str:
    """TDD の輪の 1 単位の結末の行（修正のブロックの出口 tdd の units の行。route は tdd・direct・parked）"""
    key, why = u.get("unit_key") or "（key 無し）", _one_line(u.get("why") or "")
    if u.get("route") == "tdd":
        row = (f"{key}: 赤 {u.get('red') or '—'}・緑 {u.get('green') or '—'}・整え {u.get('refactor') or '—'}"
               f"（名指しのテスト {', '.join(u.get('tests') or []) or '無し'}）")
        return row + _red_evidence(u)
    if u.get("route") == "parked":
        return f"{key}: 食い違いで止めた（{why or '理由なし'}）"
    if u.get("gave_up"):
        return f"{key}: TDD を諦めて今どおりの直しへ回した（{u['gave_up']} の段で: {why or '理由なし'}）"
    return f"{key}: 初めから今どおりの直し（{why or '理由なし'}）"


def _reused_line(reused) -> str:
    """出口 tdd の reused {suite, test_cmd}（輪の頭で控えから使い回した結果の出どころの句）を『元の結末 …・test_cmd …』に"""
    labels = (("suite", "元の結末"), ("test_cmd", "test_cmd"))
    return "・".join(f"{label} {_one_line(reused[k])}" for k, label in labels if isinstance(reused, dict) and reused.get(k))


def tdd_lines(stages) -> list:
    """修正の段ごとの TDD の輪の単位の結末の行（keep-essence の 11）。stages は [(段の名, 修正のブロックの出口 tdd か None)]。
    None（飛ばされた段・渡されていない）は出さない。輪を回していない段（ran が偽）は理由つきの 1 行（黙らない）。回した段は
    件数の 1 行と単位ごとの行（インデントつき）"""
    rows = []
    for name, tdd in stages:
        if not isinstance(tdd, dict):
            continue
        if not tdd.get("ran"):
            rows.append(f"{name}: TDD の輪を回していない（{_one_line(tdd.get('reason') or '理由なし')}）")
            continue
        units = [u for u in tdd.get("units") or [] if isinstance(u, dict)]
        green = sum(u.get("route") == "tdd" and u.get("green") == "ok" for u in units)
        gave = sum(u.get("route") == "direct" and bool(u.get("gave_up")) for u in units)
        direct = sum(u.get("route") == "direct" and not u.get("gave_up") for u in units)
        parked = sum(u.get("route") == "parked" for u in units)
        rows.append(f"{name}: {len(units)} 単位（赤→緑 {green}・TDD を諦めた {gave}・初めから今どおりの直し {direct}・止めた {parked}。"
                    f"実行器 {tdd.get('suite') or '—'}）" + (f"。輪を途中で抜けた: {_one_line(tdd['reason'])}" if tdd.get("reason") else "")
                    + (f"。控えから使った結果: {_reused_line(tdd['reused'])}" if tdd.get("reused") else ""))
        rows += [f"  - {_tdd_unit(u)}" for u in units]
    return rows


def freeze_lines(stages) -> list:
    """冒頭 2 の行（keep-essence の 3）: TDD の輪を回していない修正の段（修正のブロックの出口 tdd の ran が偽）ごとに、テストの
    凍結が効いていないと理由つきで 1 行（黙らない）。stages は tdd_lines と同じ。走っていない段（None）は出さない"""
    return [f"{FREEZE_OFF_HEAD}: {name}で効いていない（TDD の輪を回していないので既存のテストを凍らせていない——"
            f"{_one_line(tdd.get('reason') or '理由なし')}）"
            for name, tdd in stages if isinstance(tdd, dict) and not tdd.get("ran")]


MODEL_HEADING = promptsection.Section("## 模型", human=FOR_READERS)
COST_HEADING = promptsection.Section("## 費用", human=FOR_READERS)


