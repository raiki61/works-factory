"""人が関所に答える行（関所の文の「答え方」）と、関所の答えの読み。層 L1（止めの語の住処 stopby のほか works の物を何も知らない）。
標準ライブラリだけ。

利用者の PATH に実行基盤の命令は無い（起動の殻 bin/works-factory が隔離した実行基盤を通して呼ぶ）ので、答えの行は殻が env に置いた頭
（ENV。家と対象を名指して殻を通す respond。後ろに `<run-id> continue|stop "<一言>"` を足せばそのまま打てる行）で組む。殻の外で回した run は
頭が無いので、打つ前に置き換える穴 HOLE で書く（直に打てない実行基盤の行は書かない）。

- head(env=None) -> str: 答えの行の頭
- line(run_id, verb, note, env=None) -> str: 打つ行 1 本（verb は continue か stop）
- GO_WORDS・REJECT・DRY_RUN_APPROVED: 関所の決めの語。通す語でない答えは止める語と読む
- decision(got) -> dict: 関所の出力の値を {decision, text} に
- taken(got, *, go, stop_reason, place, folder, asked=None) -> dict: 関所の答えの行 {go, answer, stop_reason}。関所が開かなかった
  （got が None か空の字）時は前の決め go・stop_reason をそのまま返す。開いた時は答えを folder/gates/<place>.json に書き（同じ関所の
  答えは書き直す。人が読む控え）、通す語でなければ止めの理由 human:<place> を返す。asked（関所で見せた問いの行）が在れば答えに足す
"""
import json
import os
import pathlib

import stopby

ENV = "WORKS_ANSWER_CMD"
HOLE = "<答えの殻（bin/works-factory workflow respond --cwd <対象リポジトリ>）>"
VERBS = ("continue", "stop")
GO_WORDS = ("approve", "continue")   # approve は関所の選び肢に要る語
REJECT = "reject"   # 今の works の関所の語で、stop と同じ。関所の選び肢に無いと、この答えは run の取り消しになる
DRY_RUN_APPROVED = "approved"   # 筋書きの関所がいつも返す字。決めの語の approve と読む
ANSWERS = "gates"


def head(env=None) -> str:
    got = ((os.environ if env is None else env).get(ENV) or "").strip()
    return got or HOLE


def line(run_id: str, verb: str, note: str, env=None) -> str:
    if verb not in VERBS:
        raise ValueError(f"答えの語は {VERBS} のどれか: {verb!r}")
    return f'{head(env)} {run_id} {verb} "{note}"'


def decision(got) -> dict:
    """関所の出力の値を {decision, text} に。決めの語を持つ関所は {decision, text} を返す。筋書きの関所はいつも approved の字"""
    if isinstance(got, dict) and isinstance(got.get("decision"), str):
        return {"decision": got["decision"], "text": str(got.get("text") or "")}
    if got == DRY_RUN_APPROVED:
        return {"decision": "approve", "text": ""}
    return {"decision": str(got), "text": ""}


def taken(got, *, go: bool, stop_reason: str, place: str, folder: pathlib.Path, asked=None) -> dict:
    if got is None or got == "":
        return {"go": go, "answer": None, "stop_reason": stop_reason}
    answer = decision(got)
    if asked is not None:
        answer["asked"] = [row for row in asked if isinstance(row, str)]
    kept = pathlib.Path(folder) / ANSWERS
    kept.mkdir(parents=True, exist_ok=True)
    (kept / f"{place}.json").write_text(json.dumps(answer, ensure_ascii=False) + "\n", encoding="utf-8")
    passed = answer["decision"] in GO_WORDS
    return {"go": passed, "answer": answer, "stop_reason": "" if passed else stopby.HUMAN + place}
