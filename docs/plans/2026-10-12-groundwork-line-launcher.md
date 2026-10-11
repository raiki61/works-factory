<!-- coldwrite:skip ASF の役が読む作業の計画。語は docs/design.md の「語」の節で定義 -->
# 土台の足し・線・入口の殻の計画（2026-10-12）

土台の計画 `docs/plans/2026-10-11-foundation.md` の Task 3b・4・5 の中身の正本。各節が 1 つの issue と 1 つの PR になる。P0 を先に main に入れ、その後 A・B と 8 つのブロックの issue は互いを待たない。事前審査（今の works の計画の審査の指示書 p2.plan_review）を通してある。

# P0 土台の足し: 自分の工程を pack の形で読ませ、script が lib/ を見つける道（U5）と、Archon の要る試験の助け・CI の源を先に置く

### このリポジトリと、この issue の位置

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。これから、線（`workflows/line/`）の issue、入口の殻（`bin/works-factory`）の issue、8 つのブロック（`workflows/<ブロック>/`）の issue を同時に回す。どれも次の 3 つを要るのに、今の main には無いか、Archon の振る舞いと合っていない。それを先に 1 つの小さな PR で置き、後の issue が互いを待たないようにする。

1. ブロックの `scripts/` の script が、名前で呼べない。止めた Archon（`factory/pack.json` が名指す commit の Archon の源。`docs/design.md` の「語」）は、名前で指す script を「pack の形」の工程（`<.archon/workflows>/<pack>/<工程のフォルダ>/scripts/`）の時だけ工程のフォルダの `scripts/` から探し、ほかの工程は `<対象>/.archon/scripts/` から探す（止めた Archon の文書 `guides/script-nodes.md` の「Named Script Resolution」、`packages/workflows/src/script-discovery.ts` 151-222 行）。pack の共有の部品も `<pack>/.shared/` だけ（同じ文書の「Share code within a pack」）。今の `bin/_lib/place.py` の `workflow_source` は `<置き場>/.archon/workflows` を `workflows/` へ直に向けるので、`workflows/line/` などは pack でなく深さ 1 の平らな工程になり、`scripts/` も `.shared/` も効かない。
2. script が `lib/` を見つける道（`docs/design.md` の未決 U5）が決まっていない。Archon は run の始めに工程のフォルダを写し取り、script はその写しから走るので、リポジトリからの相対では `lib/` に届かない。
3. Archon を要る試験（`archon validate`・`workflow test`）の助けが無く、CI（`.github/workflows/tests.yml`）は Archon の源を取らないので、そういう試験はいつも見送られる（土台の計画の「全体の決まり」に「段 1 で CI が源を取るようにする予定」と在る）。

読む物: 根の `AGENTS.md`・`workflows/AGENTS.md`（E1・E2）・`bin/AGENTS.md`（E15）・`tests/AGENTS.md`、`docs/design.md` の「pack.json」の節と U5、`docs/polyfills.md` の P3、`bin/_lib/place.py`・`tests/bin/test_place.py`・`workflows/.shared/boundary.py`。

### 置く・変えるファイル

- `bin/_lib/place.py`: `workflow_source` の symlink を `<置き場>/.archon/workflows/works-factory` → リポジトリの `workflows/` に変える（pack の名は `pack.json` の `ours` に `pack: "works-factory"` を足して読む）。キャッシュの置き場を決める `cache_dir(env) -> Path`（`${XDG_CACHE_HOME:-<HOME>/.cache}/works-factory`）を足し、入口の殻と CI がこれを使う。
- `pack.json`（`ours.pack`）
- `tests/bin/test_place.py`（置き場の形の試験を直す）・`tests/shared/test_archon_contract.py`（源の見つけ方を `tests/archon.py` に寄せる。照らす行の表は変えない）
- `workflows/.shared/boundary.py` の `lib_root()`: 環境変数 `WORKS_FACTORY_ROOT` が在ればその `lib/`、無ければ今どおり自分の置き場から辿った `lib/`。`tests/shared/test_boundary.py` に試験を足す。
- `tests/archon.py`（新）: 止めた Archon の源と `bun` を見つけ、無ければ `case.skipTest("Archon の源が無い: <何が無いか>")` で見送る助け。源の置き場は、main の `tests/shared/test_archon_contract.py` の `pinned_source` の決まりをそのまま移す（環境変数 `WORKS_FACTORY_ARCHON_CACHE` か `<cache>/archon/<commit>` が無い時だけ見送り、壊れた源は赤。`place.cache_dir` には戻らない。#47 の持ち主の決め。手元で入口の殻と源を分け合うなら `cache_dir` の値を `WORKS_FACTORY_ARCHON_CACHE` に渡す。置き場の形の持ち主は `place.py` だけ）。`test_archon_contract.py` も同じ助けを使うように直す（同じ決まりを 2 か所に持たない）。使い捨ての git の木を組む助け（中の `.archon/workflows/works-factory/` に、名指した工程のフォルダと `.shared/` を写して commit する。使い捨ての `ARCHON_HOME` と `WORKS_FACTORY_ROOT` をつけて Archon を起こす）。
- `tests/layers/test_no_conversion.py`（E1）・`tests/layers/test_archon_validate.py`（E1）と `scan.py` の足し
- `.github/workflows/tests.yml`: 止めた Archon の源を取る段（`place.archon_source` を呼ぶ小さな命令。源は `factory/pack.json` の commit を鍵に actions のキャッシュに置き、`WORKS_FACTORY_ARCHON_CACHE` を立てる。これで PR #40 の照らしの試験も CI で見送られなくなる）と、bun を入れる段（版は取った源の `package.json` の `engines.bun` から読む。CI の YAML に版を写さない）
- `docs/design.md`: 「pack.json」の節の 3（置き場の形）・U5 の決め・段 2 の共通の受け入れ 3（`archon validate workflows` を「自分のブロックだけを置いた使い捨ての木で、`tests/archon.py` の助けで」に直す）。`docs/polyfills.md` の P3 の「埋め」の行（置き場の形）。`workflows/AGENTS.md` の E1 の「`.archon/workflows` がこのフォルダを指す」を pack の形に直す。
- `docs/plans/2026-10-11-foundation.md` の「全体の決まり」の CI の行

### 約束

- `test_archon_validate.py`: `tests/archon.py` の木に `workflows/` の全部（線と在るブロック）を置いて `archon validate workflows` を回し、`works-factory-*` の誤りと警告が無いこと。ただし線が `include:` する工程が 1 つでも木に無い間は、線の行だけを `include target … not found` の誤りに限って数えず、無い工程の名を並べて名前つきで見送る（`skipTest("ブロックがまだ無い: judge, plan")` の形で、ほかの工程は照らし続ける）。
- `test_no_conversion.py`: `place.workflow_source` の置き場から Archon が読む所（`.archon/workflows/works-factory/` の下）の全部のファイルが、`workflows/` とバイトで同じ。
- `place.workflow_source` の置き場の形を変えた時、前の形の置き場（`.archon/workflows` が直に `workflows/` を指す symlink）が在れば、消して回し直す案内つきの 1 行で止まる（今の `workflow_source` の FileExistsError の扱いと同じ）。

### 手順（試験が先に赤）

1. 試験を書く（`test_place.py` の置き場の形・`test_boundary.py` の `WORKS_FACTORY_ROOT`・`test_no_conversion.py`・`test_archon_validate.py`）。赤を見る。
2. 試験の木で、pack の形にした置き場の工程の `scripts/` の名前の script と `.shared/` の部品が読めることを、`archon validate workflows` で確かめる試験を 1 つ足す（小さな工程 1 つと `scripts/hello.py` を使い捨ての木に置く。`validate` は見つからない名前の script を誤りにする（止めた Archon の `validator.ts` 905-911 行））。
3. 実装して緑。
4. CI に源と bun を足し、CI の記録で Archon の要る試験が見送られていないことを確かめる。
5. 全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。

### 受け入れ

- 1・2 の試験が先に赤で入り、後で緑。
- 全部の試験が緑。手元で源か bun が無い時は Archon の要る試験だけが名前つきで見送られ、CI では見送られない。
- 層の試験（E1〜E18 の機械の行）が緑。

### 範囲（触らない物）

- `workflows/line/`・`workflows/<ブロック>/`・`lib/`・`bin/works-factory`（線・ブロック・入口の殻の issue）。

### 後の issue との関係

- 線の issue・入口の殻の issue・8 つのブロックの issue は、この PR が main に入ってから始める（どれも名前の script と `tests/archon.py` を使う）。この PR の後は互いを待たない。
- ブロックの issue の筋書きの試験は、`tests/archon.py` の木に自分のブロックだけを置いて回す（`workflow test` は見つけた工程のどれか 1 つでも読み込めなければ 1 で終わる。止めた Archon の `packages/cli/src/commands/workflow.ts` 1424-1430 行。線が先に main に入ると、ブロックが揃うまで線は読み込めない）。

### E11 の 3 つ

1. Archon が持つ物: pack の形の script と `.shared/` の探し方。それに合わせるだけで、新しい仕組みは足さない。
2. ASF が持つ物: ASF の工程は同じ pack の形（`.archon/workflows/sdlc/<工程>/scripts/`）。
3. 要るか: ブロックの script（E4）と境の口（E2）が動くための前提。

# A 線: workflows/line/works-factory-line.yaml を、ブロックの返りの約束に合わせて書き、代わりのブロックで筋書きを確かめる（土台の計画 Task 4）

### このリポジトリと、この issue の位置

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ `raiki61/claude-plugins` の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）の古い線は `works/darkfactory/darkfactory.yaml` で、その判断の多くは境の節（`h-*`。`works/darkfactory/lib/line_edge.py`）と盤面（今の works が自前で持った run の状態のファイル）に寄っていた。この issue は、新しい線 `workflows/line/works-factory-line.yaml` を、8 つのブロック（judge・plan・plan-review・fix・test-gate・eyes・report・merge）を `include:` で並べる形で書く。8 つのブロックは別の issue が同時に作っている。だから線は `docs/design.md` の「ブロックの返りの約束」の節だけを読んで書き、ブロックの代わり（代わりのブロック。下の語）で Archon の筋書きの試験（fixture）を回して確かめる。線の script は筋書きの中で本当に走らせる。本物のブロックが揃ったら、Archon の `validate`（土台の足しの issue が置く `tests/layers/test_archon_validate.py`）が線の読む欄をブロックの返す節の `output_format` と照らす。

読む物: 根の `AGENTS.md`・`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16）・`lib/AGENTS.md`（E3）・`tests/AGENTS.md`、`docs/design.md` の「線」「ブロックの返りの約束」「Archon の分かっていること」、`docs/owner-decisions.md` の `report-on-stop`・`asf-way-gates-fanout`・`no-queue`・`io-in-output-format`・`lib-port-as-is`・`unattended`・`gates` と「2026-10-11 の決めから導いた事」の線の関所の順、`docs/polyfills.md` の P2、`docs/plans/2026-10-12-lib-port.md` の「移し方」、今の works の `works/darkfactory/darkfactory.yaml`（入力は 20-97 行）・`works/darkfactory/lib/line_edge.py`・`works/darkfactory/fixtures/`・`works/blk-entry/`。

### 語

- 代わりのブロック: 試験だけで使う、本物のブロックと同じ工程の名（`works-factory-<ブロック>`）の小さな工程。中は `inner`（中の節）と、約束の返す節の名の節の 2 つの `script:` の節と `returns:` だけで、`output_format` を持たない（型の写しを持たない。持ち主の決め `io-in-output-format`）。返す値は筋書きの stub が決める。中の節が落ちた時に返す節が飛ばされる形を筋書きで作るため、節を 2 つにする。
- 筋書き: Archon の `workflow test` が読む `workflows/line/fixtures/<名>.stubs.yaml`。`fixture:`（`expect`・`fail-node`・`reached`・`inputs`）と `exec-code: true` と、節の id ごとの stub の値を持つ。`exec-code: true` の筋書きは、stub を置いた節は stub を返し、置かない `script:` の節は本当に走らせる（止めた Archon の `packages/workflows/src/dry-run.ts` 1300 行。ASF の `W/ship/fixtures/*.stubs.yaml` と同じ型。`W` は止めた Archon の源の `.archon/workflows/sdlc`）。
- 返しの節（埋め P2）: `include:` の `with:` に `{from, if_skipped}` が書けない（`docs/polyfills.md` の P2。止めた Archon の `schemas/dag-node.ts` 270-282 行）ので、飛ばされうる値を線の `script:` の節の `with:` で欄ごとに `{from: "$<節>.output.<欄>", if_skipped: null}` で受け、明示の値で返し直す節。ブロックにはその節の返りを渡す。
- 土台の足しの issue: この issue の前に main に入る小さな issue（自分の工程を pack の形で読ませ、名前の script と `.shared/` を効かせる・`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む・Archon の要る試験の助け `tests/archon.py`・CI の源・`test_archon_validate.py`・`test_no_conversion.py`）。番号は出した時に本文を直す。

### 目的

1. 線の順・関所・往復・一度だけの差し込み・深さの上げ直し・無人の方針・報告がいつも走ることを、Archon の YAML（YAML は配線だけ、計算は script、判断は役）で書く。
2. ブロックが揃う前から、線の道筋（どの筋書きでどの節に届き、どこで止まり、報告が走るか）と線の script の決めを、Archon の `workflow test` で確かめる。
3. 今の works の線の能力（下の「落とさない能力」）を落とさない。落とす物は名指し、持ち主の答えを待つ。

### 前提（先に main に要る物）

- 土台の足しの issue。
- #30（`lib/` へ今の works の部品を移す。PR #34 で main に入った）: 線の script が読む `lib/startrec.py`・`lib/gatepolicy.py`・`lib/stopby.py`・`lib/converge.py`・`lib/gatemarks.py`・`lib/answer.py`・`lib/planmarks.py`・`lib/carry.py`・`lib/ghreads.py`・`lib/forge.py`・`lib/promptsection.py`・`lib/marks.py`・`lib/graphloops/engine/` と `tests/e2e/__init__.py` を置く。
- 8 つのブロックの issue は待たない（下の「ブロックと並べて進める」）。

### 置く・変えるファイル

- `workflows/line/works-factory-line.yaml`（線。工程の名 `works-factory-line`）
- `workflows/line/scripts/`（線の名前の script。`lib/` と境の口を呼ぶだけ）
- `workflows/line/fixtures/*.stubs.yaml`（筋書き）と `workflows/line/fixtures/stub-blocks/<ブロック>/works-factory-<ブロック>.yaml`（代わりのブロック 8 つ。`fixtures/` の下は Archon が工程として読まない（止めた Archon の `workflow-discovery.ts` 216-217 行）ので、本物の run には出てこない）
- `workflows/.shared/skip_value.py`（返しの節の script が読む部品。P2 の「（予定）」を外す）
- `lib/entryshape.py`・`lib/entry.py` とその試験（下の「lib に持ってくる物」）
- `tests/layers/test_block_returns.py`（E5）・`test_outward_write.py`（E6）・`test_readonly_nodes.py`（E7）・`test_gates.py`（E16）と種（`tests/layers/seeds/e5`・`e6`・`e7`・`e16`）、`tests/layers/scan.py` に E5・E6・E7・E16
- `tests/e2e/test_line_scenarios.py`（`tests/archon.py` の木に線と代わりのブロックを置き、`workflow test works-factory-line` を回す）
- `docs/design.md`（下の「約束の直し」・U2〜U4・「線」の止め札の行）・`docs/polyfills.md`（P2）・`docs/asf-notes.md`（採った型）・`workflows/AGENTS.md` の E5 の 3 つ目の行（include の受け手の書き方）・`docs/plans/2026-10-11-foundation.md`（Task 4 を、別に渡す置き換えの文に）

### 線の節

`docs/design.md` の「線」の「順と関所」の 1〜13 のとおりに並べる。人の関所は E16 の形（線に `interactive: true`、関所は `approval:` の `message` と `decisions`。`decisions` は `approve` を必ず含む（止めた Archon の `schemas/dag-node.ts` 1301-1309 行））。

順と id（「順」は `docs/design.md` の「順と関所」の番号）:

- 1 `start`（script）
- 2 `gate-start`（approval）・`answer-start`（script。返しの節）
- 3 `test-gate-base`（include。mode base）
- 4 `judge`（include）
- 5 `plan-rounds`（loop_group。本体は `plan`・`plan-review` の include と、終わりの返しの節 `plan-out`）
- 6 `ask-before-fix`（script）・`gate-before-fix`（approval）・`answer-before-fix`（script）
- 7 `fix`（include）・`after-fix`（script）・`rejudge`（include。judge）・`judged`（script。返しの節）・`replan`・`replan-review`（include）・`ask-replan`・`gate-replan`・`answer-replan`・`refix`（include。fix の 2 度目。入力 `only_items` ← `$fix.output.replan_items` で、fix は裁かれた計画の項目に載る単位だけを直す。ほかの入力は `docs/design.md` の「fix の返り」の「`refix` の時」）・`fixed`（script。返しの節）・`redepth`（script）
- 8 `test-gate-final`（include。mode final）
- 9 `eyes`（include）
- 10 `merge-seal`（include。mode seal）
- 11 `ask-final`・`gate-final`・`answer-final`
- 12 `merge-apply`（include。mode apply）
- 13 `collect`（script。返しの節）・`report`（include）・`result`（script。線の返す節）

入力（`inputs:`）: 今の works の線の入力（`darkfactory.yaml` 20-97 行）のうち線とブロックが読む物を全部持つ。少なくとも `request`・`base`・`pr`・`spec`・`test_cmd`・`tdd_suite`・`final_gate`・`unattended`・`design_only`・`thickness`・`features_off`・`features_on`・`policy_md`・`fix_fixture`。落とす入力が在れば、名と訳（Archon が持つ・入口の殻が持つなど）を PR に書く。

各節の決め方:

- `start`: 入力を `lib/entryshape.py` でそろえ、`lib/startrec.py` の形で始めの記録を run の置き場に書き、指し札で返す。版の控え（止めた Archon の commit・Claude Code の版。今の works の `versions.py`）も始めの記録に入れる。差分も依頼の行も無い・入力の組み合わせが拒まれる（base と pr の両方・spec と unattended の組・重厚の厚み）時は、節は落ちずに `ok: false` と止めの理由の語（`lib/stopby.py`）を返す。後ろは `when:` で飛び、`collect`・`report`・`result` だけが走る（AI を起こす前に止める。ASF の `W/plan/archon-plan.yaml` の「`ready: false` も正しい終わり」と同じ形）。
- 線の script は全部、中で起きた例外を受けて `ok: false` と理由を返し、節としては落ちない（線の script が落ちると、それを受ける返しの節が読めず報告が届かない。止めた Archon の `dag-executor.ts` の `resolveBindingDirective` は、落ちた節を `if_skipped` に落とさない）。
- `ask-*`: 関所を開くかと見せる文を決める。開くかは流れなので線の script が持ち（E3 で `lib/` は流れを持たない）、方針の語は `lib/gatepolicy.py`（`opens`・`final_mode`・`unattended`）、関所の文は `lib/gatemarks.py`・`lib/answer.py` を呼ぶ。
  - 修正前: `plan-rounds` の返りの `ask_human`・`gate_axes`・`questions`・`stalled` と、無人か。無人の run では台帳の問いを載せず報告へ回す（今の works の `works/.shared/core/gatemarks.py` の `plan_gate_items`、625-655 行）。壁打ちが止まった時と、往復が 3 周で決着しなかった時と、設計だけの run（`design_only`）は必ず開く。
  - 案の直し: 約束の欄が変わったか・人に聞く種類の穴が在るか。無人の run で範囲を広げるだけの直しは聞かずに通し、通したことを記録する（今の works の `replan.py` 42・632 行）。
  - 最後: 今の works の `line_edge.py` の `_final_needs`（800-828 行）の理由（守りのパスの当たり・緑でない・申し出・人に回した物・目の阻害・残った異議ほか）を、`merge-seal`・`test-gate-final`・`fixed`・`eyes` の返りから並べ、`gatepolicy.opens(mode, reasons, guarded)` で決める。無人の run で開くはずの時は、関所を開かずに `needs_human` で止め、`merge-apply` を飛ばす（今の works で無人の殻が関所に stop を返したのと同じ結末）。開かなかったのに守りのパスの当たりか申し出が答えを待つ時も止める（`line_edge.py` 1184-1197 行）。
- `answer-*`: `depends_on: [ask-*, gate-*]`・`trigger_rule: none_failed_min_one_success`（関所が方針で飛ばされても走る。既定の `all_success` だと飛ばされる。止めた Archon の `dag-executor.ts` 1981-1983 行）。関所の出力を `{from: "$gate-*.output", if_skipped: null}` で受け、`{go, answer, stop_reason}` を返す（`answer` は `{decision, text}` か `null`）。`stop` の答えは `go: false` と止めの理由の語。関所の答えは run の置き場に `{decision, text}` で書き、報告に届く（今の works の `final-gate-answer.json` と `human_items` の行）。
- 計画の往復: `loop_group` の本体に `include: works-factory-plan`・`include: works-factory-plan-review`・`plan-out` を置く。`loop_group` の中の節は外から見えない（外から見えるのは `$plan-rounds.output` だけ。止めた Archon の文書 `guides/loop-nodes.md`、`loader.ts` 1076-1083 行）ので、`plan-out` が `$plan.output.<欄>` と `$plan-review.output.<欄>` を欄ごとに受けて返し、外の節は `$plan-rounds.output.<欄>` を読む。`plan-out` は `done`（`pass` か `stalled` が真か、plan の `round` が 3 以上）も返し、`until_bash` は `$plan-out.output.done` を見る。`max_iterations: 3`（3 周目の終わりで `done` が真になるので、上限に当たって落ちることが無い。上限に当たると節が落ちる。`loop-nodes.md` 212-216 行。今の works も上限で落とさず柵の周で止めた。`works/blk-plan/blk-plan.yaml` 536-545 行）。2 周目からの plan の `review` は `$LOOP_PREV.plan-out.output.review` で受ける（1 周目は空の字 `''`）。`include:` の id を `$LOOP_PREV` に書いても返す節に書き換わらない（`include-expander.ts` 1244-1247 行）ので、線の節 `plan-out` を読む。外から `$plan-rounds.output.<欄>` が読めることは、`exec-code` の筋書きで確かめる。
- `after-fix`: `fix` の返りの `replan_items`・`objection` から、`replan`・`rejudge` を差し込むかを返す（`when:` は配列が空かを比べられないので script が数える）。どちらも 1 run に 1 度（差し込みが 1 つずつしか無いことで縛る）。
- `judged`: `rejudge` が走れば単位と判定をその返りから、走らなければ `judge` から返す。後の段は単位と判定を `judged` から読む。再審が開いた単位と下げた単位（今の works の `rejudge.py` の `new_open_units`・`lowered`）は `collect` から報告へ渡す。
- `fixed`: `fix` と `refix` の返りを合わせる。`diff` は `refix` が走ればその物（どちらも run の始めからの累積）。配列の欄（`units` は `unit_id` ごとに後の物、`groups`・`allowed_test_changes` は和）と、申し出（`conflicts` は走った方の指し札を全部並べた配列）は 2 つを合わせ、1 回目の申し出と許したテストの変更が最後の関所と報告から消えないようにする。
- `redepth`: plan の深さ（`$plan-rounds.output.depth`）と、`fixed` の申し出・止めた単位、答えていない問い（`plan-rounds` の `questions` のうち関所で答えの無かった物）、`replan`・`rejudge` が走ったかから、`lib/depth.py` の `raise_doc` で上げ直し、`{depth, skip_optional}` を返す。`lib/depth.py` は `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品。線・plan・eyes が読む）が置き、この issue も plan の issue も置かない。それが main に入るまで、筋書きは `redepth` を stub にする。
- `collect`: `trigger_rule: all_done`。全ブロックと関所と返しの節の返りを、欄ごとに `{from, if_skipped: null}` で受ける（欄ごとに受けるので、読み手の無い欄の試験が働く）。
- `report`: `trigger_rule: all_done`（前の段が落ちても飛ばされても走る。`dag-executor.ts` 1966-2006 行）。`with:` は `$collect.output.<欄>` だけを読む。
- `result`（線の返す節）: `trigger_rule: all_done`。report の返りの結末の語と、`fixed`（boolean。結末の語が `fixed`・`fixed_needs_check` の時に真）を返す。線は `returns: result`・`outcome_field: fixed`（今の works の線も自分の節 `result` を返した。`darkfactory.yaml` 1363 行。ASF の ship も自分の `outcome` を返す）。線が自分の返す節を持つので、代わりのブロックの report に真偽の欄が要らない。
- 期限: 期限を持つ節（`script:` の `timeout`、`loop_group` の `timeout`、`approval:` の `idle_timeout`）は全部 `1728000000`（E12 の機械の表）。
- 読むだけの線の script（`ask-*`・`answer-*`・`after-fix`・`judged`・`fixed`・`plan-out`・`collect`・`result`）は `mutates_checkout: false`（E7）。`start`・`redepth` は run の置き場にだけ書く。

### 止め（持ち主の決め report-on-stop）

- どの人の関所も `decisions` に `approve` と `stop` を持つ。`stop` の答えは後ろの段を `when:` で飛ばして `collect`・`report` へ流し、結末は `stopped_by_human`。Archon の `cancel` は後ろの節を走らせない（止めた Archon の文書 `reference/cli.md` 921-955 行）ので使わない。
- 関所の間で走っている run を、報告を出して止める口は Archon に無い（`wait:` は節を止めて待つだけ。`workflow event emit` の行を読む書き方も無い。`schemas/dag-node.ts` 705-716 行・`reference/cli.md` 1141-1159 行）。今の works は境の節のどこでも止め札を読み（`line_edge.py` 174-267 行の `halt.seen`）、結末 `stopped_by_request` を出した。この issue は関所での `stop` だけを作り、関所の間の止めと `stopped_by_request` の道は持ち主の答えを待つ（答えが「止め札を埋めで置く」なら、別の issue で返しの節が札を読む形を足す）。`docs/design.md` の「線」の「どの段でも、外から止める札（止め札）を線の節が見て」の行は、答えが出るまで「関所の `stop`。関所の間の止めは持ち主の答え待ち」に直す。

### ブロックと並べて進める

土台の足しの issue の後は、並べて進められる。訳と条件:

1. 線の筋書きは、本物のブロックでなく代わりのブロックで回す。`include:` は工程の名で引き、無い名は読み込みの誤りで線ごと落ちる（止めた Archon の `include-expander.ts` 1269-1271 行）。`tests/archon.py` の木（`.archon/workflows/works-factory/` の下）に、線と `.shared/` と代わりのブロック（`works-factory-<ブロック>.yaml` の名で写す）だけを置く。本物のブロックが main に在っても混ざらない。
2. 筋書きの stub は、include を展開した後の返す節の id（`judge__verdict` など。返す節の名は約束が決めている）と、代わりのブロックの `inner` に置く。関所は筋書きではいつも `approved` の字で通り、stub も答えも置けない（`dry-run.ts` 1179-1204 行）ので、関所の答えは `answer-*` の stub で差す。往復は筋書きでは 1 周で終わったものとされ `until_bash` は走らない（`dry-run.ts` 849-890 行）ので、`plan-out` の `done` の決めは `exec-code` で走る `plan-out` の script を通して、周ごとの値の組を当てて確かめる。
3. 本物のブロックとの欄の照らしは、土台の足しの `test_archon_validate.py`（Archon の `validate`。`loader.ts` 1037-1058 行）が、8 つが揃った時に線ごと行う。それまでは線を名前つきで見送る。
4. この issue の PR は、ブロックの PR の前でも後でも merge してよい（ブロックの筋書きは自分のブロックだけの木で回す。土台の足しの issue の「後の issue との関係」）。
5. 共有のファイル: `docs/design.md`・`docs/polyfills.md`・`docs/asf-notes.md` はブロックの issue も行を足す。節の違う所への足しなので、ぶつかりは rebase の字の上だけ。`lib/` は、この issue は `lib/entryshape.py`・`lib/entry.py` だけを足す（どちらも線だけが使う）。

### lib に持ってくる物（持ち主の決め lib-port-as-is）

移し方は `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6 と同じ。違う所だけを書く。

- `works/.shared/core/entryshape.py` → `lib/entryshape.py`。`measure` が `board.diff_of`（`works/.shared/core/board.py` 554 行）を呼び、`diff_of` が写しの rules の `_worktree_tree`（`works/.shared/core/graphloops/rules/review-loop.py` 1501 行）と `_unfrozen` を呼ぶ。`board` と rules は持ってこない（移し方の 3）が、`measure` は空の入力を拒む（`refuse_empty`・`build`）芯で、盤面を開かない git の差分の読みなので外せない。そこで `diff_of`・`_worktree_tree`・`_unfrozen`（git と `engine.util` の `git`・`Reject` だけを使う約 45 行）を、元の名と中身のまま `lib/entryshape.py` の末に写し、`import board` を消す。写した行の元のパスと行を、各関数の頭の 1 行のコメントと commit と PR に書く（移し方の 1〜3 から外れる唯一の所。訳は「盤面を開かない関数が盤面のファイルに住んでいた」）。
- `works/.shared/core/entry.py` の機能の切り替えの塊（420-514 行の `FEATURES`・`FEATURE_DEFAULTS`・`features_off`・`features_on`・`feature_words`・`features_cut`・`cut_of`・`features_on_of`・`features_part`）→ `lib/entry.py`。ほかは移し方の 2 で消す（盤面に届く）。塊が読む `script_io` の `SWITCH_ON`・`SWITCH_OFF`・`SWITCH_AUTO` と `InputRefused` は、`script_io` を持ってこないので `lib/entry.py` に元の字のまま写し、元のパスと行をコメントに書く。`_resumed_features`（呼び直しで機能が前と違えば拒む）は持ってこない。Archon は run の始めに入力を写し取り、resume はその写しで走るので、機能が途中で変わらない。
- lib-port で外した試験の戻し: `works/tests/test_forge.py` の `GhReadsCase`（`ghreads._settle`。`entryshape` を使うので lib-port が外した）と、`works/tests/test_gate_head.py` の `FinalHeadCase`（最後の関所の頭の行）と `AskGateCase` の頭（修正前の関所の文の頭の 3 行）を、元の名で戻す（`GhReadsCase` は `lib/tests/test_forge.py` に、関所の頭の 2 つは線の script を確かめる試験に）。どれも線が持つ所の試験で、ブロックの issue は持ってこない（`docs/plans/2026-10-12-lib-port.md` の外した試験の名、`docs/plans/2026-10-12-blocks/` の eyes・plan-review の計画の渡し先）。盤面に届く行は移し方 5 で外し、外した名を PR に書く。
- 試験: `works/tests/test_entry_inputs.py` のうち `entryshape` の口を直に呼ぶ物（`diff_of` の 3 本・`test_build_input_from_each_entry`・`test_request_text` の見込み）と、`works/tests/test_entry.py`・`test_entry_block.py` のうち `FEATURES` の塊だけを呼ぶ物を、元の名で `lib/tests/` に置く。外した名と理由を PR に書く。
- 線の script は `boundary.lib_root()` で `lib/` を見つける（土台の足しの issue が `WORKS_FACTORY_ROOT` を読む形にする。筋書きでは `tests/archon.py` がそれを置く）。

### 約束の直し（docs/design.md と workflows/AGENTS.md）

線を書く中で約束と食い違う所が出た。YAML と約束を両方合わせる（「ブロックの返りの約束」の頭の「YAML と食い違ったら、どちらが正しいかを決めて両方を合わせる」）。

1. 線の中の id に `answer-start`・`ask-before-fix`・`answer-before-fix`・`after-fix`・`judged`・`ask-replan`・`answer-replan`・`refix`・`fixed`・`ask-final`・`answer-final`・`plan-rounds`・`plan-out`・`collect`・`result` を足す。`refix` は今の works の `refitting`（案の直しの後の 2 度目の修正。`darkfactory.yaml` 803 行）に当たり、約束の include の一覧に無かった。無いと、案の直しが計画を直しても、直した計画で直す段が無い（能力の落ち）。
2. 線の返りは `result`（線の節）。約束の「→ 線の返り」の読み手（`bin/show`・`bin/start --rounds`）は入口の殻の issue が直す。report の返す節の `outcome_field: outcome`（字の欄）は、Archon が真偽の欄を求める（`loader.ts` 175-215 行）ので report ブロックの読み込みが落ちる。report ブロックの issue に伝える（下の「頼むこと」）。
3. include の受け手の `{from, if_skipped: null}` は書けない（P2）。約束で `{ from: "$gate-before-fix.output", if_skipped: null }`・`{ from: "$gate-final.output", if_skipped: null }`・report の全部の入力に書いた所を、返しの節の返り（`$answer-before-fix.output.answer`・`$answer-final.output.answer`・`$collect.output.<欄>`）に直す。`workflows/AGENTS.md` の E5 の 3 つ目の行に「受け手が include の時は、線の返しの節で受けてから渡す（埋め P2）」を足す（Archon は include の `with:` に書いた束ねを黙って字の値として渡すので、書けたように見えて効かない）。
4. 後の段が `fix` の返りを読む所は `$fixed.output.<欄>`、`judge` の単位と判定を読む所は `$judged.output.<欄>`、`plan`・`plan-review` の返りを外から読む所は `$plan-rounds.output.<欄>` を読む。
5. plan の入力 `review` は 1 周目に空の字 `''`（約束の「1 回目は null」を直す。Archon の `$LOOP_PREV` は 1 周目に空の字を渡す）。
6. 返しの節の `output_format` は受けた欄の名だけを書き、型は受けた元（ブロックの返す節の `output_format`）を正本とする。返しの節の `from` が読む `$<ブロック>.output.<欄>` は Archon の `validate` が照らすので、型の写しを持たずに約束が縛られる。
7. U2〜U4 を分かった事で閉じる。U2: 同じブロックを 2 度差し込んだ返りは include の id ごとに分かれる（`include-expander.ts` 1-19 行）。型つきの成果物の分かれは report ブロックの issue に残す。U3: `workflow test` は使える（上の「ブロックと並べて進める」の 2 の制約つき）。U4: `loop_group` の中に `include:` は書ける（`schemas/dag-node.ts` 513-529 行）が、中の節は外から見えないので、本体の終わりに返しの節を置く。

### 落とさない能力（今の works の線から）

- 止めの理由の語を字のまま（`lib/stopby.py` の表と、線が足す語）。結末の分かれのうち人の止め `stopped_by_human` と線の止め `stopped_by_line`。頼まれた止め `stopped_by_request` は持ち主の答え待ち（上の「止め」）。
- 関所の答えの記録（`{decision, text}`。止めも残す。resume で積み増さない）。
- 最後の関所の安全（守りのパスの当たり・申し出は `protected_only`・`when_needed` でも開く。開かなかったのに待つ物が在れば止める。通すのは人の `approve` だけ。1 回目の修正の申し出も届く）。
- 無人の run の決まり（台帳の問いは関所でなく報告の頭へ。範囲を広げるだけの案の直しは通して記録。spec と unattended の組は拒む）。
- 設計だけの run と壁打ちの止まりは、修正前の関所を必ず開く。往復は 3 周で決着しなくても落ちずに関所へ回る。
- report はいつも走る（線の script とブロックの中の節が落ちても）。
- 深さの上げ直し（申し出・止めた単位・答えていない問い・案の直し・再審）と、軽量で省いた物を名指すこと。
- 一度だけの差し込み（案の直しとその後の 2 度目の修正・再審と、再審が開いた・下げた単位）。
- 機能の切り替え（`features_off`・`features_on`。語の検査は `lib/entry.py`）・版の控え・固定材料から始める入力（`fix_fixture`）。

落ちうる物（名指す）: ブロックの返す節そのものが落ちた時、`collect` はその節を読めず落ち、報告は走らない（Archon の run の記録が落ちた節を名指す）。今の works は報告が盤面を読んだので、この場合も報告が出た。線の側で耐える書き方は Archon に無い（`resolveBindingDirective`）ので、ブロックの issue に「返す節は落とさない（中で受けて `ok: false` で返す）」を頼む。

### 筋書き

今の works の `works/darkfactory/fixtures/` の 15 本のうち線に関わる物を移し、新しい形の物を足す。全部 `exec-code: true`。各筋書きは `fixture.expect` と `reached` を持ち、止まる物は `result` の結末の語を照らす（`resolved-text-contains` か `result` が書く置き場のファイル）。

- `standard`: 全部の段が回る（`fixed`）
- `start-refused`: 依頼の行も差分も無い → `start` が `ok: false`、ブロックは全部飛び、`report`・`result` が走る
- `no-fix`: `judge` の `ready: false` → 計画から後が飛ぶ（`no_fix_needed`）
- `policy-continue`: 修正前の関所が開き、`approve` と一言が `fix` の `answers` に届く
- `policy-stop`: 修正前の関所で `stop` → `fix` から後が飛ぶ（`stopped_by_human`）
- `plan-stalled`: `plan-review` の `stalled: true` → 修正前の関所が必ず開く
- `plan-unsettled`: 3 周目の値（`round: 3`・`pass: false`・`stalled: false`）→ `plan-out` の `done` が真になり、往復が落ちずに修正前の関所が開く
- `replan`: `fix` の `replan_items` と申し出 → `replan`・`replan-review`・案の直しの関所・`refix` が 1 度ずつ走り、1 回目の申し出が最後の関所の理由に残る
- `rejudge`: `fix` の `objection` → `rejudge` が 1 度走り、後の段は `judged` を読む
- `light`: 全部の単位が軽量のまま → `eyes` に R1〜R4 を省く値が渡る
- `final-stop`: 最後の関所で `stop` → `merge-apply` が飛ぶ
- `final-when-needed-green`: `when_needed` で理由が無い → 最後の関所が開かない
- `conflict-ask`: 申し出が在る → `protected_only` でも最後の関所が開く
- `unattended-needs-human`: 無人の run で最後の関所が開くはず → 開かずに止まり、`merge-apply` が飛ぶ（`needs_human`）
- `block-failed`: `judge` の `inner` が落ちた → 返す節は飛ばされ、後ろが飛び、`collect`・`report`・`result` は走る（`expect: failed`、`fail-node` は `judge__inner`）

今の works の筋書きのうち、ブロックの中の物（`pr-fallback`・`spec`・`ai-report-fail`・`rejudge-no-session`）はそのブロックの issue が持つ。止め札の筋書き `stop-flag` は、関所の間の止めの答えが出るまで置かない。

### 手順（試験が先に赤）

1. 層の試験 4 つとその種を書く。赤を見る。
   - `test_block_returns.py`（E5）: 在るブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。読み手の無い返りの欄（在るブロックの返す節の欄のうち、線の `with:`・`when:`・返しの節の `from` とほかのブロックの誰も読まない物）が赤。線の読む欄が返す節に在るかは Archon の `validate` が照らすので、この試験では照らさない（同じ決まりを 2 か所に持たない）。
   - `test_outward_write.py`（E6）・`test_readonly_nodes.py`（E7）・`test_gates.py`（E16）: `workflows/AGENTS.md` の機械の行のとおり。
2. `tests/e2e/test_line_scenarios.py` を書く（`tests/archon.py` の木で `bun <源>/packages/cli/src/cli.ts workflow test works-factory-line --cwd <木> --json` を回し、筋書きごとの結果を名前つきで照らす。源か bun が無ければ名前つきで見送る）。赤を見る。
3. `lib/entryshape.py`・`lib/entry.py` の元の試験を `lib/tests/` に置いて赤 → 上の「lib に持ってくる物」で置いて緑。
4. 代わりのブロック 8 つ・`workflows/.shared/skip_value.py`・線の script・線の YAML・筋書きを書き、1・2 が緑。
5. 文書を直す（上の「約束の直し」・P2 の置き場・「線」の止め札の行・`docs/asf-notes.md`・計画の Task 4）。
6. 全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。

### 受け入れ

- 1・2・3 の試験が先に赤で入り、後で緑。
- 全部の試験が緑。Archon の要る試験は、源か bun が無い時だけ名前つきで見送られる（CI では見送られない。土台の足しの issue が CI に源を置く）。
- 本物のブロックが 1 つも無い main の上で、15 本の筋書きが全部通る。
- 種 `e5` で、在るブロックの返す節に読み手の無い欄が在ると `test_block_returns` が赤になる。
- 層の試験（各階層の `AGENTS.md` の機械の行）が全部緑。

### 範囲（触らない物）

- `workflows/<ブロック>/`（8 つ）・`lib/` のうち `entryshape.py`・`entry.py` とその試験と、戻す試験の外（`lib/depth.py` は `docs/plans/2026-10-12-blocks/prereq.md` の issue）・`bin/`・`workflows/.shared/boundary.py`。
- 根の `AGENTS.md`・`bin/AGENTS.md`・`lib/AGENTS.md`・`tests/AGENTS.md`・`docs/owner-decisions.md`・`pack.json`・`factory/`・`harness/`。
- 関所の間の止め（持ち主の答え待ち）。周の鎖（入口の殻の issue が置き先を決める）。

### E11 の 3 つ

1. Archon が持つ物: 関所（`approval:` の `decisions`）・往復（`loop_group` と `include:`）・いつも走る節（`trigger_rule: all_done`）・線とブロックの欄の照らし（`validate`）・筋書きの試験（`workflow test` と `exec-code`）。全部 Archon の物を使う。
2. ASF が持つ物: `W/ship/archon-ship.yaml`（`if_skipped` で飛ばされた子を null で受け、どの道でも自分の 1 つの返り `outcome`）・`W/merge-queue/archon-merge-queue.yaml`（`approval:` の `decisions` と `when:`）・`W/ship/fixtures/`（include を展開した id に stub を置き、`exec-code: true` で自分の script を走らせる筋書き）。採った型は `docs/asf-notes.md` に足す。
3. 要るか: 「能力の棚卸し」の「線と入口」の行（入口の入力の形・深さ・機能の切り替え・止め札・人の関所と無人の方針・止めの理由の語・境の節・固定材料と版の控え）。足す仕組みは返しの節（埋め P2）だけで、P2 が塞がれば消す。

### 頼むこと（このリポジトリの協調。ブロックの issue の書き手へ）

- report: 返す節の `outcome_field` を真偽の欄にする（`outcome` は字の欄なので、Archon が読み込みで拒む）。入力は `$collect.output.<欄>` の形で受ける。
- plan: 入力 `review` は 1 周目に `''`。`lib/depth.py`（と、それが頼る `lib/impact.py`）は `docs/plans/2026-10-12-blocks/prereq.md` の issue が置く（plan の issue も線の issue も置かない）。線の `redepth` が `raise_doc` を読む。
- 全部: 返す節は落とさない（中で受けて `ok: false` などで返す）。筋書きの試験は、土台の足しの `tests/archon.py` の木に自分のブロックだけを置いて回す。名前の script は土台の足しの後の pack の形で効く。

# B 入口の殻 1 本 bin/works-factory: 認証と隔離を整えて、止めた Archon を起こす（土台の計画 Task 5 の書き直し。持ち主の決め one-launcher）

### このリポジトリと、この issue の位置

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。人が打つ入口は、持ち主の決め `one-launcher`（`docs/owner-decisions.md`）で「Archon の命令の別名（start・answer・show）を作らず、認証の環境を整えて Archon を起こす殻 1 本にし、人は Archon の命令をそのまま打つ」と決まった。殻の部品（認証の切り替え `bin/_lib/auth_launch.py`・`claude_auth.py`、置き場の隔離 `bin/_lib/isolate.py`、隔離した Claude に見せるプラグインの選び `bin/_lib/toolset.py`、利用者の gh のログインを継ぐ口 `bin/_lib/hostgh.py`）は、前の形の「今の works」（公開リポジトリ `raiki61/claude-plugins` の `works/`）から PR #21 で試験ごと持ってきてある。止めた Archon（`factory/pack.json` が名指す commit の Archon の源。`docs/design.md` の「語」）の取り寄せと起こす命令は `bin/_lib/place.py`（PR #28）に在る。この issue は、それらを今の works の `works/dev/archon.sh` と同じ順でつなぐ殻 `bin/works-factory` を 1 本作る。持ち主の言葉「基本的に自作部分はその認証の切り替えだけでいいね？」（`bring-launch`）のとおり、殻が持つのはつなぎだけで、新しい仕組みは足さない。

読む物: 根の `AGENTS.md`（E14・E18）・`bin/AGENTS.md`（E15）・`tests/AGENTS.md`、`docs/owner-decisions.md` の `one-launcher`・`bring-launch`・`others-may-use`・`archon-same-as-asf`・`report-on-stop`・`auth-middleware`、`docs/design.md` の「pack.json」の節と未決 U5、`docs/polyfills.md` の P1・P3、今の works の `works/dev/archon.sh`（起動の順の元）と `works/dev/launch.py` の 80-91 行（家の決め方の元）、ASF の `factory/consumer.py` の `invoke`（257-350 行。`--workflow-source` を殻が持つ形の元）。

### 目的

1. 人は `bin/works-factory <Archon の CLI の引数>` を打つ。殻は利用者の環境から認証と隔離を整え、止めた Archon を `bun` で起こし、引数をそのまま渡す。
2. `workflow run` の時だけ、殻が `--cwd` と `--workflow-source` を利用者の引数の前に足し、自分の工程（`workflows/`）を置かずに読ませる（`place.workflow_run` と同じ並べ）。
3. 既定の道は、`claude /login` だけをした人・macOS 以外の人・API キーや会社のゲートウェイの人の環境でそのまま動く（E14）。持ち主の環境の物（keychain の項目の名など）は、利用者の設定（環境変数）で渡す選べる道に留める。
4. 線とブロックの script が `lib/` を見つけられるよう、子の環境に `WORKS_FACTORY_ROOT`（このリポジトリの根）を置く（未決 U5 の `bin/` の側。境の口の側は土台の足しの issue が `boundary.lib_root()` に置く）。

### 前提

- PR #21（`bin/_lib/` の部品）と PR #28（`place.py`）が main に在る。
- 土台の足しの issue（自分の工程を pack の形で読ませる `place.workflow_source`・キャッシュの置き場 `place.cache_dir`・`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む形）が main に在る。
- 線の issue（線の YAML）を待たない。この issue の試験は偽の `bun` で回す。

### 置く・変えるファイル

- `bin/works-factory`（Python の実行ファイル。`bin/_lib/launcher.py` の `main` を呼ぶだけ）
- `bin/_lib/launcher.py`（つなぎ）
- `tests/bin/test_launcher.py`
- `README.md` の「使い方（予定）」・根の `AGENTS.md` の「リポジトリの形」の `bin/` の行・`bin/AGENTS.md` の E15 の 3 つ目の行・`docs/design.md`（「4 つの層」の図と表の入口の行・U5 の `bin/` の側・「能力の棚卸し」の「周の鎖」の行と「止め札。札を置く口は `bin/`」の行・「線」の「周の鎖は run の外で `bin/start --rounds` が持つ」・「線が運ぶ物」の「→ `bin/show`」・「ブロックの返りの約束」の「→ 線の返り（`bin/show`・`bin/start --rounds`）」と report の `outcome` の行・「作りの順」の段 1 の「`bin/answer` で答える」）・`docs/polyfills.md` の P1 の「埋め」の行・`docs/plans/2026-10-11-foundation.md` の Task 5（別に渡す置き換えの文）

### 約束（殻の振る舞い）

`bin/works-factory <args…>` は次の順で動く。番号の後の括弧は今の works の `works/dev/archon.sh` の行に当たる。

1. 隔離の前の値を取る（`archon.sh` 63-64・95 行）: 利用者の `HOME`、`CLAUDE_CONFIG_DIR` の生の値（相対なら打った場所から絶対に直す。今の works の `works/dev/guard.sh` の `works_dev_abs_claude_config` と同じ）、それを既定で埋めた値（無ければ `<HOME>/.claude`）、`PATH`、`GH_CONFIG_DIR`、`XDG_CONFIG_HOME`、本物の `claude`（`CLAUDE_BIN_PATH`、無ければ `PATH` の絶対の置き場から。相対の置き場は打った場所の下の物を拾うので使わない）。`HOME` が無ければ 1 行で止まる。
2. 対象を決める: 引数の `--cwd` の値、無ければ打った場所。実のパスに直し、git の木の中なら git の根に直す（git が無ければ 1 行で止まる。今の works の `use.sh` 250-261 行と同じ。同じ clone の下のフォルダから打っても同じ家になる）。
3. 家（Archon の DB と隔離した置き場の根）を決める: 環境変数 `WORKS_FACTORY_HOME`（絶対パスだけ受ける。相対なら 1 行で止まる）、無ければ `${XDG_STATE_HOME:-<HOME>/.local/state}/works-factory/targets/<対象の実のパスの sha256 の頭 8 字>`。対象ごとに 1 つで、起動をまたいで同じ（`run`・`approve`・`respond`・`resume` が同じ DB を見る）。訳は今の works の `works/dev/use.sh` 260 行「1 つの家に同じリポジトリの clone を 1 か所しか登録できない」と `launch.py` 80-91 行。
4. 止めた Archon の源を取る: `pack.load(<リポジトリの根>)` → `place.archon_source(pack, place.cache_dir(<利用者の環境>))`（キャッシュの置き場は CI と同じ 1 つの関数で決める。試験の助け `tests/archon.py` は `cache_dir` を読まず、`WORKS_FACTORY_ARCHON_CACHE` で渡された置き場だけを見る）。bun が無い・取れない時は `place` の 1 行の文で止まる（Archon を起こさない）。隔離の前の環境で回す（git と bun が利用者の設定を使う）。
5. `child = isolate.isolate(<利用者の環境>, <家>)`（`archon.sh` 130-142 行）。
6. gh の口（`archon.sh` 121-126・143-146 行）: `hostgh.write(<家>/host-gh, <1 の PATH>, <1 の HOME>, <1 の gh の設定の置き場>)`。口が書けたらそのフォルダを `child["PATH"]` の頭に置く。gh が無ければ置かない（gh を使う段は gh の言葉で人待ちになる。今と同じ）。
7. 送信を切る（`archon.sh` 221-223 行）: `child` に `ARCHON_TELEMETRY_DISABLED=1`・`DO_NOT_TRACK=1`。mise の信頼は今の works と同じ条件で足す（`archon.sh` 105-113・150-154 行）: `WORKS_FACTORY_NO_AUTH` でなく、`mise` が在り、利用者の mise が対象の根を信頼済み（隔離の前に `mise trust --show` の `<対象>: trusted` の行）の時だけ、`<家>/archon-home/workspaces` を `MISE_TRUSTED_CONFIG_PATHS` に足す（run の worktree は家の下の新しいパスで、対象の根の信頼が効かず、道具の失敗が偽の赤になるのを防ぐ）。
8. U5 の `bin/` の側: `child["WORKS_FACTORY_ROOT"]` にこのリポジトリの根を置く（`boundary.lib_root()` がこれを読む。土台の足しの issue）。Archon は host で走る script の節に起動の環境を渡す（止めた Archon の `packages/workflows/src/dag-executor.ts` 3057-3058 行）。Archon が run の始めに写すのは `workflows/` だけなので、run の途中でリポジトリの `lib/` を変えると走っている run に効く（この issue では変えない。README に 1 行書く）。
9. 工程を回す命令（`workflow` の `run`・`resume`・`approve`・`reject`・`respond` と `wake`・`signal`。止めた Archon が工程を走らせる命令の一覧 `packages/cli/src/cli.ts` 703 行と、その前で捌く続きの命令 424 行）と、`validate` の時:
   - 認証を先に確かめる（工程を回す命令だけ）: `auth_launch.py check --for works-factory --user-home <1 の HOME> --user-config <1 の生の値>` を利用者の環境で回し、2 なら Archon を起こさずに止まる（`archon.sh` 65-67 行）。`WORKS_FACTORY_NO_AUTH=1` なら飛ばす。
   - プラグインの選びを入れる: `toolset.py install --claude <1 の claude> --user-config <1 の埋めた値> <child の CLAUDE_CONFIG_DIR>` を `child` の環境・対象を cwd で回す（`archon.sh` 205-210 行）。`validate` の時と `WORKS_FACTORY_NO_AUTH=1` の時は `--claude` の代わりに `--no-plugins`（スキルは写し、プラグインの CLI は呼ばない。今の works の `archon.sh` 204-210 行も validate を同じ置き場で回した。`validate` はスキルの名を照らす。止めた Archon の `validator.ts` 755-766 行）。0 でなければ Archon を起こさずに、toolset の文のまま止まる。
   - ほかの命令（`status`・`get`・`list`・`runs`・`logs`・`cancel`・`abandon` など）は、走らせる工程も照らすスキルも無いので、この 2 つを飛ばす。
10. 引数を組む: 引数が `workflow run <工程の名> …` で `--resume` を持たない時は、`place.workflow_run(<源>, <place.workflow_source の置き場>, <2 の対象>, <工程の名>, *<残り>)` で組む（`--cwd` と `--workflow-source` を利用者の引数の前に置く。利用者の `--` の後ろに付くと文として渡り、Archon が黙って対象の `.archon/workflows` を探す元の動きに戻る）。`run` の直後が工程の名でなく旗なら、使い方の 1 行で止まる。利用者が `--cwd` を書いていたら、それを 2 の対象に使い、二重に足さない。利用者が `--workflow-source` を書いていたら 1 行で拒む（ASF の `factory/consumer.py` 311-312 行と同じ。殻が置き場を持つ）。ほかの命令は引数をそのまま渡す。
11. 起こす: `python3 -I bin/_lib/auth_launch.py exec --for works-factory --user-home <1 の HOME> --user-config <1 の生の値> -- <bun の絶対パス> --config=<源>/bunfig.toml <源>/packages/cli/src/cli.ts <10 の引数>` を `child` の環境で exec する（`archon.sh` 225 行）。cwd は打った場所のまま（`workflow status` などが打った場所を対象とみなす）なので、bun が打った場所の `bunfig.toml` の preload を認証つきで走らせないよう、源の `bunfig.toml` を名指す。`auth_launch.py exec` は `os.execve` で起こし PATH を探さない（`auth_launch.py` 156・164 行）ので、`bun` は `child` の PATH で絶対パスに直してから渡す（`place.workflow_run` の返す先頭の `bun` も同じに直す）。終了の値と出力は Archon のまま。

- 環境変数（全部、利用者の設定。リポジトリに値を書かない。E14）: `WORKS_FACTORY_HOME`（家）・`WORKS_FACTORY_KEYCHAIN_ITEM`（Claude のアカウントを keychain の項目の名で選ぶ。`auth_launch.py` が読む）・`WORKS_FACTORY_NO_AUTH`（認証の要らない道）・`WORKS_FACTORY_COLDWRITE_MARKETPLACE`・`WORKS_FACTORY_COLDWRITE_MARKETPLACE_REPO`（`toolset.py` が読む）。どれも無ければ、ホストのログインのまま動く。
- 殻は秘密を出さない・引数に置かない・ファイルに書かない（`auth_launch.py` の約束のまま）。

### 止めと周の鎖

- 止め（持ち主の決め `report-on-stop`）: 人は関所で `bin/works-factory workflow respond <run> stop <一言>` と打つ。線が後ろを飛ばして報告を出す（線の issue が作る）。殻は何も足さない。関所の間で走っている run を報告つきで止める口は Archon に無く、持ち主の答えを待つ（この issue の外。今は `workflow cancel` で止まり、報告は出ない）。README の使い方に、この 2 つの違いを 1 行ずつ書く。
- 周の鎖（頼まれたら run を何周もつなぐ。今の works の `use.sh start --rounds` と `works/.shared/core/chain.py`）: 殻に置かない。「能力の棚卸し」は置き先をこの issue で決めると書いている。決め: 置き先は線の後ろ（線の `report` の後に、`workflow:` の節で次の周の線を起こす形を推しとし、段 3 で確かめて作る）。訳: 殻に置くと、持ち主の言葉「自作部分はその認証の切り替えだけ」から外れる。`workflow:` の節で同じ線を起こせるかは、まだ確かめていない（段 3 で確かめる。起こせなければ置き先を決め直す）。Archon は run をつなぐ口（`workflow run --adopt <run>`・`--supersedes <run>`。止めた Archon の文書 `reference/cli.md` 312-313 行）を持つので、作るまでの間は人がそれで次の周を起こせる。`docs/design.md` の「周の鎖」の行をこの決めに直す。
- P1（持ち主の居ない `running` の run）: 埋めの置き場が `bin/show`・`bin/start`（予定）になっているが、`one-launcher` でその 2 つは作らない。止めた Archon の `workflow cancel`・`abandon` は持ち主の居ない run に `abandon` を案内し（`reference/cli.md` 921-1028 行）、`--adopt` で続きを起こせる。P1 の「埋め」の行を「置き場は未定（入口に別名を作らない。Archon の abandon と --adopt で足りるかを段 1 で確かめる）」に直す。

### 手順（試験が先に赤）

1. `tests/bin/test_launcher.py` を書く。偽の `bun`・`claude`・`gh`・`security` を `PATH` に置いた使い捨ての木で、殻を子のプロセスとして走らせ、偽の `bun` が受けた引数と環境を JSON に書かせて照らす（トークンの値は照らさず、在るかだけを見る）。走らせて赤を見る（殻が無い）。
   - `test_run_gets_cwd_and_workflow_source_before_user_args`（偽の `bun` は PATH の上にだけ置き、殻が絶対パスで起こすことも縛る）
   - `test_resume_and_approve_pass_through_unchanged`
   - `test_user_workflow_source_is_refused`
   - `test_home_is_stable_per_target`（同じ対象で 2 度・同じ clone の下のフォルダから → 同じ家、別の対象 → 別の家。`WORKS_FACTORY_HOME` の相対は止まる）
   - `test_child_is_isolated`（`HOME`・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`・`XDG_*` が全部家の下、利用者の値は残らない、送信を切る 2 つが立つ、`WORKS_FACTORY_ROOT` がリポジトリの根）
   - `test_user_values_are_taken_before_isolation`（`auth_launch` の `--user-home` が利用者の HOME、`--user-config` が生の値、`toolset` の `--user-config` が埋めた値、相対の `CLAUDE_CONFIG_DIR` は絶対に直る）
   - `test_gh_shim_heads_child_path`（口が PATH の頭に在り、`GH_TOKEN` を立てない）
   - `test_toolset_and_auth_check_only_for_workflow_executing_commands`（`status` では呼ばない。`validate` では toolset を `--no-plugins` で呼び、認証は確かめない）
   - `test_mise_trust_only_when_user_trusts_target`
   - `test_toolset_failure_stops_before_archon`・`test_missing_auth_stops_before_archon`（偽の `bun` が呼ばれない）
   - `test_claude_login_only_user_reaches_archon`（E14。借りるプラグインを入れた形の偽の利用者の設定（`toolset.py` が名で頼る `installed_plugins.json` の行と `agents/`・`hooks/` の名）を置く。keychain の項目を名指さず、`<CLAUDE_CONFIG_DIR>/.credentials.json` にだけログインが在る利用者で、macOS 以外では子に `CLAUDE_CODE_OAUTH_TOKEN` が在り、子の `CLAUDE_CONFIG_DIR` は隔離したまま。macOS では `skipTest("macOS 以外の道: ...")`。CI は ubuntu なので走る）
   - `test_api_key_user_reaches_archon`（`ANTHROPIC_API_KEY` だけの利用者で、子に受け継がれ、keychain を読まない）
   - `test_bun_missing_stops_with_one_line`
2. `bin/_lib/launcher.py`・`bin/works-factory` を書いて緑。殻は上の「約束」の 1〜11 だけを持つ。部品（`auth_launch.py`・`isolate.py`・`toolset.py`・`hostgh.py`・`place.py`・`pack.py`）は呼ぶだけで変えない（E15）。
3. 文書を直す（上の「置く・変えるファイル」）。README の使い方は次の形:
   1. 入れる: clone して `bun` を入れ、借りるプラグイン（`bin/_lib/borrow/borrow.json` の物。足りなければ殻が入れる命令を 1 行ずつ出して止まる）を Claude Code に入れる。
   2. 始める: `bin/works-factory workflow run works-factory-line --cwd <対象> --input request=<依頼>`。
   3. 答える: `bin/works-factory workflow respond <run> approve|stop [一言] --cwd <対象>`（家は対象ごとなので、対象の外から打つ時は `--cwd` が要る）。
   4. 見る: `bin/works-factory workflow status --cwd <対象>`・`workflow get <run> --cwd <対象>`。
   5. 当てる: `bin/apply`（土台の計画 Task 7。まだ無い）。
4. 全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。

### 受け入れ

- 1 の試験が先に赤で入り、後で緑。
- 全部の試験が緑。層の試験の E14（`bin/` に持ち主の環境の字が無い）・E18 も緑。
- `bin/_lib/` の持ってきた部品に差分が無い（`git diff main -- bin/_lib/auth_launch.py bin/_lib/claude_auth.py bin/_lib/isolate.py bin/_lib/toolset.py bin/_lib/hostgh.py bin/_lib/place.py bin/_lib/pack.py` が空）。
- 手で 1 度: 持ち主の手元で `bin/works-factory workflow list --cwd <小さな git の木>` が 0 で終わり、Archon の工程を並べる（止めた Archon は `--workflow-source` を `workflow run` でしか読まず、殻も新しい run にだけ足すので、`workflow list` に `works-factory-*` は並ばない）。結果を PR に書く。

### 範囲（触らない物）

- `bin/_lib/` の持ってきた部品の中身（E15。直す要が出たら止めて別の issue にする）。
- `workflows/` の線とブロック・`lib/`。
- ASF をこの殻から起こすこと。今の仮の殻（持ち主の手元の `asf-env`）は、GitHub のアカウントの名での選び（`gh auth token -u <名>`）と、隔離した家の git の資格の口を持つ。ASF の工程は PR を作り push するのでそれが要るが、自分の線は対象に差分を置くだけ（E17）で要らない。ASF を同じ殻から起こすのは、`hostgh.py` にアカウントの名を足す形を含めて別の issue にする（`auth-middleware`: GitHub の資格を役に渡さない形を守るため、トークンを環境に置かず口の中で引く）。
- 関所の間の止め・周の鎖を作ること（上の「止めと周の鎖」）。
- 今の works の `archon.sh` のうち持ってこない物と訳: 隔離した Archon の設定への既定の模型と `TITLE_GENERATION_MODEL` の書き込み（156-196 行。模型は線とブロックの役の節の `model:` が持つ。`docs/design.md` の「能力の棚卸し」の「AI の起こし方の包み → 落とす」）、`WORKS_ARCHON_VERSION`・`WORKS_CLAUDE_VERSION`（214-219 行。版の控えは線の `start` が始めの記録に書く。線の issue）、包み（adapter）と `WORKS_TESTSLOT`（持ち主の都合の物で、包みは「能力の棚卸し」で落とした）。

### E11 の 3 つ

1. Archon が持つ物: 命令の全部（run・respond・status・resume・cancel・abandon・--adopt）。殻は別名を作らず、そのまま渡す。
2. ASF が持つ物: `factory/consumer.py` が同じ事（`--cwd`・`--workflow-source` を殻が持ち、利用者の物は拒む・`bun <源>/packages/cli/src/cli.ts` で起こす）をしている。型は同じで、コードは写さない（E8）。
3. 要るか: 「能力の棚卸し」の「止め札。札を置く口は `bin/`」「周の鎖」と、`bin/AGENTS.md` の E15 の認証と隔離。足すのはつなぎだけ。
