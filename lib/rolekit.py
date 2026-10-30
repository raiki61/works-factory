"""役の節を回す共通の口（P1 計画 Task 13。C13・〔振〕10.3）。本線（graphloops）の指示書を engine と同じ描き方で描く式と、
ブロックのスクリプトの入口の約束を 1 か所に置く（前は rejudge・refix に写しが在った）。

- rejects_text:   その輪の拒否の文の全部（古い順）を、次の回の役に読ませる 1 つの文に。最後の拒否だけでは、前の回の拒否が会話に
                  残らない役は前の回の誤りを繰り返す（#345。会話を継ぐ仕組みは作らない。docs/owner-decisions.md）。役に拒否を渡す所は
                  これを読むのが決まり。外れは、会話を継ぐ輪（fresh_context: false）の頭の節が前の周の受け付けの返りから拒否の 1 件
                  だけを渡す所（前の回の拒否は会話に残る）。会話を継ぐ輪でも全部を渡してよい（judge の仕様と再審の輪・eyes の R4。
                  resume で輪が 1 周目から回り直すと役は新しい会話で起きる）
- write_rejects・reject_file・reject_file_or_blank・rejects_text_path: rejects_text を置き場の rejects-<名>.md に書く（道具を持つ役が読む）。
                  役に拒否を見せる頭書きの文は持たない（共通の断片 workflows/.shared/prompts/rejected.md）
- accept_round:   受け付けの回の住処（返答を読む→take→拒否を控えに積む→GIVE_UP_AFTER 回目で諦める→最後の回かを答える）。呼び手は
                  口を引き、控えの名も回数も自分で持たない。方針 net（計画と事前審査の受け付け）は GIVE_UP_AFTER の代わりに、届かない
                  大きさの網 NET_AFTER 回目で諦める（届けば工場の不具合。NET_WHY）。take の返りの欄 ok・reason・give_up（1 回目から諦める）・count（false なら
                  積まない）・kind（控えの行に残す）を口が読む。控え rejects-<名>.json が読めない・書けなければ、落ちずに done 真の拒否
                  （口の外の reject_file が書く rejects-<名>.md が書けない時は OSError が呼び手まで上がる）
- accept_parsed:  accept_round の本体。読んだ返答の (返答, 読めない訳)（parse_reply か resubmitted の返り）を受ける。拒まれた後の
                  出し直しを合わせる受け付けは、resubmitted で合わせた答えをここに渡す（合わせは take の前段、数えは口の 1 か所）
- with_done:      拒否の控え rejects-<名>.json の唯一の書き手（accept_round が呼ぶ 1 段）。通れば done。拒否は盤面の根の控えに積み、
                  GIVE_UP_AFTER 回目（方針 net なら NET_AFTER 回目。その行は after に NET_AFTER を残す）の拒否で done（出し直しても
                  直らない拒みは 1 回目で）。控えは run の間消さず resume を跨いで数える。
                  消すのは構造の目の段 A が測り直す周の eye.reset だけ
- is_last_attempt: 輪の今の回が諦める回（GIVE_UP_AFTER 回目）か。rolekit の外の受け付けは回の比べをこれに任せる（TDD の段の自前の数え
                  tddloop の tries は別のサブシステムで、ここを通らない）
- rejected:       盤面の節でない受け付けの拒否の文の並び（古い順。指示書の番号と、輪が落ちた周の最後の拒否の文に使う）
- reject_rows:    控えの行 {at, reason, kind}（kind は行に在る時だけ）
- gave_up_text:   役の返答を諦めた理由の 1 行の文（回数で諦めた時と、出し直させずに諦めた時）
- given_up_reason: 盤面の節でない受け付けの出口が、控えの最後の拒否の文を引く（諦めの回の数は控えの最後の行の after。無ければ
                  GIVE_UP_AFTER。網で諦めた時は NET_WHY を添える）
- attempt:        盤面の節でない受け付けの輪の今の回（控えの拒否の数 + 1）
- current_round:  輪の今の回を、控えの誤りで落ちずに読む（読めなければ accept_round と同じ done 真の拒否）。take の前に回が要る受け付けが引く
- round_outcome:  accept_round の返りの、輪の until が読む 4 つの欄 {ok, done, give_up, reason}
- _legacy_rows:   前の版の控え（reject-<名>-<k>.md・報告の <名>-rejects.json）の読み替え（resume）。rejects-<名>.json が無い時だけ読み、
                  次に積む時に rejects-<名>.json に合わせて書く。消す期限はこの関数の docstring
- parse_reply:    役の返答（$<役>.output の JSON の文字列）を dict に
- candidate_path: 受け付けが前の答えと出し直しを合わせた答えの控え（置き場の candidate-<名>.json。次の出し直しを合わせる元）
- merge_fields:   前の答えに出し直しの欄を合わせる（出し直しに在る欄が前の欄を置き換え、無い欄は前のまま）
- resubmitting:   輪の前の周が拒まれ、合わせた答えの控えが在るか（出し直しの周か。指示は共通の断片 resubmit）
- resubmitted:    受け付けが照らす答えの全体（1 回目の役の返答か、控えの前の答えと出し直しを合わせた物）を控えに書いて返す。
                  役の形が根の欄を要ると書かない（出し直しの役の形を 1 回目と同じにする。#832）ので、要る欄の欠けと、1 回目の答えの
                  出し直しの役だけの欄をここで拒む（MISSING_FIELDS・FIX_ONLY_FIELDS）

層は L3（盤面と受け付け）。ライン・include の id・ブロックの名前を書かない（tests/test_layers.py）。
"""
import copy
import datetime
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from engine.util import safe_name  # noqa: E402
import jsonfile  # noqa: E402
import oneline  # noqa: E402


class BoardGap(Exception):
    """内部の誤り（表の欠け・配線の誤り・保存できない盤面への保存・効かない差し替え）。役に返しても直らない"""


GIVE_UP_AFTER = 3                       # 輪の max_iterations と同じ数（ブロックの試験が YAML と突き合わせる）
# 計画と事前審査の受け付けの網（方針 net）。回数の上限で諦めない受け付けの輪に置く、届かない大きさの数（輪の max_iterations と
# 同じ数。線の計画の往復の網と同じ 20。ブロックの試験が YAML と突き合わせる）
NET_AFTER = 20
NET_WHY = "受け付けの網 {n} 回に届いた。工場の不具合として止めた"


def rejects_text(reasons) -> str:
    """拒否の文の並び reasons（古い順）を、回の番号を付けて 1 つの文に（空の並びは空の字）"""
    reasons = [str(r).strip() for r in reasons]
    if not reasons:
        return ""
    blocks = [f"{k} 回目の拒否:\n{r}" for k, r in enumerate(reasons, 1)]
    return "\n\n".join([f"受け付けがこれまでに拒んだ理由の全部（古い順に {len(reasons)} 件。前の回の拒否も直したままにする）。", *blocks])


def write_rejects(board, name: str, reasons) -> str:
    """拒否の文の並び reasons（古い順）の rejects_text を置き場 board の rejects-<name>.md に書き、そのパスを返す。並びが空なら空の字"""
    text = rejects_text(reasons)
    if not text:
        return ""
    path = rejects_text_path(board, name)
    path.write_text(text + "\n", encoding="utf-8")
    return str(path)


def rejects_text_path(board, name: str) -> pathlib.Path:
    """write_rejects が拒否の全部を書くファイル（置き場 board の rejects-<name>.md）"""
    return pathlib.Path(board) / f"rejects-{safe_name(name)}.md"


def reject_file(board, name: str) -> str:
    """盤面の節でない受け付け name の拒否の控えの全部を write_rejects で書いたファイル（拒否が無ければ空の字）"""
    return write_rejects(board, name, rejected(board, name))


def reject_file_or_blank(board, name: str) -> str:
    """reject_file。ただし控えが読めなければ空の字（accept_round が控えの誤りを done 真の拒否にした後の呼び手が引く。
    同じ控えを読み直して落ちない）。控えは読めて rejects-<名>.md だけ書けない時は空にせず OSError を上げる（空にすると、次の回の
    指示書が前の拒否の名指しを黙って失う）"""
    try:
        return reject_file(board, name)
    except BoardGap:
        return ""


# ---------------------------------------------------------------- 受け付け（出し直しの輪）
def _read_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as e:
        raise BoardGap(f"{path} が読めない: {e}") from None


def gave_up_text(name: str, count: int, last: str, *, at_once: bool = False) -> str:
    """役 name の返答を諦めた理由の 1 行の文（given_up_reason と、控えを自分で持つ受け付けが引く正本）。at_once は出し直させずに諦めた時（with_done の give_up）"""
    last = oneline.one_line(last)
    if at_once:
        return f"{name} の返答を受け付けが出し直させずに諦めた（拒否: {last}）"
    return f"{name} の返答が {count} 回とも受け付けで拒まれた（最後の拒否: {last}）"


# ---------------------------------------------------------------- 盤面の節でない受け付けの done
def rejects_path(board: pathlib.Path, name: str) -> pathlib.Path:
    """盤面の節でない受け付け name の拒否の控え（盤面の根。[{at, reason, kind?, give_up?}]。kind は take の返りに在った行だけ）"""
    return pathlib.Path(board) / f"rejects-{safe_name(name)}.json"


def _legacy_rows(board: pathlib.Path, name: str) -> list:
    """前の版の拒否の控えの読み替え（resume）。rejects-<name>.json が無い時だけ、前の版の形を古い順に読む: reject-<name>-<k>.md
    （k の順。行 {reason}。修正の輪の受け付け）か、<name>-rejects.json（報告の受け付けの report-rejects.json。行 {node, attempt, kind,
    reason}）。どちらも無ければ空。次に with_done が積む時に rejects-<name>.json にそろえて書く（一度だけの読み替え）。前の版の md は
    はみ出しを相談に積んだ回の分も 1 枚に数えてしまう（版を跨ぐ resume の端）。
    消す期限: 2027-01-15 以降、この変更より前に始めた run が resume されなくなったら消す"""
    folder = pathlib.Path(board)
    found = []
    for p in folder.glob("reject-*.md") if folder.is_dir() else ():
        m = re.fullmatch(rf"reject-{re.escape(name)}-(\d+)\.md", p.name)
        if m:
            found.append((int(m.group(1)), p))
    rows = []
    for _, p in sorted(found):
        try:
            rows.append({"reason": p.read_text(encoding="utf-8").rstrip("\n")})
        except OSError as e:
            raise BoardGap(f"{p} が読めない: {e}") from None
    if rows:
        return rows
    got = _read_json(folder / f"{name}-rejects.json", [])
    return [{"reason": str(r.get("reason", "")), **({"kind": r["kind"]} if r.get("kind") else {})}
            for r in got if isinstance(r, dict)] if isinstance(got, list) else []


def _rows(board: pathlib.Path, name: str) -> list:
    path = rejects_path(board, name)
    if not path.exists() and not path.is_symlink():
        return _legacy_rows(board, name)
    return _read_json(path, [])


def with_done(board: pathlib.Path, name: str, out: dict, *, give_up: bool = False, net: bool = False) -> dict:
    """拒否の控えの唯一の書き手（accept_round が呼ぶ 1 段）: 通れば done。拒否は控えに積み、GIVE_UP_AFTER 回目で done（輪はそこで抜け、
    出口が諦めを扱う）。net が真なら NET_AFTER 回目で done にし、積む行に after: NET_AFTER を残す（given_up_reason が読む）。
    give_up 真の拒否は回数を待たずに done（出し直しても直らない拒み）。out の kind が空でない字なら行に写す。
    前の版の形の控えしか無ければ、その行を引き継いで rejects-<name>.json に書く（_legacy_rows）"""
    if out.get("ok") is True:
        return {**out, "done": True}
    path = rejects_path(board, name)
    rows = _rows(board, name)
    row = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reason": str(out.get("reason", ""))}
    if isinstance(out.get("kind"), str) and out["kind"]:
        row["kind"] = out["kind"]
    if net:
        row["after"] = NET_AFTER
    rows.append({**row, "give_up": True} if give_up else row)
    jsonfile.write(path, rows, indent=2)
    return {**out, "done": give_up or len(rows) >= (NET_AFTER if net else GIVE_UP_AFTER)}


def is_last_attempt(attempt: int) -> bool:
    """輪の今の回 attempt（attempt が返す値）が、諦める回（GIVE_UP_AFTER 回目）か。rolekit の外の受け付けの回の比べはこれを引く
    （TDD の段の自前の数え tddloop の tries は別）"""
    return attempt >= GIVE_UP_AFTER


def accept_round(board, name: str, raw, take, *, reject=None, on_give_up=None, net: bool = False) -> dict:
    """受け付けの輪の 1 回（受け付けの回の住処。元 rolekit.main_accept）。役の返答の字 raw を読み（parse_reply）、accept_parsed に通す。
    raw が None なら読まずに take(None) を呼ぶ（返答の無い回と、受けるかを呼び手が先に決めた回）"""
    return accept_parsed(board, name, None if raw is None else parse_reply(raw), take, reject=reject, on_give_up=on_give_up,
                         net=net)


def accept_parsed(board, name: str, got, take, *, reject=None, on_give_up=None, net: bool = False) -> dict:
    """受け付けの輪の 1 回の本体。got は (読めた返答, 読めない訳)（parse_reply か、拒まれた後の出し直しを前の答えと合わせる
    resubmitted の返り）で、返答を take(reply) に通す。got が None なら take(None)。読めない返答と take の中の例外は
    reject(理由) で拒否にする（既定は {ok: False, reason}。受け付けは落ちない）。
    受け付けの輪の 1 回の拒否の定義はここにだけ在り（TDD の段の自前の数え tddloop の tries は別）、take の返りの欄を読む: ok でなければ
    board/rejects-<name>.json に積み（with_done）、GIVE_UP_AFTER 回目（net が真なら網の NET_AFTER 回目）で done。give_up が真なら 1 回目でも done。count が false なら控えに積まず（done は give_up が真の時だけ真）、
    kind が空でない字なら控えの行に kind として残す。諦めた時（done 真・ok 偽）は on_give_up() を呼ぶ。
    返り take の返りに done を足した物。拒否の控え rejects-<name>.json が読めない・書けなければ、落ちずに done 真の拒否（理由に
    『拒否の控えが扱えない』。on_give_up は呼ばない）。口は rejects-<name>.md を書かない（reject_file が口の後に書き、書けなければ
    OSError を呼び手まで上げる。控えは積んだ後なので、呼び手が受けずに落ちた回の出し直しは同じ拒否をもう 1 行積む）。on_give_up が落ちた時は、控えの誤りとは別の理由（『諦めた後の処理が落ちた』）の done 真の拒否"""
    reject = reject or (lambda why: {"ok": False, "reason": why})
    try:
        if got is None:
            got = take(None)
        else:
            reply, why = got
            got = take(reply) if reply is not None else reject(why)
    except Exception as e:  # noqa: BLE001
        got = reject(f"受け付けの中で例外（{type(e).__name__}: {e}）")
    give_up = got.get("give_up") is True
    try:
        if got.get("count") is False and got.get("ok") is not True:
            out = {**got, "done": give_up}
        else:
            kind = {"kind": got["kind"]} if got.get("kind") else {}
            out = {**got, **with_done(board, name, {"ok": got.get("ok") is True, "reason": str(got.get("reason") or ""), **kind},
                                      give_up=give_up, net=net)}
    except Exception as e:  # noqa: BLE001
        return {**got, **_unusable(e)}
    if out["done"] and out.get("ok") is not True and on_give_up:
        try:
            on_give_up()
        except Exception as e:  # noqa: BLE001
            return {**out, "ok": False, "done": True, "reason": f"諦めた後の処理が落ちた（控えは積めた。{type(e).__name__}: {e}）"}
    return out


def _unusable(e: Exception) -> dict:
    return {"ok": False, "done": True, "reason": f"拒否の控えが扱えない（{type(e).__name__}: {e}）"}


def current_round(board, name: str) -> tuple:
    """輪の今の回を、控えの誤りで落ちずに読む: (attempt, None)。控え rejects-<name>.json が読めなければ (0, accept_round と同じ
    done 真の拒否 {ok, done, reason})。take の前に回が要る受け付けが引き、拒否を返して照らさずに抜ける"""
    try:
        return attempt(board, name), None
    except BoardGap as e:
        return 0, _unusable(e)


def round_outcome(out: dict) -> dict:
    """accept_round（か current_round の拒否）の返り out の、輪の until が読む 4 つの欄 {ok, done, give_up, reason}。give_up は
    諦めた（done 真・ok 偽）時に真"""
    return {"ok": out["ok"], "done": out["done"], "give_up": out["done"] and not out["ok"], "reason": out["reason"]}


def _reject_rows(board: pathlib.Path, name: str) -> list:
    rows = _rows(board, name)
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def reject_rows(board: pathlib.Path, name: str) -> list:
    """盤面の節でない受け付け name の拒否の控えの行 {at, reason, kind} の並び（古い順。控えが無ければ空。kind は行に在る時だけ）"""
    return [{"at": r.get("at"), "reason": str(r.get("reason", "")), **({"kind": r["kind"]} if r.get("kind") else {})}
            for r in _reject_rows(board, name)]


def rejected(board: pathlib.Path, name: str) -> list:
    """盤面の節でない受け付け name の拒否の文の並び（古い順。控えが無ければ空）"""
    return [r["reason"] for r in reject_rows(board, name)]


def attempt(board: pathlib.Path, name: str) -> int:
    """盤面の節でない受け付け name の輪の今の回（控えの拒否の数 + 1）。控えはファイルなので、輪を 1 周目から回し直す resume を
    跨いでも数え直さない"""
    return len(rejected(board, name)) + 1


def given_up_reason(board: pathlib.Path, name: str) -> str:
    """控えの拒否が諦めの回の数（最後の行の after。無い行は GIVE_UP_AFTER）件あるか、出し直さずに諦めた拒否（give_up 真の行）が在れば、
    諦めた理由の 1 行（最後の拒否の文。網 NET_AFTER で諦めた時は NET_WHY を添える）。届いていなければ空（網の受け付けは、
    3 件の拒否の後に通った往復を諦めと読まない）"""
    rows = _reject_rows(board, name)
    at_once = any(r.get("give_up") is True for r in rows)
    after = rows[-1].get("after") if rows and isinstance(rows[-1].get("after"), int) else GIVE_UP_AFTER
    if not rows or not (at_once or len(rows) >= after):
        return ""
    text = gave_up_text(name, len(rows), str(rows[-1].get("reason", "")), at_once=at_once)
    return text + "。" + NET_WHY.format(n=after) if after == NET_AFTER and not at_once else text


def parse_reply(raw):
    """役の返答（実行基盤が $<役>.output を JSON の文字列で渡す）を dict に。読めなければ (None, 理由)。文は script_io.main と同じ"""
    try:
        reply = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:
        return None, f"返答が JSON として読めない: {e}（頭: {str(raw)[:200]!r}）"
    why = _not_object(reply, "返答")
    return (None, why) if why else (reply, "")


def _not_object(got, what: str) -> str:
    """値 got が JSON のオブジェクトでなければ、何の値か what を頭にした拒否の文（オブジェクトなら空）"""
    return "" if isinstance(got, dict) else f"{what}が JSON のオブジェクトでない（{type(got).__name__}）"


def candidate_path(board, name: str) -> pathlib.Path:
    """受け付け name が合わせた答えの控え（置き場 board の candidate-<name>.json）。拒まれた後の出し直しは拒まれた欄だけを返し、
    受け付けがこの控えと合わせてから答えの全体を照らす"""
    return pathlib.Path(board) / f"candidate-{safe_name(name)}.json"


def merge_fields(prev: dict, part: dict) -> dict:
    """前の答え prev に出し直し part を合わせた写し: part に在る欄が prev の欄を置き換え、無い欄は prev のまま。prev・part は書き換えない"""
    return {**copy.deepcopy(prev), **copy.deepcopy(part)}


def resubmitting(board, name: str, prev) -> bool:
    """輪の前の周の受け付け name が拒み（prev は with: に結んだ前の周の ok を値に戻した物）、合わせた答えの控えが在るか。真なら
    頭の節は材料の代わりに出し直しの指示（共通の断片 resubmit）を渡し、出し直しの役（1 回目の役の会話の続き）を起こさせる。resume で輪が 1 周目
    から回り直した時は prev が空なので偽"""
    return prev is False and candidate_path(board, name).is_file()


def _reply_object(got, what: str) -> tuple:
    if isinstance(got, str):
        return None, f"{what}が JSON として読めない（頭: {got[:200]!r}）"
    why = _not_object(got, what)
    return (None, why) if why else (got, "")


MISSING_FIELDS = "答えに要る欄 {keys} が無い（返していない欄を足して返せ）"
FIX_ONLY_FIELDS = "1 回目の答えに、出し直しの役だけが書く欄 {keys} が在る（この欄は書かない）"


def resubmitted(board, name: str, reply, part, merge, *, required=(), fix_only=()) -> tuple:
    """(受け付け name が照らす答えの全体, 拒否の文)。reply は 1 回目の役の返答、part は拒まれた後の出し直しの役の返答で、どちらも
    JSON に戻した値（起きなかった役は None）。part が在れば控え candidate_path の前の答えと merge(前の答え, part) で合わせ、無ければ
    reply。空の出し直しは前の答えのまま（拒否が作業ツリーのファイルだけを名指せば、役はファイルを直して欄を返さない）。合わせた答えは
    控えに書く（次の出し直しを合わせる元）。返答が object でない・控えが読めない・書けなければ (None, 訳)。
    出し直しの役の形（output_format）は 1 回目の役と同じにする（形が違うと会話の続きの最初の要求でキャッシュが効かない。#832）ので、
    形は根の欄を要ると書かない。要る欄 required は、合わせた答えに無ければここで拒む（MISSING_FIELDS）。出し直しの役だけが書く欄
    fix_only は、1 回目の答えに在れば外して控えに書き、拒む（FIX_ONLY_FIELDS）。どちらの拒みも控えは書くので、次の周の出し直しの役が
    欠けた欄だけを返せる"""
    path = candidate_path(board, name)
    late = []
    if part is None:
        got, why = _reply_object(reply, "返答")
        extra = [k for k in fix_only if got is not None and k in got]
        if extra:
            got = {k: v for k, v in got.items() if k not in extra}
            late.append(FIX_ONLY_FIELDS.format(keys=", ".join(extra)))
    else:
        part, why = _reply_object(part, "出し直しの返答")
        if why:
            return None, why
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return None, f"前の答えの控え {path} が読めない（{type(e).__name__}）ので、出し直しを合わせられない"
        got = merge(prev, part) if isinstance(prev, dict) else None
        why = "" if got is not None else f"前の答えの控え {path} が JSON のオブジェクトでない"
    if got is None:
        return None, why
    try:
        jsonfile.write(path, got, indent=2)
    except OSError as e:
        return None, f"合わせた答えを控え {path} に書けない（{type(e).__name__}: {e}）"
    missing = [k for k in required if k not in got]
    if missing:
        late.append(MISSING_FIELDS.format(keys=", ".join(missing)))
    return (None, "\n\n".join(late)) if late else (got, "")
