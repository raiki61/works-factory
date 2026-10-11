"""判定のブロック（workflows/judge/）の受け付けと支度の芯（docs/design.md の能力の名 lib/judge_accept）。

今の works で盤面（board・script_io・graphloops の engine の盤面と rules・検証器）の上に在った判定の規則を、元の関数の名のまま、
値（受けた返答・依頼の行・素材の状態・始めの記録・版・対象の根）かファイルのパスを引数で受ける形に書き直した物
（計画 docs/plans/2026-10-12-blocks/judge.md の「新しく書く物」。lib-port の「移し方」(b)）。各関数の docstring の頭に元を書く。
規則の中身（文・条件・数）は元のまま。1 run は 1 周（持ち主の決め carry）なので、前の周を読む所は空の前の周として読む。

置き場: このブロックが run の置き場に書くファイルは全部、判定の道は `judge/`、再審の道は `rejudge/` の下（JUDGE_DIR・REJUDGE_DIR）。
関数はそのフォルダのパス（jdir・rdir）を受け、置き場の名を知らない。
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

sys.dont_write_bytecode = True

_GL = pathlib.Path(__file__).resolve().parent / "graphloops"
if str(_GL) not in sys.path:
    sys.path.insert(0, str(_GL))

from engine.util import Reject, run_count  # noqa: E402
import stopby  # noqa: E402

JUDGE_DIR = "judge"
REJUDGE_DIR = "rejudge"


# ---------------------------------------------------------------- 置き場のファイル
def read_json(path, default=None):
    """path の JSON。無ければ default。読めない・JSON でなければ ValueError（壊れた控えを黙って空にしない）"""
    p = pathlib.Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"{p} が読めない（{type(e).__name__}: {e}）") from None


def write_json(path, doc) -> pathlib.Path:
    """doc を JSON で、一時のファイルから置き換えて書く。置いたパスを返す"""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


# ---------------------------------------------------------------- 検証器の表（元 works/.shared/core/scripts/review-record.py。表の字は元のまま）
# 元は record_common._rows で組み、行の欠けを exit 2 で落とした。ここは読み込みの時に namedtuple の生成が TypeError で落ちる
Rule = collections.namedtuple("Rule", "fields blocks carryable observed")
Kind = collections.namedtuple("Kind", "domain fields note")


def _rows(cls, rows: dict) -> dict:
    """元 works/.shared/core/scripts/record_common.py:37 の _rows（行の欠けは読み込みの時に TypeError で落ちる）"""
    return {name: cls(*args) for name, args in rows.items()}


# 元 review-record.py:107
MATERIALS = (
    "base_determination",  # BASE をどの規則で決めたか（P0-1）
    "local_checks",  # CI のテスト・lint のローカル実行（P0-2）
    "parallel_pr",  # 並行 PR 衝突チェック（P0-5）
    "prior_decisions",  # 先行議論の突合（P0-6）——決着済み論点の蒸し返し防止
    "local_review",  # 局所レビュー（公式 skill）
    "consistency",
    "bypass",  # 標準機構の迂回
    "hygiene",  # コード衛生（文脈遮断）
    "external_standards",  # 外部標準照合＋手元の依存
    "procedure_trace",  # 手順トレース
    "gate_efficacy",  # 新設ゲートの赤の確認
    "test_double_fidelity",  # 代役の忠実性
    "main_path_observation",  # 主経路の実行観測
    "provenance",  # 根拠の出所検査
    "fix_closure",  # 修正の閉鎖実証（P3）——直したと書くだけでなく閉じたことを確かめたか
)
# 元 review-record.py:140
STATUS = _rows(Rule, {
    "found": (("count", "detail"), False, True, True),
    "clean": (("checked",), False, True, True),
    "carried_over": (("from_round", "reason"), False, True, False),
    "not_applicable": (("reason",), False, False, False),
    "awaiting_human": (("reason",), True, False, False),
    "not_run": (("reason",), True, False, False),
})
SILENT_STATUS = tuple(k for k, r in STATUS.items() if not r.observed and not r.blocks)
OBSERVED_STATUS = tuple(k for k, r in STATUS.items() if r.observed)
# 元 review-record.py:155
REVIEWS = ("R1", "R2", "R3", "R4")
# 元 review-record.py:197
LABELS = ("block", "suggest", "nit", "question", "info")
# 元 review-record.py:233
QUESTION_KINDS = _rows(Kind, {
    "fork": ("unit", ("options",),
             "設計の岐路——処方が機構の新設・共有面の拡大に及び、候補が複数で、世界の解（標準仕様・著名 OSS の定番）を当たっても"
             "決まらない（手順書 P2「処方の列挙」・REVIEW.md「処方の最小性」）。世界の解で決まるなら岐路ではなく処方として採る。"
             "選択肢は 2 つ以上、帰結まで書く。零処方（取り下げ・既存の機構 1 つ）が落ちる理由は reason に"),
    "split": ("unit", (),
              "修正が露呈させた既存の欠陥で、凍結した目的の外。別 PR に積むかを人が決める。"
              "露呈の回収は既定のまま（REVIEW.md「別 Issue への先送りを既定にするな」）で、これは例外の申請"),
    "rule": ("unit", (),
             "同じ指摘が新証拠なく再燃し、原因がコードでなく観点の誤発火。REVIEW.md のどの観点かを reason に書く"),
    "stuck": ("unit", (), "処方の誤りか設計の問題か（発火の条件と要求は stuck_unlisted が持つ）"),
    "thrash": ("none", (),
               "新規 [block] が出続けて収束に向かわない。件数の推移で見えるもので、特定のユニットに紐づかない"),
    "premise": ("review", (),
                "R2 が premise-invalid。別 context の judge が仮定を実態で検算したかが再審の中身"),
    "unverifiable": ("review", (), "R が独立に確かめる材料を取れない"),
    "awaiting": ("material", (),
                 "素材が awaiting_human（未観測・打ち切られた一覧・洗えなかった決定記録・走らせられない CI）"),
    "field": ("none", (),
              "人が実地で確かめるまで決まらない（実機・外部の環境・権限の要る操作）で、どの素材も awaiting_human でない。"
              "素材の欄を借りるな——CI の欄を借りると、CI を再実行する工程が毎周上書きする。周を止めず、最終報告の冒頭に載る"),
})
ORIGIN_NOTE = {"unit": "origin は当該ユニットの key", "material": "origin は素材名",
               "review": "origin は R1〜R4", "none": "origin も depends も持てない"}
# 元 review-record.py:273
QUESTION_FIELDS = ("key", "kind", "status", "reason", "resolution", "options", "depends", "origin")
UNIT_FIELDS = ("key", "label", "disposition", "reason", "reopen_evidence")
# 元 review-record.py:293
QUESTION_STATUS = {
    "held": (),
    "decided": ("resolution",),
    "resolved": ("resolution",),
    "escalate": (),
}
QUESTION_STATUS_NOTE = {
    "held": "未決——次の周の judge が再審する（fork で出どころの [block] を待たせられるのは 1 周だけ）",
    "decided": "ループが決めたが、出どころの欠陥がまだ開いている",
    "resolved": "ループが決め、出どころも閉じた——次の周の台帳から落としてよい",
    "escalate": "再審の結果、人でないと決められない（好み・方針・可逆性の低い合意・目的の書き換え）",
}
# 元 review-record.py:319
NO_OPEN_ORIGIN = ("split", "rule")
# 元 review-record.py:326 の PROMPT_TABLES（判定役の材料の問いの台帳の段の {{validator.*}} の穴を描く表）
PROMPT_TABLES = {
    "question_kinds": "／".join(
        f"{k}（{ORIGIN_NOTE[v.domain]}" + ("".join(f"・{f} が要る" for f in v.fields)) + f"）: {v.note}"
        for k, v in QUESTION_KINDS.items()),
    "question_status": "／".join(
        f"{k}" + ("".join(f"（{f} が要る）" for f in v)) + f": {QUESTION_STATUS_NOTE[k]}"
        for k, v in QUESTION_STATUS.items()),
    "no_open_origin": "・".join(NO_OPEN_ORIGIN) + " は [block]・do-now のユニットを origin にも depends にもできない"
                      "（人に聞く前に直す義務が消える。defer にして構造的理由を書け）",
    "question_fields": "／".join(QUESTION_FIELDS),
    "unit_fields": "／".join(UNIT_FIELDS),
    "labels": "／".join(LABELS),
}
# 元 review-record.py:343
ASKING = ("held", "escalate")
TRACKED = ("held", "escalate", "decided")


def origin_not_awaiting(q, materials):
    """元 works/.shared/core/scripts/review-record.py:276。未決の問いの出どころが素材なのに、その素材が今 awaiting_human でないか"""
    k = QUESTION_KINDS.get(q.get("kind"))
    if not k or k.domain != "material" or q.get("status") not in ASKING:
        return False
    m = materials.get(q.get("origin"))
    return bool(m) and m.get("status") != "awaiting_human"


def targets(q):
    """元 works/.shared/core/scripts/review-record.py:494。この問いが指す出どころ全部を (欄名, 域, 値) で返す"""
    domain = QUESTION_KINDS[q["kind"]].domain
    out = [("origin", domain, q["origin"])] if "origin" in q else []
    out.extend(("depends", "unit", d) for d in q.get("depends", []))
    return out


def is_open(u):
    """元 works/.shared/core/scripts/review-record.py:624。単位が今の周に直す義務を残すか"""
    return u["label"] == "block" or (
        u["label"] == "suggest" and u.get("disposition") == "do-now"
    )


def settled_state_errors(q, units):
    """元 works/.shared/core/scripts/review-record.py:634。決着した問いの状態が、出どころのユニットがまだ開いているかと食い違っていないか"""
    k = QUESTION_KINDS.get(q.get("kind"))
    status = q.get("status")
    by_key = {u.get("key"): u for u in units}
    if not k or k.domain != "unit" or status not in ("decided", "resolved") or q.get("origin") not in by_key:
        return []
    still_open = is_open(by_key[q["origin"]])
    if status == "resolved" and still_open:
        return ["出どころが [block] / do-now のまま resolved（決着したが欠陥が"
                "残っているなら decided。resolved は出どころも閉じた問いだけ）"]
    if status == "decided" and not still_open:
        return ["出どころが閉じているのに decided（欠陥が記録から消えたなら"
                "resolved にして、次の周の台帳から降ろせ）"]
    return []


# ---------------------------------------------------------------- 規則が使う助け（元 works/.shared/core/graphloops/rules/review-loop.py）
# 元 review-loop.py:467
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")  # 「書いていない」と同じ扱いにする語


def blank(s, min_len):
    """元 works/.shared/core/graphloops/rules/review-loop.py:480。役が埋める自由文が「空同然」か（表と長さの両方で見る）"""
    t = (s or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def _keys_once(rows, label):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3067。行の key が重複しないか（重複の文の一覧）"""
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            errs.append(f"{label}[{i}] の key が重複: {r['key'][:60]}")
        seen.add(r["key"])
    return errs


# 元 review-loop.py:3304
COUNT_BUDGET = {"calls": 300, "seconds": 900}
COUNT_CACHE_FILE = "count-cache.json"
COUNT_BUDGET_FILE = "count-budget.json"


def _run_query(jdir, where, how, root, rev=None, probe=True):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3307。役が書いた問い（how）を走らせる ——（件数, 拒否文）。
    走らせられなければ件数は None。盤面の b.dir は置き場 jdir に、周の番号は 1 に読み替えた（1 run は 1 周）"""
    if not root:
        return None, f"{where}: how を走らせる場所（リポジトリのルート）を引けない——確かめられない件数は受け取らない"
    import time
    cf, ck = pathlib.Path(jdir) / COUNT_CACHE_FILE, json.dumps([how, rev], ensure_ascii=False, sort_keys=True)
    cache = (read_json(cf, {}) or {}) if rev else {}
    if ck in cache:
        got, why = cache[ck]
        return (got, "") if got is not None else (None, f"{where}: how を機械が走らせられない（{why}）")
    bf = pathlib.Path(jdir) / COUNT_BUDGET_FILE
    bud = read_json(bf, {}) or {}
    if bud.get("round") != 1:
        bud = {"round": 1, "calls": 0, "seconds": 0.0}
    if bud["calls"] >= COUNT_BUDGET["calls"] or bud["seconds"] >= COUNT_BUDGET["seconds"]:
        return None, (f"{where}: この周に数える問いを走らせた量が上限（{COUNT_BUDGET['calls']} 回か {COUNT_BUDGET['seconds']} 秒）に達した"
                      f"（{bud['calls']} 回・{bud['seconds']:.0f} 秒）——同じ返答を出し直し続けていないか。続けるなら置き場の {COUNT_BUDGET_FILE} を消す")
    t0 = time.monotonic()
    got, why = run_count(how, root, rev=rev, probe=probe)
    bud["calls"] += 1
    bud["seconds"] += time.monotonic() - t0
    write_json(bf, bud)
    if rev and got is not None:
        cache[ck] = [got, why]
        write_json(cf, cache)
    if got is None:
        return None, f"{where}: how を機械が走らせられない（{why}）"
    return got, ""


# ---------------------------------------------------------------- 止めの理由の語（lib/stopby。元の各部品が declare していた語）
JUDGE_STOP = stopby.declare("judge", "受け付けを通った判定が無いまま輪を抜けた")   # 元 blk-judge/lib/judgetake.py:43
VERIFY_STOP = stopby.declare("judge-verify", "判定の裏取りの束ね役か下請けが作業ツリーを変えた")   # 元 blk-judge/lib/judgeverify.py:47
SPEC_STOP = stopby.declare("spec", "仕様の輪が諦めた・固まらなかった")   # 元 blk-spec/lib/specblk.py:69
MATERIAL_STOP = stopby.declare("material", "素材集めの役の返答を 3 回とも受けられなかった")   # 元 blk-material の collect が盤面を止めた語
REQUEST_STOP = stopby.declare("request", "依頼の型が通らない・始めの記録が読めない")


# ================================================================ 依頼と判定（A）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# 元: works/.shared/core/accept.py の check_request・_head_at_rev・_judge_tree_unchanged・check_judge と言い換えの表、
# 写しの rules（works/.shared/core/graphloops/rules/review-loop.py）の依頼の型と judge_output とその助け、
# works/blk-judge/lib/judgetake.py の受け付けの流れ、works/blk-judge/lib/judgeverify.py の支度とまとめ、
# works/darkfactory/lib/line_edge.py の単位の目録、works/.shared/core/outpurpose.py の material_rows、
# works/.shared/core/gatemarks.py の依頼の答えの結びの照らし。盤面の値は引数か置き場 jdir のファイルで受ける。
import difflib  # noqa: E402
import shutil  # noqa: E402

import accept as core_accept  # noqa: E402  （作業ツリーの姿 tree_state・tree_moved と git の口）
import carry  # noqa: E402
import gatemarks  # noqa: E402
import judgeverify as jv  # noqa: E402
import marks  # noqa: E402
import outpurpose  # noqa: E402
import querytest  # noqa: E402
import rolekit  # noqa: E402
import worldmark  # noqa: E402
import engine.util as _util  # noqa: E402
from engine.schema import validate_schema  # noqa: E402

DIAGNOSE_NODE = "p2.diagnose"                # 判定役の節の写しの graph の名（querytest・outpurpose・gatemarks の足し欄の表の鍵）
DIAGNOSE_ROLE = "diagnose"                   # 拒否の控え rejects-<役>.json の名（rolekit.with_done）
JUDGMENT_FILE = "judgment.json"              # 元 accept.py:57 の JUDGMENT_FILE（受けた判定。judge_output が整えた返答に例と目的の外の行を戻した物）
MATERIALS_FILE = "materials.json"            # 素材の状態（素材の名 → {status, …}。材料の支度が組む）
MATERIAL_GLOB = "material-*.json"            # 素材の役が書く {role, reply, materials}
# 裏取りの置き場は judgeverify.BRIEF_DIR（verify/）の下。judgeverify がこのモジュールを読むので、読み込みの時に jv の名を引かない
VERIFY_ANSWERS_DIR = "verify/answers"          # 裏取りの下請けの答えの置き場（元 judgeverify.answers_dir の run ごとの置き場の代わり）
VERIFY_TREE_FILE = "verify/verify-tree.json"   # 束ね役を起こす前の作業ツリーの姿（元 judgeverify.TREE_FILE）
GIVE_UP_AFTER = rolekit.GIVE_UP_AFTER        # 元 judgetake.py:42（輪 diagnose-loop の max_iterations と同じ）

# 元 works/.shared/core/graphloops/rules/review-loop.py:689・:3860（init の入口で選ぶ入力の値）
GATES_MERGE = "merge"
SPEC_FLOW = "spec"
# 元 review-loop.py:472（判定の後に機械が台帳へ立てる問いの key。依頼の答えの結びを求めない字）
ASK_KEYS = {
    "R1": "累積差分の最小性を独立に測れない（R1 unverifiable）——測る材料を人が示すか、未収束のまま報告するか",
    "R2": "元の目的を独立に取れない（R2 unverifiable）——目的の出典を人が示すか、未収束のまま報告するか",
    "R3": "文書横断の整合を独立に確かめられない（R3 unverifiable）——確かめる材料を人が示すか、未収束のまま報告するか",
    "R4": "横断リスクと消えた能力を独立に確かめられない（R4 unverifiable）——基準点の材料を人が示すか、未収束のまま報告するか",
}
# 元 review-loop.py:104 の REQUEST_SCHEMA（依頼のバッチの一覧の型）
REQUEST_SCHEMA = {"type": "array", "items": {
    "type": "object", "required": ["round", "origin", "findings"], "additionalProperties": False, "properties": {
        "round": {"type": "integer", "minimum": 1},
        "origin": {"type": "string", "minLength": 1},
        "findings": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["where", "text"], "additionalProperties": False,
            "properties": {k: {"type": "string"} for k in ("where", "text", "mechanism", "measured", "false_positive_if")}}}}}}
# 元 accept.py:64 の NUMBER_HINTS（rules の拒否の番号で指せという案内を、名前を写せに言い換える）
NUMBER_HINTS = (
    ("写さずに、貼られた行の no で指せ", "削除候補の where を字面のまま写せ"),       # _carried_r1_accounted（判定の carried_r1）
)
# 元 review-loop.py:2357
ONE_LINE_FIELDS = ("key", "reason")
# 元 accept.check_judge の型の照らし（role_schema("p2.diagnose")）。写しの graph の p2.diagnose の schema の、この受け付けが
# 読む欄の型（class_query の how の中は engine の run_count が照らす）。out_of_purpose・answer_ties は受け付けが先に外す
_TEXTS = {"type": "array", "items": {"type": "string"}}
DIAGNOSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["units", "questions", "framing", "one_shot", "materials_missing", "carried_r1", "one_shot_closes", "precedents"],
    "properties": {
        "units": {"type": "array", "items": {
            "type": "object", "required": ["key", "label"], "properties": {
                "key": {"type": "string", "minLength": 1},
                "label": {"type": "string", "enum": list(LABELS)},
                "disposition": {"type": "string", "enum": ["do-now", "defer"]},
                "reason": {"type": "string"}, "reopen_evidence": {"type": "string"}, "origin_analysis": {"type": "string"},
                "why_chain": _TEXTS, "prescriptions": _TEXTS, "closed_note": {"type": "string"},
                "class_query": {"type": "object", "required": ["how", "counts", "total"], "properties": {
                    "how": {"type": "object"}, "counts": {"type": "string", "enum": ["defects", "population"]},
                    "total": {"type": "integer", "minimum": 0}, "note": {"type": "string"}}}}}},
        "questions": {"type": "array", "items": {"type": "object", "required": ["key", "kind", "status", "reason"],
                                                 "properties": {"key": {"type": "string", "minLength": 1}}}},
        "framing": {"type": "string"}, "one_shot": {"type": "string"},
        "materials_missing": _TEXTS,
        "carried_r1": {"type": "array", "items": {
            "type": "object", "required": ["where", "disposition"], "additionalProperties": False, "properties": {
                "where": {"type": "string", "minLength": 1}, "disposition": {"type": "string", "enum": ["promote", "decline"]},
                "unit_key": {"type": "string"}, "why": {"type": "string"}}}},
        "router": {"type": "array", "items": {"type": "object"}},
        "reburn_causes": {"type": "array", "items": {"type": "object"}},
        "one_shot_closes": _TEXTS,
        "precedents": {"type": "array", "items": {
            "type": "object", "required": ["key", "problem", "source", "verdict", "reason"], "properties": {
                "key": {"type": "string", "minLength": 1}, "problem": {"type": "string"}, "source": {"type": "string"},
                "verdict": {"type": "string", "enum": ["adopt", "adapt", "does_not_apply", "not_found"]},
                "reason": {"type": "string"}, "searched": {"type": "string"}, "undecided_because": {"type": "string"}}}},
    },
}


class Unreadable(Exception):
    """元 judgetake.py:47。出口を組めない（judgment.json の形が崩れた）"""


# ---------------------------------------------------------------- 依頼の型
def check_inputs(inputs):
    """元 works/.shared/core/graphloops/rules/review-loop.py:67。init の入口（置き場を作る前）で、選ぶ入力の鍵と値を確かめる——
    綴り違いの鍵や知らない値を既定（今の流れ）に倒さない。仕様の道（flow=spec）と、変異の検算を合流でまとめる選択（gates=merge）"""
    chosen = {"flow": SPEC_FLOW, "gates": GATES_MERGE}
    for k in inputs:
        # 鍵の綴り違い（gate=merge）は、黙って既定（撃つ）に倒れると選んだつもりの害がそのまま起きる。似て非なる鍵を落とす
        near = difflib.get_close_matches(k, chosen, n=1, cutoff=0.75) if k not in chosen else []
        if near:
            raise Reject(f"--input {k}=… は鍵 {near[0]} の綴り違いに見える（知らない鍵は既定の流れに倒れる）——{near[0]}={chosen[near[0]]} と書け")
    for k, want in chosen.items():
        v = inputs.get(k)
        if v is not None and v != want:
            raise Reject(f"--input {k}={v!r} は知らない値（使えるのは {k}={want}。今の流れなら {k} を渡さない）")


def add(items, reason, rnd: int = 1) -> dict:
    """元 works/.shared/core/graphloops/rules/review-loop.py:124 の add の型の規則。人の修正依頼を、判定役に渡すバッチ
    {round, origin, findings} にして返す（型が通らなければ Reject）。1 run は 1 周で、依頼は入口が判定役を起こす前に 1 度だけ積むので、
    元の「その周の判定役が起きた後は足せない」と、記録の依頼の欄の型の崩れの照らしは当たらない"""
    batch = {"round": rnd, "origin": reason, "findings": items}
    errs = validate_schema([batch], REQUEST_SCHEMA)
    if errs:
        raise Reject("add の形: [{where, text, mechanism?, measured?, false_positive_if?}] の配列（空でない）: " + "; ".join(errs))
    return batch


def check_request(items, reason: str) -> dict:
    """元 works/.shared/core/accept.py:456。依頼を rules の add（[{where, text, mechanism?, measured?, false_positive_if?}]）に通す。
    {"ok", "reason"}。通った行を置き場の request.json に書くのは呼び手（元は盤面の request.json に積んだ）"""
    def run():
        add(items, reason)
        return {"ok": True, "reason": ""}
    return core_accept.guard(run)


# ---------------------------------------------------------------- 判定の受け付け
def _name_hints(e: Reject) -> Reject:
    """元 works/.shared/core/accept.py:69。rules の拒否の番号で指せという案内を、名前を写せに言い換えた Reject にする（ほかの文はそのまま）"""
    msg = str(e)
    for by_number, by_name in NUMBER_HINTS:
        msg = msg.replace(by_number, by_name)
    return Reject(msg)


def _head_at_rev(repo, rev, role):
    """元 works/.shared/core/accept.py:472。HEAD が数える版 rev のままか。動いていれば Reject（写しの無い見張りで、役が作った物を
    commit して git status を空に戻す道を塞ぐ。dogfood run 21）。role は読むだけの役の名"""
    head = core_accept._git(repo, "rev-parse", "--verify", "-q", "HEAD").strip()
    if head != rev:
        raise Reject(f"HEAD が数える版から動いた（版 {rev[:12]} / 今 {head[:12]}）——{role}は作業ツリーと履歴を変えてはいけない"
                     "（commit・reset・checkout で履歴を動かさない）")


def _judge_tree_unchanged(repo, jdir, rev):
    """元 works/.shared/core/accept.py:481。判定役が作業ツリーを変えていないか（Ruling R3・R14）。置き場に judge-tree.json（入口が
    依頼を受け付けた時の写し。tree_state の形）が在れば、今の作業ツリーがその写しと同じかを tree_moved で見る（HEAD・枝の移動と
    git が無視するファイルの増減・書き換えも見る）。無ければ作業ツリーが綺麗で、HEAD が数える版 rev のままであることを求める。
    違えば Reject。元の盤面の judge-snapshot.json は入口が置く judge-tree.json（TREE_FILE）に読み替えた"""
    snap = read_json(pathlib.Path(jdir) / TREE_FILE)
    if snap is None:
        now = core_accept.snapshot_tree(repo)   # 共通の姿（Claude Code の控えのフォルダ CLI_OWNED を数えない）
        dirty = now["porcelain"].splitlines() + [f"!! {n}" for n in now["ignored"]]
        if dirty:
            raise Reject("作業ツリーに変更が在る——判定役は読むだけの役で、作業ツリーを変えてはいけない"
                         f"（git status --porcelain --ignored: {dirty[:5]}{' ほか' if len(dirty) > 5 else ''}）")
        _head_at_rev(repo, rev, "判定役")
        return
    core_accept.type_errors(snap, core_accept.TREE_SCHEMA, f"置き場の {TREE_FILE} ")
    moved = core_accept.tree_moved({k: snap[k] for k in core_accept.TREE_KEYS}, repo)
    if moved:
        raise Reject("依頼を受け付けた後から作業ツリーが変わった——判定役は読むだけの役で、作業ツリー・HEAD・枝・git が"
                     f"無視するファイルを変えてはいけない（{'・'.join(moved)}）")


def _carried_r1_accounted(out, prev_deletions=None):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2359。前の周の R1 最小性が挙げた削除候補を、judge が 1 件につき 1 行で
    処理したか。prev_deletions は直前の周の R1 の deletions（元 b.outputs の r1.minimality。直前の周に R1 が走っていなければ None）。
    1 run は 1 周なので、このブロックの受け付けはいつも None を渡す（元の「直前の周のものだけを見る」で空を返す道）"""
    if prev_deletions is None:
        return []
    want = [d["where"] for d in prev_deletions if isinstance(d, dict) and d.get("where")]
    rows = out.get("carried_r1") or []
    errs, seen = [], {}
    for i, r in enumerate(rows):
        w = r.get("where", "")
        if w in seen:
            errs.append(f"carried_r1 に同じ where の行が 2 本: {w}")
        seen[w] = r
        if w not in want:
            errs.append(f"carried_r1[{i}] の where '{w}' は前の周の R1 の削除候補に無い（正本は prev.r1.minimality.deletions。写さずに、貼られた行の no で指せ）")
        elif r["disposition"] == "promote" and not (r.get("unit_key") or "").strip():
            errs.append(f"carried_r1[{i}]（{w}）が disposition=promote なのに unit_key が無い")
        elif r["disposition"] == "decline" and not (r.get("why") or "").strip():
            errs.append(f"carried_r1[{i}]（{w}）が disposition=decline なのに why が無い——落とす判断にも理由が要る")
    keys = {u["key"] for u in out.get("units", [])}
    for r in rows:
        if r.get("disposition") == "promote" and r.get("unit_key") and r["unit_key"] not in keys:
            errs.append(f"carried_r1 の unit_key '{r['unit_key']}' が units に無い")
    for w in want:
        if w not in seen:
            errs.append(f"前の周の R1 が挙げた '{w}' の行が carried_r1 に無い——unit に上げるか、落とす理由を書け。"
                        "**行を省くな**（省けるなら、読んだ上で黙って落とせていた元の穴に戻る）")
    return errs


def _fork_moves_forward(out, prev_questions=()):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2404。fork が出どころの [block] を免除するのは 1 周だけ。2 周目からは
    escalate（人に実際に届く形）に上げろ。prev_questions は前の周の台帳の問い（元 loop.prev_questions。1 run は 1 周なので空）"""
    prev_exempt = set()
    for q in (prev_questions or []):
        if q.get("kind") == "fork" and q.get("status") in ASKING:
            prev_exempt |= {q.get("origin")} | set(q.get("depends", []) or [])
    prev_exempt.discard(None)
    if not prev_exempt:
        return []
    errs = []
    for i, q in enumerate(out.get("questions", [])):
        if q.get("kind") != "fork" or q.get("status") != "held":
            continue
        again = ({q.get("origin")} | set(q.get("depends", []) or [])) & prev_exempt
        if again:
            errs.append(f"questions[{i}]（fork）の出どころ {sorted(again)} は前の周も fork で免除されていた——"
                        "held のまま 2 周目に入ると、人には何も届かないまま [block] が未着手で通り続ける。"
                        "escalate に上げて人に聞くか、decided / resolved に倒せ")
    return errs


def _precedent_gap(r):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2437。先行例の 1 行に足りない物（無ければ空文字）。判定者の行と修正役の行が
    同じ規則を使う——見つからないなら何を探したか、それ以外は一次情報の出典"""
    if r.get("verdict") == "not_found":
        return "searched（何をどう探したか）が無い" if blank(r.get("searched"), 4) else ""
    return "source（一次情報の出典）が無い" if blank(r.get("source"), 4) else ""


def _precedent_errors(out):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2445。判定者の先行例の行（precedents）: 今の周に直す単位と人へ回す問いの
    key ごとに 1 行、出典つき。人へ回す問いの行には『世界の解を当たっても決まらない理由』（検証器の表はこのモジュールの頭の物）"""
    rows = out.get("precedents") or []
    errs, by = _keys_once(rows, "precedents"), {r["key"]: r for r in rows}
    for i, r in enumerate(rows):
        gap = _precedent_gap(r)
        if gap:
            errs.append(f"precedents[{i}]（{r['verdict']}）に {gap}")
    need = [(u["key"], False) for u in out["units"] if is_open(u)]
    need += [(q["key"], True) for q in out["questions"]
             if (q.get("kind") == "fork" and q.get("status") in ASKING) or q.get("status") == "escalate"]
    for k, asks in need:
        r = by.get(k)
        if r is None:
            errs.append(f"precedents に '{k[:60]}' の行が無い——今の周に直す単位と人へ回す問いには、世界の解（先行例）を当たった行が要る")
        elif asks and blank(r.get("undecided_because"), 10):
            errs.append(f"precedents['{k[:60]}'] に undecided_because が無い——世界の解を当たっても決まらない理由（困っている点・残る不安）を"
                        "書け。書けないなら自明なので人に回さず、処方として採れ")
    return errs


def _awaiting_origins(questions, materials, where):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2468。人待ちの問い（kind=awaiting で未決）の出どころが、今 awaiting_human の
    素材か。元は全部の節の done が通る check_record から呼んだ。このブロックは判定の受け付け（take）が judge_output の後に呼ぶ"""
    errs = []
    for i, q in enumerate(questions):
        if origin_not_awaiting(q, materials):
            m = materials[q["origin"]]
            errs.append(f"{where}[{i}]（awaiting・{q['status']}）の出どころの素材 '{q['origin']}' が {m.get('status')}——awaiting の出どころは"
                        "今 awaiting_human の素材だけ。素材を書く節は、人に諮っている最中の欄を awaiting_human のまま書け（見た結果は reason に）。"
                        "人が実地で確かめるまで決まらない問いは kind=field で立てろ（素材の欄を借りない）")
    return errs


def _declared_route_errors(out, prev_declared_faces=()):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2483。前の周に残すと宣言した穴を、判定者が 1 件ずつ振り分けたか
    （to_unit＝今の周の直す単位に上げた／accept＝残すことを認めた）。元は履歴を読む判定の節 p2.history でだけ当てた（judge_output の
    nid の分け）。このブロックの判定は p2.diagnose だけなので judge_output は呼ばない。prev_declared_faces は元 loop.prev_declared_faces"""
    asked = {r["key"] for r in prev_declared_faces or []}
    rows = out.get("declared_routed") or []
    errs = _keys_once(rows, "declared_routed")
    errs += [f"declared_routed の key '{r['key'][:40]}' は前の周に宣言された穴に無い" for r in rows if r["key"] not in asked]
    errs += [f"前の周に残すと宣言された穴 '{k[:40]}' を振り分けていない——to_unit（直す単位に上げる）か accept（残すことを認める）で答えろ"
             for k in sorted(asked - {r["key"] for r in rows})]
    units = {u["key"] for u in out.get("units") or []}
    errs += [f"declared_routed '{r['key'][:40]}' は to_unit なのに unit_key が今の周の units に無い" for r in rows
             if r["route"] == "to_unit" and r.get("unit_key") not in units]
    return errs


def judge_output(out, jdir, root, rev, materials, *, prev_deletions=None, prev_questions=(), defer_ledger=None):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2497。judge の返答を、検証器の語彙（このモジュールの頭の表）で先に見る。
    落ちるなら judge に返させ直す（Reject）。あわせて 1 行の欄を 1 行に正規化し、class_query の件数を engine が数えた値に置き換える
    （out を書き換える）。返りは置き換えの注記（無ければ ""）。

    盤面から引数に替えた物: 置き場 jdir（数えた件数の控え。元 b.dir）・対象の根 root と数える版 rev（元 _repo_root と
    inputs.review_rev）・素材の状態 materials（元 record.materials）・前の周の R1 の削除候補 prev_deletions・前の周の台帳の問い
    prev_questions・defer 台帳 defer_ledger（1 run は 1 周なので、どれも無い・空）。
    元が節の宣言（graph の p2.diagnose の schema と reads）で分けていた所は、p2.diagnose の決まった事実として書いた: schema に
    precedents と carried_r1 が在り、reads に prev.r1.minimality が在り、loop.prev_blocks・loop.prev_units・loop.prev_questions は無い
    （だから _stuck_unrouted と _history_rules の 2 つの検証器の規則は当たらない）。履歴の判定（p2.history）の _declared_route_errors は
    このブロックに無い。元の loop.engine_zero への書き込み（修正の側が読む 0 件の単位）は、修正が別のブロックなので持たない"""
    errs = []
    # **役の自由文から改行を落とす。** 検証器は台帳と阻害要因を「  - 」で字下げして echo するので、key / reason の
    # 中の改行が新しい行頭を作り、その行が停止文言を含めば stop_branch の行頭規則が判定行と読み違える
    for row in list(out.get("units", [])) + list(out.get("questions", [])):
        for f in ONE_LINE_FIELDS:
            if isinstance(row.get(f), str):
                row[f] = " ".join(row[f].split())
    keys = set()
    replaced, zeroed = [], []
    for i, u in enumerate(out["units"]):
        if u["key"] in keys:
            errs.append(f"units[{i}] の key が重複: {u['key']}")
        keys.add(u["key"])
        if u["label"] not in LABELS:
            errs.append(f"units[{i}] の label が不正: {u['label']}")
        if u["label"] == "suggest":
            if u.get("disposition") not in ("do-now", "defer"):
                errs.append(f"units[{i}]（suggest）に disposition（do-now / defer）が無い")
            elif u["disposition"] == "defer" and not u.get("reason"):
                errs.append(f"units[{i}] の defer に構造的理由が無い")
        # 今の周に直す単位は、同じ形を**全部**引ける機械の問いを持て。「この周に直す単位か」の正本は検証器の is_open
        if is_open(u):
            cq = u.get("class_query") or {}
            if not cq.get("how") or not isinstance(cq.get("total"), int) or isinstance(cq.get("total"), bool):
                errs.append(f"units[{i}]（今の周に直す単位）に class_query（how＝同じ形を全部引ける機械の問い・total＝その件数）が無い"
                            "——1 site しか無いなら total: 1 でそう示せ")
            else:
                # 判定役が読んだのと同じ版（この周に固定した版）で数える。修正役の after は作業ツリーで数える
                got, why = _run_query(jdir, f"units[{i}].class_query", cq["how"], root, rev=rev)
                if why:
                    errs.append(why)
                elif got == 0 and cq["total"] != 0:
                    # **0 件は黙って置き換えない**——役の数を残し、0 だったことを note に書く
                    zeroed.append(f"units[{i}].class_query（役 {cq['total']} / engine 0）")
                    cq["note"] = (f"{cq.get('note') or ''}（engine が how を走らせると 0 件——在るべき物が無い型か、問いが対象を"
                                  f"取りこぼしている。役の書いた {cq['total']} を残した）").strip()
                elif got != cq["total"]:
                    replaced.append(f"units[{i}].class_query.total {cq['total']} → {got}")
                    cq["note"] = (f"{cq.get('note') or ''}（役の書いた total は {cq['total']}。engine が how を走らせた {got} に置き換えた）").strip()
                    cq["total"] = got
    # 一撃は反証可能に——「何が消えるはずか」を名指しし、次の周が測る問いを添える
    open_units = [u for u in out["units"] if is_open(u)]
    closes = out.get("one_shot_closes") or []
    if open_units:
        if not closes:
            errs.append("one_shot_closes が空——その一撃が閉じると見込む unit の key を名指ししろ（次の周が実際の再発と突き合わせる）")
    unknown = [k for k in closes if k not in keys]
    if unknown:
        errs.append(f"one_shot_closes に今の周の units に無い key: {unknown}")
    defer = set(defer_ledger or {})
    for i, q in enumerate(out["questions"]):
        unknown = sorted(set(q) - set(QUESTION_FIELDS))
        if unknown:
            errs.append(f"questions[{i}] に知らない欄: {unknown}（書けるのは {'/'.join(QUESTION_FIELDS)}）")
        kind, status = q.get("kind"), q.get("status")
        if kind not in QUESTION_KINDS:
            errs.append(f"questions[{i}] の kind が不正: {kind}")
            continue
        if status not in QUESTION_STATUS:
            errs.append(f"questions[{i}] の status が不正: {status}")
            continue
        domain, extra = QUESTION_KINDS[kind].domain, QUESTION_KINDS[kind].fields
        for f in ("reason",) + extra + QUESTION_STATUS[status]:
            if not q.get(f):
                errs.append(f"questions[{i}]（{kind}/{status}）に '{f}' が要る")
        if kind == "fork" and not (isinstance(q.get("options"), list) and len(q["options"]) >= 2):
            errs.append(f"questions[{i}] の options は選択肢 2 つ以上（各項に帰結まで）")
        # 出どころ（origin と depends）の走査は検証器の targets 1 本
        for fld, dom, val in targets(q):
            if dom == "unit" and val not in keys | defer:
                errs.append(f"questions[{i}] の {fld} '{val}' が units にも defer 台帳にも無い")
            elif dom == "material" and val not in MATERIALS:
                errs.append(f"questions[{i}] の {fld} は素材名: {val}")
            elif dom == "review" and val not in REVIEWS:
                errs.append(f"questions[{i}] の {fld} は R1〜R4: {val}")
        if domain == "none" and (q.get("origin") or q.get("depends")):
            errs.append(f"questions[{i}]（{kind}）は origin / depends を持てない")
        for d in q.get("depends", []) or []:
            if d not in keys | defer:
                errs.append(f"questions[{i}] の depends '{d}' が units にも defer 台帳にも無い")
        if status in ASKING and kind in NO_OPEN_ORIGIN:
            for k in [q.get("origin")] + list(q.get("depends", []) or []):
                u = next((x for x in out["units"] if x["key"] == k), None)
                if u and is_open(u):
                    errs.append(f"questions[{i}]（{kind}）の出どころ '{k}' が [block] / do-now（人に聞く前に直す義務が消える。defer にして構造的理由を書け）")
        errs += [f"questions[{i}]: {m}" for m in settled_state_errors(q, out["units"])]
    awaiting = {name for name, m in (materials or {}).items() if isinstance(m, dict) and m.get("status") == "awaiting_human"}
    listed = {q.get("origin") for q in out["questions"] if q.get("kind") == "awaiting" and q.get("status") in ASKING}
    for name in sorted(awaiting - listed):
        errs.append(f"素材 '{name}' が awaiting_human なのに台帳に kind=awaiting で無い")
    if out.get("materials_missing"):
        errs.append("judge が素材の欠落を報告した（P2 を止めて当該 grader を再起動しろ）: " + ", ".join(out["materials_missing"]))
    errs += _fork_moves_forward(out, prev_questions)
    errs += _precedent_errors(out)        # p2.diagnose の schema は precedents を持つ
    errs += _carried_r1_accounted(out, prev_deletions)   # p2.diagnose は prev.r1.minimality を読み、schema に carried_r1 を持つ
    if errs:
        raise Reject("judge の返答が記録の語彙に合わない（judge に返させ直す）: " + "; ".join(errs))
    notes = ([f"class_query の件数を engine が走らせた値に置き換えた: {'; '.join(replaced)}"] if replaced else []) + \
            ([f"engine の数が 0 件なので置き換えなかった: {'; '.join(zeroed)}"] if zeroed else [])
    return " / ".join(notes)


def _materials(jdir) -> dict:
    """置き場の素材の状態（materials.json。無ければ空）"""
    doc = read_json(pathlib.Path(jdir) / MATERIALS_FILE, {})
    return doc if isinstance(doc, dict) else {}


def _judged(reply, jdir, base_rev, repo, *, prev_deletions=None, prev_questions=(), defer_ledger=None) -> tuple:
    """元 accept.check_judge の芯（書く前まで）: 作業ツリーと HEAD → 型 → class_query の例 → 先例の出どころ → judge_output →
    awaiting の出どころ（元 check_record の _awaiting_origins）。返り (正規化した返答, 例, 注記)。拒否は Reject"""
    repo_p = pathlib.Path(repo)
    with core_accept.in_repo(repo_p):
        rev = core_accept.resolve_rev(repo_p, base_rev)
        _judge_tree_unchanged(repo_p, jdir, rev)
        core_accept.type_errors(reply, DIAGNOSE_SCHEMA, "判定の返答")
        errs = querytest.problems(reply.get("units"), is_open)
        if errs:
            raise Reject("class_query の例が問いと合わない: " + "; ".join(errs))
        errs = worldmark.ref_problems(reply, jdir)
        if errs:
            raise Reject("precedents の出どころが世界の解の行に無い: " + "; ".join(errs))
        out, examples = querytest.split(reply, is_open)   # judge_output は 1 行の欄と class_query を正規化する（split の写し。返答の元は触らない）
        root = _util.repo_root(_util.git) or ""
        materials = _materials(jdir)
        try:
            note = judge_output(out, jdir, root, rev, materials, prev_deletions=prev_deletions,
                                prev_questions=prev_questions, defer_ledger=defer_ledger)
        except Reject as e:
            raise _name_hints(e)
        errs = _awaiting_origins(out["questions"], materials, "questions")
        if errs:
            raise Reject("判定の問いの台帳が素材の状態と合わない: " + "; ".join(errs))
    return out, examples, note


def _save_examples(jdir, examples) -> None:
    """元 accept.check_judge の例の控え: 例の無い判定は前の例を消すだけ（ファイルが在れば空に置き換え、無ければ作らない）"""
    if examples or marks.path_of("query", jdir).is_file():
        querytest.save(jdir, examples, replace=True)


def check_judge(reply, jdir, base_rev, repo) -> dict:
    """元 works/.shared/core/accept.py:504。判定役の返答を受け付ける。作業ツリーか HEAD が変わっていれば拒む（_judge_tree_unchanged）→
    型（DIAGNOSE_SCHEMA）→ class_query の例（querytest）→ 先例の出どころ（worldmark）→ judge_output（素材は置き場の materials.json）。
    通れば置き場の judgment.json に書く（例は外して judge_output に通し、query-examples.json に置いて戻す）。
    {"ok", "reason", "open_units", "judgment_file"}。目的の外の所見と依頼の答えの結びも照らすのは take"""
    def run():
        out, examples, note = _judged(reply, jdir, base_rev, repo)
        _save_examples(jdir, examples)
        path = write_json(pathlib.Path(jdir) / JUDGMENT_FILE, querytest.restore(out, jdir))
        return {"ok": True, "reason": note or "", "open_units": [u["key"] for u in out["units"] if is_open(u)],
                "judgment_file": str(path)}
    return core_accept.guard(run, open_units=[], judgment_file="")


# 元 works/blk-material/lib/material.py:65-73 の ROLES の P1 の 9 本（写しの graph の p1.* の役の節）
P1_NODES = ("p1.local_review", "p1.consistency_bypass", "p1.hygiene", "p1.external_standards", "p1.procedure_trace",
            "p1.gate_efficacy", "p1.test_double_fidelity", "p1.main_path_observation", "p1.provenance")


def material_rows(jdir, origin: str = "") -> list:
    """元 works/.shared/core/outpurpose.py:87。材料の行: P1 の目の素材の役が受けた返答（置き場の material-<役>.json の reply。元は
    盤面の p1.* の節の最新の出力）の中の where・text を持つ行の全部と、依頼の行（置き場の request.json。元は今の周に積まれた
    依頼のバッチ）。行は {where, text, 任意の mechanism・measured・false_positive_if, from（出どころの節と目の名）}。
    出どころの節の名は元の写しの graph の名（p1.<役の名の - を _ に>）。origin は依頼のバッチの出どころ（元 batch.origin）"""
    out = []
    files = sorted(pathlib.Path(jdir).glob(MATERIAL_GLOB))
    for nid, doc in sorted((f"p1.{str(d.get('role')).replace('-', '_')}", d)
                           for d in (read_json(p, None) for p in files) if isinstance(d, dict)):
        if nid in P1_NODES:
            outpurpose._walk(doc.get("reply"), nid, out)
    rows = read_json(pathlib.Path(jdir) / REQUEST_FILE, [])
    outpurpose._walk(rows if isinstance(rows, list) else [], f"依頼（{origin}）", out)
    return out


def request_answers(jdir) -> list:
    """元 works/.shared/core/gatemarks.py:687。依頼の answers（置き場の start.json の欄。元は盤面の start の控え。dict でない行は読まない）"""
    rows = (read_json(pathlib.Path(jdir) / START_FILE, {}) or {}).get("answers")
    return [a for a in rows if isinstance(a, dict)] if isinstance(rows, list) else []


def unmeasured(materials) -> dict:
    """元 works/.shared/core/gatemarks.py:693。今の周に測れていない素材 {名: status}: 素材のうち、検証器の表 STATUS で阻害になる
    status（not_run・awaiting_human）の物"""
    if not isinstance(materials, dict) or not materials:
        return {}
    return {n: m["status"] for n, m in materials.items()
            if isinstance(m, dict) and m.get("status") in STATUS and STATUS[m["status"]].blocks}


def origin_of(q, materials) -> str:
    """元 works/.shared/core/gatemarks.py:704。答えを結ぶ時の問いの出どころ: 台帳の origin。origin が空の問いで、key が今の周に測れていない
    素材の名で始まる（名の直後が終わりか KEY_CHAR でない字）物は、その素材の名"""
    got = q.get("origin")
    if isinstance(got, str) and got:
        return got
    key = str(q.get("key") or "")
    return next((n for n in unmeasured(materials)
                 if key.startswith(n) and not gatemarks.KEY_CHAR.match(key[len(n):len(n) + 1])), "")


def answer_binds(a, questions, materials) -> list:
    """元 works/.shared/core/gatemarks.py:716 を受け付けの呼び方（answer_rows は空の列。字の一致だけ）で。依頼の答え a が当たる返答の
    問い: question と key が字のまま等しい問い、無ければ出どころ（origin_of）が等しい問いの全部"""
    qs = [q for q in questions if isinstance(q, dict)]
    name = a.get("question")
    by_key = [q for q in qs if isinstance(q.get("key"), str) and q.get("key") and q.get("key") == name]
    return by_key or [q for q in qs if name and origin_of(q, materials) == name]


def redesign_rows(jdir) -> list:
    """元 works/.shared/core/gatemarks.py:774。依頼の prior_failures の写し（置き場の prior-failures-in.json）のうち、作り直しの行（無い・読めなければ空）"""
    try:
        rows = json.loads((pathlib.Path(jdir) / carry.PRIOR_IN_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in rows if carry.is_redesign(r)] if isinstance(rows, list) else []


def answer_tie_problems(jdir, reply, rows, materials) -> list:
    """元 works/.shared/core/gatemarks.py:824。判定の返答 reply（answer_ties を外した写し）と結びの行 rows の誤り（1 件 1 文）。
    盤面から替えた物: 依頼の answers（request_answers）・作り直しの行（redesign_rows）・測れていない素材（unmeasured。materials は
    置き場の素材の状態）・判定の後に機械が台帳へ立てる問いの key（ASK_KEYS の表。元 b.rules.ASK_KEYS）。行の 1 つの照らしは
    gatemarks._tie_row_problems をそのまま使う"""
    if not isinstance(rows, list):
        return [f"{gatemarks.ANSWER_TIES} が配列でない（{type(rows).__name__}）"]
    body = reply if isinstance(reply, dict) else {}
    questions = [q for q in body.get("questions") or [] if isinstance(q, dict)]
    units = {u.get("key"): u for u in body.get("units") or [] if isinstance(u, dict)}
    answers = {a.get("question"): a for a in request_answers(jdir)}
    redesign = {carry.row_key(r): r for r in redesign_rows(jdir)}
    out, tied = [], set()
    for i, r in enumerate(rows):
        errs, got = gatemarks._tie_row_problems(i, r, answers, redesign, {q.get("key") for q in questions}, units)
        out += errs
        if got is not None and not errs:
            if got in tied:
                out.append(f"{gatemarks.ANSWER_TIES}[{i}] が同じ {got[0]} {got[1]!r} の 2 度目（1 つの答え・行に結びは 1 つ）")
            tied.add(got)
    later = set(ASK_KEYS.values())   # 判定の後に機械が台帳へ立てる問いの key
    for name, a in answers.items():
        if ("answer", name) in tied or name in later:
            continue
        hits = answer_binds(a, questions, materials)
        if len(hits) == 1 or (not hits and name in unmeasured(materials)):
            continue
        out.append(f"依頼の答え {name!r} が" + (f"返答の複数の問いに当たる（{'・'.join(str(q.get('key')) for q in hits)}）" if hits
                                             else "返答のどの問いにも当たらない")
                   + f"のに結びが無い——{gatemarks.ANSWER_TIES} に {{answer: {name!r}, to: <今の返答の問いの key か単位の key>}} か "
                   f"{{answer: {name!r}, none: <当たらない訳。{gatemarks.ANSWER_TIE_MIN} 字以上>}} を足す")
    for key, r in redesign.items():
        if ("redesign", key) not in tied:
            out.append(f"作り直しの行 {gatemarks._squeeze(r.get('text'))!r} に結びが無い——{gatemarks.ANSWER_TIES} に {{redesign: <行の text の最初の「（」まで>, "
                       f"to: <[block] か do-now の単位の key>}} か {{redesign, none: <反証で死んだか目的の外とした訳。{gatemarks.ANSWER_TIE_MIN} 字以上>}} を足す")
    return out


def take(jdir, reply, repo, base_rev: str = "", *, prev_deletions=None, prev_questions=(), defer_ledger=None) -> dict:
    """元 works/blk-judge/lib/judgetake.py:74 の take と、受け付けの芯（元 entry.take の p2.diagnose の done と accept.check_judge）。
    順（計画の節 9）: 作業ツリーと HEAD → 型 → class_query の例（querytest）→ 先例の出どころが世界の解の行に在る（worldmark）→
    judge_output → 目的の外の所見の行を材料の行に当てる（outpurpose）→ 依頼の答えと作り直しの行の結び（answer_ties）。
    例・目的の外の行・結びは型と judge_output の前に外す（写しの型はどの欄も持たない）。通れば例を query-examples.json に、
    目的の外の行を当たった材料の行ごと out-of-purpose.json（周は 1）に、結びを answer-ties.json に置き、judge_output が整えた返答に
    例と目的の外の行を戻して judgment.json に書く（元 judgetake.finish）。
    返り {ok, reason, open_units, judgment_file}。拒否の時は judgment.json を書かない"""
    def run():
        if not isinstance(reply, dict):
            raise Reject(f"判定の返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        body, outside = outpurpose.split(reply)
        body, tie_rows = gatemarks.split_answer_ties(body)
        out, examples, note = _judged(body, jdir, base_rev, repo, prev_deletions=prev_deletions,
                                      prev_questions=prev_questions, defer_ledger=defer_ledger)
        material = material_rows(jdir)
        errs = outpurpose.problems(outside, material)
        if errs:
            raise Reject(f"{outpurpose.FIELD} の行が材料の行と合わない: " + "; ".join(errs))
        errs = answer_tie_problems(jdir, out, tie_rows, _materials(jdir))
        if errs:
            raise Reject(f"{gatemarks.ANSWER_TIES} が依頼の答えと作り直しの行に結ばれていない: " + "; ".join(errs))
        _save_examples(jdir, examples)
        outpurpose.save(jdir, 1, outside, material)
        gatemarks.save_answer_ties(jdir, 1, tie_rows)
        doc = outpurpose.restore(querytest.restore(out, jdir), jdir, 1)
        path = write_json(pathlib.Path(jdir) / JUDGMENT_FILE, doc)
        return {"ok": True, "reason": note or "", "open_units": [u["key"] for u in out["units"] if is_open(u)],
                "judgment_file": str(path)}
    return core_accept.guard(run, open_units=[], judgment_file="")


def accept(jdir, raw: str, repo, base_rev: str = "") -> dict:
    """元 works/blk-judge/lib/judgetake.py:106。役の返答の字 raw を読んで take に通す（元 rolekit.accept_role の読み）。
    返り {ok, reason, open_units, judgment_file}。done（3 回目の拒否で輪を抜ける旗）は呼び手が rolekit.with_done で足す"""
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        return {"ok": False, "reason": why, "open_units": [], "judgment_file": ""}
    return take(jdir, reply, repo, base_rev)


def _give_up(jdir) -> dict:
    """元 works/blk-judge/lib/judgetake.py:122。受け付けを通った判定が無いまま輪を抜けた: 最後の拒否の文で止めの控えを置き
    （JUDGE_STOP。もう止めの控えが在れば write_stop は書かない）、ok false の出口"""
    rows = rolekit.rejected(jdir, DIAGNOSE_ROLE)
    if rows:
        reason = f"{DIAGNOSE_NODE} の返答が {len(rows)} 回とも受け付けで拒まれた（最後の拒否: {' '.join(rows[-1].split())}）"
    else:
        reason = f"受け付けを通った判定が無いまま判定の輪を抜けた（{DIAGNOSE_NODE} の受け付けの拒否の控えも無い）"
    write_stop(jdir, JUDGE_STOP, reason)
    return {"ok": False, "open_units": [], "need_fix": False, "judgment_file": "", "one_shot": ""}


def collect(jdir) -> dict:
    """元 works/blk-judge/lib/judgetake.py:140。判定の出口。judgment.json から {ok, open_units, need_fix, judgment_file, one_shot}。
    無ければ _give_up。形が崩れていれば Unreadable"""
    path = pathlib.Path(jdir) / JUDGMENT_FILE
    try:
        judgment = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _give_up(jdir)
    except (OSError, ValueError) as e:
        raise Unreadable(f"置き場の {JUDGMENT_FILE} が読めない（{path}: {type(e).__name__}: {e}）——受け付けを通った判定が無い") from None
    units = judgment.get("units") if isinstance(judgment, dict) else None
    one_shot = judgment.get("one_shot") if isinstance(judgment, dict) else None
    if not isinstance(units, list) or not all(isinstance(u, dict) and "key" in u and "label" in u for u in units) \
            or not isinstance(one_shot, str):
        raise Unreadable(f"置き場の {JUDGMENT_FILE} の形が崩れている（units[].key・label と one_shot が要る）: {path}")
    open_units = [u["key"] for u in units if is_open(u)]
    return {"ok": True, "open_units": open_units, "need_fix": bool(open_units), "judgment_file": str(path),
            "one_shot": one_shot}


# ---------------------------------------------------------------- 単位の目録
def _unit_file_paths(u: dict, repo) -> tuple:
    """元 works/darkfactory/lib/line_edge.py:343。単位 1 つが名指すファイル（class_query.how.paths。無ければ key の頭の語）のうち、
    対象の根からの相対で在るファイルのパスと、捨てたパス。how.paths は git の pathspec（ディレクトリ・glob・絶対パスも来る）で、
    構造の目は根の中のファイルしか測らないので、ここで捨てて数を残す（黙って空の実測にしない）"""
    how = (u.get("class_query") or {}).get("how") or {}
    raw = [p for p in how.get("paths") or [] if isinstance(p, str) and p]
    if not raw and isinstance(u.get("key"), str) and u["key"].split():
        raw = [u["key"].split()[0]]
    root = pathlib.Path(repo).resolve()
    kept, dropped = [], []
    for p in raw:
        q = pathlib.PurePosixPath(p[2:] if p.startswith("./") else p)
        ok = (not q.is_absolute() and ".." not in q.parts and not any(c in p for c in "*?[:")
              and (root / q).is_file())
        (kept if ok else dropped).append(str(q) if ok else p)
    return list(dict.fromkeys(kept)), list(dict.fromkeys(dropped))


def structure_units(judgment, repo) -> list:
    """元 works/darkfactory/lib/line_edge.py:361。判定の開いた単位（is_open）を全部、構造の目の入力の形 {id, paths, summary} に写した
    並び（判定の順）。summary は単位の reason だけ。元は paths が 1 本も残らない単位を写さなかったが、計画の決めで落とさない
    （paths: [] で返す。構造の目に回すかは plan が決める）。元の書き出し（盤面の作業ファイル）と trace の行は持たない"""
    rows = []
    for u in (judgment.get("units") if isinstance(judgment, dict) else None) or []:
        if not isinstance(u, dict) or not isinstance(u.get("key"), str) or not is_open(u):
            continue
        paths, _ = _unit_file_paths(u, repo)
        reason = u.get("reason") if isinstance(u.get("reason"), str) else ""
        rows.append({"id": u["key"], "paths": paths, "summary": reason})
    return rows


# ---------------------------------------------------------------- 判定の裏取り
def verify_not_run(jdir, reason: str) -> pathlib.Path:
    """裏取りを回さなかった時の judge-verify.json（元 blk-judge/schemas/judge-verify.schema.json の形の空: 単位の行は無く、相乗りは
    確かめられなかった・訳は errors の 1 行。元の works は回さない周にファイルを置かず、読み手は無い時を空として読んだ。
    このブロックは返る時に必ず置くので、読み手（planblk.verify_part）が「確かめられなかった（訳）」と読む形にした）。置いたパスを返す"""
    return write_json(pathlib.Path(jdir) / jv.VERIFY_FILE,
                      {"units": [], "synergy": {"state": jv.UNVERIFIED, "errors": [str(reason)]}})


def _verify_off(jdir, reason: str) -> dict:
    """支度の go 偽: 番号の控えを消し（元 judgeverify._clear）、回さなかった形の申し送りを置く"""
    (pathlib.Path(jdir) / jv.PLAN_FILE).unlink(missing_ok=True)
    verify_not_run(jdir, reason)
    return {"go": False, "prompt_file": "", "reason": reason}


def prep_on(jdir, judgment, repo, verify: bool = True) -> dict:
    """元 works/blk-judge/lib/judgeverify.py:202。裏取りの支度。返り {go, prompt_file, reason}。verify（入口の機能の切り替え。
    features_cut に judge_verify が在れば偽）が偽・止めの控えが在る・受けた判定が無い・開いた単位が MIN_UNITS 未満なら go 偽で、
    回さなかった形の申し送りを置く。go なら単位ごとの下請けのファイル（verify/unit-<n>.md）・相乗りのファイル（verify/synergy.md）・
    束ね役の指示書（verify/prompt.md）・番号の控え（PLAN_FILE）・作業ツリーの姿（verify/verify-tree.json）を書き、前の起動の答えを消し、
    申し送りの初めの形（全部が UNVERIFIED）を置く。答えの置き場は置き場の verify/answers/（元は盤面の外の run ごとの置き場）"""
    jdir = pathlib.Path(jdir)
    units = jv.open_units(judgment)
    if not verify:
        return _verify_off(jdir, "判定の裏取りは機能の切り替えで切（始めの記録の features_cut に judge_verify）")
    stop = read_stop(jdir)
    if stop is not None:
        return _verify_off(jdir, f"run が止まっている（{stop['stop_reason']}）")
    if not isinstance(judgment, dict):
        return _verify_off(jdir, "受け付けを通った判定が無い")
    if len(units) < jv.MIN_UNITS:
        return _verify_off(jdir, f"開いた単位が {len(units)} つ（{jv.MIN_UNITS} つ未満は相乗りが無く、裏取りを回さない）")
    answers = jdir / VERIFY_ANSWERS_DIR
    shutil.rmtree(answers, ignore_errors=True)   # 前の起動の答えを今の判定の答えに数えない
    answers.mkdir(parents=True, exist_ok=True)
    head = jv._head(judgment)
    files = []
    for n, u in enumerate(units, 1):
        path = jdir / jv.BRIEF_DIR / f"unit-{n}.md"
        body = "\n\n".join([head, jv.UNIT_HEAD.format(n=n),
                            f"```json\n{json.dumps(jv._unit_row(u), ensure_ascii=False, indent=1)}\n```",
                            jv.UNIT_ASK.format(n=n, answer=answers / jv.ANSWER_FILE.format(n=n),
                                               schema=json.dumps(jv.unit_schema(), ensure_ascii=False))])
        path.write_text(body + "\n", encoding="utf-8")
        files.append(f"- 単位 {n}: {path}")
    syn = jdir / jv.BRIEF_DIR / "synergy.md"
    rows = "\n".join(f"- 単位 {n}: {json.dumps(jv._unit_row(u), ensure_ascii=False)}" for n, u in enumerate(units, 1))
    syn.write_text("\n\n".join([head, jv.SYNERGY_HEAD, jv.ALL_UNITS_HEAD + rows,
                                jv.SYNERGY_ASK.format(answer=answers / jv.SYNERGY_FILE,
                                                      schema=json.dumps(jv.synergy_schema(), ensure_ascii=False))])
                   + "\n", encoding="utf-8")
    files.append(f"- 相乗り: {syn}")
    prompt = jdir / jv.BRIEF_DIR / "prompt.md"
    reply = {k: v for k, v in jv.output_format().items() if k != "description"}
    prompt.write_text("\n\n".join([jv.AGG, "下請けのファイル:\n" + "\n".join(files),
                                   f"{jv.AGG_REPLY}\n\n```json\n{json.dumps(reply, ensure_ascii=False)}\n```"]) + "\n", encoding="utf-8")
    jv._write_json(jdir / VERIFY_TREE_FILE, core_accept.tree_state(pathlib.Path(repo)))
    jv._write_json(jdir / jv.PLAN_FILE, {"units": [{"n": n, "key": u["key"]} for n, u in enumerate(units, 1)], "answers": str(answers)})
    jv._write_json(jdir / jv.VERIFY_FILE, jv._initial(units))
    return {"go": True, "prompt_file": str(prompt), "reason": ""}


def _check_unit(answers, n: int, key: str) -> dict:
    """元 works/blk-judge/lib/judgeverify.py:255。答えの置き場 answers の単位 n の答えを確かめた申し送りの行"""
    got, errs = jv._load(pathlib.Path(answers) / jv.ANSWER_FILE.format(n=n), jv.unit_schema())
    if got is not None:
        if got["unit"] != n:
            errs.append(f"$.unit: {n} でない（{got['unit']}）")
        if got["verdict"] == "not_root" and len(str(got.get("real_root") or "").strip()) < 4:
            errs.append("$.real_root: not_root なのに本当の根が書かれていない")
    if errs:
        return {"n": n, "key": key, "state": jv.UNVERIFIED, "errors": errs}
    return {"n": n, "key": key, "state": jv.CHECKED, **{k: v for k, v in got.items() if k != "unit"}}


def _check_synergy(answers, keys: dict) -> dict:
    """元 works/blk-judge/lib/judgeverify.py:267。相乗りの答えを確かめ、番号を単位の key に戻した申し送りの欄"""
    got, errs = jv._load(pathlib.Path(answers) / jv.SYNERGY_FILE, jv.synergy_schema())
    if got is not None:
        nums = [x for row in got["duplicates"] + got["relations"] for x in row["units"]]
        nums += [x for row in got["order"] for x in (row["first"], row["then"])]
        errs += [f"単位 {x} は無い（単位は 1〜{len(keys)}）" for x in sorted(set(nums)) if x not in keys]
        errs += [f"$.duplicates・relations: 同じ単位だけを並べた行（{row['units']}）" for row in got["duplicates"] + got["relations"]
                 if len(set(row["units"])) < 2]
    if errs:
        return {"state": jv.UNVERIFIED, "errors": errs}

    def group(rows):
        return [{"units": [keys[x] for x in dict.fromkeys(r["units"])], "why": r["why"],
                 **({"place": r["place"]} if "place" in r else {})} for r in rows]
    return {"state": jv.CHECKED, "why": got["why"], "duplicates": group(got["duplicates"]), "relations": group(got["relations"]),
            "order": [{"first": keys[r["first"]], "then": keys[r["then"]], "why": r["why"]} for r in got["order"]]}


def merge_on(jdir, repo) -> dict:
    """元 works/blk-judge/lib/judgeverify.py:285。裏取りのまとめ。返り {ok, reason}。番号の控えが無ければ（支度が go 偽・支度が
    走らなかった）回さなかった形の申し送りを置いて ok。在れば単位ごとに答えのファイルを確かめ（型・番号・not_root の本当の根）、
    相乗りの番号を単位の key に戻して judge-verify.json に書く（単位は消さない）。束ね役か下請けが作業ツリーを変えていれば
    止めの控え（VERIFY_STOP）を置いて ok 偽（元は盤面を止めた）"""
    jdir = pathlib.Path(jdir)
    plan = jv._read_json(jdir / jv.PLAN_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("units"), list):
        if not (jdir / jv.VERIFY_FILE).is_file():
            verify_not_run(jdir, "判定の裏取りの支度が走らなかった（番号の控えが無い）")
        return {"ok": True, "reason": ""}
    snap = jv._read_json(jdir / VERIFY_TREE_FILE)
    moved = core_accept.tree_moved({k: snap[k] for k in core_accept.TREE_KEYS}, pathlib.Path(repo)) \
        if isinstance(snap, dict) and all(k in snap for k in core_accept.TREE_KEYS) else ["作業ツリーの写しが読めない"]
    answers = pathlib.Path(plan.get("answers") or jdir / VERIFY_ANSWERS_DIR)
    keys = {r["n"]: r["key"] for r in plan["units"]}
    rows = [_check_unit(answers, n, key) for n, key in keys.items()]
    syn = _check_synergy(answers, keys)
    jv._write_json(jdir / jv.VERIFY_FILE, {"units": rows, "synergy": syn})
    if moved:
        reason = "判定の裏取りの束ね役か下請けが作業ツリーを変えた（読むだけの役）: " + "・".join(moved)
        write_stop(jdir, VERIFY_STOP, reason)
        return {"ok": False, "reason": reason}
    return {"ok": True, "reason": ""}
# ================================================================ 依頼と判定（A）の終わり


# ================================================================ 材料・前提・目的・素材（B）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 材料・前提・目的・素材（B）の終わり


# ================================================================ 再審と仕様（C）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
import re  # noqa: E402
import subprocess  # noqa: E402

import accept  # noqa: E402  （作業ツリーの姿 tree_state・tree_moved）
from engine.util import READ_CAP, pick, read_capped  # noqa: E402
import querytest  # noqa: E402
import rolekit  # noqa: E402
import specblk  # noqa: E402
import tree_run  # noqa: E402

# ---------------------------------------------------------------- 仕様の段（元 works/.shared/core/graphloops/rules/review-loop.py:3852〜4043）
# 元 review-loop.py:3860〜3866（字は元のまま）
SPEC_FLOW = "spec"
SPEC_ORIGIN = "仕様（人が承認した受け入れ条件。テストの本文は writer が書いた）"
SPEC_PROVENANCE = "【仕様の受け入れ条件——テストの本文は writer が書き、人は承認しただけ。役の観察と同じく反証の対象】"
GWT = ("Given", "When", "Then")
# 役の名（with: の role）→ 受けた返答の置き場の名（J/<名>.json）と拒否の控えの名（rolekit.with_done の name）
SPEC_ROLES = {"write": "spec-write", "review": "spec-review", "revise": "spec-revise"}
# 役の名 → 写しの graph の節（拒否の文の頭。元 specblk.ROLES）
SPEC_NODES = {"write": "spec.write", "review": "spec.review", "revise": "spec.revise"}
SPEC_ASK_FILE = "spec-ask.json"     # 関所に見せた仕様（受け入れ条件ごとの sha256 つき。元 loop_state.spec_pending）と文
# 仕様の関所の止めの理由（今の works の report.py:173-174 の REQUEST_BY・HUMAN_BY の頭 + 関所の所。H5 の human:<所>・request:<所>）
SPEC_GATE = "spec-gate"
SPEC_GATE_HUMAN = "human:" + SPEC_GATE
SPEC_GATE_REQUEST = specblk.FLAG_BY_PREFIX + SPEC_GATE


def sha_file(p):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3901。役が指したファイルの sha256（読めない・通常のファイルでない・
    上限を超えるなら None）——役が指したパスを開く所は read_capped を通す"""
    import hashlib
    data, _why = read_capped(str(p), READ_CAP)
    return None if data is None else hashlib.sha256(data).hexdigest()


def _file_sha(root, rel):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3896"""
    p = pathlib.Path(root) / rel
    return sha_file(p) if p.is_file() else None


def _spec_errors(spec, root):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3908。仕様の形（post_check の共通部分）: 鍵が一意・受け入れ条件が要件を指す・
    要件は 1 件以上の受け入れ条件を持つ・テストのファイルが在ってその名前と Given/When/Then を含む。対象の根は引数 root（元は _repo_root）"""
    root = pathlib.Path(root or ".")
    reqs, acs = spec["requirements"], spec["acceptance"]
    errs = _keys_once(reqs, "requirements") + _keys_once(acs, "acceptance")
    rkeys = {r["key"] for r in reqs}
    errs += [f"acceptance '{a['key']}' の requirement '{a['requirement']}' が requirements に無い" for a in acs if a["requirement"] not in rkeys]
    errs += [f"要件 '{k}' に受け入れ条件が無い——実行できるテストを 1 つ以上書け" for k in sorted(rkeys - {a["requirement"] for a in acs})]
    for a in acs:
        data, why = read_capped(str(root / a["file"]), READ_CAP)
        if data is None:
            errs.append(f"acceptance '{a['key']}' のテストのファイル {a['file']} が読めない（{why}）——対象リポジトリに先に書け")
            continue
        text = data.decode("utf-8", errors="replace")
        if a["name"] not in text:
            errs.append(f"acceptance '{a['key']}' の name '{a['name']}' が {a['file']} に無い")
        miss = [w for w in GWT if w not in text]
        if miss:
            errs.append(f"acceptance '{a['key']}' の {a['file']} に {'/'.join(miss)} が無い——受け入れ条件は Given/When/Then をテストの中に書く")
    return errs


def spec_write_output(out, root):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3931。節の名は spec.write（元の nid）"""
    errs = _spec_errors(out, root)
    if errs:
        raise Reject(f"{SPEC_NODES['write']}: " + "; ".join(errs))


def spec_review_output(out):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3937"""
    faces = out.get("faces") or []
    errs = _keys_once(faces, "faces")
    if not faces and blank(out.get("faces_none"), 20):
        errs.append("穴を挙げないなら faces_none に何を確かめて無いと言えるかを書け")
    if errs:
        raise Reject(f"{SPEC_NODES['review']}: " + "; ".join(errs))


def spec_revise_output(out, review, root):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3946。審査の穴に key ごとに 1 度だけ答える（語彙は事前審査への答え
    plan_faces と同じ absorbed / declared）。審査の返答は引数 review（受けた J/spec-review.json。元は b.latest_output("spec.review")）"""
    asked = {f["key"] for f in (review or {}).get("faces") or []}
    rows = out["handled"]
    errs = _keys_once(rows, "handled")
    errs += [f"handled の key '{r['key'][:40]}' は仕様の審査に無い" for r in rows if r["key"] not in asked]
    errs += [f"仕様の審査の '{k[:40]}' に応答が無い——absorbed（どう取り込んだか）か declared（残す理由）で答えろ"
             for k in sorted(asked - {r["key"] for r in rows})]
    errs += _spec_errors(out["spec"], root)
    if errs:
        raise Reject(f"{SPEC_NODES['revise']}: " + "; ".join(errs))


def spec_flow(v):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3870。仕様の道を選んだ run か（条件の関数。spec.* の節だけが読む）"""
    got = v("loop.flow", None)
    return got == SPEC_FLOW, (f"仕様の道を選んだ run（flow={got}）" if got == SPEC_FLOW else
                              "仕様の道を選んでいない run（init --input flow=spec が無い）——今の流れのまま")


def spec_faces_open(v):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3883"""
    n = len((v("out.spec.review", None) or {}).get("faces") or [])
    return bool(n), f"仕様の審査が挙げた穴は {n} 件"


def spec_revise_due(v):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3889。仕様の道を選んだ run で、仕様の審査が穴を挙げたとき（spec.revise の条件）"""
    ok, why = spec_flow(v)
    return spec_faces_open(v) if ok else (ok, why)


def spec_view(review):
    """spec_revise_due が読む見方 v(鍵, 既定)。仕様の段はこのブロックの入口が仕様の道を選んだ時だけ走るので loop.flow は spec、
    out.spec.review は受けた審査の返答（無ければ既定）"""
    vals = {"loop.flow": SPEC_FLOW, "out.spec.review": review}

    def v(key, default=None):
        got = vals.get(key)
        return default if got is None else got
    return v


def spec_now(jdir):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3877 の _spec_now。いまの仕様——直した版（J/spec-revise.json の spec）が
    在ればそれ、無ければ最初の版（J/spec-write.json）。どちらも無ければ None"""
    rv = read_json(pathlib.Path(jdir) / f"{SPEC_ROLES['revise']}.json")
    return rv["spec"] if rv else read_json(pathlib.Path(jdir) / f"{SPEC_ROLES['write']}.json")


def spec_take(jdir, role, reply, root) -> dict:
    """仕様の役の返答を受け付ける（元 works/blk-spec/lib/specblk.py:213 の take と、写しの rules の post_check
    spec_write_output・spec_review_output・spec_revise_output）。返り {ok, reason, revise}。
    - 読むだけの役（review）は作業ツリーを、書く役の返答を受けた時に置いた写し（J/spec-snapshot-spec.review.json。元 prep が審査役を
      起こす前に置いた物）と比べ（accept.tree_moved）、変わっていれば拒む。書く役（write・revise）はテストのファイルを書くので比べない
    - 通れば返答を J/spec-<役>.json に置く（revise の spec が今の仕様になる。spec_now）。write が通ったら審査役の前の作業ツリーの写しを置く
    - revise は受けた審査の穴で spec_revise_due が真の時だけ真（直す輪を回すか）
    返答が dict でない・形が違う・役の名を知らない時も拒否として返す（投げない）"""
    jdir, root = pathlib.Path(jdir), pathlib.Path(root)
    if role not in SPEC_ROLES:
        return {"ok": False, "reason": f"役 {role!r} を知らない（{' / '.join(SPEC_ROLES)}）", "revise": False}
    nid = SPEC_NODES[role]
    snap_path = jdir / specblk.snapshot_name(SPEC_NODES["review"])
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{nid}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        if role == "review":
            snap = read_json(snap_path)
            if not (isinstance(snap, dict) and set(accept.TREE_KEYS) <= set(snap)):
                raise Reject(f"{snap_path} が無い・形が違う——書く役の返答を受けた時に置く（審査役を起こす前の作業ツリーと比べられない）")
            moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, root)
            if moved:
                raise Reject("読むだけの役が作業ツリーを変えた: 仕様の審査は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                             "ファイルを変えてはいけない（変えた物を元に戻せ）（" + "・".join(moved) + "）")
            spec_review_output(reply)
        elif role == "write":
            spec_write_output(reply, root)
            snap = accept.tree_state(root)
        else:
            spec_revise_output(reply, read_json(jdir / f"{SPEC_ROLES['review']}.json"), root)
    except Reject as e:
        return {"ok": False, "reason": str(e), "revise": False}
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return {"ok": False, "reason": f"{nid}: 返答の形が違う（{type(e).__name__}: {e}）", "revise": False}
    jdir.mkdir(parents=True, exist_ok=True)
    write_json(jdir / f"{SPEC_ROLES[role]}.json", reply)
    if role == "write":
        write_json(snap_path, snap)
    revise = role == "review" and spec_revise_due(spec_view(reply))[0]
    return {"ok": True, "reason": "", "revise": bool(revise)}


def spec_approve(spec, review, revise, root):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3970。仕様を人に諮る問いを組む。**受け入れ条件の run は走らせずに字面を
    見せる**——走らせるのは人が字面を見て通した後（spec_freeze）。返り (pending, asking): pending は関所に見せた仕様（受け入れ条件ごとの
    今の sha256 つき。元 loop_state.spec_pending）、asking は盤面の問いの形 {node, decision, reason, kinds, in_round, question, items,
    options}（specblk.gate_text が文にする）。review・revise は受けた返答（元 b.latest_output）"""
    root = pathlib.Path(root or ".")
    rows = [{**a, "sha256": _file_sha(root, a["file"])} for a in spec["acceptance"]]
    pending = {"requirements": spec["requirements"], "acceptance": rows, "out_of_scope": spec.get("out_of_scope") or []}
    rv = review or {}
    handled = {r["key"]: r for r in (revise or {}).get("handled") or []}
    items = [f"要件 {r['key']}: {r['text']}" for r in spec["requirements"]]
    items += [f"受け入れ条件 {r['key']}（要件 {r['requirement']}）: {r['file']} の {r['name']}——承認すると engine が `{r['run']}` を"
              "作業ツリーで走らせる（承認の前には走らせていない）" for r in rows]
    items += [f"審査の穴 [{f['kind']}] {f['key']}: {f['why'][:200]}——" + (f"{handled[f['key']]['handled']}: {handled[f['key']]['how'][:200]}" if f["key"] in handled else "答え無し")
              for f in rv.get("faces") or []]
    asking = {"node": specblk.APPROVE, "decision": "ask", "reason": "spec_approval",
              "kinds": ["spec_approval"], "in_round": True,
              "question": ("仕様（要件と受け入れ条件）を承認するか。承認すると各受け入れ条件の run のコマンドを走らせて承認の時点の終了コードを取り、"
                           "受け入れ条件を記録に固定し、判定と修正案の基準にする"
                           "（continue --note <承認の言葉や条件>）。承認しないなら run をここで止める（stop）——仕様を直してから新しい run で始めよ"),
              "items": items, "options": ["continue", "stop"]}
    return pending, asking


def spec_ask(jdir, root, run_id) -> dict:
    """関所を開くか・文 {ask, message}（元 works/blk-spec/lib/specblk.py:253 の ask と :343 の collect の止めの道）。
    止めの控えが在れば開かない。どれかの役の輪が諦めた（rolekit.given_up_reason）・受けた返答が足りない（書く・審査・穴が在るのに
    直す）なら開かずに works:spec で止める（ja.write_stop）。開く時は spec_approve の問いを specblk.gate_text で文にし、
    J/spec-ask.json に {pending, asking, message} を置く"""
    jdir = pathlib.Path(jdir)
    closed = {"ask": False, "message": ""}
    if read_stop(jdir):
        return closed
    for name in SPEC_ROLES.values():
        why = rolekit.given_up_reason(jdir, name)
        if why:
            write_stop(jdir, SPEC_STOP, why)
            return closed
    got = {role: read_json(jdir / f"{name}.json") for role, name in SPEC_ROLES.items()}
    pend = [SPEC_NODES[r] for r in ("write", "review") if got[r] is None]
    if not pend and got["revise"] is None and spec_revise_due(spec_view(got["review"]))[0]:
        pend.append(SPEC_NODES["revise"])
    if pend:
        write_stop(jdir, SPEC_STOP, f"仕様が固まっていない（待ちの節: {'・'.join(pend)}）——輪か関所が回らなかった")
        return closed
    pending, asking = spec_approve(spec_now(jdir), got["review"], got["revise"], root)
    message = specblk.gate_text(asking, run_id=run_id)
    write_json(jdir / SPEC_ASK_FILE, {"pending": pending, "asking": asking, "message": message})
    return {"ask": True, "message": message}


def _spec_run(root, cmd):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3959。受け入れ条件 1 件の run を今の作業ツリーで走らせた終了コード
    （走らなければ None と理由）。走らせるのは人が関所でこのコマンドの字面を見て通した後だけ（spec_freeze）。
    元の engine の run_tree（時間切れ 600 秒で木ごと止める）は lib に無いので、lib/tree_run.run（/bin/sh -c。止める信号で木ごと止める）で走らせる。
    期限は置かない（持ち主の決め no-timeouts）"""
    try:
        code = tree_run.run(["/bin/sh", "-c", cmd], cwd=str(root), env=tree_run.outside_env(os.environ),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return None, f"{type(e).__name__}: {e}"
    return code, ""


def spec_freeze(jdir, root, pend, approval) -> dict:
    """元 works/.shared/core/graphloops/rules/review-loop.py:4010。承認済みの仕様を J/spec.json（今の works の記録の process.spec の形:
    requirements・acceptance[{key, requirement, file, name, run, sha256, exit_at_approval}]・out_of_scope・approval）に 1 度だけ固め、
    受け入れ条件を依頼の行として J/request.json に積む（1 件の受け入れ条件が 1 行。元は人の依頼のバッチ {round, origin: SPEC_ORIGIN,
    findings} を record.process.request_findings に積んだ。ここは依頼の行の並びなので行だけを足し、出どころは各行の頭 SPEC_PROVENANCE が持つ）。
    承認の時点の終了コード（exit_at_approval）はここで各 run を走らせて取る。pend は spec_approve の pending、approval は答えの記録。
    1 run は 1 周なので round は 1。**拒む回は置き場を変えない**。返り {ok, problems}"""
    jdir = pathlib.Path(jdir)
    cur = read_json(jdir / REQUEST_FILE, [])
    if not isinstance(cur, list) or not all(isinstance(r, dict) for r in cur):
        return {"ok": False, "problems": [f"依頼の行（{REQUEST_FILE}）の型が崩れている（行の並びでない）"]}
    rows = []
    for a in pend["acceptance"]:
        code, err = _spec_run(root, a["run"])
        rows.append({**a, "exit_at_approval": code, **({"run_error": err} if err else {})})
    spec = {**pend, "acceptance": rows, "approval": approval}
    findings = [{"where": f"{a['file']}: {a['name']}",
                 "text": f"{SPEC_PROVENANCE}受け入れ条件 {a['key']}（要件 {a['requirement']}）がまだ満たされていない——承認の時点で `{a['run']}` が "
                         + ("走らない" if a["exit_at_approval"] is None else
                            "既に exit 0（緑——赤を見ていないので、テストが要件を確かめているかを疑え）" if a["exit_at_approval"] == 0 else
                            f"exit {a['exit_at_approval']}"),
                 "mechanism": f"Given/When/Then の本文は {a['file']} の {a['name']} が正本（記録に写さない）。要件: "
                              + next(r["text"] for r in pend["requirements"] if r["key"] == a["requirement"]),
                 "measured": f"承認の時点（round 1）の実測: `{a['run']}` → "
                             + (a.get("run_error") or "") + ("" if a["exit_at_approval"] is None else f"exit {a['exit_at_approval']}"),
                 "false_positive_if": f"`{a['run']}` が今の版で exit 0 で、{a['file']} が承認の後に変わっていない（sha256 {str(a['sha256'])[:12]}）なら誤り"}
                for a in rows]
    write_json(jdir / specblk.SPEC_FILE, spec)
    write_json(jdir / REQUEST_FILE, cur + findings)
    return {"ok": True, "problems": []}


def spec_answer(jdir, root, raw) -> dict:
    """仕様の関所の答え（with: の {from: $spec-gate.output, if_skipped: null} の字）を受ける（元 works/blk-spec/lib/specblk.py:302 の
    answer と :343 の collect と、写しの rules の on_answer_in_round の仕様の承認）。返り {go, reason}:
    - 開かなかった（"null"）: go false（前の節が止めた。止めの控えが無ければ works:spec で止める）
    - 止める語（stop・reject）: 一言（空なら GATE_STOP_NOTE）が "request:" で始まれば止め札 request:spec-gate、ほかは人の止め
      human:spec-gate で止める（report が stopped_by_request と stopped_by_human に分ける）
    - 通す語（approve・continue）: J/spec-ask.json の仕様を spec_freeze で固める（もう J/spec.json が在れば 2 度固めない）
    答えの形の誤り（知らない語など）は works:spec で止めて go false"""
    jdir = pathlib.Path(jdir)
    try:
        gate = specblk.parse_gate(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    except rolekit.BoardGap as e:
        write_stop(jdir, SPEC_STOP, str(e))
        return {"go": False, "reason": str(e)}
    if gate is None:
        if read_stop(jdir) is None:
            write_stop(jdir, SPEC_STOP, "仕様の関所が開かなかった（仕様が固まっていない）")
        return {"go": False, "reason": read_stop(jdir)["reason"]}
    if gate["decision"] in specblk.GATE_STOP:
        note = gate["text"] if gate["text"].strip() else specblk.GATE_STOP_NOTE
        by = SPEC_GATE_REQUEST if gate["text"].strip().startswith(specblk.FLAG_BY_PREFIX) else SPEC_GATE_HUMAN
        write_stop(jdir, by, note)
        return {"go": False, "reason": f"人が関所で仕様を承認しなかった: {note}"}
    if (jdir / specblk.SPEC_FILE).exists():
        return {"go": True, "reason": ""}
    asked = read_json(jdir / SPEC_ASK_FILE)
    if not isinstance(asked, dict) or not isinstance(asked.get("pending"), dict):
        why = f"{SPEC_ASK_FILE} が無い・形が違う——関所に見せた仕様が無いので固められない"
        write_stop(jdir, SPEC_STOP, why)
        return {"go": False, "reason": why}
    approval = {"round": 1, "node": specblk.APPROVE, "kinds": list(asked.get("asking", {}).get("kinds") or []),
                "answer": "continue", "note": gate["text"]}
    got = spec_freeze(jdir, root, asked["pending"], approval)
    if not got["ok"]:
        why = "仕様を固められない: " + "; ".join(got["problems"])
        write_stop(jdir, SPEC_STOP, why)
        return {"go": False, "reason": why}
    return {"go": True, "reason": ""}


# ---------------------------------------------------------------- 再審（元 works/.shared/core/rejudge.py と写しの rules の rejudge_output）
REJUDGE_NODE = "p2.rejudge"          # 写しの再審の節（元 rejudge.ROLE_OF の鍵）
REJUDGE_ROLE = "rejudge"             # 役の名（拒否の控え rejects-rejudge.json の名・差の行の pass）
REJUDGE_VERDICTS = ("採る", "退ける", "一部採る")   # 写しの schema の verdict の enum
REJUDGE_SETTLED = ("採る", "退ける")               # 元 rules:3210。決着して異議を降ろす答え
# 元 写しの graph の p2.rejudge の writes（to: units の pick）。再審が単位を置き換える時に残す欄で、前後の差もこの欄だけを比べる
REJUDGE_UNIT_FIELDS = ("key", "label", "disposition", "reason", "reopen_evidence")
REJUDGE_BRIEF = "brief.md"
REJUDGE_BEFORE = "units-before.json"          # 元 rejudge-units-before-<役>.json
REJUDGE_SNAPSHOT = "rejudge-snapshot.json"    # 元 rejudge.SNAPSHOT_NAME（役を起こす前の作業ツリーの姿）
REJUDGE_DIFF = "rejudge-diff.json"            # 元 rejudge.DIFF_NAME
REJUDGE_EXIT = "rejudge-exit.json"            # 元 rejudge.EXIT_NAME（再審のブロックの出口の形）
REJUDGE_REPLY = "rejudge-reply.json"          # 受けた再審の返答の並び（元 writes の append to: process.rejudge）
JUDGMENT_FILE = "judgment.json"               # 判定の置き場の名（J の 1 回目の物を読み、R に再審の後の物を書く）
# 元 rejudge.py:77。修正役に貼った番号の書き方（no N・No.N・#N・N 番）。全角の数字も \d に当たる
_NUMBERS = (re.compile(r"(?<![A-Za-z])no\.?\s*(\d+)", re.IGNORECASE), re.compile(r"[#＃]\s*(\d+)"), re.compile(r"(\d+)\s*番"))
# 判定役の材料のうち、再審の役に Read させる 1 回目のファイル（在る物だけを brief に並べる）
REJUDGE_MATERIALS = (("1 回目の判定（全部の欄）", JUDGMENT_FILE), ("判定役の材料", "diagnose-brief.md"),
                     ("対象差分", "diff.patch"), ("前提の制約", "premises.json"), ("凍結した目的", "purpose.json"),
                     ("素材の状態", "materials.json"), ("世界の解の行", "world.jsonl"), ("仕様", "spec.json"),
                     ("判定の裏取り", "judge-verify.json"), ("並行 PR の外す範囲", "pr-excluded.json"))


def rejudge_output(out):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3186。擦り合わせの返答: **新しい事実を自分で確かめたこと**を要求する。
    依頼者の指定の条件 1（反論は新しい事実を伴うときだけ通す）と 3（判定を確定する権限は移らない）を機械で持つ。
    1 run は 1 周なので、元の defer の台帳（前の周の defer の再浮上）は空で当てる物が無く、往復の回数の数え（loop_state）は
    再審の輪（max_iterations）と拒否の控えが持つ"""
    fact = (out.get("new_facts") or "").strip()
    if blank(fact, 20):
        raise Reject(f"{REJUDGE_NODE}: new_facts が空同然——回す側が出した事実を**自分で確かめた結果**を書け"
                     "（確かめずに採る／退けるのは、どちらも判定を都合よく使うことになる）")


def _rejudge_type_errors(out):
    """写しの p2.rejudge の schema のうち、受け付けが値で読む欄（verdict・new_facts・units[].key・units[].label）の型の誤り"""
    errs = []
    if out.get("verdict") not in REJUDGE_VERDICTS:
        errs.append(f"$.verdict は {' / '.join(REJUDGE_VERDICTS)} のどれか（{out.get('verdict')!r}）")
    if not isinstance(out.get("new_facts"), str):
        errs.append("$.new_facts が文字列でない")
    units = out.get("units")
    if not isinstance(units, list):
        return errs + ["$.units が配列でない"]
    for i, u in enumerate(units):
        if not isinstance(u, dict) or not isinstance(u.get("key"), str) or not u.get("key"):
            errs.append(f"$.units[{i}].key が無い")
        elif u.get("label") not in LABELS:
            errs.append(f"$.units[{i}].label は {' / '.join(LABELS)} のどれか（{u.get('label')!r}）")
    return errs


def _named_numbers(text):
    """元 works/.shared/core/rejudge.py:465"""
    got = set()
    for rx in _NUMBERS:
        for m in rx.finditer(text or ""):
            got.add(int(m.group(1)))
    return got


def diff_units(before, after, objection_text, numbered, fields=None) -> dict:
    """元 works/.shared/core/rejudge.py:473。前後の単位を key で比べる。{changed: [{key, kind, field?, before?, after?, named}],
    unnamed_changed: [key], lowered: [key]}
    - kind: changed（fields の欄が変わった。欄ごとに 1 行）・added・removed
    - named: key が異議の文に部分一致で現れるか、修正役に貼った番号（numbered の i 番目が番号 i+1）が no N・#N・N 番の形で
      現れるか。名指しを読み取れなければ偽（変化は争点外として強調する側に倒す）
    - lowered: block から他のラベルに下げた単位（指示書は禁じるが写しの規則は拒まない）
    fields の既定は写しの graph の writes の pick（REJUDGE_UNIT_FIELDS。元 unit_fields()）"""
    fields = [f for f in (fields or REJUDGE_UNIT_FIELDS) if f != "key"]
    bmap = {u.get("key"): u for u in before or []}
    amap = {u.get("key"): u for u in after or []}
    nums = _named_numbers(objection_text)
    by_number = {numbered[n - 1] for n in nums if 1 <= n <= len(numbered or [])}

    def named(k):
        return bool(objection_text) and (k in objection_text or k in by_number)

    def pick_(u):
        return {f: u[f] for f in ["key", *fields] if f in u}

    changed, unnamed, lowered = [], [], []
    for k in [*bmap, *(k for k in amap if k not in bmap)]:
        nm = named(k)
        rows = []
        if k not in amap:
            rows.append({"key": k, "kind": "removed", "before": pick_(bmap[k]), "named": nm})
        elif k not in bmap:
            rows.append({"key": k, "kind": "added", "after": pick_(amap[k]), "named": nm})
        else:
            for f in fields:
                if bmap[k].get(f) != amap[k].get(f):
                    rows.append({"key": k, "kind": "changed", "field": f, "before": bmap[k].get(f), "after": amap[k].get(f),
                                 "named": nm})
            if bmap[k].get("label") == "block" and amap[k].get("label") != "block":
                lowered.append(k)
        changed += rows
        if rows and not nm:
            unnamed.append(k)
    return {"changed": changed, "unnamed_changed": unnamed, "lowered": lowered}


def _rejudge_brief(jdir, objection, judgment, start) -> str:
    """再審の役が読む材料（元 rejudge.render が p2.rejudge.md の穴を盤面の値で埋めた所。規則の文は指示書 commands/rejudge.md が持つ）"""
    def block(v):
        return "```json\n" + json.dumps(v, ensure_ascii=False, indent=1) + "\n```"
    questions = pick(judgment.get("questions") or [], ["key", "kind", "status"])
    diagnosis = {k: judgment[k] for k in ("framing", "one_shot") if k in judgment}
    policy = ""
    pmd = (start or {}).get("policy_md") or ""
    if pmd and pathlib.Path(pmd).is_file():
        policy = pathlib.Path(pmd).read_text(encoding="utf-8", errors="replace")
    mats = [f"- {what}: `{pathlib.Path(jdir) / name}`" for what, name in REJUDGE_MATERIALS if (pathlib.Path(jdir) / name).is_file()]
    lines = ["# 再審の材料（同じ run の 1 回目の判定と、修正役の異議）", "",
             "## 回す側の異議", "", objection.strip(), "",
             "## 今の周のユニット", "", block(pick(judgment.get("units") or [], ["key", "label", "disposition"])), "",
             "## 今の周の台帳", "", block(questions) if questions else "無い", "",
             "## 自分の見立て（P2 で書いたもの）", "", block(diagnosis) if diagnosis else "無い", "",
             "## 1 回目の判定と材料（Read して読む）", "", *(mats or ["- 無い"]), "",
             "## 人の方針", "", policy.strip() or "無い", ""]
    return "\n".join(lines)


def rejudge_prep(jdir, rdir, objection, root) -> dict:
    """再審の支度（元 works/.shared/core/rejudge.py:372 の prep と :310 の snap。会話を確かめる session_ready は持たない——再審の役は
    新しい会話で起き、保存した 1 回目の判定 J/judgment.json と材料を読む。計画の「実行基盤で書けない所」の狭め）。返り {go, brief_file, reason}。
    - 1 回目の判定が無い（判定の道を通っていない run）: 再審せずに R に止めの控え works:rejudge-session（元 route が会話を確かめられない時の語）
    - 異議が空・判定が読めない・作業ツリーの姿が引けない: R に works:rejudge で止める
    - 通る時: R/brief.md（異議・単位・台帳・見立て・材料のパス・人の方針）、1 回目の前だけ R/units-before.json
      （{node, units, objection, numbered_keys}。numbered_keys は今の単位の並び——元の番号の控えの無い時の既定）、
      役を起こす前の作業ツリーの姿 R/rejudge-snapshot.json"""
    jdir, rdir = pathlib.Path(jdir), pathlib.Path(rdir)
    rdir.mkdir(parents=True, exist_ok=True)
    no = {"go": False, "brief_file": "", "reason": ""}
    if not (jdir / JUDGMENT_FILE).is_file():
        why = f"1 回目の判定（{JUDGMENT_FILE}）が無い——判定の道を通っていない run。再審せずに止めた"
        write_stop(rdir, stopby.REJUDGE_SESSION, why)
        return {**no, "reason": why}
    try:
        judgment = read_json(jdir / JUDGMENT_FILE)
        if not isinstance(judgment, dict) or not isinstance(judgment.get("units"), list):
            raise ValueError(f"{jdir / JUDGMENT_FILE} の形が違う（units の並びが無い）")
        if not (objection or "").strip():
            raise ValueError("異議の文が空——再審にかける物が無い")
        snap = accept.tree_state(pathlib.Path(root))
        start = read_json(jdir / START_FILE, {}) or {}
    except (ValueError, Reject) as e:
        write_stop(rdir, stopby.REJUDGE, str(e))
        return {**no, "reason": str(e)}
    before = rdir / REJUDGE_BEFORE
    if not before.exists():
        write_json(before, {"node": REJUDGE_NODE, "units": judgment["units"], "objection": objection,
                            "numbered_keys": [u.get("key") for u in judgment["units"] if isinstance(u, dict)]})
    write_json(rdir / REJUDGE_SNAPSHOT, snap)
    brief = rdir / REJUDGE_BRIEF
    brief.write_text(_rejudge_brief(jdir, objection, judgment, start if isinstance(start, dict) else {}), encoding="utf-8")
    return {"go": True, "brief_file": str(brief), "reason": ""}


def rejudge_take(jdir, rdir, reply, root) -> dict:
    """再審の役の返答を受け付ける（元 works/.shared/core/rejudge.py:421 の take）。返り {ok, reason, verdict}。順: 作業ツリーを
    R/rejudge-snapshot.json と比べる → 写しの型（_rejudge_type_errors）→ class_query の例で問いを試して例を外す（querytest。例は
    R/query-examples.json に足す）→ rejudge_output。拒否は {ok: False, reason}（置き場を変えない）。通れば:
    - R/judgment.json: 1 回目の判定（J/judgment.json）の units を返答の units（writes の pick: REJUDGE_UNIT_FIELDS）で置き換えた物。
      1 回目の物は上書きしない
    - R/rejudge-reply.json に受けた返答を足し（元 writes の append to: process.rejudge）、R/rejudge-diff.json に単位の前後の差を 1 行
    返答の形の誤り・支度の欠けも拒否として返す（投げない）"""
    jdir, rdir = pathlib.Path(jdir), pathlib.Path(rdir)
    no = {"ok": False, "verdict": ""}
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{REJUDGE_NODE}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        saved = read_json(rdir / REJUDGE_SNAPSHOT)
        if not isinstance(saved, dict) or not set(accept.TREE_KEYS) <= set(saved):
            raise Reject(f"作業ツリーの写し {rdir / REJUDGE_SNAPSHOT} が無い・形が違う（rejudge-prep が先に走る）")
        moved = accept.tree_moved({k: saved[k] for k in accept.TREE_KEYS}, pathlib.Path(root))
        if moved:
            raise Reject("読むだけの役が作業ツリーを変えた: 再審の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                         "ファイルを変えてはいけない（" + "・".join(moved) + "）")
        errs = _rejudge_type_errors(reply)
        if errs:
            raise Reject(f"{REJUDGE_NODE}: 返答が型に合わない: " + "; ".join(errs))
        before_doc = read_json(rdir / REJUDGE_BEFORE)
        if not isinstance(before_doc, dict):
            raise Reject(f"{REJUDGE_ROLE} の前の単位の写しが無い（rejudge-prep が先に走る）")
        errs = querytest.problems(reply.get("units"), is_open)
        if errs:
            raise Reject("class_query の例が問いと合わない: " + "; ".join(errs))
        reply, examples = querytest.split(reply, is_open)
        rejudge_output(reply)
        first = read_json(jdir / JUDGMENT_FILE) or {}
    except Reject as e:
        return {**no, "reason": str(e)}
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return {**no, "reason": f"{REJUDGE_NODE}: 返答の形が違う（{type(e).__name__}: {e}）"}
    if examples:
        querytest.save(rdir, examples)
    units = [{f: u[f] for f in REJUDGE_UNIT_FIELDS if f in u} for u in reply["units"]]
    write_json(rdir / JUDGMENT_FILE, {**(first if isinstance(first, dict) else {}), "units": units})
    write_json(rdir / REJUDGE_REPLY, (read_json(rdir / REJUDGE_REPLY, []) or []) + [reply])
    verdict = reply.get("verdict", "")
    row = {"round": 1, "pass": REJUDGE_ROLE, "node": REJUDGE_NODE, "verdict": verdict,
           **diff_units(before_doc.get("units") or [], units, before_doc.get("objection") or "",
                        before_doc.get("numbered_keys") or [])}
    write_json(rdir / REJUDGE_DIFF, (read_json(rdir / REJUDGE_DIFF, []) or []) + [row])
    return {"ok": True, "reason": "", "verdict": verdict}


def rejudge_collect(rdir) -> dict:
    """再審の出口（元 works/.shared/core/rejudge.py:525 の collect と :513 の unsettled の 0.21.0 の形）。R/rejudge-exit.json（今の works の
    blk-rejudge/schemas/rejudge-exit.schema.json の形 {ok, reason, passes, verdicts, unsettled, objection, new_open_units, lowered,
    unnamed_changed, diff_file, reads_file}）を書いて返す。
    - 受けた再審の判定（R/judgment.json）が無く、止めの控えも無い（輪が 3 回とも拒まれた）: ok false・最後の拒否の文で works:rejudge で止める
    - 既に止まっている（rejudge-session など）: ok true（後ろの節が止めの控えを読む。元と同じ）
    new_open_units と lowered は最初の再審の前の単位（R/units-before.json）と今の単位の比べ。unsettled は最後の答えが 採る・退ける なら
    決着（異議を降ろす）。reads_file は読んだ証拠を持ち込まないので空"""
    rdir = pathlib.Path(rdir)
    judgment = read_json(rdir / JUDGMENT_FILE)
    rows = read_json(rdir / REJUDGE_DIFF, []) or []
    before = read_json(rdir / REJUDGE_BEFORE)
    ok, reason = True, ""
    if judgment is None and read_stop(rdir) is None:
        ok = False
        reason = rolekit.given_up_reason(rdir, REJUDGE_ROLE) or (
            f"{REJUDGE_NODE} の返答を受けないまま再審の輪を抜けた（輪が回らなかった）")
        write_stop(rdir, stopby.REJUDGE, reason)
    verdicts = [r.get("verdict", "") for r in rows]
    new_open, lowered = [], []
    if before is not None and judgment is not None:
        was = {u.get("key"): u for u in before.get("units") or []}
        now_units = judgment.get("units") or []
        new_open = [u["key"] for u in now_units if is_open(u) and not (u["key"] in was and is_open(was[u["key"]]))]
        lowered = [u["key"] for u in now_units
                   if (was.get(u["key"]) or {}).get("label") == "block" and u.get("label") != "block"]
    objection = (before or {}).get("objection") or ""
    settled = not objection or bool(verdicts and verdicts[-1] in REJUDGE_SETTLED)
    unnamed = list(dict.fromkeys(k for r in rows for k in r.get("unnamed_changed") or []))
    diff_p = rdir / REJUDGE_DIFF
    out = {"ok": ok, "reason": reason, "passes": len(rows), "verdicts": verdicts,
           "unsettled": {"text": "" if settled else objection, "settled": settled},
           "objection": objection, "new_open_units": new_open, "lowered": lowered, "unnamed_changed": unnamed,
           "diff_file": str(diff_p) if diff_p.exists() else "", "reads_file": ""}
    write_json(rdir / REJUDGE_EXIT, out)
    return out


def rejudge_verdict(rdir):
    """再審の答えの語（採る・退ける・一部採る）。R/rejudge-exit.json の最後の verdicts（受けた再審が無い・出口が読めなければ None）"""
    try:
        doc = read_json(pathlib.Path(rdir) / REJUDGE_EXIT)
    except ValueError:
        return None
    got = (doc.get("verdicts") or [None])[-1] if isinstance(doc, dict) and doc.get("ok") else None
    return got if got in REJUDGE_VERDICTS else None
# ================================================================ 再審と仕様（C）の終わり


# ================================================================ 並行 PR と世界の解（W）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
import re  # noqa: E402
import shutil as _w_shutil  # noqa: E402

from accept import touched_files as _w_touched_files, tree_moved as _w_tree_moved  # noqa: E402
import forge  # noqa: E402
import ghreads  # noqa: E402
import prcheck  # noqa: E402
import rolekit  # noqa: E402
import worldblk  # noqa: E402
import worldmark  # noqa: E402

PR_DOWNGRADES_FILE = "pr-downgrades.json"        # 申し送りの下書き [{pr, files, note}]（GitHub に投稿しない。報告が人に渡す）
MATERIAL_PR_FILE = f"material-{prcheck.ROLE}.json"   # 並行 PR の素材 {role, reply, materials: {parallel_pr}}
PR_LIMIT = 100   # 元 works/.shared/core/graphloops/scripts/parallel-pr.py:16 の LIMIT（gh pr list の --limit）
# 元 works/.shared/core/graphloops/rules/review-loop.py:2278
GITHUB_REMOTE = re.compile(r"^(?:https?://github\.com/|ssh://git@github\.com[^/]*/|git@github\.com[^:]*:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
# 元 works/blk-pr/scripts/accept.py:21
NO_POST = "このラインは申し送りを投稿しない（持ち主の決定 2026-09-27）。下書きを note に書き handed_over を false にせよ: "
WORLD_FEATURE = "world"   # 元 works/.shared/core/entry.py:420 の WORLD_FEATURE（始めの記録の features_cut の世界の解の語）
WORLD_PURPOSE_FILE = "world-purpose.json"   # 元 works/darkfactory/lib/line_edge.py:141（世界の解の段の入力の目的の文 {purpose_text, means}）
WORLD_ROLES = {"world-classes": worldblk.CLASSES_ROLE, "world-judge": worldblk.JUDGE_ROLE}   # 役の名 → worldblk の控えの名


# ---------------------------------------------------------------- 並行 PR（機械の道）
def _github_repo(repo):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2280 の _github_repo（と works/.shared/core/entry.py の
    github_repo_redacted の、理由の文から URL の userinfo を落とす包み）。並行 PR を引く owner/repo ——（値, 引けない理由）。
    upstream の remote を先に、無ければ origin。git は lib/forge の読みで、対象の根 repo で引く"""
    up = forge._git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    remote = up.strip().split("/", 1)[0] if up and up.strip() else "origin"
    url = forge._git(repo, "remote", "get-url", remote)
    if url is None:
        return None, f"remote '{remote}' の URL が引けない"
    m = GITHUB_REMOTE.match(url.strip())
    if not m:
        return None, forge.redact(f"remote '{remote}' が GitHub でない（{url.strip()[:80]}）——同等のコマンドへの読み替えは役")
    return f"{m.group(1)}/{m.group(2)}", None


def request_wheres(rows) -> list:
    """元 works/.shared/core/graphloops/rules/review-loop.py:203 の request_wheres。依頼の行（judge/request.json の
    [{where, text, …}]）の where の一覧。元は判定から入る run の周（差分が空）だけ返したが、ここでは呼び手の _pr_files が
    差分の空の時だけ使うので同じ所に落ちる"""
    return [r["where"] for r in rows if isinstance(r, dict) and isinstance(r.get("where"), str)] if isinstance(rows, list) else []


def _pr_files(repo, diff_base: str, wheres) -> list:
    """元 works/.shared/core/graphloops/rules/review-loop.py:2293 の _pr_files。交差を取る変更ファイルの集合。差分の根 diff_base
    から今の作業ツリーまでの変更ファイル（lib/accept.touched_files）が空（判定から入る run）なら、依頼の where の文字列に
    含まれる、追跡中のパス"""
    files = []
    if diff_base:
        try:
            files = _w_touched_files(pathlib.Path(repo), diff_base)
        except Reject:
            files = []
    if files:
        return files
    tracked = (forge._git(repo, "ls-files", "-z") or "").split("\0")
    return sorted({t for t in tracked if t and any(t in w for w in wheres)})


def parallel_pr_plan(repo, diff_base: str, wheres, *, which=None) -> dict:
    """元 works/.shared/core/graphloops/rules/review-loop.py:2304 の parallel_pr_plan。返り {fallback: 理由}（役に任せる）・
    {blocked: 理由}（走らせずに not_run）・{repo, head, files}（数えを走らせる）。which は gh を探す口（試験が差し替える）"""
    slug, why = _github_repo(repo)
    if not slug:
        return {"fallback": why}
    if not (which or _w_shutil.which)("gh"):
        return {"fallback": "gh がこの環境に無い"}
    files = _pr_files(repo, diff_base, wheres)
    if not files:
        return {"blocked": "交差を取る変更ファイルの集合が空（差分も、依頼の where が名指す追跡中のパスも無い）——空の集合との交差は何も確かめない"}
    head = (forge._git(repo, "rev-parse", "HEAD") or "").strip()
    return {"repo": slug, "head": head, "files": files}


def parallel_pr_scan(repo, slug: str, head: str, files, *, gh=None) -> tuple:
    """元 works/.shared/core/graphloops/scripts/parallel-pr.py:31 の main。開いている PR を gh -R で引き、自分の PR（headRefOid が
    head）を外して、残った PR の変更ファイルと files の交差を取る。gh は lib/ghreads の読む口（gh(*args) -> (値, 読めない理由,
    no_host)。試験が差し替える）で、読むだけ。返り ({repo, listed, truncated, conflicts: [{pr, files}]}, "") か
    (None, gh が読めなかった理由)"""
    gh = gh or (lambda *args: ghreads._gh(pathlib.Path(repo), *args))
    mine = {f.strip() for f in files if f.strip()}
    prs, why, _ = gh("pr", "list", "-R", slug, "--limit", str(PR_LIMIT), "--json", "number,headRefName,headRefOid")
    if not isinstance(prs, list):
        return None, why or "gh pr list の返りが配列でない"
    others = [pr for pr in prs if isinstance(pr, dict) and pr.get("headRefOid") != head]
    conflicts = []
    for pr in others:
        doc, why, _ = gh("pr", "view", str(pr.get("number")), "-R", slug, "--json", "files")
        if not isinstance(doc, dict):
            return None, why or f"gh pr view {pr.get('number')} の返りが object でない"
        got = {str(f.get("path")).strip() for f in doc.get("files") or [] if isinstance(f, dict) and f.get("path")}
        hit = sorted(got & mine)
        if hit:
            conflicts.append({"pr": str(pr.get("number")), "files": hit})
    return {"repo": slug, "listed": len(prs), "truncated": len(prs) >= PR_LIMIT, "conflicts": conflicts}, ""


def parallel_pr_reply(launch: dict, got, why: str = "") -> dict:
    """元 works/.shared/core/graphloops/rules/review-loop.py:2320 の parallel_pr_reply。数えの結果から返答を組む。交差が在れば
    6 段（hunk を読んで担当の PR に申し送る）が要るので任せ先に回す（{fallback: 理由}）。ほかは {reply: 役の返答の形}。
    元の parallel-pr.py の exit と印字の代わりに、parallel_pr_scan の返り（got, why）を受ける"""
    empty = {"repo": "", "listed": 0, "truncated": False, "conflicts": []}
    if launch.get("blocked"):
        return {"reply": {"material": {"status": "not_run", "reason": launch["blocked"]}, **empty}}
    if got is None:
        return {"reply": {"material": {"status": "awaiting_human", "reason": f"並行 PR の数え（parallel-pr.py の書き直し）が gh を読めない（確かめられなかった）: {str(why)[-600:]}"}, **empty}}
    rest = {k: got.get(k) for k in ("repo", "listed", "truncated")}
    if got.get("conflicts"):
        return {"fallback": f"並行 PR と {len(got['conflicts'])} 件交差した（{[c['pr'] for c in got['conflicts']][:10]}）——交差した hunk を読んで担当の PR に申し送る 6 段は役"}
    if got.get("truncated"):
        return {"reply": {"material": {"status": "awaiting_human", "reason": f"gh pr list が上限 {got.get('listed')} 件で打ち切られた——打ち切られた一覧で衝突なしと書かない"}, **rest, "conflicts": []}}
    return {"reply": {"material": {"status": "clean", "checked": (f"engine が gh -R {got['repo']} で open な PR {got['listed']} 件を引き、自分の PR（headRefOid が HEAD）を除いて、"
                                                            f"変更ファイルの集合と交差 0 件（打ち切りなし）")}, **rest, "conflicts": []}}


def _pr_material(jdir, reply: dict) -> None:
    """並行 PR の素材のファイル（judge/material-pr-check.json）を置く。reply は役の返答の形（excluded を外した物）"""
    write_json(pathlib.Path(jdir) / MATERIAL_PR_FILE,
               {"role": prcheck.ROLE, "reply": reply, "materials": {"parallel_pr": reply["material"]}})


def pr_scan(jdir, repo, *, gh=None, which=None) -> dict:
    """節 pr-scan の中身。元 works/.shared/core/prcheck.py:104 の run_helper（engine の 1〜5 段を走らせ、済んだか役が要るか）と、
    元 works/.shared/core/entry.py:170-193 の forge の組み手（remote が forge でない run は素材を not_applicable（no_forge: …）で埋め、
    役を起こさない）の書き直し。返り {go, go_role, reason}: go は後の段へ進むか（仕様の段が止めた run は偽）、go_role は
    機械で決められず役 pr-check が要るか。機械が決めた時は素材のファイルと外す hunk の空の一覧（judge/pr-excluded.json）を書き、
    役に任せる時は渡し物（judge/pr-brief.json。元 prcheck.snapshot の brief の形）を書く"""
    jdir, repo = pathlib.Path(jdir), pathlib.Path(repo)
    stop = read_stop(jdir)
    if stop:
        return {"go": False, "go_role": False, "reason": f"止めの控えが在る（{stop['stop_reason']}: {stop.get('reason', '')}）"}
    start = start_view(read_json(jdir / START_FILE, {}))
    rows = read_json(jdir / REQUEST_FILE, [])
    head = (forge._git(repo, "rev-parse", "HEAD") or "").strip()
    no_forge = forge.reason(forge.detect(repo))
    if no_forge:
        result = {"reply": {"material": {"status": "not_applicable", "reason": no_forge},
                            "repo": "", "listed": 0, "truncated": False, "conflicts": []}}
    else:
        wheres = request_wheres(rows)
        launch = parallel_pr_plan(repo, start["diff_base"], wheres, which=which)
        if "fallback" in launch:
            result = launch
        elif launch.get("blocked"):
            result = parallel_pr_reply(launch, None)
        else:
            got, why = parallel_pr_scan(repo, launch["repo"], launch["head"], launch["files"], gh=gh)
            result = parallel_pr_reply(launch, got, why)
    if "fallback" in result:
        write_json(jdir / prcheck.BRIEF, {"node": prcheck.NODE, "cwd": str(repo), "base": start["diff_base"],
                                          "changed_files": _pr_files(repo, start["diff_base"], request_wheres(rows)),
                                          "request_wheres": request_wheres(rows), "fallback": result["fallback"]})
        return {"go": True, "go_role": True, "reason": result["fallback"]}
    reply = result["reply"]
    write_json(jdir / prcheck.BRIEF, {"node": prcheck.NODE, "cwd": str(repo), "base": start["diff_base"],
                                      "changed_files": _pr_files(repo, start["diff_base"], request_wheres(rows)),
                                      "request_wheres": request_wheres(rows), "fallback": ""})
    _pr_material(jdir, reply)
    write_json(jdir / prcheck.EXCLUDED, {"node": prcheck.NODE, "head": head, "excluded": []})
    m = reply["material"]
    return {"go": True, "go_role": False, "reason": f"機械が決めた: {m['status']}（{m.get('reason') or m.get('checked') or ''}）"}


# ---------------------------------------------------------------- 並行 PR（役の受け付け）
def check_no_post(reply) -> list:
    """元 works/blk-pr/scripts/accept.py:24 の check_no_post。conflicts[].handed_over が真の行の pr の一覧（空なら通す）"""
    rows = reply.get("conflicts") if isinstance(reply, dict) else None
    if not isinstance(rows, list):
        return []
    return [str(c.get("pr")) for c in rows if isinstance(c, dict) and c.get("handed_over")]


def prcheck_drafts(reply) -> list:
    """元 works/.shared/core/prcheck.py:249 の drafts。受け付けた返答の申し送りの下書き [{pr, files, note}]（note を持つ交差だけ。
    報告の冒頭が人に渡す）。盤面から読む代わりに返答を受ける"""
    return [{"pr": c["pr"], "files": c["files"], "note": c["note"]}
            for c in (reply or {}).get("conflicts", []) if isinstance(c, dict) and c.get("note")]


def prcheck_take(jdir, reply, repo) -> dict:
    """元 works/.shared/core/prcheck.py:199 の take と works/blk-pr/scripts/accept.py:34 の take の書き直し。返り {ok, reason}。
    順: 投稿していない（check_no_post）→ 読むだけの役が作業ツリーを変えていない（入口の写し judge/judge-tree.json と比べる）→
    素材の形 → 外す hunk（prcheck.check_excluded）。通れば外す hunk を中身の印つきで judge/pr-excluded.json に、申し送りの
    下書きを judge/pr-downgrades.json に、素材を judge/material-pr-check.json に書く。拒めば何も書かない。
    写しの schema は実行基盤が役の節の型で照らすので、ここでは素材の status だけを見る"""
    jdir, repo = pathlib.Path(jdir), pathlib.Path(repo)
    if not isinstance(reply, dict):
        return {"ok": False, "reason": "返答が JSON のオブジェクトでない"}
    posted = check_no_post(reply)
    if posted:
        return {"ok": False, "reason": NO_POST + ", ".join(posted)}
    before = read_json(jdir / TREE_FILE)
    if not isinstance(before, dict):
        return {"ok": False, "reason": f"{jdir / TREE_FILE} が無い——役を起こす前の作業ツリーの写しと比べられない"}
    moved = _w_tree_moved(before, repo)
    if moved:
        return {"ok": False, "reason": "読むだけの役が作業ツリーを変えた: 並行 PR の任せ先は読むだけの役で、作業ツリー・HEAD・枝・"
                "git が無視するファイルを変えてはいけない（checkout・switch・stash・reset・gh pr checkout を打つな）（"
                + "・".join(moved) + "）"}
    m = reply.get("material")
    if not isinstance(m, dict) or m.get("status") not in STATUS:
        return {"ok": False, "reason": f"返答が型に合わない（直して返し直す）: material.status は {'・'.join(STATUS)} のどれか"}
    errs = prcheck.check_excluded(reply, repo)
    if errs:
        return {"ok": False, "reason": "外す hunk（excluded）が合わない: " + "; ".join(errs)}
    excluded = prcheck._anchored(reply[prcheck.EXCLUDED_FIELD], repo)
    bare = {k: v for k, v in reply.items() if k != prcheck.EXCLUDED_FIELD}
    prcheck._write(jdir / prcheck.EXCLUDED, {"node": prcheck.NODE, "head": before.get("head", ""), "excluded": excluded})
    write_json(jdir / PR_DOWNGRADES_FILE, prcheck_drafts(bare))
    _pr_material(jdir, bare)
    return {"ok": True, "reason": ""}


def pr_accept(jdir, raw, repo) -> dict:
    """節 pr-check-accept の中身。元 works/blk-pr/scripts/accept.py:38 の main（rolekit.main_accept に take を渡す）と
    works/blk-pr/scripts/collect.py:20 の gave_up（3 回とも拒まれたら止める。by は stopby.PR）の書き直し。返り {ok, done, reason}。
    拒否は judge/rejects-pr-check.json に積み（rolekit.with_done）、諦めた時は止めの控えを置く（write_stop）"""
    jdir = pathlib.Path(jdir)
    reply, why = rolekit.parse_reply(raw)
    out = prcheck_take(jdir, reply, repo) if reply is not None else {"ok": False, "reason": why}
    out = rolekit.with_done(jdir, prcheck.ROLE, {"ok": out["ok"], "reason": out["reason"]})
    if out["done"] and not out["ok"]:
        write_stop(jdir, stopby.PR, rolekit.given_up_reason(jdir, prcheck.ROLE) or out["reason"])
    return out


# ---------------------------------------------------------------- 世界の解
def world_dir(jdir) -> pathlib.Path:
    """元 works/blk-world/lib/worldblk.py:75 の place の書き直し。worldblk の作業の置き場（judge/world/）"""
    return pathlib.Path(jdir) / worldblk.OUT_DIR


def _world_due(jdir) -> dict:
    """元 works/darkfactory/lib/line_edge.py:1026 の _world_due の書き直し。{world_go, world_purpose_file, reason}: 凍った目的の文
    （judge/purpose.json）が読めれば、目的の文と目的の役が分けた依頼の解き方（worldmark.means_of。judge/purpose-means.json）を
    段の入力の形 {purpose_text, means} にして judge/world-purpose.json に書く。読めなければ回さない（理由を返す）。
    機能の切り替え（features_cut の world）は入口が見るので、ここでは見ない"""
    jdir = pathlib.Path(jdir)
    try:
        doc = read_json(jdir / "purpose.json")
    except ValueError as e:
        doc, why = None, str(e)
    else:
        why = f"{jdir / 'purpose.json'} が無い" if doc is None else ""
    if not isinstance(doc, dict) or not isinstance(doc.get("purpose_text"), str):
        return {"world_go": False, "world_purpose_file": "", "reason": f"目的の文が読めない: {why or '形が違う'}"}
    p = write_json(jdir / WORLD_PURPOSE_FILE, {"purpose_text": doc["purpose_text"], "means": worldmark.means_of(jdir)})
    return {"world_go": True, "world_purpose_file": str(p), "reason": ""}


def world_intake(jdir, repo) -> dict:
    """節 world-intake の中身（元 works/blk-world/scripts/intake.py と classes_prep.py を 1 つにした物。中身は worldblk.intake・
    classes_prep）。返り {due, prompt, reason}: due は言い直す役を起こすか、prompt はその役の指示書の本文（役は道具を持たない）。
    依頼の行は judge/request.json、web は始めの記録の features_cut に world が在れば off（入口が段ごと切るので、実際は on）。
    止めの控えが在れば何もしない"""
    jdir = pathlib.Path(jdir)
    stop = read_stop(jdir)
    if stop:
        return {"due": False, "prompt": "", "reason": f"止めの控えが在る（{stop['stop_reason']}）"}
    start = start_view(read_json(jdir / START_FILE, {}))
    web = "off" if WORLD_FEATURE in start["features_cut"] else "on"
    due = _world_due(jdir)
    purpose_file = due["world_purpose_file"] or str(jdir / WORLD_PURPOSE_FILE)   # 無いファイルを渡し、intake が理由を残す
    got = worldblk.intake(world_dir(jdir), request=str(jdir / REQUEST_FILE), purpose_file=purpose_file, web=web, cwd=repo)
    if not got["due"]:
        return {"due": False, "prompt": "", "reason": got["reason"] or due["reason"] or "依頼の行が無い"}
    return {"due": True, "prompt": worldblk.classes_prep(world_dir(jdir))["prompt"], "reason": ""}


def world_accept(jdir, role: str, raw, *, get=None) -> dict:
    """節 world-classes-accept・world-judge-accept の中身（元 works/blk-world/scripts/classes_accept.py・judge_accept.py。中身は
    worldblk.classes_accept・judge_accept）。返り {ok, done, reason}。返答が JSON でない・置き場の控えが無い時も拒否として返す。
    拒否は worldblk の控え（judge/world/rejects-<classes|judge>.json。出口の理由が読む）と judge/rejects-<役>.json（rolekit.with_done）
    の両方に積む。get は web の役の抜き書きを取り直す口（既定は worldblk.fetch。試験が差し替える）。諦めても run は止めない"""
    jdir = pathlib.Path(jdir)
    out, inner = world_dir(jdir), WORLD_ROLES[role]
    reply, why = rolekit.parse_reply(raw)
    try:
        if reply is None:
            got = worldblk._close_round(out, inner, [why])
        elif role == "world-classes":
            got = worldblk.classes_accept(out, reply)
        else:
            got = worldblk.judge_accept(out, reply, get or worldblk.fetch)
    except (ValueError, OSError) as e:
        got = worldblk._close_round(out, inner, [f"置き場の控えが読めない: {e}"])
    return rolekit.with_done(jdir, role, {"ok": got["ok"], "reason": got["reason"]})


def world_plan(jdir) -> dict:
    """節 world-plan の中身（元 works/blk-world/scripts/plan.py と judge_prep.py を 1 つにした物。中身は worldblk.plan・judge_prep）。
    返り {due, prompt, reason}: due は web の役を起こすか、prompt はその役の指示書の本文（役は Read を持たない）"""
    jdir = pathlib.Path(jdir)
    stop = read_stop(jdir)
    if stop:
        return {"due": False, "prompt": "", "reason": f"止めの控えが在る（{stop['stop_reason']}）"}
    out = world_dir(jdir)
    try:
        got = worldblk.plan(out)
    except ValueError as e:
        return {"due": False, "prompt": "", "reason": str(e)}
    if not got["judge_due"]:
        why = worldblk._why_failed(out, worldblk.CLASSES_ROLE) if not (out / worldblk.CLASSES).is_file() else "取る類が無い"
        return {"due": False, "prompt": "", "reason": why}
    return {"due": True, "prompt": worldblk.judge_prep(out)["prompt"], "reason": ""}


def world_finish(jdir) -> dict:
    """節 world-finish の中身（元 works/blk-world/scripts/collect.py の worldblk.finish と、線の境 h-world が出口を盤面の根に写した
    worldmark.write の書き直し）。行を judge/world.jsonl に、段の控えを judge/world-state.json に書く。返り {ok, status, reason}。
    落ちた段・網に出られなかった段も run を止めない（持ち主の決め world。status: failed と reason）"""
    jdir = pathlib.Path(jdir)
    stop = read_stop(jdir)
    try:
        got = worldblk.finish(world_dir(jdir))
    except (ValueError, OSError, KeyError, TypeError) as e:
        got = {"status": "failed", "reason": f"出口を組めない: {type(e).__name__}: {e}", "world_file": "", "classes": 0, "dropped": 0}
    status, reason = got["status"], got["reason"]
    if stop and status == "ok":
        status, reason = "failed", f"止めの控えが在る（{stop['stop_reason']}）" + (f"／{reason}" if reason else "")
    dest = jdir / worldmark.WORLD_FILE
    src = pathlib.Path(got["world_file"]) if got.get("world_file") else None
    rows = src.read_text(encoding="utf-8") if status == "ok" and src and src.is_file() else ""
    dest.write_text(rows, encoding="utf-8")
    worldmark.write(jdir, status=status, reason=reason, world_file=str(dest), classes=got.get("classes", 0),
                    dropped=got.get("dropped", 0))
    return {"ok": True, "status": status, "reason": reason}
# ================================================================ 並行 PR と世界の解（W）の終わり


# ================================================================ 入口と返り（F）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
START_FILE = "start.json"          # 始めの記録を既定の値で読んだ物（start_view）
INTAKE_FILE = "intake.json"        # 入口の返り {go, mode, spec, world, verify, reason}
REQUEST_FILE = "request.json"      # 依頼の行（check_request が通した物。仕様の段が受け入れ条件の行を積む）
TREE_FILE = "judge-tree.json"      # 入口の時の作業ツリーの姿（accept.tree_state）。読むだけの役の受け付けが比べる
STOP_FILE = "stop.json"            # 止めの控え {stop_reason, reason}。最初に止めた節の物だけ残す
DEFAULT_FEATURES_CUT = ["judge_verify"]   # 今の works の入口の既定（判定の裏取りは既定で切）


def start_view(doc) -> dict:
    """始めの記録（今の works の blk-entry/schemas/start.schema.json の形）を、このブロックが読む欄だけ既定の値で読んだ物。
    欄が無い時の既定は docs/design.md の「judge の返り」の入力 start の決め（request_file は input.request_file・""、policy_md は ""、
    features_cut は ["judge_verify"]、spec は input.spec・false、answers は []、gates は ""）。base_rev は修正の起点（start の時の HEAD）、
    diff_base は差分の根（input.base.rev。P1 の役が差分を取る起点。無ければ base_rev）"""
    doc = doc if isinstance(doc, dict) else {}
    shape = doc.get("input") if isinstance(doc.get("input"), dict) else {}
    base = shape.get("base") if isinstance(shape.get("base"), dict) else {}
    cut = doc.get("features_cut")
    return {
        "request_file": doc.get("request_file") or shape.get("request_file") or "",
        "policy_md": doc.get("policy_md") or "",
        "features_cut": list(cut) if isinstance(cut, list) else list(DEFAULT_FEATURES_CUT),
        "spec": shape.get("spec") is True,
        "answers": doc.get("answers") if isinstance(doc.get("answers"), list) else [],
        "gates": doc.get("gates") if isinstance(doc.get("gates"), str) else "",
        "base_rev": doc.get("base_rev") or "",
        "diff_base": base.get("rev") or doc.get("base_rev") or "",
        "input": shape,
        "pr": shape.get("pr") if isinstance(shape.get("pr"), dict) else None,
    }


def write_stop(jdir, stop_reason: str, reason: str) -> None:
    """止めの控えを置く。もう在れば書かない（最初に止めた節の理由が run の止めの理由）"""
    p = pathlib.Path(jdir) / STOP_FILE
    if not p.exists():
        write_json(p, {"stop_reason": stop_reason, "reason": reason})


def read_stop(jdir):
    """止めの控え {stop_reason, reason}。無い・読めない・形が違えば None"""
    try:
        doc = read_json(pathlib.Path(jdir) / STOP_FILE)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("stop_reason"), str) else None


import accept  # noqa: E402
import carry  # noqa: E402
import prcheck  # noqa: E402
import worldmark  # noqa: E402

VERIFY_FEATURE = "judge_verify"    # 判定の裏取りの機能の語（元 entry.py:425）


def _intake_out(go, mode="judge", *, spec=False, world=False, verify=False, reason="") -> dict:
    return {"go": go, "mode": mode, "spec": spec, "world": world, "verify": verify, "reason": reason}


def request_rows(view: dict, repo) -> list:
    """始めの記録が名指す依頼のファイルの findings の行（lib/carry.parts で容器を解く）。依頼のファイルが無い run は、始めの記録の
    依頼の数が 0 の時だけ空の行。解けなければ ValueError（1 行）"""
    name = view["request_file"]
    if not name:
        if view["input"].get("requests"):
            raise ValueError(f"始めの記録は依頼の行が {view['input']['requests']} 件と言うのに依頼のファイルを名指していない")
        return []
    path = pathlib.Path(name)
    path = path if path.is_absolute() else pathlib.Path(repo) / path
    doc = read_json(path)
    if doc is None:
        raise ValueError(f"依頼のファイル {path} が無い")
    return carry.parts(doc)["findings"]


def intake(start, start_error: str, jdir, rdir, repo, objection: str) -> dict:
    """入口の節（intake）。再審の道（objection が空でない）は判定の置き場に触らずに mode: rejudge を返す。判定の道は、始めの記録を
    既定の値で読んで置き（START_FILE）、依頼の行を型に通して置き（REQUEST_FILE）、作業ツリーの姿を置く（TREE_FILE）。
    通らなければ止めの控えに依頼の語を書き go: false（AI を 1 つも起こさない）。機能の切り替えは始めの記録の features_cut、
    仕様の段は始めの記録の input.spec。返りは INTAKE_FILE にも書く（後ろの節は with: で結ばずにここを読む）"""
    jdir, rdir = pathlib.Path(jdir), pathlib.Path(rdir)
    if objection.strip():
        out = _intake_out(True, "rejudge")
        write_json(rdir / INTAKE_FILE, out)
        return out
    jdir.mkdir(parents=True, exist_ok=True)
    try:
        if start_error:
            raise ValueError(start_error)
        view = start_view(start)
        write_json(jdir / START_FILE, view)
        rows = request_rows(view, repo)
        checked = check_request(rows)
        if checked.get("ok") is not True:
            raise ValueError(checked.get("reason") or "依頼の行が型に通らない")
        write_json(jdir / REQUEST_FILE, rows)
        write_json(jdir / TREE_FILE, accept.tree_state(pathlib.Path(repo)))
    except (ValueError, OSError, Reject) as e:
        reason = " ".join(str(e).split())
        write_stop(jdir, REQUEST_STOP, reason)
        out = _intake_out(False, reason=reason)
    else:
        cut = set(view["features_cut"])
        out = _intake_out(True, spec=view["spec"], world=WORLD_FEATURE not in cut, verify=VERIFY_FEATURE not in cut)
    write_json(jdir / INTAKE_FILE, out)
    return out


EMPTY_JUDGMENT = {"units": [], "questions": [], "framing": "", "one_shot": "", "materials_missing": [], "carried_r1": [],
                  "one_shot_closes": [], "precedents": []}
EMPTY_PURPOSE = {"purpose_text": "", "source": "", "known_weaknesses": [], "source_files": []}
PURPOSE_FILE = "purpose.json"
PREMISES_FILE = "premises.json"
VERIFY_FILE = "judge-verify.json"
PR_EXCLUDED_FILE = "pr-excluded.json"
MATERIALS_FILE = "materials.json"
SPEC_FILE = "spec.json"
WORLD_FILE = "world.jsonl"
OUT_OF_PURPOSE_FILE = "out-of-purpose.json"
PUBLIC_FILES = (PREMISES_FILE, VERIFY_FILE, PR_EXCLUDED_FILE, MATERIALS_FILE)   # 判定の指し札の隣に必ず置く（ほかのブロックが名で開く）


def _empty_public(name: str, reason: str):
    """公開の隣のファイルの空の形（その段が走らなかった・止めの道）"""
    return {PREMISES_FILE: lambda: {"constraints": []},
            VERIFY_FILE: lambda: verify_not_run(reason),
            PR_EXCLUDED_FILE: lambda: {"node": prcheck.NODE, "excluded": []},
            MATERIALS_FILE: lambda: {}}[name]()


def _fill(path: pathlib.Path, empty) -> pathlib.Path:
    """path が無ければ空の形で置く（在る物は書き換えない）"""
    if not path.is_file():
        write_json(path, empty)
    return path


def _first_missing_stage(jdir: pathlib.Path):
    """止めの控えが無いのに受けた判定が無い時、どの段で落ちたか（段が落ちた run は控えを書く前に終わる）"""
    if not (jdir / INTAKE_FILE).is_file():
        return REQUEST_STOP, "入口の節が走っていない（始めの記録を読めないまま返る）"
    if not (jdir / PREMISES_FILE).is_file():
        return stopby.PREMISES, "前提の実測を受け付けた控えが無い（前提の段が落ちた）"
    if not (jdir / PURPOSE_FILE).is_file():
        return stopby.PURPOSE, "目的の文を受け付けた控えが無い（目的の段が落ちた）"
    return JUDGE_STOP, "受け付けを通った判定が無い（判定の段が落ちた）"


def _accepted_judgment(path: pathlib.Path):
    """受けた判定の dict。無ければ None、形が崩れていれば ValueError"""
    doc = read_json(path)
    if doc is None:
        return None
    if not (isinstance(doc, dict) and isinstance(doc.get("units"), list)
            and all(isinstance(u, dict) and isinstance(u.get("key"), str) and "label" in u for u in doc["units"])):
        raise ValueError(f"{path} の形が崩れている（units[].key・label が要る）")
    return doc


def verdict(jdir, rdir, repo, objection: str, ptr) -> dict:
    """返す節（verdict）。docs/design.md の「judge の返り」の欄をちょうど返す。止めの道でも判定と目的の指し札の先と公開の隣のファイルを
    空の形で置いてから返す。ptr(rel) は置き場からの相対パスを指し札にする口（呼び手が渡す）"""
    jdir, rdir = pathlib.Path(jdir), pathlib.Path(rdir)
    rejudging = bool(objection.strip())
    here = rdir if rejudging else jdir
    here.mkdir(parents=True, exist_ok=True)
    base = here.name

    stop = read_stop(here)
    judgment = None
    try:
        judgment = _accepted_judgment(here / JUDGMENT_FILE)
    except ValueError as e:
        stop = stop or {"stop_reason": stopby.REJUDGE if rejudging else JUDGE_STOP, "reason": str(e)}
    if judgment is None and stop is None:
        stop = dict(zip(("stop_reason", "reason"), (stopby.REJUDGE, "受け付けを通った再審が無い") if rejudging
                        else _first_missing_stage(jdir)))
    _fill(here / JUDGMENT_FILE, EMPTY_JUDGMENT)

    reason = stop["reason"] if stop else ""
    for name in PUBLIC_FILES:
        first = jdir / name
        if rejudging and first.is_file() and not (rdir / name).is_file():
            write_json(rdir / name, read_json(first))
        _fill(here / name, _empty_public(name, reason or "判定の裏取りを回さなかった"))

    purpose = jdir / PURPOSE_FILE
    if not purpose.is_file():
        purpose = _fill(here / PURPOSE_FILE, EMPTY_PURPOSE)
    world = jdir / WORLD_FILE if (jdir / WORLD_FILE).is_file() and worldmark.stage_rows(jdir) is not None else None
    spec = jdir / SPEC_FILE if (jdir / SPEC_FILE).is_file() else None
    outside = jdir / OUT_OF_PURPOSE_FILE if (jdir / OUT_OF_PURPOSE_FILE).is_file() else None

    units = structure_units(judgment, repo) if stop is None else []
    rel = lambda p: None if p is None else ptr(f"{p.parent.name}/{p.name}")   # noqa: E731
    return {
        "ready": stop is None and bool(units),
        "stop_reason": stop["stop_reason"] if stop else "",
        "units": units,
        "judgment": ptr(f"{base}/{JUDGMENT_FILE}"),
        "purpose": rel(purpose),
        "world": rel(world),
        "spec": rel(spec),
        "out_of_purpose": rel(outside),
        "rejudge_verdict": rejudge_verdict(rdir) if rejudging and stop is None else None,
    }


def verdict_fallback(jdir, rdir, objection: str, ptr) -> dict:
    """verdict の中で思わぬ誤りが起きた時の返り（返す節は落ちない。誤りの文は呼び手が標準エラーに書く）。判定と目的の指し札の先だけは
    空の形で置く"""
    here = pathlib.Path(rdir if objection.strip() else jdir)
    try:
        here.mkdir(parents=True, exist_ok=True)
        _fill(here / JUDGMENT_FILE, EMPTY_JUDGMENT)
        _fill(here / PURPOSE_FILE, EMPTY_PURPOSE)
    except OSError:
        pass
    return {"ready": False, "stop_reason": stopby.REJUDGE if objection.strip() else JUDGE_STOP, "units": [],
            "judgment": ptr(f"{here.name}/{JUDGMENT_FILE}"), "purpose": ptr(f"{here.name}/{PURPOSE_FILE}"),
            "world": None, "spec": None, "out_of_purpose": None, "rejudge_verdict": None}
# ================================================================ 入口と返り（F）の終わり
