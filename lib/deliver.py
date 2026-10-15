"""出口の考え deliver の住処。差分を対象の GitHub のリポジトリへ「専用の枝への push と既定の枝向けの PR」として提出する道。標準
ライブラリと同じ置き場の forge・oneline だけ（merge の script・開始の確かめ・報告が口を引く）。

語（入力 deliver）は空と pr の 2 つ。空は何も書かない（差分を置き場に置くだけ。今までの道）。pr は、置いた差分を専用の枝
works-factory/run-<id> へ push し、既定の枝向けの PR を作り、書いた物を読み戻した値で返す。書く所は submit の 1 か所で、
作業ツリー・index・HEAD も、対象の共通の .git も書かない（commit は呼び手が渡す一時の物の置き場に作り、対象の物は読むだけ）。

- WORDS・PR・KEY: 語の表・pr の語・入力と始めの記録の欄の名
- Refused: 語が受けられない（呼び手が入口の拒みにする）
- check(word) -> str: 語を確かめる（前後の空白は落とす。空と pr のほかは Refused で語を名指す）
- preflight(repo) -> str: pr の始めの確かめ。通れば ""、通らなければ訳。remote が GitHub か（違えば forge.reason）・host の gh が在るか・
  リポジトリが読めて push の権限が真か。夜通しの実行が最後に初めて拒むのを避けるため、始めに呼ぶ
- BRANCH_PREFIX・branch_of(id) -> str: 押す先の枝の名 works-factory/run-<id>（ほかに枝の名を組む所は無い。HEAD の枝の名は使わない）
- submit(repo, base_rev, data, run_id, scratch) -> dict: 提出する。柵は push の前に全部照らし、当たれば何も書かずに訳を返す。返りは
  delivered {ok, branch, commit, url, reason}。ok は読み戻した値が push した commit と合った時だけ真
- readback(target, branch, commit, base, number) -> dict: push と PR の読み戻し（1 つの関数）。remote の枝の先と PR の head が push
  した commit と同じか、PR が開いていて base が既定の枝か。書いた側の返り値でなく読み直した値で組む
- host_gh(path) -> str|None: PATH の上の gh のうち、読むだけの口（works-gh と同じ置き場の gh）を飛ばした最初の物
- VERBS・_gh(args): gh を呼ぶ唯一の口。通す動詞は VERBS の固定の並び（api の GET・pr list・pr create・pr view）だけ
- report_lines(start, merge_apply) -> list・head_words(start, merge_apply) -> str: 報告の行と冒頭の句（欄の名と訳の語は呼び手が持たない）

host_gh は、bin 側の探し方（bin/_lib/hostgh.py の find_gh と、読むだけの口 bin/_lib/no-post-bin/works-gh の real_gh）の 3 つ目の写し。
lib は bin を import できない（lib/AGENTS.md の E3）ので、置き場の見分けだけを持ち直した: 読むだけの口は gh と works-gh を同じ
置き場に並べるので、works-gh の在る置き場を飛ばし、その次の gh を使う（bin のパスは名指さない）。探し方を変える時は 3 つを揃える。
動詞の固定が口の側（hostgh）でなく VERBS の 1 か所なのは、口の先で動詞を決めると、読むだけの口の許す動詞の並びを口がもう 1 度持つから。

押す先のリポジトリは、環境変数 GH_REPO・GH_HOST でなく forge.detect と forge.remote_repos で決める。提出は対象の remote へ書くので、
利用者が別のリポジトリを読むために置いた変数に引かれて、別の所へ書かないようにする。gh の api は --hostname と明示のパスで打ち
（api に -R は無い）、pr の動詞だけ -R <host>/<owner>/<name> を付ける。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

import forge
import oneline

KEY = "deliver"
PR = "pr"
WORDS = ("", PR)
BRANCH_PREFIX = "works-factory/run-"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SHA = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?\Z")
VERBS = (("api",), ("pr", "list"), ("pr", "create"), ("pr", "view"))
READ_ONLY_MOUTH = "works-gh"   # 読むだけの口が gh と並べて置くファイル。これの在る置き場の gh は host の gh でない
API_PATH = re.compile(r"repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.%@:~+=/-]*)?\Z")
REPO_FLAG = re.compile(r"[a-z0-9.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IDENTITY = ("works-factory", "works-factory@localhost")
PUSH_NOTE = ("対象の pre-push フックは走らせずに push した（push は対象のコードを走らせない。フックの外の確かめは対象の CI が持つ）。"
             "枝は専用で、既定の枝には触れず、merge もしない。")


class Refused(ValueError):
    """語が受けられない"""


class GhRefused(ValueError):
    """gh の呼びが通す形の外（VERBS の外・api の書く旗・host の gh が無い）。gh は起こさない"""


class Failure(Exception):
    """出口が書けない・読み戻せない（submit が delivered の訳にする）"""


def check(word) -> str:
    got = str(word or "").strip()
    if got not in WORDS:
        raise Refused(f"{KEY}={word!r} は知らない値（空か {PR}）")
    return got


def branch_of(run_id: str) -> str:
    """押す先の枝 works-factory/run-<id>。id は枝の名と gh のパスにそのまま載せるので、安全な字だけ"""
    if not isinstance(run_id, str) or not SAFE_ID.match(run_id):
        raise ValueError(f"枝の名にできない id: {run_id!r}")
    return BRANCH_PREFIX + run_id


def host_gh(path):
    for folder in (path or "").split(os.pathsep):
        if not folder or not os.path.isabs(folder) or os.path.isfile(os.path.join(folder, READ_ONLY_MOUTH)):
            continue
        found = os.path.join(folder, "gh")
        if os.path.isfile(found) and os.access(found, os.X_OK):
            return found
    return None


# --- gh を呼ぶ口 ---------------------------------------------------------------------------------------------------------

def _value(args, at, flag):
    """旗 flag の値と、読み終えた位置（--flag=値 と --flag 値 の両方）"""
    if args[at].startswith(flag + "="):
        return args[at].split("=", 1)[1], at
    return (args[at + 1], at + 1) if at + 1 < len(args) else ("", at)


def _api_problem(args) -> str:
    """api の後ろの引数が --hostname と明示のパス 1 つだけの GET か。gh api は -X の GET の外・-f・-F・--field・--raw-field・--input で
    method が POST に変わり、-R/--repo を持たない（https://cli.github.com/manual/gh_api）。通さない形なら訳、通すなら ""。"""
    host = path = None
    at = 0
    while at < len(args):
        a = args[at]
        if a == "--hostname" or a.startswith("--hostname="):
            host, at = _value(args, at, "--hostname")
        elif a in ("-X", "--method") or a.startswith("--method=") or (a.startswith("-X") and not a.startswith("--")):
            if a.startswith("-X") and a != "-X":
                value = a[2:]
            else:
                value, at = _value(args, at, "--method")
            if value.upper() != "GET":
                return f"gh api の method は GET だけ（{value}）"
        elif a in ("--field", "--raw-field", "--input") or a.startswith(("--field=", "--raw-field=", "--input=")) \
                or (a[:2] in ("-f", "-F") and not a.startswith("--")):
            return f"gh api に {a.split('=', 1)[0]} は付けない（method が POST に変わる）"
        elif a in ("-R", "--repo") or a.startswith("--repo=") or (a.startswith("-R") and not a.startswith("--")):
            return "gh api に -R は付けない（--hostname と明示のパスで打つ）"
        elif a.startswith("-"):
            return f"gh api の旗 {a} は通さない"
        elif path is None:
            path = a
        else:
            return f"gh api のパスが 2 つ（{path}・{a}）"
        at += 1
    if not host or not forge.HOST.match(host.lower()):
        return "gh api に --hostname <host> が無い"
    if path is None or not API_PATH.match(path):
        return f"gh api のパスは repos/<owner>/<name>… の明示の形だけ（{path}）"
    return ""


def _pr_problem(args) -> str:
    repos = [args[i + 1] for i, a in enumerate(args) if a in ("-R", "--repo") and i + 1 < len(args)]
    if len(repos) != 1 or not REPO_FLAG.match(repos[0].lower()):
        return f"gh {' '.join(args[:2])} に -R <host>/<owner>/<name> が 1 つだけ要る"
    if any(a in ("-w", "--web") or a.startswith("--web=") for a in args):
        return "--web は使わない"
    return ""


def _gh(args, *, cwd=None):
    """host の gh を 1 回呼ぶ唯一の口（subprocess.CompletedProcess を返す）。通すのは VERBS の動詞だけで、api は GET の形だけ。
    通さない形と、host の gh が無い時は、gh を起こす前に GhRefused"""
    args = list(args)
    verb = next((v for v in VERBS if tuple(args[:len(v)]) == v), None)
    if verb is None:
        raise GhRefused(f"gh {' '.join(args[:2]) or '（引数なし）'} は出口が通す動詞の外（{' / '.join(' '.join(v) for v in VERBS)}）")
    why = _api_problem(args[1:]) if verb == ("api",) else _pr_problem(args)
    if why:
        raise GhRefused(why)
    gh = host_gh(os.environ.get("PATH", ""))
    if gh is None:
        raise GhRefused("host の gh が PATH に無い（読むだけの口の置き場を飛ばした先に gh が見つからない）")
    env = {**os.environ, "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1"}
    return subprocess.run([gh, *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL)


def _read(args, what: str):
    """gh の読み 1 回: (JSON の値, 失敗の訳, 見つからない（HTTP 404）か)"""
    done = _gh(args)
    if done.returncode != 0:
        first = next((s for s in f"{done.stderr}\n{done.stdout}".splitlines() if s.strip()), "")
        return None, f"{what} が exit {done.returncode}: {first}", "HTTP 404" in f"{done.stderr}{done.stdout}"
    try:
        return json.loads(done.stdout), "", False
    except ValueError:
        return None, f"{what} の出力が JSON でない", False


def _api(target, rest: str = ""):
    path = f"repos/{target['owner']}/{target['name']}" + (f"/{rest}" if rest else "")
    return _read(["api", "--hostname", target["host"], path], f"gh api {rest or 'repos'}")


def _slug(target) -> str:
    return f"{target['host']}/{target['owner']}/{target['name']}"


# --- 押す先 ---------------------------------------------------------------------------------------------------------------

def _target(repo):
    """(押す先 {host, owner, name}, 訳)。remote が GitHub でなければ forge.reason の訳"""
    found = forge.detect(repo)
    if found["kind"] != forge.GITHUB:
        return None, forge.reason(found) or f"remote の種類を決められない（{found['kind']}）"
    for got in forge.remote_repos(repo, found["remote"]):
        if got["kind"] == forge.GITHUB:
            return got, ""
    return None, "GitHub の URL の remote が無い"


def preflight(repo) -> str:
    target, why = _target(repo)
    if why:
        return why
    try:
        if host_gh(os.environ.get("PATH", "")) is None:
            return "host の gh が PATH に無い（読むだけの口の置き場を飛ばした先に gh が見つからない）"
        doc, why, _ = _api(target)
    except GhRefused as error:
        return str(error)
    if why:
        return forge.redact(oneline.one_line(f"{_slug(target)} を読めない: {why}"))
    if not isinstance(doc, dict) or (doc.get("permissions") or {}).get("push") is not True:
        return f"{_slug(target)} に push の権限が無い（gh api の permissions.push が真でない）"
    return ""


# --- 提出 -----------------------------------------------------------------------------------------------------------------

def _doc(ok: bool, branch: str = "", commit: str = "", url: str = "", reason: str = "") -> dict:
    return {"ok": ok, "branch": branch, "commit": commit, "url": url,
            "reason": forge.redact(oneline.one_line(reason)) if reason else ""}


def _git(repo, *args, env=None, data=None) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], env=env, input=data, capture_output=True, stdin=None if data else subprocess.DEVNULL)
    if done.returncode != 0:
        verb = next(a for i, a in enumerate(args) if not a.startswith("-") and (i == 0 or args[i - 1] != "-c"))
        raise Failure(f"git {verb} が落ちた: {oneline.one_line(done.stderr.decode('utf-8', 'replace'))[-300:]}")
    return done.stdout.decode("utf-8", "replace").strip()


def _fences(target, branch: str, base_rev: str):
    """push の前の柵。当たれば Failure。返り値は既定の枝の名"""
    doc, why, _ = _api(target)
    default = doc.get("default_branch") if isinstance(doc, dict) else None
    if why or not isinstance(default, str) or not default:
        raise Failure(f"既定の枝を読めない: {why or 'default_branch が無い'}")
    found, why, missing = _api(target, f"branches/{branch}")
    if why and not missing:   # 無い枝（初めての提出）は 404。守りなしと読み、規則の照らしへ進む
        raise Failure(f"押す先の枝の守りを読めない: {why}")
    if isinstance(found, dict) and found.get("protected") is True:
        raise Failure(f"押す先の枝 {branch} は守られている（protected）")
    rules, why, _ = _api(target, f"rules/branches/{branch}")
    if why:
        raise Failure(f"押す先の枝の規則を読めない: {why}")
    if rules:
        raise Failure(f"押す先の枝 {branch} に規則が効いている（rules {len(rules) if isinstance(rules, list) else '?'} 件）")
    cmp, why, _ = _api(target, f"compare/{default}...{base_rev}")
    status = cmp.get("status") if isinstance(cmp, dict) else None
    if status not in ("behind", "identical"):
        raise Failure(f"基の版 {base_rev[:12]} が既定の枝 {default} から届かない（compare: {status or why}）。"
                      "包んだ commit・push していない commit からは提出しない")
    return default


def _objects(repo) -> Path:
    common = Path(_git(repo, "rev-parse", "--git-common-dir"))
    return (common if common.is_absolute() else Path(repo) / common) / "objects"


def _commit(repo, base_rev: str, data: bytes, run_id: str, scratch: Path) -> str:
    """基の版の上に差分を当てた commit を、物の置き場 scratch に作る（対象の objects は読むだけ）。作者と commit した者は works-factory、
    日時は基の commit の日時（同じ入力から同じ commit になる。やり直しの push が通る）。作業ツリー・index・HEAD は読まない"""
    scratch.mkdir(parents=True, exist_ok=True)
    date = _git(repo, "log", "-1", "--format=%cI", base_rev)
    name, email = IDENTITY
    with tempfile.TemporaryDirectory(prefix="works-deliver-") as tmp:
        env = {**os.environ, "GIT_OBJECT_DIRECTORY": str(scratch), "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(_objects(repo)),
               "GIT_INDEX_FILE": os.path.join(tmp, "index"), "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
               "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        _git(repo, "read-tree", base_rev, env=env)
        _git(repo, "apply", "--cached", "--whitespace=nowarn", env=env, data=data)
        tree = _git(repo, "write-tree", env=env)
        if tree == _git(repo, "rev-parse", f"{base_rev}^{{tree}}", env=env):
            raise Failure("差分を当てても基の版の木と同じ（提出する物が無い）")
        return _git(repo, "commit-tree", "--no-gpg-sign", tree, "-p", base_rev, "-m", f"works-factory: run {run_id}", env=env)


def _push(repo, target, branch: str, commit: str, scratch: Path) -> None:
    """--force なしで <commit>:refs/heads/<枝> を送る。対象のフックは走らせない（core.hooksPath を空にし --no-verify）。資格は host の gh
    を git の資格の口にして渡す（push の時だけ）"""
    gh = host_gh(os.environ.get("PATH", ""))
    if gh is None:
        raise Failure("host の gh が PATH に無い")
    url = f"https://{target['host']}/{target['owner']}/{target['name']}.git"
    env = {**os.environ, "GIT_OBJECT_DIRECTORY": str(scratch), "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(_objects(repo)),
           "GIT_TERMINAL_PROMPT": "0"}
    helper = f"!{shlex.quote(gh)} auth git-credential"
    try:
        _git(repo, "-c", "core.hooksPath=/dev/null", "-c", "credential.helper=", "-c", f"credential.helper={helper}",
             "push", "--no-verify", url, f"{commit}:refs/heads/{branch}", env=env)
    except Failure as error:
        raise Failure(f"push が拒まれた・落ちた（--force は付けない）: {error}") from None


def _pr(target, branch: str, default: str, run_id: str, scratch: Path) -> int:
    """同じ枝の開いた PR が在れば作り直さず、その番号。無ければ既定の枝向けに作る"""
    flag = ["-R", _slug(target)]
    opened, why, _ = _read(["pr", "list", *flag, "--head", branch, "--state", "open", "--json", "number,url"], "gh pr list")
    if why:
        raise Failure(why)
    if isinstance(opened, list) and opened:
        return int(opened[0]["number"])
    body = (f"works-factory の実行 {run_id} が作った。\n\n差分の置き場: {scratch.parent}\n\n{PUSH_NOTE}")
    # 既定の枝は短い旗 -B で渡す（長い旗の字は、入口の入力 base の読みを見張る柵の語と同じ形で、別の考えを指すため）
    done = _gh(["pr", "create", *flag, "-B", default, "--head", branch, "--title", f"works-factory: run {run_id}", "--body", body])
    found = re.search(r"/pull/(\d+)", done.stdout)
    if done.returncode != 0 or not found:
        raise Failure(f"gh pr create が exit {done.returncode}: {oneline.one_line(done.stderr or done.stdout)[-300:]}")
    return int(found.group(1))


def readback(target, branch: str, commit: str, base: str, number: int) -> dict:
    """読み直した値で delivered を組む。ok は、remote の枝の先が push した commit と同じで、PR が開いていて head の commit・枝の名・
    base の枝が合う時だけ真（終了の値 0 は証拠にしない）。食い違いは訳で名指す"""
    ref, why, missing = _api(target, f"git/ref/heads/{branch}")
    if why:
        return _doc(False, branch, commit, reason=f"remote の枝 {branch} が無い" if missing else f"remote の枝を読めない: {why}")
    sha = (ref.get("object") or {}).get("sha") if isinstance(ref, dict) else None
    if sha != commit:
        return _doc(False, branch, commit, reason=f"remote の枝 {branch} の先が push した commit と違う（読んだ {sha}・push した {commit}）")
    pr, why, _ = _read(["pr", "view", str(number), "-R", _slug(target), "--json", "url,state,headRefOid,headRefName,baseRefName"],
                       "gh pr view")
    if why or not isinstance(pr, dict):
        return _doc(False, branch, commit, reason=f"PR を読めない: {why or 'object でない'}")
    wrong = []
    if pr.get("state") != "OPEN":
        wrong.append(f"PR が開いていない（state {pr.get('state')}）")
    if pr.get("headRefOid") != commit:
        wrong.append(f"PR の head が push した commit と違う（読んだ {pr.get('headRefOid')}・push した {commit}）")
    if pr.get("headRefName") != branch:
        wrong.append(f"PR の head の枝が違う（読んだ {pr.get('headRefName')}・押した {branch}）")
    if pr.get("baseRefName") != base:
        wrong.append(f"PR の base が既定の枝 {base} でない（読んだ {pr.get('baseRefName')}）")
    if wrong:
        return _doc(False, branch, commit, str(pr.get("url") or ""), "・".join(wrong))
    return _doc(True, str(pr["headRefName"]), sha, str(pr["url"]))


def submit(repo, base_rev: str, data: bytes, run_id: str, scratch) -> dict:
    """data（git の差分のバイト。基の版 base_rev から）を、専用の枝へ push し既定の枝向けの PR にして、delivered を返す。落ちない
    （どの失敗も ok: false と訳）。柵に当たれば何も書かない"""
    branch = commit = ""
    try:
        branch = branch_of(run_id)
        target, why = _target(repo)
        if why:
            raise Failure(why)
        if not isinstance(base_rev, str) or not SHA.match(base_rev):
            raise Failure(f"基の版が commit の sha でない: {base_rev!r}")
        if not data:
            raise Failure("提出する差分が空")
        scratch = Path(scratch)
        default = _fences(target, branch, base_rev)
        commit = _commit(repo, base_rev, data, run_id, scratch)
        _push(repo, target, branch, commit, scratch)
        number = _pr(target, branch, default, run_id, scratch)
        return readback(target, branch, commit, default, number)
    except (Failure, GhRefused, ValueError, OSError) as error:
        return _doc(False, branch, commit, reason=str(error))
    except (KeyError, TypeError) as error:
        return _doc(False, branch, commit, reason=f"gh の答えの形が想定と違う: {type(error).__name__} {error}")


# --- 報告 -----------------------------------------------------------------------------------------------------------------

def _asked(start) -> bool:
    inputs = start.get("inputs") if isinstance(start, dict) else None
    return isinstance(inputs, dict) and str(inputs.get(KEY) or "").strip() == PR


def _result(merge_apply) -> dict:
    """置く段 merge-apply の返りから出口の結果 {ok, text}。text は ok なら PR の言い方、偽なら作らなかった訳"""
    if not isinstance(merge_apply, dict):
        return {"ok": False, "text": "merge-apply が走らなかった（最後の承認ノードが通さなかった・差分が無い・手前で止まった）"}
    got = merge_apply.get("delivered")
    if isinstance(got, dict) and got.get("ok") is True:
        return {"ok": True, "url": got.get("url") or "", "branch": got.get("branch") or "", "commit": got.get("commit") or ""}
    if isinstance(got, dict):
        return {"ok": False, "text": got.get("reason") or "訳の記録なし"}
    if merge_apply.get("ok") is not True:
        return {"ok": False, "text": f"差分を置けなかった: {merge_apply.get('reason') or '訳の記録なし'}"}
    return {"ok": False, "text": "出口の結果 delivered が返っていない"}


def report_lines(start, merge_apply) -> list:
    """報告の行（入力が pr の実行だけ。空の語の実行は何も言わない）"""
    if not _asked(start):
        return []
    got = _result(merge_apply)
    if got["ok"]:
        return [f"PR: {got['url']}（専用の枝 {got['branch']} の {got['commit']} を読み戻した。既定の枝へは merge していない）"]
    return [f"PR を作らなかった（{KEY}: {PR}）: {forge.redact(oneline.one_line(got['text']))}"]


def head_words(start, merge_apply) -> str:
    """報告の冒頭の句（入力が pr の実行だけ）"""
    if not _asked(start):
        return ""
    got = _result(merge_apply)
    if got["ok"]:
        return f"PR を作った: {got['url']}"
    return f"PR を作らなかった: {forge.redact(oneline.one_line(got['text']))}"
