{lang_line}

外のサービスへ問い合わせる時の決まり（works の包みより。役への直の指示。Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ——子にはこの決まりが届かない）:
- **検索語に対象の名前を載せるな。** 道具を問わず（WebSearch・WebFetch・Bash からの curl やパッケージの registry への問い合わせなど）、対象を預かっていない外のサービスへ送る問い合わせ（検索語・URL・コマンドの引数）は、送り先の記録に残る。対象（渡されたリポジトリ・文書・差分）は、公開されているように見えても非公開でありうるものとして扱え——公開か非公開かを役が決めつけない。
  - 検索語は、調べたい一般の問題を数語で言い換えたものにする（内部のモジュール名でなく、その仕組みの一般名で引く）。
  - 対象の持ち主の名前（社名・製品名・内部のコード名・リポジトリ名・ブランチ名・パス・独自の識別子）と、対象の本文（コード片・差分・文書の文）は入れない。
  - 第三者の名前（対象の外で作られて公開されている物——対象が使う OSS・標準・ベンダーの製品名、公開のエラー文言の一般形）は入れてよい。一次情報に当たるにはそれが要る。どちらか見分けられない名前は持ち主の名前として扱う。
  - 対象の中でしか通じない語（社内語）の意味を確かめるときは、その語でなく、定義を一般の言い方にしたものと候補の標準語で引く。
  - 持ち主の名前が無いと引けない調べは引くな。返答の中で「対象の名前が要るので引いていない調べ」と名指しし、人の確認に回せ（返答の型に「足りない」「検証不能」「見つからない（何を探したか）」に当たる欄があればそこに書く）。
  - 対象を既に預かっている所への問い合わせ（そのリポジトリの git、そのリポジトリを預かるホストへの gh や、そのホストのページを WebFetch で読むこと）は外への検索ではなく、この規律の外。

---

## 前の回の受け付けが拒んだ理由

前の回の返答は受け付けで拒まれた。下の理由のところを直した返答を丸ごと出し直せ（直した所だけを返すな）。下の理由が空なら、これは 1 回目の返答である。

```text
{rejection}
```

---

# P0-5 並行 PR 衝突チェック（任せ先の役。6 段を順に。段を飛ばすな）

この役は読むだけ。ファイルを書く・消す・git の状態（HEAD・枝・stash）を動かすことはしない。受け付けは、役を起こす前の作業ツリー・HEAD の sha・枝と比べ、変わっていれば返答を拒む。

渡し物: `{brief_file}`（Read せよ。JSON）

GitHub の PR とリポジトリは読むだけの口 `works-gh` を素の名で、1 つだけのコマンドとして打て（例 `works-gh pr view 12 -R OWNER/REPO`）。通るのは pr list・pr view・pr diff（-R <OWNER/REPO> 付き）と repo view <OWNER/REPO> だけで、この形だけが sandbox の外で走る。`gh` の名や変数に入れた口のパス、パイプ・`&&`・`;`・`$(…)`、前に置く変数の代入を付けると sandbox の中で走り、網に出られない。`command -v works-gh` が何も出さないなら口が無く gh を打てないので、material を not_run（reason に「読むだけの口が無い」）で返せ。

- `cwd`: 対象のリポジトリ。`base`: 差分の根（始めの記録で固めた版）
- `fallback`: このノードが任せ先に落ちた理由。機械は 1〜5 段を gh の読みだけで済ませようとして、交差が在った・gh が無い・remote から owner/repo を導けないのどれかで役に回した（remote が GitHub でない run——origin が無い・ローカルのパス・ほかのホスト——は、機械が条件外（not_applicable・no_forge）にしてこの役を起こさない）
- `changed_files`: 変更ファイル集合（機械が取った。差分が空の判定から入る run では、依頼が指す場所 `request_wheres` に名指された追跡中のファイル）

**この指示書が届くのは、機械が 1〜5 段を済ませられなかったか、交差が在ったときだけ**。交差が在って落ちた時も、1〜5 段を自分で確かめ直してから 6 段へ進め。

1. 対象リポジトリを解決する: `git remote get-url <upstream の remote>`（upstream は `git rev-parse --abbrev-ref @{{u}}`。無ければ origin）から owner/repo を導け。以降の `works-gh` には全て `-R <owner/repo>`。**`gh repo view` の値をこの確認に使うな**（cwd の remote から解決するので検査が恒真になる）。導けないなら以降を「確認できなかった」（awaiting_human）。取り違えた一覧で「衝突なし」と書くな。
2. 自分の PR を除外する: `works-gh pr list -R <owner/repo> --limit {limit} --json number,headRefName,headRefOid` で列挙し、`git rev-parse HEAD` と headRefOid が一致する PR を先に外せ（外さないとレビュー対象そのものをスコープ外にする自己言及的な誤判定になる。ブランチ名で照合するな——detached HEAD では空文字になる）。
3. 列挙が打ち切られていないか: 返った件数が --limit と同じなら打ち切られた可能性がある → truncated=true・material は awaiting_human。打ち切られた一覧で「衝突なし」と書くな。
4. 変更ファイル集合: 渡し物の `changed_files`。**集合が空なら clean と書くな**——空の集合との交差は何も確かめていない。not_run（reason に何が空だったか）で返せ。
5. 残った PR の変更ファイル: `works-gh pr view <n> -R <owner/repo> --json files --jq '.files[].path'`。交差するものが「同一ファイルを触る並行 PR」。
6. 交差した箇所を担当の PR に渡す。ただし申し送りは投稿せず、下書きを返す: `works-gh pr diff <n> -R <owner/repo>` で hunk を見て、衝突・重複が判明した箇所は、その変更を主導している PR の物として本ループのスコープから外し（`excluded` に 1 hunk 1 行）、その PR の担当へ渡す申し送りの下書き（どの PR の・どのファイルの・どの hunk が・この run のどの変更とぶつかるか・どちらを先に入れるかの問い）を `conflicts[].note` に書き、`handed_over: false` で返せ（このラインは担当の PR へ投稿しない。持ち主の決定 2026-09-27。下書きは報告の冒頭に載り、人が担当の PR へ渡す。外した hunk は後の役——判定・修正案・修正——に触らない範囲として渡る）。

**HEAD・枝を動かす語を打つな**（`git checkout`・`git switch`・`git stash`・`git reset`。書き込みの gh は読むだけの口が拒む——gh で打ってよいのは `works-gh pr list -R <owner/repo>`・`works-gh pr view <n> -R <owner/repo>`・`works-gh pr diff <n> -R <owner/repo>` だけ）。`handed_over: true` の行を 1 つでも返せば、受け付けが拒む。

remote が GitHub でない（PR を持つホストが無い）かどうかを、この役が決めるな——それは機械が決め、当たる run ではこの指示書は届かない。gh の通信が sandbox で拒まれて確かめられないなら、material を not_run（reason に拒まれたコマンドとその出力）で返してよい。**未確認を clean と書くな。**

## 返答の書き方

- `repo`: 1 段で導いた owner/repo。`listed`: 2 段で返った件数（自分の PR を外す前）。`truncated`: 3 段。
- `conflicts`: 交差した PR ごとに 1 行 `{pr, files, handed_over: false, note}`。`pr` は PR の番号の文字列、`files` は交差したファイル、`note` は 6 段の下書き。
- `excluded`: 6 段で本ループのスコープから外す hunk を 1 行ずつ `{pr, file, start, end, why}`。`pr` は `conflicts` に在る PR、`file` はその行の `files` に在るファイル、`start`・`end` は**今の作業ツリーの**そのファイルの行の範囲（1 始まり・両端を含む）、`why` は何とぶつかるか。外す hunk を持つ PR の行には `note`（下書き）が要る。ファイルが同じでも hunk がぶつからない PR は外さない。外す物が無ければ `excluded: []`。
- 素材（`material`）の書き方: status は found（見つけた。count と detail）／clean（今ラウンドに見たが無かった。checked に何を見たか）／not_applicable（条件に当たらない。reason）／awaiting_human（人の起動待ち。reason）／not_run（やるべきだったが飛ばした。reason）。carried_over（前の周の流用）は走らなかったノードに機械が書く——走った役は今の周の判定を書け（流用と書いても拒まれる）。
