"""run の中で利用者の gh のログインを継ぐ口を書く（bin/ の起動が、HOME・XDG_* を隔離する前の値で呼ぶ）。

隔離した HOME・XDG_CONFIG_HOME の下の gh は、利用者の gh の設定（hosts.yml）も macOS の keychain のトークン（gh の既定の置き場。
keychain は HOME から探すので、隔離した HOME では login の keychain が探す先に無い。2026-10-08 に security list-keychains で確かめた）
も見えない。run の中の並行 PR の確かめ（写しの parallel-pr.py）はそれで毎回 gh の失敗になり、1 周の run が round_limit で終わった
（実の利用者の run 97fd532f）。持ち主の決定（2026-10-08）: run の中の gh は利用者の gh を継ぐ（本流の review-graph は利用者の環境の
まま gh を打つ）。そこで <dir>/gh に、PATH の上の本物の gh を利用者の HOME と gh の設定の置き場（config_dir）で起こすだけの sh の口を
書き、起動が Archon の子の PATH の頭に <dir> を置く（script のノードはこの口を打つ。役の claude には包みが読むだけの口 no-post-bin/ をさらに前に置く）。口が持つのはパスと名だけで、トークンの値は写さない・出さない・置かない。
利用者の gh がログインしていなければ gh の言葉と終了コードのまま（run の中は今どおり人待ち）。

利用者の gh が包み（PATH から自分だけを抜いて本物の gh を探す物など）でも口と呼び合わないよう、口は本物を探した利用者の PATH
（口の置き場と読むだけの口を除く）に戻してから起こす。2026-11-16 の run 2f08b32f・5196f102 では、口が子の PATH の頭のまま包みを
起こしたので、包みが口を本物と取り違え、口と包みが互いを起こし続けて gh auth token が 2 時間余り CPU を使った。ほかの道の
呼び返し（包みが env に控えた PATH を使うなど）も、口は自分の先の gh に印（ACTIVE）を立て、印の在る env で起きたら訳の 1 行で
止まる（回り続ける子を、期限でなく形で止める。持ち主の決め no-timeouts）。

環境変数だけで gh にログインする利用者（GH_TOKEN など。Linux・CI に多い）のために、起動は子の環境から 4 つのトークンの名を
外したまま（TOKENS。RELAY の拾う名から出す）、値を gh も他の道具も自動では読まない名（RELAY の渡しの名）で子に渡す（#131 のコメントの運び役の決め。持ち主の決め others-may-use・auth-middleware・roles-read-only-gh から導いた。#132）。読むのは
この口だけで、本物の gh を起こす時だけ gh の名へ戻し、渡しの名は本物の gh に見せない。子に gh の名が既に在れば（Archon がノードに
トークンを渡した時）上書きしない。役は自分の環境の渡しの名を読めるので、これも事故の柵で、堅い境ではない。

AI の役が打つ gh は、起動（launcher.py）が書く書き込みの柵の包みが役の PATH でこの口の前に置く読むだけの口 works-gh（no-post-bin/。今の works では包み
.shared/core/adapter.py の 5 が置いた）で、口の先の本物の gh がこの口。これは事故の柵で、堅い境ではない（役は利用者と同じ人で同じ
keychain を持つ）。

- config_dir(env) -> str: gh の設定の置き場（GH_CONFIG_DIR、無ければ $XDG_CONFIG_HOME/gh、無ければ $HOME/.config/gh。gh 自身の決め方）
- find_gh(path, skip) -> str|None: PATH の上の最初の gh（skip の置き場——口自身と読むだけの口——は飛ばす）
- relay(env) -> dict: env の gh のトークンを渡しの名に移した物（RELAY の行ごとに、gh 自身の先後で最初の空でない値。無い行は載せない）
- write(dir, path, home, config) -> str|None: 口（本物の gh を利用者の HOME・設定の置き場・本物を探した PATH で起こす）を <dir>/<中身の sha256 の頭 16 桁>/gh に書いてそのパスを返す。中身ごとに置き場を
  分けるので、同じ家から並べた起動・入れ子の起動（隔離した HOME を継いだ殻）が、走っている run の口を書き換えない。gh が無ければ
  何も書かずに None（前の口は消さない。別の run が使っているかもしれない）
"""
import hashlib
import os
import pathlib
import shlex

NO_POST_BIN = pathlib.Path(__file__).resolve().parent / "no-post-bin"
SHIM = "gh"
# (渡しの名, 起動が拾う名を gh の先後で)。口は頭の名へ戻す。gh は GH_TOKEN・GITHUB_TOKEN を github.com と *.ghe.com にだけ、
# GH_ENTERPRISE_TOKEN・GITHUB_ENTERPRISE_TOKEN をほかのホスト（GHES）にだけ使うので、行を分ける。渡しの名は _TOKEN で終える
# （Archon の記録の伏せ字は名の末尾で値を拾う）
RELAY = (("WORKS_FACTORY_HOST_GH_TOKEN", ("GH_TOKEN", "GITHUB_TOKEN")),
         ("WORKS_FACTORY_HOST_GH_ENTERPRISE_TOKEN", ("GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")))
# 起動が子の環境から外す gh のトークンの名。外す名と渡す名を 1 つの表から出す
TOKENS = tuple(s for _, sources in RELAY for s in sources)
# 口が自分の先の gh（利用者の gh とその子）に立てる印。印の在る env で口が起きたら、先の gh が口を呼び返している
ACTIVE = "WORKS_FACTORY_GH_SHIM_ACTIVE"   # 渡しの名（WORKS_FACTORY_HOST_）と頭を分ける
CALLED_BACK = ("works-factory: run の中の gh の口が、自分の先の gh から呼び返された。回り続けないよう止める"
               "（利用者の gh の包みが、PATH や env に残った口を本物の gh と取り違えている見込み。包みが本物を探す道を見直す）")


def config_dir(env) -> str:
    if env.get("GH_CONFIG_DIR"):
        return env["GH_CONFIG_DIR"]
    if env.get("XDG_CONFIG_HOME"):
        return os.path.join(env["XDG_CONFIG_HOME"], "gh")
    return os.path.join(env.get("HOME", ""), ".config", "gh")


def find_gh(path: str, skip=()):
    skipped = {os.path.realpath(str(s)) for s in skip}
    for d in path.split(os.pathsep):
        if not d or not os.path.isabs(d) or os.path.realpath(d) in skipped:
            continue
        c = os.path.join(d, SHIM)
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def relay(env) -> dict:
    out = {}
    for name, sources in RELAY:
        value = next((env[s] for s in sources if env.get(s)), None)
        if value:
            out[name] = value
    return out


def _under(p: str, top: pathlib.Path) -> bool:
    """PATH の置き場 p が口の置き場 top の下か（前に書いた口自身を本物と取り違えない）"""
    if not p or not os.path.isabs(p):
        return False
    real, root = os.path.realpath(p), os.path.realpath(str(top))
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def write(dir_, path: str, home: str, config: str):
    top = pathlib.Path(dir_)
    skip = [NO_POST_BIN, *(p for p in path.split(os.pathsep) if _under(p, top))]
    real = find_gh(path, skip)
    if real is None:
        return None
    skipped = {os.path.realpath(str(s)) for s in skip}
    user_path = os.pathsep.join(p for p in path.split(os.pathsep) if not (p and os.path.isabs(p) and os.path.realpath(p) in skipped))
    body = ("#!/bin/sh\n"
            "# works-factory の起動（bin/_lib/hostgh.py）が書いた口: 利用者の gh を、利用者の HOME（macOS の keychain は HOME から\n"
            "# 探す）・gh の設定の置き場・本物を探した PATH で起こす。持つのはパスと名だけ（起動が渡しの名で渡したトークンは、ここで gh の名へ戻す）\n"
            f'if [ -n "${{{ACTIVE}:-}}" ]; then\n'
            f"  echo {shlex.quote(CALLED_BACK)} >&2\n"
            "  exit 1\n"
            "fi\n"
            f"{ACTIVE}=1\n"
            f"HOME={shlex.quote(home)}\n"
            f"GH_CONFIG_DIR={shlex.quote(config)}\n"
            f"PATH={shlex.quote(user_path)}\n"
            f"export {ACTIVE} HOME GH_CONFIG_DIR PATH\n"
            + "".join(f'if [ -z "${{{gh}:-}}" ] && [ -n "${{{name}:-}}" ]; then {gh}=${name}; export {gh}; fi\n'
                      for name, (gh, _) in RELAY)
            + f"unset {' '.join(name for name, _ in RELAY)}\n"
            f'exec {shlex.quote(real)} "$@"\n')
    return place_shim(top, SHIM, body)


def place_shim(top: pathlib.Path, name: str, body: str) -> str:
    """殻を top/<中身の hash>/name に原子的に置き、そのパスを返す。中身で置き場を分けるので、同じ家で違う物を指す起動が並んでも
    互いの殻を上書きしない"""
    d = top / hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    shim = d / name
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{name}.{os.getpid()}.tmp"
    tmp.write_text(body, encoding="utf-8")
    tmp.chmod(0o755)
    os.replace(tmp, shim)
    return str(shim)
