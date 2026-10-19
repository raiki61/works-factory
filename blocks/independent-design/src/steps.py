"""独立設計の block の中身（docs/design/independent-design.md。lib/boardview.py の独立設計の部分と lib/design.py の呼び方を、port の値で
受ける形に写した物）。

目的の文・実測した制約・人が決めた前提・人の方針だけから、道具を持たない役に理想の設計を作らせる。役は修正案・判定・差分を見ない
（port がそれらを運ばない）。受け付けは役を起こす前に取った作業ツリーの姿と今を比べ、問いが立たない根拠の名指しが固めた版に在るか、
問いが立つ設計が要素を持つかを確かめる。指示の文は prompts/design.md と prompts/design.system.md が持ち、ここは材料と値だけを組む。
"""
from __future__ import annotations

import json
import pathlib
import types

import ports
import prompt

import accept    # lib/。作業ツリーの姿・guard・write_board
import cite      # lib/。依頼の名指しを引く Markdown の読み（MD_LINK・_md_lines・_md_slugs。integration.md 4.5-5）
import design    # lib/。名指し・根拠の検算・要素の照らし
import jsonfile  # lib/
import oneline   # lib/
import policy    # lib/。PASTE_CAP
import rolekit   # lib/。loop の数え・却下の控え・諦め
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import files, marks, premises, report

HYPOTHESIS = "仮説"          # 制約の kind の語（正本は前提の実測の block の出力の形。md には {hypothesis} で入れる）
UNKNOWN_SOURCE = "目的不明"   # 目的の出典の語（目的の固定の block の出力 source）
NARROWS = "狭めている"        # 目的の監査の verdict の語
START_GATE_NODE = "始めの承認ノード"   # 承認ノードの答えの行の札（lib の語）
PREMISE_MISS = "premise_invalid_reason の名指しが固めた版の実物に当たらない（追跡されたファイルと、その行の範囲を名指せ）: "
ELEMENTS_REJECT = "問いが立つ設計の elements に誤りが在る（設計の要素を 1 つ以上、id の重ならない {id, adds, removes} の行で並べる。下の行を直した返答を丸ごと出し直せ）: "
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "
NO_TREE = "役を起こす前の作業ツリーの控え {name} が無い（支度のノードが走っていない）"
STALE_WHY = "裏取りを通っていない形の findings（旧形の素の文字列、または cite 無し）に乗った『狭めている』なので、R2 を止める根拠には使わない"
PURPOSE_REVIEW_UNREAD = ("入力 purpose_review の先（目的の監査の受けた返答）を読めない（{why}）——監査は無かったとして読み、"
                         "独立設計を目的の『狭めている』では止めない")
REQUEST_UNREAD = "依頼のファイル {path} を読めない（{why}）——依頼の本文は空として読み、依頼が名指した設計書のセクションは渡っていない"
NO_ANSWERS = "承認ノードの答えが無い——独立設計に貼る人の答えは無い"
NO_CONSTRAINTS = "実測した制約が渡されていない（port constraints が空）"
# 実測した制約のうち、審査する変更が足した行を名指す物に機械が付ける欄 mark の字（prompts/design.md がこの字で読む）
ADDED_MARK = "（審査する変更 {base}..{head} が足した行: {where}）"
NOT_RUN = "役の loop が回らなかった"
CRASHED = "{step} の node が落ちた（{why}）"


# ---------------------------------------------------------------- 人が決めた前提の見え方
def answer_rows(answers) -> list:
    """port answers の値（{decision, text} か、その配列。null は無い）のうち、decision を持つ行"""
    rows = answers if isinstance(answers, list) else [answers] if isinstance(answers, dict) else []
    return [a for a in rows if isinstance(a, dict) and a.get("decision")]


def human_items(answers) -> list:
    """承認ノードの答えを design.human_answers が読む行 {round, node, kinds, answer, note} に"""
    return [{"round": 1, "node": START_GATE_NODE, "kinds": [], "answer": a["decision"], "note": a.get("text") or ""}
            for a in answer_rows(answers)]


def r2_view(request: str, answers) -> types.SimpleNamespace:
    """独立設計の前提を組むだけの見え方（承認ノードの答え・依頼の本文・名指しを引く道具だけ。修正案・判定・差分は持たない）"""
    rules = types.SimpleNamespace(MD_LINK=cite.MD_LINK, _md_lines=cite._md_lines, _md_slugs=cite._md_slugs)
    return types.SimpleNamespace(record={"process": {"human_items": human_items(answers)}},
                                 state={"inputs": {"request": request}}, rules=rules)


# ---------------------------------------------------------------- 目的の使えるか・裏取り
def _vetted(review: dict) -> bool:
    """目的の監査の findings が裏取りの柵を通った形（全部 cite を持つ。空は偽）か"""
    rows = review.get("findings") or []
    return all(isinstance(r, dict) and r.get("cite") for r in rows) if rows else False


def stale_purpose_review(review: dict) -> list:
    """裏取りを通っていない『狭めている』の判定の行（独立設計は 1 度だけ走るので周は 1）"""
    if review.get("verdict") == NARROWS and not _vetted(review):
        return [{"round": 1, "why": STALE_WHY}]
    return []


def unusable(source: str, review: dict):
    """目的の出典が独立設計に使えない理由の語（目的不明／狭めている）。使えれば None"""
    if source == UNKNOWN_SOURCE:
        return UNKNOWN_SOURCE
    return NARROWS if review.get("verdict") == NARROWS and _vetted(review) else None


# ---------------------------------------------------------------- 足した行の印
def added_marks(constraints: list, repo, base: str, head: str) -> list:
    """実測した制約のうち、text・measured_output が名指す <パス>:<行>（design.anchors）が審査する変更（起点 base → 修正前の
    HEAD head。marks.pr_added_lines）の足した行に当たる物に欄 mark（ADDED_MARK）を付けた並び。独立設計は変更の後の作業ツリーから
    測った制約を受けるので、印が無いと変更そのものを既存の仕組みと読む。base が空の run と差分を測れない時は付けない"""
    if not base:
        return constraints
    try:
        base_sha, head_sha = marks.pr_revs(repo, base, head or "HEAD")
        added = marks.pr_added_lines(repo, base_sha, head_sha) if base_sha != head_sha else {}
    except marks.MarkError:
        return constraints

    def hit(path: str, start: int, end: int) -> bool:
        try:
            rel = design.head_file(repo, path)
        except ValueError:
            return False
        return bool(added.get(rel, set()).intersection(range(start, end + 1)))

    out = []
    for c in constraints:
        where = list(dict.fromkeys(
            f"{path}:{start}" + (f"-{end}" if end != start else "")
            for key in ("text", "measured_output")
            for path, start, end in design.anchors(c.get(key) if isinstance(c, dict) else None, output=key == "measured_output")
            if hit(path, start, end)))
        out.append({**c, "mark": ADDED_MARK.format(base=base_sha[:12], head=head_sha[:12], where="、".join(where))} if where else c)
    return out


# ---------------------------------------------------------------- 方針
def policy_body(path) -> str:
    """方針の文書の本文。policy.PASTE_CAP バイトまで。超えたら先頭を切り、続きの置き場を末尾に書く（切った後の全体が上限の内）"""
    data = pathlib.Path(path).read_bytes()
    if len(data) <= policy.PASTE_CAP:
        return data.decode("utf-8", "replace")
    note = f"\n\n［方針の文書は {len(data)} バイトで、{policy.PASTE_CAP} バイトまでを貼った。続きは {path}］\n"
    room = policy.PASTE_CAP - len(note.encode("utf-8"))
    return data[:room].decode("utf-8", "ignore") + note


# ---------------------------------------------------------------- 入口
def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {e}") from None


def _blank(raw) -> bool:
    return not ports.text(raw).strip() or ports.text(raw).strip() == "null"


def _constraint_rows(value) -> list:
    """port constraints の値（配列か、{constraints: [...]}）の行"""
    rows = value.get("constraints") if isinstance(value, dict) else value
    return list(rows or [])


def _purpose_review(raw) -> tuple[dict, list]:
    """(目的の監査の受けた返答, 控えの withheld に足す行)。空は監査が無い。読めない時は落ちず、{} と訳の行（黙って空にしない）"""
    if _blank(raw):
        return {}, []
    try:
        return ports.json(raw, "purpose-review.schema.json"), []
    except ValueError as e:
        why = oneline.one_line(str(e)) or type(e).__name__
        return {}, [{"kind": "purpose_review", "what": "purpose_review", "why": PURPOSE_REVIEW_UNREAD.format(why=why)}]


def _request(raw) -> tuple[str, str, str]:
    """(依頼のファイルのパス, 読めない訳の行, 渡された字のままのパス)。空は依頼のファイルが無い（全部空）。在らない・読めない
    ファイルはパスを空にして本文を空として読み、訳を行に残す（名指しの節は渡っていない）。字のままのパスは控えの名指しに使う"""
    if _blank(raw):
        return "", "", ""
    given = ports.text(raw).strip()[:200]
    try:
        path = ports.file(raw)
        if path is not None:
            path.read_text(encoding="utf-8")
    except (ValueError, OSError, UnicodeDecodeError) as e:
        return "", REQUEST_UNREAD.format(path=given, why=type(e).__name__), given
    return (str(path) if path is not None else ""), "", given


def intake(out, *, purpose, purpose_source, purpose_review, constraints, answers, request, policy_file, base, head, lang) -> dict:
    """port を読み、この block のファイルを名で消して intake.json を書き、役を起こすかを決める。返り {due, status, reason}。
    目的が使えない（出典が目的不明・裏取りを通った狭めている）時は due: false・status: unusable。読めない port は due: false・
    status: failed と訳（purpose_review と依頼のファイルだけは落ちずに控えに名指す）。落ちない"""
    out = pathlib.Path(out)
    doc = {"purpose": "", "purpose_source": "", "purpose_review": {}, "constraints": [], "answers": [], "request": "", "request_unread": "", "request_given": "",
           "policy": "", "base": "", "head": "", "lang": "", "withheld": [], "due": False, "status": "failed", "reason": ""}
    try:
        for name in files.OWN_FILES:
            (out / name).unlink(missing_ok=True)
        for pattern in files.OWN_PROMPTS:
            for path in out.glob(pattern):
                path.unlink()
        doc["purpose"] = ports.text(purpose)
        if not doc["purpose"].strip():
            raise ValueError("入力 purpose: 目的の文が空")
        doc["purpose_source"] = ports.text(purpose_source).strip()
        doc["purpose_review"], doc["withheld"] = _purpose_review(purpose_review)
        doc["constraints"] = [] if _blank(constraints) else _port("constraints", lambda: _constraint_rows(
            ports.json(constraints, "shared:constraints.schema.json")))
        doc["answers"] = [] if _blank(answers) else _port("answers", lambda: ports.json(answers, "answers.schema.json"))
        doc["request"], doc["request_unread"], doc["request_given"] = _request(request)
        policy_path = _port("policy", lambda: ports.file(policy_file))
        doc["policy"] = str(policy_path) if policy_path is not None else ""
        doc["base"], doc["head"], doc["lang"] = ports.text(base).strip(), ports.text(head).strip(), ports.text(lang).strip()
        why = unusable(doc["purpose_source"], doc["purpose_review"])
        if why:
            doc.update(due=False, status="unusable", reason=design.UNUSABLE[why])
        else:
            doc.update(due=True, status="", reason="")
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        doc.update(due=False, status="failed", reason=oneline.one_line(f"{type(e).__name__}: {e}"))
    jsonfile.write(out / files.INTAKE, doc)
    return {"due": doc["due"], "status": doc["status"], "reason": doc["reason"]}


# ---------------------------------------------------------------- 指示
def _need(out, name):
    got = jsonfile.read_or(pathlib.Path(out) / name)
    if got is None:
        raise ValueError(f"{pathlib.Path(out) / name} が無いか読めない")
    return got


def design_prompt(out, repo) -> dict:
    """独立設計の役の指示と system prompt を組んで place に書く。前の回までの却下は place の控えから全部。役を起こす前の作業ツリーの姿
    design-tree.json と、貼った前提の控え design-premises.json も置く。返り {prompt, system}"""
    out = pathlib.Path(out)
    doc = _need(out, files.INTAKE)
    request_text = ""
    unread = doc["request_unread"]
    if doc["request"]:
        try:
            request_text = pathlib.Path(doc["request"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            unread = REQUEST_UNREAD.format(path=doc["request"], why=type(e).__name__)
    got = premises.material(r2_view(request_text, doc["answers"]), repo)
    ledger = got["ledger"]
    if unread:
        ledger["withheld"].append({"kind": "named_section", "what": doc["request_given"] or doc["request"] or "request", "why": unread})
    if not answer_rows(doc["answers"]):
        ledger["withheld"].append({"kind": "human_answer", "what": "answers", "why": NO_ANSWERS})
    if not doc["constraints"]:
        ledger["withheld"].append({"kind": "constraint", "what": "constraints", "why": NO_CONSTRAINTS})
    ledger["withheld"] += doc["withheld"]
    marked = added_marks(doc["constraints"], repo, doc["base"], doc["head"])
    stale = stale_purpose_review(doc["purpose_review"])
    rejected = rolekit.rejected(out, files.NODE)
    values = {"rejection": rolekit.rejects_text(rejected),
              "answers": got["answers"], "named": got["named"], "map": got["map"],
              "purpose": doc["purpose"], "constraints": json.dumps(marked, ensure_ascii=False), "hypothesis": HYPOTHESIS,
              "stale": json.dumps(stale, ensure_ascii=False),
              "policy_body": policy_body(doc["policy"]) if doc["policy"] else "",
              "lang": prompt.lang(doc["lang"])}
    when = {"rejected": bool(rejected), "answers": bool(got["answers"]), "named": bool(got["named"]), "stale": bool(stale),
            "policy": bool(doc["policy"]), "request_unread": bool(unread)}
    jsonfile.write(out / files.PREMISES, {"node": files.NODE, **ledger})
    jsonfile.write(out / files.TREE, accept.tree_state(pathlib.Path(repo)))
    return prompt.emit(files.AI_NODE, values, when, prompt.round_of(files.AI_NODE))


# ---------------------------------------------------------------- 受け付け
def _lines(head: str, gaps: list) -> str:
    return head + "\n" + "\n".join(f"  - {g}" for g in gaps)


def _moved(path, repo, keys) -> str:
    """役が作業ツリーを変えた・HEAD や枝を動かした訳（keys の欄で比べる。変えていなければ空）。起こす前の姿 path が読めなければその訳"""
    before = jsonfile.read_or(path)
    if not isinstance(before, dict):
        return NO_TREE.format(name=pathlib.Path(path).name)
    changes = accept.tree_moved(before, pathlib.Path(repo), keys=keys)
    return READONLY_MOVED + "；".join(changes) if changes else ""


def check_design(out, raw, repo, *, keys=accept.TREE_KEYS) -> dict:
    """独立設計の受け付け: 作業ツリーが役の前と同じ（keys の欄で比べる）→ 問いが立たない時は根拠の名指し（パス:行）が固めた版に在る
    →問いが立つ設計は要素を持つ（空と id の重なりを拒む）。通れば design.json と、返答が『渡されていない』と書いた文と控えの given の
    対（design-premises.json の claims）。拒みは控えに積み、rolekit.GIVE_UP_AFTER 回目で done・give_up。返り {ok, done, give_up, reason}"""
    out = pathlib.Path(out)

    def run(reply):
        moved = _moved(out / files.TREE, repo, keys)
        if moved:
            raise Reject(moved)
        if not reply["question_stands"]:
            misses = design.anchor_misses(reply.get("premise_invalid_reason") or reply["reason"], repo)
            if misses:
                raise Reject(PREMISE_MISS + "・".join(misses))
        gaps = design.element_gaps(reply)
        if gaps:
            raise Reject(_lines(ELEMENTS_REJECT, gaps))
        accept.write_board(out, files.DESIGN, reply)
        ledger = jsonfile.read_or(out / files.PREMISES, {})
        ledger["claims"] = design.claims_given(design.claims_unpassed(reply), ledger.get("given") or [])
        jsonfile.write(out / files.PREMISES, ledger)
        return {"ok": True, "reason": ""}
    return rolekit.round_outcome(rolekit.accept_round(out, files.NODE, raw, lambda reply: accept.guard(lambda: run(reply))))


# ---------------------------------------------------------------- 出口
def result(status: str, reason: str, *, made=None, design_file=None, premises_file=None) -> dict:
    """block の返り。ok は status が failed でないか（unusable は役を起こさないと正しく決めた事なので真）"""
    return {"ok": status != "failed", "status": status, "stands": made.get("question_stands") if made else None,
            "design": ports.pointer(design_file) if design_file else None,
            "premises": ports.pointer(premises_file) if premises_file else None, "reason": reason,
            "downgrades": report.DOWNGRADES, "report": report.lines(status, reason, made)}


def record_crash(out, step: str, why: str) -> None:
    """prep・accept の node が落ちた訳を place に残す（出口が読む。ここ自体は落ちない）"""
    try:
        jsonfile.write(pathlib.Path(out) / files.CRASH, {"step": step, "why": oneline.one_line(why)})
    except Exception:  # noqa: BLE001 — 落ちた訳を残す口が落ちても、元の誤りを隠さない
        pass


def _missing_why(out) -> str:
    """設計が取れなかった訳: 落ちた node の訳（役が回った後でも）→ 最後の却下 → 役の loop が回らなかった"""
    crash = jsonfile.read_or(out / files.CRASH)
    if isinstance(crash, dict) and crash.get("why"):
        return CRASHED.format(step=crash.get("step") or "?", why=crash["why"])
    return rolekit.given_up_reason(out, files.NODE) or NOT_RUN


def finish(out) -> dict:
    """block の返り {ok, status, stands, design, premises, reason, downgrades, report}。どの段が落ちても落ちない。finish.json にも写す"""
    out = pathlib.Path(out)
    doc = jsonfile.read_or(out / files.INTAKE)
    ledger = out / files.PREMISES if (out / files.PREMISES).is_file() else None
    if not isinstance(doc, dict):
        got = result("failed", "入口の控えが無い（入口の node が落ちた）")
    elif doc.get("status") in ("unusable", "failed"):
        got = result(doc["status"], str(doc.get("reason") or ""))
    elif isinstance(made := jsonfile.read_or(out / files.DESIGN), dict):
        got = result("ok", "", made=made, design_file=out / files.DESIGN, premises_file=ledger)
    else:
        got = result("failed", f"{design.MISSING}: {_missing_why(out)}", premises_file=ledger)
    jsonfile.write(out / files.FINISH, got)
    return got
