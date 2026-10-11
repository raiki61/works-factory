"""並行 PR の役 pr-check（元 works/.shared/core/prcheck.py。写しの graph の節 p0.parallel_pr）の受け付けが使う部品。機械の道（開いている PR
と変更ファイルの交差）と受け付けの流れは lib/judge_accept.py の pr_scan・prcheck_take が持つ。

役は担当の PR へ投稿せず、申し送りの下書きを conflicts[].note に書き handed_over を false で返す。review-graph の 6 段の「衝突した
箇所を本ループのスコープから外す」は保つ: 役は外す hunk（PR・ファイル・今の作業ツリーでの行の範囲）を excluded に並べ、受け付けが
確かめて pr-excluded.json に置く（後の役に触らせないため）。

- NODE・ROLE: 節の名前と役の名前
- EXCLUDED_FIELD・EXCLUDED_SCHEMA・EXCLUDED: 外す hunk の欄・型・置き場のファイルの名
- BRIEF: 役への渡し物のファイルの名
- check_excluded: 外す hunk の誤りの一覧。_anchored: 受け付けた時の行の中身の印を足す。_write: 置き場に書く
"""
import hashlib
import pathlib
import sys

sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))
if str(CORE / "graphloops") not in sys.path:   # 元は board の import が写しの engine を sys.path に足していた
    sys.path.insert(0, str(CORE / "graphloops"))

from engine.schema import validate_schema  # noqa: E402
import marks  # noqa: E402

NODE = "p0.parallel_pr"
ROLE = "pr-check"
# 本ループのスコープから外す hunk（works だけの欄。写しの schema の conflicts[] は additionalProperties: false で足せないので、
# 返答の一番上に置き、受け付けが外してから盤面に渡す）。start・end は今の作業ツリーのファイルの行（1 始まり・両端を含む）
EXCLUDED_FIELD = "excluded"
EXCLUDED_SCHEMA = {"type": "array", "items": {
    "type": "object", "required": ["pr", "file", "start", "end", "why"], "additionalProperties": False,
    "properties": {"pr": {"type": "string", "minLength": 1}, "file": {"type": "string", "minLength": 1},
                   "start": {"type": "integer", "minimum": 1}, "end": {"type": "integer", "minimum": 1},
                   "why": {"type": "string", "minLength": 1}}}}
EXCLUDED = marks.KINDS["pr"].file   # 受け付けた外す hunk {node, head, excluded}
BRIEF = "pr-brief.json"         # 役への渡し物（落ちた理由・交差を取る集合・版）


def _anchored(excluded: list, repo) -> list:
    """外す hunk ごとに、受け付けた時の行の中身 text（start〜end。改行つき）と、その行のバイトの sha256 を足した写し。
    行の番号は後の周の修正でずれるので、後の役・受け付けは中身で引き直す（review-graph は同じ writer が中身で覚えている）"""
    out = []
    for h in excluded:
        raw = b"".join((pathlib.Path(repo) / h["file"]).read_bytes().splitlines(keepends=True)[h["start"] - 1:h["end"]])
        out.append({**h, "text": raw.decode("utf-8", "replace"), "sha256": hashlib.sha256(raw).hexdigest()})
    return out


def check_excluded(reply: dict, repo) -> list:
    """外す hunk（excluded）の誤りの一覧（空なら通す。返答の残りは写しの schema を通った後に呼ぶ）: 型・start <= end・PR が conflicts に在りファイルがその行の files に在る・
    ファイルが今の作業ツリーに在り end が行の数を超えない・外す hunk を持つ PR の行に申し送りの下書き（note）が在る"""
    ex = reply.get("excluded")
    if ex is None:
        return ["excluded が無い（外す hunk が無ければ空の配列）"]
    errs = validate_schema(ex, EXCLUDED_SCHEMA)
    if errs:
        return [f"excluded の型: {e}" for e in errs]
    rows = {c.get("pr"): c for c in reply.get("conflicts") or [] if isinstance(c, dict)}
    out = []
    for i, h in enumerate(ex):
        at = f"excluded[{i}]（PR {h['pr']}・{h['file']}）"
        c = rows.get(h["pr"])
        if h["start"] > h["end"]:
            out.append(f"{at}: start {h['start']} が end {h['end']} より大きい")
        if c is None:
            out.append(f"{at}: PR {h['pr']} は conflicts に無い")
            continue
        if h["file"] not in (c.get("files") or []):
            out.append(f"{at}: ファイルは PR {h['pr']} の交差したファイル {c.get('files')} に無い")
        f = pathlib.Path(repo) / h["file"]
        if not f.is_file():
            out.append(f"{at}: ファイルが今の作業ツリーに無い（行の範囲は今の作業ツリーのファイルで書く）")
        else:
            n = len(f.read_bytes().splitlines())
            if h["end"] > n:
                out.append(f"{at}: end {h['end']} がファイルの行の数 {n} を超える")
        if not (c.get("note") or "").strip():
            out.append(f"{at}: 外す hunk を持つ PR {h['pr']} の行に申し送りの下書き（note）が無い")
    return out


def _write(path: pathlib.Path, obj) -> pathlib.Path:
    marks.write(path, obj)
    return path
