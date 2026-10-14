"""対象のコマンドに渡す、利用者の隔離の前の HOME・XDG の控え（#492）。層 L1（works の物を何も知らない）。標準ライブラリだけ。

起動の殻（bin/_lib/isolate.py）は HOME・XDG を run の置き場へ向ける。利用者が起こす env に OPT_IN=1 を置いた時だけ、殻は隔離の前の
値を RECORD に控え、tree_run.outside_env が対象のコマンド（試験・受け入れ・TDD の輪のコマンド）の env にだけ戻す。既定は控えず、
対象のコマンドも隔離した HOME・XDG で走る: AI が書いた試験のコードを、人が差分を見る前に利用者の keychain・gh のログインに届く
環境で走らせない（運び役の決め。持ち主の決め auth-middleware・others-may-use から導いた。PR #496 のコメント）。役の Bash は
どちらの時も隔離のまま。

- record(env) -> str | None: env の OPT_IN が "1" なら NAMES の値（無い名は null）の JSON、ほかは None
- restore(env) -> None: env の RECORD を外し、在れば中の値に戻す（null の名は外す）。形が違えば ValueError
- opted(env) -> bool: env が RECORD を持つか（対象のコマンドが利用者の HOME・XDG で走る run か）
"""
import json

OPT_IN = "WORKS_FACTORY_TARGET_USER_ENV"
RECORD = "WORKS_FACTORY_USER_ENV"
NAMES = ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME")
NOTE = "AI が書いた試験のコードを、利用者の資格に届く環境（利用者の HOME・XDG）で走らせた"


def record(env) -> str | None:
    return json.dumps({name: env.get(name) for name in NAMES}) if env.get(OPT_IN) == "1" else None


def restore(env) -> None:
    raw = env.pop(RECORD, None)
    if raw is None:
        return
    try:
        saved = json.loads(raw)
    except ValueError:
        saved = None
    if not isinstance(saved, dict) or not all(isinstance(v, (str, type(None))) for v in saved.values()):
        raise ValueError(f"{RECORD} が名から文字列か null への JSON の object でない: {raw[:200]!r}")
    for name, value in saved.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value


def opted(env) -> bool:
    return RECORD in env
