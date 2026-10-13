"""欠陥を仕込んだ較正の束を本物の工場に回し、1 行の run ごとに observed を残す（運び役が命令として打つ道具。試験のモジュールではない）。

    python3 tests/calibration/run.py run <works|works-factory> --attempts <置き場> [--only <id,…>] [--resume] [--observed <dir>] [--dry-run]
    python3 tests/calibration/run.py reobserve <works|works-factory> --attempts <置き場> [--only <id,…>] [--observed <dir>]
    python3 tests/calibration/run.py score <works|works-factory> [--observed <dir>]
    python3 tests/calibration/run.py compare [--observed <dir>]

約束は issue #214 の本文（「ランナーの約束」）。1 行の流れ: 束の行を materialize し、tests/e2e/make_target.py の make で試みのフォルダ
（target/・origin/・request.json・home/）を作って commit A（base/）と、change の行なら A の上の commit B（head/。message は依頼の
1 行目）を origin の main に push し、工場を前で起こして終わりまで待ち、記録を試みの evidence/ に写し、flags.json の表で flagged を組み、
observed を <observed>/<factory>/<行の id>--<run の id の頭 8 字>.json に書き、置き場の台帳 <置き場>/ledger.jsonl に 1 行足す。

- 終了の値: 0 済んだ・1 行が止まった（後ろの行を起こさない。--resume で続ける）・2 何も起こさずに断った。
- --resume は台帳で済んだ行を飛ばし、終わっていない run を持つ行をその run の続きから回す。--resume 無しは名指した行を全部新しい
  試みで回し（run 1 回につき observed が 1 つ足される）、終わっていない run を持つ行に当たれば断る（費用を二重に使わない）。
- 期限を置かない（持ち主の決め no-timeouts）。自分を切り離さない。関所には答えない（今の works の続きだけは、use.sh start の無人の
  末尾と同じく人が決める関所に stop と答えて報告へ進める。下の「続ける命令」）。run を止めない・取り消さない。
- 錠は --attempts の置き場ごとに 1 つ（<置き場>/.lock）で、台帳も置き場ごと。束を分けて並べて回すなら、--only で行を分け、置き場を
  行の組ごとに別にして起こす（同じ置き場に 2 つ目のランナーは断る）。observed は同じ --observed に書いてよい（名に run の id が入る）。
- アカウントは各工場の起動の殻が読む環境変数（WORKS_FACTORY_KEYCHAIN_ITEM・WORKS_KEYCHAIN_ITEM）をそのまま子に継ぐ。値は読まず、出さない。
- 試験の差し替え口は環境変数 WORKS_CALIBRATION_SHELL の 1 つだけ: works-factory の起動の殻（既定は bin/works-factory）を替える。
- reobserve は台帳で終わった行の observed を、試みの evidence/ だけから今の物差しで取り直す（工場も Archon も起こさず、記録を写し
  直さない）。evidence/ に無い来歴（工場と claude の版・入力・日時）と子の run は前の observed から引き継ぐ。前の observed が無い行は
  止まる（終了の値 1）。

observed の units（直した単位の名の並び）と asks（人の関所で止めた順の関所の名の並び。数は並びの長さ）は evidence/ から読み、読めない
時は欄を null にして unread に欄の名を、flag_evidence に読めない訳を置く（関門の unread と違い、行の判定には数えない）。読む先:
- 今の works（版は pack.json の works.commit）: units は盤面の周ごとの修正の出力 board/out/r<N>/p3.fix.json の changes[].unit_key
  （出力の置き場は .shared/core/board.py:1025、changes[].unit_key は .shared/core/graphloops/graphs/review-loop.json:3660 の p3.fix の
  pointers）。asks は record/parent.json の出来事のうち approval_requested の step_name（関所は blk-entry/blk-entry.yaml:79 の
  launch・blk-spec/blk-spec.yaml:443 の spec-gate・darkfactory/darkfactory.yaml:534・741・1247 の policy-gate・replan-gate・final-gate）。
- works-factory: units は修正の置き場 parent/fix/<include の名>/（groups.json の在る所）ごとに、join.json の単位の行に同じ置き場の
  fix-units.json の裁定の後の結末を重ねて fixed の unit_id（workflows/fix/scripts/collect.py:79-85 と同じ重ね方。join.json の無い
  置き場は join が落ちたか走らなかった印で、units を読めないとする。lib/fixboard.py:742・760・979・1445・2308）。asks は
  record/parent.json の terminal_record.nodes のうち、メイングラフの承認ノード（WorksFactory.gates）で skipped・pending でない物。

今の works（pack.json の works.commit。置き場は環境変数 WORKS_FACTORY_OLD_WORKS に、取り出した claude-plugins の works/ を渡す）の
記録の置き場と形（その版の works/dev/use.sh・lib.sh・archon.sh・canary_check.py と .shared/core/report.py で確かめた）:
- 家は WORKS_USE_HOME=<試み>/home。use.sh start は無人（WORKS_USE_UNATTENDED=1）なら起動の関所を越えて残りをその場で回し、人が決める
  関所に着けば自分で stop と答えて報告へ進める（use.sh の start の末尾）。run の控えは <家>/runs/<run-id>.json（use.sh 452 行）で、
  行ごとに新しい家にちょうど 1 つ。
- run の行は <家>/archon-home/archon.db（archon.sh の ARCHON_HOME）の表 remote_agent_workflow_runs、出来事は
  remote_agent_workflow_events。盤面は run の行の output_root の下の artifacts/runs/<id>/board（canary_check.py の頭）。
- 結末の語は盤面の report.md の頭 10 行のうち「起きたこと: 」で始まる行の（<語>）（report.py の header_outcome。語は
  decide_outcome が決めて報告の頭に書く）。
- use.sh wait の終了の値: 0 関所で待つ・3 まだ走る（決まった秒数で戻るだけで run の期限ではない）・5 終わった・1 落ちた・6 周の鎖。
- 続ける命令は use.sh show の「失敗や中断から続ける」の行と同じ形（lib.sh の works_dev_go）: 対象で
  WORKS_DEV_HOME=<家> sh dev/continue.sh dev/archon.sh workflow resume <run>。続きが人が決める関所で止まれば、use.sh start の無人の
  末尾と同じ続きの口で workflow respond <run> stop <一言> と答えて終わりまで待つ（使用枠で止まった run を続けた時に paused で残さない）。
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from bin._lib import pack  # noqa: E402
from tests.calibration import corpus  # noqa: E402
from tests.e2e import evidence, make_target  # noqa: E402
import fixboard  # noqa: E402  lib/ は corpus が sys.path に足す

FLAGS = HERE / "flags.json"
OBSERVED = HERE / "observed"
NODES = ROOT / "docs" / "nodes.json"
SHELL_ENV = "WORKS_CALIBRATION_SHELL"
OLD_WORKS_ENV = "WORKS_FACTORY_OLD_WORKS"
LINE = "works-factory-line"
OK, STOPPED, REFUSED = 0, 1, 2
SEED_INPUTS = {"test_cmd": "python3 -m unittest -v", "tdd_suite": "junit-suite.sh"}
LEDGER = "ledger.jsonl"
LOCK = ".lock"
DONE = "done"
OPEN = ("started", "stopped", "paused")   # 台帳の状態のうち run を持ちうる物。prepared（試みを作る途中で落ちた）は新しい試みで回し直す
SKIPPED = "skipped"
WAIT_RUNNING = 3
UNATTENDED_STOP = "無人の run（WORKS_USE_UNATTENDED=1）: 人が決める関所に着いたので止めて報告へ"   # use.sh start の無人の末尾の文
STATES = {"running": "running", "pending": "running", "paused": "paused", "completed": DONE}   # Archon の run の status → run_one の分かれ
RECORDED = ("units", "asks")   # 関門でなく unread に入りうる observed の欄
NOT_ASKED = ("skipped", "pending")


class Stop(Exception):
    def __init__(self, code: int, line: str):
        super().__init__(line)
        self.code = code


class WorksFactory:
    """このリポジトリの工場。殻 bin/works-factory で Archon の工程 works-factory-line を前で回す"""
    name = "works-factory"
    account = "WORKS_FACTORY_KEYCHAIN_ITEM"
    passes = {"unattended": "unattended", "final_gate": "final_gate", "thickness": "thickness"}
    gates = ("gate-start", "gate-before-fix", "gate-replan", "gate-final")   # workflows/line/works-factory-line.yaml の承認ノード

    def __init__(self):
        self.shell = Path(os.environ.get(SHELL_ENV) or ROOT / "bin" / "works-factory")

    def check(self):
        pass

    def env_names(self) -> list[str]:
        return ["WORKS_FACTORY_HOME"]

    def start_command(self, attempt: Path, base: str | None, inputs: dict) -> list[str]:
        pairs = {"request": str(attempt / "request.json"), **({"base": base} if base else {}), **SEED_INPUTS,
                 **{self.passes[k]: v for k, v in inputs.items()}}
        return [sys.executable, str(self.shell), "workflow", "run", LINE, "--cwd", str(attempt / "target"),
                *[part for k, v in pairs.items() for part in ("--input", f"{k}={v}")]]

    def resume_command(self, attempt: Path, run_id: str) -> list[str]:
        return [sys.executable, str(self.shell), "workflow", "resume", run_id, "--cwd", str(attempt / "target")]

    def _launch(self, attempt: Path, command: list[str]):
        subprocess.run(command, cwd=attempt / "home", env={**os.environ, "WORKS_FACTORY_HOME": str(attempt / "home")},
                       stdin=subprocess.DEVNULL)

    def start(self, attempt: Path, base: str | None, inputs: dict) -> str | None:
        self._launch(attempt, self.start_command(attempt, base, inputs))
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

    def _get(self, attempt: Path, run_id: str) -> dict:
        try:
            got = evidence.read_json(attempt, "get", run_id, "--json", shell=self.shell)
        except evidence.Stop as e:
            raise Stop(STOPPED, f"run {run_id} の記録を読めない: {e}") from None
        if not isinstance(got, dict):
            raise Stop(STOPPED, f"run {run_id} の workflow get の返りが dict でない")
        return got

    def state(self, attempt: Path, run_id: str) -> str:
        status = self._get(attempt, run_id).get("status")
        return _state(status)

    def gate(self, attempt: Path, run_id: str) -> str:
        for rid in [run_id, *evidence.children(self._runs(attempt), run_id)]:
            got = self._get(attempt, rid)
            node = ((got.get("metadata") or {}).get("approval") or {}).get("nodeId")
            if got.get("status") == "paused" and node:
                return node if rid == run_id else f"{node}（子の run {rid}）"
        return "（記録に関所の名が無い）"

    def resume(self, attempt: Path, run_id: str):
        self._launch(attempt, self.resume_command(attempt, run_id))

    def finish(self, attempt: Path, run_id: str) -> dict:
        try:
            kept = evidence.collect(attempt, run_id, self.shell)
        except evidence.Stop as e:
            raise Stop(STOPPED, f"run {run_id} の記録を evidence/ に写せない: {e}") from None
        for limit in kept["limits"]:
            print(f"run.py: {limit}（その置き場を読む照らしは unread になる）", file=sys.stderr)
        return {**self.ended(attempt / evidence.EVIDENCE), "children": kept["children"]}

    @staticmethod
    def ended(ev: Path) -> dict:
        got = _object(_read_json(ev, "record/parent.json")[0])
        value = _object(_object(got.get("terminal_record")).get("returns")).get("value")
        outcome = value.get("outcome") if isinstance(value, dict) else None
        return {"outcome": outcome if isinstance(outcome, str) else "",
                "seconds": _seconds(got.get("started_at"), got.get("completed_at")),
                "usd": _number(_object(got.get("metadata")).get("total_cost_usd")),
                "usd_from": "run の記録の metadata.total_cost_usd（fix の組の子の run の費用を含む）"}

    @staticmethod
    def units(ev: Path) -> tuple[list | None, str]:
        if not (ev / "parent").is_dir():
            return None, "parent: 無い"
        names = []
        for groups in sorted((ev / "parent").glob(f"fix/*/{fixboard.GROUPS_FILE}")):
            place = groups.parent
            doc, why = _read_json(ev, place / fixboard.JOIN_FILE)
            rows = doc.get("units") if isinstance(doc, dict) else None
            if not isinstance(rows, list):
                return None, why or f"{_name(ev, place / fixboard.JOIN_FILE)}: units が並びでない"
            ruled, why = None, ""
            if (place / fixboard.FIX_UNITS_FILE).exists():
                ruled, why = _read_json(ev, place / fixboard.FIX_UNITS_FILE)
            if why:
                return None, why
            rows = [r for r in rows if isinstance(r, dict) and "unit_id" in r and "status" in r]
            names += [u["unit_id"] for u in fixboard.with_ruled(rows, ruled) if u["status"] == "fixed"]
        return _unique(names), ""

    @classmethod
    def asks(cls, ev: Path) -> tuple[list | None, str]:
        doc, why = _read_json(ev, "record/parent.json")
        nodes = _object(_object(doc).get("terminal_record")).get("nodes")
        if not isinstance(nodes, list):
            return None, why or "record/parent.json: terminal_record.nodes が並びでない"
        return [n["node_id"] for n in nodes if isinstance(n, dict) and n.get("node_id") in cls.gates
                and n.get("state") not in NOT_ASKED], ""

    def provenance(self) -> dict:
        return {"factory_commit": make_target.git("-C", str(ROOT), "rev-parse", "HEAD"),
                "archon": pack.load(ROOT)["archon"]["commit"]}

    @staticmethod
    def skipped(evidence_dir: Path) -> set[str]:
        """深さで飛ばされた関門: nodes.json の where の節が record の terminal_record.nodes に在り、全部 skipped"""
        states = []
        for path in sorted((evidence_dir / "record").glob("*.json")):
            try:
                nodes = (json.loads(path.read_text(encoding="utf-8")).get("terminal_record") or {}).get("nodes") or []
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                continue
            states += [(n.get("node_id") or "", n.get("state")) for n in nodes if isinstance(n, dict)]
        out = set()
        for gate, row in json.loads(NODES.read_text(encoding="utf-8"))["graph"].items():
            names = [w.split("/", 1)[1] for w in row.get("where") or []]
            seen = [s for node, s in states if any(_node_is(node, name) for name in names)]
            if seen and all(s == SKIPPED for s in seen):
                out.add(gate)
        return out


def _node_is(node_id: str, name: str) -> bool:
    """include の中の節は <include の id>__<節の id>、輪の体の節は <輪の id>.<体の id> の形で記録に載る
    （止めた Archon の include-expander.ts・dag-executor.ts）"""
    return name in re.split(r"__|\.", node_id)


class OldWorks:
    """今の works。works/dev/use.sh で darkfactory を回す"""
    name = "works"
    account = "WORKS_KEYCHAIN_ITEM"
    passes = {"unattended": "WORKS_USE_UNATTENDED", "final_gate": "WORKS_USE_FINAL_GATE", "thickness": "WORKS_USE_THICKNESS"}
    values = {"unattended": {"true": "1"}}

    def __init__(self):
        self.dir = Path(os.environ[OLD_WORKS_ENV]) if os.environ.get(OLD_WORKS_ENV) else None
        self.dev = self.dir / "dev" if self.dir else Path(f"${OLD_WORKS_ENV}") / "dev"

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
        return ["WORKS_USE_HOME", *self.passes.values()]

    def _env(self, attempt: Path, inputs: dict) -> dict:
        return {**os.environ, "WORKS_USE_HOME": str(attempt / "home"),
                **{self.passes[k]: self.values.get(k, {}).get(v, v) for k, v in inputs.items()}}

    def start_command(self, attempt: Path, base: str | None, inputs: dict) -> list[str]:
        return ["sh", str(self.dev / "use.sh"), "start", *(["--base", base] if base else []), "--",
                str(attempt / "target"), str(attempt / "request.json"), SEED_INPUTS["test_cmd"], SEED_INPUTS["tdd_suite"]]

    def continue_command(self, verb: str, run_id: str, *rest: str) -> list[str]:
        return ["sh", str(self.dev / "continue.sh"), str(self.dev / "archon.sh"), "workflow", verb, run_id, *rest]

    def start(self, attempt: Path, base: str | None, inputs: dict) -> str | None:
        subprocess.run(self.start_command(attempt, base, inputs), cwd=attempt / "target", env=self._env(attempt, inputs),
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
        """use.sh wait を、まだ走る（3）の間は上限なしに打ち直す。終わり・関所・落ちの判じは state が db から読む"""
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
        status = self._row(attempt, run_id)[0].get("status")
        return _state(status)

    def gate(self, attempt: Path, run_id: str) -> str:
        approval = (_json_or_text(self._row(attempt, run_id)[0].get("metadata")) or {})
        node = (approval.get("approval") or {}).get("nodeId") if isinstance(approval, dict) else None
        return node or "（記録に関所の名が無い）"

    def resume(self, attempt: Path, run_id: str):
        """続きを回し、人が決める関所に着けば use.sh start の無人の末尾と同じく stop と答えて報告へ進める"""
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
            print(f"run.py: run {run_id} の盤面（{board}）が無い（盤面を読む照らしは unread になる）", file=sys.stderr)
        return {**self.ended(out), "children": []}

    @staticmethod
    def ended(ev: Path) -> dict:
        got = _object(_read_json(ev, "record/parent.json")[0])
        run = _object(got.get("run"))
        usd = next((e["data"].get("cost_usd") for e in _events(got)
                    if e.get("event_type") == "workflow_completed" and isinstance(e.get("data"), dict)), None)
        # 行の started_at は再開のたびに書き直される。最初の出来事が run の始め
        began = next((e["created_at"] for e in _events(got) if e.get("created_at")), run.get("started_at"))
        return {"outcome": _header_outcome(ev / "board"),
                "seconds": _seconds(began, run.get("completed_at")),
                "usd": _number(usd),
                "usd_from": "出来事 workflow_completed の data.cost_usd"}

    @staticmethod
    def units(ev: Path) -> tuple[list | None, str]:
        if not (ev / "board").is_dir():
            return None, "board: 無い"
        fixes = [p for p in (ev / "board").glob("out/r*/p3.fix.json") if re.fullmatch(r"r\d+", p.parent.name)]
        names = []
        for path in sorted(fixes, key=lambda p: int(p.parent.name[1:])):
            doc, why = _read_json(ev, path)
            changes = doc.get("changes") if isinstance(doc, dict) else None
            if not isinstance(changes, list):
                return None, why or f"{_name(ev, path)}: changes が並びでない"
            names += [c["unit_key"] for c in changes if isinstance(c, dict) and isinstance(c.get("unit_key"), str)]
        return _unique(names), ""

    @staticmethod
    def asks(ev: Path) -> tuple[list | None, str]:
        doc, why = _read_json(ev, "record/parent.json")
        if not isinstance(_object(doc).get("events"), list):
            return None, why or "record/parent.json: events が並びでない"
        return [e.get("step_name") or "" for e in _events(doc) if e.get("event_type") == "approval_requested"], ""

    def provenance(self) -> dict:
        found = re.search(r'^ARCHON_VERSION="([^"]+)"', (self.dev / "archon.sh").read_text(encoding="utf-8"), re.M)
        return {"factory_commit": pack.load(ROOT)["works"]["commit"], "archon": found[1] if found else None}

    @staticmethod
    def skipped(evidence_dir: Path) -> set[str]:
        """深さで飛ばされた関門: 盤面の state.json の rounds[].skipped の鍵（関門の id。.shared/core/board.py の skip が書く）"""
        try:
            rounds = json.loads((evidence_dir / "board" / "state.json").read_text(encoding="utf-8")).get("rounds") or []
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return set()
        return {gate for one in rounds if isinstance(one, dict) for gate in (one.get("skipped") or {})}


HAPPENED = "起きたこと: "


def _header_outcome(board: Path) -> str:
    try:
        lines = (board / "report.md").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    for line in lines[:10]:
        if line.startswith(HAPPENED):
            return next((w for w in corpus.OUTCOMES if f"（{w}）" in line), "")
    return ""


def _read_json(ev: Path, path) -> tuple[object, str]:
    """evidence/ の中の JSON。(値, "") か、(None, 「evidence/ からの相対パス: 無い・読めない」)"""
    path = ev / path
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except FileNotFoundError:
        return None, f"{_name(ev, path)}: 無い"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"{_name(ev, path)}: 読めない（{type(e).__name__}）"


def _name(ev: Path, path: Path) -> str:
    return path.relative_to(ev).as_posix()


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _events(record: dict) -> list[dict]:
    events = _object(record).get("events")
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def _unique(names: list) -> list:
    return list(dict.fromkeys(names))


def _json_or_text(raw):
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _seconds(start, end) -> float | None:
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


FACTORY = {c.name: c for c in (OldWorks, WorksFactory)}


# ---------------------------------------------------------------- flagged の表
def load_flags(path=FLAGS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def flags_of(table: dict, evidence_dir: Path, skipped: set[str]) -> dict:
    """表の照らしを evidence に当てて {flagged, unread, flag_evidence} を組む。照らしが 1 つ通れば flagged。深さで飛ばされた関門は
    出していないに数える。通った照らしが無く、読めないファイルが在るか、中身を読む照らし（exists でない物）のファイルが 1 つも
    無い関門は unread（関門が走ったかを言えない。落とし穴 K15）。exists の照らしのファイルが無いのは「出していない」"""
    flagged, unread, why = [], [], {}
    for gate in sorted(table):
        rules = table[gate].get("rules")
        if rules is None:
            continue
        if gate in skipped:
            why[gate] = SKIPPED
            continue
        judged = [(rule, *evidence.judge(evidence_dir, rule)) for rule in rules]
        hit = next((detail for _, state, detail in judged if state == evidence.PASS), None)
        if hit is not None:
            flagged.append(gate)
            why[gate] = hit
            continue
        broken = [detail for _, state, detail in judged if state == evidence.UNREADABLE]
        contents = [state for rule, state, _ in judged if rule["check"] != "exists"]
        if broken or (contents and all(state == evidence.MISSING for state in contents)):
            unread.append(gate)
            why[gate] = "; ".join(broken or [detail for _, state, detail in judged if state == evidence.MISSING])
    return {"flagged": flagged, "unread": unread, "flag_evidence": why}


def fingerprint(factory: str, corpus_path: Path, flags: dict) -> str:
    """束・種の全部のファイル・flags.json のその工場の節の sha256（observed が今の物差しで測られたかを見分ける）"""
    digest = hashlib.sha256()
    corpus_path = Path(corpus_path)
    seed = corpus_path.parent / json.loads(corpus_path.read_text(encoding="utf-8"))["seed"]
    parts = [("corpus.json", corpus_path.read_bytes())]
    parts += [(f"seed/{p.relative_to(seed).as_posix()}", p.read_bytes()) for p in sorted(seed.rglob("*"))
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    parts.append(("flags", json.dumps(flags.get(factory), ensure_ascii=False, sort_keys=True).encode("utf-8")))
    for name, data in parts:
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


# ---------------------------------------------------------------- run
class Ledger:
    """置き場の台帳。行ごとに最後の行が今の状態。絶対パスはここ（リポジトリの外）にだけ書く"""

    def __init__(self, attempts: Path):
        self.path = attempts / LEDGER

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def last(self, row_id: str, factory: str) -> dict | None:
        mine = [r for r in self.rows() if r["id"] == row_id and r["factory"] == factory]
        return mine[-1] if mine else None

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


def _outside(attempts: Path) -> Path:
    attempts = Path(os.path.realpath(attempts))
    if attempts.is_relative_to(Path(os.path.realpath(ROOT))):
        raise Stop(REFUSED, f"置き場 {attempts} がリポジトリの中に在る。リポジトリの外に置く")
    return attempts


def _rows(data: dict, only: str | None) -> list[dict]:
    if not only:
        return data["rows"]
    wanted = [x for x in only.split(",") if x]
    known = {r["id"] for r in data["rows"]}
    unknown = [x for x in wanted if x not in known]
    if unknown:
        raise Stop(REFUSED, f"--only の {unknown} が束に無い")
    return [r for r in data["rows"] if r["id"] in wanted]


def _inputs(data: dict, factory) -> dict:
    inputs = data["run_inputs"]
    unknown = sorted(set(inputs) - set(factory.passes))
    if unknown:
        raise Stop(REFUSED, f"束の run_inputs の鍵 {unknown} の渡し方がランナーの表に無い（{factory.name} に渡す名: {sorted(factory.passes)}）")
    return inputs


def _attempt(attempts: Path, row_id: str) -> Path:
    n = 1
    while (attempts / f"{row_id}--{n}").exists():
        n += 1
    return attempts / f"{row_id}--{n}"


def _prepare(row: dict, attempt: Path, corpus_path: Path, factory) -> str | None:
    """試みのフォルダを作り、commit A（と change の行なら B）を origin の main に置く。base に渡す A を返す（request の行は None）"""
    with tempfile.TemporaryDirectory(prefix="calibration-") as tmp:
        made = corpus.materialize(row["id"], tmp, corpus=corpus_path)
        try:
            built = make_target.make(attempt, seed=Path(made["base"]), request=Path(made["request"]),
                                     listed=factory.name == "works-factory")
        except make_target.Stop as e:
            raise Stop(STOPPED, f"行 {row['id']} の試みのフォルダを作れない: {e}") from None
        target = built["target"]
        base = make_target.git("-C", target, "rev-parse", "HEAD")
        if row["entry"] != "change":
            return None
        for path in Path(target).iterdir():
            if path.name != ".git":
                shutil.rmtree(path) if path.is_dir() else path.unlink()
        shutil.copytree(made["head"], target, dirs_exist_ok=True, ignore=corpus.COPY_IGNORE)
        make_target.git("-C", target, "add", "-A")
        make_target.git("-C", target, "commit", "-q", "-m", row["request"][0]["text"])
        make_target.git("-C", target, "push", "-q", "origin", "main")
        return base


def _resume_line(args) -> str:
    return " ".join(["python3", "tests/calibration/run.py", "run", args.factory, "--attempts", str(args.attempts),
                     "--resume", *(["--only", args.only] if args.only else [])])


def run_rows(args) -> int:
    factory = FACTORY[args.factory]()
    data = corpus.load(args.corpus)
    inputs = _inputs(data, factory)
    rows = _rows(data, args.only)
    attempts = _outside(args.attempts)
    if args.dry_run:
        return dry_run(rows, factory, inputs, attempts, args.corpus)
    factory.check()
    lock = _lock(attempts)
    try:
        ledger = Ledger(attempts)
        flags = load_flags()
        for row in rows:
            run_one(row, factory, inputs, attempts, ledger, flags, args)
    finally:
        os.close(lock)
    return OK


def run_one(row: dict, factory, inputs: dict, attempts: Path, ledger: Ledger, flags: dict, args):
    last = ledger.last(row["id"], factory.name)
    open_run = last is not None and last["state"] in OPEN
    if open_run and not args.resume:
        raise Stop(REFUSED, f"行 {row['id']} に終わっていない run が在る（試み {last['attempt']}）。続ける: {_resume_line(args)}")
    if last is not None and last["state"] == DONE and args.resume:
        return
    if open_run:
        attempt, base = Path(last["attempt"]), last.get("base")
        run_id = last.get("run_id") or factory.find_run(attempt)
    else:
        attempt = _attempt(attempts, row["id"])
        ledger.add(id=row["id"], factory=factory.name, attempt=str(attempt), state="prepared")
        base = _prepare(row, attempt, args.corpus, factory)
        run_id = None
    entry = {"id": row["id"], "factory": factory.name, "attempt": str(attempt), "base": base}
    if run_id is None:
        ledger.add(**entry, run_id=None, state="started")
        run_id = factory.start(attempt, base, inputs)
        if run_id is None:
            ledger.add(**entry, run_id=None, state="stopped")
            raise Stop(STOPPED, f"行 {row['id']}: 工場が run を残さなかった（試み {attempt}）。続ける: {_resume_line(args)}")
        ledger.add(**entry, run_id=run_id, state="started")
    else:
        state = factory.state(attempt, run_id)
        if state == "running":
            raise Stop(REFUSED, f"行 {row['id']} の run {run_id} は走っている。同じ run を 2 本走らせない")
        if state == "failed":
            factory.resume(attempt, run_id)
    state = factory.state(attempt, run_id)
    if state == "paused":
        ledger.add(**entry, run_id=run_id, state="paused")
        raise Stop(STOPPED, f"行 {row['id']}: 無人の run {run_id} が関所 {factory.gate(attempt, run_id)} で待った（工場の不具合。答えない）")
    if state != DONE:
        ledger.add(**entry, run_id=run_id, state="stopped")
        raise Stop(STOPPED, f"行 {row['id']}: run {run_id} が終わりの状態にならずに止まった（{state}）。続ける: {_resume_line(args)}")
    ended = factory.finish(attempt, run_id)
    made = {**factory.provenance(), "claude_code": _claude_version(),
            "run_inputs": {"request": "request.json", **({"base": base} if base else {}), **SEED_INPUTS, **inputs},
            "date": _now()}
    observed = observe(row, factory, run_id, ended, attempt / evidence.EVIDENCE, flags, args.corpus, made)
    write_observed(observed, Path(args.observed))
    ledger.add(**entry, run_id=run_id, child_run_ids=ended["children"], state=DONE)
    print(json.dumps(observed, ensure_ascii=False, allow_nan=False))


def observe(row, factory, run_id, ended, ev: Path, flags, corpus_path, made: dict) -> dict:
    """made は来歴のうち物差しの指紋のほかの欄（工場と claude の版・入力・日時）"""
    got = flags_of(flags[factory.name], ev, factory.skipped(ev))
    read = {name: getattr(factory, name)(ev) for name in RECORDED}
    lost = {name: why for name, (_, why) in read.items() if why}
    seconds = ended["seconds"]
    return {
        "id": row["id"], "factory": factory.name, "run_id": run_id, "outcome": ended["outcome"],
        "flagged": got["flagged"], "child_run_ids": ended["children"], "unread": got["unread"] + list(lost),
        "flag_evidence": {**got["flag_evidence"], **lost},
        "units": read["units"][0], "asks": read["asks"][0],
        "cost": {"usd": ended["usd"], "seconds": seconds, "why_null": "。".join(
            ([] if ended["usd"] is not None else [f"usd: {ended['usd_from']} が読めない"])
            + ([] if seconds is not None else ["seconds: run の記録の始めと終わりの時刻が読めない"]))},
        "provenance": {**made, "fingerprint": fingerprint(factory.name, corpus_path, flags)},
    }


def reobserve_rows(args) -> int:
    factory = FACTORY[args.factory]()
    rows = _rows(corpus.load(args.corpus), args.only)
    attempts = _outside(args.attempts)
    if not attempts.is_dir():
        raise Stop(REFUSED, f"置き場 {attempts} が無い")
    lock = _lock(attempts)
    try:
        ledger, flags = Ledger(attempts), load_flags()
        for row in rows:
            last = ledger.last(row["id"], factory.name)
            if last is None:
                continue
            if last["state"] != DONE:
                print(f"run.py: 行 {row['id']} の run は終わっていない（台帳の状態 {last['state']}）。取り直さない", file=sys.stderr)
                continue
            path = observed_path(Path(args.observed), factory.name, row["id"], last["run_id"])
            try:
                before = _object(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise Stop(STOPPED, f"行 {row['id']} の前の observed（{path}）が読めない。来歴を引き継げないので取り直さない") from None
            ev = Path(last["attempt"]) / evidence.EVIDENCE
            _, why = _read_json(ev, "record/parent.json")
            if why:
                raise Stop(STOPPED, f"行 {row['id']} の記録が読めない（{ev} の {why}）。前の observed を空の結末で上書きしないので取り直さない")
            ended = {**factory.ended(ev), "children": before.get("child_run_ids") or []}
            made = {k: v for k, v in _object(before.get("provenance")).items() if k != "fingerprint"}
            observed = observe(row, factory, last["run_id"], ended, ev, flags, args.corpus, made)
            write_observed(observed, Path(args.observed))
            print(json.dumps(observed, ensure_ascii=False, allow_nan=False))
    finally:
        os.close(lock)
    return OK


def _claude_version() -> str | None:
    if not shutil.which("claude"):
        return None
    done = subprocess.run(["claude", "--version"], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def observed_path(folder: Path, factory: str, row_id: str, run_id: str) -> Path:
    return folder / factory / f"{row_id}--{run_id[:8]}.json"


def write_observed(observed: dict, folder: Path) -> Path:
    path = observed_path(folder, observed["factory"], observed["id"], observed["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(observed, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return path


def dry_run(rows, factory, inputs, attempts: Path, corpus_path) -> int:
    """工場を起こさず、置き場にも書かない。仕込みが名指しの赤・証人の assert を出すかを確かめ、打つはずの命令を出す"""
    bad = 0
    for row in rows:
        with tempfile.TemporaryDirectory(prefix="calibration-dry-") as tmp:
            made = corpus.materialize(row["id"], tmp, corpus=corpus_path)
            proof, ok = _proof(row, Path(made["head"]))
        attempt = attempts / f"{row['id']}--N"
        base = "<commit A>" if row["entry"] == "change" else None
        bad += not ok
        print(json.dumps({"id": row["id"], "entry": row["entry"], "ok": ok, **proof,
                          "command": factory.start_command(attempt, base, inputs),
                          "env": factory.env_names(), "account_env": factory.account}, ensure_ascii=False))
    return OK if not bad else STOPPED


def _proof(row: dict, head: Path) -> tuple[dict, bool]:
    if row["red"]:
        got = corpus.seed_results(head)
        return {"red": got["failures"], "errors": got["errors"]}, got["failures"] == sorted(row["red"]) and not got["errors"]
    if row["witness"]:
        got = corpus.witness_result(head, row["witness"])
        return {"witness": got}, got == "assert"
    got = corpus.seed_results(head)
    return {"green": not got["failures"] and not got["errors"]}, not got["failures"] and not got["errors"]


# ---------------------------------------------------------------- score・compare
def read_observed(folder: Path, factory: str) -> list[tuple[str, object]]:
    out = []
    for path in sorted((Path(folder) / factory).glob("*.json")):
        try:
            out.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            out.append((path.name, f"読めない（{type(e).__name__}）"))
    return out


def verdict(rows: dict, observed) -> dict:
    """行の判定。読めなかった関門が行の当てる先に当たれば INCONCLUSIVE。対照は先に corpus.score で判じ、CLEAN の時だけ読めなかった
    関門が 1 つでも在れば INCONCLUSIVE に替える（CLEAN は「どの関門も出していない」の言い切りで、読めなかった関門はそれを言えない。
    結末で決まる FALSE_ALARM は関門を読まずに言える）"""
    row_id = observed.get("id") if isinstance(observed, dict) else None
    if row_id not in rows:
        return _inconclusive(row_id, f"observed が読めないか、行 {row_id} が束に無い")
    row = rows[row_id]
    unread = [g for g in observed.get("unread") or [] if g not in RECORDED]
    if row["kind"] == "none":
        got = corpus.score(row, observed)
        return _inconclusive(row_id, f"読めなかった関門 {list(unread)}") if got["verdict"] == "CLEAN" and unread else got
    lost = [a for a in corpus._aims(row) if a in unread]
    if lost:
        return _inconclusive(row_id, f"読めなかった関門 {lost}")
    return corpus.score(row, observed)


def _inconclusive(row_id, detail: str) -> dict:
    return {"id": row_id, "verdict": corpus.INCONCLUSIVE, "aimed_hit": False, "caught_by": [], "missed_by": [],
            "outcome_as_expected": False, "detail": detail}


def score(args) -> int:
    rows = {r["id"]: r for r in corpus.load(args.corpus)["rows"]}
    verdicts, missed = Counter(), Counter()
    for name, observed in read_observed(args.observed, args.factory):
        got = verdict(rows, observed)
        verdicts[got["verdict"]] += 1
        missed.update(got["missed_by"])
        print(json.dumps({"file": name, **got}, ensure_ascii=False))
    print(json.dumps({"verdicts": {v: verdicts[v] for v in corpus.VERDICTS}, "missed_by": dict(sorted(missed.items()))},
                     ensure_ascii=False))
    return OK


# 違いに数える欄と、その比べる値。単位と問いは数で比べる（名は工場ごとに語が違う）。費用は並べるだけ（2 つの工場で同じ値にならない）
DIFFERS = {"verdict": lambda v: v["verdict"], "outcome": lambda v: v["outcome"],
           "units": lambda v: v["units"] and v["units"]["count"], "asks": lambda v: v["asks"] and v["asks"]["count"]}


def view(rows: dict, observed: dict) -> dict:
    units, asks, cost = observed.get("units"), observed.get("asks"), _object(observed.get("cost"))
    return {"verdict": verdict(rows, observed)["verdict"], "outcome": observed.get("outcome"),
            "units": {"count": len(units), "names": units} if isinstance(units, list) else None,
            "asks": {"count": len(asks), "gates": asks} if isinstance(asks, list) else None,
            "cost": {"usd": cost.get("usd"), "seconds": cost.get("seconds")}}


def compare(args) -> int:
    """行ごとに両工場の observed を並べ、違う欄を differs に名指す。違いの訳の 1 行は人か運び役が reason に書く（出す時は空）"""
    rows = {r["id"]: r for r in corpus.load(args.corpus)["rows"]}
    flags = load_flags()
    sides = {}
    for factory in corpus.FACTORIES:
        now = fingerprint(factory, args.corpus, flags)
        for name, observed in read_observed(args.observed, factory):
            fresh = (isinstance(observed, dict) and (observed.get("provenance") or {}).get("fingerprint") == now
                     and all(field in observed for field in RECORDED))
            if not fresh:
                print(json.dumps({"stale": f"{factory}/{name}"}, ensure_ascii=False))
                continue
            sides.setdefault(observed.get("id"), {}).setdefault(factory, []).append(view(rows, observed))
    for row_id in sorted(sides, key=str):
        side = sides[row_id]
        if len(side) == 1:
            only = next(iter(side))
            print(json.dumps({"one_sided": row_id, "only": only, only: side[only]}, ensure_ascii=False))
            continue
        differs = [field for field, key in DIFFERS.items()
                   if len({tuple(sorted({json.dumps(key(v)) for v in views})) for views in side.values()}) > 1]
        print(json.dumps({"compare": row_id, "differs": differs, "reason": "", **side}, ensure_ascii=False))
    return OK


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--observed", default=str(OBSERVED))
    common.add_argument("--corpus", default=str(corpus.CORPUS))
    parser = argparse.ArgumentParser(description="較正の束を本物の工場に回すランナー")
    sub = parser.add_subparsers(dest="command", required=True)
    ran = sub.add_parser("run", parents=[common])
    ran.add_argument("factory", choices=corpus.FACTORIES)
    ran.add_argument("--attempts", required=True, type=Path)
    ran.add_argument("--only")
    ran.add_argument("--resume", action="store_true")
    ran.add_argument("--dry-run", action="store_true")
    scored = sub.add_parser("score", parents=[common])
    scored.add_argument("factory", choices=corpus.FACTORIES)
    again = sub.add_parser("reobserve", parents=[common])
    again.add_argument("factory", choices=corpus.FACTORIES)
    again.add_argument("--attempts", required=True, type=Path)
    again.add_argument("--only")
    sub.add_parser("compare", parents=[common])
    args = parser.parse_args(argv)
    try:
        return {"run": run_rows, "reobserve": reobserve_rows, "score": score, "compare": compare}[args.command](args)
    except (Stop, corpus.CorpusError) as e:
        print(f"run.py: {e}", file=sys.stderr)
        return getattr(e, "code", REFUSED)


if __name__ == "__main__":
    sys.exit(main())
