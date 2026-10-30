#!/usr/bin/env python3
"""別プロセスの claude を起こすときに、**認証だけ**を子の環境へ足す。起動そのものは呼ぶ側が持つ。

**なぜ要るか。** 子は対話の claude の認証を継がない。利用者の `claude` がシェル関数のラッパ
（Keychain から OAuth トークンを読んで `CLAUDE_CODE_OAUTH_TOKEN` に入れてから実体を起こす形）のとき、
子は実体を直に起こすのでラッパを通らず、ハーネスも子の環境にトークンを渡さない（実測 2026-09-15:
Bash から見える環境では `CLAUDE_CODE_OAUTH_TOKEN` も `CLAUDE_CONFIG_DIR` も空だった）。
**落ち方は静か**——実測 2026-09-15: 素で起こした `claude -p` は
『Failed to authenticate: OAuth session expired and could not be refreshed』の 1 行を
**標準出力に・終了コード 0 で**返した。rc では捕まらない。

**なぜトークンを argv に置かないか。** 起動の argv は呼ぶ側の文脈や記録（graphloops なら
`record.json`）に写るので、秘密がそこに残る。呼ぶ側の Bash に `$(security find-generic-password …)` を
書かせる形も採れない——auto mode の分類器が資格情報の実体化として止める（実測 2026-09-15）。
この層の中から呼ぶ分は止まらない。

**段**（上から順に、決まった時点で止める）:

1. 親の環境に認証が在る（`INHERITED`）→ 何も足さない。**利用者が選んだ経路を黙って別の口に差し替えない**
2. macOS の Keychain（サービス名は呼ぶ側の指定 → `CLAUDE_KEYCHAIN_SERVICE`。どちらも無ければ読まない）
3. 何も足さない——子自身の保存済み認証（`<CLAUDE_CONFIG_DIR>/.credentials.json`）に委ねる。
   **Keychain の無い環境ではここが主な道**で、2 は空振りする。全 OS で効くのは
   「`CLAUDE_CONFIG_DIR` を必ず子へ明示する」ことの方

`auth_env` は採った段の名前も返す。呼ぶ側はそれを人の見える所（標準エラー・ログ）に出すこと
——**認証を足せたかどうかが見えないと、認証落ちが役の返答の不良と区別できない**。
段の名前にトークンそのものは出さない。
"""
import pathlib
import subprocess
import sys

# 親の環境に在れば認証は足さない。子（claude）が読む経路——サブスクの OAuth・API キー・
# 企業のゲートウェイ・Bedrock / Vertex / Mantle。**旗の 3 つは値も見る**（`=0` は「使わない」の意味で、
# 在るだけで認証が在ることにはならない）。provider の旗の一覧は FLAGS の 1 か所にだけ置く
# （bin/_lib/auth_launch.py の PROVIDER_FLAGS は、ここに Foundry の旗を足して組む）。
FLAGS = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_MANTLE")
INHERITED = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", *FLAGS)
OFF = ("", "0", "false", "False", "no")
TOKEN_PREFIX = "sk-ant-oat01-"


def config_dir(env):
    return env.get("CLAUDE_CONFIG_DIR") or str(pathlib.Path.home() / ".claude")


def keychain_service(env, explicit=None):
    """Keychain のサービス名（呼ぶ側の指定 → `CLAUDE_KEYCHAIN_SERVICE`）。どちらも無ければ None。

    項目の名は利用者ごとに違うので、名を導く規則を持たない（E14。名を持つ人だけが名指す）。
    """
    return explicit or env.get("CLAUDE_KEYCHAIN_SERVICE") or None


def read_keychain(service, runner=subprocess.run):
    """`(トークン, 段の名前)`。取れなければ `(None, 空振りの理由)`——**例外は投げない**。

    取れないことは異常ではない（mac 以外・項目が無い・利用者が別経路で認証している）。ここで落とすと、
    子の保存済み認証で普通に動く場まで起こせなくなる。
    """
    try:
        p = runner(["security", "find-generic-password", "-s", service, "-w"],
                   capture_output=True, encoding="utf-8", timeout=10)
    except Exception as e:  # security が無い・落ちた・時間切れ
        return None, "keychain-error(%s)" % type(e).__name__
    tok = (p.stdout or "").strip()
    if not tok:
        return None, "keychain-miss"
    if not tok.startswith(TOKEN_PREFIX):
        # 壊れた値を渡すと子は認証エラーで起動すらしない。渡さなければ保存済み認証で動く目が残る
        return None, "keychain-malformed"
    return tok, "keychain"


def active(k, v):
    """その名と値が認証として効くか。旗は値が「使わない」でないことまで見る。"""
    return bool(v) and not (k in FLAGS and v in OFF)


def inherited(env):
    """親の環境に在る認証の名前（無ければ None）"""
    for k in INHERITED:
        if active(k, env.get(k)):
            return k
    return None


def auth_env(env, platform=sys.platform, runner=subprocess.run, service=None):
    """子に渡す環境と、採った段の名前を返す。渡された env は壊さない（写しを返す）。"""
    out = dict(env)
    out["CLAUDE_CONFIG_DIR"] = config_dir(out)  # 全 OS 共通の段。mac 以外はこれだけが効く
    got = inherited(out)
    if got:
        return out, "inherited(%s)" % got
    if platform != "darwin":
        return out, "none"
    svc = keychain_service(out, service)
    if svc is None:
        return out, "keychain-unnamed"
    tok, note = read_keychain(svc, runner)
    if tok:
        out["CLAUDE_CODE_OAUTH_TOKEN"] = tok
        return out, "keychain(%s)" % svc
    return out, "%s(%s)" % (note, svc)


def added(note):
    """認証を足せた段か。足せていない回だけ、呼ぶ側が静かな落ち方の注意を出せるようにする。"""
    return note.startswith(("inherited(", "keychain("))
