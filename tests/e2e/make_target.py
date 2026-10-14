"""通しの対象を作り、後で片付ける（筋書きが命令として呼ぶ。試験が import する助けではない）。

  python3 tests/e2e/make_target.py make <試みのフォルダ> [--seed <dir>] [--request <file>] [--no-ledger]
                                                             対象・その origin・依頼・家を作り、絶対パスを JSON 1 行で出す
  python3 tests/e2e/make_target.py teardown                  控えの家ごとに、終わっていない run を止めて控えから消す
  python3 tests/e2e/make_target.py stop <試みのフォルダ>      その試みの家の終わっていない run だけを止める（控えを見ない）

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の版 bee02ce2 の「対象の作り方」（今の版から消え、issue #101 が
この版を正本として指す）。試みのフォルダはリポジトリの外に置き、作業ツリーには
何も書かない。控えは、この checkout の git の私用の置き場（git rev-parse --git-dir の下）に置くので、同じ機械のほかの checkout の
控えには触らない。種と依頼の既定は target-seed/ とその中の request_ok.json。公開ベンチのランナー tests/calibration/run.py は
この道具の layout（置き場の名）だけを使い、試みのフォルダを自分で組む。--no-ledger は控えに載せない（teardown が今の works の家に works-factory の殻を当てないため。同じ checkout
でほかの run と並べる通しも、teardown がその run を止めないよう --no-ledger で作り、stop で自分の家だけを止める）。
run は殻 bin/works-factory の workflow cancel（止まらなければ abandon）で止める。プロセスを名で止めない。

種 target-seed/ の stats.py には試作と同じ 2 つのバグを仕込んである: mean の分母が len(xs) - 1（正しくは len(xs)）、clamp が上限を
超えた時に lo を返す（正しくは hi）。そのせいで test_stats.py の 3 件中 2 件が赤になる。この説明は種の文（docstring・コメント）に
書かない。対象のコードがバグの在りかを書いていると、判定の役に答えを渡し、直した後に嘘になる文を修正役が必ず書き換えて独立の目の
指摘を呼ぶ（tests/e2e/test_make_target.py の SeedTextCase が縛る）。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))   # 命令として走る時は tests/e2e/ が頭に来るだけなので
from bin._lib import launcher  # noqa: E402

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


def make(attempt: Path, seed: Path = SEED, request: Path = SEED / REQUEST, listed: bool = True) -> dict:
    attempt = Path(os.path.realpath(attempt))
    if attempt.is_relative_to(Path(git("-C", str(ROOT), "rev-parse", "--show-toplevel")).resolve()):
        raise Stop(f"試みのフォルダ {attempt} がリポジトリの中に在る。リポジトリの外に置く")
    if attempt.exists() and (not attempt.is_dir() or any(attempt.iterdir())):
        raise Stop(f"試みのフォルダ {attempt} が空のフォルダでない")
    made = layout(attempt)
    book = ledger()
    attempt.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "--bare", "-b", "main", str(made["origin"]))
    target = str(made["target"])
    shutil.copytree(seed, made["target"], ignore=shutil.ignore_patterns(REQUEST, "__pycache__", "*.pyc"))
    git("init", "-q", "-b", "main", target)
    git("-C", target, "add", "-A")
    git("-C", target, "commit", "-q", "-m", "seed")
    git("-C", target, "remote", "add", "origin", str(made["origin"]))
    git("-C", target, "push", "-q", "-u", "origin", "main")
    git("-C", target, "remote", "set-head", "origin", "main")
    shutil.copyfile(request, made["request"])
    made["home"].mkdir()
    if listed:
        book.parent.mkdir(parents=True, exist_ok=True)
        with book.open("a", encoding="utf-8") as f:
            f.write(f"{made['home']}\t{made['target']}\n")
    return {k: str(v) for k, v in made.items()}


def layout(attempt: Path) -> dict[str, Path]:
    return {"target": attempt / "target", "origin": attempt / "origin", "request": attempt / "request.json",
            "home": attempt / "home"}


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
    env = {**os.environ, launcher.HOME_ENV: str(home), "WORKS_FACTORY_NO_AUTH": "1"}
    return subprocess.run([sys.executable, str(SHELL), "workflow", *args, "--cwd", str(target)], cwd=home, env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8")


def make_args(args: list[str]) -> dict | None:
    """make の引数を make の引数の dict に。形が違えば None"""
    made: dict = {}
    rest = list(args)
    while rest:
        word = rest.pop(0)
        if word == "--no-ledger" and "listed" not in made:
            made["listed"] = False
        elif word in ("--seed", "--request") and rest and word[2:] not in made:
            made[word[2:]] = Path(rest.pop(0)).resolve()
        elif not word.startswith("--") and "attempt" not in made:
            made["attempt"] = Path(word)
        else:
            return None
    return made if "attempt" in made else None


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["make"] and (made := make_args(argv[1:])) is not None:
            print(json.dumps(make(**made)))
            return 0
        if argv == ["teardown"]:
            return 1 if teardown() else 0
        if argv[:1] == ["stop"] and len(argv) == 2:
            attempt = Path(os.path.realpath(argv[1]))
            made = layout(attempt)
            if not made["home"].is_dir():
                raise Stop(f"{attempt} に家 home/ が無い（make の作った試みのフォルダでない）")
            return 0 if stop_runs(made["home"], made["target"]) else 1
    except Stop as stop:
        print(f"make_target: {stop}", file=sys.stderr)
        return 1
    print("使い方: make_target.py make <試みのフォルダ> [--seed <dir>] [--request <file>] [--no-ledger] | make_target.py teardown"
          " | make_target.py stop <試みのフォルダ>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
