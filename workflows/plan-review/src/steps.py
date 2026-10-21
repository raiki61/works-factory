"""事前審査の block の入口の部品と、script が共に使う口（docs/design/plan-review.md の 8 節。lib/boardview.py の open_pass から、
始めの記録・承認ノードの答え・独立設計・方針の版の固めを除いた写し〔:445-527〕と、_copy_world・_copy_structure〔:666-689〕・
_role_item・replan_items〔:588-612〕・_tree_on〔:692-696〕の写し）。

- intake(out, repo, **raw): port の字を読み、形を決め、place のこの block のファイルを名で消して材料を写し、intake.json を書く。
  返り {due, form, tree, k, reason}。落ちない（誤りは intake-error.json の {why, form} と due: false）
- proposal_of(raw) -> 審査する物の字（入力 proposal か proposal_file の中身）・proposal_form(raw) -> ("plan", 修正案の役の返答) か
  ("text", 方針の文): 審査する物の形の決め（8 節の intake の 2。proposal_file の中身はいつも方針の文）
- recorded_rows(recorded, policy_path) -> 記録された方針の行（port recorded が空で方針が在れば、方針の文書の行だけ）
- replan_items(b, approved, marked_rows, ruled, conflicts): 形 replan の裁かれた項目ごとの材料
- read_intake(out) -> intake.json の中身（無い・読めなければ Missing）・record_crash(out, step, why): prep・accept が落ちた訳（crash.json）
- finish(out) -> 出口の返り（docs/design/plan-review.md の 1.2 と 8 節の finish）。finish.json にも写す
- Missing: 入口の材料が無い・読めない・組めない

intake.json の欄（形 plan と replan）:
  k（形 plan は往復の番号 = prior の往復の数 + 1。形 replan は 0）・form（"plan"|"replan"）・round（port fields の round）・
  ruled（裁かれた項目の番号の並び。形 plan は []）・cwd（作業ツリー）・review_rev（空の port は "HEAD"）・diff_base（空の port は
  review_rev）・request（依頼のファイルの本文。無い・読めなければ ""）・request_file（依頼のファイルのパスか ""）・
  policy_copy（方針の写しのパスか ""）・excluded_file（excluded.json のパスか ""）・units（判定の単位の行）・names（単位の key）・
  questions（判定の問い）・precedents（判定の先行例）・diagnosis（{framing, one_shot} の在る物）・purpose（目的の文）・
  plan（修正案の役の返答から block_answers を外し、narrows の行の決め手の欄を外した物）・plan_marks（外した決め手の欄。
  [[narrows の行ごとの {欄: 値}] 項目ごと]。gatemarks の控えの "p2.fix_plan" の marks と同じ入れ子）・
  recorded_policy（記録された方針の行。policy.RECORDED_KEY）・review_schema（files.node_schema("review")）・
  design_schema（schemas/review-design.schema.json）・design_why（設計が無い訳の 1 行。空の port で設計も無ければ DESIGN_NOT_GIVEN）・
  defaults（既定で読んだ入力の訳の行）・replan_items（形 replan の項目。形 plan は []）・tree（木の往復か）・tree_word（on|off|auto）・
  means（依頼が示した解き方の文）・lang（port lang の字）・human_items（いつも []）・materials（{}）・purpose_review（{}）
  （最後の 3 つは view と lib の古い関数が読むので空で置く）
intake.json の欄（形 text）:
  form（"text"）・k（0）・round（0）・proposal_text（方針の文）・purpose・world（世界の解の行。無ければ []）・recorded_policy・
  policy_copy・review_rev・diff_base・cwd・defaults・lang
place に写す物は docs/design/plan-review.md の 1.4（名は src/files.py）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import shutil

import ports

import conflict    # lib/。replan_rows
import converge    # lib/
import jsonfile    # lib/
import oneline     # lib/
import planmarks   # lib/
import policy      # lib/。RECORDED_KEY
import rolekit     # lib/。却下の控えと合わせた答えの控えの名
import structmark  # lib/
import worldmark   # lib/
from engine.schema import validate_schema   # lib/graphloops/engine/schema.py

from src import files, marks, proof, report, view

TREE_WORDS = ("on", "off", "auto")
DESIGN_NOT_GIVEN = "独立設計の返りが渡されていない"
NO_STRUCTURE = "構造の目の控えが渡されていない"
NO_RIPPLE = "波及の一覧が渡されていない"
NO_APPROVED = "案の直しの事前審査なのに、承認済みの修正案（入力 prior の往復の記録の plan の行）が無い"
NO_FIELDS = "入力 fields: 修正案の欄が渡されていない"
NO_JUDGMENT = "入力 judgment: 判定の返りが渡されていない"
# 既定で読んだ入力の訳の行（材料の「Inputs read with defaults」の節。今の pass_open.port の「無いとして読んだ」と REQUEST_UNREAD）
UNREAD = "入力 {name} を読めない（{why}）——無いとして読んだ"
REQUEST_UNREAD = "依頼のファイル {path} を読めない（{why}）——依頼の本文は空として読み、依頼の引用の決め手は照らせない"
EMPTY_STRUCTURE = "入力 structure が空——構造の目は走っていないとして読んだ（控えは failed）"
EMPTY_RIPPLE = "入力 ripple が空——波及の一覧は無いとして読んだ"
CRASHED = "{step} の node が落ちた（{why}）"
NOT_RUN = "役の loop が回らなかった"
NOT_PASSED = "受け付けを通らなかった（最後の却下: {last}）"
NO_INTAKE = "入口の控えが無い（入口の node が落ちた）"
GIVEN_UP_FACES = "事前審査の受け付けが諦めた: "   # 今の boardview.GIVEN_UP_FACES（src/take.py の同じ名と同じ字。試験が縛る）
# 形 replan で諦めた時の項目ごとの行の訳（今の planblk.REVIEW_GAVE_UP_WHY）と、裁定の文が無い時の字（今の planfile.NO_ROWS）
REVIEW_GAVE_UP_WHY = f"事前審査の役の返答が受け付けの網 {rolekit.NET_AFTER} 回まで拒まれ続けた: {{reason}}"
NO_ROWS = "申し出と裁定の行が見つからない（conflicts の中に、この項目を名指す行が無い）"


class Missing(Exception):
    """入口の材料が無い・読めない・組めない（入口の訳と、prep・出口の誤り）"""


# ---------------------------------------------------------------- 共に使う口
def read_intake(out) -> dict:
    """入口が置いた intake.json の中身。無い・読めない・object でなければ Missing（入口の訳が在れば載せる）"""
    p = pathlib.Path(out) / files.INTAKE
    doc = jsonfile.read_or(p)
    if not isinstance(doc, dict):
        err = jsonfile.read_or(p.with_name(files.INTAKE_ERROR))
        why = err.get("why") if isinstance(err, dict) else ""
        raise Missing(f"入口の控え {p} が無いか読めない（入口の node が通っていない）" + (f": {why}" if why else ""))
    return doc


def record_crash(out, step: str, why: str) -> None:
    """prep・accept の node が落ちた訳 {step, why} を place に残す（出口が読む。ここ自体は落ちない）"""
    try:
        jsonfile.write(pathlib.Path(out) / files.CRASH, {"step": step, "why": oneline.one_line(why)})
    except Exception:  # noqa: BLE001 — 落ちた訳を残す口が落ちても、元の誤りを隠さない
        pass


def crash_why(out) -> str:
    """crash.json の「<step> の node が落ちた（<訳>）」。無ければ空"""
    crash = jsonfile.read_or(pathlib.Path(out) / files.CRASH)
    if isinstance(crash, dict) and crash.get("why"):
        return CRASHED.format(step=crash.get("step") or "?", why=crash["why"])
    return ""


# ---------------------------------------------------------------- 入力の字
def _blank(raw) -> bool:
    """graph の with: が値の無い欄を渡す形（空の字・null・空のオブジェクト・空の配列）。既定と同じ「無い」と読む"""
    return ports.text(raw).strip() in ("", "null", "{}", "[]")


def _port(name: str, read):
    try:
        return read()
    except ValueError as e:
        raise ValueError(f"入力 {name}: {oneline.one_line(str(e))}") from None


def _shaped(name: str, value, shape: dict, what: str):
    errors = validate_schema(value, shape)
    if errors:
        raise ValueError(f"入力 {name}: {what}の形に合わない: {' / '.join(errors[:5])}")
    return value


def proposal_of(raw: dict) -> str:
    """審査する物の字: 入力 proposal か、入力 proposal_file（方針の文のファイル。在れば中身を形 text の方針の文として読む）。
    2 つを一緒に名指せば ValueError（どちらで読んだかを黙って決めない）"""
    named = ports.text(raw.get("proposal_file")).strip()
    if not named:
        return ports.text(raw.get("proposal"))
    if ports.text(raw.get("proposal")).strip():
        raise ValueError("入力 proposal と proposal_file は一緒に名指さない（方針の文のファイルは proposal_file だけで渡す）")
    path = _port("proposal_file", lambda: ports.file(named))
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"入力 proposal_file: 審査する物が空（{path}）")
    return text


def proposal_form(raw) -> tuple[str, object]:
    """審査する物の形: ("plan", 修正案の役の返答の dict) か ("text", 方針の文)。字の前後の空白を除き、(a) この run の pointer なら
    その先の JSON（読めなければ ValueError。黙って方針の文にしない。K15）・(b) { で始まり JSON の object として読めればその値・
    (c) 改行を持たず在るファイルに解ければ、その JSON——の 3 つは構造で、中身を files.PROPOSAL_SHAPE で照らす（合わなければ ValueError）。
    どれでもなければ方針の文。(b) は plan の配列を持たない object も構造と読んで照らしで拒む（設計書の字は「plan の配列を持てば」だが、
    JSON の object を方針の文として審査するのは黙った緩め。docs/design/plan-review.md の 14 節）"""
    text = ports.text(raw).strip()
    if not text:
        raise ValueError("入力 proposal: 審査する物が空")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    value = None
    if isinstance(parsed, dict) and parsed.get("type") == ports.POINTER_TYPE:
        value = _port("proposal", lambda: ports.json(text))
    elif text.startswith("{") and isinstance(parsed, dict):
        value = parsed
    elif "\n" not in text:
        try:
            path = ports.file(text)
        except ValueError:
            path = None
        if path is not None:
            value = _port("proposal", lambda: ports.json(str(path)))
    if value is None:
        return "text", text
    return "plan", _shaped("proposal", value, files.PROPOSAL_SHAPE, "修正案の役の返答")


def recorded_rows(recorded, policy_path) -> list:
    """記録された方針の行: port recorded の行が在ればそれ、無くて方針の写し policy_path が在れば、文書の行だけ
    [{source: doc, name: <写しのパス>, text: "", lines: <行数>, alias: ""}]（今の policy.recorded の文書の行と同じ形）"""
    rows = [r for r in recorded or [] if isinstance(r, dict)]
    if rows or not policy_path:
        return rows
    lines = len(pathlib.Path(policy_path).read_text(encoding="utf-8", errors="replace").splitlines())
    return [{"source": "doc", "name": str(policy_path), "text": "", "lines": lines, "alias": ""}]


def _ruling(raw) -> list:
    """port ruling の字（JSON の配列か、, で区切った番号の字）を planmarks.handed が読む並びに。空は []"""
    text = ports.text(raw).strip()
    if not text or text in ("null", "[]"):
        return []
    if text.startswith("["):
        got = json.loads(text)
        if not isinstance(got, list):
            raise ValueError("ruling が JSON の配列でない")
        return got
    return [part.strip() for part in text.split(",") if part.strip()]


# ---------------------------------------------------------------- 写し
def _clean(d: pathlib.Path) -> None:
    """この block のファイルを名で引いて消す（libdocs/ は版で引く控えなので消さない。14 節の 14）。却下の控えと合わせた答えの控えは
    lib/rolekit が名を組む物を、受け付けの名で引く（rejects-*.json の広い形で消さない）"""
    names = [*files.OWN_FILES,
             *(p.name for node in (files.REVIEW_NODE, files.TEXT_NODE)
               for p in (rolekit.rejects_path(d, node), rolekit.rejects_text_path(d, node), rolekit.candidate_path(d, node)))]
    for name in names:
        (d / name).unlink(missing_ok=True)
    for name in files.OWN_DIRS:
        shutil.rmtree(d / name, ignore_errors=True)
    for pattern in files.OWN_GLOBS:
        for path in d.glob(pattern):
            path.unlink()


def _copy_world(d: pathlib.Path, world) -> list:
    """世界の解の行の写しと段の控え（world が None なら控えを置かない＝人に回しうる行の世界の軸が今どおりの決まりに戻る）。写した行を返す"""
    if world is None:
        (d / worldmark.COPY_STATE).unlink(missing_ok=True)
        return []
    dest = d / files.WORLD_COPY
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(world, dest)
    rows = worldmark.rows(dest)
    worldmark.write(d, status="ok", reason="", world_file=str(dest), classes=len(rows), dropped=0, name=worldmark.COPY_STATE)
    return rows


def _copy_means(d: pathlib.Path, means: list) -> None:
    """依頼が示した解き方の写し（worldmark.copy_means の写しの名と形 {means: [...]}。空なら前の写しを消す）"""
    got = [m for m in means if isinstance(m, str) and m.strip()]
    if got:
        jsonfile.write(d / worldmark.COPY_MEANS, {"means": got})
    else:
        (d / worldmark.COPY_MEANS).unlink(missing_ok=True)


def _copy_structure(d: pathlib.Path, doc) -> None:
    """構造の目の控えの写し（控えの design_file が指す設計の行を写し、写しの design_file は写した物を指す）。doc が None は
    構造の目が走っていない（status failed で写す）"""
    if doc is None:
        structmark.write(d / structmark.COPY_FILE, status="failed", reason=NO_STRUCTURE, design_file="")
        return
    src = doc.get("design_file") if isinstance(doc, dict) else None
    rows = pathlib.Path(src) if src and pathlib.Path(src).is_file() else None
    dest = d / files.STRUCTURE_ROWS
    if rows is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(rows, dest)
    ok = isinstance(doc, dict) and doc.get("status") == "ok"
    structmark.write(d / structmark.COPY_FILE, status="ok" if ok else "failed",
                     reason=str(doc.get("reason") or "") if isinstance(doc, dict) else "構造の目の控えが object でない",
                     design_file=str(dest) if rows is not None else "", timed=(doc,) if isinstance(doc, dict) else ())


def _role_item(item: dict) -> dict:
    """承認済みの項目から、役の返答の型が持てない欄（鍵 item と rewrite_tests の行の範囲 limit）を外した写し
    （元 works/.shared/core/replan.py:281）"""
    out = {k: v for k, v in item.items() if k != "item"}
    if isinstance(out.get("rewrite_tests"), list):
        out["rewrite_tests"] = [{k: v for k, v in r.items() if k != "limit"} if isinstance(r, dict) else r
                                for r in out["rewrite_tests"]]
    return out


def replan_items(b, approved, marked_rows: list, ruled: list, conflicts: list) -> list:
    """裁かれた項目ごとの {item, units, rows（申し出と裁定の行）, old（承認済みの前の形）, new（直した形。決め手の欄つき）}。
    申し出の行は conflict.replan_rows の選び。承認済みの案が無い・項目が案の外なら Missing"""
    if approved is None:
        raise Missing(NO_APPROVED)
    now = planmarks.approved_items(b) or []
    out = []
    for n in ruled:
        if not 1 <= n <= min(len(approved), len(now), len(marked_rows)):
            raise Missing(f"裁かれた項目 {n} が承認済みの修正案（{len(approved)} 項目）か直した案（{len(now)} 項目）の外")
        units = [str(k) for k in now[n - 1].get("unit_keys") or []]
        new = {**_role_item(now[n - 1]), **{k: copy.deepcopy(v) for k, v in marked_rows[n - 1].items() if k == "narrows"}}
        out.append({"item": n, "units": units, "rows": conflict.replan_rows(conflicts, n, units),
                    "old": _role_item(approved[n - 1]), "new": new})
    return out


def _approved(prior: dict | None) -> list | None:
    """承認済みの修正案の項目（prior の往復の記録の plan の行 row。note_plan が案の行に欄を重ねた物で、今の
    planmarks.approved_items と同じ形 {item, **行}）。prior か plan が無ければ None（14 節の 24）"""
    rows = (prior or {}).get("plan")
    if not isinstance(rows, list) or not rows:
        return None
    return [{"item": n, **copy.deepcopy(r.get("row") or {})} for n, r in enumerate(rows, 1) if isinstance(r, dict)]


def _tree_on(b, word: str) -> bool:
    """事前審査を木にするか（on・off、auto は開いた項目が TREE_AUTO_MIN 以上。元 planblk.prep の review_tree）"""
    if word != "auto":
        return word == "on"
    from src import material
    return len(material._opened(b, material._item_rows(b))) >= material.TREE_AUTO_MIN


# ---------------------------------------------------------------- 入口
def _file(name: str, raw):
    """file の port（空は None。在らなければ ValueError）"""
    return None if _blank(raw) else _port(name, lambda: ports.file(raw))


def _json(name: str, raw, schema=None):
    return None if _blank(raw) else _port(name, lambda: ports.json(raw, schema))


def _json_file(name: str, raw):
    """file と宣言した port のうち JSON のファイルを渡す物（structure・ripple・prior・conflicts）。ports.file を通してから JSON に読む
    （値を直に渡すと file の誤りで落ちる。空は None）"""
    path = _file(name, raw)
    return None if path is None else _port(name, lambda: ports.json(str(path)))


def _soft(name: str, read, defaults: list):
    """読めない時は落とさず、無いとして読み、訳の行を defaults に足す（excluded・request・means）"""
    try:
        return read()
    except (ValueError, OSError, UnicodeDecodeError) as e:
        defaults.append(UNREAD.format(name=name, why=oneline.one_line(str(e)) or type(e).__name__))
        return None


def _request(raw, defaults: list) -> tuple[str, str]:
    """(依頼のファイルのパス, 本文)。空は ("", "")。在らない・読めないファイルは ("", "") と訳の行"""
    if _blank(raw):
        return "", ""
    given = ports.text(raw).strip()[:200]
    try:
        path = ports.file(raw)
        return str(path), path.read_text(encoding="utf-8")
    except (ValueError, OSError, UnicodeDecodeError) as e:
        defaults.append(REQUEST_UNREAD.format(path=given, why=oneline.one_line(str(e)) or type(e).__name__))
        return "", ""


def _texts(d: pathlib.Path, raw: dict, defaults: list) -> dict:
    """3 つの形が共に読む物: 目的・世界の解の行・方針・記録された方針・読む版と BASE・言語"""
    world = _file("world_rows", raw.get("world_rows"))
    rows = _port("world_rows", lambda: _copy_world(d, world))
    policy_path = _file("policy", raw.get("policy"))
    recorded = _json("recorded", raw.get("recorded"), "recorded.schema.json") or []
    rev = ports.text(raw.get("review_rev")).strip() or "HEAD"
    return {"purpose": ports.text(raw.get("purpose")).strip(), "world": rows,
            "policy_copy": str(policy_path) if policy_path is not None else "",
            policy.RECORDED_KEY: recorded_rows(recorded, policy_path),
            "review_rev": rev, "diff_base": ports.text(raw.get("diff_base")).strip() or rev,
            "lang": ports.text(raw.get("lang")).strip()}


def _plan_doc(d: pathlib.Path, repo, raw: dict, proposal: dict, defaults: list, common: dict) -> dict:
    """形 plan と replan の材料を写して intake.json の中身を組む（8 節の intake の 4〜13）"""
    ruling = _port("ruling", lambda: _ruling(raw.get("ruling")))
    form = "replan" if ruling else "plan"
    if _blank(raw.get("judgment")):
        raise ValueError(NO_JUDGMENT)
    judged = _json("judgment", raw.get("judgment"), "shared:judgment.schema.json")
    jsonfile.write(d / files.JUDGMENT, judged)
    if _blank(raw.get("fields")):
        raise ValueError(NO_FIELDS)
    fields = _json("fields", raw.get("fields"), "review-fields.schema.json")
    excluded = _soft("excluded", lambda: _file("excluded", raw.get("excluded")), defaults)
    if excluded is not None and _soft("excluded", lambda: json.loads(excluded.read_text(encoding="utf-8")), defaults) is not None:
        shutil.copyfile(excluded, d / files.EXCLUDED)
    else:
        excluded = None
    request_file, request = _request(raw.get("request"), defaults)
    means = _soft("means", lambda: _json("means", raw.get("means"), "stated-means.schema.json"), defaults) or []
    design_doc = _json("design", raw.get("design"), "review-design.schema.json")
    structure_doc = _json_file("structure", raw.get("structure"))
    if structure_doc is None:
        defaults.append(EMPTY_STRUCTURE)
    ripple_doc = _json_file("ripple", raw.get("ripple"))
    if ripple_doc is None:
        defaults.append(EMPTY_RIPPLE)
    prior = _json_file("prior", raw.get("prior"))
    if prior is not None:
        _shaped("prior", prior, files.PRIOR_SHAPE, "往復の記録")
    conflicts = _json_file("conflicts", raw.get("conflicts")) if form == "replan" else None
    tree_word = ports.text(raw.get("tree")).strip() or "auto"
    _port("tree", lambda: ports.choice(tree_word, TREE_WORDS))

    # 5. 修正案の役の返答を割る（block_answers と、narrows の行の決め手の欄）
    bare, answered = marks.split_answers(proposal)
    marked = copy.deepcopy(bare)
    bare, plan_marks = marks.split_plan(bare)
    rows = [r for r in bare.get("plan") or [] if isinstance(r, dict)]
    # 6. 形 replan: 裁かれた項目と承認済みの案
    ruled, approved = [], None
    if form == "replan":
        ruled, why = planmarks.handed(ruling, len(rows))
        if why:
            raise ValueError(f"入力 ruling: {why}")
        approved = _approved(prior)
        if approved is None:
            raise ValueError(f"入力 prior: {NO_APPROVED}")
    # 7. 欄の控えと凍結の印・案の行と欄の数
    out = view.place(d)
    planmarks.save(d, 1, fields["fields"], {int(n): v for n, v in (fields.get("amended") or {}).items()} or None, trace=out.trace)
    try:
        pairs = planmarks.paired(rows, fields["fields"], "入力 fields")
    except planmarks.FieldsBroken as e:
        raise ValueError(f"入力 fields: {e}") from None
    # 8. 往復の記録の作業の写し
    record = {"round": 1, "passes": copy.deepcopy((prior or {}).get("passes") or []), "outcome": (prior or {}).get("outcome"), "open": {}}
    if isinstance((prior or {}).get("plan"), list):
        record["plan"] = copy.deepcopy(prior["plan"])
    jsonfile.write(d / files.CONVERGE, record)
    converge.note_plan(out, [planmarks.joined(r, f) for r, f in pairs])
    if form == "plan" and answered:
        converge.note_answers(out, answered)
    jsonfile.write(d / files.PRECEDENT_CHECKS, copy.deepcopy((prior or {}).get("precedent_checks") or {}))
    k = converge.pass_no(out) if form == "plan" else 0
    # 9. 写し
    _copy_means(d, means)
    _copy_structure(d, structure_doc)
    if design_doc is not None:
        jsonfile.write(d / files.DESIGN, design_doc)
    jsonfile.write(d / files.RIPPLE, ripple_doc if ripple_doc is not None else {"items": [], "overlaps": [], "error": NO_RIPPLE})

    units = [u for u in judged.get("units") or [] if isinstance(u, dict)]
    doc = {
        "k": k, "form": form, "round": fields["round"], "ruled": ruled, "cwd": str(repo),
        "review_rev": common["review_rev"], "diff_base": common["diff_base"],
        "request": request, "request_file": request_file, "policy_copy": common["policy_copy"],
        "excluded_file": str(d / files.EXCLUDED) if excluded is not None else "",
        "units": units, "names": [u["key"] for u in units if isinstance(u.get("key"), str)],
        "questions": judged.get("questions") or [], "precedents": judged.get("precedents") or [],
        "diagnosis": {x: judged[x] for x in ("framing", "one_shot") if x in judged},
        "purpose": common["purpose"], "plan": bare, "plan_marks": plan_marks,
        policy.RECORDED_KEY: common[policy.RECORDED_KEY],
        "review_schema": files.node_schema("review"),
        "design_schema": json.loads((files.YAML.parent / "schemas" / "review-design.schema.json").read_text(encoding="utf-8")),
        "design_why": ports.text(raw.get("design_why")).strip() or ("" if design_doc is not None else DESIGN_NOT_GIVEN),
        "defaults": defaults, "replan_items": [], "tree": False, "tree_word": tree_word, "means": means, "lang": common["lang"],
        "human_items": [], "materials": {}, "purpose_review": {},
    }
    b = view.view(d, doc)
    # 11. 形 replan の項目
    if form == "replan":
        try:
            doc["replan_items"] = replan_items(b, approved, marked.get("plan") or [], ruled,
                                               [c for c in (conflicts or {}).get("items") or [] if isinstance(c, dict)])
        except Missing as e:
            raise ValueError(f"入力 ruling: {e}") from None
    # 12. 木
    doc["tree"] = form == "plan" and _tree_on(b, tree_word)
    return doc


def intake(out, repo, **raw) -> dict:
    """port の字（raw の鍵は port の名。script が os.environ.get("INPUTS_<名>") の字のまま渡す）を読み、place のこの block のファイルを
    名で消して材料を写し、intake.json を書く（docs/design/plan-review.md の 8 節）。返り {due, form, tree, k, reason}。落ちない:
    誤りは intake-error.json に {why, form} を書いて due: false"""
    d = pathlib.Path(out)
    form = ""
    try:
        _clean(d)
        defaults: list = []
        if ports.text(raw.get("proposal_file")).strip():
            form, proposal = "text", proposal_of(raw)
        else:
            form, proposal = proposal_form(proposal_of(raw))
        form = "replan" if form == "plan" and not _blank(raw.get("ruling")) else form
        common = _texts(d, raw, defaults)
        if form == "text":
            doc = {"form": "text", "k": 0, "round": 0, "proposal_text": proposal, "purpose": common["purpose"],
                   "world": common["world"], policy.RECORDED_KEY: common[policy.RECORDED_KEY],
                   "policy_copy": common["policy_copy"], "review_rev": common["review_rev"], "diff_base": common["diff_base"],
                   "cwd": str(repo), "defaults": defaults, "lang": common["lang"]}
        else:
            doc = _plan_doc(d, repo, raw, proposal, defaults, common)
            form = doc["form"]
        jsonfile.write(d / files.INTAKE, doc)
        return {"due": True, "form": form, "tree": bool(doc.get("tree")), "k": doc["k"], "reason": ""}
    except Exception as e:  # noqa: BLE001 — 入口は落ちない（出口が status: failed にする）
        why = oneline.one_line(str(e) if isinstance(e, (ValueError, Missing)) else f"{type(e).__name__}: {e}")
        try:
            (d / files.INTAKE).unlink(missing_ok=True)
            jsonfile.write(d / files.INTAKE_ERROR, {"why": why, "form": form}, parents=True)
        except OSError:
            pass
        return {"due": False, "form": form, "tree": False, "k": 0, "reason": why}


# ---------------------------------------------------------------- 出口
def ruling_text(rows: list) -> str:
    """申し出と裁定の行の裁定の文（字のまま。2 行以上は「／」で繋ぐ。今の planfile.ruling_text の写し）"""
    return "／".join(str((c.get("ruling") or {}).get("text") or "") for c in rows if isinstance(c, dict)) or NO_ROWS


def _pointer(path: pathlib.Path):
    return ports.pointer(path) if path.is_file() else None


def result(status: str, reason: str, *, form: str = "", k: int = 0, review_file=None, pass_file=None, review=None, asks=(),
           deviations=(), replan=(), gave_up=None, ruled=(), tree_items: int = 0, out=None) -> dict:
    """block の返り（docs/design/plan-review.md の 1.2）。ok は status が ok か。out（place）が在れば読んだ証拠の pointer と欠けの行を足す"""
    found, missing, failed = proof.evidence(out) if out is not None else (None, [], "")
    return {"ok": status == "ok", "status": status, "form": form, "round": k if form == "plan" else 0, "reason": reason,
            "holes": _pointer(review_file) if review_file is not None else None,
            "blocks": [str(f.get("key")) for f in converge.block_faces(review)] if status == "ok" and isinstance(review, dict) else [],
            "pass": _pointer(pass_file) if pass_file is not None else None,
            "asks": list(asks), "deviations": list(deviations), "replan": list(replan), "gave_up": gave_up,
            "reads": ports.pointer(found) if found is not None else None,
            "report": report.lines(status=status, form=form, reason=reason, review=review, k=k, ruled=ruled, tree_items=tree_items,
                                   missing=missing, proof_failed=failed)}


def _not_passed(d: pathlib.Path, node: str) -> str:
    """返答が取れなかった訳: 落ちた node の訳 → 最後の却下 → 役の loop が回らなかった"""
    last = rolekit.rejected(d, node)
    return crash_why(d) or (NOT_PASSED.format(last=oneline.one_line(last[-1])) if last else NOT_RUN)


def _tree_items(d: pathlib.Path) -> int:
    return len(list((d / files.ITEMS_DIR).glob("item-*.md")))


def _finish_text(d: pathlib.Path, doc: dict) -> dict:
    gave = rolekit.given_up_reason(d, files.TEXT_NODE)
    if gave:
        why = GIVEN_UP_FACES + gave
        # 形 text の受け付けは諦めた時に review.json を書かないので、出口が空の返答を置く（holes は諦めた時も pointer。1.2）
        jsonfile.write(d / files.REVIEW, {"faces": [], "shrink": [], "reason": why})
        return result("gave_up", why, form="text", review_file=d / files.REVIEW, out=d)
    review = jsonfile.read_or(d / files.REVIEW)
    if isinstance(review, dict):
        return result("ok", "", form="text", review_file=d / files.REVIEW, review=review, out=d)
    return result("failed", _not_passed(d, files.TEXT_NODE), form="text", out=d)


def _finish_plan(d: pathlib.Path, doc: dict) -> dict:
    form, k, ruled = doc["form"], int(doc.get("k") or 0), list(doc.get("ruled") or [])
    gave = rolekit.given_up_reason(d, files.REVIEW_NODE)
    review = jsonfile.read_or(d / files.REVIEW)
    if not gave and isinstance(review, dict) and str(review.get("reason") or "").startswith(GIVEN_UP_FACES):
        # 拒否の控えが扱えずに受け付けが諦めた時（rolekit._unusable）は控えから諦めを読めない。受け付けが書いた諦めの空の返答で読む
        gave = str(review["reason"])[len(GIVEN_UP_FACES):]
    if gave:
        gave_up = None
        if form == "replan":
            gave_up = [{"item": r["item"], "why": REVIEW_GAVE_UP_WHY.format(reason=gave), "ruling": ruling_text(r.get("rows") or [])}
                       for r in doc.get("replan_items") or [] if isinstance(r, dict)]
            jsonfile.write(d / files.REPLAN_GAVE_UP, gave_up)
        return result("gave_up", GIVEN_UP_FACES + gave, form=form, k=k, review_file=d / files.REVIEW, gave_up=gave_up, ruled=ruled, out=d)
    if not isinstance(review, dict):
        return result("failed", _not_passed(d, files.REVIEW_NODE), form=form, k=k, ruled=ruled, out=d)
    from src import gate
    replan = []
    if form == "replan":
        replan = gate.replan(d, doc, review)
        jsonfile.write(d / files.REPLAN, replan)
    return result("ok", "", form=form, k=k, review_file=d / files.REVIEW, pass_file=d / files.PASS if form == "plan" else None,
                  review=review, asks=gate.asks(d, doc, review), deviations=gate.deviations(d, doc, review), replan=replan,
                  ruled=ruled, tree_items=_tree_items(d) if doc.get("tree") else 0, out=d)


def finish(out) -> dict:
    """block の返り（1.2）。入口の控えが無ければ入口の訳で failed。形ごとに、受け付けが諦めたら gave_up、受けた返答が在れば ok、
    どちらも無ければ failed と落ちた node・最後の却下・回らなかった訳。finish.json にも写す"""
    d = pathlib.Path(out)
    doc = jsonfile.read_or(d / files.INTAKE)
    if not isinstance(doc, dict):
        err = jsonfile.read_or(d / files.INTAKE_ERROR)
        err = err if isinstance(err, dict) else {}
        got = result("failed", str(err.get("why") or NO_INTAKE), form=str(err.get("form") or ""))
    elif doc.get("form") == "text":
        got = _finish_text(d, doc)
    else:
        got = _finish_plan(d, doc)
    text = doc.get("proposal_text") if isinstance(doc, dict) and doc.get("form") == "text" else None
    got["proposal_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest() if isinstance(text, str) else ""
    jsonfile.write(d / files.FINISH, got)
    return got
