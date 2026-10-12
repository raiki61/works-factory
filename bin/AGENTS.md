<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」のセクションで定義 -->
# 入口（`bin/`）の決まり

`bin/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E15 起動の認証と隔離は今の works から持ってきた物を使う

- 認証の切り替え（今の works の `works/.shared/core/auth_launch.py`・`claude_auth.py`）、置き場の隔離（`works/dev/archon.sh` の、HOME・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`・`XDG_*` を run の置き場へ向ける所）、隔離した Claude に見せるプラグインの選び（`works/dev/toolset.py`）を、その試験ごと `bin/_lib/` に持ってくる。作り直さない。持ち主の決め `bring-launch`。今の works の works/.shared/core/record-read.py（包み adapter.py の読んだ証拠のフック）を bin/_lib/record-read.py に持ってくる。
- 止めた Archon（`docs/design.md` の「語」）を `bun` で起こす。源の取り寄せと起こす命令は `bin/_lib/place.py`（`archon_source`・`workflow_source`・`workflow_run`）を使う。`archon.sh` の実行ファイルの取り寄せは持ってこない（持ち主の決め `archon-same-as-asf` で公開版の実行ファイルは使わない）。
- 今の works の打つ口（`works/dev/use.sh`・`lib.sh`・`launch.py`）は持ってこない。人は Archon の命令をそのまま、起動の殻 `bin/works-factory`（中身は `bin/_lib/launcher.py`）を通して打つ。殻は Archon の命令の別名を作らず、上の部品を `archon.sh` と同じ順でつなぐだけ（持ち主の決め `one-launcher`）。
- 持ってきた物の中の、今の works だけの事情（写しの同期の説明・works の置き場の名）は、works-factory の言葉に直す。直した所は commit に書く。
- 人が見る。
