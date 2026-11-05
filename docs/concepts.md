<!-- coldwrite:skip 内部の設計の地図。語は冒頭の「語」のセクションで定義 -->
# 考えの住処の地図（works-factory の設計の考えが、どこに 1 つの形で住んでいるか）

状態: 2026-10-13（issue #254・PR #269）。今の works の地図（`works/docs/concepts.md`）の柵を持つ 31 の考えを 1 つずつ今の木に当て、住処が works-factory に在る考えと散らばりの考えは全部載せ、考えそのものが works-factory に無い物は下の「載せない考え」に訳を書いた。載せた考えの住処の外の当たりは、本当の漏れなら表の既知の漏れに件数と理由を置き、同じ字の別の考えに当たるだけなら語の形を狭めた。行のパスが今の木に在ることは人が見る（`docs/` の中のパスは機械が照らさない。`AGENTS.md` の E26）。まだ無い物は「予定」と書く。

works-factory 自身の木に地図と表の全部を当てる試験は置かない（`docs/design/README.md` の 9.4）。表 `docs/concepts.json` は、run の中で構造の目が対象の表として読む（works-factory 自身を直す run）。考えの住処は、block の `src/`・`lib/` の行の形のモジュール・`workflows/.shared/` の口（`docs/design/README.md` の 1.2・4.1）。表の既知の漏れの件数は 2026-11-05 に今の木で数え直した（数えは `lib/conceptfence.py` の `scan` と `verdict`）。揃いを照らす試験は無いので、その後の差分でずれうる。

載せない考え（今の works の地図に在り、考えそのものが works-factory に無い。漏れの多さは載せない訳にしない）:

- `hinge` 境のノード: メイングラフの境のノード（h-* の名のノードと住処 darkfactory/lib/line_edge.py）は works-factory に無く、design.md:472（#765 で消した。583337e の版） の通りメイングラフの when: と小さな script ノード（workflows/line/scripts/ の start・redepth・collect など）が担う
- `halt` 止め札: 共有ボードの止め札 STOP と住処 halt.py は持ち込まず（持ち主の決め stop-at-gates）、報告つきの止めは承認ノードの stop・reject の答え（一言が request: で始まれば止め札の扱い。workflows/report/src/outcome.py・lib/seal.py）が、承認ノードの間の止めは Archon の workflow cancel が担う
- `scope` 部品の置き場と宣言: 部品の宣言のファイル manifest.json と住処 scopes.py は落とし（design.md:471（#765 で消した。583337e の版））、入出力の宣言は Archon の YAML の with:・returns: と出力の型が、宣言の外の書き込みは mutates_checkout: false と書き込みの出どころの突き合わせが担う（持ち主の決め declared-io）
- `injectors` 包みが足す system prompt の塊: AI を起こす包み（前の works の adapter.py の INJECTORS と --append-system-prompt）を持ってきていない（design.md:474（#765 で消した。583337e の版） で落とした）。system prompt を足すのは Archon の AI ノードの systemPrompt（workflows/plan-review・workflows/eyes の YAML）がノードごとに字で担う
- `replycontract` 返答の契約: 返答を本文で受けて型を確かめ出し直させる包みの旗 text-reply と replycontract.py を持ってきていない（design.md:474（#765 で消した。583337e の版） で包みを落とした）。返答の型は Archon の AI ノードの output_format（SDK の構造化出力 StructuredOutput）が担う
- `writes` 役の返答を共有ボードに書く規則: graphloops の engine の共有ボードと書く規則（record.py の apply_writes・rules の WRITE_OPS）を持ってきていない（design.md（#765 で消した。583337e の版） の graphloops の写しの行で落とした）。役の返答を後ろへ渡すのは Archon のノードの出力（$<ノード>.output）と各サブグラフの script が置き場に書くファイル
- `core-seams` 写しの核の差し替えの口: 写しの核（graphloops の review-loop）が無く（lib/graphloops は engine の型検査・描き方の 7 ファイルだけ）、走る時に写しの名を替える CORE_OVERRIDES・組み手の印 rl_builder も無い。承認ノードの組み立て（gatemarks.plan_gate_items）などはグラフの script が直に呼び、写しのバイトの手直しは写しの台帳の読み口 tests/bin/copyledger.py の ! 行が担う

## 平たく言うと（3 行）

- works-factory の設計の考え（「入口の種類」「機械の web の取得」など）ごとに、それを 1 か所で持つ部品（住処）と、その考えを知ってよい所を並べた地図。
- 住処の在る考えは、住処の外に漏れたら試験で分かるようにする（柵）。住処の無い考え（散らばり）は、今の知る場所の数が増えない歯止め（数の歯止め）を持つ。
- 直す人（人も AI も）は、設計を始める前にここを読み、触る考えの住処を使う。住処の無い考えに足す時は、散らばりを増やさない形を先に選ぶ。

## 語

- 考え（concept）: 設計の 1 つの決まりごと。名前を付けて話せる単位（例: 「入口の種類を知るのは入口の変換だけ」）
- 住処（home）: その考えを 1 か所で持つ部品。ふつうは `lib/` のモジュール（持ち主の決め `concept-home`）。lib は workflows を import できない（E3）ので、持ち主の決めが書き手の側に置いた考えは、その書き手の block（例: `gate-evidence` の `workflows/test-gate/src/certify.py`。持ち主の決め `evidence-prefix-one-home`）。考えを変える時に触るのはここだけ、になっている所
- 約束（contract）: 住処の外の人がその考えに触れる時の形を決めたファイルか欄
- 知ってよい所（allowed places）: 住処のほかに、その考えの語・欄の名・値を書いてよい所。柵が照らす一覧は表 `docs/concepts.json` の `allowed` で、その全部を地図の行（住処・約束・知ってよい所）が字で名指す（試験が照らす）
- 漏れ（leak）: 知ってよい所の外に、その考えの語・欄の名・値が書かれていること。漏れた所は、考えが変わった時に一緒に直す必要があるのに、誰もそれを知らない所になる
- 散らばり: 住処の無い考え。同じ考えを複数の所がそれぞれの形で知っている状態
- 柵（fence）: 漏れを見つける安い試験。考えの語の形（正規表現）と知ってよい所を表に書き、表の外で語が見つかったら赤にする。今ある漏れは「既知の漏れ」として件数と理由つきで表に置き、減らす向きにだけ動かす。分かれ目の表より考えや柵を消す・知ってよい所・`exclude`・`bound` を広げる・語の形を変えるのも赤で、意図した緩めは表の `loosened` に新しい `"<鍵>": "<理由>"` の行を足した時だけ通る。道具は `lib/conceptfence.py`
- 状態: `住処あり`（住処が在り、柵を掛けられる）か `散らばり`（住処が無い）。どちらも柵を持つ
- 数の歯止め: 散らばりの考えの柵。知ってよい所が空で、今その考えを知っている所を全部既知の漏れとして件数つきで表に置く。まとめるたびに数が減り、増やす差分は試験が赤にする。表そのものも、`origin/main` から分かれた所の表より既知の漏れの件数の和が増えない

パスは全部リポジトリの根からの相対。表の `exclude`（試験・文書・`AGENTS.md` などの決まりの文書・ASF の物・借りた物と写し）の下は柵が見ない。AI のノードの指示の md（`workflows/*/prompts/`・`workflows/.shared/prompts/`）は柵が見る（AI に読ませる文も考えを知る所）。

## 一覧

| id | 考え | 状態 |
| --- | --- | --- |
| `entry-kind` | 入口の種類（依頼・差分の根・PR） | 住処あり |
| `web-get` | 機械の web の取得と run をまたぐ控え | 住処あり |
| `cite` | 名指しの形と場所の文の読み | 住処あり |
| `prompt-sections` | 指示書に機械が貼るセクションの見出しの宣言 | 住処あり |
| `outcome` | run の結末 | 住処あり |
| `depth` | 単位ごとの深さ | 住処あり |
| `features` | 機能の切り替え | 住処あり |
| `reads` | 読んだ証拠 | 住処あり |
| `conflict` | 食い違いの申し出 | 住処あり |
| `lanes` | 並べの組 | 住処あり |
| `marks` | 返答の足し欄 | 住処あり |
| `plan-scope` | 修正案の項目の範囲の照らし | 住処あり |
| `test-files` | テストのファイルの見分け | 住処あり |
| `red-check` | TDD の赤の判定（事実と失敗の文の引用） | 住処あり |
| `carry-over` | 次の run への持ち越し | 住処あり |
| `world` | 世界の解（問題の類ごとの定石と依頼の解き方との比べ） | 住処あり |
| `stop-reasons` | 止めの理由 | 住処あり |
| `start-record` | 始めの記録（r1/start.json） | 住処あり |
| `human-gates` | 人の承認ノードと無人の方針 | 住処あり |
| `gate-evidence` | 試験の関門の証拠の文の行の頭 | 住処あり |
| `accept-round` | 受け付けの回（返答を読む・拒否を控えに積む・上限で諦める・最後の回か） | 住処あり |
| `ledger` | 費用と時間の帳簿 | 散らばり |
| `ai-launch` | AI の起こし方（模型・effort・道具・隔離） | 散らばり |
| `prompt-assembly` | 指示書の組み立て | 散らばり |
| `lang-names` | 特定の言語・テストの実行器の名 | 散らばり |

---

## 住処あり

### `entry-kind` 入口の種類

- 状態: 住処あり
- 住処: 入口の変換 `lib/entryshape.py`（差分の根の名指しの解き `change_base`・差分も依頼の行も無い入力の拒み `refuse_empty`・入口の入力の形を作る `build`・依頼の文 `request_text`・名指した PR と issue の読み `github_reads`・PR の添え物の置き `write_pr_file`）
- 約束: 入口の入力の形（`build` が返す `{base, head_rev, diff, requests, request_file, pr, spec}`）。後ろのノードはこの中身——差分が空か・依頼の行の数・PR の添え物・仕様の段を挟むか——だけを読み、入口の種類を見ない
- 知ってよい所: 住処と、メイングラフの始めのノードの script `workflows/line/scripts/start.py`（メイングラフの入力 `INPUTS_BASE`・`INPUTS_PR` を住処へ渡す）と、周の鎖の始めのノードの script `workflows/chain/scripts/chain_start.py`（鎖の入力 `INPUTS_BASE`・`INPUTS_PR` を 1 周目の子へ写し、1 周目に名指した PR の番号を次の依頼で運ぶ）。入口の種類で分かれる形と消した種の名は住処だけ
- 今: 柵は、差分の根の名指しを読む・渡す形と、入口の種類で分かれる形・消した種の名の 2 本。試験 `lib/tests/test_concept_fences.py` の `FenceCase` が表のこの行を読み、柵が本当に当たることも見る。殻の `bin/_lib/startpoint.py` の `SKIP_FLAGS` の行は Archon の旗 `--base` を名指す写しで、入口の入力ではないので結んだ写し（bound）として数えない。試験 `tests/shared/test_archon_contract.py` が並びを Archon の旗に照らし、写しの行がその 1 行だけである事を縛る

### `web-get` 機械の web の取得と run をまたぐ控え

- 状態: 住処あり
- 住処: `lib/webget.py`（層 L1。網に出してよい URL `safe_url`・転送の決まり `SafeRedirect`・取得 `http_get`・網に出ない切り替え `is_off`・run をまたぐ控えの置き場 `shared_root` と控え `Store`）
- 約束: 口の形だけ（切り替えの名・控えの schema と期限・読む量の上限は呼ぶ側が持つ）
- 知ってよい所: 住処だけが網の素の口（`urllib.request`・`http.client`・`urlopen`）を使う。使う所はライブラリの文書の読み `lib/libdocs.py` と `lib/libdocs_web.py`、世界の解の block の `workflows/world/src/steps.py` と `workflows/world/src/excerpts.py`、試験の結果の使い回し `lib/tree_run.py`（控え `Store` だけを使う）で、どれも住処を呼ぶ
- 今: 外の当たりは 0 件

### `cite` 名指しの形と場所の文の読み

- 状態: 住処あり
- 住処: `lib/cite.py`（標準ライブラリだけ。名指しの形 `CITE`・1 つの名指しの確かめ `problem`・決め手の文の出どころの確かめ `sources_problem`・場所の文の中の名指し 1 つ分の形 `CITE_IN_WHERE` と読み `where_cites`・引用「…」の照らし `fold`・`quotes`・`quoted_in`・`missing_quotes`）
- 約束: 名指しの形と場所の文の読み、引用を畳んで部分文字列かを見る式は住処の外に持ち直さない。住処の別名・包みも置かない（読み手は `cite.CITE`・`cite.problem` を直に引く）
- 知ってよい所: 住処だけ。読み手（`lib/conflict.py`・`lib/design.py`・`lib/gatemarks.py`・`lib/worldmark.py` と、修正の `workflows/fix/src/common.py`・`workflows/fix/src/gates.py`・`workflows/fix/src/ruling.py`・診断の `workflows/diagnose/src/judge.py` ほかの block の `src/`）は住処の口を引き、自分の定数や関数に写さない
- 今: 柵は、住処の定数を別の名に写す形（`X = cite.Y`・`from cite import`・`import cite as`）と、消した別名・包みの名・場所の文の読みの定義の字と、住処の外で `cite.fold(` を組む形を見る。2026-11-05 の数え直しで、1 つ目の柵の既知の漏れに `workflows/external-standards/src/rankings.py` の 1 行を載せた。小文字の名への写しや別の名の包みは字の形で見分けられず、柵は見ない

### `prompt-sections` 指示書に機械が貼るセクションの見出しの宣言

- 状態: 住処あり
- 住処: `workflows/.shared/prompt.py`（AI のノードの指示を、そのノードの md `prompts/<node-id>.md` に値を入れて組む口 `render`・`compose`・`emit`・`render_part`・`render_shared`）。セクションの見出しの字は指示の md が持ち、Python は見出しの宣言の型を持たない（憲法の 2）
- 約束: 指示の md の値を入れる口 `{name}`・`{shared:<name>}`・`{part:<name>}` と、段落の選び `<!-- if <name> -->`（書き方は住処の docstring）
- 知ってよい所: 住処だけ。柵は、見出しの宣言の型（`Section`・`Receive`）と宣言を並べる口（`declared_sections`）の定義が Python に出ないことを見る
- 今: 外の当たりは 0 件

### `outcome` run の結末

- 状態: 住処あり
- 住処: 結末の語の並び `lib/report.py` の `OUTCOMES`（10 語）と、結末の決め方 `workflows/report/src/outcome.py` の `decide`（graph が集めた事実と run の記録から 1 語を決める）
- 約束: 報告のサブグラフの返すノードの出力 `outcome` の enum（`workflows/report/works-factory-report.yaml`）
- 知ってよい所: 住処と約束だけ
- 今: 柵は結末の語の字（`"no_fix_needed"` など）を見る。`"round_limit"` は往復のループの上限の入力の名と同じ字なので、欄の鍵（`"round_limit":`）と添字（`["round_limit"]`）は数えない。既知の漏れは、止まった結末の並び `STOP_OUTCOMES` を自分で持つ報告の機械の部分 `workflows/report/src/machine.py` とメイングラフの事実の集め `workflows/line/src/facts.py`、メイングラフの出力ノード `workflows/line/scripts/result.py`（lib を読まずに fixed を決める）の 3 ファイル 3 行

### `depth` 単位ごとの深さ

- 状態: 住処あり
- 住処: `workflows/line/src/tiers.py`（単位 1 つの深さ `unit_depth`・控えの形 `decide_doc`・信号での上げ `raise_doc`・修正の後に上げる信号 `outside_cited`（引用の外の差分）・`late_signals`（引用の外の差分・TDD の拒否・範囲の相談の理由）・run 全体の深さ `run_depth`・省く理由の文 `skip_reason`（頭の深さの省く物と単位の深さから）・報告の行 `lines`。run の頭の深さの定義 `TIERS`・段の足し `tier_adds`。修正の後の上げ直しの数え `signals`（メイングラフの上げ直しのノード `raise` の script `workflows/line/scripts/raise_depth.py` が呼ぶ 1 か所）と、控えが無い時の訳 `NO_LATE_RECORD` と、読めない控えを上げる側へ倒す信号 `LATE_UNREAD`）。段の語 `HEADS` の住処は `lib/headdepth.py`
- 約束: 計画の出力 `depth`（`[{unit_id, depth, why}]`。depth は `軽量`・`標準`）と、修正と目のサブグラフへ渡す run の頭の深さの語（平の入力 `head_depth`）。run の頭の深さの語（`軽量`・`標準`・`重厚`）は判定の出力 `depth` で、表 `TIERS` が定義する
- 知ってよい所: 住処と、メイングラフ `workflows/line/`（始めのノードの入力 `thickness` の確かめと、直した後の上げ直しのノード `raise`）
- 今: 表の既知の漏れは無い（2026-11-05 の数え直しで、`lib/fixboard.py` の 4 行が消えていた。口を引く名の柵は住処の名 `tiers.` で見る）。控えの扱いの字の柵と数えの中身の柵は、住処 `tiers.py` の外に字が無いことを見る（漏れ無し）

### `features` 機能の切り替え

- 状態: 住処あり
- 住処: `lib/entry.py` の `FEATURES`（語 → 説明）・既定 `FEATURE_DEFAULTS` と読み `features_off`・`features_on`・`features_cut`・`cut_of`・`switch`（始めの記録から機能 1 つの語を引く。名指し > 頭の深さの足し `adds` > 既定）
- 約束: メイングラフ `workflows/line/works-factory-line.yaml` の入力 `features_off`・`features_on` と、始めのノードの出口の同じ名の欄（block へは on・off・auto の平の入力。始めの記録から block に配る値はメイングラフの `workflows/line/src/deal.py` が引き、頭の深さの足しが効く事前審査の木 `review_tree` は `workflows/line/src/tiers.py` の `switches` が段の語から引く）
- 知ってよい所: 住処・約束と、入力の語を確かめて始めの記録に置く始めのノードの script `workflows/line/scripts/start.py`
- 今: 既知の漏れは、メイングラフが機能の語を自分の定数に字で持つ所（`workflows/line/src/deal.py` の `REVIEW_TREE`・`JUDGE_VERIFY`・`LANES` と `workflows/line/src/tiers.py` の `TREE_FEATURE`）の 2 ファイル 4 行（2026-11-05 の数え直しで、`lib/fixboard.py` の 1 行が消えていた）

### `reads` 読んだ証拠

- 状態: 住処あり
- 住処: `lib/reads.py`（記録の根と作業の場ごとの記録のファイル `reads_path`・`log_here`、記録の名 `LOG`、置き場の読んだ証拠と索引の名の口 `evidence_name`・`index_name`・`is_index`・`EVIDENCE_GLOB`、役ごとの証拠を集める `collect`、集めるノードの中の誤りを落ちた記録（`sources.hook` が `FAILED`）にして残す `guarded`・`failure_name`、役が web を引いた記録 `web_fetches`・`web_searches`）
- 約束: 住処の名の口（置き場の名を使う所はこの口から引く）と、Read のフックの記録の行の形 `{ts, session_id, agent_id, path, file_sha, bytes, partial, partial_why, tool_use_id}`（Agent・WebFetch・WebSearch は path を持たない形）
- 知ってよい所: 住処・Read のフックの殻 `bin/_lib/record-read.py`・各サブグラフの集めるノードの script `workflows/fix/scripts/fix_reads.py`・`workflows/plan-review/scripts/review_reads.py`。記録の置き場の決め方（鍵・控え・片付け）は書き込みの記録の `lib/writelog.py` と共にする
- 今: 外の当たりは `lib/writelog.py` の docstring の 1 行（置き場の決め方を共にする相手として記録の名を述べる）

### `conflict` 食い違いの申し出

- 状態: 住処あり
- 住処: `lib/conflict.py`（申し出の形 `ITEM_SCHEMA`・`CONFLICTS_SCHEMA`、欄の名 `FIELDS`（`WHY_FIELD`・`WHICH_FIELD`・`KIND_FIELD` を含む）、申し出の種類 `DIV_KINDS`、機械の確かめ `problems`、止めた単位の積み `park`、出どころの語 `SOURCES`（組どうしの合わせの申し出 `JOIN_SOURCE` を含む）、裁定の語 `DECISIONS`（判定のやり直し `REJUDGE` を含む）・`FIX_DECISIONS`、直す義務から外す単位 `held_by_rulings`）
- 約束: 住処の定数の表（申し出の欄と裁定の語）と、修正役の返答の欄 `conflicts` の形（`workflows/fix/works-factory-fix.yaml` の `output_format` に字で書く）
- 知ってよい所: 住処と、申し出を書いて裁く修正のサブグラフ（`workflows/fix/`。TDD のループ `workflows/fix/src/tdd.py`・裁定のループ `workflows/fix/src/ruling.py`・組の合わせの直し `workflows/fix/src/clash.py`（組どうしの合わせの申し出を積む。欄の名は住処の `clash_claims` で組み、字を写さない）を含む）と、申し出の取り込みの置き場の助け `lib/fixboard.py`
- 今: 外の当たりは、案の直しの事前審査と項目のセクションに申し出を貼る `workflows/plan-review/src/material.py`・`workflows/plan/src/brief.py` と、`lib/querytest.py` の docstring と、2026-11-05 の数え直しで表に載せた書き手の型の共通の部品（`workflows/.shared/prompts/` の書き手の指示の断片・`workflows/.shared/schemas/writer-reply.schema.json`）・武器の block の YAML・`lib/conflicts.schema.json` の、14 ファイル 48 行

### `lanes` 並べの組

- 状態: 住処あり
- 住処: `workflows/fix/src/lanes.py`（組の分け方 `groups`（タグを共にする物どうしの組。つながりは推移的。引数 `after` の依存の対 (前, 後) も同じ組に繋ぎ、組の中を前から後へ並べる）・当てた結末 `Merge`・組を順に当てる `merge_in_order`）
- 約束: 住処の口の形（`groups(rows, after=())` の返す並びと、`rows` の外の端を持つ `after` の対は捨てる約束（項目の依存から組の対を引くのは `lib/planmarks.py` の `depends_pairs`）・`Merge` の欄 `why`・`patch`・`names`・`unioned`・`clash`・`merge_in_order` に渡す `merge_one(lane, earlier)`）。何を 1 つの組に当てるか（子の差分を 3 方向で当てる `lib/unittrees.py` の `apply`）は呼び手が渡す
- 知ってよい所: 住処だけ。呼び手（組を作り子の差分を当てる `workflows/fix/src/board.py` と、締めの node `workflows/fix/scripts/join.py`）は住処の口を引き、分け方・当てる順のループ・結末の語を写さない
- 今: 外の当たりは、2026-11-05 の数え直しで載せた `workflows/line/src/facts.py` の 1 行

### `marks` 返答の足し欄

- 状態: 住処あり
- 住処: `lib/jsonfile.py`（標準ライブラリだけ。欄の道 `EACH` と道を辿る口 `rows`（欄を持つ行）・`split`（受け付けが共有ボードへ渡す前に欄を外す）と、控えの読み書き `write`・`dump`・`read_or`）
- 約束: 欄の道（鍵の名か `EACH`）と `split` の返す物（欄を外した写しと外した欄）。控えのファイルの名と欄の道は、欄を持つモジュールが自分の定数で持つ
- 知ってよい所: 住処だけが欄を手で外す。欄の意味（欄の型・欠けと誤りの検査・控えの名と中身の形・読んだ後の使い方）は欄を持つモジュール（`lib/gatemarks.py`・`lib/planmarks.py`・差分の審査の `workflows/delta-review/src/verdicts.py`・`lib/converge.py`・`lib/querytest.py`・`lib/outpurpose.py`・依頼の解き方 `means` の `lib/worldmark.py`・引き継ぎのメモ `handoff` の `lib/handoff.py`）が持ち、外す手順は住処を呼ぶ
- 今: 控えの名を定義する持ち主（`lib/gatemarks.py`・`lib/planmarks.py`・`lib/querytest.py`・`lib/outpurpose.py`・`lib/worldmark.py`・`lib/handoff.py`・並行 PR の名の表 `workflows/parallel-pr/src/files.py`）は、控えの名の柵の知ってよい所に置く。表の既知の漏れは、控えの名を lib の持ち主と同じ字で持ち直す block の名の表（`workflows/diagnose/src/files.py`・`workflows/plan/src/files.py`・`workflows/purpose/src/steps.py`）、控えのパスを持ち主の定数で直に組む所（`workflows/fix/src/board.py`）、欄を手で外す所（並行 PR の `workflows/parallel-pr/src/take.py`・手直しの `bash_writes` の `lib/writes.py`・2026-11-05 の数え直しで載せた `workflows/fix/src/board.py`・`workflows/delta-review/src/verdicts.py`・`workflows/plan/src/take.py`・`workflows/purpose/src/steps.py`。`lib/fixboard.py` の行は消えていた）。`workflows/verify/src/steps.py` は自分で組む裏取りの型で、同じ字の形の別の物

### `handoff` 引き継ぎのメモ（次の周の自分への書き置き）

- 状態: 住処あり
- 住処: `lib/handoff.py`（欄の名 `FIELD`・欄の並び `KEYS`・型 `SCHEMA`・書けという頼み `ASK`・前の周のセクションの見出し `HEAD`・使い方 `USE`・メモが無い周の文 `NONE`・読めない周の文 `UNREADABLE`・控えのパス `path_of`・控えを置く `save`・読めない控えを返す `unreadable`・前の周のセクションを組む `section`）
- 約束: 役の返答の欄 `handoff`（4 つの欄 `read`・`kept`・`set_aside`・`open`）と、周のフォルダの控え `handoff.json`（控えの名 `FILE` と置き場の口 `path_of` は住処）
- 知ってよい所: 住処だけ。計画の受け付け `workflows/plan/src/take.py` と報告の書き手の受け付け `workflows/report/src/writer.py` は住処の `FIELD`・`path_of`・`save`・`unreadable`・`section`・`ASK` を使い、型・頼み・セクションを写さない。役の返答の型の YAML の写し（`workflows/plan/works-factory-plan.yaml`・`workflows/report/works-factory-report.yaml`）は `SCHEMA` の写しで、`tests/blocks/plan/test_shape.py`・`tests/blocks/report/test_writer.py` が住処と等しいことを縛る（表の bound）
- 今: 外の当たりは、2026-11-05 の数え直しで載せた形 `workflows/.shared/schemas/handoff.schema.json` の 1 行

### `plan-scope` 修正案の項目の範囲の照らし

- 状態: 住処あり
- 住処: `lib/planrange.py`（項目の範囲の glob の並び `item_globs`・項目の範囲 `inside`・`out_of_scope` の当たり `oos_hit`・`oos_hit_for`・範囲の相談の合意 `with_agreed`・パスを結ぶ項目 `owner`・許しのパス `permit_paths`・単位に結べないパスの外れ `outside`・共有ボードで照らす `check_paths`）
- 約束: 修正案の項目の欄 `allowed_paths`・`out_of_scope`・`files`（ファイル構成の行。行の型 `FILES_SCHEMA`）・`depends_on`（欄の型と読みは `lib/planmarks.py`）
- 知ってよい所: 住処と、glob の当て方の下回り `lib/globs.py`（`glob_match`・`glob_problem`・`globs_meet`）と、項目の欄の読みを持つ `lib/planmarks.py`（`glob_match` を呼ぶ `gaps`・`test_paths`・`file_symbols`・`file_paths`）。使う所は修正の受け付けの照らし `workflows/fix/src/scope.py`・手直しの受け付け `workflows/delta-review/src/touchup.py`・波及の照らし `workflows/plan/src/ripple.py` の `_covered`・穴の名札の path の規則 `lib/holeties.py`（`inside`）・修正の組分け `workflows/fix/src/board.py` の `fix_groups`（`item_globs`）・役の brief の範囲の欄を組む `lib/fixboard.py` の `scope_brief` で、どれも住処を呼ぶ
- 今: 同じ当て方を手で書く所が残る（範囲の相談の `workflows/fix/src/consult.py`。`out_of_scope` に当たるパスを範囲から除く別の決まりで、`inside` に寄せると振る舞いが変わる。柵の表の既知の漏れ）。`lib/protect.py` は守りのファイルの型を同じ下回りで当てる別の考え

### `test-files` テストのファイルの見分け

- 状態: 住処あり
- 住処: 名の慣習は `lib/impact.py` の `is_test`（`TEST_NAME`・`TEST_STEM`。言語の表でなく名の形）、宣言と慣習を合わせた見分けは同じ `impact.py` の `is_test_file(path, declared)`。TDD のループの宣言の組は `workflows/fix/src/tdd.py` の `declared_test_files`
- 約束: 文書の宣言は対象の git の属性 `linguist-documentation`（`impact` が読む）
- 知ってよい所: 住処だけが名の型を書く。修正の `workflows/fix/src/common.py` の `PYTEST_FILE` は pytest の既定の python_files（実行器が pytest の時の名指しの型）で、知ってよい所に置く。使う所（`workflows/fix/src/gates.py`・`workflows/plan/src/ripple.py`・`workflows/plan/src/take.py`・run の広さを数える `workflows/line/src/tiers.py`）は住処の口を呼び、宣言と慣習を合わせる式を自分で組まない
- 今: `workflows/gate-efficacy/src/signals.py` の `GATE_FILE_PATTERNS`（検証ゲートの定義のファイルの広めの型）は別の考えで、テストの名の型の字を含む（柵の表の既知の漏れ）

### `red-check` TDD の赤の判定（事実と失敗の文の引用）

- 状態: 住処あり
- 住処: `workflows/fix/src/common.py` の `red_check`（赤の事実の判定。正本 `lib/baseline_red.py` の `red_problems` を中で呼び、役の引用と理由の照らしを足す）と `QUOTES_FIELD`（test の段の返答の欄と単位の記録の欄の名）、ループの記録した赤の木で名指しを走らせ直す `red_rerun`。引用を寄せた後の部分一致で照らす口は `lib/cite.py` の `quoted_in`
- 約束: 出口の欄 tdd の単位の行 `workflows/fix/src/tdd.py` の `FIELDS`。役の務めの置き場は TDD の役の指示の断片 `workflows/fix/prompts/parts/tdd.md` の test の段（引用と理由を書く務め・走る前の失敗の直し方）
- 知ってよい所: 住処・TDD のループ `workflows/fix/src/tdd.py`（単位の記録に引用を残す）・役の務めの断片 `workflows/fix/prompts/parts/tdd.md`・赤と緑の判定の正本 `lib/baseline_red.py`（`red_problems` の定義）・`lib/cite.py`・`lib/report.py`（出口 tdd の単位の行を読み、引用と理由を報告の行に並べる）・`workflows/fix/works-factory-fix.yaml`（TDD の役の返答の型 `&tdd_reply` が欄 `red_quotes` を宣言する。型の正本は output_format だけ、持ち主の決め `io-in-output-format`）。事後の関門（`workflows/fix/src/gates.py`）は `red_check`・`red_rerun` を呼ぶだけで、赤の式を持たない
- 今: 外の当たりは 0 件。機械が見るのは言語に依らない事実（名指しが走った・failure で落ちた・名指しの外は元のまま）だけで、「期待どおりの理由で落ちたか」は役が結末の失敗の文を引いて書き、機械は引用が結末の failure の文に在るかだけを照らす

### `carry-over` 次の run への持ち越し

- 状態: 住処あり
- 住処: `lib/carry.py`（依頼の容器の欄の名 `KEYS`・`ANSWER_KEYS`・`PRIOR_KEYS`、下書きの印 `DRAFT_KEYS` と `is_draft`・`draft`、共有ボードの根のファイルの名 `NEXT_REQUEST_FILE`・`PRIOR_FAILURES_FILE`・`PRIOR_IN_FILE`、依頼の解き方 `parts`・`without_prior`・`carry_ci`、次の依頼の中身 `compose`・行の鍵 `row_key`、独立の目 R2 の作り直しの行 `REDESIGN_WHERE`・`is_redesign`、照らしてから置く `place_prior`、役に貼るセクション `prior_section`、前提の検算の実測 `carried_constraints`）
- 約束: `lib/next-request.schema.json`・`lib/prior-failures.schema.json`（住処が読み、書き手は書く前に照らす。欄の名の定数と Schema の欄が揃うことは試験 `lib/tests/test_carry_home.py` が縛る）
- 知ってよい所: 住処と約束だけ。何を運ぶかは書き手の側が決め、形は住処を呼ぶ（報告 `workflows/report/src/machine.py`・承認ノード `lib/gatemarks.py`・目的の外の所見 `lib/outpurpose.py`）。読み手（入口の始めのノード `workflows/line/scripts/start.py`・診断の `workflows/diagnose/src/inputs.py`・計画の `workflows/plan/src/steps.py` ほか）も住処の名と口を引く
- 今: 柵は持ち越しのファイルの名・下書きの印・住処の定数の字と、前の失敗を欄の名の字で直に読む形（`["prior_failures"]`・`.get("prior_failures")`）。`"prior_failures":` の鍵や並びの字はグラフのノードの入出力（前の失敗のファイルのポインタ）の名と同じ字なので数えない。住処の外の当たりは、前の失敗の port を欄の名の字で開く・運ぶ block の行（診断・計画・メイングラフ・報告の 8 ファイル 10 行）で、字の形で中身の直の読みと分けられないので既知の漏れに置く。容器のほかの欄の名 `findings`・`answers` などは柵に入れず、呼び手が `carry.PRIOR` などの定数を引く決まりだけで守る

### `world` 世界の解（問題の類ごとの定石と、依頼の解き方との比べ）

- 状態: 住処あり
- 住処: `lib/worldmark.py`（行の欄の名 `FIELDS`・行のファイルの名 `WORLD_FILE`・控えの名 `STATE_FILE`・語 `VERDICTS`・`BASES`・名指しの句 `NOT_WEB`・先例の出どころの頭の字 `SOURCE_PREFIX`・読み書き `rows`・`read`・`write`・`stage_rows`・頭のセクション `section`・答えの要る行 `needs`・`need`・`unanswered`・依頼の解き方との比べの文 `challenges`・承認ノードの軸 `world_ok`・承認ノードの行 `gate_line`・報告の行 `report_lines`・先例の出どころの照らし `ref_problems`・依頼の解き方の足し欄 `MEANS` と `split_means`・`write_means`・`means_of`）
- 約束: 行の欄と語は住処の定数 `FIELDS`・`VERDICTS`・`BASES`（試験 `lib/tests/test_worldmark.py` が縛る）。行の型は `lib/world-row.schema.json`
- 知ってよい所: 住処と、世界の解の block `workflows/world/`（行と段の控えを書く出口 `workflows/world/scripts/finish.py` を含む）。読み手（`lib/planmarks.py`・`lib/gatemarks.py`・診断の `workflows/diagnose/src/judge.py`・計画の `workflows/plan/src/brief.py`・事前審査の `workflows/plan-review/src/material.py` ほか）は住処の口を引く
- 今: 柵は行のファイルと控えの名の字。表の既知の漏れは、2026-11-05 の数え直しで載せた行の形の名指し（`lib/world-row.schema.json` と、世界の解を受ける block の YAML 3 本）の 4 ファイル 4 行

### `stop-reasons` 止めの理由

- 状態: 住処あり
- 住処: `lib/stopby.py`（標準ライブラリだけ。機械の語の頭 `HEAD`（`works:`）と頭の読み `is_line`、段の語と 2 つ以上の持ち主が共に書く語の表 `REASONS` とその定数 `ADAPTER`・`LINE_SCRIPT`・`REJUDGE` など、人の止めの頭 `HUMAN`、人の答えを待つ語 `WAITING`、自分だけの語を足す口 `declare` と `declared`）
- 約束: 語の字は共有ボード・報告・固定材料に残るので変えない（試験 `lib/tests/test_stopby.py`）
- 知ってよい所: 住処だけ。書き手は住処の定数を引き、自分の定数に写さない
- 今: 柵は語の字（`"works:<名>"`・頭の `"works:"`）と、住処の定数をそのまま別の名に写す形（`X = stopby.Y`・`from stopby import`・`import stopby as`）。既知の漏れは、語の字の柵が 7 ファイル 7 行（落ちない返しのノードの `workflows/line/scripts/result.py` と、2026-11-05 の数え直しで載せた `workflows/judge/scripts/spec_in.py`・`workflows/judge/src/fallback.py`・`workflows/line/src/guard.py`・`workflows/line/src/stages.py`・`workflows/spec-driven/scripts/finish.py`・`workflows/spec/scripts/finish.py`。`workflows/judge/scripts/verdict.py`・`workflows/line/scripts/collect.py` の行は消えていた）と、定数の写しの柵が 2 ファイル 3 行（`lib/report.py` の `HUMAN_BY` と `workflows/diagnose/src/files.py`）

### `start-record` 始めの記録 `r1/start.json`

- 状態: 住処あり
- 住処: `workflows/line/src/startrec.py`（標準ライブラリだけ。置き場の名 `REL`〔字は line の置き場の名の表 `workflows/line/src/files.py` の `START`〕と `path`、読み口 `read`・`load`、書き `write`・`save`、入口の入力の形の読み `shape`・`diff_empty`・`requests`、読む版と差分の根 `read_rev`・`diff_base`、入口の文 `words`、命令の版の 1 行 `cli_version`）
- 約束: 住処の口だけ（置き場の名と読む口はここ 1 つ。記録の型の Schema は works-factory に無い。試験 `tests/blocks/line/test_startrec.py`）
- 知ってよい所: 住処と、置き場の名の字を持つ `files.START` の 1 行。書き手はメイングラフの始めのノード `workflows/line/scripts/start.py`（`startrec.write`）と、直しの前の答えで方針を固め直す `workflows/line/scripts/before_fix_answer.py`（`startrec.save`）と、固定材料の取り込み（line の `src/fixture.py` の `adopt`）と、修正に入る時に固定材料の控えの印を足す同じファイルの `noted_capture`（`workflows/line/scripts/fix_in.py` が呼ぶ）で、読み手は `startrec.read`・`startrec.load` を引く
- 今: 柵は置き場の名を字で書く形・置き場の名の別名（START_REL・START_FILE）・別の読み口（start_doc の関数）。表の既知の漏れは無い（2026-11-05 の数え直しで、最後の承認ノード `workflows/line/scripts/ask_final.py` の包み `start_doc` の 2 行が消えていた）

### `human-gates` 人の承認ノードと無人の方針

- 状態: 住処あり
- 住処: メイングラフの承認ノードの決め `workflows/line/src/gates.py`（メイングラフの入力と始めの記録の欄の名 `FINAL_KEY`・`UNATTENDED_KEY`、最後の承認ノードの開き方の語 `FINAL_GATES`（既定 `ALWAYS`）と無人の語 `UNATTENDED`、入口の語の確かめ `check`（仕様の段と無人の組みも拒む）、始めの記録からの読み `unattended_of`、最後の承認ノードを開くかの決め `opens`、報告の頭の行の句 `head_words`、無人の run が承認ノードを推しで進むか止まるかの口 `passage`（項目を受けて進むか・止める理由・推しの答えを返す）、推しの読みの形 `Push`）と、止まった事前審査の壁打ちの行に推しの尾を付けてよいかの決め `stuck_pushable`（往復の記録の `workflows/line/src/rounds.py`）
- 約束: 始めの記録（`workflows/line/src/startrec.py` の start.json の形）の 2 つの欄。書き手はメイングラフの始めのノードの 1 か所
- 知ってよい所: 住処と、メイングラフの始めのノードの script `workflows/line/scripts/start.py`（メイングラフの入力 `INPUTS_FINAL_GATE`・`INPUTS_UNATTENDED` を受けて住処の `check` に渡し、始めの記録に置く）と、周の鎖の親のグラフ `workflows/chain/works-factory-chain.yaml`（メイングラフと同じ名の入力を宣言し、周の子へ写して渡すだけ）。読み手（メイングラフの `workflows/line/src/` の部品）は住処の口で始めの記録を読む。推しの尾の字の形の持ち主 `lib/gatemarks.py`（`push_rec`）は尾を読むだけで、その読みを `Push` にするのは住処の `row_push`、推しで進むかを決めるのは住処の `passage`。修正前と案の直しの承認ノードの script は `passage` を呼ぶだけ
- 今: 柵は、方針の語の字（住処の口 `gates.<名>` は数えない）と、住処の定数を別の名に写す形と、推しの尾の読み（`push_rec`・`row_push`）を住処と gatemarks の外で呼ぶ形（推しで進むかの決めの写し）の 3 本。既知の漏れは、メイングラフの入力の宣言と始めのノードの出口の欄を後ろへ写す `workflows/line/works-factory-line.yaml` と、承認ノードの script（`workflows/line/scripts/ask_before_fix.py`・`workflows/line/scripts/ask_final.py`・`workflows/line/scripts/ask_replan.py`）が始めの記録を読まずにメイングラフの入力を写して受ける所に、2026-11-05 の数え直しで載せたメイングラフの `workflows/line/src/` の部品・修正の block・書き手の型の共通の部品と指示の md を足した 37 ファイル 119 行
- 寄せ残し: 無人の run の決めのうち、次の 2 つは住処の口の外に置く。始めの承認ノード（`workflows/line/scripts/start.py`）は無人かの読みを口 `unattended_of` で引き、無人なら開かないだけなので残しではない
  - 最後の承認ノード（`workflows/line/scripts/ask_final.py` の `ask`）の、開くはずの時に無人の run なら needs-human で止める分かれ道。開ける理由（テストが緑でない・守りのファイルを触った…）は機械が読める推しの尾を持たないので、`passage` に渡すと理由を推しの無い項目として渡す形でしか書けず、「いつも止める」を口の中の推しの読みに隠すだけで簡潔にならない。開くかの決めはもう口 `opens` に在る
  - 判定が保留にした分かれ道の問いの推しを、無人の run が答えに採るか（`lib/gatemarks.py` の `run_push`）。無人の run で推しを採るかは呼び手が値 `takes_push` で渡すが、採る条件の残り（問いの種類と状態・推しが選択肢を名指すか・出どころと depends が開いた単位か）は問いの台帳の形の決めで、口へ移すと方針の住処が判定の問いと計画の単位の形を知る

### `gate-evidence` 試験の関門の証拠の文の行の頭

- 状態: 住処あり
- 住処: `workflows/test-gate/src/certify.py`（証拠の文 `test-gate/<mode>/evidence.md` の走らせ方・ログの行の頭 `RUN_ROW`・`LOG_ROW`。lib は workflows を import できない（E3）ので、書き手の block の `src/` が持ち、返す node の script `workflows/test-gate/scripts/result.py` がそれを通して書く。持ち主の決め `evidence-prefix-one-home`）
- 約束: 行の値は出力の欄 `suites_line`・`log` と同じ字。報告と最後の承認ノードは証拠の文を開かずに出力の欄を `lib/declared_checks.py` の `gate_values` で読む
- 知ってよい所: 住処だけ。柵の外の試験と通しの照らし（`tests/e2e/evidence.json`）は `tests/blocks/test_gate/test_test_gate.py` の `EvidenceRowsCase` が住処の定数から引くことを縛る
- 今: 既知の漏れは、2026-11-05 の数え直しで載せた `workflows/line/src/final.py`・`workflows/test-gate/src/certify.py` の 2 ファイル 2 行（`workflows/line/scripts/ask_final.py` の `tests_lines` の行は消えていた）

### `accept-round` 受け付けの回（返答を読む・拒否を控えに積む・上限で諦める・最後の回か）

- 状態: 住処あり
- 住処: `lib/rolekit.py`（受け付けの回の口 `accept_round` と、読んだ返答を受けるその本体 `accept_parsed`、その返り値の 4 つの欄 `round_outcome`、控えの誤りで落ちずに今の回を読む `current_round`、拒否の控えの唯一の書き手 `with_done`、拒否の控え `rejects-<名>.json` の読み `reject_rows`・`rejected`・`attempt`・`given_up_reason`、諦める回の数 `GIVE_UP_AFTER` と最後の回かの問い `is_last_attempt`、回数で諦めない受け付け（方針 `net`。計画と事前審査の受け付け）の届かない網の数 `NET_AFTER` と網に届いた訳 `NET_WHY`、拒否の全部のファイル `reject_file`、前の版の控えの読み替え `_legacy_rows`）
- 約束: 呼び手は `rolekit.accept_round(board, name, raw, take, reject=, on_give_up=, net=)` に返答の字と `take` を渡す。方針 `net` の拒否は `NET_AFTER` 回目で `done` になり、控えの行に `after`（`NET_AFTER`）を残す。`given_up_reason` は控えの最後の行の `after`（無ければ `GIVE_UP_AFTER`）で諦めを判じる。`take` の返り値の欄 `ok`・`reason`・`give_up`（1 回目から諦める）・`count`（false なら控えに積まない）・`kind`（控えの行に残す）を口が読み、1 回の拒否の定義は口の中にだけ在る。返り値は `take` の返り値に `done` を足した物。拒否の控え `rejects-<名>.json` が読めない・書けない時は、落ちずに `done` 真の拒否（理由「拒否の控えが扱えない」）。口の外の `rolekit.reject_file` が書く `rejects-<名>.md` が書けない時は `OSError` が呼び手まで上がる。拒まれた後の出し直しを前の答えと合わせる受け付けは、`take` の前段の `rolekit.resubmitted` で合わせた答えを `rolekit.accept_parsed` に渡す（数え・諦め・控えは口の中のまま）。take の前に今の回が要る呼び手は `current_round` で読み、控えが読めなければ口を回さずにその拒否を返す
- 知ってよい所: 住処だけ。呼び手（`lib/fixboard.py` の `accept_out`・`lib/materialkit.py` と、block の受け付けの部品 `workflows/fix/src/ruling.py`・`workflows/plan/src/take.py`・`workflows/report/src/writer.py`・`workflows/diagnose/src/judge.py` ほか）は口を引き、控えの名も諦める回の数も字で書かない
- 今: 柵は、`rolekit.with_done(` の直の呼びと受け付けの回の口の定義と `round_outcome` の `give_up` の欄の写し、`GIVE_UP_AFTER`・`NET_AFTER` との大小の比べ、拒否の控えと拒否の文の置き場の名の字、`GIVE_UP_AFTER = <数>`・`NET_AFTER = <数>` の定義と見出し「前の回の受け付けが拒んだ理由」の別の宣言の 4 本。既知の漏れは無い。TDD の段の自前の数え `workflows/fix/src/tdd.py` の `tries` と拒否の文のファイル `tdd-step-reject-{}.md` は別のサブシステムで、柵の語の形に当たらない

---

## 散らばり

### `ledger` 費用と時間の帳簿

- 状態: 散らばり
- 今: 時間 `wall_s` を、構造の目の控え（`lib/structmark.py`・`lib/eye.py`）・宣言した確かめの段（`lib/declared_checks.py`）がそれぞれの形で書いて読む。数の歯止めは表の `known` の 7 ファイル 11 行（2026-11-05 の数え直しで、構造の目の block `workflows/structure/src/` と形 `workflows/.shared/schemas/structure-state.schema.json`・見る道具の `viewer/src/runread.py` を載せた）
- 計画: まだ無い

### `ai-launch` AI の起こし方（模型・effort・道具・隔離）

- 状態: 散らばり
- 今: 模型と effort の既定だけが `lib/launchgroups.py` の群の表（`GROUPS`）に住み、グラフの YAML の AI のノードは `model:` に群の名 `'@wf-<群>'` を書くだけ（`effort:` は書かない。run ごとの付け替えは `run-model-choice`）。道具 `allowed_tools:` の行と隔離は散らばりのまま: block の試験（`tests/blocks/` の block ごとの物）はノードごとに自分の表で群と道具を縛るだけ。数の歯止めは表の `known` の 49 ファイル 125 行（`workflows/*/works-factory-*.yaml` と、武器の block の `src/render.py` ほか。2026-11-05 の数え直しで揃えた）。役の claude の会話の組（`CLAUDE_CODE_PROMPT_CACHE_TTL`）と、その会話が Agent の道具で起こす下請け（subagent）の組（`CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`）のキャッシュの寿命の既定（どちらも 5 分）は `bin/_lib/launcher.py` の `PROMPT_CACHE_TTL`・`cache_ttl` に住み、運び手は Archon の run の設定の層の env（利用者の `--config` の `env:` か対象の `.archon/config.yaml` の `env:` でその組の寿命を選んでいればその組だけ載せず、利用者の shell の env は見ず、`--adopt` の起動でも載せない。訳は `docs/design/archon.md`）。前の works の run の明示の模型 `WORKS_DEV_MODEL`・隔離の旗 `isolated` は今の木に無い
- 計画: まだ無い

### `prompt-assembly` 指示書の組み立て

- 状態: 散らばり
- 今: AI のノードの指示は `workflows/.shared/prompt.py` がノードの md に値を入れて組むが、貼るセクションの見出しを自分の定数で持つ Python が残る（承認ノードの script `workflows/line/scripts/ask_replan.py`）。見出しの宣言の型を Python に置かないことは考え `prompt-sections` の柵が見る。印「機械が貼った」は付け方がそろわないので範囲の定義には使わず、柵はその字を数えるだけ。数の歯止めは表の `known` の 1 ファイル 2 行（その script が見出しを自分の定数に写す所。2026-11-05 の数え直しで、`lib/design.py`・`lib/replan.py`・`lib/carry.py` ほかの行は消えていた）
- 計画: まだ無い

### `lang-names` 特定の言語・テストの実行器の名

- 状態: 散らばり
- 今: 役の指示書と `lib/` に特定の言語・テストの実行器の名を書かない（持ち主の決め `lang-neutral`。事実上の標準の形式の名は数えない）。今その名を持つ所は、言語ごとの読み方（`lib/impact.py`・`lib/libdocs.py`・`lib/libdocs_local.py`・`lib/libdocs_web.py`。持ち主の決めの E13 の例外）・TDD のループと実行器の口（`workflows/fix/src/common.py`・`workflows/fix/src/tdd.py`・`lib/baseline_red.py`）・起動の殻の版の確かめ（`bin/apply`・`bin/works-factory`）・コメントと docstring（波及の照らしの `workflows/plan/src/ripple.py` ほか）・役の指示書（`workflows/premises/prompts/premises.md` が生成物の止め方に Python を名指す）。数の歯止めは表の `known` の 26 ファイル 53 行（2026-11-05 の数え直しで揃えた）。新しい役の指示書が名を書けば赤になる
- 計画: まだ無い（持ち主の決めの E13 の例外は、掃除の段で言語の知識を外へ出すと書く。#765 では外へ出さなかった。外へ出す段はまだ無い）
