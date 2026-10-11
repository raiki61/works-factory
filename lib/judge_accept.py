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
# ================================================================ 依頼と判定（A）の終わり


# ================================================================ 材料・前提・目的・素材（B）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 材料・前提・目的・素材（B）の終わり


# ================================================================ 再審と仕様（C）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
# ================================================================ 再審と仕様（C）の終わり


# ================================================================ 並行 PR と世界の解（W）
# （ここから下の節は持ち主ごとに分けて書く。節の境の行は消さない）
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
# ================================================================ 入口と返り（F）の終わり
