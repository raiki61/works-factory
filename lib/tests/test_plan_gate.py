"""修正前の関所（p2.human_gate）が、決め手の在る項目を人に聞かずに通すか。写しの RL を読み、線 A の核の差し替え
（entry.CORE_OVERRIDES）を盤面と同じ口（DiskBoard._apply_overrides）で当て、機械の節 human_gate を偽の盤面で直に呼ぶ（FAST。
盤面・git・子のプロセスなし）。決め手の出どころ decided_by が在り undecided_because が空で柵の印 fences が無い行は通して
state.works.gate_passes に出どころつきで残し、柵の印か undecided_because の在る行・欄の無い行は今までどおり聞く"""
import pathlib
import re
import sys
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import seal  # noqa: E402

NARROW = {"what": "空の列の mean", "why": "空の列の平均は 0 割りの例外のまま"}
# 決め手の出どころは現物に在る物（URL・パス:行・依頼の引用「…」・設計の決定の記録のパス）。世界の解は world か URL の決め手
URL = "https://docs.python.org/3/library/statistics.html#statistics.mean"
DECIDED = {"decided_by": f"{URL} の定義（空の列は StatisticsError）", "undecided_because": "", "fences": [],
           "world": "Python 公式の statistics.mean は空の列で例外を投げる"}
FACE = {"key": "clamp の上限の意味が変わる", "unit_keys": ["u"], "kind": "regression", "where": "stats.py clamp",
        "why": "上限を超えた値に lo を返す今の振る舞いに頼る呼び手が在れば結果が変わる", "severity": "block"}


ROUTE_UP = {"unit_id": "u", "verdict": "汚れる", "faces": [2], "evidence": ["/units/0/measure"], "reason": "責務が割れる",
            "chosen": "判定の式を report に 1 つ置く", "chosen_reason": "読み手が 1 つになる",
            "rejected": [{"option": "境の節に写す", "cost": "知る場所が 2 つになる"}],
            "route": "人に上げる", "route_reason": "人の前の決定が 2 つの置き場を別々に推している",
            "undecided_because": "人の前の決定が 2 つの置き場を別々に推している"}


WORLD_ROW = {"finding": 1, "where": "stats.py", "class_id": "w-mean", "problem": "空の数の並びの平均をどう扱うか",
             "activity": "統計の関数の直し", "practice": "空の並びの平均は定義されないので例外にする（見本の印 WG-4410）",
             "sources": [{"id": "x1", "url": "https://example.org/stats/mean", "excerpt": "The mean of an empty sequence is undefined."}],
             "applies": "空の並びの平均の扱い", "not_applies": "",
             "versus": {"proposed": "空の並びは 0 を返す", "verdict": "differs",
                        "challenge": "依頼は 0 を返す、定石は例外にする。呼び手が 0 を要る訳が無い限り定石を選ぶ"},
             "basis": "web", "cached": False}
REQUEST_LINE = "空の列の mean は 0 を返してほしい"


FORK_UNIT = "stats.py mean: 空の列の扱いが決まらない"
OTHER_UNIT = "stats.py clamp: 上限を超えた値に lo を返す"
FORK = {"key": "q-empty-mean", "kind": "fork", "status": "held", "origin": FORK_UNIT, "options": ["例外", "0 を返す"],
        "reason": "空の列の意味が 2 つに割れる。推し: 例外——呼び手が既に例外を捕まえている"}
UNITS = [{"key": FORK_UNIT, "label": "block"}, {"key": OTHER_UNIT, "label": "block"}]


ESCALATE = {**FORK, "key": "q-stuck-mean", "kind": "stuck", "status": "escalate"}
SKIP_MARK = "答えが無いと直さない単位"


RECORD_NAME = re.compile(r"(?<![A-Za-z0-9_.])(?:(?:p\d|spec|report)\.[a-z0-9_]+|process\.[a-z_.]+[a-z]|fix_test_scope|fix_code_as|ask_human)")
EYE_OR_STATE = re.compile(r"(?<![A-Za-z0-9_-])(?:R[1-4]|" + "|".join(map(re.escape, seal.STATUSES))
                          + r"|premise-invalid|carried_over|not_applicable|not_run)(?![A-Za-z0-9_-])")


def _spans(line: str) -> list:
    """行の外側の括弧（（）と ()）の (始め, 終わり)"""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(line):
        if ch in "（(":
            if depth == 0:
                start = i
            depth += 1
        elif ch in "）)" and depth:
            depth -= 1
            if depth == 0:
                out.append((start, i))
    return out


def internal_subjects(text: str) -> list:
    """人が読む文の行のうち、盤面の内部の名が主語になっている行。記録の名（節の名・記録の欄・裁定の語）は括弧の中の『記録の名』の
    後ろにだけ、目の名と状態の語は括弧の中にだけ置いてよい（平易な名が主語で、内部の名は括弧に回す）"""
    bad = []
    for line in text.splitlines():
        spans = _spans(line)
        inside = lambda m: next(((s, e) for s, e in spans if s < m.start() < e), None)  # noqa: E731
        for m in EYE_OR_STATE.finditer(line):
            if inside(m) is None:
                bad.append(line)
        for m in RECORD_NAME.finditer(line):
            span = inside(m)
            if span is None or "記録の名" not in line[span[0]:m.start()]:
                bad.append(line)
    return list(dict.fromkeys(bad))


# 写しの規則が本線の答え方で書く問いの文（本線 graphloops の human_gate の question と同じ形）
MAINLINE_Q = ("今ある能力を減らす変更が挙がった。通すなら continue --note <通す範囲と条件>。\n"
              "単位を外すなら --detail <JSON のファイル>。通さないなら stop")


def unquoted_mainline(text: str) -> list:
    """引用（> の行）の外で、問いの文の行がそのまま載っている行"""
    parts = [x.strip() for x in MAINLINE_Q.splitlines()]
    return [line for line in text.splitlines() if not line.lstrip().startswith(">") and any(p in line for p in parts)]


AWAITING_PR = {"key": "q-awaiting-pr", "kind": "awaiting", "status": "held", "origin": "parallel_pr",
               "reason": "人が確かめる。測り方: `gh pr list --state open`"}


PR_NOT_RUN = {"parallel_pr": {"status": "not_run", "reason": "sandbox が api.github.com への通信を拒んだ"}}
# 利用者の run 8cb2ee00 の判定役が立てた問いの形（field は写しの型で origin を持てない。key の頭が素材の名）
FIELD_PR = {"key": "parallel_pr: 対象の 3 ファイルを触る並行のオープン PR を確かめていない", "kind": "field", "status": "held",
            "reason": "素材の parallel_pr は not_run。測り方: `gh pr list --state open`"}
MEASURED = {"question": "parallel_pr", "text": "同じ所を触る PR は無い", "command": "gh pr list --state open --json files",
            "output": "[]"}


if __name__ == "__main__":
    unittest.main()
