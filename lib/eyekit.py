"""独立の目の族（blocks/r1〜r4。docs/design/r1.md の 0 節）が共に使う部品。どれも lib/eyeverdict.py の関数の写しか、それを値で
受ける形にした物（写す元は関数ごとの docstring）。標準ライブラリと KEEP の lib の部品だけを読む。実行系を知らない（パスと値を受け、
値を返す）。ファイルの名は呼び手の block が渡す。

- take_diff(place, repo, base, skip, name, none_name): 累積差分 {file, text, why, lines, changed, base, repo}
- changed_files(diff_text): 差分が触れたファイルの並び
- diff_values(diff): 断片 eye-diff の値 {diff_file, changed_files, base, repo}
- maps(repo): 断片 concept-map の値と段落の真偽 ({concept_maps, map_tail}, found)
- review_md(repo): (工場の観点の正本 lib/REVIEW.md の絶対パス, 対象の根の REVIEW.md の絶対パスか "")
- review_md_values(repo): 断片 eye-coherence の値 {review_md, repo_review_md}（対象の根に REVIEW.md が無ければ NO_REPO_REVIEW_MD）
- after_section(after_file, review)・review_line(review): R1・R3 の頭に貼る直した後の実測の材料と、事前審査の最後の往復の結論の 1 行
- human_items(answers): 承認ノードの答え {start, before_fix} を記録の行 {round, node, answer, note, …} に
- policy_start(policy_file, request_answers)・policy_body(policy_file): lib/policy.py の口に渡す最小の始めの記録と、断片 policy の本文
- recorded_rows(...)・recorded_rows_text(rows): 記録された方針の行と、断片 recorded-policy の値と段落の真偽
- status_values(eye): md に入れる判定の語 {st_pass, st_redesign, st_unverifiable}（R1 は st_fix も）
- read_reply(place, name)・verdict_row(eye, doc, why)・headline(name, row): 役の返答の読みと、判定の行の決め（docs/design/r1.md の
  0.9）と、報告の頭の 1 行
"""
from __future__ import annotations

import json
import pathlib

import answer
import changemap
import concepthome
import gatemarks
import materialkit
import oneline
import policy
import seal
import structmark

FELL_MARK = "の筋が落ちた"
NO_FILE = "出力のファイルが無い"
NO_AFTER = "直しの後の実測: 控えが無い（測っていない run）"   # 元 blk-eyes/lib/eyes.py:93
AFTER_MISNAMED = "直しの後の実測: 控え {path} を読まない（名が " + structmark.AFTER_FILE + " でない）"
# R1 の作り直しが要るの導き（verdict_row）の頭の字。最後の承認ノードと報告の冒頭に平易な主語で出る
_FIX, _REDESIGN = map(gatemarks.status_named, (seal.FIX_NEEDED, seal.REDESIGN))
UNNAMED_REDESIGN = f"目は{_REDESIGN}と書いたが、組み直す設計の点（redesign_points）の名指しが無いので{_FIX}に倒した: "
RAISED_BY_POINTS = f"組み直す設計の点（redesign_points）の名指しが在るので{_REDESIGN}にした: "
BROKEN_POINTS = (f"組み直す設計の点（redesign_points）の欄が配列でないか読める項が無く、名指しの有無を決められないので"
                 f"{gatemarks.status_named(seal.UNVERIFIABLE)}にした: ")
REVIEW_ACCEPTED = "  事前審査の最後の往復（pass-{k}）は上の外れの訳を見て案を通した（外れを認めた）"
REVIEW_BLOCKED = "  事前審査の最後の往復（pass-{k}）は上の外れの訳を見て、block の穴 {n} 件を残した（外れを認めていない）: {faces}"
REVIEW_GAVE_UP = "  事前審査の最後の往復（pass-{k}）は受け付けが諦めて案を通していない（外れを認めていない）: {why}"
REVIEW_HELD = ("  事前審査の最後の往復（pass-{k}）は block の穴を挙げ直さなかったが、前の往復の穴を保留のまま案を通していない"
               "（外れを認めていない。往復の控えの抜け方: {outcome}）")
REVIEW_NO_PLAN = "事前審査は直す物の無い周（形 design）で、案を審査していない"
REVIEW_UNREAD = "  事前審査の最後の往復の返答を読めない（外れを認めたかは分からない）: {why}"
REVIEW_NOT_GIVEN = "事前審査の往復の結論が渡されていない"
LANE = {"r1": "R1", "r2": "R2", "premise-check": "R2", "r3": "R3", "r4": "R4"}
NO_MAP_TREE = " (the tree could not be read: {why})"   # 断片 concept-map-none の {map_tail}（木を読めなかった訳）
MORE_MAPS = "- and {n} more"                          # 地図が MAX_MAPS を越えた分の行
NO_REPO_REVIEW_MD = "(none at the root of the target repository)"   # 元 prep.py:122 の「対象のリポジトリの根に REVIEW.md は無い」


# ---------------------------------------------------------------- 累積差分
def changed_files(diff_text: str) -> list[str]:
    """元 eyeverdict.changed_files。changemap.split_diff のファイルの並び"""
    return list(changemap.split_diff(diff_text)[0])


def take_diff(place, repo, base: str, skip, name: str, none_name: str) -> dict:
    """元 workflows/eyes/scripts/prep.py:78。根 base（空なら HEAD）から作業ツリーの今の姿（未追跡の新しいファイルも入れ、除くパスの頭
    skip の下は除く）までの累積差分を place/name に書く。空・取れない時は訳を place/none_name に書いてそれを指す
    （fixboard.diff_file）。返り {file, text, why, lines, changed, base, repo}。why は取れなかった訳（本当に空なら空の字）、base は
    差分を引いた版の名、repo は作業ツリーの根"""
    import fixboard   # 作り直しの間は lib の fixboard を読む（docs/design/r1.md の 10 節の 2）
    rev = (base or "").strip() or "HEAD"
    path, text, why = fixboard.diff_file(pathlib.Path(repo), lambda: rev, pathlib.Path(place), name, none_name, tuple(skip))
    return {"file": str(path), "text": text, "why": why, "lines": len(text.splitlines()), "changed": changed_files(text),
            "base": rev, "repo": str(repo)}


def diff_values(diff: dict) -> dict:
    """断片 eye-diff の値（ちょうどこの 4 つ）。changed_files は「、」でつないだ字か、差分が無い時は取れなかった訳（元 prep.py:117）"""
    return {"diff_file": str(diff["file"]), "changed_files": "、".join(diff.get("changed") or []) or str(diff.get("why") or ""),
            "base": str(diff.get("base") or "HEAD"), "repo": str(diff["repo"])}


# ---------------------------------------------------------------- 考えの地図・観点の正本
def maps(repo) -> tuple[dict, bool]:
    """元 concepthome.section の材料の部分。({concept_maps, map_tail}, found)。concept_maps は見つかった地図の「- <パス>」の行
    （MAX_MAPS を越えた分は MORE_MAPS）、map_tail は見つからない時の尾（木を読めなければ NO_MAP_TREE、読めれば空の字）、found は
    地図が 1 つ以上在るか。見出しと読み方の文は断片 concept-map-found・concept-map-none が持つ"""
    names, why = concepthome.tracked_names(pathlib.Path(repo))
    found, total = concepthome.pick_maps(names)
    rows = [f"- {m}" for m in found]
    if total > len(found):
        rows.append(MORE_MAPS.format(n=total - len(found)))
    tail = "" if found or not why else NO_MAP_TREE.format(why=oneline.one_line(why))
    return {"concept_maps": "\n".join(rows), "map_tail": tail}, bool(found)


def review_md(repo) -> tuple[str, str]:
    """元 prep.py:121-122。materialkit.review_md_paths の返り"""
    return materialkit.review_md_paths(repo)


def review_md_values(repo) -> dict:
    """断片 eye-coherence の値 {review_md, repo_review_md}。対象の根に REVIEW.md が無ければ repo_review_md は NO_REPO_REVIEW_MD
    （元 prep.py:122。R3 と、R3 をまとめて見る R4 が使う）"""
    own, theirs = review_md(repo)
    return {"review_md": own, "repo_review_md": theirs or NO_REPO_REVIEW_MD}


# ---------------------------------------------------------------- 直した後の実測と事前審査の結論
def review_line(review) -> str:
    """元 eyeverdict.plan_review_line を、事前審査の置き場を読む代わりに port review の値 {round, verdict, blocks, why} で組む形"""
    if not isinstance(review, dict) or not review:
        return REVIEW_UNREAD.format(why=REVIEW_NOT_GIVEN)
    k, verdict, why = review.get("round"), review.get("verdict"), str(review.get("why") or "")
    if verdict == "accepted":
        return REVIEW_ACCEPTED.format(k=k)
    if verdict == "blocked":
        blocks = [b for b in review.get("blocks") or [] if isinstance(b, dict)]
        return REVIEW_BLOCKED.format(k=k, n=len(blocks), faces="; ".join(f"{b.get('key')}: {b.get('why')}" for b in blocks))
    if verdict == "gave_up":
        return REVIEW_GAVE_UP.format(k=k, why=why)
    if verdict == "held":
        return REVIEW_HELD.format(k=k, outcome=why)
    if verdict == "design":
        return REVIEW_UNREAD.format(why=REVIEW_NO_PLAN)
    if verdict == "unread":
        return REVIEW_UNREAD.format(why=why)
    return REVIEW_UNREAD.format(why=f"結論の語が約束の外（{verdict!r}）")


def after_section(after_file, review) -> str:
    """元 eyeverdict.after_section。直した後の構造の実測の控え after_file（structure の block の structure-after.json。None は測って
    いない）の数の 1 文。修正案の外れの訳が在れば、訳の行と事前審査の最後の往復の結論 review_line(review) を続ける"""
    if after_file is None:
        return NO_AFTER
    path = pathlib.Path(after_file)
    if path.name != structmark.AFTER_FILE:
        return AFTER_MISNAMED.format(path=path)
    if structmark.read_after(path.parent) is None:
        return NO_AFTER
    counts = structmark.after_counts(path.parent)
    devs = structmark.deviation_lines(path.parent)
    return "\n".join([counts, *devs, review_line(review)] if devs else [counts])


# ---------------------------------------------------------------- 人の答えと方針
def human_items(answers) -> list:
    """元 eyeverdict.human_items(start_answer, answer) を、port answers の {start, before_fix} で呼ぶ形。答えた順に
    {round: 1, node, answer, note, …answer.origin(a)}（無人の run が推しで通した答えは欄 answer.PUSHED を写す）"""
    answers = answers if isinstance(answers, dict) else {}
    return [{"round": 1, "node": node, "answer": a.get("decision"), "note": (a.get("text") or "").strip() or None, **answer.origin(a)}
            for node, a in ((gatemarks.START_GATE_NODE, answers.get("start")), (gatemarks.GATE_NODE, answers.get("before_fix")))
            if isinstance(a, dict)]


def policy_start(policy_file, request_answers) -> dict:
    """lib/policy.py の公開の口（brief・recorded）に渡す最小の始めの記録（policy.version が読む形）。block は始めの記録を受けないので、
    方針の写し policy_file と依頼の answers だけを詰める"""
    return {"policy": {"named": "", "path": "", "sha256": None, "copy": str(policy_file) if policy_file else None},
            "answers": list(request_answers or [])}


def policy_body(policy_file) -> str:
    """断片 policy の {policy_body}。policy.PASTE_CAP バイトまで（超えた分は写しのパスを末尾に書く）。方針の文書が無い・読めなければ
    空の字（元 policy.section と同じく節ごと貼らない）"""
    if not policy_file or not pathlib.Path(policy_file).is_file():
        return ""
    return policy.brief(policy_start(policy_file, []))["paste"]


def recorded_rows(policy_file, request_answers, items, pushes, decisions_file) -> list:
    """記録された方針の行 [{source, name, text, …}]（元 prep.py:99 の policy.recorded）"""
    return policy.recorded(policy_start(policy_file, request_answers), decisions_file, human_items=items, pushes=list(pushes or []))


def _head(text) -> str:
    text = oneline.one_line(text or "")
    return text if len(text) <= 120 else text[:120] + "…"


def recorded_rows_text(rows) -> tuple[str, bool]:
    """断片 recorded-policy の値と段落の真偽 (recorded_rows, recorded_none)。行の組み方は元 policy._section（lib/policy.py:295-314）の
    行を英語の札にした物。名指しの字 name は変えない（受け付けと承認ノードが字で照らす）。recorded_none は名指せる行が 1 つも無いか"""
    rows = [r for r in rows or [] if isinstance(r, dict)]
    of = {s: [r for r in rows if r.get("source") == s] for s in ("doc", "answer", "gate", "push", "settled")}
    doc = of["doc"][0] if of["doc"] else None
    out = ["- Policy document: " + (f"name `{doc['name']}:<line>` (lines 1-{doc.get('lines')}; original location: "
                                     f"{doc.get('alias') or 'none'})" if doc else "none")]
    out.append("- The request's answers:" + ("" if of["answer"] else " none"))
    out += [f"  - name `{r['name']}`: {_head(r.get('text'))}" for r in of["answer"]]
    out.append("- People's answers at the approval nodes:" + ("" if of["gate"] else " none"))
    out += [f"  - name `{r['name']}`: {_head(r.get('text'))}" for r in of["gate"]]
    if of["push"]:
        out.append("- Pushes the run took on its own, with no person answering, at an approval node or for a held question of the judgment (not a person's answer):")
        out += [f"  - name `{r['name']}`: {_head(r.get('text'))}" for r in of["push"]]
    out.append("- Settled points (the prior-decisions check):" + ("" if of["settled"] else " none"))
    out += [f"  - name `{r['name']}`: {_head(r.get('text'))}" if r.get("name")
            else f"  - (no `where`, so it cannot be named) {_head(r.get('text'))}" for r in of["settled"]]
    return "\n".join(out), not any(r.get("name") for r in rows)


# ---------------------------------------------------------------- 判定の語・返答・判定の行
def status_values(eye: str) -> dict:
    """md に入れる判定の語（seal.eye_statuses(eye) に在る語だけ。fix-needed は R1 だけ）"""
    words = seal.eye_statuses(eye)
    out = {"st_pass": seal.PASSED, "st_redesign": seal.REDESIGN, "st_unverifiable": seal.UNVERIFIABLE}
    if seal.FIX_NEEDED in words:
        out["st_fix"] = seal.FIX_NEEDED
    return out


def read_reply(place, name: str) -> tuple[dict | None, str]:
    """元 eyeverdict._read_eye。(place/<name>.json の役の返答, 読めない訳)"""
    path = pathlib.Path(place) / f"{name}.json"
    if not path.is_file():
        return None, NO_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"出力のファイルが読めない: {e}"
    return (doc, "") if isinstance(doc, dict) else (None, "出力のファイルが JSON の object でない")


def fell_text(eye: str, state: str) -> str:
    """元 eyeverdict.fell_text の、ほかの目が回ったかの尾の無い形（尾を足すかは eyes のまとめが決める）"""
    return f"{LANE[eye]} {FELL_MARK}（{eye}: {state}。ノードが落ちた）"


def verdict_row(eye: str, doc, why: str = "") -> tuple[dict, bool]:
    """元 eyeverdict._row・_off_contract・fell_text。(判定の行 {status, reason}, 返答を受けたか)。docs/design/r1.md の 0.9:
    返答が無い・読めない → unverifiable（受けていない）。判定の語が目の約束の外 → 同じく（状態は「出力の判定の語が約束の外」）。
    R1 は redesign_points の名指しで作り直しを決める（名指しが在れば redesign-needed、無いのに redesign-needed なら fix-needed、
    欄が壊れていれば unverifiable）。ほかは返答のまま"""
    if not isinstance(doc, dict):
        return {"status": seal.UNVERIFIABLE, "reason": fell_text(eye, why or NO_FILE)}, False
    if doc.get("status") not in seal.eye_statuses(eye):
        return {"status": seal.UNVERIFIABLE, "reason": fell_text(eye, "出力の判定の語が約束の外")}, False
    status, reason = doc["status"], str(doc.get("reason"))
    if seal.FIX_NEEDED not in seal.eye_statuses(eye) or status == seal.UNVERIFIABLE:
        return {"status": status, "reason": reason}, True
    named = doc.get("redesign_points")
    points = [p.strip() for p in named if isinstance(p, str) and p.strip()] if isinstance(named, list) else []
    if not points and named not in (None, []):
        return {"status": seal.UNVERIFIABLE, "reason": BROKEN_POINTS + reason}, True
    if points:
        head = "" if status == seal.REDESIGN else RAISED_BY_POINTS
        return {"status": seal.REDESIGN, "reason": f"{head}{reason}（組み直す設計の点: {'／'.join(points)}）"}, True
    if status == seal.REDESIGN:
        return {"status": seal.FIX_NEEDED, "reason": UNNAMED_REDESIGN + reason}, True
    return {"status": status, "reason": reason}, True


def headline(name: str, row: dict) -> str:
    """元 runreport._eye_word。報告の頭の 1 行 「<R の名>: <status>（<reason の 1 行>）」"""
    return f"{name}: {row['status']}（{oneline.one_line(row.get('reason') or '理由なし')}）"
