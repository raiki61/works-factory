# block の設計書: report（報告を書く）

- 何の話か: run の最後に結末の語を決め、機械の報告を組み、書き手の役が人に向けた本文を書き、初見の読み手が頭だけを読んで確かめる「報告」を、単独で呼べる block `workflows/report/` にする設計。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 今の `workflows/report/` の 7 つの node を、同じ 7 つの node の block にする（facts・write-loop〔write-prep・write・cold-prep・cold・write-accept〕・finish）。入力は今の 30 個（block ごとの返り 13・承認ノードの答え 4・line の値 12 と `start`）から、`sections`（block ごとの `report` の欄を graph が並べた節）・`facts`（結末を決める事実）・`lang` の 3 つにする。報告の節の行は事実を持つ block が組み、report は並べて継ぐだけにする（README の 4.1）。結末の語の 10 語と決める順は report が持ち、どの block の欄が止め・人待ち・残りに当たるかの読み分けは line が `facts` に入れる。指示は 2 本の英語の md（`prompts/write.md`・`prompts/cold.md`）にする。keep-essence の 11（直す単位ごとの記録が報告に届く）は、fix が単位の行を `report` の欄に組み、line が節にして渡し、report が字を変えずに機械の報告と詳細のファイルに載せる形で守る（7 節）。振る舞いは変えない（変わる所は 1.9 の一覧）。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜5 節の名と順をそのまま作る）と、`sections`・`facts` を組む line の設計書の書き手（1.2 の表の「今」と 1.6）。1 波目の PR（README の 11.1）。

この文書の語は README の頭の物を使う（line・始めの記録・今は [materials.md](materials.md) の頭）。ほかに:

- 周: この文書では、断りが無ければ書き手のループの 1 回（`r<n>` のフォルダの n）。run の修正の回り（1 run = 1 周）を言う時は「run の周」と書く。
- 止めの語の頭: `report.REQUEST_BY` は `"request:"`（依頼の側が置いた止め札）、`report.HUMAN_BY` は `"human:"`（人が止めた）、`stopby.WAITING` は人待ちの語の集まり（`lib/stopby.py:108` の `CONFLICT`・`NEEDS_HUMAN`・`REPLAN`・`SPEC_CHANGED`・`TDD_REPEAT`・`UNRESTORED`）。
- 封じ・置き: merge の block が差分を確定して hash を取ること（封じ。`sealed`）と、封じた差分を対象の作業ツリーに当てること（置き。`placed`）。凍結: fix がテストの hash を取り、修正役に書き換えさせないこと（keep-essence の 3）。
- 独立の目（R1〜R4）: 修正に関わっていない AI の見直し。R1 最小性とコメント・R2 独立設計との比べと前提の検算・R3 全体の整合・R4 見えていない範囲（README の 8.4）。
- 段の表・続きの切れ目: line が渡す表 `stages`（前の段の出力のある欄が真なら後の段の出力が在るはず、という行の並び）と、それが守られていない所（`cut`。run が途中で終わった印）。
- 申し出: fix の役が出す食い違いの知らせ（keep-essence の 8）。裁定役が裁き、人に回す物と、案の直しを待つ物がある。

- 機械の報告: report が組む `report.md`。結末・冒頭 3 行・節の全部。書き手の役が読む事実で、詳細のファイルの最後に字のまま付く。
- 人に向けた報告: `report-ai.md`。機械の冒頭 3 行・書き手の返答の頭・語の定義・詳細のファイルを指す 1 行・来歴。
- 詳細のファイル: `report-detail.md`。来歴・言い換えた語・書き手の本文の字のまま・語の定義・機械の報告。
- 書き手の役（write）: 機械の報告と、そこに並ぶファイルを読み、平易な要約と人が決めることと本文を書く AI の役。道具は Read・Grep・Glob・WebSearch・WebFetch。
- 初見の読み手（cold）: 文脈も道具も持たず、人に向けた報告の頭だけを読んで、止まった所と推測した所を返す AI の役。
- 頭: 書き手の本文のうち、最初の見出しより前の要約と、見出しに「人が決めること」を持つ節（`lib/report_roles.py` の `head_of`）。
- 引き継ぎのメモ: 書き手の返答の欄 `handoff`。周ごとに新しい会話で起きる書き手が、次の周の自分へ書く（#589）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/report/`）。結末は `round_limit`。書き手は初見の読み手に 2 回拒まれ（`rejects-report.json` の 2 行。どちらも `kind: cold`）、3 回目に、初見の読み手が通さないまま上限の回で受け取られた（`ai.json` の `not_passed`）。骨組みの値はここから取った。world.md と同じ run。

## 1 block の全体

### 1.1 役

run の結末の語（10 語のどれか）と止めた段の語を、line が渡した事実から決まった順で決める。機械の報告（冒頭 3 行・人が決めること・止めたか・見る所・役が呼んだ道具・graph が渡した節の全部・次の run に引き継ぐ落ちた理由・模型・費用・注意）を組み、次の run の依頼の下書きと前の失敗を書く。結果を名乗れる run では、書き手の役に本文を書かせ、初見の読み手に頭だけを確かめさせ、通らなければ理由を付けて書き直させる（3 回目は通らなくても受け取り、印を付ける）。受け取った本文から人に向けた報告と詳細のファイルを組む。どの段が落ちても、機械の報告を指して返る。

### 1.2 port

入力（YAML の `inputs:`）:

- `sections`（必須）: `json(shared:sections.schema.json): 報告の節の配列 [{title, lines, files?}]。機械の報告に、この並びのまま 1 節ずつ載る。各 block の出力の report の欄を graph が並べた物`。
- `facts`: `json(shared:facts.schema.json): 結末と冒頭 3 行を決める事実のオブジェクト（欄は下の表）。空のオブジェクトは事実が渡されていない（結末は record_invalid）`。既定 `{}`。
- `lang`: `text: 書き手が書く本文の言語。空は依頼の言語`。既定 `""`。

`sections.schema.json`:

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["title", "lines"],
    "properties": {
      "title": {"type": "string", "minLength": 1},
      "lines": {"type": "array", "items": {"type": "string"}},
      "files": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["label", "ref"],
          "properties": {
            "label": {"type": "string", "minLength": 1},
            "ref": {"type": ["object", "string"]}
          }
        }
      }
    }
  }
}
```

- `title`: 節の見出し（`## ` を付けずに）。graph が付ける（block の名でなく、人に向けた日本語の見出し。例「TDD のループの単位ごとの結末」）。
- `lines`: 節の行（日本語）。2 つの空白で始まる行は前の行の内訳で、そのまま載る。ほかの行は頭に `- ` が付く（今の `runreport._bullets`）。
- `files`: 書き手が読むファイル。`ref` は Archon の pointer `{type, run_id, path}` か、ファイルの絶対パスの字。`form` は `ref` の指す先の form（`file`・`json(<名>)`・`jsonl(<名>)`）で、書き手 line が出どころの block の宣言の form を字のまま書く（1 つの欄が種類の違うファイルを中継するので、form は値が運ぶ。#851）。report は口 `ports.carried_file` で行の form で中身を照らして開けたパスにし、節「3. 見る所」に `{label}（{title}）: {パス}` の 1 行で並べる。開けない物は `{label}（{title}）: 開けない（{訳}）` の 1 行にし、注意の節にも同じ訳を 1 行足す（黙って落とさない）。

`facts.schema.json` は下の欄だけを持つオブジェクト（`additionalProperties: false`。どの欄も無くてよく、無い欄は表の既定）。表の「今」は、line がその値を組む元の今の計算（line の設計書がこれを写す）:

- `start_ok`: boolean。既定 false。始めの記録が読めたか。今 `facts.py` の `start_record` が None でないか。
- `problems`: 字の配列。既定 []。結果を名乗れない訳。今 `outcome.record_problems` の 1 つ目の返り（読めない入力・開けないと名乗れない指し札・申し出の控えの読めなさ・知らない答えの語）と、始めの記録の読めなさ。
- `notes`: 字の配列。既定 []。注意（読めなかった物で、結果は名乗れる）。今 `record_problems` の 2 つ目の返り・型つきの成果物の注意・TDD と目の注意・素材の読めなさ（`runreport.build` の `notes`、`lib/runreport.py:1820`）。
- `gates`: `[{at, decision, text}]`。既定 []。承認ノードごとの答え（承認ノードの順）。`at` は承認ノードの名、`decision` は答えの語か null（開かなかった）、`text` は一言。今 `outcome.GATES` の 4 つの答え（`lib/outcome.py:52`）と `node_of`。
- `stops`: `[{at, word}]`。既定 []。止めの語。今 `outcome.stop_reasons`（block の返りの `stop_reason` と line の節の止めの語）。
- `halts`: `[{at, word}]`。既定 []。line が返りの欄から読んだ止め。今 `_line_stop` の後ろの 3 つ（事前審査の往復が進まない `{at: "plan-review", word: stopby.PLAN_CONVERGE}`・計画の諦め `{at: "plan", word: <計画の stop_reason か "give-up">}`・封じと置きの ok でない `{at: <承認ノードの名でなく段の名>, word: "not-ok"}`）。
- `waits`: `{conflicts, conflicts_if_closed, others}`（どれも `[{at, word}]`。既定は 3 つとも []）。人待ち。今 `_waits` の、人に回した申し出（`conflict.asked_rows` が 1 行でも在れば `{at: "fix", word: stopby.CONFLICT}`）・案の直しを待つ申し出（`conflict.waiting_rows` が 1 行でも在れば同じ形。途中で終わっていない run だけ人待ちに数える）・ほか（前提の検算の escalate `{at: "eyes", word: "premise-escalate"}`・R4 の問い `{at: "eyes", word: "r4-ask"}`・承認ノードを開かなかった修正前の問い `{at: "plan-review", word: "ask-human"}`、この順）。
- `cut`: `{at, word}` か null。既定 null。段の表の続きの切れ目（line が段の表 `stages` で決めた所）。今 `cut_at` の `chain-cut` の部分。run の記録で落ちた節（`node-error`）は report が自分で読むので入れない。
- `optional`: 字の配列。既定 []。落ちても受け止める段の宣言（node の id の頭か id。今の line の collect の `optional`）。
- `returned`: 字の配列。既定 []。返りの在る include の id（今 `absorbed_rows` が、返りの在る block の中の落ちを重ねないために見た物）。
- `no_fix`: boolean。既定 false。直す物が無い周（今 `_no_fix`）。
- `left`: `[{where, text, unmeasured}]`。既定 []。fixed を名乗らせない残りの行（今 `residue` から受け止めた落ちの行を除いた物。`unmeasured` は測れていない素材の行か。今 `_is_material_row`）。
- `proved`: boolean。既定 false。最後のテストの ok と green と封じの ok が真か（今 `_proved`）。
- `head`: `{before, stopped, after, notices}`（どれも字の配列。既定 []）。冒頭 1 行目の結末の語の後ろに `。` でつなぐ句。`before` は今の `split_line`・`_pushed_said`、`stopped` は今の `_stopped_why`（止まった結末の時だけ使う）、`after` は今の `_ran_notes`・`suitewrite.head_note`・`userenv.NOTE`。`notices` は冒頭の下に 1 行ずつ載る起こす前の注意（今の line の `notices`）。
- `asks`: `[{kind, text, title?}]`。既定 []。`title` は決める中身を言う短い平易な題で、本文を書いた所が一緒に書く（#812。AI の役が本文を書く項目はその役の返りの形に題の欄を持ち、機械が組む項目は組むコードが決まった字で出す）。無い（古い記録・題を返さなかった役）時は種の名に戻す。人が決める物のうち、結末に依らない物（今 `_decisions` の `asks` から、種 `report.CHECKS_LEFT`・「直しきれずに残った物」・「記録が通らないこと」の 3 つを除いた物。問いの種の推しの尾は付けた後の字）。
- `tallied`: `{<種>: 整数}`。既定 {}。行の数でなく全件の数で数える種（今の `tallied`。守りのパスに当たった差分）。
- `counted_left`: 字の配列。既定 []。結末が round_limit の時に「直しきれずに残った物」から外す `where`（今 `counted_units`。直す義務に戻せなかった単位）。
- `decisions`: `{before, after, outside}`（どれも字の配列。既定 []）。節「1. 人が決めること」の line の行。`before` は今の `_pushed_lines`・`unrestored_lines`・`backed_out_lines` と、`_decisions` の行のうち問いと種の塊（結末に依らない種だけ）、`after` は `_decisions` の残りの行（保留の答え方の行から後の全部）、`outside` は目的の外の所見の件数の行（今 `_outside` の 3 つ目。次の run の依頼の下書きのファイルの名を持たない字にする）。
- `apply`: `{sealed, placed, redesign, said, pr, commits}`。既定 `{sealed: false, placed: false, redesign: "", said: "", pr: null, commits: []}`。`sealed`・`placed` は今 `_seal_state`、`redesign` は R2 が作り直しが要ると言った時のその語（今 `seal.REDESIGN`。言わなければ空）、`said` は止まった run の人の一言（今 `_apply_lines` の `said`。無ければ空）、`pr` は出口の語 pr の run の `{act, url, number, is_draft, reason}`（今 `applied-diff` の `deliver`）か null、`commits` は今 `_pr_commit_lines` の行。
- `carry`: `{findings, prior, drafts, constraints}`（どれもオブジェクトの配列。既定 []）。次の run に渡す物。今 `runreport.next_request`・`prior_failures`・`answer_drafts`・`carry.carried_constraints` の返り。
- `stop_lines`: `{before, after}`（字の配列。既定 []）。節「2. 止めたか」の line の行。`before` は今 `_stop_lines` の line の止めの語の行・承認ノードの行・封じと置きの ok でない行、`after` は続きの切れ目の行（`chain_notes`）。
- `outcome_parts`: `{gate, eyes, data}`（字。既定 ""）。節「模型」の結末の行の句。今 `_outcome_line` の最後の承認ノードの句・独立の目の句・`data_places`。
- `round`: 整数か null。既定 null。計画の何回目の案か（今 `outcome.planned(returns).round`）。
- `line_rev`: 字。既定 ""。メイングラフの版（今 `versions.line_rev(start.versions)`）。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。結末が `fixed`・`fixed_needs_check`・`no_fix_needed` のどれか（今 `outcome.OK_OUTCOMES`）。
- `outcome`: 10 語のどれか（`fixed`・`fixed_needs_check`・`no_fix_needed`・`round_limit`・`stopped_by_request`・`stopped_by_human`・`stopped_by_line`・`needs_human`・`record_invalid`・`interrupted`）。enum は `lib/report.py` の `OUTCOMES` と同じ並び。
- `stop_reason`: `<段>:<語>` か空。
- `machine`: 機械の報告の pointer（いつも在る。組めなかった時は訳だけのファイル）。
- `human`: 人に向けた報告の pointer か null（書き手のループが飛ばされた・落ちた）。
- `detail`: 詳細のファイルの pointer か null（`human` と同じ時に在る）。
- `next_request`: 次の run の依頼の下書きの pointer（form は `json(lib:next-request.schema.json)`）か null（渡す物が 0 件）。
- `prior_failures`: 前の失敗の pointer（form は `json(lib:prior-failures.schema.json)`）か null（0 件）。
- `report`: 日本語の行の配列（README の 4.1）。`結末: <平易な言い方>（<語>）`・`人に向けた報告: <パス>`（無ければ `人に向けた報告: 無い（<訳>）`）・`機械の報告: <パス>` の 3 行。

今との違い:

- 入力: 今は block の返り 13 個（`before-tests`〜`applied-diff`）・承認ノードの答え 4 個・line の値 12 個（`stops`・`stages`・`optional`・`user-env-dir` など）と `start` を受け、`lib/runreport.py` が lib の 43 モジュールを import して、block ごとの返りの欄から節の行と結末を組んだ。新しい形では、節の行は作り手の block が `report` の欄で組み（1.6）、結末の読み分けは line が `facts` に入れる。
- 出力: 今の `report`（機械の報告の pointer）・`report_ai`（人に向けた報告の pointer）は、`machine`・`human` に名を替えた。欄 `report` は README の 4.1 と 7.1 の 8 が全部の block に求める「報告の行」にした（自分で決めた。9 節）。`detail` は足した（今も書いていたが返していなかった）。
- 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）は読まない（今の facts の `listing`。TDD の単位の行と緑の認証と独立の目の判定は、作り手の block の `report` の欄で届く）。
- 始めの記録は読まない（今の facts の `start_record`。要る事実は `facts` の欄で届く）。

### 1.3 node の並び（`workflows/report/works-factory-report.yaml`）

1. `facts`（script `facts.py`）: port を読み、run の記録を読み、結末を決め、機械の報告・次の run の依頼の下書き・前の失敗を書く。`facts.json` に書き手の段の値を置く。返り `{outcome, ok, stop_reason, machine, next_request, prior_failures, ai_go, stamp}`。0 以外で終わらない（4 節の 3 段の受け皿）。
2. `write-loop`（`loop_group`、最大 3 回、`fresh_context: true`、`until_bash: done=$write-accept.output.done; test "$done" = true`、`depends_on: [facts]`、`when: "$facts.output.ai_go == 'true'"`）
   - `write-prep`（script `write_prep.py`）: 機械の報告の冒頭から、resume の前に finish が置いた「本文は無い」の行を外し、書き手の指示を組む。返り `{prompt}`。
   - `write`（AI）: `prompt: "$write-prep.output.prompt"`・`depends_on: [write-prep]`・`model: '@wf-report'`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま（2.4）。
   - `cold-prep`（script `cold_prep.py`。`depends_on: [write]`・`with: {writer: $write.output}`）: 初見の読み手の指示を組む。返り `{prompt}`。
   - `cold`（AI）: `prompt: "$cold-prep.output.prompt"`・`depends_on: [cold-prep]`・`context: fresh`・`model: '@wf-report'`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま（3.4）。
   - `write-accept`（script `write_accept.py`。`depends_on: [write, cold]`・`with: {reply: $write.output, cold: $cold.output}`）: 返り `{done, ok, reason, kind, prev_file}`。
3. `finish`（script `finish.py`。`depends_on: [facts, write-loop]`・`trigger_rule: all_done`）: 書き手のループが落ちた訳を機械の報告の冒頭に置き（resume で書き直した run では外す）、人に向けた報告と詳細のファイルを書き、出力を返す。落ちない。

node の名の今との違い: `write-reject` → `write-prep`（指示を組む node。README の頭の語の prep）、`accept` → `write-accept`、`report` → `finish`（出力の欄 `report` と node の id を分けた）。script の名 `facts`・`write_prep`・`cold_prep`・`write_accept`・`finish` は `lib/` のモジュールの名と重ならない（今の `report_accept`・`collect`・`reject` は使わない）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/<line の include の id>/`。line の include の id を今と同じ `report` にすれば、今と同じ `$ARTIFACTS_DIR/report/`）の下に書く。名は `src/files.py` だけが持つ:

- `facts.json`: facts が決めた値 `{outcome, stop_reason, ok, ai_go, stamp, lang, run_id, decisions}`（`decisions` は人が決める物の件数）。
- `report.md`: 機械の報告。`report-unwritten.md`: 組めなかった時の機械の報告。`report-facts-unwritten.md`・`report-finish-unwritten.md`: lib を読めない時の訳だけのファイル（今の `LIBLESS` の 2 つ。今の名 `report-collect-unwritten.md` は finish の名に替えた）。
- `next-request.json`・`prior-failures.json`（`carry.NEXT_REQUEST_FILE`・`carry.PRIOR_FAILURES_FILE` の字。chain と次の run の入口が読む今の名のまま）。
- `write-prompt-<n>.md`・`cold-prompt-<n>.md`（`<n>` は `rolekit.attempt(place, "report")`）。
- `rejects-report.json`・`rejects-report.md`・`candidate-report.json`（rolekit の控え。受け付けの名は今と同じ `report`）。
- `r<n>/handoff.json`（周ごとの引き継ぎのメモ。今と同じ）。
- `ai.json`（受けた書き手の返答と初見の読み手の判定）・`report-ai.md`・`report-detail.md`。

### 1.5 コードの置き場

- `workflows/report/src/__init__.py`（空）。
- `workflows/report/src/files.py`: 1.4 の名の定数と、機械の報告の report の見出し（`TITLE = "# 報告（run {run}）"`・`DECISIONS_HEADING = "## 1. 人が決めること"`・`STOP_HEADING = "## 2. 止めたか"`・`WHERE_HEADING = "## 3. 見る所"`・`CALLS_HEADING = "## 4. 役が呼んだ道具"`・`PRIOR_HEADING = "## 次の run に引き継ぐ落ちた理由"`・`MODEL_HEADING = "## 模型"`・`COST_HEADING = "## 費用"`・`NOTES_HEADING = "## 注意（読めなかった物）"`）。今の `lib/report.py` と `lib/runreport.py` の `promptsection.Section` の見出しを字にした物（`promptsection` は README の 9.1 で消す）。
- `workflows/report/src/facts_in.py`: `facts` の port の値を、1.2 の表の既定を埋めた dict にする `read(value) -> dict`。形の違う欄は `ValueError`（訳を名指す。黙って既定にしない）。
- `workflows/report/src/outcome.py`: 結末の決め `decide(facts, run) -> (outcome, stop_reason)`（1.7）・残りの行 `left_all(facts, run)`・結末で決まる人が決める物 `outcome_asks(outcome, facts, left)`。写す元 `lib/outcome.py` の `decide_outcome`・`_human_stop`・`_line_stop`・`_waits`・`cut_at`・`absorbed_rows`（`:312-535`）。返りの欄を読む所は line へ行くので写さず、`facts` の欄を読む形に書き直す。
- `workflows/report/src/transcript.py`: Archon の run の記録（`$LOG_DIR/<WORKFLOW_ID>.jsonl`）を読む `read() -> (rows, why)`（今 `boundary.transcript`、`workflows/.shared/boundary.py:299-315`）・`own_prefix()`（自分の include の頭。今 `boundary.own_prefix`、`:254-263`。`ports` に同じ口が在ればそれを呼ぶ）・`facts(rows, *, exclude_prefix, optional)`（写す元 `lib/runreport.py` の `transcript_facts`・`_declared`・`_resubmit`・`_count_call`、`:247-347`）・`cost_rows`・`resubmit_rows`・`head_cost`（`:350-388`）と、足す `token_rows(run)`（トークンの行。1.8 の 11。`facts` の返りの `tokens`・`untokened` を読む）・`node_model_lines(run)`（`_model_lines` の node ごとの行の部分、`:411-423`）・`calls_lines(run, why, repo)`（`_reads_lines` の run の記録の道具の呼びの部分と `UNSEEN`・`CHILD_RUNS` の行、`:1727-1757`・`:1779-1786`。フックの証拠のファイルを読む部分は写さない）・`writer_fell(rows, step)`（`:2081-2093`）。
- `workflows/report/src/machine.py`: 機械の報告を組む `build(sections, facts, outcome, stop_reason, run, *, place, run_id, run_why, repo) -> dict`（1.8）と `fallback_report(place, why)`。写す元 `runreport.build`（`:1789-1881`）の組み立ての順・`head_lines`（`:1242-1249`）・`ask_counts`（`:1237-1239`）・`_apply_lines`（`:1295-1311`）・`apply_said`・`_apply_answer`（`:1327-1355`）・`_gate_line`（`:1685-1689`）・`_bullets`（`:1722-1724`）・`fallback_report`（`:1893-1898`）。下書きの行は `gatemarks.draft_line` と `DRAFT_HEAD`（`lib/gatemarks.py:1095`・`:1136-1143`）を写す。次の依頼と前の失敗の書き込みは今の `:1866-1880`（`carry.compose`・`carry.errors`・`carry.write`）。
- `workflows/report/src/writer.py`: 書き手のループと出口。写す元 `runreport` の `pack_terms`・`_term_pattern`・`plain_words`・`swapped_line`・`glossary_section`（`:852-928`）・`_parse`・`_cold_of`・`_cold_lines`・`_cold_facts`・`_cold_reason`・`machine_head`・`cold_body`（`:1902-1964`）・`_refused`・`_reject_count`・`_give_up`・`_carry_rejected`・`_prior_rounds`・`accept`（`:1967-2078`）・`note_writer_fell`（`:2096-2109`）・`stamp`（`:2112-2127`）・`embedded`・`_not_passed_note`・`line_budget`・`_cut`・`_fences`・`collect`（`:2130-2211`）と、`lib/report_roles.py` の全部（`DECISIONS_HEAD`・`NOT_PASSED`・`TERM_SCHEMA`・`TEXT_SCHEMA`・`MACHINE_HEADING`・`CELL_LIMIT`・`REJECT_KINDS`・`UNKNOWN_KIND`・`COLD_REJECTS_LINE`・`FAILED_TITLE`・`GLOSSARY_HEADING`・`CELL_REASON`・`_terms_problems`・`head_of`・`format_problems`・`count_rejects`）。`handoff_part`（`:2014-2019`）は、頼みの文と使い方の文を md へ移し、前の周のメモのパスの行だけを組む `handoff_rounds(place) -> str` にする（2.3 の 11）。`stamp` は始めの記録の代わりに `round`・`line_rev`・`start_ok` を受ける（1.9）。
- `workflows/report/src/glossary.json`: `lib/glossary.json` を字のまま写す（README の 9.2 の MOVE）。`pack_terms` はこのファイルを読む。
- `workflows/.shared/schemas/sections.schema.json`・`facts.schema.json`（1.2。書き手の line と読み手の report が同じ共通の形を名指す。#851）。
- 使う `lib/`（KEEP）: `report`（`OUTCOMES`・`OUTCOME_WORDS`・`REQUEST_BY`・`HUMAN_BY`・`CHECKS_LEFT`・`ABSORBED_WHERE`・`INTERRUPTED_HEAD`・`RETRIED_HEAD`・`ABSORBED_HEAD`・`_first_error`・`_time`・`prior_lines`）・`answer`（`STOP_WORDS`・`resume`）・`stopby`（`is_line`・`WAITING`）・`carry`（`compose`・`errors`・`write`・`NEXT_REQUEST_FILE`・`PRIOR_FAILURES_FILE`・`NEXT_SCHEMA`・`PRIOR_SCHEMA`）・`handoff`（`FIELD`・`SCHEMA`・`save`・`unreadable`・`path_of`。文の定数 `ASK`・`HEAD`・`USE`・`NONE`・`UNREADABLE` は使わない）・`rolekit`（受け付けの回・控え・諦め・`candidate_path`・`reject_file_or_blank`）・`jsonfile`・`oneline`・`graphloops/engine/schema.py`（`validate_schema`）。`lib/runreport.py`・`lib/outcome.py`・`lib/report_roles.py` は import しない（写して置く。README の 9.2 の MOVE と、9.3 の「runreport は block の中身を import しない形に軽くする」）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line（組み込みの後の `workflows/line/`）: 最後に `include: works-factory-report` を置く（id `report`、`trigger_rule: all_done`）。その前の script の node（今の `collect` の後継）が、各 block の出力を受けて `sections` と `facts` を組み、place にファイルとして書いて pointer を `with:` で渡す（README の 4.2 の「欄を 3 つ以上読む時は pointer 1 つ」）。`lang` は始めの記録の `lang`。
- `sections` の並びは今の機械の報告の節の並びに合わせる（line の設計書が決める）。今の節と、新しい形でその行を組む作り手:
  - 「2. 入口・段・決めた人」（今 `_entry_lines`・`_depth_lines`・`_head_depth_line`・`_prior_in_lines`・`_policy_lines`・凍結の行）→ line。ただし run の頭の深さの行（今 `_head_depth_line`）の段と根拠は head-depth の `report`、省く物・足した物は line が組む（head-depth の設計書の 8 節の 3）。
  - 「4. 読んだ証拠と包み」のうち、フックの記録の行（今 `_reads_lines` の `HOOK_HEAD` の下。`reads-*.json` を run directory から探した物）→ 読んだ証拠の node を持つ block（今 `lib/reads.py` を使う fix・plan・plan-review・parallel-pr）が自分の `report` の欄に組む。run の記録の道具の呼びの行は report が組む（節「4. 役が呼んだ道具」）。
  - 「TDD のループの単位ごとの結末」（今 `_tdd_lines`。型つきの成果物 `tdd-unit` から）→ fix（2 度目の修正は別の節。今の `report.TDD_STAGES`）。keep-essence の 11（7 節）。
  - 「緑の認証（全部の周）」（今 `_green_lines`）→ test-gate。
  - 「独立の目」（今 `_eye_lines`）→ r1〜r4 と eyes のまとめ。r1 の行は、今の書き手の指示の構成 5 が読ませていた「削ったコメント（`r1.json` の `deletions` の `where` と `why`）」と「残した why（`r1-comments.json` の `kept` の `where` と `fact`）」を 1 件 1 行で含む（書き手の md がほかの block のファイルの名を持たない形にしたため。2.6）。
  - 「構造の目」（今 `_structure_lines`）→ structure（after）。
  - 「世界の解」（今 `_world_lines`）→ world（world.md の 1.2 の `report`）。
  - 「未確認のレンズ」（今 `_unseen_lens_lines`）→ local-review（素材の観点）。素材の観点の族は `report` の配列を 1 つだけ返すので、見ていないレンズの行は local-review の `report` の、素材の 1 行の後ろに入る（local-review の設計書の 1.6）。この行を独り立ちの節にするか、修正の後のレンズの行（今の `fixbeside.lens_lines`）と並べるかは、`sections` を組む line が決める。
  - 「判定が目的の外とした所見」（今 `_outside` の 2 つ目）→ diagnose。
  - 「模型」の群ごとの選びの行（今 `headdepth.groups_lines`）→ head-depth の `report` には入れない。ノードごとの実際の模型の事実と並ぶ節なので、head-depth の出力 `record` の pointer から KEEP の `headdepth.groups_lines` で組む（head-depth の設計書の 8 節の 3）。line が組んで `sections` に入れるか、report が受けて組むかは line の設計書で決める。
- 節「3. 見る所」の元（今の `POINTERS`、`lib/runreport.py:181-188` の 18 個）は、line が各節の `files` に入れる（判定・目的・定石・仕様・目的の外の所見・計画・構造の目・波及・事前審査・独立設計・差分・申し出と裁定・直す前の結末・試験の記録 2 つ・直した後の構造・封じた差分・置いた差分）。
- `facts` は 1.2 の表の「今」の計算を line の `src/` が持つ（承認ノードの答え・止めの語・段の表・無人の方針は line の持ち物。README の 1.2 の U・D）。
- 読み手: 周の鎖 chain（line を子の run として回す親のグラフ。`outcome`〔結末の語〕・`next_request`〔次の周の依頼の pointer〕を、line の返りの欄を通して読む。今と同じ）。line の返りの欄 `report`・`report_ai` は、組み込みで `machine`・`human` を写す（`bin/` は報告を読まない）。`detail`・`report` は line の返りの欄 `report_detail`・`report_lines` に写す（line の設計書の 1.2）。
- e2e の照らしの表 `tests/e2e/evidence.json` の行のうち `where` が `parent/report/report.md`・`report-ai.md`・`next-request.json` の物は、line の include の id を `report` にすれば置き場の字はそのまま。`writer` の欄（`lib/runreport.py::_decisions` など）は、その行を組む作り手の block の関数の名に替える（組み込みの時）。

### 1.7 結末の決め（`src/outcome.py` の `decide`）

`run` は `transcript.facts` の返り（run の記録が読めなければ `ok: False` で、`failed`・`absorbed` は空）。上から順に、最初に当たった物を返す（今の `decide_outcome` の順。`lib/outcome.py:493-535` の docstring の 1〜8）。

1. 人の止め: `gates` の行の `decision` が `answer.STOP_WORDS` のどれかなら、`text` が `report.REQUEST_BY` で始まれば `stopped_by_request`、ほかは `stopped_by_human`。止めの語は `f"{at}:{decision}"`。次に `stops` の行の `word` が `REQUEST_BY` で始まれば `stopped_by_request`、`report.HUMAN_BY` で始まれば `stopped_by_human`（`f"{at}:{word}"`）。
2. 線の止め: `stops` の行の `word` が `stopby.is_line(word)` で `stopby.WAITING` に無ければ `stopped_by_line`。無ければ `halts` の最初の行で `stopped_by_line`。
3. 切れ目 `cut`: `run.failed` が空でなければ `f"{run.failed[0]}:node-error"`、空で `facts.cut` が在れば `f"{cut.at}:{cut.word}"`、どちらも無ければ空。
4. 人待ち: `waits.conflicts` → `cut` が空なら `waits.conflicts_if_closed` → `stops` のうち `word` が `stopby.WAITING` に在る行 → `waits.others`、の順の最初の行で `needs_human`（`f"{at}:{word}"`）。
5. 記録が通らない: `start_ok` が偽なら `("record_invalid", "start:record-invalid")`、`problems` が空でなければ `("record_invalid", "report:record-invalid")`。
6. 途中で終わった: `cut` が空でなければ `("interrupted", cut)`。
7. 残り `left_all` = `facts.left` に、受け止めた落ちの行を足した物。受け止めた落ちの行は、`run.absorbed` の行のうち、`node` の include の頭（最初の `__` より前。無ければ空）が `facts.returned` に無い物ごとに `{where: f"{report.ABSORBED_WHERE} {node}", text: f"{node} が落ちた（誤り: {report._first_error(a)}）——メイングラフは受け止めて先へ進んだが、その段の結果は確かめていない（再実行の要あり）", unmeasured: False}`（今 `absorbed_rows` の字）。
8. `no_fix` が真で `left_all` が空なら `("no_fix_needed", "")`。
9. `left_all` が空でなく、全部の行の `unmeasured` が真で、`proved` が真なら `("fixed_needs_check", "")`。
10. `left_all` が空でないか、`proved` が偽なら `("round_limit", "")`。
11. ほかは `("fixed", "")`。

結末で決まる人が決める物（`outcome_asks`。`facts.asks` の後ろに足す。今 `_decisions` の parts の後ろ 3 つと同じ順）:

- `fixed_needs_check`: 種 `report.CHECKS_LEFT`、`left_all` の行ごとに `f"{where}: {text}"`。
- `round_limit`: 種「直しきれずに残った物」、`left_all` のうち `where` が `counted_left` に無い行ごとに `f"{where}: {text}"`。
- `record_invalid`: 種「記録が通らないこと」、1 件 `"record_invalid"`。

### 1.8 機械の報告の形（`src/machine.py` の `build`）

`run_id` は環境の `WORKFLOW_ID`（単独の run では自分の run、include された時は line の run）。上から:

1. `# 報告（run {run_id}）` と空行。
2. 冒頭の行（今 `head_lines`。#812 で、初見の読み手が止まる 5 つの型を直した形）:
   - `起きたこと: ` + `"。".join([report.OUTCOME_WORDS[outcome], 人が決める物が在れば f"人が決めること {和} 件が残っている"])`。`STOP_OUTCOMES` は `stopped_by_request`・`stopped_by_human`・`stopped_by_line`・`needs_human`（今 `runreport.STOP_OUTCOMES`）。`head.before`・`head.stopped` の字は頭に出さず（頭の読み手は頭しか読まないので、頭の外の節を指す句も置かない）、5 節の先頭（`stop_lines.before` の前）に置く（承認ノードの名・推しの件数・開けた理由は工場の内側の言葉で、頭の読み手には要らない）。
   - `差分を当ててよいか: ` + `apply_said`（今 `apply_said`・`_apply_answer` を `apply` の欄で書き直した物。今の `_seal_state` は `apply.sealed`・`apply.placed`、`eyes.r2.status == seal.REDESIGN` は `apply.redesign` が空でないか、文の中の語は `apply.redesign` を `seal.STATUS_WORDS` で言い換えた字（「作り直しが要る」）。人が決める物の件数は下の `counts` の和）。
   - 頭に結末の英字の語（`needs_human` など）・「封じ」・R2 などの内側の名は出さない（`差分を当ててよいか` の行は「当てる差分が無い（この run は差分を確定していない）」と言い、`bin/apply` は同じ行で「保存した差分を対象に当てる命令」と言い、`--allow-stopped` は「止まった run の差分を当てる指定」と言う）。
   - `急ぎ: ` + `urgent_said`。機械が持つ事実だけで書く: run の記録が読めて落ちたノード（`failed`・`absorbed`）が在れば「壊れた所がある」、結末が `record_invalid`・`interrupted` でも同じ、どちらでもなければ「急ぎでない——壊れた所は無く、…」と言い、後ろの句は `apply.pr`（出口の語 pr の道の渡しの結果）で選ぶ: `pr.act` が `pr` なら「PR を作っただけで、対象の既定の枝には当てていない」、`stopped` なら「PR は作らず、対象の既定の枝には当てていない」、`unconfirmed` なら「PR を作ったかは確かめられていないが、対象の既定の枝には当てていない」、`pr` が無ければ「対象のリポジトリには何も当てていない」（run は対象に差分を当てず、差分は `bin/apply` か出口の語 pr の道が対象に渡す。E17）。run の記録が読めない時は事実が無いので行を出さない（推して書かない）。
   - 人が決める物（`asks` = `facts.asks` + `outcome_asks`）が在れば `人が決めること: {和} 件（下の行は種類ごと。1 件ずつの本文は見出しに「人が決めること」を持つセクション）`、無ければ `次の run に渡す物: {carried} 件`（`carried` = `carry.findings`・`drafts`・`constraints` の数の和）。数は和の 1 つだけを頭に出す（1 つの決めには 1 つの数）。種ごとの件数は `ask_counts`（`tallied` に在る種はその数。種の名は括弧の前の頭の言い方で、同じ頭の種は合わせる）。
   - その下に 1 行ずつ: 題（`asks[].title`）が在る物は 1 件 1 行 `- {題}（{種の頭の言い方}）`、題の無い物は種ごとにまとめて `- {種の頭の言い方}`（2 件以上なら `（{n} 件）`。黙って行を落とさない）。決める物の本文は頭に出さず、4 節の `## 1. 人が決めること` に在る。
   - 最後に `head.after` を 1 行ずつ `知らせ（決めることではない）: {行}`。
3. `head.notices` が在れば、空行の後に 1 行ずつ。
4. `## 1. 人が決めること`: `decisions.before` → 結末で決まる人が決める物の塊（種ごとに `{kind}: {n} 件` と `  - {text}`）→ `decisions.after` → `次の run に渡す物: {carried} 件` に、書いた時だけ `（next-request.json）` → `decisions.outside` → 前提の検算の制約の行（`carry.constraints` ごとに `次の run の制約に足す実測（前提の検算）: {text}`）→ 下書きの行（`draft_line(carry.drafts, next_file)`。下書きが無ければ出さない）→ 差分を当てる行（今 `_apply_lines`）→ `apply.commits`。
5. `## 2. 止めたか`: `結末: {平易な言い方}（{outcome}）`・`止めた段と理由の語: {stop_reason か「止めていない」}` → `head.before`・（止まった結末の）`head.stopped` → `stop_lines.before` → run の記録が読めれば、`run.failed` ごとに `{report.INTERRUPTED_HEAD}: ノード {s} が落ちた（誤り: …）`、`run.retried` ごとに `{report.RETRIED_HEAD}: …`、`run.absorbed` ごとに `{report.ABSORBED_HEAD}: …`（今 `_stop_lines` の字）→ 落ちた node の誤りが fan_out の子の run の名乗り（`child N (run <id の先頭 8 字>)`）を持てば、子の run の記録（親の記録と同じ置き場の `<子の run の id>.jsonl`）の落ちた node ごとに `子の run {先頭 8 字} のノード {node} が落ちた（誤り: …）`、記録が読めなければ `子の run {先頭 8 字} の記録が読めない（…）`（Archon が親の node の誤りに書くのは子の失敗の総括だけで、provider の 429 などの訳は子の記録にだけ在る。`transcript.child_falls`）→ `stop_lines.after` → `problems` ごとに `結果を名乗れない訳: {p}`。
6. `## 3. 見る所`: `sections` の `files` を節の順に `{label}（{title}）: {パス}`。1 つも無ければ `出力にポインタが無い`（今の字）。
7. `## 4. 役が呼んだ道具`: `transcript.calls_lines`。今の `CHILD_RUNS`「fix の組の子の run の道具の呼びは…」は「子の run の道具の呼びは子の run の記録に在り、上のノードごとの行に入らない」にする（block の名を持たない字）。`CHILD_LOOPS` も同じく「子の run のループの回り直しは子の run の記録に在り、この行に入らない」にする。
8. `sections` を並びのまま 1 節ずつ: `## {title}` と、行に `_bullets` を当てた物。`lines` が空の節は `- この段は報告の行を返していない` の 1 行を置く（自分で決めた。9 節）。
9. `## 次の run に引き継ぐ落ちた理由`: `report.prior_lines(carry.prior, next_file)`。
10. `## 模型`: `transcript.node_model_lines(run)` と結末の行 `"／".join([f"結末: {平易な言い方}（{outcome}）", outcome_parts.gate, outcome_parts.eyes, f"次の run に渡す物: {carried} 件", f"持ち越した失敗: {len(carry.prior)} 件", outcome_parts.data])`（空の句は飛ばす）。
11. `## 費用`: `transcript.head_cost(run, run_why)`。費用の合計・node ごとの費用と時間の行（`cost_rows`）の後に、トークンの行（`token_rows`）が続き、回り直しの行（`resubmit_rows`）で終わる。トークンの行は、合計の行（「トークンの合計: 入力 N（うちキャッシュの読み R・書き W・キャッシュ外 U）・出力 O」。`入力` は Archon の `spend.tokens.input` で `cacheRead`・`cacheWrite` を含む総量なので足し直さず、`U = N − R − W`）と node ごとの同じ形の行。記録の無い node は「トークンの記録なし（記録の無い行 n 件）」、cacheRead・cacheWrite の欠けた起動か `cachePartial` の起動が在る所は「キャッシュの内訳が不明な起動 n 件」を言ってキャッシュ外を出さない。数えるのは費用と同じく自分の費用を言う行（`accounting: node`）だけで、言い直しの行（`aggregate`）は数えない。
12. `## 注意（読めなかった物）`: `facts.notes` と 6 の開けない `files` の訳と run の記録の読めなさ。無ければ `無い`。

節 4〜12 の行には `_bullets` で頭の `- ` を付ける（今の `build`）。節と節の間は空行 1 つ。最後に改行。`carry` を書く時、次の依頼は `carry.compose(findings, prior, drafts, constraints)` を `carry.errors(doc, carry.NEXT_SCHEMA)` で、前の失敗は `carry.errors(prior, carry.PRIOR_SCHEMA)` で照らし、2 つとも照らしてから書く（合わなければ `ValueError`。facts の受け皿が `record_invalid` にする。今の `:1866-1880`）。

### 1.9 振る舞いの変わる所（今との違いの全部）

- 機械の報告の節の番号: 今の「1. 人が決めること」「2. 入口・段・決めた人」「3. 止めたか」「4. 読んだ証拠と包み」「5. 見る所」は、report が持つ「1. 人が決めること」「2. 止めたか」「3. 見る所」「4. 役が呼んだ道具」と、graph が見出しを付ける節（「入口・段・決めた人」など。番号なし）になる。書き手の md の節の名指しも合わせる（2.6）。
- 節「4」のフックの記録の行は、作り手の block の節へ移る（1.6）。
- 「見る所」の行の尾が `（{段}.{欄}）` から `（{節の見出し}）` になる。
- 来歴の行の「メイングラフの版 始めの記録に無い（versions.line）」は「メイングラフの版 始めの記録に無い」になる（`versions` は line の持ち物）。
- 目的の外の所見の件数の行は、次の run の依頼の下書きのファイルの名を持たない（line が組むため）。
- 行の無い節を黙って落とさず、1 行を置く（9 節）。
- 拒みの数え（`ai.json` の `rejects`）は節 `report` の 1 つだけになる（今の `report.human_items`・`report.cold_check` の行は 2026-10-09 から常に 0）。
- 思わぬ誤りの時の機械の報告（`report-unwritten.md`）の冒頭に、利用者の環境で走らせた印の句が載らない（今は `INPUTS_USER_ENV_DIR` を読んだ。新しい形では `facts.head.after` が言うので、`facts` も読めない時は言えない）。

## 2 node の設計シート: write（書き手の役）

### 2.1 役

機械の報告と、そこに並ぶファイルを読み、冒頭 3 行の直後に置く平易な要約・人が決めること・本文を書く。周ごとに新しい会話で起き、前の周の自分のメモと前の答えを読み直して書き直す。

### 2.2 port

`facts.json`（← facts。`outcome`・`stop_reason`）・機械の報告 `report.md` のパス（← facts）・拒否の控えと前の答えの控え（← write-accept が place に積んだ物）・前の周の引き継ぎのメモ（← write-accept が `r<n>/` に置いた物）・`lang`（← port `lang`）。

### 2.3 組み立ての順（`prompts/write.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-report.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "report"))`（拒否の文の全部、古い順。初見の読み手の止まった所と推測した所を含む日本語の文。5 節）。
2. 役の段落（決まった文）: 新しい会話で起きていること・何を書くか・冒頭 3 行は機械が組むこと。
3. 結末の 1 文: `{outcome}` ← `facts.json` の `outcome`、`{stop_reason}` ← `stop_reason`（空なら空の字のまま。今と同じ）。
4. 手順 1（決まった文）と `{facts_file}` ← 機械の報告の絶対パス、`{where_heading}` ← `files.WHERE_HEADING` の `## ` を外した字（「3. 見る所」）。
5. 手順 2（決まった文）と `{stop_heading}` ← 「2. 止めたか」。
6. `<!-- if prev -->` 手順 3（前の答えを読み直す）と `{prev_file}` ← 前の答えの控え（`rolekit.candidate_path(place, "report")`）の絶対パス `<!-- end prev -->` — 条件: 拒否が 1 件以上で、前の答えの控えが在り、諦めていない（今の `runreport.accept` の返りの `prev_file` の決まり）。
7. 手順 4〜6（決まった文）と `{decisions_head}` ← `report_roles.DECISIONS_HEAD`（「人が決めること」。`head_of` が見出しを探す字と同じ字）。
8. `## Outline`（決まった文）と `{lang}` ← port `lang`（空なら `"the language of the request (the user's language)"`）、`{decisions_heading}` ← 「1. 人が決めること」、`{stop_heading}`。
9. `## Format rules`（決まった文）と `{decisions_head}`、`{cell_limit}` ← `report_roles.CELL_LIMIT`（50）。
10. 返す形の段（決まった文）。
11. `{shared:handoff}`（引き継ぎのメモの頼みと、前の周のメモの節）。断片の中の `<!-- if handoff_rounds -->` — 条件: 今の回の前の周が 1 つ以上（`rolekit.attempt(place, "report") > 1`）。`{handoff_rounds}` ← `writer.handoff_rounds(place)`（1 周 1 行 `- r<k>: <パス>`。メモの無い周は `- r<k>: (no notes)`、読めない周は `- r<k>: (unreadable)`）。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the writer of the final report, started in a new conversation. Read the record of this run and write the body of the report: the plain summary and the section on what a person decides, which come right after the first 3 lines, and the body after them. The first 3 lines (what happened, whether the diff may be applied, what a person decides, with one line per item under it) are built by the machine from the record and placed before your body.

The outcome word of this run is **{outcome}** (the stage that stopped it and the reason word: `{stop_reason}`). The machine decided it. Do not rewrite it.

1. First, Read the machine's facts file `{facts_file}`. It is the report the machine built from the outputs of the stages and the run record: the outcome, the stage that stopped, the number of things a person decides, the result of each stage, and the sections the stages returned. For each section you write, also Read the files listed in the facts' section "{where_heading}".
2. For every number that is in the facts file, write the same value as the file. If you write a number that is not in the file, say which file and which field you counted it from. The machine appends this file as it is at the end of the report, so do not list the same items again in the body. There are only two exceptions: paste the outcome and the stopping stage of the facts' section "{stop_heading}" as they are (item 3 of the outline), and write the verdicts and reasons of the independent reviews unchanged from the facts, adding an explanation for the reader (item 5 of the outline). On top of those facts, the body adds what happened and what a person should decide.
<!-- if prev -->
3. Your previous answer was rejected; the reasons are at the top of this prompt. After step 1, Read your previous answer at `{prev_file}` and revise that body. Read the notes from earlier rounds as the request at the end of this prompt says. Fix the places the reasons name, and return the whole body again, not only the parts you fixed.
<!-- end prev -->
4. You only read. Your tools are Read, Grep, Glob, and the web tools WebSearch and WebFetch. Do not change a single character of the working tree; if you do, the runtime fails this node.
5. The machine stamps the provenance line of the report (the graph, the run number, the round, and the graph version). Do not copy it yourself.
6. The report for people (`report-ai.md`) carries only the machine's first 3 lines, the head of your answer (the summary before the first heading and the section whose heading contains "{decisions_head}"), and the term definitions. Its lines are cut at a count that matches the number of things a person decides. The other sections go, together with the machine's facts, into the file with the details (`report-detail.md`), and the report for people points to that file in one line. In the report for people and in the text given to the first-time reader, the machine replaces the words in its glossary, which only the factory uses, with plain words.

## Outline (what to read: the machine's facts file above and the files it lists)

Write the report in {lang}. This covers every field a person reads: the body of the report, the terms, and the handoff notes. If the files are in another language, still write in that language. Do not translate keys, enum values, code identifiers, paths, commands, or error messages; keep them as they are (keys are matched across rounds).

1. **The section on what a person decides expands the machine's one line per item**: everything listed in the facts' section "{decisions_heading}", with the kinds named as that section names them; do not reorder them here. If a row at its top is about a group that the re-check removed because it turned red, that is a sign that a correct fix may have been dropped, so include it as an item too. When the outcome word is `stopped_by_request` (stopped by a stop mark that the request placed) or `stopped_by_human` (a person stopped it at an approval node), or when it is `needs_human` and there is a reason to open an approval node (the reason for opening in line 1 of the machine's first lines, or an independent review that did not pass — write "needs a fix" and "needs a redesign" apart, and do not give "needs a fix" as a reason to discard the diff), always include as one item where it stopped, the text of the reason, and the questions left unanswered, adding that to continue one starts a new run and that the stages after the stop did not run. If there is nothing, see the format rules. Put the questions of the judgment file's question ledger that became `resolved` or `decided` under "Decided in the judgment file", with their grounds, right after the section on what a person decides and before item 2. The order is: the first 3 lines (machine) → the summary → what a person decides → decided in the judgment file → item 2 onward.
   Write what you ask so that a person who did not watch the run can read it for the first time and decide: (1) separate what is urgent from what can wait, and give the counts first; (2) each item can be read on its own; (3) for each item, say what to decide, why it came up (the actual trigger), what happens with each option, and what stops if nobody decides; (4) give the material for choosing, but write only the options and reasons written in the judgment file (the recommendation at the tail of a question's text, and the `options` and `reason` of the judgment file's ledger), and do not recommend a new option yourself. **A question written only in internal vocabulary ([block], do-now, defer, zero prescription, R1 to R4, material names, stable keys) cannot be decided as it is.**
2. The entry and the request of this run (after the first 3 lines and what a person decides; never before the first 3 lines):
   - If the facts say that this run entered at the judgment, write in one line: "A run that entered at the judgment (the origin). The roles that look outside the request were not started until a fix went in." Even if the run looks finished, the reader must still see that no review looked beyond the request before the fix.
   - If requests were stacked in this run (the entry line in the facts and the number of requests), list their origins and counts in one line. Do not lump a person's request and the machine's main graph together as "a person's request". Do not drop any request from the report.
3. As material for judgment, paste the outcome and the stopping stage of the facts' section "{stop_heading}" as they are.
4. For each root unit, its label and what was done or why nothing was needed (the unit rows of the judgment file and of the fix's results). Then the defer ledger: the keys of the defects accepted to be fixed later.
5. The verdict and reason of each of R1, R2, R3, and R4 (the facts' section on the independent reviews). For R1, also the comments it removed and the whys it kept, as listed in its section of the facts. If the facts have no such rows, write that R1, or the earlier step that picks comment candidates, did not run.
6. The question ledger: the state of each question, and the grounds for deciding it (the resolution of a question made `resolved`) or the reason it was sent to a person.
7. The raw answer of the judgment (the judgment file; do not round it in a summary; copy the set of root unit keys, the verdict, and the reasons as they are), the source of the original purpose, and the version before the fix (the original version in the start record).
8. Observation of the main path: what was run where and what was observed. Do not write "the tests are green" as an observation.
9. Inventory of new mechanisms: list, without judging them, the mechanisms and plumbing this diff introduces (build settings, environment variables, CI jobs, template knobs, scripts, and so on).
10. If the premises drifted, the re-measured constraints and why the earlier constraints became false. Put the held or escalated items of a run that stopped without converging into item 1.

## Format rules (rules for the reader; where they disagree with the outline, follow these)

The reader runs several tasks in parallel and reads this report between switches. Write so that a person who did not watch this run and has no context of the conversation can read it for the first time and decide. The head of the body you return (before the first heading, and the section whose heading contains "{decisions_head}") is read alone by another reader with no context and no tools (the first-time reader), who checks it and, if stuck, sends it back to you with reasons. That reader is told that sections with headings and the section of the machine's facts follow the head. You may leave detailed numbers, paths, and history to those sections, naming them by heading, but put in the head what is needed to decide.

- **The machine builds the first 3 lines** (what happened, whether the diff may be applied, the number of things a person decides, and one line per item under it; the machine also puts phrases into line 1, such as that the tests did not run or that the run used an environment that reaches the user's credentials). Do not rewrite or copy those lines in the body. The head of the body (before the first heading) is the plain summary read right after them: in 2 to 3 lines, without jargon, what was found and what changed. Make the first 3 lines and the summary alone enough to say what it is about, whether it concerns the reader, and whether it is urgent.
- When there is nothing for a person to decide, do not write a stock phrase that says so, in the summary either. This replaces the line "nothing for a person to decide" of outline item 1: do not write that line, and do not put a section whose heading contains "{decisions_head}". After the summary, continue with "Decided in the judgment file" if there is any, or with item 2. Asking nothing tells the reader that no input is awaited.
- **Gather what you ask a person to decide in one place right after the first lines** (the section whose heading contains "{decisions_head}"). Do not scatter questions in later sections; gather here also the held or escalated items of a run that stopped without converging. Each item can be read on its own, in this order (the outline's (1) to (4) expanded): what to decide (1 sentence) → background (why it came up; one line each for the pull requests, issues, and files involved) → what happens with each option (the actual work, the effort, what breaks) → the recommendation and its reason (only a recommendation written in the judgment file's ledger, with its reason; if none is written, say that the judgment file has no recommendation, and do not recommend one yourself) → what happens after the answer (only what is in the record; for example, it goes into the draft of the next run's request `next-request.json`, or, if deferred, it stays at the top of the report) → what stops if nobody decides.
- Fold the details briefly under headings. Do not put the details of what you ask (cost, the content of the fix, places, long history, the raw answers of the reviewers) into the text of a question; fold them under later headings and name those headings from the question. Do not narrate progress or your own work.
- Write symbols, abbreviations, paths, and labels you made up as "content (symbol)" at their first use, for example "the defects judged to need a fix (block)", so that a reader who starts in the middle can still resolve them. A question written only in internal vocabulary ([block], do-now, defer, R1 to R4, material names, stable keys, and so on) cannot be decided as it is.
- Name things inside the factory with graph words: subgraphs (judge, fix, and so on) and their names, nodes, and approval nodes. Replace other names used only inside the factory (material names, role names, internal marks) with the user's words written in the request or with general words. Only for words that cannot be replaced, write "content (symbol)" at their first use and put them in `terms`.
- For danger or failure, say first whether it is broken now or only could break.
- Use tables only for lists of short values of a few words (states, counts, dates). **Do not put explanatory sentences in cells.** If you need to explain, drop the table and use bullets or prose. The acceptance step checks this by machine: it rejects a table with a cell that contains "。" or is longer than {cell_limit} characters (`code` parts are not counted). Number the steps. Where you copy something as it is, such as a raw answer of a reviewer, put it in a code fence (```).
- Use the established terms of the IT industry in the report's language. Avoid consulting jargon, literal translations of foreign words, and elaborate metaphors.
- Do not leave references that rely on context outside this body or before or after it, such as "the one mentioned earlier" or "the section above".

Return only the JSON `{"text": "<the body of the report in Markdown>", "terms": [{"term": "<word>", "definition": "<definition>"}], "handoff": {<the notes, with the fields the request below names>}}`, with no text before or after it. `terms` is optional: list the words used in the body that need a definition for a first-time reader. Do not add definitions inside the body; the machine adds the section of term definitions outside the body. The first-use "content (symbol)" of the format rules is a rewording of a word and does not count as adding a definition; a word that needs a longer explanation goes into `terms`, not into the body.

{shared:handoff}
```

`{"text": …}` と `{<the notes, …>}` は差し込み口の形（`{` の直後が小文字の名で `}` で閉じる）に合わないので、そのまま字として残る（world.md の 3.3 の終わりと同じ）。md に `$` の字は無い（materials.md の 3.1 の終わりの決まり）。

共通の断片 `workflows/.shared/prompts/handoff.md`（この block の PR が足す。plan の書き手も使う〔`lib/handoff.py` の docstring「計画の受け付けも報告の受け付けもここを呼び」〕ので、2 つの block が使う断片。plan の設計書はこの名を使い、断片を足さない）:

```markdown
## Notes handed over between rounds

The next round of you starts in a new conversation and keeps neither what you read nor what you thought in this conversation. In the answer field `handoff` (separate from the body and the plan; the machine puts it in the folder of the round, and it does not enter the body or the plan), write notes to the next round of you: `read` is the places you read (`path`, `lines`, and why you read them in `why`); `kept` is what you decided to keep and why, as sentences; `set_aside` is the options you set aside (`option`) and why (`why`), not only about the path you chose but also other ways to fix or to write; `open` is what is not decided yet, as sentences. Any of the lists may be empty, but write all four.
<!-- if handoff_rounds -->

Notes that earlier rounds of you wrote, named by the machine, oldest first. Read them all, from the oldest round. Read again from the places in `read`, keep what is in `kept`, do not bring back the options in `set_aside` unless the rejection reasons or the review findings ask for them, and check `open` against the rejection reasons and the review findings. A round marked "(no notes)" wrote none, or its body was empty and the machine placed none. A round marked "(unreadable)" has a broken record; go on without reading it.

{handoff_rounds}
<!-- end handoff_rounds -->
```

今の `lib/handoff.py` の `ASK`・`HEAD`・`USE`・`NONE`・`UNREADABLE`（`:41-49`）の文をこの断片に移した。`lib/handoff.py` の文の定数は、plan の書き手も断片に移した後の組み込みで消す（README の 9.3 の「文は md へ」）。

### 2.4 返す形

今の `output_format` のまま（`workflows/report/works-factory-report.yaml:213-257`）: `text`（空でない字）・`terms`（`[{term, definition}]`。任意）・`handoff`（`{read: [{path, lines, why}], kept: [字], set_aside: [{option, why}], open: [字]}`）。`required: [text, handoff]`・`additionalProperties: false`。人に見せる欄は `text` と `terms`（人に向けた報告と詳細のファイルに載る）で、言語は `{lang}`。`handoff` は人に見せない（報告にも `ai.json` にも載らない）。`handoff` の型の写しと `lib/handoff.py` の `SCHEMA` の一致を照らす今の試験は続ける（2.9）。

### 2.5 描いた骨組み（例の run の値。3 回目の回）

例の run の 3 回目の回の今の指示は、`workflows/report/commands/report.md`（53 行）に Archon が `$facts.output.*`・`$write-reject.output.*`・`$ARTIFACTS_DIR` を入れた物だった。新しい指示で同じ回を組んだ骨組み:

```markdown
{shared:rejected の本文: The acceptance step rejected your previous answer. …

受け付けがこれまでに拒んだ理由の全部（古い順に 2 件。前の回の拒否も直したままにする）。

1 回目の拒否:
初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した。次の所を、頭だけで意味が取れるように直した本文を丸ごと出し直せ:
- 止まった所: 冒頭 3 行の「起きたこと」が、止まった理由（round_limit）、…
…
2 回目の拒否:
初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した。…}

You are the writer of the final report, started in a new conversation. …

The outcome word of this run is **round_limit** (the stage that stopped it and the reason word: ``). …

1. First, Read the machine's facts file `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-ea97-409b-8066-2245d32746ab/report/report.md`. … listed in the facts' section "3. 見る所".
2. … the facts' section "2. 止めたか" …
3. Your previous answer was rejected; … Read your previous answer at `~/…/df5e111f-…/report/candidate-report.json` and revise that body. …
4. You only read. …
5. …
6. … the section whose heading contains "人が決めること" …

## Outline (what to read: the machine's facts file above and the files it lists)

Write the report in the language of the request (the user's language). …

1. … the facts' section "1. 人が決めること" …
…

## Format rules (rules for the reader; where they disagree with the outline, follow these)

…
- … longer than 50 characters …
…

Return only the JSON `{"text": …}` …

## Notes handed over between rounds

The next round of you starts in a new conversation …

Notes that earlier rounds of you wrote, named by the machine, oldest first. …

- r1: ~/…/df5e111f-…/report/r1/handoff.json
- r2: ~/…/df5e111f-…/report/r2/handoff.json
```

`{rejection}` の中身は例の run の `rejects-report.md` の字と同じ（`rolekit.rejects_text` が同じ物を組む）。`stop_reason` は空で、今と同じく空の字が入る。`lang` は空で、既定の文が入った。

### 2.6 今の指示との差

今の指示は `workflows/report/commands/report.md`（53 行）の 1 か所と、そこに Archon が入れた `$write-reject.output.handoff`（`runreport.handoff_part` が組む、`lib/handoff.py` の文）に在る。

- まとめた: 却下の扱い（md:7 の手順 3）を共通の断片 `{shared:rejected}` と、前の答えを読み直す手順（`<!-- if prev -->`）に。今は拒否の訳のファイル（`rejects-report.md`）と前の答えのファイルの、run directory からの相対のパスを渡して Read させた。新しい形では拒否の文の全部を指示に入れ（world と同じ。#351）、前の答え（本文が長い）だけを絶対パスで渡す。「1 回目は両方空」（md:7 の尾）は、却下が無い時は段落ごと入れない形にして要らなくした。
- 移した: 引き継ぎのメモの頼みと前の周の節（`lib/handoff.py` の `ASK`・`HEAD`・`USE`・`NONE`・`UNREADABLE`。Python の定数の文だった）を、共通の断片 `{shared:handoff}` に。Python に残るのは前の周のメモのパスの行と、周ごとの短い札（`(no notes)`・`(unreadable)`）だけ。
- 移した: 言語の 1 行（md:1。`$facts.output.lang_line`。`rolekit.LANG_RULE`）と「報告は依頼の言語で書く」（md:16）を、構成の頭の `Write the report in {lang}. This covers every field a person reads…` の文に（訳さない物の句も含む）。
- 移した: 機械が照らす字（見出しの字「人が決めること」・セルの字数 50・機械の報告の節の見出し）を `{decisions_head}`・`{cell_limit}`・`{decisions_heading}`・`{stop_heading}`・`{where_heading}` の値に（README の 5.3 の「md と validation が同じ字を持つべき値」）。今は md の字と `report_roles` の定数が別々に同じ字を持っていた。
- 替えた: 機械の報告の節の名指し「1. 人が決めること」「2. 入口・段・決めた人」「3. 止めたか」「5. 見る所」を、新しい番号（1.9）の値に。「2. 入口・段・決めた人」の入口の行（md:20・21）は、節を名指さず "the facts say that this run entered at the judgment" にした（その節は line が見出しを付けるので、report の md が名を持たない）。
- 替えた: 構成 5 の R1 の削ったコメントと残した why の読み方（md:24。`$ARTIFACTS_DIR/eyes/` の下の `r1.json` の欄 `deletions` と `r1-comments.json` の欄 `kept` を Read で読め）を、「facts の R1 の節に並ぶ物」に。ほかの block の place のファイルの名と欄の名を report の md が持たないため。r1 の block がその行を `report` の欄に組む（1.6）。
- 消した: `$ARTIFACTS_DIR/` の字（md:5・7・24）。Archon が `prompt:` の値の中の `$…` を置き換えるのに頼っていた。新しい形では prep が絶対パスを入れる。
- 消した: 語の表のファイルの名 `lib/glossary.json` と例の語（md:12「根本の単位・レンズ」）。書き手は語の表を開かず、機械が言い換えることだけを知ればよい。
- 替えた: 書式の決まりの日本語の例（「直すべき欠陥として判定した物（block）」「さっきの」「上のセクションの」）を英語の例に。本文の言語は `{lang}` で決まるので、例は言語に依らない言い方にした。決まり（初出で「中身（記号）」・前後の文脈に頼る参照を残さない）は同じ。
- まとめた: 構成 1 の「無ければ『人が決めることは無い』と 1 行」（md:18）と、書式の決まりの「その 1 行も書かず…置き換える」（md:33）の二重を、構成 1 の "If there is nothing, see the format rules." と書式の決まりの 1 か所に。決まりは今と同じ（書かない）。
- 消した: 材料の 2 つの列挙（md:7 の facts のファイルの中身の列挙と、見る所の下の例のファイルの列挙）。ほかの block の物の名を md が持たないため。
- 足した: 役の段落の「started in a new conversation」（この node は `fresh_context: true` で周ごとに新しい会話。今の指示には無かった。2.3 の 2）。
- 戻した: 言語の規則の全文（`rolekit.LANG_RULE`）。人が読む欄（本文・`terms`・`handoff`）は `{lang}`、key・enum の値・識別子・パス・コマンド・エラー文は訳さない。一度は "Write the report in {lang}" だけに狭めたのを戻した。
- 足した物は無い。英語にした（#764）。役の名「書き手」は "the writer"。

### 2.7 元の works と graphloops の同じ場面

- graphloops（`prompts/review-loop/report.md`、`graphs/review-loop.json` の `report`・`report.human_items`・`report.cold_check`）: 頭だけを書く役（human_items）と初見検査の節（cold_check）が書き手の前に別の node として在り、書き手は前の node の本文と初見検査の結果を受けて本文を書く。検証器の最終結果（`{{validation}}`）と判定者の生の返答（`{{?ref:raw}}`）を指示に貼る。周の全部の推移（周ごとの素材・問いの立った周）を書かせる。
- 元の works（`works/blk-report/`）: 頭だけの書き手と初見検査の節を外し（2026-10-09 の片付け。`lib/report_roles.py` の docstring「後の書き手が頭を書き直し、初見検査は 56 本とも redesign-needed で、AI の起動 2 回を使うだけだった」）、書き手が頭と本文を一度に書き、書き手のループの中の初見の読み手が頭だけを確かめる形にした。機械の報告（線 A の `report.md`）を入力 `machine_report` で受けた。工場はこの形を写した（#68）。
- 工場に無い・違う物と、その訳:
  - 頭だけの書き手と初見検査の別の node: 元の works が外した（上の片付け）。工場は外した後の形から作った（#68）。
  - 検証器の関所（graphloops の `pre: finalize`。通らなければ書き手は起きない）: 工場は結末の語 `record_invalid`（結果を名乗れない run）で書き手のループを飛ばす形にした（#68。`lib/outcome.py` の docstring の 4）。この block も同じ（`ai_go`）。
  - 判定者の生の返答を指示に貼る形: 工場は書き手に判定のファイルを Read させ、構成 7 で「要約で丸めず転記」と求める（#68）。この block も同じ。
  - 周の全部の推移: 工場は 1 run = 1 周（持ち主の決め carry）で、周をまたぐ推移は chain が持つ。この block も持たない。
  - 冒頭 3 行: 元の works と graphloops は書き手が書いた。工場は機械が run の記録から組む（#660、`860a242d`）。この block も同じ。
  - 周ごとに新しい会話で起こし、引き継ぎのメモで渡す: 工場の足し（#589）。元の works は同じ会話で出し直させた。この block も持つ。
  - 書き手のループが落ちた run を failed で終え、別のアカウントの resume で書き手だけを走り直す: 工場の足し（#702）。この block も持つ（4 節の finish）。
  - line の node の id と順の決め打ち: 工場は外した（#682）。この block は `sections` と `facts` で受けるので、line の node の id を 1 つも持たない。
- この block が両方より良く、残す物: 結末の語を機械が決めて書き手に書き換えさせない・冒頭 3 行と人が決める物の 1 件 1 行を機械が組む・表のセルの書式を機械が照らす・初見の読み手が通さないまま受け取った時に印を残して冒頭で言う・人に向けた報告の行を人が決める物の件数で切り、詳細を別のファイルに置く・工場の中の語を語の表で言い換える・書き手が落ちた run でも機械の報告を指して返る。

### 2.8 受け付け（`write-accept`）

今の `runreport.accept`（`lib/runreport.py:2022-2078`）の順のまま。`src/writer.py` の `accept(reply, cold, *, place)`:

1. 返答を読む（JSON のオブジェクトでない・本文 `text` が空なら拒む。種 `answer`）。
2. `terms` の型（`TERM_SCHEMA`。種 `answer`）。
3. 表のセルの書式（`format_problems`。「。」を含むか `CELL_LIMIT` 字を超えるセル。`` `code` `` とコードの囲みの中は数えない。種 `format`）。
4. 初見の読み手の判定が `pass` でなければ拒む（種 `cold`。理由は `_cold_reason` の字。止まった所と推測した所を全部並べ、機械が組んだ行の所は書き手には直せない物として分けて言う）。ただし次の 2 つは受け取り、`not_passed` に止まった所と推測した所を残す: (a) 読み手が通さなかった所が機械が組んだ行（`machine_lines`）だけの時（`machine_only`。書き手には直せないので、どの回でも書き直させない。`ai.json` の `machine_only` が真。#834）、(b) `rolekit.is_last_attempt` の回。
- 拒んだ回は、本文と `terms` を前の答えの控え（`candidate-report.json`）に、`handoff` を `r<n>/handoff.json` に置く（今の `_carry_rejected`）。前の周のメモが読めない・控えに書けない時は、出し直させても直らないので 1 回目で諦める（`give_up`）。
- 3 回目の拒否でループを抜ける（`rolekit.GIVE_UP_AFTER`）。諦めた時・控えが扱えない時は `ai.json` に `{accepted: false, reason, cold, rejects}` を書く。受け取った時は `{accepted: true, text, terms, cold, not_passed, machine_only, rejects}`。
- 返り `{done, ok, reason, kind, prev_file}`。`prev_file` はまだ諦めていない拒否の回で前の答えの控えが在る時だけ、その絶対パス（今は run directory からの相対だった。prep が読むだけになったので絶対パスにした）。今の `reason_file` は返さない（却下の段落の中身は prep が控えから組む）。
- 却下の理由の文（日本語）は、返答の中身で変わる所（セルの字数・止まった所と推測した所・型の拒み）を Python に残す（`CELL_REASON`・`_cold_reason`・型の拒みの文）。毎回同じ字の直し方の段落（初見の読み手が通さなかった時の書き直し方・表のセルの直し方）は `prompts/write.md` の `rejected` の段落が持つ（#764）。ループを諦めた時に `ai.json` の `reason` を通って人に向けた報告の頭に載るので、人に見せる文として日本語のまま（README の 5.3）。

### 2.9 試験

- standalone の fixture（`workflows/report/fixtures/`。AI の node だけを台本の返答で差し替え、script は本物を走らせる `--exec-code`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `sections`（`[{"title":"直した所","lines":["単位 u1: 直した"]}]`）と `facts`（`{"start_ok":true,"proved":true}`）だけ。`write` は本文 1 段落・`terms: []`・`handoff` の 4 つの空の配列、`cold` は `pass`。`reached` に `facts`・`write`・`cold`・`write-accept`・`finish`。`finish` の `outcome` が `fixed`、`human` が null でない。
  - `no-ai-report.stubs.yaml`: `facts` が `{}`。結末は `record_invalid`、書き手のループは飛び、`finish` の `human` が null（今の筋書きの写し）。
  - `stopped-by-request.stubs.yaml`: `facts.gates` に、`decision` が `answer.STOP_WORDS` の語で `text` が `request:` で始まる答え。結末は `stopped_by_request`（今の筋書きの写し）。
  - `cold-gave-up.stubs.yaml`: `cold` が 3 回とも `redesign-needed`。3 回目に受け取り、人に向けた報告の冒頭に `report_roles.NOT_PASSED` の行が在る（今は筋書きが無い）。
- `tests/blocks/report/`:
  - `test_outcome.py`: 1.7 の 11 の順を、`facts` と `run` の組で 1 つずつ照らす。写す元 `lib/tests/test_outcome.py` の `TableCase`・`LineStopCase`・`OrderCase`（返りの欄を組む見本を、`facts` の欄の見本に替える）。`ReadingCase`・`ConflictNamesCase`（返りの欄の読み分け）は写さず line の試験へ。
  - `test_machine.py`: 1.8 の節の並びと字。写す元 `lib/tests/test_runreport.py` の `BuildCase` のうち冒頭 3 行・止めたか・見る所・模型・費用・注意の物、`DraftsCase`・`CarryCase`（次の依頼と前の失敗の書き込みと schema の照らし）、`StampCase`。節の中身を返りから組む試験（`LinesCase`・`DecisionsCase` の大半・`LedgerCase`・`FixBesideLinesCase`・`TddCase`・`TypedCase`）は作り手の block と line の試験へ。
  - `test_sections.py`（keep-essence の 11。7 節）。
  - `test_transcript.py`: 写す元 `lib/tests/test_runreport.py::TranscriptCase`・`WriterFellCase` と `tests/workflows/test_report.py::RealRunCase`（止めた Archon で本物の run を回し、run の記録の行を読む）。
  - `test_writer.py`: 写す元 `lib/tests/test_runreport.py` の `GlossaryCase`・`AcceptCase`・`ReportGiveUpCase`・`CollectCase`・`ColdBodyCase`、`lib/tests/test_report_roles.py` の全部、`lib/tests/test_handoff.py` のうち `SCHEMA` と `save`・`unreadable` の物（文の定数の字の試験は写さない）。返答の型の YAML（`write` の `output_format` の `handoff`）と `handoff.SCHEMA` の一致も照らす。
  - `test_scripts.py`: script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` で、port の値だけを渡し、`facts` → `write_prep` → 台本の返答 → `cold_prep` → 台本の判定 → `write_accept` → `finish`。写す元 `tests/workflows/test_report.py` の `FactsCase`（`facts` の入力の形に替える）・`AcceptScriptCase`・`RejectScriptCase`（`write_prep` に）・`ColdPrepScriptCase`・`CollectScriptCase`。`WriterRunCase`（#702 の筋書き。書き手が使用枠の切れで落ち、別のトークンの resume で書き直す）は、block を include する小さな graph の形のまま写す。
  - `test_fixtures.py`: 今の `FixtureCase` の形（全部の fixture が通り、`archon validate` の誤りと警告が 0）。
  - `test_prompt_flow.py`: 指示の比べ（下）。
  - 写さない試験: `tests/workflows/test_report.py` の `ShapeCase`（30 の入力の説明の字）・`CopiedTextsCase`（元の works の指示書の写しの台帳）・`TypedCase`（型つきの成果物の一覧）・`OutDirCase`（`runreport.OUT_DIR`）・`ConvergeLinesCase`（往復の行。line へ）。
- 指示の比べ（README の 11.4）:
  - 1 つ目の commit: `prompts/write.md` を、今の `workflows/report/commands/report.md` の `$facts.output.lang_line`・`$facts.output.outcome`・`$facts.output.stop_reason`・`$write-reject.output.reason`・`$write-reject.output.prev`・`$write-reject.output.handoff` を `{lang_line}`・`{outcome}`・`{stop_reason}`・`{reason_file}`・`{prev}`・`{handoff}` に替え、`$ARTIFACTS_DIR/$facts.output.facts_file` を `{facts_file}` に替えた日本語の字で置く。`prompts/cold.md` も同じく `workflows/report/commands/cold-check.md` の `$cold-prep.output.body` を `{body}` に替えた字で置く。試験は例の run の値で、組んだ字が、今の md に同じ値を入れた字と同じになることを照らす。比べる前に古い字に当てる置き換えは 2 つだけ: (a) `$ARTIFACTS_DIR/` で始まる相対のパスを絶対パスに（md:24 の `$ARTIFACTS_DIR/eyes/` も run directory の絶対パスに）、(b) 「の、run の置き場からの相対のパス」を「のパス」に、「（`$ARTIFACTS_DIR/` の下のそのパス）」を空に（新しい値が絶対パスなので）。
  - 2 つ目の commit（英語）: 1 つ目の試験を消し、例の run の 1 回目と 3 回目の回の値で組んだ新しい指示と古い指示を並べた物を PR に載せ、2.6 と 3.6 の差の一覧どおりかを審査に出す。
- 守る keep-essence の番号: 11（7 節）。

## 3 node の設計シート: cold（初見の読み手）

### 3.1 役

文脈も道具も持たずに、人に向けた報告の頭だけを読み、何の話か・自分に関係あるか・急ぐか・何を決めるのかが言えるかを確かめ、止まった所と推測で埋めた所と、この本文だけで決められるかを返す。

### 3.2 port

`cold_prep` の入力 `writer`（← 同じ周の `write` の返答）と、place の機械の報告 `report.md` の冒頭（← facts）。どちらもこの block の中の物。

### 3.3 組み立ての順（`prompts/cold.md`）

1. `{shared:role-cold-reader}`（役の定義。決まった文）。
2〜3. `{shared:report-head-check}`（報告の頭の確かめの 2 段落。下の md の 2・3 段落目をこの断片に置く。この block の PR が足す。使うのは report の block の初見の読み手だけで、cold-read の block は使わない）。断片の中の差し込み口 `{machine_heading}` ← `report_roles.MACHINE_HEADING` の `## ` を外した字（「機械が各段の出力と run の記録から組んだ事実（AI は書き換えていない）」。詳細のファイルの見出しと同じ字）。
4. 渡した物だけを読めの 1 文（決まった文）。
5. 区切りの行で分けた 2 つ: `{machine}`（機械が組んだ行。機械の報告の冒頭）と `{body}`（書き手の頭とその頭に現れる語の定義の節）。どちらも `writer.cold_parts(writer, place=place)` が語の表で言い換えた物で、この順につなぐと人に向けた報告の頭と同じ字（`writer.cold_body`）。分けるのは、読み手が止まった所が書き手の書いた所か機械が組んだ行かを返せるようにするため（#834）。
6. 返す物と判定の決まり（決まった文）。止まった所と推測した所は、書き手の書いた所なら `stops`・`guessed`、機械が組んだ行なら `machine_lines` に置く。どれかに 1 つでも在れば `redesign-needed`（基準は変えない）。
7. 結びの 1 文。

却下の段落は持たない（初見の読み手は周ごとに新しい会話で、拒まれる側でない。今も持たない）。

md の本文（英語）の正本は `prompts/cold.md` と共通の断片 `workflows/.shared/prompts/report-head-check.md`（使うのは report の block の初見の読み手だけ。cold-read の block は使わず、その設計書はこの名を使って断片を足さない）。設計書は本文を写さない（#834 で写しを外した）。

### 3.4 返す形

`output_format`（`workflows/report/works-factory-report.yaml` の cold）: `verdict`（`pass`・`redesign-needed`）・`stops`（字の配列。書き手の書いた所で止まった所）・`guessed`（字の配列。書き手の書いた所で推測した所）・`machine_lines`（字の配列。機械が組んだ行で止まったか推測した所。#834 で足した）・`decidable`（boolean）。`required` は 5 つ全部・`additionalProperties: false`。人に見せる欄は `stops`・`guessed`・`machine_lines`（拒んだ回は書き手への拒否の理由に、受け取った回は人に向けた報告の冒頭の印と詳細のファイルに載る。`machine_lines` の行は「機械が組んだ行で止まった所（書き手には直せない）」と分けて言う）。言語の 1 文は持たない（今も持たない。返す字は読んだ本文の言語に倣う）。

### 3.5 描いた骨組み（例の run の値。3 回目の回）

```markdown
{shared:role-cold-reader の本文: This role is the cold reader, a first-time reader with no context. …（5 行）}

The reader of this text switches between several tasks while reading. …

You read only the head of the report. … under the heading "機械が各段の出力と run の記録から組んだ事実（AI は書き換えていない）". …

You have no context: …

==== lines the machine built begin ====
# 報告（run df5e111f-ea97-409b-8066-2245d32746ab）

起きたこと: 決めた周の数のうちに直しきれずに止まった（round_limit）。TDD の実行器を作れなかった（…）——TDD のループは回さない。…
差分を当ててよいか: PR を作った: https://github.com/raiki61/works-factory/pull/759（下書きの PR #759。merge は対象のレビューと決まりに任せる）
人が決めること: 15 件——許したテストの変更 13 件・直しきれずに残った物 2 件（1 件ずつ下の行。…）
- 許したテストの変更: lib/tests/test_runreport.py
…
==== lines the machine built end ====

==== text the writer wrote begins ====
この run の変更は一つです。PR を作る段（pr-commit）が commit 時のフック（pre-commit など）を走らせる環境を、…

## 人が決めること
…

## 語の定義（機械が付けた。本文の外）
…
==== text the writer wrote ends ====

Return (1) where you could not follow the meaning in the text the writer wrote and stopped (`stops`), …

Return only JSON that matches the output schema.
```

機械の冒頭は例の run の `report/report.md` の 1〜20 行、書き手の頭は `report/ai.json` の `text` の頭。例の run の 3 回目の判定は `redesign-needed`（`ai.json` の `cold`）で、上限の回なので受け取られた。

### 3.6 今の指示との差

今の指示は `workflows/report/commands/cold-check.md`（21 行）の 1 か所に在る。

- まとめた: 役の定義（md:1-7。`lib/agents/cold-reader.md` の写し）を共通の断片 `{shared:role-cold-reader}` に。断片の最後の箇条「出力の形と判定の語彙は呼び出し側の指示に従え」は、今の md の「下の指示に従え」と同じ意味（cold-read.md の 2.6 と同じ扱い）。
- 移した: 詳細のファイルの機械の節の見出しの字（md:11）を `{machine_heading}` の値に（`report_roles.MACHINE_HEADING` と同じ字を 2 か所が持たない）。
- 替えた: 区切りの字「==== ここから ====」「==== ここまで ====」を英語の区切りに。区切りは残した（本文は材料で、指示の節ではない）。
- 替えた: 「ラウンドの経緯・記録・差分は一切渡されていない」の「ラウンドの経緯」（md:13）を "the history" に（1 run = 1 周で、周の経緯の語が要らない）。
- まとめた: 返す JSON の形（今の md は欄ごとの箇条）を、output schema に合う JSON だけを返す 1 文に（形は schema が縛る）。
- 足した物は無い。英語にした。役の名「初見の読み手」は "the cold reader"（断片の中）。

### 3.7 元の works と graphloops の同じ場面

graphloops の `prompts/review-loop/report.cold_check.md` は書き手の前の別の node（頭だけの書き手の本文を確かめ、結果を書き手に貼る）。元の works はこれを書き手のループの中の読み手に替え（2.7）、工場はそれを写した（#68）。初見の読み手の block（cold-read、README の 8.5）は任意の文書を確かめる別の block で、この block の中の読み手とは別に在る（自分で決めた。9 節）。

### 3.8 受け付け

この node だけの受け付けは無い。返答の形の外れは Archon が node の段で拒む。判定の読みは `write-accept` の 4（読めない判定は `pass` でない物として数え、`COLD_UNREADABLE` の字を理由にする。今の `_cold_lines`）。

### 3.9 試験

2.9 の `test_writer.py`（`ColdBodyCase`・`AcceptCase` の初見の読み手の物）と、fixture の `cold-gave-up.stubs.yaml`。指示の比べは 2.9 と同じ。守る keep-essence の番号は無い。

## 4 script の node

どれも uv の頭の宣言を持ち、`sys.dont_write_bytecode = True` を import より前に置き、`workflows/.shared/` と `lib/` と block のフォルダを `sys.path` に足す（土台の `ports` の口に従う）。

- `facts.py`: `INPUTS_SECTIONS`・`INPUTS_FACTS`・`INPUTS_LANG` を `os.environ.get(…)` の字のままで読み、`ports.json(…, "shared:sections.schema.json")`・`ports.json(…, "shared:facts.schema.json")`・`ports.text(…)` で値にし、`facts_in.read` で既定を埋める。読めない入力は落とさず、その訳を `problems` に足す（結末は `record_invalid`）。`transcript.read()`、`transcript.facts(rows, exclude_prefix=transcript.own_prefix(), optional=facts.optional)`、`outcome.decide`、`machine.build` の順に呼び、`facts.json` を書いて返す。返り `{outcome, ok, stop_reason, machine, next_request, prior_failures, ai_go, stamp}`（`ai_go` は結末が `record_invalid` でない時に真。`stamp` は `writer.stamp(run_id, <block の YAML のパス>, facts.round, facts.line_rev, facts.start_ok)`）。思わぬ誤りは捕まえ、`machine.fallback_report` の機械の報告（`report-unwritten.md`）を指す `record_invalid` の返りにする。lib を読めない時は標準ライブラリだけで `report-facts-unwritten.md` を書いて返す（今の `facts.py` の 3 段のまま）。
- `write_prep.py`: `writer.note_writer_fell(<report.md>, None, run_id=…)`（resume の前に finish が置いた行を外す。今の `reject.py`）→ 2.3 の値と真偽を組み、`prompt.render("write", values, when)`、`write-prompt-<n>.md` に書いて `{prompt}` を返す。
- `cold_prep.py`: `INPUTS_WRITER` を字のままで読み、`body = writer.cold_body(raw, place=place)`、`prompt.render("cold", {"body": body, "machine_heading": …}, {})`、`cold-prompt-<n>.md` に書いて `{prompt}` を返す。
- `write_accept.py`: `INPUTS_REPLY`・`INPUTS_COLD` を字のままで読み、`writer.accept(reply, cold, place=place)` の返りから `{done, ok, reason, kind, prev_file}` を返す。思わぬ誤り（`rejects-report.md` に書けないなど）は捕まえない: node が落ちて run が failed になり、finish が「書き手のノードが落ちた」を機械の報告の頭に置き、resume できる（今の `report_accept.py` と同じ）。
- `finish.py`: `facts.json` と run の記録を読み、書き手のループ（`transcript.own_prefix() + "write-loop"`）が落ちていれば `writer.note_writer_fell(<report.md>, fell, run_id=…)`（使用枠の切れなら resume の命令 `answer.resume(run_id)` を添える。#702）。`writer.collect(<report.md の字>, place=place, stamp=…)` で人に向けた報告と詳細のファイルを書く（`ai.json` が無ければ書かない）。返りは 1.2 の出力の 9 欄。落ちない: 思わぬ誤りは捕まえて `record_invalid` と訳を返し、facts の機械の報告の pointer が在ればそれを指す（今の `collect.py` の `fallen`）。lib を読めない時は `report-finish-unwritten.md` を書いて指す。

## 5 受け付けの文と諦め

- 却下の理由の文は Python（`src/writer.py`）が組む日本語の文。中身は今のまま（本文が無い・`terms` の型・表のセル・初見の読み手の止まった所と推測）。
- 3 回目の拒否でループを抜ける。初見の読み手だけが通さない時は、3 回目に受け取って印を残す（`NOT_PASSED` の字を人に向けた報告の冒頭と詳細のファイルの拒みの数の行に）。初見の読み手が通さなかった所が機械が組んだ行だけの時は、その回に書き直させずに受け取り、同じ印に `MACHINE_ONLY` の訳を添える（#834。初見の読み手の基準も回数も変えず、書き手に直せない所で輪を回さない）。ほかの拒みで 3 回目に届いた時は受け取らず、人に向けた報告の頭の所に「報告（AI の報告を最後まで作れなかった）」と訳を置く（今の `collect` の `FAILED_TITLE`）。
- 書き手のループが落ちた時（使用枠の切れなど）は、run を failed で終え（Archon が落ちた node で run を落とす）、finish が機械の報告の冒頭に訳と resume の道を置いて返る（#702）。

## 6 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-report \
  --input sections='[{"title":"直した所","lines":["単位 u1: 直した"],"files":[{"label":"差分","ref":"/tmp/diff.patch","form":"file"}]}]' \
  --input facts='{"start_ok":true,"proved":true}'
```

作業ツリーは Archon の cwd。出力は `workflow get <run>` の `finish` の返り。始めの記録も、ほかの block の run も要らない。`sections` と `facts` を手で書けば、任意の結末の報告を作れる。

## 7 keep-essence の 11 との対応

README の 10 節の 11「直す単位ごとの記録が報告と最後の承認ノードに届く」のうち、報告に届く半分をこの block が担う。

- 書くのは fix: 組ごと・単位ごとの TDD の記録（今 `report.tdd_lines`〔`lib/report.py`〕が組む行: 単位の key・赤緑の結末・赤の引用・諦めた訳・凍結の行）を、fix の出力 `units` と `report` の欄に組む（fix の設計書）。
- 運ぶのは line: fix の `report` の欄を、見出し「TDD のループの単位ごとの結末」の節として `sections` に入れる（2 度目の修正は別の節）。最後の承認ノードは `units` を読む（line の設計書）。
- 載せるのは report: `sections` の節を、並びも字も変えずに機械の報告に載せ（1.8 の 8）、詳細のファイルの機械の節に字のまま埋める（`writer.embedded`）。書き手の指示の構成 4 が単位の行を本文に書かせる。行の無い節も黙って落とさない（`- この段は報告の行を返していない`）。
- 試験（`tests/blocks/report/test_sections.py`。作る）:
  - `SectionsCase.test_unit_rows_reach_machine_and_detail_unchanged`: 今の `lib/tests/test_runreport.py::TddCase` の見本の組（`GROUP_RAN`・`GROUP_OFF`）から今の `report.tdd_lines` で組んだ行を `sections` の 1 節にして facts の script を回し、全部の行が `report.md` の節「TDD のループの単位ごとの結末」の中に、並びのまま `- ` を付けた字で在り（字下げの行はそのまま）、受け取った書き手の返答で finish を回した後の `report-detail.md` にも同じ字で在る。赤の引用（「期待 3 が 6」「分母が違う」）が両方に在る。
  - `SectionsCase.test_sections_keep_their_order`: 3 つの節の見出しが `sections` の並びのまま並ぶ。
  - `SectionsCase.test_empty_section_is_not_dropped`: 行の無い節が見出しと 1 行で載る。
  - `SectionsCase.test_unopenable_file_is_named`: 開けない `files` の行が見る所と注意の両方に訳つきで載る。
- e2e: 照らしの表 `tests/e2e/evidence.json` の R21（結末の 1 行目）・R48（単位の赤緑の行）・R81（来歴）は、置き場の字 `parent/report/…` のまま（1.6）。`writer` の欄は組み込みで作り手の block の関数の名に替える。

## 8 試験の終わりの条件の命令（1 モジュールずつ）

```sh
uv run --isolated python3 -m unittest discover -s tests/blocks/report -t .
uv run --isolated python3 -m unittest tests.blocks.report.test_sections
uv run --isolated python3 -m unittest tests.blocks.report.test_prompt_flow
uv run --isolated python3 -m unittest tests.blocks.report.test_fixtures
uv run --isolated python3 -m unittest tests.layers.test_block_shape
```

本物の単独の run を 1 回（README の 11.2）: 6 節の命令に、例の run の `report/report.md` の節を手で `sections` にした値を入れて回し、人に向けた報告が日本語で書かれ、初見の読み手の判定が `ai.json` に在ることを確かめる。

## 9 自分で決めた事

- 出力の欄 `report` を、README の 8.5 の「報告の pointer」でなく、README の 4.1 と 7.1 の 8 が全部の block に求める「報告に載せる日本語の行の配列」にし、pointer は `machine`・`human`・`detail` の名で返す。訳: 8.5 と 4.1・7.1 の 8 が同じ欄の名に違う形を求めていて、形の検査（yes/no）が通る方に合わせた。line の返りの欄の名（`report`・`report_ai`）は組み込みで line が写す。
- 結末の 10 語と決める順は report に置き、どの block の欄が止め・人待ち・残りに当たるかの読み分けは line が `facts` に入れる。訳: README の 9.2 は `outcome` を report へ MOVE とし、8.5 は report が「結末の語を決め」と書く。一方で今の決め方は block の返りの欄の名（`stalled`・`premise_check`・`units` など）を読むので、それを report が持つと report がほかの block を名指す（憲法の 3）。読み分けは承認ノードと段の表を持つ line の持ち物（README の 1.2 の U・D）。結末の順と 10 語は chain も読む report の約束なので report に残した。
- 機械の報告の「1. 人が決めること」「2. 止めたか」「3. 見る所」「4. 役が呼んだ道具」と冒頭 3 行・次の run に引き継ぐ落ちた理由・模型・費用・注意は report が組み、ほかの節は `sections` から並べる。訳: これらは結末の語か run の記録に依り、結末を決めるのは report なので、line が先に組めない。
- run の記録（Archon の `$LOG_DIR/<WORKFLOW_ID>.jsonl`）は report が自分で読む。訳: 落ちた node（`interrupted` の決め）・費用・模型・道具の呼びは run の記録にしか無く、report 自身の node（書き手のループ）の落ちも finish が読む。README の 4.3 の「block は自分の place と、port の値が指すファイルのほかは開かない」は工場の run の記録（始めの記録・run directory の根）を指す決まりと読み、Archon が node に渡す run の記録はその外とした（README の直しに書いた）。単独の run では report 自身の node だけが載る。
- 書き手のループの中の初見の読み手（`cold`）は report の中に置き、line の `loop_group` に report と cold-read の 2 つの block を include して回す形（cold-read の設計書の `form: report_head`）は採らない。Archon は `loop_group` の中の `include:` を許す（`A/packages/workflows/src/include-expander.ts:202` ほか）ので、できないからではない。訳は 3 つ: (1) 1 回の書き手の返答を受けるかは、同じ回の初見の読み手の判定で決まる（今の `runreport.accept` は書き手の返答と判定を一緒に照らす）。graph のループにすると、受け付けの node は cold-read の後に要り、report の受け付けの決まり（表のセル・`terms` の型・前の答えの控え・引き継ぎのメモ・上限の回の受け取り）を cold-read の block か graph の script が持つことになる（憲法の 3、graph は計算を持たない）。(2) report を単独で呼ぶと初見の読み手の確かめが落ちる（憲法の 5。今の report は単独の筋書きでも確かめを回す）。(3) ループの回ごとに facts（結末の決めと機械の報告）を回し直さないために report を 2 つに割ることになり、置き場と控え（`rejects-report.json`・`r<n>/`）が 2 つの block にまたがる。文の重なりは、役の定義の断片 `role-cold-reader` と、報告の頭の確かめの段落の断片 `report-head-check`（3.3 の 2・3 の段落。cold-read の block は使わず、report の block の初見の読み手だけが使う）で避ける。
- 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）を読まない。訳: 今 TDD の単位・緑の認証・独立の目の判定を読んでいたのは、それらの block の出力を report が直に読む形だったため。新しい形では作り手が `report` の欄で行を渡す（README の 4.1）。
- 行の無い節を落とさずに 1 行を置く。訳: 今の `build` は行の無い節を黙って飛ばしていた（`if lines`）が、新しい形では節を graph が明示して渡すので、渡された節が消えると読み手は「段が走らなかった」と「行を返さなかった」を見分けられない（持ち主の決め `no-silent-loosen`）。
- `sections` の形はこの設計書が決め、土台の PR では何も置かない。訳: README の 11.1 は「sections の形は土台で決めるので、ほかの block を待たない」と書くが、ほかの block が守るのは 4.1 の `report` の欄（日本語の行の配列）だけで、節の見出しと `files` は graph が付ける。だから report の PR が `schemas/sections.schema.json` を置けば、ほかの block は待たずに作れる。
- 書き手の md から、ほかの block の place のファイルの名（`r1.json`・`r1-comments.json`）と欄の名を外し、r1 の block がその行を `report` の欄に組むことを求める。訳: 憲法の 3（block はほかの block を名指さない）。今の能力（構成 5 の R1 の削ったコメントと残した why）は、r1 の行が届くことで残る（r1 の設計書の宿題として 1.6 に書いた）。
- 共通の断片 `handoff` をこの block の PR が足す。訳: report は 1 波目、plan は 2 波目で、先に要るのが report（README の 11.1 の「最初に要った PR が足す」）。
- 実装で決めた事（作った時に、シートが黙っていたか、main の決まりと食い違った所）:
  - script の node の中身は `workflows/report/src/steps.py` に置き（`facts`・`facts_fallback`・`write_prompt`・`cold_prompt`・`finish`・`finish_fallback`）、`scripts/` は `ports.run` で呼ぶ薄い皮にした。訳: 1.5 の一覧に script の中身の置き場が無く、purpose の手本が `src/steps.py` に置く形だった。
  - 出口 `finish` は `with:` を持たず、`facts.json` と place のファイルの在り方（`report.md`・`next-request.json`・`prior-failures.json`・`report-detail.md`）から pointer を組む。facts が落ちた時も `facts.json` を書く（標準ライブラリだけ）。訳: 4 節が出口の入力を `facts.json` と run の記録としか書かず、pointer を `facts.json` に足すと 1.4 の欄の一覧と食い違う。
  - `facts.schema.json` の `tallied` は `patternProperties: {'^.+$': {type: integer}}` で値の型（整数）を書き、形の照らしが照らす（#851。前は `facts_in.read` の手の照らしだった。今の照らしは patternProperties を読む）。
  - 書き手の md の末尾の JSON の例は、Archon でなく `prompt.render` が `{{`・`}}` を 1 つの括弧にするので、閉じの `}}` を `}}}}` と書いた（シートの md は `}}` のままで、組むと `}` になり例が 1 つ閉じ足りない）。
  - `cold-gave-up.stubs.yaml` は、2.9 の筋書き（`cold` が 3 回とも通さず、3 回目に受け付けが受け取って報告の冒頭に `NOT_PASSED` の印の行を載せる）を全部は回せない。dry-run ではループが 1 周で終わる（周を続けるかを決める `until_bash` が走らない）からで、回すのは 1 周目だけ: 初見の読み手の役 `cold` が `redesign-needed` を返して通さず、受け付け `write-accept` が書き手に出し直させる（run は止まらず、出口 `finish` が返る）。残りの、3 回目に通さなかった時の受け付けの受け取りと `NOT_PASSED` の印は、`tests/blocks/report/test_scripts.py` の `AcceptCase` が確かめる。
  - 共通の断片 `handoff`・`report-head-check` を `workflows/.shared/prompts/` に足し、`workflows/.shared/AGENTS.md` の名の一覧を取り置きから今在る名へ移した。
  - `rejects-report.md` は、拒んだ回の `write-accept` が今までどおり書く（書き手の指示は `rejects-report.json` の控えから組むが、拒否の全部の読み物として残す）。
  - run の記録の `own_prefix`（自分の include の node の id の頭。include の node の id は `__` で区切られ、入れ子なら `outer__inner__`）は、ループの本体の node の path（`<ループの id>.<node の id>`）でも、`.` で切った段ごとに最後の `__` より前を順に継いで組む形にした（`ports` に同じ口が無かったので `src/transcript.py` に置いた）。

## 10 未確認

- 土台の `prompt.render` が、入らない段落の中の差し込み口の値を「使われない値」に数えるか（materials.md の 11 節）。この block は数えない前提で、`prev_file`・`handoff_rounds`・`rejection` を入る時だけ渡す。
- 土台の役の定義の断片の名 `role-cold-reader`。
- `ports` が自分の include の道の頭（今の `boundary.own_prefix`）を返す口を持つか（1.5 の `transcript.own_prefix`）。
- Archon の `when: "$facts.output.ai_go == 'true'"` の形（今の YAML のまま。真偽の出力の比べの字の形を変えない）。
- cold の `{body}` に書き手の本文が入るので、本文に `$<英字>` の字が在ると Archon が置き換え直しうる（今も同じ。`$cold-prep.output.body` の形で入れていた）。直すかは振る舞いを変えるので、この作り直しの外。
- 6 節の命令の正確な形。
