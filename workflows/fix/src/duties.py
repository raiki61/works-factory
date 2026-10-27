"""確かめの表（docs/plans/2026-10-24-fix-weapons.md の 2.4。箱の共通の義務 + 型の義務の 2 層。型を問わない部品）。

型の名から箱を引く表 BOXES と、箱の義務の表 BOX_DUTIES・型の義務の表（型のモジュールの DUTIES）をここ 1 か所に置く。共通の
受け付けが型の名で枝分かれするのは、この表を引く check の 1 か所だけ。型の義務の関数は箱の義務の結果を受け取らない（例外を書く口が
API に無い。憲法の 6）: check は「箱の義務の問題 + 型の義務の問題」を並べるだけで、どちらも問題を足すことしかできない。

どの関数も単位の事実 facts（受け付けが組む dict。下の FACTS）だけを読み、yes/no で問題の文を返す。表の行に載せた関数だけが受け付けで
効く。PR A は機械が自分で決められる照らしだけを表に置き、書き手が返す証拠（evidence.named・kinds・sites の at・fixed_by・test）が
要る照らしは、関数と試験を置いて段 2 で表に足した（docs/plans/2026-10-25-fix-weapons-stage1-a.md の 3。F1 が kinds・sites の 4 つ、
F2 が変える段の箱の義務 change_named_or_gone）。

FACTS（単位ごと）: unit（単位の key）・weapon・files（単位の行の files。根からの相対）・test_files（その中の試験のファイル。
impact.is_test_file）・kinds（files の rules.kind_of の集まり）・allowed_kinds（static の注文の変えてよい種類）・why_untested・
added（足した試験の id）・vanished（元で通っていて返した木の同じ選びの回に居ない試験の鍵）・permits（注文の permits の行）・
no_tests（base.json の印）・absent_at_base（files のうち起点の木に無いパス）・twice（足した試験を起点の木で 2 回走らせた問題の文の並び。
走らせていなければ None）・named（その単位の名指しの試験。unit_named が返答の evidence.named・注文の units[].tests・permits の rewrite の行の
試験・tdd の単位の輪の記録の tests を重ねずに並べる。変える段の型だけ引く）・before（名指し → 起点の木の結末。赤は "failure"。gates.named_before が
事後の関門と同じ事実から引き、走らせを足さない）・after（名指し → 返した木の結末。受け付けが走らせた回 cases から引く。居なければ "missing"）・
removes（注文の units[].removes）・gone（removes のうち起点の木で引けて今の木で引けない物。gone_of）・class_query（注文の units[] の物。無ければ None）・hits（問いの当たりの行
path:line の集まり。問いを行で結べない単位と問いの無い単位は None）・hunks（since から返した木までの git diff -U0 の新しい側の塊
{path: [(a, b)]}）と、書き手の返答から組む REPLY_FACTS（kinds_rows〔返答の evidence.kinds の行〕・sites〔単位の行の closure.sites の全部〕・
red_seen〔そのどれかが赤を見た〕・named〔上の名指しの試験〕）。
"""
from __future__ import annotations

import os
import pathlib
import posixpath
import re

from src import pin, rebuild, remove, static, tdd, tidy, variant

BOXES = {"tdd": "change", "variant": "change", "remove": "change", "tidy": "keep", "rebuild": "keep", "pin": "keep",
         "static": "outside"}   # 型の名（と下ごしらえの名 pin）→ 箱。注文に箱の欄を持たない
MODULES = {"tdd": tdd, "variant": variant, "remove": remove, "static": static, "tidy": tidy, "pin": pin, "rebuild": rebuild}
WEAPONS = tuple(BOXES)
REJECT = "型 {weapon} の単位 {unit} の義務: {text}"


REPLY_FACTS = ("kinds_rows", "sites", "red_seen", "named")   # 書き手の返答から組む事実の名（unit_facts が組む。読む義務の関数は段落の属性 paragraph を持つ。tests/blocks/fix/test_duty_paragraphs.py）


def box_of(weapon: str) -> str:
    return BOXES[weapon]


def change_named_or_gone(f: dict) -> list:
    """変える段の箱の義務（2.4）: 単位ごとに、(1) 名指しの試験が 1 つ以上で、どれも起点の木で failure・返した木で通る、か
    (2) 消す名 removes が空でなく、全部が gone に在る、のどちらか"""
    named = list(f.get("named") or [])
    before, after = f.get("before") or {}, f.get("after") or {}
    if named and all(before.get(t) == "failure" and after.get(t) == "passed" for t in named):
        return []
    removes = list(f.get("removes") or [])
    if removes and set(removes) <= set(f.get("gone") or []):
        return []
    return ["名指しの試験が起点の木で赤（failure）・返した木で緑にならず、消す名も返した木から全部は消えていない"
            "（変えた動きを試験か機械で示す）"]


change_named_or_gone.paragraph = "rules_named"   # 書き手に evidence.named を書かせる段落（.shared/prompts/writer.md。tests/blocks/fix/test_duty_paragraphs.py）


def keep_same_result(f: dict) -> list:
    """変えない段の箱の義務（2.4 の同じ結果の照らしのうち、居なくなった試験）: 起点で通っていて返した木の同じ選びの回に居ない試験は、
    どれも permits の remove の行の中（受け付けの新しい赤の照らしは今の selected_problems が持つ）"""
    allowed = {r.get("test") for r in f.get("permits") or [] if r.get("kind") == "remove"}
    gone = [k for k in f.get("vanished") or [] if k not in allowed]
    return [f"起点で通っていた試験が返した木で居なくなった: {gone[:10]}（振る舞いを変えない段は試験を消さない。消すのは消す名の許しの中だけ）"] \
        if gone else []


BOX_DUTIES = {"change": (change_named_or_gone,), "keep": (keep_same_result,), "outside": ()}


def table_of(weapon: str) -> tuple:
    """型 weapon の義務の関数の全部（箱の義務の表 + 型の義務の表）。照らし（check）と、書き手の指示の段落の真偽（prompts.writer_paragraphs）が
    同じ表から引く"""
    return (*BOX_DUTIES[box_of(weapon)], *MODULES[weapon].DUTIES)


def check(weapon: str, facts: dict) -> list:
    """型 weapon の単位の事実 facts を、箱の義務と型の義務の表で照らした問題の文（空なら通る）"""
    out = [t for fn in table_of(weapon) for t in fn(facts)]
    return [REJECT.format(weapon=weapon, unit=facts.get("unit", ""), text=t) for t in out]


# ---------------------------------------------------------------- 共通の受け付けが単位の事実を組んで表で照らす口
def _show(repo, rev: str, path: str):
    """版 rev のファイル path の中身（無ければ None）"""
    from leftovers import Unreadable, git   # lib/
    try:
        return git(repo, "show", f"{rev}:{path}")
    except Unreadable:
        return None


def _now(repo, path: str):
    p = pathlib.Path(repo) / path
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def _rows_files(rows) -> list:
    out: list = []
    for c in rows:
        for f in c.get("files") or []:
            p = f.get("path") if isinstance(f, dict) else f
            if isinstance(p, str) and p.strip():
                p = posixpath.normpath(p.strip())
                out += [p] if p not in out else []
    return out


def _plan_kinds(place, key: str) -> list:
    """単位 key の計画の項目の files の種類（rules.kind_of。static の変えてよい種類）"""
    import conflict   # lib/
    from src import rules
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), 1) or []
    except ValueError:
        return []
    out: list = []
    for f in fields:
        if isinstance(f, dict) and key in (f.get("unit_keys") or []):
            for row in f.get("files") or []:
                p = row.get("path") if isinstance(row, dict) else None
                k = rules.kind_of(p) if isinstance(p, str) else None
                out += [k] if k and k not in out else []
    return out


def _vanished(base: dict | None, cases) -> list:
    """元の結末で通っていて、受け付けが走らせた回（cases）に同じモジュールが出たのに居ない試験の鍵"""
    import impact   # lib/
    if not base or cases is None:
        return []
    from src import common
    ran = {impact._junit_module(c) for c in cases}
    after = {common._key(c) for c in cases}
    return [common._key(c) for c in base.get("baseline_cases") or [] if isinstance(c, dict) and c.get("outcome") == "passed"
            and impact._junit_module(c) in ran and common._key(c) not in after]


def _twice(base: dict | None, repo, added: list, work) -> list | None:
    """足した試験を 2 回名指しで走らせて、2 回とも通らなかった物の文（下ごしらえはコードを変えないので、作業ツリーのコードは起点の木の
    コードのまま）。実行器が無い・足した試験が無ければ None"""
    import baseline_red   # lib/
    from src import common
    if not base or not base.get("exe") or not added:
        return None
    pathlib.Path(work).mkdir(parents=True, exist_ok=True)   # 実行器の出力（junit・log）の置き場。受け付けの前に誰も作らない
    out = []
    for n in (1, 2):
        ran, _, why = baseline_red.run_suite(str(base["exe"]), repo, work, f"pin-twice-{n}", common._abs_ids(repo, added), only=True)
        if ran is None:
            out.append(f"足した試験を {n} 回目に走らせられない（{'; '.join(why)[:200]}）")
            continue
        bad = [t for t in added if (c := baseline_red.match_case(t, ran)) is None or c.get("outcome") != "passed"]
        if bad:
            out.append(f"足した試験 {bad[:10]} が {n} 回目に通らない（今の振る舞いを留める試験は 2 回とも通る）")
    return out


def _reply_facts(rows: list, kinds_rows, named=()) -> dict:
    """書き手の返答から組む事実（REPLY_FACTS）。rows は返答の changes のうちその単位の行、kinds_rows は返答の evidence.kinds の行、
    named はその単位の名指しの試験（unit_named が返答の evidence.named と注文・輪の記録の物を重ねた並び）"""
    sites = [s for c in rows for s in ((c.get("closure") or {}).get("sites") or []) if isinstance(s, dict)]
    return {"kinds_rows": [r for r in kinds_rows or [] if isinstance(r, dict)], "sites": sites,
            "red_seen": any(bool(s.get("red_seen")) for s in sites), "named": list(named)}


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _hunks(repo, since: str, files: list) -> dict:
    """since から今の作業ツリーまでの git diff -U0 の新しい側の塊 {path: [(a, b)]}（files の分だけ。消しだけの塊は入れない）。追跡されて
    いない新しいファイルは、ファイル全体 (1, 行数) を 1 つの塊にする。git が読めなければ {}（塊が無いので fixed_by は重ならず拒まれる）"""
    from leftovers import Unreadable, git   # lib/
    out: dict = {}
    if not files:
        return out
    try:
        text = git(repo, "-c", "core.quotePath=false", "diff", "-U0", "--no-color", since, "--", *files)
        fresh = git(repo, "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard", "--", *files).split("\n")
    except Unreadable:
        return out
    path = None
    for line in text.splitlines():
        if line.startswith("+++ "):
            name = line[4:].split("\t")[0]
            path = name[2:] if name.startswith("b/") else None
        elif path and (m := _HUNK.match(line)):
            a, d = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            if d:
                out.setdefault(path, []).append((a, a + d - 1))
    for p in (q for q in fresh if q):
        n = len((_now(repo, p) or "").splitlines())
        if n:
            out[p] = [(1, n)]
    return out


def _query_hits(repo, rev: str, cq) -> set | None:
    """単位の問い cq（注文の units[] の class_query）の起点の木 rev での当たりの行 path:line の集まり。問いが無い単位と、問いを行で
    結べない単位（ファイルごとの数が引けない・合計と合わない。unitrows の _bind の loose と同じ決まり）は None"""
    from src import unitrows
    how = (cq or {}).get("how")
    if not how:
        return None
    per_file, why = unitrows.file_counts(how, repo, rev)
    total = cq.get("total")
    if why or not isinstance(per_file, dict) or (isinstance(total, int) and not isinstance(total, bool) and sum(per_file.values()) != total):
        return None
    got, why = unitrows.hit_lines(how, repo, rev)
    return None if why else got


def _guard_ids(place) -> set:
    """承認済みの修正案の項目の受け入れの試験のうち、赤の種類が守りのテスト（planmarks.GUARD_KIND。直す前から緑で、緑のまま）の id
    （事後の関門 gates._accept_tests が guard にする物と同じ。名指しの『起点の木で赤』の義務に数えない）"""
    import conflict   # lib/
    import planmarks   # lib/
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), 1) or []
    except ValueError:
        return set()
    return {t["id"] for f in fields if isinstance(f, dict) for t in f.get("tests") or []
            if isinstance(t, dict) and isinstance(t.get("id"), str) and t.get("red_kind") == planmarks.GUARD_KIND}


def _ids(rows) -> list:
    """試験の id の並び（空でない字だけ。現れた順・重ねない）"""
    return list(dict.fromkeys(i for i in rows if isinstance(i, str) and i.strip()))


def unit_named(key: str, weapon: str, order: dict, evidence, record: dict, guards=()) -> list:
    """単位 key（型 weapon）の名指しの試験（下書き 2.1 の「受け付けの名指しの出どころ」・2.4 の変える段の義務。現れた順・重ねない）。
    1. 返答の evidence.named のうち unit_key がその単位の行の test
    2. 注文の units[] のその単位の tests（計画の項目の受け入れの試験と書き換えの試験。守りのテスト guards は数えない）
    3. 注文の permits の kind が rewrite の行の test。行は単位を持たない（任意の欄 unit は書かれない）ので、行に unit が在ればその単位、
       無ければ「その単位の注文の tests に在る」か「注文の単位がその 1 つだけ」の時にその単位に結ぶ（別の単位の書き換えで通さない）
    4. tdd の単位は輪の記録 record の units[<key>].tests（輪が名指した試験。書き手が evidence.named を書かなくても通す）"""
    units = [u for u in order.get("units") or [] if isinstance(u, dict)]
    mine = next((u for u in units if u.get("key") == key), {})
    plan = [t for t in _ids(mine.get("tests") or []) if t not in guards]
    rewrite = [r.get("test") for r in order.get("permits") or [] if isinstance(r, dict) and r.get("kind") == "rewrite"
               and r.get("unit", key) == key and (r.get("unit") == key or r.get("test") in plan or len(units) == 1)]
    loop = ((record.get("units") or {}).get(key) or {}).get("tests") or [] if weapon == "tdd" else []
    said = [r.get("test") for r in (evidence or {}).get("named") or [] if isinstance(r, dict) and r.get("unit_key") == key]
    return _ids([*said, *plan, *rewrite, *loop])


def gone_of(repo, rev: str, removes) -> list:
    """removes（注文の units[].removes）のうち、起点の木 rev で引けて今の作業ツリーで引けない物（下書き 2.4 の「gone の引き方」）。
    パスは起点の木に在り（git ls-tree）今の作業ツリーに無い物。名は起点の木で語として当たり（git grep -w -F）、今の作業ツリーでは未追跡の新しい
    ファイルも含めて 1 か所も当たらない物（定義だけでなく呼び手・文書の言及も残れば入らない）。どちらで見るかは、起点の木に同じ名のパスが在るか
    （ls-tree）で決める。git が読めない・当たりを数えられない名は入れない（安全側）。当たり無しの exit 1 は読めなかったのでなく 0 件
    （lib の engine.util の _grep_found が 0 件と読めなかったを分ける）"""
    import engine.util as util   # lib/graphloops
    from leftovers import Unreadable, git   # lib/
    out = []
    for name in _ids(removes or []):
        try:
            at_base = git(repo, "ls-tree", "--name-only", rev, "--", name).strip()
        except Unreadable:
            continue
        if at_base:
            if not os.path.lexists(pathlib.Path(repo) / name):
                out.append(name)
            continue
        hit = util._grep_found(["git", "grep", "-q", "-I", "-w", "-F", "-e", name, rev, "--"], str(repo))[0]
        if hit is not True:
            continue
        if util._grep_found(["git", "grep", "-q", "-I", "-w", "-F", "--untracked", "--exclude-standard", "-e", name, "--"], str(repo))[0] is False:
            out.append(name)
    return out


def compared(repo, rev: str, paths) -> dict:
    """paths のうち .py の、起点の版 rev と今の作業ツリーの試験の比べ {added, rewritten, removed}（足した・関数の本体の字が変わった・起点の版に在って
    今の木に無い試験の id。重ねず並べ替えた物）。返しの控え（write_returns）と受け付けの名指しの選び（reply_named）が同じ比べを引く"""
    from src import common, scope
    added, rewritten, removed = [], [], []
    for p in [p for p in paths if p.endswith(".py")]:
        old, new = _show(repo, rev, p), _now(repo, p)
        added += scope.new_test_ids(p, old, new)
        rewritten += _rewritten(p, old, new)
        if common.PYTEST_FILE.match(posixpath.basename(p)):
            before = set(scope._test_ids(p, old) or []) if old is not None else set()
            removed += sorted(before - set((scope._test_ids(p, new) or []) if new is not None else []))
    return {"added": sorted(set(added)), "rewritten": sorted(set(rewritten)), "removed": sorted(set(removed))}


def reply_named(place, repo, rev: str, reply) -> list:
    """受け付けが試験の選び（common.selected_problems の named）に足す、返答の側の名指し: 返答の evidence.named の試験と、受け付けが木の比べ
    （compared）で出す足した・書き換えた試験（下書き 2.1 の「受け付けの名指しの出どころ」の 3）。注文の側の物は orders.named_tests。
    注文の無い置き場・返答が dict でない時は空"""
    from src import orders
    weapons = orders.weapons(place)
    if not weapons or not isinstance(reply, dict):
        return []
    rows = [c for c in reply.get("changes") or [] if isinstance(c, dict) and c.get("unit_key") in weapons]
    got = compared(repo, rev, _rows_files(rows))
    said = [r.get("test") for r in (reply.get("evidence") or {}).get("named") or [] if isinstance(r, dict)]
    return _ids([*said, *got["added"], *got["rewritten"]])


def unit_facts(place, repo, rev: str, key: str, weapon: str, rows: list, *, order: dict, base, cases, declared=(), evidence=None,
               record: str = "") -> dict:
    """単位 key（型 weapon）の事実（上の FACTS）。rows は返答の changes のうちその単位の行、order はその型の注文、evidence は返答の evidence
    （kinds の行は単位に分けない。named の行は unit_key で単位に分ける）、record は今の段の輪の記録のファイル（tdd の単位の名指しを読む。
    無ければ空）。cases は受け付けが走らせた回の結末（keep の居なくなった試験と、変える段の after）"""
    import baseline_red   # lib/
    import impact   # lib/
    from src import common, gates, rules, scope
    files = _rows_files(rows)
    tests = [p for p in files if impact.is_test_file(p, set(declared))]
    added, removed = [], []
    for p in tests:
        old, new = _show(repo, rev, p), _now(repo, p)
        added += scope.new_test_ids(p, old, new)
        before = set(scope._test_ids(p, old) or []) if old is not None else set()
        removed += sorted(before - set(scope._test_ids(p, new) or [] if new is not None else []))
    kind_by_path = {p: rules.kind_of(p) for p in files}
    unit = next((u for u in order.get("units") or [] if isinstance(u, dict) and u.get("key") == key), {})
    cq = unit.get("class_query") if isinstance((unit.get("class_query") or {}).get("how"), dict) else None
    loop = common.load_record(record) if record and pathlib.Path(record).is_file() else {}
    named, before, after, removes, gone = [], {}, {}, [], []
    if box_of(weapon) == "change":   # 変える段の箱の義務の事実（ほかの箱は読まないので引かない。実行器も起こさない）
        named = unit_named(key, weapon, order, evidence, loop, _guard_ids(place))
        exe = str((base or {}).get("exe") or "")
        if named and exe:
            before = gates.named_before(place, repo, rev, exe, named, pathlib.Path(place) / "duties")
        if named and cases is not None:
            after = {t: (c["outcome"] if (c := baseline_red.match_case(t, cases)) else "missing") for t in named}
        removes = _ids(unit.get("removes") or [])
        gone = gone_of(repo, rev, removes) if removes else []
    return {"unit": key, "weapon": weapon, "files": files, "test_files": tests, "kind_by_path": kind_by_path,
            "kinds": sorted({k for k in kind_by_path.values() if k}), "allowed_kinds": _plan_kinds(place, key),
            "why_untested": str(order.get("why_untested") or ""), "added": added, "removed": removed,
            "permits": list(order.get("permits") or []), "no_tests": bool(base and base.get("no_tests") is True),
            "absent_at_base": [p for p in files if _show(repo, rev, p) is None],
            "vanished": _vanished(base, cases) if box_of(weapon) == "keep" else [],
            "twice": _twice(base, repo, added, pathlib.Path(place) / "duties") if weapon == "pin" else None,
            "class_query": cq, "hits": _query_hits(repo, rev, cq),
            "hunks": _hunks(repo, str(order.get("since") or "") or rev, files),
            "before": before, "after": after, "removes": removes, "gone": gone,
            **_reply_facts(rows, (evidence or {}).get("kinds"), named)}


def accept_problems(place, repo, rev: str, reply, *, cases=None, record: str = "") -> list:
    """共通の受け付けが型の義務の表で照らした問題の [(単位, 文)]（下書き 2.3・2.4。PR A の表は static・tidy・pin・remove の物）。
    型は注文の索引 orders.json の weapons（注文の無い置き場は照らさない）で、義務は単位の行の checked_as（裁定の後の直しの注文の、照らしに
    使う元の型。下書き 4.1 の 6）が在ればその型で引く（tdd から来た単位に variant の義務を当てない）。cases は受け付けが走らせた回の結末の
    行（keep の箱の居なくなった試験）"""
    from src import basecase, orders
    weapons = orders.weapons(place)
    if not weapons or not isinstance(reply, dict):
        return []
    docs = orders.order_docs(place)
    checked = orders.checked_as(place)
    base = basecase.read(place)
    keys = list(weapons)
    declared = basecase._declared(place, keys, 1)
    by: dict = {}
    for c in reply.get("changes") or []:
        if isinstance(c, dict) and c.get("unit_key") in weapons:
            by.setdefault(c["unit_key"], []).append(c)
    out = []
    for k, rows in by.items():
        w = checked.get(k) or weapons[k]
        if not table_of(w):
            continue
        facts = unit_facts(pathlib.Path(place), repo, rev, k, w, rows, order=docs.get(weapons[k]) or {}, base=base, cases=cases,
                           declared=declared, evidence=reply.get("evidence") if isinstance(reply.get("evidence"), dict) else None,
                           record=record)
        out += [(k, t) for t in dict.fromkeys(check(w, facts))]
    return out


def _rewritten(path: str, old, new) -> list:
    """old と new の両方に在って、関数の本体の字が違う試験の id（書き換えた試験）"""
    import ast
    from src import scope

    def bodies(src):
        try:
            tree = ast.parse(src or "")
        except (SyntaxError, ValueError):
            return {}
        lines = (src or "").splitlines()
        out = {}
        for node in tree.body:
            nodes = [(node.name, node)] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else \
                [(f"{node.name}::{m.name}", m) for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))] \
                if isinstance(node, ast.ClassDef) else []
            for name, n in nodes:
                out[f"{path}::{name}"] = "\n".join(lines[n.lineno - 1:n.end_lineno])
        return out
    a, b = bodies(old), bodies(new)
    ids = set(scope._test_ids(path, old) or []) & set(scope._test_ids(path, new) or [])
    return sorted(i for i in ids if a.get(i) != b.get(i))


def evidence_named(reply, key) -> list:
    """返答の evidence.named のうち unit_key が key の行の試験（現れた順）"""
    return [r.get("test") for r in ((reply or {}).get("evidence") or {}).get("named") or []
            if isinstance(r, dict) and r.get("unit_key") == key]


def write_returns(place, repo, rev: str, reply, *, record: str = "", owed=None) -> list:
    """共通の受け付けが返答を通した時に、型ごとの返しの控え returns/<k>.json を書く（下書き 2.1 の「返しの控え」。書くのはここ 1 か所）。
    形 {stage, weapon, group, tree, units: [{key, named}], frozen, frozen_tree, suite_made, added, rewritten, removed, files,
    why_untested, kinds}（kinds は書き手の返答の evidence.kinds の行。種類ごとの確かめの記録）。owed（受け付けた書き手の直す義務の単位）を渡せば、その単位を持つ型の注文の分だけを書く（型は 1 つずつ順に回る）。
    型は注文の索引の weapons、段の番と組は注文の物、tree は通した時の作業ツリーの木。tdd の返しの機械の欄 frozen・
    frozen_tree・suite_made は輪の記録 record から写す（ほかの型は空）。removed は起点の版に在って今の木に無い試験の id、files は返答の
    行のパス、why_untested は注文の物（修正の出力の欄 removed_tests・untested の出どころ。下書き 4.1 の 7）。注文の無い置き場は書かない。
    書いたパスを返す"""
    from src import common, orders
    weapons = orders.weapons(place)
    if not weapons or not isinstance(reply, dict):
        return []
    docs = orders.order_docs(place)
    loop = common.load_record(record) if record and pathlib.Path(record).is_file() else {}
    rows: dict = {}
    for c in reply.get("changes") or []:
        if isinstance(c, dict) and c.get("unit_key") in weapons:
            rows.setdefault(weapons[c["unit_key"]], []).append(c)
    tree = common.snapshot(repo)
    out = []
    mine = None if owed is None else set(owed)
    for w, doc in docs.items():
        keys = [u.get("key") for u in doc.get("units") or [] if isinstance(u, dict)]
        if mine is not None and not mine & set(keys):
            continue
        paths = _rows_files(rows.get(w, []))
        got = compared(repo, rev, paths)
        added, rewritten, removed = got["added"], got["rewritten"], got["removed"]
        if w == "tdd":
            added += [t for k in keys for t in ((loop.get("units") or {}).get(k) or {}).get("tests") or [] if t not in added]
        ret = {"stage": int(doc.get("stage") or 1), "weapon": w, "group": str(doc.get("group") or ""), "tree": tree,
               "units": [{"key": u.get("key"), "named": _ids([*(u.get("tests") or []), *evidence_named(reply, u.get("key"))])}
                         for u in doc.get("units") or [] if isinstance(u, dict)],
               "frozen": dict(loop.get("frozen") or {}) if w == "tdd" else {},
               "frozen_tree": str(loop.get("frozen_tree") or "") if w == "tdd" else "",
               "suite_made": list(loop.get("suite_made") or []) if w == "tdd" else [],
               "added": sorted(set(added)), "rewritten": sorted(set(rewritten)), "removed": sorted(set(removed)), "files": paths,
               "why_untested": str(doc.get("why_untested") or ""),
               "kinds": [r for r in ((reply.get("evidence") or {}).get("kinds") or []) if isinstance(r, dict)]}
        out.append(str(orders.write_return(place, ret)))
    return out


PERMIT_RANGES = ("rewrite", "agreed", "ruled", "broken")   # 凍ったファイルの照らしで範囲として読む許しの行の種類（下書き 2.3 の 9）


def frozen_by_returns(place, repo) -> list:
    """凍ったファイルの照らし（下書き 2.3 の 9）のうち返しの控えの分: 置き場の returns/ の全部の frozen（前の型・前の段の凍結）を、
    注文の索引の since の木を基準に、注文の permits の範囲（PERMIT_RANGES の行の test）と段の頭の後に取れた範囲の相談の合意
    （orders.later_agreed。注文は段の頭で 1 度しか書かない）だけを許して照らす（common.frozen_problems の
    同じ式。返しの控えは輪の状態と同じ名の欄 frozen・frozen_tree を持つ）。今の照らし facts.check_frozen は外さずに並べる（両方を
    通る物だけを通す。docs/plans/2026-10-25-fix-weapons-stage1-a.md の 1 の 3）。注文の無い置き場・控えの無い置き場は空"""
    import jsonfile   # lib/
    from src import common, files, orders
    idx = jsonfile.read_or(pathlib.Path(place) / files.ORDERS_FILE)
    since = str(idx.get("since") or "") if isinstance(idx, dict) else ""
    d = pathlib.Path(place) / files.RETURNS_DIR
    if not since or not d.is_dir():
        return []
    lims = sorted({str(r.get("test")) for doc in orders.order_docs(place).values() for r in doc.get("permits") or []
                   if isinstance(r, dict) and r.get("kind") in PERMIT_RANGES and r.get("test")} | set(orders.later_agreed(place)))
    out: list = []
    for p in sorted(d.glob("*.json"), key=lambda q: (len(q.stem), q.stem)):
        doc = jsonfile.read_or(p)
        if isinstance(doc, dict) and doc.get("frozen"):
            out += [t for t in common.frozen_problems(str(p), repo, lims, since=since) if t not in out]
    return out
