"""役の節を回す共通の口（P1 計画 Task 13。C13・〔振〕10.3）。本線（graphloops）の指示書を engine と同じ描き方で描く式と、
ブロックのスクリプトの入口の約束を 1 か所に置く（前は rejudge・refix に写しが在った）。

- with_reject:    道具ゼロの役の指示書の頭に前の拒否の文を貼る（ファイルを名指さない。裁定 R44）
- agent_def:      engine の agent_def（利用者が入れた plugin の役の定義 agents/<役>.md。無ければ None）
- with_done:      盤面の節でない受け付け（script_io.main の finish）に done を足す。拒否は盤面の根の控え rejects-<名>.json に
                  積み、通った時か give_up_after 回目の拒否で done（出し直しても直らない拒みは 1 回目で。控えは intake が
                  clear_rejects で消す）
- rejected:       盤面の節でない受け付けの拒否の文の並び（古い順。指示書の番号と、輪が落ちた周の最後の拒否の文に使う）
- given_up_reason: 盤面の節でない受け付けの出口が、控えの最後の拒否の文を引く
- attempt:        盤面の節でない受け付けの輪の今の回（控えの拒否の数 + 1）
- last_reject(folder): 置き場の下の受け付けの最後の拒否の本文（報告の前の失敗の行が読む）
- parse_reply:    役の返答（$<役>.output の JSON の文字列）を dict に
- LANG_RULE・LANG_DEFAULT・lang_line(start): 役の文の頭に足す言語の 1 行（元 rolekit.py 67-68 行・147-150 行。言語は始めの記録の
                  lang。空なら依頼文の言語。元 board.py 96 行）。判定・計画・修正・独立の目・報告の書き手の役が同じ口で読む
- record_lang_line(path): 始めの記録のファイル path から lang_line（読めなければ既定の言語の 1 行に読めない訳を添える）

層は L3（盤面と受け付け）。ライン・include の id・ブロックの名前を書かない（tests/test_layers.py）。
"""
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
from engine.validator import agent_def  # noqa: E402,F401  （fixboard のレンズが rolekit.agent_def の名で読む）
import jsonfile  # noqa: E402
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


REJECT_HEADING = promptsection.Section("## 前の回の受け付けが拒んだ理由", source="fn:rolekit.with_reject")


def with_reject(prompt: str, reason: str) -> str:
    """道具ゼロの役の指示書の頭に、前の拒否の文を貼る（役はファイルを読めない。前の周の値の差し込みで貼ると実行基盤が文の中の $… を
    置き換え直す。裁定 R44）"""
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


def _gave_up_text(name: str, count: int, last: str, *, at_once: bool = False) -> str:
    """given_up_reason が返す諦めた理由の 1 行の文。at_once は出し直させずに諦めた時（with_done の give_up）"""
    last = " ".join(str(last).split())
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
    return _gave_up_text(name, len(rows), str(rows[-1].get("reason", "")), at_once=at_once)


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
    return " ".join(max(rows, key=lambda r: r[0])[1].split()) if rows else ""


def parse_reply(raw):
    """役の返答（実行基盤が $<役>.output を JSON の文字列で渡す）を dict に。読めなければ (None, 理由)。文は script_io.main と同じ"""
    try:
        reply = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:
        return None, f"返答が JSON として読めない: {e}（頭: {str(raw)[:200]!r}）"
    if not isinstance(reply, dict):
        return None, f"返答が JSON のオブジェクトでない（{type(reply).__name__}）"
    return reply, ""
