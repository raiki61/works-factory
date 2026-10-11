"""人が関所に答える行（関所の文の「答え方」）。層 L1（works の物を何も知らない）。標準ライブラリだけ。

利用者の PATH に実行基盤の命令は無い（起動の殻 bin/works-factory が隔離した実行基盤を通して呼ぶ）ので、答えの行は殻が env に置いた頭
（ENV。殻を通して対象を名指した respond。後ろに `<run-id> continue|stop "<一言>"` を足せばそのまま打てる行）で組む。殻の外で回した run は
頭が無いので、打つ前に置き換える穴 HOLE で書く（直に打てない実行基盤の行は書かない）。
WHO_ENV に答えた者が在れば行の末尾に足す（殻は置かない。実行基盤の respond に答えた者の引数は無い）。

- head(env=None) -> str: 答えの行の頭
- line(run_id, verb, note, env=None) -> str: 打つ行 1 本（verb は continue か stop）
"""
import os

ENV = "WORKS_ANSWER_CMD"
WHO_ENV = "WORKS_ANSWER_WHO"
HOLE = "<答えの殻（bin/works-factory workflow respond --cwd <対象リポジトリ>）>"
VERBS = ("continue", "stop")


def head(env=None) -> str:
    got = ((os.environ if env is None else env).get(ENV) or "").strip()
    return got or HOLE


def line(run_id: str, verb: str, note: str, env=None) -> str:
    if verb not in VERBS:
        raise ValueError(f"答えの語は {VERBS} のどれか: {verb!r}")
    who = ((os.environ if env is None else env).get(WHO_ENV) or "").strip()
    return f'{head(env)} {run_id} {verb} "{note}"' + (f' "{who}"' if who else "")
