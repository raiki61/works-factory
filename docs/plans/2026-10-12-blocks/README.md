<!-- coldwrite:skip 計画の目録。語は docs/design.md の「語」の節で定義 -->
# ブロック 8 本と前提の計画（2026-10-12）

8 つのブロック（judge・plan・plan-review・fix・test-gate・eyes・report・merge）を ASF の archon-ship で 1 run = 1 つの大きな PR で作るための issue の本文 8 本（`<ブロック>.md`）と、その前に入れる共有の部品の issue の本文 1 本（`prereq.md`）。持ち主の決め `overnight-speed` により、段 1 の歩く骨組みを待たずに回す（`docs/design.md` の「作りの順」の段 2）。

## 順

1. issue #47（P0。土台の足し。`docs/plans/2026-10-12-groundwork-line-launcher.md` の P0）が main に入る。
2. `prereq.md` の issue（2 つ以上のブロックが読む `lib/` の部品・`tests/workflows/__init__.py`・E13 の表の行・E4 の機械の pack の形）が main に入る。P0 も `tests/layers/scan.py` を触るので、P0 と同じ時に回さない。
3. 8 本を同時に回す。8 本は互いを待たず、同じファイルを作らない（各計画の「範囲」の終わりに、作るファイルの一覧が在る）。ほかのブロックの返りは線の `with:` から入力として届くだけで、各ブロックの試験はその形の入力を自分で作る。

線（A）と入口の殻（B）の計画は `docs/plans/2026-10-12-groundwork-line-launcher.md`。8 本とは互いを待たない。

## 守りのパスの文書の直し（この計画を置いた commit で入れた物）

8 本と前提の計画が「前に入る人の直し」として頼る物は、全部この計画を置いた commit で入れてある。中身はリポジトリのその場所を読む。

- H1 ブロックの試験の置き場 `tests/workflows/`: 根の `AGENTS.md` の「リポジトリの形」・`tests/AGENTS.md` の「置き場」・`docs/owner-decisions.md` の「2026-10-11 の決めから導いた事」。
- H2 report の `outcome_field: ok`（boolean）と、Archon の `outcome_field` が boolean しか受けない事実: `docs/design.md` の「report の返り」と「Archon の分かっていること」。
- H3 段 2 の共通の受け入れ 4・5 を PR の本文に書く: `docs/design.md` の「作りの順」。
- H4 E13 の例外（持ってきた言語の表。6 つのファイルに限る）: 根の `AGENTS.md` の E13・`tests/layers/scan.py` の `E13_TABLES`・`docs/owner-decisions.md` の「導いた事」（持ち主の確かめ待ちの仮の判断）。
- H5 ブロックをまたぐ形（指し札の先・隣のファイル・直す前の結末のファイル・`conflicts.json`・型つきの成果物・関所の語・約束に無い入力・返す節は落ちない）: `docs/design.md` の「ブロックの返りの約束」の「書き方の決め」。
- H6 `docs/asf-notes.md` の A4 の採った先を E5 に合わせる（report の計画の直し）。
- H7 始めの記録の `tdd_suite`: `docs/design.md` の「線の始めの節 `start` の返り」。
- H8 R2 の `unverifiable`・merge の入力 `r2`・null 可の `diff`: `docs/design.md` の「eyes の返り」「merge の返り」。
- H9 段 2 を archon-ship で段 1 を待たずに回す: `docs/design.md` の「作りの順」の段 2 の頭。
- H10 E16 の機械の行（差し込まれるブロックは工程の頭に `interactive` などを書かない）: `workflows/AGENTS.md`。
- ブロックごとの直し: judge の E7 の例外（`workflows/AGENTS.md`）と入力 `prior_failures`、plan の入力 `conflicts` と `ready` の文、plan-review の入力 `start`・`answers`・`ruling` と棚卸しの行、fix の include `refix` と入力 `only_items` ほか、eyes の入力 `start`・`plan_questions`・`answers` と段 2 の文。どれも `docs/design.md`。E4 の機械の行の字も pack の形に直した（`workflows/AGENTS.md`。機械は `prereq.md` の 4）。

入れていない物:

- judge の計画の直し 2（仕様の受け入れテストの改変の照らし `spec.check` の置き先）: 置き先のブロックが決まって、そのブロックが作るまで入れない。今の 8 本の中では落ちている能力。
- fix の計画の直し 2（U8 の実測で駄目だった時の埋め）: fix の PR に結果を書き、土台の持ち主が `docs/polyfills.md` の行にするかを決める。
- merge の計画の直し 1 の「線の `merge-apply` の `with:` にも」: 線の YAML はまだ無い。線の issue が `docs/design.md` の約束から書く。

## 持ち主の確かめ待ち

再審（judge）・案の直し（plan）・範囲の相談の答えと 2 度目の修正（fix）を、前の役の会話の続きでなく、保存した返答を読む新しい会話で回す。仮の判断として `docs/owner-decisions.md` の「2026-10-11 の決めから導いた事」に書いた。違う答えなら judge・plan・fix の計画のその節だけを差し替える。
