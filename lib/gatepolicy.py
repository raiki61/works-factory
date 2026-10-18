"""人の関所と無人の方針（考え human-gates）の住処。標準ライブラリと startrec・answer・stopby（L1）と、事前審査の壁打ちの
控えの読み converge だけを読む。

run の入力の 2 つの語、最後の人の関所の開き方（final_gate）と無人の run か（unattended）の語・既定・確かめと、読む口を持つ。
書き手は線の入口（入口のブロックの節 open。中身は core の entry.start）の 1 か所で、check で確かめた語を始めの記録
（startrec）に置く。読み手（境の節・修正前の関所の決め手・案の直し・報告）は始めの記録をこのモジュールの口で読み、線の節ごとに
入力を写さない（入口を 1 つの入力の形にそろえる。後ろの段は入口の控えだけを読む）。

- FINAL_KEY・UNATTENDED_KEY: 線の入力と始めの記録の欄の名
- FINAL_GATES（ALWAYS・WHEN_NEEDED・PROTECTED_ONLY）: 最後の関所の開き方。空の既定は ALWAYS（P1-R3: 必ず止まれる所を残す）で、
  無人の run の空の既定は WHEN_NEEDED（無人の run は最後の関所で推しを持たず、開くはずの時は止まって差分を当てないので、ALWAYS では
  どの run も止まる。持ち主の決め unattended「人がいないときは推しの答え。」）。
  WHEN_NEEDED は開ける理由（最後のテストが緑でない・盤面が人に聞いている…）が在る時だけ、PROTECTED_ONLY は守りのファイルを
  触った時だけ開く（ほかの理由は報告の冒頭に並ぶだけ）
- UNATTENDED・UNATTENDED_WORDS: 無人の語（true）と受ける語（空は人の居る run）
- FINAL_KIND: 最後の関所の答えを残す process.human_items の行の kinds
- check(final, unattended, *, spec) -> {FINAL_KEY, UNATTENDED_KEY}: 入口の語の確かめ（語の外・仕様の段と無人の組みは Refused）
- final_mode(board_dir)・unattended(board_dir): 始めの記録からの読み（記録が無い・欄が空なら既定。記録の開き方が語の外なら
  ValueError——入口が確かめた後なので配線の誤り）
- unattended_of(doc): 始めの記録の dict（か None）からの、無人の run かの読み（unattended と報告・台帳の見え方が同じ式を引く）
- opens(mode, *, reasons, guarded): 最後の関所を開くか
- head_words(doc): 報告の頭の行の句（始めの記録の dict から。開き方が無ければ空）

無人の run が承認ノードを推しで進むか止まるかの決め（持ち主 2026-10-15「人がいないときは推しの答え。」issue #552）はここ 1 つで、
承認ノードの script（修正前・案の直し）と gatemarks はこの口を呼ぶ。推しの尾の字の形は gatemarks が持ち、読んだ物を Push で渡す。
- Push(go, note, rec): 項目か止まった壁打ちの推しの読み（通す推しか・修正役に届く一言・答えに残す読みの全部）
- Passage(go, stop_reason, asked, pushed)・passage(rows, read): 無人の run で開くはずの承認ノードの抜け方。項目 rows の全部が
  通す推しを持つ時だけ推しで進み（asked は rows、pushed は答え {decision, text, answer.PUSHED}）、ほかは開かずに止める（needs-human）
- stuck_pushable(board_dir, doc, push, *, design_only): 止まった事前審査の壁打ちの行に、事前審査の役の推しの尾を付けてよいか
"""
from __future__ import annotations

from typing import Callable, NamedTuple

import answer
import converge
import startrec
import stopby

FINAL_KEY = "final_gate"
UNATTENDED_KEY = "unattended"
FINAL_GATES = ("always", "when_needed", "protected_only")
ALWAYS, WHEN_NEEDED, PROTECTED_ONLY = FINAL_GATES
UNATTENDED = "true"
UNATTENDED_WORDS = ("", UNATTENDED)
FINAL_KIND = FINAL_KEY


class Refused(ValueError):
    """入口の語が受けられない（入口が InputRefused にする）"""


def check(final, unattended, *, spec) -> dict:
    """入口の 2 つの語を確かめて {FINAL_KEY: 開き方（空は ALWAYS、無人の run の空は WHEN_NEEDED）, UNATTENDED_KEY: 語} を返す"""
    alone = (unattended or "").strip()
    if alone not in UNATTENDED_WORDS:
        raise Refused(f"{UNATTENDED_KEY}={unattended!r} は知らない値（空か {UNATTENDED}）")
    mode = (final or "").strip() or (WHEN_NEEDED if alone else ALWAYS)
    if mode not in FINAL_GATES:
        raise Refused(f"{FINAL_KEY}={final!r} は知らない値（{' / '.join(FINAL_GATES)}）")
    if spec and alone:
        raise Refused(f"spec=on と無人の run（{UNATTENDED_KEY}）は組めない——仕様の承認は承認ノードで、無人の run は承認ノードで止めるので"
                      "仕様が固まらずに止まる（人の居る run で回す）")
    return {FINAL_KEY: mode, UNATTENDED_KEY: alone}


def final_mode(board_dir) -> str:
    """始めの記録の最後の関所の開き方（無い・空は ALWAYS。語の外は ValueError）"""
    mode = str(startrec.read(board_dir).get(FINAL_KEY) or "").strip() or ALWAYS
    if mode not in FINAL_GATES:
        raise ValueError(f"始めの記録の {FINAL_KEY}={mode!r} は知らない値（{' / '.join(FINAL_GATES)}）")
    return mode


def unattended(board_dir) -> bool:
    """run が無人で回っているか（始めの記録の欄。読めなければ人の居る run）"""
    return unattended_of(startrec.read(board_dir))


def unattended_of(doc) -> bool:
    """始めの記録の dict（か None）が無人の run か"""
    return isinstance(doc, dict) and doc.get(UNATTENDED_KEY) == UNATTENDED


def opens(mode: str, *, reasons, guarded: bool) -> bool:
    """最後の関所を開くか: ALWAYS はいつも、WHEN_NEEDED は開ける理由が在る時、PROTECTED_ONLY は守りのファイルを触った時"""
    if mode == WHEN_NEEDED:
        return bool(reasons)
    if mode == PROTECTED_ONLY:
        return bool(guarded)
    return True


def head_words(doc: dict) -> str:
    """報告の頭の行の句（始めの記録の dict の開き方。無ければ空）"""
    mode = doc.get(FINAL_KEY) if isinstance(doc, dict) else None
    return f"最後の承認ノード: {mode}" if mode else ""


class Push(NamedTuple):
    go: bool     # 通す（continue）推しか
    note: str    # 修正役に人の一言と同じ道で届く一言（尾の字）
    rec: dict    # 答えの欄 answer.PUSHED に残す読みの全部


class Passage(NamedTuple):
    go: bool
    stop_reason: str
    asked: list
    pushed: dict | None


def passage(rows: list, read: Callable[[str], Push | None]) -> Passage:
    """無人の run で開くはずの承認ノードの抜け方。read は項目の文の推しの尾の読み（gatemarks.row_push。尾が無ければ None）。
    項目の全部が通す推しを持つ時だけ推しで進む（一言は推しの note を「；」で繋いだ物）。項目が無い・推しの無い項目か止める推しが
    1 つでも在れば止める（機械は推しを作らない）"""
    pushes = [read(row) for row in rows]
    if not pushes or not all(p is not None and p.go for p in pushes):
        return Passage(False, stopby.NEEDS_HUMAN, [], None)
    note = "；".join(dict.fromkeys(p.note for p in pushes))
    return Passage(True, "", list(rows), {"decision": answer.VERBS[0], "text": note, answer.PUSHED: [p.rec for p in pushes]})


def stuck_pushable(board_dir, doc: dict, push: Push | None, *, design_only: bool) -> bool:
    """止まった事前審査の壁打ち（converge の控え doc）の行に、事前審査の役の推し push（最後の往復の push の読み。無ければ None）の
    尾を付けてよいか。全部が揃う時だけ: 無人の run・設計だけの run でない・抜け方が止まり（converge.STUCK。UNSETTLED か PERSISTED
    かでは絞らない）・最後の往復が輪の安全の上限の周で止めた物でない（上限での止まりは工場の不具合 converge.CAP_WHY で、役の推しで
    なく人が見る）・通す推しで、その note が止まった key と保留・開いた項目の番号の全部を字のまま引く（converge.uncited が空。
    修正役に届くのは note だけ）。
    付かない止まりの行は passage が止める"""
    return (unattended(board_dir) and not design_only and doc["outcome"] in converge.STUCK and not converge.capped(doc)
            and push is not None and push.go and not converge.uncited(push.note, doc))
