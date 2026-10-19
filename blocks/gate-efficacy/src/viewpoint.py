"""観点 gate-efficacy（ゲートの実効性確認）の宣言（docs/design/materials.md の 5.1・docs/design/gate-efficacy.md の 1.5）。

対象差分が新設・変更した検証ゲートを、リポジトリの写しの上で腕ごとに壊して赤・対照の緑・守る行の通過を測らせ、腕ごとの結果（arms）と
素材 gate_efficacy を返させる。合流の道（gates が merge）と判定から入る run では役を起こさず、理由つきの素材の状態を書く。ゲートの印が
無い差分では、役の『条件に当たらない』を受ける。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/
import oneline  # lib/
import recount  # lib/

from src import arms, mutation, signals

NAME = "gate-efficacy"
MATERIALS = ("gate_efficacy",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "cond"
NA_REASON = "対象差分は検証ゲート（CI ジョブ・assert・テスト・pre-commit）を新設・変更していない"
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
GATES_MERGE = "merge"
GATES_MERGE_WHY = "変異の検算は合流した版でまとめて 1 回撃つ（init --input gates=merge）"


def due(view, values) -> materialkit.Due:
    if values.get("gates") == GATES_MERGE:
        return materialkit.Due(False, GATES_MERGE_WHY)
    if values.get("entry"):
        return materialkit.entry_skip("ゲートの検算")
    return materialkit.Due(True, "ゲートの検算は合流の道でも判定から入る run でもない run で回す"
                                 "（差分の形の申告 touches_gates は機械が真に倒す。1 run は 1 周で、いつも初回）")


def fill(view, values, due) -> dict:
    if values.get("gates") == GATES_MERGE:
        return {"gate_efficacy": {"status": "not_applicable",
                                  "reason": f"{GATES_MERGE_WHY}——差分はゲートに触れているが、この run では撃たない。"
                                            "合流した版を gates=merge 無しの run で回し、そこの P1 のゲートの検算が撃つ"}}
    if values.get("entry"):
        return {"gate_efficacy": materialkit.fill_entry(values["entry"], None)}
    raise NotImplementedError("回す時の素材の埋めは呼ばれない")


def applies(view, values) -> materialkit.Due:
    return materialkit.Due(True, "差分が検証ゲートに触れる")


def judged_na(view, values) -> bool:
    """ゲートの印（signals）が差分に 1 つも無い時だけ、役の『条件に当たらない』を受ける。差分を読めなければ受けない"""
    got = signals.signals_of(view)
    return False if got is None else not got


def values(view, values) -> dict:
    m = mutation.state(view.repo)
    return {"repo": str(view.repo), "base": view.base, "diff_file": view.diff_file,
            "changed_files_file": view.changed_files_file, "decl_name": mutation.DECL_NAME,
            "mutation_argv": m["argv"], "mutation_arms": m["arms"],
            "mutation_error": "" if m["declared"] else m["error"]}


def when(view, values) -> dict:
    m = mutation.state(view.repo)
    return {"spawns": False, "mutation_declared": m["declared"], "mutation_undeclared": not m["declared"],
            "mutation_unreadable": (not m["declared"]) and bool(m["error"])}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return arms.arms_problem(NAME, reply)


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"gate_efficacy": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    if not isinstance(reply, dict):
        return []
    seen = lambda ok: "見た" if ok else "見ていない"   # noqa: E731
    return [f"  - 腕: {oneline.one_line(a.get('arm') or '')}（{oneline.one_line(a.get('gate') or '')}。"
            f"赤 {seen(a.get('red_confirmed'))}・対照の緑 {seen(a.get('control_green'))}・"
            f"守る行の通過 {seen(not recount.blank(a.get('hit_evidence'), 10))}）"
            for a in reply.get("arms") or [] if isinstance(a, dict)]
