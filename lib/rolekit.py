"""役の節を回す共通の口（P1 計画 Task 13。C13・〔振〕10.3）。本線（graphloops）の指示書を engine と同じ描き方で描く式と、
ブロックのスクリプトの入口の約束を 1 か所に置く（前は rejudge・refix に写しが在った）。

- rejects_text:   その輪の拒否の文の全部（古い順）を、次の回の役に読ませる 1 つの文に。最後の拒否だけでは、前の回の拒否が会話に
                  残らない役は前の回の誤りを繰り返す（#345。会話を継ぐ仕組みは作らない。docs/owner-decisions.md）。役に拒否を渡す所は
                  これを読むのが決まり。外れは、会話を継ぐ輪（fresh_context: false）の頭の節が前の周の受け付けの返りから拒否の 1 件
                  だけを渡す所（前の回の拒否は会話に残る）。会話を継ぐ輪でも全部を渡してよい（judge の仕様と再審の輪・eyes の R4。
                  resume で輪が 1 周目から回り直すと役は新しい会話で起きる）
- write_rejects・reject_file・rejects_text_path・REJECT_LINE: rejects_text を置き場の rejects-<名>.md に書いて名指す（道具を持つ役。
                  名指す 1 行が REJECT_LINE）
- compose:        役に読ませる材料の組み立て: 空でない部分を空行 1 つで繋ぎ、拒否の理由のファイルが在れば 1 行目で REJECT_LINE で名指す
- with_reject:    道具ゼロの役の指示書の頭に前の拒否の文を貼る（ファイルを名指さない。裁定 R44）
- with_done:      盤面の節でない受け付け（script_io.main の finish）に done を足す。拒否は盤面の根の控え rejects-<名>.json に
                  積み、通った時か give_up_after 回目の拒否で done（出し直しても直らない拒みは 1 回目で。控えは run の間
                  消さず resume を跨いで数える。消すのは構造の目の段 A が測り直す周の eye.reset だけ）
- rejected:       盤面の節でない受け付けの拒否の文の並び（古い順。指示書の番号と、輪が落ちた周の最後の拒否の文に使う）
- gave_up_text:   役の返答を諦めた理由の 1 行の文（回数で諦めた時と、出し直させずに諦めた時）
- given_up_reason: 盤面の節でない受け付けの出口が、控えの最後の拒否の文を引く
- attempt:        盤面の節でない受け付けの輪の今の回（控えの拒否の数 + 1）
- last_reject(folder): 置き場の下の受け付けの最後の拒否の本文（報告の前の失敗の行が読む）
- parse_reply:    役の返答（$<役>.output の JSON の文字列）を dict に
- candidate_path: 受け付けが前の答えと出し直しを合わせた答えの控え（置き場の candidate-<名>.json。次の出し直しを合わせる元）
- merge_fields:   前の答えに出し直しの欄を合わせる（出し直しに在る欄が前の欄を置き換え、無い欄は前のまま）
- resubmitting・write_resubmit・RESUBMIT_ASK: 輪の前の周が拒まれた時に、出し直しの役の短い指示書（拒否の文・控えのパス・役ごとの
                  返し方）を書く
- resubmitted:    受け付けが照らす答えの全体（1 回目の役の返答か、控えの前の答えと出し直しを合わせた物）を控えに書いて返す
- LANG_RULE・LANG_DEFAULT・lang_line(start): 役の文の頭に足す言語の 1 行（元 rolekit.py 67-68 行・147-150 行。言語は始めの記録の
                  lang。空なら依頼文の言語。元 board.py 96 行）。判定・計画・修正・独立の目・報告の書き手の役が同じ口で読む
- record_lang_line(path): 始めの記録のファイル path から lang_line（読めなければ既定の言語の 1 行に読めない訳を添える）
- pointed(raw, locate): 指し札の字 raw を (パス, 読めない訳) に（指し札が読めない決まりの 1 か所。planfile.pointed も同じ物）
- pointed_lang_line(raw, locate): 始めの記録の指し札の字 raw から record_lang_line（指し札が読めなくても落ちない。script が呼ぶ 1 か所）

層は L3（盤面と受け付け）。ライン・include の id・ブロックの名前を書かない（tests/test_layers.py）。
"""
import copy
import datetime
import json
import pathlib
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
import promptsection  # noqa: E402


class BoardGap(Exception):
    """内部の誤り（表の欠け・配線の誤り・保存できない盤面への保存・効かない差し替え）。役に返しても直らない"""


GIVE_UP_AFTER = 3                       # 輪の max_iterations と同じ数（ブロックの試験が YAML と突き合わせる）


# 役の文は関所と報告に機械が字のまま載せるので、書き手に言語を縛る（元 works/.shared/core/rolekit.py 67-68 行。機械で訳さない）
LANG_RULE = ("人が読む文の欄（reason・how・what・why・異議・所見・申し出の文など、承認ノードと報告に載る文）は {lang} で書け。"
             "key・enum の値・コード識別子・パス・コマンド・エラー文はそのまま（key は周をまたいで突き合わせるので訳さない）。")
LANG_DEFAULT = "依頼文の言語（利用者の言語）"   # 元 works/.shared/core/board.py 96 行


def lang_line(start) -> str:
    """役に言語を縛る 1 行。言語は始めの記録 start の欄 lang（無ければ inputs.lang、どちらも空なら LANG_DEFAULT）"""
    start = start if isinstance(start, dict) else {}
    got = start.get("lang") or ((start.get("inputs") or {}).get("lang") if isinstance(start.get("inputs"), dict) else "")
    return LANG_RULE.format(lang=str(got or "").strip() or LANG_DEFAULT)


def record_lang_line(path) -> str:
    """始めの記録のファイル path（None は記録の無い run）の lang_line。読めない・オブジェクトでなければ既定の言語の 1 行に訳を添える"""
    if path is None:
        return lang_line({})
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"{lang_line({})}（始めの記録 {path} を読めない: {type(e).__name__}。言語は既定にした）"
    if not isinstance(doc, dict):
        return f"{lang_line({})}（始めの記録 {path} が JSON のオブジェクトでない。言語は既定にした）"
    return lang_line(doc)


POINTER_UNREAD = "ポインタが読めない"


def pointed(raw: str, locate) -> tuple:
    """(指し札の字 raw が指すファイルのパス, 読めない訳)。locate は指し札の字をパスに戻す口（境の口の pointed。空の字・null は
    None）で、None なら (None, "")。ほかの run の札・札の形でない字は POINTER_UNREAD の訳"""
    try:
        path = locate(raw)
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        return None, f"{POINTER_UNREAD}: {e}"
    if path is None:
        return None, ""
    return (path, "") if pathlib.Path(path).is_file() else (None, f"ポインタの先が無い: {path}")


def pointed_lang_line(raw, locate) -> str:
    """始めの記録の指し札の字 raw の record_lang_line。locate は pointed の口。指し札が読めない・先が無ければ既定の言語の 1 行に
    訳を添える（言語の 1 行を返す節は落ちない）"""
    path, why = pointed(raw, locate)
    if why:
        return f"{lang_line({})}（始めの記録の{oneline.one_line(why)}。言語は既定にした）"
    return record_lang_line(path)


REJECT_HEADING = promptsection.Section("## 前の回の受け付けが拒んだ理由", source="fn:rolekit.with_reject")


REJECT_LINE = ("前の回までの返答は受け付けで拒まれた。これまでの拒否の理由の全部（古い順）がファイル {path} に在る。先に Read で"
               "全部読み、前の回の拒否も含めてどの理由も満たす返答を丸ごと出し直せ（直した所だけを返すな）。")


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


def compose(parts, *, reject_file: str = "") -> str:
    """役に読ませる材料の組み立て（元 works/.shared/core/rolekit.py:168 の compose。AI を通さない）: 空でない部分を字のまま空行 1 つで
    繋ぐ。reject_file（拒否の理由の全部のファイル）が在れば 1 行目でそのパスを REJECT_LINE で名指す（理由の文そのものは貼らない）。
    同じ入力からは同じバイト"""
    out = [REJECT_LINE.format(path=reject_file)] if reject_file else []
    return "\n\n".join(out + [s for s in parts if s])


def reject_file(board, name: str) -> str:
    """盤面の節でない受け付け name の拒否の控えの全部を write_rejects で書いたファイル（拒否が無ければ空の字）"""
    return write_rejects(board, name, rejected(board, name))


def with_reject(prompt: str, reason: str) -> str:
    """道具ゼロの役の指示書の頭に、前の拒否の文 reason（輪の全部なら rejects_text）を貼る（役はファイルを読めない。前の周の値の
    差し込みで貼ると実行基盤が文の中の $… を置き換え直す。裁定 R44）"""
    return (f"{REJECT_HEADING}\n\n前の回の返答は受け付けで拒まれた。下の理由のところを直した返答を丸ごと出し直せ"
            f"（直した所だけを返すな）:\n\n```text\n{reason}\n```\n\n---\n\n{prompt}")


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
    """盤面の節でない受け付け name の拒否の控え（盤面の根。[{at, reason}]）"""
    return pathlib.Path(board) / f"rejects-{safe_name(name)}.json"


def with_done(board: pathlib.Path, name: str, out: dict, *, give_up_after: int = GIVE_UP_AFTER, give_up: bool = False) -> dict:
    """script_io.main の finish: 通れば done。拒否は控えに積み、give_up_after 回目で done（輪はそこで抜け、出口が諦めを扱う）。
    give_up 真の拒否は回数を待たずに done（出し直しても直らない拒み。元 material.py の _reject(give_up=True)）"""
    if out.get("ok") is True:
        return {**out, "done": True}
    path = rejects_path(board, name)
    rows = _read_json(path, [])
    row = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reason": str(out.get("reason", ""))}
    rows.append({**row, "give_up": True} if give_up else row)
    jsonfile.write(path, rows, indent=2)
    return {**out, "done": give_up or len(rows) >= give_up_after}


def _reject_rows(board: pathlib.Path, name: str) -> list:
    rows = _read_json(rejects_path(board, name), [])
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def reject_rows(board: pathlib.Path, name: str) -> list:
    """盤面の節でない受け付け name の拒否の控えの行 {at, reason} の並び（古い順。控えが無ければ空）"""
    return [{"at": r.get("at"), "reason": str(r.get("reason", ""))} for r in _reject_rows(board, name)]


def rejected(board: pathlib.Path, name: str) -> list:
    """盤面の節でない受け付け name の拒否の文の並び（古い順。控えが無ければ空）"""
    return [r["reason"] for r in reject_rows(board, name)]


def attempt(board: pathlib.Path, name: str) -> int:
    """盤面の節でない受け付け name の輪の今の回（控えの拒否の数 + 1）。控えはファイルなので、輪を 1 周目から回し直す resume を
    跨いでも数え直さない"""
    return len(rejected(board, name)) + 1


def given_up_reason(board: pathlib.Path, name: str, *, give_up_after: int = GIVE_UP_AFTER) -> str:
    """控えの拒否が give_up_after 件あるか、出し直さずに諦めた拒否（with_done の give_up）が在れば、諦めた理由の 1 行（最後の拒否の文）。
    届いていなければ空"""
    rows = _reject_rows(board, name)
    at_once = any(r.get("give_up") is True for r in rows)
    if not rows or not (at_once or len(rows) >= give_up_after):
        return ""
    return gave_up_text(name, len(rows), str(rows[-1].get("reason", "")), at_once=at_once)


def last_reject(folder) -> str:
    """置き場 folder（の下）の受け付けの最後の拒否の本文（元 report._accept_last_files の reason_file の本文）: 拒否の控え
    rejects-<名>.json の最後の行の文と、拒否の訳のファイル reject-*.md・reject-*.txt のうち一番新しい物。無い・読めなければ空"""
    rows = []
    for p in pathlib.Path(folder).rglob("reject*") if pathlib.Path(folder).is_dir() else ():
        try:
            if p.name.startswith("rejects-") and p.suffix == ".json":
                got = json.loads(p.read_text(encoding="utf-8"))
                text = str(got[-1].get("reason", "")) if isinstance(got, list) and got and isinstance(got[-1], dict) else ""
            elif p.name.startswith("reject-") and p.suffix in (".md", ".txt"):
                text = p.read_text(encoding="utf-8", errors="replace")
            else:
                continue
            rows.append((p.stat().st_mtime, text))
        except (OSError, ValueError):
            continue
    return oneline.one_line(max(rows, key=lambda r: r[0])[1]) if rows else ""


def parse_reply(raw):
    """役の返答（実行基盤が $<役>.output を JSON の文字列で渡す）を dict に。読めなければ (None, 理由)。文は script_io.main と同じ"""
    try:
        reply = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:
        return None, f"返答が JSON として読めない: {e}（頭: {str(raw)[:200]!r}）"
    if not isinstance(reply, dict):
        return None, f"返答が JSON のオブジェクトでない（{type(reply).__name__}）"
    return reply, ""


def candidate_path(board, name: str) -> pathlib.Path:
    """受け付け name が合わせた答えの控え（置き場 board の candidate-<name>.json）。拒まれた後の出し直しは拒まれた欄だけを返し、
    受け付けがこの控えと合わせてから答えの全体を照らす"""
    return pathlib.Path(board) / f"candidate-{safe_name(name)}.json"


def merge_fields(prev: dict, part: dict) -> dict:
    """前の答え prev に出し直し part を合わせた写し: part に在る欄が prev の欄を置き換え、無い欄は prev のまま。prev・part は書き換えない"""
    return {**copy.deepcopy(prev), **copy.deepcopy(part)}


RESUBMIT_ASK = ("前の回の返答は受け付けで拒まれた。この会話の続きで、拒まれた所だけを直して返せ。材料とリポジトリは、この会話で"
                "既に読んだ物のまま（読み直すな。拒否の理由を確かめるのに要る所だけ読め）。\n\n"
                "受け付けが拒んだ理由（字のまま）:\n\n```text\n{reason}\n```\n\n"
                "機械が合わせた前の回の答えの全体: {candidate}（Read で読める。返さない所はこの形のまま残る）\n\n"
                "返し方:\n"
                "- 返すのは前と同じ型の JSON で、直す欄だけを書く。{rules}\n"
                "- 受け付けは、合わせた後の答えの全体をもう 1 度照らす")


def resubmitting(board, name: str, prev) -> bool:
    """輪の前の周の受け付け name が拒み（prev は with: に結んだ前の周の ok を値に戻した物）、合わせた答えの控えが在るか。真なら
    頭の節は材料の代わりに write_resubmit の指示書を書き、出し直しの役（1 回目の役の会話の続き）を起こさせる。resume で輪が 1 周目
    から回り直した時は prev が空なので偽"""
    return prev is False and candidate_path(board, name).is_file()


def write_resubmit(board, name: str, file: str, rules: str) -> tuple:
    """拒まれた後の出し直しの役の指示書 board/file（file は回の番号 n の雛形。RESUBMIT_ASK に最後の拒否の文・控え candidate_path・
    役ごとの返し方 rules を差し込む）を書き、(パス, 回の番号 n) を返す。役は 1 回目の役の会話の続きで起き、材料は会話に在るので貼らない"""
    board = pathlib.Path(board)
    n = attempt(board, name)
    reasons = rejected(board, name)
    path = board / file.format(n=n)
    path.write_text(RESUBMIT_ASK.format(reason=reasons[-1] if reasons else "", candidate=candidate_path(board, name), rules=rules),
                    encoding="utf-8")
    return path, n


EMPTY_RESUBMIT = "出し直しに直した欄が無い（拒まれた所を直した欄だけを、前と同じ型で返せ）"


def _reply_object(got, what: str) -> tuple:
    if isinstance(got, dict):
        return got, ""
    if isinstance(got, str):
        return None, f"{what}が JSON として読めない（頭: {got[:200]!r}）"
    return None, f"{what}が JSON のオブジェクトでない（{type(got).__name__}）"


def resubmitted(board, name: str, reply, part, merge) -> tuple:
    """(受け付け name が照らす答えの全体, 拒否の文)。reply は 1 回目の役の返答、part は拒まれた後の出し直しの役の返答で、どちらも
    JSON に戻した値（起きなかった役は None）。part が在れば控え candidate_path の前の答えと merge(前の答え, part) で合わせ、無ければ
    reply。合わせた答えは控えに書く（次の出し直しを合わせる元）。返答が object でない・出し直しが空・控えが読めなければ (None, 訳)"""
    path = candidate_path(board, name)
    if part is None:
        got, why = _reply_object(reply, "返答")
    else:
        part, why = _reply_object(part, "出し直しの返答")
        if part is not None and not part:
            why = EMPTY_RESUBMIT
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
    jsonfile.write(path, got, indent=2)
    return got, ""
