"""並行 PR の検査 p0.parallel_pr（線 A。仕様 3.8・裁定 TA8。持ち主の答え 2026-09-27: 案 (a)）。

1〜5 段（owner/repo の解決・自分の PR の除外・打ち切り・変更ファイルの交差）は、盤面の層の run_engine が写しの
parallel-pr.py を走らせる（run_helper）。交差が在る・gh が無い時だけ任せ先に落ち、読むだけの
段に書いた模型（sonnet・medium）の役 pr-check（ブロック blk-pr）が 6 段の全部をする。remote が forge（PR を持つホスト。GitHub）
でない run（origin が無い・ローカルのパス・ほかのホスト）は、entry の差し替え（on_init・parallel_pr_due・fill_materials。forge.py）
が run の初めに決めて節を条件外にし、素材を not_applicable（no_forge: <種類>）で埋めるので、ここにも役にも来ない。6 段目だけ替える: 担当の PR へ投稿せず、申し送りの下書きを
conflicts[].note に書き handed_over を false で返す（真は blk-pr/scripts/accept.py の check_no_post が拒む）。
投稿しないことは review-graph より下げた所で、<ライン>/downgrades.json に宣言し、報告の冒頭に出す。
review-graph の 6 段の「衝突した箇所を本ループのスコープから外す」は保つ: 役は外す hunk（PR・ファイル・今の作業ツリーでの行の範囲）を
excluded に並べ、受け付けが確かめて今の周の pr-excluded.json に置き、collect が excluded_file で渡す（後の役に触らせないため）。

ここに在る物:
- NODE・ROLE・OUTPUT_FORMAT: 節の名前、役の名前、役の output_format（写しの schema に works だけの欄 excluded を足し、
  印 works-node: pr-check を付けた物。excluded は受け付けが外してから盤面に渡す）
- GH_READ: 打ってよい gh の語（包みの読む口を通す。口の名と呼び方の正本は包み adapter の RO_GH・RO_GH_RULE）
- run_helper(b, *, runner=None): start（と線 B の境の節）が呼ぶ。engine で済んだか・役が要るか
- snapshot・take・collect・drafts: blk-pr の節 pr-snap・pr-accept・collect の中身（main_* はスクリプトの入口）
- downgrades・head_downgrades: 下げた物の一覧（<ライン>/downgrades.json）と、報告の頭の行の部品

盤面を開く口は線 A の entry.open_board（Task 3）。ここでは opener で差し替えられる（試験は節の表を渡して開く）。
take は entry.take（Task 9）と同じ約束の、このブロックだけの形（rolekit.accept_role の take に渡す）。
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
EXCLUDED = marks.KINDS["pr"].file   # 受け付けた外す hunk {node, excluded}（collect の excluded_file）
# 読む gh は包みの読む口を通す: 印のある起動の全部に、包み（.shared/core/adapter.py の 5）が素の gh を拒み（permissions.deny Bash(gh:*) と
#   本物の gh のパス）、許す物だけを通す口 works-gh を PATH の頭に置く。口が通すのは pr list・pr view・pr diff の -R つきと
#   repo view <OWNER/REPO> だけ。役は口を素の名の 1 つだけのコマンドで打つ（sandbox の除外に当たる形。呼び方の正本は包みの
#   RO_GH・RO_GH_EXCLUDED・RO_GH_RULE で、tests/test_gh_port.py が指示書と YAML をそれに縛る）。
# GH_READ: 口を通して打ってよい gh の語（全部 -R <owner/repo> を付ける）。許す物の正本は包みの口の側で、これは指示書の側の組。
#   禁じる物の一覧は読むだけの役にとって完全にならない（gh pr update-branch・git push など）ので、柵は許す物で組む。
GH_READ = ("pr list", "pr view", "pr diff")
BRIEF = "pr-brief.json"         # 役への渡し物（落ちた理由・交差を取る集合・版）


class Refused(Exception):
    """engine の 1〜5 段を走らせられない（呼び直しても計画が拒まれる・対象の根が引けない）。start は AI を起こす前に止める
    （entry の CiRefused と同じ扱い）"""


# ---------------------------------------------------------------- blk-pr の節
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
