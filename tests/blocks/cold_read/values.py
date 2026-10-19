"""試験の前の値（docs/design/cold-read.md の 8 節）。本文は例の run の 1 回目の初見の読み手が読んだ報告の頭（Archon の記録の
report__write-loop.cold-prep の node_output の body。対象の名だけ <owner>/<repo> に替えた）。返答は台本の 2 つ。"""

BODY = '''# 報告（run df5e111f-ea97-409b-8066-2245d32746ab）

起きたこと: 決めた判定から確かめまでの一巡の数のうちに直しきれずに止まった（round_limit）。TDD の実行器を作れなかった（test_cmd は tests/changed.py → tests/shard.py の unittest TextTestRunner（点の出力のみ）で、JUnit XML を書く指定（--junitxml 等）も xmlrunner の依存も無く、1 件ごとの結末を取れないため、緑を仮定せず作れない。）——TDD のループは回さない。JUnit XML を第 1 引数に書く実行器を入力 tdd_suite に渡せば回す。AI が書いた試験のコードを、利用者の資格に届く環境（利用者の HOME・XDG）で走らせた
差分を当ててよいか: PR を作った: https://github.com/<owner>/<repo>/pull/759（下書きの PR #759。merge は対象のレビューと決まりに任せる）
人が決めること: 15 件——許したテストの変更 13 件・直しきれずに残った物 2 件（1 件ずつ下の行。詳しくは見出しに「人が決めること」を持つセクション）
- 許したテストの変更: lib/tests/test_runreport.py
- 許したテストの変更: lib/tests/test_tree_run.py
- 許したテストの変更: lib/tests/test_userenv.py
- 許したテストの変更: tests/bin/test_isolate.py
- 許したテストの変更: tests/bin/test_launcher.py
- 許したテストの変更: tests/layers/test_block_paths.py
- 許したテストの変更: tests/shared/test_boundary.py
- 許したテストの変更: tests/workflows/test_chain.py
- 許したテストの変更: tests/workflows/test_judge.py
- 許したテストの変更: tests/workflows/test_line.py
- 許したテストの変更: tests/workflows/test_merge.py
- 許したテストの変更: tests/workflows/test_report.py
- 許したテストの変更: tests/workflows/test_test_gate.py
- 直しきれずに残った物: 修正に関わっていない AI の見直し R1: R1 が fix-needed: 考えの置き場所: 「対象のコマンドの環境で起こすコマンドの数え上げ」の置き場所は、この差分自身が docs/design.md の「対象のコマンドの環境と準備」（docs/design.md:600）と決めています。そこには「数え上げはこの 1 か所に置き、ほかの文書と docstring は性質で言ってここを指す」と書かれています。ところが lib/tree_run.py の docstring の 4 か所（outside_env の 2 句、split_mark、run）が、呼び手 pr-commit を名指しで数え上げ直しています。これにより、知る所が置き場所の外に増えました。同じく、outside_env が何をするか（HOME・XDG を戻す／uv の足した物を外す／読むだけの gh を頭に置く）の置き場所は lib/tree_run.py:103-119 です。それを pr_commit.py の docstring が中身ごと言い直しています（前の版はこのうち read_gh_first の 1 項だけを言っていた）。merge の inputs の description も、印のファイル名の字 user-env-ran（置き場所は lib/userenv.py:26 の RAN_FILE）を知る所を 1 つ増やしています。前段のコメントの候補 3 件はどれも、名指された「同じ内容の在り処」が実在することを確かめました。pr_commit.py の行末コメント 2 件は docstring の 14-15 行と同じことを言い、試験の shell_env の docstring は辞書の鍵を並べ直しただけなので、削ります。どれも字を削るだけの零処方で閉じ、振る舞い・試験・導出は落ちません。処方そのものは正当化されています。採った処方（drop_runner_env → outside_env → MARK を外して直前に置く、および 3 つの YAML と chain-start での結び）は judgment.json の prescriptions に零処方と単独の機構の棄却理由が付いています。修正案から外れた点（split_mark・place_mark を tree_run に置き、hook_env を残さない）も問題ありません。split_mark は _launch の中に書かれていた MARK を外す式を 1 か所にまとめたものです。place_mark は既存の _place_mark を公開しただけで、新しい考えは足していません。未使用の公開の名は、名で Grep して判じました（最後の試験の証拠は test_cmd の通しを走らせただけで、未使用の名を警告する検査の段を走らせたとは言っていないため）。split_mark・place_mark はどちらも _launch と pr_commit が使っており、使い道の無い名は在りません。判定の役が立てた問いの一覧は空で、逃げ道は在りません。人の方針の文書は名指されていない（空）ので、照らす方針は在りません。
- 直しきれずに残った物: 修正に関わっていない AI の見直し R3: R3 が redesign-needed: 整合の欠け（docs 追従）: 判定から確かめまでの一巡の鎖も run の共有の置き場の作り手になり、workflows/AGENTS.md:25 は『一番上のグラフ（メイングラフと判定から確かめまでの一巡の鎖）の始めの処理の段が作って入力で渡す』に直したのに、同じ考えを述べる docs/design.md:211 は『メイングラフの run の共有の置き場…メイングラフの始めの処理の段 start が作って…』のまま。同じ文書の 462 行付近と 436 行は鎖を含める形に直っているため、文書の中で割れている。README.md:73 の『試験・受け入れ・TDD の試験のコマンドが利用者の HOME・XDG で走る』の一覧にも、pr の commit のフックが入っていない（design.md の数え上げは直したが、利用者が読む英文の一覧は直していない）。どちらも 1 行ずつの直し。考えの置き場所: 置き場所の外へ新しい知る場所は増えていない。印の置き場の考えは lib/userenv.py と lib/tree_run.py の split_mark・place_mark に 1 つで、pr_commit.py は呼ぶだけ。hook_env のAI を起こす仕組みも消えて、MARK を外す処理と置く処理の写しは無い。名・規約・界面の整合は、入力 user_env_dir が merge の YAML・chain の YAML・line の YAML・各試験・design.md の対で揃っている。なお launcher.py のコメント、bin/AGENTS.md、userenv.py と tree_run.py の docstring は、数え上げを design.md の 1 か所に寄せる形で揃っている。

pr-commit が git commit のフックを走らせる環境を、他の「対象のコマンド」と同じ利用者の環境（HOME・XDG を戻し、読むだけの gh を PATH の頭に置く）に揃える直しを入れ、下書きの PR #759 まで作りました。最後のテストは緑です。ただし、修正に関わっていない AI の見直しのうち 2 つ（R1・R3）が、文書とコメントの重複・追従漏れを指して止まっています。どちらも字や 1 行の直しで、動作の欠陥ではありません。

## 人が決めること

2 種類 15 件あります。急ぐのは種類 B（2 件）で、PR #759 を merge する前に直すか決める必要があります。種類 A（13 件）は確認で、後でも構いません。

### A. 書き換えを許したテスト（13 件）

- 何を決めるか: 承認済みの案の範囲でテストを書き換えました。その 13 ファイルの変更を、そのまま受け入れてよいかを人が確かめます。
- 背景: 直しの本体は workflows/merge/scripts/pr_commit.py の `hook_env` を `tree_run.outside_env` に寄せることです。この寄せ方では印の置き場（入力 `user_env_dir`）を merge・line・chain の各 YAML で結ぶ必要があり、そのため各テストの期待も書き換わりました。対象は `lib/tests/test_runreport.py`・`lib/tests/test_tree_run.py`・`lib/tests/test_userenv.py`・`tests/bin/test_isolate.py`・`tests/bin/test_launcher.py`・`tests/layers/test_block_paths.py`・`tests/shared/test_boundary.py`・`tests/workflows/` の `test_chain.py`・`test_judge.py`・`test_line.py`・`test_merge.py`・`test_report.py`・`test_test_gate.py` です。
- 選択肢: 受け入れるなら、PR #759 のレビューでテストの差分を見るだけです。受け入れないなら、PR の該当ファイルを戻して直す手間が出ます。
- 推し: 判定のファイルにこの件の推しは書かれていません。最後の先へ進めるかを決める所（gate-final）の答えは「許したテストの 14 件は承認済みの案の範囲」でした。
- 決めないと: PR は下書きのまま残ります。merge は対象のレビューと決まりに任せる扱いです。

### B. 直しきれずに残った物（2 件）

どちらも、最後の先へ進めるかを決める所の答えは「文書だけの直しなので、作られた PR の上で直す」でした。PR #759 上での直しを誰がいつ行うかは、記録に書かれていません。

**B1. R1（fix-needed）: コメントと説明文の重複を削る**

- 何を決めるか: 重複しているコメントと説明文 9 件を削る直しを、PR #759 に足すか。
- 背景: 「対象のコマンドの環境で起こすコマンドの数え上げ」の正本は docs/design.md:600 の 1 か所と決めています。ところが lib/tree_run.py の説明文 4 か所が呼び手 pr-commit を名指して数え直しています。pr_commit.py の説明文は outside_env の中身を写しています。
- 削る対象（詳しくは「R1〜R4 の判定と理由」）: 説明文の言い直し 6 件、`pr_commit.py` の行末コメント 2 件、試験 `shell_env` の説明文の列挙 1 件。
- 選択肢: 削れば、後で outside_env を変えたときに一緒に直す場所が減ります。削らなくても、動作・テストは変わりません。
- 推し: 判定のファイルに推しは書かれていません。R1 は「字を削るだけの直しで閉じる」と見ています。
- 決めないと: 何も壊れません。重複が残ります。

**B2. R3（redesign-needed）: 文書の追従漏れ 2 か所を直す**

- 何を決めるか: 次の 2 か所を PR #759 に足して直すか。
  1. docs/design.md:211 は「メイングラフの始めの処理の段 start が作る」のままです。直した workflows/AGENTS.md:25 は「メイングラフと判定から確かめまでの一巡の鎖」になっており、同じ文書の 436・462 行付近も直っているので、文書内で食い違っています。
  2. README.md:73 の「利用者の HOME・XDG で走るコマンド」の一覧に、pr の commit のフックが入っていません。
- 選択肢: 直せば文書が揃います。直さなければ、利用者が読む README が実際の動作より狭く見えます。
- 推し: 判定のファイルに推しは書かれていません。R3 の所見には「どちらも 1 行ずつの直し」とあります。
- 決めないと: 動作は変わりません。文書の食い違いが残ります。

## 語の定義（機械が付けた。本文の外）

- outside_env: lib/tree_run.py の関数。HOME・XDG を利用者の物に戻し、uv が足した物を外し、読むだけの gh を PATH の頭に置いた、対象のコマンド用の環境を作る。
'''

PASS = {"verdict": "pass", "stops": [], "guessed": [], "decidable": True}
REDESIGN = {"verdict": "redesign-needed", "stops": ["「round_limit」が何かを言わずに出している。", "「A・B の 2 節」の中身が本文に無い。"],
            "guessed": ["「tdd_suite」は試験の入力の名だろうと推した。"], "decidable": False}
