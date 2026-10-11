"""通しの対象を作り、後で片付ける（筋書きが命令として呼ぶ。試験が import する助けではない）。

  python3 tests/e2e/make_target.py make <試みのフォルダ>   対象・その origin・依頼・家を作り、絶対パスを JSON 1 行で出す
  python3 tests/e2e/make_target.py teardown                  控えの家ごとに、終わっていない run を止めて控えから消す

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「対象の作り方」。試みのフォルダはリポジトリの外に置き、作業ツリーには
何も書かない。控えは、この checkout の git の私用の置き場（git rev-parse --git-dir の下）に置くので、同じ機械のほかの checkout の
控えには触らない。run は殻 bin/works-factory の workflow cancel（止まらなければ abandon）で止める。プロセスを名で止めない。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = Path(__file__).resolve().parent / "target-seed"
SHELL = ROOT / "bin" / "works-factory"
REQUEST = "request_ok.json"
LEDGER = ("works-factory-e2e", "homes")
# 種の 1 つの commit を利用者の git の設定（名前・署名・hook）に左右されずに作る
GIT_ID = ["-c", "user.name=works-factory-e2e", "-c", "user.email=e2e@works-factory.invalid", "-c", "commit.gpgsign=false",
          "-c", "core.hooksPath=/dev/null"]


class Stop(Exception):
    pass


def git(*args: str) -> str:
    done = subprocess.run(["git", *GIT_ID, *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise Stop(f"git {' '.join(args)} が落ちた: {' '.join(done.stderr.split())}")
    return done.stdout.strip()


def ledger() -> Path:
    return Path(git("-C", str(ROOT), "rev-parse", "--absolute-git-dir")).joinpath(*LEDGER)


def make(attempt: Path) -> dict:
    attempt = Path(os.path.realpath(attempt))
    if attempt.is_relative_to(Path(git("-C", str(ROOT), "rev-parse", "--show-toplevel")).resolve()):
        raise Stop(f"試みのフォルダ {attempt} がリポジトリの中に在る。リポジトリの外に置く")
    if attempt.exists() and (not attempt.is_dir() or any(attempt.iterdir())):
        raise Stop(f"試みのフォルダ {attempt} が空のフォルダでない")
    made = {"target": attempt / "target", "origin": attempt / "origin", "request": attempt / "request.json",
            "home": attempt / "home"}
    book = ledger()
    attempt.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "--bare", "-b", "main", str(made["origin"]))
    target = str(made["target"])
    shutil.copytree(SEED, made["target"], ignore=shutil.ignore_patterns(REQUEST, "__pycache__", "*.pyc"))
    git("init", "-q", "-b", "main", target)
    git("-C", target, "add", "-A")
    git("-C", target, "commit", "-q", "-m", "seed")
    git("-C", target, "remote", "add", "origin", str(made["origin"]))
    git("-C", target, "push", "-q", "-u", "origin", "main")
    git("-C", target, "remote", "set-head", "origin", "main")
    shutil.copyfile(SEED / REQUEST, made["request"])
    made["home"].mkdir()
    book.parent.mkdir(parents=True, exist_ok=True)
    with book.open("a", encoding="utf-8") as f:
        f.write(f"{made['home']}\t{made['target']}\n")
    return {k: str(v) for k, v in made.items()}


def teardown() -> list[str]:
    """控えの行ごとに run を止め、止め切れた行を控えから消す。止め切れなかった行（残した物）を返す"""
    book = ledger()
    if not book.exists():
        return []
    lines = [line for line in book.read_text(encoding="utf-8").splitlines() if line]
    kept = [line for line in lines if not stop_runs(*map(Path, line.split("\t")))]
    tmp = book.with_name(book.name + ".tmp")
    tmp.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    os.replace(tmp, book)
    return kept


def stop_runs(home: Path, target: Path) -> bool:
    """home の家で target に走った終わっていない run を全部止める。全部止まった（か家がもう無い）なら真"""
    if not home.is_dir():
        return True
    status = launch(home, target, "status", "--all", "--json")
    try:
        runs = json.loads(status.stdout)["runs"] if status.returncode == 0 else None
    except (json.JSONDecodeError, KeyError, TypeError):
        runs = None
    if runs is None:
        print(f"make_target: {home} の run を読めない（workflow status が終了の値 {status.returncode}）", file=sys.stderr)
        return False
    stopped = True
    for run in runs:
        if launch(home, target, "cancel", run["id"], "--json").returncode == 0:
            continue
        if launch(home, target, "abandon", run["id"], "--json").returncode != 0:
            print(f"make_target: {home} の run {run['id']} を止められない（cancel も abandon も落ちた）", file=sys.stderr)
            stopped = False
    return stopped


def launch(home: Path, target: Path, *args: str) -> subprocess.CompletedProcess:
    """殻で home の家の Archon を起こす。Archon は git のリポジトリの中でしか命令を受けないので、対象を --cwd で渡す。
    止める命令は工程を回さないので、認証を要らなくする"""
    env = {**os.environ, "WORKS_FACTORY_HOME": str(home), "WORKS_FACTORY_NO_AUTH": "1"}
    return subprocess.run([sys.executable, str(SHELL), "workflow", *args, "--cwd", str(target)], cwd=home, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "make":
            print(json.dumps(make(Path(argv[1]))))
            return 0
        if argv == ["teardown"]:
            return 1 if teardown() else 0
    except Stop as stop:
        print(f"make_target: {stop}", file=sys.stderr)
        return 1
    print("使い方: make_target.py make <試みのフォルダ> | make_target.py teardown", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
