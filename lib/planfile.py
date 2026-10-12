"""計画のブロックが要る、今の works の盤面の読みの書き直し（盤面 b の代わりに値かファイルのパスを受ける）と、計画のブロックの
置き場の小道具。元の関数は名前のまま、docstring に元の <パス>:<行>（今の works の pack.json の works.commit の版の works/ から）を書く。

置き場（計画のブロックの run の置き場の plan/）: 周ごとの r<k>/（k は往復と案の直しを通して 1 から数える）と、使い回す構造の
実測の structure/<鍵>/。周のフォルダの中:
- round.json {round, mode（plan・replan）, go（役を起こすか）, why（起こさない訳）, items（形 replan で渡す項目の番号）, structure（周の節が読む構造の置き場。plan/ からの相対のパス）}
- slots.json（案に入れてよい単位の no の並び。no は 1 始まりの位置）・brief-<n>.md（修正案の役の材料）・rejects-plan.json（拒否の控え。rolekit）・
  tree.json（役を起こす前の作業ツリーの姿）・item-brief-<no>.md（形 replan で直す項目の brief）
- review/p2.plan_review.json（この周に受けた事前審査の返答の写し）
- reply.json（受け付けた返答。番号を id に戻した全体で、works の欄も決め手の欄も持つ。項目の同じさ converge.item_hash の元）
- p2.fix_plan.json（reply.json から works の欄を外した物。2 往復目からは block_answers も）・plan-fields.json（planmarks.save の形）・
  replan.json（形 replan の時。replan.TRIP_FILE の行の形）・ripple-units.json・ripple.json・trace.jsonl
- prior-failures-in.json（入力 prior_failures の行の写し。carry.PRIOR_IN_FILE）・structure/（役を起こさない周の構造の控え）

- 直す義務: is_open（元 works/.shared/core/scripts/review-record.py:624）・_owed_units（元 works/.shared/core/conflict.py:676 の owed_units_but_asked）・
  slots・plan_slots・stuck_reason・not_allowed（元 works/blk-plan/lib/planblk.py:316・:366・:407）・named（no を id に戻す）・
  fix_plan_covers_units（元 rules/review-loop.py:3077。例外の代わりに行を返す）
- 案の直し: _plan_errors（元 works/.shared/core/replan.py:478）・exists_at（元 replan.py の _start_tree）・revised_fields（元 replan.py:365）・
  replan_section（元 replan.py の _section）・item_brief（元 replan.py:291 material の brief の行。planbrief.render で組む）
- 判定の処方: prescriptions（元 works/.shared/core/planmarks.py:804）・prescription_section（元 planblk.py:356）
- 修正前の版のテスト: base_test_texts（元 works/.shared/core/writes.py:93）
- 壁打ち: converge_record（元 works/.shared/core/converge.py:214 の read と :373 の record_pass。往復の行は converge.add_pass）。
  この控えを converge の answer_gaps・splice・revise_section・filled_units に渡す
- 材料と受け付け: write_brief・prior_section・take_plan・take_replan（元 planblk の prep・prior_part・take・with_plan_fields・revise_take と
  replan の prep・_take）
- 構造の実測: structure_dir・measure（元 works/blk-structure/scripts/stage_a.py の main）・write_state（元 blk-structure/scripts/collect.py）
- 周と出口: next_round・latest・structure_key・open_round・ripple_units・ripple_items・owed_order・collect・placeholders
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import posixpath
import subprocess
import sys
import time
from datetime import datetime, timezone

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))

import accept  # noqa: E402
import carry  # noqa: E402
import concepthome  # noqa: E402
import conflict  # noqa: E402
import context  # noqa: E402
import converge  # noqa: E402
import depth  # noqa: E402
import eye  # noqa: E402
import gatemarks  # noqa: E402
import impact  # noqa: E402
import judgeverify  # noqa: E402
import libdocs  # noqa: E402
import planblk  # noqa: E402
import planbrief  # noqa: E402
import planmarks  # noqa: E402
import prcheck  # noqa: E402
import promptsection  # noqa: E402
import replan  # noqa: E402
import ripple  # noqa: E402
import rolekit  # noqa: E402
import stage_a  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402

ROLE = "plan"                      # 修正案の役の受け付けの拒否の控えの名（rolekit.rejects_path）
PLAN_DIR = "plan"                  # run の置き場の中の、このブロックの置き場
ROUND_FILE = "round.json"
SLOTS_FILE = "slots.json"
REPLY_FILE = "reply.json"
FIX_PLAN_FILE = "p2.fix_plan.json"
REVIEW_FILE = "review/p2.plan_review.json"
BRIEF_FILE = "brief-{n}.md"
REJECT_FILE = "reject-{n}.txt"
ITEM_BRIEF_FILE = "item-brief-{no}.md"   # 案の直しで直す項目の brief（planbrief.render。周の材料 BRIEF_FILE と別の名）
TREE_FILE = "tree.json"            # 修正案の役を起こす前の作業ツリーの姿（accept.tree_state。支度の節が回ごとに置き直す）
RIPPLE_UNITS_FILE = "ripple-units.json"
RIPPLE_FILE = "ripple.json"
STRUCTURE_DIR = "structure"
UNREAD_STRUCTURE = f"{STRUCTURE_DIR}/unread"
UNITS_FILE = "units.json"
SKIPPED_FILE = "skipped-units.json"
STRUCTURE_FILE = "structure.json"
DESIGN_FILE = "design.jsonl"
KEY_LEN = 12
ASKING = ("held", "escalate")      # まだ人に聞く気がある問いの status（元 review-record.py:343）
BASE_TESTS_UNREAD_OP = "writes_base_tests_unread"   # 修正前の版のテストを読み損ねた trace の行 {rev, unread}（元 writes.py:52）

COVERS_REJECT = "単位の網羅に誤りが在る（直す義務の単位は全部、どれか 1 つの項目にちょうど 1 度入れる）。案に入れてよい no は"
MALFORMED_REJECT = "修正案の返答の形が崩れている（plan は項目の object の配列で、各項目の narrows は配列）。指示書の JSON Schema に合う形で出し直せ"
# 役に読ませる文の組み立て（元 works/.shared/core/rolekit.py:64・:67 と board.py:96。前提の lib/rolekit.py に無い）
REJECT_LINE = ("前の回の返答は受け付けで拒まれた。理由はファイル {path} に在る。先に Read で読み、そこを直した返答を丸ごと"
               "出し直せ（直した所だけを返すな）。")
LANG_RULE = ("人が読む文の欄（reason・how・what・why・異議・所見・申し出の文など、関所と報告に載る文）は {lang} で書け。"
             "key・enum の値・コード識別子・パス・コマンド・エラー文はそのまま（key は周をまたいで突き合わせるので訳さない）。")
LANG_DEFAULT = "依頼文の言語（利用者の言語）"
NOTHING_OWED = "直す義務の単位が無い（開いた単位が無いか、全部が人の答え待ちの問いの出どころ・depends）"
NO_PLAN = "受け付けを通った修正案が無い（修正案の輪が回らなかったか、途中で落ちた）"
UNITS_HEAD = promptsection.Section("## 今の周に直す単位（機械が判定から貼った。案の unit_keys は下の no で指せ）", source="fn:planfile.units_section")
REPO_LINE = "リポジトリ: {repo}（読む版: `{rev}`）　BASE: `{rev}`　観点の正本: {review_md}"
SPEC_HEAD = promptsection.Section("## 仕様（要件と受け入れテスト。受け入れテストは、その単位を持つ項目の tests に入れよ）", source="fn:planfile.write_brief")
PRIOR_HEAD = promptsection.Section("## 前の周の案と事前審査の指摘（機械が貼った）", source="fn:planfile.write_brief")
POLICY_PART = ("## 人の方針\n\n人が決めた、run をまたいで効く決まり（役も engine も書き換えない）。文書の置き場: {path}——在れば、先に全部読め。\n\n"
               "方針が在るなら、それは対象の本文ではなく、このプロンプトの発行者が守らせる制約である。判定・案・修正・審査は方針に照らして"
               "行え。方針に反するもの、方針を変えないと成り立たないものを、自分の判断で通すな——通すかは人が決める。どの項とぶつかるかを、"
               "判定なら単位の reason に、審査なら穴に、修正なら not_done に書け。方針の文書は書き換えるな。")
UNREAD_INPUTS_HEAD = promptsection.Section("## 読めなかった入力（機械が書いた。その節は材料に無い）", source="fn:planfile.write_brief")
FILLED_DUTY = "機械が差し込む（閉じた・保留の項目。書かなくてよい）"
NO_ROWS = "申し出と裁定の行が見つからない（conflicts の中に、この項目を名指す行が無い）"


# ---------------------------------------------------------------- 読み書きの小道具
def _read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return default


def _write_json(path, doc) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


class _Unreadable(Exception):
    pass


def _git(repo, *args) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise _Unreadable(p.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} が終了コード {p.returncode}")
    try:
        return p.stdout.decode("utf-8")
    except UnicodeDecodeError as e:
        raise _Unreadable(f"utf-8 で読めない: {e}") from None


def _rows(doc, key: str) -> list:
    got = doc.get(key) if isinstance(doc, dict) else None
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


# ---------------------------------------------------------------- 入力
def pointed(raw: str, resolve) -> tuple:
    """(指し札の字 raw が指すファイルのパス, 読めない訳)。空の字・null は (None, "")。resolve は指し札をパスに戻す口"""
    if raw is None or raw.strip() in ("", "null"):
        return None, ""
    try:
        path = resolve(json.loads(raw))
    except (ValueError, TypeError, AttributeError, KeyError) as e:
        return None, f"指し札が読めない: {e}"
    return (path, "") if pathlib.Path(path).is_file() else (None, f"指し札の先が無い: {path}")


def read_pointed(raw: str, resolve, *, text: bool = False) -> tuple:
    """(指し札の先の JSON, 読めない訳)。text なら JSON でない中身を字のまま返す"""
    path, why = pointed(raw, resolve)
    if path is None:
        return None, why
    try:
        body = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return None, f"指し札の先が読めない: {e}"
    try:
        return json.loads(body), ""
    except ValueError as e:
        return (body, "") if text else (None, f"指し札の先が JSON でない: {e}")


def world_rows(raw: str, resolve) -> tuple:
    """(定石の行の並び, 読めない訳)。指し札が無い（null）なら ([], "")"""
    path, why = pointed(raw, resolve)
    if path is None:
        return [], why
    try:
        return worldmark.rows(str(path)), ""
    except ValueError as e:
        return [], str(e)


def units_of(raw: str):
    """単位の目録の字を値に（JSON でなければ字のまま。段 A の読みが形の誤りを言う）"""
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def read_round(round_dir) -> dict:
    """周のフォルダの round.json（無い・読めなければ、フォルダの名の番号と形 plan・役を起こさない形・構造の置き場 UNREAD_STRUCTURE）。
    structure は置き場 plan/ からの相対のパス"""
    got = _read_json(pathlib.Path(round_dir) / ROUND_FILE, {})
    name = pathlib.Path(round_dir).name
    base = {"round": int(name[1:]) if name[:1] == "r" and name[1:].isdigit() else 1, "mode": "plan", "go": False, "why": "", "items": [],
            "structure": UNREAD_STRUCTURE}
    doc = {**base, **got} if isinstance(got, dict) else base
    if doc["mode"] not in ("plan", "replan"):
        doc["mode"] = "plan"
    if not isinstance(doc["structure"], str):
        doc["structure"] = UNREAD_STRUCTURE
    if not isinstance(doc["items"], list):
        doc["items"] = []
    return doc


def lib_section(cache, repo, judgment_file, keys, *, shared=None) -> str:
    """判定の単位のファイルが使うライブラリの文書の節（元 works/blk-plan/lib/planblk.py の lib_section。盤面の判定の出力の代わりに
    判定のファイルのパスを受ける。控えは cache の下、run をまたぐ控えは根 shared の下（None なら使わない））"""
    files, why = libdocs.unit_files(repo, judgment_file, keys) if judgment_file else ([], "判定のファイルが無い")
    text = libdocs.section(cache, repo, files, shared=shared)
    return text + (f"\n- 単位のファイルの引き: {why}" if why else "")


# ---------------------------------------------------------------- 直す義務の単位
def is_open(u) -> bool:
    """開いた単位（元 works/.shared/core/scripts/review-record.py:624 の is_open。label が block か、suggest で disposition が do-now）"""
    return u.get("label") == "block" or (u.get("label") == "suggest" and u.get("disposition") == "do-now")


def _skips(q) -> list:
    """問いの出どころと depends の単位の key（元 works/.shared/core/gatemarks.py の _skips。字でない物は読まない）"""
    depends = q.get("depends")
    return [k for k in [q.get("origin"), *(depends if isinstance(depends, list) else [])] if isinstance(k, str) and k]


def _owed_units(judgment) -> set:
    """今の周に直す義務の単位の key——開いた単位から、答えていない関所の問い（人に聞く状態の fork と、status が escalate の問い）の
    出どころ・depends を除いた物（元の works が写しの RL の _owed_units を差し替えた works/.shared/core/conflict.py:676 の
    owed_units_but_asked と、gatemarks.py:674 の asks・:1166 の withheld。判定の返答の units と questions を読む）。
    元が関所の答え（gatemarks.returned）で義務に戻す単位と、直す裁定でない裁定の単位（held_by_rulings）は、このブロックに関所の答えも
    裁定も届かないので扱わない（関所の問いは全部まだ答えていない物と読む）"""
    exempt = {k for q in _rows(judgment, "questions") if q.get("status") in ASKING
              and (q.get("kind") == "fork" or q.get("status") == "escalate") for k in _skips(q)}
    return {u["key"] for u in _rows(judgment, "units") if isinstance(u.get("key"), str) and is_open(u)} - exempt


def _units(judgment) -> dict:
    return {u["key"]: u for u in _rows(judgment, "units") if isinstance(u.get("key"), str)}


def slots(judgment) -> list:
    """案に入れてよい単位（開いた単位）の key を判定の順に。no は 1 始まりの位置（slots.json の並び）"""
    return [k for k, u in _units(judgment).items() if is_open(u)]


def plan_slots(judgment) -> tuple:
    """(必ず入れる, 入れてよい, 単位の key → 単位)（元 works/blk-plan/lib/planblk.py:316。受け付けの fix_plan_covers_units と同じ物から作る）"""
    units = _units(judgment)
    return _owed_units(judgment), {k for k, u in units.items() if is_open(u)}, units


def stuck_reason(judgment) -> str:
    """必ず入れるのに開いていない単位（plan_slots の 必ず入れる − 入れてよい）が在れば、行き止まりの理由（planblk.PLAN_STUCK・その単位の
    no と key・planblk.STUCK_WHY）。無ければ空（元 works/blk-plan/lib/planblk.py:366）"""
    owed, opened, _ = plan_slots(judgment)
    stuck = sorted(owed - opened)
    if not stuck:
        return ""
    names = slots(judgment)
    items = "・".join(f"no {names.index(k) + 1}（{k}）" if k in names else f"no の一覧に無い単位（{k}）" for k in stuck)
    return f"{planblk.PLAN_STUCK}: {items}。{planblk.STUCK_WHY}"


def _plan_keys(reply) -> list:
    rows = reply.get("plan") if isinstance(reply, dict) else None
    return [k for p in rows if isinstance(p, dict) and isinstance(p.get("unit_keys"), list)
            for k in p["unit_keys"] if isinstance(k, str)] if isinstance(rows, list) else []


def _shut(judgment, reply) -> list:
    """返答（id に戻した物）が案に入れた単位のうち、判定に在るが入れてよくも必ず入れるでもない物の key"""
    owed, opened, units = plan_slots(judgment)
    return [k for k in _plan_keys(reply) if k in units and k not in opened and k not in owed]


def not_allowed(judgment, reply) -> list:
    """修正案の返答（no を id に戻した物）が案に入れた単位のうち、受け付けが受けない物の理由の行（元 works/blk-plan/lib/planblk.py:407）"""
    units = _units(judgment)
    return [f"{k[:40]} は label={units[k].get('label')}（disposition={units[k].get('disposition', '無し')}）で直す対象でない"
            for k in _shut(judgment, reply)]


def named(reply, slot_list):
    """no の整数を slots の id に戻した返答の写し。文字列の unit_keys と slots に無い no はそのまま（網羅の照らしが知らない key と言う）"""
    got = copy.deepcopy(reply)
    for p in got.get("plan") if isinstance(got, dict) and isinstance(got.get("plan"), list) else []:
        keys = p.get("unit_keys") if isinstance(p, dict) else None
        if not isinstance(keys, list):
            continue
        for i, k in enumerate(keys):
            if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(slot_list):
                keys[i] = slot_list[k - 1]
    return got


def fix_plan_covers_units(plan, owed, opened) -> list:
    """修正案は今の周に直す単位を全部、どれか 1 つの案に入れる（元 works/.shared/core/graphloops/rules/review-loop.py:3077。
    例外の代わりに拒否の行を返す。戻せなかった no の整数も知らない key に数える）"""
    got = [k for p in plan if isinstance(p, dict) and isinstance(p.get("unit_keys"), list) for k in p["unit_keys"]]
    errs = []
    unknown = sorted({str(k) for k in got if k not in opened})   # 免除の単位（答えていない問いの出どころ・depends）は入れても入れなくてもよい
    if unknown:
        errs.append(f"今の周に直す単位に無い key {[k[:40] for k in unknown[:3]]}（写さずに、貼られた単位の no で指せ）")
    missing = sorted(set(owed) - set(got))
    if missing:
        errs.append(f"どの案にも入っていない単位 {[k[:40] for k in missing[:3]]}——直す義務の単位は全部どれかの案に入れる")
    dup = sorted({str(k) for k in got if got.count(k) > 1})
    if dup:
        errs.append(f"2 つの案に入った単位 {[k[:40] for k in dup[:3]]}——1 単位は 1 案")
    return errs


# ---------------------------------------------------------------- 判定の処方
def prescriptions(judgment) -> dict:
    """{単位の key: [処方の文]}（元 works/.shared/core/planmarks.py:804。判定の返答から。空の処方の単位は入れない）"""
    got = {}
    for u in _rows(judgment, "units"):
        if isinstance(u.get("key"), str):
            rx = [x for x in u.get("prescriptions") or [] if isinstance(x, str) and x.strip()]
            if rx:
                got[u["key"]] = rx
    return got


def prescription_section(keys, given) -> str:
    """修正案の材料に貼る、案に入れる単位 keys（並びの順）の判定の処方の節（元 works/blk-plan/lib/planblk.py:356）。処方が無ければ ""）"""
    rows = [f"{planblk.PRESCRIPTION_UNIT_HEAD.format(key=k)}\n\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(given[k], 1))
            for k in keys if k in given]
    return f"{planblk.PRESCRIPTION_HEAD}\n\n{planblk.PRESCRIPTION_ASK}\n\n" + "\n\n".join(rows) if rows else ""


# ---------------------------------------------------------------- 修正前の版
def base_test_texts(repo, rev: str) -> tuple:
    """修正前の版 rev に在ったテストの .py（名の慣習 impact.is_test の module）の中身 {パス: 中身} と、読めなかった物の並び
    （版が読めなければ ["<版>"]）（元 works/.shared/core/writes.py:93。盤面の trace の代わりに 2 つ目で返す）。
    fix の部品も同じ写しを持つ。writes.py を前提の部品にすると fix だけの部品まで連れてくるので、最後の掃除の段で 1 つにする"""
    try:
        names = _git(repo, "ls-tree", "-r", "--name-only", rev).splitlines()
    except _Unreadable:
        return {}, ["<版>"]
    out, unread = {}, []
    for path in sorted(names):
        if path.endswith(".py") and impact.is_test(path) == "module":
            try:
                out[path] = _git(repo, "show", f"{rev}:{path}")
            except _Unreadable:
                unread.append(path)
    return out, unread


def exists_at(repo, rev: str):
    """受け入れのテストの定義を版 rev の木で引く口（planmarks.gaps の exists）。版が引けなければ ValueError
    （元 works/.shared/core/replan.py の _start_tree。『分からない』を在ると・無いとに倒さない）"""
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    except _Unreadable as e:
        raise ValueError(f"修正の起点の版 {rev} が引けない: {e}") from None
    cache: dict = {}

    def exists(test_id):
        path = posixpath.normpath(str(test_id).split("::", 1)[0])
        if path not in cache:
            try:
                cache[path] = _git(repo, "show", f"{rev}:{path}")
            except _Unreadable:   # その版に無いファイル
                cache[path] = None
        return planmarks.line_in(cache[path], test_id) if cache[path] is not None else None
    return exists


# ---------------------------------------------------------------- 案の直し
def _plan_errors(rows, reply, repo, exists, tables) -> list:
    """修正案の役の直した項目の返答の誤りの行の全部（数・unit_keys の字・works の欄・構造と世界の解の行への答え・狭めない案）
    （元 works/.shared/core/replan.py:478。型の外れは役の節の output_format が先に照らす）。rows は渡した項目の行（old を持つ）"""
    plan = reply.get("plan") if isinstance(reply, dict) else None
    out = []
    if not isinstance(plan, list) or len(plan) != len(rows):
        out.append(f"plan[] は {len(rows)} 項目（貼った項目の数）")
    for i, (row, got) in enumerate(zip(rows, plan if isinstance(plan, list) else [])):
        want = row["old"].get("unit_keys")
        if not isinstance(got, dict) or got.get("unit_keys") != want:
            out.append(f"plan[{i}].unit_keys が貼った {json.dumps(want, ensure_ascii=False)} と違う（一字も変えずに写す）")
    if not replan._malformed(reply):
        out += planmarks.gaps(reply, pathlib.Path(repo), exists=exists)
        out += planmarks.structure_gaps(reply.get("plan"), tables)
        out += gatemarks.narrow_gaps(planmarks.NODE, reply)
        out += gatemarks.recommend_gaps(planmarks.NODE, reply)
    return out


def revised_fields(fields, rows, repo, *, base_tests=None) -> list:
    """直した項目（rows の行の new。決め手の欄は new_marks から戻す）を planmarks.split の欄に差し替えた項目の欄の並び
    （元 works/.shared/core/replan.py:365。盤面の控えの代わりに前の周の欄 fields を受ける。fields は書き換えない）"""
    out = copy.deepcopy(fields)
    for row in rows:
        n = row["item"]
        if isinstance(row.get("new"), dict) and 1 <= n <= len(out):
            out[n - 1] = planmarks.split({"plan": [replan.new_item(row)]}, pathlib.Path(repo), base_tests=base_tests)[1][0]
    return out


def conflict_rows(conflicts, n: int, old: dict) -> list:
    """fix の conflicts.json の行のうち、裁定が fix_plan_item で項目 n を名指す物（conflict.replan_rows）
    （元 works/.shared/core/replan.py の close が待つ行に選ぶ物）"""
    return conflict.replan_rows(_rows(conflicts, "items"), n, old.get("unit_keys"))


def item_brief(round_dir, n: int, old: dict, fields: dict, judgment, structure_dir_) -> pathlib.Path:
    """承認済みの項目 n の brief（planbrief.render。修正のブロックが項目ごとに切る物と同じ部品・同じ材料）を周のフォルダの
    ITEM_BRIEF_FILE に書く（元の修正の段の brief-<n>.md は fix の置き場に在り、このブロックは開かない）"""
    path = pathlib.Path(round_dir) / ITEM_BRIEF_FILE.format(no=n)
    path.write_text(planbrief.render(n, old, fields, _units(judgment), "", structmark.plan_section(structure_dir_)),
                    encoding="utf-8")
    return path


def replan_section(n: int, old: dict, rows: list, brief: str = "") -> str:
    """直す項目ごとの節: 番号・unit_keys（字のまま）・その項目の brief のパス・前の項目・申し出の行と裁定の文（字のまま）
    （元 works/.shared/core/replan.py の _section。盤面の食い違いの控えの代わりに fix の conflicts.json の行を受ける）"""
    lines = [replan.ITEM_HEAD.format(n=n), "",
             f"- unit_keys（この字のまま写せ）: {json.dumps(old.get('unit_keys'), ensure_ascii=False)}",
             f"- この項目の brief: {brief or '（無い）'}", "",
             replan.OLD_HEAD, "", *replan._json_block(old)]
    for i, c in enumerate(rows, 1):
        ru = c.get("ruling") or {}
        lines += ["", replan.ROW_HEAD.format(id=c.get("id") or i), "",
                  f"- 申し出の単位: {c.get('unit_key')}",
                  f"- 申し出の名指し（between）: {', '.join(map(str, c.get('between') or []))}",
                  f"- 申し出の理由（why_both_cannot_hold）: {c.get('why_both_cannot_hold')}",
                  f"- 申し出の種類（kind）: {c.get('kind') or '（無し）'}",
                  f"- 正しいと見た側（which_is_right）: {c.get('which_is_right')}",
                  f"- 裁定（{ru.get('decision')}）の文: {ru.get('text')}"]
    if not rows:
        lines += ["", NO_ROWS]
    return "\n".join(lines)


# ---------------------------------------------------------------- 壁打ち（事前審査との往復）
def _rounds(plan_dir) -> list:
    """周のフォルダ r<k> を k の順に"""
    d = pathlib.Path(plan_dir)
    got = [p for p in d.iterdir() if p.is_dir() and p.name[:1] == "r" and p.name[1:].isdigit()] if d.is_dir() else []
    return sorted(got, key=lambda p: int(p.name[1:]))


def round_no(round_dir) -> int:
    return int(pathlib.Path(round_dir).name[1:])


def converge_record(plan_dir) -> dict:
    """壁打ちの控え（converge.read の形 {round, passes, outcome, open, plan?}）を、置き場の周ごとの受け付けた案（reply.json）と
    受けた事前審査（review/p2.plan_review.json）の並びから組み直す（元 works/.shared/core/converge.py:214 の read と :373 の
    record_pass）。周 k に受けた事前審査は、それより前の一番新しい案を審査した物。案の直しの周（mode replan）は数えない"""
    doc = {"round": 0, "passes": [], "outcome": None, "open": {}}
    answers: list = []
    for d in _rounds(plan_dir):
        if read_round(d)["mode"] != "plan":
            continue
        doc["round"] = round_no(d)
        review = _read_json(d / REVIEW_FILE)
        if isinstance(review, dict) and doc.get("plan"):
            resolved = review.get(converge.RESOLVED)
            converge.add_pass(doc, review, answers=copy.deepcopy(answers),
                              resolved=resolved if isinstance(resolved, list) else [])
        reply = _read_json(d / REPLY_FILE)
        if isinstance(reply, dict) and isinstance(reply.get("plan"), list):
            doc["plan"] = converge.plan_rows(reply["plan"])
            answers = _rows(reply, converge.ANSWERS)
    return doc


# ---------------------------------------------------------------- 周
def next_round(plan_dir) -> int:
    """この置き場の次の周の番号（plan/r*/ の数 + 1。往復と案の直しを通して数える）"""
    return len(_rounds(plan_dir)) + 1


def latest(plan_dir, *, before=None):
    """受け付けた案（reply.json）の在る一番新しい周のフォルダ（before の周より前だけ。無ければ None）"""
    got = [d for d in _rounds(plan_dir) if (d / REPLY_FILE).is_file()
           and (before is None or round_no(d) < round_no(before))]
    return got[-1] if got else None


def structure_key(units, head: str) -> str:
    """構造の実測の使い回しの鍵（単位の目録と対象の HEAD の sha256 の頭 KEY_LEN 字）"""
    text = json.dumps(units, ensure_ascii=False, sort_keys=True) + "\n" + (head or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:KEY_LEN]


def open_round(plan_dir, *, ruling, judgment, review, units, repo, why: str = "") -> dict:
    """周のフォルダ r<k> を作り、round.json に周の事実を置く。形は ruling が空でなければ replan。周の中の節が読む構造の置き場
    （structure_dir。置き場からの相対のパス。役を起こさない周は周のフォルダの中の structure/ で、使い回す実測の控えに書かない）を
    ここで 1 度だけ決める。受けた review（事前審査の返答。
    形 plan の時だけ）を review/p2.plan_review.json に写す。役を起こすか（go）: plan は判定が読めて直す義務の単位が在り行き止まりが
    無い時、replan は直す元の案と渡す項目が在る時。why は呼び手が読めなかった入力の訳（在れば go は偽）。
    返りは round.json の中身と、周のフォルダの run の置き場からの相対のパス dir"""
    k = next_round(plan_dir)
    d = pathlib.Path(plan_dir) / f"r{k}"
    d.mkdir(parents=True)
    mode = "replan" if ruling else "plan"
    if mode == "plan" and isinstance(review, dict):
        _write_json(d / REVIEW_FILE, review)
    items, prev = [], None
    if not why and mode == "plan":
        why = (NOTHING_OWED if not _owed_units(judgment) else stuck_reason(judgment)) if isinstance(judgment, dict) \
            else "判定が読めない"
        if not why:
            _write_json(d / SLOTS_FILE, slots(judgment))
    elif not why:
        prev = latest(plan_dir, before=d)
        if prev is None:
            why = "直す元の承認済みの修正案が無い"
        else:
            items, why = planmarks.handed(ruling, len(_rows(_read_json(prev / REPLY_FILE), "plan")))
    structure = (f"{d.name}/{STRUCTURE_DIR}" if why
                 else structure_dir(plan_dir, units, repo, prev).relative_to(plan_dir).as_posix())
    doc = {"round": k, "mode": mode, "go": not why, "why": why, "items": items, "structure": structure}
    _write_json(d / ROUND_FILE, doc)
    return {**doc, "dir": f"{PLAN_DIR}/{d.name}"}


# ---------------------------------------------------------------- 構造の実測（段 A）と構造の目の控え
def _head(repo) -> str:
    try:
        return _git(repo, "rev-parse", "HEAD").strip()
    except _Unreadable:
        return ""


def _measured_units(units) -> tuple:
    """(測る単位の目録, paths が空で測らない単位の id)。目録が配列でなければそのまま返し、段 A の読みが形の誤りを言う"""
    if not isinstance(units, list):
        return units, []
    rows = [u for u in units if not (isinstance(u, dict) and isinstance(u.get("paths"), list) and not u["paths"])]
    return rows, [u.get("id") for u in units if isinstance(u, dict) and u not in rows]


def structure_dir(plan_dir, units, repo, source=None) -> pathlib.Path:
    """構造の実測の置き場 structure/<鍵>/。案の直し（replan）は直す元の周のフォルダ source の round.json の structure をそのまま使う
    （修正の後の作業ツリーを鍵に入れない。直した後の構造は eyes が測る）"""
    if source is not None:
        return pathlib.Path(plan_dir) / read_round(source)["structure"]
    return pathlib.Path(plan_dir) / STRUCTURE_DIR / structure_key(_measured_units(units)[0], _head(repo))


def measure(out_dir, units, root, policy_path: str) -> dict:
    """段 A の実測（元 works/blk-structure/scripts/stage_a.py の main）。同じ鍵の控え structure-state.json が在れば測らない（reused）。
    paths の在る単位を units.json に、paths の空な単位の id を skipped-units.json に書き、単位ごとに stage_a.measure_unit で測って
    structure.json を書き、design.jsonl を 0 バイトで置き直す。落ちても structure.json の status: failed と reason に残す。
    返り {structure_file, design_file, eye（構造の目を起こすか。eye.due）, reused}"""
    out_dir = pathlib.Path(out_dir)
    structure, design = out_dir / STRUCTURE_FILE, out_dir / DESIGN_FILE
    if (out_dir / structmark.STATE_FILE).is_file():
        return {"structure_file": str(structure), "design_file": str(design), "eye": False, "reused": True}
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, skipped = _measured_units(units)
    _write_json(out_dir / UNITS_FILE, rows)
    _write_json(out_dir / SKIPPED_FILE, skipped)
    t0, started = time.monotonic(), _now()
    design.write_bytes(b"")
    (out_dir / eye.EYE_FILE).unlink(missing_ok=True)
    root = pathlib.Path(root).resolve()
    doc = {"status": "ok", "reason": "", "root": str(root), "policy_path": policy_path, "units": []}
    try:
        got = stage_a.read_units(str(out_dir / UNITS_FILE))
    except ValueError as e:
        doc.update(status="failed", reason=str(e))
    else:
        found = context.find(root)
        doc["units"] = [{**stage_a.measure_unit(u, root), "concepts": context.concepts(root, u["paths"], found)} for u in got]
        if found["reason"]:
            doc["concepts_reason"] = found["reason"]
        failed = [u["id"] for u in doc["units"] if u["status"] == "failed"]
        if failed:
            doc.update(status="failed", reason=f"実測が落ちた単位: {', '.join(failed)}")
    doc["rules"] = context.rules(root, policy_path)
    eye.stamp(doc, t0, started_at=started, finished_at=_now())
    _write_json(structure, doc)
    return {"structure_file": str(structure), "design_file": str(design), "eye": eye.due(doc), "reused": False}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _outcome(doc: dict, kept: dict) -> tuple:
    """(status, reason)（元 works/blk-structure/scripts/collect.py の outcome。輪の出口の代わりに目の控え eye.json を読む）"""
    if doc.get("status") != "ok":
        return "failed", f"実測が落ちた: {doc.get('reason') or '理由の記録が無い'}"
    if not eye.due(doc):
        return "ok", ""
    if kept.get("status") == "ok":
        return "ok", ""
    if kept.get("status") == "gave_up":
        return "failed", f"構造の目の返答が {kept.get('attempt') or '?'} 回とも受け付けで拒まれた: {kept.get('reason') or ''}"
    return "failed", "構造の目の会話が落ちたか走らなかった（目の受け付けの控えが無いか途中のまま）"


def write_state(out_dir, *, skipped: str = "") -> pathlib.Path:
    """構造の目の控え structure-state.json（structmark の形）。在れば書き直さない（使い回し）。structure.json が読めなければ failed。
    skipped（役を起こさない周の訳）が在れば測らなかった周として failed とその訳（design.jsonl は 0 バイトで置く）"""
    out_dir = pathlib.Path(out_dir)
    state = out_dir / structmark.STATE_FILE
    if state.is_file():
        return state
    if skipped:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / DESIGN_FILE).write_bytes(b"")
        return structmark.write(out_dir, status="failed", reason=f"役を起こさない周で、構造を測らなかった: {skipped}",
                                design_file=str(out_dir / DESIGN_FILE), wall_s=0)
    doc = _read_json(out_dir / STRUCTURE_FILE)
    kept = eye.state(out_dir)
    if isinstance(doc, dict):
        status, reason = _outcome(doc, kept)
    else:
        status, reason = "failed", f"段 A の {STRUCTURE_FILE} が読めない"
    return structmark.write(out_dir, status=status, reason=reason, design_file=str(out_dir / DESIGN_FILE),
                            wall_s=round(eye.wall(doc) + eye.wall(kept), 3))


def answer_tables(structure_dir_, world_rows) -> list:
    """構造と世界の解の行の答えの要る表（今の works の planrange.answer_tables と同じ表を structmark と worldmark から組む）"""
    return [planmarks.design_need(structmark.dirty(structure_dir_)), worldmark.need(world_rows or [])]


# ---------------------------------------------------------------- 材料
def compose(parts, *, reject_file: str = "") -> str:
    """役に読ませる材料の組み立て（元 works/.shared/core/rolekit.py の compose）: 空でない部分を空行 1 つで繋ぐ。reject_file が
    在れば 1 行目でそのパスを名指す（理由の文そのものは貼らない）"""
    out = [REJECT_LINE.format(path=reject_file)] if reject_file else []
    return "\n\n".join(out + [s for s in parts if s])


def lang_line(lang) -> str:
    """役に言語を縛る 1 行（元 works/.shared/core/rolekit.py の lang_line。言語は始めの記録の lang）"""
    return LANG_RULE.format(lang=str(lang or "").strip() or LANG_DEFAULT)


def _dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False)


def units_section(judgment, units, skipped, filled=()) -> str:
    """修正案の材料に貼る、案に入れる単位の no と、判定の単位・問いの台帳・見立て・先行例（元の指示書 p2.fix_plan.md の頭の雛形の
    字を、単位の目録 units の paths・summary と構造の目が見ていない単位 skipped つきで機械が描いた物）。filled（filled_units）の
    単位は『必ず案に入れる』から外し、機械が差し込む no の行に分ける（元 works/blk-plan/lib/planblk.py:328 の plan_slots_section）"""
    owed, opened, all_units = plan_slots(judgment)
    catalog = {u.get("id"): u for u in units if isinstance(u, dict)} if isinstance(units, list) else {}
    names = slots(judgment)
    lines = [UNITS_HEAD, ""]
    for n, k in enumerate(names, 1):
        u, c = all_units[k], catalog.get(k) or {}
        duty = (FILLED_DUTY if k in filled else "必ず案に入れる" if k in owed
                else "入れてもよい（人の答え待ちの問いの出どころ・depends。入れなくてもよい）")
        lines.append(f"- no {n} `{k}`: label={u.get('label')}・disposition={u.get('disposition', '無し')}・{duty}")
        if c.get("paths"):
            lines.append(f"  - paths: {', '.join(map(str, c['paths']))}")
        if c.get("summary"):
            lines.append(f"  - summary: {c['summary']}")
    if filled:
        lines.append(f"- 機械が差し込む no（閉じた・保留の項目。書かなくてよい）: {sorted(names.index(k) + 1 for k in set(filled) if k in names)}")
    shut = [f"`{k}`（label={u.get('label')}・disposition={u.get('disposition', '無し')}）"
            for k, u in all_units.items() if k not in opened]
    lines.append(f"- 入れてはいけない単位（受け付けが拒む）: {'、'.join(shut) or '無し'}")
    if skipped:
        lines.append(f"- 構造の目が見ていない単位（paths が空で実測しなかった）: {'、'.join(f'`{k}`' for k in skipped)}")
    questions = [{k: q.get(k) for k in ("key", "kind", "status", "origin", "depends") if k in q}
                 for q in _rows(judgment, "questions")]
    if questions:
        lines += ["", "問いの台帳（fork の出どころ・depends に挙がった単位は待ってよい——案に入れなくてよい）: " + _dump(questions)]
    view = {k: judgment[k] for k in ("framing", "one_shot", "one_shot_closes") if k in judgment}
    if view:
        lines += ["", "判定者の見立て: " + _dump(view)]
    if judgment.get("precedents"):
        lines += ["", "判定者の先行例（世界の解）: " + _dump(judgment["precedents"])]
    return "\n".join(lines)


def _neighbor(judgment_dir, name: str) -> str:
    p = pathlib.Path(judgment_dir) / name if judgment_dir else None
    return str(p) if p is not None and p.is_file() else ""


def write_brief(round_dir, plan_dir, *, mode: str, judgment, judgment_dir, units, structure_dir_, world_rows, spec,
                repo, base_rev: str, review_md: str, lang, lib_docs: str = "", conflicts=None, policy_md: str = "",
                prior_failures=None, unread=()) -> tuple:
    """修正案の役の材料のファイル brief-<n>.md を書き、(パス, 回の番号 n) を返す。前の回の拒否が在れば、その理由を reject-<n>.txt に
    置いて頭の 1 行で名指す。両方の形に役の定義・並行 PR の外した範囲・ライブラリの文書・前の run で通らなかった物（prior_failures。
    元の planblk.prior_part）・考えの住処の地図（元は包みが旗 concept-map で足した concepthome.section）。形 plan はほかに単位と no・
    処方・構造の目の行・世界の解の行・波及の一覧・裏取りの申し送り・仕様・方針の文書の段落（policy_md が在る時。元の p2.fix_plan の
    prompt_append の policy-path.md と policy.md）・2 往復目からは前の周の案と事前審査の指摘と前の周の波及の一覧。形 replan は
    ほかに REPLAN_ASK・直す項目ごとの前の形と申し出と裁定の文だけ"""
    round_dir, plan_dir = pathlib.Path(round_dir), pathlib.Path(plan_dir)
    unread = list(unread)
    rejected = rolekit.rejected(round_dir, ROLE)
    n = len(rejected) + 1
    reject_file = ""
    if rejected:
        rf = round_dir / REJECT_FILE.format(n=len(rejected))
        rf.write_text(rejected[-1], encoding="utf-8")
        reject_file = str(rf)
    head = planblk.head("plan", _neighbor(judgment_dir, prcheck.EXCLUDED), lib_docs)
    rev = base_rev or "HEAD"
    try:
        carried = prior_section(round_dir, prior_failures)
    except ValueError as e:
        carried = ""
        unread.append(f"prior_failures: {e}")
    common = [head, carried, concepthome.section(repo)]
    if mode == "replan":
        prev = latest(plan_dir, before=round_dir)
        rows = _rows(_read_json(prev / REPLY_FILE), "plan") if prev else []
        items = [i for i in read_round(round_dir)["items"] if 1 <= i <= len(rows)]
        fields = (_read_json(prev / planmarks.FIELDS_FILE, {}) if prev else {}).get("fields") or []
        parts = [*common, replan.REPLAN_ASK,
                 *(replan_section(i, rows[i - 1], conflict_rows(conflicts, i, rows[i - 1]),
                                  str(item_brief(round_dir, i, rows[i - 1], fields[i - 1] if i <= len(fields) else {},
                                                 judgment, structure_dir_)))
                   for i in items)]
    else:
        owed, opened, _ = plan_slots(judgment)
        skipped = _read_json(pathlib.Path(structure_dir_) / SKIPPED_FILE, [])
        world = worldmark.section(world_rows or [])
        doc = _read_json(round_dir / RIPPLE_UNITS_FILE)
        record = converge_record(plan_dir)
        parts = [*common, units_section(judgment, units, skipped, converge.filled_units(record)),
                 REPO_LINE.format(repo=repo, rev=rev, review_md=review_md),
                 prescription_section([k for k in slots(judgment) if k in owed | opened], prescriptions(judgment)),
                 structmark.plan_section(structure_dir_),
                 f"{world}\n{worldmark.PLAN_ASK}\n" if world else "",
                 ripple.units_section(doc) if isinstance(doc, dict) else "",
                 planblk.verify_part(_neighbor(judgment_dir, judgeverify.VERIFY_FILE)),
                 f"{SPEC_HEAD}\n\n" + "\n".join(replan._json_block(spec)) if spec is not None else "",
                 _prior_section(round_dir, plan_dir, record),
                 POLICY_PART.format(path=policy_md) if policy_md else ""]
    notes = "\n".join([UNREAD_INPUTS_HEAD, "", *(f"- {u}" for u in unread)]) if unread else ""
    path = round_dir / BRIEF_FILE.format(n=n)
    path.write_text(compose([*parts, notes, lang_line(lang)], reject_file=reject_file), encoding="utf-8")
    return path, n


def _prior_section(round_dir, plan_dir, record: dict) -> str:
    """2 往復目からの節: 前の周の案のファイル・受けた事前審査の写し・項目の状態と返した block（revise_section）・前の周の項目ごとの
    波及の一覧（元 planblk._revise_prep の ripple.section）"""
    prev = latest(plan_dir, before=round_dir)
    if prev is None:
        return ""
    review = round_dir / REVIEW_FILE
    lines = [PRIOR_HEAD, "",
             f"- 前の周の案: {prev / FIX_PLAN_FILE} と {prev / planmarks.FIELDS_FILE}（Read で読め。閉じた項目はこの形のまま変えない）",
             f"- 事前審査の指摘: {review}" if review.is_file() else "- 事前審査の指摘: 受けていない（読めなかったか、渡されなかった）"]
    rip = _read_json(prev / RIPPLE_FILE)
    return "\n\n".join(x for x in ("\n".join(lines), converge.revise_section(record) if review.is_file() else "",
                                    ripple.section(rip) if isinstance(rip, dict) else "") if x)


def prior_section(round_dir, rows) -> str:
    """前の run で最後まで通らなかった物の節（carry.prior_section）。行 rows（入力 prior_failures の先。無ければ None）を周のフォルダの
    carry.PRIOR_IN_FILE に約束の形を照らして置いてから読む。形が違えば ValueError"""
    if rows is None:
        return ""
    if not isinstance(rows, list):
        raise ValueError(f"{carry.PRIOR_IN_FILE} の形が違う（[{{where, text}}]）")
    carry.place_prior(round_dir, rows)
    return carry.prior_section(round_dir)


# ---------------------------------------------------------------- 受け付け
def _section(head: str, lines) -> str:
    return head + "\n" + "\n".join(f"  - {g}" for g in lines) if lines else ""


def snap_tree(round_dir, repo) -> pathlib.Path:
    """修正案の役を起こす前の作業ツリーの姿を TREE_FILE に置く（元 works/blk-plan/lib/planblk.py:1062 の snap）"""
    return _write_json(pathlib.Path(round_dir) / TREE_FILE, accept.tree_state(pathlib.Path(repo)))


def _moved(round_dir, repo) -> str:
    """役が作業ツリーを変えた・HEAD や枝を動かした訳（変えていなければ空）。起こす前の姿が無ければその訳"""
    before = _read_json(pathlib.Path(round_dir) / TREE_FILE)
    if not isinstance(before, dict):
        return planblk.NO_TREE.format(name=TREE_FILE)
    moved = accept.tree_moved(before, pathlib.Path(repo))
    return planblk.READONLY_MOVED + "；".join(moved) if moved else ""


def _save(round_dir, k: int, plan: dict, fields: list, bare: dict, *, amended=None) -> dict:
    """受けた案の控えを置く。置けなければ置いた控えを消し、置けなかった控えの名を round.json の why に残して、輪を止める返り
    {ok: False, halt: True, reason}（拒否ではない。役に出し直させず、欄の無い案で進ませない。元 planblk.with_plan_fields の BoardGap）"""
    steps = ((FIX_PLAN_FILE, lambda: _write_json(round_dir / FIX_PLAN_FILE, bare)),
             (planmarks.FIELDS_FILE, lambda: planmarks.save(round_dir, k, fields, amended=amended)),
             (REPLY_FILE, lambda: _write_json(round_dir / REPLY_FILE, plan)))
    for name, step in steps:
        try:
            step()
        except OSError as e:
            for done, _ in steps:
                (round_dir / done).unlink(missing_ok=True)
            why = f"受けた修正案の控え {name} を置けない: {e}"
            _write_json(round_dir / ROUND_FILE, {**read_round(round_dir), "why": why})
            return {"ok": False, "halt": True, "reason": why}
    return {"ok": True, "reason": ""}


def take_plan(round_dir, plan_dir, *, judgment, reply, repo, tables, base_rev: str) -> dict:
    """修正案の役の返答（形 plan）を受け付ける。役が作業ツリーを動かしていれば先にそれだけで拒む（_moved）。拒否は理由を全部 1 回で
    並べて {ok: False, reason}。通れば no を id に戻した返答を
    planmarks.split で works の欄と分け、p2.fix_plan.json・plan-fields.json・reply.json を書いて {ok: True, reason: ""}（置けなければ
    _save の halt）。2 往復目からは block_answers を外して前の往復の block への答えを照らし、閉じた・保留の項目の行を差し込んだ案の全体を照らす。
    返答から捨てた閉じた項目の行は trace に converge.DROPPED_OP で残す（元 planblk.revise_take）"""
    round_dir = pathlib.Path(round_dir)
    moved = _moved(round_dir, repo)
    if moved:
        return {"ok": False, "reason": moved}
    if replan._malformed(reply):
        return {"ok": False, "reason": MALFORMED_REJECT}
    record = converge_record(plan_dir)
    bare, answers = converge.split("plan-revise", reply)
    slot_list = _read_json(round_dir / SLOTS_FILE)
    got = named(bare, slot_list if isinstance(slot_list, list) else slots(judgment))
    whole, closed, dropped = converge.splice(record, got["plan"])
    plan = {**got, "plan": whole}
    owed, opened, _ = plan_slots(judgment)
    shut = set(_shut(judgment, plan))
    allowed = list(range(1, len(slots(judgment)) + 1))
    reasons = [
        _section(planblk.ANSWERS_REJECT, converge.answer_gaps(record, answers)),
        _section(planblk.CLOSED_REJECT, closed),
        _section(planblk.NO_NARROW_REJECT, gatemarks.narrow_gaps(planmarks.NODE, plan)),
        _section(planblk.RECOMMEND_REJECT, gatemarks.recommend_gaps(planmarks.NODE, plan)),
        _section(f"{planblk.NOT_OWED_REJECT} {allowed}。外す単位:", not_allowed(judgment, plan)),
        _section(f"{COVERS_REJECT} {allowed}:", fix_plan_covers_units(
            [{**p, "unit_keys": [k for k in p["unit_keys"] if k not in shut]} if isinstance(p.get("unit_keys"), list) else p
             for p in whole], owed, opened)),
        _section(planmarks.REJECT, planmarks.gaps(plan, pathlib.Path(repo))),
        _section(planmarks.STRUCTURE_REJECT, planmarks.structure_gaps(whole, tables)),
    ]
    reason = "\n".join(r for r in reasons if r)
    if reason:
        return {"ok": False, "reason": reason}
    texts, unread = base_test_texts(repo, base_rev or "HEAD")
    if unread:
        planmarks.append_trace(round_dir, BASE_TESTS_UNREAD_OP, rev=base_rev or "HEAD", unread=unread)
    out, fields = planmarks.split(plan, pathlib.Path(repo), base_tests=texts)
    extra = {converge.ANSWERS: answers} if record["passes"] else {}
    k = round_no(round_dir)
    saved = _save(round_dir, k, {**plan, **extra}, fields, {**out, **extra})
    if saved["ok"]:
        for item_id in dropped:
            planmarks.append_trace(round_dir, converge.DROPPED_OP, round=k, pass_=len(record["passes"]) + 1, id=item_id)
    return saved


def take_replan(round_dir, plan_dir, *, items: list, reply, repo, tables, base_rev: str) -> dict:
    """修正案の役の直した項目の返答（形 replan）を受け付ける。拒否は REPLAN_REJECT と誤りの全部。通れば replan.json（行は
    replan.TRIP_KEYS の形。contract_changed・widened は事実だけ）と、直した項目を差し替えた案の全体を p2.fix_plan.json・
    plan-fields.json（amended に直した項目の核の欄。planmarks.amend と同じ）・reply.json に書き、trace に planmarks.AMEND_OP を書く。
    作業ツリーの比べと控えを置けない時は take_plan と同じ"""
    round_dir = pathlib.Path(round_dir)
    moved = _moved(round_dir, repo)
    if moved:
        return {"ok": False, "reason": moved}
    prev = latest(plan_dir, before=round_dir)
    if prev is None:
        return {"ok": False, "reason": f"{replan.REPLAN_REJECT}\n  - 直す元の承認済みの修正案が無い"}
    old = _rows(_read_json(prev / REPLY_FILE), "plan")
    rows = [{**dict.fromkeys(replan.TRIP_KEYS), "item": n, "units": list(old[n - 1].get("unit_keys") or []),
             "old": copy.deepcopy(old[n - 1])} for n in items if 1 <= n <= len(old)]
    rev = base_rev or "HEAD"
    try:
        errs = _plan_errors(rows, reply, repo, exists_at(repo, rev), tables)
    except ValueError as e:
        errs = [str(e)]
    if errs:
        return {"ok": False, "reason": _section(replan.REPLAN_REJECT, errs)}
    for row, got in zip(rows, reply["plan"]):
        bare, marks = gatemarks.split(planmarks.NODE, {"plan": [got]})
        row["new"], row["new_marks"] = bare["plan"][0], marks[0]
        before, after = replan._bare(row["old"]), replan._bare(replan.new_item(row))
        row["contract_changed"] = planmarks.contract_diff(before, after)
        row["widened"] = planmarks.widened(before, after) if row["contract_changed"] else None
    texts, unread = base_test_texts(repo, rev)
    if unread:
        planmarks.append_trace(round_dir, BASE_TESTS_UNREAD_OP, rev=rev, unread=unread)
    kept = _read_json(prev / planmarks.FIELDS_FILE, {})
    fields = revised_fields(kept.get("fields") or [], rows, repo, base_tests=texts)
    amended = {int(n): core for n, core in (kept.get(planmarks.AMENDED_KEY) or {}).items()}
    whole = copy.deepcopy(old)
    for row in rows:
        it = replan.new_item(row)
        whole[row["item"] - 1] = it
        amended[row["item"]] = {k: it[k] for k in planmarks.CORE_KEYS if k in it}
    out, _ = planmarks.split({"plan": whole}, pathlib.Path(repo))
    k = round_no(round_dir)
    saved = _save(round_dir, k, {"plan": whole}, fields, out, amended=dict(sorted(amended.items())))
    if not saved["ok"]:
        return saved
    planmarks.append_trace(round_dir, planmarks.AMEND_OP, round=k, items=sorted(row["item"] for row in rows))
    _write_json(round_dir / replan.TRIP_FILE, {"round": k, "items": rows})
    return saved


# ---------------------------------------------------------------- 波及の一覧と出口
def ripple_units(round_dir, judgment, repo, *, skip_dirs) -> pathlib.Path:
    """案の前の波及の一覧（単位の key の名の呼び出し元と試験）を ripple-units.json に書く"""
    owed, _, _ = plan_slots(judgment)
    names = slots(judgment)
    doc = ripple.for_units(repo, names + sorted(owed - set(names)), skip_dirs=skip_dirs)
    return _write_json(pathlib.Path(round_dir) / RIPPLE_UNITS_FILE, doc)


def why_not_ready(round_dir) -> str:
    """この周に案が無い訳（役を起こさなかった訳・3 回の拒否の最後の理由・輪が回らなかった）"""
    why = read_round(round_dir)["why"]
    if why:
        return str(why)
    return rolekit.given_up_reason(pathlib.Path(round_dir), ROLE) or NO_PLAN


def accepted_fields(round_dir):
    """受け付けた案の項目の欄（無い・空なら None）"""
    round_dir = pathlib.Path(round_dir)
    if not (round_dir / REPLY_FILE).is_file():
        return None
    fields = _read_json(round_dir / planmarks.FIELDS_FILE, {}).get("fields")
    return fields if isinstance(fields, list) and fields else None


def ripple_items(round_dir, repo, *, skip_dirs) -> pathlib.Path:
    """受け付けた案の項目ごとの波及の一覧を ripple.json に書く。案が無い周は {"items": [], "error": <訳>}"""
    fields = accepted_fields(round_dir)
    doc = ripple.build(repo, fields, skip_dirs=skip_dirs) if fields else {"items": [], "error": why_not_ready(round_dir)}
    return _write_json(pathlib.Path(round_dir) / RIPPLE_FILE, doc)


def owed_order(judgment) -> list:
    """直す義務の単位の key を判定の順に（深さを決める単位。元の線の h-depth が受けた h-fix の open_units）"""
    owed = _owed_units(judgment)
    return [k for k in slots(judgment) if k in owed]


def collect(round_dir, *, unit_ids, thickness: str, checked: bool) -> dict:
    """返す節の中身 {ready, depth}。ready は受け付けた案が在る。depth は unit_ids（owed_order）の単位ごとの深さ（depth.decide_doc の並び。
    案が無ければ []）"""
    fields = accepted_fields(round_dir)
    if not fields:
        return {"ready": False, "depth": []}
    doc = depth.decide_doc(fields, list(dict.fromkeys(unit_ids)), forced=thickness, checked=checked)
    return {"ready": True, "depth": [{"unit_id": k, "depth": v["depth"], "why": "・".join(v["why"])}
                                     for k, v in doc["units"].items()]}


def _filled(path: pathlib.Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def placeholders(round_dir, structure_dir_, reason: str) -> dict:
    """返りの指し札の先（plan-fields.json・structure-state.json・ripple.json）が在って空でないようにし、置き場からの相対でない
    フルパスを {plan, structure, ripple} で返す。無い物は「無い」を表す形で書く（{round, fields: []}・status: failed・{items: [], error}）"""
    round_dir, structure_dir_ = pathlib.Path(round_dir), pathlib.Path(structure_dir_)
    round_dir.mkdir(parents=True, exist_ok=True)
    structure_dir_.mkdir(parents=True, exist_ok=True)
    why = reason or NO_PLAN
    plan, state, rip = round_dir / planmarks.FIELDS_FILE, structure_dir_ / structmark.STATE_FILE, round_dir / RIPPLE_FILE
    if not _filled(plan):
        _write_json(plan, {"round": read_round(round_dir)["round"], "fields": []})
    if not _filled(state):
        design = structure_dir_ / DESIGN_FILE
        if not design.is_file():
            design.write_bytes(b"")
        structmark.write(structure_dir_, status="failed", reason=why, design_file=str(design), wall_s=0)
    if not _filled(rip):
        _write_json(rip, {"items": [], "error": why})
    return {"plan": plan, "structure": state, "ripple": rip}
