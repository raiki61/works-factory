"""並行 PR の役 pr-check（元 works/.shared/core/prcheck.py。写しの graph の節 p0.parallel_pr）の受け付けが使う部品。機械の道（開いている PR
と変更ファイルの交差）と受け付けの流れは lib/judge_accept.py の pr_scan・prcheck_take が持つ。

役は担当の PR へ投稿せず、申し送りの下書きを conflicts[].note に書き handed_over を false で返す。review-graph の 6 段の「衝突した
箇所を本ループのスコープから外す」は保つ: 役は外す hunk（PR・ファイル・今の作業ツリーでの行の範囲）を excluded に並べ、受け付けが
確かめて pr-excluded.json に置く（後の役に触らせないため）。

- NODE・ROLE: 節の名前と役の名前
- EXCLUDED_FIELD・EXCLUDED: 外す hunk の欄・置き場のファイルの名
- BRIEF: 役への渡し物のファイルの名
- check_excluded: 外す hunk の誤りの一覧。_anchored: 受け付けた時の行の中身の印を足す。_write: 置き場に書く
- DRAFTS・draft_lines(rows): 判定の隣の申し送りの下書き [{pr, files, note}] のファイルの名（docs/design.md の隣のファイル）と報告の行
- DOWNGRADES・DOWNGRADE_KEYS・downgrades(path)・head_downgrades(rows): 下げた物の宣言（元 prcheck.py:322・:345。lib/downgrades.json
  [{node, what, versus}]。node は写しの graph の節）と、報告の頭の「下げている所: K 個」
"""
import hashlib
import json
import pathlib
import sys

sys.dont_write_bytecode = True

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import marks  # noqa: E402

NODE = "p0.parallel_pr"
ROLE = "pr-check"
DRAFTS = "pr-downgrades.json"   # 申し送りの下書き [{pr, files, note}]（判定の隣。GitHub に投稿しない。報告が人に渡す）
DOWNGRADES = "downgrades.json"
DOWNGRADE_KEYS = ("node", "what", "versus")
# 本ループのスコープから外す hunk（works だけの欄。写しの schema の conflicts[] は additionalProperties: false で足せないので、
# 返答の一番上に置き、受け付けが外してから盤面に渡す）。start・end は今の作業ツリーのファイルの行（1 始まり・両端を含む）
EXCLUDED_FIELD = "excluded"
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
    """外す hunk（excluded）の誤りの一覧（空なら通す。型は役の節の output_format が照らした後に呼ぶ）: start <= end・PR が conflicts に在りファイルがその行の files に在る・
    ファイルが今の作業ツリーに在り end が行の数を超えない・外す hunk を持つ PR の行に申し送りの下書き（note）が在る"""
    ex = reply["excluded"]
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


# ---------------------------------------------------------------- 申し送りの下書きと下げた物の宣言（報告が読む）
def draft_lines(rows) -> list:
    """申し送りの下書きの報告の行（元 report._pr_lines の前半。note を持つ行だけ）"""
    return [f"並行 PR #{r.get('pr')} の担当への申し送りの下書き（{'・'.join(map(str, r.get('files') or []))}。投稿していない）: "
            f"{r['note']}" for r in rows or [] if isinstance(r, dict) and r.get("note")]


def downgrades(path: pathlib.Path = CORE / DOWNGRADES) -> list:
    """下げた物の宣言 [{node, what, versus}]（無ければ []）。形が崩れていれば ValueError（黙って 0 個と数えない）"""
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{path} が読めない: {e}") from None
    bad = [] if isinstance(rows, list) else [f"一番上が配列でない（{type(rows).__name__}）"]
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        if not (isinstance(r, dict) and sorted(r) == sorted(DOWNGRADE_KEYS)
                and all(isinstance(r[k], str) and r[k].strip() for k in DOWNGRADE_KEYS)):
            bad.append(f"{i} 行目が {{node, what, versus}}（空でない文字列）でない: {r!r}")
    if bad:
        raise ValueError(f"{path}: " + "; ".join(bad))
    return rows


def head_downgrades(rows) -> str:
    """報告の頭の行の部品「下げている所: K 個」（元 head_downgrades）"""
    return f"下げている所: {len(rows)} 個"
