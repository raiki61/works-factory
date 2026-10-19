"""place のファイルの名と、place の中の自分のファイルだけを作り直す口（docs/design/test-gate.md の 1.4）。

名はこのモジュールだけが持つ（ほかの block が読む物は出力の欄の pointer で渡す）。place は単独の run では run directory の根なので、
消すのはここに名の在るファイルとフォルダだけ。名で引き、広い形（`*.json` など）で消さない。

- INTAKE: port を読んだ値。SUITE_STATE: TDD の実行器の控え（lib/suitewrite が start_file として読み書く）
- RUN: 走らせた結果（lib/declared_checks.RUN_FILE）。LOGS/a<k>/: 走りごとのログ。JUNIT/: 宣言の段の JUnit の報告
- SNAPSHOT・MATERIAL: 任せ先の CI の役の前の作業ツリーの姿と、受け付けを通った素材。拒否の控えと合わせた答えの控えの名は lib/rolekit が組む
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
SNAPSHOT = "ci-snapshot.json"
MATERIAL = "ci-material.json"
SUITE = "suite"
SUITE_LOGS = ("suite-suite.log", "suite-suite-again.log", "junit-suite.xml")
BASELINE = "baseline.json"
EVIDENCE = "evidence.md"
FAILURE = "failure.txt"
PROMPT_GLOBS = ("ci-prompt-*.md", "ci-fix-prompt-*.md", "suite-write-prompt-*.md")


def rejects(place) -> pathlib.Path:
    import declared_checks
    import rolekit
    return rolekit.rejects_path(pathlib.Path(place), declared_checks.CI_ROLE)


def candidate(place) -> pathlib.Path:
    import declared_checks
    import rolekit
    return rolekit.candidate_path(pathlib.Path(place), declared_checks.CI_ROLE)


def own_files(place) -> list[pathlib.Path]:
    """place の中のこの block のファイルとフォルダ（logs/ は含めない。走りごとのログは上書きせず残す）"""
    place = pathlib.Path(place)
    names = [INTAKE, SUITE_STATE, RUN, JUNIT, SNAPSHOT, MATERIAL, SUITE, *SUITE_LOGS, BASELINE, EVIDENCE, FAILURE]
    found = [place / name for name in names] + [rejects(place), candidate(place)]
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
