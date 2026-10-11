"""報告のブロック（blk-report）の芯。本線の R13（report＋finalize）を、works の盤面（DiskBoard）の上で役として回す。
本線の頭だけの書き手（report.human_items）と初見検査の節（report.cold_check）はこのラインの表で absent（2026-10-09 の片付け:
後の書き手が頭を書き直し、初見検査は 56 本とも redesign-needed で、AI の起動 2 回を使うだけだった）。頭は report の書き手が
本文と一度に書き、書き手の輪の中の初見の読み手（道具なし・新しい会話）が頭だけを読んで確かめる。どの節をいつ回すか・
検証器の関所（pre: finalize）・記録への書き込みは盤面と写しの規則が決め、works は描く・起こした印・受け付け・出口だけを持つ。

- route:   盤面を settle し、書き手の節が ready か。ready でなければ理由（止めた盤面・検証器の関所・まだ周の途中・済んだ）
- prep:    本線の指示書を盤面の今の値で描く（engine の emit_instance と同じ ctx に検証器の結果 validation を足す）
           → 拒否の後なら前の拒否の文を頭に → 作業ツリーの写し → 起こした印（mark_launched）。
           書き手には、数の出どころ（盤面から機械が組んだ事実。線 A の機械の報告が在ればそれ）のファイルを渡す
- write_cold_prep: 書き手の返答の頭（平易な冒頭と人が決めること）と、その後ろに機械が付けた語の定義の節だけを、
           初見の読み手の指示書（写しの report.cold_check の指示書）に入れて描く（書き手の輪の中）
- accept:  返答を読み、書き手の run ごとの語（terms）は型を見て作業ファイルに控えて外し（盤面には {text} だけ。語の定義の節は
           pack の一覧とこの控えから描く）、本文は表のセルの書式を機械で見て（持ち主の決まり。works だけの検査）、頭を読んだ
           初見の読み手の返答を COLD_RESULT_NAME に控え、pass でなければ書き手に返し（上限の回は受け取って印を残す）、
           entry.take で盤面へ。拒否は GIVE_UP_AFTER 回目で諦めの印（done）
- collect: 出口。report を受けていれば 来歴の 1 行＋（初見の確かめを通らずに受け取った時はその 1 行）＋書き手の本文＋
           語の定義の節（本文と機械の事実に現れる語）＋機械の事実（書き換えずに最後に付ける）を盤面の REPORT_NAME に。
           受けていなければ、なぜ無いか・検証器の出力の末尾・機械の事実を付けた報告を書いて ok: false（黙らない）

指示書は本線 a1202d0 の写し（blk-report/prompts/。台帳 COPIED_FROM の手直しのほかはバイト単位で同じ）。描き方は engine と同じ
（rolekit.render_body。reads の柵・cap なし）。
"""
import json
import os
import pathlib
import re
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))   # 写しの engine（board と同じ足し方）

from engine.schema import validate_schema  # noqa: E402
import promptsection  # noqa: E402
import report  # noqa: E402

# 役の名（YAML の節 id・包みの印の名）→ 写しの graph の節
WRITE = "report-write"
# 写しの graph の報告の節の全部（このラインでは頭と初見検査が absent）。拒否の控えの数え（count_rejects）はこの全部を数える
# （頭と初見検査が回っていた前の版の run の控えも、run をまたぐ集計 dev/report_rejects.py が数えられるように）
REPORT_NODES = ("report.human_items", "report.cold_check", "report")
# 書き手の出した物を確かめる初見の読み手（盤面の節ではない。書き手の輪の中で、書き手の返答の頭だけを読む）
WRITE_COLD = "report-write-cold"
DECISIONS_HEAD = "人が決めること"
NOT_PASSED = "初見の確かめを通っていない"
# 本文を返す節（graph の text: true）の返答の型。盤面は本文の節の返答を {text} だけで受けるので、run ごとの語 terms は
# 受け付けが外して TERMS_NAME に控える
TERM_SCHEMA = {"type": "object", "required": ["term", "definition"], "additionalProperties": False,
               "properties": {"term": {"type": "string", "minLength": 1}, "definition": {"type": "string", "minLength": 1}}}
TEXT_SCHEMA = {"type": "object", "required": ["text"], "additionalProperties": False,
               "properties": {"text": {"type": "string", "minLength": 1},
                              "terms": {"type": "array", "items": TERM_SCHEMA}}}
# 輪（loop_group）の max_iterations と同じ数。受け付けがこの数だけ拒んだら諦めの印（done）を出し、輪を失敗で抜けさせずに
# 後ろへ渡す（裁定 R50）。tests/test_blk_report.py が YAML の max_iterations と同じかを見る
GIVE_UP_AFTER = 3
REJECT_HEADING = promptsection.Section("## 前の回の受け付けが拒んだ理由", source="fn:report_roles.prep")
MACHINE_HEADING = promptsection.Section("## 機械が盤面から組んだ事実（AI は書き換えていない）", human=report.FOR_READERS)
CELL_LIMIT = 50   # 表のセルの字数の上限（`コード` の部分を除く）。持ち主の決まり「セルには数語だけ」
# 拒否の種類: cold＝書き手の頭を読んだ初見の読み手が pass でない（redesign-needed・読めない返答）／format＝表のセル／
# answer＝返答の型・take の拒否
REJECT_KINDS = ("cold", "format", "answer")
# 読むときだけの種類: kind の無い行（kind が入る前の run）・知らない kind の行を捨てずに数える先。_reject は書かない
UNKNOWN_KIND = "unknown"
SNAPSHOT_PREFIX = "report-snapshot-"    # 書き手を起こす前の作業ツリーの写し（読むだけの役の比べ）
FAILED_TITLE = promptsection.Section("# 報告（AI の報告を最後まで作れなかった）", human=report.FOR_READERS)
GLOSSARY_HEADING = promptsection.Section("## 語の定義（機械が付けた。本文の外）", human=report.FOR_READERS)
CELL_REASON = ("表のセルに説明の文を入れない（書式の決まり: 表は状態・件数・日付など数語の値の一覧だけ。端末の表は列ごとに"
               f"幅を割るので、長いセルは細切れに折り返されて読めない）。「。」を含むか {CELL_LIMIT} 字を超えるセルが在る——"
               "表をやめて箇条書きか散文にするか、セルを数語に縮めて説明は表の外に書け:\n")


def _write_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- 数の出どころ
def _count(items, key):
    got = {}
    for it in items:
        k = it.get(key) if isinstance(it, dict) else None
        got[k or "未指定"] = got.get(k or "未指定", 0) + 1
    return "・".join(f"{k} {v}" for k, v in got.items()) or "なし"


# ---------------------------------------------------------------- 描く・印


def _terms_problems(reply) -> list:
    """書き手の返答の terms の欄の型の破れ（欄が無ければ空）"""
    if "terms" not in reply:
        return []
    return validate_schema(reply["terms"], TEXT_SCHEMA["properties"]["terms"], "$.terms")


def _snap_name(role) -> str:
    return f"{SNAPSHOT_PREFIX}{role}.json"


def head_of(text) -> str:
    """報告の頭: 最初の見出し（## ）より前の冒頭と、見出しに『人が決めること』を持つ節。見出しが無ければ全文"""
    head, keep, found = [], True, False
    for line in str(text or "").splitlines():
        if line.startswith("## "):
            found = True
            keep = DECISIONS_HEAD in line
        if keep:
            head.append(line)
    return "\n".join(head).strip() if found else str(text or "").strip()


# ---------------------------------------------------------------- 受け付け


def format_problems(text) -> list:
    """表のセルの書式の破れ（「。」を含むか CELL_LIMIT 字を超えるセル。`コード` の部分とコードの囲みの中は数えない）。
    1 行につき 1 つの文"""
    out, fence = [], False
    for i, line in enumerate(str(text or "").splitlines(), 1):
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = not fence
            continue
        if fence or not s.startswith("|"):
            continue
        body = re.sub(r"`[^`]*`", "", s).strip().strip("|")
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", body)]
        if all(re.fullmatch(r":?-{3,}:?", c) or not c for c in cells):
            continue
        bad = [c for c in cells if "。" in c or len(c) > CELL_LIMIT]
        if bad:
            out.append(f"{i} 行目のセル「{bad[0][:30]}{'…' if len(bad[0]) > 30 else ''}」（{len(bad[0])} 字）")
    return out


# ---------------------------------------------------------------- 出口


def count_rejects(rows) -> dict:
    """拒否の行の回数 {節: {種類: 回数}}（kind を数える。文は読まない）。kind の無い行・知らない kind の行は UNKNOWN_KIND に
    数え、REPORT_NODES の節でない行は数えない"""
    got = {nid: dict.fromkeys((*REJECT_KINDS, UNKNOWN_KIND), 0) for nid in REPORT_NODES}
    for r in rows:
        if r.get("node") in got:
            kind = r.get("kind") if r.get("kind") in REJECT_KINDS else UNKNOWN_KIND
            got[r["node"]][kind] += 1
    return got


