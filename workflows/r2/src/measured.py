"""比べの役と検算の役に貼る、機械が測ったテストの実測と累積差分の起点の材料（docs/design/r2.md の 1.5）。lib/eyeverdict.py の
outcome_side・outcome_lines・TRANSITIONS・tdd_record_lines・origin_section・FIX_DIFF_ROW の写し。見出しは写さず、md の部品
prompts/parts/measured.md が持つ。tdd_record_lines は port tdd の値（段ごとの組の配列か、読めない訳の字）を受ける。
named_scope は、変わらない赤でない行のうち名を貼るテストの範囲を、変更の周りの地図（lib/impact.map）と TDD の記録から決める。
origin_section は作り直しの間 lib の fixboard・unittrees・leftovers を読む（docs/design/r1.md の 10 節の 2）。"""
from __future__ import annotations

import baseline_red   # lib/。FAILED
import eyekit         # lib/。changed_files
import fixboard       # lib/
import impact         # lib/。map・_mod・_junit_module
import leftovers      # lib/
import oneline        # lib/
import report         # lib/。tdd_stage_groups・tdd_lines
import unittrees      # lib/

FIX_DIFF_ROW = "この run の直しの差分"   # 起点の訳の行の名（検算の役の md が {fix_diff_row} でこの名の行を指す）
# 移り方（base の側→最後の側）の並びの順と、名に添える読み。ここに無い移り方（飛ばし・片側に居ない）は後ろに出会った順
TRANSITIONS = {"赤→緑": "base で赤・最後に緑", "緑→緑": "base でも最後でも緑", "緑→赤": "base で緑・最後に赤", "赤→赤": "base でも最後でも赤"}
TRIMMED = ("緑→緑", "飛ばし→飛ばし")   # 名を貼る範囲（named_scope）で絞る移り方（結末が変わらず赤でない）
LEFT_UNNAMED = "  - ほかに {n} 件は名を貼っていない（変更したファイルから地図で届かないテストのファイルの物）"


def outcome_side(outcome: str) -> str:
    if outcome in baseline_red.FAILED:
        return "赤"
    return {"passed": "緑", "skipped": "飛ばし", "": "測っていない"}.get(outcome, outcome)


def named_scope(repo, rev: str, changed, cache_dir, stages) -> dict | None:
    """変わらない赤でない行（TRIMMED）のうち名を貼るテストの範囲 {modules, tests}。modules は、累積差分で変わったファイル changed
    （除くパスの頭の下を除いた後。Archon が作業ツリーに写す pack の置き場を起点に入れない）と、そこから地図（impact.map の seeds）が
    届くと言うテストのファイルの名の幹（impact._mod）、tests は TDD の記録（port tdd の値 stages）の単位が名指したテスト。changed が
    None（累積差分が取れない）・地図が引けない・all_tests_required の時は None（全部の名を貼る）"""
    if changed is None:
        return None
    try:
        m = impact.map(repo, rev=rev or "HEAD", seeds=list(changed), cache_dir=cache_dir)
    except (RuntimeError, OSError, ValueError, RecursionError):
        return None
    if m["all_tests_required"]:
        return None
    tests = [t for stage in stages or [] if isinstance(stage, list) for g in stage if isinstance(g, dict)
             for u in g.get("units") or [] if isinstance(u, dict) for t in u.get("tests") or [] if isinstance(t, str)]
    return {"modules": {impact._mod(f) for f in (*m["seeds"]["files"], *m["tests"])}, "tests": tests}


def _named(key: str, scope) -> bool:
    """変わらない赤でない行の名を貼るか。範囲が無い（決められない）・行のテストのファイルが分からない時は貼る（落とす向きに外さない）。
    classname の点で切ったどの部分が範囲の名の幹でも貼る（test_ で始まるフォルダの下のテストの classname は、最初の test_ の部分が
    フォルダの名になる）"""
    if scope is None:
        return True
    cls, _, name = key.partition("::")
    if impact._junit_module({"classname": cls}) is None:
        return True
    return bool(set(cls.split(".")) & scope["modules"]) or any(
        baseline_red.match_case(t, [{"classname": cls, "name": name}]) for t in scope["tests"])


def outcome_lines(test_outcomes, scope=None) -> list[str]:
    """テストを移り方ごとにまとめ、移り方の行の下にテストを名指す（赤の側は結末と落ちた文を添える）。結末が変わった行と赤→赤は全部、
    変わらない赤でない行（TRIMMED）は範囲 scope（named_scope の返り）の物だけを名指し、残りは件数の 1 行（LEFT_UNNAMED）。scope が
    None なら全部を名指す"""
    if not isinstance(test_outcomes, dict):
        return ["- 試験の関門がテストごとに base と最後を比べた結果（test_outcomes）が渡っていない。どのテストが base と最後に緑か赤かは分からない"]
    if test_outcomes.get("unmeasured"):
        return [f"- 比べていない（{oneline.one_line(test_outcomes['unmeasured'])}）。テストごとの base と最後の結末は測っていない"]
    groups: dict[str, list[str]] = {t: [] for t in TRANSITIONS}
    for r in test_outcomes.get("rows") or []:
        base, final = r.get("base") or "", r.get("final") or ""
        notes = [f"{side} {o}" for side, o in (("base", base), ("最後", final)) if o in baseline_red.FAILED]
        if notes and (why := oneline.one_line(r.get("fail_message") or "")[:200]):
            notes[-1] += f": {why}"
        move = f"{outcome_side(base)}→{outcome_side(final)}"
        shown = move not in TRIMMED or _named(str(r.get("key") or ""), scope)
        groups.setdefault(move, []).append(f"  - `{r.get('key')}`" + (f"（{'・'.join(notes)}）" if notes else "") if shown else None)
    out = []
    for move, rows in groups.items():
        if rows:
            named = [row for row in rows if row is not None]
            left = [LEFT_UNNAMED.format(n=len(rows) - len(named))] if len(named) < len(rows) else []
            out += [f"- {move}{f'（{TRANSITIONS[move]}）' if move in TRANSITIONS else ''}: {len(rows)} 件", *named, *left]
    return out or ["- 無い（base と最後のどちらの一式にもテストが居ない）"]


def tdd_record_lines(stages) -> list[str]:
    """段ごとの記録を、報告と同じ描き方（report.tdd_lines。段の名は report.tdd_stage_groups）の行に。stages は port tdd の値
    （段ごとに、組ごとの記録の配列か、読めない訳の字。無ければ None）"""
    named, notes = [], []
    for n, stage in enumerate(stages or []):
        if isinstance(stage, str):
            notes.append(f"- TDD のループの記録を読めない（{stage}）")
            continue
        named += report.tdd_stage_groups(n, stage)
    rows = [r if r.startswith(" ") else f"- {r}" for r in report.tdd_lines(named)]
    return (rows or ["- 無い（修正の段が走っていない）"]) + notes


def origin_section(repo, base: str, head: str, label: str, *, cumulative_empty: bool, skip=()) -> str:
    """累積差分の起点の訳。起点 base（入口の差分の根）が修正前の HEAD head と同じ版か PR の根かを書き、PR の差分（base → head。
    fixboard.pr_diff）とこの run の直しの差分（head → 作業ツリー。fixboard.run_diff）で変わったファイルを分けて名指す。どちらも累積
    差分と同じく除くパスの頭 skip の下は載せない。累積差分が空（cumulative_empty）なら、打ち消し合ったのか何も変えていないのかを分ける。
    label は起点の出どころの文"""
    if not base:
        return "- 累積差分の起点が分からない（差分の根が渡っていない）"
    try:
        base_sha, head_sha = fixboard.pr_revs(repo, base, head)
        pr_files = fixboard.pr_diff(repo, base_sha, head_sha, skip, "--name-only").splitlines()
        commits = int(unittrees._out(repo, "rev-list", "--count", f"{base_sha}..{head_sha}"))
        fix_files = eyekit.changed_files(fixboard.run_diff(repo, head_sha, skip))
    except (unittrees.UnitTreeError, leftovers.Unreadable, ValueError) as e:
        return f"- 累積差分の起点を測れない（{oneline.one_line(e)}）"
    where = f"（{label}）" if label else ""
    if base_sha == head_sha:
        rows = [f"- 起点は修正前の HEAD `{base_sha[:12]}`{where}。PR の差分は無い（累積差分はこの run の直しの差分だけ）"]
    else:
        rows = [f"- 起点は PR の根 `{base_sha[:12]}`{where}で、修正前の HEAD `{head_sha[:12]}` との間に PR の commit が {commits} 個在る。"
                "累積差分は PR の差分と直しの差分を合わせた物",
                f"- PR の差分（起点 → 修正前の HEAD）で変わったファイル: {'、'.join(pr_files) or '無い'}"]
    rows.append(f"- {FIX_DIFF_ROW}（修正前の HEAD → 作業ツリー）で変わったファイル: {'、'.join(fix_files) or '無い'}")
    if cumulative_empty:
        rows.append("- 累積差分が空なのは、PR の変更と直しが打ち消し合った（直しが PR の変更を元に戻した）から。何もしていないのではない"
                    if pr_files and fix_files else "- 累積差分が空なのは、PR も直しも何も変えていないから")
    return "\n".join(rows)
