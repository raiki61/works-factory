"""run の中で利用者の gh のログインを継ぐ口を書く（bin/ の起動が、HOME・XDG_* を隔離する前の値で呼ぶ）。

隔離した HOME・XDG_CONFIG_HOME の下の gh は、利用者の gh の設定（hosts.yml）も macOS の keychain のトークン（gh の既定の置き場。
keychain は HOME から探すので、隔離した HOME では login の keychain が探す先に無い。2026-10-08 に security list-keychains で確かめた）
も見えない。run の中の並行 PR の確かめ（写しの parallel-pr.py）はそれで毎回 gh の失敗になり、1 周の run が round_limit で終わった
（実の利用者の run 97fd532f）。持ち主の決定（2026-10-08）: run の中の gh は利用者の gh を継ぐ（本流の review-graph は利用者の環境の
まま gh を打つ）。そこで <dir>/gh に、PATH の上の本物の gh を利用者の HOME と gh の設定の置き場（config_dir）で起こすだけの sh の口を
書き、起動が PATH の頭（読むだけの口 no-post-bin/ のすぐ後ろ）に <dir> を置く。口が持つのはパスと名だけで、トークンの値は写さない・出さない・置かない。
利用者の gh がログインしていなければ gh の言葉と終了コードのまま（run の中は今どおり人待ち）。

環境変数だけで gh にログインする利用者（GH_TOKEN など。Linux・CI に多い）のために、起動は子の環境から 4 つのトークンの名を
外したまま（TOKENS。RELAY の拾う名から出す）、値を gh も他の道具も自動では読まない名（RELAY の渡しの名）で子に渡す（#131 のコメントの運び役の決め。持ち主の決め others-may-use・auth-middleware・roles-read-only-gh から導いた。#132）。読むのは
この口だけで、本物の gh を起こす時だけ gh の名へ戻し、渡しの名は本物の gh に見せない。子に gh の名が既に在れば（Archon が節に
トークンを渡した時）上書きしない。役は自分の環境の渡しの名を読めるので、これも事故の柵で、堅い境ではない。

AI の役が打つ gh は、起動（launcher.py）がこの口の前に置く読むだけの口 works-gh（no-post-bin/。今の works では包み
.shared/core/adapter.py の 5 が置いた）で、口の先の本物の gh がこの口。これは事故の柵で、堅い境ではない（役は利用者と同じ人で同じ
keychain を持つ）。

- config_dir(env) -> str: gh の設定の置き場（GH_CONFIG_DIR、無ければ $XDG_CONFIG_HOME/gh、無ければ $HOME/.config/gh。gh 自身の決め方）
- find_gh(path, skip) -> str|None: PATH の上の最初の gh（skip の置き場——口自身と読むだけの口——は飛ばす）
- relay(env) -> dict: env の gh のトークンを渡しの名に移した物（RELAY の行ごとに、gh 自身の先後で最初の空でない値。無い行は載せない）
- write(dir, path, home, config) -> str|None: 口を <dir>/<中身の sha256 の頭 16 桁>/gh に書いてそのパスを返す。中身ごとに置き場を
  分けるので、同じ家から並べた起動・入れ子の起動（隔離した HOME を継いだ殻）が、走っている run の口を書き換えない。gh が無ければ
  何も書かずに None（前の口は消さない。別の run が使っているかもしれない）
- CLI: `python3 -I hostgh.py write --dir <口の置き場> --path "$PATH" --home "$HOME" --gh-config-dir "${GH_CONFIG_DIR:-}"
  --xdg-config-home "${XDG_CONFIG_HOME:-}"`（隔離の前の値）。書いた口のパスか空を 1 行
"""
import argparse
import hashlib
import os
import pathlib
import shlex
import sys

NO_POST_BIN = pathlib.Path(__file__).resolve().parent / "no-post-bin"
SHIM = "gh"
# (渡しの名, 起動が拾う名を gh の先後で)。口は頭の名へ戻す。gh は GH_TOKEN・GITHUB_TOKEN を github.com と *.ghe.com にだけ、
# GH_ENTERPRISE_TOKEN・GITHUB_ENTERPRISE_TOKEN をほかのホスト（GHES）にだけ使うので、行を分ける。渡しの名は _TOKEN で終える
# （Archon の記録の伏せ字は名の末尾で値を拾う）
RELAY = (("WORKS_FACTORY_HOST_GH_TOKEN", ("GH_TOKEN", "GITHUB_TOKEN")),
         ("WORKS_FACTORY_HOST_GH_ENTERPRISE_TOKEN", ("GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")))
# 起動が子の環境から外す gh のトークンの名。外す名と渡す名を 1 つの表から出す
TOKENS = tuple(s for _, sources in RELAY for s in sources)


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
    real = find_gh(path, [NO_POST_BIN, *(p for p in path.split(os.pathsep) if _under(p, top))])
    if real is None:
        return None
    body = ("#!/bin/sh\n"
            "# works-factory の起動（bin/_lib/hostgh.py）が書いた口: 利用者の gh を、利用者の HOME（macOS の keychain は HOME から\n"
            "# 探す）と gh の設定の置き場で起こす。持つのはパスと名だけ（起動が渡しの名で渡したトークンは、ここで gh の名へ戻す）\n"
            f"HOME={shlex.quote(home)}\n"
            f"GH_CONFIG_DIR={shlex.quote(config)}\n"
            "export HOME GH_CONFIG_DIR\n"
            + "".join(f'if [ -z "${{{gh}:-}}" ] && [ -n "${{{name}:-}}" ]; then {gh}=${name}; export {gh}; fi\n'
                      for name, (gh, _) in RELAY)
            + f"unset {' '.join(name for name, _ in RELAY)}\n"
            f'exec {shlex.quote(real)} "$@"\n')
    d = top / hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    shim = d / SHIM
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{SHIM}.{os.getpid()}.tmp"
    tmp.write_text(body, encoding="utf-8")
    tmp.chmod(0o755)
    os.replace(tmp, shim)
    return str(shim)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hostgh.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--dir", required=True)
    w.add_argument("--path", required=True)
    w.add_argument("--home", required=True)
    w.add_argument("--gh-config-dir", default="")
    w.add_argument("--xdg-config-home", default="")
    a = ap.parse_args(argv)
    conf = config_dir({"GH_CONFIG_DIR": a.gh_config_dir, "XDG_CONFIG_HOME": a.xdg_config_home, "HOME": a.home})
    print(write(a.dir, a.path, a.home, conf) or "")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):   # Windows の既定コーデックに依らない（パスに日本語が在っても落ちない）
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    sys.exit(main())
