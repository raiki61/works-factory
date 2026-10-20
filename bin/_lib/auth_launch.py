#!/usr/bin/env python3
"""bin/ の起動が Claude Code の認証を拾い、Archon を起こす起こし役（標準ライブラリだけ・3.9）。

順:
1. 前の段: WORKS_FACTORY_KEYCHAIN_ITEM を名指していれば、その項目を claude_auth の read_keychain で読む。取れなければ次へ進まず止まる
2. 真ん中: claude_auth の auth_env を丸ごと呼ぶ（受け継いだ認証 → CLAUDE_KEYCHAIN_SERVICE で名指した項目）。
   claude_auth の部品をここで並べ直さない
2.5. apiKeyHelper の段: 真ん中が足せなかった時（親の環境の CLAUDE_CODE_OAUTH_TOKEN だけが認証の時も。Claude Code 自身の優先順は
   apiKeyHelper が上）、会社が配る設定（OS ごとの managed-settings.json の後に managed-settings.d/*.json を名前順）か、無ければ
   利用者の <CLAUDE_CONFIG_DIR>/settings.json（無ければ <HOME>/.claude）に apiKeyHelper が在れば、利用者の HOME・XDG で
   それを起こして標準出力のキーを ANTHROPIC_API_KEY として子に渡す（値は表示も保存もしない。標準エラーは端末へ流す。
   設定の写しは子に作らない。期限は付けない）。在る時は後ろの段へ落ちない。失敗したら黙ってほかの段へ移らず、apiKeyHelper を
   名指して止まる。設定が JSON として壊れている・apiKeyHelper が文字列でない時も、壊れたファイルを名指して止まる。
   OS が読ませない会社の設定のファイルは、Claude Code と同じく無いものとして進む。
   MDM・remote（claude.ai の server-managed settings）と対象のリポジトリの .claude/settings.json は読まない。
   置き場は環境変数 WORKS_FACTORY_MANAGED_DIR で替えられる（無ければ上の OS ごとの置き場。既定の道は変わらない）。
   起こすのは exec の 1 回だけ。check は起こさず、出どころの名とパスだけを返す（使い捨てのキーや指紋の確かめを求める helper のため）。
   check の標準出力のパイプと exec の環境でキーを渡す道は採らない（殻はトークンを読まない・出さない。launcher.py の頭）
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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))   # 隔離の前の HOME・XDG の控えの名は lib/userenv.py が持つ
import userenv  # noqa: E402

OAUTH = "CLAUDE_CODE_OAUTH_TOKEN"
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


MANAGED_DIR_ENV = "WORKS_FACTORY_MANAGED_DIR"   # 在れば、会社が配る設定の置き場をここに替える（無い時の道は default_managed_dir のまま。試験の子の環境が空のフォルダへ向ける）


def default_managed_dir(platform=sys.platform):
    """会社が配る設定のファイルの置き場（https://code.claude.com/docs/en/managed-settings）。MDM（構成プロファイル・レジストリ）は読まない"""
    if platform == "darwin":
        return pathlib.Path("/Library/Application Support/ClaudeCode")
    if platform == "win32":
        return pathlib.Path("C:\\Program Files\\ClaudeCode")
    return pathlib.Path("/etc/claude-code")


def settings_helper(path, denied_is_absent=False):
    """(apiKeyHelper のコマンドの字か None, 使えない理由か None)。ファイルが無い・キーが無い・空の字は「無い」。
    読めない・JSON として壊れている・object でない・字でない値は、黙って「無い」にせず理由を返す。ただし denied_is_absent なら、
    OS が読ませない（PermissionError）ファイルは無いものとして進む（会社の設定を読めない時の Claude Code の振る舞い。
    https://code.claude.com/docs/en/managed-settings の「If the operating system denied the read ...」）"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except PermissionError:
        if denied_is_absent:
            return None, None
        return None, "%s を読めない(PermissionError)" % path
    except (OSError, UnicodeDecodeError) as e:
        return None, "%s を読めない(%s)" % (path, type(e).__name__)
    try:
        body = json.loads(text)
    except ValueError:
        return None, "%s が JSON として壊れている" % path
    if not isinstance(body, dict):
        return None, "%s が JSON の object でない" % path
    cmd = body.get("apiKeyHelper")
    if cmd is None:
        return None, None
    if not isinstance(cmd, str):
        return None, "%s の apiKeyHelper が文字列でない" % path
    return (cmd, None) if cmd.strip() else (None, None)


def find_helper(config_dir, managed_dir):
    """(コマンド, 出どころのパス, 使えない理由)。会社の設定（managed-settings.json の後に managed-settings.d/*.json を名前順。
    単一の値は後が勝つ）に apiKeyHelper が在ればそれ、無ければ利用者の <CLAUDE_CONFIG_DIR>/settings.json。Claude Code と同じく、
    最上位の出どころの物だけを採る。対象のリポジトリの .claude/settings.json は対象の持ち物なので読まない"""
    files = [managed_dir / "managed-settings.json"]
    try:
        files += sorted(f for f in (managed_dir / "managed-settings.d").iterdir()
                        if f.suffix == ".json" and not f.name.startswith(".") and f.is_file())
    except OSError:
        pass
    found = (None, None)
    for f in files:
        cmd, why = settings_helper(f, denied_is_absent=True)
        if why:
            return None, f, why
        if cmd:
            found = (cmd, f)
    if found[0]:
        return found[0], found[1], None
    user = config_dir / "settings.json"
    cmd, why = settings_helper(user)
    return cmd, user, why


def helper_base_env(environ):
    """apiKeyHelper を起こす環境の元: 起動の殻が控えた隔離の前の HOME・XDG_*（userenv.RECORD）が在れば、それに戻す
    （exec は隔離した子の環境で走る。check は利用者の環境なので控えが無く、そのまま）"""
    out = dict(environ)
    raw = out.pop(userenv.RECORD, None)
    try:
        saved = json.loads(raw) if raw else None
    except ValueError:
        saved = None
    if isinstance(saved, dict):
        for name in userenv.NAMES:
            if saved.get(name) is None:
                out.pop(name, None)
            elif isinstance(saved[name], str):
                out[name] = saved[name]
    return out


def user_helper_runner(command, home, config, source=""):
    """apiKeyHelper を利用者の HOME・XDG・設定の置き場で起こす（Claude Code と同じくシェルで）。終わるまで待つ（期限を足さない。
    止めるのは起動した人。持ち主の決め no-timeouts）。標準エラーは捕まえずに端末へ流す（helper の問いが見えないまま待ち続けない。
    キーは標準出力にしか出ない）。何を待っているかが分かる 1 行を標準エラーに出す（キーの値は出さない）"""
    print("auth_launch.py: apiKeyHelper%s のコマンドを起こしてキーを得る（終わるまで待つ）" % (source and "（%s）" % source),
          file=sys.stderr)
    return subprocess.run(command, shell=True, stdout=subprocess.PIPE, encoding="utf-8",
                          env={**helper_base_env(os.environ), "HOME": home, "CLAUDE_CONFIG_DIR": config})


def run_helper(command, home, config, helper_runner):
    """(キー, 失敗の理由)。値は理由に入れない"""
    try:
        p = helper_runner(command, home, config)
    except Exception as e:   # 起こせない
        return None, "起こせない(%s)" % type(e).__name__
    if p.returncode != 0:
        return None, "終了コード %s" % p.returncode
    key = (p.stdout or "").strip()
    return (key, None) if key else (None, "出力が空")


def resolve(env, user_home, user_config, platform=sys.platform, runner=None, helper_runner=None, managed_dir=None, fetch=True):
    """(子に足す認証の変数, 出どころの名, 止まる理由)。取れた時は止まる理由が None、取れない時は変数が None。
    fetch が偽（check）なら apiKeyHelper は起こさず、出どころの名とパスだけを返す（変数は空）。起こすのは exec の 1 回だけ"""
    runner = runner or user_runner(user_home)
    named = env.get(ITEM_ENV)
    if named:
        tok, note = claude_auth.read_keychain(named, runner)
        if not tok:
            return None, "keychain の項目 " + named, "keychain の項目 %s を読めない: %s" % (named, note)
        return {"CLAUDE_CODE_OAUTH_TOKEN": tok}, "keychain の項目 %s（%s）" % (named, ITEM_ENV), None
    menv = dict(env, HOME=user_home, CLAUDE_CONFIG_DIR=user_config or str(pathlib.Path(user_home) / ".claude"))
    out, note = claude_auth.auth_env(menv, platform=platform, runner=runner)
    # Claude Code 自身の優先順は apiKeyHelper が CLAUDE_CODE_OAUTH_TOKEN より上。親の環境に CLAUDE_CODE_OAUTH_TOKEN しか認証が無い時は、
    # apiKeyHelper の設定が在れば先に効かせる。設定が無ければ環境のトークンを採る（CLAUDE_KEYCHAIN_SERVICE も名指していても、
    # auth_env は受け継いだ認証を先に採るので keychain の項目は読まない）。ほかの受け継いだ認証・名指し・CLAUDE_KEYCHAIN_SERVICE
    # の項目だけが認証の時は、今のまま apiKeyHelper より上
    oauth_only = claude_auth.inherited(menv) == OAUTH and not any(
        claude_auth.active(k, menv.get(k)) for k in claude_auth.INHERITED if k != OAUTH)
    if claude_auth.added(note) and not oauth_only:
        got = {k: out[k] for k in claude_auth.INHERITED if claude_auth.active(k, out.get(k))}
        name = claude_auth.inherited(env)
        if name:
            return got, name, None
        return got, "keychain の項目 %s（CLAUDE_KEYCHAIN_SERVICE）" % note[len("keychain("):-1], None
    config = menv["CLAUDE_CONFIG_DIR"]
    command, source, bad = find_helper(pathlib.Path(config), managed_dir or default_managed_dir(platform))
    if bad:
        return None, "apiKeyHelper", "apiKeyHelper の設定が使えない: %s" % bad
    if command and not fetch:
        return {}, "apiKeyHelper（%s）" % source, None
    if command:
        run = helper_runner or (lambda c, h, d: user_helper_runner(c, h, d, str(source)))
        key, miss = run_helper(command, user_home, config, run)
        if not key:
            return None, "apiKeyHelper", "apiKeyHelper（%s）が失敗した: %s" % (source, miss)
        return {"ANTHROPIC_API_KEY": key}, "apiKeyHelper（%s）" % source, None
    if claude_auth.added(note):   # 設定の無い OAuth トークンだけの認証
        return {k: out[k] for k in claude_auth.INHERITED if claude_auth.active(k, out.get(k))}, OAUTH, None
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
        p.add_argument("--managed-dir", default="")   # 会社が配る設定の置き場を替える（環境変数 MANAGED_DIR_ENV より先に効く）。殻は渡さない
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
    managed = a.managed_dir or os.environ.get(MANAGED_DIR_ENV, "")
    got, name, why = resolve(os.environ, a.user_home, a.user_config,
                             managed_dir=pathlib.Path(managed) if managed else None,
                             fetch=a.cmd == "exec")
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
