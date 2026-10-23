"""report の block へ渡す sections を組む（docs/design/line.md の 7.1。形は report の block の schemas/sections.schema.json）。

節は block の出力の report の欄をそのまま lines にし、見出しを line が付ける。見出しと並びは今の機械の報告の節に合わせ、今の報告に
無かった節は後ろに run の流れの順で足す。走らなかった block の節は載せない（走ったのに行が無い節は report が 1 行を置く）。judge と
eyes の graph は自分の節を sections で返すので、その見出しで引いて並べる。files（節「3. 見る所」の元。今の runreport.POINTERS の 18 個）は、
その事実を持つ節に入れる。

- build(values, record, *, cwd, folder) -> [{title, lines, files?}]
- entry_lines(values, record, *, cwd, folder) -> 節 1 の行（入口・段・決めた人）
"""
from __future__ import annotations

import json

from src import facts as factslib

ENTRY = "入口・段・決めた人"
TDD = "TDD のループの単位ごとの結末"
TDD_2 = "TDD のループの単位ごとの結末（2 度目の修正）"
GREEN = "緑の認証（全部の周）"
NOT_RUN = "走らせなかった範囲（CI と人に任せた物）"
EYES = "独立の目"
STRUCTURE = "構造の目"
WORLD = "世界の解"
LENS_LOCAL = "未確認のレンズと局所レビュー"
JUDGMENT = "判定（目的の外とした所見を含む）"
DESIGN = "独立設計"
ROUNDS = "計画の往復"
BEFORE_FIX = "修正前の承認ノード"
REVIEW_1 = "レンズと差分の審査（1 回目の段）"
REPLAN = "案の直し"
REVIEW_2 = "レンズと差分の審査（2 度目の段）"
PARALLEL_AFTER = "並行 PR（修正の後）"
REJUDGE = "再審"
SPEC_CHECK = "仕様の照らし"
MERGE = "封じた差分と置いた差分"
GROUPS = "模型の群の選び"
LENS_NOT_DUE = "差分の審査を回さないのでレンズは起こさない（{why}）"   # 今の fixboard.LENS_NOT_DUE
# judge の graph の節の見出し（judge の graph の src/verdict.py の TITLES の値）のうち、line が名で引く物
JUDGE_WORLD = "世界の解"
JUDGE_LOCAL = "素材: 局所レビュー"
JUDGE_DIAGNOSE = "根本の診断"
SPEC_DRIVEN = "仕様駆動の道"
JUDGE_LATER = ("run の頭の深さ", "仕様", "並行 PR", "前提の実測", "目的の固定")
JUDGE_VERIFY = "判定の単位の裏取り"
EYES_AFTER = "直した後の構造の実測"


def _d(v) -> dict:
    return v if isinstance(v, dict) else {}


def _l(v) -> list:
    return v if isinstance(v, list) else []


def _lines(got) -> list:
    return [str(x) for x in _l(_d(got).get("report"))]


def _ref(ptr):
    """files の ref（pointer か絶対パスの字）。どちらでもなければ None"""
    if isinstance(ptr, dict) and ptr.get("type") == "archon_artifact":
        return ptr
    return ptr if isinstance(ptr, str) and ptr.startswith("/") else None


def _files(*pairs) -> list:
    return [{"label": label, "ref": ref} for label, ptr in pairs if (ref := _ref(ptr)) is not None]


def _section(title: str, lines: list, files=()) -> dict:
    out = {"title": title, "lines": [str(x) for x in lines]}
    if files:
        out["files"] = list(files)
    return out


def not_run_lines(base, final) -> list:
    """節「走らせなかった範囲」の行（持ち主の決め related-tests-only）: 試験の関門の base と final の返りの related から、走らせた試験・走らせ
    なかった試験・全体の試験を CI と人に任せた事・一式を走らせた理由を並べる。関わる試験に絞らない道（利用者の宣言か test_cmd）は
    走らせ方の行（suites_line。範囲の宣言で回さなかった段を含む）を並べる。直す前（base）は自己点検だけなので、その走らせ方の行だけ
    （持ち主の決め base-selfcheck-only）。走らなかった block（返りが無い）は載せない"""
    import related   # lib/
    out = []
    for label, got in (("直す前のテスト", _d(base)), ("最後のテスト", _d(final))):
        rel = _d(got.get("related"))
        if got.get("mode") == "base" and got.get("suites_line"):   # 直す前は自己点検だけ（持ち主の決め base-selfcheck-only）
            out.append(f"{label}: {got['suites_line']}")
        elif rel.get("applied") is True:
            out += [f"{label}:", *[x if x.startswith(" ") else f"  {x}" for x in related.lines(rel)]]
        elif got.get("suites_line"):
            out.append(f"{label}: {got['suites_line']}（利用者が決めた走らせ方なので、工場は絞らない。全体の試験は CI と人に任せる）")
    return out


def _by_title(got) -> dict:
    """graph の返りの sections を見出し → 行の dict に"""
    return {str(s.get("title")): [str(x) for x in _l(s.get("lines"))] for s in _l(_d(got).get("sections")) if isinstance(s, dict)}


def entry_lines(values: dict, record: dict, *, cwd, folder) -> list:
    """節 1 の行: 始めの記録の入口の文・固定材料・最後の承認ノードの開き方・段と機能・下げている所・省く物と足した物・深さの行・前の失敗・
    方針の行・直す前のテストの語・テストの凍結が効いていない組・判定の裏取りを回さなかった訳（docs/design/line.md の 7.1 の 1）"""
    start = _d(values.get("start"))
    out = [*_part("始めの記録の行", lambda: record_lines(record)), *_part("入口の文", lambda: shape_lines(record))]
    if start.get("from_fixture") is True:
        out.append(f"固定材料から始めた（判定と修正案を作り直さず、修正から）: {json.dumps(start.get('fixture'), ensure_ascii=False)}")
    out += _part("承認ノードの開き方の語", lambda: gate_words(record))
    switches = _d(_d(values.get("fix_in")).get("switches")) or _d(values.get("tiers"))
    if switches.get("tier"):
        out.append(f"run の頭の深さの段: {switches['tier']}")
    out += _part("段と機能の行", lambda: tier_lines(record, switches.get("tier") or ""))
    out += [str(x) for x in _l(switches.get("lines"))]
    out += _part("決めた人の行", lambda: decided_lines(values))
    out += _part("forge の行", lambda: forge_lines(cwd))
    out += _part("走った段の行", lambda: ran_lines(values))
    down = [r for name in ("judge", "independent_design", "rejudge", "parallel_after") for r in _l(_d(values.get(name)).get("downgrades"))
            if isinstance(r, dict)]
    if down:
        out.append(f"下げている所: {len(down)} 件")
        out += [f"  - {r.get('what')}（替わり: {r.get('versus')}）" for r in down]
    raise_ = _d(values.get("raise"))
    out += depth_lines(raise_, switches, _d(start.get("ports")), _l(_d(values.get("fixed")).get("tdd")))
    prior = start.get("prior_failures")
    if prior:
        doc, why = factslib.read_ptr(prior)
        rows = [r for r in _l(doc) if isinstance(r, dict)]
        out.append(f"依頼が運んだ前の run の失敗（prior_failures）: {len(rows)} 件" if not why else f"依頼が運んだ前の run の失敗を読めない（{why}）")
        out += [f"  - {r.get('where')}: {r.get('text')}" for r in rows]
    try:
        out += factslib.policy_lines(record, cwd, folder)
    except Exception as e:  # noqa: BLE001
        out.append(f"{factslib.POLICY_CHANGED_HEAD}か: 確かめられない（{type(e).__name__}: {e}）")
    base = _d(values.get("test_gate_base")) or _d(_d(_d(values.get("fix_in")).get("received")).get("test_gate_base"))
    if base:
        out += _part("直す前のテストの語", lambda: [f"直す前のテスト: {base_word(base)}"])
    if base.get("baseline_line"):
        out.append(str(base["baseline_line"]))
    off = [r for name in ("fix", "refix") for r in _l(_d(values.get(name)).get("freeze_off"))]
    out += [f"テストの凍結: {r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)}" for r in off]
    judge = _d(values.get("judge"))
    if judge and judge.get("verify") is None:
        out.append(f"判定の裏取りを回さなかった: {judge.get('verify_why') or '訳の記録が無い'}")
    return out


def _part(name: str, fn) -> list:
    """節 1 の行の 1 つを組む（組めなければ訳の 1 行。節は出す）"""
    try:
        return [str(x) for x in fn()]
    except Exception as e:  # noqa: BLE001
        return [f"{name}を組めない（{type(e).__name__}: {e}）"]


def record_lines(record: dict) -> list:
    """始めの記録の 1 行と固定材料の行（元 runreport._entry_lines の頭。src/fixture.py の lines）"""
    from src import fixture, gates
    s = _d(record)
    return [f"始めの記録: run {s.get('run_id') or '—'}・元の版 {s.get('base_rev') or '—'}・テストの命令 {s.get('test_cmd') or '—'}・"
            f"TDD の実行ファイル {s.get('tdd_suite') or '—'}・無人 {s.get(gates.UNATTENDED_KEY) or '—'}", *fixture.lines(s)]


def shape_lines(record: dict) -> list:
    from src import startrec
    shape = startrec.shape(record)
    if shape is None:
        return []
    try:
        return [f"入口: {startrec.words(shape)}"]
    except (KeyError, TypeError):
        return ["入口: 入口の入力の形が読めない"]


def gate_words(record: dict) -> list:
    from src import gates
    words = gates.head_words(_d(record))
    return [words] if words else []


def tier_lines(record: dict, head: str) -> list:
    """段と機能の 1 行（元 runreport._entry_lines の「段:」の行。entry.features_part）"""
    import entry
    from src import tiers
    s = _d(record)
    part = entry.features_part(s.get(entry.FEATURES_KEY) or [], entry.features_on_of(s), tiers.tier_adds(head), tiers.tier_auto(head))
    feats = f"・{part}" if entry.FEATURES_KEY in s else ""
    return [f"段: {s.get('thickness') or '自動（機械が単位ごとに決めた）'}{feats}"]


def decided_lines(values: dict) -> list:
    """決めた人: 承認ノードの答えの数と、無人の run が推しで通した承認ノードの数"""
    import answer
    answered = [g for g in factslib.gates_of(values).values() if isinstance(g, dict)]
    pushed = sum(1 for g in answered if answer.by_push(g))
    return [f"決めた人: 承認ノードの答え {len(answered) - pushed} 件" + (f"（ほかに無人の run が推しで通した承認ノード {pushed} 件）" if pushed else "")]


FORGE_HEAD = "PR を持つホスト（forge）"


def forge_lines(cwd) -> list:
    """PR を持つホストが無い時の 1 行（並行 PR の確かめは条件外。元 runreport._entry_lines の forge の行）"""
    import forge
    why = forge.reason(forge.detect(cwd)) if cwd else ""
    return [f"{FORGE_HEAD}: 無い——並行 PR の確かめは条件外（not_applicable。{why}）"] if why else []


def ran_lines(values: dict) -> list:
    """走った段と、飛ばされた・出力の無い段（include の id。受け皿の got が在るか）"""
    ran = [rid for rid, name in factslib.RETURNED if isinstance(values.get(name), dict)]
    skipped = [rid for rid, name in factslib.RETURNED if not isinstance(values.get(name), dict)]
    return [f"走った段: {'・'.join(ran) or '無い'}", f"飛ばされた・出力の無い段: {'・'.join(skipped) or '無い'}"]


def base_word(base: dict) -> str:
    """直す前のテストの語（元 runreport._base_word）"""
    import baseline_red
    import declared_checks
    import gatemarks
    import green_cert
    import oneline
    if base.get("green"):
        return "緑"
    cause = base.get("red_cause")
    if green_cert.RAN_BY_CAUSE.get(cause) == green_cert.NOT_RAN and base.get("ok") is not True:
        why = oneline.one_line(declared_checks.gate_values(base)["reason"])
        return f"走らせられなかった（{cause}）——{gatemarks.BASELINE_NOT_RUN}" + (f"——{why}" if why else "")
    if cause == green_cert.INCOMPLETE:
        material = {}
        try:
            ptr = base.get("baseline")
            if ptr:
                from src import stages
                material = _d(baseline_red.read_baseline(stages.resolve(ptr)).get("material"))
        except (ValueError, OSError, TypeError, KeyError, AttributeError):
            material = {}
        status = material.get("status")
        if status in (green_cert.NOT_APPLICABLE, green_cert.AWAITING_HUMAN):
            why = oneline.one_line(material.get("reason") or "") if status == green_cert.AWAITING_HUMAN else ""
            return f"{gatemarks.MATERIAL_WORDS[status]}（{status}）" + (f"——{why}" if why else "")
    return "赤" + (f"（赤の原因 {base.get('red_cause')}）" if base.get("red_cause") else "")


def depth_lines(raise_: dict, switches: dict, ports_: dict, tdd: list) -> list:
    """深さの行（raise の lines）。軽量で緑の後の test_cmd を省いた単位が在れば、その数を足して tiers.lines で組み直す
    （integration.md 4.5-14。raise は修正の段の TDD の記録の前に lines を組むので数を 0 で組んでいる）"""
    try:
        n = factslib.cmd_skipped(tdd)
    except Exception as e:  # noqa: BLE001 — 数えられなくても深さの行は出す
        return [*[str(x) for x in _l(raise_.get("lines"))], f"軽量の単位で test_cmd を省いた数を数えられない（{type(e).__name__}: {e}）"]
    if not n or not raise_:
        return [str(x) for x in _l(raise_.get("lines"))]
    from src import tiers
    doc = tiers.docs_of(_l(raise_.get("units")), forced=str(ports_.get("forced") or ""))
    doc["raised"] = [str(x) for x in _l(raise_.get("raised"))]
    doc["counted"] = str(raise_.get("counted") or "")
    return [str(x) for x in tiers.lines(doc, switches.get("tier") or "", cmd_skipped=n)]


def build(values: dict, record: dict, *, cwd, folder) -> list:
    """sections の並び（docs/design/line.md の 7.1 の 1〜10）"""
    v = {k: _d(values.get(k)) for k in values}
    received = _d(v.get("fix_in", {}).get("received"))
    judge = v.get("judge") or _d(received.get("judge"))
    rounds = v.get("rounds") or _d(received.get("rounds"))
    structure = v.get("structure") or _d(received.get("structure"))
    base = v.get("test_gate_base") or _d(received.get("test_gate_base"))
    fixed, eyes = v.get("fixed", {}), v.get("eyes", {})
    judge_s, eyes_s = _by_title(judge), _by_title(eyes)
    used = set()
    out = [_section(ENTRY, entry_lines(values, record, cwd=cwd, folder=folder))]
    spec_lines = [*_lines(v.get("spec_entry")), *_lines(v.get("spec_driven_check"))]
    if spec_lines:   # 仕様駆動の run の入口の確かめと、仕様とリポジトリの食い違いの照らし（docs/design/spec-driven.md の 6.2 の変える node の 7）
        out.append(_section(SPEC_DRIVEN, spec_lines))
    if v.get("fix"):
        out.append(_section(TDD, _lines(v["fix"]), _files(("差分", fixed.get("diff")), *(("申し出と裁定", c) for c in _l(fixed.get("conflicts"))))))
    if v.get("refix"):
        out.append(_section(TDD_2, _lines(v["refix"])))
    if base or v.get("test_gate_final"):
        out.append(_section(GREEN, [*_lines(base), *_lines(v.get("test_gate_final"))],
                            _files(("直す前の結末", base.get("baseline")), ("試験の記録（直す前）", base.get("evidence")),
                                   ("試験の記録（最後）", _d(v.get("test_gate_final")).get("evidence")))))
        scope_lines = not_run_lines(base, v.get("test_gate_final"))
        if scope_lines:
            out.append(_section(NOT_RUN, scope_lines))
    if eyes:
        eye_lines = [*_lines(eyes)]
        for title, lines in eyes_s.items():
            if title != EYES_AFTER:
                eye_lines += [f"{title}:", *[f"  {x}" if not x.startswith("  ") else x for x in lines]]
        out.append(_section(EYES, eye_lines))
    if structure or EYES_AFTER in eyes_s:
        out.append(_section(STRUCTURE, [*_lines(structure), *eyes_s.get(EYES_AFTER, [])],
                            _files(("構造の目", structure.get("structure")), ("直した後の構造", eyes.get("after")))))
    if JUDGE_WORLD in judge_s:
        used.add(JUDGE_WORLD)
        out.append(_section(WORLD, judge_s[JUDGE_WORLD], _files(("定石", judge.get("world")), ("目的", judge.get("purpose")))))
    if JUDGE_LOCAL in judge_s:
        used.add(JUDGE_LOCAL)
        out.append(_section(LENS_LOCAL, judge_s[JUDGE_LOCAL]))
    if JUDGE_DIAGNOSE in judge_s:
        used.add(JUDGE_DIAGNOSE)
        out.append(_section(JUDGMENT, judge_s[JUDGE_DIAGNOSE],
                            _files(("判定", judge.get("judgment")), ("目的の外の所見", judge.get("out_of_purpose")))))
    # 9. 今の報告に無かった節（run の順）
    for title in JUDGE_LATER:
        if title in judge_s:
            used.add(title)
            files = _files(("仕様", judge.get("spec"))) if title == "仕様" else _files(("目的", judge.get("purpose"))) if title == "目的の固定" else []
            out.append(_section(title, judge_s[title], files))
    for title, lines in judge_s.items():
        if title.startswith("素材: ") and title not in used:
            used.add(title)
            out.append(_section(title, lines))
    if JUDGE_VERIFY in judge_s:
        used.add(JUDGE_VERIFY)
        out.append(_section(JUDGE_VERIFY, judge_s[JUDGE_VERIFY]))
    for title, lines in judge_s.items():
        if title not in used:
            out.append(_section(title, lines))
    if v.get("independent_design"):
        out.append(_section(DESIGN, _lines(v["independent_design"]), _files(("独立設計", v["independent_design"].get("design")))))
    if rounds:
        out.append(_section(ROUNDS, rounds_lines(rounds),
                            _files(("計画", rounds.get("plan")), ("波及", rounds.get("ripple")), ("事前審査", rounds.get("review")))))
    ask = v.get("ask_before_fix")
    if ask:
        lines = [f"開いた: {'はい' if ask.get('open') else 'いいえ'}"]
        lines += [f"聞かずに通した行: {json.dumps(p, ensure_ascii=False)}" for p in _l(ask.get("passes"))]
        lines += [f"載せなかった問い: {json.dumps(q, ensure_ascii=False)}" for q in _l(ask.get("deferred"))]
        out.append(_section(BEFORE_FIX, lines))
    out += _review_section(REVIEW_1, v.get("lens"), v.get("delta"), v.get("fix"), v.get("raise"))
    if v.get("replan") or v.get("replan_review"):
        widened = [f"聞かずに通した範囲を広げるだけの直し: {json.dumps(w, ensure_ascii=False)}" for w in _l(v.get("ask_replan", {}).get("widened"))]
        out.append(_section(REPLAN, [*_lines(v.get("replan")), *_lines(v.get("replan_review")), *widened]))
    if v.get("refix"):
        out += _review_section(REVIEW_2, v.get("lens_2"), v.get("delta_2"), v.get("refix"), v.get("raise"))
    if v.get("parallel_after"):
        out.append(_section(PARALLEL_AFTER, _lines(v["parallel_after"])))
    if v.get("rejudge") or _l(v.get("judged", {}).get("lines")):
        out.append(_section(REJUDGE, [*_lines(v.get("rejudge")), *[str(x) for x in _l(v.get("judged", {}).get("lines"))]]))
    if v.get("spec_check"):
        out.append(_section(SPEC_CHECK, _lines(v["spec_check"])))
    if v.get("merge_seal") or v.get("merge_apply"):
        out.append(_section(MERGE, [*_lines(v.get("merge_seal")), *_lines(v.get("merge_apply"))],
                            _files(("封じた差分", v.get("merge_seal", {}).get("diff")), ("置いた差分", v.get("merge_apply", {}).get("diff")))))
    groups = groups_lines(judge)
    if groups:
        out.append(_section(GROUPS, groups))
    return out


def _review_section(title: str, lens, delta, fix, raise_) -> list:
    """段ごとのレンズと差分の審査の節。fix が走ったのに回さなかった段は、訳つきの 1 行（今の fixboard.LENS_NOT_DUE）"""
    if lens or delta:
        return [_section(title, [*_lines(lens), *_lines(delta)])]
    if fix:
        why = _d(raise_).get("skip_why") or "修正の段の変更の確かめが通らなかったか、戻せない組が在った"
        return [_section(title, [LENS_NOT_DUE.format(why=why)])]
    return []


def rounds_lines(rounds: dict) -> list:
    """計画の往復の行: 往復ごとの行（src.rounds.lines。往復の記録 plan-converge.json から）と、止め時の事実"""
    lines = [f"往復: {rounds.get('round')} 周・抜け方: {'修正へ進む' if rounds.get('ok') else '修正へ進まない'}"
             + ("（止まった）" if rounds.get("stalled") else "") + ("（安全の上限で止めた。工場の不具合）" if rounds.get("capped") else "")]
    try:
        from src import rounds as roundslib
        doc, why = factslib.read_ptr(rounds.get("record"))
        if why:
            lines.append(f"往復の記録を読めない（{why}）")
        elif doc is not None:
            lines += [str(x) for x in roundslib.lines(doc)]
    except Exception as e:  # noqa: BLE001 — 往復の行を組めなくても節を出す
        lines.append(f"往復ごとの行を組めない（{type(e).__name__}: {e}）")
    return lines


def groups_lines(judge: dict) -> list:
    """模型の群の選び（head-depth の record を KEEP の headdepth.groups_lines で組む。report の設計書の 1.6）"""
    try:
        import headdepth
        doc, why = factslib.read_ptr(_d(judge).get("tier_record"))
        if why or doc is None:
            return []
        return [str(x) for x in headdepth.groups_lines(doc)]
    except Exception:  # noqa: BLE001 — 群の行を組めなければ節を出さない（模型の事実は report の節に在る）
        return []
