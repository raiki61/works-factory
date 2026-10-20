# 借りた superpowers のスキルを無人の役で読むときの読み替え

対象は、works に写した superpowers（`lib/borrow/superpowers/<版>/`。版・commit・ファイルごとの sha256 は `borrow.json` の `pin`）のスキルのうち、借りる 2 本（`lib/borrow/borrow.json` の `skills`。`bin/_lib/toolset.py` が隔離した設定の `skills/` に写す）と、部品（スキルとしては使わず、中の型を役の指示書の骨に使うファイル。`borrow.json` の `parts`）。写しは直さない。版を上げるのは `bin/_lib/toolset.py vendor` だけ。借りた物を役に載せる時の包み方（セクションごとの使い道・錨・穴・出口の語）は、包むセクションの表 `lib/borrow/seams.json` が持つ。スキルの文が人（your human partner）や調整役（下請けの AI を起こす親の会話）を前提にしている所は、works の無人の役ではこのファイルの決まりで読み替える。スキルの文とこのファイルがぶつかったら、このファイルが勝つ。さらに、役の指示書（`workflows/*/commands/*.md` と、支度のノードが組んで役に読ませる指示書）とノードの `output_format` は、このファイルより勝つ。

この読み替えは、役の種類ごとのセクション（`###` の見出しが種類の名を `・` で並べる）と、種類の見出しの外の全部の役に共通の文から成る。機械（`lib/seat.py` の `skill_overlay`）が、役の側が宣言した種類のセクションと共通の文だけを、借りたスキルを読める役と借りた型を骨にする役の指示書の末尾に載せる（superpowers の using-superpowers は、役への直の指示がスキルに勝つと定める）。載るセクションは `lib/tests/test_seat.py` と `tests/workflows/test_judge.py` が見張る。

## 読み方

- 下の見出しが読み替えの決まり。行の番号やスキルの文そのものには結び付けない（版を上げると文が変わりうる。決まりと写しの原文の結び付き（錨）は `seams.json` が持ち、試験が写しに当てて縛る）。当てはまる言い回しを見たら、その決まりで読む。

## 義務の単位の行き先（どの決まりもこれに従う）

### 修正の役

修正の決まりの正本（機械がこの役の指示書に組み込む）と同じ行。受け付け（`fix_covers_open_units`）は、直す義務の単位が `changes` に無ければ、`not_done` に理由を書いても拒む。

- **義務の単位の行き先**: 直す義務の単位（[block] と do-now）は、必ず直して `changes` に 1 行で載せる（人の答えが無いと直し方が決まらない単位だけは、直さずに「食い違いの申し出」で返す）。判定の前提・直し方に疑いが残っても、方針に反しない範囲で一番ましな直しを載せ（根を塞げなければ `root_or_symptom` を symptom にして why に理由を書く）、それが判定のフレーミングへの異議なら `rejudge_requested` に書く（次の判定で読み直される）。`not_done` に書けるのは、受け付けが免除する単位（問いの台帳で、修正の前にまだ答えていない（人の答えも無人の run が採った推しも無い）fork の出どころか depends に挙がった単位。status が escalate の問いも同じ。答えた問いの出どころ・depends は免除されない）と、義務の外の単位だけ。

## ASK 人に聞く・確かめてもらう・許しを得る

無人の役には聞く相手が居ない。止まって答えを待たない（待っても答えは来ず、受け付けのループが上限まで回って run が落ちる）。分からない項目があるうちは実装を始めない、という原則（receiving-code-review）はそのまま効く。分からない項目は下のとおり返答に書き、分かった項目だけを直す。

### 修正の役

- 上の「義務の単位の行き先」に従う。直す義務の単位は、分かる範囲で一番ましな直しを `changes` に載せる。人の答えが無いと直し方が決まらない単位は、直さずに食い違いの申し出（`conflicts`。`which_is_right` は unknown・`kind` は `needs_context`）で返す——人に回り、最後の承認ノードに届く（修正の決まりの正本の「食い違いの申し出」）。`rejudge_requested` は判定のフレーミングへの異議だけで、人への問いを書かない。義務の外の単位は `not_done` に理由を書いてよい（`unit_key`・`why`）。

### 修正の役・TDD の役

- test-driven-development の「Ask your human partner」と、部品の実装役の型の「Ask them now」「ask questions」は、止まらずに食い違いの申し出で返す。状態の語「NEEDS_CONTEXT」・「BLOCKED」も申し出に当たる（`seams.json` の `words`）。

### TDD の役

- TDD の例外（使い捨ての試作・生成したコード・設定のファイル）に当たるかどうかは、役は決めない。役は先のテストを省かない。省いてよい単位はメイングラフの側（修正案の route と機械の決まり。TDD のノードが入ったら元の graphloops の fix-tdd の `route: direct`）が決める。

### 手直しの役

- 分からない穴は `declared` で残し、`how` に何が分からないかを書く。

### 読むだけの役

- 分からないまま置いた前提を、返答の型の中の理由の欄に書く。

## POLICY 人の決めたこと・方針とぶつかる

自分の判断で通さない。方針の文書は書き換えない。

### 修正の役

「義務の単位の行き先」に従う: 直す義務の単位は、方針に反しない範囲の直しで閉じるならそれを `changes` に載せ、閉じないなら直さずに食い違いの申し出（`between` に方針の文書の行を含め、`which_is_right` は unknown・`kind` は `needs_context`）で人に回す。義務の外の単位なら `not_done` に書く。

### 手直しの役

`declared` の `how` に書く。

## COMMIT commit・push・PR・merge

役は commit しない。`git add`・`git commit`・`git stash`・`git reset`・`git checkout` で作業ツリーや履歴を動かさず、差分は作業ツリーに残したまま返す。push・PR・merge は役の仕事ではない（メイングラフの後ろのサブグラフと承認ノードが持つ）。「commit の前に確かめる」は「返答を返す前に確かめる」と読む。

部品の型の「Commit your work」と worktree を作る指示はメイングラフが持つ。役は差分を作業ツリーに残して返す。

## SUITE 一式（project's suite・full suite）を回せと言われる

役は一式を回さない。一式はメイングラフが渡す `test_cmd`（速い段）を機械が関門として回す。重い段・変異テストは CI だけが回す。役が回すのは、変えたファイルに当たる試験だけ（絞る手が無い時だけ、返答の直前に一式を 1 回だけ回す）。

## SP-REF `superpowers:` の名前での参照

無視する。Archon はプラグインを読まないので、`superpowers:` の付いた名前では何も読まれない。同じ名前のスキルが隔離した設定に在り、ノードが `skills:` に宣言していれば、`superpowers:` を除いた名前で Skill の道具から読める。宣言されていなければ読まない。

## DISPATCH 下請けの AI を起こす・調整役として振る舞う

スキルの文に従って下請けを起こさない。Agent を持つ役が起こすのは、指示書が名指す物だけ。別の目の審査は、メイングラフの別のノードが新しい会話で受け持つ。

## DELEGATE エージェントの報告を信じない

役の返答は、engine（受け付けのノード）が差分と試験を自分で確かめ直す。役は「確かめた」と書くなら、走らせたコマンドとその結果を返答に書く。役がほかのエージェントに仕事を任せることは無い。

## GIT-RANGE git で審査の範囲を取る・差分を出す

`git worktree add` はしない。Bash を持つ役は git で読む（`git diff`・`git log`・`git show`）のはよいが、HEAD・index・枝は動かさない（決まり COMMIT）。

### 審査の役

Bash を持たない（`allowed_tools` は Read・Grep・Glob）。範囲の版と差分は engine が切ってファイルで渡すので、そのパスを Read する。

## CRAWL 差分の外を読むな・変わったファイルを別に読むなと言われる

部品の審査役の型（`task-reviewer-prompt.md`）の「Do not crawl the broader codebase」と「do not Read a changed file separately」は、役の指示書が読む義務を定める役には効かない（指示書の読む義務が勝つ）。指示書が読む義務を定めない役（下請けの審査役）は型のとおり。

### 審査の役

差分を起点に、変わったファイルの今の姿と、読む側・呼び元まで Read・Grep で読む。

## GITHUB GitHub のスレッドに返信する

しない。返答はノードの `output_format` の JSON だけで、外へ書き込まない。

## PUSHBACK 審査の指摘に反論する

相手に話しかけない。反論は返答の欄に書く。理由には確かめた事実（ファイルと行・走らせた試験）を書く。

### 手直しの役

穴の key ごとに `declared` と、`how` に技術的な理由を書く。

### 修正の役

「義務の単位の行き先」に従う: 直す義務の単位への反論は `rejudge_requested` に書き、その単位は `changes` に載せる。義務の外の単位なら `not_done` に書く。

## QUOTE 人の言葉の引用・人との会話の例

引用と例に込めた原則（分からない項目があれば実装を始めない・外の審査は確かめてから直す・要らない物は作らない・モックでなく本物の振る舞いを試す）はそのまま効く。会話の相手は居ないので、例の「聞き返す」は決まり ASK で読み替える。

### 手直しの役

receiving-code-review の「From your human partner」は、works では判定が出して受け付けが通した単位に当たり、「From External Reviewers」は差分の審査の指摘に当たる。

## OUTPUT 返答の形

部品の型（`implementer-prompt.md` の報告・`task-reviewer-prompt.md` の最終の返答）の返答の形より、ノードの `output_format` の JSON の型が勝つ。merge してよいかは役が決めない。
