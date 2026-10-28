<!-- coldwrite:skip 設計の一部。語は docs/design/README.md の頭の語の一覧で定義 -->
# 見る道具（`viewer/`）の設計書

- 何の話か: 工場の作り（graph と block の図・指示の md）と、run（工場の 1 回の実行）の一覧と再生を、人が 1 枚で見る道具の設計。置き場の決めは持ち主の決め `viewer-in-repo`、決まりは `viewer/AGENTS.md` の E25、計画は `docs/plans/2026-10-28-viewer.md`（3〜7 章と 9 章の PR の切り方）。
- 今在る物（計画の PR T1）: 置き場・層の地図の行・読む部品（`src/shape.py`・`src/runread.py`・`src/session.py`）と、データを JSON に出す入口 `flowview.py`。1 枚の HTML の雛形と配置の道具（elkjs）は T2、日本語の写しは T3 で足す。

## 1 E11 の 3 つの答え

1. Archon が持っているか → 半分持っている。止めた Archon の Web の画面（`packages/web/src/experiments/console/`。`archon serve` で起こす常駐のサーバー）は、run の一覧・run の詳細とログ・ノードの状態の図・承認ノードへの答えを持つ。無い物は、block と graph の入れ子で畳んだ図（Archon の図は `include:` を開いた平たい id で並ぶ）・工場の全部の graph の一覧と設計書と port・指示の md と組んだ値と日本語の写し・Claude Code の会話の中。持ち主の答え（計画の 10 章の問い 3「なんか見にくいんだよね。Archonの画面。気にしなくていいよ」）で、重なる所も run の一覧と run ごとのログは見る道具が持つ。走っている run の追い続けと承認の答えは、読むだけ・サーバーなし（E25 の 2・3）から持たない。
2. ASF が持っているか → 持っていない。止めた Archon の `.archon/workflows/sdlc/` に run を図や HTML で見る物は無い。HTML を作る物は `intake/scripts/bench/page.ts` の 1 つ（ベンチの結果を評価のページにし、手元の小さなサーバーが頼みのたびに作って採点を受ける物）で、読むだけ・サーバーなしの 1 枚の逆なので型は採らない。
3. 本当に要るか → 要る。ただし工場の生産の外の物として。keep-essence（`docs/design/README.md` の 10 章）のどれにも当たらず、工場の中の誰も読まない。`MISSION.md` の持ち主のエッセンス「グラフそのもの」と、1 回の run でそれがどう動いたかを持ち主が 1 枚で見る口が無い。元の works と graphloops に同じ場面の物は無い。

## 2 層と頼り

- 層の地図 `docs/layers.json` の層 `viewer`（`may_use` は `shell`・`shared`・`lib`）。どの層の `may_use` にも入らない。
- 殻（`shell`）に頼るのは、run の家を殻と同じ順に引くため。読む殻の口は `bin/_lib/launcher.py` の `target_root`・`run_home` と `bin/_lib/isolate.py` の `DIRS` の 3 つ（`bin/AGENTS.md` に同じ 3 つを書く）。`target_root` を通すのは、殻が `--cwd` を実のパスと git の根に直してから `run_home` に渡すため（相対のパス・対象の下のフォルダ・symlink で違う家を引かない）。
- `lib` は `lib/runlog.py`（Archon の spend の測りの読み `measurement`・`tokens` と、記録の行の名の一部）を使う。`shared` は T3 で日本語の写しを組む口（`workflows/.shared/prompt.py`）に使う。
- 照らし: 見る道具へ頼らない向きは `tests/layers/test_viewer_apart.py`（E25 の 1）、`lib/` が見る道具を import しない向きは `tests/layers/test_lib_blind.py`（地図から頭のフォルダを作る `scan.LAYER_IMPORT` に `viewer` が入る）。見る道具自身の `may_use` は機械で照らさない: import の照らしは頭のフォルダの単位で、`may_use` の 3 つの層の頭（`bin`・`workflows`・`lib`）がどれも許されるので照らす字が無い。block と graph の中の物を import しないことは人が見る（YAML と md と script の docstring を字として読むのは見る道具の役目で、頼りに数えない）。

## 3 起こし方とデータ

工場の clone の根から `uv run --isolated python3 viewer/flowview.py [--target <対象> [--run <run の id か頭の字>]] <出力>`。

- `--target` が無ければ今の木の作りだけを出す。在れば run の家の親の run の一覧を入れ、`--run` が無ければ一番新しい親の run を見る。
- 出力は工場の clone の下を拒む（ページに対象の字と会話の中身が入る）。拒みの文は見る道具が自分で持つ（`launcher.refuse_in_factory` は run の家のための文で、意味が合わない）。
- データの欄: `made_at`（作った時刻）・`commit`・`target`・`runs`（一覧）・`run`（選んだ run）・`shape`（図の作り）・`shape_from`（`run-copy` か `tree`）・`unmatched`（図に当たらないノードの道）・`texts`（会話の字を 1 つにした表。会話の欄は番号で指す）。

## 4 作りの読み（`src/shape.py`）

- 根（pack のフォルダ）を引数で受け、今の木 `<clone>/workflows` と run の写し `<写し>/project/.archon/workflows/<pack>` を同じ形で読む。
- ノードの読み分けは種類の鍵（`loop_group`・`include`・`workflow`・`approval`・`wait`・`prompt`・`command`・`loop`・`cancel`・`bash`・`script`）のどれか 1 つ。0 個か 2 個以上は読み分けられない物として `problems` に出す。AI のノードの md（`prompts/<id>.md`）・script のノードの script（`scripts/<名>.py`）が無い物と、工場の名の頭で始まるのに木に無い `include:`・`workflow:` の先も `problems` に出す。工場の名の頭で始まらない `workflow:` の先（Archon 同梱の `archon-pr`）は工場の外の graph として印を付ける。
- 記録のノードの道（`a__b.c`。`__` は include で開いた子、`.` は `loop_group` の本体）を、`locate` が include と `workflow:` の先の graph へ辿って図の所に当てる。

## 5 記録の読み（`src/runread.py`）

- run の家の `archon-home/archon.db`（名は `isolate.DIRS`）を読むだけで開く。run の一覧は run の表の親の行（`parent_run_id` が空）だけを読み、ログは読まない。行は id・グラフの名・状態・止まっている承認ノード（DB の `node_suspended` の後に終わりの無いノード）・始め・かかった秒・費用（metadata の `total_cost_usd`）・落ちの訳の頭の 1 行（DB の `workflow_failed`）。
- 選んだ run の記録は、DB の行の `output_root` から `logs/<run>.jsonl` を読む。子の run は DB の `parent_run_id` と metadata の `parent_node_id` で辿り、子の出来事の道の頭に親のノードの道を足す。run の写しは `<output_root>/workflow-source/runs/<run>/project/.archon/workflows`。写しが無い run は今の木で読み、`shape_from` を `tree` にする。
- 出来事はノードの起動（`execution.invocation.id`）ごとに 1 つ: 始めと終わり・状態（走り中・待ち・済み・落ち）・落ちた時の誤りの字（`node_error` の `error`）・費用（`accounting` が `node` の行だけ。束ねた行は数え直さない）・模型とトークンと往復の数・道具の呼び出し（`provider_event` の `tool_call` と `tool_call_update` を試み〔`attemptId`〕で結ぶ）・script と bash の出力の終わり（`exec_output`）・出力（DB の `node_completed` の `node_output`）と、出力が指す run の置き場の小さなファイル。
- 行の型と道具の出来事の型は、止めた Archon の型の和の全部を読む型と読まない型（訳つき）に分けて持つ。知らない型の行・ノードに当たらない道具の出来事は `unread` に数え、黙って落とさない。走り中の run は `live` と作った時刻を出す。止まっている run には答える殻の命令の 1 行（`answer`）を付ける。

## 6 会話の記録の読み（`src/session.py`）

- 隔離した Claude Code の設定（`claude-config/projects/`）の中から、記録の `binding.sessionPreview`（会話の id の頭）で会話の記録を探す。Claude Code が消した古い記録は結べない。
- system と道具の一覧は `api-request-shape`、添え書き（system の片と `<system-reminder>` の片）は `api-request-blob` から取る。この 2 つの型が普通の利用者の Claude Code でも出るかは確かめていない（出なければ system と添え書きは空になる）。
- Claude Code の版は工場が止めていないので、記録の形は試験で照らさない（人が見る）。読まない型の行は型ごとに数えて返す。

## 7 照らし

1. 作りの照らし（`tests/viewer/test_shape.py`）: 今の木の全部の graph を読み、`problems` が 0。
2. Archon の名の照らし（`tests/viewer/test_archon_names.py`。源の字を読むだけで手元でも回る）: 行の型と道具の出来事の型と run の状態が源とちょうど同じ・DB の欄と置き場の名が源に在る。
3. 本物の run の照らし（`tests/viewer/test_real_run.py`。Archon を起こすので CI だけで回る）: 小さな graph を 1 回回し、読めなかった行が 0・図に当たらないノードが 0・一覧にその run が終わりの状態で 1 行在る。行の中の欄の名（`execution.path` など）はここで照らす。
4. 1 枚の照らし（T2）: 雛形に `<script src`・`import(`・`fetch(` が無い。
5. 層の照らし: 2 章の照らし。
