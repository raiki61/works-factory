"""借りたスキルの座: 借りた superpowers の節（lib/borrow/seams.json の 1 項目）を、修正のブロックの役の指示書に載せる 1 節の
文を組む。元 works/.shared/core/seat.py（修正役の並べの枝の座と、下請けのファイルを単位の worktree で読む決まりは、枝が無いので外した）。

語:
- 節（seam）: seams.json の 1 項目。use_as が skill（スキル 1 本を Skill の道具で読ませる）か prompt（部品の型の穴を埋めて指示書に置く）
- 座: 節を役に載せる口。SEATS（役の名 → 節の名）が表で持つ
- 読み替え: overlay_body（lib/borrow/unattended.md の、役の種類 OVERLAY_KINDS の節と共通の文）。頭の 1 行は各 md が持つ

口:
- carries(node)・SKILL_NODES: 座が載る役・座が skill の役（YAML の skills: と一致）
- pinned(): 写しが固定（borrow.json の superpowers.pin）と合うかを照らし (借りる物, 写しの置き場) を返す
  （合わなければ ValueError。照らしは spseam.pin_problems）
- fill(seam_id, values): 固定と照らした写しの、部品の型の穴を埋めた本文（spseam.fill）
- overlay_body(kinds): 読み替えの種類の節と共通の文だけを残した字
- NONE・VERDICT_WORDS: 型の穴に入れる物が無い時の値と、差分の審査役の型の出口の語 → 2 判定の欄（delta-review が使う）
座の文の組み立て（前の section・words_table と見出し・決まった文）、下請けの指示（前の g1_prompt・g1_section・g1_diff_cmd と G1_*）、
検索語の規律（前の query_rule。共通の断片 query-rule.md）は fix・delta-review の md と fix の prompts/sub/ に在る（integration.md 4.3-13・
4.3-追加-1）。

写しと節の表は spseam の置き場 BORROW_DIR のファイルを読む（起動の bin/_lib/toolset.py が同じ写しを run の隔離した設定へ
写す。写しを変えるのは toolset の vendor だけ）。食い違い・型の穴の埋め残りは ValueError で名指す。
"""
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True

import spseam  # noqa: E402

SEATS = {"tdd": "tdd", "tdd-new": "tdd", "fix": "implementer", "fix-ruled": "implementer", "review": "task-review",   # 役の名 → 節の名
         "refix": "receiving-review", "refix2": "receiving-review"}
SKILL_NODES = frozenset({"tdd", "tdd-new", "refix", "refix2"})   # 座が skill の役（YAML の skills: を持つ節。試験が一致を縛る。
# tdd と tdd-new は TDD の輪の同じ役を同じ単位の続きと新しい単位に分けた 2 つの節。元も tdd・tdd-rest・tdd-lane-<n> を並べた）
# 読み替え（unattended.md）の役の種類。`###` の見出しが `・` で並べる名で、見出しの外の文は全部の役に共通
FIX, TDD, REFIX, REVIEW, READER = "修正の役", "TDD の役", "手直しの役", "審査の役", "読むだけの役"
KINDS = (FIX, TDD, REFIX, REVIEW, READER)
# 読み替えを載せる役 → 受ける種類。TDD の輪の役は修正の役の決まりを返答の欄の読み替え（指示書の tdd-remap）つきで受ける。
# local-review は素材集めの局所レビュー（指示書の末尾に overlay_body の字を置く。tests/workflows/test_judge.py が照らす）
OVERLAY_KINDS = {"tdd": (FIX, TDD), "tdd-new": (FIX, TDD), "fix": (FIX,), "fix-ruled": (FIX,), "review": (REVIEW, READER),
                 "refix": (REFIX,), "refix2": (REFIX,), "local-review": (READER,)}
NONE = "（無し）"   # 型の穴に入れる物が無い時の値（人の方針の文書が無い run の [GLOBAL_CONSTRAINTS] など）
# 差分の審査役の型（task-review）の出口の語（216 の works の語）→ 差分の審査の返答の 2 判定の欄（deltamarks.KEYS）と欄の語
# （deltamarks.COMPLIANCE・QUALITY）。審査役の座の型の後ろに words_table の表で載り、役は型の語をこの欄に書く
VERDICT_SEAM = "task-review"
VERDICT_WORDS = {"compliance_pass": ("compliance", "pass"), "compliance_fail": ("compliance", "fail"),
                 "compliance_unverifiable": ("compliance", "unverifiable"),
                 "quality_pass": ("quality", "pass"), "quality_fail": ("quality", "fail")}
ITEM = "superpowers"   # borrow.json の借りる物の名


def carries(node: str) -> bool:
    """役 node に座が載るか"""
    return node in SEATS


def skill_of(seam: dict) -> str:
    """use_as が skill の節の files[0]（skills/<名>/…）の <名>。skill の節でなければ ValueError"""
    files = seam.get("files") or []
    parts = pathlib.PurePosixPath(files[0]).parts if files else ()
    if seam.get("use_as") != "skill" or len(parts) < 3 or parts[0] != "skills":
        raise ValueError(f"スキルのセクションでない（use_as {seam.get('use_as')!r}・files {files}）")
    return parts[1]




def pinned() -> tuple[dict, pathlib.Path]:
    """借りる物（borrow.json の superpowers）と写しの置き場（superpowers/<pin の版>）。写しが固定と合わなければ ValueError
    （spseam.pin_problems を名指す）。支度は書き込みの前にこれを呼ぶ"""
    item = json.loads((spseam.BORROW_DIR / "borrow.json").read_text(encoding="utf-8"))[ITEM]
    src = spseam.BORROW_DIR / ITEM / str((item.get("pin") or {}).get("version") or "")
    bad = spseam.pin_problems(src, item)
    if bad:
        raise ValueError(f"借りた写し {src} が固定（borrow.json の pin）と合わない: {'; '.join(bad)}")
    return item, src


def fill(seam_id: str, values: dict[str, str]) -> str:
    """部品の節（use_as が prompt）の型の穴を全部 values で置き換えた本文（spseam.fill）。写しが固定と違う・値の鍵が穴と違う・
    置き換えの後に穴でも埋めない語でもない角括弧の語が残れば ValueError"""
    item, src = pinned()
    return spseam.fill(seam_id, values, src, item)


def overlay_body(kinds) -> str:
    """読み替えの正本の字から、種類の節（`###` の見出し）のうち kinds のどれかを名指す物と、種類の見出しの外の文だけを残した字。
    残る物が見出しだけになった決まり（`##`）は見出しごと落とす。見出しが KINDS の外の名を名指せば ValueError"""
    path = spseam.BORROW_DIR / spseam.OVERLAY_FILE
    groups = []   # 見出しの外の塊（頭の文か決まり 1 つ）ごとに、その塊と残す種類の節
    for block in re.split(r"(?m)^(?=##+ )", path.read_text(encoding="utf-8")):
        head = block.partition("\n")[0]
        if not head.startswith("### "):
            groups.append([block])
            continue
        named = set(head.removeprefix("### ").split("・"))
        if named - set(KINDS):
            raise ValueError(f"{path} の種類の見出し {head!r} が知らない種類 {sorted(named - set(KINDS))} を名指す")
        if named & set(kinds):
            groups[-1].append(block)
    bare = [g for g in groups if len(g) == 1 and g[0].startswith("## ") and not g[0].partition("\n")[2].strip()]
    return "".join("".join(g) for g in groups if g not in bare).rstrip("\n") + "\n"
