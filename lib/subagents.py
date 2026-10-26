"""書き手が項目ごとに起こす下請け（実装役と審査役）の値の関数（docs/plans/2026-10-24-fix-weapons.md の 11.4 の 5・11.6 の D2・11.8 の決め案 B）。下請けを起こす型は、tdd の閉じの書き手の外の 5 つ
（variant・remove・pin・tidy・static。書き手の block の表 src/render.py の SPAWNS が真）で、この module は型を問わず同じ組み方をする。

下請けの実装役は借りた superpowers の implementer の型、審査役は task-review の型を改変せずに渡される。この module は、型の穴に入れる値
（項目ごとの題・brief のファイル・審査役の差分のコマンド・修正前の版）と、修正役の指示の `{g1_items}` の行を、slots の `subagents`（形
.shared/schemas/writer-slots.schema.json）から組む。pack の外の実行環境を知らない（E3。入力は引数、出力は返り値）: place のパスと、指示の md を組んだ字は呼び手（本体
.shared/writerblock.py が prompt.render_shared で組む）が引数で渡す。指示の文は持たない（憲法の 2。.shared/prompts/g1-*.md）。

slots の subagents（修正の block が組む。データだけ）の欄:
- owed: 下請けを起こす単位の key（TDD の輪が緑にした単位を除く）
- briefs: owed に当たる凍結した brief の行 [{item, file, unit_keys}]
- all_items: 凍結した brief の全部の項目の番号（案に載らない義務の単位の項目の番号を、最大の次から振る）
- seat_brief_rows: 直す義務の単位の brief を名指す行（空なら brief の無い run。実装役の [BRIEF_FILE] は判定のファイル）
- judgment_file・policy_path・base_rev・check_cmd・directory: 判定のファイル・方針の文書・修正前の版・範囲の相談の確かめのコマンド（空なら相談の節が無い）・作業ツリーの根

- entries(place, sub, ...) -> [{item, impl_file, review_file, base, patch, impl_template, review_template}]: 項目の順。項目は brief の行ごとに 1 つと、
  案のどの項目にも無い義務の単位ごとに 1 つ（判定のファイルを brief にする）。*_template は借りた型の穴を埋めた字（呼び手が g1-impl.md・
  g1-review.md の {template} に入れる）。写しが固定と合わなければ ValueError
- row(entry) -> str: 修正役の指示の下請けの項目の 1 行（項目の番号・2 つのファイル・審査役が見る差分を書くコマンド）
- diff_cmd(base, patch) -> str: 審査の前に修正役が走らせる、差分のファイルを書くコマンド
- SEAT_BRIEFS: 直す義務の単位の brief を名指すファイルの名（呼び手が seat_brief_rows から、brief の在る run だけ place に書く。実装役の
  [BRIEF_FILE] は項目ごとにその項目の brief のファイルで、このファイルは型の穴に入らない。元からそうだった）
"""
from __future__ import annotations

import pathlib
import shlex
import sys

sys.dont_write_bytecode = True

import planbrief  # noqa: E402  （項目の単位の書き方 unit_note）
import seat  # noqa: E402  （借りた型の穴を埋める seat.fill）

G1_IMPL, G1_REVIEW = "g1-impl-{n}.md", "g1-review-{n}.md"   # 下請けのファイル（置き場のファイル。n は項目の番号）
G1_PATCH_FILE = "g1-{n}.patch"   # 下請けの審査役の差分のファイル（置き場のファイル。修正役が G1_PATCH で書く）
# 審査役の型の `git diff [BASE_SHA]..[HEAD_SHA]` は、works が commit しないので作業ツリーと base の間の差分になる。[HEAD_SHA] は呼び手が
# 渡す字（g1-head-sha.md）で、型の範囲の字 <base>..<head> は <base> に直す（commit の範囲は空になる。Head の行にだけ残る。元 seat.G1_HEAD_SHA）
# 審査の前に修正役が走らせる差分のファイルのコマンド（元 seat.G1_PATCH）。{patch} は置き場の絶対パス（shell の字で囲んだ物）で、審査役の型の
# [DIFF_FILE] も同じパス。作業ツリーと base の差分と、未追跡の新しいファイルごとの全文の差分を書き、最後にそのパスを出す
# （最後の git diff --no-index は差分が在ると 1 を返すので、echo で終えて 0 にする）。最初の git diff が落ちれば 1 で終える
G1_PATCH = ('p={patch}; top="$(git rev-parse --show-toplevel)"; '
            'git -C "$top" -c core.quotePath=false diff {base} > "$p" || exit 1; '
            'git -C "$top" -c core.quotePath=false ls-files --others --exclude-standard | while IFS= read -r f; do '
            'git -C "$top" -c core.quotePath=false diff --no-index /dev/null "$f" >> "$p"; done; echo "$p"')
SEAT_BRIEFS = "seat-briefs.md"   # 直す義務の単位の brief を名指すファイル（置き場のファイル）
SCENE_HOLE = "[Scene-setting: where this fits, dependencies, architectural context]"   # 借りた implementer の型の穴の名


def _task(brief: dict, owed: list[str]) -> str:
    """下請けの実装役の型の [task name]: 修正案の項目の番号と、その項目のうち今直す単位（ほかの単位は『今は直すな』）"""
    return f"修正案の項目 {brief['item']}（直す義務の単位 {planbrief.unit_note(brief.get('unit_keys'), owed)}）"


def items(sub: dict, rest_title) -> list[tuple]:
    """下請けの項目 [(番号, brief のファイル, 実装役の型の [task name])]（項目の順）。どの項目にも無い直す義務の単位（brief の無い run は
    全部）は、判定のファイルを brief にした 1 単位 1 項目（番号は凍結した項目の最大の次から。題は rest_title(単位の key)。呼び手が md の
    g1-rest から組んだ字）"""
    owed = list(sub["owed"])
    mine = sub["briefs"]
    out = [(r["item"], r["file"], _task(r, owed)) for r in mine]
    covered = {k for r in mine for k in r["unit_keys"]}
    rest = [k for k in owed if k not in covered]
    first = max(sub["all_items"], default=0) + 1
    return out + [(first + i, sub["judgment_file"], rest_title(k)) for i, k in enumerate(rest)]


def diff_cmd(base: str, patch: str) -> str:
    """審査役に渡す差分のファイルを書くコマンド（G1_PATCH）"""
    return G1_PATCH.format(base=base, patch=shlex.quote(patch))


def row(entry: dict) -> str:
    """修正役の指示の下請けの項目の 1 行（元 seat._g1_row）"""
    return (f"項目 {entry['item']}: 実装役 {entry['impl_file']}・審査役 {entry['review_file']}・"
            f"差分のコマンド `{diff_cmd(entry['base'], entry['patch'])}`")


def entries(place, sub: dict, *, scene: str, impl_report: str, report: str, head_sha: str, rest_title) -> list[dict]:
    """項目ごとの下請けのファイルの名と、借りた型の穴を埋めた字。place は置き場。scene・impl_report・report・head_sha は呼び手が
    .shared/prompts の g1-scene・g1-impl-report・g1-report・g1-head-sha を組んだ字（前後の改行は外した物）。実装役の型の穴は
    [BRIEF_FILE]（その項目の brief）・[task name]（その項目の直す義務の単位）・[REPORT_FILE]（impl_report）・[directory]・scene、審査役の型の穴は
    [BRIEF_FILE]・[GLOBAL_CONSTRAINTS]（方針の文書。無ければ seat.NONE）・[REPORT_FILE]（report）・[BASE_SHA]（修正前の版）・[HEAD_SHA]
    （head_sha）・[DIFF_FILE]（place の g1-<n>.patch）。写しが固定と合わない・型の穴と値が違えば ValueError（seat.fill）"""
    place = pathlib.Path(place)
    common = {SCENE_HOLE: scene, "[directory]": sub["directory"]}
    base = sub["base_rev"]
    out = []
    for n, brief, task in items(sub, rest_title):
        patch = str(place / G1_PATCH_FILE.format(n=n))
        implementer = seat.fill("implementer", {**common, "[task name]": task, "[BRIEF_FILE]": brief,
                                                 "[REPORT_FILE]": impl_report})
        verdict = {"[BRIEF_FILE]": brief, "[GLOBAL_CONSTRAINTS]": sub["policy_path"] or seat.NONE, "[REPORT_FILE]": report, "[BASE_SHA]": base,
                   "[HEAD_SHA]": head_sha, "[DIFF_FILE]": patch}
        reviewer = seat.fill("task-review", verdict).replace(f"{base}..{head_sha}", base)
        out.append({"item": n, "impl_file": str(place / G1_IMPL.format(n=n)), "review_file": str(place / G1_REVIEW.format(n=n)),
                    "base": base, "patch": patch, "impl_template": implementer.rstrip("\n"), "review_template": reviewer.rstrip("\n")})
    return out
