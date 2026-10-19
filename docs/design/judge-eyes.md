# graph の設計書: judge（判定のまとめ）と eyes（独立の目のまとめ）

- 読む人: 2 つの graph を作る実装の役（作るのは README 11.1 の作る順の 4 番〔全部の block の後〕。急ぎは無い）と、作った後に直す人。どちらもこの文書の決めのとおりに作り・直す。パスは、組み込みで pack が `workflows/` に入れ替わった後の形で書く（古いサブグラフの `workflows/judge/`・`workflows/eyes/` は組み込みで消え、同じパスに新しい graph が入る）。
- 何の話か: 組み込みの前の judge のサブグラフ（古い `workflows/judge/`。YAML 2305 行）を 8.1 の block を並べる graph `workflows/judge/` に、組み込みの前の eyes のサブグラフ（古い `workflows/eyes/`）を r1〜r4 と structure（after）を並べる graph `workflows/eyes/` に作り直す設計。どちらも line から 1 つの include で呼ばれる（README 8.7。Archon 同梱の sdlc の `deliver` が `implement`・`review` を include で組む形）。型は [README.md](README.md) の 1 節（graph の定義と形の直し 7）。line の側の配線は [line.md](line.md)。
- 決めたこと: 2 つの graph は、block をいつ回すか（`when:`）・並べ方・飛ばされうる値の受け直し（埋め P2・P8）・まとめの判定（judge の `ready` と、止める訳が重なった時にどの止めの語〔`works:premises` など、run を止めた訳を表す語〕を返すかの順〔1.4〕、eyes の `ok`）だけを持つ。AI の node と観点の計算は持たない。判定の裏取り（verify の block。判定を別の役が確かめ直す）を回すかは、line が段（run の頭の深さ: 軽量・標準・重厚）ごとに引いた真偽の表 `verify_by_tier` を port で受け、head-depth の block が返した段でその表を引くだけにする（深さの表は line に 1 つ。node と `when:` はこの文書の 1.5）。再審は judge の graph を通らない（line が diagnose を直に include する）。守りのパスの当たり（差分が、人の確かめなしに変えてはならないパスに触れた件。README の語「守りのファイルと当たり」）を数えるのは eyes から merge へ移った（README 13 節）ので、eyes の `ok` は目の判定だけで決まる。
- 持ち主（リポジトリの owner）に求めること: なし。README・各 block の設計書・今のコードで決まった（3 節）。2 波目の設計書（README 11.1 の作る順の 2 つ目の組。diagnose・verify・r1〜r4）は書き終える前に置かれたので、配線はそれぞれの設計書の 1.2（port）と 1.6 に合わせた。残る確かめは 4 節（未確認の一覧。どれも持ち主の答えを待つ物ではない）。

語は README の頭の物と line.md の頭の物（始めの記録・配る値・受け皿・返し・段）を使う。ほかに:

- pointer: Archon がファイルを指す値 `{type: archon_artifact, run_id, path}`（README 4.1）。大きい中身はファイルに書き、出力ではこれを渡す。
- 境の口: pack の共通の口 `workflows/.shared/ports.py`（入力の読み・place・出力の書き）。
- 憲法の番号（憲法 5 など）: README 2 節の 6 行の番号。keep-essence の番号: README 10 節の、失ってはならない 12 の仕組みの番号。
- E8・E9・E54 などの E の番号（2 章）: eyes の能力の棚卸し `docs/plans/2026-10-13-capabilities/tail.md` の行の番号（AGENTS.md の決まりの番号 E1〜E22 とは別。2.6 に一覧）。J の番号は judge の棚卸し `docs/plans/2026-10-13-capabilities/judge.md` の行。
- 埋めの P の番号（P2・P8 など）: `docs/polyfills.md` の節の番号。

## 0 2 つの graph の共通の形

- 置き場: `workflows/judge/works-factory-judge.yaml`・`workflows/eyes/works-factory-eyes.yaml`。`scripts/`・`src/`（package `src`）・`fixtures/standalone.stubs.yaml`・`tests/blocks/judge/`・`tests/blocks/eyes/`。手本は `workflows/policy-check/`（README 13 章・`workflows/AGENTS.md`）。
- AI の node を持たない（README 7.1 の 6）。だから README 6 節の node ごとの 9 項は当たらない。
- 返す node は `verdict`（script。`trigger_rule: all_done`）。`outcome_field: ok`。返りに欄 `report`（日本語の行の配列）と `sections`（`[{title, lines, files?}]`。report の port `sections` と同じ形。include した block の `report` の欄を block ごとに 1 節にした物）を置く（README 4.1・7.1 の 8）。返す node は落ちない（境の口を読めない時も標準ライブラリだけで `ok: false` と訳を返す。今の judge の `verdict.py` と eyes の `verdict.py` の `fallen` の形）。
- include ごとに受け皿 `<id>-out`（script `returned`。今の line が YAML の錨〔anchor〕で 1 か所に書いて使い回す受け皿と同じ作り）を置く。`all_done` で集める node（`verdict` と、judge の `diagnose-in`）は受け皿の got だけを読む。流れの node（既定の `all_success`）は include の出力を直に読む（作り手が落ちれば、依る node は飛ぶ）。訳: Archon は落ちた node への `with:` を誤りにする（今の `returned.py` の docstring。止めた Archon の `dag-executor.ts` の `resolveBindingDirective`）。1 つの block の返す node が落ちても、ほかの block の結果が報告に届く。
- include の `with:` は graph の入力を `$INPUTS.<名>` で直に渡す（今の line の `merge-apply` の `deliver: "$INPUTS.deliver"` と同じ）。`when:` が graph の入力を読む所は、頭の返し `ins`（script）が入力を出力に写した物を読む（今の policy-check の `policy-in` と同じ形。`when:` の式が `$INPUTS` を読むかは確かめていないので頼らない）。
- script は `ports` の口だけで入力を読む。`returned`・`ins` の本体は `ports.picked` と `ports.flag` を呼ぶ数行（graph ごとに `scripts/` に置く。Archon は名の script を workflow のフォルダから探す）。
- 返りの欄 `optional`（README 4.1）: 落ちても line が先へ進めてよい中の node の宣言 `[{node, bare}]`。line の `collect` が include の頭を付けて読む。

## 1 judge（判定のまとめ）

### 1.1 役

依頼と差分から、直す単位を切った判定を作る。8.1 の block（head-depth・spec の write・parallel-pr・premises・purpose・world・素材の観点 10 本〔gate-efficacy を除く。3 節の持ち主の決め 2026-10-19〕・diagnose・verify）を今の judge と同じ順と条件で回し、どこかの段が止めれば、止めの語を返して後ろを回さない。判定の道だけを持ち、再審の道は持たない（line.md の 4.4）。

### 1.2 port

入力（どれも line が始めの記録から引いて配る値。line.md の 1.6。単独で回す時は既定の値で回る）:

- `request`: `json(shared:request.schema.json): 依頼の行の配列か、それを findings の欄に持つ object（工場の依頼のファイルの形）。空の配列は依頼の行が無い run`。既定 `[]`。
- `pr_text`: `text: 依頼が名指す PR の番号・題・本文を並べた文。空は PR の無い run`。既定 `""`。
- `carried`: `json(shared:constraints.schema.json): 前の run が運んだ前提の実測の行の配列。空の配列は運ばれていない`。既定 `[]`。
- `base`: `text: 入口の差分の根の commit。空は HEAD`。既定 `""`。
- `entry`: `text: 判定から入る run の出どころの文。空は判定から入る run でない`。既定 `""`。
- `web`: `choice(on|off): 世界の解の段が web で出典を探すか`。既定 `on`。
- `world`: `flag: 世界の解の段を回すか`。既定 `true`。
- `spec`: `flag: 仕様の段を挟むか（承認ノードを持つ）`。既定 `false`。
- `has_checks`・`thickness`（`choice(auto|light|standard|heavy)`。既定 `auto`）・`design_only`: head-depth の同じ名の port に渡す（説明は head-depth の 1.2 の字）。
- `verify_by_tier`: `json(verify-by-tier.schema.json): 段ごとに判定の裏取りを回すか {軽量, 標準, 重厚}（真偽）。空の object はどの段でも回さない`。既定 `{}`。形は `{"type": "object", "properties": {"軽量": {"type": "boolean"}, "標準": {"type": "boolean"}, "重厚": {"type": "boolean"}}}`（`workflows/judge/schemas/`）。
- `user_env_dir`: `text: 利用者の HOME・XDG に戻して起こした印を置く置き場の絶対パス。空は place`。既定 `""`。
- `request_origin`: `text: 依頼の行の出どころの名（判定役に見せる依頼のバッチの origin）。空は「人の依頼（依頼の行）」`。既定 `""`。diagnose へ渡す。
- `baseline`・`policy`: `file`（直す前の試験の結末・固めた方針の写し）。diagnose へ渡す。既定 `""`。
- 依頼の answers と prior_failures は渡さない: diagnose は依頼の容器（port `request`）から自分で読む（diagnose の設計書の 1.2 の `answers`・`prior_failures` の「空の配列は容器の物」）。
- `lang`: `text`。既定 `""`。どの include にも渡す。

出力（`returns: verdict`・`outcome_field: ok`）。line が配る欄だけを持つ（line.md の 4.5）:

- `ok`: boolean。止めの語が無く、diagnose が返った。
- `stop_reason`・`reason`: 1.4 の順の最初の止め（無ければ空）と、その訳。
- `ready`: boolean。`ok` で、diagnose の `ready` が真（判定を受け、開いた単位が 1 つ以上。今の J89）。開いた単位が無いのは止めでない（`ok` 真・`ready` 偽。line は直す物が無い周に進む）。
- `units`: 判定の開いた単位の目録 `[{id, paths, summary}]`（diagnose の出力。構造の目と r1 の形）。
- `questions`: diagnose の `questions`（判定の保留の問い。止めた run は空）をそのまま通す（diagnose の設計書の 1.6 の「judge のまとめは questions を返りに載せる」に合わせる。line は今は読まない）。
- `judgment`: 判定の pointer。`answer_ties`・`out_of_purpose`・`materials`（素材の 15 欄）・`brief`・`inputs`（再審の `prior_brief`・`prior_inputs` に渡す）: diagnose の出力の pointer か null。
- `purpose`（purpose の出力の `purpose` object）・`purpose_text`・`purpose_source`・`means`。
- `purpose_review`: 目的の監査の受けた返答の pointer（`{verdict, reason, findings}`。purpose-review の `material.json` の `reply` を `verdict` が place の `purpose-review.json` に写した物。回さなかった・受けなかった run は `{}` を書いた物）。independent-design の port `purpose_review` の形（今の `judge_accept.verdict` が `PURPOSE_REVIEW_FILE` に写していた事と同じ）。
- `constraints`: premises の `constraints` の pointer。
- `world`: world の `rows` の pointer か null（行が 0 の時も null。今の J29）。`world_state`: `{status, reason, classes, dropped}`（world の出力の欄。走らなかった run は `{status: "skipped", reason: <訳>}`）。
- `spec`: spec の `spec` の pointer か null。`spec_rows`・`spec_origin`: spec の `added_rows` と `added_origin`（仕様が足した受け入れ条件の行。同じ行は `spec-in` が依頼の行の後ろに積み、並行 PR・前提の実測・世界の解・先行議論の突合が依頼の行として読む〔1.3 の 4〕。diagnose は積んでいない `request` とこの行を別に受け、バッチを分けたまま 2 度数えない）。
- `excluded`・`pr_drafts`: parallel-pr の `excluded`・`drafts`。`downgrades`: parallel-pr と diagnose の `downgrades` を並べた物。
- `decisions`: prior-decisions の `material` の pointer（記録された方針の決着済みの論点の出どころ。prior-decisions の設計書の 1.6）。
- `tier`・`tier_why`・`row_asks`・`tier_record`: head-depth の `tier`・`why`・`rows`・`record`。head-depth が返らなかった run は `標準` と訳「run の頭の深さの段が返らなかった（標準で進む）」と null（今の「落ちても判定は標準で進む」。head-depth の設計書の 1.6）。
- `verify`: verify の `verify` の pointer か null（回さなかった・返らなかった）。`verify_why`: 回さなかった訳（段と名指しの表で切だった・開いた単位が無い・判定が止まった）か空。
- `report`: このまとめの行（止めの行・回さなかった段の行・返らなかった block の行）。`sections`: 0 節の形。並びは 1.3 の順。
- `optional`: `world__`・`head-depth__`・素材の 10 本の `<id>__`（落ちても判定は進む段）。

### 1.3 node の並び（`workflows/judge/works-factory-judge.yaml`）

並びと条件は今の judge のまま（`workflows/judge/works-factory-judge.yaml` の depends_on と when）。止めの記録（今の `judge/stop.json`）は使わず、前の段の出力の欄で `when:` を書く（README 4.3）。

1. `ins`（script）: 入力の `spec`・`world`・`web` を出力に写す。
2. `head-depth`（include。`depends_on: [ins]`）。`with:` `request`・`has_checks`・`thickness`・`spec`・`design_only`・`lang`。→ `head-depth-out`。
3. `spec`（include、`mode: write`。`depends_on: [ins]`・`when: $ins.output.spec == true`）。`with:` `request`・`pr_text`・`user_env_dir`・`lang`。→ `spec-out`。中に仕様の承認ノードを持つ（README 8.1。graph は持たない）。
4. `spec-in`（返し。`depends_on: [ins, spec-out]`・`none_failed_min_one_success`）: `go`（仕様の段を挟まないか、spec の `status` が `approved`）・`stop_reason`（spec の返りの止めの語。spec を挟んだのに返りが無ければ `works:spec`）・`spec`・`added_rows`・`added_origin`・`request`（graph の入力 `request` の後ろに `added_rows` の行を積んだ依頼を place の `request.json` に書いた pointer。仕様を挟まない run は入力の写し。依頼が容器の形なら `findings` の後ろに積む）。今の `spec_freeze` は受け入れ条件の行を `judge/request.json` に積み、後の前提の実測（`premises_accept`）・世界の解（`world_intake`）・並行 PR（`pr_scan` の `where`）・先行議論の突合（`request_wheres`）がそれを読んだ。block は変えず、この `request` を 5〜9 の `request` に渡して同じ能力を続ける（組み込みの決め `docs/design/integration.md` の 4.1 の 1）。
5. `parallel-pr`（include。`depends_on: [spec-in]`・`when: $spec-in.output.go == true`）。`with:` `request: $spec-in.output.request`・`base`・`changed: "[]"`・`lang`。仕様の承認の後に回る（承認で書いた受け入れテストのファイルを、役の前の写しに入れるため。parallel-pr の設計書の 1.6）。→ `parallel-pr-out`。
6. `premises`（include。`depends_on: [parallel-pr]`・`when: $parallel-pr.output.stop_reason == ''`）。`with:` `request: $spec-in.output.request`・`carried`・`lang`。→ `premises-out`。
7. `purpose`（include。`depends_on: [premises]`・`when: $premises.output.ok == true`）。`with:` `request`・`pr_text`・`constraints: $premises.output.constraints`・`lang`。→ `purpose-out`。
8. `world`（include。`depends_on: [purpose, ins]`・`when: $purpose.output.ok == true && $ins.output.world == true`）。`with:` `request: $spec-in.output.request`・`purpose: $purpose.output.purpose_text`・`means: $purpose.output.means`・`web: $ins.output.web`・`lang`。→ `world-out`。7 の purpose は積む前の入力 `request` を受ける（今の `purpose_prep` も依頼のファイルを先に読み、積んだ `request.json` は依頼のファイルが無い時だけ読んだ）。
9. 素材の観点 10 本（include。gate-efficacy は include しない〔3 節の持ち主の決め 2026-10-19〕。どれも `depends_on: [purpose, world-out]`・`trigger_rule: none_failed_min_one_success`・`when: $purpose.output.ok == true`。互いを待たずに並ぶ）。`with:` はどれも `base`・`entry`・`lang` と、観点ごとに足す物: prior-decisions は `request: $spec-in.output.request`、purpose-review と external-standards は `purpose: $purpose.output.purpose`。回す条件と回さない時の素材の埋めは各 block が持つ（materials.md の 10 節）。世界の解の受け皿 `world-out` に依るのは、世界の解が切られた・落ちた run でも素材を回すため（今の `material-route` の `depends_on: [purpose-loop, world-finish]` と `none_failed_min_one_success`）。各 `→ <id>-out`。
   - id: `prior-decisions`・`purpose-review`・`local-review`・`consistency-bypass`・`hygiene`・`external-standards`・`procedure-trace`・`test-double-fidelity`・`main-path-observation`・`provenance`。
10. `diagnose-in`（script。`depends_on:` 素材の 10 本の受け皿と `parallel-pr-out`・`head-depth-out`・`world-out`・`spec-in`・`premises-out`・`purpose-out`。`trigger_rule: all_done`。`when:` を持たない）: diagnose へ渡す飛ばされうる値をそろえる返し。落ちない（読めなければ `ok: false` と訳）。
    - `go`（前提の実測と目的の固定の受け皿の `ok` が両方真）・`purpose`（purpose の `purpose` の pointer）・`constraints`（premises の `constraints` の pointer）。diagnose の `when:` と `with:` はこの返しだけを読む（3 節の決め「`when:` は飛びうる node を読まない」）。
    - `materials`: 素材の 10 本の `material` の pointer を観点の順に並べた JSON の配列（値。diagnose の設計書の 1.6 の「11 本の `material` を並べた JSON の配列」。materials.md の 11 節の未確認「配列の組み方」の答え: Archon の `with:` は配列を組めないので script が組む）。返りの無い観点（受け皿が飛んだ）は配列に入れず `missing` に名を返す（diagnose の `materialkit.assemble` が残りを `not_run` で埋め、この graph の `report` が名指す）。
    - `pr_material`（parallel-pr の `material`。返らなければ null）・`world_rows`（world の `rows` か `""`）・`row_asks`（head-depth の `rows` か `[]`）・`depth_why`（head-depth の `why` か `""`）・`spec_rows`・`spec_origin`（`spec-in` の `added_rows` の pointer か `""` と `added_origin`）。
    - `verify`: `verify_by_tier[<head-depth の tier。返らなければ 標準>]` が真か（1.5）。
11. `diagnose`（include。`depends_on: [diagnose-in]`・`when: $diagnose-in.output.ok == true && $diagnose-in.output.go == true`）。`with:`（diagnose の設計書の 1.6）: `request`（積む前の入力）・`request_origin`・`base`・`purpose`・`constraints`・`materials`・`pr_material`・`world_rows`・`row_asks`・`depth_why`・`spec_rows`・`spec_origin` ← `diagnose-in`・`baseline`・`pr_text`・`policy`・`lang`。`objection` と `prior` は渡さない（判定の道）。素材の観点が諦めていれば、diagnose が判定役を起こさずに `stopped` と `works:material` を返す（diagnose の設計書の 1.2。今の `diagnose_prep` の「残りで組んだ上で止める」）。→ `diagnose-out`。
12. `verify`（include。`depends_on: [diagnose, diagnose-in]`・`when: $diagnose-in.output.verify == true && $diagnose.output.ready == true`）。`with:` `judgment: $diagnose.output.judgment`・`lang`。diagnose の受け付けの輪が何回回っても、diagnose が返った後に 1 回だけ回る。→ `verify-out`。
13. `verdict`（script。全部の受け皿と返しに `depends_on`。`trigger_rule: all_done`）: まとめの判定（1.4）と返り（1.2）。

### 1.4 まとめの判定（`verdict`。`src/verdict.py`）

止めの語の順（上から最初に当たった物。今の `judge_accept.verdict` と `_missing_stage` の順）:

1. 仕様: `spec-in.stop_reason`（`human:spec-gate`・`request:spec-gate`・`works:spec`）。
2. 並行 PR: parallel-pr の `stop_reason`（役を諦めた時の `works:pr`）。受け皿が飛んだ（返りが無い）なら `works:pr` と訳「並行 PR の段が返らなかった」。
3. 前提の実測: premises が返らない・`ok` が偽 → `works:premises`（今の J12。`stopby.PREMISES`）。
4. 目的の固定: purpose が返らない・`ok` が偽 → `works:purpose`（J12・J19。`stopby.PURPOSE`）。
5. 判定: diagnose が返らない → `works:judge`、返りの `stop_reason` が在ればそれ（素材の観点の諦めの `works:material`〔J62〕・3 回とも拒まれた時と読めない入力の `works:judge`〔J81〕・依頼が読めない `works:request`）。
6. 判定の裏取り: verify の `stop_reason`（作業ツリーが変わった時の `works:judge-verify`。J86）。

止めの語の字と意味の持ち主は `lib/stopby`（KEEP）。止めるかを決めるのはこの graph（README 9.3 の `stopby` の行「止めるかは judge のまとめが決める」）。止めた run でも、走った block の `sections` と、`judgment`・`purpose` の欄は返る（読み手は null か空を受ける。今は止めの道でも判定と目的の空の形を置いていた〔J90〕が、block が自分の place に書き、graph は pointer を運ぶだけなので、走らなかった block の欄は null）。

### 1.5 判定の裏取りを回すか

line が段ごとに引いた真偽の表 `verify_by_tier` を、head-depth が返した段で選ぶ（`diagnose-in` の `verify`）。表は line の深さの表（段 → 回す物）と始めの記録の名指し（`features_on`・`features_off` の `judge_verify`）から line が作る（line.md の 1.6）。この graph は段の意味も既定も知らない（段が返らない時に「標準」で引くのは、head-depth の設計書の 1.6 の「落ちても標準で進む」をそのまま写した物で、段の意味の決めではない）。訳: 段は head-depth（この graph の中）が決め、表は line が持つ（README 1.2 の D・形の直し 5）。単独で回すと表が空の object で、どの段でも回さない（今の既定「判定の裏取りは切」と同じ）。開いた単位が 2 つ未満なら verify の block が自分で回さない（verify の設計書の 1.2）。

### 1.6 place のファイルとコード

- place（judge の graph の include の道。line から include されれば `judge/`）に書くのは `verdict` の `purpose-review.json`・`verdict.json`（返りの写し）だけ。名は `src/files.py`。block のファイルは各 block の place（`judge/<id>/`）に在り、graph は pointer で受け渡す。
- `src/verdict.py`（止めの順・返りの組み立て・節の並び）・`src/files.py`。`scripts/`: `ins.py`・`returned.py`・`spec_in.py`・`diagnose_in.py`・`verdict.py`。
- 使う `lib/`: `materialkit`（`read`。素材の `status`・purpose-review の `reply` を読む）・`stopby`・`oneline`・`jsonfile`。今の `lib/judge_accept.py` の graph の部分（`intake`・`material_route`・`verdict`・`start_view`・`write_stop`・`read_stop`・`PORTS`・`FIRST_PORTS`・`require_ports`）は使わない（README 9.2 の「`judge/` の決め打ちの包みと `PORTS`・`FIRST_PORTS` は DELETE」）。

### 1.7 今の judge との比べ

今の node と、`docs/plans/2026-10-13-capabilities/judge.md` の行（J01〜J113）の行き先:

- `intake`（J01〜J05・J07）: 始めの記録の読みと依頼の型の照らしは line の `start` と各 block の `requestrows`（依頼のファイルの 3 つの拒み・findings の型・依頼 1 件以上と言うのに空の行は `start` が AI の前で拒む）。機能の切り替え（J05）は line の `when:` と配る値（`world`・`spec`・`verify_by_tier`）。止めの控え（J07）は使わない（1.4 の止めの語の順）。前の失敗の行（J06）は diagnose が依頼の容器から読む（diagnose の設計書の 1.2）。
- `head-depth-prep`〜`head-depth-loop`: head-depth の block。再審の道で回らないのは、再審が judge の graph を通らない配線で続く。
- `spec-loop`〜`spec-freeze`（J92〜J99）: spec の block（`mode: write`）。仕様の承認ノードは block の中。承認の後の作業ツリーの写しの取り直し（J97 の尾）は、parallel-pr と premises が役の直前に自分で写すので要らない（parallel-pr の設計書の 10 節の 3）。
- `pr-scan`〜`pr-check-reads`（J31〜J41）: parallel-pr の block。下げた物の宣言（J41）は block の出力 `downgrades` で line に返す。
- `premises-loop`（J08〜J13）・`purpose-prep`〜`purpose-loop`（J14〜J20）: premises・purpose の block。「目的は最初の修正の前に 1 度だけ固める」（J14）は、この graph が purpose を 1 回だけ include し、再審の道が通らないことで続く。
- `world-*`（J21〜J30）: world の block。目的の文が無い・止めた run は回さない（J27）は `when: $purpose.output.ok == true`。網が無い・web が off でも段を止めない（J25）は world の block の中で、graph は world の失敗で止めない（`optional`）。
- `material-route`・素材の 11 の輪（J42〜J62）: 素材の観点の block。回す条件と回さない時の埋めは各 block の intake（materials.md の 10 節）。役を起こす前の作業ツリーの写しは観点ごと（materials.md の 11 節の未確認「11 本の見方がずれうる」の答え: どれも同じ `base` を受け、役が作業ツリーを変えたら各 block の受け付けが拒むので、見方は同じ版の同じ作業ツリーになる。graph は `material.json` の `base` を突き合わせない）。素材の 15 欄（J60・J61）は diagnose が `materialkit.assemble` でそろえる。
- `diagnose-prep`〜`diagnose-loop`（J63〜J82）: diagnose の block。
- `verify-prep`〜`verify-merge`（J83〜J86）: verify の block と 1.5。回さない時に「回さなかった形」の申し送りを置くこと（J83 の尾）はやめる（verify の設計書の 1.6。訳は line の報告の行と、この graph の `verify_why`）。
- `rejudge-prep`〜`rejudge-loop`（J100〜J105）: diagnose の block の再審の道。line が直に include する（line.md の 4.4）。
- `verdict`（J87〜J91・J108〜J113）: この graph の `verdict`。単位の目録（J87・J88）は diagnose の出力 `units`。公開の隣のファイルを名で開く形（J108）は pointer の欄（1.2）に替わる。返す node は落ちない（J91）。
- 役の設定（J106・J107）: 各 block の YAML。
- 消した物と訳: 止めの控え `stop.json`（README 4.3）・入口の写し `start.json`・`request.json`・`intake.json`（block は port で受ける）・判定の裏取りの回さなかった形の申し送り（上）・止めの道で空の判定と目的のファイルを置くこと（走らなかった block の欄は null。読み手は null を受ける）。

### 1.8 試験（`tests/blocks/judge/`）

- standalone の筋書き `workflows/judge/fixtures/standalone.stubs.yaml`: `fixture.inputs` は `request` だけ（依頼の行 1 つ）。include した block の AI の node と loop の本体の script を台本で差し替え（README 13 章）、graph の script は本物。`reached` に `verdict`。`verdict` の `ok` が真。
- 筋書き（今の `workflows/judge/fixtures/` の 8 本を写す）: `bad-request`（依頼の型の拒みは line と block の受け付けに移ったので、premises の出口が `failed` を返す台本 → `works:premises`。`requestrows` の拒みそのものは premises の block の筋書きが見る）・`judge-gave-up`（`works:judge`）・`material-peer-stop`（素材の諦め → `works:material`）・`no-open-units`（`ok` 真・`ready` 偽）・`pass`・`spec-on`（spec が approved を返して先へ進む。承認ノードは spec の block の中で graph は通らない）・`spec-stop`（spec が止めを返す → 人が仕様の承認ノードで止めた語 `human:spec-gate` が返り、後ろを回さない。1.4 の 1）・`world-offline`（`web: off`）・`rejudge` は line へ移す（再審は line の筋書き）。足す: `verify-heavy`（`verify_by_tier` の重厚が真で、head-depth が重厚を返す → verify が回る）・`world-cut`（`world: false` でも素材が回る）。
- 振る舞いの試験: 止めの語の順（1.4 の 1〜6 を 1 つずつ立てて、最初の物が返る）・返りの無い block の欄が null で `report` に行が在る・`diagnose-in` の配列の順と `missing`・`verify` の選び（段が返らない時は標準）・`verdict` が落ちない（壊れた入力で `ok: false`）。元は今の `tests/workflows/test_judge.py` の graph の場面（README 9.5）。
- 配線の yes/no: 8.1 の block の全部を 1 回ずつ include する・再審の道の block（diagnose に `objection` を渡す include）が無い・include した block の `inputs:` が全部 `with:` で渡るか、渡さない訳の一覧に在る。
- 守る keep-essence: 7（class_query。diagnose が作り、この graph は運ぶ）・12（世界の解の行を diagnose・plan・plan-review・line へ。`world` の欄）。

## 2 eyes（独立の目のまとめ）

### 2.1 役

修正の後に、直しを作った役と別の会話で差分を確かめる 4 つの目（r1〜r4）と、直した後の構造の実測（structure の `mode: after`）を並べ、目の判定をまとめて変更を通してよいか（`ok`）を返す。目を回すか・R3 を R4 にまとめるかは line が決めて flag で渡し、この graph は `when:` に写すだけ（README 1.2 の D。r1 の設計書の 0.11）。

### 2.2 port

入力（line の `eyes-in` と配る値から。line.md の 4.5）。名と形は受ける block の port と同じにする（r1 の設計書の 0.2・各設計書の 1.2）:

- `run`: `flag: 4 つの目を回すか（偽なら目を起こさず、直した後の実測だけを回す）`。既定 `true`。
- `merge`: `flag: R3 の観点を R4 の会話に入れるか（r3 を回さず、r4 の coherence を真にする）`。既定 `false`。
- `skip_why`: `text: 目を回さない訳（報告の行）。空は訳が渡されていない`。既定 `""`。
- 4 つの目の共通の port（r1 の設計書の 0.2）: `base`・`lang`・`green`・`policy`・`review`・`answers`・`request`・`changed`・`pushes`・`decisions`（形も既定も同じ）。`after` は graph の中で structure（after）から引くので入力に持たない。
- r1 の port: `purpose`・`units`・`judgment`・`fixes`・`x_scalars`・`checks`（r1 の設計書の 1.2）。
- r2 の port: `head`・`base_label`・`design`・`design_reason`・`design_premises`・`constraints`・`test_outcomes`・`tdd`（r2 の設計書の 1.2）。`head` は structure（after）の `base` にも渡す（直す前の版）。
- r4 の port: `ripple`・`world_rows`・`asked`・`declared`（r4 の設計書の 1.2）。
- structure（after）の port: `plan`（修正が使った修正案の欄）・`intent`（structure の設計書の 1.2）。
- 形のファイル: 受ける block の `schemas/` の形と同じ中身を `workflows/eyes/schemas/` に名を `eyes-` で始めて置く（同じ名の形を pack の 2 か所に置かない。7.1 の 5）。`shared:` の物（`plan-verdict`・`gate-answers`・`pushes`・`fix-marks`・`constraints`）はそのまま名指す。

出力（`returns: verdict`・`outcome_field: ok`）。欄の名は今の eyes の返りの名を残す（line の最後の承認ノード・merge・報告が今の名で読む）:

- `ok`: boolean。2.4。
- `r1`・`r2`・`r3`・`r4`: 目の判定の行 `{status, reason}` か null（回さなかった目）。
- `questions`: r4 の `questions`（人に回す問い）。`passes`: r4 の `passes`（修正前に通したので問いから外した行）。
- `premise_check`: r2 の `premise_check`（`{verdict, reason, key, resolution, facts}` か null）。`notes`: r2 の `notes`（R2 の入力の控えの行）。今の `notes`・`r4_passes`・`premise_reply` の pointer の先を、値で返す形（r1 の設計書の 0.11）。
- `after`: structure（after）の `after` の pointer か null。`dirty`・`escalate`: 同じ出力の数。`after_ok`: structure（after）の `ok`（測れなかった時は偽。line の最後の承認ノードと報告が「直した後の実測が無い」と言う）。
- `report`・`sections`・`optional`（`structure-after__`。直した後の実測が落ちても先へ進む。E54）。

### 2.3 node の並び（`workflows/eyes/works-factory-eyes.yaml`）

1. `ins`（script）: `run`・`merge` を出力に写し、空の `head` を作業ツリーの `HEAD` の版に解いて `head` に出す（structure の `base` は空を受けない。単独で回す時のため。憲法 5）。
2. `structure-after`（include `works-factory-structure`、`mode: after`。`depends_on: [ins]`。`when:` を持たない: 目を省く run でも測る。E71）。`with:` `units`・`intent`・`policy`・`base: "$ins.output.head"`・`plan`・`lang`。→ `structure-after-out` → `after-in`（返し。`depends_on: [ins, structure-after-out]`・`none_failed_min_one_success`。`after` の pointer か `""`）。
3. `r1`（include。`depends_on: [after-in]`・`when: $ins.output.run == true`）。`with:` は r1 の設計書の 1.6（`base`・`purpose`・`units`・`judgment`・`fixes`・`x_scalars`・`green`・`checks`・`after: $after-in.output.after`・`review`・`policy`・`lang`）。→ `r1-out`。
4. `r2`（include。`depends_on: [ins]`・`when: $ins.output.run == true`）。`with:` は r2 の設計書の 1.6（`base`・`head`・`base_label`・`purpose`・`design`・`design_reason`・`design_premises`・`answers`・`request`・`changed`・`constraints`・`test_outcomes`・`tdd`・`lang`）。直した後の実測を読まないので、structure（after）を待たない（E9: R1・比較役〔R2〕・前提の検算・R3 は互いを待たない）。→ `r2-out`。
5. `r3`（include。`depends_on: [after-in]`・`when: $ins.output.run == true && $ins.output.merge == false`）。`with:` は r3 の設計書の 1.6（`base`・`green`・`after`・`review`・`policy`・`answers`・`request`・`pushes`・`decisions`・`lang`）。→ `r3-out`。
6. `r4`（include。`depends_on: [after-in, r1-out, r2-out]`・`trigger_rule: none_failed_min_one_success`・`when: $ins.output.run == true`）。R1・R2 の後に、どちらかが落ちても回す（E8。落ちた目は受け皿が飛ぶだけで、r4 の依る node は失敗にならない）。`with:` は r4 の設計書の 1.6（r3 と同じ共通の port に `changed`・`purpose`・`ripple`・`world_rows`・`asked`・`declared`・`coherence: $ins.output.merge`）。→ `r4-out`。
7. `verdict`（script。全部の受け皿と `ins`・`after-in` に `depends_on`・`all_done`）: 2.4。

今の待ち合わせの柵 `eyes-complete`（E56）は、`verdict` が受け皿だけを `all_done` で読むので要らない。今の `prep`（目ごとの指示の値の支度）は各 block の intake と prep へ、`protected` は merge へ、型つきの成果物 `eye-verdict` は作らない（r1 の設計書の 0.1）。

### 2.4 まとめの判定（`verdict`。`src/verdict.py`）

- `run` が偽: `r1`〜`r4` は null、`ok` は真（今は守りのパスを確かめられた時だけ真だったが、守りのパスは merge が数える。README 13 節）。`report` に「独立の目: 深さで省いた（<skip_why>）」の 1 行（E48）。
- `run` が真: 目ごとの行は、その block の出力の `verdict`（受け皿が飛んだ目は `{status: unverifiable, reason: eyekit.fell_text(…)}`。「R<n> の筋が落ちた（<目>: 出力が無い。ノードが落ちた）」）。`merge` が真の時、`r3` の行は r4 の出力 `coherence` の判定の行（r4 の設計書）。
- 落ちた目の訳の尾（E50）: `r4` の行が在り（r4 が返った）、ほかの目の行の `reason` が `eyekit.FELL_MARK` を含めば、「まま R4 を回した」を足す（今の `fell_text(…, ran)`。r1 の設計書の 0.9 が graph に残した物）。
- `ok`（E49）: 回した目の全部の行が `pass` で、R2 が前提の検算の道でない（r2 の `premise_check` が null）時だけ真。どれか 1 つでも `fix-needed`・`redesign-needed`・`unverifiable` なら偽。R2 の行は前提の検算の道では r2 が `unverifiable`（「前提不成立: 」の頭）を返すので、行だけでも偽になる。
- 直した後の実測の `dirty`・`escalate` は `ok` に入れない（今の eyes も入れず、最後の承認ノードが「考えの住処の柵（対象のリポジトリが考えの置き場を縛る表）の当たりの数が増えた」を開ける理由にし、報告が残りに数える。E73。structure の設計書の 1.6 が eyes の設計書に決めを任せた所）。
- `questions`・`passes` は r4、`premise_check`・`notes` は r2 の出力から写す（受け皿が飛んだ目は空の配列と null）。
- `sections`: structure（after）・r1・r2・r3（`merge` の時は無い）・r4 の `report` を 1 節ずつ（見出しは「直した後の構造の実測」「独立の目 R1 最小性とコメント」…）と、このまとめの行の節「独立の目のまとめ」（`ok` の訳・省いた目・まとめた目）。
- 落ちない: 中の誤りは全部捕まえ、`ok: false`・目の行は全部 `unverifiable`（理由に誤りの 1 行）・ほかは null か空で返す（今の `fallen`。E54・E55）。NaN と Infinity は `allow_nan=False` で落ちた返りにする。

### 2.5 place のファイルとコード

- place に書くのは `verdict.json`（返りの写し）だけ。目の返答は各 block の place に在る。
- `src/verdict.py`・`src/files.py`。`scripts/`: `ins.py`・`returned.py`・`after_in.py`・`verdict.py`。
- 使う `lib/`: `eyekit`（`fell_text`・`FELL_MARK`。r1 の PR が足す）・`seal`（判定の語 `PASSED` など）・`oneline`・`jsonfile`。今の `lib/eyeverdict.py` のまとめの部分（`collect`・`unverified`・`write_notes`）はこの graph の `src/` へ（README 9.2）。観点ごとの部分は r1〜r4 へ（r1 の設計書の 0.5）。

### 2.6 今の eyes との比べ

`docs/plans/2026-10-13-capabilities/tail.md` の E の行のうち graph に残る物（r1 の設計書の 0.12）: E8（2.3 の 6）・E9（2.3 の 3〜5）・E48（2.4）・E49（2.4）・E50 の尾（2.4）・E54〜E56（0 節と 2.4）・E58（返りの欄の並び。名は残し、`protected_hits` は merge へ移る）・E71（2.3 の 2）。E57 の型つきの成果物は作らない（読み手の report が読まない）。E36（前提の検算が escalate なら人に聞く）は line の最後の承認ノード。消した物: 守りのパスの節 `protected` と `ok` の守りの条件（merge へ。README 13 節）・`prep` の深さで目を省く決め（`run_eyes`。line の深さの表へ）・まとめた役 `eyes-one` の振り分け（r4 の port `coherence` へ）・支度の控え `eyes/prep.json` を返す node が読む形（目ごとの block の出力を受け皿で読む形へ）。

### 2.7 試験（`tests/blocks/eyes/`）

- standalone の筋書き: `fixture.inputs` は `base`・`purpose`・`units` だけ。r1〜r4 と structure の AI の node を台本で差し替え（r4 の輪の本体の script も。README 13 章）、`reached` に `verdict`。全部の目が `pass` で `ok` が真。
- 筋書き（今の `workflows/eyes/fixtures/` の 6 本を写す）: `all-light`（`run: false` → 目は飛び、structure after は走り、`ok` 真）・`one-eye`（`merge: true` → r3 が飛び、`r3` の行が r4 の `coherence` から）・`pass`・`premise`（R2 が前提の検算の道 → `ok` 偽・`premise_check` が在る）・`redesign`・`protected-hit` は merge の筋書きへ移す（守りのパスは merge）。
- 振る舞いの試験（元は今の `tests/workflows/test_eyes.py` と `lib/tests/test_eyeverdict.py` のまとめの部分。README 9.5）: `ok` の決まり（目ごとに 1 つずつ外して偽になる）・受け皿の飛んだ目が `unverifiable` と落ちた筋の訳・「まま R4 を回した」の尾・`run` 偽の行・落ちない。
- 配線の yes/no: r4 が r1・r2 の受け皿に依り `none_failed_min_one_success` を持つ・structure（after）が `when:` を持たない・r3 の `when:` が `merge` を読む・`ok` に `dirty`・`escalate` を使わない。
- 守る keep-essence: 9（R1〜R4。独立設計を作った block は修正案・判定・差分を運ぶ port を持たず、この graph は r2 に独立設計の pointer を渡すだけ）。

## 3 自分で決めた事

- 判定の裏取りを回すかを、line が引いた段ごとの真偽の表から head-depth の段で選ぶ（1.5）。根拠: 段 → 回す物の表は line に 1 つ（形の直し 5）で、段は graph の中で決まる。表を graph に写さず、表を引いた結果を値で受ければ、graph は流れの選びだけを持つ。
- 再審の道を judge の graph に持たせない。根拠: 再審で回るのは diagnose だけで、ほかの 15 の block は再審の道を通らない（今の「目的・世界の解・素材は run で 1 回」）。graph に再審の道を置くと 15 の `when:` に再審を外す句が要る。持ち主の決め `rejudge-cohabit`（再審は判定と同じ block）は diagnose の中で守る。
- 止めの記録 `stop.json` の替わりに、止めの語の順を `verdict` の 1 か所に置く（1.4）。根拠: README 4.3。止めの順は今の `verdict`・`_missing_stage` と同じ。
- 前提の実測を、並行 PR が止めた run で回さない（`when: $parallel-pr.output.stop_reason == ''`）。今は並行 PR の役が諦めても前提の役が走った（止めの控えを見るのは目的の支度から）。根拠: 止めた run では前提の結果を読む判定が回らないので、役の費用だけがかかる。読み手の落ちる能力は無い（止めた run の報告の前提の節が無くなるだけ）。
- 素材の観点の 10 本の `when:` は目的の固定が通ったかだけにする（機能の語で観点を切る道は今も無い）。回す条件は各 block（materials.md の 10 節）。
- 素材の諦めの止めは diagnose が返す `works:material` を読むだけにし、graph の `when:` に置かない。根拠: materials.md の 1.6 が読み手の diagnose に決めを任せ、diagnose の設計書の 1.2 が「判定役を起こさずに `stopped`・`works:material`」と決めた（今の J62「残りの素材で材料を組んだ上で止める」を diagnose の中で続ける）。
- 素材の 10 本の見方を graph で突き合わせない（1.7）。根拠: 同じ `base` を渡し、役が作業ツリーを変えたら各 block が拒むので、見方は同じになる。突き合わせは計算で、graph の持ち物でない。
- eyes の `ok` に直した後の実測の数を入れない（2.4）。根拠: 今の eyes と同じ（E73 の読み手は最後の承認ノードと報告）。
- `run` が偽の時の eyes の `ok` を真にする。根拠: 今の偽は「守りのパスを確かめられなかった」時だけで、その確かめは merge に移った。merge の確かめられない行が最後の承認ノードを開き apply を拒む（merge の設計書の 1.6）ので、閉じた側への倒れ方は残る。
- r2 を structure（after）の後に待たせない。根拠: r2 は直した後の実測を読まない（r1 の設計書の 0.2 の `after` は r1・r3・r4 だけ）。今は全部の目が支度の後に並んだが、支度が無くなり、待つ訳が無い。

### 作る時に決めた事（judge。設計書が黙っていた所と、止めた Archon の振る舞いで決まった所）

- `when:` は飛ばされうる node の出力を読まない。止めた Archon（`a972888a`）は、`when:` が走らなかった node の欄を読むと、その node を落とす（dry-run の実測: 「`$purpose__finish.output.ok` references field 'ok', but node … did not run」）。落ちた node を `with:` で読む verdict も落ちる。だから `diagnose-in` は `when:` を持たずに毎回走り、前提の実測と目的の固定の受け皿から `go`・`purpose`・`constraints` を運び、diagnose の `when:` と `with:` は `diagnose-in` だけを読む（1.3 の 10・11）。設計書の元の形（`diagnose-in` の `when: $purpose.output.ok`・diagnose の `when: $premises… && $purpose…`）は、前提か目的が止めた run で verdict まで落ちた。
- 受け皿（`returned`）と返し（`spec-in`・`diagnose-in`）は落ちない（`ports.run`。読めなければ `got: null` か `ok: false` と訳）。all_done で集める node は `{from, if_skipped: null}` で受けるが、止めた Archon は落ちた作り手を `if_skipped` に落とさない（受け皿の `why` が訳を運ぶ）。`ins` は落ちてよい（`with:` で読む node が無く、後ろは飛ぶだけ）。verdict は graph の入力（`world`）を `ins` でなく自分で読む。
- `spec-in` が落ちた時の止めの語は、仕様を挟む run なら `works:spec`、ほかは `works:request`（落ちる訳は依頼が読めない時だけ）。
- verdict が目的の監査の素材（`purpose-review` の `material.json` の `reply`）か世界の解の行のファイルを読めない時は、まとめを落とさず `report` に 1 行を足し、`purpose_review` は `{}`・`world` は null にする。
- 返らなかった素材の観点の行（`diagnose-in` の `missing`）は、`go` が真（判定まで進んだ）の run だけ `report` に載せる（前の段が止めた run では、素材は回っていないだけ）。`verify_why` は、止めた run は「判定が止まったので回さなかった」、段の表で切った run は「段 <語> では判定の裏取りを回さない（段ごとの表）」、開いた単位が無い run は「開いた単位が無いので回さなかった」、verify が返った run は verify の `reason`。
- `world_state` は、世界の解を回すはずの run（`world` が真で目的が通った）で受け皿が飛べば `{status: failed, reason: 世界の解の段が返らなかった}`、回さなかった run は `skipped`。
- `optional` は 1.2 の自分の宣言に、include した block が返した `optional` の行を `<id>__` の頭を付けて足す（`bare` の行はそのまま。今の line の `collect.absorbed` と同じ読み）。
- コードの置き場: 返しの中身は `src/feed.py`、まとめは `src/verdict.py`、落ちた時の形は標準ライブラリだけの `src/fallback.py`（verdict の script が境の口か lib を読めない時も同じ形を返す。1.6 の `src/verdict.py`・`src/files.py` に 2 本を足した）。段の既定は `lib/headdepth` の `STANDARD`、止めの語 `works:judge`・`works:spec` は `stopby.declare` に diagnose・spec の block と同じ名と意味で足す。
- graph の筋書きは、include した block ごとに入口（`intake`・`scan`・`prep`）と出口（`finish`）の node を台本で差し替え、block の中を飛ばす（1.8 の「AI の node と loop の本体の script を差し替え」から変えた）。訳: dry-run は include の中の loop の本体に include の道を渡さない（README 13 節）ので、block の中の道は block 自身の筋書きが見る。止めた Archon の `workflow test` は使われない台本（`unusedStubs`）を外れにするので、走らない分岐の台本は置かない。spec-on の筋書きは仕様の承認ノードを通らない（承認ノードは spec の block の筋書きが見る）。
- 試験の助け: `tests/blocks/kit.py` の `dry_run_traces` に include する block の名 `included` を足した（graph の筋書きは include 先と同じ木で回す）。`tests/layers/test_block_shape.py` の `ExistingRulesCase` は、graph のフォルダ（include を持つ物）について、今の `workflows/` の同じ名のサブグラフの役を名指す表 `KEEP_CHECKOUT` の行（`("judge", "judge-verify")`）が「工程に無い」と出る行だけを外す（graph は役を持たない。表の行は今の `workflows/judge` の物）。
- 変異の検算の観点 gate-efficacy を judge の graph に include せず、入力 `gates` も持たない。持ち主の決め `gate-efficacy-outside-judge`（2026-10-19）「重い試験は全部まとめてやるし、なんならＣＩに任せて先に進めたい」: 重い確かめは工場の run の中で回さず、まとめて回すか CI に任せる。gate-efficacy の block は pack に残り（`workflows/gate-efficacy/`）、単独の run（まとめて回す時）で使う。block は変えない。
  - diagnose の側: port `materials` は返った観点の `material.json` の配列で、観点ごとの鍵を要らない。無い観点は `materialkit.assemble` が素材の欄 `gate_efficacy` を `{status: not_run, reason: "走っていない（どのノードも返していない）"}` で埋め、材料の `gate_arms` は無い（diagnose の設計書の 5.1 の 4・7）。だから graph は何も足さずに回る。
  - 残る差: 埋まる訳の字が「走っていない」で、持ち主の決めで回さない訳（まとめて回す・CI に任せる）を言わない。`not_run` は止めない語だが、判定役には「確かめていない素材」として見える。訳を言わせるには、diagnose が観点ごとの回さない訳を受ける口（例 port で `{gate_efficacy: {status: not_applicable, reason}}` の埋めを受ける）を持つか、`materialkit.assemble` の既定の訳を変える要る。graph が gate-efficacy の block を回さずに、その block が返すはずの `not_applicable` の行を自分で組んで diagnose に渡すことは、block の持ち物（自分の出力の形）を graph が作ることになるので、しない（どちらの口にするかは diagnose の側で決める。4 節の未確認）。

### 作る時に決めた事（eyes）

- 「まま R4 を回した」の尾は r1 と r2 の行だけに足す（2.4 の「ほかの目」から狭めた）。訳: R4 が待つのは R1・R2 だけ（E8。2.3 の 6）で、R3 は R4 と並んで走るので「R3 が落ちたまま R4 を回した」は事実でない。今の `eyeverdict.collect` も尾を r1 と R2 の比べの行だけに足していた。
- `merge` が真で r4 の出力に `coherence` の行が無い（r4 が返らなかった・行が壊れた）時は、`r3` を `unverifiable`・`eyekit.fell_text("r4", "まとめた R3 の行（coherence）が無い")` にする。
- r1・r3・r4 の `after` は返し `after-in`（落ちない。structure after の `after` の pointer か `""`）から受ける。verdict は `run`・`merge`・`skip_why` を `ins` でなく graph の入力から読む（`ins` は落ちうるので `with:` で読まない。judge と同じ）。`skip_why` が空なら行は「訳が渡されていない」。
- `after_ok` は structure after の受け皿の `ok`。偽なら `report` に「直した後の構造の実測が無い（<訳>）」の 1 行。`sections` は `merge` の run で r3 の節を置かない。`optional` は structure after が返した `optional` を `structure-after__` の頭で足す。
- r4 の `trigger_rule` は 2.3 の 6 のまま `none_failed_min_one_success`（r1 の設計書の 0.11 は `all_done` と書く。依る node はどれも落ちない受け皿と返しなので、どちらでも r1・r2 が落ちた run で回る。`none_failed_min_one_success` は `after-in` が飛んだ run〔`ins` が落ちた〕で回らない）。
- 形のファイル（2.2）の名: `eyes-fixes`・`eyes-scalars`・`eyes-design`・`eyes-design-premises`・`eyes-outcomes`・`eyes-tdd`・`eyes-asked`・`eyes-declared`・`eyes-intent`（中身は受ける block の形と同じ）。
- 筋書きは judge と同じく、include した block の入口（structure は `measure`、r1〜r4 は `intake`）と出口（`finish`）を台本で差し替える。

## 4 未確認

2 波目の設計書（diagnose・r1〜r4・verify）は、この設計書を書き終える前に置かれたので、配線はその 1.2 と 1.6 に合わせた（1.3 の 10・11、2.2・2.3）。残る物:

- r1 の設計書の 0.11 の「目の判定の行が在る時の『まま R4 を回した』の尾」は graph に置いた（2.4）。r4 の出力に `coherence` の行が無い run（`merge` が偽）で `r3` が返らなかった時は、0.9 の `fell_text` で `unverifiable` にする。
- verify の出力 `stop_reason` と、開いた単位が 2 つ未満で回さなかった時の `reason`（`verify_why` に写す）は、verify の設計書の 1.2 の形のまま読む。

作った時に残った物:


- gate-efficacy を回さない run の素材の欄 `gate_efficacy` の訳（3 節の持ち主の決め 2026-10-19）: 今は diagnose の埋めの「走っていない」になる。回さない訳を判定役に見せるかと、その口（diagnose の port か `materialkit.assemble`）は diagnose の側で決める。

ほか:

- include した graph の中で include を持つ（line → judge の graph → block）形を、止めた Archon の include の展開が受けるか（README 8.7 の sdlc の `deliver` の形が手本。2 段の include で node の id が `judge__<id>__<node>` になり、place が `judge/<id>/` になること）。
- 受け皿を include ごとに置くと judge の graph の node が 17 増える。Archon の YAML の錨で本体を 1 か所にする（今の line と同じ）が、筋書きの差し替えの数も増える。
- 素材の 11 本の pointer の配列を、script の出力の欄の値（JSON の配列）として include の `with:` で渡し、diagnose の `json` の form の port がそのまま読めるか（埋め P2 の「include の `with:` は値を JSON の字で運ぶ」の形。README 4.2）。
