"""始めの記録から block に配る値を引く（docs/design/line.md の 1.6。start の出力の欄 ports）。

block は始めの記録を読まない（README 4.2・4.3）。line の start が書いた記録（固定材料の run は src.fixture.adopt が書き換えた記録）
から、同じ式でここが値を引き、node は `$start.output.ports.<名>` で読む。値の源を 1 つにする（node ごとに記録を開いて引き直すと、続きの
run で値が黙って変わった 8dfebca6 の形が戻る）。

- ports_of(record, artifacts) -> dict: 配る値の 34 欄（欄と式は line.md の 1.6。YAML の start の output_format の ports と同じ並び）
- empty() -> dict: 拒んだ run・落ちた run の ports（全部の欄を空の値: 字は ""・flag は false・object は {}・配列は []・request と
  carried は "[]"。後ろは when: で飛ぶ）
- pr_text(pr) -> str: PR の番号・題・本文を並べた文（元 lib/judge_accept.py の pr_file_text の字。PR の無い run は ""）
- entry_origin(record) -> str: 判定から入る run の出どころの文（入口の差分が空で依頼の行が 1 件以上の時だけ。元 judge_accept.due_view の
  record.process.request_entry.origin と同じ字）
- thickness_word(word) -> str: 入力 thickness の語 → head-depth の port thickness の語（空・自動 → auto、軽量 → light、標準 → standard、
  重厚 → heavy）

empty は標準ライブラリだけで組む（start の fallback が lib を読めない時も引く）。ほかの口は lib と src を関数の中で読む。
"""
from __future__ import annotations

import pathlib

AUTO = "自動"
NO_REQUEST = "[]"
# 元 lib/judge_accept.py の PR_TITLE・PR_SUBJECT_HEAD・PR_BODY_HEAD（元 entryshape.write_pr_file の見出し）
PR_TITLE = "# PR #{number}"
PR_SUBJECT_HEAD = "## 題"
PR_BODY_HEAD = "## 本文"
REVIEW_TREE = "review_tree"
JUDGE_VERIFY = "judge_verify"
LANES = ("fix_lanes", "tdd_lanes")
NAMES = ("request", "request_file", "pr_text", "carried", "carried_measured", "base", "base_rev", "request_origin", "base_label",
         "review_rev", "entry", "lang", "web", "world", "spec", "has_checks", "thickness", "forced", "design_only", "unattended", "policy",
         "test_cmd", "tdd_suite", "reuse_dir", "user_env_dir", "run_id", "deliver", "parallel", "verify_by_tier", "tree_named",
         "takes_push", "request_scope", "prior_rows", "request_answers")
FLAGS = ("carried_measured", "world", "spec", "has_checks", "design_only", "unattended", "parallel", "takes_push", "request_scope")


def empty() -> dict:
    out = {name: "" for name in NAMES}
    out.update({name: False for name in FLAGS})
    out.update({"request": NO_REQUEST, "carried": NO_REQUEST, "verify_by_tier": {}, "prior_rows": [], "request_answers": []})
    return out


def thickness_word(word: str) -> str:
    from src import tiers

    return {tiers.LIGHT: "light", tiers.STANDARD: "standard", tiers.HEAVY: "heavy"}.get(word, "auto")


def pr_text(pr) -> str:
    if not pr:
        return ""
    return (f"{PR_TITLE.format(number=pr.get('number'))}\n\n{PR_SUBJECT_HEAD}\n\n{pr.get('title') or '（空）'}\n\n"
            f"{PR_BODY_HEAD}\n\n{pr.get('body') or '（空）'}\n")


def entry_origin(record: dict) -> str:
    from src import startrec

    reqs = startrec.requests(record)
    if startrec.diff_empty(record) is True and isinstance(reqs, int) and reqs >= 1:
        return f"人の依頼（{startrec.request_file(record) or '依頼の行'}）"
    return ""


def _text(record: dict, key: str) -> str:
    got = record.get(key)
    return got if isinstance(got, str) else ""


def _named(record: dict, name: str) -> str:
    """features_on・features_off の name の名指しだけを読んだ語（on・off。名指しが無ければ空）"""
    import entry

    if name in (record.get(entry.FEATURES_ON_KEY) or []):
        return entry.SWITCH_ON
    if name in (record.get(entry.FEATURES_KEY) or []):
        return entry.SWITCH_OFF
    return ""


def _carried(artifacts: pathlib.Path) -> tuple:
    """carried.json の (pointer か "[]", 前の run の前提の検算が運んだ実測の行が在るか)"""
    import carry
    import jsonfile
    import ports

    from src import files

    path = artifacts / files.CARRIED
    if not path.is_file():
        return NO_REQUEST, False
    rows = jsonfile.read_or(path, [])
    measured = any(isinstance(r, dict) and str(r.get("measured_how") or "").startswith(carry.CARRIED_HOW_HEAD)
                   for r in rows if isinstance(rows, list))
    return ports.pointer(path), measured


def _prior_rows(artifacts: pathlib.Path) -> list:
    import carry
    import jsonfile

    rows = jsonfile.read_or(artifacts / carry.PRIOR_IN_FILE, [])
    return rows if isinstance(rows, list) else []


def ports_of(record: dict, artifacts) -> dict:
    import entry
    import policy
    import tree_run

    from src import gates, startrec, tiers

    artifacts = pathlib.Path(artifacts)
    request_file = startrec.request_file(record)
    origin = entry_origin(record)
    carried, measured = _carried(artifacts)
    cut = entry.cut_of(record)
    thickness = _text(record, "thickness").strip()
    shape = startrec.shape(record) or {}
    answers = record.get("answers")
    return {
        "request": request_file or NO_REQUEST,
        "request_file": request_file,
        "pr_text": pr_text(shape.get("pr")),
        "carried": carried,
        "carried_measured": measured,
        "base": startrec.diff_base(record),
        "base_rev": startrec.head_rev(record),
        "request_origin": origin or f"人の依頼（{request_file or '依頼の行'}）",
        "base_label": startrec.diff_base_label(record),
        "review_rev": startrec.read_rev(record),
        "entry": origin,
        "lang": _text(record, "lang"),
        "web": entry.SWITCH_ON,
        "world": entry.WORLD_FEATURE not in cut,
        "spec": bool(record.get("spec")),
        "has_checks": tiers.has_checks(record),
        "thickness": thickness_word(thickness),
        "forced": "" if thickness == AUTO else tiers.named(thickness),
        "design_only": bool(record.get("design_only")),
        "unattended": gates.unattended_of(record),
        "policy": policy.frozen_copy(record),
        "test_cmd": _text(record, "test_cmd"),
        "tdd_suite": _text(record, "tdd_suite"),
        "reuse_dir": str(tree_run.reuse_dir(artifacts)),
        "user_env_dir": str(artifacts),
        "run_id": _text(record, "run_id"),
        "deliver": entry.deliver_word(str((record.get("inputs") or {}).get("deliver") or "")),
        "parallel": not any(lane in cut for lane in LANES),
        "verify_by_tier": {tier: entry.switch(record, JUDGE_VERIFY, tiers.tier_adds(tier)) == entry.SWITCH_ON
                           for tier in tiers.HEADS},
        "tree_named": _named(record, REVIEW_TREE),
        "takes_push": gates.unattended_of(record),
        "request_scope": startrec.diff_empty(record) is True,
        "prior_rows": _prior_rows(artifacts),
        "request_answers": answers if isinstance(answers, list) else [],
    }

