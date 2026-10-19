"""並行 PR の役 pr-check の返答の受け付け（docs/design/parallel-pr.md の 4 節）。元は lib/judge_accept.py の check_no_post・prcheck_drafts・
prcheck_take・pr_accept と lib/prcheck.py の _anchored・check_excluded・_write。

照らす順: 返答が JSON のオブジェクト → 投稿していない → 読むだけの役が作業ツリーを変えていない → 素材の欄が記録の決まりに合う
（carried_over と not_applicable は書けない・札ごとの要る欄）→ 外す hunk が合う。通れば外す hunk を中身の印つきで pr-excluded.json に、
申し送りの下書きを pr-downgrades.json に、素材を material-pr-check.json に書く。拒めば何も書かない。3 回目の拒否で輪を抜ける
（rolekit.GIVE_UP_AFTER）。諦めた控えは別に書かず、出口が rolekit.given_up_reason を読む。
"""
import hashlib
import json
import pathlib

import accept as core_accept   # lib/
import jsonfile                # lib/
import materialkit             # lib/
import rolekit                 # lib/
from engine.util import Reject   # lib/graphloops/

from . import files

# 元 works/blk-pr/scripts/accept.py:21
NO_POST = "このラインは申し送りを投稿しない（持ち主の決定 2026-09-27）。下書きを note に書き handed_over を false にせよ: "
EXCLUDED_FIELD = "excluded"


def check_no_post(reply) -> list:
    """conflicts[].handed_over が真の行の pr の一覧（空なら通す）"""
    rows = reply.get("conflicts") if isinstance(reply, dict) else None
    if not isinstance(rows, list):
        return []
    return [str(c.get("pr")) for c in rows if isinstance(c, dict) and c.get("handed_over")]


def drafts(reply) -> list:
    """受け付けた返答の申し送りの下書き [{pr, files, note}]（note を持つ交差だけ）"""
    return [{"pr": c["pr"], "files": c["files"], "note": c["note"]}
            for c in (reply or {}).get("conflicts", []) if isinstance(c, dict) and c.get("note")]


def check_excluded(reply: dict, repo) -> list:
    """外す hunk（excluded）の誤りの一覧（空なら通す。型は役の節の output_format が照らした後に呼ぶ）: start <= end・PR が conflicts に在り
    ファイルがその行の files に在る・ファイルが今の作業ツリーに在り end が行の数を超えない・外す hunk を持つ PR の行に申し送りの下書き（note）が在る"""
    ex = reply[EXCLUDED_FIELD]
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


def anchored(excluded: list, repo) -> list:
    """外す hunk ごとに、受け付けた時の行の中身 text（start〜end。改行つき）と、その行のバイトの sha256 を足した写し。
    行の番号は後の周の修正でずれるので、後の役・受け付けは中身で引き直す"""
    out = []
    for h in excluded:
        raw = b"".join((pathlib.Path(repo) / h["file"]).read_bytes().splitlines(keepends=True)[h["start"] - 1:h["end"]])
        out.append({**h, "text": raw.decode("utf-8", "replace"), "sha256": hashlib.sha256(raw).hexdigest()})
    return out


def take(place, repo, reply) -> dict:
    """返り {ok, reason}。拒めば何も書かない"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    if not isinstance(reply, dict):
        return {"ok": False, "reason": "返答が JSON のオブジェクトでない"}
    posted = check_no_post(reply)
    if posted:
        return {"ok": False, "reason": NO_POST + ", ".join(posted)}
    try:
        moved = core_accept.moved_since(place, repo, core_accept.TREE_KEYS)
    except Reject as e:
        return {"ok": False, "reason": str(e)}
    if moved:
        return {"ok": False, "reason": "読むだけの役が作業ツリーを変えた: 並行 PR の任せ先は読むだけの役で、作業ツリー・HEAD・枝・"
                "git が無視するファイルを変えてはいけない（checkout・switch・stash・reset・gh pr checkout を打つな）（"
                + "・".join(moved) + "）"}
    head = json.loads((place / files.TREE).read_text(encoding="utf-8"))["head"]
    material = reply.get("material")
    errs = (["素材 'parallel_pr' が object でない"] if not isinstance(material, dict)
            else materialkit.check_record(files.ROLE, ("parallel_pr",), {"parallel_pr": material}, "never"))
    if errs:
        return {"ok": False, "reason": "素材の欄が記録の決まりに合わない: " + "; ".join(errs)}
    errs = check_excluded(reply, repo)
    if errs:
        return {"ok": False, "reason": "外す hunk（excluded）が合わない: " + "; ".join(errs)}
    excluded = anchored(reply[EXCLUDED_FIELD], repo)
    bare = {k: v for k, v in reply.items() if k != EXCLUDED_FIELD}
    jsonfile.write(place / files.EXCLUDED, {"node": files.NODE, "head": head, "excluded": excluded})
    jsonfile.write(place / files.DRAFTS, drafts(bare))
    jsonfile.write(place / files.MATERIAL, {"role": files.ROLE, "reply": bare, "materials": {"parallel_pr": bare["material"]}})
    return {"ok": True, "reason": ""}


def accept(place, repo, raw) -> dict:
    """輪の 1 回の受け付け。返り {ok, done, reason}"""
    return rolekit.accept_round(pathlib.Path(place), files.ROLE, raw, lambda reply: take(place, repo, reply))
