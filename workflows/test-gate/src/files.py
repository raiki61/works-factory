"""place のファイルの名と、place の中の自分のファイルだけを作り直す口（docs/design/test-gate.md の 1.4）。

名はこのモジュールだけが持つ（ほかの block が読む物は出力の欄の pointer で渡す）。place は単独の run では run directory の根なので、
消すのはここに名の在るファイルとフォルダだけ。名で引き、広い形（`*.json` など）で消さない。

- INTAKE: port を読んだ値。SUITE_STATE: TDD の実行器の控え（lib/suitewrite が start_file として読み書く）
- RUN: 走らせた結果（lib/declared_checks.RUN_FILE）。LOGS/a<k>/: 走りごとのログ。JUNIT/: 宣言の段の JUnit の報告
- IMPACT/: 関わる試験の選びの地図の控え（lib/related.pick の cache_dir）
- SUITE/: 実行器（runner）と書き手の材料の文。SUITE_LOGS: 実行器を走らせたログと JUnit XML
- BASELINE（base だけ）・EVIDENCE・FAILURE（証拠の文が書けない時だけ）
"""
from __future__ import annotations

import json
import pathlib
import shutil

# lib/ のモジュールは関数の中で読む（返す node の failed は lib が読めなくても名を引けるように、名の定数は lib を import せずに持つ）

MODES = ("base", "final")   # lib/declared_checks.MODES と同じ（試験が突き合わせる）
INTAKE = "intake.json"
SUITE_STATE = "suite-state.json"
RUN = "run.json"   # lib/declared_checks.RUN_FILE と同じ字（試験が突き合わせる）
LOGS = "logs"
JUNIT = "junit"
IMPACT = "impact"
SUITE = "suite"
SUITE_LOGS = ("suite-suite.log", "suite-suite-again.log", "junit-suite.xml")
BASELINE = "baseline.json"
OUTCOMES = "test-outcomes.json"
EVIDENCE = "evidence.md"
FAILURE = "failure.txt"
PROMPT_GLOBS = ("suite-write-prompt-*.md",)


def own_files(place) -> list[pathlib.Path]:
    """place の中のこの block のファイルとフォルダ（logs/ は含めない。走りごとのログは上書きせず残す）"""
    place = pathlib.Path(place)
    names = [INTAKE, SUITE_STATE, RUN, JUNIT, IMPACT, SUITE, *SUITE_LOGS, BASELINE, OUTCOMES, EVIDENCE, FAILURE]
    found = [place / name for name in names]
    for pattern in PROMPT_GLOBS:
        found += place.glob(pattern)
    return found


def fresh_place(place) -> None:
    """同じ run で同じ形をもう 1 度差し込んだ時に、前の回の素材・拒否・記録を読まないよう、この block のファイルを消す"""
    for path in own_files(place):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def log_dir(place) -> pathlib.Path:
    """今回のログの置き場 logs/a<k>/（k は空いた最初の番号。前の走りのログを上書きしない）"""
    place = pathlib.Path(place)
    place.mkdir(parents=True, exist_ok=True)
    k = 1
    while (place / LOGS / f"a{k}").exists():
        k += 1
    return place / LOGS / f"a{k}"


def suite_folder(place) -> pathlib.Path:
    return pathlib.Path(place) / SUITE


def read(place, name: str):
    return json.loads((pathlib.Path(place) / name).read_text(encoding="utf-8"))


def intake(place) -> dict:
    """intake.json の値。port が読めなかった回の intake が書いた failed があれば、その訳を ValueError で上げる（返す node の failed が
    証拠に名指す。後ろの node は port を読まずにここから読む）"""
    doc = read(place, INTAKE)
    if doc.get("failed"):
        raise ValueError(doc["failed"])
    return doc


NOT_PICKED = {"applied": False, "whole": False, "files": [], "left": [], "far": [], "reasons": [], "ran": "none"}


def related_record(picked, ran) -> dict:
    """run.json の related: 関わる試験の選び（lib/related.pick）と、走らせたか ran（related: 選んだ試験だけ・whole: 一式・none: 走らせていない）。
    絞らない道（by が role_needed でない）は applied が偽。ran は実行器を走らせた回（run・suite-try）が決める"""
    if picked is None:
        return {**NOT_PICKED, "ran": "whole" if ran else "none"}
    how = "none" if ran is None else ("whole" if picked["whole"] else "related")
    return {"applied": True, **picked, "ran": how}
