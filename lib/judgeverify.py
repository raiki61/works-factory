"""判定の根を開く（元 works/blk-judge/lib/judgeverify.py。元の設計 works の docs/plans/2026-10-06-judge-verify.md）の部品。判定役が切った
開いた単位ごとに、判定役とは別の目の下請けが「本当に根本か・証拠は在るか・場所は合っているか」を確かめ、別の 1 つの下請けが
単位どうしの重複・関わり・順番を見る。束ね役（役 judge-verify）が下請けを Agent の道具で 1 つのメッセージに並べて起こし、下請けは
答えを置き場の verify/answers の下に Write で書く。単位は消さない（直す義務。根本でないと出ても申し送りと報告の行になるだけ）。
支度と束ね（lib/judge_accept.py の prep_on・merge_on）がここの名・文・型・読み書きの口を使う。

- 置き場の名（VERIFY_FILE・BRIEF_DIR・PLAN_FILE・TREE_FILE・ANSWER_FILE・SYNERGY_FILE）と語（VERDICTS・PLACES・CHECKED・UNVERIFIED）
  と裏取りを回す単位の数の下限 MIN_UNITS
- 下請けと束ね役の指示書の文（TITLE・SUB_HEAD・RULES・UNIT_HEAD・UNIT_ASK・VIEW_HEAD・SYNERGY_HEAD・SYNERGY_ASK・AGG・AGG_REPLY）
- output_format・unit_schema・synergy_schema: 束ね役の返答と答えのファイルの型
- _head・_unit_row・_initial・_load: 支度と束ねの口（開いた単位を選ぶ open_units は is_open の持ち主 judge_accept に在る。
  ここから judge_accept を読むと、ここを先に読んだ時に循環で読み込めない）
"""
import copy
import json
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
import promptsection  # noqa: E402
import oneline  # noqa: E402
from engine.schema import validate_schema  # noqa: E402  （board が写しの engine を sys.path に足した後）

ROLE = "judge-verify"                  # 束ね役の節の id と印の名
VERIFY_FILE = "judge-verify.json"      # 申し送り（今の周。manifest の produces。判定の出力の欄 verify が指す）
BRIEF_DIR = "verify"                   # 下請けのファイルと束ね役の指示書の置き場（scope の根の今の周）
PLAN_FILE = "verify/plan.json"         # 番号の控え {units: [{n, key}], answers}（支度が書き、まとめが読む）
TREE_FILE = "verify-tree.json"         # 束ね役を起こす前の作業ツリーの姿（accept.tree_state）
ANSWER_FILE = "unit-{n}.json"
SYNERGY_FILE = "synergy.json"
MIN_UNITS = 2                          # 裏取りを回す開いた単位の数の下限（1 単位は相乗りが無く、事前審査の下請けと重なる。設計書）
SUBAGENT_TYPE = "general-purpose"      # 下請けの型は 1 つ（答えのファイルを書ける型。線の木の段 1 の教訓）
CHECKED, UNVERIFIED = "checked", "unverified"
VERDICTS = ("root", "not_root", "unsure")
PLACES = ("same", "apart")              # 関わりの行の place: 同じ行・同じ塊（か前提を変える）・同じファイルの別の所だけ
WAITING = "裏取りの答えがまだ無い（束ね役が落ちたか、下請けを起こさなかった）"

UNIT_HEAD = promptsection.Section("## この下請けの単位: 単位 {n}", source="fn:judgeverify.prep_on")   # 下請けのファイルの共通の頭（全部の単位と相乗りで同じバイト）とその単位の節の境
ANSWER_AT = "Write の道具でファイル {answer} に書け"   # 下請けのファイルが答えの置き場を名指す句
TITLE = promptsection.Section("# 判定の単位の裏取りの下請け", source="fn:judgeverify._head")
SUB_HEAD = ("この役は判定の単位の裏取りの下請け（読むだけ。Read・Grep・Glob で根拠のコードを調べ、Write は最後のセクションが名指す答えの"
            "ファイルにだけ使う。Edit・Bash を使わず、作業ツリーを 1 文字も変えない）。判定役が人の修正依頼を根本の単位に切った。"
            "その切り方を判定役とは別の目で確かめる。ほかのファイルの指示書を読みに行かなくてよい（根拠のコードは読め）。")
RULES = promptsection.Section("## 決まり（全部の下請けで同じ）\n\n"
                              "- 直し方は書かない（案は別の役が作る）。\n"
                              "- 単位を消す・足す・ラベルを変える提案はしない。単位は直す義務で、この確かめでは減らない。根本でないと出ても、"
                              "申し送りとして案を書く役と報告に届くだけ。\n"
                              "- web（WebSearch・WebFetch）は根拠のコードで決まらない時だけ使う。判定の先行例の出典は開き直さない。\n"
                              "- why・evidence は見た事実（パス:行と、そこに在った物）で書く。推測は unsure にする。", source="fn:judgeverify._head")
UNIT_ASK = ("見ること: (1) 根本か（verdict）: この単位を直せば依頼の症状が消えるか。ほかの単位か単位に無い所の結果（症状の 1 つの"
            "現れ）でないか。root・not_root・unsure のどれか。not_root なら real_root に本当の根（見つけた所のパスと名と、そこが根と"
            "言える理由）を書く。単位どうしの重なりは別の下請けが見る。(2) 証拠（evidence_found・evidence）: 判定の理由が言う事実を根拠のコードで確かめたか。確かめた所と見た事を"
            "書く。(3) 場所（location_ok・location）: 単位の key が名指すパスと名が直す所か。違えば正しい場所を location に書く"
            "（合っていれば同じ場所）。答えは下の JSON Schema に合う JSON 1 つにして、" + ANSWER_AT + "（このファイルのほかに書かない）。"
            "書いたら最後のメッセージに 1 行だけ返せ: `単位 {n}: <verdict>`。\n\n```json\n{schema}\n```")
VIEW_HEAD = promptsection.Section("## 判定者の見立て", source="fn:judgeverify._head")
SYNERGY_HEAD = promptsection.Section("## この下請けの確かめ: 単位どうしの相乗り", source="fn:judgeverify.prep_on")
SYNERGY_ASK = ("1 つの単位の中の確かめは別の下請けがする。この下請けは単位どうしの関わりだけを見る: duplicates（同じ根の別の現れ・同じ直しで"
               "閉じる）・relations（place で 2 つに分ける。same＝同じ行・同じ塊を変える、か片方の直しがもう片方の前提（名・型・"
               "呼び方）を変える。apart＝同じファイル・同じ試験のファイルの別の所（別の関数・別のクラス・別のクラスに足すテスト）を"
               "触るだけで、直しどうしは重ならない。同じファイルだけを理由に same にしない）・order（片方を先に"
               "直さないともう片方を直せない・試せない）。単位は下の番号で名指す。無ければ空の配列にし、why に見た事と無い理由を"
               "書く。答えは下の JSON Schema に合う JSON 1 つにして、" + ANSWER_AT + "（このファイルのほかに書かない）。書いたら"
               "最後のメッセージに 1 行だけ返せ: `相乗り: 重複 <数>・関わり <数>・順番 <数>`。\n\n```json\n{schema}\n```")
AGG = promptsection.Section("# 判定の単位の裏取りの束ね役（機械が書いた）\n\n"
                            "この役は束ね役。単位を自分で見ずに、下の下請けのファイルごとに Agent の道具で下請けを 1 つずつ起こせ。下請けの呼びは"
                            " 1 つのメッセージに全部並べよ（同時に走る）。subagent_type は全部 " + SUBAGENT_TYPE + "（ほかの型を使わない）。各下請けへの"
                            "頼みは「<ファイル> を Read で読み、その指示に従え」の 1 行でよい。下請けは読むだけで、答えはファイルに書き（どこに書くかは"
                            "ファイルが名指す。作業ツリーは変えない）、最後に 1 行の要約を返す。答えのファイルは機械が確かめてまとめるので、"
                            "答えの中身を写さない。", source="fn:judgeverify.prep_on")
AGG_REPLY = "下請けが全部返ったら、返答は次の JSON Schema に合う JSON だけにせよ（summary に下請けの 1 行の要約を並べる）:"


def output_format() -> dict:
    """束ね役の返答の型（印つき）。答えの中身は答えのファイルにあり、返答は要約だけ（線の木の段 1 の教訓: 束ね役に写させない）"""
    return {"type": "object", "additionalProperties": False, "required": ["summary"],
            "properties": {"summary": {"type": "string", "minLength": 10}}}


def unit_schema() -> dict:
    """単位の下請けの答えのファイルの型（not_root の本当の根 real_root はまとめが確かめる）"""
    return {"type": "object", "additionalProperties": False,
            "required": ["unit", "verdict", "evidence_found", "evidence", "location_ok", "location", "why"],
            "properties": {"unit": {"type": "integer", "minimum": 1}, "verdict": {"type": "string", "enum": list(VERDICTS)},
                           "evidence_found": {"type": "boolean"}, "evidence": {"type": "string", "minLength": 10},
                           "location_ok": {"type": "boolean"}, "location": {"type": "string", "minLength": 1},
                           "why": {"type": "string", "minLength": 10}, "real_root": {"type": "string"}}}


def synergy_schema() -> dict:
    pair = {"type": "object", "additionalProperties": False, "required": ["units", "why"],
            "properties": {"units": {"type": "array", "minItems": 2, "items": {"type": "integer", "minimum": 1}},
                           "why": {"type": "string", "minLength": 4}}}
    relation = copy.deepcopy(pair)   # 関わりの行は place（PLACES。同じ行・同じ塊か、同じファイルの別の所か）を持つ
    relation["required"] = relation["required"] + ["place"]
    relation["properties"]["place"] = {"type": "string", "enum": list(PLACES)}
    order = {"type": "object", "additionalProperties": False, "required": ["first", "then", "why"],
             "properties": {"first": {"type": "integer", "minimum": 1}, "then": {"type": "integer", "minimum": 1},
                            "why": {"type": "string", "minLength": 4}}}
    return {"type": "object", "additionalProperties": False, "required": ["why", "duplicates", "relations", "order"],
            "properties": {"why": {"type": "string", "minLength": 10}, "duplicates": {"type": "array", "items": pair},
                           "relations": {"type": "array", "items": relation},
                           "order": {"type": "array", "items": order}}}


def _unit_row(u: dict) -> dict:
    return {k: u[k] for k in ("key", "label", "disposition", "reason", "origin_analysis", "why_chain", "prescriptions")
            if k in u}


def _head(judgment: dict) -> str:
    view = {k: judgment[k] for k in ("framing", "one_shot") if isinstance(judgment.get(k), str)}
    return "\n\n".join(x for x in (TITLE, SUB_HEAD, RULES, f"{VIEW_HEAD}\n\n```json\n{json.dumps(view, ensure_ascii=False, indent=1)}\n```"
                                   if view else "") if x)


def _initial(units: list) -> dict:
    return {"units": [{"n": n, "key": u["key"], "state": UNVERIFIED, "errors": [WAITING]} for n, u in enumerate(units, 1)],
            "synergy": {"state": UNVERIFIED, "errors": [WAITING]}}


ALL_UNITS_HEAD = promptsection.Section("### 単位の全部\n\n", source="fn:judgeverify.prep_on")

RECEIVES = [
    promptsection.Receive(ROLE, head) for head in (UNIT_HEAD, TITLE, RULES, VIEW_HEAD, SYNERGY_HEAD, AGG, ALL_UNITS_HEAD)
]


def _load(path: pathlib.Path, schema: dict) -> tuple:
    """(答え, 誤りの行)"""
    if not path.is_file():
        return None, [f"答えのファイルが無い（{path}）"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, [f"答えのファイルが JSON として読めない（{oneline.one_line(e)}）"]
    errs = validate_schema(doc, schema)
    return (None, errs) if errs else (doc, [])
