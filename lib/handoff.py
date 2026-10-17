"""引き継ぎのメモ（考え handoff）の住処: 役が次の周の自分へ書くメモの型・頼み・前の周の節・控えの書き読み。

役は周ごとに新しい会話で起きて、前の周で読んだ所も考えも持たない。そこで役の返答に、本文・案とは別の欄 handoff を持たせ、
受け付けが外して周のフォルダに置き（控えの名と置き場は marks の種 handoff）、次の周の材料が前の周のメモをパスで名指す。
計画の受け付け（lib/planfile.py）も報告の受け付け（lib/runreport.py）もここを呼び、型・頼み・節を自分で持たない。
役の返答の型の YAML の写し（計画の workflows/plan/works-factory-plan.yaml・報告の workflows/report/works-factory-report.yaml）は
SCHEMA の写しで、持ち主との一致は試験が見る。

- FIELD・KEYS・SCHEMA: 返答の欄の名・4 つの欄（read・decided・rejected・doubts）・欄の型
- ASK: メモを書けという頼み（役の名を含まない。計画の材料も報告の輪の頭の節も同じ文を貼る）
- HEAD・USE・NONE・UNREADABLE: 前の周の節の見出し・前の周のメモの使い方・メモが無い周の文・読めない周の文
- path_of(board)・save(board, note): 周のフォルダ board の控えのパス・控えを置く（空なら前の控えを消す）
- unreadable(rounds): 在るのに読めない控えのパスの並び
- section(rounds): 前の周のフォルダの並び（古い順）の節。並びが空なら節ごと出さない
"""
from __future__ import annotations

import pathlib
import sys

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import marks  # noqa: E402
import promptsection  # noqa: E402

FIELD = "handoff"                 # 役の返答の頭の任意の欄。受け付けが外して周のフォルダに置く
KEYS = ("read", "decided", "rejected", "doubts")
_TEXT = {"type": "string", "minLength": 1}
SCHEMA = {"type": "object", "additionalProperties": False, "required": list(KEYS),
          "properties": {
              "read": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["path", "lines", "why"],
                  "properties": {"path": _TEXT, "lines": _TEXT, "why": _TEXT}}},
              "decided": {"type": "array", "items": _TEXT},
              "rejected": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False, "required": ["option", "why"],
                  "properties": {"option": _TEXT, "why": _TEXT}}},
              "doubts": {"type": "array", "items": _TEXT}}}
ASK = (f"次の周の自分は新しい会話で起きて、この会話で読んだ所も考えも持たない。返答の欄 {FIELD}（本文・案とは別の欄。"
       "機械が周のフォルダに置き、本文・案には入らない）に、次の周の自分へのメモを書け: read＝読んだ所（path・lines・読んだ訳 why）、"
       "decided＝そう決めた訳の文、rejected＝退けた案（option）と退けた訳（why）——選んだ道に限らず別の直し方・書き方も、"
       "doubts＝迷っている所の文。どの並びも空でよいが、4 つとも書け")
HEAD = promptsection.Section("## 前の周の引き継ぎのメモ（機械が名指した）", source="fn:handoff.section")
USE = ("前の周の自分が書いたメモの使い方: read に並ぶ所から読み直し、decided の訳を保ち、rejected の案は拒否の訳・審査の指摘が求めない限り"
       "戻さず、doubts は拒否の訳・審査の指摘と突き合わせろ。メモは古い周から順に全部読め")
NONE = "置かれていない（その周の役がメモを書かなかったか、返答の本文が空で受け付けがメモを置かなかった）"
UNREADABLE = "読めない（控えが壊れている。読まずに進め）"


def path_of(board) -> pathlib.Path:
    """周のフォルダ board の引き継ぎのメモの控えのパス（marks の種 handoff）"""
    return marks.path_of("handoff", board)


def save(board, note) -> None:
    """周のフォルダ board にメモ note を置く。note が空でない時だけ、無い周のフォルダも作ってから置く。空なら前から残る控えを消すだけで、
    フォルダは作らない（メモの無い周に空のフォルダを残さない）。置けなければ OSError をそのまま上げる"""
    path = path_of(board)
    if note:
        path.parent.mkdir(parents=True, exist_ok=True)
        marks.write(path, note)
    else:
        path.unlink(missing_ok=True)


def unreadable(rounds) -> list:
    """周のフォルダの並び rounds のうち、控えが在るのに読めない（JSON でない・オブジェクトでない）周の控えのパスの並び（並びの順）。
    控えの無い周は数えない"""
    out = []
    for board in rounds:
        path = path_of(board)
        if path.exists() and not isinstance(marks.load(path), dict):
            out.append(path)
    return out


def section(rounds) -> str:
    """前の周のフォルダの並び rounds（古い順）の節: HEAD の直後に使い方 USE を置き、1 周 1 行で、メモの在る周はパス（Read で読め。
    中身は貼らない）、無い周は NONE、読めない周は UNREADABLE と名指す。並びが空なら（前の周が無い）節ごと出さない"""
    rounds = list(rounds)
    if not rounds:
        return ""
    broken = set(unreadable(rounds))
    lines = []
    for board in rounds:
        path = path_of(board)
        if path in broken:
            note = UNREADABLE
        else:
            note = f"{path}（Read で読め）" if path.is_file() else NONE
        lines.append(f"- {pathlib.Path(board).name}: {note}")
    return f"{HEAD}\n\n{USE}\n\n" + "\n".join(lines)
