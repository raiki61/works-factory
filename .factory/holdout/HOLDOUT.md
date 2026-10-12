# 別の組み合わせの筋書き（holdout）

works-factory を、通しの筋書き（`harness/runtime.scenario.json`。人が読む要約は `harness/END-TO-END.md`）とは別の組み合わせと端の場合で確かめる筋書き。works-factory は修正の工場で、人は入口の殻 `bin/works-factory` で Archon の命令をそのまま打ち（`workflow run works-factory-line` で依頼を渡して run を始め、`workflow respond` で止まった所で答え、`workflow wait`・`workflow get` で今どこか・報告を見る）、`bin/apply` で封じた差分を当てる。run は、工場が 1 つの依頼を受けてから報告を出すまでの 1 回の実行。人の関所は、人に答えを聞いて止まる所。works-factory は Archon（AI の工程を YAML で書き、順に回す道具）の上で動く。

## 読む前に

- このリポジトリを作っているのは ASF（Archon の作者が作った、issue から merge までの工程の束）の AI で、このファイルはその AI も読める。だから隠しの確かめ（holdout）にはならない。機械が読む形の JSON はリポジトリの外（運び役の機械の `${XDG_STATE_HOME:-$HOME/.local/state}/works-factory/holdout/runtime.holdout.json`）に置き、確かめる側にだけ渡す。
- ASF の工程 `archon-lifecycle` には、入力 `holdout` を空で渡す。lifecycle は別筋が空ならその確かめを飛ばし、筋書きだけで判定する。下の 3 つの筋はどれも本物の通しを 1 回ずつ要り、PR ごとに回すと 1 つの PR の確かめに通しが 4 回走る。別筋は段 1 で 1 度だけ本物で回して確かめ、PR ごとには回さない。
- 対象・依頼・家は `python3 tests/e2e/make_target.py make <試みのフォルダ>` で作り、run の起こし方・待ち方・関所の答え方は筋書きの JSON の `request-to-report` の手順と同じ（線を起こす命令は `--detach` を付けずに前で打ち、関所の答えは `workflow respond <run> … --detach` で打つ）。`bin/works-factory` と `bin/apply` の呼び出しには毎回 `WORKS_FACTORY_HOME=<家>` を前に付ける。

## 2 つの依頼を同じ対象に続けて回す

1. 対象に依頼 A を回して最後の関所まで通し、`./bin/apply <run> --cwd <対象>` で当てる。
2. 対象で A の直しを commit し、origin に push する（run の作業ツリーは origin の枝から切られるので、当てただけの A の上には B が乗らない）。
3. 同じ対象に、A で直したファイルに触る依頼 B を回し、同じく当てる。
4. 種の試験を走らせる。

期待: B の差分は A の直しの上に乗る（A の前の中身に戻さない）。A と B が直してほしいとした試験が両方とも通り、前から通っていた試験は 1 件も落ちない。

## 関所で待っている間に Archon を起こし直す

1. 依頼を回し、最初の人の関所で止まったら、Archon の process を止めて起こし直す。
2. `./bin/works-factory workflow get <run> --cwd <対象>` で、その run が同じ関所で待っていることを見る。
3. `./bin/works-factory workflow respond <run> approve --detach --cwd <対象>` で通す。

期待: run は始めからやり直さず、関所の後から続いて報告まで届く。報告に、関所での答えが載る。

## 最後の関所で拒むと何も当たらない

1. 依頼を回し、最後の関所で `./bin/works-factory workflow respond <run> reject --detach --cwd <対象>` と拒む答えを返す。
2. `./bin/apply <run> --cwd <対象>` を呼ぶ。
3. `./bin/apply <run> --cwd <対象> --allow-stopped` を呼ぶ。

期待: 2 の `./bin/apply` は、置いた差分が無いと言って 1 で終わり、対象のリポジトリの作業ツリーは変わらない。`workflow get` が出す結末の語は `stopped_by_human`（人が拒んだ）。3 の `--allow-stopped` を付けると、封じた差分が当たる。
