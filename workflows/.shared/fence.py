"""埋め P5（docs/polyfills.md）: 読むだけの役の claude を起こす直前に、書き込みを禁じるパスの一覧を組んで sandbox の denyWrite に足す包み。

止めた Archon は役の sandbox を置き換えずに SDK へ渡す（packages/workflows/src/dag-executor.ts の
『sandbox: node.sandbox ?? workflowLevelOptions.sandbox,』・packages/providers/src/claude/provider.ts の applyNodeConfig）ので、
YAML の固定の値では run ごとに違うパス（cwd・共通の .git・worktree の根）を名指せない。Archon が起こす claude の実行ファイルは
CLAUDE_BIN_PATH で替えられる（packages/providers/src/claude/binary-resolver.ts の resolveClaudeBinaryWithSource）
ので、起動の殻（bin/_lib/launcher.py の write_fence）がこの包みをそこに置く。SDK は sandbox を `--settings` の JSON の字に入れて
渡し、設定のファイルのパスでは渡さない（tests/shared/test_archon_contract.py が SDK の源で照らす）。

一覧の組み方は今の works の role_run.protected_paths を写した（下の写しの注記）。起動に足す形は包み claude-adapter の
「旗 no-tree-write の起動に denyWrite を足す」を採り、旗の代わりに、YAML が読むだけの役に書く固定の値
（tests/layers/scan.py の NO_TREE_WRITE。~ を HOME で解くと Archon の家）を印に読む。印の無い起動は argv を変えずに起こす。
印の在る起動は、起こす前に起動の記録（--records。起動の殻が env の RECORDS_ENV でも script のノードに名指す）へ時刻と cwd の 1 行を
足し、書けなければ起こさない。記録は --own の下に置かれ、柵の中の役は書き換えられない。受け付け（以前は test-gate の ci-accept。今の使い手は無い）は
fenced_since で、役を起こす前の時刻より後にその作業ツリーで柵の掛かった起動が在ったかを見る（今の works の ci_role.take の
「包みの起動の記録を見て止める」と同じ所。棚卸しの T49）。
起こす claude の PATH の頭には、起動の殻が --path-head で名指した置き場（読むだけの gh の口 works-gh の置き場）を足す。Archon は
script のノードと役の claude に同じ環境を渡すので、gh を書き込みのできる口（script のノードが通す hostgh の口）と読むだけの口に
分けられるのは、役の claude を起こすこの包みだけ（持ち主の決め roles-read-only-gh）。
起こす claude には ENGINE_CHILD_ENV=1 を立てる。対象の重い一式（e2e など）がこの名で AI の役からの起動を見分けて拒む、今の works の
約束の名（skills/works/SKILL.md）。最後のテストは script のノードが走らせて包みを通らないので立たない（今の works と同じ）。
標準ライブラリだけを使う（起動の殻が `python -I -B` で起こす）。
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence

SETTINGS = "--settings"
DENY_WRITE = ("sandbox", "filesystem", "denyWrite")
REFUSED_EXIT = 3
RECORDS_ENV = "WORKS_FACTORY_FENCE_RECORDS"   # 起動の記録のパス。在れば run は包みを通ると宣言した
ENGINE_CHILD_ENV = "GRAPHLOOPS_ENGINE_CHILD"
PROFILE_ENV = "WORKS_FACTORY_CONNECTION_PROFILE"   # 殻が組む必要設定。探索と認証判断は殻だけが持つ


def connection(environ):
    """殻の env 契約を読み、保持値と除去名を返す。設定元を探さず資格を取得しない。"""
    raw = environ.pop(PROFILE_ENV, None)
    if raw is None:
        return {"settings": {}, "env": {}, "drop": []}
    try:
        profile = json.loads(raw)
        valid = (isinstance(profile, dict) and set(profile) == {"settings", "env", "drop"}
                 and isinstance(profile["settings"], dict) and set(profile["settings"]) <= {"env"}
                 and isinstance(profile["settings"].get("env", {}), dict)
                 and isinstance(profile["env"], dict) and isinstance(profile["drop"], list))
        if not valid:
            raise ValueError()
        bags = (profile["env"], profile["settings"].get("env", {}))
        if not all(isinstance(k, str) and isinstance(v, str) for bag in bags for k, v in bag.items()):
            raise ValueError()
        names = [*profile["env"], *profile["settings"].get("env", {}), *profile["drop"]]
        if not all(isinstance(k, str) and k not in {"HOME", "CLAUDE_CONFIG_DIR", "ARCHON_HOME", "PATH"}
                   and not k.startswith(("XDG_", "WORKS_FACTORY_", "GRAPHLOOPS_")) for k in names):
            raise ValueError()
    except (ValueError, TypeError):
        raise Refused("殻の接続設定の契約が読めない（値は表示しない）") from None
    return profile


def connection_env(environ, profile):
    for k in profile["drop"]:
        environ.pop(k, None)
    environ.update(profile["env"])



class Refused(Exception):
    """書き込みを禁じる一覧を決められない。claude を起こさずに止める"""


def protected(cwd: str, archon_home: str, claude_config: str, own: Sequence[str]) -> list[str]:
    """書き込みを禁じるパスの一覧: 今の works の protected_paths（共有ボードの代わりに Archon の家）の後ろに、Claude の設定（読んだ証拠と
    書き込みの記録とフック）と own（起動の殻が書いた口と、この run の後の役の起動や次の起動が sandbox の外で走らせる物）の実パスを足す。git が読めず
    守る場所が決まらなければ Refused"""
    paths = protected_paths(cwd, archon_home)
    if paths is None:
        raise Refused("git から守る場所を引けない（git が無いか、落ちたか、時間切れ）")
    return list(dict.fromkeys([*paths, *(os.path.realpath(p) for p in (claude_config, *own))]))


# ここから protected_paths の終わりまでは、今の works（commit 2aa7c66cf7ab の graphloops/engine/role_run.py
# 141-172 行）をそのまま写した物（docs/polyfills.md の P5）。直す時は元と見比べる
def _git(cwd, *args):
    """cwd で git を走らせる。返すのは (成功か, 行, 標準エラー)。git が無い・時間切れは (False, [], 理由)。
    role_run は盤面も graph も import しないので、engine の util.git を使わない。git の文は英語に固める（LC_ALL=C・LANGUAGE を外す）
    ——呼び元が『not a git repository』の文で作業ツリーの外を見分ける。終了コードは作業ツリーの外と所有者の食い違い（safe.directory）・
    .git の中などの致命の誤りが同じ 128 で、分けられない（分けずに外へ倒すと宣言の deny と守る場所を黙って落とす）"""
    env = {k: v for k, v in os.environ.items() if k != "LANGUAGE"}
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, env={**env, "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError) as e:
        return False, [], str(e)
    return r.returncode == 0, r.stdout.splitlines(), r.stderr


def protected_paths(cwd, board_dir=None):
    """sandbox の中の書き込みを止める場所（filesystem.denyWrite）。**cwd 自身を含む**作業ツリーの根の全部（git worktree list）・
    共有の .git の実体（git rev-parse --git-common-dir。linked worktree の gitdir と既定の盤面の置き場を含む）・盤面の置き場。
    書けるのは sandbox の既定の TMPDIR だけになる——cwd を書ける場所に残すと、役が計器を動かしてレビュー対象の未コミットの変更を
    壊せ、前後の作業ツリーの突合は事故の検知で中身を戻さない（.gitignore の対象は突合にも映らない）。祖先の作業ツリー
    （<repo>/.claude/worktrees/<名前> の本体）も根ごと名指しできる。git の作業ツリーでない cwd は cwd と盤面だけ。
    git が読めない（git が無い・時間切れ）なら None——守る場所が決まらないので sandbox の形を選ばない。"""
    cwd = os.path.realpath(cwd or os.getcwd())
    paths = {cwd} | ({os.path.realpath(board_dir)} if board_dir else set())
    ok, common, err = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not ok:
        return sorted(paths) if "not a git repository" in err else None
    ok, trees, _err = _git(cwd, "worktree", "list", "--porcelain")
    if not ok or not common:
        return None
    paths.add(os.path.realpath(common[0]))
    paths |= {os.path.realpath(x[len("worktree "):]) for x in trees if x.startswith("worktree ")}
    return sorted(paths)


def fenced_argv(argv: list[str], archon_home: str, paths: Callable[[], list[str]], extra=None) -> list[str]:
    """argv の --settings の sandbox.filesystem.denyWrite が印（~ を解くと archon_home）を持つ時だけ、paths() の一覧のうち無い物を
    後ろに足した argv。印が無ければ argv のまま。--settings の値が JSON の object でなければ（設定のファイルのパスを含む）、印を
    見落としうるので Refused"""
    at = [i for i, a in enumerate(argv) if a == SETTINGS or a.startswith(SETTINGS + "=")]
    if len(at) > 1:
        raise Refused(f"{SETTINGS} が {len(at)} 個ある。印が在るかを決められない")
    if not at:
        if extra and extra.get("env"):
            return [*argv, SETTINGS, json.dumps(extra, ensure_ascii=False)]
        return argv
    i = at[0]
    joined = argv[i] != SETTINGS
    if not joined and i + 1 == len(argv):
        raise Refused(f"{SETTINGS} に値が無い")
    raw = argv[i][len(SETTINGS) + 1:] if joined else argv[i + 1]
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError as error:
        raise Refused(f"{SETTINGS} の値を JSON として読めない（{error}）") from None
    if not isinstance(settings, dict):
        raise Refused(f"{SETTINGS} の JSON が object でない")
    deny = settings
    for key in DENY_WRITE:
        deny = deny.get(key) if isinstance(deny, dict) else None
    marked = isinstance(deny, list) and any(marks(item, archon_home) for item in deny)
    if marked:
        deny += [p for p in paths() if p not in deny]
    if extra and extra.get("env"):
        env = settings.get("env", {})
        if not isinstance(env, dict):
            raise Refused("既存 settings の env が object でない")
        settings["env"] = {**env, **extra["env"]}
    elif not marked:
        return argv
    value = json.dumps(settings, ensure_ascii=False)
    return [*argv[:i], f"{SETTINGS}={value}", *argv[i + 1:]] if joined else [*argv[:i + 1], value, *argv[i + 2:]]


def marks(item, archon_home: str) -> bool:
    return isinstance(item, str) and os.path.realpath(os.path.expanduser(item)) == os.path.realpath(archon_home)


def record(records: str, cwd: str) -> None:
    """起動の記録 records に、今の時刻と cwd の実パスの 1 行を足す。書けなければ Refused"""
    row = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "cwd": os.path.realpath(cwd)}
    try:
        os.makedirs(os.path.dirname(records), exist_ok=True)
        with open(records, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as error:
        raise Refused(f"起動の記録 {records} を書けない（{error}）") from None


def bad_declaration(records: str) -> str:
    """宣言した記録のパス records を記録の置き場に読めなければ訳の 1 行（読めれば空）"""
    return "" if os.path.isabs(records) else f"{RECORDS_ENV} が絶対パスでない（{records!r}）"


def _at(text) -> datetime.datetime | None:
    """時刻の字（ISO 8601。時差つき）。読めなければ None"""
    try:
        at = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else None


def fenced_since(records, root, since: str | None) -> str:
    """記録 records に、since より後に root（実パス）かその下を cwd にした起動が在れば空。無ければ訳の 1 行"""
    start = _at(since)
    if start is None:
        return f"役を起こす前の時刻 {since!r} が読めない"
    try:
        with open(records, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as error:
        return f"起動の記録 {records} が読めない（{error}）"
    top = os.path.realpath(root)
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not isinstance(cwd := row.get("cwd"), str):
            continue
        at = _at(row.get("at"))
        if at is not None and at > start and (cwd == top or cwd.startswith(top.rstrip(os.sep) + os.sep)):
            return ""
    return f"起動の記録 {records} に、{since} より後に {top} で柵を掛けた起動が無い"


def main(argv: list[str]) -> int:
    cut = argv.index("--") if "--" in argv else len(argv)
    ap = argparse.ArgumentParser(prog="fence.py")
    ap.add_argument("--real", required=True)
    ap.add_argument("--archon-home", required=True)
    ap.add_argument("--claude-config", required=True)
    ap.add_argument("--own", action="append", default=[])
    ap.add_argument("--records", required=True)
    ap.add_argument("--path-head", action="append", default=[])
    opts = ap.parse_args(argv[:cut])
    rest = argv[cut + 1:]

    def paths() -> list[str]:
        listed = protected(os.getcwd(), opts.archon_home, opts.claude_config, opts.own)
        record(opts.records, os.getcwd())
        return listed

    try:
        profile = connection(os.environ)
        connection_env(os.environ, profile)
        rest = fenced_argv(rest, opts.archon_home, paths, profile["settings"])
    except Refused as refused:
        print(f"works-factory fence: {refused}", file=sys.stderr)
        return REFUSED_EXIT
    os.environ[ENGINE_CHILD_ENV] = "1"
    os.environ["PATH"] = os.pathsep.join(filter(None, [*opts.path_head, os.environ.get("PATH")]))
    os.execv(opts.real, [opts.real, *rest])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
