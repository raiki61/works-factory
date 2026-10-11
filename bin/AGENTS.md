<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」の節で定義 -->
# 入口（`bin/`）の決まり

`bin/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E15 起動の認証と隔離は今の works から持ってきた物を使う

- 認証の切り替え（今の works の `works/.shared/core/auth_launch.py`・`claude_auth.py`）、置き場の隔離（`works/dev/archon.sh` の、HOME・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`・`XDG_*` を run の置き場へ向ける所）、隔離した Claude に見せるプラグインの選び（`works/dev/toolset.py`）を、その試験ごと `bin/_lib/` に持ってくる。作り直さない。持ち主の決め `bring-launch`。
- Archon は `factory/pack.json` の `integration_revision_required` の源から `bun` で起こす。源の取り寄せと起こす命令は `bin/_lib/place.py`（`archon_source`・`workflow_source`・`workflow_run`）を使う。`archon.sh` の実行ファイルの取り寄せは持ってこない（持ち主の決め `archon-same-as-asf` で公開版の実行ファイルは使わない）。
- 今の works の打つ口（`works/dev/use.sh`・`lib.sh`・`launch.py`）は持ってこない。Archon の CLI と `bin/` の薄い口で置き換える。
- 持ってきた物の中の、今の works だけの事情（写しの同期の説明・works の置き場の名）は、works-factory の言葉に直す。直した所は commit に書く。
- 人が見る。
