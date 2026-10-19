# block の設計書: verify（判定の裏取り）

- 何の話か: 根本の診断の役が依頼を切った「直す単位」を、別の目で確かめる観点「判定の裏取り」を、単独で呼べる block `blocks/verify/` にする設計。型は [README.md](README.md) に従い、手本は [world.md](world.md)。
- 決めたこと: 今の judge の 3 つの node（`verify-prep`・`judge-verify`・`verify-merge`）を、同じ 3 つの node（`prep`・`judge-verify`・`finish`）の block にする。AI の node は束ね役 1 つで、束ね役が Agent の道具で単位ごとの下請けと相乗りの下請けを並べて起こす形は今のまま。入力は判定と言語の 2 つの port だけで、run の記録を読まない。束ね役と下請けの指示は 1 本の英語の md（`prompts/judge-verify.md`）にまとめ、prep が段落を選んで束ね役の指示と下請けのファイルを組む。README の 8.1 の入力 `materials` は持たない（6 節の 1）。回すか（機能の切り替え・頭の深さ・止めの控え）は line の `when:` が決める。
- 持ち主（このリポジトリの owner。決めを下す人。README の頭の語）に求めること: なし。README と食い違う所は 6 節に、決まらない物は 8 節に置いた。本文の「持ち主の決め」はどれもこの人の決め。

この文書の語は README の頭の物を使う（block・graph・port・place・prep・accept・pointer・Archon の YAML の鍵・form の書き方）。ほかに:

- 単位: 根本の診断の役（diagnose）が依頼を切った根本の 1 件（判定の `units` の 1 行）。開いた単位は、直す義務の残る単位（`label` が `block`、か `label` が `suggest` で `disposition` が `do-now`。今の `judge_accept.is_open`）。
- 裏取り: 単位ごとの下請けが見る 3 つ。根本か（`verdict`: `root`・`not_root`・`unsure`）・証拠（`evidence_found` と見た所）・場所（`location_ok` と正しい場所）。
- 相乗り: 単位どうしの関わりを 1 つの下請けが見る。重複（同じ根の別の現れ）・関わり（`place` が `same` か `apart`）・順番（片方を先に直さないと直せない・試せない）。
- 束ね役: AI の node `judge-verify`。単位を自分で見ず、下請けを Agent の道具で 1 つのメッセージに並べて起こし、1 行の要約だけを返す。
- 申し送り: 機械がまとめた裏取りと相乗りの控え（place の `verify.json`。今の `judge/judge-verify.json`）。修正案の役と再審の役と報告が読む。単位は消さない。
- 例の run: 本物の run `179ced4a-b28e-47f2-8d8e-6ca9030d365e`（開いた単位 2 つ。今の置き場 `<run directory>/judge/verify/`）。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

判定の開いた単位が 2 つ以上ある時、単位ごとに「直せば依頼の症状が消える根本か・判定の理由が言う事実がコードに在るか・key が名指す所が直す所か」を、判定役と別の目の下請けに確かめさせる。別の 1 つの下請けに、単位どうしの重複・関わり・順番を見させる。機械が答えのファイルを型で確かめ、番号を単位の key に戻して申し送りにまとめる。単位は消さない・足さない・ラベルを変えない（根本でないと出ても申し送りと報告の行になるだけで、単位を減らすのは今どおり承認ノードの人か再審）。下請けも束ね役も読むだけで、作業ツリーを変えたら止めの語を返す。

### 1.2 port

入力（YAML の `inputs:`）:

- `judgment`（必須）: `json(judgment.schema.json): 受け付けを通った判定。欄 framing（字）・one_shot（字）・units（行の配列。行は key と label を持ち、disposition・reason・origin_analysis・why_chain・prescriptions を持ちうる）。開いた単位（label が block か、suggest で disposition が do-now）を確かめる`
- `lang`: `text: 人に見せる欄（下請けの答えの evidence・location・why・real_root と、相乗りの答えの why）の言語。空は既定の文（依頼の言語）`。既定 `""`。

`judgment.schema.json`（`blocks/verify/schemas/`。`KNOWN_KEYWORDS` の語だけ）:

```json
{"type": "object", "required": ["units"],
 "properties": {"framing": {"type": "string"}, "one_shot": {"type": "string"},
                "units": {"type": "array", "items": {"type": "object", "required": ["key", "label"],
                          "properties": {"key": {"type": "string", "minLength": 1}, "label": {"type": "string"},
                                         "disposition": {"type": "string"}}}}}}
```

`additionalProperties` は書かない（判定のほかの欄を通す）。作る時に `blocks/.shared/schemas/judgment.schema.json` が既に在れば（diagnose の PR が先に置いた時）、block の形を置かず、説明を `json(shared:judgment.schema.json): …` にする（同じ名の形が pack の 2 か所に在ると形の検査 7.1 の 5 が赤）。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。`failed` は、入力 `judgment` が読めない・prep の中で例外・指示が組めない・束ね役か下請けが作業ツリーを変えた・finish の中で例外の時。開いた単位が 2 つ未満で回さなかった時と、束ね役が落ちて答えが無い単位が残った時は `ok`（今も run を止めない。答えの無い単位は申し送りに「確かめられなかった」と載る）。
- `stop_reason`: 空か `works:judge-verify`（`lib/stopby.py` の `declare("judge-verify", "判定の裏取りの束ね役か下請けが作業ツリーを変えた")`。今の `judge_accept.VERIFY_STOP` と同じ名と同じ意味の字）。作業ツリーが変わった時だけ。run を止めるかは line が決める（今は judge が止めの控えを書き、run が止まる）。
- `reason`: 日本語の 1 行（人に見せる）。回さなかった訳・落ちた訳・確かめられなかった物の数。全部確かめた時は空。
- `verify`: pointer（申し送り `verify.json`）か null（finish が申し送りを書けずに落ちた時だけ）。中身の形は今の `judge-verify.json` のまま（読み手 `lib/planblk.py` の `verify_part` と `lib/runreport.py` の `verify_lines` が読む形）:
  - `units`: `[{n, key, state, verdict?, evidence_found?, evidence?, location_ok?, location?, why?, real_root?, errors?}]`。`state` は `checked` か `unverified`。`checked` の行は答えの欄（`unit` を除く）を持ち、`unverified` の行は `errors`（字の配列）を持つ。
  - `synergy`: `{state, why?, duplicates?, relations?, order?, errors?}`。`checked` なら `duplicates`・`relations` の行は `{units: [key…], why, place?}`、`order` の行は `{first: key, then: key, why}`。
  - 回さなかった形: `{"units": [], "synergy": {"state": "unverified", "errors": [<訳>]}}`（今の `verify_not_run`）。
- `report`: 報告の節「判定の単位の裏取り」の日本語の行の配列（`src/report.py`。5 節）。

今との違い: 今は入力を `judge/judgment.json`・始めの記録（`features_cut`・`lang`）・頭の深さの控え `judge/depth-head.json`・止めの控え `judge/stop.json` から名で開き（`workflows/judge/scripts/verify.py:27-36`・`lib/judge_accept.py:936-940`）、出口は `{ok, reason}` で、申し送りは判定の出力の欄 `verify` で外へ出していた。機能の切り替えと頭の深さと止めの控えの確かめは無くし、回すかは graph の `when:` が決める（README の 4.3・1.2 の D）。

### 1.3 node の並び（`blocks/verify/works-factory-verify.yaml`）

1. `prep`（script `prep.py`。`runtime: uv`・`mutates_checkout: false`）: port を読み、回すかを決め、下請けのファイル・番号の控え・作業ツリーの写し・申し送りの初めの形・束ね役の指示を place に書く。返り `{go, prompt, reason}`（`output_format` は 3 つとも required。`go` boolean・`prompt` string〔`go` が偽の時は空の字〕・`reason` string）。落ちない（`ports.run`。3.1）。
2. `judge-verify`（AI。`prompt: "$prep.output.prompt"`・`depends_on: [prep]`・`when: $prep.output.go == true`・`model: '@wf-judge-core'`・`context: fresh`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch, Agent, Write]`・`mutates_checkout: false`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま `{type: object, additionalProperties: false, required: [summary], properties: {summary: {type: string, minLength: 10}}}`）。輪の中に置かない（受け付けの出し直しを持たない。今のまま。2.8）。
3. `finish`（script `finish.py`。`depends_on: [prep, judge-verify]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 答えのファイルを確かめて申し送りを書き、作業ツリーを比べ、出力を返す。どの段が落ちても落ちない（今の落とし穴 K1・K13 の決まり）。`output_format` は 1.2 の出力の欄を全部 required にし、`status` は `enum: [ok, failed]`、`verify` は `type: [object, "null"]`（`properties` に pointer の `type`〔`enum: [archon_artifact]`〕・`run_id`・`path`）、`report` は字の配列。

`judge-verify` は Write を持つのに `mutates_checkout: false` を書く（下請けが答えのファイルを run の place に Write で書くだけで、作業ツリーは書かない。Archon が node の前後で作業ツリーを照らし、変えたら node を落とす）。今の E7 の検査は、この外れを `tests/layers/scan.py` の表 `KEEP_CHECKOUT` の `("judge", "judge-verify")` で許している。表の鍵はフォルダの名なので、`blocks/` に当てる検査（`tests/layers/test_block_shape.py` の `ExistingRulesCase`）では `("verify", "judge-verify")` が無いと赤になる。この block の PR で、表に同じ訳の行 `("verify", "judge-verify")` を 1 行足す（6 節の 4。今の `workflows/` の木には `verify` のフォルダが無いので、今の検査には効かない）。

script の名 `prep`・`finish` は `lib/` のモジュールの名と重ならない（README の 7.1 の 9）。今の script の名 `verify` は使わない（1 本の script を `stage` で分けていた形をやめた）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/verify/`）の下に書く。名は `src/steps.py` だけが持つ。

- `prep.json`: `{go, failed, reason}`（prep の決めの控え。finish が読む）
- `unit-<n>.md`（n は 1 から）・`synergy.md`: 下請けのファイル（今の `judge/verify/unit-<n>.md`・`synergy.md`）
- `judge-verify-prompt-<n>.md`: 束ね役の指示（`prompt.emit` が書く。今の `judge/verify/prompt.md`）
- `plan.json`: 番号の控え `{units: [{n, key}], answers: <答えの置き場の絶対パス>}`（今の `judge/verify/plan.json`）
- `tree.json`: 束ね役を起こす前の作業ツリーの写し（`lib/accept.tree_state` の形。今の `judge/verify/verify-tree.json`）
- `answers/unit-<n>.json`・`answers/synergy.json`: 下請けが Write で書く答え（今の `judge/verify/answers/`）
- `verify.json`: 申し送り（今の `judge/judge-verify.json`）

prep の頭で、この block の名のファイルだけを名で引いて消す: `prep.json`・`plan.json`・`tree.json`・`verify.json`・`synergy.md`・`answers/synergy.json`・`judge-verify-prompt-*.md`（purpose の `OWN_PROMPTS` と同じ形）と、前の `plan.json` が在ればその `units` の n ごとの `unit-<n>.md`・`answers/unit-<n>.json`、在らなければ今の判定の開いた単位の数までの n ごとの同じ 2 つ。`answers/` のフォルダそのものと place は消さない（README の 13 章「place は作るだけで、消さない」）。今の `shutil.rmtree(answers)`（`judge_accept.py:946`）の替わりで、目的（前の起動の答えを今の判定の答えに数えない）は同じ。

### 1.5 コードの置き場

- `blocks/verify/src/steps.py`: 入口と出口の中身。写す元（README の 9.2。`judgeverify` は verify へ MOVE、`judge_accept` は観点ごとに割る）:
  - `lib/judgeverify.py` の名と語と型: `MIN_UNITS`（2）・`SUBAGENT_TYPE`（`general-purpose`）・`CHECKED`・`UNVERIFIED`・`VERDICTS`・`PLACES`・`WAITING`・`output_format`（束ね役の返答 `{summary}` の型を返す関数。YAML の `judge-verify` の `output_format` と同じ物。finish の返りの型ではない）・`unit_schema`・`synergy_schema`・`_unit_row`・`_initial`・`_load`。指示の文（`TITLE`・`SUB_HEAD`・`RULES`・`UNIT_HEAD`・`ANSWER_AT`・`UNIT_ASK`・`VIEW_HEAD`・`SYNERGY_HEAD`・`ALL_UNITS_HEAD`・`SYNERGY_ASK`・`AGG`・`AGG_REPLY`）と `_head` は写さず md へ（2.3）。`promptsection` の `Section`・`Receive`・`RECEIVES` は写さない（README の 9.1 で消える）。
  - `lib/judge_accept.py` の裏取りの部分: `is_open`・`open_units`（:212-222）・`verify_not_run`・`_verify_off`・`prep_on`・`_check_unit`・`_check_synergy`・`merge_on`（:913-1027）・`_tree_snapshot`・`_moved_since`（:1118-1136）と止めの語 `VERIFY_STOP`（:303）。止めの控えの読み書き（`read_stop`・`write_stop`）は写さない（README の 4.3）。
- `blocks/verify/src/report.py`: 申し送りの値から報告の行を組む（今の `lib/runreport.py` の `verify_lines`〔:982-1014〕を、判定の返りの pointer でなく申し送りの dict で受ける形にした写しと、回さなかった時の 1 行。5 節）。
- `blocks/verify/schemas/judgment.schema.json`（1.2）。
- 使う `lib/`（import するだけ。変えない）: `accept`（`tree_state`・`tree_moved`・`status_keys`・`TREE_SCHEMA`・`type_errors`）・`engine.schema`（`validate_schema`。`lib/graphloops/engine/schema.py`）・`engine.util`（`Reject`）・`stopby`（`declare`）・`jsonfile`・`oneline`。`.shared` の `ports`・`prompt`。
- `rolekit` は使わない（輪も却下の控えも持たない）。
- 作り直しの間は `lib/judgeverify.py` と `lib/judge_accept.py` の裏取りの部分を消さない（今の judge が使う）。組み込みで消す（README の 9.2）。`is_open` は diagnose と fix（`fixboard` の義務の数え）も使う単位の行の述語なので、組み込みで diagnose の出力の行の形のモジュール（README の 4.1）ができれば、写しを消してそこを import する（8 節）。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`blocks/judge/`）: `include: works-factory-verify`（node の id `verify`）、`depends_on: [diagnose]`。`when:` は 2 つの条件の両方が真の時（論理積）: line が深さの表（段 → 回す物）と始めの記録の名指し（今の `entry.switch(start, "judge_verify", depth.tier_adds(…))`）から引いた「判定の裏取りを回すか」が真、かつ再審の道でない（判定の道。今の `verify-merge` の `when: $intake.output.mode == 'judge'` と、`verify-prep` が判定の輪の後だけに走る形）。diagnose の中の判定の受け付けの輪が何回回っても、verify は diagnose が返った後に 1 回だけ回る（今の `verify-prep` が `depends_on: [diagnose-loop]` なのと同じ）。止めの控え（今の `read_stop`）の確かめは、前の段が落ちた時に line が include しないことで替える。`with:` は `judgment: $diagnose.output.judgment`・`lang: <始めの記録の lang>`。
- 既定は回さない（持ち主の決め 2026-10-08。元の works の計り: 27 単位の 11 run で後の段を 1 度も変えず、1 run に 0.6〜3 USD と 1〜2 分を足した。`docs/owner-decisions.md` の 299 行の「重厚は判定の裏取り `judge_verify` を足す」）。この既定は line の表が持ち、block は知らない。
- 止め: line は `$verify.output.stop_reason` が空でなければ、今と同じく run をその語で止める。
- 読み手:
  - plan の修正案の役（申し送りの節。今の `lib/planblk.py` の `verify_part` を `lib/planfile.py:676` が貼る。plan の入力 `verify`〔`workflows/plan/works-factory-plan.yaml:22`〕）: `$verify.output.verify`。同じ run の中の案の直し（2 度目の include）には渡さない（元の works の設計のまま）。README の 8.2 の plan の入力に `verify` が無い（6 節の 2）。
  - diagnose の再審の役（再審の材料に「判定の裏取り」として 1 回目の申し送りを並べる。今の `judge_accept.REJUDGE_MATERIALS` の `VERIFY_FILE`）: 1 回目の `$verify.output.verify`。README の 8.1 の diagnose の入力に無い（6 節の 3）。
  - report の `sections`: `$verify.output.report`。
- block を include しない run では、読み手は pointer の null を受ける。今は judge の出口が回さなかった形の申し送りをいつも置いた（`judge_accept.py:3968-3970`。訳「判定の裏取りを回さなかった」か、機能の切り替えの訳）ので、plan の指示に「相乗り: 確かめられなかった（訳）」の節が、報告に「判定の単位の裏取り（0 単位。…）」の行が、回さない既定の run でもいつも出ていた。null の時にどう書くかは読み手（plan・report・line）の設計書で決める。
- 今の `tests/e2e/evidence.json` の L-E33（`judge_accept.py::prep_on` が `judge-verify.json` に「features_cut に judge_verify」と書く）は、回さない訳を line が持つので line の行に書き直す。J84（`judge/verify/` に下請けのファイル）と P037（plan の指示の「## 判定の単位の裏取り」）は、place のパスと見出しを新しい物に合わせる。

## 2 node の設計シート: judge-verify（束ね役。下請けのファイルも同じ md から組む）

### 2.1 役

束ね役は、単位を自分で見ず、prep が書いた下請けのファイルごとに general-purpose の下請けを Agent の道具で 1 つのメッセージに並べて起こし、全部が返ったら 1 行の要約を返す。単位ごとの下請けは自分の単位 1 つの根本・証拠・場所を確かめ、相乗りの下請けは単位どうしの重複・関わり・順番を見て、どちらも答えの JSON を指定のファイルに Write で書く。

### 2.2 port

- 束ね役の指示: 下請けのファイルの絶対パスの一覧（← prep が place に書いた物）・束ね役の返答の型（← `src/steps.py` の `output_format`。`{summary}` の型）。
- 下請けのファイル: 判定者の見立て（← port `judgment` の `framing`・`one_shot`。字の物だけ）・その単位の行（← port `judgment` の開いた単位の `key`・`label`・`disposition`・`reason`・`origin_analysis`・`why_chain`・`prescriptions`）か、全部の開いた単位の行・答えのファイルの絶対パス（← place）・答えの型（← `unit_schema`・`synergy_schema`）・語（← `VERDICTS`・`PLACES`）・`lang`（← port `lang`）。
- 判定の材料の全部・素材・依頼の行は渡さない（元の works の設計「判定の材料の全部や束ね役の指示書を読ませない」。下請けは自分の単位とコードだけで確かめる別の目）。

### 2.3 組み立ての順（`prompts/judge-verify.md`）

md は 1 本で、prep が段落の真偽を替えて 4 通りに組む（束ね役の指示 1 本と、単位ごとの下請けのファイル・相乗りの下請けのファイル）。下請けは Archon の node ではないので、下請けの指示を `prompts/` の直下の別の md にできない（README の 7.1 の 2）。断片の `prompts/parts/` は 2 つ以上の node が使う物なので使わない。1 本の md に置けば、AI に届く決まった文の在りかは md 1 本で、`prompt.render` の口だけで組める（`.shared` を変えない）。

段落の名（`when`）と、4 通りの値:

| 組む物 | `aggregator` | `view` | `unit` | `synergy` | `spawns` |
|---|---|---|---|---|---|
| 束ね役の指示 | 真 | 偽 | 偽 | 偽 | 偽 |
| 単位 n のファイル | 偽 | 見立てが在る | 真 | 偽 | 偽 |
| 相乗りのファイル | 偽 | 見立てが在る | 偽 | 真 | 偽 |

`spawns` は共通の断片 `query-rule` の中の段落（いつも偽。下請けのファイルが自分で決まりを持つので、束ね役に写させない。2.6）。

差し込み口は全部の組で同じ組の値を渡す（`prompt.render` は選ばれない段落の口にも値を要る）。入らない段落の口には空の字を渡す:

- `{subagent_type}` ← `SUBAGENT_TYPE`（`general-purpose`）
- `{files}` ← 下請けのファイルの一覧の行（`- Unit <n>: <絶対パス>` を n の順に、最後に `- Synergy: <絶対パス>`。札 `Unit`・`Synergy` は材料の短い札で Python に置く。README の 5.3）。束ね役の組だけ
- `{reply_schema}` ← `json.dumps(output_format(), ensure_ascii=False)`（`src/steps.py` の `output_format`。束ね役の返答 `{summary}` の型）。束ね役の組だけ
- `{view}` ← `json.dumps({framing, one_shot のうち字の物}, ensure_ascii=False, indent=1)`。下請けの組だけ（見立てが空なら段落 `view` が偽）
- `{n}` ← 単位の番号（字）。単位の組だけ
- `{unit_row}` ← `json.dumps(_unit_row(u), ensure_ascii=False, indent=1)`。単位の組だけ
- `{all_units}` ← `- Unit <n>: <json.dumps(_unit_row(u), ensure_ascii=False)>` の行を n の順に。相乗りの組だけ
- `{answer}` ← 答えのファイルの絶対パス（単位の組は `answers/unit-<n>.json`、相乗りの組は `answers/synergy.json`）
- `{unit_schema}`・`{synergy_schema}` ← `json.dumps(unit_schema(), ensure_ascii=False)`・`json.dumps(synergy_schema(), ensure_ascii=False)`。それぞれ単位の組・相乗りの組だけ
- `{root}`・`{not_root}`・`{unsure}` ← `VERDICTS`、`{same}`・`{apart}` ← `PLACES`（md と型と受け付けが同じ字を持つ。README の 5.3）。全部の組で同じ値
- `{lang}` ← `prompt.lang(port lang)`。全部の組で同じ値

下請けのファイルの頭（題・役の段落・外への検索の決まり・決まり・見立て）は、全部の単位と相乗りで同じバイトになる（今の `UNIT_HEAD` の注記「全部の単位と相乗りで同じバイト」。違いは `unit`・`synergy` の段落から後だけ）。

節の並び:

1. `<!-- if aggregator -->` 束ね役の題と段落（決まった文と `{subagent_type}`）・`## Sub-agent files` と `{files}` `<!-- end aggregator -->`
2. `<!-- if not aggregator -->` 下請けの題と役の段落（決まった文）`<!-- end aggregator -->`
3. `{shared:query-rule}`（外への検索と出典の決まり。断片の中に段落の印を持つので、段落の中に置けない。だから束ね役の組にも入る）
4. `<!-- if not aggregator -->` `## Rules (the same for every sub-agent)` と決まりの箇条（決まった文と `{unsure}`・`{lang}`）`<!-- end aggregator -->`
5. `<!-- if view -->` `## The judge's view` と `{view}` `<!-- end view -->`
6. `<!-- if unit -->` `## This sub-agent's unit: unit {n}` と `{unit_row}`・見ること (1)〜(3)（決まった文と `{root}`・`{not_root}`・`{unsure}`・`{answer}`・`{n}`）・`{unit_schema}` `<!-- end unit -->`
7. `<!-- if synergy -->` `## This sub-agent's check: synergy between units`・`### All units` と `{all_units}`・見ること（決まった文と `{same}`・`{apart}`・`{answer}`）・`{synergy_schema}` `<!-- end synergy -->`
8. `<!-- if aggregator -->` `## How to answer` と `{reply_schema}` `<!-- end aggregator -->`

md の本文（英語。この block の PR でこのまま置く。作った後の本文の正本は `blocks/verify/prompts/judge-verify.md` で、後の指示の変更でこの設計書は直さない）:

````markdown
<!-- if aggregator -->
# Aggregator of the checks on the judgment's units (written by the machine)

You are the aggregator. Do not look at the units yourself. For each sub-agent file listed below, start one sub-agent with the Agent tool. Put all the sub-agent calls in a single message, so that they run at the same time. Use `subagent_type` {subagent_type} for every one of them (no other type). The request to each sub-agent can be the single line "Read <file> with the Read tool and follow its instructions." Each file already carries every rule its sub-agent needs, including the rules for outside queries, so add nothing to the request. The sub-agents only read: each writes its answer to a file (the file names where) without changing the work tree, and returns a one-line summary at the end. The machine checks and merges the answer files, so do not copy what the answers say.

## Sub-agent files

{files}
<!-- end aggregator -->
<!-- if not aggregator -->
# Sub-agent that checks the judgment's units

You are a sub-agent that checks the judgment's units. You only read: look into the code behind the evidence with Read, Grep, and Glob, and use Write only for the answer file that the last section names. Do not use Edit or Bash, and do not change a single character of the work tree. The judge cut a person's fix request into root-cause units. Check that cut with an eye other than the judge's. You need not go and read instruction files elsewhere (do read the code behind the evidence).
<!-- end aggregator -->

{shared:query-rule}

<!-- if not aggregator -->
## Rules (the same for every sub-agent)

- Do not write how to fix anything (another role writes the plan).
- Do not propose removing, adding, or relabelling units. A unit is a duty to fix, and this check does not reduce it. Even if a unit turns out not to be the root cause, that only reaches the role that writes the plan and the report, as a note.
- Use the web (WebSearch, WebFetch) only when the code behind the evidence does not settle the question. Do not reopen the sources of the judge's precedents.
- Write `why` and `evidence` as facts you saw (path:line and what was there). If it is a guess, answer `{unsure}`.
- Write the free-text fields of your answer (`evidence`, `location`, `why`, `real_root`, and the `why` of every row) in {lang}. Keep paths, identifiers, and unit keys as they are. If the request is not shown to you, write in the same language as the `reason` text of the units.
<!-- end aggregator -->
<!-- if view -->

## The judge's view

```json
{view}
```
<!-- end view -->
<!-- if unit -->

## This sub-agent's unit: unit {n}

```json
{unit_row}
```

What to look at: (1) Root cause (`verdict`): if this unit is fixed, does the symptom in the request go away? Is it not the result (one appearance of the symptom) of another unit or of a place that no unit covers? One of `{root}`, `{not_root}`, `{unsure}`. If `{not_root}`, write in `real_root` the real root (the path and name of the place you found, and why it can be called the root). Overlaps between units are checked by another sub-agent. (2) Evidence (`evidence_found`, `evidence`): did you confirm in the code the facts that the judgment's reason states? Write where you checked and what you saw. (3) Place (`location_ok`, `location`): are the path and name that the unit's `key` names the place to fix? If not, write the right place in `location` (if they are right, the same place). Make your answer one JSON value that matches the JSON Schema below, and write it with the Write tool to the file {answer} (write no other file). When you have written it, return only one line as your last message: `Unit {n}: <verdict>`.

```json
{unit_schema}
```
<!-- end unit -->
<!-- if synergy -->

## This sub-agent's check: synergy between units

### All units

{all_units}

The check inside one unit is done by other sub-agents. You look only at how the units relate: `duplicates` (other appearances of the same root; closed by the same fix), `relations` (split in two by `place`: `{same}` means they change the same line or the same block, or one fix changes a premise of the other (a name, a type, a way of calling); `{apart}` means they only touch different places of the same file or the same test file (another function, another class, a test added to another class) and the fixes do not overlap; do not answer `{same}` only because the file is the same), and `order` (one cannot be fixed or tested until the other is fixed first). Name units by the numbers above. If there are none, give an empty array and write in `why` what you looked at and why there are none. Make your answer one JSON value that matches the JSON Schema below, and write it with the Write tool to the file {answer} (write no other file). When you have written it, return only one line as your last message: `Synergy: duplicates <count>, relations <count>, order <count>`.

```json
{synergy_schema}
```
<!-- end synergy -->
<!-- if aggregator -->

## How to answer

When every sub-agent has returned, answer only with JSON that matches this JSON Schema (put the sub-agents' one-line summaries in `summary`):

```json
{reply_schema}
```
<!-- end aggregator -->
````

md の中の `<file>`・`<verdict>`・`<count>` は差し込み口の形でないので字のまま残る。

### 2.4 返す形

- 束ね役: 今の `output_format` のまま `{summary}`（`minLength: 10`）。機械は読まない（答えの中身はファイルに在り、束ね役に写させない。元の works の線の木の段 1 の教訓）。人に見せる欄は無い。
- 単位の下請けの答え（`unit_schema`）: 今のまま。`unit`（1 以上の整数）・`verdict`（`root`・`not_root`・`unsure`）・`evidence_found`（boolean）・`evidence`（10 字以上）・`location_ok`（boolean）・`location`（1 字以上）・`why`（10 字以上）は必須、`real_root` は字。`additionalProperties: false`。
- 相乗りの下請けの答え（`synergy_schema`）: 今のまま。`why`（10 字以上）・`duplicates`（`{units: 2 つ以上の整数, why: 4 字以上}`）・`relations`（同じ形に `place`: `same`・`apart` が必須）・`order`（`{first, then, why}`）は全部必須。
- 人に見せる欄: 答えの `evidence`・`location`・`why`・`real_root` と、相乗りの各 `why`（修正案の指示と報告に載る）。言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値）

例の run は開いた単位 2 つ（単位 1 は `docs/polyfills.md` の証拠の書き方、単位 2 は同じ名簿の上流の確かめの欄）。`lang` は空で、`{lang}` には既定の文が入った形。place は `<place>`（line から include された時は `<run directory>/judge/verify`）と書く。

束ね役の指示（`judge-verify-prompt-1.md`）:

```markdown
# Aggregator of the checks on the judgment's units (written by the machine)

You are the aggregator. Do not look at the units yourself. …（決まった文。subagent_type general-purpose）

## Sub-agent files

- Unit 1: <place>/unit-1.md
- Unit 2: <place>/unit-2.md
- Synergy: <place>/synergy.md

Rules for queries to outside services and for the sources you use: …（{shared:query-rule} の本文。spawns が偽なので下請けの段落は入らない）

## How to answer

When every sub-agent has returned, answer only with JSON that matches this JSON Schema …

```json
{"type": "object", "additionalProperties": false, "required": ["summary"], "properties": {"summary": {"type": "string", "minLength": 10}}}
```
```

単位 1 のファイル（`unit-1.md`。単位 2 と相乗りのファイルも `## This sub-agent's …` の前まで同じバイト）:

```markdown
# Sub-agent that checks the judgment's units

You are a sub-agent that checks the judgment's units. You only read: …（決まった文）

Rules for queries to outside services and for the sources you use: …（{shared:query-rule} の本文）

## Rules (the same for every sub-agent)

- Do not write how to fix anything …（決まりの箇条 5 つ。最後は言語の 1 行で、{lang} に the language of the request (the user's language)）

## The judge's view

```json
{
 "framing": "根は 1 つ。埋めの名簿（docs/polyfills.md）の証拠と確かめの結果が、止めた Archon の版の源に機械で結ばれていない。…（約 900 字）",
 "one_shot": "名簿の照らし（scan の E2 と tests/layers/test_polyfills_listed.py）を、…（約 400 字）"
}
```

## This sub-agent's unit: unit 1

```json
{
 "key": "docs/polyfills.md 証拠: 在り処が前の版の行番号で、引用が止めた版の源の字に照らされない",
 "label": "block",
 "disposition": "do-now",
 "reason": "事実: docs/polyfills.md の `- 証拠:` の 7 行（…）…（約 1800 字）",
 "origin_analysis": "①ロジック: 文書の事実が誤っている。…",
 "why_chain": ["なぜ証拠が行番号で書かれたか: …", "…", "…"],
 "prescriptions": ["零処方: …", "…（7 本）"]
}
```

What to look at: (1) Root cause (`verdict`): … One of `root`, `not_root`, `unsure`. … write it with the Write tool to the file <place>/answers/unit-1.json (write no other file). … `Unit 1: <verdict>`.

```json
{"type": "object", "additionalProperties": false, "required": ["unit", "verdict", "evidence_found", "evidence", "location_ok", "location", "why"], …}
```
```

相乗りのファイル（`synergy.md`）は、頭が同じで、`## This sub-agent's check: synergy between units`・`### All units` の下に `- Unit 1: {"key": "docs/polyfills.md 証拠: …", …}`・`- Unit 2: {"key": "docs/polyfills.md 各行: 止めた版より後の上流で塞がったかの確かめの結果が名簿から読めない", …}` の 2 行、見ることの段落（`same`・`apart` と `<place>/answers/synergy.json`）、`synergy_schema` が続く。

例の run の答え: 単位 1・2 とも `checked`・`root`。相乗りは `checked` で、順番の 1 行（単位 1 を先に、単位 2 を後に）。報告に「判定の単位の裏取り（2 単位。単位は消していない。減らすなら承認ノードか再審で）:」と順番の 1 行が出た。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。

今の指示は 4 か所に在る: 束ね役の node の md `workflows/judge/commands/judge-verify.md`（14 行。言語の 1 行・外への検索の決まりの塊・「指示書を Read で読め」）、束ね役の指示書 `judge/verify/prompt.md`（`lib/judge_accept.py:965-968` が `AGG`・`AGG_REPLY` から組む）、下請けのファイル `unit-<n>.md`・`synergy.md`（`:948-962` が `TITLE`・`SUB_HEAD`・`RULES`・`VIEW_HEAD`・`UNIT_HEAD`・`UNIT_ASK`・`ANSWER_AT`・`SYNERGY_HEAD`・`ALL_UNITS_HEAD`・`SYNERGY_ASK` から組む。文は `lib/judgeverify.py:46-79`）。

- 移した: lib の Python の文の定数 12 個（`lib/judgeverify.py:46-79`）を md の 1 本へ。lib の Python に残るのは材料の行（単位の行の JSON・下請けのファイルの一覧）と値（語・型・番号・パス）だけ。
- まとめた: 束ね役の node の md と束ね役の指示書の 2 段（node の md が「指示書 `prompt_file` を Read で読め」と言い、指示書が本文を持つ）を、prep が組んだ指示を `prompt:` に直に入れる 1 段に（README の 5.2）。「返すのは指示書の JSON Schema に合う JSON だけ」（md:14）は `## How to answer` の 1 文に入った。
- 移した: 外への検索の決まりの塊（md:3-10）を共通の断片 `{shared:query-rule}` に。今は束ね役にだけ届き、塊の頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」で下請けへ写させていたが、同じ束ね役の指示書は下請けへの頼みを「<ファイル> を Read で読み、その指示に従え」の 1 行でよいと言い、2 つが食い違っていた（例の run の下請けのファイルに塊は無い）。新しい形では塊が下請けのファイルに入るので、決まりは写しに頼らず下請けに届く。断片の段落 `spawns` は偽にし、束ね役の段落に「ファイルが外への検索の決まりを含めて全部の決まりを持つので、頼みに足すな」の 1 文を足した。束ね役の組にも塊が入るのは、断片が段落の印を持ち段落の中に置けないため（束ね役は自分で検索しないので害は無い）。
- 消した: 塊の頭の「works の包みより」（world の 3.6 と同じ）。
- 移した: 言語の 1 行（`$verify-prep.output.lang_line`。`rolekit.lang_line` が汎用の欄の並びで束ね役の頭に付けていた物）を、下請けの決まりの 1 箇条に。人に見せる欄（`evidence`・`location`・`why`・`real_root`・相乗りの `why`）を書くのは下請けで、束ね役の `summary` は誰も読まないので、今の束ね役の頭の言語の 1 行は人に見せる欄に届いていなかった（例の run の下請けのファイルに言語の文は無い）。
- 替えた: 見出し「## この下請けの単位: 単位 {n}」「## この下請けの確かめ: 単位どうしの相乗り」「### 単位の全部」「## 判定者の見立て」「## 決まり（全部の下請けで同じ）」を英語に。下請けのファイルの一覧の札「単位 n」「相乗り」と、最後の 1 行の形「`単位 {n}: <verdict>`」「`相乗り: 重複 <数>・関わり <数>・順番 <数>`」も英語に（`Unit {n}: <verdict>`・`Synergy: duplicates <count>, relations <count>, order <count>`。機械は読まない）。
- 移した: 語（`root`・`not_root`・`unsure`・`same`・`apart`）を差し込み口に（型の enum と受け付けと同じ定数から入れる。README の 5.3）。
- 消した: 束ね役の node の YAML の `command:` と、ほかの node の id（`$verify-prep.output.lang_line`・`$verify-prep.output.prompt_file`）。
- 足した物: 上の 2 つ（束ね役の「頼みに足すな」と、下請けの言語の箇条）だけ。英語にした（#764）。
- 足した物（レビューの直し）: 言語の箇条の末尾に「依頼が見えない時は、単位の `reason` と同じ言語で書く」を足した。`lang` が空だと `{lang}` は既定の文（依頼の言語）になるが、下請けには依頼を見せない（2.2）ので解けないため。言語を選ぶ仕組みは足さず、md の 1 文で閉じる。`{lang}` はそのまま。
- 足した物（レビューの直し）: `{shared:query-rule}` が「Go to primary sources first」（一次の出典を先に読む）の項を持ち込む。元の指示（md:3-10）に無かった項で、下請けにも届く。
- 役の定義の断片（`role-inspector` など）は使わない。どれも「ファイルを作れない・作ろうとするな」と言い、答えのファイルを Write で書く下請けと食い違うため。今と同じく役の段落を md に持つ。

### 2.7 元の works と graphloops の同じ場面

元の works は `works/blk-judge/` の中の 3 つの節（`verify-prep`・`judge-verify`・`verify-merge`。設計 `works/docs/plans/2026-10-06-judge-verify.md`）。工場は #76 で judge の中に写した。工場に無い物・違う物と、その訳:

- 独立したブロックにしなかった（元の設計「入力は判定の控えだけで、判定の輪と同じ周に閉じるため」）: この block では、入力が判定の port だけなので独立の block にする（README の 8.1）。周に閉じることは、judge のまとめが diagnose の後に 1 回だけ include することで続く。
- 回す切り替え: 元はブロックの入力 `verify`（空は on。線が既定の off を渡す）。工場は始めの記録の機能の切り替えと頭の深さの段の足しから `entry.switch` が決める形にした（#76 と `9407b441` の重厚の段）。この block は切り替えを知らず、line の `when:` が決める（README の 1.2 の D）。
- 答えの置き場: 元は盤面の外の run ごとの置き場（盤面は役が書けない）。工場は judge の置き場の `verify/answers/` にした（#76。盤面が無い）。この block は place の `answers/`。
- trace の行（元の `TRACE_OP` の `judge_verify`。確かめた数・確かめられなかった数・相乗りの有無）と、まとめの出口の数（`verified`・`unverified`）: 工場に無い（#76。共有の盤面の trace が無い）。この block も足さない。数は申し送りと報告の行から読める。
- 申し送りを修正前の承認ノードの文にも載せるか（元の設計の「残り」）: 工場も載せていない。この block の外（line の承認ノードの設計書）の事。
- 1 単位の時は回さない（元の設計の費用の決め。相乗りは 2 つ以上でしか意味が無く、1 単位の見る所は事前審査の下請けと重なる）: 工場も同じ。この block も `MIN_UNITS` を持つ（入力の形で決まる block の決めで、深さの決めではないので line に出さない）。
- 出し直しの輪を持たない（元の設計「申し送りは義務を変えないので、1 単位の確かめのために束ね役をもう 1 度起こす費用に見合わない」）: 工場も同じ。この block も同じ。

graphloops の review-graph（`~/src/claude-plugins/graphloops/prompts/review-loop/`）には、判定の切り方を別の目で確かめる段が無い。近いのは、事前審査 `p2.plan_review.md` の項目ごとの下請け（案の項目を判定の理由と独立設計で深く見る）と、修正役の異議から入る再審 `p2.rejudge*.md` で、どちらも工場の plan-review と diagnose の再審が持つ。この block は graphloops より多く持つ: 単位ごとの別の目・単位どうしの相乗り・答えを機械が型と番号で確かめる・単位を消さない申し送り・読むだけの守り（作業ツリーの比べ）。

### 2.8 受け付け

束ね役の返答は Archon が `output_format` で照らすだけで、受け付けの node と出し直しの輪は持たない（今のまま。2.7）。答えのファイルの受け付けは finish が持ち、落ちた答えは単位ごとに「確かめられなかった」と誤りの行で残す（単位は消さない）。決まり（今の `_check_unit`・`_check_synergy` のまま。誤りの文も今の字のまま日本語）:

- 単位の答え: ファイルが無い →「答えのファイルが無い（<パス>）」。JSON として読めない →「答えのファイルが JSON として読めない（<訳>）」。`unit_schema` に合わない → `validate_schema` の誤りの行。`unit` が番号と違う →「$.unit: <n> でない（<値>）」。`verdict` が `not_root` で `real_root` が空白を除いて 4 字未満 →「$.real_root: not_root なのに本当の根が書かれていない」。誤りが 1 つでも在れば `state: unverified` と `errors`、無ければ `state: checked` と答えの欄（`unit` を除く）。
- 相乗りの答え: 同じく無い・読めない・型に合わない。番号の外 →「単位 <x> は無い（単位は 1〜<N>）」（番号の外の全部を小さい順に 1 行ずつ）。`duplicates`・`relations` の行が 2 つ以上の別の単位を持たない →「$.duplicates・relations: 同じ単位だけを並べた行（<units>）」。通れば番号を単位の key に戻し（行の中の重なりは最初の物だけ残す）、`relations` の `place` を残す。
- 作業ツリー: prep が置いた `tree.json` と今を `accept.tree_moved` で比べる。比べる欄は `accept.status_keys(True)`（`porcelain` を除く。node が `mutates_checkout: false` で、Archon が前後の git status を照らすため。今の `verify-merge` の `with: {status_guarded: true}` と同じ）。写しが無い・読めない・形が違う時は、その訳を変わった所として数える（閉じた側に倒す。今の `_moved_since` の `Reject` のまま）。変わっていれば、申し送りを書いた後に `status: failed`・`stop_reason: works:judge-verify`・`reason`「判定の裏取りの束ね役か下請けが作業ツリーを変えた（読むだけの役）: <変わった所を・でつないだ物>」。
- 諦めるまでの回数: 無い（輪を持たない）。束ね役の node の `retry`（2 回）だけ。

### 2.9 試験

7 節。

## 3 script の node

### 3.1 `prep.py`

`os.environ.get("INPUTS_JUDGMENT")`・`os.environ.get("INPUTS_LANG")` を字のままで読み、`steps.prep(ports.place(), judgment=…, lang=…)` を `ports.run` で呼ぶ（fallback `{"go": False, "prompt": "", "reason": "判定の裏取りの支度が落ちた（<訳>）"}`）。`steps.prep` の順:

1. 1.4 の名のファイルを消す。
2. port を読む: `judgment` は `ports.json(raw, "judgment.schema.json")`（落ちれば理由の頭に「入力 judgment: 」を付ける。world の 9.1 の 3）、`lang` は `ports.text(raw).strip()`。
3. 開いた単位を選ぶ（`open_units`: `units` の行のうち dict で `key` が字で `is_open` の物を、並びのまま）。
4. 開いた単位が `MIN_UNITS` 未満 → 回さない: 申し送りに回さなかった形（訳「開いた単位が <k> つ（2 つ未満は相乗りが無く、裏取りを回さない）」）を書き、`prep.json` に `{go: false, failed: false, reason}`、返り `{go: false, prompt: "", reason}`。
5. 4 通りの組を全部 `prompt.render("judge-verify", values, when)` で先に組む（組めなければ `PromptError` を受けて 7 へ。ファイルを書く前に組むので、組めない時に番号の控えが残らない）。
6. 書く（今の `prep_on` と同じ順）: `answers/` を作る（在れば作らない）→ `unit-<n>.md`（n の順）→ `synergy.md` → 束ね役の指示（`prompt.emit("judge-verify", values, when, prompt.round_of("judge-verify"))`）→ `tree.json`（`accept.tree_state(Path.cwd())`）→ `plan.json`（`answers` は `answers/` の絶対パス）→ 申し送りの初めの形（`_initial`。全部の単位と相乗りが `unverified` で `errors` は `[WAITING]`。束ね役が落ちても読み手に「確かめていない」が届く）→ `prep.json` に `{go: true, failed: false, reason: ""}`。返り `{go: true, prompt: <emit の prompt>, reason: ""}`。
7. 2・3・5・6 のどこかで例外 → 申し送りに回さなかった形（訳「判定の裏取りの支度の中で例外（<型の名>: <中身>）」か port の訳）を書き、`plan.json` を消し、`prep.json` に `{go: false, failed: true, reason}`、返り `{go: false, prompt: "", reason}`。今の `verify.py:37-40` と同じく判定は消さない。

`prompt.round_of` は 1 の消しの後なので、いつも 1 になる（resume で prep が走り直した時も、前の指示を消してから組む）。

### 3.2 `finish.py`

`steps.finish(ports.place())` を `ports.run` で呼ぶ（fallback `{ok: false, status: "failed", stop_reason: "", reason: "判定の裏取りのまとめの中で例外（<訳>）", verify: null, report: ["判定の単位の裏取り: まとめが落ちた（<訳>）"]}`）。`steps.finish` の順:

1. `prep.json` を読む（無い・読めない時は `{go: false, failed: true, reason: "判定の裏取りの支度が走らなかった（番号の控えが無い）"}` として扱う）。
2. `plan.json` が無い（回さなかった・支度が落ちた）: 申し送りが無ければ回さなかった形（訳は `prep.json` の `reason`）を書く。返り: `status` は `prep.json` の `failed` が真なら `failed`、偽なら `ok`。`stop_reason` は空、`reason` は `prep.json` の `reason`、`verify` は申し送りの pointer、`report` は回さなかった 1 行（5 節）。
3. `plan.json` が在る: 作業ツリーを比べ（2.8）、単位ごとに `_check_unit`、相乗りを `_check_synergy` で確かめて申し送りを書く（作業ツリーが変わっていても書く。今のまま）。返り: 作業ツリーが変わっていれば `status: failed`・`stop_reason: works:judge-verify`・その `reason`。変わっていなければ `status: ok`・`stop_reason: ""`・`reason` は、全部の単位と相乗りが `checked` なら空、そうでなければ「確かめられなかった物がある（単位 <unverified の数> / <単位の数>・相乗り <確かめた|確かめられなかった>）」。`verify` は申し送りの pointer、`report` は 5 節。`ok` は `status == "ok"`。

## 4 単独で呼ぶ

```sh
WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-verify --cwd <対象> \
  --input judgment='{"framing":"…","one_shot":"…","units":[{"key":"a.py mean: 分母","label":"block","reason":"…"},{"key":"a.py clamp: 上限","label":"block","reason":"…"}]}' \
  --input lang=日本語
```

`judgment` は値そのもの・ファイルのパス（作業ツリーからの相対か絶対）・その run の pointer のどれでもよい（README の 4.2）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。

## 5 報告の行（`src/report.py`）

`lines(doc, ran)`。`doc` は申し送りの dict、`ran` は束ね役を起こしたか（`plan.json` が在ったか）。

- `ran` が偽: `["判定の単位の裏取り: 回さなかった（<synergy の errors を・でつないだ物>）"]`。今は回さなかった run でも「判定の単位の裏取り（0 単位。単位は消していない。減らすなら承認ノードか再審で）:」と「単位どうしの相乗りは確かめられなかった」が出て、回さなかった訳は出なかった（`runreport.verify_lines` が 0 単位を確かめた場合と見分けない）。訳を出す形に替えた（6 節の 5）。
- `ran` が真: 今の `runreport.verify_lines`（:986-1014）の中身のまま。単位ごとに、`unverified` は「確かめられなかった: <key>（<errors を・でつなぎ 1 行にした物>）」、`not_root` は「根本でない: <key>（本当の根: <real_root>。<why>）」、`unsure` は「根本か決められない: <key>（<why>）」、`evidence_found` が偽は「証拠が無い: <key>（<evidence>）」、`location_ok` が偽は「場所が違う: <key>（正しい場所: <location>）」。相乗りが `checked` なら重複「重複: <units を・でつなぐ>（<why>）」と順番「順番: <first> → <then>（<why>）」（関わりは載せない。今のまま）、`checked` でなければ「単位どうしの相乗りは確かめられなかった」。行が無ければ `["判定の単位の裏取り: <単位の数> 単位とも根本・証拠・場所が合った（重複・順番の名指しなし）"]`、在れば頭「判定の単位の裏取り（<単位の数> 単位。単位は消していない。減らすなら承認ノードか再審で）:」と `  - <行>` の並び。字の 1 行化は `lib/oneline.one_line`。
- 「申し送りが読めない」の行（今の `verify_lines` の頭）は持たない（この block は自分で書いた申し送りを値で持つ）。

## 6 README へ返す問題と、根拠を書いて自分で決めた事

1. 入力 `materials` を持たない。README の 8.1 は `judgment` file と `materials` json を挙げるが、今の役も元の works の役も素材を読まない（`prep_on` が読むのは判定だけ）。元の works の設計は下請けに「判定の材料の全部を読ませない」と決めていて、自分の単位とコードだけで確かめる別の目にしている。素材を渡すと指示が変わり、判定役と同じ材料に寄った目になる。README の 8 節の頭「詳しい port は各設計書で決める」に従い、ここで決めた。`judgment` の form は `file` でなく `json(judgment.schema.json)`（値そのものも pointer も受け、単独の run と筋書きで判定を字で渡せる）。README の 8.1 の verify の行は、組み込みか次の README の直しで「入力 `judgment` json」に合わせる。
2. README の 8.2 の plan の入力に申し送りが無い。今の plan は入力 `verify` で受けて修正案の役の指示に節を貼る（`planblk.verify_part`。「根本でない・場所が違う・証拠が無いと出た単位も案から外せない。本当の根の単位と同じ項目にまとめるか、approach に答えを書け。重複・同じ所の関わり・順番は項目の組み方に使え」）。plan の設計書が入力を足さないと、この能力が落ちる。
3. README の 8.1 の diagnose の入力に申し送りが無い。今の再審の役は「判定の裏取り」を材料の 1 つとして読む（`judge_accept.REJUDGE_MATERIALS`）。diagnose の設計書が、再審の時の前の判定を運ぶ入力 `prior`（README の 8.1）の中に含めるか、入力を足すかで決める。
4. `tests/layers/scan.py` の `KEEP_CHECKOUT` に `("verify", "judge-verify")` を 1 行足す（1.3）。README の 11.1 の「各 PR が触るのは block のフォルダ・試験・設計書だけ」の外。表の鍵がフォルダの名で、block の名が今のサブグラフの名と違うため避けられない。`mutates_checkout: false` を外す道（表を触らない）は取らない: Archon が node の前後で作業ツリーを照らす守りが落ち、残るのは finish の比べだけになる（今は両方が守る）。組み込みで今の `("judge", "judge-verify")` の行を消す。
5. 報告の行の「回さなかった」の 1 行（5 節）。振る舞いの変更は報告の字だけ。読み手が回さなかった訳を見られる。
6. `ok` は `status == "ok"`。今の `verify-merge` の `ok` は作業ツリーが変わった時だけ偽で、支度が落ちた時も真だった（判定は消さず run も止めない）。この block では支度が落ちた時と port が読めない時も `failed` にする（world の 9.1 の 1 と同じく、単独で呼ぶ人が `outcome_field:` で落ちを知れるように）。run を止めるかは line が `stop_reason` で決めるので、支度が落ちても今と同じく止めない。
7. 下請けの指示を、束ね役と同じ md 1 本から、md の中の条件つきの節（`<!-- if aggregator -->`・`unit`・`synergy`・`view` の 4 つ。2.3 の表）を prep が真か偽かで選んで組む（2.3）。`prompts/parts/` の断片に分ける形と、`.shared/prompt.py` に「断片だけを組む口」を足す形は取らない。前者は 2 つ以上の node が使う物でないので README の 5.1 に合わず、後者は共通の口を変える（11.1 の外）。
8. 番号の控え `plan.json`（prep が書く、単位の番号 n と key の対応 `{units: [{n, key}], answers}`。1.4）の欄 `answers` は、下請けが答えの JSON を書くフォルダ（place の `answers/`）の絶対パスで持つ（今のまま）。finish はこの欄のフォルダから `unit-<n>.json`・`synergy.json` を読み、欄が無ければ place の `answers/` を読む。

## 7 試験と、済んだと言える条件

### 7.1 standalone の fixture（`blocks/verify/fixtures/`）

- `standalone.stubs.yaml`: 入力は `judgment`（JSON の字。開いた単位 2 つ〔`label: block`〕と、開いていない単位 1 つ〔`label: nit`〕、`framing`・`one_shot` つき）だけ。`exec-code: true`（prep を差し替えない）。`reached: [prep, judge-verify, finish]`。`resolved-text-contains` の `judge-verify` は md の決まった文 `You are the aggregator. Do not look at the units yourself.`。`judge-verify` の台本の返答は `{summary: "Unit 1: root; Unit 2: root; Synergy: duplicates 0, relations 0, order 0"}`。答えのファイルは無いので、finish は `status: ok` で、両方の単位を「確かめられなかった」と申し送る（筋書きは完了と `reached` と指示の字だけを見る）。
- `one-unit.stubs.yaml`: 開いた単位 1 つの判定。`reached: [prep, finish]`（`judge-verify` は `when:` で飛ぶ。台本の返答を置かない）。
- 筋書きは `expect: completed` を見る。作業ツリーが変わる道と答えの確かめは筋書きでなく 7.2 の試験が見る。

### 7.2 `tests/blocks/verify/`（`__init__.py` と下の 3 本）

- `test_steps.py`（`kit.load("verify", "steps")` と `kit.env`。git のリポジトリは初めの commit を置いてから使う）。今の `lib/tests/test_judge_accept.py` の `VerifyPrepCase`・`VerifyMergeCase` から写す（`judge/` のパスを place に、`ja.prep_on`・`ja.merge_on` を `steps.prep`・`steps.finish` に替える）:
  - 開いた単位の選び（今の :44「元 test_judge_verify の開いた単位の数え」）: `block`・`suggest` かつ `do-now` は開き、`suggest` の `defer`・`nit`・`info`・`key` の無い行は開かない。
  - `test_one_open_unit_does_not_go_and_writes_not_run`（今の `test_one_open_unit_or_off_does_not_go_and_writes_not_run` の 1 単位の部分。機能の切り替えの部分は line の試験へ）: 返り `go` 偽・`prompt` 空・訳が在る。申し送りは `units: []` と `unverified` の相乗り。finish の返りは `status: ok` と回さなかった 1 行。
  - port が読めない（壊れた JSON・`units` の無いオブジェクト・JSON の `null`）: `go` 偽、finish は `status: failed`・`reason` が「入力 judgment: 」で始まる・申し送りは回さなかった形。
  - `test_two_open_units_write_briefs_and_prompt`（今のまま）: 下請けのファイルの名が `unit-1.md`・`unit-2.md`・`synergy.md`、`unit-1.md` に自分の単位の key が在りほかの単位の key が無い、答えのファイルの絶対パスが在る、束ね役の指示に `general-purpose` と 3 つのファイルのパスが在る、申し送りが全部 `unverified` で `WAITING`。足す: 3 つの下請けのファイルが `## This sub-agent's` の前まで同じバイト・下請けのファイルに外への検索の決まりの頭の 1 文が在る・束ね役の指示に下請けの決まりの節（`## Rules`）が無い・`lang` に渡した字が下請けのファイルに在る。
  - 前の起動の答えを数えない: 前の `answers/unit-1.json` を置いて prep を回し直すと消える。place のほかのファイル（別の名の物）は消えない。
  - `test_good_answers_are_merged_with_keys`・`test_verification_never_deletes_units`・`test_bad_missing_and_out_of_range_answers_are_unverified`（今のまま。誤りの文の字も今のまま）。
  - `test_tree_moved_returns_stop_reason`（今の `test_tree_moved_writes_verify_stop`）: 追跡しているファイルを書き換えて finish を回すと `status: failed`・`stop_reason: works:judge-verify`・`reason` に「作業ツリーを変えた」、申し送りは単位 2 行のまま書かれる。`tree.json` を消した時も `failed`（写しが無い訳が `reason` に在る）。
  - `test_finish_without_prep_record_writes_not_run`（今の `test_merge_without_prep_record_writes_not_run`）: `plan.json` と申し送りを消すと、finish が回さなかった形を書き `status` は `prep.json` の `failed` による。
  - 止めの語: `steps` の止めの語が `stopby.HEAD + "judge-verify"` で、`lib/judge_accept` と同じ過程で読んでも `declare` が落ちない（同じ名と同じ意味）。
- `test_report.py`（今の `lib/tests/test_runreport.py` の `test_verify_pr_excluded_and_premise_hypotheses` の裏取りの部分から写し、足す）: `not_root` の行「根本でない: u1（本当の根: b.py。呼び手の側）」・全部合った時の 1 行・`unverified`・`unsure`・証拠なし・場所違い・重複・順番・相乗りが確かめられなかった時の行・回さなかった時の 1 行（訳つき）。
- `test_verify.py`（script を子のプロセスで回す。`kit.Run(self, "verify")`）: `prep` → 台本の下請けとして `answers/unit-1.json`・`unit-2.json`・`synergy.json` を書く → `finish` と回し、返りの 6 欄（`ok`・`status`・`stop_reason`・`reason`・`verify`・`report`）・`verify` の pointer の先の中身・`report` の行を照らす。`include="judge__verify__prep"`（と finish も同じ道）で回すと place が `judge/verify/` に分かれる。YAML の起こし方の照らし: `judge-verify` の `model`・`context`・`allowed_tools`・`mutates_checkout`・`retry`・`sandbox`・`output_format` が 1.3 の値（今の `tests/workflows/test_judge.py:100` の行と同じ）、`prep` の出力の 3 欄、`finish` の `trigger_rule: all_done`。

写さない試験（古い中身だけを見る）: `lib/tests/test_judge_accept.py` の `test_places_are_under_the_brief_dir`（今の置き場の名どうしの照らし）・`test_judgeverify_loads_before_judge_accept`（lib の読み込みの循環）・`test_one_open_unit_or_off_does_not_go_and_writes_not_run` の off の部分（機能の切り替えは line）、`tests/workflows/test_judge.py` の `test_heavy_record_does_not_cut_the_verify`（段の足しは line の表）・`test_verify_waits_on_the_head_depth`（頭の深さの控えを読まない。judge のまとめは `depends_on: [diagnose]`）・`test_verify_merge_waits_on_the_judge_mode`（judge のまとめの `when:` の試験へ）・`BriefCase` の言語の 1 行の照らしの verify の行（言語は `{lang}` の箇条）・`test_unreadable_start_pointer_degrades_in_every_lang_line_script` の verify の行（始めの記録を読まない）、`tests/workflows/test_judge.py:1679-1680` の写しの台帳の行（README の 9.4 で消える）。読み手の側の試験は読み手に残す: `tests/workflows/test_line.py:551-565`（plan の指示に申し送りが届く。plan と line へ）・`lib/tests/test_runreport.py:2239` の `test_broken_verify_notes_say_so`（report の読み手が null や壊れた pointer をどう書くかは report の設計書で決める）。

### 7.3 指示の比べ（審査が見る）

この block では、日本語の md で今の指示と同じ字になることを照らす 1 つ目の commit を作らない（持ち主の速さの決め。指示の比べは審査が古い指示と新しい指示を並べて見る）。審査は例の run `179ced4a-…` の `judgment.json` と同じ値で組んだ 4 通り（束ね役・`unit-1.md`・`unit-2.md`・`synergy.md`）を、今の `prompt.md`・`unit-1.md`・`unit-2.md`・`synergy.md` と束ね役の node の md と並べ、2.6 の差の一覧どおりかを見る。英語の md が残すべき今の指示（1 つずつ照らす）:

束ね役（`judge-verify.md` と `AGG`・`AGG_REPLY`）:

1. 単位を自分で見ない。
2. 下請けのファイルごとに Agent の道具で下請けを 1 つずつ起こす。
3. 下請けの呼びは 1 つのメッセージに全部並べる（同時に走る）。
4. `subagent_type` は全部 `general-purpose`（ほかの型を使わない）。
5. 各下請けへの頼みは「<ファイル> を Read で読み、その指示に従え」の 1 行でよい。
6. 下請けは読むだけで、答えはファイルに書き（どこかはファイルが名指す）、作業ツリーを変えず、最後に 1 行の要約を返す。
7. 答えのファイルは機械が確かめてまとめるので、答えの中身を写さない。
8. 下請けのファイルの一覧（単位ごとと相乗り。絶対パス）。
9. 下請けが全部返ったら、返答は型に合う JSON だけにし、`summary` に下請けの 1 行の要約を並べる。型を示す。
10. 外への検索の決まりの塊の全部（名を出さない・持ち主の名・第三者の名・社内語・名が要る調べは引かない・預かっている所は外でない。今の md:3-10）。今の束ね役への「子への指示に塊を含めよ」は、塊が下請けのファイルに入ることで替わる（2.6）。

下請け（`TITLE`・`SUB_HEAD`・`RULES`・`VIEW_HEAD`・`UNIT_HEAD`・`UNIT_ASK`・`ANSWER_AT`・`SYNERGY_HEAD`・`ALL_UNITS_HEAD`・`SYNERGY_ASK`）:

11. 読むだけ。Read・Grep・Glob で根拠のコードを調べ、Write は最後の節が名指す答えのファイルにだけ。Edit・Bash を使わず、作業ツリーを 1 文字も変えない。
12. 判定役が人の修正依頼を根本の単位に切った。その切り方を判定役とは別の目で確かめる。
13. ほかのファイルの指示書を読みに行かなくてよい（根拠のコードは読む）。
14. 決まり: 直し方は書かない（案は別の役が作る）。
15. 決まり: 単位を消す・足す・ラベルを変える提案はしない。単位は直す義務で、この確かめでは減らない。根本でないと出ても、申し送りとして案を書く役と報告に届くだけ。
16. 決まり: web は根拠のコードで決まらない時だけ。判定の先行例の出典は開き直さない。
17. 決まり: why・evidence は見た事実（パス:行と、そこに在った物）で書く。推測は unsure。
18. 判定者の見立て（`framing`・`one_shot`。字の物だけ。無ければ節ごと無い）。
19. 自分の単位の行だけ（key・label・disposition・reason・origin_analysis・why_chain・prescriptions）。
20. 見ること (1) 根本か: 直せば依頼の症状が消えるか・ほかの単位か単位に無い所の結果（症状の 1 つの現れ）でないか・3 つの語のどれか・not_root なら real_root に本当の根（見つけた所のパスと名と、根と言える理由）・単位どうしの重なりは別の下請けが見る。
21. 見ること (2) 証拠: 判定の理由が言う事実を根拠のコードで確かめたか。確かめた所と見た事。
22. 見ること (3) 場所: key が名指すパスと名が直す所か。違えば正しい場所、合っていれば同じ場所。
23. 答えは型に合う JSON 1 つで、Write でそのファイルに書く（ほかのファイルに書かない）。書いたら最後のメッセージは 1 行だけ（単位の番号と verdict）。型を示す。
24. 相乗り: 1 つの単位の中の確かめは別の下請けがし、この下請けは単位どうしの関わりだけを見る。
25. 相乗り: duplicates（同じ根の別の現れ・同じ直しで閉じる）・relations（place で 2 つ。same＝同じ行・同じ塊を変える、か片方の直しがもう片方の前提〔名・型・呼び方〕を変える。apart＝同じファイル・同じ試験のファイルの別の所〔別の関数・別のクラス・別のクラスに足すテスト〕を触るだけで直しどうしは重ならない。同じファイルだけを理由に same にしない）・order（片方を先に直さないともう片方を直せない・試せない）。
26. 相乗り: 単位は番号で名指す。無ければ空の配列にし、why に見た事と無い理由。単位の全部の行。
27. 相乗り: 答えは型に合う JSON 1 つで、Write でそのファイルに書く。書いたら最後のメッセージは 1 行だけ（重複・関わり・順番の数）。型を示す。

### 7.4 keep-essence の番号

README の 10 節の 12 の仕組みのどれも、この block が担わない。守ること: 単位を消さない（申し送りは義務を変えない）ので、fix の単位ごとの記録（11）と 3 回で諦める単位（4）の数え方に触れない。`test_verification_never_deletes_units` が縛る。

### 7.5 済んだと言える条件（PR ごと。README の 11.2）

- 2 本の筋書きが `archon workflow test` で緑。形の検査（`tests/layers/test_block_shape.py`。`ExistingRulesCase` の E7 を含む）が緑。
- `tests/blocks/verify/` が緑（手元は `WORKS_TESTS=fast` と、触った物を `-k verify` で）。
- 本物の単独の run を 1 回（費用のかかる試しは聞かずに回してよい）: 開いた単位 2 つ以上の判定を `--input judgment=<ファイル>` で渡し、下請けが答えのファイルを書き、申し送りが `checked` になることと、`report` が日本語で出ることを見る。判定の値は例の run の `judgment.json` を使える。
- 審査に、7.3 の 4 通りの並べと 27 項目の照らしを出す。

## 8 未確認

- Agent の道具で起こした `general-purpose` の下請けが、親の node の `allowed_tools`（Write を含む）と sandbox を継ぐか。今の run で下請けが答えのファイルを書けているので今の形で働くが、継ぎ方を源で確かめていない。
- 単位の行の述語 `is_open` を写しで持つ（1.5）。diagnose の設計書が判定の行の形のモジュール（README の 4.1）を `lib/` に足すなら、作る時にそちらを import して写しを持たない。足さないなら組み込みで決める。
- 束ね役の組に外への検索の決まりの塊が入る（2.6）。束ね役は検索しないので害は無いと見たが、指示の大きさが約 1.5 KB 増える。
- 読み手が include されない run の null をどう書くか（1.6）。plan・report・line の設計書で決める。
- `blocks/.shared/schemas/judgment.schema.json` を diagnose が置くか（1.2）。置けば `json(shared:judgment.schema.json)` にする。

## 9 決めた事（作った時）

- 6 節の 1（`materials` を持たない）・4（`tests/layers/scan.py` の `KEEP_CHECKOUT` に `("verify", "judge-verify")` を 1 行足す）・6（`ok` は `status == "ok"`）・7（1 本の md を段落で 4 通りに組む。`.shared` は変えない）は、設計書どおりに作った。6 節の 2・3（plan と diagnose の入力）は読み手の設計書の事で、この block では何も足していない。
- `judgment.schema.json` は `blocks/verify/schemas/` に置いた（`blocks/.shared/schemas/` に同名の形がまだ無いため）。diagnose が共通に置いたら `json(shared:judgment.schema.json)` に替えて、この形を消す。
- 見立て（`framing`・`one_shot`）が両方とも字でない判定は、`view` の段落を偽にし、`{view}` には空の字を渡す。
- `prep.json` の `failed` が真になるのは、port が読めない・指示が組めない・例外の時。開いた単位が 2 つ未満の時は `failed` が偽。
- 作業ツリーの写しが読めない・形が違う時の訳は、写しの読み込みの失敗を `OSError`・`ValueError`・`Reject` で受けて 1 行にする。
- 指示の md は英語で直に置き、日本語の同文の commit と指示の同値の試験は作っていない（第 2 波の決め）。
