"""判定の出力の行の形（単位の「直す義務が残るか」）の住処。作り手は diagnose、読み手は verify・plan・fix（docs/design/integration.md の 4.4-H）。

単位は judgment の units の 1 行 {key, label, disposition?, …}。手本は worldmark（作り手の出力ごとに lib の 1 モジュール）。

- is_open(u): 単位が今の周に直す義務を残すか（label が block、か label が suggest で disposition が do-now）
- open_units(judgment): 判定の開いた単位の並び（key が字の dict の行だけ。判定の順）
- 直す義務と計画の周が役を起こすかの決め（plan の周を開く口と line の node owed が共に引く 1 か所。統合の設計書の「持ち主の決め」の
  `planfile.round_inputs`・`held_why`。converge は gatemarks を import しない決まりなので、gatemarks.duty を呼ぶこの住処に置いた）:
  with_ledger(doc, ...)（判定に問いの台帳の見え方を添える）・owed_units(judgment)（今の周に直す義務の単位の key）・units_of・slots・
  plan_slots（必ず入れる・入れてよい・単位の表）・plan_stuck_reason（行き止まりの理由）・held_why（周が役を起こさない訳。起こすなら空）
"""

BLOCK = "block"
SUGGEST = "suggest"
DO_NOW = "do-now"


def is_open(u) -> bool:
    """単位が直す義務を残すか。label の無い単位（共通の形は label を要らない）は閉じた物として扱う"""
    if not isinstance(u, dict):
        return False
    return u.get("label") == BLOCK or (u.get("label") == SUGGEST and u.get("disposition") == DO_NOW)


def open_units(judgment) -> list:
    """判定の開いた単位（直す義務の残る物）。units が無い・形が違えば空"""
    units = judgment.get("units") if isinstance(judgment, dict) else None
    return [u for u in units or [] if isinstance(u, dict) and isinstance(u.get("key"), str) and is_open(u)]


# ---------------------------------------------------------------- 直す義務と計画の周が役を起こすかの決め
NOTHING_OWED = "直す義務の単位が無い（開いた単位が無いか、全部が人の答え待ちの問いの出どころ・depends）"
PLAN_STUCK = "修正案の行き止まり: 必ず案に入れる単位が開いていない"
STUCK_WHY = ("受け付けの写しは開いていない単位を受けず、義務からも外さないので、案の形では閉じない。人が承認ノードで問いの答えを直すか、"
             "単位を開く")
LEDGER = "_ledger"   # 判定の dict に添える問いの台帳の見え方（gatemarks.Ledger）の鍵。判定の欄ではない


def with_ledger(doc, *, ties_file=None, materials_file=None, answers=(), takes_push: bool = False):
    """判定の dict に、直す義務の数え（gatemarks.duty）が読む問いの台帳の見え方（依頼の answers と、結び・素材の状態のファイルと、無人の
    run の推しを答えとして数えるか）を LEDGER の鍵で添えた dict（doc は変えない）。判定が dict でなければ None"""
    import gatemarks   # 遅く読む（gatemarks は judgmark を読まない。読み込みの輪を作らない）
    if not isinstance(doc, dict):
        return None
    return {**doc, LEDGER: gatemarks.ledger_files(doc, ties_file=ties_file or None, materials_file=materials_file or None,
                                                  answers=[a for a in answers or [] if isinstance(a, dict)], takes_push=bool(takes_push))}


def owed_units(judgment) -> set:
    """今の周に直す義務の単位の key（gatemarks.duty。fix の直す義務と同じ口）: 開いた単位から、答えていない関所の問い（人に聞く状態の
    fork と、status が escalate の問い）の出どころ・depends を除き、依頼の answers と無人の run が採った判定の推しが答えた問いの出どころ・
    depends を戻した物。問いの台帳の見え方は with_ledger が添えた物（無ければ判定だけの見え方）"""
    import gatemarks
    got = judgment.get(LEDGER)
    return gatemarks.duty(got if isinstance(got, gatemarks.Ledger) else gatemarks.ledger(judgment))


def units_of(judgment) -> dict:
    """判定の units の行（dict で key が字）の {key: 単位}（判定の順）"""
    rows = judgment.get("units") if isinstance(judgment, dict) else None
    return {u["key"]: u for u in rows or [] if isinstance(u, dict) and isinstance(u.get("key"), str)}


def slots(judgment) -> list:
    """案に入れてよい単位（開いた単位）の key を判定の順に。no は 1 始まりの位置（slots.json の並び）"""
    return [k for k, u in units_of(judgment).items() if is_open(u)]


def plan_slots(judgment) -> tuple:
    """(必ず入れる, 入れてよい, 単位の key → 単位)。受け付けの単位の網羅の照らしと材料が同じ物から作る"""
    units = units_of(judgment)
    return owed_units(judgment), {k for k, u in units.items() if is_open(u)}, units


def plan_stuck_reason(judgment) -> str:
    """必ず入れるのに開いていない単位が在れば、行き止まりの理由（PLAN_STUCK・その単位の no と key・STUCK_WHY）。無ければ空"""
    owed, opened, _ = plan_slots(judgment)
    stuck = sorted(owed - opened)
    if not stuck:
        return ""
    names = slots(judgment)
    items = "・".join(f"no {names.index(k) + 1}（{k}）" if k in names else f"no の一覧に無い単位（{k}）" for k in stuck)
    return f"{PLAN_STUCK}: {items}。{STUCK_WHY}"


def held_why(judgment) -> str:
    """判定（with_ledger の返り。読めなければ None）の、計画の周が修正案の役を起こさない訳: 判定が読めない・直す義務の単位が無い
    （NOTHING_OWED）・行き止まりの単位が在る（plan_stuck_reason）。起こすなら空"""
    if not isinstance(judgment, dict):
        return "判定が読めない"
    return NOTHING_OWED if not owed_units(judgment) else plan_stuck_reason(judgment)
