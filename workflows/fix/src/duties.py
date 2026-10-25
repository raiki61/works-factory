"""確かめの表（docs/plans/2026-10-24-fix-weapons.md の 2.4。箱の共通の義務 + 型の義務の 2 層。型を問わない部品）。

型の名から箱を引く表 BOXES と、箱の義務の表 BOX_DUTIES・型の義務の表（型のモジュールの DUTIES）をここ 1 か所に置く。共通の
受け付けが型の名で枝分かれするのは、この表を引く check の 1 か所だけ。型の義務の関数は箱の義務の結果を受け取らない（例外を書く口が
API に無い。憲法の 6）: check は「箱の義務の問題 + 型の義務の問題」を並べるだけで、どちらも問題を足すことしかできない。

どの関数も単位の事実 facts（受け付けが組む dict。下の FACTS）だけを読み、yes/no で問題の文を返す。表の行に載せた関数だけが受け付けで
効く。PR A は機械が自分で決められる照らしだけを表に置き、書き手が返す証拠（evidence.named・kinds・sites の at・fixed_by・test）が
要る照らしは、関数と試験を置いて PR B で表に足す（docs/plans/2026-10-25-fix-weapons-stage1-a.md の 3）。

FACTS（単位ごと）: unit（単位の key）・weapon・files（単位の行の files。根からの相対）・test_files（その中の試験のファイル。
impact.is_test_file）・kinds（files の rules.kind_of の集まり）・allowed_kinds（static の注文の変えてよい種類）・why_untested・
added（足した試験の id）・vanished（元で通っていて返した木の同じ選びの回に居ない試験の鍵）・permits（注文の permits の行）・
no_tests（base.json の印）・absent_at_base（files のうち起点の木に無いパス）・twice（足した試験を起点の木で 2 回走らせた問題の文の並び。
走らせていなければ None）・named・before・after・removes・gone・sites・kinds_rows・red_seen（単位の行の sites のどれかが赤を見た）。
"""
from __future__ import annotations

from src import pin, rebuild, remove, static, tdd, tidy, variant

BOXES = {"tdd": "change", "variant": "change", "remove": "change", "tidy": "keep", "rebuild": "keep", "pin": "keep",
         "static": "outside"}   # 型の名（と下ごしらえの名 pin）→ 箱。注文に箱の欄を持たない
MODULES = {"tdd": tdd, "variant": variant, "remove": remove, "static": static, "tidy": tidy, "pin": pin, "rebuild": rebuild}
WEAPONS = tuple(BOXES)
REJECT = "型 {weapon} の単位 {unit} の義務: {text}"


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


def keep_same_result(f: dict) -> list:
    """変えない段の箱の義務（2.4 の同じ結果の照らしのうち、居なくなった試験）: 起点で通っていて返した木の同じ選びの回に居ない試験は、
    どれも permits の remove の行の中（受け付けの新しい赤の照らしは今の selected_problems が持つ）"""
    allowed = {r.get("test") for r in f.get("permits") or [] if r.get("kind") == "remove"}
    gone = [k for k in f.get("vanished") or [] if k not in allowed]
    return [f"起点で通っていた試験が返した木で居なくなった: {gone[:10]}（振る舞いを変えない段は試験を消さない。消すのは消す名の許しの中だけ）"] \
        if gone else []


BOX_DUTIES = {"change": (), "keep": (keep_same_result,), "outside": ()}   # PR B で change に change_named_or_gone を足す


def check(weapon: str, facts: dict) -> list:
    """型 weapon の単位の事実 facts を、箱の義務と型の義務の表で照らした問題の文（空なら通る）"""
    out = [t for fn in BOX_DUTIES[box_of(weapon)] for t in fn(facts)]
    out += [t for fn in MODULES[weapon].DUTIES for t in fn(facts)]
    return [REJECT.format(weapon=weapon, unit=facts.get("unit", ""), text=t) for t in out]
