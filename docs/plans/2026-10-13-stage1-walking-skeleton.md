<!-- coldwrite:skip ASF の役が読む作業の計画（issue の本文）。語は docs/design.md の「語」の節で定義 -->
# 段 1 歩く骨組み: 本物の 8 ブロックと線を本物の役で小さな対象に通しで回し、封じた差分を bin/apply で当てるまで届かせる（土台の計画 Task 7 を含む）。ASF の archon-lifecycle に渡す筋書きを、動かして確かめた形にする

置く先の提案: `docs/plans/2026-10-13-stage1-walking-skeleton.md`（issue の本文はこの文書の全部）。事前審査（今の works の計画の審査の指示書 p2.plan_review を、書き手と別の目で）を通してある。

## このリポジトリと、この issue の位置

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ `raiki61/claude-plugins` の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）の能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べた 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）・入口（`bin/`）に移している。

この issue を始める時の main には、次が入っている（入っていなければ始めない。下の「依存」）:

- 入口の殻 `bin/works-factory`（PR #63）。人は Archon の命令をそのまま打つ（`bin/works-factory workflow run …`）。殻は認証と置き場の隔離を整え、止めた Archon（`factory/pack.json` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351` の Archon の源）を `bun` で起こす。
- 8 つのブロック（issue #52〜#59）と線（issue #60）。各々は Archon の筋書きの試験（fixture。役を差し替えて配線だけを見る）と単体の試験で確かめてあるが、**本物の役（Claude）で、本物の 8 ブロックを線に並べて通しで回したことは、まだ 1 度も無い**。
- 小さな対象の種 `tests/e2e/target-seed/`（`stats.py` に仕込んだ 2 つの欠陥と、それを名指す依頼 `request_ok.json`）。

`docs/design.md` の「作りの順」の段 1（歩く骨組み）は、初めは「中身の薄いブロックを並べて通す」予定だった。持ち主の決め `overnight-speed`（`docs/owner-decisions.md`）でブロックの中身を先に作ったので、段 1 は **本物のブロックで通す** 形に変わる（段 3 の 1「線に全部の本物のブロックを並べ、`tests/e2e/` を通す」を前に出した物）。この issue がその段 1 で、1 つの PR にする（`bin/apply`・線の返りの欄・対象の作り方は CI だけで確かめられ、先に別の PR にもできるが、分ける依存は無い）。

この issue の後に出す issue から、ASF（Archon の作者が作った、issue から merge までの工程の束。止めた Archon の源の `.archon/workflows/sdlc/`）の回し方を `archon-ship` から `archon-lifecycle` に替えられるようにする。lifecycle は PR ごとに「動かして確かめる筋書き」（runtime scenario）を必ず走らせ、確かめられない間は何も取り込まない（`W/lifecycle/archon-lifecycle.yaml`:151-156・`W/lifecycle/commands/qualify-runtime.md`。`W` は止めた Archon の源の `.archon/workflows/sdlc`）。だから段 0〜1 は ship で回すと決めてある（`docs/owner-decisions.md` の「2026-10-11 の決めから導いた事」の「段 0〜1 を回す ASF の工程」）。この issue が、その筋書き（`harness/runtime.scenario.json`）を本物の通しで確かめた形にする。

## 読む物

- 根の `AGENTS.md`（E8〜E11・E13・E14・E18）・`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）・`lib/AGENTS.md`（E3）・`bin/AGENTS.md`（E15）・`tests/AGENTS.md`。
- `docs/design.md`: 「線」「ブロックの返りの約束」（特に merge・eyes・report の返り）「Archon の分かっていること」と未決 U1〜U8・「作りの順」。
- `docs/owner-decisions.md`: `overnight-speed`・`one-launcher`・`report-on-stop`・`diff-only-to-target`・`others-may-use`・`real-measure`・`superset`・`no-narrow`・`no-timeouts`・`small-core`・`carry`・`run-cost` と、「2026-10-11 の決めから導いた事」の「段 0〜1 を回す ASF の工程」。
- `docs/plans/2026-10-11-foundation.md` の Task 7（`bin/apply`）と「段 0 の終わりの確かめ」。
- `docs/plans/2026-10-12-groundwork-line-launcher.md` の A（線の節の id・`collect`・`result`・止め）と B（殻の振る舞い）。
- `docs/plans/2026-10-12-blocks/merge.md`（`merge/sealed.diff`・`merge/apply.diff` の置き方・hash・置かない時の決まり）と `fix.md`（組ごとの子の run）。
- ASF の取り付け命令が置いた物: `harness/END-TO-END.md`・`harness/runtime.scenario.json`・`harness/runtime.inputs.json`・`harness/harness.config.json`・`.factory/holdout/HOLDOUT.md`・`factory/consumer.py`（`invoke`・`harness_inputs`・`read_settings`）。
- 止めた Archon の源（`bin/_lib/place.py` の `archon_folder(cache_dir(env), commit)`。CI と同じ取り方）の中:
  - `W/lifecycle/archon-lifecycle.yaml`・`W/lifecycle/README.md`・`W/lifecycle/commands/qualify-runtime.md`
  - `W/verify-runtime/archon-verify-runtime.yaml`・`W/verify-runtime/README.md`・`W/verify-runtime/commands/verify-runtime.md`・`W/verify-runtime/scripts/read-scenario.py`
  - 文書 `packages/docs-web/src/content/docs/reference/cli.md` の `workflow run`（`--detach`・既定の作業ツリー・「Base branch precedence」440-462 行）・`workflow get`（`terminal_record`）・`workflow wait`（`attention.kind`・`respondTo`）・`workflow approve` と「Detached control verbs」・`workflow resume`・`workflow abandon`・`workflow cancel`。
  - `packages/workflows/src/schemas/terminal-record.ts`（`returns` の `available`・`unavailable`・`truncated` と `artifacts.root`）・`packages/workflows/src/artifact-pointer.ts` の頭（指し札の先の照らしは読む側の責め）。
- 今の works: `works/dev/use.sh` の `apply`（950-971 行）と `apply_checked`（396-433 行）・`works/.shared/core/report.py` の `stopped_run`（648-667 行）・`works/dev/target-seed/`・`works/dev/dogfood.sh`（種を回した入力の組）・`works/dev/use.sh` 1063-1086 行（`tdd_suite` の作り方）・`works/blk-fix/lib/tddloop.py` 296-299 行（実行器の呼び方）と 582-584 行（実行器が実行できるファイルか `.py` でないと輪を飛ばす）。

## 語

- 運び役: この issue の外で、持ち主の代わりに工程を起こし、関所に答え、PR を merge まで運ぶ人か AI（ASF の実装の役とは別）。
- 通し: 1 つの依頼を、本物の役で線の始めから報告まで回し、封じた差分を当てて対象の試験を確かめるまでの 1 回。
- 対象: 通しが直すリポジトリ。種 `tests/e2e/target-seed/` から作る使い捨ての git の木。
- 試みのフォルダ: 1 回の通しのために作る、リポジトリの外の空のフォルダ。対象・その origin・依頼・家を中に置く。run の置き場（Archon の artifacts）とは別の物。
- 家: 殻が対象ごとに使う Archon の DB と隔離した置き場の根（`WORKS_FACTORY_HOME`。`docs/plans/2026-10-12-groundwork-line-launcher.md` の B の 3）。
- 筋書き（runtime）: ASF の `archon-verify-runtime` が読む JSON（`harness/runtime.scenario.json`）。確かめの役（AI）が手順を道具で実行し、主張（assertion）ごとに `passed`・`failed`・`inconclusive` を証拠のファイルつきで返す。確かめの役はこの issue を読まないので、命令は JSON の中に全部書く。
- 別筋（holdout）: lifecycle の入力 `holdout` に渡す、筋書きと同じ形の別の JSON。作る側（ASF の実装の役）に見せない物。

## 目的

1. 本物の役で、本物の 8 ブロックを並べた線を、種の対象に通しで回す。依頼から、報告と、封じた差分を `bin/apply` で当てて種の落ちていた試験が通るまで届かせる。8 つのブロックが全部、通しの中で本物に走ったことを run の記録で示す。
2. 封じた差分を対象に当てる口 `bin/apply` を作る（土台の計画 Task 7。まだ無い）。今の works の `apply` の確かめ（消す行の許し・止まった run の許し・`git apply --check`）を落とさず、封じた hash の照らしと読み戻しを足す。
3. 通しで見つかったブロックと線のつなぎの不具合を、試験を先に赤にしてから直す。
4. 歩く骨組みで決めると書いた未決（`docs/design.md` の U1・U2 の型つきの成果物の半分・U6・U7、U8 と P2 の実物の確かめ、`docs/polyfills.md` の P1、`lib/AGENTS.md` の E3 の `deps:` の引き方）を、実測と文書で閉じて書く。
5. ASF の lifecycle に渡す入力を決め、`archon-verify-runtime` を本物で回して `verified` が返ることを確かめる。これが、次の issue から lifecycle に替える条件になる。

## 依存（この issue は次が全部 main に入ってから始める）

- issue #52〜#59（8 つのブロック）と issue #60（線）。線の節の id は `docs/plans/2026-10-12-groundwork-line-launcher.md` の A のとおりで入っている前提で書く。入った YAML と食い違えば、YAML を正として本文の id を読み替え、PR に書く。
- 入っている物: issue #47（P0。pack の形・`tests/archon.py`・CI の源）・issue #50（prereq。`lib/green_cert.py`・`lib/protect.py` ほか）・issue #61（殻。PR #63）・PR #34（lib-port）。
- 依存しない: issue #65（役が利用者の gh を通して GitHub の資格を読める件）。通しの種は GitHub を使わない。この issue では触らない。

## 置く・変えるファイル

作る:

- `bin/apply`（Python の実行ファイル。`bin/works-factory` と同じ頭で、`bin/_lib/apply.py` の `main` を呼ぶだけ）・`bin/_lib/apply.py`・`tests/bin/test_apply.py`
- `tests/e2e/make_target.py`（通しの対象を作り、後で片付ける。下の「対象の作り方」）・`tests/e2e/test_make_target.py`
- `tests/e2e/target-seed/junit-suite.sh`（種の TDD の実行器。git の mode は `100755`）
- `tests/e2e/test_scenario.py`（筋書きの形の試験。下の手順 3）

変える:

- `workflows/line/works-factory-line.yaml` の `collect` と線の返す節 `result`・その script（`workflows/line/scripts/` の物）・線の筋書き（`workflows/line/fixtures/` の `standard`・`final-stop`）: 下の「線の返りに足す欄」。
- 通しで見つかった不具合の直し: 当たったブロックのフォルダ（`workflows/<名>/`）・線・`lib/` のモジュールと、それぞれの試験。どれを直したかは PR に 1 件ずつ書く（手順 5）。
- `harness/runtime.scenario.json`・`harness/END-TO-END.md`・`harness/runtime.inputs.json`（`description` だけ）・`harness/harness.config.json`（`protected_paths` に `tests/e2e/target-seed/**`・`tests/e2e/make_target.py`）・`.factory/holdout/HOLDOUT.md`
- `docs/design.md`（U1・U2 の残り・U6・U7 を「決めた」に・U8 と P2 に実物の事実・「作りの順」の段 1 と段 3 の 1・段 2 の共有のファイルの一覧に守りのパスの足し・「ブロックの返りの約束」に「線の返り」・「段 1 の結果」の節を足す）・`docs/polyfills.md`（P1・P2・fan_out の子ごとの作業ツリーの候補の行）・`lib/AGENTS.md`（E3 の `deps:`）・`tests/AGENTS.md`（`tests/e2e/make_target.py` は筋書きが命令として呼ぶ通しの対象の作り手で、試験が import する助け（`tests/bin/`）ではない、と 1 行）・`README.md`（使い方の 5「当てる」と、線がまだ無いという文）・`docs/owner-decisions.md`（「段 0〜1 を回す ASF の工程」に、次の issue から lifecycle に替える入力と条件を 1 段落。書くのはこの PR だけで、運び役は書かない）・`docs/plans/2026-10-11-foundation.md`（Task 7 をこの issue を指す 1 行に・「段 0 の終わりの確かめ」の印）

## 約束

### bin/apply（土台の計画 Task 7）

`bin/apply <run-id> [--cwd <対象>] [--allow-delete] [--allow-stopped]`

1. 対象を決める: `--cwd` の値、無ければ打った場所。`bin/_lib/launcher.py` の `target_root` で git の根に直す（殻と同じ関数で、同じ対象から同じ家を引く。決め方を 2 か所に持たない）。
2. run を読む: 子のプロセスで `bin/works-factory workflow get <run-id> --json --cwd <対象>` を走らせ、JSON を読む（家・隔離・Archon の起こし方は殻の物を使う。`get` は工程を回す命令でないので、殻は認証の確かめもプラグインの選びもしない）。読めない・0 でない終わり・`terminal_record` が `null`（終わっていない run）・`returns.availability` が `available` でない（`unavailable` も `truncated` も）なら、終了の値 2 で 1 行言って止まる。
3. 当てる差分を選ぶ（`returns.value` は線の返す節 `result` の値。止めた Archon の `terminal-record.ts`）:
   - `value.apply` が在り `ok` が真なら、`value.apply.diff` と `value.apply.hash`。人が最後の関所を通した（か関所が開かなかった）run。
   - そうでなく `--allow-stopped` が在れば、`value.sealed.diff` と `value.sealed.hash`（`merge-seal` が封じた差分）。ただし `value.r2_status` が `redesign-needed` なら当てない（持ち主の決め `small-core`。merge の apply と同じ決まり）。最後の関所で止めた run の差分を、人が明示して当てる道（今の works の `WORKS_USE_ALLOW_STOPPED`。`use.sh` 409-424 行）。
   - どちらでもなければ、終了の値 1 で「置いた差分が無い」と結末の語（`value.outcome`）を言って止まる。封じていない差分（`merge-seal` より前で止まった run）は当てない（README の「約束すること」の「関所を通らなかった物は取り込まない」）。
4. 指し札を照らす: 指し札の `run_id` が `terminal_record.run_id` と同じ（`<run-id>` は短い id でもよいので、引数と比べない）。`path` が相対で、`terminal_record.artifacts.root` と `path` を結んだ実のパス（realpath）が `artifacts.root` の実のパスの下の、在る普通のファイル。違えば終了の値 1。
5. hash を照らす: ファイルの sha256 が 3 で選んだ hash と同じ。`apply` の道では、加えて `value.apply.hash` が `value.sealed.hash` と同じ。違えば終了の値 1 で「封じた hash と合わない」と両方の hash を言って止まり、対象は変えない。hash の正本は Archon の DB の run の記録で、置き場のファイルではない（ファイルを書き換えても記録の hash は変わらない）。
6. 消す行: `git apply --numstat --summary` に ` delete mode` が在れば、`--allow-delete` が無い限り終了の値 1 で消すファイルを並べて止まる（今の works の `WORKS_USE_ALLOW_DELETE` と同じ）。
7. `git apply --check` が通らなければ終了の値 1 で止まる（対象の手元の変更とぶつかる）。通れば `git apply` で当てる（commit しない）。
8. 読み戻す: `git apply -R --check` が通ること（当てた物が対象に在る）。通らなければ終了の値 1 で「当てたが読み戻せない」と言う。当てたファイルと「commit はしていない。試験を回してから commit する」を出して 0 で終わる。
9. 旗にしたのは、殻の選べる道（環境変数。利用者の環境の設定）と違い、この 1 回の当て方の選びだから。秘密を出さない・持ち主の環境の字を書かない（E14）。期限を置かない（`no-timeouts`）。

今の works から狭まる所（PR に名指す。どれも封じた hash を DB の記録から読む形と、README の約束から来る）:

- 鎖の最後の差分を当てる口（`use.sh apply <鎖の id>`）は持たない。周の鎖はまだ無い（`docs/design.md` の「周の鎖」）。鎖を作る issue が足す。
- 報告の節か線の `result` が落ちた run は当てられない（今の works は作業ツリーから差分を組み直して当てた）。封じた hash が記録に無い差分を当てない向きに落とす。run の作業ツリーは残るので、人は `git -C <作業ツリー> diff` で中身を見られる。
- 止まったかを言える記録が無い run を当てない（今の works は 1 行出して当てた）。上と同じ訳。

### 線の返りに足す欄

`bin/apply` は Archon の DB の記録から hash を読む。止めた Archon の `workflow get --json` が節の値を丸ごと出すのは、線の返す節（`result`）の `terminal_record.returns.value` だけで、ブロックの節の出力は `--verbose` の `outputPreview`（200 字で切る）しか出ない（`reference/cli.md` の `workflow get` の節）。だから線の `result` に次の欄を足す。`result` は `$collect.output.<欄>` だけを読む（`collect` は既に全部の返りを `if_skipped: null` で欄ごとに受けている。`result` から `merge-*` の節を直に読むと、線の返りが落ちる道が増える）。`collect` に読む欄が無ければ `collect` に足す。`docs/design.md` の「ブロックの返りの約束」に「線の返り」として書く。

- `apply`（object・null 可）: `merge-apply` の返りの `ok`・`hash`・`diff`・`reason`。飛ばされたら `null`。
- `sealed`（object・null 可）: `merge-seal` の返りの `ok`・`hash`・`diff`。飛ばされたら `null`。
- `r2_status`（string・null 可）: eyes の返りの `r2.status`。省いた・飛ばされたら `null`。
- `report`（指し札・null 可）: report の返りの `report`（人が `workflow get` から報告の本文を開くため）。

### 種の入力

通しは次の入力で回す（今の works の `dogfood.sh` が種を回した組を、線の入力に写した物。筋書きの JSON にも同じ値を字のまま書く）:

- `request`: 試みのフォルダの `request.json`（`make_target.py` が種の `request_ok.json` を写した物）の絶対パス。
- `test_cmd`: `python3 -m unittest -v`（対象の根で走る 1 行）。
- `tdd_suite`: `junit-suite.sh`（対象の根からのパス）。頭に `#!/bin/sh`、中は `out=$1; shift` の後に `PYTHONDONTWRITEBYTECODE=1 exec uv run --no-project --with pytest==<止めた版> pytest -p no:cacheprovider --continue-on-collection-errors --junitxml="$out" "$@"`。今の works が pytest の `test_cmd` から書いた実行器（`use.sh` 1072-1081 行）と同じ形で、今の works の `tddloop.py` 296-299 行は書き先の後ろに試験のファイルと node id を足して呼ぶ。実行できるファイルでないと輪が黙って飛ばされる（`tddloop.py` 582-584 行）ので mode を 100755 にする。種は対象の側の物なので、E13（`commands/` と `lib/` の言語の名）に当たらない。
- `thickness`: `標準`（全部の単位を標準の深さに固定する。軽量だと差分の審査と R1〜R4 が省かれ、eyes が本物に走ったことを示せない）。
- `final_gate`: 空（既定。最後の関所はいつも開く）。

### 対象の作り方（tests/e2e/make_target.py）

- `python3 tests/e2e/make_target.py make <試みのフォルダ>`: `<試みのフォルダ>`（リポジトリの外の空のフォルダ。中に在る物があれば止まる）の下に次を作り、絶対パスを JSON 1 行で出す（`{target, origin, request, home}`）。
  1. `origin/`: 種の `request_ok.json` を除いた中身（`junit-suite.sh` の mode を含む）で 1 つの commit を持つ裸のリポジトリ（既定の枝 `main`、`HEAD` が `main` を指す）。
  2. `target/`: `origin/` を clone した作業ツリー（`origin/HEAD` が在る）。
  3. `request.json`: 種の `request_ok.json` の写し（対象の外）。
  4. `home/`: 空のフォルダ（`WORKS_FACTORY_HOME` に渡す家）。
  5. 呼んだ checkout の git の私用の置き場（`git rev-parse --git-dir` の下の `works-factory-e2e/homes`）に `home/` と `target/` の絶対パスを 1 行足す（後の片付けのため。作業ツリーには何も書かない。確かめの節は前後の `git status --untracked-files=normal` を比べる（止めた Archon の `dag-executor.ts` の `mutates_checkout: false` の照らし））。
- `python3 tests/e2e/make_target.py teardown`: 上の控えの行ごとに、その家で終わっていない run を `bin/works-factory workflow cancel` で止め（止まらなければ `workflow abandon`）、控えから消す。控えはその checkout の物だけなので、同じ機械で走るほかの確かめの run には触らない。プロセスを名で止めない。
- 訳: 止めた Archon の `workflow run` は既定で run ごとの作業ツリーを切り、切る元の枝を「`.archon/config.yaml` の `worktree.baseBranch`」か「登録の既定の枝」か「届く remote が告げる HEAD」で決め、`main` を推測しない（`reference/cli.md` 440-462 行）。remote の無い使い捨ての木では切る元が決まらない。普通の利用者の対象には remote が在るので、対象の側に設定を足さず、remote の在る形を種でも作る（E14）。依頼のファイルを対象の外に置くのは、判定の役が依頼のファイルを対象のコードとして読まないため。作業ツリーが run ごとに切られるので、当てる前の対象（`target/`）は写した直後のまま残る。試みのフォルダをリポジトリの外に置くのは、ASF の実装の役が作業の途中で commit する（`W/implement/archon-implement.yaml`）ので、その中に混ざらないようにするため。

### 殻を続けて打つ時の決まり（実装の役・運び役・筋書きの確かめの役に共通）

- 環境変数は道具の呼び出しをまたいで残らないので、`bin/works-factory` と `bin/apply` の呼び出しには毎回 `WORKS_FACTORY_HOME=<家>` を前に付ける。
- 起こす: `WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow run works-factory-line --cwd <target> --detach --json --input request=<request> --input test_cmd='python3 -m unittest -v' --input tdd_suite=junit-suite.sh --input thickness=標準`。返った確認の `runId` が、この run の id（fix の組の子の run の id は別に在る）。
- 待つ: `WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow wait <run> --json --timeout 540 --cwd <target>` を繰り返す。`--timeout` は、道具の 1 回の呼び出しの上限（Claude Code の Bash は既定 120 秒・最大 600 秒）より短くして、呼び出しを有限にするための区切りで、run に期限を置く物ではない（run は区切りで止まらない。持ち主の決め `no-timeouts` の外）。道具の呼び出しの上限は 600 秒に上げて呼ぶ。終了の値 3（区切りが来た）なら同じ命令をもう一度打つ。
- `wait` の返りの `attention.kind` で分ける（`reference/cli.md` の `workflow wait`）:
  - `terminal`: 終わり。
  - `awaiting_response`: `get <respondTo.runId>` で関所の文を見て、`WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow respond <respondTo.runId> approve --detach --json --cwd <target>` で答える（`respondTo.runId` は子の run のことがある）。`--detach` を必ず付ける: 付けないと答えた後の run の続き（数時間）が 1 回の道具の呼び出しの中で走り、上限で殺されると持ち主の居ない `running` の run が残って再開できない（`workflow approve` の「In human mode approve/reject auto-resume the run inline」と P1）。
  - `stalled_tool_calls`: `workflow logs <run>` を見て、待ちを続ける（止めない）。
  - `owner_lost`・`action_required`・読めない返り: 止めて、`workflow get <run> --json` を証拠に残す（実装の役は手順 5 の不具合として扱う。確かめの役はその主張を `inconclusive` にする）。

## 手順（試験が先に赤）

1. `tests/bin/test_apply.py` を書いて赤を見る（`bin/_lib/apply.py` が無い）。`workflow get` の答えは偽の関数を渡すか、`tests/bin/test_launcher.py` と同じく PATH の頭に偽の `bun` を置いて殻ごと走らせる。対象と差分は `tests.bin.gitkit` の一時のリポジトリで作る。
   - `test_apply_applies_sealed_diff`（当たり、`git apply -R --check` が通り、0 で終わる）
   - `test_apply_refuses_changed_diff`（置き場のファイルを 1 バイト変えると 1 で止まり、両方の hash を言い、対象の `git status --porcelain` が前と同じ）
   - `test_apply_refuses_apply_hash_not_sealed`（`apply.hash` と `sealed.hash` が違う）
   - `test_apply_refuses_when_nothing_placed`（`apply` も `sealed` も無い・`apply` が `ok: false` で `--allow-stopped` が無い）
   - `test_apply_stopped_run_needs_flag`（`apply` が `null` で `sealed` が在る: 旗が無ければ 1、`--allow-stopped` で封じた差分が当たる）
   - `test_apply_stopped_run_refuses_redesign`（`--allow-stopped` でも `r2_status` が `redesign-needed` なら 1）
   - `test_apply_refuses_unreadable_run`（`terminal_record` が `null`・`returns` が `unavailable`・`truncated`・`get` が 0 でない → 2）
   - `test_apply_refuses_pointer_outside_root`（`..`・絶対パス・symlink で外へ出る・`terminal_record.run_id` と違う `run_id`）
   - `test_apply_accepts_short_run_id`（引数が短い id でも、`terminal_record.run_id` と指し札が同じなら当たる）
   - `test_apply_refuses_delete_unless_allowed`
   - `test_apply_refuses_when_check_fails`（対象にぶつかる手元の変更。対象は変わらない）
   - `test_bin_apply_asks_launcher_for_get`（`bin/apply` を子のプロセスで走らせ、偽の `bun` が受けた引数が `workflow get <run> --json --cwd <対象>` で、対象の外から打っても同じ家を引く）
2. 線の筋書き（`workflows/line/fixtures/standard.stubs.yaml`・`final-stop.stubs.yaml`）に `result` の欄の照らしを足して赤を見る（`standard` は `apply.ok` が真で `sealed.hash` と `apply.hash` が同じ、`final-stop` は `apply` が `null` で `sealed` が在る）。`tests/e2e/test_line_scenarios.py` で回す。
3. `tests/e2e/test_make_target.py`・`tests/e2e/test_scenario.py` を書いて赤を見る:
   - `make` の後: `target/` の `git status --porcelain` が空・`git ls-remote --symref origin HEAD` が `refs/heads/main` を告げる・`request_ok.json` が `target/` に無い・`target/junit-suite.sh` が実行できる（mode 100755）・`target/` で `python3 -m unittest -v` が 3 件中 2 件落ちる（種が赤であることの確かめ）・`./junit-suite.sh <書き先>` を直に実行すると 2 件の failure を持つ JUnit XML を書く・呼んだ checkout の `git status --porcelain --untracked-files=normal` が前と同じ。
   - `teardown`: 偽の `bun` で、控えの家ごとに `workflow cancel` が呼ばれ、控えが空になり、ほかの checkout の控えに触らない。
   - `test_scenario.py`: 止めた Archon の源の `W/verify-runtime/scripts/read-scenario.py` に `INPUTS_SCENARIO=harness/runtime.scenario.json` で渡して 0 で終わる（源が無ければ `tests/archon.py` の名前つきの見送り。CI では見送らない）。`harness/END-TO-END.md` の節の見出しに、筋書きの主張の `id` が全部、同じ順で在る。
4. `bin/_lib/apply.py`・`bin/apply`・線の `collect` と `result`・`make_target.py`・`junit-suite.sh` と、筋書きの JSON（下の「筋書きの入力」）を書いて 1〜3 を緑にする。全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。
5. 通しを本物で回す（この PR の芯。費用は問わない）。「殻を続けて打つ時の決まり」に従う:
   1. `python3 tests/e2e/make_target.py make <試みのフォルダ>` で対象・依頼・家を作る。
   2. run を起こし、`wait` と `respond … approve --detach` で終わりまで運ぶ。
   3. 当てる前に、対象で `python3 -m unittest -v` を走らせて控える（2 件落ちる）。`returns.value.apply.diff` の先のファイルを試みのフォルダに写して控え、1 バイト変えて `./bin/apply <run> --cwd <target>` が 1 で止まり対象が変わらないことを見て、控えから戻す。
   4. `./bin/apply <run> --cwd <target>` で当て、`python3 -m unittest -v` で 3 件が全部通ることを見る。
   5. `workflow get <run> --json --verbose --cwd <target>` と、fix の組の子の run ごとの同じ命令の出力を試みのフォルダに保存し、受け入れ 2 の表を作る。
   6. `python3 tests/e2e/make_target.py teardown`。
   - 通しが途中で落ちる・おかしな結末を出すたびに、superpowers:systematic-debugging の形で原因を確かめ、落ちたブロック（か線か `lib/`）の試験か筋書きに **その不具合で赤になる 1 本を先に足して赤を見てから** 直す（superpowers:test-driven-development）。直したら、通しを新しい試みのフォルダで最初から回し直す（直した `workflows/` は新しい run でしか読まれない。`workflows/` は run の始めに写し取られる）。
   - 直しが能力を削る・約束（`docs/design.md` の「ブロックの返りの約束」）の欄を変える・持ち主の決めとぶつかる時は、直さずに止めて PR に書き、持ち主の答えを待つ（`superset`・`no-narrow`）。殻（`bin/_lib/launcher.py`）の不具合は、直さずに別の issue にして PR に書く。
   - 入れ子の認証: この手順は、実装の役の会話の Bash から殻を起こす。殻は普通の利用者の道（ホストのログイン・`ANTHROPIC_API_KEY`・選べる道の `WORKS_FACTORY_KEYCHAIN_ITEM`）で認証を拾う。拾えずに殻が止まった時は、どの道で何が無かったかを殻の 1 行のまま PR に書き、この手順の 5 を運び役に渡す（下の「PR の後に運び役が行う確かめ」の 1）。手順 1〜4・6・7 はそのまま進める。
6. 未決を閉じる。仕組みは足さない。足りない時は `docs/polyfills.md` に「（予定）」の行を足すだけにする。通しの本番の run（手順 5）は壊さず、止める・殺す確かめは別の使い捨ての run で行う:
   - U1（`resume` の後の run の id は同じか）: 文書で決める（`workflow resume` は id を指して同じ run を続ける。`--adopt` は新しい run を起こす。`reference/cli.md` の `workflow resume`・`--adopt`）。加えて、使い捨ての run を 1 つ起こし、最初の関所で `workflow approve <run> --json`（答えを記録するだけで続きを走らせない形）の後に `workflow resume <run> --detach --json` を打ち、続いた run の id が同じかを見る。
   - P1（持ち主の居ない `running` の run）: 別の使い捨ての run で、役の節が走っている間に、`--detach` の子のプロセスを pid で止める。pid は `workflow abandon --json` の `recordedPid` の案内か、`ps` を家のパスで絞って見つける（名で止めない・`pkill -f` の広い形を使わない）。`workflow get`・`workflow wait` が何を言うか（`owner_lost`）、`workflow resume` が拒むか、`workflow abandon` が run の作った作業ツリー（書きかけを含む）を消すこと（`reference/cli.md` の `workflow abandon`）と、`workflow run --adopt <run>` で新しい run として続きを起こせるかを書く。結果で P1 の「埋め」の行を「足りる（埋め無し）」か「足りない（置き場の予定）」に直す。
   - U2 の残り（型つきの成果物が include ごとに分かれて見えるか）: 通しの run の `$ARTIFACTS_DIR/.archon/` の型つきの成果物の一覧で、`test-gate-base` と `test-gate-final` の `green-cert` が別の鍵で載るかを書く（線の計画 A の約束の直しの 7 が report ブロックに残した半分）。
   - U6: run の transcript（`--detach --json` の確認の `transcriptPath` の JSONL）に、役の道具の呼び出し（読んだ・書いたファイルのパス）が載るか。載る形を 1 例引き、今の works の包みが取っていた読んだ証拠と書き込みの記録（`docs/design.md` の「能力の棚卸し」の U6 の行）がそこから取れるかを書く。
   - U7: 下の「筋書きの入力」と、運び役の確かめの run の id で閉じる。
   - U8: fix の組ごとの子の run が自分の作業ツリーを持ち、差分が親に戻ったかを、run の記録（子の run の id と作業ツリーのパス・戻した組）で書く。fix の PR（#55）が書いた事と食い違えば、両方を書く。
   - P2: 通しの run で、線の返しの節が飛ばされた値を `null` で受けたことを 1 例引く。
   - E3 の `deps:`: script の節が外のパッケージ（PyYAML など）を本物の run でどう得たか（`runtime: uv` の `deps:` か、ほかの道か）を書き、`lib/AGENTS.md` の E3 の「段 1 で決める」をその事実で閉じる。ブロックごとに違う道を取っていたら、`pyproject.toml` の 1 か所の宣言を引く形にそろえる直しをこの PR で入れる（`outside-packages-ok` の「依存の宣言は 1 か所」）。ただし止めた Archon の `runtime: uv` は対象の作業ツリーを cwd に走る（`guides/script-nodes.md` 73-74・232 行）ので、自分の `pyproject.toml` を持つ対象では uv がその環境を使う。種はそれを持たないので、この確かめは「自分の `pyproject.toml` を持つ対象では未確かめ」と書いて残す。殻で環境を変える直しが要るなら、別の issue にする。
   - 段ごとの費用と時間: report が載せた段ごとの費用と時間を表にして PR に書く（持ち主の決め `run-cost`）。
7. 文書を直す（上の「置く・変えるファイル」の変える物と、下の「筋書きの入力」「段 1 の結果」）。全部の試験が緑。

## 筋書きの入力（ASF の lifecycle に渡す物）

lifecycle の入力のうち、このリポジトリが決める物:

| 入力 | 値 | 決めた所 |
| --- | --- | --- |
| `scenario` | main の checkout の `harness/runtime.scenario.json` の絶対パス | この issue |
| `holdout` | 空 | この issue |
| `required_checks`・`protected_paths` | consumer が `harness/harness.config.json` から足す | 在る |
| `merge_method` | `squash` | 今の main の取り込み方 |
| `merge_mode`・`discovery_publication` | 既定（`approve`・`preview`） | lifecycle の既定 |

- `scenario` を候補（PR）の checkout でなく main の checkout から渡す訳: 筋書きは確かめる側の物で、PR が自分の筋書きを緩めて通れないようにする（`W/verify-runtime/README.md`「Scenario secrecy from a separate builder is the caller's responsibility」）。`harness/**` は守りのパスで、筋書きを変える PR は merge queue が人の手に残す。
- 種と `make_target.py` を守りのパスに足す訳: 種は筋書きが当てる欠陥の組で、作る側が自分で変えられると筋書きを通せる（ASF が置いた `harness/mutations/defects.json` の頭の「A builder that can edit its own defect set can pass it」と同じ向き）。`tests/e2e/` のほかの試験（`test_line_scenarios.py` など）は含めない。
- `holdout` を空にする訳: lifecycle は別筋が空ならその確かめを飛ばし、筋書きだけで判定する（`W/lifecycle/README.md`・`qualify-runtime.md`）。別筋の 3 つの筋はどれも本物の通しを 1 回ずつ要り、PR ごとに回すと 1 つの PR の確かめに通しが 4 回走る。別筋は作る側に見せない物だが、`.factory/holdout/HOLDOUT.md` が公開のリポジトリに在り、今は隠せていない。だから別筋はこの issue で 1 度だけ本物で回して確かめ（下の「運び役」の 2・4）、PR ごとには回さない。隠した別筋を PR ごとに回すかは、別筋をリポジトリの外に移す時に決め直す。
- 費用の事実: 筋書きは PR ごとに本物の通しを 1 回（報告の形が崩れた時はもう 1 回、lifecycle の 1 度の直しの後にもう 1 回）走らせる。1 回の時間と費用は手順 6 の表で測り、`docs/design.md` の「段 1 の結果」に書く。lifecycle に替えるのは持ち主の前の決め（`docs/owner-decisions.md` の「開発の進め方」の「段 2 からは ASF の lifecycle」と、「導いた事」の「lifecycle は段 2 から」）で、筋書きを走らせるのは lifecycle の決まりそのものなので、この費用はその決めに含まれる。

### harness/runtime.scenario.json（書き直す）

止めた Archon の `read-scenario.py` が受ける形（`assertions` の `id`・`description`、`environment` の `ownership: external`・`setup`・`start`・`teardown`・`candidate_command`）。確かめの役はこの issue を読まないので、命令は全部 JSON の中に字のまま書く（上の「殻を続けて打つ時の決まり」と「種の入力」の中身を、確かめの役に向けて書き直して入れる。issue の手順の番号で指さない）。

- `environment`: `setup`・`start` は空（対象は主張の手順の中で試みごとに作る）。`teardown` は `python3 tests/e2e/make_target.py teardown`（確かめの節が落ちても切り離した run が走り続けないよう、その checkout が作った家の run を止める。`ownership: external` の約束「Consumers must provide a lifetime owner」）。`candidate_command` は今のまま（作業ツリーが追跡の変更無しで、`git rev-parse HEAD` が候補の版）。
- 主張は次の 4 つ。どれも、確かめの役が道具の出力を証拠のファイルに残す前提で書く（`W/verify-runtime/commands/verify-runtime.md`）。試みのフォルダは、この試みの置き場（attempt directory）の下に新しく作る。
  1. `request-to-report`: `make_target.py make` で対象・依頼・家を作り、run を起こし、関所で止まるたびに関所の文を見て `approve` で答え、終わりまで運ぶ。期待: `run --detach --json` の確認が `runId` をちょうど 1 つ返す・`workflow get <run> --json` の `terminal_record.status` が `completed`・`returns.value.outcome` が report の結末の 10 語の 1 つ・`returns.value.report` の先の報告の本文が空でない・当てる前の対象の `git status --porcelain` が空。認証が拾えずに殻が止まった時は `inconclusive` にし、殻の 1 行を reason に書く（製品の不具合ではない）。
  2. `every-block-ran`: 1 の run の `workflow get <run> --json --verbose` で、線の中の include の id（`test-gate-base`・`judge`・`plan`・`plan-review`・`fix`・`test-gate-final`・`eyes`・`merge-seal`・`merge-apply`・`report`）ごとに、節の id の中に `<include の id>__` の区切りを含む節が 1 つ以上 `completed`（計画の往復の中の節は `plan-rounds.` の頭が付く。止めた Archon の `dag-executor.ts` 4322-4331 行）。fix の役の節は組ごとの子の run に在るので、`workflow runs` で親の子の run を引き、子ごとの `get --json --verbose` で見る。役の節は `execution` に provider と模型が載る。期待: 全部の id が満たす。eyes の R1〜R4 の役の節が `completed`（深さを標準で回したので省かれない）。
  3. `changed-diff-refused`: 1 の run で、当てる前に、`returns.value.apply.diff` の先（`terminal_record.artifacts.root` の下）を試みのフォルダに写して控え、1 バイト変えてから `./bin/apply <run> --cwd <対象>` を呼ぶ。期待: 0 以外で終わり、hash が合わないことを言い、対象の `git status --porcelain` が空のまま。その後で控えから元に戻す。
  4. `sealed-diff-fixes-seed`: 3 の後、対象で `python3 -m unittest -v` を走らせて控え、`./bin/apply <run> --cwd <対象>` で当て、もう一度走らせる。期待: 当てる前は依頼が名指した 2 件（`test_mean_of_three`・`test_clamp_above_range`）が落ち、当てた後は 3 件全部が通る。対象の `git diff --stat` は空でなく、変わったファイルは報告が挙げたファイルの中だけ。
- 消す: 今の筋書きの「`workflows/*/scripts/stub.py` が在る間は inconclusive」の前提（段 2 の古い形の名残。ブロックは中身ごと入った）と、「線が無い間は inconclusive」の前提。
- この筋書きは SDLC の工程（`archon-*`）を起こさない（`W/verify-runtime/README.md`「must not recursively invoke the SDLC pack」）。起こすのは自分の線 `works-factory-line` だけ。

### harness/END-TO-END.md（書き直す）

頭に「機械が読む正本は `harness/runtime.scenario.json`。この文書は人が読む要約」と書き、4 つの主張を `id` を見出しにした節にして、各々の目的・期待・落ちたと言える物だけを書く（命令は JSON に 1 か所。写さない）。「今の状態: まだ回せない」の節を消す。節の見出しと主張の `id` が合うことは `tests/e2e/test_scenario.py` が見る。

### harness/runtime.inputs.json（description だけ直す）

「線 works-factory-line と…が在るまで、cli.invoke は空のまま」の文を消し、「止めた Archon の工程はこのファイルを読まない（lifecycle に渡すのは `scenario` と `holdout` の絶対パスだけ）」と書く。ASF の runtime host を使わない訳（子に Claude の資格を渡さない・300 秒で打ち切る・E12）は残す。ほかの欄は変えない。

### 別筋（holdout）

- 置き場: リポジトリの外（運び役の機械の `${XDG_STATE_HOME:-$HOME/.local/state}/works-factory/holdout/runtime.holdout.json`）。リポジトリにも、この issue と PR の本文にも中身を書かない（作る側に見せない確かめ。`W/verify-runtime/README.md`「Scenario secrecy … is the caller's responsibility」）。
- 形は筋書きと同じ。中身は `.factory/holdout/HOLDOUT.md` の 3 つの筋（同じ対象に 2 つの依頼を続けて回す・関所で待っている間に Archon を起こし直す・最後の関所で拒むと何も当たらない）を主張にした物。
- この PR で `.factory/holdout/HOLDOUT.md` を直す: 「今は回せない」と「lifecycle に空で渡す」の節を、上の `holdout` を空にする訳に直す。2 つの依頼の筋に「A を当てた後、対象で commit して origin に push してから B を回す」を足す（run の作業ツリーは origin の枝から切られるので、当てただけの A の上には B が乗らない）。`./bin/apply` に `--cwd <対象>` を書き、関所の答えは `respond … --detach` で打つと書く。拒む筋の期待に「`./bin/apply` は置いた差分が無いと言って 1 で終わる」と結末の語 `stopped_by_human` を書き、`--allow-stopped` を付ければ封じた差分が当たることを足す。

## 受け入れ

1. 手順 1〜3 の試験が先に赤で入り、後で緑。赤と緑の出力の要約を PR に書く。全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑（CI の `tests` も緑。CI は本物の通しを回さない）。
2. 本物の通しが 1 度、最初から最後まで通った。PR に次を書く:
   - run の id（親と fix の子）・works-factory の commit・止めた Archon の commit・Claude Code の版（始めの記録の版の控え）
   - 結末の語と報告の本文の頭
   - include の id ごとに `completed` の節の数と、役の節の provider と模型の表（セルは短い値だけ）
   - 1 バイト変えた差分を `bin/apply` が拒んだ出力と、当てた後の `python3 -m unittest -v` の出力
   - 通しで見つけて直した不具合の一覧（1 件ごとに: 落ちた節・原因・先に赤にした試験の名・直したファイル）
   - 段ごとの費用と時間の表
   - `bin/apply` で今の works から狭まる 3 つ（上の「今の works から狭まる所」）
3. `docs/design.md` の U1・U2 の残り・U6・U7 が「決めた」になり、U8・P2・P1・E3 の `deps:` に実物の事実と run の id が書いてある。決めは事実から 1 つに決まる物だけで、決まらない物は「持ち主の答え待ち」と書いて PR の冒頭に並べる。
4. 層の試験（各階層の `AGENTS.md` の機械の行）が全部緑。`bin/` に持ち主の環境の字が無い（E14）。
5. 範囲の外のファイルに差分が無い。

### PR の後に運び役が行う確かめ（この PR を merge する前の受け入れ）

ASF の工程の中から ASF の工程を起こさない（入れ子の SDLC）ので、次は ASF の実装の役でなく運び役が回す。

- 置き方: 運び役の main の clone から `git worktree add <木> <PR の head>` で PR の head の作業ツリーを作り、その中で回す（consumer は clone の共有の git の置き場から `.factory/consumer.json` を読む。`factory/consumer.py` 58-72 行）。consumer は `--cwd` に作業ツリーの根を渡し、Archon は既定で remote の HEAD（main）から run の作業ツリーを切るので、`--no-worktree` を付けて PR の head の木のまま回す。

1. 手順 5 を実装の役が認証の都合で回せなかった時は、運び役が同じ手順で回し、受け入れ 2 の材料を PR に書き足す。
2. 別筋の JSON をリポジトリの外に書き、`read-scenario.py` の照らしを通す。
3. 筋書きの確かめ: PR の head の木で `python3 factory/consumer.py run archon-verify-runtime --no-worktree --input scenario=<PR の head の木>/harness/runtime.scenario.json --input candidate=<PR の head の sha>`（以後の lifecycle は main の checkout の筋書きを渡すが、新しい筋書きはこの PR が入れるので、この 1 回だけは PR の head の物を渡し、そう PR に書く）。返りが `verified: true`。
4. 別筋の確かめ: 同じ命令で `scenario=<別筋の JSON>`。返りが `verified: true`。
5. 3・4 の run の id・`verdict`・報告のパスを PR に書く。この PR は `docs/design.md` の「段 1 の結果」に、それを書く欄を「（運び役が書く）」で置き、運び役が PR の枝に 1 commit で書き足す。3 か 4 が `failed` なら、見つかった不具合を手順 5 の形で直してから回し直す。`inconclusive` なら reason を読み、筋書きの書き方か環境の問題として直す（筋書きを緩めて通さない）。

## 範囲（触らない物）

- 線とブロックの返りの約束の欄（`docs/design.md` の「ブロックの返りの約束」）は、線の `collect`・`result` に足す欄の外は変えない。変える要が出たら止めて PR に書く。
- `bin/_lib/` の今の works から持ってきた部品（`auth_launch.py`・`claude_auth.py`・`isolate.py`・`toolset.py`・`hostgh.py`）の中身（E15）と、`launcher.py`（`target_root` を呼ぶだけ）。通しで殻の不具合が見つかったら、直さず別の issue にする。
- ASF の取り付け命令が置いた物のうち `factory/`・`FACTORY.md`・`FACTORY_RULES.md`、`harness/` の中の書くと決めた 4 つ以外（`harness/mutations/` は段 3 の較正 `tests/calibration/` で扱う）。
- 周の鎖・関所の間の止め・`stopped_by_request` の道（持ち主の答え待ち。`docs/plans/2026-10-12-groundwork-line-launcher.md` の A の「止め」）。
- 段 3 の物: 受け入れの一覧の全部の行の証・graph の節の表・較正・今の works との比べ。
- PR を作る・merge する道（E17 の選べる道）。`bin/apply` は差分を作業ツリーに当てるだけで commit しない。

## E11 の 3 つ

1. Archon が持つ物: run の記録と返す節の値（`workflow get --json` の `terminal_record`）・待ち（`workflow wait`）・関所の答え（`workflow respond`）・切り離した起動と答え（`--detach`）・run ごとの作業ツリー・止めと片付け（`cancel`・`abandon`）。全部そのまま使う。`bin/apply` は Archon に無い「封じた差分を対象に当てる」口で、`docs/design.md` の 4 つの層の表で入口が持つと決めてある。
2. ASF が持つ物: `archon-verify-runtime`（筋書きの読みと、証拠つきの主張の判定）と `archon-lifecycle`（候補の版の照らし・1 度の直し・別筋）。筋書きの形と照らしは ASF の物をそのまま使い、コードは写さない（E8）。封印と読み戻しの型は `docs/asf-notes.md` の A5（外への書き込みは 1 つの script で読み戻す）と A6（封印）。
3. 本当に要るか: 「能力の棚卸し」の「差分の封印と外への書き込み（新）」（`bin/apply`）と、`docs/design.md` の段 1（U1〜U7）。今の works の `use.sh apply` の確かめ（消す行・止まった run・`--check`）を落とさない（`superset`）。新しく足す仕組みは `make_target.py` だけで、対象を作る・片付けるの 2 つの口しか持たない。

## 持ち主に聞くこと

無し。決めた所はどれも、持ち主の前の決め（`diff-only-to-target`・`one-launcher`・`others-may-use`・`superset`・`small-core`・`no-timeouts`・「段 2 からは ASF の lifecycle」）か、ASF と Archon の文書（上の引用）で 1 つに決まる。`bin/apply` で今の works から狭まる 3 つは、README の約束「関所を通らなかった物は取り込まない」から来る物として PR に名指す。持ち主の答え待ちのまま残る物（関所の間の止め・再審などを新しい会話で回す仮の判断）は、この issue の外で、通しは答えに依らず回せる。
