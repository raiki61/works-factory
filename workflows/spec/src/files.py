"""spec の block の置き場のファイルの名と、役・語の表（docs/design/spec.md の 1.4・1.5）。名はこのモジュールだけが持つ。

place のファイル:
- intake.json: {mode, go, reason, pr_text, lang}・request.json（依頼の行。write の役が Read する）
- spec-write.json・spec-review.json・spec-revise.json（受け付けた返答）・candidate-<役>.json・rejects-<役>.json（lib/rolekit が置く）
- spec-snapshot-spec.review.json（審査役の前の作業ツリーの写し）
- spec-ask.json（承認ノードに見せた仕様と文）・spec.json（固めた仕様）・added-rows.json（足した依頼の行）
- stop.json（block の中の止めの控え {stop_reason, reason}。最初に止めた node の物だけ残す）
- <node-id>-prompt-<n>.md（prompt.emit が書く）・user-env-ran（lib/userenv が置く印）
"""
from __future__ import annotations

import json
import pathlib

import ports

import jsonfile   # lib/
import rolekit    # lib/。拒否の控え・出し直しの控えの名
import stopby     # lib/
import userenv    # lib/。印の名
from engine.util import safe_name   # lib/graphloops/engine/util.py

MODES = ("write", "check")
INTAKE, REQUEST, SPEC, SPEC_ASK, ADDED_ROWS, STOP_FILE = (
    "intake.json", "request.json", "spec.json", "spec-ask.json", "added-rows.json", "stop.json")
# 役の名（with: の role）→ 受けた返答の置き場の名（<名>.json）と拒否の控えの名（rolekit.accept_round の name）・AI の node の id
ROLES = {"write": "spec-write", "review": "spec-review", "revise": "spec-revise"}
# 役の名 → 拒否の文の頭の節の名（今の字のまま）
NODES = {"write": "spec.write", "review": "spec.review", "revise": "spec.revise"}
FIX_SUFFIX = "-fix"          # 出し直しの役の node の id は <ROLES の名>-fix
# 役の名 → 答えに要る根の欄。役の型（YAML の output_format）は出し直しの役と同じ形にするので根の欄を要ると書かず、受け付けが
# rolekit.resubmitted で確かめる（#832）
REPLY_REQUIRED = {"write": ("requirements", "acceptance", "out_of_scope"), "review": ("faces", "reason"), "revise": ("spec", "handled")}
GWT = ("Given", "When", "Then")
STOP = stopby.declare("spec", "仕様のループが諦めた・固まらなかった")
GATE = "spec-gate"
APPROVE = "spec.approve"     # 承認ノードの問いの節の名（gatemarks.gate_text に渡す）
GATE_STOP_NOTE = "承認ノードで止めた"          # stop・reject に一言が無い時の理由
FLAG_BY_PREFIX = "request:"                   # 一言がこの頭なら止め札（request:spec-gate）
FACE_KINDS = ("missing", "ambiguous", "out_of_scope")   # 審査の穴の種類（output_format の enum と md の差し込み口が同じ字）
HANDLED = ("absorbed", "declared")                       # 穴への答えの語
MIN_WHY = MIN_REASON = MIN_HOW = MIN_FACES_NONE = 20     # 審査・直しの自由文の字数の下限
ORIGIN = "仕様（人が承認した受け入れ条件。テストの本文は writer が書いた）"
PROVENANCE = "【仕様の受け入れ条件——テストの本文は writer が書き、人は承認しただけ】"
NOT_RUN = "仕様の段が最後まで回らなかった"


def role_file(place, role: str) -> pathlib.Path:
    return pathlib.Path(place) / f"{ROLES[role]}.json"


def snapshot_path(place) -> pathlib.Path:
    """審査役を起こす前の作業ツリーの写し（今の specblk.snapshot_name("spec.review")）"""
    return pathlib.Path(place) / f"spec-snapshot-{safe_name(NODES['review'])}.json"


def node_id(role: str, fix: bool = False) -> str:
    return ROLES[role] + (FIX_SUFFIX if fix else "")


def own_files() -> list[str]:
    """この block が名で持つ place のファイル（入口が write の回の頭で消す。広い形で消さない）"""
    roles = [ROLES[r] for r in ROLES]
    return [INTAKE, REQUEST, SPEC, SPEC_ASK, ADDED_ROWS, STOP_FILE, snapshot_path("").name, userenv.RAN_FILE,
            *[f"{r}.json" for r in roles],
            *[rolekit.candidate_path("", r).name for r in roles],
            *[rolekit.rejects_path(pathlib.Path(), r).name for r in roles]]


def own_prompts() -> list[str]:
    return [f"{node_id(r, fix)}-prompt-*.md" for r in ROLES for fix in (False, True)]


# ---------------------------------------------------------------- 読み書き
def read(path, default=None):
    """path の JSON。無ければ default。読めない・JSON でなければ ValueError（壊れた控えを黙って空にしない）"""
    p = pathlib.Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"{p} が読めない（{type(e).__name__}: {e}）") from None


def write(path, doc) -> pathlib.Path:
    return jsonfile.write(path, doc)


def need(place, name: str):
    got = jsonfile.read_or(pathlib.Path(place) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(place) / name} が無いか読めない")
    return got


def value(raw):
    """入力の JSON の値。null・空・無い入力は None。JSON でなければ字のまま（受け付けが『JSON として読めない』と拒む）"""
    try:
        return ports.parsed(raw)
    except ValueError:
        return raw


def write_stop(place, stop_reason: str, reason: str) -> None:
    """止めの控えを置く。もう在れば書かない（最初に止めた node の理由が block の止めの理由）"""
    path = pathlib.Path(place) / STOP_FILE
    if not path.exists():
        write(path, {"stop_reason": stop_reason, "reason": reason})


def read_stop(place):
    """止めの控え {stop_reason, reason}。無い・読めない・形が違えば None"""
    got = jsonfile.read_or(pathlib.Path(place) / STOP_FILE)
    return got if isinstance(got, dict) and isinstance(got.get("stop_reason"), str) else None
