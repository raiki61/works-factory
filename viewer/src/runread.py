"""Archon の記録の読み（run の家の `archon.db`・run ごとの `logs/<run>.jsonl`・run の写しの在り処）。Archon の名を持つのはこの 1 か所。

名は止めた Archon（`factory/pack.json` の版）の源と同じ字にし、`tests/viewer/test_archon_names.py` が源に照らす。記録の行の型と
道具の出来事の型は、源の型の和の全部をここに持ち（読む型と読まない型）、源に在ってここに無い型も同じ試験が赤にする。知らない型の行は
数えて返し、黙って落とさない。DB は読むだけで開く。

- runs(db) -> 親の run（parent_run_id が空）の一覧。新しい順。DB の run の行だけを読み、ログは読まない
- run(db, run_id) -> 選んだ run と子の run の記録（ノードごとの出来事・道具の呼び出し・費用・出力・知らない行の数え）
- pick(db, wanted) -> run の id（wanted が空なら一番新しい親の run。頭の字でもよい）
- field(output, name) -> ノードの出力（値か JSON の字）の欄 name の字。読めなければ空
- where(path, cwd) -> 会話が読んだファイルのパスを、run ごとに違う頭（作業ツリー・run の置き場・run の写し）を印に替えた字にする
"""
import contextlib
import hashlib
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
# 新しい順。承認で再開した run は行の始めを今に書き直す（packages/core/src/db/workflow-run-resume.ts）ので、出来事の最初の時刻で並べる
# （出来事の無い run は行の始め）。時刻は秒まで（datetime('now')）で、並んだら後に作った行（rowid が大きい）を新しいとする
NEWEST = (f"order by coalesce((select min(created_at) from {EVENT_TABLE} where workflow_run_id = {RUN_TABLE}.id), started_at) desc, "
          f"{RUN_TABLE}.rowid desc")
EVENT_COLUMNS = ("workflow_run_id", "event_type", "step_name", "data", "event_order", "created_at")
# run の状態（packages/workflows/src/schemas/workflow-run.ts の workflowRunStatusSchema）
STATUSES = ("pending", "running", "completed", "failed", "cancelled", "paused")
LIVE = ("pending", "running", "paused")
# 答えを待つ run の状態。待ちはこの状態の run だけに出す（止めた・放棄した run は node_completed を書かずに終わる。
# packages/core/src/operations/workflow-operations.ts の resolveAndCancelApprovalGate・abandon）
PAUSED = "paused"
# 落ちた run の状態。流れの集計（src/stages.py）が止まった段を落ちた出来事から引く
FAILED = "failed"
# run の metadata の欄（子の run を起こしたノード・費用。packages/workflows/src/dag-executor.ts）
PARENT_NODE = "parent_node_id"
TOTAL_COST = "total_cost_usd"
# DB のノードの終わりの出来事の欄（AI の呼び出しの費用と、その費用がノード自身の物か。packages/workflows/src/node-record-serialization.ts）。
# run の費用 TOTAL_COST が空の run は、ノード自身の費用の和で代える
NODE_COST = "cost_usd"
ACCOUNTING = "accounting"
# run の metadata の待ち（packages/workflows/src/schemas/workflow-run.ts の workflowWaitAttentionFields と workflowWaitStepName）。
# 答えが入った待ちは、run が次へ進む前でも答えを待たない（同じファイルの runAttention の「Answered」）
WAIT = "wait"
WAIT_KIND = "attention"
WAIT_ANSWER = "answer"
WAIT_LOOP_OWNER = "loop_group"
# ノードの種類（packages/workflows/src/schemas/dag-node.ts の DagNode の kind。出来事の kind に入る）。流れの集計（src/stages.py）が、
# AI の手番・人の答え待ち・中の出来事を束ねる器（繰り返しの周の器・並べて起こす器・子の run を起こすノード。長さを足すと中の出来事と
# 二重になる。子の run を起こすノードの行は子の総額も載せる。packages/workflows/src/node-execution.ts の accounting）を分ける
AI_KINDS = ("agent", "loop")
WAIT_NODE = "wait"
LOOP_GROUP = "loop_group"
GROUP_KINDS = (LOOP_GROUP, "compose_fan_out", "workflow")
# DB の出来事の型（ノードの出力と、run の落ちの訳。packages/workflows/src/event-emitter.ts）
OUTPUT_EVENT = "node_completed"
NODE_OUTPUT = "node_output"
FAILED_EVENT = "workflow_failed"
NODE_FAILED_EVENT = "node_failed"
SUSPENDED_EVENT = "node_suspended"
# 出力の中の欄（Archon でなく工場の記録の名。読む名はここに置く）: 人の答え待ちの出力 {decision, text} の答えの語（lib/answer.py の
# decision）と、line の返すノード result の出力の結末の語（workflows/line/works-factory-line.yaml の result の output_format。語の組は
# lib/report.py の OUTCOMES）
ANSWER_DECISION = "decision"
RESULT_NODE = "result"
RESULT_OUTCOME = "outcome"

# ログの行の型（packages/workflows/src/logger.ts の WorkflowEvent の type と、packages/workflows/src/schemas/worktree-setup.ts の
# WORKTREE_SETUP_EVENT_TYPES）。読む型と、読まない型（訳つき）に分ける
NODE_ROWS = ("node_start", "node_complete", "node_error", "node_skipped", "node_suspended")
PROVIDER_ROW = runlog.PROVIDER_ROW
EXEC_ROW = runlog.EXEC_ROW
# loop_group の until_bash の確かめの行の step の名 `<輪>-iteration-<n>`（packages/workflows/src/dag-executor.ts）
ITERATION_MARK = runlog.ITERATION_MARK
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


@contextlib.contextmanager
def connect(db: Path):
    """読むだけで開き、抜ける時に閉じる（sqlite3 の with は commit するだけで閉じない）"""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        yield con
    finally:
        con.close()


def runs(db: Path) -> list[dict]:
    """親の run の一覧（新しい順）。行は id・グラフの名・状態・止まっている承認ノード・始め・かかった秒・費用（_cost）・落ちの訳の頭の 1 行・
    結末の語（line の返すノード result の出力の outcome。result の出力が無いか読めなければ空）。
    始めとかかった秒は、DB の出来事の最初と最後の時刻から出す（承認の答えで起き直した run は、run の行の始めが起き直した時刻に
    書き換わる。packages/core/src/db/workflow-run-resume.ts）。出来事の無い run は run の行の始めと終わり"""
    with connect(db) as con:
        rows = con.execute(f"select id, workflow_name, status, started_at, completed_at, metadata from {RUN_TABLE} "
                           f"where parent_run_id is null {NEWEST}").fetchall()
        spans = {rid: (first, last) for rid, first, last in con.execute(
            f"select workflow_run_id, min(created_at), max(created_at) from {EVENT_TABLE} group by workflow_run_id")}
        waiting = _waiting(con)
        spent = _spent(con)
        errors = {rid: _error(data) for rid, data in con.execute(
            f"select workflow_run_id, data from {EVENT_TABLE} where event_type = ?", (FAILED_EVENT,))}
        outcomes = {rid: field(_json(data).get(NODE_OUTPUT), RESULT_OUTCOME) for rid, data in con.execute(
            f"select workflow_run_id, data from {EVENT_TABLE} where event_type = ? and step_name = ? order by created_at, event_order",
            (OUTPUT_EVENT, RESULT_NODE))}
    out = []
    for rid, name, status, started, completed, metadata in rows:
        meta = _json(metadata)
        started, completed = spans.get(rid) or (started, completed)
        out.append({"id": rid, "short": rid[:8], "graph": name, "status": status, "waiting": waiting.get(rid, []),
                    "started": started, "seconds": _seconds(started, completed), "cost": _cost(meta, spent, rid),
                    "error": errors.get(rid, ""), "outcome": outcomes.get(rid, "")})
    return out


def pick(db: Path, wanted: str = "") -> str:
    """run の id。wanted が空なら一番新しい親の run、在れば id そのものか一意な頭の字。当たらなければ LookupError"""
    with connect(db) as con:
        if not wanted:
            row = con.execute(f"select id from {RUN_TABLE} where parent_run_id is null {NEWEST} limit 1").fetchone()
            if row is None:
                raise LookupError("run の家に親の run が無い")
            return row[0]
        hits = [r[0] for r in con.execute(f"select id from {RUN_TABLE} where id like ? || '%'", (wanted,))]
    if len(hits) != 1:
        raise LookupError(f"run {wanted} が{'無い' if not hits else f' {len(hits)} 個に当たる'}")
    return hits[0]


def run(db: Path, run_id: str) -> dict:
    """run と子の run（workflow: のノードが起こした物。DB の parent_run_id と metadata の parent_node_id で辿る）の記録。
    始めとかかった秒は、子の run を含む出来事の最初の始めと最後の終わりから出す（runs と同じ訳）。子の run の行も、その子と孫の出来事から出す"""
    with connect(db) as con:
        top = _row(con, run_id)
        if top is None:
            raise LookupError(f"run {run_id} が DB に無い")
        outputs = _outputs(con)
        waiting = _waiting(con)
        spent = _spent(con)
        reader = _Reader(outputs)
        reader.read(top, [])
        todo, parents = [(run_id, [])], {}
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
                parents[child["id"]] = parent
                todo.append((child["id"], prefix))
    meta = _json(top["metadata"])
    root = Path(top["output_root"]) if top["output_root"] else None
    started, ended = _span(reader.events) or (top["started_at"], top["completed_at"])
    for child in reader.children:
        child["started"], child["seconds"] = _child_span(child, reader.events, parents)
    return {"id": run_id, "graph": top["workflow_name"], "status": top["status"], "live": top["status"] in LIVE,
            "waiting": waiting.get(run_id, []), "started": started, "seconds": _seconds(started, ended),
            "cost": _cost(meta, spent, run_id), "copy": str(copy(root, run_id)) if root else "",
            "children": reader.children, "events": sorted(reader.events, key=lambda e: (e["start"] or "", "/".join(e["tokens"]))),
            "skipped": reader.skipped, "checks": reader.checks, "missing_logs": reader.missing, "unread": reader.unread, "artifacts": reader.artifacts}


def _cost(meta: dict, spent: dict, run_id: str) -> float | None:
    """run の費用。metadata の TOTAL_COST が空なら、子と孫の run を含む AI の呼び出しの費用の和（_spent）。どちらも無ければ空"""
    total = runlog.number(meta.get(TOTAL_COST))
    return total if total is not None else spent.get(run_id)


def _spent(con) -> dict[str, float]:
    """run ごとの AI の呼び出しの費用の和（DB のノードの終わりの出来事のうち、費用がノード自身の物の和。子と孫の run の分を親に足す。
    子の run を起こすノードの行は子の総額を載せ、ノード自身の物でないので数えない）"""
    own = {}
    for rid, data in con.execute(f"select workflow_run_id, data from {EVENT_TABLE} where event_type in (?, ?)", (OUTPUT_EVENT, NODE_FAILED_EVENT)):
        data = _json(data)
        if data.get(ACCOUNTING) == runlog.OWN_SPEND:
            own[rid] = own.get(rid, 0.0) + (runlog.number(data.get(NODE_COST)) or 0.0)
    parents = dict(con.execute(f"select id, parent_run_id from {RUN_TABLE} where parent_run_id is not null"))
    out = {}
    for rid, cost in own.items():
        seen = set()
        while rid and rid not in seen:
            seen.add(rid)
            out[rid] = out.get(rid, 0.0) + cost
            rid = parents.get(rid)
    return {rid: round(cost, 6) for rid, cost in out.items()}


def copy(output_root: Path, run_id: str) -> Path:
    """run の写しの中の pack の置き場の親（`<写し>/project/.archon/workflows`）"""
    return output_root / SOURCE / RUNS_DIR / run_id / PROJECT_SCOPE / WORKFLOW_FOLDER


# where の頭の印（ページに出す字）
PLACE_MARK = "（run の置き場）/"
COPY_MARK = "（run の写し）/"


def where(path: str, cwd: str) -> str:
    """会話が読んだファイルのパス（無駄の手がかりの読み直しの数え）。作業ツリー（会話の cwd）の下は cwd からのパス、run の置き場
    （`<output_root>/artifacts/runs/<run>/`）と run の写し（`<output_root>/workflow-source/runs/<run>/project/`）の下は印と run の id と
    その下のパス。同じファイルを相対と絶対のパスで読めば同じ字に、別の run（fan_out の子どうし・親と子）の同じ名のファイルは別の字になる"""
    if cwd and path.startswith(cwd.rstrip("/") + "/"):
        return path[len(cwd.rstrip("/")) + 1:]
    parts = path.split("/")
    for at in range(len(parts) - 2):
        if parts[at + 1] != RUNS_DIR:
            continue
        if parts[at] == ARTIFACTS:
            return PLACE_MARK + "/".join(parts[at + 2:])
        if parts[at] == SOURCE and parts[at + 3:at + 4] == [PROJECT_SCOPE]:
            return COPY_MARK + "/".join([parts[at + 2], *parts[at + 4:]])
    return path


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
                                  "started": row["started_at"], "completed": row["completed_at"]})
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
            self.skipped.append({"tokens": ids, "time": entry.get("ts"), "cause": entry.get("cause")})
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
            text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
            event["output"], event["digest"] = _clip(text), hashlib.sha1(text.encode("utf-8")).hexdigest()
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
        確かめ。step は `<輪>{ITERATION_MARK}<n>`）は run の確かめの行にする。行は書いた run の id を持つ（同じノードから起こした子の
        run どうしは node も step も同じになる）"""
        row = {"step": entry.get("step") or "", "node": prefix, "run": self.current, "label": entry.get(runlog.EXEC_LABEL) or "", "exit": entry.get(runlog.EXIT_CODE),
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


def _span(events: list[dict]) -> tuple[str, str] | None:
    """出来事の最初の始めと最後の終わり（終わりの無い出来事は始め）。読めない時刻は数えない。読める時刻が無ければ None"""
    times = [(at, t) for e in events for t in (e["start"], e["end"]) if t and (at := _try_time(t))]
    return (min(times)[1], max(times)[1]) if times else None


def _child_span(child: dict, events: list[dict], parents: dict) -> tuple[str, float | None]:
    """子の run の始めとかかった秒。その子と孫の出来事から出し、出来事が無ければ run の行の値。行の終わりの欄は外す"""
    def under(rid):
        while rid in parents:
            if rid == child["id"]:
                return True
            rid = parents[rid]
        return False
    completed = child.pop("completed")
    started, ended = _span([e for e in events if under(e["run"])]) or (child["started"], completed)
    return started, _seconds(started, ended)


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


def _try_time(text) -> datetime | None:
    try:
        return _time(text)
    except (TypeError, ValueError):
        return None


def field(output, name: str) -> str:
    """ノードの出力（値か JSON の字。DB の node_completed の node_output）の欄 name の字。出力が object でないか欄が字でなければ空"""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            return ""
    got = output.get(name) if isinstance(output, dict) else None
    return got if isinstance(got, str) else ""


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
