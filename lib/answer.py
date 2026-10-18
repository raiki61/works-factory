"""人が関所に答える行（関所の文の「答え方」）と、関所の答えの読み。層 L1（止めの語の住処 stopby のほか works の物を何も知らない）。
標準ライブラリだけ。

利用者の PATH に実行基盤の命令は無い（起動の殻 bin/works-factory が隔離した実行基盤を通して呼ぶ）ので、答えの行は殻が env に置いた頭
（ENV。家と対象を名指して殻を通す respond。後ろに `<run-id> continue|stop "<一言>"` を足せばそのまま打てる行）で組む。殻の外で回した run は
頭が無いので、打つ前に置き換える穴 HOLE で書く（直に打てない実行基盤の行は書かない）。

- head(env=None) -> str: 答えの行の頭
- line(run_id, verb, note, env=None) -> str: 打つ行 1 本（verb は continue か stop）
- resume(run_id, env=None) -> str: 落ちた run を別のアカウントで続ける行 1 本（答えの行の頭の respond を resume に替え、殻が認証に読む
  keychain の項目名 KEYCHAIN_ENV を前に置く。項目名は穴のまま）
- GO_WORDS・STOP_WORDS・REJECT: 関所の決めの語。通す語でない答えは止める語と読む
- decision(got) -> dict: 関所の出力の値を {decision, text} に
- taken(got, *, go, stop_reason, place, folder, asked=(), pushed=None, final=False) -> dict: 関所の答えの行 {go, answer, stop_reason}。関所が開かなかった
  （got が None か空の字）時は前の決め go・stop_reason をそのまま返す。ただし無人の run が推しで進んだ（pushed が
  {decision, text, PUSHED} の dict）時は、それを答えとして開いた時と同じく書き、答えに欄 PUSHED（採った推しの並び）を残す。開いた時の答えは {decision, text, asked}（asked は関所で見せた
  問いの行。項目を持たない関所は []。読み手は asked の無い答えを別に読まない）。答えを folder/gates/<place>.json に書き（同じ関所の
  答えは書き直す。人が読む控え）、通す語でなければ止めの理由 human:<place> を返す。止める答えの一言が空なら既定の文（STOP_NOTE・
  呼び手が final を真で渡した最後の承認は FINAL_STOP_NOTE。元 works/darkfactory/lib/line_edge.py 98・104 行）を一言にする（報告の止めの理由が空にならない）
- PUSHED: 推しで進んだ答えの欄。人の答えは持たず、欄が在ることが答えの出どころが推しである印（答えた者の名ではない。
  持ち主の決め answerer-unnamed）
- by_push(row) -> bool: 答えか、答えを写した行が欄 PUSHED を持つ（推しで進んだ）
- origin(row) -> dict: 答えを別の形の行に写す時に足す欄（推しなら {PUSHED: …}、人の答えなら {}）。写しが印を落とさない
- PUSHED_NOTE・said(row) -> str: 答えを写した行 {note, …} の一言を役に渡す形。推しで進んだ行は一言の前に PUSHED_NOTE の行を置く
  （役が人の答えと読み分ける。一言が見出しで始まっても崩さない）。推しの印を修正役への行に付けるのはここだけ（判定の推しを
  無人の run が答えに採った台帳の問いの行も、gatemarks.returned_lines がこれで印を付ける）
"""
import json
import os
import pathlib
import sys

_HERE = str(pathlib.Path(__file__).resolve().parent)
if _HERE not in sys.path:   # 殻（bin/_lib/launcher.py）は from lib import answer で読み、置き場を sys.path に持たない
    sys.path.append(_HERE)
import stopby  # noqa: E402

ENV = "WORKS_ANSWER_CMD"
HOLE = "<答えの殻（bin/works-factory workflow respond --cwd <対象リポジトリ>）>"
RESPOND, RESUME = " workflow respond ", " workflow resume "
KEYCHAIN_ENV = "WORKS_FACTORY_KEYCHAIN_ITEM"   # 殻が認証に読む keychain の項目名の置き場（bin/_lib/auth_launch.py の ITEM_ENV）
KEYCHAIN_HOLE = "<keychainの項目名>"
VERBS = ("continue", "stop")
GO_WORDS = ("approve", VERBS[0])   # approve は関所の選び肢に要る語
REJECT = "reject"   # 今の works の関所の語で、stop と同じ。関所の選び肢に無いと、実行基盤がこの答えを拒む
STOP_WORDS = (VERBS[1], REJECT)
ANSWERS = "gates"
STOP_NOTE = "承認ノードで止めた"
FINAL_STOP_NOTE = "最後の承認ノードで止めた"
PUSHED = "pushed"
PUSHED_NOTE = "（無人の run が採った推し。人の答えではない）"


def head(env=None) -> str:
    got = ((os.environ if env is None else env).get(ENV) or "").strip()
    return got or HOLE


def line(run_id: str, verb: str, note: str, env=None) -> str:
    if verb not in VERBS:
        raise ValueError(f"答えの語は {VERBS} のどれか: {verb!r}")
    return f'{head(env)} {run_id} {verb} "{note}"'


def resume(run_id: str, env=None) -> str:
    return f"{KEYCHAIN_ENV}={KEYCHAIN_HOLE} {head(env).replace(RESPOND, RESUME, 1)} {run_id}"


def decision(got) -> dict:
    """関所の出力の値を {decision, text} に。関所（選び肢の待ち）は {decision, text} を返す"""
    if isinstance(got, dict) and isinstance(got.get("decision"), str):
        return {"decision": got["decision"], "text": str(got.get("text") or "")}
    return {"decision": str(got), "text": ""}


def taken(got, *, go: bool, stop_reason: str, place: str, folder: pathlib.Path, asked=(), pushed=None, final: bool = False) -> dict:
    opened = got is not None and got != ""
    if not opened and not isinstance(pushed, dict):
        return {"go": go, "answer": None, "stop_reason": stop_reason}
    answer = decision(got if opened else pushed)
    passed = answer["decision"] in GO_WORDS
    if not passed and not answer["text"].strip():
        answer["text"] = FINAL_STOP_NOTE if final else STOP_NOTE
    answer["asked"] = [row for row in asked or () if isinstance(row, str)]
    if not opened:
        answer[PUSHED] = list(pushed[PUSHED])
    kept = pathlib.Path(folder) / ANSWERS
    kept.mkdir(parents=True, exist_ok=True)
    (kept / f"{place}.json").write_text(json.dumps(answer, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"go": passed, "answer": answer, "stop_reason": "" if passed else stopby.HUMAN + place}


def by_push(row) -> bool:
    return isinstance(row, dict) and PUSHED in row


def origin(row) -> dict:
    return {PUSHED: row[PUSHED]} if by_push(row) else {}


def said(row) -> str:
    return f"{PUSHED_NOTE}\n{row['note']}" if by_push(row) else row["note"]
