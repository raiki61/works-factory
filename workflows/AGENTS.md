<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」の節で定義 -->
# グラフ（`workflows/`）の決まり

線とブロックの YAML・役の指示書・節の script・境（`.shared/`）を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E1 YAML は変換せずに Archon に渡す

- `workflows/` の YAML は手で書き、`bin/` は写さずに Archon に読ませる（`--workflow-source` に渡す置き場の `.archon/workflows/works-factory` がこのフォルダを指す pack の形。名前の script と `.shared/` は pack の形の時だけ効く。`bin/_lib/place.py`）。Archon は run の始めにその中身をバイトのまま写し取る。生成・前処理・鍵の削りをしない。
- 作りの規則は Archon の `workflow-language-constitution.md`（Archon の源の `.archon/workflow-language-constitution.md`。要点「YAML coordinates. Code computes. Agents judge.」）。YAML は節の順・関所・繰り返し・入出力の配線だけを持つ。値の計算は `script:` の節か役の指示書に置く。
- Archon の確かめ（`archon validate workflows`）が警告なしで通る。数えない警告は 1 つの形だけ: Claude Code に同梱の skill（`tests/archon.py` の `BUILTIN_SKILLS`。`code-review`・`simplify`・`security-review`）と、借りる superpowers の skill（`tests/archon.py` の `BORROWED_SKILLS`。`bin/_lib/borrow/borrow.json` の `superpowers.skills`）を節の `skills:` に名指した時の「Claude skill '<名>' not found on disk — expected for built-in…」の警告（level が warning・field が `skills`・文がこの形・名が 2 つの一覧のどちらかに在る、の全部が当たる物。照らしは `tests/archon.py` の `counted` の 1 か所）。同梱の skill はディスクに `SKILL.md` が無く、借りる skill は起動の時に run の隔離した設定へ入るので確かめの使い捨ての木には無い。止めた Archon の `packages/workflows/src/validator.ts` 698-768 行は名指すたびにこの警告を出す。一方で止めた Archon は節の `skills:` に名指した skill しか役に渡さない（`packages/providers/src/claude/provider.ts` 631 行）ので、名指さないと judge の局所レビューの役がレンズを起こせない。2 つの一覧に無い名の警告と、同梱の名でも別の置き場に入っていて届かない時の誤り（installed elsewhere）は今までどおり数える。`validate` は `--workflow-source` を受けず黙って捨て、`--cwd` は git の木しか受けないので、`.archon/workflows/works-factory/` に工程のフォルダと `.shared/` を写した使い捨ての git の木（`tests/archon.py`）を `--cwd` に渡す。
- 機械: `tests/layers/test_no_conversion.py`（Archon が読む所と `workflows/` のバイト一致）・`tests/layers/test_archon_validate.py`（確かめの結果に誤りも警告も無い。上の同梱の skill と借りる skill の警告だけは `tests/archon.py` の `counted` で数えない。種 `tests/layers/seeds/e1/workflows/skills/` で、一覧に無い名の警告と installed elsewhere の誤りが数えられることを縛る）。

## E2 境の中身は全部、名簿に載せる

- `workflows/.shared/` のファイルは 2 種類だけ。Archon との出入りの口（境の入出力のモジュール。1 つ）と、埋め（polyfill。Archon に無い物を外から補う部品）。
- 埋めは `docs/polyfills.md` に 1 行ずつ載せる。載せる欄は、穴・Archon の証拠の引用・外す条件。
- 機械: `tests/layers/test_polyfills_listed.py`（`workflows/.shared/` のファイルが、境の口か名簿の行のどれかにちょうど当たる。名簿に在って木に無い行も赤。ただし置き場のパスの直後に「（予定）」と書いた行は、木に無くてよい）。

## E4 ブロックはほかのブロックのファイルを指さない

- ブロック（`workflows/<名>/`）の script は、ほかのブロックのフォルダへのパスを組まない。受け取りは `with:` の入力・前の節の返り・指し札（`archon_artifact`）・型つきの成果物（`output_type`）だけ。
- ブロックの script は `lib/` と境の口を呼ぶだけで、確かめの中身を持たない。
- 機械: `tests/layers/test_block_paths.py`（ブロックの `scripts/` とブロックの YAML（直に書いた script）の字に、ほかのブロックを指すパス（`workflows/<名>/`・Archon が読む所の `.archon/workflows/works-factory/<名>/`（pack の形。pack の段 `works-factory` は飛ばして見る）・`../<名>/`）が無い。`scripts/` の字には `lib/`・`workflows/.shared/`・自分のブロックの外への相対パスも無い）。

## E5 ブロックの返りは 1 つの節の構造体

- ブロックの YAML は `returns:` で 1 つの節を名指す。ブロックの間で渡す物の型の正本は、その節の `output_format`（素の JSON Schema）と、線の `with:` だけ。写しの型は持たない（持ち主の決め `io-in-output-format`）。
- 大きい中身はファイルに置き、返りには指し札 `{type: archon_artifact, run_id, path}` を入れる。
- ブロックの間は `with:` と返りの構造体だけで渡す。飛ばされうる段の返りは、受ける側の `with:` に `{ from: "$<id>.output.<欄>", if_skipped: null }` を書く（ASF の `W/ship/archon-ship.yaml`:148）。受け手が include の時は、線の返しの節（`script:` の節）で受けてから渡す（埋め P2。Archon は include の `with:` に書いた束ねを黙って JSON の値として渡すので、書けたように見えて効かない）。並べた物の集まりは `fan_out:` の返り（入力の順の配列）で受ける。
- 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）を読むのは report ブロックだけ。輪の返りは最後の 1 周しか残らないので、全部の周の記録（試験の関門の認証・認めた元からの赤・範囲の外の所見）を拾うのに使う（ASF の `W/.shared/report.ts`:130-140 と同じ）。引く時は include の頭（`<include の id>__`）と `loopGroupPath` で自分の分だけに絞り、一覧の `errors` を捨てない（読めた分と一緒に返す）。読む部品は report ブロックの中に置く。
- 仕事の結末を表す欄は `outcome_field:` で名指す。run が終わったことと仕事がうまくいったことは別の事実。
- 機械: `tests/layers/test_block_returns.py`（全ブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。線が `$<include の id>.output.<欄>` で読まない返りの欄は赤）。線が読む欄が返す節の `output_format` に在るかは Archon の `validate`（`tests/layers/test_archon_validate.py`。E1）が照らす。

## E6 外への書き込みは 1 つの script の節で、書いた後に読み戻す

- GitHub・対象のリポジトリの main・人に見える所への書き込みは、ブロックごとに 1 つの `script:` の節だけが行う。書いた後に読み戻し、読めた値で返る。終了の値 0 は書けた証拠にしない。
- 機械: `tests/layers/test_outward_write.py`（`gh`・`git push`・`git merge` を呼ぶ節がブロックに 1 つ以下。名簿は試験の中の表）。読み戻しの有無は人が見る。

## E7 読むだけの節は mutates_checkout: false を書く

- 作業ツリーを変えない節（判定・計画・事前審査・独立の目・報告の役と、読むだけの script）は `mutates_checkout: false` を書く。Archon は書いた節が作業ツリーを変えたら、その節を落とす。
- 機械: `tests/layers/test_readonly_nodes.py`（ブロック `judge`・`plan`・`plan-review`・`eyes`・`report` の役の節に全部在る。ただし judge の役のうち、作業ツリーに書く役（受け入れテストのファイルを書く `spec`・`spec-revise`）と、対象のリポジトリでコマンドを走らせる役（`pr-check`・`premises`・`prior-decisions`・`local-review`・`external-standards`・`procedure-trace`・`gate-efficacy`・`test-double-fidelity`・`main-path-observation`・`provenance`）は書かない。後の 10 は、今の works と同じく受け付けの script が作業ツリーの姿を比べ、変えた返答を拒む。ほかのブロックは試験の中の表で名指した節）。
- `runtime: uv` の script は頭に uv の script の宣言（PEP 723 の 4 行 `# /// script`・`# requires-python = ">=3.12"`・`# dependencies = []`・`# ///`）を置く。Archon は script の節を対象の作業ツリーを cwd にして `uv run <ファイル>` で起こすので、宣言が無いと対象に `pyproject.toml` が在る時に uv が作業ツリーに `.venv`・`uv.lock` を作り、読むだけの節が落ちる（issue #92）。機械: `tests/workflows/test_uv_scripts.py`（`workflows/*/scripts/*.py` の頭の 4 行と、`pyproject.toml` の在る種で走らせても作業ツリーが変わらないこと。`scripts/` の 1 段下のフォルダはまだ見ない。issue #96）。

## E12 期限・タイムアウトを置かない

- YAML の節にも script にも期限を置かない。止める時は止め札で止める。持ち主の決め `no-timeouts`。
- Archon は鍵を書かない節にも既定の期限を当てる（`script:` の節は 2 分で打ち切る。Archon の文書 `packages/docs-web/src/content/docs/guides/script-nodes.md` の `timeout`「Default: `120000` (2 min)」）。だから期限を外すには、期限を持つ節に実質無しの値 `1728000000`（ミリ秒で 20 日。今の works と同じ値）を書く。期限を持つ節と鍵は次のとおり（止めた Archon（`docs/design.md` の「語」）の `packages/workflows/src/schemas/dag-node.ts`・`dag-executor.ts` で確かめた）。
  - `script:`・`bash:` の `timeout`
  - `prompt:`・`command:` の `idle_timeout`
  - `loop:` の `idle_timeout`（1 周ごと）と `timeout`（`until_bash` の確かめ。無いと 120000 ms で打ち切る）
  - `loop_group:` の `timeout`（`until_bash` の確かめ）
  - `approval:` の `idle_timeout`（`on_reject` の直しの役が受け継ぐ）
  - `wait:` の中の `deadline_ms`（`event` を待つ時）
  - `cancel:`・`include:`・`workflow:` は期限を持たない（`include:`・`workflow:` の先の節は自分の鍵を持つ）
- 機械: `tests/layers/test_no_timeouts.py`（`workflows/` の YAML の節が全部上の種類のどれかで（知らない種類は赤）、期限を持つ節に上の鍵が在り、`timeout`・`idle_timeout`・`deadline_ms` が全部 `1728000000`）。

## E16 人の関所と並べは最新の ASF の形で書く

- 人の関所: 工程に `interactive: true` を書き、関所の節は `approval:`（見せる文 `message` と選び肢 `decisions`）で書く。後ろの節はその答えを `{ from: "$<関所>.output", if_skipped: null }` で受ける（ASF の `W/merge-queue/archon-merge-queue.yaml`:8・179-225）。持ち主の決め `asf-way-gates-fanout`。
- 自分の節に `approval:` を持つブロック（judge の仕様の関所）は、工程の頭に `interactive: true` を残す。止めた Archon の単独の `archon validate` は、`approval:` の節を持つ工程の頭に `interactive: true` が無いと警告を出す（`packages/workflows/src/loader.ts` 1389-1427 行の `validateWorkflowClassPlacement` が誤りの文を返し、1666-1675 行が猶予の警告にする）。線から差し込まれた時は線の `interactive: true` が効き、ブロックの頭のこの鍵には何も言わない。
- 並べ: `fan_out:`（`items`・`as`・`max_parallel`・`join`）で書く（ASF の `W/verify-runtime-suite/archon-verify-runtime-suite.yaml`:27-34）。作業ツリーに書く並べ（fix の組）は、組ごとに子の run を起こして作業ツリーを分ける。子の run が自分の作業ツリーを持つかは段 1 で実測する（`docs/design.md` の U8）。待ちの列・固定の枝の数・錠は持たない（持ち主の決め `no-queue`）。
- 機械: `tests/layers/test_gates.py`（`approval:` の節を持つ工程を差し込む一番上の工程（線）に `interactive: true` が在る。差し込まれるブロックは工程の頭に `worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない。`interactive` は、自分の節に `approval:` を持つブロックが `true` で書く時だけ許し、ほかのブロックが書いた時と `true` 以外の値は赤）。並べの形は人が見る。

## E17 対象のリポジトリには差分を置くだけ

- merge ブロックの既定は、封じた差分を run の置き場に置くだけ。対象のリポジトリに当てるのは人で、`bin/apply` が封じた hash を照らしてから当てる。PR を作る・merge する動きは、使う人が選んだ時だけ働く道にする。対象のリポジトリごとにレビューと merge の決まりと権限が違うため（持ち主の決め `diff-only-to-target`・`others-may-use`）。
- ASF が PR を merge するのは、ASF がこのリポジトリ（works-factory）を作る時だけ。
- 人が見る。
