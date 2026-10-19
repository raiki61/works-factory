"""観点 procedure-trace（手順トレース）の宣言（docs/design/materials.md の 5.1・docs/design/procedure-trace.md の 1.5）。

対象差分が手順書・スクリプト・CI 定義に触れる run で、役に変更されたそれらの全文を読み、状態を変えない範囲で動かして確かめさせる。
触れない run では役を起こさず、理由つきの not_applicable を機械が書く。受け付けの流れと出口は lib/materialkit が持ち、ここは
宣言だけを持つ。
"""
import json
import re

import materialkit  # lib/
import oneline  # lib/

NAME = "procedure-trace"
MATERIALS = ("procedure_trace",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "cond"
NA_REASON = "対象差分に手順書・スクリプト・CI 定義の変更が無い"
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
# 写す元 lib/judge_accept.py の PROCEDURE_PATTERNS（元 rules:367）。組み込みで lib の側が消えるまで 2 つ在る
PROCEDURE_PATTERNS = (r"README", r"\.md$", r"\.sh$", r"^scripts/", r"^\.github/workflows/", r"Makefile", r"Dockerfile",
                      r"\.ya?ml$", r"^commands/", r"^hooks/")


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def procedure_files(view) -> list:
    """変更ファイルのうち、手順のファイル（PROCEDURE_PATTERNS のどれかに当たる物）"""
    return sorted({f for f in view.changed_files for p in PROCEDURE_PATTERNS if re.search(p, f)})


def applies(view, values) -> materialkit.Due:
    hit = procedure_files(view)
    return materialkit.Due(bool(hit), f"差分に手順書・スクリプト・CI 定義が {len(hit)} 件" if hit else "差分に手順書・スクリプト・CI 定義が無い")


def due(view, values) -> materialkit.Due:
    if materialkit.is_entry_run(view, values):
        return materialkit.entry_skip("手順の追跡")
    ok, why = applies(view, values)
    if ok:
        return materialkit.Due(True, f"対象差分に手順書・スクリプト・CI 定義の変更が在る（{why}）——手順の追跡を回す")
    return materialkit.Due(False, f"{NA_REASON}（{why}）——手順の追跡を起こさない")


def fill(view, values, due) -> dict:
    # 回さないのは、手順のファイルに触れない時と、判定から入る run の周（差分が空）の時。後者も差分が空なので、触れない
    # 文が入る（今の _fill_one は入口の run でも条件外の文を入れる）
    return {"procedure_trace": materialkit.fill_na(NA_REASON, applies(view, values).why)}


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    own, theirs = materialkit.review_md_paths(view.repo)
    # 対象の REVIEW.md が無い時も空の字で渡す（指示を組む口は選ばれない段落の中の差し込み口にも値を要る）
    return {"repo": str(view.repo), "diff_file": view.diff_file, "changed_files": _dump(list(view.changed_files)),
            "review_md": own, "repo_review_md": theirs}


def when(view, values) -> dict:
    return {"spawns": False, "repo_review": bool(materialkit.review_md_paths(view.repo)[1])}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"procedure_trace": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    if not isinstance(reply, dict):
        return []
    found = [f"  - 所見: {oneline.one_line(r.get('where') or '')}: {oneline.one_line(r.get('text') or '')}"
             for r in reply.get("findings") or [] if isinstance(r, dict)]
    return found + [f"  - 未実測: {oneline.one_line(r)}" for r in reply.get("unmeasured") or [] if isinstance(r, str)]
