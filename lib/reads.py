"""読んだ証拠（役が、機械が渡したパスを本当に読んだかの記録）の置き場の決め方・名の決まり・集め方の 1 か所。
今の works の works/.shared/core/reads.py から、盤面と実行基盤の出来事の読みを外して持ってきた（持ち主の決め lib-port-as-is）。

出どころは隔離した設定の PostToolUse のフック bin/_lib/record-read.py の記録だけ。Read の行は今の works と同じ形
{ts, session_id, agent_id, path, file_sha, bytes, partial, partial_why, tool_use_id}、Agent・WebFetch・WebSearch の行は path を
持たない形 {ts, session_id, agent_id, tool_use_id, tool_name, input}（input は subagent_type・url・query の 1 つ）。
今の works が使った実行基盤の出来事（tool_called）は、今の実行基盤がもう書かないので読まない。記録は作業の場（cwd）ごとの
ファイル 1 つに混ざるので、役ごとの行は差し込みの始まりの時刻 since から後の行で切る（どちらのブロックも道具を持つ役は 1 つ）。
受け付けの条件にはしない（欠けは報告が出す）。

フックが import するので、頭は標準ライブラリだけを読む（記録の状態を測る hook_evidence は collect の中で読む）。
- ROOT・LOG・root(config_dir)・reads_path(root, cwd)・log_here(): 記録の根（Claude の設定の置き場の下）と、作業の場ごとの記録のファイル
- EVIDENCE_GLOB・evidence_name(role)・index_name(owner)・is_index(name): 置き場の読んだ証拠と索引の名
- stamp()・records(log, since): 記録の時刻の形と、since から後の行（読めなければ None と訳）
- tool_count・tool_inputs・web_fetches・web_searches: 記録の行の道具の呼びの数と入力
- collect(place, role, must_read, log, *, since, repo, prefix): 役ごとの reads-<頭><役>.json を書く
"""
import hashlib
import json
import os
import pathlib
import sys
import time

ROOT = "works-reads"
LOG = "reads.jsonl"            # engine.util.hook_evidence が置き場の下に読む名（record-read.py が書く名）
KEY_LEN = 16                   # cwd の実パスの sha256 の頭の字数（置き場のフォルダの名。lib/writelog.py と同じ決め方）
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"   # 記録の行の ts（地方時。秒で切る）
EVIDENCE_GLOB = "reads-*.json"
_INDEX_SUFFIX = "-block.json"
HOOK_SEEN = ("read", "stale", "partial")   # フックで「読んだ跡が在る」状態（missing に数えない）
NOT_LAUNCHED = "役を起こしていない"
NO_ROOT = "記録の根が無い（Claude の設定の置き場が渡っていない起動）"
WEB_INPUTS = {"Agent": "subagent_type", "WebFetch": "url", "WebSearch": "query"}   # 道具 → 記録に残す入力の欄


def root(config_dir) -> pathlib.Path:
    return pathlib.Path(config_dir) / ROOT


def reads_path(root, cwd) -> pathlib.Path:
    key = hashlib.sha256(os.path.realpath(str(cwd)).encode("utf-8", "surrogateescape")).hexdigest()[:KEY_LEN]
    return pathlib.Path(root) / key / LOG


def evidence_name(role: str) -> str:
    """役 role の読んだ証拠のファイルの名（collect が書く）"""
    return f"reads-{role}.json"


def index_name(owner: str) -> str:
    """読んだ証拠を集めた側 owner が書く索引の名（{役: 役ごとの証拠のパス}。役ごとの証拠と別の名）"""
    return f"reads-{owner}{_INDEX_SUFFIX}"


def is_index(name: str) -> bool:
    return name.endswith(_INDEX_SUFFIX)


def stamp(at: float | None = None) -> str:
    """時刻 at（無ければ今）を記録の ts と同じ形に"""
    return time.strftime(TS_FORMAT, time.localtime(at))


def log_here() -> pathlib.Path | None:
    """このプロセスの Claude の設定の置き場（起動の殻が隔離した CLAUDE_CONFIG_DIR。役の会話もフックも同じ値で起きる）の下の、
    この作業の場（cwd）の記録のファイル。置き場か根が無ければ None。置き場の決まりはここの 1 か所に持つ"""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config or not root(config).is_dir():
        return None
    return reads_path(root(config), pathlib.Path.cwd())


def records(log, since: str) -> tuple:
    """(記録の行のうち ts が since 以後の物, 読めない訳)。log が None（記録の根が無い）か記録のファイルが無ければ ([], 無い訳)・
    読めなければ (None, 訳)"""
    if log is None:
        return [], NO_ROOT
    log = pathlib.Path(log)
    if not log.exists():
        return [], f"{log} が無い（記録の根の無い起動か、役が道具を呼んでいない）"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return None, f"{log} を読めない（{e}）"
    rows = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("ts"), str) and r["ts"] >= since:
            rows.append(r)
    return rows, ""


def tool_inputs(rows, tool: str) -> list:
    """記録の行のうち道具 tool の呼びの入力（記録の順）"""
    return [r.get("input") for r in rows or [] if r.get("tool_name") == tool]


def tool_count(rows, tool: str) -> int:
    return len(tool_inputs(rows, tool))


def _distinct(values) -> list:
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v.strip()))


def web_fetches(rows) -> list:
    """WebFetch で取得した URL（記録の順で重ねない）"""
    return _distinct(tool_inputs(rows, "WebFetch"))


def web_searches(rows) -> list:
    """WebSearch で引いた問い（記録の順で重ねない）"""
    return _distinct(tool_inputs(rows, "WebSearch"))


def _write_json(path: pathlib.Path, doc) -> pathlib.Path:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def collect(place, role: str, must_read: list, log, *, since: str, repo, prefix: str = "") -> dict:
    """機械が役 role に渡したパス must_read の 1 つずつについて、記録の行のうち since から後の物でフックの状態（hook_evidence の
    read・stale・partial・absent・none）を測り、place の reads-<prefix><role>.json に {role, since, rows: [{path, hook}], sources,
    missing, web} を書き、{ok: True, sources, missing, reads_file} を返す（受け付けの条件にしない）。
    - sources.hook: 記録が在れば "recorded"、無ければ "none"、読めなければ "unreadable"（どちらも訳 sources.why。読めない記録を
      読んでいないと取り違えない。その時 missing は空、各行の hook は null）
    - web: since から後の WebFetch の URL と WebSearch の問い {fetches, searches}（読めない記録なら null）
    - 相対のパスは repo に解決して測る。行の path は渡された綴りのまま"""
    repo = pathlib.Path(repo)
    got, why = records(log, since)
    must = list(dict.fromkeys(m for m in must_read if isinstance(m, str) and m))
    if got is None or log is None or not pathlib.Path(log).exists():
        sources = {"hook": "unreadable" if got is None else "none", "why": why}
        rows = [{"path": p, "hook": None} for p in must]
        missing, web = [], None if got is None else {"fetches": [], "searches": []}
    else:
        graphloops = str(pathlib.Path(__file__).resolve().parent / "graphloops")
        if graphloops not in sys.path:
            sys.path.insert(0, graphloops)
        from engine.util import hook_evidence
        index = {}
        for r in got:
            if isinstance(r.get("path"), str):
                index.setdefault(r["path"], []).append(r)
        cache = {"index": index, "n": len(got)}
        sources = {"hook": "recorded", "why": ""}
        rows, missing = [], []
        for p in must:
            hook = hook_evidence(pathlib.Path(log).parent, p if os.path.isabs(p) else str(repo / p), cache=cache)[0]
            rows.append({"path": p, "hook": hook})
            if hook not in HOOK_SEEN:
                missing.append(p)
        web = {"fetches": web_fetches(got), "searches": web_searches(got)}
    out = _write_json(pathlib.Path(place) / evidence_name(prefix + role),
                      {"role": prefix + role, "since": since, "rows": rows, "sources": sources, "missing": missing, "web": web})
    return {"ok": True, "sources": sources, "missing": missing, "reads_file": str(out)}
