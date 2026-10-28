<!-- coldwrite:skip 設計の一部。語は docs/design/README.md の頭の語の一覧で定義 -->
# 見る道具（`viewer/`）の設計書

- 何の話か: 工場の作り（graph と block の図・指示の md）と、run（工場の 1 回の実行）の一覧と再生を、人が 1 枚で見る道具の設計。置き場の決めは持ち主の決め `viewer-in-repo`、決まりは `viewer/AGENTS.md` の E25、計画は `docs/plans/2026-10-28-viewer.md`（3〜7 章と 9 章の PR の切り方）。
- 今在る物（計画の PR T1〜T3）: 置き場・層の地図の行・読む部品（`src/shape.py`・`src/runread.py`・`src/session.py`）・1 枚の HTML の組み立て（`src/page.py`・雛形 `page.tpl.html`・配置の道具 elkjs の止め `elkjs.json`）・日本語の写し（`src/ja.py` と訳の控え `ja/paragraphs.json`。6.6）・run の再生（雛形の中。6.7）と、ページを書く入口 `flowview.py`。

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
- データの欄: `made_at`（作った時刻）・`commit`・`target`・`runs`（一覧）・`run`（選んだ run）・`shape`（図の作り。graph と item に札の 1 行 `what`。4.5）・`shape_from`（`run-copy` か `tree`）・`unmatched`（図に当たらないノードの道）・`texts`（会話の字を 1 つにした表。会話の欄は番号で指す）・`stages`（段の表と段ごとの集計。6.8）。

## 4 作りの読み（`src/shape.py`）

- 根（pack のフォルダ）を引数で受け、今の木 `<clone>/workflows` と run の写し `<写し>/project/.archon/workflows/<pack>` を同じ形で読む。
- ノードの読み分けは種類の鍵（`loop_group`・`include`・`workflow`・`approval`・`wait`・`prompt`・`command`・`loop`・`cancel`・`bash`・`script`）のどれか 1 つ。0 個か 2 個以上は読み分けられない物として `problems` に出す。AI のノードの md（`prompts/<id>.md`）・script のノードの script（`scripts/<名>.py`）が無い物と、工場の名の頭で始まるのに木に無い `include:`・`workflow:` の先も `problems` に出す。工場の名の頭で始まらない `workflow:` の先（Archon 同梱の `archon-pr`）は工場の外の graph として印を付ける。
- 記録のノードの道（`a__b.c`。`__` は include で開いた子、`.` は `loop_group` の本体）を、`locate` が include と `workflow:` の先の graph へ辿って図の所に当てる。当てた所には、通った include・`workflow:` のノードを外から順に並べた道（`via`）を付ける（図が入れ子の graph へ外から入る道。6.7 の再生が使う）。

## 4.5 札の 1 行（`src/what.py`）

- 図のノードと block の札に「何をする物か」の 1 行を出す（持ち主の言葉 2026-10-29「正直全然なんのやつかわからないのも多い」。下書き `docs/plans/2026-10-29-viewer-overview.md` の 5.6）。見るたびに LLM で書かせず、工場に既に在る字から、種類ごとの順で最初に在る物の最初の文（括弧と `` ` `` の外の「。」まで）を選ぶ。読むのは設計書と、作りの読みが既に持つ字（YAML の説明・script の docstring・指示の md と日本語の写し）だけで、block の `src/` は読まない（E22）。
- 順: graph と block は、自分の設計書の「役」の見出し（設計シートの外の最初の物。見出しの下が箇条書き〔mode ごとの役〕なら、頭の印を落とした最初の項）→ YAML の説明が名指す設計書の中の、フォルダの名で始まる節の下の「役」（judge と eyes は `judge-eyes.md`）→ YAML の `description`。AI のノードは、設計書の「node の設計シート: <id>」の下の「役」→ 設計書の node の並びの行（`` `<id>`（…）: 説明 ``。見出しの括弧の外に「並び」を持つ節とその下の節の、囲みのコードの外の、id の直後に種類の括弧を持つ行だけ。port の節の同じ名の行と、別のノードの下の入れ子で出力の欄を並べた `` - `<id>`: … `` は拾わない。鎖の形 `` `a` → `b`: 説明 `` は 1 つのノードの行にしない）→ YAML の `description` → 指示の md の `You ` で始まる段落の日本語の写し（訳が無ければ英語）。script は docstring で、「受け皿」「返し」で始まる物は配線として札を細く畳む。呼ぶノード（種類 `block` は `include:`、`child` は `workflow:`）は呼ぶ先の graph の 1 行と、呼ぶ側での役（呼ぶ側の設計書の node の並びの行 → `with` の `mode` の値）。繰り返しは形から組む（「下の n ノードを最大 m 周回す器」）。承認・止め・bash は node の並びの行 → YAML の `description`。
- データ: graph と item の `what` に `line`（1 行）・`from`（出どころの文書と節）・`why`（出どころの段落の 2 文目より後ろ）・`role` と `role_from`（呼ぶ側での役）・`wire`（配線）。1 行が無い物は `line` が空で、札と板は「1 行が無い」と出す（黙って空にしない）。呼ぶ側での役が無く、呼ぶ先を 2 か所以上で使う include は「ここでの役は設計書に無い」と出す（札が同じ字で並ぶ所）。
- ページ: 札の主を 1 行（2 行で切る）にし、名と種類を下に小さく置く。板の頭に 1 行を大きく、出どころを小さく、なぜ在るかを畳みで出す。
- 1 行は今の木の設計書から引く（run の写しの図でも同じ）。docstring と指示の md は図を作った pack（写しか今の木）の物。
- 書き足し（1 行が無い 12 ノード・工場の中の語が残る 1 行・呼ぶ側での役が無い include）は別の仕事（下書きの 5.6.3）。

## 5 記録の読み（`src/runread.py`）

- run の家の `archon-home/archon.db`（名は `isolate.DIRS`）を読むだけで開く。run の一覧は run の表の親の行（`parent_run_id` が空）だけを読み、ログは読まない。行は id・グラフの名・状態・止まっている承認ノード（状態が `paused` の run だけ。DB の `node_suspended` の後に終わりの無いノード。止めた・放棄した run は `node_completed` を書かずに `cancelled` になるので、状態で絞る）・始め・かかった秒・費用（metadata の `total_cost_usd`）・落ちの訳の頭の 1 行（DB の `workflow_failed`）。
- run の始めとかかった秒は、run の行の始めと終わりでなく、出来事の最初と最後の時刻から出す（一覧は DB の出来事の表の `created_at`、選んだ run は子の run を含むログの出来事の始めと終わり）。承認の答えで起き直した run は、Archon が run の行の始めを起き直した時刻に書き換える（`packages/core/src/db/workflow-run-resume.ts`）ので、行の値では答えの後の数分しか出ない。出来事の無い run だけ行の値を使う。走り中の run は最後の出来事までの長さ。子の run の行も同じく、その子と孫の出来事から出す。読めない時刻の出来事は数えない（ページを落とさない）。
- 一覧の並びと、run を名指さない時に開く一番新しい run は、出来事の最初の時刻の新しい順（出来事の無い run は行の始め）。行の始めで並べると、起き直した run が後に始めた run より上に来る。
- 長さの丸め（ページ）: 頭の帯・一覧・大きな数は分を整数に（秒に丸めて 60 秒未満は秒）、畳みの中は「分:秒」。同じ値はどの画面でも同じ丸めで出す。始めの時刻は、DB の書き方とログの書き方をどの画面でも秒までの `YYYY-MM-DD HH:MM:SS`（UTC）にそろえて出す。
- 選んだ run の記録は、DB の行の `output_root` から `logs/<run>.jsonl` を読む。子の run は DB の `parent_run_id` と metadata の `parent_node_id` で辿り、子の出来事の道の頭に親のノードの道を足す。run の写しは `<output_root>/workflow-source/runs/<run>/project/.archon/workflows`。写しが無い run は今の木で読み、`shape_from` を `tree` にする。
- 飛んだノード（`node_skipped`）は、道と飛んだ時刻（`time`）と訳（`cause`）を持つ。
- 出来事はノードの起動（`execution.invocation.id`）ごとに 1 つ: 始めと終わり・状態（走り中・待ち・済み・落ち）・落ちた時の誤りの字（`node_error` の `error`）・費用（`accounting` が `node` の行だけ。束ねた行は数え直さない）・模型とトークンと往復の数・道具の呼び出し（`provider_event` の `tool_call` と `tool_call_update` を試み〔`attemptId`〕で結ぶ）・script と bash の出力の終わり（`exec_output`）・出力（DB の `node_completed` の `node_output`）と、出力が指す run の置き場の小さなファイル・その run の置き場の根（`artifacts`。日本語の写しが値の記録を引く。6.6）。
- 行の型と道具の出来事の型は、止めた Archon の型の和の全部を読む型と読まない型（訳つき）に分けて持つ。知らない型の行・ノードに当たらない道具の出来事は `unread` に数え、黙って落とさない。走り中の run は `live` と作った時刻を出す。答えを待つ run（状態が `paused`）には答える殻の命令の 1 行（`answer`）を付ける。答えが入って次へ進む前の間（Archon は答えを run の metadata の `wait` に書くだけで、状態は `paused` のまま `node_completed` も書かない）のノードは待ちに数えない（Archon の `runAttention` と同じ。名は `schemas/workflow-run.ts` の `workflowWaitStepName`）。承認ノードの答えはノードの出力（`wait: attention` の `{decision, text}`）から読む（`gate_decision` の行は工場が使わない古い `approval:` だけが書く）。

## 6 会話の記録の読み（`src/session.py`）

- 隔離した Claude Code の設定（`claude-config/projects/`）の中から、記録の `binding.sessionPreview`（会話の id の頭）で会話の記録を探す。Claude Code が消した古い記録は結べない。
- system と道具の一覧は `api-request-shape`、添え書き（system の片と `<system-reminder>` の片）は `api-request-blob` から取る。この 2 つの型が普通の利用者の Claude Code でも出るかは確かめていない。型の行が在ったかを `recorded` に持ち、無ければページは欄を空にせず「記録に無い」と出す。
- Claude Code の版は工場が止めていないので、記録の形は試験で照らさない（人が見る）。行の型は、読む型と読まない型（訳つき。`session.py` の `UNREAD_TYPES`。添え物・API の頼みの印・待ち行列の印・会話の題など、LLM に入った字を別の型から読む物と中身を持たない物）に分ける。どちらでもない知らない型の行だけを型ごとに数えて返し、ページの「読めなかった物」の数に入れる（読まない型まで数えると、帯の数が本当に読めなかった物を指さない）。ただし読まない型のうち字を別の型から読む物（`session.py` の `READ_FROM`。`attachment` は `api-request-blob` から、`api-request` は `api-request-shape` と `api-request-blob` から読む）は、代わりの型が記録に無い会話では知らない型と同じく数える（代わりが無ければ LLM に入った字が帯から消える）。

## 6.5 ページ（`src/page.py`・`page.tpl.html`・`elkjs.json`）

- ページは 1 枚で完結する（E25 の 3）。データは雛形の `<script type="application/json">` に、JSON の字の `<` を全部 `\u003c` にして埋める（記録の字の `</script>` や `<!--` が script の中身を閉じない）。elkjs の bundle は次の `<script>` に字のまま埋め、`</script` だけを崩す。雛形の印は 1 度ずつ埋め、埋めた字の中の印の字は埋め直さない。
- ページは HTML のビューアが body の中身を別の要素で包み、拡大縮小の `transform` を掛けて開く事がある。高さは body の直下の flex にも `position:fixed` にも頼らず、雛形のいちばん外の要素 `.app` が `100vh` で持つ（中身の高さが 0 にならない）。
- elkjs（計画の 4 章の案 E1）: 版と tarball の照らしの値（npm の登録所の `dist.integrity`。tarball の sha512）を `viewer/elkjs.json` に止める。版 0.10.0 は、窓口の手元の見る道具が使ってきた bundle（sha256 の頭 `48d338d5aeddd950`）と同じ物だったので選んだ。tarball は利用者のキャッシュ（`place.cache_dir` の下の `viewer/elkjs-<版>/`）に元の名のまま置き、読むたびに照らす。取った物もキャッシュの物も、合わなければページを書かずに止まる。網に届かない時は、置くべきパスと照らしの値を出して止まる。ページには bundle の前に、版・license（EPL-2.0）・取った所と、tarball の `package/LICENSE.md` の字を注で置く。
- 画面は 4 つ: 図（graph と block の一覧・elk で上から下に並べたノードの図・ノードを押すと板に作りとこの run の出来事・block と子の run は 2 度押しで中へ・run が在れば下の帯に再生。6.7）・run の一覧（行ごとに、その run のページを作る命令の 1 行。計画の 3.5）・ログ（ノードの出来事を時刻順に。子の run・飛んだノード・繰り返しの終わりの確かめ・出力が指すファイル。走り中は「ここまで」）・読めなかった物（作りの問題・図に当たらないノード・記録の読めなかった行・会話の記録の読まない行）。記録の字は全部 `textContent` で置き、HTML として読まない。
- LLM に入った物（AI のノードの出来事の会話）: 出来事の板の中で、頭の欄（状態・時刻・トークン）と誤りのすぐ下、道具の呼び出し・組んだ指示の写し・出力より上に置く。中身は 1 本の並びで、初めの文脈（system・道具の一覧・添え書き・最初の指示）の後に、往復ごとに積まれた物（返事・考え・道具の呼び出し・道具の結果・後から入った指示）を入った順に並べ、各片に字数を添える（中身は畳み。指示・system・添え書きには日本語の写しを畳みで添える）。往復の頭と並びの上の束に、その往復の入力のトークン（in・cache 読み・cache 書きの和。前の往復からの増え）と出力のトークンを同じ尺の棒で置き、文脈が育つ様子を一目で見せる。トークンは往復の usage から読む（`session.py` の流れの `["turn", 往復の番号]`。1 つの返事は行が分かれ、出力のトークンは終わりの行で数え終わる）。
  - 置き場を板の上の方にした訳: 再生が AI のノードの歩に来ると板がその出来事を開いて見える所へ送るので、出来事の頭のすぐ下なら歩くたびに目に入る。別のタブは図と並べて見られず、歩くたびに移る手間が出る。板の幅（最大 560px）で字の片が読みにくい時のために、並びの頭の「広く見る」で同じ並びを図の画面いっぱいの面に出す（Esc か × で閉じる）。
  - 往復の数は Claude Code の会話の記録の返事の数で、Archon が数える出来事の往復（頭の欄の「往復」）と同じとは限らない。
- 図の出来事は、同じ graph が何度 include されても、その graph の所に全部寄せる（include の文脈ごとに分けるのは見た目の磨きで回す）。
- 図の線は、順を決める依りだけを引く（ほかの依りを通って届く依りは引かない。数十の依りを持つノードへの線が束になって図を埋めるため）。依りの全部はノードの板に出す。
- 図の行き来: 根の graph は run の graph（run が無ければ `line`）。上の道しるべは常に根から始め、根へ 1 回押しで戻るボタン（⌂）を頭に置く。各段は graph の名と、外の graph の中でその graph を include・`workflow:` するノード（名が graph と違う時だけ）を出す。一覧から開いた graph も、根から include と `workflow:` を辿った一番短い道で同じ形に出す（根から辿れない graph は根の下に「辿れない」と書いて置く）。
- 開いた時の図は、全体が読める大きさで入れば全体を、入らなければ読める大きさで入口（一番上のノード）から見せる。今の graph の全部はボタン「画面に収める」で縮めて見る（graph の行き来と取り違えない名にする）。板は閉じて始め、graph の説明は道の欄の「説明」で開く。elk が並べられない時は、誤りを図の所に出す。

## 6.6 日本語の写し（`src/ja.py`・`ja/paragraphs.json`）

- 日本語の写しは、AI のノードへの英語の指示を段落ごとに日本語に訳した、人が読むための射影で、LLM には渡さない（持ち主の決め `prompt-values-for-viewer`・`viewer-in-repo` の 4）。見るたびに LLM で訳さず、訳の控え（段落の字の sha1 の頭 16 字を鍵、訳を値にした JSON）から引く。
- 控えは 2 か所（計画の 5.2 の案 J1）: 工場の指示の md（pack の `<block>/prompts/` と `.shared/prompts/`）の段落の訳は `viewer/ja/paragraphs.json` に入れる。それ以外（Claude Code の字・run の時に入った字。対象の字を含みうる）は利用者のキャッシュ（`place.cache_dir` の下の `viewer/ja-cache.json`）に置く。引く時は 2 つを合わせ、リポジトリの方が勝つ。
- 段落は、空の行と組み立ての印の行（段落の選びの印・道具の印・断片だけの行）で区切った行の塊。英字が 40 字を超え、かなが英字の 3 分の 1 未満の塊だけを訳す。訳は、差し込み口（`{name}`・`{shared:…}`・`{part:…}`）と字の `{{`・`}}` と印の頭の字を英語と同じだけ持ち、印の行を持たない物だけを使う。合わない訳は取り込まず、組む時も英語のまま残すので、写しの md の木は英語の木と同じ値と段落の選びで組める。
- 写しの組み方（計画の 5.3）: 図を作った pack（run の写しか今の木）の md を、段落を訳に差し替えて一時のフォルダに同じ形で書き、run の値の記録（`<md>-viewer-values-<n>.json`）の `values` と `when` で、工場の組み立ての口 `prompt.compose`（block と共通の断片の根を受ける。`render` と `emit` も通る口）に組ませる。値の記録の在り処は、出来事の run の置き場と、node の道から `ports.include_folders` が引く include の道。
- どの記録がどの出来事の指示か: place に書かれた英語の指示（`<md>-prompt-<n>.md`）の字が、その出来事の会話に入った指示の字と同じ物（md の名がノードの id と違う prep と、会話を続ける輪にも当たる）。当たった中にノードの id と同じ名の md の物が在ればそれだけ（続けた会話には前のノードの指示も入っている）。会話の記録が無ければ、ノードの id と同じ名の md の物。同じ所の出来事の数と記録の数が同じなら書いた順に 1 つずつ当て、違えば全部の回を並べる。当たる記録の無い出来事（値の記録を書かない組み方の指示）には写しを出さない。
- ページ: 図の板の md と system の md・出来事の組み直した指示・会話の system と添え書きと指示に、日本語の写しを畳みで添える。訳の無い段落の数（指示の md・会話）を帯の注に出す。
- 訳の控えの足し方: `flowview.py --ja-batches <置き場>` がページに出す字のうち訳の無い段落を約 3.5 万字ずつの束（`batch-<n>.en.txt`。clone の外）に書く。訳すのは取り次ぐ会話で、同じ鍵の行の訳を `batch-<n>.ja.txt` に書く。`--ja-import <置き場>` が、今の木の md の段落の鍵の訳だけを `viewer/ja/` に、ほかをキャッシュに書く（合わない訳は拒んで名指す）。md を直して古くなった鍵は残っても英語で出るだけで、`--ja-prune` が消す。
- 始めの控え: 窓口の手元の控え（904 段落）のうち、今の木の md の段落に当たる 578 段落を、取り込みの口で入れた。残りは会話の字の訳で、リポジトリに入れない。

## 6.7 再生（`page.tpl.html` の中のスクリプトだけ）

- 終わった run を後から 1 枚で歩く。操作は図の画面の下の帯: 始めへ・1 つ前・再生と止める・1 つ後・時の位置のつまみ・速さ（1 秒に進む歩）・やめる（run の終わりの姿の図へ戻る）。鍵盤の ← → と空白でも動く。ページの中のスクリプトだけで動き、別のファイルを読まない（E25 の 3）。
- 1 歩は、run の出来事（ノードの起動ごと）の始まりか終わりの 1 つで、時刻順に並べる（同じ時刻は始まりが先）。終わりの無い出来事（走り中・待ち）は始まりだけ。
- 繰り返しの周は、周ごとに別の出来事なので、そのまま 1 周ずつ歩く（帯に「周 n」を出す）。子の run（`workflow:` の先）の出来事は、親の出来事と同じ並びに時刻で入り、帯に子の run の id を出す。図の所は親のノードから辿った子の graph の中。
- 飛んだノードは歩にしない（数が出来事より多く、歩の大半が飛びになる）。時の位置が飛んだ時刻を過ぎ、その所がまだ走っていなければ「飛んだ」に見せる（resume で走った後に飛びの行が来た所は、走った姿のまま）。
- 歩へ移る時は、出来事の所の `via` で根からの道しるべを組み、違う graph なら描き直してから、そのノードを画面の真ん中へ寄せ、板に「この run で」の欄を出して今の歩の出来事だけを開いて目立たせる（中身はノードを押した時と同じ。指示の md・日本語の写し・会話・出力・飛んだ訳）。
- 図の上の姿: 今の歩のノード（太い縁と輪）・走り中（縁の色）・済み（普段の姿と終わりの状態の点）・まだ（薄い）・飛んだ（点線で薄い）。include のノードと繰り返しの箱は、中の出来事を自分の所の出来事として数える（中が走っていれば走り中、触れられた後は済み）。
- 図に当たらない出来事の歩は、図を動かさず帯に「図に当たらない」と出す。

## 6.8 段（`viewer/stages.json`・`src/stages.py`）

- 段は、line（メイングラフ）の一番上のノードを人の言葉で畳んだ単位（受付・判定・計画・修正・報告など 11 個）で、見る道具だけの考え。流れの画面（段の地図と時間の帯）が使う。設計の下書きは `docs/plans/2026-10-29-viewer-overview.md`（#907）の 3〜6 章。
- E11 の 3 つの答え: Archon は持たない（Web の画面の run の詳細は、include を開いた平たいノードの図とログの並びで、ノードを段に畳む物と段ごとの時間は無い）。ASF も持たない。要る: 図とログからは、どこからどこまでが判定で、どこからが修正か・どの段に何分と幾らかかったかが読めない（下書きの 1 章）。
- 表の置き場は見る道具の中（持ち主の決め。下書きの 5 章の S2）。工場の文書の形に見る道具の都合を持ち込まない。行ごとに名・1 行の説明・受け渡す物（次の段へ渡る物の人の言葉）・説明の出どころ（`docs/design/line.md` の 1.3 の番号）・中のノードの id を持つ。ノードごとの「何をする物か」の 1 行は表に持たず、工場の字から引く（下書きの 5.6）。
- 出来事の段は、出来事の道の頭（line の一番上のノード）で引く。include・繰り返しの周・子の run の出来事も道の頭は line のノード。run が line の run でなければ段に集めない（表は line だけ）。
- 段ごとの集計（データの `stages.run`）: 状態（通った・落ちた・待ち・走り中・飛んだ・記録に無い）・始めと終わり（段の出来事の最初と最後）・人の答え待ちの秒（`wait:` のノードの長さの和）・AI の秒と手番の数（AI のノードの長さの和と数）・往復の数（`turns`。Archon が数える出来事の往復の和）・周の数（`rounds`。繰り返しの本体の場所と周の番号の列 `loop` の組の違う物の数で、入れ子なら内の周まで。本体の場所は道を繰り返しの区切り `.` だけで切った物で、本体に直に在るノードと本体の include の中のノード〔`plan-rounds.design-turn` と `plan-rounds.plan__draft`〕を同じ周に数える〔受付 c31850 の足し 2e1ffb〕。同じ段を何周回ったかで、無駄な回り直しを見る）・費用（ドルの和だけ。4 分けごとのドルは出さない）・4 分けのトークン（記録の `input`・`output`・`cacheRead`・`cacheWrite` の和）。
  - 新しく読んだ分（`uncached`）と cache の内訳が知れない手番の数（`cacheUnknown`）は、工場の共通の口 `lib/runlog.py` の `add_tokens` と同じ訳で出す: `uncached` は `input` から cache の 2 つを引いた物で、cache の欄が欠けた手番（Archon では「知れない」の意味で 0 ではない。`docs/design/archon.md`）と `cachePartial` の手番が 1 つでも在れば出さない。`input` が cache の 2 つの和より小さい手番は引けないので数を `odd` に持ち、1 つでも在れば `uncached` を出さない（包みの関係は Claude Code と Archon の版で変わりうるので決まりとして照らさない）。
  - 中の出来事を束ねる器（繰り返しの器 `loop_group`・並べて起こす器 `compose_fan_out`・子の run を起こすノード `workflow`。`runread.GROUP_KINDS`）の出来事は、中の出来事と二重になるので数・長さ・費用に数えない。子の run を起こすノードの行には Archon が子の run の総額を載せ（`docs/design/archon.md`）、子の中の各ノードの費用も同じ段に入るため。
- 段の表の各段は、ノードの列 `nodes` と、そのうちの配線の列 `wiring`（合流・受け渡しだけで段の仕事をしない物。受け皿の `-out`・返しの `-in`・`fix-in`・`fixed`・`judged`・`eyes-in`・修正前の承認の聞きと受け `ask-before-fix`・`answer-before-fix` と仕様駆動の run の `spec-ask-before-fix`・`spec-answer-before-fix`）を持つ。段の状態（通った・飛んだ）は配線でないノードだけで決める。修正の段が飛んだ run でも `fix-in`・`fixed`・`judged` は走り、数えると修正の段が「通った」に見える（見本で分かった事。下書きの計画 `2026-10-29-viewer-overview.md` の 6.5.1）。`trigger_rule` と `when` の形からは引かない（承認の答えの `answer-*` も同じ形だが、`answer-replan` などは段の仕事をする）。
  - 修正前の承認の聞きと受け（受付 7521c4。窓口の決め B: 表示を記録の事実に合わせる）: `ask-before-fix`・`answer-before-fix` は、人に聞かずに通しや止めを決めて受け渡すだけでも走る。run 642df5d7 では人が計画の段で止め、修正前の承認の聞き `gate-before-fix` は飛んだのに、聞きと受けが走ったので修正前の承認が「通った」に見えた。2 つを配線にし、段の状態は人の答え待ち `gate-before-fix` で決める。人が答えた run は「通った」、聞かれなかった run は「飛んだ」。
  - 仕様駆動の run の聞きと受け（受付 03e0e5。決め B と同じ訳）: `spec-ask-before-fix`・`spec-answer-before-fix` は同じ本体（`ask_before_fix`・`before_fix_answer`）を受け、同じく聞かずに受け渡すだけでも走るので配線にし、段の状態は `spec-gate-before-fix` で決める。最後の承認の聞きと受け `ask-final`・`answer-final` は配線にしない（仕様駆動の版は無い）: `ask-final` は前の止めを受け渡さず、封じと試験と目の返りから最後の承認を開くか・規則で通すかを自分で決め、merge に渡す値も組む。段の仕事をする。
  - 寄せた訳（受付 c31850）: #910 の a693d6b5 は合流を形（前が飛んでも走る `trigger_rule` を持ち `when` の無い物。`runread.JOIN_RULES`）で決めていた。同じ物を表と形の 2 通りで決めないよう、表の 1 つに寄せて `JOIN_RULES` を外した。形は配線と合わない: 承認の答えを受ける `answer-*`・`ask-replan` は合流の形だが段の仕事をし、`when` を持つ返し（`structure-in`・`design-in`）と規則を持たない受け皿の `-out`・`eyes-in` は合流の形でないが配線。流れの画面の地図も表の列と出来事の `through` を読む（下書きの計画の 6.6.8）。どの段にも配線でないノードが在ることを照らすので、「段のノードが全部合流なら数える」の外しも要らない。
- 止まった所（`stages.stop`）は記録の事実から引く（下書きの計画 `2026-10-29-viewer-overview.md` の 6.6.8。受付 c31850）: 落ちた run（run の状態が `failed`。`runread.FAILED`）は最後に落ちた出来事の段。人が止めた run は、答え（`{decision, text}`）が止める語（`lib/answer.py` の `STOP_WORDS`）だった最後の人の答え待ちの出来事の段。どちらでもない run（直した・直す物が無かった・まだ走っている）には出さない。前の形（最後に走った段の 1 つ前に走った段で、間の段が全部飛んだ物）は、止めを受け渡しただけの段を返した。run 642df5d7 では人が計画の段の中の相談（`plan-rounds/gate-design`）で止め、修正前の承認の聞きと受け（`ask-before-fix`・`answer-before-fix`）はその止めを受け渡しただけなのに、修正前の承認を返していた。今は計画を返す。飛んだ段は地図で薄く出るので、道が分かれた所は別の欄にしない。
- 段の表に無い line のノード（`stages.loose`。古い run の写しの作りなど）は「読めなかった物」に出し、黙って落とさない。

## 7 照らし

1. 作りの照らし（`tests/viewer/test_shape.py`）: 今の木の全部の graph を読み、`problems` が 0。今の木の line の最初の block の頭のノードに、外から入る道（`via`）が付く（Archon を起こさずに手元で照らす）。図に当てる入口（`tests/viewer/test_flowview.py`）: 飛んだノードに当たる所（`at`）を付けても、飛んだ時刻（`time`）が残る。
2. Archon の名の照らし（`tests/viewer/test_archon_names.py`。源の字を読むだけで手元でも回る）: 行の型と道具の出来事の型と run の状態が源とちょうど同じ・DB の欄と置き場の名が源に在る。
3. 本物の run の照らし（`tests/viewer/test_real_run.py`。Archon を起こすので CI だけで回る）: 小さな graph を 1 回回し、読めなかった行が 0・図に当たらないノードが 0・include の中のノードに外の graph から入る道（`via`）が付く・一覧にその run が終わりの状態で 1 行在る。承認ノードで止まった run は待ちと `answer` を出し、答えが入って次へ進む前の間（Archon の答えを書く口 `answerAttentionWait` を bun で直に呼んで作る）と、待ちのまま放棄した後は出さない。答えた承認ノードは出力に答えを持ち、ログに `gate_decision` の行が無い。行の中の欄の名（`execution.path` など）はここで照らす。
4. 1 枚の照らし（`tests/viewer/test_page.py`）: 雛形に `<script src`・`import(`・`fetch(` が無い。elkjs は照らしの値が合わなければ止まり、合わない物をキャッシュに置かない。網に届かなければ置き場と値を出して止まる。データの字はページの script を閉じず、読み戻せる。
5. 層の照らし: 2 章の照らし。
6. 日本語の写しの照らし（`tests/viewer/test_ja.py`）: 取り込みの口が今の木の md の段落の鍵の訳だけを `viewer/ja/` に書き、合わない訳を拒む。写しは値の記録から工場の組み立ての口で組み、訳の無い段落と合わない訳は英語のまま。`viewer/ja/` の訳のうち今の木の md の段落に当たる物は、どれも英語と同じ差し込み口と印の字を持つ。本物の run では（照らしの 3 の試験）、include の中で `prompt.emit` が書いた値の記録から組み直した写しが、訳の無い時に place の英語の指示と字のまま同じ。工場の組み立ての口の照らしは `tests/blocks/shared/test_prompt.py`（値の記録で、写した木からも同じ字に組み直せる）。
7. 札の 1 行の照らし（`tests/viewer/test_what.py`）: 今の木で、1 行を選ぶ部品が読めない設計書の節（「役」の見出しの下に段落が無い）が 0（読めない節はページの「読めなかった物」にも出す）。1 行が無いノードの数は照らさない（書き足しを試験で強いない）。小さな木で、種類ごとの出どころの順・配線・呼ぶ側での役・1 行が無い物が空であること。
8. 段の照らし（`tests/viewer/test_stages.py`）: 今の木の line の一番上のノードがどれも段の表のちょうど 1 つの段に入り、表のノードがどれも line に在る。配線の列がその段のノードの中に在り、どの段にも配線でないノードが在る。段ごとの集計は小さな run の記録で、配線のノードだけが走った段（修正の段が飛び、`fix-in`・`fixed`・`judged` だけが走った run）が飛んだになり、修正前の承認は人が `gate-before-fix`（仕様駆動の run は `spec-gate-before-fix`）で答えた run だけ通ったになり（run 642df5d7 の形と、仕様駆動の run で止めを受け渡しただけの形では飛んだ）、止まった所と和が出る。子の run を起こすノードの費用を二重に足さず、cache の欄が欠けた手番と引けない手番では新しく読んだ分を出さず、止まった所は、落ちた run では最後に落ちた出来事の段、人が止めた run では答えが stop だった答え待ちの段になり（run 642df5d7 の形で計画。前の形の修正前の承認を返さない）、通す答えだけの run と落ちて続けて終わった run には出ない。
