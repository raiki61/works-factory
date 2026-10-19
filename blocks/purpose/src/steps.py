"""目的の固定の block の中身（docs/design/purpose.md。lib/judge_accept.py の目的の部分〔refuse_if_frozen・check_purpose・
purpose_prep・作業ツリーの見張り〕と lib/worldmark.py の split_means を、port の値で受ける形に写した物）。

依頼・PR の説明・前提の実測を port で受け、依頼から前の run の判断（prior_failures）を機械で外した写しを材料にして、目的の役に
この run の元の目的を 1 文にさせる。役は読むだけで、受け付けは役を起こす前に取った作業ツリーの写しと今を比べる。依頼の解き方
（means）は目的の文から外して別のファイルに置く。目的は同じ place で 1 度固めたら書き直さない（once）。指示の文は prompts/purpose.md が
持ち、ここは材料と値だけを組む。

place のファイル（名はこのモジュールだけが持つ。purpose.md の 1.4）:
- intake.json: {request, pr_text, constraints, lang, frozen, failed, reason}（request は役に見せる依頼の写し）
- tree.json: 役を起こす前の作業ツリーの写し（accept.tree_state の形）
- purpose-prompt-<n>.md（prompt.emit が書く）・rejects-purpose.json（lib/rolekit の accept_round が積む拒否の控え）
- purpose.json・purpose-means.json: 目的の控え（受けた返答から means を外した物と、{means: [...]}）
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt
import requestrows

import accept     # lib/。作業ツリーの写しと比べ・guard・in_repo
import carry      # lib/。without_prior（前の run の判断を外す）
import jsonfile   # lib/
import oneline    # lib/
import rolekit    # lib/。loop の数え・却下の控え・諦め
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import sourcefiles

INTAKE_FILE = "intake.json"
TREE_FILE = "tree.json"
PURPOSE_FILE = "purpose.json"
MEANS_FILE = "purpose-means.json"
ROLE = "purpose"          # 却下の控えの名（rejects-purpose.json）
NODE = "purpose"          # AI の node の id（prompts/purpose.md）
MEANS = "means"           # 返答の足し欄の名
PR_SOURCE = "①PR 説明"
PLAN_SOURCE = "②計画・タスク記述"
WRITER_SOURCE = "③writer の要約"
UNKNOWN_SOURCE = "目的不明"
SOURCES = (PR_SOURCE, PLAN_SOURCE, WRITER_SOURCE, UNKNOWN_SOURCE)   # 役の output_format の source の enum の並び
MEASURED = "実測"
HYPOTHESIS = "仮説"
# 受け付けが作業ツリーの写しと比べる欄。役の node は mutates_checkout: false で、Archon が node の前後の git status を照らすので
# porcelain を外す（今の受け付けの with: {status_guarded: true} と同じ）
TREE_KEYS = accept.status_keys(True)
PURPOSE_RULE = "目的の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない"
FROZEN_REASON = "目的は既に固めてある（purpose.json）"
NOT_TAKEN = "目的の文を受け付けた控えが無い（役が走らなかったか落ちた）"
REPORT_HEAD = "目的の文: "
OWN_FILES = (INTAKE_FILE, TREE_FILE, MEANS_FILE, rolekit.rejects_path(pathlib.Path(), ROLE).name)
OWN_PROMPTS = (f"{NODE}-prompt-*.md",)


# ---------------------------------------------------------------- 置き場
def _need(out, name):
    got = jsonfile.read_or(pathlib.Path(out) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(out) / name} が無いか読めない")
    return got


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


# ---------------------------------------------------------------- 入口
def request_copy(doc):
    """役に見せる依頼の写し: 容器から前の run の判断（prior_failures）を外した物（carry.without_prior）。外す欄が無ければ doc のまま"""
    bare = carry.without_prior(doc)
    return bare if bare is not None else doc


def constraint_rows(value) -> list:
    """port constraints の値（配列か、{constraints: [...]}）の行。kind が実測の行は measured_output を持つ（形の照らしは if/then を
    持たないので、ここで確かめる。元の works の intake の check_constraints と lib/judge_accept の measured_needs_output）"""
    rows = list(value.get("constraints") if isinstance(value, dict) else value)
    bad = [str(r.get("text", ""))[:60] for r in rows if r.get("kind") == MEASURED and not str(r.get("measured_output") or "").strip()]
    if bad:
        raise ValueError(f"kind={MEASURED} なのに measured_output（実行したコマンドと出力）が無い制約がある: {bad}"
                         f"——コマンドと出力を示せないものは kind={HYPOTHESIS} にする")
    return rows


def intake(out, *, request, pr_text, constraints, lang) -> dict:
    """port の字を読み、置き場に固めた目的が在れば役を起こさない（ほかのファイルも消さない）。無ければこの block のファイルを消して
    intake.json と作業ツリーの写し tree.json を書く。返り {due, reason}。落ちた時は intake.json に failed と訳を書き、due は偽"""
    out = pathlib.Path(out)
    doc = {"request": [], "pr_text": "", "constraints": [], "lang": "", "frozen": False, "failed": False, "reason": ""}
    try:
        _port("request", lambda: requestrows.parts(request))   # 形・知らない鍵・下書きの行の拒み（役に見せる写しは字のまま）
        doc["request"] = request_copy(_port("request", lambda: ports.json(request, requestrows.SCHEMA)))
        doc["pr_text"] = ports.text(pr_text)
        doc["constraints"] = _port("constraints", lambda: constraint_rows(
            ports.json(constraints, "shared:constraints.schema.json")))
        doc["lang"] = ports.text(lang).strip()
        if (out / PURPOSE_FILE).exists():
            doc.update(frozen=True, reason=FROZEN_REASON)
            jsonfile.write(out / INTAKE_FILE, doc)
            return {"due": False, "reason": FROZEN_REASON}
        for name in OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        jsonfile.write(out / INTAKE_FILE, doc)
        jsonfile.write(out / TREE_FILE, accept.tree_state(pathlib.Path.cwd()))
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        reason = oneline.one_line(f"目的の役の支度が落ちた（{type(e).__name__}: {e}）")
        jsonfile.write(out / INTAKE_FILE, {**doc, "frozen": False, "failed": True, "reason": reason})
        return {"due": False, "reason": reason}
    return {"due": True, "reason": ""}


# ---------------------------------------------------------------- 指示
def purpose_prompt(out) -> dict:
    """目的の役の指示を組んで place に書く。前の回までの却下は place の控えから全部（README の 13 章）。返り {prompt}"""
    out = pathlib.Path(out)
    doc = _need(out, INTAKE_FILE)
    rejected = rolekit.rejected(out, ROLE)
    values = {"rejection": rolekit.rejects_text(rejected),
              "request": json.dumps(doc["request"], ensure_ascii=False, indent=1),
              "pr_text": doc["pr_text"],
              "constraints": json.dumps(doc["constraints"] or [], ensure_ascii=False, indent=1),
              "pr_source": PR_SOURCE, "plan_source": PLAN_SOURCE, "writer_source": WRITER_SOURCE,
              "unknown_source": UNKNOWN_SOURCE, "measured": MEASURED, "hypothesis": HYPOTHESIS,
              "lang": prompt.lang(doc["lang"])}
    when = {"rejected": bool(rejected), "pr": bool(doc["pr_text"].strip()), "spawns": False}
    return prompt.emit(NODE, values, when, prompt.round_of(NODE))


# ---------------------------------------------------------------- 受け付け
def split_means(reply) -> tuple:
    """（足し欄 means を外した返答の写し, 依頼の解き方の並び。空白だけでない字だけ。欄が無ければ []）。dict でない返答はそのまま"""
    if not isinstance(reply, dict):
        return reply, []
    out = {k: v for k, v in reply.items() if k != MEANS}
    got = reply.get(MEANS)
    return out, [m for m in got if isinstance(m, str) and m.strip()] if isinstance(got, list) else []


def refuse_if_frozen(out) -> None:
    """置き場に目的の文が既に在れば Reject。目的は最初の修正の前に 1 度だけ固め、以降変えない（事前登録。後から書き直せると、実装に
    合わせて目的を狭める道が開く）"""
    p = pathlib.Path(out) / PURPOSE_FILE
    if p.exists():
        raise Reject(f"置き場に目的の文 {PURPOSE_FILE} が既に在る（{p}）——目的は最初の修正の前に 1 度だけ固め、"
                     "以降は変えない（graph の p0.purpose の once）")


def _tree_snapshot(path):
    """置き場に置いた作業ツリーの写し（accept.tree_state の形）。無ければ None、読めない・形が違えば Reject"""
    path = pathlib.Path(path)
    if not path.is_file():
        return None
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Reject(f"作業ツリーの写し {path} が読めない（{e}）") from None
    accept.type_errors(snap, accept.TREE_SCHEMA, f"作業ツリーの写し {path} ")
    return {k: snap[k] for k in accept.TREE_KEYS}


def _tree_unchanged(out, repo) -> None:
    """役が作業ツリーと履歴を変えていないか。置き場の写し tree.json と今を比べる（TREE_KEYS の欄。HEAD・枝・git が無視するパスも
    見る）。写しが無い・読めない・違えば Reject"""
    path = pathlib.Path(out) / TREE_FILE
    snap = _tree_snapshot(path)
    if snap is None:
        raise Reject(f"作業ツリーの写し {path} が無い——役を起こす前の作業ツリーと比べられない（写しを置くノードが先に走る）")
    moved = accept.tree_moved(snap, pathlib.Path(repo), keys=TREE_KEYS)
    if moved:
        raise Reject(f"役を起こした後から作業ツリーが変わった——{PURPOSE_RULE}（HEAD・枝・git が無視するファイルも）。作った物"
                     "（出力のファイル・キャッシュ）は rm で消し、書き換えた追跡中のファイルは git restore -- <path> で戻してから"
                     f"出し直せ（出力は $TMPDIR に置く）（{'・'.join(moved)}）")


def check(reply, out, repo) -> dict:
    """目的の役の返答を受け付ける。凍結（once）→ 作業ツリー（役は読むだけ）→ 足し欄 means を外す → source_files。通れば
    purpose.json に means を外した返答を、purpose-means.json に {means: [...]} を書く（並びが空でも書く）。返り {ok, reason}"""
    def run():
        repo_p = pathlib.Path(repo)
        with accept.in_repo(repo_p):
            refuse_if_frozen(out)
            _tree_unchanged(out, repo_p)
            got, means = split_means(reply)
            bad = sourcefiles.errors(got["source_files"], repo_p)
            if bad:
                raise Reject(f"source_files に作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る: {bad}"
                             "——出典にしたリポジトリの中のファイルを、作業ツリーの根からの相対（サブディレクトリで回していても根から・"
                             "`./` や末尾の `/`・重ねた `/`・`.` や `..` の段・symlink 経由なし・大小文字もリポジトリのまま）で書け"
                             "（依頼のファイルなどリポジトリの外の物・git が無視するファイルは書かない）")
        jsonfile.write(pathlib.Path(out) / PURPOSE_FILE, got)
        jsonfile.write(pathlib.Path(out) / MEANS_FILE, {MEANS: means})
        return {"ok": True, "reason": ""}
    return accept.guard(run)


def take(out, raw, repo) -> dict:
    """受け付けの輪の 1 回（rolekit.accept_round）。返り {ok, done, reason}。3 回目の拒否で done（run は止めない）"""
    got = rolekit.accept_round(out, ROLE, raw, lambda reply: check(reply, out, repo))
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


# ---------------------------------------------------------------- 出口
def _why_failed(out) -> str:
    """輪が通らなかった訳（諦めた文か、落ちた周の最後の拒否の文。拒否も無ければ役が走らなかった）"""
    rejected = rolekit.rejected(out, ROLE)
    return rolekit.given_up_reason(out, ROLE) or (rejected[-1] if rejected else NOT_TAKEN)


def failed(reason: str) -> dict:
    return {"ok": False, "status": "failed", "reason": reason, "purpose": None, "purpose_text": "", "source": "", "means": [],
            "report": [REPORT_HEAD + reason]}


def finish(out) -> dict:
    """block の返り {ok, status, reason, purpose, purpose_text, source, means, report}。落ちた段が在っても落ちない"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / INTAKE_FILE)
    if not isinstance(doc, dict):
        return failed("入口の控えが無い（入口の node が落ちた）")
    if doc.get("failed"):
        return failed(str(doc.get("reason") or "入口が落ちた"))
    got = jsonfile.read_or(out / PURPOSE_FILE)
    if not isinstance(got, dict):
        return failed(_why_failed(out))
    means = (jsonfile.read_or(out / MEANS_FILE) or {}).get(MEANS) or []
    return {"ok": True, "status": "ok", "reason": FROZEN_REASON if doc.get("frozen") else "",
            "purpose": ports.pointer(out / PURPOSE_FILE), "purpose_text": str(got.get("purpose_text") or ""),
            "source": str(got.get("source") or ""), "means": [str(m) for m in means], "report": []}
