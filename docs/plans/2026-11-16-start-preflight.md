# 起動の前の確かめを 1 回にまとめる（設計の相談）

起動の殻 `bin/works-factory`（中身は `bin/_lib/launcher.py`）が、足りない物を 1 つ見つけるたびに止まり、AI が打ち直しを 4 回重ねた。
この文書は、足りない物を 1 回で全部並べて止める形と、版管理の道具の shim（`PATH` に置かれた代わりの実行ファイル）の版が無い時と、殻の隔離（HOME・XDG の付け替え）の中で shim が起きない時と、
Claude Code の会話の中から打った時の認証の案内の、案・代案・残る問いを書く。実装はまだ始めていない。

持ち主の答え（2026-11-16。受付 20261116-001019-dd5cea で窓口が伝えた）を入れて、実装に渡せる形にした。答えは 2 つ:

- 問い 1（トークンを出すコマンドを名指す env を足すか）は「足す」。(c) の C4 を採り、先に持ち主の決め `oauth-token-command`（`docs/owner-decisions.md`）を書いた（E10）。
- 問い 2（keychain の無い OS で `WORKS_FACTORY_KEYCHAIN_ITEM` を見た時）は (1) 止める。訳は「keychain は macOS だけ。この OS ではこの変数を外す」。
  持ち主の Linux の設定からは窓口がこの変数を外し、配っている設定の雛形も macOS でだけ置く形に直した（リポジトリの外）。

実装の手順は 6 章。

## 1. 起きたこと（2026-11-16、別のリポジトリの部署 2 つ。Linux arm64・Claude Code の裏の会話）

部署の会話の記録で確かめた止まり方の順:

1. `bun が無い`（片方の部署だけ。`PATH` に bun が無かった）。
2. `Archon の源 … が取れない: Command '['bun', 'install', '--frozen-lockfile']' returned non-zero exit status 1.`
   その上の行に `mise ERROR No version is set for shim: bun` と、版管理の道具 mise 自身の直し方の 1 行（`mise use -g bun@<版>`）が出ていた。
   `place.archon_source` は `shutil.which("bun")` で在るかだけを見るので、在るのに起きない shim を通す。
3. 部署が `PATH` の頭に mise の入れた版の置き場を足すと、同じ所で `No version is set for shim: node`。Archon の源の
   `package.json` の `scripts.prepare` は `husky` で、`bun install` がそれを起こし、husky（9.1.7）の `bin.js` の頭は
   `#!/usr/bin/env node`。だから源を入れる時だけ node が起きる。入れ終えた後の起動は node を使わない。
4. node も足すと `認証が無いか、確かめられない。…（keychain の項目 <名> を読めない: keychain-error(FileNotFoundError)）`。
   Claude Code の設定の `env` に `WORKS_FACTORY_KEYCHAIN_ITEM` が書いてあり、Linux には keychain を読む `security` が無い。
   名指しは一番上の段なので（`bin/_lib/auth_launch.py` の `resolve`）、ほかの段を見ずに止まる。
   部署は名指しを外し、手元のトークンを出すコマンドの出力を `CLAUDE_CODE_OAUTH_TOKEN` に置いて通した。
   名指しを外すだけでは通らなかった見込みが高い: この裏の会話（同じアカウント・同じ OS）の Bash で確かめると、`CLAUDE_CODE_OAUTH_TOKEN` も
   `ANTHROPIC_API_KEY` も env に無く、設定の置き場に `.credentials.json` も無く、`claude auth status` は `loggedIn: false`・`authMethod: none`。

5. （足し。受付 20261115-235624-48b59a）利用者が版管理の道具 mise の全体の設定 `<HOME>/.config/mise/config.toml` に `bun = "1"`・`node = "22"` を足し、
   素のシェルでは shim の bun・node が起きるようになった後も、対象の clone で `workflow status --cwd .` を打つと
   `mise ERROR ... Config files in <HOME>/.config/mise/config.toml are not trusted` で止まる。

   この裏の会話で再現した（2026-11-16、mise 2026.10.25 linux-arm64）。`HOME`・`XDG_*` を一時の置き場へ向けた env（`bin/_lib/isolate.py` の
   `isolate` と同じ向け方）で、対象の clone の中から shim の `bun --version` を打つと同じ字で落ちる。利用者の env では `1.4.4` と答える。訳:

   - mise は全体の設定を `$XDG_CONFIG_HOME/mise/config.toml`（無ければ `$HOME/.config/...`）と決める。隔離で `XDG_CONFIG_HOME` が
     run の置き場へ向くので、利用者の `<HOME>/.config/mise/config.toml` は全体の設定でなくなる。
   - mise は打った場所から親へ `.config/mise/config.toml` などの名を探す。対象の clone も run の置き場も利用者の HOME の下なので、
     親をたどって `<HOME>/.config/mise/config.toml` に当たり、それを「その場所の設定」として読む。その場所の設定は信頼が要る。
   - 信頼の控え（`$XDG_STATE_HOME/mise`）も、信頼する置き場の設定（`trusted_config_paths`。利用者のはこの全体の設定の中に書いてある）も
     隔離の側に無いので、信頼の外に落ちる。利用者のシェルで `mise trust --show` が trusted と言うのは、隔離の前の env で見たから。
   - `MISE_TRUSTED_CONFIG_PATHS` でその 1 つを信頼させても、次の親（`<対象の親>/mise.toml`）で同じに落ちる。入れた版の置き場
     （`$XDG_DATA_HOME/mise`）も隔離の側に無い。mise の名の env をいくつ渡しても、隔離の向けた置き場との食い違いが残る。
   - 実体の置き場を `PATH` の頭に置けば、隔離した env でも `bun --version` は `1.4.4` と答える（shim を通らないので mise が起きない）。

   隔離した env で `bun` を名で起こすのは 2 か所: 殻が起こす Archon の本体（`launcher.launch` の `shutil.which("bun", path=child["PATH"])` は
   shim のパスを返し、`place.archon` がそれを子の env で起こす）と、`archon-pr` の `runtime: bun` の script のノード 2 つ（Archon の
   `script-invocation.ts` は `bun` を名で起こす）。工場の pack の script のノードは全部 `runtime: uv` で、`uv` が shim なら同じに落ちる
   （この環境の uv は shim でないので、確かめていない）。役の Bash で shim の道具を打っても同じ仕組みで落ちる見込みがある（確かめていない）。
   `bun install`（`place.bun_install`）は利用者の env で走るので、この止まり方はしない。

訳は 4 つ（4 つ目は 5 の足し）:

- 殻の止まる所が順に並び、最初の 1 つで止まる。bun の確かめ（`place.archon_source` の頭）→ 源の取り寄せと `bun install` →
  …→ 認証の確かめ（`launcher.launch` の `auth_launch.py check`）の順で、認証は源を取った後でしか見ない。
- 「在るか」だけを見て「起きるか」を見ない。shim は在るので通り、`bun install` の中で落ちる。落ちた時の 1 行は
  `CalledProcessError` の字だけで、道具が言った直し方の行は別の所に流れて捨てられる。
- 止まった訳の字（`keychain-error(FileNotFoundError)`）が「この OS には keychain が無い」と言わず、直し方の文（`HOWTO`）は
  あらゆる道を 1 段落に並べ、この場面の道（会話の中の Bash にはトークンが渡らない時の道）が埋もれる。
- 確かめを利用者の env でしかしない。隔離した env（`HOME`・`XDG_*` を run の置き場へ向けた env）で起きるかは見ず、
  版管理の shim のように HOME・XDG から設定を引く道具は、利用者の env で起きても隔離した env で落ちる。

## 2. 直す形

### (a) 足りない物を 1 回で全部並べて止める

案 A1（採る）: 殻の頭に「起こす前の確かめ」を置き、副作用（源の取り寄せ・依存を入れる・Archon を起こす）の前に、
下の確かめを全部打って、足りない物を 1 つの `Stop` に箇条で並べる。形は `launcher.spec_reviews` の止め方（見出しの 1 行と `- ` の行）に合わせる。

| 確かめ | いつ | 足りない時 |
| --- | --- | --- |
| bun が起きる | すべての命令 | 止める |
| uv が起きる | 実行する命令 | 止める |
| node | 源をまだ入れていない時 | 見つかるのに起きない時だけ止める |
| 本物の claude | 実行する命令 | 止める |
| 認証 | 実行する命令（`WORKS_FACTORY_NO_AUTH=1` を除く） | 止める |
| 隔離した env で bun・uv が起きる | bun はすべて・uv は実行する命令 | 止める（(d)） |

- 「起きる」は `<道具> --version` を利用者の env で打ち、終了の値が 0 かで決める。待ちの上限は付けない（持ち主の決め `no-timeouts`）。
  版管理の shim は打った場所ごとに版を選ぶので、その道具を実際に起こす場所で打つ（`bun install` は源の取り置きの置き場、Archon は打った場所）。
- 起きない時の行は、見つけた実のパス（`os.path.realpath`。shim なら `<HOME>/.local/share/mise/shims/bun` のように見える）と
  終了の値と、道具の標準エラーの頭の数行をそのまま載せる。mise なら直し方の 1 行がそこに入る。
- node は、見つからない時は止めない。node の無い環境で bun が `prepare` をどう扱うかは確かめていないので、決めは `bun install` に任せる。
  見つかるのに起きない時（今回の shim）だけ止める。
- uv は今の殻が見ていない（`spec_reviews` を除く）。Archon の script のノードが起こすので、無いと run の途中で落ちる。同じ類として足す。
- 認証の確かめは源を使わない。今は源の取り寄せ（`place.archon_source`）が認証の前にあるので、源の取り寄せを認証の確かめの後ろへ移す。
  源を最初に使うのは `forge_folder`（Archon の子の `PATH` を組む所）で、認証の確かめはその `PATH` を要らない。
  副作用の順（源の取り寄せ → Archon の起動）は変わらず、変わるのは止まる所の位置だけ。E15 の「今の works の `archon.sh` と同じ順」から外れる所として commit に書く。
- `auth_launch.py check` は止まる時の訳を標準エラーに自分で出す。並べるために、check の標準エラーを殻が受けて 1 つの箇条に入れる（値は元から出さない）。
- 確かめが全部通った後の失敗（網に届かない・`bun install` が別の訳で落ちる・exec の 1 回だけ起こす `apiKeyHelper` と
  `WORKS_FACTORY_OAUTH_TOKEN_COMMAND`（(c) の C4）のコマンドが落ちる）は、今のまま 1 つで止まる。その時の 1 行に、`bun install` の標準エラーの
  末尾を入れる（`place.forge_plugin` が既にしている形。今は `check=True` だけで字を捨てている）。

代案 A2（採らない）: `bun install --ignore-scripts` で node を要らなくする。`prepare` の husky は Archon の開発者の git のフックで工場には要らないが、
依存の側の install の台本も止まるので、`node_modules` が今と同じになるかを測らないと選べない。測るなら別の頼みにする。

代案 A3（採らない）: Archon の `doctor`（`packages/cli/src/commands/doctor*.ts`。点検を全部打って並べる命令）を起動の前に打つ。
bun の上で走るので bun が起きない時には打てず、工場の認証の段（`auth_launch.py`）も知らない。並べる形だけを借りる。

### (b) 版管理の shim に版が無い時

案 B1（採る）: 工場は版管理の道具を知らない。(a) の「起きるか」の確かめが、道具自身の標準エラーをそのまま見せる。
mise は版が無い時に `mise use -g bun@<入っている版>` を自分で言うので、直し方の 1 行はそれで届く。

代案 B2（採らない）: `<HOME>/.local/share/mise/installs/<道具>/<版>/bin` を探して使う。採らない訳:

- 版管理の道具は mise のほかにもある（asdf・nvm・volta・proto など）。1 つだけを読むと、ほかの人の環境（E14）で同じ穴が残る。
- 版を工場が選ぶことになる。Archon は `engines.bun` に版を書く（今の源は `1.4.2`）。入っている版のどれを選ぶかを工場が決めると、
  利用者が版を決めていないことを隠し、合わない版で黙って走りうる。
- `PATH` を書き換えると、利用者の env に戻して走らせる対象のコマンド（`lib/userenv.py`。持ち主の決め `target-user-env`）との違いを殻が作る。

代案 B3（採らない）: bun の置き場を名指す env（`CLAUDE_BIN_PATH` の bun 版）を足す。`PATH` の頭に足せば今も届くので、新しい名は要らない。

### (c) Claude Code の会話の中から打った時の認証

案 C1（採る。持ち主の答えの (1)）: `WORKS_FACTORY_KEYCHAIN_ITEM` が在り、OS が macOS でない時は、`security` を起こさずに止める。
今の `resolve` は名指しを見ると OS を見ずに `claude_auth.read_keychain` を呼び、`security` が無いので `keychain-error(FileNotFoundError)` の字で止まる。
名指しの段の頭で `platform != "darwin"` を見て、次の訳で止める（止める所は今と同じ一番上の段。変わるのは訳の字と、`security` を起こさないこと）:
「`WORKS_FACTORY_KEYCHAIN_ITEM`（keychain の項目 <名>）を名指しているが、keychain は macOS だけ。この OS ではこの変数を外す
（設定の `env` に書いたなら、この OS の設定から外す）。トークンは `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` か `CLAUDE_CODE_OAUTH_TOKEN` で渡せる」。
告げて下の段へ飛ばす C5 は採らない（持ち主の決め `api-key-helper-relay` の、名指した道を黙って別の口に差し替えない向き）。

案 C2（採る）: 止まる時の 1 行を、訳 → この OS とこの場面の短い直し方 → 一般の文（今の `HOWTO`）の順にする。Linux で、受け継いだ認証も
`.credentials.json` も無い時の直し方は「Claude Code の会話の中の Bash には、その会話のログインのトークンが渡らない（`claude auth status` の
`loggedIn` が false になる）。`claude setup-token` で作った長期のトークンを出すコマンドを、設定の `env` の `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` に
書く（毎回の手の配線が要らない）か、打つ命令の前で `CLAUDE_CODE_OAUTH_TOKEN` に置く」。
(a) の箇条に入るのはこの短い形で、一般の文は工場の README の認証の項目を指す。

案 C3（このリポジトリの外）: プラグインのスキルの本文（`raiki61/claude-plugins` の works-factory プラグインの `references/auth.md`）に、
「Linux と、Claude Code の会話の中から打つ時」の項目を足し、C2 と同じ道を先に書く。工場の文と同じ字にする。

案 C4（採る。持ち主の答え「足す」。持ち主の決め `oauth-token-command`）: トークンを出すコマンドを名指す env `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` を足す。
設定の `env` に書けば、会話の中の Bash（裏の会話も）で毎回の手の配線が要らなくなる。形は `apiKeyHelper`（`bin/_lib/auth_launch.py` の
`find_helper`・`run_helper`・`user_command`）に揃え、新しい起こし方を作らない:

- 値はシェルのコマンドの字。空の字は無いものとする。
- 起こすのは exec の 1 回だけで、Archon を起こす直前。check（(a) の確かめも）は起こさず、出どころの名
  「トークンを出すコマンド（`WORKS_FACTORY_OAUTH_TOKEN_COMMAND`）」だけを返す（`apiKeyHelper` と同じ。使い捨ての出力や、パスワードの置き場が
  指紋を求める時に 2 回起こさない）。
- 起こす env は `helper_base_env`（殻が控えた隔離の前の HOME・XDG に戻す）に `HOME`・`CLAUDE_CONFIG_DIR` を利用者の物で重ねた物。
  `user_command(..., shell=True)` で、標準エラーは端末へ流し、標準出力だけを捕まえる。待ちの上限は付けない（`no-timeouts`）。
  設定のファイルの `env` は重ねない（この変数自体が設定の `env` から殻の env に来ているので、`apiKeyHelper` のように読み直す要が無い）。
- 標準出力の前後の空白を除いた字を `CLAUDE_CODE_OAUTH_TOKEN` として子に渡す。値は表示も保存もしない。
- 起こせない・終了の値が 0 でない・出力が空の時は、ほかの段（起動方法の門・保存済みのログイン）へ落ちず、
  「`WORKS_FACTORY_OAUTH_TOKEN_COMMAND` のコマンドが失敗した: <訳>」で止まる（訳は `run_helper` と同じ字。値とコマンドの字は出さない）。
- 段の位置は環境の `CLAUDE_CODE_OAUTH_TOKEN` と同じ所: `apiKeyHelper` の後、起動方法の門の前。環境に `CLAUDE_CODE_OAUTH_TOKEN` も在れば
  環境の値を採り、コマンドは起こさない（その起動で手で渡した値が先）。名指し・受け継いだ認証・`CLAUDE_KEYCHAIN_SERVICE`・`apiKeyHelper` は
  今のまま先に効く（Claude Code 自身の優先順の 4. `apiKeyHelper` → 5. `CLAUDE_CODE_OAUTH_TOKEN` に合わせる）。殻の「認証は … から拾う」の 1 行が
  どの段で決まったかを言うので、上の段が勝った時も黙ってはいない。
- exec が Archon を起こす時（`child_env`）、子の env からこの変数を外す。子はトークンを受けるので要らず、役の Bash が利用者のパスワードの置き場を
  打つ道を残さない（堅い境ではなく事故の柵。役は利用者の設定のファイルを読める）。
- `WORKS_FACTORY_KEYCHAIN_ITEM` と両方在る時は、今の名指しの段が先に効く（macOS では keychain、ほかの OS では C1 で止まる）。新しい止め方は足さない。

段の位置の代案（採らない）: 名指しの段（一番上。`WORKS_FACTORY_KEYCHAIN_ITEM` の隣）に置く。工場だけの名なので、親の env の
`ANTHROPIC_API_KEY` より先に効かせる向きは立つが、相談で推して持ち主が「足す」と答えたのは `apiKeyHelper` の後の位置で、
`api-key-helper-relay` が Claude Code の優先順に合わせた並びとも揃う。

代案 C5（採らない。持ち主の答えは (1)）: keychain の無い OS では名指しを 1 行告げて飛ばし、下の段へ進む。

### (d) 隔離した env で版管理の shim が起きない時（足し。1 章の 5）

案 D1（採る）: 隔離の前に、利用者の env で、隔離した env が名で起こす bun の実体のパスを bun 自身に聞き、子はそれを起こす。

- 聞き方は `bun -e "console.log(process.execPath)"` を利用者の env で、Archon を起こす場所（対象の根）で打つ。bun 自身が実体のパスを言うので、
  工場は版管理の道具を知らない（mise・asdf・proto・volta のどれでも同じ。B1 と同じ向き）。版を選ぶのは利用者の env と、その場所の設定のまま。
- Archon の本体は、そのパスを `place.archon` に渡す（今の `shutil.which` の代わり）。
- `archon-pr` の `runtime: bun` のノードは `bun` を名で起こすので、run の置き場の下のフォルダに実体を指す `bun` のリンクを 1 つ置き、子の `PATH` の頭に足す
  （`forge_folder` と同じ足し方）。フォルダにはリンクを 1 つだけ置く（実体の置き場ごと足すと、同じフォルダのほかの物まで先に見える）。
- 対象のコマンド（`lib/tree_run.py` の `outside_env`）は、利用者の `PATH` で走るよう、そのフォルダを頭から外す（今の `_drop_uv` と同じ外し方。
  外す置き場の名は `lib/userenv.py` の制御の変数で渡す）。外さないと、対象の下の階の設定が選ぶ版でなく、対象の根で選んだ版が先に見える。
- uv は自分の実体のパスを言う口が無い。(a) の確かめで、隔離した env で `uv --version` を打ち、利用者の env では起きるのに隔離した env で起きない時は止めて、
  「HOME・XDG を run の置き場へ向けた env では、版管理の shim が設定を見失って起きない。実体の置き場を `PATH` の頭に足して打つ」と、道具の標準エラーの頭の数行を載せる。
- 確かめの順: bun の実体を聞く（利用者の env）→ 隔離した env で、そのパスの `bun --version` と `uv --version` を打つ。D1 の後も落ちる時は (a) の箇条に入れる。

代案 D2（採らない）: 子の env に mise の置き場の名（`MISE_GLOBAL_CONFIG_FILE`・`MISE_DATA_DIR`・`MISE_STATE_DIR`・`MISE_TRUSTED_CONFIG_PATHS` など）を利用者の値で渡す。

- mise だけを知ることになる。asdf（`ASDF_DATA_DIR`）・volta（`VOLTA_HOME`）などで同じ穴が残る（E14。B2 と同じ訳）。
- 隔離は Archon・役・script のノードが利用者の家の設定と状態を読み書きしないためにある（`bin/_lib/isolate.py` の頭）。mise の state と data を
  利用者の物へ向けると、役の Bash の `mise` が利用者の信頼の控えや入れた版を書き換えうる穴になる。
- 1 章の 5 のとおり、名を 1 つ渡すと次の親で落ちる。渡す名の数がいくつで足りるかを、mise の版ごとに工場が追うことになる。

代案 D3（採らない）: 利用者に `mise trust` を打ってもらう。信頼の控えは隔離した `XDG_STATE_HOME` の下に書かれ、利用者のシェルの `mise trust` は
そこに届かない。run の置き場のパスを利用者に教えて打たせる形は、置き場の形を利用者に漏らす。

代案 D4（採らない）: 隔離をやめて HOME・XDG を利用者の物のままにする。持ち主の決め `bring-launch` と `target-user-env`（隔離のまま走らせる物と、戻す物の分け）を崩す。

## 3. E11 の 3 つ

1. Archon が持っているか: `doctor` が点検を並べるが、bun の上で走るので bun が起きない時に打てず、工場の認証の段を知らない（A3）。持っていない。
2. ASF が持っているか: `factory/consumer.py` の `verify_source`・`doctor` は取り置いた源の形と命令の能力を照らすだけで、道具が起きるかと認証は見ない
   （`doctor` の返す値も `authentication not live-tested`）。持っていない。
3. 本当に要るか: 要る。止まるたびに AI が打ち直すので、1 回の run の前に 4 回の起動と、そのたびの文の読みが要った。直す所は新しい仕組みでなく、
   今ある止まる所の並べ方と字で、新しい置き場も常駐の物も足さない（C4 だけが新しい選べる道で、持ち主が「足す」と答え、決め `oauth-token-command` を先に書いた）。
   C4 も要る: Claude Code の会話の中の Bash には会話のログインのトークンが渡らず（1 章の 4）、`claude /login` しただけの Linux の人は毎回の起動で
   トークンを手で配線することになる。Archon は認証を子の `claude` に任せるだけで、ASF の `consumer.py` も認証を見ない（1 と 2 の答えのとおり）。
   起こし方は `apiKeyHelper` の部品をそのまま使い、新しい起こし方は作らない。
   (d) も要る: 利用者が素のシェルで直し終えても、隔離した env で同じ道具が落ち、利用者の側では直せない（D3）。足す物は run の置き場の下の
   リンクのフォルダ 1 つで、作り方は今の `forge_folder`、対象のコマンドの `PATH` からの外し方は今の `_drop_uv` と同じ形。新しい層・置き場の類は足さない。
   Archon は bun を `PATH` の名で起こすだけで（`script-invocation.ts`）、隔離した HOME での shim を扱う物を持たない。ASF の `consumer.py` も
   `settings.get("bun", "bun")` の名で起こす。

## 4. 試験の計画（実装の時。直しを外すと落ちる試験を先に書く）

- `tests/bin/test_launcher.py`: 一時の `PATH` に、`--version` で終了 1 と決まった字を標準エラーに出す偽の `bun`・`node` を置き、認証も無い env で
  `launch` を打つ。止まりの字に bun・node・認証の 3 つの箇条が全部在り、源を取りに行っていない（偽の fetch が呼ばれない）ことを見る。
  今の殻では bun の 1 つで止まるので落ちる。
- 同じ所で、node が見つからない時は止めないこと、源が取り置き済みの時は node を見ないことを見る。
- `tests/bin/test_auth_launch.py`（C1）: `platform` を `linux` にし、名指しの項目が在る時、止まりの訳が「keychain は macOS だけ」と
  「この変数を外す」を言い、`security` の runner が 1 度も呼ばれないことを見る。今の殻は runner を呼んで `keychain-error` の字で止まるので落ちる。
- `tests/bin/test_auth_launch.py`（C4。偽のコマンドは一時の置き場の小さな台本で、呼ばれた数と受けた `HOME` を一時のファイルに書く）:
  - check はコマンドを起こさず（呼ばれた数 0）、出どころの名に `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` が在る。
  - exec はコマンドを 1 回、利用者の `HOME`（隔離した `HOME` でない）で起こし、子の env の `CLAUDE_CODE_OAUTH_TOKEN` が出力の値で、
    子の env に `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` が無く、殻の標準出力と標準エラーに値が出ない。
  - コマンドが終了 1 で終わる時と出力が空の時、一時の `<CLAUDE_CONFIG_DIR>/.credentials.json` が在っても、それを使わずに変数の名を言って止まる。
  - 環境に `CLAUDE_CODE_OAUTH_TOKEN` が在る時・`apiKeyHelper` の設定が在る時・環境に `ANTHROPIC_API_KEY` が在る時は、コマンドを起こさない。
  - 変数が空の字の時は無いものとして、今の段（保存済みのログイン）へ進む。
  - どれも今の殻には口が無いので、check の名と exec の値の照らしで落ちる。
- `tests/bin/test_place.py`: `bun install` が標準エラーを出して落ちた時、`RuntimeError` の字にその末尾が載ることを見る。
- `tests/bin/test_launcher.py`（(d)）: 一時の置き場に、`HOME` が殻を起こした時の値でなければ終了 1 で落ちる偽の `bun` の shim と、
  その実体（`-e` で自分のパスを言い、`--version` に答える偽の bun）を置く。`launch` の組む Archon の命令の頭が実体のパスで、子の `PATH` の頭の
  フォルダの `bun` が実体を指すことを見る。今の殻は shim のパスを渡すので落ちる。
- 同じ所で、偽の `uv` の shim が隔離した env でだけ落ちる時、止まりの箇条に uv の行と「HOME・XDG を run の置き場へ向けた env」の訳が在ることを見る。
- `lib/tests/test_tree_run.py`（(d)）: 制御の変数で名指したフォルダが `PATH` の頭に在る時、対象のコマンドの `PATH` から外れることを見る。
- 手元は `tests/changed.py` だけを回す（`tests/AGENTS.md`）。

## 5. 残る問い

持ち主の選びの問いは残っていない（2 つとも 2026-11-16 に答えが来た。頭の段落と (c)）。実装の時に確かめる設計の問いが 2 つ残る（どちらも (d)）:

- 役の Bash（隔離のまま）で shim の道具（この環境なら `yq`・`node`）を打つと同じに落ちるか。落ちるなら、役の `PATH` から shim を外すか、
  役の指示に書くかを別に決める。今の頼みの範囲（起動の前）の外。
- uv が shim の環境で、uv の実体を道具を知らずに引く口が無いか（D1 は uv を止めて案内するだけ）。

## 6. 実装の手順

PR を 3 つに分ける。1 は 2・3 と独立で、小さく先に入れられる。2 の後に 3 を積む（3 の uv の行は 2 の箇条に入る）。
どの PR も、4 章のその PR の試験を先に書き、直しを外すと落ちることを見てから直す。手元は `tests/changed.py` だけを回す。

1. 認証の口（(c) の C1・C2・C4。持ち主の決め `oauth-token-command`）
   1. `bin/_lib/auth_launch.py`:
      - `resolve` の名指しの段の頭で、`platform != "darwin"` なら `security` を起こさずに C1 の訳で止める。
      - 名の置き場 `TOKEN_COMMAND_ENV = "WORKS_FACTORY_OAUTH_TOKEN_COMMAND"` を `ITEM_ENV` の隣に足す。
      - `resolve` の「設定の無い OAuth トークンだけの認証」（`if claude_auth.added(note):`）の直後、起動方法の門の前に C4 の段を足す。
        起こすのは `run_helper` に、`helper_base_env` と `user_command(..., shell=True)` で組んだ runner を渡す形（試験は `helper_runner` と同じく差し替える口を持つ）。
      - `child_env` が `TOKEN_COMMAND_ENV` を外す。
      - `HOWTO` に C4 の 1 文を足し、keychain の項目名の文に「macOS だけ」を足す。頭の docstring の段の順に C4 の段を足す。
      - C2: Linux で保存済みのログインも無い時の止まりの字を、訳 → 会話の中の Bash の短い直し方 → `HOWTO` の順にする。
   2. `README.md` の環境変数の項（英語）: `WORKS_FACTORY_KEYCHAIN_ITEM` の行に macOS だけと、ほかの OS では止まることを足す。
      `WORKS_FACTORY_OAUTH_TOKEN_COMMAND` の行を足す（起こす時・env・値を出さない・失敗で止まる・段の位置・子に渡さない）。
      `apiKeyHelper` の行の優先の並びの文に、`CLAUDE_CODE_OAUTH_TOKEN` と同じ位置であることを足す。
   3. 試験: 4 章の `tests/bin/test_auth_launch.py`（C1・C4）。
2. 起動の前の確かめを 1 回にまとめる（(a)・(b)）
   1. `bin/_lib/launcher.py`: 副作用の前に確かめを全部打ち、足りない物を 1 つの `Stop` に箇条で並べる関数を 1 つ足す（形は `spec_reviews` の止め方）。
      源の取り寄せ（`place.archon_source`）を認証の確かめの後ろへ移す。`auth_launch.py check` の標準エラーを受けて箇条に入れる。
   2. `bin/_lib/place.py`: `archon_source` の頭の `shutil.which("bun")` の確かめを外して殻の確かめへ寄せる。`bun_install` の落ちた時の字に標準エラーの末尾を載せる。
   3. `bin/AGENTS.md` の E15 の「`archon.sh` と同じ順でつなぐ」を、「副作用の順は `archon.sh` と同じ。止まる所の確かめは副作用の前にまとめる」に書き直す（人が見る決まりの字。同じ PR で）。
   4. 試験: 4 章の `tests/bin/test_launcher.py`（(a)）・`tests/bin/test_place.py`。
3. 隔離した env で shim が起きない時（(d) の D1）
   1. `bin/_lib/launcher.py`: 利用者の env で、対象の根で `bun -e "console.log(process.execPath)"` を打って実体のパスを得て、`place.archon` に渡す。
      run の置き場の下に実体を指す `bun` のリンクを 1 つだけ置いたフォルダを作り、子の `PATH` の頭に足す（`forge_folder` と同じ足し方）。
      隔離した env での `bun --version`・`uv --version` を 2 の箇条に足す。
   2. `lib/userenv.py` に、そのフォルダを渡す制御の変数の名を足し、`lib/tree_run.py` の `outside_env` が `_drop_uv` と同じ形でそのフォルダを `PATH` から外す。
   3. 試験: 4 章の `tests/bin/test_launcher.py`（(d)）・`lib/tests/test_tree_run.py`。

リポジトリの外の手（窓口へ）: (c) の C3（`raiki61/claude-plugins` の works-factory プラグインの `references/auth.md` に、Linux と会話の中から打つ時の項目を、
PR 1 の README と同じ道で足す）。PR 1 が main に入った後に頼む。
