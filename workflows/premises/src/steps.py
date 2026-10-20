"""前提の実測の block の中身（docs/design/premises.md。lib/judge_accept.py の前提の部分〔check_claims・measured_needs_output・
with_carried・check_premises・作業ツリーの比べ〕と lib/premises.py の claims を、port の値で受ける形に写した物）。

依頼の行を port で受け、実測役に作業ツリーで主張を測り直させる。役は作業ツリーを変えない約束で、受け付けは役を起こす前に取った
作業ツリーの写しと今を比べる。受けた返答に、前の run が運んだ実測を足して premises.json に書く。指示の文は prompts/premises.md が持ち、
ここは材料と値だけを組む。

place のファイル（名はこのモジュールだけが持つ。premises.md の 1.4）:
- intake.json: {findings, carried, lang, failed, reason}
- tree.json: 役を起こす前の作業ツリーの写し（accept.tree_state の形）
- premises-prompt-<n>.md（prompt.emit が書く）・rejects-premises.json（lib/rolekit の accept_round が積む拒否の控え）
- premises.json: {constraints: [...]}（受けた返答に運ばれた実測を足した物）
"""
from __future__ import annotations

import json
import pathlib

import ports
import prompt
import requestrows

import accept     # lib/。作業ツリーの写しと比べ・guard・in_repo
import jsonfile   # lib/
import oneline    # lib/
import rolekit    # lib/。loop の数え・却下の控え・諦め
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import report

INTAKE_FILE = "intake.json"
TREE_FILE = "tree.json"
PREMISES_FILE = "premises.json"
ROLE = "premises"         # 却下の控えの名（rejects-premises.json）
NODE = "premises"         # AI の node の id（prompts/premises.md）
MEASURED = "実測"          # 制約の行の kind。役の output_format の enum の並び (MEASURED, HYPOTHESIS)
HYPOTHESIS = "仮説"
PREMISES_RULE = "実測役は作業ツリーを変えてはいけない"
NOT_TAKEN = "前提の実測を受け付けた控えが無い（役が走らなかったか落ちた）"
REPORT_HEAD = "前提の制約: "
OWN_FILES = (INTAKE_FILE, TREE_FILE, PREMISES_FILE, rolekit.rejects_path(pathlib.Path(), ROLE).name)
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
def claims(findings: list) -> list:
    """依頼の行のうち measured（依頼者が測ったと書いた値）を持つ物の {where, measured}。役はこの where を text にそのまま入れて測り直す"""
    return [{"where": f["where"], "measured": f["measured"]} for f in findings or []
            if isinstance(f, dict) and isinstance(f.get("where"), str) and f.get("measured") not in (None, "")]


def _rows(value) -> list:
    """port carried の値（行の配列か {constraints: [...]}）の行。運ばれた行は前の run の検算の実測で measured_output を持たない
    （carry.carried_constraints）ので、実測の行の出力は照らさない——出力を求めるのは役の返答の受け付けだけ"""
    return list(value.get("constraints") if isinstance(value, dict) else value)


def intake(out, *, request, carried, lang) -> dict:
    """port を読み、この block のファイルを消して intake.json と作業ツリーの写し tree.json を書く。返り {due, reason}。落ちた時は
    intake.json に failed と訳を書き、due は偽"""
    out = pathlib.Path(out)
    doc = {"findings": [], "carried": [], "lang": "", "failed": False, "reason": ""}
    try:
        got = _port("request", lambda: requestrows.parts(request))   # 形・知らない鍵・下書きの行の拒み
        doc["findings"] = got["findings"]
        doc["carried"] = _port("carried", lambda: _rows(ports.json(carried, "shared:constraints.schema.json"))) or got["constraints"]
        doc["lang"] = ports.text(lang).strip()
        for name in OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        jsonfile.write(out / INTAKE_FILE, doc)
        jsonfile.write(out / TREE_FILE, accept.tree_state(pathlib.Path.cwd()))
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        reason = oneline.one_line(f"前提の実測の支度が落ちた（{type(e).__name__}: {e}）")
        jsonfile.write(out / INTAKE_FILE, {"findings": [], "carried": [], "lang": "", "failed": True, "reason": reason})
        return {"due": False, "reason": reason}
    return {"due": True, "reason": ""}


# ---------------------------------------------------------------- 指示
def premises_prompt(out) -> dict:
    """実測役の指示を組んで place に書く。前の回までの却下は place の控えから全部。返り {prompt}"""
    out = pathlib.Path(out)
    doc = _need(out, INTAKE_FILE)
    rejected = rolekit.rejected(out, ROLE)
    values = {"rejection": rolekit.rejects_text(rejected),
              "request": json.dumps(doc["findings"], ensure_ascii=False, indent=1),
              "measured": MEASURED, "hypothesis": HYPOTHESIS, "lang": prompt.lang(doc["lang"])}
    when = {"rejected": bool(rejected), "spawns": False}
    return prompt.emit(NODE, values, when, prompt.round_of(NODE))


# ---------------------------------------------------------------- 受け付け
def check_claims(reply, findings: list) -> list:
    """依頼の実測（measured を持つ行）のうち、where を text にそのまま含む制約が返答に無い物の where の一覧（空なら通る）。
    測り直せずに仮説へ落とした制約も、where を text に含めば通る"""
    rows = reply.get("constraints") if isinstance(reply, dict) else None
    texts = [c["text"] for c in rows if isinstance(c, dict) and isinstance(c.get("text"), str)] if isinstance(rows, list) else []
    return [c["where"] for c in claims(findings) if not any(c["where"] in t for t in texts)]


def measured_needs_output(reply) -> None:
    """kind=実測 の制約は、実行したコマンドと出力（measured_output）を持て。『実測』の札だけが検算なしで信頼値に昇格し、誤った事実が
    ゼロベースで疑う役に所与として渡る（実測 2026-09-12: 『CI の定義はリポジトリに無い』が実測として凍結されたが、
    .github/workflows/test.yml は実在した）。再現の形を持たないものは仮説へ落とさせる"""
    bad = [str(c.get("text"))[:60] for c in reply.get("constraints") or []
           if c.get("kind") == MEASURED and not str(c.get("measured_output") or "").strip()]
    if bad:
        raise Reject(f"p0.premises: kind={MEASURED} なのに measured_output（実行したコマンドと出力）が無い制約がある: {bad}")


def with_carried(reply: dict, carried: list) -> dict:
    """返答の制約に、運ばれた実測（前の run の前提の検算の実測）を足した物。返答に同じ text の行が在れば足さない（2 度足さない）"""
    have = {c.get("text") for c in reply.get("constraints") or [] if isinstance(c, dict)}
    return {**reply, "constraints": [*(reply.get("constraints") or []), *(c for c in carried if c.get("text") not in have)]}


def _tree_unchanged(out, repo) -> None:
    """役が作業ツリーと履歴を変えていないか。置き場の写し tree.json と今を比べる（TREE_KEYS の全部。HEAD・枝・git が無視するパスも
    見る）。写しが無い・読めない・違えば Reject"""
    moved = accept.moved_since(out, repo, accept.TREE_KEYS)   # out の tree.json（TREE_FILE）と比べる。無ければ Reject
    if moved:
        raise Reject(f"役を起こした後から作業ツリーが変わった——{PREMISES_RULE}（HEAD・枝・git が無視するファイルも）（{'・'.join(moved)}）")


def check(reply, out, repo, findings: list, carried: list) -> dict:
    """実測役の返答を受け付ける。依頼の実測を測り直したか → 作業ツリーが変わっていないか → 実測の行が出力を持つか。通れば
    premises.json に運ばれた実測を足した返答を書く。返り {ok, reason}"""
    def run():
        missing = check_claims(reply, findings)
        if missing:
            raise Reject(f"依頼の実測を測り直した制約が無い: {'・'.join(missing)}")
        repo_p = pathlib.Path(repo)
        with accept.in_repo(repo_p):
            _tree_unchanged(out, repo_p)
        measured_needs_output(reply)
        jsonfile.write(pathlib.Path(out) / PREMISES_FILE, with_carried(reply, carried))
        return {"ok": True, "reason": ""}
    return accept.guard(run)


def take(out, raw, repo) -> dict:
    """受け付けの輪の 1 回（rolekit.accept_round）。返り {ok, done, reason}。3 回目の拒否で done（run は止めない）"""
    doc = _need(out, INTAKE_FILE)
    got = rolekit.accept_round(out, ROLE, raw, lambda reply: check(reply, out, repo, doc["findings"], doc["carried"]))
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}


# ---------------------------------------------------------------- 出口
def failed(reason: str) -> dict:
    return {"ok": False, "status": "failed", "reason": reason, "constraints": None, "report": [REPORT_HEAD + reason]}


def _why_failed(out) -> str:
    """輪が通らなかった訳（諦めた文か、落ちた周の最後の拒否の文。拒否も無ければ役が走らなかった）"""
    rejected = rolekit.rejected(out, ROLE)
    return rolekit.given_up_reason(out, ROLE) or (rejected[-1] if rejected else NOT_TAKEN)


def finish(out) -> dict:
    """block の返り {ok, status, reason, constraints, report}。落ちた段が在っても落ちない"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / INTAKE_FILE)
    if not isinstance(doc, dict):
        return failed("入口の控えが無い（入口の node が落ちた）")
    if doc.get("failed"):
        return failed(str(doc.get("reason") or "入口が落ちた"))
    got = jsonfile.read_or(out / PREMISES_FILE)
    if not isinstance(got, dict):
        return failed(_why_failed(out))
    rows = [c for c in got.get("constraints") or [] if isinstance(c, dict)]
    return {"ok": True, "status": "ok", "reason": "", "constraints": ports.pointer(out / PREMISES_FILE),
            "report": report.lines(doc.get("findings"), rows, HYPOTHESIS)}
