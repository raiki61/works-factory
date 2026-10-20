"""局所レビューのレンズ（検出器 1 本）の宣言と、レンズに関わる照らし（docs/design/local-review.md の 1.5）。

**なぜ見ていないレンズの印が要るか（実測 2026-10-08、利用者の run f57a5374 ほか 6 つの会話の記録）。** 組み込みの skill code-review は
fork（下請けの会話）で走る。返答の道具 StructuredOutput を継いだ fork は所見をそこへ書いて終わり、親の Skill の結果は
『Skill execution completed』だけになった。局所レビューの役は /code-review の行を items 空・failed に『本文なし』で返し、
レンズと行の照らし（covers_lenses）は行が在れば通すので、消えた所見は「見たが所見なし」と同じ形で記録に入った
（f57a5374 では 10 件。うち 1 件は 2 run 後に阻害になった）。

包みの旗で返答の型を本文に受ける道を取ると、子にも fork にも返答の道具が無く、/code-review は所見を本文で返す。それでも
/code-review の行が空なら、本文で返った 0 件と届かなかった物を見分けられない。そこで受け付けは FORK_LENSES の空の行を
「所見なし」でなく「見ていない」と印を付けて受ける（mark_unseen。起こし直しても同じ形で落ちるので拒まない）。見ていない、は
控え LENS_FILE に残し、出口の report の行にする（unseen_lines）。

公開の名:
- LENSES・SIMPLIFY_LENS・SECURITY_COND・SECURITY_WHY・applies・skills: レンズの宣言と、この run の評価を足した物
- FORK_LENSES・UNSEEN_TAG・LENS_FILE・mark_unseen・unseen・unseen_lines: 見ていないレンズの印と控えと報告の行
- installed_plugins・lens_gap・covers_lenses: 必須のレンズの照らし、レンズと行の照らし

写す元は lib/judge_accept.py（LOCAL_REVIEW_SKILLS・_lens_gap・local_review_covers_lenses・_installed_plugins）と
lib/diverted.py。振る舞いは変えない（違いは各関数の docstring）。
"""
import copy
import os
import pathlib

import jsonfile

LENSES = (
    {"skill": "/code-review", "args": "high", "required": True},
    {"skill": "pr-review-toolkit:code-reviewer", "required": True},
    {"skill": "/simplify", "required": True},
    {"skill": "/security-review", "required": False, "applies_cond": "security_surface_touched"},
    {"skill": "pr-review-toolkit:silent-failure-hunter", "required": True},
    {"skill": "pr-review-toolkit:type-design-analyzer", "required": True},
    {"skill": "pr-review-toolkit:pr-test-analyzer", "required": True},
)
SIMPLIFY_LENS = "/simplify"
SECURITY_COND = "security_surface_touched"
# 今の機械は差分の柵を決められないので、条件 security_surface_touched をいつも真に倒す（役を起こす側に倒す）。理由はこの字
SECURITY_WHY = "差分が認証・データの取り扱い・外部との入出力に触れる"
# fork で走り、返答が親に届かないと実測したレンズ。空の行は「所見なし」に数えない
# （/simplify・/security-review は親の会話の中で走る。実測の Skill の所要 14 ミリ秒・256 ミリ秒）
FORK_LENSES = ("/code-review",)
UNSEEN_TAG = "【works: 所見を受け取れていない——このレンズは見ていないのと同じに扱え】"
LENS_FILE = "lenses.json"


def applies(cond: str) -> tuple:
    """条件 cond をこの run で評価した (真偽, 理由)。1 run は 1 周で、security_surface_touched はいつも真"""
    if cond == SECURITY_COND:
        return True, SECURITY_WHY
    raise ValueError(f"知らないレンズの条件: {cond!r}")


def skills() -> list:
    """LENSES の写しに、条件 applies_cond を持つ物だけ applies・applies_why を足した並び（写す元 judge_accept._skills から note を除いた物）"""
    out = []
    for e in LENSES:
        e = dict(e)
        if "applies_cond" in e:
            e["applies"], e["applies_why"] = applies(e["applies_cond"])
        out.append(e)
    return out


def mark_unseen(reply: dict, skills: list) -> tuple:
    """写す元 diverted.mark_unseen（字のまま）。宣言の skill のレンズ（/ で始まる名）のうち FORK_LENSES の行が items 空で invoked なら、
    failed の頭に UNSEEN_TAG を置き、material の文の欄（checked・detail・reason）にも同じ印を足した写しを返す。親の会話で走った
    レンズの行は役の申告のまま。返り (印を付けた返答の写し, 控え {unseen})。受けた返答は書き換えない"""
    out = copy.deepcopy(reply)
    notes = {"unseen": []}
    lenses = {e["skill"] for e in skills if isinstance(e.get("skill"), str) and e["skill"].startswith("/")}
    mat = out.get("material") if isinstance(out.get("material"), dict) else None
    for row in out.get("findings") or []:
        lens = row.get("skill") if isinstance(row, dict) else None
        if lens not in lenses or lens not in FORK_LENSES or row.get("items") or row.get("invoked") is not True:
            continue
        row["failed"] = f"{UNSEEN_TAG} {str(row.get('failed') or '')}"
        notes["unseen"].append(lens)
        if mat is not None:
            for k in ("checked", "detail", "reason"):
                if isinstance(mat.get(k), str):
                    mat[k] = f"{mat[k]}（{lens}: {UNSEEN_TAG}）"
    return out, notes


def unseen(reply: dict) -> list:
    """印を付けた後の返答から、見ていないレンズの名の並び（mark_unseen の控え notes["unseen"] と同じ物）"""
    return [row["skill"] for row in reply.get("findings") or []
            if isinstance(row, dict) and isinstance(row.get("failed"), str) and row["failed"].startswith(UNSEEN_TAG)]


def unseen_lines(names) -> list:
    """報告の行（写す元 diverted.report_lines の行の字）"""
    return [f"局所レビューの {n}: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ" for n in names]


def installed_plugins() -> set | None:
    """写す元 judge_accept._installed_plugins。役が読む隔離した設定（環境変数 CLAUDE_CONFIG_DIR）に入っているプラグインの名。
    読めなければ None"""
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    doc = jsonfile.read_or(pathlib.Path(cfg) / "plugins" / "installed_plugins.json") if cfg else None
    plugins = doc.get("plugins") if isinstance(doc, dict) else None
    return {k.split("@", 1)[0] for k in plugins} if isinstance(plugins, dict) else None


def _status(reply: dict) -> str:
    mat = reply.get("material")
    return mat.get("status", "") if isinstance(mat, dict) else ""


def lens_gap(skills: list, reply: dict) -> tuple | None:
    """写す元 judge_accept._lens_gap。必須のレンズを起こしていない・material を awaiting_human にした返答の (拒みの文, 出し直さないか)。
    なければ None。違い（振る舞いは同じ）: 持ち越しの変数 carry_ok を外した（1 run は 1 周で、/simplify の持ち越しはいつも受けない）・
    プラグインの入れ直しの道を bin/_lib/toolset.py install に直した"""
    rows = {r.get("skill"): r for r in reply.get("findings") or [] if isinstance(r, dict)}
    missing = [e["skill"] for e in skills if e.get("required", True) and (rows.get(e["skill"]) or {}).get("invoked") is not True]
    if not missing:
        return None
    errs = [f"'{s}' は必須のレンズなのに invoked が true でない"
            + ("（simplify_carried: true の持ち越しはこの run では受けない）" if s == SIMPLIFY_LENS else "")
            for s in missing]
    if _status(reply) == "awaiting_human":
        errs.append("必須のレンズが起きていない返答が material を awaiting_human にした")
    installed = installed_plugins()
    absent = sorted({s.split(":", 1)[0] for s in missing if ":" in s and not s.startswith("/")} - installed) \
        if installed is not None else []
    if absent:
        errs.append(f"隔離した設定（{os.environ.get('CLAUDE_CONFIG_DIR')}）にプラグイン {'・'.join(absent)} が入っていない——"
                    "起こし直しても毎回落ちるので出し直さずに人に渡す（bin/_lib/toolset.py install で入れ直してから続ける）")
    return "宣言したレンズと findings の行が合わない:\n" + "\n".join("  - " + e for e in errs), bool(absent)


def covers_lenses(skills: list, reply: dict) -> str | None:
    """写す元 judge_accept.local_review_covers_lenses。宣言したレンズ 1 本につき findings の行を 1 本、例外なく要求する。
    skills は skills() の宣言（applies つき）。拒む文を返す（通れば None）。違い: Reject を上げず文を返す・graph を名指す句を外した"""
    if not skills:
        return "宣言したレンズが空——数える対象が無い柵は全件合格になる"
    declared = [e["skill"] for e in skills]
    rows = reply.get("findings") or []
    seen, errs = {}, []
    for i, row in enumerate(rows):
        name = row.get("skill", "")
        if name in seen:
            errs.append(f"findings に同じ skill の行が 2 本: {name}")
        seen[name] = row
        if name not in declared:
            errs.append(f"findings[{i}] の skill '{name}' は宣言のレンズ（{declared}）に無い")
    for name in declared:
        row = seen.get(name)
        if row is None:
            errs.append(f"宣言した '{name}' の行が findings に無い")
        elif not row.get("items") and not (row.get("failed") or "").strip():
            errs.append(f"'{name}' の行が items も failed も持たない")
    awaiting = _status(reply) == "awaiting_human"
    for e in skills:
        row = seen.get(e["skill"])
        if row is None or "applies_cond" not in e or not e.get("applies", True) or awaiting:
            continue
        if row.get("invoked") is not True:
            errs.append(f"'{e['skill']}' は条件 {e['applies_cond']} が真の周（{e.get('applies_why', '評価の値が無いので当てる側に倒した')}）"
                        "なのに invoked が true でない")
    return ("宣言したレンズと findings の行が合わない:\n" + "\n".join("  - " + e for e in errs)) if errs else None
