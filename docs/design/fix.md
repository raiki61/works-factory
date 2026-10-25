# block の設計書: fix（修正）

- 何の話か: 承認済みの修正案を項目ごとに直す観点「修正」を、単独で呼べる block `workflows/fix/` にする設計。直しの組ごとに自分を子の run として起こし（`workflow:` と `fan_out:`）、組の子の中で単位ごとの TDD の loop と修正役を回し、親で組を合わせ（合わせ役）、食い違いの申し出を読むだけの裁定役が裁き、裁定の後に直し直す。範囲の相談（修正案の側への問い）もこの block の中に在る。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。
- 決めたこと: 今の `workflows/fix/` の node のうち、差分の審査・レンズ・手直し（`delta-cut`〜`refix2-loop`）を delta-review と lens の block に渡し、残りを同じ並びの block にする。始めの記録の代わりに port で受け、run の頭の深さ（`depth`・`head_depth`・`depth_record`）と fix の中の深さの上げ直し（`fixboard.redepth`）を外して、port `skip_rerun` 1 つにする。AI の node は 9 つ（修正役・裁定の後の修正役・相談の答え 2・TDD の役 2・裁定役・合わせ役 2）で、指示の本文は block の 5 つの断片（`fixer`・`consult`・`tdd`・`clash`・`brief`）と裁定役の md 1 本と、書く役の決まりの共通の断片 `writer-rules`（delta-review の手直しの役と共に使う）に寄せる。lib の 12 モジュールを `src/` へ写す（どの関数をどこへ写すかは 1.5）。振る舞いは変えない。変える所は 13 節に名指した物だけ。
- 読む人: この block を作る実装の役（この設計書だけで作れるように書いた）。README 11.1 の 3 波目（delta-review と同時。写す範囲は 1.5.3 で割った）。
- 持ち主に求めること: なし。README・持ち主の決め・今のコードの事実で 1 つに決まらなかった物は 16 節（未確認）に置いた。作り直しの中で見つけた今の工場の不具合（相談の答えの役が修正役の会話の分かれとして起きる・振り分けの段の書き込みが戻らない など）は直さず 13.3 に並べた（振る舞いを変えるので作り直しの外。structure の設計書の 11 節の 8 と同じ扱い）。

この文書の語は README の頭の物を使う（block・graph・port・place・prep・accept・pointer と、Archon の YAML の鍵、form の書き方）。keep-essence の番号は README の 10 節、F の番号は今の能力の棚卸し `docs/plans/2026-10-13-capabilities/fix.md` の行（組み込みで消える表なので、この設計書の 12 節が対応を持つ）。ほかに:

- line: 工場のメイングラフ（README 8.7 の graph。設計書は組み込みの時に `docs/design/line.md` に書く）。この block を include し、始めの記録（run の頭の記録）の値を port で配り、承認ノード・深さの表・往復を持つ。
- 組み込み: README 11.3 の、全部の block がそろった後の 1 本の PR。line を新しい block に切り替え、古いサブグラフ `workflows/` と、block へ写した元の `lib/` のモジュールと、能力の棚卸しの表を消す。「組み込みで消す」「組み込みで割る」はこの PR でする事。
- 止めた Archon: `factory/pack.json` が止めた版 `a972888a` の Archon の源（README 13 章。取り置きは `~/.cache/works-factory/archon/a972888a…/`）。今の工場が走る版で、行の番号はこの源の物。
- 今の工場・元の works: 「今の」はこのリポジトリの作り直し前の `workflows/fix/` と `lib/` の振る舞い（作り直しで写す元）。「元の works」は工場の移植元 `~/src/claude-plugins/works/`（README の頭の語。参照するだけ）。12 節の「今の works との比べ」は今の工場との比べ。
- 単位（unit）: 判定（diagnose の出力）が切った根本の欠陥 1 つ。key は判定の `units[].key` の字。判定は単位ごとに重さ（[block] は必ず直す欠陥・[suggest] は勧め）と扱い（do-now は今直す）を付ける。
- 直す義務の単位: 開いた単位（[block] と、判定が do-now とした [suggest]）から、人に諮っていて答えの無い問い（fork・escalate）の出どころと、その問いに頼る単位（depends）と、直さない裁定（人に回す ask_human・案の項目の直しを待つ fix_plan_item。5 節）を受けた単位を外し、人が答えて戻した単位を足した物（今の `fixboard.fix_duty`）。無人の run では、判定が推しを付けた fork と保留（held）を推しで答えたと数える（port `unattended`）。
- 項目: 承認済みの修正案の 1 項目。brief はその項目を機械が切り出して凍らせたファイル（`brief-<n>.md`）。
- 組: 項目を共にする単位・範囲が交わる項目の単位をまとめた物（今の `fixboard.fix_groups`）。組ごとに子の run が 1 つ起きる。
- 全体の形（`mode` が `whole`）: graph から include された親。組を作って子を起こし、戻し・合わせ・裁定・後始末をする。
- 組の形（`mode` が `group`）: 組 1 つを直す子の run。単独の run でもある。
- 段: 1 回目の修正の段（line が `fix` として include）と、案の直しの後の 2 回目の修正の段（line が別の id で include。前の段の申し出と輪の状態を port `prior` で受ける）。
- 役の名: 修正役（fixer）・裁定の後の修正役（fix-ruled）・相談の答えの役（consult-answer・ruled-consult-answer）・TDD の役（tdd・tdd-new）・裁定役（ruler）・合わせ役（clash-fix・裁定の後の合わせ役 clash-ruled）。英語の md では "the fixer"・"the scope answerer"・"the TDD role"・"the ruler"・"the merger"。
- 下請け: 修正役が Agent の道具で起こす実装役（implementer）と審査役（task-reviewer）。Archon の node ではない。
- 例の run: 1 回目の修正の段の親は本物の run `d31781b6-ccb9-485f-9432-7e12a835cd49`、その組の子は `c5c3642f-ff02-4f62-b4a7-b67006f544ad`（どちらも対象 raiki61/works-factory、`par: false`、実行器なし、範囲の相談 1 往復・受け付けの拒否 1 回・裁定 2 件・裁定の後の修正と相談を通った）。TDD の loop が回った組の子は本物の run `1ba3f998-47d5-4616-a5ba-c4557fa385c2`（親 `821e6fab-…`。対象は <対象>。名は書かない）。合わせ役は記録の在るどの run でも走っていない（`clash-*.md` の指示が 1 本も無い）。置き場は `~/.local/state/works-factory/targets/<target>/archon-home/workspaces/<owner>/<repo>/artifacts/runs/<run>/fix/fix/`（以下 `<place>`）。

## 1 block の全体

### 1.1 役

承認済みの修正案（無ければ判定）の直す義務の単位を、組に分けて組ごとに子の run で直す。組の子は、実行器（JUnit を書く TDD の実行器）が在れば単位ごとに赤から緑まで TDD の loop を回し（赤と緑は機械が JUnit の結末で判じる）、loop で直せなかった単位を修正役が直す。どちらの役も、受け付けが書き込みの出どころ・凍ったテスト・範囲・当たる試験・閉鎖の数え直し・書いた指し・事前審査への答えを照らし、3 回拒まれた単位だけを戻して諦める。範囲の外が要る時は修正案の側に相談し、緑にするために曲げるしかない時は食い違いの申し出を出す。親は組の差分を順に当て、当てて赤になった・字でぶつかった組を合わせ役が直し、申し出を読むだけの裁定役が持ち主の決まりで裁き、直す裁定の後に直し直す。最後に、役が残した生成物を消し、申告したファイルが本当に変わったかを確かめ、単位ごとの記録と差分を返す。

差分の審査・レンズ・手直し（今の `delta-cut`〜`refix2-loop`）はこの block に無い。深さを上げ直すか・差分の審査を回すかは line が決める（README の 1.2 の D・形の直し 5）。

### 1.2 port

入力（YAML の `inputs:`。どれも既定値を持ち、形ごとに要る物は intake が確かめる。1.3 の 1）:

- `mode`: `choice(whole|group): 形。whole は graph から include された親（組ごとに自分を子の run として起こす。単独の run では Archon が先祖と同じ名の子を拒むので回らない）。group は組 1 つを直す（単独の run・子の run）`。既定 `group`。
- `routes`: `choice(auto|plan): 単位ごとの道の決め方。auto は TDD の役が振り分ける（承認済みの案が tdd の単位は tdd に縛る）。plan は承認済みの案の route をそのまま使い、振り分けの段の AI を起こさない（承認済みの案の項目〔行〕のうち、その単位を持つ行のどれかが route: tdd なら tdd、ほかは direct で訳は行の route_why）。tdd の単位が 0 なら TDD のループを回さない`。既定 `auto`。値は `values.json` で組の子へ運ぶ。plan の時、`tdd.start` は約束（`plan_contract`）と行の `route_why`（`plan_route_whys`）で単位を振り、test の段から輪を始める。tdd の単位が無ければ元の結末（輪の頭で試験の一式を 1 回走らせて取る、直す前の結果。17 節）も取らずに輪を回さない（[spec-driven.md](spec-driven.md) の 7 章の 1）。
- `judgment`: `json(shared:judgment.schema.json): 判定（units・questions・precedents・framing などを持つ object）。whole と、out_dir の無い group では必須。out_dir の在る group（子の run）は親の写しを読むので空でよい`。既定 `""`。
- `plan`: `json(shared:plan-fields.schema.json): 承認済みの修正案の欄の控え {fields}（今の plan-fields.json。凍結の印を付けて置く）。空は修正案の無い run`。既定 `""`。
- `fix_plan`: `json(shared:fix-plan.schema.json): 承認済みの修正案の返り（項目の並びを持つ object。項目の unit_keys が承認済みの項目の出どころ）。空は修正案の無い run`。既定 `""`。
- `answer_ties`: `json(shared:answer-ties.schema.json): 依頼の答えを判定の問い・単位に結んだ行。null は結びが無い（字の一致だけ）`。既定 `null`。
- `materials`: `json(shared:materials-state.schema.json): 判定の素材の状態（素材の名 → {status, …}）。null は無い`。既定 `null`。
- `ripple`: `json(shared:ripple.schema.json): 波及の一覧（承認済みの修正案の項目が変える名の呼び出し元と試験）。空は無い`。既定 `""`。
- `skip_rerun`: `json(skip-rerun.schema.json): 緑の後の試験の走らせ直し（TDD の loop の test_cmd の関門と、組を当てた後の test_cmd）を省く単位の key の配列（line が深さの表から引く。今の depth.omits の軽量の単位）。空の配列は省かない`。既定 `[]`。
- `answers`: `json(fix-answers.schema.json): 修正の前の承認ノードの答え {decision, text, asked}。null は聞いていない`。既定 `null`。
- `request_answers`: `json(fix-request-answers.schema.json): 依頼のファイルが先に持っていた問いへの答えの行（今の始めの記録の answers）。空の配列は無い`。既定 `[]`。
- `unattended`: `flag: 無人の run か（判定の推しつきの fork・held を答えとして数える。今の gatepolicy.unattended_of）`。既定 `false`。
- `plan_review`: `json(shared:plan-review-reply.schema.json): 事前審査の返答（穴の行 faces と、まとめて小さく閉じる別案の行 shrink）。修正役は返答の欄 plan_faces で、その穴と別案の key ごとに absorbed〔直しで塞いだ〕か declared〔塞がずに申し出た〕を答える。null は事前審査の無い run`。既定 `null`。
- `prior`: `json(shared:carry.schema.json): 前の修正の段の申し送り（前の段の出力 carry の先 {conflicts, loops}）。2 回目の修正の段だけに渡す。null は 1 回目の段`。既定 `null`。
- `notes`: `text: 機械の申し送りの文（案の直しの後の 2 回目の修正の段だけ。採った項目の事前審査の穴のうち人に聞く種類でない物）。修正役と TDD の役の notes に足す。空は無い`。既定 `""`。
- `only_items`: `json(only-items.schema.json): 2 回目の修正の段で直す修正案の項目の番号の配列。空の配列は直す義務の単位の全部`。既定 `[]`。
- `baseline`: `json(lib:baseline.schema.json): 直す前の結末（試験の関門の base の出力 baseline の先）。空は実行器の無い run`。既定 `""`。
- `test_cmd`: `text: 人が渡したテストのコマンド（対象の根で走らせる 1 行）。空は無い`。既定 `""`。
- `tdd_suite`: `text: TDD の実行器のパス（第 1 引数の書き先に JUnit XML を書く物）。空は TDD の loop を回さない`。既定 `""`。
- `reuse_dir`: `text: 同じ run の中の試験の結果の控えの置き場の絶対パス。空は使い回さない`。既定 `""`。
- `reuse_key`: `text: 控えを引く時に照らす run の名。空はこの run の id`。既定 `""`。
- `user_env_dir`: `text: 利用者の HOME・XDG に戻して起こした印を置く置き場の絶対パス。空は置き場が無い（戻す run では止まる）`。既定 `""`。
- `policy`: `file: 人の方針の文書（line が固めた写し）。空は無い`。既定 `""`。
- `request`: `json(shared:request.schema.json): 人の修正依頼のファイル（役が Read し、裁定役と修正役が <絶対パス>:<行> で名指す）。空は無い`。既定 `""`。
- `parallel`: `flag: 組を子の run で並べてよいか（今の始めの記録の features_cut に fix_lanes・tdd_lanes が無い）。偽なら 1 組ずつ親の作業ツリーで回す`。既定 `true`。
- `group`: `json(group.schema.json): 組 1 つ {group_id, unit_ids, items}（group の時。親の fan_out が渡す）`。既定 `""`。
- `from_tree`: `text: 親の作業ツリーの姿の木の sha（group の時。並べる子だけ）。空は親の作業ツリーをそのまま使う`。既定 `""`。
- `out_dir`: `text: 子が組の結果を書く、親の place の中の絶対パス（group の時）。空は自分の place の groups/ に書く（単独の run）`。既定 `""`。
- `lang`: `text: 人に見せる欄（各役の md が名指す欄）の言語。空は依頼の言語`。既定 `""`。
- `excluded`: `json(shared:excluded.schema.json): 並行 PR の確かめが外した hunk（parallel-pr の出力 excluded の先 {excluded: [{pr, file, start, end, why, text, sha256}]} か、その行の配列。行の範囲は並行 PR の確かめが走った時の作業ツリーの行で、`text`・`sha256` はその行の中身の錨）。修正の受け付けが、修正の段の始めの木からの変更がこの範囲に触れた返答を拒み、組の終わりと全体の変更の確かめが、始めの木から今への変更を 1 度照らす（8.1）。null は外した hunk が無い`。既定 `null`。line が 1 回目と 2 回目の修正の段に渡す（integration の設計書の 4.1-5・line の設計書の 8.2 の決め）。`values.json` の欄 `excluded` に置き、組の子は親の物を写す。

形（形の照らしが読む語 `lib/graphloops/engine/schema.py` の KNOWN_KEYWORDS だけで書き、中身を宣言する。object には properties か patternProperties、array には items を書く。中身を宣言しない形は口 `workflows/.shared/ports.py` の `open_shapes` が拒む。#851）: 2 つ以上の block と graph が読む形は `.shared/schemas/` の 1 つを名指す（judgment・plan-fields・fix-plan・answer-ties・materials-state・plan-review-reply・carry・excluded・ripple・request）。直す前の結末は lib の住処の `lib:baseline.schema.json`。この block の `schemas/` に残すのは、この block だけが読む `skip-rerun`・`fix-answers` `{decision, text, asked}`・`fix-request-answers`（`{question, text}` の行）・`only-items`（整数の配列）・`group` の 5 本。形の崩れた excluded の行は黙って捨てずに入口で `ok: false`（`start` が `end` より大きい行も拒む）。空の字 `""` と `null` は `ports.json` に渡さず「渡されていない」と読む（intake の決まり）。

出力（`returns: finish`、`outcome_field: ok`）。今の `fix` の欄のうち fix の事実の物を名のまま保ち（line の受け皿・最後の承認ノード・eyes・merge・報告が今の名で読む）、差分の審査とレンズの欄を外し、delta-review と line が要る欄を足す:

- `ok`: boolean。組の形: 組の結果を書いた。全体の形: 戻しの記録（`join.json`）が在り、変更の確かめが通り、当たったままの組が無い（今の `done` から差分の審査の `pass` を外した物）。
- `reason`: 日本語の 1 行。ok でない訳（落ちた段・読めない port・変更の確かめの訳）。
- `units`: `[{unit_id, group_id, status (fixed|given_up|not_done), reason}]`（今のまま）。
- `groups`: `[{group_id, unit_ids, returned, reason, backed_out?, unrestored?, old_red?, uncompared?, test_cmd_notes?, clash?}]`（今のまま。`clash` は `{outcome (repaired|parked), requests, patch}`。`old_red` は確かめ直しで前から同じ形で赤だったので戻す理由にしなかった名指しの文の並びで、確かめ直しを通って親の作業ツリーに当てたままにした組の行にだけ在る。18 節。`uncompared` は確かめ直しで直す前の版と比べられなかったので戻す理由にしなかった赤の鍵 `classname::name` の並びで、同じく当てたままにした組の行にだけ在る。報告が人に聞く。20 節。`test_cmd` の行〔外した木で走らせた結果が取れない〕も入る。21 節。`test_cmd_notes` は確かめ直しの `test_cmd` の赤を、組を外した木でも赤（前から赤か環境）か走らせ直しで緑（揺れ）と見て戻す理由にしなかった文の並びで、同じく当てたままにした組の行にだけ在る。`report` に 1 件 1 行で出す。21 節）。
- `conflicts`: pointer（`conflicts.json`）か null。
- `carry`: pointer（`carry.json`。次の修正の段の port `prior` に渡す申し出と輪の状態の束。1.4）か null（組の形）。
- `replan_items`: 字の配列。fix_plan_item の裁定が誤りとした項目の番号。
- `objection`: 字。修正役の異議（rejudge_requested）と rejudge の裁定の文をつないだ物。
- `diff`: pointer（`fix.diff`。修正前の HEAD から今の作業ツリーへの累積の差分。`.archon/` を除く）。差分が無ければ空のファイル（`fix-diff-none.txt`）を指す。
- `start_tree`: 字。この段の始めの木の sha（delta-review が「修正だけの差分」を切る根。今の `groups.json` の `start_tree`）。組の形も自分の始めの木。
- `reply`: pointer（`fix-reply.json`。戻せた組の受けた返答の changes・not_done・plan_faces を合わせた物。今の `fixboard.group_fix_reply`）か null（直す返答が 1 つも無い）。
- `ruled_reply`: pointer（`fix-ruled-reply.json`）か null。
- `scope`: pointer（`scope.json`。`{plan_items, ruled_paths, agreed}`。今の `fixboard.scope_brief`。delta-review が手直しの範囲を照らす）か null（修正案の無い run）。
- `checked`: `{ok, reason}`。変更の確かめ（今の `assert-changed.json`）。組の形は `{ok: true, reason: ""}`。
- `handoff_titles`（#812）: `{handoffs の行: 修正役が同じ `breaks` に書いた `accepted_title`}`。題の無い・空白だけの行は入れない。報告の頭が「人が決めること」の題に使う（line の facts が `asks[].title` に写す）。
- `allowed_test_changes`・`changed`・`x_scalars`・`handoffs`・`mismatched`・`plan_declared`・`stop_reason`・`item_claims`・`tdd_refused`: 今のまま（`stop_reason` は当たったままの組が在れば `stopby.UNRESTORED`、ほかは `""`）。
- `allowed_tests`・`accept_trace`・`closure`・`tdd_unit`: pointer（`type: ["object","null"]`。description に指す先の形 `json(shared:allowed-tests.schema.json)`・`json(shared:accept-trace.schema.json)`・`json(shared:closure.schema.json)`・`json(shared:tdd-units.schema.json)` を書き、finish は `ports.pointer(path, <その form>)` で中身を照らしてから指す。#851）。README 8.3 の `permits` は `allowed_tests` のこと。
- `tdd`: 配列。この段の組ごとの TDD の記録（`tdd-unit.json` の中身 `[{group_id, ran, reason, suite, reused, units}]` を値で。組の形は自分の組の 1 行）。r2 の port `tdd`（段ごとの記録の配列）に line が段の順に並べて渡す（今の `fixbeside.tdd` が pointer の先を読んでいた所。r2 の設計書の 10 節の 1）。
- `frozen`: pointer（`frozen.json`。この段の輪ごとの凍ったテストのファイルの hash `{loops: [{state, frozen, frozen_tree}]}`）か null（輪が回っていない）。README 8.3 の `frozen`。今は読み手が無く、輪の状態の中にだけ在った（13.1 の 9）。
- `removed`: pointer（`json(shared:removed.schema.json)`）の配列か null（clean が消したパスの控え）。ほかの pointer の欄も同じく description に form を書く: `conflicts` は `json(lib:conflicts.schema.json)`、`carry` は `json(shared:carry.schema.json)`、`reply`・`ruled_reply` は `json(shared:fix-reply.schema.json)`、`scope` は `json(shared:scope-fields.schema.json)`、`frozen` は `json(shared:frozen.schema.json)`、`diff` は `file`。落ちない出口（finish の fallback）は pointer の dict を手で組まず、place に置いた控えのファイル（allowed-tests.json・accept-trace.json）が形に合わなければその欄を null にし、指せない理由の文を `tdd_refused.unread`（読めなかった物の文の並び）に載せる。
- `freeze_off`: 字の配列。TDD の loop を回していない組ごとに「テストの凍結が効いていない」の 1 行（今の `report.freeze_lines`。報告の冒頭に載る行なので `report` と分ける）。
- `report`: 日本語の行の配列（11 節）。

今との違い（欄）: 外した欄は `done`（→ `ok`）・`delta_review`・`delta_holes`・`lenses`（delta-review と lens の出力へ）・`optional`（落ちてよい node が無くなった。レンズが出た）。`units` の読み口 `fixbeside.read`・`records` は組み込みで line の `src/` に移る（README 9.1 で `fixbeside` は DELETE）。

### 1.3 node の並び（`workflows/fix/works-factory-fix.yaml`）

頭の `description` は「修正の block（docs/design/fix.md）。…」の 1 段落（今の頭の 8 行の中身から差分の審査を外した物）。script の node はどれも `runtime: uv`。AI の node の起こし方は 2 節〜6 節に書く（今の錨 `&fix_launch`・`&tdd_launch`・`&consult_launch`・`&clash_launch` と YAML の `ruler` の鍵を字のまま写し、`prompt:` だけを `"$<prep>.output.prompt"` にする）。

両方の形:

1. `intake`（script `intake.py`・`mutates_checkout: false`）: 全部の port を読み、形ごとの必須を確かめ（下）、place の中のこの block の名の付いたファイルを消さずに（place は作るだけ）`intake.json` と `values.json`（1.4）を書く。返り `{ok, whole, reason}`。読めない port は落ちずに `ok: false` と「入力 <名>: …」の理由（world の 9.1 の 3）。今の `route`（入力 `mode` の読み分け）を兼ねる。

全体の形（`when` に `$intake.output.whole == true && $intake.output.ok == true` を含む）:

2. `prep`（script `prep.py`。`depends_on: [intake]`）: 今の `prep` と同じ順で入力の写しを place に置き、組を作る（7 節）。返り `{groups, count, par, start_tree, out_dir}`（今のまま）。
3. `groups-par`（`workflow: works-factory-fix`。`depends_on: [prep]`・`when: "$prep.output.par == true"`・`isolation: worktree`・`fan_out: {items: $prep.output.groups, as: group, max_parallel: 5, join: all_success}`・`with: {mode: group, from_tree: $prep.output.start_tree, out_dir: $prep.output.out_dir}`）。今の注記（`all_success` の訳 #576・`max_parallel` は Archon の既定を見せる）を YAML のコメントに残す。
4. `groups-seq`（同じ。`when: "$prep.output.par == false"`・`isolation` 無し・`max_parallel: 1`・`with: {mode: group, from_tree: "", out_dir: $prep.output.out_dir}`）。
   - 子の `with:` は 3 つだけにする（今は `start`・`judgment` など 11 個を渡していたが、out_dir の在る子はどれも読まず親の place から写していた。1.2 の `judgment` の説明）。子は intake で `out_dir` の親の `values.json` を写す（7 節の `group_start.py`）。
5. `join`（script `join.py`。`depends_on: [intake, groups-par, groups-seq]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.whole == true"`）: 今のまま（7 節）。返り `{groups, returned}`。
6. `clash-loop`（`depends_on: [join]`・`when: "$prep.output.par == true"`・`loop_group: {max_iterations: 9, fresh_context: true, until_bash: done=$clash-accept.output.done; test "$done" = true}`）: `clash-prep`（script `clash_prep.py`・`with: {pass: first}`）→ `clash-fix`（AI。6 節）→ `clash-accept`（script `clash_accept.py`・`depends_on: [clash-prep, clash-fix]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$clash-fix.output", if_skipped: null}, iteration: $clash-prep.output.iteration, pass: first, limit: 9}`）。
7. `conflict-check`（script `conflict_check.py`。`depends_on: [join, clash-loop]`・`trigger_rule: none_failed_min_one_success`・`mutates_checkout: false`）: 返り `{go, count}`。
8. `rule-loop`（`depends_on: [conflict-check]`・`when: "$conflict-check.output.go == true"`・`loop_group: {max_iterations: 3, fresh_context: false, until_bash: done=$rule-accept.output.done; test "$done" = true}`）: `rule-prep`（script `rule_prep.py`）→ `ruler`（AI。5 節）→ `rule-accept`（script `rule_accept.py`・`with: {status_guarded: true, reply: $ruler.output}`）。
9. `clash-ruled-loop`（`depends_on: [conflict-check, rule-loop]`・`when: "$conflict-check.output.go == true"`・6 と同じ形で `pass: ruled`・node は `clash-ruled-prep`・`clash-ruled`・`clash-ruled-accept`）。
10. `fix-ruled-loop`（`depends_on: [conflict-check, rule-loop, clash-ruled-loop]`・`when: "$conflict-check.output.go == true"`・`loop_group: {max_iterations: 12, fresh_context: false, until_bash: done=$fix-ruled-accept.output.done; test "$done" = true}`）: `fix-ruled-prep`（script `fix_ruled_prep.py`）→ `fix-ruled`（AI。2 節）→ `ruled-consult-check`（script `consult_check.py`・`with: {reply: $fix-ruled.output, pass: ruled}`）→ `ruled-consult-ask`（`depends_on: [ruled-consult-check]`・`when: "$ruled-consult-check.output.go == true"`・`loop_group: {max_iterations: 1, fresh_context: true, until_bash: "true"}`。本体は `ruled-consult-answer`〔AI。3 節〕1 つだけ。訳は 13.3 の 1）→ `ruled-consult-accept`（script `consult_accept.py`・`depends_on: [ruled-consult-check, ruled-consult-ask]`・`trigger_rule: none_failed_min_one_success`・`with: {answer: {from: "$ruled-consult-ask.output", if_skipped: null}, pass: ruled}`）→ `fix-ruled-accept`（script `fix_ruled_accept.py`・`depends_on: [fix-ruled-prep, ruled-consult-accept]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$fix-ruled.output", if_skipped: null}, consulted: {from: "$ruled-consult-accept.output.consulted", if_skipped: false}}`）。
11. `clean`（script `clean.py`。`depends_on: [intake, clash-loop, conflict-check, rule-loop, clash-ruled-loop, fix-ruled-loop]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.whole == true"`）。
12. `assert-changed`（script `assert_changed.py`。`depends_on: [intake, clean]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.whole == true"`・`mutates_checkout: false`）。

組の形（`when` に `$intake.output.whole == false && $intake.output.ok == true` を含む）:

13. `group-start`（script `group_start.py`。`depends_on: [intake]`）: 返り `{tdd, units, reason}`（今のまま）。
14. `tdd-loop`（`depends_on: [group-start]`・`when: "$group-start.output.tdd == true"`・`loop_group: {max_iterations: 40, fresh_context: false, until_bash: done=$tdd-step.output.done; test "$done" = true}`）: `tdd-prep`（script `tdd_prep.py`。返り `{prompt, go, new_unit}`）→ `tdd`（AI。`when: "$tdd-prep.output.go == true && $tdd-prep.output.new_unit == false"`）→ `tdd-new`（AI。`depends_on: [tdd-prep, tdd]`・`trigger_rule: none_failed_min_one_success`・`when: "… new_unit == true"`・`context: fresh`）→ `tdd-step`（script `tdd_step.py`・`depends_on: [tdd-prep, tdd, tdd-new]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$tdd.output", if_skipped: null}, reply_new: {from: "$tdd-new.output", if_skipped: null}}`）。tdd-new を tdd の後ろの層に置く訳（同じ層だと Archon が並んだ層として会話を切る）を YAML のコメントに残す。
15. `fix-loop`（`depends_on: [group-start, tdd-loop]`・`trigger_rule: none_failed_min_one_success`・`loop_group: {max_iterations: 12, fresh_context: false, until_bash: done=$fix-accept.output.done; test "$done" = true}`）: `fix-prep`（script `fix_prep.py`。返り `{prompt, go, iteration}`）→ `fixer`（AI。`when: "$fix-prep.output.go == true"`）→ `consult-check`（`with: {reply: $fixer.output, pass: first}`）→ `consult-ask`（10 の `ruled-consult-ask` と同じ形。本体は `consult-answer`〔AI〕1 つだけ）→ `consult-accept`（`pass: first`・`answer` は `$consult-ask.output`）→ `fix-accept`（10 と同じ形で `fixer`・`consult-accept` を受ける）。
16. `group-end`（script `group_end.py`。`depends_on: [group-start, tdd-loop, fix-loop]`・`trigger_rule: none_failed_min_one_success`・`mutates_checkout: false`）: 返り `{result_file}`。

両方の形の終わり:

17. `nodes-ok`（`bash: "true"`・`trigger_rule: none_failed_min_one_success`・`mutates_checkout: false`・`when` 無し）: `finish` と `fix-reads` のほかの全部の node（loop の node を含む）に `depends_on` で結ぶ。どの node かが落ちた run で飛び、block の出口で落ちを見せる柵（今のまま。訳は今の YAML の注記）。
18. `fix-reads`（script `fix_reads.py`。`depends_on: [fix-loop, fix-ruled-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 読んだ証拠（7 節）。落ちない。
19. `finish`（script `finish.py`。`depends_on:` は intake と 2〜16 の全部と `fix-reads`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を組む（今の `collect.py` の後継。7 節）。落ちない。

loop の中の会話（README 13 章の決め・今の振る舞いのまま）: `rule-loop`・`fix-ruled-loop`・`tdd-loop`・`fix-loop` は `fresh_context: false` で、2 周目からは前の周の最後の会話を次の周の AI の node が継ぐ（1 周目はいつも新しい会話。止めた Archon の `dag-executor.ts:4830`）。どの loop にも、継ぐ役の直前に 2 つ以上の node の層は無い（どれも 1 本の鎖）。`clash-loop`・`clash-ruled-loop` は `fresh_context: true`。相談の答えの役は、修正の輪の本体の中の 1 周の輪（`consult-ask`・`ruled-consult-ask`）の中で新しい会話で起き、次の周の修正役は前の周の修正役の会話を継ぐ（13.3 の 1。#833）。

今との違い（node）: 外した node は `route`（intake が兼ねる）・`tdd-unit`（型つきの成果物 `tdd-unit` の読み手 `runreport` は report の `sections` に替わり、r2 は出力 `tdd` の値を読むので、`tdd-unit.json` は finish が書く）・`delta-cut`・`lens-prep`・`lens`・`lens-reply`・`lens-collect`・`delta-loop`・`refix-loop`・`review2-loop`・`refix2-loop`（delta-review と lens の block へ）。返す node の id は `fix` から `finish` にした（ほかの block と同じ。line は include の id で読むので字は動かない）。

### 1.4 place のファイル

`ports.place()`（単独の run と組の子の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/<include の id>/`。今の `fix/fix/` と `fix/refix-run/`）の下に、今と同じ名で書く。名は `src/files.py` だけが持つ（今の `fixnames`・`fixbeside` の名の住処と、`fixboard`・`tddloop`・`consult` などの名の定数の写しを 1 つにする）。

- 入口: `intake.json`（port の値）・`values.json`（今の始めの記録の写し `r1/start.json` の代わり。lib の `conflict` は値で受けるので `r1/start.json` は置かない。`{tdd_suite, test_cmd, reuse_key, reuse_dir, user_env_dir, lang, policy, request_file, answers, unattended, parallel, skip_rerun, excluded}`。`src/runvals.py` だけが読み書きする。組の子は親の物を写す）。
- 入力の写し（今のまま）: `judgment.json`・`judge-ties.json`・`judge-materials.json`・`plan-fields.json`（と凍結の印）・`fix-plan-reply.json`・`p2.plan_review.json`・`ripple.json`・`answers.json`・`only-items.json`・`baseline.json`・`base-rev.json`・`human-notes.md`・`fix-ignored-before.json`。今の `units.json`・`depth.json`・`head-depth.json`・`judge-depth-head.json`・`depth-raised.json` は書かない（読み手が無い・深さは port `skip_rerun` に替わる。13.1 の 2）。
- 組: `groups.json`・`groups/<group_id>/group-start.json`・`groups/<group_id>/result.json`・`join.json`・`join/<group_id>.diff`・`clash.json`・`clash-brief-<gid>.json`・`clash-turns-<pass>.json`。
- TDD の loop: `tdd-start.json`・`tdd-<k>/state.json`・`tdd-<k>/summary.md`・`tdd-<k>/suite-<n>.log`・`tdd-<k>/junit-<n>.xml`・`tdd-<k>/test-cmd-0.log`・`tdd-step-reject-<n>.md`・`tdd-prompt-<n>.md`・`tdd-new-prompt-<n>.md`（今の `tdd-<k>/next.md` と `next.delivered.json` の代わり。渡した証拠の種類の控えは `tdd-delivered.json`）。
- 修正の loop: `fix-head.json`・`skip-before.json`・`briefs.json`・`brief-<n>.md`・`seat-briefs.md`・`g1-impl-<n>.md`・`g1-review-<n>.md`・`libdocs.json`・`libdocs/…`・`consult.json`・`consult-<pass>.json`・`consult-<pass>-<turn>-ask.md`・`consult-<pass>-<turn>.md`・`draft-reply.json`・`fixer-prompt-<n>.md`・`fixer-delivered.json`（今の `prompt-p3.fix.md`・`prompt-p3.fix.delivered.json`・`consult-first-<turn>-resume.md`・`consult-first-overflow-queued.md` の代わり。続きの周の指示も `fixer-prompt-<n>.md` に書く）・`consult-answer-prompt-<n>.md`・`fix-units.json`・`fix-reply.json`・`fix-parked-reply.json`・`fix-parked-<n>.patch`・`rejects-fix-accept.json`・`rejects-fix-accept.md`・`fix-gates.json`・`coverage-after.json`・`count-cache.json`・`count-budget.json`・`fix-unit-rows.json`・`accept-rev-cache.json`・`writes.jsonl`・`trace.jsonl`。
- 裁定: `conflicts.json`・`conflicts-dropped.json`・`conflict-rulings.md`・`rule-tree.json`・`ruler-prompt-<n>.md`（今の `prompt-rule.md`）・`rejects-rule.json`・`rejects-rule.md`。
- 裁定の後: `fix-ruled-head.json`・`fix-ruled-prompt-<n>.md`（今の `prompt-p3.fix-ruled.md`）・`fix-ruled-delivered.json`・`ruled-consult-answer-prompt-<n>.md`・`fix-ruled-reply.json`・`rejects-fix-ruled-accept.json`・`.md`・`clash-fix-prompt-<n>.md`・`clash-ruled-prompt-<n>.md`（今の `prompt-clash-<gid>.md`）・`rejects-clash-accept-<gid>.json`・`rejects-clash-ruled-accept-<gid>.json`。
- 終わり: `fix-removed.json`・`assert-changed.json`・`fix.diff` か `fix-diff-none.txt`・`allowed-tests.json`・`accept-trace.json`・`closure.json`・`tdd-unit.json`・`frozen.json`・`scope.json`・`carry.json`・`reads-fix.json`・`reads-fix-ruled.json`・`reads-fix-block.json`・`prompt-error.json`（指示が組めなかった node と訳）・`fix-collect-error.txt`（finish の中の誤り）。

`carry.json` の形: `{conflicts: <conflicts.json の中身か null>, loops: [{state: <tdd-<k>/state.json の中身>, summary: <summary.md の字か "">}]}`（この段の place の全部の輪。子から写した物を含む）。2 回目の段の prep はこの 1 つのファイルだけを読み、`prior/<k>/state.json`・`prior/<k>/summary.md` に置いてから今の `adopt_prior_pass` と同じ写しをする（今は前の段の place のフォルダを名で開いていた。README の 4.3。13.1 の 5）。

### 1.5 コードの置き場と、作る・触るファイル

作るファイル（この block の PR が触るのはこれと `tests/blocks/fix/` と、この設計書と、下の「共通の物に足す 2 つ」だけ）:

- `workflows/fix/works-factory-fix.yaml`
- 共通の物に足す 2 つ: `workflows/.shared/prompt.py` の口 `sub`（1.5.4）と、`tests/layers/test_block_shape.py` の 7.1 の 3 の照らしの 1 つの道（14.3）。どちらも `.shared/AGENTS.md`・`workflows/AGENTS.md` の 1 行と一緒に足す。共通の断片 `writer-rules` は delta-review の PR が置き、この block は使うだけ（1.5.4）
- `workflows/fix/prompts/`: node ごとの md 9 本（`fixer.md`・`fix-ruled.md` は `{part:fixer}` の 1 行、`consult-answer.md`・`ruled-consult-answer.md` は `{part:consult}`、`tdd.md`・`tdd-new.md` は `{part:tdd}`、`clash-fix.md`・`clash-ruled.md` は `{part:clash}`、`ruler.md` は本文）と断片 `prompts/parts/`（`fixer.md`・`consult.md`・`tdd.md`・`clash.md`・修正役と TDD の役が共に使う `brief.md`・brief の行を名指す節 `brief-head.md`）と、下請けの指示 `prompts/parts/g1-impl.md`・`prompts/parts/g1-review.md`（1.5.4）。
- `workflows/fix/scripts/`: `intake.py`・`prep.py`・`join.py`・`clash_prep.py`・`clash_accept.py`・`conflict_check.py`・`rule_prep.py`・`rule_accept.py`・`fix_ruled_prep.py`・`fix_ruled_accept.py`・`consult_check.py`・`consult_accept.py`・`clean.py`・`assert_changed.py`・`group_start.py`・`tdd_prep.py`・`tdd_step.py`・`fix_prep.py`・`fix_accept.py`・`group_end.py`・`fix_reads.py`・`finish.py`（今の名のまま。`collect.py` は `finish.py`、`route.py` は `intake.py` に）。どの script も「`os.environ.get("INPUTS_<名>")` を字のまま読み、`src/` の 1 つの関数を呼び、`ports.returns` で返す」だけにする。
- `workflows/fix/src/`（package `src`。1.5.1 の写しと、この block の新しいモジュール）
- `workflows/fix/schemas/`（1.2 の 12 本）
- `workflows/fix/fixtures/`（14 節）と `workflows/fix/fixtures/tdd-runner.py`（TDD の筋書きの実行器。14 節）

#### 1.5.1 lib から `src/` へ写すモジュール（README 9.2 の MOVE）

写しは元の関数の中身を変えない。変えるのは (a) import の向き（写したモジュールどうしは `from src import <名>`）、(b) 1.5.2 の「lib のまま呼ぶ」名を lib から呼ぶ所、(c) 指示の文を組む所（2〜6 節。文を md へ出し、値と段落の真偽だけを返す形にする）、(d) 始めの記録の読み（`startrec.read(place)` → `runvals.read(place)`、`gatepolicy.unattended_of(start)` → `runvals.read(place)["unattended"]`、`policy.frozen_copy(start)` → `runvals.read(place)["policy"]`、`startrec.request_file(start)` → `…["request_file"]`、`rolekit.lang_line(start)` は md の `{lang}` に）、(e) 深さ（`fixboard.unit_depths` → `skip_rerun` の読み。13.1 の 2）、(f) 1.5.3 で delta-review・lens・dead に割った関数を写さないこと。それ以外の 1 字も変えない（試験を写して同じ振る舞いを照らす。14 節）。

| 元（lib） | 行き先（src） | 範囲 |
|---|---|---|
| `fixboard.py` | `board.py` | 1.5.3 の fix の名だけ |
| `tddloop.py` | `tdd.py` | 全部（`prep` の指示の組み立てを除く。4 節） |
| `fixgates.py` | `gates.py` | 全部 |
| `factchecks.py` | `facts.py` | 全部（`main` は事前の確かめのコマンドとして残す。1.5.5） |
| `fixrules.py` | `rules.py` | 全部の値の関数（`fix_values`・`owed_values`・`kinds_now`・`kind_of`・`ask_config`・`implementer_values`・`_g1_task`・`resume` の値など）。`rulebook.render` に渡す節の組み立て（`fix_parts`・`tdd_parts`・`ruler_parts`・`write_prompt`・`tdd_render`）は写さず、`src/prompts.py` が `prompt.emit` に渡す値と真偽を組む |
| `consult.py` | `consult.py` | 全部（`answer_text` の決まった文は md〔`prompts/parts/answer-file-head.md`・`answer-file-row.md`〕と値に割った。`question` は呼び手が無く消した。3 節） |
| `clash.py` | `clash.py` | 全部（`prompt` の決まった文は md に。6 節） |
| `ruling.py` | `ruling.py` | 全部（`prep` の指示の組み立ては md に。5 節） |
| `parking.py` | `parking.py` | 全部 |
| `lanekit.py` | `lanes.py` | 全部 |
| `planscope.py` | `scope.py` | 全部 |
| `unitrows.py` | `unitrows.py` | 全部 |

`src/` の新しいモジュール: `files.py`（place の名。1.4）・`runvals.py`（`values.json` の読み書き `write(place, ports)`・`read(place)`・`adopt(parent_place, place)`）・`intake.py`（port の読みと形ごとの必須）・`prompts.py`（9 つの AI の node の値と真偽を組む関数。2〜6 節の差し込み口の一覧と同じ名を返す）・`carry.py`（`carry.json` の書きと、`prior` から `prior/<k>/` に置く読み）・`finish.py`（出力の組み立て。今の `collect.py` の中身）・`report.py`（11 節）。

script の名と `lib/` のモジュールの名は重ねない（README 7.1 の 9）。`scripts/` の名は今のままで重ならない（`clean`・`join` などは lib に無い）。`src/` の中の名は package の中なので lib と重なってよい（`src.consult` と `lib/consult`）。

#### 1.5.2 lib のまま呼ぶ物（写さない）

次は lib の KEEP のモジュールが今 import している、か、2 つ以上の block が使う物なので、写さずに lib から呼ぶ。写すと同じ関数が 2 つ生き、lib の側（KEEP のモジュール）が古い写しを呼び続けるため。

- `conflict` の全部。README 9.2 は「`conflict` の決めの部分（申し出と裁定の積み方・`test_permits`）を fix へ MOVE」と書くが、作り直しの間は写さない。訳: KEEP の `planrange`（delta-review も使う）・`gatemarks`・`replan`・`outcome`・`runreport`・`seat` が今の `conflict` の決めの関数（`test_permits`・`edit_permits`・`agreed`・`ruled_paths`・`held_by_rulings` など）を呼ぶ。fix が写しを持つと、テストの変更を許す道が lib と fix の 2 本になり、keep-essence の 3 の「許す道は 1 本」が作り直しの間だけ崩れる余地ができる（README 10 節の 3 が「この関数は fix の `src/` の 1 つのまま残り、block をまたがない」と書く状態は、`planrange` の割りと一緒に組み込みで作る）。組み込みで行の形（KEEP）と決めの部分（fix の `src/`）に割る（16 節の 3）。
- `unittrees` の全部。README 9.2 は MOVE と書くが、KEEP の `green_cert`・`tree_run`・`groups`・`refix`（delta-review）・`eyeverdict`・`boardview` が使うので、憲法の 4（2 つ以上の使い手は lib）で KEEP に倒した。
- `fixboard` の次の名（lib の `conflict`・`planbrief`・`writes`・`eyeverdict`・`deltamarks`・`boardview`・`runreport`・`outcome`・`gatemarks` が import する。`src/board.py` は `import fixboard` で lib の物を呼ぶ）: `trace`・`trace_rows`・`TRACE_FILE`・`read_json`・`write_json`・`write_text`・`plan_view`・`marks_view`・`allowed_test_rows`・`_allowed_row`・`child_allowed_rows`・`scope_brief`・`overflow_trace`・`ALLOWED_SOURCES`・`FIX_IN_DIFF_CORE`・`run_diff`・`DIFF_EMPTY`・`diff_file`・`pr_revs`・`pr_diff`・`pr_added_lines`・`UNIT_STATUSES`・`FIXED`・`GIVEN_UP`・`NOT_DONE`・`UNIT_LEFT`・`HANDOFF_HEAD`・`accept_out`・`round_number`・`snapshot`・`touched_since`・`undeclared_writes`・`UNDECLARED`。lib の `fixboard` の残りの関数はこの block から呼ばない（`src/board.py` の写しを呼ぶ）。`overflow_trace` は値を受ける形（`overflow_trace(place, trail, *, agreed, guards, gate_tests)`。lib は相談の合意・守りのテストを読まない）なので、`src/board.py` が同じ名の `overflow_trace(place, trail, repo, *, pass_, attempt)` を持ち、合意の id（`conflict.agreed(carried=False)` の origin が accept の行）・守りのテスト（`gates.guards`）・関所の条件の相談で認めた新しいテストのうち今の木に在る物（`gates.present`）を選んで lib に値で渡す（integration.md の 4.3-1）。
- 使う lib（KEEP。README 9.3）: `accept`・`baseline_red`・`cite`・`globs`・`groups`・`impact`・`itemcommits`・`jsonfile`・`leftovers`・`libdocs`・`libdocs_local`・`libdocs_web`・`listcut`・`oneline`・`planbrief`・`planmarks`・`planrange`・`policy`・`querytest`・`reads`・`recount`・`replan`・`report`（`tdd_lines`・`freeze_lines`）・`rolekit`・`seat`（`fill`・`pinned`・`overlay_body`・`OVERLAY_KINDS`・`SEATS`・`carries`・`skill_of`。見出しと決まった文の定数は使わない。下請けの指示と座の型の穴の値〔`SCENE`・`NO_REPORT_FILE`・`G1_REPORT`・`G1_HEAD_SHA`・`G1_IMPL_REPORT`・`G1_PATCH` と `_g1_row`・`g1_diff_cmd`〕は lib の `seat` に無くなるので `src/rules.py` が持つ）・`spseam`・`borrow/`・`stopby`・`tree_run`・`gatemarks`（`duty`・`ledger_files`・`withheld_by`・`returned`・`returned_lines`・`gate_items`）・`answer`（`said`）・`writes`・`writelog`・`graphloops/engine/util.py`。`lib/startrec.py`・`lib/gatepolicy.py`・`lib/depth.py`・`lib/latedepth.py`・`lib/headdepth.py`・`lib/fixbeside.py`・`lib/fixnames.py` は import しない（line へ MOVE・DELETE の物。13.1）。

埋め: `ports.polyfill("childsweep")` は使わない（組の子の作業ツリーの後始末は line の node。README の 1.3 の歩かせ 4 の「子を起こしたノードと同じ include の中のノードが全部 completed になるまで消さない」は line の設計書が持つ）。

#### 1.5.3 `lib/fixboard.py` の名の割り当て（delta-review の設計書と重ねない）

fix の `src/board.py` へ写す（下に名を全部並べる。並べた名だけを写す。今の `lib/fixboard.py` の行の範囲では :50-245・:478-1191・:1717-2928 に在り、その中の delta-review・lens・DELETE・1.5.2 の名は写さない）: `ACCEPT_TRACE_FILE`・`tests_trace`・`accept_trace_rows`・`base_rev`・`owed_units_but_asked`・`fix_duty`・`nothing_owed_but_excused`・`READS_OWNER`・`read_stages`・`collect_reads`・`NO_RESULT`・`CHANGED_MARKS`・`DRIFT_NOTE`・`X_SCALARS`・`NOT_CHANGED`・`NOT_DECLARED`・`prep`・`_in_order`・`fix_groups`・`parallel`（port `parallel` と `git remote` と組の数で）・`SEMANTIC_CLASH`・`rerun_problem`・`rerun_cmd`（軽量の読みを `skip_rerun` に）・`CHECK_RAISED`・`UNRESTORED_HEAD`・`UNRESTORED`・`AFTER_UNRESTORED`・`join_group`・`join_rows`・`HELD`・`unrestored_of`・`held`・`with_ruled`・`child_tdd`・`child_tdd_units`・`child_verified`・`tdd_units`・`cited_rows`・`declared_files`・`changed_problem`・`replan_items`・`allowed_tests`・`changed_marks`・`x_scalars`・`objection`・`handoff_lines`・`mismatched_lines`・`closure_table`・`final_lines`・`declared_lines`・置き場の名の定数（`GROUPS_FILE`〜`PLAN_REPLY_FILE`・`ASSERT_FILE`・`PLAN_REVIEW_FILE`・`FIX_REPLY_FILE`・`JUDGMENT_FILE`・`TIES_FILE`・`MATERIALS_FILE`・`JUDGE_COPIES`・`CHECKED_COPIES`・`RIPPLE_FILE`・`ANSWERS_FILE`・`ONLY_ITEMS_FILE`・`BASELINE_FILE`・`NOTES_FILE`・`BASE_REV_FILE`。`files.py` へ）・`place_items`・`start_tree`・`group_fix_reply`・`_keys_once`・`plan_review_file`・`TESTS_HOW_HEAD`（md へ）・`tests_how_text`（行だけ。2 節）・`FACES_HEAD`（md へ）・`face_units`・`plan_face_rows`・`plan_faces_text`（行だけ）・`plan_face_errors`・`_bodies`・`test_file`・`unit_test_files`・`_moved_tests`・`tests_moved`・`ADOPTED`（`values.json` を足す。`intake.json` は子が写さない。13.4 の 2）・`FIX_UNITS_FILE`・`ALLOWED_TESTS_FILE`・`GROUP_START_FILE`・`ADOPTED_FROM`・`PRIOR_LOOP`・`NO_UNIT_RESULT`・`adopt_inputs`・`adopt_prior_pass`（`carry.json` から。1.4）・`marks_path`・`verified_tests`・`_unit_row`・`group_result`・`adopt_tdd_states`・`adopt_returned`・`ruled_states`・`group_dir`・`usable_result`・`halted_groups`・`drop_unreturned`・`RULED_REPLY_FILE`・`RULED_HEAD_FILE`・`FIX_HEAD_FILE`・受け付けの文の定数（`PARKED_PATCH`〜`RIPPLE_READ`。指示に入る文〔`CONSULT_HEAD`・`RIPPLE_READ`・`RULED_REPLY_LINE`・`JUDGE_UNREAD` の役向けの部分〕は md へ、却下の理由の文は Python のまま）・`group_owed`・`check_unique_units`・`check_opened_units`・`check_excused_units`・`skip_digests`・`record_skipped`・`check_pack_copy`・`fix_reject_rows`・`fix_reject_text`・`reply_marks`・`unit_outcomes`・`parked_reasons`・`judge_query`・`take_conflicts`・`keep_patch`・`revert_units`・`last_settle`・`park_units`・`_without_units`・`accept_reply`・`traced_ops`・`gates_trace`・`closure_reply`・`record_base_rev`・`base_rev_of`・`gate_view`（`runvals` から）・`gate_asks`・`write_notes`・`gate_items`・`consult_ask`・`ruled_reply_line`（値だけ。2 節）・`TDD_START_FILE`・`JOIN_FILE`・`loop_files`・`fixer_head`・`stage_head`・`ruled_owed`・`brief_sources`・`fix_values`・`consult_skip`・`UNREVERTABLE`・`EMPTIED`・`QUEUED`・`_overflow_items`・`gather_overflow`・`split_rows`・`_covers`・`_queue_rows`・`_without_rows`・`settle_overflow`。

delta-review の設計書へ（fix は写さない。delta-review が自分の `src/` に写す）: `ROLE_DEF_HEAD` を除く「差分の審査と手直しの材料」の節の全部（`OUT_NAME`・`out_file`・`output`・`LOOP_NAME`・`loop_file`・`loop_value`・`READONLY_MOVED`・`tree_moved_since`・`take`・`NODE_READS`・`_read_value`・`_brief`・`_given`・`_owed_rows`・`_plan_items`・`_fix_report`・`tie_items`・`hole_ties`）・`DELTA_DIR`・`DELTA_REVIEW`・`DELTA_SKIPPED`・`delta_review`・`REFIX_PROMPT`・`PLAN_ONLY_FACE_KINDS`・`NONE_MIN`・`policy_brief`・`delta_review_due`・`claimed_closed`・`delta_review_problems`・`delta_fix_problems`・`brief_lens`・`prep_fix`・`refix_prompt`・`REFIX_HEAD_FILE`・`undeclared_refix`。delta-review も使う fix の名（`base_rev`・`place_items`・`start_tree`・`_keys_once`・`stage_head`）は、delta-review が自分で写す（README 11.1 の「写す範囲が重ならない」は、同じ名を 2 つの block が別々に写すことを禁じない。1 つの block の中の写しが 1 つ）。delta-review は fix の place を開かず、fix の出力 `start_tree`・`reply`・`ruled_reply`・`scope`・`conflicts` と line の `plan_review`・`policy` を port で受ける（delta-review の設計書で決める）。

lens の設計書へ: `ROLE_DEF_HEAD`・`lens_route`・`lens_collector`・`LENS_PROMPT`・`LENSES_FILE`・`LENS_NOT_DONE`。

DELETE（どの block にも写さない）: `PREP_INPUTS`・`MODES`・`LANE_SWITCHES`（port の宣言と `files.MODES` に替わり、読み手が無い）・`depth_doc`・`returned_results`・`depth_signals`・`redepth`（line の上げ直しに寄せる。README の形の直し 5）・`DEPTH_FILE`・`HEAD_DEPTH_FILE`・`DEPTH_RAISED_FILE`・`HEAD_RECORD_FILE`・`UNITS_FILE`・`unit_depths`（`skip_rerun` に替わる）・`LENS_NOT_DUE`・`_fix_output`・`fix_reply`・`owed_keys`（本番の呼び手が無い）。`depth_signals` が数えた信号のうち line が今持たない「修正役の異議」は、出力 `objection` で line に届く（line の設計書で上げ直しの信号に足す。16 節の 4）。

`lib/fixbeside.py`（README 9.1 で DELETE）のうち fix の物: `CLOSURE_FILE`・`claimed_of`・`closure_rows`・`write` の閉鎖の表の部分 → `src/finish.py`。`_accepted_tests` → `src/finish.py`（`accept_trace` の行の選び。line の読み口が使う形は line の設計書）。`returned`・`PORTS`・`_port`・`_place` は消す（port の宣言に替わる）。

#### 1.5.4 共通の口に足す物（この block が最初に要る）

- 下請けの指示を組む口は、plan-review の枝が置いた `workflows/.shared/prompt.py` の `render_part(name, values, when=None) -> str`（呼んだ script の在る block の `prompts/parts/<name>.md` を `render` と同じ決まりで組んだ字を返し、place には書かない）を使う。書くのは呼び手（修正役に渡す下請けの指示のファイル `g1-impl-<n>.md`・`g1-review-<n>.md`）。訳: 下請けは Archon の node でないので `render` の node の md に置けず、今は決まった文を `lib/seat.py` の定数（`G1_SUB_HEAD`・`G1_SUB_RULES`・`G1_EXTRA`）と `direct.md` の節 `fix-ask-sub` と `lib/agents/judge.md`（検索語の規律）から Python が組んでいた（憲法の 2 に当たる）。block の断片の置き場は `prompts/parts/` の 1 つだけ（`docs/design/README.md` の 3 章）。この枝は初め `sub` と `prompts/sub/` を足したが、窓口の決めで `render_part` と `prompts/parts/` に替え、断片を字を変えずに移した。
- 共通の断片 `writer-rules`（`workflows/.shared/prompts/writer-rules.md`。`{shared:writer-rules}`）: 書く役の決まりの正本（今の `fix-rules/common.md` の `core-fix`・`evidence` と 4 つの種類・`core-conflict`・`core-keep`）。修正役・TDD の役と、delta-review の手直しの役の 2 つの block が使うので共通の断片にする（`workflows/.shared/AGENTS.md` と README 11.1 の決まり。工場の作り直しのまとめ役の決め。README の形の直し 3 は fix の中の断片と書いたが、手直しの役が fix の外の block になった）。置くのは先に作る delta-review の PR で、この block は受けて使うだけ（足さない・直さない）。段落の名は 9 つ: `conflict`（食い違いの申し出）・`docs`・`prompts_kind`・`config`・`code`（証拠の 4 つの種類）・`evidence`（証拠の頭と文。種類の 1 つでも真の時）・`where_fixer`・`where_tdd`・`where_rework`（証拠を書く場所の 1 文。役ごとに 1 つだけ真）。ほかの段落（直し方・守ること）はいつも入る。この block は `conflict` をいつも真で渡し、`evidence` は 4 つの種類の 1 つでも真の時に真、書く場所は修正役が `where_fixer`・TDD の役が `where_tdd` を真にして `where_rework` は偽にする（delta-review の手直しの役は `conflict` が偽、4 つの種類と `evidence` が真、`where_rework` だけが真で `where_fixer`・`where_tdd` は偽）。
- 外への検索の決まりは今在る `{shared:query-rule}`、却下の段落は `{shared:rejected}`。ほかの共通の断片は足さない。

#### 1.5.5 事前の確かめのコマンド

修正役が返答の前に走らせる事前の確かめ（今の `lib/factchecks.py` を `python3 lib/factchecks.py <place>/consult.json --reply <draft>` で起こす。F100）は、`workflows/fix/src/facts.py` の `main` を `python3 <block のフォルダ>/src/facts.py <place>/consult.json --reply <draft>` で起こす形に替える。コマンドの字は `src/prompts.py` が組んで `{check_cmd}` で md に入れる（今の `check_cmd` と同じく `sys.executable` から）。`src/facts.py` は単独で起こされた時に `sys.path` に `workflows/.shared` と `workflows/fix` と `lib/` を足す（script の頭と同じ 2 行と `ports` の import）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line の 1 回目の修正の段（include の id `fix`）: `mode: whole`・`judgment` ← diagnose の `judgment`・`answer_ties`・`materials` ← line（今の judge-out の同じ欄）・`plan`・`fix_plan`・`ripple` ← plan の往復の最後の周・`plan_review` ← 最後の事前審査・`answers` ← 修正前の承認ノードの答え（`asked` を付けて。F225）・`request_answers`・`unattended`・`parallel`・`test_cmd`・`reuse_dir`・`user_env_dir`・`lang` ← 始めの記録・`policy` ← 始めの記録の固めた写し・`request` ← 依頼のファイル・`baseline` ← `$test-gate-base.output.baseline`・`tdd_suite` ← `$test-gate-base.output.suite`・`reuse_key` ← line の run の id・`skip_rerun` ← line が深さの表から引いた軽量の単位（段 → 回す物の表が「緑の後の試験の走らせ直しを省く」を持つ段だけ。今の `depth.omits`）。
- 2 回目の修正の段（案の直しの後）: 同じ物に `plan`・`fix_plan` ← 案の直し・`ripple`・`answers`・`notes` ← 案の直しの承認ノード・`only_items` ← `$fix.output.replan_items`・`prior` ← `$fix.output.carry`・`plan_review` ← 案の直しの事前審査。
- 読み手（line の設計書で配る）: line の受け皿と 2 段の合わせ（`units`・`groups`・`conflicts`・`objection`・`stop_reason`・`ok`・`diff` ほか）・line の上げ直し（`units`・`conflicts`・`diff`・`plan_declared`・`objection`・`tdd_refused`・`accept_trace`）・delta-review（`start_tree`・`reply`・`ruled_reply`・`scope`・`conflicts`・`checked`。`when:` は `checked.ok` と `stop_reason == ""` と line の深さの表）・eyes と r2・r4（`units`・`changed`・`x_scalars`・`plan_declared`・`tdd`）・lens（`start_tree`）・merge（`item_claims`）・line の最後の承認ノードと report（`handoffs`・`mismatched`・`allowed_tests`・`accept_trace`・`closure`・`removed`・`conflicts`・`freeze_off`・`report`）・案の直し（`replan_items`・`conflicts`）。
- 組の子の作業ツリーの後始末は line の終わりの node（今の `sweep_children`）。
- `workflow: works-factory-fix` は `workflows/fix/` の block を指す（pack は `workflows/` の 1 つ。README 3 節）。

## 2 node の設計シート: fixer と fix-ruled（修正役・裁定の後の修正役）

### 2.1 役

直す義務の単位を作業ツリーの上で直し、単位ごとに 1 行（閉鎖の実証・覆いの母数・根か症状か・破りに行った入力・壊しうる面・先行例）と周の全体の欄を返す。TDD の loop が緑にした単位は直し直さず行を写す。項目ごとに実装役と審査役の下請けを Agent で起こす。範囲の外が要れば `consult` で相談し、曲げるしかなければ食い違いの申し出を返す。fix-ruled は、裁定（直す裁定）の文のとおりに、裁定が名指した単位を直し直す同じ役。

### 2.2 port

`values.json`（← port `policy`・`request`・`lang`・`tdd_suite`）・`judgment.json`（← `judgment`）・`fix-plan-reply.json`（← `fix_plan`）・`plan-fields.json`（← `plan`）・`p2.plan_review.json`（← `plan_review`）・`ripple.json`（← `ripple`）・`human-notes.md`（← `answers`・`request_answers`・`unattended`・`notes`）・`baseline.json`（← `baseline`）・TDD の loop の要約（組の中の `tdd-<k>/summary.md`）・範囲の相談の控え（place）・却下の控え `rejects-fix-accept.json`（fix-ruled は `rejects-fix-ruled-accept.json`）・裁定の文 `conflict-rulings.md` と保存した 1 回目の返答 `fix-reply.json`（fix-ruled だけ）。

### 2.3 組み立ての順（`prompts/parts/fixer.md`。`fixer.md`・`fix-ruled.md` は `{part:fixer}` の 1 行）

段落の真偽は `src/prompts.py` の `fixer_values(place, pass_)` が組む（入れ子にしない決まりなので、どの段落も 1 つの名で選ぶ。名と意味は下の表）。値の組はいつも同じで、入らない段落の口には空の字を渡す。

| 段落の名 | 真の時 |
|---|---|
| `rules` | 決まりを全部渡す周（続きの周 `resume`・`queued`・`overflow_answer` でない）。修正役と TDD の役が共に使う断片の、どの段落もこの名か下の 4 つの種類の名で選ぶ |
| `rejected` | `rules` で、却下の控えに行が在る（裁定の後の 1 周目は控えが空なので偽） |
| `rulings_first` | fix-ruled の 1 周目（今の `RULINGS_LINE`） |
| `ruled_reply` | fix-ruled で `rules`（今の `RULED_REPLY_LINE`。毎周） |
| `briefs` | `rules` で brief が在る |
| `faces` | `rules` で事前審査の穴か別案が在る |
| `scope` | `rules` で承認済みの修正案が在る（範囲の節） |
| `tests` | `rules`（テストの節。修正案の有無によらずいつも） |
| `tests_how` | `rules` で直す前の走らせ方が在る |
| `policy`・`no_policy`・`request`・`no_request` | `rules` で方針の文書・依頼のファイルが在る／無い |
| `conflict` | いつも真（共通の断片 `writer-rules` の食い違いの申し出の段落） |
| `docs`・`prompts_kind`・`config`・`code` | `rules` で、`rules.kinds_now` がその種類を選んだ（前の周に渡した種類は減らさない。控えは `fixer-delivered.json`） |
| `ask` | `rules` で `rules.ask_config` が真（答えの役の node と承認済みの項目が在る） |
| `ask_ripple` | `ask` で波及の一覧が在る |
| `libdocs` | `rules` でライブラリの文書の節が空でない |
| `g1` | `rules` で下請けを起こす単位が在る（1 回目は TDD の loop が緑にした単位を除いて残る物、fix-ruled はいつも） |
| `seat_one` | `rules` で `g1` が偽 |
| `resume` | 相談の答えを渡す続きの周（今の `fix-consult-resume`） |
| `queued` | 受け付けがはみ出しを相談に積んだ続きの周（今の `fix-overflow-queued`） |
| `overflow_answer` | はみ出しの答えを渡す続きの周（今の `fix-overflow-resume`。答えの行の origin が accept） |

並び（今の `rulebook.render` の並び: 却下の 1 行 → before → 決まり → 言語の 1 行）:

1. `<!-- if rejected -->` `{shared:rejected}`（`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "fix-accept"))`。fix-ruled は `"fix-ruled-accept"`）。
2. `<!-- if rulings_first -->` 裁定の文を先に全部読めの 1 文と `{rulings_file}`。
3. `<!-- if ruled_reply -->` 保存した 1 回目の返答を先に全部読めの 1 文と `{saved_reply}`（今の文の「あなたは新しい会話なので」は外す。13.2 の 2）。
4. `<!-- if briefs -->` `## The requirement (briefs)` と `{brief_rows}`（← `src/rules.py` の `brief_rows`。項目ごとの 1 行〔項目の番号・brief のパス・sha256・単位。今直さない単位は「今は直すな」と添える〕を `planbrief.for_units` の項目から組む。見出しと結びの 1 文〔「まず Read で全部読め…」〕は md の部品 `prompts/parts/brief-head.md` で、修正役と TDD の役の指示が `{part:brief-head}` で入れ、下請けが Read する座の型の `[BRIEF_FILE]` の本文も `render_part` で同じ部品から組む。lib の `planbrief.head_text`・`unit_note` は呼ばない）。
5. `<!-- if faces -->` `## Pre-review keys to answer (plan_faces)` と頭の 1 文と `{faces_rows}`（← `board.plan_faces_text` の行）。
6. `<!-- if scope -->` `## Paths you may change and what you must not touch` と頭の決まり（今の `planrange.OOS_MINE`）と `{scope_rows}`（← `src/rules.py` の `scope_rows`。項目ごとの範囲の行と全部の項目に効く許しの行だけ。lib の `planrange.scope_text` は呼ばない）。`<!-- if tests -->`（13.4 の 6）`## Tests you may add or change, and frozen tests` と頭の 1 文と `{tests_rows}`（← `src/rules.py` の `tests_rows`。足してよい新しいテスト・本体を変えてよい既存のテストの名指しと範囲・凍ったテストの行だけ。lib の `planrange.tests_text` は呼ばない）と結びの 1 文（名指しの外の既存のテストの関数を変える・消すと拒む）。
7. `<!-- if tests_how -->` `## How the tests were run before the fix` と `{tests_how}`（← `board.tests_how_text` の how の行）と「環境や命令を探さずにこの形で回せ」。
8. `<!-- if policy -->` 方針の文書の 1 行と `{policy_path}`／`<!-- if no_policy -->` 「方針の文書は無い」。`<!-- if request -->` 依頼のファイルの 1 行と `{request_file}`／`<!-- if no_request -->`。
9. `<!-- if rules -->` `# Fixing (the writer's job)` と役の 1 段落と `## What to read`（`{judgment_file}`・`{open_units}`・`{plan_file}`・`{policy_path}`・`{summary_file}`・`{notes_file}` と各行の決まり。今の `direct.md` の `fix-head`）。
10. `{part:brief}` と `{shared:writer-rules}`（2.3.1。`conflict` はいつも真）。
11. `<!-- if rules -->` 何も変えずに済んだと言うな（今の `fix-keep`）。
12. `<!-- if ask -->` `## Scope consultation and the pre-check`（今の `fix-ask`。`{budget}` ← `consult.BUDGET`・`{draft}`・`{check_cmd}`）。`<!-- if ask_ripple -->` 波及の一覧の 1 行と `{ripple_file}`。
13. `<!-- if libdocs -->` `## Library documents (installed version and official)` と頭の 1 文と `{libdocs_rows}`（← `libdocs.section` の本文から見出しと頭の 1 文を除いた行。数・取れた物・ライブラリごとのパス。取る・控える仕事を含む `section` は plan の枝も使うので lib に残り、この block は見出し〔`libdocs.TITLE`〕と頭の文〔`libdocs.HEAD`〕を剥がして行だけを入れる）。
14. `<!-- if g1 -->` `## Running subagents`（今の `seat.G1_HEAD`・`G1_STEPS` の 6 手順・`G1_LOOP_NOTE`・`DIVERGENCE_HINT` の 6 つの場面・`G1_OVERRIDES` を英語の決まった文に）と `{g1_items}`（← 項目ごとの 1 行「項目 n: 実装役 <ファイル>・審査役 <ファイル>・差分のコマンド <字>」）と `## Reading borrowed skills` の頭の 1 文と `{unattended}`（← `seat.overlay_body(seat.OVERLAY_KINDS["fix"])`。日本語のまま。local-review の設計書と同じ）。
15. `<!-- if seat_one -->` `## The borrowed seat`（今の `seat.HEAD`・`WINS`・`PROMPT_HEAD` を英語に）と `{seat_body}`（← `seat.fill` で埋めた superpowers の implementer の型。借りた写しの字のまま）と `{unattended}`。
16. `<!-- if rules -->` `## What to write for each fix (one changes row)` と `## What to write for the whole round` と、受け付けが見る物の結びの段落（今の `fix-reply`）。
17. `<!-- if resume -->` `# The answer to your scope consultation (continued)` と `{answer_file}`・`{left}`。
18. `<!-- if queued -->` `# Overflow the acceptance found (sent to consultation)`。
19. `<!-- if overflow_answer -->` `# The answer about the overflow (continued)` と `{answer_file}`・`{left}`。
20. 人に見せる欄の言語の 1 文と `{lang}`（名指す欄: `changes[].what`・`closure` の文の欄・`root_or_symptom.why`・`bypass_tried`・`breaks` の文の欄・`precedent.reason`・`not_done[].why`・`interactions[].checked`・`combined_effect`・`plan_faces[].how`・`rejudge_requested`・`premise_drift_note`・`conflicts[].why_both_cannot_hold`・`consult[].why`・`bash_writes[].why`。key・enum・パス・コマンドは字のまま）。

続きの周（17〜19）では 1〜16 の段落が全部偽になる。ただし共通の断片 `writer-rules` の段落を選ぶ名は `conflict` と 4 つの種類だけなので、10 の `{shared:writer-rules}` の直し方・食い違いの申し出・守ることは続きの周にも入る（今の続きの周は続きの段落と言語の 1 文だけだった。指示が長くなるだけで、役のする事は変わらない。13.2 の 1）。続きの周の 4 つの種類は偽にする。

#### 2.3.1 修正役と TDD の役が共に使う断片

どの段落も 1 つの名で選ぶ（TDD の役はいつも `rules`・`conflict` が真）。

- `prompts/parts/brief.md`（この block だけ）: `<!-- if rules -->` `## Brief rules (the source of the requirement and the background)` と決まり 1〜8（今の `brief.md` の `brief-canon`）。
- `{shared:writer-rules}`（1.5.4。delta-review の PR が置く）: いつも入る `## How to fix`（今の `core-fix` の 10 の決まり）と `## Evidence for fixes whose red-to-green a test cannot show` の頭、`<!-- if evidence -->` の頭と、書く場所の `<!-- if where_fixer -->`・`<!-- if where_tdd -->`・`<!-- if where_rework -->`、`<!-- if docs -->`・`<!-- if prompts_kind -->`・`<!-- if config -->`・`<!-- if code -->` の 4 つの種類、`<!-- if conflict -->` `## Conflict declarations (do not bend to get green)`（今の `core-conflict`）、いつも入る `## What to keep`（今の `core-keep`）。

#### 2.3.2 下請けの指示（`prompts/parts/g1-impl.md`・`g1-review.md`。1.5.4 の `prompt.render_part`）

- `g1-impl.md`: `{template}`（← `seat.fill` で項目ごとに埋めた superpowers の implementer-prompt。借りた字のまま）と、works の決まり（今の `seat.G1_SUB_HEAD`・`G1_SUB_RULES`）・`{shared:query-rule}`（`spawns` は偽。今は `lib/agents/judge.md` の写しを入れていた）・範囲の外が要る時の決まり（今の `direct.md` の `fix-ask-sub`。`{check_cmd}`）。
- `g1-review.md`: `{template}`（← task-review の型に `BASE_SHA`・`DIFF_FILE`・`GLOBAL_CONSTRAINTS` を入れた物）と今の `seat.G1_EXTRA`。
- `src/prompts.py` の `g1_files(place, items, values)` が `prompt.render_part` で組んで place の `g1-impl-<n>.md`・`g1-review-<n>.md` に書く（名は今のまま。修正役は今どおりファイルの中身を字を変えずに下請けに渡す）。

### 2.4 返す形

今の `&fix_reply` の `output_format` を字のまま写す（`precedent` の `allOf`・`if`・`then` も。13.2 の 6）。人に見せる欄と言語は 2.3 の 20。

### 2.5 描いた骨組み（例の run `c5c3642f-…` の 2 周目〔却下 1 回〕。fix-ruled は `d31781b6-…` の 2 周目）

```markdown
## Why your previous answer was rejected
…（{shared:rejected}）
受け付けがこれまでに拒んだ理由の全部（古い順に 1 件。…）
1 回目の拒否:
## 事後の関門の束（確かめ gates・1 件）…

## The requirement (briefs)
- 項目 1: <place>/brief-1.md（sha256 90e9f9b8…・単位 lib/seal.py STATUSES: …）
- 項目 2: <place>/brief-2.md（…）
- 項目 3: <place>/brief-3.md（…）
Read them all first. …

## Pre-review keys to answer (plan_faces)
…
- `ledger-54-row-is-two-phrases`（穴・suggest・contract_drift）: 案は #663 の行を 3 つ…（12 行）

## Paths you may change and what you must not touch
…
- 項目 1（単位: lib/seal.py STATUSES: …）
  - allowed_paths: `lib/seal.py`、`lib/gatemarks.py`、…
…
## Tests you may add or change, and frozen tests
…
There is no policy document.
The request file: <依頼のファイル>（read it all first）

# Fixing (the writer's job)
…
## What to read
- The judgment file: <place>/judgment.json — background …
- The keys of the units you owe a fix (JSON array): ["lib/seal.py STATUSES: …", …]
- The fix plan: <place>/p2.fix_plan.json — …
- The policy document: (empty) …
- The result of the TDD loop: (empty) — …
- The file with the answers at the approval node: <place>/human-notes.md — …

## Brief rules … / ## How to fix … / ## Evidence … （docs・prompts・config・code の 4 つ）/ ## Conflict declarations … / ## What to keep …
- Do not say "done" without changing anything. …

## Scope consultation and the pre-check
… (9 rounds in this loop) …

## Library documents (installed version and official)
数: 見つけた 1 本（…）… ### PyYAML 6.0.3 …

## Running subagents
1. … 6. …
- 項目 1: 実装役 <place>/g1-impl-1.md・審査役 <place>/g1-review-1.md・差分のコマンド …
…
## Reading borrowed skills
…
# 借りた superpowers のスキルを無人の役で読むときの読み替え …（{unattended}。日本語のまま）

## What to write for each fix (one changes row)
…
## What to write for the whole round
…
Write the human-facing fields (…) in 依頼文の言語（利用者の言語）. …
```

fix-ruled の 2 周目は、頭の 1 の後に 3（`<place>/fix-reply.json`）が入り、2（裁定の文）は 1 周目だけ。続きの周（例の run の `consult-first-1-resume.md`）の骨組みは `# The answer to your scope consultation (continued)` と答えのファイル <place>/consult-first-1.md と「残りの相談の周: 8 回」と言語の 1 文だけ。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。今の指示は `workflows/fix/commands/fix-rules/direct.md`（103 行）・`common.md`（73 行）・`brief.md`（46 行）と、`lib/fixrules.py`（`start_lines`・`RULINGS_LINE`・`fix_parts`・`resume`・`overflow_queued`）・`lib/fixboard.py`（`RULED_REPLY_LINE`・`FACES_HEAD`・`TESTS_HOW_HEAD`・`plan_faces_text`・`tests_how_text`）・`lib/planbrief.py`（`head_text`）・`lib/planrange.py`（`SCOPE_HEAD`・`TESTS_HEAD`・`OOS_MINE`・`scope_text`・`tests_text`）・`lib/libdocs.py`（`section`）・`lib/seat.py`（`section`・`g1_section` と `G1_*`・`DIVERGENCE_HINT`）・`lib/rolekit.py`（`REJECT_LINE`・`LANG_RULE`）・`lib/rulebook.py`（`HEADER` の行）に割れている。

- 移した: Python の定数に在った決まった文（上の全部の見出しと頭の文、`G1_STEPS`・`G1_OVERRIDES`・`DIVERGENCE_HINT`、`RULED_REPLY_LINE`・`RULINGS_LINE`、`resume`・`overflow_queued` の本文）を md へ。Python に残るのは材料の行（brief の行・穴の行・範囲の行・テストの行・ライブラリの行・項目ごとの下請けの行）と値。
- まとめた: 却下の 1 行（今の `REJECT_LINE`。役に却下のファイルを Read させていた）を `{shared:rejected}` の 1 か所に。却下の理由は今と同じ控えから全部（古い順）を値で入れる。
- 消した: 1 行目の HTML の印 `<!-- works-prompt {role, iteration, rules_sha, sections} -->`（`rulebook.HEADER`。読み手は試験 `test_fix_rules.py` だけで、組み立ての記録は place の `fixer-prompt-<n>.md` が持つ）。
- 消した（偽になった文）: 「修正案を書いた役がその会話の続きで答え」（今の `fix-ask`。答えの役は修正案を読む別の役）を「修正案を書いた役の代わりに、修正案を読んで答える役が答える」に。裁定の後の「あなたは新しい会話なので」（fix-ruled は `fresh_context: false` の loop で 2 周目から会話を継ぐ。1 波目の作りから足した決まり〔`fresh_context: false` の loop の役の md は新しい会話と言わない〕）。指示書のファイルを Read で全部読めの 1 行（指示は `prompt:` に字で入る）。続きの周の「前に読んだ指示書 <<prompt_file>>」は「この会話で前に渡した指示」に。
- 消した: 使われていない節 `fix-lane`（`direct.md:65-73`。どこからも組まれていない）。
- 消した: ほかの node と block の名（「差分の審査」「独立の目」「メイングラフの最後のテストの段」など、今の文が後の段の振る舞いを前提に書いた句）は、block の外の名を持たない言い方に（「後の工程が回す」）。決まりの意味は変えない。
- 移した: 言語の 1 行（`rolekit.LANG_RULE` の汎用の欄の並び）を、この node の人に見せる欄の名指しと `{lang}` に。
- 足した（指示の量だけ）: 続きの周（相談の答え・はみ出しの積み・はみ出しの答え）にも共通の断片 `writer-rules` の直し方・食い違いの申し出・守ることが入る（2.3 の結び。断片の段落の名が `conflict` と 4 つの種類だけのため）。決まりは同じ会話で前に渡した物と同じ字。ほかに足した物は次の 5 つ（指示の新旧の比べで見つかった書き漏れ。害は無い）。
- 足した: 修正役（`fixer`・`fix-ruled`）に、sandbox が下書きの置き場への書き込みを拒んだら `$TMPDIR` に書いて `--reply` にそのパスを渡す逃げ道（事前の確かめの節）。
- 無い（今の指示にあった）: 「Return only the JSON」の 1 文が `fixer`・`fix-ruled`・`ruler`・`clash-fix`・`clash-ruled` に無い。`output_format` が返りの形を縛るので害は無く、足さない。
- 変えた: `tdd` の役の名と節の並びが今の `tdd.md` と違う（節の名を英語の見出しにし、並びを 2.3 の表の順にした）。決まりの中身は同じ。
- 足した: `consult-answer` の段落 `plain` に、答え方の文（頼みの番号ごとに 1 行ずつ答える）。件数の字は「{count} scope consultation(s)」に直した（1 件の時の複数形の誤りを md で直した）。
- 言語の 1 文に、今の `rolekit.LANG_RULE` の括弧「（key は周をまたいで突き合わせるので訳さない）」を戻した（`fixer`・`ruler`・`tdd`・`clash`。元と同じ）。
- 下請け（`g1-impl`・`g1-review`）の検索の決まりは、共通の断片 `query-rule` の頭の行だけを持つ（md の同じ意味の頭の行は消した）。断片が足す「一次の出典を先に読む」は README 5.1 に 1 行で載せる（この設計書には足さない）。
- 英語にした（#764）。材料の行（`{brief_rows}` など）は今の lib が組む日本語の字のまま入る（lib を変えないため。組み込みで lib の文を md へ出す時に英語の札にする。16 節の 6）。

### 2.7 元の works と graphloops の同じ場面

- 元の works `works/blk-fix/blk-fix.yaml` の `fix-loop`（:1543。`max_iterations` 12 = 受け付けの 3 回 + 相談の枠 9、項目ごとの下請け）と受け付け `scripts/accept.py` の確かめの表 13 種（consult・frozen・writes・conflict・pack・duplicate・not_opened・accepted・excused・scope・tests・gates・copy）。工場は `accepted`（2 回目の段の控えの照らし）を外し、`closure` と `plan_faces` を足した（#94 で外し、#264 で plan_faces を戻した）。この block は今の工場の 14 種のまま。
- 元の範囲の相談は修正案を書いた役の会話の続き（`continue=fix-planner`）、裁定の後の修正役は 1 回目の修正役の会話の続き（`continue=fix`）だった。工場は Archon の loop の中で `context.resume` を使えない（同じ loop の中の node を名指せない。止めた Archon の `loader.ts` の `context.resume cannot name a source inside the same loop_group body`）ので、保存した返答と修正案を読ませる形にした（#94。F218・F222）。この block も同じ。
- 元の並べの枝の修正役（`fix-lane-loop-1..3`）と枝の決まり `fix-lane` は、組ごとの子の run に替わった（持ち主の決め `no-queue`・#94）。
- graphloops `prompts/review-loop/p3.fix.md` と `workflows/review-loop/fix/block.json`（確かめ `fix_covers_open_units`）。工場は `lib/recount.py` にほぼ全部を写した。graphloops の新しいファイルに `git add -N` を打つ決まり（p3.fix.md:42）は元の works にも工場にも無い（足さない。振る舞いの外）。
- この block が両方より良く、残す物: 書き込みの出どころを拒否にする（graphloops は記録だけ）・凍ったテストとテストの変更を許す道が 1 本・範囲の相談・食い違いの申し出と読むだけの裁定・はみ出しを拒まずに相談へ積む・最後の回だけ名指しの単位を戻して諦める・閉鎖の数え直しの食い違いを人に見せる。

### 2.8 受け付け（fix-accept・fix-ruled-accept）

8 節。

### 2.9 試験

14 節。守る keep-essence: 3・4・5・6・7・8・11。

## 3 node の設計シート: consult-answer と ruled-consult-answer（相談の答えの役）

### 3.1 役

修正役が `consult` で頼んだ範囲の外（足すパス・書き換える既存のテスト・足す新しいテスト）と、修正の前の承認ノードの条件から機械が作った頼みに、修正案を書いた側として allow・deny・defer で答える。読むだけ。

### 3.2 port

相談の頼み（← `consult-check` が `consult.screen_ask` で確かめた行。修正役の返答の `consult`〔試したこと・範囲の中で直せない訳・根拠のファイルと行を持つ。13.3 の 1〕と、受け付けが積んだはみ出し、`answers` の続けの一言）・同じ run の前の相談と答え（← place の `trace.jsonl`）・修正案（`fix-plan-reply.json`。無ければ `plan-fields.json`）・波及の一覧（← `ripple`）・`lang`。

### 3.3 組み立ての順（`prompts/parts/consult.md`。2 つの node の md は `{part:consult}` の 1 行）

1. 答える立場の 1 段落（今の `fixboard.CONSULT_HEAD`）: 修正案のファイル `{plan_file}` を先に全部読み、自分が書いた修正案として扱え。今の文の「（新しい会話）」は外す（作り直しの時は、同じ周の修正役の会話から分かれて起きたので偽だった。#833 で新しい会話で起きるようにした後も、修正案を先に全部読めの文で足りるので戻さない。13.3 の 1）。
2. `<!-- if ripple -->` 波及の一覧の 1 文と `{ripple_file}`（今の `RIPPLE_READ`）。
3. `# Scope consultation (from the fixing stage)` と今の `consult.QUESTION` の決まり（決めるのはあなた・out_of_scope の考え直し方・ほかの項目の out_of_scope を allow した時の効き方）と `{count}`（頼みの件数）。
4. `<!-- if plain -->` 頼みの答え方の段落（今の `ASK_TEXT` の「答え方」の部分。頼まれた物の中からだけ許す）。`<!-- if gate -->` 承認ノードの条件の頼みの答え方の段落（今の `ASK_GATE_TEXT` の「答え方」の部分。条件が求める物を自分で挙げてよい・関わらない条件なら deny）。
5. `<!-- if history -->` 同じ run の前の相談と答えの一覧の段落と `{history}`（← `consult.history_text`。#833）。
   `{asks}`（← `consult.asks_text` の頼みごとの節 `## 相談 <n>: 項目 <m>（単位: …）` と行〔今の範囲・out_of_scope と当たった glob と外した理由・足したいパス・テストの範囲・新しいテスト・当たり・理由・修正役の試したこと・範囲の中で直せない訳・根拠のファイルと行・承認ノードの条件の字〕。決まった文を除いた材料だけ）。
6. 答えの JSON の欄の決まり（今の `QUESTION` の後半: ask・decision・paths・tests・new_tests〔red と guard〕・spec・reason、期待を実装に合わせる許しを出すな）。
7. 人に見せる欄の言語の 1 文と `{lang}`（`reason`・`spec`）。

### 3.4 返す形

今の `&consult_answer` のまま: `answers: [{ask, decision (allow|deny|defer), new_tests?: [{id, red_kind (red|guard)}], paths, tests, spec, reason (10 字以上)}]`。

### 3.5 描いた骨組み（例の run `c5c3642f-…` の `consult-first-1-ask.md` の値。裁定の後は `d31781b6-…` の `consult-ruled-1-ask.md`）

```markdown
Answer as the author of the fix plan. Read the fix plan <place>/p2.fix_plan.json first, all of it, and treat it as the plan you wrote. …
Read the ripple list <place>/ripple.json …

# Scope consultation (from the fixing stage)
Another role is fixing the plan you wrote. It sent 3 consultations. …

## 相談 1: 項目 1（単位: lib/seal.py STATUSES: …）
- 項目の今の範囲（allowed_paths）: lib/seal.py・lib/gatemarks.py・…
- 触らない物（out_of_scope）: （無し）
- 承認ノードで出した条件（字のまま…）: （無人の run が採った推し。人の答えではない）unnamed-redesign-raw-words-on-gate-face は …
## 相談 2: … ## 相談 3: …

Return only this JSON (`answers`, one row per consultation number): …
Write `reason` and `spec` in 依頼文の言語（利用者の言語）.
```

### 3.6 今の指示との差

今の指示は `lib/fixboard.py` の `CONSULT_HEAD`・`RIPPLE_READ`（:2019-2021）と `lib/consult.py` の `QUESTION`・`ASK_TEXT`・`ASK_GATE_TEXT`（:109-157）と `question`（:373）に在る（md は無い）。

- 移した: 全部の決まった文を md へ。頼みごとの節の材料（見出し `## 相談 <n>` と行の札）は Python に残す（README 5.3 の項目ごとの札）。頼みごとに繰り返していた「答え方」の文は、頼みの種類（plain・gate）ごとに 1 回だけ md に置く。
- 消した: 「（新しい会話）」（作り直しの時は偽。#833 の後も戻さない。13.3 の 1）。
- 足した: 言語の 1 文と `{lang}`（今は言語の行が無く、`reason`・`spec` の言語を決めていなかった。README 5.3 の決まり）。
- 英語にした。

### 3.7 元の works と graphloops の同じ場面

元は修正案を書いた役の会話の続きで答えた（`blk-fix.yaml:1640` の `continue=fix-planner`）。工場は Archon の loop の中で前の会話を名指せないので、修正案を読む役にした（#94。F222）。graphloops に範囲の相談は無い。

### 3.8 受け付け（consult-accept）

8.4。

### 3.9 試験

14 節。守る keep-essence: 3（相談の合意が `test_permits` の出どころの 1 つ）。

## 4 node の設計シート: tdd と tdd-new（TDD の役）

### 4.1 役

単位ごとに、テスト（赤）→ 直す（緑）→ 申告した時だけ整える、の 1 段ずつを返す。1 周目は義務の単位を tdd か direct に振る。赤と緑は機械が JUnit の結末で判じる。tdd は同じ単位の続き（前の周の会話を継ぐ）、tdd-new は新しい単位の周（`context: fresh`）。指示は同じ md。

### 4.2 port

TDD の loop の状態 `tdd-<k>/state.json`（← `group-start` が `tdd.start` で作る。実行器 ← port `tdd_suite`、test_cmd ← `test_cmd`、軽量の単位 ← `skip_rerun`、使い回し ← `reuse_dir`・`reuse_key`）・`judgment.json`・brief・`fix-plan-reply.json`・`human-notes.md`・`values.json`（方針・依頼・`lang`）・`baseline.json` の how・前の周の却下の理由（state の `reason`）。

### 4.3 組み立ての順（`prompts/parts/tdd.md`。`tdd.md`・`tdd-new.md` は `{part:tdd}` の 1 行）

値と真偽は `src/prompts.py` の `tdd_values(place, state)`。TDD の役は毎周、決まりを全部渡す（今と同じ。`rules` はいつも真）。段の名 `phase_route`・`phase_test`・`phase_fix`・`phase_refactor` のどれか 1 つが真。

1. 題 `# The TDD loop prompt (round {iteration}, phase {phase})`。
2. `<!-- if briefs -->` `## The requirement (briefs)` と `{brief_rows}`（振り分けの段は義務の単位の全部、ほかの段は今の単位と一緒に直す単位。項目のほかの単位には「今は直すな」）。
3. `<!-- if rejected -->` `## Why the machine rejected your previous answer (fix it and return the whole answer for this phase again)` と `{rejection}`（← state の `reason`。今と同じく前の回の理由だけ。段が進むと空）。
4. `<!-- if policy -->`／`<!-- if no_policy -->`・`<!-- if request -->`／`<!-- if no_request -->`（2.3 の 8 と同じ文）。
5. `## What this role does`（今の `tdd-head` の役の段落と「毎回全部読め」。今の「2 回目からは変わった物だけを載せる」は外す。13.2 の 3）と `## What to read`（`{judgment_file}`・`{open_units}`・`{plan_file}`・`{policy_path}`・`{notes_file}`）。
6. `{part:brief}` と `{shared:writer-rules}`（2.3.1。`rules`・`conflict` はいつも真、種類は `kinds_now`）。
7. `## Reading for this loop (wins over the rules above)`（今の `tdd-remap`）。
8. `## The borrowed seat`（今の `seat.section("tdd")` の決まった文: Skill の道具で `{skill}` を読めの 1 文・勝ち負けの文）と `{seat_notes}`（← seams.json の "tdd" の効く所と効かない所の行）と `{unattended}`（← `seat.overlay_body(seat.OVERLAY_KINDS["tdd"])`）。
9. `## The promise of this phase` と `<!-- if phase_route -->`・`<!-- if phase_test -->`・`<!-- if phase_fix -->`・`<!-- if phase_refactor -->` の 1 つ（今の `tdd-phase-*`）と、いつもの段落（今の `tdd-phase-all`）。
10. `## What to do in this phase` と段ごとの段落（今の `tddloop.DO[phase]` を md の 4 つの段落に。真偽は 9 と同じ名）。`<!-- if gate -->` test_cmd の関門の 1 文と `{test_cmd}`（fix と refactor の段で関門が on）。
11. `<!-- if phase_route -->` `## Units you owe a fix` と `{owed_units}`。`<!-- if current -->`（振り分けでない段）`## The current unit` と `{current_unit}`、`<!-- if together -->` `## Units to fix together with the current unit` と `{together_rows}`、`<!-- if named -->` 名指しのテストとテストのファイル（凍っている）の行 `{named_rows}`。
12. `<!-- if handoff -->` `## Handoff from the previous units (written by the machine from the state)` と `{handoff_rows}`。`<!-- if later -->` この後の tdd の単位（今は手を付けるな）と `{later_rows}`。
13. `<!-- if tests_how -->` `## How the tests were run before the fix` と `{tests_how}`。
14. `## How to run the tests` と `{runner_cmd}`（実行器のパス。JUnit の書き先は作業ツリーの外。機械は名指しを絶対パスの node id で後ろに足す）。
15. `## The JSON to return` と段ごとの返す形（今の `tddloop.RETURN[phase]` を 4 つの段落に）と申し出の形（今の `RETURN_CONFLICT`）と「返すのは上の JSON だけ」（今の `tdd-end`）。
16. 言語の 1 文と `{lang}`（`units[].why`・`direct_why`・`red_quotes.*.why`・`what`・`refactor.why`・`why_both_cannot_hold`・`bash_writes[].why`）。

### 4.4 返す形

今の `&tdd_reply` のまま（`phase` enum route|test|fix|refactor|conflict と、units・unit_key・test_files・tests・red_quotes・direct_why・files・what・refactor・between・why_both_cannot_hold・which_is_right・correct_lines・kind・bash_writes）。

### 4.5 描いた骨組み（例の run `1ba3f998-…` の `tdd-1/next.md`〔5 回目・段 test〕。対象の名とパスは置き換えた）

```markdown
# The TDD loop prompt (round 5, phase test)

## The requirement (briefs)
- 項目 3: <place>/brief-3.md（sha256 …・単位 frontend/…:AnnouncementsBanner — …）
…
There is no policy document. / The request file: <依頼のファイル> …

## What this role does …
## What to read …
## Brief rules … ## How to fix … ## Evidence … ## Conflict declarations … ## What to keep …
## Reading for this loop (wins over the rules above) …
## The borrowed seat
Read `test-driven-development` with the Skill tool and follow its steps. …
（{unattended}: 借りた superpowers のスキルを無人の役で読むときの読み替え …）

## The promise of this phase
- **test**: Write a test that reproduces the current unit's defect and fails now. …

## What to do in this phase
Write a test that fails now …

## The current unit
- frontend/…/announcements-banner.tsx:AnnouncementsBanner — 帯が 0 件の間、…

## Handoff from the previous units (written by the machine from the state)
- backend/…:active_announcements — …: 食い違いの申し出で止めた（木は単位の頭に戻した）: …
- 今の段: test・今の単位: …（振り分けは tdd）

## How to run the tests
At the repository root, `<実行器のパス> <JUnit XML の書き先>` …

## The JSON to return
{"phase": "test", "unit_key": "<今の単位>", "test_files": [...], "tests": [...], "red_quotes": {...}}
…
Write the human-facing fields (…) in 依頼文の言語（利用者の言語）. …
```

### 4.6 今の指示との差

今の指示は `workflows/fix/commands/fix-rules/tdd.md`（86 行）・`common.md`・`brief.md` と、`lib/tddloop.py` の `prep`（:776-845）の題と `DO`・`RETURN`・`RETURN_CONFLICT`・`TOGETHER_HEAD`・`HANDOFF_HEAD`（:633-736）・`lib/fixrules.py` の `tdd_render`・`start_lines`・`lib/seat.py` の `section("tdd")` に在る。

- 移した: Python の段ごとの文（`DO`・`RETURN`・`RETURN_CONFLICT`）と見出しを md の段落へ。Python に残るのは単位の行・引き継ぎの行・テストの名指しの行と、実行器の字。
- 消した: 「この会話の 1 回目は決まりを全部載せ、2 回目からは変わった物だけを載せる」（tdd.md:6-7。実際は毎回全部載せている。試験 `test_fix_rules.py:415` が「毎回全部」を固定）。`HANDOFF_HEAD` の注の「周ごとに新しい会話」（同じ単位の段は会話を継ぐ）。`DO[phase]` の「やり方は rules/tdd.md の test の段に従え」（役に渡していないファイルの名。同じ指示の 9 の段落を指す言い方に）。使われていない節 `tdd-lane`（tdd.md:75-86）。1 行目の HTML の印。
- 移した: 言語の 1 行を、この node の欄の名指しと `{lang}` に。
- 足した物は無い。英語にした。

### 4.7 元の works と graphloops の同じ場面

- 元の works の `tdd-start`・`tdd-loop`（`blk-fix.yaml:119`・`:151`。上限 40・同じ単位は同じ会話・3 回で諦め・軽量の単位は test_cmd を走らせない）と同じ。工場の #233 で同じ単位の会話を継ぐ形（tdd と tdd-new の振り分け）を戻した。元の TDD の並べの枝（`tdd-fork`・`tdd-lane-loop-1..3`・`tdd-join`・`tdd-rest-loop`）は組ごとの子の run に替わった（#94・`no-queue`）。
- graphloops の `workflows/review-loop/fix-tdd/block.json`（`rules/review-loop-tdd.py` の `red_problems`・`green_problems`、`RETRY_MAX=3`）。graphloops は毎回一式の全部で緑を求め、書きにくさの旗（`FRICTION_FLAGS`）と `surface_change` を持つ。工場は名指しと変更に直に関わる試験だけを走らせ、一式は後の工程で 1 回（元の works と同じ）。書きにくさの旗は元の works の時から無い（足さない）。

### 4.8 受け付け（tdd-step）

8.3。

### 4.9 試験

14 節。守る keep-essence: 1・2・3・4・5・6・8・11。

## 5 node の設計シート: ruler（裁定役）

### 5.1 役

裁かれていない食い違いの申し出に、持ち主の決まり（裁定の拠り所）で 1 件ずつちょうど 1 度、6 つの裁定（fix_test_scope・fix_code_as・ask_human・replace_query・fix_plan_item・rejudge）のどれかで答える。読むだけ。

### 5.2 port

`conflicts.json`（← 組の子と親が積んだ申し出。`source` は fix・tdd・tdd-gave-up・join-clash）・裁く id（← `ruling.prep` の `unruled`）・`judgment.json`・依頼のファイル（← `request`）・方針の文書（← `policy`）・brief（同じ place の `brief-<n>.md`）・前の回の却下（← `rejects-rule.json`）・`lang`。

### 5.3 組み立ての順（`prompts/ruler.md`）

1. `<!-- if rejected -->` `{shared:rejected}`（`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "rule"))`）。
2. `<!-- if policy -->`／`<!-- if no_policy -->`・`<!-- if request -->`／`<!-- if no_request -->`（2.3 の 8）。
3. `# Ruling on conflicts (a read-only role)` と役の段落と `## What to read`（`{conflicts_file}`・`{ids}`・`{judgment_file}`・`{request_file}`・`{policy_path}`。今の `ruler-head`）。
4. `## Ruling rules (what rulings rest on)`（今の `principles.md` の 8 つ。この node だけが使うので断片にしない）。
5. `## The JSON to return`（今の `ruler-reply` の全部: 形・裁定ごとの決まり・limits が足す範囲・名の重なりの裁き方・機械が確かめる事・`tdd-gave-up` の 4 つの順・`join-clash` の 7 つの順）。
6. 言語の 1 文と `{lang}`（`text`・`ask_why.line`・`request_searched`）。

### 5.4 返す形

今の `output_format` のまま（`rulings: [{id, decision, text, limits, grounds?, request_searched?, ask_why?: {changes (direction|scope|name_only), line}, query?: {how, counts, hits, misses}}]`）。

### 5.5 描いた骨組み（例の run `d31781b6-…` の `prompt-rule.md`〔2 回目〕）

```markdown
## Why your previous answer was rejected … （1 回目の拒否: …）
There is no policy document.
The request file: <依頼のファイル>（read it all first）

# Ruling on conflicts (a read-only role)
You are the ruler. …
## What to read
- The conflict file: <place>/conflicts.json — …
- The ids to rule: `c1-1, c1-2`
- The judgment file: <place>/judgment.json — …
…
## Ruling rules (what rulings rest on)
1. … 8. …
## The JSON to return
{"rulings": [{"id": "<申し出の id>", "decision": …}]} …
Write `text`, `ask_why.line`, and `request_searched` in 依頼文の言語（利用者の言語）.
```

### 5.6 今の指示との差

今の指示は `ruler.md`（75 行）・`principles.md`（23 行）と `lib/fixrules.py` の `ruler_prompt`・`start_lines`・`lib/rolekit.py` の `REJECT_LINE`・`LANG_RULE`。

- まとめた: 却下の 1 行（ファイルを Read させていた）を `{shared:rejected}` に。
- 移した: 言語の 1 行を、この node の欄の名指しと `{lang}` に。
- 消した: 1 行目の HTML の印。
- 足した物は無い。英語にした。

### 5.7 元の works と graphloops の同じ場面

元の `rule-loop`（`blk-fix.yaml:1729`。3 回まで・読むだけの opus/high・5 つの語）。工場は `rejudge`（#446）と `ask_why`（#721）を足した。graphloops に裁定役は無い（近いのは人の承認ノード `p2.human_gate`）。

### 5.8 受け付け（rule-accept）

8.5。

### 5.9 試験

14 節。守る keep-essence: 8。

## 6 node の設計シート: clash-fix と clash-ruled（合わせ役）

### 6.1 役

組の差分を順に親の作業ツリーへ当てて試験が赤になった（`red`）か字でぶつかった（`text`）組を、機械がもう一度当てた木の上で、その組が変えたファイルの中だけで直して前の組の直しと両立させる。直せなければ何も変えずに `cannot`。clash-ruled は、裁定役が直す裁定を出した組を、裁定の文のとおりに直す。

### 6.2 port

`clash-brief-<gid>.json`（← `clash.stage` と `clash.brief`。組の単位・控えの差分・触ってよいファイル・前の組も変えたファイル・ぶつかりの種・赤の文・印を書いたファイル・名指しのテスト・戻せた組。ruled は裁定）・控えの差分 `join/<gid>.diff`・却下の控え `rejects-clash-accept-<gid>.json`（ruled は `rejects-clash-ruled-accept-<gid>.json`）・`values.json`（方針・依頼・`lang`）。

### 6.3 組み立ての順（`prompts/parts/clash.md`。2 つの node の md は `{part:clash}` の 1 行）

1. `<!-- if rejected -->` `{shared:rejected}`（`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "<accept>-<gid>"))`）。
2. `<!-- if policy -->`／`<!-- if no_policy -->`・`<!-- if request -->`／`<!-- if no_request -->`。
3. `<!-- if first -->` `# Merging groups (the merger)`（今の `clash-head-first`。材料の欄の説明と `{brief_file}`・`{patch_file}`）。`<!-- if ruled -->` `# Merging groups (the merger after a ruling)`（今の `clash-head-ruled`。`rulings_file` の欄の説明を足した物）。
4. `## The merger's rules`（今の `clash-keep`）。
5. `## The answer`（今の `clash-reply`）。
6. 受け付けが照らす事と、3 回の却下か `cannot` の後に起きる事（今の `clash-tail`）。
7. 言語の 1 文と `{lang}`（`how`・`bash_writes[].why`）。

### 6.4 返す形

今の `&clash_reply` のまま（`{handled (fixed|cannot), how (20 字以上), files, bash_writes?}`）。

### 6.5 描いた骨組み（記録の在るどの run でも合わせ役は走っていない。例の run `d31781b6-…` の組 `g1` に仮の値を足した。仮の値: 組 `g2` が `g1` と同じ `lib/seal.py` を変え、当てた後の名指しのテストが赤）

```markdown
There is no policy document. / The request file: <依頼のファイル> …

# Merging groups (the merger)
You are the merger (a writer). …
- Material: <place>/clash-brief-g2.json (Read it. JSON)
  - `group_id`・`unit_ids`: …
  - `files`: **all the files you may touch** …
…
- The kept diff: <place>/join/g2.diff

## The merger's rules …
## The answer
{"handled": "fixed" or "cannot", "how": "…", "files": [...], "bash_writes": [...]} …
The machine checks … After 3 rejections or `cannot`, …
Write `how` and `bash_writes[].why` in 依頼文の言語（利用者の言語）.
```

### 6.6 今の指示との差

今の指示は `clash.md`（60 行）と `lib/clash.py` の `prompt`（:371-385。`rulebook.render` に `HEADER`・却下の 1 行・`start_lines`・言語の 1 行を足す）。

- まとめた: 却下の 1 行を `{shared:rejected}` に。2 つの役の頭（first・ruled）は同じ md の 2 つの段落。
- 移した: 言語の 1 行を `{lang}` に。
- 消した: 1 行目の HTML の印。
- 足した物は無い。英語にした。合わせ役の loop は `fresh_context: true` なので、md は会話の継ぎを前提にしない（今と同じ。同じ組の出し直しは却下の段落で前の理由を渡す）。

### 6.7 元の works と graphloops の同じ場面

元の works は並べの枝の締め `tdd-join`・`fix-join` で、ぶつかった枝を順の輪 `tdd-rest-loop` で直し直した。工場は持ち主の決め `clash-goes-to-ruling` に従い、合わせ役が直せなければ裁定へ回す形にした（#446・#607）。順の輪で直し直さない事は棚卸しの F410 で持ち主の確かめ待ちのまま（この block は今の形を写す）。graphloops の `lane_merge`（`rules/review-loop.py:1309`）は変異の検算の線の合流で、別の能力。

### 6.8 受け付け（clash-accept・clash-ruled-accept）

8.6。

### 6.9 試験

14 節。守る keep-essence: 3（許しの無いテストのファイルを拒む）・5・8。

## 7 script の node

どの script も、頭の 2 行で `workflows/.shared` と `workflows/fix` を `sys.path` に足し、`ports` を import してから `src` を呼ぶ（world と同じ）。今の script が `boundary.place("fix")` で取っていた置き場は `ports.place()`、`boundary.work_tree()` は `Path.cwd()`（Archon の cwd）、`boundary.drop_runner_env` は `ports.drop_runner_env`、`boundary.SKIP` は `(ports.RUNTIME_COPY_PREFIX,)` に替える。誤りの扱い（落ちる node・落ちない node）は今のまま。

- `intake.py`: `INPUTS_MODE` ほか 1.2 の全部を字のまま読み、`src.intake.read(raw)` に渡す。`mode` が whole なら `judgment` が要る、group なら `group` が要り、`out_dir` が空の group は `judgment` も要る（無ければ `ok: false`・「入力 <名>: whole の形には要る」の形の理由）。`json` の形の port は `ports.json(raw, "<名>.schema.json")`（空の字は渡されていないと読む）、`file` は `ports.file`、`flag`・`choice`・`text` はそれぞれの口。`src.runvals.write(place, …)` で `values.json`（1.4。`reuse_key` が空なら `os.environ["WORKFLOW_ID"]`）、`intake.json` に読んだ値（judgment などは値か読んだパス）を書く。返り `{ok, whole, reason}`。落ちない（`ports.run`）。
- `prep.py`: 今の `prep.py` と同じ順（1 書き込みの記録を空で作る → 2 判定・判定の写し 3 つ〔ties・materials。深さの写しは書かない〕→ 3 修正案の欄と凍結の印 → 4 `fix-plan-reply.json` → 5 `p2.plan_review.json` → 6 `ripple.json` → 7 `answers.json` → 8 `only-items.json` → 9 `prior` が在れば `src.carry.adopt(place, prior, only_items, repo)`（`prior/<k>/` に置いて今の `adopt_prior_pass` と同じ写し）→ 10 `baseline.json` → 11 `fix-ignored-before.json` → 12 `base-rev.json` → 13 始めの木 → 14 `human-notes.md` → 15 `groups/` と `groups.json`）。値は `intake.json` から（今は `INPUTS_<名>` の pointer を `boundary.resolve` で開いていた）。今の落ちる時（判定が無い・修正案の形・only_items の形・prior の束の形・git の誤り）は落ちる（exit 1）。並べるかは `board.parallel`（組が 2 つ以上・port `parallel`・`git remote` が空でない）。
- `group_start.py`: 今の `group_start.py` と同じ順（並べない子の前の組の止め #576 → 書き込みの記録 → `from_tree` の写し → 入力の写し〔`out_dir` が在れば `board.adopt_inputs(Path(out_dir).parent, place, repo)` が `values.json` も写す。`intake.json` は写さない。空なら `board.prep`〕→ 並べない子の自分の前の試みを戻す → `fix-ignored-before.json` → 始めの木 → `groups.json` → `group-start.json` → `tdd.start`）。`tdd.start` の `unit_depths` は `values.json` の `skip_rerun` から `{key: "軽量"}`（今の `fixboard.unit_depths` の形。省く単位だけ）。使い回しは `tree_run.reuse_place(values.reuse_dir, values.reuse_key, rerun=bool(os.environ.get(tree_run.RERUN_ENV)))`。対象のテストを起こす前に `ports.drop_runner_env(values.user_env_dir)`。返りを `tdd-start.json` に書く（今のまま）。
- `tdd_prep.py`: 今の `tdd_prep.py` の値の組み立て（`tdd.prep` の段落の真偽と値）を `src.prompts.tdd_values(place, state)` にし、`prompt.emit("tdd-new" if new_unit else "tdd", values, when, prompt.round_of(…))` で組む。済んだ輪（resume で 1 周目から回り直した）は `{prompt: "", go: false, new_unit: false}`（今の早抜け）。brief の控えが壊れた・座が組めない・指示が組めない時は `prompt-error.json` に書いて落ちる（今の `Broken` で落ちるのと同じ）。返り `{prompt, go, new_unit}`。`new_unit` の決め（状態の `session_key` と鍵 `tdd-<k>:<route か今の単位>` の比べ）は今のまま。
- `tdd_step.py`: 今のまま（`tdd.step` → `tdd.flush_unsent` で `conflict.park_claims` → 却下が在れば `tdd-step-reject-<n>.md`）。返り `{ok, done, reason, reason_file, phase}`。
- `fix_prep.py`・`fix_ruled_prep.py`: 今の順（頭の木の控え `fix-head.json`〔ruled は `fix-ruled-head.json`〕と `skip-before.json` は 1 回だけ → 直す義務が空なら go: false → brief を切る → 続きの周〔相談の答え・はみ出しの積み・はみ出しの答え〕か、全部の決まりの周か → 下請けのファイル〔`src.prompts.g1_files`〕・ライブラリの文書〔`libdocs`〕・相談の控え〔`consult.json`〕→ `consult_skip`）。指示は `src.prompts.fixer_values(place, pass_)` と `prompt.emit("fixer"` か `"fix-ruled", …)`。ruled の go は今のまま（PRIOR でも join-clash でもない直す裁定が在る時だけ）、ruled の 1 周目は `conflict-rulings.md` が無ければ書く。続きの周の `iteration` は今と同じく数え直さない。返り `{prompt, go, iteration}`。
- `consult_check.py`・`consult_accept.py`: 今のまま（`board.consult_ask` で頼みを確かめて聞く頼みが在れば `prompt.emit("consult-answer"` か `"ruled-consult-answer", src.prompts.consult_values(…))`、`consult.settle` で答えを確かめて控えに残す）。`consult_check` の返り `{consulted, go, prompt}`（今の `prompt_file` は `prompt` に替える）、`consult_accept` は `{consulted, answer_file}`。
- `fix_accept.py`・`fix_ruled_accept.py`: 今のまま（8.2）。
- `join.py`・`clash_prep.py`・`clash_accept.py`・`conflict_check.py`・`rule_prep.py`・`rule_accept.py`・`clean.py`・`assert_changed.py`・`group_end.py`: 今のまま（8.5〜8.7 と、`join` の当てる順・確かめ直し・戻し・控え・写しは 12 節の E）。`clash_prep.py` は `prompt.emit("clash-fix"` か `"clash-ruled", src.prompts.clash_values(…))`、`rule_prep.py` は `prompt.emit("ruler", src.prompts.ruler_values(…))` で返り `{prompt, go, iteration}`・`{prompt, iteration}`（今の `prompt_file` は `prompt` に）。`rule_prep.py`・`tdd_prep.py` が今している `rulebook.CANON`・`fixrules.SHARED`・`RULES_DIR` の差し替えは要らない（md は `prompt` の口が読む）。`join.py` と `clash_accept.py` の走らせ直しの test_cmd は `board.rerun_cmd` が `values.json` の `skip_rerun` で決める（今は単位の深さの控え）。
- `fix_reads.py`: `board.collect_reads(place, writelog.log_here(), repo=…)`。段ごとの `must_read` は判定の写しと今の周の brief のファイル（指示は字で渡すので指示書のファイルは無い）。`own`（その役の session を見分ける材料）は今の指示書のファイルの代わりに、その段の brief のファイル（brief の無い run は判定の写し）。`since` は今のまま段の頭の印の時刻（13.1 の 10）。落ちない（`reads.guarded`）。
- `finish.py`: `src.finish.collect(place, whole)`。今の `collect.py` の `block()`・`fields()`・`group()` と同じ順で書いて読む（2 回目の段なら `replan.close` → `closure.json` → `allowed-tests.json`・`accept-trace.json` → `fix.diff` → `tdd-unit.json`〔今の `tdd-unit` の node の中身〕→ `frozen.json` → `fix-reply.json`〔`board.group_fix_reply`〕→ `scope.json`〔`fixboard.scope_brief`〕→ `carry.json`）。差分の審査とレンズの控え（`delta-holes.json`・`lenses.json`）は書かない。`ok` は 1.2 のとおり。中の誤りは今の `fallback` と同じく落ちずに `ok: false` と理由（`fix-collect-error.txt` を指す `diff`・空の `allowed-tests.json`）。lib が読めない時の stdlib だけの返り（今の `ports()`）も残す。

## 8 受け付け

どの受け付けも、却下の理由の文は日本語のまま Python が組む（README 5.3）。却下は `rolekit` の控え（`rejects-<名>.json`）に積み、次の回の prep が全部（古い順）を `{shared:rejected}` に入れる（今は `rejects-<名>.md` のパスを指示の 1 行目で名指していた）。3 回目の却下で諦める（`rolekit.GIVE_UP_AFTER`）。諦めても run は止めない。

### 8.1 共通の確かめの順（修正役の受け付け `board.accept_reply`。今の `fixboard.accept_reply` の写しのまま）

確かめは全部回してから最後に 1 回だけ拒む（F131）。拒否の文は `FIX_CHECKS` の順の見出しで並べる（「全部を 1 回で直して出し直せ」の決まった文は md の `parts/fixer.md` の段落 `rejected`）。順と中身（どれも今の関数のまま）: consult（枠を使い切った後の consult。欄を外して続ける）→ frozen（`facts.check_frozen`。TDD の loop が凍らせたテストのファイル。許すのは `conflict.ruled_test_limits` の範囲だけ）→ writes（`writes.check`。記録の無い run は `fixboard.undeclared_writes`）→ conflict（`board.take_conflicts`。`conflict.problems_by_entry` の欄・語・名指しの現物の照らし）→ pack（`.archon/` の下）→ excluded（`board.check_excluded`。新しい: 並行 PR に回した hunk〔port `excluded`〕の行に、修正の段の始めの木から今の作業ツリーへの変更〔`git diff -U0` の旧い側の範囲〕が触れたら、hunk ごとに「並行 PR #<pr> に回した hunk <file>:<start>-<end>（<why>）を変えた」と名指して拒む。行の番号は並行 PR の確かめが走った時の作業ツリーの行なので、始めの木の中の位置は錨〔行の `sha256`〕で引き直して比べる〔2 回目の段や順に回す組の 2 つ目以降は始めの木で行がずれる〕。錨の無い行・錨が木に無い行は記録した行のまま、同じ中身が複数在れば記録した行に近い方。始めの木が無い・git が読めない・木にファイルが無い時は、通さずに照らせない訳を 1 行で拒否にする。外した hunk が無ければ照らさない）→ duplicate → not_opened → excused（`board.fix_duty`）→ scope（`scope.check`。範囲・out_of_scope・add と remove の symbol・tests の id・同名の定義・案の外の新しいテスト）→ tests（`tdd.selected_problems`。変更に直に関わる試験を走らせ、元で赤でなかった試験の赤を拒む）→ plan_faces（`board.plan_face_errors`）→ gates（`gates.problems`。受け入れのテストの base で赤・今の木で緑と、名指しの外の既存のテストの関数の本体の変更）→ closure（`board.closure_reply` と `unitrows.build`。閉じない defects の問い・数えられない問い）→ copy（`recount.accept_fix`。直す義務の単位の行・fix_closure の黙った値・interactions・bypass_tried・breaks.result・precedent・symptom の理由・coverage の母数と数え直し・clean なのに赤を見ていない・wrote_refs・差分が足した md のリンク）。

- はみ出しだけの回（`board.gather_overflow`・`split_rows`・`settle_overflow`）: 拒まず、まだ聞いていない物を相談に積み（拒否に数えない）、聞いた後の物は機械が戻して受け付け直す（F110・F111）。
- 1 回目の段で裁かれていない申し出が place に在れば、受け付けを抜けて裁定へ回す（`fix-parked-reply.json` を書く。F207。13.3 の 5）。裁定の後の新しい申し出は機械が ask_human に裁いて積む。
- 3 回目（`rolekit.is_last_attempt`）: 拒否の行を単位に結んで（`parking.settle`）、結んだ単位を足跡を共にする単位と一緒に段の頭の木へ戻し（`fix-parked-<n>.patch` に控える）、ask_human の申し出にして積み、残りの単位で頭から受け付け直す。止める単位が残らなければ義務の残りを全部止め、それでも残れば受けずに諦める（F133・F134）。
- 通った時: `fix-units.json`・`fix-reply.json`（ruled は `fix-ruled-reply.json`）・trace の行（`fix_accepted`・はみ出しの名指し・確かめずに受けた関門の訳・吸収した行）・`fix-unit-rows.json`。
- 相談の周（`consulted` が真）は受け付けを回さず拒否に数えない（F135）。返答が無い（修正役が飛ばされた）時は `fix-units.json` に義務の単位を not_done で書いて done（1 回目）・何も書かずに done（ruled）。
- loop の上限 12 は「拒否 3 回 + 相談の枠 9」（`consult.BUDGET`）。試験が `max_iterations` と照らす（14 節）。

同じ関門 `board.check_excluded` を、受け付けを通らない変更の最後の網として 1 度ずつ回す: 組の形では `group-end` が組の始めの木から今への変更を照らし、触れた hunk の行を組の結果の `mismatched` に載せる（最後の関所を開ける理由として人に届く）。全体の形では `assert-changed` が run の始めの木から今への変更を照らし、触れていれば `ok: false` と hunk を名指す理由を返す。TDD の役・合わせ役・裁定の後の修正役の変更がここで照らされる（受け付けの 1 か所だけだと、TDD の輪が組の単位を全部緑にして修正役が飛ばされた run で素通りした）。

### 8.2 fix-accept と fix-ruled-accept の違い

ruled は、直す義務が `board.ruled_owed`（戻せた組の単位のうち fixed でない物）、頭の木が `fix-ruled-head.json`、輪の状態が `board.ruled_states`（今の段の輪だけ。PRIOR の輪は凍結に効く）、fix_test_scope の範囲がいつも許しに入り、裁定の `limits` のパスが範囲に入る（F109・F217）。

### 8.3 tdd-step（TDD の loop）

今の `tddloop.step` の写しのまま（入口の 5 つ・振り分けの段 8 つ・test の段 12・fix の段 7・refactor の段 1・申し出 1 の 34 の拒否の規則。どれも `src/tdd.py` の同じ名の関数）。拒否は段ごとに数え（段が進むと 0 に戻る）、3 回目で: 振り分けの段は全部を direct にして済む・test と fix の段は木を単位の頭に戻し、機械の申し出（`tdd-gave-up`・needs_context）を 1 件積んで次の単位へ・refactor の段は緑の木に戻して次へ（F021・F024）。案を直して戻った単位が又落ちたら ask_human（F023）。実行器が JUnit を書かない・40 周に届く周は残りを direct にして済む（F027・F028）。却下の理由は state の `reason` に積み、次の周の指示の頭に入る（3 の段落）。

### 8.4 consult-accept（相談の答え）

今の `consult.settle`・`judge` のまま: decision が 3 語のどれか・reason が 10 字以上でなければ無効、allow は頼んだ物の中だけを許し（承認ノードの条件の頼みは根の外のパスだけを捨てる）、new_tests は頼んだ id で red か guard、allow で許した物が無ければ無効、答えの役が飛ばされたら unavailable。答えは trace の `plan_scope_asked` の行と答えのファイル `consult-<pass>-<turn>.md` に残し、合意は範囲の照らし（`planrange.with_agreed`）・テストの変更の許し（`conflict.agreed_permits`）・事後の関門が読む（F219〜F221）。

### 8.5 rule-accept（裁定役）

今の `ruling.accept_rule` のまま: 作業ツリーが `rule-tree.json` から動いた（読むだけの照らし。`status_guarded: true`）・id の過不足と重なり・fix_test_scope の limits・直す裁定の limits が現物のファイル・fix_plan_item が limits を持たず brief の行を grounds に挙げる・tdd-gave-up の fix_code_as の grounds・rejudge は join-clash だけで limits 無し・replace_query の問いを hits と misses と correct_lines で試す・grounds の現物・依頼の在る run の ask_human の出どころ・ask_why の有無と name_only・同じ項目に直す裁定と fix_plan_item を並べない・同じ組の join-clash の行の裁定を揃える（F209〜F214）。通れば `conflict.apply_rulings` と `conflict-rulings.md`。3 回目で裁かれていない申し出を全部 ask_human にして人に回す（F211）。控えが読めなければ done の拒否で人に回さない（今のまま）。

### 8.6 clash-accept（合わせ役）

今の `clash.problems` と `settle_*` のまま: 印が残る → 組の変えたファイルの外を触った（ruled は裁定の limits も許す）→ 許しの無いテストのファイル（組自身のテストのファイルは許しにならない）→ 申告の無い書き込み → 名指しのテストと変えたファイルに当たる試験を親の木で走らせ直して赤。`cannot` か 3 回の却下で組を当てる前の木へ戻し、組の単位ごとに `join-clash` の申し出を積んで裁定へ回す（ruled なら ask_human で人へ）。上限 9 周の周で残りの組を申し出へ回して抜ける（`limit` は `max_iterations` と同じ。試験が照らす）。

### 8.7 node の外の確かめ（落ちない node の守り）

- `conflict-check`: 子の申し出の名指しを親の作業ツリーと許した根（依頼のファイルと親と子の place）で照らし、行が無くなった申し出は落として `conflicts-dropped.json` に名指す（F208）。
- `clean`: 当たったままの組が在れば何も消さない。控えに無かった git が無視するファイルだけを消し、`.archon/` と前から在ったフォルダは残す（F418）。
- `assert-changed`: 戻せた組と裁定の後の返答の `changes[].files` が始めの木から本当に変わったか。申告が空なら、直す義務が残らず外れた単位だけの run だけを通す（F419）。比べの誤りは `ok: false`、ほかの誤りは落ちる（今のまま。YAML の注記は「比べが通らない時も落ちず」に直す）。

## 9 元の works と graphloops の同じ場面（block 全体）

node ごとの場面は 2〜6 節の 7。block 全体では:

- 元の works の `works/blk-fix/`（2082 行の 1 つの YAML。TDD の輪・修正役の輪・裁定・相談・後始末）と、別のブロック `blk-refix`・`blk-delta`・`blk-lens`。工場は差分の審査とレンズと手直しを fix の中に入れた（#94）。この block は元の割り方に戻る（差分の審査とレンズは別の block）。
- 元の並べ（1 つの run の中の枝 3 本・待ちの列・順の輪での直し直し）は、組ごとの子の run・合わせ役・裁定に替わった（持ち主の決め `no-queue`・`clash-goes-to-ruling`。#94・#446・#607）。並べの切り替え 2 語を 1 つにした事（F403 の 1）・順の輪で直し直さない事（F410）・子の作業ツリーを機械で片付けない事（F433）・当てた後の赤で今の組だけを戻す事（F411 の 3）・2 回目の段で base の結末を使い回さない事（F043）・書いた指しの読んだ記録を次の判定へ渡さない事（F128）は、棚卸しで持ち主の確かめ待ちのまま。この block は今の形を写し、変えない。
- 元の読んだ証拠は手直しの役と審査役の分も集めた（`refix-reads`・`review-reads`）。工場は修正役と裁定の後の修正役だけ（記録なし。（未確認））。この block も同じ。差分の審査の側は delta-review の設計書。
- 元の枝の役の sandbox の `failIfUnavailable: true`（元 `blk-fix.yaml:339`）は工場の書き手の起こし方に無い（記録なし。（未確認））。この block は今の起こし方を写す（足すと振る舞いが変わる）。
- graphloops の review-graph の修正の段（`p3.fix`・`fix-tdd`・`delta`）にあって工場に無い物（同じ周の 3 往復の擦り合わせと第三の目・変異の検算の線・書きにくさの旗・周を回すこと・毎回一式で緑）は、どれも元の works の時から無いか、line・chain・test-gate の持ち物。この block には足さない。
- この block が両方より良く、残す物: 食い違いの申し出と読むだけの裁定役・範囲の相談・組の並べと合わせ役・最後の回だけ名指しの単位を諦める・書き込みの出どころを拒否にする・凍ったテストとテストの変更を許す道が 1 本・赤の失敗の文の引用の照らし・閉鎖の数え直し・単位ごとの記録が報告と承認ノードに届く。

## 10 守る keep-essence

- 1 赤緑の機械の判定: `tdd.red_check`・`baseline_red.red_problems`・`green_problems`・`gates.problems` の red_green。試験 `tests/blocks/fix/test_tdd.py`（今の `lib/tests/test_blk_fix_tdd.py::TestRedCheck`・`TestUnitLoop`、`lib/tests/test_fix_gates.py::TestRedGreen` を写す）と、組 1 つの形の TDD の筋書き（14 節）。
- 2 元から赤のテストの区別（担うのは test-gate。fix は読み手）: `tdd._must_pass`・`selected_problems` の版の写しでの照らし。試験 `test_tdd.py`（今の `TestStart` の元の結末）。
- 3 テストの凍結と許す道は 1 本: `tdd._frozen_moved`・`frozen_problems`・`facts.check_frozen`・許しは lib の `conflict.test_permits` 1 つ（1.5.2）。試験は今の `lib/tests/test_tdd_frozen.py::FrozenRuledScopeCase`・`test_conflict_kinds.py::TestReplanState.test_permit_sources_are_read_in_one_place` を `tests/blocks/fix/test_frozen.py` に写し、「`src/` に `test_permits` の写しが無く、`src/` の許しの読みが全部 `conflict.test_permits` を通る」の yes/no を足す（`test_permit_path_is_one`）。
- 4 3 回拒まれたら諦める: `tdd._give_up`・`board.last_settle`・`park_units`・`ruling.accept_rule` の手渡し・`clash.settle_parked`。試験は今の `tests/workflows/test_fix.py::FixLoopScriptsCase.test_third_reject_gives_up_only_the_named_unit` と RolesCase の上限の照らしを写す。
- 5 書き込みの出どころ: `writes.check`（KEEP）・`fixboard.undeclared_writes`（lib）。試験 `lib/tests/test_writes.py`（KEEP）と `test_fix_accept.py`（今の `FixAcceptSeamCase` の undeclared）。
- 6 当たる試験を選んで回し、回さなかった試験を名で残す: `tdd.selected_problems`・`ci_left`・`final_left`・`board.tests_trace`（`accept-trace.json`）。試験は今の `lib/tests/test_tdd_outside.py` を写す。
- 7 class_query の数え直し: `recount.accept_fix`（KEEP）・`unitrows.build`・`board.closure_reply`。試験は今の `lib/tests/test_fix_units.py` を写し、`lib/tests/test_fix_seams.py::RecountSeamCase` を振る舞いの試験に作り直す。
- 8 食い違いの申し出と読むだけの裁定役: `conflict.problems_by_entry`・`board.take_conflicts`・`ruling.accept_rule`・YAML の `ruler` の `mutates_checkout: false` と道具（Read・Grep・Glob・WebSearch・WebFetch）。試験 `test_ruling.py`（今の `RulingSeamCase`）と、E7 の読むだけの印の検査（7.1 の今ある yes/no）。
- 11 直す単位ごとの記録が報告と最後の承認ノードに届く: 出力 `units`・`tdd_unit`・`closure`・`report`（11 節）。試験 `test_finish.py` の `UnitsReachReportCase`（出力 `units` の形と、`report` の TDD の行が `report.tdd_lines` の字のまま）。report の側の試験は report の設計書の 7 節。

## 11 報告の行（`src/report.py`）

`report` は次の順の日本語の行（どれも今の lib が組む字のまま）:

1. TDD のループの単位ごとの結末: `report.tdd_lines([(f"組 {g['group_id']}", g) for g in <tdd-unit.json の組>])`（今の `runreport._tdd_lines` の中身。段の名「修正の段」「案を直した後の修正の段」は line が節の見出しで付ける）。組の結果が無く `units` だけが在れば、今の `_tdd_lines` の代わりの行（「型つきの成果物 tdd-unit が一覧に無い」）は「組の TDD の記録が無い。修正の出力の単位の行で出す:」と単位の行に替える（成果物の名を持たない字）。
2. 確かめ直しの `test_cmd` の赤を戻さなかった文: 当てたままにした組の行の `test_cmd_notes` ごとに「組 <group_id>: <文>」（`report.test_cmd_lines`。21 節）。
3. 読んだ証拠: `reads-fix-block.json` の索引と `reads-<役>.json` ごとに、今の `runreport._evidence_line`・`_index_lines` と同じ字の 1 行（「<役>（<place の中の相対のパス>）: 渡した <n>・読んだ跡の無い <m>（…）」・測れない・落ちた）。README の report の設計書の 1.6 の「読んだ証拠の node を持つ block が自分の report の欄に組む」。

`freeze_off` は `report.freeze_lines(<1 と同じ組>)`。最後の承認ノードと報告の冒頭が今 `fixbeside` で組む行（閉鎖の数え直し・回さなかった試験・確かめずに受けた関門・範囲の相談・clean が消したファイル・許したテストの変更）は、1 回目と 2 回目の段を合わせて読むので line が出力の pointer から組む（line の設計書。`fixbeside.read`・`closure_lines`・`tests_left_lines`・`gates_lines`・`plan_ask_lines`・`always_rows` の行き先）。

## 12 今の works との比べ（能力の住処）

今の fix の能力の全部の行は、棚卸し `docs/plans/2026-10-13-capabilities/fix.md` の F001〜F435（193 行。A TDD の輪と事後の関門・B 修正役と修正の受け付け・C 申し出・裁定・範囲の相談・関所の答え・D 差分の審査・レンズ・手直し・E 組の並べ・後始末・変更の確かめ・返りの約束）と、作り直しの棚卸しで足した行（下の 12.6）。決まり: A・B・C・E の行は、今その行の住処の関数（棚卸しの「証」の試験が呼ぶ物）を 1.5.1 の写しの同じ名の関数が持ち、その試験を `tests/blocks/fix/` に写して照らす。lib のまま呼ぶ物（1.5.2）はその lib の関数が持つ。違うのは下に名指した行だけ。審査の役は、写しが元の関数と import の行・1.5.1 の (a)〜(f) の外で 1 字も違わないことを `diff` で見る。

### 12.1 A（TDD の輪と事後の関門）

- 住処は `src/tdd.py`・`src/gates.py`・`src/facts.py`（`tddloop`・`fixgates`・`factchecks` の写し）。
- 違う行: F025（軽量の単位は緑の後に test_cmd を走らせない）は、単位の深さの控え（`depth.json` と `head-depth.json` の `depth.omits`）の代わりに port `skip_rerun` で決める（line が同じ表から引く）。F045（盤面と包みだけが持っていた物）は今も無い。F026 の nice は `baseline_red` のまま、機械全体の枠 slotwrap は今も無い（`no-queue`）。F013・F041（回さなかった試験と確かめずに受けた理由を trace に）は今のコードのまま写す（棚卸しの後に `tests_trace`・`gates_trace` で戻っている）。

### 12.2 B（修正役と修正の受け付け）

- 住処は `src/board.py`（受け付け）・`src/rules.py`（値）・`src/scope.py`・`src/unitrows.py`・`src/parking.py` と、lib の `recount`・`writes`・`querytest`・`planbrief`・`planrange`・`libdocs`・`seat`。
- 違う行: F140（指示の組み立ての順）は 2.3 の md の並びに替わる（並びは今のまま）。F143・F144（下請けと借りた座）は、決まった文が md と `prompts/parts/` に、借りた型の字が値に分かれる（2.3.2）。F147（読んだ証拠）は session の切り方が変わる（13.1 の 10）。F100（事前の確かめのコマンド）はコマンドの字が変わる（1.5.5）。F139（仕組みを新しく作った時に止める・深さを上げる道）は fix の中に無く、出力 `changed` を line が読む（今の fix の中の道は `redepth` の信号だけだった）。F136（2 回目の段の控え）は今も無い（`replan_items` と `prior` で残す今の決めのまま）。F106・F107 は今のコードのまま。

### 12.3 C（申し出・裁定・範囲の相談・関所の答え）

- 住処は lib の `conflict`（1.5.2）・`src/ruling.py`・`src/consult.py`・`src/board.py`（`take_conflicts`・`gate_view`・`gate_asks`・`write_notes`・`consult_ask`）。
- 違う行: F216（2 回目の段が 1 回目の申し出と裁定を見る）と F018・F023・F044 の読み口は、前の段の place のフォルダの代わりに port `prior`（出力 `carry`）から写す（13.1 の 5）。F218・F222（裁定の後の修正役と相談の答えの役が前の会話を継がない）は今のまま（Archon で不可）。相談の答えの役が同じ周の修正役の会話から分かれて起きていた事は 13.3 の 1（#833 で直した）。F224・F225 の関所の答えは port `answers`・`request_answers`・`unattended` から（`asked` を付けるのは line）。F232（相談の番号の錠）は今も無い。

- 範囲の相談を減らす 2 つ（#687。run 9744721f・a170202f の相談 4 回の数えから）: 無人の run が推しで通した関所の条件（人の言葉でない再掲）は、その周にその項目で許しの行が既に在れば、答えの役に聞き直さない（`src/consult.py` の `gate_asks`・`_pushed_only`。人の条件は今までどおり聞く）。修正案の files の symbols に足すテスト（テストのファイルの change=add で名前が test で始まる）は、案のどれかの項目の `tests` にも書く（`lib/planmarks.py` の `gaps` の `_added_test_gaps`。案の受け付けで拒む。改名の新名が `tests` に無いと、修正役が相談で新名を頼むことになる）。symbols の add を足してよい新しいテストに機械が数える案は、TDD の赤の確かめを通らない試験が入る道になるので採らない。

### 12.4 D（差分の審査・レンズ・手直し）

- F300〜F330 は全部 delta-review と lens の block へ（1.5.3）。fix に残るのは、差分の審査の材料になる事実を出力で返すことだけ（`start_tree`・`reply`・`ruled_reply`・`scope`・`conflicts`・`checked`）。
- F316〜F320（`delta_review` の欄・軽量で省く・修正の後の信号で上げ直す・省いた事実を報告に）は、上げ直しと省くかを line が決め（README の形の直し 5）、欄は delta-review の出力になる。fix の中の `redepth` は消す。

### 12.5 E（組の並べ・後始末・変更の確かめ・返りの約束）

- 住処は `src/board.py`（組・戻し・結果）・`src/lanes.py`・`src/clash.py`・lib の `groups`・`unittrees`・`leftovers`・`itemcommits`。
- 違う行: F403（並べる条件）は始めの記録の `features_cut` の代わりに port `parallel`。F406（子が親の写しを読む）は `values.json` も写す（`intake.json` は写さない。13.4 の 2）。F408（組の結果のファイル）は今のまま。F416（型つきの成果物 `tdd-unit`）は成果物を出さず、`tdd-unit.json` と出力 `tdd_unit` だけ（13.1 の 7）。F420〜F425（返りの約束）は 1.2 の欄に替わる（`done` → `ok`、差分の審査とレンズの欄を外し、5 欄を足した）。F426〜F431（最後の承認ノードと報告に届く物）は fix が出力を返し、組むのは line と report（11 節）。F432（2 段の合わせ）は line。F433（子の作業ツリーの片付け）は line の終わりの node。F434（筋書き）は 14 節の筋書きに替わる。

### 12.6 棚卸しに無かった今の振る舞い（作り直しの調べで見つけた物。どれも写して残す）

- 組の子は `with:` の入力をほとんど読まず、親の place から全部を写す（`adopt_inputs`）。修正案の無い run では直す義務の単位が 1 つずつの組になる（項目が無いので `lanekit.groups` が 1 つずつにする）。
- 合わせの申し出の積み（組どうしの合わせ）は `lib/parking.py` でなく `clash.settle_parked`。`parking` は修正の受け付けの 3 回目にだけ使う。
- 子が結果を書かずに落ちた組が在ると、`join` は作業ツリーを変えずに落ちて run を止める（#576。resume で続きから回す）。
- 当たったままの組（戻せなかった組）が在れば、合わせ・裁定・後始末を全部止め、出力の `stop_reason` が `stopby.UNRESTORED`（#403）。
- 受け付けの回は指示の番号でなく控えの却下の数で数える（`rolekit.attempt`。resume で回し直しても数え直さない）。
- 裁定の後の指示は TDD の loop の要約を渡さず（「ループは走っていない」と読める）、下請けの節がいつも載る（13.3 の 6）。
- 事前の確かめのコマンドは受け付けと同じ口を乾いた形で当て、place を書かない（F100）。

## 13 自分で決めた事と、見つけた不具合

### 13.1 形と振る舞いの決め

1. `mode` の語を `whole`・`group` の 2 つにし、既定を `group` にした（今は空が全体・`group` が組）。根拠: README 8.3 の `mode choice(whole|group)` と、単独の run と standalone の筋書きは組の形（README 8.3）。line は include の時にいつも `whole` を渡す。
2. 深さの入力（`depth`・`head_depth`・`depth_record`）と fix の中の上げ直し（`redepth`・`delta-cut` の軽量で省く判断）を外し、port `skip_rerun` 1 つにした。`depth.json`・`head-depth.json`・`judge-depth-head.json`・`depth-raised.json`・`units.json` は書かない。根拠: README の形の直し 5（上げ直しの読み手を line 1 つに）。`units.json` は読み手が無い（入力 `units` も外した）。`skip_rerun` が効く所は今の `unit_depths` が効いた所と同じ（TDD の loop の test_cmd の関門と、組を当てた後の test_cmd）。
3. 始めの記録の代わりに port で受け、block の中は `values.json` 1 つを `src/runvals.py` だけが読む（今の `startrec.read(place)` の写しの代わり）。根拠: README 4.2・4.3。`startrec`・`gatepolicy` は line へ MOVE する物なので import しない。
4. 差分の審査とレンズの node を外し、出力から `done`・`delta_review`・`delta_holes`・`lenses`・`optional` を外し、`ok`・`reason`・`start_tree`・`reply`・`ruled_reply`・`scope`・`checked`・`carry`・`tdd`・`frozen`・`freeze_off`・`report` を足した。根拠: README 8.3（delta-review と lens は別の block）・4.1（`outcome_field` と `report`）・delta-review が fix の place を開かずに済む port（4.3）。
5. 2 回目の段への申し送りを、前の段の place のフォルダ（今の `prior_conflicts` の pointer の先のフォルダを名で開いていた）から、1 つのファイル `carry.json`（出力 `carry` → port `prior`）にした。根拠: README 4.3（port の値が指すファイルのほかは開かない）。中身と写した後の振る舞いは今のまま。ただし輪だけの carry（申し出の無い 1 回目の段の輪の状態）も 2 回目の段に写る（今は申し出の在る時だけ写した）。照らしが厳しくなる側の差。
6. 子の run の `with:` を `mode`・`from_tree`・`out_dir` と fan_out の `group` だけにした。根拠: 今の子は残りを読まない（12.6）。
7. node `tdd-unit` と型つきの成果物 `tdd-unit` を外し、`tdd-unit.json` は finish が書く。根拠: 成果物の読み手（`runreport`）は report の `sections` に替わり（report の設計書の 1.6）、r2 は出力 `tdd` の値を読む（`tdd_unit` の pointer も残す）。
8. `optional` の欄を外した。根拠: 落ちても line が進めてよい node（レンズ）が block を出た。`fix-reads` は落ちない。
9. 出力 `frozen` を足した（README 8.3 の出力に在る）。今は読み手が無いので pointer で返すだけにした。
10. 読んだ証拠の役の session を、指示書のファイルを読んだ session でなく、段の頭の印の後に brief（無ければ判定の写し）を読んだ session で見分ける。根拠: 指示は `prompt:` に字で入り、役は指示書を Read しない（README 5.2）。同じ place の TDD の役も brief を読むが、修正役の段の頭の印は TDD の loop の後に置くので、時刻で分かれる。同じ置き場で brief を読む相談の答えの役の会話は、見分ける印が brief を読んだことだけなので、修正役の読みに数えられる余地がある（受け付けの条件にしない記録なので、数え過ぎる側の差として残す）。
11. 指示は `prompt: "$<prep>.output.prompt"` で字で渡す（README 5.2）。修正役の指示は今 95 KB ほど（例の run の `prompt-p3.fix.md`）。止めた Archon は node の出力を走っている間は丸ごと持ち、記録には 32 KB の頭と、resume のための全部を別のファイルに置く（`dag-executor.ts:3030` の `PERSISTED_NODE_OUTPUT_MAX_BYTES` と `formatPersistedNodeOutput`）。本物の run で確かめる（16 節の 1）。
12. `conflict` と `unittrees` を写さず lib から呼ぶ（1.5.2）。根拠: keep-essence の 3 の「許す道は 1 本」と憲法の 4。README 9.2 の MOVE の範囲は組み込みで割る（16 節の 3）。
13. intake は落ちず、読めない port は `ok: false` と理由で出口に出す。全体の形の `prep` の落ちる時（判定の写しが壊れている等）は今のまま落ちる（`nodes-ok` が落ちを見せ、finish は `ok: false` で返す）。
14. 下請けの指示は `prompt.render_part` と `prompts/parts/` で組む（1.5.4。初めは `prompt.sub`・`prompts/sub/` を足したが、窓口の決めで plan-review の枝の口に揃えた）。根拠: 憲法の 2（Python は指示の文を持たない）。
15. 7.1 の 3 の照らしを広げる（14.3）。根拠: 全体の形の AI の node は `archon workflow test` で届かない（`workflow:` の node は筋書きで差し替えられず、全体の形は fan_out で落ちる。止めた Archon の `dry-run.ts` の `collectsStub`）、`tdd` は dry-run の loop が 1 周で済むので届かない（同じ単位の 2 周目にだけ回る）。

### 13.2 指示の決め

1. md は 1 node 1 本で、同じ文を使う node どうしは断片 1 つ（`fixer`・`consult`・`tdd`・`clash`・`brief`）を `{part:…}` で入れ、delta-review の手直しの役とも使う書く役の決まりは共通の断片 `writer-rules` 1 つ（1.5.4）。段落は入れ子にできないので、どの段落も Python が組んだ 1 つの名で選ぶ（2.3 の表）。`writer-rules` の中は段落の名が `conflict` と 4 つの種類だけなので、修正役の続きの周にも直し方と守ることが入る（2.3 の結び）。
2. 文の中の偽になった句を外した: 裁定の後の「あなたは新しい会話なので」・相談の答えの役の「（新しい会話）」・「修正案を書いた役がその会話の続きで答え」。根拠: 1 波目の作りから足した決まり（`fresh_context: false` の loop の役の md は新しい会話と言わない）と、今の振る舞い（13.3 の 1）。
3. TDD の役の「2 回目からは変わった物だけを載せる」を外した（実際は毎回全部載せる）。
4. 相談の答えの役に言語の 1 文を足した（README 5.3）。
5. 材料の行（brief・穴・範囲・テスト・ライブラリ・相談の頼み・単位・引き継ぎ）は今の lib が組む日本語のまま入る。lib を変えないため（README 11.1）。決まった文だけを英語にした。役が Read するファイルの決まった文は、#764 で md に移した（裁定の文の約束の句は `src/rulings.py` が `prompts/parts/ruling-promise.md`・`ruling-previous-reply.md` から組む。答えのファイルの頭は `answer-file-head.md`・`answer-file-row.md`。合わせ役の印の決まりは `parts/clash.md`）。brief の材料の字と、項目ごとの見出しと札は日本語のまま。
6. AI の node の `output_format` は今の字のまま写す（修正役の `precedent` の `allOf`・`if`・`then`・`not` も）。根拠: 形の検査の KNOWN_KEYWORDS の決まりは port の形のファイル（`schemas/`）の決まりで、役の返答の型は Archon が役に渡す型。同じ決まりは受け付け（`recount` の `precedent` の照らし。F120）にも在る。返りの node の `output_format` は `anyOf` を使わず `type: ["object","null"]` にする。
7. 借りた字（superpowers の型・無人の読み替え `lib/borrow/unattended.md`・seams.json の効く所）は md に写さず値で入れる（`{template}`・`{seat_body}`・`{seat_notes}`・`{unattended}`）。根拠: local-review の設計書の決めと同じ（源は `lib/borrow/` の台帳）。

### 13.3 見つけた今の不具合（作り直しでは直さない。作り直しの後に別に扱う）

どれも今壊れていると本物の run で確かめた物ではない。今の YAML とコードから、壊れる余地が在ると読めた物。作り直しは振る舞いを写すので、ここでは直さない。ただし 1 は、作り直しの後に #833 で直した（1 の本文は直す前の記録で、直した形は 1 の下の「直した形」。1 の費用は、後で本物の run の記録から数えた）。

1. （#833 で直した）相談の答えの役（`consult-answer`・`ruled-consult-answer`）が、同じ周の修正役の会話から分かれて起きる。YAML に `context` が無く、止めた Archon は順に並んだ AI の node に直前の会話を継がせ（`dag-executor.ts:10230-10248` の `isFreshSequential`）、名指しの無い継ぎは会話を分ける（`:2405` の `forkSession`）。答えの役は修正役の会話の全部を見たまま修正案の側として答え、次の周の修正役は答えの役の会話の分かれを継ぐ。指示の文は新しい会話のつもりで書かれている（今の `CONSULT_HEAD`）。直し方の候補: 答えの役に `context: fresh` を置くと、次の周の修正役が答えの役の会話を継ぐ（修正役の会話が切れる）。loop の外の node の `context: {resume: …}` も同じ loop の中では使えない。直し方は別に決める。
   - 費用: 修正役（群 `@wf-fix-writers`）と答えの役（群 `@wf-fix-consult`）は模型が違うので、答えの役は修正役の会話の履歴（1 回 13.6 万トークン前後）をキャッシュに当てられず、丸ごと書き直していた（#833。10-14〜10-23 の run で API の定価で約 $11.7）。
   - 直した形: 答えの役（`consult-answer`・`ruled-consult-answer`）を、修正の輪の本体の中の、答えの役 1 つだけを置いた 1 周の輪（`consult-ask`・`ruled-consult-ask`。`loop_group: {max_iterations: 1, fresh_context: true, until_bash: "true"}`）の中に置く。`when:` と `depends_on:` は輪に置き、受け付け（`consult-accept`・`ruled-consult-accept`）は輪の返り `$consult-ask.output`（本体の唯一の終わりの答えの役の返りの字。`dag-executor.ts` の `loopGroupIterationOutput`）を受ける。答えの役の指示・道具・模型・返りの形は変えない。
   - 効き方（止めた Archon の `dag-executor.ts`）: 輪の 1 周目は外の続き（輪の外で、直前の node の会話を次の node が継ぐ線）を持たずに起きる（`executeLoopGroupNode` の「lastSequentialSession: group.fresh_context || i === 1 ? undefined」）ので、答えの役は新しい会話。外の層の続きは返りに `sessionId` の在る node だけが替え（`runLayers` の「output.state === 'completed' && !isParallelLayer && output.sessionId !== undefined」）、輪の node の返りは人の答えを待って止まった時（`interactive_loop`）のほかに会話を持たないので、輪の後も外の続きは修正役の会話のまま。周の終わりの続き（`loopLastSequentialSession`）も修正役の会話で、次の周の修正役はそれを継ぐ。答えの役が飛んだ周（`when:` が偽）は今と同じ。入れ子の輪は止めた Archon の試験（`dag-executor.test.ts` の「EDGE H: nested loop_group」）が回す形。
   - 採らなかった形: 答えの役に `context: fresh` を置く（完了した節の会話が外の続きになり、次の周の修正役が答えの役の会話を継ぐ）。答えの役を並んだ層に置く（並んだ層は外の続きを空にし、次の周の修正役が新しい会話になる）。修正役に `context: {resume: …}` を置く（同じ輪の本体の節を名指せず〔`loader.ts` の「context.resume cannot name a source inside the same loop_group body」〕、輪の前の AI の node を名指すと 1 周目の修正役がその会話を継ぐ）。答えの役を `workflow:` の子の run にする（輪の本体に `workflow:` は置けない。`loader.ts` の「'workflow' (sub-run) is not supported inside a loop_group body」）。
   - E11: (1) Archon は「新しい会話で起き、外の続きを替えない節」の鍵を持たない（`context` は `fresh`・`shared`・`resume` だけ。`schemas/dag-node.ts` の `nodeContextSchema`）が、入れ子の輪は持つので、それを使う。部品を足さないので埋めの名簿（`docs/polyfills.md`）には載せない。(2) ASF の `.archon/workflows/sdlc/` に同じ場面（輪の中で別の模型の役を挟む形）は無い。(3) 要る: 2.7 と 3.7 の元の works は、範囲の相談を修正案を書いた役の会話の続きで答え、修正役は自分の会話を続けた。工場は修正案の役の会話を名指せない（3.7）ので答えの役は新しい会話で修正案を読み、修正役の会話のつながりは元のまま保つ（keep-essence の会話の続き。README 13 章の決め）。
   - 試験: `tests/blocks/fix/test_yaml.py` の `ConversationCase`（修正の輪の本体に直に置く AI の node は修正役 1 つだけ・答えの役は答えの役 1 つだけの 1 周の `fresh_context: true` の輪の中）と、`tests/blocks/fix/test_consult.py` の `ConsultWiringCase`（受け付けが答えの役を置いた輪の返りを受ける）。
   - 経緯の渡し方（持ち主の決め 2026-10-24。新しい会話の答えの役に、修正役の経緯を届ける）:
     - 修正役は範囲の相談の行に、`why` のほかに 3 つの欄を必ず書く: `tried`（範囲の中で試したこと。1 行 1 件）・`blocked`（範囲の中で直せない訳。どこまで直して何に当たったか。10 字以上）・`evidence`（根拠のファイルと行 `{path, line}`。1 つ以上）。返りの形（YAML の `&fix_reply` の `consult`）が必須にし、書き方は `prompts/parts/fixer.md` の「Scope consultation and the pre-check」が持つ。
     - 頼みの節（`consult_check`）の先の確かめ `consult.screen_ask` が、修正役の頼み（`origin` の無い行）の 3 つの欄を照らし、欠け・空・根の外のパス・1 未満の行が在れば答えの役に聞かずに断る（`consult.summary_problem`。断った訳は答えのファイルで修正役に戻る）。受け付けが積んだはみ出しの頼み（`origin: accept`）と人の関所の条件の頼み（`origin: gate`）は機械が立てた物なので照らさない。
     - 答えの役の指示は、頼みごとの節に 3 つの欄を載せ（`consult.asks_text`）、同じ run の前の相談と答えの一覧（place の `trace.jsonl` の相談の行。組の子の place から親へ写した行も。`consult.history_text`）を段落 `history` に載せる。修正案とリポジトリは今までどおり自分で読む。
     - 採らなかった形（どれも PR #844 のコメントに経緯）: 修正役の会話の写しを同じ模型の別の手番が引き継いで要約を作る形は、手番の返りの形が修正役と違うと Claude Code の道具の一覧（返りの形は道具 `StructuredOutput` として送られる）が変わってキャッシュが外れる（run `96f35545` の `review-fix` は、直前の `review` と同じ模型・同じ道具で返りの形だけ違い、2 秒後でもキャッシュの読み 0・書き込み 156,274）。修正役の中で `/compact` を掛ける形は、compact の呼び出しが節の道具の一覧で頭（キャッシュに当てる、送る中身の先頭）を組むので同じ訳でキャッシュが外れ、同じ返りの形を持たせると `/compact` が構造化の出力を返さず Archon が節を落とす。
   - 費用の見込み（相談 1 回あたり。式は持ち主の覚え書き〔LLM のワークフローの費用の設計の手引き〕、値は実測と仮置き。持ち主の決め 2026-10-24）: 今の形（答えの役が修正役の会話を引き継ぐ。会話のキャッシュの寿命 5 分）約 $0.79、この形 約 $0.29。実測の材料: run 11 本の相談 17 回で、答えの役の平均は手番 4.2・キャッシュの書き込み 141,275・読み 254,580・出力 1,680 トークン。
   - 次の run の記録で確かめること: 答えの役の書き込みの量（`node_complete` の `execution.spend.tokens` の `cacheWrite`。新しい会話なので、指示と読んだファイルの分だけに減るはず）と、答えの誤り（経緯を知らずに答えたために、修正役が同じ相談を出し直した・許すべき物を deny した・前の答えと食い違った）。
   - 試験（経緯の渡し方）: `tests/blocks/fix/test_consult.py` の `SummaryCase`（3 つの欄の欠けを断る・機械の頼みは照らさない・3 つの欄が答えの役の指示に入る）・`HistoryCase`（前の相談と答えの一覧）・`ConsultPromptCase.test_history_paragraph_carries_earlier_answers`（段落 `history`）と、`tests/blocks/fix/test_fix_accept.py` の `test_consult_ask_screens_and_writes_the_question`（`board.consult_ask` が 3 つの欄の無い頼みを断る）。
2. TDD の振り分けの段で役が作業ツリーを変えると拒むが、戻さない。3 回目の諦めでも戻さず、残った変更は修正の段の頭の木に入る（`tddloop._route`・`_abort`）。申し出の周（phase conflict）は書き込みの出どころを照らさない。
3. `tdd-step` は `tddloop.step` が返す書き込みの照らしの結果（記録の無い run の知らせ）を trace に積まない。修正の受け付けも記録の無い run の印（`writes.NO_RECORD_OP`）を trace に書かない（手直しだけが書く）。
4. `tdd-step-reject-<n>.md` の n は却下の回でなく呼び出しの総数。
5. 1 回目の受け付けは、その周の修正役が申し出を書いていなくても、TDD の loop が積んだ裁かれていない申し出が place に在れば loop を抜け、直す義務の単位を全部 not_done にする（`fixboard.take_conflicts` の `conflict.unruled`）。
6. 裁定の後の修正役の指示は TDD の loop の要約を渡さない（`summary_file` が空で「ループは走っていない」と読める）。
7. `decision_records_changed` は 6 つの印に入らず、前の控えとの論理和を取らない。
8. `assert-changed` の YAML の注記は「落ちない」と書くが、比べの外の誤りでは落ちる（7 節の注記の直しは注記だけ）。

### 13.4 作りで決めた事（実装の役。設計書が黙っていた・main の決まりと合わなかった所）

1. lib の `conflict` は、依頼のファイルを値で受ける（`conflict.problems`・`problems_by_entry` の引数 `request_file`・`cite_roots(request_file, root)`。申し出の名指しの根と、裁定役の ask_human の出どころの照らしが使う。組み込みで `conflict` が始めの記録を読まなくなった: integration.md の 4.3-追加-6）。この block は `runvals.read(place)["request_file"]` を渡す。始めの記録の形の写し `r1/start.json` は読み手が無くなったので置かない（`files.LIB_START` を外した）。
2. 組の子は親の `values.json` と上の写しを写すが、`intake.json` は写さない。根拠: 子の `intake.json` は子の port（`group`・`from_tree`・`out_dir`）を持ち、親の物で上書きすると組を失う。子の script は組と `out_dir` を自分の `intake.json`（`src.intake.load`）から読む（今の script は `INPUTS_GROUP` などを node ごとに読んでいた）。
3. port `answers`・`materials`・`request_answers`・`plan_review` の形のファイルは、.shared と ほかの block に同じ名で別の形が在るため `fix-<名>.schema.json` にした（形の名は pack の中で 1 つの決まり〔7.1 の 5〕。port `judgment` は .shared の物を `shared:` で使う）。旧: `gate-answers.schema.json` にした（1.2 の `answers.schema.json` は independent-design の block に同じ名が在り、形の名は pack の中で 1 つの決まり〔7.1 の 5〕に当たる）。
4. 写したモジュールの中の place の名の定数（`src/tdd.py` の `STATE`・`src/consult.py` の `QUESTION_FILE`・`src/clash.py` の `BRIEF`・`src/ruling.py` の `TREE` など）は写しのまま持つ（写しの中身を変えない決まりが勝つ）。`src/files.py` は今の `fixnames`・`fixbeside` の名と `fixboard` の置き場の名の定数（1.5.3）と新しい名を持つ。
5. run をまたぐ控えの根（ライブラリの文書。今の `boundary.shared_cache`、環境変数 `STATE_DIR`）は `.shared/ports.py` の `shared_cache()` を呼ぶ（`prep` の script が引いて `src/rules.py` に値で渡す。この block に写しは持たない）。
6. 修正役の指示は、範囲の節（段落 `scope`。真偽は承認済みの修正案が在るか）とテストの節（段落 `tests`。`rules` の時はいつも真）に分ける。根拠: 今の指示はテストの節（`planrange.tests_text`）をいつも載せ、範囲の節は修正案が在る時だけだった（2.3 の表）。修正案の無い run でも、変えてよい既存のテストと「これ以外の既存のテストの関数の本体を変える・消すと拒む」の文は指示に残す。
7. 下請けの審査役の頼み `prompts/parts/g1-review.md` も、2.3.2 の `G1_EXTRA` のほかに、今の `seat.g1_prompt` どおり `G1_SUB_RULES` と検索の決まり `{shared:query-rule}`（`spawns` は偽）を持つ（今の能力を落とさない）。
8. TDD の役の座の効く所と効かない所は、差し込み口を `{seat_applies}`・`{seat_not_applies}` の 2 つに分けた（見出しの文を md に置くため。4.3 の 8 の `{seat_notes}`）。修正役の座の型の名は `{seat_file}`（今の `PROMPT_HEAD` の `{file}`）。
9. 範囲の相談の答えの役の指示は、`board.consult_ask` が受ける口 `render`（`src/prompts.consult_render`）が md から組み、place の `consult-<pass>-<turn>-ask.md` と `<node>-prompt-<n>.md` の両方に同じ字が残る（今の `consult_ask` は指示書を書いていた）。頼みごとの節の材料は `src/consult.py` の `asks_text`（今の `question` から決まった文と答え方の行を除いた物）。
10. 「読む物」の空の値は `(empty)`（今の `rulebook.EMPTY` の「（空）」の英語）。
11. `src/tdd.py` の `prep` は材料（`{go, new_unit, state, path, briefs}`）だけを返し、`handoff_rows`・`together_rows` を足した（`handoff_lines`・`_together_lines` から見出しと決まった文を除いた行）。今の単位の行 `current_lines` の「上の『前の回の返答を機械が拒んだ理由』」は材料の日本語のまま（13.2 の 5）。
12. 裁定役と合わせ役の指示は `src/prompts.py` の `ruler`・`clash` が組む（script と試験が同じ口を呼ぶ。`prompt.render` は block の中の呼び手を要る）。
13. 出力の `tdd_refused` と受け付けの行の選びは、`lib/fixbeside.py` を import せずに `src/finish.py` が今の関数と同じ中身で組む（1.5.2 の「fixbeside は import しない」）。
14. 筋書き `tdd.stubs.yaml` の実行器のパス `.archon/workflows/works-factory/fix/fixtures/tdd-runner.py` は `tests/archon.py` の木の cwd から届いた（16 節の 2 は閉じた）。
15. 共通の断片 `writer-rules` は、delta-review の PR がまだ置いていない間に、この block の側で今の `common.md` から英語で書いた（見出しは 2.3.1・2.5 の字）。delta-review の側の写しと見出しの字が違う（`Divergence reports …`・`Evidence for a fix that cannot show …`）ので、2 つを合わせる時にどちらかに揃える（修正役・TDD の役の md と `brief.md` が見出しの字で名指す）。 組み込みの前に見出しの字を揃えることが必須（修正役・TDD の役の md と `brief.md` が見出しの字で名指す）。1.5.4 の「受けて使うだけ」と違って、この枝が置いている。
16. 共通の断片 `writer-rules` の「テストで赤→緑を示せない直しの証拠」は、頭の段落 `evidence`（4 つの種類のどれかが真の時）と、答えを書く場所の段落 `where_fixer`・`where_tdd`・`where_rework`（役ごとに 1 つだけ真）に分けた。続きの周は 4 つの種類が全部偽で、頭だけが残らないようにするため。使う block が自分の役の段落だけを真にする。食い違いの申し出の `conflicts` が無い役の言い方と「後の工程」の言い方も、特定の役・段を名指さない形にした。
17. 修正役と TDD の役の指示に、今の `seat.OVERLAY_HEAD` の後半（Agent で下請けを起こすなら、読み替えのファイルを Read せよと prompt に書け）を戻した。読み替えのファイルのパスは値 `{overlay_file}`（`spseam.BORROW_DIR` の `unattended.md`）で入れる。g1 の下請けには書かない（下請けのファイルが自分の works の決まりを持つ。修正役の md の g1 の段落の言い方のとおり）。
18. 言語の 1 行は今の `rolekit.LANG_RULE` と同じく「コード識別子・エラー文」も訳さない物に入れ、修正役の人に見せる欄の並びに `coverage.remaining`・`precedent.problem`・`precedent.searched` を足した（2.6・4.6 の「移した」の差の訂正）。
19. 続きの周（相談の答え・はみ出しの積み・はみ出しの答え）の指示は、読み落とした時の逃げ道として 1 回目の指示のファイル（place の `fixer-prompt-1.md`。fix-ruled は `fix-ruled-prompt-1.md`）を値 `{first_prompt}` で名指す（2.6 の「続きの周の『前に読んだ指示書』は『この会話で前に渡した指示』に」の差を、パスつきに戻した）。
20. `finish.py` の `_tdd_refused` の読めない時の文は、今の `fixbeside._load` と同じ区別（読めない・組めなかった・形が違う）にした。`CHANGED_MARKS`・`DRIFT_NOTE` は `board.py` の物を読む（二重に持たない）。

## 14 試験

### 14.1 standalone と筋書き（`workflows/fix/fixtures/`。どれも `exec-code: true` で AI の node だけを差し替える。prep は差し替えない）

- `standalone.stubs.yaml`: 組の形・実行器なし。入力は `mode: group`・`group: '{"group_id":"g1","unit_ids":["stats.py:4 mean"],"items":[]}'`・`judgment`（その 1 単位を [block] で持つ判定の JSON の字。`class_query` を持たない）だけ。`fixer` は `changes` 1 行の返答（受け付けが拒んでも筋書きは completed）。`reached: [intake, group-start, fix-prep, fixer, consult-check, consult-accept, fix-accept, group-end, fix-reads, finish]`。`resolved-text-contains: {fixer: <fixer の md の決まった文。例 "Do not say \"done\" without changing anything">}`。判定の字に `$ARTIFACTS_DIR` を入れ、字のまま届くことも照らす（world の 9.1 の 5）。
- `consult.stubs.yaml`: 組の形で修正案（`plan`・`fix_plan`。項目 1 つ・`allowed_paths: ["stats.py"]`）を渡し、`fixer` が `consult`（項目 1・`paths: ["README.md"]`）を返す。`reached` に `consult-answer`・`consult-accept`。`resolved-text-contains: {consult-answer: <consult の md の決まった文>}`。
- `tdd.stubs.yaml`: 組の形で `tdd_suite: .archon/workflows/<pack>/fix/fixtures/tdd-runner.py`（`tests/archon.py` の木の中の block の写しの置き場。`<pack>` は `pack.json` の `ours.pack`）。`tdd-runner.py` は第 1 引数に 1 件が failure の JUnit XML を書いて 1 で終わる（後ろの引数の名指しは読まない）。`tdd-new` は振り分けの段の返答。`reached` に `group-start`・`tdd-prep`・`tdd-new`・`tdd-step`・`fix-prep`。`resolved-text-contains: {tdd-new: <tdd の md の決まった文>}`。
- `whole-stops-at-fanout.stubs.yaml`: 全体の形。入力は `mode: whole`・`judgment`・`parallel: false`。`expect: failed`・`reached: [intake, prep]`・失敗の node `groups-seq`（dry-run は `workflow:` の node を回せない。今の `block-stops-at-fanout` と同じく入力の結びと prep を見る）。
- 筋書きは完了か失敗の node・`reached`・指示の字だけを見る。受け付けに拒否を足しても筋書きは直さない。

### 14.2 `tests/blocks/fix/`（script を子のプロセスで回す。始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡す）

今の試験を写して作る（README 9.5 の fix の行）。写す時に `boundary.place("fix")` のパスを place に、始めの記録の値を port に、`prompt_file` を `prompt` に替える。古い中身だけを見る試験（`rulebook.HEADER` の行・`fixrules` の節の id の数え・`direct.md`・`tdd.md` の字の照らし・`copied_rewrites` の写しの台帳 `CopiedTextsCase`・`fixbeside.PORTS`・`depth` の上げ直し）は写さない。

- `test_intake.py`: 形ごとの必須・読めない port の理由・`values.json` の中身・`reuse_key` の既定。
- `test_yaml.py`: loop の上限が定数と同じ（TDD 40 = `tdd.MAX_ITERATIONS`・修正と裁定の後の修正 12 = 3 + `consult.BUDGET`・裁定 3 = `rolekit.GIVE_UP_AFTER`・合わせ 9 = `limit`）・`nodes-ok` が `finish` と `fix-reads` のほかの全部に結ぶ・`finish` と `fix-reads` だけが `all_done`・`fresh_context: false` の loop で継ぐ役の直前に 2 つ以上の node の層が無い・`tdd-new` だけが `context: fresh`・裁定役と相談の答えの役が `mutates_checkout: false` で書く道具を持たない・役の模型と道具と sandbox と `skills` が今の YAML と同じ（今の `RolesCase` を写す）・`groups-par` と `groups-seq` が自分を起こし `all_success`・どの AI の node の `prompt:` も同じ loop の prep の `$<id>.output.prompt`。
- `test_prompts.py`: 9 つの AI の node の md を、その prep を子のプロセスで回して組み、決まった文が入ることを見る（place は試験が用意する: 判定・修正案・申し出・状態）。表 `RENDERED = {node: <md の決まった文>}` に、筋書きで届かない 6 つ（`ruler`・`clash-fix`・`clash-ruled`・`fix-ruled`・`ruled-consult-answer`・`tdd`）を置く（14.3）。修正役の続きの周（resume・queued・overflow_answer）で決まりの段落が入らないこと、食い違いの申し出の種類（`conflict.DIV_KINDS`）の全部が共通の断片 writer-rules と TDD の役の指示に `` `語` `` で在ること・brief の決まりと裁定役の決まりが種類と範囲（`limits`）の言い方をすること（`ConflictWordsCase`。keep-essence の 8。元 `test_conflict_kinds.py` の文の照らし）、ruled の 1 周目だけ裁定の文の段落が入ること、TDD の段ごとに 1 つの段だけの段落が入ること。
- `test_tdd.py`: 今の `lib/tests/test_blk_fix_tdd.py` の全部（153 本）と `test_tdd_outside.py`・`test_tdd_frozen.py`・`test_tdd_frozen_function_span.py`・`test_baseline_red.py` のうち tddloop を呼ぶ物。`skip_rerun` で test_cmd を省く試験を足す（今の `TestTestCmdGate` の軽量の行を port で）。
- `test_frozen.py`: keep-essence の 3（10 節）。
- `test_fix_accept.py`: 今の `FixAcceptSeamCase`（36 本）・`SettleOverflowSeamCase`・`OverflowTraceSeamCase`・`FactchecksSeamCase`・`FixgatesSeamCase`・`ScopeTextSeamCase`・`PlanrangeSeamCase`・`GateItemsSeamCase`・`lib/tests/test_fix_gates.py`・`test_plan_scope.py`・`test_fix_units.py`・`test_fix_duty.py`・`test_duty_sets.py` と、`tests/workflows/test_fix.py` の `FixLoopScriptsCase`・`FixAcceptCase`・`HandoffCase`、`OverflowRowCase`（今の `lib/tests/test_impact.py`。値を受ける新しい形）、`WritesLogNameCase`（今の `lib/tests/test_writes.py`。書き込みの記録の名は `writelog.LOG` の 1 か所）。
- `test_consult.py`: 今の `lib/tests/test_consult.py` の全部と `RolesCase` の相談の配線。
- `test_join.py`・`test_clash.py`: 今の `BlockScriptsCase` の join と conflict-check・`ClashScenarioCase`・`lib/tests/test_clash.py`・`test_lanekit.py`・`GroupScriptsSeamCase`、`test_fix_seams.py` の `LanekitSeamCase`（`lanes.groups`。`test_join.py`）。
- `test_fix_seams.py` の割り当て（integration.md の 4.2-6。KEEP のモジュールを試す `TestGroups`・`TestLeftovers`・`TestWritesSeams` は lib/tests に残る）: `GateAsksCase` → `test_intake.py`、`LaneChecksSeamCase` → `test_tdd.py`（`StepLogCase`。step の記録）と `test_fix_accept.py`（`SinceCase`。since）、`SmallGapsSeamCase` → `test_tdd.py`（`RunnerSeamCase`。3 回目で諦める）と `test_fix_accept.py`（`ParkingSkipCase`。parking）と `test_prompts.py`（`ConflictWordsCase`。申し出の種類の全部が決まりの文に在る）、`LanekitSeamCase` → `test_join.py`。
- `test_ruling.py`: 今の `RulingSeamCase`・`ConflictSeamCase`・`RulerTypeCase`・`FixLoopScriptsCase` の rule の部分。
- `test_group.py`: 今の `GroupChildScriptsCase`（26 本）と `GroupChildSeamCase`。
- `test_carry.py`: 1 回目の段の `carry.json` を 2 回目の段の `prior` に渡し、PRIOR の行・AMENDED への移り・前の輪の凍結が 2 回目の受け付けに効く（今の `RefixCase` と `adopt_prior_pass` の試験を、フォルダの代わりに束で）。
- `test_finish.py`: 今の `BlockScriptsCase` の collect の全部（差分の審査とレンズの欄の物を除く）・出力の欄が `output_format` と合う・`report` と `freeze_off` の字（11 節）・`UnitsReachReportCase`。
- `tests/blocks/shared/test_prompt.py` に `SubCase`（1.5.4）。

### 14.3 形の検査に足す物（`tests/layers/test_block_shape.py`）

7.1 の 3 の照らし（`check_standalone_renders`）に 1 つの道を足す: AI の node が筋書きで照らされなくても、その block の試験 `tests/blocks/<block>/test_prompts.py` の表 `RENDERED` に node の id が在り、その値が node の md の決まった文の中に在れば、照らされたと数える（表の行を照らすのは試験の側で、形の検査は表の在りと字だけを見る yes/no）。`RENDERED` の node が筋書きでも照らされていれば、表の行は要らない（どちらか 1 つ）。この block の PR が足す（`.shared/AGENTS.md` と `workflows/AGENTS.md` の決まりの 1 行も）。

### 14.4 指示の新旧の比べ（審査の役が 1 つずつ照らす、英語の md が持つべき今の指示）

2 つ目の commit の比べは作らず（持ち主の決め・今の波の速さ）、審査の役が古い指示（例の run の `prompt-p3.fix.md` など）と新しい指示（同じ値で組んだ物）を並べ、下の一覧の決まりが全部、意味を変えずに在ることを見る。2.6・3.6・4.6・5.6・6.6 に書いた差のほかに差が無いことも見る。

- 修正役（`fixer` の断片。今の `direct.md` の `fix-head`・`fix-keep`・`fix-ask`・`fix-consult-resume`・`fix-overflow-queued`・`fix-overflow-resume`・`fix-reply`）:
  - 読む物の 6 行（判定は背景で brief が正本・brief の無い run は判定が正本で先に全部読む・直す義務の key の集合は受け付けと同じ・修正案は全体を読まなくてよく plan_faces の key は貼った節に在る・方針の文書は先に全部読む・TDD の loop で直した単位は直し直さず changes に 1 行で red_seen を写し、そのテストのファイルを変えない〔rewrite_tests と fix_test_scope の範囲だけ例外〕・direct の単位はここで直す・承認ノードの答えのファイルは超えて削るな）。
  - 何も変えずに済んだと言うな。
  - 範囲の相談: 範囲を広げるかは修正案の側が決める・黙って範囲の外を変えるな・申し出で起動を終える前に先に相談せよ・1 件 1 項目の欄（item・paths・tests・new_tests・why・tried・blocked・evidence。後ろの 3 つが欠けた頼みは機械が断る。#833）・相談の周は受け付けが回らず作業ツリーの直しは残す・受け付けが見つけたはみ出しも機械が相談に回す・out_of_scope は外した理由が今立たない訳を書く・allow・deny・defer・答えが無い時のそれぞれの振る舞い・枠（9 回）を使い切った後は申し出・期待値を実装に合わせる書き換えを頼むな・下請けは相談できず報告する。事前の確かめ: 下書きを書いてコマンドを走らせ、`rejects` の行を直してから返す。
  - 続きの周 3 つ: 答えのファイルを全部読み、続けて直し、前と同じ欄の JSON を丸ごと返す・残りの相談の周・はみ出しの周は作業ツリーを変えずに同じ JSON・allow の外は機械が戻す（自分で戻すな）。
  - 下請けを回す 6 手順（項目の順に実装役を起こし、ファイルの中身を字を変えずに渡し、2 つ目からは引き継ぎの節を足す・差分のコマンドを走らせて審査役を起こし、実装役の最後のメッセージを貼る・審査が ❌ か Needs fixes なら起こし直し、3 回まで・3 回目も通らなければ symptom にして changes に載せる・出し直しと裁定の後は名指しの項目だけ・最後に差分を自分で確かめ、bash_writes を書く）と、loop で直した単位には下請けを起こさない・NEEDS_CONTEXT と BLOCKED は申し出（6 つの場面）・DISPATCH と DELEGATE の読み替えはこの役に効かない・下請けはさらに下請けを起こさない。
  - 返答の欄: changes は単位ごとにちょうど 1 行・unit_key は一字も変えずに・files は版から変わった物だけ・what・closure（sites を先に全部挙げ、1 か所ずつ退行を注入して赤→復元で緑・path の書き方と覆いの数え方）・coverage（class_query の在る単位は書かない・件数は機械が数える・塞いだ数の数え方・残すなら remaining・閉じたかは機械が決める・問いが正しい形に当たるなら申し出）・root_or_symptom・bypass_tried（「試していない」は書かない）・breaks（機械で引け・accepted）・precedent（一次情報を自分で引く・from_judge_row・not_found と searched）。周の全体: not_done・interactions（面ごと・3 つの突き合わせ）・fix_closure（clean は赤を見た時だけ・not_applicable は修正 0 件だけ）・plan_faces（key ごとに absorbed か declared）・wrote_refs（リンクにできない指し・機械が引き直す・Markdown のリンクで書け）・rejudge_requested・conflicts・consult・差分の形の変化の 6 つの申告（security_surface_changed は迷うなら true）・x_scalars。受け付けが見る物の結び。
- 修正役と TDD の役の共通の断片（今の `brief.md`・`common.md`）: brief の決まり 1〜8・直し方の 10・証拠の 4 つの種類と書く欄・食い違いの申し出の全部（6 つの kind・query と correct_lines・population の時の写し方・機械が名指しを照らす・人に聞きたいことの行き先・両方成り立つなら申し出でない）・守ることの 5（テストを消すな緩めるな・当たる試験だけを回す〔絞る手が無い時だけ一式を 1 回〕・元で赤だった試験は追わない・直しても消えない赤は unnamed_test_broke・Edit と Write で書く・git commit しない・作業ツリーの外を書かない）。
- TDD の役（今の `tdd.md` と `tddloop` の `DO`・`RETURN`）: 1 回の返答で進めるのは 1 段・赤緑は機械が決める・毎回全部読め・読み替えの 5（欄は what へ・direct の理由の欄と direct_why で戻る道と約束の在る単位は not_red・テストを回せは fix と refactor の段だけ・PYTHONDONTWRITEBYTECODE と JUnit の書き先・申し出の返し方）・段の約束 4 つと「一緒に直す単位」「この後の単位に手を付けない」・段ごとにする事と返す JSON・申し出の形。
- 相談の答えの役: 修正案を自分が書いた物として扱う・決めるのはあなた・out_of_scope の考え直し方とほかの項目の out_of_scope を allow した時の効き方・頼まれた物の中からだけ許す・承認ノードの条件の頼みは要る物を自分で挙げてよく、関わらない条件は deny・欄の決まり（decision の 3 語・paths・tests・new_tests の red と guard・spec・reason 10 字以上・期待を実装に合わせる許しを出すな）。
- 裁定役（今の `ruler.md`・`principles.md`）: 読むだけ（機械が前後を比べて拒む）・読む物（ruling が null の行だけ・依頼に先に答えが在ればそれで裁き grounds に挙げる・名指しは全部開いて確かめ言い分を信じるな・brief を開く）・裁定の拠り所 8 つ・返す JSON の形と 6 つの裁定ごとの決まり・limits が全部の変更に効く範囲で out_of_scope に勝てない・名の重なりは人に回さず自分で裁く・機械が確かめる事・tdd-gave-up の 4 つの順・join-clash の 7 つの順。
- 合わせ役（今の `clash.md`）: 材料の欄 11（ruled は rulings_file も）・先に読む物と崩れた前提を確かめる・印の解き方・files の外を変えない・前の組の直しを消すな弱めるな・テストを緩めるな・許しの無いテストのファイルを変えない（組自身のテストは許しにならない）・名指しのテストを自分で走らせる・決まりの中で直せなければ何も変えずに cannot・返答の形・3 回の却下か cannot の後の行き先。

## 15 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-fix --cwd <対象> \
  --input mode=group \
  --input group='{"group_id":"g1","unit_ids":["<単位の key>"],"items":[]}' \
  --input judgment=<判定のファイルのパス> \
  --input test_cmd='python3 -m unittest' --input tdd_suite=<実行器のパス>
```

組 1 つを直す（out_dir が空なので、組の結果は place の `groups/g1/result.json`）。全体の形は単独の run では回らない（Archon が先祖と同じ名の子を拒む）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。

## 16 未確認

1. 95 KB ほどの指示を `prompt: "$<prep>.output.prompt"` で渡した時に、役に全部が届くか（13.1 の 11。止めた Archon の源では走っている間は丸ごと持つ）。本物の単独の run（README 11.2）で `fixer-prompt-<n>.md` と役の会話の頭を照らす。
2. （閉じた。13.4 の 14）`tdd.stubs.yaml` の実行器のパス（`.archon/workflows/<pack>/fix/fixtures/tdd-runner.py`）が、`tests/archon.py` の木の cwd から届くか。
3. 組み込みで `conflict` を行の形（KEEP）と決めの部分（fix の `src/`）に割る時、`planrange`（delta-review も使う）が `test_permits` をどこから呼ぶか（keep-essence の 3 の 1 本を保つ割り方）。
4. line の上げ直しが、今 fix の中の `redepth` だけが数えた「修正役の異議」（出力 `objection`）を信号に足すか（line の設計書）。
5. delta-review の設計書が、fix の出力の `start_tree`・`reply`・`ruled_reply`・`scope`・`conflicts`・`checked` で足りるとするか（今の delta-review の材料は fix の place の `fix-reply.json`・`p2.plan_review.json`・`conflicts.json`・`trace.jsonl` の合意・方針を読んでいた）。足りなければ fix の出力の欄を足す（この設計書を直す）。
6. 材料の行の札を英語にするか（13.2 の 5。組み込みで lib の文を md へ出す時）。
7. 13.3 の不具合の直し方（1 の相談の答えの役の会話は #833 で直した。本物の run で、答えの役の会話が新しく、次の周の修正役が修正役の会話を継ぐことは照らしていない）。
8. 棚卸しで持ち主の確かめ待ちの 6 件（9 節の 2 つ目の項）は、この作り直しで変えない。

## 17 関わる試験だけで元の結末を取る（2026-10-20。持ち主の決め `related-tests-only`）

- 何を: `group-start` が TDD の輪の頭で一式を 1 回走らせて取る元の結末（`tdd.start` の `run_suite`）を、(3) の道（`test_cmd` が空で、対象の根に `.review-checks.json` が無い run）では、組の単位が触る所に関わる試験だけにする。道 (1)(2) は変えない。詳しい決めと選びは `docs/design/test-gate.md` の 14 節。
- (3) の道かは fix が自分で決める: `related.applies(repo, values.test_cmd)`（`lib/related.py`）。test-gate の `by` を fix の port で運ばない。
- 起点: 組の単位の約束（`plan_contract` の `files` の行のパス。約束が無い単位は起点を足さない）。`related.pick(repo, rev="HEAD", seeds=<起点>, cache_dir=<置き場>/impact)` で選び、`related.args` を `run_suite` の `args` に、`only=True` で走らせる。選べない（`whole`）か、起点が 1 つも無い時は、今までどおり一式。選びが空（関わる試験が無い）なら、元の結末は空の一式でなく `{}` として輪を回し、受け付けと最後のテストの段が確かめる。
- 元の結末が関わる試験だけになるので、輪の緑の回の「元の結末に載ったモジュール」（`_reached`）は、選んだ試験のモジュールに絞られる。届かない試験・元の結末の外の試験は、今までどおり受け付けの `selected_problems` と最後のテストの段が確かめる。
- 状態 `state.json` に `related`（選びの結果）を置き、報告の節「走らせなかった範囲」が読む。
- 緑の確かめ（元の結末が関わる試験だけで、今の回が全部の試験の場面）: 関わる試験を選べなかった回（`_reached` が全部の試験）は、元の結末に無い試験も走る。この回の緑の確かめ（`baseline_red.green_problems` の `narrow`）は、比べる範囲を元の結末に載った試験・名指し・前の単位が赤から緑にした試験（`also`）に限る。範囲の外の赤では拒まず、一式の終了コードも範囲の結果が全部通っていれば問わない。元の結末が全部の試験だった PR の前の振る舞いに戻す向きの直し。

## 18 確かめ直しで前から同じ形で赤の名指しを、組を戻す理由にしない（2026-10-23。#837）

- 出どころ: issue #837（この節の直し）。持ち主は run の費用を無駄にしない方法の 1 と 2 を issue にしてよいかの問いに「1,2はい。」と答えた。方法の 1 は #836（直す前の試験で、試験を起こす起動スクリプトだけが赤なら、AI の判定を起こす前に止める）、方法の 2 がこの節（直す前と同じ落ち方の赤なら、その直しのせいではないので組を戻さない）。
- この節の語: 名指し（名指しのテスト）は、組の子の TDD の loop で修正役が赤 → 緑を確かめたテスト。結末は、試験を走らせて JUnit XML から読んだテストごとの結果の行の並び（直す前の結末は test-gate の block が取った `baseline.json` の `cases`。2026-10-23 から test-gate は直す前に試験を走らせないので、組の子の TDD の輪の頭が取った失敗の文つきの結末〔輪の状態の `baseline_cases`〕を足して読む。`board.before_cases`・19 節）。結末の語は行の結果の種類（`passed`・`failure`・`error`・`skipped` など）。
- 何を: `join`（と合わせ役の受け付け `clash.problems`）が組を親の作業ツリーに当てた後の確かめ直し `board.rerun_problem` は 3 段ある。その 1 段目（名指しだけを走らせる段）で、名指しが緑でなくても、直す前の結末と照らして「前から同じ形で赤」なら、組を戻す理由にしない。その名指しは「名指し（結末の語: 失敗の文）」の文で、確かめ直しを通って当てたままにした組の行の `old_red` に残す（`join.json` と出力 `groups`）。
- 「前から同じ形で赤」の決まり（`board.same_red`。はい・いいえ）: 次の 4 つが全部はいの時だけはい。
  1. 直す前の結末に、名指しに当たる行（`baseline_red.match_case`）が在る。
  2. 当てた後の結末に、名指しに当たる行が在る。
  3. 直す前の行と当てた後の行の結末の語が、どちらも `error`（テストの中の検査でなく、読み込み・準備で落ちた）。
  4. 失敗の文（JUnit の `error` の子の `message`。`fail_message`）が、どちらも空でなく字のまま同じ。
- `failure` を数えない訳: 名指しは、修正役が直す前に `failure` で赤だったのを確かめたテスト（TDD の赤は `failure` だけを認める。`baseline_red.red_problems`）。後の組が前の組の直しを壊して元の赤に戻すと、当てた後の行は直す前と同じ結末の語と同じ失敗の文の `failure` になり、環境の赤と見分けられない（`tests/blocks/fix/test_join.py` の `test_join_reruns_fixer_only_group_against_the_earlier_group`）。直す前も後も `error` の名指しは、親の作業ツリーではどちらの時もテストの中まで届いていない（修正役の子の作業ツリーとの環境の違い）ので、組の直しのせいではない。
- いいえの時（直す前に緑・`failure`・飛ばされた・居ない、当てた後に居ない・`failure`、失敗の文が空か違う）は今と同じに戻す理由にする。当てた後の結末に名指しの行が無い時（読み込めないモジュールを、名指しの行でなくモジュールの行で出す実行器の形）は、前から同じだったかを名指しの行どうしで比べられないので、はいにしない（見逃しを増やさない）。失敗の文を書かない実行器（空の文）と、失敗の文に作業ツリーごとに違う字（一時のパスなど）が入る赤も、いいえに倒れて今と同じに戻す。
- error の行の失敗の文: 今まで `baseline_red._failure_attrs` は `failure` の子だけを読み、`error` の行の `fail_message` は空だった。それでは error の行の失敗の文を比べられない（4 がいつもいいえ）ので、結末の語の子（`error` が在ればそれ、無ければ `failure`）の `message` と本文を読む。`fail_message` を読むほかの所（TDD の loop の赤の引用は `failure` の行だけを読む。試験の関門の block test-gate の `test_outcomes` と、r2〔独立設計との比べの block。README 8 節〕の報告は失敗の文を添えるだけ）は、error の行に文が載るだけで判定は変わらない。
- 2 段目と 3 段目は変えない。
  - 2 段目: 変えたファイルに当たる試験を走らせ、新しい赤を見る（`tdd.selected_problems`）。今も、直す前の結末で赤の行は結末の語の一致だけで外し、直す前の結末に無い行は、直す前の版（`rev`。既定は `HEAD`）を写した作業ツリーで同じ試験を走らせて比べる。
  - 3 段目: 赤が無く、run に試験の命令 `test_cmd` が在り、その関門が on の時だけ、`test_cmd` を 1 回走らせる。
- E11（根の `AGENTS.md`。仕組みを足す前に確かめる 3 つ）: (1) Archon は持たない（確かめ直しは工場の `join` の中の事）。(2) ASF も持たない（ASF の修正の流れは組を当てて確かめ直す段を持たない）。(3) 要る: README 10 節の keep-essence の 1（赤緑の機械の判定）と 2（元から赤のテストの区別）の「直しで壊した赤を見逃さない」を保ったまま、直す前から対象のコードと関わりなく赤の run（#836 の起動スクリプトの不具合など）が直しを全部戻して費用を捨てる事（run 96f35545 で約 $122。#836 の本文）を減らす。元の works（この設計書の頭の語）の確かめ直し `_green_after`（12.5 節の F411）も、名指しを直す前の結末と照らしていなかった。
- run 96f35545 で組を戻した赤: 記録（`fix/join.json`）の理由は 2 つの組とも 2 段目の物だった。その run の直す前の結末は 17 節の関わる試験だけで取った 43 件で、当てた後に新しく走ったモジュールの読み込みの失敗は直す前の結末に無く、直す前の版の写しでは実行器が差分で試験を選ぶので同じモジュールを走らせなかった。この節の直しは 1 段目の物なので、その run の 2 段目の赤は今と同じに戻す理由のまま。その run の赤の元は起動スクリプトの不具合で、止めるのは #836 の直し。

## 19 試験の環境の壊れを TDD の輪の頭で見つけて直す（2026-10-23。#836・持ち主の決め `base-runs-nothing`）

- 出どころ: #836（書き直した本文）と #828。持ち主の言葉: 「ただ最初にふるてすとはテストは重いでしょ」「TDDでは自分の関係ないとこのテストを走らせないのでは」「自分に関係ないとこの試験はしないでしょ。で、自分に関係のあるところの試験が壊れてたらついでに直してあげるとかでいいのでは」と、下の 2 つに分けた直し方への「はい」。
- 前提: test-gate は直す前の版で試験を何も走らせない（`docs/design/test-gate.md` の 15 節）。工場が書いた実行器（試験の起動スクリプト）は、走らせずに test-gate の出力の欄 `suite` に結ばれて修正の段に届く。試験の環境の壊れは、TDD の輪が関わる試験を最初に走らせる所（輪の頭 `tdd.start` の元の結末の回）で見つける。
- この節の語: 起動スクリプトは TDD の実行器（第 1 引数の書き先に JUnit XML を書く物）。工場が書いた実行器は、test-gate が取り置きから使ったか書き手の役が書いた物（line の `fix-in` が test-gate の返りの `suite_note` から決め、入力 `suite_made` で渡す。人が `tdd_suite` で渡した実行器は偽）。関わる試験は、輪の頭の元の結末が走らせた試験（走らせ方が決まらない道は 17 節の選び、ほかは一式）。

### 19.1 壊れているのが工場の物の時（起動スクリプトの書き直し）

- 決まり（はい・いいえ。`tdd._suite_broken`）: `suite_made` が真で `test_cmd` が在り、輪の頭の元の結末の回が結末を返さないか、試験が 1 件でも `error`（中身に届く前に落ちた）で、`test_cmd` を単体で走らせると緑なら、壊れているのは起動スクリプト。関わる試験だけを渡した回は、実行器を一式でも 1 回走らせ、それも同じく落ちる時だけはい（`test_cmd` の単体の回は一式を走らせるので、関わる試験だけを渡した回の `error` とは走らせ方が違い、起動スクリプトのせいとは言えない。実行器は `test_cmd` を字のまま含む約束なので、一式どうしなら同じ走らせ方を比べられる）。
- はいの時: `group-start` は輪を回さず（`tdd: false`・`suite_broken: true`）、同じバイトの取り置き（test-gate が照らしを通った実行器を run をまたいで置く所。`docs/design/test-gate.md` の頭の語）を捨てる（`suitewrite.drop_runner`）。`suite-fix-prep` が書き直す役の指示（`prompts/suite-fix.md`。壊れた本文・壊れた回のログの末尾・`test_cmd` の単体のログ。契約と書き方は test-gate の書き手と同じ共通の断片 `.shared/prompts/runner-writer.md`）を組み、`suite-fix`（AI。test-gate の `suite-write` と同じ群 `@wf-test-gate`・道具・砂場）が本文を返し、`suite-fix-try` が実行器のファイルを置き換えて（`suitewrite.put_runner`。一時のファイルから入れ替える）輪の頭をやり直す（`suitefix.retry`）。
  - 直れば輪が続き、直した実行器を取り置く（`suitewrite.keep_runner`）。実行器のファイルは test-gate の place の物を置き換えるので、最後の試験の関門も直した実行器を使う。
  - 書き直しても壊れたまま・書き手が作れない・返答が無い時は組を止める: `tdd-go` の `stop` が真で修正役の輪を回さない（確かめていない直しを書き進めない）。組の結果の `tdd` に `suite_broken`・`runner_log`・`cmd_log` が載り、出口の `stop_reason` が `stopby.SUITE_BROKEN`（line は今の止めの道で後ろの段へ進めない）。報告の冒頭の知らせの行に訳とログのパスが出る（line の `src/facts.py` の `suite_broken_notes`）。
- 書き直しは 1 回だけ（`max_iterations` の輪にしない。数の上限でなく「書き直しても直らない時だけ止める」のはい・いいえ）。
- 人が渡した実行器と、`test_cmd` の単体も赤の時は今までどおり（試験そのものの赤）。直す前の版で test-gate がしていた起動スクリプトの照らし（JUnit XML が出て試験が 1 件以上）は、輪の頭の元の結末の回が兼ねる（結末が無ければ今までどおり TDD の輪を回さずに直す）。
- 並べた組の子が同時に同じ実行器を書き直すことがある。入れ替えは一時のファイルからの置き換えなので、走っている子は前の本文か新しい本文のどちらかを読む（後に書いた方が残る）。

### 19.2 壊れているのが対象のリポジトリの試験の時（ついでに直す）

- 輪の頭の元の結末で落ちた（`failure`・`error`）試験のファイルのうち、修正案が触る所に直に関わる試験（`tdd._related_pick`。17 節の選びと同じ）に在る物を、置き場の `conflict.BROKEN_TESTS_FILE`（`{tests: [{path, ids}]}`）に書く（`tdd.broken_related`）。関わるかを選べない（`whole`）時は書かない（相談で許しを取る今の道）。
- 許し（修正役が書き換えてよい試験の行）の 6 つ目の元: `conflict.test_permits` がこのファイルの行を許しの行（出どころ `broken`〔`fixboard.ALLOWED_SOURCES` の 4 つ目〕・`id` の頭 `broken-before`・範囲はファイル全部）にする。受け付けの事後の関門（`edit_permits` の `limits`）・凍結の照らし・最後の関所は今の許しと同じ口で読む。
- 修正役の指示のテストの節に「直す前から壊れていた関わる試験（ついでに直してよい。最後の承認ノードに出る）」の行と、試験が確かめる中身を弱めずに直してよいという 1 段落（`tests_broken`）が入る。
- 最後の承認ノード: 封じた差分が触った許しの行のうち出どころ `broken` の物を「ついでに直した試験」として、書き換えを許したテストと分けた節に出し、承認ノードを開ける（止めて人の答えを待つ）理由にも足す（守りの扱い。開き方の入力 `final_gate` に依らず開く）（line の `src/final.py`）。
- 計画で認めた試験しか書き換えられない今の決まりは、ほかの試験には変えない。

### 19.3 E11 の 3 つの確かめ

1. Archon が持っているか: 持たない（node の結果を運ぶだけ）。
2. ASF が持っているか: 持たない（ASF の修正の流れは実行器を書かず、試験の環境の壊れを直す段を持たない）。
3. 本当に要るか: run 96f35545 で、起動スクリプトの壊れに気づかず約 $122 を使って直しを全部戻した。直す前の試験をやめた（#828）後、その壊れを見つけられるのは TDD の輪が関わる試験を走らせる所だけ。keep-essence の 1（赤緑の機械の判定）の実行器を、壊れたまま使わない。

### 19.4 試験

- `tests/blocks/fix/test_suite_fix.py`: 壊れの見つけ（取り置きを捨て、訳に 2 つのログ）・人が渡した実行器と赤の `test_cmd` は壊れと読まない・書き直して輪が続き取り置く・書き直しても壊れたままなら組を止めて `stopby.SUITE_BROKEN`・書き手が作れなければ止める・配線・ついでに直してよい試験の選び（関わる試験の落ちた物だけ）・許しの 6 つ目の元・確かめ直しが子の輪の頭の結末を読む（`board.before_cases`）。
- `tests/blocks/fix/test_prompts.py`: 修正役の指示の「直す前から壊れていた関わる試験」の行（表 `RENDERED` に `suite-fix`）。
- `tests/blocks/line/test_gates.py`（「ついでに直した試験」の節と開ける理由）・`tests/blocks/line/test_head_plain.py`（報告の冒頭の止めの行）・`tests/blocks/line/test_fix_in.py`（`suite_made`）。`tests/blocks/line/fix_in_before_spec.json` は `fix-in` に欄 `suite_made` を足したので取り直した（値は全部 `false`）。

## 20 確かめ直しで、直す前の版と比べる試験を名指しで走らせる（2026-10-23。#846）

- 出どころ: issue #846。持ち主は、この直し方を issue にするという推しに「おしで。」と答えた。
- 何を: 18 節の確かめ直しの 2 段目（`tdd.selected_problems`）は、直す前の結末に無い赤を、直す前の版（`rev`）を写した一時の作業ツリーで走らせて比べる（`tdd._base_reds`）。今までは今の木と同じ引数（変えた試験のファイルと `-k`）で実行器の既定の一式を回していたので、走らせる試験を差分から自分で選ぶ実行器（このリポジトリの `tests/changed.py` の形）では、差分の無い写しで比べたい試験が選ばれず、比べられなかった赤を新しい赤と数えて組を戻した（run 96f35545。18 節の終わり）。この節から、比べたい試験を名指し（`<根からのパス>::<クラス>::<名前>`。結末の行のモジュールからテストのファイルを引く `tdd._case_ids`）で、合図 `TDD_SUITE_ONLY=1` を付けて走らせる。
- 比べの決まり（はい・いいえ）: 元の結末に無い赤の 1 件ごとに、写しの結末の同じ鍵（テストを 1 件に決める `classname::name`）の行を見る。
  1. 写しで `failure` か `error` → 前から赤。新しい赤に数えない（今までと同じ。知らせに「版の写しでも赤だったので外した」）。
  2. 写しで `passed` か `skipped` → 新しい赤。
  3. 版にその試験のファイルが無い（この直しで足した試験）→ 比べるまでもなく新しい赤。
  4. ほか（写しを作れない・実行器が走らない・名指しを引けない・名指しで走らせても写しの結末に出ない）→ 比べられなかった。
- 比べられなかった赤: 組を当てた後の確かめ直し（`board.rerun_problem` に受け口 `uncompared` を渡す `join`）は、新しい赤に数えず組を戻す理由にしない。黙って前から赤として通さず、組の行の `uncompared` に鍵を名指し、run の報告の「人が決めること」の欄に「当てた後の確かめ直しで直す前の版と比べられなかった赤」として 1 件 1 行で載せて聞く（line の `facts.uncompared_rows`）。受け口を渡さない呼び（修正の受け付け）は今どおり赤のまま（修正役が直して出し直す。知らせに「比べられず赤のまま」）。合わせ役の受け付け `clash.problems` も 21 節から受け口を渡す。
- 写しの結末の控え（`REV_CACHE`）は、版と実行器の組ごとに行を持ち、行にテストの鍵ごとの結末 `outcomes` を持つ。同じ版と実行器の行に、比べたいテストの鍵が全部在れば走らせない。
- E11（根の `AGENTS.md`。仕組みを足す前に確かめる 3 つ）: (1) Archon（工場が上で動く道具）は、直す前の版と名指しで比べる仕組みを持たない（確かめ直しは工場の `join` の中の事）。(2) ASF も持たない（ASF の修正の流れは組を当てて確かめ直す段を持たない。18 節と同じ）。(3) 要る: README 10 節の keep-essence の 2（元から赤のテストの区別）を、走らせる試験を差分で選ぶ実行器でも保つ。比べられなかった赤を人に聞くのは、keep-essence の 1（直しで壊した赤を見逃さない）を、組を戻して費用を捨てずに保つため。元の works の `_green_after` は直す前の版と比べていなかった。

## 21 確かめ直しの test_cmd の 1 回の赤と、合わせ役の道の比べられなかった赤で、正しい組を戻さない（2026-10-24。#855）

- 出どころ: issue #855（#846 の続き）。持ち主の言葉は「まあようは、人間がＴＤＤするときどうするか？ってことだよ」「superpowerならどうするのよとか」、3 段目と合わせ役の道を 1 つの issue にまとめる案に「おｋ」（どれも 2026-10-24）。
- この節の語: 組を戻すは、当てた組を親の作業ツリーから外すこと。組を外した木は、組を当てる前の親の作業ツリー（`join` は当てる前に取った `tdd.snapshot`、合わせ役の受け付けは控えの行の当て直す前の木 `before`）。
- 3 段目（`board.cmd_verdict`）: 呼び手が組を外した木 `base` を渡す時、当てた後の木で `test_cmd` が緑でなければ、次の順に見る（はい・いいえ）。
  1. 組を外した木の姿で `test_cmd` を 1 回走らせる（`board._cmd_without`。走らせた後は当てた姿へ戻し、外した木で出来たファイルも残さない。ただし `.gitignore` に当たるファイル〔ビルドの出力・キャッシュ〕は木の姿に入らないので戻さない。前からの `test_cmd` の走らせ方と同じ）。外した木へ写す・当てた姿へ戻すのが落ちた時、`join` の道では呼び手の `join_group` が組を戻し、合わせ役の道では `clash.problems` から受け付けの node（`clash_accept.py`）まで落ちる（前からの `rerun_problem` の例外と同じ扱い）。
  2. 外しても赤 → 組のせいでない。組を戻さず、人にも聞かず、「前から赤（または環境）」の文（コマンドとログの末尾）を組の行の `test_cmd_notes` に置く。
  3. 外した木の結果が取れない（コマンドを起こせない）→ 呼び手が受け口 `uncompared`（20 節の、比べられなかった赤を足す並び）を渡していれば戻さず、そこへ `test_cmd` の行を足して、run の報告の「人が決めること」の欄で人に聞く（20 節）。無ければ戻す。
  4. 外すと緑 → 当てた木であと 2 回走らせる。1 回でも緑なら揺れと見て戻さず「揺れ」の文を `test_cmd_notes` に置く。3 回とも赤の時だけ戻す理由（文に「3 回とも赤」）。
- `base` を渡さない呼びは今どおり 1 回の赤で戻す。`join` と合わせ役の受け付けは `base` を渡す。
- 合わせ役の道: `clash.problems` も `rerun_problem` に受け口 `uncompared` と `base` を渡す。比べられなかった赤と `test_cmd` の前から赤・揺れは戻す理由にせず、控えの行の `uncompared`・`test_cmd_notes` に置き、受け付けを通れば `settle_repaired` が `join.json` の組の行の同じ名の欄に写す（line の `facts.uncompared_rows` が人に聞く）。合わせ役が自分で直せない赤のために 3 回合わせ直して裁定役まで回る事が無くなる。
- 今までどおり止める物: 直しで足した新しい試験の赤（`tdd.selected_problems` の「版にその試験のファイルが無い」と `board.tests_moved`）と、名指しの試験の赤（1 段目）。どちらの道も変えない。
- 根拠（my_notes の調べ）: 自分が起こしていない赤も名を挙げて報告する（superpowers 7.0.0 の test-driven-development）。揺れる赤はバグと見分けられないので走らせ直して見分ける（Fowler「Eradicating Non-Determinism in Tests」・Google の Flake Aware Culprit Finding、ICST 2023）。自分の直しが壊したなら戻す（Fowler「Continuous Integration」）。試せない版は良し悪しに数えない（git bisect の 125）。
- E11（根の `AGENTS.md`）: (1) Archon は持たない（確かめ直しは工場の `join` の中の事）。(2) ASF も持たない（18 節と同じ）。(3) 要る: keep-essence の 1（直しで壊した赤を見逃さない）を、外すと緑で 3 回とも赤の組を戻すことで保ったまま、試験の 1 回の揺れや前からの赤で正しい組を戻して出し直しの費用を捨てる事（run 96f35545 で約 $122）を無くす。元の works の `_green_after` は `test_cmd` を 1 回だけ走らせていた。
- 試験: `tests/blocks/fix/test_join.py` の `test_rerun_problem_tells_test_cmd_red_apart_on_the_tree_without_the_group`（3 段目の見分けの表と、`test_cmd_notes` と報告の行）・`tests/blocks/fix/test_clash.py` の `test_join_clash_repaired_with_an_uncompared_red_asks_a_human`（合わせ役の道）。
