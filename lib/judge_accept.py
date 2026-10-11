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

WORLD_FEATURE = "world"            # 世界の解の段の機能の語（元 works/.shared/core/entry.py:420 の WORLD_FEATURE）
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
JUDGMENT_FILE = "judgment.json"
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
