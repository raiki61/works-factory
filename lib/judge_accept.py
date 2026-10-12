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

import copy  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

import accept as core_accept  # noqa: E402  （lib/accept。このモジュールに受け付けの関数 accept が在るので別名で読む）
import baseline_red  # noqa: E402
import carry  # noqa: E402
import checkscope  # noqa: E402
import cite  # noqa: E402
import diverted  # noqa: E402
import engine.util as _util  # noqa: E402
import forge  # noqa: E402
import gatemarks  # noqa: E402
import ghreads  # noqa: E402
import jsonfile  # noqa: E402
import judgeverify as jv  # noqa: E402
import marks  # noqa: E402
import outpurpose  # noqa: E402
import prcheck  # noqa: E402
import premises as _premises  # noqa: E402
import policy  # noqa: E402
import promptsection  # noqa: E402
import purpose as _purpose  # noqa: E402
import querytest  # noqa: E402
import report  # noqa: E402  （約束の隣のファイルの名 REJUDGE_DIFF・REJUDGE_EXIT の住処）
import rolekit  # noqa: E402
import specblk  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402
import tree_run  # noqa: E402
import worldblk  # noqa: E402
import worldmark  # noqa: E402
from engine import declared  # noqa: E402
from engine.render import Renderer  # noqa: E402
from engine.schema import validate_schema  # noqa: E402
from engine.util import (READ_CAP, Reject, _grep as grep, git, hook_evidence, pick, read_capped, repo_root,  # noqa: E402
                         run_count, sum_counts)

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
    marks.write(p, doc)
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
              "素材の欄を借りるな——CI の欄を借りると、CI を再実行する段が毎周上書きする。周を止めず、最終報告の冒頭に載る"),
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
ASKING = gatemarks.ASKING
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


def open_units(judgment) -> list:
    """元 works/blk-judge/lib/judgeverify.py:168。判定の開いた単位（直す義務の残る物）"""
    units = judgment.get("units") if isinstance(judgment, dict) else None
    return [u for u in units or [] if isinstance(u, dict) and isinstance(u.get("key"), str) and is_open(u)]


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
JUDGE_STOP = stopby.declare("judge", "受け付けを通った判定が無いままループを抜けた")   # 元 blk-judge/lib/judgetake.py:43
VERIFY_STOP = stopby.declare("judge-verify", "判定の裏取りの束ね役か下請けが作業ツリーを変えた")   # 元 blk-judge/lib/judgeverify.py:47
SPEC_STOP = stopby.declare("spec", "仕様のループが諦めた・固まらなかった")   # 元 blk-spec/lib/specblk.py:69
MATERIAL_STOP = stopby.declare("material", "素材集めの役の返答を 3 回とも受けられなかった")   # 元 blk-material の collect が盤面を止めた語
REQUEST_STOP = stopby.declare("request", "依頼の型が通らない・始めの記録が読めない")


# ================================================================ 依頼と判定
# 元: works/.shared/core/accept.py の check_request・_head_at_rev・_judge_tree_unchanged・check_judge と言い換えの表、
# 写しの rules（works/.shared/core/graphloops/rules/review-loop.py）の依頼の型と judge_output とその助け、
# works/blk-judge/lib/judgetake.py の受け付けの流れ、works/blk-judge/lib/judgeverify.py の支度とまとめ、
# works/darkfactory/lib/line_edge.py の単位の目録、works/.shared/core/outpurpose.py の material_rows、
# works/.shared/core/gatemarks.py の依頼の答えの結びの照らし。盤面の値は引数か置き場 jdir のファイルで受ける。


DIAGNOSE_NODE = "p2.diagnose"                # 判定役の節の写しの graph の名（querytest・outpurpose・gatemarks の足し欄の表の鍵）
DIAGNOSE_ROLE = "diagnose"                   # 拒否の控え rejects-<役>.json の名（rolekit.with_done）
JUDGMENT_FILE = "judgment.json"              # 元 accept.py:57 の JUDGMENT_FILE（受けた判定。judge_output が整えた返答に例と目的の外の行を戻した物）
MATERIALS_FILE = gatemarks.MATERIALS_FILE
# 置き場のファイルの名は書くモジュールの物を引く
PURPOSE_FILE = _purpose.PURPOSE_FILE
PREMISES_FILE = _premises.PREMISES_FILE
VERIFY_FILE = jv.VERIFY_FILE
PR_EXCLUDED_FILE = prcheck.EXCLUDED
SPEC_FILE = specblk.SPEC_FILE
WORLD_FILE = worldmark.WORLD_FILE
MEANS_FILE = marks.KINDS[worldmark.MEANS].file
MATERIAL_GLOB = "material-*.json"            # 素材の役が書く {role, reply, materials}
VERIFY_ANSWERS_DIR = f"{jv.BRIEF_DIR}/answers"   # 裏取りの下請けの答えの置き場（元 judgeverify.answers_dir の run ごとの置き場の代わり）
VERIFY_TREE_FILE = f"{jv.BRIEF_DIR}/{jv.TREE_FILE}"   # 束ね役を起こす前の作業ツリーの姿
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


# ---------------------------------------------------------------- 依頼の型


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


def _judge_tree_unchanged(repo, jdir, rev, keys=core_accept.TREE_KEYS):
    """元 works/.shared/core/accept.py:481。判定役が作業ツリーを変えていないか（Ruling R3・R14）。置き場に diagnose-tree.json（判定役の
    支度が役を起こす前に置いた写し。tree_state の形）が在れば、今の作業ツリーがその写しと同じかを tree_moved で見る（HEAD・枝の移動と
    git が無視するファイルの増減・書き換えも見る）。無ければ作業ツリーが綺麗で、HEAD が数える版 rev のままであることを求める。
    違えば Reject。元の盤面の judge-snapshot.json は支度が置く diagnose-tree.json（DIAGNOSE_TREE_FILE）に読み替えた。keys は写しと
    比べる欄（_moved_since）"""
    if _tree_snapshot(pathlib.Path(jdir) / DIAGNOSE_TREE_FILE) is None:
        now = core_accept.snapshot_tree(repo)   # 共通の姿（Claude Code の控えのフォルダ CLI_OWNED を数えない）
        dirty = now["porcelain"].splitlines() + [f"!! {n}" for n in now["ignored"]]
        if dirty:
            raise Reject("作業ツリーに変更が在る——判定役は読むだけの役で、作業ツリーを変えてはいけない"
                         f"（git status --porcelain --ignored: {dirty[:5]}{' ほか' if len(dirty) > 5 else ''}）")
        _head_at_rev(repo, rev, "判定役")
        return
    moved = _moved_since(pathlib.Path(jdir) / DIAGNOSE_TREE_FILE, repo, keys=keys)
    if moved:
        raise Reject("判定役を起こした後から作業ツリーが変わった——判定役は読むだけの役で、作業ツリー・HEAD・枝・git が"
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
                        "今 awaiting_human の素材だけ。素材を書くノードは、人に諮っている最中の欄を awaiting_human のまま書け（見た結果は reason に）。"
                        "人が実地で確かめるまで決まらない問いは kind=field で立てろ（素材の欄を借りない）")
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


def _judged(reply, jdir, base_rev, repo, *, prev_deletions=None, prev_questions=(), defer_ledger=None,
            keys=core_accept.TREE_KEYS) -> tuple:
    """元 accept.check_judge の芯（書く前まで）: 作業ツリーと HEAD（keys は写しと比べる欄）→ class_query の例 → 先例の出どころ →
    judge_output → awaiting の出どころ（元 check_record の _awaiting_origins）。返り (正規化した返答, 例, 注記)。拒否は Reject"""
    repo_p = pathlib.Path(repo)
    with core_accept.in_repo(repo_p):
        rev = core_accept.resolve_rev(repo_p, base_rev)
        _judge_tree_unchanged(repo_p, jdir, rev, keys)
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


# 元 works/blk-material/lib/material.py:65-73 の ROLES の P1 の 9 本（写しの graph の p1.* の役の節）
P1_NODES = ("p1.local_review", "p1.consistency_bypass", "p1.hygiene", "p1.external_standards", "p1.procedure_trace",
            "p1.gate_efficacy", "p1.test_double_fidelity", "p1.main_path_observation", "p1.provenance")


def material_rows(jdir) -> list:
    """元 works/.shared/core/outpurpose.py:87。材料の行: P1 の目の素材の役が受けた返答（置き場の material-<役>.json の reply。元は
    盤面の p1.* の節の最新の出力）の中の where・text を持つ行の全部と、依頼のバッチ（request_batches）の行。行は {where, text,
    任意の mechanism・measured・false_positive_if, from（出どころの節と目の名、依頼はバッチの出どころ）}。
    出どころの節の名は元の写しの graph の名（p1.<役の名の - を _ に>）"""
    out = []
    replies = {}   # MATERIAL_GLOB は素材の役の返答の外の控え（material-view.json など。role が無い）にも当たる
    for p in pathlib.Path(jdir).glob(MATERIAL_GLOB):
        d = read_json(p, None)
        if isinstance(d, dict) and isinstance(d.get("role"), str):
            replies[f"p1.{d['role'].replace('-', '_')}"] = d.get("reply")
    for nid in sorted(replies):
        if nid in P1_NODES:
            outpurpose._walk(replies[nid], nid, out)
    for batch in request_batches(jdir, _start_of(jdir)):
        outpurpose._walk(batch["findings"], f"依頼（{batch['origin']}）", out)
    return out


def request_answers(jdir) -> list:
    """元 works/.shared/core/gatemarks.py:687。依頼の answers（置き場の start.json の欄。元は盤面の start の控え。dict でない行は読まない）"""
    rows = (read_json(pathlib.Path(jdir) / START_FILE, {}) or {}).get("answers")
    return [a for a in rows if isinstance(a, dict)] if isinstance(rows, list) else []


def unmeasured(materials) -> dict:
    """元 works/.shared/core/gatemarks.py:693。今の周に測れていない素材 {名: status}: 素材のうち、検証器の表 STATUS で阻害になる
    status（gatemarks.UNMEASURED。表との一致は試験が縛る）の物"""
    return gatemarks.unmeasured_of(materials)


def origin_of(q, materials) -> str:
    """元 works/.shared/core/gatemarks.py:704。答えを結ぶ時の問いの出どころ（gatemarks.origin。測れていない素材は materials から）"""
    return gatemarks.origin(q, unmeasured(materials))


def answer_binds(a, questions, materials) -> list:
    """元 works/.shared/core/gatemarks.py:716 を受け付けの呼び方（結びの行は空。字の一致だけ）で（gatemarks.binds）"""
    return gatemarks.binds(a, questions, missing=unmeasured(materials))


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


def take(jdir, reply, repo, base_rev: str = "", *, prev_deletions=None, prev_questions=(), defer_ledger=None,
         keys=core_accept.TREE_KEYS) -> dict:
    """元 works/blk-judge/lib/judgetake.py:74 の take と、受け付けの芯（元 entry.take の p2.diagnose の done と accept.check_judge）。
    順（計画の節 9）: 作業ツリーと HEAD → class_query の例（querytest）→ 先例の出どころが世界の解の行に在る（worldmark）→
    judge_output → 目的の外の所見の行を材料の行に当てる（outpurpose）→ 依頼の答えと作り直しの行の結び（answer_ties）。
    返答の型は判定役の節の output_format だけが持つ。例・目的の外の行・結びは judge_output の前に外す。通れば例を query-examples.json に、
    目的の外の行を当たった材料の行ごと out-of-purpose.json（周は 1）に、結びを answer-ties.json に置き、judge_output が整えた返答に
    例と目的の外の行を戻して judgment.json に書く（元 judgetake.finish）。
    keys は作業ツリーの写しと比べる欄（_judge_tree_unchanged）。返り {ok, reason, open_units, judgment_file}。拒否の時は judgment.json
    を書かない"""
    def run():
        if not isinstance(reply, dict):
            raise Reject(f"判定の返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        body, outside = outpurpose.split(reply)
        body, tie_rows = gatemarks.split_answer_ties(body)
        out, examples, note = _judged(body, jdir, base_rev, repo, prev_deletions=prev_deletions,
                                      prev_questions=prev_questions, defer_ledger=defer_ledger, keys=keys)
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


def accept_round(board, name: str, raw, take, *, reject=None, on_give_up=None) -> dict:
    """受け付けの輪の 1 回（元 rolekit.main_accept）。役の返答の字 raw を読み（rolekit.parse_reply）、take(reply) に通す。読めない
    返答と take の中の例外は reject(理由) で拒否にする（既定は {ok: False, reason}。受け付けは落ちない）。拒否は
    board/rejects-<name>.json に積み（rolekit.with_done）、3 回目で done。諦めた時は on_give_up() を呼ぶ。
    take の返りの give_up が真なら 1 回目でも done（出し直しても直らない拒み）。
    返り take の返りに done を足した物。拒否の控えが扱えなければ done 真の拒否"""
    reject = reject or (lambda why: {"ok": False, "reason": why})
    reply, why = rolekit.parse_reply(raw)
    try:
        got = take(reply) if reply is not None else reject(why)
    except Exception as e:  # noqa: BLE001
        got = reject(f"受け付けの中で例外（{type(e).__name__}: {e}）")
    try:
        out = {**got, **rolekit.with_done(board, name, {"ok": got.get("ok") is True, "reason": str(got.get("reason") or "")},
                                          give_up=got.get("give_up") is True)}
        if out["done"] and not out["ok"] and on_give_up:
            on_give_up()
    except Exception as e:  # noqa: BLE001
        out = {**got, "ok": False, "done": True, "reason": f"拒否の控えが扱えない（{type(e).__name__}: {e}）"}
    return out


def accept(jdir, raw: str, repo, base_rev: str = "", *, keys=core_accept.TREE_KEYS) -> dict:
    """元 works/blk-judge/lib/judgetake.py:106。節 diagnose-accept の中身: 判定役の返答を take に通す（accept_round。keys は take）。
    返り {ok, done, reason, open_units, judgment_file}。諦めたら止めの控えを置く（_give_up）"""
    return accept_round(jdir, DIAGNOSE_ROLE, raw, lambda reply: take(jdir, reply, repo, base_rev, keys=keys),
                        on_give_up=lambda: _give_up(jdir))


def _give_up(jdir) -> dict:
    """元 works/blk-judge/lib/judgetake.py:122。受け付けを通った判定が無いまま輪を抜けた: 最後の拒否の文で止めの控えを置き
    （JUDGE_STOP。もう止めの控えが在れば write_stop は書かない）、ok false の出口"""
    reason = (rolekit.given_up_reason(jdir, DIAGNOSE_ROLE)
              or f"受け付けを通った判定が無いまま判定のループを抜けた（{DIAGNOSE_ROLE} の受け付けの拒否の控えが諦めに届いていない）")
    write_stop(jdir, JUDGE_STOP, reason)
    return {"ok": False, "open_units": [], "need_fix": False, "judgment_file": "", "one_shot": ""}


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


STRUCTURE_DROPPED_FILE = "structure-units-dropped.json"   # 構造の目の入力に写せなかったパスと paths の空の単位の記録（元 trace の STRUCTURE_UNITS_OP）


def structure_units(judgment, repo, record=None) -> list:
    """元 works/darkfactory/lib/line_edge.py:361。判定の開いた単位（is_open）を全部、構造の目の入力の形 {id, paths, summary} に写した
    並び（判定の順）。summary は単位の reason だけ。元は paths が 1 本も残らない単位を写さなかったが、計画の決めで落とさない
    （paths: [] で返す。構造の目に回すかは plan が決める）。record（ファイルのパス）が在れば、パスの取れない単位と捨てたパスを
    {units, paths} で書く（元は trace の STRUCTURE_UNITS_OP の 1 行。黙って空の実測にしない）"""
    rows, empty, dropped = [], [], []
    for u in (judgment.get("units") if isinstance(judgment, dict) else None) or []:
        if not isinstance(u, dict) or not isinstance(u.get("key"), str) or not is_open(u):
            continue
        paths, bad = _unit_file_paths(u, repo)
        dropped += bad
        if not paths:
            empty.append(u["key"])
        reason = u.get("reason") if isinstance(u.get("reason"), str) else ""
        rows.append({"id": u["key"], "paths": paths, "summary": reason})
    if record is not None:
        write_json(record, {"units": empty, "paths": list(dict.fromkeys(dropped))})
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
    units = open_units(judgment)
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
    jsonfile.write(jdir / VERIFY_TREE_FILE, core_accept.tree_state(pathlib.Path(repo)), parents=True)
    jsonfile.write(jdir / jv.PLAN_FILE, {"units": [{"n": n, "key": u["key"]} for n, u in enumerate(units, 1)], "answers": str(answers)}, parents=True)
    jsonfile.write(jdir / jv.VERIFY_FILE, jv._initial(units), parents=True)
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


def merge_on(jdir, repo, *, keys=core_accept.TREE_KEYS) -> dict:
    """元 works/blk-judge/lib/judgeverify.py:285。裏取りのまとめ。返り {ok, reason}。番号の控えが無ければ（支度が go 偽・支度が
    走らなかった）回さなかった形の申し送りを置いて ok。在れば単位ごとに答えのファイルを確かめ（型・番号・not_root の本当の根）、
    相乗りの番号を単位の key に戻して judge-verify.json に書く（単位は消さない）。束ね役か下請けが作業ツリーを変えていれば
    止めの控え（VERIFY_STOP）を置いて ok 偽（元は盤面を止めた）。keys は作業ツリーの写しと比べる欄（_moved_since）"""
    jdir = pathlib.Path(jdir)
    plan = jsonfile.read_or(jdir / jv.PLAN_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("units"), list):
        if not (jdir / jv.VERIFY_FILE).is_file():
            verify_not_run(jdir, "判定の裏取りの支度が走らなかった（番号の控えが無い）")
        return {"ok": True, "reason": ""}
    try:
        moved = _moved_since(jdir / VERIFY_TREE_FILE, repo, keys=keys)
    except Reject as e:
        moved = [str(e)]
    answers = pathlib.Path(plan.get("answers") or jdir / VERIFY_ANSWERS_DIR)
    keys = {r["n"]: r["key"] for r in plan["units"]}
    rows = [_check_unit(answers, n, key) for n, key in keys.items()]
    syn = _check_synergy(answers, keys)
    jsonfile.write(jdir / jv.VERIFY_FILE, {"units": rows, "synergy": syn}, parents=True)
    if moved:
        reason = "判定の裏取りの束ね役か下請けが作業ツリーを変えた（読むだけの役）: " + "・".join(moved)
        write_stop(jdir, VERIFY_STOP, reason)
        return {"ok": False, "reason": reason}
    return {"ok": True, "reason": ""}


# ================================================================ 材料・前提・目的・素材
# 元: works/blk-judge/lib/judgebrief.py・works/.shared/core/entryshape.py:134-200・premises.py・purpose.py・
# works/blk-material/lib/material.py・works/blk-premises/scripts/accept.py・works/blk-purpose/scripts/intake.py と、
# 写しの rules（works/.shared/core/graphloops/rules/review-loop.py）の素材の要否・受け付け・素材の埋め（版 2aa7c66）。
# 盤面（b）を読んでいた所は、置き場 jdir のファイル・始めの記録の見方（start_view）・対象の根 repo を引数で受ける形に替えた。


PREMISES_ROLE = "premises"          # 拒否の控え rejects-premises.json の名
PURPOSE_ROLE = "purpose"            # 拒否の控え rejects-purpose.json の名
PURPOSE_BRIEF_FILE = "purpose-brief.md"
DIAGNOSE_BRIEF_FILE = "diagnose-brief.md"
DIFF_FILE = "diff.patch"
CHANGED_FILE = "changed-files.txt"
MATERIAL_VIEW_FILE = "material-view.json"     # 素材の役が読む版と差分（material_route が 1 度置く）
MATERIAL_ROUTE_FILE = "material-route.json"   # 素材ごとの要否と回さない素材の埋め（material_route）
DECL_NAME = declared.DECL_NAME


# ---------------------------------------------------------------- 依頼と PR の題と本文（元 works/.shared/core/entryshape.py:134-200）
REQUEST_HEAD = promptsection.Section("## 依頼", source="fn:entryshape.request_text")
PR_TEXT_HEAD = promptsection.Section("## PR #{number} の題と本文", source="fn:entryshape.request_text")
PR_TITLE = promptsection.Section("# PR #{number}", source="fn:entryshape.write_pr_file")
PR_SUBJECT_HEAD = promptsection.Section("## 題", source="fn:entryshape.write_pr_file")
PR_BODY_HEAD = promptsection.Section("## 本文", source="fn:entryshape.write_pr_file")


def request_text(inp: dict) -> str:
    """元 works/.shared/core/entryshape.py:141。依頼の文: 依頼のファイルの文と PR の題・本文の在る物を並べる: 両方なら見出し
    「## 依頼」「## PR #N の題と本文」つき、片方だけならその文のまま、どちらも無ければ差分の審査の 1 行"""
    pr = inp.get("pr")
    pr_text = "\n\n".join(x for x in (pr["title"], pr["body"]) if x) if pr else ""
    req = inp["request_text"]
    if req and pr_text:
        return f"{REQUEST_HEAD}\n\n{req.strip()}\n\n{PR_TEXT_HEAD.format(number=pr['number'])}\n\n{pr_text}\n"
    if req or pr_text:
        return req or pr_text
    base = inp.get("base") or {"label": "HEAD"}
    return f"変更（{base.get('label', 'HEAD')}）の審査"


def pr_file_text(pr) -> str:
    """元 works/.shared/core/entryshape.py:186 の write_pr_file が書いた本文（PR の番号・題・本文）。PR の無い run は ""。
    盤面の根の PR_FILE に置いていた所を、文を返す形にした（置くのは呼び手）"""
    if not pr:
        return ""
    return (f"{PR_TITLE.format(number=pr.get('number'))}\n\n{PR_SUBJECT_HEAD}\n\n{pr.get('title') or '（空）'}\n\n"
            f"{PR_BODY_HEAD}\n\n{pr.get('body') or '（空）'}\n")


def _pr_of(start: dict):
    """始めの記録の input.pr を {number, title, body} の形で（無い・形が違えば None）"""
    pr = start.get("pr")
    return pr if isinstance(pr, dict) and "number" in pr else None


def _request_doc(repo, start: dict):
    """始めの記録の依頼のファイル（対象の根からの相対か絶対）の (文, JSON)。無い・読めなければ ("", None)"""
    rel = start.get("request_file") or ""
    if not rel:
        return "", None
    p = pathlib.Path(rel) if pathlib.Path(rel).is_absolute() else pathlib.Path(repo) / rel
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "", None
    try:
        return text, json.loads(text)
    except ValueError:
        return text, None


# ---------------------------------------------------------------- 作業ツリーの見張り（読むだけの役の受け付け）
# 段ごとの写し（元は段ごとのブロックが役を起こす前に置いた: purpose-snapshot.json・material-snapshot.json・judge の judge-tree.json）。
# 前の段の役が残したキャッシュや仕様の段が書いたテストを、後の段の役が変えた物と数えない
PURPOSE_TREE_FILE = "purpose-tree.json"
MATERIAL_TREE_FILE = "material-tree.json"
DIAGNOSE_TREE_FILE = "diagnose-tree.json"


def snap_tree(jdir, name: str, repo) -> pathlib.Path:
    """役を起こす前の作業ツリーの姿（accept.tree_state）を置き場の name に書く（元 entry.snapshot）"""
    return write_json(pathlib.Path(jdir) / name, core_accept.tree_state(pathlib.Path(repo)))


def _tree_snapshot(path):
    """置き場に置いた作業ツリーの写し（accept.tree_state の形）。無ければ None、読めない・形が違えば Reject"""
    try:
        snap = read_json(path)
    except ValueError as e:
        raise Reject(str(e)) from None
    if snap is None:
        return None
    core_accept.type_errors(snap, core_accept.TREE_SCHEMA, f"作業ツリーの写し {path} ")
    return {k: snap[k] for k in core_accept.TREE_KEYS}


def _bytecode_in(snap: dict) -> bool:
    return any(core_accept._is_bytecode(core_accept._porcelain_path(ln)) for ln in snap["porcelain"].splitlines()) \
        or any(core_accept._is_bytecode(n) for n in snap["ignored"])


def _moved_since(path, repo, *, bytecode: bool = True, keys=core_accept.TREE_KEYS) -> list:
    """写し path（_tree_snapshot）から今の作業ツリーが変わった所の文（accept.tree_moved。keys の欄だけを比べる。同じなら空）。写しが
    無い・読めない・形が違えば Reject。bytecode=False でも写しがバイトコードを含む時は含めて比べる（写しは bytecode=True で取られる
    ので、外した姿と比べると変わっていなくても違って見える）"""
    snap = _tree_snapshot(path)
    if snap is None:
        raise Reject(f"作業ツリーの写し {path} が無い——役を起こす前の作業ツリーと比べられない（写しを置くノードが先に走る）")
    return core_accept.tree_moved(snap, pathlib.Path(repo), bytecode=bytecode or _bytecode_in(snap), keys=keys)


def _tree_unchanged(jdir, repo, rule: str, name: str, *, bytecode: bool = True, rev: str = "",
                    keys=core_accept.TREE_KEYS) -> None:
    """元 works/.shared/core/premises.py:44 と purpose.py:57 の _tree_unchanged。役が作業ツリーと履歴を変えていないか。
    置き場に役を起こす前の姿 name が在れば今と比べ（accept.tree_moved。HEAD・枝・git が無視するパスも見る）、
    無ければ作業ツリーが綺麗で、rev を渡せば HEAD が rev のままであることを求める。違えば Reject。
    bytecode=False（前提の実測役）はバイトコードを数えない（_moved_since）。keys は写しと比べる欄（_moved_since）"""
    if _tree_snapshot(pathlib.Path(jdir) / name) is None:
        now = core_accept.tree_state(repo, bytecode=bytecode)
        dirty = now["porcelain"].splitlines() + [f"!! {n}" for n in now["ignored"]]
        if dirty:
            raise Reject(f"作業ツリーに変更が在る——{rule}"
                         f"（git status --porcelain --ignored: {dirty[:5]}{' ほか' if len(dirty) > 5 else ''}）")
        if rev and now["head"] != rev:
            raise Reject(f"HEAD が数える版から動いた（版 {rev[:12]} / 今 {now['head'][:12]}）——{rule}。commit・reset・checkout で"
                         "履歴を動かしてはいけない")
        return
    moved = _moved_since(pathlib.Path(jdir) / name, repo, bytecode=bytecode, keys=keys)
    if moved:
        raise Reject(f"役を起こした後から作業ツリーが変わった——{rule}（HEAD・枝・git が無視するファイルも）。作った物"
                     "（出力のファイル・キャッシュ）は rm で消し、書き換えた追跡中のファイルは git restore -- <path> で戻してから"
                     f"出し直せ（出力は $TMPDIR に置く）（{'・'.join(moved)}）")


# ---------------------------------------------------------------- 前提の実測
def check_claims(reply: dict, items: list) -> list:
    """元 works/blk-premises/scripts/accept.py:24。依頼の実測（measured を持つ行）のうち、where を text にそのまま含む制約が返答に
    無い物の where の一覧（空なら通る）。測り直せずに kind 仮説へ落とした制約も、where を text に含めば通る"""
    cs = reply.get("constraints") if isinstance(reply, dict) else None
    texts = [c["text"] for c in cs if isinstance(c, dict) and isinstance(c.get("text"), str)] if isinstance(cs, list) else []
    return [c["where"] for c in _premises.claims(items) if not any(c["where"] in t for t in texts)]


def measured_needs_output(nid, out):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3010。kind=実測 の制約は、実行したコマンドと出力（measured_output）を持て。

    『実測』の札だけが検算なしで信頼値に昇格し、誤った事実がゼロベースで疑う役に所与として渡る
    （実測 2026-09-12: 『CI の定義はリポジトリに無い』が実測として凍結され、R2 の独立設計がそれを前提に書いた。
    .github/workflows/test.yml は実在する）。再現の形を持たないものは仮説へ落とさせる。
    """
    bad = [c["text"][:60] for c in out.get("constraints", []) if c.get("kind") == "実測" and not (c.get("measured_output") or "").strip()]
    if bad:
        raise Reject(f"{nid}: kind=実測 なのに measured_output（実行したコマンドと出力）が無い制約がある: {bad}"
                     "——コマンドと出力を示せないものは kind=仮説 に落とせ")


PREMISES_RULE = "実測役は作業ツリーを変えてはいけない"   # 元 premises.py:41 の RULE


def with_carried(reply: dict, jdir) -> dict:
    """前提の実測の返答の制約に、依頼が運んだ前の run の前提の検算の実測（CARRIED_FILE。carry.CONSTRAINTS の行）を足した物（同じ字の
    制約は 2 度足さない）。元 review-loop.py:3751-3755 の finalize が facts_to_add を盤面の制約に足した形を run をまたいで戻す"""
    carried = [c for c in read_json(pathlib.Path(jdir) / CARRIED_FILE, []) or [] if isinstance(c, dict)]
    have = {c.get("text") for c in reply.get("constraints") or [] if isinstance(c, dict)}
    return {**reply, "constraints": [*(reply.get("constraints") or []), *(c for c in carried if c.get("text") not in have)]}


def check_premises(reply: dict, jdir, repo, items: list) -> dict:
    """元 works/.shared/core/premises.py:125（と blk-premises/scripts/accept.py:32 の accept_premises）。実測役の返答を受け付ける:
    依頼の実測を測り直したか（check_claims）→ 作業ツリーか HEAD が変わっていれば拒む（_tree_unchanged。
    バイトコードは数えない）→ post_check（measured_needs_output）。通れば置き場の premises.json に返答を書く（依頼が運んだ前の run の
    実測を制約に足す。with_carried）。
    items は依頼の行（judge/request.json）。{ok, reason}"""
    def run():
        missing = check_claims(reply, items)
        if missing:
            raise Reject(f"依頼の実測を測り直した制約が無い: {'・'.join(missing)}。text に where をそのまま入れよ"
                         "（この作業ツリーで測り直せなければ kind: 仮説 に落とし、text に where と測れない理由を書く）")
        repo_p = pathlib.Path(repo)
        with core_accept.in_repo(repo_p):
            rev = core_accept.resolve_rev(repo_p, "")
            # 実測役は測るために Bash を持つが、作業ツリーは変えない約束（後ろの判定はこの後の作業ツリーを写し、
            # 修正の差分は版からの差分で数える——ここで残った物は修正役の差分に混じる）
            _tree_unchanged(jdir, repo_p, PREMISES_RULE, TREE_FILE, bytecode=False, rev=rev)
            measured_needs_output(_purpose.PREMISES_NODE, copy.deepcopy(reply))
        write_json(pathlib.Path(jdir) / _premises.PREMISES_FILE, with_carried(reply, jdir))
        return {"ok": True, "reason": ""}
    return core_accept.guard(run)


# ---------------------------------------------------------------- 目的
PURPOSE_RULE = "目的の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない"
PURPOSE_MISSING = ("（目的の文はこの run に無い——目的のノード p0.purpose がこのラインに無く、目的のファイルも渡されていない。"
                   "目的を推し量って補うな）")   # 元 works/blk-material/lib/material.py:176
PURPOSE_UNKNOWN = "目的不明"   # 目的の出典の語（目的の役の節の output_format の source の enum の 1 つ）


def refuse_if_frozen(jdir):
    """元 works/.shared/core/purpose.py:42。置き場に目的の文が既に在れば Reject。graph の p0.purpose は once——最初の修正の前に
    1 度だけ固め、以降変えない（事前登録。後から書き直せると、実装に合わせて目的を狭める道が開く）"""
    p = pathlib.Path(jdir) / _purpose.PURPOSE_FILE
    if p.exists():
        raise Reject(f"置き場に目的の文 {_purpose.PURPOSE_FILE} が既に在る（{p}）——目的は最初の修正の前に 1 度だけ固め、"
                     "以降は変えない（graph の p0.purpose の once）")


def check_purpose(reply: dict, jdir, repo, *, keys=core_accept.TREE_KEYS) -> dict:
    """元 works/.shared/core/purpose.py:102。目的の役の返答を受け付ける。凍結（once）→ 作業ツリー（役は読むだけ。purpose-tree.json と
    比べる）→ 足し欄 means を外す（worldmark.split_means）→ source_files（_source_files_errors）。
    写しの graph の p0.purpose は post_check を持たない。通れば置き場の purpose.json に書き、外した依頼の解き方を
    purpose-means.json に置く。keys は作業ツリーの写しと比べる欄（_tree_unchanged）。{ok, reason}"""
    def run():
        repo_p = pathlib.Path(repo)
        with core_accept.in_repo(repo_p):
            refuse_if_frozen(jdir)
            _tree_unchanged(jdir, repo_p, PURPOSE_RULE, PURPOSE_TREE_FILE, keys=keys)
            out, means = worldmark.split_means(reply)   # 写しの型の外の欄を外した写し
            bad = _purpose._source_files_errors(out["source_files"], repo_p)
            if bad:
                raise Reject(f"source_files に作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る: {bad}"
                             "——出典にしたリポジトリの中のファイルを、作業ツリーの根からの相対（サブディレクトリで回していても根から・"
                             "`./` や末尾の `/`・重ねた `/`・`.` や `..` の段・symlink 経由なし・大小文字もリポジトリのまま）で書け"
                             "（依頼のファイルなどリポジトリの外の物・git が無視するファイルは書かない）")
        write_json(pathlib.Path(jdir) / _purpose.PURPOSE_FILE, out)
        worldmark.write_means(jdir, means)
        if not means:
            write_json(pathlib.Path(jdir) / MEANS_FILE, {worldmark.MEANS: []})
        return {"ok": True, "reason": ""}
    return core_accept.guard(run)


def purpose_prep(jdir, repo, start: dict) -> dict:
    """元 works/blk-purpose/scripts/intake.py の書き直し。目的の役の材料を置く: 依頼から前の run の判断（prior_failures）を外した
    写しを purpose-request.json に（carry.without_prior。目的の文は前の run の判断を知らない別の目の入力になるので、指示書の頼みで
    なく機械で外す）、それと PR の説明・前提の実測（premises.json）を purpose-brief.md に。前の run の判定・前の失敗の行は書かない。
    役を起こす前の作業ツリーの姿を purpose-tree.json に置く。凍った目的が在れば go 偽。{go, brief_file, reason}"""
    j = pathlib.Path(jdir)
    try:
        refuse_if_frozen(j)
    except Reject as e:
        return {"go": False, "brief_file": "", "reason": str(e)}
    text, doc = _request_doc(repo, start)
    if doc is None:   # 依頼のファイルが無い・JSON でない run は、入口が型を確かめた依頼の行を写す
        doc = read_json(j / REQUEST_FILE, []) or []
    bare = carry.without_prior(doc)
    copy_ = bare if bare is not None else doc
    req_path = write_json(j / _purpose.REQUEST_COPY, copy_)
    cons = (read_json(j / _premises.PREMISES_FILE, {}) or {}).get("constraints") or []
    pr = _pr_of(start)
    parts = ["# 目的の役の材料（機械が組んだ物。前の run の判断は外してある）",
             f"## 依頼（{req_path}）\n\n```json\n{json.dumps(copy_, ensure_ascii=False, indent=1)}\n```",
             "## PR の説明\n\n" + (pr_file_text(pr) if pr else "（PR の無い run）"),
             "## 前提の実測（premises.json の constraints）\n\n"
             + (f"```json\n{json.dumps(cons, ensure_ascii=False, indent=1)}\n```" if cons else "（前提の実測は無い）")]
    p = j / PURPOSE_BRIEF_FILE
    p.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    snap_tree(j, PURPOSE_TREE_FILE, repo)
    return {"go": True, "brief_file": str(p), "reason": ""}


# ---------------------------------------------------------------- 素材の要否（元 rules の節の条件。見方 v(鍵, 既定) を受ける）
def cond_reads(*paths):
    """元 works/.shared/core/graphloops/engine/rules.py:17。条件の関数が読む欄の宣言"""
    def deco(fn):
        fn.reads = tuple(paths)
        return fn
    return deco


# 元 rules:97
ENTRY_SCHEMA = {"type": "object", "required": ["origin"], "additionalProperties": False,
                "properties": {"origin": {"type": "string", "minLength": 1}}}
ENTRY_BUILTIN = "request_entry"
# 元 rules:689
GATES_MERGE_WHY = "変異の検算は合流した版でまとめて 1 回撃つ（init --input gates=merge）"
# 元 rules:367
PROCEDURE_PATTERNS = (r"README", r"\.md$", r"\.sh$", r"^scripts/", r"^\.github/workflows/", r"Makefile", r"Dockerfile",
                      r"\.ya?ml$", r"^commands/", r"^hooks/")
_NO_DEFAULT = object()


class DueView:
    """元 graphloops の engine が条件の関数に渡した見方（CondView）の値を、1 run = 1 周の値で組んだ物（due_view が作る）。
    v(鍵, 既定) で読み、無い鍵は既定（無ければ None）。unevaluable は測れなかった条件の痕跡を notes に残す"""

    def __init__(self, values: dict):
        self.values = values
        self.notes = []

    def __call__(self, key, default=_NO_DEFAULT):
        fallback = None if default is _NO_DEFAULT else default
        if key in self.values:
            got = self.values[key]
            return fallback if got is None and default is not _NO_DEFAULT else got
        for cut in range(key.count("."), 0, -1):   # 入れ子の値（out.p0.purpose.source は out.p0.purpose の dict の source）
            parts = key.split(".")
            stem, tail = ".".join(parts[:cut]), parts[cut:]
            if stem in self.values and isinstance(self.values[stem], dict):
                cur = self.values[stem]
                for t in tail:
                    if not isinstance(cur, dict) or t not in cur:
                        return fallback
                    cur = cur[t]
                return cur
        return fallback

    def unevaluable(self, name, why):
        self.notes.append(f"{name}: {why}")


def due_view(start: dict, purpose, changed_files: list) -> DueView:
    """素材の要否の条件が読む見方（計画の「lib/ に持ってくる部品」の due_view）。1 run は 1 周（持ち主の決め carry）:
    round 1・prev.* は全部 None・loop.escalated は偽・入口の印 record.process.request_entry は始めの記録の input.diff.empty が真で
    input.requests が 1 以上の時だけ（今の works の入口と同じ。差分の空の run で印が立つ）・loop.request_fixed_at は None・
    out.p0.base.touches_* は全部真（元 works/.shared/core/board.py:550 の base_output と同じ。機械は差分の柵を決められないので
    役を起こす側に倒す）・loop.changed_files は対象差分の変更ファイル・loop.gates は始めの記録の gates・out.p0.purpose は
    purpose.json・loop.last_material.* は None"""
    inp = start.get("input") if isinstance(start.get("input"), dict) else {}
    diff = inp.get("diff") if isinstance(inp.get("diff"), dict) else {}
    reqs = inp.get("requests")
    entry = None
    if diff.get("empty") is True and isinstance(reqs, int) and not isinstance(reqs, bool) and reqs >= 1:
        entry = {"origin": f"人の依頼（{start.get('request_file') or '依頼の行'}）"}
    return DueView({
        "round": 1,
        "loop.escalated": False,
        "record.process.request_entry": entry,
        "loop.request_fixed_at": None,
        "out.p0.base.touches_gates": True,
        "out.p0.base.touches_external_seams": True,
        "out.p0.base.touches_user_path": True,
        "out.p0.base.touches_security_surface": True,
        "loop.changed_files": list(changed_files or []),
        "loop.gates": start.get("gates") or "",
        "out.p0.purpose": purpose if isinstance(purpose, dict) else None,
        "loop.prev_fix_files": None,
        "record.process.purpose_review": None,
        "record.process.fixes": [],
    })


def _entry_marked(v):
    """元 rules:167。入口の印（process.request_entry）が型どおりに在るか"""
    return not validate_schema(v("record.process.request_entry", None), ENTRY_SCHEMA)


@cond_reads("record.process.request_entry", "loop.request_fixed_at")
def request_entry(v):
    """元 rules:178。判定から入る run の周か。入口の印が型どおりに在り、前の周までの P3 がまだ 1 ファイルも触っていない間だけ真"""
    if not _entry_marked(v):
        return False, "入口の印（process.request_entry）が無い——通常の run"
    at = v("loop.request_fixed_at", None)
    if at:
        return False, f"入口の印は在るが、{at} 周目の P3 が修正を入れた——入口の周は終わった"
    return True, "判定から入る run の周（入口の印が在り、修正がまだ 1 ファイルも入っていない）"


@cond_reads("record.process.request_entry", "loop.request_fixed_at", "round")
def entry_first_fix(v):
    """元 rules:194。判定から入る run で、最初に修正が入った次の周か"""
    if not _entry_marked(v):
        return False, "入口の印（process.request_entry）が無い——通常の run"
    at, rnd = v("loop.request_fixed_at", None), v("round")
    return at == rnd - 1, f"判定から入る run で、最初に修正が入った周は {at}（今は {rnd} 周目）"


@cond_reads("loop.changed_files")
def touches_procedures(v):
    """元 rules:372"""
    files = v("loop.changed_files", [])
    hit = sorted({f for f in files for p in PROCEDURE_PATTERNS if re.search(p, f)})
    return bool(hit), (f"差分に手順書・スクリプト・CI 定義が {len(hit)} 件" if hit else "差分に手順書・スクリプト・CI 定義が無い")


@cond_reads("loop.prev_fix_files")
def prev_fix_touched(v):
    """元 rules:379。前の周の P3 が 1 ファイルでも触ったか（1 run = 1 周なので、いつも 0 件）"""
    n = len(v("loop.prev_fix_files", None) or [])
    return bool(n), f"前の周の P3 が触ったファイルは {n} 件"


def _findings_vetted(rows):
    """元 rules:391。目的監査の findings が裏取りの柵を通った形か（cite を持つか）。空は偽"""
    return all(isinstance(r, dict) and r.get("cite") for r in rows) if rows else False


@cond_reads("record.process.purpose_review")
def purpose_review_unvetted(v):
    """元 rules:413。記録の目的監査が、裏取りの柵より前の形で凍っているか"""
    pr = v("record.process.purpose_review", None) or {}
    if not pr.get("verdict"):
        return False, "目的監査はまだ一度も走っていない"
    rows = pr.get("findings") or []
    if not rows:
        return False, "目的監査の指摘が 0 件（根拠を連れて来る物が無い）"
    if _findings_vetted(rows):
        return False, "目的監査の指摘は裏取りの柵を通った形"
    return True, "目的監査の指摘が裏取りの柵より前の形で凍っている"


@cond_reads("out.p0.purpose", "loop.prev_fix_files")
def purpose_sources_changed(v):
    """元 rules:439。目的テキストの出典文書を、前の周の P3 が触ったか"""
    out = v("out.p0.purpose", None) or {}
    if "source_files" not in out:
        why = "p0.purpose の出力に source_files が無い（once で凍った周の schema には無かった欄）"
        v.unevaluable("purpose_sources_changed", why)
        return False, why
    srcs = out.get("source_files") or []
    if not srcs:
        return False, "目的テキストが出典ファイルを持たない"
    hit = sorted(set(v("loop.prev_fix_files", None) or []) & set(srcs))
    return bool(hit), (f"前の周の P3 が目的の出典 {hit} を触った" if hit else "前の周の P3 は目的の出典を触っていない")


@cond_reads("loop.gates")
def gates_merge(v):
    """元 rules:771。変異の検算を合流でまとめる run か"""
    got = v("loop.gates", None)
    return got == GATES_MERGE, (GATES_MERGE_WHY if got == GATES_MERGE else "変異の検算をこの run で撃つ（init --input gates=merge が無い）")


def _first(v):
    """元 rules:1028"""
    return v("round") == 1


def _eq_true(x):
    """元 rules:1032。1 も真として数え、真理値として真になるだけの値（空でない文字列など）は数えない"""
    return x == True  # noqa: E712


def _fix_says(v, field):
    """元 rules:1042"""
    return _eq_true(v(f"prev.p3.fix.{field}", False))


def _escalated(v):
    """元 rules:1046"""
    return bool(v("loop.escalated", None))


def _because(ok, when, facts):
    """元 rules:1050。理由の文: 条件の名乗り（when）と、評価に使った事実"""
    return ok, f"{when}——{'成り立つ' if ok else '成り立たない'}（{facts}）"


def _touched(field, fix_field, what):
    """元 rules:1055。差分が〜に触れるか: 差分の形の申告（p0.base の field）か、前の周の修正の申告（p3.fix の fix_field）"""
    @cond_reads(f"out.p0.base.{field}", f"prev.p3.fix.{fix_field}")
    def fn(v):
        ok = _eq_true(v(f"out.p0.base.{field}")) or _fix_says(v, fix_field)
        return ok, f"差分が{what}に触れる" if ok else f"差分も前の周の修正も{what}に触れない（p0.base.{field}・p3.fix.{fix_field}）"
    fn.__name__ = f"{field.removeprefix('touches_')}_touched"
    return fn


gates_touched = _touched("touches_gates", "gates_changed", "検証ゲート")
seams_touched = _touched("touches_external_seams", "seams_changed", "外部との継ぎ目")
user_path_touched = _touched("touches_user_path", "path_changed", "利用者から見える経路")
_security_declared = _touched("touches_security_surface", "security_surface_changed", "認証・データの取り扱い・外部との入出力")


@cond_reads(*dict.fromkeys((*_security_declared.reads, *seams_touched.reads, "record.process.fixes")))
def security_surface_touched(v):
    """元 rules:1072。認証・データの取り扱い・外部との入出力に触れるか（局所レビューの条件付きレンズ /security-review の条件）"""
    if v("out.p0.base.touches_security_surface", None) is None:
        v.unevaluable("security_surface_touched", "p0.base に touches_security_surface の欄が無い共有ボード——当てる側に倒した")
        return True, "p0.base に touches_security_surface の欄が無い共有ボードなので、当てる側に倒した（申告されていない）"
    for part in (_security_declared, seams_touched):
        ok, why = part(v)
        if ok:
            return True, why
    past = [f.get("round") for f in v("record.process.fixes", []) or []
            if isinstance(f, dict) and (f.get("security_surface_changed") is True or f.get("seams_changed") is True)]
    if past:
        return True, f"前の周（{past}）の修正が認証・データの取り扱い・外部との入出力か継ぎ目に触れた（累積の差分に残る）"
    return False, ("差分も前のどの周の修正も認証・データの取り扱い・外部との入出力・継ぎ目に触れない"
                   "（p0.base.touches_security_surface・touches_external_seams・process.fixes）")


_TOUCH = ("round", *prev_fix_touched.reads)   # 深さの節が共通して読む欄


@cond_reads(*request_entry.reads)
def not_request_entry(v):
    """元 rules:1094。判定から入る run の周でない（修正が入るまで P1 の役を起こさない）"""
    entry, why = request_entry(v)
    return (not entry), (f"{why}のため、P1 の役を起こさない" if entry else why)


@cond_reads(*request_entry.reads, *_TOUCH, "prev.p3.fix.mechanism_changed")
def external_standards_due(v):
    """元 rules:1101。判定から入る run の周でなく、初回か、機構を足した／変えた周か、前の周の P3 が何かを直した周"""
    entry, why = request_entry(v)
    if entry:
        return False, f"{why}のため、外部標準の照合を起こさない"
    ok = _first(v) or _fix_says(v, "mechanism_changed") or prev_fix_touched(v)[0]
    return _because(ok, "初回か、機構を足した／変えた周か、前の周の P3 が何かを直した周",
                    f"round={v('round')}・{prev_fix_touched(v)[1]}")


@cond_reads(*request_entry.reads, *_TOUCH)
def provenance_due(v):
    """元 rules:1112。判定から入る run の周でなく、初回か、前の周の P3 が何かを直した周"""
    entry, why = request_entry(v)
    if entry:
        return False, f"{why}のため、出典の確かめを起こさない"
    ok = _first(v) or prev_fix_touched(v)[0]
    return _because(ok, "初回か、前の周の P3 が何かを直した周", f"round={v('round')}・{prev_fix_touched(v)[1]}")


def _deep(v, touched, when, extra=None):
    """元 rules:1121。P1 の深さの節の、入口を見た後の残り: (touched and (初回[ or extra が人待ち])) or 前の周の P3 が触った"""
    t, twhy = touched(v)
    ok = (t and (_first(v) or (extra is not None and v(extra, None) == "awaiting_human"))) or prev_fix_touched(v)[0]
    return _because(ok, when, f"round={v('round')}・{twhy}・{prev_fix_touched(v)[1]}")


def _deep_due(name, touched, when, noun, merge_off=False):
    """元 rules:1129。P1 の深さの節（手順の追跡・ゲートの検算・代役の忠実さ）の条件の工場"""
    extra = gates_merge.reads if merge_off else ()

    @cond_reads(*dict.fromkeys((*extra, *request_entry.reads, *_TOUCH, *touched.reads, "loop.escalated")))
    def fn(v):
        if merge_off:
            merged, mwhy = gates_merge(v)
            if merged:
                return False, mwhy
        entry, why = request_entry(v)
        if not entry:
            ok, rwhy = _deep(v, touched, when)
            return (True, f"{rwhy}・昇格した周") if not ok and _escalated(v) else (ok, rwhy)
        if _escalated(v):
            return True, f"判定から入る run の周だが、昇格した周なので{noun}を起こす"
        return False, f"{why}のため、{noun}を起こさない"
    fn.__name__ = fn.__qualname__ = name
    fn.__doc__ = f"{when}。判定から入る run の周は外すが、昇格した周は入口より勝つ"
    return fn


procedure_trace_due = _deep_due("procedure_trace_due", touches_procedures,
                                "差分に手順書・スクリプト・CI 定義があって初回の周、または前の周の P3 が何かを直した周", "手順の追跡")
gate_efficacy_due = _deep_due("gate_efficacy_due", gates_touched,
                              "差分がゲートを新設・変更していて初回の周、または前の周の P3 が何かを直した周", "ゲートの検算",
                              merge_off=True)
test_double_fidelity_due = _deep_due("test_double_fidelity_due", seams_touched,
                                     "差分が外部との継ぎ目に触れていて初回の周、または前の周の P3 が何かを直した周", "代役の忠実さの確かめ")


@cond_reads(*request_entry.reads, *_TOUCH, *user_path_touched.reads, "loop.last_material.main_path_observation.status")
def main_path_observation_due(v):
    """元 rules:1162。判定から入る run の周でなく、差分が利用者から見える経路を変え、初回か前の周に人待ちだった周、
    または前の周の P3 が何かを直した周"""
    entry, why = request_entry(v)
    if entry:
        return False, f"{why}のため、主経路の観察を起こさない"
    return _deep(v, user_path_touched, "差分が利用者から見える経路を変え、初回か前の周に人待ちだった周、"
                 "または前の周の P3 が何かを直した周", extra="loop.last_material.main_path_observation.status")


@cond_reads("round", "prev.p3.fix.decision_records_changed", "loop.escalated", *prev_fix_touched.reads)
def prior_decisions_due(v):
    """元 rules:1173。初回か、前の周の P3 がリポジトリの外に決定記録を書き足した周、または前の周の P3 が何かを直した周（昇格した周も）"""
    ok = _first(v) or _fix_says(v, "decision_records_changed") or prev_fix_touched(v)[0] or _escalated(v)
    return _because(ok, "初回か、前の周の P3 がリポジトリの外に決定記録を書き足した周、または前の周の P3 が何かを直した周（昇格した周も）",
                    f"round={v('round')}・{prev_fix_touched(v)[1]}")


@cond_reads("out.p0.purpose.source", "round", *purpose_sources_changed.reads, *purpose_review_unvetted.reads)
def purpose_review_due(v):
    """元 rules:1183。目的テキストを writer が要約した（出典③）周"""
    src = v("out.p0.purpose.source")
    if src != "③writer の要約":
        return False, f"目的テキストの出典が {src}——監査するのは writer が要約した目的（③）だけ"
    if _first(v):
        return True, "writer が要約した目的の 1 周目"
    for f in (purpose_sources_changed, purpose_review_unvetted):
        ok, why = f(v)
        if ok:
            return True, why
    return False, "writer が要約した目的だが、1 周目でなく、出典も監査の形も変わっていない"


@cond_reads("round", *entry_first_fix.reads)
def parallel_pr_due(v):
    """元 rules:1198。1 周目か、判定から入る run で最初に修正が入った次の周"""
    if _first(v):
        return True, "1 周目"
    return entry_first_fix(v)


# 元 rules:1273 の CONDS のうち、このブロックの素材の節が名指す物
CONDS = {
    ENTRY_BUILTIN: request_entry, "not_request_entry": not_request_entry,
    "purpose_review_due": purpose_review_due, "prior_decisions_due": prior_decisions_due,
    "external_standards_due": external_standards_due, "procedure_trace_due": procedure_trace_due,
    "gate_efficacy_due": gate_efficacy_due, "test_double_fidelity_due": test_double_fidelity_due,
    "main_path_observation_due": main_path_observation_due, "provenance_due": provenance_due,
    "parallel_pr_due": parallel_pr_due, "gates_merge": gates_merge,
    "touches_procedures": touches_procedures, "gates_touched": gates_touched, "seams_touched": seams_touched,
    "user_path_touched": user_path_touched, "security_surface_touched": security_surface_touched,
}


# 元 works/.shared/core/graphloops/graphs/review-loop.json の素材の節（cond・applies_cond・na_reason・na_self_ok・materials・post_check・writes）
MATERIAL_NODES = {'p0.prior_decisions': {'cond': 'prior_decisions_due',
                        'na_self_ok': False,
                        'materials': ['prior_decisions'],
                        'writes': [{'op': 'set', 'to': 'materials.prior_decisions', 'from': 'material'},
                                   {'op': 'set',
                                    'to': 'process.prior_decisions',
                                    'from': '$',
                                    'pick': ['checked', 'searched', 'settled']}]},
 'p0.purpose_review': {'cond': 'purpose_review_due',
                       'post_check': 'purpose_findings_cited',
                       'writes': [{'op': 'set', 'to': 'process.purpose_review', 'from': '$'}]},
 'p1.local_review': {'cond': 'not_request_entry',
                     'na_self_ok': False,
                     'materials': ['local_review'],
                     'post_check': 'local_review_covers_lenses',
                     'writes': [{'op': 'set', 'to': 'materials.local_review', 'from': 'material'},
                                {'op': 'set', 'to': 'process.local_findings', 'from': 'findings'}]},
 'p1.consistency_bypass': {'cond': 'not_request_entry',
                           'na_self_ok': False,
                           'materials': ['consistency', 'bypass'],
                           'writes': [{'op': 'set', 'to': 'materials.consistency', 'from': 'consistency'},
                                      {'op': 'set', 'to': 'materials.bypass', 'from': 'bypass'},
                                      {'op': 'set', 'to': 'process.consistency_findings', 'from': 'findings'},
                                      {'op': 'set', 'to': 'process.bypass_findings', 'from': 'bypass_findings'}]},
 'p1.hygiene': {'cond': 'not_request_entry',
                'na_self_ok': False,
                'materials': ['hygiene'],
                'writes': [{'op': 'material_from_findings', 'to': 'hygiene', 'from': '$'}]},
 'p1.external_standards': {'cond': 'external_standards_due',
                           'na_self_ok': False,
                           'materials': ['external_standards'],
                           'post_check': 'external_rankings',
                           'writes': [{'op': 'set', 'to': 'materials.external_standards', 'from': 'material'},
                                      {'op': 'set', 'to': 'process.external_findings', 'from': 'findings'},
                                      {'op': 'set', 'to': 'process.external_rankings', 'from': 'rankings'}]},
 'p1.procedure_trace': {'cond': 'procedure_trace_due',
                        'applies_cond': 'touches_procedures',
                        'na_reason': '対象差分に手順書・スクリプト・CI 定義の変更が無い',
                        'materials': ['procedure_trace'],
                        'writes': [{'op': 'set', 'to': 'materials.procedure_trace', 'from': 'material'},
                                   {'op': 'set', 'to': 'process.procedure_findings', 'from': 'findings'}]},
 'p1.gate_efficacy': {'cond': 'gate_efficacy_due',
                      'applies_cond': 'gates_touched',
                      'na_reason': '対象差分は検証ゲート（CI ジョブ・assert・テスト・pre-commit）を新設・変更していない',
                      'materials': ['gate_efficacy'],
                      'post_check': 'gate_arms_all_red',
                      'writes': [{'op': 'set', 'to': 'materials.gate_efficacy', 'from': 'material'},
                                 {'op': 'set', 'to': 'process.gate_arms', 'from': 'arms'}]},
 'p1.test_double_fidelity': {'cond': 'test_double_fidelity_due',
                             'applies_cond': 'seams_touched',
                             'na_reason': '対象差分は外部との継ぎ目（別プロセス・別サービス・ブラウザ・外部 API・プロトコル）に触れていない',
                             'materials': ['test_double_fidelity'],
                             'writes': [{'op': 'set', 'to': 'materials.test_double_fidelity', 'from': 'material'}]},
 'p1.main_path_observation': {'cond': 'main_path_observation_due',
                              'applies_cond': 'user_path_touched',
                              'na_reason': '対象差分は利用者から見える経路・外部との継ぎ目を変えていない',
                              'materials': ['main_path_observation'],
                              'post_check': 'main_path_observed',
                              'writes': [{'op': 'set', 'to': 'materials.main_path_observation', 'from': 'material'}]},
 'p1.provenance': {'cond': 'provenance_due',
                   'na_self_ok': False,
                   'materials': ['provenance'],
                   'writes': [{'op': 'set', 'to': 'materials.provenance', 'from': 'material'}]}}
# 元 review-loop.json の p1.local_review の skills（レンズの正本）
LOCAL_REVIEW_SKILLS = [{'skill': '/code-review',
  'args': 'high',
  'required': True,
  'note': '組み込み（同名のプラグインが別に在る）。対象は changed_files_file に並ぶ**ファイルのパス**で渡す——ref 範囲は作業ツリーを含まない。--comment も --fix も付けるな。'},
 {'skill': 'pr-review-toolkit:code-reviewer', 'required': True, 'note': '準拠とバグ検出の両方を担う汎用レンズ。**落とすな。**'},
 {'skill': '/simplify', 'required': True, 'note': '**修正を禁じた形でだけ呼べ**（実物は既定で作業ツリーを書き換える）。4 観点（再利用・単純化・効率・高度）をそれぞれ起こし、指摘だけ返させる。'},
 {'skill': '/security-review', 'required': False, 'applies_cond': 'security_surface_touched'},
 {'skill': 'pr-review-toolkit:silent-failure-hunter', 'required': True, 'note': '黙って無力化される検査・握り潰される失敗を見る。'},
 {'skill': 'pr-review-toolkit:type-design-analyzer', 'required': True, 'note': '不変条件を平坦な値で持つ設計を見る。散文の振り分けでは当たらないクラス。'},
 {'skill': 'pr-review-toolkit:pr-test-analyzer', 'required': True, 'note': '振る舞い網羅のレンズ。他のどのノードも見ていない。'}]
# 役の名（YAML の節 id・with: の role）→ 写しの graph の節。元 works/blk-material/lib/material.py:62 の ROLES（並びは graph の順）
MATERIAL_ROLES = {
    "prior-decisions": "p0.prior_decisions",
    "purpose-review": "p0.purpose_review",
    "local-review": "p1.local_review",
    "consistency-bypass": "p1.consistency_bypass",
    "hygiene": "p1.hygiene",
    "external-standards": "p1.external_standards",
    "procedure-trace": "p1.procedure_trace",
    "gate-efficacy": "p1.gate_efficacy",
    "test-double-fidelity": "p1.test_double_fidelity",
    "main-path-observation": "p1.main_path_observation",
    "provenance": "p1.provenance",
}
# 役の指示書（commands/material-<役>.md。元の p0.*・p1.* の指示書）の穴。prep が値を描いて材料のファイルに置く
MATERIAL_HOLES = {
    "prior-decisions": ("inputs.cwd", "record.base", "loop.changed_files", "loop.request_wheres"),
    "purpose-review": ("out.p0.purpose.purpose_text", "inputs.review_rev", "inputs.cwd"),
    "local-review": ("loop.diff_file", "record.base", "loop.changed_files_file", "inputs.review_md", "?inputs.repo_review_md",
                     "node.skills"),
    "consistency-bypass": ("loop.diff_file", "loop.changed_files", "record.base", "inputs.review_md", "?inputs.repo_review_md",
                           "inputs.review_rev", "inputs.cwd"),
    "hygiene": ("section:inputs.review_md#コード衛生観点", "file:loop.diff_file"),
    "external-standards": ("loop.diff_file", "loop.changed_files", "inputs.review_md", "out.p0.purpose.purpose_text",
                           "out.p0.purpose.known_weaknesses", "inputs.cwd"),
    "procedure-trace": ("loop.diff_file", "loop.changed_files", "inputs.review_md", "inputs.cwd"),
    "gate-efficacy": ("loop.diff_file", "loop.changed_files_file", "record.base", "inputs.cwd", "loop.mutation_decl.text"),
    "test-double-fidelity": ("loop.diff_file", "loop.changed_files_file", "inputs.cwd"),
    "main-path-observation": ("loop.diff_file", "loop.changed_files_file", "inputs.cwd"),
    "provenance": ("loop.diff_file", "record.base", "inputs.cwd"),
}
SIMPLIFY_LENS = "/simplify"   # 元 material.py:124
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "   # 元 material.py:175
LOCATION_HEAD = "所見の場所の行がファイルに無い（差分の行番号を書いていないか。作業ツリーのファイルの行で書き直せ）"   # 元 material.py:164
LOCATION_MARK = "（works の受け付け: この行はファイルに無い——差分の行番号の疑い）"   # 元 material.py:165
NA_HEADING = promptsection.Section("## 『条件に当たらない』（not_applicable）を書けるか（works の受け付けより。上の指示書の読み替え）",
                                   source="fn:judge_accept._na_note")   # 元 material.py:154
NA_REFUSED = ("`not_applicable` は受け付けが拒む——見た結果を found・clean で、確かめられなかったなら not_run（理由つき）で"
              "書け。")   # 元 material.py:155
MUTATION_UNDECLARED = ("対象リポジトリの宣言（{decl}）に mutation の段が無い——在りかと呼び方は対象リポジトリの側（README・CONTRIBUTING・"
                       "CI 定義・対象リポジトリの REVIEW.md など）が名指しする物を探せ（このプロンプトは道具の名前と引数の綴りを持たない）")   # 元 rules:730
MATERIAL_BRIEF_HEAD = promptsection.Section("# 素材集めの役の材料（機械が描いた物）", source="fn:judge_accept.material_prep")
SNAPSHOT_FALLBACK_IDENT = {"GIT_AUTHOR_NAME": "graphloops", "GIT_AUTHOR_EMAIL": "graphloops@localhost",
                           "GIT_COMMITTER_NAME": "graphloops", "GIT_COMMITTER_EMAIL": "graphloops@localhost"}   # 元 rules:1546


def route_key(role: str) -> str:
    """元 material.py:185。route の返りの欄の名（YAML の when: が $material-route.output.<欄> で読む）"""
    return role.replace("-", "_")


def _material_node(role: str) -> str:
    """元 material.py:199 の _node。役の名から写しの graph の節。素材集めの役でなければ Reject"""
    if role not in MATERIAL_ROLES:
        raise Reject(f"役 {role!r} は素材集めの役（{' / '.join(MATERIAL_ROLES)}）でない——YAML の with: を確かめる")
    return MATERIAL_ROLES[role]


def review_md_paths(lib_dir, repo) -> tuple:
    """元 rules:35 の review_md_path（観点の正本の置き場）。(lib の REVIEW.md の絶対パス, 対象の根の REVIEW.md の絶対パスか "")"""
    own = pathlib.Path(lib_dir).resolve() / "REVIEW.md"
    theirs = pathlib.Path(repo).resolve() / "REVIEW.md"
    return str(own), (str(theirs) if theirs.is_file() else "")


# ---------------------------------------------------------------- 対象差分と読む版（元 rules:1356-1570）
def numstat_totals(text):
    """元 rules:1356。`git diff --numstat` の出力から（ファイル名の並び・追加行・削除行・行の数）を取る"""
    if "\0" in text:
        rows, i = [], 0
        parts = text.split("\0")
        while i < len(parts):
            head = parts[i]
            if not head.strip():
                i += 1
                continue
            cols = head.split("\t")
            if len(cols) == 3 and cols[2] == "":      # 改名: ins \t dels \t "" \0 old \0 new
                if i + 2 >= len(parts):
                    break
                rows.append([cols[0], cols[1], parts[i + 2]])
                i += 3
            else:
                rows.append(cols)
                i += 1
    else:
        rows = [ln.split("\t") for ln in text.splitlines() if ln.strip()]
    full = [r for r in rows if len(r) == 3]
    names = "\n".join(r[2] for r in full)
    ins = sum(int(r[0]) for r in full if r[0].isdigit())
    dels = sum(int(r[1]) for r in full if r[1].isdigit())
    return names, ins, dels, len(rows)


def _unfrozen(what, why, hint=None):
    """元 rules:1535。版を固定できない回の Reject（git が言った理由を必ず添える）"""
    said = " / ".join(w for w in why if w) or "git は理由を返さなかった"
    return Reject(f"この周に採点する版を固定できない（{what}。git の言い分: {said}）" + (f"——{hint}" if hint else ""))


def _worktree_tree(repo):
    """元 rules:1501。作業ツリーの今の姿の木の id（未追跡の新規ファイルも含め、追跡していない .gitignore の対象は除く）。
    本物の index を一時 index に写して印を外し（accept.copy_flag_free_index。accept.touched_files と同じ見え方）てから
    add -A する（本物の index は読むだけで書かない）。固められなければ Reject"""
    tmp = tempfile.mkdtemp(prefix="graphloops-index-")
    idx = pathlib.Path(tmp) / "index"
    env = {"GIT_INDEX_FILE": str(idx)}
    why = []
    try:
        try:
            core_accept.copy_flag_free_index(repo, idx)
        except Reject as e:
            raise Reject(f"この周に採点する版を固定できない（本物の index を印を外して写せない: {e}）")
        if git("update-index", "-q", "--really-refresh", env=env, why=why) is None or git("add", "-A", env=env, why=why) is None:
            raise _unfrozen("一時 index への git update-index / add -A が失敗した", why)
        tree = git("write-tree", env=env, why=why)
        if tree is None or not tree.strip():
            raise _unfrozen("git write-tree が木を返さない", why)
        return tree.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _snapshot(repo, msg):
    """元 rules:1550。作業ツリーの今の姿を commit 1 つに固めて返す（枝も index も動かさない）。固められなければ Reject"""
    tree = _worktree_tree(repo)
    head = git("rev-parse", "HEAD")
    parent = ["-p", head.strip()] if head and head.strip() else []
    why, snap = [], None
    for ident in (None, SNAPSHOT_FALLBACK_IDENT):
        snap = git("commit-tree", tree, *parent, "-m", msg, env=ident, why=why)
        if snap is not None:
            break
    if snap is None or not snap.strip():
        raise _unfrozen("git commit-tree が版を返さない", why)
    return snap.strip()


def _take_diff(jdir, repo, start: dict) -> dict:
    """元 rules:1399 の _take_diff（と _freeze_revision 1468）。差分の根（始めの記録の diff_base。空なら HEAD）から、作業ツリーの今の姿を
    固めた版（_snapshot。未追跡の新規ファイルも入る）までの差分を置き場の diff.patch に生バイトで書き、変更ファイル（accept.touched_files）を
    changed-files.txt に書く。返り {base, review_rev, diff_file, changed_files, changed_files_file, stat, commits}。
    空の差分は止めない（判定から入る run は差分が空なのが普通。盤面の空差分の柵は 1 run = 1 周の形では入口が見る）"""
    j, repo_p = pathlib.Path(jdir), pathlib.Path(repo)
    with core_accept.in_repo(repo_p):
        base = core_accept.resolve_rev(repo_p, start.get("diff_base") or "")
        snap = _snapshot(repo_p, "works-factory judge")
        raw = core_accept._git(repo_p, "diff", "--binary", base, snap, binary=True)
        numstat = core_accept._git(repo_p, "diff", "--numstat", "-z", base, snap)
        commits = core_accept._git(repo_p, "rev-list", "--count", f"{base}..HEAD").strip()
    _, ins, dels, nfiles = numstat_totals(numstat)
    changed = core_accept.touched_files(repo_p, base)
    j.mkdir(parents=True, exist_ok=True)
    f = j / DIFF_FILE
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, f)
    cf = j / CHANGED_FILE
    tmp = cf.with_name(f"{cf.name}.{os.getpid()}.tmp")
    tmp.write_text("\n".join(changed) + "\n", encoding="utf-8")
    os.replace(tmp, cf)
    return {"base": base, "review_rev": snap, "diff_file": str(f), "changed_files": changed, "changed_files_file": str(cf),
            "stat": f"{nfiles} files changed, {ins} insertions(+), {dels} deletions(-)", "commits": int(commits or 0)}


def _material_view(jdir, repo, start: dict, *, retake: bool = False) -> dict:
    """素材の役と判定役が読む版と差分（material-view.json）。在れば読み、無いか retake なら _take_diff で取り直して置く"""
    p = pathlib.Path(jdir) / MATERIAL_VIEW_FILE
    doc = None if retake else read_json(p)
    if not isinstance(doc, dict) or "review_rev" not in doc:
        doc = _take_diff(jdir, repo, start)
        write_json(p, doc)
    return doc


def _start_of(jdir) -> dict:
    doc = read_json(pathlib.Path(jdir) / START_FILE, {}) or {}
    return start_view(doc) if "input" not in doc else doc


def _purpose_of(jdir):
    """置き場の目的の文（purpose.json）。無い・読めなければ None"""
    try:
        doc = read_json(pathlib.Path(jdir) / _purpose.PURPOSE_FILE)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("purpose_text"), str) else None


def _requests(jdir) -> list:
    rows = read_json(pathlib.Path(jdir) / REQUEST_FILE, []) or []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def request_batches(jdir, start: dict) -> list:
    """依頼の行（request.json）を出どころごとのバッチ [{round, origin, findings}] にする（元 record.process.request_findings の形。
    1 run は 1 周なので round は 1）。仕様の段が積んだ受け入れ条件の行（spec_freeze が本文の頭に SPEC_PROVENANCE を書く）は
    origin が SPEC_ORIGIN、ほかは人の依頼（入口の印が立つ run はその出どころ）。行の無いバッチは置かない"""
    rows = _requests(jdir)
    spec = [r for r in rows if str(r.get("text") or "").startswith(SPEC_PROVENANCE)]
    human = [r for r in rows if not str(r.get("text") or "").startswith(SPEC_PROVENANCE)]
    entry = (due_view(start, None, []).values.get("record.process.request_entry") or {}).get("origin")
    human_origin = entry or f"人の依頼（{start.get('request_file') or '依頼の行'}）"
    return [{"round": 1, "origin": origin, "findings": got} for origin, got in ((human_origin, human), (SPEC_ORIGIN, spec)) if got]


def request_wheres(view: DueView, jdir) -> list:
    """元 rules:203。判定から入る run の周に、判定に届く依頼の where の一覧。そうでない周は []"""
    if not request_entry(view)[0]:
        return []
    return [r["where"] for r in _requests(jdir) if isinstance(r.get("where"), str)]


# ---------------------------------------------------------------- 素材の要否を決める（元 material.py:290 の route の書き直し）
def due_roles(view: DueView) -> dict:
    """素材集めの役ごとの (回すか, 理由)。条件は写しの graph の節の cond（元 rules の CONDS）"""
    return {role: CONDS[MATERIAL_NODES[nid]["cond"]](view) for role, nid in MATERIAL_ROLES.items()}


def _entry_skipped(view: DueView, nid: str) -> bool:
    """元 rules:213。節が入口のせいで外れたか——入口の周で、同じ条件が入口の印を外した文脈（ENTRY_OFF）なら真"""
    if not request_entry(view)[0]:
        return False
    off = DueView({**view.values, "record.process.request_entry": None})
    return CONDS[MATERIAL_NODES[nid]["cond"]](off)[0]


def _fill_one(view: DueView, jdir, nid: str, why: str) -> dict:
    """元 rules:1705 の fill_materials のうち、走らせなかった節の素材 1 つの埋め（1 周目の値。前の周の持ち越しは無い）"""
    n = MATERIAL_NODES[nid]
    if _entry_skipped(view, nid):
        origin = (view("record.process.request_entry", None) or {}).get("origin", "")
        return {"status": "not_applicable",
                "reason": f"判定から入る run（出どころ: {origin}。この周の判定に届く人の依頼 {len(_requests(jdir))} 件）のため、"
                          "P1 の役を起こしていない——依頼の外を見る目はこの周に無い（判定役と修正前後の審査だけが見る）"}
    ap = n.get("applies_cond")
    ap_ok, ap_why = CONDS[ap](view) if ap is not None else (True, "")
    if not ap_ok:
        return {"status": "not_applicable", "reason": f"{n.get('na_reason', '条件に当たらない')}（{ap_why}）"}
    if n.get("cond") == "gate_efficacy_due" and view("loop.gates", None) == GATES_MERGE:
        return {"status": "not_applicable",
                "reason": f"{GATES_MERGE_WHY}——差分はゲートに触れているが、この run では撃たない。"
                          "合流した版を gates=merge 無しの run で回し、そこの P1 のゲートの検算が撃つ"}
    return {"status": "not_run", "reason": f"走らせる条件に当たらず、流用できる前の判定も無い（ノード {nid}。{why}）"}


def material_route(jdir, repo) -> dict:
    """元 works/blk-material/lib/material.py:290 の route の書き直し。素材ごとの要否を元の条件で決める。返り {<route_key(役)>: bool…,
    reason}。止めの控えが在れば全部偽。対象差分と読む版を material-view.json（と diff.patch・changed-files.txt）に、要否と
    回さない素材の埋めを material-route.json に、役を起こす前の作業ツリーの姿を material-tree.json に置く（1 度だけ。run の再開で
    走り直しても最初の姿を残す）"""
    j = pathlib.Path(jdir)
    off = {route_key(r): False for r in MATERIAL_ROLES}
    stop = read_stop(j)
    if stop:
        reason = f"止まっている（{stop['stop_reason']}: {stop.get('reason', '')}）——素材集めの役を起こさない"
        write_json(j / MATERIAL_ROUTE_FILE, {"roles": {}, "fill": {}, "reason": reason})
        return {**off, "reason": reason}
    start = _start_of(j)
    try:
        doc = _material_view(j, repo, start, retake=True)
    except Reject as e:
        reason = f"対象差分が取れない（{e}）——素材集めの役を起こさない"
        write_json(j / MATERIAL_ROUTE_FILE, {"roles": {}, "fill": {}, "reason": reason})
        return {**off, "reason": reason}
    if not (j / MATERIAL_TREE_FILE).is_file():
        snap_tree(j, MATERIAL_TREE_FILE, repo)
    view = due_view(start, _purpose_of(j), doc["changed_files"])
    got = due_roles(view)
    fill = {}
    for role, (ok, why) in got.items():
        if not ok:
            nid = MATERIAL_ROLES[role]
            for mat in MATERIAL_NODES[nid].get("materials", []):
                fill[mat] = _fill_one(view, j, nid, why)
    reason = "・".join(f"{MATERIAL_ROLES[r]}: {'回す' if ok else why}" for r, (ok, why) in got.items())
    write_json(j / MATERIAL_ROUTE_FILE, {"roles": {r: {"run": ok, "why": why} for r, (ok, why) in got.items()},
                                         "fill": fill, "reason": reason, "notes": view.notes})
    return {**{route_key(r): ok for r, (ok, _) in got.items()}, "reason": reason}


# ---------------------------------------------------------------- 支度（元 material.py:376 の prep と render の値の埋め方）
def _skills(view: DueView, role: str) -> list:
    """元 material.py:442。この周の節の宣言のレンズ（graph の skills）に、engine が節を出す時に置いた条件の評価 applies・applies_why を
    足した物（applies_cond を持つ要素だけ）。局所レビューでない役は []"""
    if MATERIAL_ROLES.get(role) != "p1.local_review":
        return []
    out = []
    for e in LOCAL_REVIEW_SKILLS:
        e = dict(e)
        if "applies_cond" in e:
            e["applies"], e["applies_why"] = CONDS[e["applies_cond"]](view)
        out.append(e)
    return out


# 元 works/.shared/core/entry.py:206-229。ゲートの検算の役（p1.gate_efficacy）の『条件に当たらない』（canary の run e91112dd）。
# p0.base は機械が組み（due_view）、touches_gates を判定せずに真へ倒す——機械には差分の柵（分岐）がゲートかを決められないので、
# 役を起こす側に倒す。check_record はその値を機械の事実として読み、ゲートに触れない差分でも役の not_applicable を拒むので、
# 0 腕の役は not_run（検証器の阻害）しか名乗れない。差分を読むゲートの検算の役の判定を受けるのは、機械が持つ事実がどれも
# 『ゲートに触れる』と言わない時だけ: 前の周の修正がゲートを変えたと申告していない（倒した p0.base の値を外して評価する）、差分に
# 機械が見るゲートの印（GATE_FILE_PATTERNS のファイル・assert を足す・消す行）が無い。印が 1 つでも在れば拒む（測らせる）
GATE_NODE = "p1.gate_efficacy"
GATES_COND = "gates_touched"
# 検証ゲートの定義のファイル（テスト・CI・pre-commit・フック・lint・試験の設定・変異の腕の一覧）。広めに当てる——当たり過ぎは
# 役に測らせる（今まで通り）だけで、当たり漏れが役の『条件外』を通す。元の試験の実行器の名の 2 つの設定ファイル（.ini）は E13 の
# 語の表に当たるので、*.ini と *.cfg を全部当てる形に広げた
GATE_FILE_PATTERNS = (
    r"(^|/)tests?/", r"(^|/)__tests__/", r"(^|/)spec/", r"(^|/)test_[^/]*$", r"_test\.[^/]+$", r"\.(test|spec)\.[^/]+$",
    r"(^|/)conftest\.py$", r"^\.github/", r"(^|/)\.gitlab-ci\.ya?ml$", r"^\.circleci/", r"(^|/)Jenkinsfile$",
    r"(^|/)\.travis\.ya?ml$", r"(^|/)azure-pipelines\.ya?ml$", r"^\.buildkite/", r"(^|/)\.pre-commit-config\.ya?ml$",
    r"^\.husky/", r"(^|/)lefthook\.ya?ml$", r"(^|/)\.?githooks/", r"(^|/)hooks/", r"(^|/)\.review-checks\.json$",
    r"(^|/)[^/]+\.(ini|cfg)$", r"(^|/)(noxfile\.py|pyproject\.toml|Makefile|justfile|package\.json)$",
    r"(^|/)(\.flake8|\.?ruff\.toml|\.pylintrc|\.eslintrc[^/]*|eslint\.config\.[^/]+|\.shellcheckrc|\.golangci\.ya?ml)$",
    rf"(^|/){re.escape(checkscope.SCOPE_DECL)}$",   # works の範囲の宣言（宣言の段を外す所を決める）
)
_GATE_FILES = tuple(re.compile(p) for p in GATE_FILE_PATTERNS)
_ASSERT_LINE = re.compile(r"^[+-](?![+-]{2} ).*\bassert", re.M)   # 足す・消す行（ファイルの頭の +++ / --- を除く）


def gate_signals(changed_files, diff_text: str) -> list:
    """元 works/.shared/core/entry.py:231。差分に機械が見るゲートの印の一覧（空なら印が無い）: ゲートの定義のファイルと、assert を
    足す・消す行"""
    hits = [f"ゲートの定義のファイル {f}" for f in changed_files if any(p.search(f) for p in _GATE_FILES)]
    hits += [f"assert の行 {m.group(0)[:80]!r}" for m in _ASSERT_LINE.finditer(diff_text or "")]
    return hits


def role_judged_na(view: DueView, nid: str, diff_file) -> bool:
    """元 works/.shared/core/entry.py:238 の role_judged_na_works。走ったゲートの検算の役の『条件外』を、機械が持つ事実がどれも
    『ゲートに触れる』と言わない時だけ受ける（上の注記）。p0.base はいつも機械の節（due_view）。ほかの節・変更ファイルの一覧の
    無い見方・読めない差分は受けない"""
    if MATERIAL_NODES[nid].get("applies_cond") != GATES_COND:
        return False
    if CONDS[GATES_COND](DueView({**view.values, "out.p0.base.touches_gates": False}))[0]:
        return False
    files = view("loop.changed_files")
    if not isinstance(files, list):
        return False
    try:
        diff = pathlib.Path(diff_file).read_text(encoding="utf-8", errors="replace")
    except (TypeError, OSError):
        return False
    return not gate_signals(files, diff)


def _na_note(view: DueView, nid: str, diff_file) -> str:
    """元 material.py:350。節 nid の役が素材に not_applicable を書けるかの段。check_record と同じ決め: applies_cond が在れば
    この周の真偽と役の判定を受ける差し替え（role_judged_na）、無ければ graph の na_self_ok の宣言"""
    n = MATERIAL_NODES[nid]
    ap = n.get("applies_cond")
    if ap is None:
        if n.get("na_self_ok"):
            body = (f"このノードは条件（applies_cond）を持たず、graph が『条件に当たらない』を名乗れるノードと宣言している（na_self_ok: "
                    f"{n['na_self_ok']}）。当たらない時は `not_applicable`（理由を reason に）を書いてよい。")
        else:
            body = ("このノードは条件（applies_cond）を持たず、graph も『条件に当たらない』を名乗れるノードと宣言していない（na_self_ok が"
                    f"無い）ので、{NA_REFUSED}")
    else:
        ok, why = CONDS[ap](view)
        if not ok:
            body = f"このノードの条件 `{ap}` はこの周に偽（{why}）なので、`not_applicable`（理由を reason に）を書いてよい。"
        elif role_judged_na(view, nid, diff_file):
            body = (f"このノードの条件 `{ap}` はこの周に真（{why}）だが、機械が持つ事実はどれも条件を立てていない（works の受け付けは"
                    "このノードの役の判定を受ける）。差分を読んで条件に当たらないと判じたら `not_applicable`（理由を reason に）を"
                    "書いてよい。")
        else:
            body = f"このノードの条件 `{ap}` はこの周に真（{why}）なので、{NA_REFUSED}"
    return f"{NA_HEADING}\n\n{body}"


def _purpose_or_missing(jdir) -> dict:
    """元 material.py:320 の _purpose。目的の文が無い run は PURPOSE_MISSING（目的を作らない）"""
    return _purpose_of(jdir) or {"purpose_text": PURPOSE_MISSING, "source": PURPOSE_UNKNOWN, "known_weaknesses": [], "source_files": []}


def mutation_decl(root) -> dict:
    """元 review-loop.py:734 の mutation_decl。変異の実行器と腕の一覧の名指しを、役に貼る 1 段落にした {declared, text}。対象の根の
    宣言の mutation の段が在ればその値、無い・読めなければ対象リポジトリの側を探させる散文（読めない時はその訳を添える）"""
    d = declared.read(root)
    m = (d or {}).get("mutation")
    if m:
        text = (f"対象リポジトリの宣言 {DECL_NAME} の mutation の段——実行器の呼び方の頭 {json.dumps(m['argv'], ensure_ascii=False)}・"
                f"腕の一覧 {m['arms']}（口の綴りは実行器の --help が正本）")
    else:
        text = MUTATION_UNDECLARED.format(decl=DECL_NAME)
        err = (d or {}).get("mutation_error") or (d or {}).get("error")
        if err:
            text += f"（宣言は在るが mutation の段を読めない: {err}）"
    return {"declared": bool(m), "text": text}


def _material_ctx(jdir, repo, start, doc, view, review_md, repo_review_md, role="") -> dict:
    """元 material.py:332 の render が engine に渡した値の入れ物（穴の名 → 値）。盤面の記録・周の値を、置き場のファイルと
    1 run = 1 周の値で埋めた物"""
    inputs = {"cwd": str(pathlib.Path(repo).resolve()), "review_md": review_md, "review_rev": doc["review_rev"]}
    if repo_review_md:
        inputs["repo_review_md"] = repo_review_md
    return {
        "inputs": inputs,
        "record": {"base": doc["base"]},
        "loop": {"diff_file": doc["diff_file"], "changed_files": doc["changed_files"],
                 "changed_files_file": doc["changed_files_file"], "request_wheres": request_wheres(view, jdir),
                 "mutation_decl": mutation_decl(repo)},
        "out": {"p0.purpose": _purpose_or_missing(jdir)},
        "node": {"skills": _skills(view, role)},
    }


def material_prep(jdir, role: str, repo, review_md: str, repo_review_md: str = "") -> dict:
    """元 works/blk-material/lib/material.py:376 の prep（と render の値の埋め方）の書き直し。役の指示書の穴（MATERIAL_HOLES）を
    engine と同じ描き方（engine.render.Renderer。切らない）で描き、『条件に当たらない』を書けるかの段（_na_note）を足して
    material-<役>-brief.md に置く。返り {brief_file, brief（同じ本文。道具の無い役に貼る）, review_md, repo_review_md}"""
    nid = _material_node(role)
    j = pathlib.Path(jdir)
    start = _start_of(j)
    doc = _material_view(j, repo, start)
    view = due_view(start, _purpose_of(j), doc["changed_files"])
    r = Renderer(_material_ctx(j, repo, start, doc, view, review_md, repo_review_md, role), cap=None)
    parts = [f"{MATERIAL_BRIEF_HEAD}\n\n素材集めの役 {role}（graphloops のノード {nid}）の指示書の「［材料: 〜］」は、この下の同じ名のセクションの値。"
             "パス（対象差分・変更ファイルの一覧・観点の正本など）は Read で読め（道具の無い役には本文を貼ってある）。"]
    for hole in MATERIAL_HOLES[role]:
        parts.append(f"## 材料: {hole.lstrip('?')}\n\n{r.render('{{' + hole + '}}')}")
    parts.append(_na_note(view, nid, doc["diff_file"]))
    text = "\n\n".join(parts) + "\n"
    p = j / f"material-{role}-brief.md"
    p.write_text(text, encoding="utf-8")
    return {"brief_file": str(p), "brief": text, "review_md": review_md, "repo_review_md": repo_review_md}


# ---------------------------------------------------------------- 素材の受け付けの規則（元 rules の post_check と数え直し）
def main_path_observed(nid, out):
    """元 rules:2962。主経路の観測: 見たと言う状態（found / clean）は、観測した値（observed）を 1 つ以上持つ"""
    st = (out.get("material") or {}).get("status")
    if st in OBSERVED_STATUS and not out.get("observed"):
        raise Reject(f"{nid}: status={st} なのに観測した値（observed）が 1 つも無い——動かして観測した経路と値を observed に書け。"
                     "動かせなかったなら awaiting_human（何を待つか）か not_run（なぜ飛ばしたか）")


def external_rankings(nid, out):
    """元 rules:2973。外部標準照合の順位の行: 差分が乗る選択肢（diff_at）は ranked のどれかで、最上位でないなら上位を採れない理由が要る"""
    errs = []
    if not out.get("rankings") and blank(out.get("rankings_none"), 10):
        errs.append("rankings が空なのに rankings_none（順位を付けられる一般化した問題が無い理由）が無い——空の順位で clean を名乗らせない")
    for i, r in enumerate(out.get("rankings") or []):
        if r["diff_at"] not in r["ranked"]:
            errs.append(f"rankings[{i}] の diff_at '{r['diff_at'][:40]}' が ranked に無い——一次情報が推す選択肢のどれに乗るかを、ranked の綴りのまま書け")
        elif r["diff_at"] != r["ranked"][0] and blank(r.get("why_not_higher"), 10):
            errs.append(f"rankings[{i}]: 差分は最上位（{r['ranked'][0][:40]}）でなく '{r['diff_at'][:40]}' に乗るのに、上位を採れない理由（why_not_higher）が無い")
    if errs:
        raise Reject(f"{nid}: " + "; ".join(errs))


def _unproven(arms):
    """元 rules:693。覆いの証拠にならない腕——赤・対照の緑・当たりの証拠のどれかが欠けた腕の名前"""
    return [a["arm"] for a in arms if not (a.get("red_confirmed") and a.get("control_green") and not blank(a.get("hit_evidence"), 10))]


def gate_arms_all_red(nid, out):
    """元 rules:3023。赤を見ていない腕が 1 つでも在れば clean を名乗らせない（赤は覆いの証拠にならない、の裏側）"""
    arms = out.get("arms", [])
    st = out.get("material", {}).get("status")
    if not arms and st in OBSERVED_STATUS:
        raise Reject(f"{nid}: status={st} なのに腕が 0 行——撃った腕を行にするか、撃てた腕が無いなら not_run（理由つき）で書け")
    unred = [a["arm"] for a in arms if not a.get("red_confirmed")]
    nocontrol = [a["arm"] for a in arms if not a.get("control_green")]
    nohit = [a["arm"] for a in arms if blank(a.get("hit_evidence"), 10)]
    if st != "found" and _unproven(arms) and st != "awaiting_human":
        raise Reject(f"{nid}: 赤を見ていない腕 {unred} / 壊していない写しで緑を確かめていない腕 {nocontrol} / "
                     f"守る行を通ったことを測っていない腕 {nohit} が在るのに status=clean"
                     "——未達は found（count と detail に腕を書く）、人の起動待ちなら awaiting_human（reason に何を待つか）")
    proven = [a["arm"] for a in arms if a.get("red_confirmed") and a.get("control_green") and blank(a.get("hit_evidence"), 10)]
    if proven:
        nohit = proven
        raise Reject(f"{nid}: 腕 {nohit} は赤も control の緑も見ているが、**その腕が守る行を通ったこと**を測っていない"
                     "（hit_evidence）——赤は柵の不在の検知であって、この腕がその柵に当たった証拠にならない。"
                     "分岐が書く値を一意の印に替え、その印が出力か記録に現れることを確かめて hit_evidence に書け")


def local_review_covers_lenses(nid, out, skills):
    """元 rules:3214。宣言したレンズ 1 本につき findings の行を 1 本、例外なく要求する。skills は _skills の宣言（applies つき）"""
    if not skills:
        raise Reject(f"{nid} の skills が空——数える対象が無い柵は全件合格になる。graph に宣言を書け")
    declared = [e["skill"] for e in skills]
    rows = out.get("findings") or []
    seen, errs = {}, []
    for i, row in enumerate(rows):
        name = row.get("skill", "")
        if name in seen:
            errs.append(f"findings に同じ skill の行が 2 本: {name}（1 本のレンズは 1 行にまとめろ）")
        seen[name] = row
        if name not in declared:
            errs.append(f"findings[{i}] の skill '{name}' は宣言に無い——正本は graph の skills（{declared}）。"
                        "名指しを増やしたいなら graph を直せ（役が勝手に増やした名前は数えられない）")
    for name in declared:
        row = seen.get(name)
        if row is None:
            errs.append(f"宣言した '{name}' の行が findings に無い——起こしたなら items を、起こしていない・"
                        "非該当なら items を空にして failed に理由を書け。**行を省くな**（省けるなら、"
                        "未起動が所見ゼロと同じ形で通っていた元の穴に戻る）")
        elif not row.get("items") and not (row.get("failed") or "").strip():
            errs.append(f"'{name}' の行が items も failed も持たない——『起こして 0 件』なら failed に"
                        "『起こしたが所見なし』と何を見たかを書け。空の行は『起こしていない』と区別できない")
    awaiting = (out.get("material") or {}).get("status") == "awaiting_human"
    for e in skills:
        row = seen.get(e["skill"])
        if row is None or "applies_cond" not in e or not e.get("applies", True) or awaiting:
            continue
        if row.get("invoked") is not True:
            errs.append(f"'{e['skill']}' は条件 {e['applies_cond']} が真の周（{e.get('applies_why', '評価の値が無いので当てる側に倒した')}）"
                        "なのに invoked が true でない——起こして invoked: true を書け。呼び出しが落ちたなら failed に理由を書き、"
                        "material を awaiting_human にせよ")
    if errs:
        raise Reject("宣言したレンズと findings の行が合わない:\n" + "\n".join("  - " + e for e in errs))


def _repo_root():
    """元 rules:3297。対象リポジトリのルート（engine.util の git の向き先。accept.in_repo で向ける）"""
    return repo_root(git)


def _grep_count(cite_, rev):
    """元 rules:3372。固めた版に対する `git grep -F -cI`（字面として数える）。（`…:数` の文字列, ""）か（None, 理由）"""
    root = _repo_root()
    if root is None:
        return None, "git が動かない"
    return grep(["git", "grep", "-F", "-cI", "-e", cite_, rev, "--", ":(top)"], root)


def _in_version(rels):
    """元 rules:3395。指し先の候補を版の一覧で引く——{rel: "text" | "binary"}（無い rel は入らない）。git が動かなければ None"""
    got = git("ls-files", "-z", "--full-name", "--cached", "--others", "--exclude-standard", "--eol",
              "--", *[f":(top,literal){r}" for r in rels])
    if got is None:
        return None
    want, found = set(rels), {}
    for ent in got.split("\0"):
        meta, sep, path = ent.partition("\t")
        if sep and path in want:
            found[path] = "binary" if "w/-text" in meta.split() else "text"
    return found


def _resolve_target(tgt, root):
    """元 rules:3422。役が書いたパス 1 つを、リポジトリ相対の正規形 1 つに解く ——（rel, 理由）。綴りが正規形と違えば拒む"""
    rootp = pathlib.Path(root).resolve()
    try:
        real = (rootp / tgt).resolve()
        rel = real.relative_to(rootp).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None, "リポジトリの外を指している（リポジトリ相対のパスで書け。絶対パスや '..' で外へ出る指しは受け取らない）"
    if rel != tgt:
        return None, f"正規形で書け: '{rel}'（'./' 付き・'..' で戻る綴り・symlink 経由は、指し先が 1 つに決まらない）"
    return rel, ""


def _not_in_version(full):
    """元 rules:3447。版に無いパスの、事実どおりの理由（拒否文の後半）"""
    if full.is_dir():
        return "通常のファイルでない（ディレクトリなど）——ファイルを 1 つ指せ"
    if full.exists() and not full.is_file():
        return "通常のファイルでない（FIFO・ソケットなど）——ファイルを 1 つ指せ"
    if full.exists() or full.is_symlink():
        return ("在るが版の一覧に出ない（.gitignore に当たる・綴りの大文字小文字が違う・サブモジュールの中、など）——次の周に"
                "指摘側が数える版にもコミットにも入らない指し先は、他の人の手元に存在しない。リポジトリの一覧に在る綴りの、版に入るファイルを指せ")
    return "いまの作業ツリーに無い——ファイルを 1 つ指せ（綴りを確かめるか、先に作れ）"


# 元 rules:3467
CITE_LABELS = {"findings": {"what": "指摘の根拠", "target": False},
               "wrote_refs": {"what": "修正が書いた指し", "target": True}}


def _cite_errors(jdir, nid, rows, rev, label):
    """元 rules:3471。申告された字列を、現物で数え直す ——（errs, reads）。盤面の b.dir（読了の記録の置き場）は置き場 jdir に読み替えた。
    findings（指し先を持たない）は版 rev 全体を数えて件数の申告（hits）と突き合わせ、wrote_refs（指し先を持つ）は作業ツリーの
    指し先のファイルの中だけを数える。git の向き先は呼び手が accept.in_repo で決める"""
    kind = CITE_LABELS[label]
    what = kind["what"]
    if kind["target"] and rev:
        raise ValueError(f"{label}: 指し先を持つ呼び元は作業ツリーを数える（版 {rev[:12]} を渡された）")
    if not kind["target"] and not rev:
        raise Reject(f"{nid}: {what}を数え直せない（採点する版が固まっていない）——確かめられないものを合格にはしない")
    probed = {}
    errs, reads, pend = [], [], []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errs.append((i, f"{label}[{i}]: 素の文字列は受け取らない（cite を持つ形で出せ）——"
                            "裏取りの柵が入る前の形が、数え直されないまま毎周の判定材料に載り続けていた"))
            continue
        rk = row.get("kind") if kind["target"] else "text"
        if rk not in ("file", "text"):
            errs.append((i, f"{label}[{i}]: kind が {rk!r}——file（ファイルそのものを指した）か text（ファイルの中の"
                            "セクション名・見出し・引用を指した）で書け"))
            continue
        cite_ = (row.get("cite") or "").strip()
        if rk == "text" and not cite_:
            errs.append((i, f"{label}[{i}]: cite（作業ツリーで引ける字列）が空"))
            continue
        if "\n" in cite_ or "\r" in cite_:
            errs.append((i, f"{label}[{i}]: cite に改行が入っている——" + (
                "1 行 1 件で書け（書いた指しの 1 か所を、指し先の 1 行から写す）" if kind["target"] else
                "数えは行単位の git grep なので『どれか 1 行が在れば合格』に化ける（空行を混ぜれば必ず通る。-F でも同じ）。"
                "1 行 1 件に割って出せ")))
            continue
        if "\0" in cite_ or "\0" in (row.get("target") or "") or "\0" in (row.get("where") or ""):
            errs.append((i, f"{label}[{i}]: cite / target / where に NUL が入っている"
                            "——検索語にもパスにも使えない（現物から写し直せ）"))
            continue
        if not kind["target"]:
            _count_in_version(nid, what, label, i, row, cite_, rev, probed, errs)
            continue
        tgt = (row.get("target") or "").strip()
        if not tgt:
            errs.append((i, f"{label}[{i}]: target（この指しが指しているファイル）が空"
                            "——どこを見れば在ると言えるのかを書け（柵はそのファイルの中だけを数える）"))
            continue
        if "root" not in probed:
            probed["root"] = _repo_root()
        if not probed["root"]:
            raise Reject(f"{nid}: {what}の指し先を確かめられない（リポジトリのルートを引けない——git が動かないか、"
                         "リポジトリの外で打った）——確かめられないものを合格にはしない")
        rel, why = _resolve_target(tgt, probed["root"])
        if rel is None:
            errs.append((i, f"{label}[{i}]: 指し先 '{tgt}' は{why}"))
            continue
        where = (row.get("where") or "").strip()
        if not where:
            errs.append((i, f"{label}[{i}]: where（この指しを書き込んだファイル）が空"
                            "——書いた場所が分からないと、指し先と同じファイルかを誰も見られない"))
            continue
        wrel, why = _resolve_target(where, probed["root"])
        if wrel is None:
            errs.append((i, f"{label}[{i}]: 書いた場所 '{where}' は{why}"))
            continue
        pend.append((i, rk, cite_, rel, wrel))
    if pend:
        seen = _in_version(sorted({p for _, _, _, rel, wrel in pend for p in (rel, wrel)}))
        if seen is None:
            raise Reject(f"{nid}: {what}を数え直せない（git が動かない）——確かめられないものを合格にはしない")
        cache = {}
        for i, rk, cite_, rel, wrel in pend:
            full = pathlib.Path(probed["root"]) / rel
            if rel not in seen or not full.is_file():
                errs.append((i, f"{label}[{i}]: 指し先 '{rel}' は{_not_in_version(full)}"))
                continue
            wfull = pathlib.Path(probed["root"]) / wrel
            if wrel not in seen or not wfull.is_file():
                errs.append((i, f"{label}[{i}]: 書いた場所 '{wrel}' は{_not_in_version(wfull)}"))
                continue
            data = None
            if rk == "text":
                if seen[rel] == "binary":
                    errs.append((i, f"{label}[{i}]: 指し先 '{rel}' はバイナリなので中を数えられない"
                                    "——字列で確かめられる指し先（テキスト）を指すか、ファイルそのものの指しなら kind を file にせよ"))
                    continue
                data, why = read_capped(full, READ_CAP)
                if data is None:
                    errs.append((i, f"{label}[{i}]: 指し先 '{rel}' は版には在るが、作業ツリーで数えられない（{why}）"
                                    "——消した・置き換えた指し先なら、書いた指しの方を直せ"))
                    continue
            state, hwhy = hook_evidence(pathlib.Path(jdir), str(full), cache=cache, data=data)
            reads.append({"kind": rk, "cite": cite_[:60] or None, "target": rel, "where": wrel,
                          "self": wrel == rel, "state": state, "why": hwhy})
            if rk == "text" and cite_.encode("utf-8") not in data:
                hint = "（このファイルをこの run で読んだ記録が無い——記憶で書いていないか）" if state == "absent" else ""
                errs.append((i, f"{label}[{i}]: '{cite_[:40]}' は指し先 '{rel}' の中に無い{hint}"
                                "——文書に書いた指しを指し先に在る綴りへ直し、その字列で申告し直せ（申告だけ差し替えても文書の誤りは残る）"))
    return [m for _, m in sorted(errs, key=lambda e: e[0])], reads


def _count_in_version(nid, what, label, i, row, cite_, rev, probed, errs):
    """元 rules:3612。指摘の根拠の字列を版 rev で数え、0 件・件数の申告（hits）の違いを errs に積む。数えられなければ Reject"""
    got, why = _grep_count(cite_, rev)
    if why:
        if "alive" not in probed:
            probed["alive"] = git("rev-parse", "--is-inside-work-tree") is not None
            probed["rev"] = git("rev-parse", "--verify", f"{rev}^{{commit}}") is not None
        if not probed["alive"]:
            raise Reject(f"{nid}: {what}を数え直せない（git が動かない）——確かめられないものを合格にはしない")
        if not probed["rev"]:
            raise Reject(f"{nid}: {what}を数え直せない（採点する版 {rev[:12]} を解決できない）"
                         "——版が消えた run では、数えた結果も『現物に無い』も言えない")
        raise Reject(f"{nid}: {what}を数え直せない（{why}）——確かめられないものを合格にはしない")
    hits = sum_counts(got)
    if hits is None:
        raise Reject(f"{nid}: {what}を数え直せない（git grep -c の出力が `…:数` の形でない: {got.splitlines()[:1]}）")
    if hits == 0:
        errs.append((i, f"{label}[{i}]: '{cite_[:40]}' が現物に 1 件も無い"
                        "——現物に無い字列は受け取らない（現物を開いて、在る字列で出し直せ）"))
    elif row.get("hits") != hits:
        errs.append((i, f"{label}[{i}]: '{cite_[:40]}' の件数の申告 {row.get('hits')} が数え直し {hits} と違う"))


def purpose_findings_cited(jdir, nid, out, rev):
    """元 rules:3274。指摘は、作業ツリーで引ける根拠を連れて来る（数えるのは git。数えられなければ拒む）。
    rev は周に固めた版（盤面の loop.reviewed_revision。ここは material-view.json の review_rev）"""
    rows = out.get("findings") or []
    if out.get("verdict") == "狭めている" and not rows:
        raise Reject(f"{nid}: 『狭めている』のに findings が空——**判定には作業ツリーで引ける根拠を 1 件以上付けろ**"
                     "（欠落を指摘したいなら、欠けている場所の周辺に実在する字列を cite にして、"
                     "そこに在るべき物が無いことを text に書く）")
    errs, _ = _cite_errors(jdir, nid, rows, rev, "findings")
    if errs:
        raise Reject(f"{nid}: 指摘の根拠が作業ツリーで裏取りできない: " + "; ".join(errs))


# ---------------------------------------------------------------- 受け付け（元 material.py:544 の take の書き直し）
def _status(reply) -> str:
    """元 material.py:536"""
    for k in ("material", "consistency"):
        v = reply.get(k) if isinstance(reply, dict) else None
        if isinstance(v, dict) and isinstance(v.get("status"), str):
            return v["status"]
    return ""


def _installed_plugins() -> set | None:
    """元 material.py:434。役が読む隔離した設定（env の CLAUDE_CONFIG_DIR）に入っているプラグインの名。読めなければ None"""
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    try:
        doc = read_json(pathlib.Path(cfg) / "plugins" / "installed_plugins.json") if cfg else None
    except ValueError:
        doc = None
    plugins = doc.get("plugins") if isinstance(doc, dict) else None
    return {k.split("@", 1)[0] for k in plugins} if isinstance(plugins, dict) else None


def _lens_gap(skills: list, reply: dict) -> tuple | None:
    """元 material.py:455。局所レビューの返答が必須のレンズを起こしていない・material を awaiting_human にした時の (拒みの文, 出し直さないか)。
    1 run は 1 周なので /simplify の持ち越し（元 _simplify_carry_ok。2 周目からだけ当たる）は受けない"""
    rows = {r.get("skill"): r for r in reply.get("findings") or [] if isinstance(r, dict)}
    carry_ok = False
    carried = reply.get("simplify_carried") is True and carry_ok
    missing = [e["skill"] for e in skills if e.get("required", True) and (rows.get(e["skill"]) or {}).get("invoked") is not True
               and not (e["skill"] == SIMPLIFY_LENS and carried)]
    if not missing:
        return None
    errs = [f"'{s}' は必須のレンズなのに invoked が true でない——必須のレンズを起こした行だけを受け付ける。/ で始まるレンズは Skill で、"
            "<plugin>:<役> は定義の置き場を Read で読ませた汎用の子（Agent）で起こし直せ"
            + ("（simplify_carried: true の持ち越しは、この周の頭の版が前の周の頭の版と 1 ファイルも違わない周だけ受ける。"
               + ("この周は当たる——持ち越すなら simplify_carried: true を書け）" if carry_ok else "この周は当たらない）")
               if s == SIMPLIFY_LENS else "")
            for s in missing]
    if _status(reply) == "awaiting_human":
        errs.append("必須のレンズが起きていない返答は material を awaiting_human にできない——起こし直して invoked: true を書け"
                    "（拒みが上限に届けば人に渡る）")
    installed = _installed_plugins()
    absent = sorted({s.split(":", 1)[0] for s in missing if ":" in s and not s.startswith("/")} - installed) \
        if installed is not None else []
    if absent:
        errs.append(f"隔離した設定（{os.environ.get('CLAUDE_CONFIG_DIR')}）にプラグイン {'・'.join(absent)} が入っていない——"
                    "起こし直しても毎回落ちるので出し直さずに人に渡す（dev/toolset.py で入れ直してから続ける）")
    return "宣言したレンズと findings の行が合わない:\n" + "\n".join("  - " + e for e in errs), bool(absent)


def _where_rows(node) -> list:
    """元 material.py:486。返答の中の where（文字列）と text を持つ行の全部（入れ子を辿る）"""
    if isinstance(node, list):
        return [r for x in node for r in _where_rows(x)]
    if not isinstance(node, dict):
        return []
    if isinstance(node.get("where"), str) and isinstance(node.get("text"), str):
        return [node]
    return [r for v in node.values() for r in _where_rows(v)]


def _location_problems(reply, repo) -> dict:
    """元 material.py:497。{where: [外れの文]}: 行の where の <パス>:<行> のうち、作業ツリーに在るファイルを指し、行がそのファイルに無い物"""
    root, out = pathlib.Path(repo).resolve(), {}
    for row in _where_rows(reply):
        for path, a, b in cite.where_cites(row["where"]):
            p = pathlib.Path(path)
            full = (p if p.is_absolute() else root / p).resolve() if path else root
            if not path or not full.is_file() or root not in full.parents:
                continue
            ref = f"{path}:{a}" + (f"-{b}" if b else "")
            why = cite.problem(ref, root)
            if why:
                out.setdefault(row["where"], []).append(why)
    return out


def _location_gap(jdir, role, reply, repo):
    """元 material.py:514。(拒む文か None, 受ける返答)。外れが在り、この役の拒み（rejects-<役>.json）が上限の 1 つ手前に届いて
    いなければ拒む文。届いていれば外れた行の where に LOCATION_MARK を付けて受ける（場所の言い方だけで止めない）"""
    bad = _location_problems(reply, repo)
    if not bad:
        return None, reply
    if len(rolekit.rejected(pathlib.Path(jdir), role)) < rolekit.GIVE_UP_AFTER - 1:
        return LOCATION_HEAD + ":\n" + "\n".join(f"  - {w}: {'; '.join(e)}" for w, e in bad.items()), reply
    marked = json.loads(json.dumps(reply))
    for row in _where_rows(marked):
        if row["where"] in bad:
            row["where"] += LOCATION_MARK
    return None, marked


def material_from_findings(src) -> dict:
    """元 rules:1296。役の返答（findings と seen）を素材 1 つに写す（衛生の目の writes）"""
    findings = src.get("findings", [])
    m = {"status": "found" if findings else "clean", "checked": src.get("seen", "")}
    if findings:
        m["count"] = len(findings)
        m["detail"] = " / ".join(f"{f.get('where', '')}: {f.get('text', '')}" for f in findings)
    return m


def _written_materials(nid, reply) -> dict:
    """写しの graph の節の writes のうち素材（materials.<名>・op material_from_findings）を返答から写した {素材の名: 状態}"""
    out = {}
    for w in MATERIAL_NODES[nid].get("writes", []):
        if w.get("op") == "material_from_findings":
            out[w["to"]] = material_from_findings(reply)
        elif w.get("op") == "set" and w["to"].startswith("materials."):
            got = reply.get(w["from"]) if w["from"] != "$" else reply
            if isinstance(got, dict):
                out[w["to"].split(".", 1)[1]] = got
    return out


def check_record(view: DueView, nid, mats: dict, diff_file=None) -> list:
    """元 rules:3665 の check_record のうち、今 done する節の素材の欄（status × 機械が持つ事実と、status ごとの要る欄）。
    走った節に流用（黙って通る値）は書けない・applies_cond が真で走った節の not_applicable は拒む（役の判定を受ける role_judged_na
    の時を除く。diff_file は対象差分）・
    applies_cond の無い節の not_applicable は graph が na_self_ok を宣言した時だけ"""
    errs = []
    n = MATERIAL_NODES[nid]
    ap = n.get("applies_cond")
    for mat in n.get("materials", []):
        m = mats.get(mat)
        if not m:
            errs.append(f"ノード {nid} は走ったが素材 '{mat}' が返答に無い")
            continue
        st = m.get("status")
        if st in SILENT_STATUS and st != "not_applicable":
            errs.append(f"素材 '{mat}'（ノード {nid}）は今の周に走ったのに {st}——自分で見たと主張しない値は走らなかったノードに機械が書く。今の周の判定を書け")
        if st == "not_applicable":
            if ap is not None and CONDS[ap](view)[0] and not role_judged_na(view, nid, diff_file):
                errs.append(f"素材 '{mat}'（ノード {nid}）は applies_cond が真で走ったのに not_applicable——機械が持つ事実と食い違う")
            elif ap is None and not n.get("na_self_ok"):
                errs.append(f"素材 '{mat}'（ノード {nid}）は走ったのに not_applicable——このノードは正当に名乗れるノードとして graph が"
                            "宣言していない（na_self_ok）。今の周の判定を書くか、名乗れる理由を graph に宣言しろ")
        if st not in STATUS:
            errs.append(f"素材 '{mat}' の status が不正: {st!r}")
            continue
        for f in STATUS[st].fields:
            v = m.get(f)
            if f in ("count", "from_round"):   # 元 review-record.py:351 の NUMERIC_FIELDS
                if not (isinstance(v, int) and not isinstance(v, bool)):
                    errs.append(f"素材 '{mat}'（{st}）の '{f}' は数で書け")
            elif not isinstance(v, (str, list)) or not v:
                errs.append(f"素材 '{mat}'（{st}）に '{f}' が要る（何を見たかを書け）")
    return errs


def _peers_note(jdir, role: str) -> str:
    """元 material.py:530 の _peers の名指し。material-route.json で同じ時に回すほかの役を並べた文（変えたのがこの役とは限らない）"""
    try:
        roles = (read_json(pathlib.Path(jdir) / MATERIAL_ROUTE_FILE, {}) or {}).get("roles") or {}
        peers = [r for r, d in roles.items() if r != role and d.get("run")]
    except (ValueError, AttributeError) as e:
        return f"。{MATERIAL_ROUTE_FILE} が読めない（{e}）——同じ時に回す役を名指せないが、変えたのがこの役とは限らない"
    return (f"。同じ時に回す役が他に {len(peers)} 件在る（{'・'.join(peers)}）——変えたのがこの役とは限らない" if peers else "")


def material_take(jdir, role: str, reply: dict, repo, *, keys=core_accept.TREE_KEYS) -> dict:
    """元 works/blk-material/lib/material.py:544 の take の書き直し。作業ツリーを素材の役を起こす前の姿（material-tree.json）と比べる →（局所レビューだけ）
    fork のレンズの所見が届かなかった空の行に『見ていない』の印（diverted.mark_unseen）→ 必須のレンズの起動（_lens_gap）→ 所見の場所の
    行（_location_gap）→ 写しの graph の節の post_check → 素材の欄（check_record）。通れば material-<役>.json に
    {role, reply, materials} を書く（局所レビューは見ていないレンズの控えも）。keys は作業ツリーの写しと比べる欄（_moved_since）。
    {ok, reason[, give_up]}。give_up 真は出し直しても直らない拒み（隔離した設定にレンズのプラグインが無い。元 _reject(give_up=True)）。
    拒否の数えは呼び手（rolekit.with_done）"""
    def run():
        nid = _material_node(role)
        if not isinstance(reply, dict):
            raise Reject("返答が JSON のオブジェクトでない")
        j, repo_p = pathlib.Path(jdir), pathlib.Path(repo)
        moved = _moved_since(j / MATERIAL_TREE_FILE, repo_p, keys=keys)
        if moved:
            raise Reject(f"{READONLY_MOVED}素材集めの役は対象の作業ツリー・HEAD・枝・git が無視するファイルを"
                         f"変えてはいけない（{'・'.join(moved)}）{_peers_note(j, role)}")
        start = _start_of(j)
        doc = _material_view(j, repo_p, start)
        view = due_view(start, _purpose_of(j), doc["changed_files"])
        got, lens_note = reply, None
        if nid == "p1.local_review":
            got, notes = diverted.mark_unseen(reply, _skills(view, role))
            lens_note = {"round": 1, **notes}
            gap = _lens_gap(_skills(view, role), got)
            if gap:
                why, give_up = gap
                return {"ok": False, "reason": why, "give_up": give_up}
        where_gap, got = _location_gap(j, role, got, repo_p)
        if where_gap:
            raise Reject(where_gap)
        post = MATERIAL_NODES[nid].get("post_check")
        with core_accept.in_repo(repo_p):
            if post == "main_path_observed":
                main_path_observed(nid, got)
            elif post == "external_rankings":
                external_rankings(nid, got)
            elif post == "gate_arms_all_red":
                gate_arms_all_red(nid, got)
            elif post == "local_review_covers_lenses":
                local_review_covers_lenses(nid, got, _skills(view, role))
            elif post == "purpose_findings_cited":
                purpose_findings_cited(j, nid, got, doc["review_rev"])
        mats = _written_materials(nid, got)
        errs = check_record(view, nid, mats, doc["diff_file"])
        if errs:
            raise Reject("素材の欄が記録の決まりに合わない: " + "; ".join(errs))
        write_json(j / f"material-{role}.json", {"role": role, "reply": got, "materials": mats})
        if lens_note is not None:   # 受け付けが通った返答の分だけ
            write_json(j / diverted.LENS_FILE, lens_note)
        return {"ok": True, "reason": ""}
    return core_accept.guard(run)


# ---------------------------------------------------------------- 素材の 15 欄（元 rules:1705 の fill_materials の書き直し）
def _accepted(jdir) -> dict:
    """置き場の material-<役>.json（受けた返答と素材。並行 PR の material-pr-check.json も）を 役 → 中身 で"""
    out = {}
    for p in sorted(pathlib.Path(jdir).glob("material-*.json")):
        if p.name in (MATERIAL_VIEW_FILE, MATERIAL_ROUTE_FILE):
            continue
        try:
            doc = read_json(p)
        except ValueError:
            continue
        if isinstance(doc, dict) and isinstance(doc.get("materials"), dict):
            out[str(doc.get("role") or p.stem.removeprefix("material-"))] = doc
    return out


def baseline_local_checks(path) -> dict:
    """素材 local_checks（元の p0.local_checks。修正前の CI の素材）を、入力 baseline の先（test-gate の base が
    baseline_red.write_baseline で書いた直す前の結末）の material から写す。修正前のテストが通れば clean、赤なら found。
    結末が読めない・素材の形が違えば not_run と理由"""
    try:
        m = baseline_red.read_baseline(path).get("material")
    except ValueError as e:
        return {"status": "not_run", "reason": f"直す前の結末が読めない: {e}"}
    rule = STATUS.get(m.get("status")) if isinstance(m, dict) else None
    if rule is None or any(k not in m for k in rule.fields):
        return {"status": "not_run", "reason": f"直す前の結末（{path}）の素材 material の形が違う: {json.dumps(m, ensure_ascii=False)[:200]}"}
    return m


def fill_materials(jdir, local_checks=None) -> dict:
    """元 rules:1705 の fill_materials の書き直し。素材の 15 欄（MATERIALS）を全部そろえて materials.json に書いて返す:
    受けた役の素材（material-<役>.json の materials）→ local_checks は渡された修正前の CI の素材（baseline_local_checks）→ 回さないと決めた役は material-route.json の埋め（入口なら not_applicable と
    入口の理由・条件外なら not_applicable・ほかは not_run）→ 回すと決めたのに受けた返答が無い役は not_run（受け付けが 3 回とも
    拒んだならその理由、ほかは走っていない）→ base_determination は基準点の決め（元 board.py:536 の base_output と同じ形）→
    fix_closure は P1 時点の not_applicable → 残りは not_run（走っていない）"""
    j = pathlib.Path(jdir)
    mats = {}
    for doc in _accepted(j).values():
        mats.update({k: v for k, v in doc["materials"].items() if isinstance(v, dict)})
    if local_checks is not None:
        mats["local_checks"] = local_checks
    route = read_json(j / MATERIAL_ROUTE_FILE, {}) or {}
    roles, fill = route.get("roles") or {}, route.get("fill") or {}
    for role, nid in MATERIAL_ROLES.items():
        for mat in MATERIAL_NODES[nid].get("materials", []):
            if mat in mats:
                continue
            rd = roles.get(role)
            if rd is None:
                mats[mat] = {"status": "not_run", "reason": f"素材集めのノード {nid} は走っていない（素材の要否を決めるノードが回していない: "
                                                            f"{route.get('reason') or '控えが無い'}）"}
            elif not rd.get("run"):
                mats[mat] = fill.get(mat) or {"status": "not_run", "reason": f"走らせる条件に当たらない（{rd.get('why', '')}）"}
            else:
                gave = rolekit.given_up_reason(j, role)
                mats[mat] = ({"status": "not_run", "reason": f"{gave}——素材集めの役の返答を受けられなかった"} if gave else
                             {"status": "not_run", "reason": f"ノード {nid} は走っていない（受け付けを通った返答が無い）"})
    view = read_json(j / MATERIAL_VIEW_FILE, {}) or {}
    if "base_determination" not in mats and view.get("base"):
        mats["base_determination"] = {"status": "found", "count": int(view.get("commits") or 0),
                                      "detail": f"{view['base']}（始めの記録の差分の根。空なら HEAD）"}
    if "fix_closure" not in mats:
        mats["fix_closure"] = {"status": "not_applicable", "reason": "P1 時点。修正は P3 でこれから行う"}
    for name in MATERIALS:
        if name not in mats:
            mats[name] = {"status": "not_run", "reason": "走っていない（どのノードも返していない）"}
    mats = {name: mats[name] for name in MATERIALS}
    write_json(j / MATERIALS_FILE, mats)
    return mats


def materials_given_up(jdir) -> list:
    """素材集めの役のうち、受け付けが 3 回とも拒んで受けた返答が無い物の諦めの理由（元 material.py:605 の collect の名指し）"""
    acc = _accepted(jdir)
    return [why for role in MATERIAL_ROLES if role not in acc for why in [rolekit.given_up_reason(pathlib.Path(jdir), role)] if why]


# ---------------------------------------------------------------- 判定役の材料（元 works/blk-judge/lib/judgebrief.py の書き直し）
START = promptsection.Section("## 入力", human="元の graphloops の判定の指示書からセクションを切り出す探し字（役の指示書には貼らない）")
END = promptsection.Section("## 手順", human="元の graphloops の判定の指示書からセクションを切り出す探し字（役の指示書には貼らない）")
LEDGER_START, LEDGER_END = "問いの台帳（questions）", "**前の周の R1 最小性"   # 問いの台帳の決まりの段
ANSWERS_HEAD = promptsection.Section("## 依頼の answers（全部。依頼者が前の run の問いに答えた物。字が問いの key か出どころに当たらない答えは、"
                                     "返答の answer_ties で問いか単位に結ぶ）", source="fn:judge_accept.answers_section")
LEDGER_HEAD = promptsection.Section("## 問いの台帳（元の graphloops の判定の指示書の同じ段。kind・status・書ける欄はここが正本）\n\n",
                                    source="fn:judge_accept.template")
BRIEF_HEAD = promptsection.Section("# 判定の材料（共有ボードから描いた物）\n\n"
                                   "元の graphloops の判定の指示書（p2.diagnose.md）の「入力」のセクションと問いの台帳の段を、この run の置き場から engine と同じ描き方で描いた物。"
                                   "値が貼ってある欄はそのまま読め。パス（対象差分・観点の正本など）は Read で読め。手順と返す JSON の形は、この役を起こした"
                                   "指示書のとおり。", source="fn:judge_accept.brief")
# 元 works/.shared/core/gl-prompts/prompts/review-loop/p2.diagnose.md の 3〜17 行（「## 入力」の節）と 35〜38 行（問いの台帳の段）を写し、
# 語だけをグラフの語にそろえた物（持ち主の決め graph-words）（間の手順と後ろの段は判定役の指示書 commands/diagnose.md が持つ）。区切りの行（「## 手順」「**前の周の R1 最小性」で
# 始まる行）は section が切る所を示すためだけに置く。元は盤面の graph の指示書のファイルを読んだ（rolekit.prompt_graph_path）
DIAGNOSE_EXCERPT = '## 入力（素材は観点名でなく欄名で並べてある。起動しなかった欄は status がそう言っている。所見が空欄なら、そのノードはこの周に走っていない——素材の status と reason を見よ）\n素材（15 欄）: {{record.materials}}\n局所の findings: {{?record.process.local_findings}}\n隔離フレームからの観察——整合性: {{?record.process.consistency_findings}} ／ 標準機構の迂回: {{?record.process.bypass_findings}} ／ 外部標準: {{?record.process.external_findings}} ／ 手順トレース: {{?record.process.procedure_findings}}\n修正依頼の入口（この周に積まれた分。バッチごとに origin が出どころ、round が積まれた周。多くは人の依頼で役の観察ではないが、仕様の道の受け入れ条件と並行 PR の見逃しも同じ入口で届き、その 2 つは 1 件ごとの本文の頭に出どころを書いてある。どれもほかの findings と同じく反証の対象——依頼の頼み方のずれも殺しにいけ）: {{?record.process.request_findings}}\nゲートの実効性確認: {{?record.process.gate_arms}} ／ 代役の忠実性: {{?out.p1.test_double_fidelity}} ／ 主経路の実行観測: {{?out.p1.main_path_observation}} ／ 根拠の出所検査: {{?out.p1.provenance}}\n先行議論の突合（決着済み論点）: {{?out.p0.prior_decisions}}\n凍結した元の目的: {{out.p0.purpose.purpose_text}}\u3000実測した制約: {{record.process.constraints}}\n目的の監査（writer が目的を自書したときの inspector の判定。「狭めている」なら目的の内側／外側の境をそのまま信用するな）: {{?record.process.purpose_review}}\n対象差分: {{loop.diff_file}}（Read せよ。`git diff {{record.base}} {{inputs.review_rev}}`——周に固めた版との差。未追跡の新規ファイルも入る）\u3000変更ファイル: {{loop.changed_files}}\u3000リポジトリ: {{inputs.cwd}}（読む版: `{{inputs.review_rev}}`）\n観点の正本: {{inputs.review_md}}（対象リポジトリ側: {{?inputs.repo_review_md}}）。ラベルと「対応の判断」「処方の最小性」「導線を作る手段の優先順位」はここが正本。\n前の周の独立の目が返したもの（この周が初めてなら「無い」と出る）——R1 最小性: {{?prev.r1.minimality | pick status,reason,ledger_audit,increments,candidates_note}}（削除候補 deletions は各行に no を振って別に貼る: {{?prev.r1.minimality.deletions}}） ／ R3 全体整合: {{?prev.r3.coherence | pick status,reason}} ／ R4 見えていない範囲: {{?prev.r4.hidden_scope | pick status,reason,capability_inventory,policy_conflicts}}（capability_inventory.lost は BASE から消えたと R4 が見た能力、policy_conflicts は人の方針とのぶつかり。どちらも人が承認ノードで決める——答えは process.human_items）\ndefer 台帳（前の周までに受容したキー。今ラウンドの判定に使うのは「同じ欠陥なら同じキー文字列を使う」ためだけ）: {{?loop.defer_ledger}}\n\n素材のどれかが明示返答（有無・または「対象外」）を欠いているなら、1〜9 に入らず materials_missing にその欄名を返せ（無言のスキップを「なし」と誤認すると見逃しが構造完備の見た目で再発する）。\n## 手順（ここから下は役を起こした指示書。材料には貼らない）\n問いの台帳（questions）: kind は——{{validator.question_kinds}}\n\n{{validator.no_open_origin}}。素材が awaiting_human なら awaiting を必ず載せろ。status は——{{validator.question_status}}。この周に立てるなら held。**問いは阻害要因を消さない**——当のユニットは [block] のまま。**書けるのは** {{validator.question_fields}} だけ。\n\n**前の周の R1 最小性（ここから下は役を起こした指示書）\n'


POLICY_HEAD = promptsection.Section("## 人の方針", source="fn:judge_accept.policy_text")


def policy_text(start) -> str:
    """人の方針の文書（始めの記録の固めた版の写し。policy.frozen_copy）の役に貼る本文。元 policy.brief のとおり PASTE_CAP バイトで
    先頭を切り、続きの置き場を末尾に書く。文書が無ければ空"""
    copy_of = policy.frozen_copy(start)
    if not copy_of or not pathlib.Path(copy_of).is_file():
        return ""
    return policy.brief(start)["paste"]


def section(text: str, start_at: str = START, end_at: str = END) -> str:
    """元 works/blk-judge/lib/judgebrief.py:60。指示書の本文から start_at で始まる行から end_at で始まる行の前まで。
    どちらかの行が無ければ ValueError（写しが替わった。元は BoardGap）"""
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.startswith(start_at)), None)
    end = next((i for i, ln in enumerate(lines) if ln.startswith(end_at)), None)
    if start is None or end is None or end <= start:
        raise ValueError(f"p2.diagnose の指示書に「{start_at}」と「{end_at}」で始まる行がこの順に無い（写しが替わった）")
    return "".join(lines[start:end]).rstrip("\n") + "\n"


def template(text: str = DIAGNOSE_EXCERPT) -> str:
    """元 works/blk-judge/lib/judgebrief.py:70。p2.diagnose の指示書の「入力」の節と問いの台帳の段（盤面の graph から引いた指示書の
    本文を引数で受ける。既定は写した DIAGNOSE_EXCERPT）"""
    return section(text) + "\n" + LEDGER_HEAD + section(text, LEDGER_START, LEDGER_END)


def answers_section(answers) -> str:
    """元 works/blk-judge/lib/judgebrief.py:77。依頼の answers（始めの記録の answers。元は gatemarks.request_answers で盤面の
    start の控えから）の全部を並べる節（無ければ ""）"""
    rows = [a for a in answers if isinstance(a, dict)] if isinstance(answers, list) else []
    if not rows:
        return ""
    return ANSWERS_HEAD + "\n\n" + "\n".join(f"- question: {json.dumps(a.get('question'), ensure_ascii=False)} → {gatemarks.answer_note(a)}"
                                             for a in rows)


def _reply_of(acc: dict, role: str):
    doc = acc.get(role)
    return doc.get("reply") if isinstance(doc, dict) else None


def _diagnose_ctx(jdir, repo, start, doc, mats, review_md, repo_review_md) -> dict:
    """判定役の「入力」の節の穴を埋める値の入れ物。元は盤面の記録（record）・節の出力（out）・周の値（loop）・入力（inputs）・
    検証器の表（validator）から engine が埋めた。無い値は入れない（省略可の穴は engine.render.ABSENT の語になる）"""
    j = pathlib.Path(jdir)
    acc = _accepted(j)
    local, cb = _reply_of(acc, "local-review") or {}, _reply_of(acc, "consistency-bypass") or {}
    ext, proc = _reply_of(acc, "external-standards") or {}, _reply_of(acc, "procedure-trace") or {}
    gate = _reply_of(acc, "gate-efficacy") or {}
    process = {
        "local_findings": local.get("findings"),
        "consistency_findings": cb.get("findings"),
        "bypass_findings": cb.get("bypass_findings"),
        "external_findings": ext.get("findings"),
        "procedure_findings": proc.get("findings"),
        "request_findings": request_batches(j, start) or None,
        "gate_arms": gate.get("arms"),
        "purpose_review": _reply_of(acc, "purpose-review"),
        "constraints": (read_json(j / _premises.PREMISES_FILE, {}) or {}).get("constraints") or [],
    }
    out = {"p0.purpose": _purpose_or_missing(j),
           "p1.test_double_fidelity": _reply_of(acc, "test-double-fidelity"),
           "p1.main_path_observation": _reply_of(acc, "main-path-observation"),
           "p1.provenance": _reply_of(acc, "provenance"),
           "p0.prior_decisions": _reply_of(acc, "prior-decisions")}
    inputs = {"cwd": str(pathlib.Path(repo).resolve()), "review_md": review_md, "review_rev": doc["review_rev"]}
    if repo_review_md:
        inputs["repo_review_md"] = repo_review_md
    return {
        "record": {"materials": mats, "base": doc["base"], "process": {k: v for k, v in process.items() if v is not None}},
        "out": {k: v for k, v in out.items() if v is not None},
        "loop": {"diff_file": doc["diff_file"], "changed_files": doc["changed_files"]},
        "inputs": inputs,
        "validator": dict(PROMPT_TABLES),
    }


def brief(jdir, repo, start: dict, review_md: str, repo_review_md: str = "") -> str:
    """元 works/blk-judge/lib/judgebrief.py:86 の brief の書き直し。判定役の材料を diagnose-brief.md に組み、パスを返す。節の並び:
    1 頭 BRIEF_HEAD・2 世界の解の行（worldmark.section。置き場の world-state.json が行を指す時）・3 p2.diagnose の「## 入力」の節を
    置き場の値で埋めた物・4 問いの台帳の段（LEDGER_HEAD。{{validator.*}} は PROMPT_TABLES）・5 依頼と PR の題と本文（始めの記録に
    input.pr が在る時。request_text と pr_file_text）・6 依頼の answers（answers_section）・7 前の run の行（入口が置いた
    prior-failures-in.json。carry.prior_section が PRIOR_HEAD の節と REDESIGN_HEAD の節に分ける）・8 人の方針（POLICY_HEAD。文書が在る時。policy_text）。素材の状態は materials.json（無ければ fill_materials）。
    対象差分は material-view.json（無ければ取る）"""
    j = pathlib.Path(jdir)
    doc = _material_view(j, repo, start)
    mats = read_json(j / MATERIALS_FILE) or fill_materials(j)
    body = Renderer(_diagnose_ctx(j, repo, start, doc, mats, review_md, repo_review_md), cap=None).render(template())
    world = worldmark.section(worldmark.stage_rows(j) or [])
    pr = _pr_of(start)
    req = ""
    if pr:
        text, _ = _request_doc(repo, start)
        req = request_text({"request_text": text, "pr": {"number": pr.get("number"), "title": pr.get("title") or "",
                                                          "body": pr.get("body") or ""}}).rstrip("\n") + "\n\n" + pr_file_text(pr)
    answers = answers_section(start.get("answers"))
    prior = carry.prior_section(j)
    pol = policy_text(start)
    p = j / DIAGNOSE_BRIEF_FILE
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(BRIEF_HEAD + "\n\n" + (f"{world}\n" if world else "") + body + (f"\n\n{req.rstrip()}\n" if req else "")
                   + (f"\n\n{answers}\n" if answers else "") + (f"\n\n{prior}\n" if prior else "")
                   + (f"\n\n{POLICY_HEAD}\n\n{pol.strip()}\n" if pol.strip() else ""), encoding="utf-8")
    os.replace(tmp, p)
    return str(p)


def prior_of(doc) -> list:
    """入力 prior_failures の先の JSON（今の works の prior-failures-in.json の形の行の並びか、依頼の容器の形）の行 [{where, text}]。
    無ければ空。形が違えば ValueError（carry.parts）"""
    if doc is None:
        return []
    return list(doc) if isinstance(doc, list) else carry.parts(doc)[carry.PRIOR]


def diagnose_prep(jdir, repo, start: dict, objection: str, review_md: str, repo_review_md: str = "", baseline=None) -> dict:
    """判定役を起こす前の支度（元 judgebrief.brief の入口と、元 blk-material の collect の止め）。返り
    {go, brief_file, review_md, repo_review_md, reason}。入力 objection が空でない（再審の道）・止めの控えが在れば組まずに go 偽。
    対象差分を取り直して diff.patch に、素材の 15 欄を materials.json に書き（baseline は入力 baseline の先のパス。在れば素材
    local_checks をそこから写す。baseline_local_checks）、材料を組み、役を起こす前の作業ツリーの姿を
    diagnose-tree.json に置く。素材の役が 1 本でも諦めていれば、
    残りの素材で材料を組んだ上で止めの控え（MATERIAL_STOP）を置いて go 偽（今の works の素材集めの諦めが判定の前で線を止めたのと同じ）"""
    j = pathlib.Path(jdir)
    out = {"go": False, "brief_file": "", "review_md": review_md, "repo_review_md": repo_review_md, "reason": ""}
    if (objection or "").strip():
        return {**out, "reason": "再審の道（入力 objection が在る）——判定の材料は組まない"}
    stop = read_stop(j)
    if stop:
        return {**out, "reason": f"止まっている（{stop['stop_reason']}: {stop.get('reason', '')}）——判定役を起こさない"}
    try:
        _material_view(j, repo, start, retake=True)
    except Reject as e:
        return {**out, "reason": f"対象差分が取れない（{e}）——判定役を起こさない"}
    fill_materials(j, baseline_local_checks(baseline) if baseline else None)
    path = brief(j, repo, start, review_md, repo_review_md)
    snap_tree(j, DIAGNOSE_TREE_FILE, repo)
    gave = materials_given_up(j)
    if gave:
        reason = "／".join(gave)
        write_stop(j, MATERIAL_STOP, reason)
        return {**out, "brief_file": path, "reason": reason}
    return {**out, "go": True, "brief_file": path}


# ================================================================ 再審と仕様


# ---------------------------------------------------------------- 仕様の段（元 works/.shared/core/graphloops/rules/review-loop.py:3852〜4043）
# 元 review-loop.py:3860〜3866（字は元のまま）
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
SPEC_GATE_HUMAN = stopby.HUMAN + SPEC_GATE
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


def spec_take(jdir, role, reply, root, *, keys=core_accept.TREE_KEYS) -> dict:
    """仕様の役の返答を受け付ける（元 works/blk-spec/lib/specblk.py:213 の take と、写しの rules の post_check
    spec_write_output・spec_review_output・spec_revise_output）。返り {ok, reason, revise}。
    - 読むだけの役（review）は作業ツリーを、書く役の返答を受けた時に置いた写し（J/spec-snapshot-spec.review.json。元 prep が審査役を
      起こす前に置いた物）と比べ（accept.tree_moved）、変わっていれば拒む。書く役（write・revise）はテストのファイルを書くので比べない
    - 通れば返答を J/spec-<役>.json に置く（revise の spec が今の仕様になる。spec_now）。write が通ったら審査役の前の作業ツリーの写しを置く
    - revise は受けた審査の穴で spec_revise_due が真の時だけ真（直す輪を回すか）
    返答が dict でない・形が違う・役の名を知らない時も拒否として返す（投げない）。keys は審査役の写しと比べる欄（_moved_since）"""
    jdir, root = pathlib.Path(jdir), pathlib.Path(root)
    if role not in SPEC_ROLES:
        return {"ok": False, "reason": f"役 {role!r} を知らない（{' / '.join(SPEC_ROLES)}）", "revise": False}
    nid = SPEC_NODES[role]
    snap_path = jdir / specblk.snapshot_name(SPEC_NODES["review"])
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{nid}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        if role == "review":
            moved = _moved_since(snap_path, root, keys=keys)
            if moved:
                raise Reject("読むだけの役が作業ツリーを変えた: 仕様の審査は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                             "ファイルを変えてはいけない（変えた物を元に戻せ）（" + "・".join(moved) + "）")
            spec_review_output(reply)
        elif role == "write":
            spec_write_output(reply, root)
            snap = core_accept.tree_state(root)
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
        write_stop(jdir, SPEC_STOP, f"仕様が固まっていない（待ちのノード: {'・'.join(pend)}）——ループか承認ノードが回らなかった")
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
    findings} を record.process.request_findings に積んだ。ここは依頼の行の並びなので行だけを足し、出どころは各行の頭 SPEC_PROVENANCE が持つ。
    判定役の材料と目的の外の行の当て先は request_batches がこの頭で origin SPEC_ORIGIN のバッチに分ける）。
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
    - 通す語（approve・continue）: J/spec-ask.json の仕様を spec_freeze で固め、作業ツリーの姿（TREE_FILE）を取り直す
      （もう J/spec.json が在れば 2 度固めない）
    答えの形の誤り（知らない語など）は works:spec で止めて go false"""
    jdir = pathlib.Path(jdir)
    try:
        gate = specblk.parse_gate(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    except rolekit.BoardGap as e:
        write_stop(jdir, SPEC_STOP, str(e))
        return {"go": False, "reason": str(e)}
    if gate is None:
        if read_stop(jdir) is None:
            write_stop(jdir, SPEC_STOP, "仕様の承認ノードが開かなかった（仕様が固まっていない）")
        return {"go": False, "reason": read_stop(jdir)["reason"]}
    if gate["decision"] in specblk.GATE_STOP:
        note = gate["text"] if gate["text"].strip() else specblk.GATE_STOP_NOTE
        by = SPEC_GATE_REQUEST if gate["text"].strip().startswith(specblk.FLAG_BY_PREFIX) else SPEC_GATE_HUMAN
        write_stop(jdir, by, note)
        return {"go": False, "reason": f"人が承認ノードで仕様を承認しなかった: {note}"}
    if (jdir / specblk.SPEC_FILE).exists():
        return {"go": True, "reason": ""}
    asked = read_json(jdir / SPEC_ASK_FILE)
    if not isinstance(asked, dict) or not isinstance(asked.get("pending"), dict):
        why = f"{SPEC_ASK_FILE} が無い・形が違う——承認ノードに見せた仕様が無いので固められない"
        write_stop(jdir, SPEC_STOP, why)
        return {"go": False, "reason": why}
    approval = {"round": 1, "node": specblk.APPROVE, "kinds": list(asked.get("asking", {}).get("kinds") or []),
                "answer": "continue", "note": gate["text"]}
    got = spec_freeze(jdir, root, asked["pending"], approval)
    if not got["ok"]:
        why = "仕様を固められない: " + "; ".join(got["problems"])
        write_stop(jdir, SPEC_STOP, why)
        return {"go": False, "reason": why}
    snap_tree(jdir, TREE_FILE, root)   # 仕様の役が書いた受け入れテストを、後ろの読むだけの役が変えた物と数えない
    return {"go": True, "reason": ""}


# ---------------------------------------------------------------- 再審（元 works/.shared/core/rejudge.py と写しの rules の rejudge_output）
REJUDGE_NODE = "p2.rejudge"          # 写しの再審の節（元 rejudge.ROLE_OF の鍵）
REJUDGE_ROLE = "rejudge"             # 役の名（拒否の控え rejects-rejudge.json の名・差の行の pass）
REJUDGE_VERDICTS = ("採る", "退ける", "一部採る")   # 再審の役の節の output_format の verdict の enum（tests/workflows/test_judge.py が突き合わせる）
ADOPTED = REJUDGE_VERDICTS[0]                     # 異議を採る答え（最後の関所と報告が「止めずに残った異議」から外す）
REJUDGE_SETTLED = ("採る", "退ける")               # 元 rules:3210。決着して異議を降ろす答え
# 元 写しの graph の p2.rejudge の writes（to: units の pick）。再審が単位を置き換える時に残す欄で、前後の差もこの欄だけを比べる
REJUDGE_UNIT_FIELDS = ("key", "label", "disposition", "reason", "reopen_evidence")
REJUDGE_BRIEF = "brief.md"
REJUDGE_BEFORE = "units-before.json"          # 元 rejudge-units-before-<役>.json
REJUDGE_SNAPSHOT = "rejudge-snapshot.json"    # 元 rejudge.SNAPSHOT_NAME（役を起こす前の作業ツリーの姿）
REJUDGE_DIFF = report.REJUDGE_DIFF            # 元 rejudge.DIFF_NAME（名の住処は報告の定数。線の judged と報告が読む約束の隣のファイル）
REJUDGE_EXIT = report.REJUDGE_EXIT            # 元 rejudge.EXIT_NAME（再審のブロックの出口の形）
REJUDGE_REPLY = "rejudge-reply.json"          # 受けた再審の返答の並び（元 writes の append to: process.rejudge）
# 元 rejudge.py:77。修正役に貼った番号の書き方（no N・No.N・#N・N 番）。全角の数字も \d に当たる
_NUMBERS = (re.compile(r"(?<![A-Za-z])no\.?\s*(\d+)", re.IGNORECASE), re.compile(r"[#＃]\s*(\d+)"), re.compile(r"(\d+)\s*番"))
# 判定役の材料のうち、再審の役に Read させる 1 回目のファイル（在る物だけを brief に並べる）
REJUDGE_MATERIALS = (("1 回目の判定（全部の欄）", JUDGMENT_FILE), ("判定役の材料", DIAGNOSE_BRIEF_FILE),
                     ("対象差分", DIFF_FILE), ("前提の制約", PREMISES_FILE), ("凍結した目的", PURPOSE_FILE),
                     ("素材の状態", MATERIALS_FILE), ("世界の解の行", WORLD_FILE), ("仕様", SPEC_FILE),
                     ("判定の裏取り", VERIFY_FILE), ("並行 PR の外す範囲", PR_EXCLUDED_FILE))


def rejudge_output(out):
    """元 works/.shared/core/graphloops/rules/review-loop.py:3186。擦り合わせの返答: **新しい事実を自分で確かめたこと**を要求する。
    依頼者の指定の条件 1（反論は新しい事実を伴うときだけ通す）と 3（判定を確定する権限は移らない）を機械で持つ。
    1 run は 1 周なので、元の defer の台帳（前の周の defer の再浮上）は空で当てる物が無く、往復の回数の数え（loop_state）は
    再審の輪（max_iterations）と拒否の控えが持つ"""
    fact = (out.get("new_facts") or "").strip()
    if blank(fact, 20):
        raise Reject(f"{REJUDGE_NODE}: new_facts が空同然——回す側が出した事実を**自分で確かめた結果**を書け"
                     "（確かめずに採る／退けるのは、どちらも判定を都合よく使うことになる）")


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
    mats = [f"- {what}: `{pathlib.Path(jdir) / name}`" for what, name in REJUDGE_MATERIALS if (pathlib.Path(jdir) / name).is_file()]
    lines = ["# 再審の材料（同じ run の 1 回目の判定と、修正役の異議）", "",
             "## 回す側の異議", "", objection.strip(), "",
             "## 今の周のユニット", "", block(pick(judgment.get("units") or [], ["key", "label", "disposition"])), "",
             "## 今の周の台帳", "", block(questions) if questions else "無い", "",
             "## 自分の見立て（P2 で書いたもの）", "", block(diagnosis) if diagnosis else "無い", "",
             "## 1 回目の判定と材料（Read して読む）", "", *(mats or ["- 無い"]), "",
             POLICY_HEAD, "", policy_text(start).strip() or "無い", ""]
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
        snap = core_accept.tree_state(pathlib.Path(root))
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


def rejudge_take(jdir, rdir, reply, root, *, keys=core_accept.TREE_KEYS) -> dict:
    """再審の役の返答を受け付ける（元 works/.shared/core/rejudge.py:421 の take）。返り {ok, reason, verdict}。順: 作業ツリーを
    R/rejudge-snapshot.json と比べる → class_query の例で問いを試して例を外す（querytest。例は
    R/query-examples.json に足す）→ rejudge_output。拒否は {ok: False, reason}（置き場を変えない）。通れば:
    - R/judgment.json: 1 回目の判定（J/judgment.json）の units を返答の units（writes の pick: REJUDGE_UNIT_FIELDS）で置き換えた物。
      1 回目の物は上書きしない
    - R/rejudge-reply.json に受けた返答を足し（元 writes の append to: process.rejudge）、R/rejudge-diff.json に単位の前後の差を 1 行
    返答の形の誤り・支度の欠けも拒否として返す（投げない）。keys は作業ツリーの写しと比べる欄（_moved_since）"""
    jdir, rdir = pathlib.Path(jdir), pathlib.Path(rdir)
    no = {"ok": False, "verdict": ""}
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{REJUDGE_NODE}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        moved = _moved_since(rdir / REJUDGE_SNAPSHOT, root, keys=keys)
        if moved:
            raise Reject("読むだけの役が作業ツリーを変えた: 再審の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                         "ファイルを変えてはいけない（" + "・".join(moved) + "）")
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
            f"{REJUDGE_NODE} の返答を受けないまま再審のループを抜けた（ループが回らなかった）")
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


# ================================================================ 並行 PR と世界の解


PR_DOWNGRADES_FILE = prcheck.DRAFTS              # 申し送りの下書き [{pr, files, note}]（GitHub に投稿しない。報告が人に渡す）
MATERIAL_PR_FILE = f"material-{prcheck.ROLE}.json"   # 並行 PR の素材 {role, reply, materials: {parallel_pr}}
PR_LIMIT = 100   # 元 works/.shared/core/graphloops/scripts/parallel-pr.py:16 の LIMIT（gh pr list の --limit）
# 元 works/.shared/core/graphloops/rules/review-loop.py:2278
# 元 works/blk-pr/scripts/accept.py:21
NO_POST = "このラインは申し送りを投稿しない（持ち主の決定 2026-09-27）。下書きを note に書き handed_over を false にせよ: "
WORLD_FEATURE = "world"   # 元 works/.shared/core/entry.py:420 の WORLD_FEATURE（始めの記録の features_cut の世界の解の語）
WORLD_PURPOSE_FILE = "world-purpose.json"   # 元 works/darkfactory/lib/line_edge.py:141（世界の解の段の入力の目的の文 {purpose_text, means}）
WORLD_ROLES = {"world-classes": worldblk.CLASSES_ROLE, "world-judge": worldblk.JUDGE_ROLE}   # 役の名 → worldblk の控えの名


# ---------------------------------------------------------------- 並行 PR（機械の道）
def _github_repo(repo):
    """元 works/.shared/core/graphloops/rules/review-loop.py:2280 の _github_repo（と works/.shared/core/entry.py の
    github_repo_redacted の、理由の文から URL の userinfo を落とす包み）。並行 PR を引く gh -R の HOST/OWNER/REPO ——（値, 引けない
    理由）。remote の選び（upstream を先に、無ければ origin）は forge.detect、URL の読みは forge.repo_of。-R はホストまで書く
    （ghreads._repo_flag と同じ。ホストの無い名を gh は GH_HOST で解き、別のホストを読みうる）。git は対象の根 repo で引く"""
    remote = forge.detect(repo)["remote"] or "origin"
    url = forge._git(repo, "remote", "get-url", remote)
    if url is None:
        return None, f"remote '{remote}' の URL が引けない"
    got = forge.repo_of(url)
    if not got or got["kind"] != forge.GITHUB:
        return None, forge.redact(f"remote '{remote}' が GitHub でない（{url.strip()[:80]}）——同等のコマンドへの読み替えは役")
    return "/".join((got["host"], got["owner"], got["name"])), None


def _pr_files(repo, diff_base: str, wheres) -> list:
    """元 works/.shared/core/graphloops/rules/review-loop.py:2293 の _pr_files。交差を取る変更ファイルの集合。差分の根 diff_base
    から今の作業ツリーまでの変更ファイル（lib/accept.touched_files）が空（判定から入る run）なら、依頼の where の文字列に
    含まれる、追跡中のパス"""
    files = []
    if diff_base:
        try:
            files = core_accept.touched_files(pathlib.Path(repo), diff_base)
        except Reject:
            files = []
    if files:
        return files
    tracked = (forge._git(repo, "ls-files", "-z") or "").split("\0")
    return sorted({t for t in tracked if t and any(t in w for w in wheres)})


def parallel_pr_plan(repo, files, *, which=None) -> dict:
    """元 works/.shared/core/graphloops/rules/review-loop.py:2304 の parallel_pr_plan。files は交差を取る集合（_pr_files）。返り
    {fallback: 理由}（役に任せる）・{blocked: 理由}（走らせずに not_run）・{repo, head, files}（数えを走らせる）。which は gh を
    探す口（試験が差し替える）"""
    slug, why = _github_repo(repo)
    if not slug:
        return {"fallback": why}
    if not (which or shutil.which)("gh"):
        return {"fallback": "gh がこの環境に無い"}
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
        return None, why or "gh pr list の出力が配列でない"
    others = [pr for pr in prs if isinstance(pr, dict) and pr.get("headRefOid") != head]
    conflicts = []
    for pr in others:
        doc, why, _ = gh("pr", "view", str(pr.get("number")), "-R", slug, "--json", "files")
        if not isinstance(doc, dict):
            return None, why or f"gh pr view {pr.get('number')} の出力が object でない"
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
    wheres = [r["where"] for r in _requests(jdir) if isinstance(r.get("where"), str)]
    files = _pr_files(repo, start["diff_base"], wheres)
    head = (forge._git(repo, "rev-parse", "HEAD") or "").strip()
    no_forge = forge.reason(forge.detect(repo))
    if no_forge:
        result = {"reply": {"material": {"status": "not_applicable", "reason": no_forge},
                            "repo": "", "listed": 0, "truncated": False, "conflicts": []}}
    else:
        launch = parallel_pr_plan(repo, files, which=which)
        if "fallback" in launch:
            result = launch
        elif launch.get("blocked"):
            result = parallel_pr_reply(launch, None)
        else:
            got, why = parallel_pr_scan(repo, launch["repo"], launch["head"], launch["files"], gh=gh)
            result = parallel_pr_reply(launch, got, why)
    write_json(jdir / prcheck.BRIEF, {"node": prcheck.NODE, "cwd": str(repo), "base": start["diff_base"], "changed_files": files,
                                      "request_wheres": wheres, "fallback": result.get("fallback", "")})
    if "fallback" in result:
        return {"go": True, "go_role": True, "reason": result["fallback"]}
    reply = result["reply"]
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
    順: 投稿していない（check_no_post）→ 読むだけの役が作業ツリーを変えていない（入口か仕様の承認の後の写し judge/judge-tree.json と比べる）→
    素材の形 → 外す hunk（prcheck.check_excluded）。通れば外す hunk を中身の印つきで judge/pr-excluded.json に、申し送りの
    下書きを judge/pr-downgrades.json に、素材を judge/material-pr-check.json に書く。拒めば何も書かない。
    写しの schema は実行基盤が役の節の型で照らすので、ここでは素材の status だけを見る"""
    jdir, repo = pathlib.Path(jdir), pathlib.Path(repo)
    if not isinstance(reply, dict):
        return {"ok": False, "reason": "返答が JSON のオブジェクトでない"}
    posted = check_no_post(reply)
    if posted:
        return {"ok": False, "reason": NO_POST + ", ".join(posted)}
    try:
        moved = _moved_since(jdir / TREE_FILE, repo)
    except Reject as e:
        return {"ok": False, "reason": str(e)}
    head = _tree_snapshot(jdir / TREE_FILE)["head"]
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
    prcheck._write(jdir / prcheck.EXCLUDED, {"node": prcheck.NODE, "head": head, "excluded": excluded})
    write_json(jdir / PR_DOWNGRADES_FILE, prcheck_drafts(bare))
    _pr_material(jdir, bare)
    return {"ok": True, "reason": ""}


def pr_accept(jdir, raw, repo) -> dict:
    """節 pr-check-accept の中身。元 works/blk-pr/scripts/accept.py:38 の main（rolekit.main_accept に take を渡す）と
    works/blk-pr/scripts/collect.py:20 の gave_up（3 回とも拒まれたら止める。by は stopby.PR）の書き直し。返り {ok, done, reason}。
    拒否は judge/rejects-pr-check.json に積み（rolekit.with_done）、諦めた時は止めの控えを置く（write_stop）"""
    jdir = pathlib.Path(jdir)
    return accept_round(jdir, prcheck.ROLE, raw, lambda reply: prcheck_take(jdir, reply, repo),
                        on_give_up=lambda: write_stop(jdir, stopby.PR, rolekit.given_up_reason(jdir, prcheck.ROLE)))


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
        doc = read_json(jdir / PURPOSE_FILE)
    except ValueError as e:
        doc, why = None, str(e)
    else:
        why = f"{jdir / PURPOSE_FILE} が無い" if doc is None else ""
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

    def take(reply):
        try:
            if role == "world-classes":
                return worldblk.classes_accept(out, reply)
            return worldblk.judge_accept(out, reply, get or worldblk.fetch)
        except (ValueError, OSError) as e:
            return worldblk._close_round(out, inner, [f"置き場の控えが読めない: {e}"])
    return accept_round(jdir, role, raw, take, reject=lambda why: worldblk._close_round(out, inner, [why]))


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


# ================================================================ 入口と返り
START_FILE = "start.json"          # 始めの記録を既定の値で読んだ物（start_view）
INTAKE_FILE = "intake.json"        # 入口の返り {go, mode, spec, world, verify, reason}
REQUEST_FILE = "request.json"      # 依頼の行（check_request が通した物。仕様の段が受け入れ条件の行を積む）
CARRIED_FILE = "carried-constraints.json"   # 依頼が運んだ前の run の前提の検算の実測（carry.CONSTRAINTS の行。check_premises が制約に足す）
TREE_FILE = "judge-tree.json"      # 入口の時（仕様の段が在れば承認の後）の作業ツリーの姿（accept.tree_state）。並行 PR と前提の受け付けが比べる
STOP_FILE = "stop.json"            # 止めの控え {stop_reason, reason}。最初に止めた節の物だけ残す
DEFAULT_FEATURES_CUT = ["judge_verify"]   # 今の works の入口の既定（判定の裏取りは既定で切）


def start_view(doc) -> dict:
    """始めの記録（今の works の blk-entry/schemas/start.schema.json の形）を、このブロックが読む欄だけ既定の値で読んだ物。
    欄が無い時の既定は docs/design.md の「judge の出力」の入力 start の決め（request_file は input.request_file・""、policy_md は ""、
    features_cut は ["judge_verify"]、spec は input.spec・false、answers は []、gates は ""）。base_rev は修正の起点（start の時の HEAD）、
    diff_base は差分の根（startrec.diff_base。input.base.rev で、P1 の役が差分を取る起点。無ければ base_rev）。policy（固めた版）は形を問わず写し、
    読み手の policy.frozen_copy が欄の無い・壊れた記録を policy_md に倒す"""
    doc = doc if isinstance(doc, dict) else {}
    shape = doc.get("input") if isinstance(doc.get("input"), dict) else {}
    cut = doc.get("features_cut")
    return {
        "request_file": doc.get("request_file") or shape.get("request_file") or "",
        "policy_md": doc.get("policy_md") or "",
        "policy": doc.get("policy"),
        "features_cut": list(cut) if isinstance(cut, list) else list(DEFAULT_FEATURES_CUT),
        "spec": shape.get("spec") is True,
        "answers": doc.get("answers") if isinstance(doc.get("answers"), list) else [],
        "gates": doc.get("gates") if isinstance(doc.get("gates"), str) else "",
        "base_rev": doc.get("base_rev") or "",
        "diff_base": startrec.diff_base(doc),
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


VERIFY_FEATURE = "judge_verify"    # 判定の裏取りの機能の語（元 entry.py:425）


def _intake_out(go, mode="judge", *, spec=False, world=False, verify=False, reason="") -> dict:
    return {"go": go, "mode": mode, "spec": spec, "world": world, "verify": verify, "reason": reason}


def request_container(view: dict, repo):
    """始めの記録が名指す依頼のファイルを解いた容器（lib/carry.parts の形）と、そのパス。依頼のファイルが無い run は、始めの記録の
    依頼の数が 0 の時だけ空の容器。解けなければ ValueError（1 行）"""
    name = view["request_file"]
    if not name:
        if view["input"].get("requests"):
            raise ValueError(f"始めの記録は依頼の行が {view['input']['requests']} 件と言うのに依頼のファイルを名指していない")
        return carry.parts([]), None
    path = pathlib.Path(name)
    path = path if path.is_absolute() else pathlib.Path(repo) / path
    doc = read_json(path)
    if doc is None:
        raise ValueError(f"依頼のファイル {path} が無い")
    return carry.parts(doc), path


def intake(start, start_error: str, jdir, rdir, repo, objection: str, prior=None) -> dict:
    """入口の節（intake）。再審の道（objection が空でない）は判定の置き場に触らずに mode: rejudge を返す。判定の道は、始めの記録を
    既定の値で読んで置き（START_FILE）、依頼の行を型に通して置き（REQUEST_FILE。元 accept.check_request）、前の run の失敗の行
    （依頼の容器の prior_failures と、入力 prior_failures の先の JSON prior の行（prior_of））を lib/carry.place_prior で 1 度だけ置き、作業ツリーの姿を置く（TREE_FILE）。
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
        container, path = request_container(view, repo)
        rows = container["findings"]
        if rows or view["input"].get("requests"):   # 依頼の無い run 以外は空でも型に通す（元 blk-judge/scripts/intake.py 47-60 行）
            checked = check_request(rows, f"依頼のファイル {path}")
            if checked.get("ok") is not True:
                raise ValueError(checked.get("reason") or "依頼の行が型に通らない")
        write_json(jdir / REQUEST_FILE, rows)
        write_json(jdir / CARRIED_FILE, container[carry.CONSTRAINTS])
        carry.place_prior(jdir, [*container[carry.PRIOR], *prior_of(prior)])
        snap_tree(jdir, TREE_FILE, repo)
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
OUT_OF_PURPOSE_FILE = "out-of-purpose.json"
PURPOSE_REVIEW_FILE = _purpose.PURPOSE_REVIEW_FILE
PUBLIC_FILES = (PREMISES_FILE, VERIFY_FILE, PR_EXCLUDED_FILE, MATERIALS_FILE,
                PURPOSE_REVIEW_FILE)   # 判定の指し札の隣に必ず置く（ほかのブロックが名で開く）


def _empty_public(name: str):
    """公開の隣のファイルの空の形（その段が走らなかった・止めの道）"""
    return {PREMISES_FILE: lambda: {"constraints": []},
            PR_EXCLUDED_FILE: lambda: {"node": prcheck.NODE, "excluded": []},
            MATERIALS_FILE: lambda: {},
            PURPOSE_REVIEW_FILE: lambda: {}}[name]()


def _fill(path: pathlib.Path, empty) -> pathlib.Path:
    """path が無ければ空の形で置く（在る物は書き換えない）"""
    if not path.is_file():
        write_json(path, empty)
    return path


def _missing_stage(jdir: pathlib.Path, judgment) -> dict | None:
    """止めの控えが無いのに、判定の前の段の控えか受けた判定が無い時、どの段で落ちたか（段が落ちた run は控えを書く前に終わる。
    判定が在っても、前提か目的が無ければ判定の材料が欠けている）"""
    for name, by, why in ((INTAKE_FILE, REQUEST_STOP, "入口のノードが走っていない（始めの記録を読めないまま返る）"),
                          (PREMISES_FILE, stopby.PREMISES, "前提の実測を受け付けた控えが無い（前提の段が落ちた）"),
                          (PURPOSE_FILE, stopby.PURPOSE, "目的の文を受け付けた控えが無い（目的の段が落ちた）")):
        if not (jdir / name).is_file():
            return {"stop_reason": by, "reason": why}
    if judgment is None:
        return {"stop_reason": JUDGE_STOP, "reason": "受け付けを通った判定が無い（判定の段が落ちた）"}
    return None


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
    """返す節（verdict）。docs/design.md の「judge の出力」の欄をちょうど返す。止めの道でも判定と目的の指し札の先と公開の隣のファイルを
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
    if stop is None and rejudging and judgment is None:
        stop = {"stop_reason": stopby.REJUDGE, "reason": "受け付けを通った再審が無い"}
    elif stop is None and not rejudging:
        stop = _missing_stage(jdir, judgment)
    _fill(here / JUDGMENT_FILE, EMPTY_JUDGMENT)

    reason = stop["reason"] if stop else ""
    if not rejudging:
        audit = _reply_of(_accepted(jdir), "purpose-review")
        if isinstance(audit, dict):
            write_json(jdir / PURPOSE_REVIEW_FILE, audit)
    for name in PUBLIC_FILES:
        first = jdir / name
        if rejudging and first.is_file() and not (rdir / name).is_file():
            write_json(rdir / name, read_json(first))
        if name == VERIFY_FILE:
            if not (here / name).is_file():
                verify_not_run(here, reason or "判定の裏取りを回さなかった")
            continue
        _fill(here / name, _empty_public(name))

    purpose = jdir / PURPOSE_FILE
    if not purpose.is_file():
        purpose = _fill(here / PURPOSE_FILE, EMPTY_PURPOSE)
    world = jdir / WORLD_FILE if (jdir / WORLD_FILE).is_file() and worldmark.stage_rows(jdir) else None   # 行の無い段は空のファイル
    spec = jdir / SPEC_FILE if (jdir / SPEC_FILE).is_file() else None
    outside = jdir / OUT_OF_PURPOSE_FILE if (jdir / OUT_OF_PURPOSE_FILE).is_file() else None

    units = structure_units(judgment, repo, record=here / STRUCTURE_DROPPED_FILE) if stop is None else []
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
