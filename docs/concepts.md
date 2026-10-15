<!-- coldwrite:skip 内部の設計の地図。語は冒頭の「語」のセクションで定義 -->
# 考えの住処の地図（works-factory の設計の考えが、どこに 1 つの形で住んでいるか）

状態: 2026-10-13（issue #254・PR #269）。今の works の地図（`works/docs/concepts.md`）の柵を持つ 31 の考えを 1 つずつ今の木に当て、住処が works-factory に在る考えと散らばりの考えは全部載せ、考えそのものが works-factory に無い物は下の「載せない考え」に訳を書いた。載せた考えの住処の外の当たりは、本当の漏れなら表の既知の漏れに件数と理由を置き、同じ字の別の考えに当たるだけなら語の形を狭めた。行のパスは試験（`tests/layers/test_concept_fences.py`）が在ることを確かめる（まだ無い物は「予定」と書き、試験は見ない）。

載せない考え（今の works の地図に在り、考えそのものが works-factory に無い。漏れの多さは載せない訳にしない）:

- `hinge` 境のノード: メイングラフの境のノード（h-* の名のノードと住処 darkfactory/lib/line_edge.py）は works-factory に無く、docs/design.md:472 の通りメイングラフの when: と小さな script ノード（workflows/line/scripts/ の start・redepth・collect など）が担う
- `halt` 止め札: 共有ボードの止め札 STOP と住処 halt.py は持ち込まず（持ち主の決め stop-at-gates。lib/halt.py は無い）、報告つきの止めは承認ノードの stop・reject の答え（一言が request: で始まれば止め札の扱い。lib/outcome.py・lib/seal.py）が、承認ノードの間の止めは Archon の workflow cancel が担う
- `scope` 部品の置き場と宣言: 部品の宣言のファイル manifest.json と住処 scopes.py は落とし（docs/design.md:471）、入出力の宣言は Archon の YAML の with:・returns: と出力の型が、宣言の外の書き込みは mutates_checkout: false と書き込みの出どころの突き合わせが担う（持ち主の決め declared-io）
- `injectors` 包みが足す system prompt の塊: AI を起こす包み（前の works の adapter.py の INJECTORS と --append-system-prompt）を持ってきていない（docs/design.md:474 で落とした）。system prompt を足すのは Archon の AI ノードの systemPrompt（workflows/plan-review・workflows/eyes の YAML）がノードごとに字で担う
- `replycontract` 返答の契約: 返答を本文で受けて型を確かめ出し直させる包みの旗 text-reply と replycontract.py を持ってきていない（docs/design.md:474 で包みを落とした）。返答の型は Archon の AI ノードの output_format（SDK の構造化出力 StructuredOutput）が担う
- `writes` 役の返答を共有ボードに書く規則: graphloops の engine の共有ボードと書く規則（record.py の apply_writes・rules の WRITE_OPS）を持ってきていない（docs/design.md の graphloops の写しの行で落とした）。役の返答を後ろへ渡すのは Archon のノードの出力（$<ノード>.output）と各サブグラフの script が置き場に書くファイル
- `core-seams` 写しの核の差し替えの口: 写しの核（graphloops の review-loop）が無く（lib/graphloops は engine の型検査・描き方の 7 ファイルだけ）、走る時に写しの名を替える CORE_OVERRIDES・組み手の印 rl_builder も無い。承認ノードの組み立て（gatemarks.plan_gate_items）などはグラフの script が直に呼び、写しのバイトの手直しは写しの台帳の読み口 bin/_lib/copyledger.py の ! 行が担う

## 平たく言うと（3 行）

- works-factory の設計の考え（「入口の種類」「機械の web の取得」など）ごとに、それを 1 か所で持つ部品（住処）と、その考えを知ってよい所を並べた地図。
- 住処の在る考えは、住処の外に漏れたら試験で分かるようにする（柵）。住処の無い考え（散らばり）は、今の知る場所の数が増えない歯止め（数の歯止め）を持つ。
- 直す人（人も AI も）は、設計を始める前にここを読み、触る考えの住処を使う。住処の無い考えに足す時は、散らばりを増やさない形を先に選ぶ。

## 語

- 考え（concept）: 設計の 1 つの決まりごと。名前を付けて話せる単位（例: 「入口の種類を知るのは入口の変換だけ」）
- 住処（home）: その考えを 1 か所で持つ部品。ふつうは `lib/` のモジュール（持ち主の決め `concept-home`）。lib は workflows を import できない（E3）ので、持ち主の決めが書き手の側に置いた考えは、その書き手の script（例: `gate-evidence` の `workflows/test-gate/scripts/result.py`。持ち主の決め `evidence-prefix-one-home`）。考えを変える時に触るのはここだけ、になっている所
- 約束（contract）: 住処の外の人がその考えに触れる時の形を決めたファイルか欄
- 知ってよい所（allowed places）: 住処のほかに、その考えの語・欄の名・値を書いてよい所。柵が照らす一覧は表 `docs/concepts.json` の `allowed` で、その全部を地図の行（住処・約束・知ってよい所）が字で名指す（試験が照らす）
- 漏れ（leak）: 知ってよい所の外に、その考えの語・欄の名・値が書かれていること。漏れた所は、考えが変わった時に一緒に直す必要があるのに、誰もそれを知らない所になる
- 散らばり: 住処の無い考え。同じ考えを複数の所がそれぞれの形で知っている状態
- 柵（fence）: 漏れを見つける安い試験。考えの語の形（正規表現）と知ってよい所を表に書き、表の外で語が見つかったら赤にする。今ある漏れは「既知の漏れ」として件数と理由つきで表に置き、減らす向きにだけ動かす。分かれ目の表より考えや柵を消す・知ってよい所・`exclude`・`bound` を広げる・語の形を変えるのも赤で、意図した緩めは表の `loosened` に新しい `"<鍵>": "<理由>"` の行を足した時だけ通る。道具は `lib/conceptfence.py`
- 状態: `住処あり`（住処が在り、柵を掛けられる）か `散らばり`（住処が無い）。どちらも柵を持つ
- 数の歯止め: 散らばりの考えの柵。知ってよい所が空で、今その考えを知っている所を全部既知の漏れとして件数つきで表に置く。まとめるたびに数が減り、増やす差分は試験が赤にする。表そのものも、`origin/main` から分かれた所の表より既知の漏れの件数の和が増えない

パスは全部リポジトリの根からの相対。表の `exclude`（試験・文書・`AGENTS.md` などの決まりの文書・ASF の物・借りた物と写し）の下は柵が見ない。役の指示書（`workflows/*/commands/` の md）と役の定義（`lib/agents/` の md）は柵が見る（AI に読ませる文も考えを知る所）。

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
| `deliver` | 出口（差分を専用の枝と PR にして提出する道） | 住処あり |
| `gate-evidence` | 試験の関門の証拠の文の行の頭 | 住処あり |
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
- 知ってよい所: 住処だけが網の素の口（`urllib.request`・`http.client`・`urlopen`）を使う。使う所はライブラリの文書の読み `lib/libdocs.py` と `lib/libdocs_web.py`、世界の解の `lib/worldblk.py` と `lib/worldcheck.py`、試験の結果の使い回し `lib/tree_run.py`（控え `Store` だけを使う）で、どれも住処を呼ぶ
- 今: 外の当たりは 0 件

### `cite` 名指しの形と場所の文の読み

- 状態: 住処あり
- 住処: `lib/cite.py`（標準ライブラリだけ。名指しの形 `CITE`・1 つの名指しの確かめ `problem`・決め手の文の出どころの確かめ `sources_problem`・場所の文の中の名指し 1 つ分の形 `CITE_IN_WHERE` と読み `where_cites`・引用「…」の照らし `fold`・`quotes`・`quoted_in`・`missing_quotes`）
- 約束: 名指しの形と場所の文の読み、引用を畳んで部分文字列かを見る式は住処の外に持ち直さない。住処の別名・包みも置かない（読み手は `cite.CITE`・`cite.problem` を直に引く）
- 知ってよい所: 住処だけ。読み手（`lib/conflict.py`・`lib/design.py`・`lib/fixboard.py`・`lib/fixgates.py`・`lib/gatemarks.py`・`lib/judge_accept.py`・`lib/ruling.py`・`lib/tddloop.py`・`lib/worldmark.py`）は住処の口を引き、自分の定数や関数に写さない
- 今: 柵は、住処の定数を別の名に写す形（`X = cite.Y`・`from cite import`・`import cite as`）と、消した別名・包みの名・場所の文の読みの定義の字と、住処の外で `cite.fold(` を組む形を見る。小文字の名への写しや別の名の包みは字の形で見分けられず、柵は見ない

### `prompt-sections` 指示書に機械が貼るセクションの見出しの宣言

- 状態: 住処あり
- 住処: `lib/promptsection.py`（標準ライブラリだけ。セクションの宣言 `Section`・受け手の宣言 `Receive`・宣言を並べる口 `declared_sections`）
- 約束: 受け手の側の表 `RECEIVES`（その役の指示書を組むモジュールの直下）と、出どころの 3 形 `input:<名>`・`board:<モジュール>.<定数>`・`fn:<モジュール>.<関数>`
- 知ってよい所: 住処だけ。見出しの定数は役の支度のモジュール（`lib/` の直下）で `promptsection.Section(...)` の最初の引数に置く。型と口の定義が住処の外に写されないことを柵が見る
- 今: 外の当たりは 0 件

### `outcome` run の結末

- 状態: 住処あり
- 住処: 結末の語の並び `lib/report.py` の `OUTCOMES`（10 語）と、結末の決め方 `lib/outcome.py` の `decide_outcome`（サブグラフの出力・承認ノードの答え・報告が集めた事実から 1 語を決める）
- 約束: 報告のサブグラフの返すノードの出力 `outcome` の enum（`workflows/report/works-factory-report.yaml`）
- 知ってよい所: 住処と約束だけ
- 今: 柵は結末の語の字（`"no_fix_needed"` など）を見る。`"round_limit"` は往復のループの上限の入力の名と同じ字なので、欄の鍵（`"round_limit":`）と添字（`["round_limit"]`）は数えない。既知の漏れは機械の報告 `lib/runreport.py`（止まった結末の並び `STOP_OUTCOMES` と残りの行の分け）とメイングラフの出力ノード `workflows/line/scripts/result.py`（lib を読まずに fixed を決める）の 2 ファイル 4 行

### `depth` 単位ごとの深さ

- 状態: 住処あり
- 住処: `lib/depth.py`（単位 1 つの深さ `unit_depth`・控えの形 `decide_doc`・信号での上げ `raise_doc`・run 全体の深さ `run_depth`・省く理由の文 `skip_reason`・報告の行 `lines`）
- 約束: 計画の出力 `depth`（`[{unit_id, depth, why}]`。depth は `軽量`・`標準`）と、目のサブグラフへ渡す省く理由の文（平の入力）
- 知ってよい所: 住処と、メイングラフ `workflows/line/`（始めのノードの入力 `thickness` の確かめと、直した後の上げ直しのノード `redepth`）
- 今: 既知の漏れは、計画のサブグラフの出力ノード（`lib/planfile.py` が `depth.decide_doc` で出力 depth を作る）と、修正のサブグラフの置き場（`lib/fixboard.py` の `depth.json` の写しと `redepth` が呼ぶ `depth.raise_doc`）の 2 ファイル 6 行。元はメイングラフの境のノードが持っていた所

### `features` 機能の切り替え

- 状態: 住処あり
- 住処: `lib/entry.py` の `FEATURES`（語 → 説明）・既定 `FEATURE_DEFAULTS` と読み `features_off`・`features_on`・`features_cut`・`cut_of`
- 約束: メイングラフ `workflows/line/works-factory-line.yaml` の入力 `features_off`・`features_on` と、始めのノードの出口の同じ名の欄（サブグラフへは on・off・auto の平の入力）
- 知ってよい所: 住処・約束と、入力の語を確かめて始めの記録に置く始めのノードの script `workflows/line/scripts/start.py`
- 今: 既知の漏れは、サブグラフが自分の機能の語を字で持つ所（事前審査の `lib/boardview.py` の `TREE_FEATURE`・修正の `lib/fixboard.py` の `LANE_SWITCHES`・判定の `lib/judge_accept.py` の `DEFAULT_FEATURES_CUT`・`VERIFY_FEATURE`）の 3 ファイル 5 行

### `reads` 読んだ証拠

- 状態: 住処あり
- 住処: `lib/reads.py`（記録の根と作業の場ごとの記録のファイル `reads_path`・`log_here`、記録の名 `LOG`、置き場の読んだ証拠と索引の名の口 `evidence_name`・`index_name`・`is_index`・`EVIDENCE_GLOB`、役ごとの証拠を集める `collect`、集めるノードの中の誤りを落ちた記録（`sources.hook` が `FAILED`）にして残す `guarded`・`failure_name`、役が web を引いた記録 `web_fetches`・`web_searches`）
- 約束: 住処の名の口（置き場の名を使う所はこの口から引く）と、Read のフックの記録の行の形 `{ts, session_id, agent_id, path, file_sha, bytes, partial, partial_why, tool_use_id}`（Agent・WebFetch・WebSearch は path を持たない形）
- 知ってよい所: 住処・Read のフックの殻 `bin/_lib/record-read.py`・各サブグラフの集めるノードの script `workflows/fix/scripts/fix_reads.py`・`workflows/plan/scripts/plan_reads.py`・`workflows/plan-review/scripts/review_reads.py`。記録の置き場の決め方（鍵・控え・片付け）は書き込みの記録の `lib/writelog.py` と共にする
- 今: 外の当たりは `lib/writelog.py` の docstring の 1 行（置き場の決め方を共にする相手として記録の名を述べる）

### `conflict` 食い違いの申し出

- 状態: 住処あり
- 住処: `lib/conflict.py`（申し出の形 `ITEM_SCHEMA`・`CONFLICTS_SCHEMA`、欄の名 `FIELDS`（`WHY_FIELD`・`WHICH_FIELD`・`KIND_FIELD` を含む）、申し出の種類 `DIV_KINDS`、機械の確かめ `problems`、止めた単位の積み `park`、出どころの語 `SOURCES`（組どうしの合わせの申し出 `JOIN_SOURCE` を含む）、裁定の語 `DECISIONS`（判定のやり直し `REJUDGE` を含む）・`FIX_DECISIONS`、直す義務から外す単位 `held_by_rulings`）
- 約束: 住処の定数の表（申し出の欄と裁定の語）と、修正役の返答の欄 `conflicts` の形（`workflows/fix/works-factory-fix.yaml` の `output_format` に字で書く）
- 知ってよい所: 住処と、申し出を書いて裁く修正のサブグラフ（`workflows/fix/`・修正の受け付けの申し出の取り込み `lib/fixboard.py`・TDD のループ `lib/tddloop.py`・裁定のループ `lib/ruling.py`・組の合わせの直し `lib/clash.py`（組どうしの合わせの申し出を積む。欄の名は住処の `clash_claims` で組み、字を写さない））
- 今: 外の当たりは、案の直しの事前審査と項目のセクションに申し出を貼る `lib/boardview.py`・`lib/planfile.py` と、`lib/querytest.py` の docstring と、修正役の申し出の返し方を述べる素材集めの局所の審査の指示書 `workflows/judge/commands/material-local-review.md` の 4 ファイル 7 行

### `lanes` 並べの組

- 状態: 住処あり
- 住処: `lib/lanekit.py`（組の分け方 `groups`（タグを共にする物どうしの組。つながりは推移的）・当てた結末 `Merge`・組を順に当てる `merge_in_order`）
- 約束: 住処の口の形（`groups` の返す並び・`Merge` の欄 `why`・`patch`・`names`・`unioned`・`clash`・`merge_in_order` に渡す `merge_one(lane, earlier)`）。何を 1 つの組に当てるか（子の差分を 3 方向で当てる `lib/unittrees.py` の `apply`）は呼び手が渡す
- 知ってよい所: 住処だけ。呼び手（組を作る `workflows/fix/scripts/prep.py`・子の差分を当てる `workflows/fix/scripts/join.py`・`lib/fixboard.py`）は住処の口を引き、分け方・当てる順のループ・結末の語を写さない
- 今: 外の当たりは 0 件

### `marks` 返答の足し欄

- 状態: 住処あり
- 住処: `lib/marks.py`（標準ライブラリだけ。種の表 `KINDS`＝ノードか役 → 行の在り処・共有ボードの控えの名・置き場、と手順の口 `add`（役の型に足す）・`rows`・`split`（受け付けが共有ボードへ渡す前に外す）・`path_of`・`write`・`load`（控えに置く・読み戻す））
- 約束: 種の表 `KINDS` の控えの名（欄を持つモジュールは `marks.KINDS[種].file` で引く）と、控えのパスを組む `path_of`
- 知ってよい所: 住処だけが控えの名を書き、欄を手で足す・外す。欄の意味（欄の型・欠けと誤りの検査・控えの中身の形・読んだ後の使い方）は欄を持つモジュール（`lib/gatemarks.py`・`lib/planmarks.py`・`lib/deltamarks.py`・`lib/converge.py`・`lib/querytest.py`・`lib/outpurpose.py`・`lib/prcheck.py`・依頼の解き方 `means` の `lib/worldmark.py`）が持ち、手順は住処を呼ぶ
- 今: 控えの名を字で持ち直す所（`lib/judge_accept.py`・`workflows/plan/scripts/plan_collect.py`）、控えのパスを `path_of` を通さずに組む所（`lib/judge_accept.py`・`lib/planfile.py`・`lib/refix.py`）、欄を手で外す所（修正役の欄 `lib/fixboard.py`・並行 PR の `lib/judge_accept.py`・手直しの `bash_writes` の `lib/writes.py`）が残る（柵の表の既知の漏れ）。`lib/judgeverify.py` は自分で組む裏取りの型で、同じ字の形の別の物

### `plan-scope` 修正案の項目の範囲の照らし

- 状態: 住処あり
- 住処: `lib/planrange.py`（項目の範囲 `inside`・`out_of_scope` の当たり `oos_hit`・`oos_hit_for`・範囲の相談の合意 `with_agreed`・パスを結ぶ項目 `owner`・許しのパス `permit_paths`・単位に結べないパスの外れ `outside`・共有ボードで照らす `check_paths`）
- 約束: 修正案の項目の欄 `allowed_paths`・`out_of_scope`（欄の型と読みは `lib/planmarks.py`）
- 知ってよい所: 住処と、glob の当て方の下回りと項目の欄の読みを持つ `lib/planmarks.py`（`glob_match`・`test_paths`）。使う所は修正の受け付けの照らし `lib/planscope.py`・手直しの受け付け `lib/refix.py`・波及の照らし `lib/ripple.py` の `_covered` で、どれも住処を呼ぶ
- 今: 同じ当て方を手で書く所が残る（`lib/holeties.py`・`lib/consult.py`。柵の表の既知の漏れ）。`lib/protect.py` は守りのファイルの型を同じ下回りで当てる別の考え

### `test-files` テストのファイルの見分け

- 状態: 住処あり
- 住処: 名の慣習は `lib/impact.py` の `is_test`（`TEST_NAME`・`TEST_STEM`。言語の表でなく名の形）、宣言と慣習を合わせた見分けは同じ `impact.py` の `is_test_file(path, declared)`。TDD のループの宣言の組は `lib/tddloop.py` の `declared_test_files`
- 約束: 文書の宣言は対象の git の属性 `linguist-documentation`（`impact` が読む）
- 知ってよい所: 住処だけが名の型を書く。`lib/tddloop.py` の `PYTEST_FILE` は pytest の既定の python_files（実行器が pytest の時の名指しの型）で、同じ住処に置く。使う所（`lib/fixgates.py`・`lib/ripple.py`・`lib/planfile.py`・run の広さを数える `lib/depth.py`）は住処の口を呼び、宣言と慣習を合わせる式を自分で組まない
- 今: `lib/judge_accept.py` の `GATE_FILE_PATTERNS`（検証ゲートの定義のファイルの広めの型）は別の考えで、テストの名の型の字を含む（柵の表の既知の漏れ）

### `red-check` TDD の赤の判定（事実と失敗の文の引用）

- 状態: 住処あり
- 住処: `lib/tddloop.py` の `red_check`（赤の事実の判定。正本 `lib/baseline_red.py` の `red_problems` を中で呼び、役の引用と理由の照らしを足す）と `QUOTES_FIELD`（test の段の返答の欄と単位の記録の欄の名）、ループの記録した赤の木で名指しを走らせ直す `red_rerun`。引用を寄せた後の部分一致で照らす口は `lib/cite.py` の `quoted_in`
- 約束: 出口の欄 tdd の単位の行 `lib/tddloop.py` の `FIELDS`。役の務めの置き場は `workflows/fix/commands/fix-rules/tdd.md` の test の段（引用と理由を書く務め・走る前の失敗の直し方）
- 知ってよい所: 住処・赤と緑の判定の正本 `lib/baseline_red.py`（`red_problems` の定義）・`lib/cite.py`・`lib/report.py`（出口 tdd の単位の行を読み、引用と理由を報告の行に並べる）・`workflows/fix/works-factory-fix.yaml`（TDD の役の返答の型 `&tdd_reply` が欄 `red_quotes` を宣言する。型の正本は output_format だけ、持ち主の決め `io-in-output-format`）。事後の関門（`lib/fixgates.py`）と試験の関門の script（`workflows/test-gate/scripts/`）は `red_check`・`red_rerun` を呼ぶだけで、赤の式を持たない
- 今: 外の当たりは 0 件。機械が見るのは言語に依らない事実（名指しが走った・failure で落ちた・名指しの外は元のまま）だけで、「期待どおりの理由で落ちたか」は役が結末の失敗の文を引いて書き、機械は引用が結末の failure の文に在るかだけを照らす

### `carry-over` 次の run への持ち越し

- 状態: 住処あり
- 住処: `lib/carry.py`（依頼の容器の欄の名 `KEYS`・`ANSWER_KEYS`・`PRIOR_KEYS`、下書きの印 `DRAFT_KEYS` と `is_draft`・`draft`、共有ボードの根のファイルの名 `NEXT_REQUEST_FILE`・`PRIOR_FAILURES_FILE`・`PRIOR_IN_FILE`、依頼の解き方 `parts`・`without_prior`・`carry_ci`、次の依頼の中身 `compose`・行の鍵 `row_key`、独立の目 R2 の作り直しの行 `REDESIGN_WHERE`・`is_redesign`、照らしてから置く `place_prior`、役に貼るセクション `prior_section`、前提の検算の実測 `carried_constraints`）
- 約束: `lib/next-request.schema.json`・`lib/prior-failures.schema.json`（住処が読み、書き手は書く前に照らす。欄の名の定数と Schema の欄が揃うことは試験 `lib/tests/test_carry_home.py` が縛る）
- 知ってよい所: 住処と約束だけ。何を運ぶかは書き手の側が決め、形は住処を呼ぶ（報告 `lib/runreport.py`・承認ノード `lib/gatemarks.py`・目的の外の所見 `lib/outpurpose.py`）。読み手（入口の始めのノード `workflows/line/scripts/start.py`・`lib/judge_accept.py`・`lib/planfile.py` ほか）も住処の名と口を引く
- 今: 柵は持ち越しのファイルの名・下書きの印・住処の定数の字と、前の失敗を欄の名の字で直に読む形（`["prior_failures"]`・`.get("prior_failures")`）。`"prior_failures":` の鍵や並びの字はグラフのノードの入出力（前の失敗のファイルのポインタ）の名と同じ字なので数えない。住処の外の当たりは、報告の入出力のポインタを字で読み書きする `lib/runreport.py` の 3 行と `workflows/report/scripts/facts.py` の 2 行で、字の形で中身の直の読みと分けられないので既知の漏れに置く。容器のほかの欄の名 `findings`・`answers` などは柵に入れず、呼び手が `carry.PRIOR` などの定数を引く決まりだけで守る

### `world` 世界の解（問題の類ごとの定石と、依頼の解き方との比べ）

- 状態: 住処あり
- 住処: `lib/worldmark.py`（行の欄の名 `FIELDS`・行のファイルの名 `WORLD_FILE`・控えの名 `STATE_FILE`・語 `VERDICTS`・`BASES`・名指しの句 `NOT_WEB`・先例の出どころの頭の字 `SOURCE_PREFIX`・読み書き `rows`・`read`・`write`・`stage_rows`・頭のセクション `section`・答えの要る行 `needs`・`need`・`unanswered`・依頼の解き方との比べの文 `challenges`・承認ノードの軸 `world_ok`・承認ノードの行 `gate_line`・報告の行 `report_lines`・先例の出どころの照らし `ref_problems`・依頼の解き方の足し欄 `MEANS` と `split_means`・`write_means`・`means_of`）
- 約束: 行の欄と語は住処の定数 `FIELDS`・`VERDICTS`・`BASES`（試験 `lib/tests/test_worldmark.py` が縛る）。住処の docstring が名指す行の型 world-row.schema.json は works-factory に無い
- 知ってよい所: 住処と、世界の解の段のサブグラフの中身 `lib/worldblk.py` とノードの口 `workflows/judge/scripts/world_*.py`（行と控えを書く出口 world_finish を含む）。読み手（`lib/judge_accept.py`・`lib/planblk.py`・`lib/planfile.py`・`lib/planmarks.py`・`lib/gatemarks.py`・`lib/boardview.py`・`lib/runreport.py`）は住処の口を引く
- 今: 柵は行のファイルと控えの名の字。住処の外の当たりは、判定のノードの中身 `lib/judge_accept.py` の docstring 2 行と報告 `lib/runreport.py` の docstring 1 行が置き場の名を字で説明する所で、既知の漏れに置く（コードは住処の定数を引く）

### `stop-reasons` 止めの理由

- 状態: 住処あり
- 住処: `lib/stopby.py`（標準ライブラリだけ。機械の語の頭 `HEAD`（`works:`）と頭の読み `is_line`、段の語と 2 つ以上の持ち主が共に書く語の表 `REASONS` とその定数 `ADAPTER`・`LINE_SCRIPT`・`REJUDGE` など、人の止めの頭 `HUMAN`、人の答えを待つ語 `WAITING`、自分だけの語を足す口 `declare` と `declared`）
- 約束: 語の字は共有ボード・報告・固定材料に残るので変えない（試験 `lib/tests/test_stopby.py`）
- 知ってよい所: 住処だけ。書き手は住処の定数を引き、自分の定数に写さない
- 今: 柵は語の字（`"works:<名>"`・頭の `"works:"`）と、住処の定数をそのまま別の名に写す形（`X = stopby.Y`・`from stopby import`・`import stopby as`）。既知の漏れは、落ちない返しのノードが lib を読めない時のために語を字で持つ 4 か所（`workflows/.shared/boundary.py`・`workflows/judge/scripts/verdict.py`・`workflows/line/scripts/collect.py`・`workflows/line/scripts/result.py`）と、定数の写し 2 か所（`lib/outcome.py` の `WAIT_WORDS`・`lib/report.py` の `HUMAN_BY`）

### `start-record` 始めの記録 `r1/start.json`

- 状態: 住処あり
- 住処: `lib/startrec.py`（標準ライブラリだけ。置き場の名 `NAME`・`REL` と `path`、読み口 `read`・`load`、書き `write`・写し `adopt`、入口の入力の形の読み `shape`・`diff_empty`・`requests`、読む版と差分の根 `read_rev`・`diff_base`、入口の文 `words`、命令の版の 1 行 `cli_version`）
- 約束: 住処の口だけ（置き場の名と読む口はここ 1 つ。記録の型の Schema は works-factory に無い。試験 `lib/tests/test_startrec.py`）
- 知ってよい所: 住処だけ。書き手はメイングラフの始めのノード `workflows/line/scripts/start.py`（`startrec.write`）で、サブグラフは `startrec.adopt` で写し、読み手は `startrec.read`・`startrec.load` を引く
- 今: 柵は置き場の名を字で書く形・置き場の名の別名（START_REL・START_FILE）・別の読み口（start_doc の関数）。既知の漏れは、判定の置き場に始めの記録の写しを同じ名で置く `lib/judge_accept.py` の `START_FILE` とそれを引く判定の支度の 2 つの script、最後の承認ノード `workflows/line/scripts/ask_final.py` の包み `start_doc`（4 ファイル 12 行）

### `human-gates` 人の承認ノードと無人の方針

- 状態: 住処あり
- 住処: `lib/gatepolicy.py`（標準ライブラリと始めの記録だけ。メイングラフの入力と始めの記録の欄の名 `FINAL_KEY`・`UNATTENDED_KEY`、最後の承認ノードの開き方の語 `FINAL_GATES`（既定 `ALWAYS`）と無人の語 `UNATTENDED`、入口の語の確かめ `check`（仕様の段と無人の組みも拒む）、始めの記録からの読み `final_mode`・`unattended`、最後の承認ノードを開くかの決め `opens`、報告の頭の行の句 `head_words`）
- 約束: 始めの記録（`lib/startrec.py` の start.json の形）の 2 つの欄。書き手はメイングラフの始めのノードの 1 か所
- 知ってよい所: 住処と、メイングラフの始めのノードの script `workflows/line/scripts/start.py`（メイングラフの入力 `INPUTS_FINAL_GATE`・`INPUTS_UNATTENDED` を受けて住処の `check` に渡し、始めの記録に置く）と、周の鎖の親のグラフ `workflows/chain/works-factory-chain.yaml`（メイングラフと同じ名の入力を宣言し、周の子へ写して渡すだけ）。読み手（`lib/gatemarks.py`・`lib/boardview.py`・`lib/runreport.py`）は住処の口で始めの記録を読む
- 今: 柵は、方針の語の字（住処の口 `gatepolicy.<名>` は数えない）と、住処の定数を別の名に写す形の 2 本。既知の漏れは、メイングラフの入力の宣言と始めのノードの出口の欄を後ろへ写す `workflows/line/works-factory-line.yaml` と、承認ノードの script（`workflows/line/scripts/ask_before_fix.py`・`workflows/line/scripts/ask_final.py`・`workflows/line/scripts/ask_replan.py`）が始めの記録を読まずにメイングラフの入力を写して受ける所（25 行・4 ファイル）

### `deliver` 出口（差分を専用の枝と PR にして提出する道）

- 状態: 住処あり
- 住処: `lib/deliver.py`（標準ライブラリと `lib/forge.py`・`lib/oneline.py` だけ。入力の語 `WORDS`・`PR` と確かめ `check`、始めの確かめ `preflight`、押す先の枝 `BRANCH_PREFIX`・`branch_of`、提出 `submit`（柵・一時の物の置き場での commit・push・PR）、読み戻し `readback`、host の gh の探し方 `host_gh`、gh を呼ぶ唯一の口 `_gh` と通す動詞の固定の並び `VERBS`、報告の行 `report_lines` と冒頭の句 `head_words`）
- 約束: 入力 `deliver`（空か `pr`。周の鎖が最後の差分を渡す形 `handoff` は、これに加えて `placed`・`base_rev` を受ける）と出力の欄 `delivered`（`{ok, branch, commit, url, reason}` か null）。欄の正本は `workflows/merge/works-factory-merge.yaml` の入力と出力の型で、メイングラフと鎖はそれを受けて通すだけ
- 知ってよい所: 住処と、約束の 3 つの YAML（`workflows/merge/works-factory-merge.yaml`・`workflows/line/works-factory-line.yaml`・`workflows/chain/works-factory-chain.yaml`）と、語を読む・渡す script（`workflows/merge/scripts/merge.py`・`workflows/line/scripts/start.py`・`workflows/chain/scripts/chain_start.py`・`workflows/chain/scripts/result.py`）。報告 `lib/runreport.py` は住処の口 `deliver.report_lines`・`deliver.head_words` を引くだけ
- 今: 柵は、出口の語を読む・渡す形（住処の口 `deliver.<名>` は数えない）と、住処の定数を別の名に写す形の 2 本。外の当たりは 0 件。gh の探し方は `bin/_lib/hostgh.py` の `find_gh`・`bin/_lib/no-post-bin/works-gh` の `real_gh` と同じ事を持つ写しの 3 つ目（lib は bin を import できない。E3）。外へ書くノードは merge の 1 つで、`tests/layers/scan.py` の E6 の語に口の呼び `deliver.submit` を数える

### `gate-evidence` 試験の関門の証拠の文の行の頭

- 状態: 住処あり
- 住処: `workflows/test-gate/scripts/result.py`（証拠の文 `test-gate/<mode>/evidence.md` の走らせ方・ログの行の頭 `RUN_ROW`・`LOG_ROW`。lib は workflows を import できない（E3）ので、書き手の script が持つ。持ち主の決め `evidence-prefix-one-home`）
- 約束: 行の値は出力の欄 `suites_line`・`log` と同じ字。報告と最後の承認ノードは証拠の文を開かずに出力の欄を `lib/declared_checks.py` の `gate_values` で読む
- 知ってよい所: 住処だけ。柵の外の試験と通しの照らし（`tests/e2e/evidence.json`）は `tests/workflows/test_test_gate.py` の `EvidenceRowsCase` が住処の定数から引くことを縛る
- 今: 既知の漏れは、最後の承認ノードの文のログの行（`workflows/line/scripts/ask_final.py` の `tests_lines`）が同じ字の頭を持つ 1 行。証拠の文の行ではない別の文

---

## 散らばり

### `ledger` 費用と時間の帳簿

- 状態: 散らばり
- 今: 時間 `wall_s` を、構造の目の控え（`lib/structmark.py`・`lib/eye.py`・`lib/planfile.py`・`workflows/plan/scripts/plan_collect.py`）・計画の記録の表示（`lib/boardview.py`）・宣言した確かめの段（`lib/declared_checks.py`）がそれぞれの形で書いて読む。数の歯止めは表の `known` の 6 ファイル 15 行
- 計画: まだ無い

### `ai-launch` AI の起こし方（模型・effort・道具・隔離）

- 状態: 散らばり
- 今: 模型と effort の正本は役の定義の前付け（`lib/agents/`）と、グラフの YAML の AI のノードの `model:`・`effort:`・`allowed_tools:` の行。YAML の行は役の定義と結ばれておらず、試験（`tests/workflows/test_judge.py` ほか）はノードごとに自分の表で値を縛るだけ。数の歯止めは表の `known` の 13 ファイル 152 行（`workflows/*/works-factory-*.yaml` の 7 ファイル 141 行・役の定義の前付けの 5 ファイル 10 行・道具を字で述べる指示書 1 行）。前の works の run の明示の模型 `WORKS_DEV_MODEL`・隔離の旗 `isolated` は今の木に無い
- 計画: まだ無い

### `prompt-assembly` 指示書の組み立て

- 状態: 散らばり
- 今: 写しの指示書を描く式は `lib/rolekit.py` に在るが、「頭のセクション → 写しの本文 → 役の定義 → 前の拒否」の並べは役の支度のモジュールごとに組む（`lib/planblk.py`・`lib/planfile.py`・`lib/design.py`・`lib/replan.py`・`lib/boardview.py` ほか）。貼るセクションの見出しの宣言は考え `prompt-sections` に寄せた。印「機械が貼った」は付け方がそろわないので範囲の定義には使わず、柵はその字を数えるだけ。数の歯止めは表の `known` の 11 ファイル 17 行（独立の目の比べの指示書 `workflows/eyes/commands/r2-compare.md` の見出しの 2 行と、承認ノードの script `workflows/line/scripts/ask_replan.py` が見出しを自分の定数に写す 1 行を含む）
- 計画: まだ無い

### `lang-names` 特定の言語・テストの実行器の名

- 状態: 散らばり
- 今: 役の指示書と `lib/` に特定の言語・テストの実行器の名を書かない（持ち主の決め `lang-neutral`。事実上の標準の形式の名は数えない）。今その名を持つ所は、言語ごとの読み方（`lib/impact.py`・`lib/libdocs.py`・`lib/libdocs_local.py`・`lib/libdocs_web.py`・`lib/ripple.py`。持ち主の決めの E13 の例外）・TDD のループと実行器の口（`lib/tddloop.py`・`lib/baseline_red.py`）・起動の殻の版の確かめ（`bin/apply`・`bin/works-factory`）・コメントと docstring。・役の指示書（`workflows/fix/commands/fix-rules/common.md`・`workflows/judge/commands/premises.md` が手元の依存と生成物の止め方に Python を名指す）。数の歯止めは表の `known` の 18 ファイル 44 行。新しい役の指示書が名を書けば赤になる
- 計画: まだ無い（持ち主の決めの E13 の例外は掃除の段で言語の知識を外へ出す）
