"""対象のコマンドに渡す、利用者の隔離の前の HOME・XDG の控え（#492）。層 L1（works の物を何も知らない）。標準ライブラリだけ。

起動の殻（bin/_lib/isolate.py）は HOME・XDG を run の置き場へ向ける。利用者が起こす env に OPT_IN=1 を置いた時だけ、殻は隔離の前の
値を RECORD に控え、tree_run.outside_env が対象のコマンド（試験・受け入れ・TDD の試験のコマンド）の env にだけ戻す。既定は控えず、
対象のコマンドも隔離した HOME・XDG で走る: AI が書いた試験のコードを、人が差分を見る前に利用者の keychain・gh のログインに届く
環境で走らせない（運び役の決め。持ち主の決め auth-middleware・others-may-use から導いた。PR #496 のコメント）。役の Bash は
どちらの時も隔離のまま。

- record(env) -> str | None: env の OPT_IN が "1" なら NAMES の値（無い名は null）の JSON、ほかは None
- restore(env) -> None: env の CONTROL（RECORD・RAN_DIR_ENV・MARK。継いだ物）を外し、RECORD が在れば中の値に戻し（null の名は外す）、印 RAN_FILE の
  パスを MARK に置く（RAN_DIR_ENV の指す置き場。無ければ作る）。RECORD の形が違う・RAN_DIR_ENV が無ければ ValueError で、戻さない
- mark(path) -> bool: 印を置き、新しく置いたかを返す（置けなければ OSError）。起こす側（tree_run.run）が MARK を env から外し、子を
  起こす直前に呼ぶ（置けなければ起こさない。起こせなければ新しく置いた印を消す）
- opted(env) -> bool: env が RECORD を持つか（利用者が明示した run か。起動の 1 行が言う）
- ran(top) -> bool: 置き場 top に印 RAN_FILE が在るか（対象のコマンドを利用者の HOME・XDG に戻して起こした run か。報告の冒頭が言う）
"""
import json
import pathlib

OPT_IN = "WORKS_FACTORY_TARGET_USER_ENV"
RECORD = "WORKS_FACTORY_USER_ENV"
NAMES = ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME")
RAN_DIR_ENV = "WORKS_FACTORY_USER_ENV_RAN_DIR"
RAN_FILE = "user-env-ran"
MARK = "WORKS_FACTORY_USER_ENV_MARK"   # 戻した env にだけ在る、印のパス。子には渡さない
CONTROL = (RECORD, RAN_DIR_ENV, MARK)   # 工場が置く制御の変数。継いだ値は起動の殻（bin/_lib/isolate.py）と restore が外す
NOTE = "AI が書いた試験のコードを、利用者の資格に届く環境（利用者の HOME・XDG）で走らせた"


def record(env) -> str | None:
    return json.dumps({name: env.get(name) for name in NAMES}) if env.get(OPT_IN) == "1" else None


def restore(env) -> None:
    given = {name: env.pop(name, None) for name in CONTROL}
    ran_dir, raw = given[RAN_DIR_ENV], given[RECORD]
    if raw is None:
        return
    try:
        saved = json.loads(raw)
    except ValueError:
        saved = None
    if not isinstance(saved, dict) or not all(isinstance(v, (str, type(None))) for v in saved.values()):
        raise ValueError(f"{RECORD} が名から文字列か null への JSON の object でない: {raw[:200]!r}")
    if not ran_dir:
        raise ValueError(f"{RECORD} が在るのに {RAN_DIR_ENV}（印を置く run の置き場）が無い——戻せば報告が言い漏らす")
    top = pathlib.Path(ran_dir)
    top.mkdir(parents=True, exist_ok=True)
    for name, value in saved.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    env[MARK] = str(top / RAN_FILE)


def mark(path) -> bool:
    try:
        pathlib.Path(path).touch(exist_ok=False)
    except FileExistsError:
        return False
    return True


def opted(env) -> bool:
    return RECORD in env


def ran(top) -> bool:
    return top is not None and (pathlib.Path(top) / RAN_FILE).is_file()
