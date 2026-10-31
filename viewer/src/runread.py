"""Archon の記録の読み（run の家の `archon.db`・run ごとの `logs/<run>.jsonl`・run の写しの在り処）。Archon の名を持つのはこの 1 か所。

名は止めた Archon（`factory/pack.json` の版）の源と同じ字にし、`tests/viewer/test_archon_names.py` が源に照らす。記録の行の型と
道具の出来事の型は、源の型の和の全部をここに持ち（読む型と読まない型）、源に在ってここに無い型も同じ試験が赤にする。知らない型の行は
数えて返し、黙って落とさない。DB は読むだけで開く。

- runs(db) -> 親の run（parent_run_id が空）の一覧。新しい順。DB の run の行だけを読み、ログは読まない
- run(db, run_id) -> 選んだ run と子の run の記録（ノードごとの出来事・道具の呼び出し・費用・出力・知らない行の数え）
- pick(db, wanted) -> run の id（wanted が空なら一番新しい親の run。頭の字でもよい）
- field(output, name) -> ノードの出力（値か JSON の字）の欄 name の字。読めなければ空
- seconds(started, completed)・length(event)・when(text)・try_when(text) -> 時刻の差の秒・出来事の長さ・時刻の読み（読めなければ
  ValueError か None。字でない時刻も try_when は None。DB の秒までの時刻は UTC として読む）。段の集計と無駄の手がかりと会話の読みも使う
- where(path, cwd) -> 会話が読んだファイルのパスを、run ごとに違う頭（作業ツリー・run の置き場・run の写し）を印に替えた字にする
- plain(value) -> 字か None の値をそのまま返す。ほかの形は TypeError（読む側が欄の形が違う行に数える）。会話の読みも使う
"""
import contextlib
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
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
# 落ちた run の状態。流れの集計（src/stages.py）が止まった段を落ちた出来事から引き、落ちの訳もこの状態の run だけに出す（落ちた後に
# 起き直して終わった run は workflow_failed の行を残す。packages/workflows/src/dag-resume-snapshot.ts の resuming a failed run）
FAILED = "failed"
# run の metadata の欄（子の run を起こしたノード・費用。packages/workflows/src/dag-executor.ts）
PARENT_NODE = "parent_node_id"
TOTAL_COST = "total_cost_usd"
# DB のノードの終わりの出来事の欄（AI の呼び出しの費用と、その費用がノード自身の物か。packages/workflows/src/node-record-serialization.ts）。
# run の費用 TOTAL_COST が空の run は、ノード自身の費用の和で代える（後から書く費用の出来事 DEFERRED_EVENT も同じファイル）
NODE_COST = "cost_usd"
ACCOUNTING = "accounting"
# 費用を数える形は Archon の nodeCostScope（同じファイル）と resume の和（packages/workflows/src/dag-resume-snapshot.ts）に合わせる:
# accounting の語（schemas/node-execution.ts）の node だけが自前。accounting の無い古い行は印 AGGREGATE が true でなければ自前。
# compose_fan_out の instance の終わりの行（出力の欄 type が INSTANCE）はその中の全部の正で、中の行（道の頭が `<instance の道>__`）は外す
ACCOUNTINGS = ("node", "aggregate", "instance", "amendment")
AGGREGATE = "aggregate"
INSTANCE = "compose_fan_out_instance"
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
# run の終わりの出来事。終わった run は、最後のこの出来事の時刻を run の終わりにする（ログに終わりを書かずに落ちた・止めた run も）
END_EVENTS = ("workflow_completed", FAILED_EVENT, "workflow_cancelled")
NODE_FAILED_EVENT = "node_failed"
DEFERRED_EVENT = "node_deferred_usage"
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
# 起き直した run が前の起動で済んだノードについて書く node_skipped の content（packages/workflows/src/node-event-write.ts）。
# 飛んだノードに数えない（その道が済んだことは前の起動の出来事で見える）
PRIOR_SUCCESS = "prior_success"
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
# 続けた会話の印（execution.binding.sessionOrigin。packages/workflows/src/node-execution.ts）。続けた会話の記録は前の会話の往復を写して持つ
RESUMED = "resumed"
EVENT = runlog.PROVIDER_EVENT
ATTEMPT_ID = "attemptId"

CLIP = 20000
ARTIFACT_LIMIT = 60000
# 読めなかった物の訳（run["unread"] の鍵）
OBJECTLESS = "JSON の object でない行"
# object の行の中の欄の形が違う行（欄が object でない・在るはずの字が無いか字でない）。会話の記録の読み（src/session.py）も使う
SHAPELESS = "欄の形が違う行"
OUTSIDE = "run の置き場の外を指す archon_artifact"
NUL_PATH = "NUL の字を持つ path の archon_artifact"
# 片割れのサロゲート（json.loads は組の \ud83d\ude00 を 1 字にするので、字に残るのは片割れだけ）と、置き換える字
LONE = re.compile("[\ud800-\udfff]")
REPLACEMENT = "\ufffd"


@contextlib.contextmanager
def connect(db: Path):
    """読むだけで開き、抜ける時に閉じる（sqlite3 の with は commit するだけで閉じない）"""
    con = sqlite3.connect(f"{db.absolute().as_uri()}?mode=ro", uri=True)
    try:
        yield con
    finally:
        con.close()


def runs(db: Path) -> list[dict]:
    """親の run の一覧（新しい順）。行は id・グラフの名・状態・止まっている承認ノード・始め・かかった秒・費用（_cost）・落ちの訳の頭の 1 行
    （状態が failed の run だけ）・結末の語（line の返すノード result の出力の outcome。result の出力が無いか読めなければ空）。
    始めとかかった秒は、DB の出来事の最初と最後の時刻から出す（承認の答えで起き直した run は、run の行の始めが起き直した時刻に
    書き換わる。packages/core/src/db/workflow-run-resume.ts）。始めは選んだ run と同じ定義（_firsts）。終わった run の終わりは最後の
    終わりの出来事（_ends）。出来事の無い run は run の行の始めと終わり"""
    with connect(db) as con:
        rows = con.execute(f"select id, workflow_name, status, started_at, completed_at, metadata from {RUN_TABLE} "
                           f"where parent_run_id is null {NEWEST}").fetchall()
        firsts = _firsts(con)
        lasts = dict(con.execute(f"select workflow_run_id, max(created_at) from {EVENT_TABLE} group by workflow_run_id").fetchall())
        waiting = _waiting(con)
        spent = _spent(con)
        ends = _ends(con)
        errors = {rid: _error(data) for rid, data in con.execute(
            f"select workflow_run_id, data from {EVENT_TABLE} where event_type = ?", (FAILED_EVENT,))}
        outcomes = {rid: field(_json(data).get(NODE_OUTPUT), RESULT_OUTCOME) for rid, data in con.execute(
            f"select workflow_run_id, data from {EVENT_TABLE} where event_type = ? and step_name = ? order by created_at, event_order",
            (OUTPUT_EVENT, RESULT_NODE))}
    out = []
    for rid, name, status, started, completed, metadata in rows:
        meta = _json(metadata)
        if rid in firsts:
            started, completed = firsts[rid], lasts[rid]
        completed = _end(status, (ends.get(rid) or [None])[-1]) or completed
        out.append({"id": rid, "short": rid[:8], "graph": name, "status": status, "waiting": waiting.get(rid, []),
                    "started": started, "seconds": seconds(started, completed), "cost": _cost(meta, spent, rid),
                    "error": errors.get(rid, "") if status == FAILED else "", "outcome": outcomes.get(rid, "")})
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
    始めとかかった秒は、子の run を含む出来事の最初の始めと最後の終わりから出す（runs と同じ訳）。子の run の行も、その子と孫の出来事から出す。
    始めは、ログの最初の始めと DB の出来事の最初（_firsts。run の始めの印 workflow_started を含む）の早い方（DB の時刻は秒までの切り捨て
    なので、同じ秒ならログ）。一覧と同じ定義にし、長さが秒の丸めの内で合う。
    終わった run（子の run も）は、終わりを最後の終わりの出来事の時刻とログの最後の終わりの遅い方にし（DB の時刻は秒までの切り捨て）、
    終わりの無い出来事（待ちと、走り中のまま止まったノード）を、その run の終わりの出来事のうち始めの後の最初の物の時刻で閉じて印 cut を
    付ける（ログに終わりを書かずに落ちた・止めた run の長さと人の答え待ちの和が、一覧と合う。落ちた後に起き直した run の前の起動の
    ノードは、その落ちで閉じて状態を落ちたにする。前の起動の id のまま走り直す出来事は、最後の始めの後の終わりで閉じる。閉じる時刻は
    ログの形にし、始めより前にしない）。走り中の run は最後の出来事まで。
    落ちた後に同じ起動の id で走り直したノードは、起動ごとの出来事にする（_Reader._fallen）"""
    with connect(db) as con:
        top = _row(con, run_id)
        if top is None:
            raise LookupError(f"run {run_id} が DB に無い")
        outputs, odd = _outputs(con)
        waiting = _waiting(con)
        spent = _spent(con)
        ends = _ends(con)
        falls = _ends(con, (FAILED_EVENT,))
        first = _firsts(con).get(run_id)
        # 落ちは過去の事実なので、走り中の run（落ちた後に起き直した物）でも閉じる
        fell = {rid: [at for t in times if (at := _end("", t, live=True))] for rid, times in falls.items()}
        reader = _Reader(outputs, fell)
        if odd:
            reader.unread[SHAPELESS] = odd
        reader.read(top, [])
        todo, parents = [(run_id, [])], {}
        while todo:
            parent, head = todo.pop(0)
            for child in con.execute(f"select {', '.join(RUN_COLUMNS)} from {RUN_TABLE} where parent_run_id = ? order by started_at",
                                     (parent,)).fetchall():
                child = dict(zip(RUN_COLUMNS, child))
                node = _json(child["metadata"]).get(PARENT_NODE) or ""
                if not isinstance(node, str):
                    reader._count(SHAPELESS)
                    continue
                if not node:
                    reader.unread["子の run に parent_node_id が無い"] = reader.unread.get("子の run に parent_node_id が無い", 0) + 1
                    continue
                prefix = [*head, node]
                reader.read(child, prefix)
                parents[child["id"]] = parent
                todo.append((child["id"], prefix))
    meta = _json(top["metadata"])
    root = Path(top["output_root"]) if top["output_root"] else None
    closed = {row["id"]: [at for t in ends.get(row["id"], []) if (at := _end(row["status"], t))] for row in (top, *reader.children)}
    for event in reader.events:
        if not event["start"] or event["end"] or event["status"] not in ("waiting", "running"):
            continue
        # 起き直した後も同じ起動の id で走り直す出来事は、最後の始めの後の終わり（落ち）で閉じる。前の落ちでは閉じない
        begun, ends = event["last_start"] or event["start"], closed[event["run"]]
        at = _close(begun, ends) if ends else next(iter(_since(begun, fell.get(event["run"], []))), None)
        if at is None:
            continue
        event["end"], event["cut"] = _later(at, begun), True
        if event["status"] == "running" and at in fell.get(event["run"], []) and (not ends or at != ends[-1]):
            event["status"] = FAILED
    started, ended = _span(reader.events) or (top["started_at"], top["completed_at"])
    started = _earlier(_end(top["status"], first, live=True), started)
    ended = _later((closed[top["id"]] or [None])[-1], ended)
    for child in reader.children:
        child["started"], child["seconds"] = _child_span(child, reader.events, parents, (closed[child["id"]] or [None])[-1])
    return {"id": run_id, "graph": top["workflow_name"], "status": top["status"], "live": top["status"] in LIVE,
            "waiting": waiting.get(run_id, []), "started": started, "seconds": seconds(started, ended),
            "cost": _cost(meta, spent, run_id), "copy": str(copy(root, run_id)) if root else "",
            "children": reader.children, "events": sorted(reader.events, key=lambda e: (e["start"] or "", "/".join(e["tokens"]))),
            "skipped": reader.skipped, "checks": reader.checks, "missing_logs": reader.missing, "unread": reader.unread, "artifacts": reader.artifacts}


def _cost(meta: dict, spent: dict, run_id: str) -> float | None:
    """run の費用。metadata の TOTAL_COST と、run 自身の AI の呼び出しの費用の和（_spent）の大きい方（片方だけならそれ、どちらも無ければ空）。
    Archon は TOTAL_COST を run の末尾（待ち・落ち・終わり）だけで書き（packages/workflows/src/dag-executor.ts の persistRunUsage）、
    SIGTERM で落とす道（packages/cli/src/utils/owned-run-termination.ts の failWorkflowRun）は書かない。費用は減らないので、古い値は
    今の和より小さい: 承認で起き直して走っている run と、その後に SIGTERM で落ちた run の TOTAL_COST は前の待ちの時の値で、和の方が大きい"""
    known = [cost for cost in (runlog.number(meta.get(TOTAL_COST)), spent.get(run_id)) if cost is not None]
    return max(known) if known else None


def _spent(con) -> dict[str, float]:
    """run ごとの費用の和（DB のノードの終わりと後から書く費用の出来事のうち、自前の費用の行〔own_spend〕の和。run 自身の行だけを足す）。
    compose_fan_out の instance の終わりの行はその中の全部の正で、中の行は外す。費用の欄を持つ行が 1 つも無い run は和を出さない
    （bash だけの run を無料の AI の run に見せない。persistRunUsage と同じ）。
    子の run の費用は、親の run の子の run を起こすノード（workflow）の行が accounting を node にして子の総額を載せ、TOTAL_COST もこの行を
    通して子の分を含む。子の run の行を別に足すと二重に数える"""
    rows, scopes = {}, {}
    for rid, kind, step, data in con.execute(f"select workflow_run_id, event_type, step_name, data from {EVENT_TABLE} "
                                             "where event_type in (?, ?, ?)", (OUTPUT_EVENT, NODE_FAILED_EVENT, DEFERRED_EVENT)):
        data = _json(data)
        if data.get("type") == INSTANCE and kind in (OUTPUT_EVENT, NODE_FAILED_EVENT):
            scopes.setdefault(rid, set()).add(step or "")
        elif not own_spend(data.get(ACCOUNTING), data.get(AGGREGATE)):
            continue
        cost = runlog.number(data.get(NODE_COST))
        if cost is not None:
            rows.setdefault(rid, []).append((step or "", cost))
    out = {}
    for rid, costs in rows.items():
        inner = tuple(f"{scope}{shape.INCLUDED}" for scope in scopes.get(rid, ()))
        kept = [cost for step, cost in costs if not (inner and step.startswith(inner))]
        if kept:
            out[rid] = round(sum(kept), 6)
    return out


def own_spend(accounting, aggregate) -> bool:
    """行の費用が自前か（Archon の nodeCostScope）。accounting の語が在れば node だけ、無い古い行は aggregate の印が true でなければ自前"""
    if accounting in ACCOUNTINGS:
        return accounting == runlog.OWN_SPEND
    return aggregate is not True


def _ends(con, kinds: tuple[str, ...] = END_EVENTS) -> dict[str, list[str]]:
    """run ごとの終わりの出来事（既定は END_EVENTS。落ちだけなら FAILED_EVENT）の時刻（古い順。落ちた後に起き直した run は 2 つ以上）"""
    marks = ", ".join("?" * len(kinds))
    out = {}
    for rid, at in con.execute(f"select workflow_run_id, created_at from {EVENT_TABLE} where event_type in ({marks}) "
                               "order by created_at, event_order", kinds):
        out.setdefault(rid, []).append(at)
    return out


def _firsts(con) -> dict[str, str]:
    """run ごとの DB の出来事の最初の時刻（run の始めの印 workflow_started を含む）。一覧と選んだ run の始めの元"""
    return dict(con.execute(f"select workflow_run_id, min(created_at) from {EVENT_TABLE} group by workflow_run_id").fetchall())


def _end(status: str, end: str | None, live: bool = False) -> str | None:
    """DB の時刻をログの形にした物（終わった run の終わりの出来事の時刻は、出来事を閉じる時刻になる）。走り中の run（live が偽の時）と
    時刻の無い run と、読めない時刻は None"""
    at = try_when(end) if live or status not in LIVE else None
    return at.strftime("%Y-%m-%dT%H:%M:%S.") + f"{at.microsecond // 1000:03d}Z" if at else None


def _close(start: str, ends: list[str]) -> str:
    """終わりの無い出来事を閉じる終わりの出来事の時刻: 始めの後の最初の物（_since）。始めの後に無ければ最後の物。閉じる時刻は呼ぶ側が
    始めより前にしない（長さを負にしない）"""
    return (_since(start, ends) or ends[-1:])[0]


def _since(start: str, ends: list[str]) -> list[str]:
    """始めの後の終わりの出来事の時刻（DB の時刻は秒までの切り捨てなので、始めと同じ秒の物も数える）"""
    begun = try_when(start)
    floor = begun.replace(microsecond=0) if begun else None
    return [t for t in ends if floor is None or when(t) >= floor]


def _earlier(a: str | None, b: str | None) -> str | None:
    """DB の時刻 a とログの時刻 b の早い方。a は秒までの切り捨てなので、b と同じ秒なら b（読めない方と空は外す）"""
    db, log = try_when(a), try_when(b)
    if db and log:
        return a if db < log.replace(microsecond=0) else b
    return b if log else a


def _later(a: str | None, b: str | None) -> str | None:
    """2 つの時刻の遅い方（読めない方と空は外す）"""
    known = [(at, t) for t in (a, b) if (at := try_when(t))]
    return max(known)[1] if known else a or b


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
    def __init__(self, outputs: dict, falls: dict[str, list[str]]):
        """outputs は起動の id ごとの出力（_outputs）、falls は run ごとの落ち（workflow_failed）の時刻（ログの形。古い順）"""
        self.outputs, self.falls = outputs, falls
        self.events, self.skipped, self.children, self.missing, self.checks, self.artifacts = [], [], [], [], [], {}
        self.unread: dict[str, int] = {}
        self.current = ""
        self.seen_skips = set()

    def _ts(self, entry: dict) -> str | None:
        """行の時刻。読めない時刻は数えずに None にし、読めなかった物に数える（段の集計と無駄の手がかりを落とさない）"""
        ts = entry.get("ts")
        if ts is None or ts == "":
            return None
        if try_when(ts) is None:
            self._count("読めない時刻の行")
            return None
        return ts

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
            if not isinstance(entry, dict):
                self._count(OBJECTLESS)
                continue
            kind = entry.get("type")
            if not isinstance(kind, (str, type(None))):
                # 型の欄が字でない行は、型を引く前に数える（列や object の型は表を引く所で落ちる）
                self._count(SHAPELESS)
                continue
            if kind in UNREAD_ROWS:
                continue
            try:
                if kind not in READ_ROWS:
                    self._count(f"知らない行の型 {kind}")
                elif kind in NODE_ROWS:
                    self._node(entry, kind, prefix, by_invocation, by_attempt, by_step, root)
                elif kind == PROVIDER_ROW:
                    self._provider(entry, by_attempt)
                elif kind == EXEC_ROW:
                    self._exec(entry, prefix, by_step)
            except (AttributeError, KeyError, TypeError):
                # 欄の形が違う行（execution・event が object でない・loopPath の周が object でないなど）は、落ちずに数える
                self._count(SHAPELESS)

    def _node(self, entry, kind, prefix, by_invocation, by_attempt, by_step, root):
        # 1 行は 2 つに分けて読む。先に出来事に入れる値（周の番号・step・試みの id・会話の欄・誤りの字・費用・出力）を全部取り出して
        # 形を確かめ、全部が通った後で出来事を一度に書く。形が違えば何も書かずに行ごと数える（途中まで書き換えた出来事を残さず、
        # 後で使う段の集計と会話の読みで落ちない）
        execution = entry.get(EXECUTION) or {}
        path = execution.get("path") or entry.get("step") or ""
        invocation = (execution.get("invocation") or {})
        key = (path, plain(invocation.get("id")) or "")
        ids = [*_tokens(prefix), *_tokens([path])]
        loop = [_round(step.get("iteration")) for step in invocation.get("loopPath") or []]
        step = plain(entry.get("step")) or path
        attempt = plain((execution.get("attempt") or {}).get("id"))
        node = (execution.get("node") or {}).get("kind") or ""
        told = _told(execution) if kind in ("node_complete", "node_error") else {}
        error = (entry.get("error") or (execution.get("lifecycle") or {}).get("error") or "") if kind == "node_error" else ""
        cost = (runlog.number(entry.get(NODE_COST)) or 0.0) if own_spend(execution.get(ACCOUNTING), entry.get(AGGREGATE)) else 0.0
        # 出力（DB の node_completed）は通った起動の物で、同じ起動の id の前の落ちた出来事には付けない
        output = self.outputs.get(key[1]) if kind == "node_complete" else None
        text = mend(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)) if output is not None else None
        # 読めない時刻を数えるのも書き込みなので、読む段の最後に置く
        ts = self._ts(entry)
        if kind == "node_skipped":
            # 起き直すたびに Archon は when・trigger_rule で飛ぶノードの行も新しい起動の id で書き直すので、同じ run・道・周の飛びは最初の 1 つだけ
            spot = (self.current, tuple(ids), tuple(map(str, loop)))
            if entry.get("content") != PRIOR_SUCCESS and spot not in self.seen_skips:
                self.seen_skips.add(spot)
                self.skipped.append({"tokens": ids, "time": ts, "cause": entry.get("cause")})
            return
        event = by_invocation.get(key)
        # 落ちた後に起き直すと、Archon は終わっていない（落ちた物を含む）ノードに前の起動の id を使い直す（dag-resume-snapshot.ts の
        # unfinishedInvocations）。落ちた出来事の走り直しは新しい出来事にし、一度落ちたことを印 fell に持つ
        again = kind == "node_start" and event is not None and self._fallen(event, ts)
        if event is None or again:
            event = {"tokens": ids, "path": path, "run": self.current, "artifacts": str(root / ARTIFACTS / RUNS_DIR / self.current) if root else "",
                     "kind": node, "start": ts, "last_start": ts,
                     "end": None, "status": "running", "loop": loop,
                     "cost": 0.0, "calls": [], "exec": [], "error": ""}
            if again:
                event["fell"] = True
            by_invocation[key] = event
            self.events.append(event)
        by_step[step] = event
        if attempt:
            by_attempt[attempt] = event
        if kind == "node_start":
            # 繰り返しの器は答えの後も同じ起動の id で node_start を書き直す（待ちから走り中へ戻る。同じ出来事）。閉じる時刻は
            # 最後の始め（last_start）の後の物から選ぶ
            if event["status"] == "waiting":
                event["status"] = "running"
            if ts:
                event["last_start"] = ts
            return
        if kind == "node_suspended":
            event["status"] = "waiting"
            return
        event["end"] = ts
        event["status"] = "ok" if kind == "node_complete" else "failed"
        if kind == "node_error":
            event["error"] = error
        event["cost"] += cost
        event.update(told)
        if text is not None:
            event["output"], event["digest"] = _clip(text), hashlib.sha1(text.encode("utf-8")).hexdigest()
            self._artifacts(output, root)

    def _fallen(self, event: dict, ts: str | None) -> bool:
        """同じ起動の id で始め直す前に、その出来事が落ちていたか: node_error で落ちたか、前の始めの後・今の始めの前に run が落ちた
        （SIGTERM で落とす道〔owned-run-termination.ts の failWorkflowRun〕はログに node_error を書かず DB に落ちだけを書く）。
        後の方は、走り中・待ちのまま止まった出来事をその落ちで閉じて印 cut を付け、走り中の物を落ちにする（run の終わりで閉じる時と同じ形）。
        落ちから起き直しまでを長さに入れず、費用・トークン・往復・会話・誤りの字を起動ごとに持つため"""
        if event["status"] == FAILED:
            return True
        begun = event["last_start"]
        if event["status"] not in ("running", "waiting") or not begun or not ts:
            return False
        at = next((t for t in _since(begun, self.falls.get(self.current, [])) if when(t) < when(ts)), None)
        if at is None:
            return False
        event["end"], event["cut"] = _later(at, begun), True
        if event["status"] == "running":
            event["status"] = FAILED
        return True

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
                                   "status": ""})
        elif kind == TOOL_UPDATE:
            call = next((c for c in event["calls"] if c["id"] == got.get("toolCallId")), None)
            if call is not None:
                call["status"] = got.get("status") or ""
        else:
            event["calls"].append({"id": None, "name": kind, "title": _clip(_text(got.get("message") or got.get("description") or got), 400),
                                   "status": got.get("status") or ""})

    def _exec(self, entry, prefix, by_step):
        """script・bash のノードの出力の終わりは、同じ step の最後の起動に付ける。ノードに当たらない物（loop_group の until_bash の
        確かめ。step は `<輪>{ITERATION_MARK}<n>`）は run の確かめの行にする。行は書いた run の id を持つ（同じノードから起こした子の
        run どうしは node も step も同じになる）"""
        step = plain(entry.get("step")) or ""
        label, out, err = entry.get(runlog.EXEC_LABEL) or "", _clip(entry.get("stdout_tail") or "", 4000), _clip(entry.get("stderr_tail") or "", 4000)
        event = by_step.get(step)
        # 読めない時刻を数えるのも書き込みなので、確かめの最後に置く（_node と同じ）
        row = {"step": step, "node": prefix, "run": self.current, "label": label, "exit": entry.get(runlog.EXIT_CODE),
               "stdout": out, "stderr": err, "at": self._ts(entry)}
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
                    if key not in self.artifacts:
                        self._artifact(key, root / ARTIFACTS / RUNS_DIR, str(item.get("run_id") or ""), str(item["path"]))
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    def _artifact(self, key: str, runs: Path, run_id: str, name: str) -> None:
        """run の置き場（`runs/<run_id>/`）の下の小さなファイルの中身。絶対パス・`..`・symlink で置き場の外を指す物は読まずに数える
        （見る道具は run の記録だけを読む。viewer/AGENTS.md の E25 の 2）"""
        place = runs / run_id
        path = place / name
        if "\0" in run_id or "\0" in name:
            # NUL の字はパスにできず、実のパスの引きが ValueError で落ちる
            self._count(NUL_PATH)
        elif Path(os.path.realpath(place)).parent != Path(os.path.realpath(runs)) or not _within(path, place):
            self._count(OUTSIDE)
        elif path.is_file() and path.stat().st_size <= ARTIFACT_LIMIT:
            self.artifacts[key] = mend(path.read_text(encoding="utf-8", errors="replace"))

    def _count(self, what: str) -> None:
        self.unread[what] = self.unread.get(what, 0) + 1


def _told(execution: dict) -> dict:
    """終わりの行の会話の欄（会話の id の頭・続けたか・模型・トークン・往復の数）。会話の id の頭が無ければ空"""
    spend, binding = execution.get("spend") or {}, execution.get("binding") or {}
    preview = plain(binding.get("sessionPreview"))
    if not preview:
        return {}
    model = binding.get("model") or {}
    return {"session": preview, "origin": binding.get("sessionOrigin") or "",
            "model": (model.get("resolved") or {}).get("value") or model.get("requested") or "",
            "usage": runlog.tokens(runlog.measurement(spend, "tokens", lambda v: v)[0]), "turns": runlog.measurement(spend, "numTurns")[0]}


def plain(value):
    """字か None の値（id・step・会話の id の頭・道具の名）。ほかの形は TypeError で、読む側が欄の形が違う行に数える（dict の鍵や
    集合に入れる所で落ちない）"""
    if value is None or isinstance(value, str):
        return value
    raise TypeError(f"字でない値 {value!r}")


def _round(value) -> int:
    """周の番号（Archon の loopPath の iteration は整数。schemas/node-execution.ts）。ほかの形は TypeError"""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TypeError(f"整数でない周の番号 {value!r}")


def _within(path: Path, base: Path) -> bool:
    """path の実のパスが base の実のパスの下か（symlink も辿る）"""
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(base))


def mend(text: str) -> str:
    """片割れのサロゲート（JSON の `\\ud83d` だけの字）を置き換えた字。UTF-8 に書けず、hash もページも落ちる。会話の字（flowview の keep）と
    ページの全体も通す"""
    return LONE.sub(REPLACEMENT, text)


def _tokens(paths: list[str]) -> list[str]:
    return [t for path in paths for t in shape.tokens(path)]


def _row(con, run_id: str) -> dict | None:
    row = con.execute(f"select {', '.join(RUN_COLUMNS)} from {RUN_TABLE} where id = ?", (run_id,)).fetchone()
    return dict(zip(RUN_COLUMNS, row)) if row else None


def _outputs(con) -> tuple[dict, int]:
    """ノードの起動（invocation の id）ごとの出力の全文（DB の node_completed）と、欄の形が違う行（invocation が object でない・
    id が字でない）の数"""
    out, odd = {}, 0
    for (data,) in con.execute(f"select data from {EVENT_TABLE} where event_type = ?", (OUTPUT_EVENT,)):
        got = _json(data)
        invocation = got.get("invocation") or {}
        ident = invocation.get("id") if isinstance(invocation, dict) else None
        if not isinstance(invocation, dict) or not isinstance(ident, (str, type(None))):
            odd += 1
        elif ident and got.get(NODE_OUTPUT) is not None:
            out[ident] = got[NODE_OUTPUT]
    return out, odd


def _waiting(con) -> dict:
    """答えを待つ run（状態が paused）ごとの、止まって答えを待つノード（node_suspended の後に同じノードの終わりが無い物）。
    答えが入って次へ進む前のノード（metadata の待ちに答えが在る物）は外す。繰り返しの中の待ちでは Archon が本体のノード
    `<器>.<本体>` と器の両方に node_suspended を書くので、待つ本体を持つ器は並べず、答えが入れば器も外す"""
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
            steps = [wait.get("nodeId")]
            if wait.get("owner") == WAIT_LOOP_OWNER:
                steps.append(f"{wait.get('nodeId')}{shape.IN_LOOP}{wait.get('bodyWaitId')}")
            out[rid] = [name for name in out.get(rid, []) if name not in steps]
    out = {rid: [name for name in names if not any(other.startswith(name + shape.IN_LOOP) for other in names)] for rid, names in out.items()}
    return {rid: names for rid, names in out.items() if names}


def _span(events: list[dict]) -> tuple[str, str] | None:
    """出来事の最初の始めと最後の終わり（終わりの無い出来事は始め）。読めない時刻は数えない。読める時刻が無ければ None"""
    times = [(at, t) for e in events for t in (e["start"], e["end"]) if t and (at := try_when(t))]
    return (min(times)[1], max(times)[1]) if times else None


def _child_span(child: dict, events: list[dict], parents: dict, end: str | None) -> tuple[str, float | None]:
    """子の run の始めとかかった秒。その子と孫の出来事から出し、出来事が無ければ run の行の値。終わった子の run の終わりは end
    （最後の終わりの出来事）。行の終わりの欄は外す"""
    def under(rid):
        while rid in parents:
            if rid == child["id"]:
                return True
            rid = parents[rid]
        return False
    completed = child.pop("completed")
    started, ended = _span([e for e in events if under(e["run"])]) or (child["started"], completed)
    return started, seconds(started, _later(end, ended))


def _error(data: str) -> str:
    text = _json(data).get("error") or ""
    return text.splitlines()[0][:300] if isinstance(text, str) and text else ""


def seconds(started, completed) -> float | None:
    """始めから終わりまでの秒（0.1 秒に丸める）。どちらかが空か読めなければ None。段の集計と無駄の手がかりも使う"""
    first, last = try_when(started), try_when(completed)
    return round((last - first).total_seconds(), 1) if first and last else None


def length(event: dict) -> float:
    """出来事の長さの秒。終わりの無い出来事と読めない時刻は 0"""
    return seconds(event["start"], event["end"]) or 0.0


def when(text: str) -> datetime:
    """時刻の読み。ログの時刻（末尾 Z）と DB の秒までの時刻（datetime('now') の UTC で、時差を持たない）を同じ UTC で読む"""
    got = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def try_when(text) -> datetime | None:
    if not isinstance(text, str) or not text:
        return None
    try:
        return when(text)
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
