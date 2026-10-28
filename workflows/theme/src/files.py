"""theme の block の place のファイルの名と、周の番号（docs/design/theme.md の 1.3）。名はこのモジュールだけが持つ。

place の直下: current-round.json（{round}）・theme-writer-prompt-<n>.md・theme-writer-fix-prompt-<n>.md（prompt.emit）。
周のフォルダ r<k>/（k は往復の記録の往復の数 + 1）の中:

- intake.json: port を読んだ値（テーマの md と方針の写しのパス・答えの行・記録された方針の行・世界の解の行・起点の版・言語）と {due, reason}
- prior.json・prior-design.json: 往復の記録と前の周の設計の案の写し（渡された時だけ）
- rejects-theme.json・candidate-theme.json: 却下の控えと、出し直しと合わせた答えの控え（lib/rolekit が名を組む）
- design.json: 受け付けを通った設計の案
- design.md: 設計の案を人と審査役に見せる md
- crash.json: prep・accept の node が落ちた時の {step, why}
- finish.json: 出口の返答の写し

このモジュールは標準ライブラリと ports だけを import する（lib/ の import が落ちても、intake の fallback が周の番号を決められるように）。
"""
from __future__ import annotations

import json
import os
import pathlib

import ports

ROLE = "theme"                       # 却下の控えの名（rolekit.rejects_path・candidate_path）
WRITER = "theme-writer"              # 書き手の AI の node の id（prompts/theme-writer.md）
FIXER = "theme-writer-fix"           # 出し直しの役の AI の node の id（prompts/theme-writer-fix.md）
# 書き手の答えに要る根の欄。役の型は出し直しの役と同じ形にするので根の欄を要ると書かず、受け付けが rolekit.resubmitted で確かめる（#832）
REQUIRED = ("question", "purpose", "premises", "current", "parts", "reuse", "checks", "asks", "decided", "changes", "inventory", "narrows",
            "block_answers", "answers_used")
DESIGN_SCHEMA = "shared:theme-design.schema.json"
CURRENT_ROUND = "current-round.json"
INTAKE = "intake.json"
PRIOR = "prior.json"
PRIOR_DESIGN = "prior-design.json"
REJECTS = f"rejects-{ROLE}.json"     # lib/rolekit.py の rejects_path が組む名（試験が突き合わせる）
CANDIDATE = f"candidate-{ROLE}.json"  # lib/rolekit.py の candidate_path が組む名（同上）
DESIGN = "design.json"
DESIGN_MD = "design.md"
CRASH = "crash.json"
FINISH = "finish.json"
# 周を開き直した時に名で消すファイル（広い形で消さない。ほかの周のフォルダは消さない）
OWN_FILES = (INTAKE, PRIOR, PRIOR_DESIGN, REJECTS, CANDIDATE, DESIGN, DESIGN_MD, CRASH, FINISH)


def read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return default


def write_json(path, doc) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def round_dir(place, k: int) -> pathlib.Path:
    return pathlib.Path(place) / f"r{k}"


def round_no(place) -> int:
    """今の周の番号（current-round.json。無い・読めなければ 1）"""
    got = read_json(pathlib.Path(place) / CURRENT_ROUND)
    k = got.get("round") if isinstance(got, dict) else None
    return k if isinstance(k, int) and not isinstance(k, bool) and k >= 1 else 1


def folder(place) -> pathlib.Path:
    """今の周のフォルダ"""
    return round_dir(place, round_no(place))


def next_round(raw_prior) -> int:
    """port prior の値から今の周の番号（往復の記録の往復の数 + 1）。空・読めなければ 1（読めない訳は intake が拾う）"""
    if not ports.text(raw_prior).strip():
        return 1
    try:
        doc = ports.json(raw_prior, "shared:plan-converge.schema.json")
    except (ValueError, OSError):
        return 1
    return len(doc.get("passes") or []) + 1
