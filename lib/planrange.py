"""承認済みの修正案の項目の範囲で、変わったパスを照らす決まりの 1 か所（修正案の範囲の照らし。依頼 218）。修正の受け付け
（blk-fix の planscope。単位に結べる行の照らしと欠けの照らしはそちら）と、手直しの受け付け（refix.accept_fix）が同じ決まりで使う。

語:
- 項目の範囲: allowed_paths の glob と、tests・rewrite_tests の id のファイル（planmarks.test_paths）。glob の並びで言えば item_globs
- out_of_scope: 範囲の中でも触らない物で、範囲より強い。ただし範囲の相談の合意でその項目の out_of_scope から外したパス（LIFTED。
  字のまま同じパスだけ）は、その項目では当たらない
- 合意（with_agreed）: 範囲の相談で修正案を書いた役が許したパス（conflict.agreed。戻せた組の子の置き場から写した行も含む）を、
  その項目の allowed_paths に足す
- 許し（permit_paths）: テストの変更の許し（conflict.test_permits の範囲の行）のパスと、裁定の後なら直す裁定のパス
  （conflict.ruled_paths）。run の全部の項目の範囲の和に入る。out_of_scope には勝たない

- with_agreed(items, agreed)・item_globs(it)・inside(path, it)・oos_hit(path, items)・oos_hit_for(path, mine, items): 範囲の読み
- owner(path, items): パスを結ぶ項目（範囲に入る最初の項目、無ければ項目の最初）。はみ出しを相談に回す時の項目の選び
- permit_paths(b, *, ruled, agreed, round_): 許しのパスの並び（b は fix の run の置き場のフォルダのパス。conflict と同じ）
- outside(items, paths, permits, *, hint): 単位に結べない変わったパスの外れの行（全項目の範囲の和か許しに入らない・どれかの項目の
  out_of_scope に当たる）。hint なら、ほかの項目の out_of_scope に当たるがある項目の範囲には入るパスに OWNER_HINT を足す
- approved(items, *, by): 承認済みの修正案の項目の値 items（planmarks.approved_items の形。呼び手が渡す）を照らせるか
- scope(b, *, items, ruled, by, agreed, round_): 受け付けが照らす値 ({items: 合意を足した項目, permits: 許しのパス, rule: OOS_ANY,
  agreed: 足した合意の行}, "")。照らさない項目なら (None, 理由)。照らし（check_paths・planscope.check）と役の指示書（scope_text）と
  役の brief の範囲の欄（fixboard.scope_brief）が同じ値を引く 1 か所
- fix_scope(b, pass_, *, items, agreed, round_): 修正の段（pass_ first・ruled）の引数で scope を引く（rule は OOS_MINE）
- scope_text(got): 役の指示書に貼る節（SCOPE_HEAD）。scope の値の out_of_scope の決まりの文（rule）と、項目の範囲・out_of_scope・
  許しのパスを字のまま並べる
- test_ids(it): 項目の足してよい新しいテストの id（修正の段の受け付けの planscope.problems と指示書が同じ値を引く）
- tests_text(got, edits, frozen): 修正役の指示書に貼る節（TESTS_HEAD）。足してよい新しいテスト（test_ids）・本体を変えてよい既存の
  テスト（conflict.edit_permits）・凍ったテスト（factchecks.frozen_tests）を字のまま並べる
- check_paths(b, paths, *, items, ruled, by, round_): 承認済みの修正案の項目 items で paths を outside で照らす (行, 記録)。
  合意と裁定は置き場 b から読む。照らさない項目（修正案の無い・範囲の欄の無い控え）は ([], {"checked": False, "why": 理由})。
  欄の控えが凍結の印と食い違えば conflict.fields_broken の道（ValueError）
"""
from __future__ import annotations

import glob
import posixpath

import conflict
import planmarks
import promptsection
import stopby   # L1。止めの理由の住処

# 単位に結べない変わったパスがほかの項目の out_of_scope に当たり、ある項目の範囲には入る時に足す文（申告すればその項目で照らす）
OWNER_HINT = "（項目 {nums} の範囲には入る。その項目の単位の changes[].files に申告すれば、その項目の out_of_scope だけで照らす）"
LIFTED = "out_of_scope_lifted"   # with_agreed が項目の写しに足す欄: 合意でその項目の out_of_scope から外したパス（字のまま）
NO_PLAN = "承認済みの修正案か works の欄の控えが無い"
NO_SCOPE = "範囲の欄の無い控え（217 番の形の共有ボード）"
SCOPE_HEAD = promptsection.Section("## 変えてよいパスと触らない物（受け付けがこの値で照らす）", source="fn:planrange.scope_text")
TESTS_HEAD = promptsection.Section("## 変えてよいテストと凍ったテスト（受け付けがこの名で照らす）", source="fn:planrange.tests_text")


def globs(it: dict) -> list[str]:
    return [g for g in it.get("allowed_paths") or [] if isinstance(g, str) and g]


def test_ids(it: dict) -> list[str]:
    """項目の tests の id（範囲の相談の合意で足した印 agreed の行も。現れた順・重なりは 1 つ）。修正の段の受け付けは、ここに無い
    新しいテストを拒む（planscope.problems の 6）。修正役の指示書（tests_text）も同じ値を貼る"""
    return list(dict.fromkeys(row["id"] for row in it.get("tests") or []
                              if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"].strip()))


def _oos_rows(it: dict) -> list[dict]:
    return [r for r in it.get("out_of_scope") or [] if isinstance(r, dict) and isinstance(r.get("glob"), str) and r["glob"]]


def _oos(it: dict) -> list[str]:
    return [r["glob"] for r in _oos_rows(it)]


def item_globs(it: dict) -> list[str]:
    """項目の範囲（allowed_paths の glob・tests と rewrite_tests の id のファイル）を glob の並びで。テストのファイルは字のまま
    当たるよう glob.escape で包む（名に * ? [ を含んでも glob として読まない）"""
    return globs(it) + [glob.escape(f) for f in planmarks.test_paths(it)]


def inside(path: str, it: dict) -> bool:
    """path が項目の範囲（item_globs）に入るか"""
    return any(planmarks.glob_match(path, g) for g in item_globs(it))


def owner(path: str, items: list[dict]):
    """path を結ぶ項目: 範囲に入る（inside）最初の項目、無ければ items の最初。items が空なら None（受け付けがはみ出しを範囲の
    相談に回す時に、頼みをどの項目に結ぶかの決まりの 1 か所。planscope・fixgates・受け付けが呼ぶ）"""
    return next((it for it in items if inside(path, it)), items[0] if items else None)


def oos_hit(path: str, items: list[dict]):
    """path に当たる out_of_scope の最初の (項目, glob)。無ければ None。合意でその項目の out_of_scope から外したパス（LIFTED）は
    その項目では当たらない"""
    return next(((it, g) for it in items if path not in (it.get(LIFTED) or ()) for g in _oos(it)
                 if planmarks.glob_match(path, g)), None)


# 役の指示書に貼る out_of_scope の決まりの文。oos_hit（全部の項目で照らす。outside・手直しの受け付け）と oos_hit_for（行の単位の
# 項目が明示に許せばその項目だけで照らす。修正の段の受け付け planscope.problems の 1）の決まりを言う
OOS_ANY = ("`out_of_scope` は範囲より強く、許しのパスにも勝つ。どの項目の `out_of_scope` も、変えた全部のパスに当たる"
           "（範囲の相談で外したパスだけは、その項目で当たらない）。")
OOS_MINE = ("`changes[].files` に申告したパスを、その単位の項目のどれかが明示に許していれば（allowed_paths・テストのファイル）、"
            "その単位の項目の `out_of_scope` だけで照らす（ほかの項目の `out_of_scope` は当たらない）。それ以外のパスには、どの項目の"
            " `out_of_scope` も範囲より強く、許しのパスにも勝つ（範囲の相談で外したパスだけは、その項目で当たらない）。")


def oos_hit_for(path: str, mine: list[dict], items: list[dict]):
    """行の単位の項目（mine）から見た path の out_of_scope の当たり。mine のどれかが path を明示に許す（inside。allowed_paths・
    tests と rewrite_tests の id のファイル・with_agreed が足した合意）なら mine の out_of_scope だけで照らす（ほかの項目の
    out_of_scope は「その項目は触らない」で、許した項目の単位まで禁じない。run 249b）。許していなければ全部の項目で照らす。
    permits（run の全部に効く許し）は明示の許しに数えない"""
    return oos_hit(path, mine if any(inside(path, it) for it in mine) else items)


def oos_line(head: str, path: str, hit) -> str:
    return f"{head}{path} は項目 {hit[0].get('item')} の out_of_scope（{hit[1]}）に当たる"


def with_agreed(items: list[dict], agreed) -> list[dict]:
    """範囲の相談の合意（conflict.agreed の行 {item, granted_paths, granted_tests, granted_new_tests}）のパスを、その番号の項目の
    allowed_paths の後ろに足した写し。許したテストの範囲のパス・許した新しいテストのファイル・許したパスは、その項目の写しの LIFTED
    にも並べ、字のまま同じパスに限ってその項目の out_of_scope から外す（oos_hit。案を書いた役が自分の外した物を考え直して許した。
    持ち主 2026-10-07）。許した新しいテスト {id, red_kind} は、その項目の写しの tests の後ろに印 agreed つきで足す（テストのファイルは
    planmarks.test_paths で範囲に入る。案の外で足したテストの拒否の行に当たらず、今の木に在れば事後の関門が赤緑を確かめる）。印 agreed の
    行は許しで義務ではない（修正役が書かなくても・別の名で書いても欠けにしない。planscope の欠けの照らしと fixgates が外す）。同じ id は
    後の合意が前に勝つ。元の項目は変えない。
    ほかの項目は変えない。テストの書き換えの許しは conflict.test_permits が持つ"""
    more: dict = {}
    lift: dict = {}
    new_tests: dict = {}
    for r in agreed or []:
        n = str(r.get("item"))
        for p in r.get("granted_paths") or []:
            if isinstance(p, str) and p and p not in more.setdefault(n, []):
                more[n].append(p)
        tests = [got[0] for got in (conflict.parse_limit(t) for t in r.get("granted_tests") or [] if isinstance(t, str))
                 if got]
        fresh = [row for row in r.get("granted_new_tests") or [] if isinstance(row, dict) and isinstance(row.get("id"), str)
                 and row["id"].strip()]
        for row in fresh:   # 同じ id は後の合意が前に勝つ（赤の種類を相談で直せる）
            new_tests[n] = [x for x in new_tests.setdefault(n, []) if x["id"] != row["id"]]
            new_tests[n].append({"id": row["id"], "red_kind": row.get("red_kind"), "agreed": True})
        tests += [planmarks.test_paths({"tests": [row]})[0] for row in fresh if planmarks.test_paths({"tests": [row]})]
        for p in [*more.get(n, []), *tests]:
            p = posixpath.normpath(p)
            if p not in lift.setdefault(n, []):
                lift[n].append(p)
    out = []
    for it in items:
        n = str(it.get("item"))
        add = [p for p in more.get(n, []) if p not in globs(it)]
        if not add and not lift.get(n) and not new_tests.get(n):
            out.append(it)
            continue
        have = {row.get("id") for row in it.get("tests") or [] if isinstance(row, dict)}
        out.append({**it, "allowed_paths": [*(it.get("allowed_paths") or []), *add],
                    "tests": [*(it.get("tests") or []), *(row for row in new_tests.get(n, []) if row["id"] not in have)],
                    LIFTED: [*(it.get(LIFTED) or []), *lift.get(n, [])]})
    return out


def permit_paths(b, *, ruled: bool, agreed=None, round_: int = 1) -> list[str]:
    """許しのパス: テストの変更の許し（conflict.test_permits の範囲の行。裁定の範囲は含めない）のパスと、ruled なら直す裁定の
    パス（conflict.ruled_paths）。欄の控えが凍結の印と食い違えば test_permits の ValueError"""
    out = []
    for p in conflict.test_permits(b, rulings=False, agreed_rows=agreed, round_=round_):
        got = conflict.parse_limit(p["limit"]) if "limit" in p else None   # 単位で許す行（案の直し）はパスを足さない
        if got and got[0] not in out:
            out.append(got[0])
    if ruled:
        out += [p for p in conflict.ruled_paths(b) if p not in out]
    return out


def outside(items: list[dict], paths, permits=(), *, hint: bool = True) -> list[str]:
    """単位に結べない変わったパス paths の外れの行（並びの順）: どれかの項目の out_of_scope に当たる（hint なら、当たらずに範囲に
    入れる項目を OWNER_HINT で名指す）か、全項目の範囲の和にも permits にも入らない。純粋な関数"""
    permits = set(permits)
    out = []
    for p in paths:
        hit = oos_hit(p, items)
        if hit:
            owners = [it for it in items if inside(p, it) and not oos_hit(p, [it])] if hint else []
            out.append(oos_line("", p, hit) + (OWNER_HINT.format(nums="・".join(str(it.get("item")) for it in owners))
                                               if owners else ""))
        elif not (p in permits or any(inside(p, it) for it in items)):
            out.append(f"{p} はどの項目の allowed_paths にも無い")
    return out


def approved(items, *, by: str = stopby.FIX):
    """(承認済みの修正案の項目, 照らさない理由)。項目 items は planmarks.approved_items の形の値（呼び手が渡す。修正案の無い run は
    None）か、それを返す口（引数なし）。項目が無い・範囲の欄の無い控えなら (None, 理由)。口が凍結の印との食い違い
    （planmarks.FieldsBroken）を出せば conflict.fields_broken の道（by の印の文の ValueError）"""
    try:
        items = items() if callable(items) else items
    except planmarks.FieldsBroken as e:   # 控えが壊れた時の 1 本の道（ValueError）
        raise conflict.fields_broken(None, e, by=by) from None
    if items is None:
        return None, NO_PLAN
    if not planmarks.scoped(items):
        return None, NO_SCOPE
    return items, ""


def scope(b, *, items, ruled: bool, by: str = stopby.FIX, agreed=None, round_: int = 1) -> tuple[dict | None, str]:
    """受け付けが照らす値: ({items: 承認済みの修正案の項目 items（approved に渡す値か口）に範囲の相談の合意（agreed。None なら
    置き場 b の conflict.agreed）を足した物, permits: permit_paths, rule: out_of_scope の決まりの文 OOS_ANY（outside の決まり）,
    agreed: items に足した合意の行（conflict.agreed の行のまま。出どころは各行の id と group_id）}, "")。照らさない項目なら
    (None, 理由)"""
    items, why = approved(items, by=by)
    if items is None:
        return None, why
    agreed = conflict.agreed(b) if agreed is None else agreed
    return {"items": with_agreed(items, agreed), "permits": permit_paths(b, ruled=ruled, agreed=agreed, round_=round_),
            "rule": OOS_ANY, "agreed": agreed}, ""


def fix_scope(b, pass_: str, *, items, agreed=None, round_: int = 1) -> tuple[dict | None, str]:
    """修正の段（pass_ first・ruled）の受け付けが照らす値（scope。裁定の後は直す裁定のパスも許しに入る。rule は申告した単位で
    照らす planscope.problems の決まり OOS_MINE）"""
    got, why = scope(b, items=items, ruled=pass_ == "ruled", agreed=agreed, round_=round_)
    if got is None:
        return None, why
    return {**got, "rule": OOS_MINE}, ""


def _paths_line(paths) -> str:
    return "、".join(f"`{p}`" for p in paths) or "無し"


def scope_text(got) -> str:
    """役の指示書に貼る節（SCOPE_HEAD）: scope の値 got の out_of_scope の決まりの文（rule）と、項目ごとの範囲（allowed_paths の
    glob・tests と rewrite_tests の id のファイル）・out_of_scope・合意で外したパス（LIFTED）と、全部の項目に効く許しのパスを字のまま。
    got が None なら空"""
    if got is None:
        return ""
    lines = [SCOPE_HEAD, "", "受け付けは、変えたパスをこの値で照らし、外れを拒む。" + got["rule"]
             + "範囲の相談で許されたパスとテストの許しも、ここに入っている。", ""]
    for it in got["items"]:
        units = "、".join(str(k) for k in it.get("unit_keys") or []) or "無し"
        oos = [f"`{r['glob']}`" + (f"（{r['why']}）" if r.get("why") else "") for r in _oos_rows(it)]
        lines += [f"- 項目 {it.get('item')}（単位: {units}）",
                  f"  - allowed_paths: {_paths_line(globs(it))}",
                  f"  - テストのファイル（tests・rewrite_tests の id）: {_paths_line(planmarks.test_paths(it))}",
                  f"  - out_of_scope: {'、'.join(oos) or '無し'}"]
        if it.get(LIFTED):
            lines.append(f"  - 相談で out_of_scope から外したパス: {_paths_line(it[LIFTED])}")
    lines.append(f"- 全部の項目に効く許し（テストの変更の許し・直す裁定が足したパス。out_of_scope には勝たない）: "
                 f"{_paths_line(got['permits'])}")
    return "\n".join(lines)


def tests_text(got, edits: dict, frozen=None) -> str:
    """修正役の指示書に貼る節（TESTS_HEAD）: 修正の段の受け付けがテストを照らす名を字のまま。got は fix_scope の値（項目ごとの
    足してよい新しいテスト test_ids。照らさない項目なら None で、その行を出さない）、edits は conflict.edit_permits の値（本体を変えて
    よい既存のテストの名指しと範囲）、frozen は factchecks.frozen_tests の値（凍ったテストのファイルと、輪が確かめた書き換えの名指しと、
    裁定の範囲で凍結が解けない今の輪のファイル。ループの無い run は None）。純粋な関数"""
    verified = list((frozen or {}).get("verified") or [])
    lines = [TESTS_HEAD, "", "受け付けは、足したテスト・本体を変えた既存のテスト・凍ったテストのファイルをこの名で照らし、外れを拒む。"
             "外れが要るなら、変える前に範囲の相談で頼め。"]
    if got is not None:
        lines.append("- 足してよい新しいテスト（修正案の項目の tests。範囲の相談で許された物も入っている。これに無いテストを足すと拒む）:")
        for it in got["items"]:
            units = "、".join(str(k) for k in it.get("unit_keys") or []) or "無し"
            lines.append(f"  - 項目 {it.get('item')}（単位: {units}）: {_paths_line(test_ids(it))}")
    # 凍結の照らしは輪が確かめた書き換えを許しから外すので、事後の関門が id で許しても全体では拒まれる
    lines += [f"- 本体を変えてよい既存のテストの名指し（修正案の rewrite_tests と、修正案が消す名を名指すテスト）: "
              f"{_paths_line([t for t in edits['tests'] if t not in verified])}",
              "- 本体を変えてよい既存のテストの範囲（範囲の相談で許された範囲と、裁定 fix_test_scope の範囲。`<パス>` はそのファイルの全部、"
              f"`<パス>:<行>` はその行を含む関数の全体、`<パス>:<行>-<行>` は書いたとおりの行）: {_paths_line(edits['limits'])}",
              "- これ以外の既存のテストの関数の本体を変える・消すと拒む。"]
    files = (frozen or {}).get("files") or []
    if files:
        lines.append("- 凍ったテストのファイル（TDD のループが緑にした単位のテスト。上の名指しと範囲の外で書き換えると拒む。足しただけの"
                     f"新しいテストの関数は凍結に数えず、上の「足してよい新しいテスト」で照らす）: {_paths_line(files)}")
        if verified:
            lines.append(f"  - ループが書き換えて凍らせた名指し（上の名指しに在っても、もう変えるな）: {_paths_line(verified)}")
        unruled = frozen.get("unruled") or []
        if unruled:
            lines.append("  - 今の段の TDD のループが凍らせたファイル（裁定 fix_test_scope の範囲はこの周では凍結を解かない。上の名指しと"
                         f"範囲の相談の範囲の外で書き換えると拒む）: {_paths_line(unruled)}")
    return "\n".join(lines)


def check_paths(b, paths, *, items, ruled: bool = True, by: str = stopby.FIX, round_: int = 1) -> tuple[list[str], dict]:
    """承認済みの修正案の項目 items（approved に渡す値か口）で、単位に結べない変わったパス paths を、scope の値の outside で照らす
    （hint なし: 結ぶ単位を申告する欄の無い役）。合意・許し・裁定は置き場 b（conflict の置き場）から読む。
    返り (外れの行, 記録 {checked, items | why})"""
    got, why = scope(b, items=items, ruled=ruled, by=by, round_=round_)
    if got is None:
        return [], {"checked": False, "why": why}
    lines = outside(got["items"], sorted(paths), got["permits"], hint=False)
    return lines, {"checked": True, "items": [it.get("item") for it in got["items"]]}
