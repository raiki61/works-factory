"""仕様駆動の道で、会話で回した部品の審査の記録を Archon の run の記録と照らす（docs/design/spec-driven.md の 2.6 の 2）。

起動の殻（launcher.py）が、メイングラフを `--input spec_table=<表>` で起こす時と、block works-factory-spec-driven を `--input table=<表>` で
起こす時だけ呼ぶ。ほかの起動は表を読まず、uv も起こさない。表を読むのは PyYAML を宣言した script（spec-inputs.py）を uv で起こした
子だけで、ここ（殻の素の Python）は標準ライブラリだけで Archon の記録を読む（E14。持ち主の決め others-may-use）。

表の reviews の行ごとに `workflow get <run> --json` の記録を読み、次を全部照らす:
- a. 記録が在る（同じ Archon の家の run。会話から部品を回す時は、工場の run と同じ対象のパスで回す）
- b. 記録の workflow_name が行の part と同じ
- c. status が completed・outcome が succeeded で、返す値（terminal_record.returns.value）の ok が真
- d. 記録の入力（metadata.inputs。直に起こした run は名指した入力だけを残す）が、今の表と設計書から組んだ入力（spec-inputs.py）と
  同じ。比べるのは組んだ鍵だけ（ほかに名指した入力〔web・lang など〕と、部品に後で足した入力の既定は比べない）。値が JSON なら
  JSON の値で比べる。計画の審査は方針の文を proposal_file で受けた記録で、そのファイルの名（spec-inputs.py が中身の sha256 で付ける）
  が今の設計書と表から組んだ方針の文の sha256 を持つ（ファイルが残っていれば中身も照らす）
- e. 返す値から数えられる指摘が、どれもその行の findings の key に在る。計画の審査は holes の先の faces[].key の全部、世界の解は
  rows の先の行で versus.verdict が differs の class_id、前提の実測は constraints の先の行で contradicts の在る行（key は
  premises-<行の番号>）、前の決めの確かめは material の先の reply.conflicts の行（key は prior-<行の番号>）。独立設計は指摘の形を持たない
- f. 世界の解は、rows の先の行が、今の表と設計書から組んだ依頼の行（d の request）の行ごとに 1 つずつ在る: finding が 1〜行の数の
  どれも 1 回だけ・ほかの番号が無い・where がその依頼の行の where。行のファイルを返さない記録も合わない。e の指摘の照らしは書かれた
  行の指摘しか数えないので、書かれなかった行（未評価の行）を通さないためにここで照らす

e・f が読む返す値の欄と、その指す先の中身の欄は、表 RETURN_READS の 1 か所に書く（部品 → 返す値の欄・その欄の form・読む欄の道）。
form は部品の返す値の output_format のその欄の form と字のまま同じで、道はその form の形に在る（静的な照らしは
tests/layers/scan.py の E5 の _shell_reads）。指す先の中身は、読む前にその form の形で照らす（.shared の口 ports.shape_errors。
形に合わなければ e の読めない訳で止め、指摘を 0 件と読んで黙って通さない。versus.verdict が評価済みの語かも形の enum が照らす）

結果は家の spec-reviews/<中身の hash>.json に書き、パスを run の設定の層の env（RESULT_ENV）で run に渡す（resume しても同じ値）。
block の形 entry は、そのファイルが今の表と設計書の物で、全部の行が合っていることだけを照らす。

- named_table(workflow, flags) -> 表のパスか None
- check(target, table, read_table, get) -> 結果の dict。read_table(target, table) は spec-inputs.py の返す値、get(run) は記録（無ければ None）
- write(home, doc) -> パス・problems(doc) -> 合わなかった行の訳の並び
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from bin._lib import place

LINE, BLOCK = "works-factory-line", "works-factory-spec-driven"
TABLE_INPUT = {LINE: "spec_table", BLOCK: "table"}
RESULT_ENV = "WORKS_FACTORY_SPEC_REVIEWS"   # workflows/spec-driven/src/files.py の REVIEWS_ENV と同じ名
READER = Path(__file__).with_name("spec-inputs.py")
PLAN_REVIEW, WORLD = "works-factory-plan-review", "works-factory-world"
PREMISES, PRIOR_DECISIONS = "works-factory-premises", "works-factory-prior-decisions"
# 部品の返す値から読む所（e・f）: 部品 → (返す値の欄, その欄の form, 指す先の中身から読む欄の道)。道は . で段を分け、段の末の [] は
# 配列の要素。jsonl の form の道は 1 行の中の道。form と道は部品の宣言に照らされる（モジュールの docstring）
RETURN_READS = {
    PLAN_REVIEW: ("holes", "json(shared:plan-review-reply.schema.json)", ("faces[].key",)),
    PREMISES: ("constraints", "json(shared:constraints.schema.json)", ("constraints[].contradicts",)),
    PRIOR_DECISIONS: ("material", "json(shared:material.schema.json)", ("reply.conflicts[]",)),
    WORLD: ("rows", "jsonl(lib:world-row.schema.json)", ("finding", "where", "class_id", "versus.verdict")),
}
FACE_KEYS, = RETURN_READS[PLAN_REVIEW][2]
CONTRADICTS, = RETURN_READS[PREMISES][2]
CONFLICTS, = RETURN_READS[PRIOR_DECISIONS][2]
FINDING, WHERE, CLASS_ID, VERDICT = RETURN_READS[WORLD][2]
DIFFERS = "differs"   # 世界の解の行の versus.verdict のうち、指摘に数える語（形 lib:world-row.schema.json の enum の 1 つ）


def named_table(workflow: str | None, inputs: list[str]) -> str | None:
    """起動が名指した表のパス（メイングラフの spec_table・block の table。空・名指さなければ None）。inputs は --input の値の並び"""
    name = TABLE_INPUT.get(workflow or "")
    if name is None:
        return None
    got = [v.split("=", 1)[1] for v in inputs if v.split("=", 1)[0] == name and "=" in v]
    return got[-1].strip() or None if got else None


def read_table(uv: str, target: Path, table: str, env: dict) -> dict:
    """spec-inputs.py を uv で起こして表を読む（PyYAML は uv が入れる）。読めなければ RuntimeError"""
    done = subprocess.run([uv, "run", "--script", str(READER), str(target), table], env=env, capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"表を読む script が落ちた（{done.returncode}）: {done.stderr.strip()[-500:]}")
    try:
        return json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"表を読む script の返す値が JSON でない: {done.stdout.strip()[-300:]}") from None


def archon_get(head: list[str], target: Path, env: dict):
    """記録を読む口（get に渡す）: `workflow get <run> --json --cwd <対象>`。無い・読めない run は None"""
    def get(run: str):
        done = subprocess.run([*head, "workflow", "get", run, "--json", "--cwd", str(target)], env=env, capture_output=True, text=True,
                              encoding="utf-8")
        try:
            got = json.loads(done.stdout)
        except ValueError:
            return None
        return got if done.returncode == 0 and isinstance(got, dict) and got.get("ok") is not False else None
    return get


def _value(text):
    """記録の入力の字（JSON なら値）"""
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text)
    except ValueError:
        return text


def _same(recorded, built) -> bool:
    """記録の入力の字 recorded と組んだ値 built が同じか（字は字のまま、JSON の値は読んで比べる）"""
    return recorded == built if isinstance(built, str) else _value(recorded) == built


def _pointed(record: dict, ptr) -> Path | None:
    """返す値の pointer の先のファイル（terminal_record.artifacts.root の下）。pointer が無ければ None（指摘のファイルを返さない部品の
    run）。pointer が在るのに置き場の根が記録に無い・空か、pointer が根の外を指せば ValueError（指摘を 0 件と読んで黙って通さない。
    bin/_lib/apply.py の同じ場面と同じ照らし）"""
    if not isinstance(ptr, dict) or not isinstance(ptr.get("path"), str):
        return None
    root = ((record.get("terminal_record") or {}).get("artifacts") or {}).get("root")
    if not isinstance(root, str) or not root:
        raise ValueError("run の置き場の根（artifacts.root）が記録に無い")
    real_root = os.path.realpath(root)
    real = os.path.realpath(os.path.join(root, ptr["path"]))
    if os.path.commonpath([real_root, real]) != real_root:
        raise ValueError(f"pointer の path {ptr['path']} が run の置き場の外を指す")
    return Path(real)


def _walk(doc, path: str) -> list:
    """読む欄の道 path（RETURN_READS の道）の値の並び。[] の段は要素ごとに広げ、欄の無い所は None（並びの位置を保つ）"""
    got = [doc]
    for step in path.split("."):
        name, many = step.removesuffix("[]"), step.endswith("[]")
        got = [v.get(name) if isinstance(v, dict) else None for v in got]
        if many:
            got = [x for v in got for x in (v if isinstance(v, list) else [])]
    return got


def _returned(record: dict, part: str, value: dict):
    """部品 part の返す値の欄（RETURN_READS）の指す先を、その欄の form の形で照らして読んだ物（json は値、jsonl は行の並び）。
    pointer が無ければ None（指摘のファイルを返さない部品の run）。読めない・形に合わなければ ValueError（_pointed も同じ）"""
    field, form, _ = RETURN_READS[part]
    path = _pointed(record, value.get(field))
    if path is None:
        return None
    ports = place.shared("ports")
    kind, name = ports.form_of(form)
    text = path.read_text(encoding="utf-8")
    docs = [json.loads(line) for line in text.splitlines() if line.strip()] if kind == "jsonl" else [json.loads(text)]
    errors = [e for doc in docs for e in ports.shape_errors(doc, name)]
    if errors:
        raise ValueError(f"{path.name} が {form} の形に合わない: {' / '.join(errors[:3])}")
    return docs if kind == "jsonl" else docs[0]


def _keys(record: dict, part: str, value: dict) -> tuple[set, str]:
    """(返す値から数えられる指摘の key, 読めない訳)。指摘の形を持たない部品は (空, "")"""
    if part not in RETURN_READS:
        return set(), ""
    try:
        doc = _returned(record, part, value)
    except (OSError, ValueError) as error:
        return set(), f"返す値の指摘のファイルを読めない（{type(error).__name__}: {error}）"
    if doc is None:
        return set(), ""
    if part == PLAN_REVIEW:
        return {str(k) for k in _walk(doc, FACE_KEYS)}, ""
    if part == PREMISES:   # 前提の実測の行のうち contradicts（食い違う依頼の行の where）の在る行。key は premises-<行の番号>
        return {f"premises-{n}" for n, c in enumerate(_walk(doc, CONTRADICTS), 1) if c}, ""
    if part == PRIOR_DECISIONS:   # 前の決めの確かめの conflicts の行。key は prior-<行の番号>
        return {f"prior-{n}" for n, _ in enumerate(_walk(doc, CONFLICTS), 1)}, ""
    return {str(row[CLASS_ID]) for row in doc if _walk(row, VERDICT) == [DIFFERS]}, ""   # WORLD


def _same_proposal(named: str, sha: str) -> bool:
    """計画の審査が受けた方針の文のファイル（記録の proposal_file）が、今の版の字の物か: 名が spec-proposal-<sha>.md（spec-inputs.py が
    中身の sha256 で付ける名）で、ファイルが残っていれば前後の空白を除いた中身の sha256 も同じ"""
    if not named.strip() or Path(named).name != f"spec-proposal-{sha}.md":
        return False
    try:
        text = Path(named).read_text(encoding="utf-8")
    except OSError:
        return True   # 会話の後に消した一時のファイル。名の sha256 で照らした
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest() == sha


def check_row(row: dict, record, built: dict, proposal_sha: str) -> list:
    """表の reviews の 1 行の照らし（a〜f）。合わない訳の並び（空は合う）"""
    part, run = str(row.get("part") or ""), str(row.get("run") or "")
    if record is None:
        return [f"a: run {run} の記録が無い（同じ対象のパスで部品を回したか）"]
    why = []
    if record.get("workflow_name") != part:
        why.append(f"b: 記録の部品の名が {record.get('workflow_name')}（表は {part}）")
    returns = (record.get("terminal_record") or {}).get("returns") or {}
    value = returns.get("value") if returns.get("availability") == "available" and isinstance(returns.get("value"), dict) else {}
    if record.get("status") != "completed" or record.get("outcome") != "succeeded" or value.get("ok") is not True:
        why.append(f"c: 記録が成功で終わっていない（status {record.get('status')}・outcome {record.get('outcome')}・返す値の ok "
                   f"{value.get('ok')}）")
    inputs = (record.get("metadata") or {}).get("inputs") or {}
    for name, want in built.get(part, {}).items():
        if not _same(inputs.get(name), want):
            why.append(f"d: 入力 {name} が今の表と設計書から組んだ物と違う（審査した後に仕様が変わったか、組み方が違う）")
    if part == PLAN_REVIEW and not _same_proposal(str(inputs.get("proposal_file") or ""), proposal_sha):
        why.append(f"d: 方針の文が今の設計書と表から組んだ物と違う（proposal_file のファイルの名が spec-proposal-{proposal_sha}.md でない"
                   "か、中身が名の sha256 と違う。spec-inputs.py の --proposal-dir で書いたファイルを渡す）")
    keys, unread = _keys(record, part, value)
    if unread:
        why.append(f"e: {unread}")
    accepted = {str(f.get("key")) for f in row.get("findings") or [] if isinstance(f, dict)}
    missing = sorted(keys - accepted)
    if missing:
        why.append(f"e: 返す値の指摘 {'・'.join(missing)} が findings に無い（持ち主が受け入れた指摘だけを残す）")
    if part == WORLD and not unread:
        why += [f"f: {w}" for w in _world_cover(record, value, built.get(part, {}).get("request"))]
    return why


def _world_cover(record: dict, value: dict, request) -> list:
    """世界の解の行が、組んだ依頼の行 request の行ごとに 1 つずつ在り、評価済みか（f）。合わない訳の並び（空は合う）"""
    if not isinstance(request, list):
        return ["今の表と設計書から依頼の行を組めない"]
    try:
        rows = _returned(record, WORLD, value)
    except (OSError, ValueError) as error:
        return [f"世界の解の行のファイルを読めない（{type(error).__name__}: {error}）"]
    if rows is None:
        return ["世界の解の返す値に行のファイルが無い（依頼の行ごとに 1 行が要る）"]
    found: dict = {}
    for r in rows:   # 行は形で照らした物（finding は整数。真偽は整数に数えない）
        n = r[FINDING]
        found.setdefault(repr(n) if isinstance(n, bool) else n, []).append(r)
    out = []
    for n, want in enumerate(request, 1):
        got = found.pop(n, [])
        if not got:
            out.append(f"依頼の行 {n} に世界の解の行が無い（{want.get('where')}。審査していない行）")
        elif len(got) > 1:
            out.append(f"依頼の行 {n} に世界の解の行が {len(got)} つ在る")
        elif got[0][WHERE] != want.get("where"):
            out.append(f"依頼の行 {n} の世界の解の行の where が {got[0][WHERE]}（依頼の行は {want.get('where')}）")
    out += [f"依頼の行に無い番号 {n} の世界の解の行が在る" for n in found]
    return out


def check(target: Path, table: str, read, get) -> dict:
    """read(target, table) は spec-inputs.py の返す値、get(run) は記録。表が読めない・1〜4 が欠ける時は rows を作らず problems を持つ"""
    built = read(target, table)
    if not built.get("ok"):
        return {"table": built.get("table") or table, "problems": list(built.get("problems") or ["表を読めない"]), "rows": []}
    rows = []
    for row in built.get("reviews") or []:
        why = check_row(row, get(str(row.get("run") or "")), built.get("inputs") or {}, built.get("proposal_sha256") or "")
        rows.append({"part": row.get("part"), "run": row.get("run"), "ok": not why, "why": why})
    return {"table": built["table"], "table_sha256": built["table_sha256"], "design_sha256": built["design_sha256"], "problems": [],
            "rows": rows}


def problems(doc: dict) -> list:
    return list(doc.get("problems") or []) + [f"{r['part']}（run {r['run']}）: {'・'.join(r['why'])}" for r in doc["rows"] if not r["ok"]]


def write(home: Path, doc: dict) -> Path:
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    path = home / "spec-reviews" / f"{hashlib.sha256(text.encode()).hexdigest()[:16]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)
    return path
