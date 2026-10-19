"""観点 test-double-fidelity（代役の忠実性）の宣言（docs/design/materials.md の 5.1・docs/design/test-double-fidelity.md の 1.5）。

対象差分が外部との継ぎ目に触れる時に、テストの代役の形が実物と合うかを、実物から取った値 1 件で確かめさせ、不一致の行（mismatches）と
素材 test_double_fidelity を返させる。回すかは判定から入る run か（materialkit.is_entry_run: entry があり、かつ対象差分が空）だけで決める（継ぎ目に触れるかは機械が決められないので、触れる側に倒す）。
受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/
import oneline  # lib/

NAME = "test-double-fidelity"
MATERIALS = ("test_double_fidelity",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "cond"
NA_REASON = "対象差分は外部との継ぎ目（別プロセス・別サービス・ブラウザ・外部 API・プロトコル）に触れていない"
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
NOUN = "代役の忠実さの確かめ"


def due(view, values) -> materialkit.Due:
    if materialkit.is_entry_run(view, values):
        return materialkit.entry_skip(NOUN)
    return materialkit.Due(True, "代役の忠実さの確かめは、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回。"
                                 "差分が外部との継ぎ目に触れるかは機械が決められないので、触れる側に倒す）")


def fill(view, values, due) -> dict:
    return {"test_double_fidelity": materialkit.fill_entry(values["entry"], None)}


def applies(view, values) -> materialkit.Due:
    return materialkit.Due(True, "差分が外部との継ぎ目に触れる")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    return {"diff_file": view.diff_file, "changed_files_file": view.changed_files_file, "repo": str(view.repo)}


def when(view, values) -> dict:
    return {"spawns": False}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"test_double_fidelity": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    rows = reply.get("mismatches") if isinstance(reply, dict) else None
    return [f"  - 代役の不一致: {oneline.one_line(r.get('text') or '')}（{oneline.one_line(r.get('where') or '')}）"
            for r in rows or [] if isinstance(r, dict)]
