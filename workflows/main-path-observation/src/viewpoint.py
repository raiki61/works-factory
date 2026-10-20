"""観点 main-path-observation（主経路の実行観測）の宣言（docs/design/materials.md の 5.1・docs/design/main-path-observation.md の 1.5）。

対象差分が変えた、利用者から見える経路か外部との継ぎ目を、作業ツリーの外の写しで実際に 1 回動かさせ、通った値の観測の行（observed）と
素材 main_path_observation を返させる。判定から入る run 以外はいつも回し（差分が経路に触れるかは機械が決められないので、触れる側に倒す）、
『条件に当たらない』は当たる条件がいつも真なので名乗れない。受け付けの流れと出口は lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import materialkit  # lib/
import oneline  # lib/

NAME = "main-path-observation"
MATERIALS = ("main_path_observation",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "cond"
NA_REASON = "対象差分は利用者から見える経路・外部との継ぎ目を変えていない"
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
NOUN = "主経路の観察"
NO_OBSERVED = ("観点 {name}: status={st} なのに観測した値（observed）が 1 つも無い——動かして観測した経路と値を observed に書け。"
               "動かせなかったなら awaiting_human（何を待つか）か not_run（なぜ飛ばしたか）")


def due(view, values) -> materialkit.Due:
    if materialkit.is_entry_run(view, values):
        return materialkit.entry_skip(NOUN)
    return materialkit.Due(True, "主経路の観察は、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回。"
                                 "差分が利用者から見える経路に触れるかは機械が決められないので、触れる側に倒す）")


def fill(view, values, due) -> dict:
    # 依頼の件数はこの観点に渡されない（None）。due が偽になるのは判定から入る run だけ
    return {"main_path_observation": materialkit.fill_entry(values["entry"], None)}


def applies(view, values) -> materialkit.Due:
    return materialkit.Due(True, "差分が利用者から見える経路に触れる")


def judged_na(view, values) -> bool:
    return False


def values(view, values) -> dict:
    return {"diff_file": view.diff_file, "changed_files_file": view.changed_files_file, "repo": str(view.repo)}


def when(view, values) -> dict:
    return {"spawns": False}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    material = reply.get("material")
    st = material.get("status") if isinstance(material, dict) else None
    if st in materialkit.OBSERVED_STATUS and not reply.get("observed"):
        return NO_OBSERVED.format(name=NAME, st=st)
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"main_path_observation": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    rows = reply.get("observed") if isinstance(reply, dict) else None
    return [f"  - 観測: {oneline.one_line(r.get('path') or '')} → {oneline.one_line(r.get('value') or '')}"
            for r in rows or [] if isinstance(r, dict)]
