#!/usr/bin/env python3
"""bin/ の起動が Claude Code の認証を拾い、Archon を起こす起こし役（標準ライブラリだけ・3.9）。

順:
1. 前の段: WORKS_FACTORY_KEYCHAIN_ITEM を名指していれば、その項目を claude_auth の read_keychain で読む。取れなければ次へ進まず止まる
2. 真ん中: claude_auth の auth_env を丸ごと呼ぶ（受け継いだ認証 → CLAUDE_KEYCHAIN_SERVICE で名指した項目）。
   claude_auth の部品をここで並べ直さない
2.5. apiKeyHelper の段: 真ん中が足せなかった時、利用者の <CLAUDE_CONFIG_DIR>/settings.json（無ければ <HOME>/.claude）に
   apiKeyHelper が在れば、利用者の HOME でそれを起こして標準出力のキーを ANTHROPIC_API_KEY として子に渡す（値は表示も保存もしない。
   設定の写しは子に作らない）。在る時は後ろの段へ落ちない。失敗したら黙ってほかの段へ移らず、apiKeyHelper を名指して止まる
3. 後ろの段: 真ん中と apiKeyHelper の段が足せなかった時だけ、Claude Code 自身の保存済みのログインを読む。macOS では keychain の項目、
   ほかの OS では利用者の <CLAUDE_CONFIG_DIR>/.credentials.json（隔離の前の値。無ければ <HOME>/.claude）。
   子の CLAUDE_CONFIG_DIR は隔離した置き場のままなので（claude_auth の段 3 は隔離の下では効かない）、トークンを
   CLAUDE_CODE_OAUTH_TOKEN として子に渡す。keychain の無い OS で claude /login しただけの人はここで動く

keychain は利用者の HOME で読む（security はログイン keychain を $HOME 基準で探す）。値は標準出力・引数に出さない。

  auth_launch.py check --user-home <path> --user-config <path か空> [--for <殻の名>]
      値を読んで捨て、出どころの名だけを標準出力に 1 行。無ければ標準エラーに案内を 1 行出して 2
  auth_launch.py exec --user-home <path> --user-config <path か空> -- <実行ファイル> <引数…>
      同じ順で子の環境を組み、今のプロセスを実行ファイルに置き換える（WORKS_FACTORY_NO_AUTH=1 なら読まずに置き換える）
  auth_launch.py howto
      認証が無い時の案内の 1 行（殻が自分の言葉で止まる時に使う）
"""
import sys

sys.dont_write_bytecode = True   # python3 -I は PYTHONDONTWRITEBYTECODE を見ないので、pack に __pycache__ を作らない

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import subprocess  # noqa: E402
import unicodedata  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # -I はスクリプトのフォルダを sys.path に入れない
import claude_auth  # noqa: E402

ITEM_ENV = "WORKS_FACTORY_KEYCHAIN_ITEM"   # 前の段で名指す keychain の項目名の置き場
HOWTO = ("認証が無い。API キーで使うなら ANTHROPIC_API_KEY（ゲートウェイなら ANTHROPIC_BASE_URL も）を環境に置いて起動する"
         "（設定の env に書いたゲートウェイの値は子には運ばない）。API キーを返すコマンドを settings.json の apiKeyHelper に"
         "書いていれば、それを起こしてキーを得る。keychain にトークンの項目が既に在るなら、その項目名を %s か CLAUDE_KEYCHAIN_SERVICE に"
         "設定する（毎回付けずに済ますなら、Claude Code の設定の置き場の settings.json の env に"
         " \"%s\": \"<項目の名>\" の組を書く）。項目の名は推して試さず、"
         "macOS なら security find-generic-password -s <項目の名> で在るかを確かめる（値を出す -w は付けない）。"
         "無ければ claude にログインするか、"
         "claude setup-token で作ったトークンを CLAUDE_CODE_OAUTH_TOKEN に置く") % (ITEM_ENV, ITEM_ENV)

# 名指しで決めた時に子から外す名。Claude Code は CLAUDE_CODE_OAUTH_TOKEN より上の資格を先に使う
# （code.claude.com/docs/en/authentication の Authentication precedence）。claude_auth の INHERITED に無い FOUNDRY の旗もここで外す
ABOVE_TOKEN = tuple(claude_auth.INHERITED) + ("CLAUDE_CODE_USE_FOUNDRY",)
CREDENTIALS = ".credentials.json"   # keychain の無い OS で Claude Code が保存済みのログインを置くファイル（CLAUDE_CONFIG_DIR の下）


def user_runner(user_home):
    """security を利用者の HOME で起こす runner（claude_auth の read_keychain に渡す）"""
    def run(args, **kw):
        return subprocess.run(args, env={**os.environ, "HOME": user_home}, **kw)
    return run


def claude_code_items(user_config):
    """Claude Code 自身が keychain に認証を置く項目の名の候補（先に試す物から）。CLAUDE_CONFIG_DIR を設定した Claude Code は
    `Claude Code-credentials-<その値（NFC）の sha256 の頭 8 桁>` に置き、無ければ `Claude Code-credentials`"""
    items = []
    if user_config:
        digest = hashlib.sha256(unicodedata.normalize("NFC", user_config).encode("utf-8")).hexdigest()[:8]
        items.append("Claude Code-credentials-" + digest)
    items.append("Claude Code-credentials")
    return items


def login_token(raw):
    """Claude Code の保存済みのログインの値は JSON（claudeAiOauth.accessToken）かトークンそのもの。トークンの字を返す
    （JSON でなければ受けた値のまま。sk-ant-oat01- の検査は呼ぶ側）"""
    raw = raw.strip()
    try:
        tok = ((json.loads(raw) or {}).get("claudeAiOauth") or {}).get("accessToken") or ""
    except (ValueError, AttributeError):
        return raw
    return tok if isinstance(tok, str) else ""


def login_json_runner(runner):
    """keychain の項目の値をトークンだけに替えて返す runner（時間切れ・例外・sk-ant-oat01- の検査は claude_auth の read_keychain に任せる）"""
    def run(args, **kw):
        p = runner(args, **kw)
        return subprocess.CompletedProcess(args, getattr(p, "returncode", 0), stdout=login_token(p.stdout or ""))
    return run


def read_credentials(path):
    """(トークン, 空振りの理由)。read_keychain と同じく例外は投げず、sk-ant-oat01- で始まらない値は渡さない"""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "無い"
    except (OSError, UnicodeDecodeError) as e:
        return None, "読めない(%s)" % type(e).__name__
    tok = login_token(raw)
    if not tok.startswith(claude_auth.TOKEN_PREFIX):
        return None, "トークンが無い"
    return tok, None


def api_key_helper(config_dir):
    """利用者の settings.json の apiKeyHelper（コマンドの字）。無い・読めない・字でなければ None"""
    try:
        cmd = (json.loads((config_dir / "settings.json").read_text(encoding="utf-8")) or {}).get("apiKeyHelper")
    except (OSError, ValueError, AttributeError):
        return None
    return cmd if isinstance(cmd, str) and cmd.strip() else None


def user_helper_runner(command, home, config):
    """apiKeyHelper を利用者の HOME・設定の置き場で起こす（Claude Code と同じくシェルで）。終わるまで待つ（期限を足さない。
    止めるのは起動した人。持ち主の決め no-timeouts）。何を待っているかが分かる 1 行を標準エラーに出す（キーの値は出さない）"""
    print("auth_launch.py: apiKeyHelper のコマンドを起こしてキーを得る（終わるまで待つ）", file=sys.stderr)
    return subprocess.run(command, shell=True, capture_output=True, encoding="utf-8",
                          env={**os.environ, "HOME": home, "CLAUDE_CONFIG_DIR": config})


def run_helper(command, home, config, helper_runner):
    """(キー, 失敗の理由)。値と helper の標準エラーは理由に入れない"""
    try:
        p = helper_runner(command, home, config)
    except Exception as e:   # 起こせない
        return None, "起こせない(%s)" % type(e).__name__
    if p.returncode != 0:
        return None, "終了コード %s" % p.returncode
    key = (p.stdout or "").strip()
    return (key, None) if key else (None, "出力が空")


def resolve(env, user_home, user_config, platform=sys.platform, runner=None, helper_runner=None):
    """(子に足す認証の変数, 出どころの名, 止まる理由)。取れた時は止まる理由が None、取れない時は変数が None"""
    runner = runner or user_runner(user_home)
    named = env.get(ITEM_ENV)
    if named:
        tok, note = claude_auth.read_keychain(named, runner)
        if not tok:
            return None, "keychain の項目 " + named, "keychain の項目 %s を読めない: %s" % (named, note)
        return {"CLAUDE_CODE_OAUTH_TOKEN": tok}, "keychain の項目 %s（%s）" % (named, ITEM_ENV), None
    menv = dict(env, HOME=user_home, CLAUDE_CONFIG_DIR=user_config or str(pathlib.Path(user_home) / ".claude"))
    out, note = claude_auth.auth_env(menv, platform=platform, runner=runner)
    if claude_auth.added(note):
        got = {k: out[k] for k in claude_auth.INHERITED if claude_auth.active(k, out.get(k))}
        name = claude_auth.inherited(env)
        if name:
            return got, name, None
        return got, "keychain の項目 %s（CLAUDE_KEYCHAIN_SERVICE）" % note[len("keychain("):-1], None
    config = menv["CLAUDE_CONFIG_DIR"]
    command = api_key_helper(pathlib.Path(config))
    if command:
        key, miss = run_helper(command, user_home, config, helper_runner or user_helper_runner)
        if not key:
            return None, "apiKeyHelper", "apiKeyHelper（%s）が失敗した: %s" % (pathlib.Path(config) / "settings.json", miss)
        return {"ANTHROPIC_API_KEY": key}, "apiKeyHelper（%s）" % (pathlib.Path(config) / "settings.json"), None
    if platform == "darwin":
        for service in claude_code_items(user_config):
            tok, _ = claude_auth.read_keychain(service, login_json_runner(runner))
            if tok:
                return {"CLAUDE_CODE_OAUTH_TOKEN": tok}, "Claude Code の keychain の項目 " + service, None
        return None, None, "%s、Claude Code の keychain の項目 %s にも無い" % (note, " ".join(claude_code_items(user_config)))
    path = pathlib.Path(config) / CREDENTIALS
    tok, miss = read_credentials(path)
    if tok:
        return {"CLAUDE_CODE_OAUTH_TOKEN": tok}, "Claude Code の保存済みのログイン %s" % path, None
    return None, None, "%s、Claude Code の保存済みのログイン %s は%s" % (note, path, miss)


def child_env(env, got, named):
    """子の環境: 受けた環境（隔離した HOME・CLAUDE_CONFIG_DIR のまま）に認証の変数だけを足す。名指しで決めた時は、
    それより上に効く資格を外す（外さないと名指しが効かない）"""
    out = {k: v for k, v in env.items() if not (named and k in ABOVE_TOKEN)}
    out.update(got)
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="auth_launch.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("howto")
    for cmd in ("check", "exec"):
        p = sub.add_parser(cmd)
        p.add_argument("--user-home", required=True)
        p.add_argument("--user-config", default="")
        p.add_argument("--for", dest="caller", default="auth_launch.py")
        if cmd == "exec":
            p.add_argument("argv", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd == "howto":
        print(HOWTO)
        return 0
    if a.cmd == "exec":
        target = a.argv[1:] if a.argv[:1] == ["--"] else a.argv
        if not target:
            ap.error("exec には -- の後に実行ファイルが要る")
        if os.environ.get("WORKS_FACTORY_NO_AUTH") == "1":
            os.execve(target[0], target, dict(os.environ))
    got, name, why = resolve(os.environ, a.user_home, a.user_config)
    if got is None:
        print("%s: %s（%s）" % (a.caller, HOWTO, why), file=sys.stderr)
        return 2
    if a.cmd == "check":
        print(name)
        return 0
    os.execve(target[0], target, child_env(os.environ, got, bool(os.environ.get(ITEM_ENV))))


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):   # Windows の既定 cp1252 で日本語の出力が落ちないように
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
