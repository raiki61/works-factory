"""差分の審査の block の置き場のファイルの名と、往復の表（docs/design/delta-review.md の 1.4・1.5）。名の持ち主はこのモジュールだけ。

place は `ports.place()`（単独の run では run directory の直下、graph から include された時はその下の delta-review/）。入口は
このモジュールの名のファイルと指示のファイルだけを名で引いて消す（place は消さない）。
"""
import json
import pathlib

import ports

import accept  # lib/
import lens  # lib/

ROUNDS = (1, 2)
REVIEW = {1: "review-1", 2: "review-2"}   # 審査役の node の id（却下の控えの名と prompts/<id>.md）
REFIX = {1: "refix-1", 2: "refix-2"}      # 手直しの役の node の id
SKIP = (ports.RUNTIME_COPY_PREFIX,)       # 差分に数えないパスの頭（Archon の写しの置き場）
TREE_KEYS = accept.status_keys("true")    # 読むだけの役の node は mutates_checkout: false で Archon が git status を照らす。porcelain は比べから外す

INTAKE, SKIPPED, ERRORS, TRACE = "intake.json", "skipped.json", "errors.json", "trace.jsonl"
SCOPE, FIX_REPLY, PERMITS, PLAN_REVIEW, REQUEST = "scope.json", "fix-reply.json", "permits.json", "plan-review.json", "request.json"
LENS = lens.LENS_FILE   # lens.read が place から読む名
VERDICTS, HOLES, DIFF = "verdicts.json", "holes.json", "delta.diff"


def patch(n: int) -> str:
    return f"delta-{n}.patch"


def cut(n: int) -> str:
    return f"cut-{n}.json"


def review_brief(n: int) -> str:
    return f"review-{n}-brief.json"


def review_tree(n: int) -> str:
    return f"review-{n}-tree.json"


def review_reply(n: int) -> str:
    return f"review-{n}-reply.json"


def review_record(n: int) -> str:
    return f"review-{n}.json"


def refix_brief(n: int) -> str:
    return f"refix-{n}-brief.json"


def refix_head(n: int) -> str:
    return f"refix-{n}-head.json"


def refix_reply(n: int) -> str:
    return f"refix-{n}-reply.json"


def rejects(role: str) -> str:
    """却下の控えの名（lib/rolekit の rejects_path が rejects-<role>.json にする）"""
    return f"rejects-{role}.json"


OWN_FILES = (INTAKE, SKIPPED, ERRORS, TRACE, SCOPE, FIX_REPLY, PERMITS, PLAN_REVIEW, REQUEST, LENS, VERDICTS, HOLES, DIFF,
             *(f(n) for f in (patch, cut, review_brief, review_tree, review_reply, review_record, refix_brief, refix_head, refix_reply)
               for n in ROUNDS),
             *(rejects(role) for role in (*REVIEW.values(), *REFIX.values())))
OWN_PROMPTS = tuple(f"{role}-{kind}-*.md" for role in (*REVIEW.values(), *REFIX.values()) for kind in ("prompt", "system"))


def trace(place, op: str, **kw) -> None:
    """place の trace.jsonl に {"op": op, **kw} を JSON の 1 行で足す（機械の行。報告が数える）"""
    with open(pathlib.Path(place) / TRACE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": op, **kw}, ensure_ascii=False) + "\n")
