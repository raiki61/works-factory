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
2.7. 起動方法の門: 利用者が CLAUDE_BIN_PATH で起動方法（ラッパー）を置いた時（殻が --runtime で渡す）だけ、保存済みのログインの直前に、
   隔離した子の環境で `<起動方法> auth status`（JSON の authMethod）を起こして確かめる。authMethod が none 以外なら、起動方法が自分の認証を
   持つとみなし、子に何も足さずに進む（出どころは「起動方法 <パス> の認証（<authMethod>）」。claude.ai の時だけ、ラッパーが設定の置き場を
   替えている見込みの注意を添える）。終了コードが 0 でない・JSON が読めない・authMethod が無いか none の時は成り立たないので、保存済みの
   ログインへ進まず、起動方法のパス・訳・逃げ道を言って止まる（ラッパーが鍵を置けなかった時に、役が黙って既定のアカウントで走らない）。
   CLAUDE_BIN_PATH が無い道は門を通らない。email・組織名は返さず、出さない
3. 後ろの段: 真ん中と apiKeyHelper の段が足せなかった時だけ（起動方法の門を通らなかった時だけ）、Claude Code 自身の保存済みのログインを読む。macOS では keychain の項目、
   ほかの OS では利用者の <CLAUDE_CONFIG_DIR>/.credentials.json（隔離の前の値。無ければ <HOME>/.claude）。
   子の CLAUDE_CONFIG_DIR は隔離した置き場のままなので（claude_auth の段 3 は隔離の下では効かない）、トークンを
   CLAUDE_CODE_OAUTH_TOKEN として子に渡す。keychain の無い OS で claude /login しただけの人はここで動く

keychain は利用者の HOME で読む（security はログイン keychain を $HOME 基準で探す）。値は標準出力・引数に出さない。

  auth_launch.py check --user-home <path> --user-config <path か空> [--for <殻の名>] [--runtime <起動方法>]
      値を読んで捨て、出どころの名だけを標準出力に 1 行。無ければ標準エラーに案内を 1 行出して 2。
      殻は check を隔離した子の環境で起こす（役と同じ環境で起動方法を確かめる）。--runtime は利用者が CLAUDE_BIN_PATH を置いた時だけ殻が渡す
  auth_launch.py exec --user-home <path> --user-config <path か空> [--runtime <起動方法>] -- <実行ファイル> <引数…>
      同じ順で子の環境を組み、今のプロセスを実行ファイルに置き換える（WORKS_FACTORY_NO_AUTH=1 なら読まずに置き換える）
  auth_launch.py credential-export --user-home <path> --user-config <path> (--source <settings.json> | --aws <aws> [--profile <名>])
      選ばれた AWS（Bedrock・Mantle）の資格の源を、役の Claude Code が awsCredentialExport として期限の前ごとに走らせ直す包みの中身。
      殻の connection_profile が run の置き場の包み（1 行の sh）に書き、役の Claude Code が起こす。apiKeyHelper と同じ helper_settings_env で
      元の環境（隔離の前の HOME・XDG と、元の settings.json の env）を組み、--source なら元の settings.json の awsCredentialExport の
      コマンドを走るたびに読み直して sh -c に、--aws なら `aws configure export-credentials --format process` に置き換わる。
      包みのファイルにはコマンドの字も資格の出力も残らない。標準エラーに秘密を出さない
"""
import sys

sys.dont_write_bytecode = True   # python3 -I は PYTHONDONTWRITEBYTECODE を見ないので、pack に __pycache__ を作らない

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import shlex  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import unicodedata  # noqa: E402

if __package__:
    from bin._lib import claude_auth
    from lib import userenv
else:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # -I はスクリプトのフォルダを sys.path に入れない
    import claude_auth
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))
    import userenv

OAUTH = "CLAUDE_CODE_OAUTH_TOKEN"
ITEM_ENV = "WORKS_FACTORY_KEYCHAIN_ITEM"   # 前の段で名指す keychain の項目名の置き場
HOWTO = ("認証が無いか、確かめられない。API キーで使うなら ANTHROPIC_API_KEY（ゲートウェイなら ANTHROPIC_BASE_URL も）を環境に置いて起動する"
         "（設定の env に書いた接続の値——接続先・資格・proxy・証明書・alias と、選んだ Bedrock・Mantle・Vertex の公式の名——は子に運ぶ。"
         "設定の明示の資格は親の資格より勝つ。フック・権限・プラグインは運ばない）。API キーを返すコマンドを settings.json の apiKeyHelper に"
         "書いていれば、それを起こしてキーを得る。keychain にトークンの項目が既に在るなら、その項目名を %s か CLAUDE_KEYCHAIN_SERVICE に"
         "設定する（毎回付けずに済ますなら、Claude Code の設定の置き場の settings.json の env に"
         " \"%s\": \"<項目の名>\" の組を書く）。項目の名は推して試さず、"
         "macOS なら security find-generic-password -s <項目の名> で在るかを確かめる（値を出す -w は付けない）。"
         "無ければ claude にログインするか、"
         "claude setup-token で作ったトークンを CLAUDE_CODE_OAUTH_TOKEN に置く。"
         "Bedrock・Mantle・Vertex を使うなら、公式の旗（CLAUDE_CODE_USE_BEDROCK など）を環境か設定の env に置く。"
         "ラッパーを CLAUDE_BIN_PATH で渡せる") % (ITEM_ENV, ITEM_ENV)
# CLAUDE_BIN_PATH を置いた時の逃げ道の住処。起動方法の門で止める 1 行は HOWTO（理由）の形で、理由がこれを持つ
RUNTIME_ESCAPES = ("逃げ道は、ラッパーに鍵を環境変数で置かせる・CLAUDE_CODE_OAUTH_TOKEN を置く・"
                   "CLAUDE_BIN_PATH を外して PATH の claude を使う（CLAUDE_BIN_PATH を置いた時は保存済みのログインへ切り替えない）")
CLAUDE_AI_NOTE = ("注意: ラッパーが CLAUDE_CONFIG_DIR か HOME を替えている見込み。役は利用者の設定（hooks・permissions・plugins）で走りうる。"
                  "鍵を環境変数に置く形にする")

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


# 直接 API / gateway の接続・資格と alias。仕様: code.claude.com/docs/en/env-vars
# 設定の env から運ぶのは公式の名の許可リストだけ（下の AWS_ENV・VERTEX_ENV と、選ばれた provider のときの DIRECT_ENV。
# ANTHROPIC_API_KEY・ANTHROPIC_AUTH_TOKEN は provider が選ばれた時は運ばず、direct の資格へ黙って替えない）。
# 任意 helper の依存 env・フック・権限・プラグインは運ばない。
DIRECT_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_CUSTOM_HEADERS",
              "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "NODE_EXTRA_CA_CERTS", "CLAUDE_CODE_CERT_STORE",
              "CLAUDE_CODE_CLIENT_CERT", "CLAUDE_CODE_CLIENT_KEY", "CLAUDE_CODE_CLIENT_KEY_PASSPHRASE")
DIRECT_CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")   # provider が選ばれた時に設定からは運ばない direct の資格
ALIAS_ENV = tuple("ANTHROPIC_DEFAULT_%s_MODEL" % name for name in ("OPUS", "SONNET", "HAIKU", "FABLE"))
# provider の旗の一覧は claude_auth.FLAGS の 1 か所。Foundry の旗は受け継ぐ認証（INHERITED）に無いのでここで足す
PROVIDER_FLAGS = (*claude_auth.FLAGS, "CLAUDE_CODE_USE_FOUNDRY")
# 選ばれた provider ごとの公式の名（旗の名そのものも一員）。出典: code.claude.com/docs/en/amazon-bedrock・google-vertex-ai。推して増やさない
AWS_ENV = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_MANTLE", "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_PROFILE", "AWS_CONFIG_FILE",
           "AWS_SHARED_CREDENTIALS_FILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_BEARER_TOKEN_BEDROCK",
           "ANTHROPIC_BEDROCK_BASE_URL", "ANTHROPIC_BEDROCK_MANTLE_BASE_URL", "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION",
           "ANTHROPIC_BEDROCK_REGION_PREFIX", "ANTHROPIC_BEDROCK_SERVICE_TIER", "CLAUDE_CODE_SKIP_BEDROCK_AUTH",
           "CLAUDE_CODE_SKIP_MANTLE_AUTH")
VERTEX_ENV = ("CLAUDE_CODE_USE_VERTEX", "CLOUD_ML_REGION", "ANTHROPIC_VERTEX_PROJECT_ID", "ANTHROPIC_VERTEX_BASE_URL",
              "CLAUDE_CODE_SKIP_VERTEX_AUTH", "GOOGLE_APPLICATION_CREDENTIALS")
VERTEX_REGION_PREFIX = "VERTEX_REGION_CLAUDE_"   # VERTEX_ENV には、頭がこれの名（モデルごとの地域）も入る
CLOUD_ENV = (AWS_ENV, VERTEX_ENV)   # 設定と親の両方から運ぶ表の組（place.PROVIDER_ENV は別の考えなので、名を分けた）
# Foundry は親が明示した公式の値だけを運ぶ（親の env の道だけ。設定の env の Foundry は運ばず止める）。
FOUNDRY_ENV = ("CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_FOUNDRY_API_KEY", "ANTHROPIC_FOUNDRY_AUTH_TOKEN",
               "ANTHROPIC_FOUNDRY_BASE_URL", "ANTHROPIC_FOUNDRY_RESOURCE")
# 隔離した HOME の下では見つからないので、設定の道では絶対パスで指すことを求める資格のファイルの名
FILE_ENV = ("GOOGLE_APPLICATION_CREDENTIALS", "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE")
# HOME に頼らない AWS の資格の名。どれかが在れば、既定の aws の包みは置かない
AWS_HOME_FREE = ("AWS_ACCESS_KEY_ID", "AWS_BEARER_TOKEN_BEDROCK", "CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_MANTLE_AUTH",
                 "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_WEB_IDENTITY_TOKEN_FILE")
AWS_EXPORT = "aws-credential-export"   # run の置き場（write_fence の --own の top の下）に書く包みの名
AWS_EXPORT_SETTING = "awsCredentialExport"   # 公式の設定の鍵。セッションの始めと期限の前ごとに、Claude Code 自身がこのコマンドを走らせる
REFRESH_SETTINGS = ("awsAuthRefresh", "gcpAuthRefresh")   # 対話の更新のコマンド。工場では走らせない
PARENT = "親の環境"   # 旗の出どころの名（設定の env の時は、旗を持っていたファイルのパス）
MANAGED_NOTE = ("%s は Claude Code 自身が管理者の設定（%s）から走らせる（工場は止めない。remote や MDM が policy を配る機械では、"
                "Claude Code は最上位の出どころだけを使い、このファイルは使わない）")
USER_REFRESH_NOTE = "利用者の設定の %s（%s）は工場では走らせない。run の途中で資格が切れたら手で更新してから resume する"
LEFT_OUT_NOTE = ("設定の env の %s は運ばない（provider の旗を親の環境で立てた時は、親の環境の provider の名だけを運ぶ）。"
                 "役に効かせるには、親の環境に置くか、旗を設定の env で立てる")
NO_AWS_NOTE = "aws の CLI が無いので、~/.aws の SSO のキャッシュは役に届かない。SSO の profile なら aws の CLI を PATH に置く"
NO_ADC_NOTE = ("Vertex の ADC ファイル（application_default_credentials.json）が無く、GOOGLE_APPLICATION_CREDENTIALS も"
               " CLAUDE_CODE_SKIP_VERTEX_AUTH も無い。HOME に頼らない資格（GCE のメタデータなど）でなければ、役で認証に落ちる")
NO_PROFILE_NOTE = ("AWS_PROFILE（%s）を名指しているが、殻に見える資格のファイル（本当の HOME の ~/.aws・AWS_CONFIG_FILE・"
                   "AWS_SHARED_CREDENTIALS_FILE）も利用者の awsCredentialExport も無い。MDM・管理者が配る awsCredentialExport は殻から見えない"
                   "（殻は MDM を読まない）。それも無ければ役で認証に落ちる。渡す道は、~/.aws に置く・AWS_CONFIG_FILE と"
                   " AWS_SHARED_CREDENTIALS_FILE を絶対パスで置く・利用者の settings.json に awsCredentialExport を置く")


def flags_on(values):
    """values に立っている provider の旗の名（値が「使わない」の物は除く）"""
    return [k for k in PROVIDER_FLAGS if values.get(k) and values[k] not in claude_auth.OFF]


def table_of(flag):
    """旗を含む表（立っている旗の表は、その旗を含む表で引く）"""
    return next(t for t in (*CLOUD_ENV, FOUNDRY_ENV) if flag in t)


def table_names(table, values):
    """values の名のうち table の名（VERTEX_ENV は頭が VERTEX_REGION_CLAUDE_ の名も）"""
    return [k for k in values if k in table or (table is VERTEX_ENV and k.startswith(VERTEX_REGION_PREFIX))]


def settings_env(config_dir, managed_dir):
    """(env の表, 名 → その値を持っていたファイル)。利用者の settings.json の env に、管理者のファイルの env を managed_files の順に
    重ねた物。読めない・object でない時は ValueError（値は言わない）"""
    path = pathlib.Path(config_dir) / "settings.json"
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        body = {}
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError("%s の接続設定を読めない(%s)" % (path, type(error).__name__)) from None
    if not isinstance(body, dict) or not isinstance(body.get("env", {}), dict):
        raise ValueError("%s の接続設定が object でない" % path)
    values = dict(body.get("env", {}))
    origin = {k: path for k in values}
    for source in managed_files(managed_dir):   # 既存 helper と同じ管理者ファイルの優先順
        try:
            managed = json.loads(source.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError):
            continue
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ValueError("%s の接続設定を読めない(%s)" % (source, type(error).__name__)) from None
        if not isinstance(managed, dict) or not isinstance(managed.get("env", {}), dict):
            raise ValueError("%s の接続設定が object でない" % source)
        for k, v in managed.get("env", {}).items():
            values[k] = v
            origin[k] = source
    return values, origin


def connection_profile(config_dir, env, managed_dir=None, place=None):
    """隔離前の選ばれた user settings から必要値だけを返す。(profile, 告知の 1 行の字か空)。
    旗の出どころは、親の env に provider の旗（PROVIDER_FLAGS）が立っていれば親の env、立っていなければ設定の env（利用者の
    settings.json に管理者のファイルの env を managed_files の順に重ねた物）。provider が選ばれていれば、立っている旗の表（Bedrock・Mantle の
    AWS_ENV、Vertex の VERTEX_ENV、親の道だけ Foundry の FOUNDRY_ENV）の名を出どころから運ぶ。設定の道は DIRECT_ENV の接続の名
    （direct の資格を除く）も運び、alias は inline settings の env に置く。設定の Foundry と、相対パスの資格ファイルは運ばず ValueError で止める
    （名とファイルだけを言い、値は言わない）。HOME 基準の資格は cloud_credentials が運ぶか名指す。
    親の道（旗を親の env で立てた時）は設定の env の接続値（direct の資格を除く DIRECT_ENV の名・alias）を運ばず、あれば名を告知で言う。
    provider が無ければ direct の資格と alias を運び、設定に明示の資格があれば親の資格を外し、その資格の名と出どころのファイルを告知で言う。
    戻り値の秘密は env だけに運び、ファイル・inline settings に置かない（資格を出すコマンドの包みも、コマンドの字も出力も持たない）。
    helper は既存の道のまま。place(名, 中身) は run の置き場に包みを書いてパスを返す口（launcher が渡す）"""
    empty = {"settings": {}, "env": {}, "drop": []}
    if env.get(ITEM_ENV):
        return empty, ""
    flags, unread = flags_on(env), ""
    try:
        values, origin = settings_env(config_dir, managed_dir)
    except ValueError as error:
        if not flags and claude_auth.inherited(env):
            return empty, ""
        if not flags:
            raise
        unread, values, origin = str(error), {}, {}   # 親の道は BASE が settings.json を読まなかったので止めず、告知で名指す
    if flags:
        profile, note = provider_profile(config_dir, env, managed_dir, place, flags, env, {}, True, unread)
        left = [k for k in (*DIRECT_ENV, *ALIAS_ENV) if k in values and k not in DIRECT_CREDENTIALS and k not in profile["env"]]
        if left:   # 親の環境で旗を立てた道は、設定の env の接続値を運ばない。黙って役が別のモデル・接続先で走らないよう名指す
            note = "。".join(filter(None, [note, LEFT_OUT_NOTE % "・".join(left)]))
        return profile, note
    flags = flags_on(values)
    if flags:
        return provider_profile(config_dir, env, managed_dir, place, flags, values, origin, False, "")
    path = pathlib.Path(config_dir) / "settings.json"
    kept = {k: values[k] for k in (*DIRECT_ENV, *ALIAS_ENV) if k in values}
    if not all(isinstance(v, str) for v in kept.values()):
        raise ValueError("%s の接続 env が文字列でない" % path)
    explicit = any(kept.get(k) for k in DIRECT_CREDENTIALS)
    drop = list(ABOVE_TOKEN) + ["CLAUDE_API_KEY", "ANTHROPIC_CUSTOM_HEADERS",
                               "CLAUDE_CODE_API_KEY_HELPER_FD", "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR",
                               "CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST"] if explicit else []
    process = {k: v for k, v in kept.items() if k not in ALIAS_ENV}
    settings = {"env": {k: v for k, v in kept.items() if k in ALIAS_ENV}}
    notice = ""
    if explicit:   # 親の資格を外すことと、その資格を置いたファイルを言う（名とパスだけ。値は言わない）
        named = [k for k in DIRECT_CREDENTIALS if kept.get(k)]
        notice = "設定の env が直接の資格 %s を明示しているので、親の env の資格を外す（出どころ: %s）" % (
            "・".join(named), "・".join(dict.fromkeys(str(origin[k]) for k in named)))
    return {"settings": settings, "env": process, "drop": drop}, notice


def provider_profile(config_dir, env, managed_dir, place, flags, source, origin, parent, unread):
    """選ばれた provider（flags）の接続を運ぶ。source は旗の出どころの表（親の env か設定の env）、origin は設定の道で名 → ファイル、
    unread は親の道で設定を読めなかった理由（空なら読めた）。運ぶか、渡せない物（設定の Foundry・相対パスの資格ファイル）だけ
    ValueError で止めて名指す"""
    process, aliases, notes = {}, {}, []
    if parent:
        where = PARENT
        for flag in flags:
            process.update({k: source[k] for k in table_names(table_of(flag), source)})
    else:
        where = "・".join(dict.fromkeys(str(origin[f]) for f in flags))
        if "CLAUDE_CODE_USE_FOUNDRY" in flags:
            raise ValueError("%s が CLAUDE_CODE_USE_FOUNDRY を立てている。Foundry は設定の env からは運べない（値は出さない）。"
                             "親の環境に置いて起動する" % origin["CLAUDE_CODE_USE_FOUNDRY"])
        names = [k for flag in flags for k in table_names(table_of(flag), source)]
        names += [k for k in DIRECT_ENV if k in source and k not in DIRECT_CREDENTIALS]
        for k in dict.fromkeys(names):
            if not isinstance(source[k], str):
                raise ValueError("%s の接続 env %s が文字列でない" % (origin[k], k))
            if k in FILE_ENV and not os.path.isabs(source[k]):
                raise ValueError("%s の %s が絶対パスでない（相対パスの資格ファイルは、役の隔離した置き場から引けない。"
                                 "絶対パスで指す。値は出さない）" % (origin[k], k))
            process[k] = source[k]
        for k in ALIAS_ENV:
            if k in source:
                if not isinstance(source[k], str):
                    raise ValueError("%s の接続 env %s が文字列でない" % (origin[k], k))
                aliases[k] = source[k]
    export, key_notes, bad = credential_keys(config_dir, managed_dir)
    if bad and not parent:
        raise ValueError(bad)
    if unread or bad:   # 親の道は BASE が settings.json を読まなかったので、読めない時は止めず「無い」として進む
        notes.append("%s。設定にある資格の鍵は「無い」として進む" % (unread or bad))
    command = cloud_credentials(env, process, flags, export, pathlib.Path(config_dir) / "settings.json", config_dir, place, notes)
    settings = {"env": aliases} if aliases else {}
    if command:
        settings[AWS_EXPORT_SETTING] = command
    head = "選ばれた provider を運ぶ: %s（出どころ: %s）" % ("・".join(flags), where)
    return {"settings": settings, "env": process, "drop": []}, "。".join([head, *key_notes, *notes])


def credential_keys(config_dir, managed_dir):
    """(利用者の settings.json の awsCredentialExport のコマンドか None, 告知の列, 読めない理由か None)。資格の設定の鍵
    （awsCredentialExport・awsAuthRefresh・gcpAuthRefresh）は旗の出どころに関わらず、ここで同じに読む。管理者の物（管理者が先で最上位の
    出どころだけ。find_helper）は Claude Code 自身が走らせるので、殻は運ばず止めず、名指すだけ。利用者の awsAuthRefresh・gcpAuthRefresh は
    対話の更新のコマンドなので運ばず止めず、名指す。利用者の awsCredentialExport は資格の源そのものなので、呼び手が包んで運ぶ"""
    config = pathlib.Path(config_dir)
    user, notes, export = config / "settings.json", [], None
    for key in (AWS_EXPORT_SETTING, *REFRESH_SETTINGS):
        command, source, why = find_helper(config, managed_dir, key)
        if why:
            return export, notes, why
        if command and source != user:
            notes.append(MANAGED_NOTE % (key, source))
        elif command and key in REFRESH_SETTINGS:
            notes.append(USER_REFRESH_NOTE % (key, source))
        if key == AWS_EXPORT_SETTING:
            export, why = settings_helper(user, key=key)
            if why:
                return None, notes, why
    return export, notes, None


def cloud_credentials(user, process, flags, export, source, config, place, notes):
    """HOME 基準の資格の扱い（親と設定の両方の道が同じに呼ぶ）。見る値は、親の env（user）に写した値（process）を重ねた物。
    隔離した HOME では ~/.aws・~/.config/gcloud が見えないので、パスを渡すか、本当の HOME で資格を出す包みを置く。
    戻り値は settings の awsCredentialExport に置く字（shlex でくくった包みのパス。置かなければ None）。資格の有無では止めない
    （ValueError を出さない。包みが要るのに置き口 place が無い呼び出しの誤りだけ RuntimeError）。
    渡せない物は notes に名指しで足す（値は言わない）。パスだけを置き、ファイルの中身は読まない"""
    seen = {**user, **process}
    home = user.get("HOME") or ""
    command = None
    if any(flag in AWS_ENV for flag in flags):
        files = {}
        for name, rel in (("AWS_CONFIG_FILE", ".aws/config"), ("AWS_SHARED_CREDENTIALS_FILE", ".aws/credentials")):
            path = pathlib.Path(home) / rel
            if home and os.path.isabs(home) and path.is_file():
                files[name] = str(path)
        placed = [name for name in files if not seen.get(name)]   # 値が既に在れば触らない
        process.update({name: files[name] for name in placed})
        if placed:
            notes.append("本当の HOME の %s のパスを渡した（中身は読まない）" % "・".join(placed))
        free = any(seen.get(k) and seen[k] not in claude_auth.OFF for k in AWS_HOME_FREE)
        profile = seen.get("AWS_PROFILE") or ""
        wrap = None
        if export:   # 利用者の資格の源を、既定の aws の包みより優先して包む
            wrap = {"source": str(source)}
        elif not free and (profile or files):
            aws = shutil.which("aws", path=user.get("PATH", ""))
            if aws and os.path.isabs(aws):
                wrap = {"aws": aws, "profile": profile}
            else:
                notes.append(NO_AWS_NOTE)
        if wrap:
            if place is None:
                raise RuntimeError("包みの置き口 place が無い")
            command = shlex.quote(place(AWS_EXPORT, aws_export_body(user, config, **wrap)))
            notes.append("awsCredentialExport を置いた（%s）" % ("利用者の設定 %s の包み" % source if export else "既定の aws の包み"))
        if profile and not export and not free and not files and not seen.get("AWS_CONFIG_FILE") and not seen.get("AWS_SHARED_CREDENTIALS_FILE"):
            notes.append(NO_PROFILE_NOTE % profile)
    if "CLAUDE_CODE_USE_VERTEX" in flags and not seen.get("GOOGLE_APPLICATION_CREDENTIALS") \
            and not (seen.get("CLAUDE_CODE_SKIP_VERTEX_AUTH") and seen["CLAUDE_CODE_SKIP_VERTEX_AUTH"] not in claude_auth.OFF):
        gcloud = seen.get("CLOUDSDK_CONFIG")
        gcloud = pathlib.Path(gcloud if gcloud and os.path.isabs(gcloud) else pathlib.Path(home) / ".config" / "gcloud")
        adc = gcloud / "application_default_credentials.json"
        if home and os.path.isabs(home) and adc.is_file():
            process["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc)
            notes.append("ADC ファイルのパスを GOOGLE_APPLICATION_CREDENTIALS として渡した（中身は読まない）")
        else:
            notes.append(NO_ADC_NOTE)
    return command


def aws_export_body(user, config, source="", aws="", profile=""):
    """AWS の資格を本当の HOME で出す包みの中身（sh の 1 行）。元の環境を組む答えは credential-export が apiKeyHelper と同じ
    helper_settings_env に持つので、ここは戻す名も値も組まない。隔離前の HOME・XDG_* のパスだけを env で渡す（資格もコマンドの字も持たない）。
    source なら利用者の settings.json の awsCredentialExport、そうでなければ aws の絶対パスと profile"""
    argv = ["env", "%s=%s" % (userenv.RECORD, userenv.record(user)), sys.executable, "-I", "-B",
            str(pathlib.Path(__file__).resolve()), "credential-export", "--user-home", user["HOME"], "--user-config", str(config)]
    argv += ["--source", source] if source else ["--aws", aws, *(["--profile", profile] if profile else [])]
    return "#!/bin/sh\nexec " + shlex.join(argv) + "\n"


def profile_env(env, profile):
    out = {k: v for k, v in env.items() if k not in profile["drop"]}
    out.update(profile["env"])
    return out


def settings_helper(path, denied_is_absent=False, key="apiKeyHelper"):
    """(key のコマンドの字か None, 使えない理由か None)。key は読む設定の鍵（既定は apiKeyHelper。awsCredentialExport なども同じ読み口）。
    ファイルが無い・キーが無い・空の字は「無い」。
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
    cmd = body.get(key)
    if cmd is None:
        return None, None
    if not isinstance(cmd, str):
        return None, "%s の %s が文字列でない" % (path, key)
    return (cmd, None) if cmd.strip() else (None, None)


def managed_files(managed_dir):
    """既存の管理者ファイル探索の1か所。apiKeyHelper と接続設定で順序を分けない。managed_dir が None なら管理者のファイルは読まない"""
    if managed_dir is None:
        return []
    files = [managed_dir / "managed-settings.json"]
    try:
        files += sorted(f for f in (managed_dir / "managed-settings.d").iterdir()
                        if f.suffix == ".json" and not f.name.startswith(".") and f.is_file())
    except OSError:
        pass
    return files


def find_helper(config_dir, managed_dir, key="apiKeyHelper"):
    """(コマンド, 出どころのパス, 使えない理由)。会社の設定（managed-settings.json の後に managed-settings.d/*.json を名前順。
    単一の値は後が勝つ）に key（読む設定の鍵。既定は apiKeyHelper）が在ればそれ、無ければ利用者の <CLAUDE_CONFIG_DIR>/settings.json。
    Claude Code と同じく、最上位の出どころの物だけを採る。対象のリポジトリの .claude/settings.json は対象の持ち物なので読まない"""
    found = (None, None)
    for f in managed_files(managed_dir):
        cmd, why = settings_helper(f, denied_is_absent=True, key=key)
        if why:
            return None, f, why
        if cmd:
            found = (cmd, f)
    if found[0]:
        return found[0], found[1], None
    user = config_dir / "settings.json"
    cmd, why = settings_helper(user, key=key)
    return cmd, user, why


def helper_base_env(environ):
    """apiKeyHelper を起こす環境の元: 起動の殻が控えた隔離の前の HOME・XDG_*（userenv.RECORD）が在れば、それに戻す
    （exec も check も隔離した子の環境で走るので、殻を通る時は控えが在る。殻を通らない単独の check などは控えが無く、そのまま）"""
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


def helper_settings_env(environ, home, config, source="", sources=None, what="apiKeyHelper"):
    """helper 子だけに元設定の env を渡す（what は読む設定の鍵の名で、止める文が言う。apiKeyHelper も awsCredentialExport の包みも同じ答え）。
    管理者の分割設定は既存の探索順に重ね、AI の環境は変えない。"""
    out = helper_base_env(environ)
    if sources is not None and pathlib.Path(source) not in sources:
        raise ValueError("%s の元設定 %s が無い" % (what, source))
    for path in sources if sources is not None else ([pathlib.Path(source)] if source else []):
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, PermissionError) as error:
            if sources is not None and str(path) != source:
                continue   # 選んだ helper の元ファイル自体が消えた時は別経路へ落ちない
            raise ValueError("%s の元設定 %s を読めない(%s)" % (what, path, type(error).__name__)) from None
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ValueError("%s の元設定 %s を読めない(%s)" % (what, path, type(error).__name__)) from None
        values = body.get("env", {}) if isinstance(body, dict) else None
        if not isinstance(values, dict) or not all(isinstance(v, str) for v in values.values()):
            raise ValueError("%s の元設定 %s の env が文字列の表でない" % (what, path))
        out.update({k: v for k, v in values.items() if k not in (*userenv.CONTROL, "ARCHON_HOME")})
    out.update(HOME=home, CLAUDE_CONFIG_DIR=config)
    return out


def user_command(args, env, what, shell=False, stdin=None):
    """利用者の認証の命令を起こす共通の口。終わるまで待つ（期限を足さない。止めるのは起動した人。持ち主の決め no-timeouts）。
    何を待っているかが分かる 1 行を標準エラーに出し（値は出さない）、標準エラーは捕まえずに端末へ流し（命令の問いが見えないまま待ち続けない）、
    標準出力だけを捕まえる（キーや JSON は標準出力にしか出ない）。stdin を渡さなければ呼び手の標準入力を継ぐ"""
    print("auth_launch.py: %s（終わるまで待つ）" % what, file=sys.stderr)
    return subprocess.run(args, shell=shell, stdin=stdin, stdout=subprocess.PIPE, encoding="utf-8", env=env)


def user_helper_runner(command, home, config, source="", sources=None):
    """apiKeyHelper を利用者の HOME・XDG・設定の置き場で起こす（Claude Code と同じくシェルで。起こし方は user_command）"""
    return user_command(command, helper_settings_env(os.environ, home, config, source, sources),
                        "apiKeyHelper%s のコマンドを起こしてキーを得る" % (source and "（%s）" % source), shell=True)


def runtime_auth(runtime, env):
    """(authMethod か None, 成り立たない訳か None)。`<runtime> auth status`（公式。JSON の authMethod）を env（隔離した子の環境）で
    起こす。標準入力は渡さない（問いに答える人が居ない）。終了コードが 0 でない・JSON が読めない・authMethod が無いか none の時は
    成り立たない。email・組織名は返さず、訳にも入れない"""
    try:
        p = user_command([runtime, "auth", "status"], env, "起動方法 %s の認証を確かめる（auth status）" % runtime,
                         stdin=subprocess.DEVNULL)
    except (OSError, UnicodeDecodeError) as e:
        return None, "起こせない(%s)" % type(e).__name__
    if p.returncode != 0:
        return None, "auth status が終了コード %s で終わった" % p.returncode
    try:
        body = json.loads(p.stdout)
    except ValueError:
        return None, "auth status の出力が JSON として読めない"
    method = body.get("authMethod") if isinstance(body, dict) else None
    if not isinstance(method, str) or not method:
        return None, "auth status に authMethod が無い"
    if method == "none":
        return None, "auth status が authMethod none（認証が無い）を返した"
    return method, None


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


def resolve(env, user_home, user_config, platform=sys.platform, runner=None, helper_runner=None, managed_dir=None, fetch=True,
            runtime=None, probe=runtime_auth):
    """(子に足す認証の変数, 出どころの名, 止まる理由)。取れた時は止まる理由が None、取れない時は変数が None。
    fetch が偽（check）なら apiKeyHelper は起こさず、出どころの名とパスだけを返す（変数は空）。起こすのは exec の 1 回だけ。
    runtime は利用者が CLAUDE_BIN_PATH で置いた起動方法（無ければ None）。在れば、保存済みのログインの直前に probe(runtime, env)（試験で
    差し替える口。既定は runtime_auth）で起動方法の認証を確かめる門を置く。成り立てば子に何も足さず、成り立たなければ保存済みの
    ログインへ進まずに止める。名指し・受け継いだ認証・CLAUDE_KEYCHAIN_SERVICE・apiKeyHelper・環境の OAuth の段は、今のまま門より上に効く"""
    runner = runner or user_runner(user_home)
    named = env.get(ITEM_ENV)
    if named:
        tok, note = claude_auth.read_keychain(named, runner)
        if not tok:
            return None, "keychain の項目 " + named, "keychain の項目 %s を読めない: %s" % (named, note)
        return {"CLAUDE_CODE_OAUTH_TOKEN": tok}, "keychain の項目 %s（%s）" % (named, ITEM_ENV), None
    if (env.get("CLAUDE_CODE_USE_FOUNDRY") and env["CLAUDE_CODE_USE_FOUNDRY"] not in claude_auth.OFF
            and not any(claude_auth.active(k, env.get(k)) for k in claude_auth.FLAGS)):
        return {k: env[k] for k in FOUNDRY_ENV if k in env}, "CLAUDE_CODE_USE_FOUNDRY", None
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
    managed = managed_dir or default_managed_dir(platform)
    command, source, bad = find_helper(pathlib.Path(config), managed)
    if bad:
        return None, "apiKeyHelper", "apiKeyHelper の設定が使えない: %s" % bad
    if command and not fetch:
        return {}, "apiKeyHelper（%s）" % source, None
    if command:
        sources = None if source == pathlib.Path(config) / "settings.json" else managed_files(managed)
        run = helper_runner or (lambda c, h, d: user_helper_runner(c, h, d, str(source), sources))
        key, miss = run_helper(command, user_home, config, run)
        if not key:
            return None, "apiKeyHelper", "apiKeyHelper（%s）が失敗した: %s" % (source, miss)
        return {"ANTHROPIC_API_KEY": key}, "apiKeyHelper（%s）" % source, None
    if claude_auth.added(note):   # 設定の無い OAuth トークンだけの認証
        return {k: out[k] for k in claude_auth.INHERITED if claude_auth.active(k, out.get(k))}, OAUTH, None
    if runtime:   # 起動方法を置いた時は、保存済みのログインへ切り替えない（ラッパーが鍵を置けなかった時に既定のアカウントで走らない）
        method, miss = probe(runtime, env)
        source = "起動方法 %s" % runtime
        if not method:
            return None, source, "%s の認証が成り立たない: %s。%s" % (source, miss, RUNTIME_ESCAPES)
        return {}, "%s の認証（%s）" % (source, "claude.ai。" + CLAUDE_AI_NOTE if method == "claude.ai" else method), None
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


def credential_export(home, config, source="", aws="", profile=""):
    """awsCredentialExport の包み（aws_export_body）の子。env は apiKeyHelper と同じ helper_settings_env で組む（隔離前の HOME・XDG_* を
    控えから戻し、元ファイルの env と CLAUDE_CONFIG_DIR を重ねる。AI の環境は変えない）。source なら元の settings.json から走るたびに
    awsCredentialExport のコマンドの字を読み直して `/bin/sh -c` に、そうでなければ `aws configure export-credentials --format process`
    に置き換わる（標準出力が資格）。失敗は標準エラーに 1 行（秘密・コマンドの字は出さない）で 2"""
    try:
        env = helper_settings_env(os.environ, home, config, source, what=AWS_EXPORT_SETTING)
        if source:
            command, why = settings_helper(pathlib.Path(source), key=AWS_EXPORT_SETTING)
            if not command:
                raise ValueError(why or "%s に %s が無い" % (source, AWS_EXPORT_SETTING))
            argv = ["/bin/sh", "-c", command]
        else:
            argv = [aws, "configure", "export-credentials", "--format", "process", *(["--profile", profile] if profile else [])]
        os.execve(argv[0], argv, env)
    except ValueError as error:
        print("auth_launch.py credential-export: %s" % error, file=sys.stderr)
    except OSError as error:
        print("auth_launch.py credential-export: 起こせない(%s)" % type(error).__name__, file=sys.stderr)
    return 2


def child_env(env, got, named):
    """子の環境: 受けた環境（隔離した HOME・CLAUDE_CONFIG_DIR のまま）に認証の変数だけを足す。名指しで決めた時は、
    それより上に効く資格を外す（外さないと名指しが効かない）"""
    out = {k: v for k, v in env.items() if not (named and k in ABOVE_TOKEN)}
    out.update(got)
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="auth_launch.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("credential-export")
    p.add_argument("--user-home", required=True)
    p.add_argument("--user-config", required=True)
    p.add_argument("--source", default="")
    p.add_argument("--aws", default="")
    p.add_argument("--profile", default="")
    for cmd in ("check", "exec"):
        p = sub.add_parser(cmd)
        p.add_argument("--user-home", required=True)
        p.add_argument("--user-config", default="")
        p.add_argument("--for", dest="caller", default="auth_launch.py")
        p.add_argument("--runtime", default="")   # 利用者が CLAUDE_BIN_PATH で置いた起動方法（殻が、置かれた時だけ渡す）。在れば auth status で認証を確かめる
        p.add_argument("--managed-dir", default="")   # 会社が配る設定の置き場を替える（環境変数 MANAGED_DIR_ENV より先に効く）。殻は渡さない
        if cmd == "exec":
            p.add_argument("argv", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    if a.cmd == "credential-export":
        if bool(a.source) == bool(a.aws):
            ap.error("credential-export には --source か --aws の片方だけが要る")
        return credential_export(a.user_home, a.user_config, a.source, a.aws, a.profile)
    if a.cmd == "exec":
        target = a.argv[1:] if a.argv[:1] == ["--"] else a.argv
        if not target:
            ap.error("exec には -- の後に実行ファイルが要る")
        if os.environ.get("WORKS_FACTORY_NO_AUTH") == "1":
            os.execve(target[0], target, dict(os.environ))
    managed = a.managed_dir or os.environ.get(MANAGED_DIR_ENV, "")
    got, name, why = resolve(os.environ, a.user_home, a.user_config,
                             managed_dir=pathlib.Path(managed) if managed else None,
                             fetch=a.cmd == "exec", runtime=a.runtime or None)
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
