# 今の works の利用者に見える能力の照らし

今の works（`raiki61/claude-plugins` の `works/`）が利用者に見せる能力を 1 能力 1 行で並べ、works-factory の main のどこで同じ事をしているかを名指す表（#505）。works-factory は今の works の能力を落とさない作り直し（持ち主の決め `superset`・`no-narrow`）で、この表がその照らしの正本。
入口（起動の殻 `bin/works-factory`・メイングラフの入力）・メイングラフ・サブグラフの利用者に見える能力を変える PR は、該当の行を同じ PR で直す。`tests/layers/test_works_parity.py` が、目録の錨を全部覆うことと、行の欄の形と、「今」の名が main に在ることと、末尾の「前の棚卸しの今」の行が前の棚卸しの印の行と 1 つずつ合うことを照らす。

- 源: claude-plugins の `585c385a875f0cea2acdfe273b3cd4ce7b65f8d2` の 3 つのファイル。行の ID の頭の字は源ごと
  - S: `works/skills/works/SKILL.md`（利用者と AI の使い方の文。169 行）
  - U: `works/dev/use.sh`（起動の殻。1254 行）
  - K: `works/docs/keep-essence.md`（守る仕組みの 12。21 行）
- 前の棚卸し `docs/plans/2026-10-13-capabilities/` は区分ごと・関数の粒度の実装の計画で、版は `2aa7c66c`。この表は源の順に並べ、同じ能力の前の棚卸しの行 ID を欄「旧棚卸し」で引く。
- Archon が持つ能力は、工場の側で覆い直さず Archon の命令をそのまま使う（持ち主の決め `one-launcher`・`on-archon-only`）。その行の「今」は「Archon の `<命令>`」と書く。

## 欄の決まり

- 元: 源の `<ファイル>:<行>`。版が止まっているので行番号で書く
- 印: この行が覆う目録の錨を `` ` `` で囲んで並べる。錨の無い行は「無し」
- 今: works-factory の main で同じ事をする所。`path::名`（Python の最上位の関数・クラス・定数か `クラス.名`。YAML はノードの id）・README.md「<見出し>」・Archon の `<命令>` を「・」で並べる。無ければ「無し」
- 状態: 在る・形を変えて在る（<何が違うか>）・無い のどれか
- 処置: 「無い」行と、「形を変えて在る」で失った部分の在る行が持つ。次のどれか
  - `#<issue>`: 別の issue で直す（ほかの issue で扱う物はその issue を指し、二度直さない）
  - 戻した: <`path::名` か README.md「…」>: #505 の PR で戻した
  - 要らない: <訳>: keep-essence・持ち主の決め（`docs/owner-decisions.md`）・AGENTS.md の決まり・Archon が持つ、のどれかに照らした訳
- 旧棚卸し: 前の棚卸しの行 ID。無ければ「無し」。前の棚卸しの各行の「今」の字は、末尾の「前の棚卸しの今」に移した（#521）。前の棚卸しの行の「今」の欄は印だけを持つ: 字を移した行は「表」、移した字が「無し」で始まる行は「無し（表）」、住処を書かなかった行は「無し」か空

### 指しの形

#505 の本文は「ファイル:行」と書くが、この表の「今」は `path::名` で指し、行番号を書かない。行番号は関数や試験を 1 つ足すたびに関係の無い行までずれる。名で指せば、指す先を変える PR が名を消した時に `tests/layers/test_works_parity.py` が赤になり、表の直しを強いる（照らしの部品は前の棚卸しの柵 `tests/layers/test_capability_pointers.py` と同じ物を使う。末尾の「前の棚卸しの今」も同じ規則で照らす）。「元」は版を止めた源なので行番号で書く。

### 源の版を上げる時

1. 3 つのファイルを新しい版で取る: `gh api "repos/raiki61/claude-plugins/contents/<path>?ref=<commit>" -H "Accept: application/vnd.github.raw"`
2. 下の目録の抜き方の命令を打ち直し、目録と行を直す
3. 頭の版の字を直す

## 源の目録

源から決まった命令で抜いた錨。各錨は、どれかの行の「印」か「元」に在る（試験が照らす）。抜き方:

- SKILL.md の見出し: `grep -n '^#' SKILL.md` の行
- SKILL.md の環境変数: `grep -o 'WORKS_[A-Z_]*\|GRAPHLOOPS_[A-Z_]*\|CLAUDE_[A-Z_]*' SKILL.md | sort -u`
- SKILL.md の依頼の欄・結末の語・承認ノード・開き方・機能の語・`wait` の終了コード: 1〜5 のセクションの `` ` `` で囲んだ語と、`wait` の終了コードの段
- use.sh の環境変数: `grep -o '\${\?[A-Z][A-Z0-9_]*' use.sh | tr -d '${' | sort -u` から殻の中の変数を除いた、利用者が置く・読む物。特定の利用者の端末の道具の 2 つは名を書かず、それを言う注の行（`use.sh:74`）で書く
- use.sh の拒み: `grep -n 'refuse "\|problem "' use.sh` の行
- keep-essence.md の仕組み: 10〜21 行の 12

- SKILL.md の見出し（7）: `SKILL.md:6`・`SKILL.md:13`・`SKILL.md:37`・`SKILL.md:73`・`SKILL.md:101`・`SKILL.md:129`・`SKILL.md:156`
- SKILL.md の start の旗（6）: `--base`・`--pr`・`--spec`・`--rounds`・`--budget-usd`・`--`
- SKILL.md の殻の命令（12）: `check`・`start`・`answer`・`approve`・`wait`・`show`・`apply`・`clean`・`stop`・`stop.sh`・`report.sh`・`carry-ci`
- SKILL.md の環境変数（22）: `CLAUDE_CODE_OAUTH_TOKEN`・`CLAUDE_CONFIG_DIR`・`CLAUDE_KEYCHAIN_SERVICE`・`CLAUDE_PLUGIN_ROOT`・`GRAPHLOOPS_ENGINE_CHILD`・`WORKS_DESIGN_ONLY`・`WORKS_DEV_ADAPTER`・`WORKS_DEV_HOME`・`WORKS_KEYCHAIN_ITEM`・`WORKS_USE_ALLOW_DELETE`・`WORKS_USE_ALLOW_STOPPED`・`WORKS_USE_ALLOW_TESTCMD`・`WORKS_USE_FEATURES_OFF`・`WORKS_USE_FEATURES_ON`・`WORKS_USE_FINAL_GATE`・`WORKS_USE_FIX_FIXTURE`・`WORKS_USE_GATES`・`WORKS_USE_HOME`・`WORKS_USE_POLICY_MD`・`WORKS_USE_THICKNESS`・`WORKS_USE_UNATTENDED`・`WORKS_USE_WAIT_SECONDS`
- SKILL.md の依頼の欄（16）: `where`・`text`・`mechanism`・`measured`・`false_positive_if`・`findings`・`pr`・`issue`・`answers`・`prior_failures`・`question`・`command`・`output`・`draft`・`source`・`note`
- SKILL.md の結末の語（10）: `fixed`・`fixed_needs_check`・`no_fix_needed`・`round_limit`・`stopped_by_human`・`stopped_by_request`・`stopped_by_line`・`needs_human`・`record_invalid`・`interrupted`
- SKILL.md の承認ノード（3）: `launch`・`policy-gate`・`final-gate`
- SKILL.md の最後の承認ノードの開き方（3）: `protected_only`・`when_needed`・`always`
- SKILL.md の機能の語（5）: `judge_verify`・`review_tree`・`tdd_lanes`・`fix_lanes`・`graph_map`
- SKILL.md の wait の終了コード（5）: `exit 0`・`exit 1`・`exit 3`・`exit 5`・`exit 6`
- use.sh の命令（9）: `start`・`show`・`wait`・`answer`・`approve`・`stop`・`apply`・`clean`・`check`
- use.sh の start の旗（7）: `--base`・`--pr`・`--spec`・`--rounds`・`--budget-usd`・`--chain-next`・`--`
- use.sh の環境変数（22）: `WORKS_USE_HOME`・`XDG_STATE_HOME`・`WORKS_USE_WAIT_SECONDS`・`WORKS_USE_ALLOW_DELETE`・`WORKS_USE_ALLOW_STOPPED`・`WORKS_USE_ALLOW_TESTCMD`・`WORKS_USE_FINAL_GATE`・`WORKS_DEV_ADAPTER`・`WORKS_USE_POLICY_MD`・`WORKS_USE_GATES`・`WORKS_USE_THICKNESS`・`WORKS_USE_FEATURES_OFF`・`WORKS_USE_FEATURES_ON`・`WORKS_USE_FIX_FIXTURE`・`WORKS_USE_UNATTENDED`・`WORKS_DESIGN_ONLY`・`WORKS_KEYCHAIN_ITEM`・`WORKS_DEV_MODEL`・`WORKS_DEV_ARCHON`・`CLAUDE_BIN_PATH`・`CLAUDE_CONFIG_DIR`・`HOME`
- use.sh の端末の道具との結び（1）: `use.sh:74`
- use.sh の拒み（38）: `use.sh:201`・`use.sh:205`・`use.sh:209`・`use.sh:214`・`use.sh:215`・`use.sh:220`・`use.sh:247`・`use.sh:251`・`use.sh:280`・`use.sh:297`・`use.sh:300`・`use.sh:315`・`use.sh:319`・`use.sh:322`・`use.sh:327`・`use.sh:330`・`use.sh:334`・`use.sh:403`・`use.sh:425`・`use.sh:431`・`use.sh:841`・`use.sh:899`・`use.sh:903`・`use.sh:904`・`use.sh:911`・`use.sh:913`・`use.sh:931`・`use.sh:941`・`use.sh:958`・`use.sh:959`・`use.sh:967`・`use.sh:969`・`use.sh:984`・`use.sh:989`・`use.sh:991`・`use.sh:1005`・`use.sh:1035`・`use.sh:1044`
- keep-essence.md の仕組み（12）: `keep-essence.md:10`・`keep-essence.md:11`・`keep-essence.md:12`・`keep-essence.md:13`・`keep-essence.md:14`・`keep-essence.md:15`・`keep-essence.md:16`・`keep-essence.md:17`・`keep-essence.md:18`・`keep-essence.md:19`・`keep-essence.md:20`・`keep-essence.md:21`

## SKILL.md

- S001 Claude Code のスキル `/works` として「darkfactory に回して」「works で直して」と頼むと呼べる
  - 元: SKILL.md:1-4
  - 印: 無し
  - 今: 無し（README.md「使い方」の末尾が、`/works` で同じ事ができるようになると先の話として書くだけ）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `coexist-before-switch`（`/works` の差し替えは持ち主の動作確認の後の段。それまでは別の入口として並べてよい）
  - 旧棚卸し: 無し

- S002 AI を起こして費用が掛かるのは起動の後と承認ノードで進めた後だけで、起動の前の確かめは AI を起こさない
  - 元: SKILL.md:11
  - 印: `SKILL.md:6`
  - 今: `workflows/line/scripts/start.py::start`（AI の前に入力を確かめ、拒めば ok: false で後ろを when: で飛ばす）・`workflows/line/works-factory-line.yaml::gate-start`
  - 状態: 在る
  - 旧棚卸し: L-E47・L-E52

- S003 要る物は macOS（Apple silicon）で、Archon は止めた版の darwin-arm64 の実行ファイルを初回に GitHub の release から落とす
  - 元: SKILL.md:15
  - 印: `SKILL.md:13`
  - 今: `bin/_lib/place.py::archon_source`・`bin/_lib/pack.py::load`
  - 状態: 形を変えて在る（ASF の止め `factory/pack.json` の commit の Archon の源を git で取り、bun で起こす。OS を限らない）
  - 旧棚卸し: 無し

- S004 要る物として git・uv・gh・Claude Code の `claude` を求める
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/launcher.py::target_root`（git）・`bin/_lib/launcher.py::real_claude`（claude。無ければ CLAUDE_BIN_PATH を案内して止まる）・`workflows/line/works-factory-line.yaml::start`（runtime: uv）・`bin/_lib/place.py::archon_source`（bun）・`bin/works-factory`（Python 3.12 以上）
  - 状態: 形を変えて在る（bun と Python 3.12 が足された。gh は無くても動き、並行 PR の確かめが役に回る）
  - 旧棚卸し: 無し

- S005 認証の段 1 として、`WORKS_KEYCHAIN_ITEM` で名指した keychain の項目を拾う
  - 元: SKILL.md:15
  - 印: `WORKS_KEYCHAIN_ITEM`
  - 今: `bin/_lib/auth_launch.py::ITEM_ENV`・`bin/_lib/auth_launch.py::resolve`
  - 状態: 形を変えて在る（名が `WORKS_FACTORY_KEYCHAIN_ITEM`）
  - 旧棚卸し: 無し

- S006 認証の段 2a として、受け継いだ `CLAUDE_CODE_OAUTH_TOKEN` など（API キー・Bedrock・Vertex）をそのまま使う
  - 元: SKILL.md:15
  - 印: `CLAUDE_CODE_OAUTH_TOKEN`
  - 今: `bin/_lib/claude_auth.py::INHERITED`・`bin/_lib/claude_auth.py::auth_env`
  - 状態: 在る
  - 旧棚卸し: 無し

- S007 認証の段 2b として、`CLAUDE_KEYCHAIN_SERVICE` で名指した keychain の項目を拾う
  - 元: SKILL.md:15
  - 印: `CLAUDE_KEYCHAIN_SERVICE`
  - 今: `bin/_lib/claude_auth.py::keychain_service`・`bin/_lib/auth_launch.py::resolve`
  - 状態: 在る
  - 旧棚卸し: 無し

- S008 認証の段 2c として、設定の置き場から keychain の項目の名を導いて読む
  - 元: SKILL.md:15
  - 印: 無し
  - 今: 無し（`bin/_lib/claude_auth.py::keychain_service` の docstring が、名を導く規則を持たない（E14）と明記）
  - 状態: 無い
  - 処置: 要らない: AGENTS.md の E14（持ち主の環境の字をリポジトリに書かない。`tests/layers/test_no_owner_env.py` が縛る）。名を知る人は S005・S007 で名指せる
  - 旧棚卸し: 無し

- S009 認証の段 3 として、Claude Code 自身が macOS の keychain に置いた項目（`CLAUDE_CONFIG_DIR` から導く）を拾う
  - 元: SKILL.md:15
  - 印: `CLAUDE_CONFIG_DIR`
  - 今: `bin/_lib/auth_launch.py::claude_code_items`・`bin/_lib/auth_launch.py::resolve`（macOS 以外の `.credentials.json` も読む）
  - 状態: 在る
  - 旧棚卸し: 無し

- S010 拾った認証の出どころの名を出し、値は出さない
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/launcher.py::launch`（「認証は <出どころ> から拾う（値は出さない）」）・`bin/_lib/auth_launch.py::main`（check）
  - 状態: 在る
  - 旧棚卸し: 無し

- S011 ログインの項目は数時間で切れるので、長い run には `claude setup-token` のトークンを置くよう案内する
  - 元: SKILL.md:15
  - 印: `CLAUDE_CODE_OAUTH_TOKEN`
  - 今: README.md「使い方」（長い run は `claude setup-token` のトークンを `CLAUDE_CODE_OAUTH_TOKEN` に置く）・`bin/_lib/auth_launch.py::HOWTO`（認証が無い時の 1 行）
  - 状態: 在る
  - 処置: 戻した: README.md「使い方」
  - 旧棚卸し: 無し

- S012 run の中の gh は利用者の gh のログインを継ぎ、トークンは gh 自身の置き場のままにする
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/hostgh.py::write`・`bin/_lib/hostgh.py::relay`・`bin/_lib/launcher.py::launch`
  - 状態: 在る
  - 旧棚卸し: 無し

- S013 AI の役の gh は読む形だけに絞り、PR への投稿を拒む（事故の柵）
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/no-post-bin/works-gh::ALLOWED`・`bin/_lib/launcher.py::launch`（役の PATH の頭に置く）
  - 状態: 在る
  - 旧棚卸し: J106

- S014 AI の役の `git push` を拒む
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/toolset.py::DENY_PUSH`・`bin/_lib/toolset.py::permissions`（隔離した設定の permissions.deny にいつも置く）
  - 状態: 在る
  - 処置: 戻した: `bin/_lib/toolset.py::DENY_PUSH`
  - 旧棚卸し: 無し

- S015 git の資格を run に渡さない
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `bin/_lib/isolate.py::isolate`・`bin/_lib/launcher.py::launch`（`hostgh.TOKENS` を子の環境から外す）
  - 状態: 在る
  - 旧棚卸し: 無し

- S016 利用者の gh がログインしていなければ、並行 PR の確かめは人に回る
  - 元: SKILL.md:15
  - 印: 無し
  - 今: `lib/judge_accept.py::pr_scan`（機械の道が読めなければ役 pr-check に任せ、役も読めなければ素材は人待ち）・`lib/ghreads.py::read_named`
  - 状態: 在る
  - 旧棚卸し: J41

- S017 marketplace を 2 つ足して works のプラグインを入れれば、依存の coldwrite・pr-review-toolkit も入り、リポジトリの clone は要らない
  - 元: SKILL.md:17-23
  - 印: 無し
  - 今: README.md「使い方」（1 の入れる: clone・bun・借りるプラグイン）・`bin/_lib/toolset.py::installed_sources`
  - 状態: 形を変えて在る（このリポジトリを clone して殻を打つ。借りるプラグインは利用者が入れ、足りなければ殻が入れる命令を並べて止まる）
  - 処置: 要らない: 持ち主の決め `coexist-before-switch`（プラグインの入口は切り替えの段まで claude-plugins に残る。README.md「関係」）
  - 旧棚卸し: 無し

- S018 superpowers は works に写した固定の版を使い、利用者が入れた版は使わない
  - 元: SKILL.md:17
  - 印: 無し
  - 今: `bin/_lib/toolset.py::installed_sources`・`bin/_lib/toolset.py::VENDORED`（`bin/_lib/borrow/borrow.json` の pin）
  - 状態: 在る
  - 旧棚卸し: F033

- S019 coldwrite・pr-review-toolkit は利用者の入れた版をそのまま使う
  - 元: SKILL.md:17
  - 印: 無し
  - 今: `bin/_lib/toolset.py::installed_sources`（kind "plugin" は利用者が入れたプラグインから取る）
  - 状態: 在る
  - 旧棚卸し: 無し

- S020 AI を起こさずに（費用なし）uv・claude・認証・対象の条件の足りない物を入れ方つきで全部並べて 0 以外で終わる確かめの命令を持つ
  - 元: SKILL.md:25-31
  - 印: `check`・`CLAUDE_PLUGIN_ROOT`
  - 今: `bin/_lib/launcher.py::launch`（`bin/works-factory validate` で借りる物を照らし、Archon の `validate` を起こす）
  - 状態: 形を変えて在る（validate は借りる物と Archon の検証だけを見る。認証は `workflow run` の時に初めて見る。origin・uv は見ない。最初に当たった所で止まる）
  - 処置: 要らない: 持ち主の決め `one-launcher`（足りない物は `workflow run` の時に Archon を起こす前、AI の費用の前に止まる。Archon 自身の点検は `doctor`）
  - 旧棚卸し: 無し

- S021 借りる物（coldwrite・pr-review-toolkit とその agent・hook）が足りないと、足りない物ごとの 1 行と入れるコマンドを出して止まり、起動も AI の前に同じ所で止まる
  - 元: SKILL.md:31
  - 印: 無し
  - 今: `bin/_lib/toolset.py::installed_sources`（ToolsetError「借りる物が足りない。AI を起こさずに止める」）・`bin/_lib/toolset.py::_how_to_install`・`bin/_lib/launcher.py::install_toolset`
  - 状態: 在る
  - 旧棚卸し: 無し

- S022 superpowers の写しが borrow.json の pin と合わない時、その行を出して止まる
  - 元: SKILL.md:31
  - 印: 無し
  - 今: `bin/_lib/toolset.py::installed_sources`・`bin/_lib/spseam.py::pin_problems`
  - 状態: 形を変えて在る（直し方の案内が works を入れ直す道でなく、リポジトリの写しを toolset.py vendor で取り直す道）
  - 旧棚卸し: 無し

- S023 スキルの中の `use.sh`・`stop.sh`・`report.sh` のパスを、Claude Code が入れた置き場の絶対パスへ置き換える
  - 元: SKILL.md:33
  - 印: `stop.sh`・`report.sh`・`CLAUDE_PLUGIN_ROOT`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `coexist-before-switch`（スキルとプラグインの入口はまだ無い。殻は `bin/works-factory` の 1 本でパスはリポジトリの中）
  - 旧棚卸し: 無し

- S024 `archon plugin install` で直に打たず、Archon を隔離した家で起こし、役には選んだ物だけの Claude の設定を読ませる（利用者の ~/.claude を読まない）
  - 元: SKILL.md:35
  - 印: 無し
  - 今: `bin/_lib/isolate.py::isolate`・`bin/_lib/toolset.py::install`・`bin/_lib/launcher.py::install_toolset`
  - 状態: 在る
  - 旧棚卸し: 無し

- S025 依頼のファイルとして、findings の配列か `{findings, pr, issue, answers, prior_failures}` の object を受ける
  - 元: SKILL.md:39
  - 印: `SKILL.md:37`・`findings`・`pr`・`issue`・`answers`・`prior_failures`
  - 今: `lib/carry.py::parts`・`workflows/line/scripts/start.py::request`（object に constraints の欄も足された）
  - 状態: 在る
  - 旧棚卸し: L-E01

- S026 依頼のファイルはどこに置いてもよい（起動のときに写して渡す）
  - 元: SKILL.md:39
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::request`（`--input request=<パス>` を start ノードが読む）
  - 状態: 形を変えて在る（写さずに読む。相対パスは Archon が切った run の作業ツリーの根から読むので、commit していない依頼のファイルは絶対パスで渡す）
  - 旧棚卸し: L-E06

- S027 findings の必須の欄 `where`・`text` を求める
  - 元: SKILL.md:53
  - 印: `where`・`text`
  - 今: `lib/entry.py::REQUEST_SCHEMA`・`lib/entry.py::request_problems`
  - 状態: 在る
  - 旧棚卸し: L-E01

- S028 `text` には問題と目的を書き、解き方は「案（工場が定石と比べて疑う）: …」と分け、工場は案を目的から外して足し欄 `means` に置く
  - 元: SKILL.md:54
  - 印: `text`
  - 今: `workflows/judge/works-factory-judge.yaml::purpose`（指示書 `workflows/judge/commands/purpose.md` の目的と解き方を分ける指示）・`lib/judge_accept.py::check_purpose`
  - 状態: 在る
  - 旧棚卸し: J18

- S029 案を同じ種類の問題の世の中の定石と比べ、違えば違いを名指して定石を推す（案は決め手にならない）
  - 元: SKILL.md:54
  - 印: 無し
  - 今: `workflows/judge/works-factory-judge.yaml::world-classes`・`lib/worldblk.py`
  - 状態: 在る
  - 旧棚卸し: J28

- S030 案と定石の違いを報告のセクション「世界の解」に並べる
  - 元: SKILL.md:54
  - 印: 無し
  - 今: `lib/report.py::WORLD_HEADING`
  - 状態: 在る
  - 旧棚卸し: J112

- S031 案を理由に定石から外れる修正案は、修正前の承認ノードで依頼者に聞く
  - 元: SKILL.md:54
  - 印: 無し
  - 今: `lib/gatemarks.py::WORLD_KIND`
  - 状態: 在る
  - 旧棚卸し: L-G20・L-G29

- S032 任意の欄 `mechanism`・`measured`・`false_positive_if` を受ける
  - 元: SKILL.md:55
  - 印: `mechanism`・`measured`・`false_positive_if`
  - 今: `lib/entry.py::REQUEST_SCHEMA`
  - 状態: 在る
  - 旧棚卸し: L-E01

- S033 これ以外の欄を拒み、型の確かめはメイングラフの入口で AI を起こす前に止まる
  - 元: SKILL.md:56
  - 印: 無し
  - 今: `lib/entry.py::REQUEST_SCHEMA`（additionalProperties: false）・`lib/carry.py::parts`（知らない鍵）・`workflows/line/scripts/start.py::request`
  - 状態: 在る
  - 旧棚卸し: L-E01・L-E02

- S034 object の `pr`・`issue` を正の整数の配列として受ける
  - 元: SKILL.md:57
  - 印: `pr`・`issue`
  - 今: `lib/carry.py::parts`
  - 状態: 在る
  - 旧棚卸し: L-E18

- S035 名指した PR・issue の本文とコメントを、run の入口が利用者の gh のログインを継いで 1 回だけ読み、run の置き場の `github.json` に置く（読めない物は読めないと記録して進む）
  - 元: SKILL.md:57
  - 印: 無し
  - 今: `lib/entryshape.py::github_reads`・`lib/ghreads.py::read_named`・`lib/ghreads.py::place`
  - 状態: 在る
  - 旧棚卸し: L-E11・L-E18

- S036 `--pr` の base・head が読めなければ起動の時に止まる
  - 元: SKILL.md:57
  - 印: `--pr`・`start`
  - 今: `lib/entryshape.py::change_base`
  - 状態: 在る
  - 旧棚卸し: L-E14

- S037 object の形で `findings` を省くと空の配列になり、pr・answers・差分だけの依頼が通る
  - 元: SKILL.md:57
  - 印: `findings`
  - 今: `workflows/line/scripts/start.py::request`（空の findings には型の確かめを当てない）・`lib/entryshape.py::refuse_empty`（差分も依頼の行も無い時だけ拒む）
  - 状態: 在る
  - 処置: 戻した: `workflows/line/scripts/start.py::request`
  - 旧棚卸し: L-E01

- S038 `answers` を `[{question, text, command?, output?}]` の形で受け、question・text は空でない文字列、command と output は両方か無し、同じ question は 1 度だけ（違えば入口で拒む）
  - 元: SKILL.md:63
  - 印: `answers`・`question`・`text`・`command`・`output`
  - 今: `lib/carry.py::_answers`
  - 状態: 在る
  - 旧棚卸し: L-E04

- S039 当たった答えは修正前の承認ノードに載せず、保留にも数えず、報告と最後の承認ノードに「依頼者の答え: …」と並べる
  - 元: SKILL.md:63
  - 印: 無し
  - 今: `lib/gatemarks.py::request_answers`・`lib/gatemarks.py::answer_note`・`lib/gatemarks.py::answered_lines`
  - 状態: 在る
  - 旧棚卸し: L-G34・L-G37

- S040 `question` の字が問いの key と違う答えは判定役が問いか単位に結び、結ばれない答えは受け付けが判定の出力を拒み、当たらないと名乗った答えは訳つきで並べる
  - 元: SKILL.md:63
  - 印: `question`
  - 今: `lib/gatemarks.py::answer_ties`・`lib/gatemarks.py::_tie_row_problems`・`lib/judge_accept.py::answer_tie_problems`・`lib/gatemarks.py::answer_tie_lines`
  - 状態: 在る
  - 旧棚卸し: L-G34

- S041 どの問いにも当たらなかった答えも名指しで並べる
  - 元: SKILL.md:63
  - 印: 無し
  - 今: `lib/gatemarks.py::unmatched_answer_lines`
  - 状態: 在る
  - 旧棚卸し: L-G37・R26

- S042 `question` が測れなかった素材の名（`parallel_pr`・`main_path_observation` など）なら、問いが無くても当てる
  - 元: SKILL.md:63
  - 印: `question`
  - 今: `lib/gatemarks.py::material_answer`
  - 状態: 在る
  - 旧棚卸し: L-G34

- S043 素材への答えが command と output を両方持てば、素材の未実施を残りに数えず「人が手元で確かめた（実測とは書かない）」と命令と出力つきで並べる
  - 元: SKILL.md:63
  - 印: `command`・`output`
  - 今: `lib/gatemarks.py::HAND_CHECKED`・`lib/gatemarks.py::material_answer`
  - 状態: 在る
  - 旧棚卸し: R18

- S044 command・output の無い答えは測りの代わりにせず、未実施は残りに数えたままにする
  - 元: SKILL.md:63
  - 印: 無し
  - 今: `lib/gatemarks.py::material_answer`
  - 状態: 在る
  - 旧棚卸し: R18

- S045 前の run が `next-request.json` に置いた答えの下書き（`draft: true` と `source`）を入口が拒む（採るなら印を消し、採らないなら行を消す）
  - 元: SKILL.md:63
  - 印: `draft`・`source`
  - 今: `lib/carry.py::_answers`・`lib/carry.py::is_draft`
  - 状態: 在る
  - 旧棚卸し: L-G41

- S046 前の run の報告が、保留の問い・測れなかった素材・無人の run が承認ノードで止まった時に、答えの下書きを `next-request.json` の answers に置く
  - 元: SKILL.md:63
  - 印: 無し
  - 今: `lib/runreport.py::answer_drafts`・`lib/gatemarks.py::_material_draft`
  - 状態: 在る
  - 旧棚卸し: L-G41・L-D53

- S047 承認ノードの項目の行（question が承認ノードの項目の文）は依頼では当たらないので、次の run の承認ノードの continue の一言に写してから消すよう入口の拒みの文が案内する
  - 元: SKILL.md:63
  - 印: 無し
  - 今: `lib/carry.py::_answers`
  - 状態: 在る
  - 旧棚卸し: L-G41

- S048 `prior_failures` を `[{where, text}]`（どちらも空でない文字列）の形で受ける
  - 元: SKILL.md:70
  - 印: `prior_failures`・`where`・`text`
  - 今: `lib/carry.py::_prior_failures`
  - 状態: 在る
  - 旧棚卸し: L-D51

- S049 前の run の報告が `next-request.json` に prior_failures を書く
  - 元: SKILL.md:70
  - 印: 無し
  - 今: `lib/runreport.py::next_request`・`lib/carry.py::compose`
  - 状態: 在る
  - 旧棚卸し: L-D53

- S050 prior_failures を判定役と修正案の役の材料に貼り、目的の役と独立設計の役には渡さない
  - 元: SKILL.md:70
  - 印: 無し
  - 今: `lib/carry.py::prior_section`・`lib/planfile.py::prior_section`・`lib/carry.py::without_prior`・`lib/purpose.py::REQUEST_COPY`
  - 状態: 在る
  - 旧棚卸し: L-E05・L-D50・L-D52

- S051 受け付けが最後まで拒んだ理由の行は直す穴ではない注意として、独立の目 R2 の作り直しの行（where が `独立の目 R2`）は直す穴の別のセクションに貼り、次の周の先頭で直す
  - 元: SKILL.md:70
  - 印: 無し
  - 今: `lib/carry.py::prior_section`・`lib/carry.py::REDESIGN_HEAD`・`lib/carry.py::is_redesign`
  - 状態: 在る
  - 旧棚卸し: L-D52

- S052 判定役が R2 の行を 1 行ずつ反証し、生き残りを [block] か do-now の単位にし、死んだ行と目的の外の行は訳つきで報告に並べて次に運ばない
  - 元: SKILL.md:70
  - 印: 無し
  - 今: `lib/judge_accept.py::redesign_rows`・`lib/gatemarks.py::_tie_row_problems`（redesign の結び）
  - 状態: 在る
  - 旧棚卸し: L-D52

- S053 run の後の CI で赤だった試験の id を prior_failures に足す（where は `run の後の CI`、同じ行は 2 度足さない）
  - 元: SKILL.md:71
  - 印: `carry-ci`・`prior_failures`
  - 今: `lib/carry.py::carry_ci`・`lib/carry.py::main`（README.md「使い方」の 6。呼ぶ形は `python3 -I lib/carry.py carry-ci`）
  - 状態: 在る
  - 旧棚卸し: L-D54

- S054 起動の命令を前景で打ち、最初の承認ノードで戻る
  - 元: SKILL.md:75-78
  - 印: `SKILL.md:73`・`start`
  - 今: `bin/_lib/launcher.py::launch`・Archon の `workflow run`（`works-factory-line --cwd <対象> --input request=<依頼>`。承認ノードで止まって戻る）
  - 状態: 形を変えて在る（start の別名は無く、Archon の命令をそのまま打つ。持ち主の決め `one-launcher`）
  - 旧棚卸し: 無し

- S055 どの入口（依頼の JSON・base・PR）も 1 つの入力の形（差分の根・差分・依頼の行・PR の題と本文）に揃え、後ろは中身だけで決まる
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `lib/entryshape.py::build`
  - 状態: 在る
  - 旧棚卸し: L-E19・L-E55

- S056 差分が空の run は判定から入り、P1 の局所の審査の役は起こさない
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `lib/startrec.py::words`（P1_OFF_WORDS）・`workflows/judge/works-factory-judge.yaml::local-review-loop`（material-route が決める）
  - 状態: 在る
  - 旧棚卸し: L-E22

- S057 差分も依頼の行も無ければ AI の前で止まる
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `lib/entryshape.py::refuse_empty`（EMPTY_REFUSED）
  - 状態: 在る
  - 旧棚卸し: L-E07・L-E52

- S058 base と HEAD の merge-base から HEAD までを差分にする入口を持つ
  - 元: SKILL.md:81
  - 印: `--base`
  - 今: `lib/entryshape.py::change_base`・`lib/entryshape.py::merge_base`
  - 状態: 形を変えて在る（`--input base=<版>` で渡す。Archon の `--base` は run の作業ツリーを切る枝で、別の意味）
  - 旧棚卸し: L-E09・L-E10

- S059 GitHub の PR と同じ差分を、利用者の gh で読むだけで投稿せずに取る入口を持ち、読めなければ起動しない
  - 元: SKILL.md:81
  - 印: `--pr`
  - 今: `lib/entryshape.py::change_base`・`lib/entryshape.py::github_reads`・`lib/ghreads.py::read_named`
  - 状態: 形を変えて在る（`--input pr=<番号>`。殻が Archon の前に読むのでなく、run の中の start ノードが読み、読めなければ AI の前で止まる）
  - 旧棚卸し: L-E11・L-E12・L-E14

- S060 PR の入口では対象の HEAD が PR の head であることを求め、違えば拒む
  - 元: SKILL.md:81
  - 印: `--pr`
  - 今: `lib/entryshape.py::change_base`・`bin/_lib/startpoint.py::choose`（殻が Archon に `--from` で対象の今の HEAD を渡すので、PR の枝を取り出して頼めば run の作業ツリーもそこから切られる。#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: L-E13

- S061 base・PR の入口では名指した差分の全体に局所レビューのレンズ（`/code-review`・`/simplify`・pr-review-toolkit の agent）を 1 本ずつ回し、所見を判定に流す（費用が増える）
  - 元: SKILL.md:81
  - 印: `--pr`・`--base`
  - 今: `workflows/judge/works-factory-judge.yaml::local-review-loop`（指示書 `workflows/judge/commands/material-local-review.md`）・`lib/lenses.py`
  - 状態: 在る
  - 旧棚卸し: J56・J110

- S062 起動の時に差分の根を示す行を出す
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::gate_text`・`lib/startrec.py::words`
  - 状態: 形を変えて在る（起動の承認ノードの文の「入口: 差分 <版>..HEAD（N ファイル・<出どころ>）」の句）
  - 旧棚卸し: L-E22・L-E48

- S063 依頼の欄 `pr` に番号を書くのは読むだけで、差分の審査を足さない
  - 元: SKILL.md:81
  - 印: `pr`
  - 今: `lib/entryshape.py::named`（読むだけ）・`lib/entryshape.py::change_base`（差分の根は入力 pr だけから）
  - 状態: 在る
  - 旧棚卸し: L-E18

- S064 依頼の JSON を `-` にすると依頼を省き、base・PR の入口が無ければ拒む
  - 元: SKILL.md:81
  - 印: `--base`・`--pr`
  - 今: `workflows/line/scripts/start.py::request`（request を空にする）・`lib/entryshape.py::refuse_empty`
  - 状態: 形を変えて在る（`-` の語は無く、request を渡さない。差分が空なら拒む）
  - 旧棚卸し: L-E07

- S065 依頼と差分の両方を渡すと一緒に判定へ流し、依頼の文と PR の題・本文は両方とも判定と目的の役に届く
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `lib/entryshape.py::request_text`・`lib/entryshape.py::write_pr_file`
  - 状態: 在る
  - 旧棚卸し: L-E16・L-E17

- S066 判定の前に仕様の段（書き手が要件と受け入れ条件のテストを書き、別の目が審査し、人が承認ノードで承認）を挟み、どの入口とも組める
  - 元: SKILL.md:81
  - 印: `--spec`
  - 今: `workflows/judge/works-factory-judge.yaml::spec-loop`・`workflows/judge/works-factory-judge.yaml::spec-gate`・`workflows/judge/works-factory-judge.yaml::spec-freeze`・`workflows/line/scripts/start.py::words`
  - 状態: 形を変えて在る（`--input spec=on`）
  - 旧棚卸し: L-E27・J92〜J99

- S067 仕様の段は依頼の findings か PR の題と本文を求める
  - 元: SKILL.md:81
  - 印: `--spec`
  - 今: `workflows/line/scripts/start.py::start`
  - 状態: 在る
  - 旧棚卸し: L-E29

- S068 仕様の段は無人の run と組めない
  - 元: SKILL.md:81
  - 印: `--spec`・`WORKS_USE_UNATTENDED`
  - 今: `lib/gatepolicy.py::check`
  - 状態: 在る
  - 旧棚卸し: L-E28・L-G13

- S069 仕様の段は固定材料と組めない
  - 元: SKILL.md:81
  - 印: `--spec`
  - 今: `workflows/line/scripts/start.py::words`
  - 状態: 在る
  - 旧棚卸し: L-E42

- S070 修正が受け入れ条件のテストのファイルを変えると、承認し直すかの問いを最後の承認ノード・報告の冒頭・次の run の依頼に載せ、差分の審査・最後のテスト・独立の目を回さずに終わる
  - 元: SKILL.md:81
  - 印: 無し
  - 今: `workflows/line/scripts/spec_check.py::check`・`lib/judge_accept.py::spec_questions`・`bin/_lib/apply.py::respec_note`
  - 状態: 形を変えて在る（差分の審査・最後のテスト・独立の目は回したまま、問いを最後の承認ノード・報告の冒頭・次の依頼の下書きに載せて人待ちで終わる。照らせなかった時はそう言い、bin/apply は承認し直すかの問いを残した run を 1 行で知らせて当てる（今の works は黙って当てた））
  - 処置: 戻した: `workflows/line/scripts/spec_check.py::check`
  - 旧棚卸し: J97

- S071 base と PR の入口はどちらか 1 つだけ受ける
  - 元: SKILL.md:81
  - 印: `--base`・`--pr`
  - 今: `lib/entryshape.py::change_base`
  - 状態: 在る
  - 旧棚卸し: L-E08

- S072 旗は対象より前に置き、`--` の後は旗として読まない
  - 元: SKILL.md:81
  - 印: `--`
  - 今: `bin/_lib/launcher.py::require_command_first`・`bin/_lib/launcher.py::before_double_dash`・止めた Archon の `parseArgs`（strict。`packages/cli/src/cli.ts`）
  - 状態: 形を変えて在る（旗は命令の後ろに置く。README.md「使い方」）
  - 旧棚卸し: 無し

- S073 手元に commit していない変更が在ると、PR の入口は PR の head と違うとして拒み、base の入口の差分には包んだ手元の変更も入る
  - 元: SKILL.md:81
  - 印: `--pr`・`--base`
  - 今: `lib/entryshape.py::change_base`・`bin/_lib/startpoint.py::wrap`・README.md「作業ツリーの起点」（包んだ commit は PR の head と違うので run の始めで拒まれ、base の入口の差分には包んだ変更が入る。#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- S074 対象はリポジトリの下のフォルダでもよく、その git の根で回し、省けば今いるフォルダの git の根で回す
  - 元: SKILL.md:82
  - 印: 無し
  - 今: `bin/_lib/launcher.py::target_root`（`--cwd` か打った場所）
  - 状態: 在る
  - 旧棚卸し: 無し

- S075 `/private/tmp` の下の対象を拒む
  - 元: SKILL.md:82
  - 印: 無し
  - 今: `bin/_lib/launcher.py::refuse_sandbox_writable`・`bin/_lib/launcher.py::SANDBOX_WRITABLE`
  - 状態: 形を変えて在る（拒むのは実パスが `/tmp/claude-*`・`/private/tmp/claude-*` の下の対象・家・取り置きだけ）
  - 処置: 要らない: 役の sandbox が書ける置き場（`bin/_lib/launcher.py::SANDBOX_WRITABLE`）の柵に絞った
  - 旧棚卸し: 無し

- S076 commit していない変更・未追跡のファイルが在っても止めず、殻が一時の commit に包み（.gitignore の物は入れない）run をそこから切り、差分を今の手元にそのまま当たる形にする
  - 元: SKILL.md:83
  - 印: 無し
  - 今: `bin/_lib/startpoint.py::choose`・`bin/_lib/startpoint.py::wrap`・README.md「作業ツリーの起点」（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- S077 包んだ commit を守る参照を `refs/works/wraps/` にだけ置き、対象の作業ツリー・index・枝は動かさず、片付けと結べなかった起動の控えで参照を外す
  - 元: SKILL.md:83
  - 印: `clean`
  - 今: `bin/_lib/startpoint.py::wrap`
  - 状態: 形を変えて在る（包んだ commit に ref を付けず、Archon が起動の内にそこから切る run の枝が守る。対象の作業ツリー・index・枝は動かさない。#495 を #503 で戻した）
  - 処置: 要らない: 片付ける ref を作らないので clean の片付けも要らない。gc から守るのは Archon が切る run の枝（`on-archon-only`）
  - 旧棚卸し: 無し

- S078 包んだことと commit・ファイルを「包んだ（wrapped）」の行に出し、状態を見る命令も出す
  - 元: SKILL.md:83
  - 印: `show`
  - 今: `bin/_lib/startpoint.py::choose`
  - 状態: 形を変えて在る（包んだ commit とファイルを起動の 1 行に出す。状態を見る命令は出さない。#495 を #503 で戻した）
  - 処置: 要らない: 状態を見る命令は README.md「使い方」の 4 が Archon の `workflow status` で言う（`on-archon-only`）
  - 旧棚卸し: 無し

- S079 remote の `origin` を求め、無ければ確かめの命令が並べ、起動は Archon を起こす前に 1 行で止まって入れ方（`git remote add origin`・手元だけなら対象の外に裸のリポジトリ・`git remote set-head`）を出す。殻は remote を足さない
  - 元: SKILL.md:84
  - 印: `check`・`start`
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`。「Cannot detect default branch … Pass --base …」で止まる）・止めた Archon の `syncWorkspace`（`packages/git/src/repo.ts`）
  - 状態: 形を変えて在る（殻は確かめず、Archon が作業ツリーを切る所で自分の文で止まる。裸の origin の作り方の案内は無い）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が `--base` を名指せと直し方つきで止まる（`on-archon-only`）
  - 旧棚卸し: 無し

- S080 スキルを読む AI は自分で remote を足さず、預ける先の URL か手元の裸のリポジトリかを依頼者に尋ねる
  - 元: SKILL.md:84
  - 印: 無し
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: スキルの答え方の決まりで、スキルがまだ無い（持ち主の決め `coexist-before-switch`）
  - 旧棚卸し: 無し

- S081 起動の度に origin の既定の枝（origin/HEAD、無ければ origin/main、次に origin/master）を Archon の土台に渡す
  - 元: SKILL.md:85
  - 印: `start`
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`。origin/HEAD だけを読み、推さない）・Archon の `workflow run --base`
  - 状態: 形を変えて在る（殻は渡さず Archon が毎回 origin/HEAD を読む。origin/main・origin/master へは進まない）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が持ち、推さずに `--base` を名指せと言う（`on-archon-only`）
  - 旧棚卸し: 無し

- S082 既定の枝がどれも無ければ枝を推さず、`git fetch origin` と `git remote set-head origin -a` を案内して止まる
  - 元: SKILL.md:85
  - 印: 無し
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）
  - 状態: 形を変えて在る（Archon の文は `--base`・worktree.baseBranch・default_branch を案内する。fetch・set-head の案内は無い）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が直し方つきで止まる（`on-archon-only`）
  - 旧棚卸し: 無し

- S083 `origin/HEAD` が消えた枝を指す時はそれを渡さず次の枝へ進む
  - 元: SKILL.md:85
  - 印: 無し
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`。古くなった HEAD を使わない）
  - 状態: 形を変えて在る（古い origin/HEAD を使わない点は同じで、次の枝へ進まずに止まる）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が持つ（`on-archon-only`）
  - 旧棚卸し: 無し

- S084 修正の前と最後に回すテストのコマンド test_cmd を省ける入力として受ける
  - 元: SKILL.md:86
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::raw_inputs`・`lib/declared_checks.py::local_checks_material`
  - 状態: 形を変えて在る（位置の引数でなく `--input test_cmd=<命令>`）
  - 旧棚卸し: L-E38

- S085 test_cmd は機械が役の sandbox の外で直に走らせ、網も使える（網の要る検査は test_cmd に入れる）
  - 元: SKILL.md:86
  - 印: 無し
  - 今: `workflows/test-gate/works-factory-test-gate.yaml`（script ノードの run）・`lib/declared_checks.py::run_ci`
  - 状態: 在る
  - 旧棚卸し: T20・T21

- S086 雲の資格の要る検査が確かめの素材に残れば結末を `fixed_needs_check` にし、手元で確かめて次の依頼の answers に command・output を添えて返す道を示す
  - 元: SKILL.md:86
  - 印: `fixed_needs_check`・`answers`・`command`・`output`
  - 今: `lib/outcome.py::OK_OUTCOMES`・`lib/report.py::CHECKS_LEFT`・`lib/gatemarks.py::material_answer`
  - 状態: 在る
  - 旧棚卸し: R9・R18

- S087 test_cmd が在れば `.review-checks.json` の宣言に加えて回し、両方が緑の時だけ緑とし、宣言の段と同じコマンドなら 1 度だけ回す
  - 元: SKILL.md:86
  - 印: 無し
  - 今: `lib/declared_checks.py::_with_test_cmd`・`lib/declared_checks.py::_same_step`
  - 状態: 在る
  - 旧棚卸し: T2・T3

- S088 test_cmd を省くか空なら宣言を回し、宣言も無ければ CI の任せ先の役が走らせ方を探す
  - 元: SKILL.md:86
  - 印: 無し
  - 今: `lib/declared_checks.py::checks_plan`・`workflows/line/scripts/start.py::test_notes`
  - 状態: 在る
  - 旧棚卸し: T5・T6

- S089 run の worktree には無視される物（.venv・node_modules・.env）が無いので、test_cmd を worktree の中で環境を作る形にするよう README で案内する
  - 元: SKILL.md:86
  - 印: 無し
  - 今: README.md「test_cmd と作業ツリー」・`bin/_lib/testcmd_check.py::HOW`（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- S090 手元を走らせる形の test_cmd（手元の物を絶対パスで指す・editable の外の環境・立てた環境）を見つけると `止める（test_cmd）` の行を出し、Archon を起こさずに終了コード 2 で止まる（形の確かめが落ちた時も 1 行で止まる）
  - 元: SKILL.md:86
  - 印: `start`
  - 今: `bin/_lib/launcher.py::check_test_cmd`・`bin/_lib/testcmd_check.py::path_notes`・`bin/_lib/testcmd_check.py::venv_notes`（止める形と、形の確かめが落ちた時に Archon を起こさず終了コード 2 で止まる。#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- S091 依頼者が形を知った上で回すと決めた時だけ、手元を走らせる形の test_cmd を通す（AI が自分で付けない）
  - 元: SKILL.md:86
  - 印: `WORKS_USE_ALLOW_TESTCMD`
  - 今: `bin/_lib/launcher.py::ALLOW_TESTCMD_ENV`・`bin/_lib/launcher.py::check_test_cmd`
  - 状態: 形を変えて在る（名は `WORKS_FACTORY_ALLOW_TESTCMD`。#495 を #503 で戻した）
  - 旧棚卸し: 無し

- S092 相対パスのように worktree で走らない形の test_cmd は `注意（test_cmd）` の行だけ出して止めない
  - 元: SKILL.md:86
  - 印: 無し
  - 今: `bin/_lib/testcmd_check.py::path_notes`・README.md「test_cmd と作業ツリー」（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- S093 `.review-checks.json` の段の任意の `junit` を読み、報告が無い・段の起動より古い・0 件・全部 error なら、赤でなく基準の検査が走らなかった（コードの赤ではない）に回す
  - 元: SKILL.md:87
  - 印: 無し
  - 今: `lib/declared_checks.py::_junit_unran`・`lib/declared_checks.py::checks_reply`
  - 状態: 在る
  - 旧棚卸し: T27

- S094 `junit` を持たない段の赤は赤のまま、走ったかは確かめていないと添える
  - 元: SKILL.md:87
  - 印: 無し
  - 今: `lib/declared_checks.py::checks_reply`・`lib/gatemarks.py::BASELINE_UNVERIFIED`
  - 状態: 在る
  - 旧棚卸し: T23

- S095 `.works-checks.json` の `paths_ignore` の下に run の変更が全部在れば、修正前の確かめと最後のテストでその段を回さず、範囲の外で回さなかった段として名と範囲を出す
  - 元: SKILL.md:88
  - 印: 無し
  - 今: `lib/checkscope.py::read_scope`・`lib/checkscope.py::skipped_steps`・`lib/checkscope.py::skipped_text`・`lib/checkscope.py::request_files`・`lib/declared_checks.py::suites_line`
  - 状態: 在る
  - 旧棚卸し: T13・T15・T16・T17・T18

- S096 変更が範囲の外に 1 本でも在る・測れない・全段が外れる時は段を回す
  - 元: SKILL.md:88
  - 印: 無し
  - 今: `lib/checkscope.py::skipped_steps`
  - 状態: 在る
  - 旧棚卸し: T14

- S097 `.works-checks.json` の書式の誤り・宣言に無い段の名・`.review-checks.json` 自体が無い時は、名指して止める
  - 元: SKILL.md:88
  - 印: 無し
  - 今: `lib/checkscope.py::read_scope`・`lib/declared_checks.py::run_ci`（CiRefused）
  - 状態: 在る
  - 旧棚卸し: T10・T11・T12

- S098 JUnit XML の書き先を第 1 引数に受ける実行器 tdd_suite を省ける入力として受け、在れば修正の段で単位ごとの TDD のループを回す
  - 元: SKILL.md:89
  - 印: 無し
  - 今: `lib/tddloop.py`・`workflows/line/scripts/start.py::raw_inputs`
  - 状態: 形を変えて在る（`--input tdd_suite=<実行器>`）
  - 旧棚卸し: F012・F027・L-E38

- S099 TDD のループの赤・緑の回は env `TDD_SUITE_ONLY=1` を付けて実行器を呼ぶ
  - 元: SKILL.md:89
  - 印: `TDD_SUITE_ONLY`
  - 今: `lib/tddloop.py::ONLY_ENV`
  - 状態: 在る
  - 旧棚卸し: F012

- S100 tdd_suite を省き test_cmd が pytest の 1 コマンドなら、`--junitxml` を足す実行器を書いて TDD のループに渡す
  - 元: SKILL.md:89
  - 印: 無し
  - 今: 無し（`lib/tddloop.py::NO_SUITE` の道で TDD のループを飛ばし、`workflows/line/scripts/start.py::test_notes` が起動の承認ノードの文でそう言う。test_cmd から特定の実行器の旗を足す知識は `lib/` に置けず（AGENTS.md の E13・持ち主の決め `lang-neutral`）、持ち主の決め `superset` とのどちらを取るかは持ち主が決める）
  - 状態: 無い
  - 処置: #516
  - 旧棚卸し: 無し

- S101 実行器が無ければ TDD のループを飛ばして直に直し、どちらにしたかを 1 行出す
  - 元: SKILL.md:89
  - 印: 無し
  - 今: `lib/tddloop.py::SUITE_SKIPPED`・`workflows/line/scripts/start.py::test_notes`（起動の承認ノードの文に 1 行）・`lib/report.py::freeze_lines`
  - 状態: 在る
  - 旧棚卸し: F027

- S102 最後の承認ノードは既定で守りのファイルを触った時だけ開く
  - 元: SKILL.md:90
  - 印: `protected_only`・`apply`
  - 今: `lib/gatepolicy.py::check`（空の既定は always）
  - 状態: 形を変えて在る（既定は always。`--input final_gate=protected_only` で同じ動き）
  - 処置: 要らない: 今の works でもメイングラフの既定は always だった（`lib/gatepolicy.py::check`。L-E30）。`--input final_gate=protected_only` で同じ事ができ、既定を変えるのは止まる所を減らす向きなので持ち主の決め無しには変えない
  - 旧棚卸し: L-E30・L-G11

- S103 最後の承認ノードを、テストの赤・目の阻害・残った異議でも開く語と、いつも開く語で選べる
  - 元: SKILL.md:90
  - 印: `WORKS_USE_FINAL_GATE`・`when_needed`・`always`
  - 今: `lib/gatepolicy.py::check`・`lib/gatepolicy.py::opens`
  - 状態: 形を変えて在る（環境変数でなく `--input final_gate=<語>`）
  - 旧棚卸し: L-G14

- S104 Claude の包み（claude-adapter）を既定で通す
  - 元: SKILL.md:91
  - 印: 無し
  - 今: `workflows/.shared/fence.py`・`bin/_lib/launcher.py::write_fence`
  - 状態: 形を変えて在る（書き込みの柵の包み fence を役の起動に常に通す）
  - 旧棚卸し: L-E39・T49

- S105 包みを外す道を持ち、起動の 1 行目と報告に「包み無し」と出す
  - 元: SKILL.md:91
  - 印: `WORKS_DEV_ADAPTER`
  - 今: 無し（`lib/declared_checks.py::NO_ADAPTER_NOTE` の字だけ残る）
  - 状態: 無い
  - 処置: 要らない: 旧棚卸し L-E39 の決め（役は Archon の役のノードが起こし、包みを通らない道が無い。持ち主の決め `archon-base`）
  - 旧棚卸し: L-E39

- S106 メイングラフの入力 `policy_md` を渡せる
  - 元: SKILL.md:92
  - 印: `WORKS_USE_POLICY_MD`
  - 今: `workflows/line/scripts/start.py::policy_md`
  - 状態: 形を変えて在る（`--input policy_md=<パス>`）
  - 旧棚卸し: L-E35

- S107 メイングラフの入力 `gates` を渡せる
  - 元: SKILL.md:92
  - 印: `WORKS_USE_GATES`
  - 今: 無し（メイングラフの inputs に gates が無い）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `no-mutation-in-graph`（gates は変異の検算の段の語）
  - 旧棚卸し: L-E40

- S108 厚みを空（自動）・`標準`・`軽量` から選べる
  - 元: SKILL.md:92
  - 印: `WORKS_USE_THICKNESS`
  - 今: `workflows/line/scripts/start.py::words`（THICKNESS・HEAVY）
  - 状態: 形を変えて在る（`--input thickness=<語>`。`自動` も受け、`重厚` は拒む）
  - 旧棚卸し: L-E25

- S109 機能の語 judge_verify・review_tree・tdd_lanes・fix_lanes・graph_map をカンマで区切って切る・入れる
  - 元: SKILL.md:93
  - 印: `WORKS_USE_FEATURES_OFF`・`WORKS_USE_FEATURES_ON`・`judge_verify`・`review_tree`・`tdd_lanes`・`fix_lanes`・`graph_map`
  - 今: `lib/entry.py::FEATURES`・`lib/entry.py::features_off`・`lib/entry.py::features_on`
  - 状態: 形を変えて在る（`--input features_off=…`。語に world が足された。知らない語は拒む）
  - 旧棚卸し: L-E31・L-E32

- S110 既定は judge_verify が off・review_tree が auto（開いた項目が 2 つ以上の往復だけ木）・ほかは on で、名指した語が既定に勝つ
  - 元: SKILL.md:93
  - 印: `judge_verify`・`review_tree`・`WORKS_USE_FEATURES_ON`
  - 今: `lib/entry.py::FEATURE_DEFAULTS`・`lib/entry.py::feature_words`
  - 状態: 在る
  - 旧棚卸し: L-E32

- S111 同じ語を features_on と features_off の両方に名指すと起動の時に止める
  - 元: SKILL.md:93
  - 印: `start`
  - 今: `workflows/line/scripts/start.py::words`
  - 状態: 在る
  - 旧棚卸し: L-E31

- S112 on でない機能を報告の冒頭 2 に、入力を `versions.json` の `settings` に残す
  - 元: SKILL.md:93
  - 印: 無し
  - 今: `lib/entry.py::features_part`・`lib/runreport.py::_entry_lines`・`workflows/line/scripts/start.py::version_record`
  - 状態: 形を変えて在る（入力の控えは別のファイル versions.json でなく、始めの記録の versions.settings）
  - 旧棚卸し: L-E44

- S113 無人で回す道を持つ
  - 元: SKILL.md:94
  - 印: `WORKS_USE_UNATTENDED`
  - 今: `lib/gatepolicy.py::check`・`lib/gatepolicy.py::UNATTENDED`
  - 状態: 形を変えて在る（`--input unattended=true`。語が 1 でなく true）
  - 旧棚卸し: L-G12

- S114 無人の run は起動の承認ノードを越え、人が決める承認ノードに着いたら開かずに止めて報告へ進む（狭める・方針とぶつかる修正は通さない）
  - 元: SKILL.md:94
  - 印: `policy-gate`
  - 今: `workflows/line/scripts/start.py::start`（ask: not unattended）・`workflows/line/scripts/ask_before_fix.py::ask`・`lib/gatepolicy.py::unattended`・`lib/gatemarks.py::pushed_answer`
  - 状態: 形を変えて在る（承認ノードに載る項目の全部が通す推しを持てば、止まらずに推しで進む。持ち主の決め `unattended` の 2026-10-15）
  - 旧棚卸し: L-G10・L-G39・L-G40・L-W39

- S115 無人の run は判定の保留の問いだけでは承認ノードを開かず、問いの出どころだけを飛ばして直し、問いを報告の冒頭に並べる
  - 元: SKILL.md:94
  - 印: 無し
  - 今: `workflows/line/scripts/ask_before_fix.py::ask`・`lib/gatemarks.py::answered`
  - 状態: 在る
  - 旧棚卸し: L-G33・L-G38

- S116 無人の値は 1 か空だけを受け、ほか（on など）なら起動が何も作らずに止まる
  - 元: SKILL.md:94
  - 印: `start`
  - 今: `lib/gatepolicy.py::check`
  - 状態: 形を変えて在る（受ける語は空か true。止めるのはメイングラフの start ノードで、Archon の run 自体は作られて報告まで届く）
  - 旧棚卸し: L-G12

- S117 利用の家（既定は clone の実パスの sha256 の頭 8 字で clone ごとに分かれる）に pack を置き、Archon をその家に隔離して起こす
  - 元: SKILL.md:95
  - 印: `WORKS_USE_HOME`
  - 今: `bin/_lib/launcher.py::run_home`・`bin/_lib/launcher.py::HOME_ENV`・`bin/_lib/isolate.py::isolate`
  - 状態: 形を変えて在る（名は `WORKS_FACTORY_HOME`、既定は `${XDG_STATE_HOME:-~/.local/state}/works-factory/targets/<対象の実パスの sha256 の頭 8 字>`。pack は家に置かず `--workflow-source` で読ませる）
  - 旧棚卸し: 無し

- S118 殻は対象の作業ツリーに何も書かない
  - 元: SKILL.md:95
  - 印: 無し
  - 今: `bin/_lib/apply.py`（当てるのは人が bin/apply で）・`bin/_lib/place.py::workflow_run`（run は Archon の作業ツリーで走る）
  - 状態: 在る
  - 旧棚卸し: 無し

- S119 AI の役の子に `GRAPHLOOPS_ENGINE_CHILD=1` を立て（役の Bash の子にも継ぐ）、対象の重い一式が AI からの起動を拒めるようにし、メイングラフの最後のテストには立てない
  - 元: SKILL.md:96
  - 印: `GRAPHLOOPS_ENGINE_CHILD`
  - 今: `workflows/.shared/fence.py::ENGINE_CHILD_ENV`（包みが本物の claude を起こす前に立てる。script ノードの最後のテストは包みを通らないので立たない）・README.md「使い方」
  - 状態: 在る
  - 処置: 戻した: `workflows/.shared/fence.py::ENGINE_CHILD_ENV`
  - 旧棚卸し: 無し

- S120 Archon が対象の `.git` に run の worktree と枝を足し、worktree は利用の家の下に置く
  - 元: SKILL.md:97
  - 印: 無し
  - 今: 止めた Archon の worktree の提供者（`packages/isolation/src/providers/worktree.ts`。作業ツリーは ARCHON_HOME の下）・`bin/_lib/isolate.py::DIRS`（ARCHON_HOME を家の下へ）
  - 状態: 在る
  - 旧棚卸し: 無し

- S121 対象の枝を早送りするかは Archon の版次第
  - 元: SKILL.md:97
  - 印: 無し
  - 今: 止めた Archon の `syncWorkspaceBeforeCreate`（`packages/isolation/src/providers/worktree.ts`）・止めた Archon の `syncWorkspace`（`packages/git/src/repo.ts`。取り出した枝が土台の枝で遅れていれば `merge --ff-only`）
  - 状態: 在る
  - 旧棚卸し: 無し

- S122 最初に起動の承認ノードで止まって戻り、run id・状態・run の worktree・次に打つ行（進める・待つ・取り消す・答える・止める・続ける）・報告の置き場を出す
  - 元: SKILL.md:98
  - 印: `launch`
  - 今: `workflows/line/works-factory-line.yaml::gate-start`・`workflows/line/scripts/start.py::gate_text`・`bin/_lib/launcher.py::answer_head`
  - 状態: 形を変えて在る（承認ノードの文は入口・段・機能・最後の承認ノードと、そのまま打てる continue・stop の行。worktree・待つ・取り消す行・報告の置き場は無い）
  - 処置: 要らない: Archon の `workflow get`・`workflow status` が持つ（README.md「使い方」の 4）
  - 旧棚卸し: L-E47・L-E48・L-E50

- S123 2 以上の整数で周の数を名指して周をつなぎ、打たなければ 1 周で鎖の控えを作らない
  - 元: SKILL.md:99
  - 印: `--rounds`
  - 今: `workflows/chain/works-factory-chain.yaml`・`lib/chain.py::limits`・`workflows/chain/scripts/chain_start.py::start`
  - 状態: 形を変えて在る（別のグラフ `works-factory-chain` を `--input rounds=<1〜5>` で起こす。上限 5）
  - 旧棚卸し: L-D55

- S124 周をつなぐのは依頼者が何周か回してと頼んだ時だけにする（AI の答え方の決まり）
  - 元: SKILL.md:99
  - 印: 無し
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: スキルの答え方で、スキルがまだ無い（持ち主の決め `coexist-before-switch`）。グラフを AI が自分の判断で起こさない決め `no-self-launch` も在る
  - 旧棚卸し: 無し

- S125 起動の終わりに出る待つ命令を打つたびに、終わった周を見て次の周を切り離して起こす
  - 元: SKILL.md:99
  - 印: `start`・`wait`
  - 今: `workflows/chain/works-factory-chain.yaml`（Archon の workflow: ノードが周の子の run を起こして待つ）・`workflows/chain/scripts/decide.py`
  - 状態: 形を変えて在る（打つ命令は要らず、親の run が続ける。周の中の承認ノードは子の run の id で答える）
  - 旧棚卸し: L-D55・L-D58

- S126 次の周は前の周の結果（差分を当てた木）から切り、差分の審査の根は 1 周目の始めの版、依頼は前の周の残りの所見と前の失敗に 1 周目の答えを足した物にする
  - 元: SKILL.md:99
  - 印: 無し
  - 今: `lib/chain.py::next_request`・`workflows/chain/scripts/round_commit.py::commit`（前提の検算の constraints も運ぶ）
  - 状態: 在る
  - 旧棚卸し: L-D56

- S127 周の鎖と組む費用の上限を持ち、累計に最大の周の費用を足して上限を越えうるなら次の周を起こさない
  - 元: SKILL.md:99
  - 印: `--budget-usd`・`--rounds`
  - 今: `lib/chain.py::decide`・`lib/chain.py::limits`
  - 状態: 形を変えて在る（`--input budget_usd=<USD>`。費用が読めない周が在る時も止める）
  - 旧棚卸し: L-D55

- S128 周の鎖は設計だけの run と組めず、AI の前で拒む
  - 元: SKILL.md:99
  - 印: `WORKS_DESIGN_ONLY`
  - 今: `workflows/chain/scripts/chain_start.py::DESIGN_ONLY_REFUSED`・`workflows/chain/scripts/chain_start.py::start`
  - 状態: 在る
  - 処置: 戻した: `workflows/chain/scripts/chain_start.py::DESIGN_ONLY_REFUSED`
  - 旧棚卸し: L-E26

- S128b 周の鎖は固定材料の run と組めない
  - 元: SKILL.md:99
  - 印: `WORKS_USE_FIX_FIXTURE`
  - 今: `workflows/chain/scripts/chain_start.py::FIX_FIXTURE_REFUSED`・`workflows/chain/scripts/chain_start.py::start`・`workflows/chain/works-factory-chain.yaml::chain-start`
  - 状態: 形を変えて在る（殻でなく鎖のグラフの chain-start ノードが AI の前に拒む）
  - 旧棚卸し: L-E26

- S129 鎖が止まる条件として、指定の周の数・結末が閉じた・止まった・人の判断が要る・進みが無い（木が周の頭と同じ・残りが前の周と同じ）・費用の上限を持つ
  - 元: SKILL.md:99
  - 印: 無し
  - 今: `lib/chain.py::STOPS`・`lib/chain.py::decide`
  - 状態: 在る
  - 旧棚卸し: L-D55

- S130 人の判断が要る周で止めた鎖は保留して続ける口が無く、報告 `chain.md` の下書きを依頼者が見直して新しい鎖を起こす
  - 元: SKILL.md:99
  - 印: `show`・`start`・`--rounds`
  - 今: `lib/chain.py::render`・`lib/chain.py::held_rows`・`lib/chain.py::REPORT_HEAD`
  - 状態: 形を変えて在る（chain.md は親の run の置き場に在り、状態を見る命令は無い。下書きの在りかは chain.md が名指す）
  - 旧棚卸し: L-D56・L-D57

- S131 承認ノードの文に全文のファイルのパスが載り、そのファイルを読んで答える
  - 元: SKILL.md:103
  - 印: `SKILL.md:101`
  - 今: Archon の `workflow get`（承認ノードの message を全文出す）・`workflows/line/scripts/ask_final.py::FINAL_GATE_FILE`（最後の承認ノードだけ run の置き場の gates/final-gate.md に控える）
  - 状態: 形を変えて在る（全文は Archon の承認ノードの message そのもので、ファイルのパスを名指す形でない。修正前の承認ノードの全文のファイルは無い）
  - 処置: 要らない: 全文は Archon の `workflow get` がいつでも出す（on-archon-only）
  - 旧棚卸し: L-G01・L-G51

- S132 打つ行は殻が出した物をそのまま使い、`show` でいつでも出し直せる
  - 元: SKILL.md:103
  - 印: `show`
  - 今: Archon の `workflow get`（承認ノードの決めごとに `archon workflow respond` の行を出す）・`lib/answer.py::line`（承認ノードの文の答えの行）
  - 状態: 形を変えて在る（出し直しは Archon の get。get が出す行は素の `archon` の形で、殻を通す頭は承認ノードの文の中だけ）
  - 処置: 要らない: Archon が出す（one-launcher）
  - 旧棚卸し: L-G08

- S133 承認ノードの全文に載る答えの行は、殻の答えの行（家と対象を名指して殻を通す respond）で書いてある
  - 元: SKILL.md:103
  - 印: `answer`
  - 今: `bin/_lib/launcher.py::answer_head`・`lib/answer.py::head`・`lib/answer.py::HOLE`
  - 状態: 在る
  - 旧棚卸し: L-E50・L-G08

- S134 人が決める承認ノード（修正前・最後）は、回している Claude が自分で通さず必ず依頼者に聞く
  - 元: SKILL.md:105
  - 印: 無し
  - 今: `lib/gatemarks.py::gate_text`・`workflows/line/scripts/ask_final.py::final_text`（答え方の見出し「人が決める承認ノード。依頼者に聞いて、その言葉で答える」）
  - 状態: 形を変えて在る（会話の Claude への決まりでなく、承認ノードの文の 1 句）
  - 旧棚卸し: 無し

- S135 依頼者の言葉をそのまま一言にして答え、答えた者の名を末尾に付けて利用の家の answers.jsonl に残す（全文の答えの行の答えた者の欄も埋める）
  - 元: SKILL.md:105
  - 印: `answer`
  - 今: `lib/answer.py::taken`（一言は字のまま run の置き場の gates/<承認ノード>.json に残る）。答えた者を付ける所と answers.jsonl は無し
  - 状態: 形を変えて在る（一言は残るが、誰が答えたかの記録が無い）
  - 処置: 要らない: 持ち主の決め `answerer-unnamed`（答えた者の名は残さない。一言は Archon の run の記録が持つ）
  - 旧棚卸し: L-E50・L-G04・L-G08

- S136 答えた者が無いか空白だけなら殻が答えを拒む
  - 元: SKILL.md:105
  - 印: `answer`
  - 今: 無し（Archon の `workflow respond` は一言の中身を見ない）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `answerer-unnamed`（答えた者の名は残さない。一言は Archon の run の記録が持つ）
  - 旧棚卸し: L-E50

- S137 起動の承認ノード `launch` は「進める」の行で始まる（止めるなら stop）
  - 元: SKILL.md:111
  - 印: `launch`・`approve`
  - 今: `workflows/line/works-factory-line.yaml::gate-start`・`workflows/line/scripts/start.py::gate_text`・Archon の `workflow approve`／`workflow respond`
  - 状態: 在る
  - 旧棚卸し: L-E47・L-E48・L-E51・L-G01

- S138 修正前の承認ノードは要る時だけ開く: 修正案の能力の狭め・事前審査の後退や方針の穴・方針の文書の変化・判定の台帳の人に聞く問い（held・fork・escalate）
  - 元: SKILL.md:112
  - 印: `policy-gate`
  - 今: `workflows/line/scripts/ask_before_fix.py::ask`・`workflows/line/works-factory-line.yaml::gate-before-fix`・`lib/gatemarks.py::ASK_KINDS`・`lib/gatemarks.py::KIND_WORDS`
  - 状態: 在る
  - 旧棚卸し: L-G17・L-G21・L-G22

- S139 修正前の承認ノードの全文は run の置き場の `r1/gate.md`
  - 元: SKILL.md:112
  - 印: `policy-gate`
  - 今: Archon の `workflow get`（承認ノードの message）・`lib/gatemarks.py::gate_text`。答えは gates/gate-before-fix.json（`workflows/line/scripts/ask_before_fix.py::RECORD`）
  - 状態: 形を変えて在る（全文のファイルは無く、Archon の承認ノードの message で読む）
  - 処置: 要らない: Archon が全文を持つ（on-archon-only）
  - 旧棚卸し: L-G51

- S140 問いの行に選択肢と判定の役の推しが載り、`continue` の一言に問いごとの選択肢を書く。触れなければ修正役は推しで直し、出どころは直す義務に戻る
  - 元: SKILL.md:113
  - 印: 無し
  - 今: `lib/gatemarks.py::ASK_GATE_HEAD`・`lib/gatemarks.py::push_of`・`lib/gatemarks.py::gate_items`
  - 状態: 在る
  - 旧棚卸し: L-G22・L-G24・L-G32

- S141 一言の `保留: <問いの key>` で問いを保留のまま続け、その出どころはこの run で直さず報告の冒頭に並ぶ
  - 元: SKILL.md:113
  - 印: 無し
  - 今: `lib/gatemarks.py::HOLD`・`lib/gatemarks.py::held_questions`・`lib/runreport.py::ledger_state`
  - 状態: 在る
  - 旧棚卸し: L-G30・L-G31・L-G33

- S142 決め手が揃い、答えが割れず、柵（外への書き込み・取り消せない操作・方針の文書の変更・守りを広げる・web の新しい疑い）に当たらない狭めと穴の行は、承認ノードに出さずに通す
  - 元: SKILL.md:114
  - 印: 無し
  - 今: `lib/gatemarks.py::FENCES`・`lib/gatemarks.py::PASSES_FILE`（gate-passes.json）
  - 状態: 在る
  - 旧棚卸し: L-G18

- S143 聞かずに通した行は出どころつきで報告の冒頭にいつも並び、最後の承認ノードが開けばその文にも並ぶ（通した行だけでは最後の承認ノードは開かない）
  - 元: SKILL.md:114
  - 印: `protected_only`・`when_needed`
  - 今: `workflows/line/scripts/ask_final.py::final_text`（「直す前の承認ノードで通した項目」）・`lib/runreport.py::_gate_passes`
  - 状態: 在る
  - 旧棚卸し: L-G19・R34・E66

- S144 最後の承認ノードを必ず見る道 `WORKS_USE_FINAL_GATE=always`（開き方は protected_only・when_needed・always）
  - 元: SKILL.md:114・118
  - 印: `WORKS_USE_FINAL_GATE`・`protected_only`・`when_needed`・`always`
  - 今: `lib/gatepolicy.py::check`・`lib/gatepolicy.py::FINAL_GATES`（メイングラフの入力 final_gate を `--input final_gate=<語>` で渡す）
  - 状態: 形を変えて在る（環境変数でなく `--input final_gate=<語>`。既定は殻の protected_only でなく、メイングラフの always）
  - 処置: 要らない: `--input final_gate=protected_only` で同じ事ができる。今の works でもメイングラフの既定は always で（前の棚卸し L-E30）、既定を変えるのは止まる所を減らす向きなので持ち主の決め無しには変えない
  - 旧棚卸し: L-E30・L-G11・L-G14

- S145 修正前の承認ノードの `continue` の一言は修正役にファイルで届く。直さない単位を名指しても直す義務の数からは外れない（外す口は承認ノードに無い）
  - 元: SKILL.md:115
  - 印: `answer`
  - 今: `workflows/line/works-factory-line.yaml::fix`（answers に修正前の答えを渡す）・`workflows/line/scripts/before_fix_answer.py::take`
  - 状態: 在る
  - 旧棚卸し: L-G32・L-G47

- S146 修正前の承認ノードで `stop` と答えても報告は出る
  - 元: SKILL.md:116
  - 印: `answer`
  - 今: `lib/answer.py::taken`・`workflows/line/works-factory-line.yaml::report`（trigger_rule: all_done）
  - 状態: 在る
  - 旧棚卸し: L-G06・L-G07

- S147 保留の問いには、次の run の依頼の `answers` でも答えられる（報告の冒頭の答え方の行）。手元で測ったら `command` と `output` を添える
  - 元: SKILL.md:117
  - 印: `answers`・`command`・`output`
  - 今: `lib/gatemarks.py::ANSWER_HOW`・`lib/gatemarks.py::ANSWER_KEY_HEAD`・`lib/gatemarks.py::HAND_CHECKED`
  - 状態: 在る
  - 旧棚卸し: L-G34・L-G35・L-G36・R26

- S148 問いの「測り方」の命令は打つ前に読み、読み取りだけの測りの時だけ打つ
  - 元: SKILL.md:117
  - 印: 無し
  - 今: `lib/gatemarks.py::ANSWER_HOW`（答え方の行の注意の 1 句）・`workflows/judge/commands/diagnose.md`（判定の役に、測り方は読み取りだけの命令に限れと書かせる）
  - 状態: 在る
  - 処置: 戻した: `lib/gatemarks.py::ANSWER_HOW`
  - 旧棚卸し: 無し

- S149 最後の承認ノードは既定の protected_only では守りのファイルが変わった時だけ開く。守りのパスの当たりは開き方に関わらず開く
  - 元: SKILL.md:118
  - 印: `final-gate`・`protected_only`
  - 今: `workflows/line/scripts/ask_final.py::ask`・`lib/gatepolicy.py::opens`（既定の語は S144）
  - 状態: 在る
  - 旧棚卸し: L-G49・M26

- S150 when_needed で開く理由: テストが緑でない・独立の目の阻害・問いや異議が残った・修正役が人に回した物・守りのファイルの変更
  - 元: SKILL.md:118
  - 印: `when_needed`
  - 今: `workflows/line/scripts/ask_final.py::final_needs`・`workflows/line/scripts/ask_final.py::HANDOFF_REASON`
  - 状態: 在る
  - 旧棚卸し: L-G48

- S151 修正役が人に回した物（壊すと分かって通した理由）は報告の冒頭 1 にいつも並ぶ
  - 元: SKILL.md:118
  - 印: 無し
  - 今: `lib/runreport.py::_decisions`・`lib/fixboard.py::HANDOFF_HEAD`
  - 状態: 在る
  - 旧棚卸し: R23

- S152 最後の承認ノードの全文 `r1/final-gate.md`（テストの緑赤・ログ・差分の置き場・残った異議・目の判定）
  - 元: SKILL.md:118
  - 印: `final-gate`
  - 今: `workflows/line/scripts/ask_final.py::final_text`・`workflows/line/scripts/ask_final.py::keep`（gates/final-gate.md）
  - 状態: 在る
  - 旧棚卸し: L-G51

- S153 最後の承認ノードは `continue` でも `stop` でも報告へ進む
  - 元: SKILL.md:118
  - 印: 無し
  - 今: `workflows/line/works-factory-line.yaml::gate-final`・`workflows/line/works-factory-line.yaml::report`
  - 状態: 在る
  - 旧棚卸し: L-G06

- S154 最後の承認ノードで `stop` と答えた run の差分は apply が当てずに止まる
  - 元: SKILL.md:118
  - 印: `apply`
  - 今: `bin/_lib/apply.py::choose`
  - 状態: 在る
  - 旧棚卸し: M17・M43

- S155 独立の目 R4 の人への問い（消えた能力・方針とのぶつかり）が承認ノードの全文に載り、`continue` は問いに答えず、問いは報告の冒頭と次の依頼の下書きに載り、結末は needs_human
  - 元: SKILL.md:119
  - 印: `needs_human`
  - 今: `lib/eyeverdict.py::r4_gate_items`・`workflows/line/scripts/ask_final.py::question_lines`・`lib/runreport.py::_decisions`・`lib/outcome.py::_waits`（目の問いを人待ちに数える）・`lib/runreport.py::answer_drafts`（人の居る run でも目の問いを下書きに足す）
  - 状態: 在る
  - 処置: 戻した: `lib/outcome.py::_waits`・`lib/runreport.py::answer_drafts`
  - 旧棚卸し: E62・R5・R27

- S156 殻の approve・answer・承認ノードで待つ run の stop は残りの処理を切り離して回し、すぐ戻る（出力は利用の家の logs の下のログ。終了コードは起こせたかだけ）
  - 元: SKILL.md:121
  - 印: `approve`・`answer`・`stop`
  - 今: Archon の `workflow respond`・`workflow approve`・`workflow reject`・`workflow resume` の `--detach`
  - 状態: 形を変えて在る（切り離しは Archon の旗で利用者が付ける。ログの置き場も Archon の物）
  - 処置: 要らない: Archon が持つ（on-archon-only・one-launcher）
  - 旧棚卸し: 無し

- S157 `wait` で状態を 1 行と終了コードで返す（0 承認ノードで待つ・3 まだ走る・5 終わった・1 落ちた・6 鎖が次の周を起こした）
  - 元: SKILL.md:121・124
  - 印: `wait`・`exit 0`・`exit 3`・`exit 5`・`exit 1`・`exit 6`
  - 今: Archon の `workflow wait`（0 は注意が要る状態（承認ノード・終わり・持ち主が消えた）、3 は期限、1 は待ちの失敗か見つからない）
  - 状態: 形を変えて在る（承認ノードで待つ・終わったは同じ 0 で、1 行の文で分かる。鎖の子の承認ノードは子の run を名指す）
  - 処置: 要らない: Archon の wait が持つ（on-archon-only）
  - 旧棚卸し: 無し

- S158 `wait` の待ちの時間（既定 540 秒・`WORKS_USE_WAIT_SECONDS`）
  - 元: SKILL.md:121
  - 印: `wait`・`WORKS_USE_WAIT_SECONDS`
  - 今: Archon の `workflow wait` の `--timeout`（既定は期限なし）
  - 状態: 形を変えて在る（環境変数でなく旗。既定の期限は無い）
  - 処置: 要らない: 期限を足さない決まり（no-timeouts）。期限が要れば Archon の旗で足りる
  - 旧棚卸し: 無し

- S159 起動が Archon の前で落ちた時は 1 と子の出力の置き場を出し、同じ行を打ち直すと 1 度だけ起こし直す。それも落ちれば鎖を止める（`launch_failed`）
  - 元: SKILL.md:121
  - 印: `exit 1`
  - 今: `bin/_lib/launcher.py::Stop`（殻は Archon を前で起こし、落ちれば 1 行で止まる）・Archon の `workflow resume`（鎖の周は Archon の `workflow:` ノードで、落ちた周は親の resume が起こし直す）
  - 状態: 形を変えて在る（自前の切り離した起動が無いので、起こし直しは Archon の resume）
  - 処置: 要らない: 起動を切り離さないので落ちは前で見える。周の起こし直しは Archon の resume が持つ（on-archon-only）
  - 旧棚卸し: L-D58

- S160 判定が直す物を 1 つも残さなかったら修正を飛ばして報告へ行く（結末 no_fix_needed）
  - 元: SKILL.md:127
  - 印: `no_fix_needed`
  - 今: `workflows/line/works-factory-line.yaml::design-only-out`（when: nothing_owed）・`lib/outcome.py::_no_fix`
  - 状態: 在る
  - 旧棚卸し: R8

- S161 `show <対象>` が start が結んだ一番新しい run（run id を足せばその run）の状態・報告の置き場・差分のファイルを出す。結べなければ候補の run id を出す
  - 元: SKILL.md:132・135
  - 印: `SKILL.md:129`・`show`・`start`
  - 今: Archon の `workflow status`・`workflow runs`・`workflow get`（README.md「使い方」）
  - 状態: 形を変えて在る（結ぶ印は無く、対象の run の一覧から run id を選ぶ。置き場は get が出す）
  - 処置: 要らない: Archon の status・get が持つ（one-launcher）
  - 旧棚卸し: 無し

- S162 `launched_min`（起こしてからの分）を出す
  - 元: SKILL.md:135
  - 印: `show`
  - 今: Archon の `workflow status`・`workflow get` の Age
  - 状態: 在る
  - 旧棚卸し: 無し

- S163 走っている run の今走っているノードを出す
  - 元: SKILL.md:135
  - 印: `show`
  - 今: Archon の `workflow status` の Active node(s)・`workflow get --verbose` の Nodes
  - 状態: 在る
  - 旧棚卸し: 無し

- S164 `alive`・`持ち主:`（持ち主の host・pid が今も居るか。生きている・消えた・確かめられないの 3 つと理由）で、静かなだけの run と持ち主が消えた run を見分ける
  - 元: SKILL.md:135
  - 印: `show`
  - 今: Archon の `workflow wait` の owner_lost（get は持ち主の消えを出さない。docs/polyfills.md の P1 の実測）
  - 状態: 形を変えて在る（見分けは wait の 1 行だけで、status・get には出ない）
  - 処置: 要らない: Archon の wait が持ち主の生死の正（on-archon-only）
  - 旧棚卸し: 無し

- S165 持ち主を確かめられない run（別 host・記録が無い・pid の使い回し）は最後の動きから 30 分以内かで決める
  - 元: SKILL.md:135
  - 印: `show`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 期限を足さない決まり（no-timeouts）。持ち主の判定は Archon の wait が持ち、時間で推す決めを足さない（on-archon-only）
  - 旧棚卸し: 無し

- S166 走っている run のノードごとの費用 `cost_usd` を出す
  - 元: SKILL.md:135
  - 印: `show`
  - 今: Archon の `workflow get` の `--json --events`（ノードの行の費用）・終わった run は `lib/runreport.py::cost_rows`（報告の費用のセクション）
  - 状態: 形を変えて在る（走っている間の要約の行は無く、素の events の JSON で読む）
  - 処置: 要らない: Archon の記録に在る（on-archon-only）
  - 旧棚卸し: R54

- S167 持ち主が消えた run には承認・取り消し・続けるの行を出さず、記録を閉じる `abandon` の行と起こし直す案内（元の依頼・渡した入力・run の基の版）を出す
  - 元: SKILL.md:135
  - 印: `show`
  - 今: Archon の `workflow wait` の owner_lost の文（`archon workflow abandon` を名指す）・Archon の `workflow abandon`・Archon の `workflow run --adopt`
  - 状態: 形を変えて在る（abandon の行は Archon が出す。元の依頼・入力・基の版を並べた起こし直しの案内は無く、`--adopt` が前の run から起こす）
  - 処置: 要らない: Archon の abandon・--adopt が持つ（on-archon-only）
  - 旧棚卸し: 無し

- S168 試験の段が機械全体の試験の枠（同時 4 本）の空きを待つ間「試験の枠: 待っている」、枠の中なら「試験の枠: 中」を出す
  - 元: SKILL.md:135
  - 印: `show`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め no-queue（機械全体の試験の枠を持たない）
  - 旧棚卸し: T64

- S169 報告 `report.md`（冒頭に決めてほしいこと・入口・止めた理由・読んだ証拠・置き場）
  - 元: SKILL.md:137
  - 印: 無し
  - 今: `lib/report.py::HEADINGS`・`lib/report.py::REPORT_FILE`・`lib/runreport.py::build`
  - 状態: 在る
  - 旧棚卸し: R21・R40・R44・R46・R47

- S170 次の依頼の下書き `next-request.json`（findings と prior_failures。印の無い行はそのまま次の run に使える）
  - 元: SKILL.md:137
  - 印: `findings`・`prior_failures`
  - 今: `lib/runreport.py::build`・`lib/runreport.py::next_request`・`lib/carry.py::NEXT_REQUEST_FILE`・`lib/next-request.schema.json`・`workflows/report/works-factory-report.yaml::report`（出力の next_request）
  - 状態: 在る
  - 旧棚卸し: R57・L-D53

- S171 判定が目的の外とした所見（最後の周の分）を `draft: true`・`source` の印つきで findings に載せ、依頼の入口が拒む。報告の「1. 人が決めること」には件数と置き場だけ、1 件ずつは本文のセクション「判定が目的の外とした所見」
  - 元: SKILL.md:137
  - 印: `findings`・`draft`・`source`
  - 今: `lib/outpurpose.py::DRAFT_SOURCE`・`lib/carry.py::DRAFT_KEYS`・`lib/report.py::OUTSIDE_HEADING`
  - 状態: 在る
  - 旧棚卸し: R53

- S172 答えの下書き answers（保留のままの問い・問いの無い測れなかった素材・無人の run が承認ノードで止めた項目。`draft: true`・`source`。推しの無い行は text が空で材料は note）は見直すまで使えない
  - 元: SKILL.md:137
  - 印: `answers`・`draft`・`source`・`text`・`note`
  - 今: `lib/runreport.py::answer_drafts`・`lib/runreport.py::_gate_draft`
  - 状態: 在る
  - 旧棚卸し: R27・L-G41

- S173 下書きの question は答える時に字のまま書く名で、報告の保留の行の尾「答える時の answers の question」と同じ
  - 元: SKILL.md:137
  - 印: `question`
  - 今: `lib/gatemarks.py::ANSWER_KEY_HEAD`
  - 状態: 在る
  - 旧棚卸し: R26

- S174 `prior-failures.json`（最後まで通らなかった受け付けの理由と R2 の作り直しの理由）
  - 元: SKILL.md:137
  - 印: `prior_failures`
  - 今: `lib/runreport.py::prior_failures`・`lib/carry.py::PRIOR_FAILURES_FILE`・`lib/prior-failures.schema.json`
  - 状態: 在る
  - 旧棚卸し: R58

- S175 結末の語 fixed
  - 元: SKILL.md:138
  - 印: `fixed`
  - 今: `lib/outcome.py::decide_outcome`・`lib/report.py::OUTCOME_KINDS`
  - 状態: 在る
  - 旧棚卸し: R1・R11

- S176 結末の語 fixed_needs_check（残りが run の中で測れなかった確かめだけ。冒頭 1 に「人が確かめる物」、次の依頼の下書きにも載り、apply は fixed と同じく当てる）
  - 元: SKILL.md:138
  - 印: `fixed_needs_check`
  - 今: `lib/outcome.py::decide_outcome`・`lib/outcome.py::_material_row`・`lib/green_cert.py::certify`・`lib/report.py::CHECKS_LEFT`・`bin/_lib/apply.py::choose`（封じた差分なら結末を問わず当てる）。一部が回せない base でも certify が awaiting_human を通して鎖を切らず、人が確かめる物の行が素材の訳で回らなかった確かめを名指す（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: R9

- S177 結末の語 no_fix_needed
  - 元: SKILL.md:138
  - 印: `no_fix_needed`
  - 今: `lib/outcome.py::_no_fix`
  - 状態: 在る
  - 旧棚卸し: R8

- S178 結末の語 round_limit（受け付けは通ったが、検証器の阻害・最後のテストの赤・独立の目の block・受け止めた段の落ちが残った）
  - 元: SKILL.md:138
  - 印: `round_limit`
  - 今: `lib/outcome.py::decide_outcome`・`lib/outcome.py::residue`・`lib/outcome.py::absorbed_rows`
  - 状態: 在る
  - 旧棚卸し: R10・R13・R14・R19

- S179 結末の語 stopped_by_human（承認ノードで止めた）
  - 元: SKILL.md:138
  - 印: `stopped_by_human`
  - 今: `lib/outcome.py::_human_stop`
  - 状態: 在る
  - 旧棚卸し: R3

- S180 結末の語 stopped_by_request（止め札）
  - 元: SKILL.md:138
  - 印: `stopped_by_request`
  - 今: `lib/outcome.py::_human_stop`（承認ノードの止めの一言が `request:` で始まる時だけ）
  - 状態: 形を変えて在る（語は残るが、走っている run に置く止め札は無い）
  - 処置: 要らない: 持ち主の決め stop-at-gates（止め札は持ち込まない）
  - 旧棚卸し: R2・L-G55

- S181 結末の語 stopped_by_line（機械が止めた）
  - 元: SKILL.md:138
  - 印: `stopped_by_line`
  - 今: `lib/outcome.py::_line_stop`
  - 状態: 在る
  - 旧棚卸し: R4・R5b

- S182 結末の語 needs_human（人に聞いたまま）
  - 元: SKILL.md:138
  - 印: `needs_human`
  - 今: `lib/outcome.py::_waits`（R4 の問いで needs_human になる所は S155）
  - 状態: 在る
  - 旧棚卸し: R5

- S183 結末の語 record_invalid（記録が検証器を通らない）
  - 元: SKILL.md:138
  - 印: `record_invalid`
  - 今: `lib/outcome.py::record_problems`・`lib/outcome.py::decide_outcome`
  - 状態: 形を変えて在る（run の置き場の検証器は無く、始めの記録とサブグラフの出力が読めない訳で決める）
  - 処置: 要らない: run の置き場の検証器は設計で持たない（docs/design.md のサブグラフの出力の約束。前の棚卸し R6）
  - 旧棚卸し: R6

- S184 結末の語 interrupted（途中で終わった。冒頭 3 に落ちたノード。受け止めると宣言した段の落ちだけでメイングラフの終わりまで届いた run はこれにならない）
  - 元: SKILL.md:138
  - 印: `interrupted`
  - 今: `lib/outcome.py::cut_at`・`lib/outcome.py::absorbed_rows`・`lib/report.py::INTERRUPTED_HEAD`・`lib/report.py::ABSORBED_HEAD`
  - 状態: 在る
  - 旧棚卸し: R7・R44・R45・R82

- S185 差分（run の worktree と周の頭の版の差。手直しと未追跡も入る）を書く。修正は commit されない
  - 元: SKILL.md:139
  - 印: 無し
  - 今: `workflows/merge/works-factory-merge.yaml::merge`（封じた差分を run の置き場に書く）・`lib/seal.py::write_readback`
  - 状態: 形を変えて在る（置き場は利用の家の diffs の下でなく run の置き場。封じる前に止まった run は差分のファイルが無く、`bin/apply` が作業ツリーから組む素の git の行を出す）
  - 処置: 要らない: 封じる前の差分を当てないのは前の棚卸し M46 の決め（#101）。拒む 1 行が素の道を残す
  - 旧棚卸し: M1・M24・M46

- S186 `apply <対象> <run-id>` で差分を当て、手元でテストを回して commit する（当てた後に commit していないと言う）
  - 元: SKILL.md:139
  - 印: `apply`
  - 今: `bin/_lib/apply.py::main`（`bin/apply` に run id と `--cwd <対象>`）
  - 状態: 在る
  - 旧棚卸し: M39・M51

- S187 apply は `git apply --check` で当たるかを先に見る
  - 元: SKILL.md:139
  - 印: `apply`
  - 今: `bin/_lib/apply.py::put`
  - 状態: 在る
  - 旧棚卸し: M47

- S188 対象のファイルを消す差分は消すファイルを並べて止まり、`WORKS_USE_ALLOW_DELETE=1` で打ち直せば当てる
  - 元: SKILL.md:139
  - 印: `apply`・`WORKS_USE_ALLOW_DELETE`
  - 今: `bin/_lib/apply.py::put`（`--allow-delete`）
  - 状態: 形を変えて在る（環境変数でなく旗）
  - 旧棚卸し: M42・M50

- S189 記録が止まりを示す run（最後の承認ノードの stop・止め札・メイングラフの止め）の差分は、止まった結末と一言を 1 行で出して止まり、`WORKS_USE_ALLOW_STOPPED=1` で当てる
  - 元: SKILL.md:139
  - 印: `apply`・`WORKS_USE_ALLOW_STOPPED`
  - 今: `bin/_lib/apply.py::choose`・`bin/_lib/apply.py::stopped_why`（`--allow-stopped`。R2 の作り直しは許しでも当てない）
  - 状態: 形を変えて在る（環境変数でなく旗）
  - 旧棚卸し: M43・M44・M50

- S190 止まりかを記録で確かめられない run（途中で終わった・承認ノードで待つ）は、その 1 行を出して当てる
  - 元: SKILL.md:139
  - 印: `apply`
  - 今: `bin/_lib/apply.py::read_run`（拒んで終了 2）・`bin/_lib/apply.py::unchecked`（素の git apply の行を出す）
  - 状態: 形を変えて在る（当てずに拒み、素の git apply の行を出す）
  - 処置: 要らない: 前の棚卸し M45 の決め（#101。新しい旗は足さず、拒む 1 行に道を書く）
  - 旧棚卸し: M45

- S191 鎖の差分は鎖の id を渡すと、最後の差分 `final.diff`（元の基から止まりと言われていない最後の周まで）を同じ確かめで当てる
  - 元: SKILL.md:139
  - 印: `apply`・`--rounds`
  - 今: `bin/_lib/apply.py::choose`（鎖の親の run の出力 result の apply・sealed）・`workflows/chain/scripts/final_diff.py::final`。渡すのは鎖の親の run の id
  - 状態: 在る
  - 旧棚卸し: M53・L-D57

- S192 `show <対象> <鎖の id>` が周ごとと合計の報告 `chain.md`（周・run・結末・分・費用・残り・ファイルと止めた訳。読めない費用は「読めない」）を出す
  - 元: SKILL.md:139
  - 印: `show`
  - 今: `lib/chain.py::render`・`lib/chain.py::REPORT_HEAD`・Archon の `workflow get`（置き場のファイルの一覧）
  - 状態: 形を変えて在る（表は親の run の置き場の chain.md で、殻が出す口は無い）
  - 処置: 要らない: 置き場は Archon の get が名指す（one-launcher）
  - 旧棚卸し: L-D57・R69

- S193 独立の目 R2 の作り直しが残ったまま止めた鎖は、報告の頭に「閉じていない」と出る
  - 元: SKILL.md:139
  - 印: 無し
  - 今: `bin/_lib/apply.py::choose`（R2 が作り直しと言った差分を当てない）・`lib/chain.py::render`（chain.md には書かない）
  - 状態: 形を変えて在る（頭の一言は無く、取り込みで訳を言って拒む）
  - 処置: 要らない: 採る周の R2 が作り直しなら `bin/_lib/apply.py::choose` が訳を言って当てないので、取り込みの事故は起きない。`lib/chain.py` の docstring の「元から変えた所」に記録がある
  - 旧棚卸し: M19

- S194 取り込み終えたら `clean <対象> <鎖の id>` が鎖の控えと周の結果を守る参照を消す
  - 元: SKILL.md:139
  - 印: `clean`
  - 今: Archon の `complete`・Archon の `isolation cleanup`（周の結果は親の run の作業ツリーの枝の commit で、自前の参照は無い）
  - 状態: 形を変えて在る（自前の控えと参照が無く、片付けは Archon の作業ツリーの片付け）
  - 処置: 要らない: Archon が作業ツリーと枝を片付ける（on-archon-only・one-launcher）
  - 旧棚卸し: 無し

- S195 run の worktree・枝・控えと、修正の段が切った単位の worktree・守りの参照（`refs/works/units/`）は自動で片付く
  - 元: SKILL.md:140
  - 印: 無し
  - 今: `workflows/line/scripts/sweep_children.py::sweep`・`bin/_lib/childsweep.py::sweep`（fix の組の子の run の作業ツリーと枝を `complete --force` で消す）
  - 状態: 形を変えて在る（自動で消すのは completed の組の子だけ。メイングラフの run の作業ツリーと枝は残り、Archon の `complete`・`isolation cleanup` で消す）
  - 処置: 要らない: Archon が作業ツリーの片付けを持ち（on-archon-only）、差分は置き場に残るので片付けの後も `bin/apply` で当たる（前の棚卸し M41）
  - 旧棚卸し: M41

- S196 completed・cancelled の run は wait・show が差分を書いた後に消し、failed の run は次の start が差分を書いてから消して abandon で閉じる
  - 元: SKILL.md:140
  - 印: `wait`・`show`・`start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: Archon の `isolation cleanup`・`workflow cleanup` が持つ（on-archon-only）。差分は封じた時に置き場に在るので、消す前に書く手順が要らない
  - 旧棚卸し: 無し

- S197 差分を書けなかった run と、走っている・承認ノードで待つ run は残す
  - 元: SKILL.md:140
  - 印: 無し
  - 今: `bin/_lib/childsweep.py::select`（completed でない子と、fan_out・join が済んでいない子を残す）
  - 状態: 形を変えて在る（組の子の run の範囲だけ）
  - 処置: 要らない: S195 と同じ（Archon が作業ツリーの片付けを持つ。on-archon-only）
  - 旧棚卸し: 無し

- S198 start が片付けた run の id と状態を start の出力と報告の冒頭 2 に出す
  - 元: SKILL.md:140
  - 印: `start`
  - 今: `workflows/line/scripts/result.py::result`（出力の children に sweep-children の cleaned・left）
  - 状態: 形を変えて在る（start が前の run を片付けないので、出るのはこの run の組の子の片付けだけ。報告の冒頭 2 には無い）
  - 処置: 要らない: 前の run の片付けは Archon の cleanup が持つ（on-archon-only）
  - 旧棚卸し: 無し

- S199 手で消す `clean <対象> <run-id>`（走っている・承認ノードで待つ run は拒む。落ちた run は abandon で閉じる。worktree が無い run でも閉じる）
  - 元: SKILL.md:140
  - 印: `clean`
  - 今: Archon の `complete`・Archon の `workflow abandon`
  - 状態: 形を変えて在る（Archon の 2 つの命令を打つ）
  - 処置: 要らない: Archon が持つ（one-launcher・on-archon-only）
  - 旧棚卸し: 無し

- S200 report_file: 報告のノードまで届いた run では AI が書き初見の読み手が確かめた `report-ai.md`（末尾に機械の報告が字のまま）、そうでなければ機械の `report.md`。機械の報告はいつも machine_report_file
  - 元: SKILL.md:141
  - 印: 無し
  - 今: `workflows/report/works-factory-report.yaml::report`（出力の report＝機械の報告・report_ai＝AI の報告か null）・`lib/runreport.py::AI_REPORT_FILE`
  - 状態: 形を変えて在る（1 つを選んだ report_file の欄は無く、2 つの欄を並べる。AI の報告は record_invalid でない run なら回す）
  - 旧棚卸し: R60・R63・R66・R68

- S201 依頼者に聞く・伝える時は、初見で決められるように書き、決めてほしい事を最初に置く
  - 元: SKILL.md:143・145
  - 印: 無し
  - 今: `lib/gatemarks.py::head3`（承認ノードの文と報告の冒頭 3 行）
  - 状態: 形を変えて在る（機械が書く承認ノードの文と報告の頭の決まりとして在り、会話の Claude への決まりは無い）
  - 処置: 要らない: スキルの答え方の決まりは、切り替えの段まで claude-plugins の `/works` に残る（coexist-before-switch）
  - 旧棚卸し: R21・L-G24

- S202 決めてほしい事は 1 件ずつ、何を決めるか・背景・答えごとに起きること・推しと理由・答えの後に何をするか、の順に書く
  - 元: SKILL.md:146-151
  - 印: 無し
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: スキルの答え方の決まりは、切り替えの段まで claude-plugins の `/works` に残る（coexist-before-switch）
  - 旧棚卸し: 無し

- S203 結果だけを伝える時は、起きたこと・変わったこと・求めること（無ければ次に大事な事実）を先に言い、report.md の決めてほしいことを上の並びで言い直す
  - 元: SKILL.md:152
  - 印: 無し
  - 今: `lib/gatemarks.py::head3`（other＝次に大事な事実）
  - 状態: 形を変えて在る（報告の冒頭 3 行の決まりとして在る。言い直しの決まりは無い）
  - 処置: 要らない: スキルの答え方の決まりは、切り替えの段まで claude-plugins の `/works` に残る（coexist-before-switch）
  - 旧棚卸し: R21

- S204 run の中の語（R1〜R4・結末の名・block・ノードの名・run id）を使わず、使うなら中身を先に書く
  - 元: SKILL.md:153
  - 印: 無し
  - 今: `lib/gatemarks.py::named`・`lib/gatemarks.py::PLAIN`・`lib/gatemarks.py::EYES`（承認ノードの文と報告の主語を平易な名にし、内部の名は括弧に回す）
  - 状態: 形を変えて在る（機械の文の決まりとして在る）
  - 旧棚卸し: L-G25

- S205 費用・直しの中身・置き場は後ろに畳む
  - 元: SKILL.md:154
  - 印: 無し
  - 今: `lib/report.py::HEADINGS`（置き場は冒頭 5「見る所」、費用は本文のセクション）
  - 状態: 形を変えて在る（報告のセクションの並びとして在る）
  - 処置: 要らない: スキルの答え方の決まりは、切り替えの段まで claude-plugins の `/works` に残る（coexist-before-switch）
  - 旧棚卸し: R47・R54

- S206 止め方は 1 つ: `stop <対象> <run-id> "<理由>"`（承認ノードで待つ run には respond stop、走っている run には止め札を置く）
  - 元: SKILL.md:158-164
  - 印: `SKILL.md:156`・`stop`
  - 今: Archon の `workflow respond`（stop と一言）・Archon の `workflow reject`（README.md「使い方」）
  - 状態: 形を変えて在る（承認ノードで待つ run だけを報告つきで止められる。1 つの口に畳んだ別名は無い）
  - 処置: 要らない: 持ち主の決め one-launcher（別名を作らない）と stop-at-gates
  - 旧棚卸し: L-G02・L-G06

- S207 走っている run に止め札（`stop.sh <run-id> "<理由>"`）を置くと、走っている AI のノードは最後まで走り、次の境のノードで止まって報告が出る
  - 元: SKILL.md:164
  - 印: `stop.sh`
  - 今: 無し（承認ノードの間は Archon の `workflow cancel` で、報告は出ない）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め stop-at-gates（承認ノードの間の報告つきの止めを狭めとして認めた）
  - 旧棚卸し: L-G55・R2

- S208 すぐ止めたい時は「取り消す」の行（`cancel <run-id>`）で、報告のノードまで届かない
  - 元: SKILL.md:165
  - 印: 無し
  - 今: Archon の `workflow cancel`（README.md「使い方」）
  - 状態: 在る
  - 旧棚卸し: L-G55

- S209 持ち主が消えた run には取り消すの行を出さず（cancel は答えない持ち主の run を止められない）、abandon で記録を閉じる。cancelled になれば show・wait が差分を書いて片付ける
  - 元: SKILL.md:165
  - 印: `show`・`wait`
  - 今: Archon の `workflow cancel`（no_owner_answered で止められないと言う）・Archon の `workflow abandon`・Archon の `workflow wait` の owner_lost の文（docs/polyfills.md の P1）
  - 状態: 形を変えて在る（行の出し分けは Archon の wait の文。abandon は作業ツリーを書きかけごと消し、差分を書いてから片付ける手順は無い）
  - 処置: 要らない: 書きかけの取り出しは埋め P1（`bin/apply`）が持つと決めた（docs/polyfills.md の P1）
  - 旧棚卸し: 無し

- S210 続ける: 「続ける」の行（`resume <run-id>`）で済んだノードの続きから回る。failed か paused の run にだけ出る
  - 元: SKILL.md:166
  - 印: 無し
  - 今: Archon の `workflow resume`（failed・paused 以外は拒む。docs/polyfills.md の P1 の証拠）
  - 状態: 形を変えて在る（行の出し分けは無く、Archon が受けない状態を拒む）
  - 処置: 要らない: Archon が持つ（on-archon-only）
  - 旧棚卸し: 無し

- S211 ノードが落ちた run（サブグラフの中の出し直しが上限 3 回を超えた時も）でも報告のノードは走る
  - 元: SKILL.md:167
  - 印: 無し
  - 今: `workflows/line/works-factory-line.yaml::report`（trigger_rule: all_done）・`workflows/line/works-factory-line.yaml::collect`（always_run）・各サブグラフの loop の max_iterations 3
  - 状態: 在る
  - 旧棚卸し: L-G52・R67

- S212 受け止めると宣言した段の落ちは、メイングラフの終わりまで届けば結末を interrupted にせず、冒頭 3 に受け止めたノードの行、冒頭 1 の残りと次の依頼に「確かめていない（再実行の要あり）」と載る（Archon の状態は失敗のまま残りうる）
  - 元: SKILL.md:167
  - 印: `interrupted`
  - 今: `lib/outcome.py::absorbed_rows`・`lib/report.py::ABSORBED_HEAD`（受け止めた落ちは、落ちた後にほかのノードが始まったかで決める）
  - 状態: 形を変えて在る（`[optional]` の宣言でなく run の記録の並びで決める）
  - 旧棚卸し: R19・R45・R82

- S213 それ以外の落ちは結末 interrupted の report.md と next-request.json が残り、冒頭 3 に落ちたノードとその誤りの文が出る
  - 元: SKILL.md:167
  - 印: `interrupted`
  - 今: `lib/outcome.py::cut_at`・`lib/report.py::INTERRUPTED_HEAD`
  - 状態: 在る
  - 旧棚卸し: R7・R44

- S214 start で落ちた run は run の置き場も報告も無い
  - 元: SKILL.md:167
  - 印: `start`
  - 今: `workflows/line/scripts/start.py::start`（入口の拒みでも ok: false で後ろを飛ばし報告まで届く）・`bin/_lib/launcher.py::Stop`（Archon の前の止めは run を作らない）
  - 状態: 形を変えて在る（start のノードの拒みでも報告が出る。報告が無いのは殻が Archon を起こす前に止めた時だけ）
  - 旧棚卸し: L-E52・L-E53

- S215 取り消し・abandon で止めた run は、`report.sh <run-id>`（`WORKS_DEV_HOME` を前に）で run の置き場から報告を組む（結末 interrupted）
  - 元: SKILL.md:168
  - 印: `report.sh`・`WORKS_DEV_HOME`・`interrupted`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め stop-at-gates（承認ノードの間の止めは報告の出ない cancel と決め、報告つきの止めの狭めを認めた）。差分は `bin/apply` の拒む 1 行が素の git の道を出す
  - 旧棚卸し: L-G55

## use.sh

- U001 本物の AI で run を起こし、最初の承認ノード（起動の承認ノード）で止まって戻る
  - 元: use.sh:4-5・1131-1168
  - 印: `start`
  - 今: README.md「使い方」（2. 始める）・`bin/_lib/launcher.py::launch`・`workflows/line/works-factory-line.yaml::gate-start`・Archon の `workflow run`
  - 状態: 形を変えて在る（殻の別名でなく `bin/works-factory workflow run works-factory-line --cwd <対象> --input request=<依頼>` を打つ）
  - 旧棚卸し: L-E47

- U002 start --base <版> で変更から入る（差分の根を版で名指す。依頼は - で省ける）
  - 元: use.sh:6・121-131・1145-1147
  - 印: `--base`
  - 今: `workflows/line/works-factory-line.yaml`（入力 base）・`lib/entryshape.py::change_base`
  - 状態: 形を変えて在る（`--input base=<版>`。Archon の `--base` は worktree の土台の枝で別物）
  - 旧棚卸し: L-E09・L-E10

- U003 start --pr <番号> で PR から入る（差分に目を回す。依頼は - で省ける）
  - 元: use.sh:6・121-131・1145-1147
  - 印: `--pr`
  - 今: `workflows/line/works-factory-line.yaml`（入力 pr）・`lib/entryshape.py::change_base`・`lib/entryshape.py::github_reads`
  - 状態: 形を変えて在る（`--input pr=<番号>`）
  - 旧棚卸し: L-E11・L-E12・L-E13・L-E14

- U004 --base・--pr・--chain-next に値が無ければ使い方の行で終了コード 2 で終わる
  - 元: use.sh:114-117・122-125
  - 印: `--base`・`--pr`・`--chain-next`
  - 今: Archon の `workflow run --input`（値は `<鍵>=<値>` の文字列。空の値はその入力の既定になる）・`lib/entryshape.py::refuse_empty`
  - 状態: 形を変えて在る（空の値は拒まずに既定の入口になる）
  - 処置: 要らない: 引数は Archon が読み（`one-launcher`）、空の base・pr は名指し無しと同じ入口になる。依頼も差分も無ければ `lib/entryshape.py::refuse_empty` が AI の前で止める
  - 旧棚卸し: 無し

- U005 --base と --pr を両方名指すと拒む（終了コード 2）
  - 元: use.sh:126-129
  - 印: `--base`・`--pr`
  - 今: `lib/entryshape.py::change_base`（run の start ノードが AI の前に拒む）
  - 状態: 形を変えて在る（殻でなく run の start ノードが拒み、報告まで届く）
  - 旧棚卸し: L-E08

- U006 start --spec で、判定の前に仕様の段（書き手・審査・人の承認）を挟み（入力 spec=on）、そう知らせる 1 行を出す
  - 元: use.sh:41-42・133-135・1150-1153
  - 印: `--spec`
  - 今: `workflows/line/works-factory-line.yaml`（入力 spec）・`workflows/line/scripts/start.py::words`
  - 状態: 形を変えて在る（`--input spec=on`）
  - 旧棚卸し: L-E27・L-E28・L-E29

- U007 start --rounds N（2 以上）で周をつなぐ鎖を作る（1 は鎖を作らない 1 周）
  - 元: use.sh:7・96-104・1095-1098・1157-1160
  - 印: `--rounds`
  - 今: `workflows/chain/works-factory-chain.yaml`（入力 rounds）・`workflows/chain/scripts/chain_start.py::start`・README.md「使い方」（周をつなぐ）
  - 状態: 形を変えて在る（別のグラフ works-factory-chain を名指して起こす。rounds=1 も親の run になる）
  - 旧棚卸し: L-D55

- U008 --rounds の値が 1 以上の整数でなければ拒む（終了コード 2）
  - 元: use.sh:97-100
  - 印: `--rounds`
  - 今: `lib/chain.py::limits`（鎖のグラフの chain-start ノードが AI の前に拒む）
  - 状態: 形を変えて在る（上限 5 を足した。範囲の外は鎖の run の中で拒む）
  - 処置: 要らない: docs/owner-decisions.md「2026-10-11 の決めから導いた事」の周の鎖の置き場（#380）が、上限 5 と、越える時は最後の周の次の依頼で鎖を起こし直すと決めた
  - 旧棚卸し: L-D55

- U009 start --budget-usd X で鎖の費用の上限を付ける
  - 元: use.sh:8・105-111
  - 印: `--budget-usd`
  - 今: `workflows/chain/works-factory-chain.yaml`（入力 budget_usd）・`lib/chain.py::decide`
  - 状態: 形を変えて在る（`--input budget_usd=<USD>`）
  - 旧棚卸し: L-D55

- U010 --budget-usd が正の数でなければ拒む（終了コード 2）
  - 元: use.sh:106-109
  - 印: `--budget-usd`
  - 今: `lib/chain.py::limits`
  - 状態: 在る
  - 旧棚卸し: L-D55

- U011 --budget-usd を --rounds 2 以上なしで渡すと拒む
  - 元: use.sh:144-147
  - 印: `--budget-usd`・`--rounds`
  - 今: 無し（`lib/chain.py::limits` は rounds=1 でも budget_usd を受ける）
  - 状態: 無い
  - 処置: 要らない: 上限は周の間の決め（`lib/chain.py::decide`。docs/owner-decisions.md「2026-10-11 の決めから導いた事」の周の鎖の置き場 #380 が lib/chain.py に置いた）にだけ使い、周が 1 つなら次の周を起こさないので、受けても何も流れない
  - 旧棚卸し: 無し

- U012 鎖の次の周を 1 周目と同じ入力・起動の環境（WORKS_USE_* と WORKS_DESIGN_ONLY）で起こす（内部の旗 --chain-next。wait を打った殻の値を外す）
  - 元: use.sh:113-120・164-178・375-394・1063-1065・1099-1103
  - 印: `--chain-next`・`WORKS_DESIGN_ONLY`
  - 今: `workflows/chain/works-factory-chain.yaml`（周ごとの `workflow:` ノードの `with:` が test_cmd・tdd_suite・final_gate など同じ入力を子へ渡す）
  - 状態: 形を変えて在る（親のグラフが入力を運び、殻の環境は運ばない）
  - 旧棚卸し: L-D56

- U013 --chain-next に家（WORKS_USE_HOME）が無ければ拒む
  - 元: use.sh:169
  - 印: `--chain-next`・`WORKS_USE_HOME`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 内部の旗が無く、次の周は Archon の `workflow:` ノードが起こす（`on-archon-only`）
  - 旧棚卸し: 無し

- U014 --chain-next で鎖の控えから次の周を読めなければ拒む
  - 元: use.sh:172
  - 印: `--chain-next`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 鎖の控えのファイルが無く、周の決めは `workflows/chain/scripts/decide.py::decide` の出力で Archon の `workflow:` ノードへ運ぶ（`on-archon-only`）
  - 旧棚卸し: L-D58

- U015 旗は位置引数より前だけ読み、最初の -- で旗を終える
  - 元: use.sh:40・137-141
  - 印: `--`
  - 今: `bin/_lib/launcher.py::before_double_dash`・`bin/_lib/launcher.py::require_command_first`・Archon の `workflow run`（旗は Archon の parseArgs が strict で読む）
  - 状態: 形を変えて在る（旗は命令の後ろに置き、Archon が読む）
  - 旧棚卸し: 無し

- U016 start で対象を省けば今いるフォルダの git の根を対象にする
  - 元: use.sh:39・229-234
  - 印: `start`
  - 今: `bin/_lib/launcher.py::target_root`（`--cwd` が無ければ打った場所）
  - 状態: 在る
  - 旧棚卸し: 無し

- U017 依頼の位置引数 - は「依頼を省く」の意味（--base か --pr が在る時だけ）
  - 元: use.sh:42-43・317-320・1056-1061
  - 印: `--base`・`--pr`
  - 今: `workflows/line/works-factory-line.yaml`（入力 request。既定は空）
  - 状態: 形を変えて在る（request を渡さなければ省ける）
  - 旧棚卸し: L-E07

- U018 第 3 位置引数で test_cmd を渡す
  - 元: use.sh:4・233・1131
  - 印: 無し
  - 今: `workflows/line/works-factory-line.yaml`（入力 test_cmd）
  - 状態: 形を変えて在る（`--input test_cmd=<コマンド>`）
  - 旧棚卸し: L-E38

- U019 第 4 位置引数で tdd_suite をそのまま渡し（空は TDD のループを飛ばす）、そう知らせる 1 行を出す
  - 元: use.sh:55・1066-1068
  - 印: 無し
  - 今: `workflows/line/works-factory-line.yaml`（入力 tdd_suite）・`lib/tddloop.py::start`・`workflows/line/scripts/start.py::test_notes`（名指した時は言わない）
  - 状態: 形を変えて在る（`--input tdd_suite=<実行器>`。空なら TDD のループを飛ばし、起動の承認ノードの文がそう言う）
  - 旧棚卸し: L-E38・F027

- U020 引数の数が合わなければ使い方の行で終了コード 2 で終わる
  - 元: use.sh:85・150-157
  - 印: 無し
  - 今: `bin/_lib/launcher.py::require_command_first`・`bin/_lib/launcher.py::fresh_run_workflow`・Archon の各命令の使い方の行
  - 状態: 形を変えて在る（終了コードは殻 2・Archon 1）
  - 旧棚卸し: 無し

- U021 WORKS_DESIGN_ONLY=1 で設計だけの run にする（修正前の承認ノードを必ず開けて止める）
  - 元: use.sh:71・1144
  - 印: `WORKS_DESIGN_ONLY`
  - 今: `workflows/line/works-factory-line.yaml`（入力 design_only）・`workflows/line/scripts/start.py::words`
  - 状態: 形を変えて在る（`--input design_only=true`）
  - 旧棚卸し: L-E26・P247

- U022 WORKS_DESIGN_ONLY が空・1 の外なら何かを作る前に拒む
  - 元: use.sh:199-202
  - 印: `WORKS_DESIGN_ONLY`・`use.sh:201`
  - 今: `workflows/line/scripts/start.py::words`（DESIGN_ONLY_WORDS の外を拒む）
  - 状態: 形を変えて在る（run の start ノードが AI の前に拒む。語は true）
  - 旧棚卸し: L-E26

- U023 WORKS_USE_UNATTENDED=1 で無人の run にする（入力 unattended=true）
  - 元: use.sh:69-70・1143
  - 印: `WORKS_USE_UNATTENDED`
  - 今: `workflows/line/works-factory-line.yaml`（入力 unattended）・`lib/gatepolicy.py::check`
  - 状態: 形を変えて在る（`--input unattended=true`）
  - 旧棚卸し: L-E30・L-G12

- U024 WORKS_USE_UNATTENDED が空・1 の外なら拒む
  - 元: use.sh:203-206
  - 印: `WORKS_USE_UNATTENDED`・`use.sh:205`
  - 今: `lib/gatepolicy.py::check`（`workflows/line/scripts/start.py::words` から）
  - 状態: 形を変えて在る（run の start ノードが拒む。語は true）
  - 旧棚卸し: L-G12

- U025 無人の run は起動の承認ノードを自分で越える
  - 元: use.sh:1215-1225
  - 印: `WORKS_USE_UNATTENDED`
  - 今: `workflows/line/scripts/start.py::start`・`workflows/line/works-factory-line.yaml::gate-start`（無人なら開かない）
  - 状態: 形を変えて在る（殻の approve でなく、メイングラフが承認ノードを開かない）
  - 旧棚卸し: L-G10・L-E47

- U026 無人の run は人が決める承認ノードに着いたら止めて報告へ進める
  - 元: use.sh:1226-1233
  - 印: `WORKS_USE_UNATTENDED`
  - 今: `workflows/line/scripts/ask_before_fix.py::ask`・`workflows/line/scripts/ask_replan.py::ask`・`workflows/line/scripts/ask_final.py::ask`（works:needs-human の印で止める）
  - 状態: 形を変えて在る（殻の respond stop でなく、メイングラフが承認ノードを開かずに止める。修正の前と案の直しは、項目の全部が通す推しを持てば推しで進む。持ち主の決め `unattended` の 2026-10-15）
  - 旧棚卸し: L-G39

- U027 無人の run の後に、承認ノードの項目と保留の問いへの答えの下書きが、次の依頼の下書き（next-request.json）の answers に在ると案内する
  - 元: use.sh:1234-1235
  - 印: `WORKS_USE_UNATTENDED`・`answers`・`question`・`draft`・`source`
  - 今: `lib/carry.py::draft`・`lib/carry.py::compose`・`lib/runreport.py::answer_drafts`（報告が次の依頼の下書きに置く）
  - 状態: 形を変えて在る（案内の 1 行は殻に無く、下書きは報告が書く）
  - 旧棚卸し: P242

- U028 WORKS_USE_ALLOW_TESTCMD=1 で、対象の手元を走らせる形の test_cmd でも止めずに起こす
  - 元: use.sh:61・185・1026・1030-1032
  - 印: `WORKS_USE_ALLOW_TESTCMD`
  - 今: `bin/_lib/launcher.py::ALLOW_TESTCMD_ENV`・`bin/_lib/launcher.py::check_test_cmd`
  - 状態: 形を変えて在る（名は `WORKS_FACTORY_ALLOW_TESTCMD`。#495 を #503 で戻した）
  - 旧棚卸し: T70

- U029 WORKS_USE_ALLOW_TESTCMD が空・1 の外なら拒む
  - 元: use.sh:207-210
  - 印: `WORKS_USE_ALLOW_TESTCMD`・`use.sh:209`
  - 今: `bin/_lib/launcher.py::check_test_cmd`
  - 状態: 形を変えて在る（1 の外の値は拒まず、許さない側として扱う。#495 を #503 で戻した）
  - 処置: 要らない: 1 の外の値は止める側に倒れ、手元を走らせる形の test_cmd を黙って通す事は無い（keep-essence 12）
  - 旧棚卸し: T70

- U030 test_cmd が対象の手元（元の clone）を走らせる形なら、何も写す前に「止める（test_cmd）」の行と理由で止める（終了コード 2）
  - 元: use.sh:58-60・1019-1036
  - 印: `use.sh:1035`
  - 今: `bin/_lib/launcher.py::check_test_cmd`（Archon を起こす前に止め、終了コード 2。#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: T70

- U031 test_cmd の形の確かめ（testcmd_check.py）そのものが落ちたら止める（許しが在れば落ちたと出して起こす）
  - 元: use.sh:60・1038-1046
  - 印: `WORKS_USE_ALLOW_TESTCMD`・`use.sh:1044`
  - 今: `bin/_lib/launcher.py::check_test_cmd`（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: T70

- U032 run・単位の worktree で走らない形（git が無視するパスを相対で指す）の test_cmd には「注意（test_cmd）」の行だけ出して止めない
  - 元: use.sh:61-62・1028
  - 印: 無し
  - 今: `bin/_lib/testcmd_check.py::path_notes`・README.md「test_cmd と作業ツリー」（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: T70

- U033 WORKS_USE_FIX_FIXTURE で、固定材料のフォルダから判定と修正案を作り直さずに修正から始める（入力 fix_fixture）
  - 元: use.sh:67-69・182・1141
  - 印: `WORKS_USE_FIX_FIXTURE`
  - 今: `workflows/line/scripts/start.py::from_fixture`・`lib/fixture.py::adopt`・`lib/fixture.py::capture`・`workflows/line/scripts/fix_in.py::fix_in`・`workflows/line/works-factory-line.yaml::fix-in`（前の run が修正に入る時に写した `<run の置き場>/fix-fixture/` を名指すと、直す前のテスト・判定・計画の往復・修正前の承認ノードを飛ばして修正から始める）
  - 状態: 在る
  - 旧棚卸し: L-E42・L-E43

- U034 WORKS_USE_FIX_FIXTURE が在るフォルダでなければ何も作らずに拒み、在れば打った場所から絶対パスにして渡す
  - 元: use.sh:217-222
  - 印: `WORKS_USE_FIX_FIXTURE`・`use.sh:220`
  - 今: `workflows/line/scripts/start.py::fixture_dir`
  - 状態: 形を変えて在る（殻でなくメイングラフの start ノードが AI の前に拒み、相対パスは打った場所でなく対象の根から解く。依頼・方針の文書の名指しと同じ規則）
  - 旧棚卸し: L-E42

- U035 --rounds は WORKS_DESIGN_ONLY=1 と組めない（Archon を起こす前に拒む）
  - 元: use.sh:211-214
  - 印: `--rounds`・`WORKS_DESIGN_ONLY`・`use.sh:214`
  - 今: `workflows/chain/scripts/chain_start.py::DESIGN_ONLY_REFUSED`・`workflows/chain/scripts/chain_start.py::start`・`workflows/chain/works-factory-chain.yaml::chain-start`
  - 状態: 形を変えて在る（殻でなく鎖のグラフの chain-start ノードが AI の前に拒む）
  - 処置: 戻した: `workflows/chain/scripts/chain_start.py::DESIGN_ONLY_REFUSED`
  - 旧棚卸し: L-D55

- U036 --rounds は WORKS_USE_FIX_FIXTURE と組めない
  - 元: use.sh:215
  - 印: `--rounds`・`WORKS_USE_FIX_FIXTURE`・`use.sh:215`
  - 今: `workflows/chain/scripts/chain_start.py::FIX_FIXTURE_REFUSED`・`workflows/chain/scripts/chain_start.py::start`・`workflows/chain/works-factory-chain.yaml::chain-start`
  - 状態: 形を変えて在る（殻でなく鎖のグラフの chain-start ノードが AI の前に拒む）
  - 旧棚卸し: L-D55

- U037 WORKS_USE_FINAL_GATE で最後の承認ノードの開き方を選ぶ（既定 protected_only・when_needed・always）
  - 元: use.sh:63・1132
  - 印: `WORKS_USE_FINAL_GATE`・`protected_only`・`when_needed`・`always`
  - 今: `workflows/line/works-factory-line.yaml`（入力 final_gate）・`lib/gatepolicy.py::check`
  - 状態: 形を変えて在る（`--input final_gate=<語>`。既定は always で、protected_only は `--input final_gate=protected_only` の名指しが要る）
  - 処置: 要らない: 今の works でもメイングラフの既定は always で、protected_only は殻の既定だった。`--input final_gate=protected_only` で同じ事ができ、既定を変えるのは止まる所を減らす向きなので持ち主の決め無しには変えない
  - 旧棚卸し: L-E30・L-G11

- U038 WORKS_DEV_ADAPTER で、包みを既定で入れ、0 か空の明示で外して adapter=optional と「包み無し」を出す
  - 元: use.sh:63-64・260-261・1048-1050・1132
  - 印: `WORKS_DEV_ADAPTER`
  - 今: `bin/_lib/launcher.py::write_fence`（走らせる命令ではいつも包みを置く）
  - 状態: 形を変えて在る（包みはいつも在り、外す旗が無い）
  - 処置: 要らない: 前の棚卸しの L-E39 の決め「役は Archon の役のノードが起こし、包みを通らない道が無い」
  - 旧棚卸し: L-E39・T49

- U039 WORKS_USE_POLICY_MD で人の方針の文書を渡す（入力 policy_md）
  - 元: use.sh:64・1136
  - 印: `WORKS_USE_POLICY_MD`
  - 今: `workflows/line/works-factory-line.yaml`（入力 policy_md）・`workflows/line/scripts/start.py::policy_md`
  - 状態: 形を変えて在る（`--input policy_md=<パス>`）
  - 旧棚卸し: L-E35

- U040 WORKS_USE_GATES で入力 gates（merge）を渡す
  - 元: use.sh:65・1137
  - 印: `WORKS_USE_GATES`
  - 今: 無し（メイングラフの入力に gates が無い）
  - 状態: 無い
  - 処置: 要らない: gates は変異の検算の入口で、`no-mutation-in-graph` がグラフに戻さないと決めた
  - 旧棚卸し: L-E40

- U041 WORKS_USE_THICKNESS で入力 thickness を渡す
  - 元: use.sh:65・1138
  - 印: `WORKS_USE_THICKNESS`
  - 今: `workflows/line/works-factory-line.yaml`（入力 thickness）・`workflows/line/scripts/start.py::words`
  - 状態: 形を変えて在る（`--input thickness=<語>`）
  - 旧棚卸し: L-E25

- U042 WORKS_USE_FEATURES_OFF で切る機能の語（カンマ区切り）を渡す
  - 元: use.sh:65-66・1139
  - 印: `WORKS_USE_FEATURES_OFF`
  - 今: `workflows/line/works-factory-line.yaml`（入力 features_off）・`lib/entry.py::FEATURES`
  - 状態: 形を変えて在る（`--input features_off=<語>`）
  - 旧棚卸し: L-E31・L-E32

- U043 WORKS_USE_FEATURES_ON で入れる機能の語を渡す（既定で off の judge_verify・auto の review_tree を on にする）
  - 元: use.sh:65-66・1140
  - 印: `WORKS_USE_FEATURES_ON`・`judge_verify`・`review_tree`
  - 今: `workflows/line/works-factory-line.yaml`（入力 features_on）・`lib/entry.py::FEATURE_DEFAULTS`
  - 状態: 形を変えて在る（`--input features_on=<語>`）
  - 旧棚卸し: L-E31・L-E32

- U044 WORKS_USE_HOME で利用の家を選ぶ（既定は XDG_STATE_HOME か ~/.local/state の下の works/use-<対象の実パスの sha256 の頭 8 字>）。clone ごとに分ける
  - 元: use.sh:35-36・258-264
  - 印: `WORKS_USE_HOME`・`XDG_STATE_HOME`・`HOME`
  - 今: `bin/_lib/launcher.py::run_home`・`bin/_lib/launcher.py::HOME_ENV`（既定は XDG_STATE_HOME か ~/.local/state の下の works-factory/targets/<sha256 の頭 8 字>）
  - 状態: 形を変えて在る（名が WORKS_FACTORY_HOME。相対は拒み、工場の checkout の下も拒む）
  - 旧棚卸し: 無し

- U045 家が役の sandbox の書ける置き場（/tmp/claude-*）の下なら拒む
  - 元: use.sh:265
  - 印: 無し
  - 今: `bin/_lib/launcher.py::refuse_sandbox_writable`
  - 状態: 在る
  - 旧棚卸し: 無し

- U046 家の目印として、家を作った clone の実パスを <家>/target に 1 行残す
  - 元: use.sh:342-343
  - 印: 無し
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 家の名が対象の実パスの sha256 で決まり（`bin/_lib/launcher.py::run_home`）、Archon の DB が codebase の登録に対象のパスを持つ
  - 旧棚卸し: 無し

- U047 AI の役は HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR を家の下へ隔離して起こし、利用者の本物の ~/.claude を読ませない
  - 元: use.sh:33-34
  - 印: `HOME`・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`
  - 今: `bin/_lib/isolate.py::isolate`・`bin/_lib/launcher.py::install_toolset`
  - 状態: 在る
  - 旧棚卸し: 無し

- U048 CLAUDE_CONFIG_DIR の相対パスを絶対に直す
  - 元: use.sh:226
  - 印: `CLAUDE_CONFIG_DIR`
  - 今: `bin/_lib/launcher.py::absolute`
  - 状態: 在る
  - 旧棚卸し: 無し

- U049 pack を対象に置かず、tests/・dev/・docs/ を除いた写しを家の Archon の置き場へ起こすたびに入れ替える
  - 元: use.sh:37-38・338-348・802・1105
  - 印: 無し
  - 今: `bin/_lib/place.py::workflow_source`・`bin/_lib/place.py::workflow_run`（`--workflow-source` で読ませる）
  - 状態: 形を変えて在る（家に写さず、取り置いたグラフの置き場を Archon に名指す）
  - 旧棚卸し: 無し

- U050 認証の順（WORKS_KEYCHAIN_ITEM → claude_auth の auth_env → Claude Code の keychain）で、出どころの名だけを受ける
  - 元: use.sh:79-80・284-287・324-325
  - 印: `WORKS_KEYCHAIN_ITEM`
  - 今: `bin/_lib/auth_launch.py::resolve`・`bin/_lib/auth_launch.py::ITEM_ENV`
  - 状態: 形を変えて在る（名が WORKS_FACTORY_KEYCHAIN_ITEM）
  - 旧棚卸し: 無し

- U051 認証が無ければ入れ方の文で拒む
  - 元: use.sh:326-328
  - 印: `use.sh:327`・`use.sh:280`
  - 今: `bin/_lib/auth_launch.py::main`（check が入れ方を出して 2）・`bin/_lib/launcher.py::launch`
  - 状態: 在る
  - 旧棚卸し: 無し

- U052 起動の時に認証の出どころを「認証: <名>（値は出さない）」で出す
  - 元: use.sh:1051-1053
  - 印: 無し
  - 今: `bin/_lib/launcher.py::launch`（「認証は <名> から拾う（値は出さない）」）
  - 状態: 在る
  - 旧棚卸し: 無し

- U053 uv が PATH に無ければ入れ方の行で拒む
  - 元: use.sh:329-331
  - 印: `use.sh:330`・`use.sh:280`
  - 今: 止めた Archon の `checkRuntimeAvailable`（`packages/workflows/src/validator.ts`。runtime: uv の script ノードの道具が無ければ警告）・`workflows/line/works-factory-line.yaml::start`（uv で走る最初のノード）
  - 状態: 形を変えて在る（殻は確かめず、Archon の確かめが警告し、最初の start ノードが AI の前に落ちる）
  - 処置: 要らない: 道具の確かめは Archon の validator が持ち（`on-archon-only`）、uv で走る最初の start ノードが AI の費用の前に落ちる
  - 旧棚卸し: 無し

- U054 本物の claude の実行ファイル（CLAUDE_BIN_PATH か PATH）が無ければ拒む
  - 元: use.sh:289-293・332-335
  - 印: `CLAUDE_BIN_PATH`・`use.sh:334`・`use.sh:280`
  - 今: `bin/_lib/launcher.py::real_claude`・`bin/_lib/launcher.py::launch`
  - 状態: 在る
  - 旧棚卸し: 無し

- U055 WORKS_DEV_MODEL で模型を明示する（未設定なら既定。包みが前付けの無い役の段に効かせる）
  - 元: use.sh:80-81・186
  - 印: `WORKS_DEV_MODEL`
  - 今: Archon の `workflow run --model`（tier・@alias の付け替え）と各ノードの YAML の `model:`
  - 状態: 形を変えて在る（ノードごとの model: が正で、run 単位の付け替えは Archon の旗）
  - 旧棚卸し: F146・J106

- U056 run の控え（模型・claude の実行ファイル・keychain の項目の名・包み）を残し、別の殻で打つ answer・stop・show・次の周がそれで Archon を起こす
  - 元: use.sh:452-454・495-504・825・922・932・944・1101-1102
  - 印: `answer`・`stop`・`show`
  - 今: 無し（殻は打つたびに利用者の env から解く）
  - 状態: 無い
  - 処置: 要らない: 模型は YAML のノードごとに固定で run の記録に残り、claude は `bin/_lib/launcher.py::real_claude` が毎回解き、包みはいつも在る（`one-launcher` で殻は控えを持たない）
  - 旧棚卸し: 無し

- U057 WORKS_MODEL_PINNED を利用者の殻から受けない（既定の釘は控えからだけ）
  - 元: use.sh:187-188
  - 印: `WORKS_MODEL_PINNED`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U056 の控えが無く、釘の env も無い（`one-launcher`）
  - 旧棚卸し: 無し

- U058 WORKS_DEV_ARCHON で Archon を呼ぶ殻を差し替える（試験が偽物を差す）
  - 元: use.sh:82・179
  - 印: `WORKS_DEV_ARCHON`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 試験のための継ぎ目で利用者の能力でない（`bin/_lib/apply.py::main` は get の口を引数で差し替える）
  - 旧棚卸し: 無し

- U059 承認ノードの文の答えの行の頭を、殻が env WORKS_ANSWER_CMD に置く
  - 元: use.sh:73・266-268
  - 印: `WORKS_ANSWER_CMD`
  - 今: `bin/_lib/launcher.py::answer_head`・`lib/answer.py::ENV`・`lib/answer.py::head`
  - 状態: 在る
  - 旧棚卸し: L-E50・L-G08

- U060 答えの行の末尾に答えた者の穴（WORKS_ANSWER_WHO「<答えた者>」）を見せる
  - 元: use.sh:269-271
  - 印: `WORKS_ANSWER_WHO`
  - 今: 無し（`lib/answer.py::line` は答えた者を付けない）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `answerer-unnamed`（答えた者の名は残さない。一言は Archon の run の記録が持つ）
  - 旧棚卸し: L-E50・L-G08

- U061 対象が /private/tmp の下なら拒む
  - 元: use.sh:52・246-248
  - 印: `use.sh:247`
  - 今: `bin/_lib/launcher.py::refuse_sandbox_writable`・`bin/_lib/launcher.py::SANDBOX_WRITABLE`（/tmp/claude-* と /private/tmp/claude-* だけ）
  - 状態: 形を変えて在る（拒むのは役の sandbox が書ける置き場だけ）
  - 処置: 要らない: 危うさは役の sandbox の Bash が対象を書き換えられることで、`bin/_lib/launcher.py::SANDBOX_WRITABLE` の柵をその置き場に絞った
  - 旧棚卸し: 無し

- U062 対象が git のリポジトリの中でなければ拒む
  - 元: use.sh:249-252
  - 印: `use.sh:251`
  - 今: Archon の `workflow run`（codebase の解決が「Either navigate to a git repo or use --cwd to specify one.」で落ちる）
  - 状態: 形を変えて在る（殻は git の根に寄せるだけで、拒むのは Archon）
  - 旧棚卸し: 無し

- U063 下のフォルダを渡されたら git の根で回し、そう言う 1 行を出す
  - 元: use.sh:39・253-256
  - 印: 無し
  - 今: `bin/_lib/launcher.py::target_root`
  - 状態: 形を変えて在る（根に寄せるが知らせの行は無い）
  - 処置: 要らない: 家は git の根の実パスで決まり（`bin/_lib/launcher.py::target_root`・`bin/_lib/launcher.py::run_home`）、同じ clone のどこから打っても同じ対象と家になるので、知らせが無くても取り違えない
  - 旧棚卸し: 無し

- U064 対象に pack の写し .archon/workflows/works が在れば拒む（dogfood.sh で回す）
  - 元: use.sh:53・296-298
  - 印: `use.sh:297`・`use.sh:280`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: グラフを対象に写す道が無く（`bin/_lib/place.py::workflow_run` の `--workflow-source`）、自分食いの別の殻も無い（`one-launcher`）
  - 旧棚卸し: 無し

- U065 対象に remote の origin が無ければ入れ方の行（手元だけなら bare の origin を作る手順）で拒む
  - 元: use.sh:51・53・299-300
  - 印: `use.sh:300`・`use.sh:280`
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`。origin の既定の枝が分からなければ「Pass --base, set worktree.baseBranch …」で落ちる）
  - 状態: 形を変えて在る（殻は確かめず、Archon の誤りの文で落ちる。bare の origin を作る手順の案内は無い）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が「Pass --base …」と直し方つきで止まる（`on-archon-only`）
  - 旧棚卸し: 無し

- U066 Archon に渡す worktree の土台の枝を origin/HEAD → origin/main → origin/master の順に手元の追跡 ref から求め、毎回 --base で渡す（登録の時の古い枝を使わせない）
  - 元: use.sh:86・302-314・1133-1135
  - 印: `use.sh:280`
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`。遠くが広告する既定の枝を読み、古い HEAD を推さない）
  - 状態: 形を変えて在る（Archon が自分で求める。origin/master への落としは無い）
  - 処置: 要らない: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）が既定の枝を求め、分からなければ「Pass --base …」と直し方つきで止まる（`on-archon-only`）
  - 旧棚卸し: 無し

- U067 origin の既定の枝が分からなければ fetch・set-head の手順で拒む
  - 元: use.sh:315
  - 印: `use.sh:315`・`use.sh:280`
  - 今: 止めた Archon の `getDefaultBranch`（`packages/git/src/branch.ts`）の誤り・止めた Archon の「cannot detect default branch」の案内（`packages/isolation/src/errors.ts`）
  - 状態: 形を変えて在る（Archon の文。手順は --base か設定）
  - 旧棚卸し: 無し

- U068 依頼の JSON が無ければ拒む
  - 元: use.sh:321-322
  - 印: `use.sh:322`・`use.sh:280`
  - 今: `workflows/line/scripts/start.py::request`（読めない・JSON でない・形が違うを分けて拒む）
  - 状態: 形を変えて在る（run の start ノードが AI の前に拒み、報告まで届く）
  - 旧棚卸し: L-E01・L-E02

- U069 依頼を - にしたのに --base も --pr も無ければ拒む
  - 元: use.sh:317-320
  - 印: `--base`・`--pr`・`use.sh:319`・`use.sh:280`
  - 今: `lib/entryshape.py::refuse_empty`
  - 状態: 形を変えて在る（run の start ノードが拒む）
  - 旧棚卸し: L-E07

- U070 run の worktree を対象の今の姿から切る（汚れていなければ HEAD から）
  - 元: use.sh:48・1112・1125-1126
  - 印: 無し
  - 今: `bin/_lib/startpoint.py::choose`（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- U071 commit していない変更・未追跡（.gitignore の物は除く）が在れば、一時の index で包んだ commit から切る（--from。対象の作業ツリー・index・枝は動かさない）
  - 元: use.sh:48-51・350-373・1108-1124
  - 印: 無し
  - 今: `bin/_lib/startpoint.py::choose`・`bin/_lib/startpoint.py::wrap`（#495 を #503 で戻した）
  - 状態: 在る
  - 旧棚卸し: 無し

- U072 包んだファイルを <家>/wraps/<commit>.txt に控え、起動の行に「包んだ（wrapped）」と並べる
  - 元: use.sh:50・1122-1124
  - 印: 無し
  - 今: `bin/_lib/startpoint.py::choose`
  - 状態: 形を変えて在る（包んだファイルは起動の 1 行に出し、家の控えのファイルは書かない。#495 を #503 で戻した）
  - 処置: 要らない: 包んだファイルは包んだ commit そのものが持ち（`git show --stat <commit>`）、Archon が run の起点として控える（`on-archon-only`）
  - 旧棚卸し: 無し

- U073 包んだ commit を refs/works/wraps/<commit> で gc から守り、clean が run と一緒に消す
  - 元: use.sh:1108-1121・548-557
  - 印: `clean`
  - 今: `bin/_lib/startpoint.py::wrap`
  - 状態: 形を変えて在る（ref を付けず、Archon が起動の内にそこから切る run の枝が守る。#495 を #503 で戻した）
  - 処置: 要らない: 片付ける ref を作らないので clean の片付けも要らない。gc から守るのは Archon が切る run の枝（`on-archon-only`）
  - 旧棚卸し: 無し

- U074 tdd_suite を省き test_cmd が pytest の 1 コマンド（前に uv run・poetry run・python3 -m を許し、; & | < > $ ` を含まない）なら、JUnit XML を書く実行器を書いて渡す
  - 元: use.sh:55-57・1069-1082
  - 印: 無し
  - 今: 無し（`lib/tddloop.py::NO_SUITE` の道で TDD のループを飛ばす。`superset` と `lang-neutral` のどちらを取るかは S100 と同じく持ち主が決める）
  - 状態: 無い
  - 処置: #516
  - 旧棚卸し: L-E38・F027

- U075 test_cmd が pytest の 1 コマンドでなければ、「TDD のループを飛ばす」と最後の引数 <tdd_suite> の渡し方を 1 行で知らせる
  - 元: use.sh:57・1086-1089
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::test_notes`・`lib/tddloop.py::SUITE_SKIPPED`
  - 状態: 形を変えて在る（殻の出力でなく起動の承認ノードの文に出る。渡し方は `--input tdd_suite=<実行器>`。tdd_suite を省いた run では test_cmd の形を問わず出る）
  - 処置: 戻した: `workflows/line/scripts/start.py::test_notes`・`lib/tddloop.py::SUITE_SKIPPED`
  - 旧棚卸し: F027

- U076 test_cmd を省けばメイングラフの既定（対象の .review-checks.json の宣言か CI）で回すと知らせる
  - 元: use.sh:57・1083-1085
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::test_notes`・`lib/declared_checks.py::checks_plan`
  - 状態: 形を変えて在る（注は宣言も test_cmd も無い時だけ起動の承認ノードの文に出る）
  - 旧棚卸し: L-E49

- U077 鎖の次の周は 1 周目と同じ実行器を使う
  - 元: use.sh:1063-1065
  - 印: `--chain-next`
  - 今: `workflows/chain/works-factory-chain.yaml`（入力 tdd_suite。どの周の子にも同じ値を渡す）
  - 状態: 在る
  - 旧棚卸し: 無し

- U078 依頼の元を <家>/requests/<時刻>.json に写して回す（元が後で書き換わっても回した物が残る）
  - 元: use.sh:1056-1061
  - 印: 無し
  - 今: `workflows/line/scripts/start.py::request`・`workflows/line/scripts/start.py::start`（本文 request_text を始めの記録に置く）
  - 状態: 形を変えて在る（ファイルの写しでなく本文を run の始めの記録に残す）
  - 旧棚卸し: L-E06

- U079 差分の根（base=/pr=）を 1 行で知らせる
  - 元: use.sh:1145-1147
  - 印: `--base`・`--pr`
  - 今: `workflows/line/scripts/start.py::gate_text`・`lib/startrec.py::words`（入口の文）
  - 状態: 形を変えて在る（起動の承認ノードの文に出る）
  - 旧棚卸し: L-E22・L-E48

- U080 起動ごとに一意の印（入力 launch_mark）を付け、起動の後にその印で run を結ぶ
  - 元: use.sh:43-45・1090-1093・1149・1170-1172
  - 印: 無し
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: Archon の `workflow run` が run の id を返すので、印で結ぶ要が無い（`on-archon-only`・`one-launcher`。前の棚卸しの L-E41 の決め）
  - 旧棚卸し: L-E41

- U081 起動した run を結べなければ、控えも続きの行も書かず、結べなかった 1 行と候補の show の行を出して 1 で終わる
  - 元: use.sh:44-45・use.sh:1195-1198
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 結べない run が生じない。Archon の `workflow run` が run の id を返す（`one-launcher`・`on-archon-only`。前の棚卸しの L-E41 の決め）
  - 旧棚卸し: L-E41

- U082 起動が 0 で終わったのに結べない時、生きた候補を家の unbound の控えに包んだ基と一緒に残し、最後の候補の clean が消す
  - 元: use.sh:45-47・use.sh:1173-1185・use.sh:558-578
  - 印: `start`・`clean`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 結べない run が生じない。Archon の `workflow run` が run の id を返す（`on-archon-only`。L-E41）。包んだ基は U071・U073
  - 旧棚卸し: L-E41

- U083 結べない時に run の一覧が読めなければ、候補の無い控えに残して理由の行で 1 で終わる
  - 元: use.sh:1177・use.sh:1186-1194
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U082 と同じ（Archon の `workflow run` が run の id を返す。`on-archon-only`）
  - 旧棚卸し: L-E41

- U084 結べず候補も無ければ、包んだ基の参照を外したと言い、起動の終了コード（0 なら 1）で終わる
  - 元: use.sh:1199-1206
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U082 と同じ（Archon の `workflow run` が run の id を返す。`on-archon-only`）
  - 旧棚卸し: L-E41

- U085 起動の後に状態・続きの行・差分のファイルを出し、終了コードは起動が 0 でなければ起動の値、0 なら show の値にする
  - 元: use.sh:1239-1254
  - 印: `start`・`show`
  - 今: Archon の `workflow run` の出力と終了コード（止めた Archon の `workflowRunCommand`（`packages/cli/src/commands/workflow.ts`））・Archon の `workflow get`（止めた Archon の `workflowGetCommand` が承認ノードの答えの行を出す）
  - 状態: 形を変えて在る（続きの行は Archon の `workflow get` が出す）
  - 旧棚卸し: 無し

- U086 start は Archon を起こす前に、この対象の生きていない run（failed も）の差分を書いてから worktree・枝・控えを片付ける（resume しない）
  - 元: use.sh:26-27・use.sh:751-798・use.sh:1129
  - 印: `start`・`failed`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: Archon の `workflow abandon`（worktree を外す）と `isolation cleanup` が片付けを持つ（`on-archon-only`）。差分は封じて run の置き場に在るので、worktree を消した後も当てられる（M41）
  - 旧棚卸し: M41

- U087 前の run の差分を書けなければ、その run を片付けずに理由の行を出す
  - 元: use.sh:778-784
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U086 と同じ（片付けは Archon の `workflow abandon`・`isolation cleanup` が持つ。`on-archon-only`）
  - 旧棚卸し: 無し

- U088 前の run の一覧が引けない・行が読めない・生きているか確かめられない・片付けが止まった時に、それぞれ 1 行出して残す
  - 元: use.sh:759-776・use.sh:786-790
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U086 と同じ（片付けは Archon の `workflow abandon`・`isolation cleanup` が持つ。`on-archon-only`）
  - 旧棚卸し: 無し

- U089 片付けた run の id と状態を入力 cleaned_runs で報告の冒頭へ渡す
  - 元: use.sh:754-755・use.sh:787・use.sh:1154
  - 印: `start`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U086 と同じ。start が片付けないので渡す物が無い（`on-archon-only`）
  - 旧棚卸し: 無し

- U090 show で run の状態・次に打つ行・差分のファイルを出し直す
  - 元: use.sh:9-10・use.sh:814-836
  - 印: `show`
  - 今: Archon の `workflow get`・Archon の `workflow status`（README.md「使い方」の 4. 見る）・`workflows/merge/scripts/merge.py::main`（差分を run の置き場に封じて置く）
  - 状態: 形を変えて在る（状態と行は Archon、差分は merge のサブグラフが run の置き場に置く）
  - 旧棚卸し: M24・M37

- U091 show で run-id を省けば、この対象で start が結んだ一番新しい run を出す
  - 元: use.sh:9・use.sh:490-494・use.sh:821-822
  - 印: `show`
  - 今: Archon の `workflow status`（家が対象ごとなのでこの対象の run だけ）・Archon の `workflow runs --limit`
  - 状態: 形を変えて在る（一番新しい 1 本を選ぶのは人）
  - 旧棚卸し: 無し

- U092 show に鎖の id を渡すと、周ごとと合計の報告 chain.md を今の控えから描き直す（止めていない鎖は途中の姿）
  - 元: use.sh:23・use.sh:817-820
  - 印: `show`
  - 今: `workflows/chain/scripts/final_diff.py::final`・`lib/chain.py::render`（鎖の最後に親の run の置き場へ chain.md を書く）
  - 状態: 形を変えて在る（chain.md は鎖が止まった時だけ。途中の周は Archon の `workflow get` で親の run の子を見る）
  - 処置: 要らない: 途中の姿は Archon の親の run の記録（子の run の状態）が持つ（`on-archon-only`）
  - 旧棚卸し: L-D57

- U093 show の終了コードは差分の書き出しの値にする
  - 元: use.sh:829-835
  - 印: `show`
  - 今: Archon の `workflow get` の終了コード（無い run は 1）
  - 状態: 形を変えて在る（差分の書き出しでなく run を引けたかの値）
  - 旧棚卸し: 無し

- U094 wait で決まった時間まで待ち、状態を 1 行で返す
  - 元: use.sh:11-15・use.sh:837-895
  - 印: `wait`
  - 今: Archon の `workflow wait`（止めた Archon の `workflowWaitCommand`（`packages/cli/src/commands/workflow.ts`）。`--timeout` で秒を渡す）
  - 状態: 形を変えて在る（Archon の命令。終了コードの意味が違う: U096〜U100）
  - 旧棚卸し: 無し

- U095 環境変数で wait の待つ秒を決める（既定 540 秒）
  - 元: use.sh:11・use.sh:183・use.sh:840-842
  - 印: `WORKS_USE_WAIT_SECONDS`・`wait`
  - 今: Archon の `workflow wait --timeout`（既定は期限なし）
  - 状態: 形を変えて在る（既定 540 秒が無い）
  - 処置: 要らない: `no-timeouts`（期限を足さない決まり。Archon も run だけが答えられる問いに自分の時計で答えないとして既定の期限を持たない）
  - 旧棚卸し: 無し

- U096 wait の待つ秒が整数でなければ拒む
  - 元: use.sh:841
  - 印: `WORKS_USE_WAIT_SECONDS`・`wait`・`use.sh:841`
  - 今: Archon の `workflow wait` の「--timeout must be a positive number of seconds」（止めた Archon の `packages/cli/src/cli.ts` の wait の分岐）
  - 状態: 在る
  - 旧棚卸し: 無し

- U097 wait の終了コード 0 は、承認ノードで人の答えを待つ（paused）ことを示し、show の行を出す
  - 元: use.sh:12・use.sh:872-876
  - 印: `wait`・`exit 0`
  - 今: Archon の `workflow wait`（run が状態を返せば 0、状態は標準出力）
  - 状態: 形を変えて在る（0 は paused に限らない。状態の語で見分ける）
  - 旧棚卸し: 無し

- U098 wait の終了コード 3 は、期限までに承認ノードにも終わりにも着かなかったことを示し、打ち直す行と止める行を出す
  - 元: use.sh:12・use.sh:884-889
  - 印: `wait`・`exit 3`
  - 今: Archon の `workflow wait --timeout`（期限が来て run が生きていれば 3）
  - 状態: 在る
  - 旧棚卸し: 無し

- U099 wait の終了コード 5 は、run が終わった（completed・cancelled）ことを示す。鎖なら鎖を止めた
  - 元: use.sh:13・use.sh:853-869
  - 印: `wait`・`exit 5`
  - 今: Archon の `workflow wait`（終わった run も 0 と状態）
  - 状態: 形を変えて在る（コードでなく状態の語で見分ける）
  - 旧棚卸し: 無し

- U100 wait の終了コード 1 は、run が落ちた（failed など）か見つからないことを示す
  - 元: use.sh:13・use.sh:844-847・use.sh:878-882
  - 印: `wait`・`exit 1`・`failed`
  - 今: Archon の `workflow wait`（見つからなければ 1、failed は 0 と状態）
  - 状態: 形を変えて在る（failed は 0 と状態の語。続ける行は Archon の `workflow get` が出す）
  - 旧棚卸し: 無し

- U101 wait の終了コード 6 は、鎖が次の周を起こして結んだことを示し、新しい run の id と次の wait の行を出す
  - 元: use.sh:13-15・use.sh:733-737・use.sh:865-867
  - 印: `wait`・`exit 6`
  - 今: `workflows/chain/works-factory-chain.yaml`（親の run が次の周を自分で起こす。人は親の run を待つ）
  - 状態: 形を変えて在る（次の周を起こすのに wait が要らない）
  - 旧棚卸し: L-D55

- U102 答え・承認を続きの口に渡したばかりの run は、Archon がまだ paused を返しても走る run と見る
  - 元: use.sh:849-852
  - 印: `wait`・`answer`・`approve`
  - 今: Archon の `workflow approve`・`workflow respond` の `--detach`（答えを記録してから再開し、記録が答え済みを持つ。止めた Archon の `assertApprovable`（`packages/core/src/operations/workflow-operations.ts`）の「already … awaiting resume」）
  - 状態: 形を変えて在る（殻の印でなく Archon の記録が答え済みを持つ）
  - 旧棚卸し: 無し

- U103 completed・cancelled の run は、wait・show が差分を書いた後に worktree・枝・控えを自動で消す（差分のファイルは残す）
  - 元: use.sh:26・use.sh:612-624・use.sh:831-833・use.sh:864
  - 印: `wait`・`show`
  - 今: 無し（Archon は run の worktree を残す。fix の子の worktree だけ `workflows/line/scripts/sweep_children.py::main` が消す）
  - 状態: 無い
  - 処置: 要らない: Archon の `isolation cleanup`・`workflow abandon` が片付けを持つ（`on-archon-only`）。封じた差分は run の置き場に在り、worktree を消した後でも当たる（M41）
  - 旧棚卸し: M41

- U104 差分を書けなかった run は自動で片付けず、そう言う 1 行を出す
  - 元: use.sh:617-620
  - 印: `wait`・`show`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U103 と同じ（片付けは Archon の `isolation cleanup`・`workflow abandon` が持つ。`on-archon-only`）
  - 旧棚卸し: 無し

- U105 自動の片付けが止まったら、clean で打ち直せると言う
  - 元: use.sh:622
  - 印: `clean`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U103 と同じ（片付けは Archon の `isolation cleanup`・`workflow abandon` が持つ。`on-archon-only`）
  - 旧棚卸し: 無し

- U106 failed の run は自動で消さずに残す（Archon の resume が前の worktree を使い直すため）
  - 元: use.sh:27・use.sh:612-615
  - 印: `failed`
  - 今: Archon の `workflow resume`（failed の run の worktree を使い直す）
  - 状態: 在る
  - 旧棚卸し: 無し

- U107 周の終わりに、その周の起点の木に差分を当てた commit（周の結果）を作って守り、次の周をそこから切り離して起こす
  - 元: use.sh:649-691
  - 印: `wait`・`--rounds`・`--chain-next`
  - 今: `workflows/chain/scripts/round_commit.py::commit`（親の run の枝へ積む）・`workflows/chain/works-factory-chain.yaml`（周ごとの `workflow:` ノード）
  - 状態: 形を変えて在る（専用の参照でなく親の run の枝の commit）
  - 旧棚卸し: L-D55

- U108 鎖の控えの錠で、同じ run に wait を重ねて打っても次の周を 2 本起こさない（錠が取れなければ 1 行出す）
  - 元: use.sh:650-651・use.sh:658-659
  - 印: `wait`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 次の周を起こすのは親の run 1 本の `workflow:` ノードで、wait は起こさない（`on-archon-only`）
  - 旧棚卸し: L-D58

- U109 wait した run が鎖の今の周でなければ、そう言って鎖を進めない
  - 元: use.sh:661
  - 印: `wait`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U108 と同じ（次の周は親の run の `workflow:` ノードが起こす）
  - 旧棚卸し: 無し

- U110 周の差分を書けない・周の結果の commit を作れない時、その訳を鎖の控えに書いて止めの決めに渡す
  - 元: use.sh:670-679
  - 印: `wait`
  - 今: `workflows/chain/scripts/round_commit.py::refused`・`workflows/chain/scripts/decide.py::halted`
  - 状態: 形を変えて在る（ok: false の訳を受けて止めの決めが halted にする）
  - 旧棚卸し: L-D55

- U111 途中で落ちた周は周に数えず、鎖を進めない（resume の後の wait に任せる）
  - 元: use.sh:697-702
  - 印: `wait`
  - 今: Archon の `workflow:` ノード（子の run が落ちれば親も止まる）・Archon の `workflow resume`
  - 状態: 形を変えて在る（resume した親の run が続ける）
  - 旧棚卸し: L-D58

- U112 鎖を止めた時、元の基から止まりと言われていない最後の周の結果までの最後の差分 final.diff と報告 chain.md を書き、取り込む行を出す
  - 元: use.sh:703-722
  - 印: `wait`
  - 今: `workflows/chain/scripts/final_diff.py::final`・`lib/chain.py::pick`・`lib/chain.py::render`・README.md「使い方」（周をつなぐ）
  - 状態: 在る
  - 旧棚卸し: L-D57

- U113 最後の差分に採れる周が無い・git diff が落ちた時はそう言う
  - 元: use.sh:709-712・use.sh:716-720
  - 印: `wait`
  - 今: `workflows/chain/scripts/final_diff.py::nothing`
  - 状態: 在る
  - 旧棚卸し: L-D57

- U114 次の周の起動が run を結ぶ前に落ちたら、打ち直しで 1 度だけ起こし直し、2 度目なら鎖を止める
  - 元: use.sh:738-742
  - 印: `wait`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 次の周は Archon の `workflow:` ノードが同じ process で子として起こし、結べない起動が無い（`on-archon-only`）
  - 旧棚卸し: L-D58

- U115 次の周の run がまだ結ばれていない・次の周の起動を待つ時は、打ち直す行を出して期限の 3 で終わる
  - 元: use.sh:692-695・use.sh:743-746
  - 印: `wait`・`exit 3`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: U114 と同じ（次の周は Archon の `workflow:` ノードが子として起こす）
  - 旧棚卸し: L-D58

- U116 周を切り離して起こす時、周ごとの出力を鎖の置き場の round-<N>.log に書く
  - 元: use.sh:686-689
  - 印: `--chain-next`
  - 今: Archon の子の run の記録と `workflow logs`
  - 状態: 形を変えて在る（ログは Archon が子の run ごとに持つ）
  - 旧棚卸し: 無し

- U117 1 周目の起動の前に鎖の控え chain.json（周の数・上限・対象・依頼の写し・test_cmd・tdd_suite・起動の環境）を書き、起こすたびに起点を残す
  - 元: use.sh:382-394・use.sh:1155-1163
  - 印: `start`・`--rounds`・`--budget-usd`
  - 今: `workflows/chain/scripts/chain_start.py::start`（rounds・budget・1 周目の依頼・起点を出力に持つ）
  - 状態: 形を変えて在る（控えのファイルでなくノードの出力）
  - 旧棚卸し: L-D55

- U118 1 周目の --pr を次の周の依頼の pr として運ぶ
  - 元: use.sh:387
  - 印: `--pr`・`--rounds`・`pr`
  - 今: `lib/chain.py::first_of`・`workflows/chain/scripts/chain_start.py::start`（first_pr）
  - 状態: 在る
  - 旧棚卸し: L-D56

- U119 鎖を起こした時に、鎖の id・周の上限・費用の上限と、鎖を進める wait の行を出す
  - 元: use.sh:1159・use.sh:1249-1252
  - 印: `--rounds`・`--budget-usd`・`wait`
  - 今: Archon の `workflow run` の出力（親の run の id）
  - 状態: 形を変えて在る（周の数と上限は入力のまま。進める wait の行は要らない）
  - 旧棚卸し: 無し

- U120 answer で、承認ノードで待つ run に continue か stop と一言と答えた者を渡して答える
  - 元: use.sh:16・use.sh:896-924
  - 印: `answer`
  - 今: Archon の `workflow respond`（README.md「使い方」の 3. 答える）・`lib/answer.py::taken`
  - 状態: 形を変えて在る（Archon の命令をそのまま打つ）
  - 旧棚卸し: L-G02・L-G04

- U121 答えの語が continue・stop の外なら拒む
  - 元: use.sh:899
  - 印: `answer`・`use.sh:899`
  - 今: 止めた Archon の `assertRespondable`（`packages/core/src/operations/workflow-operations.ts`。承認ノードが宣言した語の外を拒む）
  - 状態: 在る
  - 旧棚卸し: L-G03

- U122 answer の --exclude は受けない（同梱のメイングラフが外す単位を読まない）と理由つきで拒む
  - 元: use.sh:900-903
  - 印: `answer`・`use.sh:903`
  - 今: Archon の CLI の引数の読みの strict（知らない旗の --exclude を拒む。止めた Archon の `packages/cli/src/cli.ts`）
  - 状態: 形を変えて在る（理由と「一言に書く」の案内は無い）
  - 旧棚卸し: 無し

- U123 answer の第 7 引数から先は受けない
  - 元: use.sh:901-905
  - 印: `answer`・`use.sh:904`
  - 今: Archon の `workflow respond`（5 つ目からの位置引数を一言につなぐ。止めた Archon の `packages/cli/src/cli.ts` の respond の分岐）
  - 状態: 形を変えて在る（拒まずに一言に入る）
  - 処置: 要らない: 余った語は一言として記録に残り、黙って捨てられない
  - 旧棚卸し: 無し

- U124 承認ノードで待つ（paused）run でなければ答えを拒む
  - 元: use.sh:909-911
  - 印: `answer`・`use.sh:911`
  - 今: 止めた Archon の `assertApprovable`（`packages/core/src/operations/workflow-operations.ts`。「Only paused runs can be approved.」）
  - 状態: 在る
  - 旧棚卸し: 無し

- U125 答えた者（第 6 引数）が無ければ拒む（殻を打った者に落とさない）
  - 元: use.sh:897・use.sh:912-913
  - 印: `answer`・`use.sh:913`
  - 今: 無し（Archon の `workflow respond` は答えた者を持たない）
  - 状態: 無い
  - 処置: 要らない: 持ち主の決め `answerer-unnamed`（答えた者の名は残さない。一言は Archon の run の記録が持つ）
  - 旧棚卸し: L-E50

- U126 答え（時刻・run・対象・語・一言・答えた者）を家の answers.jsonl に 1 行ずつ残す
  - 元: use.sh:16・use.sh:914-921
  - 印: `answer`
  - 今: `lib/answer.py::taken`（run の置き場の承認ノードごとのファイルに語・一言・問いを残す）・Archon の run の出来事の記録
  - 状態: 形を変えて在る（run ごとの置き場に残る。答えた者と、家をまたぐ 1 本の記録が無い）
  - 処置: 要らない: 持ち主の決め `answerer-unnamed`（答えた者の名は残さない。一言は Archon の run の記録が持つ）
  - 旧棚卸し: L-G04

- U127 answer・approve は残りの処理を切り離して回し、wait の行を出して終わる
  - 元: use.sh:16-17・use.sh:460-489・use.sh:923・use.sh:933
  - 印: `answer`・`approve`
  - 今: Archon の `workflow respond`・`workflow approve`・`workflow reject` の `--detach`（止めた Archon の `runDetachedControlCommand`（`packages/cli/src/commands/workflow.ts`））
  - 状態: 在る
  - 旧棚卸し: 無し

- U128 切り離した Archon が 1 秒のうちに 0 以外で終われば、ログの末尾とその終了コードで終わる
  - 元: use.sh:463・use.sh:471-485
  - 印: `answer`・`approve`
  - 今: 止めた Archon の `runDetachedControlCommand`（切り離す前に親が同じ確かめを読むだけで走らせ、落ちればその場で終わる）
  - 状態: 形を変えて在る（確かめは切り離す前。走った後の失敗は `workflow wait`・`workflow get` で見る）
  - 旧棚卸し: 無し

- U129 切り離した出力を家の logs の下に書き、その置き場を出す
  - 元: use.sh:461・use.sh:467-468・use.sh:486
  - 印: `answer`・`approve`
  - 今: Archon の `workflow logs`（`--follow` で追う）
  - 状態: 形を変えて在る（ログは Archon が run ごとに持つ）
  - 旧棚卸し: 無し

- U130 approve で起動の承認ノードを越える
  - 元: use.sh:17・use.sh:925-934
  - 印: `approve`
  - 今: Archon の `workflow approve`（または `workflow respond` に approve）・`workflows/line/works-factory-line.yaml::gate-start`
  - 状態: 在る
  - 旧棚卸し: L-E51

- U131 approve は承認ノードで待つ（paused）run でなければ拒む
  - 元: use.sh:929-931
  - 印: `approve`・`use.sh:931`
  - 今: 止めた Archon の `assertApprovable`（`packages/core/src/operations/workflow-operations.ts`）
  - 状態: 在る
  - 旧棚卸し: 無し

- U132 stop で、承認ノードで待つ run は respond stop で止めて報告へ進める
  - 元: use.sh:18・use.sh:943-946
  - 印: `stop`
  - 今: Archon の `workflow respond` に stop と一言・`lib/answer.py::taken`（README.md「使い方」の 止める）
  - 状態: 在る
  - 旧棚卸し: L-G06・L-G07

- U133 stop で、走っている・落ちた run は止め札（stop.sh）で止め、次の段の切れ目で報告を出す
  - 元: use.sh:18・use.sh:936・use.sh:947
  - 印: `stop`・`stop.sh`
  - 今: Archon の `workflow cancel`（報告は出ない）・Archon の `workflow abandon`（failed の run）
  - 状態: 形を変えて在る（報告つきの止めは承認ノードの答えだけ）
  - 処置: 要らない: `stop-at-gates`（承認ノードの間の止めは報告の無い cancel を狭めとして認めた）
  - 旧棚卸し: 無し

- U134 stop で、既に終わった run は止める物が無いと拒む
  - 元: use.sh:941
  - 印: `stop`・`use.sh:941`
  - 今: Archon の `workflow cancel`（止めた Archon の `packages/core/src/operations/workflow-operations.ts` が running の外を「Cannot cancel run with status …」で拒む）
  - 状態: 在る
  - 旧棚卸し: 無し

- U135 stop は理由（第 4 引数）を必ず取る
  - 元: use.sh:18・use.sh:152・use.sh:945・use.sh:947
  - 印: `stop`
  - 今: Archon の `workflow respond` の一言（任意）・`lib/answer.py::STOP_NOTE`（空なら既定の文）
  - 状態: 形を変えて在る（理由は任意で、空なら既定の止めの文）
  - 処置: 要らない: 空の一言でも報告の止めの理由は空にならない（`lib/answer.py::taken`）
  - 旧棚卸し: L-G07

- U136 apply で run の差分を書き直し、git apply --check の後に対象へ当てる（commit しない）
  - 元: use.sh:19-21・use.sh:396-434・use.sh:950-971
  - 印: `apply`
  - 今: `bin/_lib/apply.py::main`・`bin/_lib/apply.py::put`（README.md「使い方」の 5. 当てる）
  - 状態: 形を変えて在る（書き直しでなく、封じた差分を hash で照らして当て、読み戻す）
  - 旧棚卸し: M39・M40・M48

- U137 差分を書き直せなければ、前の差分を当てずに拒む
  - 元: use.sh:965-967
  - 印: `apply`・`use.sh:967`
  - 今: `bin/_lib/apply.py::main`（封じた hash と置き場のファイルが合わなければ拒む）・`bin/_lib/apply.py::read_run`
  - 状態: 形を変えて在る（書き直しが無く、hash の食い違いで古い差分を拒む）
  - 旧棚卸し: M40

- U138 差分が空か書けていなければ拒む
  - 元: use.sh:968-969
  - 印: `apply`・`use.sh:969`
  - 今: `bin/_lib/apply.py::choose`（置いた差分が無い）・`workflows/merge/scripts/merge.py::main`（空の差分は封じない）
  - 状態: 形を変えて在る（空の差分はそもそも封じない）
  - 旧棚卸し: M5・M40

- U139 差分が対象のファイルを消すなら、消す許しが無い限り消すファイルを並べて拒む
  - 元: use.sh:20・use.sh:401-404
  - 印: `WORKS_USE_ALLOW_DELETE`・`apply`・`use.sh:403`
  - 今: `bin/_lib/apply.py::put`（旗 --allow-delete）
  - 状態: 形を変えて在る（環境変数でなく旗 --allow-delete）
  - 旧棚卸し: M42

- U140 記録が止まりを示す run は、止めた run を当てる許しが無い限り、止まった訳（結末・止めた者・一言）と許し方で拒む
  - 元: use.sh:21・use.sh:405-426
  - 印: `WORKS_USE_ALLOW_STOPPED`・`apply`・`use.sh:425`
  - 今: `bin/_lib/apply.py::choose`・`bin/_lib/apply.py::stopped_why`（旗 --allow-stopped）
  - 状態: 形を変えて在る（旗 --allow-stopped。R2 の作り直しは許しが在っても当てない）
  - 旧棚卸し: M43・M44

- U141 許しで止まった run を当てる時に、許しが在るので当てると 1 行出す
  - 元: use.sh:427
  - 印: `WORKS_USE_ALLOW_STOPPED`
  - 今: `bin/_lib/apply.py::main`
  - 状態: 在る
  - 旧棚卸し: M44

- U142 止まりかを記録で確かめられない run は、1 行出して当てる
  - 元: use.sh:414-417・use.sh:429
  - 印: `apply`
  - 今: `bin/_lib/apply.py::read_run`・`bin/_lib/apply.py::unchecked`（メイングラフの出力が読めなければ当てず、素の git apply の行を出す）
  - 状態: 形を変えて在る（当てずに拒む）
  - 処置: 要らない: 封じた hash で確かめられない差分は当てない決め（`bin/_lib/apply.py` の docstring。docs/plans/2026-10-13-line-wiring.md の M45・M46）
  - 旧棚卸し: M45・M46

- U143 git apply --check が通らなければ、対象の手元の変更とぶつかっていないかを見ると言って拒む
  - 元: use.sh:431
  - 印: `apply`・`use.sh:431`
  - 今: `bin/_lib/apply.py::put`
  - 状態: 在る
  - 旧棚卸し: M47

- U144 止まりを確かめる部品が落ちたら、当てずに 2 で終わる
  - 元: use.sh:407-421
  - 印: `apply`
  - 今: `bin/_lib/apply.py::read_run`・`bin/_lib/apply.py::UNREADABLE`（読めなければ 2）
  - 状態: 在る
  - 旧棚卸し: M49

- U145 apply はその対象の run だけを選ぶ（別の対象の run id を渡しても見つけない）
  - 元: use.sh:445-450・use.sh:953
  - 印: `apply`
  - 今: `bin/_lib/apply.py::main`・`bin/_lib/launcher.py::target_root`（家が対象ごと）
  - 状態: 在る
  - 旧棚卸し: M51

- U146 apply に鎖の id を渡すと、鎖の最後の差分 final.diff を同じ確かめで当てる
  - 元: use.sh:22・use.sh:954-962
  - 印: `apply`
  - 今: `bin/_lib/apply.py::choose`（親の run の結果の差分と封じた hash を読む）・`workflows/chain/scripts/result.py::from_final`
  - 状態: 在る
  - 旧棚卸し: M53

- U147 鎖の最後の差分がまだ無ければ（止まっていない・採れる周が無い）、show の行で拒む
  - 元: use.sh:958
  - 印: `apply`・`use.sh:958`
  - 今: `bin/_lib/apply.py::read_run`（終わっていない親の run を拒む）・`bin/_lib/apply.py::choose`（置いた差分が無い）
  - 状態: 形を変えて在る（文はメイングラフの run と同じ「置いた差分が無い」）
  - 旧棚卸し: M53

- U148 鎖の最後の差分が空なら拒む
  - 元: use.sh:959
  - 印: `apply`・`use.sh:959`
  - 今: `workflows/chain/scripts/final_diff.py::final`（空なら封じない）・`bin/_lib/apply.py::choose`
  - 状態: 形を変えて在る（空の差分はそもそも封じない）
  - 旧棚卸し: M53

- U149 apply の許し（消す許し・止めた run を当てる許し）は 1 回の打ち込みだけに効き、鎖の控えへ運ばない
  - 元: use.sh:375-380
  - 印: `WORKS_USE_ALLOW_DELETE`・`WORKS_USE_ALLOW_STOPPED`
  - 今: `bin/_lib/apply.py::main`（旗は 1 回の呼び出しだけに効く）
  - 状態: 在る
  - 旧棚卸し: M50

- U150 clean で終わった run の worktree と枝（と控え）を消す
  - 元: use.sh:24・use.sh:508-529・use.sh:545-604・use.sh:973-1015
  - 印: `clean`
  - 今: Archon の `workflow abandon`（worktree を外す）・Archon の `isolation cleanup`
  - 状態: 形を変えて在る（Archon の命令）
  - 旧棚卸し: 無し

- U151 走っている・承認ノードで待つ run の clean は拒む（生きた状態の判定が落ちたら消さずに 2 で終わる）
  - 元: use.sh:24・use.sh:1001-1006
  - 印: `clean`・`use.sh:1005`
  - 今: Archon の `workflow abandon`（running・paused・failed を受けて止めて閉じる）
  - 状態: 形を変えて在る（拒まずに止めて片付ける）
  - 処置: 要らない: abandon は人が明示で選ぶ止めで、走っている run を黙って消す道ではない（`on-archon-only`）
  - 旧棚卸し: 無し

- U152 run の worktree から切った単位の worktree と守りの参照も先に片付ける
  - 元: use.sh:585-596
  - 印: `clean`
  - 今: `workflows/line/scripts/sweep_children.py::main`・`bin/_lib/childsweep.py::sweep`（fix の並べの子の worktree と枝を run の終わりに消す）
  - 状態: 形を変えて在る（clean でなくメイングラフの後始末のノードが自動で）
  - 旧棚卸し: 無し

- U153 clean・start が消した failed の run は、Archon の記録も abandon で閉じる（worktree がもう無くても閉じる）
  - 元: use.sh:28-29・use.sh:508-543・use.sh:579-581
  - 印: `clean`・`start`・`failed`
  - 今: Archon の `workflow abandon`（記録を cancelled にし worktree を外す）
  - 状態: 在る
  - 旧棚卸し: 無し

- U154 記録を abandon で閉じられなければ、片付けは済んだことと打ち直しの行を出して abandon の終了コードで終わる
  - 元: use.sh:531-539・use.sh:1007-1014
  - 印: `clean`
  - 今: Archon の `workflow abandon` の誤りの出力
  - 状態: 形を変えて在る（片付けと閉じが 1 命令）
  - 旧棚卸し: 無し

- U155 clean に鎖の id を渡すと、鎖の控えと周の結果を守る参照を消す
  - 元: use.sh:25・use.sh:976-998
  - 印: `clean`
  - 今: Archon の `workflow abandon` に親の run（周の結果は親の run の枝の commit）
  - 状態: 形を変えて在る（専用の参照でなく親の run を閉じる）
  - 旧棚卸し: L-D58

- U156 鎖の clean は、次の周を起こす途中（pending が残る）なら拒む
  - 元: use.sh:983-985
  - 印: `clean`・`use.sh:984`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 次の周の起動の途中という状態が無い（親の run の `workflow:` ノードが子を起こす。`on-archon-only`）
  - 旧棚卸し: L-D58

- U157 鎖の clean は、最後の周の run が生きていれば拒む
  - 元: use.sh:986-993
  - 印: `clean`・`use.sh:989`・`use.sh:991`
  - 今: Archon の `workflow abandon`（親を閉じると子も止める。止めた Archon の `workflowAbandonCommand`（`packages/cli/src/commands/workflow.ts`）の cascadeFailures）
  - 状態: 形を変えて在る（拒まずに子ごと止める）
  - 処置: 要らない: U151 と同じ（abandon は人が明示で選ぶ止め）
  - 旧棚卸し: 無し

- U158 check で、AI を起こさずに pack を置いて Archon の validate を回す
  - 元: use.sh:30・use.sh:801-807・use.sh:812
  - 印: `check`
  - 今: `bin/_lib/launcher.py::launch`（validate は認証に通さない）・`bin/_lib/launcher.py::install_toolset`（スキルの名を照らせる設定を置く）・Archon の `validate workflows`
  - 状態: 形を変えて在る（殻 `bin/works-factory` に Archon の `validate workflows` と `--cwd` で対象を渡す）
  - 旧棚卸し: 無し

- U159 check は、start に足りない物（uv・claude・認証・対象の条件）を拒まずに全部並べ、在れば終了コード 2 で終わる
  - 元: use.sh:31・use.sh:54・use.sh:273-282・use.sh:808-811
  - 印: `check`
  - 今: 無し（殻は走らせる命令で 1 つ目に止まり、uv は Archon の validate の警告）
  - 状態: 無い
  - 処置: 要らない: `one-launcher`。足りない物は `workflow run` の時に Archon を起こす前（AI の費用の前）に入れ方の行つきで止まる（README.md「使い方」の 1. 入れる）。Archon 自身の点検は Archon の `doctor`
  - 旧棚卸し: 無し

- U160 特定の利用者の端末の道具の枠の中で起こした run は、その枠とサーバを控えに残す
  - 元: use.sh:74-75
  - 印: `use.sh:74`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 特定の利用者の端末の道具との結び（#505 の受け入れ: 特定の利用者の道具の名を持ち込まない）
  - 旧棚卸し: 無し

- U161 起動・show・wait・答え・承認・止め・無人の続き・片付けのたびに、run を起こした端末の枠ごとに集計の信号を出し、全部終わった時だけ外す
  - 元: use.sh:75-77・use.sh:455-459・use.sh:796・use.sh:834・use.sh:893・use.sh:1013・use.sh:1243-1248
  - 印: `use.sh:75`・`use.sh:455`
  - 今: 無し
  - 状態: 無い
  - 処置: 要らない: 特定の利用者の端末の道具との結び（#505 の受け入れ: 特定の利用者の道具の名を持ち込まない）
  - 旧棚卸し: 無し

## keep-essence.md

- K1 直す前の名指しのテストが failure（error・一式に居ない・もう通る・飛ばされた、は拒む）で落ちることを、JUnit の結末から機械が見る（pytest の対象では tdd_suite を省いても既定で効く）
  - 元: keep-essence.md:10
  - 印: `keep-essence.md:10`
  - 今: `lib/baseline_red.py::red_problems`・`lib/tddloop.py::red_check`（TDD のループの test の段 `workflows/fix/works-factory-fix.yaml::tdd-step`）・`workflows/line/scripts/start.py::test_notes`（tdd_suite が無ければ `lib/tddloop.py::NO_SUITE` の道でループを飛ばし、始めの注に残す）
  - 状態: 形を変えて在る（tdd_suite を渡した run でだけ効く。省いた run で test_cmd から実行器を書く道は無い）
  - 処置: #516
  - 旧棚卸し: F001・F008

- K1b 直した後に名指しのテストが通り、元で通っていた試験が赤にならず、一式が 0 で終わることを JUnit から機械が見る（pytest の対象では既定で効く）
  - 元: keep-essence.md:10
  - 印: 無し
  - 今: `lib/baseline_red.py::green_problems`・`lib/tddloop.py::_green`
  - 状態: 形を変えて在る（tdd_suite を渡した run でだけ効く）
  - 処置: #516
  - 旧棚卸し: F004

- K1c 受け付けの最後に、修正前の版とループの赤の木で赤 → 緑を機械が確かめ直す（役の申告に頼らない事後の関門）
  - 元: keep-essence.md:10
  - 印: 無し
  - 今: `lib/fixgates.py::problems`・`lib/fixgates.py::_red_green`（`workflows/fix/works-factory-fix.yaml::fix-accept`）
  - 状態: 在る
  - 旧棚卸し: F037・F038・F040

- K1d 役が赤の時の失敗の文を引いて理由を書き、その引用がその回の結末（failure の文・本文、無ければその回のログ）に在ることを機械が照らす
  - 元: keep-essence.md:10
  - 印: 無し
  - 今: `lib/tddloop.py::red_check`・`lib/tddloop.py::_quote_problem`・`lib/tddloop.py::QUOTES_FIELD`
  - 状態: 在る
  - 旧棚卸し: F002・F003

- K1e 引用と理由が報告の単位の行に載り、理由の正しさは人が見る（最後の承認ノードの文には載らない）
  - 元: keep-essence.md:10
  - 印: 無し
  - 今: `lib/report.py::_red_evidence`・`lib/report.py::_tdd_unit`（`lib/runreport.py` が `lib/report.py::tdd_lines` で並べる）
  - 状態: 在る
  - 旧棚卸し: R48・F431

- K2 修正の前から赤だったテストを、元の版の結末との突き合わせで分ける（TDD のループの赤緑でも最後のテストの段でも）
  - 元: keep-essence.md:11
  - 印: `keep-essence.md:11`
  - 今: `lib/baseline_red.py::_broken_others`・`lib/baseline_red.py::_must_pass`・`lib/tddloop.py::_base_reds`・`workflows/test-gate/works-factory-test-gate.yaml::run`・`workflows/test-gate/works-factory-test-gate.yaml::result`（inherited と introduced の区別）
  - 状態: 在る
  - 旧棚卸し: F005・F006・T33・T37

- K3 TDD のループの最中: 緑にした単位のテストのファイルを hash で控え、後の段で変えたら拒む
  - 元: keep-essence.md:12
  - 印: `keep-essence.md:12`
  - 今: `lib/tddloop.py::hashes`・`lib/tddloop.py::_frozen_moved`・`lib/tddloop.py::_other_test_edits`
  - 状態: 在る
  - 旧棚卸し: F015・F018

- K3b ループが済んだ後: 修正の受け付けが、ループで緑にした単位のテストのファイルが変わっていないかを確かめる
  - 元: keep-essence.md:12
  - 印: 無し
  - 今: `lib/tddloop.py::frozen_problems`・`lib/factchecks.py`（手順 1b。`workflows/fix/works-factory-fix.yaml::fix-accept`）
  - 状態: 在る
  - 旧棚卸し: F016・F017

- K3c 既存のテストの変更を許す道は 1 本（裁定 fix_test_scope の範囲・承認済みの修正案の rewrite_tests・案の直しで直した項目・範囲の相談の合意）で、凍結の検査・事後の関門・範囲の照らし・最後の承認ノードはそこから引く
  - 元: keep-essence.md:12
  - 印: 無し
  - 今: `lib/conflict.py::test_permits`（許す元は 5 つに増えている: 修正案の removes が名指す既存テストも足した。読み手 `lib/fixgates.py::_test_edits`・`lib/tddloop.py::frozen_problems`・`lib/planrange.py::permit_paths`・`lib/conflict.py::ruled_test_doc`）
  - 状態: 在る
  - 旧棚卸し: F228・F039・F044

- K3d TDD のループの中の単位は、その単位の修正案の約束が名指した書き換えだけを変えてよい（名指しの外の既存の test 関数の本体の書き換えは走らせる前に拒む）
  - 元: keep-essence.md:12
  - 印: 無し
  - 今: `lib/tddloop.py::_plan_rewrites`・`lib/tddloop.py::_unnamed_edits`・`lib/tddloop.py::_test`
  - 状態: 在る
  - 旧棚卸し: F011・F019

- K4 直す単位が TDD のループの中で 3 回拒まれたら、作業ツリーを単位の頭の版に戻し、理由を残して食い違いの申し出（needs_context）として裁定に回し、他の単位は先へ進む
  - 元: keep-essence.md:13
  - 印: `keep-essence.md:13`
  - 今: `lib/tddloop.py::_give_up`・`lib/tddloop.py::retry_max`（= `lib/rolekit.py::GIVE_UP_AFTER` の 3）・`lib/tddloop.py::GAVE_UP_WHY`
  - 状態: 在る
  - 旧棚卸し: F021・F022・F023

- K4b 修正の受け付けの 3 回目の拒否: 拒否に結べる単位だけを段の頭の木に戻して止め（patch の控えと ask_human の裁定を残す）、受けた単位で先へ進む
  - 元: keep-essence.md:13
  - 印: 無し
  - 今: `lib/fixboard.py::accept_reply`・`lib/fixboard.py::last_settle`・`lib/fixboard.py::loop_done`（`workflows/fix/works-factory-fix.yaml::fix-accept`）
  - 状態: 在る
  - 旧棚卸し: F133・F106・F134

- K5 Edit・Write の記録と、shell で書いたファイルの申告（bash_writes）を照らし、どちらにも無い書き込みを拒む
  - 元: keep-essence.md:14
  - 印: `keep-essence.md:14`
  - 今: `lib/writes.py::check`（fix-accept・tdd-step・refix の受け付け。記録の無い run は拒まず NO_RECORD を trace と報告に残す）・記録のフック `bin/_lib/record-write.py`（`bin/_lib/toolset.py::recorder_row` が隔離した設定の PostToolUse:Edit|Write|NotebookEdit に置く）・`lib/writelog.py::log_path`
  - 状態: 在る
  - 旧棚卸し: F034・F102・F103・F310

- K6 受け付けで、変更に直に関わる試験を選んで回し、新しい赤を拒む（地図が引けなければ一式）
  - 元: keep-essence.md:15
  - 印: `keep-essence.md:15`
  - 今: `lib/tddloop.py::selected_problems`・`lib/impact.py::select_tests`（direct_only）・`workflows/fix/scripts/fix_accept.py`
  - 状態: 在る
  - 旧棚卸し: F012・F014

- K6b 回さなかった試験（手元で回さなかった ci_left・最後のテストの段に任せた final_left・final_far）を名前で trace に残し、最後の承認ノードと報告に並べる
  - 元: keep-essence.md:15
  - 印: 無し
  - 今: `lib/tddloop.py::ci_left`・`lib/tddloop.py::final_left`・`lib/tddloop.py::final_far`・`lib/impact.py::ACCEPT_TRACE_OP`（`lib/fixboard.py` が書く trace の行）・`lib/fixbeside.py::tests_left_lines`（読み手 `workflows/line/scripts/ask_final.py::fix_beside`・`lib/runreport.py`）
  - 状態: 在る
  - 旧棚卸し: F013・F041

- K7 判定役が書いた欠陥の探し方（class_query: grep の型と対象のパス）を持たせ、修正の前と後の件数を機械が数え直す
  - 元: keep-essence.md:16
  - 印: `keep-essence.md:16`
  - 今: 判定の側 `lib/judge_accept.py::judge_output`（`workflows/judge/works-factory-judge.yaml::diagnose-accept`。開いた単位に class_query を要る）・修正の側 `lib/recount.py::accept_fix`・`lib/recount.py::recount_problems`・`lib/querytest.py::closure_lines`（最後の承認ノードと報告に閉鎖の行）
  - 状態: 在る
  - 旧棚卸し: J70・J71・F112・F122・F123

- K8 依頼・テスト・コードが食い違う時に役が申し出て、読むだけの裁定役が決める
  - 元: keep-essence.md:17
  - 印: `keep-essence.md:17`
  - 今: `lib/conflict.py::ITEM_SCHEMA`（申し出の形）・`workflows/fix/works-factory-fix.yaml::rule-loop`・`workflows/fix/works-factory-fix.yaml::ruler`（allowed_tools は Read・Grep・Glob・WebSearch・WebFetch、mutates_checkout: false、sandbox 有効）・`workflows/fix/works-factory-fix.yaml::rule-accept`
  - 状態: 在る
  - 旧棚卸し: F200・F201・F209・F210・F211

- K8b 申し出が名指した箇所（`<パス>:<行>`）が現物に在るかを機械が確かめ、無ければ申し出として扱わない
  - 元: keep-essence.md:17
  - 印: 無し
  - 今: `lib/conflict.py::problems_by_entry`・`workflows/fix/works-factory-fix.yaml::conflict-check`
  - 状態: 在る
  - 旧棚卸し: F202・F208

- K9 依頼の目的だけから別の役が設計し（run で 1 度・修正の前）、修正案と突き合わせ、直した後の差分とも比べる
  - 元: keep-essence.md:18
  - 印: `keep-essence.md:18`
  - 今: `workflows/plan-review/works-factory-plan-review.yaml::r2-design-loop`・`workflows/plan-review/works-factory-plan-review.yaml::r2-prep`・`workflows/plan-review/works-factory-plan-review.yaml::r2-design`・`workflows/plan-review/works-factory-plan-review.yaml::r2-accept`（修正案との突き合わせは事前審査の材料の頭）・`workflows/eyes/works-factory-eyes.yaml::r2-compare`・`workflows/eyes/works-factory-eyes.yaml::r2-compare-verdict`
  - 状態: 在る
  - 旧棚卸し: P159・P162・P163・P175・P177・E5・E6・L-W55

- K9b R1〜R4 の 4 つの観点の審査（最小性・設計の比較・整合・隠れた範囲）
  - 元: keep-essence.md:18
  - 印: 無し
  - 今: `workflows/eyes/works-factory-eyes.yaml::r1-minimality`・`workflows/eyes/works-factory-eyes.yaml::r1-minimality-verdict`・`workflows/eyes/works-factory-eyes.yaml::r2-compare`・`workflows/eyes/works-factory-eyes.yaml::r2-compare-verdict`・`workflows/eyes/works-factory-eyes.yaml::r3-coherence`・`workflows/eyes/works-factory-eyes.yaml::r3-coherence-verdict`・`workflows/eyes/works-factory-eyes.yaml::r4-loop`・`workflows/eyes/works-factory-eyes.yaml::r4-scope-verdict`
  - 状態: 在る
  - 旧棚卸し: E2・E3・E8・E9

- K10 対象のリポジトリが守ると宣言したファイルに触れたら、開き方（protected_only・when_needed・always）に関わらず最後の人の承認ノードを開き、答えが無ければ差分を当てない
  - 元: keep-essence.md:19
  - 印: `keep-essence.md:19`・`final-gate`・`protected_only`・`when_needed`・`always`
  - 今: `lib/protect.py::TARGET_FILE`（名は `.works-protected.json`。始めの版の中身を読む）・`lib/protect.py::merged`・`workflows/eyes/works-factory-eyes.yaml::protected`・`workflows/line/scripts/ask_final.py::needs`・`lib/seal.py::apply_refusal`（`bin/apply`）
  - 状態: 在る
  - 旧棚卸し: F430・M26・M22・M31・L-G49・L-G50

- K10b 許したテストの変更（理由と許しの出どころつき）と、人に回した食い違いの申し出も最後の承認ノードに並べ、それだけでも承認ノードを開く
  - 元: keep-essence.md:19
  - 印: 無し
  - 今: `workflows/line/scripts/ask_final.py::allowed_tests`・`workflows/line/scripts/ask_final.py::conflict_section`・`workflows/line/scripts/ask_final.py::needs`・`workflows/line/scripts/ask_final.py::ALLOWED_TESTS_HEAD`・`lib/conflict.py::ruled_test_doc`
  - 状態: 在る
  - 旧棚卸し: F429・F426・F230・M30

- K11 直す単位ごとの記録（TDD のループの単位の結末・閉鎖の数え直し・人に回した物・減っていない単位）が報告と最後の承認ノードに届く
  - 元: keep-essence.md:20
  - 印: `keep-essence.md:20`
  - 今: `workflows/fix/works-factory-fix.yaml::tdd-unit`（型つきの成果物 tdd-unit）・`lib/runreport.py`（`lib/report.py::tdd_lines`・`lib/report.py::freeze_lines` で並べる）・`workflows/line/scripts/ask_final.py::final_text`（handoffs・stuck・unproven・closure・amend の行。最後の承認ノードには TDD の赤緑の単位の行は載せず、閉鎖・人に回した物などの単位の行を載せる。赤の引用を載せないのは元の 1 の決めどおり）
  - 状態: 在る
  - 旧棚卸し: F431・F416・R48・R29

- K12 設計を決める前に、依頼の各行を、依頼の解き方と対象の名を外した問題の類に言い直す（対象の識別子を含む類・検索語の無い行は拒む）
  - 元: keep-essence.md:21
  - 印: `keep-essence.md:21`
  - 今: `lib/worldblk.py::class_problems`・`lib/worldblk.py::classes_accept`・`lib/worldcheck.py::banned_tokens`・`lib/worldcheck.py::text_problems`・`workflows/judge/works-factory-judge.yaml::world-classes-loop`・`workflows/judge/works-factory-judge.yaml::world-classes-accept`
  - 状態: 在る
  - 旧棚卸し: J21・J23

- K12b 世の中がその類をどう解いているかを出どころと原文の抜き書きつきで集め、抜き書きが出どころに在ることを機械が取り直した本文で確かめる（網に出られなければ知識だけの印で進む）
  - 元: keep-essence.md:21
  - 印: 無し
  - 今: `lib/worldcheck.py::verify`・`lib/worldblk.py::judge_problems`・`lib/worldblk.py::judge_accept`・`workflows/judge/works-factory-judge.yaml::world-judge-loop`・`workflows/judge/works-factory-judge.yaml::world-judge-accept`
  - 状態: 在る
  - 旧棚卸し: J22・J26

- K12c 依頼の解き方か設計が定石と違えば、違いを名指して定石を推す（differs の行は challenge を要る。修正案の外れの訳は事前審査が見る）
  - 元: keep-essence.md:21
  - 印: 無し
  - 今: `lib/worldblk.py::MIN_CHALLENGE`・`lib/worldmark.py::VERDICTS`・`lib/worldmark.py::section`（判定・計画の材料の頭）
  - 状態: 在る
  - 旧棚卸し: J24・J28・P185

- K12d 修正案は当たる定石の行ごとに、従うか外れの訳を書き、欠けは受け付けが拒む
  - 元: keep-essence.md:21
  - 印: 無し
  - 今: `lib/worldmark.py::unanswered`・`lib/worldmark.py::PLAN_ASK`・`workflows/plan/works-factory-plan.yaml::plan-accept`
  - 状態: 在る
  - 旧棚卸し: P030

- K12e 依頼そのもの（依頼のファイル・引用・依頼の解き方）を出どころにした外れと、web で確かめていない定石からの外れは、修正前の人の承認ノードに上がる
  - 元: keep-essence.md:21
  - 印: 無し
  - 今: `lib/worldmark.py::world_ok`・`lib/gatemarks.py::WORLD_KIND`・`workflows/line/works-factory-line.yaml::gate-before-fix`
  - 状態: 在る
  - 旧棚卸し: P233・L-G29

## 数

- 行: 405
- 状態 在る: 184
- 状態 形を変えて在る: 174
- 状態 無い: 47
- 処置 #516: 4
- 処置 戻した: 10
- 処置 要らない: 107
- 無い行: S001・S008・S023・S080・S100・S105・S107・S124・S136・S165・S168・S196・S202・S207・S215・U011・U013・U014・U040・U046・U056・U057・U058・U060・U064・U074・U080・U081・U082・U083・U084・U086・U087・U088・U089・U103・U104・U105・U108・U109・U114・U115・U125・U156・U159・U160・U161

## 前の棚卸しの今

前の棚卸し `docs/plans/2026-10-13-capabilities/` の各行の「今」（works-factory の住処）を、#521 でここへ移した物。「今」の名の持ち主はこの表の 1 か所で、名を変える PR はこの表だけを直す。1 行 1 つで `- <ファイル> <行 ID>: <今>` と書き、前の棚卸しの行は「今」の欄に「表」（住処が無い行は「無し（表）」）の印だけを書き、ファイルと行 ID でここの行に当たる。語は前の棚卸しの字をグラフの語へ直した物で、源（コード・計画・前の版の文書）の字を引いた所だけは `…` で囲んで原文のまま書く。`tests/layers/test_works_parity.py` が、表の「今」と同じ規則で行番号を持たず名が main に在ることと、前の棚卸しの印の行とここの行が 1 つずつ合い、前置きの後に `- ` で始まらない行（続きの行）が無く、印が「無し（表）」の行はここの字が「無し」で始まる行だけであることを照らす。

- fix.md F001: lib/tddloop.py::red_check → lib/baseline_red.py::red_problems・lib/baseline_red.py::parse_junit
- fix.md F002: lib/tddloop.py::_quote_problem・lib/tddloop.py::MIN_QUOTE・lib/tddloop.py::red_check
- fix.md F003: lib/tddloop.py::plan_contract（同じ）
- fix.md F004: lib/tddloop.py::_green → lib/baseline_red.py::green_problems
- fix.md F005: lib/tddloop.py::start（start の中で `run_suite` を 1 回、`st["baseline"]`）・lib/baseline_red.py::_must_pass
- fix.md F006: lib/tddloop.py::selected_problems
- fix.md F007: lib/tddloop.py::_test
- fix.md F008: lib/tddloop.py::red_check
- fix.md F009: lib/tddloop.py::step
- fix.md F010: lib/tddloop.py::_route・lib/tddloop.py::_plan_tdd
- fix.md F011: lib/tddloop.py::_plan_tests・lib/tddloop.py::_plan_rewrites・lib/tddloop.py::_unnamed_edits
- fix.md F012: lib/tddloop.py::_reached・lib/tddloop.py::selected_problems、lib/impact.py
- fix.md F013: lib/fixboard.py::tests_trace（受け付けの回に impact.ACCEPT_TRACE_OP の行に ci_left・final_left・final_far）→ 子の結果の accept_trace → lib/fixboard.py::accept_trace_rows → fix の diff の隣の accept-trace.json（lib/fixbeside.py）→ ask_final と報告の lib/fixbeside.py::tests_left_lines
- fix.md F014: lib/fixboard.py::accept_reply が `tddloop.selected_problems` の知らせを `tests_trace` で diff の隣の `accept-trace.json`（受け付けの回ごとの行 `{op: fix_tests_selected, node, pass, attempt, note, ci_left, final_left, final_far}`）に積む。組の子の行は group-end が組の結果の `accept_trace` に `group_id` つきで載せ、親の collect が親の行と合わせて親の diff の隣の `accept-trace.json` に置く（止めの道・lib の無い道は無ければ `[]`）（#121）
- fix.md F015: lib/tddloop.py::hashes・lib/tddloop.py::_frozen_moved・lib/tddloop.py::_other_test_edits・lib/tddloop.py::_vanished_problems
- fix.md F016: lib/tddloop.py::frozen_problems、lib/factchecks.py::check_frozen、lib/fixboard.py::accept_reply（`note("frozen", factchecks.check_frozen(...))`）
- fix.md F017: lib/tddloop.py::_function_span（公開名 `function_span`）
- fix.md F018: 2 回目の段の prep が入力 prior_conflicts の先（1 回目の置き場）の TDD のループの状態を印 prior_pass つきで自分の置き場に写し（lib/fixboard.py::adopt_prior_pass・lib/fixboard.py::adopt_tdd_states の prior）、組の子は親から写す（lib/fixboard.py::adopt_inputs）。受け付けの凍結（lib/factchecks.py::check_frozen）が tddloop.states で 1 回目のループも見る。写したループは今の段のループに数えない（lib/fixboard.py::ruled_states）。直した項目の単位の許し AMENDED_TEST_ID は L-W18 の写した AMENDED の行から
- fix.md F019: lib/tddloop.py::_verified・lib/tddloop.py::verified_rewrites、lib/factchecks.py::check_frozen（`skip`）
- fix.md F020: lib/tddloop.py::together・lib/tddloop.py::_close_covered
- fix.md F021: lib/tddloop.py::_give_up・lib/tddloop.py::step（`source = conflict.GAVE_UP_SOURCE`）、workflows/fix/scripts/tdd_step.py::main（`flush_unsent` → `conflict.park_claims`）
- fix.md F022: lib/conflict.py::FIX_SOURCE・lib/conflict.py::TDD_SOURCE・lib/conflict.py::GAVE_UP_SOURCE、lib/tddloop.py::step
- fix.md F023: lib/conflict.py::park_claims（AMENDED の行の単位なら ask_human・by tdd-repeat）。2 回目の段の置き場と組の子の置き場に 1 回目の行が写り、直した項目の待つ行が AMENDED になる（lib/conflict.py::adopt_prior。L-W18）ので、2 回目の段の機械の諦めが働く
- fix.md F024: lib/tddloop.py::_refactor・lib/tddloop.py::_declared・lib/tddloop.py::_give_up
- fix.md F025: lib/tddloop.py::_test_cmd_gate・lib/tddloop.py::_cmd_run・lib/tddloop.py::_cmd_material、workflows/fix/scripts/group_start.py::main（始めの記録の test_cmd と単位の深さを渡す）
- fix.md F026: lib/baseline_red.py::lowered・lib/baseline_red.py::nice19（子の優先度を nice -n 19 と同じだけ下げる preexec の 1 か所。argv・環境・作業の場は変えないので、起こせるかの証明は tree_run.run が走らせる時と同じ形で行う。下げられない環境は下げずに起こしログの頭に NO_NICE の 1 行）を `run_suite`・lib/tddloop.py::_cmd_material・lib/declared_checks.py::local_checks_material が呼ぶ（#121）
- fix.md F027: lib/tddloop.py::start・lib/tddloop.py::_abort、workflows/fix/scripts/group_start.py::main、workflows/fix/fixtures/group-no-suite.stubs.yaml
- fix.md F028: lib/tddloop.py::MAX_ITERATIONS、workflows/fix/works-factory-fix.yaml::tdd-loop（`max_iterations: 40`・`until_bash: done=$tdd-step.output.done`）
- fix.md F029: lib/tddloop.py::step（`st.setdefault("calls", [])`）・lib/tddloop.py::exit_fields
- fix.md F030: lib/tddloop.py::prep、workflows/fix/scripts/tdd_step.py::REJECT（`"tdd-step-reject-{}.md"`）・workflows/fix/scripts/tdd_step.py::main
- fix.md F031: lib/tddloop.py::handoff_lines・lib/tddloop.py::current_lines（新しい）
- fix.md F032: workflows/fix/works-factory-fix.yaml::tdd-loop（`fresh_context: false`、役 `tdd`（続き）と `tdd-new`（`context: fresh`）を tdd-prep の `new_unit` で `when:` で振り分ける）、lib/tddloop.py::prep（new_unit）、workflows/fix/scripts/tdd_step.py::read_reply（#121）
- fix.md F033: workflows/fix/works-factory-fix.yaml::tdd（`skills: [test-driven-development]`）、lib/tddloop.py::prep（`seat.section("tdd")`・`raise Broken("TDD の輪の座を組めない…")`）
- fix.md F034: lib/tddloop.py::step（`writes.check(..., tdd-<k>/writes-log.jsonl)`）。PR #178 の前は本物の run に記録を書く物が無く `writes.NO_RECORD` で通った（段 1b の U6 の決めで、記録は Archon の出来事だけでは足りずフックが要ると分かった。書き込みの記録のフックは PR #178 で `bin/_lib/record-write.py` に戻った）。修正役の側の代わりの縛り（lib/fixboard.py::undeclared_writes）は TDD のループが書いた物を求めない（#94 本文の U6 のセクション）
- fix.md F035: lib/tddloop.py::prep・lib/tddloop.py::step、workflows/fix/scripts/tdd_step.py::main
- fix.md F036: lib/tddloop.py::flush_unsent、workflows/fix/scripts/tdd_step.py::main
- fix.md F037: lib/fixgates.py::problems・lib/fixgates.py::_red_green、lib/fixboard.py::accept_reply（`note("gates", …)`）
- fix.md F038: lib/fixgates.py::_red_tree_probs、lib/tddloop.py::red_rerun
- fix.md F039: lib/fixgates.py::_test_edits・lib/fixgates.py::overflow_asks
- fix.md F040: lib/fixgates.py::NO_SUITE・lib/fixgates.py::skipped
- fix.md F041: lib/fixboard.py::gates_trace（lib/fixgates.py::unchecked を lib/fixgates.py::SKIPPED_OP の行に）→ lib/fixboard.py::accept_trace_rows → accept-trace.json → lib/fixbeside.py::gates_lines（受け付け N 回・理由）
- fix.md F042: lib/fixgates.py::_record（doc を作り直してから `doc.get("guards")` を読むので、前の回の guards が落ちる。#97）
- fix.md F043: lib/fixgates.py::_base_cache（置き場ごと。2 回目の include は `fix/refix-run/` なので 1 回目の控えを読まない）
- fix.md F044: lib/fixgates.py::problems（lib/conflict.py::second_pass で裁定の範囲を引く）。2 回目の段の置き場と組の子の置き場に 1 回目の裁定と AMENDED の行が写る（L-W18）ので、メイングラフの上でも second_pass が真
- fix.md F045: 共有ボード・accept-last.json・包みが無い（lib/tests/test_blk_fix_tdd.py::TddloopSeamsGoneCase）。入力は始めの記録（workflows/line/scripts/start.py::raw_inputs・workflows/line/scripts/start.py::start の `tdd_suite`・`test_cmd`）と lib/fixboard.py::unit_depths が持つ。会話の切り替えは F032
- fix.md F100: lib/factchecks.py::precheck・lib/factchecks.py::main
- fix.md F101: lib/fixboard.py::accept_reply（文 lib/fixboard.py::CONSULT_SPENT）
- fix.md F102: lib/writes.py::check（記録の口は残る）と lib/factchecks.py::check_writes。記録を書く包みは PR #178 で `bin/_lib/record-write.py` に戻った（それまでは無かった）
- fix.md F103: lib/fixboard.py::undeclared_writes、lib/fixboard.py::accept_reply が NO_RECORD の時に呼ぶ
- fix.md F104: lib/factchecks.py::check_writes（控えの bash_writes を足す口は #121 F136 で消した）
- fix.md F105: lib/fixboard.py::check_unique_units・lib/fixboard.py::check_opened_units・lib/fixboard.py::check_excused_units、lib/fixboard.py::accept_reply
- fix.md F106: lib/fixboard.py::accept_reply（最後の回に写しでない拒否を先に単位へ結び、止める単位が残らなければ外れた単位の行を changes・not_done から外して写しの照らしを当て直し、trace に `ABSORBED_OP` = `fix_excused_dropped`。`parking.park_owed` は写しの拒否が残る時だけ）（#121）
- fix.md F107: lib/fixboard.py::check_pack_copy・lib/fixboard.py::skip_digests・lib/fixboard.py::record_skipped（確かめ pack。除くパスの頭は accept_reply の skip で受け、段の頭の姿は workflows/fix/scripts/fix_prep.py・workflows/fix/scripts/fix_ruled_prep.py が skip-before.json に控える）（#121）
- fix.md F108: lib/planscope.py::check、lib/factchecks.py::check_plan_scope、lib/fixboard.py::accept_reply
- fix.md F109: lib/planrange.py::with_agreed・lib/planrange.py::check_paths、lib/planscope.py
- fix.md F110: lib/fixboard.py::settle_overflow、lib/fixboard.py::accept_reply、lib/fixboard.py::overflow_trace
- fix.md F111: lib/fixboard.py::accept_reply（recount.accept_fix を `commit=not found` で先に当て、拒否を copy の行に積む）
- fix.md F112: lib/fixboard.py::closure_reply（lib/unitrows.py::build）、lib/fixboard.py::accept_reply で `querytest.save_closure`
- fix.md F113: lib/fixboard.py::closure_reply が同じ固めた版で数え直して zero を作り、lib/recount.py::recount_problems へ zero_keys で渡す
- fix.md F114: lib/recount.py::recount_problems
- fix.md F115: lib/recount.py::_reply_shape_problems（`judge_accept.SILENT_STATUS`）
- fix.md F116: lib/recount.py::_after_problems
- fix.md F117: lib/recount.py::_reply_shape_problems
- fix.md F118: lib/recount.py::_reply_shape_problems
- fix.md F119: lib/recount.py::_reply_shape_problems
- fix.md F120: lib/recount.py::_reply_shape_problems（判定の precedents は fixboard が置き場の judgment.json から渡す。lib/fixboard.py::accept_reply）
- fix.md F121: lib/recount.py::_reply_shape_problems
- fix.md F122: lib/recount.py::recount_problems
- fix.md F123: lib/recount.py::recount_problems
- fix.md F124: lib/recount.py::recount_problems
- fix.md F125: lib/recount.py::recount_problems
- fix.md F126: lib/recount.py::recount_problems
- fix.md F127: lib/recount.py::COUNT_BUDGET・lib/recount.py::_run_query（count-cache.json・count-budget.json）
- fix.md F128: lib/recount.py::_after_problems（judge_accept._cite_errors）
- fix.md F129: lib/recount.py::_added_md_links・lib/recount.py::_walk_as_written・lib/recount.py::md_link_errors、lib/recount.py::_after_problems
- fix.md F130: fix の入力 plan_review → prep が置き場の p2.plan_review.json に写す（組の子は fixboard.ADOPTED で写す）→ 受け付け lib/fixboard.py::accept_reply が lib/fixboard.py::plan_face_errors を照らす（検査の id plan_faces）。指示書 workflows/fix/commands/fix-rules/direct.md は元の字（10・95 行を戻した）
- fix.md F131: lib/fixboard.py::fix_reject_rows・lib/fixboard.py::fix_reject_text
- fix.md F132: lib/fixboard.py::rejects_file・lib/fixboard.py::write_reject・lib/fixboard.py::accept_out・lib/rolekit.py::REJECT_LINE
- fix.md F133: lib/fixboard.py::last_settle・lib/fixboard.py::park_units・lib/fixboard.py::accept_reply
- fix.md F134: lib/fixboard.py::accept_reply（park_owed、残れば `NOT_SETTLED` lib/fixboard.py::NOT_SETTLED で拒否のまま done）
- fix.md F135: workflows/fix/scripts/fix_accept.py（入力 consulted）、workflows/fix/works-factory-fix.yaml::fix-accept の `consulted`
- fix.md F136: 無し（#121 で消した: lib/conflict.py の held_reply・accepted_units・held_writes・with_held ほかと、読む側 fixboard.fix_duty・fix_reply・fixrules.fix_parts・factchecks.check_writes）
- fix.md F137: lib/fixboard.py::objection（組の子の結果の objection と返答の rejudge_requested を重ねずにつなぐ）→ 出力の objection
- fix.md F138: lib/fixboard.py::changed_marks、workflows/fix/scripts/collect.py::CHANGED_MARKS・workflows/fix/scripts/collect.py::fields
- fix.md F139: workflows/fix/commands/fix-rules/direct.md（申告だけ）。fix の中で止める道は無い。出力の changed に載る（F138）。メイングラフが読むかはメイングラフの範囲
- fix.md F140: lib/fixrules.py::prep・lib/fixrules.py::start_lines、lib/rulebook.py
- fix.md F141: lib/planbrief.py::cut（置き場の briefs.json）
- fix.md F142: workflows/fix/scripts/fix_prep.py、workflows/fix/works-factory-fix.yaml::fixer の `when: "$fix-prep.output.go == true"`
- fix.md F143: lib/fixrules.py::g1_values（下請けのファイルの名 `G1_IMPL`・`G1_REVIEW`）と lib/fixrules.py::prep（ループが緑にしていない単位が在れば seat.g1_section）、lib/seat.py::g1_prompt・lib/seat.py::g1_section・lib/seat.py::g1_diff_cmd。修正役に Agent の道具（workflows/fix/works-factory-fix.yaml::fixer の allowed_tools）
- fix.md F144: lib/seat.py（spseam の写し。lib は bin を import しない）、bin/_lib/spseam.py
- fix.md F145: workflows/fix/works-factory-fix.yaml::tdd・workflows/fix/works-factory-fix.yaml::refix・workflows/fix/works-factory-fix.yaml::refix2 の `skills:`
- fix.md F146: workflows/fix/works-factory-fix.yaml の各役
- fix.md F147: lib/fixboard.py::collect_reads・lib/fixboard.py::read_stages（lib/reads.collect の上。修正役 fix と裁定の後の修正役 fix-ruled の段ごとに、指示書・判定の写し・brief を渡したパスにし、段の頭の印から後の、指示書を読んだ session の行で切る）、workflows/fix/scripts/fix_reads.py（ノード fix-reads。受け付けの条件にしない。出力ノードに結ばない。落ちない）
- fix.md F148: 無し（`changes.json` を書く lib/fixboard.py の `collect` と lib/recount.py の `CHANGES_FILE` は届かず読み手も無かったので #232 で消した）。受け付けた changes は workflows/fix/scripts/fix_accept.py::finish が置き場の fix-reply.json（lib/fixboard.py::FIX_REPLY_FILE）に、単位ごとの件数は lib/recount.py::accept_fix が coverage-after.json（lib/recount.py::COVERAGE_FILE）に書く。空の changes を止めるのは workflows/fix/scripts/assert_changed.py::main → lib/fixboard.py::changed_problem・lib/fixboard.py::nothing_owed_but_excused
- fix.md F149: workflows/fix/works-factory-fix.yaml::fix-ruled の `&fix_reply`（fixer と fix-ruled が共有）
- fix.md F200: lib/fixboard.py::take_conflicts、lib/conflict.py::park
- fix.md F201: lib/conflict.py::_kind_problem
- fix.md F202: lib/conflict.py::_entry_problems（lib/conflict.py::MIN_CITES の文ほか）、lib/fixboard.py::take_conflicts
- fix.md F203: lib/conflict.py::_entry_problems、lib/fixboard.py::take_conflicts（both）
- fix.md F204: lib/conflict.py::brief_cite_problem・lib/conflict.py::_brief_problem
- fix.md F205: lib/fixboard.py::judge_query（置き場の judgment.json の units から querytest.judge_hits）を `take_conflicts` が `try_query` に渡す。judgment.json が読めなければ query の申し出ごとに `JUDGE_UNREAD` で拒む（#121）
- fix.md F206: lib/conflict.py::park、lib/fixboard.py::take_conflicts（held_by_rulings で先に外す）
- fix.md F207: lib/fixboard.py::take_conflicts、lib/fixboard.py::accept_reply
- fix.md F208: workflows/fix/scripts/conflict_check.py、lib/fixboard.py::cited_rows、YAML の rule-loop の `when: conflict-check.output.go`
- fix.md F209: lib/ruling.py::limit_problem・lib/ruling.py::grounds_problems・lib/ruling.py::problems、workflows/fix/commands/fix-rules/ruler.md、YAML のノード ruler（読むだけの道具）
- fix.md F210: lib/ruling.py::READONLY・lib/ruling.py::accept_rule（rule-tree.json と比べる）
- fix.md F211: lib/ruling.py::GIVE_UP_AFTER・lib/ruling.py::GIVE_UP_TEXT・lib/ruling.py::accept_rule
- fix.md F212: lib/ruling.py::query_problems
- fix.md F213: lib/conflict.py::apply_rulings、lib/ruling.py::plan_item_units・lib/ruling.py::plan_item_fix_problems、lib/ruling.py::accept_rule（中の `stored`）
- fix.md F214: lib/conflict.py::set_replan
- fix.md F215: lib/fixboard.py::replan_items、workflows/fix/scripts/collect.py、workflows/line/works-factory-line.yaml::replan（replan → answer-replan → refix-run の include に only_items）
- fix.md F216: fix の入力 prior_conflicts（メイングラフの refix-run に `$fix.output.conflicts`）→ prep の fixboard.adopt_prior_pass → conflict.adopt_prior（行を印 prior_pass つきで写し、直す項目の待つ行を AMENDED へ）。2 回目の段で新しく裁いた fix_plan_item の行に LATE_REPLAN_PROMISE が出て、出力ノード collect が段を抜ける時に replan.close で諦めた行にする。組の子の結果と出力 replan_items はこの段の行だけ（conflict.this_pass）。park は写した行の id と重ねない
- fix.md F217: workflows/fix/scripts/fix_ruled_prep.py・workflows/fix/scripts/fix_ruled_accept.py、lib/fixboard.py::ruled_reply_line・lib/fixboard.py::ruled_owed・lib/fixboard.py::ruled_states
- fix.md F218: 新しい会話。workflows/fix/works-factory-fix.yaml::fix-ruled は前の会話を継がず、保存した返答（fix-reply.json）と裁定の文を読む（lib/fixboard.py::ruled_reply_line）
- fix.md F219: lib/consult.py::screen・lib/consult.py::question、lib/fixboard.py::consult_ask、workflows/fix/scripts/consult_check.py
- fix.md F220: lib/consult.py::judge・lib/consult.py::settle、lib/conflict.py::agreed・lib/conflict.py::plan_asks
- fix.md F221: lib/consult.py
- fix.md F222: 新しい会話。workflows/fix/works-factory-fix.yaml::consult-answer は修正案（p2.fix_plan.json）と波及の一覧を読む読むだけの役（description「修正案と波及を読む新しい会話」）
- fix.md F223: lib/consult.py::gate_notes・lib/consult.py::gate_asks、lib/fixboard.py::gate_items
- fix.md F224: lib/fixboard.py::owed_units_but_asked・lib/fixboard.py::fix_duty・lib/fixboard.py::gate_asks・lib/fixboard.py::write_notes
- fix.md F225: メイングラフ: workflows/line/scripts/ask_before_fix.py::ask が承認ノードに載せた項目を asked で返し、workflows/line/scripts/before_fix_answer.py::take（gate_answer と同じ読み）が答え {decision, text, asked} に付けて fix の answers に渡す。fix の側は lib/gatemarks.py::gate_items
- fix.md F226: lib/conflict.py::held_by_rulings、lib/fixboard.py::fix_duty
- fix.md F227: lib/conflict.py::write_rulings
- fix.md F228: lib/conflict.py::test_permits・lib/conflict.py::fields_broken・lib/conflict.py::frozen_fields
- fix.md F231: lib/fixboard.py::fix_duty、lib/conflict.py::asked
- fix.md F232: 無し（b95b488 で外した）。組ごとの子の run が置き場を分けるので同じ置き場に同時に書くノードが無い
- fix.md F233: lib/outcome.py::conflict_counts（conflict の counts・kind_counts の写し）、lib/runreport.py::_conflict_line
- fix.md F300: lib/refix.py::_cut_delta・lib/refix.py::cut、workflows/fix/scripts/delta_cut.py::main
- fix.md F301: lib/refix.py::cut
- fix.md F302: workflows/fix/scripts/delta_cut.py::main・workflows/fix/scripts/refix_prep.py::main（n=1・2）が lib/fixboard.py::plan_review_file（置き場の p2.plan_review.json。無ければ None）を渡す
- fix.md F303: lib/fixboard.py::delta_review_problems、workflows/fix/scripts/delta_accept.py::main・workflows/fix/scripts/review2_accept.py::main
- fix.md F304: lib/fixboard.py::HUMAN_FACE_KINDS・lib/fixboard.py::PLAN_ONLY_FACE_KINDS・lib/fixboard.py::delta_review_problems
- fix.md F305: lib/fixboard.py::tree_moved_since・lib/fixboard.py::take、lib/refix.py::accept_review
- fix.md F306: lib/deltamarks.py、lib/refix.py::accept_review、YAML の delta-review の output_format の required（workflows/fix/works-factory-fix.yaml::delta-review）
- fix.md F307: lib/fixboard.py::_owed_rows、workflows/fix/scripts/refix_prep.py（go: false）
- fix.md F308: lib/fixboard.py::delta_fix_problems、workflows/fix/scripts/refix_accept.py::main（n=1・2）
- fix.md F309: lib/refix.py::accept_fix（planrange.check_paths）
- fix.md F310: lib/refix.py::accept_fix（writes.check）、lib/fixboard.py::undeclared_refix、workflows/fix/scripts/refix_accept.py（段の頭の木 refix1-head.json）
- fix.md F311: lib/holeties.py、lib/fixboard.py::tie_items・lib/fixboard.py::hole_ties・lib/fixboard.py::prep_fix
- fix.md F312: fix の diff の隣の delta-holes.json（lib/fixboard.py::hole_ties の名札と手直しの handled。lib/fixbeside.py）→ lib/fixbeside.py::branch_rows（最後の承認ノードの差分の審査の行・報告の人が決めることのセクション）
- fix.md F313: workflows/fix/scripts/cut2.py::main、lib/refix.py::cut の n=2、lib/fixboard.py::claimed_closed（2 回目の claimed_closed は 1 回目の手直しの fixed）
- fix.md F314: lib/refix.py::passes（1・2 だけ）、workflows/fix/scripts/refix_prep.py::main（n=2）
- fix.md F315: lib/fixboard.py::accept_out、YAML の delta-loop・refix-loop・review2-loop・refix2-loop の `max_iterations: 3`
- fix.md F316: lib/fixboard.py::delta_review、workflows/fix/scripts/collect.py
- fix.md F317: workflows/fix/scripts/collect.py の組の形、YAML の delta-cut・lens-collect・delta-loop の `when: "$route.output.group == false ..."`
- fix.md F318: workflows/fix/scripts/delta_cut.py::main、lib/depth.py::skip_reason
- fix.md F319: lib/fixboard.py::depth_signals・lib/fixboard.py::redepth、workflows/fix/scripts/delta_cut.py::main
- fix.md F320: 報告（lib/runreport.py::_entry_lines）は計画の深さ（plan の出力 depth）だけを出す。fix の置き場の `depth-raised.json`・`delta/skipped.json` は出力に載らない（出力は delta_review {0, true} だけ）。メイングラフの redepth（workflows/line/scripts/redepth.py）も同じ信号で上げ直すが、fix の中の上げ直しとは別に数える
- fix.md F321: lib/fixboard.py::delta_review_due、workflows/fix/scripts/delta_cut.py（修正前の版からの累積差分が空（.archon/ の下を除く）で 1 回目の claimed_closed も無ければ go: false、訳は delta/skipped.json）（#121）
- fix.md F322: lib/refix.py::_drop_stale
- fix.md F323: lib/refix.py::cut（conflict.fields_broken）
- fix.md F324: lib/refix.py::cut（seat.section）、workflows/fix/commands/delta-review.md の seat_file の行
- fix.md F325: lib/fixboard.py::refix_prompt、lib/refixrules.py、workflows/fix/commands/fix-rules/refix.md
- fix.md F326: lib/fixboard.py::lens_route、lib/lenses.py::_any_change・lib/lenses.py::LENSES（route は変更が在るか）・lib/lenses.py::render、workflows/fix/scripts/lens_prep.py
- fix.md F327: lib/lenses.py::collect、lib/lens.py、lib/fixboard.py::brief_lens、workflows/fix/scripts/lens_collect.py
- fix.md F328: diff の隣の `lenses.json`（`{collector: {ok, reason}}`）: lib/fixboard.py::lens_collector、workflows/fix/scripts/lens_collect.py（落ちる時も ok: false と理由を書く）・workflows/fix/scripts/delta_cut.py::main・workflows/fix/scripts/delta_cut.py::no_go（前の試みの物を消し、審査を回さない時は ok: true と訳）・workflows/fix/scripts/collect.py::lenses_file（行が無ければ ok: false。stdlib だけで書く）（#121）
- fix.md F329: fix の diff の隣の lenses.json（lens.summary と report_lines。lib/fixbeside.py）→ lib/fixbeside.py::always_rows・lib/fixbeside.py::lens_lines（未確認のレンズのセクション）・lib/fixbeside.py::next_items（再実行の要あり）
- fix.md F330: fix の範囲の外。works-factory では bin/_lib/toolset.py・bin/_lib/COPIED_FROM.changemap が台帳を持つ
- fix.md F400: lib/fixboard.py::fix_groups、lib/lanekit.py::groups、workflows/fix/scripts/prep.py
- fix.md F401: lib/fixboard.py::owed_keys
- fix.md F402: lib/fixboard.py::fix_groups の only_items、workflows/.shared/boundary.py::include_name・workflows/.shared/boundary.py::place
- fix.md F403: lib/fixboard.py::parallel、workflows/fix/works-factory-fix.yaml::groups-par（`when: "$prep.output.par == true"`）・workflows/fix/works-factory-fix.yaml::groups-seq
- fix.md F404: workflows/fix/works-factory-fix.yaml::groups-par の `max_parallel: 5`、lib/lanekit.py（列と錠の関数は無い）
- fix.md F405: lib/groups.py::adopt_tree（git read-tree -u --reset）、workflows/fix/scripts/group_start.py、YAML groups-par の `from_tree: $prep.output.start_tree`
- fix.md F406: lib/fixboard.py::adopt_inputs、workflows/fix/scripts/group_start.py
- fix.md F407: lib/fixboard.py::record_base_rev・lib/fixboard.py::base_rev_of
- fix.md F408: lib/fixboard.py::group_result、workflows/fix/scripts/group_end.py
- fix.md F409: lib/fixboard.py::join_group、workflows/fix/scripts/join.py、lib/unittrees.py
- fix.md F410: lib/fixboard.py::join_group、lib/lanekit.py::merge_in_order（workflows/fix/scripts/join.py::main が呼ぶ）
- fix.md F411: lib/fixboard.py::rerun_problem・lib/fixboard.py::rerun_cmd、workflows/fix/scripts/join.py::main（中の `merge_one`。名指しの無い組も変えたファイルに当たる試験を走らせ、前に戻せた組の名指しと重なりのファイルから届く試験を足し、子の関門が on で軽量でない単位が在れば test_cmd を 1 回）（#121）
- fix.md F412: lib/fixboard.py::rerun_problem（重なりの在る組の赤を「意味の食い違い」SEMANTIC_CLASH と名指す）、workflows/fix/scripts/join.py（#121）
- fix.md F413: workflows/fix/scripts/join.py::result_of と workflows/fix/scripts/join.py::main（結果の無い組で落ちる）、lib/fixboard.py::join_rows（NO_RESULT）
- fix.md F414: lib/fixboard.py::drop_unreturned、workflows/fix/scripts/group_start.py::main
- fix.md F415: lib/fixboard.py::adopt_tdd_states・lib/fixboard.py::ruled_states、lib/baseline_red.py::exe_path
- fix.md F416: lib/fixboard.py::tdd_units、workflows/fix/scripts/tdd_unit.py、YAML ノード tdd-unit
- fix.md F417: lib/leftovers.py::record_ignored、workflows/fix/scripts/prep.py（fix-ignored-before.json）
- fix.md F418: lib/leftovers.py::remove_new_ignored（skip）、workflows/fix/scripts/clean.py
- fix.md F419: workflows/fix/scripts/assert_changed.py、lib/fixboard.py::touched_since・lib/fixboard.py::declared_files・lib/fixboard.py::changed_problem
- fix.md F420: workflows/fix/works-factory-fix.yaml::fix（ノード fix）・YAML の頭の `returns: fix`・`outcome_field: done`
- fix.md F421: workflows/fix/scripts/collect.py（頭の説明の `この節は落ちない` と `if __name__ == "__main__":` の BaseException の捕まえ）・workflows/fix/scripts/collect.py::fallback・workflows/fix/scripts/collect.py::main、YAML ノード fix の `trigger_rule: all_done`
- fix.md F422: lib/fixboard.py::join_rows・lib/fixboard.py::with_ruled、workflows/fix/scripts/collect.py
- fix.md F423: workflows/fix/scripts/collect.py、lib/fixboard.py::delta_review
- fix.md F424: lib/fixboard.py::run_diff、workflows/fix/scripts/collect.py の diff_pointer
- fix.md F425: workflows/fix/scripts/collect.py::fields、lib/fixboard.py::replan_items
- fix.md F426: workflows/line/scripts/ask_final.py::asked_conflicts（fix と refix-run の conflicts.json を lib/conflict.py::human_lines で読む）・workflows/line/scripts/ask_final.py::needs の must・workflows/line/scripts/ask_final.py::conflict_section。fix の出力の約束は変えない（メイングラフが conflicts.json を読む側を採った）
- fix.md F427: fix の diff の隣の handoffs.json（lib/fixbeside.py。子の結果の handoffs と裁定の後の返答から）→ 最後の承認ノードの開ける理由とセクション・報告の冒頭
- fix.md F428: fix の diff の隣の closure.json（子の結果の closure と親の fix-unit-rows.json。lib/fixbeside.py）→ 最後の承認ノードの開ける理由とセクション
- fix.md F429: lib/fixboard.py::allowed_test_rows・lib/fixboard.py::ALLOWED_SOURCES（許しの id と出どころ）を collect が diff の隣の `allowed-tests.json`（`[{path, permit, source}]`。止めの道と lib の無い道でも `[]`）に置く。出力の allowed_test_changes はパスのまま（#121）
- fix.md F430: fix の外（メイングラフの merge-seal の protected_hits。workflows/line/scripts/ask_final.py::needs・workflows/line/scripts/ask_final.py::protected）
- fix.md F431: 出力の units（結末と理由）と型つきの成果物 tdd-unit だけ。前後の件数（coverage-after.json）と閉鎖の表（fix-unit-rows.json）は組の子の置き場に残り、出力に載らない
- fix.md F432: workflows/line/scripts/fixed.py::fixed・workflows/line/scripts/fixed.py::FIELDS・workflows/line/scripts/fixed.py::union
- fix.md F433: 無し。子の worktree と枝は残り、run の後に人が `bin/works-factory isolation cleanup`（Archon の archon isolation cleanup）で消す（PR #94「並べた run の後の片付け」）
- fix.md F434: workflows/fix/fixtures/ の 4 本
- gaps-fix.md F014: lib/fixboard.py::accept_reply が `tddloop.selected_problems` の知らせを `tests_trace` で diff の隣の `accept-trace.json`（受け付けの回ごとの行 `{op: fix_tests_selected, node, pass, attempt, note, ci_left, final_left, final_far}`）に積む。組の子の行は group-end が組の結果の `accept_trace` に `group_id` つきで載せ、親の collect が親の行と合わせて親の diff の隣の `accept-trace.json` に置く（止めの道・lib の無い道は無ければ `[]`）（#121）
- gaps-fix.md F016: lib/tddloop.py::frozen_problems、lib/factchecks.py::check_frozen、lib/fixboard.py::accept_reply（`note("frozen", factchecks.check_frozen(...))`）
- gaps-fix.md F022: lib/conflict.py::TDD_SOURCE・lib/conflict.py::GAVE_UP_SOURCE（元と同じ定数）、lib/tddloop.py::step
- gaps-fix.md F026: lib/baseline_red.py::lowered・lib/baseline_red.py::nice19（子の優先度を nice -n 19 と同じだけ下げる preexec の 1 か所。argv・環境・作業の場は変えないので、起こせるかの証明は tree_run.run が走らせる時と同じ形で行う。下げられない環境は下げずに起こしログの頭に NO_NICE の 1 行）を `run_suite`・lib/tddloop.py::_cmd_material・lib/declared_checks.py::local_checks_material が呼ぶ（#121）
- gaps-fix.md F028: lib/tddloop.py::MAX_ITERATIONS、workflows/fix/works-factory-fix.yaml::tdd-loop（`max_iterations: 40`・`until_bash: done=$tdd-step.output.done`）
- gaps-fix.md F032: workflows/fix/works-factory-fix.yaml の tdd-loop（`fresh_context: false`、役 `tdd`（続き）と `tdd-new`（`context: fresh`）を tdd-prep の `new_unit` で `when:` で振り分ける）、lib/tddloop.py::prep（new_unit）、workflows/fix/scripts/tdd_step.py::read_reply（#121）
- gaps-fix.md F033: workflows/fix/works-factory-fix.yaml::tdd（`skills: [test-driven-development]`）、lib/tddloop.py::prep（`seat.section("tdd")`・`raise Broken("TDD の輪の座を組めない…")`）
- gaps-fix.md F101: lib/fixboard.py::accept_reply（文 lib/fixboard.py::CONSULT_SPENT）
- gaps-fix.md F105: lib/fixboard.py::check_unique_units・lib/fixboard.py::check_opened_units・lib/fixboard.py::check_excused_units、lib/fixboard.py::accept_reply
- gaps-fix.md F106: lib/fixboard.py::accept_reply（最後の回に写しでない拒否を先に単位へ結び、止める単位が残らなければ外れた単位の行を changes・not_done から外して写しの照らしを当て直し、trace に `ABSORBED_OP` = `fix_excused_dropped`。`parking.park_owed` は写しの拒否が残る時だけ）（#121）
- gaps-fix.md F107: lib/fixboard.py::check_pack_copy・lib/fixboard.py::skip_digests・lib/fixboard.py::record_skipped（確かめ pack。除くパスの頭は accept_reply の skip で受け、段の頭の姿は fix_prep.py・fix_ruled_prep.py が skip-before.json に控える）（#121）
- gaps-fix.md F111: lib/fixboard.py::accept_reply（recount.accept_fix を `commit=not found` で先に当て、拒否を copy の行に積む）
- gaps-fix.md F113: lib/fixboard.py::closure_reply が同じ固めた版で数え直して zero を作り、lib/recount.py::recount_problems 前後へ zero_keys で渡す
- gaps-fix.md F117: lib/recount.py::_reply_shape_problems
- gaps-fix.md F120: lib/recount.py::_reply_shape_problems（判定の precedents は fixboard が置き場の judgment.json から渡す。lib/fixboard.py::accept_reply）
- gaps-fix.md F127: lib/recount.py::COUNT_BUDGET・lib/recount.py::_run_query（count-cache.json・count-budget.json）
- gaps-fix.md F129: lib/recount.py::_added_md_links・lib/recount.py::_walk_as_written・lib/recount.py::md_link_errors、lib/recount.py::_after_problems
- gaps-fix.md F134: lib/fixboard.py::accept_reply（park_owed、残れば lib/fixboard.py::NOT_SETTLED で拒否のまま done）
- gaps-fix.md F136: 無し（#121 で消した: lib/conflict.py の held_reply・accepted_units・held_writes・with_held ほかと、読む側 fixboard.fix_duty・fix_reply・fixrules.fix_parts・factchecks.check_writes）
- gaps-fix.md F138: lib/fixboard.py::changed_marks、workflows/fix/scripts/collect.py::CHANGED_MARKS・workflows/fix/scripts/collect.py::fields
- gaps-fix.md F147: lib/fixboard.py::collect_reads・lib/fixboard.py::read_stages（lib/reads.collect の上。修正役 fix と裁定の後の修正役 fix-ruled の段ごとに、指示書・判定の写し・brief を渡したパスにし、段の頭の印から後の、指示書を読んだ session の行で切る）、workflows/fix/scripts/fix_reads.py（ノード fix-reads。受け付けの条件にしない。出力ノードに結ばない。落ちない）
- gaps-fix.md F149: workflows/fix/works-factory-fix.yaml::fix-ruled の output_format `&fix_reply`（workflows/fix/works-factory-fix.yaml::fixer と共有）
- gaps-fix.md F202: lib/conflict.py::_entry_problems（lib/conflict.py::MIN_CITES の文ほか）、lib/fixboard.py::take_conflicts
- gaps-fix.md F203: lib/conflict.py::_entry_problems、lib/fixboard.py::take_conflicts（both）
- gaps-fix.md F205: lib/fixboard.py::judge_query（置き場の judgment.json の units から querytest.judge_hits）を `take_conflicts` が `try_query` に渡す。judgment.json が読めなければ query の申し出ごとに `JUDGE_UNREAD` で拒む（#121）
- gaps-fix.md F206: lib/conflict.py::park、lib/fixboard.py::take_conflicts（held_by_rulings で先に外す）
- gaps-fix.md F207: lib/fixboard.py::take_conflicts、lib/fixboard.py::accept_reply
- gaps-fix.md F208: workflows/fix/scripts/conflict_check.py、lib/fixboard.py::cited_rows、YAML の rule-loop の `when: conflict-check.output.go`
- gaps-fix.md F212: lib/ruling.py::query_problems
- gaps-fix.md F213: lib/conflict.py::apply_rulings、lib/ruling.py::plan_item_units・lib/ruling.py::plan_item_fix_problems、lib/ruling.py::accept_rule（中の `stored`）
- gaps-fix.md F304: lib/fixboard.py::HUMAN_FACE_KINDS・lib/fixboard.py::PLAN_ONLY_FACE_KINDS・lib/fixboard.py::delta_review_problems
- gaps-fix.md F306: lib/deltamarks.py、lib/refix.py::accept_review、YAML の delta-review の output_format の required（workflows/fix/works-factory-fix.yaml::delta-review）
- gaps-fix.md F313: workflows/fix/scripts/cut2.py::main、lib/refix.py::cut の n=2、lib/fixboard.py::claimed_closed（2 回目の claimed_closed は 1 回目の手直しの fixed）
- gaps-fix.md F317: workflows/fix/scripts/collect.py の組の形、YAML の delta-cut・lens-collect・delta-loop の `when: "$route.output.group == false ..."`
- gaps-fix.md F319: lib/fixboard.py::depth_signals・lib/fixboard.py::redepth、workflows/fix/scripts/delta_cut.py::main
- gaps-fix.md F321: lib/fixboard.py::delta_review_due、workflows/fix/scripts/delta_cut.py（修正前の版からの累積差分が空（.archon/ の下を除く）で 1 回目の claimed_closed も無ければ go: false、訳は delta/skipped.json）（#121）
- gaps-fix.md F324: lib/refix.py::cut（seat.section）、workflows/fix/commands/delta-review.md の seat_file の行
- gaps-fix.md F325: lib/fixboard.py::refix_prompt、lib/refixrules.py、workflows/fix/commands/fix-rules/refix.md
- gaps-fix.md F328: diff の隣の `lenses.json`（`{collector: {ok, reason}}`）: lib/fixboard.py::lens_collector、workflows/fix/scripts/lens_collect.py（落ちる時も ok: false と理由を書く）・delta_cut.py（前の試みの物を消し、審査を回さない時は ok: true と訳）・collect.py `lenses_file`（行が無ければ ok: false。stdlib だけで書く）（#121）
- gaps-fix.md F411: lib/fixboard.py::rerun_problem・lib/fixboard.py::rerun_cmd、workflows/fix/scripts/join.py::main（中の `merge_one`。名指しの無い組も変えたファイルに当たる試験を走らせ、前に戻せた組の名指しと重なりのファイルから届く試験を足し、子の関門が on で軽量でない単位が在れば test_cmd を 1 回）（#121）
- gaps-fix.md F412: lib/fixboard.py::rerun_problem（重なりの在る組の赤を「意味の食い違い」SEMANTIC_CLASH と名指す）、workflows/fix/scripts/join.py（#121）
- gaps-fix.md F418: lib/leftovers.py::remove_new_ignored（skip）、workflows/fix/scripts/clean.py
- gaps-fix.md F419: workflows/fix/scripts/assert_changed.py、lib/fixboard.py::touched_since・lib/fixboard.py::declared_files・lib/fixboard.py::changed_problem
- gaps-fix.md F424: lib/fixboard.py::run_diff、workflows/fix/scripts/collect.py の diff_pointer
- gaps-fix.md F425: workflows/fix/scripts/collect.py::fields、lib/fixboard.py::replan_items
- gaps-fix.md F429: lib/fixboard.py::allowed_test_rows・lib/fixboard.py::ALLOWED_SOURCES（許しの id と出どころ）を collect が diff の隣の `allowed-tests.json`（`[{path, permit, source}]`。止めの道と lib の無い道でも `[]`）に置く。出力の allowed_test_changes はパスのまま（#121）
- gaps-plan.md P005: lib/planfile.py::fix_plan_covers_units
- gaps-plan.md P007: lib/planfile.py::named（整数だけ戻す）・lib/planfile.py::fix_plan_covers_units（「写さずに、貼られた単位の no で指せ」）
- gaps-plan.md P008: lib/planfile.py::not_allowed・lib/planfile.py::take_plan（NOT_OWED_REJECT lib/planblk.py::NOT_OWED_REJECT）
- gaps-plan.md P012: lib/planfile.py::take_plan（MALFORMED_REJECT lib/planfile.py::MALFORMED_REJECT）、lib/replan.py::_malformed
- gaps-plan.md P013: lib/planfile.py::take_plan（reasons の並び）
- gaps-plan.md P015: lib/planfile.py::take_plan（RECOMMEND_REJECT lib/planblk.py::RECOMMEND_REJECT）
- gaps-plan.md P022: lib/planmarks.py::_limit・lib/planmarks.py::split
- gaps-plan.md P023: lib/planfile.py::base_test_texts・lib/planfile.py::take_plan（`_trace(BASE_TESTS_UNREAD_OP)`）
- gaps-plan.md P024: lib/planmarks.py::save（trace を渡さないので周のフォルダの trace.jsonl に直に書く）・lib/planfile.py::_save
- gaps-plan.md P025: lib/planfile.py::_save（置けなければ置いた控えを消し、round.json の why に控えの名。出力 halt で plan_accept が拒否に数えずループを止める）（#120）
- gaps-plan.md P027: lib/planfile.py::write_brief（write_brief の structmark.plan_section）
- gaps-plan.md P028: lib/structmark.py::MISSING・lib/structmark.py::plan_section・lib/planfile.py::write_state・lib/planfile.py::write_brief
- gaps-plan.md P031: lib/planfile.py::prescriptions・lib/planfile.py::prescription_section・lib/planfile.py::write_brief
- gaps-plan.md P033: lib/planblk.py::HEAD・lib/planblk.py::head（前提の部品）・lib/planfile.py::write_brief（write_brief が頭に置く）
- gaps-plan.md P034: lib/planfile.py::units_section
- gaps-plan.md P035: lib/planfile.py::REPO_LINE・lib/planfile.py::repo_line・lib/planfile.py::write_brief、lib/boardview.py::open_pass・lib/boardview.py::review_body、lib/startrec.py::read_rev・lib/startrec.py::diff_base（読む版は始めの記録の review_rev、BASE は入口の差分の根 input.base.rev。どちらも無い前の版の控えは base_rev。行は repo_line の 1 か所が描く）
- gaps-plan.md P036: lib/planfile.py::write_brief（`_neighbor(judgment_dir, "pr-excluded.json")`）
- gaps-plan.md P038: lib/planfile.py::lib_section・workflows/plan/scripts/plan_prep.py::main
- gaps-plan.md P042: lib/rolekit.py::lang_line・lib/planfile.py::write_brief
- gaps-plan.md P043: lib/planfile.py::SPEC_HEAD・lib/planfile.py::write_brief
- gaps-plan.md P046: lib/rolekit.py::REJECT_LINE・lib/rolekit.py::reject_file・lib/rolekit.py::compose・lib/planfile.py::write_brief
- gaps-plan.md P049: lib/planfile.py::snap_tree・lib/planfile.py::moved（workflows/plan/scripts/plan_prep.py が plan/r<k>/tree.json を置き、take_plan・take_replan が accept.tree_moved で比べる。拒みの頭は planblk.READONLY_MOVED・NO_TREE）（#120）
- gaps-plan.md P055: lib/planfile.py::ripple_items・lib/ripple.py::build・workflows/plan/scripts/ripple_items.py::main
- gaps-plan.md P056: lib/planfile.py::ripple_units・lib/planfile.py::write_brief・workflows/plan/scripts/ripple_units.py::main（skip_dirs は workflows/.shared/boundary.py::RUNTIME_COPY_DIRS で .archon）
- gaps-plan.md P057: lib/reads.py・lib/planfile.py::collect_reads・workflows/plan/scripts/plan_reads.py（ノード plan-reads）・bin/_lib/record-read.py・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- gaps-plan.md P059: lib/planfile.py::collect・lib/planfile.py::owed_order・workflows/plan/scripts/plan_collect.py::collected
- gaps-plan.md P064: lib/planfile.py::measure（design.jsonl の置き直し）・lib/eye.py::reset（eye.json を消す）
- gaps-plan.md P065: lib/context.py::concepts・lib/context.py::find（字のまま）
- gaps-plan.md P066: lib/context.py::find・lib/context.py::concepts
- gaps-plan.md P067: lib/context.py::rules・lib/planfile.py::measure（policy_path は start.policy_md。workflows/plan/scripts/structure_measure.py::main）
- gaps-plan.md P068: lib/planfile.py::measure（`eye.stamp`）・lib/eye.py::stamp
- gaps-plan.md P069: lib/eye.py::due・workflows/plan/works-factory-plan.yaml::structure-eye-loop の `when: "$structure-measure.output.eye == true"`
- gaps-plan.md P072: lib/eye.py::render（字のまま）
- gaps-plan.md P073: lib/eye.py::FORMS（試験 lib/tests/test_structure_eye.py が今の works の設計書の一覧を字で持って照らす）（#120）
- gaps-plan.md P076: workflows/plan/works-factory-plan.yaml::structure-eye・workflows/plan/commands/structure-eye.md（元と字のまま）
- gaps-plan.md P080: lib/eye.py::problems（route の照らし）
- gaps-plan.md P081: lib/eye.py::accept
- gaps-plan.md P083: lib/planfile.py::_outcome・lib/planfile.py::write_state・workflows/plan/works-factory-plan.yaml::structure-state（trigger_rule: all_done）
- gaps-plan.md P084: lib/planfile.py::write_state
- gaps-plan.md P085: workflows/plan/works-factory-plan.yaml::structure-state（all_done）とplan-loop（none_failed_min_one_success）・lib/structmark.py::plan_section
- gaps-plan.md P086: lib/planfile.py::keep_state（workflows/plan/scripts/structure_state.py。書けない周は周のフォルダに「構造の控えを書けない」の訳で failed を置き、round.json の structure を替えて計画へ進む）（#120）
- gaps-plan.md P087: workflows/plan/works-factory-plan.yaml::plan-loop（structure-state が落ちれば plan-loop は none_failed_min_one_success で飛ぶ）・出力ノード plan は ready: false
- gaps-plan.md P088: lib/structmark.py::plan_section・lib/planfile.py::write_brief `structmark.plan_section(structure_dir_)`
- gaps-plan.md P109: lib/converge.py::splice（planfile の写しは消え、converge のを直に使う）、lib/planfile.py::take_plan（DROPPED_OP は converge.DROPPED_OP を直に使う）
- gaps-plan.md P110: lib/planfile.py::take_plan（`extra = {block_answers}`）→ lib/boardview.py::open_pass（`converge.split("plan-revise", fix_plan)` → `converge.note_answers`）
- gaps-plan.md P114: P74 works-factory-line.yaml の `max_iterations: 20` と、plan-out・plan-review-run の `with:` の `round_limit: 20`（正本はメイングラフ。lib/boardview.py::_at_cap は入力の round_limit で converge.record_pass の at_cap を決め、数を持たない）
- gaps-plan.md P118: lib/planfile.py::write_brief（形 plan の材料に独立設計のセクションは元から無い。2 周目は会話が新しいので planmarks.HEAD を含む頭を貼り直す）
- gaps-plan.md P120: lib/boardview.py::_pass_rejects（受け付けが往復を控えた後、converge.stash_rejects でその往復の計画の周の rejects-plan.json と事前審査の拒否の行を往復の行の rejects に残す。拒否の控えは周・挟んだ回ごと）（#120）
- gaps-plan.md P121: lib/boardview.py::take_review（accept.guard が例外を拒否にし、3 回で give_up → 出力ノードが pass: false・stalled: true と訳を questions に載せる）
- gaps-plan.md P126: lib/planfile.py::item_brief・lib/planfile.py::replan_section（承認済みの項目と判定から planbrief.render で plan/r<k>/item-brief-<no>.md を組み、「この項目の brief: <パス>」で名指す）（#120）
- gaps-plan.md P134: WF workflows/plan/scripts/plan_accept.py（rolekit.with_done）、lib/planfile.py::why_not_ready
- gaps-plan.md P135: lib/planfile.py::collect_reads（形 replan は reads-replan-<役>.json と reads-replan-block.json を周のフォルダに書く）（#120）
- gaps-plan.md P137: lib/boardview.py::review_material・lib/boardview.py::replan_items・lib/boardview.py::_replan_section
- gaps-plan.md P138: lib/boardview.py::_shown_plan（形 replan の材料の「修正役の案」に裁かれた項目だけを貼る。`_faces_of` は元 replan._review_of と同じなので変えない）（#120）
- gaps-plan.md P140: lib/boardview.py::_take（converge.split・tree_split・planblk.design_gaps(items=ruled)）
- gaps-plan.md P142: lib/planfile.py::note_gave_up・lib/boardview.py::collect（出力のポインタの隣の replan-gave-up.json に項目ごとの {item, why, ruling}。訳は planblk.PLAN_GAVE_UP_WHY・REVIEW_GAVE_UP_WHY）・lib/runreport.py::replan_gave_up（前の失敗の行）（#120）
- gaps-plan.md P169: lib/boardview.py::check_design・workflows/plan-review/scripts/pass_open.py::node_schema
- gaps-plan.md P173: workflows/plan-review/commands/r2-design.md（台帳 tests/workflows/test_plan_review.py の COPIED）・lib/boardview.py::r2_prompt の DRIFT_LINE・STALE_LINE（#120）
- gaps-plan.md P180: lib/boardview.py::collect（trace に design.HANDED_OP・MISSING_OP）（#120）
- gaps-plan.md P184: lib/planmarks.py::review_section・lib/planblk.py::design_section
- gaps-plan.md P185: lib/planmarks.py::review_section（DEVIATION_HEAD のセクション）・lib/planblk.py::design_section（worldmark.challenges を渡す）
- gaps-plan.md P187: lib/boardview.py::review_material（pass-<k>/prep-error.txt）・lib/boardview.py::collect（review.json が無い時にその訳）（#120）
- gaps-plan.md P194: workflows/plan-review/commands/plan-review.md
- gaps-plan.md P211: lib/reads.py::collect・lib/boardview.py::collect_reads・workflows/plan-review/scripts/review_reads.py（ノード review-reads）・bin/_lib/record-read.py・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- gaps-plan.md P212: lib/boardview.py::collect_reads（trace の planblk.AGENT_OP）・bin/_lib/record-read.py（Agent の行）・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- gaps-plan.md P213: lib/reads.py::web_fetches・lib/reads.py::web_searches・bin/_lib/record-read.py（WebFetch・WebSearch の行）・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- gaps-plan.md P218: lib/gatemarks.py::MARK_SCHEMA・lib/gatemarks.py::NO_NARROW_SCHEMA（with_marks は #232 で消えた。役の型の欄は workflows/plan-review/works-factory-plan-review.yaml::plan-review（faces の行）と workflows/plan/works-factory-plan.yaml::plan-writer（narrows の行）に写し、持ち主との一致は試験が見る）
- gaps-plan.md P222: lib/gatemarks.py::_gate_rows・lib/boardview.py::HUMAN_FACE_KINDS
- gaps-plan.md P226: lib/gatemarks.py::_world・lib/gatemarks.py::_no_narrow・lib/gatemarks.py::_item
- gaps-plan.md P245: lib/boardview.py::_note_asked・lib/boardview.py::collect（GATE_FILE）
- judge.md J01: lib/judge_accept.py::start_view・lib/judge_accept.py::intake
- judge.md J02: lib/judge_accept.py::add・lib/judge_accept.py::check_request
- judge.md J03: lib/judge_accept.py::request_container・lib/judge_accept.py::intake
- judge.md J04: lib/judge_accept.py::intake（始めの記録が依頼 1 件以上と言えば空の行も check_request に通す）（部分 A で閉じた）
- judge.md J05: lib/judge_accept.py::intake
- judge.md J06: lib/judge_accept.py::intake（carry.place_prior）・lib/judge_accept.py::brief
- judge.md J07: lib/judge_accept.py::write_stop・lib/judge_accept.py::VERIFY_STOP・lib/judge_accept.py::SPEC_STOP・lib/judge_accept.py::MATERIAL_STOP・lib/judge_accept.py::REQUEST_STOP の語
- judge.md J08: lib/judge_accept.py::measured_needs_output
- judge.md J09: lib/judge_accept.py::check_claims・lib/premises.py::claims
- judge.md J10: lib/judge_accept.py::_tree_unchanged・lib/judge_accept.py::check_premises
- judge.md J11: workflows/judge/works-factory-judge.yaml::premises の `output_format`（型の正本。lib の写し `PREMISES_SCHEMA` は #232 で消し、lib/judge_accept.py::check_premises は型を照らし直さない）
- judge.md J12: lib/judge_accept.py::_missing_stage
- judge.md J13: workflows/judge/commands/premises.md（字は在る）
- judge.md J14: lib/judge_accept.py::refuse_if_frozen・lib/judge_accept.py::purpose_prep
- judge.md J15: lib/judge_accept.py::purpose_prep
- judge.md J16: lib/judge_accept.py::check_purpose
- judge.md J17: lib/purpose.py::_source_files_errors・lib/judge_accept.py::check_purpose
- judge.md J18: lib/judge_accept.py::check_purpose
- judge.md J20: workflows/judge/commands/purpose.md（字は在る）
- judge.md J21: lib/worldblk.py::class_id・lib/worldblk.py::class_problems
- judge.md J22: lib/worldcheck.py::verify・lib/worldblk.py::_check_excerpts
- judge.md J23: lib/worldblk.py::judge_prep・lib/worldcheck.py::banned_tokens・workflows/judge/works-factory-judge.yaml の world-classes・world-judge のノード
- judge.md J24: lib/worldblk.py::judge_problems
- judge.md J25: lib/judge_accept.py::world_finish
- judge.md J26: lib/judge_accept.py::world_accept
- judge.md J27: lib/judge_accept.py::_world_due・lib/judge_accept.py::world_intake
- judge.md J28: lib/judge_accept.py::brief・lib/judge_accept.py::_judged
- judge.md J29: lib/judge_accept.py::verdict
- judge.md J30: lib/worldblk.py::_switch
- judge.md J31: lib/judge_accept.py::parallel_pr_plan・lib/judge_accept.py::parallel_pr_scan・lib/judge_accept.py::parallel_pr_reply・lib/judge_accept.py::pr_scan
- judge.md J32: lib/judge_accept.py::pr_scan
- judge.md J33: lib/judge_accept.py::pr_scan
- judge.md J34: lib/judge_accept.py::_pr_files・lib/judge_accept.py::parallel_pr_reply
- judge.md J35: lib/judge_accept.py::check_no_post・lib/judge_accept.py::prcheck_take
- judge.md J36: lib/prcheck.py::_anchored・lib/prcheck.py::check_excluded・lib/judge_accept.py::prcheck_take
- judge.md J37: lib/judge_accept.py::prcheck_take
- judge.md J38: lib/judge_accept.py::pr_accept・lib/judge_accept.py::accept_round
- judge.md J39: lib/judge_accept.py::_github_repo（forge.redact）
- judge.md J40: lib/judge_accept.py::pr_reads（ノード workflows/judge/works-factory-judge.yaml::pr-check-reads。lib/reads.py::collect）
- judge.md J41: lib/downgrades.json（元 darkfactory/downgrades.json の写し）・lib/prcheck.py の downgrades・head_downgrades → lib/runreport.py の _downgrade_lines（入口のセクション）
- judge.md J42: lib/judge_accept.py::due_view・lib/judge_accept.py::_TOUCH・lib/judge_accept.py::not_request_entry・lib/judge_accept.py::external_standards_due・lib/judge_accept.py::provenance_due・lib/judge_accept.py::_deep・lib/judge_accept.py::_deep_due・lib/judge_accept.py::procedure_trace_due・lib/judge_accept.py::gate_efficacy_due・lib/judge_accept.py::test_double_fidelity_due・lib/judge_accept.py::main_path_observation_due・lib/judge_accept.py::prior_decisions_due・lib/judge_accept.py::purpose_review_due・lib/judge_accept.py::parallel_pr_due・lib/judge_accept.py::material_route
- judge.md J43: lib/judge_accept.py::_entry_marked・lib/judge_accept.py::_entry_skipped・lib/judge_accept.py::_fill_one
- judge.md J44: lib/judge_accept.py::purpose_review_due・lib/judge_accept.py::touches_procedures・lib/judge_accept.py::gates_merge
- judge.md J45: lib/judge_accept.py::material_route
- judge.md J46: lib/judge_accept.py::_material_ctx・lib/judge_accept.py::material_prep
- judge.md J47: lib/judge_accept.py::_na_note
- judge.md J48: lib/judge_accept.py::_purpose_or_missing・lib/judge_accept.py::PURPOSE_MISSING
- judge.md J49: lib/judge_accept.py::mutation_decl（lib/graphloops/engine/declared.py の `read` で対象の根の宣言を読む）・lib/judge_accept.py::_material_ctx
- judge.md J50: workflows/judge/commands/material-local-review.md のセクション「必須のレンズの呼び出しの失敗」「/code-review の返し方」・11 本の commands の「所見の場所の書き方」
- judge.md J51: lib/judge_accept.py::_peers_note（material-route.json で同じ時に回す役を並べる。読めなければそう言う）・lib/judge_accept.py::material_take
- judge.md J52: lib/judge_accept.py::check_record
- judge.md J53: lib/judge_accept.py::gate_signals・lib/judge_accept.py::role_judged_na
- judge.md J54: lib/judge_accept.py::main_path_observed・lib/judge_accept.py::external_rankings・lib/judge_accept.py::gate_arms_all_red
- judge.md J55: lib/judge_accept.py::purpose_findings_cited・lib/judge_accept.py::_cite_errors・lib/judge_accept.py::_count_in_version
- judge.md J56: lib/judge_accept.py::local_review_covers_lenses・lib/judge_accept.py::LOCAL_REVIEW_SKILLS
- judge.md J57: lib/judge_accept.py::_lens_gap の 2 つ目を lib/judge_accept.py::material_take が give_up で返し、lib/judge_accept.py::accept_round が lib/rolekit.py::with_done の give_up で 1 回目から done にする（lib/rolekit.py::given_up_reason が諦めとして読む）
- judge.md J58: lib/diverted.py::mark_unseen・lib/judge_accept.py::material_take
- judge.md J59: lib/judge_accept.py::_location_problems・lib/judge_accept.py::_location_gap
- judge.md J60: lib/judge_accept.py::fill_materials
- judge.md J61: lib/judge_accept.py::baseline_local_checks
- judge.md J62: lib/judge_accept.py::materials_given_up・lib/judge_accept.py::diagnose_prep
- judge.md J63: lib/judge_accept.py::brief・lib/judge_accept.py::policy_text
- judge.md J64: lib/judge_accept.py::_take_diff
- judge.md J65: workflows/judge/commands/diagnose.md（字は在る。元の `盤面の材料が無い時` の 1 句だけ無い——共有ボードの無い道が無くなったので要らない）
- judge.md J66: lib/rolekit.py::lang_line・lib/rolekit.py::record_lang_line（workflows/judge/scripts/reject.py・rejects.py・material_prep.py（素材集めのループの頭）と判定の裏取りの支度が lang_line で返し、各役の指示書の頭が `$<節>.output.lang_line` で読む）
- judge.md J67: lib/judge_accept.py::_judge_tree_unchanged・lib/judge_accept.py::snap_tree（lib/judge_accept.py::diagnose_prep で判定役の前に置く）
- judge.md J68: workflows/judge/works-factory-judge.yaml::diagnose の `output_format`（lib の写し `DIAGNOSE_SCHEMA` は #232 で消した）、改行を落とすのは lib/judge_accept.py::ONE_LINE_FIELDS・lib/judge_accept.py::judge_output
- judge.md J69: lib/judge_accept.py::judge_output
- judge.md J70: lib/judge_accept.py::judge_output・lib/judge_accept.py::_run_query
- judge.md J71: lib/querytest.py::problems・lib/querytest.py::split・lib/querytest.py::restore・lib/judge_accept.py::_judged・lib/judge_accept.py::_save_examples
- judge.md J72: lib/querytest.py::unproven
- judge.md J73: lib/judge_accept.py::judge_output
- judge.md J74: lib/judge_accept.py::judge_output（問いの照らし）・lib/judge_accept.py::QUESTION_KINDS・lib/judge_accept.py::ORIGIN_NOTE・lib/judge_accept.py::QUESTION_FIELDS・lib/judge_accept.py::UNIT_FIELDS・lib/judge_accept.py::QUESTION_STATUS・lib/judge_accept.py::QUESTION_STATUS_NOTE の表、型の側は workflows/judge/works-factory-judge.yaml::diagnose の `output_format`
- judge.md J75: lib/judge_accept.py::_precedent_gap・lib/judge_accept.py::_precedent_errors
- judge.md J76: lib/judge_accept.py::_awaiting_origins・lib/judge_accept.py::judge_output・lib/judge_accept.py::_judged
- judge.md J77: lib/judge_accept.py::judge_output
- judge.md J78: lib/judge_accept.py::_carried_r1_accounted・lib/judge_accept.py::_fork_moves_forward（受け付けはいつも空の前の周を渡す）。前の周に残すと宣言した穴の振り分け（`_declared_route_errors`）は届かなかったので #232 で消した
- judge.md J79: lib/judge_accept.py::material_rows・lib/judge_accept.py::take・lib/outpurpose.py
- judge.md J80: lib/judge_accept.py::answer_tie_problems・lib/judge_accept.py::take
- judge.md J81: lib/judge_accept.py::accept・lib/judge_accept.py::_give_up・workflows/judge/works-factory-judge.yaml の `diagnose-reject`（集めの口 `collect` は届かなかったので #232 で消した）。仕様の 3 つのループと再審のループは、頭のノード（script rejects）が with: の board・accept で拒否の控えの全部を読み rolekit.rejects_text で渡す（workflows/judge/scripts/rejects.py。#345）。どのループも fresh_context: false で、拒まれた後の出し直しは同じ役の会話の続き。仕様の 3 つのループと再審のループでは、出し直しの役（workflows/judge/works-factory-judge.yaml::spec-fix・spec-review-fix・spec-revise-fix・rejudge-fix）が拒まれた欄だけを返し、受け付けが前の答えと欄ごとに合わせる（lib/rolekit.py::resubmitted・lib/rolekit.py::merge_fields。#571）
- judge.md J82: lib/judge_accept.py::take・lib/judge_accept.py::PUBLIC_FILES
- judge.md J83: lib/judge_accept.py::prep_on・lib/judge_accept.py::verify_not_run
- judge.md J84: lib/judge_accept.py::prep_on
- judge.md J85: lib/judge_accept.py::_check_unit・lib/judge_accept.py::_check_synergy・lib/judge_accept.py::merge_on
- judge.md J86: lib/judge_accept.py::merge_on
- judge.md J87: lib/judge_accept.py::structure_units・lib/judge_accept.py::_unit_file_paths
- judge.md J88: lib/judge_accept.py::structure_units（record に捨てたパスと paths の空の単位を書く）・lib/judge_accept.py::STRUCTURE_DROPPED_FILE（lib/judge_accept.py::verdict が判定の置き場に置く）
- judge.md J89: lib/judge_accept.py::verdict・workflows/judge/scripts/verdict.py
- judge.md J90: lib/judge_accept.py::verdict・lib/judge_accept.py::_fill
- judge.md J91: workflows/judge/scripts/verdict.py・lib/judge_accept.py::verdict_fallback
- judge.md J92: lib/judge_accept.py::_spec_errors・lib/judge_accept.py::spec_write_output
- judge.md J93: lib/judge_accept.py::spec_review_output・lib/judge_accept.py::spec_revise_due・lib/judge_accept.py::spec_take
- judge.md J94: lib/judge_accept.py::spec_revise_output・lib/judge_accept.py::spec_now
- judge.md J95: lib/judge_accept.py::spec_approve・lib/judge_accept.py::spec_ask・lib/specblk.py::gate_text
- judge.md J96: lib/judge_accept.py::spec_answer・workflows/judge/works-factory-judge.yaml の spec-gate
- judge.md J97: lib/judge_accept.py::spec_freeze・lib/judge_accept.py::_spec_run・lib/judge_accept.py::spec_answer
- judge.md J98: lib/judge_accept.py::spec_ask
- judge.md J99: workflows/judge/commands/spec.md の「依頼: … request.json を Read で読め」と「実装のファイルは 1 文字も変えるな」の文・workflows/judge/commands/spec-revise.md
- judge.md J100: lib/judge_accept.py::rejudge_prep
- judge.md J101: 無し（再審役は新しい会話で、保存した judge/judgment.json と材料を読む。lib/judge_accept.py::_rejudge_brief）
- judge.md J102: lib/judge_accept.py::_rejudge_brief・lib/judge_accept.py::rejudge_prep
- judge.md J103: lib/judge_accept.py::rejudge_output・lib/judge_accept.py::rejudge_take・lib/judge_accept.py::REJUDGE_VERDICTS、型は workflows/judge/works-factory-judge.yaml::rejudge の `output_format`（lib の写し `REJUDGE_SCHEMA` は #232 で消した）
- judge.md J104: lib/judge_accept.py::diff_units・lib/judge_accept.py::rejudge_collect
- judge.md J105: lib/judge_accept.py::rejudge_take・lib/judge_accept.py::rejudge_collect
- judge.md J106: workflows/judge/works-factory-judge.yaml
- judge.md J107: 13 本の workflows/judge/commands/*.md の頭
- judge.md J108: 読み手は在る。materials.json → lib/runreport.py・lib/outcome.py・lib/boardview.py・lib/outcome.py::materials・workflows/plan-review/works-factory-plan-review.yaml の入力 judgment（隣の materials.json を名で開くと書く）、judge-verify.json → workflows/plan/works-factory-plan.yaml・lib/planfile.py・lib/runreport.py::verify_lines、pr-excluded.json → lib/planfile.py・lib/runreport.py::pr_lines、premises.json → workflows/eyes/scripts/prep.py・workflows/plan-review/scripts/r2_prep.py・lib/runreport.py::premise_lines
- judge.md J109: lib/runreport.py の ledger・ledger_state（gatemarks.unmatched_answer_lines・answer_tie_lines を 1 回目の判定の隣の answer-ties.json で引き、人が決めることのセクションに並べる）
- judge.md J110: lib/diverted.py の report_lines（判定の隣の local-review-lenses.json）→ lib/runreport.py の _unseen_lens_lines（報告の「未確認のレンズ」のセクション report.UNSEEN_LENS_HEADING）
- judge.md J111: lib/prcheck.py の DRAFTS・draft_lines（判定の隣の pr-downgrades.json）→ lib/runreport.py の _pr_draft_lines（人が決めることのセクション）
- judge.md J112: lib/runreport.py の _world_lines（1 回目の判定の隣の world-state.json を worldmark.read で。段が落ちた訳・類・落とした抜き書きの数）
- judge.md J113: 書くのは lib/judge_accept.py::rejudge_collect。読み手はメイングラフ（workflows/line/scripts/judged.py::compared が rejudge-exit.json を lib/report.py::rejudge_exit で開く）と報告（lib/runreport.py::rejudge_exit・lib/runreport.py::rejudge_lowered・lib/runreport.py::rejudge_changes が rejudge-diff.json を開く・lib/runreport.py::rejudge_lines）
- line.md L-E01: workflows/line/scripts/start.py::request、lib/entry.py::request_problems
- line.md L-E02: workflows/line/scripts/start.py::request（読めない・JSON として読めない・形の 3 つを別の文で拒む）（部分 A で閉じた）
- line.md L-E03: workflows/line/scripts/start.py::start（record["answers"]）（部分 A で閉じた）
- line.md L-E04: workflows/line/scripts/start.py::request（carry.parts の ValueError を「形」で拒む）（部分 A で閉じた）
- line.md L-E05: workflows/line/scripts/start.py::start、workflows/line/works-factory-line.yaml::judge・workflows/line/works-factory-line.yaml::plan・workflows/line/works-factory-line.yaml::rejudge-run・workflows/line/works-factory-line.yaml::replan
- line.md L-E06: workflows/line/scripts/start.py::request（部分 A で閉じた）
- line.md L-E07: lib/entryshape.py::refuse_empty・lib/entryshape.py::EMPTY_REFUSED、workflows/line/scripts/start.py::start
- line.md L-E08: lib/entryshape.py::change_base
- line.md L-E09: lib/entryshape.py::change_base（部分 A で閉じた）
- line.md L-E10: lib/entryshape.py::merge_base・lib/entryshape.py::change_base（部分 A で閉じた）
- line.md L-E11: lib/entryshape.py::github_reads、workflows/line/scripts/start.py::start（ghreads.place）（部分 A で閉じた）
- line.md L-E12: lib/entryshape.py::change_base（部分 A で閉じた）
- line.md L-E13: lib/entryshape.py::change_base（部分 A で閉じた）
- line.md L-E14: lib/entryshape.py::change_base
- line.md L-E15: lib/entryshape.py::NO_AUTH_ENV（WORKS_FACTORY_NO_AUTH。殻 bin/_lib/launcher.py・auth_launch.py と同じ名）（部分 A で閉じた）
- line.md L-E16: lib/entryshape.py::request_text、workflows/line/scripts/start.py::start（部分 A で閉じた）
- line.md L-E17: lib/entryshape.py::build（input.pr に body）→ lib/judge_accept.py::start_view・lib/judge_accept.py::_pr_of・lib/judge_accept.py::purpose_prep（部分 A で閉じた）
- line.md L-E18: lib/entryshape.py::named（部分 A で閉じた）
- line.md L-E19: lib/entryshape.py::build（部分 A で閉じた）
- line.md L-E20: lib/entryshape.py::diff_of・lib/entryshape.py::_worktree_tree
- line.md L-E21: workflows/line/scripts/start.py::start
- line.md L-E22: lib/startrec.py::words
- line.md L-E23: lib/startrec.py::shape・lib/startrec.py::diff_empty・lib/startrec.py::requests
- line.md L-E24: lib/startrec.py::path・lib/startrec.py::write・lib/startrec.py::adopt・lib/startrec.py::read（メイングラフの start は run の置き場の根の r1/start.json に書き、fix の prep・事前審査の open は adopt で字のまま写す）（部分 A で閉じた）
- line.md L-E25: workflows/line/scripts/start.py::words（部分 A で閉じた）
- line.md L-E26: workflows/line/scripts/start.py::words・workflows/line/scripts/start.py::start
- line.md L-E27: workflows/line/scripts/start.py::words・workflows/line/scripts/start.py::start（部分 A で閉じた）
- line.md L-E28: lib/gatepolicy.py::check、workflows/line/scripts/start.py::words
- line.md L-E29: workflows/line/scripts/start.py::start（依頼の findings と PR の題・本文を見る。既定の「変更（label）の審査」で空を隠さない）（部分 A で閉じた）
- line.md L-E30: lib/gatepolicy.py::check、workflows/line/scripts/start.py::words・workflows/line/scripts/start.py::start
- line.md L-E31: lib/entry.py::_feature_list、workflows/line/scripts/start.py::words
- line.md L-E32: lib/entry.py::FEATURE_DEFAULTS・lib/entry.py::feature_words・lib/entry.py::features_cut、workflows/line/scripts/start.py::start
- line.md L-E33: workflows/line/scripts/start.py::start（features_cut）（部分 A で閉じた）
- line.md L-E34: Archon の再開が済んだノードを飛ばす（start に always_run を付けない）（部分 A で閉じた）
- line.md L-E35: workflows/line/scripts/start.py::policy_md
- line.md L-E36: 各サブグラフが record.policy_md から組む（main lib/judge_accept.py::policy_text、workflows/fix/scripts/delta_cut.py::main、workflows/eyes/scripts/prep.py::out）
- line.md L-E37: lib/rolekit.py::LANG_RULE・lib/rolekit.py::lang_line・lib/rolekit.py::record_lang_line（住処を 1 つにし、fixboard・planfile・eyeverdict の写しはそれを引く）。judge はループの頭の拒否のノード workflows/judge/scripts/reject.py・rejects.py・material_prep.py（素材集めのループの頭）と判定の裏取りの支度 verify.py が `lang_line` を返し、全部の役の指示書の頭が `$<節>.output.lang_line`。report は facts が返し commands/report.md の頭（部分 A で閉じた）
- line.md L-E38: workflows/line/scripts/start.py::start（部分 A で閉じた）
- line.md L-E42: workflows/line/scripts/start.py::from_fixture・workflows/line/scripts/start.py::fixture_dir・lib/fixture.py::adopt（置き場と作業ツリーのパス・run の id・HEAD の置き換え、前の版の拒みは形の版 FORMAT。trace の 1 行の代わりに起動の承認ノードの文と報告の入口のセクションの「固定材料から」の行 lib/fixture.py::lines）（#509 で戻した）
- line.md L-E43: lib/fixture.py::capture・lib/fixture.py::noted_capture・workflows/line/scripts/fix_in.py::fix_in（今の works が写した作業の状態と名指しのファイルの代わりに、run の置き場と修正の段へ運ぶ値を写す）（#509 で戻した）
- line.md L-E44: workflows/line/scripts/start.py::version_record（lib/versions.py::snapshot を呼ぶ。書いた時の `versions` は {archon, claude_code} だけだった）。lib/startrec.py::cli_version
- line.md L-E45: lib/versions.py::snapshot（元 versions.py の名。分からない値は null と unknown の訳）（部分 A で閉じた）
- line.md L-E46: workflows/line/scripts/start.py::start（確かめの前に inputs と versions を置く）（部分 A で閉じた）
- line.md L-E47: workflows/line/works-factory-line.yaml::gate-start（when: ask）、workflows/line/scripts/start.py::start
- line.md L-E48: workflows/line/scripts/start.py::gate_text（部分 A で閉じた）
- line.md L-E49: workflows/line/scripts/start.py::depth_words・workflows/line/scripts/start.py::test_notes・workflows/line/scripts/start.py::gate_text（部分 A で閉じた）
- line.md L-E50: lib/answer.py::ENV・lib/answer.py::head・lib/answer.py::line（同じ字）。殻 bin/_lib/launcher.py::answer_head が WORKS_ANSWER_CMD を置く（殻の外の run だけ穴 lib/answer.py::HOLE）。答えた者 WORKS_ANSWER_WHO を末尾に付ける所は無い
- line.md L-E51: workflows/line/works-factory-line.yaml::answer-start、workflows/line/scripts/gate_answer.py::take → lib/answer.py::taken
- line.md L-E52: workflows/line/scripts/start.py::start、workflows/line/works-factory-line.yaml::test-gate-base ほかの when
- line.md L-E53: workflows/.shared/boundary.py::run・workflows/.shared/boundary.py::guarded_imports、workflows/line/scripts/start.py::fallback
- line.md L-E54: yaml の inputs: と workflows/line/scripts/start.py::raw_inputs
- line.md L-E55: lib/entryshape.py と workflows/line/scripts/start.py だけ（柵 entry-kind）（部分 A で閉じた）。柵の正本は表 docs/concepts.json の entry-kind
- line.md L-E56: workflows/line/works-factory-line.yaml::test-gate-base と main workflows/judge/works-factory-judge.yaml::pr-scan（pr_check）に移った
- line.md L-G01: workflows/line/works-factory-line.yaml::gate-start・workflows/line/works-factory-line.yaml::gate-before-fix・workflows/line/works-factory-line.yaml::gate-replan・workflows/line/works-factory-line.yaml::gate-final
- line.md L-G02: lib/answer.py::GO_WORDS・lib/answer.py::REJECT・lib/answer.py::taken、4 つの承認ノードの decisions（yaml の gate-*）
- line.md L-G03: workflows/line/scripts/gate_answer.py::take → lib/answer.py::taken（通す語でない答えは止め）（部分 A で閉じた）
- line.md L-G04: lib/answer.py::taken（`gates/<所>.json`。workflows/line/scripts/gate_answer.py::take が呼ぶ）→ collect（workflows/line/works-factory-line.yaml::collect）→ report
- line.md L-G05: lib/answer.py::taken（workflows/line/scripts/gate_answer.py::take が呼ぶ）、yaml の `{from, if_skipped: null}`（workflows/line/works-factory-line.yaml::answer-start・workflows/line/works-factory-line.yaml::answer-before-fix・workflows/line/works-factory-line.yaml::answer-replan・workflows/line/works-factory-line.yaml::answer-final）
- line.md L-G06: lib/answer.py::taken の `human:<所>`、collect・report の `trigger_rule: all_done`（workflows/line/works-factory-line.yaml::collect・workflows/line/works-factory-line.yaml::report）
- line.md L-G07: workflows/line/scripts/gate_answer.py::take → lib/answer.py::taken・lib/answer.py::STOP_NOTE・lib/answer.py::FINAL_STOP_NOTE（部分 A で閉じた）
- line.md L-G08: lib/answer.py::ENV・lib/answer.py::head・lib/answer.py::line、殻 bin/_lib/launcher.py::answer_head が env に頭を置く（殻の外の run だけ穴 `HOLE`。lib/answer.py::HOLE）。答えた者（WORKS_ANSWER_WHO）は付けない
- line.md L-G09: workflows/line/scripts/start.py::gate_text・yaml gate-start（部分 A で閉じた）
- line.md L-G10: workflows/line/scripts/start.py::start、workflows/line/works-factory-line.yaml::gate-start
- line.md L-G11: lib/gatepolicy.py::check、workflows/line/scripts/start.py::words
- line.md L-G12: lib/gatepolicy.py::check
- line.md L-G13: lib/gatepolicy.py::check、workflows/line/scripts/start.py::words
- line.md L-G14: lib/gatepolicy.py::opens、workflows/line/scripts/ask_final.py::ask
- line.md L-G15: workflows/line/works-factory-line.yaml::ask-final（`final_gate: $start.output.final_gate`）。workflows/line/scripts/ask_final.py::ask は `mode or ALWAYS` で読み、知らない語を確かめない
- line.md L-G16: lib/gatepolicy.py::head_words、workflows/line/scripts/start.py::gate_text、workflows/line/scripts/ask_final.py::final_head
- line.md L-G17: workflows/line/scripts/ask_before_fix.py::ask、main lib/boardview.py::collect
- line.md L-G18: lib/gatemarks.py::plan_gate_items・lib/gatemarks.py::_record、main lib/boardview.py::collect（gate-passes.json）、main lib/gate_axes.py::gather
- line.md L-G19: 報告は lib/runreport.py の `_gate_passes`。最後の承認ノードは workflows/line/scripts/ask_final.py の `review_rows`（事前審査の review の隣の gatemarks.PASSES_FILE を gatemarks.pass_lines で）と `final_text` の「直す前の承認ノードで通した項目」
- line.md L-G20: lib/gatemarks.py::_item → workflows/line/scripts/ask_before_fix.py::ask
- line.md L-G21: workflows/line/scripts/ask_before_fix.py::ask は plan-review の questions の行 {kind, text} の種類のまま承認ノードの文の頭に並べ（gatemarks.gate_text の KIND_WORDS）、ASK_GATE_HEAD は台帳の問い（fork・escalate）が在る時だけ（部分 B1）
- line.md L-G22: lib/gatemarks.py::ask_text → workflows/line/scripts/ask_before_fix.py::ask
- line.md L-G23: lib/gatemarks.py::gate_text（引用と QUOTE_NOTE）。workflows/line/scripts/ask_before_fix.py の問いの文は決まり文句 QUESTION を引用する
- line.md L-G24: lib/gatemarks.py::pushes・lib/gatemarks.py::head3・lib/gatemarks.py::push_of、workflows/line/scripts/ask_before_fix.py::gate_text・workflows/line/scripts/ask_replan.py::ask・workflows/line/scripts/ask_final.py::final_head・workflows/line/scripts/start.py::gate_text
- line.md L-G25: lib/gatemarks.py::PLAIN・lib/gatemarks.py::named・lib/gatemarks.py::eye_named。workflows/line/scripts/ask_final.py::eye_lines が目の行を eye_named で書く
- line.md L-G26: workflows/line/scripts/ask_before_fix.py::ask
- line.md L-G27: workflows/line/scripts/ask_before_fix.py::ask（needs-human）
- line.md L-G28: workflows/line/scripts/ask_before_fix.py::ask の stalled の枝（STUCK_ITEM）。上限の周も plan-review が stalled で返す。理由の尾は plan-review の questions 側に在り、行が 2 度出うる（L-D19）
- line.md L-G29: lib/gatemarks.py::world_items・lib/gatemarks.py::design_items・lib/gatemarks.py::_continued。案の直しの事前審査（replan-review）は gate_answers を受けて人が continue した行を聞き直さない
- line.md L-G30: lib/gatemarks.py::answered・lib/gatemarks.py::hold_keys、workflows/line/scripts/ask_final.py::ledger、lib/runreport.py::ledger_state
- line.md L-G31: lib/gatemarks.py::unread_hold_lines。最後の承認ノードは workflows/line/scripts/ask_final.py::ledger_rows → final_text、報告は lib/runreport.py::ledger_state の unread_holds → _decisions
- line.md L-G32: lib/gatemarks.py::returned・lib/gatemarks.py::returned_lines・lib/gatemarks.py::duty（値の見え方 ledger）。fix は lib/fixboard.py::gate_view・lib/fixboard.py::group_owed・lib/fixboard.py::write_notes が置き場の answers.json（{decision, text, asked}。asked は $ask-before-fix.output.asked）から引く
- line.md L-G33: lib/gatemarks.py::pending・lib/gatemarks.py::withheld_by・lib/gatemarks.py::withheld・lib/gatemarks.py::duty。無人の run は ask-before-fix が台帳の問いだけを deferred にして修正へ進み、fix・plan の直す義務（gatemarks.duty）が出どころを外す
- line.md L-G34: lib/gatemarks.py::binds・lib/gatemarks.py::origin（値で受ける 1 つの式。gatemarks.answer_binds・outcome.answer_binds・judge_accept.answer_binds は呼ぶだけ）。最後の承認ノードは workflows/line/scripts/ask_final.py::ledger が gatemarks.ledger_at（ledger_beside をファイルから。判定の隣の materials.json と、ties_judgment: $fix-in.output.judgment の隣の answer-ties.json）で引く。報告は lib/runreport.py::ledger
- line.md L-G35: workflows/line/scripts/ask_final.py::ledger・workflows/line/scripts/ask_final.py::ledger_rows（gatemarks.held_lines）、lib/runreport.py::ledger_state
- line.md L-G36: workflows/line/scripts/ask_final.py::final_head・workflows/line/scripts/ask_final.py::question_lines
- line.md L-G37: 報告は lib/runreport.py::_decisions。最後の承認ノードは workflows/line/scripts/ask_final.py::ledger_rows（gatemarks.answered_lines・unmatched_answer_lines）→ question_lines
- line.md L-G38: workflows/line/scripts/ask_before_fix.py::ask（無人の run は種類 fork・escalate の行だけを deferred にする）
- line.md L-G39: workflows/line/scripts/ask_before_fix.py::ask・workflows/line/scripts/ask_replan.py::ask・workflows/line/scripts/ask_final.py::ask の `works:needs-human`
- line.md L-G40: workflows/line/scripts/ask_before_fix.py::ask: 事前審査の出力 questions の行 {kind, text}（plan-review が種類を残す。lib/boardview.py::collect）のうち fork・escalate でない行（方針の文書の変化・事前審査の諦め given_up・狭め・穴・世界の解の外れ・設計）は無人の run で止める（全部が通す推しを持てば lib/gatemarks.py::pushed_answer で推しで進む）
- line.md L-G41: lib/runreport.py::answer_drafts・lib/runreport.py::build
- line.md L-G42: lib/gatemarks.py::recommend_gaps
- line.md L-G43: workflows/line/scripts/ask_replan.py::ask
- line.md L-G44: workflows/line/scripts/ask_replan.py::section（元 replan._gate_section。約束の欄の変化・項目を誤りとした申し出の文と裁定の文・前と後の項目の JSON）。ask-replan の入力 conflicts ← $fix.output.conflicts
- line.md L-G45: workflows/line/scripts/ask_replan.py::ask が lib/replan.py::widen_text（元 replan._widen_text の字）で widened を返す
- line.md L-G46: workflows/line/scripts/replan_answer.py::take、workflows/line/works-factory-line.yaml::refix-run（when）、workflows/line/scripts/ask_replan.py::ask
- line.md L-G47: workflows/line/scripts/replan_answer.py::fix_answers・workflows/line/works-factory-line.yaml::refix-run
- line.md L-G48: workflows/line/scripts/ask_final.py::needs（[(1 句, must)] の 1 つの列。final_needs・ask・final_head はこれだけを読む）
- line.md L-G49: workflows/line/scripts/ask_final.py::needs の must（守りのパス・確かめられなかった・許したテスト・人に回した申し出・読めない申し出の控え）と protected_section・conflict_section
- line.md L-G50: ask-final の must。ask-final が飛ばされれば answer-final と merge-apply も飛ぶ（merge-apply の when: $answer-final.output.go == true）
- line.md L-G51: workflows/line/scripts/ask_final.py::final_text（元 final_edge・_final_text のノードの並び）
- line.md L-G52: workflows/.shared/boundary.py::run・workflows/.shared/boundary.py::guarded_imports
- line.md L-G53: lib/stopby.py（メイングラフの語 start-refused・needs-human・line-script も表 REASONS に在る）
- line.md L-G54: lib/stopby.py（メイングラフの語と人の止めの頭 HUMAN と人待ちの印 WAITING も）、承認ノードの語は lib/answer.py。メイングラフの script は定数を引く。lib を読めない時の出力の写しは workflows/.shared/boundary.py::LINE_SCRIPT・workflows/line/scripts/result.py::LINE_SCRIPT だけ
- line.md L-G55: 無し（#74 の head docs/design.md の `順と関所` の止めの行と「能力の棚卸し」の止め札の行。今は `workflow cancel` で止まり報告は出ない。report は「request:」で始まる一言だけを止め札と読む＝lib/outcome.py::_human_stop）
- line.md L-G56: workflows/line/works-factory-line.yaml の頭の `interactive: true`
- line.md L-W01: workflows/line/works-factory-line.yaml の nodes（workflows/line/works-factory-line.yaml::start から workflows/line/works-factory-line.yaml::result まで）
- line.md L-W02: yaml の when:（workflows/line/works-factory-line.yaml::plan-rounds `judge.ready`・workflows/line/works-factory-line.yaml::fix `answer-before-fix.go`・workflows/line/works-factory-line.yaml::test-gate-final `fixed.done && redepth.stop_reason==''`・workflows/line/works-factory-line.yaml::merge-apply）
- line.md L-W03: judge のサブグラフの中（main workflows/judge/works-factory-judge.yaml::intake・workflows/judge/works-factory-judge.yaml::pr-scan・workflows/judge/works-factory-judge.yaml::premises-loop・workflows/judge/works-factory-judge.yaml::purpose-prep・workflows/judge/works-factory-judge.yaml::world-intake・workflows/judge/works-factory-judge.yaml::spec-loop）
- line.md L-W04: 無し（#74 の head docs/design.md の「能力の棚卸し」の包みの行が「落とす」と決めた）
- line.md L-W05: `$judge.output.units/judgment` を plan・plan-review へ（workflows/line/works-factory-line.yaml::plan・workflows/line/works-factory-line.yaml::plan-review-run）、fix へは中継の fix-in が集めた `$fix-in.output.units/judgment`（workflows/line/works-factory-line.yaml::fix-in・workflows/line/works-factory-line.yaml::fix。固定材料の run は写しの値）。後ろは workflows/line/scripts/judged.py::judged から
- line.md L-W06: judge の出力ノードが ready:false と stop_reason を返し、judge-out（workflows/line/works-factory-line.yaml::judge-out）が受けて collect に届く
- line.md L-W07: メイングラフの design-only（plan-review の形 design。lib/boardview.py::open_design・lib/boardview.py::_collect_design）→ workflows/line/scripts/fixed.py::no_fix（独立設計・go・差分無し）→ judged・redepth・test-gate-final・eyes（設計は $fixed.output.design）→ ask-final（封じのノードが飛んでも開く）。merge-seal・merge-apply は no_fix で飛ぶ。結末は lib/outcome.py（残りが無ければ no_fix_needed、封じの出力が無いのを切れ目と読まない）。計画の直す義務 0 件の周も workflows/line/scripts/plan_out.py::round_owes_nothing が真なら plan-out の nothing_owed で design-only に入る（#291。結末は round_limit）
- line.md L-W08: lib/judge_accept.py::structure_units（record に {units, paths} を書く）・`verdict` が判定の置き場の `structure-units-dropped.json`（`STRUCTURE_DROPPED_FILE`）に書く
- line.md L-W09: workflows/line/scripts/ask_final.py::structure_missing（計画の出力 `structure` の先の structure-state.json を `structmark.note` で読む。メイングラフの `ask-final` の `structure` ← `$fix-in.output.structure`）
- line.md L-W10: lib/planfile.py::write_brief（`planblk.verify_part` が判定の隣の judge-verify.json を貼る）
- line.md L-W11: workflows/line/works-factory-line.yaml::fix（fix の plan・ripple・depth は `$fix-in.output.*`）
- line.md L-W12: workflows/line/works-factory-line.yaml::plan-rounds（loop_group。`review: $LOOP_PREV.plan-out.output.review` は workflows/line/works-factory-line.yaml::plan）、workflows/line/scripts/plan_out.py::plan_out
- line.md L-W13: workflows/line/works-factory-line.yaml::plan-out・workflows/line/works-factory-line.yaml::plan-rounds-out
- line.md L-W14: メイングラフの fix の with: の answers: $answer-before-fix.output.answer（{decision, text, asked}。asked は $ask-before-fix.output.asked）。一言と戻った単位の行は fix の prep が write_notes（gatemarks.returned_lines）で human-notes.md に置く
- line.md L-W15: lib/answer.py::taken（workflows/line/scripts/gate_answer.py・before_fix_answer.py・replan_answer.py が呼ぶ）
- line.md L-W16: lib/answer.py::taken（ファイルを書き直すだけ）
- line.md L-W17: workflows/line/works-factory-line.yaml の refix-run の with:（plan・depth は `$replan.output.*`、ripple は `$answer-replan.output.fix_ripple`〔案の直しが作り直した一覧。作り直せなかった時だけ 1 回目の案の一覧: workflows/line/scripts/replan_answer.py::fix_ripple → lib/replan.py::remade_ripple〕、only_items は `$fix.output.replan_items`、answers は `$answer-replan.output.fix_answers`、notes は `$answer-replan.output.fix_notes`〔採った項目の事前審査の穴のうち人に聞く種類でない物。replan_answer.py の fix_notes → lib/replan.py::fix_notes・lib/replan.py::FACES_HEAD〕、prior_conflicts・plan_review）。fix の prep が notes を human-notes.md に足す（lib/fixboard.py::write_notes）
- line.md L-W18: fix の入力 prior_conflicts（メイングラフの refix-run の with: `$fix.output.conflicts`）。prep が lib/fixboard.py::adopt_prior_pass で、ポインタの先のフォルダの conflicts.json の行を印 prior_pass つきで写し（lib/conflict.py::adopt_prior。直す項目の待つ行を AMENDED へ）、TDD のループの状態を 1 回目のループとして写す。組の子は fixboard.adopt_inputs で親から写す。conflict.second_pass が真になり、lib/fixgates.py の事後の関門が 1 回目の裁定 fix_test_scope の範囲を許す
- line.md L-W19: fix の入力 plan_review（メイングラフの fix に `$plan-rounds.output.review`、refix-run に `$replan-review.output.review`）。prep が置き場の p2.plan_review.json に写し（組の子も写す）、受け付け（lib/fixboard.py::accept_reply の plan_faces の照らし plan_face_errors）が答えの無い key・事前審査に無い key・重複を拒む。差分の審査の材料（workflows/fix/scripts/delta_cut.py・workflows/fix/scripts/refix_prep.py・workflows/fix/scripts/collect.py が lib/fixboard.py::plan_review_file を渡す）の out.p2.plan_review が埋まる。指示書 direct.md は元の字
- line.md L-W20: fix の diff の隣の handoffs.json（lib/fixbeside.py。書き手は fix の collect、子の結果の handoffs で運ぶ）を workflows/line/scripts/ask_final.py の `needs`（HANDOFF_REASON）とノード（fixbeside.HANDOFF_HEAD）、lib/runreport.py の `_decisions`（冒頭 2 行目の件数）が読む
- line.md L-W21: fix の diff の隣の closure.json（lib/fixbeside.py の `closure_lines(mismatched_only)`）を ask_final の `needs`（MISMATCH_REASON）が読む
- line.md L-W22: workflows/line/scripts/ask_final.py::needs・workflows/line/scripts/ask_final.py::final_needs・workflows/line/scripts/ask_final.py::final_head（前提の検算の escalate と封じられなかった差分を足した）
- line.md L-W23: workflows/line/scripts/ask_final.py::ask（workflows/line/works-factory-line.yaml::ask-final）
- line.md L-W24: workflows/line/scripts/ask_final.py::asked_conflicts（fixed の conflicts のポインタの先ごとに lib/conflict.py::human_lines）と needs・conflict_section
- line.md L-W25: workflows/line/scripts/ask_final.py::ask。eyes が落ちれば merge-seal・ask-final・merge-apply が飛ぶ（workflows/line/works-factory-line.yaml::merge-seal・workflows/line/works-factory-line.yaml::ask-final・workflows/line/works-factory-line.yaml::merge-apply）
- line.md L-W26: lib/answer.py::taken（workflows/line/scripts/gate_answer.py::take）→ collect の gate_final（workflows/line/scripts/collect.py::GATES）→ report
- line.md L-W27: answer-final の go:false で merge-apply が飛ぶ（workflows/line/works-factory-line.yaml::merge-apply）
- line.md L-W28: workflows/line/scripts/ask_final.py::final_tests（test-gate-final の出力の欄 by・suites_line・log・baseline_line・reason を with: で受け、lib/declared_checks.py::gate_values で字にする）と tests_lines（作業ツリーはノードの cwd）
- line.md L-W29: workflows/line/scripts/ask_final.py::delta_lines（fix の delta_review の回数と通ったか）。穴の数と枝の名札・手直しの結果は got の branch_rows（今は空）で「取れない」と書く
- line.md L-W30: workflows/line/scripts/ask_final.py::judged_returns・workflows/line/scripts/ask_final.py::rejudge_rows（lib/runreport.py::rejudge_lines。ask-final の入力 units・rejudged・first_units・fix_units）
- line.md L-W31: workflows/line/scripts/ask_final.py::after_rows（structmark.after_lines: 数・柵の増え・新しい名・修正案の外れの訳）
- line.md L-W32: workflows/line/scripts/ask_final.py::review_rows（plan-rounds と replan-review の review の隣の gate-passes.json と gate.json の converge）
- line.md L-W33: workflows/line/scripts/ask_final.py::eye_lines（平易な名の目の行・前提の検算の語・残りの数え）
- line.md L-W34: workflows/line/scripts/ask_final.py::final_text: 例で証明できない判定の問い（runreport.unproven_lines）・同じ run で直した修正案の項目（amend_rows・AMEND_HEAD）・持ち越した単位（runreport.split_line を 1 行目に）・残りの数え（eye_lines）
- line.md L-W35: workflows/line/scripts/ask_final.py::question_lines（gatemarks.quote で引き、この承認ノードの答えは問いに答えないと添える）
- line.md L-W36: workflows/line/scripts/ask_final.py::ledger・workflows/line/scripts/ask_final.py::ledger_rows（held_lines・answered_lines・unmatched_answer_lines・unread_hold_lines）と question_lines
- line.md L-W37: workflows/line/scripts/ask_final.py::keep（開いた文を run の置き場の gates/final-gate.md に書く）。文の末尾が控えのパスを名指す
- line.md L-W38: workflows/line/scripts/ask_before_fix.py::ask・workflows/line/scripts/ask_before_fix.py::gate_text（細目は L-G17〜L-G28）
- line.md L-W39: workflows/line/scripts/ask_before_fix.py・ask_replan.py・ask_final.py が止め（needs-human）と deferred・widened・reasons を返し、collect が report の入力 stops・deferred・widened・final-reasons に渡す。lib/runreport.py::_line_lines・lib/runreport.py::_stop_lines
- line.md L-W40: 再審は 2 度目の修正の後（部分 D1）: fixed が 1 回目と 2 度目の修正役の異議をつないで rejudge を決め（workflows/line/scripts/fixed.py::fixed）、yaml の rejudge-run は `depends_on: [fixed]`・`when: $fixed.output.rejudge == true`、judged は fixed と rejudge-run の後、試験の関門（final）は judged の止めを読む（`when` に `$judged.output.stop_reason == ''`）
- line.md L-W41: 無し。judge を新しく挟み、異議を入力で渡す（workflows/line/works-factory-line.yaml::rejudge-run）
- line.md L-W42: 判定のサブグラフが再審の judgment の隣に rejudge-exit.json・rejudge-diff.json を書き（lib/judge_accept.rejudge_collect）、メイングラフの workflows/line/scripts/judged.py::compared と lib/runreport.py::rejudge_lines・lib/runreport.py::rejudge_opened・lib/runreport.py::rejudge_lowered・lib/runreport.py::rejudge_changes はそれを読むだけ（名は lib/report.py::REJUDGE_EXIT・lib/report.py::REJUDGE_DIFF。報告は report の入力 rejudge の judgment の隣を読む）
- line.md L-W43: workflows/line/works-factory-line.yaml::eyes（eyes の units・judgment・purpose・world ＝ `$judged.output.*`）・workflows/line/works-factory-line.yaml::ask-final（ask-final の judgment）
- line.md L-W44: workflows/line/scripts/after_fix.py::decide、workflows/line/works-factory-line.yaml::replan（ruling・conflicts）
- line.md L-W45: メイングラフの replan-review の with: の conflicts・gate_answers（申し出と裁定・修正前の承認ノードの答え）。往復の中の plan-review-run には渡さない（修正前の承認ノードより前）
- line.md L-W46: workflows/line/scripts/ask_replan.py::ask
- line.md L-W47: workflows/line/scripts/fixed.py::fixed
- line.md L-W48: 2 度目の修正の置き場は 1 回目の行を写して持ち（L-W18）、この段で新しく fix_plan_item と裁いた行に LATE_REPLAN_PROMISE が出る（lib/conflict.py::write_rulings）。fix の出力ノード collect が段を抜ける時に conflict.second_pass なら lib/replan.py::close（CLOSE_WHY）で諦めた行にする。メイングラフの fixed は 2 度目の控えのポインタを運び（1 回目の行を 2 度数えない）、ask_final の asked_conflicts が human_lines で並べる
- line.md L-W49: workflows/line/scripts/fixed.py::fixed
- line.md L-W50: workflows/line/works-factory-line.yaml::fix（fix.depth）・workflows/line/works-factory-line.yaml::redepth・workflows/line/works-factory-line.yaml::eyes（eyes.depth ＝ `$redepth.output.depth`）
- line.md L-W51: collect の with: redepth（$redepth.output）→ report の入力 redepth → lib/runreport.py::_depth_lines（lib/depth.lines）
- line.md L-W52: workflows/line/works-factory-line.yaml::test-gate-final
- line.md L-W53: test-gate のサブグラフの中（test-gate の区分）
- line.md L-W54: workflows/line/scripts/ask_final.py::after_rows（null は NO_AFTER の 1 行。failed は structmark.after_counts が理由を添える）
- line.md L-W55: workflows/line/works-factory-line.yaml::eyes（eyes.design ＝ `$plan-rounds.output.design`）
- line.md L-W56: workflows/line/scripts/fixed.py::fixed（plan・ripple。2 度目の修正が走れば replan-out の got から）→ yaml eyes の plan・ripple は $fixed.output.*（部分 A で閉じた）
- line.md L-W57: fix の出力 x_scalars（組ごとの値を名ごとに足す。lib/fixboard.py::x_scalars）と changed.premise_drift_note（lib/fixboard.py::changed_marks・lib/fixboard.py::reply_marks）。メイングラフの fixed が 2 度目の値を優先して合わせ、eyes に `x_scalars: $fixed.output.x_scalars` と changed を渡す
- line.md L-W58: workflows/line/works-factory-line.yaml::judge（judge）・workflows/line/works-factory-line.yaml::plan（plan）・workflows/line/works-factory-line.yaml::replan（replan）・workflows/line/works-factory-line.yaml::rejudge-run（rejudge）・workflows/line/works-factory-line.yaml::eyes（eyes start_answers）・workflows/line/works-factory-line.yaml::plan-review-run（plan-review answers）
- line.md L-W59: workflows/line/works-factory-line.yaml::merge-seal（merge-seal）・workflows/line/works-factory-line.yaml::merge-apply（merge-apply）
- line.md L-W60: yaml collect・report・result の all_done と collect・result の always_run（report は include で Archon が always_run を捨てる: packages/workflows/src/schemas/dag-node.ts 1085-1091・1911-1914 行。回し直した collect の出力が変われば report の中の控えを捨てる: dag-executor.ts 9716-9727 行）（部分 A で閉じた）
- line.md L-W61: 型つきの成果物 tdd-unit を report が読む（main lib/runreport.py::_tdd_stages）
- line.md L-W62: workflows/line/scripts/result.py::result・workflows/line/scripts/result.py::FIXED
- line.md L-W63: workflows/.shared/boundary.py::run・workflows/.shared/boundary.py::guarded_imports
- line.md L-W64: 無し（#74 の head docs/design.md の `順と関所` の止めの行と「能力の棚卸し」の止め札の行が持ち主の答え待ち）
- line.md L-W65: workflows/line/works-factory-line.yaml::fix-in・workflows/line/works-factory-line.yaml::test-gate-base（固定材料の run は直す前のテスト・判定・計画の往復・修正前の承認ノードを飛ばし、fix から後ろは fix-in の値を読む）（#509 で戻した）
- line.md L-W66: tests/workflows/test_line.py::LineWiringCase、tests/e2e/test_line_scenarios.py
- line.md L-W67: tests/workflows/test_line.py の表 UNPASSED（渡さない入力と訳）
- line.md L-D01: lib/depth.py::unit_depth。呼び手 lib/planfile.py::collect
- line.md L-D02: lib/depth.py::wiring
- line.md L-D03: lib/depth.py::decide_doc・lib/depth.py::run_depth
- line.md L-D04: yaml の fix.depth（$fix-in.output.depth）・refix-run.depth（$replan.output.depth）
- line.md L-D05: lib/depth.py::raise_doc、workflows/line/scripts/redepth.py::redepth
- line.md L-D06: workflows/line/scripts/redepth.py::redepth
- line.md L-D07: workflows/line/scripts/redepth.py::redepth
- line.md L-D08: workflows/line/scripts/redepth.py::pending_signals（gatemarks.ledger_beside・gatemarks.pending。判定の問いの台帳と依頼の answers と修正前の承認ノードの答え。台帳が読めなければ上げる側）
- line.md L-D09: workflows/line/scripts/redepth.py::redepth、workflows/line/works-factory-line.yaml::redepth
- line.md L-D10: workflows/line/scripts/redepth.py::wide_signals（depth.run_wide。計画の欄と fixed の差分。counted を返し報告の深さの行に出る）と fix の中の lib/fixboard.py::redepth
- line.md L-D11: yaml の eyes.depth（$redepth.output.depth）→ workflows/eyes/scripts/prep.py::out の run_eyes（depth.skip_reason）
- line.md L-D12: workflows/fix/scripts/delta_cut.py（fixboard.redepth の skip_reason で delta/skipped.json を書いて go: false。後ろのレンズ・手直しも飛ぶ）
- line.md L-D13: lib/runreport.py::_depth_lines（redepth の出力 {depth, raised, counted} を lib/depth.lines の形で。単位ごとの数・上げた信号・run の広さの数え・軽量で省いた物）
- line.md L-D14: workflows/line/scripts/redepth.py::fallback は works:line-script で止め、試験の関門から先が飛ぶ（workflows/line/works-factory-line.yaml::test-gate-final）
- line.md L-D15: workflows/line/scripts/redepth.py::merged（直した案の行で単位ごとに置き換え、1 回目の単位の行を残す）
- line.md L-D16: workflows/line/works-factory-line.yaml の `max_iterations: 20` と plan-out の `with:` の `round_limit: 20`、workflows/line/scripts/plan_out.py::plan_out（round ≥ round_limit で done）。Archon は上限に達したループを落とす（packages/workflows/src/dag-executor.ts:5222）ので done で先に抜ける
- line.md L-D17: workflows/line/works-factory-line.yaml::plan（`$LOOP_PREV.plan-out.output.review`）
- line.md L-D18: 新しい会話で、保存した案と指摘を読む
- line.md L-D19: workflows/line/scripts/ask_before_fix.py::ask: 事前審査が設計だけの行（種類 design_only。止まった理由つき）を返していれば STUCK_ITEM・DESIGN_ONLY_ITEM を足し直さない
- line.md L-D20: メイングラフが plan-review-run に `with:` の `round_limit: 20` を渡し、lib/boardview.py::_take が上限の周（計画の周 ≥ round_limit）に converge の at_cap を渡し、plan-review は stalled と理由の行（converge の CAP_WHY）を questions で返す。workflows/line/scripts/ask_before_fix.py::ask の stalled の枝が承認ノードを開ける
- line.md L-D21: workflows/line/scripts/ask_before_fix.py::ask
- line.md L-D22: lib/runreport.py::_converge_lines（事前審査の出力 review の隣の gate.json の converge を lib/gatemarks.converge_of で。計画の往復と案の直しの事前審査）
- line.md L-D23: workflows/line/scripts/after_fix.py::decide、workflows/line/works-factory-line.yaml::replan
- line.md L-D24: メイングラフ workflows/line/works-factory-line.yaml の replan の with:（ruling: $fix.output.replan_items・conflicts: $fix.output.conflicts）
- line.md L-D25: メイングラフの replan-review の with: の conflicts: $fix.output.conflicts（boardview.open_pass が項目ごとの申し出と裁定の行を貼る）
- line.md L-D26: メイングラフの replan-review の with: の gate_answers: $answer-before-fix.output.answer（{decision, text, asked}。boardview.take_gate_answers が human_items に積む）
- line.md L-D27: workflows/line/scripts/ask_replan.py::ask
- line.md L-D28: workflows/line/scripts/ask_replan.py::ask
- line.md L-D29: workflows/line/scripts/ask_replan.py が widened（lib/replan.widen_text の字。元 WIDEN_OP の trace の代わりにこのノードの出力が run の記録に 1 度残る）→ collect → report の入力 widened → lib/runreport.py::_line_lines
- line.md L-D30: workflows/line/scripts/ask_replan.py::ask
- line.md L-D31: workflows/line/scripts/ask_replan.py::section（L-G44 と同じ）
- line.md L-D32: workflows/line/scripts/fixed.py::fixed、workflows/line/works-factory-line.yaml::test-gate-final（止めの語 human:gate-replan）
- line.md L-D33: workflows/line/scripts/fixed.py::fixed。replan.ready が false だと refix が飛び、fixed.done が偽で試験の関門から先が全部飛ぶ
- line.md L-D34: workflows/line/scripts/replan_answer.py::fix_answers
- line.md L-D35: workflows/line/scripts/replan_answer.py::fix_notes（lib/replan.py::fix_notes・lib/replan.py::FACES_HEAD。人に聞く種類は lib/boardview.py::HUMAN_FACE_KINDS）→ answer-replan の出力 fix_notes → refix-run の入力 notes
- line.md L-D36: workflows/line/works-factory-line.yaml::refix-run（`only_items: $fix.output.replan_items`）
- line.md L-D37: workflows/line/scripts/fixed.py::fixed
- line.md L-D38: 2 度目の修正の段で新しく裁いた fix_plan_item の行は、fix の出力ノード collect が段を抜ける時に CLOSE_WHY で諦めた行にし（lib/replan.py::close。CLOSE_WHY の住処は lib/replan.py、lib/outcome.py は引く）、案の段には戻らない（after-fix は 1 回目の replan_items だけを読む）。メイングラフの fixed は 2 度目の控えを運ぶ
- line.md L-D39: lib/replan.py::amend_lines・lib/replan.py::AMEND_HEAD（項目ごとの 1 行）を lib/runreport.py::_amend_lines とメイングラフの workflows/line/scripts/ask_final.py が読む。項目ごとの聞いたかは案の直しの承認ノードの答えの asked（ask-replan の asked → answer-replan）
- line.md L-D40: gates/gate-replan.json（workflows/line/scripts/gate_answer.py）
- line.md L-D41: メイングラフのノード fixed の rejudge（1 回目と 2 度目の修正役の異議が在り、止めていない）→ rejudge-run の when（部分 D1 で再審を 2 度目の修正の後に移した）
- line.md L-D42: メイングラフのノード fixed の objection は 1 回目と 2 度目の修正役の異議をつないだ文で、rejudge-run は fixed の後（depends_on [fixed]、objection ← `$fixed.output.objection`）。judged・ask-final・報告（lib/runreport.py）も同じ objection を読む
- line.md L-D43: 新しい会話で保存した judge/judgment.json を読む。1 回目の判定が無ければ rejudge-session で止める（main workflows/judge/scripts/rejudge_prep.py）
- line.md L-D44: workflows/line/scripts/judged.py::judged・workflows/line/scripts/judged.py::from_env、workflows/line/works-factory-line.yaml::eyes・workflows/line/works-factory-line.yaml::ask-final
- line.md L-D45: lib/judge_accept.py::diff_units・lib/judge_accept.py::rejudge_collect が再審の出口 rejudge-exit.json に書き、workflows/line/scripts/judged.py::compared と報告の lib/runreport.py::rejudge_opened・lib/runreport.py::rejudge_lowered は読むだけ（書いた時は報告が自分でも比べ直す 2 か所だった）
- line.md L-D46: workflows/line/scripts/judged.py::compared の unread（報告への入口が無い）
- line.md L-D47: lib/runreport.py::rejudge_opened・lib/runreport.py::next_request
- line.md L-D48: workflows/line/scripts/judged.py::judged（rejudge_stop_reason を stop_reason で返す）→ 試験の関門（final）の when が `$judged.output.stop_reason == ''` を読む（部分 A で閉じ、部分 D1 で再審を 2 度目の修正の後に移したので fixed の held から試験の関門の when へ移した）
- line.md L-D49: workflows/line/scripts/ask_final.py::needs・workflows/line/scripts/ask_final.py::left_objection
- line.md L-D50: workflows/line/scripts/start.py::start、workflows/line/works-factory-line.yaml::judge・workflows/line/works-factory-line.yaml::plan・workflows/line/works-factory-line.yaml::rejudge-run・workflows/line/works-factory-line.yaml::replan
- line.md L-D51: lib/carry.py::_prior_failures（start が parts を呼ぶ）（部分 A で閉じた）
- line.md L-D52: lib/carry.py、lib/planfile.py::prior_section、main lib/judge_accept.py::purpose_prep
- line.md L-D53: lib/runreport.py::build（`build` が carry.errors で NEXT_SCHEMA・PRIOR_SCHEMA を 2 つとも照らしてから書き、合わなければ ValueError）、workflows/line/scripts/result.py::from_env（届かなかった lib/carry.py の `save` は #232 で消した）
- line.md L-D54: lib/carry.py::carry_ci・lib/carry.py::main（python3 -I lib/carry.py carry-ci）と README.md の使い方 6（部分 A で閉じた）
- line.md L-D55: 無し（#74 の head docs/design.md の「能力の棚卸し」の周の鎖の行で「メイングラフの後ろ・段 3」）
- line.md S01: `lib/conflict.py::second_pass` と `lib/fixgates.py::problems` は同じ形のまま。ただ `refix` は自分の置き場（`fix/refix-run/`）に書く（`lib/fixgates.py` のモジュールの docstring、試験 `tests/workflows/test_fix.py::BlockScriptsCase.test_prep_under_refix_writes_its_own_place`）。fix の入力（`FX` の inputs:）には 1 回目の申し出と裁定を受ける欄が無く、メイングラフの `refix` の `with:`（`LY` の refix）も渡していない → **開いている**（#94 は「メイングラフを入れた後の issue」に回した） → 部分 D1 で閉じた（fix の入力 `prior_conflicts` ← `$fix.output.conflicts`。prep が 1 回目の行とループの状態を写す `lib/fixboard.py::adopt_prior_pass`。L-W18・F018・F023・F044・F216）
- line.md S02: `workflows/fix/scripts/delta_cut.py::main`・`workflows/fix/scripts/refix_prep.py::main`・`refix2_prep.py`（今は無い）が `plan_review=None` を渡す。`lib/fixboard.py::NODE_READS` は `out.p2.plan_review` の欄を組むが、値はいつも null。修正役の指示書 `workflows/fix/commands/fix-rules/direct.md` は「今は空配列」と書く。fix の入力（`FX` の inputs:）にも、メイングラフの `fix`・`refix` の `with:`（`LY` の fix・refix）にも事前審査の出力が無い → **開いている**（fix に入力を足し、メイングラフが `$plan-rounds.output.review`（2 度目は `$replan-review.output.review`）を渡す必要がある） → 部分 D1 で閉じた（fix の入力 `plan_review`・受け付けの `plan_face_errors`・差分の審査の材料。TDD の役の指示書への貼りは戻していない: 部分 D1 の閉じる行に無い。L-W19・F130・F302）
- line.md S03: fix の出力（`FX` の出力ノードの required）に欄が無い。`lib/report.py` の docstring には `handoff_lines` の行だけが残り、関数は無い。`LS/ask_final.py` は読まない。一方で修正役の指示書 `workflows/fix/commands/fix-rules/common.md` は今も「機械が人に見せる一覧に載せる」と書いている（指示書の約束が嘘になっている）→ **開いている**
- plan.md P001: lib/gatemarks.py::duty（plan は lib/planfile.py::_owed_units・lib/planfile.py::plan_slots が read_judgment の添えた問いの台帳の見え方で呼ぶ。fix の lib/fixboard.py::group_owed と同じ口）
- plan.md P002: lib/gatemarks.py::duty が lib/gatemarks.py::returned を戻す（plan は始めの記録の依頼の answers・判定の結び・素材の状態から。承認ノードの答えは plan より後なので fix の側だけ）。held_by_rulings は fix の lib/fixboard.py::owed_units_but_asked
- plan.md P003: lib/planfile.py::slots・lib/planfile.py::named・lib/planfile.py::open_round（slots.json を書く）・lib/planfile.py::take_plan
- plan.md P004: lib/planfile.py::fix_plan_covers_units・lib/planfile.py::take_plan（lib/planfile.py::COVERS_REJECT）
- plan.md P005: lib/planfile.py::fix_plan_covers_units
- plan.md P006: lib/planfile.py::fix_plan_covers_units・lib/planfile.py::take_plan（`{COVERS_REJECT} {allowed}`。lib/planfile.py::COVERS_REJECT）
- plan.md P007: lib/planfile.py::named（整数だけ戻す）・lib/planfile.py::fix_plan_covers_units（「写さずに、貼られた単位の no で指せ」）
- plan.md P008: lib/planfile.py::not_allowed・lib/planfile.py::take_plan（lib/planblk.py::NOT_OWED_REJECT）
- plan.md P009: lib/planfile.py::plan_slots・lib/planfile.py::units_section（「入れてもよい（人の答え待ちの…）」）
- plan.md P010: lib/planfile.py::stuck_reason・lib/planfile.py::open_round（直す義務 lib/gatemarks.py::duty が依頼の答えで開いていない単位を戻すと起きる）
- plan.md P011: lib/planfile.py::open_round（lib/planfile.py::NOTHING_OWED）・workflows/plan/works-factory-plan.yaml::structure-measure・workflows/plan/works-factory-plan.yaml::plan-loop の when
- plan.md P012: lib/planfile.py::take_plan（lib/planfile.py::MALFORMED_REJECT）、lib/replan.py::_malformed
- plan.md P013: lib/planfile.py::take_plan（reasons の並び）
- plan.md P014: lib/planfile.py::take_plan（lib/planblk.py::NO_NARROW_REJECT）・役の型の required に no_narrow（workflows/plan/works-factory-plan.yaml::plan-writer）
- plan.md P015: lib/planfile.py::take_plan（lib/planblk.py::RECOMMEND_REJECT）
- plan.md P016: lib/planfile.py::take_plan（reply.json・p2.fix_plan.json に欄のまま置く）
- plan.md P017: lib/planmarks.py::gaps（元と字のまま）・lib/planfile.py::take_plan
- plan.md P018: lib/planmarks.py::gaps
- plan.md P019: lib/planmarks.py::gaps・lib/planmarks.py::glob_problem
- plan.md P020: lib/planmarks.py::_file_name・lib/planmarks.py::gaps
- plan.md P021: lib/planfile.py::_save・lib/planfile.py::take_plan
- plan.md P022: lib/planmarks.py::_limit・lib/planmarks.py::split
- plan.md P023: lib/planfile.py::base_test_texts・lib/planfile.py::take_plan（`_trace(BASE_TESTS_UNREAD_OP)`）
- plan.md P024: lib/planmarks.py::save（trace を渡さないので周のフォルダの trace.jsonl に直に書く）・lib/planfile.py::_save
- plan.md P025: lib/planfile.py::_save（置けなければ置いた控えを消し、round.json の why に控えの名。出力 halt で plan_accept が拒否に数えずループを止める）（#120）
- plan.md P026: lib/planfile.py::answer_tables・lib/planfile.py::take_plan・lib/planmarks.py::structure_gaps
- plan.md P027: lib/planfile.py::write_brief（write_brief の structmark.plan_section）
- plan.md P028: lib/structmark.py::MISSING・lib/structmark.py::plan_section・lib/planfile.py::write_state・lib/planfile.py::write_brief
- plan.md P029: lib/planfile.py::_measured_units・lib/planfile.py::units_section
- plan.md P030: lib/planfile.py::write_brief（worldmark.section・PLAN_ASK）・lib/planfile.py::answer_tables
- plan.md P031: lib/planfile.py::prescriptions・lib/planfile.py::prescription_section・lib/planfile.py::write_brief
- plan.md P032: workflows/plan/commands/fix-plan.md
- plan.md P033: lib/planblk.py::HEAD・lib/planblk.py::head（前提の部品）・lib/planfile.py::write_brief（write_brief が頭に置く）
- plan.md P034: lib/planfile.py::units_section
- plan.md P035: lib/planfile.py::REPO_LINE・lib/planfile.py::repo_line・lib/planfile.py::write_brief、lib/boardview.py::open_pass・lib/boardview.py::review_body、lib/startrec.py::read_rev・lib/startrec.py::diff_base（読む版は始めの記録の review_rev、BASE は入口の差分の根 input.base.rev。どちらも無い前の版の控えは base_rev。行は repo_line の 1 か所が描く）
- plan.md P036: lib/planfile.py::write_brief（`_neighbor(judgment_dir, "pr-excluded.json")`）
- plan.md P037: lib/planblk.py::verify_part・lib/planfile.py::write_brief
- plan.md P038: lib/planfile.py::lib_section・workflows/plan/scripts/plan_prep.py::main
- plan.md P039: lib/planfile.py::POLICY_PART・lib/planfile.py::write_brief
- plan.md P040: lib/planfile.py::write_brief
- plan.md P041: lib/planfile.py::prior_section・入力 prior_failures（workflows/plan/works-factory-plan.yaml の inputs）。メイングラフは渡す（workflows/line/works-factory-line.yaml::plan・workflows/line/works-factory-line.yaml::replan）
- plan.md P042: lib/rolekit.py::lang_line（workflows/plan/scripts/plan_prep.py::main が組んで渡す）・lib/planfile.py::write_brief
- plan.md P043: lib/planfile.py::SPEC_HEAD・lib/planfile.py::write_brief
- plan.md P044: lib/planfile.py::UNREAD_INPUTS_HEAD・lib/planfile.py::write_brief・workflows/plan/scripts/plan_prep.py::main
- plan.md P045: workflows/plan/scripts/round.py::opened・lib/planfile.py::pointed
- plan.md P046: lib/rolekit.py::REJECT_LINE・lib/rolekit.py::reject_file・lib/rolekit.py::compose・lib/planfile.py::write_brief
- plan.md P047: workflows/plan/works-factory-plan.yaml::plan-loop・workflows/plan/works-factory-plan.yaml::plan-writer-fix・workflows/plan/scripts/plan_accept.py::main・lib/planfile.py::why_not_ready
- plan.md P048: workflows/plan/works-factory-plan.yaml::plan-writer
- plan.md P049: lib/planfile.py::snap_tree・lib/planfile.py::moved（workflows/plan/scripts/plan_prep.py::main が plan/r<k>/tree.json を置き、take_plan・take_replan が accept.tree_moved で比べる。拒みの頭は planblk.READONLY_MOVED・NO_TREE）（#120）
- plan.md P050: lib/planfile.py::open_round（review/p2.plan_review.json）
- plan.md P051: lib/planfile.py::next_round・lib/planfile.py::open_round
- plan.md P052: workflows/plan/scripts/round.py::failed・workflows/plan/scripts/round.py::main
- plan.md P053: workflows/plan/scripts/plan_collect.py::failed・workflows/plan/scripts/plan_collect.py::main・lib/planfile.py::placeholders
- plan.md P054: workflows/plan/works-factory-plan.yaml::plan
- plan.md P055: lib/planfile.py::ripple_items・lib/ripple.py::build・workflows/plan/scripts/ripple_items.py
- plan.md P056: lib/planfile.py::ripple_units・lib/planfile.py::write_brief（ripple.units_section を貼る。lib/ripple.py::units_section）・workflows/plan/scripts/ripple_units.py（境の boundary.RUNTIME_COPY_DIRS）
- plan.md P057: lib/reads.py・lib/planfile.py::collect_reads・workflows/plan/scripts/plan_reads.py（ノード plan-reads）・bin/_lib/record-read.py・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- plan.md P059: lib/planfile.py::collect・lib/planfile.py::owed_order・lib/depth.py::decide_doc・lib/depth.py::unit_depth・workflows/plan/scripts/plan_collect.py::collected（共有ボードを読む lib/depth.py の `decide` は届かなかったので #232 で消した）
- plan.md P060: lib/planfile.py::measure・lib/stage_a.py::measure_unit・workflows/plan/scripts/structure_measure.py::main
- plan.md P061: lib/planfile.py::_measured_units・lib/planfile.py::measure（units.json と skipped-units.json）・lib/planfile.py::units_section
- plan.md P062: lib/stage_a.py::measure_unit・lib/planfile.py::measure
- plan.md P063: lib/stage_a.py::read_units・lib/planfile.py::measure
- plan.md P064: lib/planfile.py::measure
- plan.md P065: lib/context.py::concepts・lib/context.py::find（字のまま）
- plan.md P066: lib/context.py::find・lib/context.py::concepts
- plan.md P067: lib/context.py::rules・lib/planfile.py::measure（policy_path は start の方針。workflows/plan/scripts/structure_measure.py::main が lib/policy.py::frozen_copy で渡す）
- plan.md P068: lib/eye.py::stamp（lib/planfile.py::measure が呼ぶ）
- plan.md P069: lib/eye.py::due・workflows/plan/works-factory-plan.yaml::structure-eye-loop `when: "$structure-measure.output.eye == true"`
- plan.md P070: lib/planfile.py::structure_key・lib/planfile.py::structure_dir・lib/planfile.py::measure（reused）
- plan.md P071: lib/planfile.py::open_round（why の在る周の structure は `r<k>/structure`）・lib/planfile.py::write_state `write_state(skipped=…)`・workflows/plan/scripts/structure_state.py
- plan.md P072: lib/eye.py::render（字のまま）
- plan.md P073: lib/eye.py::FORMS（試験の lib/tests/test_structure_eye.py が今の works の設計書の一覧を字で持って照らす）（#120）
- plan.md P074: lib/eye.py::prep
- plan.md P075: lib/eye.py::_cut
- plan.md P076: workflows/plan/works-factory-plan.yaml::structure-eye・workflows/plan/commands/structure-eye.md（元と字のまま）
- plan.md P077: workflows/plan/works-factory-plan.yaml::structure-eye・lib/design-row.schema.json
- plan.md P078: lib/eye.py::problems・lib/eye.py::_pointer
- plan.md P079: lib/eye.py::problems
- plan.md P080: lib/eye.py::problems・lib/eye.py::MIN_UNDECIDED
- plan.md P081: lib/eye.py::accept・lib/eye.py::ROUTE_REASON
- plan.md P082: lib/eye.py::accept・workflows/plan/works-factory-plan.yaml::structure-eye-loop
- plan.md P083: lib/planfile.py::_outcome・lib/planfile.py::write_state・workflows/plan/works-factory-plan.yaml::structure-state（trigger_rule: all_done）
- plan.md P084: lib/planfile.py::write_state（wall_s = 実測の秒＋目の秒）・lib/eye.py::wall
- plan.md P085: workflows/plan/works-factory-plan.yaml::structure-state（structure-state は all_done）・workflows/plan/works-factory-plan.yaml::plan-loop（plan-loop は none_failed_min_one_success）・lib/structmark.py::plan_section
- plan.md P086: lib/planfile.py::keep_state（workflows/plan/scripts/structure_state.py。書けない周は周のフォルダに「構造の控えを書けない」の訳で failed を置き、round.json の structure を替えて計画へ進む）（#120）
- plan.md P087: workflows/plan/works-factory-plan.yaml::plan-loop（structure-state が落ちれば plan-loop は none_failed_min_one_success で飛ぶ）・出力ノード plan は ready: false
- plan.md P088: lib/structmark.py::plan_section・lib/planfile.py::write_brief（`structmark.plan_section(structure_dir_)`）
- plan.md P089: workflows/plan/scripts/plan_collect.py::collected・lib/planfile.py::placeholders
- plan.md P090: lib/measure.py（字のまま）
- plan.md P091: lib/measure.py
- plan.md P092: lib/measure.py
- plan.md P093: lib/measure.py
- plan.md P094: lib/measure.py
- plan.md P095: lib/measure.py
- plan.md P096: lib/measure.py
- plan.md P097: lib/concepthome.py（字のまま。包みの system prompt でなく材料の末尾に貼る、と文だけ直した）
- plan.md P098: lib/concepthome.py
- plan.md P099: lib/conceptfence.py（`changed`・`scan_change` が skip_prefix を受ける形に変わった）
- plan.md P100: docs/concepts.md・docs/concepts.json と、それを照らす tests/layers/test_concept_fences.py（CI の `tests` の check。checkout は全履歴を取り、main の表を引けなければ赤）
- plan.md P101: lib/judge_accept.py::_unit_file_paths（judge の持ち物）
- plan.md P102: lib/converge.py::decide・lib/converge.py::not_fewer（古い works 0.2.65 の e9a82061 の写し）。計画の側の写し lib/planfile.py::converge_record も同じ add_pass → decide を呼ぶ
- plan.md P103: lib/converge.py::_item_states（写し）。計画の側は lib/planfile.py::converge_record が lib/converge.py::add_pass を呼び、add_pass が _item_states を呼ぶ
- plan.md P104: lib/boardview.py::_take が converge.record_pass を呼ぶ。写すのは指示書（prompt.md）と木の下請けのファイルだけ（案・欄は計画のサブグラフの plan/r<k>/ に、審査は plan-review/pass-<k>/review.json に別に残る）
- plan.md P105: lib/converge.py::revise_section（共有ボードの代わりに控えを受ける）を lib/planfile.py::_prior_section が 2 周目の材料に貼る
- plan.md P106: lib/planfile.py::_prior_section、lib/planfile.py::open_round が受けた review を plan/r<k>/review/p2.plan_review.json に写す
- plan.md P107: lib/planfile.py::units_section（`units_section(filled=…)`）・lib/converge.py::filled_units（lib/planfile.py::write_brief が渡す）
- plan.md P108: lib/converge.py::answer_gaps、lib/planfile.py::take_plan（ANSWERS_REJECT）
- plan.md P109: lib/converge.py::splice、lib/planfile.py::take_plan（DROPPED_OP は converge.DROPPED_OP を直に使う）
- plan.md P110: lib/planfile.py::take_plan（`extra = {block_answers}`）→ lib/boardview.py::open_pass（`converge.split("plan-revise", fix_plan)` → `converge.note_answers`）
- plan.md P111: lib/boardview.py::_take（converge.resolved_gaps）
- plan.md P112: lib/boardview.py::_review_material（converge.review_section）
- plan.md P113: lib/boardview.py::collect（stalled = outcome in STUCK）、workflows/line/scripts/plan_out.py::plan_out（done = ready 偽・pass・stalled・round ≥ with: の round_limit（20））、workflows/line/works-factory-line.yaml::plan-rounds（loop_group `plan-rounds` が plan・plan-review-run・plan-out を回す）
- plan.md P114: workflows/line/works-factory-line.yaml::plan-rounds の `max_iterations: 20` と、workflows/line/works-factory-line.yaml::plan-out・workflows/line/works-factory-line.yaml::plan-review-run の `with:` の `round_limit: 20`（正本はメイングラフ。lib/boardview.py::_at_cap は入力の round_limit で converge.record_pass の at_cap を決め、数を持たない）
- plan.md P115: lib/planfile.py::next_round・lib/planfile.py::converge_record（mode replan を飛ばす）、lib/boardview.py::place（round 1 固定）
- plan.md P116: lib/planfile.py::converge_record（計画の側の組み直し）と plan-review/plan-converge.json（lib/boardview.py::_take が呼ぶ lib/converge.py::record_pass）。#75 の discoveries R10（converge の往復の本体の写し・約 120 行）
- plan.md P117: 無し。2 周目は新しい会話で、前の周の案と指摘をファイルで渡し、修正案の役は変えた項目だけを返す（lib/converge.py::splice が返さない項目に前の往復の行を機械が入れ、lib/converge.py::fixed_unchanged が fixed と答えて項目を変えていない答えを拒む。#571）。同じ周の中で受け付けに拒まれた後は、出し直しの役が同じ会話の続きで拒まれた項目だけを返し、受け付けが前の答えと合わせる（WF workflows/plan/works-factory-plan.yaml::plan-writer-fix・lib/planfile.py::merge_resubmit。plan-loop は `fresh_context: false`）
- plan.md P118: lib/planfile.py::write_brief（形 plan の材料に独立設計のセクションは元から無い。2 周目は会話が新しいので planmarks.HEAD を含む頭を貼り直す）
- plan.md P119: lib/runreport.py::_converge_lines（lib/gatemarks.py::converge_of。最後の承認ノードの ask_final.review_rows も同じ口）
- plan.md P120: lib/boardview.py::_pass_rejects（受け付けが往復を控えた後、converge.stash_rejects でその往復の計画の周の rejects-plan.json と事前審査の拒否の行を往復の行の rejects に残す。拒否の控えは周・挟んだ回ごと）（#120）
- plan.md P121: lib/boardview.py::take_review（accept.guard が例外を拒否にし、3 回で give_up → 出力ノードが pass: false・stalled: true と訳を questions に載せる）
- plan.md P122: 無し（共有ボードが無い。往復はメイングラフの loop_group）
- plan.md P123: lib/planmarks.py::handed・lib/planfile.py::open_round（ruling が空でなければ mode replan）、workflows/line/works-factory-line.yaml::replan（ruling: $fix.output.replan_items・conflicts: $fix.output.conflicts）
- plan.md P124: lib/planmarks.py::handed・lib/planfile.py::open_round（go: false・why）
- plan.md P125: lib/planfile.py::replan_section・lib/planfile.py::conflict_rows・lib/planfile.py::write_brief（形 replan）
- plan.md P126: lib/planfile.py::item_brief・lib/planfile.py::replan_section（承認済みの項目と判定から planbrief.render で plan/r<k>/item-brief-<no>.md を組み、「この項目の brief: <パス>」で名指す）（#120）
- plan.md P127: lib/planfile.py::_plan_errors・lib/planfile.py::take_replan
- plan.md P128: lib/planfile.py::exists_at・lib/planfile.py::take_replan
- plan.md P129: lib/planfile.py::take_replan、lib/replan.py::new_item
- plan.md P130: lib/planfile.py::take_replan（amended つき plan-fields.json と trace の `plan_amended`。lib/planfile.py::_save・lib/planmarks.py::AMEND_OP）・lib/planfile.py::revised_fields（受け付けで差し替える。採るかはメイングラフの承認ノード。届かなかった lib/planmarks.py の `amend` は #232 で消した）
- plan.md P131: lib/planfile.py::ripple_items（その周の案で作る）、WF workflows/plan/works-factory-plan.yaml::ripple-units（ripple-units は mode plan だけ）
- plan.md P132: lib/planfile.py::structure_dir（`structure_dir(… source=prev)`）・lib/planfile.py::open_round
- plan.md P133: lib/planfile.py::collect（その周の案で depth）、workflows/line/works-factory-line.yaml::refix-run（`depth: $replan.output.depth`）・workflows/line/works-factory-line.yaml::redepth（`replan_depth: $replan.output.depth`）
- plan.md P134: WF workflows/plan/scripts/plan_accept.py::main（rolekit.with_done）、lib/planfile.py::why_not_ready
- plan.md P135: lib/planfile.py::collect_reads（形 replan は reads-replan-<役>.json と reads-replan-block.json を周のフォルダに書く）（#120）
- plan.md P136: lib/boardview.py::open_pass（form replan）・lib/planmarks.py::handed（裁かれた項目）・lib/boardview.py::collect（`ok, stalled = not blocks, False`）
- plan.md P137: lib/boardview.py::_review_material・lib/boardview.py::replan_items・lib/boardview.py::_replan_section
- plan.md P138: lib/boardview.py::_shown_plan（形 replan の材料の「修正役の案」に裁かれた項目だけを貼る。`_faces_of` は元 replan._review_of と同じなので変えない）（#120）
- plan.md P139: lib/boardview.py::open_pass（conflicts=…）。メイングラフの workflows/line/works-factory-line.yaml::replan-review の with: に conflicts: $fix.output.conflicts
- plan.md P140: lib/boardview.py::_take（converge.split・tree_split・planblk.design_gaps(items=ruled)）
- plan.md P141: lib/boardview.py::replan_asks、workflows/line/scripts/ask_replan.py::ask（メイングラフでもう一度 contract_diff・widened を当てる）
- plan.md P142: lib/planfile.py::note_gave_up・lib/boardview.py::collect（出力のポインタの隣の replan-gave-up.json に項目ごとの {item, why, ruling}。訳は planblk.PLAN_GAVE_UP_WHY・REVIEW_GAVE_UP_WHY）・lib/runreport.py::replan_gave_up（前の失敗の行）（#120）
- plan.md P143: workflows/line/works-factory-line.yaml::gate-replan・workflows/line/works-factory-line.yaml::answer-replan（gate_answer.answer）
- plan.md P144: workflows/line/scripts/replan_answer.py::fix_answers（頭の 2 つ）と workflows/line/scripts/replan_answer.py::fix_notes（FACES_HEAD のセクション。lib/replan.py::fix_notes）→ refix-run の answers・notes
- plan.md P145: lib/replan.py::WIDEN_OP・lib/replan.py::WIDEN_LINE・lib/replan.py::WIDEN_PARTS・lib/replan.py::widen_text（ask-replan が引く）→ collect → report の入力 widened → lib/runreport.py::_line_lines
- plan.md P146: lib/replan.py::amend_lines（人が承認した・聞かずに通した（手段の欄だけ）・WIDEN_LINE・直さずに諦めた: 訳・未完了）→ 報告（lib/runreport.py::_amend_lines）と最後の承認ノード（ask_final の amend）
- plan.md P147: lib/outcome.py::CLOSE_WHY・lib/outcome.py::PENDING_WHY・lib/outcome.py::waiting_conflicts・lib/outcome.py::asked_conflicts（報告の組み立てで締めた形に読む）、lib/runreport.py::_asked_rows
- plan.md P148: 共有ボードが無いので形が変わった。1 回目と 2 回目の修正をメイングラフが束ねる（workflows/line/scripts/fixed.py::fixed、workflows/line/works-factory-line.yaml::fixed）
- plan.md P149: workflows/line/works-factory-line.yaml::refix-run（only_items: $fix.output.replan_items）・workflows/line/works-factory-line.yaml::fixed
- plan.md P150: workflows/plan-review/works-factory-plan-review.yaml::review・lib/boardview.py::collect
- plan.md P151: workflows/plan-review/works-factory-plan-review.yaml の inputs（ノードの外の宣言で id が無い）・workflows/plan-review/scripts/pass_open.py::opened
- plan.md P152: lib/boardview.py::open_pass（conflicts・gate_answers を受ける口）・メイングラフの workflows/line/works-factory-line.yaml::replan-review の with: の conflicts・gate_answers（plan-review-run は修正前の承認ノードより前なので渡さない）
- plan.md P153: workflows/plan-review/works-factory-plan-review.yaml 全部のノード・workflows/plan-review/scripts/*.py の頭
- plan.md P154: workflows/plan-review/scripts/result.py::main・lib/boardview.py::collect
- plan.md P155: workflows/plan-review/scripts/pass_open.py::main
- plan.md P156: workflows/plan-review/works-factory-plan-review.yaml::r2-design-loop・workflows/plan-review/works-factory-plan-review.yaml::review-loop・workflows/plan-review/works-factory-plan-review.yaml::review・workflows/plan-review/works-factory-plan-review.yaml::plan-review-fix
- plan.md P157: workflows/plan-review/commands/*.md・workflows/plan-review/works-factory-plan-review.yaml
- plan.md P158: workflows/plan-review/fixtures/
- plan.md P159: lib/boardview.py::r2_due・workflows/plan-review/works-factory-plan-review.yaml::r2-design-loop `when: "$open.output.r2_go == true"`
- plan.md P160: lib/boardview.py::purpose_unusable・lib/design.py::UNUSABLE
- plan.md P161: judge が判定の隣に purpose-review.json を置き（lib/judge_accept.py::verdict）、plan-review の lib/boardview.py::_purpose_review が名で開く（名は lib/purpose.py::PURPOSE_REVIEW_FILE の 1 か所）
- plan.md P162: workflows/plan-review/works-factory-plan-review.yaml::r2-design（systemPrompt。Archon の packages/providers/src/claude/provider.ts がノードの systemPrompt で既定の system prompt を置き換える）
- plan.md P163: lib/boardview.py::r2_prompt・workflows/plan-review/scripts/r2_prep.py
- plan.md P164: lib/boardview.py::r2_prompt（purpose.json の purpose_text だけを読む）
- plan.md P165: lib/design.py::premises・lib/boardview.py::DESIGN_PREMISE_REREAD・lib/boardview.py::r2_prompt
- plan.md P166: lib/boardview.py::NOT_GIVEN_START・lib/boardview.py::DEFAULTS_HEAD・lib/boardview.py::DEFAULT_START・lib/boardview.py::DEFAULT_ANSWERS・lib/boardview.py::REQUEST_UNREAD・lib/boardview.py::_request・lib/boardview.py::_defaults_line
- plan.md P167: lib/boardview.py::r2_prompt（policy.section）
- plan.md P168: lib/planfile.py::moved・lib/boardview.py::check_design
- plan.md P169: 型は workflows/plan-review/works-factory-plan-review.yaml::r2-design の `output_format`（型の正本。Claude Code がノードの中で照らして出し直させる）。lib/boardview.py::check_design は JSON として読む（rolekit.parse_reply）だけで型を照らし直さない（受け付けの `accept.type_errors` は #232 で消した）。workflows/plan-review/scripts/pass_open.py::node_schema が控える型は、design.json の読み直し（lib/design.py::read_design）と下請けの答えのファイルの faces・shrink の照らしが使う
- plan.md P170: lib/design.py::anchor_misses・lib/boardview.py::PREMISE_MISS・lib/boardview.py::check_design
- plan.md P171: lib/boardview.py::r2_prompt・lib/boardview.py::counted・lib/boardview.py::collect（design の控えが無ければ pass-<k>/design.json に missing）
- plan.md P172: lib/design.py::claims_unpassed・lib/design.py::claims_given・lib/boardview.py::check_design
- plan.md P173: workflows/plan-review/commands/r2-design.md（台帳 tests/workflows/test_plan_review.py::COPIED）・lib/boardview.py::r2_prompt の DRIFT_LINE・STALE_LINE（#120）
- plan.md P174: lib/planblk.py::design_only
- plan.md P175: lib/planblk.py::design_section・lib/boardview.py::_review_material
- plan.md P176: lib/planblk.py::DESIGN_ASK
- plan.md P177: lib/design.py::quote_gaps・lib/planblk.py::design_gaps
- plan.md P178: lib/design.py::_map_gaps
- plan.md P179: lib/design.py::quote_gaps
- plan.md P180: lib/boardview.py::collect（trace に design.HANDED_OP・MISSING_OP）（#120）
- plan.md P181: lib/planblk.py::HEAD・lib/planblk.py::head・lib/boardview.py::_review_material
- plan.md P182: lib/boardview.py::UNITS_LINE・lib/boardview.py::_review_material、lib/planfile.py::repo_line（リポジトリ・読む版・BASE・観点の正本の行）
- plan.md P183: lib/boardview.py::named
- plan.md P184: lib/planmarks.py::review_section・lib/planblk.py::design_section
- plan.md P185: lib/planmarks.py::review_section・lib/planblk.py::design_section（worldmark.challenges を渡す）
- plan.md P186: lib/planblk.py::design_section・workflows/plan-review/scripts/review_prep.py
- plan.md P187: lib/boardview.py::review_material（pass-<k>/prep-error.txt）・lib/boardview.py::collect（review.json が無い時にその訳）（#120）
- plan.md P188: lib/boardview.py::open_pass・lib/planblk.py::head
- plan.md P189: lib/planblk.py::lib_section・lib/boardview.py::_review_material
- plan.md P190: lib/boardview.py::_review_material
- plan.md P191: lib/policy.py::section・lib/policy.py::_capped・lib/boardview.py::review_body・lib/boardview.py::_review_material
- plan.md P192: lib/boardview.py::_review_material（policy_copy）・lib/boardview.py::r2_prompt（POLICY_FILE の copy）（部分 A で閉じた）
- plan.md P193: lib/boardview.py::_review_material
- plan.md P194: workflows/plan-review/commands/plan-review.md
- plan.md P195: lib/boardview.py::review_body・lib/planblk.py::_review_rules
- plan.md P196: workflows/plan-review/works-factory-plan-review.yaml::plan-review・lib/boardview.py::HUMAN_FACE_KINDS
- plan.md P197: lib/planblk.py::READONLY_MOVED・lib/planfile.py::moved・lib/boardview.py::_take・pass-<k>/tree.json
- plan.md P198: lib/boardview.py::_take
- plan.md P199: lib/planblk.py::RECOMMEND_REJECT・lib/boardview.py::_take
- plan.md P200: lib/boardview.py::plan_review_output・lib/boardview.py::_keys_once・lib/boardview.py::blank
- plan.md P201: lib/boardview.py::take_review・lib/boardview.py::GIVEN_UP_FACES・lib/boardview.py::collect
- plan.md P202: lib/planblk.py::TREE_AUTO_MIN・lib/boardview.py::tree_word・lib/boardview.py::_tree_on・workflows/line/scripts/start.py::words（features の語の照らし）
- plan.md P203: lib/planblk.py::tree_part・lib/planblk.py::SUBAGENT_TYPE・lib/planblk.py::AGG_ASK
- plan.md P204: lib/planblk.py::brief_head
- plan.md P205: lib/planblk.py::tree_merge・lib/boardview.py::_take
- plan.md P206: lib/planblk.py::check_item・lib/planblk.py::item_answer_gaps・lib/planblk.py::_errors_part
- plan.md P207: lib/planblk.py
- plan.md P208: lib/planblk.py::_diff_part・lib/planblk.py::_carried_part・lib/planblk.py::carried_hits
- plan.md P258: lib/planblk.py::_diff_part・lib/planblk.py::_changed_chars、lib/planmarks.py::joined（lib/boardview.py::open_pass が往復の控えの行に同じ番号の works の欄を重ね、allowed_paths などの変化も比べと差分に出す）
- plan.md P209: lib/planblk.py::precedent_checks・lib/planblk.py::precedent_plan・lib/planblk.py::_precedent_part・lib/planblk.py::_precedent_gaps・lib/planblk.py::save_precedents
- plan.md P210: lib/planblk.py::_surplus・lib/planblk.py::SURPLUS_OP
- plan.md P211: lib/reads.py::collect・lib/boardview.py::collect_reads・workflows/plan-review/scripts/review_reads.py（ノード review-reads）・bin/_lib/record-read.py・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- plan.md P212: lib/boardview.py::collect_reads（trace の planblk.AGENT_OP）・bin/_lib/record-read.py（Agent の行）・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- plan.md P213: lib/reads.py::web_fetches・lib/reads.py::web_searches・bin/_lib/record-read.py（WebFetch・WebSearch の行）・bin/_lib/toolset.py（隔離した設定にフックを置く）（#120）
- plan.md P214: lib/policy.py::locate・lib/policy.py::snapshot・lib/policy.py::freeze・lib/boardview.py::_frozen_policy
- plan.md P215: lib/boardview.py::policy_change・lib/boardview.py::change_row・lib/boardview.py::collect
- plan.md P216: workflows/line/scripts/start.py::start（record.policy = policy.freeze）→ lib/boardview.py::_frozen_policy（始めの記録の版をそのまま置く）（部分 A で閉じた）
- plan.md P217: lib/holeties.py（使い手は lib/refix.py・lib/fixboard.py）
- plan.md P218: lib/gatemarks.py::MARK_SCHEMA（役の型に足す口 `with_marks` は #232 で消し、欄はノードの output_format が持つ）・workflows/plan-review/works-factory-plan-review.yaml::plan-review（faces の行）・workflows/plan/works-factory-plan.yaml（narrows の行）
- plan.md P219: lib/gatemarks.py::HEAD
- plan.md P220: lib/gatemarks.py::split・lib/gatemarks.py::save・lib/boardview.py::open_pass（修正案の側）・lib/boardview.py::_take（事前審査の側）
- plan.md P221: lib/gatemarks.py::recommend_gaps・lib/boardview.py::_take（RECOMMEND_REJECT）
- plan.md P222: lib/gatemarks.py::_gate_rows・lib/boardview.py::HUMAN_FACE_KINDS
- plan.md P223: lib/gatemarks.py::plan_gate_items・lib/gatemarks.py::_record・lib/boardview.py::collect（PASSES_FILE）・lib/runreport.py::_gate_passes（隣の gate-passes.json を読む）
- plan.md P224: lib/gatemarks.py::FENCES・lib/gatemarks.py::decided
- plan.md P225: lib/gatemarks.py::plan_gate_items
- plan.md P226: lib/gatemarks.py::_world・lib/gatemarks.py::_no_narrow・lib/gatemarks.py::_item
- plan.md P227: lib/gatemarks.py::_push・lib/gatemarks.py::push_of
- plan.md P228: lib/gatemarks.py::_cite_check・lib/gatemarks.py::axes・lib/gatemarks.py::axis_reasons
- plan.md P229: lib/gatemarks.py::axes・lib/gatemarks.py::axis_reasons・lib/boardview.py::_copy_world（world が null なら控えを消して今どおりの軸に戻す）
- plan.md P230: lib/gatemarks.py::axes・lib/gatemarks.py::_answered_rows・lib/gatemarks.py::axis_reasons・lib/boardview.py::_copy_structure
- plan.md P231: lib/gatemarks.py::axes・lib/gatemarks.py::axis_reasons
- plan.md P232: lib/gate_axes.py::gather・lib/boardview.py::collect
- plan.md P233: lib/gatemarks.py::world_items・lib/gatemarks.py::plan_gate_items
- plan.md P234: lib/gatemarks.py::design_items
- plan.md P235: lib/gatemarks.py::asks・lib/gatemarks.py::ask_text・lib/gatemarks.py::ASKING
- plan.md P236: lib/gatemarks.py::plan_gate_items・lib/boardview.py::open_pass（始めの記録を置き場に写すので無人の印が届く）
- plan.md P237: lib/gatemarks.py::hold_keys・lib/gatemarks.py::_hold_scan・lib/gatemarks.py::answered
- plan.md P238: lib/gatemarks.py::unread_hold_lines。報告は lib/runreport.py::ledger_state の unread_holds → lib/runreport.py::_decisions、最後の承認ノードは workflows/line/scripts/ask_final.py::ledger_rows
- plan.md P239: lib/gatemarks.py::returned・lib/gatemarks.py::returned_lines・lib/gatemarks.py::unreturned_lines（字のまま）・lib/fixboard.py::write_notes（修正の側が約束の行を書く）
- plan.md P240: lib/gatemarks.py::withheld_by・lib/gatemarks.py::withheld・lib/gatemarks.py::held_lines
- plan.md P241: lib/gatemarks.py::duty・lib/gatemarks.py::ledger・lib/gatemarks.py::gate_items（fix は lib/fixboard.py::gate_view・lib/fixboard.py::gate_asks・lib/fixboard.py::group_owed が置き場の answers.json の asked で人が見た行を引く）。メイングラフは answer-before-fix の答えに $ask-before-fix.output.asked を付ける
- plan.md P242: lib/gatemarks.py::request_answer・lib/gatemarks.py::answer_binds・lib/gatemarks.py::unmatched_answer_lines・lib/boardview.py::open_pass（始めの記録の写しから読む）・lib/runreport.py::ledger_state（報告の側の写し）
- plan.md P243: lib/gatemarks.py::material_answer・lib/gatemarks.py::measured_materials・lib/gatemarks.py::origin（値で受ける式）。報告は lib/runreport.py::ledger_state が gatemarks の見え方で引く
- plan.md P244: lib/boardview.py::take_gate_answers・lib/boardview.py::_note_asked・workflows/plan-review/scripts/pass_open.py（入力 gate_answers）。メイングラフの workflows/line/works-factory-line.yaml::replan-review の with: に gate_answers: $answer-before-fix.output.answer
- plan.md P245: lib/boardview.py::_note_asked・lib/boardview.py::collect（gatemarks.PLAN_GATE_FILE）
- plan.md P246: lib/boardview.py::policy_change・lib/boardview.py::change_row・lib/boardview.py::collect（collect が行を足す）・lib/boardview.py::take_gate_answers（固め直し）
- plan.md P247: lib/gatemarks.py::design_item・lib/gatemarks.py::_design_only_answered・lib/boardview.py::open_pass（始めの記録の写し）
- plan.md P248: lib/gatemarks.py::design_item・lib/boardview.py::collect（stalled）
- plan.md P249: workflows/line/scripts/ask_before_fix.py::ask: 軸の行は事前審査の項目が無い時だけ足し、設計だけの行・止まりの行は事前審査の 1 行のまま
- plan.md P250: plan-review の出力 questions の行 {kind, text}（lib/boardview.py::collect・lib/gatemarks.py::question_row）。メイングラフの workflows/line/scripts/ask_before_fix.py::ask が種類で承認ノードの文の冒頭・ASK_GATE_HEAD・無人の run の振る舞いを決める
- plan.md P251: lib/gatemarks.py::gate_text・workflows/line/scripts/ask_before_fix.py::gate_text（メイングラフの持ち物）
- plan.md P252: lib/boardview.py::collect・workflows/plan-review/scripts/result.py
- plan.md P253: workflows/line/works-factory-line.yaml::plan-review-run（plan-review は plan の ready でだけ走る）・workflows/line/scripts/ask_before_fix.py::ask（plan の ready が偽なら承認ノードを開かない）・workflows/line/scripts/plan_out.py::round_owes_nothing → workflows/line/works-factory-line.yaml::design-only → workflows/line/scripts/fixed.py::no_fix → test-gate-final・eyes
- plan.md P254: lib/eyeverdict.py::r4_gate_items・lib/eyeverdict.py::_human_passed（eyes の持ち物。plan-review の questions とメイングラフの answer-before-fix の答えを読む）
- plan.md P255: 報告は lib/runreport.py::ledger_state・lib/runreport.py::_gate_passes。最後の承認ノードは workflows/line/scripts/ask_final.py::review_rows（gate-passes.json）・workflows/line/scripts/ask_final.py::ledger_rows・workflows/line/scripts/ask_final.py::question_lines
- plan.md P256: lib/runreport.py::answer_drafts（報告の持ち物。plan-review の questions と隣の p2.fix_plan.json を読む）
- plan.md P257: lib/boardview.py::collect・lib/boardview.py::GIVEN_UP_FACES
- tail.md T1: lib/declared_checks.py::checks_reply・lib/declared_checks.py::run_ci
- tail.md T2: lib/declared_checks.py::_with_test_cmd・lib/declared_checks.py::_planned_run
- tail.md T3: lib/declared_checks.py::_same_step・lib/declared_checks.py::suites_line
- tail.md T4: lib/declared_checks.py::_engine_log・lib/declared_checks.py::tree_runner
- tail.md T5: lib/declared_checks.py::_planned_run・lib/declared_checks.py::local_checks_material
- tail.md T6: lib/declared_checks.py::_planned_run・workflows/test-gate/works-factory-test-gate.yaml::ci-loop（ci-loop の when）
- tail.md T7: lib/declared_checks.py::checks_plan・lib/declared_checks.py::checks_reply
- tail.md T8: lib/declared_checks.py::run_ci・lib/declared_checks.py::_planned_run・lib/declared_checks.py::_declaration_moved（走らせた後の宣言の sha を照らし、違えば計画から 1 度だけやり直す。ログは logs/…/replan。#122）
- tail.md T9: lib/declared_checks.py::run_ci（material_problems を engine の素材にも当てる）・lib/declared_checks.py::_fall_back（engine が走らせた test_cmd の段の結果から素材を組む。落とした訳 fell_back は workflows/test-gate/scripts/result.py::evidence が証拠の文にも出す）・lib/declared_checks.py::_cant_status（#122）
- tail.md T10: lib/checkscope.py::read_scope
- tail.md T11: lib/checkscope.py::read_scope・lib/declared_checks.py::_planned_run・workflows/test-gate/scripts/run.py::main
- tail.md T12: lib/declared_checks.py::run_ci・workflows/test-gate/scripts/run.py::main
- tail.md T13: lib/checkscope.py::skipped_steps・lib/declared_checks.py::_planned_run
- tail.md T14: lib/checkscope.py::skipped_steps・workflows/test-gate/scripts/run.py::changed
- tail.md T15: workflows/test-gate/scripts/run.py::changed（境の boundary.RUNTIME_COPY_PREFIX の除き）・lib/accept.py::touched_files
- tail.md T16: workflows/test-gate/scripts/run.py::request_wheres（判定から入る run の base で始めの記録の依頼の where）・workflows/test-gate/scripts/run.py::changed・lib/checkscope.py::request_files（元 `_pr_files` の式。#122）
- tail.md T17: lib/declared_checks.py::_skipped_note・lib/checkscope.py::scope_word・lib/checkscope.py::skipped_text
- tail.md T18: lib/declared_checks.py::suites_line・workflows/test-gate/works-factory-test-gate.yaml::run・workflows/test-gate/scripts/result.py::gate_fields（サブグラフの出力 result の欄 suites_line。evidence.md の「走らせ方」の行も同じ値）
- tail.md T19: lib/declared_checks.py::_planned_run（_with_test_cmd に外した後の段を渡すので、_same_step は外した段と比べない）
- tail.md T20: lib/declared_checks.py::local_checks_material・lib/declared_checks.py::_with_test_cmd・lib/tree_run.py::command_argv
- tail.md T21: lib/declared_checks.py::_cmd_material・lib/tree_run.py::prove_launchable
- tail.md T22: lib/tree_run.py::launch_kind
- tail.md T23: lib/declared_checks.py::_cmd_material・lib/declared_checks.py::local_checks_material
- tail.md T24: lib/declared_checks.py::tree_runner・lib/tree_run.py::outside_env
- tail.md T25: workflows/test-gate/scripts/run.py::main・lib/tree_run.py::run
- tail.md T26: lib/declared_checks.py::_suite_kind・lib/declared_checks.py::suites_line（起こせない段の名指し。届かなかった `env_only_red` は #232 で消した）・lib/green_cert.py::classify
- tail.md T27: lib/declared_checks.py::_junit_unran・lib/declared_checks.py::checks_reply
- tail.md T28: lib/declared_checks.py::checks_reply
- tail.md T29: lib/declared_checks.py::_junit_reports・lib/declared_checks.py::_planned_run（走らせる前に無かった報告を消す）
- tail.md T30: lib/declared_checks.py::suites_line・workflows/test-gate/scripts/result.py::certified
- tail.md T31: lib/declared_checks.py::checks_reply（clean の checked）
- tail.md T32: workflows/test-gate/scripts/result.py::certified・lib/baseline_red.py::write_baseline・lib/baseline_red.py::read_baseline
- tail.md T33: workflows/test-gate/scripts/run.py::main・workflows/test-gate/scripts/result.py::suite_exit
- tail.md T34: lib/declared_checks.py::baseline_line・workflows/test-gate/scripts/result.py::certified
- tail.md T35: 最後の承認ノードは workflows/line/scripts/ask_final.py::final_tests・workflows/line/scripts/ask_final.py::tests_lines（test-gate-final の出力の欄 by・suites_line・baseline_line を with: で受け、lib/declared_checks.py::gate_values で字にする）。報告は lib/runreport.py::_evidence_lines（受け皿 test-gate-base-out・test-gate-final-out の欄。緑の認証のセクション）。報告の側は人が決めることのセクションにも（lib/runreport.py::_tests_head_lines。部分 C）
- tail.md T36: lib/green_cert.py::classify
- tail.md T37: lib/green_cert.py::classify
- tail.md T38: lib/green_cert.py::HEAD_LIMIT・lib/green_cert.py::_keys
- tail.md T39: lib/green_cert.py::fingerprint・lib/green_cert.py::certify
- tail.md T40: lib/green_cert.py::SELF_REPORTED・lib/green_cert.py::certify・workflows/test-gate/scripts/result.py::certified・workflows/test-gate/commands/ci.md（「自己申告として人に諮られる」の行）
- tail.md T41: workflows/line/scripts/ask_final.py::tests_lines（証拠の走らせ方が role_needed なら、engine が走らせていないこと・宣言 .review-checks.json に書く次の手・確かめて続けるか止めるか）。報告の側は lib/runreport.py::_tests_head_lines（字は lib/declared_checks.py::SELF_REPORTED_NOTE を最後の承認ノードと共に読む。部分 C）
- tail.md T42: lib/green_cert.py::certify
- tail.md T43: workflows/test-gate/scripts/result.py::failed・workflows/test-gate/scripts/result.py::main
- tail.md T44: workflows/test-gate/scripts/result.py::certified
- tail.md T45: workflows/test-gate/scripts/result.py::certified（素材が無い時 rolekit.given_up_reason の最後の拒否の文を証拠の evidence.md に出す）
- tail.md T46: workflows/test-gate/scripts/run.py::fresh_gate
- tail.md T47: workflows/test-gate/scripts/run.py::fresh_gate（logs/ のほかを消し、今回のログは空いた番号の logs/a<k>/。#122）
- tail.md T48: workflows/test-gate/works-factory-test-gate.yaml::ci-loop・workflows/test-gate/works-factory-test-gate.yaml::ci-prep・workflows/test-gate/works-factory-test-gate.yaml::ci・workflows/test-gate/works-factory-test-gate.yaml::ci-fix
- tail.md T49: workflows/test-gate/works-factory-test-gate.yaml::ci の sandbox.filesystem `{allowWrite: ['/'], denyWrite: ['~/../archon-home']}`（起動が隔離した HOME の隣の Archon の家 archon-home の下＝既定の置き場の run の作業ツリーと隣の worktree・artifacts を塞ぐ。`'.'` は cwd でなく設定の一時ファイルのフォルダに解かれ作業ツリーを塞がない——実測 2026-10-13・#293。止めた Archon はノードの sandbox をそのまま SDK に渡す: dag-executor.ts:1847・providers/src/claude/provider.ts:801-803。実測は #217（段 1a・#154）。#122）と、包み workflows/.shared/fence.py::protected_paths（埋め P5。殻 bin/_lib/launcher.py::write_fence が CLAUDE_BIN_PATH に置く。固定の値を印に読み、起こす直前に cwd・共通の .git・git worktree list の全部の根・Archon の家・Claude の設定・殻の口・包みを起こす Python・本物の claude・取り置いた Archon の源・工場の checkout の根の全体を denyWrite に足す。#309・#348）と、mutates_checkout: false・受け付けの作業ツリーの比べ（T51）。包みは印の在る起動を記録に書き（workflows/.shared/fence.py::record）、殻が子の env WORKS_FACTORY_FENCE_RECORDS で包みを宣言する。宣言した run は受け付け workflows/test-gate/scripts/ci_accept.py::judge が workflows/.shared/fence.py::fenced_since で ci-prep の後にこの作業ツリーで柵の掛かった起動を探し、無ければ返答を受けず諦める。宣言が読めない（絶対パスでない）run は workflows/test-gate/scripts/ci_prep.py が workflows/.shared/fence.py::bad_declaration で見て、役を起こさずに落ちる。宣言の無い run は workflows/test-gate/scripts/result.py::evidence が lib/declared_checks.py::NO_ADAPTER_NOTE を出す
- tail.md T50: workflows/test-gate/scripts/ci_prep.py::main
- tail.md T51: workflows/test-gate/scripts/ci_accept.py::judge・lib/accept.py::TREE_KEYS
- tail.md T52: workflows/test-gate/scripts/ci_prep.py::main
- tail.md T53: workflows/test-gate/scripts/ci_prep.py::main（前の回までの拒否の全部を rolekit.rejected の控えから読み、rolekit.rejects_text で古い順に 1 つの文にする。#345。with: の $LOOP_PREV は外した: Archon は with: に $LOOP_PREV を生のまま貼った後にノードの出力の参照をもう 1 度置き換える。dag-executor.ts:5279-5306・:464-493。#122）・workflows/test-gate/commands/ci.md
- tail.md T54: workflows/test-gate/scripts/ci_accept.py::main・lib/rolekit.py::GIVE_UP_AFTER・lib/rolekit.py::with_done
- tail.md T55: workflows/test-gate/scripts/ci_accept.py::judge・lib/rolekit.py::parse_reply
- tail.md T56: lib/declared_checks.py::material_problems・workflows/test-gate/scripts/ci_accept.py::judge
- tail.md T57: lib/declared_checks.py::MATERIAL_SCHEMA・workflows/test-gate/works-factory-test-gate.yaml::run・workflows/test-gate/works-factory-test-gate.yaml::ci
- tail.md T58: lib/declared_checks.py::drop_copy・workflows/test-gate/scripts/ci_accept.py::main・workflows/test-gate/scripts/result.py::certified
- tail.md T59: workflows/test-gate/scripts/ci_accept.py::main
- tail.md T60: workflows/test-gate/commands/ci.md（役の決まりの段落）
- tail.md T61: 無し（共有ボードの台帳を持ち込まない。docs/plans/2026-10-12-blocks/test-gate.md:51）
- tail.md T62: lib/tree_run.py::replay_group・lib/tree_run.py::keep_group・lib/tree_run.py::reuse_run（元 slotted_run から枠を外した物）・lib/tree_run.py::reuse_place・lib/declared_checks.py::tree_runner・lib/tddloop.py::_test_cmd_gate・lib/tddloop.py::start（元の結末の一式）・lib/baseline_red.py::run_suite。控えはメイングラフの run の置き場の直下 test-reuse/（run の名は始めの記録の run_id）。test-gate の base（workflows/test-gate/scripts/run.py）が引いて置き、fix の組の子の run の TDD のループの頭（workflows/fix/scripts/group_start.py。置き場は workflows/.shared/boundary.py::line_place）が test_cmd と元の結末の一式を引いて置く。final は引かない（#122）
- tail.md T63: lib/tree_run.py::note_fields・lib/tree_run.py::reused_text・lib/tree_run.py::RERUN_ENV・lib/declared_checks.py::_reused_note・lib/declared_checks.py::_reused_material・lib/declared_checks.py::_row（段の行の reused・reuse_off。trace の代わりに test-gate/<mode>/run.json の runs）。旗は script が読む（#122）
- tail.md T64: 無し（lib/declared_checks.py::tree_runner は tree_run.run を直に呼ぶ）
- tail.md T65: lib/declared_checks.py::tree_runner（使い回しの口が無い）
- tail.md T66: workflows/test-gate/scripts/result.py::main・メイングラフ workflows/line/works-factory-line.yaml::eyes（eyes は test-gate-final の後にいつも走る）・workflows/line/works-factory-line.yaml::ask-final（ask-final が tests_ok・green・red_cause を読む）
- tail.md T67: workflows/line/scripts/ask_final.py::tests_word
- tail.md T68: lib/runreport.py::_base_word（lib/runreport.py::_entry_lines の「直す前のテスト:」の行。red_cause incomplete は「走らせられなかった」）
- tail.md T69: lib/green_cert.py::certify（base の素材が awaiting_human なら直す前の結末を控えて ok を真にし、メイングラフの judge へ進む。走らせられなかった系統は素材の reason が名指し、判定の台帳の awaiting の問い〔lib/judge_accept.py::baseline_local_checks〕と、報告の人が確かめる物〔lib/outcome.py::residue〕と直す前のテストの行〔lib/runreport.py::_base_word〕に載る。人が確かめて続ける道は結末 fixed_needs_check と次の依頼の answers。今の works と同じく、一部でも全部でも止めない）
- tail.md T70: bin/_lib/launcher.py::check_test_cmd（殻が新しい run の --input test_cmd= を Archon を起こす前に照らす）・bin/_lib/testcmd_check.py::main（元の決まりのまま。#495）
- tail.md T71: lib/carry.py::carry_ci
- tail.md E1: workflows/eyes/works-factory-eyes.yaml::r1-comments ほかAI ノード 7 つ（`mutates_checkout: false`。r4-scope と r4-scope-fix 以外は `context: fresh`。r4-scope は r4-loop の 1 周目で新しい会話、workflows/eyes/works-factory-eyes.yaml::r4-scope-fix は拒まれた後にその会話の続き）
- tail.md E2: workflows/eyes/works-factory-eyes.yaml::r1-comments・workflows/eyes/works-factory-eyes.yaml::r1-minimality・workflows/eyes/works-factory-eyes.yaml::r2-compare・workflows/eyes/works-factory-eyes.yaml::premise-check・workflows/eyes/works-factory-eyes.yaml::r3-coherence・workflows/eyes/works-factory-eyes.yaml::r4-scope
- tail.md E3: workflows/eyes/works-factory-eyes.yaml::r1-comments・workflows/eyes/works-factory-eyes.yaml::r1-minimality・workflows/eyes/works-factory-eyes.yaml::r2-compare・workflows/eyes/works-factory-eyes.yaml::premise-check・workflows/eyes/works-factory-eyes.yaml::r3-coherence・workflows/eyes/works-factory-eyes.yaml::r4-scope
- tail.md E4: workflows/eyes/works-factory-eyes.yaml::r1-comments ほか
- tail.md E5: workflows/eyes/works-factory-eyes.yaml::r2-compare（`systemPrompt`）
- tail.md E6: workflows/eyes/commands/r2-compare.md
- tail.md E7: workflows/eyes/commands/r2-compare.md、workflows/eyes/scripts/prep.py::out
- tail.md E8: workflows/eyes/works-factory-eyes.yaml::r4-loop
- tail.md E9: workflows/eyes/works-factory-eyes.yaml::r1-comments・workflows/eyes/works-factory-eyes.yaml::r2-compare・workflows/eyes/works-factory-eyes.yaml::premise-check・workflows/eyes/works-factory-eyes.yaml::r3-coherence（depends_on は prep だけ）
- tail.md E10: workflows/eyes/works-factory-eyes.yaml::r1-comments-save・workflows/eyes/works-factory-eyes.yaml::r1-minimality（r1-comments-save と r1-minimality の all_done）、workflows/eyes/commands/r1-minimality.md
- tail.md E11: workflows/eyes/commands/r1-comments.md
- tail.md E12: workflows/eyes/commands/r1-comments.md
- tail.md E13: workflows/eyes/commands/r1-minimality.md
- tail.md E14: workflows/eyes/commands/r1-minimality.md、workflows/eyes/scripts/prep.py::out
- tail.md E15: lib/eyeverdict.py::scalars・lib/eyeverdict.py::scalars_text、workflows/eyes/scripts/prep.py::out
- tail.md E17: lib/eyeverdict.py::scalars、workflows/eyes/works-factory-eyes.yaml::prep（サブグラフの入力 x_scalars を読む。入力の既定は null）
- tail.md E18: lib/eyeverdict.py::scalars・lib/eyeverdict.py::scalars_text
- tail.md E19: workflows/eyes/commands/r1-minimality.md（「前の周は無い（1 run 1 周）」の固定の文）
- tail.md E20: workflows/eyes/scripts/prep.py::after・workflows/eyes/scripts/prep.py::out、lib/eyeverdict.py::NO_AFTER
- tail.md E21: workflows/eyes/commands/r1-minimality.md、workflows/eyes/commands/r3-coherence.md、workflows/eyes/scripts/prep.py::out
- tail.md E22: workflows/eyes/commands/r1-comments.md ほか 4 本
- tail.md E23: workflows/eyes/scripts/prep.py::out（lib/REVIEW.md）
- tail.md E24: workflows/eyes/scripts/prep.py::repo_review・workflows/eyes/scripts/prep.py::out、workflows/eyes/commands/r3-coherence.md
- tail.md E25: workflows/eyes/commands/r1-minimality.md、workflows/eyes/commands/r3-coherence.md、workflows/eyes/commands/r4-scope.md、workflows/eyes/scripts/prep.py::out
- tail.md E26: lib/rolekit.py::LANG_RULE・lib/rolekit.py::lang_line、workflows/eyes/scripts/prep.py::out
- tail.md E27: workflows/eyes/works-factory-eyes.yaml::r1-comments・workflows/eyes/works-factory-eyes.yaml::r1-minimality・workflows/eyes/works-factory-eyes.yaml::r2-compare・workflows/eyes/works-factory-eyes.yaml::premise-check・workflows/eyes/works-factory-eyes.yaml::r3-coherence・workflows/eyes/works-factory-eyes.yaml::r4-scope
- tail.md E28: workflows/eyes/works-factory-eyes.yaml::r4-scope（if/then）
- tail.md E29: workflows/eyes/works-factory-eyes.yaml::r1-comments・workflows/eyes/works-factory-eyes.yaml::r1-minimality・workflows/eyes/works-factory-eyes.yaml::r2-compare・workflows/eyes/works-factory-eyes.yaml::premise-check・workflows/eyes/works-factory-eyes.yaml::r3-coherence・workflows/eyes/works-factory-eyes.yaml::r4-scope（`retry: {max_attempts: 2, on_error: all}`。新しい試みで、理由は渡らない）
- tail.md E30: AI ノードの `mutates_checkout: false` で Archon がノードを落とし、出力ノードがその目を unverifiable にする
- tail.md E31: lib/eyeverdict.py::r2_compare_due、workflows/eyes/scripts/prep.py::out、workflows/eyes/works-factory-eyes.yaml::r2-compare
- tail.md E32: lib/eyeverdict.py::r2_premise_invalid、workflows/eyes/works-factory-eyes.yaml::premise-check
- tail.md E33: workflows/eyes/commands/premise-check.md、workflows/eyes/scripts/prep.py::out
- tail.md E34: lib/eyeverdict.py::premise_reason・lib/eyeverdict.py::collect
- tail.md E35: lib/eyeverdict.py::collect
- tail.md E36: workflows/line/scripts/ask_final.py::needs・workflows/line/scripts/ask_final.py::final_needs（「前提の検算が人に上げた」を承認ノードを開ける理由に足す）
- tail.md E37: eyes の出力 notes の隣の premise-check.json（lib/eyeverdict.py::premise_facts・lib/eyeverdict.py::premise_fact_lines）→ 最後の承認ノードと報告。報告が次の依頼の constraints に運び（lib/carry.py::carried_constraints・lib/carry.py::KEYS の CONSTRAINTS。lib/next-request.schema.json）、次の run の judge が premises.json の制約に足し（lib/judge_accept.py::with_carried・lib/judge_accept.py::CARRIED_FILE）、eyes の支度が目を省かない（workflows/eyes/scripts/prep.py::out の run_eyes）
- tail.md E38: lib/eyeverdict.py::premise_section、workflows/eyes/commands/r2-compare.md
- tail.md E39: lib/eyeverdict.py::human_items、lib/eyeverdict.py::premise_section
- tail.md E40: lib/eyeverdict.py::NO_CONSTRAINTS・lib/eyeverdict.py::NO_REQUEST・lib/eyeverdict.py::premise_section
- tail.md E41: lib/eyeverdict.py::_MD_FENCE・lib/eyeverdict.py::_md_lines・lib/eyeverdict.py::_md_slugs・lib/eyeverdict.py::_MD_RULES
- tail.md E42: lib/eyeverdict.py::premise_section
- tail.md E43: workflows/eyes/scripts/prep.py::premises・workflows/eyes/scripts/prep.py::constraints（判定の隣の premises.json の constraints を読む）、lib/eyeverdict.py::_constraint_rows・lib/eyeverdict.py::constraints_text。再審が走った run も、判定のサブグラフが再審の置き場に premises.json を写す（lib/judge_accept.py::verdict。tests/workflows/test_judge.py::RejudgedVerdictTest.test_rejudge_returns_its_own_units_and_keeps_the_first_judgment）
- tail.md E44: lib/eyeverdict.py::R2_PREMISES・lib/eyeverdict.py::premise_section（返す控え r2_ledger を workflows/eyes/scripts/prep.py が eyes/r2-premises.json に書く）
- tail.md E45: eyes の出力 notes（premise-inputs.json）を lib/eyeverdict.py::r2_input_lines で最後の承認ノード（ask_final の `eye_notes`）と報告（runreport の `_eye_lines`）が R2 の行の下に並べる
- tail.md E46: lib/eyeverdict.py::prompt_texts
- tail.md E47: lib/eyeverdict.py::GREEN_LINE・lib/eyeverdict.py::prompt_texts
- tail.md E48: workflows/eyes/scripts/prep.py::out、lib/eyeverdict.py::collect
- tail.md E49: lib/eyeverdict.py::collect
- tail.md E50: lib/eyeverdict.py::fell_text・lib/eyeverdict.py::_read_eye、lib/eyeverdict.py::collect
- tail.md E51: lib/eyeverdict.py::_off_contract・lib/eyeverdict.py::_row
- tail.md E52: lib/eyeverdict.py::read_design・lib/eyeverdict.py::collect
- tail.md E53: lib/eyeverdict.py::R2_NOT_COMPARED_HEAD・lib/eyeverdict.py::R2_NO_PURPOSE・lib/eyeverdict.py::R2_NO_STANDS・lib/eyeverdict.py::collect
- tail.md E54: workflows/eyes/scripts/verdict.py::fallen（とノードの script の全体を囲む try）・workflows/eyes/works-factory-eyes.yaml::verdict、lib/eyeverdict.py::unverified
- tail.md E55: workflows/eyes/works-factory-eyes.yaml::verdict（ノードの script workflows/eyes/scripts/verdict.py が prep.json の無い時に unverified を返す）・lib/eyeverdict.py::unverified
- tail.md E56: workflows/eyes/works-factory-eyes.yaml::eyes-complete・workflows/eyes/works-factory-eyes.yaml::verdict
- tail.md E57: workflows/eyes/works-factory-eyes.yaml::r1-minimality-verdict・workflows/eyes/works-factory-eyes.yaml::r2-compare-verdict・workflows/eyes/works-factory-eyes.yaml::premise-check-verdict・workflows/eyes/works-factory-eyes.yaml::r3-coherence-verdict・workflows/eyes/works-factory-eyes.yaml::r4-scope-verdict（ノードの script workflows/eyes/scripts/eye_verdict.py。最上位の関数は無い）
- tail.md E58: workflows/eyes/works-factory-eyes.yaml::verdict、lib/eyeverdict.py::RETURN_FIELDS
- tail.md E59: workflows/eyes/works-factory-eyes.yaml::protected（ノードの script workflows/eyes/scripts/protected.py）・lib/protect.py::touched
- tail.md E60: workflows/eyes/works-factory-eyes.yaml::protected（ノードの script の except が lib/seal.py::unknown_row の行を当たりにする）、lib/eyeverdict.py::_protected
- tail.md E61: lib/eyeverdict.py::collect
- tail.md E62: lib/eyeverdict.py::R4_ROWS・lib/eyeverdict.py::_r4_rows・lib/eyeverdict.py::r4_gate_items・lib/eyeverdict.py::collect
- tail.md E63: lib/eyeverdict.py::_human_passed・lib/eyeverdict.py::r4_gate_items
- tail.md E64: lib/eyeverdict.py::_human_passed
- tail.md E65: lib/eyeverdict.py::carried_section・lib/eyeverdict.py::prompt_texts、workflows/eyes/commands/r4-scope.md
- tail.md E66: eyes の出力 notes の隣の gate-passes.json（eyeverdict.gate_pass_rows）を最後の承認ノード（修正前の承認ノードで通した項目の行）と報告（runreport `_gate_passes` の EYE_PASSES_HEAD）が並べる
- tail.md E67: 無し（main の lib と #74 の head のメイングラフの scripts に方針の版の照らしが無い。lib/gatemarks.py::KIND_WORDS に語だけが在る）
- tail.md E68: lib/stage_b.py::run、workflows/eyes/works-factory-eyes.yaml::structure-after（ノードの script workflows/eyes/scripts/structure_after.py が `.archon/` の下を除いて呼ぶ）
- tail.md E69: workflows/eyes/works-factory-eyes.yaml::structure-after（ノードの script workflows/eyes/scripts/structure_after.py が測れない訳を problems に集め status: failed で返す。最上位の関数は無い）
- tail.md E70: lib/planmarks.py::deviations・workflows/eyes/works-factory-eyes.yaml::structure-after
- tail.md E71: workflows/eyes/works-factory-eyes.yaml::structure-after・workflows/eyes/works-factory-eyes.yaml::protected（structure-after と protected に when が無い）、workflows/line/works-factory-line.yaml::eyes（eyes の include に when が無い）
- tail.md E72: workflows/eyes/works-factory-eyes.yaml::verdict（ノードの script が after_ptr を collect に渡す）・lib/eyeverdict.py::collect
- tail.md E73: workflows/line/scripts/ask_final.py::after_rows（structmark.after_lines: 数の 1 文・増えた所・新しい名・外れの訳）と workflows/line/scripts/ask_final.py::needs の柵の増え。報告は lib/runreport.py::_structure_lines、残りは lib/outcome.py
- tail.md E74: lib/eye.py::stamp・workflows/eyes/works-factory-eyes.yaml::structure-after
- tail.md E75: lib/eye.py::problems
- tail.md E76: lib/eye.py::problems・lib/eye.py::accept、lib/design-row.schema.json
- tail.md E77: lib/eye.py::_cut
- tail.md R1: lib/report.py::OUTCOMES・lib/report.py::OUTCOME_WORDS、workflows/report/works-factory-report.yaml::report（出力ノードの enum）
- tail.md R2: lib/outcome.py::_human_stop
- tail.md R3: lib/outcome.py::_human_stop
- tail.md R4: lib/outcome.py::_line_stop・lib/outcome.py::plan_gave_up
- tail.md R5: lib/outcome.py::_waits・lib/outcome.py::asked_conflicts
- tail.md R5b: lib/stopby.py の表の start-refused・needs-human・line-script と、メイングラフの collect（workflows/line/scripts/collect.py::STOPS・stop_<ノード> の with:）→ report の入力 stops → workflows/report/scripts/facts.py → lib/outcome.py::stop_reasons（returns, facts）・lib/outcome.py::WAIT_WORDS（needs-human は needs_human）
- tail.md R6: lib/outcome.py::decide_outcome・lib/outcome.py::record_problems・lib/outcome.py::unknown_answers、workflows/report/scripts/facts.py::main
- tail.md R7: lib/outcome.py::cut_at・lib/outcome.py::CHAIN
- tail.md R8: lib/outcome.py::_no_fix
- tail.md R9: lib/outcome.py::decide_outcome
- tail.md R10: lib/outcome.py::decide_outcome
- tail.md R11: lib/outcome.py::decide_outcome・lib/outcome.py::OK_OUTCOMES、workflows/report/scripts/facts.py::main
- tail.md R12: lib/outcome.py::decide_outcome
- tail.md R13: lib/outcome.py::residue
- tail.md R14: lib/outcome.py::_eye_rows（facts の eyes_skip。メイングラフの redepth の skip_optional が空＝標準なのに出力の無い目を「結果が無い——再実行の要あり」で残りに数える）・lib/runreport.py::_eye_lines（結果が無い目と深さで省いた目を分ける）
- tail.md R15: lib/outcome.py::residue
- tail.md R16: lib/outcome.py::residue（fix の diffs の先の closure.json で closed が偽の単位を残りに。lib/outcome.py::fix_folders・fixbeside.not_closed）
- tail.md R17: lib/outcome.py::_after_rows
- tail.md R18: lib/outcome.py::measured_materials・lib/outcome.py::residue
- tail.md R19: lib/outcome.py::absorbed_rows
- tail.md R20: lib/runreport.py::_decisions の RESIDUE_HEAD の行（結末に依らず 0 件も。残りが在れば MISSING_EYE_NOTE）
- tail.md R21: lib/runreport.py::build・lib/runreport.py::split_line
- tail.md R22: lib/runreport.py::_decisions
- tail.md R23: lib/runreport.py::_decisions（fixbeside.HANDOFF_HEAD の件数と 1 件 1 行。fix の diffs の隣の handoffs.json）
- tail.md R24: lib/runreport.py::_amend_lines（lib/replan.amend_lines。諦めた訳は申し出の行の replan_why）
- tail.md R25: lib/runreport.py::_conflict_line・lib/outcome.py::conflict_counts
- tail.md R26: lib/runreport.py::ledger_state
- tail.md R27: lib/runreport.py::answer_drafts・lib/runreport.py::build
- tail.md R28: lib/runreport.py::unproven_lines
- tail.md R29: lib/runreport.py::_decisions（querytest.STUCK_HEAD・CLOSURE_HEAD の下に fixbeside.closure_lines。lib/querytest.py::closure_lines を表の行で読む形に写した）
- tail.md R30: lib/runreport.py::rejudge_lines・lib/runreport.py::rejudge_changes・lib/runreport.py::rejudge_opened・lib/runreport.py::rejudge_lowered・lib/runreport.py::next_request
- tail.md R31: lib/runreport.py::verify_lines・lib/runreport.py::pr_lines・lib/runreport.py::premise_lines
- tail.md R32: lib/runreport.py::inner_word_lines
- tail.md R33: lib/runreport.py::_hits
- tail.md R34: lib/runreport.py::_gate_passes
- tail.md R35: lib/runreport.py::_converge_lines（converge.lines の行が review の隣の gate.json に在る）
- tail.md R36: lib/runreport.py::_design_lines（事前審査の出力の design の先 design.json。design.anchor_note・UNANCHORED）
- tail.md R37: lib/runreport.py::_decisions（fixbeside.gates_lines・plan_ask_lines・tests_left_lines。fix の diffs の隣の accept-trace.json）
- tail.md R38: lib/runreport.py::_decisions（fixbeside.always_rows: clean が消したファイル〔fix-removed.json〕・レンズ〔lenses.json〕・仕組みの異常は取れない〔U6〕）
- tail.md R39: lib/runreport.py::next_request（fixbeside.next_items の落ちたレンズ）と lib/runreport.py::_unseen_lens_lines（局所レビューの後に fixbeside.lens_lines）
- tail.md R40: lib/runreport.py::_entry_lines
- tail.md R41: lib/runreport.py::_entry_lines（段・entry.features_part・決めた人の承認ノードの答えの数・FORGE_HEAD の forge.reason(forge.detect(repo))）
- tail.md R42: lib/runreport.py::_entry_lines が計画の depth（単位と深さ）だけを出す。lib/depth.py::lines は在るが呼ばれない
- tail.md R43: lib/report.py::freeze_lines・lib/runreport.py::_tdd_lines
- tail.md R44: lib/runreport.py::_stop_lines
- tail.md R45: lib/runreport.py::transcript_facts
- tail.md R46: lib/runreport.py::_reads_lines（lib/runreport.py::transcript_facts の calls と、lib/reads.py::collect が書いた reads-*.json）
- tail.md R47: lib/runreport.py::_where_lines・lib/runreport.py::POINTERS
- tail.md R48: lib/report.py::tdd_lines・lib/runreport.py::_tdd_stages・lib/runreport.py::_tdd_lines
- tail.md R49: lib/runreport.py::_green_lines・lib/runreport.py::_evidence_lines（走らせた一式の行とログは、test-gate-base・test-gate-final の出力の欄 by・suites_line・log を受け皿 test-gate-base-out・test-gate-final-out で受けた物。字は lib/declared_checks.py::gate_values）
- tail.md R50: lib/runreport.py::_eye_lines
- tail.md R51: lib/runreport.py::_structure_lines
- tail.md R52: lib/runreport.py::_world_lines
- tail.md R53: lib/runreport.py::_outside（3 つ目の出力の count_line の 1 行を人が決めることのセクションの、次の run に渡す物の行の前に）
- tail.md R54: lib/runreport.py::cost_rows・lib/runreport.py::head_cost・lib/runreport.py::_model_lines
- tail.md R55: lib/runreport.py::build、workflows/report/scripts/facts.py::main、workflows/report/scripts/facts.py::read_listing
- tail.md R56: lib/runreport.py::_bullets
- tail.md R57: lib/runreport.py::next_request・lib/runreport.py::build
- tail.md R58: lib/runreport.py::prior_failures、lib/report.py::prior_lines
- tail.md R59: lib/carry.py（元とバイト一致）
- tail.md R60: workflows/report/works-factory-report.yaml::write-loop・workflows/report/works-factory-report.yaml::write-reject・workflows/report/works-factory-report.yaml::write・workflows/report/works-factory-report.yaml::cold-prep・workflows/report/works-factory-report.yaml::cold・workflows/report/works-factory-report.yaml::accept、workflows/report/commands/report.md・workflows/report/commands/cold-check.md
- tail.md R61: lib/runreport.py::accept、lib/report_roles.py::format_problems・lib/report_roles.py::count_rejects
- tail.md R62: lib/report_roles.py::head_of・lib/runreport.py::cold_body、workflows/report/commands/cold-check.md
- tail.md R63: lib/runreport.py::collect・lib/runreport.py::embedded
- tail.md R64: lib/runreport.py::stamp
- tail.md R65: lib/runreport.py::glossary_section・lib/runreport.py::pack_terms、lib/glossary.json（バイト一致）
- tail.md R66: lib/runreport.py::build、workflows/report/works-factory-report.yaml::write-loop
- tail.md R67: workflows/report/works-factory-report.yaml::report、workflows/report/scripts/facts.py::fallen・workflows/report/scripts/collect.py::fallen・workflows/report/scripts/facts.py::unwritten・workflows/report/scripts/collect.py::unwritten、workflows/line/works-factory-line.yaml::report（trigger_rule: all_done）
- tail.md R68: workflows/report/works-factory-report.yaml（グラフの入力の 17 の名）・workflows/report/works-factory-report.yaml::report（出力ノードの 7 欄）
- tail.md R69: 無し（メイングラフの result は fixed の真偽だけ。tests/workflows/test_line.py::CollectAndResultCase.test_result_fixed）
- tail.md R70: workflows/line/works-factory-line.yaml::merge-apply（merge-apply は answer-final の go が真の時だけ）
- tail.md R71: 無し（workflows/report/commands/report.md の構成 1 から外した）
- tail.md R72: fix の diff の隣の closure.json（子の結果の closure で運ぶ。lib/fixbeside.py）を最後の承認ノードと報告が querytest.closure_lines で数え直す
- tail.md R73: fix の diff の隣の delta-holes.json（lib/fixbeside.py）→ lib/runreport.py::next_request（fixbeside.next_items: declared と 2 回目の fixed を名札つきで）と lib/runreport.py::_decisions（branch_rows）
- tail.md R74: lib/runreport.py::_depth_lines（redepth の出力を lib/depth.lines の形で）
- tail.md R75: lib/runreport.py::_policy_lines（事前審査の出力 review の隣の policy.json と今の文書を boardview.policy_change で比べ、change_row の 1 行）
- tail.md R76: lib/runreport.py::rejudge_lines（rejudge-exit.json の verdicts の並びと往復の数）・lib/runreport.py::rejudge_exit
- tail.md R77: lib/gatemarks.py::answer_ties・lib/gatemarks.py::ties_of・lib/gatemarks.py::answer_tie_lines・lib/gatemarks.py::returned_lines（判定が単位に結んだ答えの行）。報告は lib/runreport.py::ledger が 1 回目の判定の隣の answer-ties.json を読む。fix は prep が判定の隣から写す
- tail.md R78: lib/rolekit.py::last_reject（段の置き場の下の rejects-*.json の最後の行と reject-*.md・reject-*.txt の一番新しい物）→ lib/runreport.py::_last_reject（止めた段の前の失敗の行の文）
- tail.md R79: lib/runreport.py::_world_lines（world-state.json の reason・classes・dropped）
- tail.md R80: lib/runreport.py::_pr_draft_lines（判定の隣の pr-downgrades.json。material-pr-check.json の reply.conflicts[].note を judge_accept.prcheck_drafts が写した物）
- tail.md R81: lib/runreport.py::stamp（報告のグラフのファイルの版と、始めの記録の versions.line の頭 12 字。読めた記録に無ければ「始めの記録に無い（versions.line）」、始めの記録が読めなければ「読めない（始めの記録が読めない）」）
- tail.md R82: メイングラフの YAML の collect の with: optional（宣言の 1 か所）→ report の入力 optional → lib/runreport.py::transcript_facts（optional=）・lib/runreport.py::_declared（宣言の外の落ちは failed）
- tail.md M1: workflows/merge/scripts/merge.py::main → lib/green_cert.py::diff_bytes
- tail.md M2: workflows/line/scripts/start.py::start（始めの記録の base_rev）→ workflows/merge/scripts/merge.py::main
- tail.md M3: lib/seal.py::write_readback・workflows/merge/scripts/merge.py::main
- tail.md M4: lib/green_cert.py::diff_bytes（ValueError）→ workflows/merge/scripts/merge.py::broken（main の外の except が ok: false と理由で返す）
- tail.md M5: workflows/merge/scripts/merge.py::main
- tail.md M6: lib/seal.py::seal_refusal・lib/green_cert.py::matches
- tail.md M7: workflows/merge/scripts/merge.py::main・lib/seal.py::diff_files・lib/protect.py::hits・lib/protect.py::lines
- tail.md M8: lib/seal.py::diff_files
- tail.md M9: lib/seal.py::diff_files（`--whitespace=nowarn`）
- tail.md M10: lib/seal.py::diff_files・lib/protect.py::lines
- tail.md M11: workflows/merge/scripts/merge.py::main・lib/seal.py::UNKNOWN_HEAD・lib/seal.py::unknown_row
- tail.md M12: workflows/merge/scripts/merge.py::main（`except (protect.Broken, ValueError)`）
- tail.md M13: workflows/.shared/boundary.py::lib_root・workflows/merge/scripts/merge.py::main
- tail.md M14: workflows/merge/scripts/merge.py::main
- tail.md M15: lib/seal.py::apply_refusal
- tail.md M16: lib/seal.py::apply_refusal・workflows/merge/scripts/merge.py::main
- tail.md M17: lib/answer.py::GO_WORDS・lib/answer.py::STOP_WORDS・lib/seal.py::_answer_refusal・lib/seal.py::apply_refusal
- tail.md M18: lib/seal.py::REQUEST_BY・lib/seal.py::_answer_refusal
- tail.md M19: lib/seal.py::STATUSES（REDESIGN）・lib/seal.py::apply_refusal
- tail.md M20: lib/seal.py::apply_refusal
- tail.md M21: lib/seal.py::apply_refusal
- tail.md M22: lib/seal.py::apply_refusal
- tail.md M23: lib/seal.py::apply_refusal
- tail.md M24: workflows/merge/scripts/merge.py::main・workflows/merge/works-factory-merge.yaml::merge（`mutates_checkout: false`）
- tail.md M25: workflows/merge/scripts/merge.py::broken（main の外の except が、どの誤りも終了の値 0 で ok: false と理由にして返す）
- tail.md M26: workflows/line/scripts/ask_final.py::ask（`must`）・workflows/line/scripts/ask_final.py::needs・workflows/line/works-factory-line.yaml::ask-final（merge-seal の protected_hits を ask-final に渡す）
- tail.md M27: workflows/line/scripts/ask_final.py::final_head
- tail.md M28: workflows/line/scripts/ask_final.py::final_text・workflows/line/scripts/ask_final.py::protected_section
- tail.md M29: workflows/line/scripts/ask_final.py::protected_section（差分の見方 git -C <作業ツリー> diff <始めの記録の base_rev> -- <パス> と protect.MANIFEST。確かめられない時は理由と一覧）
- tail.md M30: workflows/line/scripts/ask_final.py::needs（許したテストを触った: must）・workflows/line/scripts/ask_final.py::protected_section（ALLOWED_TESTS_HEAD）。無人の run は開かずに止め merge-apply が飛ぶ
- tail.md M31: workflows/line/scripts/ask_final.py::ask・workflows/line/works-factory-line.yaml::merge-apply（`when: "$answer-final.output.go == true …"`）
- tail.md M32: workflows/line/scripts/ask_final.py::final_text
- tail.md M33: workflows/line/scripts/ask_final.py::needs・workflows/line/scripts/ask_final.py::final_needs
- tail.md M34: workflows/line/works-factory-line.yaml::merge-apply（when）・workflows/line/scripts/gate_answer.py::take → lib/answer.py::taken
- tail.md M35: lib/runreport.py::_stop_lines
- tail.md M36: lib/runreport.py::POINTERS・lib/runreport.py::_where_lines
- tail.md M37: lib/runreport.py::_apply_lines（人が決めることのセクション: 差分を置いた run は bin/apply <run-id>、止まった run は止まりの 1 行と --allow-stopped、R2 が redesign-needed の run は当てない。生の git apply は出さない）
- tail.md M38: lib/seal.py::deleted_paths・lib/seal.py::DELETED_HEAD。最後の承認ノードは workflows/line/scripts/ask_final.py::deleted_files（封じた差分 $merge-seal.output.diff） 。報告の側は lib/runreport.py::_tests_head_lines（seal.deleted_paths。部分 C）
- tail.md M39: bin/_lib/apply.py::main・bin/_lib/apply.py::put
- tail.md M40: bin/_lib/apply.py::main（封じた hash と置き場のファイルの sha256 の照らし）・bin/_lib/apply.py::choose（apply.hash と sealed.hash の照らし）
- tail.md M41: bin/_lib/apply.py::pointed（置き場の根 artifacts.root の下の差分だけを読み、run の作業ツリーを読まない）
- tail.md M42: bin/_lib/apply.py::put（`--allow-delete`）
- tail.md M43: bin/_lib/apply.py::choose・bin/_lib/apply.py::stopped_why（結末の語・止めた所・人の一言。人の一言はメイングラフの result の final_answer: workflows/line/scripts/result.py::main）
- tail.md M44: bin/_lib/apply.py::choose（`--allow-stopped`。R2 が redesign-needed なら旗でも拒む）・bin/_lib/apply.py::main（「--allow-stopped が在るので当てた」の 1 行）
- tail.md M45: bin/_lib/apply.py::read_run（記録が無い・returns が読めない run は 2 で拒む）・bin/_lib/apply.py::unchecked（拒む 1 行に置き場の差分を素の git apply で当てる道）
- tail.md M46: bin/_lib/apply.py::choose（封じていない差分は `--allow-stopped` でも当てない）・bin/_lib/apply.py::from_worktree（拒む 1 行に作業ツリーの差分を素の git apply で当てる道。R2 の作り直しには書かない）
- tail.md M47: bin/_lib/apply.py::put（`git apply --check`）
- tail.md M48: bin/_lib/apply.py::put（`git apply -R --check`）
- tail.md M49: bin/_lib/apply.py::main・bin/_lib/apply.py::Refuse・bin/_lib/apply.py::one_line（拒み 1・読めない run 2）
- tail.md M50: bin/_lib/apply.py::main（許しは旗 `--allow-delete`・`--allow-stopped` だけで、環境変数を読まない）
- tail.md M51: bin/_lib/apply.py::main（対象は bin/_lib/launcher.py::target_root）・bin/_lib/apply.py::ask_launcher（殻の `workflow get <run> --json --cwd <対象>`）
- tail.md M52: bin/_lib/apply.py::pointed
- tail.md M53: 無し（周の鎖そのものがまだ無い）
- tail.md M54: lib/protected.json・lib/protect.py::load
- tail.md M55: lib/protect.py::match（planmarks.glob_match）
- tail.md M56: lib/protected.json（行 manifest・checker・checker-test）
- tail.md M57: lib/protected.json（行 baseline-red・baseline-red-test・green-cert・green-cert-test）
- tail.md M58: lib/protected.json
- tail.md M59: lib/protect.py::_problems・lib/protect.py::load
- tail.md M60: lib/protect.py::touched・workflows/eyes/works-factory-eyes.yaml::protected（ノードの script workflows/eyes/scripts/protected.py が protect.touched を呼ぶ。script に最上位の名は無い）
- tail.md M61: 無し。main に今在るのに一覧に無い物: `workflows/*/scripts/*_accept.py`・`workflows/*/works-factory-*.yaml`・`lib/tddloop.py`・`lib/tests/test_blk_fix_tdd.py`・`workflows/fix/scripts/assert_changed.py`・`lib/tree_run.py`・`bin/_lib/isolate.py`・`tests/bin/test_isolate.py`・`lib/judge_accept.py`。メイングラフの `workflows/line/**` も無い（prereq の計画 docs/plans/2026-10-12-blocks/prereq.md:22 は `線の PR が足す` と書いたが、#74 の lib/protected.json は main と同じだった）
- tail.md M62: 無し（lib/protected.json の copies は空）。bin/_lib/place.py::workflow_source は pack を run の作業ツリーに写さず、別の置き場から `--workflow-source` で読ませる
- tail.md M63: workflows/eyes/works-factory-eyes.yaml::protected（ノードの script workflows/eyes/scripts/protected.py）は `protect.touched`（本物の index を通すので assume-unchanged・skip-worktree の変更を見落とす）、merge は `seal.diff_files`（M8）。報告は目の当たりも数える（lib/runreport.py）ので、2 つが食い違う道が在る
