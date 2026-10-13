"""GitHub ReviewBench（PR の審査の公開ベンチ）の口。ランナー run.py が使う（試験のモジュールではない。test_*.py に当たらない）。

課題を manifest から選び、試みのフォルダ（target は head を取り出し base が辿れる写し）を組み、PR の題と本文を依頼にし、作り手の
出力を判定役の入力（docs/JUDGING_INPUT.md の形）に変える。指摘の場所は出力の字の <パス>:<行> を head の版で照らし、照らせない物は
捨てて数を残す。標準ライブラリだけ。期限を置かない（持ち主の決め no-timeouts）。手順と形は ReviewBench の commit c17b05b の
scripts/try-agent.sh・AGENT_CONTRACT.md・docs/JUDGING_INPUT.md・docs/OFFLINE_EVAL.md・scripts/eval/eval.ts で確かめた。
"""
import json
import os
import re
import subprocess
from collections import namedtuple
from pathlib import Path

from tests.e2e import make_target

MIRROR = "https://github.com/review-bench/{name}.git"
CONTRACT_SECONDS = 1800   # AGENT_CONTRACT.md の Limits の 1 件の秒。超えた事実を控えに残すだけで、run は止めない
REF = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+):(\d+)(?:[-–](\d+))?")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
NO_REF, NOT_AT_HEAD = "番地が無い", "head に無い番地"
NO_NODE = "どのノードの出力にも所見の字が無い"
# 判定役の status → ノードの表の数の欄
VERDICTS = {"matched_tp": "hit", "novel_tp": "real", "matched_fp": "wrong", "novel_fp": "wrong"}
GIT_ENV = {"GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}
# 作り手の出力の 1 つの出どころ: evidence/ からのファイル・候補の行への道（"*" は並びを開く）・形（units は判定の単位、items は
# where と text の欄を持つ所見、findings は AGENT_CONTRACT の指摘）・items の字の欄
Source = namedtuple("Source", "file rows kind text", defaults=(None,))


class BenchError(Exception):
    pass


def name(entry: dict) -> str:
    return entry["nwo"].replace("/", "_")


def key(entry: dict) -> str:
    """scripts/lib/types.ts の prKey と同じ鍵"""
    return f"{name(entry)}_{entry['pr_number']}-{entry['head'][:8]}"


def tasks(bench: Path, language: str = "Python") -> list[dict]:
    path = Path(bench) / "corpus" / "manifest.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BenchError(f"ReviewBench の manifest（{path}）を読めない: {type(e).__name__}") from None
    if not isinstance(rows, list):
        raise BenchError(f"ReviewBench の manifest（{path}）が並びでない")
    return [r for r in rows if isinstance(r, dict) and r.get("language") == language]


def request_rows(entry: dict, changed: list[str]) -> list[dict]:
    """依頼の 1 行。where を変わったファイルにするのは、工場が where の字に含まれるパスで範囲を読むため（lib/checkscope.py）"""
    body = (entry.get("body") or "").replace("\r\n", "\n").strip()
    title = entry["title"].strip()
    return [{"where": " ".join(sorted(changed)), "text": f"{title}\n\n{body}" if body else title}]


def git(*args: str) -> str:
    done = subprocess.run(["git", *make_target.GIT_ID, *args], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, **GIT_ENV}, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise BenchError(f"git {' '.join(args)} が落ちた: {' '.join(done.stderr.split())[:300]}")
    return done.stdout


def _has(repo: Path, *shas: str) -> bool:
    return all(subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True,
                              env={**os.environ, **GIT_ENV, "GIT_NO_LAZY_FETCH": "1"}).returncode == 0 for sha in shas)


def prepare(entry: dict, attempt: Path, cache: Path, mirror: str = MIRROR) -> dict:
    """試みのフォルダを組み、{"base", "head"} を返す。target の main は head、refs/bench/base が base。origin（bare）にも同じ物を
    置く。写しは mirror から blob ごと取る（run の中で網へ blob を取りに行く道を作らない）"""
    base, head = entry["base"], entry["head"]
    repo = Path(cache) / name(entry)
    if not repo.is_dir():
        git("init", "-q", "--bare", str(repo))
    if not _has(repo, base, head):
        git("-C", str(repo), "fetch", "-q", mirror.format(name=name(entry)), f"{base}:refs/bench/{base}",
            f"{head}:refs/bench/{head}")
    made = make_target.layout(attempt)
    attempt.mkdir(parents=True)
    git("init", "-q", "--bare", "-b", "main", str(made["origin"]))
    target = str(made["target"])
    git("init", "-q", "-b", "main", target)
    git("-C", target, "fetch", "-q", "--update-head-ok", str(repo), f"refs/bench/{base}:refs/bench/base", f"refs/bench/{head}:refs/heads/main")
    git("-C", target, "reset", "-q", "--hard", "main")
    git("-C", target, "remote", "add", "origin", str(made["origin"]))
    git("-C", target, "push", "-q", "-u", "origin", "main", "refs/bench/base:refs/bench/base")
    git("-C", target, "remote", "set-head", "origin", "main")
    pr = attempt / "pr"
    pr.mkdir()
    (pr / "diff.patch").write_text(git("-C", target, "diff", f"{base}...{head}"), encoding="utf-8")
    shown = {k: entry.get(k) for k in ("repo", "pr_number", "base", "head", "nwo", "title", "body")}
    (pr / "pr.json").write_text(json.dumps({**shown, "pr_number": int(entry["pr_number"])}, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
    changed = git("-C", target, "diff", "--name-only", f"{base}...{head}").splitlines()
    made["request"].write_text(json.dumps(request_rows(entry, changed), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    made["home"].mkdir()
    return {"base": base, "head": head}


# ---------------------------------------------------------------- 指摘の一覧
def refs(text: str) -> list[tuple[str, int, int]]:
    out = []
    for path, start, end in REF.findall(text or ""):
        path = path[2:] if path.startswith("./") else path
        out.append((path, int(start), int(end or start)))
    return out


class HeadTree:
    """head の版のファイルの行数（パスごとに 1 回だけ読む）"""

    def __init__(self, target: Path, head: str):
        self.target, self.head, self.seen = Path(target), head, {}

    def lines(self, path: str) -> int | None:
        if path not in self.seen:
            done = subprocess.run(["git", "-C", str(self.target), "cat-file", "-p", f"{self.head}:{path}"],
                                  capture_output=True, stdin=subprocess.DEVNULL)
            self.seen[path] = len(done.stdout.splitlines()) if done.returncode == 0 else None
        return self.seen[path]

    def place(self, found: list[tuple[str, int, int]]) -> tuple[str, int, int] | None:
        for path, start, end in found:
            n = self.lines(path)
            if n is not None and 1 <= start <= end <= n:
                return path, start, end
        return None


def final_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """差分の hunk の左（head の版）の行の範囲。行を足すだけの hunk（数 0）は前の行の 1 行にする"""
    out, path = {}, None
    for line in diff_text.splitlines():
        if line.startswith("--- "):
            left = line[4:].split("\t")[0]
            path = left[2:] if left.startswith("a/") else None
        elif path and (m := HUNK.match(line)):
            a, b = int(m[1]), int(m[2]) if m[2] is not None else 1
            out.setdefault(path, []).append((a, a + b - 1) if b else (max(a, 1), max(a, 1)))
    return out


def _walk(doc, path: tuple) -> list:
    rows = [doc]
    for step in path:
        if step == "*":
            rows = [x for r in rows if isinstance(r, list) for x in r]
        else:
            rows = [r.get(step) for r in rows if isinstance(r, dict)]
    return [x for r in rows if isinstance(r, list) for x in r if isinstance(x, dict)]


def candidates(source, doc) -> list[dict]:
    """出どころの 1 つの文書から候補 {source, message, texts, ident[, loc]} の並び"""
    out = []
    for row in _walk(doc, source.rows):
        if source.kind == "units":
            k, reason = str(row.get("key") or ""), str(row.get("reason") or "")
            out.append({"source": source.file, "message": f"[{row.get('label')}] {k}\n{reason}", "texts": [reason, k], "ident": k})
        elif source.kind == "items":
            said = str(row.get(source.text) or "")
            message = said + (f"\n{row['mechanism']}" if row.get("mechanism") else "")
            out.append({"source": source.file, "message": message, "texts": [str(row.get("where") or ""), said], "ident": said})
        else:
            loc = (row.get("file"), row.get("start_line"), row.get("end_line"))
            if isinstance(loc[0], str) and all(isinstance(n, int) and not isinstance(n, bool) for n in loc[1:]):
                out.append({"source": source.file, "message": str(row.get("message") or ""), "texts": [],
                            "ident": None, "loc": (loc[0].removeprefix("./"), loc[1], loc[2])})
            else:
                out.append({"source": source.file, "message": str(row.get("message") or ""), "texts": [], "ident": None})
    return out


def _node(ident: str | None, runs: list) -> str | None:
    if not ident:
        return None
    escaped = json.dumps(ident, ensure_ascii=False)[1:-1]
    for _, events, prefix in runs:
        for e in events:
            if e.get("event_type") != "node_completed" or not isinstance(e.get("data"), dict):
                continue
            said = e["data"].get("node_output")
            said = said if isinstance(said, str) else json.dumps(said, ensure_ascii=False)
            if ident in said or escaped in said:
                return prefix + str(e.get("step_name") or "")
    return None


def _overlaps(ranges: dict, path: str, start: int, end: int) -> bool:
    return any(a <= end and start <= b for a, b in ranges.get(path, []))


def convert(producer, entry: dict, attempt: Path, run_id: str, base: str, head: str, ended: dict) -> tuple[dict, dict]:
    """(判定役の入力, 変換の控え)。producer は run.py の作り手（sources・node_runs・final_diff・leak_guard を持つ）"""
    ev = Path(attempt) / "evidence"
    tree = HeadTree(Path(attempt) / "target", head)
    runs = producer.node_runs(ev)
    diff, diff_why = producer.final_diff(ev)
    ranges = final_ranges(diff.read_text(encoding="utf-8")) if diff else None
    findings, kept, dropped, unread = [], [], [], {}
    for source in producer.sources:
        try:
            doc = json.loads((ev / source.file).read_text(encoding="utf-8"))
        except FileNotFoundError:
            unread[source.file] = "無い"
            continue
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            unread[source.file] = f"読めない（{type(e).__name__}）"
            continue
        for c in candidates(source, doc):
            found = [c["loc"]] if "loc" in c else [r for t in c["texts"] for r in refs(t)]
            place = tree.place(found)
            if place is None:
                dropped.append({"source": c["source"], "refs": [f"{p}:{s}-{e}" for p, s, e in found],
                                "why": NOT_AT_HEAD if found else NO_REF})
                continue
            path, start, end = place
            finding = {"file": path, "start_line": start, "end_line": end, "message": c["message"], "producer": producer.name}
            node = producer.name if "loc" in c else _node(c["ident"], runs)
            findings.append(finding)
            kept.append({**finding, "source": c["source"], "node": node, "node_why": None if node else NO_NODE,
                         "in_final_diff": None if ranges is None else _overlaps(ranges, path, start, end)})
    seconds, usd = ended.get("seconds"), ended.get("usd")
    usage = {**({"time_in_ms": int(seconds * 1000)} if seconds is not None else {}),
             **({"cost_usd": usd} if usd is not None else {})}
    doc = {"pr": {"repo": entry["repo"], "pr_number": int(entry["pr_number"]), "base": base, "head": head},
           "agent": producer.name, "findings": findings, **({"usage": usage} if usage else {})}
    record = {
        "key": key(entry), "producer": producer.name, "run_id": run_id, "attempt": str(attempt), "base": base, "head": head,
        "outcome": ended.get("outcome"), "seconds": seconds, "usd": usd, "usd_from": ended.get("usd_from"),
        "why_null": "。".join(([] if usd is not None else [f"usd: {ended.get('usd_from')} が読めない"])
                             + ([] if seconds is not None else ["seconds: run の始めと終わりの時刻が読めない"])),
        "sources": [s.file for s in producer.sources], "unread": unread,
        "findings": kept, "dropped": dropped, "dropped_count": len(dropped),
        "final_diff": diff.relative_to(ev).as_posix() if diff else None, "final_diff_why": diff_why,
        "leak_guard": producer.leak_guard, "web_calls": ended.get("web_calls"),
        "bench_limit": {"seconds": CONTRACT_SECONDS, "over": None if seconds is None else seconds > CONTRACT_SECONDS},
    }
    return doc, record


def write(out: Path, producer: str, name_: str, doc: dict, record: dict) -> tuple[Path, Path]:
    """判定役は findings/ を再帰で全部読むので、そこには判定役の入力だけを置き、控えは convert/ に分ける"""
    paths = (Path(out) / producer / "findings" / f"{name_}.json", Path(out) / producer / "convert" / f"{name_}.json")
    for path, body in zip(paths, (doc, record)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    return paths


def verdicts(details: Path) -> dict[tuple, str] | None:
    """判定役の results.details.json の (課題の鍵, file, start_line, end_line, message) → status。無ければ None"""
    try:
        rows = json.loads(Path(details).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise BenchError(f"判定役の結果（{details}）を読めない: {type(e).__name__}") from None
    return {(row.get("pr_key"), f.get("file"), f.get("start_line"), f.get("end_line"), f.get("message")): f.get("status")
            for row in rows if isinstance(row, dict) for f in row.get("candidate_findings") or [] if isinstance(f, dict)}
