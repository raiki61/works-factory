# 段 1 歩く骨組み: 本物の 8 ブロックと線を本物の役で小さな対象に通しで回し、今の works の能力を 1 行ずつ run の記録で確かめ、封じた差分を bin/apply で当てるまで届かせる。ASF の archon-lifecycle に渡す筋書きを、動かして確かめた形にする

置く先: `docs/plans/2026-10-13-stage1-walking-skeleton.md`（main に在る版を置き換える。置き換えは issue #101 の merge の後にする。#101 の本文は、main に在る版の「約束」の `bin/apply` の 1〜9・「今の works から狭まる所」・「対象の作り方」・手順の試験の名を正本として指すため）。issue は 2 つに分けて出す（下の「issue の切り方」）。issue の本文はこの文書の全部。main に在る版から動かした物: `bin/apply`・`tests/e2e/make_target.py`・種の実行器は issue #101 に、線の返りの欄（`apply`・`sealed`・`r2_status`・`report`）は線の配線の文書 `docs/plans/2026-10-13-line-wiring.md` の部分 A に移した。足した物: 今の works の能力を本物の run の記録で 1 行ずつ機械で確かめること（「能力の行の照らし」）と、落とし穴の確かめ（K1〜K20）。

## issue の切り方

- 段 1a: 下の手順 1〜5・7 と受け入れ 1〜3・6・7（照らしの表と道具・本物の通し・見えなかった行の決め・筋書き）。この文書の芯。
- 段 1b: 下の手順 6 と受け入れ 4・5（筋書きでは確かめられない Archon の振る舞いの確かめと、未決 U1・U2・U6・U7・U8・P1・P2・層の E3 の `deps:` を閉じる文書）。段 1a と同じ時に回してよい（触るファイルが重ならない。`docs/design.md` の節が違う）。
- どちらの issue も本文はこの文書の全部で、頭に「この issue は段 1a（か 1b）」と 1 行書く。「PR の後に運び役が行う確かめ」は段 1a の PR で行う。

## 冒頭

- 何の話か: works-factory の 8 つのブロックと線は、それぞれの試験と筋書き（役を差し替えて配線だけを見る試験）では確かめてあるが、本物の役（Claude）で通しで回したことが 1 度も無い。ブロックの PR は ASF の審査を通ったのに、持ち主の側の目が毎回、今の works から黙って落ちた能力を見つけた。
- この issue でする事: 種の対象に本物の通しを回し、今の works の能力の棚卸し（`docs/plans/2026-10-13-capabilities/`。1 行 = 1 能力）の行ごとに、本物の run の記録で「見えた」かを機械で照らす。見えない行は、訳を名指すか、不具合として試験を先に赤にして直す。あわせて未決 U1・U2 の残り・U6・U7・U8・P1・P2・層の E3 の `deps:` を実測で閉じ、ASF の lifecycle に渡す筋書きを本物で `verified` にする。
- 読者に求める物: ASF には「受け入れ」がこの issue の約束。持ち主に聞く事は無い（決めはどれも前の決めか Archon と ASF の文書で 1 つに決まる。末尾の「持ち主に聞くこと」）。

## 語

- works-factory: このリポジトリ。修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直している。
- 今の works: 前の形の工場。公開リポジトリ `raiki61/claude-plugins` の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`。その能力を 1 つも落とさない（持ち主の決め `superset`。能力を削る直しは人に上げる `no-narrow`。どちらも `docs/owner-decisions.md`）。
- 線・ブロック: 線は `workflows/line/`（ブロックを並べた 1 本の工程）。ブロックは `workflows/<名>/` の 8 つ（judge・plan・plan-review・fix・test-gate・eyes・merge・report）。
- ASF: Archon の作者が作った、issue から merge までの工程の束（止めた Archon の源の `.archon/workflows/sdlc/`。以下 `W`）。lifecycle はその 1 本で、PR ごとに筋書きを走らせる。
- 止めた Archon: `factory/pack.json` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351` の源。`bin/_lib/place.py` の `archon_folder(cache_dir(env), commit)` で CI と同じに取る。
- 運び役: この issue の外で、持ち主の代わりに工程を起こし、関所に答え、PR を merge まで運ぶ人か AI（ASF の実装の役とは別）。
- 通し: 1 つの依頼を、本物の役で線の始めから報告まで回し、封じた差分を当てて対象の試験を確かめるまでの 1 回。
- 対象・試みのフォルダ・家: issue #101 の `python3 tests/e2e/make_target.py make <試みのフォルダ>` が作る物。試みのフォルダはリポジトリの外の空のフォルダで、中に対象 `target/`（通しが直す使い捨ての git の木）・その origin・依頼 `request.json`・家 `home/`（殻が使う Archon の DB と置き場の根。`WORKS_FACTORY_HOME` に渡す）を作る。
- 筋書き（runtime）: ASF の `archon-verify-runtime` が読む JSON（`harness/runtime.scenario.json`）。確かめの役（AI）が手順を道具で実行し、主張（assertion）ごとに `passed`・`failed`・`inconclusive` を証拠のファイルつきで返す。確かめの役はこの issue を読まないので、命令は JSON の中に全部書く。
- 別筋（holdout）: lifecycle の入力 `holdout` に渡す、筋書きと同じ形の別の JSON。作る側（ASF の実装の役）に見せない物。
- 能力の行: 能力の棚卸しの 1 行。ID は区分の頭と番号（`L-E01`・`J12`・`P101`・`F203`・`T5`・`E40`・`R33`・`M12`）。欄は 元（今の works の file:line）・今（works-factory の住処）・証（縛る試験）・本物の run（通しの run の記録のどこで見えるか。健やかな種の run で通らない道は「筋書きでのみ」）・狭め。
- 照らしの表: この issue が作る `tests/e2e/evidence.json`。能力の行ごとに、本物の run の置き場のどのファイルの何を見れば「見えた」と言えるかを機械が読める形で書く。
- 層の決まり: 各階層の `AGENTS.md` の決まり E1〜E18 と、それを照らす `tests/layers/`。この文書では「層の E3」のように書き、能力の棚卸しの区分 E の行（独立の目の行）と分ける。
- 周ごとの値: Archon の輪（`loop_group`）で、前の周の節の出力を `$LOOP_PREV.<節>.output` で次の周が読む値。

## このリポジトリと、この issue の位置

works-factory は今の works の能力を、線・8 つのブロック・助け手（`lib/`。Archon を知らない Python）・入口（`bin/`）に移している。`docs/design.md` の「作りの順」の段 1（歩く骨組み）は、初めは「中身の薄いブロックを並べて通す」予定だった。持ち主の決め `overnight-speed` でブロックの中身を先に作ったので、段 1 は本物のブロックで通す形に変わる（段 3 の 1「線に全部の本物のブロックを並べ、`tests/e2e/` を通す」を前に出した物）。この issue がその段 1 で、1 つの PR にする。

この issue の後に出す issue から、ASF の回し方を `archon-ship` から `archon-lifecycle` に替えられるようにする。lifecycle は PR ごとに筋書きを必ず走らせ、確かめられない間は何も取り込まない（`W/lifecycle/archon-lifecycle.yaml`:151-156・`W/lifecycle/commands/qualify-runtime.md`）。この issue が、その筋書きを本物の通しで確かめた形にする。

## 依存（この issue は次が全部 main に入ってから始める）

- 線の PR #74（issue #60）と 8 つのブロック（PR #66・#69・#67・#75・#73・#68・#76・#94）と PR #100（judge と report の輪の拒否の理由を輪の頭の script の節で渡す形）。
- issue #101: `bin/apply`（封じた差分を当てる口。土台の計画 Task 7）・`tests/e2e/make_target.py`（`make` と `teardown`）・種の実行器 `tests/e2e/target-seed/junit-suite.sh`。この issue はそれらを使うだけで作らない。
- 線の配線の文書 `docs/plans/2026-10-13-line-wiring.md` の部分 0（配線の網と落とし穴の機械）と部分 A（入口・始めの記録・今壊れている物・線の返りの欄）。`bin/apply` は線の返りの欄を読む。
- 照らしの表は、線の配線の部分 A・B1・B2・C・D1・D2（#211）が main に入る前に作る（#258）。だから、それらの「閉じる行」は照らしの表で「部分 X 待ち」（`waits-part`）と名指す（部分が入るまでの区分。部分が全部入った後の check では残りを落ちに数える。その部分の issue が戻し、表の行を移す）。段 1 は、その部分が直すファイル（`workflows/line/scripts/ask_final.py`・`collect.py`・`lib/runreport.py` ほか）を、不具合の直しの外では触らない。
- 依存しない: issue #65（役が利用者の gh を通して GitHub の資格を読める件）。通しの種は GitHub を使わない。
- 入った YAML の節の id がこの文書と食い違えば、YAML を正として読み替え、PR に書く。

## 読む物

- 層の決まり: 根の `AGENTS.md`（E8〜E11・E13・E14・E18）・`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）・`lib/AGENTS.md`（E3）・`bin/AGENTS.md`（E15）・`tests/AGENTS.md`。
- `docs/design.md`: 「線」「ブロックの返りの約束」「Archon の分かっていること」と未決 U1〜U8・「作りの順」。
- `docs/owner-decisions.md`: `overnight-speed`・`one-launcher`・`report-on-stop`・`diff-only-to-target`・`others-may-use`・`real-measure`・`superset`・`no-narrow`・`no-timeouts`・`small-core`・`carry`・`run-cost` と、「2026-10-11 の決めから導いた事」の「段 0〜1 を回す ASF の工程」。
- 能力の棚卸し `docs/plans/2026-10-13-capabilities/`（`line.md`・`judge.md`・`plan.md`・`fix.md`・`tail.md`・`pitfalls.md`）。各行の「本物の run」の欄が、この issue の照らしの元。
- 線の配線の文書 `docs/plans/2026-10-13-line-wiring.md` の「落とし穴の確かめ」（K1〜K20）・部分ごとの「閉じる行」・「この文書の外」。
- issue #101 の本文（`bin/apply` の約束・`make_target.py`）。
- ASF の取り付け命令が置いた物: `harness/END-TO-END.md`・`harness/runtime.scenario.json`・`harness/runtime.inputs.json`・`harness/harness.config.json`・`.factory/holdout/HOLDOUT.md`・`factory/consumer.py`（`invoke`・`harness_inputs`・`read_settings`）。
- 止めた Archon の源の中:
  - `W/lifecycle/archon-lifecycle.yaml`・`W/lifecycle/README.md`・`W/lifecycle/commands/qualify-runtime.md`
  - `W/verify-runtime/archon-verify-runtime.yaml`・`W/verify-runtime/README.md`・`W/verify-runtime/commands/verify-runtime.md`・`W/verify-runtime/scripts/read-scenario.py`
  - 文書 `packages/docs-web/src/content/docs/reference/cli.md` の `workflow run`（`--detach`・既定の作業ツリー・「Base branch precedence」440-462 行）・`workflow get`（`terminal_record`・`--events`）・`workflow wait`（`attention.kind`・`respondTo`）・`workflow approve` と「Detached control verbs」・`workflow resume`・`workflow abandon`・`workflow cancel`
  - `packages/workflows/src/schemas/terminal-record.ts`・`packages/workflows/src/artifact-pointer.ts` の頭
  - `packages/workflows/src/dry-run.ts` 795・1053-1058 行と `fixture-runner.ts` 20-22 行（筋書きは前の周の出力を渡さない。K6）
  - `packages/workflows/src/logger.ts` 129-130・298-310 行・`packages/workflows/src/provider-events.ts` 134 行・`packages/cli/src/commands/workflow.ts` 4076-4091 行（役の道具の呼びの記録と `workflow get --events --json`。U6）
- 今の works: `works/.shared/core/report.py` の `stopped_run`（648-667 行）・`works/dev/dogfood.sh`（種を回した入力の組）・`works/docs/keep-essence.md`（今の works の強みの 12 の仕組み）。

## 目的

1. 本物の役で、本物の 8 ブロックを並べた線を、種の対象に通しで回す。依頼から、報告と、封じた差分を `bin/apply` で当てて種の落ちていた試験が通るまで届かせる。8 つのブロックが全部、通しの中で本物に走ったことを run の記録で示す。
2. 能力の棚卸しの行のうち、本物の run の記録で見える物を全部、照らしの表と照らしの道具で機械に照らさせる。見えない行は訳を名指す（部分 X 待ち・種では通らない道・棚卸しの見立ての誤り）か、不具合として直す。
3. 通しで見つかったブロックと線のつなぎの不具合を、試験を先に赤にしてから直す。
4. 筋書きでは確かめられない Archon の振る舞い（周ごとの値・関所の reject・resume の後の報告）を、使い捨ての本物の run で確かめる。
5. 歩く骨組みで決めると書いた未決（`docs/design.md` の U1・U2 の型つきの成果物の半分・U6・U7、U8 と P2 の実物の確かめ、`docs/polyfills.md` の P1、`lib/AGENTS.md` の層の E3 の `deps:` の引き方）を、実測と文書で閉じて書く。
6. ASF の lifecycle に渡す入力を決め、`archon-verify-runtime` を本物で回して `verified` が返ることを確かめる。これが、次の issue から lifecycle に替える条件になる。

## 置く・変えるファイル

作る:

- `tests/e2e/evidence.py`（照らしの道具）・`tests/e2e/evidence.json`（照らしの表）・`tests/e2e/test_evidence.py`
- `tests/e2e/loop-prev/`（周ごとの値を本物で確かめる使い捨ての工程。手順 6 の K6）・`tests/e2e/test_loop_prev_real.py`
- `tests/e2e/test_scenario.py`（筋書きの形の試験。手順 2）

変える:

- 通しで見つかった不具合の直し: 当たったブロックのフォルダ（`workflows/<名>/`）・線・`lib/` のモジュールと、それぞれの試験。どれを直したかは PR に 1 件ずつ書く（手順 4）。
- `harness/runtime.scenario.json`・`harness/END-TO-END.md`・`harness/runtime.inputs.json`（`description` だけ）・`harness/harness.config.json`（`protected_paths` に `tests/e2e/target-seed/**`・`tests/e2e/make_target.py`・`tests/e2e/evidence.json`）・`.factory/holdout/HOLDOUT.md`
- `docs/design.md`（U1・U2 の残り・U6・U7 を「決めた」に・U8 と P2 に実物の事実・「作りの順」の段 1 と段 3 の 1・「段 1 の結果」の節を足す）・`docs/polyfills.md`（P1・P2・fan_out の子ごとの作業ツリーの候補の行）・`lib/AGENTS.md`（層の E3 の `deps:`）・`tests/AGENTS.md`（`tests/e2e/evidence.py` は筋書きが命令として呼ぶ照らしの道具で、試験が import する助けではない、と 1 行）・`README.md`（線がまだ無いという文を消す）（`docs/design.md` の「段 1 の結果」に、次の issue から lifecycle に替える入力と条件を 1 段落。`docs/owner-decisions.md` は持ち主の決めの台帳なので、この PR は触らない。運び役が merge の後に「2026-10-11 の決めから導いた事」の「段 0〜1 を回す ASF の工程」から、その段落を指す 1 行を足す）・`docs/plans/2026-10-11-foundation.md`（「段 0 の終わりの確かめ」の印）
- 能力の棚卸し `docs/plans/2026-10-13-capabilities/` の行の誤り（「本物の run」の欄の置き場の名・元の行番号）は、同じ PR で直し、PR 本文に「行 ID: 旧 → 新」で並べる。行は消さない。
- 上のうち `harness/**`・`docs/design.md`・`README.md`・`**/AGENTS.md` は共有のファイル（`harness/harness.config.json` の `protected_paths`）で、merge queue が人の手に残す。直してよいのは、この文書が名指した所だけ。

## 種の入力

通しは次の入力で回す（今の works の `dogfood.sh` が種を回した組を、線の入力に写した物。筋書きの JSON にも同じ値を字のまま書く）:

- `request`: 試みのフォルダの `request.json` の絶対パス（`make_target.py make` の出力の `request`）。
- `test_cmd`: `python3 -m unittest -v`（対象の根で走る 1 行）。
- `tdd_suite`: `junit-suite.sh`（対象の根からのパス。issue #101 が置く実行器。実行できるファイルでないと TDD の輪が黙って飛ばされるので、`make` の後に mode が 100755 かを見る）。
- `thickness`: `標準`（全部の単位を標準の深さに固定する。軽量だと差分の審査と R1〜R4 が省かれ、eyes が本物に走ったことを示せない）。
- `final_gate`: 空（既定。最後の関所はいつも開く）。

種には `.review-checks.json`（試験の範囲の宣言）が無い。だから試験の関門の宣言の段（棚卸しの T1 ほか）は、この種の run では通らない。照らしの表ではそれらを「種では通らない道」と名指す（種に宣言を足すかは、この issue では決めない。足すと試験の関門の道が「任せ先の役」から「宣言の段」に替わり、筋書きの確かめ方が変わるため）。

## 殻を続けて打つ時の決まり（実装の役・運び役・筋書きの確かめの役に共通）

- 環境変数は道具の呼び出しをまたいで残らないので、`bin/works-factory` と `bin/apply` の呼び出しには毎回 `WORKS_FACTORY_HOME=<家>` を前に付ける。
- 起こす: `WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow run works-factory-line --cwd <target> --input request=<request> --input test_cmd='python3 -m unittest -v' --input tdd_suite=junit-suite.sh --input thickness=標準` を前で打つ。`--detach` を付けない: 線は `interactive: true` で、止めた Archon は切り離した新しい起こしを拒む（`packages/cli/src/commands/workflow.ts` 2306-2326 行の `assertInteractiveClassNotBackgrounded`。issue #187）。命令は最初の関所 `gate-start`（人の居る run では必ず開く。棚卸しの L-G01）で止まって返る（その前に走るのは `start` の節だけ）ので、道具の呼び出しの上限（600 秒に上げて呼ぶ）に収まる。返りは JSON でないので、run の id は `WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow runs --json --all --cwd <target>` の `runs` のうち `parent_run_id` の無い行の `id` から取る（fix の組の子の run は `parent_run_id` を持つ）。続き（関所の答え）の `--detach` は Archon が拒まない（同じ源の `!isContinuation`）。
- 待つ: `WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow wait <run> --json --timeout 540 --cwd <target>` を繰り返す。`--timeout` は、道具の 1 回の呼び出しの上限（Claude Code の Bash は既定 120 秒・最大 600 秒）より短くして、呼び出しを有限にするための区切りで、run に期限を置く物ではない（run は区切りで止まらない。持ち主の決め `no-timeouts` の外）。道具の呼び出しの上限は 600 秒に上げて呼ぶ。終了の値 3（区切りが来た）なら同じ命令をもう一度打つ。
- `wait` の返りの `attention.kind` で分ける（`reference/cli.md` の `workflow wait`）:
  - `terminal`: 終わり。
  - `awaiting_response`: `get <respondTo.runId>` で関所の文を見て、`WORKS_FACTORY_HOME=<家> ./bin/works-factory workflow respond <respondTo.runId> approve --detach --json --cwd <target>` で答える（`respondTo.runId` は子の run のことがある）。`--detach` を必ず付ける: 付けないと答えた後の run の続き（数時間）が 1 回の道具の呼び出しの中で走り、上限で殺されると持ち主の居ない `running` の run が残って再開できない（`workflow approve` の「In human mode approve/reject auto-resume the run inline」と P1）。
  - `stalled_tool_calls`: `workflow logs <run>` を見て、待ちを続ける（止めない）。
  - `owner_lost`・`action_required`・読めない返り: 止めて、`workflow get <run> --json` を証拠に残す（実装の役は手順 4 の不具合として扱う。確かめの役はその主張を `inconclusive` にする）。
- 片付け: 試みの終わりに `python3 tests/e2e/make_target.py teardown`（issue #101。その checkout の家の終わっていない run を止める。プロセスを名で止めない）。同じ checkout でほかの run（較正のランナーなど）が走る時は、teardown が控えに載った全部の家の run を止めて並んだ run まで止めるので、`make` に `--no-ledger` を付け、試みの終わりに `python3 tests/e2e/make_target.py stop <試みのフォルダ>` でその試みの家の run だけを止める（命令の正本は `harness/runtime.scenario.json`）。

## 能力の行の照らし（この issue の芯の 1 つ）

### 照らしの表 `tests/e2e/evidence.json`

能力の棚卸しの区分 L・J・P・F・T・E・R・M の全部の行を、1 行ずつ次のどれかの種類で載せる（`pitfalls.md` の K1〜K20 と、`line.md` の線への申し送り S01〜S68 は能力の行でないので載せない）。棚卸しに在って表に無い行が 1 つでも在れば `tests/e2e/test_evidence.py` が赤。

- `seen`: 本物の run で見えるはずの行で、下の 3 つの基準を全部満たす行だけ。欄は `id`・`where`（置き場の中の相対パスの glob。親の run の置き場は `parent/`、fix の組の子の run の置き場は `child-*/` で始める。run の記録 `workflow get --json --verbose` の出力は `record/parent.json`・`record/child-<n>.json`）・`check`（次の 5 つの 1 つ: `exists`〔在って空でない〕・`json-has`〔JSON の欄の道 `path` が在って null でも空でもない〕・`json-equals`〔欄の値が `value`〕・`text-contains`〔字 `text` を含む〕・`node-completed`〔run の記録の `nodes[]` に、節の id がちょうど `node` の節が `completed` で在る。`nodes[]` は飛ばされた節・落ちた節も載せるので、節の名だけを照らさない。include の頭は差し込んだ節のどれか 1 つが走れば通るので名指さない〕）・`writer`（その行の能力を決める所〔拒み・止め・既定でない側・値を作る所。保存の所でない〕の `パス::名`〔関数・定数・`クラス.名`。行番号は関係の無い行の足し引きでずれるので書かない〕。YAML と run の記録の行は節の id、最上位のコードで決める script はそれを走らせる節）。棚卸しの「本物の run」の欄の名指しを形にし、書き手のコードで確かめる。
  - 基準（3 つを全部満たす行だけを `seen` にする）: (1) 能力の決める行を消したら照らしが落ちる。(2) 何も働かなかった run の 2 つの形（全部の節が飛んだ run と、`start` は通り必ず走る節〔`start`・`answer-start`・`collect`・報告のブロック・`result`〕だけが走った run。走らなくても空の形を書く出口・支度がいつも書く欄・報告の見出しと 0 件の行・入力のこだまを含む）のどちらにも当たらない。(3) 健やかな種の run で必ず通る道の能力である。棚卸しの行の多くは拒む・止める・既定でない側の能力で、健やかな種の run では働かないので `seen` にしない。
  - 本物の通しの役目は、本物の役で各ブロック（線・judge・plan・plan-review・fix・test-gate・eyes・merge・report）が埋め物でない中身を作ったかを見ること。どのブロックにも `seen` の行を 1 つ以上置く。
- `scenario-only`: 既定。棚卸しの「本物の run」が「筋書きでのみ」で始まる行。`seen` の 3 つの基準を満たさない行は、棚卸しの欄を「筋書きでのみ（本物の通しの照らしの外。在れば <元の名指し>）」に直してここに置く（能力は棚卸しの「証」の欄の試験が縛るので落ちない）。欄 `why` は棚卸しの字（基準で移した行は「本物の通しの照らしの外（#261 の決め直し）: 」で始まる移した訳）。欄の途中に「筋書きでのみ」を含む行（例 L-E01「拒みは筋書きでのみ」）は行ごとに決める。
- `seed-cannot`: 棚卸しは置き場を名指すが、この種では通らない道の行（種に `.review-checks.json` が無い・PR も forge も無い・申し出や 3 回目の拒否が起きない、など）と、種の run でも働かなかった run と同じ跡しか残さない行（上の基準。返りの型・関所の文・節の出力は run の記録に載らない、など）。欄 `why` に、通らない訳を 1 句。照らしを持つなら、働いた時だけ当たる物にする。
- `waits-part`: 線の配線の部分 A・B1・B2・C・D1・D2 の「閉じる行」のうち、本物の run の記録で置き場を決めるまでの行。欄 `part`（`A`・`B1`・`B2`・`C`・`D1`・`D2`）。部分は全部 main に入ったので、棚卸しが「筋書きでのみ」と書く閉じる行は `scenario-only` にする（線の配線の文書の共通の決まり 10）。
- `backlog`: 線の配線の文書の「この文書の外」（「決めた物」「持ち主の答え待ち」「ブロックの中だけの穴」）に名指された行。欄 `why` に、その節の名。
- `handed-off`: 本物の run の中で働かなかったが、この PR では直さずに渡した行（下の「見えなかった行の扱い」の 3）。欄 `why`（働かなかった事実。run の記録の節の id と状態）と `to`（渡した先: 線の配線の部分の名か、区分の issue の番号）。

`seed-cannot`・`backlog`・`waits-part` の行が見えたら `seen` へ移す（下の道具が `unexpected` と言う）。`seen` の行の `where` が棚卸しの名指しと違う時は、run の記録で実際の置き場を見て直し、PR 本文に「行 ID: 旧 → 新」を書く。

### 照らしの道具 `tests/e2e/evidence.py`

- `python3 tests/e2e/evidence.py collect <試みのフォルダ> <run>`: 家と対象から、親の run と fix の組の子の run（`workflow runs` で引く）の置き場（`terminal_record.artifacts.root`）を試みのフォルダの `evidence/parent/`・`evidence/child-<n>/` に写し、`workflow get <run> --json --verbose` の出力を `evidence/record/` に置く（後で消える作業ツリーに依らない）。
- `python3 tests/e2e/evidence.py check <試みのフォルダ>`: 照らしの表を読み、行ごとに `seen`・`absent`（`seen` の行で照らしが通らない）・`unexpected`（`seed-cannot`・`backlog`・`waits-part`・`handed-off` の行なのに見えた）・`unreadable`（照らしの当たったファイルが在るが読めない。黙って `absent` にせず、読めなかった訳を出す。K15）を 1 行ずつ出し、最後に区分ごとの数を出す。`absent` か `unreadable` が 1 つでも在るか、`waits-part` の行が 1 つでも残れば（見えた・見えないに依らない）終了の値 1。
- 標準ライブラリだけで書く（筋書きの確かめの役が対象の外から呼ぶため）。期限を置かない。
- 試験 `tests/e2e/test_evidence.py`（先に赤）:
  - `EvidenceTableCase.test_every_inventory_row_is_in_the_table`（棚卸しの `line.md`・`judge.md`・`plan.md`・`fix.md`・`tail.md` の区分 L・J・P・F・T・E・R・M の行の ID の集合 = 表の ID の集合）
  - `EvidenceTableCase.test_every_row_has_a_known_kind_and_fields`
  - `EvidenceTableCase.test_scenario_only_rows_match_the_inventory`（棚卸しが「筋書きでのみ」で始まる行は `scenario-only`。「筋書きでのみ」を含まない行は `scenario-only` でない。部分は全部 main に入ったので、「筋書きでのみ」を含む行は `waits-part` に残らない。`scenario-only` の行の `why` は棚卸しの字か、基準で移した訳。基準で移した行は棚卸しの欄も「本物の通しの照らしの外」に直っている）
  - `EvidenceTableCase.test_waits_part_rows_are_closing_rows_of_that_part`（`waits-part` の行が線の配線の文書のその部分の「閉じる行」に在る。本物の run の記録で決めた閉じる行は `waits-part` を離れるので、閉じる行の全部が `waits-part` とは縛らない。#318 で直した）
  - `EvidenceTableCase.test_node_rules_name_node_ids_the_workflow_makes`（run の記録の節を照らす行が `node-completed` で、node が線と fix の YAML から組んだ節の id そのもの）
  - `EvidenceTableCase.test_seen_rows_name_a_writer_in_the_repository`（`seen` の行の `writer` が `lib/`・`workflows/`・`bin/` のコードの行で、そのファイルのコードの字（コメント・docstring・`.md` を除く）に where のファイル名かその名を作る定数が在る。決める行は保存の行から離れうるので、行の近くでなくファイルで見る。where の頭のフォルダの名も書き手かそのブロックのコードに在る。名を組んで書く・名の表から引く置き場は名を作る行を名指し、名の照らしだけを外す。run の記録の節の行の writer はその節の id を置く YAML の行）
  - `IdleRunCase.test_no_row_holds_on_a_run_where_nothing_worked`（基準の (2) を縛る。何も働かなかった run の 2 つの形の試みのフォルダ（1 つ目: 線と fix の組の子の全部の節が `skipped`、`start` は入力を受けずこだまと版の控えだけを書く。2 つ目: `start` は種の入力を受けて書く欄を全部書き、必ず走る節が `completed`。どちらも、各ブロックとメイングラフの落ちない返す節と目の `prep` を上流が全部飛んだ形で今の書き手のまま走らせた物を置く）に `check` を当て、`seen` も `unexpected` も 0 件）
  - `EvidenceTableCase.test_every_block_has_a_seen_row`（線と 8 つのブロックのどれにも `seen` の行が在る。ブロックは where の `parent/` の次のフォルダ、`child-*/` は fix、ほかは線）
  - `EvidenceTableCase.test_backlog_and_handed_off_rows_name_their_place`（`backlog` の行が線の配線の文書の「この文書の外」に在り、`handed-off` の行が `why` と `to` を持つ）
  - `EvidenceCheckCase.test_each_check_kind_passes_and_fails`（一時のフォルダに作った置き場で 5 つの照らしの通る形と通らない形）
  - `EvidenceCheckCase.test_absent_row_exits_one_and_unreadable_file_is_named`
  - `EvidenceCheckCase.test_unexpected_seen_is_reported`
  - `EvidenceCheckCase.test_waits_part_row_left_exits_one`（`waits-part` の行が残る表は見えた・見えないに依らず終了の値 1。残らず `absent`・`unreadable` も無い表は 0）
  - `EvidenceCheckCase.test_cli_exits_one_on_an_absent_row`（命令の終了の値。筋書きが読むのはこれだけ）

### 見えなかった行の扱い（手順 4 の中で）

`check` が `absent` か `unreadable` と言った行は、1 行ずつ次のどれかに決めて PR 本文に書く（数の表のセルは短い値だけ。訳は表の下に行 ID ごとの箇条書き）。

1. 棚卸しの見立ての誤り（その能力は走ったが、置き場の名が違った）: run の記録で実際の置き場を示し、表の `where` を直す。
2. 種では通らない道だった: run の記録で、その道の入口が通らなかった事実（例: 節が `skipped`）を示し、`seed-cannot` に移す。
3. 不具合（その能力の道を通ったのに、能力が働かなかった）: 手順 4 の不具合の直し方で直す。ただし、その行が線の配線の部分 A〜D2 の「閉じる行」か「この文書の外」の行なら直さずに `handed-off` で渡す（この PR の範囲を広げない）。渡すのは run を止める不具合でない時だけ。run が先へ進めない不具合は、どの行でもこの PR で直す。
4. 能力を削る直しが要る・約束（`docs/design.md` の「ブロックの返りの約束」）の欄を変える・持ち主の決めとぶつかる: 直さずに止めて PR に書き、持ち主の答えを待つ（`superset`・`no-narrow`）。

## 落とし穴の確かめ（K1〜K20）

詳しい根拠と縛る試験は `docs/plans/2026-10-13-line-wiring.md` の「落とし穴の確かめ」と棚卸しの `pitfalls.md`。この PR が直すたびに、その差分が K1〜K20 の試験を通ることを PR 本文に 1 行ずつ書く（当たる所が無ければ「当たる所が無い」）。要点だけ写す:

- K1 返す節と返す節が結ぶ節は落ちない（lib の import は守った `main` の中・最後は標準ライブラリだけで返す。Archon は落ちた節の出力を結んだ節を `all_done` でも落とす。`dag-executor.ts` 495-533 行）
- K2 `runtime: uv` の script は頭に PEP 723 の 4 行（`scripts/` の 1 段下も）
- K3 読むだけの節は `mutates_checkout: false`。Archon は `loop:` の節ではこの鍵を無視する（`schemas/dag-node.ts` 1025-1031 行）ので、読むだけの役を `loop:` で書かない
- K4 skill・agent を借りる役の節は `skills:`・`plugins:` で名指す（同梱の skill は `tests/archon.py` の `BUILTIN_SKILLS`）
- K5 `loop_group` の中の役の節は自分の `with:` を結ばない（輪の頭の script の節。PR #100）
- K6 周ごとの値は本物の run でしか確かめられない
- K7 E3・E4・E13 の層の決まり・K8 script どうしの import と循環 import を作らない
- K9 写した指示書と役の定義は元の字のまま、許した直しを試験で縛る（持ち主の決め `prompts-coldread`（2026-10-12、`docs/owner-decisions.md`）で、初見の読み手での書き直しも許した直しとして足す。4 つの約束は `tests/workflows/test_prompt_contracts.py` が別に照らす）
- K10 どの関所の `reject` も報告へ流す（Archon は `decisions` に `reject` が無いと run を取り消す。`workflow-operations.ts` 1625-1700 行）
- K11 ブロックに足す入力は既定値つき・K12 新しい入力と隣のファイルは読み手と配線の試験を持つ
- K13 返りの指し札の先は在って空でない・K14 2 度差し込むブロックの 2 度目が 1 度目の物を拾わない・K15 読めない入力を名指す・K16 返りの JSON は `allow_nan=False`
- K17 戻した能力には「外すと赤」の試験・K18 役の節の決まりを全ブロックで・K19 script の名を lib の名と同じにしない・K20 同じ定数を 2 か所に持たない

筋書きでは確かめられず、この issue が本物で確かめる物:

- K6 周ごとの値: 手順 6 の使い捨ての工程で、輪の頭の script の節が 1 周目は空、2 周目は前の周の受け付けの `reason` を返し、役の文にそれが載ることを本物で見る。通しの run でも、拒みが起きた輪が在れば、その輪の `<役>-reject` の節の出力を照らしの表に載せる（起きなければ「拒みが起きなかった」と PR に書く）。
- K10 関所の `reject`: 使い捨ての run の最初の関所（`gate-start`）に `reject` で答え、run が取り消されず（`terminal_record.status` が `completed`）、報告が走り、結末の語が `stopped_by_human` になることを見る。
- 報告がいつも走る（棚卸しの L-W60）の resume の半分: 手順 6 の P1 の確かめで、`--adopt` で続けた run の報告の節が走ることを見る。
- K1・K13: 通しの run の記録で、全部の include の返す節が `completed` で、返りの指し札の先が在って空でないことを、筋書きの every-block-ran（include ごとの節の `completed`）と、照らしの表の各ブロックの `seen` の行（埋め物でない中身）で見る。

## 手順（試験が先に赤）

1. `tests/e2e/test_evidence.py` を書いて赤を見る（`tests/e2e/evidence.py` と表が無い）。表は、棚卸しの「本物の run」の欄から作る（行の欄の字を読んで `where` と `check` に移す。迷う行は `scenario-only` に置く）。
2. `tests/e2e/test_scenario.py` を書いて赤を見る: 止めた Archon の源の `W/verify-runtime/scripts/read-scenario.py` に `INPUTS_SCENARIO=harness/runtime.scenario.json` で渡して 0 で終わる（源が無ければ `tests/archon.py` の名前つきの見送り。CI では見送らない）。`harness/END-TO-END.md` の節の見出しに、筋書きの主張の `id` が全部、同じ順で在る。
3. `tests/e2e/evidence.py`・表・筋書きの JSON（下の「筋書きの入力」）を書いて 1・2 を緑にする。全部の試験 `WORKS_FACTORY_ARCHON_REQUIRED=1 uv run --isolated python3 -m unittest discover -s . -t .` が緑。
4. 通しを本物で回す（この PR の芯。費用は問わない）。「殻を続けて打つ時の決まり」に従う:
   1. `python3 tests/e2e/make_target.py make <試みのフォルダ>` で対象・依頼・家を作る。`target/junit-suite.sh` が実行できることを見る。
   2. run を起こし、`wait` と `respond … approve --detach` で終わりまで運ぶ。
   3. 当てる前に、対象で `python3 -m unittest -v` を走らせて控える（2 件落ちる）。`returns.value.apply.diff` の先のファイルを試みのフォルダに写して控え、1 バイト変えて `./bin/apply <run> --cwd <target>` が 1 で止まり対象が変わらないことを見て、控えから戻す。
   4. `./bin/apply <run> --cwd <target>` で当て、`python3 -m unittest -v` で 3 件が全部通ることを見る。
   5. `python3 tests/e2e/evidence.py collect <試みのフォルダ> <run>` と `check <試みのフォルダ>` を走らせ、出力を PR に貼る（数の行と、`absent`・`unexpected`・`waits-part` の全行）。受け入れ 2 の材料を作る。
   6. 上の「片付け」のとおり、`python3 tests/e2e/make_target.py teardown`（`--no-ledger` で作った試みは `stop <試みのフォルダ>`）。
   - 通しが途中で落ちる・おかしな結末を出す・`check` が `absent` を出すたびに、上の「見えなかった行の扱い」で決める。不具合なら superpowers:systematic-debugging の形で原因を確かめ、落ちたブロック（か線か `lib/`）の試験か筋書きに **その不具合で赤になる 1 本を先に足して赤を見てから** 直す（superpowers:test-driven-development）。直しは K1〜K20 を通す。直したら、通しを新しい試みのフォルダで最初から回し直す（直した `workflows/` は新しい run でしか読まれない。`workflows/` は run の始めに写し取られる）。
   - 殻（`bin/_lib/launcher.py`）と `bin/apply` の不具合は、直さずに別の issue にして PR に書く。
   - 入れ子の認証: この手順は、実装の役の会話の Bash から殻を起こす。殻は普通の利用者の道（ホストのログイン・`ANTHROPIC_API_KEY`・選べる道の `WORKS_FACTORY_KEYCHAIN_ITEM`）で認証を拾う。拾えずに殻が止まった時は、どの道で何が無かったかを殻の 1 行のまま PR に書き、この手順の 4 を運び役に渡す（下の「PR の後に運び役が行う確かめ」の 1）。手順 1〜3・5〜7 はそのまま進める。
5. 筋書きの JSON と END-TO-END を、手順 4 で実際に通った命令と置き場に合わせて直す（命令は JSON に 1 か所。写さない）。
6. 使い捨ての run で確かめる（通しの本番の run は壊さず、止める・殺す確かめは別の使い捨ての run で行う。仕組みは足さない。足りない時は `docs/polyfills.md` に「（予定）」の行を足すだけにする）:
   - K6: `tests/e2e/loop-prev/` に、輪の頭の script の節（`$LOOP_PREV.<受け付け>.output.reason` を結んで返す）・役の節（模型は一番安い物。受け取った理由を返すだけ）・受け付けの script の節（1 周目は理由つきで拒み、2 周目は通す）だけの工程を置き、`tests/e2e/test_loop_prev_real.py::LoopPrevRealCase.test_reason_changes_by_round` で本物に回す（`WORKS_FACTORY_REAL_RUN=1` の時だけ走り、無ければ名前つきで見送る。CI では見送る）。殻 `bin/works-factory` は `--workflow-source` を拒み、リポジトリの `workflows/` だけを渡す（`bin/_lib/launcher.py` 46-47 行）ので、この工程は殻を通さない: `tests/archon.py` の使い捨ての git の木の作り方で `.archon/workflows/` に工程を置き、止めた Archon を `bun` で直に起こす（認証は殻と同じ普通の利用者の道。PR #100 が小さな工程を本物の役で回した時と同じ形。PR #100 の本文を読む）。1 周目の輪の頭の出力が空、2 周目が 1 周目の受け付けの理由で、役の返答にそれが載ることを assert する。この PR で 1 度本物で回し、出力を PR に貼る。工程は K1〜K5・K18 を満たす形で書く（ブロックと同じ決まり）。
   - K10: 使い捨ての run を起こし、最初の関所で `workflow respond <run> reject --detach --json` と答え、`terminal_record.status` が `completed`・`returns.value.outcome` が `stopped_by_human`・報告の本文が空でないことを見る。
   - U1（`resume` の後の run の id は同じか）: 文書で決める（`workflow resume` は id を指して同じ run を続ける。`--adopt` は新しい run を起こす。`reference/cli.md` の `workflow resume`・`--adopt`）。加えて、使い捨ての run を 1 つ起こし、最初の関所で `workflow approve <run> --json`（答えを記録するだけで続きを走らせない形）の後に `workflow resume <run> --detach --json` を打ち、続いた run の id が同じかを見る。
   - P1（持ち主の居ない `running` の run）: 別の使い捨ての run で、役の節が走っている間に、`--detach` の子のプロセスを pid で止める。pid は `workflow abandon --json` の `recordedPid` の案内か、`ps` を家のパスで絞って見つける（名で止めない・`pkill -f` の広い形を使わない）。`workflow get`・`workflow wait` が何を言うか（`owner_lost`）、`workflow resume` が拒むか、`workflow abandon` が run の作った作業ツリー（書きかけを含む）を消すこと（`reference/cli.md` の `workflow abandon`）と、`workflow run --adopt <run>` で新しい run として続きを起こせるか、その時に報告の節が走るか（L-W60）を書く。結果で P1 の「埋め」の行を「足りる（埋め無し）」か「足りない（置き場の予定）」に直す。
   - U2 の残り（型つきの成果物が include ごとに分かれて見えるか）: 通しの run の `$ARTIFACTS_DIR/.archon/` の型つきの成果物の一覧で、`test-gate-base` と `test-gate-final` の `green-cert` が別の鍵で載るかを書く。
   - U6: 止めた Archon の `workflow get --events --json` と run の transcript（`workflow get <run> --json` の `transcript_path` の JSONL）に、役の道具の呼び出し（読んだ・書いたファイルのパス・web の取得）が載るか。載る形を 1 例引き、今の works の包みが取っていた読んだ証拠と書き込みの記録（棚卸しの J40・P057・P211〜P213・F102・F147）がそこから取れるかを書く。取れると分かっても、この PR では戻さない（後の issue）と書く。
   - U7: 下の「筋書きの入力」と、運び役の確かめの run の id で閉じる。
   - U8: fix の組ごとの子の run が自分の作業ツリーを持ち、差分が親に戻ったかを、run の記録（子の run の id と作業ツリーのパス・戻した組）で書く。fix の PR #94 が書いた事（remote の無い対象では子の作業ツリーが切れず、1 つずつ回す）と食い違えば、両方を書く。
   - P2: 通しの run で、線の返しの節が飛ばされた値を `null` で受けたことを 1 例引く。
   - 層の E3 の `deps:`: script の節が外のパッケージ（PyYAML など）を本物の run でどう得たか（`runtime: uv` の `deps:` か、ほかの道か）を書き、`lib/AGENTS.md` の層の E3 の「段 1 で決める」をその事実で閉じる。ブロックごとに違う道を取っていたら、`pyproject.toml` の 1 か所の宣言を引く形にそろえる直しをこの PR で入れる（持ち主の決め `outside-packages-ok` の「依存の宣言は 1 か所」）。ただし止めた Archon の `runtime: uv` は対象の作業ツリーを cwd に走る（`guides/script-nodes.md` 73-74・232 行）ので、自分の `pyproject.toml` を持つ対象では uv がその環境を使う。種はそれを持たないので、この確かめは「自分の `pyproject.toml` を持つ対象では未確かめ」と書いて残す。殻で環境を変える直しが要るなら、別の issue にする。
   - 段ごとの費用と時間: report が載せた段ごとの費用と時間を表にして PR に書く（持ち主の決め `run-cost`）。
7. 文書を直す（上の「置く・変えるファイル」の変える物と、下の「筋書きの入力」「段 1 の結果」）。全部の試験が緑。

## 筋書きの入力（ASF の lifecycle に渡す物）

lifecycle の入力のうち、このリポジトリが決める物:

- `scenario`: main の checkout の `harness/runtime.scenario.json` の絶対パス（この issue で決める）
- `holdout`: 空（この issue で決める）
- `required_checks`・`protected_paths`: consumer が `harness/harness.config.json` から足す（在る）
- `merge_method`: `squash`（今の main の取り込み方）
- `merge_mode`・`discovery_publication`: 既定（`approve`・`preview`。lifecycle の既定）

訳:

- `scenario` を候補（PR）の checkout でなく main の checkout から渡す訳: 筋書きは確かめる側の物で、PR が自分の筋書きを緩めて通れないようにする（`W/verify-runtime/README.md`「Scenario secrecy from a separate builder is the caller's responsibility」）。`harness/**` は守りのパスで、筋書きを変える PR は merge queue が人の手に残す。
- 種・`make_target.py`・照らしの表を守りのパスに足す訳: 種は筋書きが当てる欠陥の組、照らしの表は「見えた」と言える条件で、作る側が自分で変えられると筋書きを通せる（ASF が置いた `harness/mutations/defects.json` の頭の「A builder that can edit its own defect set can pass it」と同じ向き）。`tests/e2e/` のほかの試験は含めない。
- `holdout` を空にする訳: lifecycle は別筋が空ならその確かめを飛ばし、筋書きだけで判定する（`W/lifecycle/README.md`・`qualify-runtime.md`）。別筋の 3 つの筋はどれも本物の通しを 1 回ずつ要り、PR ごとに回すと 1 つの PR の確かめに通しが 4 回走る。別筋は作る側に見せない物だが、`.factory/holdout/HOLDOUT.md` が公開のリポジトリに在り、今は隠せていない。だから別筋はこの issue で 1 度だけ本物で回して確かめ（下の「運び役」の 2・4）、PR ごとには回さない。
- 費用の事実: 筋書きは PR ごとに本物の通しを 1 回（報告の形が崩れた時はもう 1 回、lifecycle の 1 度の直しの後にもう 1 回）走らせる。1 回の時間と費用は手順 6 の表で測り、`docs/design.md` の「段 1 の結果」に書く。lifecycle に替えるのは持ち主の前の決め（`docs/owner-decisions.md` の「開発の進め方」の「段 2 からは ASF の lifecycle」）で、筋書きを走らせるのは lifecycle の決まりそのものなので、この費用はその決めに含まれる。

### harness/runtime.scenario.json（書き直す）

止めた Archon の `read-scenario.py` が受ける形（`assertions` の `id`・`description`、`environment` の `ownership: external`・`setup`・`start`・`teardown`・`candidate_command`）。確かめの役はこの issue を読まないので、命令は全部 JSON の中に字のまま書く（上の「殻を続けて打つ時の決まり」と「種の入力」の中身を、確かめの役に向けて書き直して入れる。issue の手順の番号で指さない）。

- `environment`: `setup`・`start` は空（対象は主張の手順の中で試みごとに作る）。`teardown` は `python3 tests/e2e/make_target.py teardown`（確かめの節が落ちても切り離した run が走り続けないよう、その checkout が作った家の run を止める。`ownership: external` の約束「Consumers must provide a lifetime owner」）。`candidate_command` は今のまま。
- 主張は次の 5 つ。どれも、確かめの役が道具の出力を証拠のファイルに残す前提で書く（`W/verify-runtime/commands/verify-runtime.md`）。試みのフォルダは、この試みの置き場（attempt directory）の下に新しく作る。
  1. `request-to-report`: `make_target.py make` で対象・依頼・家を作り、run を起こし、関所で止まるたびに関所の文を見て `approve` で答え、終わりまで運ぶ。期待: 起こした後の `workflow runs --json` に `parent_run_id` の無い run がちょうど 1 つ在る・`workflow get <run> --json` の `terminal_record.status` が `completed`・`returns.value.outcome` が report の結末の 10 語の 1 つ・`returns.value.report` の先の報告の本文が空でない・当てる前の対象の `git status --porcelain` が空。認証が拾えずに殻が止まった時は `inconclusive` にし、殻の 1 行を reason に書く（製品の不具合ではない）。
  2. `every-block-ran`: 1 の run の `workflow get <run> --json --verbose` の `nodes` を読む。線の include の id は `test-gate-base`・`judge`・`plan`・`plan-review-run`・`fix`・`test-gate-final`・`eyes`・`merge-seal`・`merge-apply`・`report`。include の中の節の id は `<include の id>__<節の id>`（止めた Archon の `include-expander.ts` の `inlineInclude`）、輪の中の節には `<輪の id>.` の頭が付く（`dag-executor.ts` 4322-4331 行）。`plan` と `plan-review-run` は計画の往復の輪 `plan-rounds` の中に在るので、その節の id は `plan-rounds.plan__`・`plan-rounds.plan-review-run__` で始まる。案の直しの道の include（`rejudge-run`・`replan`・`replan-review`・`refix-run`）は、通った run だけ見る。直す物の無い周の include（`design-only`）も、通った run だけ見る。fix の組は子の run として起きるので、`workflow runs` で親の子の run を引き、子ごとの `get --json --verbose` を読む（子の run の節の id には頭が付かない）。期待: include の id ごとに、親の run の `nodes` に `<include の id>__` を含む節が 1 つ以上 `completed`（fix も親の run で見る）。子の run が 1 つ以上在り、子のどれかで修正の役の節（`tdd-loop.tdd`・`tdd-loop.tdd-new`・`fix-loop.fixer`）のどれかが `completed`。eyes の R1〜R4 の役の節（`eyes__r1-comments`・`eyes__r1-minimality`・`eyes__r2-compare`・`eyes__r3-coherence`・`eyes__r4-scope`）が `completed`（深さを標準で回したので省かれない）。include の id・修正の役・eyes の役の名が線とブロックの YAML と合うことは `tests/e2e/test_scenario.py` が見る。
  3. `capabilities-evidenced`: 1 の run で `python3 tests/e2e/evidence.py collect <試みのフォルダ> <run>` と `check <試みのフォルダ>` を走らせる。期待: `check` が終了の値 0（`absent` も `unreadable` も 0 件で、`waits-part` の行が残らない）。`waits-part` の行は 1 つでも残れば（見えた行も）失敗。`seed-cannot`・`backlog`・`handed-off` の行が見えた `unexpected` は失敗にしないが、行を全部 reason に写す。
  4. `changed-diff-refused`: 1 の run で、当てる前に、`returns.value.apply.diff` の先（`terminal_record.artifacts.root` の下）を試みのフォルダに写して控え、1 バイト変えてから `./bin/apply <run> --cwd <対象>` を呼ぶ。期待: 0 以外で終わり、hash が合わないことを言い、対象の `git status --porcelain` が空のまま。その後で控えから元に戻す。
  5. `sealed-diff-fixes-seed`: 4 の後、対象で `python3 -m unittest -v` を走らせて控え、`./bin/apply <run> --cwd <対象>` で当て、もう一度走らせる。期待: 当てる前は依頼が名指した 2 件（`test_mean_of_three`・`test_clamp_above_range`）が落ち、当てた後は 3 件全部が通る。対象の `git diff --stat` は空でなく、変わったファイルは報告が挙げたファイルの中だけ。
- 消す: 今の筋書きの「`workflows/*/scripts/stub.py` が在る間は inconclusive」の前提と、「線が無い間は inconclusive」の前提。
- この筋書きは SDLC の工程（`archon-*`）を起こさない（`W/verify-runtime/README.md`「must not recursively invoke the SDLC pack」）。起こすのは自分の線 `works-factory-line` だけ。

### harness/END-TO-END.md（書き直す）

頭に「機械が読む正本は `harness/runtime.scenario.json`。この文書は人が読む要約」と書き、5 つの主張を `id` を見出しにした節にして、各々の目的・期待・落ちたと言える物だけを書く（命令は JSON に 1 か所。写さない）。「今の状態: まだ回せない」の節を消す。節の見出しと主張の `id` が合うことは `tests/e2e/test_scenario.py` が見る。

### harness/runtime.inputs.json（description だけ直す）

「線 works-factory-line と…が在るまで、cli.invoke は空のまま」の文を消し、「止めた Archon の工程はこのファイルを読まない（lifecycle に渡すのは `scenario` と `holdout` の絶対パスだけ）」と書く。ASF の runtime host を使わない訳（子に Claude の資格を渡さない・300 秒で打ち切る・層の E12）は残す。ほかの欄は変えない。

### 別筋（holdout）

- 置き場: リポジトリの外（運び役の機械の `${XDG_STATE_HOME:-$HOME/.local/state}/works-factory/holdout/runtime.holdout.json`）。リポジトリにも、この issue と PR の本文にも中身を書かない（作る側に見せない確かめ。`W/verify-runtime/README.md`「Scenario secrecy … is the caller's responsibility」）。
- 形は筋書きと同じ。中身は `.factory/holdout/HOLDOUT.md` の 3 つの筋（同じ対象に 2 つの依頼を続けて回す・関所で待っている間に Archon を起こし直す・最後の関所で拒むと何も当たらない）を主張にした物。
- この PR で `.factory/holdout/HOLDOUT.md` を直す: 「今は回せない」と「lifecycle に空で渡す」の節を、上の `holdout` を空にする訳に直す。2 つの依頼の筋に「A を当てた後、対象で commit して origin に push してから B を回す」を足す（run の作業ツリーは origin の枝から切られるので、当てただけの A の上には B が乗らない）。`./bin/apply` に `--cwd <対象>` を書き、関所の答えは `respond … --detach` で打つと書く。拒む筋の期待に「`./bin/apply` は置いた差分が無いと言って 1 で終わる」と結末の語 `stopped_by_human` を書き、`--allow-stopped` を付ければ封じた差分が当たることを足す。

## 受け入れ

1. 手順 1・2 の試験が先に赤で入り、後で緑。赤と緑の出力の要約を PR に書く。全部の試験 `WORKS_FACTORY_ARCHON_REQUIRED=1 uv run --isolated python3 -m unittest discover -s . -t .` が緑（CI の `tests` も緑。CI は本物の通しを回さない）。
2. 本物の通しが 1 度、最初から最後まで通った。PR に次を書く:
   - run の id（親と fix の子）・works-factory の commit・止めた Archon の commit・Claude Code の版（始めの記録の版の控え）
   - 結末の語と報告の本文の頭
   - include の id ごとに `completed` の節の数と、役の節の provider と模型の表（セルは短い値だけ）
   - 1 バイト変えた差分を `bin/apply` が拒んだ出力と、当てた後の `python3 -m unittest -v` の出力
   - `evidence.py check` の出力（数の行と、`absent`・`unexpected`・`waits-part` の全行）。数は区分ごと（L・J・P・F・T・E・R・M）に `seen`・`scenario-only`・`seed-cannot`・`waits-part`・`backlog` の件数
   - 最初の `check` で `absent` だった行ごとの決め（見立ての誤り・種では通らない・不具合・持ち主待ち）と訳（表の下に箇条書き）
   - 通しで見つけて直した不具合の一覧（1 件ごとに: 落ちた節・原因・先に赤にした試験の名・直したファイル・当たった能力の行 ID・K1〜K20 への答え）
   - 段ごとの費用と時間の表
3. 最後の通しで `evidence.py check` が終了の値 0（`absent` も `unreadable` も 0 件で、`waits-part` の行が残らない）。`seed-cannot` と `handed-off` の行はどれも、run の記録の事実（節の id と状態）を訳に持つ。
4. 手順 6 の K6・K10・L-W60 の確かめの出力が PR に在る。K6 の `test_loop_prev_real` を本物で 1 度回した出力（1 周目が空、2 周目が前の理由）が在る。
5. `docs/design.md` の U1・U2 の残り・U6・U7 が「決めた」になり、U8・P2・P1・層の E3 の `deps:` に実物の事実と run の id が書いてある。決めは事実から 1 つに決まる物だけで、決まらない物は「持ち主の答え待ち」と書いて PR の冒頭に並べる。
6. 層の試験（各階層の `AGENTS.md` の機械の行）が全部緑。`bin/` に持ち主の環境の字が無い（層の E14）。
7. 範囲の外のファイルに差分が無い。直した能力の行が、線の配線の部分 A〜D2 の「閉じる行」か「この文書の外」に入っていない（入っていれば、run を止める不具合だった事を PR に書く）。

### PR の後に運び役が行う確かめ（この PR を merge する前の受け入れ）

ASF の工程の中から ASF の工程を起こさない（入れ子の SDLC）ので、次は ASF の実装の役でなく運び役が回す。

- 置き方: 運び役の main の clone から `git worktree add <木> <PR の head>` で PR の head の作業ツリーを作り、その中で回す（consumer は clone の共有の git の置き場から `.factory/consumer.json` を読む。`factory/consumer.py` 58-72 行）。consumer は `--cwd` に作業ツリーの根を渡し、Archon は既定で remote の HEAD（main）から run の作業ツリーを切るので、`--no-worktree` を付けて PR の head の木のまま回す。

1. 手順 4 を実装の役が認証の都合で回せなかった時は、運び役が同じ手順で回し、受け入れ 2〜4 の材料を PR に書き足す。
2. 別筋の JSON をリポジトリの外に書き、`read-scenario.py` の照らしを通す。
3. 筋書きの確かめ: PR の head の木で `python3 factory/consumer.py run archon-verify-runtime --no-worktree --input scenario=<PR の head の木>/harness/runtime.scenario.json --input candidate=<PR の head の sha>`（以後の lifecycle は main の checkout の筋書きを渡すが、新しい筋書きはこの PR が入れるので、この 1 回だけは PR の head の物を渡し、そう PR に書く）。返りが `verified: true`。
4. 別筋の確かめ: 同じ命令で `scenario=<別筋の JSON>`。返りが `verified: true`。
5. 3・4 の run の id・`verdict`・報告のパスを PR に書く。この PR は `docs/design.md` の「段 1 の結果」に、それを書く欄を「（運び役が書く）」で置き、運び役が PR の枝に 1 commit で書き足す。3 か 4 が `failed` なら、見つかった不具合を手順 4 の形で直してから回し直す。`inconclusive` なら reason を読み、筋書きの書き方か環境の問題として直す（筋書きを緩めて通さない）。

## 範囲（触らない物）

- 線とブロックの返りの約束の欄（`docs/design.md` の「ブロックの返りの約束」）は変えない。変える要が出たら止めて PR に書く。
- `bin/` の全部（`bin/apply` と殻。issue #101 と層の E15）と `tests/e2e/make_target.py`・種（issue #101）。不具合は別の issue にする。
- 線の配線の文書の部分 A〜D2 の「閉じる行」と「この文書の外」の行を直すこと（run を止める不具合の外は `handed-off` で渡す）。
- ASF の取り付け命令が置いた物のうち `factory/`・`FACTORY.md`・`FACTORY_RULES.md`、`harness/` の中の書くと決めた 4 つ以外（`harness/mutations/` は段 3 の較正 `tests/calibration/` で扱う）。
- 周の鎖（段 3 の鎖の issue）と、関所の間で走っている run を報告つきで止める札（持ち主の決め `stop-at-gates` で持ち込まない。関所の答えの文が `request:` で始まる止め `stopped_by_request` は今の形のまま）。
- 段 3 の物: 受け入れの一覧の全部の行の証・graph の節の表・較正・今の works との比べ。この issue の照らしの表は「本物の run で見えるか」だけで、能力の正しさの全部の証ではない。
- PR を作る・merge する道（層の E17 の選べる道）。

## 層の E11 の 3 つ

1. Archon が持つ物: run の記録と返す節の値（`workflow get --json` の `terminal_record`）・出来事の記録（`--events`）・待ち（`workflow wait`）・関所の答え（`workflow respond`）・切り離した関所の答え（`--detach`）・run ごとの作業ツリー・止めと片付け（`cancel`・`abandon`）。全部そのまま使う。
2. ASF が持つ物: `archon-verify-runtime`（筋書きの読みと、証拠つきの主張の判定）と `archon-lifecycle`（候補の版の照らし・1 度の直し・別筋）。筋書きの形と照らしは ASF の物をそのまま使い、コードは写さない（層の E8）。
3. 本当に要るか: 照らしの道具 `tests/e2e/evidence.py` は、ブロックの PR が審査を通った後に能力が黙って落ちていた事実（持ち主の側の目が毎回見つけた）から要る。Archon にも ASF にも「今の works の能力が run で働いたか」を照らす口は無い。口は `collect` と `check` の 2 つだけで、表は棚卸しの行をそのまま写す。

## 持ち主に聞くこと

無し。決めた所はどれも、持ち主の前の決め（`superset`・`no-narrow`・`diff-only-to-target`・`one-launcher`・`others-may-use`・`small-core`・`no-timeouts`・「段 2 からは ASF の lifecycle」）か、ASF と Archon の文書（上の引用）で 1 つに決まる。線の配線の文書の「この文書の外」の「決めた物」（会話を継がない・関所の間の止めを持ち込まない・固定材料は独立の issue・周の鎖は段 3 ほか）と「持ち主の答え待ち」（機械全体の試験の枠・コードとコメントの比・入力 `gates`）は、どれもこの issue の外で、通しはそれらに依らず回せる。
