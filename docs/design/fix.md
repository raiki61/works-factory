# block の設計書: fix（修正）

- 何の話か: 承認済みの修正案を項目ごとに直す観点「修正」を、単独で呼べる block `workflows/fix/` にする設計。直しの組ごとに自分を子の run として起こし（`workflow:` と `fan_out:`）、組の子の中で単位ごとの TDD の loop と修正役を回し、親で組を合わせ（合わせ役）、食い違いの申し出を読むだけの裁定役が裁き、裁定の後に直し直す。範囲の相談（修正案の側への問い）もこの block の中に在る。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。
- 決めたこと: 今の `workflows/fix/` の node のうち、差分の審査・レンズ・手直し（`delta-cut`〜`refix2-loop`）を delta-review と lens の block に渡し、残りを同じ並びの block にする。始めの記録の代わりに port で受け、run の頭の深さ（`depth`・`head_depth`・`depth_record`）と fix の中の深さの上げ直し（`fixboard.redepth`）を外して、port `skip_rerun` 1 つにする。AI の node は 9 つ（修正役・裁定の後の修正役・相談の答え 2・TDD の役 2・裁定役・合わせ役 2）で、指示の本文は block の 5 つの断片（`fixer`・`consult`・`tdd`・`clash`・`brief`）と裁定役の md 1 本と、書く役の決まりの共通の断片 `writer-rules`（delta-review の手直しの役と共に使う）に寄せる。lib の 12 モジュールを `src/` へ写す（どの関数をどこへ写すかは 1.5）。振る舞いは変えない。変える所は 13 節に名指した物だけ。
- 読む人: この block を作る実装の役（この設計書だけで作れるように書いた）。README 11.1 の 3 波目（delta-review と同時。写す範囲は 1.5.3 で割った）。
- 持ち主に求めること: なし。README・持ち主の決め・今のコードの事実で 1 つに決まらなかった物は 16 節（未確認）に置いた。作り直しの中で見つけた今の工場の不具合（相談の答えの役が修正役の会話の分かれとして起きる・振り分けの段の書き込みが戻らない など）は直さず 13.3 に並べた（振る舞いを変えるので作り直しの外。structure の設計書の 11 節の 8 と同じ扱い）。
- 直し方の型の段 1（PR A。2026-10-25）の形: 組の子は、元の結末を組の頭で取って `base.json` に置き、振り分けを TDD の輪の外の `route-loop` に出し、型ごとの注文を `orders` が書いてから、tdd の輪と修正役の輪を並べる。この形は 22 節に書き（段 1 の PR B で修正役を型ごとの書き手に分けた形は 23 節。22 節の「修正役の輪」「修正役」の文は 23 節に従う）、1.3 の 13〜16・1.4・4 節・7 節・8 節・17〜19 節の該当の文は 22 節に従う。下書きは [2026-10-24-fix-weapons.md](../plans/2026-10-24-fix-weapons.md)、実装の控え（PR A の境目）は [2026-10-25-fix-weapons-stage1-a.md](../plans/2026-10-25-fix-weapons-stage1-a.md)。書き手が修正役のまま 1 つであることと、書き手の返す証拠が要る照らしを PR B に回したことは、この文書でも「段 1 の PR B で」と書く。
- 直し方の型の段 2 の D1・D2（2026-10-26）の形: 書き手の型 6 つ（tdd の閉じ・pin・tidy・static・variant・remove）を、修正の block が `include:` する葉の block `workflows/weapon-<型>/` に出した（D1 が 5 つ、D2 の段 1 で variant）。D2 の段 2 で、下請けを付ける型を下書きの 11.8 の決め（案 B）の 5 つ（variant・remove・pin・tidy・static。tdd の閉じの外）にした（24.9）。書き手に渡す slots と鎖の並びは 2 節、型の block の共通の形と共通の本体は 24 節、型ごとに違う物は型ごとの設計書（`docs/design/weapon-<型>.md`）。1.2〜1.5 の port・node の並び・コードの置き場は D2 の段 1 の後の形に合わせた。下請け（書き手が項目ごとに起こす実装役と審査役）の部品は `lib/subagents.py`・`.shared/prompts/g1-*.md`・本体 `writerblock.prep` に移った（24.9）。

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
- `routes`: `choice(auto|plan): 単位ごとの道の決め方。auto は振り分けの段の AI（`route-loop` の役 `route`。22.1）が、計画の語が `static`・`tidy`・`pin` の単位と消す名の在る単位を除いた単位を tdd か direct に振る（承認済みの案が tdd の単位は tdd に縛る）。plan は振り分けの段の AI を起こさず、型は計画の語だけで 22.1 の表の AI の答え無しの行で引く（`static`・`tidy`・`pin` の語はその型、消す名の在る単位は remove、語が `tdd` なら tdd、ほかは variant。訳は行の route_why）。tdd の単位が 0 なら TDD のループを回さない`。既定 `auto`。値は `values.json` で組の子へ運ぶ。plan の時、`orders` が計画の語から型を引き（22.1・22.2）、tdd に引いた単位だけを輪の状態に並べて test の段から輪を始める。元の結末（組の頭で関わる試験を 1 回走らせて取る、直す前の結果。`base.json`。17 節・22.3）は、tdd の単位が無くても、計画の語が `static` でない単位が組に在れば取る（[spec-driven.md](spec-driven.md) の 7 章の 1 の「tdd の単位が無ければ取らない」は段 1 で替わった。持ち主の決め `group-head-base`）。
- `judgment`: `json(shared:judgment.schema.json): 判定（units・questions・precedents・framing などを持つ object）。whole と、out_dir の無い group では必須。out_dir の在る group（子の run）は親の写しを読むので空でよい`。既定 `""`。
- `plan`: `json(shared:plan-fields.schema.json): 承認済みの修正案の欄の控え {fields}（今の plan-fields.json。凍結の印〔置いた控えの sha256 を修正案の block が trace.jsonl に書いた行。控えが印と食い違えば壊れた控えとして止める〕も一緒に置く）。空は修正案の無い run`。既定 `""`。
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

形（形の照らしが読む語 `lib/graphloops/engine/schema.py` の KNOWN_KEYWORDS だけで書き、中身を宣言する。object には properties か patternProperties、array には items を書く。中身を宣言しない形は口 `workflows/.shared/ports.py` の `open_shapes` が拒む。#851）: 2 つ以上の block と graph が読む形は `.shared/schemas/` の 1 つを名指す（judgment・plan-fields・fix-plan・answer-ties・materials-state・plan-review-reply・carry・excluded・ripple・request。D1 から、型の block が読み修正の block が組む `weapon-order`〔`workflows/fix/schemas/` から移した〕・`writer-slots`・`writer-reply` も。2 節・24 節）。直す前の結末は lib の住処の `lib:baseline.schema.json`。この block の `schemas/` に残すのは、この block だけが読む `skip-rerun`・`fix-answers` `{decision, text, asked}`・`fix-request-answers`（`{question, text}` の行）・`only-items`（整数の配列）・`group` の 5 本。形の崩れた excluded の行は黙って捨てずに入口で `ok: false`（`start` が `end` より大きい行も拒む）。空の字 `""` と `null` は `ports.json` に渡さず「渡されていない」と読む（intake の決まり）。

D1・D2 の node 間の port: `fix-prep`・`fix-ruled-prep` の返りは `{go, iteration, writer, order, slots}`（`order`・`slots` は pointer。型の block の入力。2.2。指示の字 `prompt` は D2 で外した）で、型の block の出力 `reply`（pointer）を受け付けが読む（2.8）。block 全体の入力と出力（この節の 2 つの一覧）は D1・D2 で変えない。

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
- `removed_tests`・`untested`（直し方の型の段 1 で足した。`src/finish.returned_rows`）: この段の置き場の返しの控え `returns/` から組む。`removed_tests` は起点の版に在って直した後の木に無い試験の id の並び（行は `{group_id, weapon, units, tests, only_removed}`。`only_removed` は試験を消しただけで足しも書き換えもしなかった試験のファイル）、`untested` は注文に試験を求めない訳 `why_untested` が在った直し（static の型。行は `{group_id, weapon, units, why, files: [{path, kind}]}`）。1 回目の段から写した控え（`board.PRIOR_LOOP` の印）は数えない。控えが読めなければ出力を組まずに `fallback` へ倒す。読み手は line の最後の承認ノード（節「消した試験」「試験を求めなかった直し」。`docs/design/line.md` の 2 節の 4）。
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
10. `ruled-writers-loop`（段 1 の PR B。23 節）の中の `fix-ruled-loop`: `fix-ruled-loop`（`depends_on: [conflict-check, rule-loop, clash-ruled-loop]`・`when: "$conflict-check.output.go == true"`・`loop_group: {max_iterations: 12, fresh_context: false, until_bash: done=$fix-ruled-accept.output.done; test "$done" = true}`）: `fix-ruled-prep`（script `fix_ruled_prep.py`）→ `fix-ruled`（AI。2 節）→ `ruled-consult-check`（script `consult_check.py`・`with: {reply: $fix-ruled.output, pass: ruled}`）→ `ruled-consult-ask`（`depends_on: [ruled-consult-check]`・`when: "$ruled-consult-check.output.go == true"`・`loop_group: {max_iterations: 1, fresh_context: true, until_bash: "true"}`。本体は `ruled-consult-answer`〔AI。3 節〕1 つだけ。訳は 13.3 の 1）→ `ruled-consult-accept`（script `consult_accept.py`・`depends_on: [ruled-consult-check, ruled-consult-ask]`・`trigger_rule: none_failed_min_one_success`・`with: {answer: {from: "$ruled-consult-ask.output", if_skipped: null}, pass: ruled}`）→ `fix-ruled-accept`（script `fix_ruled_accept.py`・`depends_on: [fix-ruled-prep, ruled-consult-accept]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$fix-ruled.output", if_skipped: null}, consulted: {from: "$ruled-consult-accept.output.consulted", if_skipped: false}}`）。`fix-ruled-prep` は段の頭で 1 度、裁定の後の直しの注文を親の置き場に書く（22.5）。 段 1 の PR B から、修正役 `fix-ruled` は型ごとの書き手 `pin-ruled`・`tidy-ruled`・`static-ruled`・`variant-ruled`・`remove-ruled` の鎖に替わり、`with:` の `reply` は `reply_<型>` になる（23 節）。D1 の後は、この鎖の書き手のうち `variant-ruled` 以外が、include `wr-pin`・`wr-tidy`・`wr-static`・`wr-remove` に替わる（`depends_on: [fix-ruled-prep, <前の include>]`・`when` は `$fix-ruled-prep.output.writer == 'wr-<型>'`・`with: {order, slots}`。裁定の後の段は tdd の閉じが無い。形は 2.2.1。`variant-ruled` は D2 まで node のまま）。受け付けの `with:` は `reply_<型>` ← `{from: "$wr-<型>.output.reply", if_skipped: null}`（`reply_variant` だけ `$variant-ruled.output`）。
11. `clean`（script `clean.py`。`depends_on: [intake, clash-loop, conflict-check, rule-loop, clash-ruled-loop, fix-ruled-loop]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.whole == true"`）。
12. `assert-changed`（script `assert_changed.py`。`depends_on: [intake, clean]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.whole == true"`・`mutates_checkout: false`）。

組の形（`when` に `$intake.output.whole == false && $intake.output.ok == true` を含む）:

13. `group-start`（script `group_start.py`。`depends_on: [intake]`）: 木を写し、入力を写し、元の結末を取って組の置き場の `base.json` に書く（`src/basecase.take`。22.3）。返り `{tdd, units, reason, suite_broken, no_suite}`（`tdd` は元の結末が取れた〔`base.json` の `taken`〕。`suite_broken` は 19.1、`no_suite` は 19.1 の止め方の 1）。輪の状態はここでは置かない（以前は `tdd.start` が置いた）。組の頭の返りの全体は `tdd-start.json` に書く。型の注文を書く node までの並びは次の順で、組の子の `depends_on` はこの順の前を結ぶ:
   1. `suite-fix-prep`（`when: $group-start.output.suite_broken == true`）→ `suite-fix`（AI。`when: $suite-fix-prep.output.write == true`）→ `suite-fix-try`（`when` は `suite_broken`。前が飛んでも走るので壊れた組だけに絞る）: 工場の書いた実行器の書き直し。19.1。
   2. `route-go`（script `route_go.py`。`depends_on: [group-start, suite-fix-try]`・`trigger_rule: none_failed_min_one_success`）: 返り `{route, stop}`。`route` は振り分けの AI を起こすか、`stop` は組を止めるか（`suite_broken` か `no_suite`）。22.1。
   3. `route-loop`（`depends_on: [route-go]`・`when: "$route-go.output.route == true"`・`loop_group: {max_iterations: 40, fresh_context: false, until_bash: done=$route-step.output.done; test "$done" = true}`）: `route-prep`（script。返り `{prompt, go}`）→ `route`（AI。`when: "$route-prep.output.go == true"`）→ `route-step`（script。返り `{ok, done, reason, reason_file, phase}`）。柵 40 は今の `tdd-loop` と同じ。諦めは拒否 3 回（`rolekit.GIVE_UP_AFTER`）で決め、柵とは別。
   4. `orders`（script `orders.py`。`depends_on: [group-start, route-go, route-loop]`・`trigger_rule: none_failed_min_one_success`）: 型ごとの注文 `orders/<weapon>.json` と索引 `orders.json` を書き、輪を回すかの真偽だけを返す `{tdd, writer, stop, reason}`。22.2。
14. `tdd-loop`（`depends_on: [orders]`・`when: "$orders.output.tdd == true"`・`loop_group: {max_iterations: 40, fresh_context: false, until_bash: done=$tdd-step.output.done; test "$done" = true}`）: `tdd-prep`（script `tdd_prep.py`。返り `{prompt, go, new_unit}`）→ `tdd`（AI。`when: "$tdd-prep.output.go == true && $tdd-prep.output.new_unit == false"`）→ `tdd-new`（AI。`depends_on: [tdd-prep, tdd]`・`trigger_rule: none_failed_min_one_success`・`when: "… new_unit == true"`・`context: fresh`）→ `tdd-step`（script `tdd_step.py`・`depends_on: [tdd-prep, tdd, tdd-new]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$tdd.output", if_skipped: null}, reply_new: {from: "$tdd-new.output", if_skipped: null}}`）。tdd-new を tdd の後ろの層に置く訳（同じ層だと Archon が並んだ層として会話を切る）を YAML のコメントに残す。輪の段は test・fix・refactor の 3 つ（振り分けの段は 13 の `route-loop` に出た）。
15. `writers-loop`（段 1 の PR B。23 節）の中の `fix-loop`: `fix-loop`（`depends_on: [group-start, orders, tdd-loop]`・`trigger_rule: none_failed_min_one_success`・`when: "$orders.output.writer == true && $orders.output.stop == false"`・`loop_group: {max_iterations: 12, fresh_context: false, until_bash: done=$fix-accept.output.done; test "$done" = true}`）: `fix-prep`（script `fix_prep.py`。返り `{prompt, go, iteration}`。直す義務が空か、組が no-suite で止まっていれば `go: false`〔`board.no_suite_stop`〕）→ `fixer`（AI。`when: "$fix-prep.output.go == true"`）→ `consult-check`（`with: {reply: $fixer.output, pass: first}`）→ `consult-ask`（10 の `ruled-consult-ask` と同じ形。本体は `consult-answer`〔AI〕1 つだけ）→ `consult-accept`（`pass: first`・`answer` は `$consult-ask.output`）→ `fix-accept`（10 と同じ形で `fixer`・`consult-accept` を受ける）。段 1 の PR A では、`orders` が書いた tdd 以外の型の注文（variant・remove・static・tidy・下ごしらえ）をこの輪の修正役が全部受ける（書き手は型ごとに分けない。22.2）。 段 1 の PR B から、修正役 `fixer` は型ごとの書き手 `tdd-close`・`pin`・`tidy`・`static`・`variant`・`remove` の鎖に替わる（23 節）。D1 の後は、`fix-prep` → include `w-tdd-close` → `w-pin` → `w-tidy` → `w-static` → node `variant`（D2 で include `w-variant`）→ `w-remove` → `consult-check` → `consult-ask` → `consult-accept` → `fix-accept` の並びになる（include の node の形・`when`・`with:`・錨は 2.2.1。`consult-check` と `fix-accept` の `depends_on` は書き手の node の名の代わりに include の id を並べる。受け付けの `with:` は `reply_<型>` ← `{from: "$w-<型>.output.reply", if_skipped: null}`〔`reply_variant` だけ `$variant.output`〕）。
16. `group-end`（script `group_end.py`。`depends_on: [group-start, tdd-loop, fix-loop]`・`trigger_rule: none_failed_min_one_success`・`mutates_checkout: false`）: 返り `{result_file}`。組の結果に元の結末の場所の欄 `base`（その組の `base.json` のパス）を足す（22.3）。no-suite の印は輪が済まずに抜けた組でも落とさない（`group_end.tdd_exit`）。

両方の形の終わり:

17. `nodes-ok`（`bash: "true"`・`trigger_rule: none_failed_min_one_success`・`mutates_checkout: false`・`when` 無し）: `finish` と `fix-reads` のほかの全部の node（loop の node を含む）に `depends_on` で結ぶ。どの node かが落ちた run で飛び、block の出口で落ちを見せる柵（今のまま。訳は今の YAML の注記）。
18. `fix-reads`（script `fix_reads.py`。`depends_on: [fix-loop, fix-ruled-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 読んだ証拠（7 節）。落ちない。
19. `finish`（script `finish.py`。`depends_on:` は intake と 2〜16 の全部と `fix-reads`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を組む（今の `collect.py` の後継。7 節）。落ちない。

loop の中の会話（README 13 章の決め・今の振る舞いのまま。D1 の後も、鎖の中の型の block の AI は include の中で、飛ばされた include の後ろの AI が前の周の会話を継ぐ。2.2.1）: `route-loop`・`rule-loop`・`fix-ruled-loop`・`tdd-loop`・`fix-loop` は `fresh_context: false` で、2 周目からは前の周の最後の会話を次の周の AI の node が継ぐ（1 周目はいつも新しい会話。止めた Archon の `dag-executor.ts:4830`）。どの loop にも、継ぐ役の直前に 2 つ以上の node の層は無い（どれも 1 本の鎖）。`clash-loop`・`clash-ruled-loop` は `fresh_context: true`。相談の答えの役は、修正の輪の本体の中の 1 周の輪（`consult-ask`・`ruled-consult-ask`）の中で新しい会話で起き、次の周の修正役は前の周の修正役の会話を継ぐ（13.3 の 1。#833）。

D1・D2 の後の違い（node）: 書き手の node のうち `tdd-close`・`pin`・`tidy`・`static`・`variant`・`remove`（と裁定の後の `pin-ruled`・`tidy-ruled`・`static-ruled`・`variant-ruled`・`remove-ruled`）は、この YAML の node でなく include `w-<型>`・`wr-<型>` に替わり、AI の node・指示の md・返答の形は型の block（24 節）に移る。

今との違い（node）: 外した node は `route`（intake が兼ねる）・`tdd-unit`（型つきの成果物 `tdd-unit` の読み手 `runreport` は report の `sections` に替わり、r2 は出力 `tdd` の値を読むので、`tdd-unit.json` は finish が書く）・`delta-cut`・`lens-prep`・`lens`・`lens-reply`・`lens-collect`・`delta-loop`・`refix-loop`・`review2-loop`・`refix2-loop`（delta-review と lens の block へ）。返す node の id は `fix` から `finish` にした（ほかの block と同じ。line は include の id で読むので字は動かない）。

### 1.4 place のファイル

`ports.place()`（単独の run と組の子の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/<include の id>/`。今の `fix/fix/` と `fix/refix-run/`）の下に、今と同じ名で書く。名は `src/files.py` だけが持つ（今の `fixnames`・`fixbeside` の名の住処と、`fixboard`・`tddloop`・`consult` などの名の定数の写しを 1 つにする）。

- 入口: `intake.json`（port の値）・`values.json`（今の始めの記録の写し `r1/start.json` の代わり。lib の `conflict` は値で受けるので `r1/start.json` は置かない。`{tdd_suite, test_cmd, reuse_key, reuse_dir, user_env_dir, lang, policy, request_file, answers, unattended, parallel, skip_rerun, excluded}`。`src/runvals.py` だけが読み書きする。組の子は親の物を写す）。
- 入力の写し（今のまま）: `judgment.json`・`judge-ties.json`・`judge-materials.json`・`plan-fields.json`（と凍結の印）・`fix-plan-reply.json`・`p2.plan_review.json`・`ripple.json`・`answers.json`・`only-items.json`・`baseline.json`・`base-rev.json`・`human-notes.md`・`fix-ignored-before.json`。今の `units.json`・`depth.json`・`head-depth.json`・`judge-depth-head.json`・`depth-raised.json` は書かない（読み手が無い・深さは port `skip_rerun` に替わる。13.1 の 2）。
- 組: `groups.json`・`groups/<group_id>/group-start.json`・`groups/<group_id>/result.json`・`join.json`・`join/<group_id>.diff`・`clash.json`・`clash-brief-<gid>.json`・`clash-turns-<pass>.json`。
- 型の口（段 1 の PR A。`src/files.py` の「直し方の型の口」の名）: `base.json`（組の元の結末の控え。組の置き場と確かめ直しの `<name>/`。親は自分では置かない。22.3）・`base/`（元の結末を取った回のログ・JUnit・地図の置き場。`base.json` の `work`）・`accept.json`（受け付けが書き戻す欄 `final_left`・`final_far`・`ci_left`・`suite_made`。受け付けの走る置き場ごと）・`bases/<k>/{base.json, accept.json}`（ほかの組・前の段から親と 2 回目の段へ写した元の結末。印 `ADOPTED_FROM`・`PRIOR_LOOP` は `accept.json` の鍵）・`returns/<k>.json`（共通の受け付けが通した返しの控え。22.4）・`orders/<weapon>.json`（型ごとの注文）・`orders.json`（注文の索引 `{sequence, weapons, stage, since, unsatisfied[, pass]}`）。振り分けの段の指示 `route-prompt-<n>.md` と却下の控え `route-step-reject-<n>.md` も組の置き場に書く。
- TDD の loop: `tdd-start.json`（組の頭の返り。振り分けか注文が輪の状態を置くと `state_file`・`summary_file` と `go` を足し、no-suite で止めた組は `no_suite` と訳を足す）・`tdd-<k>/state.json`（振り分けの段も同じ輪の状態に段 `route` で置く。22.1）・`tdd-<k>/summary.md`・`tdd-<k>/suite-<n>.log`・`tdd-<k>/junit-<n>.xml`・`tdd-<k>/test-cmd-0.log`・`tdd-step-reject-<n>.md`・`tdd-prompt-<n>.md`・`tdd-new-prompt-<n>.md`（今の `tdd-<k>/next.md` と `next.delivered.json` の代わり。渡した証拠の種類の控えは `tdd-delivered.json`）。
- 修正の loop: `fix-head.json`・`skip-before.json`・`briefs.json`・`brief-<n>.md`・`seat-briefs.md`・`g1-impl-<n>.md`・`g1-review-<n>.md`・`libdocs.json`・`libdocs/…`・`consult.json`・`consult-<pass>.json`・`consult-<pass>-<turn>-ask.md`・`consult-<pass>-<turn>.md`・`draft-reply.json`・`fixer-prompt-<n>.md`・`fixer-delivered.json`（今の `prompt-p3.fix.md`・`prompt-p3.fix.delivered.json`・`consult-first-<turn>-resume.md`・`consult-first-overflow-queued.md` の代わり。続きの周の指示も `fixer-prompt-<n>.md` に書く）・`consult-answer-prompt-<n>.md`・`fix-units.json`・`fix-reply.json`・`fix-parked-reply.json`・`fix-parked-<n>.patch`・`rejects-fix-accept.json`・`rejects-fix-accept.md`・`fix-gates.json`・`coverage-after.json`・`count-cache.json`・`count-budget.json`・`fix-unit-rows.json`・`accept-rev-cache.json`・`writes.jsonl`・`trace.jsonl`。
- 裁定: `conflicts.json`・`conflicts-dropped.json`・`conflict-rulings.md`・`rule-tree.json`・`ruler-prompt-<n>.md`（今の `prompt-rule.md`）・`rejects-rule.json`・`rejects-rule.md`。
- 裁定の後: `fix-ruled-head.json`・`fix-ruled-prompt-<n>.md`（今の `prompt-p3.fix-ruled.md`）・`fix-ruled-delivered.json`・`ruled-consult-answer-prompt-<n>.md`・`fix-ruled-reply.json`・`rejects-fix-ruled-accept.json`・`.md`・`clash-fix-prompt-<n>.md`・`clash-ruled-prompt-<n>.md`（今の `prompt-clash-<gid>.md`）・`rejects-clash-accept-<gid>.json`・`rejects-clash-ruled-accept-<gid>.json`。
- 型の block の place（D1。1 つの include ごとに `<修正の block の place>/<include の id>/` ができる。例 `w-static/`）: 組み上がった指示 `<型>-prompt-<n>.md`（`<n>` はその block の周の番号。1 回目の指示 `<型>-prompt-1.md` を続きの周が読み直す）と、返答 `reply-<n>.json`（`<n>` はその周の指示と同じ番号）と、返す node の返り `out-<n>.json`（prep が落ちた周の見分け）。今の `fixer-prompt-<n>.md`・`fix-ruled-prompt-<n>.md` は書かない。表の `SPAWNS` が真の型（D2 の後は variant）の block の place には、下請けのファイル `g1-impl-<n>.md`・`g1-review-<n>.md`（brief の在る run は `seat-briefs.md` も）も書かれる（24.9）。読んだ証拠の段の頭の印（`board.read_stages`）は、修正の block が自分の place に書く 1 回目の slots `slots-<include の id>-1.json`（`writers.stage_mark`）で、型の block の place の中の指示書は読まない（E4。受け取りは `with:` の入力と出力の欄の pointer だけ）。渡した証拠の種類の控え（`writers.ledger`）は修正の block の place に残り、名が include の id（`w-<型>-delivered.json`）に替わる（同じ型の周どうしで同じ名なので数えは変わらない）。
- 終わり: `fix-removed.json`・`assert-changed.json`・`fix.diff` か `fix-diff-none.txt`・`allowed-tests.json`・`accept-trace.json`・`closure.json`・`tdd-unit.json`・`frozen.json`・`scope.json`・`carry.json`・`reads-fix.json`・`reads-fix-ruled.json`・`reads-fix-block.json`・`prompt-error.json`（指示が組めなかった node と訳）・`fix-collect-error.txt`（finish の中の誤り）。

`carry.json` の形: `{conflicts: <conflicts.json の中身か null>, loops: [{state: <tdd-<k>/state.json の中身>, summary: <summary.md の字か "">}]}`（この段の place の全部の輪。子から写した物を含む）。2 回目の段の prep はこの 1 つのファイルだけを読み、`prior/<k>/state.json`・`prior/<k>/summary.md` に置いてから今の `adopt_prior_pass` と同じ写しをする（今は前の段の place のフォルダを名で開いていた。README の 4.3。13.1 の 5）。

### 1.5 コードの置き場と、作る・触るファイル

作るファイル（この block の PR が触るのはこれと `tests/blocks/fix/` と、この設計書と、下の「共通の物に足す 2 つ」だけ）:

- `workflows/fix/works-factory-fix.yaml`
- 共通の物に足す 2 つ: `workflows/.shared/prompt.py` の口 `sub`（1.5.4）と、`tests/layers/test_block_shape.py` の 7.1 の 3 の照らしの 1 つの道（14.3）。どちらも `.shared/AGENTS.md`・`workflows/AGENTS.md` の 1 行と一緒に足す。共通の断片 `writer-rules` は delta-review の PR が置き、この block は使うだけ（1.5.4）
- D1・D2 で足す・移す・消す物（1.5.6）。
- `workflows/fix/prompts/`（D1・D2 の前の形。型の書き手の md は 1.5.6 のとおり型の block へ移り、下請けの指示 `g1-impl.md`・`g1-review.md` は `.shared/prompts/` へ移った。1.5.4・24.9）: node ごとの md 9 本（`fixer.md`・`fix-ruled.md` は `{part:fixer}` の 1 行、`consult-answer.md`・`ruled-consult-answer.md` は `{part:consult}`、`tdd.md`・`tdd-new.md` は `{part:tdd}`、`clash-fix.md`・`clash-ruled.md` は `{part:clash}`、`ruler.md` は本文）と断片 `prompts/parts/`（`fixer.md`・`consult.md`・`tdd.md`・`clash.md`・修正役と TDD の役が共に使う `brief.md`・brief の行を名指す節 `brief-head.md`）。D2 の後に残るのは AI の node の md（`route`・`tdd`・`tdd-new`・`ruler`・`clash-*`・`consult-answer`・`ruled-consult-answer`・`suite-fix`）と、`parts/` の `answer-file-*`・`clash`・`consult`・`ruling-*`・`tdd`。
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

`src/` の新しいモジュール: `files.py`（place の名。1.4）・`runvals.py`（`values.json` の読み書き `write(place, ports)`・`read(place)`・`adopt(parent_place, place)`）・`intake.py`（port の読みと形ごとの必須）・`prompts.py`（AI の node の値と真偽を組む関数。2〜6 節の差し込み口の一覧と同じ名を返す。D1 から、書き手の分は `writer_slots`〔2.3〕で、型の block が組む指示の値は返さない）・`carry.py`（`carry.json` の書きと、`prior` から `prior/<k>/` に置く読み）・`finish.py`（出力の組み立て。今の `collect.py` の中身）・`report.py`（11 節）。

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
- 共通の断片 `writer-rules`（`workflows/.shared/prompts/writer-rules.md`。`{shared:writer-rules}`）: 書く役の決まりの正本（今の `fix-rules/common.md` の `core-fix`・`evidence` と 4 つの種類・`core-conflict`・`core-keep`）。修正役・TDD の役と、delta-review の手直しの役の 2 つの block が使うので共通の断片にする（`workflows/.shared/AGENTS.md` と README 11.1 の決まり。工場の作り直しのまとめ役の決め。README の形の直し 3 は fix の中の断片と書いたが、手直しの役が fix の外の block になった）。置くのは先に作る delta-review の PR で、この block は受けて使うだけ（足さない・直さない）。段落の名は 9 つ: `conflict`（食い違いの申し出）・`docs`・`prompts_kind`・`config`・`code`（証拠の 4 つの種類）・`evidence`（証拠の頭と文。種類の 1 つでも真の時）・`where_writer`・`where_tdd`・`where_rework`（証拠を書く場所の 1 文。役ごとに 1 つだけ真）。ほかの段落（直し方・守ること）はいつも入る。この block は `conflict` をいつも真で渡し、`evidence` は 4 つの種類の 1 つでも真の時に真、書く場所は型ごとの書き手が `where_writer`（PR B で修正役の `closure.verified_how` から返答の `evidence.kinds` に替えた。付録 A の W13）・TDD の役が `where_tdd` を真にして `where_rework` は偽にする（delta-review の手直しの役は `conflict` が偽、4 つの種類と `evidence` が真、`where_rework` だけが真で `where_writer`・`where_tdd` は偽）。
- 外への検索の決まりは今在る `{shared:query-rule}`、却下の段落は `{shared:rejected}`。ほかの共通の断片は足さない。

#### 1.5.5 事前の確かめのコマンド

修正役が返答の前に走らせる事前の確かめ（今の `lib/factchecks.py` を `python3 lib/factchecks.py <place>/consult.json --reply <draft>` で起こす。F100）は、`workflows/fix/src/facts.py` の `main` を `python3 <block のフォルダ>/src/facts.py <place>/consult.json --reply <draft>` で起こす形に替える。コマンドの字は `src/prompts.py` が組んで `{check_cmd}` で md に入れる（今の `check_cmd` と同じく `sys.executable` から）。`src/facts.py` は単独で起こされた時に `sys.path` に `workflows/.shared` と `workflows/fix` と `lib/` を足す（script の頭と同じ 2 行と `ports` の import）。

#### 1.5.6 D1・D2 で足す・移す・消す物（段 2。下書きの 11.6 の D1・D2 の作る物の 2〜5・7）

- 足す（pack の共通）: `workflows/.shared/writerblock.py`（`prep`・`save`・`out`・`paragraphs`。24.4）・`.shared/schemas/` の `weapon-order`（`workflows/fix/schemas/` から移す。中身は変えない）・`writer-slots`・`writer-reply`・`.shared/prompts/` の `writer-top.md`・`writer.md`・`brief-head.md`・`brief.md`（`parts/` から移す。字は変えず、中の `{part:` を `{shared:` に替えるだけ）。
- 足す（型の block）: `workflows/weapon-tdd-close/`・`weapon-pin/`・`weapon-tidy/`・`weapon-static/`・`weapon-remove/`（D1）・`weapon-variant/`（D2。24 節）。tdd の閉じを除く 5 つ（pin・tidy・static・remove・variant）は `allowed_tools` に `Agent` を持ち、表の `SPAWNS` が真（D2 の段 2。下書きの 11.8 の決め〔案 B〕）。
- 足す（D2。下請けの部品。24.9）: `lib/subagents.py`（項目ごとの値と借りた型の埋め）・`.shared/prompts/` の `g1-impl.md`・`g1-review.md`・`g1-impl-report.md`・`g1-report.md`・`g1-head-sha.md`・`g1-scene.md`・`g1-rest.md`・`seat-briefs.md`（`parts/` から `git mv`。字は変えない。`seat-briefs.md` は D1 で fix の `parts/` に置いた物）・`prompt.render_shared`・`writerblock.subagent_items`。`unit_note`・`NOT_NOW`・`NONE` は `lib/planbrief.py`（`brief_rows` と下請けの題が使う）。
- この block のコード: `src/prompts.py` の `writer_slots`（2.3。今の `writer`・`writer_values` の後継。`subagents` も組む）・`scripts/fix_prep.py`・`fix_ruled_prep.py` の返り（`order`・`slots`。2.2。`prompt` は D2 で外した）・`src/writers.py` の `node`（include の id を返す）と `reply_of(blocks, pass_)`（返りまるごとの 4 つの欄を読み、pointer を解く。2.8）と `hand_over`・YAML の 2 つの鎖（2.2.1）・`fix-accept`・`fix-ruled-accept`・`consult-check` の `with:`。
- 消す: `prompts/tdd-close.md`・`pin.md`・`tidy.md`・`static.md`・`remove.md` と `-ruled` の 4 本、`parts/tdd-close.md`・`pin.md`・`tidy.md`・`static.md`・`remove.md`、`parts/writer-top.md`・`writer.md`・`brief-head.md`・`brief.md`（`.shared` へ）（D1）。D2 で `prompts/variant.md`・`variant-ruled.md`・`parts/variant.md`（頭の役の文は `weapon-variant` の `prompts/parts/head.md` に移った）・`parts/g1-*.md`・`parts/seat-briefs.md`（`.shared/prompts/` へ）を消した。錨 `writer_launch`・`fix_reply` は、使う node が残らなくなった D2 で消した。
- 置き場: 型の block だけが使うコードは型の block の `src/`（憲法の 4）、2 つ以上の block が使う物は `.shared/`、`lib/` は Archon を知らない物だけ（E3）。共通の本体を `.shared/` に置く訳は 24.4。

### 1.6 つなぎ方（graph の側。block には書かない）

- line の 1 回目の修正の段（include の id `fix`）: `mode: whole`・`judgment` ← diagnose の `judgment`・`answer_ties`・`materials` ← line（今の judge-out の同じ欄）・`plan`・`fix_plan`・`ripple` ← plan の往復の最後の周・`plan_review` ← 最後の事前審査・`answers` ← 修正前の承認ノードの答え（`asked` を付けて。F225）・`request_answers`・`unattended`・`parallel`・`test_cmd`・`reuse_dir`・`user_env_dir`・`lang` ← 始めの記録・`policy` ← 始めの記録の固めた写し・`request` ← 依頼のファイル・`baseline` ← `$test-gate-base.output.baseline`・`tdd_suite` ← `$test-gate-base.output.suite`・`reuse_key` ← line の run の id・`skip_rerun` ← line が深さの表から引いた軽量の単位（段 → 回す物の表が「緑の後の試験の走らせ直しを省く」を持つ段だけ。今の `depth.omits`）。
- 2 回目の修正の段（案の直しの後）: 同じ物に `plan`・`fix_plan` ← 案の直し・`ripple`・`answers`・`notes` ← 案の直しの承認ノード・`only_items` ← `$fix.output.replan_items`・`prior` ← `$fix.output.carry`・`plan_review` ← 案の直しの事前審査。
- 読み手（line の設計書で配る）: line の受け皿と 2 段の合わせ（`units`・`groups`・`conflicts`・`objection`・`stop_reason`・`ok`・`diff` ほか）・line の上げ直し（`units`・`conflicts`・`diff`・`plan_declared`・`objection`・`tdd_refused`・`accept_trace`）・delta-review（`start_tree`・`reply`・`ruled_reply`・`scope`・`conflicts`・`checked`。`when:` は `checked.ok` と `stop_reason == ""` と line の深さの表）・eyes と r2・r4（`units`・`changed`・`x_scalars`・`plan_declared`・`tdd`）・lens（`start_tree`）・merge（`item_claims`）・line の最後の承認ノードと report（`handoffs`・`mismatched`・`allowed_tests`・`accept_trace`・`closure`・`removed`・`removed_tests`・`untested`・`conflicts`・`freeze_off`・`report`）・案の直し（`replan_items`・`conflicts`）。
- 組の子の作業ツリーの後始末は line の終わりの node（今の `sweep_children`）。
- `workflow: works-factory-fix` は `workflows/fix/` の block を指す（pack は `workflows/` の 1 つ。README 3 節）。

## 2 書き手に渡す slots と型の block の鎖（修正役の設計シートだった節。段 2 の D1 で書き直した）

段 1 の PR B（23 節）で、修正役 `fixer`・`fix-ruled` は型ごとの書き手 6 つの node に分かれた。段 2 の D1（下書き [2026-10-24-fix-weapons.md](../plans/2026-10-24-fix-weapons.md) の 11 章）は、そのうち 5 つ（tdd の閉じ・pin・tidy・static・remove）を、D2 は残る variant を、修正の block が `include:` する葉の block `workflows/weapon-<型>/` に出す（憲法の 3 の外し。持ち主の決め `leaf-include`）。この節は D2 の段 1 の後の形で、修正の block が書き手に渡す物（注文 `order` と指示の材料 `slots`）・鎖の並び・受け付けの読みを書く。型の block の側の共通の形（node の並び・共通の本体・写しの照らし）は 24 節、型ごとに違う物は型ごとの設計書（[weapon-tdd-close.md](weapon-tdd-close.md)・[weapon-pin.md](weapon-pin.md)・[weapon-tidy.md](weapon-tidy.md)・[weapon-static.md](weapon-static.md)・[weapon-variant.md](weapon-variant.md)・[weapon-remove.md](weapon-remove.md)）。

2.3 の並びと 2.5 の骨組みは、型の block に出した後も、書き手の組み上がった指示の並びと同じ（指示の文は変えず、md の置き場だけを移した。割った先は 2.3 に書く）。2.6・2.7 は作り直しの時の記録で、字を直さない。

### 2.1 役

直す義務の単位を作業ツリーの上で直し、単位ごとに 1 行（閉鎖の実証・覆いの母数・根か症状か・破りに行った入力・壊しうる面・先行例）と周の全体の欄を返す。型ごとの書き手が、自分の型の単位だけを受ける（役の 1 文は型ごとの設計書）。TDD の loop が緑にした単位は直し直さず行を写す（`tdd-close`）。項目ごとに実装役と審査役の下請けを Agent で起こす（表の `SPAWNS` が真の型。下書きの 11.8 の決め〔案 B〕で tdd の閉じの外の 5 つ。variant だけではない）。範囲の外が要れば `consult` で相談し、曲げるしかなければ食い違いの申し出を返す。裁定の後の段（段の番 2n）は、裁定（直す裁定）の文のとおりに、裁定が名指した単位を直し直す同じ書き手で、同じ型の block を 2 つ目の鎖（`wr-<型>`）で起こす（22.5）。

### 2.2 port

修正の block が型の block に渡す 2 つ（どちらも pointer。`fix-prep`・`fix-ruled-prep` が place に書く）:

- `order`: 形 `shared:weapon-order.schema.json`（注文 `{weapon, group, stage, since, base, units, scope, permits}`。22 節）。型ごとの `orders/<型>.json` を指す。型の block は注文の `weapon` だけを読み、表 `ORDER_WEAPON` と違えば落ちる。
- `slots`: 形 `shared:writer-slots.schema.json`（2.3）。place の `slots-<node>-<n>.json` を指す。

`fix-prep`・`fix-ruled-prep` の返りは `{go, iteration, writer, order, slots}`（`order`・`slots` は `go` が偽の周は書かず、`required` に入れない）。`writer` は起こす include の id（`writers.node` が返す。1 回目の段 `w-<型>`、裁定の後の段 `wr-<型>`）。指示の字 `prompt` は、全部の型が block になった D2 で返りから外した（型の block が組む）。注文の無い置き場（注文を書く段を通らない置き場。`writers.current` が FALLBACK の variant を返す）は、型の block が注文を必ず受けるので、`writers.hand_over` が直す義務の全部を受ける注文を `fallback-order-<段>.json` に書いて指す（`orders/` に書くと注文の在る置き場になる。本番は `orders` の node が先に注文を書くので通らない）。

型の block の出力は `{ok, reason, reply, report}`（`reply` は pointer。形 `json(shared:writer-reply.schema.json)`。受け付けの前の返答のファイル `reply-<n>.json`。`ok` が偽の周は `null` で、`reason` が訳。`report` は報告に載せる行）。受け付け（`fix-accept`・`fix-ruled-accept`・`consult-check`）は返りまるごとを受け、`writers.reply_of` で 4 つとも読む（2.8）。

指示が名指すファイル（今までと同じ。place に置かれた物）: `values.json`（← port `policy`・`request`・`lang`・`tdd_suite`）・`judgment.json`（← `judgment`）・`fix-plan-reply.json`（← `fix_plan`）・`plan-fields.json`（← `plan`）・`p2.plan_review.json`（← `plan_review`）・`ripple.json`（← `ripple`）・`human-notes.md`（← `answers`・`request_answers`・`unattended`・`notes`）・`baseline.json`（← `baseline`）・TDD の loop の要約（組の中の `tdd-<k>/summary.md`）・範囲の相談の控え（place）・却下の控え `rejects-fix-accept-<型>.json`（裁定の後は `rejects-fix-ruled-accept-<型>.json`）・裁定の文 `conflict-rulings.md` と保存した 1 回目の返答 `fix-reply.json`（裁定の後だけ）。型の block の place（`<修正の block の place>/<include の id>/`）には、組み上がった指示 `<型>-prompt-<n>.md`・返答 `reply-<n>.json`・返す node の返り `out-<n>.json` が置かれる（24.4）。

#### 2.2.1 鎖の並び（`fix-loop`。裁定の後の `fix-ruled-loop` も同じ形で `wr-`・`fix-ruled-prep`）

- 並び: `fix-prep` → `w-tdd-close` → `w-pin` → `w-tidy` → `w-static` → `w-variant` → `w-remove` → `consult-check` → `consult-ask` → `consult-accept` → `fix-accept`（今の書き手の node の並びのまま。`writers.SEQUENCE`）。`w-variant`（裁定の後は `wr-variant`）も include `works-factory-weapon-variant`。
- include の node ごとに: `include: works-factory-weapon-<型>`・`depends_on: [fix-prep, <前の include>]`・`trigger_rule: none_failed_min_one_success`（先頭の `w-tdd-close` は前が無いので書かない）・`when: "$fix-prep.output.go == true && $fix-prep.output.writer == 'w-<型>'"`・`with: {order: "$fix-prep.output.order", slots: "$fix-prep.output.slots"}`。
- 1 つの鎖の中で同じ字の `with:` は YAML の錨 1 つ（1 回目の段 `&w_with`・裁定の後 `&wr_with`）で書く。受け付けと `consult-check` の `with:` の返りの組も、鎖ごとに錨 1 つ。型ごとに違う `id`・`include`・`depends_on`・`when` は写しで、`tests/blocks/fix/test_yaml.py` が照らす。
- include の `when:` は展開した block の入口の node（`<型>-prep`）に付き、後ろの 2 つは上流が飛べば飛ぶ。鎖の次の include の入口は `trigger_rule` で、前の include が飛んでも走れる。この形で、飛ばされた include の後ろの型の block の AI が前の周の会話を継ぎ、展開の後の輪の本体に並んだ層が出ないことを本物の役で見た（下書きの 11.5 の確かめ 3・5）ので、`depends_on` の書き方は直さない。
- `consult-check`・`fix-accept` の `depends_on` は書き手の node の名の代わりに include の id を並べる（include を名指す `depends_on` は block の出口の全部を待つ）。`nodes-ok` の柵は loop の node を名指しているので変えない。
- 型の block の AI の node は include の中なので、起こし方（`model`・`settingSources`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry`）と返答の形は型の block の YAML に写す（24.6）。修正の block の YAML の錨 `writer_launch`・`fix_reply` は、使う node が残らなくなった D2 で消した。

### 2.3 slots の値と段落の出どころ（指示は 3 つの md から組む。下の並びは組み上がった指示の並び）

`prompt.render` は md の全部の `{name}` に値を要り、使われない値も拒む（README 5.2）。値と段落の名の全部が形 `.shared/schemas/writer-slots.schema.json` に並ぶ（形が鍵の組を決めれば、組む側と読む側の食い違いは `ports.json` の照らしで落ちる。憲法の 6）。組む口は 2 つに分かれる。

- 修正の block の `src/prompts.py` の `writer_slots(place, repo, pass_, weapon, values, **kw)`（今の `writer`・`writer_values` の後継。1 回目の段と裁定の後の段の両方を組む）: 型を問わない値と段落を組み、slots にする。中身は今の `writer_values` の順のまま、型が持つ物を組まない。`**kw` は今の `writer_values` の名前だけの引数のまま（`owed`・`items`・`sources`・`green`・`frozen`・`shared`・`saved_reply`。名も既定値も変えない）。義務の表から引く段落（下の 4 つ）も修正の block が引く（型の block は義務の表を知らない）。渡した証拠の種類の控え（`rules.remember`）・回の数え（`rules.iteration_next`）・相談の飛ばしの控え（`board.consult_skip`）は今のまま修正の block で、呼び手が slots を組めた後に控える（形の照らしで落ちた周は控えない）。
- 型の block の共通の本体（`workflows/.shared/writerblock.py` の `prep`。24.4）: 型が持つ値と段落を足し、`prompt.emit` で指示を組む。型ごとに違う所は block の `src/render.py` の表の 3 つの定数だけ（24.5）。

slots の形（`{values, when, subagents, summary_file}`）:

- `values`: object。型が持つ物を除いた全部（`rejection`・`rulings_file`・`saved_reply`・`brief_rows`・`faces_rows`・`scope_rows`・`tests_rows`・`tests_how`・`policy_path`・`request_file`・`judgment_file`・`open_units`・`plan_file`・`notes_file`・`budget`・`draft`・`check_cmd`・`ripple_file`・`libdocs_rows`・`answer_file`・`left`・`lang`）を `properties` で名指し、全部を `required` にする。
- `when`: object。型が持つ段落を除いた全部（`rejected`・`rulings_first`・`ruled_reply`・`briefs`・`faces`・`scope`・`tests`・`tests_new`・`tests_tail`・`tests_broken`・`frozen_files`・`tests_how`・`rules`・`ask`・`ask_ripple`・`libdocs`・`resume`・`queued`・`overflow_answer`・`conflict`・`docs`・`prompts_kind`・`config`・`code`・`evidence`・`where_writer`・`where_tdd`・`where_rework`・`rules_change`・`rules_sites`・`rules_red`・`conflict_change`・`policy`・`no_policy`・`request`・`no_request`）を全部 `required` にする。
- `subagents`: object。下請けの材料（データだけで、指示の文を持たない。`owed`・`briefs`・`all_items`・`seat_brief_rows`・`judgment_file`・`policy_path`・`base_rev`・`check_cmd`・`directory`）。9 欄を全部 `required` に置き（D2 で足した）、下請けを起こす単位が無い周・続きの周は `owed`・`briefs`・`all_items` を空の並び、字の欄を空の字にした形で置く（下書きの 11.4 の 5 の「空の並び」。object なので、欄を落とさず空の値で置く形にした。D1 は空の `{}` を通していた）。`writer_slots` は型を問わず同じ組み方で渡す（`prompts.subagents_slot`。下請けを起こす単位は TDD の輪が緑にした単位を除いた物〔`rules.dispatched`〕）。下請けを起こすかは型の block の表 `SPAWNS` が決め、偽の型の block は `subagents` を読まない。続きの周は空の形（`prompts.no_subagents`）。
- `summary_file`: 字。TDD の輪の要約のパス。`values` に入れず、上の段の欄に置く。tdd の閉じの書き手の注文の時だけ空でなく、読むのは `weapon-tdd-close` の `src/render.py` の表（定数 `SUMMARY`）だけで、本体が自分の値に足す。訳: `{summary_file}` を持つ md は `weapon-tdd-close` の頭の段落だけで、使われない値は拒まれるので、ほかの型に同じ組の `values` を渡せなくなる。

型が持つ物（slots に入れない。足すのは本体 1 か所）: 値 `first_prompt`・`unattended`・`overlay_file`・`summary_file`（`SUMMARY` が真の型だけ）・`g1_items`（表の `SPAWNS` が真で、続きの周でなく、`subagents.owed` が空でない時だけ。それ以外は空）と、段落 `spawns`・`g1`・`ask_variant`（表の `SPAWNS` から `writerblock.paragraphs` が引く）。足す名が slots の名と重なれば本体が落ちる。続きの周（`resume`・`overflow_answer`・`queued` のどれかが真）は続きの段落だけを組む周なので、本体は `unattended`・`overlay_file`・`summary_file`（`SUMMARY` が真の型だけ）を空にする（今の `writer_values` の早い返りは組まない）。`ask_variant` は slots の `ask` が偽なら偽（相談の節が入る周だけ。今の `writer_values` と同じ）。

段落の真偽（`writer_slots` が組む `when` の名と意味は下の表。入れ子にしない決まりなので、どの段落も 1 つの名で選ぶ。値の組はいつも同じで、入らない段落の口には空の字を渡す）。

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
| `g1` | 型が持つ段落（本体の `writerblock.paragraphs` が表の `SPAWNS` から引き、下請けの項目が 0 件の周は `prep` が偽に下ろす）。`SPAWNS` が偽の型ではいつも偽 |
| `seat_one` | （PR B で消した。付録 A の F108・F148b。下請けを起こさない周に借りた implementer の型を直に載せる段落） |
| `resume` | 相談の答えを渡す続きの周（今の `fix-consult-resume`） |
| `queued` | 受け付けがはみ出しを相談に積んだ続きの周（今の `fix-overflow-queued`） |
| `overflow_answer` | はみ出しの答えを渡す続きの周（今の `fix-overflow-resume`。答えの行の origin が accept） |
| `ask_variant`・`spawns` | 型が持つ段落（表の `SPAWNS`。`ask_variant` は下請けは自分で相談できないの 1 文で、`ask` が偽なら偽。`spawns` は下請けへの検索の決まりの渡しの段落） |
| `rules_change`・`rules_sites`・`rules_red`・`conflict_change` | 義務の表から引く 4 つ（修正の block が `writer_slots` で引いて `when` に入れる。`duties.box_of`・`board.RED_WEAPONS`・`SITES_WEAPONS`。指示と照らしを同じ表から引く今の形を保つ。型の block は義務の表を知らない。`prompts.writer_paragraphs` はこの 4 つだけを返す） |

並び（今の `rulebook.render` の並び: 却下の 1 行 → before → 決まり → 言語の 1 行）:

1. `<!-- if rejected -->` `{shared:rejected}`（`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "fix-accept"))`。fix-ruled は `"fix-ruled-accept"`）。
2. `<!-- if rulings_first -->` 裁定の文を先に全部読めの 1 文と `{rulings_file}`。
3. `<!-- if ruled_reply -->` 保存した 1 回目の返答を先に全部読めの 1 文と `{saved_reply}`（今の文の「あなたは新しい会話なので」は外す。13.2 の 2）。
4. `<!-- if briefs -->` `## The requirement (briefs)` と `{brief_rows}`（← `src/rules.py` の `brief_rows`。項目ごとの 1 行〔項目の番号・brief のパス・sha256・単位。今直さない単位は「今は直すな」と添える〕を `planbrief.for_units` の項目から組む。見出しと結びの 1 文〔「まず Read で全部読め…」〕は md の部品 `.shared/prompts/brief-head.md` で、書き手の指示（`writer-top.md`）と TDD の役の指示が `{shared:brief-head}` で入れる。下請けが Read する座の型の `[BRIEF_FILE]` の本文は、D2 まで fix に残る `rules.py` が `prompts/parts/seat-briefs.md`〔中身は `{shared:brief-head}` の 1 行〕を `render_part` して同じ部品から組む。lib の `planbrief.head_text`・`unit_note` は呼ばない）。
5. `<!-- if faces -->` `## Pre-review keys to answer (plan_faces)` と頭の 1 文と `{faces_rows}`（← `board.plan_faces_text` の行）。
6. `<!-- if scope -->` `## Paths you may change and what you must not touch` と頭の決まり（今の `planrange.OOS_MINE`）と `{scope_rows}`（← `src/rules.py` の `scope_rows`。項目ごとの範囲の行と全部の項目に効く許しの行だけ。lib の `planrange.scope_text` は呼ばない）。`<!-- if tests -->`（13.4 の 6）`## Tests you may add or change, and frozen tests` と頭の 1 文と `{tests_rows}`（← `src/rules.py` の `tests_rows`。足してよい新しいテスト・本体を変えてよい既存のテストの名指しと範囲・凍ったテストの行だけ。lib の `planrange.tests_text` は呼ばない）と結びの 1 文（名指しの外の既存のテストの関数を変える・消すと拒む）。
7. `<!-- if tests_how -->` `## How the tests were run before the fix` と `{tests_how}`（← `board.tests_how_text` の how の行）と「環境や命令を探さずにこの形で回せ」。
8. `<!-- if policy -->` 方針の文書の 1 行と `{policy_path}`／`<!-- if no_policy -->` 「方針の文書は無い」。`<!-- if request -->` 依頼のファイルの 1 行と `{request_file}`／`<!-- if no_request -->`。
9. `<!-- if rules -->` `# Fixing (the writer's job)` と役の 1 段落（型の block の `prompts/parts/head.md`。型ごとに違う頭の段落。出どころは型ごとの設計書）と `## What to read`（ここから `writer.md`）（`{judgment_file}`・`{open_units}`・`{plan_file}`・`{policy_path}`・`{summary_file}`・`{notes_file}` と各行の決まり。今の `direct.md` の `fix-head`）。
10. `{shared:brief}` と `{shared:writer-rules}`（2.3.1。`conflict` はいつも真）。
11. `<!-- if rules -->` 何も変えずに済んだと言うな（今の `fix-keep`）。
12. `<!-- if ask -->` `## Scope consultation and the pre-check`（今の `fix-ask`。`{budget}` ← `consult.BUDGET`・`{draft}`・`{check_cmd}`）。`<!-- if ask_ripple -->` 波及の一覧の 1 行と `{ripple_file}`。
13. `<!-- if libdocs -->` `## Library documents (installed version and official)` と頭の 1 文と `{libdocs_rows}`（← `libdocs.section` の本文から見出しと頭の 1 文を除いた行。数・取れた物・ライブラリごとのパス。取る・控える仕事を含む `section` は plan の枝も使うので lib に残り、この block は見出し〔`libdocs.TITLE`〕と頭の文〔`libdocs.HEAD`〕を剥がして行だけを入れる）。
14. `<!-- if g1 -->` `## Running subagents`（今の `seat.G1_HEAD`・`G1_STEPS` の 6 手順・`G1_LOOP_NOTE`・`DIVERGENCE_HINT` の 6 つの場面・`G1_OVERRIDES` を英語の決まった文に）と `{g1_items}`（← 項目ごとの 1 行「項目 n: 実装役 <ファイル>・審査役 <ファイル>・差分のコマンド <字>」）と `## Reading borrowed skills` の頭の 1 文と `{unattended}`（← `seat.overlay_body(seat.OVERLAY_KINDS["fix"])`。日本語のまま。local-review の設計書と同じ）。
15. （PR B で消した。付録 A の F108・F148b・G18）`<!-- if seat_one -->` `## The borrowed seat`（今の `seat.HEAD`・`WINS`・`PROMPT_HEAD` を英語に）と `{seat_body}`（← `seat.fill` で埋めた superpowers の implementer の型。借りた写しの字のまま）と `{unattended}`。
16. `<!-- if rules -->` `## What to write for each fix (one changes row)` と `## What to write for the whole round` と、受け付けが見る物の結びの段落（今の `fix-reply`）。
17. `<!-- if resume -->` `# The answer to your scope consultation (continued)` と `{answer_file}`・`{left}`。
18. `<!-- if queued -->` `# Overflow the acceptance found (sent to consultation)`。
19. `<!-- if overflow_answer -->` `# The answer about the overflow (continued)` と `{answer_file}`・`{left}`。
20. 人に見せる欄の言語の 1 文と `{lang}`（名指す欄: `changes[].what`・`closure` の文の欄・`root_or_symptom.why`・`bypass_tried`・`breaks` の文の欄・`precedent.reason`・`not_done[].why`・`interactions[].checked`・`combined_effect`・`plan_faces[].how`・`rejudge_requested`・`premise_drift_note`・`conflicts[].why_both_cannot_hold`・`consult[].why`・`bash_writes[].why`。key・enum・パス・コマンドは字のまま）。

続きの周（17〜19）では 1〜16 の段落が全部偽になる。ただし共通の断片 `writer-rules` の段落を選ぶ名は `conflict` と 4 つの種類だけなので、10 の `{shared:writer-rules}` の直し方・食い違いの申し出・守ることは続きの周にも入る（今の続きの周は続きの段落と言語の 1 文だけだった。指示が長くなるだけで、役のする事は変わらない。13.2 の 1）。続きの周の 4 つの種類は偽にする。

#### 2.3.1 書き手と TDD の役が共に使う断片

どの段落も 1 つの名で選ぶ（TDD の役はいつも `rules`・`conflict` が真）。

- `.shared/prompts/brief.md`（D1 で `parts/brief.md` から移した。書き手の型の block 5 つと、この block の TDD の役〔`parts/tdd.md` の `{shared:brief}`〕が使う）: `<!-- if rules -->` `## Brief rules (the source of the requirement and the background)` と決まり 1〜8（今の `brief.md` の `brief-canon`）。
- `{shared:writer-rules}`（1.5.4。delta-review の PR が置く）: いつも入る `## How to fix`（今の `core-fix` の 10 の決まり）と `## Evidence for fixes whose red-to-green a test cannot show` の頭、`<!-- if evidence -->` の頭と、書く場所の `<!-- if where_writer -->`・`<!-- if where_tdd -->`・`<!-- if where_rework -->`、`<!-- if docs -->`・`<!-- if prompts_kind -->`・`<!-- if config -->`・`<!-- if code -->` の 4 つの種類、`<!-- if conflict -->` `## Conflict declarations (do not bend to get green)`（今の `core-conflict`）、いつも入る `## What to keep`（今の `core-keep`）。

#### 2.3.2 下請けの指示（`prompts/parts/g1-impl.md`・`g1-review.md`。1.5.4 の `prompt.render_part`）

D2 で修正の block から `lib/subagents.py`（値と借りた型の埋め）・`.shared/prompts/g1-*.md`・本体 `writerblock.prep`（ファイルを書いて md を組む）へ移した（下書きの 11.8 の決め。案 B。24.9）。

- `g1-impl.md`: `{template}`（← `seat.fill` で項目ごとに埋めた superpowers の implementer-prompt。借りた字のまま）と、works の決まり（今の `seat.G1_SUB_HEAD`・`G1_SUB_RULES`）・`{shared:query-rule}`（`spawns` は偽。今は `lib/agents/judge.md` の写しを入れていた）・範囲の外が要る時の決まり（今の `direct.md` の `fix-ask-sub`。`{check_cmd}`）。
- `g1-review.md`: `{template}`（← task-review の型に `BASE_SHA`・`DIFF_FILE`・`GLOBAL_CONSTRAINTS` を入れた物）と今の `seat.G1_EXTRA`。
- 本体 `writerblock.subagent_items` が `prompt.render_shared` で組んで、型の block の place の `g1-impl-<n>.md`・`g1-review-<n>.md` に書く（名は今のまま。修正役は今どおりファイルの中身を字を変えずに下請けに渡す。D2 で `src/prompts.py` の `g1_files` から移した。24.9）。

### 2.4 返す形

返答の形は `.shared/schemas/writer-reply.schema.json` 1 本（今の錨 `&fix_reply` の `output_format` を字のまま写した物。`precedent` の `allOf`・`if`・`then` も。13.2 の 6）。型の block の AI の node の `output_format` は、この形のファイルと同じ中身を YAML に書く（Archon は `output_format` を外のファイルから読まない。README 4.1）。写しは型の block の数だけ増えるので、1 つの照らしで縛る（24.6）。字のまま写すのは D1 の形で、必須の欄を減らさない（持ち主の決め `no-na`）。人に見せる欄と言語は 2.3 の 20。

`.shared/schemas/` に今在る `fix-reply.schema.json`（delta-review が読む、受け付けた返答をまとめた `{changes, not_done, plan_faces}`）は別の物。

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

8 節。読みの形（D1・D2）: `fix-accept`・`fix-ruled-accept`・`consult-check` の `with:` は、型ごとの `{from: "$w-<型>.output", if_skipped: null}`（裁定の後は `wr-`。型の block の返りまるごと。variant も同じ）。`with:` の鍵の名（`reply_pin` など）と、名の組み立て（`INPUTS_REPLY_<型>`）は今のまま。
- 受ける 3 つの script は、型の block の入力ごとに `ports.picked(os.environ.get("INPUTS_REPLY_<型>"), GOT)`（`GOT = ("ok", "reason", "reply", "report")`）の呼び 1 つで欄を拾う（E5 の照らしが、include した block の返りの欄 `ok`・`reason`・`report` にも読み手を求めるため。`workflows/line/works-factory-line.yaml` の受け手の script が block の返りまるごとを受けて `ports.picked` で拾うのと同じ型。窓口の決め、受付 20261026-123356-d51294 の 1。下書き 11.4 の 3 の `$w-<型>.output.reply` と、第 19 版の `ok_<型>: {from: "$w-<型>.output.ok"}` の行の代わり。返りまるごとに `ok` が入るので、`ok_<型>` の行は足さない）。
- `consult_check.py` は 2 つの段で同じ script で、どの型の入力も字の名で読む。止めた Archon の読み込みの照らし（`exec-input-validation.ts`）は、script が字の名で読む `INPUTS_<名>` に結びを求めるので、裁定の後の段の `ruled-consult-check` は段に無い tdd の閉じを `reply_tdd_close: ''`（空の字。`ports.picked` が `None` で読む）で結ぶ。
- `writers.reply_of(blocks, pass_)` は、`SEQUENCE[pass_]` の順に見て、起きた最初の 1 つの `(返答, 報告の行)` を返す（D2 で variant の字の道〔引数 `variant`・`skipped`〕を外した）。型の block は `ok` が真でなければ、block の名 `weapon-<block_of(型)>`・include の id（`writers.node`）と返りの `reason` を名指した `ValueError`（24.2 の「落ちた周の守り」。3 つの呼び手は `main` の最初の行で `reply_of` を呼ぶので、place に何も書く前に落ちる）。`reply` の pointer は `ports.json(<pointer>, "shared:writer-reply.schema.json")` で解き、報告の行は `report`。どれも起きていなければ `(None, [])`。形に合わない・読めない時は `ValueError`（今の呼び手が `rolekit.parse_reply` の失敗で上げる `ValueError` と同じ落ち方）。呼び手は `rolekit.parse_reply(raw)` を呼ばず、返りの dict をそのまま使う。
- 報告の行: `fix-accept`・`fix-ruled-accept` は周ごとに、起きた書き手の報告の行を `board.add_writer_report` で置き場の `writer-report.json`（`[{weapon, line}]`）に積む（範囲の相談の周も積む）。組の子の行は `group_result` の `writer_report`（`group_id` を足す）で親へ渡り、`finish` の `report` に「書き手 <型>（組 <id>）: <行>」で載る（`board.writer_report_rows`・`report.writer_lines`）。D1 の型の block は `report: []` を返すので、今は行が無い。
- 返答が形に合わない時の落ち方: 型の block の `<w>-save` が `ports.json` で照らして落ちるので、受け付けの却下と出し直しにはならず、その周の終わりに内の輪が落ちる（分ける前に AI の node が落ちた時と同じ。24.2 の「落ちた周の守り」）。形の照らしは前後の空白を除いて `minLength` を数えるので、Archon の `output_format` を通った返答でも落ちうる。
- 受け付けの義務の表（22.4 の `duties`）は修正の block に在り、型の block は知らない。

### 2.9 試験

14 節。守る keep-essence: 3・4・5・6・7・8・11。D1 で足す物: 型の block の試験（24.8）・`tests/blocks/fix/test_prompts.py`（`writer_slots` の `values`・`when` の鍵の組が形の `required` と等しい・義務から引く段落が `duties`・`board.RED_WEAPONS` の表どおり・brief の在る run で下請けの `[BRIEF_FILE]` が指すファイルの字）・`tests/blocks/fix/test_yaml.py`（鎖の include の id・`when`・`with`・`trigger_rule`・受け付けの `with:` の鍵）・`tests/workflows/test_writer_prompts_kept.py`（割る前と割った後の組み上がる指示の段落の真偽と値の比べ）・`tests/workflows/test_weapon_assets.py`（付録 A の行き先ごとの数と、型ごとの頭の文）。細目は各試験の docstring。

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

単位ごとに、テスト（赤）→ 直す（緑）→ 申告した時だけ整える、の 1 段ずつを返す。赤と緑は機械が JUnit の結末で判じる。義務の単位を tdd か direct に振る段（段 `route`）は、段 1 の PR A から TDD の輪の外の `route-loop` の役 `route` が受ける（指示は同じ md の `{part:tdd}`。`prompts/route.md` は 1 行。22.1）。輪が受けるのは `orders` が tdd に引いた単位だけ。tdd は同じ単位の続き（前の周の会話を継ぐ）、tdd-new は新しい単位の周（`context: fresh`）。指示は同じ md。

### 4.2 port

TDD の loop の状態 `tdd-<k>/state.json`（← 振り分けの `route-go` か注文の `orders` が `tdd.open_state` で作り、元の結末は組の頭が書いた `base.json` から写す。実行器 ← port `tdd_suite`、test_cmd ← `test_cmd`、軽量の単位 ← `skip_rerun`、使い回し ← `reuse_dir`・`reuse_key`）・`judgment.json`・brief・`fix-plan-reply.json`・`human-notes.md`・`values.json`（方針・依頼・`lang`）・`baseline.json` の how・前の周の却下の理由（state の `reason`）。

### 4.3 組み立ての順（`prompts/parts/tdd.md`。`tdd.md`・`tdd-new.md` は `{part:tdd}` の 1 行）

値と真偽は `src/prompts.py` の `tdd_values(place, state)`。TDD の役は毎周、決まりを全部渡す（今と同じ。`rules` はいつも真）。段の名 `phase_route`・`phase_test`・`phase_fix`・`phase_refactor` のどれか 1 つが真（`phase_route` は `route-prep` が `route` の指示を組む時の段で、輪の `tdd-prep` は test・fix・refactor だけを組む）。

1. 題 `# The TDD loop prompt (round {iteration}, phase {phase})`。
2. `<!-- if briefs -->` `## The requirement (briefs)` と `{brief_rows}`（振り分けの段は義務の単位の全部、ほかの段は今の単位と一緒に直す単位。項目のほかの単位には「今は直すな」）。
3. `<!-- if rejected -->` `## Why the machine rejected your previous answer (fix it and return the whole answer for this phase again)` と `{rejection}`（← state の `reason`。今と同じく前の回の理由だけ。段が進むと空）。
4. `<!-- if policy -->`／`<!-- if no_policy -->`・`<!-- if request -->`／`<!-- if no_request -->`（2.3 の 8 と同じ文）。
5. `## What this role does`（今の `tdd-head` の役の段落と「毎回全部読め」。今の「2 回目からは変わった物だけを載せる」は外す。13.2 の 3）と `## What to read`（`{judgment_file}`・`{open_units}`・`{plan_file}`・`{policy_path}`・`{notes_file}`）。
6. `{shared:brief}` と `{shared:writer-rules}`（2.3.1。`rules`・`conflict` はいつも真、種類は `kinds_now`。D1 で `{part:brief}` から替えた）。
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
- `group_start.py`: 今の `group_start.py` と同じ順（並べない子の前の組の止め #576 → 書き込みの記録 → `from_tree` の写し → 入力の写し〔`out_dir` が在れば `board.adopt_inputs(Path(out_dir).parent, place, repo)` が `values.json` も写す。`intake.json` は写さない。空なら `board.prep`〕→ 並べない子の自分の前の試みを戻す → `fix-ignored-before.json` → 始めの木 → `groups.json` → `group-start.json`）のあと、`tdd.start` の代わりに `suitefix.begin`（= `basecase.take`。22.3）で元の結末を取って `base.json` に書く。使い回しは `tree_run.reuse_place(values.reuse_dir, values.reuse_key, rerun=bool(os.environ.get(tree_run.RERUN_ENV)))`。対象のテストを起こす前に `ports.drop_runner_env(values.user_env_dir)`。工場の書いた実行器の取り置き・捨ては `suitefix.settle_kept`（19.1）。`suitefix.begin` の返り（`tdd-start.json` に書く中身。script の返りではない）は `{go, reason, suite, base_file, state_file, summary_file}` で、`go` は偽、`state_file` は空（輪の状態は振り分けか注文が置く）。軽量の単位（`skip_rerun`）は、輪の状態を置く `tdd.open_state` の `light` に `route-go`・`orders` が渡す。そのあと `orders.no_suite_why(place)` が空でなければ、`tdd-start.json` に `no_suite: true` と訳を足して返りの `no_suite` を真にする（19.1 の止め方の 1）。script の返り（YAML の `group-start` の出力）は `{tdd（base.json の taken）, units, reason, suite_broken, no_suite}`。
- `route_go.py`: `tdd-start.json` が `suite_broken` か `no_suite` なら `{route: false, stop: true}`。`routes` が `auto` で、`base.json` の `taken` が真で、`tdd-start.json` に `state_file` がまだ無く、振る単位（`route.route_keys`）が在る時だけ、`tdd.open_state` で輪の状態を段 `route` で置き（`route.begin`）、`tdd-start.json` に `go`・`state_file`・`summary_file` を書いて `{route: true, stop: false}`。輪の状態を置けない時（`base.json` が読めない・欄の控えが食い違う）は落ちる（黙って振り分けを飛ばし、tdd の単位を variant に回さない）。22.1。
- `route_prep.py`・`route_step.py`: `route-prep` は振り分けの指示を `prompts/route.md`（`{part:tdd}` の 1 行。`src/prompts.tdd` が段 `route` の値を組む）から `route-prompt-<n>.md` に書く（済んでいれば `{prompt: "", go: false}`）。`route-step` は `route.step`（今の `tdd-step` の振り分けの段と同じ確かめ）を呼び、止めた申し出を `common.flush_unsent` → `rulings.park` で `conflicts.json` に積み、却下の理由を `route-step-reject-<n>.md` に書く。輪の状態が無い組は `{ok: true, done: true}`。
- `orders.py`: `orders.compute(place, repo)`（22.2）。落ちる時は標準エラーに 1 行で 1。
- `tdd_prep.py`: 今の `tdd_prep.py` の値の組み立て（`tdd.prep` の段落の真偽と値）を `src.prompts.tdd_values(place, state)` にし、`prompt.emit("tdd-new" if new_unit else "tdd", values, when, prompt.round_of(…))` で組む。済んだ輪（resume で 1 周目から回り直した）は `{prompt: "", go: false, new_unit: false}`（今の早抜け）。brief の控えが壊れた・座が組めない・指示が組めない時は `prompt-error.json` に書いて落ちる（今の `Broken` で落ちるのと同じ）。返り `{prompt, go, new_unit}`。`new_unit` の決め（状態の `session_key` と鍵 `tdd-<k>:<route か今の単位>` の比べ）は今のまま。
- `tdd_step.py`: 今のまま（`tdd.step` → `tdd.flush_unsent` で `conflict.park_claims` → 却下が在れば `tdd-step-reject-<n>.md`）。返り `{ok, done, reason, reason_file, phase}`。
- `fix_prep.py`・`fix_ruled_prep.py`: 今の順（頭の木の控え `fix-head.json`〔ruled は `fix-ruled-head.json`〕と `skip-before.json` は 1 回だけ → 直す義務が空なら go: false → brief を切る → 続きの周〔相談の答え・はみ出しの積み・はみ出しの答え〕か、全部の決まりの周か → 下請けの材料〔slots の `subagents`。`src.prompts.subagents_slot`〕・ライブラリの文書〔`libdocs`〕・相談の控え〔`consult.json`〕→ `consult_skip`）。指示は D2 で型の block が組む（`src.prompts.writer_slots` が slots を渡す）。ruled の go は今のまま（PRIOR でも join-clash でもない直す裁定が在る時だけ）、ruled の 1 周目は `conflict-rulings.md` が無ければ書く。続きの周の `iteration` は今と同じく数え直さない。返り `{go, iteration, writer, order, slots}`。段 1 の PR A の追加: `fix_prep.py` は、頭で `orders.regive` を呼んで tdd の輪が諦めた単位を variant の注文に書き直し、組が no-suite で止まっていれば（`board.no_suite_stop`）`go: false` で修正役を起こさない。`fix_ruled_prep.py` は、段の頭で 1 度 `orders.write_ruled` で裁定の後の注文を書く（22.5）。
- `consult_check.py`・`consult_accept.py`: 今のまま（`board.consult_ask` で頼みを確かめて聞く頼みが在れば `prompt.emit("consult-answer"` か `"ruled-consult-answer", src.prompts.consult_values(…))`、`consult.settle` で答えを確かめて控えに残す）。`consult_check` の返り `{consulted, go, prompt}`（今の `prompt_file` は `prompt` に替える）、`consult_accept` は `{consulted, answer_file}`。
- `fix_accept.py`・`fix_ruled_accept.py`: 今のまま（8.2）。段 1 の PR A の追加: 受け付けが no-suite の止めを返したら（`got["stop"]`）、出し直させずに輪を抜ける（19.1 の止め方の 3）。
- `join.py`・`clash_prep.py`・`clash_accept.py`・`conflict_check.py`・`rule_prep.py`・`rule_accept.py`・`clean.py`・`assert_changed.py`・`group_end.py`: 今のまま（8.5〜8.7 と、`join` の当てる順・確かめ直し・戻し・控え・写しは 12 節の E）。`clash_prep.py` は `prompt.emit("clash-fix"` か `"clash-ruled", src.prompts.clash_values(…))`、`rule_prep.py` は `prompt.emit("ruler", src.prompts.ruler_values(…))` で返り `{prompt, go, iteration}`・`{prompt, iteration}`（今の `prompt_file` は `prompt` に）。`rule_prep.py`・`tdd_prep.py` が今している `rulebook.CANON`・`fixrules.SHARED`・`RULES_DIR` の差し替えは要らない（md は `prompt` の口が読む）。`join.py` と `clash_accept.py` の走らせ直しの test_cmd は `board.rerun_cmd` が `values.json` の `skip_rerun` で決める（今は単位の深さの控え）。
- `fix_reads.py`: `board.collect_reads(place, writelog.log_here(), repo=…)`。段ごとの `must_read` は判定の写しと今の周の brief のファイル（指示は字で渡すので指示書のファイルは無い）。`own`（その役の session を見分ける材料）は今の指示書のファイルの代わりに、その段の brief のファイル（brief の無い run は判定の写し）。`since` は今のまま段の頭の印の時刻（13.1 の 10）。落ちない（`reads.guarded`）。
- `finish.py`: `src.finish.collect(place, whole)`。今の `collect.py` の `block()`・`fields()`・`group()` と同じ順で書いて読む（2 回目の段なら `replan.close` → `closure.json` → `allowed-tests.json`・`accept-trace.json` → `fix.diff` → `tdd-unit.json`〔今の `tdd-unit` の node の中身〕→ `frozen.json` → `fix-reply.json`〔`board.group_fix_reply`〕→ `scope.json`〔`fixboard.scope_brief`〕→ `carry.json`）。差分の審査とレンズの控え（`delta-holes.json`・`lenses.json`）は書かない。`ok` は 1.2 のとおり。中の誤りは今の `fallback` と同じく落ちずに `ok: false` と理由（`fix-collect-error.txt` を指す `diff`・空の `allowed-tests.json`）。lib が読めない時の stdlib だけの返り（今の `ports()`）も残す。

## 8 受け付け

どの受け付けも、却下の理由の文は日本語のまま Python が組む（README 5.3）。却下は `rolekit` の控え（`rejects-<名>.json`）に積み、次の回の prep が全部（古い順）を `{shared:rejected}` に入れる（今は `rejects-<名>.md` のパスを指示の 1 行目で名指していた）。3 回目の却下で諦める（`rolekit.GIVE_UP_AFTER`）。諦めても run は止めない。

### 8.1 共通の確かめの順（修正役の受け付け `board.accept_reply`。今の `fixboard.accept_reply` の写しのまま）

確かめは全部回してから最後に 1 回だけ拒む（F131）。拒否の文は `FIX_CHECKS` の順の見出しで並べる（「全部を 1 回で直して出し直せ」の決まった文は md の `.shared/prompts/writer-top.md` の段落 `rejected`。段 1 の PR B までは `parts/fixer.md`）。順と中身（どれも今の関数のまま）: consult（枠を使い切った後の consult。欄を外して続ける）→ frozen（`facts.check_frozen`。TDD の loop が凍らせたテストのファイル。許すのは `conflict.ruled_test_limits` の範囲だけ。段 1 の PR A から `duties.frozen_by_returns` を並べて、返しの控え `returns/` の凍結も注文の `permits` の範囲だけで照らす。どちらか厳しい側で、両方を通る物だけを通す。22.4）→ writes（`writes.check`。記録の無い run は `fixboard.undeclared_writes`）→ conflict（`board.take_conflicts`。`conflict.problems_by_entry` の欄・語・名指しの現物の照らし）→ pack（`.archon/` の下）→ excluded（`board.check_excluded`。新しい: 並行 PR に回した hunk〔port `excluded`〕の行に、修正の段の始めの木から今の作業ツリーへの変更〔`git diff -U0` の旧い側の範囲〕が触れたら、hunk ごとに「並行 PR #<pr> に回した hunk <file>:<start>-<end>（<why>）を変えた」と名指して拒む。行の番号は並行 PR の確かめが走った時の作業ツリーの行なので、始めの木の中の位置は錨〔行の `sha256`〕で引き直して比べる〔2 回目の段や順に回す組の 2 つ目以降は始めの木で行がずれる〕。錨の無い行・錨が木に無い行は記録した行のまま、同じ中身が複数在れば記録した行に近い方。始めの木が無い・git が読めない・木にファイルが無い時は、通さずに照らせない訳を 1 行で拒否にする。外した hunk が無ければ照らさない）→ duplicate → not_opened → excused（`board.fix_duty`）→ scope（`scope.check`。範囲・out_of_scope・add と remove の symbol・tests の id・同名の定義・案の外の新しいテスト）→ tests（`tdd.selected_problems`。変更に直に関わる試験を走らせ、元で赤でなかった試験の赤を拒む。元の結末は輪の状態があればその状態、無ければ `base.json`〔`board.accept_base`。static だけの組も実行器が在れば。厳しい側〕。名指しは輪の状態の今の名指しと、注文の `units[].tests`・`permits` の `rewrite` の行の和で、狭めない。22.4）→ no-suite の止め（`board.no_suite_at_accept`。走らせた回が 0 件・実行器が結末を返さない。型の義務より前に、事実 1 つで止める。当たれば拒否に数えず `{ok: false, stop: true}` で抜ける。19.1）→ duties（`duties.accept_problems`。型の義務。22.4）→ plan_faces（`board.plan_face_errors`）→ gates（`gates.problems`。受け入れのテストの base で赤・今の木で緑と、名指しの外の既存のテストの関数の本体の変更）→ closure（`board.closure_reply` と `unitrows.build`。閉じない defects の問い・数えられない問い）→ copy（`recount.accept_fix`。直す義務の単位の行・fix_closure の黙った値・interactions・bypass_tried・breaks.result・precedent・symptom の理由・coverage の母数と数え直し・clean なのに赤を見ていない・wrote_refs・差分が足した md のリンク）。

- はみ出しだけの回（`board.gather_overflow`・`split_rows`・`settle_overflow`）: 拒まず、まだ聞いていない物を相談に積み（拒否に数えない）、聞いた後の物は機械が戻して受け付け直す（F110・F111）。
- 1 回目の段で裁かれていない申し出が place に在れば、受け付けを抜けて裁定へ回す（`fix-parked-reply.json` を書く。F207。13.3 の 5）。裁定の後の新しい申し出は機械が ask_human に裁いて積む。
- 3 回目（`rolekit.is_last_attempt`）: 拒否の行を単位に結んで（`parking.settle`）、結んだ単位を足跡を共にする単位と一緒に段の頭の木へ戻し（`fix-parked-<n>.patch` に控える）、ask_human の申し出にして積み、残りの単位で頭から受け付け直す。止める単位が残らなければ義務の残りを全部止め、それでも残れば受けずに諦める（F133・F134）。
- 通った時: `fix-units.json`・`fix-reply.json`（ruled は `fix-ruled-reply.json`）・trace の行（`fix_accepted`・はみ出しの名指し・確かめずに受けた関門の訳・吸収した行）・`fix-unit-rows.json`・返しの控え `returns/<k>.json`（`duties.write_returns`。型ごとに 1 件。22.4）。
- 相談の周（`consulted` が真）は受け付けを回さず拒否に数えない（F135）。返答が無い（修正役が飛ばされた）時は `fix-units.json` に義務の単位を not_done で書いて done（1 回目）・何も書かずに done（ruled）。
- loop の上限 12 は「拒否 3 回 + 相談の枠 9」（`consult.BUDGET`）。試験が `max_iterations` と照らす（14 節）。

同じ関門 `board.check_excluded` を、受け付けを通らない変更の最後の網として 1 度ずつ回す: 組の形では `group-end` が組の始めの木から今への変更を照らし、触れた hunk の行を組の結果の `mismatched` に載せる（最後の関所を開ける理由として人に届く）。全体の形では `assert-changed` が run の始めの木から今への変更を照らし、触れていれば `ok: false` と hunk を名指す理由を返す。TDD の役・合わせ役・裁定の後の修正役の変更がここで照らされる（受け付けの 1 か所だけだと、TDD の輪が組の単位を全部緑にして修正役が飛ばされた run で素通りした）。

### 8.2 fix-accept と fix-ruled-accept の違い

ruled は、直す義務が `board.ruled_owed`（戻せた組の単位のうち fixed でない物）、頭の木が `fix-ruled-head.json`、輪の状態が `board.ruled_states`（今の段の輪だけ。PRIOR の輪は凍結に効く）、fix_test_scope の範囲がいつも許しに入り、裁定の `limits` のパスが範囲に入る（F109・F217）。

### 8.3 tdd-step（TDD の loop）

今の `tddloop.step` の写しのまま（入口の 5 つ・振り分けの段 8 つ・test の段 12・fix の段 7・refactor の段 1・申し出 1 の 34 の拒否の規則。段 1 の PR A から、振り分けの段の規則は `src/route.py` の `step`〔`route-step` が呼ぶ〕に移り、`src/tdd.py` は残りの段を持つ。拒否の数え方と書き込みの照らしと止めた申し出の流し〔`flush_unsent`〕は同じ）。拒否は段ごとに数え（段が進むと 0 に戻る）、3 回目で: 振り分けの段は振る単位を全部 AI の答え無しにして済む（`route._abort`。型は 22.1 の表で variant に引かれる）・test と fix の段は木を単位の頭に戻し、機械の申し出（`tdd-gave-up`・needs_context）を 1 件積んで次の単位へ・refactor の段は緑の木に戻して次へ（F021・F024）。案を直して戻った単位が又落ちたら ask_human（F023）。40 周に届く周は残りを direct にして済む（F027・F028。諦めた単位は `fix-prep` が `orders.regive` で同じ箱の variant の注文に書き直す。22.2）。実行器が JUnit を書かない（段 runner）周は、残りを direct にして済むが、もう修正役に回さず組を no-suite で止める（`tdd._abort` が輪の状態に `no_suite` を置く。19.1）。却下の理由は state の `reason` に積み、次の周の指示の頭に入る（3 の段落）。

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
2. 振り分けの段で役が作業ツリーを変えると拒むが、戻さない。3 回目の諦めでも戻さず、残った変更は修正の段の頭の木に入る（段 1 の PR A から `route._route`・`route._abort`。今も直さない）。申し出の周（phase conflict）は書き込みの出どころを照らさない。
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
16. 共通の断片 `writer-rules` の「テストで赤→緑を示せない直しの証拠」は、頭の段落 `evidence`（4 つの種類のどれかが真の時）と、答えを書く場所の段落 `where_writer`・`where_tdd`・`where_rework`（役ごとに 1 つだけ真）に分けた。続きの周は 4 つの種類が全部偽で、頭だけが残らないようにするため。使う block が自分の役の段落だけを真にする。食い違いの申し出の `conflicts` が無い役の言い方と「後の工程」の言い方も、特定の役・段を名指さない形にした。
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
- 段 1 の PR A の試験: `test_weapons.py`（振り分けの表・注文・元の結末・義務の表・返しの控え・許しの読み口・裁定の後の注文）・`test_no_suite.py`（19.4）。`tests/layers/test_weapon_imports.py` は、型のモジュールが別の型のモジュールを import していないことを縛る（段 2 で型が block になったら `test_block_shape.py` に任せて消す）。
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
9. 段 1 の PR A の形（22 節）は、本物の run で通していない（試験と筋書きだけ）。見る物: 振り分けの AI を `route-loop` に出した後の会話の継ぎ（22.1）・元の結末を組の頭に移した後の `base.json` の運び（22.3）・no-suite の止めが line の止めの道で後ろの段へ進めないこと（19.1）。
10. 輪の途中で実行器が結末を返さない時に、実行器を書き直す 1 回は段 1 の後に回した（19.1 の止め方の 2。輪の途中では呼べない）。
11. 型を 1 回ずつ回す順と、守れなかった依存を組の結果と報告へ出す所（22.2）は PR A で出口に届いていない（`orders.json` の `unsatisfied` に書くだけ）。

## 17 関わる試験だけで元の結末を取る（2026-10-20。持ち主の決め `related-tests-only`）

- 何を: `group-start` が組の頭で一式を 1 回走らせて取る元の結末（段 1 の PR A から `basecase.take` の `run_suite`。以前は TDD の輪の頭の `tdd.start`。22.3）を、(3) の道（`test_cmd` が空で、対象の根に `.review-checks.json` が無い run）では、組の単位が触る所に関わる試験だけにする。道 (1)(2) は変えない。詳しい決めと選びは `docs/design/test-gate.md` の 14 節。
- (3) の道かは fix が自分で決める: `related.applies(repo, values.test_cmd)`（`lib/related.py`）。test-gate の `by` を fix の port で運ばない。
- 起点: 組の単位の約束（`plan_contract` の `files` の行のパス。約束が無い単位は起点を足さない）。`related.pick(repo, rev="HEAD", seeds=<起点>, cache_dir=<置き場>/impact)` で選び、`related.args` を `run_suite` の `args` に、`only=True` で走らせる。選べない（`whole`）か、起点が 1 つも無い時は、今までどおり一式。選びが空（関わる試験が無い）なら、元の結末は空の一式でなく `{}`（`base.json` の `baseline`。`taken` は真）として輪を回し、受け付けと最後のテストの段が確かめる。
- 元の結末が関わる試験だけになるので、輪の緑の回の「元の結末に載ったモジュール」（`_reached`）は、選んだ試験のモジュールに絞られる。届かない試験・元の結末の外の試験は、今までどおり受け付けの `selected_problems` と最後のテストの段が確かめる。
- `base.json` に `related`（選びの結果）を置き（輪の状態にも `open_state` が同じ名で写す）、報告の節「走らせなかった範囲」が読む。
- 緑の確かめ（元の結末が関わる試験だけで、今の回が全部の試験の場面）: 関わる試験を選べなかった回（`_reached` が全部の試験）は、元の結末に無い試験も走る。この回の緑の確かめ（`baseline_red.green_problems` の `narrow`）は、比べる範囲を元の結末に載った試験・名指し・前の単位が赤から緑にした試験（`also`）に限る。範囲の外の赤では拒まず、一式の終了コードも範囲の結果が全部通っていれば問わない。元の結末が全部の試験だった PR の前の振る舞いに戻す向きの直し。

## 18 確かめ直しで前から同じ形で赤の名指しを、組を戻す理由にしない（2026-10-23。#837）

- 出どころ: issue #837（この節の直し）。持ち主は run の費用を無駄にしない方法の 1 と 2 を issue にしてよいかの問いに「1,2はい。」と答えた。方法の 1 は #836（直す前の試験で、試験を起こす起動スクリプトだけが赤なら、AI の判定を起こす前に止める）、方法の 2 がこの節（直す前と同じ落ち方の赤なら、その直しのせいではないので組を戻さない）。
- この節の語: 名指し（名指しのテスト）は、組の子の TDD の loop で修正役が赤 → 緑を確かめたテスト。結末は、試験を走らせて JUnit XML から読んだテストごとの結果の行の並び（直す前の結末は test-gate の block が取った `baseline.json` の `cases`。2026-10-23 から test-gate は直す前に試験を走らせないので、組の頭が取った失敗の文つきの結末〔段 1 の PR A から `base.json` の `baseline_cases`。場所は組の結果の欄 `base`〕を足して読む。`board.before_cases`・19 節・22.3）。結末の語は行の結果の種類（`passed`・`failure`・`error`・`skipped` など）。
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

## 19 試験の環境の壊れを組の頭（以前は TDD の輪の頭）で見つけて直す（2026-10-23。#836・持ち主の決め `base-runs-nothing`。段 1 の PR A で組の頭に移し、試験なしで直す逃げ道を閉じた）

- 出どころ: #836（書き直した本文）と #828。持ち主の言葉: 「ただ最初にふるてすとはテストは重いでしょ」「TDDでは自分の関係ないとこのテストを走らせないのでは」「自分に関係ないとこの試験はしないでしょ。で、自分に関係のあるところの試験が壊れてたらついでに直してあげるとかでいいのでは」と、下の 2 つに分けた直し方への「はい」。
- 前提: test-gate は直す前の版で試験を何も走らせない（`docs/design/test-gate.md` の 15 節）。工場が書いた実行器（試験の起動スクリプト）は、走らせずに test-gate の出力の欄 `suite` に結ばれて修正の段に届く。試験の環境の壊れは、関わる試験を最初に走らせる所（組の頭 `group-start` の元の結末の回。`basecase.take`。以前は TDD の輪の頭 `tdd.start`。持ち主の決め `base-runs-nothing` の字「TDD のループの頭」は「組の子の頭」に直した。`group-head-base`）で見つける。
- この節の語: 起動スクリプトは TDD の実行器（第 1 引数の書き先に JUnit XML を書く物）。工場が書いた実行器は、test-gate が取り置きから使ったか書き手の役が書いた物（line の `fix-in` が test-gate の返りの `suite_note` から決め、入力 `suite_made` で渡す。人が `tdd_suite` で渡した実行器は偽）。関わる試験は、組の頭の元の結末が走らせた試験（走らせ方が決まらない道は 17 節の選び、ほかは一式）。

### 19.1 壊れているのが工場の物の時（起動スクリプトの書き直し）

- 決まり（はい・いいえ。`basecase._suite_broken`）: `suite_made` が真で `test_cmd` が在り、組の頭の元の結末の回が結末を返さないか、試験が 1 件でも `error`（中身に届く前に落ちた）で、`test_cmd` を単体で走らせると緑なら、壊れているのは起動スクリプト。関わる試験だけを渡した回は、実行器を一式でも 1 回走らせ、それも同じく落ちる時だけはい（`test_cmd` の単体の回は一式を走らせるので、関わる試験だけを渡した回の `error` とは走らせ方が違い、起動スクリプトのせいとは言えない。実行器は `test_cmd` を字のまま含む約束なので、一式どうしなら同じ走らせ方を比べられる）。
- はいの時: `group-start` は輪を回さず（`tdd: false`・`suite_broken: true`）、同じバイトの取り置き（test-gate が照らしを通った実行器を run をまたいで置く所。`docs/design/test-gate.md` の頭の語）を捨てる（`suitewrite.drop_runner`）。`suite-fix-prep` が書き直す役の指示（`prompts/suite-fix.md`。壊れた本文・壊れた回のログの末尾・`test_cmd` の単体のログ。契約と書き方は test-gate の書き手と同じ共通の断片 `.shared/prompts/runner-writer.md`）を組み、`suite-fix`（AI。test-gate の `suite-write` と同じ群 `@wf-test-gate`・道具・砂場）が本文を返し、`suite-fix-try` が実行器のファイルを置き換えて（`suitewrite.put_runner`。一時のファイルから入れ替える）組の頭の元の結末の取りをやり直す（`suitefix.retry`）。
  - 直れば元の結末が取れて振り分けと注文へ進み、直した実行器を取り置く（`suitewrite.keep_runner`。取り置くのは元の結末が取れた組〔`base.json` の `taken`〕だけで、static だけの組の走らせていない実行器は取り置かない）。書き直した実行器でも元の結末が取れず壊れの印も付かない時は、組の頭と同じく止めの語 `no-suite` で止める（`suitefix.settle_start`。下の止める場所の 1）。実行器のファイルは test-gate の place の物を置き換えるので、最後の試験の関門も直した実行器を使う。
  - 書き直しても壊れたまま・書き手が作れない・返答が無い時は組を止める: `route-go` と `orders` の `stop` が真で、振り分けの AI も型の輪も修正役の輪も回さない（確かめていない直しを書き進めない）。組の結果の `tdd` に `suite_broken`・`runner_log`・`cmd_log` が載り、出口の `stop_reason` が `stopby.SUITE_BROKEN`（メイングラフ line〔`works-factory-line`〕は、出口の `stop_reason` が空でない run を今の止めの道で止め、後ろの段へ進めない）。報告の冒頭の知らせの行に訳とログのパスが出る（line の `workflows/line/src/facts.py` の `suite_broken_notes`）。
- 書き直しは 1 回だけ（`max_iterations` の輪にしない。数の上限でなく「書き直しても直らない時だけ止める」のはい・いいえ）。
- 人が渡した実行器と、`test_cmd` の単体も赤の時は今までどおり（試験そのものの赤）。直す前の版で test-gate がしていた起動スクリプトの照らし（JUnit XML が出て試験が 1 件以上）は、組の頭の元の結末の回が兼ねる。結末が無い時（実行器が無い・走らない）に TDD の輪を回さず直に直す逃げ道（持ち主の決め `suite-by-ai` の「照らしが通らなければ、今どおり TDD のループを飛ばして直に直す」）は、段 1 の PR A で閉じた。下の「試験なしで直す逃げ道を閉じる」。
- 並べた組の子が同時に同じ実行器を書き直すことがある。入れ替えは一時のファイルからの置き換えなので、走っている子は前の本文か新しい本文のどちらかを読む（後に書いた方が残る）。

- 試験なしで直す逃げ道を閉じる（段 1 の PR A。下書き 3.9・持ち主の答え 9.1 の 8。持ち主の決め `suite-by-ai` の「照らしが通らなければ、今どおり TDD のループを飛ばして直に直す」を替える。持ち主の決め `no-run-way-ask`〔`docs/owner-decisions.md`〕で替えた）: 実行器が無い・走らない組を、修正役に直に回さず、止めの語 `no-suite`（`stopby.NO_SUITE` = `works:no-suite`。`suite-broken` と並べて `lib/stopby.py` の表に足した）で止める。確かめていない直しを書き進めない向きは `base-runs-nothing` と同じ。止める場所は 3 つで、どれも yes/no で決める。
  1. 組の頭（`orders.no_suite_why`。`group-start` と書き直しの後のやり直し `suite-fix-try` が同じ口 `suitefix.settle_start` で呼ぶ）: 元の結末が取れていない（`base.json` が無いか `taken` が偽。実行器が無い・起こせない・結末が取れない）が、起動スクリプトの壊れ（`suite_broken`。書き直しの道が持つ）でなく、組に計画の語が `static` でない単位が在る時。「元の結末が取れていない」と「static でない単位が在る」はどちらも振り分けの AI の答え無しで決まるので、止める組では振り分けの AI を起こさない。`tdd-start.json` に `no_suite: true` と訳を書き、`route-go` が `stop: true`（`route: false`）、`orders` が `stop: true` を返し、型の輪も修正役の輪も回さない。**static だけの組は止めない**: 試験で示す物が無く、箱の義務も持たないので、実行器が無くても照らせる（実行器が在れば `base.json` を `taken: false`・`baseline: {}` で書く）。
  2. TDD の輪の途中（`tdd._abort` の段 `runner`）: 実行器が結末を返さない（走らない・JUnit を書かない）と、輪の状態に `no_suite: true` の印を置き、残りの単位を direct にして輪を抜ける。`fix-prep` は印が在れば（`board.no_suite_stop`）修正役を起こさない（`go: false`）。回数の上限（段 `budget`）と振り分けを諦めた時は止めにせず、同じ箱の別の型（variant）への書き直しのまま。輪の途中では実行器の書き直し（上の `suite-fix` の道）を呼べないので、輪の途中で実行器が結末を返さない・試験を 1 件も拾わない時に実行器を 1 回書き直す道は段 1 の後に回す（段 1 は止めるだけ）。
  3. 受け付け（`board.no_suite_at_accept`。修正役と裁定の後の修正役の受け付け。型の義務より前に、事実 1 つで止める）: 受け付けが変更に関わる試験を走らせた回について、次の (a) か (b) のどちらかが成り立てば止める。(a) は 1 つだけで止める。(b) の 3 つの条件は (b) にだけかかり、(a) にはかからない。
     - (a) 実行器が結末を返さない（`cases` が `None`）。
     - (b) 次の 3 つが全部成り立つ: 走らせた回が 0 件・元の結末（試験を選ぶ側と同じ `board.accept_base`。裁定の後の置き場は組の子から写した `bases/<k>/base.json`）の実行器が AI の書いた物（`suite_by_factory`。人が渡した実行器は偽）・「`no_tests` が真」か「試験が在るかが決まらない」のどちらか（後者は一覧の控え `test_list` の `status` が `absent` か `failed`。22.3）。

     0 件の yes/no は、型が試験を足したかを見ず、走らせた回の件数だけを見る（書き手の返す証拠が要る「型が足した試験が結末に居るか」は段 1 の PR B で各型の義務に足す）。一覧が 1 件以上を示した対象は当たらない。当たると `{ok: false, stop: true}` を返し、`tdd-start.json` に `no_suite` と訳を書き（`board.mark_no_suite`）、`fix-accept`・`fix-ruled-accept` は拒否に数えず輪を抜ける（`done: true`）。訳の 1 行は、走らせた回のログに加え、決まらない時は `test_list.why` と宣言の案内 `declared.LIST_HINT` を、下ごしらえ（型 `pin`）の返しが、起点の版（直す前の木）に在った設定のファイルを書き換えて受け付けに拒まれていた時はそのファイルのパス（`pin.KEPT_CONFIG` の行。受け付けの拒否の控えから引く）を載せる。
- 止めを運ぶ道: 組の結果の `tdd` に `no_suite: true` と `reason` が載り（`tdd.exit_fields`。輪が済まずに抜けた組でも `group_end.tdd_exit` が印を落とさない）、`finish.stop_of` が出口の `stop_reason` に `stopby.NO_SUITE` を名乗る（`suite_broken` が先）。裁定の後の段の受け付けが止めた時は、親の置き場の `tdd-start.json` の印を `finish` が読む（`board.no_suite_stop`）。メイングラフ line〔`works-factory-line`〕は、出口の `stop_reason` が空でない run を今の止めの道で止め、後ろの段へ進めない。
- 報告の句（メイングラフ line の `workflows/line/src/facts.py` の `suite_broken_notes`。`suite_broken` の句と同じ道で運び、試験の関門の `suite_note` と同じ冒頭に並ぶ）: 「修正の段が止めた（試験の実行器が無い・走らない。組 <group_id>）: <訳>」。
- 消えた物と残る物: `tdd.py` の `NO_SUITE` と、実行器が無い組を「今どおり直す」文は消えた。`PLAN_NO_TDD`（`routes: plan` で tdd の単位が無い組）は残り、字を「ほかの型の注文で直す」に直した。実行器が無い static だけの組の知らせ（`gates.NO_SUITE`・`common.NO_SUITE`）は字を直して残る。

### 19.2 壊れているのが対象のリポジトリの試験の時（ついでに直す）

- 組の頭の元の結末で落ちた（`failure`・`error`）試験のファイルのうち、修正案が触る所に直に関わる試験（`basecase._related_pick`。17 節の選びと同じ）に在る物を、置き場の `conflict.BROKEN_TESTS_FILE`（`{tests: [{path, ids}]}`）に書く（`basecase.broken_related`。組の頭が書く）。関わるかを選べない（`whole`）時は書かない（相談で許しを取る今の道）。
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
- `tests/blocks/fix/test_no_suite.py`: 止める 3 つの場所（組の頭・輪の途中の runner・受け付けの 0 件と一覧の決まらない時）と、static だけの組が止まらないこと、`fix-prep` が印で修正役を起こさないこと、組の出口が印を落とさないこと。下ごしらえの設定のファイルの例外（19.5）。
- `tests/blocks/fix/test_prompts.py`: 修正役の指示の「直す前から壊れていた関わる試験」の行（表 `RENDERED` に `suite-fix`）。
- `tests/blocks/line/test_gates.py`（「ついでに直した試験」の節と開ける理由）・`tests/blocks/line/test_head_plain.py`（報告の冒頭の止めの行）・`tests/blocks/line/test_fix_in.py`（`suite_made`）。`tests/blocks/line/fix_in_before_spec.json` は `fix-in` に欄 `suite_made` を足したので取り直した（値は全部 `false`）。

### 19.5 対象に試験が無い時の印 `no_tests` と、下ごしらえの設定のファイルの例外（段 1 の PR A。持ち主の答え 9.1 の 12〜14）

- `no_tests` の決め方は 22.3（`base.json` の `no_tests`・`test_list`）。持ち主の答え 9.1 の 12（案 C）は持ち主の言葉で、試験を走らせずに対象の宣言の一覧 `list` で数える。
- 窓口の決め 13（持ち主の言葉ではなく、窓口が持ち主の前の決めから決めた物。**持ち主が覆せる**。覆したら、その答えを持ち主の決めとして `docs/owner-decisions.md` へ写す）: `no_tests` が真の対象で、下ごしらえ（`pin`）が書ける設定のファイルは、修正前の版（起点の木）に無いファイルを新しく作る物だけにする。下ごしらえの義務の 1（`pin.tests_only`）が、`rules.kind_of` が `config` のパスを、`no_tests` が真で、かつそのパスが起点の木に無い（`absent_at_base`）時だけ通す。起点の木に在る設定のファイル（`.review-checks.json` を含む）の書き換えと消しは拒む（`pin.KEPT_CONFIG`）。同じ run の前の型が作った設定のファイルは、起点の木に無いので通す。
  - 訳: 起点の木に在る設定のファイルの書き換えを許す案は、`.review-checks.json` の書き換えで最後の試験まで変わるのを機械が拒まない（守りを弱める）。書き換えを人の目だけに任せる案は機械の検査にならない。新しく作る物だけを許せば、機械が yes/no を 1 つ足すだけで済み、止まる場面も狭い。止まれば訳（拒んだパス）を 19.1 の止め方の 3 の訳に載せて報告に出すので、持ち主が選んだ「決まらない時は例外を開かない」（fail closed）と同じ向き。拠った物は 9.1 の 12 の 4 と、keep-essence の 3（弱める向きを作らない）。
- 窓口の決め 14（同じく持ち主が覆せる）: 対象の宣言が無い対象では、試験が無いと決まらないままにする。試験の一覧のコマンドは対象の宣言（`.review-checks.json` の `list`）からだけ取り、工場の AI が書く実行器には一覧の口を持たせない。決まらない時は例外を開かず（`no_tests` は偽）、受け付けで走らせた回が 0 件なら 19.1 の止め方の 3 で止める。
  - 訳: 実行器に一覧の口を持たせる案は、確かめられない AI の 0 件で例外が開く（守りを弱める）。宣言からだけ取る形は、9.1 の 12 の 3 の字のまま。拠った物は 13 と同じ。
  - 宣言を読む木: 窓口の決め 13・14 は、run の中で型が書いた宣言にも当たる。`list` と、その前に走る `setup` の argv は、どちらも起点の木（`base.json` の `rev`）の宣言から読み、写した木に足した・書き換えた `list`・`setup` は読まない（起点の木に `list` が無ければ、写した木に在っても決まらない。`test_list.status` が `absent`）。走らせる所は写した木。組の順で決めが変わらないため。

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

## 22 直し方の型の段 1（PR A）の形（2026-10-25。下書き [2026-10-24-fix-weapons.md](../plans/2026-10-24-fix-weapons.md)・実装の控え [2026-10-25-fix-weapons-stage1-a.md](../plans/2026-10-25-fix-weapons-stage1-a.md)）

- 語: 「段」は 2 通りに使う。工程の段（段 1・段 2・PR A/B）と、TDD の輪の中の段（`route`・`test`・`fix`・`refactor`）。「箱」は型の区分で、change（tdd・variant・remove）・keep（tidy・rebuild・pin）・outside（static）。「回 n」は修正の block を line が入れた回で、1 回目 n=1、案の直しの後の 2 回目 n=2。「読み手」は組の結果を読む node（`group-end`・`finish`・line）。
- 何を: 組の子を「元の結末を取る → 振り分ける → 型ごとの注文を書く → 型の輪を回す → 共通の受け付けで型の義務を照らす」の順に口をそろえた。型の中身は `src/` の型のモジュール（`tdd`・`variant`・`remove`・`static`・`tidy`・`pin`・`rebuild`）に分け、型を問わない部品は `src/route.py`・`src/orders.py`・`src/basecase.py`・`src/duties.py` に置く。型のモジュールどうしは import しない（`duties.py` の表だけが引く。持ち主の答え 9.1 の 3）。
- 語の注意: 22 節と 19.5 の「9.1 の N」は、下書きの 9.1（持ち主の答え）の番。持ち主の言葉つきの答えは `docs/owner-decisions.md` に写してある（`no-run-way-ask`〔8〕・`route-new-words`〔10〕・`group-head-base`〔11〕・`no-tests-by-list`〔12〕）。13・14 は窓口の決めで、持ち主の言葉ではないので写さず、19.5 に決めと訳を書いた。
- 境目（実装の部署の決め。持ち主が覆せる。控えの 1 節）: 書き手は今の修正役 1 つのまま。型ごとの書き手の指示は PR B。書き手が返す証拠（`evidence.named`・`kinds`・`sites` の `at`・`fixed_by`・`test`・`na`）が要る照らしは、関数と試験だけ置いて受け付けに効かせない（指示なしに求めると拒否が続いて単位が諦めに倒れる）。今の照らし（凍ったファイル・試験の変更の許し・試験の無い時の止め方）は外さず、新しい口の分を足して、厳しい側（両方を通る物だけ）で読む。
- 形（`workflows/.shared/schemas/weapon-order.schema.json`・`workflows/fix/schemas/weapon-return.schema.json`）: 注文は `{weapon, group, stage, since, base, units, scope, permits[, why_untested]}`。段 2 でこの形がそのまま型の block の port になる。

### 22.1 振り分け（`src/route.py`・`route-go`・`route-loop`）

- 計画の語（承認済みの案の項目の欄 `route`）は `tdd`・`direct`・`static`・`tidy`・`pin` の 5 つ（`planmarks.ROUTES`）。単位が複数の項目に在れば、`tdd` > `direct` > `pin` > `tidy` > `static` の順で 1 つ（`route.plan_words`）。`tdd` 以外の語を選んだ項目は、選んだ訳を `route_why` に書く（`route.plan_whys`）。消す名（`units[].removes`）は項目の `files` の `change=remove` の symbol・`op=delete` の path・`op=rename` の元のパスから機械が引く（`route.plan_removes`）。
- 型を引く表（`route.weapon_of(p, a, removes)`。p は計画の語、a は振り分けの AI の答え `tdd`・`direct`・無し）。上から順に最初に当たる行:
  1. p が `static`・`tidy`・`pin` → その語の型（`pin` は下ごしらえを単独で）。この単位は振り分けの AI に渡さない。
  2. 単位に消す名が在る → `remove`。この単位も AI に渡さない。
  3. p が `tdd` → `tdd`。
  4. a が `tdd` → `tdd`。
  5. 残り（p が `direct`・計画に行が無い。a が `direct` か無し）→ `variant`。
- 語は計画が書き、機械は表を引くだけで語を推し量らない。AI に新しい語は選ばせない。`variant`・`static`・`tidy`・下ごしらえの注文の訳の 1 行は計画の `route_why`、AI が `tdd` でない方に振った単位は AI の訳（10 字以上）を写す。計画の無い run（block を単独で回す）は 1・2 の行に届かず、`tdd` か `variant` になる。
- 振る単位の集まり（`route.route_keys`）: 組の単位から、計画の語が `static`・`tidy`・`pin` の単位と消す名の在る単位を除いた物。`direct` の語の単位は AI が振る。ただし承認済みの案が tdd に縛る単位（計画の語が `tdd`）を AI が direct に振った時は `common._plan_tdd` が拒む。
- `route-go`（`scripts/route_go.py`。返り `{route, stop}`）: 次の 3 つを上から見る。(1) `tdd-start.json` が `suite_broken` か `no_suite` → `{route: false, stop: true}`。(2) `routes` が `plan`・`base.json` が取れていない（`taken` が偽。static だけの組）・輪の状態がもう在る（resume）→ 新しく置かず、`route` は、その輪の状態の段が `route` のままなら真、でなければ偽。(3) `routes` が `auto`・`taken`・振る単位が在る → `tdd.open_state` で輪の状態を段 `route` で置いて `{route: true}`。AI は tdd と variant の間でしか振らないので、実行器が無い組は AI の答えを待たずに 19.1 の止め方の 1 が決める。
- `route-loop`: `route-prep` → `route`（AI。指示は変えず、`prompts/route.md` は `{part:tdd}` の 1 行で、段 `route` の値は `src/prompts.tdd` が組む）→ `route-step`（`route.step`）。振り分けの段の状態は別のファイルにせず、後の TDD の輪と同じ輪の状態のファイル `tdd-<k>/state.json` に段 `route` で置く（輪の回数の上限と申し出の数えを今と同じに続けるため）。`route-step` が段を `routed` にし、`orders` が tdd の単位の並びを置いて段を `test` にする。
  - 諦めは拒否の数え（`rolekit` の 3 回）で決め、申し出を積んだ周は数えない。Archon の `max_iterations`（40）はその数えより大きい柵。`route` の出し直しは同じ会話を継ぐ。3 回目で振る単位を全部「AI の答え無し」にして済み、表の 5 で `variant` に引かれる（`route._abort`）。
  - 振り分けの段で作業ツリーを変えたら拒む（実行器が作ったファイル `suite_made` を除く）。振り分けは何も書かないので、諦めた時に戻す木も無い。
  - 止めた申し出は `route-step` が `flush_unsent` で盤面へ流す（`tdd-step` と同じ口）。

### 22.2 注文と、TDD の輪の後に起きる修正役（`src/orders.py`・`orders`）

- `orders.compute(place, repo)`（返り `{tdd, writer, stop, reason}`）。`tdd-start.json` が `suite_broken` か `no_suite` なら `{tdd: false, writer: false, stop: true}`。止めないなら、組の単位（義務の外の止めた単位を除く）に `weapon_of` で型を引く。振り分けの AI が諦めた単位（輪の状態の `gave_up`）は、`weapon_of` の引数 `a`（振り分けの AI の答え）を無し `""` として引く（計画の語と消す名だけで型が決まり、どれにも当たらなければ `variant`）。元の結末が取れていない組（static だけの組。ほかは組の頭が止める）は `tdd` を `variant` に替える。
- tdd に引いた単位があるか、輪の状態がもう在れば、輪の状態に並べて（`tdd.assign`。tdd に引いた単位は tdd の行、ほかは direct の行）段を `test` にする。tdd の単位が無ければ、輪は済んだことにして要約を書く（`tdd.assign` → `_finish`）。この時 tdd の輪は `when:` で飛ばされ、輪の状態が無い組の読み手は今もこの形を受ける。
- 型ごとの注文を `orders/<weapon>.json` に書く（単位の無い型の注文は消す）。索引 `orders.json` は `{sequence, weapons, stage, since, agreed, unsatisfied}`（裁定の後の段は `pass` も）。`agreed` は段の頭に在った範囲の相談の合意の見分けの字 `<group_id>:<id>`。`sequence` は下ごしらえ → tidy → static → tdd → variant → remove の箱の順。`stage` は段の番（`orders.stage_of`）。n は line がこの修正の block を何度目に入れたか（1 回目に入れた時は n=1、2 回目に入れた時は n=2。置き場に前の段の申し送り `prior/` が在るかで決める）で、その回の 1 回目の段の番は 2n−1、裁定の後の段の番は 2n（n=1 なら 1 と 2、n=2 なら 3 と 4）。`since` は注文を書いた時の作業ツリーの木。`units[].tests` は計画の項目の受け入れの試験 `tests` と書き換えの試験 `rewrite_tests` の id を機械が引く。`scope` は項目の `allowed_paths`・`out_of_scope`。
- 返りの `tdd` は「輪の状態が在って済んでいない」。`writer` は止めの無い組でいつも真。YAML の `when:` へ運ぶのは真偽だけ（憲法の 1）。
- 修正役の輪（`fix-loop`）は tdd の輪の後に起きる（`depends_on: [group-start, orders, tdd-loop]`）。段 1 の PR A では書き手が修正役のまま 1 つなので、tdd 以外の全部の型（variant・remove・static・tidy・下ごしらえ）の注文をこの輪が受ける。修正役は今と同じく、tdd の輪が緑にした単位の行も `changes` に写す（輪が自分で `changes` を書く形は、tdd の役の指示の直しが要るので段 1 の PR B で）。指示の観点の文は PR A で移さず消さない（`prompts/parts/fixer.md` は今のまま）。
- 輪が諦めた単位（40 周に届いた・3 回目の拒否）は、`fix-prep` が `orders.regive` で同じ箱の `variant` の注文に書き直す（`orders/tdd.json` から外して `orders/variant.json` に足し、索引の `weapons` を替える。何度呼んでも同じ）。
- 守れない依存（`unsatisfied`）: 項目の間の依存 `depends_on` のうち、tdd の輪が先に回るために守れない対（tdd の単位が tdd でない単位を待つ）を `orders.json` に名で書く。PR A は型を 1 回ずつ回す順を「tdd の輪、次に修正役の輪」の 2 つにしか分けない（`orders._slot`）ので、箱の順と依存の辺での型の並べ替えは段 1 の PR B で。

### 22.3 元の結末（`src/basecase.py`・`base.json`）

- 取る場所は組の頭 `group-start`（木を写した後・振り分けと注文の前に 1 度。実行器の書き直しの後のやり直し `suitefix.retry` を除いて取り直さない）。以前は TDD の輪の頭（`tdd.start`）が取って輪の状態に書き、輪の無い組では受け付けが試験を走らせなかった。今はどの型の受け付けも `base.json` で元の結末を読む。
- 取るか: 実行器が在り、組に計画の語が `static` でない単位が 1 つ以上在る時。static だけの組は走らせず、実行器が在れば `taken: false`・`baseline: {}` で書く。実行器が無いか起こせない・結末が取れない時は `base.json` を書かない（読むと無い扱いで、`taken` が偽と同じに読む。組の頭の止め 19.1 の 1）。
- 取り方は今の輪の頭のまま変えない: 関わる試験が引ければそれだけ・引けなければ一式・関わる試験が 0 本なら走らせずに `[]`（17 節。持ち主の決め `related-tests-only`）。
- **持ち主の決め `base-runs-nothing` と合わせる**: 走らせるのは元の結末の取りの 1 回（工場の実行器が走らせる関わる試験）だけ。試験が無いかの決めのために対象の試験は走らせない。「対象の宣言の一覧 `list` のコマンドだけ」を 1 度走らせる（下の `no_tests`。対象の試験そのものは走らせない）。test-gate は判定の前で一覧を走らせない。
- 欄: 輪の状態のうち受け付けが元の結末として読む欄を同じ名と形で持つ（`work`・`exe`・`suite`・`baseline`・`baseline_exit`・`baseline_cases`・`suite_made`・`test_cmd`・`test_cmd_gate`・`test_cmd_note`・`reused`・`related`）。足した欄: `rev`（起点の版 = run の修正前の版）・`taken`（取ったか）・`no_tests`・`test_list`・`suite_by_factory`（実行器が工場の書いた物か。入力 `suite_made` の値。同じ名で別の物を指さないよう、輪の状態の `suite_made`〔作ったファイル名の並び〕とは名を分けた）。
- `no_tests`（対象に試験が無い印。`basecase._no_tests`）: 次の 3 つが全部の時だけ真。(1) 起点の木に試験らしい名のファイル（`impact.is_test_file`。宣言は組の項目の計画の欄の `tests`・`rewrite_tests` のパス）が 1 本も無い。(2) 対象の宣言 `.review-checks.json` の `list`（試験を走らせずに 1 行 1 試験で出すコマンド）を走らせて 0 件。(3) 元の結末も 0 件。(1) が偽なら一覧を走らせない（`test_list.status` は `skipped`）。
- `test_list`: `{status, argv, count, why, log}`。`status` は `skipped`・`listed`・`absent`（起点の木に宣言か `list` の鍵が無い）・`failed`（形の誤り・起こせない・0 でない終了）。`absent` と `failed` は「決まらない」で、`no_tests` は偽（fail closed）。宣言の `list` と、その前に走る `setup` の argv は起点の木（`rev`）の宣言から読み、走らせる所は写した木（`tree_run.run` の任意の引数 `setup`。`[]` は準備が無い）。宣言の鍵 `list` は `lib/graphloops/engine/declared.py` の任意の鍵（案内の字 `LIST_HINT`）。窓口の決めは 19.5。
- 運ぶ道: 組の結果の欄 `base`（`base.json` のパス。`group-end` が足す）。親は組の `base.json` と `accept.json` を `bases/<k>/` に写す（`exe` は親の作業ツリーの中のパスに引き直す）。2 回目の block の置き場と組の子へは `PRIOR_LOOP` 印つきで写す。印 `ADOPTED_FROM`・`PRIOR_LOOP` は `accept.json` の鍵に置く。親の受け付けが読む元の結末は、印つきを外した組の順で最後の物（`board.ruled_base`）。確かめ直しの `board.before_cases` は欄 `base` を読む（18 節）。
- 受け付けが書き戻す欄 `final_left`・`final_far`・`ci_left`・`suite_made` は `accept.json` に書く（組の子は組の置き場、裁定の後の受け付けは親の置き場、確かめ直しは `<name>/`。`suite_made` は前の回との和）。run の全体の `suite_made` の和は `basecase.suite_made_all`（`base.json`・`accept.json`・`bases/`・`returns/` の全部と、輪の状態の和）。
- 輪の状態の無い組（static だけの組など）の受け付けは、以前は試験を走らせなかった。今は `board.accept_base` が `base.json` で選んで走らせる（厳しい側）。

### 22.4 共通の受け付けと義務の表、許しの読み口（`src/duties.py`・`src/board.py` の `accept_reply`）

- 受け付けの順は 8.1。`accept_reply` は型で枝分かれせず、型の名から箱を引く表（`duties.BOXES`: tdd・variant・remove は change、tidy・rebuild・pin は keep、static は outside）と、箱の義務の表 `BOX_DUTIES`・型の義務の表（型のモジュールの `DUTIES`）を `duties.check` 1 か所で並べる。型の義務の関数は箱の義務の結果を受け取らない（例外を書く口が API に無い。憲法の 6）。型は注文の索引 `orders.json` の `weapons` で引き、裁定の後の注文の単位の行に `checked_as` が在ればその型で義務を引く（22.5）。
- 段 1 の PR A で受け付けに効く照らしと、PR B に回した照らし（控えの 3 節）:
  - 効く: tdd の型の義務（輪の中のまま）・F135（赤を見ない clean を拒む。variant・remove・pin の単位に当てる。`board.red_units`）・static の義務 1〜3（`why_untested`・`kinds_allowed`・`no_test_edits`）・keep の同じ結果の照らし（起点で通っていて返した木の同じ選びの回に居ない試験は、注文の `remove` の許しの中だけ。`duties.keep_same_result`。tidy と pin に効く）・pin の義務 1・2（`pin.tests_only`・`twice`）・remove の `removed_in_permits`・返しの控えの凍ったファイル（`duties.frozen_by_returns`）・受け付けの名指しの和。
  - 段 1 の PR B で: 変える段の箱の義務（名指しの試験が起点の木で赤・返した木で緑、か消す名が `gone`。`duties.change_named_or_gone`）・static の義務 4（`evidence.kinds`）・pin の義務 3（`sites` の `test`）・variant の `sites` の 2 つの照らし（`sites_shape`・`unit_red`）・単位ごとの F135・`na`。関数と試験は PR A に在り、表に足すのが PR B。
- 返しの控え（`duties.write_returns`。書くのは共通の受け付けが返答を通した時の 1 か所）: `returns/<k>.json` に `{stage, weapon, group, tree, units: [{key, named}], frozen, frozen_tree, suite_made, added, rewritten}` を型ごとに 1 件書く。`<k>` はその置き場で使われていない一番小さい番号で、番号は書いた順の印にすぎない。`frozen`・`frozen_tree`・`suite_made` は tdd の返しだけ輪の状態から写す。組の子は親へ、親は 2 回目の block へ、輪の状態と同じ 3 つの道で写す（22.3 の運ぶ道）。
- 許しの読み口（`orders.permits_for(place, items, stage, rulings)`）: 注文の `permits` を、`conflict.test_permits` の行（既存の読み口）をこの注文の項目で絞った物として書く。行は `{kind, duty, test, source}` で、`kind` は `rewrite`（計画の書き換えの試験。義務の行 `duty` が真）・`remove`（消す名の許し。義務でない）・`agreed`（範囲の相談の合意）・`ruled`（裁定の範囲）・`broken`（直す前から壊れていた関わる試験。19.2）・`replan`（案の直しの許し）の 6 つ。`rewrite`・`remove` の行は項目の番号で絞り、ほかの行は run の全体の許しなのでそのまま入れる。
  - 前の型の物を引く: 注文を書く役は、run の今までの返し（`returns/` の全部。前の段の物を含む）の `added`・`rewritten` の試験と、凍ったファイルを、どの行の許しからも引いてから `permits` を書く（`replan` の行だけは引かない）。前の型や前の段が義務を果たした試験を、後の型や後の段が動かし直せない。
  - 裁定の行 `ruled` の例外: 返しの `stage` が、その裁定の控えの `stage`（`ruling.seen_stage`。裁定が見た返しの段の番 = 1 回目の段の 2n−1）以下なら、その裁定の範囲では引かない（裁定が見て許したので）。裁定より後の段の返しは古い裁定の範囲でも引いたまま。どちらも機械が書き、型と裁定役には書かせない。欄の無い古い裁定は 0 と読み、どの返しも引く。
  - 凍ったファイルの照らし: 今の `facts.check_frozen`（輪の状態の凍結と `conflict.ruled_test_limits`）は外さず、`duties.frozen_by_returns` を並べる。後者は `returns/` の全部の `frozen` を、`orders.json` の `since` の木を基準に、注文の `permits` のうち範囲として読む行（`rewrite`・`agreed`・`ruled`・`broken` の `test`）と、段の頭の後に取れた範囲の相談の合意（`orders.later_agreed`。`agreed` に無い合意。注文は段の頭で 1 度しか書かないので、段の途中の合意は注文に入らない）だけを許して照らす。段の頭に在った合意は、前の返しの凍結に当たれば `permits` から引く（下書き 2.1）。どちらか厳しい側で、両方を通る物だけを通す。修正役の事前の確かめ `facts.precheck` も同じ 2 つを照らす。
  - 受け付けの名指しの出どころ: 輪の状態の今の名指しと、注文の `units[].tests`・`permits` の `rewrite` の行（`orders.named_tests`）の和。狭めない。返しの `evidence.named`・`added`・`rewritten` は段 1 の PR B で足す。
- 弱める向きを作らない（keep-essence の 3）: PR A で足した口は、今の照らしの外ではなく並びに置く。段を越える引き（前の段の返しを後の段が裁定なしに動かせない）は、今の「輪の物だけが段を越える」より厳しい側（variant・static・下ごしらえなど、どの型の返しも段を越えて引く）。後の段で直したい時は、範囲の相談か申し出（裁定）の道に乗る。

### 22.5 裁定の後の注文（`orders.write_ruled`）

- 注文を書くのは親の `fix-ruled-prep`（段の頭で 1 度。組の子の頭ではない）。直す義務の単位を、親の置き場の返しの控えの元の型から同じ箱の型に引く（`RULED_WEAPON`: tdd の単位は `variant`、ほかは元の型のまま。控えに無い単位は `variant`）。単位の行に照らしに使う元の型 `checked_as` を書く（控えに無い単位には書かない）。
- 段の番は 2n（`orders.stage_of` の ruled）。`since` は段の頭の木（`board.fixer_head(place, "ruled")`）。`permits` は裁定の範囲を入れて（`rulings=True`）、前の型の物を引く。元の結末は親の受け付けの選び（`board.ruled_base`）。索引は `pass: ruled` を持ち（`orders.is_ruled`）、受け付けが組の子の注文と見分ける。
- 受け付けは `checked_as` で義務を引く。tdd から来た単位には variant の `sites` の義務を当てず、tdd の型の義務（輪の中の赤の記録）も当てない。当てるのは今の裁定の後の受け付けと同じ 1 つ: 受け入れの試験が、赤の見方（試験のファイルの hash が輪の凍結と同じなら輪の赤の木、違えば base の木に写して）で赤・返した木で緑。裁定の後の段の F135 は返答の全部の行で見る（`board.red_units` が `None`）。
- 裁定の後の段が、実行器が結末を返さない・試験を拾わない時は、親の置き場の `tdd-start.json` に `no_suite` を書いて止める（19.1 の止め方の 3。`finish` が出口の `stop_reason` に読む）。
- 2 回目の block の組の子が段の番 3 を数えるための空の `prior/` は、`board.adopt_inputs` が親に `prior/` が在れば子にも置く。
- 裁定 `fix_plan_item` は直す裁定に入らず、案の直しを通った 2 回目の修正の段で新しい注文になる。申し出の種類 `red_at_base` とその裁定を `fix_plan_item`・`ask_human` に絞る yes/no は、種類を出す下ごしらえの書き手が PR A に居ないので段 1 の PR B で（`conflict.DIV_KINDS` に足すと共通の断片と TDD の役の指示の既存の文を書き換えることになる）。

### 22.6 段 1 の PR B に回した物（控えの 3 節・1 の 2）

- 型ごとの書き手の指示（variant・static・tidy・pin・remove）と、修正役の指示の仕分け・移し。tdd の輪が自分で `changes` を書く形。
- 書き手が返す証拠を使う照らし（22.4 の「PR B で」の列）と、返しの `evidence`・`sites` の新しい欄を入れる返答の形（`recount` の返答の形・筋書き `standalone.stubs.yaml`・`unitrows` の直し）。
- 下ごしらえの指示の md への 1 文（在る設定のファイルは書き換えない）。機械の照らし（`pin.tests_only` の設定のファイルの例外と、拒んだパスを no-suite の訳に載せる所）と、書き手の共通の断片 `runner-writer.md`（試験がまだ無い対象では 0 件の JUnit XML を書く実行器を書いてよい）・計画の役 `plan-writer.md`（試験が無い対象では置き場を対象の慣習から選び、走らせるのに要るファイルを `allowed_paths` に書く）への 1 文ずつは PR A で入った。
- 型を 1 回ずつ回す順と依存の辺での並べ替え（22.2）と、守れなかった依存を組の結果と報告へ出す所。後の型の注文の `since` を前の型の返しの `tree` にする所（PR A は全部の型の注文の `since` が、注文を書いた時の木 1 つ）。
- 申し出の種類 `red_at_base`（22.5）。

## 23 直し方の型の段 1（PR B）の形（2026-10-25。実装の控え [2026-10-25-fix-weapons-stage1-b.md](../plans/2026-10-25-fix-weapons-stage1-b.md)）

- 何を: 修正役（`fixer`・`fix-ruled`）を型ごとの書き手に分けた。1 回目の段は `tdd-close`（tdd の輪の閉じの書き手。輪が緑にした単位の `changes` の行と周の全体の欄を書く）・`pin`・`tidy`・`static`・`variant`・`remove`、裁定の後の段は `<型>-ruled`（tdd の単位は `variant` の注文になる。22.5）。
- 輪: 外の輪 `writers-loop`・`ruled-writers-loop`（`fresh_context: true`。`max_iterations` は型の数）の 1 周が型 1 つ。頭の script `writer-pick`・`ruled-writer-pick`（`scripts/writer_pick.py`・`src/writers.pick`）が、注文の在る型を `writers.SEQUENCE` の順（1 回目の段は tdd の輪の後に tdd・pin・tidy・static・variant・remove、裁定の後の段は pin・tidy・static・variant・remove）に 1 つ選び、置き場の `writer.json` に書き、その型の段の頭（段の頭の木・除くパスの姿・注文と索引の `since`）を控え直す。1 回目の段は先に tdd の輪が諦めた単位を `variant` の注文に書き直し（`orders.regive`）、組が no-suite で止まっていれば型を選ばない。裁定の後の段は直す裁定が在る時だけ、段の頭で 1 度、裁定の後の注文（`orders.write_ruled`）を書く。
- 内の輪 `fix-loop`・`fix-ruled-loop` は今の修正の輪のまま（`fresh_context: false`・`max_iterations` 12）。書き手の node は 1 本の鎖（どの層も node 1 つ）に並び、支度の返り `writer`（書き手の node の名）で `when:` が 1 つだけを起こす。内の輪の 1 周目はいつも新しい会話で、型の中の出し直しは同じ会話を継ぐ。型どうしは会話を分け合わない。相談の 3 node と受け付けは型を問わず 1 組で、書き手の返りを `reply_<型>` で受け、起きた 1 つを読む（`writers.reply_of`）。
- 型ごとの状態: 受け付けの直す義務はその型の注文の単位（`writers.owed`）。拒否の控えと回の数えは `fix-accept-<型>`・`fix-ruled-accept-<型>`、渡した証拠の控えは `<node>-delivered.json`。受けた返答（`fix-reply.json`・`fix-ruled-reply.json`）・単位の結末（`fix-units.json`）・閉鎖の表・数え直しの件数は、型ごとに受けた物を単位で重ねる（`board.merge_reply`・`merge_units`。後の型が前の型の行を消さない）。返しの控え `returns/` は受け付けた型の分だけを書く。範囲の相談の枠は段で 1 つのまま。注文の無い置き場（注文を書く段を通らない置き場）は `variant` の書き手が直す義務の全部を受ける（`writers.FALLBACK`）。
- 指示: 今の `parts/fixer.md` を `parts/writer-top.md`（頭の材料の節）と `parts/writer.md`（決まりの本体）に割り、型の頭（役の定義）を `parts/<型>.md` に置いた（段 2 の D1 で、`writer-top.md`・`writer.md` は `.shared/prompts/` へ、型の頭は型の block の `prompts/parts/head.md` へ移した。2 節）。node の md は `{part:<型>}` の 1 行（D1 で、型の block の `prompts/<型>.md` が `{shared:writer-top}`・`{part:head}`・`{shared:writer}` を並べる形に替わった）。型だけの文は本体の段落の印で、`src/prompts.writer_paragraphs` が型から引いた真偽で選ぶ（variant の下請けの節と相談の下請けの 1 文は variant、壊して赤の証明は variant と pin、赤を見ない clean の拒否は受け付けと同じ `board.RED_WEAPONS`、変える段の申し出 `not_red` と brief の決まり 4・5 は箱 change）。行き先の表は下書きの付録 A で、組んだ指示に行の文が在ることを `tests/blocks/fix/test_assets.py` が照らす。
- 返答の形: どの書き手も今の修正役の返答の形（`*fix_reply`）に、種類ごとの確かめの記録 `evidence.kinds`（`{kind, did}` の並び）を足した物。受け付けは `returns/` の `kinds` に写す。

## 24 書き手の型の block の共通の形と slots（段 2 の D1。2026-10-26。下書きの 11.3・11.4・11.10）

- 何を: 修正の block が `include:` する葉の block `workflows/weapon-<型>/` の、型どうしで共通の形。D1 は `weapon-tdd-close`・`weapon-pin`・`weapon-tidy`・`weapon-static`・`weapon-remove` の 5 つ、D2 は `weapon-variant`（`Agent` を持つ）の 1 つで、合わせて 6 つ。以下の `<w>` は型の名（`weapon-tdd-close` の `<w>` は `tdd-close`）。型ごとに違う物は型ごとの設計書（[weapon-tdd-close.md](weapon-tdd-close.md)・[weapon-pin.md](weapon-pin.md)・[weapon-tidy.md](weapon-tidy.md)・[weapon-static.md](weapon-static.md)・[weapon-variant.md](weapon-variant.md)・[weapon-remove.md](weapon-remove.md)）だけに書き、共通の物はこの節の 1 か所に置く。slots を組むのは修正の block（2 節）で、型の block の口の意味は slots の形と組にして読む。
- 根拠: 持ち主の決め `leaf-include`（憲法の 3 の外し。型の block は葉の block）。入口の node を script にする訳: 止めた Archon は、include で合成した block の入口の AI の node をいつも新しい会話で起こす（`dag-executor.ts` の `composedBlockEntry`）ので、入口が AI だと拒まれた後の出し直しが前の周の会話を継げない。葉に限る訳: include の深さは 3 段まで（止めた Archon の `include-expander.ts` の `INCLUDE_MAX_DEPTH`）で、line → fix → 型の block で 2 段を使う。
- 作る人・読む人: 型の block を作る実装の役。急ぎではない。持ち主に求めること: なし（置き場は憲法の 4・E3・E22 と Archon の定めで 1 つに決まる）。

### 24.1 フォルダの中身

- `works-factory-weapon-<w>.yaml`（graph の名もこれ。E9）
- `prompts/<w>.md`（AI の node の指示 1 本。`{shared:writer-top}`・`{part:head}` を含む枠・`{shared:writer}` を並べるだけで、6 つの block で同じ字）・`prompts/parts/head.md`（型ごとに違う頭の段落。役の定義）
- `scripts/writer_prep.py`・`scripts/writer_save.py`・`scripts/writer_out.py`（node の `script:` の名。Archon は pack の形の workflow の script をその workflow の `scripts/` からだけ探すので、block ごとに置く。中身は 6 つの block で 1 字も違わない十数行で、本体 `.shared/writerblock.py` を呼ぶだけ）
- `src/__init__.py`・`src/render.py`（型ごとに違う物の表。定数 3 つだけで関数を持たない。24.5）
- `fixtures/standalone.stubs.yaml`（単独の筋書き。必ず置く）
- `schemas/` は置かない（形は全部 `.shared/schemas/`）

### 24.2 inputs と ports

- `inputs:`: `order`（必須。`json(shared:weapon-order.schema.json)`）・`slots`（必須。`json(shared:writer-slots.schema.json)`）。作り手（修正の block）を名指さない（E4）。入力は本体が `INPUTS_ORDER`・`INPUTS_SLOTS` で読む（宣言した入力に読み手が在るかの照らしは、block の script が import する `.shared` 直下のモジュールの `INPUTS_<名>` も数える。24.7）。
- `returns: <w>-out`・`outcome_field: ok`（E5・形の検査 7.1 の 8）。`<w>-out` の `output_format` は `{ok: boolean, reason: 字, reply: pointer か null, report: [字]}`（6 つの YAML で同じ字）。`reply` は pointer（`type`・`run_id`・`path`。description に form `json(shared:writer-reply.schema.json)` を書く）で、`ok` が偽の時は `null`（`type: [object, 'null']`。eyes の `after` と同じ書き方）。
- 落ちた周の守り（下書きの第 19 版の 11.3）: 返す節 `<w>-out` は落ちない（落とし穴 K1。`trigger_rule: all_done` で、どの node の出力も結ばない）。書き手の AI の node か、返答を置く `<w>-save` が落ちた周は `ok: false` を値で返す。分ける前と同じ守りは 2 つの道で残る。
  - 型の block の `<w>-prep`・AI の node・`<w>-save` は内の輪の本体の node なので、どれかが落ちれば、その周の終わりに内の輪が落ちる（止めた Archon の `dag-executor.ts` の「A failed body node fails the group immediately」）。
  - 周の中で後ろの node（`consult-check`・`fix-accept`）が place に書く前に、受け取る側の `writers.reply_of` が `ok` を読み、偽なら include の id と返りの `reason` を名指して落ちる（2.8）。`<w>-out` の fallback で `ok: false` になった周は本体に落ちた node が無いので、止めるのはこの読みだけ。

### 24.3 node の並び（どの block も同じ。上から順に 1 つの層に 1 つ）

1. `<w>-prep`（`script: writer_prep`・`runtime: uv`・`mutates_checkout: false`）: 本体の `writerblock.prep`。返り `{prompt}`。
2. `<w>`（AI）: 起こし方は今の書き手の錨 `writer_launch` の字のまま（`model: '@wf-fix-writers'`・`settingSources: [user]`・`allowed_tools`・`sandbox`・`idle_timeout: 1728000000`・`retry`）。`allowed_tools` は表の `SPAWNS` が真の型だけ `Agent` を足す（下書きの 11.8 の決め〔案 B〕で、tdd の閉じの外の 5 つが真。D2 の段 1 は variant だけで、段 2 で広げた）。`prompt: "$<w>-prep.output.prompt"`。`output_format` は `writer-reply.schema.json` の中身を字のまま写す。`description` は型の名だけが違う決まった字（例 `'書き手の型の block static の書き手'`）。`model` の値そのもの（模型と effort）は `lib/launchgroups.py` の群の表 1 か所に在り（E7）、YAML が写すのは群の名だけ。
3. `<w>-save`（`script: writer_save`・`runtime: uv`・`mutates_checkout: false`・`depends_on: [<w>]`・`with: {reply: "$<w>.output"}`。`trigger_rule` は既定）: 本体の `writerblock.save`。返り `{saved: true}`。
4. `<w>-out`（`script: writer_out`・`runtime: uv`・`mutates_checkout: false`・`depends_on: [<w>-save]`・`trigger_rule: all_done`。`with:` を持たない）: 本体の `writerblock.out`。

### 24.4 共通の本体 `workflows/.shared/writerblock.py`

- 置き場の根拠: 憲法の 4（6 つの block が使うので 1 つの block の中には置けない）・E3（仕事のほとんどが Archon との出入り〔`INPUTS_`・place・`prompt.emit`・`ports.pointer`・`ports.returns`〕なので `lib/` には置けない。層の地図で lib は `workflows/` を import できない。E22）・`.shared/AGENTS.md` の「`.shared` と `lib/` の分け」（pointer・`INPUTS_`・place を解く所はここの口）・止めた Archon の定め（使い回すモジュールは `<pack>/.shared/` に置き、script が import する）。E10（新しい層・置き場）には当たらない（そこの決まりが許す小さなモジュールを 1 つ足す）。口の一覧は `workflows/.shared/AGENTS.md`、E2 の口の並びと `tests/layers/scan.py` の `PACK_PORTS` に書く。
- 型の名は渡さない: script は `writerblock.prep(render)`（`writer_save.py` は `writerblock.save()`、`writer_out.py` は `writerblock.out()`）だけで、型の名は呼んだ script の在る block のフォルダの名 `weapon-<w>`（`ports.caller_block()`）から引く。名を script の字で渡すと、block のフォルダ・グラフの名・node の id・md の名に続く 5 つ目の写しになり、script が block ごとに違う字になる。フォルダから引けば 6 つの script は 1 字も違わず、照らしは「同じ字か」の yes/no 1 つで済む（24.6 の (d)）。
- `prep(table) -> {prompt}`: `order`・`slots` を `ports.json` で読む。`order.weapon` が表の `ORDER_WEAPON` と違えば落ちる（型の名と block の食い違いを書けなくする yes/no）。`slots.values`・`slots.when` に型が持つ値と段落を足し（名が slots の名と重なれば落ちる）、`prompt.emit("<w>", values, when, prompt.round_of("<w>"))` で組む。型が持つ物: 値 `first_prompt`（この block の place の `<w>-prompt-1.md`。続きの周が読み直す 1 回目の指示）・`unattended`・`overlay_file`（借りた写しの固定を照らしてから組む。続きの周は空）・`summary_file`（`SUMMARY` が真の型だけ。slots の上の段の欄を写し、空なら `(empty)`）・`g1_items`（`SPAWNS` が真の型で下請けの単位が在る時だけ。24.9）と、段落 `spawns`・`g1`・`ask_variant`。
- `paragraphs(table) -> {spawns, g1, ask_variant}`: 表の `SPAWNS` から引く下請けの段落の真偽。place を読まない関数で、`prep` と試験（`tests/workflows/test_weapon_assets.py`・`test_writer_prompts_kept.py`）が同じ関数を読む。`prep` は `g1` を下請けの項目が 0 件の周で偽に下ろし、`ask_variant` を slots の `ask` が偽の周で偽に下ろす。
- `save() -> {saved}`: 入力 `reply`（AI の node の出力）を `ports.json` で形 `shared:writer-reply.schema.json` に照らし、place の `reply-<n>.json` に書く。形に合わなければ落ちる。`<n> = prompt.round_of("<w>") - 1`（`<w>-save`・`<w>-out` の時点では同じ周の `<w>-prep` が `<w>-prompt-<n>.md` を書いた後なので、`round_of` は n+1 を返す。指示と返答が同じ番号で対になる）。本体は `reply-` のファイルを数えない（数えると、AI が落ちて `<w>-save` が走らなかった周の後で番号が指示とずれる）。
- `out() -> {ok, reason, reply, report}`: 入力を持たず、`ports.run` の形で落ちない。同じ `<n>` で、place に `<w>-prompt-<n>.md` が無いか `out-<n>.json` が在れば prep が落ちた周（前の周の返答を返し直さない）、`reply-<n>.json` が無ければ書き手か `<w>-save` が落ちた周で、どちらも `ok: false`・`reply: null`・`report` に `reason` の 1 行。ほかは `ok: true` と `reply-<n>.json` の pointer。返りは、prep が落ちた周と fallback の時を除いて `out-<n>.json` にも書く（prep が落ちた周の見分けに使う。prep が落ちた周の `<n>` は前の周の番号なので、書くと前の周の控えを `ok: false` で上書きして消す）。
- 表 `table`（block の `src/render.py`）は定数 `ORDER_WEAPON`・`SPAWNS`・`SUMMARY` を 3 つとも持つ。既定の値は本体に持たず、欠ければ落ちる。

### 24.5 型ごとに違う物

- `src/render.py` の 3 つの定数: `ORDER_WEAPON`（注文の `weapon` の語。`weapon-tdd-close` は `"tdd"`、ほかは `<w>` と同じ語）・`SPAWNS`（下請けを起こすか。真の型だけ AI の node に `Agent` を足す。下書きの 11.8 の決め〔案 B〕で、tdd の閉じの外の 5 つが真。D2 の段 1 は variant だけで、段 2 で広げた）・`SUMMARY`（TDD の輪の要約を受けるか。真は `weapon-tdd-close` だけ）。
- `prompts/parts/head.md`: 型ごとに違う頭の段落（役の定義）。出どころは D1 の基の main の `workflows/fix/prompts/parts/<型>.md` の、見出し `# Fixing (the writer's job)` と `<!-- end rules -->` の間の字（字は変えない）。型ごとの頭の文は `tests/workflows/test_weapon_assets.py` が、この main の commit の字に在ることと、型の書き手の組み上がった指示に在ることを照らす。下請けに型の決まりを渡す時（下書きの 11.8 の決め。案 B）も同じ `head.md` を組んで渡す（D2）。
- 義務の表から引く 4 つの段落（`rules_change`・`rules_sites`・`rules_red`・`conflict_change`）は型が持たない。修正の block が `writer_slots` で引く（2.3）。受け付けの義務も修正の block の `duties.py` と型のモジュール `src/<型>.py` の `DUTIES` に在り、型の block は義務の表を知らない（22.4）。
- 筋書き `fixtures/standalone.stubs.yaml`: `fixture.inputs` に `order`・`slots` を JSON の字で置き（形の検査 7.1 の 4。pointer を持たない）、`exec-code: true`、`<w>` の返答を stub に書き、`reached: [<w>-prep, <w>, <w>-save, <w>-out]`、`resolved-text-contains` に頭の段落の 1 文。値は型ごとに違ってよい。単独の run は `bin/works-factory workflow run works-factory-weapon-<w> --cwd <対象> --input order=<ファイル> --input slots=<ファイル>`（憲法の 5）。
- 修正の block の筋書きでは、include の中の node の stub を `<include の id>__<id>`（例 `w-static__static`）に替え、include の中の script（`<w>-prep`・`<w>-save`・`<w>-out`）も stub にする（筋書きは include の入力を名前の script に渡さない。[archon.md](archon.md) の U3）。

### 24.6 写しの照らし（Archon が 1 か所から読ませない物。名の表を持たない yes/no）

写す物: 書き手の AI の node の起こし方（錨 `writer_launch` の中身）と `output_format`（`writer-reply` の中身）が型の block の数だけの YAML に写る。写しを無くす道は Archon にも決まりの中にも無い（YAML の錨はファイルをまたがない・`output_format` はファイルを名指せない・workflow の頭の既定値は 1 本の中でだけ効いて AI の node が 1 つなので写しの数が減らない・AI の node だけの block を include する形は入口が AI になり深さも尽きる・埋めと生成は E1 が禁じ、型を 1 つの block にまとめるのは承認済みの形に反する）。照らしは `tests/workflows/test_weapon_blocks.py`（書き手の型の block は「`script: writer_prep` の node を持つ workflow」で見分け、名の表を持たない）:

- (a) AI の node の `output_format` が `.shared/schemas/writer-reply.schema.json` と等しい（D1 の間は fix に残る variant の node も照らしていた。D2 で variant が block になり (b) に入ったので、この足しは消した）。
- (b) YAML の全体が、型の名を置き字に替え、`allowed_tools` から `Agent` を除くと、どれも同じ（起こし方の鍵・`inputs:`・node の並び・`returns:` まで）。`prompts/<w>.md` も同じ形で照らす。
- (c) `Agent` を持つ block の組と、表の `SPAWNS` が真の block の組が同じ。
- (d) `scripts/writer_prep.py`・`writer_save.py`・`writer_out.py` が、どの block でも 1 字も違わない。
- 修正の block の 2 つの鎖の include の先が全部 `weapon-` の block で、`writers.SEQUENCE` の型ごとに鎖に 1 つずつ在る（鎖に無い block・block の無い型を書けない）。D1 の間の variant の除きは D2 で消した。

### 24.7 D1 で入った外れ（設計の字と違う所・決まりの字を直した所）

- 形の照らし `lib/graphloops/engine/schema.py` に `allOf`・`if`・`then`・`not` を足した（`KNOWN_KEYWORDS` にも）。返答の形 `writer-reply.schema.json` の `precedent` が条件つきの必須（`from_judge_row` が真でなければ `problem` が要る、など）を持ち、口 `ports.shape_errors` が知らない語を拒むため。意味は JSON Schema 2020-12 のまま（`allOf` は全部の誤りの和、`if` が通る時だけ `then`、`else` は持たない、`not` は部分が通れば誤り）。
- 入力の読み手の照らし `tests/layers/scan.py` の `_inputs_read` は、block の `scripts/`・`src/` が import する `.shared` 直下のモジュールの `INPUTS_<名>` の字も、入力の読み手に数える。本体 `writerblock` が `INPUTS_ORDER`・`INPUTS_SLOTS` を読む（block の `scripts/` の字には現れない）ので、数えないと宣言した入力に読み手が無いと誤って赤になる。数えるのは `INPUTS_<名>` の字そのものだけ（`INPUTS_{` を組む汎用の句は数えない。`ports.py` などの汎用の字で、読み手が在ると誤って数えるため）。
- `writerblock.prep` は、続きの周（`resume`・`overflow_answer`・`queued`）で `unattended`・`overlay_file`・`summary_file`（`SUMMARY` が真の型だけ）を空にし、`ask_variant` は slots の `ask` が偽なら偽にする。今の `writer_values` と同じ字にするため（組み上がる指示を割る前と変えない）。
- slots の `subagents` は D1 では `required` の無い object で、空の `{}` を通した。D2 で 9 欄を全部 `required` にし、下請けを起こさない時は空の値で置く形に直した（2.3）。
- 本体の置き場は `.shared/`。決まりの字として E2 の口の並び・E4 の place のファイルの名の句（`.shared/` の口が書く物〔`prompt.emit` の `<node>-prompt-<n>.md`・`writerblock` の `reply-<n>.json`・`out-<n>.json`〕を除く）・`tests/layers/scan.py` の `PACK_PORTS`・`.shared/AGENTS.md` の口の一覧を直した。

### 24.8 試験

- 本体の試験 `tests/blocks/shared/test_writerblock.py`（型の名の食い違い・足す名の重なり・表の定数の欠けで落ちること、`save` が形に合う返答を置き欠けた返答で落ちること、`out` が場合ごとに落ちずに返すこと）。
- 型ごとの薄い試験 `tests/blocks/weapon_<w>/test_<w>.py`: `tests/blocks/kit.py` の `WriterBlockCase` に block の名を渡して継ぐだけ（筋書きで指示が組め、頭の段落の 1 文が在ること、下請けの段落が表の `SPAWNS` に従うこと〔偽の型は偽、真の型は `spawns` が真・`g1` が `subagents.owed` の有無・`ask_variant` が `ask` に従い、下請けのファイル 2 つが place に書かれる〕、真の型の `head.md` が空の値で組めて `g1-impl-<n>.md` に渡ること、`save` と `out` の返答の pointer と返答の無い周の `ok: false`）。形の検査 7.1 の 10 が block ごとの試験のフォルダを求めるので、フォルダは残す。
- 写しの照らし `tests/workflows/test_weapon_blocks.py`（24.6）・組み上がる指示の控え `tests/workflows/test_writer_prompts_kept.py`・付録 A の行き先ごとの数と頭の文 `tests/workflows/test_weapon_assets.py`。細目は各試験の docstring に置き、この設計書に写さない（持ち主の決め `rules-tests-design-apart`）。

### 24.9 下請け（書き手が項目ごとに起こす実装役と審査役。D2 の段 1・段 2。下書きの 11.4 の 5・11.6 の D2・11.8 の決め案 B）

- 何を: 下請けの部品（値の関数・指示の md・ファイルを書く所）を、2 つ以上の block が使える置き場へ移した。組み上がる書き手の指示と下請けのファイルの字は移す前と変わらない（brief の無い run と在る run の `g1-impl-<n>.md`・`g1-review-<n>.md`・`seat-briefs.md` と修正役の指示を、移す前の main と字で比べて一致を確かめた。`tests/workflows/test_writer_prompts_kept.py` の控えも替えずに緑）。下請けを起こす型は段 1 では variant だけ（表の `SPAWNS` が真）。
- 段 2（下書きの 11.8 の決め〔案 B〕）: tdd の閉じの外の 5 つ（variant・remove・pin・tidy・static）に付けた。pin・tidy・static・remove の表の `SPAWNS` を真にして `allowed_tools` に `Agent` を足した（写しの照らし `tests/workflows/test_weapon_blocks.py` の (b)(c) が組を縛る）。`g1-impl.md` の works rules の節に、1 行に `{weapon_rule}` だけを置いた段落を足し（足すだけ。今の文は減らさない）、本体 `subagent_items` が、その block の `prompts/parts/head.md` を `prompt.render_part("head", {})`（値は空）で組んで渡す。型の決まり（pin は設定のファイルを書き換えない・コードを変えない、tidy は振る舞いを変えない、static は試験を足さない、remove は消えたことだけを確かめる試験を書かない）が、下請けの実装役の手順書の「Write tests」とぶつかるので、下請けにも字のまま守らせる。文を 2 か所に写さない。`head.md` に `{名}` が在れば `prompt.render` が値の欠けで落ちる（黙って空にしない）。表の `SPAWNS` が偽の tdd の閉じは `g1-impl` を組まないので、`{summary_file}` を持つ `head.md` は組まない。縛る試験: `tests/blocks/kit.py` の `WriterBlockCase`（表の `SPAWNS` が真の block で、`head.md` が空の値で組めて `g1-impl-<n>.md` に在る）と `tests/blocks/shared/test_writerblock.py`。付録 A の行のうち文が下請けの段落（`spawns`・`g1`・`ask_variant`）の中に在る行（Q10・F39・F101〜F106・F116・F148a）は、`tests/workflows/test_weapon_assets.py` が段落を全部真・全部偽にして組んだ字の差から機械で引き（番号の表を持たない）、表の `SPAWNS` が真の書き手の全部に在り、偽の書き手に無いことを照らす（前は `SPAWN_ONLY = {Q10}` の手の表）。付録 A の文・行き先・数は変えない。`test_writer_prompts_kept` の控えは、この狙った変化（pin・tidy・static・remove の 16 組で下請けの段落・`g1_items`・付録 A の増えた行だけ。variant と tdd の組は 1 字も変わらない）で 1 度だけ書き直した。
- 値の関数 `lib/subagents.py`（Archon を知らない。E3）: `items`（項目ごとの番号・brief のファイル・題。案に載らない義務の単位は凍結した項目の最大の次から振る）・`entries`（項目ごとのファイルの名と、借りた implementer・task-review の型の穴を埋めた字。審査役の型の `<base>..<head>` は `<base>` に直す）・`row`（修正役の指示の項目の 1 行）・`diff_cmd`（審査役に渡す差分のファイルを書くコマンド）・定数 `G1_IMPL`・`G1_REVIEW`・`G1_PATCH_FILE`・`G1_PATCH`・`SEAT_BRIEFS`。md を組んだ字（場面・報告の指示・`g1-rest` の題など）と place のパスは引数で受け、指示の文は持たない（憲法の 2。E13）。`unit_note`・`NOT_NOW`・`NONE` は brief の行（修正の block の `rules.brief_rows`）と下請けの題の 2 つが使うので `lib/planbrief.py` に出した（`planbrief` はもう `NOT_NOW`・`NONE` を持ち、`rules` が重ねて持っていた）。
- 指示の md `.shared/prompts/`: `g1-impl.md`・`g1-review.md`・`g1-impl-report.md`・`g1-report.md`・`g1-head-sha.md`・`g1-scene.md`・`g1-rest.md`・`seat-briefs.md`（修正の block の `prompts/parts/` から `git mv`。字は変えない）。組む口は `prompt.render_shared(name, values, when=None)`（`render_part` と同じ決まりで `.shared/prompts/<名>.md` を組む。`.shared` の断片は `{part:` を持たない）。
- ファイルを place に書いて md を組む所: 本体 `writerblock.prep`。表の `SPAWNS` が真の型で、続きの周でなく、slots の `subagents.owed` が空でない時、借りた写しの固定の照合（`seat.pinned`）を先に呼び、`subagent_items` が項目ごとに `g1-impl-<n>.md`・`g1-review-<n>.md` を、`subagents.seat_brief_rows` が空でなければ `seat-briefs.md` も、型の block の place に書いて、修正役の指示の `{g1_items}` の行と段落 `g1` を組む。続きの周は組まない。`seat-briefs.md` は直す義務の単位の brief を名指す行を置くだけで、実装役の型の `[BRIEF_FILE]` は項目ごとにその項目の brief のファイルを指す（移す前からそうで、変えていない）。
- slots の `subagents`（2.3）: 修正の block の `writer_slots` が `prompts.subagents_slot` で組む。`rules.dispatched`（TDD の輪が緑にした単位を除く）・`planbrief.for_units`・`rules.brief_rows`・`board.base_rev`・`prompts._check_cmd` は修正の block に残る。
- 試験: 値の関数は `lib/tests/test_subagents.py`（項目の番号・題・型の穴・`<base>..<head>` の直し・差分のコマンド）、ファイルを書く本体は `tests/blocks/shared/test_writerblock.py` の `SubagentCase`（項目ごとに 2 つのファイル・brief の無い run の残りの単位の項目・brief の在る run の `seat-briefs.md` の頭の見出しと brief の行・相談の節・照合が書き込みより先・続きの周と `SPAWNS` 偽は組まない）、修正の block が渡す材料は `tests/blocks/fix/test_prompts.py`（`subagents_slot`）。

### 24.10 D2 の段 1 で入った外れ（設計の字と違う所・設計が決めていなかった所）

- 注文を書く段を通らない置き場（`writers.current` が FALLBACK の variant を返す置き場。試験の置き場が使う）では、型の block が必ず受ける注文が無い。`hand_over` はその時だけ `fallback-order-<段>.json` に直す義務の全部を受ける注文を書いて指す（2.2）。
- 筋書きの標準 3 本（`workflows/fix/fixtures/`）は、dry-run が置き場にファイルを書けず返りの pointer の先を読めないので、返りを読む受け付けの 3 つの script も差し替えた。標準の筋書きの `resolved-text-contains`（variant）は外し、consult の筋書きが照らしていた答えの役の指示は表 `RENDERED`（`consult-answer`）と `tests/blocks/fix/test_prompts.py` の `test_consult_answer` に移した。
- `test_writer_prompts_kept` は段 1 では控えを替えない（段 2 で 1 度だけ書き直した。24.9 の段 2）。ただし `compose` の variant の枝を型の block の道に替え、指示を組んだ place が型の block の place になるので、下請けのファイルの名指しの place を `{PLACE}` に揃える置き字を足した。'resumed' の場面が受け付けへ渡す variant の返答は、block の返りの字に包む（`kit.Run.environ`）。
- `slots` の `subagents` を、型を問わず同じ組み方で渡した（設計は「下請けを起こさない型の注文の時も空の並びで置く」。下請けを起こすかは型の block の表が決めるので、修正の block に型の表を持たせない）。
