"""機能の切り替え（入力 features_off・features_on）の語と読み（元は今の works の works/.shared/core/entry.py の 420-514 行の塊）と、
出口の語（入力 deliver）の一覧と読み。

線の入口の節（workflows/line/scripts/start.py）が入力の語を確かめ、始めの記録に置き、ブロックへ渡す機能ごとの on・off・auto を作る。
依頼の行の型（REQUEST_SCHEMA・request_problems）も入口の節が依頼のファイルを読む時に当てる。
元のファイルのほかの物（盤面の口・CI の節）は盤面に届くので持ってこない（docs/plans/2026-10-12-lib-port.md の
移し方 2・3）。
"""
import pathlib
import re
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_HERE / "graphloops"))   # 写しの engine（carry と同じ足し方）

from engine.schema import validate_schema  # noqa: E402
import oneline  # noqa: E402

# 元 works/.shared/core/script_io.py 83-84 行（script_io は持ってこないので、塊が読む語だけを元の字のまま写す）
SWITCH_ON, SWITCH_OFF = "on", "off"   # 部品の切り替えの入力の語（線が run ごとに機能を切る口。空は on）
SWITCH_AUTO = "auto"                  # 自動を持つ切り替え（switch_auto）だけが受ける語（部品が自分の材料で on・off を決める）


# 入力 features_off が切る機能・features_on が入れる機能（持ち主の依頼 2026-10-07: 同じ依頼を機能を替えて回して比べる）。
# 語は線の入力の語で、線がブロックへ on・off・auto の平の入力（start の出口の同じ名の欄）に写す。並びは語の順（控えと報告の並びも同じ）
WORLD_FEATURE = "world"   # 世界の解の段の機能の語（ブロックへは写さず、線の境の節が始めの記録を cut_of で読む）
FEATURES = {
    "fix_lanes": "修正役の並べの枝（範囲の在る項目を修正のループの前の枝のループで単位の worktree ごとに同時に直す。切ると項目を作業ツリーで順に直す）",
    "graph_map": "グラフの地図（印の旗 map の役の system prompt に、包みが全体のグラフとその役の居場所を足す。切ると足さない。"
                 "サブグラフへは写さず、包みが start の控えを読む）",
    "judge_verify": "判定の裏取り（単位ごとの裏取りと単位どうしの相乗りの下請け。切ると申し送りを作らない。既定は off）",
    "review_tree": "事前審査の項目ごとの木（項目ごとの下請けと相乗りの審査。切ると審査役 1 つが案の全体を審査する。既定は auto＝"
                   "開いた項目が 2 つ以上の往復だけ木）",
    "tdd_lanes": "TDD のループの並べの周（枝ごとの worktree で枝の単位を同時に直す。切ると単位を順に回す）",
    WORLD_FEATURE: "世界の解の段（目的の後・判定の前に 1 回、依頼の行を問題の類に言い直して世の中の定石を集め、依頼の解き方と比べる。"
             "切ると段を回さず、判定・修正案・承認ノードは世界の解の行なしで進む。サブグラフへは写さず、境のノードが始めの記録を読む）",
}
# 名指さない機能の既定（持ち主の決め 2026-10-08。測り: 判定の裏取りは 27 単位の 11 run で後の段を 1 度も変えず 1 run に
# 0.6〜3 USD と 1〜2 分、事前審査の木は審査役 1 つの 2〜3 倍の費用で審査役 1 つが見逃した本物の穴を出さなかった）。ほかの機能は on。
# auto はブロックが自分の材料で決める語（事前審査の木: 開いた項目が 2 つ以上の往復だけ木）。名指した語（features_on・features_off）は既定に勝つ
FEATURE_DEFAULTS = {"judge_verify": SWITCH_OFF, "review_tree": SWITCH_AUTO}
FEATURES_KEY = "features_off"   # start の控えの欄（語の順の配列）
FEATURES_ON_KEY = "features_on"   # 同じく入れる機能の欄（欄の無い控えは前の版の run。features_on_of が読む）
# start の控えの実効で off の機能の欄（既定で off の機能を含む語の順の配列。包みが工程の地図で読む。欄の無い控えは前の版で、
# 前の版の既定は全部 on なので features_off の語だけが off）
FEATURES_CUT_KEY = "features_cut"


class InputRefused(Exception):
    """入力を受けない（AI を起こす前に run を止める）。文は人に向けた 1 行"""

    def __init__(self, msg):
        super().__init__(oneline.one_line(msg))


def _feature_list(word: str, key: str) -> list:
    """入力 key（機能の語をカンマか空白で区切った 1 行）を、語の順に重ねずに並べた配列にする。FEATURES の外の語は名を言って
    InputRefused（黙って切らずに・入れずに回さない）"""
    words = [w for w in re.split(r"[\s,、・]+", word or "") if w]
    bad = [w for w in dict.fromkeys(words) if w not in FEATURES]
    if bad:
        raise InputRefused(f"{key} に知らない機能 {', '.join(bad)}（名指せるのは {' / '.join(FEATURES)}）")
    return sorted(set(words))


def features_off(word: str) -> list:
    """入力 features_off（切る機能。空は既定 FEATURE_DEFAULTS のまま）の語の配列"""
    return _feature_list(word, FEATURES_KEY)


def features_on(word: str) -> list:
    """入力 features_on（入れる機能。既定で off・auto の機能を on にする。空は既定のまま）の語の配列"""
    return _feature_list(word, FEATURES_ON_KEY)


def feature_words(off, on=(), adds=()) -> dict:
    """start の出口の機能ごとの欄 {<機能>: on | off | auto}（線がブロックの切り替えの入力へ写す）。名指した語が足しに、足しが既定に勝つ:
    features_on の語は on・features_off の語は off・adds（run の頭の深さの段が足す機能。depth.tier_adds）の語は on・どれにも無ければ
    FEATURE_DEFAULTS（無ければ on）。features_on と features_off の両方に在る語と、名指した段の足しを features_off で切る組は入口の
    節（start）が拒むので届かない（features_off が足しに勝つのは、入口の後に head-depth が選んだ段の足しだけ）"""
    off, on, adds = set(off or ()), set(on or ()), set(adds or ())
    return {name: SWITCH_ON if name in on else SWITCH_OFF if name in off else SWITCH_ON if name in adds
            else FEATURE_DEFAULTS.get(name, SWITCH_ON) for name in FEATURES}


def switch(doc, name: str, adds=()) -> str:
    """始めの記録 doc の機能 name の語（on・off・auto）を feature_words と同じ式で返す。doc の欄 features_off・features_on の名指しと
    adds だけを読み、記録が無い・欄が無ければ名指し無しとして FEATURE_DEFAULTS を返す"""
    doc = doc if isinstance(doc, dict) else {}
    return feature_words(doc.get(FEATURES_KEY) or [], doc.get(FEATURES_ON_KEY) or [], adds)[name]


def features_cut(off, on=(), adds=()) -> list:
    """実効で off の機能の語（語の順。start の控えの FEATURES_CUT_KEY）"""
    return [k for k, v in feature_words(off, on, adds).items() if v == SWITCH_OFF]


def cut_of(doc: dict) -> set:
    """start の控え doc の実効で off の機能（欄 FEATURES_CUT_KEY。欄の無い前の版の控えは、前の版の既定が全部 on なので
    features_off の語だけ）"""
    key = FEATURES_CUT_KEY if isinstance(doc, dict) and FEATURES_CUT_KEY in doc else FEATURES_KEY
    return set((doc or {}).get(key) or []) if isinstance(doc, dict) else set()


def features_on_of(doc: dict) -> list:
    """start の控え doc の入れた機能。features_on の欄の無い控えは前の版の run で、その版の既定は全部 on なので、既定で
    on でない機能のうち features_off に無い物を入れた物と読む（呼び直しと報告で腕を黙って替えない）"""
    if FEATURES_ON_KEY in doc:
        return list(doc.get(FEATURES_ON_KEY) or [])
    off = set(doc.get(FEATURES_KEY) or [])
    return sorted(k for k in FEATURE_DEFAULTS if k not in off)


def features_part(off, on=(), adds=()) -> str:
    """頭の行と報告の冒頭 2 の機能の語: on でない機能を語の順に「<機能> <off|auto>」で並べる（全部 on なら「機能: 全部 on」）"""
    rest = [f"{k} {v}" for k, v in feature_words(off, on, adds).items() if v != SWITCH_ON]
    return f"機能: {'・'.join(rest)}" if rest else "機能: 全部 on"


# 出口の語（入力 deliver。対象へどう渡すか）。空は封じた差分を run の置き場に置くだけ（既定。持ち主の決め diff-only-to-target）、
# pr は run の枝に積んで PR まで作る（対象の既定の枝へは push しない・merge しない）。メイングラフと周の鎖の始めのノードと merge が読む
DELIVER_DIFF, DELIVER_PR = "", "pr"
DELIVERS = (DELIVER_DIFF, DELIVER_PR)


def deliver_word(word: str) -> str:
    """入力 deliver の語（前後の空白を除く）。DELIVERS の外の語は InputRefused"""
    word = (word or "").strip()
    if word not in DELIVERS:
        raise InputRefused(f"deliver={word!r} は知らない語（空か {DELIVER_PR}）")
    return word


# 元 works/.shared/core/graphloops/rules/review-loop.py 90-96 行（依頼の周ごとのバッチの一覧の型。字は元のまま）
REQUEST_SCHEMA = {"type": "array", "items": {
    "type": "object", "required": ["round", "origin", "findings"], "additionalProperties": False, "properties": {
        "round": {"type": "integer", "minimum": 1},
        "origin": {"type": "string", "minLength": 1},
        "findings": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["where", "text"], "additionalProperties": False,
            "properties": {k: {"type": "string"} for k in ("where", "text", "mechanism", "measured", "false_positive_if")}}}}}}
ORIGIN = "works-factory"   # 依頼の出どころ（型が空でない字を求めるだけ。元は works/darkfactory）


def request_problems(items: list) -> list:
    """依頼の行 items が依頼の型（REQUEST_SCHEMA の findings）に合わない訳の並び。合えば空。元 works/.shared/core/entry.py 634 行"""
    return validate_schema([{"round": 1, "origin": ORIGIN, "findings": items}], REQUEST_SCHEMA)
