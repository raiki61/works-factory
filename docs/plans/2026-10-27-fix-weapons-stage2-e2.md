# 直し方の型の段 2・PR E2 の控え（TDD の輪を block `weapon-tdd` へ出す。受付 20261026-212457-df5027）

読む人と使い方: PR E2（「直し方の型の段 2」〔正本の 11 章。直し方の型を 1 つずつ block に上げる段〕の PR の 1 本の名で、PR の番号ではない。前の 1 本が E1）を実装する人と審査する人が、設計の正本と並べて読む実装の控え（記録を兼ねる）。決めは済んでいて、読む人に判断を求める所は無い。中身は 3 つ: 1 節が「`src/common.py` などの関数をどこへ移すか」の数えの結果、2 節が正本の字だけでは書けなかった所の決め 12 個、3 節が commit の切り方。

設計の正本は `docs/plans/2026-10-24-fix-weapons.md`（以下「正本」）の 11.6 の「E2 `weapon-tdd`」（と、そこが引く 11.1 の 3・7、11.3 の返す節、11.4 の 3、11.9 の 3、11.10、3.1 の「許しの読み」、`docs/design/README.md` の 4.3）。この控えは、正本が実装の頭に回した決め（11.9 の 3）と、正本の字だけでは書けなかった所の決めを書く。この控えが名指す関数・欄と 1 節の数えは、枝 `weapons-stage2-e2` の頭（E1 の head `621e7acb`。#885 のレビューの直しの後）のコードの物。

語（このリポジトリの言い回し。詳しくは `AGENTS.md` と正本の「語」の章）:

- Archon: works-factory が上で動く、AI の処理をグラフにして YAML で書いて回す外の道具。`loop_group` の `max_iterations`（周の上限）・`trigger_rule`・`context: fresh` などは Archon の YAML の鍵。
- block: `workflows/<名>/` のフォルダ 1 つにまとめた処理の一区画（YAML 1 本と、その script・指示・形）。宣言した入出力（port）だけで受け渡しし、ほかの block の置き場を開けない。「修正の block」は `workflows/fix/`、「`weapon-tdd`」は E2 で新しく作る TDD の block。
- 置き場（place）: block ごとの作業のファイルを書くフォルダ。
- 輪: TDD の繰り返し（赤・緑・整えの段を単位ごとに回す loop）。「輪の状態」は輪が回る間に読み書きする `tdd-<k>/state.json`、「輪の記録」は輪が抜ける時に書く `tdd-<k>/record.json`（E1 で作った。輪の外はこちらだけを読む）。
- 単位: 直す義務の 1 つ（鍵 `unit_key` で名指す）。組: 一緒に直す単位のまとまりで、組ごとに輪を回す。「落ちた組」は失敗で終わった組。
- 振り分け: 輪の前の段で、単位ごとに tdd（試験を先に書く）か direct（試験を書かずに直す）かを AI が決める役（`route`）。
- 注文: 修正の block の node `orders` が型ごとに書く `orders/<型>.json`。型の block（`weapon-tdd` など）が受け取る入力で、「注文の欄」はその JSON の鍵（例 `tdd`）。
- 申し出: 書き手（直す役の AI）が「この単位は自分では直せない」「依頼とぶつかる」と止めて出す依頼。今は `conflicts.json` に流し（書き出し）、組の後で裁かれる。
- 錨: YAML の anchor（`&名` で置き `*名`・`<<: *名` で使う）。「起こし方の錨」は AI の node の起こし方の鍵（`model`・`allowed_tools` など）をまとめた `tdd_launch`。
- 作る物 1〜6: 正本 11.6 の「E2 `weapon-tdd`」の「作る物」の番号付きの一覧（1 は `workflows/weapon-tdd/` の新設、2 は移す物、3 は申し出の流し、4 は修正の block の直し、5 は決まりと設計書、6 は振り分けと TDD の役で同じ物を 2 か所に持たない形）。
- E13: `AGENTS.md` の決まりの 1 つ（指示と `lib/` に特定の言語・テストの実行器の名を書かない。拡張子と言語の表は `lib/impact.py` などに限って置いてよい）。
- 下書き: 正本そのもの（正本は自分を「下書き」と呼ぶ）。主に 11.6 の E2 と 11.9 の 3 の字。この控えが下書きから変えた所は、その場で訳を書く。
- 訳: 理由のこと（翻訳ではない）。

## 1 頭の数え（11.9 の 3。`src/common.py`・`rules.kinds_*` の行き先）

数え方: `workflows/fix/` の `src/`・`scripts/` を ast で読み、`common.<名>`・`from src.common import <名>` の参照を集めた。輪の側は `src/tdd.py` の輪の中身（この節の終わりの箇条「`src/tdd.py` の中で修正の block に残す物」に挙げた物の外の関数と定数）・`scripts/tdd_prep.py`・`tdd_step.py`・`prompts.tdd_values`。ほかは修正の block の側。`common.py` の中の呼びは閉包で辿った（輪が使う関数が中で呼ぶ物も輪の側に数える）。

| 行き先 | 数 |
| --- | --- |
| 両方（`lib/loopkit.py` へ） | 41 |
| 輪だけ（`weapon-tdd/src/` へ） | 0 |
| 修正の block だけ（`common.py` に残す） | 59 |

- 両方の 41: `Broken`・`GATE_ON`・`GATE_OFF`・`MIN_WHY`・`MIN_QUOTE`・`QUOTES_FIELD`・`UNSENT`・`PYTEST_FILE`・`rules`・`snapshot`・`touched`・`restore`・`restore_paths`・`hashes`・`red_check`・`_quote_target`・`_quote_problem`・`_key`・`_abs_ids`・`_abs_paths`・`_id_base`・`_norm_id`・`id_path`・`_unnamed_edits`・`_verified`・`_load`・`_save`・`load_state`・`_owed`・`_unit`・`_blank`・`_cmd_run`・`_cmd_material`・`_reached`・`_contract`・`_plan_tdd`・`_mark_parked`・`flush_unsent`・`flush_claims`・`retry_max`・`conflict_item`。
  - 訳: 輪の中で使う部品は、どれも振り分け（`src/route.py`。修正の block に残る）か受け付け・事後の関門（`gates.py`・`board.py`・`facts.py`・`duties.py`）も使う。振り分けは輪と同じ形の状態（`route.json`）を同じ部品で回すので、輪だけの物が残らない。
  - 下書きは「両方が多ければ 2 つに分けるか（版の写しと戻し・赤の判定）」を問うた。1 つ（`lib/loopkit.py`）にする。訳: 41 の名は互いに呼び合い（`red_check` が `_quote_*`・`rules`、`_reached` が `_abs_*`、`conflict_item` が `_owed`）、割ると 2 つのモジュールが互いを import する。使い手も同じ 2 つ（修正の block と `weapon-tdd`）。
- 同じ数え方で、修正の block の外の部品のうち輪が使う物: `board.test_file`・`board.unit_test_files`（`join.py`・`clash.py`・`finish.py` も使う）→ `lib/loopkit.py`。`board.judge_query` の本体（判定の写しと置き換えた問いから `querytest.judge_hits` を組む所）→ `lib/querytest.py` の新しい口（置き場の名 `JUDGMENT_FILE` は修正の block に残し、パスで受ける）。`rules.brief_rows` → `lib/planbrief.py`（輪の周ごとの brief の行。修正の block の書き手と下請けも使う）。
- 証拠の種類の数え: `rules.kinds_now`・`kinds_for`・`remember` と、それが呼ぶ `unit_paths`・`changed_paths`・`select_kinds`・`delivered`・`iteration_next`・`KINDS`・`PATH_TOKEN`、`prompts._kinds_when`（と `WRITER_KINDS`）は、修正の block（書き手の slots・振り分け）と輪の両方が使う → 新しい `lib/evidencekinds.py`。
  - 外す物: `rules.kind_of` と拡張子の表（`CODE_SUFFIXES` など）は `lib/impact.py` へ（E13 の例外のファイル。`lib/` の新しいモジュールに拡張子と言語の表を置けない。`CODE_SUFFIXES` の `.java`・`.php` などは E13 の機械の語の表にも当たる）。
- `src/tdd.py` の中で修正の block に残す物（輪の外が呼ぶ・輪の状態を作る前の計算）: `_open_units`・`_duty`・`plan_contract`・`_light_units`・`new_state`・`start`・`BASE_FIELDS`・`ROUTE_CARRY`・`ROUTES`・`PLAN_*`（振り分けの状態と注文の種を作る。`src/route.py` へ）、`green_units`・`exit_fields`・`refused_units`・`ROUTE_REFUSED`（輪の記録の読み手。`src/tdd.py` に義務の表 `DUTIES`・`BOX` と残す）。
  - 下書きの「E2 の後の `src/tdd.py` は義務の表だけ」から変えた訳: 記録の読み手 3 つは修正の block だけが使い（`fix_prep`・`group_end`・`finish`）、輪の記録の形（`.shared/schemas/tdd-record.schema.json`）を読む側。義務の表のモジュールに置けば `test_weapon_imports.py` の照らす名も変わらない。

## 2 正本の字だけでは書けなかった所の決め

1. 注文の欄 `orders.tdd` を広げる。輪の頭 `tdd-start` は今の `open_state`・`assign` と同じ状態を作るが、`open_state` は修正の block の置き場（関所の答え・裁定・凍結した欄）を読む。block の外の置き場は開けない（README 4.3）ので、`orders` が今と同じに計算した値を注文に書く: E1 の `iterations`・`calls`・`kinds` に、`open_units`（振る義務の単位）・`excused`（外れた単位と訳）・`contract`（`plan_contract` の結果。下書きの「単位の約束」）・`routed`（振り分けの結果。`ROUTE_CARRY` のうち `order`・`units`〔`route`・`why`・`gave_up`〕・`parked`・`parked_why`・`note`・`handoff` と段。振り分けを起こさなかった組は null）・`routes`・`whys`（`assign` に渡す単位ごとの道と訳）を足す。どれも形に全部書く（7.1 の 11）。
   - 振り分けの `unsent` は運ばない。`route-step` が周ごとに流し終えているので、`orders` は空でなければ落ちる（黙って捨てない）。
   - 状態の骨（`new_state` の辞書の鍵の並び）は `lib/loopkit.py` の 1 つの関数に置き、振り分けの `new_state`（修正の block）と `tdd-start`（`weapon-tdd`）がそれを呼ぶ（同じ形を 2 か所に書かない）。
2. `context`（`.shared/schemas/tdd-context.schema.json`）の欄: 下書きの欄に、輪の中が修正の block の置き場から読んでいた物を足す。
   - 材料 `material {values, when}`: `prompts` の新しい 1 つの関数（下書きの「run の材料の部」。正本 11.6 の E2 の作る物 6 が挙げる、判定・修正案・方針・依頼・notes のパス・`lang`・`tests_how`・借りた座の `skill`〔座は `lib/seat.py` の語で、借りた superpowers〔`lib/borrow/`〕の節を役の指示に載せる口。`skill` はその役に Skill の道具で読ませる借りたスキルの名〕など、run ごとに決まる指示の材料）の返り。振り分けの指示も同じ返りから組む。
   - 生の値: `judgment_file`・`request_file`（種類の数えと申し出の名指しの根に使う。指示用の `shown()` の字と分ける）・`base_rev`・`user_env_dir`（`tdd-step` が対象のテストに Archon の変数を継がせない口）。
   - `briefs`（凍結した brief の行。`orders` が `planbrief.cut_at` で切る）・`briefs_by_unit`（`planbrief.by_unit_at` の行。申し出の brief の照らしと諦めの申し出の名指し）・`cite_root`（申し出の名指しを許す作業ツリーと依頼のファイルの外の根。今は輪の状態の置き場の親）・`replaced_queries`（裁定が置き換えた問い。`querytest` の口に渡す）。
   - `light`（緑の後の test_cmd を走らせない単位）。下書きの `skip_rerun` は `light` の元で、輪は `light` しか読まないので欄にしない。
3. tdd の単位が無く振り分けを起こした組（E1 の未確認点 1）: 今は `orders` が輪の状態を作り、`assign` がすぐ済ませて `record.json`（振り分けの呼び `calls`・direct の単位の行・止めた単位）を書く。E2 ではこの組に tdd の注文が無い（注文の `units` は 1 つ以上）ので `weapon-tdd` を起こさず、`orders` が同じ記録を `tdd-<k>/record.json` に書く。記録の中身を作る `record`・出口の行 `exit_rows` は状態の写しだけの関数なので `lib/loopkit.py` に置き、輪と `orders` が同じ関数で書く。要約 `summary.md` はこの組では書かない（読むのは tdd の閉じの書き手だけで、tdd の注文の無い組には起きない）。記録の `summary` は空の字。最後の承認の `tdd_refused` は今と同じに振り分けの拒否を数える。
4. 出口の欄 `tdd`（`exit_fields`）: 今は組の終わりが輪の状態を読む。E2 では輪の記録に欄 `exit`（今の `exit_fields` のうち輪の状態から組む部分）を足し、`exit_fields` は記録を読んで組の頭の印（`no_suite`・`suite_broken`）を重ねる。照らす事は変えない（同じ値を記録から読む）。
5. 修正の block の `tdd-start.json` の `state_file` は、`tdd-take` が写した記録 `tdd-<k>/record.json` のパスにする（鍵の名は今のまま。読み手 `board.loop_files` はその隣の記録を読むので、記録そのものでも同じ所に当たる）。E1 の `finish._frozen` の `state` と同じ扱い。
6. `orders` の返りの `tdd` は「`weapon-tdd` を起こすか」の真偽（tdd の単位が在る組）にする。今は「輪の状態が済んでいないか」で、tdd の単位の在る組では同じ値になる。
7. 申し出: 輪は止めた申し出を状態の `unsent` に積むだけにする（`tdd-step` は流さない）。`tdd-out` が状態の `unsent` を返し、`tdd-take` が今の `common.flush_unsent` と同じ口（`rulings.park`）で流す。
8. TDD の役の照らし（下書きの縛る試験。`tests/workflows/test_weapon_blocks.py` に足す物で、振り分けの `route` と輪の `tdd`・`tdd-new` の 3 つの AI の node が、同じ起こし方の鍵〔起こし方の錨 `tdd_launch` の中身〕と同じ返答の形を持つことを照らす。node どうしで違ってよい鍵は比べない。下書きはその「比べないつなぎの鍵」を `id`・`description`・`prompt`・`depends_on`・`when` とした）: 比べないつなぎの鍵に `trigger_rule`・`context` も入れる（`tdd-new` だけが `trigger_rule`・`context: fresh` を持ち、どちらも起こし方の錨 `tdd_launch` の外の鍵なので、比べると 3 つが等しくならない）。`output_format` は形のファイルとの比べで別に照らす。
9. `current_lines` の段 `route` の枝は振り分け（`src/route.py`）へ移す。輪の状態の段は `tdd-start` の後いつも test・fix・refactor か済みで、route の枝は振り分けでしか通らない。`tdd_values` の段 `route` の枝も同じ。
10. `conflict_item` は置き場を状態から引かず、`request_file`・`cite_root`・`briefs_by_unit` を引数で受ける（振り分けは修正の block の置き場の値、輪は `context` の値を渡す）。
11. 輪が done にならずに loop を抜けた時（E1 の PR のレビュー a28320 が E2 へ申し送った 2 つ目の点。`tdd-step` が落ちた・Archon の `max_iterations` に輪の数えより先に届いた）: 記録 `record.json` が無いので、`tdd-out` は `ok: false` と訳（「輪の記録が無い（輪が済まずに抜けた）」）を返し、`tdd-take` は修正の block の置き場に何も書かずに落ちる。組は落ちた組として終わる。今は記録が無いまま次の段の書き手の輪（`writers-loop`。輪の後に、書き手の型〔tdd の閉じ・variant など〕の AI が直す loop）へ進む。輪の外は輪の記録だけを読むので、その輪の分が誰にも告げられずに抜け落ちる: 最後の承認（メイングラフ line の終わりの、直しを出す前の承認の段）に出す欄 `tdd_refused`（`finish._tdd_refused`。記録の `calls` から修正役が拒まれた単位を数える）にその輪の拒まれた単位が入らず、足跡 `parking.footprint`（単位ごとに触ったファイルの組。記録の単位ごとの `files`・`test_files` から組む）にその輪が触ったファイルが入らない。E2 では黙って漏らさず止める（上のとおり `tdd-take` が落ちて組が落ちる。守りが強まる向き）。輪の数えの上限 40（`MAX_ITERATIONS`）と YAML の `max_iterations: 40` は同じ値で、輪の数えが先に届いて done を書くので、ふだんは起きない。
12. 注文の欄 `tdd` の数え（レビュー a28320 が申し送った 1 つ目の点）: E1 では `orders.compute` が同じ処理の中で計算した値（振り分けの周の数・呼びの控え・渡した証拠の種類）をそのまま `open_state(counted=)` に渡して輪の状態を作り、注文 `orders/tdd.json` の欄 `tdd` には同じ値を書くだけで、誰も読まなかった。E2 では `tdd-start` が注文の欄 `tdd` から読んで輪を始める（この節の 1）。試験の助け（`tests/blocks/fix/steps.py`。試験の中で `orders` の node と同じ口を呼んで輪を 1 歩ずつ進める関数）も、計算した値を直に渡すのをやめ、注文の欄から輪を始める形にする。


## 3 切り方（commit）

0. 割る前の字の控えの試験（golden）。今の形で緑を確かめてから次へ。
1. 段 A: `lib/loopkit.py`・`lib/evidencekinds.py`・`impact`・`planbrief`・`querytest` への切り出しと、指示の値の組み立ての割り（材料・振り分け・輪）。修正の block の中で振る舞いを変えない。
2. 段 B: `weapon-tdd` の block（正本 11.6 の E2 の作る物 1・2）・申し出の流し（作る物 3）・`orders`・`tdd-take`・YAML（作る物 4）・試験の移し。
3. 段 C: 決まりと設計書（作る物 5）・TDD の役の照らし（2 節の 8）・E1 の縛る試験 3（正本 11.6 の E1 の縛る試験の 3。輪の外の `src/`・`scripts/` が輪の状態のファイルの名を名指さないことを見る yes/no の試験。E2 では block の形の検査が代わりに照らす）を消す。
