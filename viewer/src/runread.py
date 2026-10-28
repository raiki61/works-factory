"""Archon の記録の読み（run の家の `archon.db`・run ごとの `logs/<run>.jsonl`・run の写しの在り処）。Archon の名を持つのはこの 1 か所。

名は止めた Archon（`factory/pack.json` の版）の源と同じ字にし、`tests/viewer/test_archon_names.py` が源に照らす。記録の行の型と
道具の出来事の型は、源の型の和の全部をここに持ち（読む型と読まない型）、源に在ってここに無い型も同じ試験が赤にする。知らない型の行は
数えて返し、黙って落とさない。DB は読むだけで開く。

- runs(db) -> 親の run（parent_run_id が空）の一覧。新しい順。DB の run の行だけを読み、ログは読まない
- run(db, run_id) -> 選んだ run と子の run の記録（ノードごとの出来事・道具の呼び出し・費用・出力・知らない行の数え）
- pick(db, wanted) -> run の id（wanted が空なら一番新しい親の run。頭の字でもよい）
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import runlog   # lib/（viewer/src/__init__.py が sys.path に足す）
from viewer.src import shape

# 置き場（packages/core/src/db/connection.ts・packages/paths/src/archon-paths.ts の getStoragePathsForRoot・getRunLogPathForRoot・
# getRunWorkflowSourceDirForRoot・getRunArtifactsDirForRoot・getWorkflowFolderSearchPaths・packages/workflows/src/workflow-source.ts の
# PROJECT_SCOPE_DIR）
DB_FILE = "archon.db"
LOGS = "logs"
SOURCE = "workflow-source"
ARTIFACTS = "artifacts"
RUNS_DIR = "runs"
PROJECT_SCOPE = "project"
WORKFLOW_FOLDER = ".archon/workflows"

# DB の表と欄（packages/core/src/db/adapters/sqlite.ts の CREATE TABLE）
RUN_TABLE = "remote_agent_workflow_runs"
RUN_COLUMNS = ("id", "workflow_name", "status", "parent_run_id", "started_at", "completed_at", "output_root", "metadata")
EVENT_TABLE = "remote_agent_workflow_events"
EVENT_COLUMNS = ("workflow_run_id", "event_type", "step_name", "data", "event_order", "created_at")
# run の状態（packages/workflows/src/schemas/workflow-run.ts の workflowRunStatusSchema）
STATUSES = ("pending", "running", "completed", "failed", "cancelled", "paused")
LIVE = ("pending", "running", "paused")
# 答えを待つ run の状態。待ちはこの状態の run だけに出す（止めた・放棄した run は node_completed を書かずに終わる。
# packages/core/src/operations/workflow-operations.ts の resolveAndCancelApprovalGate・abandon）
PAUSED = "paused"
# run の metadata の欄（子の run を起こしたノード・費用。packages/workflows/src/dag-executor.ts）
PARENT_NODE = "parent_node_id"
TOTAL_COST = "total_cost_usd"
# run の metadata の待ち（packages/workflows/src/schemas/workflow-run.ts の workflowWaitAttentionFields と workflowWaitStepName）。
# 答えが入った待ちは、run が次へ進む前でも答えを待たない（同じファイルの runAttention の「Answered」）
WAIT = "wait"
WAIT_KIND = "attention"
WAIT_ANSWER = "answer"
WAIT_LOOP_OWNER = "loop_group"
# DB の出来事の型（ノードの出力と、run の落ちの訳。packages/workflows/src/event-emitter.ts）
OUTPUT_EVENT = "node_completed"
NODE_OUTPUT = "node_output"
FAILED_EVENT = "workflow_failed"
SUSPENDED_EVENT = "node_suspended"

# ログの行の型（packages/workflows/src/logger.ts の WorkflowEvent の type と、packages/workflows/src/schemas/worktree-setup.ts の
# WORKTREE_SETUP_EVENT_TYPES）。読む型と、読まない型（訳つき）に分ける
NODE_ROWS = ("node_start", "node_complete", "node_error", "node_skipped", "node_suspended")
PROVIDER_ROW = runlog.PROVIDER_ROW
EXEC_ROW = runlog.EXEC_ROW
READ_ROWS = (*NODE_ROWS, PROVIDER_ROW, EXEC_ROW)
UNREAD_ROWS = {
    "gate_decision": "古い承認ノード approval: の答え。工場の承認ノード wait: attention はこの行を書かず、答えをノードの出力 {decision, text} に持つ",
    "workflow_start": "run の始めの印。始めの時刻は DB の run の行から読む",
    "workflow_resume": "resume の境の印。ノードの出来事は resume の前と後の行を同じに読む",
    "workflow_complete": "run の終わりの印。状態・終わりの時刻・費用は DB の run の行から読む",
    "workflow_error": "run の落ちの印。落ちの訳は DB の workflow_failed から読む",
    "watchdog_reset": "期限の見張りを延ばした印で、中身を持たない",
    "assistant": "古い記録だけの型（provider_event に替わった）",
    "tool": "古い記録だけの型（provider_event に替わった）",
    "validation": "古い記録だけの型（書く所が消えた）",
    "worktree_setup_started": "作業ツリーの用意の始めで、ノードの出来事でない",
    "worktree_setup_completed": "作業ツリーの用意の終わりで、ノードの出来事でない",
    "worktree_setup_failed": "作業ツリーの用意の落ちで、run の落ちの訳は DB の workflow_failed から読む",
}
# 道具の出来事の型（packages/provider-contract/src/events.ts の providerEventSchema の和）
TOOL_CALL = runlog.TOOL_CALL
TOOL_UPDATE = "tool_call_update"
READ_EVENTS = (TOOL_CALL, TOOL_UPDATE, "warning", "subtask")
UNREAD_EVENTS = {
    "agent_message_chunk": "AI の言葉の断片。会話の中身は Claude Code の記録から読む",
    "agent_thought_chunk": "AI の考えの断片。会話の中身は Claude Code の記録から読む",
    "mcp_server_status": "MCP の口の状態",
    "compaction": "会話の縮め",
    "hook": "フックの起動",
    "state_update": "動いているか待っているかの印",
}
# 行の欄（logger.ts・schemas/node-execution.ts・schemas/provider-event.ts）
EXECUTION = "execution"
EVENT = runlog.PROVIDER_EVENT
ATTEMPT_ID = "attemptId"

CLIP = 20000
ARTIFACT_LIMIT = 60000


def connect(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def runs(db: Path) -> list[dict]:
    """親の run の一覧（新しい順）。行は id・グラフの名・状態・止まっている承認ノード・始め・かかった秒・費用・落ちの訳の頭の 1 行"""
    with connect(db) as con:
        rows = con.execute(f"select id, workflow_name, status, started_at, completed_at, metadata from {RUN_TABLE} "
                           "where parent_run_id is null order by started_at desc").fetchall()
        waiting = _waiting(con)
        errors = {rid: _error(data) for rid, data in con.execute(
            f"select workflow_run_id, data from {EVENT_TABLE} where event_type = ?", (FAILED_EVENT,))}
    out = []
    for rid, name, status, started, completed, metadata in rows:
        meta = _json(metadata)
        out.append({"id": rid, "short": rid[:8], "graph": name, "status": status, "waiting": waiting.get(rid, []),
                    "started": started, "seconds": _seconds(started, completed), "cost": runlog.number(meta.get(TOTAL_COST)),
                    "error": errors.get(rid, "")})
    return out


def pick(db: Path, wanted: str = "") -> str:
    """run の id。wanted が空なら一番新しい親の run、在れば id そのものか一意な頭の字。当たらなければ LookupError"""
    with connect(db) as con:
        if not wanted:
            row = con.execute(f"select id from {RUN_TABLE} where parent_run_id is null order by started_at desc limit 1").fetchone()
            if row is None:
                raise LookupError("run の家に親の run が無い")
            return row[0]
        hits = [r[0] for r in con.execute(f"select id from {RUN_TABLE} where id like ? || '%'", (wanted,))]
    if len(hits) != 1:
        raise LookupError(f"run {wanted} が{'無い' if not hits else f' {len(hits)} 個に当たる'}")
    return hits[0]


def run(db: Path, run_id: str) -> dict:
    """run と子の run（workflow: のノードが起こした物。DB の parent_run_id と metadata の parent_node_id で辿る）の記録"""
    with connect(db) as con:
        top = _row(con, run_id)
        if top is None:
            raise LookupError(f"run {run_id} が DB に無い")
        outputs = _outputs(con)
        waiting = _waiting(con)
        reader = _Reader(outputs)
        reader.read(top, [])
        todo = [(run_id, [])]
        while todo:
            parent, head = todo.pop(0)
            for child in con.execute(f"select {', '.join(RUN_COLUMNS)} from {RUN_TABLE} where parent_run_id = ? order by started_at",
                                     (parent,)).fetchall():
                child = dict(zip(RUN_COLUMNS, child))
                node = _json(child["metadata"]).get(PARENT_NODE) or ""
                if not node:
                    reader.unread["子の run に parent_node_id が無い"] = reader.unread.get("子の run に parent_node_id が無い", 0) + 1
                    continue
                prefix = [*head, node]
                reader.read(child, prefix)
                todo.append((child["id"], prefix))
    meta = _json(top["metadata"])
    root = Path(top["output_root"]) if top["output_root"] else None
    return {"id": run_id, "graph": top["workflow_name"], "status": top["status"], "live": top["status"] in LIVE,
            "waiting": waiting.get(run_id, []), "started": top["started_at"], "seconds": _seconds(top["started_at"], top["completed_at"]),
            "cost": runlog.number(meta.get(TOTAL_COST)), "copy": str(copy(root, run_id)) if root else "",
            "children": reader.children, "events": sorted(reader.events, key=lambda e: (e["start"] or "", "/".join(e["tokens"]))),
            "skipped": reader.skipped, "checks": reader.checks, "missing_logs": reader.missing, "unread": reader.unread, "artifacts": reader.artifacts}


def copy(output_root: Path, run_id: str) -> Path:
    """run の写しの中の pack の置き場の親（`<写し>/project/.archon/workflows`）"""
    return output_root / SOURCE / RUNS_DIR / run_id / PROJECT_SCOPE / WORKFLOW_FOLDER


class _Reader:
    def __init__(self, outputs: dict):
        self.outputs = outputs
        self.events, self.skipped, self.children, self.missing, self.checks, self.artifacts = [], [], [], [], [], {}
        self.unread: dict[str, int] = {}
        self.current = ""

    def read(self, row: dict, prefix: list[str]) -> None:
        self.current = row["id"]
        root = Path(row["output_root"]) if row["output_root"] else None
        log = root / LOGS / f"{row['id']}.jsonl" if root else None
        if prefix:
            self.children.append({"id": row["id"], "graph": row["workflow_name"], "status": row["status"], "node": prefix,
                                  "started": row["started_at"], "seconds": _seconds(row["started_at"], row["completed_at"])})
        if log is None or not log.is_file():
            self.missing.append(row["id"])
            return
        by_invocation, by_attempt, by_step = {}, {}, {}
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                self._count("JSON でない行")
                continue
            kind = entry.get("type")
            if kind in UNREAD_ROWS:
                continue
            if kind not in READ_ROWS:
                self._count(f"知らない行の型 {kind}")
            elif kind in NODE_ROWS:
                self._node(entry, kind, prefix, by_invocation, by_attempt, by_step, root)
            elif kind == PROVIDER_ROW:
                self._provider(entry, by_attempt)
            elif kind == EXEC_ROW:
                self._exec(entry, prefix, by_step)

    def _node(self, entry, kind, prefix, by_invocation, by_attempt, by_step, root):
        execution = entry.get(EXECUTION) or {}
        path = execution.get("path") or entry.get("step") or ""
        invocation = (execution.get("invocation") or {})
        key = (path, invocation.get("id") or "")
        ids = [*_tokens(prefix), *_tokens([path])]
        if kind == "node_skipped":
            self.skipped.append({"tokens": ids, "at": entry.get("ts"), "cause": entry.get("cause")})
            return
        event = by_invocation.get(key)
        if event is None:
            event = {"tokens": ids, "path": path, "run": self.current, "artifacts": str(root / ARTIFACTS / RUNS_DIR / self.current) if root else "",
                     "kind": (execution.get("node") or {}).get("kind") or "", "start": entry.get("ts"),
                     "end": None, "status": "running", "loop": [step.get("iteration") for step in invocation.get("loopPath") or []],
                     "cost": 0.0, "calls": [], "exec": [], "error": ""}
            by_invocation[key] = event
            self.events.append(event)
        by_step[entry.get("step") or path] = event
        attempt = (execution.get("attempt") or {}).get("id")
        if attempt:
            by_attempt[attempt] = event
        if kind == "node_start":
            return
        if kind == "node_suspended":
            event["status"] = "waiting"
            return
        event["end"] = entry.get("ts")
        event["status"] = "ok" if kind == "node_complete" else "failed"
        if kind == "node_error":
            event["error"] = entry.get("error") or (execution.get("lifecycle") or {}).get("error") or ""
        if execution.get("accounting") == runlog.OWN_SPEND:
            event["cost"] += runlog.number(entry.get("cost_usd")) or 0.0
        spend, binding = execution.get("spend") or {}, execution.get("binding") or {}
        if binding.get("sessionPreview"):
            model = binding.get("model") or {}
            event.update(session=binding["sessionPreview"], origin=binding.get("sessionOrigin") or "",
                         model=(model.get("resolved") or {}).get("value") or model.get("requested") or "", effort=binding.get("effort") or "",
                         usage=runlog.tokens(runlog.measurement(spend, "tokens", lambda v: v)[0]),
                         turns=runlog.measurement(spend, "numTurns")[0])
        output = self.outputs.get(key[1])
        if output is not None:
            event["output"] = _clip(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False))
            self._artifacts(output, root)

    def _provider(self, entry, by_attempt):
        event = by_attempt.get(entry.get(ATTEMPT_ID))
        got = entry.get(EVENT) or {}
        kind = got.get("type")
        if kind in UNREAD_EVENTS:
            return
        if kind not in READ_EVENTS:
            self._count(f"知らない道具の出来事の型 {kind}")
            return
        if event is None:
            self._count("ノードに当たらない道具の出来事")
            return
        if kind == TOOL_CALL:
            event["calls"].append({"id": got.get("toolCallId"), "name": got.get(runlog.TOOL_NAME), "title": _clip(got.get("title") or "", 400),
                                   "status": "", "error": False})
        elif kind == TOOL_UPDATE:
            call = next((c for c in event["calls"] if c["id"] == got.get("toolCallId")), None)
            if call is not None:
                call["status"] = got.get("status") or ""
        else:
            event["calls"].append({"id": None, "name": kind, "title": _clip(_text(got.get("message") or got.get("description") or got), 400),
                                   "status": got.get("status") or "", "error": False})

    def _exec(self, entry, prefix, by_step):
        """script・bash のノードの出力の終わりは、同じ step の最後の起動に付ける。ノードに当たらない物（loop_group の until_bash の
        確かめ。step は `<輪>-iteration-<n>`）は run の確かめの行にする"""
        row = {"step": entry.get("step") or "", "node": prefix, "label": entry.get(runlog.EXEC_LABEL) or "", "exit": entry.get(runlog.EXIT_CODE),
               "stdout": _clip(entry.get("stdout_tail") or "", 4000), "stderr": _clip(entry.get("stderr_tail") or "", 4000), "at": entry.get("ts")}
        event = by_step.get(row["step"])
        if event is None:
            self.checks.append(row)
        else:
            event["exec"].append(row)

    def _artifacts(self, output, root):
        """出力が指す run の置き場の小さなファイル（archon_artifact）の中身"""
        try:
            value = json.loads(output) if isinstance(output, str) else output
        except ValueError:
            return
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("type") == "archon_artifact" and item.get("path") and root:
                    key = f"{item.get('run_id')}/{item['path']}"
                    path = root / ARTIFACTS / RUNS_DIR / str(item.get("run_id") or "") / item["path"]
                    if key not in self.artifacts and path.is_file() and path.stat().st_size <= ARTIFACT_LIMIT:
                        self.artifacts[key] = path.read_text(encoding="utf-8", errors="replace")
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    def _count(self, what: str) -> None:
        self.unread[what] = self.unread.get(what, 0) + 1


def _tokens(paths: list[str]) -> list[str]:
    return [t for path in paths for t in shape.tokens(path)]


def _row(con, run_id: str) -> dict | None:
    row = con.execute(f"select {', '.join(RUN_COLUMNS)} from {RUN_TABLE} where id = ?", (run_id,)).fetchone()
    return dict(zip(RUN_COLUMNS, row)) if row else None


def _outputs(con) -> dict:
    """ノードの起動（invocation の id）ごとの出力の全文（DB の node_completed）"""
    out = {}
    for (data,) in con.execute(f"select data from {EVENT_TABLE} where event_type = ?", (OUTPUT_EVENT,)):
        got = _json(data)
        invocation = (got.get("invocation") or {}).get("id")
        if invocation and got.get(NODE_OUTPUT) is not None:
            out[invocation] = got[NODE_OUTPUT]
    return out


def _waiting(con) -> dict:
    """答えを待つ run（状態が paused）ごとの、止まって答えを待つノード（node_suspended の後に同じノードの終わりが無い物）。
    答えが入って次へ進む前のノード（metadata の待ちに答えが在る物）は外す"""
    out = {}
    for rid, step, kind in con.execute(f"select e.workflow_run_id, e.step_name, e.event_type from {EVENT_TABLE} e "
                                       f"join {RUN_TABLE} r on r.id = e.workflow_run_id where r.status = ? and e.event_type in (?, ?) "
                                       "order by e.workflow_run_id, e.created_at, e.event_order",
                                       (PAUSED, SUSPENDED_EVENT, OUTPUT_EVENT)):
        names = out.setdefault(rid, [])
        if kind == SUSPENDED_EVENT and step not in names:
            names.append(step)
        elif kind == OUTPUT_EVENT and step in names:
            names.remove(step)
    for rid, metadata in con.execute(f"select id, metadata from {RUN_TABLE} where status = ?", (PAUSED,)):
        wait = _json(metadata).get(WAIT)
        if isinstance(wait, dict) and wait.get("kind") == WAIT_KIND and wait.get(WAIT_ANSWER) is not None:
            step = f"{wait.get('nodeId')}.{wait.get('bodyWaitId')}" if wait.get("owner") == WAIT_LOOP_OWNER else wait.get("nodeId")
            if step in out.get(rid, []):
                out[rid].remove(step)
    return {rid: names for rid, names in out.items() if names}


def _error(data: str) -> str:
    text = _json(data).get("error") or ""
    return text.splitlines()[0][:300] if isinstance(text, str) and text else ""


def _seconds(started, completed):
    if not started or not completed:
        return None
    try:
        return round((_time(completed) - _time(started)).total_seconds(), 1)
    except ValueError:
        return None


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _json(text) -> dict:
    try:
        got = json.loads(text or "{}")
    except (TypeError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _clip(text: str, size: int = CLIP) -> str:
    return text if len(text) <= size else text[:size] + f"\n…（残り {len(text) - size} 字）"
