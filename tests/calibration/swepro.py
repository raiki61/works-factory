"""公開ベンチ SWE-Bench Pro V2 の Python の課題（ansible・openlibrary・qutebrowser）で、依頼から直す力を課題のコンテナの中で測る
（運び役が命令として打つ道具。試験のモジュールではない）。持ち主の決め public-bench-at-major（docs/owner-decisions.md）。
Harbor を import しない。Harbor の agent の殻は tests/calibration/swepro_agent.py の WorksBench で、ホストと課題のコンテナの両方で
このファイルが走る（コンテナへはリポジトリの git archive HEAD の写しとして届く）。

    PYTHONPATH=<リポジトリの根> uv run --isolated --extra bench harbor run -p <SWE-Bench Pro の v2/tasks> -i <instance_id> … \\
        -e docker -a tests.calibration.swepro_agent:WorksBench --ak producer=<works-factory|claude> \\
        --allow-agent-host api.anthropic.com --agent-timeout-multiplier inf -o <リポジトリの外の置き場> --job-name <名>
    python3 tests/calibration/swepro.py tally <置き場>/<名>
    python3 tests/calibration/swepro.py inside <works-factory|claude>   （殻が課題のコンテナの中で打つ）

再採点は Pro の patch_replay:PatchReplayAgent に --ak source_job=<置き場>/<名> を渡す（<試み>/agent/model.patch を読む）。

作り手: works-factory（run.WorksFactory。殻 bin/works-factory で works-factory-line を前で回し、試験のコマンドを test_cmd に渡す）・
claude（素の Claude Code を run.PLAIN_MODEL・run.PLAIN_EFFORT で claude -p 1 回。Pro の公開の手順と同じく instruction だけを渡す）。
今の works は回さない（#437 の運び役の決め。訳は OLD_WORKS）。

1 件の流れ: 殻が setup で課題のイメージの上の /opt/works-bench に道具と工場を載せ（setup_commands）、run で課題の入力
（task_inputs。依頼の行と、リポジトリごとの試験のコマンド TEST_COMMANDS）と認証のファイルを上げ、inside を 1 回打つ。inside は
試みのフォルダ <置き場>/attempt（home/・/app への target・request.json）で作り手を起こし、工場なら終わった run の封じた差分を
bin/_lib/apply.py で /app に当て、結果を /logs/agent/works-bench.json に書く。殻は /app の差分を model.patch に取り
（capture_command）、起こし役の標準出力と予測を <試み>/agent/ に書く（prediction）。tally は job の予測を数える。

- 無人の run が人に聞いて止まった（承認ノードで待った・結末の種が chain.KIND_HUMAN）時は stopped を立てる。封じた差分が在れば
  --allow-stopped で当て、封じる前に止まった run は当てずに空の patch（未解決）として数える。run を resume しない。
  /app の変更を取れなかった時も stopped を立て、model_patch を null にする（変更は /app に残っていて、空の patch ではない）。
- 作り手が落ちた（認証の拒否・工場の run が起きない・封じた差分が当たらない・結末が BROKE）時と起こし役が落ちた時は error に
  訳を書き、予測の failed を立てる。ふつうの未解決（直せなかった）と分けて数える。BROKE（record_invalid・interrupted）は
  工場そのものが壊れて終わった結末で、人の判断を待っていないので stopped（人待ち）に入れない。
- 期限を置かない（持ち主の決め no-timeouts）。Pro の 1 件の上限 PRO_SECONDS は、超えた事実を予測の pro_limit に残すだけ。
- 認証は ACCEPTED_AUTH だけを運ぶ。他（ゲートウェイ・Bedrock・Vertex）は殻が upload の前に断り、断った訳を予測の error に書く
  （state は AUTH_REFUSED、failed を立てる）。
- 漏れの塞ぎ: 認証の変数（ACCEPTED_AUTH）はファイルで 1 回だけ上げ、inside が読んで消して自分の env に置く（docker の exec の
  env はホストの ps に出る）。結果と予測には env の名だけを書く。
  gh の認証は渡さず、WebFetch・WebSearch は run.bench_env と toolset.DENY_WEB で拒む。
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))   # 頭に入れると lib/tests が根の tests を隠す（tests/AGENTS.md）
from bin._lib import apply, claude_auth, launcher, pack  # noqa: E402
import chain  # noqa: E402
import report  # noqa: E402
from tests.calibration import run  # noqa: E402
from tests.e2e import evidence  # noqa: E402

PLACE = "/opt/works-bench"
WORKDIR = "/app"
OUT = "/logs/agent"   # Harbor が <試み>/agent に写す置き場
PRO_SECONDS = 3000    # 課題の task.toml の [agent] timeout_sec（Pro の README の 50-minute budget）
OLD_WORKS = ("今の works は SWE-Bench Pro で回さない（#437 の運び役の決め）: 比べの相手（持ち主の決め public-bench-at-major）は"
             "素の Claude Code と前の版の工場で、今の works は段 4 で退ける（coexist-before-switch）。版を止めた works/dev/archon.sh が"
             "Archon を macOS arm64 の実行ファイル（archon-darwin-arm64）に止めていて、課題のコンテナ（linux/amd64）で回すには"
             "今の works を変えるしかない")
# 作業の段の網は api.anthropic.com だけが開く。この 2 つはそこへそのまま届き、中の工場の殻も素の claude -p も env から読む
ACCEPTED_AUTH = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
AUTH_REFUSED = "auth_refused"
SECRET, TASK, RESULT, PATCH, PREDICTION = "secret/auth.json", "task/task.json", "works-bench.json", "model.patch", "prediction.json"
INSIDE_STDOUT, INSIDE_STDERR = "inside.stdout", "inside.stderr"
DRIVER_FAILED = "driver_failed"
# 工場そのものが壊れて終わった結末（記録が読めない・節が落ちて線が進まなかった）。人を待っていないので stopped に入れない
BROKE = ("record_invalid", "interrupted")
REPO_TAR, REPO_STEP = "repo.tar", "repo"
UV_VERSION, BUN_VERSION = "0.11.29", "1.4.3"
INSTANCE = re.compile(r"^instance_(.+?)__(.+?)-[0-9a-f]{40}")
# 各リポジトリの課題の tests/run_script.sh の run_all_tests で一番多い形。課題ごとの隠した試験の名は含めない。工場は test_cmd を
# Archon の作業ツリーの根で走らせるので、パスは相対にする
TEST_COMMANDS = {
    "ansible/ansible": "PYTHONPATH=lib:test/lib python -m pytest test/units -q",
    "internetarchive/openlibrary": "PYTHONPATH=. OL_CONFIG=conf/openlibrary.yml python -m pytest . --ignore=infogami "
                                   "--ignore=vendor --ignore=node_modules --ignore=tests/integration -q",
    "qutebrowser/qutebrowser": "QT_QPA_PLATFORM=offscreen dbus-run-session -- python -m pytest -q --disable-warnings "
                               "--benchmark-disable --deselect=tests/end2end/ --deselect=tests/unit/browser/ "
                               "--deselect=tests/unit/javascript/ tests/unit",
}


class BenchError(Exception):
    pass


# ---------------------------------------------------------------- 課題の入力
def instance_of(image: str) -> str:
    """課題のイメージ ghcr.io/scaleapi/swe-bench_pro-v2:<instance_id> の tag"""
    _, colon, tag = image.rpartition(":")
    if not colon or not tag:
        raise BenchError(f"課題のイメージ {image} に instance_id の tag が無い")
    return tag


def repo_of(instance_id: str) -> str:
    found = INSTANCE.match(instance_id)
    if not found:
        raise BenchError(f"instance_id {instance_id} が instance_<org>__<repo>-<commit> の形でない")
    return f"{found[1]}/{found[2]}"


def task_inputs(instruction: str, image: str) -> dict:
    """依頼の行は 1 つ。where にパスを書かない（変わるファイルは正解の patch にしか無く、書けば答えを漏らす）"""
    instance_id = instance_of(image)
    repo = repo_of(instance_id)
    if repo not in TEST_COMMANDS:
        raise BenchError(f"{repo} の課題は回さない。SWE-Bench Pro V2 は Python の 3 リポジトリ（{' '.join(TEST_COMMANDS)}）だけを回す")
    return {"instance_id": instance_id, "repo": repo, "request": [{"where": f"SWE-Bench Pro V2 {instance_id}", "text": instruction}],
            "test_cmd": TEST_COMMANDS[repo]}


# ---------------------------------------------------------------- 殻が打つ命令
def _paths(place: str) -> dict:
    return {"bin": f"{place}/bin", "bun": f"{place}/bun", "python": f"{place}/python", "home": f"{place}/user-home"}


def tool_env(place: str) -> str:
    """setup の命令の頭の env の字。課題の道具を PATH の先に置き、工場の道具を後ろに足す"""
    p = _paths(place)
    return f'HOME={p["home"]} PATH="$PATH:{p["bin"]}:{p["bun"]}/bin" UV_PYTHON_INSTALL_DIR={p["python"]}'


def setup_commands(claude_version: str, place: str = PLACE) -> list[tuple[str, str]]:
    """(名, 命令)。殻が順に root で打つ。名 REPO_STEP の前に、殻が工場の写し <place>/repo.tar を上げる"""
    p, env = _paths(place), tool_env(place)
    packages = "ca-certificates curl git bubblewrap socat procps unzip"
    archive = ("sed -i -e 's|deb.debian.org/debian-security|archive.debian.org/debian-security|g' "
               "-e 's|security.debian.org|archive.debian.org|g' -e 's|deb.debian.org|archive.debian.org|g' -e '/-updates/d' "
               "/etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null")
    plugins = [(name, entry["marketplace"], entry["marketplace_repo"])
               for name, entry in json.loads((ROOT / "bin" / "_lib" / "borrow" / "borrow.json").read_text(encoding="utf-8")).items()
               if entry.get("kind") == "plugin" and entry.get("marketplace_repo")]
    return [
        ("place", f"mkdir -p {p['bin']} {p['home']} {place}/task {place}/secret && chmod 700 {place}/secret"),
        ("apt", f"export DEBIAN_FRONTEND=noninteractive; "
                f"fetch() {{ apt-get \"$@\" update && apt-get \"$@\" install -y --no-install-recommends {packages}; }}; "
                f"fetch || {{ {archive}; fetch -o Acquire::Check-Valid-Until=false; }}; "
                f"for tool in curl git bwrap socat; do command -v \"$tool\" >/dev/null || {{ echo \"$tool が無い\" >&2; exit 1; }}; done"),
        ("uv", f"curl -LsSf https://astral.sh/uv/{UV_VERSION}/install.sh | env UV_INSTALL_DIR={p['bin']} UV_NO_MODIFY_PATH=1 sh "
               f"&& {p['bin']}/uv --version"),
        ("python", f"export UV_PYTHON_INSTALL_DIR={p['python']}; {p['bin']}/uv python install 3.12 --no-bin "
                   f"&& ln -sf \"$({p['bin']}/uv python find --managed-python 3.12)\" {p['bin']}/python3.12 "
                   f"&& {p['bin']}/python3.12 --version"),
        ("bun", f"curl -fsSL https://bun.sh/install | env BUN_INSTALL={p['bun']} bash -s bun-v{BUN_VERSION} "
                f"&& {p['bun']}/bin/bun --version"),
        ("claude", f"curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s {shlex.quote(claude_version)} "
                   f"&& ln -sf /root/.local/bin/claude {p['bin']}/claude && {p['bin']}/claude --version"),
        (REPO_STEP, f"mkdir -p {place}/repo && tar -xf {place}/{REPO_TAR} -C {place}/repo && rm -f {place}/{REPO_TAR}"),
        # 殻は命令に依らず先に Archon の源を取り置く（止めた commit の clone と bun install）。網の開いた setup で済ませる
        ("archon", f"cd {p['home']} && env {env} WORKS_FACTORY_NO_AUTH=1 {p['bin']}/python3.12 {place}/repo/bin/works-factory version"),
        # bin/_lib/toolset.py の install は借りるプラグインが利用者の installed_plugins.json に無いと止まる
        ("plugin", " && ".join(f"cd {p['home']} && env {env} claude plugin marketplace add {repo} "
                               f"&& env {env} claude plugin install {name}@{market}" for name, market, repo in plugins)),
        # 役の節は sandbox の failIfUnavailable: true を持つ。立たなければ何時間も回す前に落とす
        ("sandbox", "bwrap --ro-bind / / --unshare-user --unshare-net true "
                    "|| { echo 'Claude Code の sandbox（bwrap）がコンテナで立たない' >&2; exit 1; }"),
    ]


def inside_command(producer: str, place: str = PLACE) -> str:
    return shlex.join([f"{place}/bin/python3.12", f"{place}/repo/tests/calibration/swepro.py", "inside", producer])


def capture_command(workdir: str, out: str) -> str:
    """作り手に依らず同じ口で /app の変更を予測に取る（Pro の locked_claude_code.py の _CAPTURE と同じ意味）。
    取れなければ model.patch を残さず終了の値 1（途中まで書いた空の patch を未解決と読ませない）"""
    w, o = shlex.quote(workdir), shlex.quote(out)
    return (f"mkdir -p {o} && cd {w} && git add -A && git diff --cached > {o}/{PATCH} || {{ rm -f {o}/{PATCH}; failed=1; }}; "
            f"git -C {w} reset -q; exit ${{failed:-0}}")


# ---------------------------------------------------------------- コンテナの中の起こし役
def auth_refused(got: dict | None, why: str | None, env) -> str:
    """auth_launch.resolve の結果をコンテナへ運べるか。運べるなら空の字、断るなら訳（値は書かない）"""
    if got is None:
        return f"認証が無い: {why}"
    other = sorted(k for k in got if k not in ACCEPTED_AUTH and not (k in claude_auth.FLAGS and got[k] in claude_auth.OFF))
    if other:
        return (f"{' '.join(other)} は受けない（受けるのは {' か '.join(ACCEPTED_AUTH)}）: 届け先が api.anthropic.com でないか"
                "別の資格が要り、課題のコンテナの網（--allow-agent-host api.anthropic.com）では届かない")
    if env.get("ANTHROPIC_BASE_URL"):
        return ("ANTHROPIC_BASE_URL が在る: ゲートウェイに向けた資格は api.anthropic.com に通らず、課題のコンテナの網も"
                "ゲートウェイへは開いていない")
    return ""


def child_env(place: str, auth: dict, base: dict) -> dict:
    p = _paths(place)
    return {**base, "HOME": p["home"], "PATH": os.pathsep.join(filter(None, [base.get("PATH"), p["bin"], f"{p['bun']}/bin"])),
            "UV_PYTHON_INSTALL_DIR": p["python"],
            "IS_SANDBOX": "1",   # root で bypassPermissions を許す（Harbor の upstream の claude_code.py と同じ）
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",   # 作業の段の網は api.anthropic.com だけが開く
            **auth}


def stopped(state: str, outcome: str) -> bool:
    """無人の run が人に聞いて止まった（承認ノードで待った・結末の種が人待ち）"""
    return state == "paused" or report.OUTCOME_KINDS.get(outcome) == chain.KIND_HUMAN


def status(workdir: Path) -> str:
    return subprocess.run(["git", "-C", str(workdir), "status", "--porcelain=v1", "--untracked-files=all"],
                          capture_output=True, text=True, encoding="utf-8").stdout


# 作り手の起こし方。どれも got（起こし役の結果）を埋め、落ちた作り手は got["error"] に訳を書く。起動の前に分かる欄（inputs・
# env_names）を先に置くので、run.Stop で抜けても結果に残る
def plain_fix(attempt: Path, workdir: Path, out: Path, task: dict, got: dict):
    """素の Claude Code（ハーネスの基準）。/app で claude -p を 1 回、instruction そのものを渡して直させる"""
    plain = run.PlainClaude()
    got.update(inputs=["instruction"], env_names=list(run.PlainClaude.ISOLATED_ENV), provenance=plain.provenance())
    env = plain.isolated_env(attempt)
    mine = attempt / "out"   # run.PlainClaude が結果を読む置き場
    mine.mkdir(exist_ok=True)
    with (mine / run.PlainClaude.RESULT).open("wb") as result:
        subprocess.run(plain.claude_args(task["request"][0]["text"]), cwd=workdir, env=env, stdin=subprocess.DEVNULL,
                       stdout=result)
    shutil.copy2(mine / run.PlainClaude.RESULT, out / run.PlainClaude.RESULT)
    session = plain.find_run(attempt)
    ended = plain.ended(mine)
    got.update(run_id=session, state=plain.state(attempt, session or ""), outcome=ended["outcome"],
               factory_seconds=ended["seconds"], usd=ended["usd"], usd_from=ended["usd_from"])
    if got["state"] != run.DONE:
        said = run._object(run._read_json(mine, run.PlainClaude.RESULT)).get("result")
        got["error"] = f"claude -p が誤りで終わった: {apply.one_line(str(said or '結果の JSON が無い'))}"


def drive_factory(attempt: Path, workdir: Path, out: Path, task: dict, got: dict):
    """工場を前で回し、終わった run の封じた差分を当てる。止まった run は答えず resume もしない"""
    producer = run.WorksFactory({"test_cmd": task["test_cmd"]})
    got.update(inputs=list(producer.input_pairs(attempt, "")), test_cmd=task["test_cmd"], env_names=producer.env_names(),
               provenance={"archon": pack.load(ROOT)["archon"]["commit"]})
    before = status(workdir)
    run_id = producer.start(attempt, "")
    state = producer.state(attempt, run_id) if run_id else "failed"
    got.update(run_id=run_id, state=state)
    if state == "paused":
        got["gate"] = producer.gate(attempt, run_id)
        return
    if state != run.DONE:
        got["error"] = (f"工場の run {run_id} が {state} で終わった" if run_id
                        else f"工場の run が起きなかった（家 {attempt / 'home'} に run が無い）")
        return
    ended = producer.finish(attempt, run_id)
    shutil.copytree(attempt / evidence.EVIDENCE, out / evidence.EVIDENCE, symlinks=True, dirs_exist_ok=True)
    got.update(outcome=ended["outcome"], factory_seconds=ended["seconds"], usd=ended["usd"], usd_from=ended["usd_from"],
               children=ended["children"], target_changed_during_run=status(workdir) != before)
    said_out, said_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said_out), contextlib.redirect_stderr(said_err):
        code = apply.main([run_id, "--cwd", str(workdir), "--allow-delete", "--allow-stopped"],
                          get=lambda rid, _target: evidence.launch(attempt, "get", rid, "--json", shell=producer.shell))
    lines = [line for line in (said_err.getvalue() + said_out.getvalue()).splitlines() if line.strip()]
    got["apply"] = {"code": code, "line": lines[0] if lines else ""}
    if code != 0 and meant_to_deliver(attempt / evidence.EVIDENCE):
        got["error"] = f"封じた差分が当たらない: {got['apply']['line']}"
    if not got.get("error") and ended["outcome"] in BROKE:
        got["error"] = f"工場の run {run_id} が結末 {ended['outcome']} で終わった（工場が壊れた）"


def meant_to_deliver(ev: Path) -> bool:
    """run が封じた差分を渡すつもりで終わった（封じた・R2 が作り直しを言っていない）。apply がそれを拒めば作り手の落ち"""
    record = run._object(run._read_json(ev, "record/parent.json"))
    value = run._object(run._object(record.get("terminal_record")).get("returns")).get("value")
    value = value if isinstance(value, dict) else {}
    return run._object(value.get("sealed")).get("ok") is True and value.get("r2_status") != apply.seal.REDESIGN


PRODUCERS = {run.WorksFactory.name: drive_factory, run.PlainClaude.name: plain_fix}


def chosen(producer: str) -> str:
    if producer == run.OldWorks.name:
        raise ValueError(OLD_WORKS)
    if producer not in PRODUCERS:
        raise ValueError(f"作り手 {producer} を知らない（{' か '.join(PRODUCERS)}）")
    return producer


def inside(args) -> int:
    place, workdir, out = Path(args.place), Path(args.workdir), Path(args.out)
    secret = place / SECRET
    try:
        auth = json.loads(secret.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"swepro.py: 認証のファイル {secret} を読めない（殻が上げる）: {type(e).__name__}", file=sys.stderr)
        return run.REFUSED
    finally:
        secret.unlink(missing_ok=True)
    if not (isinstance(auth, dict) and auth and set(auth) <= set(ACCEPTED_AUTH) and all(isinstance(v, str) for v in auth.values())):
        print(f"swepro.py: 認証のファイル {secret} が {' か '.join(ACCEPTED_AUTH)} の名と字の値の object でない", file=sys.stderr)
        return run.REFUSED
    task = json.loads((place / TASK).read_text(encoding="utf-8"))
    added = child_env(str(place), auth, {"PATH": os.environ.get("PATH", "")})
    os.environ.update(added)
    attempt = place / "attempt"
    (attempt / "home").mkdir(parents=True, exist_ok=True)
    if not (attempt / "target").is_symlink():
        (attempt / "target").symlink_to(workdir)
    (attempt / "request.json").write_text(json.dumps(task["request"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out.mkdir(parents=True, exist_ok=True)
    result = {"instance_id": task["instance_id"], "producer": args.producer, "error": None}
    code = run.OK
    try:
        PRODUCERS[args.producer](attempt, workdir, out, task, result)
    except run.Stop as e:
        result.setdefault("state", "failed")
        result["error"] = str(e)
        code = run.STOPPED
    result["env_names"] = sorted({*added, *result.get("env_names", [])})
    result["provenance"] = {**result.get("provenance", {}), "claude_code": run._claude_version(launcher.real_claude(os.environ))}
    (out / RESULT).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if result["error"]:
        print(f"swepro.py: {result['error']}", file=sys.stderr)
    return code


# ---------------------------------------------------------------- 予測と数え
def stop_why(state: str, outcome: str, gate: str | None, captured: bool) -> str:
    """止まった訳（止まっていなければ空）"""
    if not captured:
        return f"{WORKDIR} の変更を {PATCH} に取れなかった（変更は {WORKDIR} に残る）"
    if state == "paused":
        return f"承認ノード {gate} で待った"
    return f"結末 {outcome}" if stopped(state, outcome) else ""


def prediction(instance_id: str, producer: str, patch: str | None, result: dict | None, seconds: float | None,
               factory_commit: str | None) -> dict:
    """result が None なら起こし役が結果を書けずに落ちた。patch が None なら /app の変更を取れなかった。
    seconds は殻が exec の前後で測った秒（作り手に依らず同じ物差し）"""
    wrote = isinstance(result, dict)
    got = result if wrote else {}
    state, outcome = got.get("state") if wrote else DRIVER_FAILED, got.get("outcome") or ""
    error = got.get("error") if wrote else "起こし役 swepro.py inside が結果を書かずに終わった"
    why = stop_why(state, outcome, got.get("gate"), patch is not None)
    return {**got, "instance_id": instance_id, "producer": producer, "model_patch": patch, "state": state, "outcome": outcome,
            "usd": got.get("usd"), "error": error, "failed": bool(error), "stopped": bool(why), "stop_why": why,
            "seconds": seconds, "pro_limit": {"seconds": PRO_SECONDS, "over": None if seconds is None else seconds > PRO_SECONDS},
            "provenance": {**(got.get("provenance") or {}), "factory_commit": factory_commit}}


def tally(job: Path) -> dict:
    rows = []
    for path in sorted(job.glob(f"*/agent/{PREDICTION}")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise BenchError(f"予測 {path} を読めない: {e}") from None
        if not isinstance(row, dict):
            raise BenchError(f"予測 {path} が object でない")
        rows.append(row)
    usd = [r["usd"] for r in rows if run._number(r.get("usd")) is not None]
    return {"producers": sorted({str(r.get("producer")) for r in rows}), "tasks": len(rows),
            "stopped": sum(bool(r.get("stopped")) for r in rows), "failed": sum(bool(r.get("failed")) for r in rows),
            "over_pro_limit": sum((r.get("pro_limit") or {}).get("over") is True for r in rows),
            "empty_patch": sum(isinstance(r.get("model_patch"), str) and not r["model_patch"].strip() for r in rows),
            "unmeasured_seconds": sum(r.get("seconds") is None for r in rows),
            "usd": round(sum(usd), 6), "usd_missing": len(rows) - len(usd)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SWE-Bench Pro V2 の Python の課題を課題のコンテナの中で回す")
    sub = parser.add_subparsers(dest="command", required=True)
    driven = sub.add_parser("inside")
    driven.add_argument("producer", choices=sorted(PRODUCERS))
    driven.add_argument("--workdir", default=WORKDIR)
    driven.add_argument("--place", default=PLACE)
    driven.add_argument("--out", default=OUT)
    counted = sub.add_parser("tally")
    counted.add_argument("job", type=Path)
    args = parser.parse_args(argv)
    if args.command == "inside":
        return inside(args)
    try:
        print(json.dumps(tally(args.job), ensure_ascii=False))
    except BenchError as e:
        print(f"swepro.py: {e}", file=sys.stderr)
        return run.STOPPED
    return run.OK


if __name__ == "__main__":
    sys.exit(main())
