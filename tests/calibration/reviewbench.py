"""GitHub ReviewBench（PR の審査の公開ベンチ）の口。ランナー run.py が使う（試験のモジュールではない。test_*.py に当たらない）。

課題を manifest から選び、試みのフォルダ（target は head を取り出し base が辿れる写し）を組み、PR の題と本文を依頼にし、作り手の
出力を判定役の入力（docs/JUDGING_INPUT.md の形）に変える。指摘の場所は出力の字の <パス>:<行> を head の版で照らし、パスがファイル名
だけの番地は候補の key・where のパスか head の一意なファイルに解いて元の番地を残し、照らせない物は捨てて数を残す。標準ライブラリ
だけ。期限を置かない（持ち主の決め no-timeouts）。手順と形は ReviewBench の commit c17b05b の
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
# ASCII: 日本語の字の直後のパスで、前の字をパスに含めない
REF = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]+):(\d+)(?:[-–](\d+))?", re.ASCII)
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
# 候補の key・where の字の中の、repo からのパス（/ を 1 つ以上持つ）。文の番地のパスがファイル名だけの時の手がかり
HINT = re.compile(r"(?<![\w./-])(?:\./)?((?:[\w.-]+/)+[\w.-]+)", re.ASCII)
NO_REF, NOT_AT_HEAD, AMBIGUOUS = "番地が無い", "head に無い番地", "番地のパスが一意に決まらない"
NO_NODE = "どのノードの出力にも所見の字が無い"
# 判定役の status → ノードの表の数の欄
VERDICTS = {"matched_tp": "hit", "novel_tp": "real", "matched_fp": "wrong", "novel_fp": "wrong"}
GIT_ENV = {"GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}
# 作り手の出力の 1 つの出どころ: evidence/ からのファイル・候補の行への道（"*" は並びを開く）・形（units は判定の単位、items は
# where と text の欄を持つ所見、findings は AGENT_CONTRACT の指摘）・items の字の欄・在れば file の代わりに読むファイル
Source = namedtuple("Source", "file rows kind text prefer", defaults=(None, None))


MISSING = "無い"   # 読み元のファイルが無い時の unread の字（全部の読み元が無ければ convert が止まる）


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


def has(repo: Path, *shas: str) -> bool:
    return all(subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True,
                              env={**os.environ, **GIT_ENV, "GIT_NO_LAZY_FETCH": "1"}).returncode == 0 for sha in shas)


def prepare(entry: dict, attempt: Path, cache: Path, mirror: str = MIRROR) -> dict:
    """試みのフォルダを組み、{"base", "head"} を返す。target の main は head、refs/bench/base が base。origin（bare）にも同じ物を
    置く。写しは mirror から blob ごと取る（run の中で網へ blob を取りに行く道を作らない）"""
    base, head = entry["base"], entry["head"]
    repo = Path(cache) / name(entry)
    if not repo.is_dir():
        git("init", "-q", "--bare", str(repo))
    if not has(repo, base, head):
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
    """head の版のファイルの一覧（1 回だけ取る）と行数（パスごとに 1 回だけ読む）"""

    def __init__(self, target: Path, head: str):
        self.target, self.head, self.seen, self._files = Path(target), head, {}, None

    def lines(self, path: str) -> int | None:
        if path not in self.seen:
            done = subprocess.run(["git", "-C", str(self.target), "cat-file", "-p", f"{self.head}:{path}"],
                                  capture_output=True, stdin=subprocess.DEVNULL)
            self.seen[path] = len(done.stdout.splitlines()) if done.returncode == 0 else None
        return self.seen[path]

    def files(self) -> set[str]:
        if self._files is None:
            done = subprocess.run(["git", "-C", str(self.target), "ls-tree", "-r", "-z", "--name-only", self.head],
                                  capture_output=True, stdin=subprocess.DEVNULL)
            self._files = set(done.stdout.decode("utf-8", "surrogateescape").split("\0")) - {""} if done.returncode == 0 else set()
        return self._files

    def resolve(self, path: str, hints: list[str]) -> list[str]:
        """head に無いパスの読みの候補。手がかりのパスのうち /<path> で終わる物が head に 1 つだけならそれ、でなければ head の
        ファイルのうち /<path> で終わる物の全部"""
        tail = "/" + path
        by_hint = {h for h in hints if h.endswith(tail)} & self.files()
        return list(by_hint) if len(by_hint) == 1 else sorted(f for f in self.files() if f.endswith(tail))

    def fits(self, path: str, start: int, end: int) -> bool:
        n = self.lines(path)
        return n is not None and 1 <= start <= end <= n

    def place(self, found: list[tuple[str, int, int]], hints: list[str] | None = None) -> tuple[str, int, int, str | None] | str:
        """最初に head で照らせた番地 (パス, 始め, 終わり, 解く前の番地か None)、照らせなければ捨てる訳。hints が None なら
        パスを解かない。head に在るパスは行が外れても解かない"""
        ambiguous = False
        for path, start, end in found:
            if self.fits(path, start, end):
                return path, start, end, None
            if hints is None or self.lines(path) is not None:
                continue
            read = self.resolve(path, hints)
            if len(read) == 1 and self.fits(read[0], start, end):
                return read[0], start, end, f"{path}:{start}-{end}"
            ambiguous = ambiguous or len(read) > 1
        return AMBIGUOUS if ambiguous else NOT_AT_HEAD if found else NO_REF


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
    """出どころの 1 つの文書から候補 {source, message, texts, ident[, hints][, loc]} の並び。hints は番地のパスを解く手がかりの
    パス（units は key、items は where の中の物）で、構造で場所を持つ findings には無い"""
    out = []
    for row in _walk(doc, source.rows):
        if source.kind == "units":
            k, reason = str(row.get("key") or ""), str(row.get("reason") or "")
            out.append({"source": source.file, "message": f"[{row.get('label')}] {k}\n{reason}", "texts": [reason, k], "ident": k,
                        "hints": HINT.findall(k)})
        elif source.kind == "items":
            said = str(row.get(source.text) or "")
            message = said + (f"\n{row['mechanism']}" if row.get("mechanism") else "")
            where = str(row.get("where") or "")
            out.append({"source": source.file, "message": message, "texts": [where, said], "ident": said,
                        "hints": HINT.findall(where)})
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
    sources = [source._replace(file=source.prefer) if source.prefer and (ev / source.prefer).is_file() else source
               for source in producer.sources]
    for source in sources:
        try:
            doc = json.loads((ev / source.file).read_text(encoding="utf-8"))
        except FileNotFoundError:
            unread[source.file] = MISSING
            continue
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            unread[source.file] = f"読めない（{type(e).__name__}）"
            continue
        for c in candidates(source, doc):
            found = [c["loc"]] if "loc" in c else [r for t in c["texts"] for r in refs(t)]
            place = tree.place(found, c.get("hints"))
            if isinstance(place, str):
                dropped.append({"source": c["source"], "refs": [f"{p}:{s}-{e}" for p, s, e in found], "why": place})
                continue
            path, start, end, written = place
            finding = {"file": path, "start_line": start, "end_line": end, "message": c["message"], "producer": producer.name}
            node = producer.name if "loc" in c else _node(c["ident"], runs)
            findings.append(finding)
            kept.append({**finding, "ref_as_written": written, "source": c["source"], "node": node,
                         "node_why": None if node else NO_NODE,
                         "in_final_diff": None if ranges is None else _overlaps(ranges, path, start, end)})
    if sources and all(why == MISSING for why in unread.values()) and len(unread) == len(sources):
        raise BenchError(f"{producer.name} の読み元が全部無い（{', '.join(unread)}）。置き場の道が run の記録と合っていない。"
                         "0 件で採点を続けない")
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
        "sources": [s.file for s in sources], "unread": unread,
        "findings": kept, "resolved_count": sum(f["ref_as_written"] is not None for f in kept),
        "dropped": dropped, "dropped_count": len(dropped),
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
    got = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for f in row.get("candidate_findings") or []:
            if not isinstance(f, dict):
                continue
            status = f.get("status")
            if status not in VERDICTS:
                raise BenchError(f"判定役の結果（{details}）に知らない判定の語 {status!r}（課題 {row.get('pr_key')}）。"
                                 "reviewbench.VERDICTS を ReviewBench の版に合わせる")
            got[(row.get("pr_key"), f.get("file"), f.get("start_line"), f.get("end_line"), f.get("message"))] = status
    return got
