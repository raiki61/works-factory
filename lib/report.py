"""報告の定型（P1 計画 Task 27・〔線A計〕T15。仕様 6 節・裁定 TA12・TA15）。AI は書かない。文は機械の定型だけ。

元は works/.shared/core/report.py。盤面（b）を読んだ関数は、ブロックの返りを引数で受ける形で lib/outcome（結末の語の決め方）と
lib/runreport（機械の報告・次の依頼・前の失敗・費用）に移した。ここに残るのは両方と報告のブロック、差分の審査の受け付け（lib/refix）が
読む語と小さな組み立て:
- OUTCOMES・OUTCOME_WORDS: 結末の語（報告のブロックの返す節の enum と同じ 10 語）と、冒頭 3 行の 1 行目の平易な言い方
- OUTCOME_KINDS: 結末の語 → 周の鎖（lib/chain.py）が見る種
- 報告の見出し（TITLE_HEADING・HEADINGS の冒頭 1〜5・PRIOR_HEADING・OUTSIDE_HEADING・WORLD_HEADING・TDD_HEADING・
  MODEL_HEADING・COST_HEADING・STRUCTURE_HEADING。人が読む本文の物で役の指示書には貼らない FOR_READERS）と行の where・頭の語
- prior_lines(rows, next_file): 次の run に運んだ落ちた理由の節の行
- tdd_lines(stages)・freeze_lines(stages): 修正の段ごとの TDD の輪の単位の結末の行（keep-essence の 11）と、輪を回していない段で
  テストの凍結が効いていないと言う冒頭 2 の行（keep-essence の 3）
- INNER_WORDS・INNER_WORD・INNER_WORDS_HEAD: 直しが対象に書く文に混じってはいけない works の内側の語の表と見出し
- inner_word_hits(diff_text, known)・target_uses(repo, rev, word)・INNER_FACE_KIND: 差分の足した行への表の照らし（読み手は
  lib/runreport の報告の一覧と lib/refix の差分の審査の受け付け）と、対象が直す前の版で既に使う語か、機械の穴の kind の語

書き手のモジュール（ライン・ブロック）を import せずに名前で読む（層 L3 は上の層を import しない。裁定 R59）。
"""
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import answer  # noqa: E402
import carry  # noqa: E402  （L1。次の run への持ち越しの形の住処: ファイルの名・欄の名・約束の Schema）
import chain  # noqa: E402
import changemap  # noqa: E402
import oneline  # noqa: E402
import promptsection  # noqa: E402
import stopby  # noqa: E402

OUTCOMES = ("fixed", "fixed_needs_check", "no_fix_needed", "round_limit", "stopped_by_request", "stopped_by_human", "stopped_by_line",
            "needs_human", "record_invalid", "interrupted")
# 結末の語 → 周の鎖が見る種（chain.KIND_*）。鎖は結末の語を字で持たず、ここを引く
OUTCOME_KINDS = {"fixed": chain.KIND_CLOSED, "no_fix_needed": chain.KIND_CLOSED, "round_limit": chain.KIND_OPEN,
                 "stopped_by_request": chain.KIND_HALTED, "stopped_by_human": chain.KIND_HALTED, "stopped_by_line": chain.KIND_HALTED,
                 "record_invalid": chain.KIND_HALTED, "needs_human": chain.KIND_HUMAN, "fixed_needs_check": chain.KIND_HUMAN,
                 "interrupted": chain.KIND_WAIT}


EYES = ("R1", "R2", "R3", "R4")
CHECKS_LEFT = "人が確かめる物"   # fixed_needs_check の残り（冒頭 3 行の件数と冒頭 1 の見出し）
EYES_WHERE = "独立の目"
ABSORBED_WHERE = "受け止めた落ち"
REPORT_FILE = "report.md"
FOR_READERS = "人が読む報告の本文の見出し。役の指示書には貼らない"
PRIOR_HEADING = promptsection.Section("## 次の run に引き継ぐ落ちた理由", human=FOR_READERS)
OUTSIDE_HEADING = promptsection.Section("## 判定が目的の外とした所見", human=FOR_READERS)   # 1 件ずつの行（outpurpose.report_lines）。冒頭 1 は件数の行だけ（outpurpose.count_line）
WORLD_HEADING = promptsection.Section("## 世界の解", human=FOR_READERS)   # 依頼の行ごとの定石と依頼の解き方との比べ（runreport._world_lines。控えの無い run は節を出さない）
TDD_HEADING = promptsection.Section("## TDD のループの単位ごとの結末", human=FOR_READERS)   # keep-essence の 11（修正のブロックの出口 tdd を、修正の段ごとに単位の行で）
TDD_STAGES = ("修正の段", "案を直した後の修正の段")   # build の tdd の並び（ラインの report の with の fix_tdd・refit_tdd の順）
FREEZE_OFF_HEAD = "テストの凍結"   # 冒頭 2 の行の頭（TDD の輪を回していない修正の段は、凍結が効いていないと言う。freeze_lines）
R2_REDESIGN = "R2 が redesign-needed"      # 検証器と独立の目が R2 の作り直しの行に付ける頭（findings から外し prior_failures にだけ載せる）
FINAL_GATE_STOPS = answer.STOP_WORDS            # 最後の関所の答えのうち止める語（書き手 line_edge の GATE_STOP）
REQUEST_BY = "request:"                        # 止め札で止めた盤面の state.stop.by の頭
HUMAN_BY = stopby.HUMAN
DECISIONS_HEADING = promptsection.Section("## 1. 人が決めること", human=FOR_READERS)
ENTRY_HEADING = promptsection.Section("## 2. 入口・段・決めた人", human=FOR_READERS)
STOP_HEADING = promptsection.Section("## 3. 止めたか", human=FOR_READERS)
READS_HEADING = promptsection.Section("## 4. 読んだ証拠と包み", human=FOR_READERS)
WHERE_HEADING = promptsection.Section("## 5. 見る所", human=FOR_READERS)
HEADINGS = (DECISIONS_HEADING, ENTRY_HEADING, STOP_HEADING, READS_HEADING, WHERE_HEADING)
TITLE_HEADING = promptsection.Section("# 報告（run {run}）", human=FOR_READERS)
INTERRUPTED_HEAD = "run が途中で終わった"
RETRIED_HEAD = "前の試みで落ち、続きで済んだノード"
ABSORBED_HEAD = "落ちたが、メイングラフが宣言のとおり受け止めたノード"
REJUDGE_WHERE = "判定（再審の結果）"           # 次の run の依頼の再審の結果の行の where
# 再審の judgment の隣のファイル（書き手は判定のブロックの lib/judge_accept.rejudge_take・rejudge_collect。再審の判定の出力の欄
# rejudge_diff・rejudge_exit が指し、線の judged と報告はその欄から読むだけで、再審の前後を自分で数えない）
REJUDGE_DIFF = "rejudge-diff.json"             # 往復ごとの単位の前後の差 [{round, pass, verdict, changed, unnamed_changed, lowered}]
REJUDGE_EXIT = "rejudge-exit.json"             # 再審の出口 {ok, reason, passes, verdicts, unsettled, objection, new_open_units, lowered, unnamed_changed, …}
# 直しが対象に書く文に混じってはいけない works の内側の語と run の中の事情の言い方（修正役の共通の決まり
# workflows/fix/commands/fix-rules/common.md の「対象に書く文」。利用者の run 8cb2ee00 の差分が Terraform のコメントに「この単位」
# 「作業ツリー」を書いた）。報告では拒まず並べ、差分の審査では手直しの義務の穴になる
INNER_WORDS = ("この単位", "単位の key", "作業ツリー", "共有ボード", "盤面", "この周", "この run", "判定役", "修正役", "独立の目",
               "承認ノード", "関所")
INNER_WORD = re.compile("|".join(re.escape(w) + ("(?!辺)" if w == "この周" else "") for w in INNER_WORDS))   # 「この周辺」は除く
INNER_WORDS_HEAD = "直しが対象に足した行に works の内側の語（対象の読み手に通じない。当てる前に言い換えるかを決める）"
INNER_FACE_KIND = "inner_word"


def target_uses(repo, rev: str, word: str) -> bool:
    """対象が直す前の版 rev で既にその語を使うか（版か置き場が無い・git が落ちれば偽＝並べる側）"""
    if not (repo and rev):
        return False
    try:
        got = subprocess.run(["git", "-C", str(repo), "grep", "-q", "-F", "-e", word, str(rev), "--"], capture_output=True)
    except OSError:
        return False
    return got.returncode == 0


def inner_word_hits(diff_text: str, known) -> list:
    """直しの差分 diff_text が足した行のうち内側の語（INNER_WORD）を含む行 [{path, line（新しい側の行番号）, words, text}]。対象が
    直す前の版で既に使う語 known(語) は数えない（語ごとに 1 度だけ引く）。当たりが無ければ空"""
    seen, hits = {}, []
    for path, lines in changemap.split_diff(diff_text)[0].items():
        for n, ln in changemap.new_side(lines):
            words = list(dict.fromkeys(INNER_WORD.findall(ln))) if ln.startswith("+") else []
            words = [w for w in words if not seen.setdefault(w, known(w))]
            if words:
                hits.append({"path": path, "line": n, "words": words, "text": oneline.one_line(ln[1:].strip())})
    return hits


# ---------------------------------------------------------------- 小道具
def _write_text(path: pathlib.Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _first_error(x: dict) -> str:
    """落ちた節の行 {node, error} の誤りの文の 1 行目（無ければその旨）"""
    return (str(x.get("error") or "").strip().splitlines() or ["（誤りの文が無い）"])[0]


def rejudge_exit(path) -> tuple:
    """(再審の出口 rejudge-exit.json の中身, 読めなかった訳)。path は出口のファイル（再審の判定の出力の欄 rejudge_exit。None は再審が
    出口を書かなかった）。無い・読めない・形が違えば (None, 訳)"""
    if path is None:
        return None, f"再審の出口 {REJUDGE_EXIT} が無い（再審の判定の出力の rejudge_exit が null）"
    path = pathlib.Path(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"再審の出口 {path.name} が無い（{path}）"
    except (OSError, ValueError) as e:
        return None, f"再審の出口 {path} が読めない（{oneline.one_line(e)}）"
    if not isinstance(doc, dict):
        return None, f"再審の出口 {path} が JSON のオブジェクトでない"
    return doc, ""


# ---------------------------------------------------------------- 次の run に渡す依頼
def _r2_redesign(row) -> bool:
    return str(row.get("text") or "").startswith(R2_REDESIGN)


def prior_lines(rows: list, next_file: str) -> list:
    """報告の節 PRIOR_HEADING の行（次の run に運んだ行の件数と 1 件 1 行）。名指すのは書いたファイルだけ: 行が在れば
    carry.PRIOR_FAILURES_FILE、次の依頼の下書きも書いた時（next_file が空でない）はそれも"""
    if not rows:
        return ["0 件"]
    also = f"。次の run の依頼の下書き {next_file} の prior_failures にも載せた" if next_file else ""
    return [f"{len(rows)} 件（{carry.PRIOR_FAILURES_FILE} に書いた{also}。判定役と修正案の役の材料に貼る。受け付けの拒否の行は"
            "直す穴ではない注意で、R2 の作り直しの行は次の周の先頭で直す穴）"] + [f"{r['where']}: {r['text']}" for r in rows]


# ---------------------------------------------------------------- 冒頭 3 行と 1〜5
# 結末の語（decide_outcome の返り）→ 平易な言い方（冒頭 3 行の 1 行目。語は括弧に残す）
OUTCOME_WORDS = {"fixed": "直して、最後のテストまで通った",
                 "fixed_needs_check": "直して、最後のテストまで通った。run の中で測れなかった確かめが残る（人の確かめ待ち）",
                 "no_fix_needed": "直す物が無かった",
                 "round_limit": "決めた周の数のうちに直しきれずに止まった", "stopped_by_request": "止め札で止めた",
                 "stopped_by_human": "人が承認ノードで止めた", "stopped_by_line": "ラインが途中で止めた",
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
            out.append(f"赤の引用 {test}: 「{oneline.one_line(q.get('quote', ''))[:200]}」（理由: {oneline.one_line(q.get('why', ''))[:200]}）")
    if u.get("stub_files"):
        out.append(f"仮の実装 {', '.join(u['stub_files'])}")
    if u.get("quote_unchecked"):
        out.append(f"引用を照らせなかった名指し {', '.join(u['quote_unchecked'])}")
    return "。" + "。".join(out) if out else ""


def _tdd_unit(u: dict) -> str:
    """TDD の輪の 1 単位の結末の行（修正のブロックの出口 tdd の units の行。route は tdd・direct・parked）"""
    key, why = u.get("unit_key") or "（key 無し）", oneline.one_line(u.get("why") or "")
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
    return "・".join(f"{label} {oneline.one_line(reused[k])}" for k, label in labels if isinstance(reused, dict) and reused.get(k))


def tdd_stage_groups(n: int, groups) -> list:
    """n 番目（0 から）の修正の段の組ごとの物 groups（tdd-unit の本文）を、tdd_lines に渡す [(段の名（組 id）, 組の物)] に。段の名は
    TDD_STAGES の順で、並びを超えた段は番号を足す（報告と独立の目の比較役が同じ名で段を指す）"""
    name = TDD_STAGES[min(n, len(TDD_STAGES) - 1)] + (f" {n}" if n >= len(TDD_STAGES) else "")
    return [(f"{name}（組 {g.get('group_id')}）", g) for g in groups if isinstance(g, dict)]


def tdd_lines(stages) -> list:
    """修正の段ごとの TDD の輪の単位の結末の行（keep-essence の 11）。stages は [(段の名, 修正のブロックの出口 tdd か None)]。
    None（飛ばされた段・渡されていない）は出さない。輪を回していない段（ran が偽）は理由つきの 1 行（黙らない）。回した段は
    件数の 1 行と単位ごとの行（インデントつき）"""
    rows = []
    for name, tdd in stages:
        if not isinstance(tdd, dict):
            continue
        if not tdd.get("ran"):
            rows.append(f"{name}: TDD のループを回していない（{oneline.one_line(tdd.get('reason') or '理由なし')}）")
            continue
        units = [u for u in tdd.get("units") or [] if isinstance(u, dict)]
        green = sum(u.get("route") == "tdd" and u.get("green") == "ok" for u in units)
        gave = sum(u.get("route") == "direct" and bool(u.get("gave_up")) for u in units)
        direct = sum(u.get("route") == "direct" and not u.get("gave_up") for u in units)
        parked = sum(u.get("route") == "parked" for u in units)
        rows.append(f"{name}: {len(units)} 単位（赤→緑 {green}・TDD を諦めた {gave}・初めから今どおりの直し {direct}・止めた {parked}。"
                    f"実行器 {tdd.get('suite') or '—'}）" + (f"。ループを途中で抜けた: {oneline.one_line(tdd['reason'])}" if tdd.get("reason") else "")
                    + (f"。控えから使った結果: {_reused_line(tdd['reused'])}" if tdd.get("reused") else ""))
        rows += [f"  - {_tdd_unit(u)}" for u in units]
    return rows


def freeze_lines(stages) -> list:
    """冒頭 2 の行（keep-essence の 3）: TDD の輪を回していない修正の段（修正のブロックの出口 tdd の ran が偽）ごとに、テストの
    凍結が効いていないと理由つきで 1 行（黙らない）。stages は tdd_lines と同じ。走っていない段（None）は出さない"""
    return [f"{FREEZE_OFF_HEAD}: {name}で効いていない（TDD のループを回していないので既存のテストを凍らせていない——"
            f"{oneline.one_line(tdd.get('reason') or '理由なし')}）"
            for name, tdd in stages if isinstance(tdd, dict) and not tdd.get("ran")]


MODEL_HEADING = promptsection.Section("## 模型", human=FOR_READERS)
COST_HEADING = promptsection.Section("## 費用", human=FOR_READERS)
STRUCTURE_HEADING = promptsection.Section("## 構造の目", human=FOR_READERS)
UNSEEN_LENS_HEADING = promptsection.Section("## 未確認のレンズ", human=FOR_READERS)   # 局所レビューの見ていないレンズ（diverted.report_lines）


