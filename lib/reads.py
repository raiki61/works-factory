"""読んだ証拠（役が、機械が渡したパスを本当に読んだかの記録）の置き場の決め方・名の決まり・集め方の 1 か所。
今の works の works/.shared/core/reads.py から、盤面と実行基盤の出来事の読みを外して持ってきた（持ち主の決め lib-port-as-is）。

出どころは隔離した設定の PostToolUse のフック bin/_lib/record-read.py の記録だけ。Read の行は今の works と同じ形
{ts, session_id, agent_id, path, file_sha, bytes, partial, partial_why, tool_use_id}、Agent・WebFetch・WebSearch の行は path を
持たない形 {ts, session_id, agent_id, tool_use_id, tool_name, input}（input は subagent_type・url・query の 1 つ）。
今の works が使った実行基盤の出来事（tool_called）は、今の実行基盤がもう書かないので読まない。記録は作業の場（cwd）ごとの
ファイル 1 つに混ざり、同じ作業の場で別のブロックの役（線の判定のやり直しなど）が並んで走りうる。だから役ごとの行は、差し込みの
始まりの時刻 since から後の行のうち、その役だけに渡した材料 own を読んだ session の行で切る（今の works は節ごとに切った。subagent の
行は親の session_id を持つ）。
受け付けの条件にはしない（欠けは報告が出す）。

フックが import するので、頭は標準ライブラリだけを読む（記録の状態を測る hook_evidence は collect の中で読む）。
- ROOT・LOG・root(config_dir)・reads_path(root, cwd)・open_log(root, cwd)・log_here(): 記録の根（Claude の設定の置き場の下）と、作業の場
  ごとの記録のファイル（置き場の鍵・作業の場の控え・片付けは lib/writelog と同じ物）
- EVIDENCE_GLOB・REPLAN・role_key(role, replan)・evidence_name(role)・index_name(owner, replan)・is_index(name): 置き場の読んだ証拠と索引の名
- INDEX_WHY・index_why(path): 索引の訳の鍵と、それを読む 1 か所
- stamp()・records(log, since): 記録の時刻の形と、since から後の行（読めなければ None と訳。記録が無い訳は NO_CONFIG・NO_ROOT・ファイルが無いを分ける）
- tool_count・tool_inputs・web_fetches・web_searches: 記録の行の道具の呼びの数と入力
- collect(place, role, must_read, log, *, own, since, repo, replan): 役ごとの reads-<役>.json（案の直しは reads-replan-<役>.json）を書く
- guarded(collect, owner, place, replan, unread)・failure_name(owner, at): 集めるノードの中の誤りを、sources.hook が FAILED の
  reads-*.json にして残す（名は role_key。差し込みの往復と形が読めなければ UNREAD_PASS）
- read_evidence(path): collect・guarded が書いた reads-*.json を読む（読む側の 1 か所）
"""
import json
import os
import pathlib
import sys
import time

_HERE = str(pathlib.Path(__file__).resolve().parent)
if _HERE not in sys.path:   # 殻（bin/_lib/launcher.py）は from lib import reads で読み、置き場を sys.path に持たない
    sys.path.append(_HERE)
import oneline  # noqa: E402
import writelog  # noqa: E402

ROOT = "works-reads"
LOG = "reads.jsonl"            # engine.util.hook_evidence が置き場の下に読む名（record-read.py が書く名）
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"   # 記録の行の ts（地方時。秒で切る）
EVIDENCE_GLOB = "reads-*.json"
_INDEX_SUFFIX = "-block.json"
REPLAN = "replan"              # 案の直しの差し込みの役の名の頭と索引の持ち主（1 回目の物を上書きしない。元 replan.READS_PREFIX・READS_INDEX）
RECORDED = "recorded"           # sources.hook: フックの記録が在る
FAILED = "failed"               # sources.hook: 読んだ証拠を集めるノードの中で誤りが起き、測れなかった（guarded が書く）
HOOK_SEEN = ("read", "stale", "partial")   # フックで「読んだ跡が在る」状態（missing に数えない）
NOT_LAUNCHED = "役を起こしていない"
INDEX_WHY = "why"              # 索引の中の訳の鍵（役を起こしていない段など。役の名と並ぶ。index_why が読む）
NO_CONFIG = "Claude の設定の置き場が渡っていない起動（CLAUDE_CONFIG_DIR が無い）"
NO_ROOT = "記録の根が無い（読んだ証拠のフックを置いていない起動）"
SHAPE_WRONG = "読んだ証拠の形が違う"
UNREAD_PASS = "往復の番号と形が読めない（推し量らず、置き場の根に役の素の名で書いた）"   # guarded の unread の訳の頭
WEB_INPUTS = {"Agent": "subagent_type", "WebFetch": "url", "WebSearch": "query"}   # 道具 → 記録に残す入力の欄


def root(config_dir) -> pathlib.Path:
    return pathlib.Path(config_dir) / ROOT


def reads_path(root, cwd) -> pathlib.Path:
    return writelog.log_path(root, cwd, LOG)


def open_log(root, cwd) -> pathlib.Path:
    """reads_path の置き場を作り、作業の場の実パスを控えて（writelog.sweep が片付ける）記録のファイルを返す"""
    return writelog.open_log(root, cwd, LOG)


def role_key(role: str, replan: bool = False) -> str:
    """読んだ証拠と索引の中での役 role の名（案の直しの差し込みは頭に REPLAN）"""
    return f"{REPLAN}-{role}" if replan else role


def evidence_name(role: str) -> str:
    """役 role の読んだ証拠のファイルの名（collect が書く）"""
    return f"reads-{role}.json"


def index_name(owner: str, replan: bool = False) -> str:
    """読んだ証拠を集めた側 owner が書く索引の名（{役: 役ごとの証拠のパス}。役ごとの証拠と別の名。案の直しの差し込みは持ち主を REPLAN に）"""
    return f"reads-{REPLAN if replan else owner}{_INDEX_SUFFIX}"


def index_why(path) -> str:
    """索引 path の訳（INDEX_WHY）。読めない・訳が無ければ """""
    try:
        why = json.loads(pathlib.Path(path).read_text(encoding="utf-8")).get(INDEX_WHY)
    except (OSError, ValueError, AttributeError):
        return ""
    return why if isinstance(why, str) else ""


def is_index(name: str) -> bool:
    return name.endswith(_INDEX_SUFFIX)


def stamp(at: float | None = None) -> str:
    """時刻 at（無ければ今）を記録の ts と同じ形に"""
    return time.strftime(TS_FORMAT, time.localtime(at))


def log_here() -> pathlib.Path | None:
    """このプロセスの Claude の設定の置き場（起動の殻が隔離した CLAUDE_CONFIG_DIR。役の会話もフックも同じ値で起きる）の下の、
    この作業の場（cwd）の記録のファイル。置き場が渡っていなければ None。置き場の決まりはここの 1 か所に持つ"""
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if not config:
        return None
    return reads_path(root(config), pathlib.Path.cwd())


def records(log, since: str) -> tuple:
    """(記録の行のうち ts が since 以後の物, 読めない訳)。記録が無ければ ([], 無い訳)・読めなければ (None, 訳)。無い訳は、log が
    None（設定の置き場が渡っていない）なら NO_CONFIG、記録の根（reads_path の根）が無ければ NO_ROOT、根は在って記録のファイルが無ければ
    そのパス"""
    if log is None:
        return [], NO_CONFIG
    log = pathlib.Path(log)
    if not log.exists():
        if not log.parent.parent.is_dir():
            return [], NO_ROOT
        return [], f"{log} が無い（役が道具を呼んでいない）"
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


def _real(p: str, repo: pathlib.Path) -> str:
    return os.path.realpath(p if os.path.isabs(p) else str(repo / p))


def collect(place, role: str, must_read: list, log, *, own: list, since: str, repo, replan: bool = False) -> dict:
    """機械が役 role に渡したパス must_read の 1 つずつについて、記録の行のうち since から後で、役 role だけに渡した材料 own（must_read の
    うちほかの役が読まない物）を読んだ session の物でフックの状態（hook_evidence の read・stale・partial・absent・none）を測り、place の reads-<role_key(role, replan)>.json に {role, since, rows: [{path, hook}],
    sources, missing, web} を書き、{ok: True, sources, missing, reads_file, records} を返す（受け付けの条件にしない。records は
    役の session の行で、読めなければ None）。
    - sources.hook: 記録が在れば "recorded"、無ければ "none"、読めなければ "unreadable"（どちらも訳 sources.why。読めない記録を
      読んでいないと取り違えない。その時 missing は空、各行の hook は null）
    - web: 役の session の WebFetch の URL と WebSearch の問い {fetches, searches}（読めない記録なら null）
    - 相対のパスは repo に解決して測る。行の path は渡された綴りのまま"""
    repo = pathlib.Path(repo)
    got, why = records(log, since)
    must = list(dict.fromkeys(m for m in must_read if isinstance(m, str) and m))
    if why:
        sources = {"hook": "unreadable" if got is None else "none", "why": why}
        rows = [{"path": p, "hook": None} for p in must]
        missing, web = [], None if got is None else {"fetches": [], "searches": []}
    else:
        graphloops = str(pathlib.Path(__file__).resolve().parent / "graphloops")
        if graphloops not in sys.path:
            sys.path.insert(0, graphloops)
        from engine.util import hook_evidence
        mine = {_real(p, repo) for p in own}
        sessions = {r.get("session_id") for r in got if r.get("path") in mine}
        got = [r for r in got if r.get("session_id") in sessions]
        index = {}
        for r in got:
            if isinstance(r.get("path"), str):
                index.setdefault(r["path"], []).append(r)
        cache = {"index": index, "n": len(got)}
        sources = {"hook": RECORDED, "why": ""}
        rows, missing = [], []
        for p in must:
            hook = hook_evidence(pathlib.Path(log).parent, _real(p, repo), cache=cache)[0]
            rows.append({"path": p, "hook": hook})
            if hook not in HOOK_SEEN:
                missing.append(p)
        web = {"fetches": web_fetches(got), "searches": web_searches(got)}
    name = role_key(role, replan)
    out = _write_json(pathlib.Path(place) / evidence_name(name),
                      {"role": name, "since": since, "rows": rows, "sources": sources, "missing": missing, "web": web})
    return {"ok": True, "sources": sources, "missing": missing, "reads_file": str(out), "records": got}


def failure_name(owner: str, at: float | None = None) -> str:
    """集める側 owner のノードが落ちた記録のファイルの名。役ごとの証拠を上書きせず、同じ置き場に 2 度差し込まれるノード（事前審査と
    案の直しの事前審査）の物も時刻（at。無ければ今）で分ける"""
    return f"{evidence_name(owner).removesuffix('.json')}-failed-{time.strftime('%Y%m%d-%H%M%S', time.localtime(at))}.json"


def guarded(collect, *, owner: str, place, replan: bool = False, unread: str = "") -> dict:
    """読んだ証拠を集めるノードの返り: collect()（{ok, missing, index_file}）に reason "" を足す。collect が誤りを上げたら、place に
    sources.hook が FAILED で訳つきの読んだ証拠（名は role_key(owner, replan) の failure_name）を書き、{ok: False, missing: [],
    index_file: "", reason} を返す。ノードの返りは誰も読まないので、報告が「役を起こしていない」と取り違えないよう置き場に残す。
    呼び手が差し込みの往復と形を読めず place と replan を決められなかった時は、その訳 unread を UNREAD_PASS と並べて訳に添える"""
    try:
        return {**collect(), "reason": ""}
    except Exception as e:  # noqa: BLE001  読んだ証拠は受け付けの条件でない（ノードを落とさない）
        reason = f"{type(e).__name__}: {oneline.one_line(e)}"
    p = pathlib.Path(place)
    p.mkdir(parents=True, exist_ok=True)
    name = role_key(owner, replan)
    why = f"{reason}（{UNREAD_PASS}: {oneline.one_line(unread)}）" if unread else reason
    _write_json(p / failure_name(name), {"role": name, "since": stamp(), "rows": [], "sources": {"hook": FAILED, "why": why},
                                         "missing": [], "web": None})
    return {"ok": False, "missing": [], "index_file": "", "reason": reason}


def read_evidence(path) -> tuple:
    """collect が書いた読んだ証拠のファイルを読み、(中身, "") を返す。中身は role（文字列）・rows・missing（並び）・sources（dict）の
    型を確かめた dict。読めなければ (None, 誤りの型と文)、形が違えば (None, SHAPE_WRONG)"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{type(e).__name__}: {oneline.one_line(e)}"
    if not (isinstance(doc, dict) and isinstance(doc.get("role"), str) and isinstance(doc.get("rows"), list)
            and isinstance(doc.get("missing"), list) and isinstance(doc.get("sources"), dict)):
        return None, SHAPE_WRONG
    return doc, ""
