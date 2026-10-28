<!-- coldwrite:skip 設計の一部。語は docs/design/README.md の頭の語の一覧で定義 -->
# 見る道具（`viewer/`）の設計書

- 何の話か: 工場の作り（graph と block の図・指示の md）と、run（工場の 1 回の実行）の一覧と再生を、人が 1 枚で見る道具の設計。置き場の決めは持ち主の決め `viewer-in-repo`、決まりは `viewer/AGENTS.md` の E25、計画は `docs/plans/2026-10-28-viewer.md`（3〜7 章と 9 章の PR の切り方）。
- 今在る物（計画の PR T1〜T3）: 置き場・層の地図の行・読む部品（`src/shape.py`・`src/runread.py`・`src/session.py`）・1 枚の HTML の組み立て（`src/page.py`・雛形 `page.tpl.html`・配置の道具 elkjs の止め `elkjs.json`）・日本語の写し（`src/ja.py` と訳の控え `ja/paragraphs.json`。6.6）と、ページを書く入口 `flowview.py`。

## 1 E11 の 3 つの答え

1. Archon が持っているか → 半分持っている。止めた Archon の Web の画面（`packages/web/src/experiments/console/`。`archon serve` で起こす常駐のサーバー）は、run の一覧・run の詳細とログ・ノードの状態の図・承認ノードへの答えを持つ。無い物は、block と graph の入れ子で畳んだ図（Archon の図は `include:` を開いた平たい id で並ぶ）・工場の全部の graph の一覧と設計書と port・指示の md と組んだ値と日本語の写し・Claude Code の会話の中。持ち主の答え（計画の 10 章の問い 3「なんか見にくいんだよね。Archonの画面。気にしなくていいよ」）で、重なる所も run の一覧と run ごとのログは見る道具が持つ。走っている run の追い続けと承認の答えは、読むだけ・サーバーなし（E25 の 2・3）から持たない。
2. ASF が持っているか → 持っていない。止めた Archon の `.archon/workflows/sdlc/` に run を図や HTML で見る物は無い。HTML を作る物は `intake/scripts/bench/page.ts` の 1 つ（ベンチの結果を評価のページにし、手元の小さなサーバーが頼みのたびに作って採点を受ける物）で、読むだけ・サーバーなしの 1 枚の逆なので型は採らない。
3. 本当に要るか → 要る。ただし工場の生産の外の物として。keep-essence（`docs/design/README.md` の 10 章）のどれにも当たらず、工場の中の誰も読まない。`MISSION.md` の持ち主のエッセンス「グラフそのもの」と、1 回の run でそれがどう動いたかを持ち主が 1 枚で見る口が無い。元の works と graphloops に同じ場面の物は無い。

## 2 層と頼り

- 層の地図 `docs/layers.json` の層 `viewer`（`may_use` は `shell`・`shared`・`lib`）。どの層の `may_use` にも入らない。
- 殻（`shell`）に頼るのは、run の家を殻と同じ順に引くため。読む殻の口は `bin/_lib/launcher.py` の `target_root`・`run_home`・その 2 つが止まる時に投げる `Stop`（見る道具は受けて文を出し、終了の値 2 で止まる）と、`bin/_lib/isolate.py` の `DIRS` と、`bin/_lib/place.py` の `cache_dir`（elkjs を殻と同じ取り置きの置き場に置く）の 5 つ（`bin/AGENTS.md` に同じ 5 つを書く）。`target_root` を通すのは、殻が `--cwd` を実のパスと git の根に直してから `run_home` に渡すため（相対のパス・対象の下のフォルダ・symlink で違う家を引かない）。
- `lib` は `lib/runlog.py`（Archon の spend の測りの読み `measurement`・`tokens` と、記録の行の名の一部）と、網の口 `lib/webget.py`（elkjs の取り寄せ）を使う。`shared` は日本語の写しを組む口（`workflows/.shared/prompt.py` の `compose`）と、値の記録の在り処を node の道から引く口（`workflows/.shared/ports.py` の `include_folders`）に使う（6.6）。
- 照らし: 見る道具へ頼らない向きは `tests/layers/test_viewer_apart.py`（E25 の 1）、`lib/` が見る道具を import しない向きは `tests/layers/test_lib_blind.py`（地図から頭のフォルダを作る `scan.LAYER_IMPORT` に `viewer` が入る）。見る道具自身の `may_use` は機械で照らさない: import の照らしは頭のフォルダの単位で、`may_use` の 3 つの層の頭（`bin`・`workflows`・`lib`）がどれも許されるので照らす字が無い。block と graph の中の物を import しないことは人が見る（YAML と md と script の docstring を字として読むのは見る道具の役目で、頼りに数えない）。

## 3 起こし方とデータ

工場の clone の根から `uv run --isolated python3 viewer/flowview.py [--target <対象> [--run <run の id か頭の字>]] <出力の html>`。

- `--target` が無ければ今の木の作りだけを出す。在れば run の家の親の run の一覧を入れ、`--run` が無ければ一番新しい親の run を見る。
- 出力は工場の clone の下を拒む（ページに対象の字と会話の中身が入る）。拒みの文は見る道具が自分で持つ（`launcher.refuse_in_factory` は run の家のための文で、意味が合わない）。
- 出力は 1 枚の HTML（6.5）。初めての 1 回だけ elkjs を網から取る。
- データの欄: `made_at`（作った時刻）・`commit`・`target`・`runs`（一覧）・`run`（選んだ run）・`shape`（図の作り）・`shape_from`（`run-copy` か `tree`）・`unmatched`（図に当たらないノードの道）・`texts`（会話の字を 1 つにした表。会話の欄は番号で指す）。

## 4 作りの読み（`src/shape.py`）

- 根（pack のフォルダ）を引数で受け、今の木 `<clone>/workflows` と run の写し `<写し>/project/.archon/workflows/<pack>` を同じ形で読む。
- ノードの読み分けは種類の鍵（`loop_group`・`include`・`workflow`・`approval`・`wait`・`prompt`・`command`・`loop`・`cancel`・`bash`・`script`）のどれか 1 つ。0 個か 2 個以上は読み分けられない物として `problems` に出す。AI のノードの md（`prompts/<id>.md`）・script のノードの script（`scripts/<名>.py`）が無い物と、工場の名の頭で始まるのに木に無い `include:`・`workflow:` の先も `problems` に出す。工場の名の頭で始まらない `workflow:` の先（Archon 同梱の `archon-pr`）は工場の外の graph として印を付ける。
- 記録のノードの道（`a__b.c`。`__` は include で開いた子、`.` は `loop_group` の本体）を、`locate` が include と `workflow:` の先の graph へ辿って図の所に当てる。

## 5 記録の読み（`src/runread.py`）

- run の家の `archon-home/archon.db`（名は `isolate.DIRS`）を読むだけで開く。run の一覧は run の表の親の行（`parent_run_id` が空）だけを読み、ログは読まない。行は id・グラフの名・状態・止まっている承認ノード（状態が `paused` の run だけ。DB の `node_suspended` の後に終わりの無いノード。止めた・放棄した run は `node_completed` を書かずに `cancelled` になるので、状態で絞る）・始め・かかった秒・費用（metadata の `total_cost_usd`）・落ちの訳の頭の 1 行（DB の `workflow_failed`）。
- 選んだ run の記録は、DB の行の `output_root` から `logs/<run>.jsonl` を読む。子の run は DB の `parent_run_id` と metadata の `parent_node_id` で辿り、子の出来事の道の頭に親のノードの道を足す。run の写しは `<output_root>/workflow-source/runs/<run>/project/.archon/workflows`。写しが無い run は今の木で読み、`shape_from` を `tree` にする。
- 出来事はノードの起動（`execution.invocation.id`）ごとに 1 つ: 始めと終わり・状態（走り中・待ち・済み・落ち）・落ちた時の誤りの字（`node_error` の `error`）・費用（`accounting` が `node` の行だけ。束ねた行は数え直さない）・模型とトークンと往復の数・道具の呼び出し（`provider_event` の `tool_call` と `tool_call_update` を試み〔`attemptId`〕で結ぶ）・script と bash の出力の終わり（`exec_output`）・出力（DB の `node_completed` の `node_output`）と、出力が指す run の置き場の小さなファイル・その run の置き場の根（`artifacts`。日本語の写しが値の記録を引く。6.6）。
- 行の型と道具の出来事の型は、止めた Archon の型の和の全部を読む型と読まない型（訳つき）に分けて持つ。知らない型の行・ノードに当たらない道具の出来事は `unread` に数え、黙って落とさない。走り中の run は `live` と作った時刻を出す。答えを待つ run（状態が `paused`）には答える殻の命令の 1 行（`answer`）を付ける。答えが入って次へ進む前の間（Archon は答えを run の metadata の `wait` に書くだけで、状態は `paused` のまま `node_completed` も書かない）のノードは待ちに数えない（Archon の `runAttention` と同じ。名は `schemas/workflow-run.ts` の `workflowWaitStepName`）。承認ノードの答えはノードの出力（`wait: attention` の `{decision, text}`）から読む（`gate_decision` の行は工場が使わない古い `approval:` だけが書く）。

## 6 会話の記録の読み（`src/session.py`）

- 隔離した Claude Code の設定（`claude-config/projects/`）の中から、記録の `binding.sessionPreview`（会話の id の頭）で会話の記録を探す。Claude Code が消した古い記録は結べない。
- system と道具の一覧は `api-request-shape`、添え書き（system の片と `<system-reminder>` の片）は `api-request-blob` から取る。この 2 つの型が普通の利用者の Claude Code でも出るかは確かめていない。型の行が在ったかを `recorded` に持ち、無ければページは欄を空にせず「記録に無い」と出す。
- Claude Code の版は工場が止めていないので、記録の形は試験で照らさない（人が見る）。読まない型の行は型ごとに数えて返す。

## 6.5 ページ（`src/page.py`・`page.tpl.html`・`elkjs.json`）

- ページは 1 枚で完結する（E25 の 3）。データは雛形の `<script type="application/json">` に、JSON の字の `<` を全部 `\u003c` にして埋める（記録の字の `</script>` や `<!--` が script の中身を閉じない）。elkjs の bundle は次の `<script>` に字のまま埋め、`</script` だけを崩す。雛形の印は 1 度ずつ埋め、埋めた字の中の印の字は埋め直さない。
- elkjs（計画の 4 章の案 E1）: 版と tarball の照らしの値（npm の登録所の `dist.integrity`。tarball の sha512）を `viewer/elkjs.json` に止める。版 0.10.0 は、窓口の手元の見る道具が使ってきた bundle（sha256 の頭 `48d338d5aeddd950`）と同じ物だったので選んだ。tarball は利用者のキャッシュ（`place.cache_dir` の下の `viewer/elkjs-<版>/`）に元の名のまま置き、読むたびに照らす。取った物もキャッシュの物も、合わなければページを書かずに止まる。網に届かない時は、置くべきパスと照らしの値を出して止まる。ページには bundle の前に、版・license（EPL-2.0）・取った所と、tarball の `package/LICENSE.md` の字を注で置く。
- 画面は 4 つ: 図（graph と block の一覧・elk で上から下に並べたノードの図・ノードを押すと板に作りとこの run の出来事・block と子の run は 2 度押しで中へ）・run の一覧（行ごとに、その run のページを作る命令の 1 行。計画の 3.5）・ログ（ノードの出来事を時刻順に。子の run・飛んだノード・繰り返しの終わりの確かめ・出力が指すファイル。走り中は「ここまで」）・読めなかった物（作りの問題・図に当たらないノード・記録の読めなかった行・会話の記録の読まない行）。記録の字は全部 `textContent` で置き、HTML として読まない。
- 図の出来事は、同じ graph が何度 include されても、その graph の所に全部寄せる（include の文脈ごとに分けるのは見た目の磨きで回す）。

## 6.6 日本語の写し（`src/ja.py`・`ja/paragraphs.json`）

- 日本語の写しは、AI のノードへの英語の指示を段落ごとに日本語に訳した、人が読むための射影で、LLM には渡さない（持ち主の決め `prompt-values-for-viewer`・`viewer-in-repo` の 4）。見るたびに LLM で訳さず、訳の控え（段落の字の sha1 の頭 16 字を鍵、訳を値にした JSON）から引く。
- 控えは 2 か所（計画の 5.2 の案 J1）: 工場の指示の md（pack の `<block>/prompts/` と `.shared/prompts/`）の段落の訳は `viewer/ja/paragraphs.json` に入れる。それ以外（Claude Code の字・run の時に入った字。対象の字を含みうる）は利用者のキャッシュ（`place.cache_dir` の下の `viewer/ja-cache.json`）に置く。引く時は 2 つを合わせ、リポジトリの方が勝つ。
- 段落は、空の行と組み立ての印の行（段落の選びの印・道具の印・断片だけの行）で区切った行の塊。英字が 40 字を超え、かなが英字の 3 分の 1 未満の塊だけを訳す。訳は、差し込み口（`{name}`・`{shared:…}`・`{part:…}`）と字の `{{`・`}}` と印の頭の字を英語と同じだけ持ち、印の行を持たない物だけを使う。合わない訳は取り込まず、組む時も英語のまま残すので、写しの md の木は英語の木と同じ値と段落の選びで組める。
- 写しの組み方（計画の 5.3）: 図を作った pack（run の写しか今の木）の md を、段落を訳に差し替えて一時のフォルダに同じ形で書き、run の値の記録（`<md>-viewer-values-<n>.json`）の `values` と `when` で、工場の組み立ての口 `prompt.compose`（block と共通の断片の根を受ける。`render` と `emit` も通る口）に組ませる。値の記録の在り処は、出来事の run の置き場と、node の道から `ports.include_folders` が引く include の道。
- どの記録がどの出来事の指示か: place に書かれた英語の指示（`<md>-prompt-<n>.md`）の字が、その出来事の会話に入った指示の字と同じ物（md の名がノードの id と違う prep と、会話を続ける輪にも当たる）。当たった中にノードの id と同じ名の md の物が在ればそれだけ（続けた会話には前のノードの指示も入っている）。会話の記録が無ければ、ノードの id と同じ名の md の物。同じ所の出来事の数と記録の数が同じなら書いた順に 1 つずつ当て、違えば全部の回を並べる。当たる記録の無い出来事（値の記録を書かない組み方の指示）には写しを出さない。
- ページ: 図の板の md と system の md・出来事の組み直した指示・会話の system と添え書きと指示に、日本語の写しを畳みで添える。訳の無い段落の数（指示の md・会話）を帯の注に出す。
- 訳の控えの足し方: `flowview.py --ja-batches <置き場>` がページに出す字のうち訳の無い段落を約 3.5 万字ずつの束（`batch-<n>.en.txt`。clone の外）に書く。訳すのは取り次ぐ会話で、同じ鍵の行の訳を `batch-<n>.ja.txt` に書く。`--ja-import <置き場>` が、今の木の md の段落の鍵の訳だけを `viewer/ja/` に、ほかをキャッシュに書く（合わない訳は拒んで名指す）。md を直して古くなった鍵は残っても英語で出るだけで、`--ja-prune` が消す。
- 始めの控え: 窓口の手元の控え（904 段落）のうち、今の木の md の段落に当たる 578 段落を、取り込みの口で入れた。残りは会話の字の訳で、リポジトリに入れない。

## 7 照らし

1. 作りの照らし（`tests/viewer/test_shape.py`）: 今の木の全部の graph を読み、`problems` が 0。
2. Archon の名の照らし（`tests/viewer/test_archon_names.py`。源の字を読むだけで手元でも回る）: 行の型と道具の出来事の型と run の状態が源とちょうど同じ・DB の欄と置き場の名が源に在る。
3. 本物の run の照らし（`tests/viewer/test_real_run.py`。Archon を起こすので CI だけで回る）: 小さな graph を 1 回回し、読めなかった行が 0・図に当たらないノードが 0・一覧にその run が終わりの状態で 1 行在る。承認ノードで止まった run は待ちと `answer` を出し、答えが入って次へ進む前の間（Archon の答えを書く口 `answerAttentionWait` を bun で直に呼んで作る）と、待ちのまま放棄した後は出さない。答えた承認ノードは出力に答えを持ち、ログに `gate_decision` の行が無い。行の中の欄の名（`execution.path` など）はここで照らす。
4. 1 枚の照らし（`tests/viewer/test_page.py`）: 雛形に `<script src`・`import(`・`fetch(` が無い。elkjs は照らしの値が合わなければ止まり、合わない物をキャッシュに置かない。網に届かなければ置き場と値を出して止まる。データの字はページの script を閉じず、読み戻せる。
5. 層の照らし: 2 章の照らし。
6. 日本語の写しの照らし（`tests/viewer/test_ja.py`）: 取り込みの口が今の木の md の段落の鍵の訳だけを `viewer/ja/` に書き、合わない訳を拒む。写しは値の記録から工場の組み立ての口で組み、訳の無い段落と合わない訳は英語のまま。`viewer/ja/` の訳のうち今の木の md の段落に当たる物は、どれも英語と同じ差し込み口と印の字を持つ。本物の run では（照らしの 3 の試験）、include の中で `prompt.emit` が書いた値の記録から組み直した写しが、訳の無い時に place の英語の指示と字のまま同じ。工場の組み立ての口の照らしは `tests/blocks/shared/test_prompt.py`（値の記録で、写した木からも同じ字に組み直せる）。
