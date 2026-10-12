"""役の節を回す共通の口（P1 計画 Task 13。C13・〔振〕10.3）。本線（graphloops）の指示書を engine と同じ描き方で描く式と、
ブロックのスクリプトの入口の約束を 1 か所に置く（前は rejudge・refix に写しが在った）。

- with_reject:    道具ゼロの役の指示書の頭に前の拒否の文を貼る（ファイルを名指さない。裁定 R44）
- agent_def:      engine の agent_def（役の定義 agents/<役>.md）を、写しの plugin の役は pack の写し（core/agents/）から引く
- with_done:      盤面の節でない受け付け（script_io.main の finish）に done を足す。拒否は盤面の根の控え rejects-<名>.json に
                  積み、通った時か give_up_after 回目の拒否で done（控えは intake が clear_rejects で消す）
- rejected:       盤面の節でない受け付けの拒否の文の並び（古い順。指示書の番号と、輪が落ちた周の最後の拒否の文に使う）
- given_up_reason: 盤面の節でない受け付けの出口が、控えの最後の拒否の文を引く
- parse_reply:    役の返答（$<役>.output の JSON の文字列）を dict に
- LANG_RULE・LANG_DEFAULT・lang_line(start): 役の文の頭に足す言語の 1 行（元 rolekit.py 67-68 行・147-150 行。言語は始めの記録の
                  lang。空なら依頼文の言語。元 board.py 96 行）。判定・計画・修正・独立の目・報告の書き手の役が同じ口で読む
- record_lang_line(path): 始めの記録のファイル path から lang_line（読めなければ既定の言語の 1 行に読めない訳を添える）

層は L3（盤面と受け付け）。ライン・include の id・ブロックの名前を書かない（tests/test_layers.py）。
"""
import datetime
import json
import os
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように（必ず import より前）

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from engine.util import safe_name  # noqa: E402
from engine.validator import agent_def as _engine_agent_def, env_root  # noqa: E402
import promptsection  # noqa: E402


class BoardGap(Exception):
    """内部の誤り（表の欠け・配線の誤り・保存できない盤面への保存・効かない差し替え）。役に返しても直らない"""


AGENTS_PLUGIN = "convergence-loops"    # core/agents/ に写した役の定義の plugin（写しの graph の plugin。tests/test_core_copy.py）
GIVE_UP_AFTER = 3                       # 輪の max_iterations と同じ数（ブロックの試験が YAML と突き合わせる）


def agent_def(agent_type: str):
    """engine の agent_def と同じ返り（無ければ None）。本線の engine は隣に並ぶ plugin の agents/<役>.md を読むが、pack の engine の
    隣は plugin でないので、写しの plugin（AGENTS_PLUGIN）の役は、置き場 <PLUGIN>_ROOT が明示されていなければ pack の写し
    （core/agents/。COPIED_FROM）を指して引く——利用者の plugin のキャッシュに依らない（run 31: 隔離した CLAUDE_CONFIG_DIR に
    convergence-loops が無く、独立の目の支度が BoardGap で落ちた）。明示された置き場と別 plugin の役は engine の探し方のまま。
    置き場の環境変数はこの呼びの間だけ置く（後で起こす子のプロセス——対象の試験など——へ漏らさない）"""
    plugin = agent_type.rpartition(":")[0]
    key = env_root(plugin) if plugin else ""
    if plugin != AGENTS_PLUGIN or os.environ.get(key):
        return _engine_agent_def(agent_type)
    os.environ[key] = str(_CORE)
    try:
        return _engine_agent_def(agent_type)
    finally:
        os.environ.pop(key, None)


# 役の文は関所と報告に機械が字のまま載せるので、書き手に言語を縛る（元 works/.shared/core/rolekit.py 67-68 行。機械で訳さない）
LANG_RULE = ("人が読む文の欄（reason・how・what・why・異議・所見・申し出の文など、関所と報告に載る文）は {lang} で書け。"
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
    """道具ゼロの役の指示書の頭に、前の拒否の文を貼る（役はファイルを読めない。$LOOP_PREV で貼ると実行基盤が文の中の $… を
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


def _write_json(path: pathlib.Path, doc) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _gave_up_text(name: str, count: int, last: str) -> str:
    """諦めた理由の 1 行（gave_up と given_up_reason が共に使う文の正本）"""
    return f"{name} の返答が {count} 回とも受け付けで拒まれた（最後の拒否: {' '.join(str(last).split())}）"


# ---------------------------------------------------------------- 盤面の節でない受け付けの done
def rejects_path(board: pathlib.Path, name: str) -> pathlib.Path:
    """盤面の節でない受け付け name の拒否の控え（盤面の根。[{at, reason}]）"""
    return pathlib.Path(board) / f"rejects-{safe_name(name)}.json"


def with_done(board: pathlib.Path, name: str, out: dict, *, give_up_after: int = GIVE_UP_AFTER) -> dict:
    """script_io.main の finish: 通れば done。拒否は控えに積み、give_up_after 回目で done（輪はそこで抜け、出口が諦めを扱う）"""
    if out.get("ok") is True:
        return {**out, "done": True}
    path = rejects_path(board, name)
    rows = _read_json(path, [])
    rows.append({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reason": str(out.get("reason", ""))})
    _write_json(path, rows)
    return {**out, "done": len(rows) >= give_up_after}


def rejected(board: pathlib.Path, name: str) -> list:
    """盤面の節でない受け付け name の拒否の文の並び（古い順。控えが無ければ空）"""
    rows = _read_json(rejects_path(board, name), [])
    return [str(r.get("reason", "")) for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def given_up_reason(board: pathlib.Path, name: str, *, give_up_after: int = GIVE_UP_AFTER) -> str:
    """控えの拒否が give_up_after 件あれば、諦めた理由の 1 行（最後の拒否の文）。届いていなければ空"""
    got = rejected(board, name)
    return _gave_up_text(name, len(got), got[-1]) if len(got) >= give_up_after else ""


def parse_reply(raw):
    """役の返答（実行基盤が $<役>.output を JSON の文字列で渡す）を dict に。読めなければ (None, 理由)。文は script_io.main と同じ"""
    try:
        reply = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as e:
        return None, f"返答が JSON として読めない: {e}（頭: {str(raw)[:200]!r}）"
    if not isinstance(reply, dict):
        return None, f"返答が JSON のオブジェクトでない（{type(reply).__name__}）"
    return reply, ""
