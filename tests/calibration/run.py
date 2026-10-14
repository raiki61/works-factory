"""公開ベンチ GitHub ReviewBench の Python の課題を 3 つの作り手で無人で回し、判定役の入力・変換の控え・ノードごとの表を残す
（運び役が命令として打つ道具。試験のモジュールではない）。持ち主の決め public-bench-at-major（docs/owner-decisions.md）。

    python3 tests/calibration/run.py run <works|works-factory|claude> --bench <ReviewBench の写し> --attempts <置き場> --out <置き場>
        [--language Python] [--only <課題の鍵,…>] [--resume] [--dry-run] [--mirror <取り先の型>]
    python3 tests/calibration/run.py judge <作り手> --bench <ReviewBench の写し> --out <置き場> [--model claude-sonnet-5]
    python3 tests/calibration/run.py convert <作り手> --attempts <置き場> --out <置き場> [--only <課題の鍵,…>]
    python3 tests/calibration/run.py nodes <作り手> --out <置き場>

作り手: works-factory（殻 bin/works-factory で works-factory-line を前で回す）・works（今の works の dev/use.sh。版は pack.json の
works.commit、置き場は環境変数 WORKS_FACTORY_OLD_WORKS）・claude（素の Claude Code を同じ模型・effort で claude -p 1 回）。

1 件の流れ: manifest の行の base と head を ReviewBench の mirror（--mirror。既定は reviewbench.MIRROR）から <置き場>/.repos/ の
写しに取り、試みのフォルダ <置き場>/<課題の鍵>--<n>/ を組む（target/ は head を取り出し refs/bench/base が base、origin/ は同じ物の
bare、request.json は PR の題と本文の 1 行、pr/ は diff.patch と pr.json、home/ は作り手の家）。作り手を base を渡して前で起こし、
終わりまで待ち、記録を試みの evidence/ に写し、指摘の一覧に変えて <out>/<作り手>/findings/<鍵>.json（判定役の入力）と
<out>/<作り手>/convert/<鍵>.json（変換の控え。捨てた指摘・ノード・最後の差分に入ったか）に書き、置き場の台帳
<置き場>/ledger.jsonl に 1 行足す。judge は ReviewBench の写しの中で npm run judge を打ち、<out>/<作り手>/scoring/ に書く（判定役は
環境変数 ANTHROPIC_API_KEY を読む）。
convert は台帳で済んだ課題の試みの evidence/ と target/（head の版で番地を照らす）から変換だけをやり直して findings/ と convert/ を
書き直す（run を起こさない。来歴と web_calls は前の控えから引き継ぐ。target/ で head を読めなければ書き換えずに止まる）。
nodes は控えと出来事から <out>/<作り手>/nodes.json・nodes.md を書く。

- 終了の値: 0 済んだ・1 止まった（後ろの課題を起こさない。--resume で続ける）・2 何も起こさずに断った。
- --resume は台帳で済んだ課題を飛ばし、終わっていない run を持つ課題をその run の続きから回す。--resume 無しは名指した課題を
  全部新しい試みで回し、終わっていない run を持つ課題に当たれば断る（費用を二重に使わない）。
- 期限を置かない（持ち主の決め no-timeouts）。ベンチの 1 件の上限は超えた事実を控えに残すだけ。自分を切り離さない。承認ノードには
  答えない（今の works の続きだけは、use.sh start の無人の末尾と同じく人が決める承認に stop と答えて報告へ進める）。run を止めない。
- 無人の止め（needs_human など。Archon の run は completed）は、そこまでの出力から変換する。
- 漏れの塞ぎ: 3 つとも gh の認証を渡さない（子の env から hostgh.TOKENS を外し、GH_CONFIG_DIR を試みの home/gh-none の空の置き場に
  向ける）。WebFetch・WebSearch は隔離した設定の settings.json の permissions（toolset.DENY_WEB）で拒む。works-factory は
  WORKS_FACTORY_DENY_WEB=1 で殻の toolset に置かせ、素の Claude Code はランナーが置く。今の works は版を止めた toolset の柵が
  permissions を拒むので塞げず、控えの leak_guard に書く。
- 錠は --attempts の置き場ごとに 1 つ（<置き場>/.lock）。アカウントは各作り手の起動が読む環境変数（WORKS_FACTORY_KEYCHAIN_ITEM・
  WORKS_KEYCHAIN_ITEM）をそのまま子に継ぐ。値は読まず、出さない。
- 試験の差し替え口は環境変数 WORKS_CALIBRATION_SHELL の 1 つだけ: works-factory の起動の殻（既定は bin/works-factory）を替える。

今の works の記録の置き場と形（その版の works/dev/use.sh・lib.sh・archon.sh・canary_check.py と .shared/core/report.py で確かめた）:
- 家は WORKS_USE_HOME=<試み>/home。use.sh start は無人（WORKS_USE_UNATTENDED=1）なら起動の承認を越えて残りをその場で回し、人が
  決める承認に着けば自分で stop と答えて報告へ進める。run の控えは <家>/runs/<run-id>.json で、試みごとにちょうど 1 つ。
- run の行は <家>/archon-home/archon.db の表 remote_agent_workflow_runs、出来事は remote_agent_workflow_events。出力の置き場
  （board）は run の行の output_root の下の artifacts/runs/<id>/board。
- 結末の語は board の report.md の頭 10 行のうち「起きたこと: 」で始まる行の（<語>）。
- use.sh wait の終了の値: 0 承認で待つ・3 まだ走る（決まった秒数で戻るだけで run の期限ではない）・5 終わった・1 落ちた・6 周の鎖。
- 続ける命令は対象で WORKS_DEV_HOME=<家> sh dev/continue.sh dev/archon.sh workflow resume <run>。続きが人が決める承認で止まれば
  workflow respond <run> stop <一言> と答えて終わりまで待つ。
"""
import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))   # 頭に入れると lib/tests が根の tests を隠す（tests/AGENTS.md）
from bin._lib import hostgh, isolate, launcher, pack, toolset  # noqa: E402
import judge_accept  # noqa: E402
import reads  # noqa: E402
from report import OUTCOMES  # noqa: E402
from tests.calibration import nodes, reviewbench  # noqa: E402
from tests.calibration.reviewbench import Source  # noqa: E402
from tests.e2e import evidence, make_target  # noqa: E402

SHELL_ENV = "WORKS_CALIBRATION_SHELL"
OLD_WORKS_ENV = "WORKS_FACTORY_OLD_WORKS"
LINE = "works-factory-line"
OK, STOPPED, REFUSED = 0, 1, 2
# 無人の入力（#214 と同じ値。手厚さは既定）。test_cmd・tdd_suite は課題ごとに違うので渡さず、工場が自分で探す
BENCH_INPUTS = {"unattended": "true", "final_gate": "when_needed"}
LEDGER = "ledger.jsonl"
LOCK = ".lock"
REPOS = ".repos"
DONE = "done"
OPEN = ("started", "stopped", "paused")   # 台帳の状態のうち run を持ちうる物。prepared（試みを作る途中で落ちた）は新しい試みで回し直す
WAIT_RUNNING = 3
UNATTENDED_STOP = "無人の run（WORKS_USE_UNATTENDED=1）: 人が決める承認に着いたので止めて報告へ"   # use.sh start の無人の末尾の文
STATES = {"running": "running", "pending": "running", "paused": "paused", "completed": DONE}   # Archon の run の status → run_one の分かれ
# get --verbose の記録は --events を足すと nodes を落とすので、出来事の列は記録とは別のファイルに写す
EVENTS = "record/{name}-events.json"
WITHHELD = {"web": "denied", "gh": "withheld"}
JUDGE_MODEL = "claude-sonnet-5"   # 公開の採点と同じ判定役の模型（ReviewBench の docs/OFFLINE_EVAL.md）
KEY_LINE = "判定役が API キーを要るなら、作るかは持ち主の決め（#435）"
# 素の Claude Code の模型と effort は、works-factory の判定の中心の役（workflows/judge/works-factory-judge.yaml の diagnose）と同じ。
# 持ち主の言葉「同じ模型・effort」の基準を run ごとに揺らさないため、旗で選ばせない
PLAIN_MODEL, PLAIN_EFFORT = "opus", "high"
PLAIN_PROMPT = """You are reviewing a pull request. The current directory is the repository checked out at the pull request head (HEAD).
The change under review is `git diff $RB_BASE...HEAD`; the same diff is in the file $RB_DIFF, and the pull request metadata is in $RB_PR_JSON.

Review the change and report the problems it introduces. Write the result as JSON to the file $RB_OUT in this shape:
{"pr": {"repo": ..., "pr_number": ..., "base": ..., "head": ...}, "agent": "claude", "findings": [{"file": ..., "start_line": ..., "end_line": ..., "message": ..., "producer": "claude"}]}
- Copy the pr fields from $RB_PR_JSON.
- file is relative to the repository root, uses forward slashes, and has no leading ./
- start_line and end_line are line numbers in the file at HEAD.
- One finding per problem. message says what is wrong and why it matters.
- Write an empty findings array if you find no problems.

Do not modify any file in the repository."""


class Stop(Exception):
    def __init__(self, code: int, line: str):
        super().__init__(line)
        self.code = code


def bench_env(attempt: Path) -> dict:
    """3 つの作り手の起動の土台の env。gh の認証を渡さず、WebFetch・WebSearch の拒みを頼む"""
    env = {k: v for k, v in os.environ.items() if k not in hostgh.TOKENS}
    none = attempt / "home" / "gh-none"
    none.mkdir(parents=True, exist_ok=True)
    return {**env, "GH_CONFIG_DIR": str(none), toolset.DENY_WEB_ENV: "1"}


class WorksFactory:
    """このリポジトリの工場。殻 bin/works-factory で Archon のグラフ works-factory-line を前で回す"""
    name = "works-factory"
    account = "WORKS_FACTORY_KEYCHAIN_ITEM"
    archon = True
    # 再審が走った run は rejudge/judgment.json が 1 回目の units を置き換える（lib/judge_accept.py の rejudge_take）
    sources = (Source(f"parent/{judge_accept.JUDGE_DIR}/{judge_accept.JUDGMENT_FILE}", ("units",), "units",
                      prefer=f"parent/{judge_accept.REJUDGE_DIR}/{judge_accept.JUDGMENT_FILE}"),
               Source("parent/eyes/r1.json", ("deletions",), "items", "why"),
               Source("parent/eyes/r4.json", ("surfaced",), "items", "text"))
    leak_guard = WITHHELD

    def __init__(self, inputs: dict | None = None):
        self.shell = Path(os.environ.get(SHELL_ENV) or ROOT / "bin" / "works-factory")
        self.inputs = {**BENCH_INPUTS, **(inputs or {})}
        self.last_said = ""   # 最後の start の出力の最後の行。run が起きなかった時の Archon の断りはここにだけ在る

    def check(self):
        pass

    def env_names(self) -> list[str]:
        return [launcher.HOME_ENV, "GH_CONFIG_DIR", toolset.DENY_WEB_ENV]

    def input_pairs(self, attempt: Path, base: str) -> dict[str, str]:
        return {"request": str(attempt / "request.json"), "base": base, **self.inputs}

    def start_command(self, attempt: Path, base: str) -> list[str]:
        return [sys.executable, str(self.shell), "workflow", "run", LINE, "--cwd", str(attempt / "target"),
                *[part for k, v in self.input_pairs(attempt, base).items() for part in ("--input", f"{k}={v}")]]

    def resume_command(self, attempt: Path, run_id: str) -> list[str]:
        return [sys.executable, str(self.shell), "workflow", "resume", run_id, "--cwd", str(attempt / "target")]

    def _launch(self, attempt: Path, command: list[str]) -> str:
        """殻を起こし、標準出力と標準エラーを混ぜて自分の標準出力へそのまま流す。返すのは出力の最後の空でない行"""
        last = ""
        with subprocess.Popen(command, cwd=attempt / "home", env={**bench_env(attempt), launcher.HOME_ENV: str(attempt / "home")},
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace") as shell:
            for line in shell.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                last = line if line.strip() else last
        return last.strip()

    def start(self, attempt: Path, base: str) -> str | None:
        self.last_said = self._launch(attempt, self.start_command(attempt, base))
        return self.find_run(attempt)

    def find_run(self, attempt: Path) -> str | None:
        parents = [r["id"] for r in self._runs(attempt) if not r.get("parent_run_id")]
        if len(parents) > 1:
            raise Stop(STOPPED, f"家 {attempt / 'home'} に親の run が {len(parents)} 本在る（1 本のはず）: {parents}")
        return parents[0] if parents else None

    def _runs(self, attempt: Path) -> list[dict]:
        try:
            return evidence.runs(attempt, self.shell)
        except evidence.Stop as e:
            raise Stop(STOPPED, f"家 {attempt / 'home'} の run を読めない: {e}") from None

    def _get(self, attempt: Path, run_id: str, *flags: str, what: str = "の記録を読めない") -> dict:
        try:
            got = evidence.read_json(attempt, "get", run_id, "--json", *flags, shell=self.shell)
        except evidence.Stop as e:
            raise Stop(STOPPED, f"run {run_id} {what}: {e}") from None
        if not isinstance(got, dict):
            raise Stop(STOPPED, f"run {run_id} {what}: workflow get の返す値が dict でない")
        return got

    def state(self, attempt: Path, run_id: str) -> str:
        return _state(self._get(attempt, run_id).get("status"))

    def gate(self, attempt: Path, run_id: str) -> str:
        for rid in [run_id, *evidence.children(self._runs(attempt), run_id)]:
            got = self._get(attempt, rid)
            node = ((got.get("metadata") or {}).get("approval") or {}).get("nodeId")
            if got.get("status") == "paused" and node:
                return node if rid == run_id else f"{node}（子の run {rid}）"
        return "（記録に承認ノードの名が無い）"

    def resume(self, attempt: Path, run_id: str):
        self._launch(attempt, self.resume_command(attempt, run_id))

    def finish(self, attempt: Path, run_id: str) -> dict:
        try:
            kept = evidence.collect(attempt, run_id, self.shell)
        except evidence.Stop as e:
            raise Stop(STOPPED, f"run {run_id} の記録を evidence/ に写せない: {e}") from None
        for limit in kept["limits"]:
            print(f"run.py: {limit}（その置き場から読む指摘は控えの unread に出る）", file=sys.stderr)
        ev = attempt / evidence.EVIDENCE
        for name, rid in kept["named"]:
            got = self._get(attempt, rid, "--verbose", "--events", what="の出来事の列を evidence/ に写せない")
            (ev / EVENTS.format(name=name)).write_text(
                json.dumps({"events": _events(got)}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return {**self.ended(ev), "children": kept["children"], "web_calls": web_calls(attempt)}

    @staticmethod
    def ended(ev: Path) -> dict:
        got = _object(_read_json(ev, "record/parent.json"))
        value = _object(_object(got.get("terminal_record")).get("returns")).get("value")
        outcome = value.get("outcome") if isinstance(value, dict) else None
        return {"outcome": outcome if isinstance(outcome, str) else "",
                "seconds": _span(_events(_read_json(ev, EVENTS.format(name="parent"))), got.get("completed_at")),
                "usd": _number(_object(got.get("metadata")).get("total_cost_usd")),
                "usd_from": "run の記録の metadata.total_cost_usd（fix の組の子の run の費用を含む）"}

    @staticmethod
    def node_runs(ev: Path) -> list[tuple[str, list[dict], str]]:
        """(グラフの名, 出来事, ノードの id の頭)。親は頭なし、子は <子のグラフの短い名>/"""
        out = []
        for path in sorted((ev / "record").glob("*.json"), key=lambda p: (p.stem != "parent", p.stem)):
            if path.stem.endswith("-events"):
                continue
            workflow = str(_object(_read_json(ev, path.relative_to(ev))).get("workflow_name") or "")
            events = _events(_read_json(ev, EVENTS.format(name=path.stem)))
            out.append((workflow, events, "" if path.stem == "parent" else f"{nodes.short(workflow)}/"))
        return out

    @staticmethod
    def final_diff(ev: Path) -> tuple[Path | None, str | None]:
        diff = ev / "parent" / "merge" / "sealed.diff"
        return (diff, None) if diff.is_file() else (None, "封じの前で止まった run（parent/merge/sealed.diff が無い）")

    def provenance(self) -> dict:
        return {"factory_commit": make_target.git("-C", str(ROOT), "rev-parse", "HEAD"),
                "archon": pack.load(ROOT)["archon"]["commit"]}


def web_calls(attempt: Path) -> int | None:
    """隔離した設定の読んだ証拠の記録のうち、拒む道具（toolset.DENY_WEB）の行の数。記録の根が無いか、記録のどれかが読めなければ
    None（測れていない）。記録のフックは PostToolUse なので、拒まれた呼びは数に入らない"""
    root = reads.root(attempt / "home" / isolate.DIRS["CLAUDE_CONFIG_DIR"])
    if not root.is_dir():
        return None
    logs = [reads.records(log, "")[0] for log in root.rglob(reads.LOG)]
    if any(rows is None for rows in logs):
        return None
    return sum(reads.tool_count(rows, tool) for rows in logs for tool in toolset.DENY_WEB["deny"])


class OldWorks:
    """今の works。works/dev/use.sh で darkfactory を回す"""
    name = "works"
    account = "WORKS_KEYCHAIN_ITEM"
    archon = True
    passes = {"unattended": "WORKS_USE_UNATTENDED", "final_gate": "WORKS_USE_FINAL_GATE"}
    values = {"unattended": {"true": "1"}}
    sources = (Source("board/out/r1/p2.diagnose.json", ("units",), "units"),
               Source("board/out/r1/p1.local_review.json", ("findings", "*", "items"), "items", "text"))
    leak_guard = {"web": "open", "gh": "withheld",
                  "why": "版を止めた今の works の toolset の柵が settings.json の permissions を拒み、今の works は変えない"}

    def __init__(self):
        self.dir = Path(os.environ[OLD_WORKS_ENV]) if os.environ.get(OLD_WORKS_ENV) else None
        self.dev = self.dir / "dev" if self.dir else Path(f"${OLD_WORKS_ENV}") / "dev"
        self.inputs = dict(BENCH_INPUTS)

    def check(self):
        if self.dir is None:
            raise Stop(REFUSED, f"{OLD_WORKS_ENV} に今の works の置き場（works.commit を取り出した claude-plugins の works/）を渡す")
        want = pack.load(ROOT)["works"]["commit"]
        try:
            have = make_target.git("-C", str(self.dir), "rev-parse", "HEAD")
        except make_target.Stop as e:
            raise Stop(REFUSED, f"{OLD_WORKS_ENV} の HEAD を読めない: {e}") from None
        if have != want:
            raise Stop(REFUSED, f"今の works の置き場の HEAD {have} が pack.json の works.commit {want} と違う")
        changed = make_target.git("-C", str(self.dir), "status", "--porcelain", "--", ".")
        if changed:
            raise Stop(REFUSED, f"今の works の置き場に commit していない変更が在る（来歴の works.commit と回す物がずれる）: "
                                f"{' '.join(line[3:] for line in changed.splitlines())}")
        if not (self.dev / "use.sh").is_file():
            raise Stop(REFUSED, f"今の works の置き場に dev/use.sh が無い（{self.dev / 'use.sh'}）")

    def env_names(self) -> list[str]:
        return ["WORKS_USE_HOME", *self.passes.values(), "GH_CONFIG_DIR"]

    def _env(self, attempt: Path, inputs: dict) -> dict:
        return {**bench_env(attempt), "WORKS_USE_HOME": str(attempt / "home"),
                **{self.passes[k]: self.values.get(k, {}).get(v, v) for k, v in inputs.items()}}

    input_pairs = WorksFactory.input_pairs

    def start_command(self, attempt: Path, base: str) -> list[str]:
        pairs = self.input_pairs(attempt, base)
        return ["sh", str(self.dev / "use.sh"), "start", "--base", pairs["base"], "--", str(attempt / "target"), pairs["request"]]

    def continue_command(self, verb: str, run_id: str, *rest: str) -> list[str]:
        return ["sh", str(self.dev / "continue.sh"), str(self.dev / "archon.sh"), "workflow", verb, run_id, *rest]

    def start(self, attempt: Path, base: str) -> str | None:
        subprocess.run(self.start_command(attempt, base), cwd=attempt / "target", env=self._env(attempt, self.inputs),
                       stdin=subprocess.DEVNULL)
        run_id = self.find_run(attempt)
        if run_id:
            self._wait(attempt, run_id)
        return run_id

    def find_run(self, attempt: Path) -> str | None:
        kept = sorted((attempt / "home" / "runs").glob("*.json"))
        if len(kept) > 1:
            raise Stop(STOPPED, f"家 {attempt / 'home'} に run の控えが {len(kept)} 個在る（1 個のはず）")
        return kept[0].stem if kept else None

    def _wait(self, attempt: Path, run_id: str):
        """use.sh wait を、まだ走る（3）の間は上限なしに打ち直す。終わり・承認・落ちの判じは state が db から読む"""
        while subprocess.run(["sh", str(self.dev / "use.sh"), "wait", str(attempt / "target"), run_id],
                             cwd=attempt / "target", env=self._env(attempt, {}),
                             stdin=subprocess.DEVNULL).returncode == WAIT_RUNNING:
            pass

    def _row(self, attempt: Path, run_id: str) -> tuple[dict, list[dict]]:
        db = attempt / "home" / "archon-home" / "archon.db"
        if not db.is_file():
            raise Stop(STOPPED, f"run {run_id} の archon.db が無い（{db}）")
        try:
            con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                con.row_factory = sqlite3.Row
                row = con.execute("SELECT * FROM remote_agent_workflow_runs WHERE id = ?", (run_id,)).fetchone()
                events = con.execute("SELECT event_type, step_name, data, created_at FROM remote_agent_workflow_events "
                                     "WHERE workflow_run_id = ? ORDER BY event_order, rowid", (run_id,)).fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            raise Stop(STOPPED, f"run {run_id} の archon.db を読めない: {e}") from None
        if row is None:
            raise Stop(STOPPED, f"archon.db に run {run_id} の行が無い")
        return dict(row), [{**dict(e), "data": _json_or_text(e["data"])} for e in events]

    def state(self, attempt: Path, run_id: str) -> str:
        return _state(self._row(attempt, run_id)[0].get("status"))

    def gate(self, attempt: Path, run_id: str) -> str:
        approval = (_json_or_text(self._row(attempt, run_id)[0].get("metadata")) or {})
        node = (approval.get("approval") or {}).get("nodeId") if isinstance(approval, dict) else None
        return node or "（記録に承認ノードの名が無い）"

    def resume(self, attempt: Path, run_id: str):
        """続きを回し、人が決める承認に着けば use.sh start の無人の末尾と同じく stop と答えて報告へ進める"""
        self._continue(attempt, "resume", run_id)
        if self.state(attempt, run_id) == "paused":
            self._continue(attempt, "respond", run_id, "stop", UNATTENDED_STOP)

    def _continue(self, attempt: Path, verb: str, run_id: str, *rest: str):
        subprocess.run(self.continue_command(verb, run_id, *rest), cwd=attempt / "target",
                       env={**self._env(attempt, {}), "WORKS_DEV_HOME": str(attempt / "home")}, stdin=subprocess.DEVNULL)
        self._wait(attempt, run_id)

    def finish(self, attempt: Path, run_id: str) -> dict:
        row, events = self._row(attempt, run_id)
        board = Path(row.get("output_root") or "") / "artifacts" / "runs" / run_id / "board"
        out = evidence.fresh(attempt)
        (out / "record" / "parent.json").write_text(
            json.dumps({"run": row, "events": events}, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        if board.is_dir():
            shutil.copytree(board, out / "board", symlinks=True)
        else:
            print(f"run.py: run {run_id} の出力の置き場（{board}）が無い（そこから読む指摘は控えの unread に出る）", file=sys.stderr)
        return {**self.ended(out), "children": [], "web_calls": None}

    @staticmethod
    def ended(ev: Path) -> dict:
        got = _object(_read_json(ev, "record/parent.json"))
        run = _object(got.get("run"))
        usd = next((e["data"].get("cost_usd") for e in _events(got)
                    if e.get("event_type") == "workflow_completed" and isinstance(e.get("data"), dict)), None)
        return {"outcome": _header_outcome(ev / "board"),
                "seconds": _span(_events(got), run.get("completed_at")),
                "usd": _number(usd),
                "usd_from": "出来事 workflow_completed の data.cost_usd"}

    @staticmethod
    def node_runs(ev: Path) -> list[tuple[str, list[dict], str]]:
        got = _object(_read_json(ev, "record/parent.json"))
        return [(str(_object(got.get("run")).get("workflow_name") or ""), _events(got), "")]

    @staticmethod
    def final_diff(ev: Path) -> tuple[Path | None, str | None]:
        """直しの差分 board/fix-delta-r<N>.patch。左が head の版なのは 1 周目だけなので、ちょうど 1 つの時だけ使う"""
        found = sorted((ev / "board").glob("fix-delta-r*.patch"))
        if len(found) == 1:
            return found[0], None
        return None, "board/fix-delta-r*.patch が無い" if not found else "周が 2 つ以上で、後の周の番地が head でない"

    def provenance(self) -> dict:
        found = re.search(r'^ARCHON_VERSION="([^"]+)"', (self.dev / "archon.sh").read_text(encoding="utf-8"), re.M)
        return {"factory_commit": pack.load(ROOT)["works"]["commit"], "archon": found[1] if found else None}


class PlainClaude:
    """素の Claude Code（ハーネスの基準）。対象で claude -p を 1 回、審査だけを頼み、指摘を $RB_OUT に書かせる"""
    name = "claude"
    account = "WORKS_FACTORY_KEYCHAIN_ITEM"
    archon = False
    sources = (Source("findings.json", ("findings",), "findings"),)
    leak_guard = WITHHELD
    RESULT, FINDINGS = "claude-result.json", "findings.json"
    ISOLATED_ENV = ("HOME", "CLAUDE_CONFIG_DIR", "GH_CONFIG_DIR")
    INPUTS = ("RB_BASE", "RB_HEAD", "RB_DIFF", "RB_PR_JSON")   # 対象の入力。来歴の run_inputs はこれだけ
    RUN_ENV = (*INPUTS, "RB_OUT", "RB_AGENT")   # start が子に置く RB_* の全部。PLAIN_PROMPT が読む $RB_* はこの内

    def __init__(self):
        self.claude = launcher.real_claude(os.environ)

    def check(self):
        if not self.claude:
            raise Stop(REFUSED, f"claude が見つからない。PATH に置くか {launcher.CLAUDE_BIN_ENV} に絶対パスを設定する")

    def env_names(self) -> list[str]:
        return [*self.ISOLATED_ENV, *self.RUN_ENV]

    def claude_args(self, prompt: str) -> list[str]:
        """同じ模型・effort で web を断った claude -p 1 回。ReviewBench と SWE-Bench Pro の基準がここを共に引く"""
        return [self.claude or "claude", "--model", PLAIN_MODEL, "--effort", PLAIN_EFFORT, "--output-format", "json",
                "--permission-mode", "bypassPermissions", "--disallowedTools", *toolset.DENY_WEB["deny"], "-p", prompt]

    @staticmethod
    def isolated_env(attempt: Path) -> dict[str, str]:
        env = isolate.isolate(bench_env(attempt), attempt / "home")
        (Path(env["CLAUDE_CONFIG_DIR"]) / "settings.json").write_text(
            json.dumps({"permissions": toolset.DENY_WEB}, indent=2) + "\n", encoding="utf-8")
        return env

    def start_command(self, attempt: Path, base: str) -> list[str]:
        user = os.environ
        return [sys.executable, "-I", str(ROOT / "bin" / "_lib" / "auth_launch.py"), "exec", "--for", "works-factory",
                "--user-home", user.get("HOME", ""), "--user-config", user.get("CLAUDE_CONFIG_DIR", ""), "--",
                *self.claude_args(PLAIN_PROMPT)]

    def input_pairs(self, attempt: Path, base: str) -> dict[str, str]:
        pr = json.loads((attempt / "pr" / "pr.json").read_text(encoding="utf-8"))
        return dict(zip(self.INPUTS, (base, pr["head"], str(attempt / "pr" / "diff.patch"), str(attempt / "pr" / "pr.json")),
                        strict=True))

    def run_env(self, attempt: Path, base: str) -> dict[str, str]:
        return dict(zip(self.RUN_ENV, (*self.input_pairs(attempt, base).values(), str(attempt / "out" / self.FINDINGS), self.name),
                        strict=True))

    def start(self, attempt: Path, base: str) -> str | None:
        env = self.isolated_env(attempt)
        out = attempt / "out"
        out.mkdir(exist_ok=True)
        (out / self.FINDINGS).unlink(missing_ok=True)
        env.update(self.run_env(attempt, base))
        with (out / self.RESULT).open("wb") as result:
            subprocess.run(self.start_command(attempt, base), cwd=attempt / "target", env=env, stdin=subprocess.DEVNULL,
                           stdout=result)
        return self.find_run(attempt)

    def _result(self, attempt: Path) -> dict | None:
        doc = _read_json(attempt / "out", self.RESULT)
        return doc if isinstance(doc, dict) else None

    def find_run(self, attempt: Path) -> str | None:
        session = (self._result(attempt) or {}).get("session_id")
        return session if isinstance(session, str) and session else None

    def state(self, attempt: Path, run_id: str) -> str:
        """claude -p は認証の拒否・API の誤り・turn の上限でも session_id の付いた結果を書き、is_error で落ちを言う"""
        got = self._result(attempt)
        return DONE if got is not None and not got.get("is_error") else "failed"

    def gate(self, attempt: Path, run_id: str) -> str:
        return ""

    def resume(self, attempt: Path, run_id: str):
        self.start(attempt, json.loads((attempt / "pr" / "pr.json").read_text(encoding="utf-8"))["base"])

    def finish(self, attempt: Path, run_id: str) -> dict:
        ev = evidence.fresh(attempt)
        for name in (self.RESULT, self.FINDINGS):
            if (attempt / "out" / name).is_file():
                shutil.copy2(attempt / "out" / name, ev / name)
        return {**self.ended(ev), "children": [], "web_calls": None}

    @staticmethod
    def ended(ev: Path) -> dict:
        got = _object(_read_json(ev, PlainClaude.RESULT))
        ms = _number(got.get("duration_ms"))
        return {"outcome": "error" if got.get("is_error") else "done",
                "seconds": None if ms is None else ms / 1000,
                "usd": _number(got.get("total_cost_usd")),
                "usd_from": "claude -p の出力の total_cost_usd"}

    @staticmethod
    def node_runs(ev: Path) -> list:
        return []

    @staticmethod
    def final_diff(ev: Path) -> tuple[None, str]:
        return None, "審査だけを頼み、直さない"

    def provenance(self) -> dict:
        return {"model": PLAIN_MODEL, "effort": PLAIN_EFFORT}


HAPPENED = "起きたこと: "


def _header_outcome(board: Path) -> str:
    try:
        lines = (board / "report.md").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    for line in lines[:10]:
        if line.startswith(HAPPENED):
            return next((w for w in OUTCOMES if f"（{w}）" in line), "")
    return ""


def _read_json(ev: Path, path):
    """ev の中の JSON。無い・読めなければ None"""
    try:
        return json.loads((ev / path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _events(record: dict) -> list[dict]:
    events = _object(record).get("events")
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def _json_or_text(raw):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _span(events: list[dict], end) -> float | None:
    """Archon は再開のたびに run の行の started_at を書き直すので、run の始めは最初の出来事の時刻"""
    start = next((e["created_at"] for e in events if e.get("created_at")), None)
    try:
        began, ended = (datetime.datetime.fromisoformat(str(t).replace(" ", "T").replace("Z", "+00:00")) for t in (start, end))
        if (began.tzinfo is None) != (ended.tzinfo is None):
            return None
        return round((ended - began).total_seconds(), 3)
    except (TypeError, ValueError):
        return None


def _number(value) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _state(status) -> str:
    return STATES.get(status, "failed")


PRODUCERS = {c.name: c for c in (OldWorks, WorksFactory, PlainClaude)}


# ---------------------------------------------------------------- run
class Ledger:
    """置き場の台帳。課題と作り手ごとに最後の行が今の状態。絶対パスはここ（リポジトリの外）にだけ書く"""

    def __init__(self, attempts: Path):
        self.path = attempts / LEDGER

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def current(self, producer: str) -> dict[str, dict]:
        return {r["id"]: r for r in self.rows() if r["producer"] == producer}

    def last(self, task: str, producer: str) -> dict | None:
        return self.current(producer).get(task)

    def add(self, **row):
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**row, "at": _now()}, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _lock(attempts: Path) -> int:
    attempts.mkdir(parents=True, exist_ok=True)
    fd = os.open(attempts / LOCK, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Stop(REFUSED, f"置き場 {attempts} は別のランナーが使っている（錠 {attempts / LOCK}）。置き場を分けて起こす") from None
    return fd


def _outside(place: Path) -> Path:
    place = Path(os.path.realpath(place))
    if place.is_relative_to(Path(os.path.realpath(ROOT))):
        raise Stop(REFUSED, f"置き場 {place} がリポジトリの中に在る。リポジトリの外に置く")
    return place


def _tasks(args) -> list[dict]:
    try:
        found = reviewbench.tasks(args.bench, args.language)
    except reviewbench.BenchError as e:
        raise Stop(REFUSED, str(e)) from None
    if not args.only:
        return found
    wanted = [x for x in args.only.split(",") if x]
    known = {reviewbench.key(t) for t in found}
    unknown = [x for x in wanted if x not in known]
    if unknown:
        raise Stop(REFUSED, f"--only の {unknown} が manifest の {args.language} の課題に無い")
    return [t for t in found if reviewbench.key(t) in wanted]


def _attempt(attempts: Path, task: str) -> Path:
    n = 1
    while (attempts / f"{task}--{n}").exists():
        n += 1
    return attempts / f"{task}--{n}"


def _resume_line(args) -> str:
    return " ".join(["python3", "tests/calibration/run.py", "run", args.producer, "--bench", str(args.bench),
                     "--attempts", str(args.attempts), "--out", str(args.out), "--resume",
                     *(["--only", args.only] if args.only else [])])


def run_tasks(args) -> int:
    producer = PRODUCERS[args.producer]()
    found = _tasks(args)
    attempts, out = _outside(args.attempts), _outside(args.out)
    if args.dry_run:
        return dry_run(found, producer, attempts)
    producer.check()
    lock = _lock(attempts)
    try:
        ledger = Ledger(attempts)
        for entry in found:
            run_one(entry, producer, attempts, out, ledger, args)
    finally:
        os.close(lock)
    return OK


def run_one(entry: dict, producer, attempts: Path, out: Path, ledger: Ledger, args):
    task = reviewbench.key(entry)
    last = ledger.last(task, producer.name)
    open_run = last is not None and last["state"] in OPEN
    if open_run and not args.resume:
        raise Stop(REFUSED, f"課題 {task} に終わっていない run が在る（試み {last['attempt']}）。続ける: {_resume_line(args)}")
    if last is not None and last["state"] == DONE and args.resume:
        return
    if open_run:
        attempt, base, head = Path(last["attempt"]), last["base"], last["head"]
        run_id = last.get("run_id") or producer.find_run(attempt)
    else:
        attempt = _attempt(attempts, task)
        ledger.add(id=task, producer=producer.name, attempt=str(attempt), state="prepared")
        try:
            made = reviewbench.prepare(entry, attempt, attempts / REPOS, args.mirror)
        except reviewbench.BenchError as e:
            raise Stop(STOPPED, f"課題 {task} の試みのフォルダを作れない: {e}") from None
        base, head = made["base"], made["head"]
        run_id = None
    row = {"id": task, "producer": producer.name, "attempt": str(attempt), "base": base, "head": head}
    if run_id is None:
        ledger.add(**row, run_id=None, state="started")
        run_id = producer.start(attempt, base)
        if run_id is None:
            ledger.add(**row, run_id=None, state="stopped")
            raise Stop(STOPPED, f"課題 {task}: 作り手が run を残さなかった（試み {attempt}）。続ける: {_resume_line(args)}")
        ledger.add(**row, run_id=run_id, state="started")
    else:
        state = producer.state(attempt, run_id)
        if state == "running":
            raise Stop(REFUSED, f"課題 {task} の run {run_id} は走っている。同じ run を 2 本走らせない")
        if state == "failed":
            producer.resume(attempt, run_id)
    state = producer.state(attempt, run_id)
    if state == "paused":
        ledger.add(**row, run_id=run_id, state="paused")
        raise Stop(STOPPED, f"課題 {task}: 無人の run {run_id} が承認ノード {producer.gate(attempt, run_id)} で待った（工場の不具合。答えない）")
    if state != DONE:
        ledger.add(**row, run_id=run_id, state="stopped")
        raise Stop(STOPPED, f"課題 {task}: run {run_id} が終わりの状態にならずに止まった（{state}）。続ける: {_resume_line(args)}")
    ended = producer.finish(attempt, run_id)
    provenance = {**producer.provenance(), "claude_code": _claude_version(launcher.real_claude(os.environ)),
                  "run_inputs": {k: v.removeprefix(f"{attempt}{os.sep}") for k, v in producer.input_pairs(attempt, base).items()},
                  "date": _now()}
    convert_one(producer, entry, {**row, "run_id": run_id}, out, web_calls=ended["web_calls"], provenance=provenance)
    ledger.add(**row, run_id=run_id, child_run_ids=ended["children"], state=DONE)


def convert_one(producer, entry: dict, row: dict, out: Path, *, web_calls: int | None, provenance: dict | None):
    """試みの evidence/ から変換して findings/ と convert/ に書く。run と convert（やり直し）が共にここで組む。web_calls と
    provenance は run の時にだけ測れて evidence/ から読み直せないので、やり直しは前の控えから引き継いで渡す"""
    attempt = Path(row["attempt"])
    ended = {**producer.ended(attempt / evidence.EVIDENCE), "web_calls": web_calls}
    doc, record = reviewbench.convert(producer, entry, attempt, row["run_id"], row["base"], row["head"], ended)
    record["provenance"] = provenance
    reviewbench.write(out, producer.name, row["id"], doc, record)
    print(json.dumps(record, ensure_ascii=False, allow_nan=False))


def _claude_version(claude: str | None) -> str | None:
    """作り手が起こす claude（殻と同じく CLAUDE_BIN_PATH か PATH から決めた物）の版"""
    if not claude:
        return None
    done = subprocess.run([claude, "--version"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def dry_run(found: list[dict], producer, attempts: Path) -> int:
    """作り手を起こさず、置き場にも書かない。課題ごとに打つはずの命令を出す（課題の鍵の一覧も兼ねる）"""
    for entry in found:
        task = reviewbench.key(entry)
        print(json.dumps({"key": task, "base": entry["base"], "head": entry["head"],
                          "command": producer.start_command(attempts / f"{task}--N", entry["base"]),
                          "env": producer.env_names(), "account_env": producer.account}, ensure_ascii=False))
    return OK


def reconvert(args) -> int:
    producer = PRODUCERS[args.producer]()
    attempts, out = _outside(args.attempts), _outside(args.out)
    ledger = Ledger(attempts)
    if not ledger.path.exists():
        raise Stop(REFUSED, f"台帳 {ledger.path} が無い。run で回した置き場を --attempts に渡す")
    lock = _lock(attempts)
    try:
        done = {task: row for task, row in ledger.current(producer.name).items() if row["state"] == DONE}
        if not done:
            raise Stop(REFUSED, f"台帳 {ledger.path} に作り手 {producer.name} の済んだ課題が無い")
        wanted = [x for x in args.only.split(",") if x] if args.only else sorted(done)
        unknown = [x for x in wanted if x not in done]
        if unknown:
            raise Stop(REFUSED, f"{unknown} は台帳 {ledger.path} で作り手 {producer.name} の済んだ課題でない")
        for task in wanted:
            reconvert_one(producer, done[task], out)
    finally:
        os.close(lock)
    return OK


def reconvert_one(producer, row: dict, out: Path):
    task, attempt = row["id"], Path(row["attempt"])
    try:
        entry = json.loads((attempt / "pr" / "pr.json").read_text(encoding="utf-8"))
        before = json.loads((out / producer.name / "convert" / f"{task}.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Stop(STOPPED, f"課題 {task} の pr/pr.json か前の変換の控えを読めない: {type(e).__name__}") from None
    if not reviewbench.has(attempt / "target", row["head"]):
        raise Stop(STOPPED, f"課題 {task} の試みの target/ で head {row['head']} を読めない（{attempt / 'target'}）。控えは書き換えない")
    convert_one(producer, entry, row, out, web_calls=before.get("web_calls"), provenance=before.get("provenance"))


# ---------------------------------------------------------------- judge・nodes
def judge(args) -> int:
    bench, mine = Path(args.bench), _outside(args.out) / args.producer
    if not (bench / "node_modules").is_dir():
        raise Stop(REFUSED, f"ReviewBench の写し {bench} に node_modules が無い。先に npm ci を打つ")
    if not (mine / "findings").is_dir():
        raise Stop(REFUSED, f"{mine / 'findings'} が無い。先に run で回す")
    settings = mine / ".judge"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "models.json").write_text(json.dumps({"providers": {"anthropic": {"apiKey": "ANTHROPIC_API_KEY", "models": [
        {"id": args.model, "reasoning": True, "contextWindow": 1000000, "maxTokens": 64000}]}}}, indent=2) + "\n", encoding="utf-8")
    done = subprocess.run(["npm", "run", "judge", "--", "--candidate", str(mine / "findings"), "--provider", "anthropic",
                           "--model", args.model, "--output", str(mine / "scoring" / "results.json")],
                          cwd=bench, env={**os.environ, "PI_CODING_AGENT_DIR": str(settings)}, stdin=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        tail = done.stderr.strip().splitlines()[-5:]
        raise Stop(STOPPED, "\n".join([f"判定役が終了の値 {done.returncode} で止まった:", *tail, KEY_LINE]))
    return OK


def table(args) -> int:
    out = _outside(args.out)
    try:
        got = nodes.table(out, PRODUCERS[args.producer]())
    except reviewbench.BenchError as e:
        raise Stop(STOPPED, str(e)) from None
    mine = out / args.producer
    mine.mkdir(parents=True, exist_ok=True)
    (mine / "nodes.json").write_text(json.dumps(got, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    (mine / "nodes.md").write_text(nodes.markdown(got), encoding="utf-8")
    print(json.dumps({"nodes": str(mine / "nodes.json"), "md": str(mine / "nodes.md")}, ensure_ascii=False))
    return OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="公開ベンチ ReviewBench を 3 つの作り手で回すランナー")
    sub = parser.add_subparsers(dest="command", required=True)
    ran = sub.add_parser("run")
    ran.add_argument("producer", choices=sorted(PRODUCERS))
    ran.add_argument("--bench", required=True, type=Path)
    ran.add_argument("--attempts", required=True, type=Path)
    ran.add_argument("--out", required=True, type=Path)
    ran.add_argument("--language", default="Python")
    ran.add_argument("--only")
    ran.add_argument("--resume", action="store_true")
    ran.add_argument("--dry-run", action="store_true")
    ran.add_argument("--mirror", default=reviewbench.MIRROR)
    judged = sub.add_parser("judge")
    judged.add_argument("producer", choices=sorted(PRODUCERS))
    judged.add_argument("--bench", required=True, type=Path)
    judged.add_argument("--out", required=True, type=Path)
    judged.add_argument("--model", default=JUDGE_MODEL)
    again = sub.add_parser("convert")
    again.add_argument("producer", choices=sorted(PRODUCERS))
    again.add_argument("--attempts", required=True, type=Path)
    again.add_argument("--out", required=True, type=Path)
    again.add_argument("--only")
    counted = sub.add_parser("nodes")
    counted.add_argument("producer", choices=sorted(PRODUCERS))
    counted.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        return {"run": run_tasks, "judge": judge, "convert": reconvert, "nodes": table}[args.command](args)
    except Stop as e:
        print(f"run.py: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
