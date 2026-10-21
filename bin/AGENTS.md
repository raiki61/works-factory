<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# 入口（`bin/`）の決まり

`bin/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E15 起動の認証と隔離は今の works から持ってきた物を使う

- 認証の切り替え（今の works の `works/.shared/core/auth_launch.py`・`claude_auth.py`）、置き場の隔離（`works/dev/archon.sh` の、HOME・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`・`XDG_*` を run の置き場へ向ける所）、隔離した Claude に見せるプラグインの選び（`works/dev/toolset.py`）を、その試験ごと `bin/_lib/` に持ってくる。作り直さない。持ち主の決め `bring-launch`。対象のコマンド（`lib/tree_run.py` の `outside_env` の env で起こすコマンド。数え上げは `docs/design/archon.md` の「対象のコマンドの環境と準備」）だけ、隔離の前の HOME・`XDG_*` に戻して走らせる（持ち主の答え。`docs/owner-decisions.md` の `target-user-env`）。殻はいつも隔離の前の値を控え（旗は無い）、戻すのは対象のコマンドの env だけ（控えと戻しは `lib/userenv.py`）。AI が書いた試験のコードは利用者の権限で走り、書く物も利用者の家に入るので、殻は実行する run のたびにそれと、守りが要るなら工場ごとコンテナか VM の中で回す道を起動の 1 行で告げる（`bin/_lib/launcher.py` の `TARGET_ENV_NOTICE`）。報告の冒頭の句は、対象のコマンドを実際に戻して起こした run だけが言う（印は `lib/userenv.py` の `RAN_FILE`。一番上のグラフ（メイングラフと周の鎖）の run の place に置く）。Archon・役の Bash・工場の script 自身（`outside_env` の env で起こす子を除く）は隔離のまま。今の works の works/.shared/core/record-read.py（包み adapter.py の読んだ証拠のフック）を bin/_lib/record-read.py に持ってくる。
- 止めた Archon（`docs/design/archon.md`）を `bun` で起こす。源の取り寄せと起こす命令は `bin/_lib/place.py`（`archon_source`・`workflow_source`・`workflow_run`）を使う。`archon.sh` の実行ファイルの取り寄せは持ってこない（持ち主の決め `archon-same-as-asf` で公開版の実行ファイルは使わない）。
- 今の works の打つ口（`works/dev/use.sh`・`lib.sh`・`launch.py`）は持ってこない。人は Archon の命令をそのまま、起動の殻 `bin/works-factory`（中身は `bin/_lib/launcher.py`）を通して打つ。殻は Archon の命令の別名を作らず、上の部品を `archon.sh` と同じ順でつなぐだけ（持ち主の決め `one-launcher`）。
- 殻は `--input test_cmd=` を照らさない。外し: 本線を `--input spec_table=<表>` で、block `works-factory-spec-driven` を `--input table=<表>` で起こす時だけ、殻は仕様駆動の道の表を読み（PyYAML を宣言した `bin/_lib/spec-inputs.py` を uv で起こす）、会話で回した部品の審査の記録を `workflow get <run> --json` で読んで照らし（`bin/_lib/specreviews.py`）、結果のファイルを run の設定の層の env で渡す。合わなければ Archon を起こさずに止める。Archon の run の記録を読めるのは殻だけなので殻に置く（持ち主の決め `spec-driven-shape`。docs/design/spec-driven.md の 2.6 の 2）。表を名指さない起動は表も記録も読まず、uv も起こさない。
- 殻は `--input test_cmd=` を照らさない。test_cmd の形の確かめ（今の works の `works/dev/testcmd_check.py`）は line の `workflows/line/src/testcmd_check.py` に在り、メイングラフの頭のノード `testcmd` が照らして、止める時は Archon の `cancel:` で run を止める（#678）。run の作業ツリーの起点（今の works の `use.sh` の start の包み）は、殻が `bin/_lib/startpoint.py` で決めた commit を `--from` に組み、作業ツリーは Archon が切る（殻は worktree を切らない）。
- 持ってきた物の中の、今の works だけの事情（写しの同期の説明・works の置き場の名）は、works-factory の言葉に直す。直した所は commit に書く。
- 人が見る。
