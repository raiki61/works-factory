"""役の節を回す共通の口（P1 計画 Task 13。C13・〔振〕10.3）。本線（graphloops）の指示書を engine と同じ描き方で描く式と、
ブロックのスクリプトの入口の約束を 1 か所に置く（前は rejudge・refix に写しが在った）。

- rejects_text:   その輪の拒否の文の全部（古い順）を、次の回の役に読ませる 1 つの文に。最後の拒否だけでは、前の回の拒否が会話に
                  残らない役は前の回の誤りを繰り返す（#345。会話を継ぐ仕組みは作らない。docs/owner-decisions.md）。役に拒否を渡す所は
                  これを読むのが決まり。外れは、会話を継ぐ輪（fresh_context: false）の頭の節が前の周の受け付けの返りから拒否の 1 件
                  だけを渡す所（前の回の拒否は会話に残る）
- write_rejects・reject_file・reject_file_or_blank・rejects_text_path・REJECT_LINE: rejects_text を置き場の rejects-<名>.md に書いて名指す（道具を持つ役。
                  名指す 1 行が REJECT_LINE）
- compose:        役に読ませる材料の組み立て: 空でない部分を空行 1 つで繋ぎ、拒否の理由のファイルが在れば 1 行目で REJECT_LINE で名指す
- with_reject:    道具ゼロの役の指示書の頭に前の拒否の文を貼る（ファイルを名指さない。裁定 R44）
- accept_round:   受け付けの回の住処（返答を読む→take→拒否を控えに積む→GIVE_UP_AFTER 回目で諦める→最後の回かを答える）。呼び手は
                  口を引き、控えの名も回数も自分で持たない。take の返りの欄 ok・reason・give_up（1 回目から諦める）・count（false なら
                  積まない）・kind（控えの行に残す）を口が読む。控え rejects-<名>.json が読めない・書けなければ、落ちずに done 真の拒否
                  （口の外の reject_file が書く rejects-<名>.md が書けない時は OSError が呼び手まで上がる）
- with_done:      拒否の控え rejects-<名>.json の唯一の書き手（accept_round が呼ぶ 1 段）。通れば done。拒否は盤面の根の控えに積み、
                  GIVE_UP_AFTER 回目の拒否で done（出し直しても直らない拒みは 1 回目で）。控えは run の間消さず resume を跨いで数える。
                  消すのは構造の目の段 A が測り直す周の eye.reset だけ
- is_last_attempt: 輪の今の回が諦める回（GIVE_UP_AFTER 回目）か。比べの式を知る所はここだけ
- rejected:       盤面の節でない受け付けの拒否の文の並び（古い順。指示書の番号と、輪が落ちた周の最後の拒否の文に使う）
- reject_rows:    控えの行 {at, reason, kind}（kind は行に在る時だけ）
- gave_up_text:   役の返答を諦めた理由の 1 行の文（回数で諦めた時と、出し直させずに諦めた時）
- given_up_reason: 盤面の節でない受け付けの出口が、控えの最後の拒否の文を引く
- attempt:        盤面の節でない受け付けの輪の今の回（控えの拒否の数 + 1）
- current_round:  輪の今の回を、控えの誤りで落ちずに読む（読めなければ accept_round と同じ done 真の拒否）。take の前に回が要る受け付けが引く
- round_outcome:  accept_round の返りの、輪の until が読む 4 つの欄 {ok, done, give_up, reason}
- _legacy_rows:   前の版の控え（reject-<名>-<k>.md・報告の <名>-rejects.json）の読み替え（resume）。rejects-<名>.json が無い時だけ読み、
                  次に積む時に rejects-<名>.json に合わせて書く。消す期限はこの関数の docstring
- last_reject(folder): 置き場の下の受け付けの最後の拒否の本文（報告の前の失敗の行が読む）
- parse_reply:    役の返答（$<役>.output の JSON の文字列）を dict に
- LANG_RULE・LANG_DEFAULT・lang_line(start): 役の文の頭に足す言語の 1 行（元 rolekit.py 67-68 行・147-150 行。言語は始めの記録の
                  lang。空なら依頼文の言語。元 board.py 96 行）。判定・計画・修正・独立の目・報告の書き手の役が同じ口で読む
- record_lang_line(path): 始めの記録のファイル path から lang_line（読めなければ既定の言語の 1 行に読めない訳を添える）
- pointed(raw, locate): 指し札の字 raw を (パス, 読めない訳) に（指し札が読めない決まりの 1 か所。planfile.pointed も同じ物）
- pointed_lang_line(raw, locate): 始めの記録の指し札の字 raw から record_lang_line（指し札が読めなくても落ちない。script が呼ぶ 1 か所）

層は L3（盤面と受け付け）。ライン・include の id・ブロックの名前を書かない（tests/test_layers.py）。
"""
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


def reject_file_or_blank(board, name: str) -> str:
    """reject_file。ただし控えが読めなければ空の字（accept_round が控えの誤りを done 真の拒否にした後の呼び手が引く。
    同じ控えを読み直して落ちない）。控えは読めて rejects-<名>.md だけ書けない時は空にせず OSError を上げる（空にすると、次の回の
    指示書が前の拒否の名指しを黙って失う）"""
    try:
        return reject_file(board, name)
    except BoardGap:
        return ""


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
    """盤面の節でない受け付け name の拒否の控え（盤面の根。[{at, reason, kind?, give_up?}]。kind は take の返りに在った行だけ）"""
    return pathlib.Path(board) / f"rejects-{safe_name(name)}.json"


def _legacy_rows(board: pathlib.Path, name: str) -> list:
    """前の版の拒否の控えの読み替え（resume）。rejects-<name>.json が無い時だけ、前の版の形を古い順に読む: reject-<name>-<k>.md
    （k の順。行 {reason}。修正の輪の受け付け）か、<name>-rejects.json（報告の受け付けの report-rejects.json。行 {node, attempt, kind,
    reason}）。どちらも無ければ空。次に with_done が積む時に rejects-<name>.json にそろえて書く（一度だけの読み替え）。前の版の md は
    はみ出しを相談に積んだ回の分も 1 枚に数えてしまう（版を跨ぐ resume の端）。
    消す期限: 2027-01-15 以降、この変更より前に始めた run が resume されなくなったら、last_reject の reject-*.md・reject-*.txt の枝と一緒に消す"""
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


def with_done(board: pathlib.Path, name: str, out: dict, *, give_up: bool = False) -> dict:
    """拒否の控えの唯一の書き手（accept_round が呼ぶ 1 段）: 通れば done。拒否は控えに積み、GIVE_UP_AFTER 回目で done（輪はそこで抜け、
    出口が諦めを扱う）。give_up 真の拒否は回数を待たずに done（出し直しても直らない拒み）。out の kind が空でない字なら行に写す。
    前の版の形の控えしか無ければ、その行を引き継いで rejects-<name>.json に書く（_legacy_rows）"""
    if out.get("ok") is True:
        return {**out, "done": True}
    path = rejects_path(board, name)
    rows = _rows(board, name)
    row = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "reason": str(out.get("reason", ""))}
    if isinstance(out.get("kind"), str) and out["kind"]:
        row["kind"] = out["kind"]
    rows.append({**row, "give_up": True} if give_up else row)
    jsonfile.write(path, rows, indent=2)
    return {**out, "done": give_up or len(rows) >= GIVE_UP_AFTER}


def is_last_attempt(attempt: int) -> bool:
    """輪の今の回 attempt（attempt が返す値）が、諦める回（GIVE_UP_AFTER 回目）か。比べの式を知る所はここだけ"""
    return attempt >= GIVE_UP_AFTER


def accept_round(board, name: str, raw, take, *, reject=None, on_give_up=None) -> dict:
    """受け付けの輪の 1 回（受け付けの回の住処。元 rolekit.main_accept）。役の返答の字 raw を読み（parse_reply）、take(reply) に通す。
    raw が None なら読まずに take(None) を呼ぶ（返答の無い回と、受けるかを呼び手が先に決めた回）。読めない返答と take の中の例外は
    reject(理由) で拒否にする（既定は {ok: False, reason}。受け付けは落ちない）。
    1 回の拒否の定義はここにだけ在り、take の返りの欄を読む: ok でなければ board/rejects-<name>.json に積み（with_done）、
    GIVE_UP_AFTER 回目で done。give_up が真なら 1 回目でも done。count が false なら控えに積まず（done は give_up が真の時だけ真）、
    kind が空でない字なら控えの行に kind として残す。諦めた時（done 真・ok 偽）は on_give_up() を呼ぶ。
    返り take の返りに done を足した物。拒否の控え rejects-<name>.json が読めない・書けなければ、落ちずに done 真の拒否（理由に
    『拒否の控えが扱えない』。on_give_up は呼ばない）。口は rejects-<name>.md を書かない（reject_file が口の後に書き、書けなければ
    OSError を呼び手まで上げる。控えは積んだ後なので、呼び手が受けずに落ちた回の出し直しは同じ拒否をもう 1 行積む）。on_give_up が落ちた時は、控えの誤りとは別の理由（『諦めた後の処理が落ちた』）の done 真の拒否"""
    reject = reject or (lambda why: {"ok": False, "reason": why})
    try:
        if raw is None:
            got = take(None)
        else:
            reply, why = parse_reply(raw)
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
                                      give_up=give_up)}
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
    """控えの拒否が GIVE_UP_AFTER 件あるか、出し直さずに諦めた拒否（give_up 真の行）が在れば、諦めた理由の 1 行（最後の拒否の文）。
    届いていなければ空"""
    rows = _reject_rows(board, name)
    at_once = any(r.get("give_up") is True for r in rows)
    if not rows or not (at_once or len(rows) >= GIVE_UP_AFTER):
        return ""
    return gave_up_text(name, len(rows), str(rows[-1].get("reason", "")), at_once=at_once)


def last_reject(folder) -> str:
    """置き場 folder（の下）の受け付けの最後の拒否の本文（元 report._accept_last_files の reason_file の本文）: 拒否の控え
    rejects-<名>.json の最後の行の文と、前の版の run の拒否の訳のファイル reject-*.md・reject-*.txt のうち一番新しい物。無い・読めなければ空。
    reject-*.md・reject-*.txt の枝は前の版の run の置き場で届き、_legacy_rows と一緒に消す"""
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
