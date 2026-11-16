# 起動の前の確かめを 1 回にまとめる（設計の相談）

起動の殻 `bin/works-factory`（中身は `bin/_lib/launcher.py`）が、足りない物を 1 つ見つけるたびに止まり、AI が打ち直しを 4 回重ねた。
この文書は、足りない物を 1 回で全部並べて止める形と、版管理の道具の shim（`PATH` に置かれた代わりの実行ファイル）と、
Claude Code の会話の中から打った時の認証の案内の、案・代案・残る問いを書く。実装はまだ始めていない。

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

訳は 3 つ:

- 殻の止まる所が順に並び、最初の 1 つで止まる。bun の確かめ（`place.archon_source` の頭）→ 源の取り寄せと `bun install` →
  …→ 認証の確かめ（`launcher.launch` の `auth_launch.py check`）の順で、認証は源を取った後でしか見ない。
- 「在るか」だけを見て「起きるか」を見ない。shim は在るので通り、`bun install` の中で落ちる。落ちた時の 1 行は
  `CalledProcessError` の字だけで、道具が言った直し方の行は別の所に流れて捨てられる。
- 止まった訳の字（`keychain-error(FileNotFoundError)`）が「この OS には keychain が無い」と言わず、直し方の文（`HOWTO`）は
  あらゆる道を 1 段落に並べ、この場面の道（会話の中の Bash にはトークンが渡らない時の道）が埋もれる。

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
- 確かめが全部通った後の失敗（網に届かない・`bun install` が別の訳で落ちる）は、今のまま 1 つで止まる。その時の 1 行に、`bun install` の標準エラーの
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

案 C1（採る）: 名指しの項目が読めない訳を字にする。`WORKS_FACTORY_KEYCHAIN_ITEM` が在り、`security` が無い（macOS でない）時の訳を
「keychain は macOS だけで、この OS には `security` が無い。この OS ではこの名を外して打つ（設定の `env` に書いたなら、その起動では
`unset` する）」にする。止めるのは今のまま（持ち主の決め `api-key-helper-relay` の、名指した道を黙って別の口に差し替えない向き）。

案 C2（採る）: 止まる時の 1 行を、訳 → この OS とこの場面の短い直し方 → 一般の文（今の `HOWTO`）の順にする。Linux で、受け継いだ認証も
`.credentials.json` も無い時の直し方は「Claude Code の会話の中の Bash には、その会話のログインのトークンが渡らない（`claude auth status` の
`loggedIn` が false になる）。`claude setup-token` で作った長期のトークンを、打つ命令の前で `CLAUDE_CODE_OAUTH_TOKEN` に置く」。
(a) の箇条に入るのはこの短い形で、一般の文は工場の README の認証の項目を指す。

案 C3（このリポジトリの外）: プラグインのスキルの本文（`raiki61/claude-plugins` の works-factory プラグインの `references/auth.md`）に、
「Linux と、Claude Code の会話の中から打つ時」の項目を足し、C2 と同じ道を先に書く。工場の文と同じ字にする。

代案 C4（持ち主の選び）: トークンを出すコマンドを名指す env（たとえば `WORKS_FACTORY_OAUTH_TOKEN_COMMAND`）を足す。殻は `apiKeyHelper` と同じに、
exec の 1 回だけ利用者の HOME・XDG で起こし、標準出力を `CLAUDE_CODE_OAUTH_TOKEN` として子に渡す（値は表示も保存もしない）。設定の `env` に書けば、
会話の中の Bash（裏の会話も）で毎回の手の配線が要らなくなる。新しい選べる道なので、E10 の決めを先に書く。段の位置は環境の
`CLAUDE_CODE_OAUTH_TOKEN` と同じ（`apiKeyHelper` の後）を推す。

代案 C5（推さない）: keychain の無い OS では名指しを 1 行告げて飛ばし、下の段へ進む。持ち主のように macOS と Linux で同じ設定の `env` を使う人は
外し忘れがなくなるが、`api-key-helper-relay` の向きと食い違う。

## 3. E11 の 3 つ

1. Archon が持っているか: `doctor` が点検を並べるが、bun の上で走るので bun が起きない時に打てず、工場の認証の段を知らない（A3）。持っていない。
2. ASF が持っているか: `factory/consumer.py` の `verify_source`・`doctor` は取り置いた源の形と命令の能力を照らすだけで、道具が起きるかと認証は見ない
   （`doctor` の返す値も `authentication not live-tested`）。持っていない。
3. 本当に要るか: 要る。止まるたびに AI が打ち直すので、1 回の run の前に 4 回の起動と、そのたびの文の読みが要った。直す所は新しい仕組みでなく、
   今ある止まる所の並べ方と字で、新しい置き場も常駐の物も足さない（C4 だけが新しい選べる道で、持ち主の選びに回す）。

## 4. 試験の計画（実装の時。直しを外すと落ちる試験を先に書く）

- `tests/bin/test_launcher.py`: 一時の `PATH` に、`--version` で終了 1 と決まった字を標準エラーに出す偽の `bun`・`node` を置き、認証も無い env で
  `launch` を打つ。止まりの字に bun・node・認証の 3 つの箇条が全部在り、源を取りに行っていない（偽の fetch が呼ばれない）ことを見る。
  今の殻では bun の 1 つで止まるので落ちる。
- 同じ所で、node が見つからない時は止めないこと、源が取り置き済みの時は node を見ないことを見る。
- `tests/bin/test_auth_launch.py`: `platform` を `linux` にし、名指しの項目が在って `security` が無い時の訳が「keychain は macOS だけ」を言うことを見る。
- `tests/bin/test_place.py`: `bun install` が標準エラーを出して落ちた時、`RuntimeError` の字にその末尾が載ることを見る。
- 手元は `tests/changed.py` だけを回す（`tests/AGENTS.md`）。

## 5. 残る問い

- C4（トークンを出すコマンドを名指す env）を足すか。足さないなら、会話の中から打つ人は C2 の案内のとおり命令の前で `CLAUDE_CODE_OAUTH_TOKEN` を置く。
- keychain の無い OS で名指しを見た時、止める（C1。推す）か、告げて飛ばす（C5）か。C1 なら、持ち主の Linux の設定の置き場の `env` から
  `WORKS_FACTORY_KEYCHAIN_ITEM` を外すのが要る（利用者の設定で、リポジトリの外）。
